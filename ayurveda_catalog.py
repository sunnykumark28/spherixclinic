"""
ayurveda_catalog.py
High-performance parser and search engine for AyurGenixAI_Dataset.csv (367+ Ayurvedic Disease Profiles & Vedic Formulations).
Provides fast in-memory indexing, multi-language searching (English, Hindi, Marathi), Dosha categorization, and clinical monographs.
"""

import os
import csv
import re

CSV_PATH = os.path.join(os.path.dirname(__file__), 'AyurGenixAI_Dataset.csv')

ALL_AYUR_DISEASES = []
AYUR_DISEASES_BY_ID = {}
AYUR_DISEASES_BY_DOSHA = {}
TOP_FEATURED_AYUR_CONDITIONS = []

def _clean(val):
    if not val:
        return ""
    return str(val).strip()

def _categorize_ayurveda_disease(dis_name, symptoms, herbs):
    text = f"{dis_name} {symptoms} {herbs}".lower()
    if re.search(r'cough|cold|asthma|bronchitis|respiratory|sinus|rhinitis|tonsil|sore throat|breath', text):
        return 'Respiratory & Immunity'
    elif re.search(r'acidity|indigestion|gerd|gas|bloat|constipation|ulcer|diarrhea|liver|jaundice|hepatitis|gut|stomach|piles|fistula', text):
        return 'Digestive & Metabolism'
    elif re.search(r'arthritis|joint|knee|back pain|sciatica|gout|osteoporosis|cervical|spondylitis|muscle|paralysis', text):
        return 'Joints & Musculoskeletal'
    elif re.search(r'anxiety|stress|depression|insomnia|sleep|migraine|headache|memory|mental|alzheimer|adhd', text):
        return 'Mental Health & Neurology'
    elif re.search(r'diabetes|sugar|thyroid|obesity|weight|metabolic|pcos|pcod|hormone', text):
        return 'Endocrine & Metabolic'
    elif re.search(r'skin|acne|eczema|psoriasis|dermatitis|hair|alopecia|dandruff|vitiligo|rash', text):
        return 'Skin & Hair Health'
    elif re.search(r'heart|hypertension|blood pressure|cardiac|cholesterol|angina|artery', text):
        return 'Cardiovascular Health'
    elif re.search(r'kidney|renal|uti|urine|stone|calculi|prostate', text):
        return 'Renal & Urinary'
    elif re.search(r'fever|infection|dengue|typhoid|malaria|viral', text):
        return 'Fevers & Viral Care'
    elif re.search(r'menstrual|period|uterine|pregnancy|lactation|female|menopause', text):
        return "Women's Health"
    return 'General Clinical Ayurveda'

