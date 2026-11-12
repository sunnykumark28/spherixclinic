import json
import random
from datetime import datetime
from flask_login import UserMixin
from spherix.config import (
    utcnow, GLOBAL_COUNTRY_FLAGS, GLOBAL_COUNTRY_TIMEZONES,
    format_dual_currency, generate_user_license_id, ensure_safe_date
)

class Doctor(UserMixin):
    def __init__(self, id, first_name, last_name, email, password, department, **kwargs):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.department = department
        self.phone = kwargs.get('phone')
        self.specialization = kwargs.get('specialization')
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.profile_picture_data = kwargs.get('profile_picture_data')
        self.profile_picture_content_type = kwargs.get('profile_picture_content_type')
        self.cover_image_url = kwargs.get('cover_image_url')
        self.address = kwargs.get('address')
        self.bio = kwargs.get('bio')
        self.hospital_name = kwargs.get('hospital_name')
        self.hospital_address = kwargs.get('hospital_address')
        self.state = kwargs.get('state')
        self.city = kwargs.get('city')
        self.district = kwargs.get('district')

        self.pincode = kwargs.get('pincode')
        self.country = kwargs.get('country', 'India')
        self.is_international = kwargs.get('is_international', str(self.country).strip().lower() not in ['india', 'in'])
        self.currency = kwargs.get('currency', 'USD' if self.is_international else 'INR')
        self.timezone = kwargs.get('timezone', GLOBAL_COUNTRY_TIMEZONES.get(self.country, 'IST (UTC+5:30)'))
        self.international_accreditation = kwargs.get('international_accreditation', 'JCI Accredited & ABIM Certified' if self.is_international else 'NMC / MCI Certified Specialist')
        self.telemedicine_modes = kwargs.get('telemedicine_modes', ['Cross-Border HD Video Telemedicine', 'International Second Opinion', 'E-Prescription Desk'])
        self.languages_spoken = kwargs.get('languages_spoken', 'English, Hindi' if self.country == 'India' else 'English, Spanish, Arabic')

        self.qualification = kwargs.get('qualification')
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or generate_user_license_id('doctor')
        self.license_no = self.license_number
        self.experience = kwargs.get('experience')
        self.consultation_type = kwargs.get('consultation_type', 'Cross-Border Video Consultation' if self.is_international else 'In-Person & Online')
        self.working_hours = kwargs.get('working_hours', '09:00 AM - 05:00 PM')
        
        # Social links & Extended Profile Details
        raw_social = kwargs.get('social_links', {})
        if isinstance(raw_social, str):
            try:
                self.social_links = json.loads(raw_social)
            except Exception:
                self.social_links = {}
        elif isinstance(raw_social, dict):
            self.social_links = dict(raw_social)
        else:
            self.social_links = {}

        pd = self.social_links.get('profile_details', {}) if isinstance(self.social_links, dict) else {}

        self.cover_image_url = kwargs.get('cover_image_url') or pd.get('cover_image_url') or self.cover_image_url or ''
        self.consultation_fee = kwargs.get('consultation_fee') or pd.get('consultation_fee')

        self.secondary_specialization = kwargs.get('secondary_specialization') or pd.get('secondary_specialization') or ''
        self.medical_degrees = kwargs.get('medical_degrees') or pd.get('medical_degrees') or self.qualification or ''
        self.university_name = kwargs.get('university_name') or pd.get('university_name') or ''
        self.graduation_year = kwargs.get('graduation_year') or pd.get('graduation_year') or ''
        self.certifications = kwargs.get('certifications') or pd.get('certifications') or ''
        self.fellowships = kwargs.get('fellowships') or pd.get('fellowships') or ''
        self.career_summary = kwargs.get('career_summary') or pd.get('career_summary') or ''
        self.treatment_philosophy = kwargs.get('treatment_philosophy') or pd.get('treatment_philosophy') or ''
        self.conditions_treated = kwargs.get('conditions_treated') or pd.get('conditions_treated') or ''
        self.treatments_offered = kwargs.get('treatments_offered') or pd.get('treatments_offered') or ''
        self.follow_up_fee = kwargs.get('follow_up_fee') or pd.get('follow_up_fee')
        self.video_fee = kwargs.get('video_fee') or pd.get('video_fee')
        self.appointment_duration = kwargs.get('appointment_duration') or pd.get('appointment_duration') or ''
        self.opd_schedule = kwargs.get('opd_schedule') or pd.get('opd_schedule') or ''
        self.awards = kwargs.get('awards') or pd.get('awards') or ''
        self.publications = kwargs.get('publications') or pd.get('publications') or ''
        self.memberships = kwargs.get('memberships') or pd.get('memberships') or ''
        self.patient_instructions = kwargs.get('patient_instructions') or pd.get('patient_instructions') or ''
        self.faqs_custom = kwargs.get('faqs_custom') or pd.get('faqs_custom') or ''
        self.whatsapp_number = kwargs.get('whatsapp_number') or pd.get('whatsapp_number') or self.phone or ''

        # Comprehensive Profile & Practice Attributes (Sections A-H)
        self.title = kwargs.get('title') or pd.get('title') or 'Dr.'
        self.gender = kwargs.get('gender') or pd.get('gender') or ''
        self.dob = kwargs.get('dob') or pd.get('dob') or ''
        self.mbbs_degree = kwargs.get('mbbs_degree') or pd.get('mbbs_degree') or ''
        self.higher_degree = kwargs.get('higher_degree') or pd.get('higher_degree') or (self.qualification or '')
        self.college_name = kwargs.get('college_name') or pd.get('college_name') or ''
        self.medical_council_reg = kwargs.get('medical_council_reg') or pd.get('medical_council_reg') or self.license_number or ''
        self.medical_training = kwargs.get('medical_training') or pd.get('medical_training') or ''
        self.previous_hospitals = kwargs.get('previous_hospitals') or pd.get('previous_hospitals') or ''
        self.previous_employment = kwargs.get('previous_employment') or pd.get('previous_employment') or ''
        self.professional_experience = kwargs.get('professional_experience') or pd.get('professional_experience') or ''
        self.areas_of_expertise = kwargs.get('areas_of_expertise') or pd.get('areas_of_expertise') or ''
        self.sub_specializations = kwargs.get('sub_specializations') or pd.get('sub_specializations') or ''
        self.diseases_diagnosed = kwargs.get('diseases_diagnosed') or pd.get('diseases_diagnosed') or ''
        self.medical_procedures = kwargs.get('medical_procedures') or pd.get('medical_procedures') or ''
        self.preventive_healthcare = kwargs.get('preventive_healthcare') or pd.get('preventive_healthcare') or ''
        self.patient_counselling = kwargs.get('patient_counselling') or pd.get('patient_counselling') or ''
        self.diagnostic_services = kwargs.get('diagnostic_services') or pd.get('diagnostic_services') or ''
        self.clinic_name = kwargs.get('clinic_name') or pd.get('clinic_name') or ''
        self.clinic_address = kwargs.get('clinic_address') or pd.get('clinic_address') or ''
        self.hospital_affiliations = kwargs.get('hospital_affiliations') or pd.get('hospital_affiliations') or ''
        self.consultation_location = kwargs.get('consultation_location') or pd.get('consultation_location') or ''
        self.weekly_availability = kwargs.get('weekly_availability') or pd.get('weekly_availability') or ''
        self.available_slots = kwargs.get('available_slots') or pd.get('available_slots') or ''
        self.gallery_urls = kwargs.get('gallery_urls') or pd.get('gallery_urls') or ''
        self.clinic_photos = kwargs.get('clinic_photos') or pd.get('clinic_photos') or ''
        self.hospital_photos = kwargs.get('hospital_photos') or pd.get('hospital_photos') or ''
        self.event_photos = kwargs.get('event_photos') or pd.get('event_photos') or ''
        self.certificate_urls = kwargs.get('certificate_urls') or pd.get('certificate_urls') or ''
        self.video_urls = kwargs.get('video_urls') or pd.get('video_urls') or ''
        self.achievements = kwargs.get('achievements') or pd.get('achievements') or ''
        self.research_papers = kwargs.get('research_papers') or pd.get('research_papers') or ''
        self.medical_conferences = kwargs.get('medical_conferences') or pd.get('medical_conferences') or ''
        self.healthcare_contributions = kwargs.get('healthcare_contributions') or pd.get('healthcare_contributions') or ''
        self.honours = kwargs.get('honours') or pd.get('honours') or ''
        
        # Publishing & Verification State
        self.publishing_status = kwargs.get('publishing_status') or pd.get('publishing_status') or ('published' if kwargs.get('is_verified') else 'published')
        self._slug = kwargs.get('slug') or pd.get('slug')
        self.created_at = kwargs.get('created_at') or pd.get('created_at') or utcnow().isoformat()
        self.updated_at = kwargs.get('updated_at') or pd.get('updated_at') or utcnow().isoformat()

        self.is_verified = kwargs.get('is_verified', False)
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_doctor = True
        self.is_patient = False
        self.is_hospital = False
        self.is_staff = False
        self.is_blood_donor = False
        self.is_organ_donor = False
        self.role = 'Doctor'
        self.availability_status = kwargs.get('availability_status', 'available')
        self.hospital_id = kwargs.get('hospital_id')
        self.latitude = kwargs.get('latitude')
        self.longitude = kwargs.get('longitude')
        self.hospital_approval_status = kwargs.get('hospital_approval_status', 'approved' if kwargs.get('hospital_name') else None)

    def get_id(self):
        return f"doctor-{self.id}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def country_flag(self):
        return GLOBAL_COUNTRY_FLAGS.get(self.country, '🌍')

    @property
    def formatted_fee(self):
        if self.consultation_fee is None or str(self.consultation_fee).strip() == '':
            return None
        try:
            val = float(self.consultation_fee)
            if val == 0:
                return "Free"
            return format_dual_currency(val, self.currency)
        except (ValueError, TypeError):
            return None

    @property
    def formatted_follow_up_fee(self):
        if self.follow_up_fee is None or str(self.follow_up_fee).strip() == '':
            return None
        try:
            val = float(self.follow_up_fee)
            if val == 0:
                return "Free"
            return format_dual_currency(val, self.currency)
        except (ValueError, TypeError):
            return None

    @property
    def formatted_video_fee(self):
        if self.video_fee is None or str(self.video_fee).strip() == '':
            return None
        try:
            val = float(self.video_fee)
            if val == 0:
                return "Free"
            return format_dual_currency(val, self.currency)
        except (ValueError, TypeError):
            return None

    @property
    def profile_completion_pct(self):
        checks = [
            bool(self.first_name and self.last_name),
            bool(self.profile_picture_url or getattr(self, 'profile_picture_data', None)),
            bool(self.email),
            bool(self.phone),
            bool(self.department),
            bool(self.specialization),
            bool(self.qualification),
            bool(self.license_number),
            bool(self.hospital_name),
            bool(self.city or self.district),
            bool(self.bio),
            bool(self.languages_spoken),
            bool(self.working_hours),
            bool(self.consultation_fee)
        ]
        completed = sum(1 for c in checks if c)
        return max(75, min(100, int((completed / len(checks)) * 100)))

    @property
    def conditions_list(self):
        if self.conditions_treated:
            return [c.strip() for c in self.conditions_treated.replace(';', ',').split(',') if c.strip()]
        return []

    @property
    def treatments_list(self):
        if self.treatments_offered:
            return [t.strip() for t in self.treatments_offered.replace(';', ',').split(',') if t.strip()]
        return []

    @property
    def awards_list(self):
        if self.awards:
            return [a.strip() for a in self.awards.replace(';', ',').split(',') if a.strip()]
        return []

    @property
    def publications_list(self):
        if self.publications:
            return [p.strip() for p in self.publications.replace('\n', ';').split(';') if p.strip()]
        return []

    @property
    def memberships_list(self):
        if self.memberships:
            return [m.strip() for m in self.memberships.replace(';', ',').split(',') if m.strip()]
        return []

    @property
    def certifications_list(self):
        if self.certifications:
            return [c.strip() for c in self.certifications.replace(';', ',').split(',') if c.strip()]
        return []

    @property
    def faqs_list(self):
        if getattr(self, 'faqs_custom', None):
            try:
                import json
                parsed = json.loads(self.faqs_custom)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        items = []
        if getattr(self, 'patient_instructions', None):
            items.append({
                "q": "What medical documents should I bring to the consultation?",
                "a": self.patient_instructions
            })
        if getattr(self, 'consultation_type', None) and ('video' in self.consultation_type.lower() or 'online' in self.consultation_type.lower() or getattr(self, 'is_international', False)):
            items.append({
                "q": "Is video telemedicine available for international or outstation patients?",
                "a": f"Yes. {self.full_title_name} provides 256-bit encrypted HD video consultations with digital prescription delivery."
            })
        return items

    @property
    def reviews(self):
        from spherix.services.database import TEMP_DATA
        return sorted([review for review in TEMP_DATA.get('reviews', {}).values() if review.doctor_id == self.id], key=lambda r: r.created_at, reverse=True)

    @property
    def average_rating(self):
        reviews = self.reviews
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def appointments(self):
        from spherix.services.database import TEMP_DATA
        return [appt for appt in TEMP_DATA.get('appointments', {}).values() if appt.doctor_id == self.id]

    @property
    def messages(self):
        from spherix.services.database import TEMP_DATA
        return [msg for msg in TEMP_DATA.get('messages', {}).values() if msg.doctor_id == self.id]

    @property
    def full_title_name(self):
        t = (getattr(self, 'title', None) or 'Dr.').strip()
        n = self.name.strip()
        if n.lower().startswith('dr.') or n.lower().startswith('dr '):
            return n
        return f"{t} {n}"

    @property
    def slug(self):
        if getattr(self, '_slug', None):
            return self._slug
        import re
        t = (getattr(self, 'title', None) or 'dr').strip().lower().replace('.', '')
        base = f"{t}-{self.first_name}-{self.last_name}".strip()
        clean = re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')
        if not clean or clean == 'dr':
            clean = f"doctor-{str(self.id).replace('/', '-').lower()}"
        return clean

    @property
    def is_publicly_visible(self):
        status = getattr(self, 'publishing_status', 'published')
        is_blocked = getattr(self, 'is_blocked', False)
        is_hidden = getattr(self, 'is_hidden', False)
        return (status in ['published', 'approved']) and not is_hidden and not is_blocked

    @property
    def procedures_list(self):
        raw = getattr(self, 'medical_procedures', None) or getattr(self, 'treatments_offered', None) or ''
        if raw:
            return [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
        return []

    @property
    def sub_specializations_list(self):
        raw = getattr(self, 'sub_specializations', None) or getattr(self, 'secondary_specialization', None) or ''
        if raw:
            return [s.strip() for s in raw.replace(';', ',').split(',') if s.strip()]
        return []

    @property
    def diseases_list(self):
        raw = getattr(self, 'diseases_diagnosed', None) or getattr(self, 'conditions_treated', None) or ''
        if raw:
            return [d.strip() for d in raw.replace(';', ',').split(',') if d.strip()]
        return self.conditions_list

    @property
    def preventive_list(self):
        raw = getattr(self, 'preventive_healthcare', None) or ''
        if raw:
            return [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
        return []

    @property
    def counselling_list(self):
        raw = getattr(self, 'patient_counselling', None) or ''
        if raw:
            return [c.strip() for c in raw.replace(';', ',').split(',') if c.strip()]
        return []

    @property
    def diagnostic_list(self):
        raw = getattr(self, 'diagnostic_services', None) or ''
        if raw:
            return [d.strip() for d in raw.replace(';', ',').split(',') if d.strip()]
        return []

    @property
    def affiliations_list(self):
        raw = getattr(self, 'hospital_affiliations', None) or ''
        items = []
        if getattr(self, 'hospital_name', None):
            items.append(self.hospital_name)
        if raw:
            for aff in raw.replace(';', ',').split(','):
                a = aff.strip()
                if a and a not in items:
                    items.append(a)
        return items

    @property
    def gallery_list(self):
        urls = []
        raw = getattr(self, 'gallery_urls', None) or ''
        if raw:
            urls.extend([u.strip() for u in raw.replace('\n', ',').split(',') if u.strip()])
        return urls

    @property
    def clinic_photos_list(self):
        raw = getattr(self, 'clinic_photos', None) or ''
        if raw:
            return [u.strip() for u in raw.replace('\n', ',').split(',') if u.strip()]
        return []

    @property
    def hospital_photos_list(self):
        raw = getattr(self, 'hospital_photos', None) or ''
        if raw:
            return [u.strip() for u in raw.replace('\n', ',').split(',') if u.strip()]
        return []

    @property
    def event_photos_list(self):
        raw = getattr(self, 'event_photos', None) or ''
        if raw:
            return [u.strip() for u in raw.replace('\n', ',').split(',') if u.strip()]
        return []

    @property
    def certificates_list(self):
        raw = getattr(self, 'certificate_urls', None) or ''
        if raw:
            return [u.strip() for u in raw.replace('\n', ',').split(',') if u.strip()]
        return []

    @property
    def videos_list(self):
        raw = getattr(self, 'video_urls', None) or ''
        if raw:
            return [u.strip() for u in raw.replace('\n', ',').split(',') if u.strip()]
        return []

    @property
    def research_papers_list(self):
        raw = getattr(self, 'research_papers', None) or ''
        if raw:
            return [p.strip() for p in raw.replace('\n', ';').split(';') if p.strip()]
        return self.publications_list

    @property
    def conferences_list(self):
        raw = getattr(self, 'medical_conferences', None) or ''
        if raw:
            return [c.strip() for c in raw.replace('\n', ';').split(';') if c.strip()]
        return []

    @property
    def cover_display_url(self):
        cov = getattr(self, 'cover_image_url', None)
        if cov:
            p = str(cov).strip()
            if p.startswith('http://') or p.startswith('https://') or p.startswith('/static/'):
                return p
            if p.startswith('doctor_covers/') or p.startswith('hospital_covers/'):
                return f"/static/uploads/{p}"
            return f"/static/uploads/{p}"
        # If doctor has clinic photos or gallery photos
        if hasattr(self, 'clinic_photos_list') and self.clinic_photos_list:
            return self.clinic_photos_list[0]
        if hasattr(self, 'gallery_list') and self.gallery_list:
            return self.gallery_list[0]
        if hasattr(self, 'hospital_photos_list') and self.hospital_photos_list:
            return self.hospital_photos_list[0]
        return None

    @property
    def contributions_list(self):
        raw = getattr(self, 'healthcare_contributions', None) or ''
        if raw:
            return [c.strip() for c in raw.replace('\n', ';').split(';') if c.strip()]
        return []

    @property
    def honours_list(self):
        raw = getattr(self, 'honours', None) or ''
        if raw:
            return [h.strip() for h in raw.replace('\n', ',').split(',') if h.strip()]
        return self.awards_list

    @property
    def available_slots_list(self):
        raw = getattr(self, 'available_slots', None) or ''
        if raw:
            return [s.strip() for s in raw.replace(';', ',').split(',') if s.strip()]
        return []

    @property
    def previous_hospitals_list(self):
        raw = getattr(self, 'previous_hospitals', None) or ''
        if raw:
            return [h.strip() for h in raw.replace(';', ',').split(',') if h.strip()]
        return []

    @property
    def previous_employment_list(self):
        raw = getattr(self, 'previous_employment', None) or ''
        if raw:
            return [e.strip() for e in raw.replace('\n', ';').split(';') if e.strip()]
        return []

    @property
    def areas_of_expertise_list(self):
        raw = getattr(self, 'areas_of_expertise', None) or ''
        if raw:
            return [e.strip() for e in raw.replace(';', ',').split(',') if e.strip()]
        if self.specialization:
            specs = [self.specialization]
            if self.sub_specializations_list:
                specs.extend(self.sub_specializations_list)
            return specs
        return []



class Patient(UserMixin):
    def __init__(self, id, name, email, password, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.age = kwargs.get('age')
        self.gender = kwargs.get('gender')
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.profile_picture_data = kwargs.get('profile_picture_data')
        self.profile_picture_content_type = kwargs.get('profile_picture_content_type')
        self.phone = kwargs.get('phone')
        self.address = kwargs.get('address')
        self.country = kwargs.get('country', 'India')
        self.preferred_currency = kwargs.get('preferred_currency', 'INR')
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or kwargs.get('health_id') or generate_user_license_id('patient')
        self.license_no = self.license_number
        self.health_id = self.license_number
        self.is_verified = bool(kwargs.get('is_verified', False))
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_patient = True
        self.is_doctor = False
        self.is_hospital = False
        self.is_blood_donor = False
        self.is_organ_donor = False
        self.is_staff = False
        self.role = 'Patient'
        
        import json
        self.clinical_record = kwargs.get('clinical_record')
        if isinstance(self.clinical_record, str):
            try:
                self.clinical_record = json.loads(self.clinical_record)
            except:
                self.clinical_record = {}
        elif not isinstance(self.clinical_record, dict):
            self.clinical_record = {}

    def get_id(self):
        return f"patient-{self.id}"

    @property
    def appointments(self):
        from spherix.services.database import TEMP_DATA
        return [
            appt for appt in TEMP_DATA.get('appointments', {}).values()
            if appt.patient_id == self.id or (appt.patient_phone and self.phone and str(appt.patient_phone).strip() == str(self.phone).strip())
        ]


class Staff(UserMixin):
    def __init__(self, id, name, email, password, role, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role
        self.phone = kwargs.get('phone')
        self.hospital_name = kwargs.get('hospital_name')
        self.hospital_id = kwargs.get('hospital_id')
        self.created_at = kwargs.get('created_at', utcnow())
        self.last_login = kwargs.get('last_login')
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or f"STAFF-REG-{datetime.now().year}-{random.randint(10000, 99999)}"
        self.license_no = self.license_number
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.is_doctor = False
        self.is_staff = True
        self.is_hospital = False
        self.is_patient = False
        self.is_blood_donor = False
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.profile_picture_data = kwargs.get('profile_picture_data')
        self.profile_picture_content_type = kwargs.get('profile_picture_content_type')
        self.shift = kwargs.get('shift', 'Day Shift (08:00 - 16:00)')
        self.department = kwargs.get('department', self.role)
        self.on_duty = kwargs.get('on_duty', True)

    def get_id(self):
        return f"staff-{self.id}"

    @property
    def hospital(self):
        from spherix.services.database import TEMP_DATA
        h_id = getattr(self, 'hospital_id', None)
        h_name = getattr(self, 'hospital_name', None)
        if h_id and str(h_id) in TEMP_DATA.get('hospitals', {}):
            return TEMP_DATA['hospitals'][str(h_id)]
        if h_id:
            h = next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(getattr(h, 'id', '')) == str(h_id)), None)
            if h: return h
        if h_name:
            return next((h for h in TEMP_DATA.get('hospitals', {}).values() if (getattr(h, 'name', '') or '').lower().strip() == h_name.lower().strip()), None)
        return None

    @property
    def appointments(self):
        return []

HospitalStaff = Staff


class Hospital(UserMixin):
    def __init__(self, id, name, email, password, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.logo_url = kwargs.get('logo_url')
        self.phone = kwargs.get('phone')
        self.emergency_phone = kwargs.get('emergency_phone') or self.phone or '102'
        self.ambulance_phone = kwargs.get('ambulance_phone') or self.phone or '108'
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or kwargs.get('licenseNo') or generate_user_license_id('hospital')
        self.license_no = self.license_number
        self.president_ceo = kwargs.get('president_ceo') or kwargs.get('director_name') or kwargs.get('md_name') or ''
        self.director_name = self.president_ceo
        self.superintendent_name = kwargs.get('superintendent_name') or kwargs.get('doctor_name') or kwargs.get('blood_bank_staff') or ''
        self.blood_bank_staff = self.superintendent_name
        self.city = kwargs.get('city')
        self.state = kwargs.get('state')
        self.zip_code = kwargs.get('zip_code')
        self.country = kwargs.get('country', 'India')
        self.is_international = kwargs.get('is_international', str(self.country).strip().lower() not in ['india', 'in'])
        self.currency = kwargs.get('currency', 'USD' if self.is_international else 'INR')
        self.timezone = kwargs.get('timezone', GLOBAL_COUNTRY_TIMEZONES.get(self.country, 'IST (UTC+5:30)'))
        self.total_beds = int(kwargs.get('total_beds') or 0)
        self.available_beds = int(kwargs.get('available_beds') or 0)
        self.icu_beds = int(kwargs.get('icu_beds') or 0)
        self.available_icu_beds = int(kwargs.get('available_icu_beds') or 0)
        self.doctors_available = kwargs.get('doctors_available') or 'Available'
        self.address = kwargs.get('address')
        
        raw_gen = kwargs.get('general_bed_fee')
        self.general_bed_fee = float(raw_gen) if raw_gen is not None and str(raw_gen).strip() != '' else None
        raw_icu = kwargs.get('icu_bed_fee')
        self.icu_bed_fee = float(raw_icu) if raw_icu is not None and str(raw_icu).strip() != '' else None
        
        self.is_verified = bool(kwargs.get('is_verified', False))
        self.is_blocked = bool(kwargs.get('is_blocked', False))
        self.is_hidden = bool(kwargs.get('is_hidden', False))
        self.is_doctor = False
        self.is_hospital = True
        self.is_patient = False
        self.is_blood_donor = False
        self.is_organ_donor = False
        self.is_staff = False
        self.role = 'Hospital'
        self.accreditation = kwargs.get('accreditation') or ''
        self.international_services = kwargs.get('international_services', [
            'Medical Visa Assistance & Invitation Letters',
            'Dedicated Airport Pickup & Patient Transfer',
            'Multi-Language Medical Translators (Arabic, Russian, French)',
            'International Direct Health Insurance Billing',
            'VIP International Patient Suites & Telehealth Follow-ups'
        ])
        self.international_bed_booking_enabled = kwargs.get('international_bed_booking_enabled', True)
        self.blood_stock = kwargs.get('blood_stock', {
            "A+": 0, "A-": 0, "B+": 0, "B-": 0, "AB+": 0, "AB-": 0, "O+": 0, "O-": 0
        })

        # Hospital Type Classification & Advanced Attributes
        from spherix.hospital_types import get_hospital_types_master_dict, get_default_hospital_type
        
        type_id_raw = kwargs.get('hospital_type_id')
        if type_id_raw is not None and str(type_id_raw).isdigit():
            self.hospital_type_id = int(type_id_raw)
        else:
            default_t = get_default_hospital_type(self.name)
            self.hospital_type_id = default_t.id

        self.hospital_type = kwargs.get('hospital_type') or kwargs.get('facility_type') or (get_hospital_types_master_dict().get(self.hospital_type_id).name if self.hospital_type_id in get_hospital_types_master_dict() else 'General Hospital')
        self.custom_hospital_type = kwargs.get('custom_hospital_type', '')
        
        # Parse Specialties
        raw_specs = kwargs.get('specialties')
        if isinstance(raw_specs, list):
            self.specialties = raw_specs
        elif isinstance(raw_specs, str) and raw_specs.strip():
            import json
            try:
                self.specialties = json.loads(raw_specs)
            except Exception:
                self.specialties = [s.strip() for s in raw_specs.split(',') if s.strip()]
        else:
            self.specialties = []

        # Parse Facilities
        raw_facs = kwargs.get('facilities')
        if isinstance(raw_facs, list):
            self.facilities = raw_facs
        elif isinstance(raw_facs, str) and raw_facs.strip():
            import json
            try:
                self.facilities = json.loads(raw_facs)
            except Exception:
                self.facilities = [f.strip() for f in raw_facs.split(',') if f.strip()]
        else:
            self.facilities = []

        self.emergency_services = bool(kwargs.get('emergency_services', True))
        self.about = kwargs.get('about') or kwargs.get('bio') or ''
        
        # Geolocation Coordinates
        try:
            self.latitude = float(kwargs.get('latitude')) if kwargs.get('latitude') is not None else None
            self.longitude = float(kwargs.get('longitude')) if kwargs.get('longitude') is not None else None
        except (ValueError, TypeError):
            self.latitude = None
            self.longitude = None

        # Extended Profile & Facility Management Specifications
        self.cover_image_url = kwargs.get('cover_image_url')
        self.establishment_year = str(kwargs.get('establishment_year') or '').strip()
        self.website = kwargs.get('website') or ''
        self.google_maps_url = kwargs.get('google_maps_url') or ''
        self.infrastructure = kwargs.get('infrastructure') or ''
        
        # Ward-wise Bed Breakdown
        self.general_beds = int(kwargs.get('general_beds') or max(0, self.total_beds - self.icu_beds))
        self.available_general_beds = int(kwargs.get('available_general_beds') or max(0, self.available_beds - self.available_icu_beds))
        self.private_beds = int(kwargs.get('private_beds') or 0)
        self.available_private_beds = int(kwargs.get('available_private_beds') or 0)
        self.nicu_beds = int(kwargs.get('nicu_beds') or 0)
        self.available_nicu_beds = int(kwargs.get('available_nicu_beds') or 0)
        self.picu_beds = int(kwargs.get('picu_beds') or 0)
        self.available_picu_beds = int(kwargs.get('available_picu_beds') or 0)
        self.emergency_beds = int(kwargs.get('emergency_beds') or 0)
        self.available_emergency_beds = int(kwargs.get('available_emergency_beds') or 0)
        self.operation_theatres = int(kwargs.get('operation_theatres') or 0)
        self.available_ot = int(kwargs.get('available_ot') or 0)
        
        # Recalculate total beds if general beds provided
        if self.general_beds > 0 and self.total_beds == 0:
            self.total_beds = self.general_beds + self.icu_beds + self.private_beds
            self.available_beds = self.available_general_beds + self.available_icu_beds + self.available_private_beds

        # Clinical Infrastructure, Equipment & Diagnostic Scope
        self.medical_equipment = kwargs.get('medical_equipment') or ''
        self.diagnostic_services = kwargs.get('diagnostic_services') or ''
        self.laboratory_facilities = kwargs.get('laboratory_facilities') or ''
        self.blood_bank_available = bool(kwargs.get('blood_bank_available', False))
        self.pharmacy_available = bool(kwargs.get('pharmacy_available', False))
        self.pharmacy_hours = kwargs.get('pharmacy_hours') or ''
        self.ambulance_services = bool(kwargs.get('ambulance_services', False))
        self.ambulance_count = int(kwargs.get('ambulance_count') or 0)
        
        # Pricing, Rates & Insurance
        raw_fee = kwargs.get('consultation_fee')
        self.consultation_fee = float(raw_fee) if raw_fee is not None and str(raw_fee).strip() != '' else None
        raw_pvt = kwargs.get('private_bed_fee')
        self.private_bed_fee = float(raw_pvt) if raw_pvt is not None and str(raw_pvt).strip() != '' else None
        raw_adm = kwargs.get('admission_charge')
        self.admission_charge = float(raw_adm) if raw_adm is not None and str(raw_adm).strip() != '' else None
        raw_fu = kwargs.get('follow_up_fee')
        self.follow_up_fee = float(raw_fu) if raw_fu is not None and str(raw_fu).strip() != '' else None
        raw_emg = kwargs.get('emergency_bed_fee')
        self.emergency_bed_fee = float(raw_emg) if raw_emg is not None and str(raw_emg).strip() != '' else None
        raw_ot = kwargs.get('ot_fee')
        self.ot_fee = float(raw_ot) if raw_ot is not None and str(raw_ot).strip() != '' else None
        raw_amb = kwargs.get('ambulance_fee')
        self.ambulance_fee = float(raw_amb) if raw_amb is not None and str(raw_amb).strip() != '' else None
        self.insurance_cashless = kwargs.get('insurance_cashless') or ''
        self.certifications = kwargs.get('certifications') or ''
        
        # Media & Operational Policies
        self.gallery_urls = kwargs.get('gallery_urls') or ''
        self.video_urls = kwargs.get('video_urls') or ''
        self.visiting_hours = kwargs.get('visiting_hours') or ''
        self.patient_support_email = kwargs.get('patient_support_email') or self.email
        self.patient_support_phone = kwargs.get('patient_support_phone') or self.phone
        self.patient_guidelines = kwargs.get('patient_guidelines') or ''
        self.faqs = kwargs.get('faqs') or ''
        self.social_links = kwargs.get('social_links') or {}
        self.departments_custom = kwargs.get('departments_custom') or ''
        
        # Publishing & Verification State (Section 6)
        self.publishing_status = kwargs.get('publishing_status') or ('published' if self.is_verified else 'pending_verification')
        self._slug = kwargs.get('slug')
        self.created_at = kwargs.get('created_at') or utcnow().isoformat()
        self.updated_at = kwargs.get('updated_at') or utcnow().isoformat()

    def get_id(self):
        return f"hospital-{self.id}"

    @property
    def primary_type_obj(self):
        from spherix.hospital_types import get_hospital_types_master_dict, get_default_hospital_type
        types_dict = get_hospital_types_master_dict()
        if self.hospital_type_id in types_dict:
            return types_dict[self.hospital_type_id]
        return get_default_hospital_type(self.name)

    @property
    def type_name(self):
        return getattr(self.primary_type_obj, 'name', self.hospital_type or 'General Hospital')

    @property
    def type_description(self):
        return getattr(self.primary_type_obj, 'description', '')

    @property
    def type_icon(self):
        return getattr(self.primary_type_obj, 'icon', 'fa-solid fa-hospital')

    @property
    def type_color(self):
        return getattr(self.primary_type_obj, 'color', 'emerald')

    @property
    def type_badge_bg(self):
        return getattr(self.primary_type_obj, 'badge_bg', 'bg-emerald-50')

    @property
    def type_badge_text(self):
        return getattr(self.primary_type_obj, 'badge_text', 'text-emerald-700')

    @property
    def type_badge_border(self):
        return getattr(self.primary_type_obj, 'badge_border', 'border-emerald-200')

    def has_facility(self, facility_name: str) -> bool:
        if not self.facilities:
            return False
        fn = facility_name.lower().strip()
        return any(fn in f.lower() for f in self.facilities)

    def has_specialty(self, specialty_name: str) -> bool:
        if not self.specialties:
            return False
        sn = specialty_name.lower().strip()
        return any(sn in s.lower() for s in self.specialties)

    @property
    def country_flag(self):
        return GLOBAL_COUNTRY_FLAGS.get(self.country, '🌍')

    @property
    def formatted_general_bed_fee(self):
        if self.general_bed_fee is None:
            return None
        if self.general_bed_fee == 0:
            return "Free"
        return format_dual_currency(self.general_bed_fee, self.currency)

    @property
    def formatted_icu_bed_fee(self):
        if self.icu_bed_fee is None:
            return None
        if self.icu_bed_fee == 0:
            return "Free"
        return format_dual_currency(self.icu_bed_fee, self.currency)

    @property
    def formatted_private_bed_fee(self):
        if self.private_bed_fee is None:
            return None
        if self.private_bed_fee == 0:
            return "Free"
        return format_dual_currency(self.private_bed_fee, self.currency)

    @property
    def formatted_admission_charge(self):
        if self.admission_charge is None:
            return None
        if self.admission_charge == 0:
            return "Free"
        return format_dual_currency(self.admission_charge, self.currency)

    @property
    def formatted_consultation_fee(self):
        if self.consultation_fee is None:
            return None
        if self.consultation_fee == 0:
            return "Free"
        return format_dual_currency(self.consultation_fee, self.currency)

    @property
    def formatted_follow_up_fee(self):
        if self.follow_up_fee is None:
            return None
        if self.follow_up_fee == 0:
            return "Free"
        return format_dual_currency(self.follow_up_fee, self.currency)

    @property
    def formatted_emergency_bed_fee(self):
        if self.emergency_bed_fee is None:
            return None
        if self.emergency_bed_fee == 0:
            return "Free"
        return format_dual_currency(self.emergency_bed_fee, self.currency)

    @property
    def formatted_ot_fee(self):
        if self.ot_fee is None:
            return None
        if self.ot_fee == 0:
            return "Free"
        return format_dual_currency(self.ot_fee, self.currency)

    @property
    def formatted_ambulance_fee(self):
        if self.ambulance_fee is None:
            return None
        if self.ambulance_fee == 0:
            return "Free"
        return format_dual_currency(self.ambulance_fee, self.currency)

    @property
    def blood_stock_dict(self):
        if isinstance(self.blood_stock, dict):
            return self.blood_stock
        return {}

    @property
    def total_blood_units(self):
        if not isinstance(self.blood_stock, dict):
            return 0
        return sum(int(v or 0) for v in self.blood_stock.values())

    @property
    def doctors(self):
        from spherix.services.database import TEMP_DATA
        return [
            d for d in TEMP_DATA.get('doctors', {}).values()
            if (d.hospital_name == self.name or str(getattr(d, 'hospital_id', '')) == str(self.id))
            and not getattr(d, 'is_hidden', False)
            and not getattr(d, 'is_blocked', False)
            and getattr(d, 'publishing_status', 'published') in ['published', 'approved']
        ]

    @property
    def doctor_count(self):
        return len(self.doctors)

    @property
    def departments_with_doctors(self):
        dept_map = {}
        for d in self.doctors:
            dept = d.department or 'General Medicine'
            if dept not in dept_map:
                dept_map[dept] = []
            dept_map[dept].append(d)
        return dept_map

    @property
    def appointments(self):
        from spherix.services.database import TEMP_DATA
        doctor_ids = {d.id for d in self.doctors}
        return [
            appt for appt in TEMP_DATA.get('appointments', {}).values()
            if appt.doctor_id in doctor_ids or str(getattr(appt, 'hospital_id', '')) == str(self.id)
        ]

    @property
    def staff(self):
        from spherix.services.database import TEMP_DATA
        return [
            s for s in TEMP_DATA.get('staff', {}).values()
            if (s.hospital_name == self.name or str(getattr(s, 'hospital_id', '')) == str(self.id))
            and not getattr(s, 'is_blocked', False)
        ]

    @property
    def medical_staff(self):
        return self.staff

    @property
    def slug(self):
        if getattr(self, '_slug', None):
            return self._slug
        import re
        base = self.name or f"hospital-{self.id}"
        clean = re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')
        return clean or f"hospital-{self.id}"

    @property
    def is_publicly_visible(self):
        return (getattr(self, 'publishing_status', 'published') in ['published', 'approved']) and not self.is_hidden and not self.is_blocked

    @property
    def logo_display_url(self):
        if self.logo_url:
            p = str(self.logo_url).strip()
            if p.startswith('http://') or p.startswith('https://') or p.startswith('/static/'):
                return p
            if p.startswith('hospital_logos/'):
                return f"/static/uploads/{p}"
            return f"/static/uploads/hospital_logos/{p}"
        return "/static/images/spherix_clinic_logo.png"

    @property
    def cover_display_url(self):
        if self.cover_image_url:
            p = str(self.cover_image_url).strip()
            if p.startswith('http://') or p.startswith('https://') or p.startswith('/static/'):
                return p
            if p.startswith('hospital_covers/'):
                return f"/static/uploads/{p}"
            return f"/static/uploads/hospital_covers/{p}"
        return "/static/images/half_earth_background.jpg"

    @property
    def departments_list(self):
        doc_depts = list(self.departments_with_doctors.keys())
        custom = []
        if self.departments_custom:
            custom = [d.strip() for d in self.departments_custom.replace(';', ',').split(',') if d.strip()]
        combined = []
        for d in doc_depts + custom:
            if d and d not in combined:
                combined.append(d)
        return combined

    @property
    def facilities_list(self):
        if self.facilities:
            if isinstance(self.facilities, list):
                return self.facilities
            try:
                import json
                return json.loads(self.facilities)
            except Exception:
                return [f.strip() for f in str(self.facilities).split(',') if f.strip()]
        return []

    @property
    def infrastructure_list(self):
        if self.infrastructure:
            return [i.strip() for i in self.infrastructure.replace(';', ',').split(',') if i.strip()]
        return []

    @property
    def equipment_list(self):
        if self.medical_equipment:
            return [e.strip() for e in self.medical_equipment.replace(';', ',').split(',') if e.strip()]
        return []

    @property
    def diagnostic_list(self):
        if self.diagnostic_services:
            return [d.strip() for d in self.diagnostic_services.replace(';', ',').split(',') if d.strip()]
        return []

    @property
    def lab_list(self):
        if self.laboratory_facilities:
            return [l.strip() for l in self.laboratory_facilities.replace(';', ',').split(',') if l.strip()]
        return []

    @property
    def insurance_list(self):
        if self.insurance_cashless:
            return [ins.strip() for ins in self.insurance_cashless.replace(';', ',').split(',') if ins.strip()]
        return []

    @property
    def certifications_list(self):
        if self.certifications:
            return [c.strip() for c in self.certifications.replace(';', ',').split(',') if c.strip()]
        return []

    @property
    def gallery_list(self):
        if self.gallery_urls:
            items = [g.strip() for g in self.gallery_urls.replace(';', ',').split(',') if g.strip()]
            if items:
                return items
        return []

    @property
    def video_list(self):
        if self.video_urls:
            return [v.strip() for v in self.video_urls.replace(';', ',').split(',') if v.strip()]
        return []

    @property
    def faqs_list(self):
        if self.faqs:
            try:
                import json
                parsed = json.loads(self.faqs)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        items = []
        if getattr(self, 'patient_guidelines', None):
            items.append({
                "q": "What identification and medical documents are needed for patient admission?",
                "a": self.patient_guidelines
            })
        if getattr(self, 'visiting_hours', None):
            items.append({
                "q": "What are the visiting hours for general wards and intensive care units?",
                "a": f"Inpatient visiting hours are {self.visiting_hours}."
            })
        if getattr(self, 'emergency_services', False):
            items.append({
                "q": "Are emergency admissions and ambulance services available?",
                "a": f"Emergency care is operational 24/7. Emergency contact: {self.emergency_phone or self.phone or 'Contact reception desk'}."
            })
        return items

    @property
    def social_links_dict(self):
        if isinstance(self.social_links, dict):
            return self.social_links
        try:
            import json
            return json.loads(self.social_links)
        except Exception:
            return {}

    @property
    def reviews(self):
        from spherix.services.database import TEMP_DATA
        return [r for r in TEMP_DATA.get('reviews', {}).values() if str(getattr(r, 'hospital_id', '')) == str(self.id)]

    @property
    def average_rating(self):
        revs = self.reviews
        if not revs:
            return None
        return round(sum(r.rating for r in revs) / len(revs), 1)

    @property
    def reviews_count(self):
        return len(self.reviews)


class BloodDonor(UserMixin):
    def __init__(self, id, name, email, phone, blood_group, age, city, password=None, last_donation=None, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.blood_group = blood_group
        self.age = age
        self.city = city
        self.password = password
        self.last_donation = ensure_safe_date(last_donation)
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.profile_picture_data = kwargs.get('profile_picture_data')
        self.profile_picture_content_type = kwargs.get('profile_picture_content_type')
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or kwargs.get('donor_card_id') or generate_user_license_id('blood_donor')
        self.license_no = self.license_number
        self.donor_card_id = self.license_number
        self.status = kwargs.get('status', 'pending')
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.hospital_id = kwargs.get('hospital_id')
        self.hospital_name = kwargs.get('hospital_name')
        self.assigned_staff_name = kwargs.get('assigned_staff_name')
        self.superintendent_name = kwargs.get('superintendent_name')
        self.president_ceo = kwargs.get('president_ceo')
        self.is_blood_donor = True
        self.is_doctor = False
        self.is_hospital = False
        self.is_patient = False
        self.is_organ_donor = False
        self.is_staff = False
        self.role = 'Blood Donor'
        
    def get_id(self):
        return f"blood_donor-{self.id}"

    @property
    def appointments(self):
        return []


class OrganDonor(UserMixin):
    def __init__(self, id, name, email, phone, organs, blood_group, age, city, password=None, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.organs = organs if isinstance(organs, list) else []
        self.blood_group = blood_group
        self.age = age
        self.city = city
        self.password = password
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.profile_picture_data = kwargs.get('profile_picture_data')
        self.profile_picture_content_type = kwargs.get('profile_picture_content_type')
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or kwargs.get('pledge_id') or generate_user_license_id('organ_donor')
        self.license_no = self.license_number
        self.pledge_id = self.license_number
        self.status = kwargs.get('status', 'pending')
        self.is_blocked = kwargs.get('is_blocked', False)
        self.is_hidden = kwargs.get('is_hidden', False)
        self.hospital_id = kwargs.get('hospital_id')
        self.hospital_name = kwargs.get('hospital_name')
        self.assigned_staff_name = kwargs.get('assigned_staff_name')
        self.superintendent_name = kwargs.get('superintendent_name')
        self.president_ceo = kwargs.get('president_ceo')
        self.is_organ_donor = True
        self.is_blood_donor = False
        self.is_doctor = False
        self.is_hospital = False
        self.is_patient = False
        self.is_staff = False
        self.role = 'Organ Donor'

    def get_id(self):
        return f"organ_donor-{self.id}"

    @property
    def appointments(self):
        return []



