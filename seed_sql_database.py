import os
import sys
import datetime
from werkzeug.security import generate_password_hash

# Ensure ODBC path is set for macOS
if sys.platform == 'darwin' and not os.environ.get('ODBCSYSINI'):
    for prefix in ['/opt/homebrew/etc', '/usr/local/etc']:
        if os.path.exists(os.path.join(prefix, 'odbcinst.ini')):
            os.environ['ODBCSYSINI'] = prefix
            break

import pyodbc
from app import get_db_connection

def populate_all_sql_data():
    print("=========================================================")
    print("   SPHERIX CLINIC - COMPREHENSIVE SQL DATA SEEDING   ")
    print("=========================================================")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to SQL Database. Aborting.")
        return
        
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
        cursor.execute("SELECT id FROM doctors WHERE id = ? OR email = ?", doc[0], doc[3])
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
        cursor.execute("SELECT id FROM patients WHERE id = ? OR email = ?", pat[0], pat[2])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO patients (id, name, email, password, age, gender, phone, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, pat)
            print(f"  ✓ Added Patient: {pat[1]} ({pat[2]})")

    # 3. Hospitals
    hospitals_data = [
        ('HPT/2026/001', 'SMCH (Spherix Memorial Care Hospital)', 'hospital@spherixclinic.com', default_hash, 150, 42, 25, 6, 'Available', 'Main Medical Campus, Station Road, Motihari, Bihar', 1),
        ('HPT/2026/002', 'Metro Health City Hospital', 'metro@example.com', default_hash, 250, 78, 40, 12, 'Available', '450 Lexington Ave, New York, NY', 1),
        ('HPT/2026/003', 'St. Jude Regional Medical Center', 'stjude@example.com', default_hash, 180, 55, 30, 8, 'Available', '12 Medical Park Blvd, Chicago, IL', 1),
        ('HPT/2026/004', 'Apollo Super Speciality Hospital', 'apollo@example.com', default_hash, 320, 95, 50, 14, 'Available', 'Mathura Road, Sarita Vihar, New Delhi', 1)
    ]
    for hpt in hospitals_data:
        cursor.execute("SELECT id FROM hospitals WHERE id = ? OR email = ?", hpt[0], hpt[2])
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
        cursor.execute("SELECT id FROM staff WHERE id = ? OR email = ?", stf[0], stf[2])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO staff (id, name, email, password, role, phone, hospital_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, stf)
            print(f"  ✓ Added Staff: {stf[1]} ({stf[4]})")

    # 5. Blood Donors
    blood_donors_data = [
        ('BD/2026/001', 'Sunny Kushwaha', 'sunny28skk@gmail.com', '9334325920', 'AB+', 24, 'Motihari', default_hash, '2026-06-15'),
        ('BD/2026/002', 'David Miller', 'david.m@example.com', '+1 (555) 887-1234', 'O-', 28, 'New York', default_hash, '2026-07-20'),
        ('BD/2026/003', 'Rohan Gupta', 'rohan.g@example.com', '+91 983 5544 332', 'O+', 31, 'Patna', default_hash, '2026-08-01'),
        ('BD/2026/004', 'Sarah Lin', 'sarah.lin@example.com', '+1 (555) 776-5544', 'A+', 26, 'Chicago', default_hash, '2026-05-10'),
        ('BD/2026/005', 'Amitav Ghosh', 'amitav@example.com', '+91 943 2211 009', 'B+', 35, 'Kolkata', default_hash, '2026-07-14')
    ]
    for bd in blood_donors_data:
        cursor.execute("SELECT id FROM blood_donors WHERE id = ? OR email = ?", bd[0], bd[2])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO blood_donors (id, name, email, phone, blood_group, age, city, password, last_donation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, bd)
            print(f"  ✓ Added Blood Donor: {bd[1]} ({bd[4]})")

    # 6. Organ Donors
    organ_donors_data = [
        ('OD/2026/001', 'Elena Rostova', 'elena@example.com', '+1 (555) 432-1098', 'Heart, Kidneys, Corneas', 'O+', 29, 'New York', default_hash),
        ('OD/2026/002', 'Ramesh Chandra', 'ramesh.c@example.com', '+91 983 1122 334', 'Kidneys, Liver', 'B+', 42, 'Patna', default_hash),
        ('OD/2026/003', 'Claire Beaumont', 'claire.b@example.com', '+1 (555) 998-7766', 'All Organs, Skin Tissue', 'A-', 33, 'Chicago', default_hash)
    ]
    for od in organ_donors_data:
        cursor.execute("SELECT id FROM organ_donors WHERE id = ? OR email = ?", od[0], od[2])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO organ_donors (id, name, email, phone, organs, blood_group, age, city, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, od)
            print(f"  ✓ Added Organ Donor: {od[1]} ({od[4]})")

    # 7. Donation Camps
    camps_data = [
        (101, 'Red Cross Central Life Drive 2026', 'Community Medical Grounds, Station Road, Motihari', '2026-09-05', '09:00 AM - 05:00 PM', 'Indian Red Cross Society & SMCH', '+91 933 4325 920'),
        (102, 'Rotary Club Metropolitan Blood Drive', 'Madison Square Health Arena, New York, NY', '2026-09-12', '08:30 AM - 04:30 PM', 'Rotary International & Metro Health', '+1 (555) 900-1000'),
        (103, 'National Voluntary Transfusion Drive', 'Gandhi Maidan Health Pavilion, Patna, Bihar', '2026-09-18', '09:00 AM - 06:00 PM', 'State Blood Transfusion Council (SBTC)', '+91 982 3456 789')
    ]
    for camp in camps_data:
        cursor.execute("SELECT id FROM camps WHERE id = ?", camp[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO camps (id, name, location, date, time, organizer, contact)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, camp)
            print(f"  ✓ Added Blood Camp: {camp[1]}")

    # 8. Appointments
    appointments_data = [
        (1001, 'Rahul Sharma', 'DOC/2026/002', 'PAT/2026/001', '2026-08-25', '10:30:00', 34, 'PID-9901', '+91 944 1234 567', 'Routine Cardiovascular Health Checkup & ECG Review', 'Confirmed'),
        (1002, 'Emily Watson', 'DOC/2026/003', 'PAT/2026/002', '2026-08-26', '14:00:00', 29, 'PID-9902', '+1 (555) 678-9012', 'Chronic Migraine & Neurological Screening', 'Confirmed'),
        (1003, 'Vikram Patel', 'DOC/2026/005', 'PAT/2026/003', '2026-08-27', '11:15:00', 48, 'PID-9903', '+91 982 3456 789', 'Lumbar Spine Consultation & X-Ray Followup', 'Pending')
    ]
    for apt in appointments_data:
        cursor.execute("SELECT id FROM appointments WHERE id = ?", apt[0])
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
        cursor.execute("SELECT id FROM bed_bookings WHERE id = ?", bb[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO bed_bookings (
                    id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status, room_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, bb)
            print(f"  ✓ Added Bed Booking #{bb[0]}: {bb[3]} at {bb[8]}")

    # 10. Organ Requests
    organ_requests_data = [
        (3001, 'HPT/2026/001', 'Mr. Amit Kumar', 'Kidney', 'O+', 'Critical (48 Hours)', 'Active Matching'),
        (3002, 'HPT/2026/002', 'Mrs. Linda Johnson', 'Corneas', 'A+', 'Urgent', 'Donor Contacted')
    ]
    for oq in organ_requests_data:
        cursor.execute("SELECT id FROM organ_requests WHERE id = ?", oq[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO organ_requests (
                    id, hospital_id, patient_name, organ_needed, blood_group, urgency, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, oq)
            print(f"  ✓ Added Organ Request #{oq[0]}: {oq[2]} ({oq[3]})")

    # 11. Patient Vitals (Identity Column)
    vitals_data = [
        ('PAT/2026/001', 68.5, 72, 105, 120, 80),
        ('PAT/2026/003', 74.0, 84, 130, 135, 88)
    ]
    cursor.execute("SELECT COUNT(*) FROM patient_vitals")
    if cursor.fetchone()[0] == 0:
        for vt in vitals_data:
            cursor.execute("""
                INSERT INTO patient_vitals (
                    patient_id, weight, heart_rate, blood_sugar, systolic_bp, diastolic_bp, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, GETDATE())
            """, vt)
            print(f"  ✓ Added Vital Record for Patient {vt[0]}")

    # 12. Visitor Passes
    passes_data = [
        (5001, 'HPT/2026/001', 'VP-2026-001', 'Sunita Sharma', '+91 944 5566 778', 'Rahul Sharma', 'Ward 304', 'Spouse', 6, 'ACTIVE', 'Front Desk')
    ]
    for ps in passes_data:
        cursor.execute("SELECT id FROM visitor_passes WHERE id = ?", ps[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO visitor_passes (
                    id, hospital_id, pass_number, visitor_name, visitor_phone, patient_name, ward_room, relation, valid_hours, status, issued_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ps)
            print(f"  ✓ Added Visitor Pass #{ps[0]} for {ps[3]}")

    # 13. Reviews
    reviews_data = [
        (6001, 'DOC/2026/002', 'PAT/2026/001', 'Rahul Sharma', 5, 'Dr. Sarah Jenkins provided an exceptional consultation. Clear diagnosis, attentive care, and accurate medication prescription.'),
        (6002, 'DOC/2026/003', 'PAT/2026/002', 'Emily Watson', 5, 'Dr. Chen is brilliant. Solved my neurological symptoms that other clinics missed for months.')
    ]
    for rv in reviews_data:
        cursor.execute("SELECT id FROM reviews WHERE id = ?", rv[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO reviews (id, doctor_id, patient_id, patient_name, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?)
            """, rv)
            print(f"  ✓ Added Doctor Review #{rv[0]}")

    # 14. Orders
    orders_data = [
        (7001, 'PAT/2026/001', '[{"name": "Pantop DSR", "quantity": 2, "price": 145.0}, {"name": "Acelock", "quantity": 1, "price": 85.0}]', 375.0, 'Civil Lines, Motihari, Bihar', '2026-08-22', 'Delivered'),
        (7002, 'PAT/2026/002', '[{"name": "Multi-Vitamin Vitalize", "quantity": 1, "price": 220.0}]', 220.0, '742 Evergreen Terrace, New York, NY', '2026-08-23', 'Processing')
    ]
    for ord_row in orders_data:
        cursor.execute("SELECT id FROM orders WHERE id = ?", ord_row[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO orders (id, patient_id, items, total_price, shipping_address, order_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ord_row)
            print(f"  ✓ Added Pharmacy Order #{ord_row[0]}")

    # 15. Activity Logs
    activity_data = [
        (8001, 'HPT/2026/001', 'admin@spherixclinic.com', 'Admin Login', 'Authorized administrator authenticated via encrypted root console'),
        (8002, 'HPT/2026/001', 'sumit@gmail.com', 'Stock Inventory', 'Updated blood bank stock units (+5 units O+)'),
        (8003, 'HPT/2026/001', 'doctor@example.com', 'Prescription Authored', 'Prescription generated for Patient PID-9901')
    ]
    for act in activity_data:
        cursor.execute("SELECT id FROM activity_logs WHERE id = ?", act[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO activity_logs (id, hospital_id, user_name, action, details)
                VALUES (?, ?, ?, ?, ?)
            """, act)
            print(f"  ✓ Added Activity Log #{act[0]}")

    # 16. Contact Messages (Identity Column)
    contact_data = [
        ('Dr. Samantha Reed', 'samantha.reed@medresearch.org', '+1 (555) 901-2345', 'Boston, MA', 'Inquiry regarding clinical partnership with Spherix AI diagnostic engine for multi-center research.', '2026-08-23')
    ]
    cursor.execute("SELECT COUNT(*) FROM contact_messages")
    if cursor.fetchone()[0] == 0:
        for msg in contact_data:
            cursor.execute("""
                INSERT INTO contact_messages (name, email, phone, address, message, date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, msg)
            print(f"  ✓ Added Contact Message from {msg[0]}")

    # 17. Camp Registrations
    camp_reg_data = [
        (10001, 'Red Cross Central Life Drive 2026', 'Rahul Sharma', 'patient@example.com', '+91 944 1234 567')
    ]
    for cr in camp_reg_data:
        cursor.execute("SELECT id FROM camp_registrations WHERE id = ?", cr[0])
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO camp_registrations (id, camp_name, name, email, phone)
                VALUES (?, ?, ?, ?, ?)
            """, cr)
            print(f"  ✓ Added Camp Registration #{cr[0]}")

    # Commit all transaction batches
    conn.commit()
    conn.close()
    print("\n🎉 ALL TABLES CREATED & COMPREHENSIVE DATA POPULATED SUCCESSFULLY INTO SQL SERVER!")

if __name__ == '__main__':
    populate_all_sql_data()
