import os
import sys

# Automatically configure unixODBC paths on macOS for Homebrew installations
if sys.platform == 'darwin' and not os.environ.get('ODBCSYSINI'):
    for prefix in ['/opt/homebrew/etc', '/usr/local/etc']:
        if os.path.exists(os.path.join(prefix, 'odbcinst.ini')):
            os.environ['ODBCSYSINI'] = prefix
            print(f"ℹ️ Automatically configured ODBCSYSINI={prefix}")
            break

# Configuration matching your Docker / SQL Server setup
SERVER = os.getenv('DB_SERVER', 'localhost')
DATABASE = os.getenv('DB_NAME', 'dev_ai_plus')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD', 'RadhaRani@123')
DRIVER = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')

# Attempt to import pyodbc with fallback path detection
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

def get_connection(db_name='master'):
    """Creates an ODBC connection string and returns a connection object."""
    if not HAS_PYODBC:
        return None
    conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={db_name};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
    return pyodbc.connect(conn_str, autocommit=True)

def setup_database():
    print("--- Starting Full Database Setup & Table Creation ---")
    
    if not HAS_PYODBC:
        print("\n⚠️  Notice: 'pyodbc' is not installed in your current active Python environment.")
        print("👉 To install pyodbc for SQL Server, run:")
        print("   pip install pyodbc\n")
        print("🔄 Initializing local SQLite database schema ('dev_ai_plus.db') as fallback...\n")
        setup_sqlite_database()
        return

    # 1. Ensure Database Exists in SQL Server
    try:
        conn = get_connection('master')
        cursor = conn.cursor()
        cursor.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{DATABASE}') CREATE DATABASE {DATABASE}")
        print(f"✅ Database '{DATABASE}' ensured.")
        conn.close()
    except Exception as e:
        print(f"❌ Error creating/verifying SQL Server database: {e}")
        print("Tip: Ensure your SQL Server container/service is active.")
        print("🔄 Setting up local SQLite tables as fallback...")
        setup_sqlite_database()
        return

    # 2. Create and Ensure All Tables in SQL Server
    try:
        conn = get_connection(DATABASE)
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
                profile_picture_content_type VARCHAR(50) NULL
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
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255),
                subject NVARCHAR(255),
                message NVARCHAR(MAX),
                created_at DATETIME DEFAULT GETDATE()
            )"""),
            ("medicines", """CREATE TABLE medicines (
                id INT PRIMARY KEY,
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
            )""")
        ]

        for name, query in tables:
            cursor.execute(f"IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{name}' AND xtype='U') {query}")
            print(f"✅ SQL Server Table '{name}' verified/created.")

        cursor.execute("SELECT COUNT(*) FROM blood_stock")
        if cursor.fetchone()[0] == 0:
            stock_data = [('A+', 15), ('A-', 5), ('B+', 12), ('B-', 4), ('AB+', 8), ('AB-', 3), ('O+', 25), ('O-', 10)]
            cursor.executemany("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", stock_data)
            print("✅ Initialized blood stock data.")

        conn.commit()
        conn.close()
        print("\n🎉 --- All SQL Database Tables Created & Verified Successfully --- 🎉")

    except Exception as e:
        print(f"❌ Error during table creation: {e}")

def setup_sqlite_database():
    """Initializes local SQLite database with all tables (0 dependencies)."""
    import sqlite3
    db_file = os.path.join(os.path.dirname(__file__), 'dev_ai_plus.db')
    conn = sqlite3.connect(db_file)
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
        "CREATE TABLE IF NOT EXISTS contact_messages (id INTEGER PRIMARY KEY, name TEXT, email TEXT, subject TEXT, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS medicines (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER DEFAULT 0, description TEXT)",
        "CREATE TABLE IF NOT EXISTS referrals (id INTEGER PRIMARY KEY, patient_id TEXT, referred_to_hospital_id TEXT, reason TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS visitor_passes (id INTEGER PRIMARY KEY, visitor_name TEXT, patient_name TEXT, hospital_id TEXT, visit_date DATE, status TEXT DEFAULT 'approved', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ]

    for stmt in sqlite_tables:
        cursor.execute(stmt)

    cursor.execute("SELECT COUNT(*) FROM blood_stock")
    if cursor.fetchone()[0] == 0:
        stock_data = [('A+', 15), ('A-', 5), ('B+', 12), ('B-', 4), ('AB+', 8), ('AB-', 3), ('O+', 25), ('O-', 10)]
        cursor.executemany("INSERT OR IGNORE INTO blood_stock (blood_group, quantity) VALUES (?, ?)", stock_data)

    conn.commit()
    conn.close()
    print(f"🎉 --- SQLite Database '{db_file}' (All 24 Tables) Created & Verified Successfully --- 🎉")

if __name__ == "__main__":
    setup_database()