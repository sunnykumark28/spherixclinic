from datetime import datetime
from spherix.config import utcnow, ensure_safe_date

class Appointment:
    def __init__(self, id, patient_name, doctor_id, appointment_date, appointment_time, **kwargs):
        self.id = id
        self.patient_name = patient_name
        self.doctor_id = doctor_id
        self.appointment_date = ensure_safe_date(appointment_date)
        self.appointment_time = ensure_safe_date(appointment_time)
        self.patient_age = kwargs.get('patient_age')
        self.patient_id_number = kwargs.get('patient_id_number')
        self.patient_phone = kwargs.get('patient_phone')
        self.patient_id = kwargs.get('patient_id')
        self.reason = kwargs.get('reason')
        self.status = kwargs.get('status', 'confirmed')
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))
        self.original_appointment_date = ensure_safe_date(kwargs.get('original_appointment_date'))
        self.original_appointment_time = ensure_safe_date(kwargs.get('original_appointment_time'))
        self.document_path = kwargs.get('document_path')
        self.prescription_path = kwargs.get('prescription_path')
        self.hospital_id = kwargs.get('hospital_id')
        self.department = kwargs.get('department')
        self.is_auto_assigned = kwargs.get('is_auto_assigned', False)
        self.staff_assigned_by = kwargs.get('staff_assigned_by')
        
        self.consultation_type = kwargs.get('consultation_type', 'Cross-Border Video Consultation')
        self.patient_country = kwargs.get('patient_country', 'India')
        self.doctor_country = kwargs.get('doctor_country', 'India')
        self.patient_timezone = kwargs.get('patient_timezone', 'IST (UTC+5:30)')
        self.doctor_timezone = kwargs.get('doctor_timezone', 'IST (UTC+5:30)')
        self.telemedicine_room_id = kwargs.get('telemedicine_room_id', f"DevAiConsult_Appt{self.id}")
        self.international_medical_notes = kwargs.get('international_medical_notes', '')
        fee_val = kwargs.get('fee_amount')
        self.fee_amount = float(fee_val) if fee_val is not None and str(fee_val).strip() != '' else 500.0

    @property
    def doctor(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('doctors', {}).get(self.doctor_id)

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('patients', {}).get(self.patient_id)


class PatientVital:
    def __init__(self, id, patient_id, weight=None, heart_rate=None, blood_sugar=None, systolic_bp=None, diastolic_bp=None, recorded_at=None, **kwargs):
        self.id = int(id or 0)
        self.patient_id = patient_id
        self.weight = float(weight) if (weight is not None and str(weight).strip() != '') else None
        self.heart_rate = int(heart_rate) if (heart_rate is not None and str(heart_rate).strip() != '') else None
        self.blood_sugar = int(blood_sugar) if (blood_sugar is not None and str(blood_sugar).strip() != '') else None
        self.systolic_bp = int(systolic_bp) if (systolic_bp is not None and str(systolic_bp).strip() != '') else None
        self.diastolic_bp = int(diastolic_bp) if (diastolic_bp is not None and str(diastolic_bp).strip() != '') else None
        
        dt = recorded_at or kwargs.get('recorded_at', utcnow())
        self.recorded_at = ensure_safe_date(dt)

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('patients', {}).get(self.patient_id)


class OrganRequest:
    def __init__(self, id, patient_id, patient_name, organ_needed, blood_group, urgency, status='active', hospital_id=None, **kwargs):
        self.id = id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.organ_needed = organ_needed
        self.blood_group = blood_group
        self.urgency = urgency
        self.status = status
        self.hospital_id = str(hospital_id) if hospital_id else None
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))


class LabRequest:
    def __init__(self, id, doctor_id, patient_id, patient_name, test_name, status='pending', notes='', **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.test_name = test_name
        self.status = status
        self.notes = notes
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))


