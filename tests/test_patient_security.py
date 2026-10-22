import pytest
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
from spherix import create_app
from spherix.services.database import TEMP_DATA
from spherix.models.user import Patient

@pytest.fixture
def security_test_client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_patient_security_dashboard_render(security_test_client):
    client = security_test_client
    # Setup test patient
    pat_id = 'PAT_SEC_TEST_01'
    patient = Patient(
        id=pat_id,
        name='Security Tester',
        email='sec_tester@example.com',
        phone='9999988888',
        password=generate_password_hash('OldPass123!', method='pbkdf2:sha256:260000')
    )
    patient.is_verified = True
    TEMP_DATA['patients'][pat_id] = patient

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['user_role'] = 'patient'

    res = client.get('/patient/dashboard?tab=security')
    assert res.status_code == 200
    assert b"Security &amp; Safety" in res.data or b"Security & Safety" in res.data
    assert b"Change Password" in res.data
    assert b"Don&#039;t know current password? Use OTP" in res.data or b"Use OTP" in res.data
    assert b"sidebarForgotOtp" in res.data
    assert b"Delete Account Zone" in res.data
    assert b"sidebarDeleteAccount" in res.data
    assert b"Temporarily Deactivate Account" in res.data
    assert b"Permanently Delete Account" in res.data

def test_patient_change_password_standard(security_test_client):
    client = security_test_client
    pat_id = 'PAT_SEC_TEST_02'
    patient = Patient(
        id=pat_id,
        name='Pass Changer',
        email='pass_changer@example.com',
        phone='9999988887',
        password=generate_password_hash('CurrentPass123!', method='pbkdf2:sha256:260000')
    )
    patient.is_verified = True
    TEMP_DATA['patients'][pat_id] = patient

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['user_role'] = 'patient'

    # 1. Incorrect current password
    res_fail = client.post('/patient/dashboard', data={
        'action': 'change_password',
        'current_password': 'WrongPassword!',
        'new_password': 'NewPass12345!',
        'confirm_password': 'NewPass12345!',
        'ajax': '1'
    })
    assert res_fail.status_code == 400
    assert not res_fail.json['success']

    # 2. Correct current password
    res_ok = client.post('/patient/dashboard', data={
        'action': 'change_password',
        'current_password': 'CurrentPass123!',
        'new_password': 'NewPass12345!',
        'confirm_password': 'NewPass12345!',
        'ajax': '1'
    })
    assert res_ok.status_code == 200
    assert res_ok.json['success']
    assert check_password_hash(patient.password, 'NewPass12345!')

def test_patient_forgot_password_otp_flow(security_test_client):
    client = security_test_client
    pat_id = 'PAT_SEC_TEST_03'
    patient = Patient(
        id=pat_id,
        name='OTP Tester',
        email='otp_tester@example.com',
        phone='9999988886',
        password=generate_password_hash('ForgottenPass123!', method='pbkdf2:sha256:260000')
    )
    patient.is_verified = True
    TEMP_DATA['patients'][pat_id] = patient

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['user_role'] = 'patient'

    # Step 1: Request OTP
    res_req = client.post('/patient/dashboard', data={
        'action': 'request_security_otp',
        'ajax': '1'
    })
    assert res_req.status_code == 200
    assert res_req.json['success']

    with client.session_transaction() as sess:
        otp = sess['security_otp']['otp']

    # Step 2: Reset Password with wrong OTP
    res_bad = client.post('/patient/dashboard', data={
        'action': 'reset_password_otp',
        'otp': '000000',
        'new_password': 'ResetPass123!',
        'confirm_password': 'ResetPass123!',
        'ajax': '1'
    })
    assert res_bad.status_code == 400
    assert not res_bad.json['success']

    # Step 3: Reset Password with valid OTP
    res_good = client.post('/patient/dashboard', data={
        'action': 'reset_password_otp',
        'otp': otp,
        'new_password': 'ResetPass123!',
        'confirm_password': 'ResetPass123!',
        'ajax': '1'
    })
    assert res_good.status_code == 200
    assert res_good.json['success']
    assert check_password_hash(patient.password, 'ResetPass123!')

def test_patient_delete_and_deactivate_flow(security_test_client):
    client = security_test_client
    pat_id = 'PAT_SEC_TEST_04'
    patient = Patient(
        id=pat_id,
        name='Deactivate Tester',
        email='deact_tester@example.com',
        phone='9999988885',
        password=generate_password_hash('MyPass123!', method='pbkdf2:sha256:260000')
    )
    patient.is_verified = True
    TEMP_DATA['patients'][pat_id] = patient

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['user_role'] = 'patient'

    # 1. Request OTP with incorrect password -> should fail
    res_req_bad = client.post('/patient/dashboard', data={
        'action': 'request_delete_account_otp',
        'verify_password': 'WrongPassword!',
        'ajax': '1'
    })
    assert res_req_bad.status_code == 400
    assert not res_req_bad.json['success']

    # 2. Request OTP with correct password -> should succeed
    res_req_good = client.post('/patient/dashboard', data={
        'action': 'request_delete_account_otp',
        'verify_password': 'MyPass123!',
        'ajax': '1'
    })
    assert res_req_good.status_code == 200
    assert res_req_good.json['success']

    with client.session_transaction() as sess:
        otp = sess['delete_account_otp']['otp']

    # 3. Confirm Deactivation with invalid OTP -> should fail
    res_deact_bad = client.post('/patient/dashboard', data={
        'action': 'delete_or_deactivate_profile',
        'op_type': 'deactivate',
        'verify_password': 'MyPass123!',
        'otp': '999999',
        'ajax': '1'
    })
    assert res_deact_bad.status_code == 400

    # 4. Confirm Deactivation with valid OTP and password -> should succeed
    res_deact = client.post('/patient/dashboard', data={
        'action': 'delete_or_deactivate_profile',
        'op_type': 'deactivate',
        'verify_password': 'MyPass123!',
        'otp': otp,
        'ajax': '1'
    })
    assert res_deact.status_code == 200
    assert res_deact.json['success']
    assert getattr(patient, 'is_deactivated', False) is True
