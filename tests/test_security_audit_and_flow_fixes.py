import pytest
import os
import json
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
from spherix import create_app
from spherix.services.database import TEMP_DATA, setup_admin_user, restore_backup_data
from spherix.models.user import Doctor, Patient, Hospital, Staff
from spherix.models.clinical import PatientVital

@pytest.fixture
def test_app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'audit-test-key-12345'
    })
    yield app

@pytest.fixture
def client(test_app):
    return test_app.test_client()

def test_admin_backdoor_passwords_rejected(client, test_app):
    """Ensure weak default passwords like admin, admin123, Admin@1234 are rejected."""
    admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').lower() == 'admin@spherixclinic.com'), None)
    if not admin_doc:
        setup_admin_user()
        admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').lower() == 'admin@spherixclinic.com'), None)

    # Set strong password
    admin_doc.password = generate_password_hash('StrongAdminPassword@2026!')

    # Ensure environment bootstrap password is not matching the backdoors
    old_env = os.environ.get('ADMIN_BOOTSTRAP_PASSWORD')
    os.environ['ADMIN_BOOTSTRAP_PASSWORD'] = 'ExplicitBootstrapKey#999'

    try:
        weak_passwords = ['admin', 'admin123', 'Admin123', 'Admin@1234', 'spherixadmin', 'spherixclinic']
        for bad_pass in weak_passwords:
            # Bypass captcha challenge for test
            from security.captcha import create_test_challenge
            cid, code = create_test_challenge(portal_type='admin')
            with client.session_transaction() as sess:
                sess['_captcha_challenge_admin'] = cid

            res = client.post('/admin/login', data={
                'email': 'admin@spherixclinic.com',
                'password': bad_pass,
                'captcha': code
            }, follow_redirects=False)

            # Must fail authentication and redirect back to login, not dashboard
            assert res.status_code == 302
            assert '/admin/dashboard' not in res.location
    finally:
        if old_env:
            os.environ['ADMIN_BOOTSTRAP_PASSWORD'] = old_env
        else:
            os.environ.pop('ADMIN_BOOTSTRAP_PASSWORD', None)

def test_patient_required_blocks_non_patients(client):
    """Ensure doctors, hospitals, and staff cannot access patient-only endpoints."""
    # 1. Staff logged in
    stf = Staff(id='STF_RBAC_01', name='Nurse Alice', email='alice.staff@example.com', password=generate_password_hash('Pass123!'), role='Nurse')
    TEMP_DATA['staff']['STF_RBAC_01'] = stf

    with client.session_transaction() as sess:
        sess['_user_id'] = 'STF_RBAC_01'
        sess['user_role'] = 'staff'

    res = client.get('/patient/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/patient/login' in res.location or '/patient-login' in res.location

    # 2. Hospital logged in
    hosp = Hospital(id='HPT_RBAC_01', name='Metro Hospital', email='metro@example.com', password=generate_password_hash('Pass123!'))
    TEMP_DATA['hospitals']['HPT_RBAC_01'] = hosp

    with client.session_transaction() as sess:
        sess['_user_id'] = 'HPT_RBAC_01'
        sess['user_role'] = 'hospital'

    res = client.get('/patient/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/patient/login' in res.location or '/patient-login' in res.location

def test_staff_update_profile_requires_auth(client):
    """Ensure /staff/profile/update blocks unauthenticated POST requests."""
    res = client.post('/staff/profile/update', data={'name': 'Malicious Update'}, follow_redirects=False)
    assert res.status_code == 302
    assert '/staff/login' in res.location or '/staff-login' in res.location

def test_admin_restore_rehydrates_temp_data(client, test_app):
    """Ensure admin_restore restores JSON backup into TEMP_DATA and objects."""
    admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').lower() == 'admin@spherixclinic.com'), None)
    if not admin_doc:
        setup_admin_user()
        admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').lower() == 'admin@spherixclinic.com'), None)

    backup_payload = {
        'doctors': {
            'DOC_RESTORE_01': {
                'id': 'DOC_RESTORE_01',
                'first_name': 'Restored',
                'last_name': 'Doctor',
                'email': 'restored.doc@example.com',
                'password': generate_password_hash('Pass123!'),
                'department': 'Neurology'
            }
        },
        'patients': {
            'PAT_RESTORE_01': {
                'id': 'PAT_RESTORE_01',
                'name': 'Restored Patient',
                'email': 'restored.pat@example.com',
                'password': generate_password_hash('Pass123!')
            }
        }
    }

    # Test restore_backup_data directly
    success = restore_backup_data(backup_payload)
    assert success is True
    assert 'DOC_RESTORE_01' in TEMP_DATA['doctors']
    assert isinstance(TEMP_DATA['doctors']['DOC_RESTORE_01'], Doctor)
    assert TEMP_DATA['doctors']['DOC_RESTORE_01'].first_name == 'Restored'

    assert 'PAT_RESTORE_01' in TEMP_DATA['patients']
    assert isinstance(TEMP_DATA['patients']['PAT_RESTORE_01'], Patient)
    assert TEMP_DATA['patients']['PAT_RESTORE_01'].name == 'Restored Patient'

def test_nutrition_fitness_patient_vitals_no_crash(client):
    """Ensure nutrition fitness generator reads patient vitals without raising AttributeError."""
    pat_id = 'PAT_VITALS_01'
    patient = Patient(id=pat_id, name='Vitals Patient', email='vitals@example.com', password='pass')
    TEMP_DATA['patients'][pat_id] = patient
    TEMP_DATA['patient_vitals']['PV_01'] = PatientVital(
        id='PV_01',
        patient_id=pat_id,
        weight='72.5',
        height='178.0',
        recorded_at='2026-10-24 10:00:00'
    )

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['role'] = 'patient'
        sess['user_role'] = 'patient'

    res = client.get('/nutrition-fitness')
    assert res.status_code == 200
    assert b'72.5' in res.data or b'178' in res.data or b'Nutrition' in res.data