class BedBooking:
    def __init__(self, id, hospital_id, patient_id, patient_name, patient_phone, bed_type, reason, status='pending', **kwargs):
        self.id = id
        self.hospital_id = hospital_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.patient_phone = patient_phone
        self.bed_type = bed_type
        self.reason = reason
        self.status = status
        self.room_number = kwargs.get('room_number')
        self.patient_country = kwargs.get('patient_country', 'India')
        self.is_international = kwargs.get('is_international', False)
        self.passport_number = kwargs.get('passport_number')
        self.medical_visa_needed = kwargs.get('medical_visa_needed', False)
        self.currency = kwargs.get('currency', 'INR')
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))

    @property
    def hospital(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('hospitals', {}).get(self.hospital_id)


class PatientMedicalRecord:
    """Represents a confidential medical record uploaded by a patient and selectively shared with doctors."""
    def __init__(self, id, patient_id, title, record_type='Lab Report', record_date=None, **kwargs):
        self.id = str(id)
        self.patient_id = str(patient_id)
        self.patient_name = kwargs.get('patient_name', '')
        self.title = title
        self.record_type = record_type  # 'Lab Report', 'Prescription', 'Radiology & Scan', 'Discharge Summary', 'Vaccination Certificate', 'Clinical Note', 'Other'
        self.record_date = record_date or datetime.now().strftime('%Y-%m-%d')
        self.doctor_name = kwargs.get('doctor_name', '')
        self.facility_name = kwargs.get('facility_name', '')
        self.description = kwargs.get('description', '')
        self.file_path = kwargs.get('file_path', '')
        self.file_name = kwargs.get('file_name', '')
        self.file_type = kwargs.get('file_type', 'pdf')
        self.file_size = kwargs.get('file_size', '0 KB')
        
        # Shared Doctors: List of doctor IDs who have been granted access
        shared_with_val = kwargs.get('shared_with', [])
        if isinstance(shared_with_val, str):
            try:
                import json
                self.shared_with = json.loads(shared_with_val)
            except Exception:
                self.shared_with = [s.strip() for s in shared_with_val.split(',') if s.strip()]
        elif isinstance(shared_with_val, list):
            self.shared_with = [str(x) for x in shared_with_val]
        else:
            self.shared_with = []

        # Doctor clinical review remarks: { "doctor_id": { "doctor_name": "...", "note": "...", "created_at": "..." } }
        doctor_notes_val = kwargs.get('doctor_notes', {})
        if isinstance(doctor_notes_val, str):
            try:
                import json
                self.doctor_notes = json.loads(doctor_notes_val)
            except Exception:
                self.doctor_notes = {}
        elif isinstance(doctor_notes_val, dict):
            self.doctor_notes = doctor_notes_val
        else:
            self.doctor_notes = {}

        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('patients', {}).get(self.patient_id)

    def is_shared_with(self, doctor_id):
        """Checks whether a specific doctor ID has authorized access to this medical record."""
        if not doctor_id:
            return False
        return str(doctor_id) in [str(d) for d in self.shared_with]

    def share_with_doctor(self, doctor_id):
        """Grants access to a doctor."""
        d_id = str(doctor_id)
        if d_id not in [str(d) for d in self.shared_with]:
            self.shared_with.append(d_id)

    def revoke_doctor_access(self, doctor_id):
        """Revokes access from a doctor."""
        d_id = str(doctor_id)
        self.shared_with = [d for d in self.shared_with if str(d) != d_id]

    def add_doctor_note(self, doctor_id, doctor_name, note):
        """Appends or updates clinical feedback from an attending doctor."""
        self.doctor_notes[str(doctor_id)] = {
            "doctor_id": str(doctor_id),
            "doctor_name": doctor_name,
            "note": note,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


class Job:
    def __init__(self, id, title, dept=None, department=None, location='Remote / Global', salary=None, salary_range=None, summary='', overview=None, full_desc=None, responsibilities=None, requirements=None, benefits=None, tech_stack=None, apply_deadline=None, is_active=True, is_hot=False, employment_type=None, experience=None, openings=1, created_at=None, **kwargs):
        self.id = int(id or 0) if str(id).isdigit() else id
        self.req_id = kwargs.get('req_id', f"REQ-2026-{self.id:02d}" if isinstance(self.id, int) else f"REQ-{self.id}")
        self.title = str(title).strip()
        
        dept_val = department or dept or 'Engineering & AI'
        self.department = str(dept_val).strip()
        dept_lower = self.department.lower()
        if 'ai' in dept_lower or 'eng' in dept_lower or 'tech' in dept_lower or 'dev' in dept_lower:
            self.dept = 'ai'
        elif 'clinic' in dept_lower or 'med' in dept_lower or 'oncol' in dept_lower or 'card' in dept_lower or 'doc' in dept_lower:
            self.dept = 'clinical'
        elif 'design' in dept_lower or 'product' in dept_lower or 'ux' in dept_lower:
            self.dept = 'product'
        elif 'secur' in dept_lower or 'hipaa' in dept_lower or 'cloud' in dept_lower:
            self.dept = 'security'
        else:
            self.dept = 'ops'
            
        self.dept_label = kwargs.get('dept_label') or self.department or self._get_dept_label(self.dept)
        self.employment_type = str(employment_type or kwargs.get('type') or 'Full-Time • Remote / Hybrid').strip()
        self.type = self.employment_type
        self.experience = str(experience or '2+ Years').strip()
        self.openings = int(openings or 1)
        self.location = str(location or 'Remote / Global').strip()
        self.salary_range = str(salary_range or salary or 'Competitive + Equity').strip()
        self.salary = self.salary_range
        self.overview = str(overview or summary or '').strip()
        self.summary = self.overview
        self.full_desc = str(full_desc or self.overview).strip()
        
        if isinstance(responsibilities, list):
            self.responsibilities = [str(r).strip() for r in responsibilities if str(r).strip()]
        elif isinstance(responsibilities, str) and responsibilities.strip():
            self.responsibilities = [r.strip() for r in responsibilities.split('\n') if r.strip()]
        else:
            self.responsibilities = []
            
        if isinstance(requirements, list):
            self.requirements = [str(r).strip() for r in requirements if str(r).strip()]
        elif isinstance(requirements, str) and requirements.strip():
            self.requirements = [r.strip() for r in requirements.split('\n') if r.strip()]
        else:
            self.requirements = []

        if isinstance(benefits, list):
            self.benefits = [str(b).strip() for b in benefits if str(b).strip()]
        elif isinstance(benefits, str) and benefits.strip():
            self.benefits = [b.strip() for b in benefits.split('\n') if b.strip()]
        else:
            self.benefits = []
            
        if isinstance(tech_stack, list):
            self.tech_stack = [str(t).strip() for t in tech_stack if str(t).strip()]
        elif isinstance(tech_stack, str) and tech_stack.strip():
            self.tech_stack = [t.strip() for t in tech_stack.split(',') if t.strip()]
        else:
            self.tech_stack = [r for r in self.requirements[:4]] if self.requirements else ['Healthcare Systems', 'Clinical AI']

        self.apply_deadline = ensure_safe_date(apply_deadline) if apply_deadline else None
        self.is_active = bool(is_active)
        self.is_hot = bool(is_hot) or (self.openings > 1)
        self.created_at = ensure_safe_date(created_at or utcnow())
        self.applications_count = int(kwargs.get('applications_count', 0))

    def _get_dept_label(self, d):
        mapping = {
            'ai': 'Engineering & AI',
            'clinical': 'Clinical Science & MD',
            'product': 'Product & Systems Design',
            'security': 'HIPAA & Cloud Security',
            'ops': 'Hospital & Clinic Operations'
        }
        return mapping.get(str(d).lower(), 'General')

    @property
    def is_expired(self):
        """Returns True if the application deadline has passed, meaning the job should automatically hide."""
        if not self.apply_deadline:
            return False
        try:
            today = datetime.now().date()
            if isinstance(self.apply_deadline, datetime):
                return self.apply_deadline.date() < today
            elif hasattr(self.apply_deadline, 'year') and hasattr(self.apply_deadline, 'month') and hasattr(self.apply_deadline, 'day'):
                return self.apply_deadline < today
            elif isinstance(self.apply_deadline, str):
                cleaned = self.apply_deadline.split('T')[0].split(' ')[0]
                dl = datetime.strptime(cleaned, '%Y-%m-%d').date()
                return dl < today
        except Exception:
            return False
        return False

    @property
    def deadline_formatted(self):
        if not self.apply_deadline:
            return "Open until filled"
        try:
            if isinstance(self.apply_deadline, datetime):
                return self.apply_deadline.strftime("%b %d, %Y")
            elif hasattr(self.apply_deadline, 'strftime'):
                return self.apply_deadline.strftime("%b %d, %Y")
            elif isinstance(self.apply_deadline, str):
                cleaned = self.apply_deadline.split('T')[0].split(' ')[0]
                dt = datetime.strptime(cleaned, '%Y-%m-%d')
                return dt.strftime("%b %d, %Y")
        except Exception:
            return str(self.apply_deadline)
        return str(self.apply_deadline)

    def to_dict(self):
        deadline_str = ''
        if self.apply_deadline:
            if hasattr(self.apply_deadline, 'strftime'):
                deadline_str = self.apply_deadline.strftime('%Y-%m-%d')
            else:
                deadline_str = str(self.apply_deadline).split('T')[0].split(' ')[0]

        return {
            'id': self.id,
            'reqId': self.req_id,
            'title': self.title,
            'dept': self.dept,
            'department': self.department,
            'deptLabel': self.dept_label,
            'type': self.type,
            'employmentType': self.employment_type,
            'experience': self.experience,
            'openings': self.openings,
            'location': self.location,
            'salary': self.salary,
            'salaryRange': self.salary_range,
            'summary': self.summary,
            'overview': self.overview,
            'fullDesc': self.full_desc,
            'responsibilities': self.responsibilities,
            'requirements': self.requirements,
            'benefits': self.benefits,
            'techStack': self.tech_stack,
            'apply_deadline': deadline_str,
            'applyDeadline': deadline_str,
            'deadline_formatted': self.deadline_formatted,
            'deadlineFormatted': self.deadline_formatted,
            'isActive': self.is_active,
            'is_active': self.is_active,
            'isHot': self.is_hot,
            'is_hot': self.is_hot,
            'isExpired': self.is_expired,
            'is_expired': self.is_expired,
            'applicationsCount': self.applications_count
        }


class JobApplication:
    def __init__(self, id, job_id, applicant_name=None, candidate_name=None, email=None, candidate_email=None, phone='', experience_years='', current_company='', linkedin_portfolio='', candidate_url=None, resume_link='', cover_note='', note='', status='Pending Review', created_at=None, **kwargs):
        self.id = int(id or 0) if str(id).isdigit() else id
        self.job_id = int(job_id or 0) if str(job_id).isdigit() else job_id
        self.applicant_name = str(applicant_name or candidate_name or '').strip()
        self.candidate_name = self.applicant_name
        self.email = str(email or candidate_email or '').strip().lower()
        self.candidate_email = self.email
        self.phone = str(phone or '').strip()
        self.experience_years = str(experience_years or kwargs.get('experience') or '').strip()
        self.current_company = str(current_company or kwargs.get('company') or '').strip()
        self.linkedin_portfolio = str(linkedin_portfolio or candidate_url or kwargs.get('portfolio') or '').strip()
        self.candidate_url = self.linkedin_portfolio
        self.resume_link = str(resume_link or kwargs.get('resume') or '').strip()
        self.cover_note = str(cover_note or note or '').strip()
        self.note = self.cover_note
        self.status = str(status or 'Pending Review').strip()
        self.created_at = ensure_safe_date(created_at or utcnow())
        self.job_title = kwargs.get('job_title', '')

    def to_dict(self):
        return {
            'id': self.id,
            'jobId': self.job_id,
            'job_id': self.job_id,
            'jobTitle': self.job_title,
            'job_title': self.job_title,
            'applicantName': self.applicant_name,
            'applicant_name': self.applicant_name,
            'candidateName': self.applicant_name,
            'email': self.email,
            'candidateEmail': self.email,
            'phone': self.phone,
            'experienceYears': self.experience_years,
            'experience_years': self.experience_years,
            'currentCompany': self.current_company,
            'current_company': self.current_company,
            'linkedinPortfolio': self.linkedin_portfolio,
            'linkedin_portfolio': self.linkedin_portfolio,
            'candidateUrl': self.linkedin_portfolio,
            'resumeLink': self.resume_link,
            'resume_link': self.resume_link,
            'coverNote': self.cover_note,
            'cover_note': self.cover_note,
            'note': self.cover_note,
            'status': self.status,
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(self.created_at, 'strftime') else str(self.created_at),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(self.created_at, 'strftime') else str(self.created_at)
        }



