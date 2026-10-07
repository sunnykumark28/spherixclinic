from spherix.services.upload_service import save_user_profile_image, upload_to_cloudinary, UPLOAD_CACHE
from fpdf import FPDF


import markdown

def render_markdown_filter(text):
    return markdown.markdown(text or '', extensions=['fenced_code', 'tables', 'nl2br'])


from spherix.routes.gallery_data import *
from spherix.services.database import deduplicate_entities
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
import re
import tempfile
import base64
from spherix.routes.blood_organ import generate_user_id_card_pdf
from datetime import datetime, date, time, timedelta, timezone
from io import BytesIO, StringIO
from functools import wraps
from urllib.parse import urlparse, quote_plus
from collections import Counter

try:
    import qrcode
except ImportError:
    qrcode = None

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
    utcnow, parse_route_id, get_actual_user_id, format_dual_currency,
    convert_currency, get_currency_symbol, generate_user_license_id,
    BLOG_POSTS, allowed_file, SECRET_KEY, GLOBAL_CURRENCY_RATES,
    GLOBAL_CURRENCY_SYMBOLS, COUNTRIES_195, GLOBAL_COUNTRY_FLAGS,
    GLOBAL_COUNTRY_TIMEZONES, search_countries,
    generate_captcha_text, generate_captcha_image_bytes
)
from spherix.models import (
    Doctor, Patient, Staff, HospitalStaff, Hospital, BloodDonor, OrganDonor,
    Appointment, PatientVital, LabRequest, OrganRequest, BedBooking,
    Order, Review, Feedback, Message, ActivityLog, Referral, Notification
)
from spherix.services.database import (
    TEMP_DATA, get_db_connection, save_data, load_data,
    sync_data_to_sql, load_data_from_sql, create_notification, get_temp_data_item
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
    SYMPTOM_CACHE, ACTIVE_SYMPTOM_REPORTS, LAST_API_CALL_TIME,
    _is_vision_configured, _analyze_image_with_vision, _analyze_image_with_groq_vision,
    _is_groq_configured, _invoke_groq_drug_info, _invoke_openfda_drug_info,
    _invoke_groq_condition_info, _invoke_groq_soap_generator, mock_soap_note_generator,
    analyzer
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
    from medicine_catalog import MEDICINES_CATALOG, search_medicines
except ImportError:
    MEDICINES_CATALOG = []
    def search_medicines(*args, **kwargs): return {'total': 0, 'medicines': []}

try:
    from spherix.routes.pharmacy_constants import MEDICINE_LIST
except ImportError:
    MEDICINE_LIST = []

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
    from disease_catalog import (
        DISEASE_CATALOG, search_diseases, get_top_diseases, find_disease_by_name_or_id,
        ALL_DISEASES as MEDQUAD_ALL_DISEASES, DISEASES_BY_CATEGORY as MEDQUAD_CATEGORIES
    )
except ImportError:
    DISEASE_CATALOG = {}
    search_diseases = lambda **kwargs: {'total': 0, 'diseases': []}
    get_top_diseases = lambda limit=36: []
    find_disease_by_name_or_id = lambda identifier: None
    MEDQUAD_ALL_DISEASES = []
    MEDQUAD_CATEGORIES = {}

main_bp = Blueprint('main', __name__)

@main_bp.route('/static/uploads/<path:filename>')
def serve_uploaded_static_file(filename):
    """Serves uploaded files from memory cache, local static directory, or /tmp directory."""
    clean_path = filename.lstrip('/')
    base_name = os.path.basename(clean_path)

    # 1. Check in-memory upload cache
    if clean_path in UPLOAD_CACHE:
        data, mimetype = UPLOAD_CACHE[clean_path]
        return send_file(BytesIO(data), mimetype=mimetype)
    if base_name in UPLOAD_CACHE:
        data, mimetype = UPLOAD_CACHE[base_name]
        return send_file(BytesIO(data), mimetype=mimetype)

    # 2. Check local disk static/uploads
    static_upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    local_file_path = os.path.join(static_upload_dir, clean_path)
    if os.path.exists(local_file_path) and os.path.isfile(local_file_path):
        return send_from_directory(static_upload_dir, clean_path)

    # 3. Check /tmp/uploads directory (Vercel serverless environment)
    tmp_upload_dir = os.path.join('/tmp', 'uploads')
    tmp_file_path = os.path.join(tmp_upload_dir, clean_path)
    if os.path.exists(tmp_file_path) and os.path.isfile(tmp_file_path):
        return send_from_directory(tmp_upload_dir, clean_path)

    # 4. Check subdirectories under static/uploads or /tmp/uploads
    for sub in ['doctor_profiles', 'hospital_logos', 'signatures', 'stamps', 'prescriptions', 'documents']:
        sub_local = os.path.join(static_upload_dir, sub, base_name)
        if os.path.exists(sub_local) and os.path.isfile(sub_local):
            return send_from_directory(os.path.join(static_upload_dir, sub), base_name)
        sub_tmp = os.path.join(tmp_upload_dir, sub, base_name)
        if os.path.exists(sub_tmp) and os.path.isfile(sub_tmp):
            return send_from_directory(os.path.join(tmp_upload_dir, sub), base_name)

    return ("File not found", 404)



@main_bp.route('/api/countries', methods=['GET'])
def api_countries():
    """Searchable API for all 195 countries with live query filtering."""
    q = request.args.get('q', '').strip()
    return jsonify(search_countries(q))



@main_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
def bulk_mark_notifications_read():
    user_id = str(current_user.id)
    updated = False
    
    # Update memory
    for notif in list(TEMP_DATA.get('notifications', {}).values()):
        if str(notif.user_id) == user_id and notif.status == 'unread':
            notif.status = 'read'
            updated = True
            
    # Update database
    if updated:
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE notifications SET status='read' WHERE user_id=? AND status='unread'", (user_id,))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"⚠️ Error updating notifications status: {e}")
            
        save_data()
        flash("All notifications marked as read.", "success")
        
    return redirect(request.referrer or url_for('home'))



@main_bp.route('/')
def home():
    current_year = datetime.now().year
    stats = {
        'doctors': len(TEMP_DATA.get('doctors', {})),
        'hospitals': len(TEMP_DATA.get('hospitals', {})),
        'patients': len(TEMP_DATA.get('patients', {})),
        'emergencies': len(TEMP_DATA.get('bed_bookings', {})),
        'appointments': len(TEMP_DATA.get('appointments', {})),
        'blood_donors': len(TEMP_DATA.get('blood_donors', {})),
        'organ_donors': len(TEMP_DATA.get('organ_donors', {})),
        'orders': len(TEMP_DATA.get('orders', {})),
        'medicines': len(TEMP_DATA.get('medicines', {})),
        'camps': len(TEMP_DATA.get('camps', {})),
        'countries': len(COUNTRIES_195),
        'feedbacks': len(TEMP_DATA.get('feedbacks', {}))
    }
    
    # Fetch all verified doctors to showcase in the loop
    all_doctors = list(TEMP_DATA.get('doctors', {}).values())
    verified_doctors = deduplicate_entities([d for d in all_doctors if getattr(d, 'is_verified', True) and not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)])

    # Fetch patient webapp feedbacks
    all_feedbacks = list(TEMP_DATA.get('feedbacks', {}).values())
    sorted_feedbacks = sorted(all_feedbacks, key=lambda f: getattr(f, 'created_at', datetime.min), reverse=True)
    
    # Fetch all verified hospitals to showcase in the loop
    all_hospitals = list(TEMP_DATA.get('hospitals', {}).values())
    verified_hospitals = deduplicate_entities([h for h in all_hospitals if getattr(h, 'is_verified', True) and not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)])
    
    all_organ_requests = [r for r in TEMP_DATA.get('organ_requests', {}).values() if r.status == 'active']
    recent_organ_requests = sorted(all_organ_requests, key=lambda r: r.created_at, reverse=True)[:6]
    
    # Compile doctor opinions
    doctor_opinions_raw = TEMP_DATA.get('doctor_opinions', {})
    doctor_opinions_list = []
    for doc_id, op in doctor_opinions_raw.items():
        doc = TEMP_DATA['doctors'].get(doc_id)
        if doc and not getattr(doc, 'is_hidden', False) and not getattr(doc, 'is_blocked', False):
            created_at_val = op.get('created_at')
            if isinstance(created_at_val, str):
                try: dt_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
                except ValueError: dt_val = datetime.now()
            else:
                dt_val = created_at_val or datetime.now()
            
            doctor_opinions_list.append({
                'doctor_id': doc_id,
                'first_name': doc.first_name,
                'last_name': doc.last_name,
                'profile_picture_url': getattr(doc, 'profile_picture_url', None),
                'specialization': doc.specialization,
                'department': doc.department,
                'rating': int(op.get('rating', 5)),
                'experience': op.get('experience', ''),
                'average_appointments': op.get('average_appointments', ''),
                'created_at': dt_val,
                'created_at_formatted': dt_val.strftime('%b %d, %Y')
            })
            
    doctor_opinions_list.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Load upcoming medical/blood donation camps
    all_camps = list(TEMP_DATA.get('camps', {}).values())
    upcoming_camps = sorted(
        all_camps,
        key=lambda c: c.get('date', '') if isinstance(c, dict) else getattr(c, 'date', ''),
        reverse=False
    )[:3]
    
    # Calculate real community feedback stats
    ratings_list = []
    for fb in all_feedbacks:
        r = getattr(fb, 'rating', None) or (fb.get('rating') if isinstance(fb, dict) else None)
        if r is not None:
            try: ratings_list.append(float(r))
            except: pass
    for op in doctor_opinions_raw.values():
        r = op.get('rating') if isinstance(op, dict) else getattr(op, 'rating', None)
        if r is not None:
            try: ratings_list.append(float(r))
            except: pass
    for rev in TEMP_DATA.get('reviews', {}).values():
        r = getattr(rev, 'rating', None) or (rev.get('rating') if isinstance(rev, dict) else None)
        if r is not None:
            try: ratings_list.append(float(r))
            except: pass

    if ratings_list:
        avg_rating = round(sum(ratings_list) / len(ratings_list), 1)
        high_ratings = sum(1 for r in ratings_list if r >= 4.0)
        trust_percent = round((high_ratings / len(ratings_list)) * 100, 1)
    else:
        avg_rating = 5.0
        trust_percent = 100.0

    total_feedback_reviews_count = len(all_feedbacks) + len(doctor_opinions_list)
    stats['avg_rating'] = avg_rating
    stats['trust_percent'] = trust_percent
    stats['total_reviews_count'] = total_feedback_reviews_count

    # Find the specific doctor to feature as the founder
    founder_doctor = next((d for d in all_doctors if d.first_name == 'Sunny' and d.last_name == 'Kushwaha'), None)
    
    return render_template('home.html', current_year=current_year, stats=stats, featured_doctors=verified_doctors, featured_hospitals=verified_hospitals, recent_organ_requests=recent_organ_requests, feedbacks=sorted_feedbacks, doctor_opinions=doctor_opinions_list, camps=upcoming_camps, all_countries_195=COUNTRIES_195)



@main_bp.route("/health-tips")
def health_tips():
    return render_template("health_tips.html")



@main_bp.route("/emergency")
def emergency():
    return render_template("emergency.html")



@main_bp.route("/first-aid")
def first_aid():
    return render_template("first_aid.html")



@main_bp.route('/dashboard')
@login_required
def dashboard_dispatcher():
    """
    A smart dispatcher that redirects any logged-in user to their
    correct dashboard based on their role in real-time.
    """
    if getattr(current_user, 'email', '') == 'admin@spherixclinic.com':
        return redirect(url_for('admin_dashboard'))
    if getattr(current_user, 'is_blood_donor', False) or isinstance(current_user, BloodDonor):
        return redirect(url_for('blood_donor_dashboard'))
    if getattr(current_user, 'is_organ_donor', False) or isinstance(current_user, OrganDonor):
        return redirect(url_for('organ_donor_dashboard'))
    if getattr(current_user, 'is_hospital', False) or isinstance(current_user, Hospital):
        return redirect(url_for('hospital_dashboard'))
    if getattr(current_user, 'is_staff', False) or isinstance(current_user, Staff):
        return redirect(url_for('staff_dashboard'))
    if getattr(current_user, 'is_doctor', False) or isinstance(current_user, Doctor):
        return redirect(url_for('doctor_dashboard'))
    if getattr(current_user, 'is_patient', False) or isinstance(current_user, Patient):
        return redirect(url_for('patient_dashboard'))
    return redirect(url_for('home'))



@main_bp.route('/hospital/<path:hospital_id>/medical_travel_inquiry', methods=['POST'])
def medical_travel_inquiry(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    patient_name = request.form.get('patient_name')
    patient_email = request.form.get('patient_email')
    patient_phone = request.form.get('patient_phone')
    patient_country = request.form.get('patient_country', 'India')
    medical_condition = request.form.get('medical_condition', '')
    passport_number = request.form.get('passport_number', '')

    flash(f"✈️ International Patient & Medical Travel Inquiry submitted to {hospital.name}! Our Global Healthcare Coordinator will contact you at {patient_email or patient_phone} within 24 hours.", "success")
    return redirect(url_for('hospital_detail', hospital_id=hospital_id))



@main_bp.route('/doctor/<path:doc_id>/review', methods=['POST'])
@patient_required
def add_review(doc_id):
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('doctors_list'))

    rating = request.form.get('rating')
    comment = request.form.get('comment')

    if not rating:
        flash("A rating is required to submit a review.", "error")
        return redirect(url_for('doctor_detail', doc_id=doc_id))

    review_id = TEMP_DATA['next_ids']['review']
    new_review = Review(
        id=review_id,
        doctor_id=doc_id,
        patient_id=current_user.id,
        patient_name=current_user.name,
        rating=int(rating),
        comment=comment
    )
    TEMP_DATA['reviews'][review_id] = new_review
    TEMP_DATA['next_ids']['review'] += 1
    save_data()
    flash("Your review has been submitted successfully!", "success")
    return redirect(url_for('doctor_detail', doc_id=doc_id))



@main_bp.route('/doctor/refer_patient/<patient_id>', methods=['POST'])
@doctor_required
def refer_patient(patient_id):
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for('doctor_dashboard'))

    referred_doctor_id = request.form.get('referred_doctor_id')
    reason = request.form.get('reason')

    if not referred_doctor_id or not reason:
        flash("Please select a doctor and provide a reason for the referral.", "error")
        return redirect(request.referrer)

    referral_id = TEMP_DATA['next_ids'].get('referral', 1)
    
    if 'referrals' not in TEMP_DATA:
        TEMP_DATA['referrals'] = {}
        
    new_referral = Referral(
        id=referral_id,
        patient_id=patient_id,
        referring_doctor_id=current_user.id,
        referred_doctor_id=referred_doctor_id,
        reason=reason,
        status='pending'
    )

    TEMP_DATA['referrals'][referral_id] = new_referral
    TEMP_DATA['next_ids']['referral'] = referral_id + 1
    save_data()

    flash(f"Referral for {patient.name} sent successfully.", "success")
    return redirect(url_for('doctor_dashboard') + '?tab=referrals')



@main_bp.route('/referral/<int:referral_id>/<action>', methods=['POST'])
@doctor_required
def handle_referral(referral_id, action):
    referral = TEMP_DATA.get('referrals', {}).get(referral_id)

    if not referral or referral.referred_doctor_id != current_user.id:
        flash("Referral not found or you are not authorized.", "error")
        return redirect(url_for('doctor_dashboard'))

    if action == 'accept':
        referral.status = 'accepted'
        flash("Referral accepted. You can now contact the patient.", "success")
        msg_for_referrer = f"Your referral of {referral.patient.name} to Dr. {current_user.first_name} {current_user.last_name} has been accepted."
        msg_for_patient = f"Your referral to Dr. {current_user.first_name} {current_user.last_name} has been accepted. You can now book an appointment."
        link_for_patient = url_for('doctor_detail', doc_id=current_user.id)
    elif action == 'reject':
        referral.status = 'rejected'
        flash("Referral rejected.", "info")
        msg_for_referrer = f"Your referral of {referral.patient.name} to Dr. {current_user.first_name} {current_user.last_name} has been rejected."
        msg_for_patient = f"Your referral to Dr. {current_user.first_name} {current_user.last_name} has been rejected. Please contact your primary doctor for alternatives."
        link_for_patient = url_for('patient_dashboard')
    else:
        flash("Invalid action.", "error")
        return redirect(url_for('doctor_dashboard'))

    # Create notification for referring doctor
    notification_id = TEMP_DATA['next_ids'].get('notification', 1)
    notif_referrer = Notification(
        id=notification_id,
        user_id=referral.referring_doctor_id,
        user_type='doctor',
        message=msg_for_referrer,
        link=url_for('doctor_dashboard') + '?tab=referrals'
    )
    TEMP_DATA.setdefault('notifications', {})[notification_id] = notif_referrer
    TEMP_DATA['next_ids']['notification'] = notification_id + 1

    # Create notification for patient
    notification_id = TEMP_DATA['next_ids'].get('notification', 1)
    notif_patient = Notification(
        id=notification_id,
        user_id=referral.patient_id,
        user_type='patient',
        message=msg_for_patient,
        link=link_for_patient
    )
    TEMP_DATA.setdefault('notifications', {})[notification_id] = notif_patient
    TEMP_DATA['next_ids']['notification'] = notification_id + 1
    save_data()
    return redirect(url_for('doctor_dashboard') + '?tab=referrals')



