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
from math import ceil
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
    Appointment, PatientVital, LabRequest, OrganRequest, BedBooking, PatientMedicalRecord,
    Order, Review, Feedback, Message, ActivityLog, Referral, Notification
)
from spherix.services.database import (
    TEMP_DATA, get_db_connection, save_data, load_data,
    sync_data_to_sql, load_data_from_sql, create_notification, get_temp_data_item,
    deduplicate_entities
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
    SYMPTOM_CACHE, ACTIVE_SYMPTOM_REPORTS, LAST_API_CALL_TIME,
    _is_groq_configured, _extract_groq_text_response,
    GROQ_API_BASE, GROQ_API_MODEL, GROQ_API_KEY
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

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/doctors')
def doctors_list():
    # This route fetches doctors from the database with global and domestic filtering
    all_db_doctors = deduplicate_entities([d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)])
    q = request.args.get('q', '').lower().strip()
    dept = request.args.get('dept', '').strip()
    country_filter = request.args.get('country', '').strip()
    scope = request.args.get('scope', '').strip() # 'all', 'domestic', 'international'
    tele_only = request.args.get('telemedicine', '').strip()
    
    filtered_doctors = all_db_doctors
    if q:
        filtered_doctors = [
            d for d in filtered_doctors 
            if q in f"{d.first_name} {d.last_name}".lower() 
            or (d.department and q in d.department.lower())
            or (d.specialization and q in d.specialization.lower())
            or (d.hospital_name and q in d.hospital_name.lower())
            or (getattr(d, 'country', None) and q in d.country.lower())
        ]
    if dept:
        filtered_doctors = [
            d for d in filtered_doctors
            if d.department and d.department.lower() == dept.lower()
        ]
    if country_filter and country_filter.lower() != 'all':
        filtered_doctors = [
            d for d in filtered_doctors
            if getattr(d, 'country', '').lower() == country_filter.lower()
        ]
    if scope == 'domestic':
        filtered_doctors = [d for d in filtered_doctors if getattr(d, 'country', 'India') in ['India', 'IN']]
    elif scope == 'international':
        filtered_doctors = [d for d in filtered_doctors if getattr(d, 'country', 'India') not in ['India', 'IN']]
    if tele_only == '1' or tele_only.lower() == 'true':
        filtered_doctors = [d for d in filtered_doctors if getattr(d, 'is_international', False) or 'video' in str(getattr(d, 'consultation_type', '')).lower() or 'telemedicine' in str(getattr(d, 'consultation_type', '')).lower()]
        
    # Get unique departments present in our doctors database
    available_depts = sorted(list(set(d.department for d in all_db_doctors if d.department)))
    available_countries = sorted(list(set(getattr(d, 'country', 'India') for d in all_db_doctors if getattr(d, 'country', None))))
    
    # FontAwesome icons mapped for standard specialties to enhance aesthetics
    dept_icons = {
        'Cardiology': 'fa-heart-pulse',
        'Gynecology': 'fa-baby-carriage',
        'Neurology': 'fa-brain',
        'Orthopedics': 'fa-bone',
        'Pediatrics': 'fa-baby',
        'Dermatology': 'fa-hand-dots',
        'General Medicine': 'fa-stethoscope',
        'Oncology': 'fa-ribbon',
        'Ophthalmology': 'fa-eye',
        'ENT': 'fa-ear-listen',
        'Dentistry': 'fa-tooth',
        'Psychiatry': 'fa-head-side-virus',
        'Urology': 'fa-kidney',
        'Gastroenterology': 'fa-stethoscope',
        'Pulmonology': 'fa-lungs',
        'Nephrology': 'fa-kidney',
        'Endocrinology': 'fa-vial',
        'Rheumatology': 'fa-hand-holding-medical'
    }
    
    display_depts = []
    # 1. Add departments with doctors
    for d_name in available_depts:
        icon = dept_icons.get(d_name, 'fa-user-md')
        display_depts.append({
            'name': d_name,
            'icon': icon,
            'count': sum(1 for d in all_db_doctors if d.department == d_name)
        })
    # 2. Add other popular specialties (with count 0) to make the list look full and professional
    common_depts = [
        'Cardiology', 'Gynecology', 'Neurology', 'Orthopedics', 'Pediatrics', 
        'Dermatology', 'General Medicine', 'Oncology', 'Ophthalmology', 
        'ENT', 'Dentistry', 'Psychiatry', 'Urology', 'Gastroenterology', 
        'Pulmonology', 'Nephrology', 'Endocrinology', 'Rheumatology'
    ]
    for cd in common_depts:
        if not any(d['name'].lower() == cd.lower() for d in display_depts):
            icon = dept_icons.get(cd, 'fa-user-md')
            display_depts.append({
                'name': cd,
                'icon': icon,
                'count': 0
            })
            
    display_depts = sorted(display_depts, key=lambda x: x['name'])
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 9
    total_filtered = len(filtered_doctors)
    total_pages = (total_filtered + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_doctors = filtered_doctors[start_idx:end_idx]
    
    return render_template(
        'doctor.html', 
        doctors=paginated_doctors, 
        q=q, 
        active_dept=dept, 
        active_country=country_filter,
        active_scope=scope,
        departments=display_depts,
        available_countries=available_countries,
        country_flags=GLOBAL_COUNTRY_FLAGS,
        total_doctors_count=len(all_db_doctors),
        page=page,
        total_pages=total_pages
    )



@doctor_bp.route('/doctor/<path:doc_id>', methods=['GET', 'POST'])
def doctor_detail(doc_id):
    # Find doctor from the database
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if not doctor:
        return "Doctor not found", 404

    doc_id_val = doc_id # Use the string ID

    # If POST, it's an appointment booking
    if request.method == 'POST':
        # Collect appointment details
        patient_name = request.form.get('patient_name')
        patient_phone = request.form.get('patient_phone')
        patient_age = request.form.get('patient_age')
        patient_id_number = request.form.get('patient_id_number')
        appointment_date_str = request.form.get('date')
        appointment_time_str = request.form.get('time')
        reason = request.form.get('reason')

        # Handle File Upload
        document_path = None
        if 'medical_document' in request.files:
            file = request.files['medical_document']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static/uploads/documents')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_filename))
                document_path = unique_filename

        if not all([patient_name, patient_phone, patient_age, patient_id_number, appointment_date_str, appointment_time_str]):
            flash('All fields are required to book an appointment.', 'error')
        else:
            consult_type = request.form.get('consultation_type') or ('Cross-Border Video Consultation' if getattr(doctor, 'is_international', False) else 'In-Person & Online')
            p_country = request.form.get('patient_country') or getattr(current_user, 'country', 'India')
            
            # Create a new appointment in the in-memory store
            appt_id = TEMP_DATA['next_ids']['appointment']
            new_appointment = Appointment(
                id=appt_id,
                patient_name=patient_name,
                doctor_id=doc_id_val,
                appointment_date=datetime.strptime(appointment_date_str, '%Y-%m-%d').date(),
                appointment_time=datetime.strptime(appointment_time_str, '%H:%M').time(),
                patient_phone=patient_phone,
                patient_age=patient_age,
                patient_id_number=patient_id_number,
                reason=reason,
                status='awaiting_payment',
                document_path=document_path,
                department=doctor.department or 'General Medicine',
                consultation_type=consult_type,
                patient_country=p_country,
                doctor_country=getattr(doctor, 'country', 'India'),
                doctor_timezone=getattr(doctor, 'timezone', 'IST (UTC+5:30)'),
                currency=getattr(doctor, 'currency', 'INR'),
                fee_amount=float(doctor.consultation_fee or 500.0),
                telemedicine_room_id=f"DevAiConsult_Appt{appt_id}_Doc{str(doc_id_val).replace('/', '')}"
            )
            if current_user.is_authenticated and not current_user.is_doctor:
                new_appointment.patient_id = current_user.id

            TEMP_DATA['appointments'][appt_id] = new_appointment
            TEMP_DATA['next_ids']['appointment'] += 1
            save_data() # Save after creating appointment
            return redirect(url_for('appointment_payment', appointment_id=appt_id))
        return redirect(url_for('doctor_detail', doc_id=doc_id_val))

    # Fetch other specialists in the same department or hospital
    related_doctors = [
        d for d in TEMP_DATA['doctors'].values() 
        if str(d.id) != str(doctor.id) 
        and not getattr(d, 'is_hidden', False) 
        and not getattr(d, 'is_blocked', False)
        and (d.department == doctor.department or (doctor.hospital_name and d.hospital_name == doctor.hospital_name))
    ][:4]

    return render_template('doctor_detail.html', doctor=doctor, related_doctors=related_doctors)



@doctor_bp.route('/doctor/info')
def doctor_info():
    return render_template('doctor_info.html')




@doctor_bp.route('/doctor/dashboard', methods=['GET', 'POST'])
@doctor_required
def doctor_dashboard():
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    if not doctor:
        flash('Doctor not found.', 'error')
        return redirect(url_for('doctor_login'))

    pending_hospital = None
    if doctor.hospital_id and doctor.hospital_approval_status == 'pending':
        pending_hospital = TEMP_DATA['hospitals'].get(doctor.hospital_id)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not check_password_hash(doctor.password, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('doctor_dashboard', tab='settings'))

            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('doctor_dashboard', tab='settings'))

            doctor.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
            save_data()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('doctor_dashboard', tab='settings'))

        fields_to_update = [
            'first_name', 'last_name', 'email', 'phone', 'department', 
            'specialization', 'address', 'hospital_name', 'hospital_address', 'city', 'state',
            'district', 'pincode', 'country', 'bio', 'qualification', 'license_number',
            'experience', 'consultation_type', 'consultation_fee', 'latitude', 'longitude',
            'working_hours', 'languages_spoken', 'social_links'
        ]
        for field in fields_to_update:
            if field in request.form:
                setattr(doctor, field, request.form.get(field))
        
        # Handle Profile Picture Upload (Cropped Base64 or Raw File)
        profile_input = request.form.get('cropped_profile_image') or request.form.get('profile_image_base64')
        if not profile_input and 'profilePicture' in request.files:
            file = request.files['profilePicture']
            if file and file.filename != '':
                profile_input = file

        if profile_input:
            saved_filename = save_user_profile_image(
                profile_input,
                target_size=(500, 500),
                filename_prefix=f"doctor_profile_{doctor.id}"
            )
            if saved_filename:
                doctor.profile_picture_url = saved_filename
        save_data()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('doctor_dashboard'))

    # Fetch upcoming appointments
    today = date.today()
    todays_appointments = sorted([
        appt for appt in TEMP_DATA['appointments'].values()
        if appt.doctor_id == doctor.id and \
           appt.appointment_date == today and \
           appt.status != 'cancelled'
    ], key=lambda x: x.appointment_time)

    all_doctor_appointments = sorted([
        appt for appt in TEMP_DATA['appointments'].values()
        if appt.doctor_id == doctor.id and \
           appt.status != 'cancelled' # Include cancelled for filtering, but default view might exclude
    ], key=lambda x: (x.appointment_date, x.appointment_time))

    # Calculate Total Income
    total_income = 0
    try:
        fee = float(doctor.consultation_fee) if doctor.consultation_fee else 0.0
    except ValueError:
        fee = 0.0
    
    for appt in TEMP_DATA['appointments'].values():
        if appt.doctor_id == doctor.id and appt.status in ['confirmed', 'completed']:
            total_income += fee

    # --- Filtering Logic ---
    search_query = request.args.get('search_query', '').strip().lower()
    filter_status = request.args.get('filter_status', 'all')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    filtered_appointments = []
    for appt in all_doctor_appointments:
        # Date filter
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                if appt.appointment_date < start_dt:
                    continue
            except ValueError:
                pass # Ignore invalid date format
        if end_date_str:
            try:
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if appt.appointment_date > end_dt:
                    continue
            except ValueError:
                pass # Ignore invalid date format

        # Status filter
        if filter_status != 'all' and appt.status != filter_status:
            continue

        # Search query (patient name) filter
        if search_query and search_query not in appt.patient_name.lower():
            continue

        filtered_appointments.append(appt)

    # Sort filtered appointments by date and time
    filtered_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time))

    # --- Pagination Logic ---
    page = request.args.get('page', 1, type=int)
    per_page = 5 # Number of appointments per page
    total_appointments = len(filtered_appointments)
    total_pages = ceil(total_appointments / per_page) if total_appointments > 0 else 1

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_appointments = filtered_appointments[start_index:end_index]

    # Generate Realistic Activity Log from real data
    activities = []
    for appt in TEMP_DATA.get('appointments', {}).values():
        if appt.doctor_id == doctor.id:
            color = 'emerald' if appt.status == 'confirmed' else ('amber' if appt.status == 'pending' else 'slate')
            dt_val = getattr(appt, 'created_at', utcnow())
            if isinstance(dt_val, str):
                try: dt_val = datetime.fromisoformat(dt_val.replace('Z', '+00:00').split('.')[0])
                except ValueError: dt_val = utcnow()
            
            activities.append({
                'title': f"Appointment {appt.status.capitalize()}",
                'desc': f"Patient: {appt.patient_name}",
                'time': dt_val,
                'color': color
            })
            
    for msg in TEMP_DATA.get('messages', {}).values():
        if msg.doctor_id == doctor.id and msg.sender == 'patient':
            p_name = TEMP_DATA['patients'][msg.patient_id].name if msg.patient_id in TEMP_DATA['patients'] else 'Patient'
            activities.append({
                'title': "New Message Received",
                'desc': f"From: {p_name}",
                'time': getattr(msg, 'created_at', utcnow()),
                'color': 'blue'
            })
    
    activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = activities[:5]

    # Calculate Past 6 Months Analytics (Consultation Volume & Earnings)
    import calendar
    analytics_labels = []
    all_doctors = list(TEMP_DATA['doctors'].values())
    
    incoming_referrals = sorted([
        ref for ref in TEMP_DATA.get('referrals', {}).values()
        if ref.referred_doctor_id == current_user.id
    ], key=lambda x: x.created_at, reverse=True)
    
    sent_referrals = sorted([
        ref for ref in TEMP_DATA.get('referrals', {}).values()
        if ref.referring_doctor_id == current_user.id
    ], key=lambda x: x.created_at, reverse=True)

    # Calculate Past 6 Months Analytics (Consultation Volume & Earnings)
    unread_notifications = [
        n for n in TEMP_DATA.get('notifications', {}).values()
        if n.user_id == current_user.id and n.status == 'unread'
    ]
    unread_notifications.sort(key=lambda x: x.created_at, reverse=True)

    import calendar
    analytics_volume = []
    analytics_earnings = []
    
    current_date = date.today()
    for i in range(5, -1, -1):
        y = current_date.year
        m = current_date.month - i
        while m <= 0:
            m += 12
            y -= 1
        
        month_name = calendar.month_abbr[m] + f" {y}"
        analytics_labels.append(month_name)
        
        month_appts = [
            appt for appt in TEMP_DATA['appointments'].values()
            if appt.doctor_id == doctor.id and \
               appt.appointment_date.year == y and \
               appt.appointment_date.month == m and \
               appt.status in ['confirmed', 'completed']
        ]
        analytics_volume.append(len(month_appts))
        
        try:
            fee = float(doctor.consultation_fee) if doctor.consultation_fee else 0.0
        except ValueError:
            fee = 0.0
        analytics_earnings.append(len(month_appts) * fee)

    # Filter patients: only show those who have booked an appointment or sent a message to this doctor
    contacted_patient_ids = set()
    for appt in TEMP_DATA.get('appointments', {}).values():
        if appt.doctor_id == doctor.id:
            contacted_patient_ids.add(appt.patient_id)
    for msg in TEMP_DATA.get('messages', {}).values():
        if msg.doctor_id == doctor.id:
            contacted_patient_ids.add(msg.patient_id)

    patients_list = [
        pat for pat in TEMP_DATA.get('patients', {}).values()
        if pat.id in contacted_patient_ids
    ]
    patients_json = [{
        'id': pat.id,
        'name': pat.name,
        'email': pat.email,
        'age': pat.age,
        'gender': pat.gender,
        'profile_picture_url': pat.profile_picture_url,
        'phone': pat.phone,
        'address': pat.address,
        'clinical_record': get_patient_clinical_record(pat)
    } for pat in patients_list]
    pharmacy_meds = TEMP_DATA.get('medicines', [])
    
    # Serialize all doctor appointments to JSON for client EHR auditing
    appointments_json = [{
        'id': appt.id,
        'patient_id': appt.patient_id,
        'patient_name': appt.patient_name,
        'appointment_date': appt.appointment_date.strftime('%Y-%m-%d'),
        'appointment_time': appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time else '',
        'reason': appt.reason or 'Consultation',
        'status': appt.status,
        'prescription_path': appt.prescription_path
    } for appt in all_doctor_appointments]

    # Fetch lab requests made by this doctor
    lab_requests = [
        req for req in TEMP_DATA.get('lab_requests', {}).values()
        if req.doctor_id == doctor.id
    ]
    lab_requests.sort(key=lambda x: x.created_at, reverse=True)

    # Fetch telemedicine appointments (fallback to all confirmed/pending if none are labeled telemedicine)
    telemedicine_appointments = [
        appt for appt in all_doctor_appointments
        if appt.status in ['confirmed', 'pending'] and any(term in str(getattr(appt, 'reason', '')).lower() for term in ['video', 'telemedicine', 'online', 'virtual'])
    ]
    if not telemedicine_appointments:
        telemedicine_appointments = [
            appt for appt in all_doctor_appointments
            if appt.status in ['confirmed', 'pending']
        ]

    # Fetch real bed bookings for the doctor's hospital
    bed_bookings = [
        bb for bb in TEMP_DATA.get('bed_bookings', {}).values()
        if doctor.hospital_id and str(bb.hospital_id) == str(doctor.hospital_id)
    ]

    # Fetch confidential medical records shared with this doctor by patients
    shared_medical_records = [
        rec for rec in TEMP_DATA.get('medical_records', {}).values()
        if rec.is_shared_with(doctor.id) or rec.is_shared_with(current_user.id)
    ]
    shared_medical_records.sort(key=lambda r: str(r.record_date or r.created_at), reverse=True)

    return render_template(
        'doctor_dashboard.html',
        doctor=doctor,
        upcoming_appointments=paginated_appointments, # Now this is the paginated list
        search_query=search_query,
        filter_status=filter_status,
        start_date=start_date_str,
        end_date=end_date_str,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_appointments=total_appointments,
        total_income=total_income,
        recent_activities=recent_activities,
        analytics_labels=analytics_labels,
        analytics_volume=analytics_volume,
        analytics_earnings=analytics_earnings,
        patients=patients_list,
        patients_json=patients_json,
        pharmacy_meds=pharmacy_meds,
        appointments_json=appointments_json,
        opinion=TEMP_DATA.get('doctor_opinions', {}).get(doctor.id),
        pending_hospital=pending_hospital,
        todays_appointments=todays_appointments,
        lab_requests=lab_requests,
        shared_medical_records=shared_medical_records,
        profile_url=url_for('get_doctor_image', doc_id=doctor.id),
        telemedicine_appointments=telemedicine_appointments,
        bed_bookings=bed_bookings,
        unread_notifications=unread_notifications
    )



