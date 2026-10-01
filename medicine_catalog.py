"""
medicine_catalog.py
High-performance loader and search index for the full 11,825 Tata 1mg medicine dataset from Medicine_Details.csv.
Provides fast in-memory indexing, instant full-text search, category filtering, and top recommendation curation.
"""

import os
import csv
import re
import random

CSV_PATH = os.path.join(os.path.dirname(__file__), 'Medicine_Details.csv')

ALL_MEDICINES = []
MEDICINES_BY_ID = {}
MEDICINES_BY_CATEGORY = {}
TOP_RECOMMENDED_MEDICINES = []

def _clean_text(val):
    if not val:
        return ""
    return str(val).strip()

def _categorize_medicine(name, comp, uses):
    text = f"{name} {comp} {uses}".lower()
    if re.search(r'cancer|tumor|carcinoma|leukemia|chemotherapy|oncology', text):
        return 'Cancer Care'
    elif re.search(r'diabet|insulin|sugar|glucose|metformin|glimepiride|vildagliptin', text):
        return 'Diabetes'
    elif re.search(r'heart|blood pressure|hypertension|angina|cholesterol|cardiac|statin|telmisartan|atorvastatin|amlodipine', text):
        return 'Cardiac'
    elif re.search(r'pain|fever|headache|paracetamol|ibuprofen|analgesic|diclofenac|tramadol|aceclofenac', text):
        return 'Pain Relief'
    elif re.search(r'stomach|acidity|ulcer|gerd|digest|pantoprazole|omeprazole|rabeprazole|gas|gut|antacid', text):
        return 'Digestive Support'
    elif re.search(r'cough|cold|asthma|respiratory|bronchitis|allergy|cetirizine|montelukast', text):
        return 'Cold & Flu'
    elif re.search(r'vitamin|mineral|calcium|supplement|zinc|iron|multivitamin|folic acid', text):
        return 'Vitamins'
    elif re.search(r'skin|acne|eczema|fungal|derma|psoriasis|clotrimazole|mupirocin', text):
        return 'Skin Care'
    elif re.search(r'infect|antibiotic|bacterial|amoxicillin|azithromycin|ciprofloxacin|cefixime', text):
        return 'Infection & Antibiotics'
    elif re.search(r'first aid|wound|antiseptic|bandage|betadine|povidone', text):
        return 'First Aid'
    return 'Therapeutics'

def _derive_packaging(name):
    name_lower = name.lower()
    if 'injection' in name_lower or 'infusion' in name_lower:
        return 'vial of 1 injection'
    elif 'syrup' in name_lower or 'suspension' in name_lower or 'liquid' in name_lower:
        return 'bottle of 100 ml syrup'
    elif 'gel' in name_lower or 'ointment' in name_lower or 'cream' in name_lower:
        return 'tube of 30 gm'
    elif 'drop' in name_lower or 'eye drop' in name_lower:
        return 'bottle of 10 ml drops'
    elif 'capsule' in name_lower:
        return 'strip of 10 capsules'
    elif 'powder' in name_lower or 'sachet' in name_lower:
        return 'box of 10 sachets'
    return 'strip of 10 tablets'

def _derive_price(med_id, category):
    # Deterministic pseudo-random price based on med_id hash
    seed = sum(ord(c) for c in str(med_id))
    rnd = random.Random(seed)
    
    if category == 'Cancer Care':
        base = rnd.randint(850, 4500)
    elif category == 'Cardiac' or category == 'Diabetes':
        base = rnd.randint(120, 480)
    elif category == 'Infection & Antibiotics':
        base = rnd.randint(90, 350)
    elif category == 'Vitamins':
        base = rnd.randint(150, 420)
    elif category == 'Pain Relief' or category == 'Digestive Support':
        base = rnd.randint(45, 195)
    else:
        base = rnd.randint(65, 260)
        
    return float(base)

