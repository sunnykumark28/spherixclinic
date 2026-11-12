import pytest
from werkzeug.security import generate_password_hash
from spherix import create_app
from spherix.models import Hospital
from spherix.services.database import TEMP_DATA

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            hosp_id = 'HPT/2026/001'
            default_pass = generate_password_hash('Hospital@123', method='pbkdf2:sha256:260000')
            TEMP_DATA['hospitals'][hosp_id] = Hospital(
                id=hosp_id,
                name='Spherix Apex Super Specialty Hospital',
                email='hospital.settings.test@spherixclinic.com',
                password=default_pass,
                total_beds=250,
                available_beds=80,
                icu_beds=35,
                available_icu_beds=10,
                general_beds=150,
                available_general_beds=50,
                private_beds=50,
                available_private_beds=15,
                nicu_beds=15,
                available_nicu_beds=5,
                picu_beds=10,
                available_picu_beds=3,
                emergency_beds=20,
                available_emergency_beds=8,
                operation_theatres=8,
                available_ot=2,
                consultation_fee=850.0,
                follow_up_fee=400.0,
                general_bed_fee=1200.0,
                private_bed_fee=3500.0,
                icu_bed_fee=4000.0,
                emergency_bed_fee=1800.0,
                ot_fee=7500.0,
                admission_charge=600.0,
                ambulance_fee=1500.0,
                address='Plot 44, Institutional Healthcare Zone',
                city='New Delhi',
                state='Delhi',
                zip_code='110029',
                country='India',
                is_verified=True,
                publishing_status='published',
                blood_bank_available=True,
                blood_stock={"A+": 15, "A-": 6, "B+": 20, "B-": 5, "AB+": 10, "AB-": 3, "O+": 25, "O-": 8},
                ambulance_services=True,
                ambulance_count=4,
                pharmacy_available=True,
                pharmacy_hours='24/7 Round the Clock',
                emergency_services=True,
                emergency_phone='+91 11 2658 9911',
                ambulance_phone='+91 11 2658 9922',
                patient_support_phone='+91 11 2658 9933',
                patient_support_email='care@spherixapex.com',
                website='https://apex.spherixclinic.com',
                infrastructure='Centralized PSA Oxygen Plant, 100% DG Backup, HEPA HVAC, CSSD Unit',
                medical_equipment='3T Digital MRI, 128-Slice Dual Source CT, Biplane Cath Lab, Dialysis',
                diagnostic_services='Digital X-Ray, 4D USG, Color Doppler, Echocardiography',
                laboratory_facilities='Automated Biochemistry, PCR Molecular Lab, Histopathology',
                insurance_cashless='Star Health, HDFC ERGO, ICICI Lombard, Ayushman Bharat PM-JAY',
                certifications='ISO 9001:2015, Green OT Certified, AERB Compliant',
                accreditation='NABH / JCI Accredited',
                visiting_hours='Morning: 10:00 AM - 12:00 PM | Evening: 05:00 PM - 07:00 PM',
                patient_guidelines='Government photo ID and active health insurance card required for cashless admission.',
                social_links={'facebook': 'https://facebook.com/spherixapex', 'twitter': 'https://twitter.com/spherixapex', 'linkedin': 'https://linkedin.com/company/spherixapex'},
                gallery_urls='https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d, https://images.unsplash.com/photo-1586773860418-d37222d8fce3',
                video_urls='https://www.youtube.com/watch?v=hospital-tour-2026'
            )
            yield client

