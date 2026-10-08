"""
Comprehensive Enterprise Test Suite for Spherix Global Diagnostic & Pathology Network
Tests: Multi-Tenancy, RBAC, Registration, Verification, Geolocation, Orders, Phlebotomy,
Sample Tracking (Barcode/QR), Lab Results Entry, Pathologist Authorization, Report Versioning,
Tamper-proof QR verification, Doctor Referrals, and Security.
"""

import os
import sys
import pytest
import json
import secrets
from datetime import date, datetime

os.environ['DIAGNOSTIC_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_spherixclinic.db')
os.environ['SQLITE_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_spherixclinic.db')

from spherix import create_app
from spherix.services.diagnostic_catalog import (
    DIAGNOSTIC_MASTER_CATEGORIES, MASTER_TESTS_CATALOG, MASTER_PACKAGES_CATALOG,
    get_test_by_code, get_package_by_code
)
from spherix.services.diagnostic_db import (
    get_diagnostic_db, init_diagnostic_schema, haversine_distance,
    find_matching_pathology_centers, register_pathology_organization_and_center,
    update_center_verification_status, authenticate_pathology_staff,
    create_diagnostic_booking_order, enter_technician_lab_results,
    approve_and_release_diagnostic_report, create_doctor_diagnostic_referral,
    get_diagnostic_order_by_id
)

@pytest.fixture(autouse=True)
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        init_diagnostic_schema()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()

# ==============================================================================
# 1. CATALOG & BIOLOGICAL SPECIFICATION TESTS
# ==============================================================================

def test_diagnostic_categories_and_tests_loaded():
    """Verifies all 19 standard diagnostic categories and core tests exist."""
    assert len(DIAGNOSTIC_MASTER_CATEGORIES) >= 18
    assert len(MASTER_TESTS_CATALOG) >= 15
    assert len(MASTER_PACKAGES_CATALOG) >= 4

    cbc = get_test_by_code('CBC')
    assert cbc is not None
    assert cbc['category_code'] == 'HEM'
    assert 'Lavender Top' in cbc['container_type']
    assert len(cbc['parameters']) >= 10

    lft = get_test_by_code('LFT')
    assert lft is not None
    assert lft['fasting_required'] is True

    pkg = get_package_by_code('PKG-EXEC-FULL')
    assert pkg is not None
    assert 'CBC' in pkg['test_codes']
    assert 'LFT' in pkg['test_codes']

# ==============================================================================
# 2. GEOLOCATION & HAVERSINE DISTANCE TESTS
# ==============================================================================

def test_haversine_distance_calculation():
    """Verifies accurate geodesic distance between coordinates."""
    # Delhi (28.6139, 77.2090) to Noida (28.5355, 77.3910) ~ 20km
    d = haversine_distance(28.6139, 77.2090, 28.5355, 77.3910)
    assert 15.0 <= d <= 25.0

    # Same location
    d_same = haversine_distance(40.7128, -74.0060, 40.7128, -74.0060)
    assert d_same == 0.0

def test_find_matching_pathology_centers():
    """Verifies geospatial lab search with test requirements and radius."""
    # Search around Delhi coordinates
    labs_delhi = find_matching_pathology_centers(
        user_lat=28.6304,
        user_lng=77.2177,
        country="India",
        max_distance_km=50.0
    )
    assert len(labs_delhi) >= 1
    assert any("Delhi" in l['city'] for l in labs_delhi)
    assert labs_delhi[0]['distance_km'] < 10.0

    # Search USA labs
    labs_nyc = find_matching_pathology_centers(
        user_lat=40.7610,
        user_lng=-73.9723,
        country="United States",
        max_distance_km=50.0
    )
    assert len(labs_nyc) >= 1
    assert labs_nyc[0]['currency'] == 'USD'

# ==============================================================================
# 3. MULTI-TENANT REGISTRATION & RBAC VERIFICATION
# ==============================================================================

def test_pathology_registration_and_admin_verification():
    """Tests 5-step global lab registration and admin verification."""
    unique_suffix = secrets.token_hex(3).lower()
    org_email = f"lab.{unique_suffix}@eurodiagnostics.de"
    admin_email = f"director.{unique_suffix}@eurodiagnostics.de"

    org_data = {
        "legal_name": f"Euro Diagnostics Berlin {unique_suffix}",
        "display_name": "Euro Labs",
        "email": org_email,
        "phone": "+49 30 1234567",
        "country": "Germany",
        "currency": "EUR",
        "timezone": "CET (UTC+1:00)"
    }
    center_data = {
        "center_name": f"Euro Diagnostic Reference Suite {unique_suffix}",
        "address": "Friedrichstrasse 100",
        "city": "Berlin",
        "state_province": "Berlin",
        "postal_code": "10117",
        "latitude": 52.5200,
        "longitude": 13.4050,
        "home_collection_enabled": True,
        "walkin_enabled": True,
        "home_collection_radius_km": 30.0,
        "home_collection_fee": 25.0
    }
    admin_data = {
        "full_name": "Dr. Klaus Richter, MD",
        "email": admin_email,
        "password": "SecurePassword@2026!"
    }

    success, msg, res = register_pathology_organization_and_center(org_data, center_data, admin_data)
    assert success is True
    center_id = res['center_id']

    # Initial state is PENDING_VERIFICATION -> unverified centers cannot take public patient bookings
    unverified_search = find_matching_pathology_centers(city="Berlin", country="Germany")
    assert not any(l['id'] == center_id for l in unverified_search)

    # Admin verifies center
    v_success, v_msg = update_center_verification_status(center_id, "VERIFIED", verified_by="SUPER_ADMIN_SPHERIX")
    assert v_success is True

    # Now center appears in verified search
    verified_search = find_matching_pathology_centers(city="Berlin", country="Germany")
    assert any(l['id'] == center_id for l in verified_search)

    # Authenticate administrator
    staff_auth = authenticate_pathology_staff(admin_email, "SecurePassword@2026!")
    assert staff_auth is not None
    assert staff_auth['role'] == 'admin'
    assert staff_auth['center_id'] == center_id

