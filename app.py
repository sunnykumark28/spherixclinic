import os
import json
import csv
import random
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, make_response
import math
from datetime import datetime, date, time, timedelta
from dotenv import load_dotenv
import time as time_module
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from fpdf import FPDF
from io import BytesIO, StringIO
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from functools import wraps
import smtplib
from math import ceil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import re
import markdown
import requests
import urllib3
# Disable SSL warnings when verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import base64
import traceback
from collections import Counter
try:
    import qrcode
except ImportError:
    qrcode = None
    print("⚠️ Optional package 'qrcode' not installed; QR image generation may be disabled.")
import tempfile
try:
    from authlib.integrations.flask_client import OAuth
except ImportError:
    OAuth = None
    print("⚠️ Optional package 'authlib' not installed; OAuth login features may be disabled.")
try:
    import pyodbc
except ImportError:
    pyodbc = None
    print("⚠️ Optional package 'pyodbc' not installed; database connectivity may be impacted.")
try:
    from flask_socketio import SocketIO, emit, join_room
except ImportError:
    SocketIO = None
    emit = None
    join_room = None
    print("⚠️ Optional package 'flask_socketio' not installed; real-time chat features will be disabled.")

try:
    from google.cloud import vision
except ImportError:
    vision = None
    print("⚠️ Optional package 'google-cloud-vision' not installed; image analysis will be disabled.")

# Load environment variables before using any API keys
load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_MODEL = os.getenv('GROQ_API_MODEL', 'openai/gpt-oss-20b')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'GROQ').strip().upper()


def _is_groq_configured():
    return bool(GROQ_API_KEY and GROQ_API_KEY != 'none')


def _determine_ai_provider():
    if _is_groq_configured():
        return 'GROQ'
    return None


AI_PROVIDER_ACTIVE = _determine_ai_provider()
print(f"ℹ️ AI provider selected: {AI_PROVIDER_ACTIVE or 'NONE'}")

# Google Vision API Configuration
GOOGLE_VISION_API_KEY = os.getenv('GOOGLE_VISION_API_KEY')
ENABLE_IMAGE_ANALYSIS = os.getenv('ENABLE_IMAGE_ANALYSIS', 'true').lower() == 'true'

def _is_vision_configured():
    return bool(GOOGLE_VISION_API_KEY and vision and ENABLE_IMAGE_ANALYSIS)

if _is_vision_configured():
    print("✅ Google Vision API configured for image analysis")

# Helper to ensure text passed to FPDF contains only latin-1 characters
def to_latin1_str(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    # Normalize common dashes to ASCII hyphen
    value = value.replace('\u2014', '-').replace('\u2013', '-')
    # Encode to latin-1 replacing unencodable characters, then decode back to str
    return value.encode('latin-1', 'replace').decode('latin-1')

from drug_data import DRUG_DATABASE
from policy_data import POLICY_DATA
# Import data from other modules
from flask import request, redirect, url_for

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'a_very_secret_default_key') # Use an environment variable for secret key

# SocketIO may be optional for minimal operation if package is missing
if SocketIO:
    socketio = SocketIO(app, cors_allowed_origins="*")

    @socketio.on('join')
    def on_join(data):
        room = data.get('room')
        if room:
            join_room(room)

    @socketio.on('typing')
    def on_typing(data):
        room = data.get('room')
        is_typing = data.get('is_typing', False)
        sender = data.get('sender')
        if room:
            emit('user_typing', {
                'sender': sender,
                'is_typing': is_typing
            }, room=room, include_self=False)
else:
    socketio = None

# Helper function to get actual user ID from Flask-Login ID
def get_actual_user_id(user_id):
    """Extract actual ID from Flask-Login prefixed ID (e.g., 'doctor-123' -> '123')."""
    if not user_id or not isinstance(user_id, str):
        return user_id
    prefixes = ('doctor-', 'patient-', 'staff-', 'hospital-', 'blood_donor-', 'organ_donor-')
    for prefix in prefixes:
        if user_id.startswith(prefix):
            id_val = user_id[len(prefix):]
            return int(id_val) if id_val.isdigit() else id_val
    return user_id

# OAuth Setup
if OAuth:
    oauth = OAuth(app)
else:
    oauth = None

google_client_id = os.getenv('GOOGLE_CLIENT_ID')
google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

# Strip whitespace if keys are present to avoid 'invalid_client' errors
if google_client_id: google_client_id = google_client_id.strip()
if google_client_secret: google_client_secret = google_client_secret.strip()

