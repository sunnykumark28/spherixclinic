import pytest
import json
from werkzeug.security import generate_password_hash
from spherix import create_app
from spherix.models import Doctor
from spherix.services.database import TEMP_DATA

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            doc_id = 'DOC/2026/001'
            default_pass = generate_password_hash('Doctor@123', method='pbkdf2:sha256:260000')
            TEMP_DATA['doctors'][doc_id] = Doctor(
                id=doc_id,
                first_name='Rajesh',
                last_name='Verma',
                email='dr.rajesh.verma@spherixclinic.com',
                password=default_pass,
                department='Cardiology',
                specialization='Interventional Cardiology',
                qualification='MBBS, MD',
                license_number='NMC/2018/88921',
                hospital_name='Spherix Central Hospital',
                city='New Delhi',
                state='Delhi',
                country='India',
                is_verified=True,
                publishing_status='published'
            )
            yield client

def test_doctor_profile_update_and_public_sync(client):
    doc_id = 'DOC/2026/001'
    doc = TEMP_DATA['doctors'][doc_id]

    with client.session_transaction() as sess:
        sess['_user_id'] = f"doctor-{doc_id}"
        sess['_fresh'] = True

    # 1. Update doctor profile with comprehensive attributes (Sections A-H)
    payload = {
        'action': 'update_profile',
        'title': 'Prof. Dr.',
        'first_name': 'Rajesh',
        'last_name': 'Verma',
        'gender': 'Male',
        'dob': '1980-05-15',
        'phone': '+91 98765 43210',
        'whatsapp_number': '+91 98765 43210',
        'email': doc.email,
        'license_number': 'NMC/2018/88921',
        'medical_council_reg': 'Delhi Medical Council / NMC Certified Specialist',
        'department': 'Cardiology',
        'specialization': 'Interventional & Structural Cardiology',
        'secondary_specialization': 'Preventive Cardiometabolic Medicine',
        'experience': '16',
        'languages_spoken': 'English, Hindi, Bengali',
        'availability_status': 'available',
        # Section B: Qualifications
        'qualification': 'MBBS, MD (Medicine), DM (Cardiology), FESC',
        'mbbs_degree': 'MBBS (Hons), University Gold Medalist',
        'higher_degree': 'MD - Internal Medicine, DM - Cardiology',
        'medical_degrees': 'MBBS, MD, DM, FESC, FSCAI (USA)',
        'university_name': 'All India Institute of Medical Sciences (AIIMS)',
        'college_name': 'Maulana Azad Medical College',
        'graduation_year': '2008',
        'certifications': 'Board Certified Interventional Cardiologist, ACLS AHA Provider, European Society of Cardiology Fellow',
        'fellowships': 'Fellowship in Advanced Structural Heart Interventions (FSCAI USA)',
        'medical_training': 'Complex Coronary Bifurcation Stenting Masterclass, TAVR Transcatheter Valve Workshop',
        # Section C: Experience
        'hospital_name': 'Spherix Central Hospital',
        'previous_hospitals': 'AIIMS New Delhi, Fortis Escorts Heart Institute, Medanta The Medicity',
        'previous_employment': 'Senior Resident (Cardiology) - AIIMS (2012-2015); Associate Consultant - Fortis Escorts (2015-2019); Senior Consultant - Spherix (2019-Present)',
        'professional_experience': 'Over 16 years of clinical excellence in complex percutaneous coronary intervention, coronary bifurcation stenting, and preventive cardiometabolic care.',
        'areas_of_expertise': 'Complex Angioplasty, TAVR Valve Therapies, Preventive Cardiology, Heart Failure Optimization',
        'memberships': 'Cardiological Society of India (CSI), Indian Medical Association (IMA), Fellow of European Society of Cardiology (FESC)',
        # Section D: Specializations & Procedures
        'sub_specializations': 'Structural Heart Diseases, Intravascular Ultrasound (IVUS), Optical Coherence Tomography (OCT)',
        'conditions_treated': 'Coronary Artery Disease, Refractory Angina, Acute Coronary Syndrome, Heart Failure with Preserved Ejection Fraction',
        'diseases_diagnosed': 'Valvular Heart Sclerosis, Hypertrophic Cardiomyopathy, Complex Arrhythmias',
        'treatments_offered': 'Evidence-Based Statin Optimization, Digital Cardiac Rehabilitation, Coronary Interventions',
        'medical_procedures': 'Coronary Angiography, 2D Strain Echocardiography, FFR Coronary Physiology Assessment',
        'preventive_healthcare': 'Annual Cardiovascular Risk Stratification, Comprehensive Lipid Panel Review, Lifestyle Modification Plans',
        'patient_counselling': 'Pre-Angioplasty Family Counselling, Post-Infarction Mental Wellness Support',
        'diagnostic_services': '12-Lead Digital ECG Analysis, 24-Hour Holter Telemetry, Exercise Stress Testing',
        # Section E: Hospital & Clinic Info
        'hospital_address': 'Sector 14, Health City Medical Enclave, New Delhi',
        'clinic_name': 'Dr. Verma Heart & Vascular Clinic',
        'clinic_address': 'Suite #302, MedTower, Barakhamba Road, New Delhi',
        'hospital_affiliations': 'Spherix Central Hospital, Metro Heart Institute, Apex Multi-Specialty Hospital',
        'consultation_location': 'OPD Block B, Executive Chamber #204',
        'city': 'New Delhi',
        'state': 'Delhi',
        'district': 'Central Delhi',
        'pincode': '110001',
        'country': 'India',
        'opd_schedule': 'Monday – Saturday: 10:00 AM – 05:00 PM (Executive Chamber #204)',
        'working_hours': '10:00 AM - 05:00 PM',
        # Section F: Appointment & Fees
        'consultation_fee': '1200',
        'follow_up_fee': '600',
        'video_fee': '1000',
        'appointment_duration': '30 Mins',
        'weekly_availability': 'Monday – Saturday: 10:00 AM – 05:00 PM',
        'available_slots': '10:00 AM, 11:30 AM, 02:30 PM, 04:00 PM',
        'consultation_type': 'In-Person & Telehealth',
        # Section G: Gallery & Media
        'gallery_urls': 'https://example.com/dr_verma_opd.jpg, https://example.com/dr_verma_cathlab.jpg',
        'clinic_photos': 'https://example.com/clinic_front.jpg',
        'video_urls': 'https://www.youtube.com/watch?v=spherix_heart_health',
        # Section H: Achievements & Publications
        'bio': 'Prof. Dr. Rajesh Verma is a distinguished Senior Interventional Cardiologist committed to precision cardiovascular therapeutics and digital health democratization.',
        'career_summary': '16+ years clinical practice heading high-volume catheterization laboratories and authoring international cardiac safety protocols.',
        'treatment_philosophy': 'Patient-first, evidence-driven cardiovascular medicine combining precision interventional technologies with compassionate lifestyle healing.',
        'awards': 'National Healthcare Leadership Award in Cardiology (2023), AIIMS Best Clinical Fellow Medal, Distinguished Cardiologist of the Year',
        'achievements': 'Pioneered zero-contrast coronary angioplasty in chronic kidney disease patients; performed 6,000+ cardiac catheterizations.',
        'publications': 'Contemporary Protocols in Complex Bifurcation Stenting — Indian Heart Journal; Safety Profiles in Tele-Cardiology — Journal of Clinical Medicine',
        'research_papers': 'Long-term Outcomes of Bioresorbable Scaffolds in South Asian Cohorts: A 5-Year Prospective Study',
        'medical_conferences': 'Faculty Speaker at Cardiological Society of India Annual Congress (2023, 2024); International Transcatheter Therapeutics (TCT) Delegate',
        'healthcare_contributions': 'Conducted 30+ Free Cardiovascular Health Camps across rural districts screening over 10,000 patients.',
        'patient_instructions': 'Please carry previous coronary angiogram CDs, recent lipid panels, kidney function tests, and active prescription records.'
    }

    resp = client.post('/doctor/dashboard', data=payload, follow_redirects=True)
    assert resp.status_code == 200

    # 2. Check in-memory database record
    updated_doc = TEMP_DATA['doctors'][doc_id]
    assert updated_doc.title == 'Prof. Dr.'
    assert updated_doc.full_title_name == 'Prof. Dr. Rajesh Verma'
    assert updated_doc.specialization == 'Interventional & Structural Cardiology'
    assert updated_doc.secondary_specialization == 'Preventive Cardiometabolic Medicine'
    assert updated_doc.experience == '16'
    assert updated_doc.mbbs_degree == 'MBBS (Hons), University Gold Medalist'
    assert updated_doc.university_name == 'All India Institute of Medical Sciences (AIIMS)'
    assert updated_doc.consultation_fee == '1200'
    assert updated_doc.follow_up_fee == '600'
    assert updated_doc.video_fee == '1000'
    assert updated_doc.clinic_name == 'Dr. Verma Heart & Vascular Clinic'
    assert 'Metro Heart Institute' in updated_doc.affiliations_list
    assert 'Complex Angioplasty' in updated_doc.areas_of_expertise_list

    # 3. Verify public view via slug route: /doctors/<doctor_slug>
    doc_slug = updated_doc.slug
    assert 'rajesh-verma' in doc_slug
    public_resp = client.get(f"/doctors/{doc_slug}")
    assert public_resp.status_code == 200
    html = public_resp.data.decode('utf-8')

    # Verify updated doctor data appears on public page
    assert 'Prof. Dr. Rajesh Verma' in html
    assert 'Interventional &amp; Structural Cardiology' in html or 'Interventional & Structural Cardiology' in html
    assert 'Preventive Cardiometabolic Medicine' in html
    assert 'All India Institute of Medical Sciences (AIIMS)' in html
    assert '1200' in html
    assert '600' in html
    assert '1000' in html
    assert 'Dr. Verma Heart &amp; Vascular Clinic' in html or 'Dr. Verma Heart & Vascular Clinic' in html
    assert 'National Healthcare Leadership Award' in html

    # Verify all 14 navigation tabs are rendered
    assert '1. Overview' in html
    assert '2. About Doctor' in html
    assert '3. Qualifications' in html
    assert '4. Experience' in html
    assert '5. Specializations' in html
    assert '6. Conditions Treated' in html
    assert '7. Treatments' in html
    assert '8. Hospital &amp; Clinics' in html or '8. Hospital & Clinics' in html
    assert '9. Consultation Fees' in html
    assert '10. Availability' in html
    assert '11. Reviews &amp; Ratings' in html or '11. Reviews & Ratings' in html
    assert '12. Achievements' in html
    assert '13. Gallery' in html
    assert '14. FAQs' in html

    # 4. Verify public view via ID route: /doctor/<doc_id>
    id_resp = client.get(f"/doctor/{doc_id}")
    assert id_resp.status_code == 200
    id_html = id_resp.data.decode('utf-8')
    assert 'Prof. Dr. Rajesh Verma' in id_html
    assert 'Dr. Verma Heart &amp; Vascular Clinic' in id_html or 'Dr. Verma Heart & Vascular Clinic' in id_html