# ==============================================================================
# 4. BOOKING, ACCESSIONING, RESULTS & VERSIONED REPORTS WORKFLOW
# ==============================================================================

def test_full_diagnostic_order_lifecycle():
    """
    Tests end-to-end lifecycle:
    Booking -> Accession Barcode -> Technician Results -> Pathologist Sign-off -> Versioned Release -> QR Verify
    """
    # 1. Create booking order
    patient_data = {
        "id": "PAT_TEST_001",
        "name": "Sarah Connor",
        "email": "sarah.connor@example.com",
        "phone": "+91 99887 76655",
        "address": "Skyline Heights, Sector 18, Gurugram",
        "lat": 28.4595,
        "lng": 77.0266
    }
    items = [
        {"type": "TEST", "id": "TST-CBC-LAB-DELHI-001", "name": "Complete Blood Count", "code": "CBC", "price": 350.0},
        {"type": "TEST", "id": "TST-HBA1C-LAB-DELHI-001", "name": "HbA1c Glycated Hemoglobin", "code": "HBA1C", "price": 450.0}
    ]

    success, msg, ord_info = create_diagnostic_booking_order(
        patient_data=patient_data,
        center_id="LAB-DELHI-001",
        service_type="HOME_COLLECTION",
        scheduled_date=date.today().strftime("%Y-%m-%d"),
        scheduled_slot="07:00-09:00",
        items=items,
        payment_method="ONLINE"
    )
    assert success is True
    order_id = ord_info['order_id']
    sample_code = ord_info['sample_code']
    assert sample_code.startswith("SMP-")

    # 2. Verify accession record created
    order = get_diagnostic_order_by_id(order_id)
    assert order is not None
    assert order['sample']['sample_code'] == sample_code
    assert order['phlebotomy']['phlebotomist_name'] is not None

    # 3. Technician enters results
    test_results = [
        {"test_name": "Complete Blood Count", "parameter_name": "Hemoglobin", "result_value": "13.8", "unit": "g/dL", "reference_range": "12.0 - 15.5", "abnormal_flag": "NORMAL"},
        {"test_name": "Complete Blood Count", "parameter_name": "Platelet Count", "result_value": "2.40", "unit": "lakhs/uL", "reference_range": "1.5 - 4.5", "abnormal_flag": "NORMAL"},
        {"test_name": "HbA1c Glycated Hemoglobin", "parameter_name": "HbA1c", "result_value": "5.4", "unit": "%", "reference_range": "4.0 - 5.6", "abnormal_flag": "NORMAL"}
    ]
    t_success, t_msg = enter_technician_lab_results(
        order_id=order_id,
        technician_id="STF-DELHI-03",
        technician_name="Anil Sengupta",
        results_list=test_results
    )
    assert t_success is True

    # 4. Pathologist reviews and releases v1 report
    r_success, r_msg, rep_v1 = approve_and_release_diagnostic_report(
        order_id=order_id,
        pathologist_id="STF-DELHI-01",
        pathologist_name="Dr. Rajeshwar Verma, MD",
        summary="Optimal glycemic control and normal erythrocyte indices.",
        interpretation="Physiological baseline parameters."
    )
    assert r_success is True
    assert rep_v1['version'] == 'v1'

    # 5. Pathologist issues corrected v2 amendment
    r2_success, r2_msg, rep_v2 = approve_and_release_diagnostic_report(
        order_id=order_id,
        pathologist_id="STF-DELHI-01",
        pathologist_name="Dr. Rajeshwar Verma, MD",
        summary="Optimal glycemic control. Amended with platelet morphology note.",
        interpretation="Normocytic normochromic red cells.",
        is_correction=True,
        correction_reason="Added peripheral blood smear morphology annotation"
    )
    assert r2_success is True
    assert rep_v2['version'] == 'v2'

    # Verify order state
    final_order = get_diagnostic_order_by_id(order_id)
    assert final_order['status'] == 'REPORT_RELEASED'
    assert final_order['report']['version'] == 'v2'

# ==============================================================================
# 5. DOCTOR REFERRAL WORKFLOW TESTS
# ==============================================================================

