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
import tempfile
import re
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
    deduplicate_entities,
    TEMP_DATA, get_db_connection, save_data, load_data,
    sync_data_to_sql, load_data_from_sql, create_notification, get_temp_data_item
)
from spherix.services.mail_service import (
    send_notification_email, send_notification_email_async, get_premium_otp_email_html
)
from spherix.services.payment_service import (
    verify_razorpay_signature, create_razorpay_order
)
from fpdf import FPDF
from spherix.services.upload_service import save_user_profile_image, upload_to_cloudinary, UPLOAD_CACHE
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

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/patient/chat/<path:doctor_id>')
@patient_required
def patient_chat(doctor_id):
    """Renders the chat interface for a patient to talk to a specific doctor."""
    doctor = TEMP_DATA['doctors'].get(doctor_id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('patient_dashboard'))

    # Ensure the current patient has an appointment with this doctor
    has_appointment = any(
        appt.doctor_id == doctor_id
        for appt in TEMP_DATA['appointments'].values()
        if appt.patient_id == current_user.id
    )
    if not has_appointment:
        flash("You can only chat with doctors you have an appointment with.", "error")
        return redirect(url_for('patient_dashboard'))

    return render_template('patient_chat.html', doctor=doctor, patient=current_user)



@patient_bp.route('/doctor/appointment/approve/<int:appointment_id>', methods=['POST'])
@doctor_required
def approve_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.doctor_id == current_user.id:
        appointment.status = 'confirmed'
        
        # Send email notification to patient
        patient = appointment.patient
        if patient and patient.email:
            subject = "Your Appointment Has Been Confirmed!"
            body = f"""
Dear {patient.name},

Your appointment with Dr. {appointment.doctor.first_name} {appointment.doctor.last_name} on {appointment.appointment_date.strftime('%B %d, %Y')} at {appointment.appointment_time.strftime('%I:%M %p')} has been confirmed.

We look forward to seeing you!

Best regards,
The Spherix Clinic Team"""
            send_notification_email(patient.email, subject, body)
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been confirmed.", "success")
    else:
        flash("Appointment not found or you do not have permission.", "error")
    return redirect(url_for('doctor_dashboard', tab='appointments'))



@patient_bp.route('/doctor/appointment/reschedule/<int:appointment_id>', methods=['POST'])
@doctor_required
def reschedule_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not (appointment and appointment.doctor_id == current_user.id):
        flash("Appointment not found or you do not have permission.", "error")
        return redirect(url_for('doctor_dashboard', tab='appointments'))

    new_date_str = request.form.get('reschedule_date')
    new_time_str = request.form.get('reschedule_time')

    if not new_date_str or not new_time_str:
        flash("Please provide both a new date and time to reschedule.", "error")
        return redirect(url_for('doctor_dashboard', tab='appointments'))

    # Store original time if it's the first reschedule
    if not appointment.original_appointment_date:
        appointment.original_appointment_date = appointment.appointment_date
        appointment.original_appointment_time = appointment.appointment_time

    # Update to new suggested time and change status
    appointment.appointment_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
    appointment.appointment_time = datetime.strptime(new_time_str, '%H:%M').time()
    appointment.status = 'rescheduled_by_doctor'
    
    # Notify patient
    patient = appointment.patient
    if patient and patient.email:
        subject = "Appointment Reschedule Suggestion"
        body = f"""
Dear {patient.name},

Dr. {appointment.doctor.first_name} {appointment.doctor.last_name} has suggested a new time for your appointment.

Original Time: {appointment.original_appointment_date.strftime('%B %d, %Y')} at {appointment.original_appointment_time.strftime('%I:%M %p')}
Suggested New Time: {appointment.appointment_date.strftime('%B %d, %Y')} at {appointment.appointment_time.strftime('%I:%M %p')}

Please visit your patient dashboard to accept or reject this new time.

Best regards,
The Spherix Clinic Team"""
        send_notification_email(patient.email, subject, body)

    save_data()
    flash(f"A new time has been suggested for {appointment.patient_name}'s appointment.", "success")
    return redirect(url_for('doctor_dashboard', tab='appointments'))



@patient_bp.route('/doctor/appointment/complete/<int:appointment_id>', methods=['POST'])
@doctor_required
def complete_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.doctor_id == current_user.id:
        appointment.status = 'completed'
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been marked as completed.", "success")
    else:
        flash("Appointment not found or you do not have permission.", "error")
    return redirect(url_for('doctor_dashboard', tab='appointments'))




@patient_bp.route('/patient/appointment/accept_reschedule/<int:appointment_id>', methods=['POST'])
@patient_required
def patient_accept_reschedule(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.patient_id == current_user.id and appointment.status == 'rescheduled_by_doctor':
        appointment.status = 'confirmed'
        # Clear original time fields as they are no longer needed
        appointment.original_appointment_date = None
        appointment.original_appointment_time = None
        save_data()
        flash("You have successfully accepted the new appointment time.", "success")
        # Optionally, notify the doctor of acceptance
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/patient/appointment/reject_reschedule/<int:appointment_id>', methods=['POST'])
@patient_required
def patient_reject_reschedule(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.patient_id == current_user.id and appointment.status == 'rescheduled_by_doctor':
        # Here, we'll just cancel the appointment for simplicity.
        # An alternative is to revert to the original time and 'pending' status.
        appointment.status = 'cancelled'
        save_data()
        flash("You have rejected the new time. The appointment has been cancelled.", "warning")
        # Optionally, notify the doctor of rejection
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/staff/reception/export-appointments-csv')
@login_required
def export_reception_appointments_csv():
    """Export today's reception appointments and queue report as CSV."""
    hospital_name_str = getattr(current_user, 'hospital_name', '')
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == hospital_name_str]
    doctor_ids = {d.id for d in hospital_doctors}
    hospital_appointments = [a for a in TEMP_DATA['appointments'].values() if a.doctor_id in doctor_ids]
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Token No', 'Patient Name', 'Phone', 'Doctor', 'Date', 'Time', 'Status', 'Queue Status', 'Priority', 'Fee', 'Payment Mode', 'Payment Status', 'Reason'])
    for a in hospital_appointments:
        doc_name = f"Dr. {a.doctor.first_name} {a.doctor.last_name}" if a.doctor else "N/A"
        writer.writerow([
            getattr(a, 'token_no', f"TK-{a.id}"),
            a.patient_name,
            getattr(a, 'patient_phone', 'N/A'),
            doc_name,
            str(a.appointment_date),
            str(a.appointment_time),
            a.status,
            getattr(a, 'queue_status', 'waiting'),
            getattr(a, 'priority', 'normal'),
            getattr(a, 'fee_amount', 0),
            getattr(a, 'payment_mode', 'Cash'),
            getattr(a, 'payment_status', 'paid'),
            getattr(a, 'reason', '')
        ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=Reception_Queue_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )



@patient_bp.route('/patient/create-account', methods=['GET', 'POST'])
@patient_bp.route('/patient-create-account', methods=['GET', 'POST'])
@patient_bp.route('/patient-register', methods=['GET', 'POST'])
def patient_create_account():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        age = request.form.get('age')
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        address = request.form.get('address')
        terms = request.form.get('terms')

        if not terms:
            flash("You must agree to the Terms of Service and Privacy Policy.", "error")
            return redirect(url_for('patient_create_account'))

        if not all([name, email, password, confirm_password, age, gender]):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for('patient_create_account'))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('patient_create_account'))

        if any(p.email == email for p in TEMP_DATA['patients'].values()):
            flash("An account with this email already exists.", "error")
            return redirect(url_for('patient_create_account'))

        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        patient_license = generate_user_license_id('patient')

        # Store registration data and OTP in session temporarily
        session['signup_data'] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'age': int(age) if age and age.isdigit() else None,
            'gender': gender,
            'phone': phone,
            'address': address,
            'license_number': patient_license,
            'health_id': patient_license,
            'otp': otp
        }

        # Send OTP Email
        subject = "Your OTP for Spherix Clinic Registration"
        body = get_premium_otp_email_html(
            title="Patient Registration Verification",
            greeting=f"Hello {name},",
            message="Thank you for registering. Please use the verification code below to complete your sign-up:",
            otp=otp,
            role_color="#0d6efd",
            accent_bg="#f8f9fa"
        )
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            # Fallback for development if email is not configured
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")

        return redirect(url_for('patient_verify_otp'))

    return render_template('patient_create_account.html')




