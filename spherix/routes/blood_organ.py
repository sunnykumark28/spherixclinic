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

blood_organ_bp = Blueprint('blood_organ', __name__)

@blood_organ_bp.route('/hospital/<path:hospital_id>/organ_inquiry', methods=['POST'])
def hospital_organ_inquiry(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    name = request.form.get('name')
    email = request.form.get('email')
    organ_needed = request.form.get('organ_needed')
    blood_group = request.form.get('blood_group')
    message = request.form.get('message')

    if name and email and organ_needed and blood_group and message:
        # Send transplant inquiry email
        subject = f"Organ Transplant / Request Inquiry from {name} - {hospital.name}"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #4f46e5;">Organ Transplant Inquiry</h2>
            <p><strong>From:</strong> {name} ({email})</p>
            <p><strong>Organ Needed:</strong> {organ_needed.capitalize()}</p>
            <p><strong>Blood Group:</strong> {blood_group}</p>
            <p><strong>Message / Demands:</strong></p>
            <div style="background: #eef2ff; padding: 15px; border-left: 4px solid #4f46e5; border-radius: 4px;">
                {message}
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">This message was sent via the hospital organ transplant portal.</p>
        </div>
        """
        if hospital.email:
            send_notification_email(hospital.email, subject, body, is_html=True)
            flash("Your request has been submitted to the hospital's transplant coordinator team.", "success")
        else:
            flash("This hospital does not have a registered email for inquiries.", "warning")
            
        if socketio:
            socketio.emit('new_organ_inquiry', {
                'name': name,
                'email': email,
                'organ_needed': organ_needed,
                'blood_group': blood_group,
                'message': message,
                'time': datetime.now().strftime('%I:%M %p')
            # pyrefly: ignore [unexpected-keyword]
            }, room=f'hospital_{hospital.id}')
    else:
        flash("Please fill out all fields.", "error")

    return redirect(url_for('hospital_detail', hospital_id=hospital_id))



@blood_organ_bp.route('/hospital/<path:hospital_id>/blood_inquiry', methods=['POST'])
def hospital_blood_inquiry(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    if name and email and message:
        subject = f"Blood Bank Inquiry from {name} - {hospital.name}"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #e11d48;">Blood Bank Inquiry</h2>
            <p><strong>From:</strong> {name} ({email})</p>
            <p><strong>Message:</strong></p>
            <div style="background: #fff1f2; padding: 15px; border-left: 4px solid #e11d48; border-radius: 4px;">
                {message}
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">This message was sent via the hospital blood bank portal.</p>
        </div>
        """
        if hospital.email:
            send_notification_email(hospital.email, subject, body, is_html=True)
            flash("Your message has been sent to the hospital's blood bank team.", "success")
        else:
            flash("This hospital does not have a registered email for inquiries.", "warning")
            
        if socketio:
            socketio.emit('new_blood_inquiry', {
                'name': name,
                'email': email,
                'message': message,
                'time': datetime.now().strftime('%I:%M %p')
            # pyrefly: ignore [unexpected-keyword]
            }, room=f'hospital_{hospital.id}')
    else:
        flash("Please fill out all fields.", "error")

    return redirect(url_for('hospital_detail', hospital_id=hospital_id))



@blood_organ_bp.route('/admin/export/camp-registrations')
@admin_required
def export_camp_registrations():
    """Exports camp registrations to a CSV file."""
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Camp Name', 'Name', 'Email', 'Phone'])
    
    registrations = list(TEMP_DATA.get('camp_registrations', {}).values())
    for reg in registrations:
        cw.writerow([
            reg.get('date', ''),
            reg.get('camp_name', ''),
            reg.get('name', ''),
            reg.get('email', ''),
            reg.get('phone', '')
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=camp_registrations.csv"
    output.headers["Content-type"] = "text/csv"
    return output



@blood_organ_bp.route('/hospital/organ-donor/<path:donor_id>/contact', methods=['POST'])
@hospital_or_staff_role_required('Organ Donor Management')
def hospital_contact_organ_donor(donor_id):
    donor_id = parse_route_id(donor_id)
    donor = TEMP_DATA.get('organ_donors', {}).get(donor_id)
    is_hospital = getattr(current_user, 'is_hospital', False)
    dash_url = 'hospital_dashboard' if is_hospital else 'staff_dashboard'

    if not donor:
        flash("Organ donor not found.", "error")
        return redirect(url_for(dash_url) + '#organ_donors')

    subject = request.form.get('subject', 'Message from Hospital')
    message = request.form.get('message')

    if not message:
        flash("Message cannot be empty.", "error")
        return redirect(url_for(dash_url) + '#organ_donors')

    hospital_name = current_user.name if is_hospital else current_user.hospital_name
    
    body = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #0284c7;">Message from {hospital_name}</h2>
        <p>Dear {donor.name},</p>
            <p>You have received a secure message from <strong>{hospital_name}</strong> via the Spherix Clinic Organ Donor Network:</p>
        <div style="background: #f0f9ff; padding: 15px; border-left: 4px solid #0284c7; border-radius: 4px; margin: 20px 0;">
            {message}
        </div>
        <p>Please contact the hospital directly if you have any questions or to follow up.</p>
    </div>
    """
    
    if send_notification_email(donor.email, subject, body, is_html=True):
        flash(f"Message sent to {donor.name} successfully.", "success")
    else:
        flash("Failed to send message. Please check email configuration.", "error")
        
    return redirect(url_for(dash_url) + '#organ_donors')




@blood_organ_bp.route('/staff/dashboard/blood', methods=['GET', 'POST'])
@staff_role_required('Blood Donor Management')
def staff_blood_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    tab = request.args.get('tab', 'overview')

    if not hospital:
        flash("Hospital not found for your staff account.", "error")
        return redirect(url_for('staff_dashboard'))
    
    # This is required for the KPI card to work correctly.
    # In a real app, you'd fetch this from the database based on the hospital.
    camps = [c for c in TEMP_DATA.get('camps', {}).values() if c.get('organizer') == hospital_name]

    if request.method == 'POST' and hospital:
        if 'edit_blood_donor' in request.form:
            donor_id = parse_route_id(request.form.get('donor_id', ''))
            if donor_id in TEMP_DATA.get('blood_donors', {}):
                donor = TEMP_DATA['blood_donors'][donor_id]
                donor.name = request.form.get('name', donor.name)
                donor.email = request.form.get('email', donor.email)
                donor.phone = request.form.get('phone', donor.phone)
                donor.blood_group = request.form.get('blood_group', donor.blood_group)
                donor.city = request.form.get('city', donor.city)
                save_data()
                flash(f"Donor '{donor.name}' updated successfully.", "success")
            target_tab = request.form.get('redirect_tab', 'donor_management')
            return redirect(url_for('staff_blood_dashboard', tab=target_tab))
        elif 'delete_blood_donor' in request.form:
            donor_id = parse_route_id(request.form.get('donor_id', ''))
            if donor_id in TEMP_DATA.get('blood_donors', {}):
                donor_name = TEMP_DATA['blood_donors'][donor_id].name
                del TEMP_DATA['blood_donors'][donor_id]
                save_data()
                flash(f"Donor '{donor_name}' has been deleted.", "success")
            target_tab = request.form.get('redirect_tab', 'donor_management')
            return redirect(url_for('staff_blood_dashboard', tab=target_tab))
        elif 'approve_blood_donor' in request.form:
            donor_id = parse_route_id(request.form.get('donor_id', ''))
            if donor_id in TEMP_DATA.get('blood_donors', {}):
                TEMP_DATA['blood_donors'][donor_id].status = 'approved'
                save_data()
                flash("Blood donor registration approved.", "success")
        elif 'reject_blood_donor' in request.form:
            donor_id = parse_route_id(request.form.get('donor_id', ''))
            if donor_id in TEMP_DATA.get('blood_donors', {}):
                TEMP_DATA['blood_donors'][donor_id].status = 'rejected'
                save_data()
                flash("Blood donor registration rejected.", "success")
        elif 'staff_add_blood_donor' in request.form:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            phone = request.form.get('phone')
            blood_group = request.form.get('blood_group')
            age = int(request.form.get('age', 0))
            city = request.form.get('city')
            last_donation = request.form.get('last_donation')
            
            if not all([name, email, password, phone, blood_group, city]):
                flash("All required fields must be filled.", "error")
            elif any(d.email == email for d in TEMP_DATA['blood_donors'].values()):
                flash("A donor with this email already exists.", "error")
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
                    last_donation=last_donation or None,
                    hospital_id=hospital.id,
                    status='approved'
                )
                TEMP_DATA['blood_donors'][donor_id] = new_donor
                TEMP_DATA['next_ids']['blood_donor'] += 1
                save_data()
                flash(f"New donor '{name}' registered successfully with ID: {donor_id}.", "success")
        elif 'record_donor_donation' in request.form:
            donor_id = parse_route_id(request.form.get('donor_id', ''))
            quantity = int(request.form.get('quantity', 1))
            donation_date_str = request.form.get('donation_date')
            
            if not donation_date_str:
                donation_date_str = date.today().isoformat()
                
            if donor_id in TEMP_DATA.get('blood_donors', {}):
                donor = TEMP_DATA['blood_donors'][donor_id]
                donor.last_donation = donation_date_str
                donor.status = 'approved'
                
                # Update blood stock
                bg = donor.blood_group
                hospital.blood_stock[bg] = hospital.blood_stock.get(bg, 0) + quantity
                
                # Log activity
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Approved & Recorded Donation",
                    details=f"Recorded donation of {quantity} units of {bg} blood for registered donor: {donor.name}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f"Donation of {quantity} units of {bg} recorded for {donor.name}. Certificate is now active.", "success")
        elif 'add_camp' in request.form:
            camp_id = TEMP_DATA['next_ids']['camp']
            TEMP_DATA['camps'][camp_id] = {
                "id": camp_id, "name": request.form.get('name'),
                "location": request.form.get('location'), "date": request.form.get('date'),
                "time": request.form.get('time'), "organizer": hospital_name, "contact": request.form.get('contact')
            }
            TEMP_DATA['next_ids']['camp'] += 1
            save_data()
            flash("Blood donation camp added.", "success")
        elif 'delete_camp' in request.form:
            camp_id = request.form.get('camp_id')
            if camp_id and camp_id.isdigit() and int(camp_id) in TEMP_DATA.get('camps', {}):
                del TEMP_DATA['camps'][int(camp_id)]
                save_data()
                flash("Camp deleted.", "success")
        elif 'delete_camp_registration' in request.form:
            reg_id = request.form.get('reg_id')
            if reg_id and reg_id.isdigit() and int(reg_id) in TEMP_DATA.get('camp_registrations', {}):
                del TEMP_DATA['camp_registrations'][int(reg_id)]
                save_data()
                flash("Camp registration deleted.", "success")
        elif 'issue_blood' in request.form:
            blood_group = request.form.get('blood_group')
            quantity = int(request.form.get('quantity', 0))
            recipient_name = request.form.get('recipient_name', 'Patient')
            
            current_qty = hospital.blood_stock.get(blood_group, 0)
            if current_qty >= quantity:
                hospital.blood_stock[blood_group] = current_qty - quantity
                
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Issued Blood Units",
                    details=f"Issued {quantity} units of {blood_group} blood for recipient: {recipient_name}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f"Successfully issued {quantity} units of {blood_group} blood.", "success")
            else:
                flash(f"Insufficient stock of {blood_group} blood! Available: {current_qty} units.", "error")
        elif 'record_donation' in request.form:
            blood_group = request.form.get('blood_group')
            quantity = int(request.form.get('quantity', 0))
            donor_name = request.form.get('donor_name', 'Anonymous')
            
            hospital.blood_stock[blood_group] = hospital.blood_stock.get(blood_group, 0) + quantity
            
            log_id = TEMP_DATA['next_ids']['activity_log']
            TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                id=log_id,
                hospital_id=hospital.id,
                user_name=current_user.name,
                action="Received Blood Donation",
                details=f"Received {quantity} units of {blood_group} blood from donor: {donor_name}."
            )
            TEMP_DATA['next_ids']['activity_log'] += 1
            
            save_data()
            flash(f"Successfully recorded donation of {quantity} units of {blood_group} blood from {donor_name}.", "success")
        target_tab = request.form.get('redirect_tab', 'overview')
        return redirect(url_for('staff_blood_dashboard', tab=target_tab))
        
    blood_donors = [d for d in TEMP_DATA.get('blood_donors', {}).values() if getattr(d, 'hospital_id', None) == hospital.id or not getattr(d, 'hospital_id', None)]
    blood_stock = hospital.blood_stock if hasattr(hospital, 'blood_stock') else TEMP_DATA.get('blood_stock', {})
    camps = [c for c in TEMP_DATA.get('camps', {}).values() if c.get('organizer') == hospital_name]
    camp_names = [c['name'] for c in camps]
    camp_registrations = [r for r in TEMP_DATA.get('camp_registrations', {}).values() if r.get('camp_name') in camp_names]

    return render_template('staff_blood_dashboard.html', 
                           staff=current_user, hospital=hospital, blood_donors=blood_donors, 
                           blood_stock=blood_stock, camps=camps, camp_registrations=camp_registrations, 
                           activity_logs=activity_logs, tab=tab)



@blood_organ_bp.route('/staff/dashboard/organ', methods=['GET', 'POST'])
@staff_role_required('Organ Donor Management')
def staff_organ_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    tab = request.args.get('tab', 'overview')

    if request.method == 'POST' and hospital:
        donor_id = parse_route_id(request.form.get('donor_id', ''))
        if 'edit_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            donor = TEMP_DATA['organ_donors'][donor_id]
            donor.name, donor.email = request.form.get('name', donor.name), request.form.get('email', donor.email)
            donor.phone, donor.city = request.form.get('phone', donor.phone), request.form.get('city', donor.city)
            donor.blood_group, donor.organs = request.form.get('blood_group', donor.blood_group), request.form.getlist('organs')
            save_data()
            flash("Organ donor updated.", "success")
            return redirect(url_for('staff_organ_dashboard', tab='donor_registry'))
        elif 'delete_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            del TEMP_DATA['organ_donors'][donor_id]
            save_data()
            flash("Organ donor deleted.", "success")
            return redirect(url_for('staff_organ_dashboard', tab='donor_registry'))
        elif 'approve_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            TEMP_DATA['organ_donors'][donor_id].status = 'approved'
            save_data()
            flash("Organ donor pledge approved.", "success")
            return redirect(url_for('staff_organ_dashboard', tab='donor_registry'))
        elif 'reject_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            TEMP_DATA['organ_donors'][donor_id].status = 'rejected'
            save_data()
            flash("Organ donor pledge rejected.", "success")
            return redirect(url_for('staff_organ_dashboard', tab='donor_registry'))
        elif 'add_organ_request' in request.form:
            try:
                if 'organ_request' not in TEMP_DATA['next_ids']:
                    TEMP_DATA['next_ids']['organ_request'] = max([1] + [int(k) for k in TEMP_DATA.get('organ_requests', {}).keys() if str(k).isdigit()]) + 1
                req_id = TEMP_DATA['next_ids']['organ_request']
                patient_name = request.form.get('patient_name')
                organ_needed = request.form.get('organ_needed')
                blood_group = request.form.get('blood_group')
                urgency = request.form.get('urgency')
                
                new_req = OrganRequest(
                    id=req_id,
                    patient_id='walk-in',
                    patient_name=patient_name,
                    organ_needed=organ_needed,
                    blood_group=blood_group,
                    urgency=urgency,
                    status='active',
                    hospital_id=hospital.id
                )
                TEMP_DATA['organ_requests'][req_id] = new_req
                TEMP_DATA['next_ids']['organ_request'] += 1
                
                if 'activity_log' not in TEMP_DATA['next_ids']:
                    TEMP_DATA['next_ids']['activity_log'] = max([1] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Organ Request Registered",
                    details=f"Registered request for {organ_needed} ({blood_group}) for patient {patient_name}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f"Organ request for {organ_needed} ({blood_group}) registered successfully.", "success")
            except Exception as e:
                flash(f"Error adding organ request: {str(e)}", "error")
            return redirect(url_for('staff_organ_dashboard', tab='transplant_requests'))
        elif 'match_donor_to_request' in request.form:
            req_id = parse_route_id(request.form.get('request_id'))
            donor_id = parse_route_id(request.form.get('donor_id'))
            
            req = TEMP_DATA.get('organ_requests', {}).get(req_id)
            donor = TEMP_DATA.get('organ_donors', {}).get(donor_id)
            
            if req and donor and donor.status == 'approved' and req.status == 'active':
                req.status = 'matched'
                donor.status = 'matched'
                
                if 'activity_log' not in TEMP_DATA['next_ids']:
                    TEMP_DATA['next_ids']['activity_log'] = max([1] + [int(k) for k in TEMP_DATA.get('activity_logs', {}).keys() if str(k).isdigit()]) + 1
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Organ Match Approved",
                    details=f"Successfully matched Donor {donor.name} with Patient {req.patient_name} for {req.organ_needed}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash(f"Organ match successful! Donor {donor.name} linked with Patient {req.patient_name}.", "success")
            return redirect(url_for('staff_organ_dashboard', tab='matching_log'))
        return redirect(url_for('staff_organ_dashboard', tab=tab))

    organ_donors = [d for d in TEMP_DATA.get('organ_donors', {}).values() if getattr(d, 'hospital_id', None) == hospital.id or not getattr(d, 'hospital_id', None)]
    organ_requests = [r for r in TEMP_DATA.get('organ_requests', {}).values() if hospital and r.hospital_id == hospital.id]
    
    return render_template('staff_organ_dashboard.html', 
                           staff=current_user, hospital=hospital, organ_donors=organ_donors, 
                           organ_requests=organ_requests, activity_logs=activity_logs, tab=tab)



@blood_organ_bp.route('/api/staff/blood/live-stats')
@staff_required
def staff_blood_live_stats():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    blood_donors = [d for d in TEMP_DATA.get('blood_donors', {}).values() if not getattr(d, 'hospital_id', None) or (hospital and str(d.hospital_id) == str(hospital.id))]
    blood_stock = hospital.blood_stock if hospital and hasattr(hospital, 'blood_stock') and isinstance(hospital.blood_stock, dict) else TEMP_DATA.get('blood_stock', {})
    camps = [c for c in TEMP_DATA.get('camps', {}).values() if not hospital_name or c.get('organizer') == hospital_name]
    
    serialized_donors = []
    for d in blood_donors[:30]:
        serialized_donors.append({
            "id": d.id,
            "name": d.name,
            "email": d.email,
            "phone": d.phone,
            "blood_group": d.blood_group,
            "city": getattr(d, 'city', 'N/A'),
            "status": getattr(d, 'status', 'approved'),
            "last_donation": getattr(d, 'last_donation', 'Never')
        })
        
    return jsonify({
        "success": True,
        "stats": {
            "total_units": sum(blood_stock.values()) if isinstance(blood_stock, dict) else 0,
            "total_donors": len(blood_donors),
            "approved_donors": len([d for d in blood_donors if getattr(d, 'status', '') == 'approved']),
            "pending_donors": len([d for d in blood_donors if getattr(d, 'status', '') == 'pending']),
            "camps_count": len(camps)
        },
        "blood_stock": blood_stock,
        "blood_donors": serialized_donors
    })



@blood_organ_bp.route('/api/staff/organ/live-stats')
@staff_required
def staff_organ_live_stats():
    hospital_name, hospital, activity_logs = get_common_staff_data(current_user)
    
    organ_donors = [d for d in TEMP_DATA.get('organ_donors', {}).values() if not getattr(d, 'hospital_id', None) or (hospital and str(d.hospital_id) == str(hospital.id))]
    organ_requests = [r for r in TEMP_DATA.get('organ_requests', {}).values() if not hospital or str(r.hospital_id) == str(hospital.id)]
    
    serialized_donors = []
    for d in organ_donors[:30]:
        serialized_donors.append({
            "id": d.id,
            "name": d.name,
            "blood_group": d.blood_group,
            "organs": d.organs if isinstance(d.organs, list) else [d.organs],
            "city": getattr(d, 'city', 'N/A'),
            "status": getattr(d, 'status', 'approved')
        })
        
    serialized_requests = []
    for r in organ_requests[:30]:
        serialized_requests.append({
            "id": r.id,
            "patient_name": r.patient_name,
            "organ_needed": r.organ_needed,
            "blood_group": r.blood_group,
            "urgency": r.urgency,
            "status": r.status
        })
        
    return jsonify({
        "success": True,
        "stats": {
            "total_donors": len(organ_donors),
            "active_requests": len([r for r in organ_requests if getattr(r, 'status', '') == 'active']),
            "matched_cases": len([r for r in organ_requests if getattr(r, 'status', '') == 'matched']),
            "pending_pledges": len([d for d in organ_donors if getattr(d, 'status', '') == 'pending'])
        },
        "organ_donors": serialized_donors,
        "organ_requests": serialized_requests
    })



@blood_organ_bp.route('/blood-donor/dashboard', methods=['GET', 'POST'])
@login_required
def blood_donor_dashboard():
    if not isinstance(current_user, BloodDonor):
        flash("Access denied.", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        action = request.form.get('action')
        tab = request.args.get('tab', 'overview')

        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('blood_donor_dashboard', tab='settings'))

            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('blood_donor_dashboard', tab='settings'))

            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
            save_data()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('blood_donor_dashboard', tab='settings'))

        if 'update_profile' in request.form or request.form.get('update_profile'):
            current_user.name = request.form.get('name', current_user.name)
            current_user.phone = request.form.get('phone', current_user.phone)
            current_user.city = request.form.get('city', current_user.city)
            current_user.blood_group = request.form.get('blood_group', current_user.blood_group)
            current_user.last_donation = request.form.get('last_donation', current_user.last_donation)
            
            age = request.form.get('age')
            if age and age.isdigit():
                current_user.age = int(age)
            
            # Handle email update with uniqueness check
            new_email = request.form.get('email')
            if new_email and new_email != current_user.email:
                existing = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == new_email and d.id != current_user.id), None)
                if existing:
                    flash("Email already exists.", "error")
                else:
                    current_user.email = new_email

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
                    filename_prefix=f"bd_profile_{current_user.id}"
                )
                if saved_filename:
                    current_user.profile_picture_url = saved_filename
        
            save_data()
            flash("Profile updated successfully!", "success")
            if request.args.get('tab') == 'settings':
                return redirect(url_for('blood_donor_dashboard', tab='settings'))
            return redirect(url_for('blood_donor_dashboard'))
        
        elif 'delete_account' in request.form:
            donor_id = current_user.id
            logout_user()
            if donor_id in TEMP_DATA['blood_donors']:
                del TEMP_DATA['blood_donors'][donor_id]
                save_data()
            flash("Your account has been deleted.", "success")
            return redirect(url_for('home'))

        elif 'delete_picture' in request.form:
            if current_user.profile_picture_url:
                current_user.profile_picture_url = None
    # Fetch linked hospital and blood bank inventory
    donor_hospital = None
    if getattr(current_user, 'hospital_id', None):
        donor_hospital = TEMP_DATA.get('hospitals', {}).get(current_user.hospital_id)
    if not donor_hospital and getattr(current_user, 'hospital_name', None):
        donor_hospital = next((h for h in TEMP_DATA.get('hospitals', {}).values() if h.name == current_user.hospital_name), None)
    if not donor_hospital and TEMP_DATA.get('hospitals'):
        donor_hospital = next(iter(TEMP_DATA['hospitals'].values()))

    # Live blood stock from staff inventory
    blood_stock = {}
    if donor_hospital and hasattr(donor_hospital, 'blood_stock') and donor_hospital.blood_stock:
        blood_stock = donor_hospital.blood_stock
    else:
        blood_stock = TEMP_DATA.get('blood_stock', {'A+': 18, 'A-': 8, 'B+': 24, 'B-': 6, 'AB+': 12, 'AB-': 4, 'O+': 32, 'O-': 5})

    # Camps organized by hospital staff & partner drives
    all_camps = list(TEMP_DATA.get('camps', {}).values())

    # Donor's verified camp registrations from staff records
    my_registrations = [
        r for r in TEMP_DATA.get('camp_registrations', {}).values()
        if (r.get('email') and r.get('email').lower() == (current_user.email or '').lower()) or
           (r.get('phone') and r.get('phone') == (current_user.phone or ''))
    ]

    # Activity/donation logs recorded by staff
    donor_logs = [
        log for log in TEMP_DATA.get('activity_logs', {}).values()
        if (current_user.name and current_user.name.lower() in (log.details or '').lower()) or
           (getattr(log, 'hospital_id', None) == getattr(current_user, 'hospital_id', None))
    ][:10]

    return render_template(
        'blood_donor_dashboard.html',
        donor=current_user,
        camps=all_camps,
        hospital=donor_hospital,
        blood_stock=blood_stock,
        my_registrations=my_registrations,
        donor_logs=donor_logs
    )




@blood_organ_bp.route('/blood-donors')
def blood_donors_list():
    city_query = request.args.get('city', '').strip().lower()
    blood_group_query = request.args.get('blood_group', '').strip()

    # Show all active non-hidden, non-blocked blood donors to the public
    all_donors = deduplicate_entities([d for d in TEMP_DATA['blood_donors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)])
    filtered_donors = []

    for donor in all_donors:
        match_city = True
        match_bg = True

        if city_query:
            if not donor.city or city_query not in donor.city.lower():
                match_city = False
        
        if blood_group_query:
            if blood_group_query != donor.blood_group:
                match_bg = False
        
        if match_city and match_bg:
            filtered_donors.append(donor)

    return render_template('blood_donors.html', donors=filtered_donors, city=city_query, blood_group=blood_group_query)



@blood_organ_bp.route('/organ-donor/dashboard', methods=['GET', 'POST'])
@login_required
def organ_donor_dashboard():
    if not isinstance(current_user, OrganDonor):
        flash("Access denied.", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        if 'update_profile' in request.form:
            current_user.name = request.form.get('name', current_user.name)
            current_user.phone = request.form.get('phone', current_user.phone)
            current_user.city = request.form.get('city', current_user.city)
            
            age = request.form.get('age')
            if age and age.isdigit():
                current_user.age = int(age)
            
            # Handle email update with uniqueness check
            new_email = request.form.get('email')
            if new_email and new_email != current_user.email:
                existing = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == new_email), None)
                if existing:
                    flash("Email already exists.", "error")
                else:
                    current_user.email = new_email

            current_user.organs = request.form.getlist('organs')

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
                    filename_prefix=f"od_profile_{current_user.id}"
                )
                if saved_filename:
                    current_user.profile_picture_url = saved_filename

            save_data()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('organ_donor_dashboard'))
        elif 'delete_picture' in request.form: # This is line 12037
            if current_user.profile_picture_url:
                # Optionally, you could also use os.remove to delete the file from the server
                current_user.profile_picture_url = None
                save_data()
                flash("Profile picture removed.", "success")
            return redirect(url_for('organ_donor_dashboard'))
        
        elif 'delete_account' in request.form:
            donor_id = current_user.id
            logout_user()
            if donor_id in TEMP_DATA['organ_donors']:
                del TEMP_DATA['organ_donors'][donor_id]
                save_data()
            flash("Your account has been deleted.", "success")
            return redirect(url_for('home'))

    return render_template('organ_donor_dashboard.html', donor=current_user, organ_requests=list(TEMP_DATA.get('organ_requests', {}).values()))



@blood_organ_bp.route('/organ-donor/certificate')
@login_required
def download_organ_donor_certificate():
    donor = None
    if isinstance(current_user, OrganDonor):
        donor = current_user
    elif current_user.is_authenticated:
        donor_id = request.args.get('donor_id')
        if donor_id and donor_id in TEMP_DATA.get('organ_donors', {}):
            donor = TEMP_DATA['organ_donors'][donor_id]
            
    if not donor:
        flash("Access denied or organ donor record not found.", "error")
        return redirect(url_for('home'))

    try:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=False)
        
        # Load Luxury Gold & Black Certificate Template Background
        bg_img_path = os.path.join(current_app.root_path, 'static', 'images', 'certificate_template.png')
        if os.path.exists(bg_img_path):
            pdf.image(bg_img_path, x=0, y=0, w=297, h=210)
        else:
            pdf.set_fill_color(253, 252, 248)
            pdf.rect(0, 0, 297, 210, 'F')
            pdf.set_draw_color(202, 156, 56)
            pdf.set_line_width(2.0)
            pdf.rect(8, 8, 281, 194)
        hosp = None
        if hasattr(donor, 'hospital_id') and donor.hospital_id and donor.hospital_id in TEMP_DATA.get('hospitals', {}):
            hosp = TEMP_DATA['hospitals'][donor.hospital_id]
        elif hasattr(donor, 'hospital_name') and donor.hospital_name:
            hosp = next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(h.name).strip().lower() == str(donor.hospital_name).strip().lower()), None)
        
        if not hosp:
            if getattr(current_user, 'is_hospital', False):
                hosp = current_user
            elif getattr(current_user, 'is_staff', False) and hasattr(current_user, 'hospital_name'):
                hosp = next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(h.name).strip().lower() == str(current_user.hospital_name).strip().lower()), None)
            elif TEMP_DATA.get('hospitals'):
                hosp = list(TEMP_DATA['hospitals'].values())[0]

        # Extract EXACT hospital details
        hospital_name = getattr(hosp, 'name', 'Registered Healthcare Facility')
        hospital_city = getattr(hosp, 'city', '')
        hospital_state = getattr(hosp, 'state', '')
        hospital_id_code = str(getattr(hosp, 'id', 'HOSP'))
        
        president_name = getattr(donor, 'president_ceo', None) or getattr(hosp, 'president_ceo', None) or getattr(hosp, 'director_name', None) or f"Managing Director ({hospital_name})"
        superintendent_name = getattr(donor, 'assigned_staff_name', None) or getattr(donor, 'superintendent_name', None) or getattr(donor, 'verified_by', None) or getattr(hosp, 'superintendent_name', None) or getattr(hosp, 'blood_bank_staff', None) or f"Medical Superintendent ({hospital_name})"

        hospital_name_clean = to_latin1_str(hospital_name)
        hospital_city_clean = to_latin1_str(hospital_city)
        hospital_state_clean = to_latin1_str(hospital_state)
        superintendent_name_clean = to_latin1_str(superintendent_name)
        president_name_clean = to_latin1_str(president_name)

        # Usable content area (Centered on A4 297mm x 210mm)
        content_left = 30
        content_w = 237
        
        # 1. Authority Header
        pdf.set_xy(content_left, 36)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(185, 135, 35)
        pdf.cell(content_w, 5, f"{hospital_name_clean.upper()}  |  NATIONAL ORGAN TRANSPLANT REGISTRY", 0, 1, 'C')

        # 2. Main Title
        pdf.set_xy(content_left, 43)
        pdf.set_font('Times', 'B', 25)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(content_w, 9, "CERTIFICATE OF HONOR", 0, 1, 'C')

        pdf.set_xy(content_left, 53)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(185, 135, 35)
        pdf.cell(content_w, 5, "NATIONAL HUMANITARIAN LIFE PLEDGE COMMENDATION", 0, 1, 'C')

        # Gold Divider Line
        pdf.set_draw_color(202, 156, 56)
        pdf.set_line_width(0.5)
        pdf.line(90, 60, 138, 60)
        pdf.line(159, 60, 207, 60)
        pdf.set_fill_color(185, 135, 35)
        pdf.rect(146.5, 58.5, 4, 3, 'DF')

        # 3. Conferral Preamble
        pdf.set_xy(content_left, 65)
        pdf.set_font('Times', 'I', 12)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(content_w, 6, "This Official Commendation is Proudly Conferred Upon", 0, 1, 'C')

        # 4. Benefactor Donor Name
        pdf.set_xy(content_left, 73)
        donor_name_clean = to_latin1_str(donor.name).upper()
        pdf.set_font('Times', 'B', 24)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(content_w, 9, donor_name_clean, 0, 1, 'C')

        # 5. Preamble statement
        pdf.set_xy(content_left, 84)
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(content_w, 5, "in highest recognition of the noble voluntary commitment to save and transform human lives.", 0, 1, 'C')

        # 6. Details Box
        organs_list = donor.organs if isinstance(donor.organs, list) else [str(donor.organs)]
        organs_str = ", ".join(organs_list) if organs_list else "All Vital Organs & Tissues"
        organs_clean = to_latin1_str(organs_str)
        
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        pdf.rect(38, 93, 221, 23, 'FD')

        pdf.set_xy(43, 96)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(100, 4.5, f"REGISTRY ID: #{to_latin1_str(donor.id)}", 0, 0, 'L')
        pdf.cell(111, 4.5, f"BLOOD GROUP: {to_latin1_str(donor.blood_group)}", 0, 1, 'R')

        pdf.set_xy(43, 102)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(185, 135, 35)
        pdf.cell(211, 4.5, f"PLEDGED GIFTS OF LIFE: {organs_clean}", 0, 1, 'L')

        pdf.set_xy(43, 108)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(100, 4, f"REGISTERED FACILITY: {hospital_name_clean}", 0, 0, 'L')
        pdf.cell(111, 4, "STATUS: VERIFIED VOLUNTARY BENEFACTOR", 0, 1, 'R')

        # 7. Commendation Narrative
        pdf.set_xy(content_left + 8, 121)
        pdf.set_font('Times', 'I', 9.5)
        pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(content_w - 16, 4.5, 
            f"By pledging the gift of life at {hospital_name_clean}, the donor has demonstrated the highest ideals of compassion, altruism, and clinical solidarity. This document officially certifies registration within the official National Organ & Tissue Registry under validated medical consent protocols.", 
            0, 'C')

        # 8. Signatures & Verification Area (Y = 142)
        y_sig = 142
        
        pdf.set_draw_color(15, 23, 42)
        pdf.set_line_width(0.3)
        pdf.line(40, y_sig + 11, 105, y_sig + 11)
        pdf.set_xy(38, y_sig + 12.5)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.cell(69, 3.5, superintendent_name_clean.upper(), 0, 1, 'C')
        pdf.set_xy(38, y_sig + 16)
        pdf.set_font('Helvetica', '', 6.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(69, 3, "Medical Superintendent / Transplant Coordinator", 0, 1, 'C')
        pdf.set_xy(38, y_sig + 19)
        pdf.cell(69, 3, f"{hospital_name_clean} Clinical Staff", 0, 1, 'C')

        pdf.line(120, y_sig + 11, 185, y_sig + 11)
        pdf.set_xy(118, y_sig + 12.5)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(69, 3.5, president_name_clean.upper(), 0, 1, 'C')
        pdf.set_xy(118, y_sig + 16)
        pdf.set_font('Helvetica', '', 6.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(69, 3, "President & Chief Executive / MD", 0, 1, 'C')
        pdf.set_xy(118, y_sig + 19)
        pdf.cell(69, 3, hospital_name_clean, 0, 1, 'C')

        # Far Right: QR Code
        qr = qrcode.QRCode(box_size=6, border=1)
        qr_url = url_for('organ_donor_dashboard', _external=True)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_qr:
            qr_img.save(tmp_qr)
            pdf.image(tmp_qr.name, x=212, y=y_sig - 1, w=22, h=22)
            try: os.unlink(tmp_qr.name)
            except OSError: pass
        pdf.set_draw_color(202, 156, 56)
        pdf.set_line_width(0.3)
        pdf.rect(211, y_sig - 2, 24, 24)
        pdf.set_xy(201, y_sig + 23)
        pdf.set_font('Helvetica', 'B', 5.5)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(44, 3, "SCAN TO VERIFY PLEDGE", 0, 1, 'C')

        # 9. Bottom Micro-Print Security Footer
        pdf.set_xy(content_left, 178)
        pdf.set_font('Helvetica', '', 6)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(content_w, 3, f"{hospital_name_clean.upper()}  |  REGISTRY ID: #{to_latin1_str(donor.id)}  |  LEGAL NATIONAL ORGAN PLEDGE", 0, 1, 'C')

        buffer = BytesIO()
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            pdf_output = pdf_output.encode('latin1')
        buffer.write(pdf_output)
        buffer.seek(0)
        
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', donor.name.strip())
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Organ_Donor_Pledge_Certificate_{safe_name}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"❌ Error generating organ donor certificate: {e}")
        flash("Could not generate certificate at this time.", "error")
        return redirect(url_for('organ_donor_dashboard'))
        return redirect(url_for('organ_donor_dashboard'))



@blood_organ_bp.route('/organ-donors')
def organ_donors_list():
    city_query = request.args.get('city', '').strip().lower()
    organ_query = request.args.get('organ', '').strip().lower()

    # Show all active non-hidden, non-blocked organ donors to the public
    all_donors = deduplicate_entities([d for d in TEMP_DATA['organ_donors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)])
    filtered_donors = []

    for donor in all_donors:
        match_city = True
        match_organ = True

        if city_query:
            if not donor.city or city_query not in donor.city.lower():
                match_city = False
        
        if organ_query:
            if not donor.organs or not any(organ_query in o.lower() for o in donor.organs):
                match_organ = False
        
        if match_city and match_organ:
            filtered_donors.append(donor)

    return render_template('organ_donors.html', donors=filtered_donors, city=city_query, organ=organ_query)



@blood_organ_bp.route('/organ-donor/certificate/<path:donor_id>')
def download_organ_certificate(donor_id):
    donor_id = parse_route_id(donor_id)
    donor = TEMP_DATA['organ_donors'].get(donor_id)
    if not donor:
        flash("Donor not found.", "error")
        return redirect(url_for('organ_donors_list'))

    try:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=False)
        
        # --- 1. Background & Border (Premium Style) ---
        pdf.set_fill_color(253, 252, 247) # Premium ivory/cream background
        pdf.rect(0, 0, 297, 210, 'F')

        # Outer thick border (Crimson Blood Red)
        pdf.set_draw_color(153, 27, 27) 
        pdf.set_line_width(4)
        pdf.rect(10, 10, 277, 190)

        # Inner elegant border (Premium Gold)
        pdf.set_draw_color(192, 156, 66)
        pdf.set_line_width(0.8)
        pdf.rect(16, 16, 265, 178)
        pdf.rect(18, 18, 261, 174) # Double inner line

        # Gold Corner Ornaments
        pdf.line(16, 26, 26, 16)
        pdf.line(16, 32, 32, 16)
        pdf.line(281, 26, 271, 16)
        pdf.line(281, 32, 265, 16)
        pdf.line(16, 184, 26, 194)
        pdf.line(16, 178, 32, 194)
        pdf.line(281, 184, 271, 194)
        pdf.line(281, 178, 265, 194)

        # Concentric security lines
        pdf.set_draw_color(245, 241, 230)
        pdf.set_line_width(0.2)
        center_x, center_y = 148.5, 105
        for i in range(10, 70, 10):
            pdf.rect(center_x - i, center_y - i, i * 2, i * 2)

        # --- 2. Header ---
        try:
            id_val = int(donor.id)
            cert_number = f"OD/{donor.created_at.year}/{id_val:05d}"
        except (ValueError, TypeError):
            cert_number = str(donor.id)
        pdf.set_xy(25, 25)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 6, f"Certificate No: {cert_number}", 0, 1, 'L')

        # Top Center: Spherix Clinic
        pdf.set_y(26)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(15, 23, 42) # Navy
        pdf.cell(0, 6, 'SPHERIX CLINIC HEALTH INTELLIGENCE', 0, 1, 'C')
        
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(192, 156, 66) # Gold
        pdf.cell(0, 5, 'RECOGNIZING EXCELLENCE IN HUMANITY', 0, 1, 'C')

        # Center Title
        pdf.set_y(44)
        pdf.set_font('Times', 'B', 32)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 12, 'ORGAN DONATION PLEDGE', 0, 1, 'C')

        # Gold Elegant Divider Line with Center Diamond/Square
        pdf.set_draw_color(192, 156, 66)
        pdf.set_line_width(0.6)
        pdf.line(110, 58, 145, 58)
        pdf.line(152, 58, 187, 58)
        pdf.set_fill_color(192, 156, 66)
        pdf.rect(147, 56.5, 3, 3, 'DF')

        # --- 3. Body Content ---
        pdf.set_y(62)
        pdf.set_font('Times', 'I', 15)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 8, 'This honorable pledge is proudly made by', 0, 1, 'C')
        
        pdf.ln(2)
        name = to_latin1_str(donor.name).upper()
        pdf.set_font('Times', 'B', 32)
        pdf.set_text_color(192, 156, 66) # Gold Name
        pdf.cell(0, 14, name, 0, 1, 'C')
        
        pdf.ln(4)
        organs_str = ", ".join(donor.organs) if donor.organs else "All Viable Organs"
        
        # Rounded Metadata Box (Sleek gold-bordered rectangle)
        pdf.set_fill_color(248, 245, 235)
        pdf.set_draw_color(192, 156, 66)
        pdf.set_line_width(0.4)
        # We can draw it as a normal rectangle since it's cleaner and safer than custom rounded rects
        pdf.rect(48, 90, 201, 12, 'DF')
        
        pdf.set_xy(48, 92)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(201, 8, f"BLOOD GROUP: {donor.blood_group}   |   ORGANS PLEDGED: {to_latin1_str(organs_str).upper()}", 0, 1, 'C')
        
        pdf.set_y(108)
        pdf.set_font('Times', 'I', 14)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 6.5, 'For your selfless and voluntary decision to pledge your organs.\nYour noble commitment will serve as a beacon of hope and a second chance at life for those in need.', 0, 'C')
        
        # --- 4. Footer & Custom Signature Font ---
        y_footer = 160
        
        # Bottom Left: Details
        pdf.set_xy(35, y_footer)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(120, 120, 120)
        
        pdf.cell(25, 5, "DATE:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 5, str(donor.created_at.strftime('%Y-%m-%d')), 0, 1, 'L')
        
        pdf.set_x(35)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(25, 5, "ISSUER:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 5, "Spherix Clinic Organ Registry", 0, 1, 'L')

        # Official Stamp
        try:
            stamp_path = os.path.join(current_app.root_path, 'static', 'images', 'stamp.png')
            if os.path.exists(stamp_path):
                from PIL import Image
                import tempfile
                with Image.open(stamp_path) as img:
                    rgb_img = img.convert('RGB')
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                        rgb_img.save(tmp.name, 'JPEG')
                        pdf.image(tmp.name, x=136.5, y=y_footer - 8, w=24)
                    os.unlink(tmp.name)
            else:
                raise FileNotFoundError("Stamp file not found")
        except Exception as e:
            print(f"⚠️ Stamp image error on organ cert: {e}")
            pass # Fallback to no stamp

        # Bottom Right: Signature & Organization
        pdf.set_xy(190, y_footer - 15)
        
        # CUSTOM SIGNATURE FONT LOGIC
        signature_drawn = False
        try:
            signature_img_path = os.path.join(current_app.root_path, 'static', 'images', 'signature.png')
            if os.path.exists(signature_img_path):
                try:
                    from PIL import Image
                    import tempfile
                    with Image.open(signature_img_path) as img:
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode in ('RGBA', 'LA'):
                            bg.paste(img, mask=img.split()[3])
                        else:
                            bg.paste(img)
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            bg.save(tmp.name, 'JPEG')
                            pdf.image(tmp.name, x=205, y=y_footer - 13, w=30)
                        os.unlink(tmp.name)
                    signature_drawn = True
                except Exception as img_err:
                    print(f"PIL process signature error: {img_err}")
                pdf.set_y(y_footer + 5) # Move cursor down to match text spacing
        except Exception as e:
            print(f"Signature error: {e}")
            pass
            
        if not signature_drawn:
            custom_font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'signature.ttf')
            try:
                if os.path.exists(custom_font_path):
                    pdf.add_font('RealSignature', '', custom_font_path, uni=True)
                    pdf.set_font('RealSignature', '', 36)
                else:
                    pdf.set_font('Times', 'I', 28)
            except:
                pdf.set_font('Times', 'I', 28)
                
            pdf.set_text_color(15, 23, 42)
            pdf.set_xy(190, y_footer - 10)
            pdf.cell(60, 16, 'Sunny', 0, 1, 'C')
        
        # Line under signature
        pdf.set_draw_color(15, 23, 42)
        pdf.set_line_width(0.5)
        pdf.line(195, y_footer + 8, 245, y_footer + 8)
        
        pdf.set_xy(190, y_footer + 10)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(60, 4, 'PRESIDENT, Spherix Clinic', 0, 1, 'C')
        
        pdf.set_xy(190, y_footer + 14)
        pdf.set_font('Times', 'B', 11)
        pdf.set_text_color(192, 156, 66)
        pdf.cell(60, 5, 'Medical Board Approved', 0, 0, 'C')
        
        # QR Code with Gold Border
        pdf.set_draw_color(192, 156, 66)
        pdf.set_line_width(0.4)
        pdf.rect(254, 149, 24, 24)
        
        qr_url = url_for('organ_donors_list', _external=True)
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_qr:
            qr_img.save(tmp_qr)
            tmp_qr_path = tmp_qr.name
            
        pdf.image(tmp_qr_path, x=255, y=150, w=22, h=22)
        try: os.unlink(tmp_qr_path)
        except OSError: pass

        try:
            pdf_output = pdf.output(dest='S')
            pdf_bytes = pdf_output.encode('latin-1') if isinstance(pdf_output, str) else pdf_output
        except TypeError:
            pdf_bytes = pdf.output()
             
        if request.args.get('action') == 'email':
            subject = "Your Organ Donation Pledge Certificate - Spherix Clinic"
            body = f"Dear {donor.name},\n\nThank you for your noble decision to pledge your organs. Please find your official organ donor certificate attached to this email.\n\nBest regards,\nSpherix Clinic Organ Registry"
            send_notification_email(donor.email, subject, body, is_html=False, attachment_name=f"organ_pledge_{donor.id}.pdf", attachment_data=pdf_bytes)
            flash("Certificate sent to your email successfully!", "success")
            return redirect(url_for('organ_donor_dashboard'))
        else:
            return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'organ_pledge_{donor.id}.pdf', mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating organ certificate: {e}")
        flash("An error occurred while generating the certificate.", "error")
        return redirect(url_for('organ_donors_list'))



@blood_organ_bp.route('/blood-bank')
def blood_bank():
    """Displays the blood bank inventory."""
    hospitals_with_stock = [h for h in TEMP_DATA['hospitals'].values() if getattr(h, 'is_verified', True) and not getattr(h, 'is_hidden', False)]
    return render_template('blood_bank.html', stock=TEMP_DATA['blood_stock'], hospitals=hospitals_with_stock)



@blood_organ_bp.route('/blood-bank/update', methods=['POST'])
@login_required
def update_blood_stock():
    """Allows hospitals and admins to update blood stock levels."""
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@spherixclinic.com'
    is_hospital = getattr(current_user, 'is_hospital', False)
    is_blood_staff = getattr(current_user, 'is_staff', False) and current_user.role == 'Blood Donor Management'
    
    if not (is_admin or is_hospital or is_blood_staff):
        flash("Access denied. Only authorized personnel can manage inventory.", "error")
        return redirect(url_for('blood_bank'))

    group = request.form.get('group')
    operation = request.form.get('operation') # 'add' or 'sub'
    hospital_id = request.form.get('hospital_id')
    
    hosp = None
    if is_admin and hospital_id:
        hosp = TEMP_DATA['hospitals'].get(hospital_id)
    elif is_hospital:
        hosp = current_user
    elif is_blood_staff:
        hosp = next((h for h in TEMP_DATA['hospitals'].values() if h.name == current_user.hospital_name), None)

    if hosp:
        if not hasattr(hosp, 'blood_stock') or not isinstance(hosp.blood_stock, dict):
            hosp.blood_stock = { "A+": 0, "A-": 0, "B+": 0, "B-": 0, "AB+": 0, "AB-": 0, "O+": 0, "O-": 0 }
        if group in hosp.blood_stock:
            if operation == 'add':
                hosp.blood_stock[group] += 1
            elif operation == 'sub' and hosp.blood_stock[group] > 0:
                hosp.blood_stock[group] -= 1
            save_data()
    else:
        if group in TEMP_DATA['blood_stock']:
            if operation == 'add':
                TEMP_DATA['blood_stock'][group] += 1
            elif operation == 'sub' and TEMP_DATA['blood_stock'][group] > 0:
                TEMP_DATA['blood_stock'][group] -= 1
            save_data()
            
    # Stay on the current dashboard view after modifying inventory
    return redirect(request.referrer or url_for('blood_bank'))



@blood_organ_bp.route('/blood-donation-camps')
def blood_donation_camps():
    """Displays a list of upcoming blood donation camps."""

    camps = list(TEMP_DATA['camps'].values())
    return render_template('blood_donation_camps.html', camps=camps)



@blood_organ_bp.route('/blood-donor/id-card')
@login_required
def download_blood_donor_id_card():
    donor = None
    if isinstance(current_user, BloodDonor):
        donor = current_user
    elif current_user.is_authenticated:
        d_id = request.args.get('donor_id') or request.args.get('id')
        if d_id and d_id in TEMP_DATA.get('blood_donors', {}):
            donor = TEMP_DATA['blood_donors'][d_id]

    if not donor:
        flash("Blood donor record not found.", "error")
        return redirect(url_for('home'))

    try:
        buffer = generate_user_id_card_pdf(
            user_type='Blood donor',
            name=donor.name,
            user_id=str(donor.id),
            phone=getattr(donor, 'phone', 'N/A'),
            address=getattr(donor, 'city', None) or 'Registered Donor',
            blood_group=getattr(donor, 'blood_group', None),
            extra_info='Voluntary Donor',
            photo_filename=getattr(donor, 'profile_picture_url', None),
            hospital_name=getattr(donor, 'hospital_name', None)
        )
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', donor.name.strip())
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Blood_Donor_ID_Card_{safe_name}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error generating blood donor ID card: {e}")
        flash("Could not generate ID card at this time.", "error")
        return redirect(url_for('blood_donor_dashboard'))



@blood_organ_bp.route('/organ-donor/id-card')
@login_required
def download_organ_donor_id_card():
    donor = None
    if isinstance(current_user, OrganDonor):
        donor = current_user
    elif current_user.is_authenticated:
        d_id = request.args.get('donor_id') or request.args.get('id')
        if d_id and d_id in TEMP_DATA.get('organ_donors', {}):
            donor = TEMP_DATA['organ_donors'][d_id]

    if not donor:
        flash("Organ donor record not found.", "error")
        return redirect(url_for('home'))

    try:
        organs_str = ", ".join(donor.organs) if isinstance(donor.organs, list) and donor.organs else "8 Vital Organs"
        buffer = generate_user_id_card_pdf(
            user_type='Organ donor',
            name=donor.name,
            user_id=str(donor.id),
            phone=getattr(donor, 'phone', 'N/A'),
            address=getattr(donor, 'city', None) or 'Registry Benefactor',
            blood_group=getattr(donor, 'blood_group', None),
            extra_info=f"Pledge: {organs_str[:12]}",
            photo_filename=getattr(donor, 'profile_picture_url', None),
            hospital_name=getattr(donor, 'hospital_name', None)
        )
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', donor.name.strip())
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Organ_Donor_ID_Card_{safe_name}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error generating organ donor ID card: {e}")
        flash("Could not generate ID card at this time.", "error")
        return redirect(url_for('organ_donor_dashboard'))



@blood_organ_bp.route('/blood-bank/dashboard', methods=['GET', 'POST'])
@login_required
def blood_bank_dashboard():
    """Dedicated dashboard for Blood Bank Managers."""
    # Allow Admins and Hospitals to access this dashboard
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@spherixclinic.com'
    is_hospital = getattr(current_user, 'is_hospital', False)
    is_blood_staff = getattr(current_user, 'is_staff', False) and current_user.role == 'Blood Donor Management'
    
    if not (is_admin or is_hospital or is_blood_staff):
        flash("Access denied. Authorized personnel only.", "error")
        return redirect(url_for('home'))
        
    hosp_id = None
    if is_hospital:
        hosp_id = current_user.id
    elif is_blood_staff:
        hosp = next((h for h in TEMP_DATA['hospitals'].values() if h.name == current_user.hospital_name), None)
        if hosp:
            hosp_id = hosp.id

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'edit_donor':
            donor_id = request.form.get('donor_id')
            if donor_id:
                donor_id = parse_route_id(donor_id)
                if donor_id in TEMP_DATA.get('blood_donors', {}):
                    donor = TEMP_DATA['blood_donors'][donor_id]
                    donor.name = request.form.get('name', donor.name)
                    donor.email = request.form.get('email', donor.email)
                    donor.phone = request.form.get('phone', donor.phone)
                    donor.blood_group = request.form.get('blood_group', donor.blood_group)
                    donor.city = request.form.get('city', donor.city)
                    save_data()
                    flash('Donor account updated successfully.', 'success')
                    
        elif action == 'delete_donor':
            donor_id = request.form.get('donor_id')
            if donor_id:
                donor_id = parse_route_id(donor_id)
                if donor_id in TEMP_DATA.get('blood_donors', {}):
                    del TEMP_DATA['blood_donors'][donor_id]
                    save_data()
                    flash('Donor account deleted successfully.', 'success')
                    
        elif action == 'add_camp':
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

                organizer = current_user.name if hasattr(current_user, 'name') else 'Blood Bank Admin'
                if getattr(current_user, 'is_staff', False):
                    organizer = current_user.hospital_name

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
                flash("Blood donation camp added successfully.", "success")
                
        elif action == 'delete_camp':
            camp_id = request.form.get('camp_id')
            if camp_id and camp_id.isdigit():
                camp_id = int(camp_id)
                if camp_id in TEMP_DATA.get('camps', {}):
                    del TEMP_DATA['camps'][camp_id]
                    save_data()
                    flash("Camp deleted successfully.", "success")
                    
        elif action == 'delete_registration':
            reg_id = request.form.get('reg_id')
            if reg_id and reg_id.isdigit():
                reg_id = int(reg_id)
                if reg_id in TEMP_DATA.get('camp_registrations', {}):
                    del TEMP_DATA['camp_registrations'][reg_id]
                    save_data()
                    flash("Camp registration deleted successfully.", "success")

        return redirect(url_for('blood_bank_dashboard'))

    camps = list(TEMP_DATA.get('camps', {}).values())
    if is_hospital:
        camps = [c for c in camps if c.get('organizer') == current_user.name]
    elif is_blood_staff:
        camps = [c for c in camps if c.get('organizer') == current_user.hospital_name]

    camp_registrations = list(TEMP_DATA.get('camp_registrations', {}).values())
    if is_hospital or is_blood_staff:
        camp_names = [c['name'] for c in camps]
        camp_registrations = [r for r in camp_registrations if r.get('camp_name') in camp_names]

    if hosp_id:
        donors = [d for d in TEMP_DATA.get('blood_donors', {}).values() if getattr(d, 'hospital_id', None) == hosp_id or not getattr(d, 'hospital_id', None)]
        stock = TEMP_DATA['hospitals'][hosp_id].blood_stock if hasattr(TEMP_DATA['hospitals'][hosp_id], 'blood_stock') else TEMP_DATA['blood_stock']
    else:
        donors = list(TEMP_DATA.get('blood_donors', {}).values())
        stock = TEMP_DATA.get('blood_stock', {})

    return render_template('blood_bank_dashboard.html', 
                           stock=stock, 
                           donors=donors,
                           camps=camps,
                           camp_registrations=camp_registrations,
                           hosp_id=hosp_id)



@blood_organ_bp.route('/patient/organ-request/create', methods=['POST'])
@patient_required
def create_organ_request():
    """Allows a patient to broadcast an organ transplant request."""
    organ_needed = request.form.get('organ_needed')
    blood_group = request.form.get('blood_group')
    urgency = request.form.get('urgency')
    hospital_id = request.form.get('hospital_id')
    
    if not all([organ_needed, blood_group, urgency]):
        flash("Please fill out all required fields.", "error")
        return redirect(url_for('patient_dashboard'))
        
    if 'organ_requests' not in TEMP_DATA:
        TEMP_DATA['organ_requests'] = {}
        
    req_id = TEMP_DATA['next_ids']['organ_request']
    new_req = OrganRequest(
        id=req_id,
        patient_id=current_user.id,
        patient_name=current_user.name,
        organ_needed=organ_needed,
        blood_group=blood_group,
        urgency=urgency,
        status='active',
        hospital_id=hospital_id
    )
    TEMP_DATA['organ_requests'][req_id] = new_req
    TEMP_DATA['next_ids']['organ_request'] += 1
    save_data()
    flash("Organ transplant request broadcasted successfully.", "success")
    return redirect(url_for('patient_dashboard'))





def generate_user_id_card_pdf(user_type, name, user_id, phone, address, blood_group=None, extra_info=None, photo_filename=None, hospital_name=None):
    """
    Generates a CR80 vertical Digital ID card (54mm x 91.8mm) for Patients, Blood Donors, and Organ Donors.
    Includes:
    - Background template (static/images/id_card_template.png)
    - Photo on top (clipped circular/rounded avatar or actual profile photo)
    - User's Name below photo
    - Role Identity badge (PATIENT, BLOOD DONOR, ORGAN DONOR)
    - Contact Number, Address, and clinical vitals (Blood group, pledge, facility)
    - Scannable Code128 Barcode with user card ID at the bottom
    """
    from PIL import Image, ImageDraw
    card_w = 54.0
    card_h = 91.8

    pdf = FPDF(orientation='P', unit='mm', format=(card_w, card_h))
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # 1. Background Template
    bg_path = os.path.join(current_app.root_path, 'static', 'images', 'id_card_template.png')
    if os.path.exists(bg_path):
        pdf.image(bg_path, x=0, y=0, w=card_w, h=card_h)
    else:
        pdf.set_fill_color(24, 24, 27)
        pdf.rect(0, 0, card_w, card_h, 'F')

    # Role Colors & Badges
    user_type_lower = str(user_type).lower()
    if 'blood' in user_type_lower:
        badge_bg = (185, 28, 28) # Crimson
        badge_text = 'BLOOD DONOR'
        avatar_bg = (185, 28, 28)
    elif 'organ' in user_type_lower:
        badge_bg = (67, 56, 202) # Indigo
        badge_text = 'ORGAN DONOR'
        avatar_bg = (67, 56, 202)
    else:
        badge_bg = (13, 148, 136) # Teal
        badge_text = 'PATIENT'
        avatar_bg = (13, 148, 136)

    # 2. Profile Picture on Top (Circular / Rounded with white border)
    avatar_size = 240
    avatar_img = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(avatar_img)

    photo_loaded = False
    if photo_filename:
        photo_path = os.path.join(current_app.root_path, 'static', 'uploads', photo_filename)
        if not os.path.exists(photo_path):
            photo_path = os.path.join(current_app.root_path, 'static', photo_filename)
        if os.path.exists(photo_path):
            try:
                user_photo = Image.open(photo_path).convert('RGBA')
                min_dim = min(user_photo.size)
                left = (user_photo.width - min_dim) / 2
                top = (user_photo.height - min_dim) / 2
                user_photo = user_photo.crop((left, top, left + min_dim, top + min_dim))
                user_photo = user_photo.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((4, 4, avatar_size - 4, avatar_size - 4), fill=255)
                
                avatar_img.paste(user_photo, (0, 0), mask)
                draw.ellipse((4, 4, avatar_size - 4, avatar_size - 4), outline=(245, 245, 245), width=6)
                photo_loaded = True
            except Exception as e:
                print(f"Error loading profile picture for ID card: {e}")

    if not photo_loaded:
        draw.ellipse((4, 4, avatar_size - 4, avatar_size - 4), fill=avatar_bg, outline=(245, 245, 245), width=6)
        draw.ellipse((avatar_size * 0.35, avatar_size * 0.22, avatar_size * 0.65, avatar_size * 0.52), fill=(255, 255, 255))
        draw.pieslice((avatar_size * 0.2, avatar_size * 0.55, avatar_size * 0.8, avatar_size * 1.15), 180, 360, fill=(255, 255, 255))

    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_av:
        avatar_img.save(tmp_av.name)
        pdf.image(tmp_av.name, x=(card_w - 20) / 2, y=7, w=20, h=20)
        try: os.unlink(tmp_av.name)
        except OSError: pass

    # 3. Name Below Photo
    pdf.set_xy(3, 29)
    pdf.set_font('Helvetica', 'B', 8.5)
    pdf.set_text_color(255, 255, 255)
    clean_name = to_latin1_str(str(name).upper())[:22]
    pdf.cell(card_w - 6, 4, clean_name, 0, 1, 'C')

    # 4. User Identity Badge Below Name
    pdf.set_xy((card_w - 28) / 2, 34)
    pdf.set_fill_color(badge_bg[0], badge_bg[1], badge_bg[2])
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 5.5)
    pdf.cell(28, 3.5, badge_text, 0, 1, 'C', fill=True)

    # 5. Details Section (ID, Contact Number, Address, Vitals)
    pdf.set_fill_color(30, 30, 38)
    pdf.set_draw_color(60, 60, 75)
    pdf.set_line_width(0.2)
    pdf.rect(4, 39.5, card_w - 8, 28, 'FD')

    y_pos = 41
    pdf.set_text_color(160, 160, 175)
    pdf.set_font('Helvetica', 'B', 5)
    pdf.set_xy(6, y_pos)
    pdf.cell(18, 3.2, 'CARD ID:', 0, 0, 'L')
    pdf.set_text_color(255, 255, 255)
    pdf.cell(24, 3.2, to_latin1_str(str(user_id))[:18], 0, 1, 'L')

    y_pos += 3.5
    pdf.set_text_color(160, 160, 175)
    pdf.set_xy(6, y_pos)
    pdf.cell(18, 3.2, 'PHONE:', 0, 0, 'L')
    pdf.set_text_color(255, 255, 255)
    pdf.cell(24, 3.2, to_latin1_str(str(phone or 'N/A'))[:16], 0, 1, 'L')

    y_pos += 3.5
    pdf.set_text_color(160, 160, 175)
    pdf.set_xy(6, y_pos)
    pdf.cell(18, 3.2, 'ADDRESS:', 0, 0, 'L')
    pdf.set_text_color(255, 255, 255)
    pdf.cell(24, 3.2, to_latin1_str(str(address or 'N/A'))[:18], 0, 1, 'L')

    if blood_group:
        y_pos += 3.5
        pdf.set_text_color(160, 160, 175)
        pdf.set_xy(6, y_pos)
        pdf.cell(18, 3.2, 'BLOOD GRP:', 0, 0, 'L')
        pdf.set_text_color(244, 63, 94) # Coral / Red
        pdf.set_font('Helvetica', 'B', 5.5)
        pdf.cell(24, 3.2, to_latin1_str(str(blood_group)), 0, 1, 'L')

    if extra_info or hospital_name:
        y_pos += 3.5
        pdf.set_text_color(160, 160, 175)
        pdf.set_font('Helvetica', 'B', 5)
        pdf.set_xy(6, y_pos)
        info_label = 'FACILITY:' if hospital_name else 'DETAILS:'
        info_val = hospital_name or extra_info
        pdf.cell(18, 3.2, info_label, 0, 0, 'L')
        pdf.set_text_color(217, 119, 6) # Amber
        pdf.cell(24, 3.2, to_latin1_str(str(info_val))[:18], 0, 1, 'L')

    # 6. Scannable Code128 Barcode at Bottom
    try:
        import barcode  # type: ignore
        from barcode.writer import ImageWriter  # type: ignore
        Code128 = barcode.get_barcode_class('code128')
        raw_code = re.sub(r'[^a-zA-Z0-9_-]', '', str(user_id)) or 'ID12345'
        bc = Code128(raw_code, writer=ImageWriter())
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_bc:
            bc_img = bc.render(writer_options={'write_text': False, 'module_width': 0.25, 'module_height': 8.0, 'quiet_zone': 1.0})
            bc_img.save(tmp_bc.name)
            pdf.image(tmp_bc.name, x=6, y=69.5, w=card_w - 12, h=11)
            try: os.unlink(tmp_bc.name)
            except OSError: pass
    except Exception as e:
        print(f"Error generating barcode: {e}")

    pdf.set_xy(3, 81.5)
    pdf.set_font('Helvetica', 'B', 4.5)
    pdf.set_text_color(160, 160, 175)
    barcode_label = to_latin1_str(str(user_id))
    pdf.cell(card_w - 6, 2.5, f"*{barcode_label}*", 0, 1, 'C')

    pdf.set_xy(3, 85)
    pdf.set_font('Helvetica', '', 3.8)
    pdf.set_text_color(120, 120, 135)
    pdf.cell(card_w - 6, 2.5, 'OFFICIAL SPHERIX DIGITAL IDENTITY CARD', 0, 1, 'C')

    buffer = BytesIO()
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode('latin1')
    buffer.write(pdf_output)
    buffer.seek(0)
    return buffer