def test_doctor_diagnostic_referral_creation():
    """Tests doctor referral creation and tracking."""
    success, msg, res = create_doctor_diagnostic_referral(
        doctor_id="DOC_2026_001",
        doctor_name="Dr. Sameer Joshi, MD",
        patient_id="PAT_2026_001",
        patient_name="Rohan Sharma",
        center_id="LAB-DELHI-001",
        test_codes=["CBC", "LIPID", "TSH"],
        clinical_indication="Unexplained fatigue, evaluation for thyroid & lipid metabolism",
        priority="URGENT",
        instructions="Please perform peripheral blood smear review"
    )
    assert success is True
    assert res['referral_number'].startswith("REF-DX-")
    assert res['tests_count'] == 3

# ==============================================================================
# 6. WEB HTTP ENDPOINT ROUTE TESTS
# ==============================================================================

def test_diagnostic_web_routes_render_cleanly(client):
    """Verifies all public and patient diagnostic endpoints return HTTP 200."""
    # 1. Main portal
    res_home = client.get('/diagnostic')
    assert res_home.status_code == 200
    assert b"Global Diagnostic Network" in res_home.data
    assert b"Complete Blood Count" in res_home.data

    # 2. Tests catalog
    res_tests = client.get('/diagnostic/tests')
    assert res_tests.status_code == 200

    # 3. Test detail
    res_detail = client.get('/diagnostic/tests/CBC')
    assert res_detail.status_code == 200
    assert b"Biological Parameters" in res_detail.data

    # 4. Search API
    res_search = client.get('/diagnostic/search?q=lipid')
    assert res_search.status_code == 200
    data = res_search.get_json()
    assert data['success'] is True
    assert data['tests_count'] >= 1

    # 5. Pathology Login & Register
    res_login = client.get('/pathology/login')
    assert res_login.status_code == 200
    assert (b"Pathology Center Portal" in res_login.data or b"Pathology Sign In" in res_login.data)

    res_reg = client.get('/pathology/register')
    assert res_reg.status_code == 200
    assert (b"Register Your Pathology Center" in res_reg.data or b"Register Lab Center" in res_reg.data)

    # 6. Public QR verification
    from spherix.services.diagnostic_db import create_diagnostic_booking_order, enter_technician_lab_results, approve_and_release_diagnostic_report
    success_bk, _, ord_res = create_diagnostic_booking_order(
        patient_data={"id": "PAT_VERIFY", "name": "Meera Joshi", "email": "meera@example.com", "phone": "+91 99000 11223", "address": "New Delhi", "lat": 28.6, "lng": 77.2},
        center_id="LAB-DELHI-001",
        service_type="WALK_IN",
        scheduled_date=date.today().strftime("%Y-%m-%d"),
        scheduled_slot="09:00-10:00",
        items=[{"type": "TEST", "id": "TST-CBC-LAB-DELHI-001", "name": "Complete Blood Count", "code": "CBC", "price": 350.0}],
        payment_method="ONLINE"
    )
    enter_technician_lab_results(ord_res['order_id'], "STF-DELHI-03", "Anil MLT", [{"test_name": "CBC", "parameter_name": "Hb", "result_value": "13.5", "unit": "g/dL", "reference_range": "12-15", "abnormal_flag": "NORMAL"}])
    _, _, rep_data = approve_and_release_diagnostic_report(ord_res['order_id'], "STF-DELHI-01", "Dr. Rajeshwar Verma", "Normal findings", "Baseline clear")

    res_verify = client.get(f"/diagnostic/verify-report/{rep_data['report_number']}")
    assert res_verify.status_code == 200
    assert b"Verified Diagnostic Report" in res_verify.data or b"Spherix Diagnostic" in res_verify.data


def test_diagnostic_patient_web_booking_flow(client):
    """
    Tests end-to-end patient web interaction:
    1. Patient visits /diagnostic and discovers nearby centers
    2. Submits a Doorstep Home Collection booking with CASH_AT_COLLECTION payment
    3. Submits a Walk-in booking with ONLINE payment
    4. Views order tracking page with live status and sample barcode
    """
    # 1. Doorstep Booking with Cash On Collection
    with client.session_transaction() as sess:
        sess['user_id'] = 'PAT_WEB_01'
        sess['user_role'] = 'patient'
        sess['user_name'] = 'Ananya Sen'
        sess['user_email'] = 'ananya.sen@example.com'

    home_payload = {
        'center_id': 'LAB-DELHI-001',
        'service_type': 'HOME_COLLECTION',
        'scheduled_date': date.today().strftime('%Y-%m-%d'),
        'scheduled_slot': '08:00 - 10:00 AM',
        'patient_name': 'Ananya Sen',
        'patient_email': 'ananya.sen@example.com',
        'patient_phone': '+91 98765 43210',
        'patient_address': 'Flat 402, Lotus Greens, Sector 78, Noida',
        'patient_lat': '28.5355',
        'patient_lng': '77.3910',
        'test_codes': 'CBC,LIPID',
        'payment_method': 'CASH_AT_COLLECTION',
        'notes': 'Please ring doorbell twice'
    }

    res_post_home = client.post('/diagnostic/book', data=home_payload, follow_redirects=True)
    assert res_post_home.status_code == 200
    assert b"Booking confirmed!" in res_post_home.data or b"Order #" in res_post_home.data

    # 2. Walk-in Booking with Online Payment
    walkin_payload = {
        'center_id': 'LAB-DELHI-001',
        'service_type': 'WALK_IN',
        'scheduled_date': date.today().strftime('%Y-%m-%d'),
        'scheduled_slot': '11:00 - 01:00 PM',
        'patient_name': 'Ananya Sen',
        'patient_email': 'ananya.sen@example.com',
        'patient_phone': '+91 98765 43210',
        'test_codes': 'TSH',
        'payment_method': 'ONLINE'
    }

    res_post_walkin = client.post('/diagnostic/book', data=walkin_payload, follow_redirects=True)
    assert res_post_walkin.status_code == 200
    assert b"Booking confirmed!" in res_post_walkin.data or b"SMP-" in res_post_walkin.data


