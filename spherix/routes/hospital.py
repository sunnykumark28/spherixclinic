from spherix.services.upload_service import save_user_profile_image, upload_to_cloudinary, UPLOAD_CACHE
from fpdf import FPDF
import os
import sys
import json
import csv
import random
import copy
import uuid
import math
import time as time_module
import hashlib
import traceback
from datetime import datetime, date, time, timedelta, timezone
from io import BytesIO, StringIO
from functools import wraps
from urllib.parse import urlparse, quote_plus
from collections import Counter

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session, send_file, make_response,
    send_from_directory, Response, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from flask_login import login_user, login_required, logout_user, current_user

from spherix.config import (
    generate_captcha_text, generate_captcha_image_bytes,
    utcnow, parse_route_id, get_actual_user_id, format_dual_currency,
    convert_currency, get_currency_symbol, generate_user_license_id,
    BLOG_POSTS, allowed_file, SECRET_KEY, GLOBAL_CURRENCY_RATES,
    GLOBAL_CURRENCY_SYMBOLS, COUNTRIES_195, GLOBAL_COUNTRY_FLAGS,
    GLOBAL_COUNTRY_TIMEZONES, search_countries
)
from spherix.models import (
    Doctor, Patient, Staff, HospitalStaff, Hospital, BloodDonor, OrganDonor,
    Appointment, PatientVital, LabRequest, OrganRequest, BedBooking,
    Order, Review, Feedback, Message, ActivityLog, Referral, Notification
)
from spherix.services.database import (
    TEMP_DATA, get_db_connection, save_data, load_data,
    sync_data_to_sql, load_data_from_sql, create_notification, get_temp_data_item,
    deduplicate_entities, filter_hospitals_advanced, get_hospital_types,
    get_hospital_type_by_id, calculate_haversine_distance
)
from spherix.hospital_types import (
    HOSPITAL_TYPE_MASTER_DATA, MASTER_FACILITIES_LIST, HospitalType
)
from spherix.services.mail_service import (
    send_notification_email, send_notification_email_async, get_premium_otp_email_html
)
from spherix.services.payment_service import (
    verify_razorpay_signature, create_razorpay_order,
    get_razorpay_key_id, create_razorpay_payment_link
)
from spherix.services.pdf_service import (
    SpherixClinicalPrescriptionPDF, generate_spherix_clinical_pdf, to_latin1_str
)
from spherix.services.ai_service import (
    analyze_symptoms_locally, get_cache_key, _extract_json_payload,
    SYMPTOM_CACHE, ACTIVE_SYMPTOM_REPORTS, LAST_API_CALL_TIME
)
from spherix.routes.decorators import (
    patient_required, doctor_required, admin_required, hospital_required,
    staff_required, hospital_or_staff_role_required, staff_role_required,
    get_common_staff_data
)
from spherix.extensions import limiter, csrf, talisman, cors, jwt, oauth, socketio, razorpay_client

try:
    from audit_logger import log_medical_access
except ImportError:
    def log_medical_access(*args, **kwargs): pass

try:
    from policy_data import POLICY_DATA
except ImportError:
    POLICY_DATA = {}

try:
    from medicine_catalog import MEDICINES_CATALOG
except ImportError:
    MEDICINES_CATALOG = []

try:
    from prescription_ocr import extract_prescription_text
except ImportError:
    def extract_prescription_text(*args, **kwargs): return ""

try:
    from drug_data import DRUG_DATABASE
except ImportError:
    DRUG_DATABASE = {}

try:
    from ayurveda_catalog import AYURVEDA_KNOWLEDGE_BASE
except ImportError:
    AYURVEDA_KNOWLEDGE_BASE = {}

try:
    from disease_catalog import DISEASE_CATALOG
except ImportError:
    DISEASE_CATALOG = {}

hospital_bp = Blueprint('hospital', __name__)

@hospital_bp.route('/hospitals')
def hospitals_list():
    """Displays a list of registered hospitals with advanced multi-dimensional filtering."""
    all_hospitals = deduplicate_entities([
        h for h in TEMP_DATA.get('hospitals', {}).values() 
        if not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)
    ])
    
    # Query parameters
    search_query = request.args.get('q', '').strip()
    type_param = request.args.get('type', request.args.get('type_id', request.args.get('hospital_type', ''))).strip()
    specialty_query = request.args.get('specialty', '').strip()
    city_query = request.args.get('city', '').strip()
    state_query = request.args.get('state', '').strip()
    locality_query = request.args.get('locality', '').strip()
    country_filter = request.args.get('country', '').strip()
    scope = request.args.get('scope', '').strip()
    
    verified_raw = request.args.get('verified', '').strip().lower()
    verified_only = verified_raw in ['true', '1', 'yes', 'on']
    
    emergency_raw = request.args.get('emergency', '').strip().lower()
    emergency_only = emergency_raw in ['true', '1', 'yes', 'on']
    
    # Facilities multi-select list
    facilities_list = request.args.getlist('facilities') or request.args.getlist('facilities[]') or request.args.getlist('facility')
    if not facilities_list and request.args.get('facilities_csv'):
        facilities_list = [f.strip() for f in request.args.get('facilities_csv').split(',') if f.strip()]
        
    nearby_raw = request.args.get('nearby', '').strip().lower()
    nearby_only = nearby_raw in ['true', '1', 'yes', 'on']
    
    user_lat = request.args.get('lat', None, type=float)
    user_lng = request.args.get('lng', None, type=float)
    max_distance_km = request.args.get('distance', 50.0, type=float)
    view_mode = request.args.get('view', 'grid').strip().lower()
    if view_mode not in ['grid', 'list']:
        view_mode = 'grid'
        
    # Execute advanced filter engine
    filtered_hospitals = filter_hospitals_advanced(
        search_query=search_query,
        type_id=type_param,
        specialty=specialty_query,
        city=city_query,
        state=state_query,
        locality=locality_query,
        country=country_filter,
        scope=scope,
        verified_only=verified_only,
        emergency_only=emergency_only,
        facilities_filter=facilities_list,
        user_lat=user_lat,
        user_lng=user_lng,
        nearby_only=nearby_only,
        max_distance_km=max_distance_km
    )
    
    # Master types catalog and counts
    hospital_types = get_hospital_types(active_only=True)
    type_counts = {'all': len(all_hospitals)}
    for ht in hospital_types:
        type_counts[str(ht.id)] = sum(1 for h in all_hospitals if str(getattr(h, 'hospital_type_id', 1)) == str(ht.id) or (getattr(h, 'hospital_type', '') or '').lower() == ht.name.lower())

    # Active Type Object if filtered
    active_type_obj = None
    if type_param and type_param.lower() != 'all':
        try:
            t_id = int(type_param)
            active_type_obj = get_hospital_type_by_id(t_id)
        except (ValueError, TypeError):
            active_type_obj = next((ht for ht in hospital_types if ht.slug == type_param.lower() or ht.name.lower() == type_param.lower()), None)

    # Distinct specialties across hospitals and doctors for filter dropdown
    distinct_specialties = set()
    for h in all_hospitals:
        if getattr(h, 'specialties', None):
            for s in h.specialties:
                if s and s.strip():
                    distinct_specialties.add(s.strip())
    for d in TEMP_DATA.get('doctors', {}).values():
        if getattr(d, 'specialization', None):
            distinct_specialties.add(d.specialization.strip())
        if getattr(d, 'department', None):
            distinct_specialties.add(d.department.strip())
    all_specialties = sorted(list(distinct_specialties))

    # Distinct cities and states
    all_cities = sorted(list(set(h.city.strip() for h in all_hospitals if getattr(h, 'city', None) and h.city.strip())))
    all_states = sorted(list(set(h.state.strip() for h in all_hospitals if getattr(h, 'state', None) and h.state.strip())))
    available_countries = sorted(list(set(getattr(h, 'country', 'India') for h in all_hospitals if getattr(h, 'country', None))))

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 9 if view_mode == 'grid' else 10
    total_filtered = len(filtered_hospitals)
    total_pages = (total_filtered + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_hospitals = filtered_hospitals[start_idx:end_idx]

    # Telemetry statistics
    total_partner_hospitals = len(all_hospitals)
    total_avail_icu_beds = sum(int(getattr(h, 'available_icu_beds', 0) or 0) for h in all_hospitals)
    total_avail_gen_beds = sum(int(getattr(h, 'available_beds', 0) or 0) for h in all_hospitals)
    total_total_beds = sum(int(getattr(h, 'total_beds', 0) or 0) for h in all_hospitals)
    total_doctors_count = sum(getattr(h, 'doctor_count', 0) for h in all_hospitals)
    verified_hospitals_count = sum(1 for h in all_hospitals if getattr(h, 'is_verified', True))
    verified_percent = round((verified_hospitals_count / max(total_partner_hospitals, 1)) * 100)

    # Return JSON for AJAX requests
    if request.args.get('format') == 'json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'total_filtered': total_filtered,
            'total_pages': total_pages,
            'current_page': page,
            'hospitals': [
                {
                    'id': h.id,
                    'name': h.name,
                    'hospital_type': getattr(h, 'type_name', 'General Hospital'),
                    'hospital_type_id': getattr(h, 'hospital_type_id', 1),
                    'type_icon': getattr(h, 'type_icon', 'fa-hospital'),
                    'type_color': getattr(h, 'type_color', '#0284c7'),
                    'city': h.city or '',
                    'state': h.state or '',
                    'country': getattr(h, 'country', 'India'),
                    'address': h.address or '',
                    'is_verified': getattr(h, 'is_verified', True),
                    'emergency_services': getattr(h, 'emergency_services', True),
                    'total_beds': getattr(h, 'total_beds', 0),
                    'available_beds': getattr(h, 'available_beds', 0),
                    'available_icu_beds': getattr(h, 'available_icu_beds', 0),
                    'specialties': getattr(h, 'specialties', []),
                    'facilities': getattr(h, 'facilities', []),
                    'distance_km': getattr(h, 'distance_km', None),
                    'logo_url': getattr(h, 'logo_url', None) or getattr(h, 'profile_picture_url', None),
                    'url': url_for('hospital.hospital_detail', hospital_id=h.id)
                }
                for h in paginated_hospitals
            ]
        })

    return render_template(
        'hospitals.html', 
        hospitals=paginated_hospitals,
        total_filtered=total_filtered,
        hospital_types=hospital_types,
        type_counts=type_counts,
        active_type_id=type_param,
        active_type_obj=active_type_obj,
        master_facilities=MASTER_FACILITIES_LIST,
        selected_facilities=facilities_list,
        all_specialties=all_specialties,
        active_specialty=specialty_query,
        all_cities=all_cities,
        all_states=all_states,
        q=search_query, 
        city=city_query,
        state=state_query,
        locality=locality_query,
        active_country=country_filter,
        active_scope=scope,
        verified_only=verified_only,
        emergency_only=emergency_only,
        nearby_only=nearby_only,
        user_lat=user_lat,
        user_lng=user_lng,
        view_mode=view_mode,
        available_countries=available_countries,
        country_flags=GLOBAL_COUNTRY_FLAGS,
        page=page,
        total_pages=total_pages,
        total_partner_hospitals=total_partner_hospitals,
        total_avail_icu_beds=total_avail_icu_beds,
        total_avail_gen_beds=total_avail_gen_beds,
        total_total_beds=total_total_beds,
        total_doctors_count=total_doctors_count,
        verified_percent=verified_percent
    )



@hospital_bp.route('/api/emergency/nearby-hospitals')
def api_nearby_hospitals():
    """Returns real-time emergency telemetry for hospitals sorted by proximity and availability."""
    import math
    
    # City coordinates reference dictionary for fallback geolocation
    CITY_COORDS = {
        'delhi': (28.6139, 77.2090),
        'new delhi': (28.6139, 77.2090),
        'mumbai': (19.0760, 72.8777),
        'bangalore': (12.9716, 77.5946),
        'bengaluru': (12.9716, 77.5946),
        'hyderabad': (17.3850, 78.4867),
        'chennai': (13.0827, 80.2707),
        'kolkata': (22.5726, 88.3639),
        'pune': (18.5204, 73.8567),
        'ahmedabad': (23.0225, 72.5714),
        'jaipur': (26.9124, 75.7873),
        'lucknow': (26.8467, 80.9462),
        'chandigarh': (30.7333, 76.7794),
        'noida': (28.5355, 77.3910),
        'gurgaon': (28.4595, 77.0266),
        'gurugram': (28.4595, 77.0266),
        'kochi': (9.9312, 76.2673),
        'indore': (22.7196, 75.8577),
        'bhopal': (23.2599, 77.4126),
        'patna': (25.5941, 85.1376),
        'varanasi': (25.3176, 82.9739),
        'surat': (21.1702, 72.8311),
        'nagpur': (21.1458, 79.0882),
        'new york': (40.7128, -74.0060),
        'london': (51.5074, -0.1278),
        'dubai': (25.2048, 55.2708),
        'singapore': (1.3521, 103.8198),
        'tokyo': (35.6762, 139.6503),
        'sydney': (-33.8688, 151.2093),
        'toronto': (43.6532, -79.3832),
        'chicago': (41.8781, -87.6298)
    }

    def calc_distance(lat1, lon1, lat2, lon2):
        R = 6371.0  # Radius of Earth in km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    search_q = request.args.get('q', '').lower().strip()
    city_filter = request.args.get('city', '').lower().strip()
    blood_group = request.args.get('blood_group', '').strip()
    icu_only = request.args.get('icu_only', 'false').lower() == 'true'
    radius_km = request.args.get('radius', type=float)  # in km

    # If city is supplied without GPS coordinates, try resolving city center
    if (user_lat is None or user_lng is None) and city_filter:
        for cname, coords in CITY_COORDS.items():
            if cname in city_filter or city_filter in cname:
                user_lat, user_lng = coords
                break

    all_hospitals = deduplicate_entities([h for h in TEMP_DATA['hospitals'].values() if not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)])
    results = []

    for h in all_hospitals:
        # Check ICU filter
        avail_icu = int(getattr(h, 'available_icu_beds', 0) or 0)
        if icu_only and avail_icu <= 0:
            continue

        # Check Blood group filter
        if blood_group:
            stock = getattr(h, 'blood_stock', {}) or {}
            if not isinstance(stock, dict) or stock.get(blood_group, 0) <= 0:
                continue

        # Check search query
        h_name = (h.name or '').lower()
        h_city = (h.city or '').lower()
        h_addr = (h.address or '').lower()
        h_country = (getattr(h, 'country', '') or '').lower()
        
        if search_q:
            if search_q not in h_name and search_q not in h_city and search_q not in h_addr and search_q not in h_country:
                continue

        if city_filter and not (user_lat and user_lng):
            if city_filter not in h_city and city_filter not in h_addr:
                continue

        # Determine hospital coordinates
        h_lat = getattr(h, 'latitude', None)
        h_lng = getattr(h, 'longitude', None)

        # Fallback to city coordinates if not explicitly set
        if h_lat is None or h_lng is None:
            for cname, coords in CITY_COORDS.items():
                if cname in h_city or cname in h_addr or cname in h_country:
                    h_lat, h_lng = coords
                    break

        # Calculate distance
        distance_km = None
        est_minutes = None
        if user_lat is not None and user_lng is not None and h_lat is not None and h_lng is not None:
            try:
                distance_km = round(calc_distance(user_lat, user_lng, float(h_lat), float(h_lng)), 1)
                if radius_km and distance_km > radius_km:
                    continue
                # Ambulance estimated arrival time (~45 km/h avg speed in city traffic)
                est_minutes = max(3, int(round((distance_km / 45.0) * 60)))
            except Exception:
                distance_km = None
                est_minutes = None

        dest_query = f"{h.name}, {h.address or h.city or h.country or ''}".strip(', ')
        results.append({
            'id': h.id,
            'name': h.name,
            'phone': h.phone or '+91 1800 200 4567',
            'emergency_phone': h.phone or '102',
            'email': h.email,
            'city': h.city or 'Main City Center',
            'state': h.state or '',
            'country': getattr(h, 'country', 'India'),
            'country_flag': getattr(h, 'country_flag', '🏥'),
            'address': h.address or f"{h.city or 'Clinical District'}, Emergency Wing",
            'available_beds': int(getattr(h, 'available_beds', 0) or 0),
            'total_beds': int(getattr(h, 'total_beds', 0) or 0),
            'available_icu_beds': avail_icu,
            'icu_beds': int(getattr(h, 'icu_beds', 0) or 0),
            'general_bed_fee': getattr(h, 'general_bed_fee', 1000.0),
            'icu_bed_fee': getattr(h, 'icu_bed_fee', 2500.0),
            'doctors_available': getattr(h, 'doctors_available', 'Available'),
            'doctor_count': getattr(h, 'doctor_count', 0),
            'distance_km': distance_km,
            'est_minutes': est_minutes,
            'blood_stock': getattr(h, 'blood_stock', {}),
            'detail_url': url_for('hospital_detail', hospital_id=h.id),
            'directions_url': f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(dest_query)}"
        })

    # Sort: If distance is available, sort by distance asc; else by available ICU beds desc
    if user_lat is not None and user_lng is not None:
        results.sort(key=lambda x: (x['distance_km'] is None, x['distance_km'] or 999999, -x['available_icu_beds']))
    else:
        results.sort(key=lambda x: -x['available_icu_beds'])

    return jsonify({
        'status': 'success',
        'count': len(results),
        'user_location': {'lat': user_lat, 'lng': user_lng} if user_lat and user_lng else None,
        'hospitals': results
    })



