from spherix.routes.main import main_bp
from spherix.routes.auth import auth_bp
from spherix.routes.patient import patient_bp
from spherix.routes.doctor import doctor_bp
from spherix.routes.hospital import hospital_bp
from spherix.routes.staff import staff_bp
from spherix.routes.pharmacy import pharmacy_bp
from spherix.routes.blood_organ import blood_organ_bp
from spherix.routes.clinical_ai import clinical_ai_bp
from spherix.routes.admin import admin_bp
from spherix.routes.pathology import pathology_bp

ALL_BLUEPRINTS = [
    main_bp,
    auth_bp,
    patient_bp,
    doctor_bp,
    hospital_bp,
    staff_bp,
    pharmacy_bp,
    blood_organ_bp,
    clinical_ai_bp,
    admin_bp,
    pathology_bp
]

__all__ = [
    'main_bp',
    'auth_bp',
    'patient_bp',
    'doctor_bp',
    'hospital_bp',
    'staff_bp',
    'pharmacy_bp',
    'blood_organ_bp',
    'clinical_ai_bp',
    'admin_bp',
    'pathology_bp',
    'ALL_BLUEPRINTS'
]