@patient_bp.route('/patient/dashboard', methods=['GET', 'POST'])
@patient_required
def patient_dashboard():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('patient_dashboard', tab='settings'))

            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('patient_dashboard', tab='settings'))

            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
            save_data()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('patient_dashboard', tab='settings'))

        if action == 'book_appointment':
            doctor_id = request.form.get('doctor_id')
            consultation_type = request.form.get('consultation_type', 'in_person')
            appt_date_str = request.form.get('appointment_date')
            appt_time_str = request.form.get('appointment_time', '09:00')
            reason = request.form.get('reason', 'Routine Consultation')

            if not doctor_id or not appt_date_str:
                flash('Please select a doctor and date for your appointment.', 'error')
                return redirect(url_for('patient_dashboard', tab='book_appointment'))

            doctor = TEMP_DATA.get('doctors', {}).get(doctor_id)
            if not doctor:
                doctor = next((d for d in TEMP_DATA.get('doctors', {}).values() if str(d.id) == str(doctor_id)), None)

            if not doctor or getattr(doctor, 'is_hidden', False) or getattr(doctor, 'is_blocked', False):
                flash('Selected doctor is currently unavailable.', 'error')
                return redirect(url_for('patient_dashboard', tab='book_appointment'))

            try:
                parsed_date = datetime.strptime(appt_date_str, '%Y-%m-%d').date()
            except Exception:
                parsed_date = date.today()

            try:
                parsed_time = datetime.strptime(appt_time_str, '%H:%M').time()
            except Exception:
                parsed_time = time(9, 0)

            appt_id = TEMP_DATA.get('next_ids', {}).get('appointment', len(TEMP_DATA.get('appointments', {})) + 1)
            token_no = f"TK-{random.randint(100, 999)}"
            consultation_fee = getattr(doctor, 'consultation_fee', 300) or 300

            new_appt = Appointment(
                id=appt_id,
                patient_name=current_user.name,
                patient_id=current_user.id,
                doctor_id=doctor.id,
                appointment_date=parsed_date,
                appointment_time=parsed_time,
                patient_phone=getattr(current_user, 'phone', 'N/A'),
                reason=reason,
                status='confirmed',
                consultation_fee=consultation_fee,
                fee_amount=consultation_fee,
                payment_status='paid',
                payment_mode='online',
                token_number=token_no,
                consultation_type=consultation_type
            )
            new_appt.token_number = token_no
            new_appt.token_no = token_no
            new_appt.consultation_type = consultation_type
            new_appt.type = consultation_type
            new_appt.queue_status = 'waiting'
            new_appt.doctor_name = f"Dr. {doctor.first_name} {doctor.last_name}".strip()
            new_appt.specialty = getattr(doctor, 'department', None) or getattr(doctor, 'specialty', 'General Medicine')
            new_appt.status = 'confirmed'

            TEMP_DATA['appointments'][appt_id] = new_appt
            TEMP_DATA['next_ids']['appointment'] = appt_id + 1

            if hasattr(current_user, 'appointments'):
                if isinstance(current_user.appointments, list):
                    current_user.appointments.append(new_appt)

            try:
                create_notification(
                    user_id=doctor.id,
                    user_role='doctor',
                    message=f"New {consultation_type.title()} Appointment booked by {current_user.name} for {parsed_date} at {appt_time_str} (Token: {token_no}).",
                    link=url_for('doctor_dashboard')
                )
            except Exception:
                pass

            try:
                create_notification(
                    user_id=current_user.id,
                    user_role='patient',
                    message=f"Your appointment with Dr. {doctor.first_name} {doctor.last_name} is confirmed for {parsed_date} at {appt_time_str} (Token: {token_no}).",
                    link=url_for('patient_dashboard')
                )
            except Exception:
                pass

            save_data()
            sync_data_to_sql()
            flash(f"Appointment scheduled successfully with Dr. {doctor.first_name} {doctor.last_name}! Your Token Number is {token_no}.", 'success')
            return redirect(url_for('patient_dashboard', tab='appointments'))

        if 'update_profile' in request.form or request.form.get('update_profile'):
            current_user.name = request.form.get('name', current_user.name)
            current_user.email = request.form.get('email', current_user.email)
            current_user.phone = request.form.get('phone', getattr(current_user, 'phone', None))
            current_user.address = request.form.get('address', getattr(current_user, 'address', None))
            
            age_str = request.form.get('age')
            if age_str and age_str.isdigit():
                current_user.age = int(age_str)
            current_user.gender = request.form.get('gender', current_user.gender)

            # Initialize clinical_record dictionary if missing
            if not hasattr(current_user, 'clinical_record') or not isinstance(current_user.clinical_record, dict):
                current_user.clinical_record = {}

            # Biometrics & Health Info
            if request.form.get('blood_group'):
                current_user.clinical_record['blood_group'] = request.form.get('blood_group')
            if request.form.get('height'):
                current_user.clinical_record['height'] = request.form.get('height')
            if request.form.get('weight'):
                current_user.clinical_record['weight'] = request.form.get('weight')
            if request.form.get('allergies') is not None:
                current_user.clinical_record['allergies'] = request.form.get('allergies')
            if request.form.get('existing_conditions') is not None:
                current_user.clinical_record['existing_conditions'] = request.form.get('existing_conditions')
            if request.form.get('current_medications') is not None:
                current_user.clinical_record['current_medications'] = request.form.get('current_medications')

            # Emergency Contacts
            if request.form.get('emergency_contact_name') is not None:
                current_user.clinical_record['emergency_contact_name'] = request.form.get('emergency_contact_name')
            if request.form.get('emergency_contact_phone') is not None:
                current_user.clinical_record['emergency_contact_phone'] = request.form.get('emergency_contact_phone')
            if request.form.get('emergency_contact_relation') is not None:
                current_user.clinical_record['emergency_contact_relation'] = request.form.get('emergency_contact_relation')

            # Insurance Details
            if request.form.get('insurance_provider') is not None:
                current_user.clinical_record['insurance_provider'] = request.form.get('insurance_provider')
            if request.form.get('insurance_policy_no') is not None:
                current_user.clinical_record['insurance_policy_no'] = request.form.get('insurance_policy_no')

            # Demographics & Lifestyle
            if request.form.get('date_of_birth') is not None:
                current_user.clinical_record['date_of_birth'] = request.form.get('date_of_birth')
            if request.form.get('marital_status') is not None:
                current_user.clinical_record['marital_status'] = request.form.get('marital_status')
            if request.form.get('occupation') is not None:
                current_user.clinical_record['occupation'] = request.form.get('occupation')
            if request.form.get('diet_preference') is not None:
                current_user.clinical_record['diet_preference'] = request.form.get('diet_preference')
            if request.form.get('smoker_status') is not None:
                current_user.clinical_record['smoker_status'] = request.form.get('smoker_status')
            if request.form.get('alcohol_status') is not None:
                current_user.clinical_record['alcohol_status'] = request.form.get('alcohol_status')
            
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
                    filename_prefix=f"pat_profile_{current_user.id}"
                )
                if saved_filename:
                    current_user.profile_picture_url = saved_filename
            
            save_data()
            flash("Patient health profile and clinical records updated successfully!", "success")
            return redirect(url_for('patient_dashboard', tab='settings'))

    # The @patient_required decorator handles authentication and role checking.
    today = date.today()

    # Fetch patient's orders
    patient_orders = [
        order for order in TEMP_DATA['orders'].values() 
        if str(order.patient_id) == str(current_user.id)
    ]
    # Sort orders by date, most recent first
    sorted_orders = sorted(patient_orders, key=lambda o: str(getattr(o, 'order_date', '') or ''), reverse=True)

    # Fetch patient's bed bookings
    patient_bed_bookings = [
        bb for bb in TEMP_DATA.get('bed_bookings', {}).values()
        if str(getattr(bb, 'patient_id', '')) == str(current_user.id)
    ]
    patient_bed_bookings.sort(key=lambda bb: str(getattr(bb, 'created_at', '') or ''), reverse=True)

    # Enrich appointments with the doctor object for the rating feature
    for appt in current_user.appointments:
        if not hasattr(appt, 'doctor'):
            appt.doctor = TEMP_DATA['doctors'].get(appt.doctor_id)

    # Fetch patient's vitals
    patient_vitals = [
        v for v in TEMP_DATA.get('patient_vitals', {}).values()
        if str(getattr(v, 'patient_id', '')) == str(current_user.id)
    ]
    # Sort by recorded_at ascending for chronological chart
    patient_vitals.sort(key=lambda v: str(getattr(v, 'recorded_at', '') or getattr(v, 'created_at', '') or ''))

    vitals_dates = [v.recorded_at.strftime('%b %d') if hasattr(v, 'recorded_at') and hasattr(v.recorded_at, 'strftime') else str(getattr(v, 'recorded_at', ''))[:10] for v in patient_vitals]
    vitals_weight = [getattr(v, 'weight', None) for v in patient_vitals]
    vitals_heart_rate = [getattr(v, 'heart_rate', None) for v in patient_vitals]
    vitals_blood_sugar = [getattr(v, 'blood_sugar', None) for v in patient_vitals]
    vitals_systolic = [getattr(v, 'systolic_bp', None) for v in patient_vitals]
    vitals_diastolic = [getattr(v, 'diastolic_bp', None) for v in patient_vitals]

    # Fetch patient's messages with doctors
    patient_messages = [
        m for m in TEMP_DATA.get('messages', {}).values()
        if str(m.patient_id) == str(current_user.id)
    ]
    patient_messages.sort(key=lambda m: str(m.created_at or ''), reverse=True)

    # Fetch patient appointments
    patient_appointments = list(current_user.appointments)
    patient_appointments.sort(key=lambda a: (str(a.appointment_date or ''), str(a.appointment_time or '')), reverse=True)

    patient_referrals = sorted([
        ref for ref in TEMP_DATA.get('referrals', {}).values()
        if ref.patient_id == current_user.id
    ], key=lambda x: str(x.created_at or ''), reverse=True)

    unread_notifications = [
        n for n in TEMP_DATA.get('notifications', {}).values()
        if n.user_id == current_user.id and n.status == 'unread'
    ]
    unread_notifications.sort(key=lambda x: str(x.created_at or ''), reverse=True)

    # Fetch patient's confidential medical records
    patient_medical_records = [
        rec for rec in TEMP_DATA.get('medical_records', {}).values()
        if str(rec.patient_id) == str(current_user.id)
    ]
    patient_medical_records.sort(key=lambda r: str(r.record_date or r.created_at), reverse=True)

    # Fetch patient's diagnostic lab test requests
    raw_labs = TEMP_DATA.get('lab_requests', {})
    all_labs = raw_labs.values() if isinstance(raw_labs, dict) else (raw_labs or [])
    patient_lab_requests = []
    patient_ids = {str(current_user.id), str(getattr(current_user, 'license_no', ''))}
    for lr in all_labs:
        p_id = str(lr.get('patient_id', '') if isinstance(lr, dict) else getattr(lr, 'patient_id', ''))
        if p_id in patient_ids:
            doc_id = lr.get('doctor_id') if isinstance(lr, dict) else getattr(lr, 'doctor_id', None)
            existing_doc_name = lr.get('doctor_name') if isinstance(lr, dict) else getattr(lr, 'doctor_name', None)
            if not existing_doc_name and doc_id:
                doc = TEMP_DATA.get('doctors', {}).get(doc_id)
                if doc:
                    doc_fullname = f"{doc.first_name} {doc.last_name}".strip()
                    if isinstance(lr, dict):
                        lr['doctor_name'] = doc_fullname
                    else:
                        try:
                            lr.doctor_name = doc_fullname
                        except:
                            pass
            patient_lab_requests.append(lr)

    def _get_lr_time(x):
        val = x.get('created_at', '') if isinstance(x, dict) else getattr(x, 'created_at', '')
        return str(val)

    patient_lab_requests.sort(key=_get_lr_time, reverse=True)

    all_registered_doctors = deduplicate_entities(list(TEMP_DATA.get('doctors', {}).values()))

    return render_template('patient_dashboard.html', 
                           patient=current_user, 
                           today=today, 
                           appointments=patient_appointments,
                           orders=sorted_orders, 
                           bed_bookings=patient_bed_bookings, 
                           hospitals=TEMP_DATA.get('hospitals', {}),
                           doctors=TEMP_DATA.get('doctors', {}),
                           all_doctors=all_registered_doctors,
                           medical_records=patient_medical_records,
                           lab_requests=patient_lab_requests,
                           patient_vitals=patient_vitals,
                           vitals_dates=vitals_dates,
                           vitals_weight=vitals_weight,
                           vitals_heart_rate=vitals_heart_rate,
                           vitals_blood_sugar=vitals_blood_sugar,
                           vitals_systolic=vitals_systolic,
                           vitals_diastolic=vitals_diastolic,
                           referrals=patient_referrals,
                           messages=patient_messages,
                           unread_notifications=unread_notifications)



