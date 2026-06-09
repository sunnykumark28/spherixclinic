import pyodbc
import time

# Configuration matching your Docker setup
SERVER = 'localhost'
DATABASE = 'dev_ai_plus'
USERNAME = 'sa'
PASSWORD = 'RadhaRani@123'
# On macOS with Docker, usually Driver 17 or 18 is used.
DRIVER = '{ODBC Driver 17 for SQL Server}' 

def get_connection(db_name='master'):
    """Creates a connection string and returns a connection object."""
    conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={db_name};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
    return pyodbc.connect(conn_str, autocommit=True)

def setup_database():
    print("--- Starting Database Setup ---")
    
    # 1. Create Database
    try:
        conn = get_connection('master')
        cursor = conn.cursor()
        cursor.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{DATABASE}') CREATE DATABASE {DATABASE}")
        print(f"✅ Database '{DATABASE}' ensured.")
        conn.close()
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        print("Tip: Ensure your Docker container is running and you have the ODBC Driver installed (brew install msodbcsql17).")
        return

    # 2. Create Tables
    try:
        conn = get_connection(DATABASE)
        cursor = conn.cursor()

        # Doctors Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='doctors' AND xtype='U')
            CREATE TABLE doctors (
                id VARCHAR(50) PRIMARY KEY,
                first_name NVARCHAR(100),
                last_name NVARCHAR(100),
                email NVARCHAR(255) UNIQUE,
                password NVARCHAR(255),
                department NVARCHAR(100),
                phone NVARCHAR(20),
                specialization NVARCHAR(100),
                address NVARCHAR(MAX),
                profile_picture_url NVARCHAR(MAX),
                bio NVARCHAR(MAX),
                hospital_name NVARCHAR(255),
                hospital_address NVARCHAR(MAX),
                state NVARCHAR(100),
                district NVARCHAR(100),
                pincode NVARCHAR(20),
                qualification NVARCHAR(MAX),
                license_number NVARCHAR(100),
                experience NVARCHAR(50),
                consultation_type NVARCHAR(50),
                consultation_fee NVARCHAR(50),
                working_hours NVARCHAR(MAX),
                languages_spoken NVARCHAR(MAX),
                social_links NVARCHAR(MAX),
                is_verified BIT DEFAULT 0
            )
        """)
        print("✅ Table 'doctors' created.")

        # Patients Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='patients' AND xtype='U')
            CREATE TABLE patients (
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255) UNIQUE,
                password NVARCHAR(255),
                age INT,
                gender NVARCHAR(50),
                profile_picture_url NVARCHAR(255) NULL
            )
        """)
        
        # Add profile_picture_url column if it doesn't exist (for existing databases)
        cursor.execute("""
            IF NOT EXISTS(SELECT * FROM sys.columns WHERE Name = N'profile_picture_url' AND Object_ID = Object_ID(N'patients'))
            BEGIN
                ALTER TABLE patients ADD profile_picture_url NVARCHAR(255) NULL
            END
        """)
        print("✅ Table 'patients' created.")

        # Hospitals Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='hospitals' AND xtype='U')
            CREATE TABLE hospitals (
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255) UNIQUE,
                password NVARCHAR(255),
                logo_url NVARCHAR(MAX),
                total_beds INT DEFAULT 0,
                available_beds INT DEFAULT 0,
                address NVARCHAR(MAX)
            )
        """)
        
        # Add address column if it doesn't exist (for existing databases)
        cursor.execute("""
            IF NOT EXISTS(SELECT * FROM sys.columns WHERE Name = N'address' AND Object_ID = Object_ID(N'hospitals'))
            BEGIN
                ALTER TABLE hospitals ADD address NVARCHAR(MAX)
            END
        """)
        print("✅ Table 'hospitals' created.")

        # Add new columns for ICU beds and doctors availability
        cursor.execute("""
            IF NOT EXISTS(SELECT * FROM sys.columns WHERE Name = N'icu_beds' AND Object_ID = Object_ID(N'hospitals'))
            BEGIN
                ALTER TABLE hospitals ADD icu_beds INT DEFAULT 0;
                ALTER TABLE hospitals ADD available_icu_beds INT DEFAULT 0;
                ALTER TABLE hospitals ADD doctors_available NVARCHAR(50) DEFAULT 'Available';
            END
        """)

        # Staff Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='staff' AND xtype='U')
            CREATE TABLE staff (
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255) UNIQUE,
                password NVARCHAR(255),
                role NVARCHAR(100),
                phone NVARCHAR(20),
                hospital_name NVARCHAR(255)
            )
        """)
        print("✅ Table 'staff' created.")

        # Appointments Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='appointments' AND xtype='U')
            CREATE TABLE appointments (
                id INT PRIMARY KEY,
                patient_name NVARCHAR(255),
                doctor_id VARCHAR(50),
                patient_id INT,
                appointment_date DATE,
                appointment_time TIME,
                patient_age INT,
                patient_id_number NVARCHAR(50),
                patient_phone NVARCHAR(20),
                reason NVARCHAR(MAX),
                status NVARCHAR(50),
                created_at DATETIME DEFAULT GETDATE(),
                original_appointment_date DATE,
                original_appointment_time TIME,
                document_path NVARCHAR(MAX),
                prescription_path NVARCHAR(MAX)
            )
        """)
        print("✅ Table 'appointments' created.")

        # Reviews Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='reviews' AND xtype='U')
            CREATE TABLE reviews (
                id INT PRIMARY KEY,
                doctor_id VARCHAR(50),
                patient_id INT,
                patient_name NVARCHAR(255),
                rating INT,
                comment NVARCHAR(MAX),
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        print("✅ Table 'reviews' created.")

        # Messages Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='messages' AND xtype='U')
            CREATE TABLE messages (
                id INT PRIMARY KEY,
                doctor_id VARCHAR(50),
                patient_id INT,
                sender NVARCHAR(50),
                content NVARCHAR(MAX),
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        print("✅ Table 'messages' created.")

        # Orders Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='orders' AND xtype='U')
            CREATE TABLE orders (
                id INT PRIMARY KEY,
                patient_id INT,
                items NVARCHAR(MAX),
                total_price FLOAT,
                shipping_address NVARCHAR(MAX),
                order_date DATE,
                status NVARCHAR(50)
            )
        """)
        print("✅ Table 'orders' created.")

        # Blood Donors Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='blood_donors' AND xtype='U')
            CREATE TABLE blood_donors (
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255) UNIQUE,
                phone NVARCHAR(20),
                blood_group NVARCHAR(10),
                age INT,
                city NVARCHAR(100),
                password NVARCHAR(255),
                last_donation DATE,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        
        # Add profile_picture_url column if it doesn't exist
        cursor.execute("""
            IF NOT EXISTS(SELECT * FROM sys.columns WHERE Name = N'profile_picture_url' AND Object_ID = Object_ID(N'blood_donors'))
            BEGIN
                ALTER TABLE blood_donors ADD profile_picture_url NVARCHAR(255) NULL
            END
        """)
        print("✅ Table 'blood_donors' created.")

        # Organ Donors Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='organ_donors' AND xtype='U')
            CREATE TABLE organ_donors (
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                email NVARCHAR(255) UNIQUE,
                phone NVARCHAR(20),
                organs NVARCHAR(MAX),
                blood_group NVARCHAR(10),
                age INT,
                city NVARCHAR(100),
                password NVARCHAR(255) NULL,
                profile_picture_url NVARCHAR(255) NULL,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        
        # Add profile_picture_url column if it doesn't exist (for existing databases)
        cursor.execute("""
            IF NOT EXISTS(SELECT * FROM sys.columns WHERE Name = N'profile_picture_url' AND Object_ID = Object_ID(N'organ_donors'))
            BEGIN
                ALTER TABLE organ_donors ADD profile_picture_url NVARCHAR(255) NULL
            END
        """)
        print("✅ Table 'organ_donors' created.")

        # Camps Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='camps' AND xtype='U')
            CREATE TABLE camps (
                id INT PRIMARY KEY,
                name NVARCHAR(255),
                location NVARCHAR(MAX),
                date NVARCHAR(50),
                time NVARCHAR(50),
                organizer NVARCHAR(255),
                contact NVARCHAR(50)
            )
        """)
        print("✅ Table 'camps' created.")

        # Camp Registrations Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='camp_registrations' AND xtype='U')
            CREATE TABLE camp_registrations (
                id INT PRIMARY KEY,
                camp_name NVARCHAR(255),
                name NVARCHAR(255),
                email NVARCHAR(255),
                phone NVARCHAR(20),
                date DATETIME DEFAULT GETDATE()
            )
        """)
        print("✅ Table 'camp_registrations' created.")

        # Blood Stock Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='blood_stock' AND xtype='U')
            CREATE TABLE blood_stock (
                blood_group NVARCHAR(10) PRIMARY KEY,
                quantity INT DEFAULT 0
            )
        """)
        print("✅ Table 'blood_stock' created.")

        # Doctor Images Table (For storing profile pictures in DB)
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='doctor_images' AND xtype='U')
            CREATE TABLE doctor_images (
                doctor_id VARCHAR(50) PRIMARY KEY,
                image_data VARBINARY(MAX),
                content_type VARCHAR(50)
            )
        """)
        print("✅ Table 'doctor_images' created.")

        # Bed Bookings Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bed_bookings' AND xtype='U')
            CREATE TABLE bed_bookings (
                id INT PRIMARY KEY,
                hospital_id INT,
                patient_id INT,
                patient_name NVARCHAR(255),
                patient_phone NVARCHAR(20),
                bed_type NVARCHAR(50),
                reason NVARCHAR(MAX),
                status NVARCHAR(50),
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        print("✅ Table 'bed_bookings' created.")

        # Initialize Blood Stock
        cursor.execute("SELECT COUNT(*) FROM blood_stock")
        if cursor.fetchone()[0] == 0:
            stock_data = [('A+', 15), ('A-', 5), ('B+', 12), ('B-', 4), ('AB+', 8), ('AB-', 3), ('O+', 25), ('O-', 10)]
            cursor.executemany("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", stock_data)
            print("✅ Initialized blood stock data.")

        conn.commit()
        conn.close()
        print("--- Database Setup Completed Successfully ---")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    setup_database()