@doctor_bp.route('/doctor/medical-records/<record_id>/add-note', methods=['POST'])
@doctor_required
def doctor_add_medical_record_note(record_id):
    """Allows an authorized doctor to add clinical feedback / consultation remarks to a shared patient record."""
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    if not doctor:
        flash('Doctor profile not found.', 'error')
        return redirect(url_for('doctor_dashboard') + '#ehr')

    record = TEMP_DATA.get('medical_records', {}).get(str(record_id))
    if not record or not (record.is_shared_with(doctor.id) or record.is_shared_with(current_user.id)):
        flash('Unauthorized or medical record not shared with you.', 'error')
        return redirect(url_for('doctor_dashboard') + '#ehr')

    note_text = (request.form.get('doctor_note') or '').strip()
    if note_text:
        doc_name = getattr(doctor, 'name', '') or f"Dr. {doctor.first_name} {doctor.last_name}".strip()
        record.add_doctor_note(
            doctor_id=doctor.id,
            doctor_name=doc_name,
            note=note_text
        )
        save_data()
        
        # Notify patient of doctor review
        create_notification(
            user_id=record.patient_id,
            user_type='patient',
            message=f"{doc_name} reviewed your medical record '{record.title}' and provided clinical remarks.",
            link=url_for('patient_dashboard') + '?tab=tab-medical_records'
        )
        flash(f"Clinical consultation remarks added to '{record.title}' successfully.", 'success')
    else:
        flash('Please enter your clinical review remarks before submitting.', 'warning')

    return redirect(url_for('doctor_dashboard') + '#ehr')




