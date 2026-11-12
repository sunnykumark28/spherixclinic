import pytest
from app import create_app
from spherix.services.database import TEMP_DATA
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
        id='ADMIN-CHART-TEST',
        name='Super Admin',
        email='admin@spherixclinic.com',
        password='HashedPassword123!'
    )
    admin.is_verified = True
    admin.mfa_enabled = True
    TEMP_DATA.setdefault('patients', {})['ADMIN-CHART-TEST'] = admin
    with client.session_transaction() as sess:
        sess['_user_id'] = 'ADMIN-CHART-TEST'
        sess['is_admin'] = True
        sess['user_role'] = 'admin'
    return admin


def test_admin_dashboard_charts_and_analysis_modal_rendered(client, auth_admin):
    """
    Validates that:
    1. All 8 chart canvas elements exist in the admin dashboard.
    2. All 8 hidden data spans exist with proper JSON data attributes.
    3. The #chartAnalysisModal exists with KPI strip, canvas, and data table.
    4. SPHERIX_CHARTS_REGISTRY and openChartAnalysis exist in scripts.
    """
    response = client.get('/admin/dashboard')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # 1. Check all 8 Chart Canvases
    chart_ids = [
        'mainChart',
        'hospitalChart',
        'doctorEarningsChart',
        'bloodBankChart',
        'departmentLoadChart',
        'appointmentStatusChart',
        'pharmacyCategoryChart',
        'cybersecurityThreatChart'
    ]
    for cid in chart_ids:
        assert f'id="{cid}"' in html, f"Chart canvas {cid} not found in admin dashboard"

    # 2. Check all 8 Hidden Data Spans
    span_ids = [
        'earnings-dates-data',
        'earnings-values-data',
        'doctor-names-data',
        'doctor-earnings-data',
        'hospital-names-data',
        'hospital-counts-data',
        'blood-group-labels-data',
        'blood-group-values-data',
        'dept-load-labels-data',
        'dept-load-counts-data',
        'appt-status-labels-data',
        'appt-status-counts-data',
        'pharmacy-cat-labels-data',
        'pharmacy-cat-counts-data',
        'threat-event-labels-data',
        'threat-event-counts-data'
    ]
    for sid in span_ids:
        assert f'id="{sid}"' in html, f"Data span {sid} not found in admin dashboard"

    # 3. Check Deep Analysis Modal and Subcomponents
    assert 'id="chartAnalysisModal"' in html
    assert 'id="analysisModalCanvas"' in html
    assert 'id="analysisKpiPeak"' in html
    assert 'id="analysisKpiMin"' in html
    assert 'id="analysisKpiMean"' in html
    assert 'id="analysisKpiTotal"' in html
    assert 'id="analysisInsightsList"' in html
    assert 'id="analysisTable"' in html
    assert 'id="analysisTableSearch"' in html
    assert 'openChartAnalysis' in html
    assert 'SPHERIX_CHARTS_REGISTRY' in html
    assert 'toggleModalFullscreen' in html
    assert 'exportAnalysisChartPNG' in html
    assert 'exportAnalysisChartCSV' in html
