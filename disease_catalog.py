"""
disease_catalog.py
High-performance in-memory indexer for the MedQuAD medical knowledge dataset (16,412 QA pairs across 5,126 conditions).
Provides instant search by disease name, symptom keywords, therapeutic category, and full clinical monograph generation.
"""

import os
import csv
import re
from collections import defaultdict

MEDQUAD_CSV_PATH = os.path.join(os.path.dirname(__file__), 'medquad.csv')

ALL_DISEASES = []
DISEASES_BY_ID = {}
DISEASES_BY_NAME = {}
DISEASES_BY_CATEGORY = defaultdict(list)
TOP_CURATED_DISEASES = []

def _clean_text(val):
    if not val:
        return ""
    # Strip excess whitespace, html remnants, or odd formatting
    text = str(val).strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def _extract_symptom_tags(text, disease_name=""):
    """Extracts top concise symptom phrases for pill badges."""
    common_symptom_patterns = [
        'fever', 'headache', 'fatigue', 'shortness of breath', 'chest pain',
        'nausea', 'vomiting', 'dizziness', 'cough', 'joint pain', 'muscle weakness',
        'swelling', 'rash', 'itching', 'weight loss', 'weight gain', 'blurred vision',
        'vision loss', 'high blood pressure', 'tremor', 'seizure', 'stomach pain',
        'diarrhea', 'constipation', 'dry mouth', 'numbness', 'tingling', 'difficulty swallowing',
        'loss of appetite', 'chills', 'night sweats', 'sneezing', 'sore throat', 'wheezing',
        'palpitations', 'insomnia', 'memory loss', 'anxiety', 'mood changes', 'back pain'
    ]
    
    found = []
    text_lower = text.lower()
    for s in common_symptom_patterns:
        if s in text_lower and s not in disease_name.lower():
            found.append(s.title())
            if len(found) >= 5:
                break
                
    if not found:
        # Fallback to key sentences or phrases
        words = [w.capitalize() for w in re.findall(r'[a-zA-Z]{4,}', text)[:4] if w.lower() not in ['symptoms', 'disease', 'condition', 'often', 'include', 'people', 'patient']]
        found = words[:4] if words else ['Clinical Observation Needed']
        
    return found

def _categorize_disease(name, overview_text, symptoms_text):
    combo = f"{name} {overview_text} {symptoms_text}".lower()
    
    if re.search(r'cancer|tumor|carcinoma|leukemia|lymphoma|sarcoma|melanoma|oncolog|neoplasm|malignan', combo):
        return 'Oncology & Cancer'
    elif re.search(r'heart|cardiac|artery|hypertension|blood pressure|angina|arrhythmia|vascular|stroke|atherosclerosis|coronary|aortic', combo):
        return 'Cardiology & Heart'
    elif re.search(r'brain|neuro|nerve|seizure|epilepsy|parkinson|alzheimer|migraine|dementia|sclerosis|ataxia|neuropathy|paralysis|stroke', combo):
        return 'Neurology & Brain'
    elif re.search(r'diabet|insulin|thyroid|hormon|endocrine|glucose|adrenal|pituitary|cushing|metabolic', combo):
        return 'Diabetes & Endocrine'
    elif re.search(r'lung|respiratory|asthma|bronch|pneumonia|copd|pulmonary|cough|breath|emphysema|cystic fibrosis', combo):
        return 'Respiratory & Pulmonology'
    elif re.search(r'skin|derma|rash|eczema|psoriasis|acne|alopecia|melanin|epiderm|cutaneous|blister', combo):
        return 'Dermatology & Skin'
    elif re.search(r'stomach|gut|digest|bowel|colon|gastric|liver|hepatitis|cirrhosis|pancrea|crohn|ulcer|gerd|esophag|intestin', combo):
        return 'Gastroenterology & Digestive'
    elif re.search(r'infect|virus|viral|bacteria|fungal|hiv|aids|flu|covid|tuberculosis|malaria|measles|fever|parasit', combo):
        return 'Infectious Diseases'
    elif re.search(r'bone|joint|arthrit|osteo|spine|muscle|myopathy|musculoskeletal|gout|fracture|tendon|rheumat', combo):
        return 'Musculoskeletal & Bones'
    elif re.search(r'eye|ocular|retin|glaucoma|vision|cornea|cataract|blindness|optic', combo):
        return 'Ophthalmology & Eye'
    elif re.search(r'syndrome|mutation|chromosom|inherited|congenital|gene|genetic|familial|dwarfism|dystrophy|autosomal|deficiency', combo):
        return 'Rare & Genetic Disorders'
    
    return 'General Clinical Medicine'