@doctor_bp.route('/doctor/lab-request/add', methods=['POST'])
@doctor_required
def doctor_add_lab_request():
    patient_id = request.form.get('patient_id')
    test_name = request.form.get('test_name')
    notes = request.form.get('notes', '')
    
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for('doctor_dashboard', tab='lab_requests'))
        
    if not test_name:
        flash("Test name is required.", "error")
        return redirect(url_for('doctor_dashboard', tab='lab_requests'))
        
    if 'lab_requests' not in TEMP_DATA:
        TEMP_DATA['lab_requests'] = {}
        
    # Generate next ID
    max_id = max([int(k) for k in TEMP_DATA['lab_requests'].keys()] + [0])
    new_id = str(max_id + 1)
    
    new_request = LabRequest(
        id=new_id,
        doctor_id=current_user.id,
        patient_id=patient.id,
        patient_name=patient.name,
        test_name=test_name,
        notes=notes
    )
    TEMP_DATA['lab_requests'][new_id] = new_request
    save_data()
    flash("Lab request ordered successfully!", "success")
    return redirect(url_for('doctor_dashboard', tab='lab_requests'))



@doctor_bp.route('/doctor/availability/update', methods=['POST'])
@doctor_required
def doctor_update_availability():
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('doctor_login'))
        
    doctor.availability_status = request.form.get('availability_status', 'available')
    doctor.working_hours = request.form.get('working_hours', '9:00 AM - 5:00 PM')
    save_data()
    flash("Availability updated successfully!", "success")
    return redirect(url_for('doctor_dashboard', tab='availability'))



