import os
import json
from flask import current_app

DEFAULT_GALLERY_METADATA = {
    'images/hospital.png': {
        'title': 'Advanced Clinical Trauma & Inpatient Center',
        'category': 'clinical',
        'author': 'Spherix Facilities',
        'description': 'Modern multidisciplinary tertiary healthcare center equipped with 24x7 emergency and trauma wings.'
    },
    'images/cancerp.png': {
        'title': 'Oncology Diagnostic & Proton Therapy Facility',
        'category': 'clinical',
        'author': 'Oncology Department',
        'description': 'Specialized cancer diagnostic wing featuring precision radiation therapy and robotic surgery suites.'
    },
    'images/doctor_specialist_art.jpg': {
        'title': 'Clinical Specialist Consultation Portal',
        'category': 'clinical',
        'author': 'Dr. Sarah Jenkins',
        'description': 'Physician consultation and remote clinical telemetry system overview for specialized diagnostics.'
    },
    'images/hospital_staff_art.jpg': {
        'title': 'Emergency Triage & Critical Care Operations',
        'category': 'clinical',
        'author': 'Clinical Operations',
        'description': 'Multidisciplinary nursing and healthcare staff operations in active hospital ward management.'
    },
    'images/patient_art.jpg': {
        'title': 'Digital Patient Care & Remote Health Monitoring',
        'category': 'clinical',
        'author': 'Outpatient Services',
        'description': 'Patient-centered healthcare interface and personalized symptom tracking telemetry.'
    }
}

def load_gallery_metadata():
    metadata_path = os.path.join(current_app.root_path, 'static', 'uploads', 'gallery_metadata.json')
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading gallery metadata: {e}")
    return {}

def save_gallery_metadata(metadata):
    metadata_path = os.path.join(current_app.root_path, 'static', 'uploads', 'gallery_metadata.json')
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)
    except Exception as e:
        print(f"Error saving gallery metadata: {e}")