def load_all_diseases():
    """Parses and aggregates all 16,412 QA pairs across 5,126 conditions from medquad.csv."""
    global ALL_DISEASES, DISEASES_BY_ID, DISEASES_BY_NAME, DISEASES_BY_CATEGORY, TOP_CURATED_DISEASES
    
    if ALL_DISEASES:
        return ALL_DISEASES
        
    if not os.path.exists(MEDQUAD_CSV_PATH):
        print(f"⚠️ medquad.csv not found at {MEDQUAD_CSV_PATH}")
        return []
        
    disease_map = defaultdict(lambda: {
        'name': '',
        'overviews': [],
        'symptoms': [],
        'causes': [],
        'treatments': [],
        'diagnoses': [],
        'preventions': [],
        'sources': set(),
        'all_qa': []
    })
    
    with open(MEDQUAD_CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fa = _clean_text(row.get('focus_area', ''))
            if not fa:
                continue
                
            q = _clean_text(row.get('question', ''))
            ans = _clean_text(row.get('answer', ''))
            src = _clean_text(row.get('source', 'NIH / CDC MedQuAD'))
            
            if not ans:
                continue
                
            entry = disease_map[fa]
            entry['name'] = fa
            entry['sources'].add(src)
            entry['all_qa'].append({'question': q, 'answer': ans, 'source': src})
            
            q_lower = q.lower()
            if 'symptom' in q_lower or 'sign' in q_lower:
                entry['symptoms'].append(ans)
            elif 'cause' in q_lower or 'risk' in q_lower or 'inherit' in q_lower or 'genetic' in q_lower:
                entry['causes'].append(ans)
            elif 'treatment' in q_lower or 'cure' in q_lower or 'therap' in q_lower or 'manage' in q_lower or 'surgery' in q_lower or 'medication' in q_lower:
                entry['treatments'].append(ans)
            elif 'diagnos' in q_lower or 'test' in q_lower or 'exam' in q_lower or 'screen' in q_lower:
                entry['diagnoses'].append(ans)
            elif 'prevent' in q_lower or 'avoid' in q_lower:
                entry['preventions'].append(ans)
            elif 'what is' in q_lower or 'what are' in q_lower or 'overview' in q_lower or not entry['overviews']:
                entry['overviews'].append(ans)
                
    compiled_list = []
    by_cat = defaultdict(list)
    by_id = {}
    by_name = {}
    
    for idx, (name, d) in enumerate(disease_map.items(), start=1):
        dis_id = f"dis_{idx}"
        
        # Best synthesis
        overview = d['overviews'][0] if d['overviews'] else (d['all_qa'][0]['answer'] if d['all_qa'] else f"{name} is a diagnosed medical condition.")
        symptoms_text = "\n\n".join(d['symptoms']) if d['symptoms'] else "Symptoms vary widely depending on stage and individual patient presentation. Clinical evaluation is recommended."
        causes_text = "\n\n".join(d['causes']) if d['causes'] else "Underlying etiology may include genetic, environmental, or physiological factors."
        treatments_text = "\n\n".join(d['treatments']) if d['treatments'] else "Treatment plans focus on symptom management, pharmacological therapy, and clinical supervision."
        diagnoses_text = "\n\n".join(d['diagnoses']) if d['diagnoses'] else "Diagnosis involves medical history examination, blood work, physical assessment, and diagnostic imaging."
        preventions_text = "\n\n".join(d['preventions']) if d['preventions'] else "Adopting a healthy lifestyle, avoiding known triggers, and early medical intervention help mitigate risks."
        
        category = _categorize_disease(name, overview, symptoms_text)
        symptom_tags = _extract_symptom_tags(symptoms_text, name)
        
        # Primary source badge
        src_list = sorted(list(d['sources']))
        source_label = ", ".join(src_list) if src_list else "NIH / CDC MedQuAD"
        
        dis_obj = {
            'id': dis_id,
            'name': name,
            'category': category,
            'overview': overview,
            'symptoms_text': symptoms_text,
            'symptom_tags': symptom_tags,
            'causes_text': causes_text,
            'treatments_text': treatments_text,
            'diagnoses_text': diagnoses_text,
            'preventions_text': preventions_text,
            'sources': src_list,
            'source_label': source_label,
            'qa_count': len(d['all_qa']),
            'all_qa': d['all_qa']
        }
        
        compiled_list.append(dis_obj)
        by_id[dis_id] = dis_obj
        by_name[name.lower()] = dis_obj
        by_cat[category].append(dis_obj)
        
    ALL_DISEASES = compiled_list
    DISEASES_BY_ID = by_id
    DISEASES_BY_NAME = by_name
    DISEASES_BY_CATEGORY = by_cat
    
    # Curate high-value flagship conditions for instant initial rendering
    flagship_names = [
        'Glaucoma', 'High Blood Pressure', 'Diabetes', 'Asthma', 'Heart Attack', 'Migraine',
        'Alzheimer\'s Disease', 'Eczema', 'Stroke', 'Depression', 'Pneumonia', 'Lupus',
        'Chronic Kidney Disease', 'Osteoarthritis', 'Gout', 'Anemia', 'Hepatitis B',
        'Thyroid Diseases', 'Crohn\'s Disease', 'Multiple Sclerosis', 'Parkinson\'s Disease',
        'Celiac Disease', 'Psoriasis', 'Sleep Apnea', 'Tuberculosis', 'Dengue', 'Measles',
        'Arrhythmia', 'Coronary Artery Disease', 'Rheumatoid Arthritis', 'Endometriosis',
        'Cystic Fibrosis', 'Skin Cancer', 'Breast Cancer', 'Prostate Cancer', 'Colon Cancer'
    ]
    
    curated = []
    for fn in flagship_names:
        matched = next((d for d in compiled_list if fn.lower() in d['name'].lower() or d['name'].lower() in fn.lower()), None)
        if matched and matched not in curated:
            curated.append(matched)
            
    # Supplement up to 36 top diseases with high QA counts
    if len(curated) < 36:
        sorted_by_qa = sorted(compiled_list, key=lambda x: -x['qa_count'])
        for item in sorted_by_qa:
            if item not in curated:
                curated.append(item)
                if len(curated) >= 36:
                    break
                    
    TOP_CURATED_DISEASES = curated
    print(f"✅ MedQuAD Disease Catalog Loaded: {len(ALL_DISEASES)} conditions indexed from medquad.csv (Curated {len(TOP_CURATED_DISEASES)} flagship diseases)")
    return ALL_DISEASES

def get_top_diseases(limit=36):
    if not ALL_DISEASES:
        load_all_diseases()
    return TOP_CURATED_DISEASES[:limit]

def search_diseases(query="", category="all", symptom="", page=1, limit=24):
    """
    High-speed multi-faceted search across all 5,126 diseases from medquad.csv.
    Matches disease name, symptom keywords, category, and QA answer text.
    """
    if not ALL_DISEASES:
        load_all_diseases()
        
    q = (query or "").strip().lower()
    cat = (category or "all").strip().lower()
    sym = (symptom or "").strip().lower()
    
    # 1. Category Filter
    if cat and cat != "all":
        matched_cat = next((k for k in DISEASES_BY_CATEGORY.keys() if k.lower() == cat or cat in k.lower()), None)
        pool = DISEASES_BY_CATEGORY.get(matched_cat, []) if matched_cat else ALL_DISEASES
    else:
        pool = ALL_DISEASES
        
    # 2. Text Search Filtering
    if q or sym:
        search_terms = f"{q} {sym}".strip().lower()
        scored = []
        for d in pool:
            name_lower = d['name'].lower()
            symptom_lower = d['symptoms_text'].lower()
            overview_lower = d['overview'].lower()
            
            # Match score ranking
            if search_terms == name_lower:
                scored.append((0, d))
            elif search_terms in name_lower:
                scored.append((1, d))
            elif any(search_terms in tag.lower() for tag in d['symptom_tags']):
                scored.append((2, d))
            elif search_terms in symptom_lower:
                scored.append((3, d))
            elif search_terms in overview_lower:
                scored.append((4, d))
            elif all(term in f"{name_lower} {symptom_lower} {overview_lower}" for term in search_terms.split()):
                scored.append((5, d))
                
        scored.sort(key=lambda x: (x[0], -x[1]['qa_count']))
        filtered = [item[1] for item in scored]
    else:
        filtered = pool
        
    total_count = len(filtered)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated = filtered[start_idx:end_idx]
    
    return {
        'total': total_count,
        'page': page,
        'limit': limit,
        'total_pages': (total_count + limit - 1) // limit if limit else 1,
        'diseases': paginated
    }

def find_disease_by_name_or_id(identifier):
    if not ALL_DISEASES:
        load_all_diseases()
        
    clean = str(identifier).strip().lower()
    if clean in DISEASES_BY_ID:
        return DISEASES_BY_ID[clean]
    if clean in DISEASES_BY_NAME:
        return DISEASES_BY_NAME[clean]
        
    # Substring search
    for d in ALL_DISEASES:
        if clean in d['name'].lower() or d['name'].lower() in clean:
            return d
            
    return None

# Load on import
load_all_diseases()
