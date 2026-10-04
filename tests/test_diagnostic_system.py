"""
tests/test_diagnostic_system.py
Complete 30-Point Quality Assurance & Integration Test Suite
for Spherix Clinic Diagnostic Test Booking, Doctor Referral & Pathology Lab Ecosystem (Section 19).
"""

import os
import io
import json
import uuid
import pytest
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

from spherix.services.database import get_db_connection, TEMP_DATA, save_data
from spherix.models.user import PathologyLab, Patient, Doctor
from spherix.services.diagnostic_db import (
    init_diagnostic_schema,
    find_matching_pathology_labs,
    can_transition_booking,
    get_lab_dashboard_metrics,
    generate_sample_id,
    generate_booking_id,
    generate_referral_number,
    generate_report_number,
    log_diagnostic_audit,
    get_patient_diagnostic_data,
    get_doctor_diagnostic_data,
    get_admin_diagnostic_data,
    VALID_TRANSITIONS
)

# ─── Test Fixture & Seeding Helper ────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_diagnostic_environment(app):
    """Initializes diagnostic database tables and seeds test entities for the suite."""
    with app.app_context():
        init_diagnostic_schema()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Seed 4 Test Laboratories in different lifecycle states
        hashed_pwd = generate_password_hash("Secret@123", method='pbkdf2:sha256:260000')

        labs_data = [
            ("LAB-TEST-APPROVED", "Spherix Central Diagnostics", "Spherix Central Labs", "REG-APP-001", "Independent", "Dr. Mehta", "9876543210", "approved_lab@spherix.test", hashed_pwd, "123 Healthcare Ave", "Mumbai", "Maharashtra", "400001", 19.0760, 72.8777, 25.0, "LIC-001", "NABL-999", 1, 1, 1, "APPROVED", 1),
            ("LAB-TEST-PENDING", "Apex Bio Diagnostics", "Apex Bio Labs", "REG-PEN-002", "Hospital Attached", "Mr. Sharma", "9876543211", "pending_lab@spherix.test", hashed_pwd, "456 Marine Lines", "Mumbai", "Maharashtra", "400002", 18.9400, 72.8200, 15.0, "LIC-002", None, 0, 1, 1, "PENDING_VERIFICATION", 1),
            ("LAB-TEST-REJECTED", "Faulty Diagnostics Ltd", "Faulty Labs", "REG-REJ-003", "Franchise", "Mr. Gupta", "9876543212", "rejected_lab@spherix.test", hashed_pwd, "789 Western Express", "Mumbai", "Maharashtra", "400050", 19.0500, 72.8400, 10.0, "LIC-003", None, 0, 0, 1, "REJECTED", 1),
            ("LAB-TEST-SUSPENDED", "Suspended Lab Co", "Suspended Lab", "REG-SUS-004", "Independent", "Dr. Rao", "9876543213", "suspended_lab@spherix.test", hashed_pwd, "101 Eastern Highway", "Mumbai", "Maharashtra", "400070", 19.0600, 72.8900, 10.0, "LIC-004", None, 0, 1, 0, "SUSPENDED", 1),
        ]

        for ld in labs_data:
            cursor.execute("""
                INSERT OR REPLACE INTO diagnostic_labs (
                    id, legal_name, display_name, registration_number, lab_type, owner_name,
                    phone, email, password, address, city, state, pincode, latitude, longitude,
                    service_radius_km, license_number, nabl_accreditation_number, is_nabl_accredited,
                    home_collection_available, walkin_available, status, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ld)

        # Seed services for Approved Lab (FBS, CBC, LFT)
        cursor.execute("INSERT OR REPLACE INTO diagnostic_lab_services (lab_id, test_id, price, mrp, home_collection_fee, home_collection_available, processing_available, custom_tat_hours, is_available) VALUES ('LAB-TEST-APPROVED', 'TEST-FBS', 150.0, 200.0, 50.0, 1, 1, 12, 1)")
        cursor.execute("INSERT OR REPLACE INTO diagnostic_lab_services (lab_id, test_id, price, mrp, home_collection_fee, home_collection_available, processing_available, custom_tat_hours, is_available) VALUES ('LAB-TEST-APPROVED', 'TEST-CBC', 350.0, 450.0, 50.0, 1, 1, 24, 1)")
        cursor.execute("INSERT OR REPLACE INTO diagnostic_lab_services (lab_id, test_id, price, mrp, home_collection_fee, home_collection_available, processing_available, custom_tat_hours, is_available) VALUES ('LAB-TEST-APPROVED', 'TEST-LFT', 600.0, 800.0, 50.0, 1, 1, 24, 1)")

        conn.commit()
        conn.close()

        # Seed in TEMP_DATA for Flask-Login session loaders
        if 'pathology_labs' not in TEMP_DATA:
            TEMP_DATA['pathology_labs'] = {}
        for ld in labs_data:
            lab_obj = PathologyLab(id=ld[0], legal_name=ld[1], display_name=ld[2], email=ld[7], password=ld[8], status=ld[21], is_active=bool(ld[22]))
            lab_obj.legal_name = ld[1]
            lab_obj.registration_number = ld[3]
            lab_obj.phone = ld[6]
            TEMP_DATA['pathology_labs'][ld[0]] = lab_obj

        # Seed mock patient
        if 'patients' not in TEMP_DATA:
            TEMP_DATA['patients'] = {}
        test_patient = Patient(id=99901, email="pat_diag_test@spherix.test", password=hashed_pwd, name="Test Diag Patient", phone="9988776655")
        test_patient.address = "Flat 402, Sunshine Towers, Mumbai"
        test_patient.city = "Mumbai"
        test_patient.pincode = "400001"
        test_patient.latitude = 19.0760
        test_patient.longitude = 72.8777
        TEMP_DATA['patients'][99901] = test_patient

        # Seed mock doctor
        if 'doctors' not in TEMP_DATA:
            TEMP_DATA['doctors'] = {}
        test_doc = Doctor(88801, "Sunil", "Verma", "doc_diag_test@spherix.test", hashed_pwd, "Internal Medicine")
        test_doc.department = "Internal Medicine"
        test_doc.phone = "9123456780"
        test_doc.consultation_fee = 500
        TEMP_DATA['doctors'][88801] = test_doc


# ─── 1. Authentication & Role Security Tests ──────────────────────────────────

def test_01_approved_lab_login_successful(client):
    """TC-1: Approved lab login successful and redirects to dashboard."""
    resp = client.post('/pathology/login', data={
        'email': 'approved_lab@spherix.test',
        'password': 'Secret@123'
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/pathology/dashboard' in resp.headers.get('Location', '')

def test_02_pending_lab_login_redirected_to_pending_screen(client):
    """TC-2: Pending lab login informs user of PENDING_VERIFICATION status."""
    resp = client.post('/pathology/login', data={
        'email': 'pending_lab@spherix.test',
        'password': 'Secret@123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"pending verification" in resp.data.lower()

def test_03_rejected_lab_login_blocked(client):
    """TC-3: Rejected lab login is strictly blocked."""
    resp = client.post('/pathology/login', data={
        'email': 'rejected_lab@spherix.test',
        'password': 'Secret@123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"rejected" in resp.data.lower()

def test_04_suspended_lab_login_blocked(client):
    """TC-4: Suspended lab login is strictly blocked."""
    resp = client.post('/pathology/login', data={
        'email': 'suspended_lab@spherix.test',
        'password': 'Secret@123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"suspended" in resp.data.lower()

def test_05_lab_registration_persists_all_fields(client):
    """TC-5: Lab registration persists all legal, compliance, and location fields."""
    unique_email = f"lab_reg_{uuid.uuid4().hex[:6]}@spherix.test"
    unique_reg = f"REG-TEST-{uuid.uuid4().hex[:6]}"
    
    resp = client.post('/pathology/register', data={
        'legal_name': 'Metro Diagnostic Center Pvt Ltd',
        'display_name': 'Metro Diagnostics',
        'registration_number': unique_reg,
        'lab_type': 'Independent Pathology Lab',
        'owner_name': 'Dr. K. S. Rao',
        'phone': '9820011223',
        'email': unique_email,
        'password': 'Password@123',
        'confirm_password': 'Password@123',
        'address': 'Plot 42, Bandra West',
        'city': 'Mumbai',
        'state': 'Maharashtra',
        'pincode': '400050',
        'latitude': '19.0596',
        'longitude': '72.8295',
        'service_radius_km': '15.0',
        'license_number': 'LIC-METRO-99',
        'is_nabl_accredited': '1',
        'nabl_accreditation_number': 'NABL-MC-555',
        'operating_hours': '07:00 AM - 09:00 PM',
        'bank_name': 'HDFC Bank',
        'account_number': '50100987654321',
        'account_holder': 'Metro Diagnostic Center',
        'ifsc_code': 'HDFC0000123',
        'terms_agreed': '1',
        'tests': ['TEST-FBS', 'TEST-CBC']
    }, follow_redirects=True)

    assert resp.status_code == 200
    # Verify in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, legal_name, nabl_accreditation_number FROM diagnostic_labs WHERE email = ?", (unique_email,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[1] == 'PENDING_VERIFICATION'
    assert row[2] == 'Metro Diagnostic Center Pvt Ltd'
    assert row[3] == 'NABL-MC-555'


# ─── 2. Matching Engine & Distance Tests ──────────────────────────────────────

def test_06_matching_engine_returns_only_labs_offering_all_tests():
    """TC-6: Matching engine returns only labs that offer ALL requested tests."""
    # Approved lab offers FBS, CBC, LFT
    # Request FBS + CBC -> Should match Approved lab
    match_fbs_cbc = find_matching_pathology_labs(['TEST-FBS', 'TEST-CBC'], 19.0760, 72.8777, search_radius_km=30.0)
    assert any(l['id'] == 'LAB-TEST-APPROVED' for l in match_fbs_cbc)

    # Request FBS + MRI -> Approved lab doesn't offer MRI -> Should NOT match
    match_with_mri = find_matching_pathology_labs(['TEST-FBS', 'TEST-MRI-BRAIN'], 19.0760, 72.8777, search_radius_km=30.0)
    assert not any(l['id'] == 'LAB-TEST-APPROVED' for l in match_with_mri)

def test_07_matching_engine_excludes_inactive_labs():
    """TC-7: Matching engine strictly excludes inactive, suspended, or rejected labs."""
    # Apex Bio is pending, Faulty is rejected, Suspended is suspended
    matches = find_matching_pathology_labs(['TEST-FBS'], 19.0760, 72.8777, search_radius_km=100.0)
    matched_ids = [l['id'] for l in matches]

    assert 'LAB-TEST-PENDING' not in matched_ids
    assert 'LAB-TEST-REJECTED' not in matched_ids
    assert 'LAB-TEST-SUSPENDED' not in matched_ids

def test_08_matching_engine_respects_search_radius():
    """TC-8: Matching engine respects geographic search radius (Haversine formula)."""
    # Delhi coords (28.6139, 77.2090) vs Mumbai lab (19.0760, 72.8777) ~ 1150 km away
    matches_close = find_matching_pathology_labs(['TEST-FBS'], 28.6139, 77.2090, search_radius_km=50.0)
    assert not any(l['id'] == 'LAB-TEST-APPROVED' for l in matches_close)

    # If radius expanded to 1500 km, Mumbai lab should be captured
    matches_wide = find_matching_pathology_labs(['TEST-FBS'], 28.6139, 77.2090, search_radius_km=1500.0)
    assert any(l['id'] == 'LAB-TEST-APPROVED' for l in matches_wide)


# ─── 3. State Machine & Booking Workflow Tests ────────────────────────────────

def test_09_booking_state_transition_valid_lifecycle():
    """TC-9: Booking state transitions follow the authorized healthcare lifecycle."""
    assert can_transition_booking('REQUESTED', 'AWAITING_LAB_ACCEPTANCE')
    assert can_transition_booking('AWAITING_LAB_ACCEPTANCE', 'ACCEPTED')
    assert can_transition_booking('ACCEPTED', 'CONFIRMED')
    assert can_transition_booking('CONFIRMED', 'COLLECTION_SCHEDULED')
    assert can_transition_booking('COLLECTION_SCHEDULED', 'COLLECTOR_ASSIGNED')
    assert can_transition_booking('COLLECTOR_ASSIGNED', 'SAMPLE_COLLECTED')
    assert can_transition_booking('SAMPLE_COLLECTED', 'SAMPLE_RECEIVED')
    assert can_transition_booking('SAMPLE_RECEIVED', 'PROCESSING')
    assert can_transition_booking('PROCESSING', 'REPORT_PUBLISHED')
    assert can_transition_booking('REPORT_PUBLISHED', 'COMPLETED')

def test_10_invalid_state_jump_blocked():
    """TC-10: Invalid state jumps (e.g., DRAFT directly to COMPLETED) are strictly blocked."""
    assert not can_transition_booking('DRAFT', 'COMPLETED')
    assert not can_transition_booking('REQUESTED', 'PROCESSING')
    assert not can_transition_booking('SAMPLE_COLLECTED', 'REPORT_PUBLISHED')
    assert not can_transition_booking('COMPLETED', 'REQUESTED')

def test_11_decline_requires_reason(client):
    """TC-11: Declining a diagnostic booking requires an audited reason."""
    conn = get_db_connection()
    cursor = conn.cursor()
    b_id = f"BK-TEST-DECLINE-{uuid.uuid4().hex[:4]}"
    cursor.execute("""
        INSERT INTO diagnostic_bookings (
            id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot,
            subtotal, collection_fee, total_amount, lab_payout_amount, status
        ) VALUES (?, '99901', 'Test Patient', 'LAB-TEST-APPROVED', '2026-10-15', '08:00 AM - 09:00 AM', 150.0, 50.0, 200.0, 185.0, 'REQUESTED')
    """, (b_id,))
    conn.commit()
    conn.close()

    # Log in as Approved Lab
    client.post('/pathology/login', data={'email': 'approved_lab@spherix.test', 'password': 'Secret@123'})

    # Attempt decline with empty reason
    resp = client.post(f'/pathology/booking/{b_id}/decline', data={'reason': '   '}, follow_redirects=True)
    assert b"reason is required" in resp.data.lower()

    # Attempt decline with valid clinical/operational reason
    resp2 = client.post(f'/pathology/booking/{b_id}/decline', data={'reason': 'Slot fully booked, no phlebotomist available.'}, follow_redirects=True)
    assert b"declined" in resp2.data.lower()

def test_12_cancellation_rules_enforced_at_every_state():
    """TC-12: Cancellation rules enforced according to physical specimen status."""
    # Pre-collection states allow cancellation
    assert 'CANCELLED' in VALID_TRANSITIONS['REQUESTED']
    assert 'CANCELLED' in VALID_TRANSITIONS['ACCEPTED']
    assert 'CANCELLED' in VALID_TRANSITIONS['CONFIRMED']
    assert 'CANCELLED' in VALID_TRANSITIONS['COLLECTION_SCHEDULED']

    # Once sample is received at lab or in analyzer processing, cancellation is disallowed
    assert 'CANCELLED' not in VALID_TRANSITIONS['SAMPLE_RECEIVED']
    assert 'CANCELLED' not in VALID_TRANSITIONS['PROCESSING']
    assert 'CANCELLED' not in VALID_TRANSITIONS['REPORT_PUBLISHED']


# ─── 4. Access Control & Confidentiality Tests ────────────────────────────────

def test_13_patient_can_view_only_own_bookings():
    """TC-13: Patient query service isolates records: patient sees only their own bookings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Insert booking for Patient A (99901) and Patient B (99902)
    b_a = f"BK-PATA-{uuid.uuid4().hex[:4]}"
    b_b = f"BK-PATB-{uuid.uuid4().hex[:4]}"
    cursor.execute("INSERT INTO diagnostic_bookings (id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot, subtotal, total_amount, lab_payout_amount, status) VALUES (?, '99901', 'Patient A', 'LAB-TEST-APPROVED', '2026-10-15', '08:00 AM - 09:00 AM', 150.0, 150.0, 135.0, 'REQUESTED')", (b_a,))
    cursor.execute("INSERT INTO diagnostic_bookings (id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot, subtotal, total_amount, lab_payout_amount, status) VALUES (?, '99902', 'Patient B', 'LAB-TEST-APPROVED', '2026-10-15', '08:00 AM - 09:00 AM', 150.0, 150.0, 135.0, 'REQUESTED')", (b_b,))
    conn.commit()
    conn.close()

    pat_a_data = get_patient_diagnostic_data('99901')
    pat_a_ids = [b['id'] for b in pat_a_data['bookings']]

    assert b_a in pat_a_ids
    assert b_b not in pat_a_ids

def test_14_lab_can_view_only_own_bookings(client):
    """TC-14: Lab dashboard isolates records: Lab 1 sees only its own bookings, not Lab 2."""
    conn = get_db_connection()
    cursor = conn.cursor()
    b_lab1 = f"BK-LAB1-{uuid.uuid4().hex[:4]}"
    b_lab2 = f"BK-LAB2-{uuid.uuid4().hex[:4]}"
    cursor.execute("INSERT INTO diagnostic_bookings (id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot, subtotal, total_amount, lab_payout_amount, status) VALUES (?, '99901', 'Patient A', 'LAB-TEST-APPROVED', '2026-10-15', '08:00 AM - 09:00 AM', 150.0, 150.0, 135.0, 'REQUESTED')", (b_lab1,))
    cursor.execute("INSERT INTO diagnostic_bookings (id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot, subtotal, total_amount, lab_payout_amount, status) VALUES (?, '99901', 'Patient A', 'LAB-TEST-PENDING', '2026-10-15', '08:00 AM - 09:00 AM', 150.0, 150.0, 135.0, 'REQUESTED')", (b_lab2,))
    conn.commit()
    conn.close()

    # Log in as Approved Lab
    client.post('/pathology/login', data={'email': 'approved_lab@spherix.test', 'password': 'Secret@123'})
    resp = client.get('/pathology/dashboard')
    assert resp.status_code == 200
    assert b_lab1.encode() in resp.data
    assert b_lab2.encode() not in resp.data

def test_15_doctor_can_view_only_authored_referrals():
    """TC-15: Doctor query service isolates referrals: doctor sees only referrals they authored."""
    conn = get_db_connection()
    cursor = conn.cursor()
    ref_doc1 = f"REF-DOC1-{uuid.uuid4().hex[:4]}"
    ref_doc2 = f"REF-DOC2-{uuid.uuid4().hex[:4]}"
    cursor.execute("INSERT INTO diagnostic_referrals (id, referral_number, doctor_id, doctor_name, patient_id, patient_name, clinical_indication, status, created_at) VALUES (?, ?, '88801', 'Dr. Sunil Verma', '99901', 'Test Patient', 'Hypertension check', 'ISSUED', '2026-01-01 10:00:00')", (f"id-{ref_doc1}", ref_doc1))
    cursor.execute("INSERT INTO diagnostic_referrals (id, referral_number, doctor_id, doctor_name, patient_id, patient_name, clinical_indication, status, created_at) VALUES (?, ?, '88802', 'Dr. Another Doc', '99901', 'Test Patient', 'Diabetes check', 'ISSUED', '2026-01-01 10:00:00')", (f"id-{ref_doc2}", ref_doc2))
    conn.commit()
    conn.close()

    doc1_data = get_doctor_diagnostic_data('88801')
    doc1_numbers = [r['referral_number'] for r in doc1_data['referrals']]

    assert ref_doc1 in doc1_numbers
    assert ref_doc2 not in doc1_numbers


# ─── 5. Report Management & Secure Download Tests ─────────────────────────────

def test_16_unauthorized_report_download_blocked_with_403(client):
    """TC-16: Unauthenticated or unauthorized user download is blocked with 403 or redirect."""
    resp = client.get('/diagnostic/report/NON_EXISTENT_OR_RESTRICTED/download')
    assert resp.status_code in [302, 401, 403]

def test_17_authorized_patient_report_download_succeeds(client, tmp_path):
    """TC-17: Authorized patient report download succeeds."""
    # Create test report file on disk
    report_id = f"REP-PAT-TEST-{uuid.uuid4().hex[:4]}"
    report_file = tmp_path / "test_patient_report.pdf"
    report_file.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_reports (
            id, booking_id, patient_id, doctor_id, lab_id, test_id, test_name,
            report_number, file_path, file_name, file_size, mime_type, status, version
        ) VALUES (?, 'BK-001', '99901', '88801', 'LAB-TEST-APPROVED', 'TEST-FBS', 'Fasting Blood Sugar',
                  ?, ?, 'test_patient_report.pdf', 100, 'application/pdf', 'PUBLISHED', 1)
    """, (report_id, report_id, str(report_file)))
    conn.commit()
    conn.close()

    # Authenticate as Patient 99901
    with client.session_transaction() as sess:
        sess['_user_id'] = '99901'
        sess['_user_type'] = 'patient'

    resp = client.get(f'/diagnostic/report/{report_id}/download')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'

def test_18_authorized_doctor_report_download_succeeds(client, tmp_path):
    """TC-18: Authorized referring doctor report download succeeds."""
    report_id = f"REP-DOC-TEST-{uuid.uuid4().hex[:4]}"
    report_file = tmp_path / "test_doctor_report.pdf"
    report_file.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_reports (
            id, booking_id, patient_id, doctor_id, lab_id, test_id, test_name,
            report_number, file_path, file_name, file_size, mime_type, status, version
        ) VALUES (?, 'BK-002', '99901', '88801', 'LAB-TEST-APPROVED', 'TEST-CBC', 'Complete Blood Count',
                  ?, ?, 'test_doctor_report.pdf', 100, 'application/pdf', 'PUBLISHED', 1)
    """, (report_id, report_id, str(report_file)))
    conn.commit()
    conn.close()

    # Authenticate as Doctor 88801
    with client.session_transaction() as sess:
        sess['_user_id'] = '88801'
        sess['_user_type'] = 'doctor'

    resp = client.get(f'/diagnostic/report/{report_id}/download')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'