@doctor_bp.route('/doctor/ipd/discharge/<booking_id>', methods=['POST'])
@doctor_required
def doctor_discharge_patient(booking_id):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if not booking:
        booking = TEMP_DATA.get('bed_bookings', {}).get(int(booking_id)) if booking_id.isdigit() else None
        
    if not booking:
        flash("Bed booking not found.", "error")
        return redirect(url_for('doctor_dashboard', tab='ipd_management'))
        
    booking.status = 'discharged'
    save_data()
    flash("Patient discharged and bed released successfully.", "success")
    return redirect(url_for('doctor_dashboard', tab='ipd_management'))



@doctor_bp.route('/doctor/ipd/approve/<booking_id>', methods=['POST'])
@doctor_required
def doctor_approve_bed_booking(booking_id):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if not booking:
        booking = TEMP_DATA.get('bed_bookings', {}).get(int(booking_id)) if booking_id.isdigit() else None
        
    if not booking:
        flash("Bed booking not found.", "error")
        return redirect(url_for('doctor_dashboard', tab='ipd_management'))
        
    booking.status = 'approved'
    save_data()
    flash("Bed booking approved successfully.", "success")
    return redirect(url_for('doctor_dashboard', tab='ipd_management'))



@doctor_bp.route('/api/doctor/submit-opinion', methods=['POST'])
@doctor_required
def submit_doctor_opinion():
    rating = request.form.get('rating', 5, type=int)
    experience = request.form.get('experience', '').strip()
    average_appointments = request.form.get('average_appointments', '').strip()
    
    if not experience:
        flash('Please enter your experience/opinion text.', 'error')
        return redirect(url_for('doctor_dashboard'))
        
    TEMP_DATA.setdefault('doctor_opinions', {})[current_user.id] = {
        'doctor_id': current_user.id,
        'rating': rating,
        'experience': experience,
        'average_appointments': average_appointments,
        'created_at': utcnow().isoformat()
    }
    save_data()
    flash('Thank you for sharing your opinion!', 'success')
    return redirect(url_for('doctor_dashboard') + '?tab=opinion')



@doctor_bp.route('/doctor/image/<path:doc_id>')
@doctor_bp.route('/image/doctor/<path:doc_id>')
def get_doctor_image(doc_id):
    """Serves the doctor's profile image from the database or static files."""
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if not doctor and doc_id in ['admin', 'DOC/2026/001']:
        doctor = next((d for d in TEMP_DATA['doctors'].values() if getattr(d, 'email', '') == 'admin@spherixclinic.com'), None)

    static_dir = current_app.static_folder or os.path.join(current_app.root_path, '..', 'static')

    # Check for administration user profile image
    if doctor and (
        getattr(doctor, 'email', '') == 'admin@spherixclinic.com' or
        getattr(doctor, 'department', '') in ['Administration', 'System Core Administration'] or
        getattr(doctor, 'profile_picture_url', '') in ['images/sunnykk.jpg', 'sunnykk.jpg', 'static/images/sunnykk.jpg']
    ):
        admin_img_path = os.path.join(static_dir, 'images', 'sunnykk.jpg')
        if os.path.exists(admin_img_path):
            return send_file(admin_img_path)

    if doctor and getattr(doctor, 'profile_picture_url', None):
        pic_url = str(doctor.profile_picture_url).strip()
        if pic_url.startswith('images/'):
            file_path = os.path.join(static_dir, pic_url)
        elif pic_url.startswith('uploads/'):
            file_path = os.path.join(static_dir, pic_url)
        else:
            file_path = os.path.join(static_dir, 'uploads', pic_url)
            if not os.path.exists(file_path):
                alt_path = os.path.join(static_dir, 'images', pic_url)
                if os.path.exists(alt_path):
                    file_path = alt_path

        if os.path.exists(file_path):
            return send_file(file_path)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT image_data, content_type FROM doctor_images WHERE doctor_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return send_file(BytesIO(row[0]), mimetype=row[1])
    except Exception as e:
        print(f"Error fetching image for {doc_id}: {e}")

    # Fallback placeholder if no image in DB
    # Generate a realistic face from pravatar using a deterministic hash of the ID
    return redirect(f"https://i.pravatar.cc/250?u={doc_id}")



@doctor_bp.route('/doctor/chat/<path:patient_id>')
@doctor_required
@log_medical_access(action_name="OPEN_PATIENT_CHAT", target_patient_param="patient_id")
def doctor_chat(patient_id):
    patient_id = parse_route_id(patient_id)
    """Renders the chat interface for a doctor to talk to a specific patient."""
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for('doctor_dashboard'))

    # Ensure the current doctor has an appointment with this patient to be able to chat
    has_appointment = any(
        appt.patient_id == patient_id
        for appt in TEMP_DATA['appointments'].values()
        if appt.doctor_id == current_user.id
    )
    if not has_appointment:
        flash("You can only chat with patients you have an appointment with.", "error")
        return redirect(url_for('doctor_dashboard'))

    return render_template('doctor_chat.html', patient=patient, doctor=current_user)



@doctor_bp.route('/api/chat/<path:patient_id>/send', methods=['POST'])
@doctor_required
@log_medical_access(action_name="SEND_CHAT_MESSAGE", target_patient_param="patient_id")
def send_chat_message(patient_id):
    patient_id = parse_route_id(patient_id)
    """API endpoint for a doctor to send a message to a patient."""
    if request.is_json:
        data = request.get_json()
        content = data.get('content', '').strip()
    else:
        content = request.form.get('content', '').strip()
        
    attachment_url = None
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
            attachment_url = f"chat_{timestamp}_{filename}"
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'chat')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, attachment_url))

    if not content and not attachment_url:
        return jsonify({"success": False, "message": "Message cannot be empty."}), 400

    msg_id = TEMP_DATA['next_ids']['message']
    new_message = Message(
        id=msg_id, doctor_id=current_user.id, patient_id=patient_id,
        sender='doctor', content=content, attachment_url=attachment_url
    )
    TEMP_DATA['messages'][msg_id] = new_message
    TEMP_DATA['next_ids']['message'] += 1
    save_data()
    
    room = f"doctor_patient_{current_user.id}_{patient_id}"
    socketio.emit('new_message', {
        'sender': 'doctor',
        'content': content,
        'attachment_url': attachment_url,
        'created_at': new_message.created_at.isoformat()
    }, room=room)
    
    return jsonify({"success": True, "message": "Message sent."})