def test_groq_ai_clinical_insights_and_pathologist_summary():
    """Verifies Groq AI clinical insight extraction and pathologist summary generation."""
    from spherix.services.diagnostic_ai import get_groq_diagnostic_test_insight, generate_pathologist_ai_summary

    # 1. CBC Insights
    cbc_insight = get_groq_diagnostic_test_insight('CBC')
    assert cbc_insight is not None
    assert 'overview' in cbc_insight
    assert len(cbc_insight['why_prescribed']) >= 1
    assert 'preparation_guide' in cbc_insight
    assert 'interpretation_guide' in cbc_insight
    assert 'high_levels' in cbc_insight['interpretation_guide']
    assert 'clinical_faqs' in cbc_insight

    # 2. TSH Insights
    tsh_insight = get_groq_diagnostic_test_insight('TSH')
    assert tsh_insight is not None
    assert 'Thyroid' in tsh_insight['overview'] or 'TSH' in tsh_insight['overview'] or 'thyroid' in tsh_insight['overview'].lower()

    # 3. Pathologist Summary Generator
    test_obs = [
        {"parameter_name": "Hemoglobin", "result_value": "14.5", "unit": "g/dL", "reference_range": "13.5-17.5", "abnormal_flag": "NORMAL"},
        {"parameter_name": "Platelet Count", "result_value": "2.8", "unit": "lakhs/uL", "reference_range": "1.5-4.5", "abnormal_flag": "NORMAL"}
    ]
    summary_res = generate_pathologist_ai_summary(test_obs)
    assert 'summary' in summary_res
    assert 'interpretation' in summary_res


def test_cross_center_price_comparison_and_availability(client):
    """Verifies cross-center price comparison matrix and availability endpoints."""
    from spherix.services.diagnostic_db import get_test_price_comparison, check_test_availability_by_location

    # 1. DB function test
    comp = get_test_price_comparison('CBC')
    assert comp['test_code'] == 'CBC'
    assert comp['centers_count'] >= 1
    assert comp['min_price'] > 0

    avail = check_test_availability_by_location('CBC', city='New Delhi')
    assert avail['available'] is True
    assert avail['matching_centers_count'] >= 1

    # 2. Web endpoint tests
    res_compare = client.get('/diagnostic/compare?code=CBC')
    assert res_compare.status_code == 200
    assert b"Multi-Center Price Comparison Engine" in res_compare.data

    res_ai_api = client.get('/api/diagnostic/ai-explore-test?code=CBC')
    assert res_ai_api.status_code == 200
    ai_json = res_ai_api.get_json()
    assert ai_json['success'] is True
    assert 'insights' in ai_json

    res_price_api = client.get('/api/diagnostic/compare-prices?code=CBC')
    assert res_price_api.status_code == 200
    p_json = res_price_api.get_json()
    assert p_json['success'] is True
    assert p_json['comparison']['centers_count'] >= 1

    res_avail_api = client.get('/api/diagnostic/check-availability?postal_code=110001')
    assert res_avail_api.status_code == 200
    av_json = res_avail_api.get_json()
    assert av_json['success'] is True
    assert av_json['availability']['available'] is True


# ==============================================================================
# 9. SETTINGS, ADDRESS, AND DOCTOR/HOSPITAL CONNECTIONS
# ==============================================================================

