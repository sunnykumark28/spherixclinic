import json
import pyodbc
import os

# Configuration matching your Docker setup
SERVER = 'localhost'
DATABASE = 'dev_ai_plus'
USERNAME = 'sa'
PASSWORD = 'RadhaRani@123'
DRIVER = '{ODBC Driver 17 for SQL Server}'
JSON_FILE = '/Users/sunnykushwaha/Projects/dev_ai_plus/data_store.json'

def get_connection():
    conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;Autocommit=True'
    return pyodbc.connect(conn_str, autocommit=True)

def migrate():
    if not os.path.exists(JSON_FILE):
        print(f"❌ File {JSON_FILE} not found.")
        return

    print(f"📖 Reading data from {JSON_FILE}...")
    with open(JSON_FILE, 'r') as f:
        data = json.load(f)

    try:
        conn = get_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print("--- Starting Migration ---")

    # 1. Migrate Doctors
    doctors = data.get('doctors', {})
    print(f"👨‍⚕️ Found {len(doctors)} doctors to migrate.")
    for doc_id, doc in doctors.items():
        try:
            # Check if doctor already exists to avoid duplicates
            cursor.execute("SELECT id FROM doctors WHERE id = ?", doc['id'])
            if cursor.fetchone():
                print(f"   ⚠️ Doctor {doc['id']} already exists. Skipping.")
                continue
            
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
            print(f"   ✅ Inserted Doctor {doc['id']}")
        except Exception as e:
            print(f"   ❌ Error inserting doctor {doc_id}: {e}")

    # 2. Migrate Hospitals
    hospitals = data.get('hospitals', {})
    print(f"🏥 Found {len(hospitals)} hospitals to migrate.")
    for hosp_id, hosp in hospitals.items():
        try:
            cursor.execute("SELECT id FROM hospitals WHERE id = ?", hosp['id'])
            if cursor.fetchone():
                print(f"   ⚠️ Hospital {hosp['id']} already exists. Skipping.")
                continue

            try:
                sql = """INSERT INTO hospitals (
                    id, name, email, password, logo_url, total_beds, available_beds, address, icu_beds, available_icu_beds, doctors_available
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                
                values = (
                    hosp.get('id'), hosp.get('name'), hosp.get('email'), hosp.get('password'),
                    hosp.get('logo_url'), hosp.get('total_beds', 0), hosp.get('available_beds', 0),
                    hosp.get('address'), hosp.get('icu_beds', 0), hosp.get('available_icu_beds', 0),
                    hosp.get('doctors_available', 'Available')
                )
                cursor.execute(sql, values)
            except pyodbc.Error:
                sql = """INSERT INTO hospitals (
                    id, name, email, password, logo_url, total_beds, available_beds
                ) VALUES (?, ?, ?, ?, ?, ?, ?)"""
                
                values = (
                    hosp.get('id'), hosp.get('name'), hosp.get('email'), hosp.get('password'),
                    hosp.get('logo_url'), hosp.get('total_beds', 0), hosp.get('available_beds', 0)
                )
                cursor.execute(sql, values)
            print(f"   ✅ Inserted Hospital {hosp['id']}")
        except Exception as e:
            print(f"   ❌ Error inserting hospital {hosp_id}: {e}")

    # 3. Migrate Blood Stock
    blood_stock = data.get('blood_stock', {})
    print(f"🩸 Updating blood stock...")
    for group, quantity in blood_stock.items():
        # Update existing stock or insert if missing
        cursor.execute("SELECT blood_group FROM blood_stock WHERE blood_group = ?", group)
        if cursor.fetchone():
            cursor.execute("UPDATE blood_stock SET quantity = ? WHERE blood_group = ?", quantity, group)
        else:
            cursor.execute("INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)", group, quantity)

    # 4. Migrate Organ Donors
    organ_donors = data.get('organ_donors', {})
    print(f"🫀 Found {len(organ_donors)} organ donors to migrate.")
    for od_id, od in organ_donors.items():
        try:
            cursor.execute("SELECT id FROM organ_donors WHERE id = ?", od.get('id'))
            if cursor.fetchone():
                print(f"   ⚠️ Organ Donor {od.get('id')} already exists. Skipping.")
                continue

            sql = """INSERT INTO organ_donors (
                id, name, email, phone, organs, blood_group, age, city, password, profile_picture_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            
            # Ensure organs list is converted to a JSON string for the DB
            organs_data = od.get('organs', [])
            organs_json = json.dumps(organs_data) if isinstance(organs_data, list) else str(organs_data)

            values = (
                od.get('id'), od.get('name'), od.get('email'), od.get('phone'),
                organs_json, od.get('blood_group'), od.get('age'),
                od.get('city'), od.get('password'), od.get('profile_picture_url'), od.get('created_at')
            )
            cursor.execute(sql, values)
            print(f"   ✅ Inserted Organ Donor {od.get('id')}")
        except Exception as e:
            print(f"   ❌ Error inserting organ donor {od_id}: {e}")

    # 5. Migrate Messages
    messages = data.get('messages', {})
    print(f"💬 Found {len(messages)} messages to migrate.")
    for msg_id, msg in messages.items():
        try:
            cursor.execute("SELECT id FROM messages WHERE id = ?", msg.get('id'))
            if cursor.fetchone():
                continue
            
            sql = """INSERT INTO messages (
                id, doctor_id, patient_id, sender, content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)"""
            
            values = (
                msg.get('id'), msg.get('doctor_id'), msg.get('patient_id'), 
                msg.get('sender'), msg.get('content'), msg.get('created_at')
            )
            cursor.execute(sql, values)
        except Exception as e:
            print(f"   ❌ Error inserting message {msg_id}: {e}")

    conn.close()
    print("--- Migration Completed Successfully ---")

if __name__ == '__main__':
    migrate()