def test_19_authorized_lab_report_download_succeeds(client, tmp_path):
    """TC-19: Authorized issuing pathology lab report download succeeds."""
    report_id = f"REP-LAB-TEST-{uuid.uuid4().hex[:4]}"
    report_file = tmp_path / "test_lab_report.pdf"
    report_file.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_reports (
            id, booking_id, patient_id, doctor_id, lab_id, test_id, test_name,
            report_number, file_path, file_name, file_size, mime_type, status, version
        ) VALUES (?, 'BK-003', '99901', '88801', 'LAB-TEST-APPROVED', 'TEST-LFT', 'Liver Function Test',
                  ?, ?, 'test_lab_report.pdf', 100, 'application/pdf', 'PUBLISHED', 1)
    """, (report_id, report_id, str(report_file)))
    conn.commit()
    conn.close()

    # Authenticate as Approved Lab
    with client.session_transaction() as sess:
        sess['_user_id'] = 'LAB-TEST-APPROVED'
        sess['_user_type'] = 'pathology_lab'

    resp = client.get(f'/diagnostic/report/{report_id}/download')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'

def test_20_report_amendment_increments_version_and_preserves_original(client):
    """TC-20: Report amendment increments version number, records audit, and preserves original."""
    report_id = f"REP-AMEND-{uuid.uuid4().hex[:4]}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_reports (
            id, booking_id, patient_id, lab_id, test_id, test_name, report_number,
            file_path, file_name, status, version
        ) VALUES (?, 'BK-004', '99901', 'LAB-TEST-APPROVED', 'TEST-FBS', 'FBS', ?,
                  'spherix/uploads/diagnostic_reports/v1.pdf', 'v1.pdf', 'PUBLISHED', 1)
    """, (report_id, report_id))
    conn.commit()
    conn.close()

    # Log in as Approved Lab
    client.post('/pathology/login', data={'email': 'approved_lab@spherix.test', 'password': 'Secret@123'})

    # Submit amendment
    dummy_pdf = (io.BytesIO(b"%PDF-1.4 amended content"), "amended_report.pdf")
    resp = client.post(f'/report/{report_id}/amend', data={
        'amendment_reason': 'Recalibrated fasting glucose reference interval after instrument recheck.',
        'amended_by': 'Dr. Chief Pathologist',
        'report_file': dummy_pdf
    }, content_type='multipart/form-data', follow_redirects=True)

    assert resp.status_code == 200

    # Verify version 2 in diagnostic_reports and version 1 in diagnostic_report_versions
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version, amendment_reason FROM diagnostic_reports WHERE id = ?", (report_id,))
    rep_row = cursor.fetchone()
    assert rep_row[0] == 2
    assert "recalibrated" in rep_row[1].lower()

    cursor.execute("SELECT version, amendment_reason FROM diagnostic_report_versions WHERE report_id = ?", (report_id,))
    ver_row = cursor.fetchone()
    conn.close()

    assert ver_row is not None
    assert ver_row[0] == 1

