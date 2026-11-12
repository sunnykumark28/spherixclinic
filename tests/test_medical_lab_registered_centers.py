import pytest
from app import app
from spherix.services.diagnostic_db import get_diagnostic_db, init_diagnostic_schema

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            init_diagnostic_schema()
        yield client

def test_diagnostic_centers_directory_shows_only_registered_and_no_duplicates(client):
    """Verifies that /diagnostic/centers shows only registered pathology centers and never shows duplicates."""
    res = client.get('/diagnostic/centers')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Shows Registered badge
    assert 'Registered Pathology Center' in html
    assert 'Spherix Central Reference Diagnostics' in html
    assert 'Spherix Regional Clinical Laboratory' in html

    # Unregistered foreign demo lab is NOT shown
    assert 'Apex Global Diagnostics' not in html

    # Area pills for genuine registered locations exist
    assert 'Motihari' in html
    assert 'New Delhi' in html
    assert 'New York' not in html

    # Verify no duplicates exist in rendered directory cards
    assert html.count('href="/diagnostic/centers/LAB-DELHI-001"') == 1
    assert html.count('href="/diagnostic/centers/LAB-BIHAR-002"') == 1

def test_diagnostic_centers_deduplication_safeguard(client):
    """Verifies that if duplicate center records exist in DB, they are deduplicated in the directory."""
    conn = get_diagnostic_db()
    cur = conn.cursor()
    # Insert a duplicate center with the same facility name & city but different ID
    cur.execute("""
    INSERT INTO pathology_centers (
        id, organization_id, center_name, branch_name, email, phone,
        address, city, state_province, postal_code, country,
        verification_status, is_active
    ) VALUES (
        'LAB-DUP-001', 'ORG-SPX-CENTRAL', 'Spherix Central Reference Diagnostics', 'Branch 2', 'dup@spherixclinic.com', '9999999999',
        'Duplicate Address', 'New Delhi', 'Delhi', '110001', 'India',
        'VERIFIED', 1
    )
    """)
    conn.commit()
    conn.close()

    try:
        res = client.get('/diagnostic/centers')
        assert res.status_code == 200
        html = res.data.decode('utf-8')

        # The facility should appear only once (the duplicate ID is not rendered)
        assert html.count('href="/diagnostic/centers/LAB-DELHI-001"') == 1
        assert 'href="/diagnostic/centers/LAB-DUP-001"' not in html
    finally:
        conn = get_diagnostic_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM pathology_centers WHERE id = 'LAB-DUP-001'")
        conn.commit()
        conn.close()

def test_medical_lab_landing_section_and_area_pills(client):
    """Verifies Section 6 on /medical-lab loads registered centers and area pills without duplicates."""
    res = client.get('/medical-lab')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Section 6 exists with anchor id
    assert 'id="pathology-centers-section"' in html
    assert 'Pathology Centers in Selected Area' in html

    # Area pills container exists
    assert 'id="pathologyAreaPillsContainer"' in html
    assert 'id="pathologyCentersGrid"' in html

    # Area pills for registered cities are present
    assert 'Motihari' in html
    assert 'New Delhi' in html
    assert 'New York' not in html

    # Links preserve medical-lab endpoint and jump to #pathology-centers-section
    assert 'href="/medical-lab#pathology-centers-section"' in html
    assert 'href="/medical-lab?city=Motihari#pathology-centers-section"' in html

    # Registered center cards rendered without duplicates
    assert html.count('href="/diagnostic/centers/LAB-DELHI-001"') == 1
    assert html.count('href="/diagnostic/centers/LAB-BIHAR-002"') == 1

def test_medical_lab_city_filter_motihari(client):
    """Verifies that selecting Motihari displays the Motihari center and marks non-matching hidden."""
    res = client.get('/medical-lab?city=Motihari')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Motihari card is visible (does not have hidden class)
    assert 'data-city="motihari"' in html
    motihari_part = [s for s in html.split('<div data-city="motihari"') if len(s) > 1]
    assert len(motihari_part) > 1
    card_header = motihari_part[1].split('>')[0]
    assert 'hidden' not in card_header

    # Other cards have 'hidden' class
    delhi_part = [s for s in html.split('<div data-city="new delhi"') if len(s) > 1]
    assert len(delhi_part) > 1
    assert 'hidden' in delhi_part[1].split('>')[0]

    # Motihari pill is active
    assert 'data-area="motihari"' in html

def test_unverified_or_inactive_centers_are_excluded(client):
    """Verifies that unverified or inactive centers do not appear in registered areas or centers."""
    conn = get_diagnostic_db()
    cur = conn.cursor()
    
    # Insert an unverified center and an inactive center
    cur.execute("""
    INSERT INTO pathology_centers (
        id, organization_id, center_name, branch_name, email, phone,
        address, city, state_province, postal_code, country,
        verification_status, is_active
    ) VALUES (
        'LAB-FAKE-001', 'ORG-SPX-CENTRAL', 'Fake Unverified Center', 'Test', 'unverified@test.com', '9999999999',
        'Test Address', 'GhostCity', 'GhostState', '000000', 'India',
        'PENDING_VERIFICATION', 1
    )
    """)
    cur.execute("""
    INSERT INTO pathology_centers (
        id, organization_id, center_name, branch_name, email, phone,
        address, city, state_province, postal_code, country,
        verification_status, is_active
    ) VALUES (
        'LAB-FAKE-002', 'ORG-SPX-CENTRAL', 'Fake Inactive Center', 'Test', 'inactive@test.com', '9999999999',
        'Test Address', 'InactiveCity', 'InactiveState', '000000', 'India',
        'VERIFIED', 0
    )
    """)
    conn.commit()
    conn.close()

    try:
        from spherix.routes.diagnostic import get_registered_areas
        areas = get_registered_areas()
        area_names = [a['city'] for a in areas]
        assert 'GhostCity' not in area_names
        assert 'InactiveCity' not in area_names

        res = client.get('/diagnostic/centers')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'Fake Unverified Center' not in html
        assert 'Fake Inactive Center' not in html
    finally:
        # Clean up inserted test rows
        conn = get_diagnostic_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM pathology_centers WHERE id IN ('LAB-FAKE-001', 'LAB-FAKE-002')")
        conn.commit()
        conn.close()
