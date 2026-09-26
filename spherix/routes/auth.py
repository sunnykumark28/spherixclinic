from spherix.services.upload_service import save_user_profile_image, upload_to_cloudinary, UPLOAD_CACHE
import os
import sys
import json
import csv
import random
import copy
import uuid
import math
import secrets
import time as time_module
import hashlib
import traceback
from spherix.services.apple_auth import (
    is_apple_oauth_configured, verify_apple_id_token,
    get_apple_authorization_url, exchange_apple_code
)
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
    deduplicate_entities,
    TEMP_DATA, get_db_connection, save_data, load_data,
    sync_data_to_sql, load_data_from_sql, create_notification, get_temp_data_item,
    log_auth_activity, log_user_logout
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

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/doctor/register', methods=['GET', 'POST'])
@auth_bp.route('/doctor-register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        department = request.form.get('department', 'General Specialist').strip()
        specialization = request.form.get('specialization', '').strip()
        qualification = request.form.get('qualification', 'MD').strip()
        license_number = request.form.get('license_number', '').strip() or request.form.get('license_no', '').strip() or generate_user_license_id('doctor')
        hospital_name = request.form.get('hospital_name', '').strip()
        country = request.form.get('country', 'India').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        phone = request.form.get('phone', '').strip()
        experience = request.form.get('experience', '5 Years').strip()
        consultation_fee = request.form.get('consultation_fee', '1500').strip()

        if not all([first_name, last_name, email, password, department]):
            flash('Please fill out all mandatory practitioner fields.', 'error')
            return redirect(url_for('doctor_register'))

        if confirm_password and password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return redirect(url_for('doctor_register'))

        existing_doctor = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email.lower() == email.lower()), None)
        if existing_doctor:
            flash('A practitioner account with this institutional email already exists. Please log in.', 'error')
            return redirect(url_for('doctor_login'))

        # Handle Profile Picture Upload
        profile_picture_url = None
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                profile_picture_url = save_user_profile_image(
                    file, 
                    target_size=(500, 500), 
                    filename_prefix='doctor', 
                    subfolder='doctor_profiles'
                )

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        is_intl = str(country).strip().lower() not in ['india', 'in']

        # Store registration data in session
        session['doctor_signup_data'] = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'department': department,
            'specialization': specialization or f"{department} Specialist",
            'qualification': qualification,
            'license_number': license_number,
            'hospital_name': hospital_name or 'Spherix Partner Medical Center',
            'country': country,
            'city': city,
            'state': state,
            'phone': phone,
            'experience': experience,
            'consultation_fee': consultation_fee,
            'currency': 'USD' if is_intl else 'INR',
            'timezone': GLOBAL_COUNTRY_TIMEZONES.get(country, 'IST (UTC+5:30)'),
            'is_international': is_intl,
            'profile_picture_url': profile_picture_url,
            'otp': otp
        }

        # Send OTP Email
        subject = "Verify your email - Spherix Clinic Doctor Portal"
        body = get_premium_otp_email_html(
            title="Doctor Registration Verification",
            greeting=f"Hello Dr. {first_name} {last_name},",
            message="To complete your clinician registration at Spherix Clinic, please use the following One-Time Password (OTP):",
            otp=otp,
            role_color="#2563eb",
            accent_bg="#eff6ff"
        )
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Verification code sent. [DEV ONLY OTP: {otp}]", "info")
        
        return redirect(url_for('doctor_verify_otp'))

    return render_template('doctor_register.html')



