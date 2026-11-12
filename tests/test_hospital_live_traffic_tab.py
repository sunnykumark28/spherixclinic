import pytest
from spherix import create_app
from werkzeug.security import generate_password_hash
from spherix.models.user import Hospital
from spherix.services.database import TEMP_DATA

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        with app.app_context():
            hosp_id = 'HPT/2026/001'
            if hosp_id not in TEMP_DATA['hospitals']:
                default_pass = generate_password_hash('Hospital@123', method='pbkdf2:sha256:260000')
                TEMP_DATA['hospitals'][hosp_id] = Hospital(
                    id=hosp_id,
                    name='Spherix Apex Clinic',
                    email='hospital.traffic.test@spherixclinic.com',
                    password=default_pass,
                    is_verified=True,
                    publishing_status='published'
                )
            yield client

def test_hospital_live_traffic_tab_and_navigation(client):
    """Verify that Live Traffic Stream is configured as a dedicated tab and navigation item."""
    hosp_id = 'HPT/2026/001'
    with client.session_transaction() as sess:
        sess['_user_id'] = f'hospital-{hosp_id}'
        sess['_fresh'] = True

    res = client.get('/hospital/dashboard?tab=traffic')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Tab container and header
    assert 'x-show="activeTab === \'traffic\'"' in html
    assert 'LIVE TRAFFIC &amp; PATIENT INTAKE STREAM' in html or 'LIVE TRAFFIC & PATIENT INTAKE STREAM' in html
    assert 'Live Traffic &amp; Patient Stream Intake' in html or 'Live Traffic & Patient Stream Intake' in html

    # 2. Controls and metrics
    assert 'Auto Stream Ingestion' in html
    assert 'Total Live Patients' in html
    assert 'Active Bed Bookings' in html
    assert 'Latest Stream Event' in html
    assert 'Live Patient Intake Feed' in html

    # 3. Sidebar and subtabs navigation
    assert 'Live Traffic Stream' in html
    assert "id: 'traffic'" in html
    assert "label: 'Live Traffic'" in html

    # 4. Floating panel docked by default
    assert 'showFloatingTraffic' in html
    assert 'x-show="showFloatingTraffic"' in html
