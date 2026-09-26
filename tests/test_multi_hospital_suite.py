import pytest
from flask import session
from werkzeug.security import generate_password_hash
from spherix import create_app
from spherix.models import Staff, Hospital
from spherix.services.database import TEMP_DATA, load_data, save_data

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            load_data()
            # Seed test isolated multi-hospital fixtures
            default_pass = generate_password_hash('Admin@123', method='pbkdf2:sha256:260000')
            hosp_a_id = 'HPT/2026/001'
            hosp_b_id = 'HPT/2026/002'
            TEMP_DATA['hospitals'][hosp_a_id] = Hospital(
                id=hosp_a_id, name='SMCH (Spherix Memorial Care Hospital)', email='hospital.test@spherixclinic.com',
                password=default_pass, total_beds=150, available_beds=42, icu_beds=25, available_icu_beds=6,
                doctors_available='Available', address='Main Medical Campus, Motihari, Bihar', city='Motihari', state='Bihar',
                general_bed_fee=1000.0, icu_bed_fee=2500.0, is_verified=True,
                blood_stock={'A+': 18, 'A-': 8, 'B+': 24, 'B-': 6, 'AB+': 12, 'AB-': 4, 'O+': 32, 'O-': 10}
            )
            TEMP_DATA['hospitals'][hosp_b_id] = Hospital(
                id=hosp_b_id, name='Apollo Super Speciality Hospital', email='apollo.test@example.com',
                password=default_pass, total_beds=320, available_beds=95, icu_beds=50, available_icu_beds=14,
                doctors_available='Available', address='Mathura Road, Sarita Vihar, New Delhi', city='New Delhi', state='DL',
                general_bed_fee=1200.0, icu_bed_fee=3000.0, is_verified=True,
                blood_stock={'A+': 25, 'A-': 12, 'B+': 30, 'B-': 8, 'AB+': 15, 'AB-': 5, 'O+': 40, 'O-': 14}
            )
            staff_list = [
                ('STF/2026/001', 'Sumit Kumar', 'sumit@gmail.com', 'Blood Donor Management', '+91 933 4325 921', hosp_a_id, 'SMCH (Spherix Memorial Care Hospital)'),
                ('STF/2026/002', 'Dr. Rajiv Verma', 'organ.smch@example.com', 'Organ Donor Management', '+91 988 2233 441', hosp_a_id, 'SMCH (Spherix Memorial Care Hospital)'),
                ('STF/2026/003', 'Sunita Kumari', 'reception.smch@example.com', 'Receptionist', '+91 944 3322 110', hosp_a_id, 'SMCH (Spherix Memorial Care Hospital)'),
                ('STF/2026/004', 'Amitabh Sen', 'bed.smch@example.com', 'Bed Management', '+91 977 4455 667', hosp_a_id, 'SMCH (Spherix Memorial Care Hospital)'),
                ('STF/2026/005', 'Pooja Sharma', 'pooja.nurse@example.com', 'Nurse', '+91 988 7766 554', hosp_a_id, 'SMCH (Spherix Memorial Care Hospital)'),
                ('STF/2026/006', 'Ramesh Prasad', 'general.smch@example.com', 'General Staff', '+91 911 2233 445', hosp_a_id, 'SMCH (Spherix Memorial Care Hospital)'),
                ('STF/2026/011', 'Marcus Vance', 'blood.apollo@example.com', 'Blood Donor Management', '+91 944 5566 771', hosp_b_id, 'Apollo Super Speciality Hospital'),
                ('STF/2026/012', 'Dr. Liam O\'Connor', 'organ.apollo@example.com', 'Organ Donor Management', '+91 944 5566 772', hosp_b_id, 'Apollo Super Speciality Hospital'),
                ('STF/2026/013', 'Kevin Vance', 'kevin.reception@example.com', 'Receptionist', '+91 944 5566 778', hosp_b_id, 'Apollo Super Speciality Hospital'),
                ('STF/2026/014', 'David Miller', 'bed.apollo@example.com', 'Bed Management', '+91 944 5566 774', hosp_b_id, 'Apollo Super Speciality Hospital'),
                ('STF/2026/015', 'Sarah Jenkins RN', 'nurse.apollo@example.com', 'Nurse', '+91 944 5566 775', hosp_b_id, 'Apollo Super Speciality Hospital'),
                ('STF/2026/016', 'John Doe', 'general.apollo@example.com', 'General Staff', '+91 944 5566 776', hosp_b_id, 'Apollo Super Speciality Hospital'),
            ]
            for sid, sname, semail, srole, sphone, shid, shname in staff_list:
                TEMP_DATA['staff'][sid] = Staff(
                    id=sid, name=sname, email=semail, password=default_pass,
                    role=srole, phone=sphone, hospital_id=shid, hospital_name=shname, on_duty=True
                )
            # Default ward beds for testing
            if 'beds' not in TEMP_DATA:
                TEMP_DATA['beds'] = {}
            TEMP_DATA['beds']['HPT/2026/001_GW-102'] = {
                'id': 'HPT/2026/001_GW-102', 'bed_id': 'GW-102', 'hospital_id': hosp_a_id,
                'ward': 'General Ward A', 'floor': '1st Floor', 'bed_type': 'General', 'status': 'Available', 'room_number': 'GW-102'
            }
        yield client

