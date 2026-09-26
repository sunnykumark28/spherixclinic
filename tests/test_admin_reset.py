import pytest
from flask import session
from spherix.services.database import TEMP_DATA, setup_admin_user
from werkzeug.security import generate_password_hash

def test_admin_database_reset_multi_step_flow(client, app):
    # Setup admin user in TEMP_DATA
    admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').lower() == 'admin@spherixclinic.com'), None)
    if not admin_doc:
        setup_admin_user()
        admin_doc = next((d for d in TEMP_DATA.get('doctors', {}).values() if getattr(d, 'email', '').lower() == 'admin@spherixclinic.com'), None)
    
    admin_doc.password = generate_password_hash('AdminSecretPass!123')

    # 1. Unauthenticated request should redirect or fail
    res = client.post('/admin/system/reset/request-otp', json={'password': 'AdminSecretPass!123'})
    assert res.status_code == 302 or res.status_code == 401

    # Login as Admin
    with client.session_transaction() as sess:
        sess['_user_id'] = f"doctor-{admin_doc.id}"

    # 2. Step 1: Wrong password -> 401
    res = client.post('/admin/system/reset/request-otp', json={'password': 'WrongPassword!'})
    assert res.status_code == 401
    data = res.get_json()
    assert data['success'] is False

    # 3. Step 1: Correct password -> 200 + Dispatches OTP
    res = client.post('/admin/system/reset/request-otp', json={'password': 'AdminSecretPass!123'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'masked_email' in data
    assert 'dev_otp' in data
    valid_otp = data['dev_otp']

    # 4. Step 2: Invalid OTP -> 400
    res = client.post('/admin/system/reset/verify-otp', json={'otp': '000000'})
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False

    # 5. Step 2: Valid OTP -> 200
    res = client.post('/admin/system/reset/verify-otp', json={'otp': valid_otp})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

    # 6. Step 3: Missing policy agreement -> 400
    res = client.post('/admin/system/reset', json={
        'policy_agreed': False,
        'confirmation_phrase': 'RESET SPHERIX DATABASE'
    })
    assert res.status_code == 400
    assert res.get_json()['success'] is False

    # 7. Step 3: Wrong confirmation phrase -> 400
    res = client.post('/admin/system/reset', json={
        'policy_agreed': True,
        'confirmation_phrase': 'RESET'
    })
    assert res.status_code == 400
    assert res.get_json()['success'] is False

    # 8. Step 4: Full Valid Execution -> 200 + Resets DB
    res = client.post('/admin/system/reset', json={
        'policy_agreed': True,
        'confirmation_phrase': 'RESET SPHERIX DATABASE'
    })
    assert res.status_code == 200
    assert res.get_json()['success'] is True