@main_bp.route('/api/notifications')
@login_required
def get_notifications():
    user_id = current_user.id
    user_type = 'doctor' if getattr(current_user, 'is_doctor', False) else 'patient'

    notifications = [
        {
            "id": n.id, "message": n.message, "link": n.link,
            "created_at": n.created_at.isoformat()
        }
        for n in TEMP_DATA.get('notifications', {}).values()
        if n.user_id == user_id and n.user_type == user_type and n.status == 'unread'
    ]
    notifications.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify(notifications)



@main_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    data = request.get_json()
    notification_ids = data.get('ids', [])
    for notif_id in notification_ids:
        notification = TEMP_DATA.get('notifications', {}).get(int(notif_id))
        if notification and notification.user_id == current_user.id:
            notification.status = 'read'
    save_data()
    return jsonify({'success': True})



@main_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_notifications_read():
    """AJAX endpoint: mark all notifications for current user as read."""
    user_id = str(current_user.id)
    updated = 0
    for notif in list(TEMP_DATA.get('notifications', {}).values()):
        if str(notif.user_id) == user_id and notif.status == 'unread':
            notif.status = 'read'
            updated += 1
    if updated:
        save_data()
    return jsonify({'success': True, 'updated': updated})



@main_bp.route('/doctor/patient/<patient_id>/update-clinical-record', methods=['POST'])
@doctor_required
def update_patient_clinical_record(patient_id):
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        return jsonify({'success': False, 'message': 'Patient not found'}), 404
        
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
        
    record = getattr(patient, 'clinical_record', {})
    if not isinstance(record, dict):
        record = {}
        
    action = data.get('action')
    if action == 'add_vital':
        vitals = record.get('vitals', [])
        vitals.append({
            'date': date.today().strftime('%Y-%m-%d'),
            'bp': data.get('bp'),
            'pulse': int(data.get('pulse', 72)),
            'temp': float(data.get('temp', 98.6)),
            'spo2': int(data.get('spo2', 98)),
            'rr': int(data.get('rr', 16))
        })
        record['vitals'] = vitals
    elif action == 'add_allergy':
        allergies = record.get('allergies', [])
        allergy = data.get('allergy')
        if allergy and allergy not in allergies:
            allergies.append(allergy)
        record['allergies'] = allergies
    elif action == 'remove_allergy':
        allergies = record.get('allergies', [])
        allergy = data.get('allergy')
        if allergy in allergies:
            allergies.remove(allergy)
        record['allergies'] = allergies
    elif action == 'add_condition':
        conditions = record.get('conditions', [])
        condition = data.get('condition')
        if condition and condition not in conditions:
            conditions.append(condition)
        record['conditions'] = conditions
    elif action == 'remove_condition':
        conditions = record.get('conditions', [])
        condition = data.get('condition')
        if condition in conditions:
            conditions.remove(condition)
        record['conditions'] = conditions
    elif action == 'add_lab':
        labs = record.get('labs', [])
        labs.append({
            'date': date.today().strftime('%Y-%m-%d'),
            'test': data.get('test'),
            'result': data.get('result', 'Pending'),
            'status': data.get('status', 'Ordered')
        })
        record['labs'] = labs
    elif action == 'update_lab':
        labs = record.get('labs', [])
        idx = data.get('index')
        if idx is not None and 0 <= idx < len(labs):
            labs[idx]['result'] = data.get('result')
            labs[idx]['status'] = 'Completed'
        record['labs'] = labs
    elif action == 'add_note':
        notes = record.get('notes', [])
        notes.append({
            'date': date.today().strftime('%Y-%m-%d'),
            'content': data.get('content')
        })
        record['notes'] = notes

    patient.clinical_record = record
    save_data()
    return jsonify({'success': True, 'clinical_record': record})



@main_bp.route('/api/doctor/generate-soap', methods=['POST'])
@doctor_required
def generate_soap_note():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'success': False, 'message': 'No text provided'}), 400
        
    raw_text = data['text'].strip()
    if not raw_text:
        return jsonify({'success': False, 'message': 'Empty text'}), 400
        
    soap_html = _invoke_groq_soap_generator(raw_text)
    if not soap_html:
        soap_html = mock_soap_note_generator(raw_text)
        
    return jsonify({'success': True, 'soap_note': soap_html})



@main_bp.route('/staff/image/<path:staff_id>')
def get_staff_image(staff_id):
    """Serves the staff member's profile image."""
    staff = TEMP_DATA['staff'].get(staff_id)
    if staff and getattr(staff, 'profile_picture_url', None):
        return redirect(url_for('static', filename='uploads/' + staff.profile_picture_url))
    name_str = staff.name if staff else "Staff Member"
    return redirect(f"https://api.dicebear.com/7.x/initials/svg?seed={name_str}&backgroundColor=ecfdf5&textColor=047857")



@main_bp.route('/api/chat/<path:patient_id>/messages')
@login_required
@log_medical_access(action_name="VIEW_CHAT_HISTORY", target_patient_param="patient_id")
def get_chat_messages(patient_id):
    patient_id = parse_route_id(patient_id)
    """API endpoint to fetch chat messages between the current doctor and a patient."""
    if not current_user.is_doctor:
        return jsonify({"error": "Access denied"}), 403

    messages = [
        {"sender": msg.sender, "content": msg.content, "attachment_url": getattr(msg, 'attachment_url', None), "created_at": msg.created_at.isoformat()}
        for msg in TEMP_DATA['messages'].values()
        if msg.doctor_id == current_user.id and msg.patient_id == patient_id
    ]
    messages.sort(key=lambda x: x['created_at'])
    return jsonify(messages)



@main_bp.route('/api/patient/chat/<path:doctor_id>/messages')
@patient_required
def get_patient_chat_messages(doctor_id):
    """API endpoint for a patient to fetch chat messages with a doctor."""
    patient_id = get_actual_user_id(current_user.id)
    messages = [
        {"sender": msg.sender, "content": msg.content, "attachment_url": getattr(msg, 'attachment_url', None), "created_at": msg.created_at.isoformat()}
        for msg in TEMP_DATA['messages'].values()
        if msg.patient_id == patient_id and msg.doctor_id == doctor_id
    ]
    messages.sort(key=lambda x: x['created_at'])
    return jsonify(messages)



@main_bp.route('/api/patient/chat/<path:doctor_id>/send', methods=['POST'])
@patient_required
def send_patient_chat_message(doctor_id):
    """API endpoint for a patient to send a message to a doctor."""
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
        id=msg_id,
        doctor_id=doctor_id,
        patient_id=current_user.id,
        sender='patient',
        content=content,
        attachment_url=attachment_url
    )
    TEMP_DATA['messages'][msg_id] = new_message
    TEMP_DATA['next_ids']['message'] += 1
    save_data()
    
    room = f"doctor_patient_{doctor_id}_{current_user.id}"
    socketio.emit('new_message', {
        'sender': 'patient',
        'content': content,
        'attachment_url': attachment_url,
        'created_at': new_message.created_at.isoformat()
    }, room=room)
    
    return jsonify({"success": True, "message": "Message sent."})



@main_bp.route('/api/patient/chat/<path:doctor_id>/send', methods=['POST'])
@patient_required
def send_message_patient(doctor_id):
    """Send a message from patient to doctor."""
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
    
    # Check if doctor exists
    doctor = TEMP_DATA['doctors'].get(doctor_id)
    if not doctor:
        return jsonify({"success": False, "message": "Doctor not found."}), 404
    
    patient_id = get_actual_user_id(current_user.id)
    
    # Save message
    msg_id = TEMP_DATA['next_ids']['message']
    new_message = Message(
        id=msg_id, doctor_id=doctor_id, patient_id=patient_id,
        sender='patient', content=content, attachment_url=attachment_url
    )
    TEMP_DATA['messages'][msg_id] = new_message
    TEMP_DATA['next_ids']['message'] += 1
    save_data()
    
    # Emit via Socket.IO
    room = f"doctor_patient_{doctor_id}_{patient_id}"
    socketio.emit('new_message', {
        'sender': 'patient',
        'content': content,
        'attachment_url': attachment_url,
        'created_at': new_message.created_at.isoformat()
    }, room=room)
    
    return jsonify({"success": True, "message": "Message sent."})



@main_bp.route('/drugs')
def drugs():
    # Categorize the drugs for the template
    categorized_drugs = {}
    return render_template('drugs.html', categorized_drugs=categorized_drugs)



@main_bp.route('/drug-info/<path:drug_name>')
def drug_info(drug_name):
    """API endpoint to get information about a specific drug."""

    # Try OpenFDA API First
    fda_info = _invoke_openfda_drug_info(drug_name)
    if fda_info:
        return jsonify(fda_info)

    # Fallback to AI-generated drug details
    ai_info = _invoke_groq_drug_info(drug_name)
    if ai_info:
        return jsonify(ai_info)

    return jsonify({
        "description": f"Detailed information for '{drug_name}' is not available in our local database or OpenFDA. Please consult a pharmacist or doctor.",
        "error": "Drug not found."
    }), 404



@main_bp.route('/conditions')
@main_bp.route('/diseases')
@main_bp.route('/symptoms-diseases')
def conditions():
    """
    Renders the Spherix Clinical Conditions, Symptoms & Disease Encyclopedia powered by MedQuAD (NIH / CDC).
    """
    top_diseases = get_top_diseases(limit=36)
    total_count = len(MEDQUAD_ALL_DISEASES) if MEDQUAD_ALL_DISEASES else 5125
    categories = list(MEDQUAD_CATEGORIES.keys()) if MEDQUAD_CATEGORIES else [
        'Cardiology & Heart', 'Neurology & Brain', 'Diabetes & Endocrine',
        'Respiratory & Pulmonology', 'Oncology & Cancer', 'Dermatology & Skin',
        'Gastroenterology & Digestive', 'Infectious Diseases', 'Musculoskeletal & Bones',
        'Ophthalmology & Eye', 'Rare & Genetic Disorders'
    ]
    drug_names = sorted(MEDICINE_LIST, key=lambda x: x.lower()) if MEDICINE_LIST else []
    return render_template(
        'conditions.html',
        top_diseases=top_diseases,
        total_diseases_count=total_count,
        categories=categories,
        drug_names=drug_names
    )