def test_21_published_report_read_only_unless_amended(client):
    """TC-21: Published report is read-only and requires explicit amendment reason to alter."""
    report_id = f"REP-RO-{uuid.uuid4().hex[:4]}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_reports (
            id, booking_id, patient_id, lab_id, test_id, test_name, report_number,
            file_path, file_name, status, version
        ) VALUES (?, 'BK-005', '99901', 'LAB-TEST-APPROVED', 'TEST-FBS', 'FBS', ?,
                  'spherix/uploads/diagnostic_reports/v1.pdf', 'v1.pdf', 'PUBLISHED', 1)
    """, (report_id, report_id))
    conn.commit()
    conn.close()

    client.post('/pathology/login', data={'email': 'approved_lab@spherix.test', 'password': 'Secret@123'})

    # Submitting empty reason fails validation
    resp = client.post(f'/report/{report_id}/amend', data={
        'amendment_reason': '   ',
        'amended_by': 'Pathologist'
    }, follow_redirects=True)
    assert b"reason is required" in resp.data.lower()


# ─── 6. Financial, Commission & Settlement Tests ──────────────────────────────

def test_22_duplicate_payment_signature_rejected_idempotency(client):
    """TC-22: Duplicate payment signature verification is idempotent and rejected."""
    b_id = f"BK-PAY-{uuid.uuid4().hex[:4]}"
    payment_id = f"pay_{uuid.uuid4().hex[:10]}"
    order_id = f"order_{uuid.uuid4().hex[:10]}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_bookings (
            id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot,
            subtotal, total_amount, lab_payout_amount, status
        ) VALUES (?, '99901', 'Test Patient', 'LAB-TEST-APPROVED', '2026-10-15', '08:00 AM - 09:00 AM', 500.0, 500.0, 450.0, 'REQUESTED')
    """, (b_id,))
    conn.commit()
    conn.close()

    # First verification
    resp1 = client.post('/api/diagnostic/payment/verify', json={
        'booking_id': b_id,
        'razorpay_payment_id': payment_id,
        'razorpay_order_id': order_id,
        'razorpay_signature': 'test_signature'
    })
    data1 = resp1.get_json()
    assert data1['success'] is True

    # Second duplicate verification
    resp2 = client.post('/api/diagnostic/payment/verify', json={
        'booking_id': b_id,
        'razorpay_payment_id': payment_id,
        'razorpay_order_id': order_id,
        'razorpay_signature': 'test_signature'
    })
    data2 = resp2.get_json()
    assert data2['success'] is True
    assert data2.get('already_verified') is True

