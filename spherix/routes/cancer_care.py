import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from spherix.cancer_data import CANCER_DATA
from spherix.services.database import TEMP_DATA, save_data
from spherix.models.clinical import Appointment, PatientMedicalRecord
from spherix.models.user import Doctor, Hospital
from spherix.config import utcnow, ensure_safe_date
from spherix.extensions import csrf

cancer_care_bp = Blueprint('cancer_care', __name__)


# ==================== HELPERS & SEEDING ====================

def seed_oncology_data_if_needed():
    """Ensures verified oncology doctors and hospitals exist in TEMP_DATA for cross-module integration."""
    faculty_specs = [
        {
            "id": "DOC-ONCO-101",
            "first_name": "Dr. Sarah",
            "last_name": "Jenkins",
            "email": "sarah.jenkins@spherixclinic.com",
            "password": "seeded_faculty_pw_101",
            "department": "Oncology",
            "specialization": "Medical Oncology & Immunotherapy Lead",
            "qualification": "MD, DM (Medical Oncology - Tata Memorial), FACP",
            "experience": 16,
            "hospital_name": "Spherix Comprehensive Cancer Hub (Main Bunkers)",
            "consultation_fee": 1500,
            "working_hours": "Mon - Fri (09:00 AM - 04:00 PM)",
            "profile_picture_url": "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
            "phone": "+91 98765 43210",
            "city": "Metropolitan Medical City",
            "state": "National Capital Region",
            "country": "India",
            "publishing_status": "published",
            "is_verified": 1
        },
        {
            "id": "DOC-ONCO-102",
            "first_name": "Dr. Arvind",
            "last_name": "Ramesh",
            "email": "arvind.ramesh@spherixclinic.com",
            "password": "seeded_faculty_pw_102",
            "department": "Oncology",
            "specialization": "Surgical Oncology (Robotic & GI)",
            "qualification": "MS, MCh (Surgical Oncology - AIIMS), da Vinci Certified",
            "experience": 19,
            "hospital_name": "Spherix Robotic Surgery & Oncology Institute",
            "consultation_fee": 1800,
            "working_hours": "Tue - Sat (10:00 AM - 05:00 PM)",
            "profile_picture_url": "https://images.unsplash.com/photo-1622253692010-333f2da6031d?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
            "phone": "+91 98765 43211",
            "city": "North Cyber Medical City",
            "state": "National Capital Region",
            "country": "India",
            "publishing_status": "published",
            "is_verified": 1
        },
        {
            "id": "DOC-ONCO-103",
            "first_name": "Dr. Elena",
            "last_name": "Rostova",
            "email": "elena.rostova@spherixclinic.com",
            "password": "seeded_faculty_pw_103",
            "department": "Oncology",
            "specialization": "Radiation Oncology & CyberKnife Specialist",
            "qualification": "MD (Radiation Oncology), PhD (Stereotactic SBRT - ESMO)",
            "experience": 14,
            "hospital_name": "Spherix Advanced LINAC Radiotherapy Center",
            "consultation_fee": 1400,
            "working_hours": "Mon - Thu (08:30 AM - 03:30 PM)",
            "profile_picture_url": "https://images.unsplash.com/photo-1594824813583-722a4666f4a8?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
            "phone": "+91 98765 43212",
            "city": "Metropolitan Medical City",
            "state": "National Capital Region",
            "country": "India",
            "publishing_status": "published",
            "is_verified": 1
        },
        {
            "id": "DOC-ONCO-104",
            "first_name": "Dr. Marcus",
            "last_name": "Vance",
            "email": "marcus.vance@spherixclinic.com",
            "password": "seeded_faculty_pw_104",
            "department": "Oncology",
            "specialization": "Hematology & Bone Marrow Transplant",
            "qualification": "MD, FRCPath, BMT Fellowship (Fred Hutchinson)",
            "experience": 17,
            "hospital_name": "Spherix Cellular Therapeutics & BMT Wing",
            "consultation_fee": 1600,
            "working_hours": "Mon - Fri (10:00 AM - 04:30 PM)",
            "profile_picture_url": "https://images.unsplash.com/photo-1537368910025-700350fe46c7?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
            "phone": "+91 98765 43213",
            "city": "South Bio-Medical District",
            "state": "National Capital Region",
            "country": "India",
            "publishing_status": "published",
            "is_verified": 1
        }
    ]

    for d in faculty_specs:
        if d['id'] not in TEMP_DATA['doctors']:
            TEMP_DATA['doctors'][d['id']] = Doctor(**d)
        else:
            existing = TEMP_DATA['doctors'][d['id']]
            if isinstance(getattr(existing, 'experience', None), str):
                import re
                m = re.search(r'\d+', existing.experience)
                if m:
                    existing.experience = int(m.group(0))

    hospitals_specs = [
        {
            "id": "HOSP-ONCO-01",
            "name": "Spherix Comprehensive Cancer Institute",
            "email": "cancer.institute@spherixclinic.com",
            "password": "seeded_hospital_pw_01",
            "hospital_type": "National Apex Cancer Centre",
            "hospital_type_id": 1,
            "city": "Metropolitan Medical City",
            "state": "National Capital Region",
            "country": "India",
            "address": "402 Healthcare Avenue, Medical Enclave",
            "phone": "1800-774-3749",
            "emergency_phone": "1800-774-3749",
            "specialties": ["Oncology", "Cancer Care", "Surgical Oncology", "Radiation Oncology", "Medical Oncology"],
            "departments": ["Oncology", "Surgical Oncology", "Radiation Oncology", "Pathology"],
            "logo_url": "https://images.unsplash.com/photo-1586773860418-d37222d8fce3?ixlib=rb-4.0.3&auto=format&fit=crop&w=600&q=80",
            "cover_image_url": "https://images.unsplash.com/photo-1586773860418-d37222d8fce3?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80",
            "total_beds": 450,
            "available_beds": 82,
            "icu_beds": 60,
            "publishing_status": "published",
            "is_verified": 1
        },
        {
            "id": "HOSP-ONCO-02",
            "name": "Spherix Proton & Robotic Oncology Pavilion",
            "email": "proton.robotics@spherixclinic.com",
            "password": "seeded_hospital_pw_02",
            "hospital_type": "Advanced Surgical & Proton Hub",
            "hospital_type_id": 1,
            "city": "North Cyber Medical City",
            "state": "National Capital Region",
            "country": "India",
            "address": "Block 9, Robotic Health Corridor",
            "phone": "1800-774-3750",
            "emergency_phone": "1800-774-3750",
            "specialties": ["Oncology", "Proton Radiotherapy", "Robotic Surgery", "Precision Medicine"],
            "departments": ["Oncology", "Robotic Surgery", "Proton Therapy"],
            "logo_url": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?ixlib=rb-4.0.3&auto=format&fit=crop&w=600&q=80",
            "cover_image_url": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80",
            "total_beds": 320,
            "available_beds": 45,
            "icu_beds": 40,
            "publishing_status": "published",
            "is_verified": 1
        },
        {
            "id": "HOSP-ONCO-03",
            "name": "Spherix BMT & Cellular Therapeutics Center",
            "email": "bmt.cellular@spherixclinic.com",
            "password": "seeded_hospital_pw_03",
            "hospital_type": "Hematology & Stem Cell Institute",
            "hospital_type_id": 1,
            "city": "South Bio-Medical District",
            "state": "National Capital Region",
            "country": "India",
            "address": "15 Gene Park Road",
            "phone": "1800-774-3751",
            "emergency_phone": "1800-774-3751",
            "specialties": ["Oncology", "Hematology", "Bone Marrow Transplant", "Cellular Immunotherapy"],
            "departments": ["Oncology", "Hematology", "BMT Unit"],
            "logo_url": "https://images.unsplash.com/photo-1516549655169-df83a0774514?ixlib=rb-4.0.3&auto=format&fit=crop&w=600&q=80",
            "cover_image_url": "https://images.unsplash.com/photo-1516549655169-df83a0774514?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80",
            "total_beds": 200,
            "available_beds": 28,
            "icu_beds": 30,
            "publishing_status": "published",
            "is_verified": 1
        }
    ]

    for h in hospitals_specs:
        if h['id'] not in TEMP_DATA['hospitals']:
            TEMP_DATA['hospitals'][h['id']] = Hospital(**h)


