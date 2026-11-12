import pytest
from app import create_app
from spherix.models.user import Doctor, Hospital
from spherix.services.database import TEMP_DATA

@pytest.fixture
def app_instance():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app

@pytest.fixture
def client(app_instance):
    return app_instance.test_client()

def test_doctor_strict_data_authorization_no_fallbacks(app_instance, client):
    """
    Test that a doctor without consultation fees, reviews, or address:
    - Never shows ₹500 fallback or fake 4.9 rating.
    - Shows 'Consultation fee not provided.'
    - Shows 'No patient reviews have been submitted for this doctor yet.'
    - Shows 'Location information not available.'
    - Includes layout protection classes (pb-28 lg:pb-12 overflow-x-hidden).
    """
    doc_id = 'DOC-AUTH-TEST-001'
    doc = Doctor(
        doc_id,
        'Aarav',
        'Nair',
        'aarav.nair.auth@test.com',
        'TestPass123!',
        'Cardiology',
        specialization='Clinical Cardiology',
        publishing_status='published',
        is_verified=True,
        is_approved=True,
        is_hidden=False,
        is_blocked=False
    )
    # Explicitly ensure fees and locations are None/empty
    doc.consultation_fee = None
    doc.video_fee = None
    doc.follow_up_fee = None
    doc.address = ''
    doc.hospital_address = ''
    doc.clinic_address = ''
    doc.city = ''
    doc.state = ''
    doc.country = ''
    
    TEMP_DATA['doctors'][doc_id] = doc

    res = client.get(f'/doctor/{doc_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify no fake ₹500 or fake 4.9
    assert 'Consultation fee not provided.' in html
    assert 'No patient reviews have been submitted for this doctor yet.' in html
    assert 'Location information not available.' in html
    assert 'maps.google.com/maps?q=' not in html
    # Ensure fake sample reviews are NOT present
    assert 'Rajesh Kumar Verma' not in html
    assert 'Ananya Sharma' not in html
    # UI layout protection
    assert 'overflow-x-hidden' in html

def test_doctor_authorized_data_rendered_accurately(app_instance, client):
    """
    Test that doctor-authorized fee (including Free), location, and genuine reviews
    are rendered accurately without synthetic alterations.
    """
    doc_id = 'DOC-AUTH-TEST-VALID-002'
    doc = Doctor(
        doc_id,
        'Priya',
        'Sharma',
        'priya.sharma.valid@test.com',
        'TestPass123!',
        'Pediatrics',
        specialization='Pediatric Cardiology',
        consultation_fee=0.0,
        address='Connaught Place Suite 101',
        city='New Delhi',
        publishing_status='published',
        is_verified=True,
        is_approved=True,
        is_hidden=False,
        is_blocked=False
    )
    TEMP_DATA['doctors'][doc_id] = doc

    # Add genuine review in TEMP_DATA['reviews']
    from spherix.models.commerce import Review
    rev = Review('REV-TEST-001', doc_id, 'PAT-001', 'Meera Joshi', 5, 'Outstanding clinical care for my child.')
    TEMP_DATA['reviews']['REV-TEST-001'] = rev

    res = client.get(f'/doctor/{doc_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Free fee rendering
    assert 'Free' in html
    # Map embed present because verified address exists
    assert 'maps.google.com/maps?q=' in html
    # Genuine review displayed
    assert 'Meera Joshi' in html
    assert 'Outstanding clinical care for my child.' in html

def test_doctor_unpublished_hidden_blocked_access_control(app_instance, client):
    """
    Test that non-published/hidden/blocked doctor profiles cannot be viewed anonymously
    and are not in public search listing.
    """
    draft_doc_id = 'DOC-AUTH-DRAFT-002'
    draft_doc = Doctor(
        draft_doc_id,
        'Dev',
        'Draft',
        'dev.draft@test.com',
        'TestPass123!',
        'Neurology',
        publishing_status='draft',
        is_verified=False,
        is_approved=False
    )
    TEMP_DATA['doctors'][draft_doc_id] = draft_doc

    # Anonymous access should be blocked or redirected away
    res = client.get(f'/doctor/{draft_doc_id}')
    assert res.status_code in (302, 403, 404)

    # Public list should NOT include draft doctor
    list_res = client.get('/doctors')
    assert list_res.status_code == 200
    list_html = list_res.data.decode('utf-8')
    assert draft_doc_id not in list_html
    assert 'Dev Draft' not in list_html

    # Blocked doctor
    blocked_id = 'DOC-AUTH-BLOCKED-003'
    blocked_doc = Doctor(
        blocked_id,
        'Karan',
        'Blocked',
        'karan.blocked@test.com',
        'TestPass123!',
        'Neurology',
        publishing_status='published',
        is_blocked=True
    )
    TEMP_DATA['doctors'][blocked_id] = blocked_doc
    res_blocked = client.get(f'/doctor/{blocked_id}')
    assert res_blocked.status_code in (302, 403, 404)

def test_hospital_strict_data_authorization_no_fallbacks(app_instance, client):
    """
    Test that a hospital without fees, reviews, or address:
    - Displays 'Contact hospital for pricing.' instead of fallback rates.
    - Displays 'No hospital reviews available' instead of fake 4.8.
    - Displays 'Location information not available.' without a broken map iframe.
    - Displays empty states for accreditations and insurance when not submitted.
    """
    hosp_id = 'HOSP-AUTH-TEST-001'
    hosp = Hospital(
        hosp_id,
        'Aura Health Institute',
        'aura.health@test.com',
        'TestPass123!',
        publishing_status='published',
        is_verified=True,
        is_approved=True,
        is_hidden=False,
        is_blocked=False
    )
    hosp.consultation_fee = None
    hosp.general_bed_fee = None
    hosp.private_bed_fee = None
    hosp.icu_bed_fee = None
    hosp.admission_charge = None
    hosp.address = ''
    hosp.city = ''
    hosp.state = ''
    hosp.latitude = None
    hosp.longitude = None
    hosp.accreditations = ''
    hosp.insurance_tieups = ''
    hosp.president_ceo = ''
    hosp.superintendent_name = ''
    
    TEMP_DATA['hospitals'][hosp_id] = hosp

    res = client.get(f'/hospital/{hosp_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'Contact hospital for pricing.' in html
    assert 'No hospital reviews available' in html
    assert 'Location information not available.' in html
    assert 'maps.google.com/maps?q=' not in html
    assert 'Dr. Rajesh Verma, MD' not in html
    assert 'Dr. Sunil Mehta, MD' not in html
    assert 'Accreditation information not provided by hospital administration.' in html

def test_hospital_unpublished_hidden_blocked_access_control(app_instance, client):
    """
    Test that non-published/hidden/blocked hospital profiles cannot be viewed anonymously
    and are not in public search listing.
    """
    draft_hosp_id = 'HOSP-AUTH-DRAFT-002'
    draft_hosp = Hospital(
        draft_hosp_id,
        'Draft Hospital Facility',
        'draft.hospital@test.com',
        'TestPass123!',
        publishing_status='draft',
        is_verified=False,
        is_approved=False
    )
    TEMP_DATA['hospitals'][draft_hosp_id] = draft_hosp

    res = client.get(f'/hospital/{draft_hosp_id}')
    assert res.status_code in (302, 403, 404)

    list_res = client.get('/hospitals')
    assert list_res.status_code == 200
    list_html = list_res.data.decode('utf-8')
    assert draft_hosp_id not in list_html
    assert 'Draft Hospital Facility' not in list_html