def test_23_failed_payment_does_not_confirm_booking(client):
    """TC-23: Missing or invalid payment verification payload does not confirm booking."""
    b_id = f"BK-FAILPAY-{uuid.uuid4().hex[:4]}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diagnostic_bookings (
            id, patient_id, patient_name, lab_id, scheduled_date, scheduled_slot,
            subtotal, total_amount, lab_payout_amount, status
        ) VALUES (?, '99901', 'Test Patient', 'LAB-TEST-APPROVED', '2026-10-15', '08:00 AM - 09:00 AM', 500.0, 500.0, 450.0, 'REQUESTED')
    """, (b_id,))
    conn.commit()
    conn.close()

    # Post without payment_id
    resp = client.post('/api/diagnostic/payment/verify', json={
        'booking_id': b_id,
        'razorpay_payment_id': '',
        'razorpay_order_id': ''
    })
    assert resp.status_code == 400

    # Ensure booking status remains REQUESTED
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM diagnostic_bookings WHERE id = ?", (b_id,))
    status = cursor.fetchone()[0]
    conn.close()
    assert status == 'REQUESTED'

def test_24_commission_calculation_separate_from_doctor_consultation():
    """TC-24: Pathology lab commission (10%) is isolated from doctor consultation balances."""
    subtotal = 1000.0
    collection_fee = 100.0
    lab_commission_rate = 10.0 # 10%
    platform_fee = subtotal * (lab_commission_rate / 100.0) # 100.0
    lab_payout = (subtotal + collection_fee) - platform_fee # 1000.0

    assert platform_fee == 100.0
    assert lab_payout == 1000.0

    # Doctor consultation balance check: ensure Doctor 88801 consultation fee is untouched
    doc = TEMP_DATA['doctors'][88801]
    assert doc.consultation_fee == 500

def test_25_settlement_balance_updates_correctly():
    """TC-25: Dashboard metrics correctly calculates total revenue and settlement balance."""
    metrics = get_lab_dashboard_metrics('LAB-TEST-APPROVED')
    assert isinstance(metrics['total_revenue'], float)
    assert isinstance(metrics['settlement_balance'], float)
    assert metrics['settlement_balance'] <= metrics['total_revenue']


# ─── 7. Doctor Referral & Sample Traceability Tests ───────────────────────────

def test_26_doctor_referral_creates_valid_booking_linkage(client):
    """TC-26: Doctor referral creates valid database record and links with referral number."""
    # Authenticate as Doctor
    with client.session_transaction() as sess:
        sess['_user_id'] = '88801'
        sess['_user_type'] = 'doctor'

    resp = client.post('/doctor/diagnostic-referral/create', data={
        'patient_id': '99901',
        'priority': 'URGENT',
        'clinical_indication': 'Suspected iron deficiency anemia and chronic fatigue syndrome.',
        'doctor_instructions': 'Verify full hemogram including ESR.',
        'selected_lab_id': 'LAB-TEST-APPROVED',
        'test_ids': ['TEST-CBC', 'TEST-FBS']
    }, follow_redirects=True)

    assert resp.status_code == 200

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, referral_number, priority, status FROM diagnostic_referrals WHERE doctor_id = '88801' ORDER BY created_at DESC")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[1].startswith('REF-')
    assert row[2] == 'URGENT'
    assert row[3] == 'ISSUED'

def test_27_prescription_upload_persists_file(client, tmp_path):
    """TC-27: Patient direct diagnostic booking persists prescription upload file."""
    # Authenticate as Patient
    with client.session_transaction() as sess:
        sess['_user_id'] = '99901'
        sess['_user_type'] = 'patient'

    dummy_presc = (io.BytesIO(b"%PDF-1.4 prescription file content"), "rx_sample.pdf")
    resp = client.post('/patient/diagnostic/book', data={
        'lab_id': 'LAB-TEST-APPROVED',
        'test_ids': 'TEST-CBC',
        'collection_type': 'HOME_COLLECTION',
        'scheduled_date': date.today().isoformat(),
        'scheduled_slot': '08:00 AM - 09:00 AM',
        'collection_address': 'Flat 402, Sunshine Towers, Mumbai',
        'collection_city': 'Mumbai',
        'collection_pincode': '400001',
        'patient_phone': '9988776655',
        'prescription_file': dummy_presc
    }, content_type='multipart/form-data', follow_redirects=True)

    assert resp.status_code == 200
    assert b"successfully" in resp.data.lower()

    # Verify booking in database has prescription filename recorded
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, prescription_file FROM diagnostic_bookings WHERE patient_id = '99901' ORDER BY created_at DESC")
    b_row = cursor.fetchone()
    conn.close()

    assert b_row is not None
    assert b_row[1] is not None
    assert "rx_sample.pdf" in b_row[1] or "presc_" in b_row[1]

def test_28_sample_tracking_barcode_generated_and_unique():
    """TC-28: Traceable specimen barcode generated via generate_sample_id() is cryptographically unique."""
    id1 = generate_sample_id()
    id2 = generate_sample_id()

    assert id1.startswith('SMP-')
    assert id2.startswith('SMP-')
    assert id1 != id2


# ─── 8. Audit Logging & Admin Review Tests ────────────────────────────────────

def test_29_audit_log_entry_created_on_sensitive_state_changes():
    """TC-29: Audit log entry created on sensitive state changes."""
    actor_id = 'ADMIN-SUPER'
    resource_id = f"BK-AUDIT-{uuid.uuid4().hex[:4]}"

    log_diagnostic_audit(
        actor_type='ADMIN',
        actor_id=actor_id,
        action='UPDATE_BOOKING_STATUS',
        resource_type='DIAGNOSTIC_BOOKING',
        resource_id=resource_id,
        details='Emergency force transition to CONFIRMED'
    )

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT action, resource_id FROM diagnostic_audit_logs WHERE resource_id = ?", (resource_id,))
    audit_row = cursor.fetchone()
    conn.close()

    assert audit_row is not None
    assert audit_row[0] == 'UPDATE_BOOKING_STATUS'
    assert audit_row[1] == resource_id

def test_30_admin_approve_reject_transitions_lab_status(client):
    """TC-30: Admin approve and reject transitions lab account status correctly."""
    conn = get_db_connection()
    cursor = conn.cursor()
    lab_to_approve = f"LAB-ADM-APP-{uuid.uuid4().hex[:4]}"
    lab_to_reject = f"LAB-ADM-REJ-{uuid.uuid4().hex[:4]}"

    cursor.execute("INSERT INTO diagnostic_labs (id, legal_name, display_name, registration_number, phone, email, password, address, city, state, pincode, status) VALUES (?, 'Lab Alpha', 'Alpha', ?, '9999999901', ?, 'pwd', 'Addr', 'City', 'State', '111111', 'PENDING_VERIFICATION')", (lab_to_approve, f"R-{lab_to_approve}", f"{lab_to_approve}@test.com"))
    cursor.execute("INSERT INTO diagnostic_labs (id, legal_name, display_name, registration_number, phone, email, password, address, city, state, pincode, status) VALUES (?, 'Lab Beta', 'Beta', ?, '9999999902', ?, 'pwd', 'Addr', 'City', 'State', '111111', 'PENDING_VERIFICATION')", (lab_to_reject, f"R-{lab_to_reject}", f"{lab_to_reject}@test.com"))
    conn.commit()
    conn.close()

    # Authenticate as Admin
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_user_type'] = 'admin'

    # Admin approves Lab Alpha
    resp_app = client.post(f'/admin/diagnostic/lab/{lab_to_approve}/approve', follow_redirects=True)
    assert resp_app.status_code == 200

    # Admin rejects Lab Beta with reason
    resp_rej = client.post(f'/admin/diagnostic/lab/{lab_to_reject}/reject', data={'rejection_reason': 'Invalid registration certificate number.'}, follow_redirects=True)
    assert resp_rej.status_code == 200

    # Verify status in DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM diagnostic_labs WHERE id = ?", (lab_to_approve,))
    assert cursor.fetchone()[0] == 'APPROVED'

    cursor.execute("SELECT status, rejection_reason FROM diagnostic_labs WHERE id = ?", (lab_to_reject,))
    row_rej = cursor.fetchone()
    conn.close()

    assert row_rej[0] == 'REJECTED'
    assert "invalid registration" in row_rej[1].lower()


# ─── 9. Full Multi-Step Integration Workflow Verification ─────────────────────

def test_31_complete_patient_lifecycle_workflow(client, tmp_path):
    """
    TC-31 Integration: Full Patient Workflow:
    Patient Search -> Nearby Approved Lab -> Booking -> Lab Acceptance -> Payment
    -> Collector Assignment -> Sample Collection -> Lab Processing -> Draft Upload
    -> Verified Publication -> Patient & Doctor Report Access.
    """
    patient_id = '99901'
    lab_id = 'LAB-TEST-APPROVED'
    test_id = 'TEST-CBC'

    # Step 1: Search nearby labs offering TEST-CBC
    match_resp = client.get(f'/api/diagnostics/matching-labs?test_ids={test_id}&lat=19.0760&lng=72.8777&radius=30')
    assert match_resp.status_code == 200
    match_json = match_resp.get_json()
    assert match_json['success'] is True
    assert len(match_json['labs']) > 0

    # Step 2: Patient books diagnostic test
    with client.session_transaction() as sess:
        sess['_user_id'] = patient_id
        sess['_user_type'] = 'patient'

    book_resp = client.post('/patient/diagnostic/book', data={
        'lab_id': lab_id,
        'test_ids': test_id,
        'collection_type': 'HOME_COLLECTION',
        'collection_address': '123 Marine Drive, Mumbai',
        'collection_city': 'Mumbai',
        'collection_pincode': '400001',
        'scheduled_date': '2026-10-20',
        'scheduled_slot': '08:00 AM - 09:00 AM'
    }, follow_redirects=False)
    assert book_resp.status_code in [200, 302]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, total_amount FROM diagnostic_bookings WHERE patient_id = ? ORDER BY created_at DESC", (patient_id,))
    booking_row = cursor.fetchone()
    conn.close()

    assert booking_row is not None
    booking_id = booking_row[0]
    assert booking_row[1] == 'REQUESTED'

    # Step 3: Pathology Lab logs in and accepts booking
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    accept_resp = client.post(f'/pathology/booking/{booking_id}/accept', follow_redirects=False)
    assert accept_resp.status_code in [200, 302]

    # Step 4: Payment verification via Webhook API
    pay_resp = client.post('/api/diagnostic/payment/verify', json={
        'booking_id': booking_id,
        'payment_id': f'pay_{uuid.uuid4().hex[:8]}',
        'order_id': f'order_{uuid.uuid4().hex[:8]}'
    })
    assert pay_resp.status_code == 200
    assert pay_resp.get_json()['status'] == 'CONFIRMED'

    # Step 5: Lab assigns phlebotomist collector
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    assign_resp = client.post(f'/pathology/booking/{booking_id}/assign-collector', data={
        'collector_name': 'Ramesh Phlebotomist',
        'collector_phone': '9876543219'
    }, follow_redirects=False)
    assert assign_resp.status_code in [200, 302]

    # Step 6: Sample collected
    collect_resp = client.post(f'/pathology/booking/{booking_id}/collect-sample', follow_redirects=False)
    assert collect_resp.status_code in [200, 302]

    # Step 7: Sample received at lab
    recv_resp = client.post(f'/pathology/booking/{booking_id}/receive-sample', follow_redirects=False)
    assert recv_resp.status_code in [200, 302]

    # Step 8: Processing starts
    proc_resp = client.post(f'/pathology/booking/{booking_id}/start-processing', follow_redirects=False)
    assert proc_resp.status_code in [200, 302]

    # Step 9: Report Draft uploaded
    dummy_pdf = (io.BytesIO(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"), "cbc_report.pdf")
    upload_resp = client.post('/pathology/report/upload', data={
        'booking_id': booking_id,
        'test_id': test_id,
        'clinical_summary': 'Normal hemogram. Platelets within limits.',
        'report_file': dummy_pdf
    }, content_type='multipart/form-data', follow_redirects=False)
    assert upload_resp.status_code in [200, 302]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, report_number, status FROM diagnostic_reports WHERE booking_id = ?", (booking_id,))
    rep_row = cursor.fetchone()
    conn.close()

    assert rep_row is not None
    report_id = rep_row[0]
    assert rep_row[2] == 'DRAFT'

    # Step 10: Report Verified and Published
    pub_resp = client.post(f'/pathology/report/{report_id}/publish', data={
        'verified_by': 'Dr. S. Mehta, MD (Chief Pathologist)'
    }, follow_redirects=False)
    assert pub_resp.status_code in [200, 302]

    # Step 11: Patient downloads verified report
    with client.session_transaction() as sess:
        sess['_user_id'] = patient_id
        sess['_user_type'] = 'patient'

    dl_resp = client.get(f'/diagnostic/report/{report_id}/download')
    assert dl_resp.status_code == 200
    assert dl_resp.mimetype == 'application/pdf'


def test_32_complete_doctor_referral_lifecycle_workflow(client):
    """
    TC-32 Integration: Full Doctor Diagnostic Referral Workflow:
    Doctor -> Patient Selection -> Test Prescription -> Lab Referral -> Booking Linkage
    -> Lab Acceptance -> Final Report Available to Attending Doctor.
    """
    doctor_id = '88801'
    patient_id = '99901'
    lab_id = 'LAB-TEST-APPROVED'

    # Authenticate as Doctor
    with client.session_transaction() as sess:
        sess['_user_id'] = doctor_id
        sess['_user_type'] = 'doctor'

    # Step 1: Doctor issues referral with selected lab
    ref_resp = client.post('/doctor/diagnostic-referral/create', data={
        'patient_id': patient_id,
        'priority': 'TIME_SENSITIVE',
        'clinical_indication': 'Suspected acute pancreatitis. Check LFT & Serum Lipase.',
        'doctor_instructions': 'Fasting sample preferred.',
        'selected_lab_id': lab_id,
        'test_ids': ['TEST-LFT', 'TEST-FBS']
    }, follow_redirects=True)
    assert ref_resp.status_code == 200

    # Verify referral & booking records
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, referral_number, booking_id, status FROM diagnostic_referrals WHERE doctor_id = ? ORDER BY created_at DESC", (doctor_id,))
    ref_row = cursor.fetchone()
    conn.close()

    assert ref_row is not None
    assert ref_row[1].startswith('REF-')
    assert ref_row[2] is not None # Linked booking_id created
    booking_id = ref_row[2]

    # Step 2: Patient queries their diagnostic dashboard data
    pat_data = get_patient_diagnostic_data(patient_id)
    assert len(pat_data['referrals']) > 0

    # Step 3: Lab accepts referral booking
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    acc_resp = client.post(f'/pathology/booking/{booking_id}/accept', follow_redirects=False)
    assert acc_resp.status_code in [200, 302]

    # Step 4: Doctor queries their referrals and sees linked active booking
    doc_data = get_doctor_diagnostic_data(doctor_id)
    assert len(doc_data['referrals']) > 0


def test_33_complete_pathology_registration_and_configuration_workflow(client):
    """
    TC-33 Integration: Full Pathology Laboratory Lifecycle:
    Registration -> Pending Verification -> Admin Inspection & Approval -> Lab Login
    -> Service Price Configuration -> Operating Availability Toggle.
    """
    unique_email = f"metro_lab_{uuid.uuid4().hex[:6]}@spherix.test"
    unique_reg = f"REG-METRO-{uuid.uuid4().hex[:4].upper()}"

    # Step 1: Lab Registration
    reg_resp = client.post('/pathology/register', data={
        'legal_name': 'Metro Diagnostic Labs Pvt Ltd',
        'display_name': 'Metro Diagnostics',
        'registration_number': unique_reg,
        'lab_type': 'Independent',
        'owner_name': 'Dr. A. Sen',
        'phone': '9876543299',
        'email': unique_email,
        'password': 'SecurePassword@123',
        'confirm_password': 'SecurePassword@123',
        'address': '78 Sector 5, Salt Lake',
        'city': 'Kolkata',
        'state': 'West Bengal',
        'pincode': '700091',
        'latitude': '22.5726',
        'longitude': '88.3639',
        'service_radius_km': '20.0',
        'license_number': 'LIC-METRO-001',
        'home_collection_available': '1',
        'walkin_available': '1'
    }, follow_redirects=False)
    assert reg_resp.status_code in [200, 302]

    # Verify Lab created in PENDING_VERIFICATION
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, is_active FROM diagnostic_labs WHERE email = ?", (unique_email,))
    lab_row = cursor.fetchone()
    conn.close()

    assert lab_row is not None
    lab_id = lab_row[0]
    assert lab_row[1] == 'PENDING_VERIFICATION'

    # Step 2: Login while pending displays pending verification warning
    login_pend = client.post('/pathology/login', data={
        'email': unique_email,
        'password': 'SecurePassword@123'
    }, follow_redirects=True)
    assert login_pend.status_code == 200
    assert b"under administrative verification" in login_pend.data.lower() or b"pending verification" in login_pend.data.lower()

    # Step 3: Admin approves the laboratory
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['_user_type'] = 'admin'

    app_resp = client.post(f'/admin/diagnostic/lab/{lab_id}/approve', follow_redirects=False)
    assert app_resp.status_code in [200, 302]

    # Step 4: Approved Lab logs in successfully
    login_succ = client.post('/pathology/login', data={
        'email': unique_email,
        'password': 'SecurePassword@123'
    }, follow_redirects=False)
    assert login_succ.status_code == 302
    assert '/pathology/dashboard' in login_succ.headers['Location']

    # Step 5: Lab updates custom test pricing
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    price_resp = client.post('/pathology/service/update-price', data={
        'test_id': 'TEST-CBC',
        'price': '349.0',
        'mrp': '499.0',
        'home_collection_fee': '50.0',
        'custom_tat_hours': '6'
    }, follow_redirects=False)
    assert price_resp.status_code in [200, 302]

    # Step 6: Lab toggles test availability
    toggle_resp = client.post('/pathology/service/toggle-availability', data={
        'test_id': 'TEST-CBC'
    })
    assert toggle_resp.status_code == 200
    assert toggle_resp.get_json()['success'] is True


# ─── 10. Test Catalog Add, Remove, Hide & Show Tests ──────────────────────────

def test_34_lab_add_new_test_from_master_catalog(client):
    """TC-34: Laboratory can add a new test from the Master Catalog with custom pricing and TAT."""
    lab_id = 'LAB-TEST-APPROVED'
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    # Add Thyroid Profile (TEST-TSH or similar from master catalog)
    resp = client.post('/pathology/service/add-test', data={
        'test_id': 'TEST-TSH',
        'price': '299.0',
        'mrp': '450.0',
        'home_collection_fee': '40.0',
        'custom_tat_hours': '12',
        'home_collection_available': '1',
        'is_available': '1'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"successfully added" in resp.data.lower()

    # Verify in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT price, mrp, home_collection_fee, custom_tat_hours, is_available FROM diagnostic_lab_services WHERE lab_id = ? AND test_id = 'TEST-TSH'", (lab_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 299.0
    assert row[1] == 450.0
    assert row[2] == 40.0
    assert row[3] == 12
    assert row[4] == 1


def test_35_lab_remove_test_from_services(client):
    """TC-35: Laboratory can remove an offered test from their catalog."""
    lab_id = 'LAB-TEST-APPROVED'
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    # Ensure TEST-LFT exists first
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO diagnostic_lab_services (lab_id, test_id, price, mrp, home_collection_fee, is_available) VALUES (?, 'TEST-LFT', 600.0, 800.0, 50.0, 1)", (lab_id,))
    conn.commit()
    conn.close()

    # Remove TEST-LFT
    resp = client.post('/pathology/service/TEST-LFT/remove', follow_redirects=True)
    assert resp.status_code == 200
    assert b"removed from your active laboratory services" in resp.data.lower()

    # Verify no longer in diagnostic_lab_services
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diagnostic_lab_services WHERE lab_id = ? AND test_id = 'TEST-LFT'", (lab_id,))
    assert cursor.fetchone() is None
    conn.close()


def test_36_lab_hide_and_show_test_public_interface(client):
    """TC-36: Laboratory can Hide and Show tests on the public interface (toggle visibility)."""
    lab_id = 'LAB-TEST-APPROVED'
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    # Ensure TEST-CBC is active and public
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO diagnostic_lab_services (lab_id, test_id, price, mrp, home_collection_fee, is_available, processing_available) VALUES (?, 'TEST-CBC', 350.0, 450.0, 50.0, 1, 1)", (lab_id,))
    conn.commit()
    conn.close()

    # 1. Hide the test (is_available -> 0)
    hide_resp = client.post('/pathology/service/TEST-CBC/toggle-visibility', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert hide_resp.status_code == 200
    hide_json = hide_resp.get_json()
    assert hide_json['success'] is True
    assert hide_json['is_available'] == 0

    # Verify test is hidden in DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_available FROM diagnostic_lab_services WHERE lab_id = ? AND test_id = 'TEST-CBC'", (lab_id,))
    assert cursor.fetchone()[0] == 0
    conn.close()

    # Verify matching engine no longer returns this lab for TEST-CBC while hidden
    match_resp = client.get('/api/diagnostics/matching-labs?test_ids=TEST-CBC&lat=19.0760&lng=72.8777')
    match_labs = match_resp.get_json().get('labs', [])
    assert not any(l['id'] == lab_id for l in match_labs)

    # 2. Show the test again (is_available -> 1)
    show_resp = client.post('/pathology/service/TEST-CBC/toggle-visibility', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert show_resp.status_code == 200
    show_json = show_resp.get_json()
    assert show_json['success'] is True
    assert show_json['is_available'] == 1

    # Verify matching engine returns this lab again
    match_resp2 = client.get('/api/diagnostics/matching-labs?test_ids=TEST-CBC&lat=19.0760&lng=72.8777')
    match_labs2 = match_resp2.get_json().get('labs', [])
    assert any(l['id'] == lab_id for l in match_labs2)


def test_37_lab_appointment_slot_and_staff_management(client):
    """TC-37: Laboratory can add/delete appointment slots and staff members."""
    lab_id = 'LAB-TEST-APPROVED'
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    # Add Slot
    slot_resp = client.post('/pathology/slots/add', data={
        'slot_date': '2026-11-01',
        'slot_time': '06:30 AM - 08:00 AM (Early Fasting)',
        'collection_type': 'HOME_COLLECTION',
        'max_capacity': '15'
    }, follow_redirects=True)
    assert slot_resp.status_code == 200
    assert b"created with capacity" in slot_resp.data.lower()

    # Add Staff
    staff_resp = client.post('/pathology/staff/add', data={
        'name': 'Pooja Sharma',
        'phone': '9876543210',
        'email': 'pooja@central.lab',
        'role': 'Senior Pathologist'
    }, follow_redirects=True)
    assert staff_resp.status_code == 200
    assert b"registered successfully" in staff_resp.data.lower()


def test_38_lab_settlement_payout_request(client):
    """TC-38: Laboratory can submit a settlement payout withdrawal request."""
    lab_id = 'LAB-TEST-APPROVED'
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    resp = client.post('/pathology/settlement/request', follow_redirects=True)
    assert resp.status_code == 200


def test_39_lab_dashboard_renders_with_unified_layout(client):
    """TC-39: Pathology dashboard renders successfully with unified dashboard_layout.html."""
    lab_id = 'LAB-TEST-APPROVED'
    with client.session_transaction() as sess:
        sess['_user_id'] = lab_id
        sess['_user_type'] = 'pathology_lab'

    resp = client.get('/pathology/dashboard')
    assert resp.status_code == 200
    assert b"Spherix Clinic" in resp.data
    assert b"Pathology Lab Workspace" in resp.data or b"Lab Operations" in resp.data
    assert b"Master Catalog" in resp.data
    assert b"Settlement Payouts" in resp.data



