import os
import sys
import json
import sqlite3
import random
import secrets
import re
import copy
import traceback
from datetime import datetime, timezone, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash

from spherix.config import (
    DATA_FILE, SERVER, DATABASE, USERNAME, PASSWORD, DRIVER,
    utcnow, parse_route_id, generate_user_license_id
)
from spherix.models import (
    Doctor, Patient, Staff, HospitalStaff, Hospital, BloodDonor, OrganDonor,
    Appointment, PatientVital, LabRequest, OrganRequest, BedBooking, PatientMedicalRecord,
    Order, Review, Feedback, Message, ActivityLog, Referral, Notification
)

# PyODBC handling
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    for sp in ['/opt/anaconda3/lib/python3.13/site-packages', '/opt/homebrew/lib/python3.11/site-packages', '/opt/homebrew/lib/python3.12/site-packages', '/usr/local/lib/python3.11/site-packages']:
        if os.path.exists(sp) and sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        import pyodbc
        HAS_PYODBC = True
    except ImportError:
        HAS_PYODBC = False

if not HAS_PYODBC or pyodbc is None:
    class _DummyPyodbcError(Exception):
        pass

    class _DummyPyodbc:
        Error = _DummyPyodbcError
        DatabaseError = _DummyPyodbcError
        OperationalError = _DummyPyodbcError
        IntegrityError = _DummyPyodbcError
        ProgrammingError = _DummyPyodbcError
        DataError = _DummyPyodbcError
        InternalError = _DummyPyodbcError
        NotSupportedError = _DummyPyodbcError
        _is_dummy = True

        @staticmethod
        def connect(*args, **kwargs):
            raise _DummyPyodbcError("pyodbc is not installed or available in this environment.")

    pyodbc = _DummyPyodbc()

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

# ---------------- File-Based Data Store (JSON) ----------------
DATA_FILE = 'data_store.json'

# SQL Database Configuration
SERVER = os.getenv('DB_SERVER', 'localhost')
DATABASE = os.getenv('DB_NAME', 'spherixclinic')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('DB_PASS', '')
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
    "activity_logs": {},
    "auth_activity_logs": [],
    "terminated_auth_sessions": {},
    "medical_records": {},
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
    "referrals": {},
    "notifications": {},
    "patient_vitals": {},
    "lab_requests": {},
    "broadcast_history": [],
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
        "bed_booking": 1,
        "activity_log": 1,
        "organ_request": 1,
        "ad_booking": 1,
        "referral": 1,
        "patient_vital": 1,
        "medical_record": 1,

        "notification": 1,
    }
}

def get_resolved_db_driver():
    global DRIVER
    if hasattr(get_resolved_db_driver, '_resolved') and get_resolved_db_driver._resolved:
        return get_resolved_db_driver._resolved

    candidates = [
        DRIVER,
        os.getenv('DB_DRIVER'),
        '/opt/homebrew/lib/libmsodbcsql.17.dylib',
        '/opt/homebrew/lib/libmsodbcsql.18.dylib',
        '/usr/local/lib/libmsodbcsql.17.dylib',
        '/usr/local/lib/libmsodbcsql.18.dylib',
        '{ODBC Driver 18 for SQL Server}',
        '{ODBC Driver 17 for SQL Server}',
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 17 for SQL Server'
    ]
    
    server = SERVER
    uid = USERNAME
    pwd = PASSWORD
    
    if not HAS_PYODBC or getattr(pyodbc, '_is_dummy', False):
        return None

    for drv in candidates:
        if not drv:
            continue
        if drv.startswith('/') and not os.path.exists(drv):
            continue
        try:
            test_conn = pyodbc.connect(
                f'DRIVER={drv};SERVER={server};DATABASE=master;UID={uid};PWD={pwd};TrustServerCertificate=yes;Autocommit=True',
                timeout=3,
                autocommit=True
            )
            test_conn.close()
            get_resolved_db_driver._resolved = drv
            DRIVER = drv
            return drv
        except Exception:
            continue

    get_resolved_db_driver._resolved = DRIVER
    return DRIVER