def test_doctor_profile_ajax_update(client):
    doc_id = 'DOC/2026/001'

    with client.session_transaction() as sess:
        sess['_user_id'] = f"doctor-{doc_id}"
        sess['_fresh'] = True

    ajax_payload = {
        'action': 'update_profile',
        'title': 'Dr.',
        'first_name': 'Rajesh',
        'last_name': 'Verma',
        'department': 'Cardiology',
        'specialization': 'Interventional Cardiology',
        'consultation_fee': '1500',
        'working_hours': '09:00 AM - 04:00 PM',
        'bio': 'AJAX updated cardiology specialist profile.'
    }

    resp = client.post(
        '/doctor/dashboard',
        data=ajax_payload,
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode('utf-8'))
    assert data.get('success') is True
    assert 'slug' in data
    assert 'public_url' in data
    assert '/doctors/' in data['public_url']

    # Database reflection
    assert TEMP_DATA['doctors'][doc_id].consultation_fee == '1500'

def test_doctor_visibility_and_suspension_control(client):
    doc_id = 'DOC/2026/001'
    doc = TEMP_DATA['doctors'][doc_id]

    # Set doctor as suspended
    doc.publishing_status = 'suspended'
    doc_slug = doc.slug

    # 1. Doctor owner can view even if suspended
    with client.session_transaction() as sess:
        sess['_user_id'] = f"doctor-{doc_id}"
        sess['user_role'] = 'doctor'
        sess['_fresh'] = True

    owner_resp = client.get(f"/doctors/{doc_slug}")
    assert owner_resp.status_code == 200

    # 2. Logout: Anonymous user cannot view suspended profile (redirects or 404)
    client.get('/logout')

    anon_resp = client.get(f"/doctors/{doc_slug}", follow_redirects=False)
    assert anon_resp.status_code in [302, 404]

    # 3. Restore to published: public can view
    doc.publishing_status = 'published'
    public_resp = client.get(f"/doctors/{doc_slug}")
    assert public_resp.status_code == 200

    # Restore to published
    doc.publishing_status = 'published'
    public_resp = client.get(f"/doctors/{doc_slug}")
    assert public_resp.status_code == 200

    # Restore to published
    doc.publishing_status = 'published'
    public_resp = client.get(f"/doctors/{doc_slug}")
    assert public_resp.status_code == 200
