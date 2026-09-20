from datetime import datetime
from spherix.config import utcnow

class Appointment:
    def __init__(self, id, patient_name, doctor_id, appointment_date, appointment_time, **kwargs):
        self.id = id
        self.patient_name = patient_name
        self.doctor_id = doctor_id
        self.appointment_date = appointment_date
        self.appointment_time = appointment_time
        self.patient_age = kwargs.get('patient_age')
        self.patient_id_number = kwargs.get('patient_id_number')
        self.patient_phone = kwargs.get('patient_phone')
        self.patient_id = kwargs.get('patient_id')
        self.reason = kwargs.get('reason')
        self.status = kwargs.get('status', 'confirmed')
        self.created_at = kwargs.get('created_at', utcnow())
        self.original_appointment_date = kwargs.get('original_appointment_date')
        self.original_appointment_time = kwargs.get('original_appointment_time')
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
        if isinstance(dt, str):
            try:
                self.recorded_at = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except ValueError:
                self.recorded_at = utcnow()
        else:
            self.recorded_at = dt

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
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val


class LabRequest:
    def __init__(self, id, doctor_id, patient_id, patient_name, test_name, status='pending', notes='', **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.test_name = test_name
        self.status = status
        self.notes = notes
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val


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
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val

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