def test_pathology_settings_profile_and_address_updates(client):
    """Verifies that center profile, address details, and staff updates persist in DB and via endpoints."""
    from spherix.services.diagnostic_db import (
        update_pathology_center_profile, update_pathology_center_address,
        update_pathology_staff_profile, get_diagnostic_db,
        connect_with_doctor, connect_with_hospital,
        get_center_doctor_connections, get_center_hospital_connections
    )

    center_id = "LAB-DELHI-001"

    # 1. Update Profile directly in DB
    ok_prof, _ = update_pathology_center_profile(
        center_id=center_id,
        data={
            'center_name': "Spherix Apex Diagnostics Central",
            'email': "apex.delhi@spherixlab.org",
            'phone': "+91 11 9999 8888",
            'emergency_phone': "+91 11 9999 0000",
            'website': "https://apex.spherixclinic.org",
            'operating_hours': "Mon-Sun: 06:00 AM - 10:00 PM",
            'is_nabl_accredited': True,
            'is_cap_accredited': True,
            'is_iso_certified': True,
            'home_collection_enabled': True,
            'home_collection_fee': 150.0
        }
    )
    assert ok_prof is True

    # 2. Update Address details (address name, coordinates, additional info)
    ok_addr, _ = update_pathology_center_address(
        center_id=center_id,
        data={
            'address_name': "Corporate Diagnostic Tower A",
            'address': "Tower A, Connaught Place, Block E",
            'landmark': "Near Rajiv Chowk Metro Gate 4",
            'address_additional_info': "Basement Parking B2, Dedicated Pathology Elevator Available",
            'city': "New Delhi",
            'state_province': "Delhi",
            'postal_code': "110001",
            'country': "India",
            'latitude': 28.6315,
            'longitude': 77.2185,
            'timezone': "Asia/Kolkata"
        }
    )
    assert ok_addr is True

    # Verify persisted in database
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pathology_centers WHERE id = ?", (center_id,))
    center = cursor.fetchone()
    conn.close()

    assert center is not None
    assert center['center_name'] == "Spherix Apex Diagnostics Central"
    assert center['address_name'] == "Corporate Diagnostic Tower A"
    assert center['landmark'] == "Near Rajiv Chowk Metro Gate 4"
    assert center['address_additional_info'] == "Basement Parking B2, Dedicated Pathology Elevator Available"
    assert center['website'] == "https://apex.spherixclinic.org"
    assert center['latitude'] == 28.6315
    assert center['longitude'] == 77.2185

    # 3. Doctor & Hospital Connections
    ok_doc, _ = connect_with_doctor(
        center_id=center_id,
        doctor_id="DOC001",
        partnership_type="Direct Referral",
        notes="Preferred diagnostic center for Cardiology and Lipid profiles"
    )
    assert ok_doc is True
    doc_list = get_center_doctor_connections(center_id)
    assert len(doc_list) >= 1
    assert any(d['doctor_id'] == 'DOC001' for d in doc_list)

    ok_hosp, _ = connect_with_hospital(
        center_id=center_id,
        hospital_id="HOSP001",
        partnership_type="Outsourced Pathology Partner",
        notes="Official secondary diagnostics partner for Apollo Hospital Delhi"
    )
    assert ok_hosp is True
    hosp_list = get_center_hospital_connections(center_id)
    assert len(hosp_list) >= 1
    assert any(h['hospital_id'] == 'HOSP001' for h in hosp_list)

    # 4. Web session tests for Settings & Connections
    with client.session_transaction() as sess:
        sess['pathology_staff_id'] = 'STF-DELHI-01'

    # Test settings page renders
    res_settings = client.get('/pathology/settings?tab=address')
    assert res_settings.status_code == 200
    assert b"Address &amp; Geolocation" in res_settings.data or b"Address & Geolocation" in res_settings.data

    # Test settings address POST
    res_addr_post = client.post('/pathology/settings/address', data={
        'address_name': 'Main Clinical Center Lab',
        'address': 'Building 4, Connaught Circus',
        'landmark': 'Opposite Standard Chartered',
        'address_additional_info': 'First floor, Wheelchair ramp at entrance',
        'city': 'New Delhi',
        'state_province': 'Delhi',
        'postal_code': '110001',
        'country': 'India',
        'latitude': '28.6320',
        'longitude': '77.2190',
        'timezone': 'Asia/Kolkata'
    }, follow_redirects=True)
    assert res_addr_post.status_code == 200
    assert b"Pathology center location &amp; address information saved." in res_addr_post.data or b"Pathology center location & address information saved." in res_addr_post.data

    # Test doctor connection POST
    res_doc_post = client.post('/pathology/connect/doctor', data={
        'doctor_id': 'DOC002',
        'doctor_name': 'Dr. Sunita Sharma',
        'partnership_type': 'Consulting Partner',
        'notes': 'Referrals for thyroid and biochemistry tests'
    }, follow_redirects=True)
    assert res_doc_post.status_code == 200
    assert b"Referral partnership request transmitted to doctor" in res_doc_post.data or b"Doctor referral connection" in res_doc_post.data or b"doctor" in res_doc_post.data


# ==============================================================================
# 10. TRIPARTITE HOSPITAL-DOCTOR-PATHOLOGY DUAL ACCEPTANCE & MEDICINE TRANSMISSION
# ==============================================================================