@doctor_bp.route('/api/doctor/update_status', methods=['POST'])
@doctor_required
def update_doctor_status():
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    if not doctor:
        return jsonify({"success": False, "message": "Doctor not found."}), 404
    data = request.get_json() or {}
    status = data.get('status')
    if status not in ['available', 'busy', 'on_leave']:
        return jsonify({"success": False, "message": "Invalid status value."}), 400
    doctor.availability_status = status
    save_data()
    return jsonify({"success": True, "message": "Status updated successfully.", "status": status})



@doctor_bp.route('/api/doctor/appointment/complete_with_prescription/<int:appointment_id>', methods=['POST'])
@doctor_required
def complete_with_prescription(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not (appointment and appointment.doctor_id == current_user.id):
        return jsonify({"success": False, "message": "Appointment not found or permission denied."}), 404
        
    data = request.get_json() or {}
    diagnosis = data.get('diagnosis', '').strip()
    medicines = data.get('medicines', [])
    instructions = data.get('instructions', '').strip()
    
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        doctor = appointment.doctor
        hospital = None
        for h in TEMP_DATA.get('hospitals', {}).values():
            if str(getattr(h, 'name', '')).strip().lower() == str(doctor.hospital_name).strip().lower():
                hospital = h
                break
                
        # Logo styling
        logo_loaded = False
        if hospital and getattr(hospital, 'logo_url', None):
            logo_path = os.path.join(current_app.root_path, 'static/uploads/hospital_logos', hospital.logo_url)
            if os.path.exists(logo_path):
                try:
                    pdf.image(logo_path, 15, 15, 22, 22)
                    logo_loaded = True
                except Exception as e:
                    print(f"Error loading logo: {e}")
                    
        if logo_loaded:
            pdf.set_left_margin(42)
            pdf.set_x(42)
            
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(13, 148, 136) # Premium health teal
        h_name = hospital.name if hospital else (doctor.hospital_name or 'SPHERIX HEALTHCARE')
        pdf.cell(0, 8, to_latin1_str(h_name), 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139) # Slate-500
        
        # Resolve address, phone, email dynamically using hospital, falling back to doctor attributes
        addr = None
        phone = None
        email = None
        
        if hospital:
            addr = hospital.address or doctor.hospital_address or doctor.address
            phone = hospital.phone or doctor.phone
            email = hospital.email or doctor.email
        else:
            addr = doctor.hospital_address or doctor.address
            phone = doctor.phone
            email = doctor.email
            
        if addr:
            pdf.cell(0, 5, to_latin1_str(addr), 0, 1, 'L')
        if phone or email:
            contact_info = ""
            if phone:
                contact_info += f"Phone: {phone}"
            if email:
                if contact_info:
                    contact_info += " | "
                contact_info += f"Email: {email}"
            pdf.cell(0, 5, to_latin1_str(contact_info), 0, 1, 'L')
            
        pdf.set_left_margin(15)
        pdf.set_x(15)
        pdf.ln(6)
        
        # Horizontal separating line
        pdf.set_draw_color(13, 148, 136)
        pdf.set_line_width(0.8)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(6)
        
        # Doctor & Patient Info Side-by-Side
        doctor_y = pdf.get_y()
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(30, 41, 59) # Slate-800
        pdf.cell(90, 5, f"Dr. {doctor.first_name} {doctor.last_name}", 0, 1)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(90, 4.5, f"Specialization: {doctor.specialization or 'General Specialist'}", 0, 1)
        pdf.cell(90, 4.5, f"Reg/License No: {doctor.license_number or 'N/A'}", 0, 1)
        
        patient_y = doctor_y
        pdf.set_xy(110, patient_y)
        
        patient = appointment.patient
        patient_age = getattr(patient, 'age', appointment.patient_age) or 'N/A'
        patient_gender = getattr(patient, 'gender', 'N/A')
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(85, 5, f"Patient: {appointment.patient_name}", 0, 1)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.set_x(110)
        pdf.cell(85, 4.5, f"Age / Gender: {patient_age} / {patient_gender}", 0, 1)
        pdf.set_x(110)
        pdf.cell(85, 4.5, f"Date: {date.today().strftime('%b %d, %Y')} | ID: #{appointment.id}", 0, 1)
        
        pdf.set_y(patient_y + 18)
        pdf.ln(4)
        
        # Clinical summary
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(13, 148, 136)
        pdf.cell(0, 6, "CLINICAL DIAGNOSIS & SUMMARY", 0, 1)
        
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(71, 85, 105)
        diag_str = diagnosis if diagnosis else "General Consultation & Follow-up"
        pdf.multi_cell(0, 5.5, to_latin1_str(diag_str))
        pdf.ln(5)
        
        # Rx Symbol
        pdf.set_font('Times', 'B', 24)
        pdf.set_text_color(13, 148, 136)
        pdf.cell(0, 10, "Rx", 0, 1)
        pdf.set_font('Helvetica', '', 10)
        
        pdf.set_text_color(30, 41, 59)
        if medicines:
            # Table Header
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_fill_color(240, 253, 250) # Light teal
            pdf.set_draw_color(204, 251, 241) # Light teal border
            pdf.cell(75, 8, " Medicine Name", 1, 0, 'L', 1)
            pdf.cell(35, 8, " Dosage", 1, 0, 'C', 1)
            pdf.cell(40, 8, " Timing / Instructions", 1, 0, 'C', 1)
            pdf.cell(30, 8, " Duration", 1, 1, 'C', 1)
            
            # Rows
            pdf.set_font('Helvetica', '', 9)
            pdf.set_draw_color(241, 245, 249) # Light slate borders
            for m in medicines:
                name_str = f" {m.get('name', 'N/A')}"
                dosage_str = f" {m.get('dosage', 'N/A')}"
                timing_str = f" {m.get('timing', 'N/A')}"
                duration_str = f" {m.get('duration', 'N/A')}"
                
                pdf.cell(75, 8, to_latin1_str(name_str), 1, 0, 'L')
                pdf.cell(35, 8, to_latin1_str(dosage_str), 1, 0, 'C')
                pdf.cell(40, 8, to_latin1_str(timing_str), 1, 0, 'C')
                pdf.cell(30, 8, to_latin1_str(duration_str), 1, 1, 'C')
        else:
            pdf.set_font('Helvetica', 'I', 9.5)
            pdf.set_text_color(148, 163, 184)
            pdf.cell(0, 6, "No specific medications prescribed.", 0, 1)
        pdf.ln(5)
        
        if instructions:
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(13, 148, 136)
            pdf.cell(0, 6, "SPECIAL INSTRUCTIONS", 0, 1)
            pdf.set_text_color(71, 85, 105)
            pdf.set_font('Helvetica', '', 9.5)
            pdf.multi_cell(0, 5.5, to_latin1_str(instructions))
            pdf.ln(10)
            
        current_y = pdf.get_y()
        if current_y > 230:
            pdf.add_page()
            current_y = pdf.get_y()
            
        pdf.set_y(current_y + 15)
        pdf.set_draw_color(203, 213, 225)
        pdf.line(130, pdf.get_y(), 190, pdf.get_y())
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_font('Helvetica', 'B', 9.5)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(115, 5, "", 0, 0)
        pdf.cell(75, 5, f"Dr. {doctor.first_name} {doctor.last_name}", 0, 1, 'C')
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(115, 5, "", 0, 0)
        pdf.cell(75, 5, "Authorized Practitioner Signature", 0, 1, 'C')
        
        timestamp = utcnow().strftime('%Y%m%d%H%M%S')
        unique_filename = f"rx_{timestamp}_{appointment.id}.pdf"
        upload_folder = os.path.join(current_app.root_path, 'static/uploads/prescriptions')
        os.makedirs(upload_folder, exist_ok=True)
        pdf.output(os.path.join(upload_folder, unique_filename), 'F')
        
        appointment.prescription_path = unique_filename
        appointment.status = 'completed'
        save_data()
        
        patient = appointment.patient
        if patient and patient.email:
            subject = "Prescription Issued & Appointment Completed"
            body = f"Dear {patient.name},\n\nDr. {doctor.first_name} {doctor.last_name} has completed your appointment on {appointment.appointment_date} and issued a digital prescription.\n\nYou can view and download the prescription PDF directly from your dashboard.\n\nBest regards,\nThe Spherix Clinic Team"
            send_notification_email(patient.email, subject, body)
            
        return jsonify({"success": True, "message": "Prescription generated and appointment completed.", "prescription_path": unique_filename})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error generating prescription: {str(e)}"}), 500



@doctor_bp.route('/api/doctor/conversations', methods=['GET'])
@doctor_required
def get_doctor_conversations():
    """Get list of all patients with whom a doctor has conversations."""
    conversations = {}
    unread_by_patient = {}
    
    doctor_id = get_actual_user_id(current_user.id)
    
    # Collect all messages for this doctor
    for msg in TEMP_DATA['messages'].values():
        if msg.doctor_id == doctor_id:
            patient_id = msg.patient_id
            
            if patient_id not in conversations:
                patient = TEMP_DATA['patients'].get(patient_id)
                conversations[patient_id] = {
                    'patient_id': patient_id,
                    'patient_name': patient.name if patient else 'Unknown Patient',
                    'profile_picture_url': patient.profile_picture_url if patient else None,
                    'last_message': msg.content[:50],
                    'unread_count': 0
                }
            
            # Update last message (rough, just take the most recent)
            conversations[patient_id]['last_message'] = msg.content[:50]
            
            # Count unread messages from patient
            if msg.sender == 'patient' and msg.patient_id not in unread_by_patient:
                unread_by_patient[patient_id] = 0
    
    # Count unread messages for each patient
    for msg in TEMP_DATA['messages'].values():
        if msg.doctor_id == doctor_id and msg.sender == 'patient':
            if msg.patient_id not in unread_by_patient:
                unread_by_patient[msg.patient_id] = 0
            # Consider all patient messages as unread (in a real app, you'd track read status)
            unread_by_patient[msg.patient_id] += 1
    
    # Sort by most recent
    sorted_convs = sorted(conversations.values(), key=lambda x: -len(str(x['last_message'])))
    
    return jsonify({
        'conversations': sorted_convs
    })



@doctor_bp.route('/api/patient/doctor-conversations', methods=['GET'])
@patient_required
def get_patient_doctor_conversations():
    """Get list of all doctors with whom a patient has conversations."""
    conversations = {}
    unread_by_doctor = {}
    
    patient_id = get_actual_user_id(current_user.id)
    
    # Collect all messages for this patient
    for msg in TEMP_DATA['messages'].values():
        if msg.patient_id == patient_id:
            doctor_id = msg.doctor_id
            
            if doctor_id not in conversations:
                doctor = TEMP_DATA['doctors'].get(doctor_id)
                if doctor:
                    conversations[doctor_id] = {
                        'doctor_id': doctor_id,
                        'doctor_name': f"{doctor.first_name} {doctor.last_name}",
                        'specialization': doctor.specialization,
                        'profile_picture_url': doctor.profile_picture_url,
                        'last_message': msg.content[:50],
                        'unread_count': 0
                    }
            
            # Update last message
            if doctor_id in conversations:
                conversations[doctor_id]['last_message'] = msg.content[:50]
    
    # Count unread messages for each doctor
    for msg in TEMP_DATA['messages'].values():
        if msg.patient_id == patient_id and msg.sender == 'doctor':
            if msg.doctor_id not in unread_by_doctor:
                unread_by_doctor[msg.doctor_id] = 0
            # Count unread messages
            unread_by_doctor[msg.doctor_id] += 1
    
    # Update unread counts
    for doctor_id in conversations:
        conversations[doctor_id]['unread_count'] = unread_by_doctor.get(doctor_id, 0)
    
    # Sort by most recent
    sorted_convs = sorted(conversations.values(), key=lambda x: -len(str(x['last_message'])))
    
    return jsonify({
        'conversations': sorted_convs
    })



@doctor_bp.route('/api/doctor/chat/<path:patient_id>/send', methods=['POST'])
@doctor_required
def send_message_doctor(patient_id):
    patient_id = parse_route_id(patient_id)
    """Send a message from doctor to patient."""
    if request.is_json:
        data = request.get_json()
        content = data.get('content', '').strip()
    else:
        content = request.form.get('content', '').strip()
    
    attachment_url = None
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
            attachment_url = f"chat_{timestamp}_{filename}"
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'chat')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, attachment_url))

    if not content and not attachment_url:
        return jsonify({"success": False, "message": "Message cannot be empty."}), 400
    
    # Check if patient exists
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        return jsonify({"success": False, "message": "Patient not found."}), 404
    
    doctor_id = get_actual_user_id(current_user.id)
    
    # Save message
    msg_id = TEMP_DATA['next_ids']['message']
    new_message = Message(
        id=msg_id, doctor_id=doctor_id, patient_id=patient_id,
        sender='doctor', content=content, attachment_url=attachment_url
    )
    TEMP_DATA['messages'][msg_id] = new_message
    TEMP_DATA['next_ids']['message'] += 1
    save_data()
    
    # Emit via Socket.IO
    room = f"doctor_patient_{doctor_id}_{patient_id}"
    socketio.emit('new_message', {
        'sender': 'doctor',
        'content': content,
        'attachment_url': attachment_url,
        'created_at': new_message.created_at.isoformat()
    }, room=room)
    
    return jsonify({"success": True, "message": "Message sent."})