@hospital_bp.route('/hospital/<path:hospital_id>')
def hospital_detail(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))
    
    # Get doctors for this hospital
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if (d.hospital_name == hospital.name or str(getattr(d, 'hospital_id', '')) == str(hospital.id))
        and not getattr(d, 'is_hidden', False)
        and not getattr(d, 'is_blocked', False)
    ]
    
    departments_with_doctors = {}
    for doc in hospital_doctors:
        dept = doc.department or 'General Medicine'
        if dept not in departments_with_doctors:
            departments_with_doctors[dept] = []
        departments_with_doctors[dept].append(doc)

    hospital_departments = sorted(departments_with_doctors.keys())

    # Sort doctors consistently (by ID)
    def parse_doc_id(d):
        val = d.id
        if isinstance(val, int):
            return (0, val)
        if isinstance(val, str):
            if val.isdigit():
                return (0, int(val))
            import re
            m = re.search(r'\d+', val)
            if m:
                return (0, int(m.group(0)))
            return (1, val)
        return (2, str(val))
    hospital_doctors.sort(key=parse_doc_id)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 12
    total_filtered = len(hospital_doctors)
    total_pages = (total_filtered + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_doctors = hospital_doctors[start_idx:end_idx]
    
    hospital_organ_requests = [r for r in TEMP_DATA.get('organ_requests', {}).values() if r.hospital_id == str(hospital.id) and r.status == 'active']
    hospital_organ_donors = [d for d in TEMP_DATA.get('organ_donors', {}).values() if str(getattr(d, 'hospital_id', '')) == str(hospital.id) and getattr(d, 'status', 'pending') == 'approved']
    
    return render_template(
        'hospital_detail.html', 
        hospital=hospital, 
        doctors=paginated_doctors, 
        all_doctors=hospital_doctors,
        departments_with_doctors=departments_with_doctors,
        departments=hospital_departments,
        organ_requests=hospital_organ_requests,
        organ_donors=hospital_organ_donors,
        page=page,
        total_pages=total_pages
    )



@hospital_bp.route('/hospital/<path:hospital_id>/inquiry', methods=['POST'])
def hospital_inquiry(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    if name and email and message:
        subject = f"New Inquiry from {name} - Spherix Clinic"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #059669;">New Patient Inquiry</h2>
            <p><strong>From:</strong> {name} ({email})</p>
            <p><strong>Message:</strong></p>
            <div style="background: #f9fafb; padding: 15px; border-left: 4px solid #059669; border-radius: 4px;">
                {message}
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">This message was sent via the hospital public profile page.</p>
        </div>
        """
        if hospital.email:
            send_notification_email(hospital.email, subject, body, is_html=True)
            flash("Your message has been sent to the hospital administration.", "success")
        else:
            flash("This hospital does not have a registered email for inquiries.", "warning")
    else:
        flash("Please fill out all fields.", "error")

    return redirect(url_for('hospital_detail', hospital_id=hospital_id))



@hospital_bp.route('/hospital/<path:hospital_id>/medical_travel_inquiry', methods=['POST'])
def medical_travel_inquiry(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    patient_name = request.form.get('patient_name')
    email = request.form.get('email')
    country = request.form.get('origin_country')
    treatment = request.form.get('treatment_required')
    message = request.form.get('notes', '')

    if patient_name and email:
        subject = f"Cross-Border Medical Visa Inquiry: {patient_name} ({country or 'International'}) - Spherix Clinic"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #4f46e5;">International Patient & Medical Visa Inquiry</h2>
            <p><strong>Patient Name:</strong> {patient_name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Origin Country:</strong> {country or 'N/A'}</p>
            <p><strong>Treatment Requested:</strong> {treatment or 'General Clinical Inquiry'}</p>
            <p><strong>Notes:</strong></p>
            <div style="background: #f8fafc; padding: 15px; border-left: 4px solid #4f46e5; border-radius: 4px;">
                {message or 'Requesting medical visa assistance and clinical admission quote.'}
            </div>
        </div>
        """
        if hospital.email:
            send_notification_email(hospital.email, subject, body, is_html=True)
            flash("Your cross-border medical travel inquiry has been transmitted to the hospital international desk.", "success")
        else:
            flash("Your inquiry has been logged. Our international concierge will assist you.", "success")
    else:
        flash("Please provide your name and email address.", "error")

    return redirect(url_for('hospital_detail', hospital_id=hospital_id))



@hospital_bp.route('/hospital/<path:hospital_id>/blood_inquiry', methods=['POST'])
def hospital_blood_inquiry(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    name = request.form.get('name')
    email = request.form.get('email')
    blood_group = request.form.get('blood_group')
    units = request.form.get('units', '1')
    urgency = request.form.get('urgency', 'Immediate / Emergency')

    if name and email and blood_group:
        subject = f"🚨 URGENT Transfusion Inquiry: {blood_group} ({units} units) - Spherix Clinic"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #dc2626;">Emergency Blood Bank Transfusion Request</h2>
            <p><strong>Requester:</strong> {name} ({email})</p>
            <p><strong>Blood Group:</strong> <span style="font-size: 16px; font-weight: bold; color: #dc2626;">{blood_group}</span></p>
            <p><strong>Units Required:</strong> {units}</p>
            <p><strong>Urgency:</strong> {urgency}</p>
        </div>
        """
        if hospital.email:
            send_notification_email(hospital.email, subject, body, is_html=True)
            flash(f"Emergency blood inquiry for {blood_group} ({units} units) has been sent to {hospital.name}.", "success")
        else:
            flash("Transfusion inquiry logged with hospital blood bank registry.", "success")
    else:
        flash("Please specify name, contact email, and blood group.", "error")

    return redirect(url_for('hospital_detail', hospital_id=hospital_id))



@hospital_bp.route('/hospital/<path:hospital_id>/book_bed', methods=['POST'])
@patient_required
def book_hospital_bed(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    bed_type = request.form.get('bed_type')
    patient_name = request.form.get('patient_name')
    patient_phone = request.form.get('patient_phone')
    reason = request.form.get('reason')
    
    if not all([bed_type, patient_name, patient_phone, reason]):
        flash("All fields are required to request an emergency bed.", "error")
        return redirect(url_for('hospital_detail', hospital_id=hospital_id))

    # Initialize dict if it hasn't been set
    if 'bed_bookings' not in TEMP_DATA:
        TEMP_DATA['bed_bookings'] = {}
        
    if 'bed_booking' not in TEMP_DATA['next_ids']:
        TEMP_DATA['next_ids']['bed_booking'] = max([1] + [int(k) for k in TEMP_DATA['bed_bookings'].keys()]) + 1

    booking_id = TEMP_DATA['next_ids']['bed_booking']
    new_booking = BedBooking(
        id=booking_id,
        hospital_id=hospital_id,
        patient_id=current_user.id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        bed_type=bed_type,
        reason=reason,
        status='awaiting_payment'
    )
    TEMP_DATA['bed_bookings'][booking_id] = new_booking
    TEMP_DATA['next_ids']['bed_booking'] += 1
    save_data()
    return redirect(url_for('bed_booking_payment', booking_id=booking_id))



@hospital_bp.route('/hospital/bed_booking/payment/<int:booking_id>', methods=['GET', 'POST'])
@patient_required
def bed_booking_payment(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if not booking or booking.patient_id != current_user.id:
        flash("Booking not found.", "error")
        return redirect(url_for('patient_dashboard'))
        
    if booking.status not in ('awaiting_payment', 'pending'):
        flash("This booking has already been paid for or processed.", "warning")
        return redirect(url_for('patient_dashboard'))

    hospital = get_temp_data_item('hospitals', booking.hospital_id)
    if not hospital:
        flash("Hospital record not found.", "error")
        return redirect(url_for('patient_dashboard'))

    try:
        raw_fee = hospital.icu_bed_fee if booking.bed_type == 'ICU' else hospital.general_bed_fee
        fee = float(raw_fee) if raw_fee and float(raw_fee) > 0 else (4500.0 if booking.bed_type == 'ICU' else 1500.0)
    except (ValueError, TypeError):
        fee = 4500.0 if booking.bed_type == 'ICU' else 1500.0

    rzp_key_id = get_razorpay_key_id()
    
    if request.method == 'POST':
        razorpay_payment_id = request.form.get('razorpay_payment_id')
        razorpay_order_id = request.form.get('razorpay_order_id')
        razorpay_signature = request.form.get('razorpay_signature')
        payment_method = request.form.get('payment_method', 'razorpay')

        # 1. Razorpay Signature Verification
        if razorpay_payment_id and razorpay_order_id and razorpay_signature:
            is_valid = verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
            if is_valid:
                booking.status = 'confirmed'
                booking.payment_id = razorpay_payment_id
                booking.payment_method = 'Razorpay Online'
                
                # Update bed count in live hospital state
                if booking.bed_type == 'ICU' and getattr(hospital, 'available_icu_beds', 0) > 0:
                    hospital.available_icu_beds -= 1
                elif getattr(hospital, 'available_beds', 0) > 0:
                    hospital.available_beds -= 1
                    
                save_data()
                flash(f"🎉 Payment verified via Razorpay! Emergency {booking.bed_type} bed confirmed at {hospital.name}.", "success")
                return redirect(url_for('patient_dashboard'))
            else:
                flash("⚠️ Payment verification signature mismatch. Please contact clinic support.", "error")
                return redirect(url_for('bed_booking_payment', booking_id=booking_id))

        # 2. Razorpay Hosted Payment Link Option
        if payment_method in ('razorpay_link', 'card', 'upi') and razorpay_client:
            try:
                callback_url = url_for('patient_dashboard', _external=True) + f'?bed_paid={booking.id}'
                payment_link = create_razorpay_payment_link(
                    amount_inr=fee,
                    reference_id=f"bed_{booking.id}_{int(time_module.time())}",
                    description=f"Emergency {booking.bed_type} Bed Reservation - {hospital.name}",
                    customer_name=booking.patient_name,
                    customer_email=getattr(current_user, 'email', 'patient@spherixclinic.com'),
                    customer_phone=booking.patient_phone,
                    callback_url=callback_url
                )
                if payment_link and 'short_url' in payment_link:
                    return redirect(payment_link['short_url'], code=303)
            except Exception as e:
                flash(f"Payment gateway note: {str(e)}", "info")

        # 3. Direct confirmation fallback (sandbox / simulation)
        booking.status = 'confirmed'
        booking.payment_method = 'Confirmed'
        save_data()
        flash(f"Payment successful! Emergency {booking.bed_type} bed request confirmed at {hospital.name}.", "success")
        return redirect(url_for('patient_dashboard'))

    # Pre-generate Razorpay Order for client-side modal checkout
    rzp_order = create_razorpay_order(
        amount_inr=fee,
        receipt=f"bed_{booking.id}",
        notes={'booking_id': str(booking.id), 'hospital': hospital.name, 'bed_type': booking.bed_type}
    )
    rzp_order_id = rzp_order.get('id', '') if rzp_order else ''

    return render_template(
        'bed_booking_payment.html',
        booking=booking,
        hospital=hospital,
        fee=fee,
        razorpay_key_id=rzp_key_id,
        razorpay_order_id=rzp_order_id,
        amount_paise=int(fee * 100)
    )



@hospital_bp.route('/hospital/<path:hospital_id>/book_appointment', methods=['POST'])
@patient_required
def book_hospital_appointment(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))
        
    department = request.form.get('department')
    doctor_id = request.form.get('doctor_id')
    patient_name = request.form.get('patient_name')
    patient_phone = request.form.get('patient_phone')
    patient_age = request.form.get('patient_age')
    patient_id_number = request.form.get('patient_id_number')
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    reason = request.form.get('reason')
    
    if not all([patient_name, patient_phone, patient_age, patient_id_number, date_str, time_str]):
        flash("All required patient and schedule details must be provided.", "error")
        return redirect(url_for('hospital_detail', hospital_id=hospital_id))
        
    appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    appt_time = datetime.strptime(time_str, '%H:%M').time()
    
    # Hospital doctors list
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if (d.hospital_name == hospital.name or str(getattr(d, 'hospital_id', '')) == str(hospital.id))]
    
    is_auto_assigned = False
    assigned_doctor = None
    
    # If a specific doctor was chosen (and not 'auto')
    if doctor_id and doctor_id != 'auto' and doctor_id != 'unassigned':
        assigned_doctor = TEMP_DATA['doctors'].get(doctor_id)
        if not assigned_doctor or (assigned_doctor.hospital_name != hospital.name and str(getattr(assigned_doctor, 'hospital_id', '')) != str(hospital.id)):
            flash("Selected doctor is not associated with this facility.", "error")
            return redirect(url_for('hospital_detail', hospital_id=hospital_id))
    else:
        # Department-wise booking: Staff / duty roster auto-assignment
        is_auto_assigned = True
        dept_doctors = [d for d in hospital_doctors if (d.department or '').lower() == (department or '').lower()] if department else hospital_doctors
        if not dept_doctors:
            dept_doctors = hospital_doctors
            
        # Priority: Check active on-duty / available doctors
        available_dept_docs = [d for d in dept_doctors if getattr(d, 'availability_status', 'available') != 'unavailable']
        assigned_doctor = available_dept_docs[0] if available_dept_docs else (dept_doctors[0] if dept_doctors else None)

    assigned_doc_id = assigned_doctor.id if assigned_doctor else None
    if not assigned_doc_id and hospital_doctors:
        assigned_doc_id = hospital_doctors[0].id

    if not assigned_doc_id:
        flash("No clinical specialists currently available in this department. Hospital desk has been notified.", "error")
        return redirect(url_for('hospital_detail', hospital_id=hospital_id))
        
    appt_id = TEMP_DATA['next_ids']['appointment']
    new_appointment = Appointment(
        id=appt_id,
        patient_name=patient_name,
        doctor_id=assigned_doc_id,
        appointment_date=appt_date,
        appointment_time=appt_time,
        patient_phone=patient_phone,
        patient_age=patient_age,
        patient_id_number=patient_id_number,
        reason=reason,
        status='awaiting_payment',
        hospital_id=hospital.id,
        department=department or (assigned_doctor.department if assigned_doctor else 'General Medicine'),
        is_auto_assigned=is_auto_assigned
    )
    new_appointment.patient_id = current_user.id
    TEMP_DATA['appointments'][appt_id] = new_appointment
    TEMP_DATA['next_ids']['appointment'] += 1
    save_data()
    
    return redirect(url_for('appointment_payment', appointment_id=appt_id))



@hospital_bp.route('/api/hospital/live-stats')
@hospital_required
def hospital_live_stats():
    # Filter doctors belonging to this hospital
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or \
           (getattr(d, 'hospital_name', None) and d.hospital_name == current_user.name)
    ]
    # Filter staff
    hospital_staff = [s for s in TEMP_DATA['staff'].values() if s.hospital_name == current_user.name]
    
    # Filter appointments
    hospital_appointments = []
    unique_patient_ids = set()
    for appt in TEMP_DATA['appointments'].values():
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        if doc and (doc.hospital_id == current_user.id or doc.hospital_name == current_user.name):
            hospital_appointments.append(appt)
            if appt.patient_id:
                unique_patient_ids.add(appt.patient_id)
                
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    hospital_patients = [TEMP_DATA['patients'][pid] for pid in unique_patient_ids if pid in TEMP_DATA['patients']]
    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if str(b.hospital_id) == str(current_user.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)

    # Calculate revenues
    total_appointment_revenue = 0.0
    for appt in hospital_appointments:
        if appt.status in ['completed', 'approved', 'paid']:
            doc = TEMP_DATA['doctors'].get(appt.doctor_id)
            if doc:
                try:
                    fee = float(str(doc.consultation_fee).replace('₹', '').replace(',', '').strip() or 0)
                except ValueError:
                    fee = 150.0
                total_appointment_revenue += fee

    total_bed_revenue = 0.0
    for booking in hospital_bed_bookings:
        if booking.status in ['approved', 'discharged', 'paid']:
            fee = float(getattr(current_user, 'icu_bed_fee', 2500.0) if booking.bed_type == 'ICU' else getattr(current_user, 'general_bed_fee', 1000.0))
            total_bed_revenue += fee

    activity_logs = [log for log in TEMP_DATA.get('activity_logs', {}).values() if getattr(log, 'hospital_id', None) == current_user.id]
    activity_logs.sort(key=lambda x: getattr(x, 'created_at', utcnow()), reverse=True)

    # Stats & KPI Calculations
    today = date.today()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart_labels = [d.strftime('%b %d') for d in last_7_days]
    
    # 7-day appointment volume
    appt_counts_by_day = Counter(a.appointment_date for a in hospital_appointments if a.appointment_date)
    chart_data = [appt_counts_by_day.get(d, 0) for d in last_7_days]
    
    # 7-day revenue trend
    revenue_by_day = {d: 0.0 for d in last_7_days}
    for a in hospital_appointments:
        if a.appointment_date in revenue_by_day and a.status in ['completed', 'approved', 'paid', 'confirmed']:
            doc = TEMP_DATA['doctors'].get(a.doctor_id)
            fee = 150.0
            if doc:
                try:
                    fee = float(str(doc.consultation_fee).replace('₹', '').replace(',', '').strip() or 0)
                except ValueError:
                    fee = 150.0
            revenue_by_day[a.appointment_date] += fee
            
    for b in hospital_bed_bookings:
        b_date = b.created_at.date() if hasattr(b.created_at, 'date') else today
        if b_date in revenue_by_day and b.status in ['approved', 'discharged', 'paid', 'pending']:
            fee = float(getattr(current_user, 'icu_bed_fee', 2500.0) if b.bed_type == 'ICU' else getattr(current_user, 'general_bed_fee', 1000.0))
            revenue_by_day[b_date] += fee
            
    revenue_chart_data = [round(revenue_by_day[d], 2) for d in last_7_days]

    # Department distribution
    dept_counter = Counter()
    for doc in hospital_doctors:
        dept = doc.department or 'General Medicine'
        dept_counter[dept] += 1
    for appt in hospital_appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        dept = doc.department if (doc and doc.department) else 'General Medicine'
        dept_counter[dept] += 1
    if not dept_counter:
        dept_counter = {'General Medicine': 2, 'Cardiology': 1, 'Orthopaedics': 1}
    dept_labels = list(dept_counter.keys())
    dept_data = list(dept_counter.values())

    # Bed occupancy & distribution
    total_beds = current_user.total_beds if current_user.total_beds is not None else 50
    available_beds = current_user.available_beds if current_user.available_beds is not None else 40
    icu_beds = current_user.icu_beds if current_user.icu_beds is not None else 10
    available_icu_beds = current_user.available_icu_beds if current_user.available_icu_beds is not None else 8
    
    occupied_general = max(0, total_beds - available_beds)
    occupied_icu = max(0, icu_beds - available_icu_beds)
    bed_distribution_data = [occupied_general, available_beds, occupied_icu, available_icu_beds]
    
    total_bed_capacity = total_beds + icu_beds
    bed_occupancy_percent = round(((occupied_general + occupied_icu) / total_bed_capacity * 100)) if total_bed_capacity > 0 else 0

    # Clinical Triage & Status Breakdown
    status_counter = Counter(a.status for a in hospital_appointments)
    case_status_labels = ["Confirmed OPD", "Pending / Triage", "Emergency Beds", "Discharged / Done"]
    case_status_data = [
        status_counter.get('confirmed', 0),
        status_counter.get('pending', 0) + status_counter.get('awaiting_payment', 0),
        len([b for b in hospital_bed_bookings if b.status in ['pending', 'approved']]),
        status_counter.get('completed', 0) + status_counter.get('discharged', 0) + len([b for b in hospital_bed_bookings if b.status == 'discharged'])
    ]

    # Blood Bank stock
    blood_stock = current_user.blood_stock if hasattr(current_user, 'blood_stock') and isinstance(current_user.blood_stock, dict) else TEMP_DATA.get('blood_stock', {})
    blood_group_labels = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    blood_group_data = [blood_stock.get(bg, 0) for bg in blood_group_labels]

    # Stats dict
    stats = {
        "total_appointments": len(hospital_appointments),
        "total_doctors": len(hospital_doctors),
        "available_beds": available_beds,
        "total_beds": total_beds,
        "available_icu_beds": available_icu_beds,
        "icu_beds": icu_beds,
        "occupied_general_beds": occupied_general,
        "occupied_icu_beds": occupied_icu,
        "total_patients": len(hospital_patients),
        "total_appointment_revenue": total_appointment_revenue,
        "total_bed_revenue": total_bed_revenue,
        "total_revenue": total_appointment_revenue + total_bed_revenue,
        "bed_occupancy_percent": bed_occupancy_percent,
        "pending_bed_bookings_count": len([b for b in hospital_bed_bookings if b.status == 'pending']),
        "today_appointments_count": len([a for a in hospital_appointments if a.appointment_date == today]),
        "emergency_cases_count": len([b for b in hospital_bed_bookings if 'emergency' in str(getattr(b, 'reason', '')).lower() or b.bed_type == 'ICU']),
        "active_admissions_count": len([b for b in hospital_bed_bookings if b.status in ['approved', 'active', 'paid']])
    }

    # Serialize appointments
    serialized_appointments = []
    for appt in hospital_appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        pat = TEMP_DATA['patients'].get(appt.patient_id) if getattr(appt, 'patient_id', None) else None
        created_at_val = getattr(appt, 'created_at', None)
        created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(created_at_val, 'strftime') else str(created_at_val or '')
        serialized_appointments.append({
            "id": appt.id,
            "patient_name": appt.patient_name,
            "patient_phone": getattr(appt, 'patient_phone', None) or (pat.phone if pat else "N/A"),
            "patient_age": str(getattr(appt, 'patient_age', None) or (pat.age if pat and getattr(pat, 'age', None) else "32")),
            "patient_gender": str(getattr(pat, 'gender', 'Not specified') if pat else "Not specified"),
            "patient_id_number": str(getattr(appt, 'patient_id_number', None) or (f"UID-{pat.id}" if pat else f"UID-{appt.id:06d}")),
            "doctor_name": f"Dr. {doc.first_name} {doc.last_name}" if doc else "N/A",
            "doctor_dept": doc.department if doc else "N/A",
            "date": appt.appointment_date.strftime('%b %d, %Y') if appt.appointment_date else "N/A",
            "time": appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time else "N/A",
            "reason": appt.reason or "General Consultation",
            "status": appt.status,
            "created_at": created_at_str,
            "is_real": True
        })

    # Serialize bed bookings
    serialized_bed_bookings = []
    for booking in hospital_bed_bookings:
        pat = TEMP_DATA['patients'].get(booking.patient_id) if getattr(booking, 'patient_id', None) else None
        created_at_val = getattr(booking, 'created_at', None)
        created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(created_at_val, 'strftime') else str(created_at_val or '')
        serialized_bed_bookings.append({
            "id": booking.id,
            "patient_name": booking.patient_name,
            "patient_phone": getattr(booking, 'patient_phone', None) or (pat.phone if pat else "N/A"),
            "patient_age": str(getattr(pat, 'age', '45') if pat and getattr(pat, 'age', None) else "45"),
            "patient_gender": str(getattr(pat, 'gender', 'Not specified') if pat else "Not specified"),
            "patient_id_number": str(f"UID-{pat.id}" if pat else f"UID-BED{booking.id:04d}"),
            "bed_type": booking.bed_type,
            "reason": booking.reason or "Emergency Inpatient Admission",
            "status": booking.status,
            "room_number": booking.room_number or "",
            "created_at": created_at_str,
            "is_real": True
        })

    # Serialize activity logs
    serialized_activity_logs = []
    for log in activity_logs[:20]:
        log_created_at = getattr(log, 'created_at', utcnow())
        serialized_activity_logs.append({
            "id": log.id,
            "timestamp": log_created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(log_created_at, 'strftime') else str(log_created_at),
            "user_name": log.user_name,
            "action": log.action,
            "details": log.details
        })

    return jsonify({
        "success": True,
        "stats": stats,
        "appointments": serialized_appointments,
        "bed_bookings": serialized_bed_bookings,
        "activity_logs": serialized_activity_logs,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "revenue_labels": chart_labels,
        "revenue_data": revenue_chart_data,
        "dept_labels": dept_labels,
        "dept_data": dept_data,
        "case_status_labels": case_status_labels,
        "case_status_data": case_status_data,
        "bed_distribution_data": bed_distribution_data,
        "blood_group_labels": blood_group_labels,
        "blood_group_data": blood_group_data
    })



@hospital_bp.route('/api/hospital/simulate-event', methods=['POST'])
@hospital_required
def hospital_simulate_event():
    # Filter doctors belonging to this hospital to assign one
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or \
           (getattr(d, 'hospital_name', None) and d.hospital_name == current_user.name)
    ]
    if not hospital_doctors:
        # Check if there are any doctors in the system
        hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False)]
        if not hospital_doctors:
            return jsonify({'status': 'error', 'message': 'No registered doctors available for this hospital.'}), 400

    event_type = request.json.get('type') if (request.is_json and request.json) else request.form.get('type')
    if not event_type or event_type == 'random':
        event_type = random.choice(['appointment', 'bed'])

    # Use real registered patients from system if available
    existing_real_patients = [p for p in TEMP_DATA.get('patients', {}).values() if hasattr(p, 'name') and p.name]
    
    if existing_real_patients:
        chosen_patient = random.choice(existing_real_patients)
        patient_name = chosen_patient.name
        patient_phone = chosen_patient.phone or f"9{random.randint(100000000, 999999999)}"
        patient_age = str(getattr(chosen_patient, 'age', 32) or 32)
        patient_gender = getattr(chosen_patient, 'gender', 'Male') or 'Male'
        patient_id_str = chosen_patient.id
        patient_id_number = f"UID-{chosen_patient.id}"
    else:
        patient_name = "Walk-in Patient"
        patient_phone = f"9{random.randint(100000000, 999999999)}"
        patient_age = "30"
        patient_gender = "Male"
        patient_id_str = "walkin"
        patient_id_number = "UID-WALKIN"

    opd_reasons = [
        "Routine cardiovascular checkup", "Persistent migraine check", "Mild seasonal fever and dry cough", 
        "Follow-up orthopaedic consultation", "Allergy skin rash checkup", "Annual preventive health screening",
        "Abdominal discomfort evaluation", "Ophthalmic visual field examination"
    ]
    
    bed_reasons = [
        "Moderate lobar pneumonia therapy", "Post-operative major surgery monitoring", "Acute gastroenteritis observation",
        "Severe diabetic ketoacidosis stabilization", "Inpatient rehabilitation and IV antibiotics administration"
    ]
    
    emergency_reasons = [
        "Acute myocardial infarction (Cardiac)", "Traumatic head injury post-accident", "Acute respiratory failure",
        "Severe sepsis requiring aggressive resuscitation", "High grade fever with convulsions"
    ]
    
    # We will log the activity
    activity_id = TEMP_DATA['next_ids'].get('activity_log', len(TEMP_DATA.get('activity_logs', {})) + 1)
    
    simulated_event = {}

    if event_type == 'appointment':
        doc = random.choice(hospital_doctors)
        appt_id = TEMP_DATA['next_ids']['appointment']
        appt_date = date.today()
        appt_time = time(random.randint(9, 17), random.choice([0, 15, 30, 45]))
        reason = random.choice(opd_reasons)
        
        new_appt = Appointment(
            id=appt_id,
            patient_name=patient_name,
            doctor_id=doc.id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            patient_phone=patient_phone,
            patient_age=patient_age,
            patient_id_number=patient_id_number,
            reason=reason,
            status='pending'
        )
        new_appt.patient_id = patient_id_str
        TEMP_DATA['appointments'][appt_id] = new_appt
        TEMP_DATA['next_ids']['appointment'] += 1
        
        # Log activity
        log = ActivityLog(
            id=activity_id,
            hospital_id=current_user.id,
            user_name=patient_name,
            action="Live OPD Walk-in",
            details=f"Live patient arrival for {patient_name} with Dr. {doc.first_name} {doc.last_name} ({doc.department})"
        )
        TEMP_DATA.setdefault('activity_logs', {})[activity_id] = log
        TEMP_DATA['next_ids']['activity_log'] = activity_id + 1
        
        simulated_event = {
            "type": "appointment",
            "id": appt_id,
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "patient_age": patient_age,
            "patient_gender": patient_gender,
            "patient_id_number": patient_id_number,
            "doctor_name": f"Dr. {doc.first_name} {doc.last_name}",
            "doctor_dept": doc.department,
            "date": appt_date.strftime('%b %d, %Y'),
            "time": appt_time.strftime('%I:%M %p'),
            "reason": reason,
            "status": "pending",
            "is_real": False
        }
    else:
        # Bed booking
        is_icu = random.choice([True, False])
        bed_type = "ICU" if is_icu else "General"
        reason = random.choice(emergency_reasons) if is_icu else random.choice(bed_reasons)
        
        if 'bed_bookings' not in TEMP_DATA:
            TEMP_DATA['bed_bookings'] = {}
        if 'bed_booking' not in TEMP_DATA['next_ids']:
            TEMP_DATA['next_ids']['bed_booking'] = max([1] + [int(k) for k in TEMP_DATA['bed_bookings'].keys()]) + 1
            
        booking_id = TEMP_DATA['next_ids']['bed_booking']
        new_booking = BedBooking(
            id=booking_id,
            hospital_id=current_user.id,
            patient_id=patient_id_str,
            patient_name=patient_name,
            patient_phone=patient_phone,
            bed_type=bed_type,
            reason=reason,
            status='pending'
        )
        TEMP_DATA['bed_bookings'][booking_id] = new_booking
        TEMP_DATA['next_ids']['bed_booking'] += 1
        
        # Log activity
        log = ActivityLog(
            id=activity_id,
            hospital_id=current_user.id,
            user_name=patient_name,
            action="Emergency Bed Request",
            details=f"Live emergency {bed_type} Bed request for {patient_name} due to {reason}"
        )
        TEMP_DATA.setdefault('activity_logs', {})[activity_id] = log
        TEMP_DATA['next_ids']['activity_log'] = activity_id + 1
        
        simulated_event = {
            "type": "bed_booking",
            "id": booking_id,
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "patient_age": patient_age,
            "patient_gender": patient_gender,
            "patient_id_number": patient_id_number,
            "bed_type": bed_type,
            "reason": reason,
            "status": "pending",
            "is_real": False
        }
        
    save_data()
    return jsonify({
        "success": True,
        "event": simulated_event,
        "message": f"Successfully processed new {event_type} request for {patient_name}!"
    })



@hospital_bp.route('/doctor/respond-hospital-invitation', methods=['POST'])
@doctor_required
def respond_hospital_invitation():
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    if not doctor:
        flash('Doctor not found.', 'error')
        return redirect(url_for('doctor_login'))
        
    action = request.form.get('action')
    h_id = request.form.get('hospital_id')
    
    if doctor.hospital_id == h_id and doctor.hospital_approval_status == 'pending':
        hospital = TEMP_DATA['hospitals'].get(h_id)
        if not hospital:
            flash('Hospital not found.', 'error')
            return redirect(url_for('doctor_dashboard'))
            
        if action == 'accept':
            doctor.hospital_approval_status = 'approved'
            doctor.hospital_name = hospital.name
            doctor.hospital_address = hospital.address
            save_data()
            flash(f'You have joined {hospital.name} staff successfully!', 'success')
        elif action == 'decline':
            doctor.hospital_id = None
            doctor.hospital_approval_status = None
            save_data()
            flash(f'You declined the invitation from {hospital.name}.', 'info')
    else:
        flash('Invalid invitation request.', 'error')
        
    return redirect(url_for('doctor_dashboard'))



@hospital_bp.route('/hospital/export_appointments')
@hospital_required
def export_hospital_appointments():
    """Exports all hospital appointments to a downloadable CSV file."""
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Appointment ID', 'Date', 'Time', 'Patient Name', 'Phone', 'Doctor Name', 'Department', 'Reason', 'Status'])
    
    hospital_doctors = [d.id for d in TEMP_DATA['doctors'].values() if d.hospital_name == current_user.name]
    appointments = [a for a in TEMP_DATA['appointments'].values() if a.doctor_id in hospital_doctors]
    appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    
    for appt in appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        doc_name = f"Dr. {doc.first_name} {doc.last_name}" if doc else "Unknown"
        dept = doc.department if doc else "Unknown"
        cw.writerow([
            appt.id,
            appt.appointment_date.strftime('%Y-%m-%d') if appt.appointment_date else '',
            appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time else '',
            appt.patient_name,
            appt.patient_phone,
            doc_name,
            dept,
            appt.reason,
            appt.status.capitalize()
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=hospital_appointments.csv"
    output.headers["Content-type"] = "text/csv"
    return output



@hospital_bp.route('/hospital/export_report_pdf')
@hospital_required
def export_hospital_report_pdf():
    """Generates a PDF report of the current hospital facility status."""
    hospital = current_user
    
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == hospital.name]
    hospital_staff = [s for s in TEMP_DATA['staff'].values() if s.hospital_name == hospital.name]
    
    doc_ids = {d.id for d in hospital_doctors}
    appointments = [a for a in TEMP_DATA['appointments'].values() if a.doctor_id in doc_ids]
    
    try:
        class HospitalReportPDF(FPDF):
            def header(self):
                self.set_fill_color(240, 248, 255)
                self.rect(0, 0, 210, 35, 'F')
                self.set_y(12)
                self.set_font('Helvetica', 'B', 22)
                self.set_text_color(15, 23, 42)
                self.cell(0, 10, 'FACILITY STATUS REPORT', 0, 1, 'C')
                self.set_font('Helvetica', 'I', 11)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, to_latin1_str(hospital.name), 0, 1, 'C')
                self.ln(10)

            def footer(self):
                self.set_y(-15)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f'Page {self.page_no()} - Securely Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 0, 'C')

            def section_title(self, title):
                self.ln(6)
                self.set_font('Helvetica', 'B', 12)
                self.set_text_color(255, 255, 255)
                self.set_fill_color(5, 150, 105) # Emerald 600
                self.cell(0, 9, f'  {title}', 0, 1, 'L', fill=True)
                self.ln(3)

        pdf = HospitalReportPDF()
        pdf.add_page()
        
        pdf.section_title('1. Capacity & Resources')
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(95, 8, f"Total General Beds: {hospital.total_beds} (Available: {hospital.available_beds})", 0, 0)
        pdf.cell(95, 8, f"Total ICU Beds: {hospital.icu_beds} (Available: {hospital.available_icu_beds})", 0, 1)
        pdf.cell(95, 8, f"Active Doctors: {len(hospital_doctors)}", 0, 0)
        pdf.cell(95, 8, f"Active Staff: {len(hospital_staff)}", 0, 1)
        
        blood_stock = getattr(hospital, 'blood_stock', {})
        if blood_stock:
            pdf.section_title('2. Blood Bank Inventory')
            pdf.set_font('Helvetica', '', 11)
            for g, qty in blood_stock.items():
                pdf.cell(45, 8, f"{g}: {qty} Units", 1, 0, 'C')
                if list(blood_stock.keys()).index(g) % 4 == 3: pdf.ln()
            pdf.ln(5)

        pdf.section_title('3. Appointments Summary')
        status_counts = Counter([a.status for a in appointments])
        pdf.set_font('Helvetica', '', 11)
        for status, count in status_counts.items():
            pdf.cell(0, 8, f"{status.capitalize()} Appointments: {count}", 0, 1)
            
        pdf_output = pdf.output(dest='S')
        pdf_bytes = pdf_output.encode('latin-1', 'replace') if isinstance(pdf_output, str) else pdf_output
        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'{hospital.name.replace(" ", "_")}_Report.pdf', mimetype='application/pdf')
    except Exception as e:
        flash(f"Error generating PDF report: {e}", "error")
        return redirect(url_for('hospital_dashboard'))



@hospital_bp.route('/hospital/bed_booking/<int:booking_id>/<action>', methods=['POST'])
@hospital_or_staff_role_required('Bed Management')
def handle_bed_booking(booking_id, action):
    booking = get_temp_data_item('bed_bookings', booking_id)
    
    is_hospital = getattr(current_user, 'is_hospital', False)
    if is_hospital:
        hospital = current_user
    else:
        hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.name == getattr(current_user, 'hospital_name', '')), None)

    if not booking or not hospital or str(booking.hospital_id) != str(hospital.id):
        flash("Booking not found or unauthorized.", "error")
        return redirect(request.referrer or url_for('home'))

    if action == 'undo_reject':
        if booking.status == 'rejected':
            booking.status = 'pending'
            flash("Rejection undone. Status is pending.", "success")
        else:
            flash("Can only undo rejected bookings.", "warning")
    else:
        if booking.status != 'pending':
            flash("This booking has already been processed.", "warning")
            return redirect(request.referrer or url_for('home'))

        if action == 'approve':
            room_number = request.form.get('room_number', 'N/A')
            if booking.bed_type == 'ICU':
                if hospital.available_icu_beds > 0:
                    hospital.available_icu_beds -= 1
                    booking.status = 'approved'
                    booking.room_number = room_number
                    flash("ICU Bed booking approved and availability updated.", "success")
                    if booking.patient_id != 'walk-in':
                        create_notification(
                            user_id=booking.patient_id,
                            user_type='patient',
                            message=f"Your ICU Bed booking at {hospital.name} has been approved! Room: {room_number}.",
                            link="/patient/dashboard?tab=beds"
                        )
                else:
                    flash("No ICU beds available!", "error")
            else:
                if hospital.available_beds > 0:
                    hospital.available_beds -= 1
                    booking.status = 'approved'
                    booking.room_number = room_number
                    flash("General Bed booking approved and availability updated.", "success")
                    if booking.patient_id != 'walk-in':
                        create_notification(
                            user_id=booking.patient_id,
                            user_type='patient',
                            message=f"Your General Bed booking at {hospital.name} has been approved! Room: {room_number}.",
                            link="/patient/dashboard?tab=beds"
                        )
                else:
                    flash("No General beds available!", "error")
        elif action == 'reject':
            booking.status = 'rejected'
            flash("Bed booking rejected.", "success")
            if booking.patient_id != 'walk-in':
                create_notification(
                    user_id=booking.patient_id,
                    user_type='patient',
                    message=f"Your Bed booking request at {hospital.name} has been rejected.",
                    link="/patient/dashboard?tab=beds"
                )
    
    save_data()
    return redirect(request.referrer or url_for('home'))



@hospital_bp.route('/bed_booking/invoice/<int:booking_id>')
@login_required
def bed_booking_invoice(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if not booking:
        flash("Booking not found.", "error")
        return redirect(url_for('home'))

    pat_id_str = str(getattr(booking, 'patient_id', ''))
    user_id_str = str(getattr(current_user, 'id', ''))
    user_lic_str = str(getattr(current_user, 'license_no', ''))
    is_patient = (getattr(current_user, 'is_patient', False) or (hasattr(current_user, 'is_doctor') and not current_user.is_doctor)) and (
        pat_id_str in (user_id_str, user_lic_str) or
        (getattr(booking, 'patient_phone', None) and getattr(current_user, 'phone', None) and str(booking.patient_phone).strip() == str(current_user.phone).strip()) or
        (getattr(booking, 'patient_name', '').strip().lower() == getattr(current_user, 'name', '').strip().lower())
    )
    is_hospital = getattr(current_user, 'is_hospital', False) and str(getattr(booking, 'hospital_id', '')) == str(current_user.id)
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@spherixclinic.com'

    if not (is_patient or is_hospital or is_admin):
        flash("Unauthorized access to invoice.", "error")
        return redirect(url_for('home'))

    if booking.status != 'approved':
        flash("Invoice is only available for approved bookings.", "warning")
        return redirect(request.referrer or url_for('home'))

    hospital = TEMP_DATA.get('hospitals', {}).get(booking.hospital_id)
    hosp_name = getattr(hospital, 'name', 'Affiliated Healthcare Hospital')
    hosp_address = getattr(hospital, 'address', 'Medical District Central Facility')
    fee = (getattr(hospital, 'icu_bed_fee', 2500) if booking.bed_type == 'ICU' else getattr(hospital, 'general_bed_fee', 800)) if hospital else (2500 if booking.bed_type == 'ICU' else 800)

    try:
        class BedBookingInvoicePDF(FPDF):
            def header(self):
                # Page Border
                self.set_draw_color(15, 23, 42)
                self.set_line_width(0.8)
                self.rect(8, 8, 194, 281)

                # Modern Header Banner
                self.set_fill_color(15, 23, 42) # Deep Slate/Navy
                self.rect(8, 8, 194, 26, 'F')
                
                self.set_y(13)
                self.set_font('Helvetica', 'B', 16)
                self.set_text_color(255, 255, 255)
                self.cell(0, 8, 'SPHERIX CLINIC - BED BOOKING INVOICE', 0, 1, 'C')
                self.set_font('Helvetica', 'B', 8)
                self.set_text_color(156, 163, 175) # Light gray
                self.cell(0, 4, 'SECURE CLINICAL INFRASTRUCTURE PORTAL', 0, 1, 'C')
                self.set_text_color(0, 0, 0)
                
            def footer(self):
                self.set_y(-22)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.set_draw_color(229, 231, 235)
                self.set_line_width(0.2)
                self.line(12, self.get_y(), 198, self.get_y())
                self.ln(2)
                self.cell(0, 4, 'Disclaimer: This invoice is a legally binding payment receipt. Keep secure.', 0, 1, 'C')
                self.cell(0, 4, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} // Spherix Health Systems', 0, 1, 'C')

        pdf = BedBookingInvoicePDF()
        pdf.add_page()
        pdf.set_margins(12, 12, 12)
        pdf.ln(18) # Add space after header
        
        # Hospital details header
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, to_latin1_str(hosp_name), 0, 1, 'L')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, to_latin1_str(hosp_address or 'N/A'), 0, 1, 'L')
        pdf.ln(4)
        
        # Meta Block
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Invoice Reference:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(65, 6, f'BB-{booking.id}', 0, 0, 'L')
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Billing Date:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        billing_date = booking.created_at.strftime('%Y-%m-%d') if hasattr(booking.created_at, 'strftime') else (str(booking.created_at)[:10] if booking.created_at else datetime.now().strftime('%Y-%m-%d'))
        pdf.cell(0, 6, billing_date, 0, 1, 'L')
        
        pdf.ln(5)
        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.3)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(5)
        
        # Column Details Block (Billed To vs Booking Details)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(93, 8, 'Billed To:', 0, 0, 'L')
        pdf.cell(93, 8, 'Booking Details:', 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(93, 5, to_latin1_str(booking.patient_name), 0, 0, 'L')
        pdf.cell(93, 5, f'Status: {booking.status.capitalize()}', 0, 1, 'L')
        
        pdf.cell(93, 5, f'Phone: {booking.patient_phone}', 0, 0, 'L')
        pdf.cell(93, 5, f'Assigned Bed: {booking.bed_type} - #{getattr(booking, "room_number", "N/A")}', 0, 1, 'L')
        
        pdf.ln(10)
        
        # Tabular Itemized Grid
        pdf.set_fill_color(240, 246, 255) # Soft Blue fill
        pdf.set_draw_color(191, 219, 254) # Blue-200 border
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(30, 58, 138) # Dark Blue text
        pdf.cell(136, 10, '  Item Description', 1, 0, 'L', fill=True)
        pdf.cell(50, 10, 'Amount  ', 1, 1, 'R', fill=True)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        desc = f"Emergency {booking.bed_type} Bed Booking - Spherix Network Support"
        pdf.cell(136, 10, f"  {desc}", 1, 0, 'L')
        pdf.cell(50, 10, f"Rs. {fee:.2f}  ", 1, 1, 'R')
        
        # Grand Total Row
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(136, 12, 'Grand Total Paid:  ', 0, 0, 'R')
        pdf.set_text_color(30, 58, 138)
        pdf.cell(50, 12, f"Rs. {fee:.2f}  ", 1, 1, 'R')
        
        pdf.ln(12)
        
        # PAID Stamp / Badge
        pdf.set_fill_color(209, 250, 229) # Light green
        pdf.set_draw_color(16, 185, 129) # Green border
        pdf.set_line_width(0.5)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(6, 95, 70) # Dark green text
        # Center the stamp
        pdf.set_x(70)
        pdf.cell(70, 10, 'PAID & CLINICALLY APPROVED', 1, 1, 'C', fill=True)

        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode('latin-1', 'replace')
        else:
            pdf_bytes = pdf_output

        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'bed_booking_invoice_{booking.id}.pdf', mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating bed booking invoice: {e}")
        flash("An error occurred while generating the invoice.", "error")
        return redirect(request.referrer or url_for('home'))



@hospital_bp.route('/hospital/bed_booking/<int:booking_id>/email_invoice', methods=['POST'])
@hospital_required
def email_bed_booking_invoice(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if not booking or str(booking.hospital_id) != str(current_user.id):
        flash("Booking not found or unauthorized.", "error")
        return redirect(url_for('hospital_dashboard') + '#beds')

    if booking.status != 'approved':
        flash("Invoice is only available for approved bookings.", "warning")
        return redirect(url_for('hospital_dashboard') + '#beds')

    patient = TEMP_DATA['patients'].get(booking.patient_id)
    if not patient or not patient.email:
        flash("Patient email not found.", "error")
        return redirect(url_for('hospital_dashboard') + '#beds')

    hospital = TEMP_DATA['hospitals'].get(booking.hospital_id)
    fee = hospital.icu_bed_fee if booking.bed_type == 'ICU' else hospital.general_bed_fee

    try:
        class BedBookingInvoicePDF(FPDF):
            def header(self):
                # Page Border
                self.set_draw_color(15, 23, 42)
                self.set_line_width(0.8)
                self.rect(8, 8, 194, 281)

                # Modern Header Banner
                self.set_fill_color(15, 23, 42) # Deep Slate/Navy
                self.rect(8, 8, 194, 26, 'F')
                
                self.set_y(13)
                self.set_font('Helvetica', 'B', 16)
                self.set_text_color(255, 255, 255)
                self.cell(0, 8, 'SPHERIX CLINIC - BED BOOKING INVOICE', 0, 1, 'C')
                self.set_font('Helvetica', 'B', 8)
                self.set_text_color(156, 163, 175) # Light gray
                self.cell(0, 4, 'SECURE CLINICAL INFRASTRUCTURE PORTAL', 0, 1, 'C')
                self.set_text_color(0, 0, 0)
                
            def footer(self):
                self.set_y(-22)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.set_draw_color(229, 231, 235)
                self.set_line_width(0.2)
                self.line(12, self.get_y(), 198, self.get_y())
                self.ln(2)
                self.cell(0, 4, 'Disclaimer: This invoice is a legally binding payment receipt. Keep secure.', 0, 1, 'C')
                self.cell(0, 4, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} // Spherix Health Systems', 0, 1, 'C')

        pdf = BedBookingInvoicePDF()
        pdf.add_page()
        pdf.set_margins(12, 12, 12)
        pdf.ln(18) # Add space after header
        
        # Hospital details header
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, to_latin1_str(hospital.name), 0, 1, 'L')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, to_latin1_str(hospital.address or 'N/A'), 0, 1, 'L')
        pdf.ln(4)
        
        # Meta Block
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Invoice Reference:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(65, 6, f'BB-{booking.id}', 0, 0, 'L')
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Billing Date:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, booking.created_at.strftime('%Y-%m-%d'), 0, 1, 'L')
        
        pdf.ln(5)
        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.3)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(5)
        
        # Column Details Block (Billed To vs Booking Details)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(93, 8, 'Billed To:', 0, 0, 'L')
        pdf.cell(93, 8, 'Booking Details:', 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(93, 5, to_latin1_str(booking.patient_name), 0, 0, 'L')
        pdf.cell(93, 5, f'Status: {booking.status.capitalize()}', 0, 1, 'L')
        
        pdf.cell(93, 5, f'Phone: {booking.patient_phone}', 0, 0, 'L')
        pdf.cell(93, 5, f'Assigned Bed: {booking.bed_type} - #{getattr(booking, "room_number", "N/A")}', 0, 1, 'L')
        
        pdf.ln(10)
        
        # Tabular Itemized Grid
        pdf.set_fill_color(240, 246, 255) # Soft Blue fill
        pdf.set_draw_color(191, 219, 254) # Blue-200 border
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(30, 58, 138) # Dark Blue text
        pdf.cell(136, 10, '  Item Description', 1, 0, 'L', fill=True)
        pdf.cell(50, 10, 'Amount  ', 1, 1, 'R', fill=True)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        desc = f"Emergency {booking.bed_type} Bed Booking - Spherix Network Support"
        pdf.cell(136, 10, f"  {desc}", 1, 0, 'L')
        pdf.cell(50, 10, f"Rs. {fee:.2f}  ", 1, 1, 'R')
        
        # Grand Total Row
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(136, 12, 'Grand Total Paid:  ', 0, 0, 'R')
        pdf.set_text_color(30, 58, 138)
        pdf.cell(50, 12, f"Rs. {fee:.2f}  ", 1, 1, 'R')
        
        pdf.ln(12)
        
        # PAID Stamp / Badge
        pdf.set_fill_color(209, 250, 229) # Light green
        pdf.set_draw_color(16, 185, 129) # Green border
        pdf.set_line_width(0.5)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(6, 95, 70) # Dark green text
        # Center the stamp
        pdf.set_x(70)
        pdf.cell(70, 10, 'PAID & CLINICALLY APPROVED', 1, 1, 'C', fill=True)

        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode('latin-1', 'replace')
        else:
            pdf_bytes = pdf_output

        # Send Email
        subject = f"Invoice for Emergency Bed Booking - {hospital.name}"
        body = f"Dear {patient.name},\n\nPlease find attached the invoice for your emergency {booking.bed_type} bed booking at {hospital.name}.\n\nBest regards,\n{hospital.name}"
        
        if send_notification_email(patient.email, subject, body, is_html=False, attachment_name=f'bed_booking_invoice_{booking.id}.pdf', attachment_data=pdf_bytes):
            flash(f"Invoice emailed successfully to {patient.email}.", "success")
        else:
            flash("Failed to send email. Check your email configuration.", "error")

    except Exception as e:
        print(f"Error emailing bed booking invoice: {e}")
        flash("An error occurred while generating or sending the invoice.", "error")

    return redirect(url_for('hospital_dashboard') + '#beds')




@hospital_bp.route('/hospital/dashboard', methods=['GET', 'POST'])
@hospital_required
def hospital_dashboard():
    """Displays the hospital dashboard with appointments, doctors, and settings."""
    
    # 1. Handle POST requests (Forms)
    if request.method == 'POST':
        # --- Add Doctor ---
        if 'add_doctor' in request.form:
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                flash('Email and password are required.', 'error')
                return redirect(url_for('hospital_dashboard') + '#doctors')
                
            # Check if doctor exists globally
            existing = next((d for d in TEMP_DATA['doctors'].values() if d.email == email), None)
            if existing:
                flash('A doctor with this email already exists in the system.', 'error')
            else:
                year = datetime.now().year
                next_id_num = TEMP_DATA['next_ids']['doctor']
                new_id = f"DOC/{year}/{next_id_num:03d}"
                
                new_doctor = Doctor(
                    id=new_id,
                    first_name=request.form.get('first_name'),
                    last_name=request.form.get('last_name'),
                    email=email,
                    password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
                    department=request.form.get('department'),
                    hospital_id=current_user.id,
                    hospital_approval_status='pending',
                    hospital_name=None,
                    hospital_address=None,
                    phone=request.form.get('phone'),
                    specialization=request.form.get('specialization')
                )
                TEMP_DATA['doctors'][new_id] = new_doctor
                TEMP_DATA['next_ids']['doctor'] += 1
                save_data()
                flash(f'Dr. {new_doctor.last_name} registered successfully. Pending approval on their dashboard.', 'success')
            return redirect(url_for('hospital_dashboard') + '#doctors')

        # --- Invite Existing Doctor ---
        elif 'invite_doctor' in request.form:
            doc_id = request.form.get('invited_doctor_id')
            invited_doc = TEMP_DATA['doctors'].get(doc_id)
            if not invited_doc:
                flash('Doctor not found in the system.', 'error')
            elif invited_doc.hospital_id == current_user.id:
                flash('This doctor is already associated with your hospital.', 'error')
            else:
                invited_doc.hospital_id = current_user.id
                invited_doc.hospital_approval_status = 'pending'
                save_data()
                flash(f'Invitation sent to Dr. {invited_doc.last_name} successfully. Pending their approval.', 'success')
            return redirect(url_for('hospital_dashboard') + '#doctors')

        # --- Add Staff ---
        elif 'add_staff' in request.form:
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                flash('Email and password are required.', 'error')
                return redirect(url_for('hospital_dashboard') + '#staff')
                
            existing = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)
            if existing:
                flash('A staff member with this email already exists.', 'error')
            else:
                staff_id = f"STF/{datetime.now().year}/{TEMP_DATA['next_ids']['staff']:03d}"
                
                profile_pic = None
                if 'profilePicture' in request.files:
                    file = request.files['profilePicture']
                    if file and file.filename != '':
                        if allowed_file(file.filename):
                            profile_pic = save_user_profile_image(
                                file,
                                target_size=(500, 500),
                                filename_prefix=f"staff_profile_{str(staff_id).replace('/', '_')}"
                            )
                        else:
                            flash('Invalid image file format.', 'error')
                
                new_staff = Staff(
                    id=staff_id,
                    name=request.form.get('name'),
                    email=email,
                    password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
                    role=request.form.get('role'),
                    phone=request.form.get('phone'),
                    hospital_name=current_user.name,
                    profile_picture_url=profile_pic
                )
                TEMP_DATA['staff'][staff_id] = new_staff
                TEMP_DATA['next_ids']['staff'] += 1
                save_data()
                flash(f'Staff member {new_staff.name} added successfully.', 'success')
            return redirect(url_for('hospital_dashboard') + '#staff')

        # --- Edit Staff ---
        elif 'edit_staff' in request.form:
            staff_id_str = request.form.get('staff_id')
            if staff_id_str:
                staff_id = parse_route_id(staff_id_str)
                if staff_id in TEMP_DATA['staff']:
                    staff_member = TEMP_DATA['staff'][staff_id]
                    if staff_member.hospital_name == current_user.name:
                        staff_member.name = request.form.get('name')
                        staff_member.email = request.form.get('email')
                        staff_member.role = request.form.get('role')
                        staff_member.phone = request.form.get('phone')
                        
                        new_password = request.form.get('password')
                        if new_password:
                            staff_member.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
                        
                        save_data()
                        flash('Staff member updated successfully.', 'success')
                    else:
                        flash('Permission denied.', 'error')
            return redirect(url_for('hospital_dashboard'))

        # --- Delete Staff ---
        elif 'delete_staff' in request.form:
            staff_id_str = request.form.get('staff_id')
            if staff_id_str:
                staff_id = parse_route_id(staff_id_str)
                if staff_id in TEMP_DATA['staff']:
                    staff_member = TEMP_DATA['staff'][staff_id]
                    if staff_member.hospital_name == current_user.name:
                        del TEMP_DATA['staff'][staff_id]
                        save_data()
                        flash('Staff member removed successfully.', 'success')
                    else:
                        flash('Permission denied.', 'error')
                else:
                    flash('Staff member not found.', 'error')
            return redirect(url_for('hospital_dashboard'))
            
        elif 'toggle_staff_block' in request.form:
            staff_id_str = request.form.get('staff_id')
            if staff_id_str:
                staff_id = parse_route_id(staff_id_str)
                staff_member = TEMP_DATA.get('staff', {}).get(staff_id)
                if staff_member and staff_member.hospital_name == current_user.name:
                    staff_member.is_blocked = not getattr(staff_member, 'is_blocked', False)
                    save_data()
                    flash(f"Staff member account has been {'blocked' if staff_member.is_blocked else 'unblocked'}.", "success")
            return redirect(url_for('hospital_dashboard') + '#staff')

        # --- Add Blood Donor ---
        elif 'add_blood_donor' in request.form:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            phone = request.form.get('phone')
            blood_group = request.form.get('blood_group')
            age_val = request.form.get('age')
            age = int(age_val) if age_val and age_val.strip().isdigit() else 0
            city = request.form.get('city')
            
            if not all([name, email, password, phone, blood_group, city]):
                flash("All required fields must be filled.", "error")
            elif any(d.email == email for d in TEMP_DATA['blood_donors'].values()):
                flash("A blood donor with this email already exists.", "error")
            else:
                donor_id = f"BD/{datetime.now().year}/{TEMP_DATA['next_ids']['blood_donor']:03d}"
                new_donor = BloodDonor(
                    id=donor_id,
                    name=name,
                    email=email,
                    phone=phone,
                    blood_group=blood_group,
                    age=age,
                    city=city,
                    password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
                    hospital_id=current_user.id,
                    status='approved'
                )
                TEMP_DATA['blood_donors'][donor_id] = new_donor
                TEMP_DATA['next_ids']['blood_donor'] += 1
                save_data()
                flash(f"Blood donor '{name}' registered successfully with ID: {donor_id}.", "success")
            return redirect(url_for('hospital_dashboard') + '#blood')

        # --- Add Organ Donor ---
        elif 'add_organ_donor' in request.form:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            phone = request.form.get('phone')
            blood_group = request.form.get('blood_group')
            age_val = request.form.get('age')
            age = int(age_val) if age_val and age_val.strip().isdigit() else 0
            city = request.form.get('city')
            organs = request.form.getlist('organs')
            
            if not all([name, email, password, phone, blood_group, city]) or not organs:
                flash("All required fields must be filled and at least one organ selected.", "error")
            elif any(d.email == email for d in TEMP_DATA['organ_donors'].values()):
                flash("An organ donor with this email already exists.", "error")
            else:
                donor_id = f"OD/{datetime.now().year}/{TEMP_DATA['next_ids']['organ_donor']:03d}"
                new_donor = OrganDonor(
                    id=donor_id,
                    name=name,
                    email=email,
                    phone=phone,
                    organs=organs,
                    blood_group=blood_group,
                    age=age,
                    city=city,
                    password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
                    hospital_id=current_user.id,
                    status='approved'
                )
                TEMP_DATA['organ_donors'][donor_id] = new_donor
                TEMP_DATA['next_ids']['organ_donor'] += 1
                save_data()
                flash(f"Organ donor '{name}' registered successfully with ID: {donor_id}.", "success")
            return redirect(url_for('hospital_dashboard') + '#organs')

        # --- Update Profile ---
        elif 'update_profile' in request.form:
            # Check if new email is unique
            new_email = request.form.get('email')
            if new_email != current_user.email:
                existing_hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == new_email), None)
                if existing_hospital:
                    flash('This email is already registered to another hospital.', 'error')
                    return redirect(url_for('hospital_dashboard') + '#settings')
                current_user.email = new_email
            
            # Update basic info
            current_user.name = request.form.get('name')
            current_user.president_ceo = request.form.get('president_ceo', '').strip() or getattr(current_user, 'president_ceo', 'Managing Director')
            current_user.director_name = current_user.president_ceo
            current_user.superintendent_name = request.form.get('superintendent_name', '').strip() or getattr(current_user, 'superintendent_name', 'Medical Superintendent')
            current_user.blood_bank_staff = current_user.superintendent_name
            current_user.phone = request.form.get('phone')
            current_user.address = request.form.get('address')
            current_user.city = request.form.get('city')
            current_user.state = request.form.get('state')
            current_user.zip_code = request.form.get('zip_code')

            # Classification & Specialization Updates
            hosp_type_id = request.form.get('hospital_type_id')
            if hosp_type_id:
                try:
                    current_user.hospital_type_id = int(hosp_type_id)
                    ht_obj = get_hospital_type_by_id(current_user.hospital_type_id)
                    if ht_obj:
                        current_user.hospital_type = ht_obj.name
                except (ValueError, TypeError):
                    pass
            elif request.form.get('facility_type'):
                current_user.hospital_type = request.form.get('facility_type')

            # Specialties
            spec_list = request.form.getlist('specialties')
            if not spec_list and request.form.get('specialties_csv'):
                spec_list = [s.strip() for s in request.form.get('specialties_csv').split(',') if s.strip()]
            if spec_list:
                current_user.specialties = spec_list

            # Facilities
            fac_list = request.form.getlist('facilities')
            if not fac_list and request.form.get('facilities_csv'):
                fac_list = [f.strip() for f in request.form.get('facilities_csv').split(',') if f.strip()]
            if fac_list:
                current_user.facilities = fac_list

            # Emergency Services
            if 'emergency_services' in request.form:
                current_user.emergency_services = request.form.get('emergency_services') in ['on', 'true', '1', True]
            if request.form.get('emergency_phone'):
                current_user.emergency_phone = request.form.get('emergency_phone').strip()
            if request.form.get('ambulance_phone'):
                current_user.ambulance_phone = request.form.get('ambulance_phone').strip()

            # About & Geolocation Coordinates
            if 'about' in request.form:
                current_user.about = request.form.get('about', '').strip()
            if request.form.get('latitude'):
                try:
                    current_user.latitude = float(request.form.get('latitude'))
                except (ValueError, TypeError):
                    pass
            if request.form.get('longitude'):
                try:
                    current_user.longitude = float(request.form.get('longitude'))
                except (ValueError, TypeError):
                    pass
            
            # Handle Logo / Profile Image Upload (Base64 cropped or raw file)
            logo_input = request.form.get('cropped_profile_image') or request.form.get('logo_base64')
            if not logo_input and 'logo' in request.files:
                file = request.files['logo']
                if file and file.filename != '':
                    logo_input = file

            if logo_input:
                saved_logo = save_user_profile_image(
                    logo_input,
                    target_size=(500, 500),
                    filename_prefix=f"hospital_logo_{current_user.id}",
                    subfolder='hospital_logos'
                )
                if saved_logo:
                    current_user.logo_url = saved_logo
                    current_user.profile_picture_url = saved_logo
            
            # Synchronize into TEMP_DATA
            if current_user.id in TEMP_DATA.get('hospitals', {}):
                hosp_mem = TEMP_DATA['hospitals'][current_user.id]
                hosp_mem.name = current_user.name
                hosp_mem.email = current_user.email
                hosp_mem.president_ceo = current_user.president_ceo
                hosp_mem.director_name = current_user.director_name
                hosp_mem.superintendent_name = current_user.superintendent_name
                hosp_mem.blood_bank_staff = current_user.blood_bank_staff
                hosp_mem.phone = current_user.phone
                hosp_mem.address = current_user.address
                hosp_mem.city = current_user.city
                hosp_mem.state = current_user.state
                hosp_mem.zip_code = current_user.zip_code
                hosp_mem.hospital_type_id = getattr(current_user, 'hospital_type_id', 1)
                hosp_mem.hospital_type = getattr(current_user, 'hospital_type', 'General Hospital')
                hosp_mem.specialties = getattr(current_user, 'specialties', [])
                hosp_mem.facilities = getattr(current_user, 'facilities', [])
                hosp_mem.emergency_services = getattr(current_user, 'emergency_services', True)
                hosp_mem.emergency_phone = getattr(current_user, 'emergency_phone', None)
                hosp_mem.ambulance_phone = getattr(current_user, 'ambulance_phone', None)
                hosp_mem.about = getattr(current_user, 'about', '')
                hosp_mem.latitude = getattr(current_user, 'latitude', None)
                hosp_mem.longitude = getattr(current_user, 'longitude', None)
                hosp_mem.logo_url = getattr(current_user, 'logo_url', None)
            
            save_data()
            flash('Hospital profile and clinical classification updated successfully.', 'success')
            return redirect(url_for('hospital_dashboard') + '#settings')

        # --- Update Security ---
        elif 'update_security' in request.form:
            current_password = request.form.get('current_password')
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('hospital_dashboard') + '#settings')
            
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('hospital_dashboard') + '#settings')
            
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
            save_data()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('hospital_dashboard') + '#settings')

        # --- Update Resources ---
        elif 'update_resources' in request.form:
            try:
                total = int(request.form.get('total_beds', current_user.total_beds))
                available = int(request.form.get('available_beds', current_user.available_beds))
                icu = int(request.form.get('icu_beds', current_user.icu_beds))
                avail_icu = int(request.form.get('available_icu_beds', current_user.available_icu_beds))
                
                if available > total or avail_icu > icu:
                    flash('Available beds cannot exceed total capacity.', 'warning')
                else:
                    current_user.total_beds = total
                    current_user.available_beds = available
                    current_user.icu_beds = icu
                    current_user.available_icu_beds = avail_icu
                    
                    if 'general_bed_fee' in request.form:
                        current_user.general_bed_fee = float(request.form.get('general_bed_fee', current_user.general_bed_fee))
                    if 'icu_bed_fee' in request.form:
                        current_user.icu_bed_fee = float(request.form.get('icu_bed_fee', current_user.icu_bed_fee))
                        
                    current_user.doctors_available = request.form.get('doctors_available', current_user.doctors_available)
                    
                    save_data()
                    flash('Resources and availability updated successfully.', 'success')
            except ValueError:
                flash('Invalid input for resources.', 'error')
            return redirect(url_for('hospital_dashboard') + '#settings')

        # --- Delete Doctor ---
        elif 'delete_doctor' in request.form:
            doc_id = request.form.get('doctor_id')
            if doc_id in TEMP_DATA['doctors']:
                if TEMP_DATA['doctors'][doc_id].hospital_name == current_user.name:
                    # Cleanup related data
                    appointments_to_delete = [k for k, v in TEMP_DATA['appointments'].items() if v.doctor_id == doc_id]
                    for appt_id in appointments_to_delete:
                        del TEMP_DATA['appointments'][appt_id]
                    
                    reviews_to_delete = [k for k, v in TEMP_DATA['reviews'].items() if v.doctor_id == doc_id]
                    for review_id in reviews_to_delete:
                        del TEMP_DATA['reviews'][review_id]

                    messages_to_delete = [k for k, v in TEMP_DATA['messages'].items() if v.doctor_id == doc_id]
                    for msg_id in messages_to_delete:
                        del TEMP_DATA['messages'][msg_id]

                    del TEMP_DATA['doctors'][doc_id]
                    save_data()
                    flash('Doctor removed successfully.', 'success')
                else:
                    flash('Permission denied.', 'error')
            else:
                flash('Doctor not found.', 'error')
            return redirect(url_for('hospital_dashboard'))

        # --- Update Beds ---
        elif 'update_beds' in request.form:
            try:
                total = int(request.form.get('total_beds', current_user.total_beds))
                available = int(request.form.get('available_beds', current_user.available_beds))
                icu = int(request.form.get('icu_beds', current_user.icu_beds))
                avail_icu = int(request.form.get('available_icu_beds', current_user.available_icu_beds))
                
                if available > total or avail_icu > icu:
                    flash('Available beds cannot exceed total capacity.', 'warning')
                else:
                    current_user.total_beds = total
                    current_user.available_beds = available
                    current_user.icu_beds = icu
                    current_user.available_icu_beds = avail_icu
                    save_data()
                    flash('Bed availability updated successfully.', 'success')
            except ValueError:
                flash('Invalid input for bed counts.', 'error')
            return redirect(url_for('hospital_dashboard'))
            
        # --- Add Camp ---
        elif 'add_camp' in request.form:
            name = request.form.get('name')
            location = request.form.get('location')
            date_str = request.form.get('date')
            time_str = request.form.get('time')
            contact = request.form.get('contact')

            if all([name, location, date_str, time_str]):
                camp_id = TEMP_DATA['next_ids']['camp']
                try:
                    formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y')
                except ValueError:
                    formatted_date = date_str

                new_camp = {
                    "id": camp_id,
                    "name": name,
                    "location": location,
                    "date": formatted_date,
                    "time": time_str,
                    "organizer": current_user.name,
                    "contact": contact
                }
                TEMP_DATA['camps'][camp_id] = new_camp
                TEMP_DATA['next_ids']['camp'] += 1
                save_data()
                flash("Blood donation camp added successfully.", "success")
            else:
                flash("Missing required fields.", "error")
            return redirect(url_for('hospital_dashboard') + '#camps')

        # --- Delete Camp ---
        elif 'delete_camp' in request.form:
            camp_id = int(request.form.get('camp_id'))
            if camp_id in TEMP_DATA['camps']:
                if TEMP_DATA['camps'][camp_id].get('organizer') == current_user.name:
                    del TEMP_DATA['camps'][camp_id]
                    save_data()
                    flash("Camp deleted successfully.", "success")
                else:
                    flash("Permission denied.", "error")
            return redirect(url_for('hospital_dashboard') + '#camps')

    # Filter ALL doctors belonging to this hospital (both approved and pending)
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or \
           (getattr(d, 'hospital_name', None) and d.hospital_name == current_user.name)
    ]
    pending_doctors = [
        d for d in hospital_doctors
        if getattr(d, 'hospital_approval_status', 'approved') == 'pending'
    ]
    available_unlinked_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if str(getattr(d, 'hospital_id', '')) != str(current_user.id) and \
           (not getattr(d, 'hospital_name', None) or d.hospital_name != current_user.name)
    ]
    
    # Filter staff belonging to this hospital
    hospital_staff = [s for s in TEMP_DATA['staff'].values() if s.hospital_name == current_user.name]
    
    # Filter appointments for doctors in this hospital
    hospital_appointments = []
    unique_patient_ids = set()
    
    for appt in TEMP_DATA['appointments'].values():
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        if doc and (doc.hospital_id == current_user.id or doc.hospital_name == current_user.name):
            hospital_appointments.append(appt)
            if appt.patient_id:
                unique_patient_ids.add(appt.patient_id)

    # Sort appointments by date (newest first)
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    
    # Get Patient objects
    hospital_patients = [TEMP_DATA['patients'][pid] for pid in unique_patient_ids if pid in TEMP_DATA['patients']]

    # Stats & Multi-dimensional Analytics Data
    today = date.today()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart_labels = [d.strftime('%b %d') for d in last_7_days]
    
    # 7-day appointment volume
    appt_counts_by_day = Counter(a.appointment_date for a in hospital_appointments if a.appointment_date)
    chart_data = [appt_counts_by_day.get(d, 0) for d in last_7_days]

    # Filter camps organized by this hospital
    hospital_camps = [c for c in TEMP_DATA['camps'].values() if c.get('organizer') == current_user.name]
    
    # Filter Bed Bookings for this hospital
    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if str(b.hospital_id) == str(current_user.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)

    all_blood_donors = [d for d in TEMP_DATA.get('blood_donors', {}).values() if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or not getattr(d, 'hospital_id', None)]
    all_organ_donors = [d for d in TEMP_DATA.get('organ_donors', {}).values() if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or not getattr(d, 'hospital_id', None)]
    blood_stock = current_user.blood_stock if hasattr(current_user, 'blood_stock') and isinstance(current_user.blood_stock, dict) else TEMP_DATA.get('blood_stock', {})

    # Calculate revenue figures
    total_appointment_revenue = 0.0
    for appt in hospital_appointments:
        if appt.status in ['completed', 'approved', 'paid', 'confirmed']:
            doc = TEMP_DATA['doctors'].get(appt.doctor_id)
            if doc:
                try:
                    fee = float(str(doc.consultation_fee).replace('₹', '').replace(',', '').strip() or 0)
                except ValueError:
                    fee = 150.0
                total_appointment_revenue += fee

    total_bed_revenue = 0.0
    for booking in hospital_bed_bookings:
        if booking.status in ['approved', 'discharged', 'paid', 'pending']:
            fee = float(getattr(current_user, 'icu_bed_fee', 2500.0) if booking.bed_type == 'ICU' else getattr(current_user, 'general_bed_fee', 1000.0))
            total_bed_revenue += fee

    # 7-day revenue trend
    revenue_by_day = {d: 0.0 for d in last_7_days}
    for a in hospital_appointments:
        if a.appointment_date in revenue_by_day and a.status in ['completed', 'approved', 'paid', 'confirmed']:
            doc = TEMP_DATA['doctors'].get(a.doctor_id)
            fee = 150.0
            if doc:
                try:
                    fee = float(str(doc.consultation_fee).replace('₹', '').replace(',', '').strip() or 0)
                except ValueError:
                    fee = 150.0
            revenue_by_day[a.appointment_date] += fee
            
    for b in hospital_bed_bookings:
        b_date = b.created_at.date() if hasattr(b.created_at, 'date') else today
        if b_date in revenue_by_day and b.status in ['approved', 'discharged', 'paid', 'pending']:
            fee = float(getattr(current_user, 'icu_bed_fee', 2500.0) if b.bed_type == 'ICU' else getattr(current_user, 'general_bed_fee', 1000.0))
            revenue_by_day[b_date] += fee
            
    revenue_chart_data = [round(revenue_by_day[d], 2) for d in last_7_days]

    # Department distribution
    dept_counter = Counter()
    for doc in hospital_doctors:
        dept = doc.department or 'General Medicine'
        dept_counter[dept] += 1
    for appt in hospital_appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        dept = doc.department if (doc and doc.department) else 'General Medicine'
        dept_counter[dept] += 1
    if not dept_counter:
        dept_counter = {'General Medicine': 2, 'Cardiology': 1, 'Orthopaedics': 1}
    dept_labels = list(dept_counter.keys())
    dept_data = list(dept_counter.values())

    # Bed capacity & occupancy
    total_beds = current_user.total_beds if current_user.total_beds is not None else 50
    available_beds = current_user.available_beds if current_user.available_beds is not None else 40
    icu_beds = current_user.icu_beds if current_user.icu_beds is not None else 10
    available_icu_beds = current_user.available_icu_beds if current_user.available_icu_beds is not None else 8
    
    occupied_general = max(0, total_beds - available_beds)
    occupied_icu = max(0, icu_beds - available_icu_beds)
    bed_distribution_data = [occupied_general, available_beds, occupied_icu, available_icu_beds]
    
    total_bed_capacity = total_beds + icu_beds
    bed_occupancy_percent = round(((occupied_general + occupied_icu) / total_bed_capacity * 100)) if total_bed_capacity > 0 else 0

    # Clinical Triage & Status Breakdown
    status_counter = Counter(a.status for a in hospital_appointments)
    case_status_labels = ["Confirmed OPD", "Pending / Triage", "Emergency Beds", "Discharged / Done"]
    case_status_data = [
        status_counter.get('confirmed', 0),
        status_counter.get('pending', 0) + status_counter.get('awaiting_payment', 0),
        len([b for b in hospital_bed_bookings if b.status in ['pending', 'approved']]),
        status_counter.get('completed', 0) + status_counter.get('discharged', 0) + len([b for b in hospital_bed_bookings if b.status == 'discharged'])
    ]

    # Blood Bank stock
    blood_group_labels = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    blood_group_data = [blood_stock.get(bg, 0) for bg in blood_group_labels]

    # Get activity logs for this hospital
    activity_logs = [log for log in TEMP_DATA.get('activity_logs', {}).values() if getattr(log, 'hospital_id', None) == current_user.id]

    hospital_doctor_ids = {doctor.id for doctor in hospital_doctors}
    hospital_admissions = [
        booking for booking in hospital_bed_bookings
        if booking.status in ['approved', 'active', 'paid']
    ]
    hospital_emergency_cases = [
        booking for booking in hospital_bed_bookings
        if 'emergency' in str(getattr(booking, 'reason', '')).lower() or booking.bed_type == 'ICU'
    ]
    hospital_opd_appointments = [
        appointment for appointment in hospital_appointments
        if appointment.appointment_date == today and appointment.status != 'cancelled'
    ]
    hospital_telemedicine_appointments = [
        appointment for appointment in hospital_appointments
        if any(term in str(getattr(appointment, 'reason', '')).lower() for term in ['video', 'telemedicine', 'online', 'virtual'])
    ]
    hospital_emr_records = [
        patient for patient in hospital_patients
        if any(appointment.patient_id == patient.id for appointment in hospital_appointments)
    ]
    hospital_laboratory_requests = [
        request_item for request_item in TEMP_DATA.get('lab_requests', {}).values()
        if getattr(request_item, 'doctor_id', None) in hospital_doctor_ids
    ]
    hospital_radiology_requests = [
        appointment for appointment in hospital_appointments
        if any(term in str(getattr(appointment, 'reason', '')).lower() for term in ['radiology', 'scan', 'x-ray', 'imaging', 'mri', 'ct'])
    ]
    hospital_ot_schedule = [
        appointment for appointment in hospital_appointments
        if any(term in str(getattr(appointment, 'reason', '')).lower() for term in ['surgery', 'surgical', 'operation', 'ot '])
    ]
    hospital_nursing_staff = [
        staff_member for staff_member in hospital_staff
        if 'nurse' in str(getattr(staff_member, 'role', '')).lower()
    ]
    hospital_departments_with_doctors = {}
    for doc in hospital_doctors:
        dept = doc.department or 'General Medicine'
        if dept not in hospital_departments_with_doctors:
            hospital_departments_with_doctors[dept] = []
        hospital_departments_with_doctors[dept].append(doc)

    hospital_departments = sorted(hospital_departments_with_doctors.keys())
    hospital_insurance_claims = [
        appointment for appointment in hospital_appointments
        if getattr(appointment, 'insurance_provider', None) or getattr(appointment, 'insurance_status', None)
    ]
    hospital_payroll_staff = [
        staff_member for staff_member in hospital_staff
        if getattr(staff_member, 'salary', None) is not None
    ]
    if 'ambulances' not in TEMP_DATA or not TEMP_DATA['ambulances']:
        TEMP_DATA['ambulances'] = {
            "AMB-101": {"id": "AMB-101", "driver": "Rajesh Kumar", "phone": "+91 98765 43210", "type": "Advanced Cardiac Life Support (ACLS)", "status": "Available at Base", "location": "Hospital Bay 1"},
            "AMB-102": {"id": "AMB-102", "driver": "Vikram Singh", "phone": "+91 98765 43211", "type": "Basic Life Support (BLS)", "status": "Available at Base", "location": "North Wing Hub"},
            "AMB-103": {"id": "AMB-103", "driver": "Amit Sharma", "phone": "+91 98765 43212", "type": "Neonatal ICU Ambulance", "status": "En-Route", "location": "City Centre Sector 4"}
        }
    hospital_ambulances = TEMP_DATA['ambulances']
    hospital_patient_vitals = list(TEMP_DATA.get('patient_vitals', {}).values())
    hospital_inventory = TEMP_DATA.get('medicines', [])
    hospital_reports = {
        'appointments': len(hospital_appointments),
        'patients': len(hospital_patients),
        'doctors': len(hospital_doctors),
        'staff': len(hospital_staff),
        'admissions': len(hospital_admissions),
        'emergency_cases': len(hospital_emergency_cases),
        'lab_requests': len(hospital_laboratory_requests),
        'ambulances': len(hospital_ambulances)
    }

    # Prepare serialized representations for Alpine.js initial state
    appointments_serialized = []
    for appt in hospital_appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        pat = TEMP_DATA['patients'].get(appt.patient_id) if getattr(appt, 'patient_id', None) else None
        created_at_val = getattr(appt, 'created_at', None)
        created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(created_at_val, 'strftime') else str(created_at_val or '')
        dept_val = getattr(appt, 'department', None) or (doc.department if doc else "General Medicine")
        is_auto = getattr(appt, 'is_auto_assigned', False)
        staff_by = getattr(appt, 'staff_assigned_by', None)
        appointments_serialized.append({
            "id": appt.id,
            "patient_name": appt.patient_name,
            "patient_phone": getattr(appt, 'patient_phone', None) or (pat.phone if pat else "N/A"),
            "patient_age": str(getattr(appt, 'patient_age', None) or (pat.age if pat and getattr(pat, 'age', None) else "32")),
            "patient_gender": str(getattr(pat, 'gender', 'Not specified') if pat else "Not specified"),
            "patient_id_number": str(getattr(appt, 'patient_id_number', None) or (f"UID-{pat.id}" if pat else f"UID-{appt.id:06d}")),
            "doctor_id": str(appt.doctor_id) if appt.doctor_id else "",
            "doctor_name": f"Dr. {doc.first_name} {doc.last_name}" if doc else "Pending Staff Assignment",
            "doctor_dept": dept_val,
            "is_auto_assigned": is_auto,
            "staff_assigned_by": staff_by,
            "date": appt.appointment_date.strftime('%b %d, %Y') if appt.appointment_date else "N/A",
            "time": appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time else "N/A",
            "reason": appt.reason or "General Consultation",
            "status": appt.status,
            "created_at": created_at_str,
            "is_real": True
        })

    bed_bookings_serialized = []
    for booking in hospital_bed_bookings:
        pat = TEMP_DATA['patients'].get(booking.patient_id) if getattr(booking, 'patient_id', None) else None
        created_at_val = getattr(booking, 'created_at', None)
        created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(created_at_val, 'strftime') else str(created_at_val or '')
        bed_bookings_serialized.append({
            "id": booking.id,
            "patient_name": booking.patient_name,
            "patient_phone": getattr(booking, 'patient_phone', None) or (pat.phone if pat else "N/A"),
            "patient_age": str(getattr(pat, 'age', '45') if pat and getattr(pat, 'age', None) else "45"),
            "patient_gender": str(getattr(pat, 'gender', 'Not specified') if pat else "Not specified"),
            "patient_id_number": str(f"UID-{pat.id}" if pat else f"UID-BED{booking.id:04d}"),
            "bed_type": booking.bed_type,
            "reason": booking.reason or "Emergency Inpatient Admission",
            "status": booking.status,
            "room_number": booking.room_number or "",
            "created_at": created_at_str,
            "is_real": True
        })

    activity_logs_serialized = []
    for log in sorted(activity_logs, key=lambda x: getattr(x, 'created_at', utcnow()), reverse=True)[:20]:
        log_created_at = getattr(log, 'created_at', utcnow())
        activity_logs_serialized.append({
            "id": log.id,
            "timestamp": log_created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(log_created_at, 'strftime') else str(log_created_at),
            "user_name": log.user_name,
            "action": log.action,
            "details": log.details
        })

    # Notifications for this hospital
    hospital_notifications = [
        n for n in TEMP_DATA.get('notifications', {}).values()
        if (str(getattr(n, 'user_id', '')) == str(current_user.id) or getattr(n, 'user_type', None) == 'hospital')
    ]
    def _get_notif_sort_key(n):
        c = getattr(n, 'created_at', None)
        if isinstance(c, datetime):
            return c.isoformat()
        return str(c) if c else ''
    hospital_notifications.sort(key=_get_notif_sort_key, reverse=True)
    unread_notifications = [n for n in hospital_notifications if getattr(n, 'status', 'unread') == 'unread']

    return render_template('hospital_dashboard.html', 
                           appointments_serialized=appointments_serialized,
                           bed_bookings_serialized=bed_bookings_serialized,
                           activity_logs_serialized=activity_logs_serialized,
                           appointments=hospital_appointments, 
                           doctors=hospital_doctors,
                           departments_with_doctors=hospital_departments_with_doctors,
                           hospital_departments=hospital_departments,
                           pending_doctors=pending_doctors,
                           available_unlinked_doctors=available_unlinked_doctors,
                           staff=hospital_staff,
                           patients=hospital_patients,
                           camps=hospital_camps,
                           bed_bookings=hospital_bed_bookings,
                           blood_donors=all_blood_donors,
                           organ_donors=all_organ_donors,
                           blood_stock=blood_stock,
                           chart_labels=chart_labels, 
                           chart_data=chart_data,
                           revenue_labels=chart_labels,
                           revenue_chart_data=revenue_chart_data,
                           dept_labels=dept_labels,
                           dept_data=dept_data,
                           case_status_labels=case_status_labels,
                           case_status_data=case_status_data,
                           bed_distribution_data=bed_distribution_data,
                           blood_group_labels=blood_group_labels,
                           blood_group_data=blood_group_data,
                           bed_occupancy_percent=bed_occupancy_percent,
                           occupied_general_beds=occupied_general,
                           occupied_icu_beds=occupied_icu,
                           activity_logs=activity_logs,
                           total_appointment_revenue=total_appointment_revenue,
                           total_bed_revenue=total_bed_revenue,
                           total_revenue=total_appointment_revenue + total_bed_revenue,
                           opd_appointments=hospital_opd_appointments,
                           admissions=hospital_admissions,
                           emergency_cases=hospital_emergency_cases,
                           telemedicine_appointments=hospital_telemedicine_appointments,
                           emr_records=hospital_emr_records,
                           laboratory_requests=hospital_laboratory_requests,
                           radiology_requests=hospital_radiology_requests,
                           ot_schedule=hospital_ot_schedule,
                           nursing_staff=hospital_nursing_staff,
                           departments=hospital_departments,
                           insurance_claims=hospital_insurance_claims,
                           payroll_staff=hospital_payroll_staff,
                           inventory=hospital_inventory,
                           ambulances=hospital_ambulances,
                           patient_vitals=hospital_patient_vitals,
                           reports=hospital_reports,
                           unread_notifications=unread_notifications,
                           hospital_notifications=hospital_notifications,
                           hospital_types=get_hospital_types(active_only=True),
                           master_facilities=MASTER_FACILITIES_LIST)



@hospital_bp.route('/hospital/notifications/mark-read', methods=['POST'])
@hospital_required
def hospital_mark_notifications_read():
    """Marks all unread notifications for this hospital as read."""
    count = 0
    for n in TEMP_DATA.get('notifications', {}).values():
        if (str(getattr(n, 'user_id', '')) == str(current_user.id) or getattr(n, 'user_type', None) == 'hospital') and getattr(n, 'status', 'unread') == 'unread':
            n.status = 'read'
            count += 1
    if count > 0:
        save_data()
    return jsonify({"success": True, "count": count})



@hospital_bp.route('/hospital/staff/add', methods=['POST'])
@hospital_required
def hospital_add_staff():
    """Allows a hospital to add a new staff member."""
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash('Email and password are required.', 'error')
        return redirect(url_for('hospital_dashboard') + '#staff')
        
    existing = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)
    if existing:
        flash('A staff member with this email already exists.', 'error')
        return redirect(url_for('hospital_dashboard') + '#staff')

    staff_id = f"STF/{datetime.now().year}/{TEMP_DATA['next_ids']['staff']:03d}"
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
    new_staff = Staff(id=staff_id, name=request.form.get('name'), email=email, password=hashed_password, role=request.form.get('role'), phone=request.form.get('phone'), hospital_name=current_user.name)
    TEMP_DATA['staff'][staff_id] = new_staff
    TEMP_DATA['next_ids']['staff'] += 1
    save_data()
    flash(f"Staff member '{new_staff.name}' has been added successfully!", "success")
    return redirect(url_for('hospital_dashboard') + '#staff')



@hospital_bp.route('/hospital/staff/manage/<action>/<path:staff_id>', methods=['POST'])
@hospital_required
def hospital_manage_staff(action, staff_id):
    """Handles blocking/unblocking and deleting staff for the current hospital."""
    staff_id = parse_route_id(staff_id)
    staff = TEMP_DATA['staff'].get(staff_id)

    if not staff or staff.hospital_name != current_user.name:
        flash("Staff member not found or you do not have permission.", "error")
        return redirect(url_for('hospital_dashboard') + '#staff')

    if action == 'toggle_block':
        staff.is_blocked = not getattr(staff, 'is_blocked', False)
        status_text = 'blocked' if staff.is_blocked else 'unblocked'
        flash(f"Staff member has been {status_text}.", "success")
    elif action == 'delete':
        del TEMP_DATA['staff'][staff_id]
        flash("Staff member has been deleted.", "success")
    else:
        flash("Invalid action.", "error")
    
    save_data()
    return redirect(url_for('hospital_dashboard') + '#staff')



@hospital_bp.route('/hospital/dashboard/staff/<path:staff_id>/update', methods=['POST'])
@hospital_required
def update_hospital_staff(staff_id):
    staff_id = parse_route_id(staff_id)
    staff_member = TEMP_DATA['staff'].get(staff_id)
    if not staff_member:
        flash('Staff member not found.', 'error')
        return redirect(url_for('hospital_dashboard') + '#staff')
        
    if staff_member.hospital_name != current_user.name:
        flash('Permission denied.', 'error')
        return redirect(url_for('hospital_dashboard') + '#staff')
        
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    role = request.form.get('role')
    password = request.form.get('password')
    
    if not name or not email or not role:
        flash('Name, Email, and Role are required.', 'error')
        return redirect(url_for('hospital_dashboard') + '#staff')
        
    # Check duplicate email
    dup = next((s for s in TEMP_DATA['staff'].values() if s.email == email and s.id != staff_id), None)
    if dup:
        flash('Email is already in use by another staff member.', 'error')
        return redirect(url_for('hospital_dashboard') + '#staff')
        
    staff_member.name = name
    staff_member.email = email
    staff_member.phone = phone
    staff_member.role = role
    
    if password:
        staff_member.password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        
    if 'profilePicture' in request.files:
        file = request.files['profilePicture']
        if file and file.filename != '':
            if allowed_file(file.filename):
                saved_pic = save_user_profile_image(
                    file,
                    target_size=(500, 500),
                    filename_prefix=f"staff_profile_{str(staff_member.id).replace('/', '_')}"
                )
                if saved_pic:
                    staff_member.profile_picture_url = saved_pic
            else:
                flash('Invalid image file format.', 'error')
                
    save_data()
    flash(f'Staff member {staff_member.name} updated successfully.', 'success')
    return redirect(url_for('hospital_dashboard') + '#staff')



@hospital_bp.route('/hospital/user/action', methods=['POST'])
@hospital_required
def hospital_universal_user_action():
    """Universal handler for block, hide, delete, verify/approve across all hospital entity types."""
    user_type = request.form.get('user_type')
    user_id = request.form.get('user_id')
    action = request.form.get('action')
    tab_redirect = request.form.get('tab_redirect', 'overview')

    if not user_type or not user_id or not action:
        flash("Missing parameters for user action.", "error")
        return redirect(url_for('hospital_dashboard') + f'#{tab_redirect}')

    user_id = parse_route_id(user_id)
    type_map = {
        'doctor': ('doctors', 'Doctor'),
        'patient': ('patients', 'Patient'),
        'staff': ('staff', 'Staff Member'),
        'blood_donor': ('blood_donors', 'Blood Donor'),
        'organ_donor': ('organ_donors', 'Organ Donor')
    }

    if user_type not in type_map:
        flash("Invalid user type specified.", "error")
        return redirect(url_for('hospital_dashboard') + f'#{tab_redirect}')

    collection_key, display_name = type_map[user_type]
    user_obj = TEMP_DATA.get(collection_key, {}).get(user_id)

    if not user_obj:
        user_obj = next((v for k, v in TEMP_DATA.get(collection_key, {}).items() if str(k) == str(user_id) or str(getattr(v, 'id', '')) == str(user_id)), None)

    if not user_obj:
        flash(f"{display_name} not found in hospital database.", "error")
        return redirect(url_for('hospital_dashboard') + f'#{tab_redirect}')

    target_name = getattr(user_obj, 'name', None) or f"{getattr(user_obj, 'first_name', '')} {getattr(user_obj, 'last_name', '')}".strip() or str(user_id)

    if action == 'toggle_block':
        user_obj.is_blocked = not getattr(user_obj, 'is_blocked', False)
        status_str = "blocked" if user_obj.is_blocked else "unblocked"
        flash(f"{display_name} '{target_name}' has been {status_str} successfully.", "success")

    elif action == 'toggle_hide':
        user_obj.is_hidden = not getattr(user_obj, 'is_hidden', False)
        status_str = "hidden from directory" if user_obj.is_hidden else "made visible in directory"
        flash(f"{display_name} '{target_name}' is now {status_str}.", "success")

    elif action in ('toggle_verify', 'approve'):
        if collection_key == 'doctors' or hasattr(user_obj, 'hospital_approval_status'):
            user_obj.hospital_approval_status = 'approved'
            user_obj.hospital_id = current_user.id
            user_obj.hospital_name = current_user.name
            user_obj.hospital_address = current_user.address
            user_obj.is_verified = True
            flash(f"Dr. {target_name} has been approved and fully affiliated with {current_user.name}.", "success")
        elif hasattr(user_obj, 'status'):
            user_obj.status = 'approved'
            if hasattr(user_obj, 'is_verified'):
                user_obj.is_verified = True
            flash(f"{display_name} '{target_name}' status set to 'approved'.", "success")
        elif hasattr(user_obj, 'is_verified'):
            user_obj.is_verified = not getattr(user_obj, 'is_verified', False)
            status_str = "verified" if user_obj.is_verified else "unverified"
            flash(f"{display_name} '{target_name}' verification set to {status_str}.", "success")

    elif action == 'delete':
        actual_key = next((k for k, v in TEMP_DATA[collection_key].items() if v == user_obj or str(k) == str(user_id)), user_id)
        TEMP_DATA[collection_key].pop(actual_key, None)
        
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute(f"DELETE FROM {collection_key} WHERE id = ?", (str(actual_key),))
                conn.commit()
        except Exception as sql_del_err:
            print(f"⚠️ SQL direct delete note: {sql_del_err}")

        flash(f"{display_name} '{target_name}' has been permanently deleted from records.", "success")

    else:
        flash(f"Unrecognized action '{action}'.", "error")

    save_data()
    return redirect(url_for('hospital_dashboard') + f'#{tab_redirect}')




@hospital_bp.route('/hospital/user/details/<user_type>/<path:user_id>', methods=['GET'])
@hospital_required
def hospital_get_user_details(user_type, user_id):
    """Returns rich JSON profile details for the hospital user inspection modal."""
    user_id = parse_route_id(user_id)
    type_map = {
        'doctor': ('doctors', 'Doctor'),
        'patient': ('patients', 'Patient'),
        'staff': ('staff', 'Staff Member'),
        'blood_donor': ('blood_donors', 'Blood Donor'),
        'organ_donor': ('organ_donors', 'Organ Donor')
    }
    if user_type not in type_map:
        return jsonify({'success': False, 'error': 'Invalid user type'}), 400

    col, label = type_map[user_type]
    user = TEMP_DATA.get(col, {}).get(user_id)
    if not user:
        user = next((v for k, v in TEMP_DATA.get(col, {}).items() if str(k) == str(user_id) or str(getattr(v, 'id', '')) == str(user_id)), None)

    if not user:
        return jsonify({'success': False, 'error': f'{label} not found'}), 404

    avatar_url = None
    if user_type == 'doctor':
        avatar_url = url_for('get_doctor_image', doc_id=user.id)
    elif getattr(user, 'profile_picture_url', None):
        avatar_url = url_for('static', filename='uploads/' + user.profile_picture_url)

    name = getattr(user, 'name', None) or f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()

    data = {
        'success': True,
        'user_type': user_type,
        'user_type_label': label,
        'id': str(user.id),
        'name': name,
        'email': getattr(user, 'email', 'N/A'),
        'phone': getattr(user, 'phone', 'N/A'),
        'avatar_url': avatar_url,
        'is_blocked': bool(getattr(user, 'is_blocked', False)),
        'is_hidden': bool(getattr(user, 'is_hidden', False)),
        'is_verified': bool(getattr(user, 'is_verified', False)),
        'status': getattr(user, 'status', getattr(user, 'hospital_approval_status', 'active')),
        'age': getattr(user, 'age', None),
        'gender': getattr(user, 'gender', None),
        'city': getattr(user, 'city', None),
        'address': getattr(user, 'address', None),
        'created_at': str(getattr(user, 'created_at', '')) if getattr(user, 'created_at', None) else None,
        'extra_info': {}
    }

    if user_type == 'doctor':
        data['extra_info'] = {
            'department': getattr(user, 'department', 'General'),
            'specialization': getattr(user, 'specialization', 'General Specialist'),
            'qualification': getattr(user, 'qualification', 'MD/MBBS'),
            'experience': getattr(user, 'experience', 'N/A'),
            'consultation_fee': getattr(user, 'consultation_fee', '500'),
            'license_number': getattr(user, 'license_number', 'N/A'),
            'availability_status': getattr(user, 'availability_status', 'available'),
            'hospital_name': getattr(user, 'hospital_name', current_user.name),
            'profile_detail_url': url_for('doctor_detail', doc_id=user.id)
        }
    elif user_type == 'patient':
        data['extra_info'] = {
            'clinical_record': getattr(user, 'clinical_record', {}),
            'emergency_contact': getattr(user, 'emergency_contact', 'N/A'),
            'id_card_url': url_for('download_patient_id_card')
        }
    elif user_type == 'staff':
        data['extra_info'] = {
            'role': getattr(user, 'role', 'Staff'),
            'hospital_name': getattr(user, 'hospital_name', current_user.name),
            'last_login': str(getattr(user, 'last_login', 'None'))
        }
    elif user_type == 'blood_donor':
        data['extra_info'] = {
            'blood_group': getattr(user, 'blood_group', 'N/A'),
            'last_donation': str(getattr(user, 'last_donation', 'None')),
            'certificate_url': url_for('download_donation_certificate'),
            'id_card_url': url_for('download_blood_donor_id_card')
        }
    elif user_type == 'organ_donor':
        data['extra_info'] = {
            'organs': getattr(user, 'organs', []),
            'blood_group': getattr(user, 'blood_group', 'N/A'),
            'certificate_url': url_for('download_donation_certificate'),
            'id_card_url': url_for('download_organ_donor_id_card')
        }

    return jsonify(data)




@hospital_bp.route('/hospital/opd/status/<int:appointment_id>/<status>', methods=['POST'])
@hospital_required
def hospital_opd_update_status(appointment_id, status):
    appt = TEMP_DATA['appointments'].get(appointment_id)
    if appt:
        appt.status = status
        save_data()
        flash(f"OPD Visit #{appointment_id} updated to {status.capitalize()}.", "success")
    return redirect(url_for('hospital_dashboard', tab='opd'))



@hospital_bp.route('/hospital/ipd/admit', methods=['POST'])
@hospital_required
def hospital_ipd_admit():
    patient_name = request.form.get('patient_name')
    patient_phone = request.form.get('patient_phone', 'N/A')
    bed_type = request.form.get('bed_type', 'General Ward')
    room_number = request.form.get('room_number', 'Ward-A 101')
    reason = request.form.get('reason', 'Inpatient Admission')
    
    if not patient_name:
        flash('Patient name is required for IPD Admission.', 'error')
        return redirect(url_for('hospital_dashboard', tab='ipd'))
        
    booking_id = TEMP_DATA['next_ids'].get('bed_booking', 100)
    TEMP_DATA['next_ids']['bed_booking'] = booking_id + 1
    
    booking = BedBooking(
        id=booking_id,
        hospital_id=current_user.id,
        patient_id=None,
        patient_name=patient_name,
        patient_phone=patient_phone,
        bed_type='ICU' if 'icu' in bed_type.lower() else 'General Ward',
        reason=reason,
        status='approved',
        room_number=room_number,
        created_at=utcnow()
    )
    if 'bed_bookings' not in TEMP_DATA:
        TEMP_DATA['bed_bookings'] = {}
    TEMP_DATA['bed_bookings'][booking_id] = booking
    
    if 'icu' in bed_type.lower():
        current_user.available_icu_beds = max(0, (current_user.available_icu_beds or 1) - 1)
    else:
        current_user.available_beds = max(0, (current_user.available_beds or 1) - 1)
        
    save_data()
    flash(f"Inpatient {patient_name} admitted to {room_number} successfully!", "success")
    return redirect(url_for('hospital_dashboard', tab='ipd'))



@hospital_bp.route('/hospital/ipd/discharge/<int:booking_id>', methods=['POST'])
@hospital_required
def hospital_ipd_discharge(booking_id):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if booking:
        booking.status = 'discharged'
        if booking.bed_type == 'ICU':
            current_user.available_icu_beds = min(current_user.icu_beds or 10, (current_user.available_icu_beds or 0) + 1)
        else:
            current_user.available_beds = min(current_user.total_beds or 50, (current_user.available_beds or 0) + 1)
        save_data()
        flash(f"Patient {booking.patient_name} discharged successfully. Bed released.", "success")
    return redirect(url_for('hospital_dashboard', tab='ipd'))



@hospital_bp.route('/hospital/lab/update/<int:request_id>/<status>', methods=['POST'])
@hospital_required
def hospital_lab_update_status(request_id, status):
    lab_req = TEMP_DATA.get('lab_requests', {}).get(request_id)
    if lab_req:
        lab_req.status = status
        save_data()
        flash(f"Lab Order #{request_id} updated to {status.capitalize()}.", "success")
    return redirect(url_for('hospital_dashboard', tab='laboratory'))



@hospital_bp.route('/hospital/ot/schedule', methods=['POST'])
@hospital_required
def hospital_ot_schedule_surgery():
    patient_name = request.form.get('patient_name')
    procedure_name = request.form.get('procedure_name', 'General Surgery')
    doctor_id = request.form.get('doctor_id')
    ot_room = request.form.get('ot_room', 'OT-1 (Major Suite)')
    sched_date = request.form.get('surgery_date')
    
    if not patient_name:
        flash('Patient name is required for OT scheduling.', 'error')
        return redirect(url_for('hospital_dashboard', tab='ot_management'))
        
    appt_id = TEMP_DATA['next_ids']['appointment']
    TEMP_DATA['next_ids']['appointment'] += 1
    
    try:
        surgery_dt = datetime.strptime(sched_date, '%Y-%m-%d').date() if sched_date else date.today()
    except Exception:
        surgery_dt = date.today()
        
    appt = Appointment(
        id=appt_id,
        doctor_id=doctor_id,
        patient_id=None,
        patient_name=patient_name,
        appointment_date=surgery_dt,
        appointment_time=datetime.now().time(),
        reason=f"[SURGERY / OT: {ot_room}] {procedure_name}",
        status='confirmed',
        created_at=utcnow()
    )
    TEMP_DATA['appointments'][appt_id] = appt
    save_data()
    flash(f"Surgery scheduled in {ot_room} for {patient_name}.", "success")
    return redirect(url_for('hospital_dashboard', tab='ot_management'))



@hospital_bp.route('/hospital/ambulance/dispatch', methods=['POST'])
@hospital_required
def hospital_ambulance_dispatch():
    vehicle_id = request.form.get('vehicle_id', 'AMB-101')
    pickup_address = request.form.get('pickup_address', 'Emergency Location')
    emergency_type = request.form.get('emergency_type', 'Acute Medical Response')
    
    if 'ambulances' not in TEMP_DATA:
        TEMP_DATA['ambulances'] = {}
    
    TEMP_DATA['ambulances'][vehicle_id] = {
        'id': vehicle_id,
        'driver': request.form.get('driver', 'Rajesh Kumar'),
        'phone': request.form.get('driver_phone', '+91 98765 43210'),
        'type': 'Advanced Cardiac Life Support (ACLS)',
        'status': 'En-Route to Patient',
        'location': pickup_address,
        'emergency_type': emergency_type,
        'dispatched_at': utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_data()
    flash(f"🚑 Ambulance {vehicle_id} dispatched immediately to {pickup_address}!", "warning")
    return redirect(url_for('hospital_dashboard', tab='ambulance'))



@hospital_bp.route('/hospital/ambulance/status/<vehicle_id>/<status>', methods=['POST'])
@hospital_required
def hospital_ambulance_set_status(vehicle_id, status):
    if 'ambulances' in TEMP_DATA and vehicle_id in TEMP_DATA['ambulances']:
        TEMP_DATA['ambulances'][vehicle_id]['status'] = status.replace('_', ' ').title()
        save_data()
        flash(f"Ambulance {vehicle_id} status updated to {status.replace('_', ' ').title()}.", "success")
    return redirect(url_for('hospital_dashboard', tab='ambulance'))



@hospital_bp.route('/hospital/insurance/claim', methods=['POST'])
@hospital_required
def hospital_insurance_submit_claim():
    patient_name = request.form.get('patient_name')
    provider = request.form.get('insurance_provider', 'Star Health Insurance')
    policy_no = request.form.get('policy_number', 'POL-2026-9812')
    claim_amount = request.form.get('claim_amount', '45000')
    
    appt_id = TEMP_DATA['next_ids']['appointment']
    TEMP_DATA['next_ids']['appointment'] += 1
    
    appt = Appointment(
        id=appt_id,
        doctor_id=None,
        patient_id=None,
        patient_name=patient_name,
        appointment_date=date.today(),
        appointment_time=datetime.now().time(),
        reason=f"[INSURANCE PRE-AUTH] {provider} (Policy: {policy_no}) - Amount: ₹{claim_amount}",
        status='confirmed',
        created_at=utcnow()
    )
    appt.insurance_provider = provider
    appt.insurance_status = 'Pre-Auth Approved'
    TEMP_DATA['appointments'][appt_id] = appt
    save_data()
    flash(f"Insurance Claim Pre-Auth of ₹{claim_amount} submitted to {provider} for {patient_name}.", "success")
    return redirect(url_for('hospital_dashboard', tab='insurance'))



@hospital_bp.route('/hospital/department/add', methods=['POST'])
@hospital_required
def hospital_department_add():
    dept_name = request.form.get('department_name')
    if dept_name:
        flash(f"Department '{dept_name}' registered successfully for {current_user.name}.", "success")
    return redirect(url_for('hospital_dashboard', tab='departments'))



@hospital_bp.route('/hospital/nursing/vitals', methods=['POST'])
@hospital_required
def hospital_nursing_record_vitals():
    patient_name = request.form.get('patient_name')
    bp = request.form.get('blood_pressure', '120/80')
    pulse = request.form.get('pulse_rate', '74')
    spo2 = request.form.get('spo2', '98%')
    temp = request.form.get('temperature', '98.6°F')
    sugar = request.form.get('blood_sugar', '105 mg/dL')
    
    if 'patient_vitals' not in TEMP_DATA:
        TEMP_DATA['patient_vitals'] = {}
        
    try:
        sys_bp, dia_bp = map(int, bp.split('/'))
    except Exception:
        sys_bp, dia_bp = 120, 80
        
    try:
        hr = int(pulse)
    except Exception:
        hr = 74
        
    try:
        bs = float(str(sugar).replace('mg/dL', '').strip())
    except Exception:
        bs = 105.0

    v_id = max([0] + [int(k) for k in TEMP_DATA.get('patient_vitals', {}).keys() if str(k).isdigit()]) + 1
    vital_obj = PatientVital(
        id=v_id,
        patient_id=None,
        weight=65.0,
        heart_rate=hr,
        blood_sugar=bs,
        systolic_bp=sys_bp,
        diastolic_bp=dia_bp,
        recorded_at=utcnow()
    )
    vital_obj.patient_name = patient_name
    vital_obj.bp = bp
    vital_obj.pulse = pulse
    vital_obj.spo2 = spo2
    vital_obj.temperature = temp
    TEMP_DATA['patient_vitals'][v_id] = vital_obj
    save_data()
    flash(f"Nursing Station: Vitals logged for {patient_name} (BP: {bp}, SpO2: {spo2}, Pulse: {pulse} bpm).", "success")
    return redirect(url_for('hospital_dashboard', tab='nursing'))



@hospital_bp.route('/hospital/billing/create', methods=['POST'])
@hospital_required
def hospital_billing_create_invoice():
    patient_name = request.form.get('patient_name')
    service = request.form.get('service', 'Clinical Consultation & Diagnostics')
    amount = request.form.get('amount', '1500')
    payment_method = request.form.get('payment_method', 'UPI / Card')
    
    flash(f"Invoice generated for {patient_name}: ₹{amount} ({service}) via {payment_method}.", "success")
    return redirect(url_for('hospital_dashboard', tab='billing'))



@hospital_bp.route('/hospital/appointment/create', methods=['POST'])
@hospital_or_staff_role_required('Appointment Management', 'Receptionist')
def hospital_create_appointment():
    patient_name = request.form.get('patient_name')
    doctor_id = request.form.get('doctor_id')
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    patient_phone = request.form.get('patient_phone')
    reason = request.form.get('reason')
    
    if not all([patient_name, doctor_id, date_str, time_str]):
        flash("Required fields missing for appointment creation.", "error")
        return redirect(request.referrer or url_for('staff_dashboard'))
        
    appt_id = TEMP_DATA['next_ids']['appointment']
    new_appointment = Appointment(
        id=appt_id, patient_name=patient_name, doctor_id=doctor_id,
        appointment_date=datetime.strptime(date_str, '%Y-%m-%d').date(),
        appointment_time=datetime.strptime(time_str, '%H:%M').time(),
        patient_phone=patient_phone, reason=reason, status='confirmed'
    )
    TEMP_DATA['appointments'][appt_id] = new_appointment
    TEMP_DATA['next_ids']['appointment'] += 1
    save_data()
    flash(f"Appointment for {patient_name} successfully scheduled.", "success")
    return redirect(request.referrer or url_for('staff_dashboard'))



@hospital_bp.route('/hospital/appointment/cancel/<int:appointment_id>', methods=['POST'])
@hospital_or_staff_role_required('Appointment Management', 'Receptionist')
def hospital_cancel_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    is_hospital = getattr(current_user, 'is_hospital', False)
    hosp = current_user if is_hospital else next((h for h in TEMP_DATA['hospitals'].values() if h.name == current_user.hospital_name), None)
    
    if appointment and hosp and TEMP_DATA['doctors'].get(appointment.doctor_id, {}).hospital_name == hosp.name:
        appointment.status = 'cancelled'
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been cancelled.", "success")
    else:
        flash("Appointment not found or unauthorized.", "error")
    return redirect(request.referrer or url_for('staff_dashboard' if not is_hospital else 'hospital_dashboard'))



@hospital_bp.route('/patient/bed_booking/cancel/<int:booking_id>', methods=['POST'])
@patient_required
def patient_cancel_bed_booking(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if booking and booking.patient_id == current_user.id:
        if booking.status in ['pending', 'awaiting_payment']:
            booking.status = 'cancelled'
            save_data()
            flash('Bed booking request cancelled successfully.', 'success')
        else:
            flash('Cannot cancel a booking that is already processed.', 'error')
    else:
        flash('Booking not found or unauthorized.', 'error')
    return redirect(url_for('patient_dashboard'))



@hospital_bp.route('/patient/bed_booking/edit/<int:booking_id>', methods=['POST'])
@patient_required
def patient_edit_bed_booking(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if booking and booking.patient_id == current_user.id:
        if booking.status in ['pending', 'awaiting_payment']:
            booking.bed_type = request.form.get('bed_type', booking.bed_type)
            booking.reason = request.form.get('reason', booking.reason)
            booking.patient_phone = request.form.get('patient_phone', booking.patient_phone)
            save_data()
            flash('Bed booking updated successfully.', 'success')
        else:
            flash('Cannot edit a booking that is already processed.', 'error')
    else:
        flash('Booking not found or unauthorized.', 'error')
    return redirect(url_for('patient_dashboard'))



@hospital_bp.route('/hospital/live-queue/<hospital_id>')
def hospital_live_queue(hospital_id):
    """Renders dedicated full-screen waiting room TV kiosk for the hospital."""
    hospital = TEMP_DATA.get('hospitals', {}).get(parse_route_id(hospital_id))
    return render_template('hospital_live_queue.html', hospital=hospital)




@hospital_bp.route('/api/queue/call-next', methods=['POST'])
def api_queue_call_next():
    """Doctor or OPD desk calls the next patient token."""
    data = request.get_json() or {}
    token = data.get('token', 'A-105')
    cabin = data.get('cabin', 'Cabin 01')
    doctor = data.get('doctor', 'Dr. Specialist')
    hospital_id = data.get('hospital_id', 1)
    
    queues = TEMP_DATA.setdefault('opd_queues', {})
    hosp_queue = queues.setdefault(hospital_id, {'now_calling': {}, 'history': []})
    
    calling_data = {
        'token': token,
        'cabin': cabin,
        'doctor': doctor,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    hosp_queue['now_calling'] = calling_data
    hosp_queue['history'].insert(0, calling_data)
    
    if socketio:
        try:
            socketio.emit('queue_token_called', calling_data)
        except Exception:
            pass
            
    return jsonify({'success': True, 'calling': calling_data})






def ensure_hospital_sample_data(hospital_id, hospital_name):
    """No-op: Only real database records are loaded."""
    pass


# ==============================================================================
# HOSPITAL & PATHOLOGY DIAGNOSTIC NETWORK INTEGRATION
# ==============================================================================

@hospital_bp.route('/hospital/pathology/connect', methods=['POST'])
@hospital_required
def hospital_pathology_connect():
    """Hospital sends a partnership connection request to a pathology center specifying the doctor."""
    hospital = TEMP_DATA['hospitals'].get(current_user.id)
    if not hospital:
        flash("Hospital profile not found.", "error")
        return redirect(url_for('hospital_dashboard'))

    center_id = request.form.get('center_id')
    doctor_id = request.form.get('doctor_id')
    partnership_type = request.form.get('partnership_type', 'ROUTINE_DIAGNOSTICS')
    notes = request.form.get('notes', 'Hospital pathology diagnostic tie-up agreement')

    if not center_id:
        flash("Please select a diagnostic pathology center.", "error")
        return redirect(url_for('hospital_dashboard', tab='partners'))

    doc_name = None
    if doctor_id:
        doc_obj = TEMP_DATA.get('doctors', {}).get(doctor_id)
        if doc_obj:
            doc_name = f"Dr. {doc_obj.first_name} {doc_obj.last_name}"

    from spherix.services.diagnostic_db import connect_with_hospital
    success, msg = connect_with_hospital(
        center_id=center_id,
        hospital_id=str(hospital.id),
        doctor_id=doctor_id,
        notes=notes,
        partnership_type=partnership_type,
        requested_by='HOSPITAL',
        doctor_name=doc_name,
        hospital_name=hospital.name
    )

    if success:
        flash("Hospital connection request sent. Final activation requires doctor acceptance and pathology confirmation.", "success")
    else:
        flash(f"Connection request failed: {msg}", "error")
    return redirect(url_for('hospital_dashboard', tab='partners'))


@hospital_bp.route('/hospital/pathology/respond-connection', methods=['POST'])
@hospital_required
def hospital_pathology_respond():
    """Hospital confirms or declines a partnership request with a pathology center."""
    conn_id = request.form.get('connection_id')
    action = request.form.get('action', 'accept')
    notes = request.form.get('notes')

    from spherix.services.diagnostic_db import respond_hospital_pathology_connection
    success, msg, data = respond_hospital_pathology_connection(conn_id, actor_role='hospital', action=action, notes=notes)

    if success:
        flash(msg, "success")
    else:
        flash(f"Hospital response failed: {msg}", "error")
    return redirect(url_for('hospital_dashboard', tab='partners'))