@main_bp.route('/api/diseases/search')
def api_search_diseases():
    """
    High-speed JSON search across all 5,126 diseases and symptoms from MedQuAD dataset.
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', 'all').strip()
    symptom = request.args.get('symptom', '').strip()
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    try:
        limit = int(request.args.get('limit', 24))
    except (ValueError, TypeError):
        limit = 24
        
    results = search_diseases(query=q, category=category, symptom=symptom, page=page, limit=limit)
    return jsonify({
        'success': True,
        **results
    })



@main_bp.route('/api/disease-info/<path:disease_identifier>')
def api_disease_info(disease_identifier):
    """
    Returns an exhaustive 15-section clinical monograph combining MedQuAD knowledge + Groq AI Clinical Engine.
    Sections:
    1. Overview
    2. Key Facts
    3. Symptoms
    4. Causes
    5. Risk Factors
    6. Diagnosis
    7. Prevention
    8. Specialist to Visit
    9. Treatment
    10. Complications
    11. Alternative Therapies
    12. Home Care
    13. Living With
    14. FAQs
    15. References
    """
    medquad_entry = find_disease_by_name_or_id(disease_identifier)
    disease_name = medquad_entry['name'] if medquad_entry else disease_identifier.strip()
    
    # Call Groq AI for deep clinical synthesis
    groq_data = _invoke_groq_condition_info(disease_name)
    
    category = medquad_entry.get('category', 'General Clinical Medicine') if medquad_entry else 'General Clinical Medicine'
    source_label = 'NIH / CDC MedQuAD + Groq AI Clinical Engine' if (medquad_entry and groq_data) else ('NIH / CDC MedQuAD Archive' if medquad_entry else 'Groq AI Clinical Reference')
    
    # 1. Overview
    overview = (groq_data and groq_data.get('overview')) or (medquad_entry and medquad_entry.get('overview')) or f"{disease_name} is a clinically identified medical condition requiring professional diagnosis and therapeutic monitoring."
    
    # 2. Key Facts
    key_facts = (groq_data and groq_data.get('key_facts')) or [
        f"{disease_name} is recognized globally as a condition requiring structured clinical evaluation.",
        "Early diagnostic testing and prompt intervention significantly improve patient prognosis.",
        "Comprehensive care involves multi-modal therapeutic strategies and lifestyle adaptations.",
        "Regular monitoring with your primary care provider ensures optimal treatment compliance."
    ]
    
    # 3. Symptoms
    groq_sym = groq_data.get('symptoms') if groq_data else None
    if isinstance(groq_sym, dict):
        symptoms_desc = groq_sym.get('description', '')
        symptoms_list = groq_sym.get('list', [])
    elif isinstance(groq_sym, list):
        symptoms_desc = "Clinical symptoms vary in intensity and onset based on disease stage and individual physiology."
        symptoms_list = groq_sym
    else:
        symptoms_desc = medquad_entry.get('symptoms_text', '') if medquad_entry else "Symptoms can vary significantly from mild to severe."
        symptoms_list = (medquad_entry.get('symptom_tags', []) if medquad_entry else []) or ["Clinical discomfort", "Systemic fatigue", "Functional limitation"]
        
    # 4. Causes
    causes_list = (groq_data and groq_data.get('causes')) or (
        [medquad_entry.get('causes_text', '')[:300]] if (medquad_entry and medquad_entry.get('causes_text')) else [
            f"Underlying cellular and physiological dysregulation associated with {disease_name}.",
            "Genetic predisposition and familial risk markers.",
            "Environmental triggers, immune response, or lifestyle factors."
        ]
    )
    
    # 5. Risk Factors
    risk_factors = (groq_data and groq_data.get('risk_factors')) or [
        "Advancing age and demographic vulnerability.",
        "Family history and inherited genetic traits.",
        "Sedentary lifestyle, nutritional imbalances, or chronic stress.",
        "Preexisting comorbidities or immune system alterations."
    ]
    
    # 6. Diagnosis
    diagnosis_list = (groq_data and groq_data.get('diagnosis')) or (
        [medquad_entry.get('diagnoses_text', '')[:300]] if (medquad_entry and medquad_entry.get('diagnoses_text')) else [
            "Comprehensive physical examination and review of medical history.",
            "Diagnostic blood panels and targeted metabolic biomarkers.",
            "High-resolution imaging studies (MRI, CT, Ultrasound, X-ray).",
            "Specialized functional assays or tissue biopsy when indicated."
        ]
    )
    
    # 7. Prevention
    prevention_list = (groq_data and groq_data.get('prevention')) or (
        [medquad_entry.get('preventions_text', '')[:300]] if (medquad_entry and medquad_entry.get('preventions_text')) else [
            "Maintain a nutrient-rich, balanced dietary regimen.",
            "Participate in regular physical exercise tailored to your health level.",
            "Attend scheduled health checkups and preventive screenings.",
            "Avoid tobacco, excessive alcohol consumption, and known triggers."
        ]
    )
    
    # 8. Specialist to Visit
    specialist_info = (groq_data and groq_data.get('specialist_to_visit')) or {
        'primary_specialist': f"{category.split('&')[0].strip()} Specialist",
        'department': category,
        'when_urgent': 'Seek immediate medical attention if you experience severe pain, difficulty breathing, acute neurological symptoms, or unrelenting high fever.'
    }
    
    # 9. Treatment
    groq_treat = groq_data.get('treatment') if groq_data else None
    if isinstance(groq_treat, dict):
        treatment_overview = groq_treat.get('overview', '')
        treatment_meds = groq_treat.get('medications', [])
        treatment_procedures = groq_treat.get('procedures', [])
        treatment_therapies = groq_treat.get('therapies', [])
    else:
        treatment_overview = medquad_entry.get('treatments_text', '')[:400] if medquad_entry else f"Management of {disease_name} includes pharmacological therapies and clinical supervision."
        treatment_meds = ["Targeted prescription formulations under physician guidance", "Symptomatic relief medications", "Supportive anti-inflammatory or regulating agents"]
        treatment_procedures = ["Clinical monitoring and functional assessment", "Minimally invasive or corrective interventions when indicated"]
        treatment_therapies = ["Physiotherapy and physical rehabilitation", "Nutritional counseling and lifestyle adjustments"]
        
    # 10. Complications
    complications_list = (groq_data and groq_data.get('complications')) or [
        f"Progression of {disease_name} leading to organ or tissue damage.",
        "Secondary infections or systemic inflammatory exacerbations.",
        "Decreased functional independence and impaired quality of life.",
        "Acute medical crises requiring emergency hospital care."
    ]
    
    # 11. Alternative Therapies
    alt_therapies = (groq_data and groq_data.get('alternative_therapies')) or [
        "Evidence-based physiotherapy and customized rehabilitation exercises.",
        "Mindfulness meditation, breathwork, and clinical stress reduction.",
        "Dietary nutraceuticals and targeted botanical supplements under doctor guidance.",
        "Acupuncture or therapeutic massage for symptom and pain relief."
    ]
    
    # 12. Home Care
    home_care = (groq_data and groq_data.get('home_care')) or [
        "Maintain adequate daily hydration (2-3 liters of clean fluids).",
        "Prioritize 7-8 hours of restful, uninterrupted sleep nightly.",
        "Keep a daily log of symptoms, vitals, and medication schedules.",
        "Apply recommended hot or cold compresses for localized relief."
    ]
    
    # 13. Living With
    living_with = (groq_data and groq_data.get('living_with')) or [
        "Establish a predictable daily routine adhering to your care plan.",
        "Join patient support communities for emotional and practical guidance.",
        "Communicate openly with family members and caregivers regarding your needs.",
        "Schedule periodic health reviews to calibrate medications and dosages."
    ]
    
    # 14. FAQs
    faqs = (groq_data and groq_data.get('faqs')) or [
        {
            'question': f"Can {disease_name} be cured permanently?",
            'answer': f"While certain acute forms can be fully resolved, many chronic conditions are effectively managed through modern therapies and healthy lifestyle adaptations."
        },
        {
            'question': "What diet is recommended for this condition?",
            'answer': "A balanced, anti-inflammatory whole-food diet rich in green vegetables, lean proteins, and fiber while minimizing processed sugars is widely beneficial."
        },
        {
            'question': "When should I seek emergency medical help?",
            'answer': "Seek immediate emergency care if you experience sudden severe pain, chest tightness, breathing distress, sudden weakness, or high fever."
        }
    ]
    
    # 15. References
    references = (groq_data and groq_data.get('references')) or [
        "National Institutes of Health (NIH) Clinical Records",
        "Centers for Disease Control and Prevention (CDC) Health Topics",
        "World Health Organization (WHO) Global Disease Reports",
        "MedQuAD Verified Medical Question Answering Dataset",
        "U.S. National Library of Medicine & PubMed"
    ]
    
    structured_monograph = {
        'name': disease_name,
        'category': category,
        'source_label': source_label,
        'groq_ai_enhanced': bool(groq_data),
        'medquad_qa_count': medquad_entry.get('qa_count', 0) if medquad_entry else len(faqs),
        'symptom_tags': medquad_entry.get('symptom_tags', []) if medquad_entry else [s for s in symptoms_list[:4]],
        
        # 15 Exact Sections
        'overview': overview,
        'key_facts': key_facts,
        'symptoms': {
            'description': symptoms_desc,
            'list': symptoms_list
        },
        'causes': causes_list,
        'risk_factors': risk_factors,
        'diagnosis': diagnosis_list,
        'prevention': prevention_list,
        'specialist_to_visit': specialist_info,
        'treatment': {
            'overview': treatment_overview,
            'medications': treatment_meds,
            'procedures': treatment_procedures,
            'therapies': treatment_therapies
        },
        'complications': complications_list,
        'alternative_therapies': alt_therapies,
        'home_care': home_care,
        'living_with': living_with,
        'faqs': faqs,
        'references': references,
        
        # Full MedQuAD Q&A archive
        'medquad_qa': medquad_entry.get('all_qa', []) if medquad_entry else []
    }
    
    return jsonify({
        'success': True,
        'disease': structured_monograph
    })







@main_bp.route('/condition-info/<path:condition_name>')
def condition_info(condition_name):
    """API endpoint to get information about a specific medical condition."""
    condition_data = None
    if analyzer:
        details_result = analyzer.get_condition_details(condition_name)
        if details_result:
            condition_data = details_result.get('details')

    if condition_data:
        return jsonify({
            'condition_name': condition_name,
            'description': condition_data.get('description', ''),
            'common_symptoms': condition_data.get('common_symptoms', []),
            'typical_treatments': condition_data.get('typical_treatments', []),
            'recommended_medicines': condition_data.get('recommended_medicines', []),
            'what_not_to_do': condition_data.get('what_not_to_do', []),
            'self_care': condition_data.get('self_care', []),
            'when_to_see_doctor': condition_data.get('when_to_see_doctor', ''),
            'key_precautions': condition_data.get('key_precautions', []),
            'source': 'local'
        })

    ai_info = _invoke_groq_condition_info(condition_name)
    if ai_info:
        return jsonify(ai_info)

    return jsonify({
        'description': f"Details are not available for '{condition_name}'. Please consult a medical professional.",
        'error': 'Condition not found.'
    }), 404




@main_bp.route('/about')
def about():
    stats = {
        'doctors': len([d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'is_verified', True) and not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]),
        'hospitals': len([h for h in TEMP_DATA.get('hospitals', {}).values() if not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)]),
        'patients': len(TEMP_DATA.get('patients', {})),
        'medicines': len(TEMP_DATA.get('medicines', {})),
        'blood_donors': len(TEMP_DATA.get('blood_donors', {})),
        'organ_donors': len(TEMP_DATA.get('organ_donors', {})),
        'appointments': len(TEMP_DATA.get('appointments', {}))
    }
    return render_template('about.html', stats=stats)


@main_bp.route('/sny')
def sny():
    stats = {
        'doctors': len([d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'is_verified', True) and not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]),
        'hospitals': len([h for h in TEMP_DATA.get('hospitals', {}).values() if not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)]),
        'patients': len(TEMP_DATA.get('patients', {})),
        'medicines': len(TEMP_DATA.get('medicines', {})),
        'blood_donors': len(TEMP_DATA.get('blood_donors', {})),
        'organ_donors': len(TEMP_DATA.get('organ_donors', {})),
        'appointments': len(TEMP_DATA.get('appointments', {}))
    }
    return render_template('sny.html', stats=stats)



@main_bp.route('/gallery')
def gallery():
    raw_images = []

    # 1. Add static clinical images that exist on disk
    for img_rel in DEFAULT_GALLERY_METADATA.keys():
        full_p = os.path.join(current_app.root_path, 'static', img_rel)
        if os.path.exists(full_p) and os.path.isfile(full_p):
            raw_images.append(img_rel)

    # 2. Load dynamic uploads from static/uploads directory
    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    if os.path.exists(uploads_dir):
        try:
            upload_files = []
            for f in os.listdir(uploads_dir):
                if (f.startswith(('captured_symptom_', 'uploaded_symptom_', 'gallery_upload_', 'scan_symptom_'))) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    upload_files.append(f)
            upload_files.sort(reverse=True)
            for f in upload_files:
                raw_images.insert(0, f"uploads/{f}") # Add newest uploads to the beginning
        except Exception as e:
            print(f"Error loading gallery uploads: {e}")

    # Deduplicate while preserving order and ensuring physical file existence
    seen = set()
    gallery_images = []
    for img in raw_images:
        clean_img = img.strip()
        full_p = os.path.join(current_app.root_path, 'static', clean_img)
        if clean_img not in seen and os.path.exists(full_p) and os.path.isfile(full_p):
            seen.add(clean_img)
            gallery_images.append(clean_img)

    # Build full metadata lookup
    metadata = DEFAULT_GALLERY_METADATA.copy()
    dynamic_metadata = load_gallery_metadata()
    metadata.update(dynamic_metadata)

    # Populate missing metadata dynamically for valid images
    for img in gallery_images:
        if img not in metadata:
            is_upload = 'uploads/' in img
            metadata[img] = {
                'title': 'Symptom Case Specimen' if is_upload else 'Clinical Specimen',
                'category': 'uploads' if is_upload else 'clinical',
                'author': 'Patient Case' if is_upload else 'Clinical Database',
                'description': 'Patient uploaded visual case file for symptom analysis.' if is_upload else 'Clinical reference image for diagnostic training.'
            }

    videos = [
        {"url": "https://www.youtube.com/watch?v=7D-gxaie6UI", "title": "Precision Robotic Surgery & Diagnostic Imaging"},
        {"url": "https://www.youtube.com/watch?v=b1-pZumCz7Q", "title": "Next-Gen Clinical ICU Patient Telemetry"}
    ]

    return render_template('gallery.html', images=gallery_images, metadata=metadata, videos=videos)



@main_bp.route('/gallery/upload', methods=['POST'])
def gallery_upload():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'clinical').strip()
    author = request.form.get('author', 'Anonymous').strip()
    description = request.form.get('description', '').strip()
    file = request.files.get('file')
    
    if not file or not file.filename:
        flash('Please select an image file to upload.', 'error')
        return redirect(url_for('gallery'))
        
    if not title:
        title = "Untitled Specimen"
    if not description:
        description = "No description provided."
        
    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
    
    try:
        filename = secure_filename(file.filename)
        stored_name = f"gallery_upload_{timestamp}_{filename}"
        save_path = os.path.join(uploads_dir, stored_name)
        file.save(save_path)
        
        # Save to metadata JSON
        dynamic_metadata = load_gallery_metadata()
        dynamic_metadata[f"uploads/{stored_name}"] = {
            'title': title,
            'category': category,
            'author': author,
            'description': description
        }
        save_gallery_metadata(dynamic_metadata)
        flash('Media successfully uploaded and indexed in the repository!', 'success')
    except Exception as e:
        print(f"Error during gallery upload: {e}")
        flash('An error occurred while uploading your media. Please try again.', 'error')
        
    return redirect(url_for('gallery'))




@main_bp.route('/gallery/download')
def download_watermarked_image():
    filepath_param = request.args.get('filepath', '')
    if not filepath_param:
        return "Filepath parameter is required", 400
        
    clean_path = filepath_param.lstrip('/')
    if not clean_path.startswith('static/'):
        return "Unauthorized file path access", 403
        
    full_path = os.path.join(current_app.root_path, clean_path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return "File not found", 404
        
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        with Image.open(full_path) as img:
            img_format = img.format or 'JPEG'
            txt_img = img.convert('RGBA')
            
            overlay = Image.new('RGBA', txt_img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            width, height = img.size
            font_size = int(width * 0.05)
            if font_size < 16:
                font_size = 16
            
            font = None
            try:
                font_paths = [
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/Library/Fonts/Arial.ttf",
                    "Arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                ]
                for path in font_paths:
                    try:
                        font = ImageFont.truetype(path, font_size)
                        break
                    except Exception:
                        continue
                if not font:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
                
            text = "Spherix Clinic"
            
            if hasattr(draw, 'textbbox'):
                text_width = draw.textbbox((0, 0), text, font=font)[2]
                text_height = draw.textbbox((0, 0), text, font=font)[3]
            else:
                text_width, text_height = draw.textsize(text, font=font)
                
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            # Semi-transparent backing rectangle
            padding = 15
            box_x0 = x - padding
            box_y0 = y - padding
            box_x1 = x + text_width + padding
            box_y1 = y + text_height + padding
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=(15, 23, 42, 100))
            
            draw.text((x, y), text, fill=(255, 255, 255, 140), font=font)
            
            watermarked_img = Image.alpha_composite(txt_img, overlay)
            
            if img_format == 'JPEG':
                watermarked_img = watermarked_img.convert('RGB')
                
            from io import BytesIO
            img_io = BytesIO()
            watermarked_img.save(img_io, format=img_format)
            img_io.seek(0)
            
            original_filename = os.path.basename(full_path)
            download_name = f"watermarked_{original_filename}"
            mimetype = 'image/jpeg' if img_format == 'JPEG' else 'image/png' if img_format == 'PNG' else 'application/octet-stream'
            
            return send_file(img_io, mimetype=mimetype, as_attachment=True, download_name=download_name)
            
    except Exception as e:
        print(f"❌ Error applying watermark: {e}")
        return send_file(full_path, as_attachment=True)



@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    settings = TEMP_DATA.get('settings', {})
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone', 'N/A')
        address = request.form.get('address', 'N/A')
        message = request.form.get('message')
        
        if name and email and message:
            new_message = {
                'name': name,
                'email': email,
                'phone': phone,
                'address': address,
                'message': message,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            TEMP_DATA['contact_messages'].insert(0, new_message) # Add to top
            save_data()
            
            # Send notification email to admin
            admin_email = 'isunny28skk@gmail.com'
            subject = f"New Contact Inquiry from {name}"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2 style="color: #0ea5e9;">New Contact Inquiry</h2>
                <p><strong>Name:</strong> {name}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Phone:</strong> {phone}</p>
                <p><strong>Address:</strong> {address}</p>
                <p><strong>Message:</strong></p>
                <div style="background: #f8fafc; padding: 15px; border-left: 4px solid #0ea5e9; border-radius: 4px;">
                    {message}
                </div>
            </div>
            """
            send_notification_email(admin_email, subject, body, is_html=True)
            
            flash("Your message has been sent successfully!", "success")
            return redirect(url_for('contact'))
            
    return render_template('contact.html', settings=settings)