def test_hospital_dashboard_settings_html_contains_all_sections(client):
    """Verifies that hospital settings display and edit modes expose all expected fields and sub-tabs."""
    hosp_id = 'HPT/2026/001'
    with client.session_transaction() as sess:
        sess['_user_id'] = f"hospital-{hosp_id}"
        sess['_fresh'] = True

    resp = client.get('/hospital/dashboard')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # Sub-tabs navigation buttons
    assert "Hospital Profile" in html
    assert "Branding &amp; Media" in html or "Branding & Media" in html
    assert "Ward &amp; Bed Capacity" in html or "Ward & Bed Capacity" in html
    assert "Clinical &amp; Specialties" in html or "Clinical & Specialties" in html
    assert "Infrastructure &amp; Labs" in html or "Infrastructure & Labs" in html
    assert "Rate Card &amp; TPAs" in html or "Rate Card & TPAs" in html
    assert "Emergency &amp; Blood" in html or "Emergency & Blood" in html
    assert "Policies, Hours &amp; FAQs" in html or "Policies, Hours & FAQs" in html
    assert "Social Presence" in html
    assert "Security &amp; Password" in html or "Security & Password" in html

    # Essential display cards
    assert "Hospital Identity &amp; Governance" in html or "Hospital Identity & Governance" in html
    assert "Contact Coordinates, Helplines &amp; Geolocation" in html or "Contact Coordinates" in html
    assert "Inpatient Ward Bed Inventory &amp; Operating Theatres" in html or "Ward Bed Inventory" in html
    assert "Blood Bank Component Reserves" in html or "Live Blood Bank Stock" in html
    assert "Campus Photo Gallery" in html
    assert "Hospital Video Tours" in html
    assert "Frequently Asked Questions" in html
    assert "Empanelled Cashless Insurance &amp; TPAs" in html or "Cashless Insurance" in html

    # Form inputs for all 40+ attributes in Edit Mode
    assert 'name="name"' in html
    assert 'name="hospital_type_id"' in html
    assert 'name="establishment_year"' in html
    assert 'name="license_number"' in html
    assert 'name="president_ceo"' in html
    assert 'name="superintendent_name"' in html
    assert 'name="email"' in html
    assert 'name="phone"' in html
    assert 'name="emergency_phone"' in html
    assert 'name="ambulance_phone"' in html
    assert 'name="patient_support_phone"' in html
    assert 'name="patient_support_email"' in html
    assert 'name="address"' in html
    assert 'name="city"' in html
    assert 'name="state"' in html
    assert 'name="country"' in html
    assert 'name="zip_code"' in html
    assert 'name="google_maps_url"' in html
    assert 'name="latitude"' in html
    assert 'name="longitude"' in html
    assert 'name="departments_custom"' in html
    assert 'name="specialties_csv"' in html
    assert 'name="general_beds"' in html
    assert 'name="available_general_beds"' in html
    assert 'name="private_beds"' in html
    assert 'name="available_private_beds"' in html
    assert 'name="icu_beds"' in html
    assert 'name="available_icu_beds"' in html
    assert 'name="nicu_beds"' in html
    assert 'name="available_nicu_beds"' in html
    assert 'name="picu_beds"' in html
    assert 'name="available_picu_beds"' in html
    assert 'name="emergency_beds"' in html
    assert 'name="available_emergency_beds"' in html
    assert 'name="operation_theatres"' in html
    assert 'name="available_ot"' in html
    assert 'name="consultation_fee"' in html
    assert 'name="follow_up_fee"' in html
    assert 'name="general_bed_fee"' in html
    assert 'name="private_bed_fee"' in html
    assert 'name="icu_bed_fee"' in html
    assert 'name="emergency_bed_fee"' in html
    assert 'name="ot_fee"' in html
    assert 'name="admission_charge"' in html
    assert 'name="ambulance_fee"' in html
    assert 'name="insurance_cashless"' in html
    assert 'name="emergency_services"' in html
    assert 'name="blood_bank_available"' in html
    assert 'name="blood_stock_Apos"' in html
    assert 'name="blood_stock_Bpos"' in html
    assert 'name="blood_stock_Opos"' in html
    assert 'name="pharmacy_available"' in html
    assert 'name="pharmacy_hours"' in html
    assert 'name="ambulance_services"' in html
    assert 'name="ambulance_count"' in html
    assert 'name="visiting_hours"' in html
    assert 'name="patient_guidelines"' in html
    assert 'name="social_facebook"' in html
    assert 'name="social_twitter"' in html
    assert 'name="social_linkedin"' in html
    assert 'name="social_youtube"' in html
    assert 'name="social_instagram"' in html
    assert 'name="publishing_status"' in html

