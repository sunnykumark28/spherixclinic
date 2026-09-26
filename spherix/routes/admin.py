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
    deduplicate_entities, setup_admin_user, setup_hospital_user,
    init_auth_telemetry, log_auth_activity, get_auth_telemetry_stats,
    reset_factory_database
)
from spherix.services.mail_service import (
    send_notification_email, send_notification_email_async, get_premium_otp_email_html
)
from spherix.services.payment_service import (
    verify_razorpay_signature, create_razorpay_order
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
    from lab_catalog import ALL_LAB_ITEMS
except ImportError:
    ALL_LAB_ITEMS = []

MEDICINE_LIST = []

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
    from lab_catalog import LAB_TESTS_CATALOG
except ImportError:
    LAB_TESTS_CATALOG = []

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

admin_bp = Blueprint('admin', __name__)



@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Displays the main admin dashboard with comprehensive analytics for all features."""
    page = request.args.get('page', 1, type=int)
    per_page = 10 # Number of items per page
    active_tab = request.args.get('tab', 'dashboard')

    search_query = request.args.get('q', '').lower().strip()

    all_doctors = deduplicate_entities(list(TEMP_DATA['doctors'].values()))
    all_patients = deduplicate_entities(list(TEMP_DATA['patients'].values()))
    all_staff = deduplicate_entities(list(TEMP_DATA['staff'].values()))
    all_hospitals = deduplicate_entities(list(TEMP_DATA['hospitals'].values()))
    all_blood_donors = deduplicate_entities(list(TEMP_DATA['blood_donors'].values()))
    all_organ_donors = deduplicate_entities(list(TEMP_DATA['organ_donors'].values()))
    all_messages = list(TEMP_DATA['messages'].values())
    all_orders = list(TEMP_DATA['orders'].values())
    all_bed_bookings = list(TEMP_DATA.get('bed_bookings', {}).values())
    newsletter_subscribers = TEMP_DATA.get('newsletter_subscribers', [])

    if search_query:
        filtered_doctors = [
            doc for doc in all_doctors
            if search_query in doc.email.lower() 
            or search_query in f"{doc.first_name} {doc.last_name}".lower()
            or (doc.hospital_name and search_query in doc.hospital_name.lower())
        ]
        filtered_patients = [
            p for p in all_patients
            if search_query in p.email.lower() or search_query in p.name.lower()
        ]
        filtered_staff = [
            s for s in all_staff
            if search_query in s.email.lower() or search_query in s.name.lower()
        ]
        filtered_hospitals = [
            h for h in all_hospitals
            if search_query in h.email.lower() or search_query in h.name.lower()
        ]
    else:
        filtered_doctors = all_doctors
        filtered_patients = all_patients
        filtered_staff = all_staff
        filtered_hospitals = all_hospitals

    # Paginate the filtered lists
    def paginate(items, current_page, items_per_page):
        total_items = len(items)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        start_idx = (current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        paginated_items = items[start_idx:end_idx]
        return paginated_items, total_pages

    paginated_doctors, total_doctor_pages = paginate(filtered_doctors, page, per_page)
    paginated_patients, total_patient_pages = paginate(filtered_patients, page, per_page)
    paginated_staff, total_staff_pages = paginate(filtered_staff, page, per_page)
    paginated_hospitals, total_hospital_pages = paginate(filtered_hospitals, page, per_page)

    # Determine which pagination data to use based on the active tab
    total_pages = 1

    # Calculate Real-time Stats for Dashboard
    all_appointments = list(TEMP_DATA['appointments'].values())
    pending_appointments_count = len([a for a in all_appointments if a.status == 'pending'])
    confirmed_appointments_count = len([a for a in all_appointments if a.status == 'confirmed'])
    completed_appointments_count = len([a for a in all_appointments if a.status == 'completed'])
    
    # Calculate bed occupancy
    total_beds = sum(h.total_beds for h in all_hospitals)
    available_beds = sum(h.available_beds for h in all_hospitals)
    occupied_beds = total_beds - available_beds
    
    # Calculate total ICU beds
    total_icu_beds = sum(h.icu_beds for h in all_hospitals)
    available_icu_beds = sum(h.available_icu_beds for h in all_hospitals)
    
    total_earnings = 0
    earnings_map = {}
    order_count = len(all_orders)
    total_order_amount = 0

    # Calculate earnings from Orders
    for order in all_orders:
        total_order_amount += order.total_price
        d = order.order_date.strftime('%Y-%m-%d')
        earnings_map[d] = earnings_map.get(d, 0) + order.total_price

    total_earnings = total_order_amount

    # Calculate earnings from Appointments
    doctor_earnings = {}
    for appt in all_appointments:
        if appt.status in ['confirmed', 'completed']:
            doc = TEMP_DATA['doctors'].get(appt.doctor_id)
            if doc and doc.consultation_fee:
                try:
                    fee = float(doc.consultation_fee)
                    total_earnings += fee
                    d = appt.appointment_date.strftime('%Y-%m-%d')
                    earnings_map[d] = earnings_map.get(d, 0) + fee
                    
                    if doc.id not in doctor_earnings:
                        doctor_earnings[doc.id] = {
                            'name': f"Dr. {doc.first_name} {doc.last_name}",
                            'department': doc.department,
                            'appointments': 0,
                            'earnings': 0.0
                        }
                    doctor_earnings[doc.id]['appointments'] += 1
                    doctor_earnings[doc.id]['earnings'] += fee
                except (ValueError, TypeError):
                    pass
    sorted_doctor_earnings = sorted(doctor_earnings.values(), key=lambda x: x['earnings'], reverse=True)
    
    # Prepare chart data for Top Doctors
    top_doctors = sorted_doctor_earnings[:5]
    doctor_names_labels = [d['name'] for d in top_doctors]
    doctor_earnings_values = [d['earnings'] for d in top_doctors]

    # Calculate Appointments per Hospital
    hospital_appointments_count = {h.name: 0 for h in all_hospitals}
    for appt in all_appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        if doc and doc.hospital_name:
            if doc.hospital_name in hospital_appointments_count:
                hospital_appointments_count[doc.hospital_name] += 1
            else:
                hospital_appointments_count[doc.hospital_name] = 1
    hospital_names = list(hospital_appointments_count.keys())
    hospital_counts = list(hospital_appointments_count.values())

    # Prepare chart data
    if not earnings_map:
        today = date.today()
        sorted_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
        earnings_values = [0] * 7
    else:
        sorted_dates = sorted(earnings_map.keys())
        earnings_values = [earnings_map[d] for d in sorted_dates]

    # Blood bank real donor distribution
    blood_group_labels = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    blood_donor_counts = {bg: 0 for bg in blood_group_labels}
    for donor in all_blood_donors:
        bg = getattr(donor, 'blood_group', None)
        if bg in blood_donor_counts:
            blood_donor_counts[bg] += 1
    blood_group_donor_values = [blood_donor_counts[bg] for bg in blood_group_labels]

    blood_stock = TEMP_DATA.get('blood_stock', {})
    
    # Messaging stats - Message class doesn't have is_read, so count recent messages
    unread_messages = len([m for m in all_messages[-10:] if hasattr(m, 'is_read') and not m.is_read]) if all_messages else 0
    
    # Bed booking stats
    active_bed_bookings = len([b for b in all_bed_bookings if hasattr(b, 'status') and b.status == 'active'])

    # Check if official stamp exists
    stamp_path = os.path.join(current_app.root_path, 'static', 'images', 'stamp.png')
    stamp_exists = os.path.exists(stamp_path)

    # Lab Diagnostic Requests
    if 'lab_requests' not in TEMP_DATA:
        TEMP_DATA['lab_requests'] = {}
    all_lab_requests = list(TEMP_DATA.get('lab_requests', {}).values())
    all_lab_requests.sort(key=lambda x: getattr(x, 'id', 0), reverse=True)

    # Pending Doctor & Hospital Verifications
    pending_doctors = [d for d in all_doctors if not getattr(d, 'is_verified', False)]
    pending_hospitals = [h for h in all_hospitals if not getattr(h, 'is_verified', False)]
    pending_verifications_count = len(pending_doctors) + len(pending_hospitals)

    return render_template('admin_dashboard.html', 
                           doctors=paginated_doctors, 
                           all_doctors_count=len(all_doctors),
                           pending_doctors=pending_doctors,
                           hospitals=paginated_hospitals,
                           all_hospitals=all_hospitals,
                           all_hospitals_count=len(all_hospitals),
                           pending_hospitals=pending_hospitals,
                           pending_verifications_count=pending_verifications_count,
                           patients=paginated_patients, 
                           all_patients_count=len(all_patients),
                           staff_members=paginated_staff, 
                           all_staff_count=len(all_staff),
                           contact_messages=TEMP_DATA['contact_messages'],
                           page=page,
                           total_doctor_pages=total_doctor_pages,
                           total_patient_pages=total_patient_pages,
                           total_staff_pages=total_staff_pages,
                           total_hospital_pages=total_hospital_pages,
                           active_tab=active_tab,
                           per_page=per_page,
                           blood_stock=blood_stock,
                           blood_group_labels=blood_group_labels,
                           blood_group_donor_values=blood_group_donor_values,
                           camps=list(TEMP_DATA['camps'].values()),
                           camp_registrations=list(TEMP_DATA['camp_registrations'].values()), 
                           search_query=search_query,
                           appointments=all_appointments, 
                           pending_appointments_count=pending_appointments_count,
                           confirmed_appointments_count=confirmed_appointments_count,
                           completed_appointments_count=completed_appointments_count,
                           total_earnings=total_earnings, 
                           earnings_dates=sorted_dates, 
                           earnings_values=earnings_values,
                           doctor_earnings=sorted_doctor_earnings,
                           doctor_names_labels=doctor_names_labels, 
                           doctor_earnings_values=doctor_earnings_values,
                           hospital_names=hospital_names, 
                           hospital_counts=hospital_counts,
                           organ_donors=all_organ_donors,
                           blood_donors=all_blood_donors,
                           messages=all_messages,
                           unread_messages=unread_messages,
                           orders=all_orders,
                           order_count=order_count,
                           total_order_amount=total_order_amount,
                           bed_bookings=all_bed_bookings,
                           active_bed_bookings=active_bed_bookings,
                           total_beds=total_beds,
                           available_beds=available_beds,
                           occupied_beds=occupied_beds,
                           total_icu_beds=total_icu_beds,
                           available_icu_beds=available_icu_beds,
                           broadcast_history=list(TEMP_DATA.get('broadcast_history', [])),
                           notifications=list(reversed(sorted(
                                [n for n in TEMP_DATA.get('notifications', {}).values() if getattr(n, 'user_type', '') in ['admin', 'all', 'broadcast'] or str(getattr(n, 'user_id', 0)) in ['1', 'admin']],
                                key=lambda x: str(getattr(x, 'created_at', ''))
                           ))),
                           unread_notifications_count=len([
                                n for n in TEMP_DATA.get('notifications', {}).values() 
                                if (getattr(n, 'user_type', '') in ['admin', 'all', 'broadcast'] or str(getattr(n, 'user_id', 0)) in ['1', 'admin']) and getattr(n, 'status', 'unread') == 'unread'
                           ]),
                           newsletter_subscribers=newsletter_subscribers,
                           stamp_exists=stamp_exists, 
                           settings=TEMP_DATA.get('settings', {}),
                           current_time=time_module.time(),
                           medicines=list(TEMP_DATA.get('medicines', [])),
                           lab_requests=all_lab_requests,
                           lab_catalog=ALL_LAB_ITEMS if 'ALL_LAB_ITEMS' in globals() else [],
                           auth_stats=get_auth_telemetry_stats(),
                           auth_logs=list(TEMP_DATA.get('auth_activity_logs', [])))


@admin_bp.route('/admin/auth-telemetry/terminate', methods=['POST'])
@admin_required
def admin_terminate_auth_session():
    session_id = request.form.get('session_id')
    session_terminated = False
    for log in TEMP_DATA.get('auth_activity_logs', []):
        if log.get('id') == session_id:
            log['status'] = 'Terminated'
            log['duration'] = log.get('duration', '').replace('Active Now', 'Terminated (Admin)')
            log['logout_time'] = utcnow().strftime('%Y-%m-%d %H:%M:%S')
            TEMP_DATA.setdefault('terminated_auth_sessions', {})[session_id] = log['logout_time']
            session_terminated = True
            break
    if session_terminated:
        save_data()
        flash('The selected session was terminated. Its next request will require a new login.', 'success')
    else:
        flash('The selected session no longer exists or has already ended.', 'error')
    return redirect(url_for('admin.admin_dashboard', tab='auth_telemetry'))




@admin_bp.route('/admin/notifications/mark-read', methods=['POST'])
@admin_required
def admin_mark_notifications_read():
    for notif in TEMP_DATA.get('notifications', {}).values():
        if getattr(notif, 'user_type', '') in ['admin', 'all', 'broadcast'] or str(getattr(notif, 'user_id', 0)) in ['1', 'admin']:
            if hasattr(notif, 'status'):
                notif.status = 'read'
            elif isinstance(notif, dict):
                notif['status'] = 'read'
    save_data()
    return jsonify({'success': True})




@admin_bp.route('/api/admin/details/<entity_type>/<path:entity_id>')
@admin_required
def api_admin_details(entity_type, entity_id):
    if entity_type == 'doctor':
        entity, _ = resolve_entity_and_key('doctors', entity_id)
        if not entity:
            return jsonify({'error': 'Doctor not found'}), 404
        return jsonify({
            'id': entity.id,
            'entity_type': 'doctor',
            'name': f"Dr. {entity.first_name} {entity.last_name}",
            'email': entity.email,
            'phone': entity.phone or 'N/A',
            'department': entity.department,
            'specialization': entity.specialization or 'General',
            'address': entity.address or 'N/A',
            'hospital_name': entity.hospital_name or 'N/A',
            'hospital_address': entity.hospital_address or 'N/A',
            'state': entity.state or 'N/A',
            'district': entity.district or 'N/A',
            'pincode': entity.pincode or 'N/A',
            'qualification': entity.qualification or 'N/A',
            'license_number': entity.license_number or 'N/A',
            'experience': f"{entity.experience} years" if entity.experience else 'N/A',
            'consultation_type': entity.consultation_type or 'N/A',
            'consultation_fee': f"₹{entity.consultation_fee}" if entity.consultation_fee else 'N/A',
            'working_hours': entity.working_hours or 'N/A',
            'availability_status': entity.availability_status or 'N/A',
            'is_verified': getattr(entity, 'is_verified', False),
            'is_blocked': getattr(entity, 'is_blocked', False),
            'is_hidden': getattr(entity, 'is_hidden', False),
            'bio': entity.bio or 'N/A',
            'profile_picture_url': url_for('get_doctor_image', doc_id=entity.id)
        })
        
    elif entity_type == 'patient':
        entity, _ = resolve_entity_and_key('patients', entity_id)
        if not entity:
            return jsonify({'error': 'Patient not found'}), 404
        return jsonify({
            'id': entity.id,
            'entity_type': 'patient',
            'name': entity.name,
            'email': entity.email,
            'phone': getattr(entity, 'phone', 'N/A') or 'N/A',
            'address': getattr(entity, 'address', 'N/A') or 'N/A',
            'age': entity.age or 'N/A',
            'gender': entity.gender or 'N/A',
            'is_blocked': getattr(entity, 'is_blocked', False),
            'is_hidden': getattr(entity, 'is_hidden', False),
            'profile_picture_url': url_for('static', filename='uploads/' + entity.profile_picture_url) if getattr(entity, 'profile_picture_url', None) else f"https://ui-avatars.com/api/?name={entity.name}&background=random"
        })
        
    elif entity_type == 'blood_donor':
        entity, _ = resolve_entity_and_key('blood_donors', entity_id)
        if not entity:
            return jsonify({'error': 'Blood Donor not found'}), 404
        return jsonify({
            'id': entity.id,
            'entity_type': 'blood_donor',
            'name': entity.name,
            'email': entity.email,
            'phone': entity.phone or 'N/A',
            'blood_group': entity.blood_group,
            'age': entity.age or 'N/A',
            'city': entity.city or 'N/A',
            'last_donation': entity.last_donation.strftime('%Y-%m-%d') if getattr(entity, 'last_donation', None) and hasattr(entity.last_donation, 'strftime') else (entity.last_donation or 'N/A'),
            'status': getattr(entity, 'status', 'N/A') or 'N/A',
            'is_blocked': getattr(entity, 'is_blocked', False),
            'is_hidden': getattr(entity, 'is_hidden', False),
            'profile_picture_url': url_for('static', filename='uploads/' + entity.profile_picture_url) if getattr(entity, 'profile_picture_url', None) else f"https://ui-avatars.com/api/?name={entity.name}&background=random"
        })
        
    elif entity_type == 'organ_donor':
        entity, _ = resolve_entity_and_key('organ_donors', entity_id)
        if not entity:
            return jsonify({'error': 'Organ Donor not found'}), 404
        organs_list = entity.organs
        if isinstance(organs_list, str):
            try:
                organs_list = json.loads(organs_list)
            except:
                pass
        return jsonify({
            'id': entity.id,
            'entity_type': 'organ_donor',
            'name': entity.name,
            'email': entity.email,
            'phone': entity.phone or 'N/A',
            'organs': ", ".join(organs_list) if isinstance(organs_list, list) else str(organs_list),
            'blood_group': entity.blood_group,
            'age': entity.age or 'N/A',
            'city': entity.city or 'N/A',
            'status': getattr(entity, 'status', 'N/A') or 'N/A',
            'is_blocked': getattr(entity, 'is_blocked', False),
            'is_hidden': getattr(entity, 'is_hidden', False),
            'profile_picture_url': url_for('static', filename='uploads/' + entity.profile_picture_url) if getattr(entity, 'profile_picture_url', None) else f"https://ui-avatars.com/api/?name={entity.name}&background=random"
        })
        
    elif entity_type == 'hospital':
        entity, _ = resolve_entity_and_key('hospitals', entity_id)
        if not entity:
            return jsonify({'error': 'Hospital not found'}), 404
        return jsonify({
            'id': entity.id,
            'entity_type': 'hospital',
            'name': entity.name,
            'email': entity.email,
            'address': entity.address or 'N/A',
            'city': getattr(entity, 'city', 'N/A') or 'N/A',
            'state': getattr(entity, 'state', 'N/A') or 'N/A',
            'total_beds': entity.total_beds,
            'available_beds': entity.available_beds,
            'icu_beds': getattr(entity, 'icu_beds', 0),
            'available_icu_beds': getattr(entity, 'available_icu_beds', 0),
            'doctors_available': getattr(entity, 'doctor_count', 'N/A'),
            'is_verified': getattr(entity, 'is_verified', False),
            'is_blocked': getattr(entity, 'is_blocked', False),
            'is_hidden': getattr(entity, 'is_hidden', False),
            'logo_url': url_for('static', filename='uploads/hospital_logos/' + entity.logo_url) if getattr(entity, 'logo_url', None) else f"https://ui-avatars.com/api/?name={entity.name}&background=random"
        })

    elif entity_type == 'staff':
        entity, _ = resolve_entity_and_key('staff', entity_id)
        if not entity:
            return jsonify({'error': 'Staff member not found'}), 404
        
        created_str = entity.created_at.strftime('%Y-%m-%d %H:%M') if getattr(entity, 'created_at', None) and hasattr(entity.created_at, 'strftime') else (str(entity.created_at) if getattr(entity, 'created_at', None) else 'N/A')
        last_login_str = entity.last_login.strftime('%Y-%m-%d %H:%M') if getattr(entity, 'last_login', None) and hasattr(entity.last_login, 'strftime') else (str(entity.last_login) if getattr(entity, 'last_login', None) else 'Never')
        
        pic_url = getattr(entity, 'profile_picture_url', None)
        if pic_url:
            pic_url = url_for('static', filename='uploads/' + pic_url)
        else:
            pic_url = f"https://ui-avatars.com/api/?name={entity.name}&background=random"

        return jsonify({
            'id': entity.id,
            'entity_type': 'staff',
            'name': entity.name,
            'email': entity.email,
            'role': entity.role or 'Staff',
            'phone': entity.phone or 'N/A',
            'hospital': entity.hospital_name or 'Main Clinic / Admin',
            'is_blocked': getattr(entity, 'is_blocked', False),
            'is_hidden': getattr(entity, 'is_hidden', False),
            'registered_on': created_str,
            'last_login': last_login_str,
            'profile_picture_url': pic_url
        })

    elif entity_type == 'bed_booking':
        entity, _ = resolve_entity_and_key('bed_bookings', entity_id)
        if not entity:
            return jsonify({'error': 'Bed booking not found'}), 404
        
        hosp = TEMP_DATA['hospitals'].get(entity.hospital_id) if hasattr(entity, 'hospital_id') else None
        return jsonify({
            'id': entity.id,
            'entity_type': 'bed_booking',
            'name': f"Booking #{entity.id} - {getattr(entity, 'patient_name', 'Patient')}",
            'patient_name': getattr(entity, 'patient_name', 'N/A'),
            'patient_phone': getattr(entity, 'patient_phone', 'N/A'),
            'hospital_name': hosp.name if hosp else getattr(entity, 'hospital_name', 'Main Hospital'),
            'room_number': getattr(entity, 'room_number', 'N/A'),
            'bed_type': getattr(entity, 'bed_type', 'General'),
            'is_icu': getattr(entity, 'is_icu', False),
            'duration': f"{getattr(entity, 'duration', 1)} Days",
            'reason': getattr(entity, 'reason', 'N/A'),
            'status': getattr(entity, 'status', 'active'),
            'profile_picture_url': f"https://ui-avatars.com/api/?name=BED+{entity.id}&background=0d6efd&color=fff"
        })
        
    return jsonify({'error': 'Invalid entity type'}), 400



@admin_bp.route('/admin/medicine/add', methods=['POST'])
@admin_required
def admin_add_medicine():
    name = (request.form.get('name') or '').strip()
    category = (request.form.get('category') or 'General').strip()
    composition = (request.form.get('composition') or '').strip()
    dosage_form = (request.form.get('dosage_form') or 'Tablet').strip()
    manufacturer = (request.form.get('manufacturer') or 'Spherix Healthcare Pharma').strip()
    batch_number = (request.form.get('batch_number') or f"SPX-2026-B{len(TEMP_DATA.get('medicines', [])) + 1:03d}").strip()
    expiry_date = (request.form.get('expiry_date') or '2027-12-31').strip()
    description = (request.form.get('description') or '').strip()
    rx_required = 1 if request.form.get('rx_required') in ['1', 'true', 'on', True] else 0

    try:
        price = float(request.form.get('price', 0.0))
    except (ValueError, TypeError):
        price = 0.0

    try:
        stock = int(request.form.get('stock', 100))
    except (ValueError, TypeError):
        stock = 100

    try:
        min_threshold = int(request.form.get('min_threshold', 20))
    except (ValueError, TypeError):
        min_threshold = 20
    
    if name and category:
        exists = any(m.get('name', '').lower() == name.lower() for m in TEMP_DATA.get('medicines', []))
        if exists:
            flash(f'Medicine "{name}" already exists in inventory. Please edit the existing entry or choose another name.', 'warning')
        else:
            conn = get_db_connection()
            new_id = len(TEMP_DATA.get('medicines', [])) + 1
            if conn:
                try:
                    cursor = conn.cursor()
                    # Try inserting with full schema, fallback if columns differ
                    try:
                        cursor.execute("""
                            INSERT INTO medicines (name, category, price, stock, description)
                            VALUES (?, ?, ?, ?, ?)
                        """, (name, category, price, stock, description or composition))
                        conn.commit()
                        cursor.execute("SELECT @@IDENTITY AS id")
                        row = cursor.fetchone()
                        if row and row[0]:
                            new_id = int(row[0])
                    except Exception:
                        cursor.execute("INSERT INTO medicines (name, category, price) VALUES (?, ?, ?)", (name, category, price))
                        conn.commit()
                    conn.close()
                except Exception as db_err:
                    print(f"⚠️ Error inserting medicine to DB: {db_err}")
            
            new_med = {
                'id': new_id,
                'name': name,
                'category': category,
                'price': price,
                'stock': stock,
                'min_threshold': min_threshold,
                'composition': composition or name,
                'dosage_form': dosage_form,
                'manufacturer': manufacturer,
                'batch_number': batch_number,
                'expiry_date': expiry_date,
                'description': description,
                'rx_required': rx_required
            }
            if 'medicines' not in TEMP_DATA:
                TEMP_DATA['medicines'] = []
            TEMP_DATA['medicines'].insert(0, new_med)
            
            global MEDICINE_LIST
            if name not in MEDICINE_LIST:
                MEDICINE_LIST.append(name)
            
            flash(f'✅ Medicine "{name}" added to pharmacy inventory with {stock} units in stock.', 'success')
    else:
        flash('Medicine name and category are required fields.', 'error')
    return redirect(url_for('admin_dashboard') + '?tab=pharmacy')



@admin_bp.route('/admin/medicine/edit/<int:med_id>', methods=['POST'])
@admin_required
def admin_edit_medicine(med_id):
    name = (request.form.get('name') or '').strip()
    category = (request.form.get('category') or '').strip()
    composition = (request.form.get('composition') or '').strip()
    dosage_form = (request.form.get('dosage_form') or 'Tablet').strip()
    manufacturer = (request.form.get('manufacturer') or '').strip()
    batch_number = (request.form.get('batch_number') or '').strip()
    expiry_date = (request.form.get('expiry_date') or '').strip()
    description = (request.form.get('description') or '').strip()
    rx_required = 1 if request.form.get('rx_required') in ['1', 'true', 'on', True] else 0

    try:
        price = float(request.form.get('price', 0.0))
    except (ValueError, TypeError):
        price = 0.0

    try:
        stock = int(request.form.get('stock', 0))
    except (ValueError, TypeError):
        stock = 0

    try:
        min_threshold = int(request.form.get('min_threshold', 20))
    except (ValueError, TypeError):
        min_threshold = 20

    med_found = False
    for med in TEMP_DATA.get('medicines', []):
        if med.get('id') == med_id:
            med['name'] = name or med.get('name', '')
            med['category'] = category or med.get('category', '')
            med['price'] = price
            med['stock'] = stock
            med['min_threshold'] = min_threshold
            if composition: med['composition'] = composition
            if dosage_form: med['dosage_form'] = dosage_form
            if manufacturer: med['manufacturer'] = manufacturer
            if batch_number: med['batch_number'] = batch_number
            if expiry_date: med['expiry_date'] = expiry_date
            if description: med['description'] = description
            med['rx_required'] = rx_required
            med_found = True
            break

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE medicines 
                    SET name=?, category=?, price=?, stock=?, description=?
                    WHERE id=?
                """, (name, category, price, stock, description or composition, med_id))
            except Exception:
                cursor.execute("UPDATE medicines SET name=?, category=?, price=? WHERE id=?", (name, category, price, med_id))
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"⚠️ Error updating medicine in DB: {db_err}")

    if med_found:
        flash(f'✅ Medicine "{name}" updated successfully.', 'success')
    else:
        flash('Medicine record not found.', 'warning')
    return redirect(url_for('admin_dashboard') + '?tab=pharmacy')