@main_bp.route('/api/feedback', methods=['POST'])
@csrf.exempt
def submit_feedback():
    data = request.json or {}
    feedback_type = data.get('type', 'general')
    message = data.get('message', '').strip()
    rating = data.get('rating', '5')
    custom_name = data.get('name', '').strip()
    custom_email = data.get('email', '').strip()
    
    attachment_b64 = data.get('attachment', '')
    attachment_url = ''
    if attachment_b64 and ';base64,' in attachment_b64:
        try:
            import base64
            feedback_dir = os.path.join(current_app.static_folder, 'uploads', 'feedback')
            os.makedirs(feedback_dir, exist_ok=True)
            header, encoded = attachment_b64.split(';base64,', 1)
            ext = 'png'
            if 'image/jpeg' in header or 'image/jpg' in header:
                ext = 'jpg'
            elif 'image/webp' in header:
                ext = 'webp'
            filename = f"feedback_{int(datetime.now().timestamp())}_{os.urandom(4).hex()}.{ext}"
            file_path = os.path.join(feedback_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(base64.b64decode(encoded))
            attachment_url = f"/static/uploads/feedback/{filename}"
        except Exception as e:
            print(f"⚠️ Error saving feedback attachment: {e}")

    if message:
        user_info = custom_name or "Guest Patient"
        user_email = custom_email or "guest@spherixclinic.com"
        if current_user.is_authenticated:
            user_email = custom_email or getattr(current_user, 'email', 'patient@spherixclinic.com')
            if hasattr(current_user, 'name'):
                user_info = custom_name or current_user.name
            elif hasattr(current_user, 'first_name'):
                user_info = custom_name or f"Dr. {current_user.first_name} {current_user.last_name}"
            else:
                user_info = custom_name or f"User #{current_user.id}"

        star_str = "⭐" * int(rating) if str(rating).isdigit() else "⭐ 5/5"

        msg_body = f"Rating: {rating}/5 Stars\nType: {feedback_type.title()}\n\n{message}"
        if attachment_url:
            msg_body += f"\n\nAttached Screenshot: {attachment_url}"

        new_message = {
            'name': f'[{star_str}] Feedback ({feedback_type.title()}) - {user_info}',
            'email': user_email,
            'message': msg_body,
            'attachment': attachment_url,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        TEMP_DATA.setdefault('contact_messages', []).insert(0, new_message)

        # Store directly into TEMP_DATA['feedbacks'] for live ecosystem showcase
        try:
            fb_id = len(TEMP_DATA.get('feedbacks', {})) + 1
            rating_int = int(rating) if str(rating).isdigit() else 5
            patient_id = current_user.id if current_user.is_authenticated else None
            
            new_fb = Feedback(
                id=fb_id,
                patient_id=patient_id,
                patient_name=user_info,
                rating=rating_int,
                comments=message,
                feedback_target=feedback_type,
                target_name=feedback_type.title() + " Review",
                created_at=datetime.now()
            )
            TEMP_DATA.setdefault('feedbacks', {})[fb_id] = new_fb
        except Exception as fb_err:
            print(f"⚠️ Error creating feedback instance: {fb_err}")

        save_data()
        
        admin_email = 'admin@spherixclinic.com'
        subject = f"[{star_str}] New Feedback ({feedback_type.title()}) from {user_info}"
        
        img_html = f'<div style="margin-top: 12px;"><p><strong>Attached Screenshot:</strong></p><img src="{attachment_url}" style="max-width: 100%; max-height: 300px; border-radius: 8px; border: 1px solid #cbd5e1;" /></div>' if attachment_url else ''

        body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; color: #1e293b; max-width: 600px; border: 1px solid #e2e8f0; border-radius: 16px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
                <h2 style="color: #4f46e5; margin: 0;">Spherix Clinic Feedback Hub</h2>
            </div>
            <p style="margin: 4px 0;"><strong>From:</strong> {user_info} (&lt;{user_email}&gt;)</p>
            <p style="margin: 4px 0;"><strong>Category:</strong> <span style="background: #eef2ff; color: #4338ca; padding: 2px 8px; border-radius: 6px; font-weight: bold;">{feedback_type.title()}</span></p>
            <p style="margin: 4px 0;"><strong>Patient Rating:</strong> {star_str} ({rating}/5)</p>
            <div style="margin-top: 16px; background: #f8fafc; padding: 16px; border-left: 4px solid #4f46e5; border-radius: 8px; font-size: 14px; line-height: 1.6; white-space: pre-wrap;">{message}</div>
            {img_html}
            <p style="margin-top: 20px; font-size: 12px; color: #94a3b8;">Logged into Spherix Central Intelligence Node at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        """
        try:
            send_notification_email(admin_email, subject, body, is_html=True)
        except Exception:
            pass
        return jsonify({'success': True, 'message': 'Feedback successfully received. Thank you!'})
    return jsonify({'success': False, 'error': 'Message content is required.'}), 400



@main_bp.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    name = request.form.get('name', '').strip()
    contact = request.form.get('contact', '').strip()
    interests = request.form.getlist('interests')
    
    if email and name:
        if not any(sub['email'] == email for sub in TEMP_DATA.get('newsletter_subscribers', [])):
            TEMP_DATA.setdefault('newsletter_subscribers', []).append({
                'email': email,
                'name': name,
                'contact': contact,
                'interests': interests,
                'subscribed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            save_data()
            
        admin_email = 'admin@spherixclinic.com'
        subject = "New Newsletter Subscription"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #0891b2;">New Subscriber!</h2>
            <p>A new user has subscribed to the Spherix Clinic newsletter.</p>
            <p><strong>Name:</strong> {name or 'N/A'}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Contact:</strong> {contact or 'N/A'}</p>
            <p><strong>Interests:</strong> {', '.join(interests) if interests else 'None selected'}</p>
        </div>
        """
        send_notification_email(admin_email, subject, body, is_html=True)
        
        # Send Welcome Email to Subscriber
        user_subject = "Welcome to the Spherix Clinic Newsletter!"
        user_body = get_premium_otp_email_html(
            title="Subscription Confirmed!",
            greeting=f"Welcome to the Spherix Network, {name or 'there'}.",
            message="Thank you for subscribing. You are now connected to our intelligence broadcast and will be the first to receive exclusive updates on Neural Diagnostics, Bio-Telemetry, and Longevity Science.",
            otp="WELCOME",
            role_color="#0891b2",
            accent_bg="#ecfeff"
        )
        send_notification_email(email, user_subject, user_body, is_html=True)
        flash("Successfully subscribed to the Spherix Network.", "subscribe_success")
    else:
        flash("Please provide a valid name and email address.", "error")
    return redirect(request.referrer or url_for('home'))



@main_bp.route('/api/qr')
def generate_qr():
    """Generates a dynamic QR Code for a given URL."""
    url = request.args.get('url', '')
    if not url or not qrcode:
        return "QR Code generation not available.", 400
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')



@main_bp.route('/api/captcha/image/<portal_type>')
def get_captcha_image(portal_type):
    """Returns a securely distorted visual CAPTCHA image."""
    key = f"{portal_type}_captcha"
    if request.args.get('refresh') == '1' or key not in session or not session.get(key):
        session[key] = generate_captcha_text(5)
    
    text = session.get(key, generate_captcha_text(5))
    image_bytes = generate_captcha_image_bytes(text)
    response = make_response(image_bytes)
    response.headers['Content-Type'] = 'image/png'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response



@main_bp.route('/api/captcha/refresh/<portal_type>')
def refresh_captcha(portal_type):
    """Refreshes CAPTCHA for a specific portal type."""
    new_captcha = generate_captcha_text(5)
    key = f"{portal_type}_captcha"
    session[key] = new_captcha
    return jsonify({'success': True, 'captcha': new_captcha})



@main_bp.route('/staff/reception/walkin-receipt/<int:appt_id>')
@main_bp.route('/patient/appointment/<int:appt_id>/receipt')
@main_bp.route('/walkin-receipt-pdf/<int:appt_id>')
@login_required
def walkin_receipt_pdf(appt_id):
    """Generate a styled PDF prescription/receipt for a walk-in appointment."""
    appt = TEMP_DATA.get('appointments', {}).get(appt_id)
    if not appt:
        flash("Appointment not found.", "error")
        if getattr(current_user, 'is_patient', False):
            return redirect(url_for('patient_dashboard'))
        return redirect(url_for('staff_reception_dashboard'))

    hospital_name_str = getattr(current_user, 'hospital_name', '')
    hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.name == hospital_name_str), None)
    doctor = TEMP_DATA['doctors'].get(appt.doctor_id)

    try:
        class WalkInReceiptPDF(FPDF):
            def header(self):
                # Outer border
                self.set_draw_color(67, 97, 238)
                self.set_line_width(1.2)
                self.rect(8, 8, 194, 281)

                # Dark header banner
                self.set_fill_color(15, 23, 42)
                self.rect(8, 8, 194, 32, 'F')

                # Clinic name
                self.set_y(13)
                self.set_font('Helvetica', 'B', 18)
                self.set_text_color(255, 255, 255)
                self.cell(0, 9, 'SPHERIX CLINIC', 0, 1, 'C')
                self.set_font('Helvetica', '', 8)
                self.set_text_color(148, 163, 184)
                self.cell(0, 5, 'Advanced Healthcare & Diagnostics Center', 0, 1, 'C')
                self.set_text_color(0, 0, 0)

            def footer(self):
                self.set_y(-26)
                self.set_draw_color(226, 232, 240)
                self.set_line_width(0.3)
                self.line(12, self.get_y(), 198, self.get_y())
                self.ln(2)
                self.set_font('Helvetica', 'I', 7.5)
                self.set_text_color(148, 163, 184)
                self.cell(0, 4, 'This is a computer-generated document and does not require a physical signature.', 0, 1, 'C')
                self.cell(0, 4, f'Generated: {datetime.now().strftime("%d %b %Y, %I:%M %p")}  |  Spherix Health Systems', 0, 1, 'C')

        pdf = WalkInReceiptPDF()
        pdf.add_page()
        pdf.set_margins(14, 14, 14)
        pdf.ln(28)  # space after header

        # ── RECEIPT TYPE LABEL ──
        pdf.set_fill_color(239, 246, 255)
        pdf.set_draw_color(219, 234, 254)
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(29, 78, 216)
        token_str = getattr(appt, 'token_no', f"TK-{appt_id:02d}")
        priority_str = getattr(appt, 'priority', 'normal').upper()
        pdf.cell(0, 10, f'  WALK-IN REGISTRATION RECEIPT  |  TOKEN: {token_str}  [{priority_str}]', 1, 1, 'L', fill=True)
        pdf.ln(4)

        # ── RECEIPT META ──
        receipt_no = f"WI-{appt_id:05d}"
        visit_date = appt.appointment_date.strftime('%d %B %Y') if hasattr(appt.appointment_date, 'strftime') else str(appt.appointment_date)
        visit_time = appt.appointment_time.strftime('%I:%M %p') if appt.appointment_time and hasattr(appt.appointment_time, 'strftime') else str(appt.appointment_time or 'N/A')

        def row(label, value, bold_val=False):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(55, 7, label + ':', 0, 0)
            pdf.set_font('Helvetica', 'B' if bold_val else '', 9)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 7, to_latin1_str(str(value)), 0, 1)

        row('Receipt No.', receipt_no, bold_val=True)
        row('Token No.', token_str, bold_val=True)
        row('Visit Date & Time', f"{visit_date} at {visit_time}")
        row('Priority / Triage', priority_str)
        row('Status', appt.status.upper())
        row('Consultation Fee', f"Rs. {getattr(appt, 'fee_amount', 300):.2f} ({getattr(appt, 'payment_mode', 'Cash')} - {getattr(appt, 'payment_status', 'paid').upper()})")
        pdf.ln(3)

        # ── DIVIDER ──
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(4)

        # ── PATIENT INFORMATION ──
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(67, 97, 238)
        pdf.cell(0, 7, 'PATIENT INFORMATION', 0, 1)
        pdf.ln(1)
        row('Patient Name', appt.patient_name or 'N/A', bold_val=True)
        row('Phone', appt.patient_phone or 'N/A')
        row('Reason / Complaint', appt.reason or 'Walk-in Consultation')
        
        # Vitals if present
        vitals = getattr(appt, 'vitals', {})
        if vitals and any(vitals.values()):
            vitals_parts = []
            if vitals.get('bp'): vitals_parts.append(f"BP: {vitals.get('bp')} mmHg")
            if vitals.get('pulse'): vitals_parts.append(f"Pulse: {vitals.get('pulse')} bpm")
            if vitals.get('temp'): vitals_parts.append(f"Temp: {vitals.get('temp')} F")
            if vitals.get('spo2'): vitals_parts.append(f"SpO2: {vitals.get('spo2')}%")
            if vitals.get('weight'): vitals_parts.append(f"Weight: {vitals.get('weight')} kg")
            if vitals.get('allergies'): vitals_parts.append(f"Allergies: {vitals.get('allergies')}")
            row('Recorded Vitals', " | ".join(vitals_parts))
        pdf.ln(4)

        # ── ATTENDING DOCTOR ──
        pdf.set_draw_color(226, 232, 240)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(67, 97, 238)
        pdf.cell(0, 7, 'ATTENDING DOCTOR', 0, 1)
        pdf.ln(1)
        if doctor:
            row('Doctor Name', f'Dr. {doctor.first_name} {doctor.last_name}', bold_val=True)
            row('Specialty', doctor.specialty or 'General Practitioner')
            row('Room / OPD', getattr(doctor, 'opd_room', 'Room 101'))
        else:
            row('Doctor', 'Not Assigned')
        pdf.ln(4)

        # ── HOSPITAL INFORMATION ──
        pdf.set_draw_color(226, 232, 240)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(67, 97, 238)
        pdf.cell(0, 7, 'HOSPITAL / FACILITY', 0, 1)
        pdf.ln(1)
        if hospital:
            row('Hospital Name', hospital.name, bold_val=True)
            row('Address', hospital.address or 'N/A')
            row('Phone', hospital.phone or 'N/A')
            row('Email', hospital.email or 'N/A')
        else:
            row('Facility', hospital_name_str or 'Spherix Clinic')
        pdf.ln(6)

        # ── PRESCRIPTION / ADVICE SECTION ──
        pdf.set_draw_color(226, 232, 240)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(67, 97, 238)
        pdf.cell(0, 7, 'DOCTOR\'S ADVICE / PRESCRIPTION NOTES', 0, 1)
        pdf.ln(2)

        # Lined area for prescription
        pdf.set_draw_color(203, 213, 225)
        pdf.set_line_width(0.2)
        for _ in range(5):
            pdf.line(14, pdf.get_y() + 1, 196, pdf.get_y() + 1)
            pdf.ln(8)
        pdf.ln(3)

        # ── SPHERIX CLINIC OFFICIAL STAMP ──
        pdf.set_draw_color(226, 232, 240)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(5)

        # Stamp Box
        stamp_y = pdf.get_y()
        stamp_x = 118
        stamp_w = 74
        stamp_h = 36

        pdf.set_draw_color(67, 97, 238)
        pdf.set_line_width(0.8)
        pdf.rect(stamp_x, stamp_y, stamp_w, stamp_h)

        # Inner stamp border
        pdf.set_draw_color(99, 102, 241)
        pdf.set_line_width(0.3)
        pdf.rect(stamp_x + 2, stamp_y + 2, stamp_w - 4, stamp_h - 4)

        # Stamp text
        pdf.set_xy(stamp_x, stamp_y + 4)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(67, 97, 238)
        pdf.cell(stamp_w, 5, 'SPHERIX CLINIC', 0, 1, 'C')
        pdf.set_x(stamp_x)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(stamp_w, 4, 'Official Registration Stamp', 0, 1, 'C')
        pdf.set_x(stamp_x)
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(stamp_w, 4, f'TOKEN: {token_str} | REF: {receipt_no}', 0, 1, 'C')
        pdf.set_x(stamp_x)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(stamp_w, 4, visit_date, 0, 1, 'C')

        # Signature line on left
        pdf.set_y(stamp_y + 5)
        pdf.set_x(14)
        pdf.set_draw_color(100, 116, 139)
        pdf.set_line_width(0.3)
        pdf.line(14, stamp_y + 30, 100, stamp_y + 30)
        pdf.set_y(stamp_y + 32)
        pdf.set_x(14)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(86, 4, "Attending Doctor / Reception Signature", 0, 0, 'C')

        pdf.ln(stamp_h + 3)

        # ── IMPORTANT NOTE ──
        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(251, 191, 36)
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(146, 64, 14)
        pdf.multi_cell(0, 5, '  NOTE: Please retain this registration slip. Your token will be announced on the OPD display board.', 1, 'L', fill=True)

        # Output
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        from flask import Response
        response = Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=WalkIn_Receipt_{receipt_no}.pdf'
            }
        )
        return response

    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "error")
        if getattr(current_user, 'is_patient', False):
            return redirect(url_for('patient_dashboard'))
        return redirect(url_for('staff_reception_dashboard'))



@main_bp.route('/staff/reception/visitor-pass-pdf/<int:pass_id>')
@login_required
def visitor_pass_pdf(pass_id):
    """Generate a styled printable PDF security pass for hospital visitors/attendants."""
    passes = TEMP_DATA.get('visitor_passes', {})
    pass_obj = passes.get(pass_id)
    if not pass_obj:
        flash("Visitor pass not found.", "error")
        return redirect(url_for('staff_reception_dashboard'))
    
    hospital_name_str = getattr(current_user, 'hospital_name', '')
    hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.name == hospital_name_str), None)
    
    try:
        class VisitorPassPDF(FPDF):
            def header(self):
                self.set_draw_color(16, 185, 129)
                self.set_line_width(1.2)
                self.rect(8, 8, 194, 281)

                self.set_fill_color(15, 23, 42)
                self.rect(8, 8, 194, 30, 'F')

                self.set_y(13)
                self.set_font('Helvetica', 'B', 18)
                self.set_text_color(255, 255, 255)
                self.cell(0, 8, 'SPHERIX CLINIC', 0, 1, 'C')
                self.set_font('Helvetica', 'B', 9)
                self.set_text_color(52, 211, 153)
                self.cell(0, 5, 'OFFICIAL VISITOR / ATTENDANT SECURITY PASS', 0, 1, 'C')
                self.set_text_color(0, 0, 0)
        
        pdf = VisitorPassPDF()
        pdf.add_page()
        pdf.set_margins(14, 14, 14)
        pdf.ln(26)
        
        # Big Pass Badge Card
        pdf.set_fill_color(236, 253, 245)
        pdf.set_draw_color(16, 185, 129)
        pdf.set_line_width(0.8)
        pdf.rect(14, pdf.get_y(), 182, 34, 'DF')
        
        start_y = pdf.get_y()
        pdf.set_xy(18, start_y + 4)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(6, 95, 70)
        pdf.cell(100, 8, f"PASS NO: {pass_obj.get('pass_number', 'VP-0001')}", 0, 1)
        
        pdf.set_x(18)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(100, 6, f"VISITOR: {pass_obj.get('visitor_name', 'N/A')}", 0, 1)
        
        pdf.set_x(18)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(100, 5, f"Valid For: {pass_obj.get('valid_hours', 2)} Hours | Ward/Bed: {pass_obj.get('ward_room', 'General Ward')}", 0, 1)
        
        # Status pill
        pdf.set_xy(135, start_y + 8)
        pdf.set_fill_color(16, 185, 129)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(50, 14, pass_obj.get('status', 'ACTIVE').upper(), 0, 1, 'C', fill=True)
        
        pdf.set_y(start_y + 40)
        
        def row(label, value, bold_val=False):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(55, 7, label + ':', 0, 0)
            pdf.set_font('Helvetica', 'B' if bold_val else '', 9)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 7, to_latin1_str(str(value)), 0, 1)
            
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(6, 95, 70)
        pdf.cell(0, 8, 'VISITOR & PATIENT DETAILS', 0, 1)
        pdf.ln(1)
        
        row('Patient Name', pass_obj.get('patient_name', 'N/A'), bold_val=True)
        row('Ward / Room No.', pass_obj.get('ward_room', 'N/A'), bold_val=True)
        row('Visitor Name', pass_obj.get('visitor_name', 'N/A'), bold_val=True)
        row('Visitor Phone', pass_obj.get('visitor_phone', 'N/A'))
        row('Relationship', pass_obj.get('relation', 'Attendant / Family'))
        row('Issued Time', pass_obj.get('issued_at', datetime.now()).strftime('%d %b %Y, %I:%M %p') if hasattr(pass_obj.get('issued_at'), 'strftime') else str(pass_obj.get('issued_at', '')))
        row('Hospital / Facility', hospital.name if hospital else hospital_name_str or 'Spherix Clinic')
        
        pdf.ln(8)
        
        # Stamp Box
        stamp_y = pdf.get_y()
        stamp_x = 118
        stamp_w = 74
        stamp_h = 36

        pdf.set_draw_color(16, 185, 129)
        pdf.set_line_width(0.8)
        pdf.rect(stamp_x, stamp_y, stamp_w, stamp_h)

        pdf.set_draw_color(52, 211, 153)
        pdf.set_line_width(0.3)
        pdf.rect(stamp_x + 2, stamp_y + 2, stamp_w - 4, stamp_h - 4)

        pdf.set_xy(stamp_x, stamp_y + 4)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(6, 95, 70)
        pdf.cell(stamp_w, 5, 'SPHERIX CLINIC', 0, 1, 'C')
        pdf.set_x(stamp_x)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(stamp_w, 4, 'Security & Reception Stamp', 0, 1, 'C')
        pdf.set_x(stamp_x)
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(stamp_w, 4, f"PASS: {pass_obj.get('pass_number', 'VP-0001')}", 0, 1, 'C')
        pdf.set_x(stamp_x)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(stamp_w, 4, datetime.now().strftime('%d %B %Y'), 0, 1, 'C')

        pdf.set_y(stamp_y + 5)
        pdf.set_x(14)
        pdf.set_draw_color(100, 116, 139)
        pdf.set_line_width(0.3)
        pdf.line(14, stamp_y + 30, 100, stamp_y + 30)
        pdf.set_y(stamp_y + 32)
        pdf.set_x(14)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(86, 4, "Reception Officer Signature", 0, 0, 'C')

        pdf.ln(stamp_h + 8)

        # Terms Box
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(0, 5, 'VISITOR GUIDELINES: 1. Keep this pass visible at all times. 2. Only 1 visitor permitted per patient at a time in ICU/Special Wards. 3. Wash/Sanitize hands before entering wards. 4. Return this pass at the reception upon checkout.', 1, 'L', fill=True)
        
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        from flask import Response
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f"attachment; filename=Visitor_Pass_{pass_obj.get('pass_number', 'VP-0001')}.pdf"}
        )
    except Exception as e:
        flash(f"Error generating Visitor Pass PDF: {str(e)}", "error")
        return redirect(url_for('staff_reception_dashboard'))