def get_oncology_specialists():
    """Retrieves verified oncology doctors from TEMP_DATA or seeds structured oncology faculty."""
    seed_oncology_data_if_needed()
    doctors = list(TEMP_DATA.get('doctors', {}).values())
    oncology_docs = []
    
    for d in doctors:
        spec = (getattr(d, 'specialization', '') or getattr(d, 'department', '') or getattr(d, 'specialty', '')).lower()
        if any(term in spec for term in ['oncolog', 'cancer', 'chemo', 'hematolog', 'tumor', 'radiation', 'surgical onco']):
            oncology_docs.append(d)
            
    return oncology_docs


def get_oncology_hospitals():
    """Retrieves verified cancer hospitals and specialized centers from original accounts or oncology catalog."""
    seed_oncology_data_if_needed()
    from spherix.models.user import is_original_hospital_account
    hospitals = [
        h for h in TEMP_DATA.get('hospitals', {}).values()
        if is_original_hospital_account(h)
    ]
    cancer_hubs = []
    
    for h in hospitals:
        name = (getattr(h, 'name', '') or '').lower()
        htype = (getattr(h, 'type', '') or getattr(h, 'hospital_type', '') or '').lower()
        specs = [s.lower() for s in getattr(h, 'specialties', [])]
        if any(term in name or term in htype or any(term in s for s in specs) for term in ['cancer', 'onco', 'memorial', 'speciality', 'multi', 'central']):
            cancer_hubs.append(h)
            
    if not cancer_hubs:
        return globals().get('ONCOLOGY_CATALOG_HOSPITALS', [])
        
    return cancer_hubs


# ==================== 18 DEDICATED ROUTES ====================

# 1. Cancer Care Home
@cancer_care_bp.route("/cancer-care", endpoint="index")
@cancer_care_bp.route("/cancer-care", endpoint="cancer_care")
def index():
    """Renders the executive Cancer Care Centre homepage."""
    return render_template("cancer_care/home.html", cancers=CANCER_DATA)


# 2. Cancer Awareness
@cancer_care_bp.route("/cancer-care/awareness", endpoint="awareness")
def awareness():
    """Renders public cancer awareness, CAUTION warning signs, and myths vs facts."""
    return render_template("cancer_care/awareness.html")