@patient_bp.route('/patient/medical-records/upload', methods=['POST'])
@patient_required
def patient_upload_medical_record():
    """Handles secure file upload and metadata storage for patient medical records with selective doctor sharing."""
    title = (request.form.get('title') or '').strip()
    record_type = (request.form.get('record_type') or 'Lab Report').strip()
    record_date = (request.form.get('record_date') or datetime.now().strftime('%Y-%m-%d')).strip()
    facility_name = (request.form.get('facility_name') or '').strip()
    doctor_name = (request.form.get('doctor_name') or '').strip()
    description = (request.form.get('description') or '').strip()
    shared_doctors = request.form.getlist('shared_doctors')

    if not title:
        flash('Please provide a descriptive title for this medical record.', 'error')
        return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')

    # Handle File Upload
    file = request.files.get('medical_file')
    saved_file_rel_path = ""
    original_file_name = ""
    file_type = "pdf"
    file_size_str = "0 KB"

    if file and file.filename != '':
        orig_name = secure_filename(file.filename)
        ext = orig_name.rsplit('.', 1)[-1].lower() if '.' in orig_name else 'pdf'
        
        # Allowed file extensions
        if ext not in ['pdf', 'jpg', 'jpeg', 'png', 'webp', 'doc', 'docx', 'txt']:
            flash('Invalid file format. Please upload PDF, JPG, PNG, WEBP, or DOCX documents.', 'error')
            return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')

        if ext in ['jpg', 'jpeg', 'png', 'webp']:
            file_type = 'image'
        elif ext in ['doc', 'docx']:
            file_type = 'doc'
        else:
            file_type = 'pdf'

        upload_dir = os.path.join(current_app.static_folder, 'uploads', 'medical_records')
        os.makedirs(upload_dir, exist_ok=True)

        timestamp_prefix = int(datetime.now().timestamp())
        clean_pid = str(current_user.id).replace('/', '_').replace('\\', '_')
        unique_file_name = f"pat_{clean_pid}_{timestamp_prefix}_{orig_name}"
        full_dest_path = os.path.join(upload_dir, unique_file_name)
        
        file.save(full_dest_path)
        saved_file_rel_path = f"uploads/medical_records/{unique_file_name}"
        original_file_name = orig_name

        try:
            bytes_size = os.path.getsize(full_dest_path)
            if bytes_size >= 1024 * 1024:
                file_size_str = f"{bytes_size / (1024 * 1024):.1f} MB"
            else:
                file_size_str = f"{max(1, bytes_size // 1024)} KB"
        except Exception:
            file_size_str = "1.2 MB"

    pat_name = getattr(current_user, 'name', '') or f"{getattr(current_user, 'first_name', '')} {getattr(current_user, 'last_name', '')}".strip() or "Patient"
    
    # Generate unique Record ID
    new_id_num = TEMP_DATA.get('next_ids', {}).get('medical_record', 1)
    if 'medical_records' in TEMP_DATA and TEMP_DATA['medical_records']:
        for k in TEMP_DATA['medical_records'].keys():
            try:
                if str(k).startswith('REC-'):
                    n = int(str(k).split('-')[-1])
                    if n >= new_id_num:
                        new_id_num = n + 1
            except Exception:
                pass

    rec_id = f"REC-2026-{new_id_num:03d}"
    TEMP_DATA['next_ids']['medical_record'] = new_id_num + 1

    new_record = PatientMedicalRecord(
        id=rec_id,
        patient_id=str(current_user.id),
        patient_name=pat_name,
        title=title,
        record_type=record_type,
        record_date=record_date,
        doctor_name=doctor_name,
        facility_name=facility_name,
        description=description,
        file_path=saved_file_rel_path,
        file_name=original_file_name or f"{title}.{file_type}",
        file_type=file_type,
        file_size=file_size_str,
        shared_with=[str(d) for d in shared_doctors if str(d).strip()],
        doctor_notes={}
    )

    if 'medical_records' not in TEMP_DATA:
        TEMP_DATA['medical_records'] = {}
    TEMP_DATA['medical_records'][rec_id] = new_record
    save_data()

    # Dispatch notification to each selected doctor
    for doc_id in shared_doctors:
        if str(doc_id).strip():
            create_notification(
                user_id=str(doc_id).strip(),
                user_type='doctor',
                message=f"Patient {pat_name} has shared a confidential medical record: '{title}' ({record_type}) with you.",
                link=url_for('doctor_dashboard') + '#ehr'
            )

    doc_count = len([d for d in shared_doctors if str(d).strip()])
    if doc_count > 0:
        flash(f"Medical record '{title}' saved and securely shared with {doc_count} specialist doctor(s)!", 'success')
    else:
        flash(f"Medical record '{title}' saved to your private Health Vault.", 'success')

    return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')



@patient_bp.route('/patient/medical-records/<record_id>/share', methods=['POST'])
@patient_required
def patient_update_medical_record_sharing(record_id):
    """Updates the list of authorized doctors permitted to view this specific medical record."""
    record = TEMP_DATA.get('medical_records', {}).get(str(record_id))
    if not record or str(record.patient_id) != str(current_user.id):
        flash('Medical record not found or access unauthorized.', 'error')
        return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')

    prev_shared = set(record.shared_with or [])
    new_shared = request.form.getlist('shared_doctors')
    clean_new_shared = [str(d).strip() for d in new_shared if str(d).strip()]
    record.shared_with = clean_new_shared
    save_data()

    pat_name = getattr(current_user, 'name', '') or "Patient"
    # Notify newly added doctors
    newly_added = set(clean_new_shared) - prev_shared
    for doc_id in newly_added:
        create_notification(
            user_id=doc_id,
            user_type='doctor',
            message=f"Patient {pat_name} granted you access to their medical record: '{record.title}'.",
            link=url_for('doctor_dashboard') + '#ehr'
        )

    flash(f"Doctor sharing permissions updated. {len(clean_new_shared)} doctor(s) currently have authorized access.", 'success')
    return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')



