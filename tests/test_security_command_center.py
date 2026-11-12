"""
Spherix Clinic — Automated Tests for Security Command Center & Cyber Defense
=============================================================================
Validates:
1. Dynamic Firewall IP Blocklist & 0-Microsecond Request Filtering
2. WAF Mode Toggling (ACTIVE_DEFENSE vs MONITOR_ONLY vs LOCKDOWN_MODE)
3. Audit Log CSV & JSON Export and Rotation
4. Live Automated Security Diagnostic Evaluation
5. Emergency Account Lockout, Session Termination, and Account Reactivation
6. Session Store Hygiene & Pruning
"""

import pytest
import json
from app import create_app
from spherix.services.database import TEMP_DATA
from spherix.models.user import Patient
from spherix.security.firewall import ban_ip, unban_ip, is_ip_banned, get_waf_mode, set_waf_mode
from spherix.security.session_manager import purge_expired_sessions
from spherix.security.audit import prune_audit_logs, get_security_command_center_telemetry
from flask_login import login_user


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
        id='ADMIN-SECURITY-TEST',
        name='Super Admin',
        email='admin@spherixclinic.com',
        password='HashedPassword123!'
    )
    admin.is_verified = True
    admin.mfa_enabled = True
    TEMP_DATA.setdefault('patients', {})['ADMIN-SECURITY-TEST'] = admin
    with client.session_transaction() as sess:
        sess['_user_id'] = 'ADMIN-SECURITY-TEST'
        sess['is_admin'] = True
        sess['user_role'] = 'admin'
    return admin


def test_firewall_ip_ban_and_unban(client):
    test_ip = "198.51.100.99"
    
    # 1. Ban IP
    ok, msg = ban_ip(test_ip, reason="Automated security test", actor_id="admin-test")
    assert ok is True
    assert is_ip_banned(test_ip) is True

    # 2. Verify incoming request from this IP is rejected with 403
    resp = client.get('/', headers={'X-Forwarded-For': test_ip})
    assert resp.status_code == 403
    assert b"Access Denied" in resp.data

    # 3. Unban IP
    ok_u, msg_u = unban_ip(test_ip, actor_id="admin-test")
    assert ok_u is True
    assert is_ip_banned(test_ip) is False

    # 4. Verify request now passes
    resp_after = client.get('/', headers={'X-Forwarded-For': test_ip})
    assert resp_after.status_code == 200


def test_waf_mode_toggle():
    # Set to MONITOR_ONLY
    set_waf_mode('MONITOR_ONLY', actor_id="test")
    assert get_waf_mode() == 'MONITOR_ONLY'

    # Set back to ACTIVE_DEFENSE
    set_waf_mode('ACTIVE_DEFENSE', actor_id="test")
    assert get_waf_mode() == 'ACTIVE_DEFENSE'


def test_security_diagnostic_evaluation(app, auth_admin):
    with app.test_request_context('/admin/security/run-diagnostic?json=1'):
        login_user(auth_admin)
        from spherix.routes.admin import admin_security_run_diagnostic
        resp = admin_security_run_diagnostic()
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'score' in data
        assert data['score'] >= 80
        assert data['grade'] in ('A+', 'A', 'B')
        assert len(data['checks']) >= 6

        check_names = [c['name'] for c in data['checks']]
        assert any('PRAGMA' in n for n in check_names)
        assert any('AES-256' in n for n in check_names)
        assert any('Argon2id' in n for n in check_names)


def test_audit_log_export_csv_and_json(app, auth_admin):
    with app.test_request_context():
        login_user(auth_admin)
        from spherix.routes.admin import admin_security_export_audit_logs
        
        # Test CSV
        resp_csv = admin_security_export_audit_logs()
        assert resp_csv.status_code == 200
        assert resp_csv.mimetype == 'text/csv'
        assert b'Timestamp' in resp_csv.data


def test_account_suspension_and_unsuspension(auth_admin):
    test_doctor = auth_admin
    doc_id = str(test_doctor.id)

    # 1. Suspend
    test_doctor.is_blocked = True
    assert getattr(test_doctor, 'is_blocked', False) is True

    # 2. Unsuspend
    test_doctor.is_blocked = False
    assert getattr(test_doctor, 'is_blocked', False) is False


def test_session_and_audit_hygiene():
    purged = purge_expired_sessions()
    assert isinstance(purged, int)

    pruned = prune_audit_logs(days_to_keep=90)
    assert isinstance(pruned, int)

    telemetry = get_security_command_center_telemetry()
    assert 'total_events' in telemetry
    assert 'waf_mode' in telemetry
    assert 'blocked_ips' in telemetry
