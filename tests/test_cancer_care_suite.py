import html as html_lib
import pytest
from spherix import create_app
from spherix.cancer_data import CANCER_DATA
from spherix.services.database import TEMP_DATA

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_patient(client):
    from spherix.models.user import Patient
    pat = Patient(
        id='PAT-ONCO-TEST',
        name='Test Oncology Patient',
        email='testoncopat@spherix.com',
        phone='1234567890',
        password='password123'
    )
    pat.is_verified = True
    TEMP_DATA['patients']['PAT-ONCO-TEST'] = pat
    with client.session_transaction() as sess:
        sess['_user_id'] = 'PAT-ONCO-TEST'
        sess['user_role'] = 'patient'
    return pat

def test_all_18_cancer_pages_return_200(client, auth_patient):
    """Verifies that all 18 dedicated pages in the multi-page Cancer Care Centre render HTTP 200 for authenticated patient."""
    endpoints = [
        ('/cancer-care', 'Precision Oncology'),
        ('/cancer-care/awareness', 'Cancer Awareness'),
        ('/cancer-care/symptom-checker', 'Cancer Symptom Checker'),
        ('/cancer-care/types', 'Cancer Types'),
        ('/cancer-care/types/breast-cancer', 'Breast Cancer'),
        ('/cancer-care/types/lung-cancer', 'Lung Cancer'),
        ('/cancer-care/types/cervical-cancer', 'Cervical Cancer'),
        ('/cancer-care/prevention-screening', 'Cancer Prevention & Screening'),
        ('/cancer-care/diagnosis-testing', 'Advanced Diagnostic Testing & TNM Staging'),
        ('/cancer-care/treatment', 'Cancer Treatment Modalities & Pathways'),
        ('/cancer-care/specialists', 'Cancer Specialists & Oncologists'),
        ('/cancer-care/hospitals', 'Oncology Hospital Directory'),
        ('/cancer-care/book-appointment', 'Schedule an Oncology Consultation'),
        ('/cancer-care/ai-companion', 'AI Cancer Care Companion'),
        ('/cancer-care/reports', 'Medical Report Management Vault'),
        ('/cancer-care/journey', 'My Cancer Care Journey'),
        ('/cancer-care/recovery-rehab', 'Cancer Recovery & Physical Rehabilitation'),
        ('/cancer-care/nutrition-wellness', 'Oncology Nutrition & Integrative Wellness'),
        ('/cancer-care/support', 'Patient & Family Support Services'),
        ('/cancer-care/palliative-care', 'Palliative & Supportive Oncology Care'),
        ('/cancer-care/faqs', 'Frequently Asked Oncology Questions')
    ]

    for path, expected_text in endpoints:
        res = client.get(path)
        assert res.status_code == 200, f"Route {path} failed with status {res.status_code}"
        html_text = res.data.decode('utf-8')
        assert expected_text in html_text or html_lib.escape(expected_text) in html_text, f"Expected '{expected_text}' in response for {path}"

def test_backward_compatibility_endpoints(app):
    """Verifies that url_for('cancer_care') and url_for('cancer_care.index') resolve correctly."""
    with app.test_request_context():
        from flask import url_for
        assert url_for('cancer_care') == '/cancer-care'
        assert url_for('cancer_care.index') == '/cancer-care'
        assert url_for('cancer_care.types') == '/cancer-care/types'
        assert url_for('cancer_care.type_detail', slug='breast-cancer') == '/cancer-care/types/breast-cancer'

def test_symptom_checker_non_diagnostic_disclaimer(client):
    """Ensures the upgraded symptom checker has medical disclaimers and does not produce unsupported scores."""
    res = client.get('/cancer-care/symptom-checker')
    assert res.status_code == 200
    html_text = res.data.decode('utf-8')
    assert "THIS IS NOT A CANCER DIAGNOSIS" in html_text
    assert "Breast & Axilla" in html_text or "Breast &amp; Axilla" in html_text
    assert "Chest & Lungs" in html_text or "Chest &amp; Lungs" in html_text

def test_all_14_cancer_monographs_load(client):
    """Verifies that all 14 monographs in CANCER_DATA render properly."""
    assert len(CANCER_DATA) >= 14
    for slug in CANCER_DATA.keys():
        res = client.get(f'/cancer-care/types/{slug}')
        assert res.status_code == 200, f"Monograph for {slug} returned {res.status_code}"
        html_text = res.data.decode('utf-8')
        name = CANCER_DATA[slug]['name']
        assert (name in html_text or html_lib.escape(name) in html_text)
        assert "Standard Molecular Biomarkers" in html_text

def test_appointment_booking_post_flow(client, auth_patient):
    """Verifies that booking an oncology consultation saves into appointments data store."""
    payload = {
        'patient_name': 'Test Oncology Patient',
        'patient_phone': '+91 9876543210',
        'patient_age': '54',
        'patient_gender': 'female',
        'doctor_id': 'DOC-ONCO-101',
        'consultation_type': 'In-Person Hospital Visit',
        'appointment_date': '2026-12-01',
        'appointment_time': '10:00 AM',
        'clinical_notes': 'Mammographic density BI-RADS 4 follow-up consultation.'
    }
    res = client.post('/cancer-care/book-appointment', data=payload, follow_redirects=True)
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert "Oncology consultation booked successfully" in html

