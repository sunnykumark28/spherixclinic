import pytest
from werkzeug.security import generate_password_hash
from spherix.models.user import Hospital
from spherix.services.database import TEMP_DATA

def test_draggable_live_traffic_stream_panel(client):
    """
    Verify that the Live Traffic Stream panel on Hospital Dashboard is configured
    with draggable handle, reset control, and pointer drag scripts.
    """
    hosp_id = 'HPT/2026/001'
    if hosp_id not in TEMP_DATA['hospitals']:
        default_pass = generate_password_hash('Hospital@123', method='pbkdf2:sha256:260000')
        TEMP_DATA['hospitals'][hosp_id] = Hospital(
            id=hosp_id,
            name='Spherix Clinic',
            email='hospital.test@spherixclinic.com',
            password=default_pass,
            address='Main Medical Campus, New Delhi',
            city='New Delhi',
            country='India',
            is_verified=True,
            publishing_status='published'
        )

    with client.session_transaction() as sess:
        sess['_user_id'] = f'hospital-{hosp_id}'
        sess['_fresh'] = True

    res = client.get('/hospital/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Panel container check
    assert 'id="liveTrafficPanel"' in html
    assert 'floating-simulator-panel' in html

    # Drag handle & grip icon check
    assert 'id="liveTrafficHeader"' in html
    assert 'traffic-panel-drag-handle' in html
    assert 'fa-grip-vertical' in html

    # Reset button check
    assert 'id="resetTrafficPosBtn"' in html

    # Drag implementation script check
    assert 'initDraggableTrafficPanel' in html
    assert 'spherix_live_traffic_position' in html
    assert 'pointerdown' in html
    assert 'pointermove' in html
    assert 'pointerup' in html