def login_staff_helper(client, email, password='Admin@123'):
    client.get('/staff/login')
    with client.session_transaction() as sess:
        captcha = sess.get('staff_captcha', '')
    return client.post('/staff/login', data={
        'email': email,
        'password': password,
        'agree_terms': 'on',
        'captcha': captcha
    }, follow_redirects=True)

def test_multi_hospital_dispatch_and_isolation(client):
    """Test that all 6 roles redirect to their specific dashboards and see only their hospital's data."""
    # 1. Hospital A Blood Staff
    res = login_staff_helper(client, 'sumit@gmail.com')
    assert res.status_code == 200
    res_dash = client.get('/staff/dashboard', follow_redirects=True)
    assert b'Blood Bank Command Station' in res_dash.data
    # Should see Hospital A name, not Hospital B
    assert b'Apollo' not in res_dash.data
    client.get('/logout', follow_redirects=True)

    # 2. Hospital B Blood Staff
    res = login_staff_helper(client, 'blood.apollo@example.com')
    assert res.status_code == 200
    res_dash = client.get('/staff/dashboard', follow_redirects=True)
    assert b'Blood Bank Command Station' in res_dash.data
    assert b'Apollo Super Speciality Hospital' in res_dash.data
    client.get('/logout', follow_redirects=True)

    # 3. Hospital A Reception Staff
    res = login_staff_helper(client, 'reception.smch@example.com')
    assert res.status_code == 200
    res_dash = client.get('/staff/dashboard', follow_redirects=True)
    assert b'Front Desk' in res_dash.data or b'Reception' in res_dash.data
    client.get('/logout', follow_redirects=True)

    # 4. Hospital A Bed Management Staff
    res = login_staff_helper(client, 'bed.smch@example.com')
    assert res.status_code == 200
    res_dash = client.get('/staff/dashboard', follow_redirects=True)
    assert b'Bed Management' in res_dash.data
    client.get('/logout', follow_redirects=True)

    # 5. Hospital A Nurse
    res = login_staff_helper(client, 'pooja.nurse@example.com')
    assert res.status_code == 200
    res_dash = client.get('/staff/dashboard', follow_redirects=True)
    assert b'Nursing Station' in res_dash.data
    client.get('/logout', follow_redirects=True)

    # 6. Hospital A General Staff
    res = login_staff_helper(client, 'general.smch@example.com')
    assert res.status_code == 200
    res_dash = client.get('/staff/dashboard', follow_redirects=True)
    assert b'Staff Operations' in res_dash.data or b'Staff Workspace' in res_dash.data
    client.get('/logout', follow_redirects=True)

def test_cross_hospital_idor_and_rbac(client):
    """Test RBAC restrictions between roles and IDOR prevention across hospitals."""
    # Nurse trying to access Reception dashboard
    login_staff_helper(client, 'pooja.nurse@example.com')
    res = client.get('/staff/dashboard/reception', follow_redirects=True)
    # Should be denied / flashed unauthorized
    assert (b'Access denied' in res.data) or (b'Staff Operations' in res.data) or (b'Nursing Station' in res.data)
    client.get('/logout', follow_redirects=True)

    # Receptionist trying to access Bed dashboard
    login_staff_helper(client, 'reception.smch@example.com')
    res = client.get('/staff/dashboard/beds', follow_redirects=True)
    assert (b'Access denied' in res.data) or (b'Reception' in res.data)
    client.get('/logout', follow_redirects=True)

    # Hospital A blood staff fulfilling Hospital B request (IDOR)
    login_staff_helper(client, 'sumit@gmail.com')
    # Blood request 2 belongs to Hospital B
    res = client.post('/staff/dashboard/blood', data={
        'fulfill_blood_request': '1',
        'request_id': '2',
        'redirect_tab': 'requests'
    }, follow_redirects=True)
    assert b'Access Denied' in res.data
    client.get('/logout', follow_redirects=True)