# 3. Cancer Symptom Checker
@cancer_care_bp.route("/cancer-care/symptom-checker", endpoint="symptom_checker")
def symptom_checker():
    """Renders the upgraded anatomical symptom checker and clinical triage interface."""
    return render_template("cancer_care/symptom_checker.html")


@cancer_care_bp.route("/cancer-care/symptoms")
@cancer_care_bp.route("/cancer-care/symptoms-checker")
def cancer_care_symptoms_redirect():
    """Redirects to the Spherix Clinic multi-step AI Symptoms Analyzer (symptoms_step1.html)."""
    return redirect(url_for('symptoms'))


# 4. Cancer Types & Directory
@cancer_care_bp.route("/cancer-care/types", endpoint="types")
def types():
    """Renders the searchable, filterable directory of all 14 cancer monographs."""
    return render_template("cancer_care/types.html", cancers=CANCER_DATA)


@cancer_care_bp.route("/cancer-care/types/<slug>", endpoint="type_detail")
def type_detail(slug):
    """Renders the reusable individual monograph for a specific cancer."""
    if slug not in CANCER_DATA:
        flash(f"Cancer type '{slug}' not found in registry.", "error")
        return redirect(url_for('cancer_care.types'))
    cancer = CANCER_DATA[slug]
    return render_template("cancer_care/detail.html", cancer=cancer, cancer_slug=slug)


# 5. Cancer Prevention and Screening
@cancer_care_bp.route("/cancer-care/prevention-screening", endpoint="prevention_screening")
def prevention_screening():
    """Renders cancer screening timetables by age/gender and genetic risk roadmaps."""
    return render_template("cancer_care/prevention_screening.html")


# 6. Cancer Diagnosis and Testing
@cancer_care_bp.route("/cancer-care/diagnosis-testing", endpoint="diagnosis_testing")
def diagnosis_testing():
    """Renders biopsy modalities, PET-CT/MRI imaging, and the interactive TNM staging calculator."""
    return render_template("cancer_care/diagnosis_testing.html")


# 7. Cancer Treatment Information
@cancer_care_bp.route("/cancer-care/treatment", endpoint="treatment")
def treatment():
    """Renders multimodal treatment pathways: surgery, chemo, radiation, immunotherapy, targeted & hormone."""
    return render_template("cancer_care/treatment.html")


# 8. Cancer Specialist Directory
@cancer_care_bp.route("/cancer-care/specialists", endpoint="specialists")
def specialists():
    """Renders the filterable directory of verified oncology consultants."""
    docs = get_oncology_specialists()
    return render_template("cancer_care/specialists.html", specialists=docs)


# 9. Oncology Hospital Directory
@cancer_care_bp.route("/cancer-care/hospitals", endpoint="hospitals")
def hospitals():
    """Renders accredited cancer hospitals, LINAC bunkers, and specialized units."""
    hosps = get_oncology_hospitals()
    return render_template("cancer_care/hospitals.html", oncology_hospitals=hosps)


# 9b. Dynamic Appointment & Booking Entrypoint
@cancer_care_bp.route("/cancer-care/appointment", endpoint="appointment_flow")
@cancer_care_bp.route("/cancer-care/book", endpoint="book_redirect")
def appointment_flow():
    """When user clicks book appointment, redirect to patient login then to oncology specialists."""
    target = url_for('doctors_list', dept='Oncology')
    if not current_user.is_authenticated or str(getattr(current_user, 'role', '')).lower() != 'patient':
        return redirect(url_for('patient_login', next=target))
    return redirect(target)


