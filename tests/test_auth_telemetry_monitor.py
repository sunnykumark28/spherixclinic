import pytest
from app import create_app
from spherix.services.database import TEMP_DATA, log_auth_activity
from spherix.models.user import Patient


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
        id='ADMIN-AUTH-TELEMETRY-TEST',
        name='Security Admin',
        email='admin@spherixclinic.com',
        password='HashedPassword123!'
    )
    admin.is_verified = True
    admin.mfa_enabled = True
    TEMP_DATA.setdefault('patients', {})['ADMIN-AUTH-TELEMETRY-TEST'] = admin
    with client.session_transaction() as sess:
        sess['_user_id'] = 'ADMIN-AUTH-TELEMETRY-TEST'
        sess['is_admin'] = True
        sess['user_role'] = 'admin'
    return admin


def test_auth_telemetry_table_horizontal_scroll_and_drawer(client, auth_admin):
    """
    Validates that:
    1. The Auth & Login Monitor table has the wide horizontal scroll wrapper and sticky user column.
    2. All 11 requested columns exist (including Login Tries, Forgot Pwd Tries, Active Session Duration).
    3. The #userAuthDrawer offcanvas sidebar drawer is rendered.
    4. The embedded JSON script #user-auth-summaries-json is present.
    5. Filter buttons exist for all authentication events.
    """
    response = client.get('/admin/dashboard?tab=auth_telemetry')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # 1. Container & Table verification
    assert 'auth-table-scroll-container' in html
    assert 'auth-sticky-col' in html
    assert 'id="authTelemetryTable"' in html

    # 2. Key column headers verification
    assert 'User Profile &amp; Role' in html or 'User Profile & Role' in html
    assert 'Event Action' in html
    assert 'Status' in html
    assert 'Login Tries' in html
    assert 'Forgot Pwd Tries' in html
    assert 'Session Active Duration' in html
    assert 'Logout Time' in html
    assert 'Device / Client' in html
    assert 'Security Actions' in html

    # 3. Filter buttons verification
    assert "filterAuthLogsByAction('all', this)" in html
    assert "filterAuthLogsByAction('Active', this)" in html
    assert "filterAuthLogsByAction('Login', this)" in html
    assert "filterAuthLogsByAction('Logout', this)" in html
    assert "filterAuthLogsByAction('Failed Login', this)" in html
    assert "filterAuthLogsByAction('Password Change', this)" in html
    assert "filterAuthLogsByAction('Forgot Password', this)" in html
    assert "filterAuthLogsByAction('Password Reset', this)" in html
    assert "filterAuthLogsByAction('Suspicious', this)" in html

    # 4. Offcanvas Drawer verification
    assert 'id="userAuthDrawer"' in html
    assert 'id="user-auth-summaries-json"' in html
    assert 'id="userDrawerAvatar"' in html
    assert 'id="userDrawerName"' in html
    assert 'id="userDrawerEmail"' in html
    assert 'id="kpiUserLogins"' in html
    assert 'id="kpiUserLogouts"' in html
    assert 'id="kpiUserLoginTries"' in html
    assert 'id="kpiUserForgotPwd"' in html
    assert 'id="kpiUserActiveDuration"' in html
    assert 'id="kpiUserPwdChanges"' in html
    assert 'id="userDrawerTimelineList"' in html

    # 5. JavaScript engine integration verification
    assert 'openUserAuthDrawer' in html
    assert 'populateUserAuthDrawer' in html
    assert 'terminateDrawerSession' in html
    assert 'terminateSessionFromRow' in html
    assert 'copyUserDrawerSummary' in html


def test_api_admin_auth_user_details(client, auth_admin):
    """
    Validates that the /api/admin/auth-user/<user_ref> endpoint returns real-time JSON
    metrics for a given user email or user ID.
    """
    test_email = 'telemetry_target@spherixclinic.com'
    test_uid = 'PAT-TEL-999'

    # Seed distinct auth events for this user
    log_auth_activity(
        user_id=test_uid,
        user_name='Telemetry Target',
        user_email=test_email,
        role='Patient',
        action='Successful Login',
        status='Active Session',
        ip_address='192.168.1.100',
        user_agent='Mozilla/5.0 Test Browser'
    )
    log_auth_activity(
        user_id=test_uid,
        user_name='Telemetry Target',
        user_email=test_email,
        role='Patient',
        action='Failed Login',
        status='Invalid Credentials',
        ip_address='192.168.1.100',
        user_agent='Mozilla/5.0 Test Browser'
    )
    log_auth_activity(
        user_id=test_uid,
        user_name='Telemetry Target',
        user_email=test_email,
        role='Patient',
        action='Forgot Password Request',
        status='Pending OTP',
        ip_address='192.168.1.100',
        user_agent='Mozilla/5.0 Test Browser'
    )
    log_auth_activity(
        user_id=test_uid,
        user_name='Telemetry Target',
        user_email=test_email,
        role='Patient',
        action='Password Change',
        status='Success',
        ip_address='192.168.1.100',
        user_agent='Mozilla/5.0 Test Browser'
    )

    # Query via email
    res = client.get(f'/api/admin/auth-user/{test_email}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    user = data['user']
    assert user['email'] == test_email
    assert user['login_tries'] >= 2  # 1 success + 1 failed
    assert user['failed_login_tries'] >= 1
    assert user['forgot_password_tries'] >= 1
    assert user['password_changes'] >= 1
    assert len(user['events']) >= 4

    # Query via user ID
    res_id = client.get(f'/api/admin/auth-user/{test_uid}')
    assert res_id.status_code == 200
    assert res_id.get_json()['success'] is True

    # Query non-existent user
    res_notfound = client.get('/api/admin/auth-user/nonexistent_user_99999@test.com')
    assert res_notfound.status_code == 404
    assert res_notfound.get_json()['success'] is False


def test_admin_terminate_auth_session_ajax(client, auth_admin):
    """
    Validates that /admin/auth-telemetry/terminate supports AJAX requests and responds with JSON.
    """
    # Create active session
    log_auth_activity(
        user_id='SESSION-USER-1',
        user_name='Active User',
        user_email='active@spherixclinic.com',
        role='Doctor',
        action='Successful Login',
        status='Active Session'
    )
    session_log = TEMP_DATA['auth_activity_logs'][-1]
    session_id = session_log['id']

    # Terminate via AJAX JSON
    res = client.post(
        '/admin/auth-telemetry/terminate',
        json={'session_id': session_id},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data['success'] is True

    # Verify log state changed
    terminated_log = next((l for l in TEMP_DATA['auth_activity_logs'] if l['id'] == session_id), None)
    assert terminated_log is not None
    assert terminated_log['status'] == 'Terminated'
    assert 'Terminated (Admin)' in terminated_log['duration']