@doctor_bp.route('/api/doctor/chat/<path:patient_id>/messages')
@doctor_required
def get_doctor_patient_messages(patient_id):
    patient_id = parse_route_id(patient_id)
    """Get messages between doctor and specific patient."""
    # Check if patient exists
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        return jsonify([]), 200  # Return empty array if patient not found
    
    doctor_id = get_actual_user_id(current_user.id)
    
    messages = [
        {
            "sender": msg.sender,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "attachment_url": getattr(msg, 'attachment_url', None)
        }
        for msg in TEMP_DATA['messages'].values()
        if msg.doctor_id == doctor_id and msg.patient_id == patient_id
    ]
    messages.sort(key=lambda x: x['created_at'])
    return jsonify(messages)



@doctor_bp.route('/doctor/appointment/cancel/<int:appointment_id>', methods=['POST'])
@doctor_required
def doctor_cancel_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.doctor_id == current_user.id:
        appointment.status = 'cancelled'        
        # Send email notification to patient about cancellation
        patient = appointment.patient
        if patient and patient.email:
            subject = "Notification: Your Appointment Has Been Cancelled"
            body = f"""
Dear {patient.name},

We are writing to inform you that your appointment with Dr. {appointment.doctor.first_name} {appointment.doctor.last_name} scheduled for {appointment.appointment_date.strftime('%B %d, %Y')} at {appointment.appointment_time.strftime('%I:%M %p')} has been cancelled by the doctor's office.

We apologize for any inconvenience this may cause. You can book a new appointment with this doctor or find another specialist on our platform.

Best regards,
The Spherix Clinic Team"""
            send_notification_email(patient.email, subject, body)
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been cancelled.", "success")
    else:
        flash("Appointment not found or you do not have permission.", "error")
    return redirect(url_for('doctor_dashboard'))