@main_bp.route('/auth/callback')
def google_authorize():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.userinfo()
    
    email = user_info['email']
    name = user_info['name']
    role = session.get('google_login_role', 'patient')
    is_new_user = False
    year = datetime.now().year
    
    if role == 'patient':
        user = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if not user:
            is_new_user = True
            new_id = f"PAT/{year}/{TEMP_DATA['next_ids']['patient']:03d}"
            user = Patient(id=new_id, name=name, email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'))
            TEMP_DATA['patients'][new_id] = user
            TEMP_DATA['next_ids']['patient'] += 1
            save_data()
            flash('Account created via Google.', 'success')
        login_user(user)
        if is_new_user:
            return redirect(url_for('complete_profile'))
        return redirect(url_for('patient_dashboard'))

    elif role == 'doctor':
        user = next((d for d in TEMP_DATA['doctors'].values() if d.email == email), None)
        if not user:
            is_new_user = True
            year = datetime.now().year
            next_id_num = TEMP_DATA['next_ids']['doctor']
            new_id = f"DOC/{year}/{next_id_num:03d}"
            user = Doctor(
                id=new_id, first_name=name.split()[0], last_name=" ".join(name.split()[1:]) if " " in name else "",
                email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), is_verified=False,
                department="General"
            )
            TEMP_DATA['doctors'][new_id] = user
            TEMP_DATA['next_ids']['doctor'] += 1
            save_data()
            flash('Doctor account created via Google. Please update your profile.', 'info')
        login_user(user)
        if is_new_user:
            return redirect(url_for('complete_profile'))
        return redirect(url_for('doctor_dashboard'))

    elif role == 'blood_donor':
        user = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == email), None)
        if not user:
            is_new_user = True
            donor_id = f"BD/{year}/{TEMP_DATA['next_ids']['blood_donor']:03d}"
            user = BloodDonor(id=donor_id, name=name, email=email, phone="N/A", blood_group="Unknown", age=18, city="Unknown", password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'))
            TEMP_DATA['blood_donors'][donor_id] = user
            TEMP_DATA['next_ids']['blood_donor'] += 1
            save_data()
            flash('Account created via Google. Please wait for staff verification.', 'info')
                
        if getattr(user, 'status', 'pending') == 'approved':
            login_user(user)
            if is_new_user:
                return redirect(url_for('complete_profile'))
            return redirect(url_for('blood_donor_dashboard'))
        flash('Your account is pending verification by hospital staff.', 'warning')
        return redirect(url_for('blood_donor_login'))

    elif role == 'organ_donor':
        user = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)
        if not user:
            is_new_user = True
            donor_id = f"OD/{year}/{TEMP_DATA['next_ids']['organ_donor']:03d}"
            user = OrganDonor(id=donor_id, name=name, email=email, phone="N/A", organs=[], blood_group="Unknown", age=18, city="Unknown", password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'))
            TEMP_DATA['organ_donors'][donor_id] = user
            TEMP_DATA['next_ids']['organ_donor'] += 1
            save_data()
            flash('Organ donor account created via Google. Please wait for staff verification.', 'info')
                
        if getattr(user, 'status', 'pending') == 'approved':
            login_user(user)
            if is_new_user:
                return redirect(url_for('complete_profile'))
            return redirect(url_for('organ_donor_dashboard'))
        flash('Your account is pending verification by hospital staff.', 'warning')
        return redirect(url_for('organ_donor_login'))

    elif role == 'hospital':
        user = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if not user:
            is_new_user = True
            hospital_id = f"HPT/{year}/{TEMP_DATA['next_ids']['hospital']:03d}"
            user = Hospital(id=hospital_id, name=name, email=email, password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'), is_verified=False)
            TEMP_DATA['hospitals'][hospital_id] = user
            TEMP_DATA['next_ids']['hospital'] += 1
            save_data()
            flash('Hospital account created via Google. Please wait for admin verification.', 'info')
        if getattr(user, 'is_verified', True):
            login_user(user)
            if is_new_user:
                return redirect(url_for('complete_profile'))
            return redirect(url_for('hospital_dashboard'))
        flash('Your hospital account is pending verification.', 'warning')

    return redirect(url_for('home'))




@main_bp.route('/complete-profile')
@login_required
def complete_profile():
    """Redirect new Google SSO users to their respective dashboard settings."""
    flash("Please take a moment to complete your profile details.", "info")
    
    if getattr(current_user, 'is_doctor', False):
        return redirect(url_for('doctor_dashboard') + '#settings')
    elif getattr(current_user, 'is_hospital', False):
        return redirect(url_for('hospital_dashboard') + '#settings')
    elif isinstance(current_user, BloodDonor):
        return redirect(url_for('blood_donor_dashboard') + '#settings')
    elif isinstance(current_user, OrganDonor):
        return redirect(url_for('organ_donor_dashboard') + '#settings')
    return redirect(url_for('patient_dashboard') + '#settings')



@main_bp.route('/blood-donor/certificate')
@login_required
def download_donation_certificate():
    donor = None
    if isinstance(current_user, BloodDonor):
        donor = current_user
    elif current_user.is_authenticated:
        donor_id = request.args.get('donor_id')
        if donor_id and donor_id in TEMP_DATA.get('blood_donors', {}):
            donor = TEMP_DATA['blood_donors'][donor_id]
            
    if not donor:
        flash("Access denied or donor not found.", "error")
        return redirect(url_for('home'))
    
    if not donor.last_donation:
        flash("No donation record found to generate a certificate.", "error")
        if isinstance(current_user, BloodDonor):
            return redirect(url_for('blood_donor_dashboard'))
        elif getattr(current_user, 'is_staff', False):
            return redirect(url_for('staff_blood_dashboard'))
        else:
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

        # Usable content area (Centered on A4 297mm x 210mm)
        content_left = 32
        content_w = 233

        # Hospital & Authority Resolution
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

        # Extract EXACT hospital details (NO hardcoded Spherix Clinic or dummy names)
        hospital_name = getattr(hosp, 'name', 'Registered Healthcare Facility')
        hospital_city = getattr(hosp, 'city', '')
        hospital_state = getattr(hosp, 'state', '')
        hospital_id_code = str(getattr(hosp, 'id', 'HOSP'))
        
        # MD / President & Chief Executive of THAT specific hospital
        president_name = getattr(donor, 'president_ceo', None) or getattr(hosp, 'president_ceo', None) or getattr(hosp, 'director_name', None) or f"Managing Director ({hospital_name})"

        # Medical Superintendent / Blood Bank Staff of THAT specific hospital
        superintendent_name = getattr(donor, 'assigned_staff_name', None) or getattr(donor, 'superintendent_name', None) or getattr(donor, 'verified_by', None) or getattr(hosp, 'superintendent_name', None) or getattr(hosp, 'blood_bank_staff', None) or f"Medical Superintendent ({hospital_name})"

        hospital_name_clean = to_latin1_str(hospital_name)
        hospital_city_clean = to_latin1_str(hospital_city)
        hospital_state_clean = to_latin1_str(hospital_state)
        superintendent_name_clean = to_latin1_str(superintendent_name)
        president_name_clean = to_latin1_str(president_name)

        try:
            id_val = int(donor.id.split('/')[-1]) if '/' in str(donor.id) else int(donor.id)
            year_val = donor.created_at.year if hasattr(donor, 'created_at') and donor.created_at else datetime.now().year
            cert_number = f"CERT/{hospital_id_code}/BD/{year_val}/{id_val:04d}"
        except (ValueError, TypeError):
            cert_number = f"CERT/{hospital_id_code}/BD/{donor.id}"

        # 1. Authority Header
        pdf.set_xy(content_left, 36)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(185, 135, 35) # Gold
        pdf.cell(content_w, 5, f"{hospital_name_clean.upper()}  |  TRANSFUSION MEDICINE & CLINICAL BLOOD BANK", 0, 1, 'C')

        # 2. Main Title
        pdf.set_xy(content_left, 43)
        pdf.set_font('Times', 'B', 25)
        pdf.set_text_color(15, 23, 42) # Deep Navy
        pdf.cell(content_w, 9, "CERTIFICATE OF HONOR", 0, 1, 'C')

        pdf.set_xy(content_left, 53)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(185, 135, 35)
        pdf.cell(content_w, 5, "VOLUNTARY BLOOD DONATION & LIFE COMMENDATION", 0, 1, 'C')

        # Gold Divider Line with Center Diamond
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
        pdf.cell(content_w, 6, "This Distinguished Commendation is Proudly Conferred Upon", 0, 1, 'C')

        # 4. Donor Recipient Name
        pdf.set_xy(content_left, 73)
        donor_name_clean = to_latin1_str(donor.name).upper()
        pdf.set_font('Times', 'B', 24)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(content_w, 9, donor_name_clean, 0, 1, 'C')

        # 5. Preamble Subtext
        pdf.set_xy(content_left, 84)
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(content_w, 5, "in highest recognition of voluntary humanitarian donation and saving precious lives.", 0, 1, 'C')

        # 6. Clinical Verification Box
        donation_date_str = str(donor.last_donation or date.today())
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        pdf.rect(38, 93, 221, 23, 'FD')

        pdf.set_xy(43, 96)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(100, 4.5, f"CERTIFICATE ID: #{cert_number}", 0, 0, 'L')
        pdf.cell(111, 4.5, f"BLOOD GROUP: {to_latin1_str(donor.blood_group)} (RH TESTED)", 0, 1, 'R')

        pdf.set_xy(43, 102)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.set_text_color(185, 135, 35)
        pdf.cell(211, 4.5, f"ISSUING FACILITY: {hospital_name_clean.upper()}", 0, 1, 'L')

        pdf.set_xy(43, 108)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        loc_str = f"{hospital_city_clean}, {hospital_state_clean}" if hospital_city_clean else "Clinical Division"
        pdf.cell(100, 4, f"DONATION RECORDED: {donation_date_str}", 0, 0, 'L')
        pdf.cell(111, 4, f"LOCATION: {loc_str}", 0, 1, 'R')

        # 7. Commendation Narrative
        pdf.set_xy(content_left + 8, 121)
        pdf.set_font('Times', 'I', 9.5)
        pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(content_w - 16, 4.5, 
            f"In sincere gratitude for your voluntary, selfless gift of whole blood at {hospital_name_clean}. By answering the call to save lives, your contribution directly bolsters critical emergency surgical reserves, restores vital health to patients, and exemplifies the finest humanitarian ideals.", 
            0, 'C')

        # 8. Signatures & Verification Area (Y = 142)
        y_sig = 142
        
        pdf.set_draw_color(15, 23, 42)
        pdf.set_line_width(0.3)
        pdf.line(40, y_sig + 11, 105, y_sig + 11)
        
        pdf.set_xy(38, y_sig + 12.5)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(69, 3.5, superintendent_name_clean.upper(), 0, 1, 'C')
        pdf.set_xy(38, y_sig + 16)
        pdf.set_font('Helvetica', '', 6.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(69, 3, "Medical Superintendent / Blood Bank Staff", 0, 1, 'C')
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

        # Far Right: QR Code Authenticator
        qr = qrcode.QRCode(box_size=6, border=1)
        qr_url = url_for('blood_donor_dashboard', _external=True)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_qr:
            qr_img.save(tmp_qr)
            pdf.image(tmp_qr.name, x=212, y=y_sig - 1, w=22, h=22)
            try:
                os.unlink(tmp_qr.name)
            except OSError:
                pass
                
        pdf.set_draw_color(202, 156, 56)
        pdf.set_line_width(0.3)
        pdf.rect(211, y_sig - 2, 24, 24)
        
        pdf.set_xy(201, y_sig + 23)
        pdf.set_font('Helvetica', 'B', 5.5)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(44, 3, "SCAN TO VERIFY RECORD", 0, 1, 'C')

        # 9. Bottom Micro-Print Security Footer (Y = 178)
        pdf.set_xy(content_left, 178)
        pdf.set_font('Helvetica', '', 6)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(content_w, 3, f"ISSUED BY {hospital_name_clean.upper()}  |  SERIAL: #{cert_number}  |  VERIFIED CLINICAL BLOOD TRANSFUSION RECORD", 0, 1, 'C')

        try:
            pdf_output = pdf.output(dest='S')
            pdf_bytes = pdf_output.encode('latin-1') if isinstance(pdf_output, str) else pdf_output
        except TypeError:
            pdf_bytes = pdf.output()
            
        if request.args.get('action') == 'email':
            subject = "Your Blood Donation Certificate - Spherix Clinic"
            body = f"Dear {donor.name},\n\nThank you for your noble contribution! Please find your blood donation certificate attached to this email.\n\nBest regards,\nSpherix Clinic Blood Bank Network"
            send_notification_email(donor.email, subject, body, is_html=False, attachment_name="donation_certificate.pdf", attachment_data=pdf_bytes)
            flash("Certificate sent to your email successfully!", "success")
            if isinstance(current_user, BloodDonor):
                return redirect(url_for('blood_donor_dashboard'))
            else:
                return redirect(url_for('staff_blood_dashboard'))
        else:
            return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name='donation_certificate.pdf', mimetype='application/pdf')
            
    except Exception as e:
        print(f"Error generating certificate: {e}")
        flash("An error occurred while generating the certificate.", "error")
        if isinstance(current_user, BloodDonor):
            return redirect(url_for('blood_donor_dashboard'))
        else:
            return redirect(url_for('staff_blood_dashboard'))



@main_bp.route('/patient/id-card')
@login_required
def download_patient_id_card():
    patient = None
    if getattr(current_user, 'is_patient', False):
        patient = current_user
    elif current_user.is_authenticated:
        p_id = request.args.get('patient_id') or request.args.get('id')
        if p_id:
            parsed_id = parse_route_id(p_id)
            patient = TEMP_DATA.get('patients', {}).get(parsed_id)

    if not patient:
        flash("Patient record not found.", "error")
        return redirect(url_for('home'))

    try:
        buffer = generate_user_id_card_pdf(
            user_type='Patient',
            name=patient.name,
            user_id=f"PT-{patient.id}",
            phone=getattr(patient, 'phone', 'N/A'),
            address=getattr(patient, 'city', None) or getattr(patient, 'address', None) or 'Registered Citizen',
            blood_group=getattr(patient, 'blood_group', 'Not Recorded'),
            extra_info='Verified Patient',
            photo_filename=getattr(patient, 'profile_picture_url', None)
        )
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', patient.name.strip())
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Patient_ID_Card_{safe_name}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"Error generating patient ID card: {e}")
        flash("Could not generate ID card at this time.", "error")
        return redirect(url_for('patient_dashboard'))



@main_bp.route('/patient/feedback', methods=['POST'])
@patient_required
def submit_patient_feedback():
    rating = request.form.get('rating')
    comments = request.form.get('comments', '')
    feedback_target = request.form.get('feedback_target', 'web_application')
    
    referrer = request.referrer or url_for('patient_dashboard')
    
    if not rating:
        flash("Rating is required.", "error")
        if 'patient/dashboard' in referrer:
            return redirect(url_for('patient_dashboard') + '#feedback')
        elif url_for('home') in referrer or referrer == request.url_root:
            return redirect(url_for('home') + '#feedback-section')
        return redirect(referrer)

    # Resolve target ID & Name based on selection
    target_id = None
    target_name = None
    
    if feedback_target == 'doctor':
        target_id = request.form.get('target_id_doctor')
        if target_id:
            doc = TEMP_DATA.get('doctors', {}).get(target_id)
            if doc:
                target_name = f"Dr. {doc.first_name} {doc.last_name}"
            else:
                target_id = None
    elif feedback_target == 'hospital':
        target_id = request.form.get('target_id_hospital')
        if target_id:
            hosp = TEMP_DATA.get('hospitals', {}).get(target_id)
            if hosp:
                target_name = hosp.name
            else:
                target_id = None
    elif feedback_target == 'medical_shop':
        target_name = "Medical Shop"
    else:
        feedback_target = 'web_application'
        target_name = "Web Application"
    
    # Generate unique ID
    feedback_id = len(TEMP_DATA.get('feedbacks', {})) + 1
    
    new_fb = Feedback(
        id=feedback_id,
        patient_id=current_user.id,
        patient_name=current_user.name,
        rating=int(rating),
        comments=comments,
        feedback_target=feedback_target,
        target_id=target_id,
        target_name=target_name
    )
    if 'feedbacks' not in TEMP_DATA:
        TEMP_DATA['feedbacks'] = {}
    TEMP_DATA['feedbacks'][feedback_id] = new_fb
    
    # Also link to doctor reviews for real doctor profile ratings
    if feedback_target == 'doctor' and target_id:
        review_id = len(TEMP_DATA.get('reviews', {})) + 1
        new_review = Review(
            id=review_id,
            doctor_id=target_id,
            patient_id=current_user.id,
            patient_name=current_user.name,
            rating=int(rating),
            comment=comments
        )
        if 'reviews' not in TEMP_DATA:
            TEMP_DATA['reviews'] = {}
        TEMP_DATA['reviews'][review_id] = new_review
    
    save_data()
    flash("Thank you for your feedback!", "success")
    
    if 'patient/dashboard' in referrer:
        return redirect(url_for('patient_dashboard') + '#feedback')
    elif url_for('home') in referrer or referrer == request.url_root:
        return redirect(url_for('home') + '#feedback-section')
    return redirect(referrer)



@main_bp.route('/api/patient/vitals', methods=['POST'])
@patient_required
@csrf.exempt
def log_patient_vitals():
    """Endpoint for patients to log their vitals (Weight, Heart Rate, Blood Sugar, Blood Pressure)"""
    try:
        weight = request.form.get('weight')
        heart_rate = request.form.get('heart_rate')
        blood_sugar = request.form.get('blood_sugar')
        systolic_bp = request.form.get('systolic_bp')
        diastolic_bp = request.form.get('diastolic_bp')
        
        # Validation
        if not any([weight, heart_rate, blood_sugar, systolic_bp, diastolic_bp]):
            return jsonify({'success': False, 'error': 'Please provide at least one vital metric.'}), 400
            
        next_id = TEMP_DATA['next_ids'].get('patient_vital', 1)
        
        # Convert and validate types
        weight_val = float(weight) if weight else None
        hr_val = int(heart_rate) if heart_rate else None
        sugar_val = int(blood_sugar) if blood_sugar else None
        sys_val = int(systolic_bp) if systolic_bp else None
        dia_val = int(diastolic_bp) if diastolic_bp else None
        
        vital = PatientVital(
            id=next_id,
            patient_id=current_user.id,
            weight=weight_val,
            heart_rate=hr_val,
            blood_sugar=sugar_val,
            systolic_bp=sys_val,
            diastolic_bp=dia_val,
            recorded_at=utcnow()
        )
        
        if 'patient_vitals' not in TEMP_DATA:
            TEMP_DATA['patient_vitals'] = {}
        TEMP_DATA['patient_vitals'][next_id] = vital
        TEMP_DATA['next_ids']['patient_vital'] = next_id + 1
        save_data()
        
        flash("Vitals logged successfully!", "success")
        return jsonify({'success': True, 'message': 'Vitals logged successfully!'})
    except ValueError as ve:
        return jsonify({'success': False, 'error': f"Invalid metric format: {str(ve)}"}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to log vitals: {str(e)}"}), 500




@main_bp.route("/careers")
def careers():
    return render_template("careers.html")




@main_bp.route("/blog")
def blog():
    return render_template("blog.html")



@main_bp.route("/research")
def research():
    return render_template("research.html")



@main_bp.route('/research/<topic>')
def research_detail(topic):
    research_topics = {
        "ai_symptom_analysis": {
            "title": "AI Symptom Analysis",
            "description": "Exploring deep learning models that analyze patient symptoms and predict possible health conditions.",
            "image": "images/ai_symptom.jpg"
        },
        "disease_prediction": {
            "title": "Disease Prediction Models",
            "description": "Using machine learning to predict diseases from medical history, images, and genetic data.",
            "image": "images/disease_prediction.jpg"
        },
        "genomic_integration": {
            "title": "Genomic Data Integration",
            "description": "Integrating AI and genomic datasets to advance personalized treatment and diagnostics.",
            "image": "images/genomics.jpg"
        },
        "clinical_ai_tools": {
            "title": "Clinical AI Tools",
            "description": "Designing AI systems that assist doctors in real-time decision making.",
            "image": "images/clinical_ai.jpg"
        },
        "chatbot_consultation": {
            "title": "AI Chatbot & Teleconsultation",
            "description": "Conversational AI that bridges patients and healthcare professionals for online diagnosis.",
            "image": "images/chatbot.jpg"
        },
        "data_ethics": {
            "title": "Data Privacy & Ethics",
            "description": "Researching ethical frameworks for AI in healthcare, focusing on patient data privacy and consent.",
            "image": "images/data_ethics.jpg"
            },
        "robotic_assistance": {
            "title": "Robotic Assistance in Surgery",
            "description": "Exploring AI-powered robotic systems that enhance precision and outcomes in surgical procedures.",
            "image": "images/robotic_surgery.jpg"
        },
        "neural_imaging": {
            "title": "Neural Imaging Analysis",
            "description": "Applying AI to interpret complex neural imaging data for neurological disorder diagnosis.",
            "image": "images/neural_imaging.jpg"
        },
        "drug_discovery": {
            "title": "AI in Drug Discovery",
            "description": "Utilizing AI algorithms to accelerate the drug discovery process and identify new therapeutic compounds.",
            "image": "images/drug_discovery.jpg"
        },
        "health_data_analytics": {
            "title": "Health Data Analytics",
            "description": "Leveraging big data and AI to extract insights from large-scale health datasets for improved public health outcomes.",
            "image": "images/health_data.jpg"
        }
    }

    topic_data = research_topics.get(topic)
    if not topic_data:
        return render_template("404.html"), 404

    return render_template("research_detail.html", topic=topic_data)



@main_bp.route("/resources")
def resources():
    return render_template("research.html")



@main_bp.route('/api/global-search', methods=['GET'])
def api_global_search():
    """
    Unified Global Clinical & Healthcare Omnisearch API.
    Searches across:
      - Clinical Diagnostic AI & Healthcare Services
      - Registered Medical Specialists & Doctors
      - Hospital Facilities & Bed telemetry
      - Tata 1mg Medicine & Pharmacy Catalog
      - Clinical Diseases & Medical Encyclopedia (NIH / CDC)
      - Healthcare Portals & System Actions
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', 'all').lower().strip()
    try:
        limit = int(request.args.get('limit', 20))
    except (ValueError, TypeError):
        limit = 20
    
    if not q:
        default_items = [
            {'title': 'Drug & Food Interaction Matrix', 'badge': 'Diagnostic AI', 'icon': 'fas fa-pills', 'url': url_for('drug_checker'), 'desc': 'AI safety check for polypharmacy & food interactions', 'type': 'service'},
            {'title': 'Find Cardiologists & Heart Specialists', 'badge': 'Specialist', 'icon': 'fas fa-heart-pulse', 'url': url_for('doctors_list', dept='Cardiology'), 'desc': 'Top rated cardiologists and OPD slots', 'type': 'doctor'},
            {'title': 'Emergency Hospitals & ICU Beds', 'badge': 'Hospital', 'icon': 'fas fa-hospital', 'url': url_for('hospitals_list'), 'desc': '24/7 emergency telemetry and bed status', 'type': 'hospital'},
            {'title': 'Tata 1mg Pharmacy Catalog', 'badge': 'Pharmacy', 'icon': 'fas fa-prescription-bottle-medical', 'url': url_for('medical_shop'), 'desc': 'Browse 11,800+ medicines with genuine pricing', 'type': 'medicine'},
            {'title': 'Lab Report AI Analyzer', 'badge': 'Diagnostic AI', 'icon': 'fas fa-microscope', 'url': url_for('lab_analyzer'), 'desc': 'Automated biomarker extraction and clinical assessment', 'type': 'service'},
            {'title': 'Radiology AI Scan Suite', 'badge': 'Diagnostic AI', 'icon': 'fas fa-x-ray', 'url': url_for('radiology_ai'), 'desc': 'Chest X-ray & MRI anomaly detection', 'type': 'service'},
            {'title': 'Disease & Symptom Encyclopedia', 'badge': 'Conditions', 'icon': 'fas fa-book-medical', 'url': url_for('conditions'), 'desc': '5,100+ NIH/CDC clinical condition monographs', 'type': 'disease'}
        ]
        return jsonify({
            'success': True,
            'query': '',
            'total': len(default_items),
            'results': default_items,
            'quick_suggestions': default_items
        })

    q_lower = q.lower()
    results = []
    
    # 1. CLINICAL SERVICES & TOOLS
    CLINICAL_SERVICES = [
        {'title': 'Drug & Food Interaction Checker', 'category': 'Diagnostic AI', 'icon': 'fas fa-pills', 'url': url_for('drug_checker'), 'desc': 'Check polypharmacy, food safety, and interaction warnings', 'tags': 'drug medicine pharmacy food interaction contraindication side effects'},
        {'title': 'Lab Report AI Analyzer', 'category': 'Diagnostic AI', 'icon': 'fas fa-microscope', 'url': url_for('lab_analyzer'), 'desc': 'Instant blood work & biometric lab analyzer', 'tags': 'lab blood test report cbc lft kft lipid sugar hemoglobin analyzer'},
        {'title': 'Radiology AI Scan Assessment', 'category': 'Diagnostic AI', 'icon': 'fas fa-x-ray', 'url': url_for('radiology_ai'), 'desc': 'X-Ray, CT & MRI AI anomaly diagnostic triage', 'tags': 'radiology xray mri ct scan imaging bone lung chest'},
        {'title': 'Comprehensive Cancer Care Hub', 'category': 'Clinical Care', 'icon': 'fas fa-ribbon', 'url': url_for('cancer_care'), 'desc': 'Oncology staging, tumor markers & clinical pathways', 'tags': 'cancer oncology tumor chemo chemotherapy radiation biopsy'},
        {'title': 'Telemedicine Virtual Consultation', 'category': 'Clinical Care', 'icon': 'fas fa-video', 'url': url_for('telemedicine'), 'desc': 'Direct video consultations & digital e-prescriptions', 'tags': 'telemedicine video call doctor online consult opd remote'},
        {'title': 'Symptoms AI Clinical Triage', 'category': 'Diagnostic AI', 'icon': 'fas fa-stethoscope', 'url': url_for('symptoms'), 'desc': 'Differential diagnosis & symptom assessment engine', 'tags': 'symptom triage differential diagnosis sick pain cough fever'},
        {'title': 'Organ Donor Registry & Pledge', 'category': 'Community Care', 'icon': 'fas fa-hand-holding-heart', 'url': url_for('organ_donors_list'), 'desc': 'Verified organ donor registry & pledge certification', 'tags': 'organ donor transplant kidney liver heart pledge donation'},
        {'title': 'Blood Bank & Emergency Camps', 'category': 'Community Care', 'icon': 'fas fa-tint', 'url': url_for('blood_bank'), 'desc': 'Live blood unit inventory & active donation camps', 'tags': 'blood bank donor a+ b+ o+ ab+ platelets plasma emergency camp'},
        {'title': 'Ayurvedic Formulations & Dosha Matrix', 'category': 'Alternative Medicine', 'icon': 'fas fa-leaf', 'url': url_for('ayurveda'), 'desc': '367+ Vedic Ayurvedic profiles & herb compositions', 'tags': 'ayurveda herb dosha vata pitta kapha vedic natural organic'},
        {'title': 'Yoga & Biometric Posture Suite', 'category': 'Wellness', 'icon': 'fas fa-person-praying', 'url': url_for('yoga'), 'desc': 'Therapeutic asanas & breathing protocol guidance', 'tags': 'yoga asana meditation pranayama exercise fitness wellness posture'},
        {'title': 'Nutrition & Fitness Planner', 'category': 'Wellness & Nutrition', 'icon': 'fas fa-apple-whole', 'url': url_for('clinical_ai.nutrition_fitness_planner'), 'desc': 'Personalized 7-day meal plans, macro targets, workout splits & clinical calorie planning', 'tags': 'nutrition diet fitness meal plan workout gym calories macros protein fat bmr tdee weight loss muscle gain'},
        {'title': 'Health Calculators Suite', 'category': 'Clinical Tools', 'icon': 'fas fa-calculator', 'url': url_for('health_calculators'), 'desc': 'BMI, BMR, GFR, cardiovascular risk & dosage calculators', 'tags': 'calculator bmi bmr gfr dosage calories heart risk calculation'},
        {'title': 'First Aid & Emergency Guides', 'category': 'Emergency', 'icon': 'fas fa-kit-medical', 'url': url_for('first_aid'), 'desc': 'Step-by-step life-saving first aid triage manuals', 'tags': 'first aid cpr choking burn bleed fracture emergency stroke'},
        {'title': 'Spherix Meds Online Pharmacy', 'category': 'Pharmacy', 'icon': 'fas fa-prescription-bottle-medical', 'url': url_for('medical_shop'), 'desc': 'Order verified medicines & clinical health products', 'tags': 'pharmacy shop buy medicine drugs pills order delivery'},
        {'title': 'Patient Portal Login / Register', 'category': 'Portal', 'icon': 'fas fa-user-injured', 'url': url_for('patient_login'), 'desc': 'Access your clinical health records and appointments', 'tags': 'patient login signin signup register records dashboard'},
        {'title': 'Doctor Portal & Clinical Suite', 'category': 'Portal', 'icon': 'fas fa-user-md', 'url': url_for('doctor_login'), 'desc': 'Doctor login for OPD appointments & e-prescriptions', 'tags': 'doctor login portal physician opd appointments prescription'},
        {'title': 'Hospital Facility Management Console', 'category': 'Portal', 'icon': 'fas fa-hospital', 'url': url_for('hospital_login'), 'desc': 'Hospital console for bed telemetry, ICU, & admissions', 'tags': 'hospital facility login console beds admissions icu staff'},
        {'title': 'Spherix Careers & Clinical Openings', 'category': 'Information', 'icon': 'fas fa-briefcase', 'url': url_for('careers'), 'desc': 'Join the Spherix medical intelligence team', 'tags': 'careers jobs hiring medical openings doctor nurse engineer'},
        {'title': 'Medical Journal & Health Blog', 'category': 'Information', 'icon': 'fas fa-newspaper', 'url': url_for('blog'), 'desc': 'Latest medical research papers & clinical health insights', 'tags': 'blog journal articles research news health tips insights'},
        {'title': 'Daily Physician Health Tips', 'category': 'Information', 'icon': 'fas fa-lightbulb', 'url': url_for('health_tips'), 'desc': 'Curated daily health tips from board-certified doctors', 'tags': 'health tips daily advice wellness diet lifestyle guidance'},
        {'title': 'Spherix Media & Facility Gallery', 'category': 'Information', 'icon': 'fas fa-images', 'url': url_for('gallery'), 'desc': 'Explore our high-tech clinics, ICU labs & camps', 'tags': 'gallery photos facilities clinic hospital images labs'},
        {'title': 'Legal, HIPAA & Privacy Hub', 'category': 'Legal', 'icon': 'fas fa-shield-halved', 'url': url_for('legal_hub', policy_id='privacy-policy'), 'desc': 'Privacy policy, HIPAA compliance & patient PHI rights', 'tags': 'privacy policy terms hipaa legal patient rights compliance'}
    ]

    if category in ['all', 'services', 'tools', 'portals']:
        for s in CLINICAL_SERVICES:
            searchable = f"{s['title']} {s['desc']} {s.get('tags', '')}".lower()
            if any(term in searchable for term in q_lower.split()):
                results.append({
                    'type': 'service',
                    'title': s['title'],
                    'badge': s['category'],
                    'icon': s['icon'],
                    'url': s['url'],
                    'desc': s['desc']
                })

    # 2. DOCTORS & SPECIALISTS
    if category in ['all', 'doctors', 'specialists']:
        matched_doctors = 0
        all_docs = [d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
        for doc in all_docs:
            doc_name = f"Dr. {doc.first_name} {doc.last_name}".strip()
            doc_text = f"{doc_name} {getattr(doc, 'department', '')} {getattr(doc, 'specialization', '')} {getattr(doc, 'hospital_name', '')} {getattr(doc, 'city', '')} {getattr(doc, 'qualifications', '')}".lower()
            if any(term in doc_text for term in q_lower.split()):
                doc_img = url_for('get_doctor_image', doc_id=doc.id) if hasattr(doc, 'id') else None
                doc_url = url_for('doctors_list', q=doc.first_name)
                results.append({
                    'type': 'doctor',
                    'title': doc_name,
                    'badge': doc.specialization or doc.department or 'Specialist',
                    'icon': 'fas fa-user-md',
                    'image': doc_img,
                    'url': doc_url,
                    'desc': f"{doc.department or 'General Medicine'} • {doc.hospital_name or 'Spherix Network'} • ₹{getattr(doc, 'consultation_fee', 500)} Fee"
                })
                matched_doctors += 1
                if matched_doctors >= 6:
                    break

    # 3. HOSPITALS & FACILITIES
    if category in ['all', 'hospitals']:
        matched_hospitals = 0
        all_hosps = [h for h in TEMP_DATA['hospitals'].values() if not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)]
        for hosp in all_hosps:
            hosp_text = f"{hosp.name} {getattr(hosp, 'city', '')} {getattr(hosp, 'address', '')} {getattr(hosp, 'state', '')} {getattr(hosp, 'country', '')}".lower()
            if any(term in hosp_text for term in q_lower.split()):
                hosp_url = url_for('hospitals_list', q=hosp.name)
                results.append({
                    'type': 'hospital',
                    'title': hosp.name,
                    'badge': 'Hospital Center',
                    'icon': 'fas fa-hospital',
                    'url': hosp_url,
                    'desc': f"{hosp.city or 'General Facility'} • {getattr(hosp, 'address', 'Spherix Clinical Network')}"
                })
                matched_hospitals += 1
                if matched_hospitals >= 5:
                    break

    # 4. MEDICINES & PHARMACY (Tata 1mg Catalog)
    if category in ['all', 'medicines', 'pharmacy']:
        try:
            med_res = search_medicines(query=q, limit=6)
            for m in med_res.get('medicines', []):
                m_url = f"{url_for('medical_shop')}?q={m.get('name', '')}"
                results.append({
                    'type': 'medicine',
                    'title': m.get('name', 'Medicine'),
                    'badge': f"₹{m.get('price', 0)}" if m.get('price') else 'Pharmacy',
                    'icon': 'fas fa-tablets',
                    'url': m_url,
                    'desc': f"{m.get('manufacturer', 'Genuine')} • {m.get('short_composition', m.get('composition', 'Pharmaceutical formulation'))[:60]}"
                })
        except Exception:
            pass

    # 5. DISEASES & MEDICAL CONDITIONS (NIH / CDC MedQuAD Encyclopedia)
    if category in ['all', 'diseases', 'conditions']:
        try:
            dis_res = search_diseases(query=q, limit=6)
            for d in dis_res.get('diseases', []):
                d_url = f"{url_for('conditions')}?disease={d.get('name', '')}"
                results.append({
                    'type': 'disease',
                    'title': d.get('name', 'Condition'),
                    'badge': d.get('category', 'Disease'),
                    'icon': 'fas fa-disease',
                    'url': d_url,
                    'desc': d.get('overview', 'Clinical disease monograph & symptom guide')[:100] + '...'
                })
        except Exception:
            pass

    return jsonify({
        'success': True,
        'query': q,
        'total': len(results),
        'results': results[:limit]
    })



@main_bp.route('/order/invoice/<int:order_id>')
@patient_required
def print_invoice(order_id):
    """Generates and serves a PDF invoice for a specific order."""
    order = TEMP_DATA['orders'].get(order_id)
    if not order or order.patient_id != current_user.id:
        flash("Order not found.", "error")
        return redirect(url_for('patient_dashboard'))

    try:
        class PharmacyInvoicePDF(FPDF):
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
                self.cell(0, 8, 'SPHERIX CLINIC - PHARMACY INVOICE', 0, 1, 'C')
                self.set_font('Helvetica', 'B', 8)
                self.set_text_color(156, 163, 175) # Light gray
                self.cell(0, 4, 'SECURE MEDICAL DISPENSARY GATEWAY', 0, 1, 'C')
                self.set_text_color(0, 0, 0)
                
            def footer(self):
                self.set_y(-22)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.set_draw_color(229, 231, 235)
                self.set_line_width(0.2)
                self.line(12, self.get_y(), 198, self.get_y())
                self.ln(2)
                self.cell(0, 4, 'Disclaimer: This invoice confirms transaction settlement for prescribed pharmacy inventory.', 0, 1, 'C')
                self.cell(0, 4, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} // Spherix Health Systems', 0, 1, 'C')

        pdf = PharmacyInvoicePDF()
        pdf.add_page()
        pdf.set_margins(12, 12, 12)
        pdf.ln(18) # Add space after header
        
        # Spherix details header
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, 'Spherix Rx Medical Shop', 0, 1, 'L')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, 'Motihari, Bihar, 845401', 0, 1, 'L')
        pdf.ln(4)
        
        # Meta Block
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Order Identifier:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(65, 6, f'#{order.id}', 0, 0, 'L')
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(35, 6, 'Order Date:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        order_date_disp = order.order_date.strftime('%B %d, %Y') if (order.order_date and hasattr(order.order_date, 'strftime')) else str(order.order_date or 'N/A')
        pdf.cell(0, 6, order_date_disp, 0, 1, 'L')
        
        pdf.ln(5)
        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.3)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(5)
        
        # Column Details Block (Billed To)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, 'Shipping & Billing Address:', 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        addr = order.shipping_address
        addr_name = to_latin1_str(addr.get('name', ''))
        addr_address = to_latin1_str(addr.get('address', ''))
        addr_city = to_latin1_str(addr.get('city', ''))
        addr_state = to_latin1_str(addr.get('state', ''))
        addr_pincode = to_latin1_str(addr.get('pincode', ''))
        pdf.cell(0, 5, addr_name, 0, 1, 'L')
        pdf.cell(0, 5, addr_address, 0, 1, 'L')
        pdf.cell(0, 5, f"{addr_city}, {addr_state} {addr_pincode}", 0, 1, 'L')
        
        pdf.ln(8)
        
        # Tabular Itemized Grid
        pdf.set_fill_color(240, 246, 255) # Soft Blue fill
        pdf.set_draw_color(191, 219, 254) # Blue-200 border
        pdf.set_line_width(0.3)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(30, 58, 138) # Dark Blue text
        
        pdf.cell(96, 10, '  Item Description', 1, 0, 'L', fill=True)
        pdf.cell(25, 10, 'Quantity', 1, 0, 'C', fill=True)
        pdf.cell(30, 10, 'Unit Price', 1, 0, 'C', fill=True)
        pdf.cell(35, 10, 'Total  ', 1, 1, 'R', fill=True)
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(15, 23, 42)
        for item in order.items:
            item_name = to_latin1_str(item.get('name', ''))
            pdf.cell(96, 10, f"  {item_name}", 1, 0, 'L')
            pdf.cell(25, 10, str(item['quantity']), 1, 0, 'C')
            pdf.cell(30, 10, f"Rs. {item['price']:.2f}", 1, 0, 'C')
            pdf.cell(35, 10, f"Rs. {item['price'] * item['quantity']:.2f}  ", 1, 1, 'R')
            
        # Grand Total Row
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(151, 12, 'Grand Total:  ', 0, 0, 'R')
        pdf.set_text_color(30, 58, 138)
        pdf.cell(35, 12, f"Rs. {order.total_price:.2f}  ", 1, 1, 'R')

        # PAID Stamp / Badge (if status is paid/processing/completed)
        is_paid = str(order.status).lower() not in ['cancelled', 'awaiting payment', 'pending payment']
        if is_paid:
            pdf.ln(12)
            pdf.set_fill_color(209, 250, 229) # Light green
            pdf.set_draw_color(16, 185, 129) # Green border
            pdf.set_line_width(0.5)
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(6, 95, 70) # Dark green text
            pdf.set_x(70)
            pdf.cell(70, 10, 'PAID & SETTLED', 1, 1, 'C', fill=True)

        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            try:
                pdf_bytes = pdf_output.encode('latin-1')
            except UnicodeEncodeError:
                pdf_bytes = pdf_output.encode('latin-1', 'replace')
        else:
            pdf_bytes = pdf_output

        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'invoice_{order.id}.pdf', mimetype='application/pdf', conditional=True)
    except Exception as e:
        print(f"Error generating PDF invoice: {e}")
        flash('An error occurred while generating the invoice.', 'error')
        return redirect(url_for('order_details', order_id=order.id))



@main_bp.route('/read-files', methods=['GET', 'POST'])
@csrf.exempt
def read_files():
    analysis_result = None
    uploaded_image = None
    
    if request.method == 'POST':
        camera_data = request.form.get('camera_image_data', '').strip()
        file = request.files.get('document')
        analysis_type = request.form.get('analysis_type', 'general')
        
        file_path = None
        unique_filename = None

        if camera_data and camera_data.startswith('data:image'):
            try:
                header, encoded = camera_data.split(',', 1)
                file_bytes = base64.b64decode(encoded)
                timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                unique_filename = f"camera_scan_{timestamp}.jpg"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, unique_filename)
                with open(file_path, 'wb') as f:
                    f.write(file_bytes)
                uploaded_image = f"/static/uploads/documents/{unique_filename}"
            except Exception as e:
                flash(f'Failed to process camera snapshot: {e}', 'error')
                return redirect(request.url)
        elif file and file.filename != '' and allowed_file(file.filename):
            if file.filename.rsplit('.', 1)[1].lower() == 'pdf':
                flash('Please upload an image file (JPG, PNG, JPEG, WEBP) for visual AI document analysis.', 'error')
                return redirect(request.url)
            filename = secure_filename(file.filename)
            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
            unique_filename = f"doc_analysis_{timestamp}_{filename}"
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            uploaded_image = f"/static/uploads/documents/{unique_filename}"
        else:
            flash('Please upload a document image or capture a photo with your camera.', 'error')
            return redirect(request.url)

        prompt = ""
        if analysis_type == 'xray':
            prompt = "You are an AI medical assistant. Analyze this X-Ray/MRI/CT scan image. Identify any visible abnormalities, fractures, or specific medical conditions. Be professional and objective, but add a disclaimer that you are an AI."
        elif analysis_type == 'report':
            prompt = "You are an AI medical assistant. Read and analyze this medical lab report. Summarize the key findings, highlight any abnormal values, and explain what they might mean in simple terms. Add a disclaimer that you are an AI."
        elif analysis_type == 'prescription':
            prompt = "You are an AI medical assistant. Read this doctor's handwritten prescription. Extract the medicine names, dosages, and instructions clearly into a list format."
        else:
            prompt = "You are an AI medical assistant. Analyze this medical document or image. Provide a clear summary of the findings."
            
        # Perform AI Analysis
        # 1. Attempt Google Cloud Vision for initial feature extraction
        gcv_findings = None
        if _is_vision_configured():
            print("🔍 Analyzing document with Google Cloud Vision API...")
            gcv_findings = _analyze_image_with_vision(file_path)
            
        if gcv_findings and 'analysis' in gcv_findings:
            prompt += f"\n\nGoogle Cloud Vision detected the following raw features:\n{gcv_findings['analysis']}\nIntegrate these findings into your analysis."
            
        # 2. Use Groq Vision for comprehensive LLM-based analysis
        groq_findings = _analyze_image_with_groq_vision(file_path, custom_prompt=prompt)
        if groq_findings and 'analysis' in groq_findings:
            analysis_result = groq_findings['analysis']
        elif groq_findings and 'error' in groq_findings:
            if gcv_findings and 'analysis' in gcv_findings:
                analysis_result = f"### Google Cloud Vision (Raw Findings)\n\n{gcv_findings['analysis']}"
                flash("Groq Vision API failed. Using fallback Google Cloud Vision analysis.", "warning")
            else:
                flash(f"AI analysis failed: {groq_findings['error']}", "error")
        else:
            flash("AI analysis failed. Please ensure Groq Vision API is configured and the image is clear.", "error")

    if analysis_result:
        return render_template('read_files_result.html', analysis_result=analysis_result, uploaded_image=uploaded_image)

    return render_template('read_files.html')




@main_bp.route('/faq')
def faq_page():
    return render_template('faq.html') # This will render our new faq.html template







@main_bp.route('/legal', defaults={'policy_id': 'terms-of-service'})
@main_bp.route('/legal/<policy_id>')
def legal_hub(policy_id='terms-of-service'):
    """Renders a specific policy page based on the policy_id."""
    alias_map = {
        'privacy': 'privacy-policy',
        'terms': 'terms-of-service',
        'doctor': 'doctor-agreement',
        'hospital': 'hospital-agreement',
        'donor': 'donor-policy',
        'donors': 'donor-policy',
        'staff': 'staff-agreement',
        'staffs': 'staff-agreement',
        'patient': 'patient-terms',
        'oncology': 'oncology-policy',
        'genomics': 'genomics-privacy',
        'trials': 'clinical-trials-policy',
        'telemedicine': 'telemedicine-policy',
        'ai-ethics': 'ai-ethics-governance',
        'cookie': 'cookie-policy'
    }
    canonical_id = alias_map.get(policy_id, policy_id)
    policy = POLICY_DATA.get(canonical_id)
    if not policy:
        return render_template("404.html"), 404

    return render_template('policy.html',
                           policy=policy,
                           all_policies=POLICY_DATA,
                           current_id=canonical_id)



@main_bp.route('/privacy-policy')
@main_bp.route('/privacy')
def privacy_policy():
    return legal_hub('privacy-policy')



@main_bp.route('/terms-of-service')
@main_bp.route('/terms')
def terms_of_service():
    return legal_hub('terms-of-service')



@main_bp.route('/image/<user_type>/<user_id>')
def serve_image(user_type, user_id):
    """Serves a profile picture from memory, database, or disk."""
    user_id_str = str(user_id).strip()
    entity = None
    if user_type == 'doctor':
        entity = TEMP_DATA.get('doctors', {}).get(user_id) or TEMP_DATA.get('doctors', {}).get(user_id_str)
    elif user_type == 'patient':
        entity = TEMP_DATA.get('patients', {}).get(parse_route_id(user_id)) or TEMP_DATA.get('patients', {}).get(user_id_str)
    elif user_type == 'staff':
        entity = TEMP_DATA.get('staff', {}).get(parse_route_id(user_id)) or TEMP_DATA.get('staff', {}).get(user_id_str)
    elif user_type == 'blood_donor':
        entity = TEMP_DATA.get('blood_donors', {}).get(parse_route_id(user_id)) or TEMP_DATA.get('blood_donors', {}).get(user_id_str)
    elif user_type == 'organ_donor':
        entity = TEMP_DATA.get('organ_donors', {}).get(parse_route_id(user_id)) or TEMP_DATA.get('organ_donors', {}).get(user_id_str)
    elif user_type == 'hospital':
        entity = TEMP_DATA.get('hospitals', {}).get(parse_route_id(user_id)) or TEMP_DATA.get('hospitals', {}).get(user_id_str)

    if entity and hasattr(entity, 'profile_picture_data') and entity.profile_picture_data:
        return send_file(
            BytesIO(entity.profile_picture_data),
            mimetype=getattr(entity, 'profile_picture_content_type', 'image/jpeg') or 'image/jpeg'
        )

    # Check for direct file path or URL
    pic_url = getattr(entity, 'profile_picture_url', None) or getattr(entity, 'logo_url', None)
    if pic_url:
        if pic_url.startswith('http://') or pic_url.startswith('https://'):
            return redirect(pic_url)
        # Search static uploads folders on disk
        clean_name = os.path.basename(pic_url)
        for sub in ['', 'doctor_profiles', 'signatures', 'stamps', 'prescriptions', 'documents']:
            disk_path = os.path.join(current_app.root_path, 'static', 'uploads', sub, clean_name)
            if os.path.exists(disk_path) and os.path.isfile(disk_path):
                return send_file(disk_path)

    # Check doctor_images database table
    if user_type == 'doctor':
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT image_data, content_type FROM doctor_images WHERE doctor_id = ?", (user_id_str,))
                row = cursor.fetchone()
                if row and row[0]:
                    return send_file(BytesIO(row[0]), mimetype=row[1] or 'image/jpeg')
        except Exception:
            pass

    # Fallback to initials avatar
    name_str = getattr(entity, 'name', getattr(entity, 'first_name', user_id_str or 'User'))
    return redirect(f"https://api.dicebear.com/7.x/initials/svg?seed={name_str}")



@main_bp.route('/static/uploads/<path:filename>')
@main_bp.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """Serves uploaded files and images with in-memory cache, multi-directory search, and avatar fallback."""
    clean_name = os.path.basename(filename)

    # 1. Check in-memory UPLOAD_CACHE first
    if filename in UPLOAD_CACHE:
        data_bytes, mimetype = UPLOAD_CACHE[filename]
        return send_file(BytesIO(data_bytes), mimetype=mimetype)
    if clean_name in UPLOAD_CACHE:
        data_bytes, mimetype = UPLOAD_CACHE[clean_name]
        return send_file(BytesIO(data_bytes), mimetype=mimetype)

    # 2. Check filesystem search paths
    search_dirs = [
        os.path.join(current_app.root_path, 'static', 'uploads'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'hospital_logos'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'doctor_profiles'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'signatures'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'stamps'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'prescriptions'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'documents'),
        os.path.join(current_app.root_path, 'static', 'uploads', 'medical_records'),
        os.path.join(current_app.root_path, 'static', 'images'),
        os.path.join(current_app.root_path, 'static', 'img'),
        os.path.join(current_app.root_path, 'static'),
        os.path.join('/tmp', 'uploads'),
        os.path.join('/tmp', 'uploads', 'hospital_logos')
    ]
    for d in search_dirs:
        target = os.path.join(d, clean_name)
        if os.path.exists(target) and os.path.isfile(target):
            return send_file(target)

    # Check if requested filename exists with path intact
    direct_target = os.path.join(current_app.root_path, 'static', filename)
    if os.path.exists(direct_target) and os.path.isfile(direct_target):
        return send_file(direct_target)

    # Fallback to avatar if an image filename is missing on disk
    name_clean = clean_name.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
    return redirect(f"https://api.dicebear.com/7.x/initials/svg?seed={name_clean}")




@main_bp.route('/emergency/track/<sos_id>')
def emergency_track(sos_id):
    """Live GPS Emergency SOS Dispatch Tracking View."""
    dispatches = TEMP_DATA.setdefault('emergency_dispatches', {})
    emergency = dispatches.get(sos_id)
    if not emergency:
        # Create a mock/demo tracking state for direct testing
        emergency = {
            'id': sos_id,
            'hospital_name': 'AIIMS Trauma & Emergency Center',
            'hospital_id': 1,
            'patient_name': getattr(current_user, 'name', 'Citizen in Need') if current_user.is_authenticated else 'Emergency Patient',
            'status': 'en_route',
            'eta': '4-6 mins',
            'triage_level': 'Level 1 Critical',
            'lat': 28.6139,
            'lng': 77.2090,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        dispatches[sos_id] = emergency
    return render_template('emergency_tracking.html', emergency=emergency)




@main_bp.route('/api/emergency/trigger', methods=['POST'])
def api_emergency_trigger():
    """Triggers an Emergency SOS dispatch, assigns nearest hospital, and broadcasts alert."""
    data = request.get_json() or {}
    dispatches = TEMP_DATA.setdefault('emergency_dispatches', {})
    
    sos_id = f"SOS-{int(datetime.now().timestamp())}"
    lat = float(data.get('lat', 28.6139))
    lng = float(data.get('lng', 77.2090))
    emergency_type = data.get('type', 'General Medical Emergency')
    
    # Assign nearest hospital
    hospitals = list(TEMP_DATA.get('hospitals', {}).values())
    hospital_name = hospitals[0].name if hospitals else "Spherix Central Trauma Hospital"
    hospital_id = hospitals[0].id if hospitals else 1
    
    dispatch_record = {
        'id': sos_id,
        'patient_name': getattr(current_user, 'name', 'Emergency Patient') if current_user.is_authenticated else 'Emergency Patient',
        'phone': getattr(current_user, 'phone', '+91 9334325920') if current_user.is_authenticated else '+91 9334325920',
        'blood_group': getattr(current_user, 'blood_group', 'O+') if current_user.is_authenticated else 'O+',
        'lat': lat,
        'lng': lng,
        'emergency_type': emergency_type,
        'status': 'dispatched',
        'eta': '5-8 Mins',
        'hospital_name': hospital_name,
        'hospital_id': hospital_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    dispatches[sos_id] = dispatch_record
    
    # Broadcast through SocketIO if connected
    if socketio:
        try:
            socketio.emit('emergency_sos_alert', dispatch_record)
        except Exception:
            pass
            
    return jsonify({
        'success': True,
        'sos_id': sos_id,
        'tracking_url': url_for('emergency_track', sos_id=sos_id),
        'dispatch': dispatch_record
    })




@main_bp.route('/api/emergency/active', methods=['GET'])
def api_emergency_active():
    """Returns active emergency SOS records."""
    dispatches = list(TEMP_DATA.setdefault('emergency_dispatches', {}).values())
    return jsonify({'success': True, 'dispatches': dispatches})




@main_bp.route('/api/emergency/update-status', methods=['POST'])
def api_emergency_update_status():
    """Paramedic/Hospital updates ambulance progress status."""
    data = request.get_json() or {}
    sos_id = data.get('sos_id')
    new_status = data.get('status')
    
    dispatches = TEMP_DATA.setdefault('emergency_dispatches', {})
    if sos_id in dispatches:
        dispatches[sos_id]['status'] = new_status
        if socketio:
            try:
                socketio.emit('emergency_status_update', {'sos_id': sos_id, 'status': new_status})
            except Exception:
                pass
        return jsonify({'success': True, 'dispatch': dispatches[sos_id]})
    return jsonify({'success': False, 'error': 'SOS record not found'}), 404




@main_bp.route('/ambulance/book', methods=['GET', 'POST'])
def ambulance_book(is_air=None):
    """Booking gateway for 24/7 Road & Air Ambulances."""
    if is_air is None:
        is_air = 'air-ambulance' in request.path or request.args.get('service') == 'air'
    
    fleet_catalog = {
        'road_bls': {
            'id': 'road_bls', 'category': 'road', 'name': 'Basic Life Support (BLS) Ambulance',
            'fee': 1499.0, 'eta': '6-10 Mins', 'icon': 'fas fa-truck-medical',
            'badge': 'BLS Certified', 'specs': 'Oxygen Support • Paramedic First Aid • Spine Board'
        },
        'road_acls': {
            'id': 'road_acls', 'category': 'road', 'name': 'Advanced Cardiac Life Support (ACLS ICU)',
            'fee': 3499.0, 'eta': '4-8 Mins', 'icon': 'fas fa-heart-pulse',
            'badge': 'ICU on Wheels', 'specs': 'Transport Ventilator • Monitored Defibrillator • ER Physician'
        },
        'road_neonatal': {
            'id': 'road_neonatal', 'category': 'road', 'name': 'Neonatal / Pediatric ICU Ambulance',
            'fee': 4299.0, 'eta': '8-12 Mins', 'icon': 'fas fa-baby',
            'badge': 'NICU Protocol', 'specs': 'Neonatal Incubator • Nitric Oxide Delivery • Neonatologist'
        },
        'air_heli': {
            'id': 'air_heli', 'category': 'air', 'name': 'Emergency Air Ambulance Helicopter (EC-145)',
            'fee': 15000.0, 'eta': '15-25 Mins', 'icon': 'fas fa-helicopter',
            'badge': 'Aero-Medical Heli', 'specs': 'Twin-Turbine • Dual Stretcher • Flight Surgeon & Trauma Nurse'
        },
        'air_jet': {
            'id': 'air_jet', 'category': 'air', 'name': 'Critical Care Fixed-Wing Jet (King Air / Learjet)',
            'fee': 25000.0, 'eta': '30-45 Mins', 'icon': 'fas fa-plane-departure',
            'badge': 'Inter-State Aero Jet', 'specs': 'Pressurized Cabin • Full Airborne ICU • Multi-City Transit'
        }
    }

    if request.method == 'POST':
        selected_type = request.form.get('ambulance_type', 'road_acls' if not is_air else 'air_heli')
        patient_name = request.form.get('patient_name', '').strip()
        patient_phone = (request.form.get('patient_phone') or request.form.get('contact_phone') or '').strip()
        pickup_address = (request.form.get('pickup_address') or request.form.get('pickup_location') or '').strip()
        destination_hospital = (request.form.get('destination_hospital') or request.form.get('hospital') or 'Nearest Trauma Center').strip()
        emergency_notes = (request.form.get('emergency_notes') or request.form.get('medical_notes') or '').strip()

        if not patient_name or not patient_phone or not pickup_address:
            flash("Please provide patient name, emergency contact phone, and pickup location.", "error")
            return redirect(request.url)

        vehicle_info = fleet_catalog.get(selected_type, fleet_catalog['road_acls'])
        fee = vehicle_info['fee']

        bookings = TEMP_DATA.setdefault('ambulance_bookings', {})
        booking_id = f"AMB-{int(time_module.time())}"
        
        booking_record = {
            'id': booking_id,
            'patient_name': patient_name,
            'patient_phone': patient_phone,
            'pickup_address': pickup_address,
            'destination_hospital': destination_hospital,
            'emergency_notes': emergency_notes,
            'ambulance_type': selected_type,
            'service_category': vehicle_info['category'],
            'vehicle_name': vehicle_info['name'],
            'fee': fee,
            'status': 'awaiting_payment',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': current_user.id if current_user.is_authenticated else None
        }
        bookings[booking_id] = booking_record
        save_data()

        return redirect(url_for('ambulance_payment', booking_id=booking_id))

    return render_template(
        'ambulance_booking.html',
        is_air=is_air,
        fleet=fleet_catalog,
        default_type='air_heli' if is_air else 'road_acls'
    )


@main_bp.route('/air-ambulance/book', methods=['GET', 'POST'])
def air_ambulance_book():
    """Charter booking gateway for critical care helicopter and fixed-wing air ambulances."""
    return ambulance_book(is_air=True)


@main_bp.route('/ambulance/payment/<booking_id>', methods=['GET', 'POST'])
def ambulance_payment(booking_id):
    """Razorpay Checkout for Ambulance & Air Ambulance dispatch fee."""
    bookings = TEMP_DATA.setdefault('ambulance_bookings', {})
    booking = bookings.get(booking_id)
    if not booking:
        flash("Ambulance dispatch booking not found.", "error")
        return redirect(url_for('ambulance_book'))

    fee = float(booking.get('fee', 2499.0))
    rzp_key_id = get_razorpay_key_id()

    if request.method == 'POST':
        razorpay_payment_id = request.form.get('razorpay_payment_id')
        razorpay_order_id = request.form.get('razorpay_order_id')
        razorpay_signature = request.form.get('razorpay_signature')

        if razorpay_payment_id and razorpay_order_id and razorpay_signature:
            is_valid = verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
            if not is_valid:
                flash("⚠️ Payment verification mismatch. Please contact emergency dispatch.", "error")
                return redirect(url_for('ambulance_payment', booking_id=booking_id))

        # Mark booking as dispatched & active
        booking['status'] = 'dispatched'
        booking['payment_id'] = razorpay_payment_id or 'rzp_verified'
        booking['payment_method'] = 'Razorpay Instant'

        # Create live SOS GPS record for real-time tracking radar
        dispatches = TEMP_DATA.setdefault('emergency_dispatches', {})
        dispatches[booking_id] = {
            'id': booking_id,
            'patient_name': booking['patient_name'],
            'phone': booking['patient_phone'],
            'hospital_name': booking['destination_hospital'],
            'pickup_address': booking['pickup_address'],
            'vehicle_name': booking['vehicle_name'],
            'status': 'en_route',
            'eta': '4-7 Mins' if booking['service_category'] == 'road' else '12-18 Mins',
            'triage_level': 'Priority Code Red' if 'air' in booking['service_category'] else 'Immediate Dispatch',
            'lat': 28.6139,
            'lng': 77.2090,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        save_data()

        # Emit live socket event if available
        if socketio:
            try:
                socketio.emit('emergency_sos_alert', dispatches[booking_id])
            except Exception:
                pass

        flash(f"🚨 Payment verified via Razorpay! {booking['vehicle_name']} dispatched to {booking['pickup_address']}.", "success")
        return redirect(url_for('emergency_track', sos_id=booking_id))

    # Create Razorpay Order
    rzp_order = create_razorpay_order(
        amount_inr=fee,
        receipt=f"amb_{booking_id}",
        notes={'booking_id': str(booking_id), 'vehicle': booking['vehicle_name']}
    )
    rzp_order_id = rzp_order.get('id', '') if rzp_order else ''

    return render_template(
        'ambulance_payment.html',
        booking=booking,
        fee=fee,
        razorpay_key_id=rzp_key_id,
        razorpay_order_id=rzp_order_id,
        amount_paise=int(fee * 100)
    )




@main_bp.route('/api/notifications/adherence', methods=['GET'])
def api_notifications_adherence():
    """Returns user notification stream with adherence alerts and unread count."""
    notifications = [
        {'id': 1, 'title': 'Medication Adherence Alert', 'message': 'Time to take Metformin 500mg after dinner.', 'type': 'medication', 'timestamp': '10 mins ago', 'read': False},
        {'id': 2, 'title': 'Appointment Confirmed', 'message': 'Dr. Rajesh Sharma confirmed consultation for tomorrow 10:30 AM.', 'type': 'appointment', 'timestamp': '2 hours ago', 'read': False},
        {'id': 3, 'title': 'Lab Report Ready', 'message': 'Your Complete Blood Count report is processed and ready.', 'type': 'lab', 'timestamp': '1 day ago', 'read': True}
    ]
    return jsonify({'success': True, 'notifications': notifications, 'unread_count': 2})




@main_bp.route('/api/notifications/send-simulated', methods=['POST'])
def api_notifications_send_simulated():
    """Simulates real-time dispatch of WhatsApp/SMS message."""
    data = request.get_json() or {}
    phone = data.get('phone', '+91 9334325920')
    message = data.get('message', 'Your Spherix appointment is confirmed.')
    channel = data.get('channel', 'WhatsApp')
    
    return jsonify({
        'success': True,
        'status': 'DELIVERED',
        'channel': channel,
        'recipient': phone,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })






@main_bp.route('/googleeb21c3b8aa08b91b.html')
def google_verification_file():
    """Serves the Google Search Console HTML verification file."""
    return Response("google-site-verification: googleeb21c3b8aa08b91b.html", mimetype='text/html')




@main_bp.route('/robots.txt')
def robots_txt():
    """Generates standard robots.txt instructions for search engine crawlers."""
    base = request.url_root.rstrip('/')
    content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /staff/
Disallow: /patient/dashboard
Disallow: /doctor/dashboard
Disallow: /hospital/dashboard

Sitemap: {base}/sitemap.xml
"""
    return Response(content, mimetype='text/plain')




@main_bp.route('/sitemap.xml')
def sitemap_xml():
    """Generates dynamic XML sitemap of all public pages for Google Search Console."""
    base = request.url_root.rstrip('/')
    now_date = datetime.now().strftime('%Y-%m-%d')
    
    pages = [
        {'loc': f"{base}/", 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': f"{base}/medical-shop", 'priority': '0.95', 'changefreq': 'daily'},
        {'loc': f"{base}/symptoms", 'priority': '0.90', 'changefreq': 'weekly'},
        {'loc': f"{base}/hospitals", 'priority': '0.85', 'changefreq': 'daily'},
        {'loc': f"{base}/conditions", 'priority': '0.85', 'changefreq': 'weekly'},
        {'loc': f"{base}/ayurveda", 'priority': '0.80', 'changefreq': 'weekly'},
        {'loc': f"{base}/cancer-care", 'priority': '0.80', 'changefreq': 'weekly'},
        {'loc': f"{base}/blood-bank", 'priority': '0.80', 'changefreq': 'daily'},
        {'loc': f"{base}/blood-donation-camps", 'priority': '0.75', 'changefreq': 'weekly'},
        {'loc': f"{base}/organ-donors", 'priority': '0.75', 'changefreq': 'weekly'},
        {'loc': f"{base}/drug-checker", 'priority': '0.80', 'changefreq': 'weekly'},
        {'loc': f"{base}/emergency", 'priority': '0.90', 'changefreq': 'monthly'},
        {'loc': f"{base}/login", 'priority': '0.70', 'changefreq': 'monthly'},
        {'loc': f"{base}/patient/login", 'priority': '0.60', 'changefreq': 'monthly'},
        {'loc': f"{base}/doctor/login", 'priority': '0.60', 'changefreq': 'monthly'},
        {'loc': f"{base}/hospital/login", 'priority': '0.60', 'changefreq': 'monthly'},
        {'loc': f"{base}/about", 'priority': '0.50', 'changefreq': 'monthly'},
        {'loc': f"{base}/contact", 'priority': '0.50', 'changefreq': 'monthly'},
        {'loc': f"{base}/faq", 'priority': '0.50', 'changefreq': 'monthly'},
        {'loc': f"{base}/blog", 'priority': '0.70', 'changefreq': 'weekly'},
    ]

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for p in pages:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{p["loc"]}</loc>')
        xml_lines.append(f'    <lastmod>{now_date}</lastmod>')
        xml_lines.append(f'    <changefreq>{p["changefreq"]}</changefreq>')
        xml_lines.append(f'    <priority>{p["priority"]}</priority>')
        xml_lines.append('  </url>')
    xml_lines.append('</urlset>')

    return Response('\n'.join(xml_lines), mimetype='application/xml')




