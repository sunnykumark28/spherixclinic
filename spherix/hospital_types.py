"""
spherix/hospital_types.py — Hospital Types Master Catalog & Classification System
Defines the centralized 18 hospital categories + 'Other', seed data, and data access utilities.
"""

from typing import List, Dict, Any, Optional

# Standard 18 Hospital Categories + Other Category as per Spherix Clinic specification
HOSPITAL_TYPE_MASTER_DATA = [
    {
        "id": 1,
        "name": "General Hospital",
        "slug": "general-hospital",
        "description": "Provides treatment for common medical conditions",
        "icon": "fa-solid fa-hospital",
        "color": "emerald",
        "badge_bg": "bg-emerald-50",
        "badge_text": "text-emerald-700",
        "badge_border": "border-emerald-200",
        "is_active": 1,
        "common_specialties": ["General Medicine", "General Surgery", "Family Medicine", "Preventive Healthcare", "Outpatient Care"],
        "default_facilities": ["24x7 Emergency", "Pharmacy", "In-House Pathology", "General Wards", "Ambulance"]
    },
    {
        "id": 2,
        "name": "Multispecialty Hospital",
        "slug": "multispecialty-hospital",
        "description": "Offers multiple medical departments",
        "icon": "fa-solid fa-square-h",
        "color": "teal",
        "badge_bg": "bg-teal-50",
        "badge_text": "text-teal-700",
        "badge_border": "border-teal-200",
        "is_active": 1,
        "common_specialties": ["Internal Medicine", "Cardiology", "Neurology", "Orthopedics", "Gastroenterology", "Pulmonology"],
        "default_facilities": ["24x7 Emergency", "ICU / CCU", "Blood Bank", "Diagnostic Imaging", "Pharmacy", "Ambulance", "Operation Theatres"]
    },
    {
        "id": 3,
        "name": "Super Specialty Hospital",
        "slug": "super-specialty-hospital",
        "description": "Focuses on advanced specialized treatments",
        "icon": "fa-solid fa-star-of-life",
        "color": "blue",
        "badge_bg": "bg-blue-50",
        "badge_text": "text-blue-700",
        "badge_border": "border-blue-200",
        "is_active": 1,
        "common_specialties": ["Cardiothoracic Surgery", "Neurosurgery", "Organ Transplantation", "Surgical Oncology", "Interventional Radiology"],
        "default_facilities": ["24x7 Emergency", "Level-1 Trauma", "Advanced ICU", "Blood Bank", "Organ Transplant Suite", "MRI & CT Suite", "Telemedicine Desk"]
    },
    {
        "id": 4,
        "name": "Cardiology Hospital",
        "slug": "cardiology-hospital",
        "description": "Heart and cardiovascular treatment",
        "icon": "fa-solid fa-heart-pulse",
        "color": "rose",
        "badge_bg": "bg-rose-50",
        "badge_text": "text-rose-700",
        "badge_border": "border-rose-200",
        "is_active": 1,
        "common_specialties": ["Interventional Cardiology", "Cardiothoracic Surgery", "Electrophysiology", "Pediatric Cardiology", "Heart Failure Clinic"],
        "default_facilities": ["24x7 Cardiac Emergency", "Cath Lab", "Coronary Care Unit (CCU)", "Cardiac Ambulances", "Echo & TMT Suite"]
    },
    {
        "id": 5,
        "name": "Oncology Hospital",
        "slug": "oncology-hospital",
        "description": "Cancer diagnosis and treatment",
        "icon": "fa-solid fa-ribbon",
        "color": "purple",
        "badge_bg": "bg-purple-50",
        "badge_text": "text-purple-700",
        "badge_border": "border-purple-200",
        "is_active": 1,
        "common_specialties": ["Medical Oncology", "Surgical Oncology", "Radiation Oncology", "Hematology Oncology", "Palliative Care"],
        "default_facilities": ["Chemotherapy Daycare", "Linear Accelerator (LINAC)", "PET-CT Imaging", "Bone Marrow Transplant Unit", "In-House Pathology"]
    },
    {
        "id": 6,
        "name": "Neurology Hospital",
        "slug": "neurology-hospital",
        "description": "Brain and nervous system treatment",
        "icon": "fa-solid fa-brain",
        "color": "indigo",
        "badge_bg": "bg-indigo-50",
        "badge_text": "text-indigo-700",
        "badge_border": "border-indigo-200",
        "is_active": 1,
        "common_specialties": ["Neurology", "Neurosurgery", "Stroke Care", "Spine Surgery", "Epilepsy Clinic", "Neuro-Rehabilitation"],
        "default_facilities": ["24x7 Comprehensive Stroke Unit", "Neuro-ICU", "3T MRI & High-Speed CT", "EEG & EMG Lab", "Neuro-Navigation Theatres"]
    },
    {
        "id": 7,
        "name": "Orthopedic Hospital",
        "slug": "orthopedic-hospital",
        "description": "Bone, joint, and spine treatment",
        "icon": "fa-solid fa-bone",
        "color": "amber",
        "badge_bg": "bg-amber-50",
        "badge_text": "text-amber-800",
        "badge_border": "border-amber-200",
        "is_active": 1,
        "common_specialties": ["Joint Replacement", "Spine Surgery", "Sports Medicine", "Arthroscopy", "Pediatric Orthopedics", "Trauma Reconstruction"],
        "default_facilities": ["Robotic Joint Surgery Suite", "Physiotherapy & Rehabilitation", "Digital X-Ray & Dexa Scan", "Laminar Flow OTs"]
    },
    {
        "id": 8,
        "name": "Maternity Hospital",
        "slug": "maternity-hospital",
        "description": "Pregnancy, childbirth, and women's care",
        "icon": "fa-solid fa-person-pregnant",
        "color": "pink",
        "badge_bg": "bg-pink-50",
        "badge_text": "text-pink-700",
        "badge_border": "border-pink-200",
        "is_active": 1,
        "common_specialties": ["Obstetrics", "Gynecology", "Fetal Medicine", "Reproductive Endocrinology / IVF", "High-Risk Pregnancy Care"],
        "default_facilities": ["24x7 Obstetric Emergency", "Labor Delivery Recovery (LDR) Rooms", "Neonatal ICU (NICU Level-3)", "4D Ultrasound Suite"]
    },
    {
        "id": 9,
        "name": "Pediatric Hospital",
        "slug": "pediatric-hospital",
        "description": "Medical care for infants and children",
        "icon": "fa-solid fa-baby",
        "color": "cyan",
        "badge_bg": "bg-cyan-50",
        "badge_text": "text-cyan-800",
        "badge_border": "border-cyan-200",
        "is_active": 1,
        "common_specialties": ["General Pediatrics", "Pediatric Surgery", "Neonatology", "Pediatric Cardiology", "Child Psychology"],
        "default_facilities": ["Pediatric ICU (PICU)", "Neonatal ICU (NICU)", "Pediatric Emergency", "Child-Friendly Play Zones", "Immunization Clinic"]
    },
    {
        "id": 10,
        "name": "Psychiatric Hospital",
        "slug": "psychiatric-hospital",
        "description": "Mental health treatment",
        "icon": "fa-solid fa-head-side-virus",
        "color": "violet",
        "badge_bg": "bg-violet-50",
        "badge_text": "text-violet-700",
        "badge_border": "border-violet-200",
        "is_active": 1,
        "common_specialties": ["Clinical Psychiatry", "Clinical Psychology", "Addiction Medicine", "Cognitive Behavioral Therapy", "Adolescent Mental Health"],
        "default_facilities": ["24x7 Crisis Intervention", "Inpatient Psychiatric Ward", "De-Addiction & Rehab Center", "Counseling Suites"]
    },
    {
        "id": 11,
        "name": "Eye Hospital",
        "slug": "eye-hospital",
        "description": "Ophthalmology and vision care",
        "icon": "fa-solid fa-eye",
        "color": "sky",
        "badge_bg": "bg-sky-50",
        "badge_text": "text-sky-700",
        "badge_border": "border-sky-200",
        "is_active": 1,
        "common_specialties": ["Cataract & Refractive Surgery", "Retina & Vitreous", "Glaucoma", "Cornea & Eye Banking", "Pediatric Ophthalmology"],
        "default_facilities": ["LASIK & SMILE Suite", "Eye Bank Facility", "Micro-Surgical Theatres", "Optical & Vision Diagnostic Lab"]
    },
    {
        "id": 12,
        "name": "Dental Hospital",
        "slug": "dental-hospital",
        "description": "Oral and dental treatment",
        "icon": "fa-solid fa-tooth",
        "color": "emerald",
        "badge_bg": "bg-emerald-50",
        "badge_text": "text-emerald-700",
        "badge_border": "border-emerald-200",
        "is_active": 1,
        "common_specialties": ["Orthodontics", "Maxillofacial Surgery", "Endodontics", "Periodontics", "Implantology", "Prosthodontics"],
        "default_facilities": ["Digital Smile Design & OPG", "Dental Implantology Lab", "Sedation Dentistry Suites", "Sterilization Hub"]
    },
    {
        "id": 13,
        "name": "ENT Hospital",
        "slug": "ent-hospital",
        "description": "Ear, nose, and throat treatment",
        "icon": "fa-solid fa-ear-listen",
        "color": "teal",
        "badge_bg": "bg-teal-50",
        "badge_text": "text-teal-700",
        "badge_border": "border-teal-200",
        "is_active": 1,
        "common_specialties": ["Otology & Cochlear Implants", "Rhinology & Sinus Surgery", "Laryngology & Voice Disorders", "Head and Neck Surgery"],
        "default_facilities": ["Audiology & Speech Therapy Lab", "Endoscopic ENT Surgery Suite", "Cochlear Implant Center", "Sleep Apnea Lab"]
    },
    {
        "id": 14,
        "name": "Nephrology Hospital",
        "slug": "nephrology-hospital",
        "description": "Kidney-related treatment",
        "icon": "fa-solid fa-shield-virus",
        "color": "orange",
        "badge_bg": "bg-orange-50",
        "badge_text": "text-orange-800",
        "badge_border": "border-orange-200",
        "is_active": 1,
        "common_specialties": ["Clinical Nephrology", "Renal Transplantation", "Hemodialysis", "Peritoneal Dialysis", "Pediatric Nephrology"],
        "default_facilities": ["24x7 Hemodialysis Unit", "Kidney Transplant ICU", "Water Treatment (RO) Plant", "Renal Biopsy Suite"]
    },
    {
        "id": 15,
        "name": "Rehabilitation Hospital",
        "slug": "rehabilitation-hospital",
        "description": "Physical recovery and rehabilitation",
        "icon": "fa-solid fa-wheelchair",
        "color": "green",
        "badge_bg": "bg-green-50",
        "badge_text": "text-green-800",
        "badge_border": "border-green-200",
        "is_active": 1,
        "common_specialties": ["Physiotherapy", "Occupational Therapy", "Speech & Swallow Rehabilitation", "Spinal Cord Injury Rehab", "Cardiac Rehabilitation"],
        "default_facilities": ["Robotic Gait Training Gym", "Hydrotherapy Pool", "Prosthetics & Orthotics Center", "ADL Simulation Suite"]
    },
    {
        "id": 16,
        "name": "Infectious Disease Hospital",
        "slug": "infectious-disease-hospital",
        "description": "Treatment of infectious diseases",
        "icon": "fa-solid fa-virus-covid",
        "color": "red",
        "badge_bg": "bg-red-50",
        "badge_text": "text-red-700",
        "badge_border": "border-red-200",
        "is_active": 1,
        "common_specialties": ["Infectious Disease Medicine", "Tropical Diseases", "Travel Medicine", "Epidemiology & Outbreak Management", "HIV/Immunology"],
        "default_facilities": ["Negative Pressure Isolation Wards", "BSL-3 Molecular Diagnostics", "Quarantine Suites", "Infection Control Unit"]
    },
    {
        "id": 17,
        "name": "Burns and Plastic Surgery Hospital",
        "slug": "burns-plastic-surgery-hospital",
        "description": "Burn care and reconstructive surgery",
        "icon": "fa-solid fa-fire-flame-curved",
        "color": "amber",
        "badge_bg": "bg-amber-50",
        "badge_text": "text-amber-800",
        "badge_border": "border-amber-200",
        "is_active": 1,
        "common_specialties": ["Acute Burn Management", "Reconstructive Microsurgery", "Craniofacial Surgery", "Cosmetic & Plastic Surgery", "Wound Care"],
        "default_facilities": ["Sterile Burn ICU", "Skin Bank", "Hydrotherapy & Debridement Units", "Hyperbaric Oxygen Therapy (HBOT)"]
    },
    {
        "id": 18,
        "name": "Emergency and Trauma Hospital",
        "slug": "emergency-trauma-hospital",
        "description": "Emergency injuries and critical care",
        "icon": "fa-solid fa-truck-medical",
        "color": "red",
        "badge_bg": "bg-red-50",
        "badge_text": "text-red-700",
        "badge_border": "border-red-200",
        "is_active": 1,
        "common_specialties": ["Emergency Medicine", "Trauma Surgery", "Critical Care Medicine", "Resuscitation & Toxicology", "Vascular Emergency"],
        "default_facilities": ["Level-1 Trauma Resuscitation Bays", "Helipad & Rapid Ambulance Dispatch", "24x7 Emergency Theatres", "Trauma ICU"]
    },
    {
        "id": 19,
        "name": "Other",
        "slug": "other",
        "description": "Specialized or custom medical facility",
        "icon": "fa-solid fa-clinic-medical",
        "color": "slate",
        "badge_bg": "bg-slate-100",
        "badge_text": "text-slate-700",
        "badge_border": "border-slate-300",
        "is_active": 1,
        "common_specialties": ["Ayurveda", "Homeopathy", "Integrative Medicine", "Alternative Therapies", "Geriatric Care"],
        "default_facilities": ["Outpatient Consultation", "Daycare Facility", "Diagnostic Support", "Wellness Center"]
    }
]

