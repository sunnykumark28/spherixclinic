"""
setup_db.py — Unified Master Database Management Utility for Spherix Clinic & S iCons
Consolidates Database Creation, Table Schemas, Production Data Seeding,
JSON Data Migration, and Database Reset Operations into a single master module.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load .env variables early
load_dotenv()

# ─── Automatic unixODBC path discovery on macOS ──────────────────────────────
if sys.platform == 'darwin' and not os.environ.get('ODBCSYSINI'):
    for prefix in ['/opt/homebrew/etc', '/usr/local/etc']:
        if os.path.exists(os.path.join(prefix, 'odbcinst.ini')):
            os.environ['ODBCSYSINI'] = prefix
            break

# ─── Environment & Database Configuration ─────────────────────────────────────
SERVER   = os.getenv('DB_SERVER', 'localhost')
DATABASE = os.getenv('DB_NAME', 'spherixclinic')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD', 'AnupriyaK#1234')
DRIVER   = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spherixclinic.db')

# ─── PyODBC Import with site-packages fallback ───────────────────────────────
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    for sp in ['/opt/anaconda3/lib/python3.13/site-packages', '/opt/homebrew/lib/python3.11/site-packages', '/opt/homebrew/lib/python3.12/site-packages']:
        if os.path.exists(sp) and sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        import pyodbc
        HAS_PYODBC = True
    except ImportError:
        HAS_PYODBC = False

# ─── Connection Utilities ─────────────────────────────────────────────────────
def get_sql_server_connection(db_name=DATABASE):
    """Returns a pyodbc connection to the specified SQL Server database."""
    if not HAS_PYODBC:
        return None
    try:
        conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={db_name};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
        return pyodbc.connect(conn_str, autocommit=True)
    except Exception as e:
        print(f"⚠️ SQL Server connection notice ({db_name}): {e}")
        return None

def get_sqlite_connection():
    """Returns a connection to the local SQLite database fallback."""
    import sqlite3
    return sqlite3.connect(SQLITE_DB_PATH)

def print_banner(title, char="═"):
    print(f"\n{char * 60}")
    print(f"   {title}")
    print(f"{char * 60}")

# ─── 1. TABLE CREATION & SCHEMA SETUP ─────────────────────────────────────────
def setup_database_schema(force_sqlite=False):
    """Creates all 24 tables in SQL Server (or SQLite fallback)."""
    print_banner("🏗️  SPHERIX CLINIC — DATABASE SCHEMA INITIALIZATION")

    if not force_sqlite and HAS_PYODBC:
        try:
            # 1. Ensure master database exists
            master_conn = get_sql_server_connection('master')
            if master_conn:
                cursor = master_conn.cursor()
                cursor.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{DATABASE}') CREATE DATABASE {DATABASE}")
                print(f"✅ SQL Server database '{DATABASE}' verified/created.")
                master_conn.close()

            # 2. Connect to target database and build tables
            conn = get_sql_server_connection(DATABASE)
            if conn:
                cursor = conn.cursor()
                tables = [
                    ("doctors", """CREATE TABLE doctors (
                        id VARCHAR(50) PRIMARY KEY,
                        first_name NVARCHAR(100),
                        last_name NVARCHAR(100),
                        email NVARCHAR(255) UNIQUE,
                        password NVARCHAR(255),
                        department NVARCHAR(100),
                        phone NVARCHAR(50),
                        specialization NVARCHAR(255),
                        address NVARCHAR(MAX),
                        profile_picture_url NVARCHAR(MAX),
                        bio NVARCHAR(MAX),
                        hospital_name NVARCHAR(255),
                        hospital_address NVARCHAR(MAX),
                        country NVARCHAR(100) DEFAULT 'India',
                        city NVARCHAR(100),
                        state NVARCHAR(100),
                        district NVARCHAR(100),
                        pincode NVARCHAR(20),
                        qualification NVARCHAR(MAX),
                        license_number NVARCHAR(100),
                        experience NVARCHAR(50),
                        consultation_type NVARCHAR(100),
                        consultation_fee NVARCHAR(50),
                        currency NVARCHAR(10) DEFAULT 'INR',
                        timezone NVARCHAR(50) DEFAULT 'IST (UTC+5:30)',
                        working_hours NVARCHAR(MAX),
                        languages_spoken NVARCHAR(MAX),
                        international_accreditation NVARCHAR(MAX),
                        telemedicine_modes NVARCHAR(MAX),
                        social_links NVARCHAR(MAX),
                        is_international BIT DEFAULT 0,
                        is_verified BIT DEFAULT 1,
                        is_blocked BIT DEFAULT 0,
                        is_hidden BIT DEFAULT 0,
                        availability_status NVARCHAR(50) DEFAULT 'available'
                    )"""),
                    ("patients", """CREATE TABLE patients (
                        id VARCHAR(50) PRIMARY KEY,
                        name NVARCHAR(255),
                        email NVARCHAR(255) UNIQUE,
                        password NVARCHAR(255),
                        age INT,
                        gender NVARCHAR(50),
                        phone NVARCHAR(50) NULL,
                        country NVARCHAR(100) DEFAULT 'India',
                        address NVARCHAR(MAX) NULL,
                        profile_picture_url NVARCHAR(255) NULL,
                        profile_picture_data VARBINARY(MAX) NULL,
                        profile_picture_content_type VARCHAR(50) NULL,
                        license_number NVARCHAR(100) NULL,
                        blood_group NVARCHAR(20) NULL,
                        height NVARCHAR(20) NULL,
                        weight NVARCHAR(20) NULL,
                        allergies NVARCHAR(MAX) NULL,
                        existing_conditions NVARCHAR(MAX) NULL,
                        current_medications NVARCHAR(MAX) NULL,
                        emergency_contact_name NVARCHAR(255) NULL,
                        emergency_contact_phone NVARCHAR(50) NULL,
                        emergency_contact_relation NVARCHAR(100) NULL,
                        insurance_provider NVARCHAR(255) NULL,
                        insurance_policy_no NVARCHAR(100) NULL,
                        date_of_birth NVARCHAR(50) NULL,
                        occupation NVARCHAR(100) NULL,
                        diet_preference NVARCHAR(50) NULL,
                        smoker_status NVARCHAR(50) NULL,
                        alcohol_status NVARCHAR(50) NULL,
                        clinical_record NVARCHAR(MAX) NULL
                    )"""),
                    ("hospitals", """CREATE TABLE hospitals (
                        id VARCHAR(50) PRIMARY KEY,
                        name NVARCHAR(255),
                        email NVARCHAR(255) UNIQUE,
                        password NVARCHAR(255),
                        logo_url NVARCHAR(MAX),
                        country NVARCHAR(100) DEFAULT 'India',
                        city NVARCHAR(100),
                        state NVARCHAR(100),
                        address NVARCHAR(MAX),
                        phone NVARCHAR(50),
                        currency NVARCHAR(10) DEFAULT 'INR',
                        timezone NVARCHAR(50) DEFAULT 'IST (UTC+5:30)',
                        total_beds INT DEFAULT 0,
                        available_beds INT DEFAULT 0,
                        icu_beds INT DEFAULT 0,
                        available_icu_beds INT DEFAULT 0,
                        general_bed_fee FLOAT DEFAULT 1000.0,
                        icu_bed_fee FLOAT DEFAULT 2500.0,
                        doctors_available NVARCHAR(50) DEFAULT 'Available',
                        accreditation NVARCHAR(255) DEFAULT 'NABH Accredited',
                        international_services NVARCHAR(MAX),
                        is_international BIT DEFAULT 0,
                        is_verified BIT DEFAULT 1,
                        is_blocked BIT DEFAULT 0,
                        is_hidden BIT DEFAULT 0
                    )"""),
                    ("staff", """CREATE TABLE staff (
                        id VARCHAR(50) PRIMARY KEY,
                        name NVARCHAR(255),
                        email NVARCHAR(255) UNIQUE,
                        password NVARCHAR(255),
                        role NVARCHAR(100),
                        phone NVARCHAR(50),
                        hospital_name NVARCHAR(255),
                        last_login DATETIME NULL,
                        created_at DATETIME NULL,
                        profile_picture_url NVARCHAR(MAX) NULL,
                        profile_picture_data VARBINARY(MAX) NULL,
                        profile_picture_content_type VARCHAR(50) NULL
                    )"""),
                    ("appointments", """CREATE TABLE appointments (
                        id INT PRIMARY KEY,
                        patient_name NVARCHAR(255),
                        doctor_id VARCHAR(50),
                        patient_id VARCHAR(50),
                        appointment_date DATE,
                        appointment_time TIME,
                        patient_age INT,
                        patient_id_number NVARCHAR(50),
                        patient_phone NVARCHAR(50),
                        patient_country NVARCHAR(100) DEFAULT 'India',
                        doctor_country NVARCHAR(100),
                        doctor_timezone NVARCHAR(50),
                        currency NVARCHAR(10) DEFAULT 'INR',
                        fee_amount NVARCHAR(50),
                        telemedicine_room_id NVARCHAR(255),
                        consultation_type NVARCHAR(100),
                        reason NVARCHAR(MAX),
                        status NVARCHAR(50),
                        created_at DATETIME DEFAULT GETDATE(),
                        original_appointment_date DATE,
                        original_appointment_time TIME,
                        document_path NVARCHAR(MAX),
                        prescription_path NVARCHAR(MAX)
                    )"""),
                    ("bed_bookings", """CREATE TABLE bed_bookings (
                        id INT PRIMARY KEY,
                        hospital_id VARCHAR(50),
                        patient_id VARCHAR(50),
                        patient_name NVARCHAR(255),
                        patient_phone NVARCHAR(50),
                        patient_country NVARCHAR(100) DEFAULT 'India',
                        passport_number NVARCHAR(100),
                        medical_visa_needed BIT DEFAULT 0,
                        bed_type NVARCHAR(50),
                        reason NVARCHAR(MAX),
                        status NVARCHAR(50),
                        currency NVARCHAR(10) DEFAULT 'INR',
                        is_international BIT DEFAULT 0,
                        room_number NVARCHAR(50),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("reviews", """CREATE TABLE reviews (
                        id INT PRIMARY KEY,
                        doctor_id VARCHAR(50),
                        patient_id VARCHAR(50),
                        patient_name NVARCHAR(255),
                        rating INT,
                        comment NVARCHAR(MAX),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("messages", """CREATE TABLE messages (
                        id INT PRIMARY KEY,
                        doctor_id VARCHAR(50),
                        patient_id VARCHAR(50),
                        sender NVARCHAR(50),
                        content NVARCHAR(MAX),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("orders", """CREATE TABLE orders (
                        id INT PRIMARY KEY,
                        patient_id VARCHAR(50),
                        items NVARCHAR(MAX),
                        total_price FLOAT,
                        shipping_address NVARCHAR(MAX),
                        order_date DATE,
                        status NVARCHAR(50)
                    )"""),
                    ("blood_donors", """CREATE TABLE blood_donors (
                        id VARCHAR(50) PRIMARY KEY,
                        name NVARCHAR(255),
                        email NVARCHAR(255) UNIQUE,
                        phone NVARCHAR(50),
                        blood_group NVARCHAR(10),
                        age INT,
                        city NVARCHAR(100),
                        password NVARCHAR(255),
                        last_donation DATE,
                        profile_picture_url NVARCHAR(255) NULL,
                        profile_picture_data VARBINARY(MAX) NULL,
                        profile_picture_content_type VARCHAR(50) NULL,
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("organ_donors", """CREATE TABLE organ_donors (
                        id VARCHAR(50) PRIMARY KEY,
                        name NVARCHAR(255),
                        email NVARCHAR(255) UNIQUE,
                        phone NVARCHAR(50),
                        organs NVARCHAR(MAX),
                        blood_group NVARCHAR(10),
                        age INT,
                        city NVARCHAR(100),
                        password NVARCHAR(255) NULL,
                        profile_picture_url NVARCHAR(255) NULL,
                        profile_picture_data VARBINARY(MAX) NULL,
                        profile_picture_content_type VARCHAR(50) NULL,
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("camps", """CREATE TABLE camps (
                        id INT PRIMARY KEY,
                        name NVARCHAR(255),
                        location NVARCHAR(MAX),
                        date NVARCHAR(50),
                        time NVARCHAR(50),
                        organizer NVARCHAR(255),
                        contact NVARCHAR(50)
                    )"""),
                    ("camp_registrations", """CREATE TABLE camp_registrations (
                        id INT PRIMARY KEY,
                        camp_name NVARCHAR(255),
                        name NVARCHAR(255),
                        email NVARCHAR(255),
                        phone NVARCHAR(50),
                        date DATETIME DEFAULT GETDATE()
                    )"""),
                    ("blood_stock", """CREATE TABLE blood_stock (
                        blood_group NVARCHAR(10) PRIMARY KEY,
                        quantity INT DEFAULT 0
                    )"""),
                    ("doctor_images", """CREATE TABLE doctor_images (
                        doctor_id VARCHAR(50) PRIMARY KEY,
                        image_data VARBINARY(MAX),
                        content_type VARCHAR(50)
                    )"""),
                    ("sicons_applications", """CREATE TABLE sicons_applications (
                        id INT PRIMARY KEY,
                        full_name NVARCHAR(255),
                        email NVARCHAR(255),
                        phone NVARCHAR(50),
                        position NVARCHAR(255),
                        department NVARCHAR(255),
                        submitted_at DATETIME,
                        files NVARCHAR(MAX),
                        form_data NVARCHAR(MAX),
                        profile_picture_data VARBINARY(MAX) NULL,
                        profile_picture_content_type VARCHAR(50) NULL
                    )"""),
                    ("organ_requests", """CREATE TABLE organ_requests (
                        id INT PRIMARY KEY,
                        patient_id VARCHAR(50),
                        hospital_id VARCHAR(50),
                        organ_type NVARCHAR(100),
                        urgency NVARCHAR(50),
                        status NVARCHAR(50),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_feedback", """CREATE TABLE patient_feedback (
                        id INT PRIMARY KEY,
                        patient_id VARCHAR(50),
                        patient_name NVARCHAR(255),
                        rating INT,
                        comments NVARCHAR(MAX) NULL,
                        feedback_target NVARCHAR(100) NULL,
                        target_id VARCHAR(50) NULL,
                        target_name NVARCHAR(255) NULL,
                        created_at DATETIME
                    )"""),
                    ("doctor_opinions", """CREATE TABLE doctor_opinions (
                        doctor_id VARCHAR(50) PRIMARY KEY,
                        rating INT,
                        experience NVARCHAR(MAX) NULL,
                        average_appointments NVARCHAR(100) NULL,
                        created_at DATETIME
                    )"""),
                    ("notifications", """CREATE TABLE notifications (
                        id INT PRIMARY KEY,
                        user_id VARCHAR(50),
                        user_type NVARCHAR(50),
                        title NVARCHAR(255),
                        message NVARCHAR(MAX),
                        status NVARCHAR(50) DEFAULT 'unread',
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("contact_messages", """CREATE TABLE contact_messages (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        name NVARCHAR(255),
                        email NVARCHAR(255),
                        phone NVARCHAR(50),
                        address NVARCHAR(MAX),
                        message NVARCHAR(MAX),
                        date DATETIME DEFAULT GETDATE()
                    )"""),
                    ("medicines", """CREATE TABLE medicines (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        name NVARCHAR(255),
                        category NVARCHAR(100),
                        price FLOAT,
                        stock INT DEFAULT 0,
                        description NVARCHAR(MAX)
                    )"""),
                    ("referrals", """CREATE TABLE referrals (
                        id INT PRIMARY KEY,
                        patient_id VARCHAR(50),
                        referred_to_hospital_id VARCHAR(50),
                        reason NVARCHAR(MAX),
                        status NVARCHAR(50) DEFAULT 'pending',
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("visitor_passes", """CREATE TABLE visitor_passes (
                        id INT PRIMARY KEY,
                        visitor_name NVARCHAR(255),
                        patient_name NVARCHAR(255),
                        hospital_id VARCHAR(50),
                        visit_date DATE,
                        status NVARCHAR(50) DEFAULT 'approved',
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("activity_logs", """CREATE TABLE activity_logs (
                        id INT PRIMARY KEY,
                        hospital_id VARCHAR(50),
                        actor NVARCHAR(255),
                        action NVARCHAR(255),
                        details NVARCHAR(MAX),
                        timestamp DATETIME DEFAULT GETDATE()
                    )"""),
                    ("settings", """CREATE TABLE settings (
                        setting_key VARCHAR(255) PRIMARY KEY,
                        setting_value NVARCHAR(MAX)
                    )"""),
                    ("newsletter_subscribers", """CREATE TABLE newsletter_subscribers (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        email NVARCHAR(255) UNIQUE,
                        subscribed_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_vitals", """CREATE TABLE patient_vitals (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        weight FLOAT NULL,
                        heart_rate INT NULL,
                        blood_sugar INT NULL,
                        systolic_bp INT NULL,
                        diastolic_bp INT NULL,
                        blood_pressure NVARCHAR(50) NULL,
                        spo2 INT NULL,
                        temperature NVARCHAR(20) NULL,
                        height NVARCHAR(20) NULL,
                        bmi NVARCHAR(20) NULL,
                        notes NVARCHAR(MAX) NULL,
                        recorded_at DATETIME DEFAULT GETDATE(),
                        date_recorded DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_medical_records", """CREATE TABLE patient_medical_records (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        doctor_id VARCHAR(50) NULL,
                        doctor_name NVARCHAR(255) NULL,
                        title NVARCHAR(255),
                        record_type NVARCHAR(100),
                        file_path NVARCHAR(500) NULL,
                        clinical_notes NVARCHAR(MAX) NULL,
                        record_date DATE NULL,
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_emergency_contacts", """CREATE TABLE patient_emergency_contacts (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        contact_name NVARCHAR(255),
                        relationship NVARCHAR(100),
                        phone NVARCHAR(50),
                        email NVARCHAR(255) NULL,
                        is_primary BIT DEFAULT 0,
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_medication_schedules", """CREATE TABLE patient_medication_schedules (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        medicine_name NVARCHAR(255),
                        dosage NVARCHAR(100),
                        timing NVARCHAR(100),
                        frequency NVARCHAR(100),
                        instructions NVARCHAR(MAX) NULL,
                        status NVARCHAR(50) DEFAULT 'active',
                        date_logged DATETIME DEFAULT GETDATE(),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_symptom_checks", """CREATE TABLE patient_symptom_checks (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        primary_symptom NVARCHAR(255),
                        duration NVARCHAR(100),
                        urgency_level NVARCHAR(50),
                        possible_causes NVARCHAR(MAX) NULL,
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_ai_queries", """CREATE TABLE patient_ai_queries (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        query_text NVARCHAR(MAX),
                        response_summary NVARCHAR(MAX),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("patient_lifestyle_logs", """CREATE TABLE patient_lifestyle_logs (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        patient_id VARCHAR(50),
                        water_intake_liters FLOAT NULL,
                        sleep_hours FLOAT NULL,
                        calories_burned INT NULL,
                        mood NVARCHAR(50) NULL,
                        notes NVARCHAR(MAX) NULL,
                        logged_date DATE DEFAULT CAST(GETDATE() AS DATE),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("lab_requests", """CREATE TABLE lab_requests (
                        id INT PRIMARY KEY,
                        doctor_id VARCHAR(50),
                        patient_id VARCHAR(50),
                        patient_name NVARCHAR(255),
                        test_name NVARCHAR(255),
                        status NVARCHAR(50) DEFAULT 'pending',
                        notes NVARCHAR(MAX),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("ad_bookings", """CREATE TABLE ad_bookings (
                        id INT PRIMARY KEY,
                        advertiser_name NVARCHAR(255),
                        email NVARCHAR(255),
                        phone NVARCHAR(50),
                        banner_url NVARCHAR(MAX),
                        target_url NVARCHAR(MAX),
                        duration_days INT,
                        status NVARCHAR(50) DEFAULT 'pending',
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("symptom_reviews", """CREATE TABLE symptom_reviews (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        symptoms NVARCHAR(MAX),
                        predicted_condition NVARCHAR(255),
                        severity NVARCHAR(50),
                        accuracy_rating INT,
                        user_feedback NVARCHAR(MAX),
                        created_at DATETIME DEFAULT GETDATE()
                    )"""),
                    ("audit_logs", """CREATE TABLE audit_logs (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        operator NVARCHAR(255),
                        action_name NVARCHAR(255),
                        target_patient NVARCHAR(100),
                        route NVARCHAR(255),
                        ip_address NVARCHAR(50),
                        timestamp DATETIME DEFAULT GETDATE()
                    )"""),
                    ("ayurveda_remedies", """CREATE TABLE ayurveda_remedies (
                        id INT PRIMARY KEY,
                        disease_name NVARCHAR(255),
                        symptoms NVARCHAR(MAX),
                        dosha_type NVARCHAR(100),
                        herbal_formulation NVARCHAR(MAX),
                        dosage_instructions NVARCHAR(MAX),
                        dietary_advice NVARCHAR(MAX)
                    )"""),
                    ("diseases_catalog", """CREATE TABLE diseases_catalog (
                        id VARCHAR(50) PRIMARY KEY,
                        disease_name NVARCHAR(255),
                        category NVARCHAR(100),
                        symptom_tags NVARCHAR(MAX),
                        description NVARCHAR(MAX),
                        clinical_qa NVARCHAR(MAX)
                    )"""),
                    ("lab_packages", """CREATE TABLE lab_packages (
                        id VARCHAR(50) PRIMARY KEY,
                        name NVARCHAR(255),
                        category NVARCHAR(100),
                        concern NVARCHAR(100),
                        price FLOAT,
                        mrp FLOAT,
                        parameters_count INT,
                        sample_type NVARCHAR(100),
                        fasting_required NVARCHAR(50),
                        badge NVARCHAR(50)
                    )"""),
                    ("insurance_policies", """CREATE TABLE insurance_policies (
                        id VARCHAR(50) PRIMARY KEY,
                        policy_name NVARCHAR(255),
                        provider NVARCHAR(255),
                        sum_insured FLOAT,
                        annual_premium FLOAT,
                        network_hospitals_count INT,
                        claim_settlement_ratio FLOAT,
                        key_benefits NVARCHAR(MAX)
                    )"""),
                    ("medical_travel_countries", """CREATE TABLE medical_travel_countries (
                        id VARCHAR(10) PRIMARY KEY,
                        country_name NVARCHAR(100),
                        currency_code NVARCHAR(10),
                        currency_symbol NVARCHAR(10),
                        flag_emoji NVARCHAR(10),
                        visa_type NVARCHAR(100),
                        processing_days INT,
                        translator_available BIT DEFAULT 1,
                        partner_hospitals_count INT
                    )""")
                ]

                for name, query in tables:
                    cursor.execute(f"IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{name}' AND xtype='U') {query}")
                    print(f"  ✓ SQL Server Table: '{name}'")

                cursor.execute("SELECT COUNT(*) FROM blood_stock")
                if cursor.fetchone()[0] == 0:
                    stock_data = [('A+', 15), ('A-', 5), ('B+', 12), ('B-', 4), ('AB+', 8), ('AB-', 3), ('O+', 25), ('O-', 10)]
                    cursor.executemany("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", stock_data)
                    print("  ✓ Blood stock defaults initialized.")

                conn.commit()
                conn.close()
                print("🎉 SQL Server Tables Verified Successfully.")
                return True
        except Exception as e:
            print(f"⚠️ SQL Server setup encounter: {e}")

    # Fallback / Force SQLite
    setup_sqlite_tables()
    return True

def setup_sqlite_tables():
    """Initializes local SQLite database with all schema tables."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    sqlite_tables = [
        "CREATE TABLE IF NOT EXISTS doctors (id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT UNIQUE, password TEXT, department TEXT, phone TEXT, specialization TEXT, address TEXT, profile_picture_url TEXT, bio TEXT, hospital_name TEXT, hospital_address TEXT, country TEXT DEFAULT 'India', city TEXT, state TEXT, district TEXT, pincode TEXT, qualification TEXT, license_number TEXT, experience TEXT, consultation_type TEXT, consultation_fee TEXT, currency TEXT DEFAULT 'INR', timezone TEXT DEFAULT 'IST (UTC+5:30)', working_hours TEXT, languages_spoken TEXT, international_accreditation TEXT, telemedicine_modes TEXT, social_links TEXT, is_international INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 1, is_blocked INTEGER DEFAULT 0, is_hidden INTEGER DEFAULT 0, availability_status TEXT DEFAULT 'available')",
        "CREATE TABLE IF NOT EXISTS patients (id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, age INTEGER, gender TEXT, phone TEXT, country TEXT DEFAULT 'India', address TEXT, profile_picture_url TEXT, profile_picture_data BLOB, profile_picture_content_type TEXT)",
        "CREATE TABLE IF NOT EXISTS hospitals (id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, logo_url TEXT, country TEXT DEFAULT 'India', city TEXT, state TEXT, address TEXT, phone TEXT, currency TEXT DEFAULT 'INR', timezone TEXT DEFAULT 'IST (UTC+5:30)', total_beds INTEGER DEFAULT 0, available_beds INTEGER DEFAULT 0, icu_beds INTEGER DEFAULT 0, available_icu_beds INTEGER DEFAULT 0, general_bed_fee REAL DEFAULT 1000.0, icu_bed_fee REAL DEFAULT 2500.0, doctors_available TEXT DEFAULT 'Available', accreditation TEXT DEFAULT 'NABH Accredited', international_services TEXT, is_international INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 1, is_blocked INTEGER DEFAULT 0, is_hidden INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS staff (id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, password TEXT, role TEXT, phone TEXT, hospital_name TEXT, last_login TIMESTAMP, created_at TIMESTAMP, profile_picture_data BLOB, profile_picture_content_type TEXT)",
        "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY, patient_name TEXT, doctor_id TEXT, patient_id TEXT, appointment_date DATE, appointment_time TIME, patient_age INTEGER, patient_id_number TEXT, patient_phone TEXT, patient_country TEXT DEFAULT 'India', doctor_country TEXT, doctor_timezone TEXT, currency TEXT DEFAULT 'INR', fee_amount TEXT, telemedicine_room_id TEXT, consultation_type TEXT, reason TEXT, status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, original_appointment_date DATE, original_appointment_time TIME, document_path TEXT, prescription_path TEXT)",
        "CREATE TABLE IF NOT EXISTS bed_bookings (id INTEGER PRIMARY KEY, hospital_id TEXT, patient_id TEXT, patient_name TEXT, patient_phone TEXT, patient_country TEXT DEFAULT 'India', passport_number TEXT, medical_visa_needed INTEGER DEFAULT 0, bed_type TEXT, reason TEXT, status TEXT, currency TEXT DEFAULT 'INR', is_international INTEGER DEFAULT 0, room_number TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, doctor_id TEXT, patient_id TEXT, patient_name TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, doctor_id TEXT, patient_id TEXT, sender TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, patient_id TEXT, items TEXT, total_price REAL, shipping_address TEXT, order_date DATE, status TEXT)",
        "CREATE TABLE IF NOT EXISTS blood_donors (id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, phone TEXT, blood_group TEXT, age INTEGER, city TEXT, password TEXT, last_donation DATE, profile_picture_url TEXT, profile_picture_data BLOB, profile_picture_content_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS organ_donors (id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, phone TEXT, organs TEXT, blood_group TEXT, age INTEGER, city TEXT, password TEXT, profile_picture_url TEXT, profile_picture_data BLOB, profile_picture_content_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS camps (id INTEGER PRIMARY KEY, name TEXT, location TEXT, date TEXT, time TEXT, organizer TEXT, contact TEXT)",
        "CREATE TABLE IF NOT EXISTS camp_registrations (id INTEGER PRIMARY KEY, camp_name TEXT, name TEXT, email TEXT, phone TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS blood_stock (blood_group TEXT PRIMARY KEY, quantity INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS doctor_images (doctor_id TEXT PRIMARY KEY, image_data BLOB, content_type TEXT)",
        "CREATE TABLE IF NOT EXISTS sicons_applications (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, phone TEXT, position TEXT, department TEXT, submitted_at TIMESTAMP, files TEXT, form_data TEXT, profile_picture_data BLOB, profile_picture_content_type TEXT)",
        "CREATE TABLE IF NOT EXISTS organ_requests (id INTEGER PRIMARY KEY, patient_id TEXT, hospital_id TEXT, organ_type TEXT, urgency TEXT, status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS patient_feedback (id INTEGER PRIMARY KEY, patient_id TEXT, patient_name TEXT, rating INTEGER, comments TEXT, feedback_target TEXT, target_id TEXT, target_name TEXT, created_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS doctor_opinions (doctor_id TEXT PRIMARY KEY, rating INTEGER, experience TEXT, average_appointments TEXT, created_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, user_id TEXT, user_type TEXT, title TEXT, message TEXT, status TEXT DEFAULT 'unread', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS contact_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, address TEXT, message TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS medicines (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER DEFAULT 0, description TEXT)",
        "CREATE TABLE IF NOT EXISTS referrals (id INTEGER PRIMARY KEY, patient_id TEXT, referred_to_hospital_id TEXT, reason TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS visitor_passes (id INTEGER PRIMARY KEY, visitor_name TEXT, patient_name TEXT, hospital_id TEXT, visit_date DATE, status TEXT DEFAULT 'approved', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY, hospital_id TEXT, actor TEXT, action TEXT, details TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
        "CREATE TABLE IF NOT EXISTS newsletter_subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS patient_vitals (id INTEGER PRIMARY KEY, patient_id TEXT, weight REAL, heart_rate INTEGER, blood_sugar INTEGER, systolic_bp INTEGER, diastolic_bp INTEGER, recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS lab_requests (id INTEGER PRIMARY KEY, doctor_id TEXT, patient_id TEXT, patient_name TEXT, test_name TEXT, status TEXT DEFAULT 'pending', notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS ad_bookings (id INTEGER PRIMARY KEY, advertiser_name TEXT, email TEXT, phone TEXT, banner_url TEXT, target_url TEXT, duration_days INTEGER, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS symptom_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, symptoms TEXT, predicted_condition TEXT, severity TEXT, accuracy_rating INTEGER, user_feedback TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, operator TEXT, action_name TEXT, target_patient TEXT, route TEXT, ip_address TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS ayurveda_remedies (id INTEGER PRIMARY KEY, disease_name TEXT, symptoms TEXT, dosha_type TEXT, herbal_formulation TEXT, dosage_instructions TEXT, dietary_advice TEXT)",
        "CREATE TABLE IF NOT EXISTS diseases_catalog (id TEXT PRIMARY KEY, disease_name TEXT, category TEXT, symptom_tags TEXT, description TEXT, clinical_qa TEXT)",
        "CREATE TABLE IF NOT EXISTS lab_packages (id TEXT PRIMARY KEY, name TEXT, category TEXT, concern TEXT, price REAL, mrp REAL, parameters_count INTEGER, sample_type TEXT, fasting_required TEXT, badge TEXT)",
        "CREATE TABLE IF NOT EXISTS insurance_policies (id TEXT PRIMARY KEY, policy_name TEXT, provider TEXT, sum_insured REAL, annual_premium REAL, network_hospitals_count INTEGER, claim_settlement_ratio REAL, key_benefits TEXT)",
        "CREATE TABLE IF NOT EXISTS medical_travel_countries (id TEXT PRIMARY KEY, country_name TEXT, currency_code TEXT, currency_symbol TEXT, flag_emoji TEXT, visa_type TEXT, processing_days INTEGER, translator_available INTEGER DEFAULT 1, partner_hospitals_count INTEGER)"
    ]

    for stmt in sqlite_tables:
        cursor.execute(stmt)

    cursor.execute("SELECT COUNT(*) FROM blood_stock")
    if cursor.fetchone()[0] == 0:
        stock_data = [('A+', 15), ('A-', 5), ('B+', 12), ('B-', 4), ('AB+', 8), ('AB-', 3), ('O+', 25), ('O-', 10)]
        cursor.executemany("INSERT OR IGNORE INTO blood_stock (blood_group, quantity) VALUES (?, ?)", stock_data)

    conn.commit()
    conn.close()
    print(f"🎉 Local SQLite Database '{SQLITE_DB_PATH}' (24 Tables) Created & Verified Successfully.")

# ─── 2. SEEDING PRODUCTION & DEMO DATA ────────────────────────────────────────
def seed_all_database_data():
    """Seeds doctors, hospitals, patients, staff, appointments, blood donors, and clinical data."""
    print_banner("🌱  SPHERIX CLINIC — COMPREHENSIVE DATA SEEDING")

    conn = get_sql_server_connection(DATABASE)
    is_sqlite = False
    if not conn:
        print("ℹ️ SQL Server unavailable. Seeding local SQLite fallback database...")
        conn = get_sqlite_connection()
        is_sqlite = True

    cursor = conn.cursor()
    default_hash = generate_password_hash("password123")
    admin_hash = generate_password_hash("Admin@1234")

    # 1. Doctors
    doctors_data = [
        ('DOC/2026/001', 'Sunny', 'Kushwaha', 'admin@spherixclinic.com', admin_hash, 'Administration', '+91 933 4325 920', 'Chief Medical Officer', 'Spherix Clinical HQ, Motihari', '15 Years', 'MD, FACC', 'MCI-00192', '1000', 'English, Hindi', 'SMCH', 'Motihari, Bihar', 'available', 1),
        ('DOC/2026/002', 'Sarah', 'Jenkins', 'doctor@example.com', default_hash, 'Cardiology', '+1 (555) 234-5678', 'Interventional Cardiology', 'Cardiology Wing, Floor 4, Suite 402', '12 Years', 'MD, Harvard Medical School', 'MCI-88492', '750', 'English, Spanish', 'SMCH', 'Motihari, Bihar', 'available', 1),
        ('DOC/2026/003', 'Robert', 'Chen', 'chen@example.com', default_hash, 'Neurology', '+1 (555) 345-6789', 'Cerebrovascular & Stroke Care', 'Neurology Diagnostic Lab, Suite 201', '14 Years', 'MD, Johns Hopkins University', 'MCI-99234', '800', 'English, Mandarin', 'Metro Health City Hospital', 'New York, NY', 'available', 1),
        ('DOC/2026/004', 'Marie', 'Curie', 'marie@example.com', default_hash, 'Oncology', '+1 (555) 456-7890', 'Radiation Oncology & Immunotherapy', 'Cancer Care Pavilion, Block B', '18 Years', 'MD, PhD Oncology', 'MCI-54369', '900', 'English, French', 'Apollo Super Speciality Hospital', 'New Delhi, DL', 'available', 1),
        ('DOC/2026/005', 'Arun', 'Verma', 'arun.verma@example.com', default_hash, 'Orthopedics', '+91 987 6543 210', 'Joint Replacement & Spine Surgery', 'Orthopedic Surgery Center', '10 Years', 'MS (Ortho), AIIMS New Delhi', 'MCI-77312', '600', 'English, Hindi', 'SMCH', 'Motihari, Bihar', 'available', 1)
    ]
    for doc in doctors_data:
        cursor.execute("SELECT id FROM doctors WHERE id = ? OR email = ?", (doc[0], doc[3]))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO doctors (
                    id, first_name, last_name, email, password, department, phone, specialization, 
                    address, experience, qualification, license_number, consultation_fee, 
                    languages_spoken, hospital_name, hospital_address, availability_status, is_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, doc)
            print(f"  ✓ Added Doctor: Dr. {doc[1]} {doc[2]} ({doc[5]})")

    # 2. Patients
    patients_data = [
        ('PAT/2026/001', 'Rahul Sharma', 'patient@example.com', default_hash, 34, 'Male', '+91 944 1234 567', 'Civil Lines, Motihari, Bihar'),
        ('PAT/2026/002', 'Emily Watson', 'emily.watson@example.com', default_hash, 29, 'Female', '+1 (555) 678-9012', '742 Evergreen Terrace, New York, NY'),
        ('PAT/2026/003', 'Vikram Patel', 'vikram@example.com', default_hash, 48, 'Male', '+91 982 3456 789', 'Boring Road, Patna, Bihar'),
        ('PAT/2026/004', 'Anita Roy', 'anita@example.com', default_hash, 52, 'Female', '+91 971 2345 678', 'Park Street, Kolkata, West Bengal')
    ]
    for pat in patients_data:
        cursor.execute("SELECT id FROM patients WHERE id = ? OR email = ?", (pat[0], pat[2]))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO patients (id, name, email, password, age, gender, phone, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", pat)
            print(f"  ✓ Added Patient: {pat[1]} ({pat[2]})")

    # 3. Hospitals
    hospitals_data = [
        ('HPT/2026/001', 'SMCH (Spherix Memorial Care Hospital)', 'hospital@spherixclinic.com', default_hash, 150, 42, 25, 6, 'Available', 'Main Medical Campus, Station Road, Motihari, Bihar', 1),
        ('HPT/2026/002', 'Metro Health City Hospital', 'metro@example.com', default_hash, 250, 78, 40, 12, 'Available', '450 Lexington Ave, New York, NY', 1),
        ('HPT/2026/003', 'St. Jude Regional Medical Center', 'stjude@example.com', default_hash, 180, 55, 30, 8, 'Available', '12 Medical Park Blvd, Chicago, IL', 1),
        ('HPT/2026/004', 'Apollo Super Speciality Hospital', 'apollo@example.com', default_hash, 320, 95, 50, 14, 'Available', 'Mathura Road, Sarita Vihar, New Delhi', 1)
    ]
    for hpt in hospitals_data:
        cursor.execute("SELECT id FROM hospitals WHERE id = ? OR email = ?", (hpt[0], hpt[2]))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO hospitals (
                    id, name, email, password, total_beds, available_beds, icu_beds, 
                    available_icu_beds, doctors_available, address, is_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, hpt)
            print(f"  ✓ Added Hospital: {hpt[1]}")

    # 4. Staff
    staff_data = [
        ('STF/2026/001', 'Sumit Kumar', 'sumit@gmail.com', default_hash, 'Blood Donor Management', '9334325921', 'SMCH'),
        ('STF/2026/002', 'Pooja Sharma', 'pooja.nurse@example.com', default_hash, 'Triage Nursing Officer', '+91 988 7766 554', 'SMCH'),
        ('STF/2026/003', 'Kevin Vance', 'kevin.reception@example.com', default_hash, 'Front Desk Reception Coordinator', '+1 (555) 443-2211', 'Metro Health City Hospital')
    ]
    for stf in staff_data:
        cursor.execute("SELECT id FROM staff WHERE id = ? OR email = ?", (stf[0], stf[2]))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO staff (id, name, email, password, role, phone, hospital_name) VALUES (?, ?, ?, ?, ?, ?, ?)", stf)
            print(f"  ✓ Added Staff: {stf[1]} ({stf[4]})")

    # 5. Blood Donors
    blood_donors_data = [
        ('BD/2026/001', 'Sunny Kushwaha', 'sunny28skk@gmail.com', '9334325920', 'AB+', 24, 'Motihari', default_hash, '2026-06-15'),
        ('BD/2026/002', 'David Miller', 'david.m@example.com', '+1 (555) 887-1234', 'O-', 28, 'New York', default_hash, '2026-07-20'),
        ('BD/2026/003', 'Rohan Gupta', 'rohan.g@example.com', '+91 983 5544 332', 'O+', 31, 'Patna', default_hash, '2026-08-01'),
        ('BD/2026/004', 'Sarah Lin', 'sarah.lin@example.com', '+1 (555) 776-5544', 'A+', 26, 'Chicago', default_hash, '2026-05-10')
    ]
    for bd in blood_donors_data:
        cursor.execute("SELECT id FROM blood_donors WHERE id = ? OR email = ?", (bd[0], bd[2]))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", bd)
            print(f"  ✓ Added Blood Donor: {bd[1]} ({bd[4]})")

    # 6. Organ Donors
    organ_donors_data = [
        ('OD/2026/001', 'Elena Rostova', 'elena@example.com', '+1 (555) 432-1098', 'Heart, Kidneys, Corneas', 'O+', 29, 'New York', default_hash),
        ('OD/2026/002', 'Ramesh Chandra', 'ramesh.c@example.com', '+91 983 1122 334', 'Kidneys, Liver', 'B+', 42, 'Patna', default_hash)
    ]
    for od in organ_donors_data:
        cursor.execute("SELECT id FROM organ_donors WHERE id = ? OR email = ?", (od[0], od[2]))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", od)
            print(f"  ✓ Added Organ Donor: {od[1]} ({od[4]})")

    # 7. Donation Camps
    camps_data = [
        (101, 'Red Cross Central Life Drive 2026', 'Community Medical Grounds, Station Road, Motihari', '2026-09-05', '09:00 AM - 05:00 PM', 'Indian Red Cross Society & SMCH', '+91 933 4325 920'),
        (102, 'Rotary Club Metropolitan Blood Drive', 'Madison Square Health Arena, New York, NY', '2026-09-12', '08:30 AM - 04:30 PM', 'Rotary International & Metro Health', '+1 (555) 900-1000')
    ]
    for camp in camps_data:
        cursor.execute("SELECT id FROM camps WHERE id = ?", (camp[0],))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO camps (id, name, location, date, time, organizer, contact) VALUES (?, ?, ?, ?, ?, ?, ?)", camp)
            print(f"  ✓ Added Blood Camp: {camp[1]}")

    # 8. Appointments
    appointments_data = [
        (1001, 'Rahul Sharma', 'DOC/2026/002', 'PAT/2026/001', '2026-08-25', '10:30:00', 34, 'PID-9901', '+91 944 1234 567', 'Routine Cardiovascular Health Checkup & ECG Review', 'Confirmed'),
        (1002, 'Emily Watson', 'DOC/2026/003', 'PAT/2026/002', '2026-08-26', '14:00:00', 29, 'PID-9902', '+1 (555) 678-9012', 'Chronic Migraine & Neurological Screening', 'Confirmed')
    ]
    for apt in appointments_data:
        cursor.execute("SELECT id FROM appointments WHERE id = ?", (apt[0],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO appointments (
                    id, patient_name, doctor_id, patient_id, appointment_date, appointment_time, 
                    patient_age, patient_id_number, patient_phone, reason, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, apt)
            print(f"  ✓ Added Appointment #{apt[0]}: {apt[1]} -> Dr. ID {apt[2]}")

    # 9. Bed Bookings
    bed_bookings_data = [
        (2001, 'HPT/2026/001', 'PAT/2026/001', 'Rahul Sharma', '+91 944 1234 567', 'General Deluxe Ward', 'Post-Op Observation & Fluid Therapy', 'Admitted', 'Ward 304'),
        (2002, 'HPT/2026/001', 'PAT/2026/003', 'Vikram Patel', '+91 982 3456 789', 'ICU Specialized Unit', 'Acute Cardiac Monitoring', 'Reserved', 'ICU Bed 04')
    ]
    for bb in bed_bookings_data:
        cursor.execute("SELECT id FROM bed_bookings WHERE id = ?", (bb[0],))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO bed_bookings (id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, room_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", bb)
            print(f"  ✓ Added Bed Booking #{bb[0]}: {bb[3]}")

    conn.commit()
    conn.close()
    print("🎉 All Master Data Successfully Seeded.")
    return True

# ─── 3. JSON DATA MIGRATION UTILITY ──────────────────────────────────────────
def migrate_json_data(json_path=None):
    """Migrates JSON data store files into SQL database tables."""
    print_banner("📦  SPHERIX CLINIC — JSON DATA MIGRATION")

    if not json_path:
        for candidate in ['data_store.json', 'data_store.json.migrated', 'data.json']:
            cpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), candidate)
            if os.path.exists(cpath):
                json_path = cpath
                break

    if not json_path or not os.path.exists(json_path):
        print("ℹ️ No JSON migration archive found. Skipping file migration.")
        return False

    print(f"📖 Reading records from '{json_path}'...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_sql_server_connection(DATABASE) or get_sqlite_connection()
    cursor = conn.cursor()

    # Migrate Doctors
    for doc_id, doc in data.get('doctors', {}).items():
        try:
            cursor.execute("SELECT id FROM doctors WHERE id = ?", (doc.get('id'),))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO doctors (
                        id, first_name, last_name, email, password, department, phone, specialization, 
                        address, profile_picture_url, bio, hospital_name, hospital_address, state, 
                        district, pincode, qualification, license_number, experience, consultation_type, 
                        consultation_fee, working_hours, languages_spoken, social_links, is_verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc.get('id'), doc.get('first_name'), doc.get('last_name'), doc.get('email'), doc.get('password'),
                    doc.get('department'), doc.get('phone'), doc.get('specialization'), doc.get('address'),
                    doc.get('profile_picture_url'), doc.get('bio'), doc.get('hospital_name'), doc.get('hospital_address'),
                    doc.get('state'), doc.get('district'), doc.get('pincode'), doc.get('qualification'),
                    doc.get('license_number'), doc.get('experience'), doc.get('consultation_type'),
                    doc.get('consultation_fee'), doc.get('working_hours'), doc.get('languages_spoken'),
                    doc.get('social_links'), doc.get('is_verified', 1)
                ))
                print(f"  ✓ Migrated Doctor {doc.get('id')}")
        except Exception as e:
            print(f"  ⚠️ Doctor migration skipped ({doc_id}): {e}")

    conn.commit()
    conn.close()
    print("✅ JSON Migration Completed.")
    return True

# ─── 4. DATABASE RESET & RESTORE UTILITY ─────────────────────────────────────
def reset_database(force=False):
    """Truncates/clears all tables and restores baseline defaults."""
    print_banner("⚠️  SPHERIX CLINIC — DATABASE RESET & SANITIZATION")

    if not force:
        confirm = input("⚠️  Are you sure you want to reset and clear all data? (Type 'RESET' to confirm): ").strip()
        if confirm != 'RESET':
            print("❌ Reset operation aborted.")
            return False

    tables_to_clear = [
        'camp_registrations', 'appointments', 'messages', 'orders', 'reviews',
        'bed_bookings', 'doctor_images', 'staff', 'doctors', 'patients',
        'hospitals', 'blood_donors', 'organ_donors', 'camps', 'blood_stock',
        'organ_requests', 'patient_vitals', 'activity_logs', 'contact_messages',
        'sicons_applications', 'medicines', 'visitor_passes', 'referrals', 'notifications'
    ]

    conn = get_sql_server_connection(DATABASE)
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'")
            for table in tables_to_clear:
                try:
                    cursor.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL DELETE FROM {table}")
                    print(f"  ✓ Cleared table: {table}")
                except Exception as e:
                    print(f"  ⚠️ Could not clear {table}: {e}")
            cursor.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? WITH CHECK CHECK CONSTRAINT ALL'")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ SQL Server reset error: {e}")

    # Also clear SQLite fallback if exists
    if os.path.exists(SQLITE_DB_PATH):
        try:
            s_conn = get_sqlite_connection()
            s_cur = s_conn.cursor()
            for table in tables_to_clear:
                try:
                    s_cur.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
            s_conn.commit()
            s_conn.close()
            print(f"  ✓ Cleared local SQLite tables in '{SQLITE_DB_PATH}'")
        except Exception as e:
            print(f"⚠️ SQLite reset error: {e}")

    # Re-seed baseline defaults
    setup_database_schema()
    seed_all_database_data()
    print("✅ Database Successfully Reset & Restored to Initial Clean State.")
    return True

# ─── 5. CLI DISPATCHER ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Spherix Clinic Unified Master Database Utility")
    parser.add_argument('--setup', action='store_true', help="Initialize all schemas and tables")
    parser.add_argument('--seed', action='store_true', help="Seed complete production and test dataset")
    parser.add_argument('--migrate', action='store_true', help="Migrate JSON data into SQL tables")
    parser.add_argument('--reset', action='store_true', help="Reset and re-initialize all database tables")
    parser.add_argument('--sqlite', action='store_true', help="Force setup on local SQLite fallback database")
    parser.add_argument('--all', action='store_true', help="Run schema setup + complete data seeding")

    args = parser.parse_args()

    if args.reset:
        reset_database(force=True)
    elif args.migrate:
        migrate_json_data()
    elif args.seed:
        seed_all_database_data()
    elif args.sqlite:
        setup_sqlite_tables()
        seed_all_database_data()
    elif args.setup:
        setup_database_schema()
    else:
        # Default: Full Schema Setup + Data Seeding
        setup_database_schema()
        seed_all_database_data()

if __name__ == '__main__':
    main()