def test_oncology_navigation_and_auth_flows(client, auth_patient):
    """
    Verifies the 4 user-specified oncology routing behaviors:
    1. Unauthenticated click on Book Appointment -> redirects to Patient Login with next pointing to Oncology department in specialists.
       Authenticated patient click on Book Appointment -> redirects directly to Oncology department in specialists (/doctors?dept=Oncology).
    2. Click on Cancer Specialist -> routes to /doctors?dept=Oncology and displays verified oncology specialists.
    3. Click on Oncology Hospital -> routes to /hospitals?specialty=Oncology and displays verified oncology hospitals.
    4. Accessing or submitting book oncology consultation page requires patient login -> redirects unauthenticated users to /patient-login.
    """
    unauth_client = client.application.test_client()

    # 1. Unauthenticated Book Appointment
    res1_unauth = unauth_client.get('/cancer-care/appointment')
    assert res1_unauth.status_code == 302
    assert '/patient-login' in res1_unauth.headers.get('Location')
    assert 'dept' in res1_unauth.headers.get('Location') and 'Oncology' in res1_unauth.headers.get('Location')

    # 1. Authenticated Book Appointment (logged in patient)
    res1_auth = client.get('/cancer-care/appointment')
    assert res1_auth.status_code == 302
    assert res1_auth.headers.get('Location') == '/doctors?dept=Oncology'

    # 2. Cancer Specialist -> /doctors?dept=Oncology
    res2 = client.get('/doctors?dept=Oncology')
    assert res2.status_code == 200
    html2 = res2.data.decode('utf-8')
    assert 'Oncology' in html2
    assert 'Jenkins' in html2 or 'Ramesh' in html2 or 'Oncologist' in html2

    # 3. Oncology Hospital -> /hospitals?specialty=Oncology
    res3 = client.get('/hospitals?specialty=Oncology')
    assert res3.status_code == 200
    html3 = res3.data.decode('utf-8')
    assert 'Oncology' in html3 or 'Cancer' in html3
    assert 'Comprehensive Cancer' in html3 or 'Cancer Institute' in html3

    # 4. Final Book Oncology consultation page requires login
    res4_unauth = unauth_client.get('/cancer-care/book-appointment')
    assert res4_unauth.status_code == 302
    assert '/patient-login' in res4_unauth.headers.get('Location')
    assert 'next=%2Fcancer-care%2Fbook-appointment' in res4_unauth.headers.get('Location') or 'book-appointment' in res4_unauth.headers.get('Location')

    # 5. Click on Symptoms Checker -> routes to /symptoms and renders Step 1 (symptoms_step1.html)
    res5 = client.get('/symptoms')
    assert res5.status_code == 200
    html5 = res5.data.decode('utf-8')
    assert "Step 1: Patient Profile" in html5 or "AI Symptoms Analyzer" in html5

    # Check that cancer care navigation points to /symptoms
    res_home = client.get('/cancer-care')
    assert res_home.status_code == 200
    assert '/symptoms' in res_home.data.decode('utf-8')

def test_cancer_apis(client):
    """Verifies all JSON cancer care APIs."""
    # Clinical trials
    trials_res = client.get('/api/cancer/clinical-trials')
    assert trials_res.status_code == 200
    trials_data = trials_res.get_json()
    assert trials_data['success'] is True
    assert len(trials_data['trials']) >= 4

    # AI consult
    ai_res = client.post('/api/cancer/ai-consult', json={'query': 'What is Gleason Score?'})
    assert ai_res.status_code == 200
    ai_data = ai_res.get_json()
    assert ai_data['success'] is True
    assert 'Gleason' in ai_data['answer']
    # Ensure no raw asterisks
    assert '**' not in ai_data['answer']

def test_cancer_care_branding_and_fullscreen(client):
    """Verifies that the logo and full-screen responsive classes are properly rendered."""
    res = client.get('/cancer-care')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'spherix_cancer_logo.png' in html, "Cancer logo spherix_cancer_logo.png missing from /cancer-care"
    assert 'brand-font-spherix' in html, "brand-font-spherix font class missing"
    assert 'brand-font-oncology' in html, "brand-font-oncology font class missing"
    assert 'max-w-[1920px]' in html, "max-w-[1920px] full-screen class missing"
    assert 'Spherix' in html
    assert 'Oncology' in html

def test_home_page_with_seeded_oncology_faculty(client):
    """Regression test ensuring home page (/) sorts doctors safely even when experience contains text."""
    from spherix.routes.cancer_care import seed_oncology_data_if_needed
    seed_oncology_data_if_needed()
    res = client.get('/')
    assert res.status_code == 200
    assert b"Spherix" in res.data