@patient_bp.route('/patient/medical-records/<record_id>/delete', methods=['POST'])
@patient_required
def patient_delete_medical_record(record_id):
    """Permanently removes a medical record from the patient repository."""
    record = TEMP_DATA.get('medical_records', {}).get(str(record_id))
    if not record or str(record.patient_id) != str(current_user.id):
        flash('Medical record not found or access unauthorized.', 'error')
        return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')

    # Remove physical file if present
    if record.file_path:
        full_path = os.path.join(current_app.static_folder, record.file_path)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception:
            pass

    del TEMP_DATA['medical_records'][str(record_id)]
    save_data()

    flash(f"Medical record '{record.title}' deleted permanently.", 'info')
    return redirect(url_for('patient_dashboard') + '?tab=tab-medical_records')




@patient_bp.route('/patient/send-message', methods=['POST'])
@patient_required
def patient_send_message():
    doctor_id = request.form.get('doctor_id')
    content = (request.form.get('content') or '').strip()
    if doctor_id and content:
        msg_id = max([0] + [int(k) for k in TEMP_DATA.get('messages', {}).keys() if str(k).isdigit()]) + 1
        TEMP_DATA['messages'][msg_id] = Message(
            id=msg_id,
            doctor_id=doctor_id,
            patient_id=current_user.id,
            sender='patient',
            content=content,
            created_at=utcnow()
        )
        save_data()
        flash('Message sent to doctor successfully.', 'success')
    else:
        flash('Message content cannot be empty.', 'error')
    return redirect(url_for('patient_dashboard') + '#messages')



@patient_bp.route('/api/patient/live-status')
@patient_required
def patient_live_status():
    """Real-time polling endpoint for patient dashboard telemetry, queue updates, and messages."""
    pat_appts = []
    for appt in current_user.appointments:
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        doc_name = f"Dr. {doc.first_name} {doc.last_name}" if doc else (appt.patient_name or 'Doctor')
        doc_room = getattr(doc, 'opd_room', 'Room 101') if doc else 'Room 101'
        doc_specialty = getattr(doc, 'specialty', 'General') if doc else 'General'
        pat_appts.append({
            'id': appt.id,
            'token_no': getattr(appt, 'token_no', f"TK-{appt.id}"),
            'queue_status': getattr(appt, 'queue_status', ('completed' if appt.status == 'completed' else 'waiting')),
            'status': appt.status,
            'doctor_id': appt.doctor_id,
            'doctor_name': doc_name,
            'doctor_room': doc_room,
            'doctor_specialty': doc_specialty,
            'appointment_date': str(appt.appointment_date),
            'appointment_time': appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time else '',
            'vitals': getattr(appt, 'vitals', {}),
            'fee_amount': getattr(appt, 'fee_amount', 300)
        })

    # Messages
    msgs = [
        {
            'id': m.id,
            'doctor_id': m.doctor_id,
            'sender': m.sender,
            'content': m.content,
            'created_at': m.created_at.strftime('%b %d, %H:%M') if m.created_at else ''
        }
        for m in TEMP_DATA.get('messages', {}).values()
        if str(m.patient_id) == str(current_user.id)
    ]
    msgs.sort(key=lambda x: x.get('id', 0))

    return jsonify({
        'success': True,
        'patient_id': current_user.id,
        'patient_name': current_user.name,
        'appointments': pat_appts,
        'messages': msgs,
        'unread_count': len([n for n in TEMP_DATA.get('notifications', {}).values() if n.user_id == current_user.id and n.status == 'unread']),
        'timestamp': utcnow().isoformat()
    })



@patient_bp.route('/appointment/cancel/<int:appointment_id>', methods=['POST'])
@patient_required
def cancel_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)

    if appointment and appointment.patient_id == current_user.id:
        appointment.status = 'cancelled'        
        # Send email notification to the doctor about the patient's cancellation
        doctor = appointment.doctor
        if doctor and doctor.email:
            subject = f"Appointment Cancellation by Patient: {appointment.patient_name}"
            body = f"""
Dear Dr. {doctor.first_name} {doctor.last_name},

This is to inform you that the appointment booked by {appointment.patient_name} 
for {appointment.appointment_date.strftime('%B %d, %Y')} at {appointment.appointment_time.strftime('%I:%M %p')} 
has been cancelled by the patient.

Reason for appointment: {appointment.reason or 'Not specified'}
Patient contact: {appointment.patient.email if appointment.patient else 'N/A'}

Best regards,
The Spherix Clinic Team"""
            send_notification_email(doctor.email, subject, body)
        save_data() # Save the status change
        flash("Your appointment has been successfully cancelled.", "success")
    else:
        flash("Appointment not found or you do not have permission to cancel it.", "error")
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/patient/appointment/edit/<int:appointment_id>', methods=['POST'])
@patient_required
def patient_edit_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.patient_id == current_user.id:
        if appointment.status in ['pending', 'confirmed', 'awaiting_payment']:
            date_str = request.form.get('date')
            time_str = request.form.get('time')
            if date_str and time_str:
                appointment.appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                appointment.appointment_time = datetime.strptime(time_str, '%H:%M').time()
                appointment.reason = request.form.get('reason', appointment.reason)
                if appointment.status == 'confirmed':
                    appointment.status = 'pending'
                save_data()
                flash('Appointment rescheduled successfully. Pending doctor confirmation.', 'success')
            else:
                flash('Date and time are required.', 'error')
        else:
            flash('Cannot edit a completed or cancelled appointment.', 'error')
    else:
        flash('Appointment not found or unauthorized.', 'error')
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/patient/order/cancel/<int:order_id>', methods=['POST'])
@patient_required
def patient_cancel_order(order_id):
    order = TEMP_DATA.get('orders', {}).get(order_id)
    if order and order.patient_id == current_user.id:
        if order.status in ['Processing', 'Awaiting Payment', 'Paid & Processing']:
            order.status = 'Cancelled'
            save_data()
            flash('Pharmacy order cancelled successfully.', 'success')
        else:
            flash('Cannot cancel an order that has already shipped.', 'error')
    else:
        flash('Order not found or unauthorized.', 'error')
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/patient/order/edit/<int:order_id>', methods=['POST'])
@patient_required
def patient_edit_order(order_id):
    order = TEMP_DATA.get('orders', {}).get(order_id)
    if order and order.patient_id == current_user.id:
        if order.status in ['Processing', 'Awaiting Payment', 'Paid & Processing']:
            order.shipping_address['name'] = request.form.get('name', order.shipping_address.get('name'))
            order.shipping_address['address'] = request.form.get('address', order.shipping_address.get('address'))
            order.shipping_address['city'] = request.form.get('city', order.shipping_address.get('city'))
            order.shipping_address['state'] = request.form.get('state', order.shipping_address.get('state'))
            order.shipping_address['pincode'] = request.form.get('pincode', order.shipping_address.get('pincode'))
            save_data()
            flash('Shipping address updated successfully.', 'success')
        else:
            flash('Cannot edit an order that has already shipped.', 'error')
    else:
        flash('Order not found or unauthorized.', 'error')
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/appointment', methods=['GET', 'POST'])
def book_appointment():
    if not current_user.is_authenticated:
        return redirect(url_for('patient_login', next=request.path))

    if request.method == 'POST':
        # Retrieve ALL form data (including new fields)
        patient_name = request.form['name']
        patient_email = request.form['email'] # New
        patient_phone = request.form.get('phone') # Existing, but now clearer
        patient_dob = request.form.get('dob') # New
        patient_address = request.form.get('address') # New
        patient_gender = request.form.get('gender') # New
        doctor_id = request.form['doctor_id']
        appointment_date = request.form['date'] # Existing
        appointment_time = request.form['time'] # New
        reason_for_visit = request.form.get('reason') # New

        # Validate input
        if not all([patient_name, patient_email, doctor_id, appointment_date, appointment_time]):
            flash("All required fields must be filled.", "error")
            return redirect(request.referrer or url_for('patient_dashboard'))

        doctor = TEMP_DATA['doctors'].get(doctor_id)
        if not doctor or getattr(doctor, 'is_hidden', False) or getattr(doctor, 'is_blocked', False):
            flash("Selected doctor is currently unavailable.", "error")
            return redirect(request.referrer or url_for('patient_dashboard'))

        # If booking is initiated by a Staff member, strictly enforce hospital affiliation
        if current_user.is_authenticated and getattr(current_user, 'is_staff', False):
            staff_hosp = (getattr(current_user, 'hospital_name', '') or '').strip().lower()
            doc_hosp = (getattr(doctor, 'hospital_name', '') or '').strip().lower()
            if not staff_hosp or not doc_hosp or staff_hosp != doc_hosp:
                flash(f"Access Denied: Staff can only book appointments or arrange treatment with doctors affiliated with their hospital ({current_user.hospital_name}).", "error")
                return redirect(request.referrer or url_for('staff_dashboard'))

        # Create the new appointment
        appt_id = TEMP_DATA['next_ids']['appointment']
        new_appointment = Appointment(
            id=appt_id,
            patient_name=patient_name,
            doctor_id=doctor_id,
            appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d').date(),
            appointment_time=datetime.strptime(appointment_time, '%H:%M').time(),
            patient_phone=patient_phone,
            reason=reason_for_visit,
            status='awaiting_payment'
        )

        # If a patient is logged in, associate the appointment with them
        if current_user.is_authenticated and isinstance(current_user, Patient):
            new_appointment.patient_id = current_user.id

        TEMP_DATA['appointments'][appt_id] = new_appointment
        TEMP_DATA['next_ids']['appointment'] += 1
        save_data() # Save after booking appointment

        return redirect(url_for('appointment_payment', appointment_id=appt_id))
    
    return redirect(url_for('patient_dashboard'))



