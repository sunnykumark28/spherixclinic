import pytest
from flask import session
from werkzeug.security import generate_password_hash
from spherix import create_app
from spherix.services.database import TEMP_DATA
from spherix.models.user import Doctor, Patient, Hospital, HospitalStaff, BloodDonor, OrganDonor

@pytest.fixture
def auth_client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_unauthenticated_protected_routes_redirect_to_own_login(auth_client):
    client = auth_client

    # 1. Doctor protected route
    res = client.get('/doctor/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/doctor/login' in res.location or '/doctor-login' in res.location

    # 2. Patient protected route
    res = client.get('/patient/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/patient/login' in res.location or '/patient-login' in res.location

    # 3. Hospital protected route
    res = client.get('/hospital/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/hospital/login' in res.location or '/hospital-login' in res.location

    # 4. Staff protected route
    res = client.get('/staff/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/staff/login' in res.location or '/staff-login' in res.location

    # 5. Admin protected route
    res = client.get('/admin/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/admin/login' in res.location or '/admin-login' in res.location

    # 6. Blood Donor protected route
    res = client.get('/blood-donor/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/blood-donor' in res.location and 'login' in res.location

    # 7. Organ Donor protected route
    res = client.get('/organ-donor/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/organ-donor' in res.location and 'login' in res.location

    # 8. Pathology protected route
    res = client.get('/pathology/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/pathology/login' in res.location

def test_root_portal_routes_redirect_unauthenticated_to_own_login(auth_client):
    client = auth_client

    for portal_path, expected_login_path in [
        ('/doctor', '/doctor'),
        ('/patient', '/patient'),
        ('/hospital', '/hospital'),
        ('/staff', '/staff'),
        ('/admin', '/admin'),
        ('/blood-donor', '/blood-donor'),
        ('/organ-donor', '/organ-donor'),
    ]:
        res = client.get(portal_path, follow_redirects=False)
        assert res.status_code in [301, 302]
        assert expected_login_path in res.location
        assert 'login' in res.location

def test_doctor_logout_redirects_to_doctor_login(auth_client):
    client = auth_client
    doc_id = 'DOC_LOGOUT_TEST_01'
    doctor = Doctor(
        id=doc_id,
        first_name='Logout',
        last_name='Doctor',
        email='logout_doc@example.com',
        password=generate_password_hash('DocPass123!', method='pbkdf2:sha256:260000'),
        department='Cardiology'
    )
    TEMP_DATA['doctors'][doc_id] = doctor

    with client.session_transaction() as sess:
        sess['_user_id'] = doc_id
        sess['user_role'] = 'doctor'

    # Calling generic /logout while logged in as doctor
    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/doctor/login' in res.location or '/doctor-login' in res.location

def test_patient_logout_redirects_to_patient_login(auth_client):
    client = auth_client
    pat_id = 'PAT_LOGOUT_TEST_01'
    patient = Patient(
        id=pat_id,
        name='Logout Patient',
        email='logout_pat@example.com',
        phone='9991112223',
        password=generate_password_hash('PatPass123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['patients'][pat_id] = patient

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['user_role'] = 'patient'

    # Calling generic /logout while logged in as patient
    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/patient/login' in res.location or '/patient-login' in res.location

def test_hospital_logout_redirects_to_hospital_login(auth_client):
    client = auth_client
    hosp_id = 'HPT_LOGOUT_TEST_01'
    hospital = Hospital(
        id=hosp_id,
        name='Logout Hospital',
        email='logout_hosp@example.com',
        password=generate_password_hash('HospPass123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['hospitals'][hosp_id] = hospital

    with client.session_transaction() as sess:
        sess['_user_id'] = hosp_id
        sess['user_role'] = 'hospital'

    # Calling generic /logout while logged in as hospital
    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/hospital/login' in res.location or '/hospital-login' in res.location

def test_staff_logout_redirects_to_staff_login(auth_client):
    client = auth_client
    stf_id = 'STF_LOGOUT_TEST_01'
    staff = HospitalStaff(
        id=stf_id,
        name='Logout Staff',
        email='logout_stf@example.com',
        hospital_id='HPT_LOGOUT_TEST_01',
        role='General Staff',
        password=generate_password_hash('StaffPass123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['staff'][stf_id] = staff

    with client.session_transaction() as sess:
        sess['_user_id'] = stf_id
        sess['user_role'] = 'staff'

    # Calling generic /logout while logged in as staff
    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/staff/login' in res.location or '/staff-login' in res.location

def test_admin_logout_redirects_to_admin_login(auth_client):
    client = auth_client

    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['user_role'] = 'admin'
        sess['is_admin'] = True

    # Calling generic /logout or /admin/logout
    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/admin/login' in res.location or '/admin-login' in res.location

def test_blood_donor_logout_redirects_to_blood_donor_login(auth_client):
    client = auth_client
    bd_id = 'BD_LOGOUT_TEST_01'
    donor = BloodDonor(
        id=bd_id,
        name='Logout Blood Donor',
        email='logout_bd@example.com',
        phone='9994445556',
        blood_group='O+',
        age=30,
        city='City',
        password=generate_password_hash('BdPass123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['blood_donors'][bd_id] = donor

    with client.session_transaction() as sess:
        sess['_user_id'] = bd_id
        sess['user_role'] = 'blood_donor'

    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/blood-donor' in res.location and 'login' in res.location

def test_organ_donor_logout_redirects_to_organ_donor_login(auth_client):
    client = auth_client
    od_id = 'OD_LOGOUT_TEST_01'
    donor = OrganDonor(
        id=od_id,
        name='Logout Organ Donor',
        email='logout_od@example.com',
        phone='9997778889',
        organs=['Kidney'],
        blood_group='A+',
        age=35,
        city='City',
        password=generate_password_hash('OdPass123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['organ_donors'][od_id] = donor

    with client.session_transaction() as sess:
        sess['_user_id'] = od_id
        sess['user_role'] = 'organ_donor'

    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/organ-donor' in res.location and 'login' in res.location

def test_pathology_logout_redirects_to_pathology_login(auth_client):
    client = auth_client

    with client.session_transaction() as sess:
        sess['pathology_staff_id'] = 1
        sess['pathology_center_id'] = 1
        sess['_user_type'] = 'pathology'

    res = client.get('/pathology/logout', follow_redirects=False)
    assert res.status_code == 302
    assert '/pathology/login' in res.location

def test_login_landing_role_and_next_dispatch(auth_client):
    client = auth_client

    # Role param dispatch
    res = client.get('/login?role=doctor', follow_redirects=False)
    assert res.status_code == 302
    assert '/doctor/login' in res.location or '/doctor-login' in res.location

    res = client.get('/login?role=patient', follow_redirects=False)
    assert res.status_code == 302
    assert '/patient/login' in res.location or '/patient-login' in res.location

    res = client.get('/login?role=hospital', follow_redirects=False)
    assert res.status_code == 302
    assert '/hospital/login' in res.location or '/hospital-login' in res.location

    res = client.get('/login?role=staff', follow_redirects=False)
    assert res.status_code == 302
    assert '/staff/login' in res.location or '/staff-login' in res.location

    res = client.get('/login?role=admin', follow_redirects=False)
    assert res.status_code == 302
    assert '/admin/login' in res.location or '/admin-login' in res.location

    # Next param dispatch
    res = client.get('/login?next=/doctor/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/doctor/login' in res.location or '/doctor-login' in res.location

    res = client.get('/login?next=/patient/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/patient/login' in res.location or '/patient-login' in res.location
