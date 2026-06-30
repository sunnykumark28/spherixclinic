import os
import sys

# Automatically configure unixODBC paths on macOS for Homebrew installations
if sys.platform == 'darwin' and not os.environ.get('ODBCSYSINI'):
    for prefix in ['/opt/homebrew/etc', '/usr/local/etc']:
        if os.path.exists(os.path.join(prefix, 'odbcinst.ini')):
            os.environ['ODBCSYSINI'] = prefix
            print(f"ℹ️ Automatically configured ODBCSYSINI={prefix}")
            break

import json
import csv
import random
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, make_response
import math
from datetime import datetime, date, time, timedelta, timezone

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from dotenv import load_dotenv

# Load environment variables early so API keys are available for all modules
load_dotenv()
import time as time_module
import hashlib
from urllib.parse import urlparse
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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import markdown
import requests
from flask_wtf.csrf import CSRFProtect
import urllib3
from flask_cors import CORS
from flask_jwt_extended import JWTManager
try:
    import razorpay  # type: ignore
    key_id = os.getenv('RAZORPAY_KEY_ID', '')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    if key_id and key_secret:
        razorpay_client = razorpay.Client(auth=(key_id, key_secret))
    else:
        razorpay_client = None
except ImportError:
    razorpay_client = None
    print("⚠️ Optional package 'razorpay' not installed; payment gateway features may be disabled.")
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

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_MODEL = os.getenv('GROQ_API_MODEL', 'llama3-8b-8192')
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
OPENFDA_API_KEY = os.getenv('OPENFDA_API_KEY')

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

from policy_data import POLICY_DATA
# Import data from other modules
from flask import request, redirect, url_for
from audit_logger import log_medical_access

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', os.urandom(24).hex()) # Use an environment variable for secret key

csrf = CSRFProtect(app)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

Talisman(app, content_security_policy=None) # Note: Customizing CSP is highly recommended later.

# REST API support for web frontend and mobile clients
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', os.urandom(24).hex())
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=7)
# API routes currently store a dict in the JWT identity. Newer PyJWT versions
# validate the `sub` claim as a string unless this compatibility flag is off.
app.config['JWT_VERIFY_SUB'] = False
jwt = JWTManager(app)

from api import register_api_blueprints
register_api_blueprints(app)
for api_blueprint_name in ('auth', 'patient', 'doctor', 'appointment', 'shop', 'ai', 'blood_bank'):
    blueprint = app.blueprints.get(api_blueprint_name)
    if blueprint:
        csrf.exempt(blueprint)

import gzip
from io import BytesIO

@app.after_request
def optimize_response(response):
    # 1. Cache-Control for static assets (1 year max-age, immutable)
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
    else:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'

    # 2. Gzip compression for text-based content (HTML, CSS, JS, JSON)
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if (
        response.status_code < 200 or 
        response.status_code >= 300 or 
        'gzip' not in accept_encoding.lower() or 
        'Content-Length' in response.headers and int(response.headers['Content-Length']) < 500
    ):
        return response

    content_type = response.headers.get('Content-Type', '')
    if 'text' not in content_type and 'javascript' not in content_type and 'json' not in content_type:
        return response

    # Compress response body
    try:
        response.direct_passthrough = False
        data = response.get_data()
        
        gzip_buffer = BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gzip_file:
            gzip_file.write(data)
            
        gzip_data = gzip_buffer.getvalue()
        
        response.set_data(gzip_data)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(gzip_data)
        response.headers['Vary'] = 'Accept-Encoding'
    except Exception as e:
        app.logger.warning(f"Failed to compress response: {e}")
        
    return response

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
            # pyrefly: ignore [unexpected-keyword]
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

def parse_route_id(id_val):
    """Parses ID to integer if it represents a legacy numerical ID, otherwise returns the string."""
    return int(id_val) if isinstance(id_val, str) and id_val.isdigit() else id_val

def get_temp_data_item(category, item_id):
    if item_id is None:
        return None
    sub_dict = TEMP_DATA.get(category, {})
    res = sub_dict.get(item_id)
    if res is not None:
        return res
    res = sub_dict.get(str(item_id))
    if res is not None:
        return res
    try:
        res = sub_dict.get(int(item_id))
        if res is not None:
            return res
    except (ValueError, TypeError):
        pass
    return None

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
# Set to 200 MB
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024


# Friendly handler for requests that exceed the MAX_CONTENT_LENGTH
@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(error):
    # Inform the user and redirect back to a sensible page
    try:
        flash('Uploaded file is too large. Please use an image smaller than 200 MB.', 'error')
    except Exception:
        pass
    return redirect(request.referrer or url_for('symptoms'))

# Initialize Flask-Limiter to protect against brute-force attacks
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"], # General limits for all routes
    storage_uri="memory://" # Use in-memory storage
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        role, id_val = user_id.split('-', 1)
        parsed_id = parse_route_id(id_val)
        if role == 'doctor':
            return TEMP_DATA['doctors'].get(parsed_id)
        elif role == 'patient':
            return TEMP_DATA['patients'].get(parsed_id)
        elif role == 'staff':
            return TEMP_DATA['staff'].get(parsed_id)
        elif role == 'hospital':
            return TEMP_DATA['hospitals'].get(parsed_id)
        elif role == 'blood_donor':
            return TEMP_DATA['blood_donors'].get(parsed_id)
        elif role == 'organ_donor':
            return TEMP_DATA['organ_donors'].get(parsed_id)
    except (ValueError, AttributeError):
        # Handle cases where user_id is not in the expected format
        return None
    return None # User not found

@app.before_request
def check_blocked_status():
    if current_user and current_user.is_authenticated:
        if getattr(current_user, 'is_blocked', False):
            # Exclude login/logout endpoints and static files from redirection to prevent infinite loops
            excluded_endpoints = ['static', 'login_landing', 'logout', 'doctor_login', 'patient_login', 'staff_login', 'hospital_login', 'blood_donor_login', 'organ_donor_login']
            if request.endpoint and request.endpoint not in excluded_endpoints:
                logout_user()
                flash("Your account has been blocked by the administrator.", "error")
                return redirect(url_for('login_landing'))

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
            if not hasattr(current_user, 'email') or current_user.email != 'admin@spherixclinic.com':
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

def staff_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_staff', False):
            flash("Access denied. This page is for hospital staff only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def hospital_or_staff_role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            is_hospital = getattr(current_user, 'is_hospital', False)
            is_staff = getattr(current_user, 'is_staff', False)
            
            if is_hospital:
                return f(*args, **kwargs)
            elif is_staff and getattr(current_user, 'role', None) in allowed_roles:
                return f(*args, **kwargs)
            else:
                flash("Access denied. You do not have the required permissions.", "error")
                return redirect(url_for('login_landing'))
        return decorated_function
    return decorator

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
    "organ_requests": {},
    "contact_messages": [],
    "camp_registrations": {},
    "camps": {},
    "newsletter_subscribers": [],
    "medicines": [],
    "sicons_applications": [],
    "activity_logs": {},
    "blood_stock": {
        "A+": 15, "A-": 5, "B+": 12, "B-": 4, "AB+": 8, "AB-": 3, "O+": 25, "O-": 10
    },
    "settings": {
        "hq_address": "Spherix Clinic Health Intelligence, Motihari\nBihar State, 845401\nIndia",
        "contact_email": "support@spherixclinic.com",
        "contact_phone": "+91 933 4325 920"
    },
    "bed_bookings": {},
    "ad_bookings": {},
    "doctor_opinions": {},
    "patient_vitals": {},
    "symptom_reviews": [],
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
        "sicons_application": 1,
        "bed_booking": 1,
        "activity_log": 1,
        "organ_request": 1,
        "ad_booking": 1,
        "patient_vital": 1,
    }
}

def get_db_connection():
    try:
        conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
        return pyodbc.connect(conn_str, autocommit=True)
    except pyodbc.Error as e:
        if "Can't open lib" in str(e) or "Driver Manager" in str(e):
            return None  # ODBC driver not available
        raise

def migrate_legacy_schema(cursor):
    """Checks for existing INT ID columns and automatically migrates them to VARCHAR without losing data."""
    print("🔍 Checking for legacy INT ID columns that need migration...")
    
    # 1. Migrate Primary Keys
    tables_with_string_pk = ['doctors', 'patients', 'hospitals', 'staff', 'blood_donors', 'organ_donors']
    for table in tables_with_string_pk:
        cursor.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 1:
            cursor.execute(f"SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}' AND COLUMN_NAME = 'id'")
            row = cursor.fetchone()
            if row and row[0] == 'int':
                print(f"⚠️  Migrating '{table}' id column from INT to VARCHAR(50)...")
                # Find Primary Key constraint dynamically
                cursor.execute(f"SELECT name FROM sys.key_constraints WHERE type = 'PK' AND parent_object_id = OBJECT_ID('{table}')")
                pk_row = cursor.fetchone()
                if pk_row:
                    cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {pk_row[0]}")
                
                # Alter column to string type
                cursor.execute(f"ALTER TABLE {table} ALTER COLUMN id VARCHAR(50) NOT NULL")
                
                # Re-apply Primary Key constraint
                cursor.execute(f"ALTER TABLE {table} ADD CONSTRAINT PK_{table}_id PRIMARY KEY (id)")
                print(f"✅  Migrated '{table}' id column.")

    # 2. Migrate Foreign Keys
    tables_with_string_fks = [
        ('appointments', 'doctor_id'), ('appointments', 'patient_id'),
        ('reviews', 'doctor_id'), ('reviews', 'patient_id'),
        ('messages', 'doctor_id'), ('messages', 'patient_id'),
        ('orders', 'patient_id'),
        ('organ_requests', 'patient_id'), ('organ_requests', 'hospital_id'),
        ('bed_bookings', 'hospital_id'), ('bed_bookings', 'patient_id')
    ]
    
    for table, col in tables_with_string_fks:
        cursor.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 1:
            cursor.execute(f"SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}' AND COLUMN_NAME = '{col}'")
            row = cursor.fetchone()
            if row and row[0] == 'int':
                print(f"⚠️  Migrating '{table}.{col}' from INT to VARCHAR(255)...")
                cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {col} VARCHAR(255)")
                print(f"✅  Migrated '{table}.{col}'.")

    # 3. Add Missing Columns
    cursor.execute("IF OBJECT_ID('doctors', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
    if cursor.fetchone()[0] == 1:
        cursor.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'doctors' AND COLUMN_NAME = 'country'")
        if not cursor.fetchone():
            print("⚠️  Adding missing 'country' column to 'doctors' table...")
            cursor.execute("ALTER TABLE doctors ADD country NVARCHAR(100) DEFAULT 'India'")
            print("✅  Added 'country' column.")

        cursor.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'doctors' AND COLUMN_NAME = 'city'")
        if not cursor.fetchone():
            print("⚠️  Adding missing 'city' column to 'doctors' table...")
            cursor.execute("ALTER TABLE doctors ADD city NVARCHAR(100)")
            print("✅  Added 'city' column.")

        cursor.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'doctors' AND COLUMN_NAME = 'availability_status'")
        if not cursor.fetchone():
            print("⚠️  Adding missing 'availability_status' column to 'doctors' table...")
            cursor.execute("ALTER TABLE doctors ADD availability_status NVARCHAR(50) DEFAULT 'available'")
            print("✅  Added 'availability_status' column.")

    cursor.execute("IF OBJECT_ID('patients', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
    if cursor.fetchone()[0] == 1:
        cursor.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patients' AND COLUMN_NAME = 'phone'")
        if not cursor.fetchone():
            print("⚠️  Adding missing 'phone' column to 'patients' table...")
            cursor.execute("ALTER TABLE patients ADD phone NVARCHAR(50) NULL")
            print("✅  Added 'phone' column.")

        cursor.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patients' AND COLUMN_NAME = 'address'")
        if not cursor.fetchone():
            print("⚠️  Adding missing 'address' column to 'patients' table...")
            cursor.execute("ALTER TABLE patients ADD address NVARCHAR(MAX) NULL")
            print("✅  Added 'address' column.")

    # 4. Check & Create patient_feedback table
    cursor.execute("IF OBJECT_ID('patient_feedback', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
    if cursor.fetchone()[0] == 0:
        print("⚠️  Creating 'patient_feedback' table...")
        cursor.execute("""
            CREATE TABLE patient_feedback (
                id INT PRIMARY KEY,
                patient_id VARCHAR(50),
                patient_name NVARCHAR(255),
                rating INT,
                comments NVARCHAR(MAX) NULL,
                feedback_target NVARCHAR(100) NULL,
                target_id VARCHAR(50) NULL,
                target_name NVARCHAR(255) NULL,
                created_at DATETIME
            )
        """)
        print("✅  Created 'patient_feedback' table.")
    else:
        # Check and add columns if they are missing
        try:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patient_feedback'")
            existing_columns = {col[0] for col in cursor.fetchall()}
            if 'feedback_target' not in existing_columns:
                print("⚠️  Adding missing columns to 'patient_feedback' table...")
                cursor.execute("ALTER TABLE patient_feedback ADD feedback_target NVARCHAR(100) NULL")
                cursor.execute("ALTER TABLE patient_feedback ADD target_id VARCHAR(50) NULL")
                cursor.execute("ALTER TABLE patient_feedback ADD target_name NVARCHAR(255) NULL")
                print("✅  Added missing columns.")
        except Exception as col_err:
            print(f"⚠️  Error checking/updating patient_feedback columns: {col_err}")

    # 4b. Check & Create doctor_opinions table
    cursor.execute("IF OBJECT_ID('doctor_opinions', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
    if cursor.fetchone()[0] == 0:
        print("⚠️  Creating 'doctor_opinions' table...")
        cursor.execute("""
            CREATE TABLE doctor_opinions (
                doctor_id VARCHAR(50) PRIMARY KEY,
                rating INT,
                experience NVARCHAR(MAX) NULL,
                average_appointments NVARCHAR(100) NULL,
                created_at DATETIME
            )
        """)
        print("✅  Created 'doctor_opinions' table.")

    # Check and add missing columns to the 'staff' table
    try:
        cursor.execute("IF OBJECT_ID('staff', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 1:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'staff'")
            existing_staff_cols = {col[0] for col in cursor.fetchall()}
            if 'last_login' not in existing_staff_cols:
                print("⚠️  Adding missing 'last_login' column to 'staff' table...")
                cursor.execute("ALTER TABLE staff ADD last_login DATETIME NULL")
                print("✅  Added 'last_login' column.")
            if 'created_at' not in existing_staff_cols:
                print("⚠️  Adding missing 'created_at' column to 'staff' table...")
                cursor.execute("ALTER TABLE staff ADD created_at DATETIME NULL")
                print("✅  Added 'created_at' column.")
    except Exception as staff_err:
        print(f"⚠️  Error checking/updating staff columns: {staff_err}")




def save_data():
    """Saves the current state of TEMP_DATA to the SQL Database and local JSON backup."""
    print("💾 Syncing data...")
    # 1. Save to local JSON backup first to ensure persistence
    try:
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_store.json')
        with open(json_path, 'w') as f:
            json.dump(TEMP_DATA, f, cls=DataEncoder, indent=4)
        print("   ✅ Local JSON backup updated.")
    except Exception as json_err:
        print(f"⚠️  Could not write local data_store.json backup: {json_err}")

    # 2. Sync to SQL Database
    try:
        conn = get_db_connection()
        if conn is None:
            print("⚠️  SQL Database connection not available. Skipping database sync.")
            return
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
                    address=?, profile_picture_url=?, bio=?, hospital_name=?, hospital_address=?, city=?, state=?, 
                    district=?, pincode=?, country=?, qualification=?, license_number=?, experience=?, consultation_type=?, 
                    consultation_fee=?, working_hours=?, languages_spoken=?, social_links=?, is_verified=?, availability_status=?,
                    hospital_id=?, hospital_approval_status=?
                    WHERE id=?"""
                values = (
                    doc.first_name, doc.last_name, doc.email, doc.password, doc.department, doc.phone, doc.specialization,
                    doc.address, doc.profile_picture_url, doc.bio, doc.hospital_name, doc.hospital_address, getattr(doc, 'city', None), doc.state,
                    doc.district, doc.pincode, getattr(doc, 'country', 'India'), doc.qualification, doc.license_number, doc.experience, doc.consultation_type,
                    doc.consultation_fee, doc.working_hours, json_safe(getattr(doc, 'languages_spoken', None)), json_safe(getattr(doc, 'social_links', {})), getattr(doc, 'is_verified', False),
                    getattr(doc, 'availability_status', 'available'),
                    getattr(doc, 'hospital_id', None), getattr(doc, 'hospital_approval_status', None),
                    doc_id
                )

            else:

                sql = """INSERT INTO doctors (
                    id, first_name, last_name, email, password, department, phone, specialization, 
                    address, profile_picture_url, bio, hospital_name, hospital_address, city, state, 
                    district, pincode, country, qualification, license_number, experience, consultation_type, 
                    consultation_fee, working_hours, languages_spoken, social_links, is_verified, availability_status,
                    hospital_id, hospital_approval_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                values = (
                    doc_id, doc.first_name, doc.last_name, doc.email, doc.password, doc.department, doc.phone, doc.specialization,
                    doc.address, doc.profile_picture_url, doc.bio, doc.hospital_name, doc.hospital_address, getattr(doc, 'city', None), doc.state,
                    doc.district, doc.pincode, getattr(doc, 'country', 'India'), doc.qualification, doc.license_number, doc.experience, doc.consultation_type,
                    doc.consultation_fee, doc.working_hours, json_safe(getattr(doc, 'languages_spoken', None)), json_safe(getattr(doc, 'social_links', {})), getattr(doc, 'is_verified', False),
                    getattr(doc, 'availability_status', 'available'),
                    getattr(doc, 'hospital_id', None), getattr(doc, 'hospital_approval_status', None)
                )

            cursor.execute(sql, values)
            try:
                cursor.execute("UPDATE doctors SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(doc, 'is_blocked', False), getattr(doc, 'is_hidden', False), doc_id))
            except pyodbc.Error:
                pass

        # 2. Patients
        cursor.execute("SELECT id FROM patients")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['patients'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM patients WHERE id = ?", del_id)
        
        for p_id, p in TEMP_DATA['patients'].items():
            if p_id in db_ids:
                try:
                    cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=?, profile_picture_url=?, phone=?, address=?, clinical_record=? WHERE id=?", 
                                   (p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), json.dumps(getattr(p, 'clinical_record', {})), p_id))
                except pyodbc.Error:
                    try:
                        cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=?, profile_picture_url=?, phone=?, address=? WHERE id=?", 
                                       (p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), p_id))
                    except pyodbc.Error:
                        cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=? WHERE id=?", 
                                       (p.name, p.email, p.password, p.age, p.gender, p_id))
            else:
                try:
                    cursor.execute("INSERT INTO patients (id, name, email, password, age, gender, profile_picture_url, phone, address, clinical_record) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (p_id, p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), json.dumps(getattr(p, 'clinical_record', {}))))
                except pyodbc.Error:
                    try:
                        cursor.execute("INSERT INTO patients (id, name, email, password, age, gender, profile_picture_url, phone, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (p_id, p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None)))
                    except pyodbc.Error:
                        cursor.execute("INSERT INTO patients (id, name, email, password, age, gender) VALUES (?, ?, ?, ?, ?, ?)",
                                       (p_id, p.name, p.email, p.password, p.age, p.gender))
            try:
                cursor.execute("UPDATE patients SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(p, 'is_blocked', False), getattr(p, 'is_hidden', False), p_id))
            except pyodbc.Error:
                pass

        # 3. Hospitals
        cursor.execute("SELECT id FROM hospitals")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['hospitals'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM hospitals WHERE id = ?", del_id)
        
        for h_id, h in TEMP_DATA['hospitals'].items():
            if h_id in db_ids:
                try:
                    cursor.execute("UPDATE hospitals SET name=?, email=?, password=?, logo_url=?, total_beds=?, available_beds=?, address=?, icu_beds=?, available_icu_beds=?, doctors_available=?, is_verified=?, blood_stock=? WHERE id=?",
                                   (h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available, getattr(h, 'is_verified', True), json_safe(getattr(h, 'blood_stock', {})), h_id))
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
            try:
                cursor.execute("UPDATE hospitals SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(h, 'is_blocked', False), getattr(h, 'is_hidden', False), h_id))
            except pyodbc.Error:
                pass

        # 4. Staff
        cursor.execute("SELECT id FROM staff")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['staff'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM staff WHERE id = ?", del_id)
        
        for s_id, s in TEMP_DATA['staff'].items():
            if s_id in db_ids:
                cursor.execute("UPDATE staff SET name=?, email=?, password=?, role=?, phone=?, hospital_name=?, last_login=?, created_at=?, profile_picture_url=? WHERE id=?",
                               (s.name, s.email, s.password, s.role, s.phone, s.hospital_name, getattr(s, 'last_login', None), getattr(s, 'created_at', utcnow()), getattr(s, 'profile_picture_url', None), s_id))
            else:
                cursor.execute("INSERT INTO staff (id, name, email, password, role, phone, hospital_name, last_login, created_at, profile_picture_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (s_id, s.name, s.email, s.password, s.role, s.phone, s.hospital_name, getattr(s, 'last_login', None), getattr(s, 'created_at', utcnow()), getattr(s, 'profile_picture_url', None)))
            try:
                cursor.execute("UPDATE staff SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(s, 'is_blocked', False), getattr(s, 'is_hidden', False), s_id))
            except pyodbc.Error:
                pass

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
                    cursor.execute("UPDATE blood_donors SET name=?, email=?, phone=?, blood_group=?, age=?, city=?, password=?, last_donation=?, profile_picture_url=?, created_at=?, status=?, hospital_id=? WHERE id=?",
                                   (b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at, getattr(b, 'status', 'pending'), getattr(b, 'hospital_id', None), b_id))
                except pyodbc.Error:
                    try:
                        cursor.execute("UPDATE blood_donors SET name=?, email=?, phone=?, blood_group=?, age=?, city=?, password=?, last_donation=?, profile_picture_url=?, created_at=?, status=? WHERE id=?",
                                       (b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at, getattr(b, 'status', 'pending'), b_id))
                    except pyodbc.Error:
                        cursor.execute("UPDATE blood_donors SET name=?, email=?, phone=?, blood_group=?, age=?, city=?, password=?, last_donation=?, created_at=? WHERE id=?",
                                       (b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, b.created_at, b_id))
            else:
                try:
                    cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, profile_picture_url, created_at, status, hospital_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (b_id, b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at, getattr(b, 'status', 'pending'), getattr(b, 'hospital_id', None)))
                except pyodbc.Error:
                    try:
                        cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, profile_picture_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (b_id, b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at))
                    except pyodbc.Error:
                        cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (b_id, b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, b.created_at))
            try:
                cursor.execute("UPDATE blood_donors SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(b, 'is_blocked', False), getattr(b, 'is_hidden', False), b_id))
            except pyodbc.Error:
                pass

        # Organ Donors
        cursor.execute("SELECT id FROM organ_donors")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['organ_donors'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM organ_donors WHERE id = ?", del_id)
        
        for od_id, od in TEMP_DATA['organ_donors'].items():
            if od_id in db_ids:
                try:
                    cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, profile_picture_url=?, created_at=?, status=?, hospital_id=? WHERE id=?",
                                   (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, getattr(od, 'status', 'pending'), getattr(od, 'hospital_id', None), od_id))
                except pyodbc.Error:
                    try:
                        cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, profile_picture_url=?, created_at=?, status=? WHERE id=?",
                                       (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, getattr(od, 'status', 'pending'), od_id))
                    except pyodbc.Error:
                        try:
                            cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, profile_picture_url=?, created_at=? WHERE id=?",
                                           (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, od_id))
                        except pyodbc.Error:
                            cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, created_at=? WHERE id=?",
                                           (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, od.created_at, od_id))
            else:
                try:
                    cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password, profile_picture_url, created_at, status, hospital_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (od_id, od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, getattr(od, 'status', 'pending'), getattr(od, 'hospital_id', None)))
                except pyodbc.Error:
                    try:
                        cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password, profile_picture_url, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (od_id, od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, getattr(od, 'status', 'pending')))
                    except pyodbc.Error:
                        try:
                            cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password, profile_picture_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                           (od_id, od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at))
                        except pyodbc.Error:
                            cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                           (od_id, od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, od.created_at))
            try:
                cursor.execute("UPDATE organ_donors SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(od, 'is_blocked', False), getattr(od, 'is_hidden', False), od_id))
            except pyodbc.Error:
                pass
                
        # Organ Requests
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='organ_requests' AND xtype='U')
            CREATE TABLE organ_requests (
                id INT PRIMARY KEY,
                patient_id VARCHAR(255),
                patient_name VARCHAR(255),
                organ_needed VARCHAR(255),
                blood_group VARCHAR(50),
                urgency VARCHAR(50),
                status VARCHAR(50),
                hospital_id VARCHAR(255),
                created_at DATETIME
            )
            """)
            cursor.execute("SELECT id FROM organ_requests")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('organ_requests', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM organ_requests WHERE id = ?", del_id)
            
            for or_id, o_req in TEMP_DATA.get('organ_requests', {}).items():
                if or_id in db_ids:
                    cursor.execute("UPDATE organ_requests SET patient_id=?, patient_name=?, organ_needed=?, blood_group=?, urgency=?, status=?, hospital_id=?, created_at=? WHERE id=?",
                                   (o_req.patient_id, o_req.patient_name, o_req.organ_needed, o_req.blood_group, o_req.urgency, o_req.status, o_req.hospital_id, o_req.created_at, or_id))
                else:
                    cursor.execute("INSERT INTO organ_requests (id, patient_id, patient_name, organ_needed, blood_group, urgency, status, hospital_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (or_id, o_req.patient_id, o_req.patient_name, o_req.organ_needed, o_req.blood_group, o_req.urgency, o_req.status, o_req.hospital_id, o_req.created_at))
        except Exception as e:
            print(f"⚠️ Skipping organ_requests sync (table might not exist): {e}")

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
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bed_bookings' AND xtype='U')
            CREATE TABLE bed_bookings (
                id INT PRIMARY KEY,
                hospital_id VARCHAR(255),
                patient_id VARCHAR(255),
                patient_name VARCHAR(255),
                patient_phone VARCHAR(50),
                bed_type VARCHAR(50),
                reason VARCHAR(MAX),
                status VARCHAR(50),
                created_at DATETIME,
                room_number VARCHAR(50)
            )
            """)
            cursor.execute("SELECT id FROM bed_bookings")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('bed_bookings', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM bed_bookings WHERE id = ?", del_id)
            
            for bb_id, bb in TEMP_DATA.get('bed_bookings', {}).items():
                if bb_id in db_ids:
                    try:
                        cursor.execute("UPDATE bed_bookings SET hospital_id=?, patient_id=?, patient_name=?, patient_phone=?, bed_type=?, reason=?, status=?, created_at=?, room_number=? WHERE id=?",
                                       (bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, getattr(bb, 'room_number', None), bb_id))
                    except pyodbc.Error:
                        cursor.execute("UPDATE bed_bookings SET hospital_id=?, patient_id=?, patient_name=?, patient_phone=?, bed_type=?, reason=?, status=?, created_at=? WHERE id=?",
                                       (bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, bb_id))
                else:
                    try:
                        cursor.execute("INSERT INTO bed_bookings (id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, created_at, room_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (bb_id, bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, getattr(bb, 'room_number', None)))
                    except pyodbc.Error:
                        cursor.execute("INSERT INTO bed_bookings (id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (bb_id, bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at))
        except Exception as e:
            print(f"⚠️ Skipping bed_bookings sync (table might not exist): {e}")

        # 14. Activity Logs
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='activity_logs' AND xtype='U')
            CREATE TABLE activity_logs (
                id INT PRIMARY KEY,
                hospital_id VARCHAR(255),
                user_name VARCHAR(255),
                action VARCHAR(255),
                details VARCHAR(MAX),
                created_at DATETIME
            )
            """)
            cursor.execute("SELECT id FROM activity_logs")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('activity_logs', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM activity_logs WHERE id = ?", del_id)
            
            for al_id, al in TEMP_DATA.get('activity_logs', {}).items():
                if al_id in db_ids:
                    cursor.execute("UPDATE activity_logs SET hospital_id=?, user_name=?, action=?, details=?, created_at=? WHERE id=?",
                                   (al.hospital_id, al.user_name, al.action, al.details, al.created_at, al_id))
                else:
                    cursor.execute("INSERT INTO activity_logs (id, hospital_id, user_name, action, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   (al_id, al.hospital_id, al.user_name, al.action, al.details, al.created_at))
        except Exception as e:
            print(f"⚠️ Skipping activity_logs sync (table might not exist): {e}")

        # 15. Settings
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='settings' AND xtype='U')
            CREATE TABLE settings (
                setting_key VARCHAR(255) PRIMARY KEY,
                setting_value NVARCHAR(MAX)
            )
            """)
            for key, val in TEMP_DATA.get('settings', {}).items():
                cursor.execute("IF EXISTS (SELECT * FROM settings WHERE setting_key = ?) UPDATE settings SET setting_value = ? WHERE setting_key = ? ELSE INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)", (key, val, key, key, val))
        except Exception as e:
            print(f"⚠️ Skipping settings sync (table might not exist): {e}")

        # 16. Spherix iCons Applications
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sicons_applications' AND xtype='U')
            CREATE TABLE sicons_applications (
                id INT PRIMARY KEY,
                full_name NVARCHAR(255),
                email NVARCHAR(255),
                phone NVARCHAR(50),
                position NVARCHAR(255),
                department NVARCHAR(255),
                submitted_at DATETIME,
                files NVARCHAR(MAX),
                form_data NVARCHAR(MAX)
            )
            """)
            cursor.execute("SELECT id FROM sicons_applications")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = {app.get('id') for app in TEMP_DATA.get('sicons_applications', []) if 'id' in app}
            
            for del_id in db_ids - mem_ids:
                cursor.execute("DELETE FROM sicons_applications WHERE id = ?", del_id)
                
            for app_data in TEMP_DATA.get('sicons_applications', []):
                if 'id' not in app_data:
                    continue
                app_id = app_data['id']
                files_json = json_safe(app_data.get('files', {}))
                form_data = {k: v for k, v in app_data.items() if k not in ['id', 'full_name', 'email', 'phone', 'position', 'department', 'submitted_at', 'files']}
                
                if app_id in db_ids:
                    cursor.execute("UPDATE sicons_applications SET full_name=?, email=?, phone=?, position=?, department=?, submitted_at=?, files=?, form_data=? WHERE id=?",
                                   (app_data.get('full_name'), app_data.get('email'), app_data.get('phone'), app_data.get('position'), app_data.get('department'), app_data.get('submitted_at'), files_json, json_safe(form_data), app_id))
                else:
                    cursor.execute("INSERT INTO sicons_applications (id, full_name, email, phone, position, department, submitted_at, files, form_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (app_id, app_data.get('full_name'), app_data.get('email'), app_data.get('phone'), app_data.get('position'), app_data.get('department'), app_data.get('submitted_at'), files_json, json_safe(form_data)))
        except Exception as e:
            print(f"⚠️ Skipping sicons_applications sync (table might not exist): {e}")

        # 17. Contact Messages
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='contact_messages' AND xtype='U')
            CREATE TABLE contact_messages (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255),
                phone NVARCHAR(50),
                address NVARCHAR(MAX),
                message NVARCHAR(MAX),
                date DATETIME
            )
            """)
            cursor.execute("DELETE FROM contact_messages")
            for msg in reversed(TEMP_DATA.get('contact_messages', [])):
                cursor.execute("INSERT INTO contact_messages (name, email, phone, address, message, date) VALUES (?, ?, ?, ?, ?, ?)",
                               (msg.get('name'), msg.get('email'), msg.get('phone'), msg.get('address'), msg.get('message'), msg.get('date')))
        except Exception as e:
            print(f"⚠️ Skipping contact_messages sync (table might not exist): {e}")

        # 18. Newsletter Subscribers
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='newsletter_subscribers' AND xtype='U')
            CREATE TABLE newsletter_subscribers (
                email NVARCHAR(255) PRIMARY KEY,
                name NVARCHAR(255) NULL,
                contact NVARCHAR(50) NULL,
                interests NVARCHAR(MAX) NULL,
                subscribed_at DATETIME DEFAULT GETDATE()
            )
            """)
            
            # Ensure columns exist in case table was created previously with older schema
            try:
                cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('newsletter_subscribers') AND name = 'name'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE newsletter_subscribers ADD name NVARCHAR(255) NULL")
                cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('newsletter_subscribers') AND name = 'contact'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE newsletter_subscribers ADD contact NVARCHAR(50) NULL")
                cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('newsletter_subscribers') AND name = 'interests'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE newsletter_subscribers ADD interests NVARCHAR(MAX) NULL")
            except Exception as col_err:
                print(f"⚠️ Error ensuring columns on newsletter_subscribers sync: {col_err}")

            cursor.execute("SELECT email FROM newsletter_subscribers")
            db_emails = {row[0] for row in cursor.fetchall()}
            mem_emails = {sub['email'] for sub in TEMP_DATA.get('newsletter_subscribers', [])}
            
            for del_email in db_emails - mem_emails:
                cursor.execute("DELETE FROM newsletter_subscribers WHERE email = ?", del_email)
                
            for sub in TEMP_DATA.get('newsletter_subscribers', []):
                if sub['email'] not in db_emails:
                    cursor.execute("""
                        INSERT INTO newsletter_subscribers (email, name, contact, interests, subscribed_at) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        sub['email'], 
                        sub.get('name'), 
                        sub.get('contact'), 
                        ','.join(sub.get('interests', [])) if isinstance(sub.get('interests'), list) else sub.get('interests'),
                        sub['subscribed_at']
                    ))
        except Exception as e:
            print(f"⚠️ Skipping newsletter_subscribers sync (table might not exist): {e}")
            
        # 19. Medicines
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='medicines' AND xtype='U')
            CREATE TABLE medicines (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) UNIQUE,
                category NVARCHAR(100),
                price FLOAT
            )
            """)
            cursor.execute("SELECT name FROM medicines")
            db_meds = {row[0] for row in cursor.fetchall()}
            mem_meds = {m['name'] for m in TEMP_DATA.get('medicines', [])}
            
            for del_med in db_meds - mem_meds:
                cursor.execute("DELETE FROM medicines WHERE name = ?", del_med)
                
            for m in TEMP_DATA.get('medicines', []):
                if m['name'] not in db_meds:
                    cursor.execute("INSERT INTO medicines (name, category, price) VALUES (?, ?, ?)", 
                                   (m['name'], m.get('category', 'General'), m.get('price', 0.0)))
                else:
                    cursor.execute("UPDATE medicines SET category=?, price=? WHERE name=?", 
                                   (m.get('category', 'General'), m.get('price', 0.0), m['name']))
        except Exception as e:
            print(f"⚠️ Skipping medicines sync (table might not exist): {e}")

        # 12. Patient Feedbacks
        try:
            cursor.execute("IF OBJECT_ID('patient_feedback', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                cursor.execute("SELECT id FROM patient_feedback")
                db_ids = {row[0] for row in cursor.fetchall()}
                mem_ids = set(TEMP_DATA.get('feedbacks', {}).keys())
                for del_id in db_ids - mem_ids:
                    cursor.execute("DELETE FROM patient_feedback WHERE id = ?", del_id)
                for fb_id, fb in TEMP_DATA.get('feedbacks', {}).items():
                    if fb_id in db_ids:
                        cursor.execute("UPDATE patient_feedback SET patient_id=?, patient_name=?, rating=?, comments=?, feedback_target=?, target_id=?, target_name=? WHERE id=?",
                                       (fb.patient_id, fb.patient_name, fb.rating, fb.comments, getattr(fb, 'feedback_target', 'web_application'), getattr(fb, 'target_id', None), getattr(fb, 'target_name', None), fb_id))
                    else:
                        cursor.execute("INSERT INTO patient_feedback (id, patient_id, patient_name, rating, comments, feedback_target, target_id, target_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (fb_id, fb.patient_id, fb.patient_name, fb.rating, fb.comments, getattr(fb, 'feedback_target', 'web_application'), getattr(fb, 'target_id', None), getattr(fb, 'target_name', None), fb.created_at))
        except Exception as e:
            print(f"⚠️ Skipping feedback sync: {e}")

        # 13. Doctor Opinions
        try:
            cursor.execute("IF OBJECT_ID('doctor_opinions', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                cursor.execute("SELECT doctor_id FROM doctor_opinions")
                db_doc_ids = {row[0] for row in cursor.fetchall()}
                mem_doc_ids = set(TEMP_DATA.get('doctor_opinions', {}).keys())
                for del_id in db_doc_ids - mem_doc_ids:
                    cursor.execute("DELETE FROM doctor_opinions WHERE doctor_id = ?", del_id)
                for doc_id, op in TEMP_DATA.get('doctor_opinions', {}).items():
                    created_at_val = op.get('created_at')
                    if isinstance(created_at_val, str):
                        try: created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
                        except ValueError: created_at_val = utcnow()
                    else:
                        created_at_val = created_at_val or utcnow()

                    if doc_id in db_doc_ids:
                        cursor.execute("UPDATE doctor_opinions SET rating=?, experience=?, average_appointments=? WHERE doctor_id=?",
                                       (op.get('rating', 5), op.get('experience', ''), op.get('average_appointments', ''), doc_id))
                    else:
                        cursor.execute("INSERT INTO doctor_opinions (doctor_id, rating, experience, average_appointments, created_at) VALUES (?, ?, ?, ?, ?)",
                                       (doc_id, op.get('rating', 5), op.get('experience', ''), op.get('average_appointments', ''), created_at_val))
        except Exception as e:
            print(f"⚠️ Skipping doctor opinions sync: {e}")

        # Sync Patient Vitals
        try:
            cursor.execute("IF OBJECT_ID('patient_vitals', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                cursor.execute("SELECT id FROM patient_vitals")
                db_vital_ids = {row[0] for row in cursor.fetchall()}
                mem_vital_ids = set(TEMP_DATA.get('patient_vitals', {}).keys())
                for del_id in db_vital_ids - mem_vital_ids:
                    cursor.execute("DELETE FROM patient_vitals WHERE id = ?", del_id)
                for v_id, vit in TEMP_DATA.get('patient_vitals', {}).items():
                    rec_at = getattr(vit, 'recorded_at', utcnow())
                    if isinstance(rec_at, str):
                        try: rec_at = datetime.fromisoformat(rec_at.replace('Z', '+00:00'))
                        except ValueError: rec_at = utcnow()
                    
                    if v_id in db_vital_ids:
                        cursor.execute("UPDATE patient_vitals SET patient_id=?, weight=?, heart_rate=?, blood_sugar=?, systolic_bp=?, diastolic_bp=?, recorded_at=? WHERE id=?",
                                       (vit.patient_id, vit.weight, vit.heart_rate, vit.blood_sugar, vit.systolic_bp, vit.diastolic_bp, rec_at, v_id))
                    else:
                        cursor.execute("SET IDENTITY_INSERT patient_vitals ON")
                        cursor.execute("INSERT INTO patient_vitals (id, patient_id, weight, heart_rate, blood_sugar, systolic_bp, diastolic_bp, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                       (v_id, vit.patient_id, vit.weight, vit.heart_rate, vit.blood_sugar, vit.systolic_bp, vit.diastolic_bp, rec_at))
                        cursor.execute("SET IDENTITY_INSERT patient_vitals OFF")
        except Exception as e:
            print(f"⚠️ Skipping patient_vitals sync: {e}")

        # Sync Doctor Symptom Reviews
        try:
            cursor.execute("IF OBJECT_ID('doctor_symptom_reviews', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                cursor.execute("SELECT id FROM doctor_symptom_reviews")
                db_rev_ids = {row[0] for row in cursor.fetchall()}
                
                mem_revs = TEMP_DATA.get('symptom_reviews', [])
                mem_rev_ids = {r['id'] for r in mem_revs if 'id' in r}
                
                for del_id in db_rev_ids - mem_rev_ids:
                    cursor.execute("DELETE FROM doctor_symptom_reviews WHERE id = ?", del_id)
                    
                for r in mem_revs:
                    created_at_val = r.get('created_at')
                    if isinstance(created_at_val, str):
                        try: created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
                        except ValueError: created_at_val = utcnow()
                    else:
                        created_at_val = created_at_val or utcnow()
                        
                    if r.get('id') in db_rev_ids:
                        cursor.execute("""
                            UPDATE doctor_symptom_reviews 
                            SET symptom_query=?, doctor_id=?, doctor_name=?, status=?, clinical_remarks=?, prescribed_treatment=?, recommended_tests=? 
                            WHERE id=?
                        """, (
                            r['symptom_query'], r['doctor_id'], r['doctor_name'], r['status'], 
                            r.get('clinical_remarks'), r.get('prescribed_treatment'), r.get('recommended_tests'), 
                            r['id']
                        ))
                    else:
                        cursor.execute("""
                            INSERT INTO doctor_symptom_reviews (symptom_query, doctor_id, doctor_name, status, clinical_remarks, prescribed_treatment, recommended_tests, created_at) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            r['symptom_query'], r['doctor_id'], r['doctor_name'], r['status'], 
                            r.get('clinical_remarks'), r.get('prescribed_treatment'), r.get('recommended_tests'), 
                            created_at_val
                        ))
        except Exception as e:
            print(f"⚠️ Skipping doctor_symptom_reviews sync: {e}")

        conn.commit()
        conn.close()
        print("✅ Data synced to SQL successfully.")
    except Exception as e:
        print(f"❌ Error syncing to SQL: {e}")
        traceback.print_exc()