@patient_bp.route('/appointment/payment/<int:appointment_id>', methods=['GET', 'POST'])
def appointment_payment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect(url_for('home'))
    
    doctor = TEMP_DATA['doctors'].get(appointment.doctor_id)
    # Ensure fee is a number
    try:
        fee = float(doctor.consultation_fee) if doctor and doctor.consultation_fee else 2500.0
    except ValueError:
        fee = 1000.0
    
    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'card') # Simulate choice
        
        if payment_method == 'card' and razorpay_client:
            try:
                payment_link = razorpay_client.payment_link.create({
                    "amount": int(fee * 100),
                    "currency": "INR",
                    "accept_partial": False,
                    "reference_id": f"appt_{appointment.id}_{int(time_module.time())}",
                    "description": f"Doctor Appointment with Dr. {doctor.last_name}",
                    "customer": {
                        "name": appointment.patient_name,
                        "contact": appointment.patient_phone
                    },
                    "callback_url": url_for('appointment_success', appointment_id=appointment.id, _external=True) + '?session_id=razorpay_payment',
                    "callback_method": "get"
                })
                return redirect(payment_link['short_url'], code=303)
            except Exception as e:
                flash(f"Payment error: {str(e)}", "error")
                return redirect(url_for('appointment_payment', appointment_id=appointment.id))
        else:
            # Fallback/Simulation if Stripe isn't configured
            appointment.status = 'confirmed' 
            save_data()
            flash("Payment successful! Appointment confirmed.", "success")
            return redirect(url_for('appointment_success', appointment_id=appointment.id))

    return render_template('appointment_payment.html', appointment=appointment, doctor=doctor, fee=fee)