def test_hospital_settings_full_profile_update_and_sync(client):
    """Submits the complete settings form and verifies all fields persist to database and public view."""
    hosp_id = 'HPT/2026/001'
    hosp = TEMP_DATA['hospitals'][hosp_id]

    with client.session_transaction() as sess:
        sess['_user_id'] = f"hospital-{hosp_id}"
        sess['_fresh'] = True

    payload = {
        'update_profile': '1',
        'name': 'Spherix Global Medical Center',
        'email': hosp.email,
        'phone': '+91 11 2658 1111',
        'emergency_phone': '+91 11 2658 2222',
        'ambulance_phone': '+91 11 2658 3333',
        'patient_support_phone': '+91 11 2658 4444',
        'patient_support_email': 'support@spherixglobal.com',
        'website': 'https://global.spherixclinic.com',
        'establishment_year': '2005',
        'about': 'Premier global medical destination dedicated to clinical excellence and compassionate healing.',
        'address': 'Main Diplomatic Enclave, Chanakyapuri',
        'city': 'New Delhi',
        'state': 'Delhi',
        'zip_code': '110021',
        'country': 'India',
        'departments_custom': 'Cardiothoracic Surgery, Interventional Oncology, Pediatric Neurology, Organ Transplant',
        'specialties_csv': 'Cardiology, Oncology, Neurosurgery, Nephrology, Orthopedics',
        'infrastructure': 'Central Oxygen PSA Plant, Dual DG Generator Backup, Class 100 Laminar OT Suites',
        'medical_equipment': '3 Tesla MRI, 256-Slice Dual CT, Da Vinci Xi Robot, ECMO Unit',
        'diagnostic_services': 'Full Body PET-CT, 4D Ultrasound, Digital Fluoroscopy, Endoscopic Ultrasound',
        'laboratory_facilities': 'NABL-Accredited Molecular Diagnostic Lab, Flow Cytometry, Automated Biochemistry',
        'general_beds': '220',
        'available_general_beds': '45',
        'private_beds': '70',
        'available_private_beds': '12',
        'icu_beds': '40',
        'available_icu_beds': '8',
        'nicu_beds': '15',
        'available_nicu_beds': '5',
        'picu_beds': '10',
        'available_picu_beds': '3',
        'emergency_beds': '25',
        'available_emergency_beds': '7',
        'operation_theatres': '12',
        'available_ot': '4',
        'consultation_fee': '900',
        'follow_up_fee': '450',
        'general_bed_fee': '1600',
        'private_bed_fee': '4200',
        'icu_bed_fee': '4500',
        'emergency_bed_fee': '2000',
        'ot_fee': '8000',
        'admission_charge': '700',
        'ambulance_fee': '1800',
        'insurance_cashless': 'Star Health, HDFC ERGO, ICICI Lombard, Ayushman Bharat PM-JAY, Medi Assist, Max Bupa',
        'emergency_services': 'on',
        'blood_bank_available': 'on',
        'blood_stock_Apos': '22',
        'blood_stock_Aneg': '8',
        'blood_stock_Bpos': '30',
        'blood_stock_Bneg': '7',
        'blood_stock_ABpos': '14',
        'blood_stock_ABneg': '4',
        'blood_stock_Opos': '40',
        'blood_stock_Oneg': '12',
        'pharmacy_available': 'on',
        'pharmacy_hours': '24/7 Round the Clock',
        'ambulance_services': 'on',
        'ambulance_count': '6',
        'international_bed_booking_enabled': 'on',
        'international_services_csv': 'Medical Visa Assistance, Airport Transfer, Multi-Language Translators, VIP International Patient Suites',
        'visiting_hours': 'Morning: 10:00 AM - 12:00 PM | Evening: 05:00 PM - 07:00 PM',
        'patient_guidelines': 'Valid photo identity card and cashless TPA insurance e-card mandatory at admission.',
        'social_facebook': 'https://facebook.com/spherixglobal',
        'social_twitter': 'https://x.com/spherixglobal',
        'social_linkedin': 'https://linkedin.com/company/spherixglobal',
        'social_youtube': 'https://youtube.com/@spherixglobal',
        'social_instagram': 'https://instagram.com/spherixglobal',
        'publishing_status': 'published'
    }

    resp = client.post('/hospital/dashboard', data=payload, follow_redirects=True)
    assert resp.status_code == 200

    # Verify updated database record
    updated = TEMP_DATA['hospitals'][hosp_id]
    assert updated.name == 'Spherix Global Medical Center'
    assert updated.general_beds == 220
    assert updated.consultation_fee == 900.0
    assert updated.follow_up_fee == 450.0
    assert updated.emergency_bed_fee == 2000.0
    assert updated.ot_fee == 8000.0
    assert updated.ambulance_fee == 1800.0
    assert updated.blood_stock['A+'] == 22
    assert updated.blood_stock['O+'] == 40
    assert updated.total_blood_units == (22 + 8 + 30 + 7 + 14 + 4 + 40 + 12)
    assert updated.ambulance_count == 6
    assert updated.slug == 'spherix-global-medical-center'

    # Verify synchronized public view via Slug
    public_resp = client.get(f'/hospitals/{updated.slug}')
    assert public_resp.status_code == 200
    pdata = public_resp.data.decode('utf-8')
    assert 'Spherix Global Medical Center' in pdata
    assert 'Cardiothoracic Surgery' in pdata
    assert 'Da Vinci Xi Robot' in pdata
    assert 'Star Health' in pdata

def test_hospital_settings_subtabs_isolation_and_selection(client):
    """Verifies that clicking any chosen subtab in Hospital Settings isolates only that subtab's cards/details."""
    hosp_id = 'HPT/2026/001'
    with client.session_transaction() as sess:
        sess['_user_id'] = f"hospital-{hosp_id}"
        sess['_fresh'] = True

    resp = client.get('/hospital/dashboard')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # 1. Verify Alpine switchSettingsTab or subtab selector exists
    assert "switchSettingsTab(" in html or "settingsTab =" in html

    # 2. Check each subtab button triggers its specific subtab
    expected_subtabs = [
        'profile', 'branding', 'resources', 'clinical', 'infrastructure',
        'rates', 'emergency', 'policies', 'social', 'security'
    ]
    for tab in expected_subtabs:
        # Button must call switchSettingsTab(tab) or settingsTab = tab
        assert f"switchSettingsTab('{tab}')" in html or f"settingsTab = '{tab}'" in html or f'switchSettingsTab("{tab}")' in html, f"Missing trigger for subtab {tab}"
        
        # Dedicated container for this tab with x-show scoping
        assert f"settingsTab === '{tab}'" in html, f"Missing x-show isolation for subtab {tab}"

    # 3. Verify 'all' option for full settings view
    assert "settingsTab === 'all'" in html