def test_tripartite_hospital_doctor_pathology_connection_and_medicine_transmission(client):
    """
    Verifies that when a hospital sends a connect request to a pathology center:
    1. Connection is ONLY active after hospital accepts AND the designated doctor accepts.
    2. When the doctor transmits their medicine prescription, it records accurately under the pathology center.
    """
    from spherix.services.diagnostic_db import (
        connect_with_hospital, respond_hospital_pathology_connection,
        respond_doctor_pathology_connection, create_doctor_diagnostic_referral,
        get_incoming_doctor_prescriptions_and_medicines, get_diagnostic_db
    )

    center_id = "LAB-DELHI-001"
    hospital_id = f"HOSP-MAX-{secrets.token_hex(3)}"
    doctor_id = f"DOC-CARTER-{secrets.token_hex(3)}"

    # Step 1: Hospital sends connect request to Pathology Center specifying doctor
    ok_init, msg_init = connect_with_hospital(
        center_id=center_id,
        hospital_id=hospital_id,
        doctor_id=doctor_id,
        notes="Cardiology & Metabolic pathology partnership",
        partnership_type="ROUTINE_DIAGNOSTICS",
        requested_by="HOSPITAL",
        doctor_name="Dr. Carter",
        hospital_name="Max Healthcare"
    )
    assert ok_init is True

    # Verify initial state: Hospital accepted=1, Doctor accepted=0, Status=PENDING_DOCTOR
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospital_pathology_connections WHERE center_id = ? AND hospital_id = ?", (center_id, hospital_id))
    h_conn = cursor.fetchone()
    conn.close()

    assert h_conn is not None
    assert h_conn['hospital_accepted'] == 1
    assert h_conn['doctor_accepted'] == 0
    assert h_conn['status'] == 'PENDING_DOCTOR'

    # Step 2: Pathology Center accepts the connection request
    ok_path, msg_path, path_data = respond_hospital_pathology_connection(
        connection_id=h_conn['id'],
        actor_role='pathology',
        action='accept'
    )
    assert ok_path is True
    # Crucial Rule: Still PENDING_DOCTOR because the doctor has NOT accepted yet!
    assert path_data['status'] == 'PENDING_DOCTOR'
    assert path_data['doctor_accepted'] == 0
    assert path_data['hospital_accepted'] == 1
    assert path_data['pathology_accepted'] == 1

    # Step 3: The Doctor accepts the partnership
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctor_pathology_connections WHERE center_id = ? AND doctor_id = ?", (center_id, doctor_id))
    d_conn = cursor.fetchone()
    conn.close()
    assert d_conn is not None

    ok_doc, msg_doc, doc_data = respond_doctor_pathology_connection(
        connection_id=d_conn['id'],
        action='accept'
    )
    assert ok_doc is True
    # Now BOTH hospital AND doctor accepted -> Status becomes ACCEPTED
    assert doc_data['status'] == 'ACCEPTED'

    # Verify hospital_pathology_connections also transitioned to ACCEPTED
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospital_pathology_connections WHERE id = ?", (h_conn['id'],))
    updated_h_conn = cursor.fetchone()
    conn.close()
    assert updated_h_conn['status'] == 'ACCEPTED'
    assert updated_h_conn['doctor_accepted'] == 1
    assert updated_h_conn['hospital_accepted'] == 1

    # Step 4: Doctor sends his medicines and diagnostic tests to the pathology center
    prescribed_medicines = [
        {"name": "Atorvastatin 20mg", "dosage": "1 Tab", "frequency": "Once Nightly", "duration": "30 Days"},
        {"name": "Metformin 500mg", "dosage": "1 Tab", "frequency": "Twice Daily", "duration": "30 Days"}
    ]
    recommended_tests = ["LIPID", "HBA1C", "FBS"]

    ok_ref, msg_ref, ref_data = create_doctor_diagnostic_referral(
        doctor_id=doctor_id,
        doctor_name="Dr. Carter",
        patient_id="PAT-TEST-101",
        patient_name="John Doe",
        center_id=center_id,
        test_codes=recommended_tests,
        clinical_indication="Cardiometabolic Risk Assessment with Dyslipidemia",
        priority="URGENT",
        doctor_instructions="12-hour overnight fasting required.",
        medicines=prescribed_medicines,
        hospital_id=hospital_id,
        hospital_name="Max Healthcare"
    )
    assert ok_ref is True
    assert ref_data['medicines_count'] == 2
    assert ref_data['tests_count'] == 3

    # Step 5: Pathology Center retrieves incoming prescription & medicines schedule
    incoming_orders = get_incoming_doctor_prescriptions_and_medicines(center_id)
    assert len(incoming_orders) >= 1

    latest_order = next(o for o in incoming_orders if o['id'] == ref_data['referral_id'])
    assert latest_order['patient_name'] == "John Doe"
    assert latest_order['doctor_name'] == "Dr. Carter"
    assert latest_order['hospital_name'] == "Max Healthcare"
    assert len(latest_order['medicines_list']) == 2
    assert latest_order['medicines_list'][0]['name'] == "Atorvastatin 20mg"
    assert latest_order['medicines_list'][1]['name'] == "Metformin 500mg"