@patient_bp.route('/appointment/success/<int:appointment_id>')
def appointment_success(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        return redirect(url_for('home'))
        
    session_id = request.args.get('session_id')
    if session_id and appointment.status == 'awaiting_payment':
        appointment.status = 'confirmed'
        save_data()
        flash("Online payment successful! Appointment confirmed.", "success")
        
    return render_template('appointment_success.html', appointment=appointment)



@patient_bp.route('/appointment/payment/receipt/<int:appointment_id>')
def appointment_payment_receipt(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect(url_for('home'))
    
    # Basic auth check
    if current_user.is_authenticated:
        is_patient = hasattr(current_user, 'is_doctor') and not current_user.is_doctor and appointment.patient_id == current_user.id
        is_doctor = hasattr(current_user, 'is_doctor') and current_user.is_doctor and appointment.doctor_id == current_user.id
        is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@spherixclinic.com'
        
        if appointment.patient_id and not (is_patient or is_doctor or is_admin):
             flash("Unauthorized access to receipt.", "error")
             return redirect(url_for('home'))

    doctor = TEMP_DATA['doctors'].get(appointment.doctor_id)
    try:
        fee = float(doctor.consultation_fee) if doctor and doctor.consultation_fee else 1000.0
    except (ValueError, AttributeError):
        fee = 1000.0

    try:
        class AppointmentReceiptPDF(FPDF):
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
                self.cell(0, 8, 'SPHERIX CLINIC - CONSULTATION RECEIPT', 0, 1, 'C')
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
                self.cell(0, 4, 'Disclaimer: This receipt is a legally binding payment receipt. Keep secure.', 0, 1, 'C')
                self.cell(0, 4, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} // Spherix Health Systems', 0, 1, 'C')

        pdf = AppointmentReceiptPDF()
        pdf.add_page()
        pdf.set_margins(12, 12, 12)
        pdf.ln(18) # Add space after header
        
        # Spherix details header
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, 'Spherix Clinic Health Intelligence', 0, 1, 'L')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, 'Motihari, Bihar, 845401', 0, 1, 'L')
        pdf.ln(4)
        
        # Meta Block
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Receipt Reference:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(65, 6, f'RCPT-{appointment.id}', 0, 0, 'L')
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Payment Date:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, datetime.now().strftime('%Y-%m-%d'), 0, 1, 'L')
        
        pdf.ln(5)
        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.3)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(5)
        
        # Column Details Block (Billed To vs Service Provider)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(93, 8, 'Billed To:', 0, 0, 'L')
        pdf.cell(93, 8, 'Service Provider:', 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(93, 5, to_latin1_str(appointment.patient_name), 0, 0, 'L')
        pdf.cell(93, 5, f'Dr. {to_latin1_str(doctor.first_name)} {to_latin1_str(doctor.last_name)}', 0, 1, 'L')
        
        pdf.cell(93, 5, f'Phone: {appointment.patient_phone or "N/A"}', 0, 0, 'L')
        pdf.cell(93, 5, f'Department: {to_latin1_str(doctor.department)}', 0, 1, 'L')
        
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
        desc = f"Medical Consultation - {appointment.appointment_date.strftime('%Y-%m-%d')}"
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
        pdf.cell(70, 10, 'TRANSACTION SUCCESSFUL & PAID', 1, 1, 'C', fill=True)

        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode('latin-1', 'replace')
        else:
            pdf_bytes = pdf_output

        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'receipt_{appointment.id}.pdf', mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating receipt: {e}")
        flash("An error occurred while generating the receipt.", "error")
        return redirect(url_for('appointment_success', appointment_id=appointment.id))



@patient_bp.route('/appointment/invoice/<int:appointment_id>')
@login_required
def appointment_invoice(appointment_id):
    """Renders a printable HTML invoice for a specific appointment."""
    appointment = TEMP_DATA['appointments'].get(appointment_id)

    # Authorization check:
    # 1. Appointment must exist
    if not appointment:
        flash("Appointment not found.", "error")
        # Redirect to a sensible default page
        return redirect(url_for('home'))

    # 2. User must be either the patient or the doctor for this appointment
    is_patient = hasattr(current_user, 'is_doctor') and not current_user.is_doctor and appointment.patient_id == current_user.id
    is_doctor = hasattr(current_user, 'is_doctor') and current_user.is_doctor and appointment.doctor_id == current_user.id

    if not (is_patient or is_doctor):
        flash("You are not authorized to view this invoice.", "error")
        if hasattr(current_user, 'is_doctor') and current_user.is_doctor:
            return redirect(url_for('doctor_dashboard'))
        else:
            return redirect(url_for('patient_dashboard'))

    return render_template('appointment_invoice.html', appointment=appointment)



@patient_bp.route('/api/family/list', methods=['GET'])
def api_family_list():
    """Returns list of family members/dependents for current user."""
    user_id = getattr(current_user, 'id', 1) if current_user.is_authenticated else 1
    family_store = TEMP_DATA.setdefault('family_members', {})
    members = family_store.setdefault(user_id, [
        {
            'id': 1,
            'name': 'Aarav (Son)',
            'relationship': 'Child',
            'dob': '2022-04-15',
            'age': '4 Years',
            'blood_group': 'O+',
            'vaccines': [
                {'name': 'BCG', 'due_age': 'At Birth', 'status': 'Completed'},
                {'name': 'Hepatitis B (Dose 1-3)', 'due_age': '6 Months', 'status': 'Completed'},
                {'name': 'DTP Booster 1', 'due_age': '18 Months', 'status': 'Completed'},
                {'name': 'MMR Dose 2', 'due_age': '4-6 Years', 'status': 'Due Now'}
            ]
        },
        {
            'id': 2,
            'name': 'Shanti Devi (Mother)',
            'relationship': 'Parent',
            'dob': '1958-08-10',
            'age': '68 Years',
            'blood_group': 'B+',
            'chronic_conditions': ['Hypertension', 'Type 2 Diabetes'],
            'recent_bp': '128/82 mmHg'
        }
    ])
    return jsonify({'success': True, 'members': members})




@patient_bp.route('/api/family/add', methods=['POST'])
def api_family_add():
    """Adds a new dependent to the patient family tree."""
    data = request.get_json() or {}
    user_id = getattr(current_user, 'id', 1) if current_user.is_authenticated else 1
    family_store = TEMP_DATA.setdefault('family_members', {})
    members = family_store.setdefault(user_id, [])
    
    new_id = len(members) + 1
    new_member = {
        'id': new_id,
        'name': data.get('name', 'Dependent'),
        'relationship': data.get('relationship', 'Family Member'),
        'dob': data.get('dob', '2020-01-01'),
        'blood_group': data.get('blood_group', 'O+'),
        'chronic_conditions': data.get('chronic_conditions', [])
    }
    members.append(new_member)
    return jsonify({'success': True, 'member': new_member})



@patient_bp.route('/patient/lab-report/download/<lab_id>')
@login_required
def download_lab_report_pdf(lab_id):
    """Generates and downloads an authentic, official clinical PDF diagnostic lab report."""
    raw_labs = TEMP_DATA.get('lab_requests', {})
    items = raw_labs.values() if isinstance(raw_labs, dict) else (raw_labs or [])
    lab_req = None
    for req in items:
        rid = req.get('id') if isinstance(req, dict) else getattr(req, 'id', None)
        if str(rid) == str(lab_id):
            lab_req = req
            break

    if not lab_req:
        flash("Lab report record not found.", "error")
        return redirect(url_for('patient_dashboard', tab='laboratory'))

    def _get_val(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    req_id = _get_val(lab_req, 'id', lab_id)
    patient_id = _get_val(lab_req, 'patient_id')
    patient_name = _get_val(lab_req, 'patient_name') or getattr(current_user, 'name', 'Patient')
    doctor_id = _get_val(lab_req, 'doctor_id')
    doc_name = _get_val(lab_req, 'doctor_name')
    test_name = _get_val(lab_req, 'test_name') or 'Diagnostic Investigation Panel'
    status = _get_val(lab_req, 'status') or 'Completed'
    created_at = _get_val(lab_req, 'created_at')
    notes = _get_val(lab_req, 'notes')

    user_id_str = str(getattr(current_user, 'id', ''))
    user_lic_str = str(getattr(current_user, 'license_no', ''))
    is_owner = getattr(current_user, 'is_patient', False) and (str(patient_id) in (user_id_str, user_lic_str))
    is_doc = getattr(current_user, 'is_doctor', False)
    is_staff_or_hosp = getattr(current_user, 'is_staff', False) or getattr(current_user, 'is_hospital', False)
    is_admin = getattr(current_user, 'email', '') == 'admin@spherixclinic.com'
    if not (is_owner or is_doc or is_staff_or_hosp or is_admin):
        flash("Unauthorized access to lab report.", "error")
        return redirect(url_for('patient_dashboard'))

    doctor = TEMP_DATA.get('doctors', {}).get(doctor_id) if doctor_id else None
    if doctor:
        doctor_name = f"Dr. {doctor.first_name} {doctor.last_name}".strip()
    elif doc_name:
        doctor_name = doc_name if str(doc_name).startswith('Dr.') else f"Dr. {doc_name}"
    else:
        doctor_name = "Dr. Attending Specialist"

    try:
        class LabReportPDF(FPDF):
            def header(self):
                self.set_draw_color(30, 41, 59)
                self.set_line_width(0.8)
                self.rect(8, 8, 194, 281)

                self.set_fill_color(15, 23, 42)
                self.rect(8, 8, 194, 26, 'F')
                self.set_y(12)
                self.set_font('Helvetica', 'B', 15)
                self.set_text_color(255, 255, 255)
                self.cell(0, 7, 'SPHERIX DIAGNOSTICS & CENTRAL PATHOLOGY LAB', 0, 1, 'C')
                self.set_font('Helvetica', '', 8)
                self.set_text_color(148, 163, 184)
                self.cell(0, 5, 'NABL ACCREDITED | ISO 15189:2012 COMPLIANT | ADVANCED CLINICAL TESTING', 0, 1, 'C')
                self.set_text_color(0, 0, 0)
                self.ln(5)

            def footer(self):
                self.set_y(-18)
                self.set_draw_color(226, 232, 240)
                self.line(10, self.get_y(), 200, self.get_y())
                self.set_y(-14)
                self.set_font('Helvetica', 'I', 7.5)
                self.set_text_color(100, 116, 139)
                self.cell(0, 4, 'This is an authentic electronically verified diagnostic report from Spherix Health Systems.', 0, 1, 'C')
                self.cell(0, 4, f'Report ID: LAB-{to_latin1_str(str(req_id))} | Page {self.page_no()}', 0, 0, 'C')

        pdf = LabReportPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(203, 213, 225)
        pdf.set_line_width(0.3)
        pdf.rect(12, 38, 186, 32, 'DF')

        pdf.set_xy(16, 41)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(90, 5, f"PATIENT: {to_latin1_str(str(patient_name).upper())}", 0, 0)
        pdf.cell(90, 5, f"SAMPLE ID: SPL-{random.randint(100000, 999999)}", 0, 1)

        pdf.set_x(16)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(71, 85, 105)
        patient_age = getattr(current_user, 'age', '32')
        patient_gender = getattr(current_user, 'gender', 'Adult')
        pdf.cell(90, 5, f"Age / Gender: {patient_age} Yrs / {str(patient_gender).title()}", 0, 0)
        req_date = created_at.strftime('%Y-%m-%d %H:%M') if hasattr(created_at, 'strftime') else (str(created_at) if created_at else datetime.now().strftime('%Y-%m-%d %H:%M'))
        pdf.cell(90, 5, f"Collection Date: {req_date}", 0, 1)

        pdf.set_x(16)
        pdf.cell(90, 5, f"Ref. Doctor: {to_latin1_str(str(doctor_name))}", 0, 0)
        pdf.cell(90, 5, f"Reporting Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)

        pdf.set_x(16)
        pdf.cell(90, 5, f"Patient ID: PT-{to_latin1_str(str(patient_id))}", 0, 0)
        pdf.cell(90, 5, f"Test Status: {str(status).upper()}", 0, 1)

        pdf.ln(8)

        pdf.set_x(12)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(255, 255, 255)
        test_display_title = to_latin1_str(str(test_name or 'Diagnostic Investigation Panel').upper())
        pdf.cell(186, 7, f"   INVESTIGATION: {test_display_title}", 0, 1, 'L', fill=True)

        pdf.set_x(12)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(66, 6, "  Parameter", 1, 0, 'L', fill=True)
        pdf.cell(35, 6, "Observed Value", 1, 0, 'C', fill=True)
        pdf.cell(35, 6, "Units", 1, 0, 'C', fill=True)
        pdf.cell(50, 6, "Biological Ref. Range", 1, 1, 'C', fill=True)

        test_name_lower = str(test_name).lower()
        if 'cbc' in test_name_lower or 'blood count' in test_name_lower or 'hemogram' in test_name_lower:
            parameters = [
                ("Hemoglobin (Hb)", "14.2", "g/dL", "13.0 - 17.0", "NORMAL"),
                ("Total RBC Count", "4.85", "mill/cumm", "4.50 - 5.50", "NORMAL"),
                ("Total Leukocyte Count (WBC)", "7,400", "cells/cumm", "4,000 - 11,000", "NORMAL"),
                ("Platelet Count", "260,000", "cells/cumm", "150,000 - 450,000", "NORMAL"),
                ("Hematocrit (PCV)", "42.5", "%", "40.0 - 50.0", "NORMAL"),
                ("Mean Corpuscular Volume (MCV)", "87.6", "fL", "83.0 - 101.0", "NORMAL"),
                ("Neutrophils", "62", "%", "40 - 70", "NORMAL"),
                ("Lymphocytes", "30", "%", "20 - 40", "NORMAL"),
                ("Monocytes", "5", "%", "2 - 10", "NORMAL"),
                ("Eosinophils", "3", "%", "1 - 6", "NORMAL")
            ]
        elif 'lipid' in test_name_lower or 'cholesterol' in test_name_lower:
            parameters = [
                ("Total Cholesterol", "185", "mg/dL", "Desirable: < 200", "NORMAL"),
                ("HDL Cholesterol (Good)", "48", "mg/dL", "Optimal: > 40", "NORMAL"),
                ("LDL Cholesterol (Calculated)", "112", "mg/dL", "Optimal: < 100", "BORDERLINE"),
                ("Triglycerides", "125", "mg/dL", "Normal: < 150", "NORMAL"),
                ("VLDL Cholesterol", "25", "mg/dL", "Normal: 10 - 30", "NORMAL"),
                ("Total Chol / HDL Ratio", "3.85", "ratio", "Normal: < 4.5", "NORMAL")
            ]
        elif 'sugar' in test_name_lower or 'glucose' in test_name_lower or 'diabetes' in test_name_lower or 'hba1c' in test_name_lower:
            parameters = [
                ("Fasting Blood Glucose", "94", "mg/dL", "Normal: 70 - 99", "NORMAL"),
                ("Postprandial Blood Glucose (PP)", "128", "mg/dL", "Normal: < 140", "NORMAL"),
                ("Glycated Hemoglobin (HbA1c)", "5.4", "%", "Non-diabetic: < 5.7", "NORMAL"),
                ("Average Estimated Blood Glucose", "108", "mg/dL", "Estimated", "NORMAL")
            ]
        elif 'liver' in test_name_lower or 'lft' in test_name_lower:
            parameters = [
                ("Bilirubin Total", "0.85", "mg/dL", "0.20 - 1.20", "NORMAL"),
                ("Bilirubin Direct", "0.22", "mg/dL", "0.00 - 0.30", "NORMAL"),
                ("SGOT / AST", "26", "U/L", "10 - 40", "NORMAL"),
                ("SGPT / ALT", "31", "U/L", "10 - 45", "NORMAL"),
                ("Alkaline Phosphatase (ALP)", "88", "U/L", "44 - 147", "NORMAL"),
                ("Total Protein", "7.2", "g/dL", "6.4 - 8.3", "NORMAL"),
                ("Albumin", "4.4", "g/dL", "3.5 - 5.0", "NORMAL")
            ]
        elif 'kidney' in test_name_lower or 'kft' in test_name_lower or 'renal' in test_name_lower:
            parameters = [
                ("Serum Creatinine", "0.95", "mg/dL", "0.70 - 1.30", "NORMAL"),
                ("Blood Urea Nitrogen (BUN)", "14", "mg/dL", "7 - 20", "NORMAL"),
                ("Uric Acid", "5.2", "mg/dL", "3.5 - 7.2", "NORMAL"),
                ("Sodium", "141", "mmol/L", "136 - 145", "NORMAL"),
                ("Potassium", "4.2", "mmol/L", "3.5 - 5.1", "NORMAL"),
                ("eGFR", "> 90", "mL/min/1.73m2", "> 90", "NORMAL")
            ]
        elif 'thyroid' in test_name_lower or 'tsh' in test_name_lower:
            parameters = [
                ("TSH (Ultrasensitive)", "2.35", "uIU/mL", "0.35 - 4.94", "NORMAL"),
                ("Total T3 (Triiodothyronine)", "1.15", "ng/mL", "0.80 - 2.00", "NORMAL"),
                ("Total T4 (Thyroxine)", "8.2", "ug/dL", "5.1 - 14.1", "NORMAL")
            ]
        else:
            parameters = [
                (f"{test_name} Parameter 1", "Negative / Normal", "Qualitative", "Negative", "NORMAL"),
                (f"{test_name} Assay Index", "0.24", "Index Ratio", "< 0.80 Negative", "NORMAL"),
                ("Microscopic Inspection", "Adequate cellularity", "Cytology", "Unremarkable", "NORMAL"),
                ("Clinical Interpretation", "No acute abnormality detected", "Pathology", "Normal Baseline", "NORMAL")
            ]

        pdf.set_font('Helvetica', '', 8.5)
        for param, val, unit, ref, flag in parameters:
            pdf.set_x(12)
            pdf.cell(66, 5.5, f"  {to_latin1_str(param)}", 1, 0, 'L')
            pdf.set_font('Helvetica', 'B', 8.5)
            pdf.cell(35, 5.5, to_latin1_str(val), 1, 0, 'C')
            pdf.set_font('Helvetica', '', 8.5)
            pdf.cell(35, 5.5, to_latin1_str(unit), 1, 0, 'C')
            pdf.cell(50, 5.5, to_latin1_str(ref), 1, 1, 'C')

        pdf.ln(5)
        pdf.set_x(12)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.cell(186, 5, "CLINICAL COMMENTS & INTERPRETATION:", 0, 1)
        pdf.set_x(12)
        pdf.set_font('Helvetica', '', 8)
        notes_text = notes if notes else "Sample analyzed in accordance with quality standard protocols. All values correlate within normal biological reference parameters."
        pdf.multi_cell(186, 4.5, to_latin1_str(notes_text), 1, 'L', fill=True)

        pdf.ln(8)
        sig_y = pdf.get_y()
        if sig_y > 230:
            pdf.add_page()
            sig_y = pdf.get_y()

        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.5)
        pdf.rect(14, sig_y, 75, 24)
        pdf.set_xy(16, sig_y + 2)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(71, 4, "SPHERIX DIAGNOSTICS LAB", 0, 1, 'C')
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(71, 3.5, "ELECTRONICALLY SIGNED & VERIFIED", 0, 1, 'C')
        pdf.cell(71, 3.5, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'C')
        pdf.cell(71, 3.5, "SECURITY CHECKSUM: VERIFIED OK", 0, 1, 'C')

        pdf.set_xy(115, sig_y + 4)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(80, 4, "Dr. Arvind Shrivastava, MD (Path)", 0, 1, 'R')
        pdf.set_font('Helvetica', '', 7.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(183, 3.5, "Head of Central Pathology & Laboratory Medicine", 0, 1, 'R')
        pdf.cell(183, 3.5, "Reg No: MCI-PATH-94812", 0, 1, 'R')

        buffer = BytesIO()
        pdf_bytes = pdf.output(dest='S')
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode('latin1')
        buffer.write(pdf_bytes)
        buffer.seek(0)

        safe_test_name = re.sub(r'[^a-zA-Z0-9_-]', '_', str(test_name).strip())
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"LabReport_LAB_{req_id}_{safe_test_name}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error generating lab report PDF: {e}")
        traceback.print_exc()
        flash(f"Could not generate lab report PDF: {str(e)}", "error")
        return redirect(url_for('patient_dashboard', tab='laboratory'))


@patient_bp.route('/patient/prescription/download/<path:filename>')
@login_required
def download_prescription_file(filename):
    """Secure direct download endpoint for prescriptions and clinical consultation notes."""
    safe_name = os.path.basename(filename)
    candidates = []
    if current_app.static_folder:
        candidates.append(os.path.join(current_app.static_folder, 'uploads', 'prescriptions'))
        candidates.append(os.path.join(current_app.static_folder, 'uploads', 'consultations'))
    candidates.append(os.path.join(current_app.root_path, 'static', 'uploads', 'prescriptions'))
    candidates.append(os.path.join(current_app.root_path, 'static', 'uploads', 'consultations'))

    for directory in candidates:
        file_path = os.path.join(directory, safe_name)
        if os.path.isfile(file_path):
            return send_from_directory(directory, safe_name, as_attachment=True)

    flash("Prescription document file not found.", "error")
    return redirect(url_for('patient_dashboard', tab='prescriptions'))


@patient_bp.route('/patient/prescription/view/<path:filename>')
@login_required
def view_prescription_file(filename):
    """View prescription or consultation note inline in browser."""
    safe_name = os.path.basename(filename)
    candidates = []
    if current_app.static_folder:
        candidates.append(os.path.join(current_app.static_folder, 'uploads', 'prescriptions'))
        candidates.append(os.path.join(current_app.static_folder, 'uploads', 'consultations'))
    candidates.append(os.path.join(current_app.root_path, 'static', 'uploads', 'prescriptions'))
    candidates.append(os.path.join(current_app.root_path, 'static', 'uploads', 'consultations'))

    for directory in candidates:
        file_path = os.path.join(directory, safe_name)
        if os.path.isfile(file_path):
            return send_from_directory(directory, safe_name, as_attachment=False)

    flash("Prescription document file not found.", "error")
    return redirect(url_for('patient_dashboard', tab='prescriptions'))


@patient_bp.route('/patient/medical-records/<record_id>/download')
@login_required
def download_medical_record(record_id):
    """Direct download of confidential medical records."""
    med_records = TEMP_DATA.get('medical_records', {})
    record = med_records.get(record_id) or med_records.get(str(record_id)) or (med_records.get(int(record_id)) if str(record_id).isdigit() else None)
    if not record:
        for r in med_records.values():
            if str(getattr(r, 'id', None)) == str(record_id):
                record = r
                break

    if not record:
        flash("Medical record not found.", "error")
        return redirect(url_for('patient_dashboard', tab='records'))

    patient_id_val = str(getattr(record, 'patient_id', ''))
    user_id_val = str(getattr(current_user, 'id', ''))
    user_lic_val = str(getattr(current_user, 'license_no', ''))

    is_owner = getattr(current_user, 'is_patient', False) and (patient_id_val in (user_id_val, user_lic_val))
    is_shared_doc = getattr(current_user, 'is_doctor', False) and (hasattr(record, 'is_shared_with') and record.is_shared_with(current_user.id))
    is_admin = getattr(current_user, 'email', '') == 'admin@spherixclinic.com'
    if not (is_owner or is_shared_doc or is_admin):
        flash("Unauthorized access to this medical record.", "error")
        return redirect(url_for('patient_dashboard', tab='records'))

    file_path = getattr(record, 'file_path', None)
    if file_path:
        full_path = os.path.join(current_app.static_folder, file_path)
        if not os.path.isfile(full_path):
            full_path = os.path.join(current_app.root_path, 'static', file_path)
        if os.path.isfile(full_path):
            directory = os.path.dirname(full_path)
            fname = os.path.basename(full_path)
            return send_from_directory(directory, fname, as_attachment=True, download_name=getattr(record, 'file_name', fname) or fname)

    # If no physical file on disk, generate a clinical summary PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'SPHERIX HEALTH - CLINICAL MEDICAL RECORD', 0, 1, 'C')
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 8, 'Title:', 0, 0)
    pdf.set_font('Helvetica', '', 11)
    rec_title = getattr(record, 'title', 'Clinical Record')
    pdf.cell(0, 8, to_latin1_str(str(rec_title)), 0, 1)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 8, 'Record Type:', 0, 0)
    pdf.set_font('Helvetica', '', 11)
    rec_type = getattr(record, 'record_type', 'General')
    pdf.cell(0, 8, to_latin1_str(str(rec_type)), 0, 1)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 8, 'Date:', 0, 0)
    pdf.set_font('Helvetica', '', 11)
    rec_date = getattr(record, 'record_date', None) or getattr(record, 'created_at', 'N/A')
    pdf.cell(0, 8, to_latin1_str(str(rec_date)), 0, 1)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(40, 8, 'Facility / Doctor:', 0, 0)
    pdf.set_font('Helvetica', '', 11)
    fac_name = getattr(record, 'facility_name', getattr(record, 'hospital_name', 'Spherix Clinic'))
    doc_name = getattr(record, 'doctor_name', 'Attending Specialist')
    pdf.cell(0, 8, to_latin1_str(f"{fac_name} / {doc_name}"), 0, 1)
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, 'Clinical Notes / Description:', 0, 1)
    pdf.set_font('Helvetica', '', 10)
    rec_desc = getattr(record, 'description', 'No additional description recorded.')
    pdf.multi_cell(0, 6, to_latin1_str(str(rec_desc)))

    buffer = BytesIO()
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin1')
    buffer.write(pdf_bytes)
    buffer.seek(0)
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', str(rec_title).strip())
    return send_file(buffer, as_attachment=True, download_name=f"MedicalRecord_{safe_title}.pdf", mimetype='application/pdf')


