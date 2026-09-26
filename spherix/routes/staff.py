from spherix.services.upload_service import save_user_profile_image, upload_to_cloudinary, UPLOAD_CACHE
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

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/pharmacist', methods=['GET', 'POST'])
def pharmacist():
    settings = TEMP_DATA.get('settings', {})
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone', 'N/A')
        address = request.form.get('address', 'N/A')
        topic = request.form.get('topic', 'Pharmacist Support')
        message = request.form.get('message')

        if name and email and message:
            new_message = {
                'name': name,
                'email': email,
                'phone': phone,
                'address': address,
                'message': message,
                'category': topic,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            TEMP_DATA['contact_messages'].insert(0, new_message)
            save_data()

            admin_email = 'isunny28skk@gmail.com'
            subject = f"New Pharmacist Inquiry from {name}"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2 style="color: #0ea5e9;">New Pharmacist Inquiry</h2>
                <p><strong>Name:</strong> {name}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Phone:</strong> {phone}</p>
                <p><strong>Address:</strong> {address}</p>
                <p><strong>Topic:</strong> {topic}</p>
                <p><strong>Message:</strong></p>
                <div style="background: #f8fafc; padding: 15px; border-left: 4px solid #0ea5e9; border-radius: 4px;">
                    {message}
                </div>
            </div>
            """
            send_notification_email(admin_email, subject, body, is_html=True)

            flash("Your pharmacist request has been sent successfully!", "success")
            return redirect(url_for('pharmacist'))

    return render_template('pharmacist.html', settings=settings)



@staff_bp.route('/staff/dashboard')
@staff_required
def staff_dashboard():
    """Main dispatcher for staff dashboards based on role."""
    role = (getattr(current_user, 'role', '') or '').strip().lower()
    if any(r in role for r in ['reception', 'appointment', 'front desk']):
        return redirect(url_for('staff_reception_dashboard'))
    elif 'bed' in role:
        return redirect(url_for('staff_bed_dashboard'))
    elif 'blood' in role:
        return redirect(url_for('staff_blood_dashboard'))
    elif 'organ' in role:
        return redirect(url_for('staff_organ_dashboard'))
    elif 'nurse' in role or 'nursing' in role:
        return redirect(url_for('staff_nursing_dashboard'))
    else:
        return redirect(url_for('staff_general_dashboard'))



@staff_bp.route('/staff/profile/update', methods=['POST'])
def staff_update_profile():
    """Shared route for updating staff profile details."""
    # This route is called from multiple dashboards, so we use the generic @staff_required
    current_user.name = request.form.get('name', current_user.name)
    current_user.phone = request.form.get('phone', current_user.phone)
    new_password = request.form.get('password')
    if new_password:
         current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')

    # Handle Cropped Base64 Profile Picture or Raw File Upload
    profile_input = request.form.get('cropped_profile_image') or request.form.get('profile_image_base64')
    if not profile_input and 'profilePicture' in request.files:
        file = request.files['profilePicture']
        if file and file.filename != '':
            profile_input = file

    if profile_input:
        saved_filename = save_user_profile_image(
            profile_input,
            target_size=(500, 500),
            filename_prefix=f"staff_profile_{current_user.id}"
        )
        if saved_filename:
            current_user.profile_picture_url = saved_filename

    save_data()
    flash('Profile updated successfully!', 'success')
    return redirect(request.referrer or url_for('staff_dashboard'))



@staff_bp.route('/staff/dashboard/reception', methods=['GET', 'POST'])
@staff_role_required('Receptionist', 'Appointment Management')
def staff_reception_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    if 'visitor_passes' not in TEMP_DATA:
        TEMP_DATA['visitor_passes'] = {}

    hospital_name_clean = (hospital_name or '').strip().lower()
    hospital_id_str = str(hospital.id) if hospital and hasattr(hospital, 'id') else ''
    
    # Strictly retrieve doctors affiliated with this hospital
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if (hospital_name_clean and (getattr(d, 'hospital_name', '') or '').strip().lower() == hospital_name_clean) or
           (hospital_id_str and str(getattr(d, 'hospital_id', '')) == hospital_id_str)
    ]
    hospital_doctor_ids = {d.id for d in hospital_doctors}

    if request.method == 'POST' and hospital:
        if 'cancel_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                appt.status = 'cancelled'
                save_data()
                flash('Appointment cancelled successfully.', 'success')
        elif 'approve_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                appt.status = 'confirmed'
                save_data()
                flash('Appointment confirmed successfully.', 'success')
        elif 'complete_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                appt.status = 'completed'
                appt.queue_status = 'completed'
                save_data()
                flash('Appointment marked as completed.', 'success')
        elif 'reschedule_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                try:
                    new_date = datetime.strptime(request.form.get('new_date'), '%Y-%m-%d').date()
                    new_time = datetime.strptime(request.form.get('new_time'), '%H:%M').time()
                    appt.original_appointment_date = appt.appointment_date
                    appt.original_appointment_time = appt.appointment_time
                    appt.appointment_date = new_date
                    appt.appointment_time = new_time
                    save_data()
                    flash(f'Appointment rescheduled to {new_date} at {new_time.strftime("%I:%M %p")}.', 'success')
                except Exception as e:
                    flash(f'Error rescheduling: {str(e)}', 'error')
        elif 'update_queue_status' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                new_q_status = request.form.get('queue_status', 'waiting')
                appt.queue_status = new_q_status
                if new_q_status == 'in_consultation':
                    appt.status = 'confirmed'
                elif new_q_status == 'completed':
                    appt.status = 'completed'
                save_data()
                flash(f'Queue status for {appt.patient_name} updated to {new_q_status.replace("_", " ").title()}.', 'info')
        elif 'update_vitals' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                appt.vitals = {
                    'bp': request.form.get('bp', ''),
                    'pulse': request.form.get('pulse', ''),
                    'temp': request.form.get('temp', ''),
                    'spo2': request.form.get('spo2', ''),
                    'weight': request.form.get('weight', ''),
                    'allergies': request.form.get('allergies', '')
                }
                save_data()
                flash(f'Vitals recorded successfully for {appt.patient_name}.', 'success')
        elif 'collect_fee' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                appt = TEMP_DATA['appointments'][appt_id]
                if parse_route_id(appt.doctor_id) not in hospital_doctor_ids:
                    flash(f"Access Denied: You can only manage appointments for doctors affiliated with your hospital ({hospital_name}).", "error")
                    return redirect(url_for('staff_reception_dashboard'))
                try:
                    appt.fee_amount = float(request.form.get('fee_amount', 0))
                except Exception:
                    appt.fee_amount = 0
                appt.payment_mode = request.form.get('payment_mode', 'Cash')
                appt.payment_status = request.form.get('payment_status', 'paid')
                save_data()
                flash(f'Payment of Rs. {appt.fee_amount:.2f} ({appt.payment_mode}) recorded for {appt.patient_name}.', 'success')
        elif 'issue_visitor_pass' in request.form:
            try:
                pass_id = max([0] + [int(k) for k in TEMP_DATA['visitor_passes'].keys() if str(k).isdigit()]) + 1
                pass_num = f"VP-{pass_id:04d}"
                visitor_name = request.form.get('visitor_name')
                visitor_phone = request.form.get('visitor_phone')
                patient_name = request.form.get('patient_name')
                ward_room = request.form.get('ward_room', 'General Ward')
                relation = request.form.get('relation', 'Family / Attendant')
                valid_hours = request.form.get('valid_hours', '2')

                TEMP_DATA['visitor_passes'][pass_id] = {
                    'id': pass_id,
                    'hospital_id': hospital.id,
                    'pass_number': pass_num,
                    'visitor_name': visitor_name,
                    'visitor_phone': visitor_phone,
                    'patient_name': patient_name,
                    'ward_room': ward_room,
                    'relation': relation,
                    'valid_hours': valid_hours,
                    'status': 'active',
                    'issued_at': datetime.now(),
                    'issued_by': current_user.name
                }
                save_data()
                flash(f'Visitor Pass #{pass_num} issued successfully for {visitor_name}.', 'success')
            except Exception as e:
                flash(f'Error issuing visitor pass: {str(e)}', 'error')
        elif 'checkout_visitor_pass' in request.form:
            pass_id = parse_route_id(request.form.get('pass_id'))
            if pass_id in TEMP_DATA.get('visitor_passes', {}):
                TEMP_DATA['visitor_passes'][pass_id]['status'] = 'checked_out'
                save_data()
                flash('Visitor pass checked out successfully.', 'info')
        elif 'register_patient' in request.form:
            try:
                name = request.form.get('patient_name')
                phone = request.form.get('patient_phone')
                email = request.form.get('patient_email') or f"{phone}@spherixclinic.local"
                age = request.form.get('patient_age')
                gender = request.form.get('patient_gender')
                blood_group = request.form.get('blood_group', 'Not Specified')
                address = request.form.get('address', '')
                allergies = request.form.get('allergies', '')
                medical_history = request.form.get('medical_history', '')
                emergency_contact = request.form.get('emergency_contact', '')
                
                next_p_num = TEMP_DATA['next_ids']['patient']
                new_id = f"PAT/{datetime.now().year}/{next_p_num:03d}"
                TEMP_DATA['next_ids']['patient'] += 1
                
                new_patient = Patient(
                    id=new_id,
                    name=name,
                    email=email,
                    password=generate_password_hash("Patient@123", method='pbkdf2:sha256:260000'),
                    age=age,
                    gender=gender,
                    phone=phone,
                    address=address,
                    clinical_record={
                        'blood_group': blood_group,
                        'allergies': allergies,
                        'medical_history': medical_history,
                        'emergency_contact': emergency_contact
                    }
                )
                TEMP_DATA['patients'][new_id] = new_patient
                
                # Check if also creating appointment
                doctor_id = request.form.get('doctor_id')
                token_num = "TK-01"
                if doctor_id:
                    parsed_doc_id = parse_route_id(doctor_id)
                    if parsed_doc_id not in hospital_doctor_ids:
                        flash(f"Access Denied: You can only book appointments with doctors affiliated with your hospital ({hospital_name}).", "error")
                        return redirect(url_for('staff_reception_dashboard'))

                    appt_id = TEMP_DATA['next_ids']['appointment']
                    date_str = request.form.get('appointment_date') or datetime.now().strftime('%Y-%m-%d')
                    time_str = request.form.get('appointment_time') or datetime.now().strftime('%H:%M')
                    reason = request.form.get('reason', 'General Consultation')
                    priority = request.form.get('priority', 'normal')
                    
                    doc_today_appts = [
                        a for a in TEMP_DATA['appointments'].values() 
                        if str(a.appointment_date) == date_str and (not doctor_id or str(a.doctor_id) == str(doctor_id))
                    ]
                    token_num = f"TK-{len(doc_today_appts) + 1:02d}"
                    
                    new_appt = Appointment(
                        id=appt_id,
                        patient_name=name,
                        doctor_id=doctor_id,
                        appointment_date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                        appointment_time=datetime.strptime(time_str, '%H:%M').time(),
                        patient_phone=phone,
                        patient_id=new_id,
                        reason=reason,
                        status='confirmed'
                    )
                    new_appt.token_no = token_num
                    new_appt.priority = priority
                    new_appt.queue_status = 'waiting'
                    new_appt.vitals = {
                        'bp': request.form.get('bp', ''),
                        'pulse': request.form.get('pulse', ''),
                        'temp': request.form.get('temp', ''),
                        'spo2': request.form.get('spo2', ''),
                        'weight': request.form.get('weight', ''),
                        'allergies': allergies
                    }
                    try:
                        new_appt.fee_amount = float(request.form.get('fee_amount', 300))
                    except Exception:
                        new_appt.fee_amount = 300.0
                    new_appt.payment_mode = request.form.get('payment_mode', 'Cash')
                    new_appt.payment_status = request.form.get('payment_status', 'paid')
                    
                    TEMP_DATA['appointments'][appt_id] = new_appt
                    TEMP_DATA['next_ids']['appointment'] += 1

                    # Create welcome message from Doctor to Patient
                    doc_obj = TEMP_DATA['doctors'].get(parsed_doc_id)
                    doc_name = f"Dr. {doc_obj.first_name} {doc_obj.last_name}" if doc_obj else "Attending Physician"
                    msg_id = max([0] + [int(k) for k in TEMP_DATA.get('messages', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['messages'][msg_id] = Message(
                        id=msg_id,
                        doctor_id=doctor_id,
                        patient_id=new_id,
                        sender='doctor',
                        content=f"Hello {name}, welcome to Spherix Clinic! I have been assigned as your attending physician for Token #{token_num}. Please feel free to message here for any prescription clarification or follow-up advice."
                    )
                    
                    # Create notification for patient
                    notif_id = max([0] + [int(k) for k in TEMP_DATA.get('notifications', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['notifications'][notif_id] = Notification(
                        id=notif_id,
                        user_id=new_id,
                        user_type='patient',
                        message=f"Your consultation with {doc_name} is scheduled for Token #{token_num} ({getattr(doc_obj, 'opd_room', 'Room 101')}).",
                        link=url_for('patient_dashboard'),
                        status='unread',
                        created_at=utcnow()
                    )

                # Save vitals to patient_vitals for telemetry charts
                if request.form.get('bp') or request.form.get('pulse') or request.form.get('weight'):
                    v_id = max([0] + [int(k) for k in TEMP_DATA.get('patient_vitals', {}).keys() if str(k).isdigit()]) + 1
                    bp_val = request.form.get('bp', '')
                    sys_bp = int(bp_val.split('/')[0]) if '/' in bp_val and bp_val.split('/')[0].isdigit() else None
                    dia_bp = int(bp_val.split('/')[1]) if '/' in bp_val and bp_val.split('/')[1].isdigit() else None
                    pulse_val = int(request.form.get('pulse')) if request.form.get('pulse', '').isdigit() else None
                    weight_val = float(request.form.get('weight')) if request.form.get('weight', '').replace('.','',1).isdigit() else None
                    TEMP_DATA['patient_vitals'][v_id] = PatientVital(
                        id=v_id,
                        patient_id=new_id,
                        weight=weight_val,
                        heart_rate=pulse_val,
                        systolic_bp=sys_bp,
                        diastolic_bp=dia_bp,
                        recorded_at=utcnow()
                    )
                
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="New Patient Registered",
                    details=f"Registered patient {name} (ID: {new_id}, Phone: {phone})."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f'Patient {name} registered! Assigned Patient ID: {new_id} • Password: Patient@123 (Login using Phone: {phone} or ID: {new_id})', 'success')
            except Exception as e:
                flash(f'Error registering patient: {str(e)}', 'error')
        elif 'update_doctor_roster' in request.form:
            doc_id = parse_route_id(request.form.get('doctor_id'))
            if doc_id not in hospital_doctor_ids:
                flash(f"Access Denied: You can only manage rosters for doctors affiliated with your hospital ({hospital_name}).", "error")
                return redirect(url_for('staff_reception_dashboard'))
            doc = TEMP_DATA['doctors'].get(doc_id)
            if doc:
                doc.roster_status = request.form.get('roster_status', 'Available')
                doc.opd_room = request.form.get('opd_room', 'Room 101')
                save_data()
                flash(f'Dr. {doc.first_name} {doc.last_name} roster updated to {doc.roster_status} ({doc.opd_room}).', 'success')
        elif 'book_walkin' in request.form:
            try:
                appt_id = TEMP_DATA['next_ids']['appointment']
                patient_name = request.form.get('patient_name')
                patient_phone = (request.form.get('patient_phone') or '').strip()
                doctor_id = request.form.get('doctor_id')
                date_str = request.form.get('appointment_date')
                time_str = request.form.get('appointment_time')
                reason = request.form.get('reason', 'Walk-in Consultation')
                priority = request.form.get('priority', 'normal')

                if doctor_id:
                    parsed_doc_id = parse_route_id(doctor_id)
                    if parsed_doc_id not in hospital_doctor_ids:
                        flash(f"Access Denied: You can only book appointments with doctors affiliated with your hospital ({hospital_name}).", "error")
                        return redirect(url_for('staff_reception_dashboard'))
                
                # Check if patient exists or auto-create account
                patient_match = next((p for p in TEMP_DATA['patients'].values() if p.phone and p.phone.strip() == patient_phone), None)
                if patient_match:
                    assigned_pat_id = patient_match.id
                else:
                    # Auto-register patient record so they can immediately log in
                    next_p_num = TEMP_DATA['next_ids']['patient']
                    assigned_pat_id = f"PAT/{datetime.now().year}/{next_p_num:03d}"
                    TEMP_DATA['next_ids']['patient'] += 1
                    new_pat_obj = Patient(
                        id=assigned_pat_id,
                        name=patient_name,
                        email=f"{patient_phone}@spherixclinic.local",
                        password=generate_password_hash("Patient@123", method='pbkdf2:sha256:260000'),
                        phone=patient_phone,
                        clinical_record={'blood_group': 'Not Specified', 'allergies': request.form.get('allergies', '')}
                    )
                    TEMP_DATA['patients'][assigned_pat_id] = new_pat_obj

                # Auto-generate Token for Today
                doc_today_appts = [
                    a for a in TEMP_DATA['appointments'].values() 
                    if str(a.appointment_date) == date_str and (not doctor_id or str(a.doctor_id) == str(doctor_id))
                ]
                token_num = f"TK-{len(doc_today_appts) + 1:02d}"

                new_appt = Appointment(
                    id=appt_id,
                    patient_name=patient_name,
                    doctor_id=doctor_id,
                    appointment_date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    appointment_time=datetime.strptime(time_str, '%H:%M').time(),
                    patient_phone=patient_phone,
                    reason=reason,
                    status='confirmed'
                )
                new_appt.patient_id = assigned_pat_id
                new_appt.token_no = token_num
                new_appt.priority = priority
                new_appt.queue_status = 'waiting'
                
                # Vitals
                new_appt.vitals = {
                    'bp': request.form.get('bp', ''),
                    'pulse': request.form.get('pulse', ''),
                    'temp': request.form.get('temp', ''),
                    'spo2': request.form.get('spo2', ''),
                    'weight': request.form.get('weight', ''),
                    'allergies': request.form.get('allergies', '')
                }
                
                # Billing
                try:
                    new_appt.fee_amount = float(request.form.get('fee_amount', 300))
                except Exception:
                    new_appt.fee_amount = 300.0
                new_appt.payment_mode = request.form.get('payment_mode', 'Cash')
                new_appt.payment_status = request.form.get('payment_status', 'paid')

                TEMP_DATA['appointments'][appt_id] = new_appt
                TEMP_DATA['next_ids']['appointment'] += 1

                # Save vitals to patient_vitals for telemetry charts
                if request.form.get('bp') or request.form.get('pulse') or request.form.get('weight'):
                    v_id = max([0] + [int(k) for k in TEMP_DATA.get('patient_vitals', {}).keys() if str(k).isdigit()]) + 1
                    bp_val = request.form.get('bp', '')
                    sys_bp = int(bp_val.split('/')[0]) if '/' in bp_val and bp_val.split('/')[0].isdigit() else None
                    dia_bp = int(bp_val.split('/')[1]) if '/' in bp_val and bp_val.split('/')[1].isdigit() else None
                    pulse_val = int(request.form.get('pulse')) if request.form.get('pulse', '').isdigit() else None
                    weight_val = float(request.form.get('weight')) if request.form.get('weight', '').replace('.','',1).isdigit() else None
                    TEMP_DATA['patient_vitals'][v_id] = PatientVital(
                        id=v_id,
                        patient_id=assigned_pat_id,
                        weight=weight_val,
                        heart_rate=pulse_val,
                        systolic_bp=sys_bp,
                        diastolic_bp=dia_bp,
                        recorded_at=utcnow()
                    )

                # Create welcome message from Doctor to Patient
                if doctor_id:
                    doc_obj = TEMP_DATA['doctors'].get(doctor_id)
                    doc_name = f"Dr. {doc_obj.first_name} {doc_obj.last_name}" if doc_obj else "Attending Physician"
                    msg_id = max([0] + [int(k) for k in TEMP_DATA.get('messages', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['messages'][msg_id] = Message(
                        id=msg_id,
                        doctor_id=doctor_id,
                        patient_id=assigned_pat_id,
                        sender='doctor',
                        content=f"Hello {patient_name}, welcome to Spherix Clinic! I am your attending physician for Token #{token_num}. You can view your prescription, medical telemetry, or message me here anytime."
                    )
                    
                    # Create notification for patient
                    notif_id = max([0] + [int(k) for k in TEMP_DATA.get('notifications', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['notifications'][notif_id] = Notification(
                        id=notif_id,
                        user_id=assigned_pat_id,
                        user_type='patient',
                        message=f"Walk-in consultation token #{token_num} registered with {doc_name} ({getattr(doc_obj, 'opd_room', 'Room 101')}).",
                        link=url_for('patient_dashboard'),
                        status='unread',
                        created_at=utcnow()
                    )
                
                # Log activity
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Walk-in Registered",
                    details=f"Token {token_num} | Walk-in {patient_name} ({priority.upper()}) registered."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f'Walk-in registered! Assigned Token: {token_num}.', 'success')
            except Exception as e:
                flash(f'Error registering walk-in: {str(e)}', 'error')
        elif 'direct_bed_admission' in request.form:
            try:
                patient_name = request.form.get('patient_name')
                patient_phone = (request.form.get('patient_phone') or '').strip()
                bed_type = request.form.get('bed_type', 'General')
                room_number = request.form.get('room_number', 'Admitted - Reception')
                reason = request.form.get('reason', 'Direct Inpatient Admission via Reception')
                
                # Check if patient exists or auto-register real patient in TEMP_DATA['patients']
                patient_match = next((p for p in TEMP_DATA['patients'].values() if p.phone and p.phone.strip() == patient_phone), None)
                if patient_match:
                    assigned_pat_id = patient_match.id
                else:
                    next_p_num = TEMP_DATA['next_ids']['patient']
                    assigned_pat_id = f"PAT/{datetime.now().year}/{next_p_num:03d}"
                    TEMP_DATA['next_ids']['patient'] += 1
                    new_pat_obj = Patient(
                        id=assigned_pat_id,
                        name=patient_name,
                        email=f"{patient_phone}@spherixclinic.local" if patient_phone else f"patient{next_p_num}@spherixclinic.local",
                        password=generate_password_hash("Patient@123", method='pbkdf2:sha256:260000'),
                        phone=patient_phone,
                        clinical_record={'blood_group': 'Not Specified', 'allergies': ''}
                    )
                    TEMP_DATA['patients'][assigned_pat_id] = new_pat_obj
                
                if bed_type == 'ICU':
                    if hospital.available_icu_beds <= 0:
                        flash('No ICU beds available!', 'error')
                        return redirect(url_for('staff_reception_dashboard'))
                    hospital.available_icu_beds -= 1
                else:
                    if hospital.available_beds <= 0:
                        flash('No General beds available!', 'error')
                        return redirect(url_for('staff_reception_dashboard'))
                    hospital.available_beds -= 1
                    
                booking_id = max([0] + [int(k) for k in TEMP_DATA.get('bed_bookings', {}).keys() if str(k).isdigit()]) + 1

                # Sync with beds inventory in TEMP_DATA['beds']
                matched_bed = None
                for b in TEMP_DATA.get('beds', {}).values():
                    if str(b.get('hospital_id', '')) == str(hospital.id):
                        if room_number and (b.get('bed_id') == room_number or b.get('room_number') == room_number):
                            matched_bed = b
                            break
                        elif not matched_bed and b.get('status') == 'Available' and (
                            (bed_type == 'ICU' and b.get('bed_type') == 'ICU') or 
                            (bed_type != 'ICU' and b.get('bed_type') != 'ICU')
                        ):
                            matched_bed = b

                if matched_bed:
                    matched_bed['status'] = 'Occupied'
                    matched_bed['patient_name'] = patient_name
                    matched_bed['booking_id'] = booking_id
                    room_number = matched_bed.get('bed_id') or matched_bed.get('room_number') or room_number

                new_booking = BedBooking(
                    id=booking_id,
                    hospital_id=hospital.id,
                    patient_id=assigned_pat_id,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    bed_type=bed_type,
                    reason=reason,
                    status='approved',
                    room_number=room_number
                )
                if 'bed_bookings' not in TEMP_DATA:
                    TEMP_DATA['bed_bookings'] = {}
                TEMP_DATA['bed_bookings'][booking_id] = new_booking
                
                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Reception Direct Bed Admission",
                    details=f"Admitted patient {patient_name} directly to {bed_type} Bed ({room_number}). Transferred to Nursing Station."
                )
                save_data()
                flash(f"Patient {patient_name} admitted directly to {bed_type} Bed ({room_number})! Nursing and Bed Management stations updated in real-time.", "success")
            except Exception as e:
                flash(f"Error admitting patient to bed: {str(e)}", "error")
            return redirect(url_for('staff_reception_dashboard'))
        elif 'request_emergency_blood' in request.form:
            try:
                patient_name = request.form.get('patient_name')
                blood_group = request.form.get('blood_group')
                units = int(request.form.get('units', 1))
                urgency = request.form.get('urgency', 'Stat / Emergency')
                
                if 'blood_requests' not in TEMP_DATA:
                    TEMP_DATA['blood_requests'] = {}
                req_id = max([0] + [int(k) for k in TEMP_DATA['blood_requests'].keys() if str(k).isdigit()]) + 1
                TEMP_DATA['blood_requests'][req_id] = {
                    'id': req_id,
                    'hospital_id': hospital.id,
                    'patient_name': patient_name,
                    'blood_group': blood_group,
                    'units': units,
                    'urgency': urgency,
                    'status': 'pending',
                    'requested_by': f"{current_user.name} (Reception)",
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
                }

                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Emergency Blood Requisition",
                    details=f"Reception Emergency Requisition: {units} units of {blood_group} for {patient_name} ({urgency})."
                )
                save_data()
                flash(f"Emergency requisition for {units} units of {blood_group} blood sent to Blood Bank Management.", "warning")
            except Exception as e:
                flash(f"Error requesting blood: {str(e)}", "error")
            return redirect(url_for('staff_reception_dashboard'))
        elif 'add_organ_request' in request.form:
            try:
                patient_name = request.form.get('patient_name')
                organ_needed = request.form.get('organ_needed')
                blood_group = request.form.get('blood_group')
                urgency = request.form.get('urgency', 'Standard')
                
                req_id = max([0] + [int(k) for k in TEMP_DATA.get('organ_requests', {}).keys() if str(k).isdigit()]) + 1
                new_req = OrganRequest(
                    id=req_id,
                    patient_id='walkin',
                    patient_name=patient_name,
                    organ_needed=organ_needed,
                    blood_group=blood_group,
                    urgency=urgency,
                    status='active',
                    hospital_id=hospital.id
                )
                if 'organ_requests' not in TEMP_DATA:
                    TEMP_DATA['organ_requests'] = {}
                TEMP_DATA['organ_requests'][req_id] = new_req
                
                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Organ Request Registered",
                    details=f"Reception registered organ recipient request for {organ_needed} ({blood_group}) for {patient_name}."
                )
                save_data()
                flash(f"Organ recipient request for {organ_needed} ({blood_group}) registered with Organ Donor Management.", "success")
            except Exception as e:
                flash(f"Error registering organ request: {str(e)}", "error")
            return redirect(url_for('staff_reception_dashboard'))
        elif 'update_hospital_profile' in request.form:
            try:
                hospital.phone = request.form.get('phone', hospital.phone)
                hospital.email = request.form.get('email', hospital.email)
                hospital.address = request.form.get('address', hospital.address)
                
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Hospital Profile Updated",
                    details=f"Updated hospital phone: {hospital.phone}, email: {hospital.email}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash('Hospital details updated successfully.', 'success')
            except Exception as e:
                flash(f'Error updating hospital details: {str(e)}', 'error')
        return redirect(url_for('staff_reception_dashboard'))
    
    hospital_name_clean = (hospital_name or '').strip().lower()
    hospital_id_str = str(hospital.id) if hospital and hasattr(hospital, 'id') else ''
    
    # Strictly match doctors belonging to this hospital - zero cross-hospital leakage
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if (hospital_name_clean and (getattr(d, 'hospital_name', '') or '').strip().lower() == hospital_name_clean) or
           (hospital_id_str and str(getattr(d, 'hospital_id', '')) == hospital_id_str)
    ]
    doctor_ids = {d.id for d in hospital_doctors}
    hospital_appointments = [a for a in TEMP_DATA['appointments'].values() if parse_route_id(a.doctor_id) in doctor_ids]
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)

    hospital_doctors = deduplicate_entities(hospital_doctors)
    departments_with_doctors = {}
    for doc in hospital_doctors:
        dept = doc.department or 'General Medicine'
        if dept not in departments_with_doctors:
            departments_with_doctors[dept] = []
        departments_with_doctors[dept].append(doc)
    hospital_departments = sorted(departments_with_doctors.keys())
    
    # All registered patients in the system (most recent first)
    all_patients = deduplicate_entities(list(TEMP_DATA.get('patients', {}).values()))
    all_patients.sort(key=lambda p: str(getattr(p, 'id', '')), reverse=True)
    
    # Hospital visitor passes
    hospital_passes = [
        p for p in TEMP_DATA.get('visitor_passes', {}).values() 
        if not hospital or str(p.get('hospital_id', '')) == str(hospital.id)
    ]
    hospital_passes.sort(key=lambda x: x.get('issued_at', datetime.min), reverse=True)

    # Interconnected cross-department data
    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if hospital and str(b.hospital_id) == str(hospital.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)
    blood_stock = hospital.blood_stock if hospital and hasattr(hospital, 'blood_stock') else TEMP_DATA.get('blood_stock', {})
    organ_requests = [r for r in TEMP_DATA.get('organ_requests', {}).values() if hospital and r.hospital_id == hospital.id]
    
    return render_template('staff_reception_dashboard.html', 
                           staff=current_user, hospital=hospital, doctors=hospital_doctors, 
                           departments_with_doctors=departments_with_doctors,
                           departments=hospital_departments,
                           appointments=hospital_appointments, patients=all_patients, 
                           visitor_passes=hospital_passes,
                           bed_bookings=hospital_bed_bookings,
                           blood_stock=blood_stock,
                           organ_requests=organ_requests,
                           activity_logs=activity_logs, today=datetime.now())



@staff_bp.route('/staff/dashboard/beds', methods=['GET', 'POST'])
@staff_role_required('Bed Management')
def staff_bed_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    if request.method == 'POST' and hospital:
        if 'update_beds' in request.form:
            try:
                total = int(request.form.get('total_beds', hospital.total_beds))
                available = int(request.form.get('available_beds', hospital.available_beds))
                icu = int(request.form.get('icu_beds', hospital.icu_beds))
                avail_icu = int(request.form.get('available_icu_beds', hospital.available_icu_beds))
                if available > total or avail_icu > icu:
                    flash('Available beds cannot exceed total capacity.', 'warning')
                else:
                    hospital.total_beds, hospital.available_beds = total, available
                    hospital.icu_beds, hospital.available_icu_beds = icu, avail_icu
                    save_data()
                    flash('Bed inventory updated successfully.', 'success')
            except ValueError:
                flash('Invalid input for bed counts.', 'error')
        elif 'update_bed_charges' in request.form:
            try:
                if 'general_bed_fee' in request.form:
                    hospital.general_bed_fee = float(request.form.get('general_bed_fee', hospital.general_bed_fee))
                if 'icu_bed_fee' in request.form:
                    hospital.icu_bed_fee = float(request.form.get('icu_bed_fee', hospital.icu_bed_fee))
                save_data()
                flash('Bed pricing updated successfully.', 'success')
            except ValueError:
                flash('Invalid input for bed pricing.', 'error')
        elif 'discharge_patient' in request.form:
            booking_id = parse_route_id(request.form.get('booking_id'))
            booking = get_temp_data_item('bed_bookings', booking_id)
            if booking and str(booking.hospital_id) == str(hospital.id) and booking.status in ['approved', 'active']:
                booking.status = 'discharged'
                # Find matching bed in TEMP_DATA['beds'] and transition to 'Cleaning'
                matched_bed = None
                for b in TEMP_DATA.get('beds', {}).values():
                    if str(b.get('hospital_id', '')) == str(hospital.id):
                        if (getattr(booking, 'room_number', None) and (b.get('bed_id') == booking.room_number or b.get('room_number') == booking.room_number)) or \
                           (b.get('patient_name') == booking.patient_name) or \
                           (b.get('booking_id') == booking.id):
                            matched_bed = b
                            break
                if matched_bed:
                    matched_bed['status'] = 'Cleaning'
                    matched_bed['patient_name'] = None
                    matched_bed['booking_id'] = None
                    matched_bed['notes'] = f"Patient {booking.patient_name} discharged. Sanitation and linen reset needed."
                
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Discharged Patient",
                    details=f"Discharged patient {booking.patient_name} from {booking.bed_type} Bed {booking.room_number or 'N/A'}. Bed transitioned to Cleaning status for housekeeping."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash('Patient discharged. Bed has transitioned to Cleaning status for housekeeping sanitization.', 'info')
        elif 'mark_bed_cleaned' in request.form:
            bed_id = request.form.get('bed_id')
            matched_bed = None
            for b in TEMP_DATA.get('beds', {}).values():
                if str(b.get('hospital_id', '')) == str(hospital.id) and (b.get('id') == bed_id or b.get('bed_id') == bed_id):
                    matched_bed = b
                    break
            if matched_bed:
                if matched_bed.get('status') == 'Cleaning':
                    matched_bed['status'] = 'Available'
                    matched_bed['patient_name'] = None
                    matched_bed['booking_id'] = None
                    matched_bed['notes'] = ''
                    if matched_bed.get('bed_type') == 'ICU':
                        hospital.available_icu_beds = min(hospital.icu_beds, hospital.available_icu_beds + 1)
                    else:
                        hospital.available_beds = min(hospital.total_beds, hospital.available_beds + 1)
                    
                    log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                        id=log_id,
                        hospital_id=hospital.id,
                        user_name=current_user.name,
                        action="Bed Sanitized & Cleared",
                        details=f"Housekeeping complete: Bed {matched_bed.get('bed_id', bed_id)} sanitized and marked Available."
                    )
                    save_data()
                    flash(f"Bed {matched_bed.get('bed_id', bed_id)} sanitized and released to Available inventory.", 'success')
                else:
                    flash(f"Bed {matched_bed.get('bed_id', bed_id)} is currently in '{matched_bed.get('status')}' status (not 'Cleaning').", 'warning')
            else:
                flash("Bed not found or access denied.", "error")
        elif 'update_bed_status' in request.form:
            bed_id = request.form.get('bed_id')
            new_status = request.form.get('status', 'Available')
            patient_name_input = request.form.get('patient_name', '').strip()
            
            matched_bed = None
            for b in TEMP_DATA.get('beds', {}).values():
                if str(b.get('hospital_id', '')) == str(hospital.id) and (b.get('id') == bed_id or b.get('bed_id') == bed_id):
                    matched_bed = b
                    break
            if matched_bed:
                old_status = matched_bed.get('status', 'Available')
                is_icu = matched_bed.get('bed_type') == 'ICU'
                
                # Capacity adjustments
                if old_status == 'Available' and new_status != 'Available':
                    if is_icu:
                        hospital.available_icu_beds = max(0, hospital.available_icu_beds - 1)
                    else:
                        hospital.available_beds = max(0, hospital.available_beds - 1)
                elif old_status != 'Available' and new_status == 'Available':
                    if is_icu:
                        hospital.available_icu_beds = min(hospital.icu_beds, hospital.available_icu_beds + 1)
                    else:
                        hospital.available_beds = min(hospital.total_beds, hospital.available_beds + 1)
                
                matched_bed['status'] = new_status
                if new_status == 'Occupied':
                    if patient_name_input:
                        matched_bed['patient_name'] = patient_name_input
                elif new_status == 'Available':
                    matched_bed['patient_name'] = None
                    matched_bed['booking_id'] = None
                    matched_bed['notes'] = ''
                
                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Bed Status Updated",
                    details=f"Bed {matched_bed.get('bed_id', bed_id)} status transitioned from '{old_status}' to '{new_status}'."
                )
                save_data()
                flash(f"Bed {matched_bed.get('bed_id', bed_id)} updated to {new_status}.", 'success')
            else:
                flash("Bed not found or access denied.", "error")
        elif 'allocate_bed_directly' in request.form:
            try:
                patient_name = request.form.get('patient_name')
                patient_phone = request.form.get('patient_phone')
                bed_type = request.form.get('bed_type', 'General')
                room_number = request.form.get('room_number', 'N/A')
                reason = request.form.get('reason', 'Direct Admission')
                
                if bed_type == 'ICU':
                    if hospital.available_icu_beds <= 0:
                        flash('No available ICU beds!', 'error')
                        return redirect(url_for('staff_bed_dashboard'))
                    hospital.available_icu_beds -= 1
                else:
                    if hospital.available_beds <= 0:
                        flash('No available General beds!', 'error')
                        return redirect(url_for('staff_bed_dashboard'))
                    hospital.available_beds -= 1
                    
                if 'bed_booking' not in TEMP_DATA['next_ids']:
                    TEMP_DATA['next_ids']['bed_booking'] = max([1] + [int(k) for k in TEMP_DATA.get('bed_bookings', {}).keys() if str(k).isdigit()]) + 1
                booking_id = TEMP_DATA['next_ids']['bed_booking']

                # Sync with beds inventory in TEMP_DATA['beds']
                matched_bed = None
                for b in TEMP_DATA.get('beds', {}).values():
                    if str(b.get('hospital_id', '')) == str(hospital.id):
                        if room_number and (b.get('bed_id') == room_number or b.get('room_number') == room_number):
                            matched_bed = b
                            break
                        elif not matched_bed and b.get('status') == 'Available' and (
                            (bed_type == 'ICU' and b.get('bed_type') == 'ICU') or 
                            (bed_type != 'ICU' and b.get('bed_type') != 'ICU')
                        ):
                            matched_bed = b

                if matched_bed:
                    matched_bed['status'] = 'Occupied'
                    matched_bed['patient_name'] = patient_name
                    matched_bed['booking_id'] = booking_id
                    room_number = matched_bed.get('bed_id') or matched_bed.get('room_number') or room_number

                new_booking = BedBooking(
                    id=booking_id,
                    hospital_id=hospital.id,
                    patient_id='walk-in',
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    bed_type=bed_type,
                    reason=reason,
                    status='approved',
                    room_number=room_number
                )
                TEMP_DATA['bed_bookings'][booking_id] = new_booking
                TEMP_DATA['next_ids']['bed_booking'] += 1
                
                if 'activity_log' not in TEMP_DATA['next_ids']:
                    TEMP_DATA['next_ids']['activity_log'] = max([1] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Direct Bed Allocation",
                    details=f"Allocated {bed_type} Bed {room_number} directly to patient {patient_name}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f'Patient directly admitted to {bed_type} Bed {room_number}.', 'success')
            except Exception as e:
                flash(f'Error allocating bed: {str(e)}', 'error')
        elif 'transfer_bed' in request.form:
            try:
                booking_id = parse_route_id(request.form.get('booking_id'))
                new_bed_type = request.form.get('new_bed_type', 'General')
                new_room_number = request.form.get('new_room_number', 'N/A')
                booking = get_temp_data_item('bed_bookings', booking_id)
                if booking and str(booking.hospital_id) == str(hospital.id) and booking.status == 'approved':
                    old_bed_type = booking.bed_type
                    old_room_number = booking.room_number

                    # Transition old bed to Cleaning
                    for b in TEMP_DATA.get('beds', {}).values():
                        if str(b.get('hospital_id', '')) == str(hospital.id) and (
                            b.get('bed_id') == old_room_number or b.get('patient_name') == booking.patient_name
                        ):
                            b['status'] = 'Cleaning'
                            b['patient_name'] = None
                            b['notes'] = f"Transferred to {new_room_number}. Housekeeping needed."
                            break

                    # Transition new bed to Occupied
                    for b in TEMP_DATA.get('beds', {}).values():
                        if str(b.get('hospital_id', '')) == str(hospital.id) and (
                            b.get('bed_id') == new_room_number or b.get('room_number') == new_room_number
                        ):
                            b['status'] = 'Occupied'
                            b['patient_name'] = booking.patient_name
                            b['booking_id'] = booking.id
                            break

                    if old_bed_type != new_bed_type:
                        if new_bed_type == 'ICU':
                            if hospital.available_icu_beds <= 0:
                                flash('No available ICU beds for transfer!', 'error')
                                return redirect(url_for('staff_bed_dashboard'))
                            hospital.available_icu_beds -= 1
                            hospital.available_beds = min(hospital.total_beds, hospital.available_beds + 1)
                        else:
                            if hospital.available_beds <= 0:
                                flash('No available General beds for transfer!', 'error')
                                return redirect(url_for('staff_bed_dashboard'))
                            hospital.available_beds -= 1
                            hospital.available_icu_beds = min(hospital.icu_beds, hospital.available_icu_beds + 1)
                    booking.bed_type = new_bed_type
                    booking.room_number = new_room_number
                    
                    log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                        id=log_id,
                        hospital_id=hospital.id,
                        user_name=current_user.name,
                        action="Bed Transfer",
                        details=f"Transferred patient {booking.patient_name} from {old_bed_type} to {new_bed_type} (Room {new_room_number}). Old bed queued for Cleaning."
                    )
                    save_data()
                    flash(f"Patient {booking.patient_name} transferred to {new_bed_type} Bed (Room {new_room_number}).", "success")
            except Exception as e:
                flash(f"Error transferring bed: {str(e)}", "error")
        return redirect(url_for('staff_bed_dashboard'))

    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if hospital and str(b.hospital_id) == str(hospital.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)

    # Isolated Beds Inventory for this hospital
    hospital_beds = [b for b in TEMP_DATA.get('beds', {}).values() if hospital and str(b.get('hospital_id', '')) == str(hospital.id)]
    hospital_beds.sort(key=lambda x: (x.get('ward', ''), x.get('bed_id', '')))

    # Group beds by ward
    wards = {}
    for b in hospital_beds:
        w_name = b.get('ward', 'General Ward')
        if w_name not in wards:
            wards[w_name] = []
        wards[w_name].append(b)
    
    return render_template('staff_bed_dashboard.html', 
                           staff=current_user, hospital=hospital, 
                           bed_bookings=hospital_bed_bookings,
                           beds=hospital_beds,
                           wards=wards,
                           activity_logs=activity_logs)



@staff_bp.route('/staff/dashboard/nursing', methods=['GET', 'POST'])
@staff_role_required('Nurse', 'Nursing')
def staff_nursing_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    if request.method == 'POST' and hospital:
        if 'record_patient_vitals' in request.form:
            try:
                patient_id = request.form.get('patient_id')
                bp = request.form.get('bp', '')
                pulse = request.form.get('pulse')
                temp = request.form.get('temperature')
                spo2 = request.form.get('spo2')
                sugar = request.form.get('blood_sugar')
                notes = request.form.get('notes', '')
                
                sys_bp = int(bp.split('/')[0]) if '/' in bp and bp.split('/')[0].isdigit() else None
                dia_bp = int(bp.split('/')[1]) if '/' in bp and bp.split('/')[1].isdigit() else None
                pulse_val = int(pulse) if pulse and pulse.isdigit() else None
                sugar_val = float(sugar) if sugar and sugar.replace('.', '', 1).isdigit() else None
                
                v_id = max([0] + [int(k) for k in TEMP_DATA.get('patient_vitals', {}).keys() if str(k).isdigit()]) + 1
                new_vital = PatientVital(
                    id=v_id,
                    patient_id=patient_id,
                    weight=None,
                    heart_rate=pulse_val,
                    blood_sugar=sugar_val,
                    systolic_bp=sys_bp,
                    diastolic_bp=dia_bp,
                    recorded_at=utcnow()
                )
                if 'patient_vitals' not in TEMP_DATA:
                    TEMP_DATA['patient_vitals'] = {}
                TEMP_DATA['patient_vitals'][v_id] = new_vital
                
                # Also record on bed booking if inpatient
                booking_id = request.form.get('booking_id')
                if booking_id:
                    b_id = parse_route_id(booking_id)
                    booking = get_temp_data_item('bed_bookings', b_id)
                    if booking:
                        booking.latest_vitals = {
                            'bp': bp,
                            'pulse': pulse,
                            'temp': temp,
                            'spo2': spo2,
                            'blood_sugar': sugar,
                            'notes': notes,
                            'recorded_at': utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                            'recorded_by': current_user.name
                        }
                
                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Recorded Patient Vitals",
                    details=f"Recorded telemetry vitals (BP: {bp}, Pulse: {pulse} bpm, SpO2: {spo2}%, Temp: {temp}°F) for Patient #{patient_id}."
                )
                
                save_data()
                flash(f"Clinical vitals recorded successfully for Patient #{patient_id}.", "success")
            except Exception as e:
                flash(f"Error recording vitals: {str(e)}", "error")
            return redirect(url_for('staff_nursing_dashboard'))

        elif 'log_medication_dose' in request.form:
            try:
                patient_name = request.form.get('patient_name')
                medicine_name = request.form.get('medicine_name')
                dosage = request.form.get('dosage')
                route = request.form.get('route', 'Oral')
                
                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Administered Medication",
                    details=f"Administered {medicine_name} ({dosage}, via {route}) to Inpatient {patient_name}."
                )
                save_data()
                flash(f"Medication dose for {patient_name} ({medicine_name} - {dosage}) logged in MAR.", "success")
            except Exception as e:
                flash(f"Error logging medication: {str(e)}", "error")
            return redirect(url_for('staff_nursing_dashboard'))

        elif 'update_patient_care_status' in request.form:
            try:
                booking_id = parse_route_id(request.form.get('booking_id'))
                care_status = request.form.get('care_status', 'Stable')
                booking = get_temp_data_item('bed_bookings', booking_id)
                if booking and str(booking.hospital_id) == str(hospital.id):
                    booking.care_status = care_status
                    
                    log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                        id=log_id,
                        hospital_id=hospital.id,
                        user_name=current_user.name,
                        action="Care Acuity Updated",
                        details=f"Updated clinical care acuity for {booking.patient_name} to '{care_status}'."
                    )
                    save_data()
                    flash(f"Care status for {booking.patient_name} updated to '{care_status}'.", "info")
            except Exception as e:
                flash(f"Error updating status: {str(e)}", "error")
            return redirect(url_for('staff_nursing_dashboard'))

        elif 'request_blood_transfusion' in request.form:
            try:
                patient_name = request.form.get('patient_name')
                blood_group = request.form.get('blood_group')
                units = int(request.form.get('units', 1))
                urgency = request.form.get('urgency', 'Stat / Emergency')
                
                if 'blood_requests' not in TEMP_DATA:
                    TEMP_DATA['blood_requests'] = {}
                req_id = max([0] + [int(k) for k in TEMP_DATA['blood_requests'].keys() if str(k).isdigit()]) + 1
                TEMP_DATA['blood_requests'][req_id] = {
                    'id': req_id,
                    'hospital_id': hospital.id,
                    'patient_name': patient_name,
                    'blood_group': blood_group,
                    'units': units,
                    'urgency': urgency,
                    'status': 'pending',
                    'requested_by': f"{current_user.name} (Nurse)",
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
                }

                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Blood Transfusion Request",
                    details=f"Urgent Nursing Requisition: {units} units of {blood_group} for {patient_name} ({urgency})."
                )
                save_data()
                flash(f"Urgent requisition for {units} units of {blood_group} blood dispatched to Blood Bank.", "warning")
            except Exception as e:
                flash(f"Error requesting blood: {str(e)}", "error")
            return redirect(url_for('staff_nursing_dashboard'))

        elif 'discharge_inpatient' in request.form:
            try:
                booking_id = parse_route_id(request.form.get('booking_id'))
                booking = get_temp_data_item('bed_bookings', booking_id)
                if booking and str(booking.hospital_id) == str(hospital.id) and booking.status in ['approved', 'active']:
                    booking.status = 'discharged'
                    # Put matching bed into 'Cleaning'
                    for bed in TEMP_DATA.get('beds', {}).values():
                        if str(bed.get('hospital_id', '')) == str(hospital.id) and (
                            bed.get('patient_name') == booking.patient_name or
                            bed.get('bed_id') == booking.room_number or
                            bed.get('id') == booking.room_number
                        ):
                            bed['status'] = 'Cleaning'
                            bed['patient_name'] = None
                            bed['booking_id'] = None
                            bed['notes'] = f"Discharged by Nurse {current_user.name}. Sanitation requested."
                            break
                    log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                    TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                        id=log_id,
                        hospital_id=hospital.id,
                        user_name=current_user.name,
                        action="Inpatient Nursing Discharge",
                        details=f"Clinical nursing discharge clearance issued for {booking.patient_name}. Bed transferred to Housekeeping for Cleaning."
                    )
                    save_data()
                    flash(f"Inpatient {booking.patient_name} clinically cleared and discharged. Bed queued for housekeeping cleaning.", "success")
            except Exception as e:
                flash(f"Error discharging inpatient: {str(e)}", "error")
            return redirect(url_for('staff_nursing_dashboard'))

        elif 'transfer_inpatient' in request.form:
            try:
                booking_id = parse_route_id(request.form.get('booking_id'))
                new_bed_type = request.form.get('new_bed_type', 'General')
                new_room = request.form.get('new_room_number', 'N/A')
                booking = get_temp_data_item('bed_bookings', booking_id)
                if booking and str(booking.hospital_id) == str(hospital.id):
                    old_type = booking.bed_type
                    old_room = booking.room_number

                    # Transition old bed to Cleaning
                    for b in TEMP_DATA.get('beds', {}).values():
                        if str(b.get('hospital_id', '')) == str(hospital.id) and (
                            b.get('bed_id') == old_room or b.get('patient_name') == booking.patient_name
                        ):
                            b['status'] = 'Cleaning'
                            b['patient_name'] = None
                            b['notes'] = f"Transferred to {new_room}. Housekeeping needed."
                            break

                    # Transition new bed to Occupied
                    for b in TEMP_DATA.get('beds', {}).values():
                        if str(b.get('hospital_id', '')) == str(hospital.id) and (
                            b.get('bed_id') == new_room or b.get('room_number') == new_room
                        ):
                            b['status'] = 'Occupied'
                            b['patient_name'] = booking.patient_name
                            b['booking_id'] = booking.id
                            break

                    if old_type != new_bed_type:
                        if new_bed_type == 'ICU':
                            if hospital.available_icu_beds <= 0:
                                flash('No available ICU beds!', 'error')
                                return redirect(url_for('staff_nursing_dashboard'))
                            hospital.available_icu_beds -= 1
                            hospital.available_beds = min(hospital.total_beds, hospital.available_beds + 1)
                        else:
                            if hospital.available_beds <= 0:
                                flash('No available General beds!', 'error')
                                return redirect(url_for('staff_nursing_dashboard'))
                            hospital.available_beds -= 1
                            hospital.available_icu_beds = min(hospital.icu_beds, hospital.available_icu_beds + 1)
                    booking.bed_type = new_bed_type
                    booking.room_number = new_room
                    save_data()
                    flash(f"Inpatient {booking.patient_name} transferred to {new_bed_type} Bed ({new_room}).", "success")
            except Exception as e:
                flash(f"Error transferring inpatient: {str(e)}", "error")
            return redirect(url_for('staff_nursing_dashboard'))

    # Load active hospital inpatients (General & ICU)
    hospital_inpatients = [
        b for b in TEMP_DATA.get('bed_bookings', {}).values() 
        if hospital and str(b.hospital_id) == str(hospital.id) and b.status in ['approved', 'active']
    ]
    hospital_inpatients.sort(key=lambda x: (0 if x.bed_type == 'ICU' else 1, x.room_number or 'ZZZ'))
    
    blood_stock = hospital.blood_stock if hospital and hasattr(hospital, 'blood_stock') and isinstance(hospital.blood_stock, dict) else TEMP_DATA.get('blood_stock', {})
    
    return render_template('staff_nursing_dashboard.html',
                           staff=current_user, hospital=hospital,
                           inpatients=hospital_inpatients,
                           blood_stock=blood_stock,
                           activity_logs=activity_logs)



@staff_bp.route('/api/staff/reception/live-stats')
@staff_required
def staff_reception_live_stats():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    today = date.today()
    
    hospital_name_clean = (hospital_name or '').strip().lower()
    hospital_id_str = str(hospital.id) if hospital and hasattr(hospital, 'id') else ''
    
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if (hospital_name_clean and (getattr(d, 'hospital_name', '') or '').strip().lower() == hospital_name_clean) or
           (hospital_id_str and str(getattr(d, 'hospital_id', '')) == hospital_id_str)
    ]
    doctor_ids = {d.id for d in hospital_doctors}
    hospital_appointments = [a for a in TEMP_DATA['appointments'].values() if parse_route_id(a.doctor_id) in doctor_ids]
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    
    hospital_passes = [
        p for p in TEMP_DATA.get('visitor_passes', {}).values() 
        if not hospital or str(p.get('hospital_id', '')) == str(hospital.id)
    ]
    hospital_passes.sort(key=lambda x: x.get('issued_at', datetime.min), reverse=True)
    
    blood_stock = hospital.blood_stock if hospital and hasattr(hospital, 'blood_stock') and isinstance(hospital.blood_stock, dict) else TEMP_DATA.get('blood_stock', {})
    
    serialized_appointments = []
    for a in hospital_appointments[:50]:
        doc = TEMP_DATA['doctors'].get(a.doctor_id)
        pat = TEMP_DATA['patients'].get(a.patient_id) if getattr(a, 'patient_id', None) else None
        serialized_appointments.append({
            "id": a.id,
            "patient_name": a.patient_name,
            "patient_phone": getattr(a, 'patient_phone', None) or (pat.phone if pat else "N/A"),
            "patient_age": str(getattr(a, 'patient_age', None) or (pat.age if pat and getattr(pat, 'age', None) else "N/A")),
            "doctor_name": f"Dr. {doc.first_name} {doc.last_name}" if doc else "N/A",
            "doctor_dept": doc.department if doc else "General",
            "date": a.appointment_date.strftime('%b %d, %Y') if a.appointment_date else "N/A",
            "time": a.appointment_time.strftime('%I:%M %p') if a.appointment_time else "N/A",
            "reason": a.reason or "OPD Consultation",
            "status": a.status,
            "queue_status": getattr(a, 'queue_status', 'waiting'),
            "token_no": getattr(a, 'token_no', f"TK-{a.id:02d}"),
            "priority": getattr(a, 'priority', 'normal')
        })
        
    return jsonify({
        "success": True,
        "stats": {
            "total_appointments": len(hospital_appointments),
            "today_appointments_count": len([a for a in hospital_appointments if a.appointment_date == today]),
            "waiting_count": len([a for a in hospital_appointments if a.appointment_date == today and getattr(a, 'queue_status', 'waiting') == 'waiting']),
            "in_consultation_count": len([a for a in hospital_appointments if a.appointment_date == today and getattr(a, 'queue_status', '') == 'in_consultation']),
            "completed_count": len([a for a in hospital_appointments if a.appointment_date == today and (a.status == 'completed' or getattr(a, 'queue_status', '') == 'completed')]),
            "active_visitor_passes": len([p for p in hospital_passes if p.get('status') == 'active']),
            "available_beds": getattr(hospital, 'available_beds', 0) if hospital else 0,
            "available_icu_beds": getattr(hospital, 'available_icu_beds', 0) if hospital else 0,
            "total_blood_units": sum(blood_stock.values()) if isinstance(blood_stock, dict) else 0
        },
        "appointments": serialized_appointments,
        "visitor_passes": hospital_passes[:15]
    })



@staff_bp.route('/api/staff/beds/live-stats')
@staff_required
def staff_beds_live_stats():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if hospital and str(b.hospital_id) == str(hospital.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)
    
    total_beds = getattr(hospital, 'total_beds', 50) if hospital else 50
    available_beds = getattr(hospital, 'available_beds', 40) if hospital else 40
    icu_beds = getattr(hospital, 'icu_beds', 10) if hospital else 10
    available_icu = getattr(hospital, 'available_icu_beds', 8) if hospital else 8
    
    occupied_general = max(0, total_beds - available_beds)
    occupied_icu = max(0, icu_beds - available_icu)
    total_capacity = total_beds + icu_beds
    occupancy_percent = round(((occupied_general + occupied_icu) / total_capacity * 100)) if total_capacity > 0 else 0
    
    # Beds list
    hospital_beds = [b for b in TEMP_DATA.get('beds', {}).values() if hospital and str(b.get('hospital_id', '')) == str(hospital.id)]
    cleaning_count = len([b for b in hospital_beds if b.get('status') == 'Cleaning'])
    occupied_beds_count = len([b for b in hospital_beds if b.get('status') == 'Occupied'])
    available_beds_count = len([b for b in hospital_beds if b.get('status') == 'Available'])
    reserved_beds_count = len([b for b in hospital_beds if b.get('status') == 'Reserved'])

    serialized_beds = [
        {
            "id": b.get("id"),
            "bed_id": b.get("bed_id"),
            "ward": b.get("ward"),
            "floor": b.get("floor"),
            "bed_type": b.get("bed_type"),
            "status": b.get("status"),
            "patient_name": b.get("patient_name", ""),
            "notes": b.get("notes", "")
        }
        for b in hospital_beds
    ]

    serialized_bed_bookings = []
    for b in hospital_bed_bookings:
        created_at_val = getattr(b, 'created_at', None)
        created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M') if hasattr(created_at_val, 'strftime') else str(created_at_val or '')
        serialized_bed_bookings.append({
            "id": b.id,
            "patient_name": b.patient_name,
            "patient_phone": getattr(b, 'patient_phone', "N/A"),
            "bed_type": b.bed_type,
            "room_number": b.room_number or "N/A",
            "reason": b.reason or "Inpatient Admission",
            "status": b.status,
            "care_status": getattr(b, 'care_status', 'Stable'),
            "created_at": created_at_str
        })
        
    return jsonify({
        "success": True,
        "stats": {
            "total_beds": total_beds,
            "available_beds": available_beds,
            "occupied_general_beds": occupied_general,
            "icu_beds": icu_beds,
            "available_icu_beds": available_icu,
            "occupied_icu_beds": occupied_icu,
            "bed_occupancy_percent": occupancy_percent,
            "active_admissions_count": len([b for b in hospital_bed_bookings if b.status in ['approved', 'active']]),
            "cleaning_beds_count": cleaning_count,
            "occupied_beds_count": occupied_beds_count,
            "available_beds_count": available_beds_count,
            "reserved_beds_count": reserved_beds_count
        },
        "bed_bookings": serialized_bed_bookings,
        "beds": serialized_beds
    })



@staff_bp.route('/api/staff/nursing/live-stats')
@staff_required
def staff_nursing_live_stats():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    hospital_inpatients = [
        b for b in TEMP_DATA.get('bed_bookings', {}).values() 
        if hospital and str(b.hospital_id) == str(hospital.id) and b.status in ['approved', 'active']
    ]
    hospital_inpatients.sort(key=lambda x: (0 if x.bed_type == 'ICU' else 1, x.room_number or 'ZZZ'))
    
    blood_stock = hospital.blood_stock if hospital and hasattr(hospital, 'blood_stock') and isinstance(hospital.blood_stock, dict) else TEMP_DATA.get('blood_stock', {})
    
    serialized_inpatients = []
    for b in hospital_inpatients:
        created_at_val = getattr(b, 'created_at', None)
        created_at_str = created_at_val.strftime('%Y-%m-%d %H:%M') if hasattr(created_at_val, 'strftime') else str(created_at_val or '')
        serialized_inpatients.append({
            "id": b.id,
            "patient_name": b.patient_name,
            "patient_phone": getattr(b, 'patient_phone', "N/A"),
            "patient_id": getattr(b, 'patient_id', "N/A"),
            "bed_type": b.bed_type,
            "room_number": b.room_number or "N/A",
            "reason": b.reason or "Admitted Inpatient",
            "status": b.status,
            "care_status": getattr(b, 'care_status', 'Stable'),
            "latest_vitals": getattr(b, 'latest_vitals', None),
            "created_at": created_at_str
        })
        
    return jsonify({
        "success": True,
        "stats": {
            "total_inpatients": len(hospital_inpatients),
            "icu_inpatients": len([b for b in hospital_inpatients if b.bed_type == 'ICU']),
            "general_inpatients": len([b for b in hospital_inpatients if b.bed_type != 'ICU']),
            "critical_cases": len([b for b in hospital_inpatients if getattr(b, 'care_status', '') == 'Critical' or b.bed_type == 'ICU']),
            "available_general_beds": getattr(hospital, 'available_beds', 0) if hospital else 0,
            "available_icu_beds": getattr(hospital, 'available_icu_beds', 0) if hospital else 0
        },
        "inpatients": serialized_inpatients,
        "blood_stock": blood_stock
    })



@staff_bp.route('/staff/dashboard/general', methods=['GET', 'POST'])
@staff_role_required('General Staff', 'Nurse', 'Pharmacist', 'Lab Technician', 'Admin Staff')
def staff_general_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    if request.method == 'POST' and hospital:
        if 'clock_in' in request.form:
            today_str = date.today().isoformat()
            att_key = f"{str(current_user.id).replace('/', '_')}_{today_str}"
            if 'attendance_logs' not in TEMP_DATA:
                TEMP_DATA['attendance_logs'] = {}
            TEMP_DATA['attendance_logs'][att_key] = {
                'staff_id': current_user.id,
                'staff_name': current_user.name,
                'hospital_id': hospital.id,
                'date': today_str,
                'clock_in': datetime.now().strftime('%I:%M %p'),
                'clock_out': None,
                'hours': 0.0,
                'status': 'On Duty'
            }
            current_user.on_duty = True
            log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
            TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                id=log_id,
                hospital_id=hospital.id,
                user_name=current_user.name,
                action="Staff Shift Clock-In",
                details=f"{current_user.name} clocked in for shift duty at {datetime.now().strftime('%I:%M %p')}."
            )
            save_data()
            flash(f"Clocked in successfully at {datetime.now().strftime('%I:%M %p')}. Have a safe & productive shift!", "success")
            return redirect(url_for('staff_general_dashboard'))

        elif 'clock_out' in request.form:
            today_str = date.today().isoformat()
            att_key = f"{str(current_user.id).replace('/', '_')}_{today_str}"
            if 'attendance_logs' in TEMP_DATA and att_key in TEMP_DATA['attendance_logs']:
                att = TEMP_DATA['attendance_logs'][att_key]
                att['clock_out'] = datetime.now().strftime('%I:%M %p')
                att['status'] = 'Completed'
                att['hours'] = 8.0  # standard shift duration
            current_user.on_duty = False
            log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
            TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                id=log_id,
                hospital_id=hospital.id,
                user_name=current_user.name,
                action="Staff Shift Clock-Out",
                details=f"{current_user.name} clocked out of shift duty at {datetime.now().strftime('%I:%M %p')}."
            )
            save_data()
            flash("Clocked out successfully. Thank you for your service today!", "info")
            return redirect(url_for('staff_general_dashboard'))

        elif 'create_task' in request.form:
            title = request.form.get('title')
            description = request.form.get('description', '')
            assigned_to = request.form.get('assigned_to', current_user.name)
            priority = request.form.get('priority', 'Medium')
            due_date = request.form.get('due_date') or date.today().isoformat()

            if 'staff_tasks' not in TEMP_DATA:
                TEMP_DATA['staff_tasks'] = {}
            task_id = max([0] + [int(k) for k in TEMP_DATA['staff_tasks'].keys() if str(k).isdigit()]) + 1
            TEMP_DATA['staff_tasks'][task_id] = {
                'id': task_id,
                'hospital_id': hospital.id,
                'title': title,
                'description': description,
                'assigned_to': assigned_to,
                'priority': priority,
                'due_date': due_date,
                'status': 'Pending',
                'created_by': current_user.name,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
            TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                id=log_id,
                hospital_id=hospital.id,
                user_name=current_user.name,
                action="New Duty Task Created",
                details=f"Created task '{title}' assigned to {assigned_to} (Priority: {priority})."
            )
            save_data()
            flash(f"Duty Task '{title}' assigned successfully.", "success")
            return redirect(url_for('staff_general_dashboard'))

        elif 'update_task_status' in request.form:
            try:
                task_id = int(request.form.get('task_id'))
                new_status = request.form.get('status', 'Pending')
                task = TEMP_DATA.get('staff_tasks', {}).get(task_id)
                if task and str(task.get('hospital_id', '')) == str(hospital.id):
                    old_status = task.get('status', 'Pending')
                    task['status'] = new_status
                    save_data()
                    flash(f"Task #{task_id} status updated from '{old_status}' to '{new_status}'.", "success")
                else:
                    flash("Access Denied: Task not found or belongs to another hospital.", "error")
            except Exception as e:
                flash(f"Error updating task: {str(e)}", "error")
            return redirect(url_for('staff_general_dashboard'))

        elif 'apply_leave' in request.form:
            try:
                leave_type = request.form.get('leave_type', 'Casual Leave')
                start_date_str = request.form.get('start_date')
                end_date_str = request.form.get('end_date')
                reason = request.form.get('reason', '')
                
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                days = max(1, (end_dt - start_dt).days + 1)

                if 'leave_requests' not in TEMP_DATA:
                    TEMP_DATA['leave_requests'] = {}
                leave_id = max([0] + [int(k) for k in TEMP_DATA['leave_requests'].keys() if str(k).isdigit()]) + 1
                TEMP_DATA['leave_requests'][leave_id] = {
                    'id': leave_id,
                    'staff_id': current_user.id,
                    'staff_name': current_user.name,
                    'hospital_id': hospital.id,
                    'leave_type': leave_type,
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'days': days,
                    'reason': reason,
                    'status': 'Pending',
                    'submitted_at': datetime.now().strftime('%Y-%m-%d %H:%M')
                }
                log_id = max([0] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Leave Application Submitted",
                    details=f"{current_user.name} applied for {days} day(s) {leave_type} ({start_date_str} to {end_date_str})."
                )
                save_data()
                flash(f"Leave request for {days} day(s) submitted for management approval.", "success")
            except Exception as e:
                flash(f"Error submitting leave request: {str(e)}", "error")
            return redirect(url_for('staff_general_dashboard'))

        elif 'post_bulletin' in request.form:
            title = request.form.get('title')
            content = request.form.get('content')
            
            bulletin_key = f"bulletins_{hospital.id}"
            bulletins = json.loads(TEMP_DATA['settings'].get(bulletin_key, "[]"))
            bulletins.insert(0, {
                "id": len(bulletins) + 1,
                "title": title,
                "content": content,
                "author": current_user.name,
                "date": datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            TEMP_DATA['settings'][bulletin_key] = json.dumps(bulletins)
            
            log_id = TEMP_DATA['next_ids']['activity_log']
            TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                id=log_id,
                hospital_id=hospital.id,
                user_name=current_user.name,
                action="Posted Bulletin Notice",
                details=f"Posted memo: {title}"
            )
            TEMP_DATA['next_ids']['activity_log'] += 1
            
            save_data()
            flash("Announcement posted to the hospital bulletin board.", "success")
            return redirect(url_for('staff_general_dashboard'))

    bulletin_key = f"bulletins_{hospital.id}" if hospital else ""
    bulletins = []
    if bulletin_key:
        try:
            bulletins = json.loads(TEMP_DATA['settings'].get(bulletin_key, "[]"))
        except Exception:
            bulletins = []

    # Isolated Hospital Staff Tasks
    hospital_tasks = [t for t in TEMP_DATA.get('staff_tasks', {}).values() if hospital and str(t.get('hospital_id', '')) == str(hospital.id)]
    hospital_tasks.sort(key=lambda x: (0 if x.get('status') != 'Completed' else 1, x.get('due_date', '')))

    # Isolated Hospital Leave Requests
    hospital_leaves = [l for l in TEMP_DATA.get('leave_requests', {}).values() if hospital and str(l.get('hospital_id', '')) == str(hospital.id)]
    hospital_leaves.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)

    # Isolated Hospital Attendance Records
    hospital_attendance = [a for a in TEMP_DATA.get('attendance_logs', {}).values() if hospital and str(a.get('hospital_id', '')) == str(hospital.id)]
    hospital_attendance.sort(key=lambda x: x.get('date', ''), reverse=True)

    today_str = date.today().isoformat()
    att_key = f"{str(current_user.id).replace('/', '_')}_{today_str}"
    today_attendance = TEMP_DATA.get('attendance_logs', {}).get(att_key)

    # Isolated Hospital Colleagues
    colleagues = [s for s in TEMP_DATA.get('staff', {}).values() if hospital and str(getattr(s, 'hospital_id', '')) == str(hospital.id)]
    colleagues.sort(key=lambda x: x.name)
            
    return render_template('staff_general_dashboard.html', 
                           staff=current_user, hospital=hospital, 
                           activity_logs=activity_logs, 
                           bulletins=bulletins,
                           tasks=hospital_tasks,
                           leave_requests=hospital_leaves,
                           attendance_logs=hospital_attendance,
                           today_attendance=today_attendance,
                           colleagues=colleagues,
                           today=date.today())