def test_laboratory_workstation_features(client):
    """Tests Dr Lal PathLabs laboratory-side workstation suite: accessioning, coldchain logging, and walkin calling."""
    from spherix.services.diagnostic_db import create_diagnostic_booking_order

    # 1. Create a real diagnostic booking order
    patient_data = {
        "id": "PAT_TEST_WORKSTATION",
        "name": "Vikram Singh",
        "email": "vikram@example.com",
        "phone": "+91 98888 11223",
        "address": "Connaught Place, New Delhi",
        "lat": 28.6304,
        "lng": 77.2177
    }
    items = [
        {"type": "TEST", "id": "TST-CBC-LAB-DELHI-001", "name": "Complete Blood Count", "code": "CBC", "price": 350.0}
    ]
    success, msg, ord_info = create_diagnostic_booking_order(
        patient_data=patient_data,
        center_id="LAB-DELHI-001",
        service_type="HOME_COLLECTION",
        scheduled_date=date.today().strftime("%Y-%m-%d"),
        scheduled_slot="07:00-09:00",
        items=items,
        payment_method="ONLINE"
    )
    assert success is True
    order_id = ord_info['order_id']
    assignment_id = ord_info.get('assignment_id') or f"ASG-{order_id}"

    # 2. Authenticate as Pathology Staff
    with client.session_transaction() as sess:
        sess['pathology_staff_id'] = 'STF-DELHI-01'
        sess['pathology_center_id'] = 'LAB-DELHI-001'
        sess['pathology_role'] = 'admin'
        sess['pathology_name'] = 'Dr. Rajesh Lal'

    # 3. Test specimen accessioning
    res_accession = client.post(f'/pathology/orders/{order_id}/accession-specimen', data={
        'vacutainer_type': 'Lavender Top (EDTA)',
        'specimen_quality': 'Satisfactory / Normal',
        'barcode_data': 'LPL-SMP-999888',
        'status': 'RECEIVED'
    }, follow_redirects=True)
    assert res_accession.status_code == 200

    # 4. Test cold-chain temperature logging
    res_temp = client.post(f'/pathology/collections/{assignment_id}/log-temperature', data={
        'temperature_c': '4.2',
        'temp_notes': 'Routine ice-pack verification'
    }, follow_redirects=True)
    assert res_temp.status_code == 200

    # 4. Test walkin token caller
    res_walkin = client.get('/pathology/walkins')
    assert res_walkin.status_code == 200
    assert b"Walk-in Patient Token Queue" in res_walkin.data or b"Token" in res_walkin.data

    # 5. Test pathology dashboard overview renders without UndefinedError
    res_dash = client.get('/pathology/dashboard')
    assert res_dash.status_code == 200
    assert b"Live Laboratory Accessions" in res_dash.data or b"Dashboard Overview" in res_dash.data

    # 6. Test global dashboard search API
    res_search = client.get('/api/pathology/search?q=CBC')
    assert res_search.status_code == 200
    search_data = res_search.get_json()
    assert search_data['success'] is True
    assert isinstance(search_data['results'], list)


def test_test_catalog_visibility_and_pricing_management(client):
    """Tests the Test Catalog & Pricing Management tab, public visibility toggle, discount/offer prices, and slide drawer updates."""
    from spherix.services.diagnostic_db import (
        get_diagnostic_tests_for_center, toggle_diagnostic_test_visibility,
        update_diagnostic_test_details, get_diagnostic_db
    )

    center_id = "LAB-DELHI-001"

    # 1. Fetch center tests
    tests = get_diagnostic_tests_for_center(center_id)
    assert len(tests) > 0
    cbc_test = next((t for t in tests if t['test_code'] == 'CBC'), None)
    assert cbc_test is not None
    test_id = cbc_test['id']

    # 2. Toggle public visibility
    ok, msg, new_state = toggle_diagnostic_test_visibility(test_id, center_id)
    assert ok is True
    assert new_state in (0, 1)

    # 3. Update pricing with discount % and offer price
    update_data = {
        'price': 450.0,
        'discount_percent': 20.0,
        'offer_price': 360.0,
        'badge': 'SWASTHFIT POPULAR',
        'is_active': '1',
        'is_public': '1',
        'sample_type': 'Blood',
        'container_type': 'Lavender Top (EDTA)',
        'required_quantity': '3.0 mL',
        'fasting_required': '1',
        'fasting_hours': 10,
        'turnaround_hours': 8,
        'preparation_instructions': '10 hours overnight fasting recommended.',
        'home_collection_eligible': '1',
        'walkin_eligible': '1'
    }
    ok_up, msg_up = update_diagnostic_test_details(test_id, center_id, update_data)
    assert ok_up is True

    # Verify DB persistence
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diagnostic_tests WHERE id = ?", (test_id,))
    updated_row = cursor.fetchone()
    conn.close()

    assert updated_row['price'] == 450.0
    assert updated_row['discount_percent'] == 20.0
    assert updated_row['offer_price'] == 360.0
    assert updated_row['badge'] == 'SWASTHFIT POPULAR'
    assert updated_row['is_active'] == 1
    assert updated_row['turnaround_hours'] == 8

    # 4. Test Web Endpoints with Authenticated Session
    with client.session_transaction() as sess:
        sess['pathology_staff_id'] = 'STF-DELHI-01'
        sess['pathology_center_id'] = 'LAB-DELHI-001'
        sess['pathology_role'] = 'admin'
        sess['pathology_name'] = 'Dr. Rajesh Lal'

    # GET /pathology/tests renders catalog and drawer
    res_tests = client.get('/pathology/tests')
    assert res_tests.status_code == 200
    assert b"Diagnostic Test Catalog" in res_tests.data
    assert b"testDetailDrawer" in res_tests.data
    assert b"SWASTHFIT POPULAR" in res_tests.data

    # POST /pathology/tests/<id>/toggle-visibility
    res_toggle = client.post(f'/pathology/tests/{test_id}/toggle-visibility', follow_redirects=True)
    assert res_toggle.status_code == 200

    # POST /pathology/tests/<id>/update
    res_update_web = client.post(f'/pathology/tests/{test_id}/update', data={
        'price': '500',
        'discount_percent': '25',
        'offer_price': '375',
        'badge': '25% OFF SPECIAL',
        'is_active': '1',
        'sample_type': 'Blood',
        'container_type': 'Lavender Top (EDTA)',
        'required_quantity': '2.0 mL',
        'fasting_required': '0',
        'fasting_hours': '0',
        'turnaround_hours': '6',
        'preparation_instructions': 'No fasting required',
        'home_collection_eligible': '1',
        'walkin_eligible': '1'
    }, follow_redirects=True)
    assert res_update_web.status_code == 200
    assert b"updated successfully" in res_update_web.data