def get_db_connection(database_name=None):
    if HAS_PYODBC and not getattr(pyodbc, '_is_dummy', False):
        target_db = database_name or DATABASE
        active_driver = get_resolved_db_driver()
        if active_driver:
            try:
                conn_str = f'DRIVER={active_driver};SERVER={SERVER};DATABASE={target_db};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
                return pyodbc.connect(conn_str, autocommit=True)
            except Exception as e:
                if "Cannot open database" in str(e) or "database does not exist" in str(e).lower():
                    try:
                        master_conn = pyodbc.connect(
                            f'DRIVER={active_driver};SERVER={SERVER};DATABASE=master;UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True',
                            timeout=3,
                            autocommit=True
                        )
                        m_cursor = master_conn.cursor()
                        m_cursor.execute(f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{target_db}') CREATE DATABASE {target_db};")
                        master_conn.close()
                        return pyodbc.connect(f'DRIVER={active_driver};SERVER={SERVER};DATABASE={target_db};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True', autocommit=True)
                    except Exception as create_err:
                        print(f"⚠️ Error ensuring database {target_db}: {create_err}")

    # Fallback to local SQLite database if SQL Server is not reachable or not configured
    try:
        import sqlite3
        import shutil
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        is_serverless = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') or os.getenv('LAMBDA_TASK_ROOT'))
        
        if is_serverless:
            tmp_db_path = '/tmp/spherixclinic.db'
            src_db_path = os.path.join(project_root, 'spherixclinic.db')
            if not os.path.exists(tmp_db_path):
                if os.path.exists(src_db_path):
                    try:
                        shutil.copy2(src_db_path, tmp_db_path)
                    except Exception as cp_err:
                        print(f"⚠️ Error copying DB to /tmp: {cp_err}")
            sqlite_db_path = tmp_db_path
        else:
            sqlite_db_path = os.getenv('SQLITE_DB_PATH', os.path.join(project_root, 'spherixclinic.db'))

        if not os.path.exists(sqlite_db_path):
            try:
                import setup_db
                setup_db.setup_sqlite_tables()
                setup_db.seed_production_data()
            except Exception as se:
                print(f"⚠️ Note during SQLite initial seeding: {se}")

        conn = sqlite3.connect(sqlite_db_path, check_same_thread=False, isolation_level=None, timeout=30.0)
        try:
            if not is_serverless:
                conn.execute("PRAGMA journal_mode=WAL;")
            else:
                conn.execute("PRAGMA journal_mode=MEMORY;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        return conn
    except Exception as sq_err:
        print(f"⚠️ Error connecting to local SQLite database: {sq_err}")
        return None

def check_table_exists(cursor, table_name):
    """Checks if a table exists in SQLite or SQL Server without raising an operational error."""
    try:
        is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
        if is_sqlite_conn:
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            return cursor.fetchone() is not None
        else:
            cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            row = cursor.fetchone()
            return bool(row and row[0] == 1)
    except Exception:
        return False

def ensure_table_schema(cursor, table_name, sqlite_schema, sqlserver_schema):
    """Safely creates a table in SQLite or SQL Server without syntax errors."""
    try:
        is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
        if is_sqlite_conn:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({sqlite_schema})")
        else:
            cursor.execute(f"IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{table_name}' AND xtype='U') CREATE TABLE {table_name} ({sqlserver_schema})")
    except Exception as e:
        print(f"⚠️ ensure_table_schema note for {table_name}: {e}")

def ensure_sqlite_columns(cursor):
    """Ensures missing columns exist in SQLite database tables."""
    is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
    if not is_sqlite_conn:
        return
    # Hospitals table columns
    hosp_cols = [
        ('phone', 'TEXT'), ('city', 'TEXT'), ('state', 'TEXT'), ('address', 'TEXT'), ('logo_url', 'TEXT'),
        ('country', "TEXT DEFAULT 'India'"), ('currency', "TEXT DEFAULT 'INR'"), ('timezone', "TEXT DEFAULT 'IST (UTC+5:30)'"),
        ('total_beds', 'INTEGER DEFAULT 0'), ('available_beds', 'INTEGER DEFAULT 0'),
        ('icu_beds', 'INTEGER DEFAULT 0'), ('available_icu_beds', 'INTEGER DEFAULT 0'),
        ('general_bed_fee', 'REAL DEFAULT 1000.0'), ('icu_bed_fee', 'REAL DEFAULT 2500.0'),
        ('doctors_available', "TEXT DEFAULT 'Available'"), ('accreditation', "TEXT DEFAULT 'NABH / ISO 9001 Certified'"),
        ('international_services', 'TEXT'), ('is_international', 'INTEGER DEFAULT 0'),
        ('is_verified', 'INTEGER DEFAULT 1'), ('is_blocked', 'INTEGER DEFAULT 0'), ('is_hidden', 'INTEGER DEFAULT 0'),
        ('blood_stock', 'TEXT'), ('president_ceo', 'TEXT'), ('superintendent_name', 'TEXT'), ('zip_code', 'TEXT')
    ]
    for col, col_def in hosp_cols:
        try:
            cursor.execute(f"ALTER TABLE hospitals ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    # Staff table columns
    try:
        cursor.execute("ALTER TABLE staff ADD COLUMN profile_picture_url TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE staff ADD COLUMN hospital_id TEXT")
    except Exception:
        pass

    # Blood Donors table columns
    try:
        cursor.execute("ALTER TABLE blood_donors ADD COLUMN hospital_id TEXT")
    except Exception:
        pass

    # Organ Donors table columns
    try:
        cursor.execute("ALTER TABLE organ_donors ADD COLUMN hospital_id TEXT")
    except Exception:
        pass

    # Notifications table columns
    try:
        cursor.execute("ALTER TABLE notifications ADD COLUMN link TEXT")
    except Exception:
        pass


def migrate_legacy_schema(cursor):
    """Checks for existing INT ID columns and automatically migrates them to VARCHAR without losing data."""
    if hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3'):
        return
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

    # Check and add missing image columns across all relevant tables
    image_column_checks = [
        ('doctors', 'profile_picture_url', 'NVARCHAR(500) NULL'),
        ('patients', 'profile_picture_url', 'NVARCHAR(500) NULL'),
        ('staff', 'profile_picture_url', 'NVARCHAR(500) NULL'),
        ('blood_donors', 'profile_picture_url', 'NVARCHAR(500) NULL'),
        ('organ_donors', 'profile_picture_url', 'NVARCHAR(500) NULL'),
        ('hospitals', 'logo_url', 'NVARCHAR(500) NULL'),
        ('medicines', 'image_url', 'NVARCHAR(500) NULL')
    ]
    for tbl, col, col_def in image_column_checks:
        try:
            cursor.execute(f"IF OBJECT_ID('{tbl}', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
            if cursor.fetchone()[0] == 1:
                cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tbl}' AND COLUMN_NAME = '{col}'")
                if not cursor.fetchone():
                    print(f"⚠️  Adding missing '{col}' column to '{tbl}' table in SQL...")
                    cursor.execute(f"ALTER TABLE {tbl} ADD {col} {col_def}")
                    print(f"✅  Added '{col}' column to '{tbl}'.")
        except Exception as img_col_err:
            print(f"⚠️  Error checking/updating {tbl}.{col}: {img_col_err}")

    # 5. Check & Ensure Patient Dashboard Schema and Tables
    patient_columns = [
        ('clinical_record', 'NVARCHAR(MAX) NULL'),
        ('license_number', 'NVARCHAR(100) NULL'),
        ('blood_group', 'NVARCHAR(20) NULL'),
        ('height', 'NVARCHAR(20) NULL'),
        ('weight', 'NVARCHAR(20) NULL'),
        ('allergies', 'NVARCHAR(MAX) NULL'),
        ('existing_conditions', 'NVARCHAR(MAX) NULL'),
        ('current_medications', 'NVARCHAR(MAX) NULL'),
        ('emergency_contact_name', 'NVARCHAR(255) NULL'),
        ('emergency_contact_phone', 'NVARCHAR(50) NULL'),
        ('emergency_contact_relation', 'NVARCHAR(100) NULL'),
        ('insurance_provider', 'NVARCHAR(255) NULL'),
        ('insurance_policy_no', 'NVARCHAR(100) NULL'),
        ('date_of_birth', 'NVARCHAR(50) NULL'),
        ('occupation', 'NVARCHAR(100) NULL'),
        ('diet_preference', 'NVARCHAR(50) NULL'),
        ('smoker_status', 'NVARCHAR(50) NULL'),
        ('alcohol_status', 'NVARCHAR(50) NULL')
    ]
    try:
        cursor.execute("IF OBJECT_ID('patients', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 1:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patients'")
            existing_pat_cols = {col[0] for col in cursor.fetchall()}
            for col, col_def in patient_columns:
                if col not in existing_pat_cols:
                    print(f"⚠️  Adding missing '{col}' column to 'patients' table...")
                    cursor.execute(f"ALTER TABLE patients ADD {col} {col_def}")
                    print(f"✅  Added '{col}' column to 'patients'.")
    except Exception as pat_err:
        print(f"⚠️  Error checking/updating patient columns: {pat_err}")

    # Patient Vitals Table Columns
    try:
        cursor.execute("IF OBJECT_ID('patient_vitals', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 0:
            print("⚠️  Creating 'patient_vitals' table...")
            cursor.execute("""
                CREATE TABLE patient_vitals (
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
                )
            """)
            print("✅  Created 'patient_vitals' table.")
        else:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patient_vitals'")
            existing_vit_cols = {col[0] for col in cursor.fetchall()}
            vitals_cols = [
                ('spo2', 'INT NULL'),
                ('temperature', 'NVARCHAR(20) NULL'),
                ('height', 'NVARCHAR(20) NULL'),
                ('bmi', 'NVARCHAR(20) NULL'),
                ('blood_pressure', 'NVARCHAR(50) NULL'),
                ('notes', 'NVARCHAR(MAX) NULL'),
                ('date_recorded', 'DATETIME DEFAULT GETDATE()')
            ]
            for col, col_def in vitals_cols:
                if col not in existing_vit_cols:
                    cursor.execute(f"ALTER TABLE patient_vitals ADD {col} {col_def}")
    except Exception as vit_err:
        print(f"⚠️  Error checking/updating patient_vitals: {vit_err}")

    # Patient Medical Records Table
    try:
        cursor.execute("IF OBJECT_ID('patient_medical_records', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        has_table = cursor.fetchone()[0] == 1
        if has_table:
            cursor.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patient_medical_records' AND COLUMN_NAME = 'id'")
            id_type_row = cursor.fetchone()
            if id_type_row and id_type_row[0].lower() == 'int':
                print("⚠️  Migrating 'patient_medical_records' to VARCHAR primary key schema...")
                cursor.execute("DROP TABLE patient_medical_records")
                has_table = False

        if not has_table:
            print("⚠️  Creating 'patient_medical_records' table...")
            cursor.execute("""
                CREATE TABLE patient_medical_records (
                    id VARCHAR(50) PRIMARY KEY,
                    patient_id VARCHAR(50),
                    patient_name NVARCHAR(255) NULL,
                    title NVARCHAR(255),
                    record_type NVARCHAR(100),
                    record_date VARCHAR(50) NULL,
                    doctor_name NVARCHAR(255) NULL,
                    facility_name NVARCHAR(255) NULL,
                    description NVARCHAR(MAX) NULL,
                    file_path NVARCHAR(500) NULL,
                    file_name NVARCHAR(255) NULL,
                    file_type NVARCHAR(50) NULL,
                    file_size NVARCHAR(50) NULL,
                    shared_doctors_json NVARCHAR(MAX) NULL,
                    doctor_notes_json NVARCHAR(MAX) NULL,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            print("✅  Created 'patient_medical_records' table.")

        else:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'patient_medical_records'")
            existing_mr_cols = {row[0].lower() for row in cursor.fetchall()}
            mr_cols = [
                ('patient_name', 'NVARCHAR(255) NULL'),
                ('facility_name', 'NVARCHAR(255) NULL'),
                ('description', 'NVARCHAR(MAX) NULL'),
                ('file_name', 'NVARCHAR(255) NULL'),
                ('file_type', 'NVARCHAR(50) NULL'),
                ('file_size', 'NVARCHAR(50) NULL'),
                ('shared_doctors_json', 'NVARCHAR(MAX) NULL'),
                ('doctor_notes_json', 'NVARCHAR(MAX) NULL'),
            ]
            for col, col_def in mr_cols:
                if col.lower() not in existing_mr_cols:
                    cursor.execute(f"ALTER TABLE patient_medical_records ADD {col} {col_def}")
    except Exception as mr_err:
        print(f"⚠️  Error checking/updating patient_medical_records: {mr_err}")


    # Patient Emergency Contacts Table
    try:
        cursor.execute("IF OBJECT_ID('patient_emergency_contacts', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 0:
            print("⚠️  Creating 'patient_emergency_contacts' table...")
            cursor.execute("""
                CREATE TABLE patient_emergency_contacts (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    patient_id VARCHAR(50),
                    contact_name NVARCHAR(255),
                    relationship NVARCHAR(100),
                    phone NVARCHAR(50),
                    email NVARCHAR(255) NULL,
                    is_primary BIT DEFAULT 0,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            print("✅  Created 'patient_emergency_contacts' table.")
    except Exception as ec_err:
        print(f"⚠️  Error checking/updating patient_emergency_contacts: {ec_err}")

    # Patient Medication Schedules Table
    try:
        cursor.execute("IF OBJECT_ID('patient_medication_schedules', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 0:
            print("⚠️  Creating 'patient_medication_schedules' table...")
            cursor.execute("""
                CREATE TABLE patient_medication_schedules (
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
                )
            """)
            print("✅  Created 'patient_medication_schedules' table.")
    except Exception as ms_err:
        print(f"⚠️  Error checking/updating patient_medication_schedules: {ms_err}")

    # Patient Symptom Checks Table
    try:
        cursor.execute("IF OBJECT_ID('patient_symptom_checks', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 0:
            print("⚠️  Creating 'patient_symptom_checks' table...")
            cursor.execute("""
                CREATE TABLE patient_symptom_checks (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    patient_id VARCHAR(50),
                    primary_symptom NVARCHAR(255),
                    duration NVARCHAR(100),
                    urgency_level NVARCHAR(50),
                    possible_causes NVARCHAR(MAX) NULL,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            print("✅  Created 'patient_symptom_checks' table.")
    except Exception as sc_err:
        print(f"⚠️  Error checking/updating patient_symptom_checks: {sc_err}")

    # Patient AI Queries Table
    try:
        cursor.execute("IF OBJECT_ID('patient_ai_queries', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 0:
            print("⚠️  Creating 'patient_ai_queries' table...")
            cursor.execute("""
                CREATE TABLE patient_ai_queries (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    patient_id VARCHAR(50),
                    query_text NVARCHAR(MAX),
                    response_summary NVARCHAR(MAX),
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            print("✅  Created 'patient_ai_queries' table.")
    except Exception as ai_err:
        print(f"⚠️  Error checking/updating patient_ai_queries: {ai_err}")

    # Patient Lifestyle Logs Table
    try:
        cursor.execute("IF OBJECT_ID('patient_lifestyle_logs', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
        if cursor.fetchone()[0] == 0:
            print("⚠️  Creating 'patient_lifestyle_logs' table...")
            cursor.execute("""
                CREATE TABLE patient_lifestyle_logs (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    patient_id VARCHAR(50),
                    water_intake_liters FLOAT NULL,
                    sleep_hours FLOAT NULL,
                    calories_burned INT NULL,
                    mood NVARCHAR(50) NULL,
                    notes NVARCHAR(MAX) NULL,
                    logged_date DATE DEFAULT CAST(GETDATE() AS DATE),
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            print("✅  Created 'patient_lifestyle_logs' table.")
    except Exception as ls_err:
        print(f"⚠️  Error checking/updating patient_lifestyle_logs: {ls_err}")





def save_data():
    """Saves the current state of TEMP_DATA to the SQL Database and local JSON backup."""
    print("💾 Syncing data to SQL Database...")
    try:
        conn = get_db_connection()
        if conn is None:
            print("❌ SQL Database connection not available. Data cannot be saved.")
            return
        cursor = conn.cursor()
        ensure_sqlite_columns(cursor)

        def json_safe(val):
            if isinstance(val, (dict, list)):
                return json.dumps(val)
            return val

        # 1. Doctors
        cursor.execute("SELECT id FROM doctors")
        db_doc_rows = cursor.fetchall()
        db_doc_str_ids = {str(row[0]) for row in db_doc_rows}
        mem_doc_str_ids = {str(k) for k in TEMP_DATA['doctors'].keys()}
        for del_id in db_doc_str_ids - mem_doc_str_ids:
            cursor.execute("DELETE FROM doctors WHERE id = ?", (del_id,))
        

        # Sync doctor images separately
        try:
            cursor.execute("SELECT doctor_id FROM doctor_images")
            db_img_ids = {str(row[0]) for row in cursor.fetchall()}
            
            for doc_id, doc in TEMP_DATA['doctors'].items():
                if hasattr(doc, 'profile_picture_data') and doc.profile_picture_data:
                    doc_img_id_str = str(doc_id)
                    if doc_img_id_str in db_img_ids:
                        cursor.execute("UPDATE doctor_images SET image_data = ?, content_type = ? WHERE doctor_id = ?", 
                                       (doc.profile_picture_data, doc.profile_picture_content_type, doc_img_id_str))
                    else:
                        cursor.execute("INSERT INTO doctor_images (doctor_id, image_data, content_type) VALUES (?, ?, ?)", 
                                       (doc_img_id_str, doc.profile_picture_data, doc.profile_picture_content_type))
        except Exception as img_err:
            print(f"⚠️  Could not sync doctor_images table: {img_err}")

        for doc_id, doc in TEMP_DATA['doctors'].items():
            doc_id_str = str(doc_id)
            doc_hosp_id = getattr(doc, 'hospital_id', None)
            if doc_hosp_id is not None:
                try:
                    doc_hosp_id = int(str(doc_hosp_id).split('/')[-1]) if '/' in str(doc_hosp_id) else int(doc_hosp_id)
                except (ValueError, TypeError):
                    doc_hosp_id = None
                
            if doc_id_str in db_doc_str_ids:
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
                    doc_hosp_id, getattr(doc, 'hospital_approval_status', None),
                    doc_id_str
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
                    doc_id_str, doc.first_name, doc.last_name, doc.email, doc.password, doc.department, doc.phone, doc.specialization,
                    doc.address, doc.profile_picture_url, doc.bio, doc.hospital_name, doc.hospital_address, getattr(doc, 'city', None), doc.state,
                    doc.district, doc.pincode, getattr(doc, 'country', 'India'), doc.qualification, doc.license_number, doc.experience, doc.consultation_type,
                    doc.consultation_fee, doc.working_hours, json_safe(getattr(doc, 'languages_spoken', None)), json_safe(getattr(doc, 'social_links', {})), getattr(doc, 'is_verified', False),
                    getattr(doc, 'availability_status', 'available'),
                    doc_hosp_id, getattr(doc, 'hospital_approval_status', None)
                )

            try:
                cursor.execute(sql, values)
                try:
                    cursor.execute("UPDATE doctors SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(doc, 'is_blocked', False), getattr(doc, 'is_hidden', False), doc_id_str))
                except pyodbc.Error:
                    pass
            except Exception as e:
                pass

        # 2. Patients
        cursor.execute("SELECT id FROM patients")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['patients'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM patients WHERE id = ?", (del_id,))
        
        for p_id, p in TEMP_DATA['patients'].items():
            cr = getattr(p, 'clinical_record', {})
            if not isinstance(cr, dict):
                try: cr = json.loads(cr)
                except: cr = {}
            
            p_blood = getattr(p, 'blood_group', cr.get('blood_group'))
            p_height = getattr(p, 'height', cr.get('height'))
            p_weight = getattr(p, 'weight', cr.get('weight'))
            p_allergies = getattr(p, 'allergies', cr.get('allergies'))
            p_existing = getattr(p, 'existing_conditions', cr.get('existing_conditions'))
            p_meds = getattr(p, 'current_medications', cr.get('current_medications'))
            p_ec_name = getattr(p, 'emergency_contact_name', cr.get('emergency_contact_name'))
            p_ec_phone = getattr(p, 'emergency_contact_phone', cr.get('emergency_contact_phone'))
            p_ec_rel = getattr(p, 'emergency_contact_relation', cr.get('emergency_contact_relation'))
            p_ins_prov = getattr(p, 'insurance_provider', cr.get('insurance_provider'))
            p_ins_pol = getattr(p, 'insurance_policy_no', cr.get('insurance_policy_no'))
            p_dob = getattr(p, 'date_of_birth', cr.get('date_of_birth'))
            p_occ = getattr(p, 'occupation', cr.get('occupation'))
            p_diet = getattr(p, 'diet_preference', cr.get('diet_preference'))
            p_smoker = getattr(p, 'smoker_status', cr.get('smoker_status'))
            p_alcohol = getattr(p, 'alcohol_status', cr.get('alcohol_status'))
            p_lic = getattr(p, 'license_number', getattr(p, 'license_no', getattr(p, 'health_id', None)))

            if p_id in db_ids:
                try:
                    cursor.execute("""
                        UPDATE patients SET 
                            name=?, email=?, password=?, age=?, gender=?, profile_picture_url=?, phone=?, address=?, clinical_record=?,
                            license_number=?, blood_group=?, height=?, weight=?, allergies=?, existing_conditions=?, current_medications=?,
                            emergency_contact_name=?, emergency_contact_phone=?, emergency_contact_relation=?, insurance_provider=?,
                            insurance_policy_no=?, date_of_birth=?, occupation=?, diet_preference=?, smoker_status=?, alcohol_status=?
                        WHERE id=?
                    """, (
                        p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), json.dumps(cr),
                        p_lic, p_blood, p_height, p_weight, p_allergies, p_existing, p_meds,
                        p_ec_name, p_ec_phone, p_ec_rel, p_ins_prov,
                        p_ins_pol, p_dob, p_occ, p_diet, p_smoker, p_alcohol,
                        p_id
                    ))
                except pyodbc.Error:
                    try:
                        cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=?, profile_picture_url=?, phone=?, address=?, clinical_record=? WHERE id=?",
                                       (p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), json.dumps(cr), p_id))
                    except pyodbc.Error:
                        cursor.execute("UPDATE patients SET name=?, email=?, password=?, age=?, gender=?, profile_picture_url=? WHERE id=?",
                                       (p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), p_id))
            else:
                try:
                    cursor.execute("""
                        INSERT INTO patients (
                            id, name, email, password, age, gender, profile_picture_url, phone, address, clinical_record,
                            license_number, blood_group, height, weight, allergies, existing_conditions, current_medications,
                            emergency_contact_name, emergency_contact_phone, emergency_contact_relation, insurance_provider,
                            insurance_policy_no, date_of_birth, occupation, diet_preference, smoker_status, alcohol_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        p_id, p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), json.dumps(cr),
                        p_lic, p_blood, p_height, p_weight, p_allergies, p_existing, p_meds,
                        p_ec_name, p_ec_phone, p_ec_rel, p_ins_prov,
                        p_ins_pol, p_dob, p_occ, p_diet, p_smoker, p_alcohol
                    ))
                except pyodbc.Error:
                    try:
                        cursor.execute("INSERT INTO patients (id, name, email, password, age, gender, profile_picture_url, phone, address, clinical_record) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (p_id, p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None), getattr(p, 'phone', None), getattr(p, 'address', None), json.dumps(cr)))
                    except pyodbc.Error:
                        cursor.execute("INSERT INTO patients (id, name, email, password, age, gender, profile_picture_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                       (p_id, p.name, p.email, p.password, p.age, p.gender, getattr(p, 'profile_picture_url', None)))
            try:
                cursor.execute("UPDATE patients SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(p, 'is_blocked', False), getattr(p, 'is_hidden', False), p_id))
            except pyodbc.Error:
                pass

        # 3. Hospitals
        cursor.execute("SELECT id FROM hospitals")
        db_hosp_rows = cursor.fetchall()
        db_hosp_str_ids = {str(row[0]) for row in db_hosp_rows}
        mem_hosp_str_ids = {str(k) for k in TEMP_DATA['hospitals'].keys()}
        for del_id in db_hosp_str_ids - mem_hosp_str_ids:
            cursor.execute("DELETE FROM hospitals WHERE id = ?", (del_id,))
        
        for h_id, h in TEMP_DATA['hospitals'].items():
            h_id_str = str(h_id)
            if h_id_str in db_hosp_str_ids:
                try:
                    cursor.execute("""
                        UPDATE hospitals SET 
                            name=?, email=?, password=?, logo_url=?, 
                            country=?, city=?, state=?, address=?, phone=?, currency=?, timezone=?,
                            total_beds=?, available_beds=?, icu_beds=?, available_icu_beds=?, 
                            general_bed_fee=?, icu_bed_fee=?, doctors_available=?, 
                            is_verified=?, blood_stock=?,
                            president_ceo=?, superintendent_name=?, zip_code=?
                        WHERE id=?
                    """, (
                        h.name, h.email, h.password, h.logo_url,
                        getattr(h, 'country', 'India'), getattr(h, 'city', None), getattr(h, 'state', None), getattr(h, 'address', None), getattr(h, 'phone', None), getattr(h, 'currency', 'INR'), getattr(h, 'timezone', 'IST (UTC+5:30)'),
                        h.total_beds, h.available_beds, h.icu_beds, h.available_icu_beds,
                        getattr(h, 'general_bed_fee', 1000.0), getattr(h, 'icu_bed_fee', 2500.0), getattr(h, 'doctors_available', 'Available'),
                        getattr(h, 'is_verified', True), json_safe(getattr(h, 'blood_stock', {})),
                        getattr(h, 'president_ceo', None), getattr(h, 'superintendent_name', None), getattr(h, 'zip_code', None),
                        h_id_str
                    ))
                except Exception:
                    try:
                        cursor.execute("""
                            UPDATE hospitals SET 
                                name=?, email=?, password=?, logo_url=?, 
                                country=?, city=?, state=?, address=?, phone=?, currency=?, timezone=?,
                                total_beds=?, available_beds=?, icu_beds=?, available_icu_beds=?, 
                                general_bed_fee=?, icu_bed_fee=?, doctors_available=?, 
                                is_verified=?, blood_stock=?
                            WHERE id=?
                        """, (
                            h.name, h.email, h.password, h.logo_url,
                            getattr(h, 'country', 'India'), getattr(h, 'city', None), getattr(h, 'state', None), getattr(h, 'address', None), getattr(h, 'phone', None), getattr(h, 'currency', 'INR'), getattr(h, 'timezone', 'IST (UTC+5:30)'),
                            h.total_beds, h.available_beds, h.icu_beds, h.available_icu_beds,
                            getattr(h, 'general_bed_fee', 1000.0), getattr(h, 'icu_bed_fee', 2500.0), getattr(h, 'doctors_available', 'Available'),
                            getattr(h, 'is_verified', True), json_safe(getattr(h, 'blood_stock', {})),
                            h_id_str
                        ))
                    except Exception:
                        try:
                            cursor.execute("UPDATE hospitals SET name=?, email=?, password=?, logo_url=?, total_beds=?, available_beds=?, address=?, icu_beds=?, available_icu_beds=?, doctors_available=?, is_verified=?, blood_stock=? WHERE id=?",
                                           (h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available, getattr(h, 'is_verified', True), json_safe(getattr(h, 'blood_stock', {})), h_id_str))
                        except Exception:
                            cursor.execute("UPDATE hospitals SET name=?, email=?, password=?, logo_url=?, total_beds=?, available_beds=?, address=? WHERE id=?",
                                           (h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h_id_str))
            else:
                try:
                    cursor.execute("""
                        INSERT INTO hospitals (
                            id, name, email, password, logo_url, 
                            country, city, state, address, phone, currency, timezone,
                            total_beds, available_beds, icu_beds, available_icu_beds, 
                            general_bed_fee, icu_bed_fee, doctors_available, 
                            is_verified, president_ceo, superintendent_name, zip_code
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        h_id_str, h.name, h.email, h.password, h.logo_url,
                        getattr(h, 'country', 'India'), getattr(h, 'city', None), getattr(h, 'state', None), getattr(h, 'address', None), getattr(h, 'phone', None), getattr(h, 'currency', 'INR'), getattr(h, 'timezone', 'IST (UTC+5:30)'),
                        h.total_beds, h.available_beds, h.icu_beds, h.available_icu_beds,
                        getattr(h, 'general_bed_fee', 1000.0), getattr(h, 'icu_bed_fee', 2500.0), getattr(h, 'doctors_available', 'Available'),
                        getattr(h, 'is_verified', True), getattr(h, 'president_ceo', None), getattr(h, 'superintendent_name', None), getattr(h, 'zip_code', None)
                    ))
                except Exception:
                    try:
                        cursor.execute("INSERT INTO hospitals (id, name, email, password, logo_url, total_beds, available_beds, address, icu_beds, available_icu_beds, doctors_available, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (h_id_str, h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address, h.icu_beds, h.available_icu_beds, h.doctors_available, getattr(h, 'is_verified', True)))
                    except Exception:
                        cursor.execute("INSERT INTO hospitals (id, name, email, password, logo_url, total_beds, available_beds, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                       (h_id_str, h.name, h.email, h.password, h.logo_url, h.total_beds, h.available_beds, h.address))
            try:
                cursor.execute("UPDATE hospitals SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(h, 'is_blocked', False), getattr(h, 'is_hidden', False), h_id_str))
            except Exception:
                pass

        # 4. Staff
        cursor.execute("SELECT id FROM staff")
        db_raw_ids = {row[0] for row in cursor.fetchall()}
        db_ids_str = {str(r) for r in db_raw_ids}
        mem_keys_str = {str(k) for k in TEMP_DATA['staff'].keys()}

        for del_id in db_raw_ids:
            if str(del_id) not in mem_keys_str:
                cursor.execute("DELETE FROM staff WHERE id = ?", (del_id,))
        
        for s_id, s in TEMP_DATA['staff'].items():
            s_id_str = str(s_id)
            h_id = getattr(s, 'hospital_id', None)
            if not h_id and getattr(s, 'hospital_name', None):
                h_match = next((h for h in TEMP_DATA.get('hospitals', {}).values() if (getattr(h, 'name', '') or '').lower().strip() == s.hospital_name.lower().strip()), None)
                if h_match:
                    h_id = h_match.id
                    s.hospital_id = h_id

            target_id = s_id if s_id in db_raw_ids else (s_id_str if s_id_str in db_ids_str else None)
            if target_id is not None:
                try:
                    cursor.execute("UPDATE staff SET name=?, email=?, password=?, role=?, phone=?, hospital_name=?, last_login=?, created_at=?, profile_picture_url=?, hospital_id=? WHERE id=?", 
                                   (s.name, s.email, s.password, s.role, s.phone, s.hospital_name, getattr(s, 'last_login', None), getattr(s, 'created_at', utcnow()), getattr(s, 'profile_picture_url', None), h_id, target_id))
                except Exception:
                    cursor.execute("UPDATE staff SET name=?, email=?, password=?, role=?, phone=?, hospital_name=?, last_login=?, created_at=?, profile_picture_url=? WHERE id=?", 
                                   (s.name, s.email, s.password, s.role, s.phone, s.hospital_name, getattr(s, 'last_login', None), getattr(s, 'created_at', utcnow()), getattr(s, 'profile_picture_url', None), target_id))
            else:
                try:
                    cursor.execute("INSERT INTO staff (id, name, email, password, role, phone, hospital_name, last_login, created_at, profile_picture_url, hospital_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (s_id, s.name, s.email, s.password, s.role, s.phone, s.hospital_name, getattr(s, 'last_login', None), getattr(s, 'created_at', utcnow()), getattr(s, 'profile_picture_url', None), h_id))
                except Exception:
                    cursor.execute("INSERT INTO staff (id, name, email, password, role, phone, hospital_name, last_login, created_at, profile_picture_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (s_id, s.name, s.email, s.password, s.role, s.phone, s.hospital_name, getattr(s, 'last_login', None), getattr(s, 'created_at', utcnow()), getattr(s, 'profile_picture_url', None)))
            try:
                cursor.execute("UPDATE staff SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(s, 'is_blocked', False), getattr(s, 'is_hidden', False), s_id))
            except Exception:
                pass

        # 5. Appointments
        cursor.execute("SELECT id FROM appointments")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['appointments'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM appointments WHERE id = ?", (del_id,))
        
        for a_id, a in TEMP_DATA['appointments'].items():
            appt_date_val = str(a.appointment_date) if a.appointment_date is not None else None
            appt_time_val = a.appointment_time.strftime('%H:%M:%S') if hasattr(a.appointment_time, 'strftime') else (str(a.appointment_time) if a.appointment_time is not None else None)
            orig_date_val = str(a.original_appointment_date) if a.original_appointment_date is not None else None
            orig_time_val = a.original_appointment_time.strftime('%H:%M:%S') if hasattr(a.original_appointment_time, 'strftime') else (str(a.original_appointment_time) if a.original_appointment_time is not None else None)
            created_at_val = a.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(a.created_at, 'strftime') else (str(a.created_at) if a.created_at is not None else None)

            if a_id in db_ids:
                sql = """UPDATE appointments SET 
                    patient_name=?, doctor_id=?, patient_id=?, appointment_date=?, appointment_time=?, 
                    patient_age=?, patient_id_number=?, patient_phone=?, reason=?, status=?, 
                    created_at=?, original_appointment_date=?, original_appointment_time=?, 
                    document_path=?, prescription_path=? WHERE id=?"""
                values = (
                    a.patient_name, a.doctor_id, a.patient_id, appt_date_val, appt_time_val,
                    a.patient_age, a.patient_id_number, a.patient_phone, a.reason, a.status,
                    created_at_val, orig_date_val, orig_time_val,
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
                    a_id, a.patient_name, a.doctor_id, a.patient_id, appt_date_val, appt_time_val,
                    a.patient_age, a.patient_id_number, a.patient_phone, a.reason, a.status,
                    created_at_val, orig_date_val, orig_time_val,
                    a.document_path, a.prescription_path
                )
            cursor.execute(sql, values)

        # 6. Reviews
        cursor.execute("SELECT id FROM reviews")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['reviews'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM reviews WHERE id = ?", (del_id,))
        
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
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM messages WHERE id = ?", (del_id,))
        
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
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM orders WHERE id = ?", (del_id,))
        
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
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM blood_donors WHERE id = ?", (del_id,))
        
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
                        cursor.execute("UPDATE blood_donors SET name=?, email=?, phone=?, blood_group=?, age=?, city=?, password=?, last_donation=?, profile_picture_url=?, created_at=? WHERE id=?",
                                       (b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at, b_id))
            else:
                try:
                    cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, profile_picture_url, created_at, status, hospital_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (b_id, b.name, b.email, b.phone, b.blood_group, b.age, b.city, b.password, b.last_donation, getattr(b, 'profile_picture_url', None), b.created_at, getattr(b, 'status', 'pending'), getattr(b, 'hospital_id', None)))
                except pyodbc.Error:
                    try:
                        cursor.execute("INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation, profile_picture_url, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM organ_donors WHERE id = ?", (del_id,))
        
        for od_id, od in TEMP_DATA['organ_donors'].items():
            if od_id in db_ids:
                try:
                    cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, profile_picture_url=?, created_at=?, status=?, hospital_id=? WHERE id=?",
                                   (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, getattr(od, 'status', 'pending'), getattr(od, 'hospital_id', None), od_id))
                except pyodbc.Error:
                    cursor.execute("UPDATE organ_donors SET name=?, email=?, phone=?, organs=?, blood_group=?, age=?, city=?, password=?, profile_picture_url=?, created_at=? WHERE id=?",
                                   (od.name, od.email, od.phone, json_safe(od.organs), od.blood_group, od.age, od.city, od.password, getattr(od, 'profile_picture_url', None), od.created_at, od_id))
            else:
                try:
                    cursor.execute("DELETE FROM organ_donors WHERE email = ?", (od.email,))
                except pyodbc.Error:
                    pass
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
                            pass
            try:
                cursor.execute("UPDATE organ_donors SET is_blocked=?, is_hidden=? WHERE id=?", (getattr(od, 'is_blocked', False), getattr(od, 'is_hidden', False), od_id))
            except pyodbc.Error:
                pass
                
        # Organ Requests
        try:
            ensure_table_schema(
                cursor, 'organ_requests',
                "id INTEGER PRIMARY KEY, patient_id TEXT, patient_name TEXT, organ_needed TEXT, blood_group TEXT, urgency TEXT, status TEXT, hospital_id TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, patient_id VARCHAR(255), patient_name VARCHAR(255), organ_needed VARCHAR(255), blood_group VARCHAR(50), urgency VARCHAR(50), status VARCHAR(50), hospital_id VARCHAR(255), created_at DATETIME"
            )
            cursor.execute("SELECT id FROM organ_requests")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('organ_requests', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM organ_requests WHERE id = ?", (del_id,))
            
            for or_id, o_req in TEMP_DATA.get('organ_requests', {}).items():
                if or_id in db_ids:
                    cursor.execute("UPDATE organ_requests SET patient_id=?, patient_name=?, organ_needed=?, blood_group=?, urgency=?, status=?, hospital_id=?, created_at=? WHERE id=?",
                                   (o_req.patient_id, o_req.patient_name, o_req.organ_needed, o_req.blood_group, o_req.urgency, o_req.status, o_req.hospital_id, o_req.created_at, or_id))
                else:
                    cursor.execute("INSERT INTO organ_requests (id, patient_id, patient_name, organ_needed, blood_group, urgency, status, hospital_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (or_id, o_req.patient_id, o_req.patient_name, o_req.organ_needed, o_req.blood_group, o_req.urgency, o_req.status, o_req.hospital_id, o_req.created_at))
        except Exception as e:
            print(f"⚠️ Skipping organ_requests sync: {e}")

        # 10. Camps
        cursor.execute("SELECT id FROM camps")
        db_ids = {row[0] for row in cursor.fetchall()}
        mem_ids = set(TEMP_DATA['camps'].keys())
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM camps WHERE id = ?", (del_id,))
        
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
        for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM camp_registrations WHERE id = ?", (del_id,))
        
        for cr_id, cr in TEMP_DATA['camp_registrations'].items():
            if cr_id in db_ids:
                cursor.execute("UPDATE camp_registrations SET camp_name=?, name=?, email=?, phone=?, date=? WHERE id=?",
                               (cr['camp_name'], cr['name'], cr['email'], cr['phone'], cr['date'], cr_id))
            else:
                cursor.execute("INSERT INTO camp_registrations (id, camp_name, name, email, phone, date) VALUES (?, ?, ?, ?, ?, ?)",
                               (cr_id, cr['camp_name'], cr['name'], cr['email'], cr['phone'], cr['date']))

        # 12. Blood Stock
        for group, qty in TEMP_DATA['blood_stock'].items():
            cursor.execute("SELECT blood_group FROM blood_stock WHERE blood_group = ?", (group,))
            if cursor.fetchone():
                cursor.execute("UPDATE blood_stock SET quantity = ? WHERE blood_group = ?", (qty, group))
            else:
                cursor.execute("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", (group, qty))

        # 13. Bed Bookings
        try:
            ensure_table_schema(
                cursor, 'bed_bookings',
                "id INTEGER PRIMARY KEY, hospital_id TEXT, patient_id TEXT, patient_name TEXT, patient_phone TEXT, bed_type TEXT, reason TEXT, status TEXT, created_at TIMESTAMP, room_number TEXT",
                "id INT PRIMARY KEY, hospital_id VARCHAR(255), patient_id VARCHAR(255), patient_name VARCHAR(255), patient_phone VARCHAR(50), bed_type VARCHAR(50), reason VARCHAR(MAX), status VARCHAR(50), created_at DATETIME, room_number VARCHAR(50)"
            )
            cursor.execute("SELECT id FROM bed_bookings")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('bed_bookings', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM bed_bookings WHERE id = ?", (del_id,))
            
            for bb_id, bb in TEMP_DATA.get('bed_bookings', {}).items():
                if bb_id in db_ids:
                    try:
                        cursor.execute("UPDATE bed_bookings SET hospital_id=?, patient_id=?, patient_name=?, patient_phone=?, bed_type=?, reason=?, status=?, created_at=?, room_number=? WHERE id=?",
                                       (bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, getattr(bb, 'room_number', None), bb_id))
                    except Exception:
                        cursor.execute("UPDATE bed_bookings SET hospital_id=?, patient_id=?, patient_name=?, patient_phone=?, bed_type=?, reason=?, status=?, created_at=? WHERE id=?",
                                       (bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, bb_id))
                else:
                    try:
                        cursor.execute("INSERT INTO bed_bookings (id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, created_at, room_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (bb_id, bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at, getattr(bb, 'room_number', None)))
                    except Exception:
                        cursor.execute("INSERT INTO bed_bookings (id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (bb_id, bb.hospital_id, bb.patient_id, bb.patient_name, bb.patient_phone, bb.bed_type, bb.reason, bb.status, bb.created_at))
        except Exception as e:
            print(f"⚠️ Skipping bed_bookings sync: {e}")

        # 14. Activity Logs
        try:
            ensure_table_schema(
                cursor, 'activity_logs',
                "id INTEGER PRIMARY KEY, hospital_id TEXT, user_name TEXT, action TEXT, details TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, hospital_id VARCHAR(255), user_name VARCHAR(255), action VARCHAR(255), details VARCHAR(MAX), created_at DATETIME"
            )
            cursor.execute("SELECT id FROM activity_logs")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('activity_logs', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM activity_logs WHERE id = ?", (del_id,))
            
            for al_id, al in TEMP_DATA.get('activity_logs', {}).items():
                if al_id in db_ids:
                    cursor.execute("UPDATE activity_logs SET hospital_id=?, user_name=?, action=?, details=?, created_at=? WHERE id=?",
                                   (al.hospital_id, al.user_name, al.action, al.details, al.created_at, al_id))
                else:
                    cursor.execute("INSERT INTO activity_logs (id, hospital_id, user_name, action, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   (al_id, al.hospital_id, al.user_name, al.action, al.details, al.created_at))
        except Exception as e:
            print(f"⚠️ Skipping activity_logs sync: {e}")

        # 15. Settings
        try:
            ensure_table_schema(
                cursor, 'settings',
                "key TEXT PRIMARY KEY, value TEXT",
                "setting_key VARCHAR(255) PRIMARY KEY, setting_value NVARCHAR(MAX)"
            )
            is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
            cursor.execute("SELECT * FROM settings LIMIT 1" if is_sqlite_conn else "SELECT TOP 1 * FROM settings")
            cols = [c[0] for c in cursor.description] if cursor.description else ['key', 'value']
            key_col = 'setting_key' if 'setting_key' in cols else 'key'
            val_col = 'setting_value' if 'setting_value' in cols else 'value'
            if 'beds' in TEMP_DATA:
                TEMP_DATA['settings']['beds_data'] = json.dumps(TEMP_DATA['beds'])
            if 'staff_tasks' in TEMP_DATA:
                TEMP_DATA['settings']['staff_tasks'] = json.dumps(TEMP_DATA['staff_tasks'])
            if 'leave_requests' in TEMP_DATA:
                TEMP_DATA['settings']['leave_requests'] = json.dumps(TEMP_DATA['leave_requests'])
            if 'attendance_logs' in TEMP_DATA:
                TEMP_DATA['settings']['attendance_logs'] = json.dumps(TEMP_DATA['attendance_logs'])
            if 'blood_requests' in TEMP_DATA:
                TEMP_DATA['settings']['blood_requests'] = json.dumps(TEMP_DATA['blood_requests'])

            for key, val in TEMP_DATA.get('settings', {}).items():
                cursor.execute(f"SELECT 1 FROM settings WHERE [{key_col}] = ?", (key,))
                if cursor.fetchone():
                    cursor.execute(f"UPDATE settings SET [{val_col}] = ? WHERE [{key_col}] = ?", (val, key))
                else:
                    cursor.execute(f"INSERT INTO settings ([{key_col}], [{val_col}]) VALUES (?, ?)", (key, val))
        except Exception as e:
            print(f"⚠️ Skipping settings sync: {e}")


        # 17. Contact Messages
        try:
            ensure_table_schema(
                cursor, 'contact_messages',
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, address TEXT, message TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(255), email NVARCHAR(255), phone NVARCHAR(50), address NVARCHAR(MAX), message NVARCHAR(MAX), date DATETIME"
            )
            cursor.execute("DELETE FROM contact_messages")
            for msg in reversed(TEMP_DATA.get('contact_messages', [])):
                cursor.execute("INSERT INTO contact_messages (name, email, phone, address, message, date) VALUES (?, ?, ?, ?, ?, ?)",
                               (msg.get('name'), msg.get('email'), msg.get('phone'), msg.get('address'), msg.get('message'), msg.get('date')))
        except Exception as e:
            print(f"⚠️ Skipping contact_messages sync: {e}")

        # 18. Newsletter Subscribers
        try:
            ensure_table_schema(
                cursor, 'newsletter_subscribers',
                "email TEXT PRIMARY KEY, name TEXT, contact TEXT, interests TEXT, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "email NVARCHAR(255) PRIMARY KEY, name NVARCHAR(255) NULL, contact NVARCHAR(50) NULL, interests NVARCHAR(MAX) NULL, subscribed_at DATETIME DEFAULT GETDATE()"
            )
            
            # Ensure columns exist in case table was created previously with older schema
            try:
                is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
                if not is_sqlite_conn:
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
                cursor.execute("DELETE FROM newsletter_subscribers WHERE email = ?", (del_email,))
                
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
            print(f"⚠️ Skipping newsletter_subscribers sync: {e}")
            
        # 19. Medicines
        try:
            ensure_table_schema(
                cursor, 'medicines',
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, category TEXT, price REAL",
                "id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(255) UNIQUE, category NVARCHAR(100), price FLOAT"
            )
            cursor.execute("SELECT name FROM medicines")
            db_meds = {row[0] for row in cursor.fetchall()}
            mem_meds = {m['name'] for m in TEMP_DATA.get('medicines', [])}
            
            for del_med in db_meds - mem_meds:
                cursor.execute("DELETE FROM medicines WHERE name = ?", (del_med,))
                
            for m in TEMP_DATA.get('medicines', []):
                if m['name'] not in db_meds:
                    cursor.execute("INSERT INTO medicines (name, category, price) VALUES (?, ?, ?)", 
                                   (m['name'], m.get('category', 'General'), m.get('price', 0.0)))
                else:
                    cursor.execute("UPDATE medicines SET category=?, price=? WHERE name=?", 
                                   (m.get('category', 'General'), m.get('price', 0.0), m['name']))
        except Exception as e:
            print(f"⚠️ Skipping medicines sync: {e}")

        # 12. Patient Feedbacks
        try:
            if check_table_exists(cursor, 'patient_feedback'):
                cursor.execute("SELECT id FROM patient_feedback")
                db_ids = {row[0] for row in cursor.fetchall()}
                mem_ids = set(TEMP_DATA.get('feedbacks', {}).keys())
                for del_id in db_ids - mem_ids:
                    cursor.execute("DELETE FROM patient_feedback WHERE id = ?", (del_id,))
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
            if check_table_exists(cursor, 'doctor_opinions'):
                cursor.execute("SELECT doctor_id FROM doctor_opinions")
                db_doc_ids = {row[0] for row in cursor.fetchall()}
                mem_doc_ids = set(TEMP_DATA.get('doctor_opinions', {}).keys())
                for del_id in db_doc_ids - mem_doc_ids:
                    cursor.execute("DELETE FROM doctor_opinions WHERE doctor_id = ?", (del_id,))
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
            is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
            has_pv = False
            if is_sqlite_conn:
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='patient_vitals'")
                has_pv = cursor.fetchone() is not None
            else:
                cursor.execute("IF OBJECT_ID('patient_vitals', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
                has_pv = cursor.fetchone()[0] == 1

            if has_pv:
                cursor.execute("SELECT id FROM patient_vitals")
                db_vital_ids = {row[0] for row in cursor.fetchall()}
                mem_vital_ids = set(TEMP_DATA.get('patient_vitals', {}).keys())
                for del_id in db_vital_ids - mem_vital_ids:
                    cursor.execute("DELETE FROM patient_vitals WHERE id = ?", (del_id,))
                for v_id, vit in TEMP_DATA.get('patient_vitals', {}).items():
                    rec_at = getattr(vit, 'recorded_at', utcnow())
                    if isinstance(rec_at, str):
                        try: rec_at = datetime.fromisoformat(rec_at.replace('Z', '+00:00'))
                        except ValueError: rec_at = utcnow()
                    
                    target_pid = vit.patient_id
                    if target_pid not in TEMP_DATA.get('patients', {}):
                        if TEMP_DATA.get('patients'):
                            target_pid = list(TEMP_DATA['patients'].keys())[0]
                        else:
                            continue
                    
                    if v_id in db_vital_ids:
                        cursor.execute("UPDATE patient_vitals SET patient_id=?, weight=?, heart_rate=?, blood_sugar=?, systolic_bp=?, diastolic_bp=?, recorded_at=? WHERE id=?",
                                       (target_pid, vit.weight, vit.heart_rate, vit.blood_sugar, vit.systolic_bp, vit.diastolic_bp, rec_at, v_id))
                    else:
                        if not is_sqlite_conn:
                            cursor.execute("SET IDENTITY_INSERT patient_vitals ON")
                        cursor.execute("INSERT INTO patient_vitals (id, patient_id, weight, heart_rate, blood_sugar, systolic_bp, diastolic_bp, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                       (v_id, target_pid, vit.weight, vit.heart_rate, vit.blood_sugar, vit.systolic_bp, vit.diastolic_bp, rec_at))
                        if not is_sqlite_conn:
                            cursor.execute("SET IDENTITY_INSERT patient_vitals OFF")
        except Exception as e:
            print(f"⚠️ Skipping patient_vitals sync: {e}")

        # Sync Patient Medical Records
        try:
            is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
            has_pmr = False
            if is_sqlite_conn:
                cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='patient_medical_records'")
                has_pmr = cursor.fetchone() is not None
            else:
                cursor.execute("IF OBJECT_ID('patient_medical_records', 'U') IS NOT NULL SELECT 1 ELSE SELECT 0")
                has_pmr = cursor.fetchone()[0] == 1

            if has_pmr:
                cursor.execute("SELECT id FROM patient_medical_records")
                db_mr_ids = {str(row[0]) for row in cursor.fetchall()}
                mem_mr_ids = {str(k) for k in TEMP_DATA.get('medical_records', {}).keys()}
                for del_id in db_mr_ids - mem_mr_ids:
                    cursor.execute("DELETE FROM patient_medical_records WHERE id = ?", (del_id,))
                for mr_id, rec in TEMP_DATA.get('medical_records', {}).items():
                    mr_id_str = str(mr_id)
                    rec_created = getattr(rec, 'created_at', utcnow())
                    if isinstance(rec_created, str):
                        try: rec_created = datetime.fromisoformat(rec_created.replace('Z', '+00:00'))
                        except ValueError: rec_created = utcnow()

                    shared_json = json.dumps(getattr(rec, 'shared_with', []))
                    notes_json = json.dumps(getattr(rec, 'doctor_notes', {}))

                    if mr_id_str in db_mr_ids:
                        cursor.execute("""
                            UPDATE patient_medical_records SET 
                                patient_id=?, patient_name=?, title=?, record_type=?, record_date=?,
                                doctor_name=?, facility_name=?, description=?, file_path=?, file_name=?,
                                file_type=?, file_size=?, shared_doctors_json=?, doctor_notes_json=?, created_at=?
                            WHERE id=?
                        """, (
                            str(rec.patient_id), rec.patient_name, rec.title, rec.record_type, str(rec.record_date),
                            rec.doctor_name, rec.facility_name, rec.description, rec.file_path, rec.file_name,
                            rec.file_type, rec.file_size, shared_json, notes_json, rec_created, mr_id_str
                        ))
                    else:
                        cursor.execute("""
                            INSERT INTO patient_medical_records (
                                id, patient_id, patient_name, title, record_type, record_date,
                                doctor_name, facility_name, description, file_path, file_name,
                                file_type, file_size, shared_doctors_json, doctor_notes_json, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            mr_id_str, str(rec.patient_id), rec.patient_name, rec.title, rec.record_type, str(rec.record_date),
                            rec.doctor_name, rec.facility_name, rec.description, rec.file_path, rec.file_name,
                            rec.file_type, rec.file_size, shared_json, notes_json, rec_created
                        ))
        except Exception as e:
            print(f"⚠️ Skipping patient_medical_records sync: {e}")


        # Notifications
        try:
            ensure_table_schema(
                cursor, 'notifications',
                "id INTEGER PRIMARY KEY, user_id TEXT, user_type TEXT, message TEXT, link TEXT, status TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, user_id VARCHAR(255), user_type VARCHAR(50), message NVARCHAR(MAX), link NVARCHAR(MAX), status VARCHAR(50), created_at DATETIME"
            )
            cursor.execute("SELECT id FROM notifications")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('notifications', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM notifications WHERE id = ?", (del_id,))
            
            for notif_id, notif in TEMP_DATA.get('notifications', {}).items():
                u_id = getattr(notif, 'user_id', notif.get('user_id', 1) if isinstance(notif, dict) else 1)
                u_type = getattr(notif, 'user_type', notif.get('user_type', 'admin') if isinstance(notif, dict) else 'admin')
                msg = getattr(notif, 'message', notif.get('message', '') if isinstance(notif, dict) else '')
                lnk = getattr(notif, 'link', notif.get('link', None) if isinstance(notif, dict) else None)
                st = getattr(notif, 'status', notif.get('status', 'unread') if isinstance(notif, dict) else 'unread')
                c_at = getattr(notif, 'created_at', notif.get('created_at', None) if isinstance(notif, dict) else None) or utcnow()

                if notif_id in db_ids:
                    cursor.execute("UPDATE notifications SET user_id=?, user_type=?, message=?, link=?, status=?, created_at=? WHERE id=?", (u_id, u_type, msg, lnk, st, c_at, notif_id))
                else:
                    cursor.execute("INSERT INTO notifications (id, user_id, user_type, message, link, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (notif_id, u_id, u_type, msg, lnk, st, c_at))
        except Exception as e:
            print(f"⚠️ Skipping notifications sync: {e}")
        # Referrals
        try:
            ensure_table_schema(
                cursor, 'referrals',
                "id INTEGER PRIMARY KEY, patient_id TEXT, referring_doctor_id TEXT, referred_doctor_id TEXT, reason TEXT, status TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, patient_id VARCHAR(255), referring_doctor_id VARCHAR(255), referred_doctor_id VARCHAR(255), reason NVARCHAR(MAX), status VARCHAR(50), created_at DATETIME"
            )
            cursor.execute("SELECT id FROM referrals")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = set(TEMP_DATA.get('referrals', {}).keys())
            for del_id in db_ids - mem_ids: cursor.execute("DELETE FROM referrals WHERE id = ?", (del_id,))
            
            for ref_id, ref in TEMP_DATA.get('referrals', {}).items():
                if ref_id in db_ids:
                    cursor.execute("UPDATE referrals SET patient_id=?, referring_doctor_id=?, referred_doctor_id=?, reason=?, status=?, created_at=? WHERE id=?", (ref.patient_id, ref.referring_doctor_id, ref.referred_doctor_id, ref.reason, ref.status, ref.created_at, ref_id))
                else:
                    cursor.execute("INSERT INTO referrals (id, patient_id, referring_doctor_id, referred_doctor_id, reason, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (ref_id, ref.patient_id, ref.referring_doctor_id, ref.referred_doctor_id, ref.reason, ref.status, ref.created_at))
        except Exception as e:
            print(f"⚠️ Skipping referrals sync: {e}")
        # Sync Doctor Symptom Reviews
        try:
            if check_table_exists(cursor, 'doctor_symptom_reviews'):
                cursor.execute("SELECT id FROM doctor_symptom_reviews")
                db_rev_ids = {row[0] for row in cursor.fetchall()}
                
                mem_revs = TEMP_DATA.get('symptom_reviews', [])
                mem_rev_ids = {r['id'] for r in mem_revs if 'id' in r}
                
                for del_id in db_rev_ids - mem_rev_ids:
                    cursor.execute("DELETE FROM doctor_symptom_reviews WHERE id = ?", (del_id,))
                    
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

        # 22. Visitor Passes
        try:
            ensure_table_schema(
                cursor, 'visitor_passes',
                "id INTEGER PRIMARY KEY, hospital_id TEXT, pass_number TEXT, visitor_name TEXT, visitor_phone TEXT, patient_name TEXT, ward_room TEXT, relation TEXT, valid_hours TEXT, status TEXT, issued_at TIMESTAMP, issued_by TEXT",
                "id INT PRIMARY KEY, hospital_id VARCHAR(255), pass_number VARCHAR(50), visitor_name VARCHAR(255), visitor_phone VARCHAR(50), patient_name VARCHAR(255), ward_room VARCHAR(100), relation VARCHAR(100), valid_hours VARCHAR(50), status VARCHAR(50), issued_at DATETIME, issued_by VARCHAR(255)"
            )
            cursor.execute("SELECT id FROM visitor_passes")
            db_ids = {row[0] for row in cursor.fetchall()}
            mem_ids = {int(p['id']) for p in TEMP_DATA.get('visitor_passes', {}).values() if isinstance(p, dict) and 'id' in p}
            for del_id in db_ids - mem_ids:
                cursor.execute("DELETE FROM visitor_passes WHERE id = ?", (del_id,))
            for p_id, vp in TEMP_DATA.get('visitor_passes', {}).items():
                if isinstance(vp, dict) and 'id' in vp:
                    if int(vp['id']) in db_ids:
                        cursor.execute("""
                            UPDATE visitor_passes SET hospital_id=?, pass_number=?, visitor_name=?, visitor_phone=?, patient_name=?, ward_room=?, relation=?, valid_hours=?, status=?, issued_at=?, issued_by=?
                            WHERE id=?
                        """, (
                            vp.get('hospital_id'), vp.get('pass_number'), vp.get('visitor_name'), vp.get('visitor_phone'),
                            vp.get('patient_name'), vp.get('ward_room'), vp.get('relation'), vp.get('valid_hours'),
                            vp.get('status'), vp.get('issued_at'), vp.get('issued_by'), vp['id']
                        ))
                    else:
                        cursor.execute("""
                            INSERT INTO visitor_passes (id, hospital_id, pass_number, visitor_name, visitor_phone, patient_name, ward_room, relation, valid_hours, status, issued_at, issued_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            vp['id'], vp.get('hospital_id'), vp.get('pass_number'), vp.get('visitor_name'), vp.get('visitor_phone'),
                            vp.get('patient_name'), vp.get('ward_room'), vp.get('relation'), vp.get('valid_hours'),
                            vp.get('status'), vp.get('issued_at'), vp.get('issued_by')
                        ))
        except Exception as e:
            print(f"⚠️ Skipping visitor_passes sync: {e}")

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

def load_data():
    """Loads data from SQL Database into TEMP_DATA, rehydrating objects."""
    global TEMP_DATA
    print("🔄 Loading data from SQL Database...")

    try:
        conn = get_db_connection()
        if conn is None:
            print("⚠️ Database connection not available. Operating with in-memory dataset.")
            return
        cursor = conn.cursor()

        # Perform data-safe migration of schema and ensure all tables/columns exist
        migrate_legacy_schema(cursor)
        
        try:
            from spherix.services.diagnostic_db import init_diagnostic_schema
            init_diagnostic_schema()
        except Exception as diag_err:
            print(f"⚠️ Diagnostic init note: {diag_err}")

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

        # 2b. Pathology Labs
        try:
            from spherix.models.user import PathologyLab
            labs = fetch_dict("SELECT * FROM diagnostic_labs")
            TEMP_DATA['pathology_labs'] = {l['id']: PathologyLab(**l) for l in labs}
        except Exception as l_err:
            TEMP_DATA['pathology_labs'] = {}

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
        for s in stf:
            if not s.get('hospital_id') and s.get('hospital_name'):
                h_match = next((h for h in TEMP_DATA['hospitals'].values() if (getattr(h, 'name', '') or '').lower().strip() == s['hospital_name'].lower().strip()), None)
                if h_match:
                    s['hospital_id'] = h_match.id
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
            ensure_table_schema(
                cursor, 'organ_requests',
                "id INTEGER PRIMARY KEY, patient_id TEXT, patient_name TEXT, organ_needed TEXT, blood_group TEXT, urgency TEXT, status TEXT, hospital_id TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, patient_id VARCHAR(255), patient_name VARCHAR(255), organ_needed VARCHAR(255), blood_group VARCHAR(50), urgency VARCHAR(50), status VARCHAR(50), hospital_id VARCHAR(255), created_at DATETIME"
            )
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
            ensure_table_schema(
                cursor, 'bed_bookings',
                "id INTEGER PRIMARY KEY, hospital_id TEXT, patient_id TEXT, patient_name TEXT, patient_phone TEXT, bed_type TEXT, reason TEXT, status TEXT, created_at TIMESTAMP, room_number TEXT",
                "id INT PRIMARY KEY, hospital_id VARCHAR(255), patient_id VARCHAR(255), patient_name VARCHAR(255), patient_phone VARCHAR(50), bed_type VARCHAR(50), reason VARCHAR(MAX), status VARCHAR(50), created_at DATETIME, room_number VARCHAR(50)"
            )
            bbs = fetch_dict("SELECT * FROM bed_bookings")
            if 'bed_bookings' not in TEMP_DATA: TEMP_DATA['bed_bookings'] = {}
            TEMP_DATA['bed_bookings'] = {b['id']: BedBooking(**b) for b in bbs}
        except Exception:
            print("⚠️ Skipping bed_bookings load (table might not exist)")
            if 'bed_bookings' not in TEMP_DATA: TEMP_DATA['bed_bookings'] = {}

        # 14. Activity Logs
        try:
            ensure_table_schema(
                cursor, 'activity_logs',
                "id INTEGER PRIMARY KEY, hospital_id TEXT, user_name TEXT, action TEXT, details TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, hospital_id VARCHAR(255), user_name VARCHAR(255), action VARCHAR(255), details VARCHAR(MAX), created_at DATETIME"
            )
            alogs = fetch_dict("SELECT * FROM activity_logs")
            if 'activity_logs' not in TEMP_DATA: TEMP_DATA['activity_logs'] = {}
            TEMP_DATA['activity_logs'] = {l['id']: ActivityLog(**l) for l in alogs}
        except Exception:
            print("⚠️ Skipping activity_logs load (table might not exist)")
            if 'activity_logs' not in TEMP_DATA: TEMP_DATA['activity_logs'] = {}

        # 15. Settings
        try:
            ensure_table_schema(
                cursor, 'settings',
                "key TEXT PRIMARY KEY, value TEXT",
                "setting_key VARCHAR(255) PRIMARY KEY, setting_value NVARCHAR(MAX)"
            )
            setts = fetch_dict("SELECT * FROM settings")
            if 'settings' not in TEMP_DATA: 
                TEMP_DATA['settings'] = {
                    "hq_address": "Spherix Clinic Health Intelligence, Motihari\nBihar State, 845401\nIndia",
                    "contact_email": "support@spherixclinic.com",
                    "contact_phone": "+91 933 4325 920"
                }
            for s in setts:
                k = s.get('setting_key') or s.get('key')
                v = s.get('setting_value') or s.get('value')
                if k:
                    TEMP_DATA['settings'][k] = v
            try:
                if 'beds_data' in TEMP_DATA['settings']:
                    TEMP_DATA['beds'] = json.loads(TEMP_DATA['settings']['beds_data'])
                if 'staff_tasks' in TEMP_DATA['settings']:
                    raw_tasks = json.loads(TEMP_DATA['settings']['staff_tasks'])
                    TEMP_DATA['staff_tasks'] = {int(k) if str(k).isdigit() else k: v for k, v in raw_tasks.items()}
                if 'leave_requests' in TEMP_DATA['settings']:
                    raw_leave = json.loads(TEMP_DATA['settings']['leave_requests'])
                    TEMP_DATA['leave_requests'] = {int(k) if str(k).isdigit() else k: v for k, v in raw_leave.items()}
                if 'attendance_logs' in TEMP_DATA['settings']:
                    TEMP_DATA['attendance_logs'] = json.loads(TEMP_DATA['settings']['attendance_logs'])
                if 'blood_requests' in TEMP_DATA['settings']:
                    raw_br = json.loads(TEMP_DATA['settings']['blood_requests'])
                    TEMP_DATA['blood_requests'] = {int(k) if str(k).isdigit() else k: v for k, v in raw_br.items()}
            except Exception as e:
                print(f"⚠️ Error rehydrating staff entities: {e}")
        except Exception as e:
            print(f"⚠️ Skipping settings load: {e}")

        # 17. Contact Messages
        try:
            ensure_table_schema(
                cursor, 'contact_messages',
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, address TEXT, message TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(255), email NVARCHAR(255), phone NVARCHAR(50), address NVARCHAR(MAX), message NVARCHAR(MAX), date DATETIME"
            )
            c_msgs = fetch_dict("SELECT * FROM contact_messages ORDER BY id DESC")
            TEMP_DATA['contact_messages'] = []
            for c in c_msgs:
                TEMP_DATA['contact_messages'].append({
                    'name': c['name'], 'email': c['email'], 'phone': c['phone'], 'address': c['address'],
                    'message': c['message'], 'date': c['date'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(c['date'], datetime) else c['date']
                })
        except Exception as e:
            print(f"⚠️ Skipping contact_messages load: {e}")
            if 'contact_messages' not in TEMP_DATA: TEMP_DATA['contact_messages'] = []

        # 18. Newsletter Subscribers
        try:
            ensure_table_schema(
                cursor, 'newsletter_subscribers',
                "email TEXT PRIMARY KEY, name TEXT, contact TEXT, interests TEXT, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                "email NVARCHAR(255) PRIMARY KEY, name NVARCHAR(255) NULL, contact NVARCHAR(50) NULL, interests NVARCHAR(MAX) NULL, subscribed_at DATETIME DEFAULT GETDATE()"
            )
            
            # Ensure columns exist in case table was created previously with older schema
            try:
                is_sqlite_conn = hasattr(cursor, 'connection') and getattr(cursor.connection, '__module__', '').startswith('sqlite3')
                if not is_sqlite_conn:
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
            print(f"⚠️ Skipping newsletter_subscribers load: {e}")
            if 'newsletter_subscribers' not in TEMP_DATA: TEMP_DATA['newsletter_subscribers'] = []
            
        # 19. Medicines
        try:
            ensure_table_schema(
                cursor, 'medicines',
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, category TEXT, price REAL",
                "id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(255) UNIQUE, category NVARCHAR(100), price FLOAT"
            )
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
            if check_table_exists(cursor, 'patient_feedback'):
                fbs = fetch_dict("SELECT * FROM patient_feedback")
                TEMP_DATA['feedbacks'] = {fb['id']: Feedback(**fb) for fb in fbs}
            else:
                TEMP_DATA['feedbacks'] = {}
        except Exception as e:
            print(f"⚠️ Skipping feedback load: {e}")
            TEMP_DATA['feedbacks'] = {}

        # 21. Doctor Opinions
        try:
            if check_table_exists(cursor, 'doctor_opinions'):
                ops = fetch_dict("SELECT * FROM doctor_opinions")
                TEMP_DATA['doctor_opinions'] = {op['doctor_id']: op for op in ops}
            else:
                TEMP_DATA['doctor_opinions'] = {}
        except Exception as e:
            print(f"⚠️ Skipping doctor opinions load: {e}")
            TEMP_DATA['doctor_opinions'] = {}

        # 21b. Patient Vitals
        try:
            if check_table_exists(cursor, 'patient_vitals'):
                vits = fetch_dict("SELECT * FROM patient_vitals")
                TEMP_DATA['patient_vitals'] = {v['id']: PatientVital(**v) for v in vits}
            else:
                TEMP_DATA['patient_vitals'] = {}
        except Exception as e:
            print(f"⚠️ Skipping patient_vitals load: {e}")
            TEMP_DATA['patient_vitals'] = {}

        # 21c. Patient Medical Records
        try:
            if check_table_exists(cursor, 'patient_medical_records'):
                mr_rows = fetch_dict("SELECT * FROM patient_medical_records")
                TEMP_DATA['medical_records'] = {}
                for mr in mr_rows:
                    shared_list = []
                    if mr.get('shared_doctors_json'):
                        try:
                            shared_list = json.loads(mr['shared_doctors_json'])
                        except Exception:
                            shared_list = []
                    notes_dict = {}
                    if mr.get('doctor_notes_json'):
                        try:
                            notes_dict = json.loads(mr['doctor_notes_json'])
                        except Exception:
                            notes_dict = {}
                    rec_obj = PatientMedicalRecord(
                        id=mr['id'],
                        patient_id=mr.get('patient_id'),
                        patient_name=mr.get('patient_name', ''),
                        title=mr.get('title', 'Medical Record'),
                        record_type=mr.get('record_type', 'Lab Report'),
                        record_date=str(mr.get('record_date') or ''),
                        doctor_name=mr.get('doctor_name', ''),
                        facility_name=mr.get('facility_name', ''),
                        description=mr.get('description', ''),
                        file_path=mr.get('file_path', ''),
                        file_name=mr.get('file_name', ''),
                        file_type=mr.get('file_type', 'pdf'),
                        file_size=mr.get('file_size', '0 KB'),
                        shared_with=shared_list,
                        doctor_notes=notes_dict,
                        created_at=mr.get('created_at')
                    )
                    TEMP_DATA['medical_records'][rec_obj.id] = rec_obj
            else:
                TEMP_DATA['medical_records'] = {}
        except Exception as e:
            print(f"⚠️ Skipping patient_medical_records load: {e}")
            TEMP_DATA['medical_records'] = {}

        seed_initial_patient_medical_records()


        # Referrals
        try:
            ensure_table_schema(
                cursor, 'referrals',
                "id INTEGER PRIMARY KEY, patient_id TEXT, referring_doctor_id TEXT, referred_doctor_id TEXT, reason TEXT, status TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, patient_id VARCHAR(255), referring_doctor_id VARCHAR(255), referred_doctor_id VARCHAR(255), reason NVARCHAR(MAX), status VARCHAR(50), created_at DATETIME"
            )
            refs = fetch_dict("SELECT * FROM referrals")
            if 'referrals' not in TEMP_DATA: TEMP_DATA['referrals'] = {}
            TEMP_DATA['referrals'] = {r['id']: Referral(**r) for r in refs}
        except Exception:
            print("⚠️ Skipping referrals load (table might not exist)")
            if 'referrals' not in TEMP_DATA: TEMP_DATA['referrals'] = {}

        # Notifications
        try:
            ensure_table_schema(
                cursor, 'notifications',
                "id INTEGER PRIMARY KEY, user_id TEXT, user_type TEXT, message TEXT, link TEXT, status TEXT, created_at TIMESTAMP",
                "id INT PRIMARY KEY, user_id VARCHAR(255), user_type VARCHAR(50), message NVARCHAR(MAX), link NVARCHAR(MAX), status VARCHAR(50), created_at DATETIME"
            )
            notifs = fetch_dict("SELECT * FROM notifications")
            if 'notifications' not in TEMP_DATA: TEMP_DATA['notifications'] = {}
            TEMP_DATA['notifications'] = {n['id']: Notification(**n) for n in notifs}
        except Exception as e:
            print(f"⚠️ Skipping notifications load (table might not exist): {e}")
            if 'notifications' not in TEMP_DATA: TEMP_DATA['notifications'] = {}

        # 21c. Doctor Symptom Reviews
        try:
            if check_table_exists(cursor, 'doctor_symptom_reviews'):
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

        # 22. Visitor Passes
        try:
            ensure_table_schema(
                cursor, 'visitor_passes',
                "id INTEGER PRIMARY KEY, hospital_id TEXT, pass_number TEXT, visitor_name TEXT, visitor_phone TEXT, patient_name TEXT, ward_room TEXT, relation TEXT, valid_hours TEXT, status TEXT, issued_at TIMESTAMP, issued_by TEXT",
                "id INT PRIMARY KEY, hospital_id VARCHAR(255), pass_number VARCHAR(50), visitor_name VARCHAR(255), visitor_phone VARCHAR(50), patient_name VARCHAR(255), ward_room VARCHAR(100), relation VARCHAR(100), valid_hours VARCHAR(50), status VARCHAR(50), issued_at DATETIME, issued_by VARCHAR(255)"
            )
            vpasses = fetch_dict("SELECT * FROM visitor_passes")
            if 'visitor_passes' not in TEMP_DATA: TEMP_DATA['visitor_passes'] = {}
            for vp in vpasses:
                TEMP_DATA['visitor_passes'][vp['id']] = vp
        except Exception as e:
            print(f"⚠️ Skipping visitor_passes load: {e}")
            if 'visitor_passes' not in TEMP_DATA: TEMP_DATA['visitor_passes'] = {}

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

        # Simple integer IDs (Including bed_booking & visitor_pass)
        for entity in ['appointment', 'review', 'message', 'order', 'camp', 'camp_registration', 'bed_booking', 'activity_log', 'organ_request', 'patient_vital', 'referral', 'notification', 'visitor_pass']:
            dict_key = f"{entity}s" if entity != 'visitor_pass' else 'visitor_passes'
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

        # Ensure primary admin exists in memory and DB and purge any mock/test data
        chg_admin = setup_admin_user()
        chg_clean = cleanup_temporary_and_duplicate_data()
        init_auth_telemetry()
        if chg_admin or chg_clean:
            save_data()


        conn.close()
        print("✅ Data loaded from SQL successfully. Cleaned temporary and duplicate data.")
    except Exception as e:
        print(f"❌ Error loading data from SQL: {e}")

def seed_initial_patient_medical_records():
    """Seeds realistic initial medical records for registered patients if empty."""
    global TEMP_DATA
    if 'medical_records' not in TEMP_DATA:
        TEMP_DATA['medical_records'] = {}
    if len(TEMP_DATA['medical_records']) > 0:
        return
    
    patients = TEMP_DATA.get('patients', {})
    if not patients:
        return
    
    first_patient_id = list(patients.keys())[0]
    patient_obj = patients[first_patient_id]
    patient_name = getattr(patient_obj, 'name', '') or f"{getattr(patient_obj, 'first_name', '')} {getattr(patient_obj, 'last_name', '')}".strip() or "Registered Patient"
    
    # Pick a registered doctor ID if available (e.g. DOC/2026/001)
    doctors = TEMP_DATA.get('doctors', {})
    doc_id = list(doctors.keys())[0] if doctors else 'DOC/2026/001'
    doc_name = getattr(doctors.get(doc_id), 'name', 'Dr. Sunny Kushwaha') if doctors.get(doc_id) else 'Dr. Sunny Kushwaha'

    now_dt = datetime.now()
    records = [
        PatientMedicalRecord(
            id="REC-2026-001",
            patient_id=first_patient_id,
            patient_name=patient_name,
            title="Complete Diagnostic Blood & Lipid Panel",
            record_type="Lab Report",
            record_date=(now_dt - timedelta(days=5)).strftime('%Y-%m-%d'),
            doctor_name=doc_name,
            facility_name="Spherix Central Pathology Laboratory",
            description="Fasting blood glucose 94 mg/dL, HbA1c 5.4%, Total Cholesterol 178 mg/dL, HDL 52 mg/dL, LDL 102 mg/dL. All metabolic parameters within standard clinical reference ranges.",
            file_path="uploads/medical_records/sample_blood_report.pdf",
            file_name="CBC_Lipid_Panel_Report_2026.pdf",
            file_type="pdf",
            file_size="1.8 MB",
            shared_with=[str(doc_id)],
            doctor_notes={
                str(doc_id): {
                    "doctor_id": str(doc_id),
                    "doctor_name": doc_name,
                    "note": "Lipid profile and HbA1c are optimal. Continue balanced Mediterranean dietary routine.",
                    "created_at": (now_dt - timedelta(days=4)).strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        ),
        PatientMedicalRecord(
            id="REC-2026-002",
            patient_id=first_patient_id,
            patient_name=patient_name,
            title="Digital Chest Radiography (X-Ray PA View)",
            record_type="Radiology & Scan",
            record_date=(now_dt - timedelta(days=12)).strftime('%Y-%m-%d'),
            doctor_name=doc_name,
            facility_name="SMCH Imaging & Radiology Center",
            description="Bilateral lung fields clear. No focal consolidation, pneumothorax, or pleural effusion. Normal cardiac silhouette and mediastinal contours.",
            file_path="uploads/medical_records/sample_chest_xray.jpg",
            file_name="Chest_XRay_Digital_Scan.jpg",
            file_type="image",
            file_size="2.4 MB",
            shared_with=[str(doc_id)],
            doctor_notes={}
        ),
        PatientMedicalRecord(
            id="REC-2026-003",
            patient_id=first_patient_id,
            patient_name=patient_name,
            title="Post-Consultation Clinical Prescription",
            record_type="Prescription",
            record_date=(now_dt - timedelta(days=20)).strftime('%Y-%m-%d'),
            doctor_name=doc_name,
            facility_name="Spherix Outpatient Specialty Clinic",
            description="1. Tab. Paracetamol 650mg SOS for pyrexia\n2. Tab. Vitamin D3 60,000 IU once weekly x 8 weeks\n3. Daily hydration (3L) & adequate rest.",
            file_path="uploads/medical_records/sample_prescription.pdf",
            file_name="Official_Clinical_Prescription.pdf",
            file_type="pdf",
            file_size="640 KB",
            shared_with=[],
            doctor_notes={}
        )
    ]

    for rec in records:
        TEMP_DATA['medical_records'][rec.id] = rec

def cleanup_temporary_and_duplicate_data():
    """
    Removes mock, demo, and test data from TEMP_DATA,
    ensuring only the primary Administrator and genuine live user accounts exist.
    Purges test doctors, hospitals, staff, patients, and donors.
    Returns True if any items were purged or deduplicated.
    """
    global TEMP_DATA
    data_changed = False
    
    mock_doctor_emails = {
        'sarah.jenkins@spherixclinic.com', 'elena.rostova@spherixclinic.com',
        'kenji.sato@spherixclinic.com', 'aris.thorne@spherixclinic.com',
        'amelie.laurent@spherixclinic.com', 'liam.o.connor@spherixclinic.com',
        'hans.schmidt@spherixclinic.com', 'fatima.al-mansoor@spherixclinic.com',
        'marcus.vance@spherixclinic.com', 'olivia.williams@spherixclinic.com',
        'doctor@example.com', 'doctor@spherixclinic.com', 'chen@example.com',
        'marie@example.com', 'arun.verma@example.com'
    }
    mock_hospital_emails = {
        'contact@aiims.edu.in', 'care@apollohealthcity.in', 'fmri@fortishealthcare.com',
        'info@medanta.org', 'international@mayoclinic.org', 'globaldesk@clevelandclinic.ae',
        'international@mountelizabeth.sg', 'international@londonbridge.co.uk',
        'international@charite.de', 'globaldesk@uhn.ca', 'international@mh.org.au',
        'metro@example.com', 'hospital@spherixclinic.com', 'apollo@example.com',
        'stjude@example.com', 'hospital.test@spherixclinic.com', 'apollo.test@example.com'
    }
    mock_staff_emails = {
        'sumit@gmail.com', 'pooja.nurse@example.com', 'kevin.reception@example.com',
        'blood.smch@example.com', 'organ.smch@example.com', 'priya.reception@example.com',
        'bed.smch@example.com', 'nurse.smch@example.com', 'general.smch@example.com',
        'blood.apollo@example.com', 'organ.apollo@example.com', 'kevin.apollo@example.com',
        'bed.apollo@example.com', 'nurse.apollo@example.com', 'general.apollo@example.com',
        'blood.metro@example.com', 'organ.metro@example.com', 'bed.metro@example.com',
        'nurse.metro@example.com', 'general.metro@example.com', 'reception.smch@example.com'
    }
    mock_patient_emails = {
        'patient@spherixclinic.com', 'patient@example.com', 'emily.watson@example.com',
        'vikram@example.com', 'anita@example.com', 'rajesh.sharma@example.com',
        'test@example.com'
    }
    mock_blood_donor_emails = {
        'rohan.donor@spherixclinic.com', 'aarav.donor@spherixclinic.com',
        'sunny28skk@gmail.com', 'david.m@example.com', 'rohan.g@example.com',
        'sarah.lin@example.com'
    }
    mock_organ_donor_emails = {
        'aditya.organdonor@spherixclinic.com', 'ananya.organdonor@spherixclinic.com',
        'elena@example.com', 'ramesh.c@example.com'
    }

    # 1. Doctors (Preserve only genuine admin and non-test verified doctors)
    cleaned_doctors = {}
    seen_doc_emails = set()
    for doc_id, doc in list(TEMP_DATA.get('doctors', {}).items()):
        doc_email = (getattr(doc, 'email', '') or '').strip().lower()
        doc_fname = (getattr(doc, 'first_name', '') or '').strip().lower()
        doc_lname = (getattr(doc, 'last_name', '') or '').strip().lower()
        if doc_email in mock_doctor_emails or doc_email.endswith('@example.com') or doc_email.startswith('sarah.jenkins.') or (doc_fname == 'aarav' and doc_lname == 'verma'):
            data_changed = True
            continue
        if doc_email and doc_email in seen_doc_emails:
            data_changed = True
            continue
        if 'metro health' in (getattr(doc, 'hospital_name', '') or '').lower():
            doc.hospital_name = ''
            doc.hospital_id = ''
            data_changed = True
        if doc_email:
            seen_doc_emails.add(doc_email)
        cleaned_doctors[doc_id] = doc
    if len(cleaned_doctors) != len(TEMP_DATA.get('doctors', {})):
        data_changed = True
    TEMP_DATA['doctors'] = cleaned_doctors

    # 2. Patients (Purge test patients)
    cleaned_patients = {}
    seen_pat_emails = set()
    for pat_id, pat in list(TEMP_DATA.get('patients', {}).items()):
        pat_email = (getattr(pat, 'email', '') or '').strip().lower()
        pat_name = (getattr(pat, 'name', '') or '').strip().lower()
        if pat_email in mock_patient_emails or pat_email.endswith('@example.com') or pat_email.endswith('@spherixclinic.local') or 'test integration' in pat_name or getattr(pat, 'address', '') == "Verified Resident, City Portal":
            data_changed = True
            continue
        if pat_email and pat_email in seen_pat_emails:
            data_changed = True
            continue
        if pat_email:
            seen_pat_emails.add(pat_email)
        cleaned_patients[pat_id] = pat
    if len(cleaned_patients) != len(TEMP_DATA.get('patients', {})):
        data_changed = True
    TEMP_DATA['patients'] = cleaned_patients

    # 3. Hospitals (Purge test hospitals)
    cleaned_hospitals = {}
    seen_hosp_emails = set()
    for hosp_id, hosp in list(TEMP_DATA.get('hospitals', {}).items()):
        hosp_email = (getattr(hosp, 'email', '') or '').strip().lower()
        hosp_name = (getattr(hosp, 'name', '') or '').strip().lower()
        if hosp_email in mock_hospital_emails or hosp_email.endswith('@example.com') or 'metro health' in hosp_name or 'test' in hosp_email:
            data_changed = True
            continue
        if hosp_email and hosp_email in seen_hosp_emails:
            data_changed = True
            continue
        if hosp_email:
            seen_hosp_emails.add(hosp_email)
        cleaned_hospitals[hosp_id] = hosp
    if len(cleaned_hospitals) != len(TEMP_DATA.get('hospitals', {})):
        data_changed = True
    TEMP_DATA['hospitals'] = cleaned_hospitals

    # 4. Staff (Purge test staff)
    cleaned_staff = {}
    seen_staff_emails = set()
    for staff_id, staff in list(TEMP_DATA.get('staff', {}).items()):
        staff_email = (getattr(staff, 'email', '') or '').strip().lower()
        staff_hosp_name = (getattr(staff, 'hospital_name', '') or '').strip().lower()
        if staff_email in mock_staff_emails or staff_email.endswith('@example.com') or staff_email.endswith('@metro.com') or 'metro@' in staff_email:
            data_changed = True
            continue
        if staff_email and staff_email in seen_staff_emails:
            data_changed = True
            continue
        if staff_email:
            seen_staff_emails.add(staff_email)
        cleaned_staff[staff_id] = staff
    if len(cleaned_staff) != len(TEMP_DATA.get('staff', {})):
        data_changed = True
    TEMP_DATA['staff'] = cleaned_staff

    # 5. Blood Donors (Purge test blood donors)
    cleaned_blood_donors = {}
    seen_bd_emails = set()
    for bd_id, bd in list(TEMP_DATA.get('blood_donors', {}).items()):
        bd_email = (getattr(bd, 'email', '') or '').strip().lower()
        if bd_email in mock_blood_donor_emails or bd_email.endswith('@example.com') or str(bd_id) in ['BD/2026/001', 'BD/2026/002', 'BD/2026/003', 'BD/2026/004']:
            data_changed = True
            continue
        if bd_email and bd_email in seen_bd_emails:
            data_changed = True
            continue
        if bd_email:
            seen_bd_emails.add(bd_email)
        cleaned_blood_donors[bd_id] = bd
    if len(cleaned_blood_donors) != len(TEMP_DATA.get('blood_donors', {})):
        data_changed = True
    TEMP_DATA['blood_donors'] = cleaned_blood_donors

    # 6. Organ Donors (Purge test organ donors)
    cleaned_organ_donors = {}
    seen_od_emails = set()
    for od_id, od in list(TEMP_DATA.get('organ_donors', {}).items()):
        od_email = (getattr(od, 'email', '') or '').strip().lower()
        if od_email in mock_organ_donor_emails or od_email.endswith('@example.com') or str(od_id) in ['OD/2026/001', 'OD/2026/002']:
            data_changed = True
            continue
        if od_email and od_email in seen_od_emails:
            data_changed = True
            continue
        if od_email:
            seen_od_emails.add(od_email)
        cleaned_organ_donors[od_id] = od
    if len(cleaned_organ_donors) != len(TEMP_DATA.get('organ_donors', {})):
        data_changed = True
    TEMP_DATA['organ_donors'] = cleaned_organ_donors

    # 7. Purge test camps and registrations
    if 'camps' in TEMP_DATA:
        TEMP_DATA['camps'] = {k: v for k, v in TEMP_DATA['camps'].items() if getattr(v, 'id', None) not in [101, 102]}
    if 'camp_registrations' in TEMP_DATA:
        TEMP_DATA['camp_registrations'] = {k: v for k, v in TEMP_DATA['camp_registrations'].items() if getattr(v, 'email', '') not in mock_patient_emails and not (getattr(v, 'email', '') or '').endswith('@example.com')}

    return data_changed

def deduplicate_entities(entities):
    """Returns a list with duplicate entities removed preserving original order."""
    if not entities:
        return []
    unique_list = []
    seen_ids = set()
    seen_emails = set()
    for item in entities:
        item_id = str(getattr(item, 'id', ''))
        item_email = (getattr(item, 'email', '') or '').strip().lower()
        if item_id and item_id in seen_ids:
            continue
        if item_email and item_email in seen_emails:
            continue
        if item_id:
            seen_ids.add(item_id)
        if item_email:
            seen_emails.add(item_email)
        unique_list.append(item)
    return unique_list

def setup_admin_user():
    """
    Ensures the primary Administrator doctor account (admin@spherixclinic.com) exists.
    Returns True if data was changed, False otherwise.
    """
    admin_email = 'admin@spherixclinic.com'
    admin_password = os.getenv('ADMIN_BOOTSTRAP_PASSWORD', '').strip() or 'Admin@123'
    data_changed = False

    admin_user = next((doc for doc in TEMP_DATA['doctors'].values() if doc.email == admin_email), None)
    if not admin_user:
        admin_user = next((p for p in TEMP_DATA['patients'].values() if p.email == admin_email), None)

    if admin_user:
        if isinstance(admin_user, Doctor):
            if admin_user.first_name in ["Admin", "admin"] and admin_user.last_name in ["User", "user"]:
                admin_user.first_name = "Sunny"
                admin_user.last_name = "Kushwaha"
                data_changed = True
            if getattr(admin_user, 'profile_picture_url', None) != 'images/sunnykk.jpg':
                admin_user.profile_picture_url = 'images/sunnykk.jpg'
                data_changed = True
            admin_user.is_verified = True
        elif hasattr(admin_user, 'name') and admin_user.name in ["Admin User", "Admin"]:
            admin_user.name = "Sunny Kushwaha"
            if getattr(admin_user, 'profile_picture_url', None) != 'images/sunnykk.jpg':
                admin_user.profile_picture_url = 'images/sunnykk.jpg'
            data_changed = True
    else:
        year = datetime.now().year
        next_id_num = TEMP_DATA['next_ids']['doctor']
        new_id = f"DOC/{year}/{next_id_num:03d}"
        hashed_password = generate_password_hash(admin_password, method='pbkdf2:sha256:260000')
        new_admin_doctor = Doctor(
            id=new_id, first_name="Sunny", last_name="Kushwaha", is_verified=True,
            email=admin_email, password=hashed_password, department="Administration",
            phone='+91 933 4325 920',
            specialization='Chief Medical Officer & Administrator',
            profile_picture_url='images/sunnykk.jpg'
        )
        TEMP_DATA['doctors'][new_id] = new_admin_doctor
        TEMP_DATA['next_ids']['doctor'] += 1
        print(f"✅ Admin user '{admin_email}' (Dr. Sunny Kushwaha) created.")
        data_changed = True
    
    return data_changed

def setup_hospital_user():
    """No-op: Prevents auto-generating dummy hospital users."""
    return False

def setup_patient_user():
    """No-op: Prevents auto-generating dummy patient users."""
    return False

def setup_multi_hospital_and_staff():
    """No-op: Prevents auto-generating dummy multi-hospital staff and fixtures."""
    return False


def setup_international_network():
    return False



def create_notification(user_id, user_type, message, link=None):
    """Creates a notification, saves it in memory, and triggers save_data() to sync to the SQL database."""
    if 'notifications' not in TEMP_DATA:
        TEMP_DATA['notifications'] = {}
    if 'next_ids' not in TEMP_DATA:
        TEMP_DATA['next_ids'] = {}
    if 'notification' not in TEMP_DATA['next_ids']:
        keys = [int(k) for k in TEMP_DATA['notifications'].keys() if str(k).isdigit()]
        TEMP_DATA['next_ids']['notification'] = max([1] + keys) + 1
        
    notif_id = TEMP_DATA['next_ids']['notification']
    new_notif = Notification(
        id=notif_id,
        user_id=user_id,
        user_type=user_type,
        message=message,
        link=link,
        status='unread',
        created_at=utcnow()
    )
    TEMP_DATA['notifications'][notif_id] = new_notif
    TEMP_DATA['next_ids']['notification'] += 1
    save_data()
    return new_notif


sync_data_to_sql = save_data
load_data_from_sql = load_data


def normalize_role_key(role):
    r = (role or '').lower()
    if 'doc' in r: return 'doctor'
    if 'staff' in r: return 'staff'
    if 'hosp' in r: return 'hospital'
    if 'patient' in r: return 'patient'
    if 'blood' in r: return 'blood_donor'
    if 'organ' in r: return 'organ_donor'
    return 'general'


def parse_real_device_info(ua_str=None):
    """Extracts genuine human-readable OS and Browser from client User-Agent."""
    if not ua_str:
        try:
            from flask import request as flask_req
            if flask_req:
                ua_str = flask_req.headers.get('User-Agent', '')
        except Exception:
            pass
            
    if not ua_str or ua_str in ['Web Browser', 'System Agent']:
        return 'Web Client'
        
    ua = str(ua_str)
    os_name = 'Web Device'
    if 'Macintosh' in ua or 'Mac OS X' in ua:
        os_name = 'macOS'
    elif 'Windows' in ua:
        if 'NT 10.0' in ua: os_name = 'Windows 11/10'
        elif 'NT 6.3' in ua: os_name = 'Windows 8.1'
        elif 'NT 6.1' in ua: os_name = 'Windows 7'
        else: os_name = 'Windows'
    elif 'iPhone' in ua:
        os_name = 'iPhone • iOS'
    elif 'iPad' in ua:
        os_name = 'iPad • iPadOS'
    elif 'Android' in ua:
        os_name = 'Android'
    elif 'Linux' in ua:
        os_name = 'Linux'

    browser_name = 'Browser'
    if 'Edg/' in ua or 'Edge/' in ua:
        browser_name = 'Edge'
    elif 'Chrome/' in ua and 'Safari/' in ua:
        browser_name = 'Chrome'
    elif 'Safari/' in ua and 'Chrome/' not in ua:
        browser_name = 'Safari'
    elif 'Firefox/' in ua:
        browser_name = 'Firefox'
    elif 'OPR/' in ua or 'Opera/' in ua:
        browser_name = 'Opera'

    return f"{os_name} • {browser_name}"


def parse_real_location(user_id=None, role_key=None, user_email=None):
    """Retrieves real geographical address and clinic facility from the user's database profile."""
    if not user_id and not user_email:
        return 'Local Clinic Gateway'
        
    role_key = (role_key or '').lower()
    
    if role_key == 'doctor':
        doc = TEMP_DATA.get('doctors', {}).get(user_id) or next((d for d in TEMP_DATA.get('doctors', {}).values() if str(getattr(d, 'id', '')) == str(user_id) or getattr(d, 'email', '') == str(user_email)), None)
        if doc:
            parts = [getattr(doc, 'district', None) or getattr(doc, 'city', None), getattr(doc, 'state', None)]
            loc = ', '.join([str(p).strip() for p in parts if p])
            if loc: return loc
            if getattr(doc, 'hospital_name', None): return str(getattr(doc, 'hospital_name'))
            if getattr(doc, 'hospital_address', None): return str(getattr(doc, 'hospital_address'))
            if getattr(doc, 'address', None): return str(getattr(doc, 'address'))
    elif role_key == 'hospital':
        hosp = TEMP_DATA.get('hospitals', {}).get(user_id) or next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(getattr(h, 'id', '')) == str(user_id) or getattr(h, 'email', '') == str(user_email)), None)
        if hosp:
            parts = [getattr(hosp, 'city', None), getattr(hosp, 'state', None)]
            loc = ', '.join([str(p).strip() for p in parts if p])
            if loc: return loc
            if getattr(hosp, 'address', None): return str(getattr(hosp, 'address'))
    elif role_key == 'staff':
        st = TEMP_DATA.get('staff', {}).get(user_id) or next((s for s in TEMP_DATA.get('staff', {}).values() if str(getattr(s, 'id', '')) == str(user_id) or getattr(s, 'email', '') == str(user_email)), None)
        if st:
            addr = getattr(st, 'address', None) or getattr(st, 'city', None)
            if addr: return str(addr)
            dept = getattr(st, 'department', None) or getattr(st, 'role', None)
            if dept: return f"SMCH • {dept}"
    elif role_key == 'patient':
        pt = TEMP_DATA.get('patients', {}).get(user_id) or next((p for p in TEMP_DATA.get('patients', {}).values() if str(getattr(p, 'id', '')) == str(user_id) or getattr(p, 'email', '') == str(user_email)), None)
        if pt:
            parts = [getattr(pt, 'city', None) or getattr(pt, 'district', None), getattr(pt, 'state', None)]
            loc = ', '.join([str(p).strip() for p in parts if p])
            if loc: return loc
            if getattr(pt, 'address', None): return str(getattr(pt, 'address'))
    elif role_key == 'blood_donor':
        bd = TEMP_DATA.get('blood_donors', {}).get(user_id) or next((b for b in TEMP_DATA.get('blood_donors', {}).values() if str(getattr(b, 'id', '')) == str(user_id) or getattr(b, 'email', '') == str(user_email)), None)
        if bd:
            parts = [getattr(bd, 'city', None), getattr(bd, 'state', None)]
            loc = ', '.join([str(p).strip() for p in parts if p])
            if loc: return loc
            if getattr(bd, 'address', None): return str(getattr(bd, 'address'))
    elif role_key == 'organ_donor':
        od = TEMP_DATA.get('organ_donors', {}).get(user_id) or next((o for o in TEMP_DATA.get('organ_donors', {}).values() if str(getattr(o, 'id', '')) == str(user_id) or getattr(o, 'email', '') == str(user_email)), None)
        if od:
            parts = [getattr(od, 'city', None), getattr(od, 'state', None)]
            loc = ', '.join([str(p).strip() for p in parts if p])
            if loc: return loc
            if getattr(od, 'address', None): return str(getattr(od, 'address'))

    return 'Local Clinic Gateway'


def recalculate_live_auth_durations():
    """Recalculates real elapsed durations for all active and completed sessions."""
    global TEMP_DATA
    now_dt = utcnow()
    for log in TEMP_DATA.get('auth_activity_logs', []):
        if log.get('status') == 'Active' and log.get('login_time'):
            try:
                login_dt = datetime.strptime(log['login_time'], '%Y-%m-%d %H:%M:%S')
                diff_sec = max(0, int((now_dt - login_dt).total_seconds()))
                mins = diff_sec // 60
                hours = mins // 60
                rem_mins = mins % 60
                if hours > 0:
                    log['duration'] = f"Active Now ({hours}h {rem_mins}m)"
                elif mins > 0:
                    log['duration'] = f"Active Now ({mins}m)"
                else:
                    log['duration'] = "Active Now (< 1m)"
            except Exception:
                pass


def init_auth_telemetry():
    """Keeps authentication telemetry limited to recorded authentication events."""
    global TEMP_DATA
    if 'auth_activity_logs' not in TEMP_DATA:
        TEMP_DATA['auth_activity_logs'] = []

    # Older builds fabricated one active session for every registered account.
    # Remove those synthetic records so this monitor represents real logins only.
    synthetic_prefixes = ('AUTH-DOC-', 'AUTH-HOSP-', 'AUTH-STF-', 'AUTH-PAT-', 'AUTH-BD-', 'AUTH-OD-')
    logs = TEMP_DATA['auth_activity_logs']
    TEMP_DATA['auth_activity_logs'] = [
        log for log in logs
        if not str(log.get('id', '')).startswith(synthetic_prefixes)
    ]
    recalculate_live_auth_durations()
    return
        
    # If logs list is empty, initialize telemetry entries for real registered users only
    if len(TEMP_DATA['auth_activity_logs']) == 0:
        base_time = utcnow()
        real_logs = []
        
        # Real Doctors
        for d_id, doc in TEMP_DATA.get('doctors', {}).items():
            name = getattr(doc, 'name', '') or f"Dr. {getattr(doc, 'first_name', '')} {getattr(doc, 'last_name', '')}".strip()
            email = getattr(doc, 'email', '')
            pic = getattr(doc, 'profile_picture_url', None) or getattr(doc, 'image', None) or ('images/sunnykk.jpg' if email == 'admin@spherixclinic.com' else None)
            loc = parse_real_location(d_id, 'doctor', email)
            real_logs.append({
                "id": f"AUTH-DOC-{str(d_id).replace('/', '-')}",
                "user_id": str(d_id),
                "user_name": name,
                "user_email": email,
                "role": "Doctor",
                "role_key": "doctor",
                "profile_picture_url": pic,
                "action": "Active Session",
                "status": "Active",
                "ip_address": "127.0.0.1",
                "location": loc,
                "device": "macOS • Chrome",
                "login_time": (base_time - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'),
                "logout_time": None,
                "duration": "Active Now (45m)",
                "details": f"Doctor console active ({getattr(doc, 'specialization', 'General Medicine')})",
                "created_at": (base_time - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S')
            })
            
        # Real Hospitals
        for h_id, hosp in TEMP_DATA.get('hospitals', {}).items():
            name = getattr(hosp, 'name', 'Hospital Facility')
            email = getattr(hosp, 'email', '')
            pic = getattr(hosp, 'logo_url', None) or getattr(hosp, 'image', None) or getattr(hosp, 'profile_picture_url', None)
            loc = parse_real_location(h_id, 'hospital', email)
            real_logs.append({
                "id": f"AUTH-HOSP-{str(h_id).replace('/', '-')}",
                "user_id": str(h_id),
                "user_name": name,
                "user_email": email,
                "role": "Hospital",
                "role_key": "hospital",
                "profile_picture_url": pic,
                "action": "Active Session",
                "status": "Active",
                "ip_address": "192.168.1.100",
                "location": loc,
                "device": "Linux Terminal • Chrome",
                "login_time": (base_time - timedelta(hours=2, minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),
                "logout_time": None,
                "duration": "Active Now (2h 10m)",
                "details": "Hospital administrative portal connected",
                "created_at": (base_time - timedelta(hours=2, minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
            })

        # Real Staff
        for s_id, st in TEMP_DATA.get('staff', {}).items():
            name = getattr(st, 'name', '') or f"{getattr(st, 'first_name', '')} {getattr(st, 'last_name', '')}".strip()
            email = getattr(st, 'email', '')
            role_title = getattr(st, 'role', 'Staff') or 'Staff'
            pic = getattr(st, 'profile_picture_url', None) or getattr(st, 'image', None) or getattr(st, 'avatar', None)
            loc = parse_real_location(s_id, 'staff', email)
            real_logs.append({
                "id": f"AUTH-STF-{s_id}",
                "user_id": str(s_id),
                "user_name": name,
                "user_email": email,
                "role": f"Staff ({role_title})",
                "role_key": "staff",
                "profile_picture_url": pic,
                "action": "Active Session",
                "status": "Active",
                "ip_address": "192.168.1.105",
                "location": loc,
                "device": "Windows 11 • Edge",
                "login_time": (base_time - timedelta(hours=1, minutes=30)).strftime('%Y-%m-%d %H:%M:%S'),
                "logout_time": None,
                "duration": "Active Now (1h 30m)",
                "details": f"Staff session for {role_title}",
                "created_at": (base_time - timedelta(hours=1, minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
            })

        # Real Patients
        for p_id, pt in TEMP_DATA.get('patients', {}).items():
            name = getattr(pt, 'name', '') or f"{getattr(pt, 'first_name', '')} {getattr(pt, 'last_name', '')}".strip()
            email = getattr(pt, 'email', '')
            pic = getattr(pt, 'profile_picture_url', None) or getattr(pt, 'image', None)
            loc = parse_real_location(p_id, 'patient', email)
            real_logs.append({
                "id": f"AUTH-PAT-{p_id}",
                "user_id": str(p_id),
                "user_name": name,
                "user_email": email,
                "role": "Patient",
                "role_key": "patient",
                "profile_picture_url": pic,
                "action": "Active Session",
                "status": "Active",
                "ip_address": "103.21.244.10",
                "location": loc,
                "device": "iPhone • Mobile Safari",
                "login_time": (base_time - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'),
                "logout_time": None,
                "duration": "Active Now (20m)",
                "details": "Patient portal session",
                "created_at": (base_time - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')
            })

        # Real Blood Donors
        for b_id, bd in TEMP_DATA.get('blood_donors', {}).items():
            name = getattr(bd, 'name', 'Blood Donor')
            email = getattr(bd, 'email', '')
            pic = getattr(bd, 'profile_picture_url', None) or getattr(bd, 'image', None)
            loc = parse_real_location(b_id, 'blood_donor', email)
            real_logs.append({
                "id": f"AUTH-BD-{b_id}",
                "user_id": str(b_id),
                "user_name": name,
                "user_email": email,
                "role": "Blood Donor",
                "role_key": "blood_donor",
                "profile_picture_url": pic,
                "action": "Active Session",
                "status": "Active",
                "ip_address": "182.72.10.45",
                "location": loc,
                "device": "Android • Chrome",
                "login_time": (base_time - timedelta(minutes=35)).strftime('%Y-%m-%d %H:%M:%S'),
                "logout_time": None,
                "duration": "Active Now (35m)",
                "details": "Blood donation network registry",
                "created_at": (base_time - timedelta(minutes=35)).strftime('%Y-%m-%d %H:%M:%S')
            })

        # Real Organ Donors
        for o_id, od in TEMP_DATA.get('organ_donors', {}).items():
            name = getattr(od, 'name', 'Organ Donor')
            email = getattr(od, 'email', '')
            pic = getattr(od, 'profile_picture_url', None) or getattr(od, 'image', None)
            loc = parse_real_location(o_id, 'organ_donor', email)
            real_logs.append({
                "id": f"AUTH-OD-{o_id}",
                "user_id": str(o_id),
                "user_name": name,
                "user_email": email,
                "role": "Organ Donor",
                "role_key": "organ_donor",
                "profile_picture_url": pic,
                "action": "Active Session",
                "status": "Active",
                "ip_address": "157.34.89.20",
                "location": loc,
                "device": "macOS • Safari",
                "login_time": (base_time - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
                "logout_time": None,
                "duration": "Active Now (15m)",
                "details": "Organ donor registry verification",
                "created_at": (base_time - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
            })

        TEMP_DATA['auth_activity_logs'] = real_logs
    else:
        recalculate_live_auth_durations()


def log_auth_activity(user_id, user_name, user_email, role, action, ip_address=None, user_agent=None, details=None, status='Active', duration=None, login_time=None, logout_time=None, profile_picture_url=None, location=None):
    """Logs a real authentication event (login, logout, active session, failed login, etc.)."""
    init_auth_telemetry()
    now_dt = utcnow()
    log_id = f"AUTH-{int(now_dt.timestamp())}-{len(TEMP_DATA['auth_activity_logs']) + 1}"
    
    # Try getting real client IP and User-Agent from Flask request context if available
    try:
        from flask import request as flask_req
        if flask_req:
            if not ip_address:
                ip_address = flask_req.headers.get('CF-Connecting-IP') or flask_req.headers.get('X-Real-IP') or flask_req.headers.get('X-Forwarded-For') or flask_req.remote_addr
                if ip_address and ',' in ip_address:
                    ip_address = ip_address.split(',')[0].strip()
            if not user_agent:
                user_agent = flask_req.headers.get('User-Agent', '')
    except Exception:
        pass

    real_device = parse_real_device_info(user_agent)
    role_key = normalize_role_key(role)
    real_location = location or parse_real_location(user_id, role_key, user_email)
    
    # Automatic lookup of profile picture if not passed
    if not profile_picture_url and user_id:
        if role_key == 'doctor':
            doc = TEMP_DATA.get('doctors', {}).get(user_id) or next((d for d in TEMP_DATA.get('doctors', {}).values() if str(getattr(d, 'id', '')) == str(user_id) or getattr(d, 'email', '') == str(user_email)), None)
            if doc: profile_picture_url = getattr(doc, 'profile_picture_url', None) or getattr(doc, 'image', None) or ('images/sunnykk.jpg' if getattr(doc, 'email', '') == 'admin@spherixclinic.com' else None)
        elif role_key == 'hospital':
            hosp = TEMP_DATA.get('hospitals', {}).get(user_id) or next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(getattr(h, 'id', '')) == str(user_id) or getattr(h, 'email', '') == str(user_email)), None)
            if hosp: profile_picture_url = getattr(hosp, 'logo_url', None) or getattr(hosp, 'image', None) or getattr(hosp, 'profile_picture_url', None)
        elif role_key == 'staff':
            st = TEMP_DATA.get('staff', {}).get(user_id) or next((s for s in TEMP_DATA.get('staff', {}).values() if str(getattr(s, 'id', '')) == str(user_id) or getattr(s, 'email', '') == str(user_email)), None)
            if st: profile_picture_url = getattr(st, 'profile_picture_url', None) or getattr(st, 'image', None) or getattr(st, 'avatar', None)
        elif role_key == 'patient':
            pt = TEMP_DATA.get('patients', {}).get(user_id) or next((p for p in TEMP_DATA.get('patients', {}).values() if str(getattr(p, 'id', '')) == str(user_id) or getattr(p, 'email', '') == str(user_email)), None)
            if pt: profile_picture_url = getattr(pt, 'profile_picture_url', None) or getattr(pt, 'image', None)
        elif role_key == 'blood_donor':
            bd = TEMP_DATA.get('blood_donors', {}).get(user_id) or next((b for b in TEMP_DATA.get('blood_donors', {}).values() if str(getattr(b, 'id', '')) == str(user_id) or getattr(b, 'email', '') == str(user_email)), None)
            if bd: profile_picture_url = getattr(bd, 'profile_picture_url', None) or getattr(bd, 'image', None)
        elif role_key == 'organ_donor':
            od = TEMP_DATA.get('organ_donors', {}).get(user_id) or next((o for o in TEMP_DATA.get('organ_donors', {}).values() if str(getattr(o, 'id', '')) == str(user_id) or getattr(o, 'email', '') == str(user_email)), None)
            if od: profile_picture_url = getattr(od, 'profile_picture_url', None) or getattr(od, 'image', None)

    dur = duration
    if not dur:
        if action in ['LOGIN', 'Active Session', 'Successful Login'] or status == 'Active':
            dur = 'Active Now (< 1m)'
        elif action in ['FAILED_LOGIN', 'Failed Login']:
            dur = '0m'
        else:
            dur = 'Active Now'

    log_entry = {
        'id': log_id,
        'user_id': str(user_id or 'GUEST'),
        'user_name': user_name or 'User',
        'user_email': user_email or 'N/A',
        'role': role or 'General User',
        'role_key': role_key,
        'profile_picture_url': profile_picture_url,
        'action': action,
        'status': status,
        'ip_address': ip_address or '127.0.0.1',
        'location': real_location,
        'device': real_device,
        'details': details or f"{role} {action} completed successfully.",
        'login_time': login_time or now_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'logout_time': logout_time,
        'duration': dur,
        'created_at': now_dt.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    TEMP_DATA['auth_activity_logs'].insert(0, log_entry)
    if len(TEMP_DATA['auth_activity_logs']) > 500:
        TEMP_DATA['auth_activity_logs'] = TEMP_DATA['auth_activity_logs'][:500]

    if status == 'Active' and action in ('LOGIN', 'Active Session', 'Successful Login'):
        try:
            from flask import has_request_context, session
            if has_request_context():
                session['auth_session_id'] = log_id
        except Exception:
            pass
        
    return log_id


def log_user_logout(user_id=None, user_email=None, role=None):
    """Updates active session to completed and records precise logout timestamp & duration."""
    global TEMP_DATA
    if 'auth_activity_logs' not in TEMP_DATA:
        return
    now_dt = utcnow()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    try:
        from flask import has_request_context, session
        auth_session_id = session.get('auth_session_id') if has_request_context() else None
    except Exception:
        auth_session_id = None
    
    matched = False
    for log in TEMP_DATA['auth_activity_logs']:
        if auth_session_id and str(log.get('id')) != str(auth_session_id):
            continue
        if (user_id and str(log.get('user_id')) == str(user_id)) or (user_email and str(log.get('user_email', '')).lower() == str(user_email).lower()):
            if log.get('status') == 'Active':
                log['status'] = 'Completed'
                log['action'] = 'Normal Logout'
                log['logout_time'] = now_str
                # Calculate elapsed duration
                try:
                    login_dt = datetime.strptime(log['login_time'], '%Y-%m-%d %H:%M:%S')
                    diff_seconds = max(0, int((now_dt - login_dt).total_seconds()))
                    mins = diff_seconds // 60
                    hours = mins // 60
                    rem_mins = mins % 60
                    if hours > 0:
                        log['duration'] = f"{hours}h {rem_mins}m"
                    elif mins > 0:
                        log['duration'] = f"{mins}m"
                    else:
                        log['duration'] = "< 1m"
                except Exception:
                    log['duration'] = 'Completed'
                matched = True
                break
                
    if not matched and (user_id or user_email):
        log_auth_activity(
            user_id=user_id,
            user_name=str(user_email or user_id),
            user_email=user_email,
            role=role or 'User',
            action='Normal Logout',
            status='Completed',
            duration='1m',
            logout_time=now_str
        )


def get_auth_telemetry_stats():
    """Calculates live telemetry metrics dynamically from real activity logs."""
    init_auth_telemetry()
    recalculate_live_auth_durations()
    logs = TEMP_DATA.get('auth_activity_logs', [])
    
    now_dt = utcnow()
    day_ago = now_dt - timedelta(hours=24)

    def occurred_within_day(log):
        timestamp = log.get('created_at') or log.get('login_time')
        try:
            return datetime.strptime(str(timestamp), '%Y-%m-%d %H:%M:%S') >= day_ago
        except (TypeError, ValueError):
            return False

    recent_logs = [log for log in logs if occurred_within_day(log)]
    active_sessions_count = sum(1 for log in logs if log.get('status') == 'Active')
    failed_count = sum(1 for log in recent_logs if log.get('status') == 'Failed' or 'Failed' in str(log.get('action', '')))
    successful_count = sum(1 for log in recent_logs if str(log.get('action', '')).lower() in ('login', 'successful login'))
    suspicious_count = sum(1 for log in recent_logs if log.get('status') in ['Blocked', 'Quarantined'] or 'Suspicious' in str(log.get('action', '')))
    password_resets_count = sum(1 for log in recent_logs if 'PASSWORD_RESET' in str(log.get('action', '')) or 'Password Reset' in str(log.get('action', '')))
    duration_minutes = []
    for log in logs:
        if log.get('status') == 'Active':
            continue
        match = re.search(r'(\d+)h\s*(\d+)?m|(?<!h\s)(\d+)m', str(log.get('duration', '')))
        if match:
            duration_minutes.append(int(match.group(1)) * 60 + int(match.group(2) or 0) if match.group(1) else int(match.group(3)))
    average_minutes = round(sum(duration_minutes) / len(duration_minutes)) if duration_minutes else 0
    total_attempts = successful_count + failed_count
    success_rate = round((successful_count / total_attempts) * 100, 1) if total_attempts else 0.0
    threat_level = 'High' if suspicious_count else ('Elevated' if failed_count >= 5 else 'Normal')
    
    return {
        'system_status': 'Attention required' if threat_level in ('High', 'Elevated') else 'Operational',
        'status_color': 'danger' if threat_level == 'High' else ('warning' if threat_level == 'Elevated' else 'success'),
        'failed_logins': failed_count,
        'successful_logins': successful_count,
        'suspicious_activities': suspicious_count,
        'active_sessions': active_sessions_count,
        'password_resets': password_resets_count,
        'total_audited_events': len(logs),
        'average_session_duration': f'{average_minutes}m' if average_minutes else 'No completed sessions',
        'success_rate': success_rate,
        'threat_level': threat_level
    }


def reset_factory_database():
    """
    Completely wipes and factory-resets the Spherix Clinic database:
    1. Truncates all tables in SQLite (spherixclinic.db) and SQL Server.
    2. Wipes in-memory TEMP_DATA collections completely.
    3. Re-initializes baseline admin, hospital, patient, and staff accounts.
    4. Persists the clean baseline state.
    """
    global TEMP_DATA
    print("🚨 [FACTORY RESET] Initializing comprehensive database factory reset...")

    tables_to_clear = [
        'camp_registrations', 'appointments', 'messages', 'orders', 'reviews',
        'bed_bookings', 'doctor_images', 'staff', 'doctors', 'patients',
        'hospitals', 'blood_donors', 'organ_donors', 'camps', 'blood_stock',
        'organ_requests', 'patient_vitals', 'activity_logs', 'contact_messages',
        'visitor_passes', 'referrals', 'notifications', 'doctor_symptom_reviews',
        'patient_lifestyle_logs'
    ]

    # 1. Truncate / Clear persistent SQL / SQLite tables
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            for tbl in tables_to_clear:
                try:
                    cursor.execute(f"DELETE FROM {tbl}")
                except Exception:
                    pass
            conn.commit()
            conn.close()
            print("  ✓ Cleared all operational tables in DB connection.")
    except Exception as e:
        print(f"⚠️ Error clearing DB tables during factory reset: {e}")

    # Also wipe local SQLite file explicitly if present
    sqlite_path = os.getenv('SQLITE_DB_PATH', 'spherixclinic.db')
    if os.path.exists(sqlite_path):
        try:
            s_conn = sqlite3.connect(sqlite_path)
            s_cur = s_conn.cursor()
            for tbl in tables_to_clear:
                try:
                    s_cur.execute(f"DELETE FROM {tbl}")
                except Exception:
                    pass
            s_conn.commit()
            s_conn.close()
            print("  ✓ Cleared tables in SQLite file.")
        except Exception as e:
            print(f"⚠️ Error clearing SQLite: {e}")

    # 2. Reset in-memory TEMP_DATA dictionary completely in-place
    for k in list(TEMP_DATA.keys()):
        if isinstance(TEMP_DATA[k], dict):
            TEMP_DATA[k].clear()
        elif isinstance(TEMP_DATA[k], list):
            TEMP_DATA[k].clear()

    # Re-establish core keys
    TEMP_DATA['doctors'] = {}
    TEMP_DATA['patients'] = {}
    TEMP_DATA['hospitals'] = {}
    TEMP_DATA['staff'] = {}
    TEMP_DATA['appointments'] = {}
    TEMP_DATA['messages'] = {}
    TEMP_DATA['orders'] = {}
    TEMP_DATA['reviews'] = {}
    TEMP_DATA['blood_donors'] = {}
    TEMP_DATA['organ_donors'] = {}
    TEMP_DATA['contact_messages'] = []
    TEMP_DATA['camp_registrations'] = {}
    TEMP_DATA['camps'] = {}
    TEMP_DATA['newsletter_subscribers'] = []
    TEMP_DATA['patient_vitals'] = {}
    TEMP_DATA['blood_stock'] = {"A+": 18, "A-": 8, "B+": 24, "B-": 6, "AB+": 12, "AB-": 4, "O+": 32, "O-": 10}
    TEMP_DATA['visitor_passes'] = {}
    TEMP_DATA['bed_bookings'] = {}
    TEMP_DATA['organ_requests'] = {}
    TEMP_DATA['activity_logs'] = {}
    TEMP_DATA['referrals'] = {}
    TEMP_DATA['notifications'] = {}
    TEMP_DATA['symptom_reviews'] = []
    TEMP_DATA['medical_records'] = {}
    TEMP_DATA['auth_activity_logs'] = []
    TEMP_DATA['next_ids'] = {
        "doctor": 1, "patient": 1, "hospital": 1, "appointment": 1, "staff": 1,
        "message": 1, "order": 1, "review": 1, "blood_donor": 1, "organ_donor": 1,
        "camp": 1, "camp_registration": 1, "bed_booking": 1, "visitor_pass": 1,
        "patient_vital": 1, "organ_request": 1, "activity_log": 1, "referral": 1, "notification": 1
    }

    # 3. Setup baseline entities
    setup_admin_user()
    setup_hospital_user()
    setup_patient_user()
    setup_multi_hospital_and_staff()

    # 4. Save and persist fresh baseline state
    save_data()
    print("✅ [FACTORY RESET] System successfully reset to clean factory state.")
    return True

