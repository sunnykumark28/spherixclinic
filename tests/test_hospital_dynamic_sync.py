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
                name='Spherix Clinic',
                email='hospital.test@spherixclinic.com',
                password=default_pass,
                total_beds=150,
                available_beds=40,
                icu_beds=20,
                available_icu_beds=5,
                address='Main Medical Campus, New Delhi',
                city='New Delhi',
                state='Delhi',
                country='India',
                is_verified=True,
                publishing_status='published'
            )
            yield client

def test_hospital_profile_update_and_public_sync(client):
    hosp_id = 'HPT/2026/001'
    hosp = TEMP_DATA['hospitals'][hosp_id]

    with client.session_transaction() as sess:
        sess['_user_id'] = f"hospital-{hosp_id}"
        sess['_fresh'] = True

    # 1. Update hospital profile with 40+ attributes
    payload = {
        'update_profile': '1',
        'name': 'Spherix Apex Super Specialty Hospital',
        'email': hosp.email,
        'phone': '+91 11 2658 7777',
        'emergency_phone': '+91 11 2658 8888',
        'ambulance_phone': '+91 11 2658 9999',
        'patient_support_phone': '+91 11 2658 0000',
        'patient_support_email': 'support@spherixapex.com',
        'website': 'https://apex.spherixclinic.com',
        'establishment_year': '2001',
        'about': 'State-of-the-art tertiary care center pioneering precision oncology and robotic surgery.',
        'address': 'Sector 12, Health Boulevard, Institutional Area',
        'city': 'New Delhi',
        'state': 'Delhi',
        'zip_code': '110029',
        'country': 'India',
        'departments_custom': 'Robotic Surgery, Bone Marrow Transplant, Neuro-Trauma, Pediatric Cardiology',
        'specialties_csv': 'Oncology, Cardiology, Neurosurgery, Organ Transplant',
        'infrastructure': 'Central Oxygen PSA Plant, 100% DG Power Backup, HEPA-filtered HVAC Surgical Suites',
        'medical_equipment': '3 Tesla Digital MRI, 128-Slice Dual Source CT, Biplane Cath Lab, ECMO Unit',
        'diagnostic_services': 'Digital Radiography, 4D Ultrasound, Color Doppler, Echocardiography',
        'laboratory_facilities': 'Automated Biochemistry Analyzer, PCR Molecular Lab, Histopathology',
        'general_beds': '200',
        'available_general_beds': '35',
        'private_beds': '60',
        'available_private_beds': '10',
        'icu_beds': '35',
        'available_icu_beds': '6',
        'nicu_beds': '12',
        'available_nicu_beds': '4',
        'picu_beds': '8',
        'available_picu_beds': '2',
        'emergency_beds': '20',
        'available_emergency_beds': '5',
        'operation_theatres': '10',
        'available_ot': '3',
        'consultation_fee': '800',
        'general_bed_fee': '1500',
        'private_bed_fee': '4000',
        'icu_bed_fee': '3200',
        'admission_charge': '600',
        'insurance_cashless': 'Star Health, HDFC ERGO, ICICI Lombard, Ayushman Bharat PM-JAY, Medi Assist',
        'emergency_services': 'on',
        'blood_bank_available': 'on',
        'pharmacy_available': 'on',
        'pharmacy_hours': '24/7 Round the Clock',
        'ambulance_services': 'on',
        'ambulance_count': '5',
        'visiting_hours': 'Morning: 10:00 AM - 12:00 PM | Evening: 05:00 PM - 07:00 PM',
        'patient_guidelines': 'Government photo ID and active health insurance card required for cashless admission.'
    }

    resp = client.post('/hospital/dashboard', data=payload, follow_redirects=True)
    assert resp.status_code == 200

    # 2. Check updated database record
    updated = TEMP_DATA['hospitals'][hosp_id]
    assert updated.name == 'Spherix Apex Super Specialty Hospital'
    assert updated.general_beds == 200
    assert updated.consultation_fee == 800.0
    assert updated.slug == 'spherix-apex-super-specialty-hospital'

    # 3. Synchronized public view via Slug
    slug_resp = client.get(f'/hospitals/{updated.slug}')
    assert slug_resp.status_code == 200
    assert b'Spherix Apex Super Specialty Hospital' in slug_resp.data
    assert b'Robotic Surgery' in slug_resp.data
    assert b'3 Tesla Digital MRI' in slug_resp.data
    assert b'Central Oxygen PSA Plant' in slug_resp.data
    assert b'Star Health' in slug_resp.data

    # 4. Synchronized public view via ID
    id_resp = client.get(f'/hospital/{hosp_id}')
    assert id_resp.status_code == 200
    assert b'Spherix Apex Super Specialty Hospital' in id_resp.data

def test_hospital_profile_ajax_sync(client):
    hosp_id = 'HPT/2026/001'
    hosp = TEMP_DATA['hospitals'][hosp_id]

    with client.session_transaction() as sess:
        sess['_user_id'] = f"hospital-{hosp_id}"
        sess['_fresh'] = True

    ajax_payload = {
        'update_profile': '1',
        'name': 'Spherix Innovation Health',
        'email': hosp.email,
        'consultation_fee': '950'
    }

    resp = client.post('/hospital/dashboard', data=ajax_payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['slug'] == 'spherix-innovation-health'
    assert data['public_url'] == '/hospitals/spherix-innovation-health'