def load_ayurveda_catalog():
    global ALL_AYUR_DISEASES, AYUR_DISEASES_BY_ID, AYUR_DISEASES_BY_DOSHA, TOP_FEATURED_AYUR_CONDITIONS
    
    ALL_AYUR_DISEASES = []
    AYUR_DISEASES_BY_ID = {}
    AYUR_DISEASES_BY_DOSHA = {}
    
    if not os.path.exists(CSV_PATH):
        print(f"⚠️ Warning: AyurGenixAI_Dataset.csv not found at {CSV_PATH}")
        return

    try:
        with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            idx = 1
            for row in reader:
                dis_name = _clean(row.get('\ufeffDisease') or row.get('Disease'))
                if not dis_name:
                    continue

                hindi_name = _clean(row.get('Hindi Name'))
                marathi_name = _clean(row.get('Marathi Name'))
                symptoms = _clean(row.get('Symptoms'))
                diagnosis = _clean(row.get('Diagnosis & Tests'))
                severity = _clean(row.get('Symptom Severity'))
                duration = _clean(row.get('Duration of Treatment'))
                med_history = _clean(row.get('Medical History'))
                curr_meds = _clean(row.get('Current Medications'))
                risk_factors = _clean(row.get('Risk Factors'))
                env_factors = _clean(row.get('Environmental Factors'))
                sleep = _clean(row.get('Sleep Patterns'))
                stress = _clean(row.get('Stress Levels'))
                activity = _clean(row.get('Physical Activity Levels'))
                family_hist = _clean(row.get('Family History'))
                diet = _clean(row.get('Dietary Habits'))
                allergies = _clean(row.get('Allergies (Food/Env)'))
                seasonal = _clean(row.get('Seasonal Variation'))
                age_group = _clean(row.get('Age Group'))
                gender = _clean(row.get('Gender'))
                lifestyle = _clean(row.get('Occupation and Lifestyle'))
                remedies = _clean(row.get('Herbal/Alternative Remedies'))
                herbs = _clean(row.get('Ayurvedic Herbs'))
                formulation = _clean(row.get('Formulation'))
                doshas = _clean(row.get('Doshas')) or 'Tridoshic'
                prakriti = _clean(row.get('Constitution/Prakriti'))
                diet_lifestyle = _clean(row.get('Diet and Lifestyle Recommendations'))
                yoga = _clean(row.get('Yoga & Physical Therapy'))
                intervention = _clean(row.get('Medical Intervention'))
                prevention = _clean(row.get('Prevention'))
                prognosis = _clean(row.get('Prognosis'))
                complications = _clean(row.get('Complications'))
                patient_recs = _clean(row.get('Patient Recommendations'))

                slug_id = f"AYUR-{idx:03d}-" + re.sub(r'[^a-zA-Z0-9]+', '-', dis_name).strip('-').lower()
                category = _categorize_ayurveda_disease(dis_name, symptoms, herbs)

                # Parse herb tags
                herb_tags = [h.strip() for h in re.split(r'[,;]+', herbs) if h.strip()]
                yoga_tags = [y.strip() for y in re.split(r'[,;]+', yoga) if y.strip()]

                item = {
                    "id": slug_id,
                    "index": idx,
                    "name": dis_name,
                    "hindi_name": hindi_name,
                    "marathi_name": marathi_name,
                    "category": category,
                    "symptoms": symptoms,
                    "diagnosis_tests": diagnosis,
                    "severity": severity,
                    "duration_of_treatment": duration,
                    "medical_history": med_history,
                    "current_medications": curr_meds,
                    "risk_factors": risk_factors,
                    "environmental_factors": env_factors,
                    "sleep_patterns": sleep,
                    "stress_levels": stress,
                    "physical_activity": activity,
                    "family_history": family_hist,
                    "dietary_habits": diet,
                    "allergies": allergies,
                    "seasonal_variation": seasonal,
                    "age_group": age_group,
                    "gender": gender,
                    "lifestyle": lifestyle,
                    "herbal_remedies": remedies,
                    "ayurvedic_herbs": herbs,
                    "herb_tags": herb_tags,
                    "formulation": formulation,
                    "doshas": doshas,
                    "constitution_prakriti": prakriti,
                    "diet_recommendations": diet_lifestyle,
                    "yoga_therapy": yoga,
                    "yoga_tags": yoga_tags,
                    "medical_intervention": intervention,
                    "prevention": prevention,
                    "prognosis": prognosis,
                    "complications": complications,
                    "patient_recommendations": patient_recs
                }

                ALL_AYUR_DISEASES.append(item)
                AYUR_DISEASES_BY_ID[slug_id] = item
                AYUR_DISEASES_BY_ID[dis_name.lower()] = item

                # Map by primary Dosha
                for d_token in ['Vata', 'Pitta', 'Kapha']:
                    if d_token.lower() in doshas.lower():
                        AYUR_DISEASES_BY_DOSHA.setdefault(d_token, []).append(item)

                idx += 1

        # Curate top flagship conditions for instant initial render
        flagship_names = [
            'acidity', 'cough', 'arthritis', 'anxiety', 'diabetes', 'insomnia',
            'hypertension', 'asthma', 'migraine', 'acne', 'obesity', 'pcos',
            'constipation', 'allergies', 'back pain', 'jaundice', 'hypothyroidism',
            'anemia', 'alopecia', 'gerd', 'gout', 'sciatica', 'depression', 'sinusitis'
        ]
        
        for item in ALL_AYUR_DISEASES:
            if any(fn in item['name'].lower() for fn in flagship_names):
                TOP_FEATURED_AYUR_CONDITIONS.append(item)
                if len(TOP_FEATURED_AYUR_CONDITIONS) >= 36:
                    break
        
        if len(TOP_FEATURED_AYUR_CONDITIONS) < 36:
            TOP_FEATURED_AYUR_CONDITIONS = ALL_AYUR_DISEASES[:36]

        print(f"✅ AyurGenixAI Dataset Loaded: {len(ALL_AYUR_DISEASES)} Ayurvedic conditions indexed across 10 clinical domains.")

    except Exception as e:
        print(f"❌ Error loading AyurGenixAI dataset: {e}")

# Initialize upon module import
load_ayurveda_catalog()

def get_all_ayurveda_diseases():
    return ALL_AYUR_DISEASES

def get_featured_ayurveda_conditions():
    return TOP_FEATURED_AYUR_CONDITIONS

def get_ayurveda_disease_by_id_or_name(identifier):
    if not identifier:
        return None
    ident_str = str(identifier).strip().lower()
    if ident_str in AYUR_DISEASES_BY_ID:
        return AYUR_DISEASES_BY_ID[ident_str]
    for item in ALL_AYUR_DISEASES:
        if item["id"].lower() == ident_str or item["name"].lower() == ident_str:
            return item
    # Partial match
    for item in ALL_AYUR_DISEASES:
        if ident_str in item["name"].lower() or (item["hindi_name"] and ident_str in item["hindi_name"].lower()):
            return item
    return None

def search_ayurveda_catalog(query="", dosha="all", category="all", page=1, limit=24):
    """
    Multilingual fuzzy search across English, Hindi, Marathi, symptoms, herbs, and Doshas.
    """
    q = (query or "").strip().lower()
    dosha_filter = (dosha or "all").strip().lower()
    cat_filter = (category or "all").strip().lower()

    matches = []
    for item in ALL_AYUR_DISEASES:
        # Category filter
        if cat_filter != "all" and item.get("category", "").lower() != cat_filter:
            continue

        # Dosha filter
        if dosha_filter != "all" and dosha_filter not in item.get("doshas", "").lower():
            continue

        # Text search (English name, Hindi name, Marathi name, symptoms, herbs, yoga)
        if q:
            corpus = f"{item['name']} {item['hindi_name']} {item['marathi_name']} {item['symptoms']} {item['ayurvedic_herbs']} {item['formulation']} {item['yoga_therapy']} {item['category']}".lower()
            if q not in corpus:
                continue

        matches.append(item)

    total = len(matches)
    start = (page - 1) * limit
    end = start + limit
    paginated = matches[start:end]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
        "results": paginated
    }