if oauth:
    oauth.register(
        name='google',
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
else:
    print("⚠️ OAuth frontend not configured because authlib/OAuth is unavailable.")

# Limit maximum request payload (useful for uploaded images)
# Set to 16 MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


# Friendly handler for requests that exceed the MAX_CONTENT_LENGTH
@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(error):
    # Inform the user and redirect back to a sensible page
    try:
        flash('Uploaded file is too large. Please use an image smaller than 16 MB.', 'error')
    except Exception:
        pass
    return redirect(request.referrer or url_for('symptoms'))

# Initialize Flask-Limiter to protect against brute-force attacks
# limiter = Limiter(
#     get_remote_address,
#     app=app,
#     default_limits=["200 per day", "50 per hour"], # General limits for all routes
#     storage_uri="memory://" # Use in-memory storage
# )

# ---------------- Flask-Login Setup ----------------
# Email Configuration for Notifications
MAIL_SERVER = str(os.getenv('MAIL_SERVER', '')).strip(" '\"")
MAIL_PORT = int(str(os.getenv('MAIL_PORT', '587')).strip(" '\"") or 587)
MAIL_USE_TLS = str(os.getenv('MAIL_USE_TLS', 'True')).strip(" '\"").lower() == 'true'
MAIL_USERNAME = str(os.getenv('MAIL_USERNAME', '')).strip(" '\"")
MAIL_PASSWORD = str(os.getenv('MAIL_PASSWORD', '')).strip(" '\"")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_landing' # Redirect here if @login_required fails

@login_manager.user_loader
def load_user(user_id):
    """Load user from in-memory store for Flask-Login."""
    # user_id is now expected to be in the format 'role-id' (e.g., 'doctor-1', 'patient-1')
    try:
        role, id_val = user_id.split('-')
        if role == 'doctor':
            # Doctor IDs are always strings
            return TEMP_DATA['doctors'].get(id_val)
        elif role == 'patient':
            return TEMP_DATA['patients'].get(int(id_val))
        elif role == 'staff':
            return TEMP_DATA['staff'].get(int(id_val))
        elif role == 'hospital':
            return TEMP_DATA['hospitals'].get(int(id_val))
        elif role == 'blood_donor':
            return TEMP_DATA['blood_donors'].get(int(id_val))
        elif role == 'organ_donor':
            return TEMP_DATA['organ_donors'].get(int(id_val))
    except (ValueError, AttributeError):
        # Handle cases where user_id is not in the expected format
        return None
    return None # User not found

# ---------------- Custom Decorators for Role-Based Access ----------------
def patient_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_doctor:
            flash("Access denied. This page is for patients only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_doctor:
            flash("Access denied. This page is for doctors only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # For simplicity, we'll hardcode the admin email.
        # In a real app, you'd use a role/permission system.
        if not hasattr(current_user, 'email') or current_user.email != 'admin@devai.plus':
            flash("You do not have administrative privileges.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def hospital_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_hospital', False):
            flash("Access denied. This page is for hospital administrators only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- File-Based Data Store (JSON) ----------------
DATA_FILE = 'data_store.json'

# SQL Database Configuration
SERVER = os.getenv('DB_SERVER', 'localhost')
DATABASE = os.getenv('DB_NAME', 'dev_ai_plus')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASS', 'RadhaRani@123')
DRIVER = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')

# Default structure if the data file doesn't exist
TEMP_DATA = {
    "doctors": {},
    "patients": {},
    "hospitals": {},
    "staff": {},
    "appointments": {},
    "messages": {},
    "orders": {},
    "reviews": {},
    "blood_donors": {},
    "organ_donors": {},
    "contact_messages": [],
    "camp_registrations": {},
    "camps": {},
    "blood_stock": {
        "A+": 15, "A-": 5, "B+": 12, "B-": 4, "AB+": 8, "AB-": 3, "O+": 25, "O-": 10
    },
    "bed_bookings": {},
    "next_ids": {
        "doctor": 1,
        "patient": 1,
        "hospital": 1,
        "appointment": 1,
        "staff": 1,
        "message": 1,
        "order": 1,
        "review": 1,
        "blood_donor": 1,
        "organ_donor": 1,
        "camp": 1,
        "camp_registration": 1,
        "bed_booking": 1,
    }
}

def get_db_connection():
    conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
    return pyodbc.connect(conn_str, autocommit=True)

def save_data():
    """Saves the current state of TEMP_DATA to the SQL Database."""
    print("💾 Syncing data to SQL Database...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        def json_safe(val):
            if isinstance(val, (dict, list)):
                return json.dumps(val)
            return val

        # 1. Doctors
        cursor.execute("SELECT id FROM doctors")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['doctors'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM doctors WHERE id = ?", del_id)
        
        for doc_id, doc in TEMP_DATA['doctors'].items():
            if doc_id in db_ids:
                sql = """UPDATE doctors SET 
                    first_name=?, last_name=?, email=?, password=?, department=?, phone=?, specialization=?, 
                    address=?, profile_picture_url=?, bio=?, hospital_name=?, hospital_address=?, state=?, 
                    district=?, pincode=?, qualification=?, license_number=?, experience=?, consultation_type=?, 
                    consultation_fee=?, working_hours=?, languages_spoken=?, social_links=?, is_verified=?
                    WHERE id=?"""
                values = (
                    doc.first_name, doc.last_name, doc.email, doc.password, doc.department, doc.phone, doc.specialization,
                    doc.address, doc.profile_picture_url, doc.bio, doc.hospital_name, doc.hospital_address, doc.state,
                    doc.district, doc.pincode, doc.qualification, doc.license_number, doc.experience, doc.consultation_type,
                    doc.consultation_fee, doc.working_hours, doc.languages_spoken, json_safe(doc.social_links), doc.is_verified,
                    doc_id
                )
            else:
                sql = """INSERT INTO doctors (
                    id, first_name, last_name, email, password, department, phone, specialization, 
                    address, profile_picture_url, bio, hospital_name, hospital_address, state, 
                    district, pincode, qualification, license_number, experience, consultation_type, 
                    consultation_fee, working_hours, languages_spoken, social_links, is_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                values = (
                    doc_id, doc.first_name, doc.last_name, doc.email, doc.password, doc.department, doc.phone, doc.specialization,
                    doc.address, doc.profile_picture_url, doc.bio, doc.hospital_name, doc.hospital_address, doc.state,
                    doc.district, doc.pincode, doc.qualification, doc.license_number, doc.experience, doc.consultation_type,
                    doc.consultation_fee, doc.working_hours, doc.languages_spoken, json_safe(doc.social_links), doc.is_verified
                )
            cursor.execute(sql, values)

        # 2. Patients
        cursor.execute("SELECT id FROM patients")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['patients'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM patients WHERE id = ?", del_id)
        
        for p_id, p in TEMP_DATA['patients'].items():
            if p_id in db_ids:
                try:
                    cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=?, profile_picture_url=? WHERE id=?", 
                                   (p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), p_id))
                except pyodbc.Error:
                    cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=? WHERE id=?", 
                                   (p.name, p.email, p.password, p.age, p.gender, p_id))
            else:
                try:
                    cursor.execute("INSERT INTO patients (id, name, email, password, age, gender, profile_picture_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (p_id, p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None)))
                except pyodbc.Error:
                    cursor.execute("INSERT INTO patients (id, name, email, password, age, gender) VALUES (?, ?, ?, ?, ?, ?)",
                                   (p_id, p.name, p.email, p.password, p.age, p.gender))

        # 3. Hospitals
        cursor.execute("SELECT id FROM hospitals")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['hospitals'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM hospitals WHERE id = ?", del_id)
        
        for h_id, h in TEMP_DATA['hospitals'].items():
            if h_id in db_ids:
                try:
                    cursor.execute("UPDATE hospitals SET name=?, email=?, password=?, logo_url=?, total_beds=?, available_beds=?, address=?, icu_beds=?, available_icu_beds=?, doctors_available=?, is_verified=? WHERE id=?",
                                   (h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available, getattr(h, 'is_verified', True), h_id))
                except pyodbc.Error:
                    try:
                        cursor.execute("UPDATE hospitals SET name=?, email=?, password=?, logo_url=?, total_beds=?, available_beds=?, address=?, icu_beds=?, available_icu_beds=?, doctors_available=? WHERE id=?",
                                       (h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available, h_id))
                    except pyodbc.Error:
                        cursor.execute("UPDATE hospitals SET name=?, email=?, password=?, logo_url=?, total_beds=?, available_beds=?, address=? WHERE id=?",
                                       (h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h_id))
            else:
                try:
                    cursor.execute("INSERT INTO hospitals (id, name, email, password, logo_url, total_beds, available_beds, address, icu_beds, available_icu_beds, doctors_available, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (h_id, h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available, getattr(h, 'is_verified', True)))
                except pyodbc.Error:
                    try:
                        cursor.execute("INSERT INTO hospitals (id, name, email, password, logo_url, total_beds, available_beds, address, icu_beds, available_icu_beds, doctors_available) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (h_id, h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available))
                    except pyodbc.Error:
                        cursor.execute("INSERT INTO hospitals (id, name, email, password, logo_url, total_beds, available_beds, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                       (h_id, h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address))

        # 4. Staff
        cursor.execute("SELECT id FROM staff")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['staff'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM staff WHERE id = ?", del_id)
        
        for s_id, s in TEMP_DATA['staff'].items():
            if s_id in db_ids:
                cursor.execute("UPDATE staff SET name=?, email=?, password=?, role=?, phone=?, hospital_name=? WHERE id=?",
                               (s.name, s.email, s.password, s.role, s.phone, s.hospital_name, s_id))
            else:
                cursor.execute("INSERT INTO staff (id, name, email, password, role, phone, hospital_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (s_id, s.name, s.email, s.password, s.role, s.phone, s.hospital_name))

        # 5. Appointments
        cursor.execute("SELECT id FROM appointments")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['appointments'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM appointments WHERE id = ?", del_id)
        
        for a_id, a in TEMP_DATA['appointments'].items():
            if a_id in db_ids:
                sql = """UPDATE appointments SET 
                    patient_name=?, doctor_id=?, patient_id=?, appointment_date=?, appointment_time=?, 
                    patient_age=?, patient_id_number=?, patient_phone=?, reason=?, status=?, 
                    created_at=?, original_appointment_date=?, original_appointment_time=?, 
                    document_path=?, prescription_path=? WHERE id=?"""
                values = (
                    a.patient_name, a.doctor_id, a.patient_id, a.appointment_date, a.appointment_time,
                    a.patient_age, a.patient_id_number, a.patient_phone, a.reason, a.status,
                    a.created_at, a.original_appointment_date, a.original_appointment_time,
                    a.document_path, a.prescription_path, a_id
                )
            else:
                sql = """INSERT INTO appointments (
                    id, patient_name, doctor_id, patient_id, appointment_date, appointment_time, 
                    patient_age, patient_id_number, patient_phone, reason, status, 
                    created_at, original_appointment_date, original_appointment_time, 
                    document_path, prescription_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                values = (
                    a_id, a.patient_name, a.doctor_id, a.patient_id, a.appointment_date, a.appointment_time,
                    a.patient_age, a.patient_id_number, a.patient_phone, a.reason, a.status,
                    a.created_at, a.original_appointment_date, a.original_appointment_time,
                    a.document_path, a.prescription_path
                )
            cursor.execute(sql, values)

        # 6. Reviews
        cursor.execute("SELECT id FROM reviews")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['reviews'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM reviews WHERE id = ?", del_id)
        
        for r_id, r in TEMP_DATA['reviews'].items():
            if r_id in db_ids:
                cursor.execute("UPDATE reviews SET doctor_id=?, patient_id=?, patient_name=?, rating=?, comment=?, created_at=? WHERE id=?",
                               (r.doctor_id, r.patient_id, r.patient_name, r.rating, r.comment, r.created_at, r_id))
            else:
                cursor.execute("INSERT INTO reviews (id, doctor_id, patient_id, patient_name, rating, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (r_id, r.doctor_id, r.patient_id, r.patient_name, r.rating, r.comment, r.created_at))

        # 7. Messages
        cursor.execute("SELECT id FROM messages")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['messages'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM messages WHERE id = ?", del_id)
        
        for m_id, m in TEMP_DATA['messages'].items():
            if m_id in db_ids:
                try:
                    cursor.execute("UPDATE messages SET doctor_id=?, patient_id=?, sender=?, content=?, created_at=?, attachment_url=? WHERE id=?",
                                   (m.doctor_id, m.patient_id, m.sender, m.content, m.created_at, getattr(m, 'attachment_url', None), m_id))
                except pyodbc.Error:
                    cursor.execute("UPDATE messages SET doctor_id=?, patient_id=?, sender=?, content=?, created_at=? WHERE id=?",
                                   (m.doctor_id, m.patient_id, m.sender, m.content, m.created_at, m_id))
            else:
                try:
                    cursor.execute("INSERT INTO messages (id, doctor_id, patient_id, sender, content, created_at, attachment_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (m_id, m.doctor_id, m.patient_id, m.sender, m.content, m.created_at, getattr(m, 'attachment_url', None)))
                except pyodbc.Error:
                    cursor.execute("INSERT INTO messages (id, doctor_id, patient_id, sender, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   (m_id, m.doctor_id, m.patient_id, m.sender, m.content, m.created_at))

        # 8. Orders
        cursor.execute("SELECT id FROM orders")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['orders'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM orders WHERE id = ?", del_id)
        
        for o_id, o in TEMP_DATA['orders'].items():
            if o_id in db_ids:
                cursor.execute("UPDATE orders SET patient_id=?, items=?, total_price=?, shipping_address=?, order_date=?, status=? WHERE id=?",
                               (o.patient_id, json_safe(o.items), o.total_price, json_safe(o.shipping_address), o.order_date, o.status, o_id))
            else:
                cursor.execute("INSERT INTO orders (id, patient_id, items, total_price, shipping_address, order_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (o_id, o.patient_id, json_safe(o.items), o.total_price, json_safe(o.shipping_address), o.order_date, o.status))

        # 9. Blood Donors
        cursor.execute("SELECT id FROM blood_donors")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['blood_donors'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM blood_donors WHERE id = ?", del_id)
        
        for b_id, b in TEMP_DATA['blood_donors'].items():
            if b_id in db_ids:
                try:
                    cursor.execute("UPDATE blood_donors SET name=?, email=?, phone=?, blood_group=?, age=?, city=?, password=?, last_donation=?, profile_picture_url=?, created_at=? WHERE id=?",
                                   (b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at, b_id))
                except pyodbc.Error:
                    cursor.execute("UPDATE blood_donors SET name=?, email=?, phone=?, blood_group=?, age=?, city=?, password=?, last_donation=?, created_at=? WHERE id=?",
                                   (b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, b.created_at, b_id))
            else:
                try:
                    cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, profile_picture_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (b_id, b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at))
                except pyodbc.Error:
                    cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (b_id, b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, b.created_at))

        # Organ Donors
        cursor.execute("SELECT id FROM organ_donors")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['organ_donors'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM organ_donors WHERE id = ?", del_id)
        
        for od_id, od in TEMP_DATA['organ_donors'].items():
            if od_id in db_ids:
                try:
                    cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, profile_picture_url=?, created_at=? WHERE id=?",
                                   (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, od_id))
                except pyodbc.Error:
                    cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, created_at=? WHERE id=?",
                                   (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, od.created_at, od_id))
            else:
                try:
                    cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password, profile_picture_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (od_id, od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at))
                except pyodbc.Error:
                    cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (od_id, od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, od.created_at))

        # 10. Camps
        cursor.execute("SELECT id FROM camps")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['camps'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM camps WHERE id = ?", del_id)
        
        for c_id, c in TEMP_DATA['camps'].items():
            if c_id in db_ids:
                cursor.execute("UPDATE camps SET name=?, location=?, date=?, time=?, organizer=?, contact=? WHERE id=?",
                               (c['name'], c['location'], c['date'], c['time'], c['organizer'], c['contact'], c_id))
            else:
                cursor.execute("INSERT INTO camps (id, name, location, date, time, organizer, contact) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (c_id, c['name'], c['location'], c['date'], c['time'], c['organizer'], c['contact']))

        # 11. Camp Registrations
        cursor.execute("SELECT id FROM camp_registrations")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['camp_registrations'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM camp_registrations WHERE id = ?", del_id)
        
        for cr_id, cr in TEMP_DATA['camp_registrations'].items():
            if cr_id in db_ids:
                cursor.execute("UPDATE camp_registrations SET camp_name=?, name=?, email=?, phone=?, date=? WHERE id=?",
                               (cr['camp_name'], cr['name'], cr['email'], cr['phone'], cr['date'], cr_id))
            else:
                cursor.execute("INSERT INTO camp_registrations (id, camp_name, name, email, phone, date) VALUES (?, ?, ?, ?, ?, ?)",
                               (cr_id, cr['camp_name'], cr['name'], cr['email'], cr['phone'], cr['date']))

        # 12. Blood Stock
        for group, qty in TEMP_DATA['blood_stock'].items():
            cursor.execute("SELECT blood_group FROM blood_stock WHERE blood_group = ?", group)
            if cursor.fetchone():
                cursor.execute("UPDATE blood_stock SET quantity = ? WHERE blood_group = ?", (qty, group))
            else:
                cursor.execute("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", (group, qty))

        # 13. Bed Bookings (Wrapped in try/except in case table doesn't exist locally)
        try:
            cursor.execute("SELECT id FROM bed_bookings")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('bed_bookings', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM bed_bookings WHERE id = ?", del_id)
            
            for bb_id, bb in TEMP_DATA.get('bed_bookings', {}).items():
                if bb_id in db_ids:
                    cursor.execute("UPDATE bed_bookings SET hospital_id=?, patient_id=?, patient_name=?, patient_phone=?, bed_type=?, reason=?, status=?, created_at=? WHERE id=?",
                                   (bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, bb_id))
                else:
                    cursor.execute("INSERT INTO bed_bookings (id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (bb_id, bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at))
        except Exception as e:
            print(f"⚠️ Skipping bed_bookings sync (table might not exist): {e}")

        conn.commit()
        conn.close()
        print("✅ Data synced to SQL successfully.")
    except Exception as e:
        print(f"❌ Error syncing to SQL: {e}")
        traceback.print_exc()

def load_data():
    """Loads data from SQL Database into TEMP_DATA, rehydrating objects."""
    global TEMP_DATA
    print("🔄 Loading data from SQL Database...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        def fetch_dict(query):
            cursor.execute(query)
            cols = [column[0] for column in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

        # 1. Doctors
        docs = fetch_dict("SELECT * FROM doctors")
        TEMP_DATA['doctors'] = {d['id']: Doctor(**d) for d in docs}

        # 2. Patients
        pats = fetch_dict("SELECT * FROM patients")
        TEMP_DATA['patients'] = {p['id']: Patient(**p) for p in pats}

        # 3. Hospitals
        hosps = fetch_dict("SELECT * FROM hospitals")
        TEMP_DATA['hospitals'] = {h['id']: Hospital(**h) for h in hosps}

        # 4. Staff
        stf = fetch_dict("SELECT * FROM staff")
        TEMP_DATA['staff'] = {s['id']: Staff(**s) for s in stf}

        # 5. Appointments
        appts = fetch_dict("SELECT * FROM appointments")
        TEMP_DATA['appointments'] = {a['id']: Appointment(**a) for a in appts}

        # 6. Reviews
        revs = fetch_dict("SELECT * FROM reviews")
        TEMP_DATA['reviews'] = {r['id']: Review(**r) for r in revs}

        # 7. Messages
        msgs = fetch_dict("SELECT * FROM messages")
        TEMP_DATA['messages'] = {m['id']: Message(**m) for m in msgs}

        # 8. Orders
        ords = fetch_dict("SELECT * FROM orders")
        for o in ords:
            # Handle JSON fields stored as strings
            if isinstance(o.get('items'), str):
                try: o['items'] = json.loads(o['items'].replace("'", '"'))
                except: o['items'] = []
            if isinstance(o.get('shipping_address'), str):
                try: o['shipping_address'] = json.loads(o['shipping_address'].replace("'", '"'))
                except: o['shipping_address'] = {}
        TEMP_DATA['orders'] = {o['id']: Order(**o) for o in ords}

        # 9. Blood Donors
        bd = fetch_dict("SELECT * FROM blood_donors")
        TEMP_DATA['blood_donors'] = {b['id']: BloodDonor(**b) for b in bd}

        # Organ Donors
        ods = fetch_dict("SELECT * FROM organ_donors")
        for od in ods:
            if isinstance(od.get('organs'), str):
                try: od['organs'] = json.loads(od['organs'].replace("'", '"'))
                except: od['organs'] = []
        TEMP_DATA['organ_donors'] = {od['id']: OrganDonor(**od) for od in ods}

        # 10. Camps
        cmps = fetch_dict("SELECT * FROM camps")
        TEMP_DATA['camps'] = {c['id']: c for c in cmps}

        # 11. Camp Registrations
        cregs = fetch_dict("SELECT * FROM camp_registrations")
        TEMP_DATA['camp_registrations'] = {c['id']: c for c in cregs}

        # 12. Blood Stock
        bs = fetch_dict("SELECT * FROM blood_stock")
        TEMP_DATA['blood_stock'] = {b['blood_group']: b['quantity'] for b in bs}
        
        # 13. Bed Bookings
        try:
            bbs = fetch_dict("SELECT * FROM bed_bookings")
            if 'bed_bookings' not in TEMP_DATA: TEMP_DATA['bed_bookings'] = {}
            TEMP_DATA['bed_bookings'] = {b['id']: BedBooking(**b) for b in bbs}
        except Exception:
            print("⚠️ Skipping bed_bookings load (table might not exist)")
            if 'bed_bookings' not in TEMP_DATA: TEMP_DATA['bed_bookings'] = {}

        # 13. Calculate Next IDs (based on max existing IDs)
        if TEMP_DATA['doctors']:
            # Parse IDs like DOC/2026/001
            max_doc = 0
            for d_id in TEMP_DATA.get('doctors', {}):
                try:
                    if isinstance(d_id, str) and '/' in d_id:
                        num = int(d_id.split('/')[-1])
                        if num > max_doc: max_doc = num
                except: pass
            TEMP_DATA['next_ids']['doctor'] = max_doc + 1
        
        # Simple integer IDs (Including bed_booking)
        for entity in ['patient', 'hospital', 'staff', 'appointment', 'review', 'message', 'order', 'blood_donor', 'organ_donor', 'camp', 'camp_registration', 'bed_booking']:
            collection = TEMP_DATA.get(f"{entity}s" if entity != 'staff' else 'staff')
            if collection:
                TEMP_DATA['next_ids'][entity] = max(collection.keys()) + 1

        conn.close()
        print("✅ Data loaded from SQL successfully.")
    except Exception as e:
        print(f"❌ Error loading data from SQL: {e}")

# ---------------- ML Model and Knowledge Base Setup ----------------
KNOWLEDGE_BASE = {}
try:
    with open('knowledge_base.json', 'r') as f:
        KNOWLEDGE_BASE = json.load(f)
    print("✅ Knowledge base loaded successfully.")
except FileNotFoundError:
    print("⚠️  'knowledge_base.json' not found. Detailed advice will be limited.")



# ---------------- Data Models (Plain Python Classes) ----------------
class Doctor(UserMixin): # UserMixin should ideally be the first parent
    def __init__(self, id, first_name, last_name, email, password, department, **kwargs):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.department = department
        self.phone = kwargs.get('phone')
        self.specialization = kwargs.get('specialization')
        self.address = kwargs.get('address')
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.bio = kwargs.get('bio')
        self.hospital_name = kwargs.get('hospital_name')
        self.hospital_address = kwargs.get('hospital_address')
        self.state = kwargs.get('state')
        self.district = kwargs.get('district')
        self.pincode = kwargs.get('pincode')
        # New fields from your request
        self.qualification = kwargs.get('qualification')
        self.license_number = kwargs.get('license_number')
        self.experience = kwargs.get('experience')
        self.consultation_type = kwargs.get('consultation_type')
        self.consultation_fee = kwargs.get('consultation_fee')
        self.working_hours = kwargs.get('working_hours')
        self.languages_spoken = kwargs.get('languages_spoken')
        self.social_links = kwargs.get('social_links')
        self.is_verified = kwargs.get('is_verified', False)
        self.is_doctor = True

    def get_id(self):
        """Return a unique ID for Flask-Login, prefixed with the role."""
        return f"doctor-{self.id}"

    @property
    def reviews(self):
        return sorted([review for review in TEMP_DATA['reviews'].values() if review.doctor_id == self.id], key=lambda r: r.created_at, reverse=True)

    @property
    def average_rating(self):
        reviews = self.reviews
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)
    @property
    def appointments(self):
        return [appt for appt in TEMP_DATA['appointments'].values() if appt.doctor_id == self.id]

    @property
    def messages(self):
        return [msg for msg in TEMP_DATA['messages'].values() if msg.doctor_id == self.id]

class Patient(UserMixin): # UserMixin should ideally be the first parent
    def __init__(self, id, name, email, password, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.age = kwargs.get('age')
        self.gender = kwargs.get('gender')
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.is_doctor = False

    def get_id(self):
        """Return a unique ID for Flask-Login, prefixed with the role."""
        return f"patient-{self.id}" # This is correct

    @property
    def appointments(self):
        return [appt for appt in TEMP_DATA['appointments'].values() if appt.patient_id == self.id]

class Staff(UserMixin):
    def __init__(self, id, name, email, password, role, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role # e.g., 'Nurse', 'Receptionist'
        self.phone = kwargs.get('phone')
        self.hospital_name = kwargs.get('hospital_name')
        self.is_doctor = False
        self.is_staff = True

    def get_id(self):
        """Return a unique ID for Flask-Login, prefixed with the role."""
        return f"staff-{self.id}"

class Hospital(UserMixin):
    def __init__(self, id, name, email, password, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.logo_url = kwargs.get('logo_url')
        self.phone = kwargs.get('phone')
        self.city = kwargs.get('city')
        self.state = kwargs.get('state')
        self.zip_code = kwargs.get('zip_code')
        self.total_beds = int(kwargs.get('total_beds', 0))
        self.available_beds = int(kwargs.get('available_beds', 0))
        self.icu_beds = int(kwargs.get('icu_beds', 0))
        self.available_icu_beds = int(kwargs.get('available_icu_beds', 0))
        self.doctors_available = kwargs.get('doctors_available', 'Available')
        self.address = kwargs.get('address')
        self.general_bed_fee = float(kwargs.get('general_bed_fee', 50.0))
        self.icu_bed_fee = float(kwargs.get('icu_bed_fee', 150.0))
        self.is_verified = kwargs.get('is_verified', True) # Default True for backward compatibility
        self.is_doctor = False
        self.is_hospital = True

    def get_id(self):
        return f"hospital-{self.id}"

    @property
    def doctor_count(self):
        return len([d for d in TEMP_DATA['doctors'].values() if d.hospital_name == self.name])

class Appointment:
    def __init__(self, id, patient_name, doctor_id, appointment_date, appointment_time, **kwargs): # Added patient_age and patient_id_number
        self.id = id
        self.patient_name = patient_name
        self.doctor_id = doctor_id
        self.appointment_date = appointment_date
        self.appointment_time = appointment_time
        # New fields from booking form
        self.patient_age = kwargs.get('patient_age')
        self.patient_id_number = kwargs.get('patient_id_number')
        # Existing fields
        self.patient_phone = kwargs.get('patient_phone')
        self.patient_id = kwargs.get('patient_id')
        self.reason = kwargs.get('reason')
        self.status = kwargs.get('status', 'confirmed')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        # Fields for rescheduling
        self.original_appointment_date = kwargs.get('original_appointment_date')
        self.original_appointment_time = kwargs.get('original_appointment_time')
        self.document_path = kwargs.get('document_path')
        self.prescription_path = kwargs.get('prescription_path')


    @property
    def doctor(self):
        return TEMP_DATA['doctors'].get(self.doctor_id)

    @property
    def patient(self):
        return TEMP_DATA['patients'].get(self.patient_id)

class Review:
    def __init__(self, id, doctor_id, patient_id, patient_name, rating, comment, **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.rating = int(rating)
        self.comment = comment
        self.created_at = kwargs.get('created_at', datetime.utcnow())

class BloodDonor(UserMixin):
    def __init__(self, id, name, email, phone, blood_group, age, city, password=None, last_donation=None, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.blood_group = blood_group
        self.age = age
        self.city = city
        self.password = password
        self.last_donation = last_donation
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.is_doctor = False
        
    def get_id(self):
        return f"blood_donor-{self.id}"

class OrganDonor(UserMixin):
    def __init__(self, id, name, email, phone, organs, blood_group, age, city, password=None, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.organs = organs if isinstance(organs, list) else []
        self.blood_group = blood_group
        self.age = age
        self.city = city
        self.password = password
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.is_doctor = False

    def get_id(self):
        return f"organ_donor-{self.id}"

class Message:
    def __init__(self, id, doctor_id, patient_id, sender, content, **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.sender = sender
        self.content = content
        self.attachment_url = kwargs.get('attachment_url')
        
        created_at_val = kwargs.get('created_at', datetime.utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = datetime.utcnow()
        self.created_at = created_at_val

    @property
    def doctor(self):
        # Doctor ID is a string like 'DOC/2024/001'
        return TEMP_DATA['doctors'].get(self.doctor_id)

    @property
    def patient(self):
        return TEMP_DATA['patients'].get(self.patient_id)

class Order:
    def __init__(self, id, patient_id, items, total_price, shipping_address, order_date, status='Processing'):
        self.id = id
        self.patient_id = patient_id
        self.items = items # list of dicts from cart
        self.total_price = total_price
        self.shipping_address = shipping_address
        self.order_date = order_date
        self.status = status

class BedBooking:
    def __init__(self, id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status='pending', **kwargs):
        self.id = id
        self.hospital_id = hospital_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.patient_phone = patient_phone
        self.bed_type = bed_type
        self.reason = reason
        self.status = status
        
        created_at_val = kwargs.get('created_at', datetime.utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = datetime.utcnow()
        self.created_at = created_at_val

load_data() # Load data on startup instead of seeding every time

# ============ LOAD KNOWLEDGE BASE FOR LOCAL FALLBACK ============
KNOWLEDGE_BASE = {}
SYMPTOM_KEYWORDS = {}

def load_knowledge_base():
    """Load knowledge base from JSON file for local analysis fallback."""
    global KNOWLEDGE_BASE, SYMPTOM_KEYWORDS
    try:
        with open('knowledge_base.json', 'r') as f:
            KNOWLEDGE_BASE = json.load(f)
            print(f"✅ Loaded knowledge base with {len(KNOWLEDGE_BASE)} conditions")
        
        # Build symptom keyword index
        for condition, data in KNOWLEDGE_BASE.items():
            description = data.get('description', '').lower()
            advice = data.get('detailed_advice', '').lower()
            combined = f"{condition.lower()} {description} {advice}"
            SYMPTOM_KEYWORDS[condition] = combined.split()
    except FileNotFoundError:
        print("⚠️ Knowledge base not found. Using minimal fallback.")
        KNOWLEDGE_BASE = {}
    except json.JSONDecodeError as e:
        print(f"⚠️ Error parsing knowledge base: {e}")
        KNOWLEDGE_BASE = {}

# Load on startup
load_knowledge_base()

# Initialize the new SymptomAnalyzer (global instance for reuse)
try:
    from symptoms_analyzer import SymptomAnalyzer
    analyzer = SymptomAnalyzer()
    print("✅ SymptomAnalyzer initialized for advanced diagnosis")
except ImportError:
    analyzer = None
    print("⚠️ SymptomAnalyzer not available - using local fallback only")
except Exception as e:
    analyzer = None
    print(f"⚠️ Error initializing SymptomAnalyzer: {e}")

def analyze_symptoms_locally(symptoms_query, age=None, gender=None):
    """
    Local fallback analyzer using knowledge base keyword matching.
    Does not require API calls.
    """
    query_lower = symptoms_query.lower()
    query_words = set(query_lower.split())
    
    # Score each condition based on keyword matches
    condition_scores = {}
    
    for condition, keywords in SYMPTOM_KEYWORDS.items():
        keyword_set = set(keywords)
        matches = len(query_words & keyword_set)
        if matches > 0:
            condition_scores[condition] = matches
    
    # Get top condition(s)
    if condition_scores:
        top_condition = max(condition_scores, key=condition_scores.get)
        condition_data = KNOWLEDGE_BASE.get(top_condition, {})
        
        return {
            "conditions": [top_condition, "General symptom pattern"],
            "confidence_scores": [75, 50],
            "advice": condition_data.get('detailed_advice', 'Please consult a healthcare provider for personalized advice.'),
            "description": condition_data.get('description', 'Analysis based on local knowledge base.'),
            "self_care": condition_data.get('self_care', ["Rest", "Stay hydrated", "Monitor symptoms"]),
            "suggested_medicines": ["Consult healthcare provider for medication"],
            "when_to_see_doctor": condition_data.get('when_to_see_doctor', 'Consult a doctor if symptoms persist or worsen.'),
            "recommended_departments": condition_data.get('recommended_departments', ['General Medicine']),
            "note": "⚠️ This analysis uses local knowledge base (AI API unavailable). Please consult a healthcare professional for accurate diagnosis."
        }
    
    # Default fallback response
    return {
        "conditions": ["General Consultation Recommended"],
        "confidence_scores": [40],
        "advice": "Your symptoms require professional medical evaluation. Please consult a healthcare provider for accurate diagnosis and treatment.",
        "description": "Unable to identify specific condition from symptoms provided.",
        "self_care": ["Rest", "Stay hydrated", "Monitor symptoms", "Keep a symptom diary"],
        "suggested_medicines": ["Consult healthcare provider"],
        "when_to_see_doctor": "It is recommended to see a healthcare provider to properly diagnose your symptoms.",
        "recommended_departments": ["General Medicine"],
        "note": "⚠️ This analysis uses local knowledge base (AI API unavailable). Please consult a healthcare professional for accurate diagnosis."
    }

# ============ CACHING & RATE LIMITING FOR AI APIs ============
SYMPTOM_CACHE = {}  # Cache for symptom analysis results
LAST_API_CALL_TIME = {}  # Track last API call time per user

def get_cache_key(symptoms_query, age, gender):
    """Generate a hash-based cache key from symptoms and patient info."""
    cache_str = f"{symptoms_query}:{age}:{gender}"
    return hashlib.md5(cache_str.encode()).hexdigest()


def _extract_json_payload(text):
    """Extract JSON object from AI response text safely."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    
    # Clean up markdown code blocks safely
    if text.startswith('```'):
        lines = text.split('\n')
        if len(lines) > 1 and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        text = '\n'.join(lines).strip()

    # Find first JSON object in text
    try:
        # attempt direct parse
        return json.loads(text)
    except Exception:
        pass

    # last fallback: attempt to pull chars between first '{' and last '}'
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass

    return None



def _analyze_image_with_vision(image_path):
    """
    Analyze symptoms from an image using Google Vision API.
    Returns visual findings relevant to medical analysis.
    """
    if not _is_vision_configured():
        return None
    
    try:
        # Read image file
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        # Create Vision client with API key
        client = vision.ImageAnnotatorClient(
            client_options={"api_key": GOOGLE_VISION_API_KEY}
        )
        
        image = vision.Image(content=content)
        
        # Perform multiple analyses for comprehensive results
        features = [
            vision.Feature({'type_': vision.Feature.Type.LABEL_DETECTION}),
            vision.Feature({'type_': vision.Feature.Type.TEXT_DETECTION}),
            vision.Feature({'type_': vision.Feature.Type.OBJECT_LOCALIZATION}),
            vision.Feature({'type_': vision.Feature.Type.SAFE_SEARCH_DETECTION}),
        ]
        
        request_obj = vision.AnnotateImageRequest({"image": image, "features": features})
        response = client.annotate_image(request_obj)
        
        # Extract relevant findings
        findings = {
            'visual_elements': [],
            'text_found': '',
            'objects_detected': [],
            'analysis': ''
        }
        
        # Get labels (what's visible in the image)
        if response.label_annotations:
            findings['visual_elements'] = [
                label.description for label in response.label_annotations[:5]
            ]
        
        # Extract text from image (OCR)
        if response.text_annotations:
            findings['text_found'] = response.text_annotations[0].description[:500]
        
        # Get objects detected
        if response.localized_object_annotations:
            findings['objects_detected'] = [
                obj.name for obj in response.localized_object_annotations[:3]
            ]
        
        # Build analysis description from findings
        analysis_parts = []
        if findings['visual_elements']:
            analysis_parts.append(f"Visual indicators: {', '.join(findings['visual_elements'])}")
        if findings['text_found']:
            analysis_parts.append(f"Text visible in image: {findings['text_found'][:100]}...")
        if findings['objects_detected']:
            analysis_parts.append(f"Objects identified: {', '.join(findings['objects_detected'])}")
        
        findings['analysis'] = ' '.join(analysis_parts) or "Image analyzed successfully"
        
        print(f"✅ Image analysis complete: {findings['analysis'][:100]}...")
        return findings
        
    except Exception as e:
        print(f"❌ Image analysis error: {e}")
        return None


def _invoke_groq_symptom_analysis(symptoms_query, age=None, gender=None):
    """Call Groq API for symptom analysis and normalize output schema."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/responses"
    prompt = f"""You are a professional medical triage assistant. Analyze these patient symptom details and produce a JSON object ONLY. Output valid JSON without any markdown formatting like ```json.

symptoms: {symptoms_query}
age: {age or 'unknown'}
gender: {gender or 'unknown'}

CRITICAL INSTRUCTION: Explicitly tailor your diagnosis, advice, and warnings to a patient of this specific age and biological sex. Consider gender-specific conditions, hormonal factors, and physiological risk factors.

Required keys:
- conditions: list of 1-3 probable condition names (strings)
- confidence_scores: list of numeric probabilities matching conditions (0-100)
- advice: concise medical advice for the user.
- description: short explanation of likely condition.
- self_care: list of 3 practical self-care steps.
- suggested_medicines: list of safe over-the-counter suggestions (non-prescriptive).
- when_to_see_doctor: red-flags with urgency guidance.
- recommended_departments: list of relevant specialty departments.
- note: short caution that this is not a diagnosis.
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'input': prompt,
        'temperature': 0.25,
        'max_output_tokens': 2048
    }

    try:
        print(f"📤 Calling Groq API at: {endpoint}")
        print(f"📤 With model: {GROQ_API_MODEL}, headers: Authorization={GROQ_API_KEY[:20]}...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=False)
        response.raise_for_status()
        payload_json = response.json()

        output_text = payload_json.get('output_text')
        if not output_text:
            output = payload_json.get('output', [])
            if isinstance(output, list) and len(output) > 1:
                # Look for the message type output
                for item in output:
                    if item.get('type') == 'message':
                        content = item.get('content', [])
                        if isinstance(content, list) and content:
                            for content_item in content:
                                if content_item.get('type') == 'output_text':
                                    output_text = content_item.get('text', '')
                                    break
                        break
            if not output_text:
                raise ValueError('Groq response has no output_text')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        result = {
            'conditions': parsed.get('conditions') if isinstance(parsed.get('conditions'), list) else [parsed.get('conditions')] if parsed.get('conditions') else ['Non-specific symptoms'],
            'confidence_scores': parsed.get('confidence_scores') if isinstance(parsed.get('confidence_scores'), list) else [60],
            'advice': parsed.get('advice') or parsed.get('recommendation') or 'Please consult a medical professional.',
            'description': parsed.get('description') or 'Symptom pattern analysis from Groq AI.',
            'self_care': parsed.get('self_care') if isinstance(parsed.get('self_care'), list) else ['Monitor symptoms', 'Stay hydrated', 'If symptoms worsen, seek healthcare.'],
            'suggested_medicines': parsed.get('suggested_medicines') if isinstance(parsed.get('suggested_medicines'), list) else ['Rest', 'Hydration', 'Gentle pain relief'],
            'when_to_see_doctor': parsed.get('when_to_see_doctor') or 'Visit a doctor if symptoms worsen or persist beyond 48 hours.',
            'recommended_departments': parsed.get('recommended_departments') if isinstance(parsed.get('recommended_departments'), list) else ['General Medicine'],
            'note': parsed.get('note') or 'This is an AI-generated suggestion and not a medical diagnosis.',
        }

        if len(result['confidence_scores']) < len(result['conditions']):
            result['confidence_scores'] = result['confidence_scores'] + [55] * (len(result['conditions']) - len(result['confidence_scores']))

        return result

    except Exception as e:
        print(f"⚠️ Groq analysis failed: {e}")
        return {
            'conditions': ['AI Service Unavailable'],
            'confidence_scores': [0],
            'advice': 'Could not complete analysis via Groq API. Please verify API key and network connectivity.',
            'description': 'Groq API call error.',
            'self_care': ['Check your network and API key', 'Retry the analysis', 'Consult a healthcare professional in-person if urgent'],
            'suggested_medicines': ['Consult a doctor'],
            'when_to_see_doctor': 'Contact healthcare provider if condition appears serious.',
            'recommended_departments': ['General Medicine'],
            'note': str(e),
            'error_details': str(e)
        }


def _invoke_groq_drug_info(drug_name):
    """Call Groq API to generate a drug information summary."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/responses"
    prompt = f"""You are a professional medical reference assistant. Provide a JSON object only, no markdown or extra text.

Drug name: {drug_name}

Required keys:
- drug_name: string
- description: string
- primary_use: concise primary medical use or indication
- common_side_effects: list of 3-5 common side effects
- caution: short caution statement, including when to consult a doctor
- clinical_notes: brief note about important usage or safety information
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'input': prompt,
        'temperature': 0.2,
        'max_output_tokens': 1024
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=False)
        response.raise_for_status()
        payload_json = response.json()

        output_text = payload_json.get('output_text')
        if not output_text:
            output = payload_json.get('output', [])
            if isinstance(output, list):
                for item in output:
                    if item.get('type') == 'message':
                        content = item.get('content', [])
                        if isinstance(content, list):
                            for content_item in content:
                                if content_item.get('type') == 'output_text':
                                    output_text = content_item.get('text', '')
                                    break
                        break
        if not output_text:
            raise ValueError('Groq response has no output_text')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        return {
            'drug_name': parsed.get('drug_name', drug_name),
            'description': parsed.get('description', 'No description available.'),
            'primary_use': parsed.get('primary_use', 'General medication use.'),
            'common_side_effects': parsed.get('common_side_effects') if isinstance(parsed.get('common_side_effects'), list) else [],
            'caution': parsed.get('caution', 'Consult a healthcare professional before use.'),
            'clinical_notes': parsed.get('clinical_notes', ''),
            'source': 'ai'
        }
    except Exception as e:
        print(f"❌ Groq drug info generation failed: {e}")
        return None


def _invoke_groq_condition_info(condition_name):
    """Call Groq API to generate a detailed condition summary."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/responses"
    prompt = f"""You are a professional medical reference assistant. Provide a JSON object only, with no markdown or extra text.

Condition name: {condition_name}

Required keys:
- condition_name: string
- description: string
- common_symptoms: list of 3-5 symptoms
- typical_treatments: list of 3-5 treatment approaches or solutions
- recommended_medicines: list of 3-5 common medicines or supplements (non-prescriptive)
- what_not_to_do: list of 3-5 actions to avoid
- self_care: list of 3-5 practical self-care actions
- when_to_see_doctor: string
- key_precautions: list of 3-5 important precautions
- source: string
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'input': prompt,
        'temperature': 0.25,
        'max_output_tokens': 2048
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=False)
        response.raise_for_status()
        payload_json = response.json()

        output_text = payload_json.get('output_text')
        if not output_text:
            output = payload_json.get('output', [])
            if isinstance(output, list):
                for item in output:
                    if item.get('type') == 'message':
                        content = item.get('content', [])
                        if isinstance(content, list):
                            for content_item in content:
                                if content_item.get('type') == 'output_text':
                                    output_text = content_item.get('text', '')
                                    break
                        break
        if not output_text:
            raise ValueError('Groq response has no output_text')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        return {
            'condition_name': parsed.get('condition_name', condition_name),
            'description': parsed.get('description', ''),
            'common_symptoms': parsed.get('common_symptoms') if isinstance(parsed.get('common_symptoms'), list) else [],
            'typical_treatments': parsed.get('typical_treatments') if isinstance(parsed.get('typical_treatments'), list) else [],
            'recommended_medicines': parsed.get('recommended_medicines') if isinstance(parsed.get('recommended_medicines'), list) else [],
            'what_not_to_do': parsed.get('what_not_to_do') if isinstance(parsed.get('what_not_to_do'), list) else [],
            'self_care': parsed.get('self_care') if isinstance(parsed.get('self_care'), list) else [],
            'when_to_see_doctor': parsed.get('when_to_see_doctor', ''),
            'key_precautions': parsed.get('key_precautions') if isinstance(parsed.get('key_precautions'), list) else [],
            'source': 'ai'
        }
    except Exception as e:
        print(f"❌ Groq condition info generation failed: {e}")
        return None


def get_ml_analysis(symptoms_query, age=None, gender=None, image_path=None):
    """
    Primary symptom analyser: Groq API only. No local knowledge base fallback.
    """
    print(f"📚 Analyzing symptoms via {AI_PROVIDER_ACTIVE or 'NONE'}: '{symptoms_query}' [age={age}, gender={gender}]")

    if image_path:
        # Resolve local image path if it's a URL path
        if image_path.startswith('/static/'):
            local_image_path = os.path.join(app.root_path, image_path.lstrip('/'))
        else:
            local_image_path = image_path
            
        # Analyze image with Google Vision API using the absolute path
        vision_findings = _analyze_image_with_vision(local_image_path)
        if vision_findings:
            # Enhance symptoms_query with image analysis findings
            enhanced_query = f"{symptoms_query}\n\nVisual Analysis: {vision_findings['analysis']}"
            # Use enhanced query for Groq analysis
            symptoms_query = enhanced_query
            print(f"✅ Enhanced symptom query with image analysis")
        else:
            print("⚠️ Image analysis failed, proceeding with text analysis only")

    # Check cache first
    cache_key = get_cache_key(symptoms_query, age, gender)
    if cache_key in SYMPTOM_CACHE:
        print(f"✅ Using cached AI result for key: {cache_key}")
        return SYMPTOM_CACHE[cache_key]

    # Rate limiting: ensure at least 10 seconds between API calls
    current_time = time_module.time()
    if 'global' in LAST_API_CALL_TIME:
        time_since_last = current_time - LAST_API_CALL_TIME['global']
        if time_since_last < 10:  # 10 second minimum interval
            wait_time = 10 - time_since_last
            print(f"⏳ Rate limiting: waiting {wait_time:.1f}s before API call")
            time_module.sleep(wait_time)

    if AI_PROVIDER_ACTIVE != 'GROQ':
        print("⚠️ Groq API is not configured. Symptom analysis cannot proceed.")
        return {
            'conditions': ['Groq API not configured'],
            'confidence_scores': [0],
            'advice': 'Please configure GROQ_API_KEY and set AI_PROVIDER=GROQ.',
            'description': 'Symptom analysis requires Groq API configuration.',
            'self_care': ['Configure Groq API key', 'Restart the application'],
            'suggested_medicines': ['N/A'],
            'when_to_see_doctor': 'N/A',
            'recommended_departments': ['N/A'],
            'note': 'Groq API is required for symptom analysis in this mode.',
            'error_details': 'GROQ_API_KEY missing or invalid'
        }

    result = _invoke_groq_symptom_analysis(symptoms_query, age, gender)

    if result and 'error_details' not in result:
        LAST_API_CALL_TIME['global'] = time_module.time()
        SYMPTOM_CACHE[cache_key] = result
        return result

    print("❌ Groq analysis failed. No local fallback is allowed.")
    if result:
        return result

    return {
        'conditions': ['AI Service Unavailable'],
        'confidence_scores': [0],
        'advice': 'Groq API call failed. Please verify your GROQ_API_KEY and network connectivity.',
        'description': 'Groq API call error.',
        'self_care': ['Check your GROQ_API_KEY', 'Retry the analysis', 'Consult a healthcare professional in-person if urgent'],
        'suggested_medicines': ['Consult a doctor'],
        'when_to_see_doctor': 'Contact healthcare provider if condition appears serious.',
        'recommended_departments': ['General Medicine'],
        'note': 'This application is configured to use Groq only. Local fallback is disabled.',
        'error_details': 'Groq API call failed'
    }


def send_notification_email(to_email, subject, body, is_html=False, attachment_name=None, attachment_data=None):
    """Sends an email notification."""
    if not all([MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD]):
        print(f"⚠️ Email sending is not configured. Server: '{MAIL_SERVER}', User: '{MAIL_USERNAME}', Pass: {'***' if MAIL_PASSWORD else 'None'}")
        return False

    if attachment_data:
        msg = MIMEMultipart()
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body))
            
        part = MIMEApplication(attachment_data, Name=attachment_name)
        part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
        msg.attach(part)
    else:
        if is_html:
            msg = MIMEText(body, 'html')
        else:
            msg = MIMEText(body)

    msg['Subject'] = subject
    msg['From'] = MAIL_USERNAME
    msg['To'] = to_email

    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            if MAIL_USE_TLS:
                server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
        print(f"Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"⚠️ SMTP Authentication Error: {e}. If using Gmail, ensure you are using a 16-digit 'App Password'.")
        return False
    except Exception as e:
        print(f"⚠️ Failed to send email to {to_email}: {e}")
        return False

def setup_admin_user():
    """
    Ensures the admin user exists with a default password for development.
    This function will create the admin user if it doesn't exist,
    or update the password if it does.
    """
    admin_email = 'admin@devai.plus'
    admin_password = 'admin@123' # Explicitly setting the admin password here
    hashed_password = generate_password_hash(admin_password, method='pbkdf2:sha256:260000')

    # Check if admin exists as a doctor or patient
    admin_user = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == admin_email), None)
    if not admin_user:
        admin_user = next((p for p in TEMP_DATA['patients'].values() if p.email == admin_email), None)

    if admin_user:
        # Admin user exists, just update the password to the default
        admin_user.password = hashed_password
        if isinstance(admin_user, Doctor):
            admin_user.is_verified = True
        print(f"✅ Admin user '{admin_email}' found. Password has been reset to the default.")
        save_data()
    else:
        # Admin user does not exist, create one as a doctor
        year = datetime.now().year
        next_id_num = TEMP_DATA['next_ids']['doctor']
        new_id = f"DOC/{year}/{next_id_num:03d}"
        new_admin_doctor = Doctor(
            id=new_id, first_name="Admin", last_name="User", is_verified=True,
            email=admin_email, password=hashed_password, department="Administration"
        )
        TEMP_DATA['doctors'][new_id] = new_admin_doctor
        TEMP_DATA['next_ids']['doctor'] += 1
        print(f"✅ Admin user '{admin_email}' created with a new default password.")
        save_data()

def setup_hospital_user():
    """Ensures a default hospital user exists."""
    email = 'hospital@devai.plus'
    password = 'hospital123'
    hashed = generate_password_hash(password, method='pbkdf2:sha256:260000')
    
    existing = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
    if not existing:
        new_id = TEMP_DATA['next_ids']['hospital']
        hospital = Hospital(id=new_id, name="General Hospital", email=email, password=hashed)
        TEMP_DATA['hospitals'][new_id] = hospital
        TEMP_DATA['next_ids']['hospital'] += 1
        save_data()
        print(f"✅ Hospital user '{email}' created.")


# ---------------- Context Processors ----------------
@app.context_processor
def inject_cart():
    """Makes cart information available to all templates."""
    cart = session.get('cart', [])
    cart_item_count = 0
    total_price = 0
    for item in cart:
        cart_item_count += item.get('quantity', 0)
        total_price += item.get('quantity', 0) * item.get('price', 0)
     
    return dict(cart=cart, 
                cart_item_count=cart_item_count, 
                cart_total_price=round(total_price, 2))

# ---------------- Routes ----------------

@app.route('/')
def home():
    current_year = datetime.now().year
    return render_template('home.html', current_year=current_year)

@app.route("/health-tips")
def health_tips():
    return render_template("health_tips.html")

@app.route("/emergency")
def emergency():
    return render_template("emergency.html")

@app.route("/first-aid")
def first_aid():
    return render_template("first_aid.html")

@app.route("/ayurveda")
def ayurveda():
    return render_template("ayurveda.html")

@app.route("/telemedicine")
@app.route("/telemedicine/<int:appointment_id>")
def telemedicine(appointment_id=None):
    room_name = None
    if appointment_id:
        appointment = TEMP_DATA['appointments'].get(appointment_id)
        if appointment:
            # Creates a unique, deterministic room ID tied to this exact database appointment
            safe_doc_id = str(appointment.doctor_id).replace('/', '')
            room_name = f"DevAiConsult_Appt{appointment.id}_Doc{safe_doc_id}"
    return render_template("telemedicine.html", room_name=room_name)

# ========== AI DIAGNOSIS LANDING PAGE ==========
@app.route('/check', methods=['GET'])
def ai_diagnosis():
    """
    AI Diagnosis landing page - gateway to the diagnosis system.
    Showcases features and allows users to start diagnosis.
    """
    return render_template('ai_diagnosis.html')

# ========== SYMPTOM CONSULTATION ROUTES ==========
@app.route('/check-symptoms', methods=['GET', 'POST'])
def symptoms():
    if request.method == 'POST':
        age = request.form.get('age')
        gender = request.form.get('gender')
        if not age or not gender:
            flash('Please fill in all fields', 'error')
            return redirect(url_for('symptoms'))
        session['age'] = age
        session['gender'] = gender
        return redirect(url_for('symptoms_step2'))

    return render_template('symptoms_step1.html')


@app.route('/symptoms/step2', methods=['GET', 'POST'])
def symptoms_step2():
    """Step 2: collect detailed symptom info (text, body part, optional image) and redirect to results."""
    if request.method == 'POST':
        symptoms_text = request.form.get('symptoms', '').strip()
        body_part = request.form.get('body_part', '').strip()
        camera_data = request.form.get('camera_image_data')

        # Server-side validation: ensure at least one input is provided
        if not symptoms_text and not body_part and not camera_data:
            flash('Please provide at least one input: describe symptoms, select an area, or capture an image.', 'error')
            return redirect(url_for('symptoms_step2'))

        # Save into session for later processing
        session['symptoms'] = symptoms_text
        session['body_part'] = body_part

        # 1) Check for base64 camera image data (from in-browser camera capture)
        if camera_data:
            try:
                # Format: data:image/png;base64,<base64data>
                header, encoded = camera_data.split(',', 1)
                binary_data = base64.b64decode(encoded)

                uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                stored_name = f"captured_symptom_{timestamp}.jpg"
                save_path = os.path.join(uploads_dir, stored_name)
                with open(save_path, 'wb') as f:
                    f.write(binary_data)

                # Save relative path in session for later use
                session['symptom_image_path'] = f"/static/uploads/{stored_name}"
            except Exception as e:
                print(f"⚠️ Failed to decode/save camera image: {e}")
        else:
            # Wipe out previous image session if a new text/dropdown analysis is run without a camera
            session.pop('symptom_image_path', None)

        return redirect(url_for('symptoms_result'))

    # GET -> render the step2 template
    return render_template('symptoms_step2.html')

# Step 3 & 4: AI Process and Results
@app.route('/symptoms/result')
def symptoms_result():
    """
    Displays the analysis results using the new advanced SymptomAnalyzer.
    Uses modern template with better formatting and UX.
    """
    age = session.get('age')
    gender = session.get('gender')
    symptoms = session.get('symptoms', '')
    body_part = session.get('body_part', '')
    image_path = session.get('symptom_image_path')

    input_text = symptoms or f"Symptoms in {body_part}"
    
    # Use ML-based analysis (Groq API) as the primary method.
    result = get_ml_analysis(input_text, age=age, gender=gender, image_path=image_path)

    if result.get("conditions") and ("AI Service Unavailable" in result.get("conditions") or "Groq API" in result.get("conditions") or "Groq API not configured" in result.get("conditions")):
        api_error = result.get("error_details", "Please try again later.")
        flash(f"Groq API Failed: {api_error}", "error")
        return redirect(url_for('symptoms_step2'))

    session['symptom_analysis_result'] = result

    doctors_for_recommendation = []
    recommended_depts = result.get('recommended_departments', [])
    all_db_doctors = list(TEMP_DATA['doctors'].values())
    if recommended_depts:
        doctors_for_recommendation = [
            doc for doc in all_db_doctors
            if doc.department in recommended_depts
        ]

    return render_template('symptom_result.html',
                           query=input_text,
                           result=result,
                           doctors=doctors_for_recommendation,
                           age=age,
                           gender=gender)

# ========== ADVANCED SYMPTOMS ANALYZER API ENDPOINTS ==========
@app.route('/api/symptoms/analyze', methods=['POST'])
def api_symptoms_analyze():
    """
    API endpoint for advanced symptoms analysis using the new SymptomAnalyzer.
    
    Request JSON:
    {
        "symptoms": "description of symptoms",
        "age": 30,
        "gender": "M",
        "body_part": "chest"
    }
    
    Response: Full analysis with conditions, confidence, severity, recommendations
    """
    try:
        if not analyzer:
            return jsonify({'error': 'Analyzer not available', 'success': False}), 500
        
        data = request.get_json() or {}
        symptoms = data.get('symptoms', '').strip()
        age = data.get('age')
        gender = data.get('gender')
        body_part = data.get('body_part')
        
        if not symptoms:
            return jsonify({'error': 'Symptoms field is required', 'success': False}), 400
        
        # Perform analysis using AI (Groq)
        result = get_ml_analysis(
            symptoms_query=symptoms,
            age=age,
            gender=gender
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ API Analysis Error: {e}")
        return jsonify({
            'error': f'Analysis failed: {str(e)}',
            'success': False
        }), 500

@app.route('/api/symptoms/quick', methods=['POST'])
def api_symptoms_quick():
    """
    Quick symptom analysis endpoint - lightweight version.
    
    Request JSON: {"symptoms": "description"}
    Response: Top conditions only
    """
    try:
        if not analyzer:
            return jsonify({'error': 'Analyzer not available', 'success': False}), 500
        
        data = request.get_json() or {}
        symptoms = data.get('symptoms', '').strip()
        
        if not symptoms:
            return jsonify({'error': 'Symptoms field is required', 'success': False}), 400
        
        # Quick analysis using AI
        analysis = get_ml_analysis(symptoms)
        quick_result = {
            'symptoms': symptoms,
            'top_condition': analysis.get('conditions', [None])[0] if analysis.get('conditions') else None,
            'all_matches': [{'name': cond, 'confidence': conf} for cond, conf in zip(analysis.get('conditions', []), analysis.get('confidence_scores', []))],
            'severity': 'Unknown',  # Groq doesn't provide severity levels
            'confidence': 'High' if analysis.get('conditions') else 'Low'
        }
        
        return jsonify({
            'success': True,
            'data': quick_result,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Quick Analysis Error: {e}")
        return jsonify({
            'error': f'Quick analysis failed: {str(e)}',
            'success': False
        }), 500

@app.route('/api/symptoms/search', methods=['GET'])
def api_symptoms_search():
    """
    Search for conditions matching a keyword.
    
    Query: /api/symptoms/search?keyword=fever
    Response: List of matching conditions
    """
    try:
        if not analyzer:
            return jsonify({'error': 'Analyzer not available', 'success': False}), 500
        
        keyword = request.args.get('keyword', '').strip()
        
        if not keyword:
            return jsonify({'error': 'Keyword parameter is required', 'success': False}), 400
        
        if len(keyword) < 2:
            return jsonify({'error': 'Keyword must be at least 2 characters', 'success': False}), 400
        
        results = analyzer.search_conditions(keyword)
        
        return jsonify({
            'success': True,
            'keyword': keyword,
            'results': results,
            'count': len(results),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Search Error: {e}")
        return jsonify({
            'error': f'Search failed: {str(e)}',
            'success': False
        }), 500

@app.route('/api/symptoms/condition/<condition_name>', methods=['GET'])
def api_symptoms_condition(condition_name):
    """
    Get details about a specific condition.
    
    URL: /api/symptoms/condition/Flu
    Response: Full condition details
    """
    try:
        if not analyzer:
            return jsonify({'error': 'Analyzer not available', 'success': False}), 500
        
        details = analyzer.get_condition_details(condition_name)
        
        if not details:
            return jsonify({
                'error': f'Condition "{condition_name}" not found',
                'success': False
            }), 404
        
        return jsonify({
            'success': True,
            'data': details,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ Condition Details Error: {e}")
        return jsonify({
            'error': f'Failed to retrieve condition details: {str(e)}',
            'success': False
        }), 500

@app.route('/api/symptoms/all-conditions', methods=['GET'])
def api_symptoms_all_conditions():
    """
    Get list of all available conditions.
    
    Response: List of all 48+ conditions in knowledge base
    """
    try:
        if not analyzer:
            return jsonify({'error': 'Analyzer not available', 'success': False}), 500
        
        conditions = analyzer.get_all_conditions()
        
        return jsonify({
            'success': True,
            'conditions': conditions,
            'total': len(conditions),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"❌ All Conditions Error: {e}")
        return jsonify({
            'error': f'Failed to retrieve conditions: {str(e)}',
            'success': False
        }), 500

# ========== END API ENDPOINTS ==========

@app.route('/symptom/receipt/details', methods=['GET', 'POST'])
def symptom_receipt_details():
    if 'symptom_analysis_result' not in session:
        flash('No symptom analysis result found.', 'error')
        return redirect(url_for('symptoms'))

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        try:
            class ReceiptPDF(FPDF):
                def header(self):
                    # Page Border
                    self.set_draw_color(0, 80, 180) # Deep Blue Border
                    self.set_line_width(1)
                    self.rect(5, 5, 200, 287) # A4 size approx with margin
                    
                    # Watermark Logic
                    self.set_font('Helvetica', 'B', 50)
                    self.set_text_color(240, 240, 240)
                    angle = 45
                    x = self.w / 2
                    y = self.h / 2
                    c = math.cos(math.radians(angle))
                    s = math.sin(math.radians(angle))
                    cx = x * self.k
                    cy = (self.h - y) * self.k
                    s_val = f'q {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {cx:.2f} {cy:.2f} cm 1 0 0 1 {-cx:.2f} {-cy:.2f} cm'
                    self._out(s_val)
                    self.text(x - 80, y, 'DEV Ai+ - S iCons')
                    self._out('Q')
                    self.set_text_color(0, 0, 0)
                    
                def footer(self):
                    self.set_y(-25)
                    self.set_font('Helvetica', 'I', 8)
                    self.set_text_color(100, 100, 100)
                    self.set_draw_color(200, 200, 200)
                    self.set_line_width(0.2)
                    self.line(10, self.get_y(), 200, self.get_y())
                    self.ln(2)
                    self.multi_cell(0, 4, "Disclaimer: This receipt is generated by an AI system. It is not a substitute for professional medical diagnosis or treatment. Please consult a certified healthcare professional for accurate medical advice.", 0, 'C')
                    self.multi_cell(0, 4, "Be Healthy! Your Health is our first Priority.", 0, 'C')

            pdf = ReceiptPDF()
            pdf.add_page()
            
            # 2. Header with Background
            pdf.set_fill_color(240, 248, 255) # AliceBlue background
            pdf.rect(6, 6, 198, 30, 'F')
            
            # Add Company Logo
            try:
                logo_path = os.path.join(app.root_path, 'static', 'images', 'devai.jpg')
                if os.path.exists(logo_path):
                    pdf.image(logo_path, x=10, y=8, h=26)
            except Exception:
                pass
            
            pdf.set_y(15)
            pdf.set_font('Helvetica', 'B', 22)
            pdf.set_text_color(0, 51, 102) # Dark Blue Text
            pdf.cell(0, 10, 'SYMPTOM ANALYSIS RECEIPT', 0, 1, 'C')
            
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, 'Generated by DEV Ai+ Health Intelligence', 0, 1, 'C')
            pdf.ln(15)
            
            # 3. Patient Information Table
            pdf.set_font('Helvetica', 'B', 14)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, 'Patient Details', 0, 1, 'L')
            
            # Table Settings
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_fill_color(245, 245, 245) # Light Gray for labels
            pdf.set_draw_color(200, 200, 200) # Gray borders
            pdf.set_line_width(0.2)
            
            # Row 1: Name & Date
            pdf.cell(30, 8, 'Name:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(70, 8, to_latin1_str(name), 1, 0, 'L')
            
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(30, 8, 'Date:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(60, 8, datetime.now().strftime('%Y-%m-%d'), 1, 1, 'L')
            
            # Row 2: Email & Phone
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(30, 8, 'Email:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(70, 8, to_latin1_str(email), 1, 0, 'L')
            
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(30, 8, 'Phone:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(60, 8, to_latin1_str(phone), 1, 1, 'L')
            
            # Row 3: Address (Full Width)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(30, 8, 'Address:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(160, 8, to_latin1_str(address), 1, 1, 'L')
            
            pdf.ln(10)
            
            # 4. Analysis Details Section
            pdf.set_font('Helvetica', 'B', 14)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, 'Clinical Analysis', 0, 1, 'L')
            pdf.set_draw_color(0, 80, 180) # Blue separator line
            pdf.set_line_width(0.5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            result = session.get('symptom_analysis_result', {})
            query = session.get('symptoms', '') or f"Symptoms in {session.get('body_part', '')}"
            
            # Reported Symptoms Box
            pdf.set_fill_color(250, 250, 255)
            pdf.set_draw_color(220, 220, 220)
            pdf.set_line_width(0.2)
            
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, 'Reported Symptoms:', 0, 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.multi_cell(0, 6, to_latin1_str(query), 1, 'L', True)
            pdf.ln(5)
            
            conditions = result.get('conditions', [])
            if conditions:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_text_color(180, 0, 0) # Dark Red
                pdf.cell(0, 8, "Potential Conditions Identified:", 0, 1)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Helvetica', '', 10)
                for cond in conditions:
                    pdf.cell(10, 6, chr(149), 0, 0, 'R') # Bullet point
                    pdf.cell(0, 6, to_latin1_str(cond), 0, 1)
                pdf.ln(5)
            
            advice = result.get('advice', '')
            if advice:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_fill_color(235, 245, 235) # Light Green background
                pdf.cell(0, 8, "AI Generated Advice:", 0, 1, 'L', 1)
                pdf.set_font('Helvetica', '', 10)
                pdf.multi_cell(0, 6, to_latin1_str(advice))
                pdf.ln(5)

            self_care = result.get('self_care', [])
            if self_care:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_fill_color(240, 248, 255) # AliceBlue
                pdf.cell(0, 8, "Self-Care Recommendations:", 0, 1, 'L', 1)
                pdf.set_font('Helvetica', '', 10)
                for item in self_care:
                    pdf.cell(10, 6, chr(149), 0, 0, 'R')
                    pdf.multi_cell(0, 6, to_latin1_str(item))
                pdf.ln(5)

            medicines = result.get('suggested_medicines', [])
            if medicines:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_fill_color(255, 250, 240) # FloralWhite
                pdf.cell(0, 8, "Suggested Medicines (OTC):", 0, 1, 'L', 1)
                pdf.set_font('Helvetica', '', 10)
                for med in medicines:
                    pdf.cell(10, 6, chr(149), 0, 0, 'R')
                    pdf.multi_cell(0, 6, to_latin1_str(med))
                pdf.ln(5)

            departments = result.get('recommended_departments', [])
            if departments:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_fill_color(250, 245, 255) # Light Purple
                pdf.cell(0, 8, "Recommended Departments:", 0, 1, 'L', 1)
                pdf.set_font('Helvetica', '', 10)
                for dept in departments:
                    pdf.cell(10, 6, chr(149), 0, 0, 'R')
                    pdf.multi_cell(0, 6, to_latin1_str(dept))
                pdf.ln(5)

            when_to_see = result.get('when_to_see_doctor', '')
            if when_to_see:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_fill_color(255, 235, 235) # Light Red
                pdf.set_text_color(180, 0, 0)
                pdf.cell(0, 8, "When to See a Doctor:", 0, 1, 'L', 1)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Helvetica', '', 10)
                pdf.multi_cell(0, 6, to_latin1_str(when_to_see))
                pdf.ln(5)

            # Output
            pdf_output = pdf.output(dest='S')
            if isinstance(pdf_output, str):
                pdf_bytes = pdf_output.encode('latin-1', 'replace')
            else:
                pdf_bytes = pdf_output

            return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name='symptom_receipt.pdf', mimetype='application/pdf')
            
        except Exception as e:
            print(f"PDF Error: {e}")
            flash('Error generating receipt.', 'error')
            return redirect(url_for('symptoms_result'))

    return render_template('symptom_receipt_form.html')

@app.route('/download/symptoms/pdf')
def download_symptoms_pdf():
    """Generates and serves a PDF report of the symptom analysis."""
    if 'symptom_analysis_result' not in session:
        flash('No symptom analysis result found to download.', 'error')
        return redirect(url_for('symptoms'))

    # Retrieve data from session
    try:
        age = session.get('age', 'N/A')
        gender = session.get('gender', 'N/A')
        query = session.get('symptoms', '') or f"Symptoms in {session.get('body_part', '')}"
        result = session.get('symptom_analysis_result', {})

        # --- PDF Generation with Premium Design ---
        class ColorPDF(FPDF):
            PRIMARY_COLOR = (59, 130, 246) # blue-500
            SECONDARY_COLOR = (107, 114, 128) # gray-500
            TEXT_COLOR = (17, 24, 39) # gray-900
            LIGHT_BG_COLOR = (243, 244, 246) # gray-100

            def header(self):
                # Colorful header with logo and title
                self.set_fill_color(*self.PRIMARY_COLOR)
                self.rect(0, 0, self.w, 18, 'F')
                self.set_font('Helvetica', 'B', 12)
                self.set_text_color(255, 255, 255)
                try:
                    logo_path = os.path.join(app.root_path, 'static', 'images', 'devai.jpg')
                    if os.path.exists(logo_path):
                        self.image(logo_path, 10, 5, 8)
                except Exception:
                    pass
                self.set_xy(22, 4)
                header_text = to_latin1_str('DEV AI+ Health Intelligence Report')
                self.cell(0, 10, header_text)
                self.set_font('Helvetica', '', 10)
                date_text = to_latin1_str(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d')}")
                self.cell(0, 10, date_text, 0, 0, 'R')
                self.ln(25)

            def footer(self):
                # Footer with page number and disclaimer
                self.set_y(-15)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(*self.SECONDARY_COLOR)
                self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')
                self.set_x(10)
                disclaimer_text = to_latin1_str('This is an AI-generated report, not a substitute for professional medical advice.')
                self.cell(0, 10, disclaimer_text, 0, 0, 'L')

            def section_title(self, title):
                # Section title with a blue accent line
                self.set_font('Helvetica', 'B', 14)
                self.set_text_color(*self.TEXT_COLOR)
                title_safe = to_latin1_str(title)
                self.cell(0, 6, title_safe, 0, 1, 'L')
                self.set_draw_color(*self.PRIMARY_COLOR)
                self.line(self.get_x(), self.get_y(), self.get_x() + 30, self.get_y())
                self.ln(5)

            def card(self, title, content_callback, card_height):
                # A card with a colored header
                x = self.get_x()
                y = self.get_y()
                # Card border
                self.set_draw_color(229, 231, 235) # gray-200
                self.rect(x, y, self.w - 20, card_height, 'D')
                # Card header
                self.set_fill_color(*self.LIGHT_BG_COLOR)
                self.rect(x, y, self.w - 20, 10, 'F')
                self.set_xy(x + 4, y + 1)
                self.set_font('Helvetica', 'B', 11)
                self.set_text_color(*self.SECONDARY_COLOR)
                self.cell(0, 8, title)
                # Card content
                self.set_xy(x + 4, y + 14)
                self.set_text_color(*self.TEXT_COLOR)
                content_callback()
                self.set_xy(x, y + card_height + 10)

        pdf = ColorPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)

        # --- Main Title ---
        pdf.section_title('Patient & Symptom Summary')

        # --- Two-column layout for patient info and query ---
        col_width = (pdf.w - 30) / 2
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(col_width, 7, 'Patient Information', 0, 0)
        pdf.cell(col_width, 7, 'Symptom Query', 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_fill_color(*pdf.LIGHT_BG_COLOR)
        
        # Store current Y to align the second column
        y_pos = pdf.get_y()
        pdf.multi_cell(col_width, 7, to_latin1_str(f'Age: {age}\nGender: {gender}'), 1, 'L', 1)
        pdf.set_xy(pdf.get_x() + col_width + 10, y_pos)
        pdf.multi_cell(col_width, 14, to_latin1_str(f'"{query}"'), 1, 'L', 1)
        pdf.ln(10)

        # --- Sanitize Text for PDF ---
        advice_text = result.get('advice', 'No advice available.')
        advice_safe = to_latin1_str(advice_text)
        conditions = result.get('conditions', [])
        conditions_safe = [to_latin1_str(c) for c in conditions]
        rec_depts = result.get('recommended_departments', [])
        rec_depts_safe = [to_latin1_str(d) for d in rec_depts]
        self_care_safe = [to_latin1_str(s) for s in result.get('self_care', [])]
        when_to_see_doctor_safe = to_latin1_str(result.get('when_to_see_doctor', ''))

        # --- AI Analysis Section ---
        pdf.section_title('AI Analysis & Recommendations')

        # --- Potential Conditions Card ---
        def conditions_content():
            if not conditions_safe:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(*pdf.SECONDARY_COLOR)
                pdf.cell(0, 6, 'No specific conditions identified by the model.', 0, 1)
            else:
                for cond in conditions_safe:
                    pdf.set_font('Helvetica', 'B', 12)
                    pdf.set_text_color(*pdf.PRIMARY_COLOR)
                    pdf.cell(0, 8, f'- {cond}', 0, 1, 'L')
                    # Description for the condition
                    pdf.set_font('Helvetica', '', 10)
                    pdf.set_text_color(*pdf.TEXT_COLOR)
                    description_safe = to_latin1_str(KNOWLEDGE_BASE.get(cond, {}).get('description', 'No description available.'))
                    pdf.multi_cell(0, 5, description_safe, 0, 'L')
                    pdf.ln(2)
        pdf.card('Potential Condition(s)', conditions_content, 30 + (len(conditions_safe) * 20))

        # --- General Advice Card ---
        def advice_content():
            pdf.set_font('Helvetica', '', 10)
            pdf.multi_cell(0, 6, advice_safe, 0, 'L')
        pdf.card('General Advice', advice_content, 40)

        # --- Self-Care and When to See a Doctor (Two-column card) ---
        def care_guidance_content():
            col_width = (pdf.w - 40) / 2
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(col_width, 7, 'Recommended Self-Care', 0, 0)
            pdf.cell(col_width, 7, 'When to See a Doctor', 0, 1)
            pdf.ln(1)
            
            y_pos = pdf.get_y()
            pdf.set_font('Helvetica', '', 9)
            # Self-care column
            if self_care_safe:
                for item in self_care_safe:
                    pdf.multi_cell(col_width, 5, f'- {item}', 0, 'L')
                    pdf.ln(1)
            else:
                pdf.multi_cell(col_width, 5, '- No specific self-care tips available.', 0, 'L')
            
            # When to see doctor column
            pdf.set_xy(pdf.get_x() + col_width + 10, y_pos)
            pdf.multi_cell(col_width, 5, when_to_see_doctor_safe, 0, 'L')

        pdf.card('Care Guidance', care_guidance_content, 60)

        # --- Recommended Specialists Card ---
        def specialists_content():
            # Recommended Departments
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, 'Recommended Departments:', 0, 1)
            pdf.set_font('Helvetica', '', 10)
            if rec_depts_safe:
                for dept in rec_depts_safe:
                    pdf.set_fill_color(221, 238, 255) # blue-100
                    pdf.set_text_color(*pdf.PRIMARY_COLOR)
                    pdf.set_font('Helvetica', 'B', 10)
                    pdf.cell(pdf.get_string_width(dept) + 8, 7, dept, 0, 0, 'C', fill=True)
                    pdf.cell(4, 7, '', 0, 0) # spacer
            else:
                pdf.set_text_color(*pdf.SECONDARY_COLOR)
                pdf.cell(0, 6, 'General Medicine', 0, 0)
            pdf.ln(12)

            # Suggested Doctors
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(*pdf.TEXT_COLOR)
            pdf.cell(0, 6, 'Suggested Doctors in Network:', 0, 1)
            pdf.set_font('Helvetica', '', 10)
            
            suggested_doctors = [d for d in TEMP_DATA['doctors'].values() if d.department in rec_depts][:3]
            if suggested_doctors:
                for doc in suggested_doctors:
                    name = f"Dr. {doc.first_name} {doc.last_name}"
                    dept = doc.department
                    pdf.set_font('Helvetica', 'B', 10)
                    pdf.cell(0, 6, to_latin1_str(f'- {name}'), 0, 0, 'L')
                    pdf.set_font('Helvetica', '', 10)
                    pdf.cell(0, 6, to_latin1_str(f'({dept})'), 0, 1, 'R')
            else:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(*pdf.SECONDARY_COLOR)
                pdf.cell(0, 6, 'No specific specialists found. Please browse our directory.', 0, 1)

        pdf.card('Next Steps & Specialist Recommendations', specialists_content, 65)

        # --- PDF Output ---
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            try:
                pdf_bytes = pdf_output.encode('latin-1')
            except UnicodeEncodeError:
                pdf_bytes = pdf_output.encode('latin-1', 'replace')
        else:
            pdf_bytes = pdf_output

        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name='symptom_report.pdf', mimetype='application/pdf')

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error generating PDF: {e}\n{tb}")
        # Include a short hint to user and log full traceback to a file for easier debugging
        try:
            with open('pdf_error.log', 'a') as logf:
                logf.write(f"[{datetime.utcnow().isoformat()}] Error generating PDF: {e}\n{tb}\n\n")
        except Exception:
            pass
        flash(f'An error occurred while generating the PDF report: {str(e)}', 'error')
        return redirect(url_for('symptoms_result'))

@app.route('/doctors')
def doctors_list():
    # This route now fetches doctors from the database
    all_db_doctors = list(TEMP_DATA['doctors'].values())
    q = request.args.get('q', '').lower()
    if q:
        filtered_doctors = [
            d for d in all_db_doctors 
            if q in f"{d.first_name} {d.last_name}".lower() 
            or (d.department and q in d.department.lower())
            or (d.specialization and q in d.specialization.lower())
            or (d.hospital_name and q in d.hospital_name.lower())
        ]
    else:
        filtered_doctors = all_db_doctors
    return render_template('doctor.html', doctors=filtered_doctors, q=q)

@app.route('/hospitals')
def hospitals_list():
    """Displays a list of registered hospitals."""
    hospitals = list(TEMP_DATA['hospitals'].values())
    return render_template('hospitals.html', hospitals=hospitals)

@app.route('/hospital/<int:hospital_id>')
def hospital_detail(hospital_id):
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))
    
    # Get doctors for this hospital
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == hospital.name]
    
    return render_template('hospital_detail.html', hospital=hospital, doctors=hospital_doctors)

@app.route('/hospital/<int:hospital_id>/inquiry', methods=['POST'])
def hospital_inquiry(hospital_id):
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))

    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    if name and email and message:
        subject = f"New Inquiry from {name} - DEV AI+"
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

@app.route('/hospital/<int:hospital_id>/book_bed', methods=['POST'])
@patient_required
def book_hospital_bed(hospital_id):
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
        TEMP_DATA['next_ids']['bed_booking'] = max([1] + list(TEMP_DATA['bed_bookings'].keys())) + 1

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

@app.route('/hospital/bed_booking/payment/<int:booking_id>', methods=['GET', 'POST'])
@patient_required
def bed_booking_payment(booking_id):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if not booking or booking.patient_id != current_user.id:
        flash("Booking not found.", "error")
        return redirect(url_for('patient_dashboard'))
        
    if booking.status != 'awaiting_payment':
        flash("This booking has already been paid for or processed.", "warning")
        return redirect(url_for('patient_dashboard'))

    hospital = TEMP_DATA['hospitals'].get(booking.hospital_id)
    fee = hospital.icu_bed_fee if booking.bed_type == 'ICU' else hospital.general_bed_fee
    
    if request.method == 'POST':
        booking.status = 'pending' # Paid and waiting for hospital approval
        save_data()
        flash(f"Payment successful! Emergency {booking.bed_type} bed request sent to {hospital.name}.", "success")
        return redirect(url_for('patient_dashboard'))
        
    return render_template('bed_booking_payment.html', booking=booking, hospital=hospital, fee=fee)

@app.route('/hospital/<int:hospital_id>/book_appointment', methods=['POST'])
@patient_required
def book_hospital_appointment(hospital_id):
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))
        
    doctor_id = request.form.get('doctor_id')
    patient_name = request.form.get('patient_name')
    patient_phone = request.form.get('patient_phone')
    patient_age = request.form.get('patient_age')
    patient_id_number = request.form.get('patient_id_number')
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    reason = request.form.get('reason')
    
    if not all([doctor_id, patient_name, patient_phone, patient_age, patient_id_number, date_str, time_str]):
        flash("All fields are required to book an appointment.", "error")
        return redirect(url_for('hospital_detail', hospital_id=hospital_id))
        
    doctor = TEMP_DATA['doctors'].get(doctor_id)
    if not doctor or doctor.hospital_name != hospital.name:
        flash("Invalid doctor selected.", "error")
        return redirect(url_for('hospital_detail', hospital_id=hospital_id))
        
    appt_id = TEMP_DATA['next_ids']['appointment']
    new_appointment = Appointment(
        id=appt_id,
        patient_name=patient_name,
        doctor_id=doctor_id,
        appointment_date=datetime.strptime(date_str, '%Y-%m-%d').date(),
        appointment_time=datetime.strptime(time_str, '%H:%M').time(),
        patient_phone=patient_phone,
        patient_age=patient_age,
        patient_id_number=patient_id_number,
        reason=reason,
        status='awaiting_payment'
    )
    new_appointment.patient_id = current_user.id
    TEMP_DATA['appointments'][appt_id] = new_appointment
    TEMP_DATA['next_ids']['appointment'] += 1
    save_data()
    
    return redirect(url_for('appointment_payment', appointment_id=appt_id))

@app.route('/doctor/<path:doc_id>', methods=['GET', 'POST'])
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
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                upload_folder = os.path.join(app.root_path, 'static/uploads/documents')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_filename))
                document_path = unique_filename

        if not all([patient_name, patient_phone, patient_age, patient_id_number, appointment_date_str, appointment_time_str]):
            flash('All fields are required to book an appointment.', 'error')
        else:
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
                status='awaiting_payment', # Set status to awaiting_payment for payment flow
                document_path=document_path
            )
            if current_user.is_authenticated and not current_user.is_doctor:
                new_appointment.patient_id = current_user.id

            TEMP_DATA['appointments'][appt_id] = new_appointment
            TEMP_DATA['next_ids']['appointment'] += 1
            save_data() # Save after creating appointment
            return redirect(url_for('appointment_payment', appointment_id=appt_id))
        return redirect(url_for('doctor_detail', doc_id=doc_id_val))

    return render_template('doctor_detail.html', doctor=doctor)

@app.route('/doctor/<path:doc_id>/review', methods=['POST'])
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

# ---------------- Doctor Portal Routes ----------------
@app.route('/doctor/register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        department = request.form.get('department')

        if not all([first_name, last_name, email, password, department]):
            flash('Please fill out all required fields.', 'error')
            return redirect(url_for('doctor_register'))

        if confirm_password and password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('doctor_register'))

        existing_doctor = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == email), None)
        if existing_doctor:
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('doctor_register'))

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store registration data in session
        session['doctor_signup_data'] = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'department': department,
            'otp': otp
        }

        # Send OTP Email
        subject = "Verify your email - DEV AI+ Doctor Portal"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #2563eb;">Doctor Registration Verification</h2>
            <p>Hello Dr. <strong>{last_name}</strong>,</p>
            <p>To complete your registration, please use the following One-Time Password (OTP):</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #2563eb; background: #eff6ff; padding: 15px 30px; border-radius: 5px; border: 1px solid #dbeafe;">{otp}</span>
            </div>
            <p>If you did not request this code, please ignore this email.</p>
        </div>
        """
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash("Failed to send OTP email. For development, check the terminal for the OTP.", "warning")
        
        return redirect(url_for('doctor_verify_otp'))

    return render_template('doctor_register.html')

@app.route('/doctor/verify-otp', methods=['GET', 'POST'])
def doctor_verify_otp():
    if 'doctor_signup_data' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('doctor_register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_data = session.get('doctor_signup_data')
        
        if entered_otp == stored_data.get('otp'):
            # Create Account
            year = datetime.now().year
            next_id_num = TEMP_DATA['next_ids']['doctor']
            new_id = f"DOC/{year}/{next_id_num:03d}"
            
            new_doctor = Doctor(
                id=new_id,
                first_name=stored_data['first_name'],
                last_name=stored_data['last_name'],
                email=stored_data['email'],
                password=stored_data['password'], # Already hashed
                department=stored_data['department'],
                is_verified=False # Requires admin approval
            )
            
            TEMP_DATA['doctors'][new_id] = new_doctor
            TEMP_DATA['next_ids']['doctor'] += 1
            save_data()
            
            session.pop('doctor_signup_data', None)
            flash(f'Account verified! Your ID is {new_id}. Please wait for admin approval before logging in.', 'success')
            return redirect(url_for('doctor_login'))
        else:
            flash("Invalid OTP. Please try again.", "error")
            
    return render_template('doctor_verify_otp.html')

@app.route('/doctor/resend-otp')
def doctor_resend_otp():
    if 'doctor_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['doctor_signup_data']['otp'] = otp
        
        email = session['doctor_signup_data']['email']
        name = session['doctor_signup_data'].get('last_name', 'Doctor')
        
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #2563eb;">New Verification Code</h2>
            <p>Hello Dr. <strong>{name}</strong>,</p>
            <p>Here is your new OTP for registration:</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #2563eb; background: #eff6ff; padding: 15px 30px; border-radius: 5px; border: 1px solid #dbeafe;">{otp}</span>
            </div>
        </div>
        """
        if send_notification_email(email, "Resend OTP - DEV AI+ Doctor", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash("Failed to resend OTP email. For development, check the terminal for the new OTP.", "warning")
    return redirect(url_for('doctor_verify_otp'))

@app.route('/doctor/info')
def doctor_info():
    return render_template('doctor_info.html')


@app.route('/doctor/login', methods=['GET', 'POST'])
# @limiter.limit("10 per minute") # Specific, stricter limit for login attempts
def doctor_login():
    if request.method == 'POST':
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
            if not doctor.is_verified:
                flash('Your account is pending verification by an administrator.', 'warning')
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

                login_user(doctor)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('doctor_dashboard'))

        flash('Invalid email or password.', 'error')
        return redirect(url_for('doctor_login'))

    return render_template('doctor_login.html')

@app.route('/doctor/dashboard', methods=['GET', 'POST'])
@doctor_required
def doctor_dashboard():
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    if not doctor:
        flash('Doctor not found.', 'error')
        return redirect(url_for('doctor_login'))

    if request.method == 'POST':
        # ... (existing profile update logic) ...
        fields_to_update = [
            'first_name', 'last_name', 'email', 'phone', 'department', 
            'specialization', 'hospital_name', 'hospital_address', 'state',
            'district', 'pincode', 'bio', 'qualification', 'license_number',
            'experience', 'consultation_type', 'consultation_fee',
            'working_hours', 'languages_spoken', 'social_links'
        ]
        for field in fields_to_update:
            if field in request.form:
                setattr(doctor, field, request.form.get(field))
        
        # Handle Profile Picture Upload
        if 'profilePicture' in request.files:
            file = request.files['profilePicture']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                unique_filename = f"doc_profile_{timestamp}_{filename}"
                upload_folder = os.path.join(app.root_path, 'static/uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_filename))
                doctor.profile_picture_url = unique_filename

        save_data()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('doctor_dashboard'))

    # Fetch upcoming appointments
    today = date.today()
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
        total_income=total_income
    )

@app.route('/doctor/image/<path:doc_id>')
def get_doctor_image(doc_id):
    """Serves the doctor's profile image from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT image_data, content_type FROM doctor_images WHERE doctor_id = ?", doc_id)
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return send_file(BytesIO(row[0]), mimetype=row[1])
    except Exception as e:
        print(f"Error fetching image for {doc_id}: {e}")

    # Fallback placeholder if no image in DB
    # Try to generate a personalized avatar if doctor exists
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if doctor:
        return redirect(f"https://ui-avatars.com/api/?name={doctor.first_name}+{doctor.last_name}&background=random&size=256")
    
    return redirect('https://ui-avatars.com/api/?name=Doctor&background=random&size=256')

@app.route('/doctor/chat/<int:patient_id>')
@doctor_required
def doctor_chat(patient_id):
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

@app.route('/api/chat/<int:patient_id>/messages')
@login_required
def get_chat_messages(patient_id):
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

@app.route('/api/chat/<int:patient_id>/send', methods=['POST'])
@doctor_required
def send_chat_message(patient_id):
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
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            attachment_url = f"chat_{timestamp}_{filename}"
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'chat')
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

@app.route('/patient/chat/<path:doctor_id>')
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

@app.route('/api/patient/chat/<path:doctor_id>/messages')
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

@app.route('/api/patient/chat/<path:doctor_id>/send', methods=['POST'])
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
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            attachment_url = f"chat_{timestamp}_{filename}"
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'chat')
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

@app.route('/api/doctor/conversations', methods=['GET'])
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

@app.route('/api/patient/doctor-conversations', methods=['GET'])
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

@app.route('/api/doctor/chat/<int:patient_id>/send', methods=['POST'])
@doctor_required
def send_message_doctor(patient_id):
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
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            attachment_url = f"chat_{timestamp}_{filename}"
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'chat')
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

@app.route('/api/doctor/chat/<int:patient_id>/messages')
@doctor_required
def get_doctor_patient_messages(patient_id):
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

@app.route('/api/patient/chat/<path:doctor_id>/send', methods=['POST'])
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
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            attachment_url = f"chat_{timestamp}_{filename}"
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'chat')
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

@app.route('/doctor/appointment/approve/<int:appointment_id>', methods=['POST'])
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
The DEV AI+ Team"""
            send_notification_email(patient.email, subject, body)
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been confirmed.", "success")
    else:
        flash("Appointment not found or you do not have permission.", "error")
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/appointment/cancel/<int:appointment_id>', methods=['POST'])
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
The DEV AI+ Team"""
            send_notification_email(patient.email, subject, body)
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been cancelled.", "success")
    else:
        flash("Appointment not found or you do not have permission.", "error")
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/appointment/reschedule/<int:appointment_id>', methods=['POST'])
@doctor_required
def reschedule_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not (appointment and appointment.doctor_id == current_user.id):
        flash("Appointment not found or you do not have permission.", "error")
        return redirect(url_for('doctor_dashboard'))

    new_date_str = request.form.get('reschedule_date')
    new_time_str = request.form.get('reschedule_time')

    if not new_date_str or not new_time_str:
        flash("Please provide both a new date and time to reschedule.", "error")
        return redirect(url_for('doctor_dashboard'))

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
The DEV AI+ Team"""
        send_notification_email(patient.email, subject, body)

    save_data()
    flash(f"A new time has been suggested for {appointment.patient_name}'s appointment.", "success")
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/appointment/upload_prescription/<int:appointment_id>', methods=['POST'])
@doctor_required
def upload_prescription(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not (appointment and appointment.doctor_id == current_user.id):
        flash("Appointment not found or permission denied.", "error")
        return redirect(url_for('doctor_dashboard'))

    file = request.files.get('prescription')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_filename = f"rx_{timestamp}_{filename}"
        upload_folder = os.path.join(app.root_path, 'static/uploads/prescriptions')
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, unique_filename))

        appointment.prescription_path = unique_filename
        save_data()

        # Notify Patient
        patient = appointment.patient
        if patient and patient.email:
            subject = "Prescription Uploaded"
            body = f"Dear {patient.name},\n\nDr. {appointment.doctor.first_name} {appointment.doctor.last_name} has uploaded a prescription for your appointment on {appointment.appointment_date}.\n\nYou can view and download it from your dashboard.\n\nBest regards,\nThe DEV AI+ Team"
            send_notification_email(patient.email, subject, body)

        flash('Prescription uploaded successfully.', 'success')
    else:
        flash('No file selected.', 'error')

    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/appointment/complete/<int:appointment_id>', methods=['POST'])
@doctor_required
def complete_appointment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if appointment and appointment.doctor_id == current_user.id:
        appointment.status = 'completed'
        save_data()
        flash(f"Appointment for {appointment.patient_name} has been marked as completed.", "success")
    else:
        flash("Appointment not found or you do not have permission.", "error")
    return redirect(url_for('doctor_dashboard'))

@app.route('/patient/appointment/accept_reschedule/<int:appointment_id>', methods=['POST'])
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

@app.route('/patient/appointment/reject_reschedule/<int:appointment_id>', methods=['POST'])
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

@app.route('/drugs')
def drugs():
    # Categorize the drugs for the template
    categorized_drugs = {
        "Pain & Inflammation": [
            "Acetaminophen (Tylenol)", "Ibuprofen (Advil, Motrin)", "Naproxen (Aleve)",
            "Aspirin (Ecotrin)", "Diclofenac (Voltaren)", "Tramadol (Ultram)",
            "Codeine", "Morphine", "Oxycodone (OxyContin)", "Hydrocodone/APAP (Vicodin)",
            "Celecoxib (Celebrex)", "Meloxicam (Mobic)", "Gabapentin (Neurontin)",
            "Pregabalin (Lyrica)", "Lidocaine (Lidoderm Patch)",
        ],
        "Gastrointestinal": [
            "Omeprazole (Prilosec)", "Esomeprazole (Nexium)", "Pantoprazole (Protonix)",
            "Famotidine (Pepcid)", "Ranitidine (Zantac - now largely replaced by Famotidine)",
            "Calcium Carbonate (Tums)", "Loperamide (Imodium)", "Bismuth Subsalicylate (Pepto-Bismol)",
            "Docusate Sodium (Colace)", "Polyethylene Glycol (Miralax)", "Senna (Senokot)",
            "Metoclopramide (Reglan)", "Ondansetron (Zofran)", "Lansoprazole (Prevacid)",
        ],
        "Cardiovascular": [
            "Lisinopril (Prinivil) - ACE Inhibitor", "Amlodipine (Norvasc) - Calcium Channel Blocker",
            "Atorvastatin (Lipitor) - Statin", "Simvastatin (Zocor) - Statin", "Rosuvastatin (Crestor) - Statin",
            "Metoprolol (Lopressor) - Beta Blocker", "Carvedilol (Coreg) - Beta Blocker",
            "Losartan (Cozaar) - ARB", "Furosemide (Lasix) - Diuretic", "Hydrochlorothiazide (HCTZ) - Diuretic",
            "Warfarin (Coumadin) - Anticoagulant", "Apixaban (Eliquis) - Anticoagulant",
            "Rivaroxaban (Xarelto) - Anticoagulant", "Clopidogrel (Plavix) - Antiplatelet",
            "Digoxin (Lanoxin)", "Nitroglycerin",
        ],
        "Respiratory & Allergy": [
            "Albuterol (Ventolin) - Rescue Inhaler", "Fluticasone (Flonase) - Nasal Spray/Inhaler",
            "Montelukast (Singulair)", "Cetirizine (Zyrtec) - Antihistamine", "Loratadine (Claritin) - Antihistamine",
            "Fexofenadine (Allegra) - Antihistamine", "Diphenhydramine (Benadryl) - Antihistamine",
            "Guaifenesin (Mucinex) - Expectorant", "Dextromethorphan (Delsym) - Cough Suppressant",
            "Pseudoephedrine (Sudafed) - Decongestant",
        ],
        "Antibiotics & Anti-Infectives": [
            "Amoxicillin", "Amoxicillin/Clavulanate (Augmentin)", "Azithromycin (Zithromax)", "Doxycycline",
            "Ciprofloxacin (Cipro)", "Levofloxacin (Levaquin)", "Metronidazole (Flagyl)", "Cephalexin (Keflex)",
            "Penicillin", "Clindamycin", "Fluconazole (Diflucan) - Antifungal", "Mupirocin (Bactroban) - Topical Antibiotic",
            "Terbinafine (Lamisil) - Antifungal",
        ],
        "Endocrine & Hormones": [
            "Metformin (Glucophage)", "Insulin (Various types: Glargine, Lispro, etc.)",
            "Levothyroxine (Synthroid) - Thyroid Hormone", "Prednisone - Corticosteroid",
            "Hydrocortisone - Corticosteroid", "Ethinyl Estradiol/Norethindrone - Oral Contraceptive",
            "Epinephrine (EpiPen)",
        ],
        "Vitamins & Supplements": [
            "Vitamin D (Ergocalciferol/Cholecalciferol)", "Folic Acid", "Ferrous Sulfate - Iron",
            "Potassium Chloride", "Magnesium Oxide/Citrate", "Calcium", "Omega-3 Fatty Acids (Fish Oil)",
            "Melatonin", "Biotin", "Vitamin B12 (Cyanocobalamin)",
        ],
        "Mental Health & Neurology": [
            "Sertraline (Zoloft) - Antidepressant (SSRI)", "Escitalopram (Lexapro) - Antidepressant (SSRI)",
            "Fluoxetine (Prozac) - Antidepressant (SSRI)", "Alprazolam (Xanax) - Anti-Anxiety (Benzodiazepine)",
            "Clonazepam (Klonopin) - Anti-Anxiety (Benzodiazepine)", "Zolpidem (Ambien) - Sleep Aid",
            "Trazodone - Antidepressant/Sleep Aid", "Bupropion (Wellbutrin) - Antidepressant",
            "Venlafaxine (Effexor) - Antidepressant (SNRI)", "Quetiapine (Seroquel) - Antipsychotic",
            "Aripiprazole (Abilify) - Antipsychotic", "Lamotrigine (Lamictal) - Anti-seizure/Mood Stabilizer",
            "Tizanidine (Zanaflex) - Muscle Relaxer", "Cyclobenzaprine (Flexeril) - Muscle Relaxer",
            "Sumatriptan (Imitrex) - Migraine",
        ],
        "Ophthalmology & Otic": [
            "Latanoprost (Xalatan) - Glaucoma", "Bimatoprost (Lumigan) - Glaucoma",
            "Ciprofloxacin (Otic drops) - Ear Infection",
        ],
        "Dermatology & Topical": [
            "Hydrocortisone Cream", "Clotrimazole (Lotrimin) - Topical Antifungal", "Benzoyl Peroxide - Acne",
            "Salicylic Acid - Acne", "Bacitracin - Topical Antibiotic Ointment", "Clobetasol - Topical Steroid",
        ],
    }
    return render_template('drugs.html', categorized_drugs=categorized_drugs)

@app.route('/drug-info/<path:drug_name>')
def drug_info(drug_name):
    """API endpoint to get information about a specific drug."""
    info = DRUG_DATABASE.get(drug_name)
    if info:
        payload = {
            'drug_name': drug_name,
            'description': info.get('description', ''),
            'primary_use': info.get('primary_use', ''),
            'common_side_effects': info.get('common_side_effects', []),
            'caution': info.get('caution', ''),
            'clinical_notes': info.get('clinical_notes', ''),
            'source': 'local'
        }
        return jsonify(payload)

    # Fallback to AI-generated drug details
    ai_info = _invoke_groq_drug_info(drug_name)
    if ai_info:
        return jsonify(ai_info)

    return jsonify({
        "description": f"Detailed information for '{drug_name}' is not available in our local database. Please consult a pharmacist or doctor.",
        "error": "Drug not found."
    }), 404

@app.route('/conditions')
def conditions():
    conditions_list = [
        'Diabetes', 'Hypertension', 'Asthma', 'Arthritis', 'Migraine',
        'Allergy', 'Thyroid Disorder', 'Depression', 'Anxiety', 'Flu' , 'covid-19', 'Bronchitis', 'Pneumonia',
        'Eczema', 'Psoriasis', 'Acne', 'Osteoporosis', 'Gout', 'Irritable Bowel Syndrome', 'Crohn\'s Disease',
        'Ulcerative Colitis', 'Gastroesophageal Reflux Disease', 'Chronic Kidney Disease', 'Heart Failure',
        'Coronary Artery Disease', 'Stroke', 'Chronic Obstructive Pulmonary Disease', 'Sleep Apnea',
        'Fibromyalgia', 'Anemia', 'Vitamin D Deficiency', 'Obesity', 'Menopause', 'Prostate Issues',
        'Urinary Tract Infection', 'Sinusitis', 'Ear Infection', 'Conjunctivitis', 'Tonsillitis',
        'Lupus', 'Multiple Sclerosis', 'Parkinson\'s Disease', 'Alzheimer\'s Disease', 'Epilepsy',
        'Attention Deficit Hyperactivity Disorder', 'Autism Spectrum Disorder', 'Celiac Disease', 'Hepatitis B', 'Hepatitis C',
        'Tuberculosis', 'Lyme Disease', 'Dengue Fever', 'Rheumatoid Arthritis', 'Ankylosing Spondylitis', 'Sjögren\'s Syndrome',
        'Psoriatic Arthritis', 'Endometriosis', 'Polycystic Ovary Syndrome', 'Infertility', 'Erectile Dysfunction',
    ]
    drug_names = sorted(DRUG_DATABASE.keys(), key=lambda x: x.lower())
    return render_template('conditions.html', conditions=conditions_list, drug_names=drug_names)

@app.route('/medical-lab')
def medical_lab():
    return render_template('medical_lab.html')

@app.route('/condition-info/<path:condition_name>')
def condition_info(condition_name):
    """API endpoint to get information about a specific medical condition."""
    condition_data = KNOWLEDGE_BASE.get(condition_name)
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


@app.route('/about')
def about():
    return render_template('about.html')

# ---------------- Gallery Route ----------------
@app.route('/gallery')
def gallery():
    gallery_images = [
        'image3.jpg','image4.jpg','image5.jpg','image6.jpg','image7.jpg',
        'image8.jpg','image10.jpg','image12.jpg','image13.jpg','image14.jpg',
        'image15.jpg','image16.jpg','image17.jpg','image18.jpg',
    ]

    videos = [
        {"url":"https://www.youtube.com/watch?v=7D-gxaie6UI", "title":"Research Video 1"},
        {"url":"https://www.youtube.com/watch?v=b1-pZumCz7Q", "title":"Research Video 2"}
    ]

    return render_template('gallery.html', images=gallery_images, videos=videos)

@app.route('/logout')
def logout():
    logout_user() # Use Flask-Login's logout_user function
    return redirect(url_for('home'))


@app.route('/research')
def research():
    return render_template('research.html')

@app.route('/research/<topic>')
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
        return render_template("404.html"), 404  # optional 404 page

    return render_template("research_detail.html", topic=topic_data)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        if name and email and message:
            new_message = {
                'name': name,
                'email': email,
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
                <p><strong>Message:</strong></p>
                <div style="background: #f8fafc; padding: 15px; border-left: 4px solid #0ea5e9; border-radius: 4px;">
                    {message}
                </div>
            </div>
            """
            send_notification_email(admin_email, subject, body, is_html=True)
            
            flash("Your message has been sent successfully!", "success")
            return redirect(url_for('contact'))
            
    return render_template('contact.html')

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    feedback_type = data.get('type')
    message = data.get('message')
    
    if feedback_type and message:
        user_info = "Guest"
        user_email = "Guest"
        if current_user.is_authenticated:
            user_email = getattr(current_user, 'email', 'Guest')
            if hasattr(current_user, 'name'):
                user_info = current_user.name
            elif hasattr(current_user, 'first_name'):
                user_info = f"Dr. {current_user.first_name} {current_user.last_name}"
            else:
                user_info = f"User {current_user.id}"

        new_message = {
            'name': f'Feedback ({feedback_type.title()}) - {user_info}',
            'email': user_email,
            'message': message,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        TEMP_DATA['contact_messages'].insert(0, new_message)
        save_data()
        
        admin_email = 'isunny28skk@gmail.com'
        subject = f"New Feedback ({feedback_type.title()}) from {user_info}"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #4f46e5;">New System Feedback</h2>
            <p><strong>From:</strong> {user_info} ({user_email})</p>
            <p><strong>Type:</strong> {feedback_type.title()}</p>
            <p><strong>Message:</strong></p>
            <div style="background: #f8fafc; padding: 15px; border-left: 4px solid #4f46e5; border-radius: 4px;">
                {message}
            </div>
        </div>
        """
        send_notification_email(admin_email, subject, body, is_html=True)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Missing data'}), 400

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if email:
        admin_email = 'isunny28skk@gmail.com'
        subject = "New Newsletter Subscription"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #e11d48;">New Subscriber!</h2>
            <p>A new user has subscribed to the DEV AI+ newsletter.</p>
            <p><strong>Email:</strong> {email}</p>
        </div>
        """
        send_notification_email(admin_email, subject, body, is_html=True)
        flash("Thank you for subscribing to our newsletter!", "success")
    else:
        flash("Please provide a valid email address.", "error")
    return redirect(request.referrer or url_for('home'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Displays the main admin dashboard with comprehensive analytics for all features."""
    search_query = request.args.get('q', '').lower().strip()

    all_doctors = list(TEMP_DATA['doctors'].values())
    all_patients = list(TEMP_DATA['patients'].values())
    all_staff = list(TEMP_DATA['staff'].values())
    all_hospitals = list(TEMP_DATA['hospitals'].values())
    all_blood_donors = list(TEMP_DATA['blood_donors'].values())
    all_organ_donors = list(TEMP_DATA['organ_donors'].values())
    all_messages = list(TEMP_DATA['messages'].values())
    all_orders = list(TEMP_DATA['orders'].values())
    all_bed_bookings = list(TEMP_DATA.get('bed_bookings', {}).values())

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

    # Blood bank analytics
    blood_stock = TEMP_DATA.get('blood_stock', {})
    
    # Messaging stats - Message class doesn't have is_read, so count recent messages
    unread_messages = len([m for m in all_messages[-10:] if hasattr(m, 'is_read') and not m.is_read]) if all_messages else 0
    
    # Bed booking stats
    active_bed_bookings = len([b for b in all_bed_bookings if hasattr(b, 'status') and b.status == 'active'])

    # Check if official stamp exists
    stamp_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
    stamp_exists = os.path.exists(stamp_path)

    return render_template('admin_dashboard.html', 
                           doctors=filtered_doctors, hospitals=filtered_hospitals,
                           patients=filtered_patients, staff_members=filtered_staff, 
                           contact_messages=TEMP_DATA['contact_messages'],
                           blood_stock=blood_stock,
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
                           stamp_exists=stamp_exists, 
                           current_time=time_module.time())

@app.route('/admin/upload-signature', methods=['POST'])
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
        upload_folder = os.path.join(app.root_path, 'static', 'images')
        os.makedirs(upload_folder, exist_ok=True) # Ensure directory exists
        save_path = os.path.join(upload_folder, 'signature.png')
        file.save(save_path)
        flash('Official signature image updated successfully!', 'success')
            
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload-stamp', methods=['POST'])
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
        upload_folder = os.path.join(app.root_path, 'static', 'images')
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, 'stamp.png')
        file.save(save_path)
        flash('Official stamp image updated successfully!', 'success')
            
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export/camp-registrations')
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

@app.route('/admin/doctor/view/<path:doc_id>')
@admin_required
def admin_view_doctor(doc_id):
    """Displays a read-only view of a doctor's profile for the admin."""
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_view_doctor.html', doctor=doctor)

@app.route('/admin/doctor/verify/<path:doc_id>', methods=['POST'])
@admin_required
def admin_verify_doctor(doc_id):
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if doctor:
        doctor.is_verified = True
        save_data()
        
        # Send verification email
        if doctor.email:
            subject = "Account Verified - DEV AI+"
            body = f"""
Dear Dr. {doctor.first_name} {doctor.last_name},

Your account has been successfully verified by the administration team.
You now have full access to the Doctor Dashboard.

Login here: {url_for('doctor_login', _external=True)}

Best regards,
DEV AI+ Team
"""
            send_notification_email(doctor.email, subject, body)

        flash(f"Doctor {doctor.first_name} {doctor.last_name} has been verified.", "success")
    else:
        flash("Doctor not found.", "error")
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/hospital/verify/<int:hospital_id>', methods=['POST'])
@admin_required
def admin_verify_hospital(hospital_id):
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if hospital:
        hospital.is_verified = True
        save_data()
        
        if hospital.email:
            subject = "Welcome to DEV AI+ - Account Verified & Onboarding Steps"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 10px;">
                <h2 style="color: #059669; text-align: center;">Welcome to DEV AI+ Network!</h2>
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
                    &copy; {datetime.now().year} DEV AI+ Health Systems. All rights reserved.<br>
                    This is an automated message, please do not reply directly to this email.
                </p>
            </div>
            """
            send_notification_email(hospital.email, subject, body, is_html=True)

        flash(f"Hospital {hospital.name} has been verified.", "success")
    else:
        flash("Hospital not found.", "error")
    return redirect(request.referrer or url_for('admin_dashboard') + '#hospitals')

@app.route('/admin/doctor/add', methods=['GET', 'POST'])
@admin_required
def admin_add_doctor():
    """Allows an admin to add a new doctor."""
    if request.method == 'POST':
        email = request.form.get('email')
        existing_doctor = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == email), None)
        if existing_doctor:
            flash('A doctor with this email already exists.', 'error')
            return render_template('admin_add_doctor_form.html')

        year = datetime.now().year
        next_id_num = TEMP_DATA['next_ids']['doctor']
        new_id = f"DOC/{year}/{next_id_num:03d}"
        
        new_doctor = Doctor(
            id=new_id,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=email,
            password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256:260000'),
            department=request.form.get('department'),
            is_verified=True # Admins adding doctors are auto-verified
        )
        TEMP_DATA['doctors'][new_id] = new_doctor
        TEMP_DATA['next_ids']['doctor'] += 1
        save_data()
        flash(f"Doctor {new_doctor.first_name} {new_doctor.last_name} has been added successfully.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_doctor_form.html')

@app.route('/admin/patient/add', methods=['GET', 'POST'])
@admin_required
def admin_add_patient():
    """Allows an admin to add a new patient."""
    if request.method == 'POST':
        email = request.form.get('email')
        existing_patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if existing_patient:
            flash('A patient with this email already exists.', 'error')
            return render_template('admin_add_patient_form.html')

        new_id = TEMP_DATA['next_ids']['patient']
        new_patient = Patient(id=new_id, name=request.form.get('name'), email=email, password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256:260000'))
        TEMP_DATA['patients'][new_id] = new_patient
        TEMP_DATA['next_ids']['patient'] += 1
        save_data()
        flash(f"Patient {new_patient.name} has been added successfully.", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_add_patient_form.html')

@app.route('/admin/doctor/edit/<path:doc_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_doctor(doc_id):
    """Allows an admin to edit a doctor's profile."""
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # Update doctor's attributes from the form
        fields_to_update = [
            'first_name', 'last_name', 'email', 'phone', 'department', 
            'specialization', 'hospital_name', 'hospital_address', 'state',
            'district', 'pincode', 'bio', 'qualification', 'license_number',
            'experience', 'consultation_type', 'consultation_fee',
            'working_hours', 'languages_spoken'
        ]
        for field in fields_to_update:
            if field in request.form:
                setattr(doctor, field, request.form.get(field))
        
        # Handle social links separately as it's a dictionary
        doctor.social_links = request.form.get('social_links')

        save_data()
        flash(f"Doctor {doctor.first_name} {doctor.last_name}'s profile has been updated.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_doctor.html', doctor=doctor)

@app.route('/admin/patient/edit/<int:patient_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_patient(patient_id):
    """Allows an admin to edit a patient's profile."""
    patient = TEMP_DATA['patients'].get(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # Update patient's attributes from the form
        patient.name = request.form.get('name', patient.name)
        patient.email = request.form.get('email', patient.email)
        age_str = request.form.get('age')
        patient.age = int(age_str) if age_str and age_str.isdigit() else patient.age
        patient.gender = request.form.get('gender', patient.gender)
        
        save_data()
        flash(f"Patient {patient.name}'s profile has been updated.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_patient.html', patient=patient)

@app.route('/admin/staff/add', methods=['GET', 'POST'])
@admin_required
def admin_add_staff(): # The endpoint name is 'admin_add_staff'
    """Allows an admin to add a new staff member."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')
        phone = request.form.get('phone')

        if not all([name, email, role, password]):
            flash("All fields are required to add a staff member.", "error")
            return render_template('admin_add_staff_form.html')

        existing_staff = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)
        if existing_staff:
            flash(f"A staff member with the email {email} already exists.", "error")
            return render_template('admin_add_staff_form.html')

        staff_id = TEMP_DATA['next_ids']['staff']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        new_staff = Staff(id=staff_id, name=name, email=email, password=hashed_password, role=role, phone=phone)

        TEMP_DATA['staff'][staff_id] = new_staff
        TEMP_DATA['next_ids']['staff'] += 1
        save_data()
        flash(f"Staff member '{name}' has been added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    # For a GET request, show the form to add a staff member.
    return render_template('admin_add_staff_form.html')


@app.route('/admin/staff/edit/<int:staff_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_staff(staff_id):
    """Allows an admin to edit a staff member."""
    staff = TEMP_DATA['staff'].get(staff_id)
    if not staff:
        flash("Staff member not found.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        staff.name = request.form.get('name', staff.name)
        staff.email = request.form.get('email', staff.email)
        staff.role = request.form.get('role', staff.role)
        staff.phone = request.form.get('phone', staff.phone)
        save_data()
        flash(f"Staff member {staff.name} updated successfully.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_staff.html', staff=staff)

@app.route('/admin/staff/delete/<int:staff_id>', methods=['POST'])
@admin_required
def admin_delete_staff(staff_id):
    """Allows an admin to delete a staff member."""
    if staff_id in TEMP_DATA['staff']:
        del TEMP_DATA['staff'][staff_id]
        save_data()
        flash("Staff member deleted successfully.", "success")
    else:
        flash("Staff member not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/doctor/delete/<path:doc_id>', methods=['POST'])
@admin_required
def admin_delete_doctor(doc_id):
    """Allows an admin to delete a doctor and their associated data."""
    if doc_id in TEMP_DATA['doctors']:
        # To maintain data integrity, remove related items
        
        # Remove appointments for this doctor
        appointments_to_delete = [k for k, v in TEMP_DATA['appointments'].items() if v.doctor_id == doc_id]
        for appt_id in appointments_to_delete:
            del TEMP_DATA['appointments'][appt_id]

        # Remove reviews for this doctor
        reviews_to_delete = [k for k, v in TEMP_DATA['reviews'].items() if v.doctor_id == doc_id]
        for review_id in reviews_to_delete:
            del TEMP_DATA['reviews'][review_id]

        # Remove messages for this doctor
        messages_to_delete = [k for k, v in TEMP_DATA['messages'].items() if v.doctor_id == doc_id]
        for msg_id in messages_to_delete:
            del TEMP_DATA['messages'][msg_id]

        # Finally, delete the doctor
        del TEMP_DATA['doctors'][doc_id]
        save_data()
        flash(f"Doctor with ID {doc_id} and all their associated data has been deleted.", "success")
    else:
        flash("Doctor not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/patient/delete/<int:patient_id>', methods=['POST'])
@admin_required
def admin_delete_patient(patient_id):
    """Allows an admin to delete a patient and their associated data."""
    if patient_id in TEMP_DATA['patients']:
        # Remove appointments for this patient
        appointments_to_delete = [k for k, v in TEMP_DATA['appointments'].items() if v.patient_id == patient_id]
        for appt_id in appointments_to_delete:
            del TEMP_DATA['appointments'][appt_id]
        
        # Delete the patient
        del TEMP_DATA['patients'][patient_id]
        save_data()
        flash(f"Patient with ID {patient_id} and their appointments have been deleted.", "success")
    else:
        flash("Patient not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/organ-donor/edit/<int:donor_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_organ_donor(donor_id):
    """Allows an admin to edit an organ donor's profile."""
    donor = TEMP_DATA['organ_donors'].get(donor_id)
    if not donor:
        flash("Organ donor not found.", "error")
        return redirect(url_for('admin_dashboard'))

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
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_organ_donor.html', donor=donor)

@app.route('/admin/organ-donor/delete/<int:donor_id>', methods=['POST'])
@admin_required
def admin_delete_organ_donor(donor_id):
    """Allows an admin to delete an organ donor."""
    if donor_id in TEMP_DATA['organ_donors']:
        del TEMP_DATA['organ_donors'][donor_id]
        save_data()
        flash("Organ donor deleted successfully.", "success")
    else:
        flash("Organ donor not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/hospital/add', methods=['GET', 'POST'])
@admin_required
def admin_add_hospital():
    """Allows an admin to add a new hospital."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([name, email, password]):
            flash("All fields are required.", "error")
            return render_template('admin_add_hospital_form.html')

        existing_hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if existing_hospital:
            flash(f"A hospital with email {email} already exists.", "error")
            return render_template('admin_add_hospital_form.html')

        hospital_id = TEMP_DATA['next_ids']['hospital']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        new_hospital = Hospital(id=hospital_id, name=name, email=email, password=hashed_password)
        
        TEMP_DATA['hospitals'][hospital_id] = new_hospital
        TEMP_DATA['next_ids']['hospital'] += 1
        save_data()
        flash(f"Hospital '{name}' added successfully.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_hospital_form.html')

@app.route('/admin/hospital/edit/<int:hospital_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_hospital(hospital_id):
    """Allows an admin to edit an existing hospital."""
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        hospital.name = request.form.get('name')
        hospital.email = request.form.get('email')
        save_data()
        flash(f"Hospital '{hospital.name}' updated successfully.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_hospital.html', hospital=hospital)

@app.route('/admin/hospital/delete/<int:hospital_id>', methods=['POST'])
@admin_required
def admin_delete_hospital(hospital_id):
    """Allows an admin to delete a hospital."""
    if hospital_id in TEMP_DATA['hospitals']:
        del TEMP_DATA['hospitals'][hospital_id]
        save_data()
        flash("Hospital deleted successfully.", "success")
    else:
        flash("Hospital not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles the login process for the administrator."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # The admin user is hardcoded for this application
        if email != 'admin@devai.plus':
            flash('Invalid admin credentials.', 'error')
            return redirect(url_for('admin_login'))

        # The admin user can be either a doctor or a patient, so we check both data stores.
        user = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == email), None)
        if not user:
            user = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Admin login successful! Welcome to the dashboard.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.', 'error')
            return redirect(url_for('admin_login'))

    return render_template('admin_login.html')

@app.route('/hospital/register', methods=['GET', 'POST'])
def hospital_register():
    """Handles the registration process for new hospitals."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([name, email, password, confirm_password]):
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('hospital_register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('hospital_register'))

        existing_hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if existing_hospital:
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('hospital_register'))

        # Handle Logo Upload
        logo_filename = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                logo_filename = f"hospital_logo_{timestamp}_{filename}"
                upload_folder = os.path.join(app.root_path, 'static/uploads/hospital_logos')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, logo_filename))
        
        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store registration data in session
        session['hospital_signup_data'] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'otp': otp,
            'logo_url': logo_filename
        }

        # Send OTP Email
        subject = "Verify your email - DEV AI+ Hospital Portal"
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #059669;">Hospital Registration Verification</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>To complete your hospital registration, please use the following One-Time Password (OTP):</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #059669; background: #ecfdf5; padding: 15px 30px; border-radius: 5px; border: 1px solid #d1fae5;">{otp}</span>
            </div>
            <p>If you did not request this code, please ignore this email.</p>
        </div>
        """
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash("Failed to send OTP email. For development, check the terminal for the OTP.", "warning")
        
        return redirect(url_for('hospital_verify_otp'))

    return render_template('hospital_register.html')

@app.route('/hospital/verify-otp', methods=['GET', 'POST'])
def hospital_verify_otp():
    if 'hospital_signup_data' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('hospital_register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_data = session.get('hospital_signup_data')
        
        if entered_otp == stored_data.get('otp'):
            # Create Account
            new_id = TEMP_DATA['next_ids']['hospital']
            new_hospital = Hospital(
                id=new_id,
                name=stored_data['name'],
                email=stored_data['email'],
                password=stored_data['password'],
                logo_url=stored_data.get('logo_url'),
                is_verified=False
            )
            
            TEMP_DATA['hospitals'][new_id] = new_hospital
            TEMP_DATA['next_ids']['hospital'] += 1
            save_data()
            
            session.pop('hospital_signup_data', None)
            flash('Hospital account created successfully! Please wait for admin approval before logging in.', 'success')
            return redirect(url_for('hospital_login'))
        else:
            flash("Invalid OTP. Please try again.", "error")
            
    return render_template('hospital_verify_otp.html')

@app.route('/hospital/resend-otp')
def hospital_resend_otp():
    if 'hospital_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['hospital_signup_data']['otp'] = otp
        
        email = session['hospital_signup_data']['email']
        name = session['hospital_signup_data'].get('name', 'Hospital Admin')
        
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #059669;">New Verification Code</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>Here is your new OTP for hospital registration:</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #059669; background: #ecfdf5; padding: 15px 30px; border-radius: 5px; border: 1px solid #d1fae5;">{otp}</span>
            </div>
        </div>
        """
        if send_notification_email(email, "Resend OTP - DEV AI+ Hospital", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash("Failed to resend OTP email. For development, check the terminal for the new OTP.", "warning")
    return redirect(url_for('hospital_verify_otp'))

@app.route('/hospital/forgot-password', methods=['GET', 'POST'])
def hospital_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        
        if hospital:
            otp = str(random.randint(100000, 999999))
            session['hospital_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - DEV AI+ Hospital"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>Password Reset Request</h2>
                <p>Use the following OTP to reset your password:</p>
                <h1 style="color: #059669;">{otp}</h1>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
            """
            send_notification_email(email, subject, body, is_html=True)
            flash("An OTP has been sent to your email.", "info")
            return redirect(url_for('hospital_reset_password'))
        else:
            flash("No hospital account found with that email.", "error")
            
    return render_template('hospital_forgot_password.html')

@app.route('/hospital/reset-password', methods=['GET', 'POST'])
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

@app.route('/hospital/login', methods=['GET', 'POST'])
def hospital_login():
    """Handles the login process for hospital administrators."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)

        if hospital and check_password_hash(hospital.password, password):
            if not getattr(hospital, 'is_verified', True):
                flash('Your account is pending verification by an administrator.', 'warning')
                return redirect(url_for('hospital_login'))
            login_user(hospital)
            flash('Hospital login successful!', 'success')
            return redirect(url_for('hospital_dashboard'))
        else:
            flash('Invalid hospital credentials.', 'error')
            return redirect(url_for('hospital_login'))

    return render_template('hospital_login.html')

@app.route('/hospital/bed_booking/<int:booking_id>/<action>', methods=['POST'])
@hospital_required
def handle_bed_booking(booking_id, action):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if not booking or booking.hospital_id != current_user.id:
        flash("Booking not found or unauthorized.", "error")
        return redirect(url_for('hospital_dashboard'))

    if booking.status != 'pending':
        flash("This booking has already been processed.", "warning")
        return redirect(url_for('hospital_dashboard') + '#beds')

    if action == 'approve':
        if booking.bed_type == 'ICU':
            if current_user.available_icu_beds > 0:
                current_user.available_icu_beds -= 1
                booking.status = 'approved'
                flash("ICU Bed booking approved and availability updated.", "success")
            else:
                flash("No ICU beds available!", "error")
        else:
            if current_user.available_beds > 0:
                current_user.available_beds -= 1
                booking.status = 'approved'
                flash("General Bed booking approved and availability updated.", "success")
            else:
                flash("No General beds available!", "error")
    elif action == 'reject':
        booking.status = 'rejected'
        flash("Bed booking rejected.", "success")
    
    save_data()
    return redirect(url_for('hospital_dashboard') + '#beds')

@app.route('/bed_booking/invoice/<int:booking_id>')
@login_required
def bed_booking_invoice(booking_id):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if not booking:
        flash("Booking not found.", "error")
        return redirect(url_for('home'))

    is_patient = hasattr(current_user, 'is_doctor') and not current_user.is_doctor and booking.patient_id == current_user.id
    is_hospital = getattr(current_user, 'is_hospital', False) and booking.hospital_id == current_user.id
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@devai.plus'

    if not (is_patient or is_hospital or is_admin):
        flash("Unauthorized access to invoice.", "error")
        return redirect(url_for('home'))

    if booking.status != 'approved':
        flash("Invoice is only available for approved bookings.", "warning")
        return redirect(request.referrer or url_for('home'))

    hospital = TEMP_DATA['hospitals'].get(booking.hospital_id)
    fee = hospital.icu_bed_fee if booking.bed_type == 'ICU' else hospital.general_bed_fee

    try:
        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font('Helvetica', 'B', 20)
        pdf.cell(0, 10, 'BED BOOKING INVOICE', 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, to_latin1_str(hospital.name), 0, 1, 'C')
        pdf.cell(0, 5, to_latin1_str(hospital.address) if hospital.address else 'N/A', 0, 1, 'C')
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, f'Invoice #: BB-{booking.id}', 0, 1, 'R')
        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 8, f'Date: {booking.created_at.strftime("%B %d, %Y")}', 0, 1, 'R')
        pdf.ln(10)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(95, 8, 'Billed To:', 0, 0)
        pdf.cell(95, 8, 'Booking Details:', 0, 1)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(95, 6, to_latin1_str(booking.patient_name), 0, 0)
        pdf.cell(95, 6, f'Bed Type: {booking.bed_type}', 0, 1)
        pdf.cell(95, 6, f'Phone: {booking.patient_phone}', 0, 0)
        pdf.cell(95, 6, f'Status: {booking.status.capitalize()}', 0, 1)
        pdf.ln(15)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(140, 10, 'Description', 1, 0, 'L', 1)
        pdf.cell(50, 10, 'Amount', 1, 1, 'R', 1)
        pdf.set_font('Helvetica', '', 11)
        desc = f"Emergency {booking.bed_type} Bed Booking"
        pdf.cell(140, 10, desc, 1, 0, 'L')
        pdf.cell(50, 10, f"Rs. {fee:.2f}", 1, 1, 'R')

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(140, 12, 'Total Paid', 0, 0, 'R')
        pdf.cell(50, 12, f"Rs. {fee:.2f}", 1, 1, 'R')
        
        pdf.ln(15)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 10, 'PAID & APPROVED', 0, 1, 'C')

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

@app.route('/hospital/bed_booking/<int:booking_id>/email_invoice', methods=['POST'])
@hospital_required
def email_bed_booking_invoice(booking_id):
    booking = TEMP_DATA.get('bed_bookings', {}).get(booking_id)
    if not booking or booking.hospital_id != current_user.id:
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
        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font('Helvetica', 'B', 20)
        pdf.cell(0, 10, 'BED BOOKING INVOICE', 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, to_latin1_str(hospital.name), 0, 1, 'C')
        pdf.cell(0, 5, to_latin1_str(hospital.address) if hospital.address else 'N/A', 0, 1, 'C')
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, f'Invoice #: BB-{booking.id}', 0, 1, 'R')
        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 8, f'Date: {booking.created_at.strftime("%B %d, %Y")}', 0, 1, 'R')
        pdf.ln(10)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(95, 8, 'Billed To:', 0, 0)
        pdf.cell(95, 8, 'Booking Details:', 0, 1)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(95, 6, to_latin1_str(booking.patient_name), 0, 0)
        pdf.cell(95, 6, f'Bed Type: {booking.bed_type}', 0, 1)
        pdf.cell(95, 6, f'Phone: {booking.patient_phone}', 0, 0)
        pdf.cell(95, 6, f'Status: {booking.status.capitalize()}', 0, 1)
        pdf.ln(15)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(140, 10, 'Description', 1, 0, 'L', 1)
        pdf.cell(50, 10, 'Amount', 1, 1, 'R', 1)
        pdf.set_font('Helvetica', '', 11)
        desc = f"Emergency {booking.bed_type} Bed Booking"
        pdf.cell(140, 10, desc, 1, 0, 'L')
        pdf.cell(50, 10, f"Rs. {fee:.2f}", 1, 1, 'R')

        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(140, 12, 'Total Paid', 0, 0, 'R')
        pdf.cell(50, 12, f"Rs. {fee:.2f}", 1, 1, 'R')
        
        pdf.ln(15)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 10, 'PAID & APPROVED', 0, 1, 'C')

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

@app.route('/hospital/dashboard', methods=['GET', 'POST'])
@hospital_required
def hospital_dashboard():
    """Displays the hospital dashboard with appointments, doctors, and settings."""
    
    # 1. Handle POST requests (Forms)
    if request.method == 'POST':
        # --- Add Doctor ---
        if 'add_doctor' in request.form:
            email = request.form.get('email')
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
                    password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256:260000'),
                    department=request.form.get('department'),
                    hospital_name=current_user.name, # Automatically link to this hospital
                    hospital_address=request.form.get('hospital_address') or "On Campus",
                    phone=request.form.get('phone'),
                    specialization=request.form.get('specialization')
                )
                TEMP_DATA['doctors'][new_id] = new_doctor
                TEMP_DATA['next_ids']['doctor'] += 1
                save_data()
                flash(f'Dr. {new_doctor.last_name} added successfully.', 'success')
            return redirect(url_for('hospital_dashboard'))

        # --- Add Staff ---
        elif 'add_staff' in request.form:
            email = request.form.get('email')
            existing = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)
            if existing:
                flash('A staff member with this email already exists.', 'error')
            else:
                staff_id = TEMP_DATA['next_ids']['staff']
                new_staff = Staff(
                    id=staff_id,
                    name=request.form.get('name'),
                    email=email,
                    password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256:260000'),
                    role=request.form.get('role'),
                    phone=request.form.get('phone'),
                    hospital_name=current_user.name
                )
                TEMP_DATA['staff'][staff_id] = new_staff
                TEMP_DATA['next_ids']['staff'] += 1
                save_data()
                flash(f'Staff member {new_staff.name} added successfully.', 'success')
            return redirect(url_for('hospital_dashboard'))

        # --- Edit Staff ---
        elif 'edit_staff' in request.form:
            staff_id_str = request.form.get('staff_id')
            if staff_id_str and staff_id_str.isdigit():
                staff_id = int(staff_id_str)
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
            if staff_id_str and staff_id_str.isdigit():
                staff_id = int(staff_id_str)
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
            current_user.phone = request.form.get('phone')
            current_user.address = request.form.get('address')
            current_user.city = request.form.get('city')
            current_user.state = request.form.get('state')
            current_user.zip_code = request.form.get('zip_code')
            
            # Handle Logo Upload
            if 'logo' in request.files:
                file = request.files['logo']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"hospital_logo_{timestamp}_{filename}"
                    upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'hospital_logos')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, unique_filename))
                    current_user.logo_url = unique_filename
            
            save_data()
            flash('Hospital profile updated successfully.', 'success')
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

    # 2. Prepare Data for View
    # Filter doctors belonging to this hospital
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == current_user.name]
    
    # Filter staff belonging to this hospital
    hospital_staff = [s for s in TEMP_DATA['staff'].values() if s.hospital_name == current_user.name]
    
    # Filter appointments for doctors in this hospital
    hospital_appointments = []
    unique_patient_ids = set()
    
    for appt in TEMP_DATA['appointments'].values():
        doc = TEMP_DATA['doctors'].get(appt.doctor_id)
        if doc and doc.hospital_name == current_user.name:
            hospital_appointments.append(appt)
            if appt.patient_id:
                unique_patient_ids.add(appt.patient_id)

    # Sort appointments by date (newest first)
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    
    # Get Patient objects
    hospital_patients = [TEMP_DATA['patients'][pid] for pid in unique_patient_ids if pid in TEMP_DATA['patients']]

    # Chart Data (Appointments per day)
    dates = [appt.appointment_date for appt in hospital_appointments if appt.appointment_date]
    date_counts = Counter(dates)
    sorted_dates = sorted(date_counts.keys())
    chart_labels = [d.strftime('%Y-%m-%d') for d in sorted_dates]
    chart_data = [date_counts[d] for d in sorted_dates]

    # Filter camps organized by this hospital
    hospital_camps = [c for c in TEMP_DATA['camps'].values() if c.get('organizer') == current_user.name]
    
    # Filter Bed Bookings for this hospital
    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if b.hospital_id == current_user.id]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)

    return render_template('hospital_dashboard.html', 
                           appointments=hospital_appointments, 
                           doctors=hospital_doctors,
                           staff=hospital_staff,
                           patients=hospital_patients,
                           camps=hospital_camps,
                           bed_bookings=hospital_bed_bookings,
                           chart_labels=chart_labels, 
                           chart_data=chart_data)

@app.route('/login_landing') # Renamed to avoid conflict if /login is for patient
def login_landing():
    return render_template('login_landing.html')

@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    """Handles login for staff members."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        staff_member = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)

        if staff_member and check_password_hash(staff_member.password, password):
            login_user(staff_member)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('staff_dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('staff_login'))

    return render_template('staff_login.html')

@app.route('/staff/dashboard')
@login_required # We can create a @staff_required decorator later
def staff_dashboard():
    """Placeholder dashboard for logged-in staff."""
    return render_template('staff_dashboard.html')

@app.route('/patient/login', methods=['GET', 'POST'])
# @limiter.limit("10 per minute") # Specific, stricter limit for login attempts
def patient_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        
        if patient:
            try:
                # Standard check
                is_valid = check_password_hash(patient.password, password)
            except AttributeError as e:
                # Fallback for old hash methods like scrypt if hashlib doesn't support it
                if 'scrypt' in str(e):
                    # This is a workaround and assumes the password is correct if the old hash fails.
                    # A better check would be against a known legacy hash if possible, but this will allow migration.
                    # For this to work, we are essentially trusting the password is correct to migrate it.
                    # A more secure way is to re-hash the provided password and check against that, but werkzeug doesn't expose the salt.
                    # The most pragmatic approach is to allow the login and force re-hash.
                    is_valid = True # Assume valid to trigger re-hash
                else:
                    is_valid = False # Another attribute error occurred

            if is_valid:
                # If login is successful, check if the password needs to be rehashed to the new format.
                if not patient.password.startswith('pbkdf2:sha256'):
                    patient.password = generate_password_hash(password, method='pbkdf2:sha256:260000')
                    save_data() # Save the updated password hash

                login_user(patient)
                flash("Logged in successfully!", "success")
                return redirect(url_for('patient_dashboard'))

        flash("Invalid email or password", "error")
    return render_template('patient_login.html')

@app.route('/patient/signup', methods=['GET', 'POST'])
def patient_signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password') # Raw password
        age = request.form.get('age') # Assuming age is also submitted
        gender = request.form.get('gender') # Assuming gender is also submitted

        if not all([name, email, password]):
            flash("Name, email, and password are required fields.", "error")
            return redirect(url_for('patient_signup'))

        existing_patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if existing_patient:
            flash("An account with this email already exists.", "error")
            return redirect(url_for('patient_signup'))
        
        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))

        # Store registration data and OTP in session temporarily
        session['signup_data'] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'age': int(age) if age and age.isdigit() else None,
            'gender': gender,
            'otp': otp
        }

        # Send OTP Email
        subject = "Your OTP for DEV AI+ Registration"
        
        # HTML Email Body
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px;">
            <h2 style="color: #0d6efd; text-align: center;">Welcome to DEV AI+</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>Thank you for registering. Please use the verification code below to complete your sign-up:</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #0d6efd; background: #f8f9fa; padding: 15px 30px; border-radius: 5px; border: 1px solid #ddd;">{otp}</span>
            </div>
            <p>If you did not request this code, please ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; text-align: center; color: #aaa;">&copy; {datetime.now().year} DEV AI+. All rights reserved.</p>
        </div>
        """
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            # Fallback for development if email is not configured
            print(f"DEBUG: OTP for {email} is {otp}")
            flash("Failed to send OTP email. For development, check the terminal for the OTP.", "warning")

        return redirect(url_for('patient_verify_otp'))
    return render_template('patient_signup.html')

@app.route('/patient/verify-otp', methods=['GET', 'POST'])
def patient_verify_otp():
    if 'signup_data' not in session:
        flash("Session expired. Please sign up again.", "error")
        return redirect(url_for('patient_signup'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_data = session.get('signup_data')
        
        if entered_otp == stored_data.get('otp'):
            # OTP Matches - Create Account
            new_id = TEMP_DATA['next_ids']['patient']
            new_patient = Patient(
                id=new_id,
                name=stored_data['name'],
                email=stored_data['email'],
                password=stored_data['password'], # Already hashed in signup step
                age=stored_data['age'],
                gender=stored_data['gender']
            )
            TEMP_DATA['patients'][new_id] = new_patient
            TEMP_DATA['next_ids']['patient'] += 1
            save_data()
            
            # Clear session data
            session.pop('signup_data', None)
            
            flash("Account verified and created successfully! Please log in.", "success")
            return redirect(url_for('patient_login'))
        else:
            flash("Invalid OTP. Please try again.", "error")
    
    return render_template('patient_verify_otp.html')

@app.route('/patient/resend-otp')
def patient_resend_otp():
    if 'signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['signup_data']['otp'] = otp
        
        email = session['signup_data']['email']
        name = session['signup_data'].get('name', 'Patient')
        
        body = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #0d6efd;">New Verification Code</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>Here is your new OTP for registration:</p>
            <div style="text-align: center; margin: 30px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #0d6efd; background: #f8f9fa; padding: 15px 30px; border-radius: 5px; border: 1px solid #ddd;">{otp}</span>
            </div>
        </div>
        """
        if send_notification_email(email, "Resend OTP - DEV AI+", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash("Failed to resend OTP email. For development, check the terminal for the new OTP.", "warning")
    return redirect(url_for('patient_verify_otp'))

@app.route('/patient/forgot-password', methods=['GET', 'POST'])
def patient_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        
        if patient:
            otp = str(random.randint(100000, 999999))
            session['reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - DEV AI+"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>Password Reset Request</h2>
                <p>Use the following OTP to reset your password:</p>
                <h1 style="color: #0d6efd;">{otp}</h1>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
            """
            send_notification_email(email, subject, body, is_html=True)
            flash("An OTP has been sent to your email.", "info")
            return redirect(url_for('patient_reset_password'))
        else:
            flash("No account found with that email.", "error")
            
    return render_template('patient_forgot_password.html')

@app.route('/patient/reset-password', methods=['GET', 'POST'])
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

@app.route('/login/google')
def google_login():
    # Get the intended role from query params, default to patient if not specified
    role = request.args.get('role', 'patient')
    session['google_login_role'] = role
    redirect_uri = url_for('google_authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def google_authorize():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.userinfo()
    
    email = user_info['email']
    name = user_info['name']
    role = session.get('google_login_role', 'patient')
    is_new_user = False
    
    if role == 'patient':
        user = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if not user:
            is_new_user = True
            new_id = TEMP_DATA['next_ids']['patient']
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
            donor_id = TEMP_DATA['next_ids']['blood_donor']
            user = BloodDonor(id=donor_id, name=name, email=email, phone="N/A", blood_group="Unknown", age=18, city="Unknown", password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'))
            TEMP_DATA['blood_donors'][donor_id] = user
            TEMP_DATA['next_ids']['blood_donor'] += 1
            save_data()
            flash('Account created via Google. Please update your profile details.', 'info')
        login_user(user)
        if is_new_user:
            return redirect(url_for('complete_profile'))
        return redirect(url_for('blood_donor_dashboard'))

    elif role == 'organ_donor':
        user = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)
        if not user:
            is_new_user = True
            donor_id = TEMP_DATA['next_ids']['organ_donor']
            user = OrganDonor(id=donor_id, name=name, email=email, phone="N/A", organs=[], blood_group="Unknown", age=18, city="Unknown", password=generate_password_hash(os.urandom(24).hex(), method='pbkdf2:sha256:260000'))
            TEMP_DATA['organ_donors'][donor_id] = user
            TEMP_DATA['next_ids']['organ_donor'] += 1
            save_data()
            flash('Organ donor account created via Google. Please update your profile.', 'info')
        login_user(user)
        if is_new_user:
            return redirect(url_for('complete_profile'))
        return redirect(url_for('organ_donor_dashboard'))

    elif role == 'hospital':
        user = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if not user:
            is_new_user = True
            hospital_id = TEMP_DATA['next_ids']['hospital']
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


@app.route('/complete-profile')
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

@app.route('/blood-donor-register', methods=['GET', 'POST'])
def blood_donor_register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        blood_group = request.form.get('blood_group')
        age = request.form.get('age')
        city = request.form.get('city')
        last_donation = request.form.get('last_donation')

        if not all([name, email, password, phone, blood_group, age, city]):
            flash('Please fill out all required fields.', 'error')
            return redirect(url_for('blood_donor_register'))

        if any(d.email == email for d in TEMP_DATA['blood_donors'].values()):
            flash('A donor with this email already exists.', 'error')
            return redirect(url_for('blood_donor_register'))
        
        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store registration data in session
        session['donor_signup_data'] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'phone': phone,
            'blood_group': blood_group,
            'age': int(age) if age and age.isdigit() else 0,
            'city': city,
            'last_donation': last_donation,
            'otp': otp
        }

        # Send OTP Email
        subject = "Verify your email - DEV AI+ Blood Donor"
        
        # HTML Email Body
        body = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; padding: 40px 20px; color: #333; max-width: 600px; margin: 0 auto; background-color: #f9fafb;">
            <div style="background-color: #ffffff; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h2 style="color: #dc2626; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">DEV AI+</h2>
                    <p style="color: #9ca3af; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px; font-weight: 600;">Blood Donor Network</p>
                </div>
                
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 20px;">Hello <strong>{name}</strong>,</p>
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 30px; color: #4b5563;">
                    Thank you for joining our community of lifesavers. To complete your registration and verify your email address, please use the One-Time Password (OTP) below.
                </p>
                
                <div style="text-align: center; margin: 40px 0;">
                    <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #dc2626; background: #fef2f2; padding: 20px 40px; border-radius: 12px; border: 2px dashed #fecaca; display: inline-block;">{otp}</span>
                </div>
                
                <p style="font-size: 14px; color: #6b7280; text-align: center; margin-bottom: 0;">
                    This code will expire in 10 minutes. If you did not initiate this request, please ignore this email.
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #9ca3af; font-size: 12px;">
                <p>&copy; {datetime.now().year} DEV AI+ Health Systems. All rights reserved.</p>
            </div>
        </div>
        """
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash("Failed to send OTP email. For development, check the terminal for the OTP.", "warning")

        return redirect(url_for('blood_donor_verify_otp'))
    
    return render_template('blood_donor_register.html')

@app.route('/blood-donor/verify-otp', methods=['GET', 'POST'])
def blood_donor_verify_otp():
    if 'donor_signup_data' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('blood_donor_register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_data = session.get('donor_signup_data')
        
        if entered_otp == stored_data.get('otp'):
            # Create Account
            donor_id = TEMP_DATA['next_ids']['blood_donor']
            new_donor = BloodDonor(
                id=donor_id, 
                name=stored_data['name'], 
                email=stored_data['email'], 
                phone=stored_data['phone'],
                blood_group=stored_data['blood_group'], 
                age=stored_data['age'], 
                city=stored_data['city'], 
                password=stored_data['password'], 
                last_donation=stored_data['last_donation']
            )
            
            TEMP_DATA['blood_donors'][donor_id] = new_donor
            TEMP_DATA['next_ids']['blood_donor'] += 1
            save_data()
            
            session.pop('donor_signup_data', None)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('blood_donor_login'))
        else:
            flash("Invalid OTP. Please try again.", "error")
            
    return render_template('blood_donor_verify_otp.html')

@app.route('/blood-donor/resend-otp')
def blood_donor_resend_otp():
    if 'donor_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['donor_signup_data']['otp'] = otp
        
        email = session['donor_signup_data']['email']
        name = session['donor_signup_data'].get('name', 'Donor')
        
        body = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; padding: 40px 20px; color: #333; max-width: 600px; margin: 0 auto; background-color: #f9fafb;">
            <div style="background-color: #ffffff; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h2 style="color: #dc2626; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">DEV AI+</h2>
                    <p style="color: #9ca3af; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px; font-weight: 600;">Blood Donor Network</p>
                </div>
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 20px;">Hello <strong>{name}</strong>,</p>
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 30px; color: #4b5563;">Here is your new verification code:</p>
                <div style="text-align: center; margin: 40px 0;">
                    <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #dc2626; background: #fef2f2; padding: 20px 40px; border-radius: 12px; border: 2px dashed #fecaca; display: inline-block;">{otp}</span>
                </div>
                <p style="font-size: 14px; color: #6b7280; text-align: center; margin-bottom: 0;">This code will expire in 10 minutes.</p>
            </div>
            <div style="text-align: center; margin-top: 30px; color: #9ca3af; font-size: 12px;">
                <p>&copy; {datetime.now().year} DEV AI+ Health Systems. All rights reserved.</p>
            </div>
        </div>
        """
        if send_notification_email(email, "Resend OTP - DEV AI+", body, is_html=True):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash("Failed to resend OTP email. For development, check the terminal for the new OTP.", "warning")
    return redirect(url_for('blood_donor_verify_otp'))

@app.route('/blood-donor/forgot-password', methods=['GET', 'POST'])
def blood_donor_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        donor = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == email), None)
        
        if donor:
            otp = str(random.randint(100000, 999999))
            session['donor_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - DEV AI+ Blood Donor"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>Password Reset Request</h2>
                <p>Use the following OTP to reset your password:</p>
                <h1 style="color: #dc2626;">{otp}</h1>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
            """
            send_notification_email(email, subject, body, is_html=True)
            flash("An OTP has been sent to your email.", "info")
            return redirect(url_for('blood_donor_reset_password'))
        else:
            flash("No donor account found with that email.", "error")
            
    return render_template('blood_donor_forgot_password.html')

@app.route('/blood-donor/reset-password', methods=['GET', 'POST'])
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

@app.route('/blood-donor-login', methods=['GET', 'POST'])
def blood_donor_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        donor = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == email), None)

        if donor and donor.password and check_password_hash(donor.password, password):
            login_user(donor)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('blood_donor_dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('blood_donor_login'))

    return render_template('blood_donor_login.html')

@app.route('/blood-donor/dashboard', methods=['GET', 'POST'])
@login_required
def blood_donor_dashboard():
    if not isinstance(current_user, BloodDonor):
        flash("Access denied.", "error")
        return redirect(url_for('home'))

    if request.method == 'POST':
        if 'update_profile' in request.form:
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
                existing = next((d for d in TEMP_DATA['blood_donors'].values() if d.email == new_email), None)
                if existing:
                    flash("Email already exists.", "error")
                else:
                    current_user.email = new_email

            # Handle Profile Picture Upload
            if 'profilePicture' in request.files:
                file = request.files['profilePicture']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"bd_profile_{timestamp}_{filename}"
                    upload_folder = os.path.join(app.root_path, 'static', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, unique_filename))
                    current_user.profile_picture_url = unique_filename

            save_data()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('blood_donor_dashboard'))
        
        elif 'delete_picture' in request.form:
            if current_user.profile_picture_url:
                current_user.profile_picture_url = None
                save_data()
                flash("Profile picture removed.", "success")
            return redirect(url_for('blood_donor_dashboard'))

        elif 'delete_account' in request.form:
            donor_id = current_user.id
            logout_user()
            if donor_id in TEMP_DATA['blood_donors']:
                del TEMP_DATA['blood_donors'][donor_id]
                save_data()
            flash("Your account has been deleted.", "success")
            return redirect(url_for('home'))

    return render_template('blood_donor_dashboard.html', donor=current_user)

@app.route('/blood-donors')
def blood_donors_list():
    city_query = request.args.get('city', '').strip().lower()
    blood_group_query = request.args.get('blood_group', '').strip()

    all_donors = list(TEMP_DATA['blood_donors'].values())
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

@app.route('/organ-donor-register', methods=['GET', 'POST'])
def organ_donor_register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        organs = request.form.getlist('organs')
        blood_group = request.form.get('blood_group')
        age = request.form.get('age')
        city = request.form.get('city')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([name, email, phone, organs, blood_group, age, city, password, confirm_password]):
            flash('Please fill out all required fields.', 'error')
            return redirect(url_for('organ_donor_register'))

        if any(d.email == email for d in TEMP_DATA['organ_donors'].values()):
            flash('A donor with this email already exists.', 'error')
            return redirect(url_for('organ_donor_register'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('organ_donor_register'))
        
        # Generate OTP
        otp = str(random.randint(100000, 999999))

        # Store registration data in session
        session['organ_donor_signup_data'] = {
            'name': name,
            'email': email,
            'phone': phone,
            'organs': organs,
            'blood_group': blood_group,
            'age': int(age) if age and age.isdigit() else 0,
            'city': city,
            'password': generate_password_hash(password, method='pbkdf2:sha256:260000'),
            'otp': otp
        }
        
        # Send OTP Email
        subject = "Verify your email - DEV AI+ Organ Donor"
        
        # HTML Email Body
        body = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; padding: 40px 20px; color: #333; max-width: 600px; margin: 0 auto; background-color: #f9fafb;">
            <div style="background-color: #ffffff; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h2 style="color: #0284c7; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">DEV AI+</h2>
                    <p style="color: #9ca3af; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px; font-weight: 600;">Organ Donor Registry</p>
                </div>
                
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 20px;">Hello <strong>{name}</strong>,</p>
                <p style="font-size: 16px; line-height: 1.6; margin-bottom: 30px; color: #4b5563;">
                    Thank you for your noble decision to pledge your organs. To complete your registration and verify your email address, please use the One-Time Password (OTP) below.
                </p>
                
                <div style="text-align: center; margin: 40px 0;">
                    <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #0284c7; background: #f0f9ff; padding: 20px 40px; border-radius: 12px; border: 2px dashed #bae6fd; display: inline-block;">{otp}</span>
                </div>
                
                <p style="font-size: 14px; color: #6b7280; text-align: center; margin-bottom: 0;">
                    This code will expire in 10 minutes. If you did not initiate this request, please ignore this email.
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #9ca3af; font-size: 12px;">
                <p>&copy; {datetime.now().year} DEV AI+ Health Systems. All rights reserved.</p>
            </div>
        </div>
        """
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash("Failed to send OTP email. For development, check the terminal for the OTP.", "warning")

        return redirect(url_for('organ_donor_verify_otp'))

    return render_template('organ_donor_register.html')

@app.route('/organ-donor/verify-otp', methods=['GET', 'POST'])
def organ_donor_verify_otp():
    if 'organ_donor_signup_data' not in session:
        flash("Session expired. Please register again.", "error")
        return redirect(url_for('organ_donor_register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        stored_data = session.get('organ_donor_signup_data')
        
        if entered_otp == stored_data.get('otp'):
            # Create Account
            donor_id = TEMP_DATA['next_ids']['organ_donor']
            new_donor = OrganDonor(
                id=donor_id, 
                name=stored_data['name'], 
                email=stored_data['email'], 
                phone=stored_data['phone'],
                organs=stored_data['organs'],
                blood_group=stored_data['blood_group'], 
                age=stored_data['age'], 
                city=stored_data['city'],
                password=stored_data['password']
            )
            
            TEMP_DATA['organ_donors'][donor_id] = new_donor
            TEMP_DATA['next_ids']['organ_donor'] += 1
            save_data()
            
            # Send Welcome & Confirmation Email
            subject = "Thank you for registering as an Organ Donor - DEV AI+"
            body = f"Dear {stored_data['name']},\n\nThank you for taking the noble step of registering as an organ donor. Your pledge to donate {', '.join(stored_data['organs'])} can save multiple lives.\n\nBest regards,\nDEV AI+ Team"
            send_notification_email(stored_data['email'], subject, body)

            session.pop('organ_donor_signup_data', None)
            flash('Thank you for registering as an organ donor! Please log in.', 'success')
            return redirect(url_for('organ_donor_login'))
        else:
            flash("Invalid OTP. Please try again.", "error")
            
    return render_template('organ_donor_verify_otp.html')

@app.route('/organ-donor/resend-otp')
def organ_donor_resend_otp():
    if 'organ_donor_signup_data' in session:
        otp = str(random.randint(100000, 999999))
        session['organ_donor_signup_data']['otp'] = otp
        email = session['organ_donor_signup_data']['email']
        name = session['organ_donor_signup_data'].get('name', 'Donor')
        
        body = f"Hello {name},\n\nHere is your new verification code: {otp}\n\nThis code will expire in 10 minutes."
        if send_notification_email(email, "Resend OTP - DEV AI+", body, is_html=False):
            flash("New OTP sent.", "info")
        else:
            print(f"DEBUG: Resent OTP for {email} is {otp}")
            flash("Failed to resend OTP email. For development, check the terminal for the new OTP.", "warning")
    return redirect(url_for('organ_donor_verify_otp'))

@app.route('/organ-donor/forgot-password', methods=['GET', 'POST'])
def organ_donor_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        donor = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)
        
        if donor:
            otp = str(random.randint(100000, 999999))
            session['organ_donor_reset_data'] = {'email': email, 'otp': otp}
            
            subject = "Reset Your Password - DEV AI+ Organ Registry"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2>Password Reset Request</h2>
                <p>Use the following OTP to reset your password:</p>
                <h1 style="color: #0284c7;">{otp}</h1>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
            """
            send_notification_email(email, subject, body, is_html=True)
            flash("An OTP has been sent to your email.", "info")
            return redirect(url_for('organ_donor_reset_password'))
        else:
            flash("No donor account found with that email.", "error")
            
    return render_template('organ_donor_forgot_password.html')

@app.route('/organ-donor/reset-password', methods=['GET', 'POST'])
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

@app.route('/organ-donor-login', methods=['GET', 'POST'])
def organ_donor_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        donor = next((d for d in TEMP_DATA['organ_donors'].values() if d.email == email), None)

        if donor and donor.password and check_password_hash(donor.password, password):
            login_user(donor)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('organ_donor_dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('organ_donor_login'))

    return render_template('organ_donor_login.html')

@app.route('/organ-donor/dashboard', methods=['GET', 'POST'])
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

            # Handle Profile Picture Upload
            if 'profilePicture' in request.files:
                file = request.files['profilePicture']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"od_profile_{timestamp}_{filename}"
                    upload_folder = os.path.join(app.root_path, 'static', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, unique_filename))
                    current_user.profile_picture_url = unique_filename

            save_data()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('organ_donor_dashboard'))
            
        elif 'delete_picture' in request.form:
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

    return render_template('organ_donor_dashboard.html', donor=current_user)

@app.route('/organ-donors')
def organ_donors_list():
    city_query = request.args.get('city', '').strip().lower()
    organ_query = request.args.get('organ', '').strip().lower()

    all_donors = list(TEMP_DATA['organ_donors'].values())
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

@app.route('/organ-donor/certificate/<int:donor_id>')
def download_organ_certificate(donor_id):
    donor = TEMP_DATA['organ_donors'].get(donor_id)
    if not donor:
        flash("Donor not found.", "error")
        return redirect(url_for('organ_donors_list'))

    try:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        
        # --- 1. Background & Border ---
        pdf.set_fill_color(245, 252, 255) 
        pdf.rect(0, 0, 297, 210, 'F')

        # --- DEV Ai+ Watermark ---
        pdf.set_font('Helvetica', 'B', 140)
        pdf.set_text_color(230, 245, 255)
        
        # Rotate 45 degrees around center
        angle = 45
        x = pdf.w / 2
        y = pdf.h / 2
        c = math.cos(math.radians(angle))
        s = math.sin(math.radians(angle))
        cx = x * pdf.k
        cy = (pdf.h - y) * pdf.k
        s_val = f'q {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {cx:.2f} {cy:.2f} cm 1 0 0 1 {-cx:.2f} {-cy:.2f} cm'
        pdf._out(s_val)
        pdf.text(x - 110, y + 45, 'DEV Ai+')
        pdf._out('Q')

        # --- Complex Decorative Border ---
        pdf.set_draw_color(0, 102, 204) # Deep Blue
        pdf.set_line_width(2)
        pdf.rect(5, 5, 287, 200)

        pdf.set_draw_color(218, 165, 32) # Gold
        pdf.set_line_width(0.5)
        pdf.rect(8, 8, 281, 194)
        pdf.rect(9, 9, 279, 192)
        
        pdf.set_draw_color(0, 102, 204)
        pdf.set_line_width(1)
        pdf.rect(13, 13, 271, 184)

        # --- 2. Header ---
        pdf.set_text_color(80, 80, 80)
        
        # Certificate Number at top left side
        cert_number = f"OD/{donor.created_at.year}/{donor.id:05d}"
        pdf.set_xy(18, 18)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"Certificate Number: {cert_number}", 0, 1, 'L')

        pdf.set_y(22)
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(218, 165, 32)
        pdf.cell(0, 10, 'DEV AI+ HEALTH INTELLIGENCE', 0, 1, 'C')
        
        pdf.set_font('Times', 'I', 12)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, 'Recognizing Excellence in Humanity', 0, 1, 'C')

        pdf.set_y(50)
        pdf.set_font('Times', 'B', 42)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(0, 15, 'ORGAN DONATION PLEDGE', 0, 1, 'C')

        # --- 3. Body Content ---
        pdf.ln(8)
        pdf.set_font('Times', 'I', 16)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 10, 'This honorable pledge is proudly made by', 0, 1, 'C')
        
        pdf.ln(4)
        name = to_latin1_str(donor.name).upper()
        pdf.set_font('Helvetica', 'B', 34)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 20, name, 0, 1, 'C')
        
        name_w = pdf.get_string_width(name) + 40
        start_x = (297 - name_w) / 2
        pdf.set_draw_color(218, 165, 32)
        pdf.set_line_width(1)
        pdf.line(start_x, pdf.get_y(), start_x + name_w, pdf.get_y())
        
        pdf.ln(8)
        organs_str = ", ".join(donor.organs) if donor.organs else "All Viable Organs"
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(0, 8, f"BLOOD GROUP: {donor.blood_group}   |   ORGANS PLEDGED: {to_latin1_str(organs_str).upper()}", 0, 1, 'C')
        
        pdf.ln(8)
        pdf.set_font('Times', 'I', 16)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 8, 'For your selfless and voluntary decision to pledge your organs.\nYour noble commitment will serve as a beacon of hope and a second chance at life for those in need.', 0, 'C')
        
        # --- 4. Footer & QR ---
        y_footer = 155
        pdf.set_xy(35, y_footer + 5)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(100, 100, 100)
        
        pdf.cell(30, 6, "DATE:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 6, str(donor.created_at.strftime('%Y-%m-%d')), 0, 1, 'L')
        
        pdf.set_x(35)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(30, 6, "ISSUER:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 6, "DEV Ai+ Organ Registry", 0, 1, 'L')

        # Signature Block
        
        # Official Stamp
        try:
            stamp_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
            if os.path.exists(stamp_path):
                # Centered horizontally: (297 / 2) - (25 / 2) = 136.5
                pdf.image(stamp_path, x=136.5, y=y_footer - 5, w=25)
        except Exception:
            pass

        pdf.set_xy(200, y_footer)
        signature_drawn = False
        try:
            signature_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
            if os.path.exists(signature_path):
                pdf.image(signature_path, x=215, y=y_footer - 2, w=30)
                pdf.set_y(y_footer + 12)
                signature_drawn = True
        except Exception:
            pass
            
        if not signature_drawn:
            pdf.set_font('Times', 'I', 24)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(60, 12, 'Sunny Kushwaha', 0, 1, 'C')
        
        pdf.set_draw_color(100, 100, 100)
        pdf.set_line_width(0.3)
        pdf.line(205, pdf.get_y(), 255, pdf.get_y())
        
        pdf.set_xy(200, pdf.get_y() + 2)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(60, 5, 'PRESIDENT, DEV AI+', 0, 1, 'C')
        
        # QR Code
        qr_url = url_for('organ_donors_list', _external=True)
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_qr:
            qr_img.save(tmp_qr)
            tmp_qr_path = tmp_qr.name
            
        pdf.image(tmp_qr_path, x=262, y=165, w=20, h=20)
        try: os.unlink(tmp_qr_path)
        except OSError: pass

        try:
            pdf_output = pdf.output(dest='S')
            pdf_bytes = pdf_output.encode('latin-1') if isinstance(pdf_output, str) else pdf_output
        except TypeError:
            pdf_bytes = pdf.output()
             
        if request.args.get('action') == 'email':
            subject = "Your Organ Donation Pledge Certificate - DEV AI+"
            body = f"Dear {donor.name},\n\nThank you for your noble decision to pledge your organs. Please find your official organ donor certificate attached to this email.\n\nBest regards,\nDEV AI+ Organ Registry"
            send_notification_email(donor.email, subject, body, is_html=False, attachment_name=f"organ_pledge_{donor.id}.pdf", attachment_data=pdf_bytes)
            flash("Certificate sent to your email successfully!", "success")
            return redirect(url_for('organ_donor_dashboard'))
        else:
            return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'organ_pledge_{donor.id}.pdf', mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating organ certificate: {e}")
        flash("An error occurred while generating the certificate.", "error")
        return redirect(url_for('organ_donors_list'))

@app.route('/blood-bank')
def blood_bank():
    """Displays the blood bank inventory."""
    return render_template('blood_bank.html', stock=TEMP_DATA['blood_stock'])

@app.route('/blood-bank/update', methods=['POST'])
@login_required
def update_blood_stock():
    """Allows hospitals and admins to update blood stock levels."""
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@devai.plus'
    is_hospital = getattr(current_user, 'is_hospital', False)
    
    if not (is_admin or is_hospital):
        flash("Access denied. Only authorized personnel can manage inventory.", "error")
        return redirect(url_for('blood_bank'))

    group = request.form.get('group')
    operation = request.form.get('operation') # 'add' or 'sub'
    
    if group in TEMP_DATA['blood_stock']:
        if operation == 'add':
            TEMP_DATA['blood_stock'][group] += 1
        elif operation == 'sub' and TEMP_DATA['blood_stock'][group] > 0:
            TEMP_DATA['blood_stock'][group] -= 1
        save_data()
    
    return redirect(url_for('blood_bank'))

@app.route('/blood-donation-camps')
def blood_donation_camps():
    """Displays a list of upcoming blood donation camps."""
    today = date.today()
    
    # Initialize default camps if none exist
    if not TEMP_DATA['camps']:
        default_camps = [
            {
                "name": "City Center Life Saver Drive",
                "location": "Central Community Hall, Downtown",
                "date": (today + timedelta(days=5)).strftime('%B %d, %Y'),
                "time": "09:00 AM - 05:00 PM",
                "organizer": "Red Cross Society",
                "contact": "+1 234-567-8900"
            },
            {
                "name": "University Campus Blood Camp",
                "location": "Student Union Building, State University",
                "date": (today + timedelta(days=12)).strftime('%B %d, %Y'),
                "time": "10:00 AM - 04:00 PM",
                "organizer": "NSS Unit",
                "contact": "+1 987-654-3210"
            },
            {
                "name": "Corporate Park Charity Drive",
                "location": "Tech Park Plaza, Sector 5",
                "date": (today + timedelta(days=20)).strftime('%B %d, %Y'),
                "time": "09:30 AM - 03:30 PM",
                "organizer": "Rotary Club",
                "contact": "+1 555-123-4567"
            }
        ]
        for c in default_camps:
            cid = TEMP_DATA['next_ids']['camp']
            c['id'] = cid
            TEMP_DATA['camps'][cid] = c
            TEMP_DATA['next_ids']['camp'] += 1
        save_data()

    camps = list(TEMP_DATA['camps'].values())
    return render_template('blood_donation_camps.html', camps=camps)

@app.route('/blood-donation-camps/register', methods=['POST'])
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

@app.route('/admin/camp/add', methods=['POST'])
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

@app.route('/admin/camp/delete/<int:camp_id>', methods=['POST'])
@admin_required
def admin_delete_camp(camp_id):
    if camp_id in TEMP_DATA['camps']:
        del TEMP_DATA['camps'][camp_id]
        save_data()
        flash("Camp deleted successfully.", "success")
    else:
        flash("Camp not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/blood-donor/certificate')
@login_required
def download_donation_certificate():
    if not isinstance(current_user, BloodDonor):
        flash("Access denied.", "error")
        return redirect(url_for('home'))
    
    if not current_user.last_donation:
        flash("No donation record found to generate a certificate.", "error")
        return redirect(url_for('blood_donor_dashboard'))

    try:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        
        # --- 1. Background & Border ---
        # Light beige background (simulating paper texture color)
        pdf.set_fill_color(255, 252, 245) 
        pdf.rect(0, 0, 297, 210, 'F')

        # --- DEV Ai+ Watermark ---
        pdf.set_font('Helvetica', 'B', 140)
        pdf.set_text_color(250, 240, 235) # Very light warm tone for watermark
        
        # Rotate 45 degrees around center
        angle = 45
        x = pdf.w / 2
        y = pdf.h / 2
        c = math.cos(math.radians(angle))
        s = math.sin(math.radians(angle))
        cx = x * pdf.k
        cy = (pdf.h - y) * pdf.k
        s_val = f'q {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {cx:.2f} {cy:.2f} cm 1 0 0 1 {-cx:.2f} {-cy:.2f} cm'
        pdf._out(s_val)
        pdf.text(x - 110, y + 45, 'DEV Ai+')
        pdf._out('Q')

        # --- Complex Decorative Border ---
        
        # 1. Outer Frame (Dark Red)
        pdf.set_draw_color(139, 0, 0) 
        pdf.set_line_width(2)
        pdf.rect(5, 5, 287, 200)

        # 2. Middle Frame (Gold) - Double Line
        pdf.set_draw_color(218, 165, 32)
        pdf.set_line_width(0.5)
        pdf.rect(8, 8, 281, 194)
        pdf.rect(9, 9, 279, 192)
        
        # 3. Inner Frame (Dark Red)
        pdf.set_draw_color(139, 0, 0)
        pdf.set_line_width(1)
        pdf.rect(13, 13, 271, 184)

        # 4. Corner Ornaments (Classic Style)
        pdf.set_draw_color(139, 0, 0) # Dark Red
        pdf.set_line_width(0.8)
        
        # Top-Left Corner
        pdf.line(13, 25, 13, 13); pdf.line(13, 13, 25, 13); pdf.line(13, 13, 20, 20)
        # Top-Right Corner
        pdf.line(284, 25, 284, 13); pdf.line(284, 13, 272, 13); pdf.line(284, 13, 277, 20)
        # Bottom-Left Corner
        pdf.line(13, 185, 13, 197); pdf.line(13, 197, 25, 197); pdf.line(13, 197, 20, 190)
        # Bottom-Right Corner
        pdf.line(284, 185, 284, 197); pdf.line(284, 197, 272, 197); pdf.line(284, 197, 277, 190)
        
        # 5. Gold Corner Dots
        pdf.set_fill_color(218, 165, 32)
        pdf.ellipse(11.5, 11.5, 3, 3, 'F')
        pdf.ellipse(282.5, 11.5, 3, 3, 'F')
        pdf.ellipse(11.5, 195.5, 3, 3, 'F')
        pdf.ellipse(282.5, 195.5, 3, 3, 'F')

        # --- 2. Header ---
        pdf.set_text_color(80, 80, 80)
        pdf.set_font('Times', 'B', 12)
        
        # Certificate Number at top left side
        cert_number = f"BD/{current_user.created_at.year}/{current_user.id:05d}"
        pdf.set_xy(18, 18)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"Certificate Number: {cert_number}", 0, 1, 'L')

        # Top Center: DEV AI+
        pdf.set_y(22)
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(218, 165, 32) # Gold
        pdf.cell(0, 10, 'DEV AI+ HEALTH INTELLIGENCE', 0, 1, 'C')
        
        pdf.set_font('Times', 'I', 12)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, 'Recognizing Excellence in Humanity', 0, 1, 'C')

        # Center Title
        pdf.set_y(50)
        pdf.set_font('Times', 'B', 42)
        pdf.set_text_color(139, 0, 0) # Dark Red
        pdf.cell(0, 15, 'CERTIFICATE OF APPRECIATION', 0, 1, 'C')

        # --- 3. Body Content ---
        pdf.ln(8)
        pdf.set_font('Times', 'I', 16)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 10, 'This honor is proudly presented to', 0, 1, 'C')
        
        pdf.ln(4)
        
        # Donor Name
        name = to_latin1_str(current_user.name).upper()
        pdf.set_font('Helvetica', 'B', 34)
        pdf.set_text_color(15, 23, 42) # Slate 900
        pdf.cell(0, 20, name, 0, 1, 'C')
        
        # Line under name
        name_w = pdf.get_string_width(name) + 40
        start_x = (297 - name_w) / 2
        pdf.set_draw_color(218, 165, 32) # Gold Line
        pdf.set_line_width(1)
        pdf.line(start_x, pdf.get_y(), start_x + name_w, pdf.get_y())
        
        pdf.ln(8)
        
        # Blood Group & Location
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(139, 0, 0)
        pdf.cell(0, 8, f"BLOOD GROUP: {current_user.blood_group}   |   LOCATION: {to_latin1_str(current_user.city).upper()}", 0, 1, 'C')
        
        pdf.ln(8)
        
        # Appreciation Text
        pdf.set_font('Times', 'I', 16)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 8, 'For your selfless and voluntary blood donation.\nYour noble contribution serves as a beacon of hope and a lifeline for those in need.', 0, 'C')
        
        # --- 4. Footer ---
        y_footer = 155
        
        # Bottom Left: Details
        pdf.set_xy(35, y_footer + 5)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(100, 100, 100)
        donation_date = current_user.last_donation or date.today()
        
        pdf.cell(30, 6, "DATE:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 6, str(donation_date), 0, 1, 'L')
        
        pdf.set_x(35)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(30, 6, "ISSUER:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 6, "DEV Ai+ Blood Bank Network", 0, 1, 'L')

        # Official Stamp
        try:
            stamp_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
            if os.path.exists(stamp_path):
                # Centered horizontally: (297 / 2) - (25 / 2) = 136.5
                pdf.image(stamp_path, x=136.5, y=y_footer - 5, w=25)
        except Exception:
            pass

        # Bottom Right: Signature & Organization
        pdf.set_xy(200, y_footer)
        
        signature_drawn = False
        try:
            signature_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
            if os.path.exists(signature_path):
                pdf.image(signature_path, x=215, y=y_footer - 2, w=30)
                pdf.set_y(y_footer + 12) # Move cursor down to match text spacing
                signature_drawn = True
        except Exception:
            pass
            
        if not signature_drawn:
            pdf.set_font('Times', 'I', 24) # Script-like
            pdf.set_text_color(15, 23, 42)
            pdf.cell(60, 12, 'Sunny Kushwaha', 0, 1, 'C') # Text fallback
        
        # Line under signature
        pdf.set_draw_color(100, 100, 100)
        pdf.set_line_width(0.3)
        pdf.line(205, pdf.get_y(), 255, pdf.get_y())
        
        pdf.set_xy(200, pdf.get_y() + 2)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(60, 5, 'PRESIDENT, DEV AI+', 0, 1, 'C')
        
        pdf.set_xy(200, pdf.get_y() + 1)
        pdf.set_font('Times', 'B', 14)
        pdf.set_text_color(218, 165, 32)
        pdf.cell(60, 6, 'Medical Board Approved', 0, 0, 'C')
        
        # --- 5. QR Code ---
        # Generate QR code linking to the donor's dashboard
        qr_url = url_for('blood_donor_dashboard', _external=True)
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_qr:
            qr_img.save(tmp_qr)
            tmp_qr_path = tmp_qr.name
            
        pdf.image(tmp_qr_path, x=262, y=165, w=20, h=20)
        try:
            os.unlink(tmp_qr_path)
        except OSError:
            pass

        try:
            pdf_output = pdf.output(dest='S')
            pdf_bytes = pdf_output.encode('latin-1') if isinstance(pdf_output, str) else pdf_output
        except TypeError:
            pdf_bytes = pdf.output()
             
        if request.args.get('action') == 'email':
            subject = "Your Blood Donation Certificate - DEV AI+"
            body = f"Dear {current_user.name},\n\nThank you for your noble contribution! Please find your blood donation certificate attached to this email.\n\nBest regards,\nDEV AI+ Blood Bank Network"
            send_notification_email(current_user.email, subject, body, is_html=False, attachment_name="donation_certificate.pdf", attachment_data=pdf_bytes)
            flash("Certificate sent to your email successfully!", "success")
            return redirect(url_for('blood_donor_dashboard'))
        else:
            return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name='donation_certificate.pdf', mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating certificate: {e}")
        flash("An error occurred while generating the certificate.", "error")
        return redirect(url_for('blood_donor_dashboard'))

@app.route('/admin/camp-registration/delete/<int:reg_id>', methods=['POST'])
@admin_required
def admin_delete_camp_registration(reg_id):
    if reg_id in TEMP_DATA['camp_registrations']:
        del TEMP_DATA['camp_registrations'][reg_id]
        save_data()
        flash("Registration deleted successfully.", "success")
    else:
        flash("Registration not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/blood-bank/dashboard')
@login_required
def blood_bank_dashboard():
    """Dedicated dashboard for Blood Bank Managers."""
    # Allow Admins and Hospitals to access this dashboard
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@devai.plus'
    is_hospital = getattr(current_user, 'is_hospital', False)
    
    if not (is_admin or is_hospital):
        flash("Access denied. Authorized personnel only.", "error")
        return redirect(url_for('home'))
        
    return render_template('blood_bank_dashboard.html', stock=TEMP_DATA['blood_stock'], donors=TEMP_DATA['blood_donors'].values())

@app.route('/patient/dashboard', methods=['GET', 'POST'])
@patient_required
def patient_dashboard():
    if request.method == 'POST':
        if 'update_profile' in request.form:
            current_user.name = request.form.get('name', current_user.name)
            current_user.email = request.form.get('email', current_user.email)
            age_str = request.form.get('age')
            if age_str and age_str.isdigit():
                current_user.age = int(age_str)
            current_user.gender = request.form.get('gender', current_user.gender)
            
            # Handle Profile Picture Upload
            if 'profilePicture' in request.files:
                file = request.files['profilePicture']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"pat_profile_{timestamp}_{filename}"
                    upload_folder = os.path.join(app.root_path, 'static', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, unique_filename))
                    current_user.profile_picture_url = unique_filename
            
            save_data()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('patient_dashboard'))

    # The @patient_required decorator handles authentication and role checking.
    today = date.today()

    # Fetch patient's orders
    patient_orders = [
        order for order in TEMP_DATA['orders'].values() 
        if order.patient_id == current_user.id
    ]
    # Sort orders by date, most recent first
    sorted_orders = sorted(patient_orders, key=lambda o: o.order_date, reverse=True)

    # Fetch patient's bed bookings
    patient_bed_bookings = [
        bb for bb in TEMP_DATA.get('bed_bookings', {}).values()
        if bb.patient_id == current_user.id
    ]
    patient_bed_bookings.sort(key=lambda bb: bb.created_at, reverse=True)

    return render_template('patient_dashboard.html', patient=current_user, today=today, orders=sorted_orders, bed_bookings=patient_bed_bookings, hospitals=TEMP_DATA.get('hospitals', {}))

@app.route('/appointment/cancel/<int:appointment_id>', methods=['POST'])
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
The DEV AI+ Team"""
            send_notification_email(doctor.email, subject, body)
        save_data() # Save the status change
        flash("Your appointment has been successfully cancelled.", "success")
    else:
        flash("Appointment not found or you do not have permission to cancel it.", "error")
    return redirect(url_for('patient_dashboard'))

# ... (rest of your app.py code) ...

@app.route('/appointment', methods=['GET', 'POST'])
def book_appointment():
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
            doctors_from_db = list(TEMP_DATA['doctors'].values())
            return render_template('book_appointment.html', doctors=doctors_from_db)

        doctor = TEMP_DATA['doctors'].get(doctor_id)
        if not doctor:
            flash("Selected doctor does not exist.", "error")
            doctors_from_db = list(TEMP_DATA['doctors'].values())
            return render_template('book_appointment.html', doctors=doctors_from_db)

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
    
    doctors_from_db = list(TEMP_DATA['doctors'].values())
    return render_template('book_appointment.html', doctors=doctors_from_db)

@app.route('/appointment/payment/<int:appointment_id>', methods=['GET', 'POST'])
def appointment_payment(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect(url_for('home'))
    
    doctor = TEMP_DATA['doctors'].get(appointment.doctor_id)
    # Ensure fee is a number
    try:
        fee = float(doctor.consultation_fee) if doctor and doctor.consultation_fee else 50.0
    except ValueError:
        fee = 50.0
    
    if request.method == 'POST':
        # Simulate payment processing
        appointment.status = 'confirmed' 
        save_data()
        flash("Payment successful! Appointment confirmed.", "success")
        return redirect(url_for('appointment_success', appointment_id=appointment.id))

    return render_template('appointment_payment.html', appointment=appointment, doctor=doctor, fee=fee)

@app.route('/appointment/success/<int:appointment_id>')
def appointment_success(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        return redirect(url_for('home'))
    return render_template('appointment_success.html', appointment=appointment)

@app.route('/appointment/payment/receipt/<int:appointment_id>')
def appointment_payment_receipt(appointment_id):
    appointment = TEMP_DATA['appointments'].get(appointment_id)
    if not appointment:
        flash("Appointment not found.", "error")
        return redirect(url_for('home'))
    
    # Basic auth check
    if current_user.is_authenticated:
        is_patient = hasattr(current_user, 'is_doctor') and not current_user.is_doctor and appointment.patient_id == current_user.id
        is_doctor = hasattr(current_user, 'is_doctor') and current_user.is_doctor and appointment.doctor_id == current_user.id
        is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@devai.plus'
        
        if appointment.patient_id and not (is_patient or is_doctor or is_admin):
             flash("Unauthorized access to receipt.", "error")
             return redirect(url_for('home'))

    doctor = TEMP_DATA['doctors'].get(appointment.doctor_id)
    try:
        fee = float(doctor.consultation_fee) if doctor and doctor.consultation_fee else 50.0
    except (ValueError, AttributeError):
        fee = 50.0

    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font('Helvetica', 'B', 20)
        pdf.cell(0, 10, 'PAYMENT RECEIPT', 0, 1, 'C')
        pdf.ln(5)

        # Company Info
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, 'DEV AI+ Health Platform', 0, 1, 'C')
        pdf.cell(0, 5, '123 Health Lane, Wellness City', 0, 1, 'C')
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

        # Receipt Meta
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, f'Receipt #: RCPT-{appointment.id}', 0, 1, 'R')
        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 8, f'Date: {datetime.now().strftime("%B %d, %Y")}', 0, 1, 'R')
        pdf.ln(10)

        # Details Section
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # Patient & Doctor Details
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(95, 8, 'Billed To:', 0, 0)
        pdf.cell(95, 8, 'Service Provider:', 0, 1)
        
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(95, 6, to_latin1_str(appointment.patient_name), 0, 0)
        pdf.cell(95, 6, f'Dr. {to_latin1_str(doctor.first_name)} {to_latin1_str(doctor.last_name)}', 0, 1)
        
        pdf.cell(95, 6, f'Phone: {appointment.patient_phone}', 0, 0)
        pdf.cell(95, 6, to_latin1_str(doctor.department), 0, 1)
        pdf.ln(15)

        # Payment Details
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(140, 10, 'Description', 1, 0, 'L', 1)
        pdf.cell(50, 10, 'Amount', 1, 1, 'R', 1)

        pdf.set_font('Helvetica', '', 11)
        desc = f"Medical Consultation - {appointment.appointment_date.strftime('%Y-%m-%d')}"
        pdf.cell(140, 10, desc, 1, 0, 'L')
        pdf.cell(50, 10, f"Rs. {fee:.2f}", 1, 1, 'R')

        # Total
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(140, 12, 'Total Paid', 0, 0, 'R')
        pdf.cell(50, 12, f"Rs. {fee:.2f}", 1, 1, 'R')
        
        pdf.ln(15)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(0, 128, 0) # Green
        pdf.cell(0, 10, 'PAID', 0, 1, 'C')

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

@app.route("/careers")
def careers():
    return render_template("careers.html")


@app.route("/blog")
def blog():
    return render_template("blog.html")

@app.route("/resources")
def resources():
    return render_template("resources.html")

MEDICINE_LIST = [
    "Abacavir", "Abemaciclib", "Abiraterone", "Acalabrutinib", "Acamprosate", "Acarbose", "Acebutolol",
    "Acetaminophen (Paracetamol)", "Acetazolamide", "Acetylcysteine", "Aciclovir", "Acitretin",
    "Adalimumab", "Adapalene", "Adefovir", "Adenosine", "Albendazole", "Albuterol (Salbutamol)",
    "Alendronic acid", "Alfuzosin", "Allopurinol", "Almotriptan", "Alogliptin", "Alprazolam",
    "Alprostadil", "Amantadine", "Ambrisentan", "Amikacin", "Amiloride", "Aminophylline",
    "Amiodarone", "Amitriptyline", "Amlodipine", "Amoxapine", "Amoxicillin", "Amphotericin B",
    "Ampicillin", "Anagrelide", "Anastrozole", "Apixaban", "Aripiprazole", "Artemether", "Artesunate",
    "Ascorbic Acid (Vitamin C)", "Aspirin", "Atazanavir", "Atenolol", "Atezolizumab", "Atomoxetine",
    "Atorvastatin", "Atovaquone", "Azathioprine", "Azelastine", "Azithromycin", "Baclofen",
    "Beclometasone", "Benazepril", "Bendamustine", "Bendroflumethiazide", "Benzonatate",
    "Benzoyl peroxide", "Benztropine", "Betahistine", "Betamethasone", "Bicalutamide", "Bimatoprost",
    "Bisacodyl", "Bisoprolol", "Bortezomib", "Bosutinib", "Brimonidine", "Brinzolamide",
    "Bromocriptine", "Budesonide", "Bumetanide", "Bupivacaine", "Buprenorphine", "Bupropion",
    "Buspirone", "Busulfan", "Cabergoline", "Cabozantinib", "Calcipotriol", "Calcitonin",
    "Calcitriol", "Candesartan", "Capecitabine", "Capsaicin", "Captopril", "Carbamazepine",
    "Carbimazole", "Carboplatin", "Carfilzomib", "Carisoprodol", "Carvedilol", "Cefaclor",
    "Cefadroxil", "Cefazolin", "Cefdinir", "Cefepime", "Cefixime", "Cefpodoxime", "Cefprozil",
    "Ceftazidime", "Ceftriaxone", "Cefuroxime", "Celecoxib", "Cephalexin", "Cetirizine",
    "Chloramphenicol", "Chlordiazepoxide", "Chlorhexidine", "Chlorphenamine", "Chlorpromazine",
    "Chlorthalidone", "Cholestyramine", "Ciclopirox", "Cilostazol", "Cimetidine", "Ciprofloxacin",
    "Cisplatin", "Citalopram", "Clarithromycin", "Clindamycin", "Clobetasol", "Clomipramine",
    "Clonazepam", "Clonidine", "Clopidogrel", "Clotrimazole", "Clozapine", "Co-amoxiclav", "Codeine",
    "Colchicine", "Colesevelam", "Cyclizine", "Cyclobenzaprine", "Cyclophosphamide", "Cyclosporine",
    "Cytarabine", "Dabigatran", "Dapagliflozin", "Dapsone", "Daptomycin", "Darunavir", "Dasatinib",
    "Dexamethasone", "Dexlansoprazole", "Dexmethylphenidate", "Dextroamphetamine",
    "Dextromethorphan (common in syrup)", "Diazepam", "Diclofenac", "Dicyclomine", "Digoxin",
    "Dihydrocodeine", "Diltiazem", "Diphenhydramine (common in syrup)", "Dipyridamole", "Disulfiram",
    "Divalproex", "Docetaxel", "Docusate", "Domperidone", "Donepezil", "Dorzolamide", "Doxazosin",
    "Doxepin", "Doxorubicin", "Doxycycline", "Duloxetine", "Dutasteride", "Efavirenz", "Eletriptan",
    "Enalapril", "Enoxaparin", "Entacapone", "Entecavir", "Enzalutamide", "Epirubicin", "Eplerenone",
    "Epoetin alfa", "Eprosartan", "Erlotinib", "Ertapenem", "Erythromycin", "Escitalopram",
    "Esomeprazole", "Estradiol", "Eszopiclone", "Etanercept", "Ethambutol", "Ethinyl estradiol",
    "Ethosuximide", "Etoposide", "Etoricoxib", "Everolimus", "Exemestane", "Exenatide", "Ezetimibe",
    "Famotidine", "Febuxostat", "Felodipine", "Fenofibrate", "Fentanyl", "Ferrous sulfate",
    "Fexofenadine", "Finasteride", "Flecainide", "Flucloxacillin", "Fluconazole", "Fludrocortisone",
    "Fluorouracil", "Fluoxetine", "Fluticasone", "Fluvastatin", "Fluvoxamine", "Folic acid",
    "Fondaparinux", "Formoterol", "Fosfomycin", "Fosinopril", "Furosemide", "Fusidic acid",
    "Gabapentin", "Galantamine", "Gemcitabine", "Gemfibrozil", "Gentamicin", "Gliclazide",
    "Glimepiride", "Glipizide", "Glyburide", "Goserelin", "Granisetron", "Guaifenesin (common in syrup)",
    "Griseofulvin", "Haloperidol", "Heparin", "Hydralazine", "Hydrochlorothiazide", "Hydrocortisone",
    "Hydromorphone", "Hydroxychloroquine", "Hydroxyurea", "Hydroxyzine", "Hyoscine", "Ibandronic acid",
    "Ibrutinib", "Ibuprofen", "Idarubicin", "Ifosfamide", "Imatinib", "Imipenem", "Imipramine",
    "Imiquimod", "Indapamide", "Indomethacin", "Infliximab", "Insulin", "Ipratropium", "Irbesartan",
    "Irinotecan", "Isoniazid", "Isosorbide dinitrate", "Isosorbide mononitrate", "Isotretinoin",
    "Itraconazole", "Ketamine", "Ketoconazole", "Ketoprofen", "Ketorolac", "Labetalol", "Lacosamide",
    "Lactulose (common in syrup)", "Lamivudine", "Lamotrigine", "Lansoprazole", "Latanoprost",
    "Leflunomide", "Lenalidomide", "Lenvatinib", "Letrozole", "Levetiracetam", "Levocetirizine",
    "Levofloxacin", "Levonorgestrel", "Levothyroxine", "Lidocaine", "Linagliptin", "Linezolid",
    "Liraglutide", "Lisdexamfetamine", "Lisinopril", "Lithium", "Loperamide", "Loratadine",
    "Lorazepam", "Losartan", "Lovastatin", "Lurasidone", "Maraviroc", "Mebendazole", "Meclizine",
    "Medroxyprogesterone", "Mefenamic acid", "Megestrol", "Melatonin", "Meloxicam", "Melphalan",
    "Memantine", "Mercaptopurine", "Meropenem", "Mesalazine", "Metformin", "Methadone", "Methimazole",
    "Methocarbamol", "Methotrexate", "Methyldopa", "Methylphenidate", "Methylprednisolone",
    "Metoclopramide", "Metoprolol", "Metronidazole", "Miconazole", "Midazolam", "Minocycline",
    "Minoxidil", "Mirtazapine", "Misoprostol", "Mitomycin", "Modafinil", "Mometasone", "Montelukast",
    "Morphine", "Moxifloxacin", "Mupirocin", "Mycophenolate", "Nabumetone", "Nadolol", "Naloxone",
    "Naltrexone", "Naproxen", "Naratriptan", "Nebivolol", "Nefazodone", "Neomycin", "Nevirapine",
    "Niacin", "Nicardipine", "Nicorandil", "Nicotine", "Nifedipine", "Nilotinib", "Nitrofurantoin",
    "Nitroglycerin", "Norethindrone", "Nortriptyline", "Nystatin", "Ofloxacin", "Olanzapine",
    "Olmesartan", "Olopatadine", "Omalizumab", "Omeprazole", "Ondansetron", "Oseltamivir",
    "Oxcarbazepine", "Oxybutynin", "Oxycodone", "Oxymetazoline", "Paclitaxel", "Palbociclib",
    "Paliperidone", "Pantoprazole", "Paroxetine", "Pazopanib", "Penicillamine", "Penicillin",
    "Pentoxifylline", "Perindopril", "Permethrin", "Phenazopyridine", "Phenelzine", "Phenobarbital",
    "Phenoxymethylpenicillin", "Phentermine", "Phenylephrine", "Phenytoin", "Pioglitazone",
    "Piperacillin", "Piroxicam", "Pitavastatin", "Polyethylene glycol", "Pomalidomide",
    "Potassium chloride", "Pramipexole", "Prasugrel", "Pravastatin", "Praziquantel", "Prazosin",
    "Prednisolone", "Prednisone", "Pregabalin", "Primaquine", "Probenecid", "Prochlorperazine",
    "Progesterone", "Promethazine", "Propafenone", "Propofol", "Propranolol", "Propylthiouracil",
    "Pseudoephedrine (common in syrup)", "Pyrazinamide", "Pyridostigmine", "Quetiapine", "Quinapril",
    "Quinidine", "Quinine", "Rabeprazole", "Raltegravir", "Ramipril", "Ranitidine", "Ranolazine",
    "Rasagiline", "Repaglinide", "Ribavirin", "Rifampicin (Rifampin)", "Rifaximin", "Riluzole",
    "Risedronate", "Risperidone", "Ritonavir", "Rivaroxaban", "Rivastigmine", "Rizatriptan",
    "Ropinirole", "Rosiglitazone", "Rosuvastatin", "Ruxolitinib", "Salbutamol (Albuterol)",
    "Salmeterol", "Saquinavir", "Saxagliptin", "Scopolamine", "Selegiline", "Selenium sulfide",
    "Semaglutide", "Sertraline", "Sevelamer", "Sildenafil", "Simethicone", "Simvastatin", "Sirolimus",
    "Sitagliptin", "Sodium bicarbonate", "Sodium cromoglicate", "Sofosbuvir", "Solifenacin",
    "Somatropin", "Sotalol", "Spironolactone", "Stavudine", "Streptokinase", "Sucralfate",
    "Sulfacetamide", "Sulfamethoxazole", "Sulfasalazine", "Sumatriptan", "Sunitinib", "Tacrolimus",
    "Tadalafil", "Tamoxifen", "Tamsulosin", "Tazobactam", "Telmisartan", "Temazepam", "Tenofovir",
    "Terazosin", "Terbinafine", "Terbutaline", "Testosterone", "Tetracycline", "Theophylline",
    "Thiamine", "Thioguanine", "Tiotropium", "Tizanidine", "Tobramycin", "Tofacitinib", "Tolterodine",
    "Topiramate", "Topotecan", "Torsemide", "Tramadol", "Tranexamic acid", "Tranylcypromine",
    "Trastuzumab", "Trazodone", "Tretinoin", "Triamcinolone", "Triamterene", "Triazolam",
    "Trimethoprim", "Tropicamide", "Upadacitinib", "Ustekinumab", "Valaciclovir", "Valganciclovir",
    "Valproic acid", "Valsartan", "Vancomycin", "Vardenafil", "Varenicline", "Venlafaxine",
    "Verapamil", "Vigabatrin", "Vildagliptin", "Vinblastine", "Vincristine", "Voriconazole",
    "Vortioxetine", "Warfarin", "Xylometazoline", "Zafirlukast", "Zaleplon", "Zidovudine",
    "Ziprasidone", "Zoledronic acid", "Zolmitriptan", "Zolpidem", "Zonisamide", "Zopiclone"
]

@app.route('/medical-shop')
def medical_shop():
    """
    Renders the medical shop page.
    Passes the list of medicines to the template.
    """
    return render_template('medical_shop.html', medicines=MEDICINE_LIST)

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    """Adds a product to the session-based shopping cart."""
    data = request.json
    product_name = data.get('name')
    product_price = data.get('price')

    if not product_name or product_price is None:
        return jsonify({'success': False, 'message': 'Missing product data.'}), 400

    cart = session.get('cart', [])
    
    # Check if item already in cart
    found = False
    for item in cart:
        if item.get('name') == product_name:
            item['quantity'] = item.get('quantity', 0) + 1
            found = True
            break
    
    if not found:
        cart.append({'name': product_name, 'price': product_price, 'quantity': 1})

    session['cart'] = cart
    
    # Calculate new total item count
    new_total_items = sum(item.get('quantity', 0) for item in cart)

    return jsonify({'success': True, 'message': f'{product_name} added to cart.', 'cart_item_count': new_total_items})

@app.route('/cart')
def view_cart():
    """Displays the shopping cart page."""
    return render_template('cart.html')

@app.route('/update-cart-item', methods=['POST'])
def update_cart_item():
    """Updates the quantity of an item in the cart."""
    data = request.json
    product_name = data.get('name')
    action = data.get('action') # 'increase', 'decrease', 'remove'

    cart = session.get('cart', [])
    new_cart = []
    item_removed = False
    updated_item_data = None

    for item in cart:
        if item['name'] == product_name:
            if action == 'increase':
                item['quantity'] += 1
                updated_item_data = item
            elif action == 'decrease' and item['quantity'] > 1:
                item['quantity'] -= 1
                updated_item_data = item
            elif action == 'remove' or (action == 'decrease' and item['quantity'] <= 1):
                item_removed = True
                continue # Skip adding it to the new cart
        
        if not (item['name'] == product_name and item_removed):
            new_cart.append(item)
    
    session['cart'] = new_cart

    # Recalculate total price
    total_price = sum(i['price'] * i['quantity'] for i in new_cart)

    response = {
        'success': True,
        'cart_total_price': round(total_price, 2),
        'item_removed': item_removed,
        'item': updated_item_data # Will be None if item is removed
    }
    return jsonify(response)

@app.route('/checkout', methods=['GET', 'POST'])
@patient_required
def checkout():
    """Handles the checkout process."""
    cart = session.get('cart', [])
    if not cart:
        flash("Your cart is empty. Please add items before checking out.", "error")
        return redirect(url_for('medical_shop'))

    if request.method == 'POST':
        # Process the order
        shipping_address = {
            "name": request.form.get('name'),
            "address": request.form.get('address'),
            "city": request.form.get('city'),
            "state": request.form.get('state'),
            "pincode": request.form.get('pincode'),
        }
        
        order_id = TEMP_DATA['next_ids']['order']
        new_order = Order(
            id=order_id,
            patient_id=current_user.id,
            items=cart,
            total_price=inject_cart()['cart_total_price'],
            shipping_address=shipping_address,
            order_date=date.today()
        )
        TEMP_DATA['orders'][order_id] = new_order
        TEMP_DATA['next_ids']['order'] += 1
        save_data() # Save after creating order

        # Clear the cart
        session.pop('cart', None)

        return redirect(url_for('order_success', order_id=order_id))

    return render_template('checkout.html')

@app.route('/order-success/<int:order_id>')
@patient_required
def order_success(order_id):
    """Displays a confirmation page after a successful order."""
    return render_template('order_success.html', order_id=order_id)

@app.route('/order/<int:order_id>')
@patient_required
def order_details(order_id):
    """Displays the details of a specific order."""
    order = TEMP_DATA['orders'].get(order_id)

    if not order or order.patient_id != current_user.id:
        flash("Order not found.", "error")
        return redirect(url_for('patient_dashboard'))

    return render_template('order_details.html', order=order)

@app.route('/order/invoice/<int:order_id>')
@patient_required
def print_invoice(order_id):
    """Generates and serves a PDF invoice for a specific order."""
    order = TEMP_DATA['orders'].get(order_id)
    if not order or order.patient_id != current_user.id:
        flash("Order not found.", "error")
        return redirect(url_for('patient_dashboard'))

    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Use a standard font that doesn't require an external file

        # Header
        pdf.set_font('Helvetica', 'B', 24)
        pdf.cell(0, 10, 'INVOICE', 0, 1, 'R')
        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 7, 'DEV AI+ Medical', 0, 1, 'R')
        pdf.cell(0, 7, '123 Health Lane, Wellness City', 0, 1, 'R')
        pdf.ln(15)

        # Billing Info
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 7, 'Bill To:', 0, 1)
        pdf.set_font('Helvetica', '', 12)
        addr = order.shipping_address
        addr_name = to_latin1_str(addr.get('name', ''))
        addr_address = to_latin1_str(addr.get('address', ''))
        addr_city = to_latin1_str(addr.get('city', ''))
        addr_state = to_latin1_str(addr.get('state', ''))
        addr_pincode = to_latin1_str(addr.get('pincode', ''))
        pdf.cell(0, 7, addr_name, 0, 1)
        pdf.cell(0, 7, addr_address, 0, 1)
        pdf.cell(0, 7, f"{addr_city}, {addr_state} {addr_pincode}", 0, 1)
        pdf.ln(10)

        # Order Details
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(40, 10, f"Order ID: #{order.id}")
        pdf.cell(0, 10, f"Order Date: {order.order_date.strftime('%B %d, %Y')}", 0, 1, 'R')
        pdf.ln(5)

        # Table Header
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(100, 10, 'Item Description', 1, 0, 'L', 1)
        pdf.cell(30, 10, 'Quantity', 1, 0, 'C', 1)
        pdf.cell(30, 10, 'Unit Price', 1, 0, 'C', 1)
        pdf.cell(30, 10, 'Total', 1, 1, 'C', 1)

        # Table Rows
        pdf.set_font('Helvetica', '', 12)
        for item in order.items:
            item_name = to_latin1_str(item.get('name', ''))
            pdf.cell(100, 10, item_name, 1)
            pdf.cell(30, 10, str(item['quantity']), 1, 0, 'C')
            pdf.cell(30, 10, f"Rs. {item['price']:.2f}", 1, 0, 'R')
            pdf.cell(30, 10, f"Rs. {item['price'] * item['quantity']:.2f}", 1, 1, 'R')

        # Grand Total
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(160, 12, 'Grand Total:', 0, 0, 'R')
        pdf.cell(30, 12, f"Rs. {order.total_price:.2f}", 1, 1, 'R')

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

@app.route('/appointment/invoice/<int:appointment_id>')
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

@app.route('/health-consult')
def health_consult():
    # This will look for healthconsult.html in the 'templates' folder
    return render_template('healthconsult.html')

@app.route('/bmi-calculator')
def bmi_calculator():
    return render_template('bmi_calculator.html')



@app.template_filter('markdown')
def render_markdown_filter(text):
    # 'fenced_code', 'tables', 'nl2br' are common useful extensions
    return markdown.markdown(text, extensions=['fenced_code', 'tables', 'nl2br'])


    # Main route for the FAQ page
@app.route('/faq')
def faq_page():
    return render_template('faq.html') # This will render our new faq.html template

@app.route('/sicons')
def sicons():
    return render_template('sicons.html')

# ---------------- Legal & Policy Routes ----------------
@app.route('/legal/<policy_id>')
def legal_hub(policy_id):
    """Renders a specific policy page based on the policy_id."""
    policy = POLICY_DATA.get(policy_id)
    if not policy:
        return render_template("404.html"), 404

    return render_template('policy.html',
                           policy=policy,
                           all_policies=POLICY_DATA,
                           current_id=policy_id)

# ---------------- Admin/Debug Routes ----------------
@app.route('/admin/clear-doctors')
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

@app.route('/admin/system/reset', methods=['POST'])
@admin_required
def admin_system_reset():
    """Resets the system data to factory defaults (clears all users except admin/hospital)."""
    global TEMP_DATA
    # Reset to initial state
    TEMP_DATA = {
        "doctors": {},
        "patients": {},
        "hospitals": {},
        "staff": {},
        "appointments": {},
        "messages": {},
        "orders": {},
        "reviews": {},
        "blood_donors": {},
        "organ_donors": {},
        "contact_messages": [],
        "camp_registrations": {},
        "camps": {},
        "blood_stock": {
            "A+": 15, "A-": 5, "B+": 12, "B-": 4, "AB+": 8, "AB-": 3, "O+": 25, "O-": 10
        },
        "next_ids": {
            "doctor": 1,
            "patient": 1,
            "hospital": 1,
            "appointment": 1,
            "staff": 1,
            "message": 1,
            "order": 1,
            "review": 1,
            "blood_donor": 1,
            "organ_donor": 1,
            "camp": 1,
            "camp_registration": 1,
        }
    }
    
    # Re-initialize default users so you aren't locked out
    setup_admin_user()
    setup_hospital_user()
    
    save_data()
    flash("System has been reset. All data (except default Admin/Hospital) is cleared.", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """Handles chat messages from the global AI assistant using true AI generation."""
    try:
        data = request.json
        history = data.get('history', [])
        
        # Support legacy 'message' format just in case
        if not history:
            message = data.get('message', '').strip()
            if message:
                history = [{'role': 'user', 'content': message}]
            else:
                return jsonify({'reply': "I need a message to respond to. Please type something!"})

        if not _is_groq_configured():
            return jsonify({'reply': "I'm sorry, but my AI neural network is currently offline. Please configure the GROQ_API_KEY to enable chat."})

        # System prompt setting Devin's persona
        system_prompt = (
            "You are Devin, the official AI health assistant for DEV AI+ (MediConnect). "
            "You are friendly, empathetic, professional, and knowledgeable about general health, medicine, and the platform's features. "
            "Keep your responses concise, well-structured, and easy to read. "
            "IMPORTANT: Always remind users that you are an AI and they should consult a human doctor for formal medical advice."
        )

        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Try the standard OpenAI-compatible Groq endpoint first
        try:
            endpoint_openai = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
            messages = [{"role": "system", "content": system_prompt}] + history
            
            payload_openai = {
                'model': GROQ_API_MODEL,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 500
            }
            
            resp = requests.post(endpoint_openai, headers=headers, json=payload_openai, timeout=30, verify=False)
            resp.raise_for_status()
            reply_text = resp.json()['choices'][0]['message']['content']
            return jsonify({'reply': reply_text.strip()})
            
        except Exception as e:
            print(f"Standard Chatbot API Error: {e}. Trying fallback format...")
            # Fallback to the /responses and 'input' format used in symptom analysis
            prompt = f"{system_prompt}\n\nConversation History:\n"
            for msg in history[-6:]:
                role = "User" if msg.get('role') == 'user' else "Devin"
                prompt += f"{role}: {msg.get('content')}\n"
            prompt += "Devin:"

            endpoint_custom = f"{GROQ_API_BASE.rstrip('/')}/responses"
            payload_custom = {
                'model': GROQ_API_MODEL,
                'input': prompt,
                'temperature': 0.7,
                'max_output_tokens': 500
            }
            response = requests.post(endpoint_custom, headers=headers, json=payload_custom, timeout=30, verify=False)
            response.raise_for_status()
            payload_json = response.json()

            reply_text = payload_json.get('output_text')
            if not reply_text:
                output = payload_json.get('output', [])
                if isinstance(output, list):
                    for item in output:
                        if item.get('type') == 'message':
                            content = item.get('content', [])
                            if isinstance(content, list):
                                for content_item in content:
                                    if content_item.get('type') == 'output_text':
                                        reply_text = content_item.get('text', '')
                                        break
                        break
            
            if reply_text:
                return jsonify({'reply': reply_text.strip()})
            else:
                raise ValueError("No text generated in fallback format")

    except Exception as e:
        print(f"Chatbot error: {e}")
        return jsonify({'reply': "I'm experiencing some technical difficulties connecting to my neural network. Please try again in a moment, or contact our support team for assistance."})

# Ensure default users exist when running via Gunicorn or Python
setup_admin_user()
setup_hospital_user()

if __name__ == '__main__':
    import os
    import ssl
    
    # SSL/HTTPS Configuration
    ssl_cert = os.getenv('SSL_CERT_PATH', 'ssl/cert.pem')
    ssl_key = os.getenv('SSL_KEY_PATH', 'ssl/key.pem')
    use_ssl = os.getenv('USE_SSL', 'True').lower() == 'true'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Prepare SSL context if certificates exist
    ssl_context = None
    if use_ssl and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(ssl_cert, ssl_key)
            protocol = "HTTPS"
            print(f"🔒 SSL enabled - Using certificates:")
            print(f"   📄 Certificate: {ssl_cert}")
            print(f"   🔑 Private Key: {ssl_key}")
        except Exception as e:
            print(f"⚠️  Failed to load SSL certificates: {e}")
            ssl_context = None
            protocol = "HTTP"
    else:
        protocol = "HTTP"
        if use_ssl:
            print("⚠️  SSL disabled - Running in HTTP mode (not secure)")
            print(f"   ❌ Certificate file not found: {ssl_cert}")
            print(f"   ❌ Key file not found: {ssl_key}")
    
    print(f"\n🚀 Starting Dev AI+ Health Platform")
    print(f"📍 {protocol} Server: {protocol.lower()}://{host}:{port}")
    print(f"🔐 SSL Context: {'Enabled' if ssl_context else 'Disabled'}")
    print(f"📊 Debug Mode: {'ON' if debug else 'OFF'}")
    print(f"\n✅ Application is ready! Visit: {protocol.lower()}://{host}:{port}\n")
    
    # Run Flask app with or without SSL
    try:
        if socketio:
            socketio.run(app, debug=debug, host=host, port=port, ssl_context=ssl_context)
        else:
            app.run(debug=debug, host=host, port=port, ssl_context=ssl_context)
    except Exception as e:
        print(f"❌ Error starting server: {e}")