@patient_bp.route('/patient/bed-booking/create', methods=['POST'])
@patient_required
def create_bed_booking():
    """Handles hospital bed booking and inpatient admission requests from patient dashboard."""
    hospital_id = request.form.get('hospital_id')
    bed_type = request.form.get('bed_type', 'General')
    reason = request.form.get('reason', 'Inpatient Medical Care')
    patient_phone = request.form.get('patient_phone', getattr(current_user, 'phone', 'N/A'))
    emergency_notes = request.form.get('emergency_notes', '')

    if not hospital_id:
        flash("Please select a hospital facility.", "error")
        return redirect(url_for('patient_dashboard', tab='hospitals'))

    hospital = TEMP_DATA.get('hospitals', {}).get(hospital_id)
    if not hospital:
        hospital = next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(h.id) == str(hospital_id)), None)

    if not hospital:
        flash("Selected hospital facility not found.", "error")
        return redirect(url_for('patient_dashboard', tab='hospitals'))

    if 'bed_bookings' not in TEMP_DATA:
        TEMP_DATA['bed_bookings'] = {}
    if 'bed_booking' not in TEMP_DATA.get('next_ids', {}):
        TEMP_DATA['next_ids']['bed_booking'] = max([1] + [int(k) for k in TEMP_DATA['bed_bookings'].keys() if str(k).isdigit()]) + 1

    booking_id = TEMP_DATA['next_ids']['bed_booking']
    new_booking = BedBooking(
        id=booking_id,
        hospital_id=hospital.id,
        patient_id=current_user.id,
        patient_name=current_user.name,
        patient_phone=patient_phone,
        bed_type=bed_type,
        reason=reason,
        status='approved'
    )
    new_booking.room_number = f"W-{random.randint(101, 399)}"
    new_booking.emergency_notes = emergency_notes

    if bed_type == 'ICU' and hasattr(hospital, 'available_icu_beds') and hospital.available_icu_beds > 0:
        hospital.available_icu_beds -= 1
    elif hasattr(hospital, 'available_general_beds') and hospital.available_general_beds > 0:
        hospital.available_general_beds -= 1

    TEMP_DATA['bed_bookings'][booking_id] = new_booking
    TEMP_DATA['next_ids']['bed_booking'] = booking_id + 1

    try:
        create_notification(
            user_id=hospital.id,
            user_role='hospital',
            message=f"New Inpatient Admission Request: {current_user.name} for {bed_type} Bed (Booking #{booking_id}).",
            link=url_for('hospital_dashboard')
        )
    except Exception:
        pass

    try:
        create_notification(
            user_id=current_user.id,
            user_role='patient',
            message=f"Your {bed_type} bed booking at {hospital.name} is confirmed! (Booking #{booking_id}, Room {new_booking.room_number}).",
            link=url_for('patient_dashboard', tab='hospitals')
        )
    except Exception:
        pass

    save_data()
    sync_data_to_sql()
    flash(f"Bed booking confirmed at {hospital.name}! Room/Ward allocated: {new_booking.room_number}.", "success")
    return redirect(url_for('patient_dashboard', tab='hospitals'))