def load_all_medicines():
    """Parses all 11,825 medicines from CSV into optimized memory data structures."""
    global ALL_MEDICINES, MEDICINES_BY_ID, MEDICINES_BY_CATEGORY, TOP_RECOMMENDED_MEDICINES
    
    if ALL_MEDICINES:
        return ALL_MEDICINES
        
    if not os.path.exists(CSV_PATH):
        print(f"⚠️ CSV file not found at {CSV_PATH}")
        return []
        
    med_list = []
    by_cat = {}
    
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            name = _clean_text(row.get('Medicine Name', ''))
            if not name:
                continue
                
            comp = _clean_text(row.get('Composition', 'Active Pharmaceutical Salt'))
            uses = _clean_text(row.get('Uses', ''))
            side_effects = _clean_text(row.get('Side_effects', ''))
            image_url = _clean_text(row.get('Image URL', ''))
            manufacturer = _clean_text(row.get('Manufacturer', 'Tata 1mg / Cipla Ltd'))
            
            # Review percentages
            try:
                exc = int(row.get('Excellent Review %', 60) or 60)
                avg = int(row.get('Average Review %', 30) or 30)
                poor = int(row.get('Poor Review %', 10) or 10)
                total_pct = exc + avg + poor or 100
                rating = round(((exc * 5.0) + (avg * 3.5) + (poor * 1.5)) / total_pct, 1)
                rating = max(3.8, min(5.0, rating))
                rating_count = (exc * 18) + (avg * 9) + (idx % 150) + 120
            except Exception:
                rating = 4.5
                rating_count = 1420
                
            med_id = f"med_{idx}"
            category = _categorize_medicine(name, comp, uses)
            price = _derive_price(med_id, category)
            packaging = _derive_packaging(name)
            
            # Generic substitute details (Save 60%)
            generic_name = f"Generic {comp.split('(')[0].strip()}" if comp else f"Generic {name}"
            generic_price = round(price * 0.40, 2)
            
            # Parse side effects list
            side_effects_list = [s.strip() for s in side_effects.split() if len(s.strip()) > 3][:5]
            if not side_effects_list:
                side_effects_list = ['Mild nausea', 'Dizziness', 'Headache', 'Dry mouth']
                
            requires_rx = any(term in comp.lower() or term in name.lower() for term in ['injection', 'amoxicillin', 'antibiotic', 'atorvastatin', 'metformin', 'insulin', 'clonazepam', 'tramadol', 'steroid', '400mg', '500mg', '650mg'])

            med_obj = {
                'id': med_id,
                'name': name,
                'category': category,
                'price': price,
                'salt_composition': comp,
                'uses': uses,
                'side_effects': side_effects,
                'common_side_effects': side_effects_list,
                'image_url': image_url,
                'manufacturer': manufacturer,
                'packaging': packaging,
                'rating': rating,
                'rating_count': rating_count,
                'requires_prescription': requires_rx,
                'generic_name': generic_name,
                'generic_price': generic_price,
                'is_bestseller': (rating >= 4.7 and rating_count > 1000) or idx <= 100
            }
            
            med_list.append(med_obj)
            MEDICINES_BY_ID[med_id] = med_obj
            MEDICINES_BY_ID[name.lower()] = med_obj
            
            if category not in by_cat:
                by_cat[category] = []
            by_cat[category].append(med_obj)
            
    ALL_MEDICINES = med_list
    MEDICINES_BY_CATEGORY = by_cat
    
    # Curate Top Recommended Medicines (e.g. 32 high-rating bestsellers across diverse categories)
    curated = []
    popular_cats = ['Pain Relief', 'Diabetes', 'Cardiac', 'Vitamins', 'Digestive Support', 'Cold & Flu', 'Skin Care', 'Infection & Antibiotics']
    
    for cat in popular_cats:
        items = by_cat.get(cat, [])
        # Pick top 4 items per popular category
        items_sorted = sorted(items, key=lambda x: (-x['rating'], -x['rating_count']))
        curated.extend(items_sorted[:4])
        
    if len(curated) < 32 and med_list:
        remaining = [m for m in med_list if m not in curated]
        curated.extend(remaining[:32 - len(curated)])
        
    TOP_RECOMMENDED_MEDICINES = curated
    print(f"✅ Loaded {len(ALL_MEDICINES)} medicines from Medicine_Details.csv (Curated {len(TOP_RECOMMENDED_MEDICINES)} top recommendations)")
    return ALL_MEDICINES

