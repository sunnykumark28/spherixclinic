import os
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_insurance_plans_images_exist_on_disk():
    """Verify that all 6 photorealistic plan images exist in static/images/insurance/."""
    expected_images = [
        'plan_term_shield.jpg',
        'plan_family_protection.jpg',
        'plan_arogya_dual.jpg',
        'plan_whole_life.jpg',
        'plan_guaranteed_savings.jpg',
        'plan_digital_eshield.jpg'
    ]
    for img_name in expected_images:
        path = os.path.join('static', 'images', 'insurance', img_name)
        assert os.path.isfile(path), f"Expected plan image {path} does not exist"
        assert os.path.getsize(path) > 10000, f"Plan image {path} is too small or corrupt"

def test_explore_plans_stacked_layout_and_images(client):
    """Verify that /patient/insurance/plans displays stacked cards with images and interactive features."""
    res = client.get('/patient/insurance/plans')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Stacked layout (one below one)
    assert 'space-y-6' in html
    assert 'plan-card' in html

    # Images referenced
    assert '/static/images/insurance/plan_term_shield.jpg' in html
    assert '/static/images/insurance/plan_family_protection.jpg' in html
    assert '/static/images/insurance/plan_arogya_dual.jpg' in html
    assert '/static/images/insurance/plan_whole_life.jpg' in html
    assert '/static/images/insurance/plan_guaranteed_savings.jpg' in html
    assert '/static/images/insurance/plan_digital_eshield.jpg' in html

    # Real-life insurance features
    assert '99.85% CSR' in html or '99.85%' in html
    assert 'IRDAI UIN:' in html
    assert 'Zero Medicals' in html or 'Zero medicals' in html
    assert '4-Hour Express' in html or '4-Hr Express' in html
    assert 'freqBtnMonthly' in html
    assert 'freqBtnAnnual' in html
    assert 'plan-price-display' in html
    assert 'togglePlanDetails' in html
    assert 'floatingCompareDock' in html
    assert 'modalCalcForm' in html

def test_explore_plans_category_filters(client):
    """Verify category filtering works smoothly."""
    res_term = client.get('/patient/insurance/plans?category=Term+Life')
    assert res_term.status_code == 200
    html = res_term.data.decode('utf-8')
    assert 'SLIC Suraksha Supreme Term Shield' in html
    assert 'SLIC Arogya Raksha Dual Health' in html