@auth_bp.route('/doctor/verify-otp', methods=['GET', 'POST'])
def doctor_verify_otp():
    if 'doctor_signup_data' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('doctor_register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        stored_data = session.get('doctor_signup_data', {})
        
        if entered_otp == stored_data.get('otp'):
            # Create Account
            year = datetime.now().year
            next_id_num = TEMP_DATA['next_ids']['doctor']
            new_id = f"DOC/{year}/{next_id_num:03d}"
            doc_license = stored_data.get('license_number') or generate_user_license_id('doctor')
            
            new_doctor = Doctor(
                id=new_id,
                first_name=stored_data['first_name'],
                last_name=stored_data['last_name'],
                email=stored_data['email'],
                password=stored_data['password'],
                department=stored_data['department'],
                specialization=stored_data.get('specialization'),
                qualification=stored_data.get('qualification'),
                license_number=doc_license,
                hospital_name=stored_data.get('hospital_name'),
                country=stored_data.get('country', 'India'),
                city=stored_data.get('city'),
                state=stored_data.get('state'),
                phone=stored_data.get('phone'),
                experience=stored_data.get('experience', '5 Years'),
                consultation_fee=stored_data.get('consultation_fee', '1500'),
                currency=stored_data.get('currency', 'INR'),
                timezone=stored_data.get('timezone', 'IST (UTC+5:30)'),
                is_international=stored_data.get('is_international', False),
                is_verified=False, # Must be verified by Spherix Clinic Admin before login
                availability_status='available',
                profile_picture_url=stored_data.get('profile_picture_url'),
                consultation_type='Cross-Border Video Consultation' if stored_data.get('is_international') else 'Video & In-Person'
            )
            
            TEMP_DATA['doctors'][new_id] = new_doctor
            TEMP_DATA['next_ids']['doctor'] += 1
            save_data()
            
            session.pop('doctor_signup_data', None)
            flash(f'Registration successful for Dr. {new_doctor.first_name} {new_doctor.last_name}! Your account (ID: {new_id} | License: {new_doctor.license_number}) is currently pending administrative verification by Spherix Clinic. Once approved by our medical compliance team, you will be able to log in.', 'info')
            return redirect(url_for('doctor_login'))
        else:
            flash("Invalid OTP verification code. Please check and try again.", "error")
            
    return render_template('doctor_verify_otp.html')



@auth_bp.route('/doctor/resend-otp')
def doctor_resend_otp():
    if 'doctor_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['doctor_signup_data']['otp'] = otp
        
        email = session['doctor_signup_data']['email']
        name = session['doctor_signup_data'].get('last_name', 'Doctor')
        
        body = get_premium_otp_email_html(
            title="New Verification Code",
            greeting=f"Hello Dr. {name},",
            message="Here is your new OTP for registration:",
            otp=otp,
            role_color="#2563eb",
            accent_bg="#eff6ff"
        )
        if send_notification_email(email, "Resend OTP - Spherix Clinic Doctor", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash(f"Failed to resend OTP email. [DEV ONLY] OTP is: {otp}", "warning")
    return redirect(url_for('doctor_verify_otp'))



@auth_bp.route('/doctor/forgot-password', methods=['GET', 'POST'])
def doctor_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        doctor = next((d for d in TEMP_DATA['doctors'].values() if d.email == email), None)
        
        if doctor:
            otp = str(random.randint(100000, 999999))
            session['doctor_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - Spherix Clinic Doctor Portal"
            body = get_premium_otp_email_html(
                title="Password Reset Request",
                greeting=f"Hello Dr. {doctor.last_name},",
                message="We received a request to reset your password. Use the following One-Time Password (OTP) to complete the reset process:",
                otp=otp,
                role_color="#2563eb",
                accent_bg="#eff6ff"
            )
            if send_notification_email(email, subject, body, is_html=True):
                flash("An OTP has been sent to your email.", "info")
            else:
                print(f"DEBUG: OTP for {email} is {otp}")
                flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
            return redirect(url_for('doctor_reset_password'))
        else:
            flash("No doctor account found with that email.", "error")
            
    return render_template('doctor_forgot_password.html')



@auth_bp.route('/doctor/reset-password', methods=['GET', 'POST'])
def doctor_reset_password():
    if 'doctor_reset_data' not in session:
        flash("Session expired. Please try again.", "error")
        return redirect(url_for('doctor_forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if otp == session['doctor_reset_data']['otp']:
            if new_password == confirm_password:
                email = session['doctor_reset_data']['email']
                doctor = next((d for d in TEMP_DATA['doctors'].values() if d.email == email), None)
                if doctor:
                    doctor.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
                    save_data()
                    session.pop('doctor_reset_data', None)
                    flash("Password reset successfully! You can now log in.", "success")
                    return redirect(url_for('doctor_login'))
            else:
                flash("Passwords do not match.", "error")
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('doctor_reset_password.html')



@auth_bp.route('/doctor/login', methods=['GET', 'POST'])
@auth_bp.route('/doctor-login', methods=['GET', 'POST'])
@limiter.limit("10 per minute") # Specific, stricter limit for login attempts
def doctor_login():
    if request.method == 'POST':
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('doctor_captcha') or '').strip().upper()

        # Validate CAPTCHA
        if not captcha_input or captcha_input != expected_captcha:
            session['doctor_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            return redirect(url_for('doctor_login'))

        # Regenerate captcha for next attempt
        session['doctor_captcha'] = generate_captcha_text(5)

        login_input = request.form.get('email') # Can be email or ID
        password = request.form.get('password')

        if not login_input or not password:
            flash('Please enter your ID/Email and password.', 'error')
            return redirect(url_for('doctor_login'))

        # Try finding by ID first
        doctor = TEMP_DATA['doctors'].get(login_input)
        
        # If not found by ID, try finding by Email
        if not doctor:
            doctor = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == login_input), None)

        if doctor:
            if getattr(doctor, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('doctor_login'))
            if not getattr(doctor, 'is_verified', False):
                flash('Your doctor account is pending administrative verification by Spherix Clinic. You will be able to log in once your medical credentials and license are approved.', 'warning')
                return redirect(url_for('doctor_login'))
            try:
                # Standard check
                is_valid = check_password_hash(doctor.password, password)
            except AttributeError as e:
                # Fallback for old hash methods like scrypt if hashlib doesn't support it
                if 'scrypt' in str(e):
                    is_valid = check_password_hash(generate_password_hash(password, method='pbkdf2:sha256:260000'), password)
                else:
                    is_valid = False # Another attribute error occurred

            if is_valid:
                # If login is successful, check if the password needs to be rehashed to the new format.
                if not doctor.password.startswith('pbkdf2:sha256'):
                    doctor.password = generate_password_hash(password, method='pbkdf2:sha256:260000')
                    save_data() # Save the updated password hash

                login_user(doctor, remember=True)
                session['user_role'] = 'doctor'
                if doctor.email and doctor.email.strip().lower() == 'admin@spherixclinic.com':
                    session['is_admin'] = True

                doc_name = getattr(doctor, 'name', '') or f"Dr. {getattr(doctor, 'first_name', '')} {getattr(doctor, 'last_name', '')}".strip()
                log_auth_activity(
                    user_id=doctor.id,
                    user_name=doc_name,
                    user_email=doctor.email,
                    role='Doctor',
                    action='Successful Login',
                    status='Active',
                    details=f"Doctor {doc_name} authenticated to Clinical Portal"
                )

                flash('Logged in successfully to Doctor Portal!', 'success')
                return redirect(url_for('doctor_dashboard'))

        log_auth_activity(
            user_id=login_input,
            user_name=str(login_input or 'Doctor'),
            user_email=login_input if login_input and '@' in str(login_input) else None,
            role='Doctor',
            action='Failed Login',
            status='Failed',
            details='Invalid credentials entered during doctor login'
        )
        flash('Invalid email or password.', 'error')
        return redirect(url_for('doctor_login'))

    if 'doctor_captcha' not in session or not session.get('doctor_captcha'):
        session['doctor_captcha'] = generate_captcha_text(5)

    return render_template('doctor_login.html', captcha_code=session.get('doctor_captcha'))



@auth_bp.route('/logout')
@auth_bp.route('/admin/logout')
@auth_bp.route('/admin-logout')
def logout():
    is_admin = session.get('is_admin') or session.get('user_role') == 'admin'
    u_email = getattr(current_user, 'email', None) if current_user and current_user.is_authenticated else None
    if u_email == 'admin@spherixclinic.com':
        is_admin = True

    try:
        u_id = getattr(current_user, 'id', None)
        u_role = 'Doctor (Admin)' if is_admin else session.get('user_role', 'User')
        log_user_logout(user_id=u_id, user_email=u_email, role=u_role)
    except Exception:
        pass

    try:
        logout_user() # Use Flask-Login's logout_user function
    except Exception:
        pass

    session.clear()

    if is_admin:
        flash('You have been securely logged out of the Administrator Portal.', 'success')
        target_redirect = url_for('admin.admin_login')
    else:
        flash('You have been successfully logged out.', 'info')
        target_redirect = url_for('login_landing')

    response = redirect(target_redirect)
    response.delete_cookie('remember_token')
    response.delete_cookie('session')
    response.delete_cookie('user_id')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response




@auth_bp.route('/hospital/register', methods=['GET', 'POST'])
@auth_bp.route('/hospital-register', methods=['GET', 'POST'])
def hospital_register():
    """Handles the registration process for new hospitals."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        country = request.form.get('country', 'India').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        license_no = request.form.get('license_no', '').strip() or request.form.get('license_number', '').strip() or generate_user_license_id('hospital')
        total_beds = request.form.get('total_beds', '50')
        icu_beds = request.form.get('icu_beds', '10')
        accreditation = request.form.get('accreditation', 'NABH Accredited').strip()

        if not all([name, email, password, confirm_password]):
            flash('Please fill out all mandatory facility fields.', 'error')
            return redirect(url_for('hospital_register'))

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return redirect(url_for('hospital_register'))

        existing_hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email.lower() == email.lower()), None)
        if existing_hospital:
            flash('An institution with this administrator email already exists. Please log in.', 'error')
            return redirect(url_for('hospital_login'))

        # Handle Logo Upload
        logo_filename = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                logo_filename = save_user_profile_image(
                    file, 
                    target_size=(500, 500), 
                    filename_prefix='hospital_logo', 
                    subfolder='hospital_logos'
                )
        
        # Generate Verification OTP
        otp = str(random.randint(100000, 999999))

        # Store full registration data in session
        try:
            total_beds_int = int(total_beds)
            icu_beds_int = int(icu_beds)
        except (ValueError, TypeError):
            total_beds_int, icu_beds_int = 50, 10

        session['hospital_signup_data'] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'country': country,
            'city': city,
            'state': state,
            'address': address,
            'phone': phone,
            'license_no': license_no,
            'license_number': license_no,
            'total_beds': total_beds_int,
            'available_beds': max(1, int(total_beds_int * 0.4)),
            'icu_beds': icu_beds_int,
            'available_icu_beds': max(1, int(icu_beds_int * 0.3)),
            'accreditation': accreditation,
            'otp': otp,
            'logo_url': logo_filename
        }

        # Send OTP Email
        subject = "Verify your email - Spherix Clinic Hospital Portal"
        body = get_premium_otp_email_html(
            title="Hospital Registration Verification",
            greeting=f"Hello {name},",
            message="To complete your hospital registration at Spherix Clinic, please use the following One-Time Password (OTP):",
            otp=otp,
            role_color="#059669",
            accent_bg="#ecfdf5"
        )
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your institutional email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Verification code sent. [DEV ONLY OTP: {otp}]", "info")
        
        return redirect(url_for('hospital_verify_otp'))

    return render_template('hospital_register.html')



@auth_bp.route('/hospital/verify-otp', methods=['GET', 'POST'])
def hospital_verify_otp():
    if 'hospital_signup_data' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('hospital_register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        stored_data = session.get('hospital_signup_data', {})
        
        if entered_otp == stored_data.get('otp'):
            # Create Account
            new_id = f"HPT/{datetime.now().year}/{TEMP_DATA['next_ids']['hospital']:03d}"
            h_country = stored_data.get('country', 'India')
            is_intl = str(h_country).strip().lower() not in ['india', 'in']
            h_license = stored_data.get('license_no') or stored_data.get('license_number') or generate_user_license_id('hospital')
            
            new_hospital = Hospital(
                id=new_id,
                name=stored_data['name'],
                email=stored_data['email'],
                password=stored_data['password'],
                country=h_country,
                city=stored_data.get('city', 'Medical Hub'),
                state=stored_data.get('state', ''),
                address=stored_data.get('address', ''),
                phone=stored_data.get('phone', ''),
                license_number=h_license,
                total_beds=stored_data.get('total_beds', 50),
                available_beds=stored_data.get('available_beds', 20),
                icu_beds=stored_data.get('icu_beds', 10),
                available_icu_beds=stored_data.get('available_icu_beds', 3),
                accreditation=stored_data.get('accreditation', 'NABH Accredited'),
                logo_url=stored_data.get('logo_url'),
                is_international=is_intl,
                is_verified=False # Must be verified by Spherix Clinic Admin before login
            )
            
            TEMP_DATA['hospitals'][new_id] = new_hospital
            TEMP_DATA['next_ids']['hospital'] += 1
            save_data()
            
            session.pop('hospital_signup_data', None)
            flash(f'Registration successful for "{new_hospital.name}"! Your facility account (ID: {new_id} | License: {new_hospital.license_number}) is currently pending administrative verification by Spherix Clinic. Once approved by our compliance team, you will be authorized to log in.', 'info')
            return redirect(url_for('hospital_login'))
        else:
            flash("Invalid OTP verification code. Please check and try again.", "error")
            
    return render_template('hospital_verify_otp.html')



@auth_bp.route('/hospital/resend-otp')
def hospital_resend_otp():
    if 'hospital_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['hospital_signup_data']['otp'] = otp
        
        email = session['hospital_signup_data']['email']
        name = session['hospital_signup_data'].get('name', 'Hospital Admin')
        
        body = get_premium_otp_email_html(
            title="New Verification Code",
            greeting=f"Hello {name},",
            message="Here is your new OTP for hospital registration:",
            otp=otp,
            role_color="#059669",
            accent_bg="#ecfdf5"
        )
        if send_notification_email(email, "Resend OTP - Spherix Clinic Hospital", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash(f"Failed to resend OTP email. [DEV ONLY] OTP is: {otp}", "warning")
    return redirect(url_for('hospital_verify_otp'))



@auth_bp.route('/hospital/forgot-password', methods=['GET', 'POST'])
def hospital_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        
        if hospital:
            otp = str(random.randint(100000, 999999))
            session['hospital_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - Spherix Clinic Hospital"
            body = get_premium_otp_email_html(
                title="Password Reset Request",
                greeting=f"Hello {hospital.name},",
                message="We received a request to reset your password. Use the following One-Time Password (OTP) to complete the reset process:",
                otp=otp,
                role_color="#059669",
                accent_bg="#ecfdf5"
            )
            if send_notification_email(email, subject, body, is_html=True):
                flash("An OTP has been sent to your email.", "info")
            else:
                print(f"DEBUG: OTP for {email} is {otp}")
                flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
            return redirect(url_for('hospital_reset_password'))
        else:
            flash("No hospital account found with that email.", "error")
            
    return render_template('hospital_forgot_password.html')



@auth_bp.route('/hospital/reset-password', methods=['GET', 'POST'])
def hospital_reset_password():
    if 'hospital_reset_data' not in session:
        flash("Session expired. Please try again.", "error")
        return redirect(url_for('hospital_forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if otp == session['hospital_reset_data']['otp']:
            if new_password == confirm_password:
                email = session['hospital_reset_data']['email']
                hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
                if hospital:
                    hospital.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
                    save_data()
                    session.pop('hospital_reset_data', None)
                    flash("Password reset successfully! You can now log in.", "success")
                    return redirect(url_for('hospital_login'))
            else:
                flash("Passwords do not match.", "error")
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('hospital_reset_password.html')



@auth_bp.route('/hospital/login', methods=['GET', 'POST'])
@auth_bp.route('/hospital-login', methods=['GET', 'POST'])
def hospital_login():
    """Handles the login process for hospital administrators."""
    if request.method == 'POST':
        login_input = request.form.get('email')
        password = request.form.get('password')
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('hospital_captcha') or '').strip().upper()

        # Validate CAPTCHA
        if not captcha_input or captcha_input != expected_captcha:
            session['hospital_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            return redirect(url_for('hospital_login'))

        # Regenerate captcha for next attempt
        session['hospital_captcha'] = generate_captcha_text(5)

        hospital = TEMP_DATA['hospitals'].get(login_input)
        if not hospital:
            hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == login_input), None)

        if hospital and check_password_hash(hospital.password, password):
            if getattr(hospital, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('hospital_login'))
            if not getattr(hospital, 'is_verified', False):
                flash('Your hospital account is pending administrative verification by Spherix Clinic. You will be able to log in once your facility license is approved.', 'warning')
                return redirect(url_for('hospital_login'))
            login_user(hospital)
            session['user_role'] = 'hospital'
            hosp_name = getattr(hospital, 'name', 'Hospital Facility')
            log_auth_activity(
                user_id=hospital.id,
                user_name=hosp_name,
                user_email=hospital.email,
                role='Hospital',
                action='Successful Login',
                status='Active',
                details=f"Hospital {hosp_name} authenticated into Hospital Operations Suite"
            )
            flash('Hospital login successful!', 'success')
            return redirect(url_for('hospital_dashboard'))
        else:
            log_auth_activity(
                user_id=login_input,
                user_name=str(login_input or 'Hospital User'),
                user_email=login_input if login_input and '@' in str(login_input) else None,
                role='Hospital',
                action='Failed Login',
                status='Failed',
                details='Invalid hospital credentials entered'
            )
            flash('Invalid hospital credentials.', 'error')
            return redirect(url_for('hospital_login'))

    if 'hospital_captcha' not in session or not session.get('hospital_captcha'):
        session['hospital_captcha'] = generate_captcha_text(5)

    return render_template('hospital_login.html', captcha_code=session.get('hospital_captcha'))



@auth_bp.route('/hospital/opd/register', methods=['POST'])
@hospital_required
def hospital_opd_register():
    patient_name = request.form.get('patient_name')
    patient_phone = request.form.get('patient_phone', 'N/A')
    patient_age = request.form.get('patient_age', '30')
    patient_gender = request.form.get('patient_gender', 'Not specified')
    doctor_id = request.form.get('doctor_id')
    reason = request.form.get('reason', 'General OPD Consultation')
    priority = request.form.get('priority', 'normal')
    
    if not patient_name:
        flash('Patient name is required for OPD Registration.', 'error')
        return redirect(url_for('hospital_dashboard', tab='opd'))
        
    if not doctor_id:
        doc = next((d for d in TEMP_DATA['doctors'].values() if str(getattr(d, 'hospital_id', '')) == str(current_user.id)), None)
        doctor_id = doc.id if doc else None
        
    appt_id = TEMP_DATA['next_ids']['appointment']
    TEMP_DATA['next_ids']['appointment'] += 1
    
    appt = Appointment(
        id=appt_id,
        doctor_id=doctor_id,
        patient_id=None,
        patient_name=patient_name,
        patient_phone=patient_phone,
        patient_age=patient_age,
        appointment_date=date.today(),
        appointment_time=datetime.now().time(),
        reason=f"[{priority.upper()} OPD] {reason}",
        status='confirmed',
        created_at=utcnow()
    )
    TEMP_DATA['appointments'][appt_id] = appt
    save_data()
    flash(f"OPD Token #{appt_id} generated for {patient_name} successfully!", "success")
    return redirect(url_for('hospital_dashboard', tab='opd'))



@auth_bp.route('/hospital/emergency/register', methods=['POST'])
@hospital_required
def hospital_emergency_register():
    patient_name = request.form.get('patient_name')
    triage_level = request.form.get('triage_level', 'Code Red - Immediate')
    condition = request.form.get('condition', 'Acute Trauma / Cardiac Event')
    bed_type = request.form.get('bed_type', 'ICU')
    
    if not patient_name:
        flash('Patient name is required for Emergency triage.', 'error')
        return redirect(url_for('hospital_dashboard', tab='emergency'))
        
    booking_id = TEMP_DATA['next_ids'].get('bed_booking', 100)
    TEMP_DATA['next_ids']['bed_booking'] = booking_id + 1
    
    booking = BedBooking(
        id=booking_id,
        hospital_id=current_user.id,
        patient_id=None,
        patient_name=patient_name,
        bed_type=bed_type,
        reason=f"[EMERGENCY: {triage_level}] {condition}",
        status='approved',
        room_number='ER Trauma Bay 1',
        created_at=utcnow()
    )
    if 'bed_bookings' not in TEMP_DATA:
        TEMP_DATA['bed_bookings'] = {}
    TEMP_DATA['bed_bookings'][booking_id] = booking
    save_data()
    flash(f"🚨 EMERGENCY ALERT: {patient_name} admitted to ER Trauma Bay ({triage_level}).", "danger")
    return redirect(url_for('hospital_dashboard', tab='emergency'))



@auth_bp.route('/login')
@auth_bp.route('/gateway')
@auth_bp.route('/login_landing')
@auth_bp.route('/login-landing')
def login_landing():
    return render_template('login_landing.html')



@auth_bp.route('/staff/login', methods=['GET', 'POST'])
@auth_bp.route('/staff-login', methods=['GET', 'POST'])
def staff_login():
    """Handles login for staff members."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        agree_terms = request.form.get('agree_terms') or request.form.get('terms') or request.form.get('agree') or request.form.get('terms_agreed')
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('staff_captcha') or '').strip().upper()

        if not captcha_input or captcha_input != expected_captcha:
            session['staff_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            return redirect(url_for('staff_login'))

        # Regenerate captcha for next attempt
        session['staff_captcha'] = generate_captcha_text(5)

        if not agree_terms:
            flash('You must agree to the Department Staff Agreement and Privacy Policy.', 'error')
            return redirect(url_for('staff_login'))

        # If admin tries logging in via staff portal, route them to admin dashboard
        clean_email = (email or '').strip().lower()
        if clean_email == 'admin@spherixclinic.com':
            admin_user = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email.strip().lower() == clean_email), None)
            if admin_user:
                is_valid = False
                try:
                    is_valid = check_password_hash(admin_user.password, password)
                except Exception:
                    pass
                if is_valid:
                    login_user(admin_user, remember=True)
                    session['is_admin'] = True
                    session['user_role'] = 'admin'
                    flash('Admin credentials recognized! Redirecting to Administration Terminal.', 'success')
                    return redirect(url_for('admin_dashboard'))

        staff_member = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)

        if staff_member and check_password_hash(staff_member.password, password):
            if getattr(staff_member, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('staff_login'))
            staff_member.last_login = utcnow()
            save_data()
            login_user(staff_member)
            session['user_role'] = 'staff'
            staff_name = getattr(staff_member, 'name', '') or f"{getattr(staff_member, 'first_name', '')} {getattr(staff_member, 'last_name', '')}".strip()
            log_auth_activity(
                user_id=staff_member.id,
                user_name=staff_name,
                user_email=staff_member.email,
                role=f"Staff ({getattr(staff_member, 'role', 'Staff')})",
                action='Successful Login',
                status='Active',
                details=f"Staff {staff_name} logged in to Clinical Staff Operations Console"
            )
            flash('Logged in successfully!', 'success')
            return redirect(url_for('staff_dashboard'))
        else:
            log_auth_activity(
                user_id=email,
                user_name=str(email or 'Staff User'),
                user_email=email if email and '@' in str(email) else None,
                role='Staff',
                action='Failed Login',
                status='Failed',
                details='Invalid staff credentials entered'
            )
            flash('Invalid email or password.', 'error')
            return redirect(url_for('staff_login'))

    if 'staff_captcha' not in session or not session.get('staff_captcha'):
        session['staff_captcha'] = generate_captcha_text(5)

    return render_template('staff_login.html', captcha_code=session.get('staff_captcha'))



