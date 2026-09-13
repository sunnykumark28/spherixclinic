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

def search_medicines(query="", category="all", page=1, limit=32):
    """
    High-speed search across all 11,825 medicines by name, chemical salt, manufacturer, or uses.
    Supports category filtering and pagination.
    """
    if not ALL_MEDICINES:
        load_all_medicines()
        
    q = (query or "").strip().lower()
    cat = (category or "all").strip().lower()
    
    # 1. Category subset
    if cat and cat != "all":
        # Match category name
        matched_cat = next((k for k in MEDICINES_BY_CATEGORY.keys() if k.lower() == cat or cat in k.lower()), None)
        pool = MEDICINES_BY_CATEGORY.get(matched_cat, []) if matched_cat else ALL_MEDICINES
    else:
        pool = ALL_MEDICINES
        
    # 2. Text Search Filtering
    if q:
        results = []
        for m in pool:
            name = m['name'].lower()
            salt = m['salt_composition'].lower()
            mfg = m['manufacturer'].lower()
            uses = m['uses'].lower()
            
            # Match score
            if q in name:
                results.append((0, m))  # Exact name substring: highest priority
            elif q in salt:
                results.append((1, m))  # Chemical salt match: high priority
            elif q in uses:
                results.append((2, m))  # Indication match
            elif q in mfg:
                results.append((3, m))  # Manufacturer match
                
        results.sort(key=lambda x: (x[0], -x[1]['rating'], -x[1]['rating_count']))
        filtered = [item[1] for item in results]
    else:
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

# Initialize on import
load_all_medicines()