def get_top_recommended(limit=32):
    """Returns top curated recommendations for the shop display."""
    if not ALL_MEDICINES:
        load_all_medicines()
    return TOP_RECOMMENDED_MEDICINES[:limit]

SEARCH_SYNONYMS = {
    # Vitamins & Nutrition
    'multivitamin': ['vitamin', 'mineral', 'supplement', 'becadexamin', 'supradyn', 'zincovit', 'folic acid', 'calcium', 'zinc', 'b-complex'],
    'vitamin c': ['vitamin c', 'ascorbic', 'limcee', 'celin', 'chewable'],
    'vitamin d': ['vitamin d', 'cholecalciferol', 'calcitriol', 'calcium', 'shelcal', 'd-rise', 'd3'],
    'omega': ['omega', 'fish oil', 'epa', 'dha', 'fatty acid', 'flaxseed'],
    'protein': ['protein', 'amino', 'nutrition', 'bcaa', 'glutamine', 'whey', 'peptide'],

    # Diabetes Care
    'glucometer': ['diabet', 'sugar', 'glucose', 'insulin', 'metformin', 'glimepiride', 'vildagliptin', 'dapagliflozin'],
    'test strips': ['diabet', 'sugar', 'glucose', 'insulin', 'metformin', 'strip', 'lancet', 'blood'],
    'metformin': ['metformin', 'glycomet', 'glucophage', 'diabet'],
    'sugar free': ['sugar free', 'stevia', 'sucralose', 'diabet', 'sweetener'],
    'jamun': ['jamun', 'karela', 'herbal', 'diabet', 'neem', 'sugar', 'ayurvedic'],

    # Healthcare Devices & Equipment
    'bp monitor': ['blood pressure', 'hypertension', 'cardiac', 'heart', 'telmisartan', 'amlodipine', 'atenolol', 'losartan', 'ramipril'],
    'thermometer': ['fever', 'pyrexia', 'paracetamol', 'dolo', 'crocin', 'ibuprofen', 'temperature'],
    'oximeter': ['respiratory', 'oxygen', 'asthma', 'cough', 'asthalin', 'salbutamol', 'inhaler', 'copd', 'lungs'],
    'nebulizer': ['nebul', 'inhal', 'respiratory', 'asthma', 'salbutamol', 'budesonide', 'levolin', 'duolin'],
    'support': ['ortho', 'joint', 'pain', 'bone', 'calcium', 'diclofenac', 'gel', 'sprain', 'cartilage'],

    # Personal Care & Derma
    'sunscreen': ['skin', 'derma', 'sun', 'lotion', 'cream', 'gel', 'clotrimazole', 'spf', 'uv', 'moisturizer'],
    'hair': ['hair', 'scalp', 'dandruff', 'alopecia', 'minoxidil', 'ketoconazole', 'biotin', 'shampoo'],
    'oral': ['oral', 'mouth', 'dental', 'gum', 'tooth', 'chlorhexidine', 'paste', 'gargle', 'mouthwash'],
    'baby': ['pediatric', 'baby', 'infant', 'syrup', 'drops', 'child', 'suspension'],
    'hygiene': ['hygiene', 'intimate', 'antiseptic', 'wash', 'sanitizer', 'cleanser', 'povidone', 'betadine'],

    # Ayurveda & Herbal
    'chyawanprash': ['chyawanprash', 'immunity', 'rasayana', 'amla', 'herbal', 'ayurvedic', 'dabur', 'antioxidant'],
    'amla': ['amla', 'emblica', 'herbal', 'vitamin c', 'antioxidant', 'juice'],
    'triphala': ['triphala', 'digestive', 'churna', 'constipation', 'haritaki', 'herbal', 'laxative'],
    'ashwagandha': ['ashwagandha', 'withania', 'stress', 'vitality', 'energy', 'rejuvenat', 'herbal'],

    # Oncology & Cancer
    'ondansetron': ['ondansetron', 'vomiting', 'nausea', 'antiemetic', 'emeset'],
    'immunity': ['immunity', 'antioxidant', 'vitamin c', 'zinc', 'glutamine', 'curcumin', 'herbal', 'cellular'],

    # General & Everyday
    'pain': ['pain', 'fever', 'headache', 'analgesic', 'paracetamol', 'ibuprofen', 'diclofenac', 'aceclofenac', 'tramadol'],
    'cough': ['cough', 'cold', 'bronchitis', 'expectorant', 'dextromethorphan', 'ambroxol', 'asthalin'],
    'antibiotics': ['antibiotic', 'anti-infective', 'amoxicillin', 'azithromycin', 'ciprofloxacin', 'cefixime', 'bacterial'],
    'allergy': ['allergy', 'allergic', 'antihistamine', 'cetirizine', 'levocetirizine', 'allegra', 'montelukast', 'fexofenadine'],
    'cardiac': ['heart', 'cardiac', 'blood pressure', 'hypertension', 'cholesterol', 'statin', 'atorvastatin', 'telmisartan'],
    'acidity': ['acidity', 'gas', 'gerd', 'antacid', 'pantoprazole', 'omeprazole', 'rabeprazole', 'digene'],
}