def test_full_connected_lifecycle(client):
    """
    Test the complete operational chain:
    1. Direct Bed Admission at Reception
    2. Bed shows Occupied on Ward Floorplan
    3. Nurse submits blood request
    4. Blood Bank fulfills blood request (deducts stock)
    5. Nurse/Bed staff discharges patient
    6. Bed transitions to 'Cleaning'
    7. Staff marks bed cleaned -> Available
    """
    # Step 1: Reception registers direct admission
    login_staff_helper(client, 'reception.smch@example.com')
    res = client.post('/staff/dashboard/reception', data={
        'direct_bed_admission': '1',
        'patient_name': 'Test Integration Patient',
        'patient_phone': '9876543210',
        'bed_type': 'General',
        'room_number': 'GW-102',
        'reason': 'Acute observation'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'admitted directly' in res.data
    client.get('/logout', follow_redirects=True)

    # Step 2: Bed Dashboard shows bed as Occupied
    login_staff_helper(client, 'bed.smch@example.com')
    res_bed = client.get('/staff/dashboard/beds')
    assert b'GW-102' in res_bed.data
    assert b'Test Integration Patient' in res_bed.data
    client.get('/logout', follow_redirects=True)

    # Step 3: Nurse requests blood transfusion
    login_staff_helper(client, 'pooja.nurse@example.com')
    res_nurse = client.post('/staff/dashboard/nursing', data={
        'request_blood_transfusion': '1',
        'patient_name': 'Test Integration Patient',
        'blood_group': 'O+',
        'units': '2',
        'urgency': 'Stat / Emergency'
    }, follow_redirects=True)
    assert b'Urgent requisition' in res_nurse.data
    client.get('/logout', follow_redirects=True)

    # Step 4: Blood staff sees and fulfills the request
    login_staff_helper(client, 'sumit@gmail.com')
    res_blood = client.get('/staff/dashboard/blood?tab=requests')
    assert b'Test Integration Patient' in res_blood.data
    assert b'Stat / Emergency' in res_blood.data
    
    # Get initial O+ stock for SMCH
    hosp_a = TEMP_DATA['hospitals']['HPT/2026/001']
    initial_stock = hosp_a.blood_stock['O+']
    
    # Find request id for Test Integration Patient
    req_id = next((r['id'] for r in TEMP_DATA['blood_requests'].values() if r.get('patient_name') == 'Test Integration Patient'), None)
    assert req_id is not None

    res_fulfill = client.post('/staff/dashboard/blood', data={
        'fulfill_blood_request': '1',
        'request_id': str(req_id),
        'redirect_tab': 'requests'
    }, follow_redirects=True)
    assert b'Successfully fulfilled' in res_fulfill.data
    # Verify stock deducted
    assert hosp_a.blood_stock['O+'] == initial_stock - 2
    client.get('/logout', follow_redirects=True)

    # Step 5: Discharge patient from bed
    login_staff_helper(client, 'bed.smch@example.com')
    booking_id = next((b.id for b in TEMP_DATA['bed_bookings'].values() if b.patient_name == 'Test Integration Patient' and b.status in ['approved', 'active']), None)
    assert booking_id is not None
    
    res_discharge = client.post('/staff/dashboard/beds', data={
        'discharge_patient': '1',
        'booking_id': str(booking_id)
    }, follow_redirects=True)
    assert b'transitioned to Cleaning' in res_discharge.data

    # Step 6: Verify bed is in 'Cleaning' status on floorplan
    res_after_discharge = client.get('/staff/dashboard/beds')
    assert b'Awaiting Sanitization' in res_after_discharge.data or b'Cleaning' in res_after_discharge.data

    # Step 7: Mark bed cleaned -> transitions to 'Available'
    avail_before = hosp_a.available_beds
    res_clean = client.post('/staff/dashboard/beds', data={
        'mark_bed_cleaned': '1',
        'bed_id': 'GW-102'
    }, follow_redirects=True)
    assert b'sanitized and released to Available' in res_clean.data
    assert hosp_a.available_beds == avail_before + 1
    client.get('/logout', follow_redirects=True)

def test_general_staff_operations(client):
    """Test clock in, clock out, task creation, status update, and leave application."""
    login_staff_helper(client, 'general.smch@example.com')
    
    # Clock in
    res_clockin = client.post('/staff/dashboard/general', data={'clock_in': '1'}, follow_redirects=True)
    assert b'Clocked in successfully' in res_clockin.data

    # Create task
    res_task = client.post('/staff/dashboard/general', data={
        'create_task': '1',
        'title': 'Test Sanitization Task',
        'description': 'Inspect sanitation of Level 1 hallways',
        'assigned_to': 'Ramesh Prasad',
        'priority': 'High',
        'due_date': '2026-09-30'
    }, follow_redirects=True)
    assert b'assigned successfully' in res_task.data
    
    # Find created task
    task = next((t for t in TEMP_DATA['staff_tasks'].values() if t.get('title') == 'Test Sanitization Task'), None)
    assert task is not None
    assert task['hospital_id'] == 'HPT/2026/001'

    # Update task status to Completed
    res_update_task = client.post('/staff/dashboard/general', data={
        'update_task_status': '1',
        'task_id': str(task['id']),
        'status': 'Completed'
    }, follow_redirects=True)
    assert b'status updated' in res_update_task.data
    assert task['status'] == 'Completed'

    # Apply leave
    res_leave = client.post('/staff/dashboard/general', data={
        'apply_leave': '1',
        'leave_type': 'Casual Leave',
        'start_date': '2026-10-01',
        'end_date': '2026-10-03',
        'reason': 'Personal family event'
    }, follow_redirects=True)
    assert b'Leave request for 3 day(s) submitted' in res_leave.data

    # Clock out
    res_clockout = client.post('/staff/dashboard/general', data={'clock_out': '1'}, follow_redirects=True)
    assert b'Clocked out successfully' in res_clockout.data
    client.get('/logout', follow_redirects=True)