@doctor_bp.route('/doctor/appointment/upload_prescription/<int:appointment_id>', methods=['POST'])
@doctor_required
def upload_prescription(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not (appointment and appointment.doctor_id == current_user.id):
        flash("Appointment not found or permission denied.", "error")
        return redirect(url_for('doctor_dashboard'))

    file = request.files.get('prescription')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        timestamp = utcnow().strftime('%Y%m%d%H%M%S')
        unique_filename = f"rx_{timestamp}_{filename}"
        upload_folder = os.path.join(current_app.root_path, 'static/uploads/prescriptions')
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, unique_filename))

        appointment.prescription_path = unique_filename
        save_data()

        # Notify Patient
        patient = appointment.patient
        if patient and patient.email:
            subject = "Prescription Uploaded"
            body = f"Dear {patient.name},\n\nDr. {appointment.doctor.first_name} {appointment.doctor.last_name} has uploaded a prescription for your appointment on {appointment.appointment_date}.\n\nYou can view and download it from your dashboard.\n\nBest regards,\nThe Spherix Clinic Team"
            send_notification_email(patient.email, subject, body)

        flash('Prescription uploaded successfully.', 'success')
    else:
        flash('No file selected.', 'error')

    return redirect(url_for('doctor_dashboard'))



@doctor_bp.route('/hospital/doctor/add', methods=['POST'])
@hospital_required
def hospital_add_doctor():
    """Allows a hospital to add a new doctor to the system and associate them with the hospital."""
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash('Email and password are required.', 'error')
        return redirect(url_for('hospital_dashboard') + '#doctors')
        
    existing = next((d for d in TEMP_DATA['doctors'].values() if d.email == email), None)
    if existing:
        flash('A doctor with this email already exists in the system. Please use the "Invite Doctor" feature.', 'error')
        return redirect(url_for('hospital_dashboard') + '#doctors')
        
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
        specialization=request.form.get('specialization'),
        phone=request.form.get('phone'),
        hospital_id=current_user.id,
        hospital_name=current_user.name,
        hospital_address=current_user.address,
        hospital_approval_status='approved', # Approved by the hospital that adds them
        is_verified=True # Assume verified if added by a hospital
    )
    TEMP_DATA['doctors'][new_id] = new_doctor
    TEMP_DATA['next_ids']['doctor'] += 1
    save_data()
    flash(f'Dr. {new_doctor.last_name} has been added to your hospital staff.', 'success')
    return redirect(url_for('hospital_dashboard') + '#doctors')



@doctor_bp.route('/hospital/doctor/remove/<path:doc_id>', methods=['POST'])
@hospital_required
def hospital_remove_doctor_association(doc_id):
    """Removes a doctor's association from the current hospital."""
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if doctor and str(doctor.hospital_id) == str(current_user.id):
        doctor.hospital_id = None
        doctor.hospital_name = None
        doctor.hospital_address = None
        doctor.hospital_approval_status = None
        save_data()
        flash(f"Dr. {doctor.last_name} has been removed from your hospital's staff.", "success")
    else:
        flash("Doctor not found or not associated with your hospital.", "error")
    return redirect(url_for('hospital_dashboard') + '#doctors')



@doctor_bp.route('/staff/reception/prescription-print/<int:appt_id>')
@login_required
def prescription_print(appt_id):
    """Render a clean, high-resolution printable medical prescription & registration slip with automatic print trigger."""
    appt = TEMP_DATA.get('appointments', {}).get(appt_id)
    if not appt:
        flash("Appointment not found.", "error")
        return redirect(url_for('staff_reception_dashboard'))
    
    hospital_name_str = getattr(current_user, 'hospital_name', '')
    hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.name == hospital_name_str), None)
    doctor = TEMP_DATA['doctors'].get(appt.doctor_id)
    
    # Check if patient exists
    patient = None
    if getattr(appt, 'patient_id', None) and appt.patient_id in TEMP_DATA['patients']:
        patient = TEMP_DATA['patients'][appt.patient_id]
        
    return render_template('prescription_print.html', appt=appt, hospital=hospital, doctor=doctor, patient=patient, now=datetime.now())