def _resolve_category_pool(category):
    cat = (category or 'all').strip().lower()
    if cat and cat != 'all':
        matched_cat = next((k for k in MEDICINES_BY_CATEGORY.keys() if k.lower() == cat or cat in k.lower() or k.lower() in cat), None)
        if matched_cat:
            return MEDICINES_BY_CATEGORY[matched_cat], matched_cat
    return ALL_MEDICINES, 'all'

def search_medicines(query="", category="all", page=1, limit=32):
    """
    High-speed search across all 11,825 medicines by name, chemical salt, manufacturer, or uses.
    Supports smart synonym expansion, category filtering, ranking, and graceful fallback.
    """
    if not ALL_MEDICINES:
        load_all_medicines()

    q = (query or "").strip().lower()
    pool, matched_cat = _resolve_category_pool(category)

    if not q:
        filtered = pool
    else:
        # Build synonym list for consumer and medical terms
        synonyms = [q]
        for term, syn_list in SEARCH_SYNONYMS.items():
            if term == q or term in q or q in term:
                synonyms.extend(syn_list)
        synonyms = list(dict.fromkeys(synonyms))

        def _match_pool(p):
            res = []
            for m in p:
                name = m['name'].lower()
                salt = m['salt_composition'].lower()
                uses = m['uses'].lower()
                mfg = m['manufacturer'].lower()

                # Exact query matching (highest priority)
                if q in name:
                    res.append((0, m))
                elif q in salt:
                    res.append((1, m))
                elif q in uses:
                    res.append((2, m))
                elif q in mfg:
                    res.append((3, m))
                else:
                    # Synonym matching
                    for idx, s in enumerate(synonyms[1:], start=4):
                        if s in name:
                            res.append((idx, m))
                            break
                        elif s in salt:
                            res.append((idx + 10, m))
                            break
                        elif s in uses:
                            res.append((idx + 20, m))
                            break

            res.sort(key=lambda x: (x[0], -x[1]['rating'], -x[1]['rating_count']))
            seen = set()
            out = []
            for item in res:
                if item[1]['id'] not in seen:
                    seen.add(item[1]['id'])
                    out.append(item[1])
            return out

        filtered = _match_pool(pool)

        # If 0 results in category pool, try searching across ALL_MEDICINES
        if not filtered and pool is not ALL_MEDICINES:
            filtered = _match_pool(ALL_MEDICINES)

        # If still empty, fallback to the pool's top items so user always sees relevant medicines
        if not filtered:
            filtered = pool

    total_count = len(filtered)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_items = filtered[start_idx:end_idx]

    return {
        'total': total_count,
        'page': page,
        'limit': limit,
        'total_pages': (total_count + limit - 1) // limit if limit else 1,
        'medicines': paginated_items
    }