# Standard Available Facilities Master List
MASTER_FACILITIES_LIST = [
    {"id": "24x7_emergency", "name": "24x7 Emergency", "icon": "fa-solid fa-truck-medical", "category": "Emergency"},
    {"id": "icu", "name": "Intensive Care Unit (ICU)", "icon": "fa-solid fa-heart-pulse", "category": "Critical Care"},
    {"id": "blood_bank", "name": "Blood Bank", "icon": "fa-solid fa-tint", "category": "Support Services"},
    {"id": "pathology_lab", "name": "Pathology & Diagnostics Lab", "icon": "fa-solid fa-microscope", "category": "Diagnostics"},
    {"id": "pharmacy_247", "name": "24x7 Pharmacy", "icon": "fa-solid fa-pills", "category": "Pharmacy"},
    {"id": "ambulance", "name": "Advanced Life Support Ambulance", "icon": "fa-solid fa-van-shuttle", "category": "Emergency"},
    {"id": "telemedicine", "name": "Cross-Border Telemedicine", "icon": "fa-solid fa-video", "category": "Digital Health"},
    {"id": "organ_transplant", "name": "Organ Transplant Unit", "icon": "fa-solid fa-hand-holding-medical", "category": "Advanced Care"},
    {"id": "dialysis", "name": "Hemodialysis Center", "icon": "fa-solid fa-shield-virus", "category": "Specialized Units"},
    {"id": "radiology", "name": "Radiology (MRI / CT / X-Ray)", "icon": "fa-solid fa-x-ray", "category": "Diagnostics"},
    {"id": "cafeteria", "name": "In-House Nutrition & Cafeteria", "icon": "fa-solid fa-utensils", "category": "Amenities"},
    {"id": "parking_wifi", "name": "Valet Parking & High-Speed WiFi", "icon": "fa-solid fa-square-parking", "category": "Amenities"}
]