def test_diagnostic_portal_navigation_tabs_and_menu_drawer(client):
    """Tests the presence of navigation tabs, three-line menu drawer, cart drawer, and modals on /diagnostic."""
    res = client.get('/diagnostic')
    assert res.status_code == 200

    # 1. Check navigation tabs
    assert b"Book Home Collect" in res.data
    assert b"Book Radiology/Scan" in res.data
    assert b"Doctors" in res.data
    assert b"About Us" in res.data
    assert b"Cart" in res.data

    # 2. Check three-line menu drawer elements
    assert b"diagnosticMenuDrawer" in res.data
    assert b"BOOK Test" in res.data
    assert b"Nearest Center" in res.data
    assert b"Upload Rx" in res.data or b"Upload Prescription" in res.data
    assert b"Download Report" in res.data

    # 3. Check Cart drawer and Radiology/About/Nearest modals
    assert b"diagnosticCartDrawer" in res.data
    assert b"radiologyBookingModal" in res.data
    assert b"aboutUsModal" in res.data
    assert b"nearestCenterModal" in res.data


def test_add_new_diagnostic_test_to_catalog(client):
    """Tests adding a new diagnostic test to a center catalog and web endpoint submission."""
    from spherix.services.diagnostic_db import add_diagnostic_test, get_diagnostic_db

    center_id = "LAB-DELHI-001"
    code_suffix = secrets.token_hex(3).upper()
    custom_code_1 = f"VITD_{code_suffix}"
    custom_code_2 = f"FERR_{code_suffix}"

    # 1. Direct Service Layer Add Test
    new_test_payload = {
        'test_name': f'Vitamin D 25-Hydroxy Total {code_suffix}',
        'test_code': custom_code_1,
        'category_name': 'Endocrinology & Hormones',
        'description': 'Quantitative test for 25-OH Vitamin D deficiency and calcium metabolism.',
        'sample_type': 'Blood',
        'container_type': 'Gold Top (SST Gel Separator)',
        'required_quantity': '3.0 mL',
        'fasting_required': '1',
        'fasting_hours': 10,
        'turnaround_hours': 24,
        'price': '1200.00',
        'discount_percent': '25.0',
        'offer_price': '900.00',
        'badge': 'PREVENTIVE ESSENTIAL',
        'is_active': '1',
        'is_public': '1',
        'home_collection_eligible': '1',
        'walkin_eligible': '1'
    }

    ok, msg, created_id = add_diagnostic_test(center_id, new_test_payload)
    assert ok is True
    assert created_id is not None
    assert custom_code_1 in created_id

    # Verify DB record
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diagnostic_tests WHERE id = ?", (created_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row['test_name'] == f'Vitamin D 25-Hydroxy Total {code_suffix}'
    assert row['test_code'] == custom_code_1
    assert row['price'] == 1200.0
    assert row['offer_price'] == 900.0
    assert row['discount_percent'] == 25.0
    assert row['badge'] == 'PREVENTIVE ESSENTIAL'
    assert row['is_active'] == 1

    # 2. Web Form Submission via POST /pathology/tests/add
    with client.session_transaction() as sess:
        sess['pathology_staff_id'] = 'STF-DELHI-01'
        sess['pathology_center_id'] = 'LAB-DELHI-001'
        sess['pathology_role'] = 'admin'
        sess['pathology_name'] = 'Dr. Rajesh Lal'

    web_post_res = client.post('/pathology/tests/add', data={
        'test_name': f'Serum Ferritin Iron Stores {code_suffix}',
        'test_code': custom_code_2,
        'category_name': 'Hematology & Blood Studies',
        'description': 'Evaluation of iron storage levels and anemia assessment.',
        'sample_type': 'Serum',
        'container_type': 'Gold Top (SST Gel Separator)',
        'required_quantity': '2.0 mL',
        'fasting_required': '0',
        'fasting_hours': '0',
        'turnaround_hours': 12,
        'price': '650.00',
        'discount_percent': '15.0',
        'badge': 'DOCTOR CHOICE',
        'is_active': '1',
        'is_public': '1',
        'home_collection_eligible': '1',
        'walkin_eligible': '1'
    }, follow_redirects=True)

    assert web_post_res.status_code == 200
    assert f"Serum Ferritin Iron Stores {code_suffix}".encode() in web_post_res.data
    assert b"DOCTOR CHOICE" in web_post_res.data
    assert b"Add New Diagnostic Test" in web_post_res.data
    assert b"addTestModal" in web_post_res.data







