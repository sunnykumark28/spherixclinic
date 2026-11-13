import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from spherix.services.database import TEMP_DATA
from spherix.models.user import Patient, Hospital, is_original_hospital_account


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
def auth_admin(client):
    admin = Patient(
        id='ADMIN-HOSP-TEST',
        name='Super Admin',
        email='admin@spherixclinic.com',
        password='HashedPassword123!'
    )
    admin.is_verified = True
    admin.mfa_enabled = True
    TEMP_DATA.setdefault('patients', {})['ADMIN-HOSP-TEST'] = admin
    with client.session_transaction() as sess:
        sess['_user_id'] = 'ADMIN-HOSP-TEST'
        sess['is_admin'] = True
        sess['user_role'] = 'admin'
    return admin


def test_is_original_hospital_account_validation():
    """
    Validates that is_original_hospital_account accepts genuine registered hospital accounts
    and rejects synthetic / seeded dummy fixtures.
    """
    real_hosp = Hospital(
        id='HPT/2026/001',
        name='Max Super Specialty Hospital',
        email='admin@maxhealthcare.com',
        password=generate_password_hash('RealHospitalPass123!')
    )
    assert is_original_hospital_account(real_hosp) is True
    assert real_hosp.is_original_account is True

    # Seeded oncology hospitals should be rejected
    seeded_onco_hosp = Hospital(
        id='HOSP-ONCO-01',
        name='Spherix Comprehensive Cancer Institute',
        email='cancer.institute@spherixclinic.com',
        password='seeded_hospital_pw_01'
    )
    assert is_original_hospital_account(seeded_onco_hosp) is False
    assert seeded_onco_hosp.is_original_account is False

    # Dummy / synthetic prefixed hospitals should be rejected
    dummy_hosp = Hospital(
        id='SEEDED-HOSP-99',
        name='Dummy Center',
        email='dummy@test.com',
        password='pass'
    )
    assert is_original_hospital_account(dummy_hosp) is False


def test_admin_dashboard_hospitals_section_shows_only_original_accounts(client, auth_admin):
    """
    Validates that the admin dashboard hospital section displays ONLY original hospital accounts
    and strictly excludes seeded/dummy hospitals.
    """
    # 1. Setup real hospital user
    real_hosp = Hospital(
        id='HPT/2026/789',
        name='Fortis Memorial Research Institute',
        email='admin@fortismemorial.org',
        password=generate_password_hash('RealPass123!'),
        total_beds=400,
        available_beds=120,
        icu_beds=50,
        available_icu_beds=15,
        hospital_type='Multispeciality Hospital'
    )
    real_hosp.is_verified = True
    TEMP_DATA.setdefault('hospitals', {})['HPT/2026/789'] = real_hosp

    # 2. Setup seeded fake hospital
    fake_hosp = Hospital(
        id='HOSP-ONCO-01',
        name='Spherix Comprehensive Cancer Institute',
        email='cancer.institute@spherixclinic.com',
        password='seeded_hospital_pw_01',
        total_beds=450,
        available_beds=82
    )
    TEMP_DATA['hospitals']['HOSP-ONCO-01'] = fake_hosp

    # 3. Request Admin Dashboard Hospitals Tab
    res = client.get('/admin/dashboard?tab=hospitals')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # The real hospital MUST be displayed in the table
    assert 'Fortis Memorial Research Institute' in html
    assert 'admin@fortismemorial.org' in html
    assert 'HPT/2026/789' in html
    assert 'Hospital User' in html

    # The seeded dummy hospital MUST NOT be displayed in the table
    assert 'HOSP-ONCO-01' not in html
    assert 'cancer.institute@spherixclinic.com' not in html


def test_classification_hospitals_api_shows_only_original_accounts(client, auth_admin):
    """
    Validates that /api/admin/classification/<type_id>/hospitals returns only original accounts.
    """
    real_hosp = Hospital(
        id='HPT/2026/555',
        name='Apex Heart & Lung Institute',
        email='contact@apexheart.org',
        password=generate_password_hash('RealPass123!'),
        hospital_type_id=1,
        hospital_type='General Hospital'
    )
    TEMP_DATA.setdefault('hospitals', {})['HPT/2026/555'] = real_hosp

    # Add seeded hospital with same hospital_type_id
    fake_hosp = Hospital(
        id='HOSP-ONCO-02',
        name='Spherix Proton & Robotic Oncology Pavilion',
        email='proton.robotics@spherixclinic.com',
        password='seeded_hospital_pw_02',
        hospital_type_id=1
    )
    TEMP_DATA['hospitals']['HOSP-ONCO-02'] = fake_hosp

    res = client.get('/api/admin/classification/1/hospitals')
    assert res.status_code == 200
    data = res.get_json()
    assert 'hospitals' in data
    
    returned_ids = [h['id'] for h in data['hospitals']]
    assert 'HPT/2026/555' in returned_ids
    assert 'HOSP-ONCO-02' not in returned_ids