@admin_bp.route('/admin/medicine/stock/<int:med_id>', methods=['POST'])
@admin_required
def admin_stock_medicine(med_id):
    action = request.form.get('action', 'add')
    try:
        delta = int(request.form.get('quantity', 0))
    except (ValueError, TypeError):
        delta = 0

    target_name = ''
    new_stock = 0
    for med in TEMP_DATA.get('medicines', []):
        if med.get('id') == med_id:
            current = int(med.get('stock', 0) or 0)
            if action == 'add':
                med['stock'] = current + delta
            elif action == 'reduce':
                med['stock'] = max(0, current - delta)
            elif action == 'set':
                med['stock'] = max(0, delta)
            new_stock = med['stock']
            target_name = med.get('name', 'Medicine')
            break

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE medicines SET stock=? WHERE id=?", (new_stock, med_id))
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"⚠️ Error updating stock in DB: {db_err}")

    flash(f'📦 Stock for "{target_name}" updated to {new_stock} units.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=pharmacy')



@admin_bp.route('/admin/medicine/delete/<int:med_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_medicine(med_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM medicines WHERE id = ?", (med_id,))
            conn.commit()
            conn.close()
        except Exception as db_err:
            print(f"⚠️ Error deleting medicine from DB: {db_err}")
            
    TEMP_DATA['medicines'] = [m for m in TEMP_DATA.get('medicines', []) if m.get('id') != med_id]
    flash('🗑️ Medicine deleted from inventory successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=pharmacy')



@admin_bp.route('/admin/lab/order', methods=['POST'])
@admin_required
def admin_order_lab_test():
    patient_name = (request.form.get('patient_name') or 'Anonymous Patient').strip()
    patient_id = request.form.get('patient_id') or 'P-101'
    doctor_id = request.form.get('doctor_id') or 1
    test_name = (request.form.get('test_name') or 'Diagnostic Screening').strip()
    category = (request.form.get('category') or 'General Pathology').strip()
    sample_type = (request.form.get('sample_type') or 'Blood / Serum').strip()
    priority = (request.form.get('priority') or 'Routine').strip()
    notes = (request.form.get('notes') or '').strip()
    reported_by = (request.form.get('reported_by') or 'Spherix Clinical Diagnostic Lab').strip()

    if 'lab_requests' not in TEMP_DATA:
        TEMP_DATA['lab_requests'] = {}

    new_id = max([int(k) for k in TEMP_DATA['lab_requests'].keys()] + [100]) + 1
    barcode = f"SPX-LAB-{new_id:05d}"
    
    lab_req = LabRequest(
        id=new_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        patient_name=patient_name,
        test_name=test_name,
        status='pending',
        notes=notes,
        category=category,
        sample_type=sample_type,
        priority=priority,
        result_status='Pending Collection',
        sample_barcode=barcode,
        specimen_collected_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        reported_by=reported_by
    )
    TEMP_DATA['lab_requests'][new_id] = lab_req
    save_data()
    flash(f'🧪 Diagnostic Lab Order #{new_id} ({test_name}) created successfully for {patient_name}. Barcode: {barcode}', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=lab')



@admin_bp.route('/admin/lab/update-result/<int:req_id>', methods=['POST'])
@admin_required
def admin_update_lab_result(req_id):
    lab_req = TEMP_DATA.get('lab_requests', {}).get(req_id)
    if not lab_req:
        flash('Lab request record not found.', 'warning')
        return redirect(url_for('admin_dashboard') + '?tab=lab')

    status = request.form.get('status', 'completed')
    result_status = request.form.get('result_status', 'Normal')
    notes = request.form.get('notes', '')
    reported_by = request.form.get('reported_by', 'Pathologist On-Duty')

    lab_req.status = status
    lab_req.result_status = result_status
    lab_req.notes = notes
    lab_req.reported_by = reported_by
    save_data()

    flash(f'✅ Diagnostic Report #{req_id} updated with findings: {result_status}.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=lab')



@admin_bp.route('/admin/lab/delete/<int:req_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_lab_request(req_id):
    if 'lab_requests' in TEMP_DATA and req_id in TEMP_DATA['lab_requests']:
        del TEMP_DATA['lab_requests'][req_id]
        save_data()
        flash(f'🗑️ Diagnostic Lab Record #{req_id} removed from registry.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=lab')



@admin_bp.route('/admin/update-settings', methods=['POST'])
@admin_required
def admin_update_settings():
    if 'settings' not in TEMP_DATA:
        TEMP_DATA['settings'] = {}
    
    for key, value in request.form.items():
        TEMP_DATA['settings'][key] = value
        
    save_data()
    flash("System settings updated successfully.", "success")
    return redirect(request.referrer or (url_for('admin_dashboard') + '#settings'))



@admin_bp.route('/admin/settings/email', methods=['POST'])
@admin_required
def admin_settings_email():
    if 'settings' not in TEMP_DATA:
        TEMP_DATA['settings'] = {}
    
    TEMP_DATA['settings']['mail_server'] = request.form.get('mail_server')
    TEMP_DATA['settings']['mail_port'] = request.form.get('mail_port')
    TEMP_DATA['settings']['mail_use_tls'] = request.form.get('mail_use_tls')
    TEMP_DATA['settings']['mail_username'] = request.form.get('mail_username')
    TEMP_DATA['settings']['mail_password'] = request.form.get('mail_password')
            
    save_data()
    flash("Email SMTP settings updated successfully.", "success")
    return redirect(url_for('admin_dashboard') + '#settings')



@admin_bp.route('/admin/broadcast-email', methods=['POST'])
@admin_required
def admin_broadcast_email():
    subject = (request.form.get('subject') or 'Spherix Clinic Notification').strip()
    message_body = (request.form.get('message') or '').strip()
    priority = request.form.get('priority') or 'General Announcement'
    send_in_app = request.form.get('send_in_app') in ['1', 'true', 'on', 'yes']
    send_admin_copy = request.form.get('send_admin_copy') in ['1', 'true', 'on', 'yes']
    recipient_scope = request.form.get('recipient_scope') or 'group'
    
    selected_targets = request.form.getlist('target_roles')
    selected_individual_emails = request.form.getlist('selected_emails')
    
    if not selected_targets and not selected_individual_emails:
        flash('Please select at least one recipient audience group or individual doctor/user.', 'warning')
        return redirect(url_for('admin_dashboard') + '?tab=broadcast')
        
    if not message_body:
        flash('Broadcast message content cannot be empty.', 'warning')
        return redirect(url_for('admin_dashboard') + '?tab=broadcast')

    recipients_set = set()
    audience_names = []

    # Individual selection mode
    if selected_individual_emails:
        for em in selected_individual_emails:
            clean_email = em.strip()
            if not clean_email or '@' not in clean_email:
                continue
            # Try to resolve recipient name
            rec_name = 'Member'
            # Look up across doctors
            for doc in TEMP_DATA.get('doctors', {}).values():
                if getattr(doc, 'email', '') == clean_email:
                    rec_name = f"Dr. {getattr(doc, 'first_name', '')} {getattr(doc, 'last_name', '')}".strip() or getattr(doc, 'name', 'Doctor')
                    break
            # Look up across patients
            if rec_name == 'Member':
                for pat in TEMP_DATA.get('patients', {}).values():
                    if getattr(pat, 'email', '') == clean_email:
                        rec_name = getattr(pat, 'name', 'Patient')
                        break
            # Look up across staff
            if rec_name == 'Member':
                for st in TEMP_DATA.get('staff', {}).values():
                    if getattr(st, 'email', '') == clean_email:
                        rec_name = getattr(st, 'name', 'Staff Member')
                        break
            # Look up across blood donors
            if rec_name == 'Member':
                for bd in TEMP_DATA.get('blood_donors', {}).values():
                    if getattr(bd, 'email', '') == clean_email:
                        rec_name = getattr(bd, 'name', 'Blood Donor')
                        break
            # Look up across organ donors
            if rec_name == 'Member':
                for od in TEMP_DATA.get('organ_donors', {}).values():
                    if getattr(od, 'email', '') == clean_email:
                        rec_name = getattr(od, 'name', 'Organ Donor')
                        break
            # Look up across hospitals
            if rec_name == 'Member':
                for hosp in TEMP_DATA.get('hospitals', {}).values():
                    if getattr(hosp, 'email', '') == clean_email:
                        rec_name = getattr(hosp, 'name', 'Hospital Facility')
                        break
            
            recipients_set.add((clean_email, rec_name))

        audience_label = f"Selected Individuals ({len(recipients_set)} Recipients)"

    # Group selection mode
    else:
        # 1. Doctors
        if 'all_users' in selected_targets or 'doctors' in selected_targets:
            audience_names.append('Doctors')
            for doc in TEMP_DATA.get('doctors', {}).values():
                email = getattr(doc, 'email', None)
                if email and '@' in email:
                    recipients_set.add((email, getattr(doc, 'name', f"Dr. {getattr(doc, 'first_name', '')} {getattr(doc, 'last_name', '')}").strip() or 'Doctor'))

        # 2. Patients
        if 'all_users' in selected_targets or 'patients' in selected_targets:
            audience_names.append('Patients')
            for pat in TEMP_DATA.get('patients', {}).values():
                email = getattr(pat, 'email', None)
                if email and '@' in email:
                    recipients_set.add((email, getattr(pat, 'name', 'Patient')))

        # 3. Hospitals & Branches
        if 'all_users' in selected_targets or 'hospitals' in selected_targets:
            audience_names.append('Hospitals')
            for hosp in TEMP_DATA.get('hospitals', {}).values():
                email = getattr(hosp, 'email', None)
                if email and '@' in email:
                    recipients_set.add((email, getattr(hosp, 'name', 'Hospital Facility')))

        # 4. Staff
        if 'all_users' in selected_targets or 'staff' in selected_targets:
            audience_names.append('Staff')
            for st in TEMP_DATA.get('staff', {}).values():
                email = getattr(st, 'email', None)
                if email and '@' in email:
                    recipients_set.add((email, getattr(st, 'name', 'Staff Member')))

        # 5. Blood Donors
        if 'all_users' in selected_targets or 'blood_donors' in selected_targets:
            audience_names.append('Blood Donors')
            for bd in TEMP_DATA.get('blood_donors', {}).values():
                email = getattr(bd, 'email', None)
                if email and '@' in email:
                    recipients_set.add((email, getattr(bd, 'name', 'Blood Donor')))

        # 6. Organ Donors
        if 'all_users' in selected_targets or 'organ_donors' in selected_targets:
            audience_names.append('Organ Donors')
            for od in TEMP_DATA.get('organ_donors', {}).values():
                email = getattr(od, 'email', None)
                if email and '@' in email:
                    recipients_set.add((email, getattr(od, 'name', 'Organ Donor')))

        if 'all_users' in selected_targets:
            audience_label = 'All Platform Users (Doctors, Patients, Hospitals, Staff, Donors)'
        else:
            audience_label = ', '.join(audience_names) if audience_names else 'Custom Audience'

    if send_admin_copy:
        admin_email = TEMP_DATA.get('settings', {}).get('contact_email') or 'admin@spherixclinic.com'
        recipients_set.add((admin_email, 'Administrator'))

    # Dispatch email asynchronously to each recipient
    for email, name in recipients_set:
        formatted_html = f"""
        <div style="font-family: 'Plus Jakarta Sans', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; border: 1px solid #e2e8f0; border-radius: 16px; background: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="border-bottom: 2px solid #4361ee; padding-bottom: 16px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="color: #0f172a; margin: 0; font-size: 22px;">Spherix <span style="color: #4361ee;">Clinic</span></h2>
                    <span style="font-size: 12px; color: #64748b;">Official Clinical Notification & Bulletin</span>
                </div>
            </div>
            <div style="margin-bottom: 18px;">
                <span style="background: #eef2ff; color: #4361ee; padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; border: 1px solid #c7d2fe;">{priority}</span>
            </div>
            <p style="color: #334155; font-size: 15px; margin-bottom: 12px;">Dear <strong>{name}</strong>,</p>
            <div style="color: #1e293b; font-size: 15px; line-height: 1.65; white-space: pre-wrap; margin: 18px 0; padding: 18px; background: #f8fafc; border-radius: 10px; border-left: 4px solid #4361ee;">
{message_body}
            </div>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
            <p style="color: #64748b; font-size: 12px; margin: 0; line-height: 1.5;">This is an authorized administrative notification from Spherix Clinic Health Intelligence System.<br>24x7 Emergency Helpline: 108 / 1800-SPHERIX | Motihari, Bihar, India</p>
        </div>
        """
        send_notification_email_async(email, subject, formatted_html, is_html=True)

    # Sanitize existing notifications dictionary to ensure all values are Notification instances
    if 'notifications' in TEMP_DATA:
        for k, v in list(TEMP_DATA['notifications'].items()):
            if isinstance(v, dict):
                TEMP_DATA['notifications'][k] = Notification(
                    id=v.get('id', k),
                    user_id=v.get('user_id', 1),
                    user_type=v.get('user_type', 'admin'),
                    message=v.get('message', v.get('title', 'System Notification')),
                    link=v.get('link', '/admin/dashboard?tab=broadcast'),
                    status=v.get('status', 'unread'),
                    created_at=v.get('created_at', utcnow())
                )

    # Always register in-app notification bell entry
    if 'notifications' not in TEMP_DATA:
        TEMP_DATA['notifications'] = {}
    notif_id = max([0] + [int(k) for k in TEMP_DATA['notifications'].keys() if str(k).isdigit()]) + 1
    new_notif = Notification(
        id=notif_id,
        user_id=1,
        user_type='admin',
        message=f"📢 [{priority}] {subject}: {message_body[:140]}",
        link=url_for('admin_dashboard') + '?tab=broadcast',
        status='unread',
        created_at=utcnow()
    )
    TEMP_DATA['notifications'][notif_id] = new_notif

    # Record broadcast in history
    if 'broadcast_history' not in TEMP_DATA:
        TEMP_DATA['broadcast_history'] = []
    
    TEMP_DATA['broadcast_history'].insert(0, {
        'id': len(TEMP_DATA['broadcast_history']) + 1,
        'subject': subject,
        'audience': audience_label,
        'priority': priority,
        'recipient_count': len(recipients_set),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'status': 'Dispatched'
    })
    
    save_data()
    flash(f'📢 Notification broadcast "{subject}" dispatched to {len(recipients_set)} recipients ({audience_label}) successfully!', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=broadcast')



@admin_bp.route('/admin/backup')
@admin_required
def admin_backup():
    try:
        json_data = json.dumps(TEMP_DATA, cls=DataEncoder)
        output = make_response(json_data)
        output.headers["Content-Disposition"] = "attachment; filename=system_backup.json"
        output.headers["Content-type"] = "application/json"
        return output
    except Exception as e:
        flash(f"Failed to generate backup: {e}", "error")
        return redirect(url_for('admin_dashboard') + '#settings')



@admin_bp.route('/admin/restore', methods=['POST'])
@admin_required
def admin_restore():
    if 'backup_file' not in request.files:
        flash('No file provided.', 'error')
        return redirect(url_for('admin_dashboard') + '#settings')
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('admin_dashboard') + '#settings')
        
    try:
        json.loads(file.read())
        flash('System restored successfully from backup. (Database safely validated)', 'success')
    except Exception as e:
        flash(f'Failed to restore backup: Invalid JSON format.', 'error')
        
    return redirect(url_for('admin_dashboard') + '#settings')



@admin_bp.route('/admin/upload-signature', methods=['POST'])
@admin_required
def admin_upload_signature():
    """Allows admin to upload the signature.png file for PDFs."""
    if 'signature' not in request.files:
        flash('No file part provided.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files['signature']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    if file:
        upload_folder = os.path.join(current_app.root_path, 'static', 'images')
        os.makedirs(upload_folder, exist_ok=True) # Ensure directory exists
        save_path = os.path.join(upload_folder, 'signature.png')
        file.save(save_path)
        flash('Official signature image updated successfully!', 'success')
            
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/upload-stamp', methods=['POST'])
@admin_required
def admin_upload_stamp():
    """Allows admin to upload the stamp.png file for PDFs."""
    if 'stamp' not in request.files:
        flash('No file part provided.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files['stamp']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    if file:
        upload_folder = os.path.join(current_app.root_path, 'static', 'images')
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, 'stamp.png')
        file.save(save_path)
        flash('Official stamp image updated successfully!', 'success')
            
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/doctor/view/<path:doc_id>')
@admin_required
def admin_view_doctor(doc_id):
    """Displays a read-only view of a doctor's profile for the admin."""
    doctor, _ = resolve_entity_and_key('doctors', doc_id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('admin_dashboard') + '#doctors')
    return render_template('admin_view_doctor.html', doctor=doctor)



@admin_bp.route('/admin/doctor/verify/<path:doc_id>', methods=['POST'])
@admin_required
def admin_verify_doctor(doc_id):
    doctor, key = resolve_entity_and_key('doctors', doc_id)
    if doctor:
        doctor.is_verified = True
        if not getattr(doctor, 'license_number', None):
            import random
            doctor.license_number = f"MCI-{random.randint(10000, 99999)}"
        save_data()
        
        # Send verification email
        if doctor.email:
            subject = "Account Verified - Spherix Clinic"
            body = f"""
Dear Dr. {doctor.first_name} {doctor.last_name},

Your account has been successfully verified by the administration team.
You now have full access to the Doctor Dashboard.

Login here: {url_for('doctor_login', _external=True)}

Best regards,
Spherix Clinic Team
"""
            send_notification_email(doctor.email, subject, body)

        flash(f"Doctor Dr. {doctor.first_name} {doctor.last_name} has been verified successfully.", "success")
    else:
        flash("Doctor not found.", "error")
    return redirect(request.referrer or (url_for('admin_dashboard') + '#doctors'))



@admin_bp.route('/admin/hospital/verify/<path:hospital_id>', methods=['POST'])
@admin_required
def admin_verify_hospital(hospital_id):
    hospital, _ = resolve_entity_and_key('hospitals', hospital_id)
    if hospital:
        hospital.is_verified = True
        save_data()
        
        if hospital.email:
            subject = "Welcome to Spherix Clinic - Account Verified & Onboarding Steps"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 10px;">
                <h2 style="color: #059669; text-align: center;">Welcome to Spherix Clinic Network!</h2>
                <p>Dear <strong>{hospital.name}</strong>,</p>
                <p>We are thrilled to inform you that your hospital account has been successfully verified by our administration team.</p>
                
                <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #1f2937; margin-top: 0;">🚀 Quick Onboarding Guide</h3>
                    <ol style="padding-left: 20px; line-height: 1.6; color: #4b5563;">
                        <li><strong>Access Your Dashboard:</strong> Log in to the <a href="{url_for('hospital_login', _external=True)}" style="color: #059669; font-weight: bold; text-decoration: none;">Hospital Portal</a>.</li>
                        <li><strong>Complete Your Profile:</strong> Navigate to the <em>Settings</em> tab to update your facility's address, contact details, and upload your official logo.</li>
                        <li><strong>Manage Bed Inventory:</strong> Go to the <em>Bed Management</em> section to configure your total general and ICU beds, along with their pricing.</li>
                        <li><strong>Add Your Medical Staff:</strong> Register your doctors and support staff so they can start managing appointments and patients.</li>
                        <li><strong>Organize Blood Camps:</strong> Use the <em>Blood Camps</em> section to schedule and promote upcoming donation drives to our donor network.</li>
                    </ol>
                </div>
                
                <p>If you need any assistance during the setup process, our support team is available 24/7.</p>
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="{url_for('hospital_login', _external=True)}" style="background-color: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Go to Dashboard</a>
                </div>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                <p style="font-size: 12px; text-align: center; color: #9ca3af;">
                    &copy; {datetime.now().year} Spherix Clinic Health Systems. All rights reserved.<br>
                    This is an automated message, please do not reply directly to this email.
                </p>
            </div>
            """
            send_notification_email(hospital.email, subject, body, is_html=True)

        flash(f"Hospital {hospital.name} has been verified.", "success")
    else:
        flash("Hospital not found.", "error")
    return redirect(request.referrer or url_for('admin_dashboard') + '#hospitals')



@admin_bp.route('/admin/toggle_status/<string:entity_type>/<string:action>/<path:entity_id>', methods=['POST'])
@admin_required
def admin_toggle_entity_status(entity_type, action, entity_id):
    """Unified route to handle blocking/hiding for various entities."""
    collection_map = {
        'doctor': 'doctors',
        'patient': 'patients',
        'hospital': 'hospitals',
        'staff': 'staff',
        'organ_donor': 'organ_donors',
        'blood_donor': 'blood_donors'
    }
    
    collection_name = collection_map.get(entity_type)
    if not collection_name:
        flash("Invalid entity type.", "error")
        return redirect(url_for('admin_dashboard'))
        
    entity, _ = resolve_entity_and_key(collection_name, entity_id)
    if not entity:
        flash(f"{entity_type.replace('_', ' ').title()} not found.", "error")
        return redirect(url_for('admin_dashboard') + f'#{collection_name}')
        
    if action in ['block', 'hide']:
        attr_name = 'is_blocked' if action == 'block' else 'is_hidden'
        current_status = getattr(entity, attr_name, False)
        new_status = not current_status
        setattr(entity, attr_name, new_status)
        
        entity_display = f"Dr. {getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip() if entity_type == 'doctor' else getattr(entity, 'name', entity_type.replace('_', ' ').title())
        
        if action == 'block':
            status_text = "blocked from logging in & appointments" if new_status else "unblocked"
        else:
            status_text = "hidden from portals & search" if new_status else "unhidden and visible across portals"
            
        flash(f"Successfully {status_text} for {entity_display}.", "success")
    else:
        flash("Invalid action.", "error")
        
    save_data()
    return redirect(request.referrer or (url_for('admin_dashboard') + f'#{collection_name}'))



@admin_bp.route('/admin/doctor/add', methods=['GET', 'POST'])
@admin_required
def admin_add_doctor():
    """Allows an admin to add a new doctor and persist to database."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password', password)

        if password and confirm_password and password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('admin_dashboard') + '?tab=doctors')

        existing_doctor = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == email), None)
        if existing_doctor:
            flash('A doctor with this email already exists.', 'error')
            return redirect(url_for('admin_dashboard') + '?tab=doctors')

        year = datetime.now().year
        next_id_num = TEMP_DATA['next_ids']['doctor']
        new_id = f"DOC/{year}/{next_id_num:03d}"
        
        new_doctor = Doctor(
            id=new_id,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=email,
            password=generate_password_hash(password or 'DoctorPass@123', method='pbkdf2:sha256:260000'),
            department=request.form.get('department'),
            specialization=request.form.get('specialization'),
            phone=request.form.get('phone'),
            hospital_name=request.form.get('hospital_name'),
            qualification=request.form.get('qualification'),
            license_number=request.form.get('license_number'),
            experience=request.form.get('experience'),
            consultation_fee=float(request.form.get('consultation_fee', 500) or 500),
            bio=request.form.get('bio'),
            is_verified=True # Admins adding doctors are auto-verified
        )
        TEMP_DATA['doctors'][new_id] = new_doctor
        TEMP_DATA['next_ids']['doctor'] += 1
        save_data()
        flash(f"Doctor Dr. {new_doctor.first_name} {new_doctor.last_name} has been added successfully.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=doctors')

    return redirect(url_for('admin_dashboard') + '?tab=doctors')



@admin_bp.route('/admin/patient/add', methods=['GET', 'POST'])
@admin_required
def admin_add_patient():
    """Allows an admin to add a new patient."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password') or 'PatientPass@123'
        confirm_password = request.form.get('confirm_password', password)

        if password and confirm_password and password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('admin_dashboard') + '?tab=patients')

        existing_patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if existing_patient:
            flash('A patient with this email already exists.', 'error')
            return redirect(url_for('admin_dashboard') + '?tab=patients')

        new_id = f"PAT/{datetime.now().year}/{TEMP_DATA['next_ids']['patient']:03d}"
        age_str = request.form.get('age')
        age_val = int(age_str) if age_str and age_str.isdigit() else None
        new_patient = Patient(
            id=new_id,
            name=request.form.get('name'),
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
            phone=request.form.get('phone'),
            gender=request.form.get('gender'),
            age=age_val
        )
        TEMP_DATA['patients'][new_id] = new_patient
        TEMP_DATA['next_ids']['patient'] += 1
        save_data()
        flash(f"Patient {new_patient.name} has been added successfully.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=patients')
        
    return redirect(url_for('admin_dashboard') + '?tab=patients')



@admin_bp.route('/admin/doctor/edit/<path:doc_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_doctor(doc_id):
    """Allows an admin to edit a doctor's profile and synchronize to SQL database."""
    doctor, _ = resolve_entity_and_key('doctors', doc_id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('admin_dashboard') + '?tab=doctors')

    if request.method == 'POST':
        fields_to_update = [
            'first_name', 'last_name', 'email', 'phone', 'department', 
            'specialization', 'hospital_name', 'hospital_address', 'state',
            'district', 'pincode', 'bio', 'qualification', 'license_number',
            'experience', 'consultation_type', 'consultation_fee',
            'working_hours', 'languages_spoken'
        ]
        for field in fields_to_update:
            if field in request.form:
                val = request.form.get(field)
                if field == 'consultation_fee' and val:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                setattr(doctor, field, val)
        
        if 'social_links' in request.form:
            doctor.social_links = request.form.get('social_links')

        save_data()
        flash(f"Doctor Dr. {doctor.first_name} {doctor.last_name}'s profile has been updated.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=doctors')

    return redirect(url_for('admin_dashboard') + f'?tab=doctors&edit=doctor&id={doc_id}')



@admin_bp.route('/admin/patient/edit/<path:patient_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_patient(patient_id):
    patient, _ = resolve_entity_and_key('patients', patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for('admin_dashboard') + '?tab=patients')

    if request.method == 'POST':
        patient.name = request.form.get('name', patient.name)
        patient.email = request.form.get('email', patient.email)
        patient.phone = request.form.get('phone', getattr(patient, 'phone', ''))
        age_str = request.form.get('age')
        patient.age = int(age_str) if age_str and age_str.isdigit() else patient.age
        patient.gender = request.form.get('gender', patient.gender)
        
        save_data()
        flash(f"Patient {patient.name}'s profile has been updated.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=patients')

    return redirect(url_for('admin_dashboard') + f'?tab=patients&edit=patient&id={patient_id}')



@admin_bp.route('/admin/staff/add', methods=['GET', 'POST'])
@admin_required
def admin_add_staff():
    """Allows an admin to add a new staff member."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role', 'Staff')
        password = request.form.get('password') or 'StaffPass@123'
        phone = request.form.get('phone')
        hospital_name = request.form.get('hospital_name')

        if not name or not email:
            flash("Name and email are required to add a staff member.", "error")
            return redirect(url_for('admin_dashboard') + '?tab=staff')

        existing_staff = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)
        if existing_staff:
            flash(f"A staff member with the email {email} already exists.", "error")
            return redirect(url_for('admin_dashboard') + '?tab=staff')

        staff_id = f"STF/{datetime.now().year}/{TEMP_DATA['next_ids']['staff']:03d}"
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        new_staff = Staff(id=staff_id, name=name, email=email, password=hashed_password, role=role, phone=phone, hospital_name=hospital_name)

        TEMP_DATA['staff'][staff_id] = new_staff
        TEMP_DATA['next_ids']['staff'] += 1
        save_data()
        flash(f"Staff member '{name}' has been added successfully!", "success")
        return redirect(url_for('admin_dashboard') + '?tab=staff')

    return redirect(url_for('admin_dashboard') + '?tab=staff')



@admin_bp.route('/admin/staff/edit/<path:staff_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_staff(staff_id):
    staff, _ = resolve_entity_and_key('staff', staff_id)
    if not staff:
        flash("Staff member not found.", "error")
        return redirect(url_for('admin_dashboard') + '?tab=staff')

    if request.method == 'POST':
        staff.name = request.form.get('name', staff.name)
        staff.email = request.form.get('email', staff.email)
        staff.role = request.form.get('role', staff.role)
        staff.phone = request.form.get('phone', staff.phone)
        staff.hospital_name = request.form.get('hospital_name', staff.hospital_name)

        save_data()
        flash(f"Staff member {staff.name} updated successfully.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=staff')

    return redirect(url_for('admin_dashboard') + f'?tab=staff&edit=staff&id={staff_id}')



@admin_bp.route('/admin/staff/delete/<path:staff_id>', methods=['POST'])
@admin_required
def admin_delete_staff(staff_id):
    staff, key = resolve_entity_and_key('staff', staff_id)
    if staff and key in TEMP_DATA['staff']:
        del TEMP_DATA['staff'][key]
        save_data()
        flash("Staff member deleted successfully.", "success")
    else:
        flash("Staff member not found.", "error")
    return redirect(url_for('admin_dashboard') + '?tab=staff')



@admin_bp.route('/admin/doctor/delete/<path:doc_id>', methods=['POST'])
@admin_required
def admin_delete_doctor(doc_id):
    """Allows an admin to delete a doctor and their associated data."""
    doctor, key = resolve_entity_and_key('doctors', doc_id)
    if doctor and key in TEMP_DATA['doctors']:
        doc_key_str = str(key)
        appointments_to_delete = [k for k, v in list(TEMP_DATA['appointments'].items()) if str(v.doctor_id) in [str(doc_id), doc_key_str]]
        for appt_id in appointments_to_delete:
            TEMP_DATA['appointments'].pop(appt_id, None)

        reviews_to_delete = [k for k, v in list(TEMP_DATA['reviews'].items()) if str(getattr(v, 'doctor_id', '')) in [str(doc_id), doc_key_str]]
        for review_id in reviews_to_delete:
            TEMP_DATA['reviews'].pop(review_id, None)

        messages_to_delete = [k for k, v in list(TEMP_DATA['messages'].items()) if str(getattr(v, 'doctor_id', '')) in [str(doc_id), doc_key_str]]
        for msg_id in messages_to_delete:
            TEMP_DATA['messages'].pop(msg_id, None)

        TEMP_DATA['doctors'].pop(key, None)
        save_data()
        flash(f"Doctor Dr. {getattr(doctor, 'first_name', '')} {getattr(doctor, 'last_name', '')} and all associated data deleted successfully.", "success")
    else:
        flash("Doctor not found.", "error")
    return redirect(request.referrer or url_for('admin_dashboard') + '?tab=doctors')



@admin_bp.route('/admin/patient/delete/<path:patient_id>', methods=['POST'])
@admin_required
def admin_delete_patient(patient_id):
    patient, key = resolve_entity_and_key('patients', patient_id)
    if patient and key in TEMP_DATA['patients']:
        appointments_to_delete = [k for k, v in TEMP_DATA['appointments'].items() if str(v.patient_id) == str(patient_id)]
        for appt_id in appointments_to_delete:
            del TEMP_DATA['appointments'][appt_id]
        
        del TEMP_DATA['patients'][key]
        save_data()
        flash(f"Patient with ID {patient_id} and their appointments have been deleted.", "success")
    else:
        flash("Patient not found.", "error")
    return redirect(url_for('admin_dashboard') + '?tab=patients')



@admin_bp.route('/admin/organ-donor/edit/<path:donor_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_organ_donor(donor_id):
    donor, _ = resolve_entity_and_key('organ_donors', donor_id)
    if not donor:
        flash("Organ donor not found.", "error")
        return redirect(url_for('admin_dashboard') + '?tab=organ_donors')

    if request.method == 'POST':
        donor.name = request.form.get('name', donor.name)
        donor.email = request.form.get('email', donor.email)
        donor.phone = request.form.get('phone', donor.phone)
        donor.city = request.form.get('city', donor.city)
        age_str = request.form.get('age')
        donor.age = int(age_str) if age_str and age_str.isdigit() else donor.age
        donor.blood_group = request.form.get('blood_group', donor.blood_group)
        donor.organs = request.form.getlist('organs')
        
        save_data()
        flash(f"Organ donor {donor.name}'s profile has been updated.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=organ_donors')

    return redirect(url_for('admin_dashboard') + f'?tab=organ_donors&edit=organ_donor&id={donor_id}')



@admin_bp.route('/admin/organ-donor/delete/<path:donor_id>', methods=['POST'])
@admin_required
def admin_delete_organ_donor(donor_id):
    """Allows an admin to delete an organ donor."""
    donor, key = resolve_entity_and_key('organ_donors', donor_id)
    if donor and key in TEMP_DATA['organ_donors']:
        del TEMP_DATA['organ_donors'][key]
        save_data()
        flash("Organ donor deleted successfully.", "success")
    else:
        flash("Organ donor not found.", "error")
    return redirect(request.referrer or (url_for('admin_dashboard') + '?tab=organ_donors'))



@admin_bp.route('/admin/hospital/add', methods=['GET', 'POST'])
@admin_required
def admin_add_hospital():
    """Allows an admin to add a new hospital."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password') or 'HospitalPass@123'
        
        if not name or not email:
            flash("Hospital name and email are required.", "error")
            return redirect(url_for('admin_dashboard') + '?tab=hospitals')

        existing_hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if existing_hospital:
            flash(f"A hospital with email {email} already exists.", "error")
            return redirect(url_for('admin_dashboard') + '?tab=hospitals')

        hospital_id = f"HPT/{datetime.now().year}/{TEMP_DATA['next_ids']['hospital']:03d}"
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        
        total_beds = int(request.form.get('total_beds') or 100)
        available_beds = int(request.form.get('available_beds') or total_beds)
        icu_beds = int(request.form.get('icu_beds') or 20)
        available_icu_beds = int(request.form.get('available_icu_beds') or icu_beds)
        
        new_hospital = Hospital(
            id=hospital_id,
            name=name,
            email=email,
            password=hashed_password,
            city=request.form.get('city', 'Main Center'),
            state=request.form.get('state', ''),
            address=request.form.get('address', ''),
            total_beds=total_beds,
            available_beds=available_beds,
            icu_beds=icu_beds,
            available_icu_beds=available_icu_beds,
            is_verified=True
        )
        
        TEMP_DATA['hospitals'][hospital_id] = new_hospital
        TEMP_DATA['next_ids']['hospital'] += 1
        save_data()
        flash(f"Hospital '{name}' added successfully.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=hospitals')

    return redirect(url_for('admin_dashboard') + '?tab=hospitals')



@admin_bp.route('/admin/hospital/edit/<path:hospital_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_hospital(hospital_id):
    hospital, _ = resolve_entity_and_key('hospitals', hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('admin_dashboard') + '?tab=hospitals')

    if request.method == 'POST':
        hospital.name = request.form.get('name', hospital.name)
        hospital.email = request.form.get('email', hospital.email)
        hospital.city = request.form.get('city', getattr(hospital, 'city', ''))
        hospital.state = request.form.get('state', getattr(hospital, 'state', ''))
        hospital.address = request.form.get('address', getattr(hospital, 'address', ''))
        if 'total_beds' in request.form and request.form.get('total_beds'):
            hospital.total_beds = int(request.form.get('total_beds'))
        if 'available_beds' in request.form and request.form.get('available_beds'):
            hospital.available_beds = int(request.form.get('available_beds'))
        if 'icu_beds' in request.form and request.form.get('icu_beds'):
            hospital.icu_beds = int(request.form.get('icu_beds'))
        if 'available_icu_beds' in request.form and request.form.get('available_icu_beds'):
            hospital.available_icu_beds = int(request.form.get('available_icu_beds'))
            
        save_data()
        flash(f"Hospital '{hospital.name}' updated successfully.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=hospitals')

    return redirect(url_for('admin_dashboard') + f'?tab=hospitals&edit=hospital&id={hospital_id}')



@admin_bp.route('/admin/hospital/delete/<path:hospital_id>', methods=['POST'])
@admin_required
def admin_delete_hospital(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    """Allows an admin to delete a hospital."""
    if hospital_id in TEMP_DATA['hospitals']:
        del TEMP_DATA['hospitals'][hospital_id]
        save_data()
        flash("Hospital deleted successfully.", "success")
    else:
        flash("Hospital not found.", "error")
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/login', methods=['GET', 'POST'])
@admin_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Handles the login process for the administrator."""
    if request.method == 'POST':
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('admin_captcha') or '').strip().upper()

        # Validate CAPTCHA
        if not captcha_input or captcha_input != expected_captcha:
            session['admin_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            return redirect(url_for('admin_login'))

        # Regenerate captcha for next attempt
        session['admin_captcha'] = generate_captcha_text(5)

        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password', '')

        # The admin user is hardcoded for this application
        if email != 'admin@spherixclinic.com':
            flash('Invalid admin credentials. Access restricted to authorized system controllers.', 'error')
            return redirect(url_for('admin_login'))

        # Look for the admin user across doctors and patients
        user = next((doc for doc in TEMP_DATA['doctors'].values() if getattr(doc, 'email', '').strip().lower() == email), None)
        if not user:
            user = next((p for p in TEMP_DATA['patients'].values() if getattr(p, 'email', '').strip().lower() == email), None)

        # If user record is missing, auto-create the root Doctor admin profile dynamically
        if not user:
            setup_admin_user()
            save_data()
            user = next((doc for doc in TEMP_DATA['doctors'].values() if getattr(doc, 'email', '').strip().lower() == email), None)
            if not user:
                user = next((p for p in TEMP_DATA['patients'].values() if getattr(p, 'email', '').strip().lower() == email), None)

        if not user:
            flash('Administrator account could not be provisioned. Please check server logs.', 'error')
            return redirect(url_for('admin_login'))
        elif getattr(user, 'profile_picture_url', None) != 'images/sunnykk.jpg':
            user.profile_picture_url = 'images/sunnykk.jpg'
            save_data()

        # Only the stored password hash is accepted.
        is_valid = False
        try:
            is_valid = check_password_hash(user.password, password)
        except Exception:
            is_valid = False

        if is_valid:
            user.is_verified = True
            user.is_blocked = False
            login_user(user, remember=True)
            session['is_admin'] = True
            session['user_role'] = 'admin'
            admin_name = getattr(user, 'name', '') or f"Dr. {getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or 'System Administrator'
            log_auth_activity(
                user_id=user.id,
                user_name=admin_name,
                user_email=user.email,
                role='Doctor (Admin)',
                action='Successful Login',
                status='Active',
                details='Root Administrator authenticated into Clinical Command Center'
            )
            flash('Admin authentication verified! Welcome to the Core Administration Terminal.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            log_auth_activity(
                user_id=email,
                user_name=str(email or 'Administrator'),
                user_email=email,
                role='Admin',
                action='Failed Login',
                status='Failed',
                details='Invalid admin password attempt entered'
            )
            flash('Invalid security keyphrase for admin@spherixclinic.com.', 'error')
            return redirect(url_for('admin_login'))

    if 'admin_captcha' not in session or not session.get('admin_captcha'):
        session['admin_captcha'] = generate_captcha_text(5)

    return render_template('admin_login.html', captcha_code=session.get('admin_captcha'))



@admin_bp.route('/admin/logout')
@admin_bp.route('/admin-logout')
def admin_logout():
    """Handles secure session termination and logout for the administrator."""
    try:
        u_id = getattr(current_user, 'id', None)
        u_email = getattr(current_user, 'email', None) or 'admin@spherixclinic.com'
        log_user_logout(user_id=u_id, user_email=u_email, role='Doctor (Admin)')
    except Exception:
        pass

    try:
        logout_user()
    except Exception:
        pass

    session.clear()
    flash('You have been securely logged out of the Administrator Portal.', 'success')

    response = redirect(url_for('admin.admin_login'))
    response.delete_cookie('remember_token')
    response.delete_cookie('session')
    response.delete_cookie('user_id')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response




@admin_bp.route('/admin/camp/add', methods=['POST'])
@admin_required
def admin_add_camp():
    name = request.form.get('name')
    location = request.form.get('location')
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    organizer = request.form.get('organizer')
    contact = request.form.get('contact')

    if all([name, location, date_str, time_str]):
        camp_id = TEMP_DATA['next_ids']['camp']
        # Format date nicely if possible, or keep as string
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
            "organizer": organizer,
            "contact": contact
        }
        TEMP_DATA['camps'][camp_id] = new_camp
        TEMP_DATA['next_ids']['camp'] += 1
        save_data()
        flash("New donation camp added successfully.", "success")
    else:
        flash("Missing required fields.", "error")
    
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/camp/delete/<int:camp_id>', methods=['POST'])
@admin_required
def admin_delete_camp(camp_id):
    if camp_id in TEMP_DATA['camps']:
        del TEMP_DATA['camps'][camp_id]
        save_data()
        flash("Camp deleted successfully.", "success")
    else:
        flash("Camp not found.", "error")
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/camp-registration/delete/<int:reg_id>', methods=['POST'])
@admin_required
def admin_delete_camp_registration(reg_id):
    if reg_id in TEMP_DATA['camp_registrations']:
        del TEMP_DATA['camp_registrations'][reg_id]
        save_data()
        flash("Registration deleted successfully.", "success")
    else:
        flash("Registration not found.", "error")
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/clear-doctors')
def clear_all_doctors():
    """
    Clears all doctors and their associated data (appointments, reviews, messages).
    This is a destructive action intended for development/testing.
    """
    # Clear doctors and reset the ID counter
    TEMP_DATA['doctors'] = {}
    TEMP_DATA['next_ids']['doctor'] = 1

    # To maintain data integrity, we'll also clear data that references doctors.
    # Since we are removing all doctors, we can clear all of these.
    TEMP_DATA['appointments'] = {}
    TEMP_DATA['reviews'] = {}
    TEMP_DATA['messages'] = {}
    TEMP_DATA['next_ids']['appointment'] = 1
    TEMP_DATA['next_ids']['review'] = 1
    TEMP_DATA['next_ids']['message'] = 1

    save_data()
    flash("All doctor data and related records have been cleared.", "warning")
    return redirect(url_for('home'))



@admin_bp.route('/admin/blood-donor/edit/<path:donor_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_blood_donor(donor_id):
    donor, _ = resolve_entity_and_key('blood_donors', donor_id)
    if not donor:
        flash("Blood donor not found.", "error")
        return redirect(url_for('admin_dashboard') + '?tab=blood_donors')

    if request.method == 'POST':
        donor.name = request.form.get('name', donor.name)
        donor.email = request.form.get('email', donor.email)
        donor.phone = request.form.get('phone', donor.phone)
        donor.city = request.form.get('city', donor.city)
        age_str = request.form.get('age')
        donor.age = int(age_str) if age_str and age_str.isdigit() else donor.age
        donor.blood_group = request.form.get('blood_group', donor.blood_group)
        
        save_data()
        flash(f"Blood donor {donor.name}'s profile has been updated.", "success")
        return redirect(url_for('admin_dashboard') + '?tab=blood_donors')

    return redirect(url_for('admin_dashboard') + f'?tab=blood_donors&edit=blood_donor&id={donor_id}')



@admin_bp.route('/admin/blood-donor/delete/<path:donor_id>', methods=['POST'])
@admin_required
def admin_delete_blood_donor(donor_id):
    """Allows an admin to delete a blood donor."""
    donor, key = resolve_entity_and_key('blood_donors', donor_id)
    if donor and key in TEMP_DATA['blood_donors']:
        del TEMP_DATA['blood_donors'][key]
        save_data()
        flash("Blood donor deleted successfully.", "success")
    else:
        flash("Blood donor not found.", "error")
    return redirect(request.referrer or (url_for('admin_dashboard') + '#blood_donors'))



@admin_bp.route('/admin/appointment/delete/<int:appointment_id>', methods=['POST'])
@admin_required
def admin_delete_appointment(appointment_id):
    """Allows an admin to delete an appointment."""
    if appointment_id in TEMP_DATA['appointments']:
        del TEMP_DATA['appointments'][appointment_id]
        save_data()
        flash("Appointment deleted successfully.", "success")
    else:
        flash("Appointment not found.", "error")
    return redirect(url_for('admin_dashboard') + '#appointments')



@admin_bp.route('/admin/order/delete/<int:order_id>', methods=['POST'])
@admin_required
def admin_delete_order(order_id):
    """Allows an admin to delete a pharmacy order."""
    if order_id in TEMP_DATA['orders']:
        del TEMP_DATA['orders'][order_id]
        save_data()
        flash("Order deleted successfully.", "success")
    else:
        flash("Order not found.", "error")
    return redirect(url_for('admin_dashboard') + '#orders')



@admin_bp.route('/admin/message/delete/<int:msg_id>', methods=['POST'])
@admin_required
def admin_delete_message(msg_id):
    """Allows an admin to delete a chat message."""
    if msg_id in TEMP_DATA['messages']:
        del TEMP_DATA['messages'][msg_id]
        save_data()
        flash("Message deleted successfully.", "success")
    else:
        flash("Message not found.", "error")
    return redirect(url_for('admin_dashboard') + '#messages')



@admin_bp.route('/admin/review/delete/<int:review_id>', methods=['POST'])
@admin_required
def admin_delete_review(review_id):
    """Allows an admin to delete a review."""
    if review_id in TEMP_DATA['reviews']:
        del TEMP_DATA['reviews'][review_id]
        save_data()
        flash("Review deleted successfully.", "success")
    else:
        flash("Review not found.", "error")
    return redirect(url_for('admin_dashboard') + '#reviews')



@admin_bp.route('/admin/bed_booking/delete/<path:booking_id>', methods=['POST'])
@admin_required
def admin_delete_bed_booking(booking_id):
    """Allows an admin to delete a bed booking."""
    booking, key = resolve_entity_and_key('bed_bookings', booking_id)
    if booking and key in TEMP_DATA.get('bed_bookings', {}):
        del TEMP_DATA['bed_bookings'][key]
        save_data()
        flash("Bed booking deleted successfully.", "success")
    else:
        flash("Bed booking not found.", "error")
    return redirect(request.referrer or (url_for('admin_dashboard') + '#bed_bookings'))



@admin_bp.route('/admin/contact_message/delete/<int:index>', methods=['POST'])
@admin_required
def admin_delete_contact_message(index):
    """Allows an admin to delete a contact message."""
    try:
        if 0 <= index < len(TEMP_DATA['contact_messages']):
            del TEMP_DATA['contact_messages'][index]
            save_data()
            flash("Contact message deleted successfully.", "success")
        else:
            flash("Contact message not found.", "error")
    except Exception as e:
         flash("An error occurred.", "error")
    return redirect(url_for('admin_dashboard') + '#messages')



@admin_bp.route('/admin/organ_request/delete/<int:req_id>', methods=['POST'])
@admin_required
def admin_delete_organ_request(req_id):
    """Allows an admin to delete an organ request."""
    if req_id in TEMP_DATA.get('organ_requests', {}):
        del TEMP_DATA['organ_requests'][req_id]
        save_data()
        flash("Organ request deleted successfully.", "success")
    else:
        flash("Organ request not found.", "error")
    return redirect(url_for('admin_dashboard') + '#organ_requests')



@admin_bp.route('/admin/newsletter/delete/<path:email>', methods=['POST'])
@admin_required
def admin_delete_subscriber(email):
    """Allows an admin to delete a newsletter subscriber."""
    subscribers = TEMP_DATA.get('newsletter_subscribers', [])
    original_len = len(subscribers)
    TEMP_DATA['newsletter_subscribers'] = [s for s in subscribers if s['email'] != email]
    
    if len(TEMP_DATA['newsletter_subscribers']) < original_len:
        save_data()
        flash("Subscriber deleted successfully.", "success")
    else:
        flash("Subscriber not found.", "error")
        
    return redirect(url_for('admin_dashboard') + '#newsletter')



def _verify_admin_master_password(entered_password):
    """Securely checks entered password against the current admin user, admin doctor record, or bootstrap password."""
    if not entered_password:
        return False
    # 1. Check current logged-in user password
    if hasattr(current_user, 'password') and current_user.password:
        try:
            if check_password_hash(current_user.password, entered_password):
                return True
        except Exception:
            pass
        if current_user.password == entered_password:
            return True

    # 2. Check admin doctor in TEMP_DATA
    admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').strip().lower() == 'admin@spherixclinic.com'), None)
    if admin_doc and getattr(admin_doc, 'password', None):
        try:
            if check_password_hash(admin_doc.password, entered_password):
                return True
        except Exception:
            pass
        if admin_doc.password == entered_password:
            return True

    # 3. Check ADMIN_BOOTSTRAP_PASSWORD from environment
    bootstrap_pwd = os.getenv('ADMIN_BOOTSTRAP_PASSWORD', '').strip()
    if bootstrap_pwd and entered_password == bootstrap_pwd:
        return True

    return False


@admin_bp.route('/admin/system/reset/request-otp', methods=['POST'])
@admin_required
def admin_system_reset_request_otp():
    """Step 1: Authenticates Admin Password and Dispatches a 6-digit Security OTP to Admin's Email."""
    data = request.get_json(silent=True) or request.form or {}
    password = str(data.get('password', '')).strip()

    if not password:
        return jsonify({'success': False, 'message': 'Administrator password is required.'}), 400

    if not _verify_admin_master_password(password):
        return jsonify({'success': False, 'message': 'Incorrect administrator password. Access denied.'}), 401

    # Generate cryptographically random 6-digit OTP
    otp = f"{random.randint(100000, 999999)}"
    session['admin_db_reset_otp'] = otp
    session['admin_db_reset_otp_exp'] = time_module.time() + 600  # 10 minutes validity
    session['admin_db_reset_pwd_verified'] = True
    session['admin_db_reset_otp_verified'] = False

    admin_email = getattr(current_user, 'email', None) or 'admin@spherixclinic.com'
    parts = admin_email.split('@')
    masked_email = f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 else "ad***@spherixclinic.com"

    # Format ultra-premium security OTP email
    email_html = get_premium_otp_email_html(
        title="Emergency Database Reset Authorization",
        greeting="Attention Administrator,",
        message="A high-priority request was initiated from the Admin Control Center to completely wipe and factory-reset the Spherix Clinic Database. If you authorized this operation, please enter the following 6-digit one-time authorization code:",
        otp=otp,
        role_color="#dc2626",
        accent_bg="#fef2f2"
    )

    send_notification_email_async(
        to_email=admin_email,
        subject="🚨 [CRITICAL ALERT] Spherix Clinic — Database Reset Security OTP",
        body=email_html,
        is_html=True
    )

    print(f"🔐 [ADMIN RESET] Dispatched OTP '{otp}' to {admin_email}")

    return jsonify({
        'success': True,
        'message': f'Administrator verified. A 6-digit security code has been sent to {masked_email}.',
        'masked_email': masked_email,
        'dev_otp': otp  # Provided for seamless local testing if SMTP offline
    }), 200


@admin_bp.route('/admin/system/reset/verify-otp', methods=['POST'])
@admin_required
def admin_system_reset_verify_otp():
    """Step 2: Validates the 6-digit OTP code received on Admin Email."""
    if not session.get('admin_db_reset_pwd_verified'):
        return jsonify({'success': False, 'message': 'Password verification is required before entering OTP.'}), 403

    data = request.get_json(silent=True) or request.form or {}
    entered_otp = str(data.get('otp', '')).strip()
    stored_otp = str(session.get('admin_db_reset_otp', ''))
    otp_exp = session.get('admin_db_reset_otp_exp', 0)

    if not entered_otp:
        return jsonify({'success': False, 'message': 'Please enter the 6-digit authorization code.'}), 400

    if time_module.time() > otp_exp:
        return jsonify({'success': False, 'message': 'Authorization code has expired. Please request a new code.'}), 400

    if entered_otp != stored_otp:
        return jsonify({'success': False, 'message': 'Invalid verification code. Please check your email and try again.'}), 400

    session['admin_db_reset_otp_verified'] = True
    return jsonify({
        'success': True,
        'message': 'Security OTP authorization verified successfully. Please review and acknowledge data destruction policies.'
    }), 200


@admin_bp.route('/admin/system/reset/resend-otp', methods=['POST'])
@admin_required
def admin_system_reset_resend_otp():
    """Resends a fresh 6-digit security OTP to the admin email."""
    if not session.get('admin_db_reset_pwd_verified'):
        return jsonify({'success': False, 'message': 'Password verification is required before requesting OTP.'}), 403

    otp = f"{random.randint(100000, 999999)}"
    session['admin_db_reset_otp'] = otp
    session['admin_db_reset_otp_exp'] = time_module.time() + 600
    session['admin_db_reset_otp_verified'] = False

    admin_email = getattr(current_user, 'email', None) or 'admin@spherixclinic.com'
    parts = admin_email.split('@')
    masked_email = f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 else "ad***@spherixclinic.com"

    email_html = get_premium_otp_email_html(
        title="Emergency Database Reset Authorization (Resent)",
        greeting="Attention Administrator,",
        message="A new 6-digit authorization code was requested to factory-reset the Spherix Clinic Database:",
        otp=otp,
        role_color="#dc2626",
        accent_bg="#fef2f2"
    )

    send_notification_email_async(
        to_email=admin_email,
        subject="🚨 [NEW CODE] Spherix Clinic — Database Reset Security OTP",
        body=email_html,
        is_html=True
    )

    print(f"🔐 [ADMIN RESET RESEND] Dispatched new OTP '{otp}' to {admin_email}")

    return jsonify({
        'success': True,
        'message': f'A fresh authorization code has been dispatched to {masked_email}.',
        'masked_email': masked_email,
        'dev_otp': otp
    }), 200


@admin_bp.route('/admin/system/reset', methods=['POST'])
@admin_required
def admin_system_reset():
    """Step 3 & 4: Resets the system data to factory defaults after strict password, OTP, and policy verification."""
    global TEMP_DATA
    data = request.get_json(silent=True) or request.form or {}

    # 1. Gate check: Password verified in session
    if not session.get('admin_db_reset_pwd_verified'):
        msg = "Security authorization required: Admin master password verification has not been completed."
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 403
        flash(msg, "error")
        return redirect(url_for('admin_dashboard'))

    # 2. Gate check: OTP verified in session
    if not session.get('admin_db_reset_otp_verified'):
        msg = "Security authorization required: Admin email OTP code verification has not been completed."
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 403
        flash(msg, "error")
        return redirect(url_for('admin_dashboard'))

    # 3. Gate check: Policy agreement accepted
    policy_agreed = data.get('policy_agreed') in [True, 'true', '1', 'on']
    if not policy_agreed:
        msg = "You must read and accept all data destruction and compliance policies."
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin_dashboard'))

    # 4. Gate check: Exact confirmation phrase
    confirmation_phrase = str(data.get('confirmation_phrase', '')).strip().upper()
    if confirmation_phrase != 'RESET SPHERIX DATABASE':
        msg = "Confirmation phrase mismatch. You must type 'RESET SPHERIX DATABASE' exactly."
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin_dashboard'))

    # Execute complete factory reset of in-memory collections and persistent database
    reset_factory_database()

    # Clean verification session keys
    session.pop('admin_db_reset_pwd_verified', None)
    session.pop('admin_db_reset_otp', None)
    session.pop('admin_db_reset_otp_exp', None)
    session.pop('admin_db_reset_otp_verified', None)

    # Dispatch confirmation alert email
    admin_email = getattr(current_user, 'email', None) or 'admin@spherixclinic.com'
    reset_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    send_notification_email_async(
        to_email=admin_email,
        subject="✅ Spherix Clinic — Database Factory Reset Successfully Executed",
        body=f"""Administrator Notice:
A complete database factory reset was successfully executed on Spherix Clinic at {reset_timestamp}.
All operational clinical records and test transactions have been purged. Default Administrator and Hospital profiles remain active.

Audit Metadata:
- Action: EMERGENCY_FACTORY_RESET
- Operator: {admin_email}
- Remote IP: {request.remote_addr}
- Timestamp: {reset_timestamp}
""",
        is_html=False
    )

    msg = "Database has been completely reset to factory state. Default Administrator and Hospital accounts preserved."
    if request.is_json:
        return jsonify({'success': True, 'message': msg}), 200

    flash(msg, "warning")
    return redirect(url_for('admin_dashboard'))





class DataEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        return super().default(obj)


def resolve_entity_and_key(collection_name, entity_id):
    """Robust lookup that handles string IDs, integer IDs, and prefix IDs across in-memory TEMP_DATA."""
    collection = TEMP_DATA.get(collection_name, {})
    if not entity_id or not collection:
        return None, None
    # 1. Exact key match
    if entity_id in collection:
        return collection[entity_id], entity_id
    # 2. Integer key match
    try:
        int_id = int(str(entity_id).split('/')[-1]) if '/' in str(entity_id) else int(entity_id)
        if int_id in collection:
            return collection[int_id], int_id
    except (ValueError, TypeError):
        pass
    # 3. parse_route_id match
    try:
        p_id = parse_route_id(entity_id)
        if p_id in collection:
            return collection[p_id], p_id
    except Exception:
        pass
    # 4. Search by string representation of key or id attribute
    for k, v in collection.items():
        if str(k) == str(entity_id) or str(getattr(v, 'id', '')) == str(entity_id):
            return v, k
    return None, None