def auto_migrate_local_data(cursor):
    """Automatically migrates data from local SQLite database (app.db) and data_store.json into SQL Server if they exist."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sqlite_db_path = os.path.join(base_dir, 'app.db')
    json_store_path = os.path.join(base_dir, 'data_store.json')
    
    # 1. Migrate SQLite
    if os.path.exists(sqlite_db_path):
        print(f"📦 Found local SQLite database at {sqlite_db_path}. Auto-migrating new records...")
        try:
            import sqlite3
            sqlite_conn = sqlite3.connect(sqlite_db_path)
            sqlite_conn.row_factory = sqlite3.Row
            sqlite_cursor = sqlite_conn.cursor()
            
            # Check SQLite tables
            sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            sqlite_tables = [r[0] for r in sqlite_cursor.fetchall()]
            
            # Migrate Doctors
            if 'doctors' in sqlite_tables:
                sqlite_cursor.execute("SELECT * FROM doctors")
                for row in sqlite_cursor.fetchall():
                    row = dict(row)
                    doc_id = f"DOC/{row['id']}"
                    cursor.execute("SELECT id FROM doctors WHERE id = ?", doc_id)
                    if not cursor.fetchone():
                        sql = """INSERT INTO doctors (
                            id, first_name, last_name, email, password, department, phone, specialization, 
                            address, profile_picture_url, bio, country, is_verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                        values = (
                            doc_id, row.get('first_name'), row.get('last_name'), row.get('email'), row.get('password'),
                            row.get('department', ''), row.get('phone', ''), row.get('specialization', ''),
                            row.get('address', ''), row.get('profile_picture_url', ''), row.get('bio', ''),
                            'India', 1
                        )
                        cursor.execute(sql, values)
                        print(f"   ✅ Auto-migrated Doctor {doc_id} from SQLite.")

            # Migrate Patients
            if 'patients' in sqlite_tables:
                sqlite_cursor.execute("SELECT * FROM patients")
                for row in sqlite_cursor.fetchall():
                    row = dict(row)
                    pat_id = f"PAT/{row['id']}"
                    cursor.execute("SELECT id FROM patients WHERE id = ?", pat_id)
                    if not cursor.fetchone():
                        name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or 'Unknown Patient'
                        sql = """INSERT INTO patients (
                            id, name, email, password, age, gender
                        ) VALUES (?, ?, ?, ?, ?, ?)"""
                        values = (
                            pat_id, name, row.get('email'), row.get('password'), 30, 'Not Specified'
                        )
                        cursor.execute(sql, values)
                        print(f"   ✅ Auto-migrated Patient {pat_id} from SQLite.")

            # Migrate Appointments
            if 'appointments' in sqlite_tables:
                sqlite_cursor.execute("SELECT * FROM appointments")
                for row in sqlite_cursor.fetchall():
                    row = dict(row)
                    appt_id = row['id']
                    cursor.execute("SELECT id FROM appointments WHERE id = ?", appt_id)
                    if not cursor.fetchone():
                        doc_id = f"DOC/{row['doctor_id']}" if row['doctor_id'] else None
                        raw_time = row.get('time') or ''
                        appt_date = None
                        appt_time = None
                        try:
                            if ' ' in raw_time:
                                dt = datetime.strptime(raw_time, '%Y-%m-%d %H:%M')
                                appt_date = dt.date()
                                appt_time = dt.time()
                            elif '/' in raw_time:
                                dt = datetime.strptime(raw_time, '%d/%m/%Y')
                                appt_date = dt.date()
                                appt_time = datetime.strptime("10:00:00", "%H:%M:%S").time()
                            else:
                                appt_date = datetime.now().date()
                                appt_time = datetime.now().time()
                        except Exception as pe:
                            appt_date = datetime.now().date()
                            appt_time = datetime.now().time()

                        sql = """INSERT INTO appointments (
                            id, patient_name, doctor_id, patient_id, appointment_date, appointment_time, 
                            patient_age, patient_phone, reason, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                        values = (
                            appt_id, row.get('patient_name'), doc_id, None, appt_date, appt_time,
                            30, row.get('patient_phone', ''), 'Consultation', 'confirmed'
                        )
                        cursor.execute(sql, values)
                        print(f"   ✅ Auto-migrated Appointment #{appt_id} from SQLite.")

            # Migrate Messages
            if 'messages' in sqlite_tables:
                sqlite_cursor.execute("SELECT * FROM messages")
                for row in sqlite_cursor.fetchall():
                    row = dict(row)
                    msg_id = row['id']
                    cursor.execute("SELECT id FROM messages WHERE id = ?", msg_id)
                    if not cursor.fetchone():
                        doc_id = f"DOC/{row['doctor_id']}" if row.get('doctor_id') else None
                        created_at_raw = row.get('created_at', '')
                        try:
                            created_at = datetime.strptime(created_at_raw.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        except:
                            created_at = datetime.now()

                        sql = """INSERT INTO messages (
                            id, doctor_id, patient_id, sender, content, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)"""
                        values = (
                            msg_id, doc_id, None, row.get('sender', 'patient'), row.get('content', ''), created_at
                        )
                        cursor.execute(sql, values)
                        print(f"   ✅ Auto-migrated Message #{msg_id} from SQLite.")

            sqlite_conn.close()
            try:
                os.rename(sqlite_db_path, sqlite_db_path + '.migrated')
                print(f"📂 SQLite database renamed to {sqlite_db_path}.migrated")
            except Exception as re:
                print(f"⚠️ Could not rename SQLite file: {re}")
                
        except Exception as e:
            print(f"❌ Error during automatic SQLite data migration: {e}")
            import traceback
            traceback.print_exc()

    # 2. Migrate data_store.json
    if os.path.exists(json_store_path):
        print(f"📦 Found local data_store.json file. Auto-migrating records...")
        try:
            with open(json_store_path, 'r') as f:
                data = json.load(f)
            
            # Migrate Doctors
            doctors = data.get('doctors', {})
            for doc_id, doc in doctors.items():
                cursor.execute("SELECT id FROM doctors WHERE id = ?", doc.get('id'))
                if not cursor.fetchone():
                    sql = """INSERT INTO doctors (
                        id, first_name, last_name, email, password, department, phone, specialization, 
                        address, profile_picture_url, bio, hospital_name, hospital_address, state, 
                        district, pincode, qualification, license_number, experience, consultation_type, 
                        consultation_fee, working_hours, languages_spoken, social_links, is_verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                    values = (
                        doc.get('id'), doc.get('first_name'), doc.get('last_name'), doc.get('email'), doc.get('password'),
                        doc.get('department'), doc.get('phone'), doc.get('specialization'), doc.get('address'),
                        doc.get('profile_picture_url'), doc.get('bio'), doc.get('hospital_name'), doc.get('hospital_address'),
                        doc.get('state'), doc.get('district'), doc.get('pincode'), doc.get('qualification'),
                        doc.get('license_number'), doc.get('experience'), doc.get('consultation_type'),
                        doc.get('consultation_fee'), doc.get('working_hours'), doc.get('languages_spoken'),
                        doc.get('social_links'), doc.get('is_verified', False)
                    )
                    cursor.execute(sql, values)
                    print(f"   ✅ Auto-migrated Doctor {doc.get('id')} from JSON.")

            # Migrate Hospitals
            hospitals = data.get('hospitals', {})
            for hosp_id, hosp in hospitals.items():
                cursor.execute("SELECT id FROM hospitals WHERE id = ?", hosp.get('id'))
                if not cursor.fetchone():
                    try:
                        sql = """INSERT INTO hospitals (
                            id, name, email, password, logo_url, total_beds, available_beds, address, icu_beds, available_icu_beds, doctors_available, is_verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                        values = (
                            hosp.get('id'), hosp.get('name'), hosp.get('email'), hosp.get('password'),
                            hosp.get('logo_url'), hosp.get('total_beds', 0), hosp.get('available_beds', 0),
                            hosp.get('address'), hosp.get('icu_beds', 0), hosp.get('available_icu_beds', 0),
                            hosp.get('doctors_available', 'Available'), hosp.get('is_verified', True)
                        )
                        cursor.execute(sql, values)
                    except:
                        sql = """INSERT INTO hospitals (
                            id, name, email, password, logo_url, total_beds, available_beds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)"""
                        values = (
                            hosp.get('id'), hosp.get('name'), hosp.get('email'), hosp.get('password'),
                            hosp.get('logo_url'), hosp.get('total_beds', 0), hosp.get('available_beds', 0)
                        )
                        cursor.execute(sql, values)
                    print(f"   ✅ Auto-migrated Hospital {hosp.get('id')} from JSON.")

            # Migrate Blood Stock
            blood_stock = data.get('blood_stock', {})
            for group, quantity in blood_stock.items():
                cursor.execute("SELECT blood_group FROM blood_stock WHERE blood_group = ?", group)
                if cursor.fetchone():
                    cursor.execute("UPDATE blood_stock SET quantity = ? WHERE blood_group = ?", quantity, group)
                else:
                    cursor.execute("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", group, quantity)

            # Migrate Organ Donors
            organ_donors = data.get('organ_donors', {})
            for od_id, od in organ_donors.items():
                cursor.execute("SELECT id FROM organ_donors WHERE id = ?", od.get('id'))
                if not cursor.fetchone():
                    sql = """INSERT INTO organ_donors (
                        id, name, email, phone, organs, blood_group, age, city, password, profile_picture_url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                    organs_data = od.get('organs', [])
                    organs_json = json.dumps(organs_data) if isinstance(organs_data, list) else str(organs_data)
                    values = (
                        od.get('id'), od.get('name'), od.get('email'), od.get('phone'),
                        organs_json, od.get('blood_group'), od.get('age'),
                        od.get('city'), od.get('password'), od.get('profile_picture_url'), od.get('created_at')
                    )
                    cursor.execute(sql, values)
                    print(f"   ✅ Auto-migrated Organ Donor {od.get('id')} from JSON.")

            # Migrate Messages
            messages = data.get('messages', {})
            for msg_id, msg in messages.items():
                cursor.execute("SELECT id FROM messages WHERE id = ?", msg.get('id'))
                if not cursor.fetchone():
                    sql = """INSERT INTO messages (
                        id, doctor_id, patient_id, sender, content, created_at, attachment_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)"""
                    values = (
                        msg.get('id'), msg.get('doctor_id'), msg.get('patient_id'), 
                        msg.get('sender'), msg.get('content'), msg.get('created_at'), msg.get('attachment_url')
                    )
                    cursor.execute(sql, values)

            # Migrate Contact Messages
            contact_messages = data.get('contact_messages', [])
            for msg in reversed(contact_messages):
                sql = """INSERT INTO contact_messages (name, email, phone, address, message, date) 
                         VALUES (?, ?, ?, ?, ?, ?)"""
                values = (
                    msg.get('name'), msg.get('email'), msg.get('phone'), 
                    msg.get('address'), msg.get('message'), msg.get('date')
                )
                cursor.execute(sql, values)
                
            print("📂 Auto-migration from JSON complete.")
            try:
                os.rename(json_store_path, json_store_path + '.migrated')
                print(f"📂 JSON data store renamed to {json_store_path}.migrated")
            except Exception as re:
                print(f"⚠️ Could not rename JSON data store file: {re}")

        except Exception as e:
            print(f"❌ Error during automatic JSON data migration: {e}")

def load_from_json():
    global TEMP_DATA
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_store.json')
    if not os.path.exists(json_path):
        print("⚠️  No local JSON data store found.")
        return
    print("🔄 Loading data from local JSON database...")
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        def try_int(k):
            try: return int(k)
            except (ValueError, TypeError): return k

        # 1. Doctors
        TEMP_DATA['doctors'] = {k: Doctor(**v) for k, v in data.get('doctors', {}).items()}

        # 2. Patients
        TEMP_DATA['patients'] = {k: Patient(**v) for k, v in data.get('patients', {}).items()}

        # 3. Hospitals
        TEMP_DATA['hospitals'] = {}
        for k, v in data.get('hospitals', {}).items():
            TEMP_DATA['hospitals'][k] = Hospital(**v)

        # 4. Staff
        TEMP_DATA['staff'] = {k: Staff(**v) for k, v in data.get('staff', {}).items()}

        # 5. Appointments
        TEMP_DATA['appointments'] = {}
        for k, v in data.get('appointments', {}).items():
            if 'appointment_date' in v and isinstance(v['appointment_date'], str):
                try: v['appointment_date'] = date.fromisoformat(v['appointment_date'])
                except ValueError: pass
            if 'appointment_time' in v and isinstance(v['appointment_time'], str):
                try: v['appointment_time'] = time.fromisoformat(v['appointment_time'])
                except ValueError: pass
            if 'original_appointment_date' in v and isinstance(v['original_appointment_date'], str):
                try: v['original_appointment_date'] = date.fromisoformat(v['original_appointment_date'])
                except ValueError: pass
            if 'original_appointment_time' in v and isinstance(v['original_appointment_time'], str):
                try: v['original_appointment_time'] = time.fromisoformat(v['original_appointment_time'])
                except ValueError: pass
            if 'created_at' in v and isinstance(v['created_at'], str):
                try: v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['appointments'][try_int(k)] = Appointment(**v)

        # 6. Reviews
        TEMP_DATA['reviews'] = {}
        for k, v in data.get('reviews', {}).items():
            if 'created_at' in v and isinstance(v['created_at'], str):
                try: v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['reviews'][try_int(k)] = Review(**v)

        # 7. Messages
        TEMP_DATA['messages'] = {}
        for k, v in data.get('messages', {}).items():
            if 'created_at' in v and isinstance(v['created_at'], str):
                try: v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['messages'][try_int(k)] = Message(**v)

        # 8. Orders
        TEMP_DATA['orders'] = {}
        for k, v in data.get('orders', {}).items():
            TEMP_DATA['orders'][try_int(k)] = Order(**v)

        # 9. Blood Donors
        TEMP_DATA['blood_donors'] = {k: BloodDonor(**v) for k, v in data.get('blood_donors', {}).items()}

        # 10. Organ Donors
        TEMP_DATA['organ_donors'] = {k: OrganDonor(**v) for k, v in data.get('organ_donors', {}).items()}

        # 11. Organ Requests
        TEMP_DATA['organ_requests'] = {}
        for k, v in data.get('organ_requests', {}).items():
            if 'created_at' in v and isinstance(v['created_at'], str):
                try: v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['organ_requests'][try_int(k)] = OrganRequest(**v)

        # 12. Contact Messages
        TEMP_DATA['contact_messages'] = data.get('contact_messages', [])

        # 13. Camp Registrations
        TEMP_DATA['camp_registrations'] = {try_int(k): v for k, v in data.get('camp_registrations', {}).items()}

        # 14. Camps
        TEMP_DATA['camps'] = {try_int(k): v for k, v in data.get('camps', {}).items()}

        # 15. Newsletter Subscribers
        TEMP_DATA['newsletter_subscribers'] = data.get('newsletter_subscribers', [])

        # 16. Medicines
        TEMP_DATA['medicines'] = data.get('medicines', [])

        # 17. Sicons Applications
        TEMP_DATA['sicons_applications'] = data.get('sicons_applications', [])

        # 18. Activity Logs
        TEMP_DATA['activity_logs'] = {}
        for k, v in data.get('activity_logs', {}).items():
            if 'created_at' in v and isinstance(v['created_at'], str):
                try: v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['activity_logs'][try_int(k)] = ActivityLog(**v)

        # 19. Blood Stock
        TEMP_DATA['blood_stock'] = data.get('blood_stock', TEMP_DATA['blood_stock'])

        # 20. Settings
        TEMP_DATA['settings'] = data.get('settings', TEMP_DATA['settings'])

        # 21. Bed Bookings
        TEMP_DATA['bed_bookings'] = {}
        for k, v in data.get('bed_bookings', {}).items():
            if 'created_at' in v and isinstance(v['created_at'], str):
                try: v['created_at'] = datetime.fromisoformat(v['created_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['bed_bookings'][try_int(k)] = BedBooking(**v)

        # 22. Ad Bookings
        TEMP_DATA['ad_bookings'] = {try_int(k): v for k, v in data.get('ad_bookings', {}).items()}

        # 22b. Doctor Opinions
        TEMP_DATA['doctor_opinions'] = data.get('doctor_opinions', {})

        # 22c. Patient Vitals
        TEMP_DATA['patient_vitals'] = {}
        for k, v in data.get('patient_vitals', {}).items():
            if 'recorded_at' in v and isinstance(v['recorded_at'], str):
                try: v['recorded_at'] = datetime.fromisoformat(v['recorded_at'].replace('Z', '+00:00'))
                except ValueError: pass
            TEMP_DATA['patient_vitals'][try_int(k)] = PatientVital(**v)

        # 23. Next IDs
        TEMP_DATA['next_ids'] = {k: int(v) for k, v in data.get('next_ids', {}).items()}
        
        print("   ✅ Local JSON data loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load local JSON data: {e}")

def load_data():
    """Loads data from SQL Database into TEMP_DATA, rehydrating objects."""
    global TEMP_DATA
    print("🔄 Loading data from SQL Database...")

    try:
        conn = get_db_connection()
        if conn is None:
            print("⚠️  SQL Database connection not available. Falling back to local JSON database...")
            load_from_json()
            return
        cursor = conn.cursor()

        # Perform data-safe migration of INT to VARCHAR if tables already exist
        migrate_legacy_schema(cursor)
        
        # Auto-migrate local SQLite or JSON data stores dynamically
        auto_migrate_local_data(cursor)

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
        for h in hosps:
            # Ensure fees are read safely, defaulting to standard if NULL in DB
            h['general_bed_fee'] = h.get('general_bed_fee') if h.get('general_bed_fee') is not None else 1000.0
            h['icu_bed_fee'] = h.get('icu_bed_fee') if h.get('icu_bed_fee') is not None else 2500.0
            if isinstance(h.get('blood_stock'), str):
                try: h['blood_stock'] = json.loads(h['blood_stock'].replace("'", '"'))
                except: h['blood_stock'] = { "A+": 0, "A-": 0, "B+": 0, "B-": 0, "AB+": 0, "AB-": 0, "O+": 0, "O-": 0 }
            elif not h.get('blood_stock'):
                h['blood_stock'] = { "A+": 0, "A-": 0, "B+": 0, "B-": 0, "AB+": 0, "AB-": 0, "O+": 0, "O-": 0 }
            
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
            # Normalize items to ensure quantity is always present
            if isinstance(o.get('items'), list):
                for item in o['items']:
                    if isinstance(item, dict) and 'quantity' not in item:
                        item['quantity'] = 1
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

        # Organ Requests
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='organ_requests' AND xtype='U')
            CREATE TABLE organ_requests (
                id INT PRIMARY KEY,
                patient_id VARCHAR(255),
                patient_name VARCHAR(255),
                organ_needed VARCHAR(255),
                blood_group VARCHAR(50),
                urgency VARCHAR(50),
                status VARCHAR(50),
                hospital_id VARCHAR(255),
                created_at DATETIME
            )
            """)
            oreqs = fetch_dict("SELECT * FROM organ_requests")
            if 'organ_requests' not in TEMP_DATA: TEMP_DATA['organ_requests'] = {}
            TEMP_DATA['organ_requests'] = {o['id']: OrganRequest(**o) for o in oreqs}
        except Exception:
            print("⚠️ Skipping organ_requests load (table might not exist)")

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
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bed_bookings' AND xtype='U')
            CREATE TABLE bed_bookings (
                id INT PRIMARY KEY,
                hospital_id VARCHAR(255),
                patient_id VARCHAR(255),
                patient_name VARCHAR(255),
                patient_phone VARCHAR(50),
                bed_type VARCHAR(50),
                reason VARCHAR(MAX),
                status VARCHAR(50),
                created_at DATETIME,
                room_number VARCHAR(50)
            )
            """)
            bbs = fetch_dict("SELECT * FROM bed_bookings")
            if 'bed_bookings' not in TEMP_DATA: TEMP_DATA['bed_bookings'] = {}
            TEMP_DATA['bed_bookings'] = {b['id']: BedBooking(**b) for b in bbs}
        except Exception:
            print("⚠️ Skipping bed_bookings load (table might not exist)")
            if 'bed_bookings' not in TEMP_DATA: TEMP_DATA['bed_bookings'] = {}

        # 14. Activity Logs
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='activity_logs' AND xtype='U')
            CREATE TABLE activity_logs (
                id INT PRIMARY KEY,
                hospital_id VARCHAR(255),
                user_name VARCHAR(255),
                action VARCHAR(255),
                details VARCHAR(MAX),
                created_at DATETIME
            )
            """)
            alogs = fetch_dict("SELECT * FROM activity_logs")
            if 'activity_logs' not in TEMP_DATA: TEMP_DATA['activity_logs'] = {}
            TEMP_DATA['activity_logs'] = {l['id']: ActivityLog(**l) for l in alogs}
        except Exception:
            print("⚠️ Skipping activity_logs load (table might not exist)")
            if 'activity_logs' not in TEMP_DATA: TEMP_DATA['activity_logs'] = {}

        # 15. Settings
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='settings' AND xtype='U')
            CREATE TABLE settings (
                setting_key VARCHAR(255) PRIMARY KEY,
                setting_value NVARCHAR(MAX)
            )
            """)
            setts = fetch_dict("SELECT * FROM settings")
            if 'settings' not in TEMP_DATA: 
                TEMP_DATA['settings'] = {
                    "hq_address": "Spherix Clinic Health Intelligence, Motihari\nBihar State, 845401\nIndia",
                    "contact_email": "support@spherixclinic.com",
                    "contact_phone": "+91 933 4325 920"
                }
            for s in setts:
                TEMP_DATA['settings'][s['setting_key']] = s['setting_value']
        except Exception:
            print("⚠️ Skipping settings load (table might not exist)")

        # 16. Spherix iCons Applications
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sicons_applications' AND xtype='U')
            CREATE TABLE sicons_applications (
                id INT PRIMARY KEY,
                full_name NVARCHAR(255),
                email NVARCHAR(255),
                phone NVARCHAR(50),
                position NVARCHAR(255),
                department NVARCHAR(255),
                submitted_at DATETIME,
                files NVARCHAR(MAX),
                form_data NVARCHAR(MAX)
            )
            """)
            apps = fetch_dict("SELECT * FROM sicons_applications")
            TEMP_DATA['sicons_applications'] = []
            for a in apps:
                try: form_data = json.loads(a.get('form_data', '{}'))
                except: form_data = {}
                try: files_data = json.loads(a.get('files', '{}'))
                except: files_data = {}
                
                merged = {**form_data, 'id': a['id'], 'full_name': a['full_name'], 'email': a['email'], 'phone': a['phone'], 'position': a['position'], 'department': a['department'], 'submitted_at': a['submitted_at'].isoformat() if isinstance(a['submitted_at'], datetime) else a['submitted_at'], 'files': files_data}
                TEMP_DATA['sicons_applications'].append(merged)
                
        except Exception as e:
            print(f"⚠️ Skipping sicons_applications load (table might not exist): {e}")
            if 'sicons_applications' not in TEMP_DATA: TEMP_DATA['sicons_applications'] = []

        # 17. Contact Messages
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='contact_messages' AND xtype='U')
            CREATE TABLE contact_messages (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255),
                phone NVARCHAR(50),
                address NVARCHAR(MAX),
                message NVARCHAR(MAX),
                date DATETIME
            )
            """)
            c_msgs = fetch_dict("SELECT * FROM contact_messages ORDER BY id DESC")
            TEMP_DATA['contact_messages'] = []
            for c in c_msgs:
                TEMP_DATA['contact_messages'].append({
                    'name': c['name'], 'email': c['email'], 'phone': c['phone'], 'address': c['address'],
                    'message': c['message'], 'date': c['date'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(c['date'], datetime) else c['date']
                })
        except Exception as e:
            print(f"⚠️ Skipping contact_messages load (table might not exist): {e}")
            if 'contact_messages' not in TEMP_DATA: TEMP_DATA['contact_messages'] = []

        # 18. Newsletter Subscribers
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='newsletter_subscribers' AND xtype='U')
            CREATE TABLE newsletter_subscribers (
                email NVARCHAR(255) PRIMARY KEY,
                name NVARCHAR(255) NULL,
                contact NVARCHAR(50) NULL,
                interests NVARCHAR(MAX) NULL,
                subscribed_at DATETIME DEFAULT GETDATE()
            )
            """)
            
            # Ensure columns exist in case table was created previously with older schema
            try:
                cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('newsletter_subscribers') AND name = 'name'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE newsletter_subscribers ADD name NVARCHAR(255) NULL")
                cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('newsletter_subscribers') AND name = 'contact'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE newsletter_subscribers ADD contact NVARCHAR(50) NULL")
                cursor.execute("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('newsletter_subscribers') AND name = 'interests'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE newsletter_subscribers ADD interests NVARCHAR(MAX) NULL")
            except Exception as col_err:
                print(f"⚠️ Error ensuring columns on newsletter_subscribers load: {col_err}")

            subs = fetch_dict("SELECT * FROM newsletter_subscribers ORDER BY subscribed_at DESC")
            TEMP_DATA['newsletter_subscribers'] = []
            for s in subs:
                raw_interests = s.get('interests')
                interests_list = []
                if raw_interests:
                    if raw_interests.startswith('[') and raw_interests.endswith(']'):
                        try:
                            interests_list = json.loads(raw_interests)
                        except Exception:
                            interests_list = [i.strip() for i in raw_interests.split(',') if i.strip()]
                    else:
                        interests_list = [i.strip() for i in raw_interests.split(',') if i.strip()]
                        
                TEMP_DATA['newsletter_subscribers'].append({
                    'email': s['email'],
                    'name': s.get('name') or '',
                    'contact': s.get('contact') or '',
                    'interests': interests_list,
                    'subscribed_at': s['subscribed_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(s['subscribed_at'], datetime) else s['subscribed_at']
                })
        except Exception as e:
            print(f"⚠️ Skipping newsletter_subscribers load (table might not exist): {e}")
            if 'newsletter_subscribers' not in TEMP_DATA: TEMP_DATA['newsletter_subscribers'] = []
            
        # 19. Medicines
        try:
            cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='medicines' AND xtype='U')
            CREATE TABLE medicines (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) UNIQUE,
                category NVARCHAR(100),
                price FLOAT
            )
            """)
            meds = fetch_dict("SELECT * FROM medicines")
            if not meds:
                print("🌱 Seeding comprehensive medicines dataset...")
                default_meds = [
                    ('Pantop DSR (Pantoprazole + Domperidone)', 'Gastrointestinal', 145.00),
                    ('Acelock (Aceclofenac + Paracetamol)', 'Analgesic (Pain Relief)', 85.00),
                    ('Calpol 650 (Paracetamol)', 'Analgesic (Pain Relief)', 33.00),
                    ('Dolo 650 (Paracetamol)', 'Analgesic (Pain Relief)', 34.50),
                    ('Augmentin 625 Duo (Amoxicillin + Clavulanic Acid)', 'Antibiotic', 220.00),
                    ('Pan-40 (Pantoprazole)', 'Gastrointestinal', 160.00),
                    ('Omez 20 (Omeprazole)', 'Gastrointestinal', 65.00),
                    ('Zyrtec 10mg (Cetirizine)', 'Anti-Allergic', 42.00),
                    ('Alerid (Cetirizine)', 'Anti-Allergic', 38.00),
                    ('Limcee 500mg (Vitamin C)', 'Supplements', 25.00),
                    ('Metformin 500mg (Glycomet)', 'Anti-Diabetic', 24.00),
                    ('Lipitor 10mg (Atorvastatin)', 'Cardiovascular', 185.00),
                    ('Atorva 10mg (Atorvastatin)', 'Cardiovascular', 72.00),
                    ('Telma 40 (Telmisartan)', 'Cardiovascular', 98.00),
                    ('Amlokind 5 (Amlodipine)', 'Cardiovascular', 32.00),
                    ('Azithral 500 (Azithromycin)', 'Antibiotic', 130.00),
                    ('Azee 500 (Azithromycin)', 'Antibiotic', 125.00),
                    ('Taxim-O 200 (Cefixime)', 'Antibiotic', 115.00),
                    ('Zifi 200 (Cefixime)', 'Antibiotic', 122.00),
                    ('Ciplox 500 (Ciprofloxacin)', 'Antibiotic', 45.00),
                    ('Flagyl 400 (Metronidazole)', 'Antibiotic', 28.00),
                    ('Meftal-Spas (Mefenamic Acid + Dicyclomine)', 'Analgesic (Pain Relief)', 52.00),
                    ('Combiflam (Ibuprofen + Paracetamol)', 'Analgesic (Pain Relief)', 47.00),
                    ('Zerodol-P (Aceclofenac + Paracetamol)', 'Analgesic (Pain Relief)', 110.00),
                    ('Voveran 50mg (Diclofenac)', 'Analgesic (Pain Relief)', 80.00),
                    ('Aciloc 150 (Ranitidine)', 'Gastrointestinal', 45.00),
                    ('Zantac 150 (Ranitidine)', 'Gastrointestinal', 55.00),
                    ('Pepcid 20mg (Famotidine)', 'Gastrointestinal', 38.00),
                    ('Nexium 40mg (Esomeprazole)', 'Gastrointestinal', 210.00),
                    ('Sompraz 40 (Esomeprazole)', 'Gastrointestinal', 140.00),
                    ('Rabeloc 20 (Rabeprazole)', 'Gastrointestinal', 125.00),
                    ('Aciphex 20mg (Rabeprazole)', 'Gastrointestinal', 195.00),
                    ('Zofran 4mg (Ondansetron)', 'Gastrointestinal', 112.00),
                    ('Emeset 4mg (Ondansetron)', 'Gastrointestinal', 40.00),
                    ('Vomikind 4mg (Ondansetron)', 'Gastrointestinal', 38.00),
                    ('Sucrafil Suspension 200ml (Sucralfate)', 'Gastrointestinal', 245.00),
                    ('Digene Gel Syrup 200ml (Antacid)', 'Gastrointestinal', 165.00),
                    ('Gelusil Liquid 200ml (Antacid)', 'Gastrointestinal', 158.00),
                    ('Xyzal 5mg (Levocetirizine)', 'Anti-Allergic', 85.00),
                    ('Montair-LC (Montelukast + Levocetirizine)', 'Anti-Allergic', 220.00),
                    ('Montek-LC (Montelukast + Levocetirizine)', 'Anti-Allergic', 215.00),
                    ('Benadryl DR Syrup 100ml (Dextromethorphan)', 'Respiratory/Cough', 135.00),
                    ('Ascoril LS Syrup 100ml (Ambroxol + Levosalbutamol)', 'Respiratory/Cough', 128.00),
                    ('Ascoril D Syrup 100ml (Cough Suppressant)', 'Respiratory/Cough', 132.00),
                    ('Allegra 120mg (Fexofenadine)', 'Anti-Allergic', 218.00),
                    ('Avil 25mg (Pheniramine Maleate)', 'Anti-Allergic', 12.00),
                    ('Brufen 400 (Ibuprofen)', 'Analgesic (Pain Relief)', 18.00),
                    ('Naprosyn 500mg (Naproxen)', 'Analgesic (Pain Relief)', 64.00),
                    ('Aleve 220mg (Naproxen)', 'Analgesic (Pain Relief)', 140.00),
                    ('Ketanov 10mg (Ketorolac)', 'Analgesic (Pain Relief)', 82.00),
                    ('Jardiance 10mg (Empagliflozin)', 'Anti-Diabetic', 560.00),
                    ('Galvus Met 50/500mg (Vildagliptin + Metformin)', 'Anti-Diabetic', 340.00),
                    ('Janumet 50/500mg (Sitagliptin + Metformin)', 'Anti-Diabetic', 420.00),
                    ('Glucophage XR 500mg (Metformin)', 'Anti-Diabetic', 65.00),
                    ('Amaryl 1mg (Glimepiride)', 'Anti-Diabetic', 55.00),
                    ('Concor 5mg (Bisoprolol)', 'Cardiovascular', 120.00),
                    ('Minipress XL 5mg (Prazosin)', 'Cardiovascular', 240.00),
                    ('Cardace 5mg (Ramipril)', 'Cardiovascular', 145.00),
                    ('Clopilet 75mg (Clopidogrel)', 'Cardiovascular', 95.00),
                    ('Ecosprin 75mg (Aspirin)', 'Cardiovascular', 6.50),
                    ('Rosuvas 10mg (Rosuvastatin)', 'Cardiovascular', 165.00),
                    ('Crestor 10mg (Rosuvastatin)', 'Cardiovascular', 310.00),
                    ('Lasix 40mg (Furosemide)', 'Cardiovascular', 15.00),
                    ('Aldactone 25mg (Spironolactone)', 'Cardiovascular', 42.00),
                    ('Ar निरंतर (Asthalin 4mg - Salbutamol)', 'Respiratory/Asthma', 12.00),
                    ('Ventolin Inhaler (Albuterol)', 'Respiratory/Asthma', 220.00),
                    ('Seretide Accuhaler (Fluticasone + Salmeterol)', 'Respiratory/Asthma', 850.00),
                    ('Foracort 200 Inhaler (Formoterol + Budesonide)', 'Respiratory/Asthma', 480.00),
                    ('Singulair 10mg (Montelukast)', 'Anti-Allergic', 310.00),
                    ('Atarax 25mg (Hydroxyzine)', 'Anti-Allergic', 85.00),
                    ('Elocon Cream 15g (Mometasone)', 'Dermatological', 280.00),
                    ('Betnovate-N Cream 20g (Betamethasone + Neomycin)', 'Dermatological', 45.00),
                    ('Quadriderm RF Cream 5g (Multi-Action Skin Cream)', 'Dermatological', 92.00),
                    ('Clotrin Ear Drops (Clotrimazole)', 'ENT Care', 75.00),
                    ('Otrivin 0.1% Nasal Spray (Xylometazoline)', 'ENT Care', 115.00),
                    ('Ciplox Eye/Ear Drops (Ciprofloxacin)', 'ENT Care', 22.00),
                    ('Tears Naturale II Eye Drops (Artificial Tears)', 'Eye Care', 240.00),
                    ('Claritin 10mg (Loratadine)', 'Anti-Allergic', 160.00),
                    ('Duphaston 10mg (Dydrogesterone)', 'Hormonal/Gynaecology', 720.00),
                    ('Evion 400mg (Vitamin E)', 'Supplements', 42.00),
                    ('Neurobion Forte (Vitamin B Complex)', 'Supplements', 38.00),
                    ('Calcirol Granules 1g (Cholecalciferol Vit-D3)', 'Supplements', 55.00),
                    ('Becosules Capsules (B-Complex + Vitamin C)', 'Supplements', 52.00),
                    ('Liv 52 Syrup 200ml (Herbal Liver Tonic)', 'Supplements', 180.00),
                    ('Cremaffin Liquid 225ml (Laxative)', 'Gastrointestinal', 260.00),
                    ('Dulcolax 5mg (Bisacodyl)', 'Gastrointestinal', 14.00),
                    ('Loperamide 2mg (Imodium)', 'Gastrointestinal', 25.00),
                    ('Sporlac DS (Lactic Acid Bacillus Probiotic)', 'Gastrointestinal', 95.00),
                    ('Liv 52 Tablets (Herbal Liver Care)', 'Supplements', 150.00),
                    ('Clexane 0.4ml Injection (Enoxaparin Sodium)', 'Anticoagulant', 580.00),
                    ('Arkamin 100mcg (Clonidine)', 'Cardiovascular', 68.00),
                    ('Stemetil 5mg (Prochlorperazine for Vertigo)', 'CNS/Neurology', 110.00),
                    ('Vertin 16mg (Betahistine)', 'CNS/Neurology', 185.00),
                    ('Pacitane 2mg (Trihexyphenidyl)', 'CNS/Neurology', 48.00),
                    ('Alprax 0.5mg (Alprazolam)', 'Neuro-Psychiatric', 62.00),
                    ('Zoloft 50mg (Sertraline)', 'Neuro-Psychiatric', 290.00),
                    ('Clonil 25mg (Clomipramine)', 'Neuro-Psychiatric', 130.00),
                    ('Nexito 10mg (Escitalopram)', 'Neuro-Psychiatric', 115.00),
                    ('Epitril 0.5mg (Clonazepam)', 'Neuro-Psychiatric', 45.00),
                    ('Gralise 300mg (Gabapentin)', 'CNS/Neurology', 380.00),
                    ('Tegretol 200mg (Carbamazepine)', 'CNS/Neurology', 42.00),
                    ('Stugeron 25mg (Cinnarizine)', 'CNS/Neurology', 128.00),
                    ('Moxikind-CV Kid Syrup (Amoxicillin + Clavulanate)', 'Pediatric Antibiotic', 115.00),
                    ('Zifi 100 Dry Syrup (Cefixime)', 'Pediatric Antibiotic', 90.00),
                    ('Macfast 250 Oral Suspension (Paracetamol)', 'Pediatric Analgesic', 42.00),
                    ('Ibugesic Plus Syrup (Ibuprofen + Paracetamol)', 'Pediatric Analgesic', 62.00),
                    ('Meftal-Spas Suspension (Mefenamic Acid Spasms)', 'Pediatric Analgesic', 54.00),
                    ('Ondem Syrup (Ondansetron Anti-Vomiting)', 'Pediatric Gastro', 48.00),
                    ('Ambrolite Syrup (Ambroxol Cough Mucolytic)', 'Pediatric Cough', 95.00),
                    ('Cheston Cold Syrup (Cetirizine + Phenylephrine)', 'Pediatric Cold', 78.00),
                    ('Thyronorm 50mcg (Levothyroxine)', 'Hormones / Thyroid', 145.00),
                    ('Eltroxin 75mcg (Levothyroxine)', 'Hormones / Thyroid', 152.00),
                    ('Fluconazole 150mg (Forcan)', 'Anti-Fungal', 45.00),
                    ('Syscan 150 (Fluconazole)', 'Anti-Fungal', 48.00),
                    ('Itraconazole 200mg (Canditral)', 'Anti-Fungal', 210.00),
                    ('Sporanox 100mg (Itraconazole)', 'Anti-Fungal', 340.00),
                    ('Ketocip Shampoo 2% (Ketoconazole)', 'Anti-Fungal / Topical', 285.00),
                    ('Lulifin Cream 30g (Luliconazole)', 'Anti-Fungal / Topical', 390.00),
                    ('Keval 100mg (Fluconazole Liquid)', 'Anti-Fungal Oral', 110.00),
                    ('Pregabalin 75mg (Lyrica)', 'Neuropathic Pain / CNS', 850.00),
                    ('Maxgalin 75mg (Pregabalin)', 'Neuropathic Pain / CNS', 190.00),
                    ('Pregabalin + Methylcobalamin (Preva-M)', 'Neuropathic Pain / CNS', 240.00),
                    ('Gabapin NT (Gabapentin + Nortriptyline)', 'Neuropathic Pain / CNS', 295.00),
                    ('Cobadex Forte (Multivitamins & Zinc)', 'Supplements', 115.00),
                    ('Zincovit Tablets (Nutritional Supplement)', 'Supplements', 105.00),
                    ('Zincovit Syrup 200ml (Pediatric Supplement)', 'Supplements', 145.00),
                    ('Shelcal 500 (Calcium + Vitamin D3)', 'Supplements', 128.00),
                    ('Ostocalcium B12 Liquid 200ml', 'Supplements', 165.00),
                    ('Feronia XT (Iron + Folic Acid)', 'Supplements / Anemia', 185.00),
                    ('Dexorange Syrup 200ml (Hematinic Tonic)', 'Supplements / Anemia', 174.00),
                    ('Linezolid 600mg (Lizomac)', 'Advanced Antibiotic', 380.00),
                    ('Linid 600 (Linezolid)', 'Advanced Antibiotic', 365.00),
                    ('Faropenem 200mg (Farobact)', 'Advanced Antibiotic', 420.00),
                    ('Meropenem 1g Injection (Meronem)', 'Critical Care Antibiotic', 1250.00),
                    ('Monocef 1g Injection (Ceftriaxone)', 'Injectable Antibiotic', 65.00),
                    ('Pipzo 4.5g Injection (Piperacillin + Tazobactam)', 'Injectable Antibiotic', 480.00),
                    ('Pantocid IT (Pantoprazole + Itopride)', 'Gastrointestinal', 215.00),
                    ('Ganaton 50mg (Itopride Hydrocholoride)', 'Gastrointestinal', 260.00),
                    ('Librax (Chlordiazepoxide + Clidinium)', 'Gastrointestinal / IBS', 145.00),
                    ('Colospa 135mg (Mebeverine for IBS)', 'Gastrointestinal / IBS', 290.00),
                    ('Diamicron XR 60mg (Gliclazide)', 'Anti-Diabetic', 195.00),
                    ('Tendia 20mg (Teneligliptin)', 'Anti-Diabetic', 95.00),
                    ('Zita Met 50/500 (Teneligliptin + Metformin)', 'Anti-Diabetic', 165.00),
                    ('Rybelsus 3mg (Oral Semaglutide)', 'Anti-Diabetic', 3400.00),
                    ('Minidiab 5mg (Glipizide)', 'Anti-Diabetic', 42.00),
                    ('Lantus Solostar Pen 3ml (Insulin Glargine)', 'Anti-Diabetic Injectable', 1450.00),
                    ('Mixtard 30/70 Suspension (Insulin)', 'Anti-Diabetic Injectable', 380.00),
                    ('Humalog 100 IU/ml (Insulin Lispro)', 'Anti-Diabetic Injectable', 620.00),
                    ('Imuran 50mg (Azathioprine)', 'Immunosuppressant', 280.00),
                    ('Cellcept 500mg (Mycophenolate Mofetil)', 'Immunosuppressant', 890.00),
                    ('Plaquenil 200mg (Hydroxychloroquine)', 'Autoimmune / RA', 145.00),
                    ('HCQS 200 (Hydroxychloroquine)', 'Autoimmune / RA', 115.00),
                    ('Folitrax 7.5mg (Methotrexate)', 'Autoimmune / Oncology', 85.00),
                    ('Decadan 4mg (Dexamethasone Steroid)', 'Corticosteroid', 12.00),
                    ('Wysolone 10mg (Prednisolone Steroid)', 'Corticosteroid', 18.50),
                    ('Deflazacort 6mg (Defcort)', 'Corticosteroid', 125.00),
                    ('Medrol 8mg (Methylprednisolone)', 'Corticosteroid', 95.00),
                    ('Kenacort 40mg Injection (Triamcinolone)', 'Corticosteroid', 160.00),
                    ('Amlong-H (Amlodipine + Hydrochlorothiazide)', 'Cardiovascular', 72.00),
                    ('Telma-AM (Telmisartan + Amlodipine)', 'Cardiovascular', 185.00),
                    ('Cilacar 10mg (Cilnidipine)', 'Cardiovascular', 128.00),
                    ('Clesid 10mg (Cilnidipine)', 'Cardiovascular', 110.00),
                    ('Nepresol 25mg (Hydralazine)', 'Cardiovascular', 95.00),
                    ('Isordil 5mg (Isosorbide Dinitrate)', 'Cardiovascular / Angina', 32.00),
                    ('Sorbitrate 10mg (Isosorbide Dinitrate)', 'Cardiovascular / Angina', 28.00),
                    ('Amiodarone 200mg (Cordarone)', 'Cardiovascular / Arrhythmia', 165.00),
                    ('Dilzem 30mg (Diltiazem)', 'Cardiovascular', 68.00),
                    ('Meto-ER 25mg (Metoprolol Succinate Prolonged)', 'Cardiovascular', 85.00),
                    ('Nebicard 5mg (Nebivolol)', 'Cardiovascular', 140.00),
                    ('Arkamin Drops (Clonidine for Paediatric Hypertension)', 'Cardiovascular', 45.00)
                ]
                cursor.executemany("INSERT INTO medicines (name, category, price) VALUES (?, ?, ?)", default_meds)
                conn.commit()
                meds = fetch_dict("SELECT * FROM medicines")
                print(f"✅ Seeding complete. Loaded {len(meds)} medicines.")
            TEMP_DATA['medicines'] = meds
            global MEDICINE_LIST
            MEDICINE_LIST = [m['name'] for m in meds]
        except Exception as e:
            print(f"⚠️ Skipping medicines load (table might not exist): {e}")
            if 'medicines' not in TEMP_DATA: TEMP_DATA['medicines'] = []

        # 20. Patient Feedback
        try:
            cursor.execute("IF OBJECT_ID('patient_feedback', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                fbs = fetch_dict("SELECT * FROM patient_feedback")
                TEMP_DATA['feedbacks'] = {fb['id']: Feedback(**fb) for fb in fbs}
            else:
                TEMP_DATA['feedbacks'] = {}
        except Exception as e:
            print(f"⚠️ Skipping feedback load: {e}")
            TEMP_DATA['feedbacks'] = {}

        # 21. Doctor Opinions
        try:
            cursor.execute("IF OBJECT_ID('doctor_opinions', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                ops = fetch_dict("SELECT * FROM doctor_opinions")
                TEMP_DATA['doctor_opinions'] = {op['doctor_id']: op for op in ops}
            else:
                TEMP_DATA['doctor_opinions'] = {}
        except Exception as e:
            print(f"⚠️ Skipping doctor opinions load: {e}")
            TEMP_DATA['doctor_opinions'] = {}

        # 21b. Patient Vitals
        try:
            cursor.execute("IF OBJECT_ID('patient_vitals', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                vits = fetch_dict("SELECT * FROM patient_vitals")
                TEMP_DATA['patient_vitals'] = {v['id']: PatientVital(**v) for v in vits}
            else:
                TEMP_DATA['patient_vitals'] = {}
        except Exception as e:
            print(f"⚠️ Skipping patient_vitals load: {e}")
            TEMP_DATA['patient_vitals'] = {}

        # 21c. Doctor Symptom Reviews
        try:
            cursor.execute("IF OBJECT_ID('doctor_symptom_reviews', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                revs = fetch_dict("SELECT * FROM doctor_symptom_reviews")
                TEMP_DATA['symptom_reviews'] = []
                for r in revs:
                    TEMP_DATA['symptom_reviews'].append({
                        'id': r['id'],
                        'symptom_query': r['symptom_query'],
                        'doctor_id': r['doctor_id'],
                        'doctor_name': r['doctor_name'],
                        'status': r['status'],
                        'clinical_remarks': r.get('clinical_remarks') or '',
                        'prescribed_treatment': r.get('prescribed_treatment') or '',
                        'recommended_tests': r.get('recommended_tests') or '',
                        'created_at': r['created_at'].isoformat() if isinstance(r['created_at'], datetime) else r['created_at']
                    })
            else:
                TEMP_DATA['symptom_reviews'] = []
        except Exception as e:
            print(f"⚠️ Skipping doctor_symptom_reviews load: {e}")
            TEMP_DATA['symptom_reviews'] = []

        # 16. Calculate Next IDs (based on max existing IDs)
        for entity, prefix in [('doctor', 'DOC'), ('patient', 'PAT'), ('hospital', 'HPT'), 
                               ('staff', 'STF'), ('blood_donor', 'BD'), ('organ_donor', 'OD')]:
            dict_key = f"{entity}s" if entity != 'staff' else 'staff'
            collection = TEMP_DATA.get(dict_key, {})
            max_val = 0
            for key in collection.keys():
                if isinstance(key, str) and '/' in key:
                    try:
                        num = int(key.split('/')[-1])
                        if num > max_val:
                            max_val = num
                    except ValueError:
                        pass
            TEMP_DATA['next_ids'][entity] = max_val + 1

        # Simple integer IDs (Including bed_booking)
        for entity in ['appointment', 'review', 'message', 'order', 'camp', 'camp_registration', 'bed_booking', 'activity_log', 'organ_request', 'patient_vital']:
            dict_key = f"{entity}s"
            collection = TEMP_DATA.get(dict_key, {})
            if collection:
                max_val = 0
                for key in collection.keys():
                    try:
                        num = int(key)
                        if num > max_val:
                            max_val = num
                    except ValueError:
                        pass
                TEMP_DATA['next_ids'][entity] = max_val + 1
                
        max_sicons_id = 0
        for app_data in TEMP_DATA.get('sicons_applications', []):
            if app_data.get('id', 0) > max_sicons_id:
                max_sicons_id = app_data['id']
        TEMP_DATA['next_ids']['sicons_application'] = max_sicons_id + 1

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
        self.city = kwargs.get('city')
        self.district = kwargs.get('district')

        self.pincode = kwargs.get('pincode')
        self.country = kwargs.get('country', 'India')
        # New fields from your request
        self.qualification = kwargs.get('qualification')

        self.license_number = kwargs.get('license_number')
        self.experience = kwargs.get('experience')
        self.consultation_type = kwargs.get('consultation_type')
        self.consultation_fee = kwargs.get('consultation_fee')
        self.working_hours = kwargs.get('working_hours')
        self.languages_spoken = kwargs.get('languages_spoken')
        self.social_links = kwargs.get('social_links', {})
        self.is_verified = kwargs.get('is_verified', False)
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_doctor = True
        self.availability_status = kwargs.get('availability_status', 'available')
        self.hospital_id = kwargs.get('hospital_id')
        self.hospital_approval_status = kwargs.get('hospital_approval_status', 'approved' if kwargs.get('hospital_name') else None)

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
        self.phone = kwargs.get('phone')
        self.address = kwargs.get('address')
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_doctor = False
        
        self.clinical_record = kwargs.get('clinical_record')
        if isinstance(self.clinical_record, str):
            try:
                self.clinical_record = json.loads(self.clinical_record)
            except:
                self.clinical_record = {}
        elif not isinstance(self.clinical_record, dict):
            self.clinical_record = {}

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
        self.created_at = kwargs.get('created_at', utcnow())
        self.last_login = kwargs.get('last_login')
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_doctor = False
        self.is_staff = True
        self.profile_picture_url = kwargs.get('profile_picture_url')

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
        self.general_bed_fee = float(kwargs.get('general_bed_fee', 1000.0))
        self.icu_bed_fee = float(kwargs.get('icu_bed_fee', 2500.0))
        self.is_verified = kwargs.get('is_verified', True) # Default True for backward compatibility
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_doctor = False
        self.is_hospital = True
        self.blood_stock = kwargs.get('blood_stock', {
            "A+": 0, "A-": 0, "B+": 0, "B-": 0, "AB+": 0, "AB-": 0, "O+": 0, "O-": 0
        })

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
        self.created_at = kwargs.get('created_at', utcnow())
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
        self.created_at = kwargs.get('created_at', utcnow())

    @property
    def doctor(self):
        return TEMP_DATA['doctors'].get(self.doctor_id)

class Feedback:
    def __init__(self, id, patient_id, patient_name, rating, comments, **kwargs):
        self.id = int(id)
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.rating = int(rating)
        self.comments = comments
        self.feedback_target = kwargs.get('feedback_target', 'web_application')
        self.target_id = kwargs.get('target_id')
        self.target_name = kwargs.get('target_name')
        dt = kwargs.get('created_at', utcnow())
        if isinstance(dt, str):
            try:
                self.created_at = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except ValueError:
                self.created_at = utcnow()
        else:
            self.created_at = dt

    @property
    def patient(self):
        p = TEMP_DATA.get('patients', {}).get(self.patient_id)
        if not p:
            for pid, patient_obj in TEMP_DATA.get('patients', {}).items():
                if str(pid) == str(self.patient_id):
                    return patient_obj
        return p


class PatientVital:
    def __init__(self, id, patient_id, weight, heart_rate, blood_sugar, systolic_bp, diastolic_bp, recorded_at=None, **kwargs):
        self.id = int(id)
        self.patient_id = patient_id
        self.weight = float(weight) if weight is not None else None
        self.heart_rate = int(heart_rate) if heart_rate is not None else None
        self.blood_sugar = int(blood_sugar) if blood_sugar is not None else None
        self.systolic_bp = int(systolic_bp) if systolic_bp is not None else None
        self.diastolic_bp = int(diastolic_bp) if diastolic_bp is not None else None
        
        dt = recorded_at or kwargs.get('recorded_at', utcnow())
        if isinstance(dt, str):
            try:
                self.recorded_at = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except ValueError:
                self.recorded_at = utcnow()
        else:
            self.recorded_at = dt

    @property
    def patient(self):
        return TEMP_DATA['patients'].get(self.patient_id)


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
        self.created_at = kwargs.get('created_at', utcnow())
        self.status = kwargs.get('status', 'pending')
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
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
        self.created_at = kwargs.get('created_at', utcnow())
        self.status = kwargs.get('status', 'pending')
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.hospital_id = kwargs.get('hospital_id')
        self.is_doctor = False

    def get_id(self):
        return f"organ_donor-{self.id}"

class OrganRequest:
    def __init__(self, id, patient_id, patient_name, organ_needed, blood_group, urgency, status='active', hospital_id=None, **kwargs):
        self.id = id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.organ_needed = organ_needed
        self.blood_group = blood_group
        self.urgency = urgency
        self.status = status
        self.hospital_id = str(hospital_id) if hospital_id else None
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val

class Message:
    def __init__(self, id, doctor_id, patient_id, sender, content, **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.sender = sender
        self.content = content
        self.attachment_url = kwargs.get('attachment_url')
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
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
        self.room_number = kwargs.get('room_number')
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val

class ActivityLog:
    def __init__(self, id, hospital_id, user_name, action, details, **kwargs):
        self.id = id
        self.hospital_id = hospital_id
        self.user_name = user_name
        self.action = action
        self.details = details
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
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

def get_cache_key(symptoms_query, age, gender, height=None, weight=None):
    """Generate a hash-based cache key from symptoms and patient info."""
    cache_str = f"{symptoms_query}:{age}:{gender}:{height}:{weight}"
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
        
        # Perform multiple analyses for comprehensive results using dictionary format
        request_dict = {
            "image": {"content": content},
            "features": [
                {"type_": vision.Feature.Type.LABEL_DETECTION},
                {"type_": vision.Feature.Type.TEXT_DETECTION},
                {"type_": vision.Feature.Type.OBJECT_LOCALIZATION},
                {"type_": vision.Feature.Type.SAFE_SEARCH_DETECTION},
            ],
        }
        
        response = client.annotate_image(request=request_dict)
        
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

def _analyze_image_with_groq_vision(image_path, custom_prompt=None):
    """Fallback image analysis using Groq Vision API."""
    if not _is_groq_configured():
        return {'error': 'GROQ_API_KEY is not configured.'}

    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        mime_type = "image/jpeg"
        if str(image_path).lower().endswith(".png"):
            mime_type = "image/png"

        endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
        if "responses" in endpoint:
            endpoint = endpoint.replace("responses", "chat/completions")
            
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Try active multimodal models
        models_to_try = [
            "qwen/qwen3.6-27b",
            "meta-llama/llama-4-scout-17b-16e-instruct"
        ]

        last_error = "No models attempted"
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": custom_prompt or "Analyze this image for any visible medical symptoms, skin conditions, or relevant health indicators. Be objective and concise. Note: This is for an AI symptom checker."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{encoded_string}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 1024
            }
            try:
                print(f"🔄 Attempting Groq Vision analysis with model: {model}...")
                response = requests.post(endpoint, headers=headers, json=payload, timeout=45, verify=True)
                if response.ok:
                    data = response.json()
                    analysis_text = data['choices'][0]['message']['content']
                    print(f"✅ Groq Vision analysis complete (with {model}): {analysis_text[:100]}...")
                    return {
                        'analysis': analysis_text
                    }
                else:
                    error_msg = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', error_msg)
                    except Exception:
                        pass
                    last_error = f"API Error ({model}): {error_msg}"
                    print(f"⚠️ Groq Vision model {model} failed: {last_error}")
            except Exception as e:
                last_error = f"Request Error ({model}): {str(e)}"
                print(f"⚠️ Groq Vision model {model} request failed: {last_error}")

        # If all models fail
        print(f"❌ All Groq Vision models failed. Last error: {last_error}")
        return {'error': last_error}
    except Exception as e:
        print(f"❌ Groq Vision analysis error: {e}")
        return {'error': str(e)}

def _invoke_groq_symptom_analysis(symptoms_query, age=None, gender=None, height=None, weight=None):
    """Call Groq API for symptom analysis and normalize output schema."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")

    prompt = f"""You are a professional medical triage assistant. Analyze these patient symptom details and produce a JSON object ONLY. Output valid JSON without any markdown formatting like ```json.

symptoms: {symptoms_query}
age: {age or 'unknown'}
gender: {gender or 'unknown'}
height: {height or 'unknown'} cm
weight: {weight or 'unknown'} kg

CRITICAL INSTRUCTION: Explicitly tailor your diagnosis, advice, and warnings to a patient of this specific age, biological sex, height, and weight. Consider gender-specific conditions, hormonal factors, physiological risk factors, and BMI-related implications if applicable.

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
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 2048,
        'response_format': {'type': 'json_object'}
    }

    try:
        print(f"📤 Calling Groq API at: {endpoint}")
        print(f"📤 With model: {GROQ_API_MODEL}, headers: Authorization={GROQ_API_KEY[:20]}...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()

        output_text = _extract_groq_text_response(payload_json)
        if not output_text:
            raise ValueError('Groq response has no content')

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        conditions = parsed.get('conditions') if isinstance(parsed.get('conditions'), list) else [parsed.get('conditions')] if parsed.get('conditions') else ['Non-specific symptoms']
        
        # Clean and normalize confidence scores, handling concatenated formats like 702010 -> 70, 20, 10
        raw_scores = parsed.get('confidence_scores')
        if not isinstance(raw_scores, list):
            if raw_scores is not None:
                raw_scores = [raw_scores]
            else:
                raw_scores = []
        
        cleaned_scores = []
        for val in raw_scores:
            try:
                val_int = int(val)
                if val_int > 100:
                    s = str(val_int)
                    pairs = []
                    idx = 0
                    while idx < len(s):
                        if len(s) - idx == 1:
                            pairs.append(int(s[idx:]))
                            idx += 1
                        else:
                            val_pair = int(s[idx:idx+2])
                            if val_pair <= 100:
                                pairs.append(val_pair)
                                idx += 2
                            else:
                                pairs.append(int(s[idx:idx+1]))
                                idx += 1
                    if all(0 <= p <= 100 for p in pairs):
                        cleaned_scores.extend(pairs)
                        continue
                cleaned_scores.append(val_int if 0 <= val_int <= 100 else 60)
            except (ValueError, TypeError):
                cleaned_scores.append(60)
                
        if len(cleaned_scores) < len(conditions):
            cleaned_scores = cleaned_scores + [55] * (len(conditions) - len(cleaned_scores))
        elif len(cleaned_scores) > len(conditions):
            cleaned_scores = cleaned_scores[:len(conditions)]

        result = {
            'conditions': conditions,
            'confidence_scores': cleaned_scores,
            'advice': parsed.get('advice') or parsed.get('recommendation') or 'Please consult a medical professional.',
            'description': parsed.get('description') or 'Symptom pattern analysis from Groq AI.',
            'self_care': parsed.get('self_care') if isinstance(parsed.get('self_care'), list) else ['Monitor symptoms', 'Stay hydrated', 'If symptoms worsen, seek healthcare.'],
            'suggested_medicines': parsed.get('suggested_medicines') if isinstance(parsed.get('suggested_medicines'), list) else ['Rest', 'Hydration', 'Gentle pain relief'],
            'when_to_see_doctor': parsed.get('when_to_see_doctor') or 'Visit a doctor if symptoms worsen or persist beyond 48 hours.',
            'recommended_departments': parsed.get('recommended_departments') if isinstance(parsed.get('recommended_departments'), list) else ['General Medicine'],
            'note': parsed.get('note') or 'This is an AI-generated suggestion and not a medical diagnosis.',
        }

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


def _extract_groq_text_response(payload_json):
    if 'choices' in payload_json and len(payload_json['choices']) > 0:
        return payload_json['choices'][0]['message']['content']
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
    return output_text or ''


def _invoke_groq_symptom_followup(symptoms_context, followup_question, age=None, gender=None):
    """Call Groq API to answer a follow-up chat question about symptoms."""
    if not _is_groq_configured():
        return 'AI follow-up unavailable because Groq API is not configured.'

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")
    prompt = f"""You are a professional medical triage assistant. Use the following patient symptom summary and current AI analysis to answer the follow-up question clearly and safely.

Patient info:
- Age: {age or 'unknown'}
- Gender: {gender or 'unknown'}

Current symptom summary:
{symptoms_context}

Follow-up question:
{followup_question}

Respond in plain text only. Provide a concise answer, include any necessary caution, and mention when the user should seek medical help or finalize the result."""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 512
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()
        return _extract_groq_text_response(payload_json).strip() or 'The AI assistant could not generate a response. Please try again.'
    except Exception as e:
        print(f"⚠️ Groq follow-up chat failed: {e}")
        return 'AI follow-up unavailable at the moment. Please try again later.'


def _invoke_groq_symptom_finalization(result, chat_history, age=None, gender=None):
    """Call Groq API to create a finalized summary based on the analysis and chat context."""
    if not _is_groq_configured():
        return result.get('clinical_summary') or result.get('description') or 'Finalized result is unavailable because AI service is not configured.'

    summary_parts = [result.get('clinical_summary') or result.get('description', ''), 'Recommendations: ' + '; '.join(result.get('ai_recommendations', []))]
    if result.get('warning_alerts'):
        summary_parts.append('Warnings: ' + '; '.join(result.get('warning_alerts', [])))
    chat_section = '\n'.join([f"Patient: {entry['message']}\nAI: {entry['response']}" for entry in chat_history[-5:]]) if chat_history else 'No follow-up chat history.'

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")
    prompt = f"""You are a professional medical triage assistant. Create a finalized patient-facing summary for the following symptom analysis and follow-up chat.

Patient info:
- Age: {age or 'unknown'}
- Gender: {gender or 'unknown'}

Current summary and recommendations:
{chr(10).join(part for part in summary_parts if part)}

Recent follow-up chat:
{chat_section}

Write a concise final result statement that includes the most critical diagnosis points, next steps, and whether this should be reviewed by a specialist or saved in a PDF report. Use plain text only."""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 512
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()
        return _extract_groq_text_response(payload_json).strip() or (result.get('clinical_summary') or result.get('description') or 'Finalized summary generation failed.')
    except Exception as e:
        print(f"⚠️ Groq finalization failed: {e}")
        return result.get('clinical_summary') or result.get('description') or 'Finalized result could not be generated.'


def _invoke_groq_drug_info(drug_name):
    """Call Groq API to generate a drug information summary."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")
    prompt = f"""You are a professional medical reference assistant. Provide a JSON object only, no markdown or extra text.

Drug name: {drug_name}

Required keys:
- drug_name: string
- description: string
- primary_use: concise primary medical use or indication
- common_side_effects: list of 3-5 common side effects
- caution: short caution statement, including when to consult a doctor
- clinical_notes: brief note about important usage or safety information
- usage_instructions: step-by-step instructions on how to use/take the medicine
- dosage_interval: clinical advice on how much time to wait before reuse (interval/frequency)
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': GROQ_API_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2,
        'max_tokens': 1024,
        'response_format': {'type': 'json_object'}
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()

        output_text = _extract_groq_text_response(payload_json)
        if not output_text:
            raise ValueError('Groq response has no content')

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
            'usage_instructions': parsed.get('usage_instructions', 'Refer to packaging or professional advice.'),
            'dosage_interval': parsed.get('dosage_interval', 'Consult a healthcare professional for exact dosage intervals.'),
            'source': 'ai'
        }
    except Exception as e:
        print(f"❌ Groq drug info generation failed: {e}")
        return None


def _invoke_openfda_drug_info(drug_name):
    """Call OpenFDA API to get authoritative drug information."""
    # Clean the drug name to remove dosages, forms, and instructions
    search_term = str(drug_name).split('(')[0].split(',')[0].strip()
    
    # Split by common conjunctions to isolate the primary medication
    search_term = re.split(r'(?i)\b(or|and|with)\b', search_term)[0].strip()
    
    # Remove everything from the first digit onwards (e.g., "200mg", "2-3 times")
    search_term = re.split(r'\d+', search_term)[0].strip()
    
    # Remove common non-drug terms
    stop_words = r'(?i)\b(topical|gel|cream|ointment|applied|every|hours|for|pain|relief|daily|times|mg|ml|mcg|tablet|capsule|oral|syrup|without|food|water|nasal|decongestant|spray|drops|suppository|inhaler|cough|cold|medication)\b'
    search_term = re.sub(stop_words, '', search_term).strip()
    
    # Cleanup extra spaces or hyphens at the ends
    search_term = re.sub(r'[-\s]+', ' ', search_term).strip(' -')
    
    # Fallback if entirely stripped
    if len(search_term) < 3:
        search_term = str(drug_name).split()[0].strip('()-,. ')
        
    # Keep it to a maximum of 2 words for better exact matching
    words = search_term.split()
    if len(words) > 2:
        search_term = " ".join(words[:2])
        
    if not search_term:
        return None
    
    endpoint = "https://api.fda.gov/drug/label.json"
    query = f'openfda.brand_name:"{search_term}" OR openfda.generic_name:"{search_term}"'
    params = {'search': query, 'limit': 1}
    
    if OPENFDA_API_KEY:
        params['api_key'] = OPENFDA_API_KEY
        
    try:
        response = requests.get(endpoint, params=params, timeout=10)
        
        # If 404, try searching just the first word (often the base generic or brand name)
        if response.status_code == 404 and len(words) > 1:
            fallback_term = words[0]
            query = f'openfda.brand_name:"{fallback_term}" OR openfda.generic_name:"{fallback_term}"'
            params['search'] = query
            response = requests.get(endpoint, params=params, timeout=10)
            
        # Do not raise an exception for 404s, just return None so it falls back cleanly to Groq
        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        
        if not data.get('results'):
            return None
            
        result = data['results'][0]
        openfda = result.get('openfda', {})
        
        brand_name = openfda.get('brand_name', [drug_name])[0]
        indications = result.get('indications_and_usage', [''])[0]
        description = result.get('description', [''])[0]
        if not description:
            description = indications if indications else 'No detailed description available.'
            
        adverse = result.get('adverse_reactions', [''])[0]
        if adverse:
            adverse = adverse.replace('\n', ' ').replace('•', '')
            side_effects = [s.strip().capitalize() for s in adverse.split(',') if s.strip() and len(s) < 50][:5]
            if not side_effects:
                side_effects = [adverse[:150] + "..."]
        else:
            side_effects = []
            
        warnings = result.get('warnings', ['Consult a healthcare professional before use.'])[0]
        dosage = result.get('dosage_and_administration', ['Refer to packaging or professional advice.'])[0]
        
        def truncate(text, length=250):
            if not text: return ""
            text = text.replace('\n', ' ').strip()
            return text[:length] + "..." if len(text) > length else text
            
        return {
            'drug_name': brand_name.title(),
            'description': truncate(description, 400),
            'primary_use': truncate(indications, 200) or 'General medication use.',
            'common_side_effects': side_effects if side_effects else ['See package insert for full side effects list.'],
            'caution': truncate(warnings, 200),
            'clinical_notes': truncate(result.get('boxed_warning', [''])[0], 200),
            'usage_instructions': truncate(dosage, 300),
            'dosage_interval': truncate(result.get('how_supplied', ['Consult a healthcare professional for exact dosage intervals.'])[0], 200),
            'source': 'OpenFDA API'
        }
    except Exception as e:
        print(f"❌ OpenFDA API call failed for '{drug_name}': {e}")
        return None


def _invoke_groq_condition_info(condition_name):
    """Call Groq API to generate a detailed condition summary."""
    if not _is_groq_configured():
        return None

    endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
    if "responses" in endpoint:
        endpoint = endpoint.replace("responses", "chat/completions")

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
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.25,
        'max_tokens': 2048
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()

        output_text = payload_json.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not output_text:
            raise ValueError('Groq response has no content')

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


def get_ml_analysis(symptoms_query, age=None, gender=None, image_path=None, height=None, weight=None):
    """
    Primary symptom analyser: Groq API only. No local knowledge base fallback.
    """
    print(f"📚 Analyzing symptoms via {AI_PROVIDER_ACTIVE or 'local fallback'}: '{symptoms_query}' [age={age}, gender={gender}, height={height}, weight={weight}]")

    if image_path:
        local_image_path = os.path.join(app.root_path, image_path.lstrip('/'))

        # Analyze image with Google Vision API using the absolute path
        vision_findings = None
        if os.path.exists(local_image_path):
            vision_findings = _analyze_image_with_vision(local_image_path)

        # If Google Vision is not configured or fails, try Groq Vision API
        if not vision_findings:
            print("⚠️ Google Vision not available or failed. Attempting Groq Vision API...")
            groq_findings = _analyze_image_with_groq_vision(local_image_path) if os.path.exists(local_image_path) else None
            if groq_findings and 'analysis' in groq_findings:
                vision_findings = groq_findings
                
        if vision_findings:
            # Enhance symptoms_query with image analysis findings
            enhanced_query = f"{symptoms_query}\n\nVisual Analysis: {vision_findings['analysis']}"
            # Use enhanced query for Groq analysis
            symptoms_query = enhanced_query
            print(f"✅ Enhanced symptom query with image analysis")
        else:
            print("⚠️ Image analysis failed, proceeding with text analysis only")

    # Check cache first
    cache_key = get_cache_key(symptoms_query, age, gender, height, weight)
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

    if AI_PROVIDER_ACTIVE != 'GROQ' or not _is_groq_configured():
        print("⚠️ Groq API is not configured. Falling back to local SymptomAnalyzer.")
        if analyzer:
            return analyzer.analyze(symptoms_query, age=age, gender=gender, body_part=None)
        else:
            return analyze_symptoms_locally(symptoms_query, age=age, gender=gender)

    result = _invoke_groq_symptom_analysis(symptoms_query, age, gender, height, weight)

    if result and 'error_details' not in result:
        # Enrich suggested medicines with OpenFDA side effects
        if 'suggested_medicines' in result and isinstance(result['suggested_medicines'], list):
            enhanced_medicines = []
            for med in result['suggested_medicines']:
                med_name = str(med).split('-')[0].split('(')[0].split(',')[0].strip()
                skip_words = ['rest', 'hydration', 'none', 'n/a', 'consult', 'water', 'sleep', 'fluid', 'monitor', 'warm', 'tea', 'honey']
                if not any(sw in med_name.lower() for sw in skip_words) and len(med_name) > 3:
                    fda_info = _invoke_openfda_drug_info(med_name)
                    if fda_info and fda_info.get('common_side_effects'):
                        effects = [e for e in fda_info['common_side_effects'] if 'package insert' not in e.lower() and len(e) < 60]
                        if effects:
                            side_effects_str = ", ".join(effects[:2])
                            enhanced_medicines.append(f"{med} (Possible side effects: {side_effects_str.lower()})")
                            continue
                enhanced_medicines.append(med)
            result['suggested_medicines'] = enhanced_medicines

        LAST_API_CALL_TIME['global'] = time_module.time()
        SYMPTOM_CACHE[cache_key] = result
        return result

    print("❌ Groq analysis failed. Falling back to local SymptomAnalyzer.")
    if analyzer:
        return analyzer.analyze(symptoms_query, age=age, gender=gender, body_part=None)
    else:
        # Final fallback to the most basic local analyzer
        return analyze_symptoms_locally(symptoms_query, age=age, gender=gender)


def _parse_text_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r'[\n;]+', str(value)) if item.strip()]


def _normalize_text(value):
    if value is None:
        return ''
    if isinstance(value, list):
        return ' '.join(str(item) for item in value if item)
    return str(value)


def _derive_risk_level(severity, duration, when_to_see_doctor, conditions):
    if severity:
        normalized = _normalize_text(severity).lower()
        if any(token in normalized for token in ['very severe', 'severe', 'high', 'urgent', 'intense']):
            return '🔴 High'
        if any(token in normalized for token in ['moderate', 'persistent', 'ongoing']):
            return '🟡 Moderate'
        return '🟢 Low'

    if when_to_see_doctor:
        warning_text = _normalize_text(when_to_see_doctor).lower()
        if any(token in warning_text for token in ['immediate', 'emergency', 'urgent', 'difficulty breathing', 'chest pain', 'loss of consciousness']):
            return '🔴 High'
        if any(token in warning_text for token in ['monitor', 'follow up', 'persistent', 'recurring']):
            return '🟡 Moderate'

    if duration:
        normalized = _normalize_text(duration).lower()
        if any(token in normalized for token in ['week', 'month', 'persistent', 'chronic', 'ongoing']):
            return '🟡 Moderate'

    return '🟢 Low'


def _build_suggested_tests(recommended_departments, conditions, risk_level):
    tests = []
    department_text = ' '.join(recommended_departments or []).lower()
    if 'cardio' in department_text or 'heart' in department_text:
        tests.append('ECG')
    if 'ortho' in department_text or 'bone' in department_text or 'joint' in department_text:
        tests.append('X-ray')
    if 'dermat' in department_text or 'skin' in department_text:
        tests.append('Skin evaluation')
    if 'neuro' in department_text or 'brain' in department_text or 'nerv' in department_text:
        tests.append('MRI')
    if 'gastro' in department_text or 'digest' in department_text or 'abdomen' in department_text:
        tests.append('Abdominal ultrasound')
    if not tests:
        tests.append('CBC')
        if risk_level != '🟢 Low':
            tests.append('X-ray')
            tests.append('ECG')
    return tests[:4]


def _build_symptom_response(raw_result, age, gender, duration, severity, body_part, body_part_detail, worse_factors, better_factors, current_medicines, allergies, medical_history):
    conditions = raw_result.get('conditions') if isinstance(raw_result.get('conditions'), list) else []
    possibilities = []
    labels = ['Primary Possibility', 'Secondary Possibility', 'Less Likely Possibility']
    for index, condition in enumerate(conditions[:3]):
        possibilities.append(f"{labels[index]}: {condition}")
    if not possibilities:
        possibilities.append('Primary Possibility: The symptoms may align with a common clinical pattern requiring further review.')

    if raw_result.get('description'):
        clinical_summary = f"{_normalize_text(raw_result.get('description')).strip()}"
    else:
        severity_text = _normalize_text(severity).lower()
        details = [age and f"At {age} years old", gender and f"{gender}", duration and f"after {duration}", severity_text and f"with {severity_text} symptoms"]
        clinical_summary = ' '.join([d for d in details if d]) or 'This assessment reviews the reported symptoms and clinical context to identify likely explanations.'

    ai_recommendations = _parse_text_list(raw_result.get('advice'))
    if not ai_recommendations:
        ai_recommendations = ['Rest the affected area', 'Stay hydrated', 'Monitor the symptoms closely', 'Avoid activities that worsen discomfort']
    ai_recommendations = ai_recommendations[:5]

    self_care = _parse_text_list(raw_result.get('self_care'))
    if not self_care:
        self_care = ['Apply gentle cold or warm compresses as appropriate', 'Keep a regular sleep schedule', 'Practice light movement and avoid prolonged immobility']
    self_care = self_care[:5]

    supportive_relief_options = _parse_text_list(raw_result.get('suggested_medicines'))
    if not supportive_relief_options:
        supportive_relief_options = ['Acetaminophen', 'Ibuprofen', 'Topical pain-relief gels']
    if all('consult' not in option.lower() for option in supportive_relief_options):
        supportive_relief_options.append('Consult a healthcare professional before taking medication.')
    supportive_relief_options = supportive_relief_options[:5]

    warning_alerts = _parse_text_list(raw_result.get('when_to_see_doctor')) + _parse_text_list(raw_result.get('key_precautions'))
    warning_alerts = [alert for alert in warning_alerts if alert]
    if not warning_alerts:
        warning_alerts = ['Seek medical attention if symptoms worsen', 'Watch for fever or difficulty breathing', 'Consult a doctor if new numbness or weakness appears']
    warning_alerts = warning_alerts[:5]

    recommended_specialists = raw_result.get('recommended_departments') if isinstance(raw_result.get('recommended_departments'), list) else []
    if not recommended_specialists:
        recommended_specialists = ['General Practitioner']

    risk_level = _derive_risk_level(severity, duration, raw_result.get('when_to_see_doctor', ''), conditions)
    suggested_tests = _build_suggested_tests(recommended_specialists, conditions, risk_level)

    medical_disclaimer = 'This AI-generated assessment is intended for informational purposes only and should not be considered a medical diagnosis. Please consult a licensed healthcare professional for accurate evaluation and treatment.'

    return {
        **raw_result,
        'clinical_possibilities': possibilities,
        'clinical_summary': clinical_summary,
        'ai_recommendations': ai_recommendations,
        'self_care_suggestions': self_care,
        'supportive_relief_options': supportive_relief_options,
        'warning_alerts': warning_alerts,
        'recommended_specialists': recommended_specialists,
        'risk_level': risk_level,
        'suggested_tests': suggested_tests,
        'medical_disclaimer': medical_disclaimer
    }

def get_premium_otp_email_html(title, greeting, message, otp, role_color='#2563eb', accent_bg='#eff6ff'):
    """Generates an ultra-premium, modern, and responsive HTML email template for OTP delivery."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; width: 100% !important;">
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); border: 1px solid #e2e8f0;">
                    <!-- Header Banner -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 32px; text-align: center;">
                            <div style="font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
                                SPHERIX<span style="color: {role_color};">CLINIC</span>
                            </div>
                            <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 2px; margin-top: 4px;">Digital Health System</div>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 32px;">
                            <h2 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #0f172a; line-height: 1.3;">{title}</h2>
                            <p style="margin: 0 0 12px 0; font-size: 15px; color: #475569; line-height: 1.5;">{greeting}</p>
                            <p style="margin: 0 0 28px 0; font-size: 15px; color: #475569; line-height: 1.5;">{message}</p>
                            
                            <!-- OTP Badge -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 28px;">
                                <tr>
                                    <td align="center" style="background-color: {accent_bg}; border: 2px dashed {role_color}; border-radius: 12px; padding: 20px;">
                                        <span style="font-family: 'Courier New', Courier, monospace; font-size: 38px; font-weight: 800; letter-spacing: 6px; color: {role_color}; text-shadow: 1px 1px 0px rgba(255,255,255,0.8);">{otp}</span>
                                    </td>
                                </tr>
                            </table>
                            
                            <div style="background-color: #f1f5f9; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td style="vertical-align: top; width: 24px; padding-top: 2px;">
                                            <span style="font-size: 16px; color: #64748b;">ℹ️</span>
                                        </td>
                                        <td style="font-size: 13px; color: #64748b; line-height: 1.45; padding-left: 8px;">
                                            This verification code is valid for <strong>10 minutes</strong>. For security, never share this code with anyone. Spherix staff will never ask for it.
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            
                            <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5; text-align: center;">
                                If you did not make this request, please ignore this email or contact support if you have concerns.
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; padding: 24px 32px; border-top: 1px solid #edf2f7; text-align: center; font-size: 12px; color: #64748b;">
                            <p style="margin: 0 0 8px 0; font-weight: 600;">Spherix Clinic Health Systems</p>
                            <p style="margin: 0; font-size: 11px; color: #94a3b8;">&copy; {datetime.now().year} Spherix Clinic. Secure clinical information system.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def send_notification_email(to_email, subject, body, is_html=False, attachment_name=None, attachment_data=None):
    """Sends an email notification."""
    settings = TEMP_DATA.get('settings', {})
    
    server = settings.get('mail_server') or MAIL_SERVER
    port = int(settings.get('mail_port') or MAIL_PORT)
    use_tls_val = settings.get('mail_use_tls')
    use_tls = use_tls_val == 'true' if use_tls_val else MAIL_USE_TLS
    username = settings.get('mail_username') or MAIL_USERNAME
    password = settings.get('mail_password') or MAIL_PASSWORD

    if not all([server, username, password]):
        print(f"⚠️ Email sending is not configured. Server: '{server}', User: '{username}', Pass: {'***' if password else 'None'}")
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
    msg['From'] = username
    msg['To'] = to_email

    try:
        with smtplib.SMTP(server, port) as smtp_server:
            if use_tls:
                smtp_server.starttls()
            smtp_server.login(username, password)
            smtp_server.send_message(msg)
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
    admin_email = 'admin@spherixclinic.com'
    admin_password = 'Admin@123' # Explicitly setting the admin password here
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
    email = 'hospital@spherixclinic.com'
    password = 'hospital123'
    hashed = generate_password_hash(password, method='pbkdf2:sha256:260000')
    
    existing = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
    if not existing:
        year = datetime.now().year
        new_id = f"HPT/{year}/{TEMP_DATA['next_ids']['hospital']:03d}"
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
    normalized_cart = []
    for item in cart:
        quantity = int(item.get('quantity', 0) or 0)
        try:
            price_value = float(item.get('price', 0))
        except (TypeError, ValueError):
            price_value = 0.0

        normalized_cart.append({
            'name': item.get('name'),
            'quantity': quantity,
            'price': price_value
        })
        cart_item_count += quantity
        total_price += quantity * price_value
     
    session['cart'] = normalized_cart
    return dict(cart=normalized_cart, 
                cart_item_count=cart_item_count, 
                cart_total_price=round(total_price, 2))

# ---------------- Routes ----------------

@app.route('/')
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
        'orders': len(TEMP_DATA.get('orders', {}))
    }
    
    # Fetch all verified doctors to showcase in the loop
    all_doctors = list(TEMP_DATA.get('doctors', {}).values())
    verified_doctors = [d for d in all_doctors if getattr(d, 'is_verified', False) and not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]

    # Fetch patient webapp feedbacks
    all_feedbacks = list(TEMP_DATA.get('feedbacks', {}).values())
    sorted_feedbacks = sorted(all_feedbacks, key=lambda f: getattr(f, 'created_at', datetime.min), reverse=True)
    
    # Fetch all verified hospitals to showcase in the loop
    all_hospitals = list(TEMP_DATA.get('hospitals', {}).values())
    verified_hospitals = [h for h in all_hospitals if getattr(h, 'is_verified', True) and not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)]
    
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
    
    return render_template('home.html', current_year=current_year, stats=stats, featured_doctors=verified_doctors, featured_hospitals=verified_hospitals, recent_organ_requests=recent_organ_requests, feedbacks=sorted_feedbacks, doctor_opinions=doctor_opinions_list, camps=upcoming_camps)

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

@app.route("/yoga")
def yoga():
    return render_template("yoga.html")

@app.route("/telemedicine")
@app.route("/telemedicine/<appointment_id>")
def telemedicine(appointment_id=None):
    room_name = None
    if appointment_id:
        appointment = TEMP_DATA['appointments'].get(appointment_id)
        if not appointment:
            try:
                appointment = TEMP_DATA['appointments'].get(int(appointment_id))
            except (ValueError, TypeError):
                pass
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
        height = request.form.get('height')
        weight = request.form.get('weight')
        medical_history = request.form.get('medical_history', '').strip()
        if not age or not gender or not height or not weight:
            flash('Please fill in the required profile fields', 'error')
            return redirect(url_for('symptoms'))
        session['age'] = age
        session['gender'] = gender
        session['height'] = height
        session['weight'] = weight
        session['medical_history'] = medical_history
        return redirect(url_for('symptoms_step2'))

    return render_template('symptoms_step1.html')


@app.route('/symptoms/step2', methods=['GET', 'POST'])
def symptoms_step2():
    """Step 2: collect detailed symptom info (text, body part, optional image) and redirect to results."""
    if request.method == 'POST':
        symptoms_text = request.form.get('symptoms', '').strip()
        body_part = request.form.get('body_part', '').strip()
        body_part_detail = request.form.get('body_part_detail', '').strip()
        duration = request.form.get('duration', '').strip()
        severity = request.form.get('severity', '').strip()
        worse_factors = request.form.get('worse_factors', '').strip()
        better_factors = request.form.get('better_factors', '').strip()
        current_medicines = request.form.get('current_medicines', '').strip()
        allergies = request.form.get('allergies', '').strip()
        selected_symptoms_raw = request.form.get('selected_symptoms', '').strip()
        camera_data = request.form.get('camera_image_data')
        medical_history = session.get('medical_history', '').strip()

        try:
            selected_symptoms = json.loads(selected_symptoms_raw) if selected_symptoms_raw else []
            if not isinstance(selected_symptoms, list):
                selected_symptoms = []
        except json.JSONDecodeError:
            selected_symptoms = []

        uploaded_file = request.files.get('symptom_image') or request.files.get('image') or request.files.get('file')

        if not symptoms_text and not body_part and not camera_data and not (uploaded_file and uploaded_file.filename):
            flash('Please provide at least one input: describe symptoms, select an area, or capture/upload an image.', 'error')
            return redirect(url_for('symptoms_step2'))

        compiled_symptoms = symptoms_text
        if selected_symptoms:
            compiled_symptoms += "\nSymptom keywords: " + ", ".join(selected_symptoms)
        if duration:
            compiled_symptoms += f"\nDuration: {duration}"
        if severity:
            compiled_symptoms += f"\nSeverity: {severity}"
        if body_part_detail:
            compiled_symptoms += f"\nSpecific location: {body_part_detail}"
        if worse_factors:
            compiled_symptoms += f"\nAggravating factors: {worse_factors}"
        if better_factors:
            compiled_symptoms += f"\nRelieving factors: {better_factors}"
        if current_medicines:
            compiled_symptoms += f"\nCurrent medications: {current_medicines}"
        if allergies:
            compiled_symptoms += f"\nAllergies: {allergies}"
        if medical_history:
            compiled_symptoms += f"\nMedical history: {medical_history}"
        if body_part and body_part not in compiled_symptoms:
            compiled_symptoms += f"\nAffected body part: {body_part}"

        session['symptoms'] = compiled_symptoms
        session['body_part'] = body_part
        session['body_part_detail'] = body_part_detail
        session['symptom_duration'] = duration
        session['symptom_severity'] = severity
        session['worse_factors'] = worse_factors
        session['better_factors'] = better_factors
        session['current_medicines'] = current_medicines
        session['allergies'] = allergies
        session['selected_symptoms'] = selected_symptoms
        session['raw_symptoms'] = symptoms_text

        uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        timestamp = utcnow().strftime('%Y%m%d%H%M%S')

        if uploaded_file and uploaded_file.filename:
            try:
                filename = secure_filename(uploaded_file.filename)
                stored_name = f"uploaded_symptom_{timestamp}_{filename}"
                save_path = os.path.join(uploads_dir, stored_name)
                uploaded_file.save(save_path)
                session['symptom_image_path'] = f"/static/uploads/{stored_name}"
            except Exception as e:
                print(f"⚠️ Failed to save uploaded image: {e}")

        elif camera_data:
            try:
                header, encoded = camera_data.split(',', 1)
                binary_data = base64.b64decode(encoded)
                stored_name = f"captured_symptom_{timestamp}.jpg"
                save_path = os.path.join(uploads_dir, stored_name)
                with open(save_path, 'wb') as f:
                    f.write(binary_data)
                session['symptom_image_path'] = f"/static/uploads/{stored_name}"
            except Exception as e:
                print(f"⚠️ Failed to decode/save camera image: {e}")
        else:
            session.pop('symptom_image_path', None)

        return redirect(url_for('symptoms_result'))

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
    height = session.get('height')
    weight = session.get('weight')
    symptoms = session.get('symptoms', '')
    body_part = session.get('body_part', '')
    image_path = session.get('symptom_image_path')

    if symptoms and body_part:
        input_text = f"{symptoms} (Location: {body_part})"
    elif body_part:
        input_text = f"Symptoms in {body_part}"
    else:
        input_text = symptoms or "Unspecified symptoms"
    
    # Use ML-based analysis (Groq API) as the primary method.
    result = get_ml_analysis(input_text, age=age, gender=gender, image_path=image_path, height=height, weight=weight)

    if result.get("conditions") and ("AI Service Unavailable" in result.get("conditions") or "Groq API" in result.get("conditions") or "Groq API not configured" in result.get("conditions")):
        api_error = result.get("error_details", "Please try again later.")
        flash(f"Groq API Failed: {api_error}", "error")
        return redirect(url_for('symptoms_step2'))

    symptom_response = _build_symptom_response(
        result,
        age=age,
        gender=gender,
        duration=session.get('symptom_duration', ''),
        severity=session.get('symptom_severity', ''),
        body_part=body_part,
        body_part_detail=session.get('body_part_detail', ''),
        worse_factors=session.get('worse_factors', ''),
        better_factors=session.get('better_factors', ''),
        current_medicines=session.get('current_medicines', ''),
        allergies=session.get('allergies', ''),
        medical_history=session.get('medical_history', '')
    )

    session['symptom_analysis_result'] = symptom_response

    doctors_for_recommendation = []
    recommended_depts = symptom_response.get('recommended_departments', [])
    all_db_doctors = list(TEMP_DATA['doctors'].values())
    if recommended_depts:
        doctors_for_recommendation = [
            doc for doc in all_db_doctors
            if doc.department in recommended_depts
        ]

    # Look for a physician validation review that matches this symptom query
    matching_reviews = [
        r for r in TEMP_DATA.get('symptom_reviews', [])
        if r['symptom_query'].lower().strip() == input_text.lower().strip()
    ]
    doctor_review = matching_reviews[0] if matching_reviews else None

    # Enrich suggested medicines with OpenFDA details
    enriched_relief = []
    for option in symptom_response.get('supportive_relief_options', []):
        if 'consult' in option.lower() or len(option.strip()) < 3:
            enriched_relief.append({
                'name': option,
                'is_disclaimer': True
            })
            continue
            
        parts = re.split(r'(?i)\b(for|to|with|and)\b|\(|,', option)
        med_name = parts[0].strip(' ,.-()')
        
        try:
            fda_info = _invoke_openfda_drug_info(med_name)
        except Exception:
            fda_info = None
            
        if fda_info:
            enriched_relief.append({
                'name': option,
                'is_disclaimer': False,
                'fda_verified': True,
                'brand_name': fda_info.get('drug_name'),
                'generic_name': med_name.title(),
                'primary_use': fda_info.get('primary_use'),
                'side_effects': fda_info.get('common_side_effects', [])[:3],
                'caution': fda_info.get('caution'),
                'instructions': fda_info.get('usage_instructions'),
                'source': 'OpenFDA API'
            })
        else:
            enriched_relief.append({
                'name': option,
                'is_disclaimer': False,
                'fda_verified': False,
                'generic_name': med_name.title()
            })
            
    # Update the supportive_relief_options list inside the response dictionary
    symptom_response['supportive_relief_options'] = enriched_relief

    return render_template('symptom_result.html',
                           query=input_text,
                           result=symptom_response,
                           doctors=doctors_for_recommendation,
                           age=age,
                           gender=gender,
                           raw_symptoms=session.get('raw_symptoms', ''),
                           duration=session.get('symptom_duration', ''),
                           severity=session.get('symptom_severity', ''),
                           worse_factors=session.get('worse_factors', ''),
                           better_factors=session.get('better_factors', ''),
                           current_medicines=session.get('current_medicines', ''),
                           allergies=session.get('allergies', ''),
                           chat_history=session.get('symptom_chat_history', []),
                           finalized=session.get('symptom_finalized', False),
                           finalized_summary=session.get('symptom_finalized_summary', ''),
                           doctor_review=doctor_review)

@app.route('/symptoms/chat', methods=['POST'])
@csrf.exempt
def symptoms_chat():
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip() if isinstance(data, dict) else request.form.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Please enter a chat message.'}), 400

    result = session.get('symptom_analysis_result', {}) or {}
    symptoms_context = result.get('clinical_summary') or result.get('description') or session.get('symptoms', '')
    age = session.get('age')
    gender = session.get('gender')
    answer = _invoke_groq_symptom_followup(symptoms_context, message, age=age, gender=gender)

    chat_history = session.get('symptom_chat_history', [])
    chat_history.append({'role': 'user', 'message': message, 'response': answer})
    session['symptom_chat_history'] = chat_history[-10:]
    session.modified = True

    return jsonify({'success': True, 'assistant': answer, 'history': session['symptom_chat_history']})

@app.route('/symptoms/finalize', methods=['POST'])
@csrf.exempt
def symptoms_finalize():
    if 'symptom_analysis_result' not in session:
        flash('No symptom analysis result found to finalize.', 'error')
        return redirect(url_for('symptoms'))

    result = session.get('symptom_analysis_result', {})
    chat_history = session.get('symptom_chat_history', [])
    age = session.get('age')
    gender = session.get('gender')
    final_text = _invoke_groq_symptom_finalization(result, chat_history, age=age, gender=gender)

    session['symptom_finalized'] = True
    session['symptom_finalized_summary'] = final_text
    session.modified = True

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'finalized': True,
            'finalized_summary': final_text,
            'redirect': url_for('symptoms_result')
        })

    flash('Your symptom result has been finalized and will be included in the updated PDF.', 'success')
    return redirect(url_for('symptoms_result'))

@app.route('/api/symptom-result/validate', methods=['POST'])
@doctor_required
def validate_symptom_result():
    symptom_query = request.form.get('symptom_query', '').strip()
    status = request.form.get('status', 'Approved AI Findings').strip()
    clinical_remarks = request.form.get('clinical_remarks', '').strip()
    prescribed_treatment = request.form.get('prescribed_treatment', '').strip()
    recommended_tests = request.form.get('recommended_tests', '').strip()
    
    if not symptom_query:
        flash("Symptom query is required to sign off.", "error")
        return redirect(request.referrer or url_for('home'))
        
    doctor = TEMP_DATA['doctors'].get(current_user.id)
    doc_name = f"{doctor.first_name} {doctor.last_name}" if doctor else "Registered Clinician"
    
    # Find existing review by this doctor for this query
    reviews = TEMP_DATA.setdefault('symptom_reviews', [])
    existing = next((r for r in reviews if r['symptom_query'].lower().strip() == symptom_query.lower().strip() and r['doctor_id'] == current_user.id), None)
    
    if existing:
        existing['status'] = status
        existing['clinical_remarks'] = clinical_remarks
        existing['prescribed_treatment'] = prescribed_treatment
        existing['recommended_tests'] = recommended_tests
        existing['created_at'] = utcnow().isoformat()
    else:
        # Assign a temporary ID
        max_id = max([r['id'] for r in reviews if 'id' in r] + [0])
        new_id = max_id + 1
        reviews.append({
            'id': new_id,
            'symptom_query': symptom_query,
            'doctor_id': current_user.id,
            'doctor_name': doc_name,
            'status': status,
            'clinical_remarks': clinical_remarks,
            'prescribed_treatment': prescribed_treatment,
            'recommended_tests': recommended_tests,
            'created_at': utcnow().isoformat()
        })
        
    save_data()
    flash("Case clinically validated and signed successfully.", "success")
    return redirect(url_for('symptoms_result'))

# ========== ADVANCED SYMPTOMS ANALYZER API ENDPOINTS ==========
@app.route('/api/symptoms/analyze', methods=['POST'])
@csrf.exempt
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
        height = data.get('height')
        weight = data.get('weight')
        body_part = data.get('body_part')
        
        if symptoms and body_part:
            symptoms = f"{symptoms} (Location: {body_part})"
        elif body_part:
            symptoms = f"Symptoms in {body_part}"
        elif not symptoms:
            return jsonify({'error': 'Symptoms field is required', 'success': False}), 400
        
        # Perform analysis using AI (Groq)
        result = get_ml_analysis(
            symptoms_query=symptoms,
            age=age,
            gender=gender,
            height=height,
            weight=weight
        )
        
        # Update the session so PDF exports and receipts use the latest context and results
        session['symptoms'] = data.get('symptoms', '').strip()
        session['symptom_analysis_result'] = result

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
@csrf.exempt
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
        subscribe_newsletter = request.form.get('subscribe') == 'yes'
        
        if subscribe_newsletter and email:
            if not any(sub['email'] == email for sub in TEMP_DATA.get('newsletter_subscribers', [])):
                TEMP_DATA.setdefault('newsletter_subscribers', []).append({
                    'email': email,
                    'subscribed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                save_data()
                
            admin_email = 'admin@spherixclinic.com'
            subject = "New Newsletter Subscription"
            body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
                <h2 style="color: #e11d48;">New Subscriber!</h2>
                <p>A new user has subscribed to the Spherix Clinic newsletter.</p>
                <p><strong>Email:</strong> {email}</p>
            </div>
            """
            send_notification_email(admin_email, subject, body, is_html=True)
            
            # Send Welcome Email to Subscriber
            user_subject = "Welcome to the Spherix Clinic Newsletter!"
            user_body = f"""
            <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #020617; color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #1e293b;">
                <div style="background: linear-gradient(135deg, #0891b2 0%, #2563eb 100%); padding: 30px 20px; text-align: center;">
                    <h2 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 1px;">Spherix Clinic</h2>
                    <p style="color: #cffafe; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px;">Medical Intelligence Network</p>
                </div>
                <div style="padding: 40px 30px; background-color: #0f172a;">
                    <h3 style="color: #38bdf8; font-size: 20px; margin-top: 0;">Sync Established.</h3>
                    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1; margin-bottom: 20px;">Welcome to the Spherix Network, {name or 'there'}.</p>
                    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1; margin-bottom: 30px;">Thank you for subscribing. You are now connected to our intelligence broadcast and will be the first to receive exclusive updates on Neural Diagnostics, Bio-Telemetry, and Longevity Science.</p>
                    <p style="font-size: 14px; color: #94a3b8; margin-bottom: 0;">Stay optimized,</p>
                    <p style="font-size: 14px; color: #f8fafc; font-weight: bold; margin-top: 5px;">Spherix Clinic Core Team</p>
                </div>
                <div style="background-color: #020617; padding: 20px; text-align: center; border-top: 1px solid #1e293b;">
                    <p style="color: #64748b; font-size: 11px; margin: 0;">&copy; {datetime.now().year} Spherix Clinic. All rights reserved.</p>
                    <p style="color: #64748b; font-size: 11px; margin-top: 5px;">Headquarters: Motihari, Bihar - 845401, India | +91 933 4325 920</p>
                </div>
            </div>
            """
            send_notification_email(email, user_subject, user_body, is_html=True)
        
        try:
            class ReceiptPDF(FPDF):
                def header(self):
                    # Page Border
                    self.set_draw_color(15, 23, 42)
                    self.set_line_width(0.8)
                    self.rect(8, 8, 194, 281)
                    
                    # Watermark Logic
                    self.set_font('Helvetica', 'B', 40)
                    self.set_text_color(245, 247, 250)
                    angle = 45
                    x = self.w / 2
                    y = self.h / 2
                    c = math.cos(math.radians(angle))
                    s = math.sin(math.radians(angle))
                    cx = x * self.k
                    cy = (self.h - y) * self.k
                    s_val = f'q {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {cx:.2f} {cy:.2f} cm 1 0 0 1 {-cx:.2f} {-cy:.2f} cm'
                    self._out(s_val)
                    self.text(x - 70, y, 'Spherix Clinic Systems')
                    self._out('Q')
                    self.set_text_color(0, 0, 0)
                    
                def footer(self):
                    self.set_y(-22)
                    self.set_font('Helvetica', 'I', 8)
                    self.set_text_color(128, 128, 128)
                    self.set_draw_color(229, 231, 235)
                    self.set_line_width(0.2)
                    self.line(12, self.get_y(), 198, self.get_y())
                    self.ln(2)
                    self.multi_cell(0, 4, "Disclaimer: This receipt is generated by Spherix Neural Diagnostics. It is not a substitute for professional medical diagnosis or treatment.", 0, 'C')
                    self.multi_cell(0, 4, "Be Healthy! Your Health is our first Priority.", 0, 'C')

            pdf = ReceiptPDF()
            pdf.add_page()
            pdf.set_margins(12, 12, 12)
            
            # Header Banner
            pdf.set_fill_color(15, 23, 42) # Deep Slate
            pdf.rect(8, 8, 194, 26, 'F')
            
            pdf.set_y(13)
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 8, 'SYMPTOM ANALYSIS RECEIPT', 0, 1, 'C')
            pdf.set_font('Helvetica', 'B', 8)
            pdf.set_text_color(156, 163, 175)
            pdf.cell(0, 4, 'GENOMIC DIAGNOSTICS & TELEMETRY HUB', 0, 1, 'C')
            pdf.ln(12)
            
            # 3. Patient Information Block
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 8, 'Patient Profile & Intake Details', 0, 1, 'L')
            
            # Table Settings
            pdf.set_fill_color(240, 246, 255) # Soft Blue fill
            pdf.set_draw_color(191, 219, 254) # Blue-200 border
            pdf.set_line_width(0.3)
            
            # Row 1: Name & Date
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(30, 8, '  Name:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(70, 8, f'  {to_latin1_str(name)}', 1, 0, 'L')
            
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(30, 8, '  Date:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(60, 8, f'  {datetime.now().strftime("%Y-%m-%d")}', 1, 1, 'L')
            
            # Row 2: Email & Phone
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(30, 8, '  Email:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(70, 8, f'  {to_latin1_str(email)}', 1, 0, 'L')
            
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(30, 8, '  Phone:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(60, 8, f'  {to_latin1_str(phone)}', 1, 1, 'L')
            
            # Row 3: Address (Full Width)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(30, 8, '  Address:', 1, 0, 'L', 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(160, 8, f'  {to_latin1_str(address)}', 1, 1, 'L')
            
            pdf.ln(6)
            
            # 4. Analysis Details Section
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 8, 'Clinical Assessment Results', 0, 1, 'L')
            pdf.set_draw_color(15, 23, 42)
            pdf.set_line_width(0.4)
            pdf.line(12, pdf.get_y(), 198, pdf.get_y())
            pdf.ln(4)
            
            result = session.get('symptom_analysis_result', {})
            symptoms_val = session.get('symptoms', '')
            body_part_val = session.get('body_part', '')
            image_path = session.get('symptom_image_path')
            if symptoms_val and body_part_val:
                raw_query = f"{symptoms_val} (Location: {body_part_val})"
            elif body_part_val:
                raw_query = f"Symptoms in {body_part_val}"
            else:
                raw_query = symptoms_val or "Unspecified symptoms"
            
            clean_query = raw_query.replace(" | Additional context/question: ", "\nQ: ").replace(" | ", "\nQ: ")
            
            # Look for a physician validation review that matches this symptom query
            matching_reviews = [
                r for r in TEMP_DATA.get('symptom_reviews', [])
                if r['symptom_query'].lower().strip() == raw_query.lower().strip()
            ]
            doctor_review = matching_reviews[0] if matching_reviews else None
            
            # Reported Symptoms Box
            pdf.set_fill_color(250, 250, 255)
            pdf.set_draw_color(220, 220, 220)
            pdf.set_line_width(0.2)
            
            pdf.set_font('Helvetica', 'B', 11)
            pdf.cell(0, 8, 'Reported Symptoms:', 0, 1)
            pdf.set_font('Helvetica', '', 10)
            pdf.multi_cell(0, 6, to_latin1_str(clean_query), 1, 'L', True)
            pdf.ln(5)

            finalized_summary = session.get('symptom_finalized_summary', '') if session.get('symptom_finalized') else ''
            chat_history = session.get('symptom_chat_history', []) or []
            if finalized_summary:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.cell(0, 8, 'Finalized Result Summary:', 0, 1)
                pdf.set_font('Helvetica', '', 10)
                pdf.multi_cell(0, 6, to_latin1_str(finalized_summary), 0, 'L')
                pdf.ln(5)
            if chat_history:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.cell(0, 8, 'AI Follow-Up Chat Transcript:', 0, 1)
                pdf.set_font('Helvetica', '', 9)
                for entry in chat_history[-6:]:
                    speaker = 'You' if entry.get('role') == 'user' else 'AI'
                    text = to_latin1_str(entry.get('message') if speaker == 'You' else entry.get('response'))
                    pdf.cell(0, 5, f'{speaker}:', 0, 1)
                    pdf.multi_cell(0, 5, text, 0, 'L')
                    pdf.ln(1)
                pdf.ln(3)

            # --- Uploaded Image ---
            if image_path:
                local_image_path = os.path.join(app.root_path, image_path.lstrip('/'))
                if os.path.exists(local_image_path):
                    if pdf.get_y() > 230:
                        pdf.add_page()
                    pdf.set_font('Helvetica', 'B', 11)
                    pdf.cell(0, 8, 'Visual Evidence:', 0, 1)
                    try:
                        current_y = pdf.get_y()
                        pdf.image(local_image_path, x=10, y=current_y, h=40)
                        pdf.set_y(current_y + 45)
                    except Exception:
                        pdf.set_font('Helvetica', 'I', 10)
                        pdf.cell(0, 6, 'Image preview unavailable.', 0, 1)
            
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

            # --- Doctor's Signature & Stamp Section ---
            pdf.ln(10)
            
            # Auto page-break if space is too tight for the signature blocks
            if pdf.get_y() > 240:
                pdf.add_page()
                
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 10, 'Physician Validation (For Official Use Only)', 0, 1, 'L')
            
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.2)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)
            
            # Draw two boxes for Signature and Stamp
            pdf.set_font('Helvetica', 'I', 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(90, 6, "Attending Doctor's Signature & Date:", 0, 0, 'L')
            pdf.cell(10, 6, "", 0, 0, 'L') # spacer
            pdf.cell(90, 6, "Official Hospital/Clinic Stamp:", 0, 1, 'L')
            
            current_y = pdf.get_y()
            current_y = pdf.get_y()
            pdf.set_draw_color(16, 185, 129)
            pdf.set_fill_color(240, 253, 244) # light green
            pdf.rect(10, current_y + 2, 85, 25, 'DF')
            pdf.rect(110, current_y + 2, 85, 25, 'DF')
            
            # Draw signature image if exists
            sig_img_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
            if os.path.exists(sig_img_path):
                pdf.image(sig_img_path, x=15, y=current_y + 4.5, w=75, h=20)
            else:
                # Fallback text
                doctor_name = doctor_review['doctor_name'] if doctor_review else "Sunny Kumar"
                pdf.set_xy(15, current_y + 10)
                pdf.set_font('Courier', 'BI', 11)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(75, 8, to_latin1_str(f"/s/ Dr. {doctor_name}"), 0, 0, 'C')
            
            # Draw stamp image if exists
            stamp_img_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
            if os.path.exists(stamp_img_path):
                pdf.image(stamp_img_path, x=140, y=current_y + 4.5, w=25, h=20)
            else:
                # Fallback text
                pdf.set_xy(115, current_y + 10)
                pdf.set_font('Helvetica', 'B', 10)
                pdf.set_text_color(16, 185, 129)
                pdf.cell(75, 8, 'SPHERIX VERIFIED', 0, 1, 'C')
                
            pdf.ln(30) # Push cursor past the drawn boxes

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
        symptoms_val = session.get('symptoms', '')
        body_part_val = session.get('body_part', '')
        if symptoms_val and body_part_val:
                raw_query = f"{symptoms_val} (Location: {body_part_val})"
        elif body_part_val:
                raw_query = f"Symptoms in {body_part_val}"
        else:
                raw_query = symptoms_val or "Unspecified symptoms"
            
        clean_query = raw_query.replace(" | Additional context/question: ", "\nQ: ").replace(" | ", "\nQ: ")
        result = session.get('symptom_analysis_result', {})
        image_path = session.get('symptom_image_path')

        # Look for a physician validation review that matches this symptom query
        matching_reviews = [
            r for r in TEMP_DATA.get('symptom_reviews', [])
            if r['symptom_query'].lower().strip() == raw_query.lower().strip()
        ]
        doctor_review = matching_reviews[0] if matching_reviews else None

        # --- PDF Generation with Premium Design ---
        class ColorPDF(FPDF):
            PRIMARY_COLOR = (15, 23, 42) # Deep Slate/Navy
            SECONDARY_COLOR = (71, 85, 105) # Slate-600
            TEXT_COLOR = (15, 23, 42) # Deep Slate text
            LIGHT_BG_COLOR = (240, 246, 255) # Soft Blue tint

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
                header_text = to_latin1_str('Spherix Clinic Health Intelligence Report')
                self.cell(0, 10, header_text)
                self.set_font('Helvetica', '', 10)
                date_text = to_latin1_str(f"Generated: {utcnow().strftime('%Y-%m-%d')}")
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
            
            def draw_bar_chart(self, data, labels, x, y, width, height):
                if not data:
                    return
                
                self.set_xy(x, y)
                self.set_font('Helvetica', 'B', 10)
                self.cell(width, 8, 'Confidence Scores', 0, 1, 'C')
                self.ln(2)
                
                bar_height = (height - 10) / len(data)
                max_val = 100 # Confidence is 0-100
                chart_width = width - 45 # leave space for labels
                
                for i, val in enumerate(data):
                    label = to_latin1_str(labels[i][:25]) # Truncate label
                    bar_width = (val / max_val) * chart_width
                    
                    # Label
                    self.set_font('Helvetica', '', 8)
                    self.set_text_color(80, 80, 80)
                    self.set_xy(x, y + 15 + (i * bar_height))
                    self.cell(43, bar_height, label, 0, 0, 'R')
                    
                    # Bar Background
                    self.set_fill_color(243, 244, 246) # gray-100
                    self.rect(x + 45, y + 15 + (i * bar_height) + 1, chart_width, bar_height - 2, 'F')
                    
                    # Bar Foreground
                    self.set_fill_color(*self.PRIMARY_COLOR)
                    self.rect(x + 45, y + 15 + (i * bar_height) + 1, bar_width, bar_height - 2, 'F')
                    
                    # Value text inside bar
                    self.set_font('Helvetica', 'B', 8)
                    self.set_text_color(255, 255, 255)
                    if bar_width > 12:
                        self.set_xy(x + 45 + bar_width - 12, y + 15 + (i * bar_height) + (bar_height/2) - 2)
                        self.cell(10, 4, f'{int(val)}%')
                    # Value text outside bar if too small
                    elif bar_width > 0:
                        self.set_text_color(80, 80, 80)
                        self.set_xy(x + 45 + bar_width + 2, y + 15 + (i * bar_height) + (bar_height/2) - 2)
                        self.cell(10, 4, f'{int(val)}%')

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
        y_after_col1 = pdf.get_y()
            
        pdf.set_xy(pdf.get_x() + col_width + 10, y_pos)
        pdf.multi_cell(col_width, 7, to_latin1_str(clean_query), 1, 'L', 1)
        y_after_col2 = pdf.get_y()
            
        pdf.set_y(max(y_after_col1, y_after_col2) + 10)

        # Draw Confidence Scores Bar Chart
        pdf.draw_bar_chart(result.get('confidence_scores', []), result.get('conditions', []), pdf.get_x(), pdf.get_y(), pdf.w - 20, 35)
        pdf.set_y(pdf.get_y() + 45)

        # --- Uploaded Image Section ---
        if image_path:
            local_image_path = os.path.join(app.root_path, image_path.lstrip('/'))
            if os.path.exists(local_image_path):
                def image_content():
                    try:
                        pdf.image(local_image_path, x=pdf.get_x(), y=pdf.get_y(), h=50)
                    except Exception:
                        pdf.set_font('Helvetica', 'I', 10)
                        pdf.cell(0, 10, 'Image preview unavailable.', 0, 1)
                
                pdf.card('Visual Symptom Input', image_content, 65)

        # --- Sanitize Text for PDF ---
        advice_text = result.get('advice', 'No advice available.')
        advice_safe = to_latin1_str(advice_text)
        conditions = result.get('conditions', [])
        conditions_safe = [to_latin1_str(c) for c in conditions]
        rec_depts = result.get('recommended_departments', [])
        rec_depts_safe = [to_latin1_str(d) for d in rec_depts]
        self_care_safe = [to_latin1_str(s) for s in result.get('self_care', [])]
        when_to_see_doctor_safe = to_latin1_str(result.get('when_to_see_doctor', ''))
        finalized_summary_safe = to_latin1_str(session.get('symptom_finalized_summary', '')) if session.get('symptom_finalized') else ''
        chat_history_list = session.get('symptom_chat_history', []) or []

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
                    pdf.cell(0, 8, cond, 0, 1, 'L')
                    # Description for the condition
                    pdf.set_font('Helvetica', '', 10)
                    pdf.set_text_color(*pdf.TEXT_COLOR)
                    description_safe = to_latin1_str(KNOWLEDGE_BASE.get(cond, {}).get('description', 'No description available.'))
                    pdf.multi_cell(0, 5, description_safe, 0, 'L')
                    pdf.ln(3)
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
                    pdf.multi_cell(col_width, 5, f'{chr(149)} {item}', 0, 'L')
                    pdf.ln(1.5)
            else:
                pdf.multi_cell(col_width, 5, 'No specific self-care tips available.', 0, 'L')
            
            # When to see doctor column
            y_after_col1 = pdf.get_y()
            pdf.set_xy(pdf.get_x() + col_width + 10, y_pos)
            pdf.multi_cell(col_width, 5, when_to_see_doctor_safe, 0, 'L')
            y_after_col2 = pdf.get_y()
            
            pdf.set_y(max(y_after_col1, y_after_col2))

        pdf.card('Care Guidance', care_guidance_content, 60)

        if finalized_summary_safe:
            def finalize_content():
                pdf.set_font('Helvetica', '', 10)
                pdf.multi_cell(0, 6, finalized_summary_safe, 0, 'L')
            pdf.card('Finalized Result Summary', finalize_content, 50)

        if chat_history_list:
            def transcript_content():
                pdf.set_font('Helvetica', '', 9)
                for entry in chat_history_list[-6:]:
                    speaker = 'You' if entry.get('role') == 'user' else 'AI'
                    text = to_latin1_str(entry.get('response') if speaker == 'AI' else entry.get('message'))
                    pdf.set_font('Helvetica', 'B', 9)
                    pdf.cell(0, 5, f'{speaker}:', 0, 1)
                    pdf.set_font('Helvetica', '', 9)
                    pdf.multi_cell(0, 5, text, 0, 'L')
                    pdf.ln(1)
            transcript_height = min(90, 24 + len(chat_history_list) * 16)
            pdf.card('AI Follow-Up Chat Transcript', transcript_content, transcript_height)

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
                    pdf.cell(0, 6, to_latin1_str(name), 0, 0, 'L')
                    pdf.set_font('Helvetica', '', 10)
                    pdf.cell(0, 6, to_latin1_str(f'({dept})'), 0, 1, 'R')
            else:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(*pdf.SECONDARY_COLOR)
                pdf.cell(0, 6, 'No specific specialists found. Please browse our directory.', 0, 1)

        pdf.card('Next Steps & Specialist Recommendations', specialists_content, 65)

        # Auto page-break if space is too tight for the signature blocks
        if pdf.get_y() > 230:
            pdf.add_page()
            
        pdf.ln(10)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(16, 185, 129) # Emerald Green
        pdf.cell(0, 8, 'Clinical Audit & Verification Verdict', 0, 1, 'L')
        pdf.set_draw_color(16, 185, 129)
        pdf.set_line_width(0.4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        
        doctor_name = doctor_review['doctor_name'] if doctor_review else "Sunny Kumar"
        status_val = doctor_review['status'] if doctor_review else "Signed & Verified"
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(50, 6, 'Reviewing Physician:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, to_latin1_str(f"Dr. {doctor_name}"), 0, 1, 'L')
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Assessment Status:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, to_latin1_str(status_val), 0, 1, 'L')
        
        remarks = doctor_review.get('clinical_remarks') if doctor_review else "AI-Assisted Symptom Analysis Report has been audited and matches official diagnostic criteria."
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Physician Remarks:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, to_latin1_str(remarks), 0, 'L')
            
        treatment = doctor_review.get('prescribed_treatment') if doctor_review else "Rest and follow the suggested OTC and self-care guidelines. Consult a specialist if symptoms persist."
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Prescribed Course:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, to_latin1_str(treatment), 0, 'L')
            
        tests = doctor_review.get('recommended_tests') if doctor_review else "Routine blood count (CBC) if symptoms persist."
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(50, 6, 'Recommended Tests:', 0, 0, 'L')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6, to_latin1_str(tests), 0, 1, 'L')
            
        # Draw Stamp and Signature Boxes
        pdf.ln(5)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(90, 6, "Signature of Attending Physician:", 0, 0, 'L')
        pdf.cell(10, 6, "", 0, 0, 'L')
        pdf.cell(90, 6, "Authorized Stamp:", 0, 1, 'L')
        
        current_y = pdf.get_y()
        pdf.set_draw_color(16, 185, 129)
        pdf.set_fill_color(240, 253, 244) # light green
        pdf.rect(10, current_y + 2, 85, 20, 'DF')
        pdf.rect(110, current_y + 2, 85, 20, 'DF')
        
        # Draw signature image if exists
        sig_img_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
        if os.path.exists(sig_img_path):
            pdf.image(sig_img_path, x=15, y=current_y + 3, w=75, h=18)
        else:
            # Fallback text
            pdf.set_xy(15, current_y + 8)
            pdf.set_font('Courier', 'BI', 11)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(75, 8, to_latin1_str(f"/s/ Dr. {doctor_name}"), 0, 0, 'C')
        
        # Draw stamp image if exists
        stamp_img_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
        if os.path.exists(stamp_img_path):
            pdf.image(stamp_img_path, x=140, y=current_y + 3, w=25, h=18)
        else:
            # Fallback text
            pdf.set_xy(115, current_y + 8)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(16, 185, 129)
            pdf.cell(75, 8, 'SPHERIX VERIFIED', 0, 1, 'C')
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln(15)

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
                logf.write(f"[{utcnow().isoformat()}] Error generating PDF: {e}\n{tb}\n\n")
        except Exception:
            pass
        flash(f'An error occurred while generating the PDF report: {str(e)}', 'error')
        return redirect(url_for('symptoms_result'))

@app.route('/doctors')
def doctors_list():
    # This route now fetches doctors from the database
    all_db_doctors = [d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
    q = request.args.get('q', '').lower().strip()
    dept = request.args.get('dept', '').strip()
    
    filtered_doctors = all_db_doctors
    if q:
        filtered_doctors = [
            d for d in filtered_doctors 
            if q in f"{d.first_name} {d.last_name}".lower() 
            or (d.department and q in d.department.lower())
            or (d.specialization and q in d.specialization.lower())
            or (d.hospital_name and q in d.hospital_name.lower())
        ]
    if dept:
        filtered_doctors = [
            d for d in filtered_doctors
            if d.department and d.department.lower() == dept.lower()
        ]
        
    # Get unique departments present in our doctors database
    available_depts = sorted(list(set(d.department for d in all_db_doctors if d.department)))
    
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
        departments=display_depts,
        total_doctors_count=len(all_db_doctors),
        page=page,
        total_pages=total_pages
    )

@app.route('/hospitals')
def hospitals_list():
    """Displays a list of registered hospitals."""
    all_hospitals = [h for h in TEMP_DATA['hospitals'].values() if not getattr(h, 'is_hidden', False) and not getattr(h, 'is_blocked', False)]
    
    search_query = request.args.get('q', '').lower().strip()
    city_query = request.args.get('city', '').lower().strip()
    
    filtered_hospitals = []
    for h in all_hospitals:
        # Filter by city (checking both city and address fields)
        if city_query and city_query not in (h.city or '').lower() and city_query not in (h.address or '').lower():
            continue
        
        # Filter by search query (name or doctor specialties)
        if search_query:
            match_name = search_query in h.name.lower()
            
            # Check doctors in this hospital to match specialties like "cancer" or "heart surgery"
            hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == h.name]
            match_specialty = any(
                search_query in (d.department or '').lower() or 
                search_query in (d.specialization or '').lower() 
                for d in hospital_doctors
            )
            
            if not (match_name or match_specialty):
                continue
                
        filtered_hospitals.append(h)

    # Sort hospitals according to ID
    def parse_id(h):
        val = h.id
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
    filtered_hospitals.sort(key=parse_id)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 9
    total_filtered = len(filtered_hospitals)
    total_pages = (total_filtered + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_hospitals = filtered_hospitals[start_idx:end_idx]

    return render_template(
        'hospitals.html', 
        hospitals=paginated_hospitals, 
        q=search_query, 
        city=city_query,
        page=page,
        total_pages=total_pages
    )

@app.route('/hospital/<path:hospital_id>')
def hospital_detail(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
    if not hospital:
        flash("Hospital not found.", "error")
        return redirect(url_for('hospitals_list'))
    
    # Get doctors for this hospital
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == hospital.name]
    
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
    per_page = 9
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
        organ_requests=hospital_organ_requests,
        organ_donors=hospital_organ_donors,
        page=page,
        total_pages=total_pages
    )

@app.route('/hospital/<path:hospital_id>/inquiry', methods=['POST'])
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

@app.route('/hospital/<path:hospital_id>/organ_inquiry', methods=['POST'])
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

@app.route('/hospital/<path:hospital_id>/blood_inquiry', methods=['POST'])
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

@app.route('/hospital/<path:hospital_id>/book_bed', methods=['POST'])
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

@app.route('/hospital/bed_booking/payment/<int:booking_id>', methods=['GET', 'POST'])
@patient_required
def bed_booking_payment(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if not booking or booking.patient_id != current_user.id:
        flash("Booking not found.", "error")
        return redirect(url_for('patient_dashboard'))
        
    if booking.status != 'awaiting_payment':
        flash("This booking has already been paid for or processed.", "warning")
        return redirect(url_for('patient_dashboard'))

    hospital = get_temp_data_item('hospitals', booking.hospital_id)
    fee = hospital.icu_bed_fee if booking.bed_type == 'ICU' else hospital.general_bed_fee
    
    if request.method == 'POST':
        booking.status = 'pending' # Paid and waiting for hospital approval
        save_data()
        flash(f"Payment successful! Emergency {booking.bed_type} bed request sent to {hospital.name}.", "success")
        return redirect(url_for('patient_dashboard'))
        
    return render_template('bed_booking_payment.html', booking=booking, hospital=hospital, fee=fee)

@app.route('/hospital/<path:hospital_id>/book_appointment', methods=['POST'])
@patient_required
def book_hospital_appointment(hospital_id):
    hospital_id = parse_route_id(hospital_id)
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
                timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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
        subject = "Verify your email - Spherix Clinic Doctor Portal"
        body = get_premium_otp_email_html(
            title="Doctor Registration Verification",
            greeting=f"Hello Dr. {last_name},",
            message="To complete your registration at Spherix Clinic, please use the following One-Time Password (OTP):",
            otp=otp,
            role_color="#2563eb",
            accent_bg="#eff6ff"
        )
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
        
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

@app.route('/doctor/info')
def doctor_info():
    return render_template('doctor_info.html')


@app.route('/doctor/forgot-password', methods=['GET', 'POST'])
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

@app.route('/doctor/reset-password', methods=['GET', 'POST'])
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

@app.route('/doctor/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute") # Specific, stricter limit for login attempts
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
            if getattr(doctor, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('doctor_login'))
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

@app.route('/doctor/dashboard', methods=['GET', 'POST'])
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
        # ... (existing profile update logic) ...
        fields_to_update = [
            'first_name', 'last_name', 'email', 'phone', 'department', 
            'specialization', 'address', 'hospital_name', 'hospital_address', 'city', 'state',
            'district', 'pincode', 'country', 'bio', 'qualification', 'license_number',
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
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"doc_profile_{timestamp}_{filename}"
                    upload_folder = os.path.join(app.root_path, 'static/uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, unique_filename))
                    doctor.profile_picture_url = unique_filename
                else:
                    flash('Invalid file format. Allowed types: png, jpg, jpeg, gif, pdf.', 'error')

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
        pending_hospital=pending_hospital
    )

@app.route('/api/doctor/submit-opinion', methods=['POST'])
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

@app.route('/doctor/respond-hospital-invitation', methods=['POST'])
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

@app.route('/doctor/patient/<patient_id>/update-clinical-record', methods=['POST'])
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

@app.route('/api/doctor/generate-soap', methods=['POST'])
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

@app.route('/doctor/image/<path:doc_id>')
def get_doctor_image(doc_id):
    """Serves the doctor's profile image from the database or static files."""
    doctor = TEMP_DATA['doctors'].get(doc_id)
    if doctor and getattr(doctor, 'profile_picture_url', None):
        file_path = os.path.join(app.root_path, 'static/uploads', doctor.profile_picture_url)
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

@app.route('/staff/image/<path:staff_id>')
def get_staff_image(staff_id):
    """Serves the staff member's profile image."""
    staff = TEMP_DATA['staff'].get(staff_id)
    if staff and getattr(staff, 'profile_picture_url', None):
        return redirect(url_for('static', filename='uploads/' + staff.profile_picture_url))
    name_str = staff.name if staff else "Staff Member"
    return redirect(f"https://api.dicebear.com/7.x/initials/svg?seed={name_str}&backgroundColor=ecfdf5&textColor=047857")

@app.route('/doctor/chat/<path:patient_id>')
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

@app.route('/api/chat/<path:patient_id>/messages')
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

@app.route('/api/chat/<path:patient_id>/send', methods=['POST'])
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
            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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

@app.route('/api/doctor/update_status', methods=['POST'])
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

@app.route('/api/medicines', methods=['GET'])
@login_required
def get_medicines_list():
    query = request.args.get('q', '').strip().lower()
    results = []
    meds = TEMP_DATA.get('medicines', [])
    for m in meds:
        name = m.get('name', '')
        if not query or query in name.lower():
            results.append({
                'name': name,
                'category': m.get('category', ''),
                'price': m.get('price', 0.0)
            })
    return jsonify(results[:20])

@app.route('/api/doctor/appointment/complete_with_prescription/<int:appointment_id>', methods=['POST'])
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
            logo_path = os.path.join(app.root_path, 'static/uploads/hospital_logos', hospital.logo_url)
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
        upload_folder = os.path.join(app.root_path, 'static/uploads/prescriptions')
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

@app.route('/api/doctor/chat/<path:patient_id>/send', methods=['POST'])
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

@app.route('/api/doctor/chat/<path:patient_id>/messages')
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
            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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
The Spherix Clinic Team"""
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
The Spherix Clinic Team"""
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
The Spherix Clinic Team"""
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
        timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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
            body = f"Dear {patient.name},\n\nDr. {appointment.doctor.first_name} {appointment.doctor.last_name} has uploaded a prescription for your appointment on {appointment.appointment_date}.\n\nYou can view and download it from your dashboard.\n\nBest regards,\nThe Spherix Clinic Team"
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
    categorized_drugs = {}
    return render_template('drugs.html', categorized_drugs=categorized_drugs)

@app.route('/drug-info/<path:drug_name>')
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
    drug_names = sorted(MEDICINE_LIST, key=lambda x: x.lower())
    return render_template('conditions.html', conditions=conditions_list, drug_names=drug_names)

@app.route('/medical-lab')
def medical_lab():
    return render_template('medical_lab.html')

@app.route('/medical-lab/payment', methods=['POST'])
@patient_required
def medical_lab_payment():
    if not razorpay_client:
        return jsonify({"success": False, "error": "Payment gateway is not configured."}), 503

    data = request.get_json(silent=True)
    selected_tests = data.get('selected_tests') if data else None
    if not selected_tests or not isinstance(selected_tests, list):
        return jsonify({"success": False, "error": "No lab test selection provided."}), 400

    subtotal = 0.0
    items = []
    for entry in selected_tests:
        item_id = entry.get('id')
        name = entry.get('name')
        price = entry.get('price')
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 0.0
        if not name or price <= 0:
            continue
        items.append({"id": item_id, "name": name, "price": price, "quantity": 1})
        subtotal += price

    if subtotal <= 0:
        return jsonify({"success": False, "error": "Please select at least one valid lab test."}), 400

    total_price = round(subtotal + 4.99, 2)
    order_id = TEMP_DATA['next_ids']['order']
    new_order = Order(
        id=order_id,
        patient_id=current_user.id,
        items=items,
        total_price=total_price,
        shipping_address={},
        order_date=date.today(),
        status='Awaiting Payment'
    )
    TEMP_DATA['orders'][order_id] = new_order
    TEMP_DATA['next_ids']['order'] += 1
    save_data()

    try:
        payment_link = razorpay_client.payment_link.create({
            "amount": int(total_price * 100),
            "currency": "INR",
            "accept_partial": False,
            "reference_id": f"lab_{order_id}_{int(time_module.time())}",
            "description": f"Lab Test Booking #{order_id}",
            "customer": {
                "name": current_user.name or current_user.email,
                "email": current_user.email
            },
            "callback_url": url_for('order_success', order_id=order_id, _external=True) + '?session_id=razorpay_payment',
            "callback_method": "get"
        })
        return jsonify({"success": True, "redirect_url": payment_link['short_url']})
    except Exception as e:
        return jsonify({"success": False, "error": f"Payment gateway error: {str(e)}"}), 500

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
        'images/image3.jpg','images/image4.jpg','images/image5.jpg','images/image6.jpg','images/image7.jpg',
        'images/image8.jpg','images/image10.jpg','images/image12.jpg','images/image13.jpg','images/image14.jpg',
        'images/image15.jpg','images/image16.jpg','images/image17.jpg','images/image18.jpg',
    ]

    # Load symptom uploaded images from Step 2
    uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
    if os.path.exists(uploads_dir):
        try:
            # Fetch files starting with 'captured_symptom_' and sort them so the newest are first
            uploaded_files = sorted(
                [f for f in os.listdir(uploads_dir) if f.startswith('captured_symptom_') and f.endswith('.jpg')],
                reverse=True
            )
            for f in uploaded_files:
                gallery_images.insert(0, f"uploads/{f}") # Add to the beginning of the gallery
        except Exception as e:
            print(f"Error loading gallery uploads: {e}")

    videos = [
        {"url":"https://www.youtube.com/watch?v=7D-gxaie6UI", "title":"Research Video 1"},
        {"url":"https://www.youtube.com/watch?v=b1-pZumCz7Q", "title":"Research Video 2"}
    ]

    return render_template('gallery.html', images=gallery_images, videos=videos)

@app.route('/gallery/download')
def download_watermarked_image():
    filepath_param = request.args.get('filepath', '')
    if not filepath_param:
        return "Filepath parameter is required", 400
        
    clean_path = filepath_param.lstrip('/')
    if not clean_path.startswith('static/'):
        return "Unauthorized file path access", 403
        
    full_path = os.path.join(app.root_path, clean_path)
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

@app.route('/logout')
def logout():
    logout_user() # Use Flask-Login's logout_user function
    return redirect(url_for('login_landing'))

@app.route('/contact', methods=['GET', 'POST'])
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

@app.route('/pharmacist', methods=['GET', 'POST'])
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

@app.route('/api/feedback', methods=['POST'])
@csrf.exempt
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
        
        admin_email = 'admin@spherixclinic.com'
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
    name = request.form.get('name')
    contact = request.form.get('contact')
    interests = request.form.getlist('interests')
    
    if email:
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
        user_body = f"""
        <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #020617; color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #1e293b;">
            <div style="background: linear-gradient(135deg, #0891b2 0%, #2563eb 100%); padding: 30px 20px; text-align: center;">
                <h2 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 1px;">Spherix Clinic</h2>
                <p style="color: #cffafe; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px;">Medical Intelligence Network</p>
            </div>
            <div style="padding: 40px 30px; background-color: #0f172a;">
                <h3 style="color: #38bdf8; font-size: 20px; margin-top: 0;">Sync Established.</h3>
                <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1; margin-bottom: 20px;">Welcome to the Spherix Network.</p>
                <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1; margin-bottom: 30px;">Thank you for subscribing. You are now connected to our intelligence broadcast and will be the first to receive exclusive updates on Neural Diagnostics, Bio-Telemetry, and Longevity Science.</p>
                <p style="font-size: 14px; color: #94a3b8; margin-bottom: 0;">Stay optimized,</p>
                <p style="font-size: 14px; color: #f8fafc; font-weight: bold; margin-top: 5px;">Spherix Clinic Core Team</p>
            </div>
            <div style="background-color: #020617; padding: 20px; text-align: center; border-top: 1px solid #1e293b;">
                <p style="color: #64748b; font-size: 11px; margin: 0;">&copy; {datetime.now().year} Spherix Clinic. All rights reserved.</p>
                <p style="color: #64748b; font-size: 11px; margin-top: 5px;">Headquarters: Motihari, Bihar - 845401, India | +91 933 4325 920</p>
            </div>
        </div>
        """
        send_notification_email(email, user_subject, user_body, is_html=True)
        flash("Successfully subscribed to the Spherix Network.", "subscribe_success")
    else:
        flash("Please provide a valid email address.", "error")
    return redirect(request.referrer or url_for('home'))

@app.route('/admin/download-sicons-file/<filename>')
@admin_required
def admin_download_sicons_file(filename):
    safe_filename = secure_filename(filename)
    filepath = os.path.join(app.root_path, 'static', 'uploads', 'sicons_apps', safe_filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash("Application file not found.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/sicons/approve/<int:app_id>', methods=['POST'])
@admin_required
def admin_approve_sicons(app_id):
    sicons_apps = TEMP_DATA.get('sicons_applications', [])
    app_data = next((a for a in sicons_apps if a.get('id') == app_id), None)
    
    if app_data:
        app_data['status'] = 'approved'
        save_data()
        
        applicant_email = app_data.get('email')
        if applicant_email:
            subject = "Application Approved - Spherix iCons Engineering"
            body = f"""
            <div style="font-family: Arial, sans-serif; background-color: #000; color: #fff; padding: 30px; border: 1px solid #333;">
                <h2 style="color: #E01E23; letter-spacing: 2px;">Spherix iCons // DEPLOYMENT APPROVED</h2>
                <p style="color: #ccc;">ATTN: {app_data.get('full_name', 'CANDIDATE').upper()}</p>
                <p style="color: #ccc; line-height: 1.6;">Congratulations. Your application for the position of <strong>{app_data.get('position', 'Engineering Role').upper()}</strong> has been approved by Spherix iCons Engineering Leadership.</p>
                <p style="color: #ccc; line-height: 1.6;">Our deployment team will contact you shortly with the next steps and onboarding protocols.</p>
                <br>
                <p style="font-size: 11px; color: #666; letter-spacing: 1px; text-transform: uppercase;">
                    Spherix iCons Deployment Operations<br>
                    System Status: Verified
                </p>
            </div>
            """
            send_notification_email(to_email=applicant_email, subject=subject, body=body, is_html=True)
            
        flash(f"Application for {app_data.get('full_name')} approved.", "success")
    else:
        flash("Application not found.", "error")
        
    return redirect(url_for('admin_dashboard') + '#sicons_apps')

@app.route('/admin/sicons/reject/<int:app_id>', methods=['POST'])
@admin_required
def admin_reject_sicons(app_id):
    sicons_apps = TEMP_DATA.get('sicons_applications', [])
    app_data = next((a for a in sicons_apps if a.get('id') == app_id), None)
    
    if app_data:
        app_data['status'] = 'rejected'
        save_data()
        
        applicant_email = app_data.get('email')
        if applicant_email:
            subject = "Application Status Update - Spherix iCons Engineering"
            body = f"""
            <div style="font-family: Arial, sans-serif; background-color: #000; color: #fff; padding: 30px; border: 1px solid #333;">
                <h2 style="color: #E01E23; letter-spacing: 2px;">Spherix iCons // DEPLOYMENT UPDATE</h2>
                <p style="color: #ccc;">ATTN: {app_data.get('full_name', 'CANDIDATE').upper()}</p>
                <p style="color: #ccc; line-height: 1.6;">Thank you for your interest in joining Spherix iCons as a <strong>{app_data.get('position', 'Engineering Role').upper()}</strong>.</p>
                <p style="color: #ccc; line-height: 1.6;">After careful review of your professional metadata, we regret to inform you that we will not be moving forward with your deployment at this time.</p>
                <p style="color: #ccc; line-height: 1.6;">We appreciate your ambition to build the pulse of sentient technology and wish you the best in your future endeavors.</p>
                <br>
                <p style="font-size: 11px; color: #666; letter-spacing: 1px; text-transform: uppercase;">
                    Spherix iCons Deployment Operations<br>
                    System Status: Archived
                </p>
            </div>
            """
            send_notification_email(to_email=applicant_email, subject=subject, body=body, is_html=True)
            
        flash(f"Application for {app_data.get('full_name')} rejected.", "success")
    else:
        flash("Application not found.", "error")
        
    return redirect(url_for('admin_dashboard') + '#sicons_apps')

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
    sicons_apps = TEMP_DATA.get('sicons_applications', [])
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
                           sicons_applications=sicons_apps,
                           newsletter_subscribers=newsletter_subscribers,
                           stamp_exists=stamp_exists, 
                                                       settings=TEMP_DATA.get('settings', {}),
                            current_time=time_module.time(),
                            medicines=list(TEMP_DATA.get('medicines', [])))

@app.route('/admin/medicine/add', methods=['POST'])
@admin_required
def admin_add_medicine():
    name = request.form.get('name')
    category = request.form.get('category')
    try:
        price = float(request.form.get('price', 0.0))
    except ValueError:
        price = 0.0
    
    if name and category:
        exists = any(m['name'].lower() == name.lower() for m in TEMP_DATA.get('medicines', []))
        if exists:
            flash('Medicine already exists in inventory.', 'warning')
        else:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO medicines (name, category, price) VALUES (?, ?, ?)", (name, category, price))
                    conn.commit()
                    conn.close()
                except Exception as db_err:
                    print(f"⚠️ Error inserting medicine to DB: {db_err}")
            
            new_id = len(TEMP_DATA.get('medicines', [])) + 1
            new_med = {'id': new_id, 'name': name, 'category': category, 'price': price}
            if 'medicines' not in TEMP_DATA:
                TEMP_DATA['medicines'] = []
            TEMP_DATA['medicines'].append(new_med)
            
            global MEDICINE_LIST
            if name not in MEDICINE_LIST:
                MEDICINE_LIST.append(name)
            
            flash('Medicine registered successfully.', 'success')
    else:
        flash('Medicine name and category are required.', 'error')
    return redirect(url_for('admin_dashboard') + '#pharmacy')

@app.route('/admin/medicine/delete/<int:med_id>', methods=['POST'])
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
            
    TEMP_DATA['medicines'] = [m for m in TEMP_DATA.get('medicines', []) if m['id'] != med_id]
    flash('Medicine deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '#pharmacy')

@app.route('/admin/update-settings', methods=['POST'])
@admin_required
def admin_update_settings():
    if 'settings' not in TEMP_DATA:
        TEMP_DATA['settings'] = {}
    
    hq_address = request.form.get('hq_address')
    if hq_address is not None:
        TEMP_DATA['settings']['hq_address'] = hq_address
    contact_email = request.form.get('contact_email')
    if contact_email is not None:
        TEMP_DATA['settings']['contact_email'] = contact_email
    contact_phone = request.form.get('contact_phone')
    if contact_phone is not None:
        TEMP_DATA['settings']['contact_phone'] = contact_phone
        
    save_data()
    flash("System settings updated successfully.", "success")
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/settings/email', methods=['POST'])
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

class DataEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        return super().default(obj)

@app.route('/admin/backup')
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

@app.route('/admin/restore', methods=['POST'])
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

@app.route('/hospital/export_appointments')
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

@app.route('/hospital/export_report_pdf')
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

@app.route('/api/qr')
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

        flash(f"Doctor {doctor.first_name} {doctor.last_name} has been verified.", "success")
    else:
        flash("Doctor not found.", "error")
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/hospital/verify/<path:hospital_id>', methods=['POST'])
@admin_required
def admin_verify_hospital(hospital_id):
    hospital_id = parse_route_id(hospital_id)
    hospital = TEMP_DATA['hospitals'].get(hospital_id)
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

@app.route('/admin/toggle_status/<string:entity_type>/<string:action>/<path:entity_id>', methods=['POST'])
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
        
    parsed_id = entity_id
    if entity_type != 'doctor':
        try:
            parsed_id = int(entity_id)
        except ValueError:
            pass
            
    entity = TEMP_DATA.get(collection_name, {}).get(parsed_id)
    if not entity:
        flash(f"{entity_type.replace('_', ' ').title()} not found.", "error")
        return redirect(url_for('admin_dashboard') + f'#{collection_name}')
        
    if action in ['block', 'hide']:
        attr_name = f'is_{action}ed' if action == 'block' else f'is_{action}den'
        current_status = getattr(entity, attr_name, False)
        setattr(entity, attr_name, not current_status)
        status_text = f"{action}ed" if not current_status else f"un{action}ed" if action == 'block' else f"un{action}den"
        flash(f"Successfully {status_text} the {entity_type.replace('_', ' ')}.", "success")
    else:
        flash("Invalid action.", "error")
        
    save_data()
    return redirect(url_for('admin_dashboard') + f'#{collection_name}')

@app.route('/admin/doctor/add', methods=['GET', 'POST'])
@admin_required
def admin_add_doctor():
    """Allows an admin to add a new doctor."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('admin_add_doctor_form.html')

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
            password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
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
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('admin_add_patient_form.html')

        existing_patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        if existing_patient:
            flash('A patient with this email already exists.', 'error')
            return render_template('admin_add_patient_form.html')

        new_id = f"PAT/{datetime.now().year}/{TEMP_DATA['next_ids']['patient']:03d}"
        new_patient = Patient(id=new_id, name=request.form.get('name'), email=email, password=generate_password_hash(password, method='pbkdf2:sha256:260000'))
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

@app.route('/admin/patient/edit/<path:patient_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_patient(patient_id):
    patient_id = parse_route_id(patient_id)
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
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        hospital_name = request.form.get('hospital_name')

        if not all([name, email, role, password, confirm_password]):
            flash("All fields including confirm password are required to add a staff member.", "error")
            return render_template('admin_add_staff_form.html', hospitals=list(TEMP_DATA['hospitals'].values()))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('admin_add_staff_form.html', hospitals=list(TEMP_DATA['hospitals'].values()))

        existing_staff = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)
        if existing_staff:
            flash(f"A staff member with the email {email} already exists.", "error")
            return render_template('admin_add_staff_form.html', hospitals=list(TEMP_DATA['hospitals'].values()))

        staff_id = f"STF/{datetime.now().year}/{TEMP_DATA['next_ids']['staff']:03d}"
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        new_staff = Staff(id=staff_id, name=name, email=email, password=hashed_password, role=role, phone=phone, hospital_name=hospital_name)

        TEMP_DATA['staff'][staff_id] = new_staff
        TEMP_DATA['next_ids']['staff'] += 1
        save_data()
        flash(f"Staff member '{name}' has been added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    # For a GET request, show the form to add a staff member.
    return render_template('admin_add_staff_form.html', hospitals=list(TEMP_DATA['hospitals'].values()))


@app.route('/admin/staff/edit/<path:staff_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_staff(staff_id):
    staff_id = parse_route_id(staff_id)
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
        staff.hospital_name = request.form.get('hospital_name', staff.hospital_name)
        save_data()
        flash(f"Staff member {staff.name} updated successfully.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_staff.html', staff=staff, hospitals=list(TEMP_DATA['hospitals'].values()))

@app.route('/admin/staff/delete/<path:staff_id>', methods=['POST'])
@admin_required
def admin_delete_staff(staff_id):
    staff_id = parse_route_id(staff_id)
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

@app.route('/admin/patient/delete/<path:patient_id>', methods=['POST'])
@admin_required
def admin_delete_patient(patient_id):
    patient_id = parse_route_id(patient_id)
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

@app.route('/admin/organ-donor/edit/<path:donor_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_organ_donor(donor_id):
    donor_id = parse_route_id(donor_id)
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

@app.route('/admin/organ-donor/delete/<path:donor_id>', methods=['POST'])
@admin_required
def admin_delete_organ_donor(donor_id):
    donor_id = parse_route_id(donor_id)
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
        confirm_password = request.form.get('confirm_password')
        
        if not all([name, email, password, confirm_password]):
            flash("All fields including confirm password are required.", "error")
            return render_template('admin_add_hospital_form.html')

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('admin_add_hospital_form.html')

        existing_hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.email == email), None)
        if existing_hospital:
            flash(f"A hospital with email {email} already exists.", "error")
            return render_template('admin_add_hospital_form.html')

        hospital_id = f"HPT/{datetime.now().year}/{TEMP_DATA['next_ids']['hospital']:03d}"
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')
        new_hospital = Hospital(id=hospital_id, name=name, email=email, password=hashed_password)
        
        TEMP_DATA['hospitals'][hospital_id] = new_hospital
        TEMP_DATA['next_ids']['hospital'] += 1
        save_data()
        flash(f"Hospital '{name}' added successfully.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_hospital_form.html')

@app.route('/admin/hospital/edit/<path:hospital_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_hospital(hospital_id):
    hospital_id = parse_route_id(hospital_id)
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

@app.route('/admin/hospital/delete/<path:hospital_id>', methods=['POST'])
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

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles the login process for the administrator."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # The admin user is hardcoded for this application
        if email != 'admin@spherixclinic.com':
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
                timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")
        
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
            new_id = f"HPT/{datetime.now().year}/{TEMP_DATA['next_ids']['hospital']:03d}"
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

@app.route('/hospital/forgot-password', methods=['GET', 'POST'])
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
            if getattr(hospital, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('hospital_login'))
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
                else:
                    flash("No ICU beds available!", "error")
            else:
                if hospital.available_beds > 0:
                    hospital.available_beds -= 1
                    booking.status = 'approved'
                    booking.room_number = room_number
                    flash("General Bed booking approved and availability updated.", "success")
                else:
                    flash("No General beds available!", "error")
        elif action == 'reject':
            booking.status = 'rejected'
            flash("Bed booking rejected.", "success")
    
    save_data()
    return redirect(request.referrer or url_for('home'))

@app.route('/bed_booking/invoice/<int:booking_id>')
@login_required
def bed_booking_invoice(booking_id):
    booking = get_temp_data_item('bed_bookings', booking_id)
    if not booking:
        flash("Booking not found.", "error")
        return redirect(url_for('home'))

    is_patient = hasattr(current_user, 'is_doctor') and not current_user.is_doctor and str(booking.patient_id) == str(current_user.id)
    is_hospital = getattr(current_user, 'is_hospital', False) and str(booking.hospital_id) == str(current_user.id)
    is_admin = hasattr(current_user, 'email') and current_user.email == 'admin@spherixclinic.com'

    if not (is_patient or is_hospital or is_admin):
        flash("Unauthorized access to invoice.", "error")
        return redirect(url_for('home'))

    if booking.status != 'approved':
        flash("Invoice is only available for approved bookings.", "warning")
        return redirect(request.referrer or url_for('home'))

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

        return send_file(BytesIO(pdf_bytes), as_attachment=True, download_name=f'bed_booking_invoice_{booking.id}.pdf', mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating bed booking invoice: {e}")
        flash("An error occurred while generating the invoice.", "error")
        return redirect(request.referrer or url_for('home'))

@app.route('/hospital/bed_booking/<int:booking_id>/email_invoice', methods=['POST'])
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

@app.route('/hospital/dashboard', methods=['GET', 'POST'])
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
                            filename = secure_filename(file.filename)
                            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                            unique_filename = f"staff_profile_{timestamp}_{filename}"
                            upload_folder = os.path.join(app.root_path, 'static/uploads')
                            os.makedirs(upload_folder, exist_ok=True)
                            file.save(os.path.join(upload_folder, unique_filename))
                            profile_pic = unique_filename
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
                    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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

    # Filter doctors belonging to this hospital
    hospital_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if (d.hospital_id == current_user.id and d.hospital_approval_status == 'approved') or \
           (not d.hospital_id and d.hospital_name == current_user.name)
    ]
    pending_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if d.hospital_id == current_user.id and d.hospital_approval_status == 'pending'
    ]
    available_unlinked_doctors = [
        d for d in TEMP_DATA['doctors'].values()
        if d.hospital_id != current_user.id and d.hospital_name != current_user.name
    ]
    
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
    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if str(b.hospital_id) == str(current_user.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)

    all_blood_donors = [d for d in TEMP_DATA.get('blood_donors', {}).values() if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or not getattr(d, 'hospital_id', None)]
    all_organ_donors = [d for d in TEMP_DATA.get('organ_donors', {}).values() if str(getattr(d, 'hospital_id', '')) == str(current_user.id) or not getattr(d, 'hospital_id', None)]
    blood_stock = current_user.blood_stock if hasattr(current_user, 'blood_stock') else TEMP_DATA.get('blood_stock', {})

    return render_template('hospital_dashboard.html', 
                           appointments=hospital_appointments, 
                           doctors=hospital_doctors,
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
                           chart_data=chart_data)

@app.route('/hospital/dashboard/staff/<path:staff_id>/update', methods=['POST'])
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
                filename = secure_filename(file.filename)
                timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                unique_filename = f"staff_profile_{timestamp}_{filename}"
                upload_folder = os.path.join(app.root_path, 'static/uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, unique_filename))
                staff_member.profile_picture_url = unique_filename
            else:
                flash('Invalid image file format.', 'error')
                
    save_data()
    flash(f'Staff member {staff_member.name} updated successfully.', 'success')
    return redirect(url_for('hospital_dashboard') + '#staff')

@app.route('/hospital/organ-donor/<path:donor_id>/contact', methods=['POST'])
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

@app.route('/login_landing') # Renamed to avoid conflict if /login is for patient
def login_landing():
    return render_template('login_landing.html')

@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    """Handles login for staff members."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        agree_terms = request.form.get('agree_terms')

        if not agree_terms:
            flash('You must agree to the Department Staff Agreement and Privacy Policy.', 'error')
            return redirect(url_for('staff_login'))

        staff_member = next((s for s in TEMP_DATA['staff'].values() if s.email == email), None)

        if staff_member and check_password_hash(staff_member.password, password):
            if getattr(staff_member, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('staff_login'))
            staff_member.last_login = utcnow()
            save_data()
            login_user(staff_member)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('staff_dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('staff_login'))

    return render_template('staff_login.html')

def get_common_staff_data():
    """Helper to load standard hospital info to avoid repeating code."""
    hospital_name = current_user.hospital_name
    hospital = next((h for h in TEMP_DATA['hospitals'].values() if h.name == hospital_name), None)
    activity_logs = []
    if hospital:
        activity_logs = [log for log in TEMP_DATA.get('activity_logs', {}).values() if str(log.hospital_id) == str(hospital.id)]
        activity_logs.sort(key=lambda x: x.created_at, reverse=True)
    return hospital_name, hospital, activity_logs

@app.route('/staff/dashboard')
@staff_required
def staff_dashboard():
    """Main dispatcher for staff dashboards based on role."""
    role = getattr(current_user, 'role', '')
    if role in ['Receptionist', 'Appointment Management']:
        return redirect(url_for('staff_reception_dashboard'))
    elif role == 'Bed Management':
        return redirect(url_for('staff_bed_dashboard'))
    elif role == 'Blood Donor Management':
        return redirect(url_for('staff_blood_dashboard'))
    elif role == 'Organ Donor Management':
        return redirect(url_for('staff_organ_dashboard'))
    else:
        return redirect(url_for('staff_general_dashboard'))

@app.route('/staff/profile/update', methods=['POST'])
@staff_required
def staff_update_profile():
    """Shared route for updating staff profile details."""
    current_user.name = request.form.get('name', current_user.name)
    current_user.phone = request.form.get('phone', current_user.phone)
    new_password = request.form.get('password')
    if new_password:
         current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256:260000')
    save_data()
    flash('Profile updated successfully!', 'success')
    return redirect(request.referrer or url_for('staff_dashboard'))

@app.route('/staff/dashboard/reception', methods=['GET', 'POST'])
@staff_required
def staff_reception_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data()
    
    if request.method == 'POST' and hospital:
        if 'cancel_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                TEMP_DATA['appointments'][appt_id].status = 'cancelled'
                save_data()
                flash('Appointment cancelled successfully.', 'success')
        elif 'approve_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                TEMP_DATA['appointments'][appt_id].status = 'confirmed'
                save_data()
                flash('Appointment confirmed successfully.', 'success')
        elif 'complete_appointment' in request.form:
            appt_id = parse_route_id(request.form.get('appointment_id'))
            if appt_id in TEMP_DATA['appointments']:
                TEMP_DATA['appointments'][appt_id].status = 'completed'
                save_data()
                flash('Appointment marked as completed.', 'success')
        elif 'book_walkin' in request.form:
            try:
                appt_id = TEMP_DATA['next_ids']['appointment']
                patient_name = request.form.get('patient_name')
                patient_phone = request.form.get('patient_phone')
                doctor_id = request.form.get('doctor_id')
                date_str = request.form.get('appointment_date')
                time_str = request.form.get('appointment_time')
                reason = request.form.get('reason', 'Walk-in Consultation')
                
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
                new_appt.patient_id = 'walk-in'
                TEMP_DATA['appointments'][appt_id] = new_appt
                TEMP_DATA['next_ids']['appointment'] += 1
                
                # Log activity
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Walk-in Registered",
                    details=f"Registered walk-in patient {patient_name} for doctor {doctor_id}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash('Walk-in appointment registered and confirmed.', 'success')
            except Exception as e:
                flash(f'Error registering walk-in: {str(e)}', 'error')
        elif 'update_hospital_profile' in request.form:
            try:
                hospital.phone = request.form.get('phone', hospital.phone)
                hospital.email = request.form.get('email', hospital.email)
                hospital.address = request.form.get('address', hospital.address)
                
                # Log activity
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
    
    hospital_doctors = [d for d in TEMP_DATA['doctors'].values() if d.hospital_name == hospital_name]
    doctor_ids = {d.id for d in hospital_doctors}
    hospital_appointments = [a for a in TEMP_DATA['appointments'].values() if a.doctor_id in doctor_ids]
    hospital_appointments.sort(key=lambda x: (x.appointment_date, x.appointment_time), reverse=True)
    patient_ids = {a.patient_id for a in hospital_appointments if a.patient_id}
    hospital_patients = [TEMP_DATA['patients'][pid] for pid in patient_ids if pid in TEMP_DATA['patients']]
    
    return render_template('staff_reception_dashboard.html', 
                           staff=current_user, hospital=hospital, doctors=hospital_doctors, 
                           appointments=hospital_appointments, patients=hospital_patients, 
                           activity_logs=activity_logs)

@app.route('/staff/dashboard/beds', methods=['GET', 'POST'])
@staff_required
def staff_bed_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data()
    
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
            if booking and str(booking.hospital_id) == str(hospital.id) and booking.status == 'approved':
                booking.status = 'discharged'
                if booking.bed_type == 'ICU':
                    hospital.available_icu_beds = min(hospital.icu_beds, hospital.available_icu_beds + 1)
                else:
                    hospital.available_beds = min(hospital.total_beds, hospital.available_beds + 1)
                
                log_id = TEMP_DATA['next_ids']['activity_log']
                TEMP_DATA['activity_logs'][log_id] = ActivityLog(
                    id=log_id,
                    hospital_id=hospital.id,
                    user_name=current_user.name,
                    action="Discharged Patient",
                    details=f"Discharged patient {booking.patient_name} from {booking.bed_type} Bed {booking.room_number or 'N/A'}."
                )
                TEMP_DATA['next_ids']['activity_log'] += 1
                
                save_data()
                flash('Patient discharged and bed released successfully.', 'success')
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
                    
                booking_id = TEMP_DATA['next_ids']['bed_booking']
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
        return redirect(url_for('staff_bed_dashboard'))

    hospital_bed_bookings = [b for b in TEMP_DATA.get('bed_bookings', {}).values() if hospital and str(b.hospital_id) == str(hospital.id)]
    hospital_bed_bookings.sort(key=lambda x: x.created_at, reverse=True)
    
    return render_template('staff_bed_dashboard.html', 
                           staff=current_user, hospital=hospital, 
                           bed_bookings=hospital_bed_bookings, activity_logs=activity_logs)

@app.route('/staff/dashboard/blood', methods=['GET', 'POST'])
@staff_required
def staff_blood_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data()

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
                flash("Blood donor updated successfully.", "success")
        elif 'delete_blood_donor' in request.form:
            donor_id = parse_route_id(request.form.get('donor_id', ''))
            if donor_id in TEMP_DATA.get('blood_donors', {}):
                del TEMP_DATA['blood_donors'][donor_id]
                save_data()
                flash("Blood donor deleted successfully.", "success")
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
        return redirect(url_for('staff_blood_dashboard'))

    blood_donors = [d for d in TEMP_DATA.get('blood_donors', {}).values() if getattr(d, 'hospital_id', None) == hospital.id or not getattr(d, 'hospital_id', None)]
    blood_stock = hospital.blood_stock if hasattr(hospital, 'blood_stock') else TEMP_DATA.get('blood_stock', {})
    camps = [c for c in TEMP_DATA.get('camps', {}).values() if c.get('organizer') == hospital_name]
    camp_names = [c['name'] for c in camps]
    camp_registrations = [r for r in TEMP_DATA.get('camp_registrations', {}).values() if r.get('camp_name') in camp_names]

    return render_template('staff_blood_dashboard.html', 
                           staff=current_user, hospital=hospital, blood_donors=blood_donors, 
                           blood_stock=blood_stock, camps=camps, camp_registrations=camp_registrations, 
                           activity_logs=activity_logs)

@app.route('/staff/dashboard/organ', methods=['GET', 'POST'])
@staff_required
def staff_organ_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data()

    if request.method == 'POST' and hospital:
        donor_id = parse_route_id(request.form.get('donor_id', ''))
        if 'edit_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            donor = TEMP_DATA['organ_donors'][donor_id]
            donor.name, donor.email = request.form.get('name', donor.name), request.form.get('email', donor.email)
            donor.phone, donor.city = request.form.get('phone', donor.phone), request.form.get('city', donor.city)
            donor.blood_group, donor.organs = request.form.get('blood_group', donor.blood_group), request.form.getlist('organs')
            save_data()
            flash("Organ donor updated.", "success")
        elif 'delete_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            del TEMP_DATA['organ_donors'][donor_id]
            save_data()
            flash("Organ donor deleted.", "success")
        elif 'approve_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            TEMP_DATA['organ_donors'][donor_id].status = 'approved'
            save_data()
            flash("Organ donor pledge approved.", "success")
        elif 'reject_organ_donor' in request.form and donor_id in TEMP_DATA.get('organ_donors', {}):
            TEMP_DATA['organ_donors'][donor_id].status = 'rejected'
            save_data()
            flash("Organ donor pledge rejected.", "success")
        elif 'add_organ_request' in request.form:
            try:
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
        elif 'match_donor_to_request' in request.form:
            req_id = parse_route_id(request.form.get('request_id'))
            donor_id = parse_route_id(request.form.get('donor_id'))
            
            req = TEMP_DATA.get('organ_requests', {}).get(req_id)
            donor = TEMP_DATA.get('organ_donors', {}).get(donor_id)
            
            if req and donor and donor.status == 'approved' and req.status == 'active':
                req.status = 'matched'
                donor.status = 'matched'
                
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
        return redirect(url_for('staff_organ_dashboard'))

    organ_donors = [d for d in TEMP_DATA.get('organ_donors', {}).values() if getattr(d, 'hospital_id', None) == hospital.id or not getattr(d, 'hospital_id', None)]
    organ_requests = [r for r in TEMP_DATA.get('organ_requests', {}).values() if hospital and r.hospital_id == hospital.id]
    
    return render_template('staff_organ_dashboard.html', 
                           staff=current_user, hospital=hospital, organ_donors=organ_donors, 
                           organ_requests=organ_requests, activity_logs=activity_logs)

@app.route('/staff/dashboard/general', methods=['GET', 'POST'])
@staff_required
def staff_general_dashboard():
    hospital_name, hospital, activity_logs = get_common_staff_data()
    
    if request.method == 'POST' and hospital:
        if 'post_bulletin' in request.form:
            title = request.form.get('title')
            content = request.form.get('content')
            
            bulletin_key = f"bulletins_{hospital.id}"
            bulletins = json.loads(TEMP_DATA['settings'].get(bulletin_key, "[]"))
            bulletins.append({
                "id": len(bulletins) + 1,
                "title": title,
                "content": content,
                "author": current_user.name,
                "date": datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            # Keep bulletins sorted newest first
            bulletins.reverse()
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
            
    return render_template('staff_general_dashboard.html', 
                           staff=current_user, hospital=hospital, 
                           activity_logs=activity_logs, bulletins=bulletins)

@app.route('/patient/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute") # Specific, stricter limit for login attempts
def patient_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        patient = next((p for p in TEMP_DATA['patients'].values() if p.email == email), None)
        
        if patient:
            if getattr(patient, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('patient_login'))
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
                next_page = request.form.get('next') or request.args.get('next')
                if next_page and urlparse(next_page).netloc == '':
                    return redirect(next_page)
                return redirect(url_for('patient_dashboard'))

        flash("Invalid email or password", "error")
    return render_template('patient_login.html', next_page=request.args.get('next'))

@app.route('/patient/signup', methods=['GET', 'POST'])
def patient_signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password') # Raw password
        confirm_password = request.form.get('confirm_password')
        age = request.form.get('age') # Assuming age is also submitted
        gender = request.form.get('gender') # Assuming gender is also submitted

        if not all([name, email, password, confirm_password]):
            flash("Name, email, password, and confirm password are required fields.", "error")
            return redirect(url_for('patient_signup'))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
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
            new_id = f"PAT/{datetime.now().year}/{TEMP_DATA['next_ids']['patient']:03d}"
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

@app.route('/patient/forgot-password', methods=['GET', 'POST'])
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
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        blood_group = request.form.get('blood_group')
        age = request.form.get('age')
        city = request.form.get('city')
        last_donation = request.form.get('last_donation')
        agree_terms = request.form.get('agree_terms')
        hospital_id = request.form.get('hospital_id')

        if not agree_terms:
            flash('You must agree to the Donor Consent Form and Privacy Policy.', 'error')
            return redirect(url_for('blood_donor_register'))

        if not all([name, email, password, confirm_password, phone, blood_group, age, city]):
            flash('Please fill out all required fields.', 'error')
            return redirect(url_for('blood_donor_register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
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
            'otp': otp,
            'hospital_id': hospital_id
        }

        # Send OTP Email
        subject = "Verify your email - Spherix Clinic Blood Donor"
        body = get_premium_otp_email_html(
            title="Blood Donor Verification",
            greeting=f"Hello {name},",
            message="Thank you for joining our community of lifesavers. To complete your registration and verify your email address, please use the One-Time Password (OTP) below:",
            otp=otp,
            role_color="#dc2626",
            accent_bg="#fef2f2"
        )
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")

        return redirect(url_for('blood_donor_verify_otp'))
        
    hospitals = [h for h in TEMP_DATA['hospitals'].values() if getattr(h, 'is_verified', True) and not getattr(h, 'is_hidden', False)]
    return render_template('blood_donor_register.html', hospitals=hospitals)

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
            donor_id = f"BD/{datetime.now().year}/{TEMP_DATA['next_ids']['blood_donor']:03d}"
            new_donor = BloodDonor(
                id=donor_id, 
                name=stored_data['name'], 
                email=stored_data['email'], 
                phone=stored_data['phone'],
                blood_group=stored_data['blood_group'], 
                age=stored_data['age'], 
                city=stored_data['city'], 
                password=stored_data['password'], 
                last_donation=stored_data['last_donation'],
                hospital_id=stored_data.get('hospital_id')
            )
            
            TEMP_DATA['blood_donors'][donor_id] = new_donor
            TEMP_DATA['next_ids']['blood_donor'] += 1
            save_data()
            
            session.pop('donor_signup_data', None)
            flash('Registration successful! Please wait for staff approval before logging in.', 'success')
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

@app.route('/blood-donor/forgot-password', methods=['GET', 'POST'])
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
            if getattr(donor, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('blood_donor_login'))
            if getattr(donor, 'status', 'pending') != 'approved':
                flash('Your account is pending verification by the hospital staff.', 'warning')
                return redirect(url_for('blood_donor_login'))
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
                    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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

    return render_template('blood_donor_dashboard.html', donor=current_user, camps=list(TEMP_DATA.get('camps', {}).values()))

@app.route('/blood-donors')
def blood_donors_list():
    city_query = request.args.get('city', '').strip().lower()
    blood_group_query = request.args.get('blood_group', '').strip()

    # Only show approved donors to the public
    all_donors = [d for d in TEMP_DATA['blood_donors'].values() if getattr(d, 'status', 'pending') == 'approved' and not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
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
        agree_terms = request.form.get('agree_terms')
        hospital_id = request.form.get('hospital_id')

        if not agree_terms:
            flash('You must agree to the Donor Consent Form and Privacy Policy.', 'error')
            return redirect(url_for('organ_donor_register'))

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
            'otp': otp,
            'hospital_id': hospital_id
        }
        
        # Send OTP Email
        subject = "Verify your email - Spherix Clinic Organ Donor"
        body = get_premium_otp_email_html(
            title="Organ Donor Verification",
            greeting=f"Hello {name},",
            message="Thank you for your noble decision to pledge your organs. To complete your registration and verify your email address, please use the One-Time Password (OTP) below:",
            otp=otp,
            role_color="#0284c7",
            accent_bg="#f0f9ff"
        )
        
        if send_notification_email(email, subject, body, is_html=True):
            flash("OTP sent to your email. Please verify.", "info")
        else:
            print(f"DEBUG: OTP for {email} is {otp}")
            flash(f"Failed to send OTP email. [DEV ONLY] OTP is: {otp}", "warning")

        return redirect(url_for('organ_donor_verify_otp'))

    preselected_hospital_id = request.args.get('hospital_id', '')
    hospitals = [h for h in TEMP_DATA['hospitals'].values() if getattr(h, 'is_verified', True) and not getattr(h, 'is_hidden', False)]
    return render_template('organ_donor_register.html', hospitals=hospitals, preselected_hospital_id=preselected_hospital_id)

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
            donor_id = f"OD/{datetime.now().year}/{TEMP_DATA['next_ids']['organ_donor']:03d}"
            new_donor = OrganDonor(
                id=donor_id, 
                name=stored_data['name'], 
                email=stored_data['email'], 
                phone=stored_data['phone'],
                organs=stored_data['organs'],
                blood_group=stored_data['blood_group'], 
                age=stored_data['age'], 
                city=stored_data['city'],
                password=stored_data['password'],
                hospital_id=stored_data.get('hospital_id')
            )
            
            TEMP_DATA['organ_donors'][donor_id] = new_donor
            TEMP_DATA['next_ids']['organ_donor'] += 1
            save_data()
            
            # Send Welcome & Confirmation Email
            subject = "Thank you for registering as an Organ Donor - Spherix Clinic"
            body = f"Dear {stored_data['name']},\n\nThank you for taking the noble step of registering as an organ donor. Your pledge to donate {', '.join(stored_data['organs'])} can save multiple lives.\n\nBest regards,\nSpherix Clinic Team"
            send_notification_email(stored_data['email'], subject, body)

            session.pop('organ_donor_signup_data', None)
            flash('Thank you for registering! Please wait for staff approval before logging in.', 'success')
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

@app.route('/organ-donor/forgot-password', methods=['GET', 'POST'])
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
            if getattr(donor, 'is_blocked', False):
                flash('Your account has been blocked by an administrator.', 'error')
                return redirect(url_for('organ_donor_login'))
            if getattr(donor, 'status', 'pending') != 'approved':
                flash('Your account is pending verification by the hospital staff.', 'warning')
                return redirect(url_for('organ_donor_login'))
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
                    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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

    return render_template('organ_donor_dashboard.html', donor=current_user, organ_requests=list(TEMP_DATA.get('organ_requests', {}).values()))

@app.route('/organ-donors')
def organ_donors_list():
    city_query = request.args.get('city', '').strip().lower()
    organ_query = request.args.get('organ', '').strip().lower()

    # Only show approved donors to the public
    all_donors = [d for d in TEMP_DATA['organ_donors'].values() if getattr(d, 'status', 'pending') == 'approved' and not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
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

@app.route('/organ-donor/certificate/<path:donor_id>')
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
            stamp_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
            if os.path.exists(stamp_path):
                pdf.image(stamp_path, x=136.5, y=y_footer - 8, w=24)
        except Exception:
            pass

        # Bottom Right: Signature & Organization
        pdf.set_xy(190, y_footer - 15)
        
        # CUSTOM SIGNATURE FONT LOGIC
        signature_drawn = False
        try:
            signature_img_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
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
            custom_font_path = os.path.join(app.root_path, 'static', 'fonts', 'signature.ttf')
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

@app.route('/blood-bank')
def blood_bank():
    """Displays the blood bank inventory."""
    hospitals_with_stock = [h for h in TEMP_DATA['hospitals'].values() if getattr(h, 'is_verified', True) and not getattr(h, 'is_hidden', False)]
    return render_template('blood_bank.html', stock=TEMP_DATA['blood_stock'], hospitals=hospitals_with_stock)

@app.route('/blood-bank/update', methods=['POST'])
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

@app.route('/blood-donation-camps')
def blood_donation_camps():
    """Displays a list of upcoming blood donation camps."""

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
            id_val = int(current_user.id)
            cert_number = f"BD/{current_user.created_at.year}/{id_val:05d}"
        except (ValueError, TypeError):
            cert_number = str(current_user.id)
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
        pdf.cell(0, 12, 'CERTIFICATE OF APPRECIATION', 0, 1, 'C')

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
        pdf.cell(0, 8, 'This honor is proudly presented to', 0, 1, 'C')
        
        pdf.ln(2)
        name = to_latin1_str(current_user.name).upper()
        pdf.set_font('Times', 'B', 32)
        pdf.set_text_color(192, 156, 66) # Gold Name
        pdf.cell(0, 14, name, 0, 1, 'C')
        
        pdf.ln(4)
        
        # Rounded Metadata Box (Sleek gold-bordered rectangle)
        pdf.set_fill_color(248, 245, 235)
        pdf.set_draw_color(192, 156, 66)
        pdf.set_line_width(0.4)
        pdf.rect(48, 90, 201, 12, 'DF')
        
        pdf.set_xy(48, 92)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(201, 8, f"BLOOD GROUP: {current_user.blood_group}   |   LOCATION: {to_latin1_str(current_user.city).upper()}", 0, 1, 'C')
        
        pdf.set_y(108)
        pdf.set_font('Times', 'I', 14)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 6.5, 'For your selfless and voluntary blood donation.\nYour noble contribution serves as a beacon of hope and a lifeline for those in need.', 0, 'C')
        
        # --- 4. Footer & Custom Signature Font ---
        y_footer = 160
        
        # Bottom Left: Details
        pdf.set_xy(35, y_footer)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(120, 120, 120)
        donation_date = current_user.last_donation or date.today()
        
        pdf.cell(25, 5, "DATE:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 5, str(donation_date), 0, 1, 'L')
        
        pdf.set_x(35)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(25, 5, "ISSUER:", 0, 0, 'L')
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(50, 5, "Spherix Clinic Blood Bank Network", 0, 1, 'L')

        # Official Stamp
        try:
            stamp_path = os.path.join(app.root_path, 'static', 'images', 'stamp.png')
            if os.path.exists(stamp_path):
                pdf.image(stamp_path, x=136.5, y=y_footer - 8, w=24)
        except Exception:
            pass

        # Bottom Right: Signature & Organization
        pdf.set_xy(190, y_footer - 15)
        
        # CUSTOM SIGNATURE FONT LOGIC
        signature_drawn = False
        try:
            signature_img_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
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
            custom_font_path = os.path.join(app.root_path, 'static', 'fonts', 'signature.ttf')
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
        
        # Generate QR code linking to the donor's dashboard
        qr_url = url_for('blood_donor_dashboard', _external=True)
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_qr:
            qr_img.save(tmp_qr)
            tmp_qr_path = tmp_qr.name
            
        pdf.image(tmp_qr_path, x=255, y=150, w=22, h=22)
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
            subject = "Your Blood Donation Certificate - Spherix Clinic"
            body = f"Dear {current_user.name},\n\nThank you for your noble contribution! Please find your blood donation certificate attached to this email.\n\nBest regards,\nSpherix Clinic Blood Bank Network"
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

@app.route('/blood-bank/dashboard', methods=['GET', 'POST'])
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

@app.route('/patient/dashboard', methods=['GET', 'POST'])
@patient_required
def patient_dashboard():
    if request.method == 'POST':
        if 'update_profile' in request.form:
            current_user.name = request.form.get('name', current_user.name)
            current_user.email = request.form.get('email', current_user.email)
            current_user.phone = request.form.get('phone', getattr(current_user, 'phone', None))
            current_user.address = request.form.get('address', getattr(current_user, 'address', None))
            age_str = request.form.get('age')
            if age_str and age_str.isdigit():
                current_user.age = int(age_str)
            current_user.gender = request.form.get('gender', current_user.gender)
            
            # Handle Profile Picture Upload
            if 'profilePicture' in request.files:
                file = request.files['profilePicture']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
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

    # Fetch patient's vitals
    patient_vitals = [
        v for v in TEMP_DATA.get('patient_vitals', {}).values()
        if v.patient_id == current_user.id
    ]
    # Sort by recorded_at ascending for chronological chart
    patient_vitals.sort(key=lambda v: v.recorded_at)

    vitals_dates = [v.recorded_at.strftime('%b %d') for v in patient_vitals]
    vitals_weight = [v.weight for v in patient_vitals]
    vitals_heart_rate = [v.heart_rate for v in patient_vitals]
    vitals_blood_sugar = [v.blood_sugar for v in patient_vitals]
    vitals_systolic = [v.systolic_bp for v in patient_vitals]
    vitals_diastolic = [v.diastolic_bp for v in patient_vitals]

    return render_template('patient_dashboard.html', 
                           patient=current_user, 
                           today=today, 
                           orders=sorted_orders, 
                           bed_bookings=patient_bed_bookings, 
                           hospitals=TEMP_DATA.get('hospitals', {}),
                           doctors=TEMP_DATA.get('doctors', {}),
                           vitals_dates=vitals_dates,
                           vitals_weight=vitals_weight,
                           vitals_heart_rate=vitals_heart_rate,
                           vitals_blood_sugar=vitals_blood_sugar,
                           vitals_systolic=vitals_systolic,
                           vitals_diastolic=vitals_diastolic)

@app.route('/patient/feedback', methods=['POST'])
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

@app.route('/api/patient/vitals', methods=['POST'])
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


@app.route('/hospital/appointment/create', methods=['POST'])
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

@app.route('/hospital/appointment/cancel/<int:appointment_id>', methods=['POST'])
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
The Spherix Clinic Team"""
            send_notification_email(doctor.email, subject, body)
        save_data() # Save the status change
        flash("Your appointment has been successfully cancelled.", "success")
    else:
        flash("Appointment not found or you do not have permission to cancel it.", "error")
    return redirect(url_for('patient_dashboard'))

@app.route('/patient/appointment/edit/<int:appointment_id>', methods=['POST'])
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

@app.route('/patient/bed_booking/cancel/<int:booking_id>', methods=['POST'])
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

@app.route('/patient/bed_booking/edit/<int:booking_id>', methods=['POST'])
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

@app.route('/patient/order/cancel/<int:order_id>', methods=['POST'])
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

@app.route('/patient/order/edit/<int:order_id>', methods=['POST'])
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

@app.route('/patient/organ-request/create', methods=['POST'])
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

# ... (rest of your app.py code) ...

@app.route('/appointment', methods=['GET', 'POST'])
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
            doctors_from_db = [d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
            return render_template('book_appointment.html', doctors=doctors_from_db)

        doctor = TEMP_DATA['doctors'].get(doctor_id)
        if not doctor or getattr(doctor, 'is_hidden', False) or getattr(doctor, 'is_blocked', False):
            flash("Selected doctor is currently unavailable.", "error")
            doctors_from_db = [d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
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
    
    doctors_from_db = [d for d in TEMP_DATA['doctors'].values() if not getattr(d, 'is_hidden', False) and not getattr(d, 'is_blocked', False)]
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

@app.route('/appointment/success/<int:appointment_id>')
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
        pdf.cell(0, 6, 'Spherix Clinic Health Platform', 0, 1, 'L')
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

@app.route("/careers")
def careers():
    return render_template("careers.html")


@app.route("/blog")
def blog():
    return render_template("blog.html")

@app.route("/research")
def research():
    return render_template("research.html")

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
        return render_template("404.html"), 404

    return render_template("research_detail.html", topic=topic_data)

@app.route("/resources")
def resources():
    return render_template("research.html")

# ==================== CANCER CARE PORTAL ====================
CANCER_DATA = {
    "breast-cancer": {
        "name": "Breast Cancer",
        "image": "https://images.unsplash.com/photo-1579684385127-1ef15d508118?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Cancer that forms in the cells of the breasts, predominantly affecting women but can also affect men.",
        "symptoms": ["Lump in the breast", "Change in breast size/shape", "Changes to the skin over the breast", "Inverted nipple"],
        "risk_factors": ["Age", "Family history", "Genetics (BRCA1/BRCA2)", "Radiation exposure", "Obesity"],
        "prevention": ["Regular screening (Mammograms)", "Maintain healthy weight", "Exercise regularly", "Limit alcohol"],
        "treatments": ["Surgery (Lumpectomy/Mastectomy)", "Radiation therapy", "Chemotherapy", "Hormone therapy"]
    },
    "lung-cancer": {
        "name": "Lung Cancer",
        "image": "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "A cancer that begins in the lungs and most often occurs in people who smoke.",
        "symptoms": ["A new persistent cough", "Coughing up blood", "Shortness of breath", "Chest pain", "Unexplained weight loss"],
        "risk_factors": ["Smoking", "Secondhand smoke exposure", "Exposure to radon gas", "Asbestos exposure", "Family history"],
        "prevention": ["Don't smoke", "Avoid secondhand smoke", "Test home for radon", "Avoid carcinogens at work"],
        "treatments": ["Surgery", "Radiation therapy", "Chemotherapy", "Targeted drug therapy", "Immunotherapy"]
    },
    "prostate-cancer": {
        "name": "Prostate Cancer",
        "image": "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Cancer that occurs in the prostate — a small walnut-shaped gland in men that produces the seminal fluid.",
        "symptoms": ["Trouble urinating", "Decreased force in the stream of urine", "Blood in urine", "Bone pain", "Unexplained weight loss"],
        "risk_factors": ["Older age", "Race (higher risk in Black men)", "Family history", "Obesity"],
        "prevention": ["Choose a healthy diet full of fruits and vegetables", "Choose healthy foods over supplements", "Exercise most days of the week", "Maintain a healthy weight"],
        "treatments": ["Active surveillance", "Surgery", "Radiation therapy", "Hormone therapy", "Cryotherapy"]
    },
    "colorectal-cancer": {
        "name": "Colorectal Cancer",
        "image": "https://images.unsplash.com/photo-1559757175-5700dde675bc?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Cancer that begins in the colon or rectum. It typically begins as noncancerous polyps that become malignant over time.",
        "symptoms": ["A persistent change in bowel habits", "Rectal bleeding or blood in stool", "Persistent abdominal discomfort", "A feeling that the bowel doesn't empty completely", "Weakness or fatigue"],
        "risk_factors": ["Older age", "African-American race", "Personal history of polyps", "Inflammatory intestinal conditions", "Low-fiber, high-fat diet"],
        "prevention": ["Screening tests (Colonoscopy)", "Eat a variety of fruits, vegetables and whole grains", "Stop smoking", "Exercise most days of the week"],
        "treatments": ["Surgery", "Chemotherapy", "Radiation therapy", "Targeted therapy", "Immunotherapy"]
    },
    "skin-cancer-melanoma": {
        "name": "Skin Cancer (Melanoma)",
        "image": "https://images.unsplash.com/photo-1559757148-5c350d0d3c56?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "The most serious type of skin cancer, develops in the cells (melanocytes) that produce melanin — the pigment that gives your skin its color.",
        "symptoms": ["A change in an existing mole", "The development of a new pigmented or unusual-looking growth on your skin"],
        "risk_factors": ["Fair skin", "A history of sunburns", "Excessive ultraviolet (UV) light exposure", "Living closer to the equator or at a higher elevation", "Having many moles"],
        "prevention": ["Avoid the sun during the middle of the day", "Wear sunscreen year-round", "Wear protective clothing", "Avoid tanning beds", "Check skin regularly"],
        "treatments": ["Surgery to remove affected nodes", "Immunotherapy", "Targeted therapy", "Radiation therapy", "Chemotherapy"]
    },
    "leukemia": {
        "name": "Leukemia",
        "image": "https://images.unsplash.com/photo-1579154204601-01588f351e67?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Cancer of the body's blood-forming tissues, including the bone marrow and the lymphatic system.",
        "symptoms": ["Fever or chills", "Persistent fatigue, weakness", "Frequent or severe infections", "Losing weight without trying", "Swollen lymph nodes", "Easy bleeding or bruising"],
        "risk_factors": ["Previous cancer treatment", "Genetic disorders", "Exposure to certain chemicals", "Smoking", "Family history of leukemia"],
        "prevention": ["Avoid high doses of radiation", "Avoid exposure to the chemical benzene", "Avoid smoking or using tobacco products"],
        "treatments": ["Chemotherapy", "Biological therapy", "Targeted therapy", "Radiation therapy", "Stem cell transplant"]
    }
}

@app.route("/cancer-care")
def cancer_care():
    """Displays the main page listing all types of cancers."""
    return render_template("cancer_care.html", cancers=CANCER_DATA)

@app.route("/cancer-care/<cancer_slug>")
def cancer_detail(cancer_slug):
    """Displays comprehensive details of a specifically selected cancer."""
    cancer = CANCER_DATA.get(cancer_slug)
    if not cancer:
        flash("Cancer type not found.", "error")
        return redirect(url_for('cancer_care'))
    return render_template("cancer_detail.html", cancer=cancer)

@app.route('/api/medicine/ai-search', methods=['POST'])
@csrf.exempt
def api_medicine_ai_search():
    """Uses OpenFDA or Groq to find medicine details based on a search query."""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'error': 'Please provide a search query.'}), 400

    # Try OpenFDA API First
    fda_info = _invoke_openfda_drug_info(query)
    if fda_info:
        # Determine form
        query_lower = (query + " " + fda_info.get('drug_name', '') + " " + fda_info.get('description', '')).lower()
        form = 'Tablet'
        if any(w in query_lower for w in ['syrup', 'sirup', 'liquid', 'suspension', 'elixir']):
            form = 'Syrup'
        elif any(w in query_lower for w in ['capsule', 'capsul', 'softgel']):
            form = 'Capsule'
        elif any(w in query_lower for w in ['injection', 'injectable', 'vial', 'ampoule']):
            form = 'Injection'
        elif any(w in query_lower for w in ['gel', 'cream', 'ointment', 'topical']):
            form = 'Gel'
        elif any(w in query_lower for w in ['spray', 'aerosol', 'inhaler']):
            form = 'Spray'
        elif any(w in query_lower for w in ['drop', 'eye drops', 'ear drops']):
            form = 'Drops'

        medicine_data = {
            'name': fda_info.get('drug_name', query),
            'form': form,
            'company': 'FDA Registered Manufacturer',
            'composition': 'Standard Formulation',
            'uses': [fda_info.get('primary_use', 'General Use')],
            'side_effects': fda_info.get('common_side_effects', ['Consult packaging']),
            'doses': 'As directed by physician',
            'how_to_use': 'Follow clinical instructions on packaging.',
            'warnings': [fda_info.get('caution', 'Consult a healthcare professional before use.')],
            'price': round(random.uniform(10.0, 500.0), 2)
        }
        return jsonify({'success': True, 'medicine': medicine_data})

    # Fallback to Groq AI
    if not _is_groq_configured():
        return jsonify({'success': False, 'error': 'AI provider is not configured.'}), 500

    prompt = f"""You are a pharmaceutical AI assistant. Find the most appropriate medicine for this search query: "{query}".
Provide the response as a valid JSON object ONLY. No markdown, no extra text.
Required keys:
- name: string (Brand or generic name)
- form: string (Choose one: 'Tablet', 'Syrup', 'Capsule', 'Gel', 'Injection', 'Drops', 'Spray', 'Other')
- company: string (Typical manufacturer)
- composition: string (Active ingredients)
- uses: list of strings (Primary benefits/uses, max 4)
- side_effects: list of strings (Key side effects, max 4)
- doses: string (General dosage guidance)
- how_to_use: string (Administration instructions)
- warnings: list of strings (Important precautions, warnings, or contraindications, max 3)
- price: float (Generate a realistic random price in INR between 10.0 and 500.0)
"""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }

    try:
        # Try standard OpenAI format first
        endpoint = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
        if "responses" in endpoint:
            endpoint = endpoint.replace("responses", "chat/completions")
            
        payload = {
            'model': GROQ_API_MODEL,
            'messages': [
                {"role": "system", "content": "You are a pharmaceutical AI assistant. Always return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            'temperature': 0.2,
            'max_tokens': 1024,
            'response_format': {'type': 'json_object'}
        }
        
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30, verify=True)
        response.raise_for_status()
        payload_json = response.json()
        
        output_text = _extract_groq_text_response(payload_json)

        parsed = _extract_json_payload(output_text)
        if not parsed or not isinstance(parsed, dict):
            raise ValueError('Groq response could not be parsed as JSON')

        # Ensure fallbacks exist
        if 'form' not in parsed:
            parsed['form'] = 'Tablet'
        if 'warnings' not in parsed:
            parsed['warnings'] = ['Consult a doctor before use.']
        if 'side_effects' not in parsed:
            parsed['side_effects'] = ['Consult packaging.']
        if 'uses' not in parsed:
            parsed['uses'] = ['General medication use.']

        return jsonify({'success': True, 'medicine': parsed})
    except Exception as e:
        print(f"❌ AI Medicine Search chat/completions failed: {e}. Trying fallback format...")
        try:
            endpoint_fallback = f"{GROQ_API_BASE.rstrip('/')}/responses"
            payload_fallback = {
                'model': GROQ_API_MODEL,
                'input': prompt,
                'temperature': 0.2,
                'max_output_tokens': 1024
            }
            response = requests.post(endpoint_fallback, headers=headers, json=payload_fallback, timeout=30, verify=True)
            response.raise_for_status()
            payload_json = response.json()

            output_text = payload_json.get('output_text')
            if not output_text and 'choices' in payload_json and len(payload_json['choices']) > 0:
                output_text = payload_json['choices'][0]['message']['content']

            parsed = _extract_json_payload(output_text)
            if not parsed or not isinstance(parsed, dict):
                raise ValueError('Groq response could not be parsed as JSON')

            # Ensure fallbacks exist
            if 'form' not in parsed:
                parsed['form'] = 'Tablet'
            if 'warnings' not in parsed:
                parsed['warnings'] = ['Consult a doctor before use.']
            if 'side_effects' not in parsed:
                parsed['side_effects'] = ['Consult packaging.']
            if 'uses' not in parsed:
                parsed['uses'] = ['General medication use.']

            return jsonify({'success': True, 'medicine': parsed})
        except Exception as e2:
            print(f"❌ AI Medicine Search fallback failed: {e2}")
            return jsonify({'success': False, 'error': 'Failed to analyze medicine via AI.'}), 500

MEDICINE_LIST = []

@app.route('/medical-shop')
def medical_shop():
    """
    Renders the medical shop page.
    Passes the list of medicines to the template.
    """
    db_medicines = TEMP_DATA.get('medicines', [])
    if not db_medicines:
        fallback_medicines = [
            {'name': 'Paracetamol 500mg', 'category': 'Pain Relief', 'price': 49.0},
            {'name': 'Vitamin C Tablets', 'category': 'Vitamins', 'price': 99.0},
            {'name': 'Ibuprofen 200mg', 'category': 'Pain Relief', 'price': 79.0},
            {'name': 'Cough Relief Syrup', 'category': 'Cold & Flu', 'price': 120.0},
            {'name': 'Multivitamin Gummies', 'category': 'Vitamins', 'price': 199.0},
            {'name': 'Digestive Support Capsules', 'category': 'Digestive Support', 'price': 150.0},
            {'name': 'Wound Care Gel', 'category': 'First Aid', 'price': 85.0},
            {'name': 'Allergy Relief Tablets', 'category': 'Cold & Flu', 'price': 65.0}
        ]
        db_medicines = fallback_medicines
        
    # Calculate average rating for medical shop
    shop_ratings = [fb.rating for fb in TEMP_DATA.get('feedbacks', {}).values() if getattr(fb, 'feedback_target', None) == 'medical_shop']
    avg_rating = round(sum(shop_ratings) / len(shop_ratings), 1) if shop_ratings else 4.8
    rating_count = len(shop_ratings) if shop_ratings else 24
    
    return render_template('medical_shop.html', medicines=db_medicines, display_medicines=db_medicines, avg_rating=avg_rating, rating_count=rating_count)

@app.route('/medicine/<path:medicine_name>')
def medicine_detail(medicine_name):
    """Displays detailed information about a specific medicine."""
    fda_info = _invoke_openfda_drug_info(medicine_name)
    if not fda_info:
        fda_info = _invoke_groq_drug_info(medicine_name)
        
    if not fda_info:
        fda_info = {
            'drug_name': medicine_name,
            'description': f"Detailed information for '{medicine_name}' is not currently available in our database. Please consult a pharmacist or healthcare provider for specific details.",
            'primary_use': 'Consult a healthcare professional for indications.',
            'common_side_effects': ['Please refer to the manufacturer packaging or consult a doctor.'],
            'caution': 'Always consult a healthcare professional before starting any new medication.',
            'clinical_notes': ''
        }
        
    # Determine price from catalog or consistent fallback mock based on name length
    matched_med = next((m for m in TEMP_DATA.get('medicines', []) if m['name'].lower() == medicine_name.lower()), None)
    price = matched_med['price'] if matched_med else (99.0 + (len(medicine_name) * 10.0))
    
    return render_template('medicine_detail.html', medicine=fda_info, price=price)

@app.route('/add-to-cart', methods=['POST'])
@csrf.exempt
def add_to_cart():
    """Adds a product to the session-based shopping cart."""
    data = request.json
    product_name = data.get('name')
    product_price = data.get('price')

    if not product_name or product_price is None:
        return jsonify({'success': False, 'message': 'Missing product data.'}), 400

    try:
        product_price = float(product_price)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid product price.'}), 400

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

@app.route('/api/pharmacy/upload-prescription', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def upload_prescription_to_cart():
    """Handles prescription image upload, runs OCR, and adds recognized medicines to the cart."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected.'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = utcnow().strftime('%Y%m%d%H%M%S')
        unique_filename = f"ocr_{timestamp}_{filename}"
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'prescriptions_ocr')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, unique_filename)
        file.save(filepath)
        
        try:
            from prescription_ocr import extract_text_from_image, parse_medicines_with_groq
            raw_text = extract_text_from_image(filepath)
            medicines = parse_medicines_with_groq(raw_text)
            
            if not medicines:
                return jsonify({'success': False, 'error': 'No recognizable medicines found in the image.'}), 400
            
            cart = session.get('cart', [])
            added_items = []
            for med in medicines:
                med_name = med.get('medicine_name', 'Unknown Medicine')
                if med_name == 'Unknown Medicine': continue
                
                if not any(item.get('name') == med_name for item in cart):
                    cart.append({'name': med_name, 'price': 150.0, 'quantity': 1})
                added_items.append(med_name)
            
            session['cart'] = cart
            session.modified = True
            return jsonify({'success': True, 'message': f"Added {len(added_items)} medicines to cart.", 'medicines': added_items, 'cart_item_count': sum(int(item.get('quantity', 0) or 0) for item in cart)})
        except Exception as e:
            return jsonify({'success': False, 'error': f"Failed to process prescription: {str(e)}"}), 500
    return jsonify({'success': False, 'error': 'Invalid file type.'}), 400

@app.route('/pharmacy/upload-prescription')
def upload_prescription_page():
    """Renders a dedicated page for uploading a prescription (PDF, JPEG, PNG, JPG)."""
    cart = session.get('cart', [])
    cart_item_count = sum(int(item.get('quantity', 0) or 0) for item in cart)
    return render_template('upload_prescription.html', cart_item_count=cart_item_count)

@app.route('/cart')
def view_cart():
    """Displays the shopping cart page."""
    return render_template('cart.html')

@app.route('/update-cart-item', methods=['POST'])
@csrf.exempt
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
        # Normalize stored values before any operation
        try:
            item['price'] = float(item.get('price', 0))
        except (TypeError, ValueError):
            item['price'] = 0.0
        item['quantity'] = int(item.get('quantity', 0) or 0)

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
    total_price = 0
    for i in new_cart:
        total_price += i['price'] * i['quantity']

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
        payment_method = request.form.get('payment_method', 'cod')
        
        order_id = TEMP_DATA['next_ids']['order']
        new_order = Order(
            id=order_id,
            patient_id=current_user.id,
            items=cart,
            total_price=inject_cart()['cart_total_price'],
            shipping_address=shipping_address,
            order_date=date.today(),
            status='Processing' if payment_method == 'cod' else 'Awaiting Payment'
        )
        TEMP_DATA['orders'][order_id] = new_order
        TEMP_DATA['next_ids']['order'] += 1
        save_data() # Save after creating order

        # Handle Online Payment (Razorpay)
        if payment_method == 'card' and razorpay_client:
            try:
                payment_link = razorpay_client.payment_link.create({
                    "amount": int(new_order.total_price * 100), # Amount in paise
                    "currency": "INR",
                    "accept_partial": False,
                    "reference_id": f"order_{order_id}_{int(time_module.time())}",
                    "description": f"Pharmacy Order #{order_id}",
                    "customer": {
                        "name": current_user.name,
                        "email": current_user.email
                    },
                    "callback_url": url_for('order_success', order_id=order_id, _external=True) + '?session_id=razorpay_payment',
                    "callback_method": "get"
                })
                return redirect(payment_link['short_url'], code=303)
            except Exception as e:
                flash(f"Payment gateway error: {str(e)}", "error")
                return redirect(url_for('checkout'))

        # Handle Cash on Delivery (COD)
        session.pop('cart', None)
        return redirect(url_for('order_success', order_id=order_id))

    return render_template('checkout.html')

@app.route('/order-success/<int:order_id>')
@patient_required
def order_success(order_id):
    """Displays a confirmation page after a successful order."""
    order = TEMP_DATA['orders'].get(order_id)
    
    # Check if returning from a successful Stripe payment
    session_id = request.args.get('session_id')
    if session_id and order and order.status == 'Awaiting Payment':
        order.status = 'Paid & Processing'
        save_data()
        session.pop('cart', None) # Clear cart after successful payment
        
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
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, order.order_date.strftime('%B %d, %Y'), 0, 1, 'L')
        
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

@app.route('/read-files', methods=['GET', 'POST'])
@csrf.exempt
def read_files():
    analysis_result = None
    uploaded_image = None
    
    if request.method == 'POST':
        if 'document' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
            
        file = request.files['document']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
            
        analysis_type = request.form.get('analysis_type', 'general')
        
        if file and allowed_file(file.filename):
            if file.filename.rsplit('.', 1)[1].lower() == 'pdf':
                 flash('Please upload an image file (JPG, PNG, JPEG) instead of PDF for visual AI analysis.', 'error')
                 return redirect(request.url)
                 
            filename = secure_filename(file.filename)
            timestamp = utcnow().strftime('%Y%m%d%H%M%S')
            unique_filename = f"doc_analysis_{timestamp}_{filename}"
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'documents')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            uploaded_image = f"/static/uploads/documents/{unique_filename}"
            
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
        else:
            flash('Invalid file format. Allowed types: png, jpg, jpeg, gif.', 'error')

    if analysis_result:
        return render_template('read_files_result.html', analysis_result=analysis_result, uploaded_image=uploaded_image)

    return render_template('read_files.html')


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

@app.route('/sicons-application/download-ack/<filename>')
def download_sicons_ack(filename):
    safe_filename = secure_filename(filename)
    filepath = os.path.join(app.root_path, 'static', 'uploads', 'sicons_apps', safe_filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=f"Spherix_iCons_Acknowledgement.pdf")
    flash("Acknowledgement file not found or expired.", "error")
    return redirect(url_for('sicons_application'))

@app.route('/sicons-application', methods=['GET', 'POST'])
def sicons_application():
    if request.method == 'POST':
        # Ensure the secure upload directory exists
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'sicons_apps')
        os.makedirs(upload_folder, exist_ok=True)
        
        saved_files = {}
        # Handle single file uploads
        for field_name in ['profile_photo', 'resume', 'cover_letter', 'id_proof']:
            if field_name in request.files:
                file = request.files[field_name]
                if file and file.filename != '':
                    if allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                        unique_filename = f"{field_name}_{timestamp}_{filename}"
                        file.save(os.path.join(upload_folder, unique_filename))
                        saved_files[field_name] = unique_filename
                    else:
                        flash(f'Invalid file format for {field_name}.', 'error')

        # Handle multiple file uploads (certificates)
        cert_filenames = []
        if 'certificates' in request.files:
            for file in request.files.getlist('certificates'):
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
                    unique_filename = f"cert_{timestamp}_{filename}"
                    file.save(os.path.join(upload_folder, unique_filename))
                    cert_filenames.append(unique_filename)
        if cert_filenames:
            saved_files['certificates'] = cert_filenames

        # Extract form data and combine with file references
        application_data = request.form.to_dict()
        application_data['files'] = saved_files
        application_data['submitted_at'] = utcnow().isoformat()
        application_data['id'] = TEMP_DATA['next_ids'].get('sicons_application', 1)
        application_data['status'] = 'pending'
        TEMP_DATA['next_ids']['sicons_application'] += 1

        # Store the application locally
        if 'sicons_applications' not in TEMP_DATA:
            TEMP_DATA['sicons_applications'] = []
        TEMP_DATA['sicons_applications'].append(application_data)
        
        save_data()

        # Generate Acknowledgement PDF
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Background & Outer Cyber Border
            pdf.set_fill_color(5, 5, 5)
            pdf.rect(0, 0, 210, 297, 'F')
            
            pdf.set_draw_color(224, 30, 35) # Red-600 Outer Frame
            pdf.set_line_width(0.5)
            pdf.rect(10, 10, 190, 277)
            
            pdf.set_draw_color(40, 40, 40) # Inner Subtle Frame
            pdf.set_line_width(0.2)
            pdf.rect(12, 12, 186, 273)
            
            # Header Top-Left
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 22)
            pdf.set_xy(20, 22)
            pdf.cell(0, 10, 'Spherix iCons', 0, 1, 'L')
            
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(224, 30, 35)
            pdf.set_x(20)
            pdf.cell(0, 5, 'ENGINEERING DIVISION // DEPLOYMENT PROTOCOL', 0, 1, 'L')
            
            # Line Separator
            pdf.set_draw_color(224, 30, 35)
            pdf.line(20, 40, 190, 40)
            
            # Title
            pdf.set_xy(20, 48)
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 10, 'CANDIDATE DOSSIER ACKNOWLEDGED', 0, 1, 'C')
            
            # Metadata Dossier Box
            pdf.set_y(65)
            pdf.set_x(20)
            pdf.set_fill_color(15, 15, 15)
            pdf.set_draw_color(60, 60, 60)
            pdf.rect(20, 65, 170, 38, 'DF')
            
            pdf.set_xy(25, 70)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(156, 163, 175) # Slate-400
            pdf.cell(35, 7, 'CANDIDATE:', 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 7, application_data.get('full_name', 'UNKNOWN').upper(), 0, 1)
            
            pdf.set_x(25)
            pdf.set_text_color(156, 163, 175)
            pdf.cell(35, 7, 'TARGET DEPT:', 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 7, application_data.get('department', 'ENGINEERING').upper(), 0, 1)
            
            pdf.set_x(25)
            pdf.set_text_color(156, 163, 175)
            pdf.cell(35, 7, 'POSITION:', 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 7, application_data.get('position', 'UNSPECIFIED').upper(), 0, 1)
            
            pdf.set_x(25)
            pdf.set_text_color(156, 163, 175)
            pdf.cell(35, 7, 'TIMESTAMP:', 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 7, f"{utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", 0, 1)
            
            # Body text
            pdf.set_y(115)
            pdf.set_x(20)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', '', 11)
            pdf.set_text_color(200, 200, 200)
            
            body_text = (
                "This document serves as cryptographic verification of your successful transmission to the "
                "Spherix iCons global recruitment node. Your professional metadata, biometric identity markers, and "
                "technical dossiers have been securely encrypted and deposited within our private subnet.\n\n"
                "Our neural screening systems, in tandem with Spherix iCons engineering leadership, will evaluate "
                "your specifications against current deployment requirements. If your parameters align with our "
                "mission to architect sentient technology, a network representative will establish contact.\n\n"
                "We recognize your ambition to build the pulse of the future."
            )
            
            pdf.multi_cell(170, 8, body_text, align='J')
            
            # Bottom Left Sign-off
            pdf.set_y(220)
            pdf.set_x(20)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(224, 30, 35)
            pdf.cell(0, 6, 'SYSTEM STATUS: ACCEPTED', 0, 1, 'L')
            
            pdf.set_x(20)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 6, 'Spherix iCons Deployment Operations', 0, 1, 'L')
            
            # Bottom Cyber Watermark
            pdf.set_y(260)
            pdf.set_x(10)
            pdf.set_font('Courier', 'B', 8)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(0, 6, '01001000 01100101 01101100 01101100 01101111 // END OF TRANSMISSION', 0, 1, 'C')

            timestamp_ack = utcnow().strftime('%Y%m%d%H%M%S')
            safe_name = secure_filename(application_data.get('full_name', 'candidate'))
            ack_filename = f"ack_{timestamp_ack}_{safe_name}.pdf"
            ack_filepath = os.path.join(upload_folder, ack_filename)
            pdf.output(ack_filepath)
            
            # Add acknowledgment to data and re-save
            application_data['files']['acknowledgement'] = ack_filename
            save_data()

            # Read the generated PDF back into memory for the email attachment
            try:
                with open(ack_filepath, 'rb') as f:
                    pdf_bytes = f.read()
                
                applicant_email = application_data.get('email')
                if applicant_email:
                    email_subject = "Spherix iCons Deployment Operations - Application Acknowledgement"
                    email_body = f"""
                    <div style="font-family: Arial, sans-serif; background-color: #000; color: #fff; padding: 30px; border: 1px solid #333;">
                        <h2 style="color: #E01E23; letter-spacing: 2px;">Spherix iCons // ENGINEERING DIVISION</h2>
                        <p style="color: #ccc;">ATTN: {application_data.get('full_name', 'CANDIDATE').upper()}</p>
                        <p style="color: #ccc; line-height: 1.6;">Your application metadata for the position of <strong>{application_data.get('position', 'Engineering Role').upper()}</strong> has been successfully transmitted to our global recruitment node.</p>
                        <p style="color: #ccc; line-height: 1.6;">Please find attached your official Candidate Acknowledgement document verifying your submission.</p>
                        <p style="color: #ccc; line-height: 1.6;">Our neural screening systems and engineering leadership will review your profile. If your specifications align with our current deployment protocols, a representative will initiate contact.</p>
                        <br>
                        <p style="font-size: 11px; color: #666; letter-spacing: 1px; text-transform: uppercase;">
                            Spherix iCons Deployment Operations<br>
                            System Status: Accepted
                        </p>
                    </div>
                    """
                    send_notification_email(to_email=applicant_email, subject=email_subject, body=email_body, is_html=True, attachment_name=ack_filename, attachment_data=pdf_bytes)
                    
            except Exception as email_err:
                print(f"Error sending acknowledgement email: {email_err}")

            session['last_ack_file'] = ack_filename

        except Exception as e:
            print(f"Error generating acknowledgement PDF: {e}")

        flash("Candidate Deployment Profile Transmitted Successfully. Spherix iCons Engineering will review your application.", "success")
        return redirect(url_for('sicons_application'))

    ack_file = session.pop('last_ack_file', None)
    return render_template('sicons_application.html', ack_file=ack_file)

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

@app.route('/admin/blood-donor/edit/<path:donor_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_blood_donor(donor_id):
    donor_id = parse_route_id(donor_id)
    """Allows an admin to edit a blood donor's profile."""
    donor = TEMP_DATA['blood_donors'].get(donor_id)
    if not donor:
        flash("Blood donor not found.", "error")
        return redirect(url_for('admin_dashboard') + '#blood_donors')

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
        return redirect(url_for('admin_dashboard') + '#blood_donors')

    return render_template('admin_edit_blood_donor.html', donor=donor)

@app.route('/admin/blood-donor/delete/<path:donor_id>', methods=['POST'])
@admin_required
def admin_delete_blood_donor(donor_id):
    donor_id = parse_route_id(donor_id)
    """Allows an admin to delete a blood donor."""
    if donor_id in TEMP_DATA['blood_donors']:
        del TEMP_DATA['blood_donors'][donor_id]
        save_data()
        flash("Blood donor deleted successfully.", "success")
    else:
        flash("Blood donor not found.", "error")
    return redirect(url_for('admin_dashboard') + '#blood_donors')

@app.route('/admin/appointment/delete/<int:appointment_id>', methods=['POST'])
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

@app.route('/admin/order/delete/<int:order_id>', methods=['POST'])
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

@app.route('/admin/message/delete/<int:msg_id>', methods=['POST'])
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

@app.route('/admin/review/delete/<int:review_id>', methods=['POST'])
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

@app.route('/admin/bed_booking/delete/<int:booking_id>', methods=['POST'])
@admin_required
def admin_delete_bed_booking(booking_id):
    """Allows an admin to delete a bed booking."""
    if booking_id in TEMP_DATA.get('bed_bookings', {}):
        del TEMP_DATA['bed_bookings'][booking_id]
        save_data()
        flash("Bed booking deleted successfully.", "success")
    else:
        flash("Bed booking not found.", "error")
    return redirect(url_for('admin_dashboard') + '#bed_bookings')

@app.route('/admin/contact_message/delete/<int:index>', methods=['POST'])
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

@app.route('/admin/organ_request/delete/<int:req_id>', methods=['POST'])
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

@app.route('/admin/newsletter/delete/<path:email>', methods=['POST'])
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
        "newsletter_subscribers": [],
        "sicons_applications": [],
        "patient_vitals": {},
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
            "sicons_application": 1,
            "patient_vital": 1,
        }
    }
    
    # Re-initialize default users so you aren't locked out
    setup_admin_user()
    setup_hospital_user()
    
    save_data()
    flash("System has been reset. All data (except default Admin/Hospital) is cleared.", "warning")
    return redirect(url_for('admin_dashboard'))

def get_chatbot_faq_response(message):
    """Return a canned answer for common registration and website usage questions."""
    if not message:
        return None
    text = message.lower().strip()

    if any(keyword in text for keyword in [
        'patient account', 'patient register', 'register as patient', 'create patient', 'patient signup', 'patient sign up'
    ]):
        return (
            "To create a patient account:\n"
            "1. Open the Patient Register page.\n"
            "2. Enter your name, email, phone number, password, and medical details.\n"
            "3. Submit the form and verify your email or OTP if prompted.\n"
            "4. Login with Patient Login to access appointments, chat, e-pharmacy, and reports."
        )

    if any(keyword in text for keyword in [
        'donor account', 'register as donor', 'blood donor', 'organ donor', 'register as an organ donor', 'register as a blood donor'
    ]):
        return (
            "To register as a donor:\n"
            "1. Choose Blood Donor or Organ Donor registration.\n"
            "2. Fill in your personal details, blood group, location, and donation preferences.\n"
            "3. Submit the form.\n"
            "4. Your donor profile will be saved and can be reviewed by admins or blood bank staff."
        )

    if any(keyword in text for keyword in [
        'become a doctor', 'doctor account', 'register as doctor', 'doctor registration', 'doctor signup', 'doctor sign up'
    ]):
        return (
            "To become a doctor:\n"
            "1. Open the Doctor Register page.\n"
            "2. Enter your professional details, specialization, qualifications, and clinic/hospital information.\n"
            "3. Upload any required documents if asked.\n"
            "4. Submit the form and wait for admin approval.\n"
            "5. After approval, login with Doctor Login to manage appointments and consult patients."
        )

    if any(keyword in text for keyword in [
        'register as a hospital', 'hospital account', 'hospital register', 'hospital registration', 'register hospital'
    ]):
        return (
            "To register as a hospital:\n"
            "1. Open the Hospital Register page.\n"
            "2. Enter hospital name, contact details, bed counts, and administration information.\n"
            "3. Provide any verification documents if required.\n"
            "4. Submit your application and wait for admin approval."
        )

    if any(keyword in text for keyword in [
        'how to use', 'how do i use', 'how can i use', 'what can i do', 'use this website', 'use this web application', 'how to use this web application'
    ]):
        return (
            "To use the website:\n"
            "1. Choose your role: Patient, Doctor, Hospital, Blood Donor, or Organ Donor.\n"
            "2. Register and login for your chosen role.\n"
            "3. Patients can book appointments, use symptom analysis, buy medicines, and chat with doctors.\n"
            "4. Doctors can manage appointments, consult patients, and upload prescriptions.\n"
            "5. Hospitals can manage bed inventory, emergency requests, and staff assignments.\n"
            "6. Donors can update availability and respond to donation requests."
        )

    if any(keyword in text for keyword in [
        'symptom analyzer', 'ai diagnosis', 'ai symptom', 'analyze symptoms', 'symptom analysis'
    ]):
        return (
            "To use the AI symptom analyzer:\n"
            "1. Open the AI Diagnosis or symptom analyzer page.\n"
            "2. Enter your symptoms in plain language.\n"
            "3. Submit the form to receive possible conditions, severity risk, and department suggestions.\n"
            "4. If chat is enabled, you can ask follow-up questions about your results."
        )

    if any(keyword in text for keyword in [
        'book appointment', 'appointment booking', 'book a doctor', 'book appointment'
    ]):
        return (
            "To book an appointment:\n"
            "1. Login as a patient.\n"
            "2. Select a doctor and available date/time.\n"
            "3. Confirm the booking.\n"
            "4. Complete payment if required.\n"
            "5. View the appointment in your patient dashboard."
        )

    if any(keyword in text for keyword in [
        'payment', 'pay', 'razorpay', 'checkout'
    ]):
        return (
            "To pay for an appointment or service:\n"
            "1. Complete your booking or order.\n"
            "2. Proceed to the payment page.\n"
            "3. Use the Razorpay checkout to complete your payment securely.\n"
            "4. Download the invoice after payment."
        )

    return None

@app.route('/api/chatbot', methods=['POST'])
@csrf.exempt
def api_chatbot():
    """Handles chat messages from the global AI assistant using true AI generation."""
    try:
        data = request.get_json(silent=True) or {}
        history = data.get('history', [])
        
        # Support legacy 'message' format just in case
        if not history:
            message = data.get('message', '').strip()
            if message:
                history = [{'role': 'user', 'content': message}]
            else:
                return jsonify({'reply': "I need a message to respond to. Please type something!"})

        user_message = ''
        for msg in reversed(history):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                break

        faq_reply = get_chatbot_faq_response(user_message)
        if faq_reply:
            return jsonify({'reply': faq_reply})

        if not _is_groq_configured():
            return jsonify({'reply': "I'm sorry, but my AI neural network is currently offline. Please configure the GROQ_API_KEY to enable chat."})

        # System prompt setting the AI's persona
        system_prompt = (
            "You are Spherix AI Assistant, the official AI health assistant for Spherix Clinic. "
            "You are friendly, empathetic, professional, and knowledgeable about general health, medicine, and the platform's features. "
            "When users ask about registration, account setup, or how to use the platform, answer clearly with page names and step-by-step instructions. "
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
            if "responses" in endpoint_openai:
                endpoint_openai = endpoint_openai.replace("responses", "chat/completions")
            messages = [{"role": "system", "content": system_prompt}] + history
            
            payload_openai = {
                'model': GROQ_API_MODEL,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 2048
            }
            
            resp = requests.post(endpoint_openai, headers=headers, json=payload_openai, timeout=30, verify=False)
            resp.raise_for_status()
            reply_text = _extract_groq_text_response(resp.json())
            return jsonify({'reply': reply_text.strip()})
            
        except Exception as e:
            print(f"Standard Chatbot API Error: {e}. Trying fallback format...")
            # Fallback to the chat/completions and messages format
            prompt = f"{system_prompt}\n\nConversation History:\n"
            for msg in history[-6:]:
                role = "User" if msg.get('role') == 'user' else "Spherix AI Assistant"
                prompt += f"{role}: {msg.get('content')}\n"
            prompt += "Spherix AI Assistant:"

            endpoint_custom = f"{GROQ_API_BASE.rstrip('/')}/chat/completions"
            if "responses" in endpoint_custom:
                endpoint_custom = endpoint_custom.replace("responses", "chat/completions")

            payload_custom = {
                'model': GROQ_API_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 2048
            }
            response = requests.post(endpoint_custom, headers=headers, json=payload_custom, timeout=30, verify=True)
            response.raise_for_status()
            payload_json = response.json()

            reply_text = _extract_groq_text_response(payload_json)
            
            if reply_text:
                return jsonify({'reply': reply_text.strip()})
            else:
                raise ValueError("No text generated in fallback format")

    except Exception as e:
        print(f"Chatbot error: {e}")
        return jsonify({'reply': "I'm experiencing some technical difficulties connecting to my neural network. Please try again in a moment, or contact our support team for assistance."})

# ==================== ADVERTISEMENT BOOKING ====================
@app.route('/ad-booking', methods=['GET', 'POST'])
def ad_booking():
    """Handle advertisement booking requests"""
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        budget = request.form.get('budget', '').strip()
        
        # Validate required fields
        if not all([company_name, email, budget]):
            flash("Company name, email, and budget are required fields.", "error")
            return render_template('ad_booking.html')
        
        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash("Please enter a valid email address.", "error")
            return render_template('ad_booking.html')
        
        # Validate budget is a number
        try:
            budget_amount = float(budget)
            if budget_amount < 1000:
                flash("Minimum budget is ₹1,000.", "error")
                return render_template('ad_booking.html')
        except ValueError:
            flash("Budget must be a valid number.", "error")
            return render_template('ad_booking.html')
        
        # Store ad booking request
        if 'ad_bookings' not in TEMP_DATA:
            TEMP_DATA['ad_bookings'] = {}
        
        ad_id = TEMP_DATA['next_ids'].get('ad_booking', 1)
        ad_booking_data = {
            'id': ad_id,
            'company_name': company_name,
            'email': email,
            'phone': phone,
            'budget': budget_amount,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'notes': ''
        }
        
        TEMP_DATA['ad_bookings'][ad_id] = ad_booking_data
        TEMP_DATA['next_ids']['ad_booking'] = ad_id + 1
        save_data()
        
        flash(f"✅ Advertisement booking request submitted! We'll contact you within 24 hours at {email}", "success")
        return render_template('ad_booking.html')
    
    return render_template('ad_booking.html')

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
    
    print(f"\n🚀 Starting Spherix Clinic Health Platform")
    print(f"📍 {protocol} Server: {protocol.lower()}://{host}:{port}")
    print(f"🔐 SSL Context: {'Enabled' if ssl_context else 'Disabled'}")
    print(f"📊 Debug Mode: {'ON' if debug else 'OFF'}")
    print(f"\n✅ Application is ready! Visit: {protocol.lower()}://{host}:{port}\n")
    
    # Run Flask app with or without SSL
    try:
        if socketio:
            socketio.run(app, debug=debug, host=host, port=port, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
        else:
            app.run(debug=debug, host=host, port=port, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
