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

    # Stacked layout (one below one, full screen touching side)
    assert 'space-y-6' in html
    assert 'plan-card' in html
    assert 'border-x-0' in html
    assert 'max-w-7xl' not in html

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

def test_explore_plans_cta_ecosystem(client):
    """Verify the high-converting Call-To-Action (CTA) ecosystem on /patient/insurance/plans."""
    res = client.get('/patient/insurance/plans')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Main Dedicated CTA section
    assert 'id="plans-cta-section"' in html
    assert 'Speak to a Certified Life Advisor in 2 Minutes' in html
    assert '2-Min Callback Guarantee' in html
    assert '100% Spam-Free Promise' in html
    assert '15% Clinic Discount' in html
    assert 'WhatsApp Policy Bond' in html

    # 2. Direct Hotlines (Toll-Free and WhatsApp)
    assert '1800 266 8888' in html
    assert 'tel:18002668888' in html
    assert 'wa.me/9118002668888' in html

    # 3. Interactive Callback Request Form
    assert 'id="ctaCallbackForm"' in html
    assert 'id="ctaCallbackName"' in html
    assert 'id="ctaCallbackPhone"' in html
    assert 'id="ctaCallbackPlan"' in html
    assert 'id="ctaCallbackTime"' in html
    assert 'id="ctaCallbackSubmitBtn"' in html
    assert 'Request Free 2-Min Callback' in html

    # 4. In-Card Upgraded CTAs
    assert 'Apply Online Now' in html
    assert 'Zero Medicals up to ₹1.5 Cr' in html
    assert 'Speak to Advisor About This Plan' in html
    assert 'Calculate My Quote' in html

    # 5. Floating Quick-Contact Pill
    assert 'id="floatingAdvisorPill"' in html
    assert 'Free Advisor Callback' in html

def login_as_admin(client, admin_id='DOC/2026/001'):
    from spherix.models.user import Doctor
    from spherix.services.database import TEMP_DATA
    from werkzeug.security import generate_password_hash
    if 'doctors' not in TEMP_DATA:
        TEMP_DATA['doctors'] = {}
    admin = Doctor(
        id='DOC/2026/001',
        first_name='Sunny',
        last_name='Kushwaha',
        email='admin@spherixclinic.com',
        role='admin',
        department='Administration',
        password=generate_password_hash('Admin123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['doctors']['DOC/2026/001'] = admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
        sess['user_role'] = 'admin'
        sess['_user_type'] = 'admin'

def test_admin_post_new_insurance_shows_on_public_view(client):
    """Verify that when spherix clinic admin creates/posts a new insurance plan, it immediately shows on public view."""
    login_as_admin(client)

    # 1. Admin accesses console products tab
    res_admin = client.get('/admin/insurance/console?tab=products')
    assert res_admin.status_code == 200
    html_admin = res_admin.data.decode('utf-8')
    assert 'Post New Insurance Plan' in html_admin
    assert 'postPlanModal' in html_admin

    # 2. Admin posts a brand new plan
    new_plan_name = "SLIC AyurRaksha Special Life Protection"
    post_data = {
        'product_name': new_plan_name,
        'partner_id': 'INS-PARTNER-SLIC',
        'category': 'Term Life',
        'uin_number': 'SLIC101N999V01',
        'tagline': 'Integrates clinical wellness and full-spectrum financial security.',
        'base_annual_rate_per_lakh': '8.80',
        'min_sum_insured': '2500000',
        'max_sum_insured': '50000000',
        'default_sum_insured': '10000000',
        'min_term_years': '10',
        'max_term_years': '40',
        'min_entry_age': '18',
        'max_entry_age': '65',
        'key_benefits': 'Direct cashless settlement\nWellness premium discounts up to 15%',
        'exclusions': 'Standard suicide exclusion within 1 year',
        'image_url': '/static/images/insurance/plan_term_shield.jpg',
        'is_featured': '1'
    }
    res_post = client.post('/admin/insurance/product/new', data=post_data, follow_redirects=True)
    assert res_post.status_code == 200

    # 3. Verify public view immediately displays the new insurance plan
    res_public = client.get('/patient/insurance/plans')
    assert res_public.status_code == 200
    public_html = res_public.data.decode('utf-8')
    assert new_plan_name in public_html
    assert 'SLIC101N999V01' in public_html
    assert 'Integrates clinical wellness' in public_html

def test_all_insurance_templates_full_screen(client):
    """Verify that all insurance pages have removed max-w-7xl and use full-screen architecture."""
    pages = [
        '/patient/insurance/plans',
        '/patient/insurance/hub',
        '/patient/insurance/compare'
    ]
    for page in pages:
        res = client.get(page)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'max-w-7xl' not in html, f"Page {page} still has max-w-7xl"

    # Also verify admin console is full-screen
    login_as_admin(client)
    res_admin = client.get('/admin/insurance/console')
    assert res_admin.status_code == 200
    html_admin = res_admin.data.decode('utf-8')
    assert 'max-w-7xl' not in html_admin

def test_admin_insurance_console_admin_layout_and_slide_over_sidebar(client):
    """Verify that /admin/insurance/console uses the Admin Layout and slide-over sidebar drawer for posting plans."""
    login_as_admin(client)

    # 1. Main console in admin layout
    res = client.get('/admin/insurance/console')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Must extend dashboard_layout and render admin sidebar
    assert 'class="sidebar" id="sidebar"' in html
    assert 'class="top-header"' in html
    assert 'Life Insurance Console' in html
    assert 'nav-item active' in html
    assert 'toggleSidebar()' in html
    assert 'admin-dashboard-shell' in html

    # Slide-over sidebar drawer for posting new plan
    assert 'id="postPlanSidebar"' in html
    assert 'id="postPlanDrawerOverlay"' in html
    assert 'openPostPlanSidebar()' in html
    assert 'closePostPlanSidebar()' in html
    assert 'action="/admin/insurance/product/new"' in html
    assert "urlParams.get('action') === 'new_plan'" in html

    # Test tabs rendering
    for tab in ['overview', 'partners', 'products', 'applications', 'policies', 'audit']:
        res_tab = client.get(f'/admin/insurance/console?tab={tab}')
        assert res_tab.status_code == 200
        html_tab = res_tab.data.decode('utf-8')
        assert 'class="sidebar" id="sidebar"' in html_tab
        assert 'id="postPlanSidebar"' in html_tab