@doctor_bp.route('/hospital/appointment/assign_doctor/<int:appointment_id>', methods=['POST'])
@hospital_or_staff_role_required('Appointment Management', 'Receptionist')
def hospital_assign_appointment_doctor(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        flash("Appointment record not found.", "error")
        return redirect(request.referrer or url_for('hospital_dashboard'))
        
    is_hospital = getattr(current_user, 'is_hospital', False)
    hosp = current_user if is_hospital else next((h for h in TEMP_DATA['hospitals'].values() if h.name == current_user.hospital_name), None)
    
    new_doctor_id = request.form.get('doctor_id')
    new_doctor = TEMP_DATA['doctors'].get(new_doctor_id)
    
    if not new_doctor or (new_doctor.hospital_name != hosp.name and str(getattr(new_doctor, 'hospital_id', '')) != str(hosp.id)):
        flash("Invalid doctor selected. The specialist must belong to this hospital facility.", "error")
        return redirect(request.referrer or url_for('hospital_dashboard'))
        
    appointment.doctor_id = new_doctor.id
    appointment.department = new_doctor.department or appointment.department
    appointment.is_auto_assigned = False
    appointment.staff_assigned_by = current_user.name if hasattr(current_user, 'name') else 'Hospital Staff'
    save_data()
    flash(f"Assigned Dr. {new_doctor.first_name} {new_doctor.last_name} ({new_doctor.department}) to appointment #{appointment_id} for {appointment.patient_name}.", "success")
    return redirect(request.referrer or url_for('hospital_dashboard') + '#appointments')



@doctor_bp.route('/pharmacy/upload-prescription')
def upload_prescription_page():
    """Redirects to the Medical Shop with the interactive Prescription Upload Sidebar opened."""
    return redirect(url_for('medical_shop', upload='1'))





def get_patient_clinical_record(patient):
    # Retrieve clinical record
    record = getattr(patient, 'clinical_record', None)
    if not record or not isinstance(record, dict) or not record.get('initialized', False):
        import random
        # Seed by name hash so it's deterministic
        name_hash = sum(ord(c) for c in patient.name) if patient.name else 0
        rng = random.Random(name_hash)
        
        common_allergies = ["Penicillin", "Sulfa Drugs", "Peanuts", "Dust Mites", "Pollen", "Aspirin", "Ibuprofen"]
        common_conditions = ["Hypertension", "Type 2 Diabetes", "Asthma", "Dyslipidemia", "Migraine", "Hypothyroidism", "GERD"]
        
        # Pick 0-2 allergies
        num_allergies = rng.randint(0, 2)
        allergies = rng.sample(common_allergies, num_allergies) if num_allergies > 0 else []
        
        # Pick 0-2 conditions
        num_conditions = rng.randint(0, 2)
        conditions = rng.sample(common_conditions, num_conditions) if num_conditions > 0 else []
        
        # Vitals history
        vitals = []
        base_bp_systolic = rng.randint(110, 135)
        base_bp_diastolic = rng.randint(70, 85)
        base_pulse = rng.randint(65, 80)
        
        for i in range(rng.randint(2, 4)):
            days_ago = (i + 1) * rng.randint(10, 30)
            record_date = (date.today() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            bp_sys = base_bp_systolic + rng.randint(-5, 5)
            bp_dia = base_bp_diastolic + rng.randint(-5, 5)
            pulse = base_pulse + rng.randint(-6, 6)
            temp = round(98.0 + rng.uniform(0.1, 1.2), 1)
            spo2 = rng.randint(97, 100)
            rr = rng.randint(12, 18)
            
            vitals.append({
                'date': record_date,
                'bp': f"{bp_sys}/{bp_dia}",
                'pulse': pulse,
                'temp': temp,
                'spo2': spo2,
                'rr': rr
            })
        
        vitals.reverse() # chronologically ascending
        
        # Labs
        labs = []
        if conditions:
            if "Hypertension" in conditions or "Dyslipidemia" in conditions:
                labs.append({
                    'date': (date.today() - timedelta(days=15)).strftime('%Y-%m-%d'),
                    'test': "Lipid Profile",
                    'result': f"Total Cholesterol: {rng.randint(190, 250)} mg/dL, LDL: {rng.randint(125, 168)} mg/dL (Elevated)",
                    'status': "Completed"
                })
            if "Type 2 Diabetes" in conditions:
                labs.append({
                    'date': (date.today() - timedelta(days=15)).strftime('%Y-%m-%d'),
                    'test': "HbA1c Glycated Hemoglobin",
                    'result': f"HbA1c: {round(rng.uniform(5.7, 7.3), 1)}% (Target: < 7.0%)",
                    'status': "Completed"
                })
        
        labs.append({
            'date': (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'test': "Complete Blood Count (CBC)",
            'result': "Hemoglobin: 14.1 g/dL, WBC: 7,100 /uL, Platelets: 245,000 /uL (Normal)",
            'status': "Completed"
        })
        
        record = {
            'initialized': True,
            'allergies': allergies,
            'conditions': conditions,
            'vitals': vitals,
            'labs': labs,
            'notes': [
                {
                    'date': (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'),
                    'content': "<div class='space-y-3 font-sans text-slate-700 text-xs'><div><span class='font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1'>Subjective (S)</span><p class='bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic'>Patient reports occasional headache and tiredness over past 2 weeks. No chest pain or dyspnea.</p></div><div><span class='font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1'>Objective (O)</span><p class='bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic'>BP: 130/82, Pulse: 72 bpm, Temp: 98.4 F, SpO2: 98%. Chest clear, CVS normal.</p></div><div><span class='font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1'>Assessment (A)</span><p class='bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic'>Mild essential hypertension, fatigue. Advised diet modifications.</p></div><div><span class='font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1'>Plan (P)</span><p class='bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic'>Order CBC and Lipid profile. Review in 2 weeks. Monitor BP twice weekly.</p></div></div>"
                }
            ]
        }
        patient.clinical_record = record
    return record


def _invoke_groq_soap_generator(raw_text):
    if not _is_groq_configured():
        return None
    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    prompt = f"""You are an advanced AI Clinical Scribe. Convert the following unstructured clinical observations/notes into a highly professional, formatted SOAP note (Subjective, Objective, Assessment, Plan). Keep the language formal, medically precise, and clear.
    
Unstructured observations:
"{raw_text}"

Output only the formatted SOAP note in HTML format (using Tailwind CSS class labels or simple markup). Do not include any introductory or concluding text outside the SOAP note. Use headings for S, O, A, P.
"""
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [
            {'role': 'system', 'content': 'You are a professional medical assistant.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.2
    }
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    try:
        import requests
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        payload_json = resp.json()
        text = _extract_groq_text_response(payload_json)
        return text
    except Exception as e:
        print(f"⚠️ Groq SOAP generation failed: {e}")
        return None


def mock_soap_note_generator(raw_text):
    sentences = [s.strip() for s in raw_text.split('.') if s.strip()]
    
    subjective = []
    objective = []
    assessment = []
    plan = []
    
    for s in sentences:
        s_lower = s.lower()
        if any(w in s_lower for w in ["feel", "complain", "pain", "headache", "nausea", "cough", "history", "patient reports", "duration", "days"]):
            subjective.append(s)
        elif any(w in s_lower for w in ["bp", "temp", "pulse", "bpm", "oxygen", "spo2", "examination", "exam", "clear", "normal", "heart rate", "lungs"]):
            objective.append(s)
        elif any(w in s_lower for w in ["diagnose", "ruling out", "stage", "chronic", "acute", "suspected", "staging"]):
            assessment.append(s)
        else:
            plan.append(s)
            
    if not subjective: subjective = ["Patient presents for clinical evaluation. " + raw_text]
    if not objective: objective = ["Vitals reviewed. Physical exam stable."]
    if not assessment: assessment = ["Symptomatic evaluation. Differential diagnosis considered based on patient history."]
    if not plan: plan = ["Follow up as directed. Monitor symptoms and report any red flags."]
    
    html = f"""
    <div class="space-y-3 font-sans text-slate-700 text-xs">
        <div>
            <span class="font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1">Subjective (S)</span>
            <p class="bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic">{" ".join(subjective)}</p>
        </div>
        <div>
            <span class="font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1">Objective (O)</span>
            <p class="bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic">{" ".join(objective)}</p>
        </div>
        <div>
            <span class="font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1">Assessment (A)</span>
            <p class="bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic">{" ".join(assessment)}</p>
        </div>
        <div>
            <span class="font-bold text-slate-800 text-[10px] uppercase tracking-wider block mb-1">Plan (P)</span>
            <p class="bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic">{" ".join(plan)}</p>
        </div>
    </div>
    """
    return html