class HospitalType:
    """Represents a master hospital type classification in Spherix Clinic."""
    def __init__(self, id: int, name: str, description: str = "", slug: str = "", 
                 icon: str = "fa-solid fa-hospital", color: str = "emerald", 
                 is_active: int = 1, badge_bg: str = "bg-emerald-50", 
                 badge_text: str = "text-emerald-700", badge_border: str = "border-emerald-200", 
                 **kwargs):
        self.id = int(id)
        self.name = str(name).strip()
        self.slug = slug or self.name.lower().replace(" ", "-").replace("&", "and")
        self.description = description or ""
        self.icon = icon or "fa-solid fa-hospital"
        self.color = color or "emerald"
        self.badge_bg = badge_bg or "bg-emerald-50"
        self.badge_text = badge_text or "text-emerald-700"
        self.badge_border = badge_border or "border-emerald-200"
        self.is_active = bool(int(is_active)) if is_active is not None else True
        self.common_specialties = kwargs.get('common_specialties', [])
        self.default_facilities = kwargs.get('default_facilities', [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "badge_bg": self.badge_bg,
            "badge_text": self.badge_text,
            "badge_border": self.badge_border,
            "is_active": 1 if self.is_active else 0,
            "common_specialties": self.common_specialties,
            "default_facilities": self.default_facilities
        }


def get_hospital_types_master_dict() -> Dict[int, HospitalType]:
    """Returns a dictionary of all 18 + Other hospital types indexed by ID."""
    return {item['id']: HospitalType(**item) for item in HOSPITAL_TYPE_MASTER_DATA}


def get_default_hospital_type(hospital_name: str = "") -> HospitalType:
    """Intelligently detects or defaults a hospital type based on its name."""
    name_lower = hospital_name.lower()
    types_dict = get_hospital_types_master_dict()
    
    if any(k in name_lower for k in ["cardio", "heart", "cardiac"]):
        return types_dict[4] # Cardiology
    elif any(k in name_lower for k in ["cancer", "onco", "tumor"]):
        return types_dict[5] # Oncology
    elif any(k in name_lower for k in ["neuro", "brain", "spine"]):
        return types_dict[6] # Neurology
    elif any(k in name_lower for k in ["ortho", "bone", "joint"]):
        return types_dict[7] # Orthopedic
    elif any(k in name_lower for k in ["maternity", "women", "mother"]):
        return types_dict[8] # Maternity
    elif any(k in name_lower for k in ["child", "pediatric", "kids"]):
        return types_dict[9] # Pediatric
    elif any(k in name_lower for k in ["eye", "vision", "ophthalm"]):
        return types_dict[10] # Eye
    elif any(k in name_lower for k in ["dental", "tooth", "oral"]):
        return types_dict[12] # Dental
    elif any(k in name_lower for k in ["ent", "ear", "throat"]):
        return types_dict[13] # ENT
    elif any(k in name_lower for k in ["kidney", "renal", "nephro"]):
        return types_dict[14] # Nephrology
    elif any(k in name_lower for k in ["rehab", "recovery", "therapy"]):
        return types_dict[15] # Rehabilitation
    elif any(k in name_lower for k in ["trauma", "emergency", "urgent"]):
        return types_dict[18] # Emergency and Trauma
    elif any(k in name_lower for k in ["super specialty", "super-specialty", "multispeciality", "multispecialty", "memorial", "apollo", "fortis", "max", "aiims", "medanta"]):
        return types_dict[2] # Multispecialty Hospital
    else:
        return types_dict[1] # General Hospital


def get_all_hospital_types(active_only: bool = False) -> List[HospitalType]:
    """Returns a list of all master hospital types."""
    types = [HospitalType(**item) for item in HOSPITAL_TYPE_MASTER_DATA]
    if active_only:
        types = [t for t in types if t.is_active]
    return types


def get_hospital_type_by_id(type_id: int) -> Optional[HospitalType]:
    """Retrieves a hospital type by ID."""
    types_dict = get_hospital_types_master_dict()
    try:
        return types_dict.get(int(type_id))
    except (ValueError, TypeError):
        return None


def get_hospital_type_by_slug(slug: str) -> Optional[HospitalType]:
    """Retrieves a hospital type by slug."""
    clean_slug = (slug or '').lower().strip()
    for t in get_all_hospital_types():
        if t.slug == clean_slug or t.name.lower() == clean_slug:
            return t
    return None