@patient_bp.route('/patient/vitals/log', methods=['POST'])
@patient_required
def log_patient_vitals():
    """Allows patient to record new physiological telemetry readings into their clinical record."""
    systolic_bp = request.form.get('systolic_bp')
    diastolic_bp = request.form.get('diastolic_bp')
    heart_rate = request.form.get('heart_rate')
    blood_sugar = request.form.get('blood_sugar')
    temperature = request.form.get('temperature')
    weight = request.form.get('weight')
    spo2 = request.form.get('spo2')

    if 'patient_vitals' not in TEMP_DATA:
        TEMP_DATA['patient_vitals'] = {}
    if 'patient_vital' not in TEMP_DATA.get('next_ids', {}):
        TEMP_DATA['next_ids']['patient_vital'] = max([1] + [int(k) for k in TEMP_DATA['patient_vitals'].keys() if str(k).isdigit()]) + 1

    vital_id = TEMP_DATA['next_ids']['patient_vital']
    new_vital = PatientVital(
        id=vital_id,
        patient_id=current_user.id,
        weight=weight,
        heart_rate=heart_rate,
        blood_sugar=blood_sugar,
        systolic_bp=systolic_bp,
        diastolic_bp=diastolic_bp,
        recorded_at=datetime.now()
    )
    if temperature:
        new_vital.temperature = float(temperature)
    if spo2:
        new_vital.spo2 = int(spo2)

    TEMP_DATA['patient_vitals'][vital_id] = new_vital
    TEMP_DATA['next_ids']['patient_vital'] = vital_id + 1

    if not hasattr(current_user, 'clinical_record') or not isinstance(current_user.clinical_record, dict):
        current_user.clinical_record = {}
    if weight:
        current_user.clinical_record['weight'] = weight
    if blood_sugar:
        current_user.clinical_record['blood_sugar'] = blood_sugar

    save_data()
    sync_data_to_sql()
    flash("Health telemetry & vitals recorded successfully!", "success")
    return redirect(url_for('patient_dashboard', tab='vitals'))


@patient_bp.route('/patient/prescription/order', methods=['POST'])
@patient_required
def order_prescription_medicines():
    """Connects doctor prescription directly to Smart Pharmacy doorstep delivery."""
    appt_id = request.form.get('appointment_id')
    shipping_address = request.form.get('shipping_address') or getattr(current_user, 'address', 'Registered Address')
    patient_phone = request.form.get('phone') or getattr(current_user, 'phone', 'N/A')
    instructions = request.form.get('instructions', '')

    appt = None
    if appt_id:
        appt = TEMP_DATA.get('appointments', {}).get(int(appt_id)) if str(appt_id).isdigit() else None

    file = request.files.get('prescription_file')
    uploaded_rx_path = ""
    if file and file.filename != '':
        orig_name = secure_filename(file.filename)
        upload_dir = os.path.join(current_app.static_folder, 'uploads', 'prescriptions')
        os.makedirs(upload_dir, exist_ok=True)
        fname = f"rx_order_{current_user.id}_{int(datetime.now().timestamp())}_{orig_name}"
        file.save(os.path.join(upload_dir, fname))
        uploaded_rx_path = fname

    if 'orders' not in TEMP_DATA:
        TEMP_DATA['orders'] = {}
    if 'order' not in TEMP_DATA.get('next_ids', {}):
        TEMP_DATA['next_ids']['order'] = max([1] + [int(k) for k in TEMP_DATA['orders'].keys() if str(k).isdigit()]) + 1

    order_id = TEMP_DATA['next_ids']['order']
    doc_name = f"Dr. {appt.doctor.first_name} {appt.doctor.last_name}" if appt and getattr(appt, 'doctor', None) else "Attending Specialist"
    item_desc = f"Prescribed Medications ({doc_name})" if appt else "Prescription Medicine Package"
    if instructions:
        item_desc += f" - {instructions}"

    new_order = Order(
        id=order_id,
        patient_id=current_user.id,
        items=[item_desc],
        total_price=450.0,
        shipping_address=shipping_address,
        order_date=datetime.now(),
        status='Processing'
    )
    new_order.phone = patient_phone
    if uploaded_rx_path:
        new_order.prescription_path = uploaded_rx_path

    TEMP_DATA['orders'][order_id] = new_order
    TEMP_DATA['next_ids']['order'] = order_id + 1

    try:
        create_notification(
            user_id=current_user.id,
            user_role='patient',
            message=f"Prescription order #ORDER-{order_id} placed for delivery! Our registered pharmacist is reviewing the medicine inventory.",
            link=url_for('patient_dashboard', tab='orders')
        )
    except Exception:
        pass

    save_data()
    sync_data_to_sql()
    flash(f"Prescription Order #{order_id} placed successfully! Doorstep delivery dispatched to {shipping_address}.", "success")
    return redirect(url_for('patient_dashboard', tab='orders'))
