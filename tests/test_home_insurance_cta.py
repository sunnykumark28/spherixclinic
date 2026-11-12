import pytest

def test_home_page_insurance_cta(client):
    """
    Test that home.html features:
    1. A dedicated Life Insurance CTA section (Spherix Life Insurance Corporation - SLIC).
    2. Spherix Insurance branding: 'Spherix Insurance – A Financial Protection Division of Spherix Clinic'.
    3. Direct links to explore plans, compare plans, and patient insurance portal.
    4. Key trust metrics: cashless hospital admission, sum assured, and instant quotes.
    5. The Hero section quick insurance ribbon.
    """
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Main Insurance CTA Section exists
    assert 'id="insurance-cta-section"' in html
    assert 'Spherix Life Insurance (SLIC)' in html
    assert 'Spherix Insurance &bull; A Financial Protection Division of Spherix Clinic' in html

    # 2. Value propositions
    assert 'Up to ₹2 Cr Life Cover' in html
    assert 'Cashless Hospital Admission' in html
    assert 'Instant Actuarial Quotes' in html
    assert '99.2% Claim Settlement' in html

    # 3. Action links
    assert '/patient/insurance/plans' in html
    assert '/patient/insurance/compare' in html
    assert '/patient/insurance' in html

    # 4. Hero Quick Ribbon
    assert 'Spherix Life Insurance (SLIC)' in html
    assert 'Explore Plans' in html


def test_services_dropdown_includes_insurance_tab(client):
    """
    Test that the global navigation SERVICES dropdown and mobile menu in layout.html:
    1. Contains Life Insurance (SLIC).
    2. Links to explore insurance plans, compare plans, and the insurance portal.
    3. Has active styling for insurance routes.
    """
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Desktop Services Dropdown
    assert 'SERVICES' in html
    assert 'Life Insurance (SLIC)' in html
    assert 'Financial Protection &bull; Spherix Life Insurance (SLIC)' in html
    assert '₹2 Cr Coverage' in html
    assert 'Term Life, Whole Life &amp; Family Protection' in html

    # Services links in dropdown
    assert '/patient/insurance/plans' in html
    assert '/patient/insurance/compare' in html
    assert '/patient/insurance' in html