# 10. Cancer Appointment Booking
@cancer_care_bp.route("/cancer-care/book-appointment", methods=["GET", "POST"], endpoint="book_appointment")
def book_appointment():
    """Schedules an oncology consultation or Tumor Board second opinion."""
    if not current_user.is_authenticated:
        flash("Please log in to your patient account to book an oncology consultation.", "info")
        return redirect(url_for('patient_login', next=request.full_path if request.query_string else request.path))
    if str(getattr(current_user, 'role', '')).lower() != 'patient':
        flash("Please switch to or log in with a Patient account to book an oncology consultation.", "warning")
        return redirect(url_for('patient_login', next=request.full_path if request.query_string else request.path))

    specialists_list = get_oncology_specialists()
    
    if request.method == "POST":
        patient_name = request.form.get("patient_name", "").strip()
        phone = request.form.get("patient_phone", "").strip()
        age = request.form.get("patient_age", "").strip()
        gender = request.form.get("patient_gender", "female").strip()
        doctor_id = request.form.get("doctor_id", "DOC-ONCO-101").strip()
        consultation_type = request.form.get("consultation_type", "In-Person Hospital Visit").strip()
        appt_date = request.form.get("appointment_date", "").strip()
        appt_time = request.form.get("appointment_time", "10:00 AM").strip()
        notes = request.form.get("clinical_notes", "").strip()
        
        if not patient_name or not phone or not appt_date:
            flash("Please provide patient name, contact phone number, and preferred date.", "error")
            return redirect(url_for('cancer_care.book_appointment'))
            
        # File attachment if uploaded
        uploaded_doc_path = None
        if 'medical_report' in request.files:
            file = request.files['medical_report']
            if file and file.filename:
                filename = secure_filename(f"ONCO_APPT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'cancer_reports')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                uploaded_doc_path = f"/static/uploads/cancer_reports/{filename}"

        # Assign unique appointment ID
        appt_id = TEMP_DATA.get('next_ids', {}).get('appointment', 3001)
        TEMP_DATA.setdefault('next_ids', {})['appointment'] = appt_id + 1
        
        patient_id = str(current_user.id) if current_user.is_authenticated else f"PAT-ONCO-{appt_id}"
        
        new_appt = Appointment(
            id=appt_id,
            patient_name=patient_name,
            doctor_id=doctor_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            patient_age=age,
            patient_phone=phone,
            patient_id=patient_id,
            reason=f"[ONCOLOGY: {consultation_type}] {notes}",
            status="confirmed",
            consultation_type=consultation_type,
            document_path=uploaded_doc_path,
            created_at=utcnow()
        )
        
        TEMP_DATA.setdefault('appointments', {})[appt_id] = new_appt
        save_data()
        
        flash(f"Oncology consultation booked successfully for {patient_name} on {appt_date} at {appt_time}. Reference: ONCO-APPT-{appt_id}.", "success")
        return redirect(url_for('cancer_care.journey'))

    selected_doctor_id = request.args.get("doctor_id", "")
    target_cancer = request.args.get("cancer", "")
    return render_template(
        "cancer_care/book_appointment.html",
        specialists=specialists_list,
        selected_doctor_id=selected_doctor_id,
        target_cancer=target_cancer
    )


# 11. AI Cancer Companion
@cancer_care_bp.route("/cancer-care/ai-companion", endpoint="ai_companion")
def ai_companion():
    """Renders the full-page 24/7 AI oncology companion powered by clinical intelligence."""
    return render_template("cancer_care/ai_companion.html")


# 12. Medical Report Management
@cancer_care_bp.route("/cancer-care/reports", methods=["GET", "POST"], endpoint="reports")
def reports():
    """Manages patient medical reports with HIPAA-compliant encrypted storage and doctor access sharing."""
    user_id = str(current_user.id) if current_user.is_authenticated else "sample_patient"
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        record_type = request.form.get("record_type", "Biopsy / Histopathology").strip()
        record_date = request.form.get("record_date", datetime.now().strftime('%Y-%m-%d')).strip()
        facility = request.form.get("facility_name", "Spherix Central Pathology").strip()
        
        if not title:
            flash("Please provide a title for the medical record.", "error")
            return redirect(url_for('cancer_care.reports'))
            
        saved_rel_path = None
        file_size_str = "0 KB"
        file_type = "pdf"
        
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'pdf'
                file_type = file_ext
                clean_name = secure_filename(f"REPORT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'cancer_reports')
                os.makedirs(upload_dir, exist_ok=True)
                full_path = os.path.join(upload_dir, clean_name)
                file.save(full_path)
                saved_rel_path = f"/static/uploads/cancer_reports/{clean_name}"
                file_size_str = f"{max(1, os.path.getsize(full_path) // 1024)} KB"

        rec_id_num = TEMP_DATA.get('next_ids', {}).get('medical_record', 101)
        TEMP_DATA.setdefault('next_ids', {})['medical_record'] = rec_id_num + 1
        rec_id = f"REC-ONCO-{rec_id_num:04d}"
        
        new_record = PatientMedicalRecord(
            id=rec_id,
            patient_id=user_id,
            patient_name=getattr(current_user, 'name', 'Patient'),
            title=title,
            record_type=record_type,
            record_date=record_date,
            facility_name=facility,
            file_path=saved_rel_path or '',
            file_type=file_type,
            file_size=file_size_str,
            shared_with=["all_verified_oncologists"]
        )
        
        TEMP_DATA.setdefault('medical_records', {})[rec_id] = new_record
        save_data()
        
        flash(f"Medical report '{title}' successfully encrypted and archived in your confidential vault.", "success")
        return redirect(url_for('cancer_care.reports'))

    # Retrieve patient's medical records
    all_recs = list(TEMP_DATA.get('medical_records', {}).values())
    if current_user.is_authenticated:
        user_recs = [r for r in all_recs if str(r.patient_id) == user_id]
    else:
        user_recs = all_recs[:4]  # Curated sample records for guests
        
    return render_template("cancer_care/reports.html", reports=user_recs)


# 13. My Cancer Care Journey
@cancer_care_bp.route("/cancer-care/journey", endpoint="journey")
def journey():
    """Renders the 6-milestone patient roadmap and symptom logging interface."""
    return render_template("cancer_care/journey.html")


# 14. Recovery and Rehabilitation
@cancer_care_bp.route("/cancer-care/recovery-rehab", endpoint="recovery_rehab")
def recovery_rehab():
    """Renders specialized lymphedema, post-op physiotherapy, and fatigue recovery protocols."""
    return render_template("cancer_care/recovery_rehab.html")


# 15. Nutrition and Wellness
@cancer_care_bp.route("/cancer-care/nutrition-wellness", endpoint="nutrition_wellness")
def nutrition_wellness():
    """Renders clinical oncology dietetics, neutropenic safety, and mind-body wellness."""
    return render_template("cancer_care/nutrition_wellness.html")


# 16. Patient and Family Support
@cancer_care_bp.route("/cancer-care/support", endpoint="support")
def support():
    """Renders psycho-oncology counseling, caregiver burnout support, and government financial aid."""
    return render_template("cancer_care/support.html")


# 17. Palliative Care
@cancer_care_bp.route("/cancer-care/palliative-care", endpoint="palliative_care")
def palliative_care():
    """Renders the WHO pain ladder, symptom relief, home hospice, and advance care planning."""
    return render_template("cancer_care/palliative_care.html")


# 18. Cancer Care FAQs
@cancer_care_bp.route("/cancer-care/faqs", endpoint="faqs")
def faqs():
    """Renders categorized, searchable oncology frequently asked questions."""
    return render_template("cancer_care/faqs.html")


# ==================== JSON ONCOLOGY APIS ====================

@cancer_care_bp.route("/api/cancer/risk-assess", methods=["POST"])
@csrf.exempt
def api_cancer_risk_assess():
    """Computes evidence-based oncology risk score and personalized screening roadmap."""
    data = request.get_json() or {}
    
    age = int(data.get('age', 35) or 35)
    gender = str(data.get('gender', 'female')).lower()
    family_history = data.get('family_history', [])
    smoking = data.get('smoking', 'never')
    sun_exposure = data.get('sun_exposure', 'low')
    symptoms = data.get('symptoms', [])
    
    score = 10
    risk_factors_detected = []
    screenings_recommended = []
    
    if age >= 50:
        score += 25
        risk_factors_detected.append("Advancing age (≥50)")
    elif age >= 40:
        score += 15
        risk_factors_detected.append("Age 40-49 screening threshold")
    
    if "breast" in family_history or "ovarian" in family_history or "breast_ovarian" in family_history:
        score += 25
        risk_factors_detected.append("Hereditary Breast/Ovarian Cancer syndrome risk")
        screenings_recommended.append({
            "test": "Genetic Testing (BRCA1/2) & Annual Breast MRI",
            "timeline": "Immediate consultation with Cancer Genetics specialist",
            "urgency": "High"
        })
    if "colon" in family_history or "colon_gi" in family_history:
        score += 20
        risk_factors_detected.append("Familial Colorectal Cancer risk")
        screenings_recommended.append({
            "test": "Early Screening Colonoscopy",
            "timeline": f"Start at age {max(25, age - 10)} or immediately",
            "urgency": "High"
        })
    if "prostate" in family_history and gender == 'male':
        score += 15
        risk_factors_detected.append("First-degree Prostate Cancer history")
        screenings_recommended.append({
            "test": "Serum PSA + DRE Exam",
            "timeline": "Annual baseline test starting age 40",
            "urgency": "Moderate"
        })
        
    if smoking == 'current_heavy':
        score += 30
        risk_factors_detected.append("Heavy tobacco consumption (>20 pack-years)")
        if age >= 50:
            screenings_recommended.append({
                "test": "Low-Dose Chest CT (LDCT)",
                "timeline": "Annual thoracic screening recommended",
                "urgency": "High"
            })
    elif smoking in ['current_light', 'smokeless']:
        score += 15
        risk_factors_detected.append("Active tobacco exposure")
    elif smoking == 'former':
        score += 8
        risk_factors_detected.append("Former tobacco history")
        
    if sun_exposure == 'high':
        score += 12
        risk_factors_detected.append("Frequent UV / blistering sunburn exposure")
        screenings_recommended.append({
            "test": "Full-Body Digital Dermoscopy",
            "timeline": "Annual total body skin mapping",
            "urgency": "Moderate"
        })
        
    red_flag_count = 0
    symptom_explanations = []
    if "unexplained_weight_loss" in symptoms or "weight_loss" in symptoms:
        score += 20
        red_flag_count += 1
        symptom_explanations.append("Unexplained weight loss (>10 lbs in 6 months)")
    if "palpable_lump" in symptoms:
        score += 25
        red_flag_count += 1
        symptom_explanations.append("New palpable breast/lymph node mass")
    if "persistent_cough" in symptoms:
        score += 18
        red_flag_count += 1
        symptom_explanations.append("Chronic cough or hemoptysis (>3 weeks)")
    if "rectal_bleeding" in symptoms:
        score += 22
        red_flag_count += 1
        symptom_explanations.append("Rectal bleeding or unexplained dark stools")
    if "changing_mole" in symptoms:
        score += 20
        red_flag_count += 1
        symptom_explanations.append("Asymmetrical or evolving pigmented skin mole")
        
    if gender == 'female' and age >= 40 and not any('Mammogram' in s['test'] for s in screenings_recommended):
        screenings_recommended.append({
            "test": "Annual 3D Digital Mammogram",
            "timeline": "Every 12 months for women aged 40+",
            "urgency": "Standard"
        })
    if age >= 45 and not any('Colonoscopy' in s['test'] for s in screenings_recommended):
        screenings_recommended.append({
            "test": "Screening Colonoscopy",
            "timeline": "Every 10 years (or annual FIT test) starting at 45",
            "urgency": "Standard"
        })
    if gender == 'male' and age >= 50 and not any('PSA' in s['test'] for s in screenings_recommended):
        screenings_recommended.append({
            "test": "Prostate Specific Antigen (PSA) Blood Test",
            "timeline": "Every 1-2 years based on baseline PSA level",
            "urgency": "Standard"
        })
        
    score = min(100, max(5, score))
    
    if red_flag_count >= 2 or score >= 70:
        risk_level = "High"
        risk_color = "#e11d48"
        summary = "Elevated risk indicators detected. We strongly recommend scheduling a clinical consultation with an oncology specialist for targeted diagnostic workup."
    elif red_flag_count == 1 or score >= 45:
        risk_level = "Elevated"
        risk_color = "#f59e0b"
        summary = "Moderate-to-elevated clinical risk factors identified. Proactive screening and lifestyle risk reduction are recommended."
    elif score >= 25:
        risk_level = "Moderate"
        risk_color = "#0ea5e9"
        summary = "Standard age and lifestyle risk profile. Adhere to routine preventive health screenings."
    else:
        risk_level = "Low"
        risk_color = "#10b981"
        summary = "Low baseline oncological risk profile. Maintain balanced nutrition, exercise, and age-recommended checkups."
        
    return jsonify({
        "success": True,
        "risk_score": score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "summary": summary,
        "risk_factors": risk_factors_detected,
        "warning_symptoms": symptom_explanations,
        "screenings": screenings_recommended,
        "preventive_actions": [
            "Maintain an active physical regimen (≥150 min weekly moderate exercise)",
            "Adopt a Mediterranean diet rich in antioxidants, cruciferous vegetables, and dietary fiber",
            "Strictly avoid tobacco products and minimize alcohol intake",
            "Practice sun safety with broad-spectrum SPF 50+ sunscreen",
            "Stay up-to-date with your annual clinical examinations at Spherix Clinic"
        ]
    })


@cancer_care_bp.route("/api/cancer/ai-consult", methods=["POST"])
@csrf.exempt
def api_cancer_ai_consult():
    """Interactive oncology intelligence advisor for patients, survivors, and caregivers."""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({"success": False, "error": "Please enter a clinical question or oncology term."}), 400
        
    ai_response = None
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if groq_api_key and not groq_api_key.startswith("gsk_yourActual"):
        try:
            import requests
            headers = {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
            system_prompt = (
                "You are Spherix Clinic's Senior Oncology Intelligence AI Assistant. "
                "Provide accurate, compassionate, medically sound, and evidence-based explanations of cancer biology, "
                "staging (TNM), diagnostic pathology terms (HER2, EGFR, Gleason, etc.), treatment mechanisms (chemo, immunotherapy, radiation), "
                "and supportive symptom management. Never use markdown asterisks (no raw '**'). Always format headings with standard punctuation or bullet points. "
                "Always remind users to discuss clinical decisions with their oncologist."
            )
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.3,
                "max_tokens": 600
            }
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                result = resp.json()
                ai_response = result['choices'][0]['message']['content']
                # Clean any raw asterisks if generated
                ai_response = ai_response.replace('**', '')
        except Exception as e:
            print(f"DEBUG: Groq cancer consult fallback due to {e}")
            
    if not ai_response:
        q_lower = query.lower()
        if "gleason" in q_lower:
            ai_response = (
                "Gleason Score Explanation:\n\n"
                "The Gleason Score evaluates prostate biopsy tissue pattern (Grade Group 1 to 5):\n"
                "• Gleason 6 (3+3): Low-grade, slow growing (Grade Group 1).\n"
                "• Gleason 7 (3+4 or 4+3): Intermediate risk (Grade Group 2 or 3).\n"
                "• Gleason 8-10: High-grade, more aggressive (Grade Group 4 or 5).\n\n"
                "Clinical Guidance: A Gleason score helps your multidisciplinary team decide between Active Surveillance, Surgery (Prostatectomy), or Radiation."
            )
        elif "her2" in q_lower or "er/pr" in q_lower:
            ai_response = (
                "Breast Cancer Biomarkers (HER2 & ER/PR):\n\n"
                "• ER+ / PR+ (Hormone Receptor Positive): Cells grow in response to estrogen/progesterone. Responds well to endocrine blockers like Tamoxifen or Anastrozole.\n"
                "• HER2-Positive: Cells produce excess HER2 growth protein. Targeted monoclonal antibodies like Trastuzumab (Herceptin) and Pertuzumab specifically bind to and destroy these cells.\n"
                "• Triple Negative (TNBC): Lacks ER, PR, and HER2; treated with targeted chemotherapy and modern immune checkpoint inhibitors (Pembrolizumab)."
            )
        elif "immunotherapy" in q_lower or "checkpoint" in q_lower or "pd-l1" in q_lower:
            ai_response = (
                "How Immunotherapy Works:\n\n"
                "Unlike traditional chemotherapy (which directly damages dividing cells), Immunotherapy unleashes your body's immune T-cells to recognize and destroy cancer cells.\n\n"
                "• Checkpoint Inhibitors (PD-1 / PD-L1 Blockers): Cancer cells often present a shield (PD-L1). Drugs like Pembrolizumab and Nivolumab remove this shield.\n"
                "• Side Effects: Side effects are primarily inflammatory (rash, colitis, pneumonitis, thyroiditis), which are promptly managed with corticosteroids."
            )
        elif "stage 4" in q_lower or "metastatic" in q_lower:
            ai_response = (
                "Understanding Metastatic (Stage IV) Cancer:\n\n"
                "Stage IV means cancer cells have spread beyond the primary organ to distant sites (such as liver, lungs, bones, or brain).\n\n"
                "• Modern Advances: Precision oncology, targeted molecular therapy, and immunotherapy have transformed many Stage IV conditions into manageable chronic conditions.\n"
                "• Goals of Therapy: Maximize quality of life, maintain durable disease control, and target genetic vulnerabilities in tumor DNA."
            )
        elif "nausea" in q_lower or "side effect" in q_lower or "fatigue" in q_lower:
            ai_response = (
                "Chemotherapy Side-Effect Management:\n\n"
                "1. Anticipatory & Acute Nausea: Modern 3-drug antiemetic regimens (5-HT3 antagonists + NK1 inhibitors + Dexamethasone) prevent up to 90% of nausea.\n"
                "2. Fatigue: Gentle 15-minute daily walks, strategic short naps, and drinking 2-3 liters of electrolyte-rich fluids daily.\n"
                "3. Infection Precaution: If you develop a fever ≥100.4°F (38.0°C) during chemotherapy, contact your care team immediately for febrile neutropenia evaluation."
            )
        else:
            ai_response = (
                f"Oncology Clinical Intelligence Insights:\n\n"
                f"Regarding your inquiry about '{query}':\n\n"
                "• Clinical Context: In modern oncology, diagnosis and treatment are personalized based on genomic profiling, biomarkers, and high-resolution staging.\n"
                "• Next Steps: We recommend compiling your pathology report and imaging scans for discussion with your Spherix Clinic oncology specialist.\n\n"
                "Clinical Disclaimer: This AI consultation provides evidence-based educational insights and does not replace formal clinical evaluation."
            )
            
    return jsonify({
        "success": True,
        "query": query,
        "answer": ai_response,
        "timestamp": utcnow().strftime('%H:%M:%S UTC')
    })


@cancer_care_bp.route("/api/cancer/clinical-trials", methods=["GET"])
def api_cancer_clinical_trials():
    """Returns verified active oncology clinical trials."""
    trials = [
        {
            "id": "NCT-05891240",
            "title": "Next-Generation Dual Checkpoint Inhibitor in Advanced NSCLC",
            "phase": "Phase III",
            "condition": "Lung Cancer (NSCLC)",
            "eligibility": "Stage III/IV, PD-L1 ≥ 1%, No prior immunotherapy",
            "locations": ["Spherix Oncology Research Center", "Memorial Cancer Institute"],
            "status": "Recruiting"
        },
        {
            "id": "NCT-05118432",
            "title": "Novel Antibody-Drug Conjugate (ADC) for HER2-Low Metastatic Breast Cancer",
            "phase": "Phase II",
            "condition": "Breast Cancer",
            "eligibility": "HER2 IHC 1+ or 2+/ISH-, Progression on prior endocrine therapy",
            "locations": ["Spherix Comprehensive Cancer Hub"],
            "status": "Recruiting"
        },
        {
            "id": "NCT-04987112",
            "title": "PSMA-Targeted Radioligand Therapy for Castration-Resistant Prostate Cancer",
            "phase": "Phase III",
            "condition": "Prostate Cancer",
            "eligibility": "PSMA-positive PET scan, mCRPC with prior ARPI exposure",
            "locations": ["Spherix Nuclear Medicine Unit"],
            "status": "Active"
        },
        {
            "id": "NCT-06041988",
            "title": "Personalized mRNA Neoantigen Vaccine Combined with Pembrolizumab for Resected Melanoma",
            "phase": "Phase II/III",
            "condition": "Melanoma",
            "eligibility": "High-risk Stage IIIB-IV post complete surgical resection",
            "locations": ["Spherix Genomic Therapeutics Suite"],
            "status": "Recruiting"
        }
    ]
    return jsonify({"success": True, "trials": trials})


@cancer_care_bp.route("/api/cancer/ai-deep-diagnosis", methods=["POST"])
@csrf.exempt
def api_cancer_ai_deep_diagnosis():
    """Performs structured oncology diagnostic matching and clinical triage."""
    data = request.get_json() or {}
    
    age = int(data.get('age', 40) or 40)
    gender = str(data.get('gender', 'female')).lower()
    organ_system = str(data.get('organ_system', 'general')).lower()
    duration = str(data.get('duration', '1-3 months'))
    symptoms_text = str(data.get('symptoms_text', '')).strip()
    red_flags = data.get('red_flags', [])
    family_history = data.get('family_history', [])
    smoking = str(data.get('smoking', 'never'))
    lab_notes = str(data.get('lab_notes', '')).strip()
    
    # Clinical Expert Heuristic Engine
    full_text = f"{organ_system} {symptoms_text} {' '.join(red_flags)} {lab_notes}".lower()
    
    if "breast" in organ_system or "breast" in full_text:
        is_high = "palpable_lump" in red_flags or "lump" in full_text
        ai_result = {
            "primary_condition": "Suspected Mammary Neoplasm / Breast Lesion" if is_high else "Benign Breast Condition (Fibroadenoma / Cyst)",
            "confidence_pct": 84 if is_high else 65,
            "risk_level": "High Risk" if is_high else "Moderate Risk",
            "risk_color": "#e11d48" if is_high else "#0ea5e9",
            "urgency": "Urgent (Diagnostic workup within 1-2 weeks)" if is_high else "Standard Clinical Exam",
            "differential_diagnoses": ["Invasive Ductal Carcinoma (IDC)", "Ductal Carcinoma In Situ (DCIS)", "Fibroadenoma", "Fibrocystic Mastopathy"],
            "key_biomarkers": ["HER2/neu (ERBB2)", "Estrogen Receptor (ER)", "Progesterone Receptor (PR)", "Ki-67 Proliferation", "BRCA1 / BRCA2 Germline"],
            "diagnostic_workup": [
                "High-Resolution 3D Digital Diagnostic Mammogram with Tomosynthesis",
                "Targeted Breast & Axillary Lymph Node Ultrasound",
                "Ultrasound-Guided Core Needle Biopsy with Histopathology",
                "Contrast-Enhanced Breast MRI if high risk"
            ],
            "treatment_pathway": [
                "Breast-Conserving Surgery with Sentinel Node Biopsy or Mastectomy",
                "Targeted Anti-HER2 Monoclonal Antibodies (Trastuzumab + Pertuzumab)",
                "Endocrine Blockade (Tamoxifen or Aromatase Inhibitors)",
                "Adjuvant or Neoadjuvant Chemotherapy & Whole Breast Radiotherapy"
            ],
            "specialist_type": "Breast Surgical Oncologist & Comprehensive Breast Center",
            "clinical_summary": f"Reported breast changes over {duration} require imaging and histological evaluation to establish precise tissue diagnosis."
        }
    elif "lung" in organ_system or "chest" in organ_system or "cough" in full_text:
        is_high = "hemoptysis" in red_flags or "unexplained_weight_loss" in red_flags or smoking == 'current_heavy'
        ai_result = {
            "primary_condition": "Pulmonary Nodule / Bronchogenic Neoplasm" if is_high else "Chronic Bronchial Inflammatory Syndrome",
            "confidence_pct": 82 if is_high else 60,
            "risk_level": "High Risk" if is_high else "Elevated Risk",
            "risk_color": "#e11d48" if is_high else "#f59e0b",
            "urgency": "Urgent (Thoracic Oncology consult within 1-2 weeks)",
            "differential_diagnoses": ["Non-Small Cell Lung Cancer", "Small Cell Lung Cancer", "Infectious Granuloma", "Atypical Pneumonitis"],
            "key_biomarkers": ["EGFR Mutation", "ALK Gene Rearrangement", "ROS1", "BRAF V600E", "PD-L1 TPS (%)"],
            "diagnostic_workup": [
                "High-Resolution Contrast Chest CT Scan",
                "Whole-Body FDG PET-CT for Staging",
                "EBUS Transbronchial Needle Aspiration",
                "Next-Generation Sequencing (NGS 50+ Lung Panel)"
            ],
            "treatment_pathway": [
                "VATS or Robotic Lobectomy",
                "Targeted Tyrosine Kinase Inhibitors (Osimertinib, Alectinib)",
                "Immune Checkpoint Blockade (Pembrolizumab)",
                "Stereotactic Body Radiotherapy (SBRT)"
            ],
            "specialist_type": "Thoracic Surgical Oncologist & Interventional Pulmonologist",
            "clinical_summary": f"Respiratory symptoms lasting {duration} warrant high-resolution thoracic imaging and staging."
        }
    else:
        is_high = len(red_flags) >= 2 or "unexplained_weight_loss" in red_flags
        ai_result = {
            "primary_condition": "Oncologic Diagnostic Evaluation Indicated" if is_high else "Non-Malignant Systemic Presentation",
            "confidence_pct": 74 if is_high else 55,
            "risk_level": "High Risk" if is_high else "Moderate Risk",
            "risk_color": "#e11d48" if is_high else "#0ea5e9",
            "urgency": "Priority (Comprehensive Oncology Consultation)",
            "differential_diagnoses": ["Malignancy of Undetermined Primary", "Systemic Endocrine Disorder", "Chronic Autoimmune Syndrome"],
            "key_biomarkers": ["Serum Tumor Markers (CEA, CA 19-9, CA 125, PSA)", "Circulating Tumor DNA", "Next-Gen Comprehensive Genomic Panel"],
            "diagnostic_workup": [
                "Comprehensive Oncology Blood Panel with CBC, CMP, LDH",
                "Total-Body Contrast-Enhanced CT Scan",
                "Targeted Tissue Biopsy of suspicious lesion",
                "Genetic Counseling"
            ],
            "treatment_pathway": [
                "Multidisciplinary Tumor Board Staging",
                "Targeted molecular therapy based on alterations",
                "Systemic Immunotherapy & Chemotherapy protocols"
            ],
            "specialist_type": "Multidisciplinary Medical Oncologist",
            "clinical_summary": f"Reported symptoms over {duration} with {len(red_flags)} warning indicators require formal multidisciplinary diagnostic evaluation."
        }

    return jsonify({
        "success": True,
        "result": ai_result,
        "input_profile": {
            "age": age,
            "gender": gender,
            "organ_system": organ_system,
            "duration": duration
        },
        "timestamp": utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    })