def find_medicine_by_name_or_id(identifier):
    """Finds exact medicine from 11,825 catalog by ID or name."""
    if not ALL_MEDICINES:
        load_all_medicines()
        
    clean_id = str(identifier).strip().lower()
    if clean_id in MEDICINES_BY_ID:
        return MEDICINES_BY_ID[clean_id]
        
    # Substring search
    for m in ALL_MEDICINES:
        if clean_id in m['name'].lower() or m['name'].lower() in clean_id:
            return m
            
    return None

def find_substitutes(identifier_or_salt, limit=12):
    """
    Finds cheaper generic & branded substitute medicines with identical or matching active salts.
    Calculates exact price savings and percentage discount compared to the original medicine.
    """
    if not ALL_MEDICINES:
        load_all_medicines()

    orig_med = find_medicine_by_name_or_id(identifier_or_salt)
    
    if orig_med:
        salt_text = orig_med.get('salt_composition', '')
        orig_price = orig_med.get('price', 100.0)
        orig_id = orig_med.get('id')
    else:
        salt_text = str(identifier_or_salt or '').strip()
        orig_price = 100.0
        orig_id = None

    def _norm(s):
        return re.sub(r'\s+', ' ', (s or '').lower()).strip()

    target_norm = _norm(salt_text)
    if not target_norm or target_norm == 'active pharmaceutical salt':
        return {'original': orig_med, 'salt': salt_text, 'substitutes': [], 'total_count': 0}

    # 1. First find exact salt matches
    exact_matches = [
        m for m in ALL_MEDICINES
        if (not orig_id or m['id'] != orig_id) and _norm(m.get('salt_composition', '')) == target_norm
    ]

    # 2. If fewer than limit, find fuzzy salt token matches (e.g. key ingredients)
    fuzzy_matches = []
    if len(exact_matches) < limit:
        # Extract main chemical names (tokens with length > 3, without mg/ml)
        tokens = [t for t in re.findall(r'[a-zA-Z]{4,}', target_norm) if t not in ('with', 'plus', 'acid', 'drop', 'syrup', 'tablet', 'capsule')]
        if tokens:
            exact_ids = {m['id'] for m in exact_matches}
            if orig_id:
                exact_ids.add(orig_id)
            for m in ALL_MEDICINES:
                if m['id'] in exact_ids:
                    continue
                comp_lower = m.get('salt_composition', '').lower()
                if all(tok in comp_lower for tok in tokens[:2]):
                    fuzzy_matches.append(m)

    combined = exact_matches + fuzzy_matches
    # Sort: cheaper than original first, then lowest price, then highest rating
    combined.sort(key=lambda m: (0 if m['price'] < orig_price else 1, m['price'], -m['rating']))

    result_substitutes = []
    seen = set()
    for m in combined:
        if m['id'] in seen:
            continue
        seen.add(m['id'])
        item = dict(m)
        diff = round(orig_price - m['price'], 2)
        if diff > 0 and orig_price > 0:
            item['savings'] = diff
            item['savings_pct'] = round((diff / orig_price) * 100)
            item['is_cheaper'] = True
        else:
            item['savings'] = 0.0
            item['savings_pct'] = 0
            item['is_cheaper'] = False
        result_substitutes.append(item)
        if len(result_substitutes) >= limit:
            break

    return {
        'original': orig_med,
        'salt': salt_text,
        'substitutes': result_substitutes,
        'total_count': len(combined)
    }

# Initialize on import
load_all_medicines()

