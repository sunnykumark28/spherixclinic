import pytest
import json
import sqlite3
from app import app
from spherix.services.insurance_db import (
    init_insurance_schema,
    get_all_insurance_products,
    get_insurance_product_by_id,
    calculate_life_insurance_quotation,
    get_patient_insurance_policies,
    get_patient_insurance_applications,
    get_insurance_db,
    save_insurance_application_draft,
    submit_insurance_application,
    issue_verified_policy_for_application
)
from spherix.services.insurance_integration import get_insurer_adapter
from spherix.models.user import Doctor, Patient
from spherix.services.database import TEMP_DATA
from werkzeug.security import generate_password_hash

def setup_test_users():
    if 'patients' not in TEMP_DATA:
        TEMP_DATA['patients'] = {}
    if 'doctors' not in TEMP_DATA:
        TEMP_DATA['doctors'] = {}

    pat = Patient(
        id='PAT/2026/001',
        name='Sunny Kumar',
        email='sunny28skk@gmail.com',
        phone='9876543210',
        password=generate_password_hash('Patient123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['patients']['PAT/2026/001'] = pat

    pat2 = Patient(
        id='PAT/2026/999',
        name='Intruder Patient',
        email='intruder@gmail.com',
        phone='9876543299',
        password=generate_password_hash('Patient123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA['patients']['PAT/2026/999'] = pat2

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

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    setup_test_users()
    with app.test_client() as client:
        with app.app_context():
            init_insurance_schema()
        yield client

def login_as_patient(client, patient_id='PAT/2026/001'):
    setup_test_users()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(patient_id)
        sess['_fresh'] = True
        sess['user_role'] = 'patient'
        sess['_user_type'] = 'patient'

def login_as_admin(client, admin_id='DOC/2026/001'):
    setup_test_users()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
        sess['user_role'] = 'admin'
        sess['_user_type'] = 'admin'

def test_01_insurance_schema_and_seed_partners(client):
    """Verifies that insurance schema initializes and seeds Spherix Life Insurance Corporation (SLIC) as the sole underwriter."""
    products = get_all_insurance_products()
    assert len(products) >= 6

    # Verify Spherix Life Insurance Corporation (SLIC) is the sole authorized underwriter
    insurers = {p['insurer_name'] for p in products}
    assert any('SLIC' in name or 'Spherix Life' in name for name in insurers)
    assert all('SLIC' in p['insurer_name'] or 'Spherix Life' in p['insurer_name'] for p in products)

    # Check valid UIN format and CSR ratios
    for p in products:
        assert 'SLIC' in p['uin']
        assert p['uin_number'].startswith('SLIC')
        assert p['claim_settlement_ratio'] >= 99.0

def test_02_actuarial_quotation_engine(client):
    """Verifies the quotation engine accurately calculates age factors, term factors, smoker surcharges, and statutory GST."""
    # 30-year old non-smoker, 1 Crore cover, 30-year term
    quote_healthy = calculate_life_insurance_quotation(
        product_id='PROD-HDFC-CLICK2PROTECT',
        age=30,
        gender='male',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        is_smoker=False
    )
    assert quote_healthy['base_premium'] > 0
    assert quote_healthy['annual_gst'] == round(quote_healthy['annual_net_premium'] * 0.18, 2)
    assert quote_healthy['total_periodic_premium'] > 0

    # Smoker surcharge verification
    quote_smoker = calculate_life_insurance_quotation(
        product_id='PROD-HDFC-CLICK2PROTECT',
        age=30,
        gender='male',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        is_smoker=True
    )
    assert quote_smoker['annual_net_premium'] > quote_healthy['annual_net_premium']

    # Older age surcharge verification (50 yrs vs 30 yrs)
    quote_older = calculate_life_insurance_quotation(
        product_id='PROD-HDFC-CLICK2PROTECT',
        age=50,
        gender='male',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        is_smoker=False
    )
    assert quote_older['annual_net_premium'] > quote_healthy['annual_net_premium']

    # API endpoint test
    res = client.post('/api/insurance/quote', json={
        'product_id': 'PROD-ICICI-IPROTECT',
        'age': 32,
        'gender': 'female',
        'sum_insured': 15000000,
        'policy_term_years': 25,
        'premium_frequency': 'MONTHLY',
        'is_smoker': False
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'quote' in data
    assert data['quote']['premium_frequency'] == 'MONTHLY'

def test_03_patient_dashboard_sidebar_and_tab_integration(client):
    """Verifies that patient dashboard includes all 10 requested navigation items and the tab-insurance section."""
    login_as_patient(client, 'PAT/2026/001')
    res = client.get('/patient/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # All 10 navigation items
    assert 'Life Insurance' in html
    assert 'Explore Insurance Plans' in html
    assert 'Compare Plans' in html
    assert 'Apply for Insurance' in html
    assert 'My Applications' in html
    assert 'My Insurance Policies' in html
    assert 'Premium Payments' in html
    assert 'Claims Assistance' in html
    assert 'Insurance Documents' in html
    assert 'Insurance Support' in html

    # Tab section and division branding
    assert 'id="tab-insurance"' in html
    assert 'Spherix Insurance' in html
    assert 'A Financial Protection Division of Spherix Clinic' in html

    # Header quick-access dropdown verification
    assert 'headerInsuranceDropdown' in html
    assert 'SLIC Insurance' in html
    assert '99.85% CSR' in html

def test_04_marketplace_catalog_and_plan_details(client):
    """Verifies /patient/insurance, /patient/insurance/plans, and brochure downloads."""
    login_as_patient(client, 'PAT/2026/001')
    res = client.get('/patient/insurance')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Spherix Insurance' in html
    assert 'SLIC' in html or 'Spherix Life Insurance Corporation' in html

    # Plans Catalog
    res_plans = client.get('/patient/insurance/plans')
    assert res_plans.status_code == 200
    html_plans = res_plans.data.decode('utf-8')
    assert 'SLIC Suraksha Supreme Term Shield' in html_plans
    assert 'SLIC Parivar Smart Protection Shield' in html_plans
    assert 'SLIC Jeevan Amrit Whole Life Cover' in html_plans
    assert 'SLIC Bhavishya Dhan Guaranteed Savings Plan' in html_plans
    assert 'IRDAI UIN:' in html_plans
    assert 'SLIC101N001V01' in html_plans

def test_05_plan_comparison_matrix(client):
    """Verifies /patient/insurance/compare renders side-by-side comparison matrix with clear illustrative estimates notice."""
    login_as_patient(client, 'PAT/2026/001')
    res = client.get('/patient/insurance/compare?p1=PROD-SLIC-SHIELD&p2=PROD-SLIC-PARIVAR')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Plan Comparison Matrix' in html or 'Comparison Matrix' in html
    assert 'illustrative' in html.lower()
    assert 'confirmed' in html.lower()
    assert 'SLIC' in html
    assert 'Claim Settlement Ratio' in html

def test_06_multi_step_proposal_draft_and_save(client):
    """Verifies proposal draft creation, updates, and persistence."""
    login_as_patient(client, 'PAT/2026/001')

    # Step 1: Initialize draft
    res_wizard = client.get('/patient/insurance/apply?plan_id=PROD-HDFC-CLICK2PROTECT')
    assert res_wizard.status_code == 200
    html = res_wizard.data.decode('utf-8')
    assert 'Step 1: Personal' in html
    assert 'Step 2: Life Coverage' in html
    assert 'Step 3: Designated Nominee' in html
    assert 'Step 4: Statutory Health' in html
    assert 'Step 5: KYC Verification' in html
    assert 'Step 6: Review Proposal' in html

    # Save draft via API / form
    app_id = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-HDFC-CLICK2PROTECT',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        quoted_premium=9500.0,
        applicant_data={
            'first_name': 'Sunny',
            'last_name': 'Kumar',
            'email': 'sunny28skk@gmail.com',
            'phone': '9876543210',
            'dob': '1995-05-15',
            'gender': 'male',
            'annual_income': 1500000,
            'occupation': 'Salaried'
        },
        nominee_data={
            'nominee_name': 'Anita Kumar',
            'relationship': 'Spouse',
            'nominee_dob': '1996-08-20',
            'nominee_phone': '9876543211',
            'share_pct': 100
        },
        declarations={
            'is_smoker': False,
            'has_pre_existing': False,
            'statutory_consent': True
        }
    )
    assert app_id.startswith('APP-SPX-')

    # Verify retrieved in patient applications
    apps = get_patient_insurance_applications('PAT/2026/001')
    match = next((a for a in apps if a['id'] == app_id), None)
    assert match is not None
    assert match['status'] == 'DRAFT'

def test_07_underwriting_decision_and_status_sync(client):
    """Verifies that submitting an application engages the insurer underwriting adapter.
    Healthy proposals are APPROVED / PAYMENT_PENDING; proposals with severe conditions require review.
    """
    login_as_patient(client, 'PAT/2026/001')

    # Case A: Standard healthy application
    app_id_clean = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-MAX-SMART-WEALTH',
        sum_insured=10000000,
        policy_term_years=25,
        premium_frequency='ANNUAL',
        quoted_premium=12000.0,
        applicant_data={'first_name': 'Sunny', 'last_name': 'Kumar', 'email': 'sunny@test.com', 'dob': '1995-01-01', 'gender': 'male'},
        nominee_data={'nominee_name': 'Anita Kumar', 'relationship': 'Spouse'},
        declarations={'has_pre_existing': False, 'statutory_consent': True}
    )
    res_submit = submit_insurance_application(app_id_clean)
    assert res_submit['status'] in ['APPROVED', 'PAYMENT_PENDING']
    assert res_submit['insurer_decision'] in ['ACCEPTED', 'STANDARD_ACCEPTANCE']

    # Case B: Proposal with declared critical illness
    app_id_risk = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-TATA-SAMPOORNA',
        sum_insured=20000000,
        policy_term_years=35,
        premium_frequency='ANNUAL',
        quoted_premium=18000.0,
        applicant_data={'first_name': 'Sunny', 'last_name': 'Kumar', 'email': 'sunny@test.com', 'dob': '1990-01-01', 'gender': 'male'},
        nominee_data={'nominee_name': 'Anita Kumar', 'relationship': 'Spouse'},
        declarations={'has_pre_existing': True, 'condition_details': 'Cardiac Surgery 2024', 'statutory_consent': True}
    )
    res_submit_risk = submit_insurance_application(app_id_risk)
    assert res_submit_risk['status'] in ['UNDER_REVIEW', 'ADDITIONAL_INFO_REQUIRED']

def test_08_payment_verification_and_policy_issuance(client):
    """Verifies server-side payment token verification and cryptographic policy issuance."""
    login_as_patient(client, 'PAT/2026/001')

    # Create approved application ready for payment
    app_id = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-ICICI-IPROTECT',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        quoted_premium=8400.0,
        applicant_data={'first_name': 'Sunny', 'last_name': 'Kumar', 'email': 'sunny@test.com', 'dob': '1995-01-01', 'gender': 'male'},
        nominee_data={'nominee_name': 'Anita Kumar', 'relationship': 'Spouse'},
        declarations={'has_pre_existing': False, 'statutory_consent': True}
    )
    submit_insurance_application(app_id)

    # Issue policy via verified payment
    res_issue = issue_verified_policy_for_application(
        application_id=app_id,
        payment_ref='TXN-TEST-GATEWAY-001',
        amount_paid=8400.0,
        payment_method='UPI'
    )
    assert res_issue['success'] is True
    policy_id = res_issue['policy_id']
    policy_num = res_issue['policy_number']
    assert policy_num.startswith('SLIC-POL-2026-')

    # Verify policy in patient list
    policies = get_patient_insurance_policies('PAT/2026/001')
    match_pol = next((p for p in policies if p['id'] == policy_id), None)
    assert match_pol is not None
    assert match_pol['status'] == 'ACTIVE'
    assert match_pol['verification_hash'] != ''
    assert len(match_pol['verification_hash']) == 64  # SHA256 length

def test_09_official_policy_document_rendering(client):
    """Verifies that the policy certificate schedule renders properly with legal disclaimers and cryptographic seal."""
    login_as_patient(client, 'PAT/2026/001')

    # Create & issue a policy
    app_id = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-HDFC-CLICK2PROTECT',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        quoted_premium=9500.0,
        applicant_data={'first_name': 'Sunny', 'last_name': 'Kumar', 'email': 'sunny@test.com'},
        nominee_data={'nominee_name': 'Anita Kumar', 'relationship': 'Spouse'}
    )
    submit_insurance_application(app_id)
    res_issue = issue_verified_policy_for_application(app_id, 'TXN-DOC-001', 9500.0, 'NETBANKING')
    policy_id = res_issue['policy_id']

    # Request document
    res_doc = client.get(f'/patient/insurance/policies/{policy_id}/document')
    assert res_doc.status_code == 200
    html_doc = res_doc.data.decode('utf-8')
    assert 'CERTIFICATE OF LIFE INSURANCE SCHEDULE' in html_doc
    assert 'Spherix Insurance' in html_doc
    assert 'CRYPTOGRAPHIC VERIFICATION SEAL' in html_doc
    assert res_issue['policy_number'] in html_doc
    assert 'Section 45 of Insurance Act' in html_doc

def test_10_strict_patient_data_isolation(client):
    """Verifies that Patient A cannot view, modify, or download documents belonging to Patient B."""
    # Create policy for Patient 1
    app_p1 = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-HDFC-CLICK2PROTECT',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        quoted_premium=9500.0,
        applicant_data={'first_name': 'Sunny'},
        nominee_data={'nominee_name': 'Anita'}
    )
    submit_insurance_application(app_p1)
    res_p1 = issue_verified_policy_for_application(app_p1, 'TXN-P1-001', 9500.0, 'CARD')
    pol_id_p1 = res_p1['policy_id']

    # Log in as a different patient: 'PAT/2026/999'
    login_as_patient(client, 'PAT/2026/999')

    # Attempt to view Patient 1's application detail -> must redirect with flash error
    res_app_intrude = client.get(f'/patient/insurance/applications/{app_p1}', follow_redirects=True)
    assert b"Unauthorized access" in res_app_intrude.data or res_app_intrude.status_code in [302, 403]

    # Attempt to view Patient 1's policy detail -> must be blocked
    res_pol_intrude = client.get(f'/patient/insurance/policies/{pol_id_p1}', follow_redirects=True)
    assert b"Unauthorized access" in res_pol_intrude.data or res_pol_intrude.status_code in [302, 403]

    # Attempt to download Patient 1's document -> must be blocked
    res_doc_intrude = client.get(f'/patient/insurance/policies/{pol_id_p1}/document', follow_redirects=True)
    assert b"Unauthorized access" in res_doc_intrude.data or res_doc_intrude.status_code in [302, 403]

def test_11_claims_assistance_workflow(client):
    """Verifies claims assistance filing, registration, and hospital coordinator assignment."""
    login_as_patient(client, 'PAT/2026/001')

    # Issue policy
    app_id = save_insurance_application_draft(
        patient_id='PAT/2026/001',
        product_id='PROD-HDFC-CLICK2PROTECT',
        sum_insured=10000000,
        policy_term_years=30,
        premium_frequency='ANNUAL',
        quoted_premium=9500.0
    )
    submit_insurance_application(app_id)
    res_issue = issue_verified_policy_for_application(app_id, 'TXN-CLM-001', 9500.0, 'UPI')
    policy_id = res_issue['policy_id']

    # File claim request
    res_post_claim = client.post('/patient/insurance/claims/request', data={
        'policy_id': policy_id,
        'claim_type': 'CRITICAL_ILLNESS',
        'event_date': '2026-03-01',
        'hospital_name': 'Spherix Super Specialty Hospital',
        'estimated_amount': '250000',
        'claim_description': 'Acute hospital admission for cardiac observation.'
    }, follow_redirects=True)
    assert res_post_claim.status_code == 200
    html_claim = res_post_claim.data.decode('utf-8')
    assert 'Claim assistance' in html_claim or 'CLM-' in html_claim or 'SPX-CLM-' in html_claim

def test_12_insurance_support_portal(client):
    """Verifies 3-tier support portal with partner GROs, IRDAI Bima Bharosa and Spherix desk."""
    login_as_patient(client, 'PAT/2026/001')
    res = client.get('/patient/insurance/support')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Spherix Insurance' in html or 'Insurance' in html
    assert 'IRDAI' in html
    assert '155255' in html  # IRDAI toll-free helpline

def test_13_admin_role_security_and_console(client):
    """Verifies that non-admins cannot access /admin/insurance, and admins can access and view the audit log and policy registry."""
    # 1. Non-admin patient is blocked
    login_as_patient(client, 'PAT/2026/001')
    res_unauth = client.get('/admin/insurance', follow_redirects=False)
    assert res_unauth.status_code in [302, 403]

    # 2. Admin can access
    login_as_admin(client, 'DOC/2026/001')
    res_admin = client.get('/admin/insurance')
    assert res_admin.status_code == 200
    html_admin = res_admin.data.decode('utf-8')
    assert 'Spherix Insurance' in html_admin
    assert 'Console' in html_admin
    assert 'Audit Trail' in html_admin
    assert 'Partner Insurers' in html_admin