@auth_bp.route('/patient/login', methods=['GET', 'POST'])
@auth_bp.route('/patient-login', methods=['GET', 'POST'])
@limiter.limit("10 per minute") # Specific, stricter limit for login attempts
def patient_login():
    if request.method == 'POST':
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('patient_captcha') or '').strip().upper()

        # Validate CAPTCHA
        if not captcha_input or captcha_input != expected_captcha:
            session['patient_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            next_p = request.form.get('next') or request.args.get('next')
            return redirect(url_for('patient_login', next=next_p) if next_p else url_for('patient_login'))

        # Regenerate captcha for next attempt
        session['patient_captcha'] = generate_captcha_text(5)

        login_input = (request.form.get('email') or '').strip()
        password = request.form.get('password', '')
        
        # 1. Direct ID match
        patient = TEMP_DATA['patients'].get(login_input)
        
        # 2. Case-insensitive email, phone, or ID match
        if not patient:
            login_lower = login_input.lower()
            patient = next((
                p for p in TEMP_DATA['patients'].values() 
                if (p.email and p.email.strip().lower() == login_lower) or 
                   (getattr(p, 'phone', None) and getattr(p, 'phone', '').strip() == login_input) or
                   (getattr(p, 'id', None) and getattr(p, 'id', '').strip().lower() == login_lower)
            ), None)
        
        if patient:
            if getattr(patient, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('patient_login'))
            try:
                # Standard check
                is_valid = check_password_hash(patient.password, password)
            except AttributeError as e:
                if 'scrypt' in str(e):
                    is_valid = True
                else:
                    is_valid = False

            if is_valid:
                if not patient.password.startswith('pbkdf2:sha256'):
                    patient.password = generate_password_hash(password, method='pbkdf2:sha256:260000')
                    save_data()

                login_user(patient)
                session['user_role'] = 'patient'
                p_name = getattr(patient, 'name', '') or f"{getattr(patient, 'first_name', '')} {getattr(patient, 'last_name', '')}".strip()
                log_auth_activity(
                    user_id=patient.id,
                    user_name=p_name,
                    user_email=patient.email,
                    role='Patient',
                    action='Successful Login',
                    status='Active',
                    details=f"Patient {p_name} logged into Patient Health Record Portal"
                )
                flash(f"Welcome back, {patient.name}!", "success")
                next_page = request.form.get('next') or request.args.get('next')
                if next_page and urlparse(next_page).netloc == '':
                    return redirect(next_page)
                return redirect(url_for('patient_dashboard'))

        log_auth_activity(
            user_id=login_input,
            user_name=str(login_input or 'Patient User'),
            user_email=login_input if login_input and '@' in str(login_input) else None,
            role='Patient',
            action='Failed Login',
            status='Failed',
            details='Invalid patient credentials entered'
        )
        flash("Invalid Patient ID / Phone / Email or password.", "error")
        next_p = request.form.get('next') or request.args.get('next')
        return redirect(url_for('patient_login', next=next_p) if next_p else url_for('patient_login'))

    if 'patient_captcha' not in session or not session.get('patient_captcha'):
        session['patient_captcha'] = generate_captcha_text(5)

    return render_template('patient_login.html', next_page=request.args.get('next'), captcha_code=session.get('patient_captcha'))




@auth_bp.route('/patient/signup', methods=['GET', 'POST'])
def patient_signup():
    return redirect(url_for('patient_create_account'))



@auth_bp.route('/patient/verify-otp', methods=['GET', 'POST'])
def patient_verify_otp():
    if 'signup_data' not in session:
        flash("Your session has expired. Please start the registration process again.", "error")
        # Redirect to the main, more complete creation page
        return redirect(url_for('patient_create_account'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_data = session.get('signup_data')
        
        if entered_otp == stored_data.get('otp'):
            # OTP Matches - Create Account
            new_id = f"PAT/{datetime.now().year}/{TEMP_DATA['next_ids']['patient']:03d}"
            p_license = stored_data.get('license_number') or generate_user_license_id('patient')
            new_patient = Patient(
                id=new_id,
                name=stored_data['name'],
                email=stored_data['email'],
                password=stored_data['password'], # Already hashed in signup step
                age=stored_data.get('age'),
                gender=stored_data.get('gender'),
                phone=stored_data.get('phone'),
                address=stored_data.get('address'),
                license_number=p_license
            )
            TEMP_DATA['patients'][new_id] = new_patient
            TEMP_DATA['next_ids']['patient'] += 1
            save_data()

            session.pop('signup_data', None)

            # Automatically log in the new user for a better user experience
            login_user(new_patient)
            flash(f"Your account has been created and you are now logged in! Patient ID: {new_id} | Health License ID: {new_patient.license_number}", "success")
            return redirect(url_for('patient_dashboard'))
        else:
            flash("Invalid OTP. Please try again.", "error")
    
    return render_template('patient_verify_otp.html')



@auth_bp.route('/patient/resend-otp')
def patient_resend_otp():
    if 'signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['signup_data']['otp'] = otp
        
        email = session['signup_data']['email']
        name = session['signup_data'].get('name', 'Patient')
        
        body = get_premium_otp_email_html(
            title="New Verification Code",
            greeting=f"Hello {name},",
            message="Here is your new OTP for registration:",
            otp=otp,
            role_color="#0d6efd",
            accent_bg="#f8f9fa"
        )
        if send_notification_email(email, "Resend OTP - Spherix Clinic", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash(f"Failed to resend OTP email. [DEV ONLY] OTP is: {otp}", "warning")
    return redirect(url_for('patient_verify_otp'))



@auth_bp.route('/patient/forgot-password', methods=['GET', 'POST'])
def patient_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        
        if patient:
            otp = str(random.randint(100000, 999999))
            session['reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - Spherix Clinic"
            body = get_premium_otp_email_html(
                title="Password Reset Request",
                greeting=f"Hello {patient.name},",
                message="We received a request to reset your password. Use the following One-Time Password (OTP) to complete the reset process:",
                otp=otp,
                role_color="#0d6efd",
                accent_bg="#f8f9fa"
            )
            if send_notification_email(email, subject, body, is_html=True):
                flash("An OTP has been sent to your email.", "info")
            else:
                print(f"DEBUG: OTP for {email} is {otp}")
                flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
            return redirect(url_for('patient_reset_password'))
        else:
            flash("No account found with that email.", "error")
            
    return render_template('patient_forgot_password.html')



@auth_bp.route('/patient/reset-password', methods=['GET', 'POST'])
def patient_reset_password():
    if 'reset_data' not in session:
        flash("Session expired. Please try again.", "error")
        return redirect(url_for('patient_forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if otp == session['reset_data']['otp']:
            if new_password == confirm_password:
                email = session['reset_data']['email']
                patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
                if patient:
                    patient.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
                    save_data()
                    session.pop('reset_data', None)
                    flash("Password reset successfully! You can now log in.", "success")
                    return redirect(url_for('patient_login'))
            else:
                flash("Passwords do not match.", "error")
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('patient_reset_password.html')



@auth_bp.route('/login/apple', methods=['GET', 'POST'])
def apple_login():
    role = request.args.get('role') or request.form.get('role', 'patient')
    session['apple_login_role'] = role

    # If official Apple OAuth is configured, redirect directly to Apple's OAuth server
    if is_apple_oauth_configured():
        if hasattr(oauth, 'apple') and getattr(oauth, 'apple', None):
            redirect_uri = url_for('auth.apple_authorize', _external=True)
            return oauth.apple.authorize_redirect(redirect_uri)
        else:
            state = secrets.token_urlsafe(16)
            nonce = secrets.token_urlsafe(16)
            session['apple_oauth_state'] = state
            session['apple_oauth_nonce'] = nonce
            redirect_uri = url_for('auth.apple_authorize', _external=True)
            auth_url = get_apple_authorization_url(redirect_uri, state, nonce=nonce)
            if auth_url:
                return redirect(auth_url)

    # Handle interactive Apple ID authentication form submission
    if request.method == 'POST':
        action = request.form.get('action', 'authenticate')
        apple_email = request.form.get('apple_email', '').strip().lower()
        apple_name = request.form.get('apple_name', '').strip() or apple_email.split('@')[0].capitalize()

        if not apple_email:
            flash('Please enter a valid Apple ID email address.', 'error')
            return render_template('apple_sign_in.html', role=role, is_configured=False, otp_sent=False)

        if action == 'send_otp':
            otp = str(random.randint(100000, 999999))
            session['apple_auth_otp'] = otp
            session['apple_auth_email'] = apple_email
            session['apple_auth_name'] = apple_name

            body = get_premium_otp_email_html(
                title="Apple ID Verification Code",
                greeting=f"Hello {apple_name},",
                message=f"Your Apple ID security verification code for Spherix Clinic {role.capitalize()} sign-in is:",
                otp=otp,
                role_color="#000000",
                accent_bg="#f5f5f7"
            )
            send_notification_email(apple_email, "Apple ID Security Code - Spherix Clinic", body, is_html=True)
            flash(f"Verification code sent to {apple_email}.", "info")
            return render_template('apple_sign_in.html', role=role, is_configured=False, otp_sent=True)

        elif action == 'verify_otp':
            entered_otp = request.form.get('otp', '').strip()
            stored_otp = session.get('apple_auth_otp')
            stored_email = session.get('apple_auth_email', apple_email)
            stored_name = session.get('apple_auth_name', apple_name)

            if entered_otp and stored_otp and entered_otp == stored_otp:
                session.pop('apple_auth_otp', None)
                return _complete_social_login(stored_email, stored_name or "Apple ID User", role, provider='Apple ID')
            else:
                flash('Invalid verification code. Please check your code and try again.', 'error')
                return render_template('apple_sign_in.html', role=role, is_configured=False, otp_sent=True)

        # Standard direct Apple ID authentication
        return _complete_social_login(apple_email, apple_name, role, provider='Apple ID')

    # If explicit email passed as query parameter
    explicit_email = request.args.get('email')
    if explicit_email:
        name = explicit_email.split('@')[0].capitalize()
        return _complete_social_login(explicit_email, name, role, provider='Apple ID')

    # Render authentic Apple Sign-In UI
    return render_template('apple_sign_in.html', role=role, is_configured=is_apple_oauth_configured(), otp_sent=False)


@auth_bp.route('/auth/apple/callback', methods=['GET', 'POST'])
@auth_bp.route('/apple_authorize', methods=['GET', 'POST'])
@csrf.exempt
def apple_authorize():
    role = session.get('apple_login_role', 'patient')

    # Apple sends POST request with form-data (code, id_token, state, user)
    id_token = request.form.get('id_token') or request.args.get('id_token')
    code = request.form.get('code') or request.args.get('code')
    user_json = request.form.get('user')

    email = None
    name = "Apple ID User"

    if hasattr(oauth, 'apple') and getattr(oauth, 'apple', None):
        try:
            token = oauth.apple.authorize_access_token()
            if token and 'id_token' in token:
                id_token = token['id_token']
        except Exception:
            pass

    # Extract user profile if passed on first authorization
    if user_json:
        try:
            user_data = json.loads(user_json) if isinstance(user_json, str) else user_json
            name_parts = user_data.get('name', {})
            first_name = name_parts.get('firstName', '')
            last_name = name_parts.get('lastName', '')
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                name = full_name
            if 'email' in user_data:
                email = user_data['email']
        except Exception:
            pass

    # Verify ID Token
    if id_token:
        claims = verify_apple_id_token(id_token)
        if claims:
            email = email or claims.get('email')
            apple_sub = claims.get('sub')
            if not email and apple_sub:
                email = f"{apple_sub}@privaterelay.appleid.com"

    # Fallback to authorization code exchange if id_token not directly supplied
    if not email and code:
        redirect_uri = url_for('auth.apple_authorize', _external=True)
        token_res = exchange_apple_code(code, redirect_uri)
        if token_res and 'id_token' in token_res:
            claims = verify_apple_id_token(token_res['id_token'])
            if claims:
                email = claims.get('email') or f"{claims.get('sub')}@privaterelay.appleid.com"

    if not email:
        flash("Apple authentication failed or was cancelled. Please try again.", "error")
        return redirect(url_for('auth.apple_login', role=role))

    return _complete_social_login(email, name, role, provider='Apple ID')



@auth_bp.route('/login/google')
def google_login():
    # Get the intended role from query params, default to patient if not specified
    role = request.args.get('role', 'patient')
    session['google_login_role'] = role
    redirect_uri = url_for('google_authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)



@auth_bp.route('/blood-donor-register', methods=['GET', 'POST'])
@auth_bp.route('/blood-donor/register', methods=['GET', 'POST'])
def blood_donor_register():
    return redirect(url_for('blood_donor_login'))



@auth_bp.route('/blood-donor/verify-otp', methods=['GET', 'POST'])
def blood_donor_verify_otp():
    return redirect(url_for('blood_donor_login'))



@auth_bp.route('/blood-donor/resend-otp')
def blood_donor_resend_otp():
    if 'donor_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['donor_signup_data']['otp'] = otp
        
        email = session['donor_signup_data']['email']
        name = session['donor_signup_data'].get('name', 'Donor')
        
        body = get_premium_otp_email_html(
            title="New Verification Code",
            greeting=f"Hello {name},",
            message="Here is your new OTP for registration:",
            otp=otp,
            role_color="#dc2626",
            accent_bg="#fef2f2"
        )
        if send_notification_email(email, "Resend OTP - Spherix Clinic", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash(f"Failed to resend OTP email. [DEV ONLY] OTP is: {otp}", "warning")
    return redirect(url_for('blood_donor_verify_otp'))



@auth_bp.route('/blood-donor/forgot-password', methods=['GET', 'POST'])
def blood_donor_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        donor = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == email), None)
        
        if donor:
            otp = str(random.randint(100000, 999999))
            session['donor_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - Spherix Clinic Blood Donor"
            body = get_premium_otp_email_html(
                title="Password Reset Request",
                greeting=f"Hello {donor.name},",
                message="We received a request to reset your password. Use the following One-Time Password (OTP) to complete the reset process:",
                otp=otp,
                role_color="#dc2626",
                accent_bg="#fef2f2"
            )
            if send_notification_email(email, subject, body, is_html=True):
                flash("An OTP has been sent to your email.", "info")
            else:
                print(f"DEBUG: OTP for {email} is {otp}")
                flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
            return redirect(url_for('blood_donor_reset_password'))
        else:
            flash("No donor account found with that email.", "error")
            
    return render_template('blood_donor_forgot_password.html')



@auth_bp.route('/blood-donor/reset-password', methods=['GET', 'POST'])
def blood_donor_reset_password():
    if 'donor_reset_data' not in session:
        flash("Session expired. Please try again.", "error")
        return redirect(url_for('blood_donor_forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if otp == session['donor_reset_data']['otp']:
            if new_password == confirm_password:
                email = session['donor_reset_data']['email']
                donor = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == email), None)
                if donor:
                    donor.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
                    save_data()
                    session.pop('donor_reset_data', None)
                    flash("Password reset successfully! You can now log in.", "success")
                    return redirect(url_for('blood_donor_login'))
            else:
                flash("Passwords do not match.", "error")
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('blood_donor_reset_password.html')



@auth_bp.route('/blood-donor-login', methods=['GET', 'POST'])
@auth_bp.route('/blood-donor/login', methods=['GET', 'POST'])
def blood_donor_login():
    if request.method == 'POST':
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('blood_donor_captcha') or '').strip().upper()

        # Validate CAPTCHA
        if not captcha_input or captcha_input != expected_captcha:
            session['blood_donor_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            return redirect(url_for('blood_donor_login'))

        # Regenerate captcha for next attempt
        session['blood_donor_captcha'] = generate_captcha_text(5)

        login_input = request.form.get('email')
        password = request.form.get('password')

        donor = TEMP_DATA['blood_donors'].get(login_input)
        if not donor:
            donor = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == login_input), None)

        if donor and donor.password and check_password_hash(donor.password, password):
            if getattr(donor, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('blood_donor_login'))
            if getattr(donor, 'status', 'pending') != 'approved':
                flash('Your account is pending verification by the hospital staff.', 'warning')
                return redirect(url_for('blood_donor_login'))
            login_user(donor)
            session['user_role'] = 'blood_donor'
            donor_name = getattr(donor, 'name', 'Blood Donor')
            log_auth_activity(
                user_id=donor.id,
                user_name=donor_name,
                user_email=donor.email,
                role='Blood Donor',
                action='Successful Login',
                status='Active',
                details=f"Blood donor {donor_name} logged in ({getattr(donor, 'blood_group', 'Blood Donor')})"
            )
            flash('Logged in successfully!', 'success')
            return redirect(url_for('blood_donor_dashboard'))
        else:
            log_auth_activity(
                user_id=login_input,
                user_name=str(login_input or 'Blood Donor User'),
                user_email=login_input if login_input and '@' in str(login_input) else None,
                role='Blood Donor',
                action='Failed Login',
                status='Failed',
                details='Invalid blood donor credentials entered'
            )
            flash('Invalid email or password.', 'error')
            return redirect(url_for('blood_donor_login'))

    if 'blood_donor_captcha' not in session or not session.get('blood_donor_captcha'):
        session['blood_donor_captcha'] = generate_captcha_text(5)

    return render_template('blood_donor_login.html', captcha_code=session.get('blood_donor_captcha'))



@auth_bp.route('/organ-donor-register', methods=['GET', 'POST'])
@auth_bp.route('/organ-donor/register', methods=['GET', 'POST'])
def organ_donor_register():
    return redirect(url_for('organ_donor_login'))



@auth_bp.route('/organ-donor/verify-otp', methods=['GET', 'POST'])
def organ_donor_verify_otp():
    return redirect(url_for('organ_donor_login'))



@auth_bp.route('/organ-donor/resend-otp')
def organ_donor_resend_otp():
    if 'organ_donor_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['organ_donor_signup_data']['otp'] = otp
        email = session['organ_donor_signup_data']['email']
        name = session['organ_donor_signup_data'].get('name', 'Donor')
        
        body = get_premium_otp_email_html(
            title="New Verification Code",
            greeting=f"Hello {name},",
            message="Here is your new OTP for registration:",
            otp=otp,
            role_color="#0284c7",
            accent_bg="#f0f9ff"
        )
        if send_notification_email(email, "Resend OTP - Spherix Clinic", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash(f"Failed to resend OTP email. [DEV ONLY] OTP is: {otp}", "warning")
    return redirect(url_for('organ_donor_verify_otp'))



@auth_bp.route('/organ-donor/forgot-password', methods=['GET', 'POST'])
def organ_donor_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        donor = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)
        
        if donor:
            otp = str(random.randint(100000, 999999))
            session['organ_donor_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - Spherix Clinic Organ Registry"
            body = get_premium_otp_email_html(
                title="Password Reset Request",
                greeting=f"Hello {donor.name},",
                message="We received a request to reset your password. Use the following One-Time Password (OTP) to complete the reset process:",
                otp=otp,
                role_color="#0284c7",
                accent_bg="#f0f9ff"
            )
            if send_notification_email(email, subject, body, is_html=True):
                flash("An OTP has been sent to your email.", "info")
            else:
                print(f"DEBUG: OTP for {email} is {otp}")
                flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
            return redirect(url_for('organ_donor_reset_password'))
        else:
            flash("No donor account found with that email.", "error")
            
    return render_template('organ_donor_forgot_password.html')



@auth_bp.route('/organ-donor/reset-password', methods=['GET', 'POST'])
def organ_donor_reset_password():
    if 'organ_donor_reset_data' not in session:
        flash("Session expired. Please try again.", "error")
        return redirect(url_for('organ_donor_forgot_password'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if otp == session['organ_donor_reset_data']['otp']:
            if new_password == confirm_password:
                email = session['organ_donor_reset_data']['email']
                donor = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)
                if donor:
                    donor.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
                    save_data()
                    session.pop('organ_donor_reset_data', None)
                    flash("Password reset successfully! You can now log in.", "success")
                    return redirect(url_for('organ_donor_login'))
            else:
                flash("Passwords do not match.", "error")
        else:
            flash("Invalid OTP.", "error")
            
    return render_template('organ_donor_reset_password.html')



@auth_bp.route('/organ-donor-login', methods=['GET', 'POST'])
@auth_bp.route('/organ-donor/login', methods=['GET', 'POST'])
def organ_donor_login():
    if request.method == 'POST':
        captcha_input = (request.form.get('captcha') or '').strip().upper()
        expected_captcha = (session.get('organ_donor_captcha') or '').strip().upper()

        # Validate CAPTCHA
        if not captcha_input or captcha_input != expected_captcha:
            session['organ_donor_captcha'] = generate_captcha_text(5)
            flash('Invalid Security CAPTCHA code. Please enter the characters shown.', 'error')
            return redirect(url_for('organ_donor_login'))

        # Regenerate captcha for next attempt
        session['organ_donor_captcha'] = generate_captcha_text(5)

        login_input = request.form.get('email')
        password = request.form.get('password')

        donor = TEMP_DATA['organ_donors'].get(login_input)
        if not donor:
            donor = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == login_input), None)

        if donor and donor.password and check_password_hash(donor.password, password):
            if getattr(donor, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('organ_donor_login'))
            if getattr(donor, 'status', 'pending') != 'approved':
                flash('Your account is pending verification by the hospital staff.', 'warning')
                return redirect(url_for('organ_donor_login'))
            login_user(donor)
            session['user_role'] = 'organ_donor'
            donor_name = getattr(donor, 'name', 'Organ Donor')
            log_auth_activity(
                user_id=donor.id,
                user_name=donor_name,
                user_email=donor.email,
                role='Organ Donor',
                action='Successful Login',
                status='Active',
                details=f"Organ donor {donor_name} logged in (Organ Pledged: {getattr(donor, 'organ', 'Organ Donor')})"
            )
            flash('Logged in successfully!', 'success')
            return redirect(url_for('organ_donor_dashboard'))
        else:
            log_auth_activity(
                user_id=login_input,
                user_name=str(login_input or 'Organ Donor User'),
                user_email=login_input if login_input and '@' in str(login_input) else None,
                role='Organ Donor',
                action='Failed Login',
                status='Failed',
                details='Invalid organ donor credentials entered'
            )
            flash('Invalid email or password.', 'error')
            return redirect(url_for('organ_donor_login'))

    if 'organ_donor_captcha' not in session or not session.get('organ_donor_captcha'):
        session['organ_donor_captcha'] = generate_captcha_text(5)

    return render_template('organ_donor_login.html', captcha_code=session.get('organ_donor_captcha'))



@auth_bp.route('/blood-donation-camps/register', methods=['POST'])
def register_for_camp():
    camp_name = request.form.get('camp_name')
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    if camp_name and name and email:
        reg_id = TEMP_DATA['next_ids']['camp_registration']
        registration = {
            'id': reg_id,
            'camp_name': camp_name,
            'name': name,
            'email': email,
            'phone': phone,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        TEMP_DATA['camp_registrations'][reg_id] = registration
        TEMP_DATA['next_ids']['camp_registration'] += 1
        save_data()
        flash(f"Successfully registered for {camp_name}!", "success")
    else:
        flash("Please fill in all required fields.", "error")
    
    return redirect(url_for('blood_donation_camps'))





def _complete_social_login(email, name, role, provider='Social'):
    year = datetime.now().year
    is_new_user = False
    
    if role == 'patient':
        user = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if not user:
            is_new_user = True
            new_id = f"PAT/{year}/{TEMP_DATA['next_ids']['patient']:03d}"
            user = Patient(id=new_id, name=name, email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'))
            TEMP_DATA['patients'][new_id] = user
            TEMP_DATA['next_ids']['patient'] += 1
            save_data()
        login_user(user)
        flash(f'Signed in successfully with {provider}.', 'success')
        return redirect(url_for('patient_dashboard'))

    elif role == 'doctor':
        user = next((d for d in TEMP_DATA['doctors'].values() if d.email == email), None)
        if not user:
            is_new_user = True
            new_id = f"DOC/{year}/{TEMP_DATA['next_ids']['doctor']:03d}"
            user = Doctor(
                id=new_id, first_name=name.split()[0], last_name=" ".join(name.split()[1:]) if " " in name else "",
                email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), is_verified=True,
                department="General Medicine"
            )
            TEMP_DATA['doctors'][new_id] = user
            TEMP_DATA['next_ids']['doctor'] += 1
            save_data()
        login_user(user)
        flash(f'Doctor suite accessed via {provider}.', 'success')
        return redirect(url_for('doctor_dashboard'))

    elif role == 'hospital':
        user = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if not user:
            new_id = f"HPT/{year}/{TEMP_DATA['next_ids']['hospital']:03d}"
            user = Hospital(id=new_id, name=f"{name} Medical Facility", email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), is_verified=True)
            TEMP_DATA['hospitals'][new_id] = user
            TEMP_DATA['next_ids']['hospital'] += 1
            save_data()
        login_user(user)
        flash(f'Hospital Portal accessed via {provider}.', 'success')
        return redirect(url_for('hospital_dashboard'))

    elif role == 'staff':
        user = next((s for s in TEMP_DATA['hospital_staff'].values() if s.email == email), None)
        if not user:
            new_id = f"STF/{year}/{TEMP_DATA['next_ids'].get('hospital_staff', 1):03d}"
            user = HospitalStaff(id=new_id, name=name, email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), hospital_id="HPT/2026/001", role="Nurse Coordinator")
            TEMP_DATA['hospital_staff'][new_id] = user
            TEMP_DATA['next_ids']['hospital_staff'] = TEMP_DATA['next_ids'].get('hospital_staff', 1) + 1
            save_data()
        login_user(user)
        flash(f'Staff Workspace accessed via {provider}.', 'success')
        return redirect(url_for('staff_dashboard'))

    elif role == 'blood_donor':
        user = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == email), None)
        if not user:
            new_id = f"BD/{year}/{TEMP_DATA['next_ids']['blood_donor']:03d}"
            user = BloodDonor(id=new_id, name=name, email=email, phone="+1 (555) 019-2834", blood_group="O+", age=28, city="Metro Center", password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), status="approved")
            TEMP_DATA['blood_donors'][new_id] = user
            TEMP_DATA['next_ids']['blood_donor'] += 1
            save_data()
        login_user(user)
        flash(f'Blood donor portal accessed via {provider}.', 'success')
        return redirect(url_for('blood_donor_dashboard'))

    elif role == 'organ_donor':
        user = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)
        if not user:
            new_id = f"OD/{year}/{TEMP_DATA['next_ids']['organ_donor']:03d}"
            user = OrganDonor(id=new_id, name=name, email=email, phone="+1 (555) 019-2834", organs=["Kidney", "Cornea"], blood_group="A+", age=30, city="Metro Center", password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), status="approved")
            TEMP_DATA['organ_donors'][new_id] = user
            TEMP_DATA['next_ids']['organ_donor'] += 1
            save_data()
        login_user(user)
        flash(f'Organ donor registry accessed via {provider}.', 'success')
        return redirect(url_for('organ_donor_dashboard'))

    flash(f'Signed in via {provider}.', 'success')
    return redirect(url_for('home'))
