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
        self.address = kwargs.get('address')
        self.profile_picture_url = kwargs.get('profile_picture_url')
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
        self.consultation_fee = kwargs.get('consultation_fee', '500')
        self.working_hours = kwargs.get('working_hours', '09:00 AM - 05:00 PM')
        self.social_links = kwargs.get('social_links', {})
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
        return format_dual_currency(self.consultation_fee, self.currency)

    @property
    def reviews(self):
        from spherix.services.database import TEMP_DATA
        return sorted([review for review in TEMP_DATA.get('reviews', {}).values() if review.doctor_id == self.id], key=lambda r: r.created_at, reverse=True)

    @property
    def average_rating(self):
        reviews = self.reviews
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def appointments(self):
        from spherix.services.database import TEMP_DATA
        return [appt for appt in TEMP_DATA.get('appointments', {}).values() if appt.doctor_id == self.id]

    @property
    def messages(self):
        from spherix.services.database import TEMP_DATA
        return [msg for msg in TEMP_DATA.get('messages', {}).values() if msg.doctor_id == self.id]


class Patient(UserMixin):
    def __init__(self, id, name, email, password, **kwargs):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.age = kwargs.get('age')
        self.gender = kwargs.get('gender')
        self.profile_picture_url = kwargs.get('profile_picture_url')
        self.phone = kwargs.get('phone')
        self.address = kwargs.get('address')
        self.country = kwargs.get('country', 'India')
        self.preferred_currency = kwargs.get('preferred_currency', 'INR')
        self.license_number = kwargs.get('license_number') or kwargs.get('license_no') or kwargs.get('health_id') or generate_user_license_id('patient')
        self.license_no = self.license_number
        self.health_id = self.license_number
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
        self.is_organ_donor = False
        self.profile_picture_url = kwargs.get('profile_picture_url')
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
        self.president_ceo = kwargs.get('president_ceo', kwargs.get('director_name', kwargs.get('md_name', f"Dr. {self.name.split()[0]} MD, Chief Executive")))
        self.director_name = self.president_ceo
        self.superintendent_name = kwargs.get('superintendent_name', kwargs.get('doctor_name', kwargs.get('blood_bank_staff', f"Dr. {self.name.split()[0]} Superintendent")))
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
        self.general_bed_fee = float(kwargs.get('general_bed_fee') or 1000.0)
        self.icu_bed_fee = float(kwargs.get('icu_bed_fee') or 2500.0)
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
        self.accreditation = kwargs.get('accreditation', 'JCI Gold Accredited' if self.is_international else 'NABH / ISO 9001 Certified')
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
            default_spec = get_hospital_types_master_dict().get(self.hospital_type_id)
            self.specialties = list(default_spec.common_specialties) if default_spec else ["General Medicine", "Emergency Care"]

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
            default_spec = get_hospital_types_master_dict().get(self.hospital_type_id)
            self.facilities = list(default_spec.default_facilities) if default_spec else ["24x7 Emergency", "ICU", "Blood Bank", "Pathology Lab", "Pharmacy", "Ambulance"]

        self.emergency_services = bool(kwargs.get('emergency_services', True))
        self.about = kwargs.get('about') or kwargs.get('bio') or f"{self.name} is a premier healthcare institution providing comprehensive clinical care, 24x7 emergency response, modern inpatient suites, and advanced diagnostics."
        
        # Geolocation Coordinates
        try:
            self.latitude = float(kwargs.get('latitude')) if kwargs.get('latitude') is not None else None
            self.longitude = float(kwargs.get('longitude')) if kwargs.get('longitude') is not None else None
        except (ValueError, TypeError):
            self.latitude = None
            self.longitude = None

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
        return format_dual_currency(self.general_bed_fee, self.currency)

    @property
    def formatted_icu_bed_fee(self):
        return format_dual_currency(self.icu_bed_fee, self.currency)

    @property
    def doctors(self):
        from spherix.services.database import TEMP_DATA
        return [
            d for d in TEMP_DATA.get('doctors', {}).values()
            if (d.hospital_name == self.name or str(getattr(d, 'hospital_id', '')) == str(self.id))
            and not getattr(d, 'is_hidden', False)
            and not getattr(d, 'is_blocked', False)
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



