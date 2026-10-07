"""
Spherix Diagnostic Network - Clinical AI & Groq Intelligence Service
Provides deep laboratory medicine insights, pre-test preparation guides,
biomarker interpretations, and automated pathologist report drafting via Groq API.
"""

import os
import json
import re
import requests
from typing import Dict, Any, Optional, List
from spherix.services.diagnostic_catalog import get_test_by_code, MASTER_TESTS_CATALOG

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_BASE = os.getenv('GROQ_API_BASE', 'https://api.groq.com/openai/v1')
GROQ_API_MODEL = os.getenv('GROQ_API_MODEL', 'openai/gpt-oss-20b')

# Clinical Knowledge Base Fallback for Offline / Non-API environments
FALLBACK_TEST_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "CBC": {
        "overview": "A Complete Blood Count (CBC) is a cornerstone hematological test evaluating cellular components of blood: red cells, white cells, and platelets. It provides immediate diagnostic signals for anemia, bacterial or viral infections, bone marrow disorders, and leukemia.",
        "why_prescribed": [
            "Investigate persistent fatigue, unexplained weakness, or dizziness",
            "Screen for active systemic infections or inflammatory states",
            "Evaluate bleeding tendencies, easy bruising, or clotting issues",
            "Pre-operative health assessment and chemotherapy response monitoring"
        ],
        "biological_role": "Assesses hematopoietic activity in bone marrow, oxygen transport capacity through erythrocyte hemoglobin, and cellular immune response mediated by neutrophils, lymphocytes, monocytes, eosinophils, and basophils.",
        "preparation_guide": {
            "fasting_required": False,
            "fasting_hours": 0,
            "instructions": "No specific fasting required. Drink plenty of water before collection to ensure smooth venipuncture.",
            "medication_advice": "Inform your phlebotomist if taking anticoagulant medications like Warfarin or Aspirin."
        },
        "side_effects_guide": {
            "common_sensations": "Brief, mild pinch during sterile needle insertion. Slight localized tenderness or minor bruising at the puncture site.",
            "rare_reactions": "Mild, transient dizziness or lightheadedness (vasovagal response), especially if anxious or dehydrated.",
            "safety_measures": "100% sterile single-use disposable vacutainers, alcohol swab antisepsis, and certified phlebotomist technique.",
            "aftercare_instructions": "Keep firm pressure on the puncture site with a sterile cotton pad for 2-3 minutes. Keep bandage on for 1 hour. Avoid heavy lifting with the arm for 2 hours, and drink plenty of fluids."
        },
        "interpretation_guide": {
            "high_levels": "Elevated WBC (Leukocytosis) suggests bacterial infection, inflammation, or hematologic malignancy. Elevated RBC (Polycythemia) may indicate chronic hypoxia, smoking, or dehydration. Elevated Platelets (Thrombocytosis) indicate reactive inflammation.",
            "low_levels": "Low Hemoglobin/RBC indicates Anemia (iron deficiency, B12 deficiency, or hemolysis). Low WBC (Leukopenia) indicates viral suppression or bone marrow stress. Low Platelets (Thrombocytopenia) carries risk of spontaneous bleeding."
        },
        "related_health_conditions": ["Iron Deficiency Anemia", "Bacterial & Viral Infections", "Thrombocytopenia", "Leukemia / Lymphoma", "Polycythemia Vera"],
        "recommended_followups": ["Ferritin / Iron Profile", "ESR / CRP Inflammatory Markers", "Peripheral Blood Smear Review", "Vitamin B12 & Folate"],
        "clinical_faqs": [
            {"q": "How long does a CBC take to process?", "a": "Automated 5-part hematology analyzers typically complete a CBC within 2 to 4 hours of accessioning."},
            {"q": "Can I eat before giving a CBC sample?", "a": "Yes. Fasting is not strictly necessary for a standalone CBC unless combined with a Fasting Blood Glucose or Lipid profile."},
            {"q": "What does a high WBC count mean?", "a": "High WBC count usually means your immune system is actively fighting an infection or responding to severe tissue inflammation."}
        ]
    },
    "LIPID": {
        "overview": "A Lipid Profile evaluates circulating cholesterol and triglyceride fractions to quantify cardiovascular and cerebrovascular risk, arterial plaque deposition, and metabolic health.",
        "why_prescribed": [
            "Cardiovascular risk stratification and coronary artery disease screening",
            "Monitoring lipid-lowering pharmacotherapy (e.g. Statins)",
            "Assessment of metabolic syndrome and insulin resistance in diabetic patients",
            "Routine health checkups for adults above 25 years"
        ],
        "biological_role": "Measures Total Cholesterol, High-Density Lipoprotein (HDL - cardioprotective 'good' cholesterol), Low-Density Lipoprotein (LDL - atherogenic 'bad' cholesterol), and Triglycerides transported via apolipoproteins.",
        "preparation_guide": {
            "fasting_required": True,
            "fasting_hours": 10,
            "instructions": "Strict 10-12 hour water-only fasting is required. Avoid alcohol and fatty meals for 24 hours prior to sampling.",
            "medication_advice": "Consult your prescribing doctor before withholding morning statin or blood pressure medications."
        },
        "interpretation_guide": {
            "high_levels": "High LDL (>100 mg/dL) and High Triglycerides (>150 mg/dL) significantly elevate atherosclerosis risk, ischemic heart disease, and pancreatitis.",
            "low_levels": "Low HDL (<40 mg/dL in men, <50 mg/dL in women) indicates reduced reverse cholesterol transport and elevated cardiovascular vulnerability."
        },
        "related_health_conditions": ["Atherosclerosis", "Coronary Artery Disease", "Hyperlipidemia", "Familial Hypercholesterolemia", "Metabolic Syndrome"],
        "recommended_followups": ["Apolipoprotein A1 & B", "hs-CRP (High-Sensitivity C-Reactive Protein)", "HbA1c Glycemic Test", "Carotid Doppler & ECG"],
        "clinical_faqs": [
            {"q": "Why is fasting mandatory for a lipid profile?", "a": "Recent food intake heavily spikes serum triglycerides and chylomicrons, distorting LDL calculations."},
            {"q": "What is an ideal LDL cholesterol level?", "a": "For low-risk individuals, LDL below 100 mg/dL is optimal. For cardiac patients, target LDL is often below 70 or 55 mg/dL."}
        ]
    },
    "TSH": {
        "overview": "Thyroid Stimulating Hormone (TSH) is synthesized by the anterior pituitary gland to regulate thyroid gland synthesis of Triiodothyronine (T3) and Thyroxine (T4). It is the most sensitive first-line screening marker for thyroid dysfunction.",
        "why_prescribed": [
            "Evaluation of unexplained weight fluctuations, persistent fatigue, or mood swings",
            "Screening for heat/cold intolerance, palpitations, or menstrual irregularities",
            "Monitoring levothyroxine (Thyronorm/Eltroxin) dosage titration in hypothyroidism",
            "Fertility evaluation and prenatal maternal screening"
        ],
        "biological_role": "Operates via a negative feedback loop with pituitary-hypothalamic-thyroid axis to regulate basal metabolic rate, cardiac chronotropy, neural conduction, and body thermogenesis.",
        "preparation_guide": {
            "fasting_required": False,
            "fasting_hours": 0,
            "instructions": "Morning blood collection (between 7:00 AM - 10:00 AM) is recommended due to diurnal variations. Biotin supplements should be avoided for 48 hours.",
            "medication_advice": "If on thyroid medication, give blood sample before taking your morning dose unless instructed otherwise by your endocrinologist."
        },
        "interpretation_guide": {
            "high_levels": "Elevated TSH (>4.5 uIU/mL) indicates Primary Hypothyroidism or Hashimoto's Thyroiditis. The pituitary is overworking to stimulate an underactive thyroid gland.",
            "low_levels": "Suppressed TSH (<0.4 uIU/mL) indicates Hyperthyroidism (Graves' disease, toxic nodule) or over-replacement of thyroid hormone medication."
        },
        "related_health_conditions": ["Hypothyroidism", "Hyperthyroidism", "Hashimoto's Thyroiditis", "Graves' Disease", "Subacute Thyroiditis"],
        "recommended_followups": ["Free T3 & Free T4", "Anti-TPO Antibodies", "Anti-Thyroglobulin Antibodies", "Thyroid Ultrasound Scan"],
        "clinical_faqs": [
            {"q": "Does biotin interfere with TSH testing?", "a": "Yes, high-dose biotin (Vitamin B7) can falsely lower TSH in competitive immunoassay platforms. Discontinue for 48 hours prior to testing."},
            {"q": "Why is morning testing preferred for TSH?", "a": "TSH levels follow a circadian rhythm and are highest during early morning hours, providing the most reproducible clinical baseline."}
        ]
    },
    "HBA1C": {
        "overview": "Glycated Hemoglobin (HbA1c) quantifies the percentage of hemoglobin bound to glucose, providing an accurate measure of average plasma glucose concentrations over the preceding 90 to 120 days (the average lifespan of red blood cells).",
        "why_prescribed": [
            "Diagnostic confirmation of Type 2 Diabetes Mellitus and Pre-diabetes",
            "Quarterly glycemic monitoring and therapeutic management for diagnosed diabetics",
            "Evaluation of macrovascular and microvascular complications risk",
            "Assessment of gestational diabetes follow-up"
        ],
        "biological_role": "Reflects non-enzymatic glycation of erythrocyte hemoglobin A0 to forming hemoglobin A1c via the Amadori rearrangement, directly proportional to integrated blood sugar levels.",
        "preparation_guide": {
            "fasting_required": False,
            "fasting_hours": 0,
            "instructions": "Fasting is not required. You may eat and take your normal prescribed medications before the blood draw.",
            "medication_advice": "Continue antidiabetic medications (Metformin, Insulin, etc.) as routinely scheduled."
        },
        "interpretation_guide": {
            "high_levels": "HbA1c 5.7% - 6.4% indicates Pre-diabetes (impaired glucose tolerance). HbA1c >= 6.5% confirms Diabetes Mellitus. HbA1c > 8.0% denotes suboptimal glycemic control requiring therapeutic escalation.",
            "low_levels": "Normal physiological baseline is < 5.7%. Abnormally low values (< 4.0%) may occur in hemolytic anemia, frequent hypoglycemia, or recent blood transfusion."
        },
        "related_health_conditions": ["Type 1 & Type 2 Diabetes Mellitus", "Pre-diabetes", "Diabetic Nephropathy", "Diabetic Retinopathy", "Gestational Diabetes"],
        "recommended_followups": ["Fasting & Post-Prandial Blood Sugar", "Serum Creatinine & eGFR", "Urine Albumin-to-Creatinine Ratio (UACR)", "Lipid Profile"],
        "clinical_faqs": [
            {"q": "How often should a diabetic person get an HbA1c test?", "a": "Every 3 months if glycemic goals are not met or therapy is adjusted; every 6 months if blood sugar is stably controlled."},
            {"q": "Can HbA1c be altered by recent sweet food intake?", "a": "No. HbA1c reflects 3 months of cumulative glucose exposure and is not influenced by food eaten on the day of the test."}
        ]
    },
    "LFT": {
        "overview": "Liver Function Test (LFT) is a comprehensive biochemical panel assessing hepatocellular integrity, synthetic functional capacity (Albumin/Total Protein), and biliary excretory pathways (Bilirubin & Alkaline Phosphatase).",
        "why_prescribed": [
            "Evaluation of jaundice, right upper abdominal pain, dark urine, or pruritus",
            "Monitoring hepatotoxicity from medications (Statins, NSAIDs, Antibiotics, Chemotherapy)",
            "Screening for viral hepatitis, fatty liver disease (NAFLD), and alcoholic liver disease",
            "Routine metabolic panel in chronic disease management"
        ],
        "biological_role": "Quantifies transaminases (ALT/SGPT, AST/SGOT) released upon hepatocellular injury, serum bilirubin fractions (Total, Direct, Indirect), Alkaline Phosphatase (ALP), and Gamma-Glutamyl Transferase (GGT).",
        "preparation_guide": {
            "fasting_required": True,
            "fasting_hours": 8,
            "instructions": "8-hour overnight fasting is recommended for optimal bilirubin and enzyme clarity. Avoid alcohol for at least 48 hours.",
            "medication_advice": "Inform the testing center about all prescribed and over-the-counter herbal supplements."
        },
        "interpretation_guide": {
            "high_levels": "Marked ALT/AST elevation (>5x upper limit) indicates acute hepatitis, drug toxicity, or ischemic hepatitis. High Direct Bilirubin & ALP indicates biliary tract obstruction or cholestasis. Isolated GGT elevation suggests alcohol or enzyme induction.",
            "low_levels": "Low Serum Albumin indicates chronic liver cirrhosis, malabsorption, or protein-losing nephropathy."
        },
        "related_health_conditions": ["Non-Alcoholic Fatty Liver Disease (NAFLD)", "Viral Hepatitis A/B/C", "Liver Cirrhosis", "Gallstones / Choledocholithiasis", "Drug-Induced Liver Injury (DILI)"],
        "recommended_followups": ["Hepatitis B (HBsAg) & Hepatitis C (Anti-HCV)", "Abdominal Ultrasound / FibroScan", "Prothrombin Time (PT/INR)", "Serum Alpha-Fetoprotein (AFP)"],
        "clinical_faqs": [
            {"q": "What is the difference between ALT and AST?", "a": "ALT (SGPT) is highly specific to liver tissue. AST (SGOT) is present in liver as well as heart and skeletal muscle."},
            {"q": "Can fatty liver show normal LFT results?", "a": "Yes, mild to moderate steatosis can occur with borderline or normal transaminases. Ultrasound or FibroScan is recommended for definitive staging."}
        ]
    },
    "KFT": {
        "overview": "Kidney Function Test (KFT / RFT) is an essential diagnostic profile measuring serum Creatinine, Blood Urea Nitrogen (BUN), Uric Acid, and vital Electrolytes (Sodium, Potassium, Chloride) to evaluate glomerular filtration and renal homeostasis.",
        "why_prescribed": [
            "Assessment of renal clearance in hypertension, diabetes, and cardiovascular diseases",
            "Investigation of edema, oliguria, flank pain, or unexplained hypertension",
            "Pre-contrast computed tomography (CT) renal safety screening",
            "Monitoring nephrotoxic drugs (ACE inhibitors, NSAIDs, Aminoglycosides)"
        ],
        "biological_role": "Creatinine and Urea reflect glomerular filtration rate (eGFR). Electrolytes maintain fluid balance, cardiac transmembrane potential, and acid-base equilibrium.",
        "preparation_guide": {
            "fasting_required": False,
            "fasting_hours": 0,
            "instructions": "Maintain normal hydration. Avoid strenuous heavy resistance exercise or excessive cooked red meat intake 24 hours prior.",
            "medication_advice": "Do not stop blood pressure medications without consulting your nephrologist."
        },
        "interpretation_guide": {
            "high_levels": "Elevated Creatinine and Urea signify acute kidney injury (AKI) or progressive chronic kidney disease (CKD). High Uric Acid precipitates Gout and nephrolithiasis. High Potassium (Hyperkalemia) requires urgent cardiac attention.",
            "low_levels": "Low Urea can indicate severe malnutrition or advanced liver insufficiency. Low Sodium (Hyponatremia) causes confusion and lethargy."
        },
        "related_health_conditions": ["Chronic Kidney Disease (CKD)", "Acute Kidney Injury (AKI)", "Hypertensive Nephrosclerosis", "Diabetic Nephropathy", "Hyperuricemia / Gout"],
        "recommended_followups": ["Urine Routine & Microscopic Exam", "Urine Microalbumin / UACR", "Kidney Ultrasound (KUB)", "Serum Cystatin-C"],
        "clinical_faqs": [
            {"q": "What is eGFR and what is a normal value?", "a": "Estimated Glomerular Filtration Rate (eGFR) measures how many milliliters of blood kidneys filter per minute. A normal value is 90 mL/min/1.73m² or higher."},
            {"q": "Can drinking water before the test alter results?", "a": "Moderate water intake is beneficial because dehydration can falsely elevate serum creatinine and urea."}
        ]
    },
    "VITD": {
        "overview": "25-Hydroxy Vitamin D [25(OH)D] is the primary circulating form and gold standard biomarker for assessing systemic Vitamin D nutritional status, bone mineral density, and calcium absorption.",
        "why_prescribed": [
            "Investigation of chronic bone pain, muscle weakness, and fatigue",
            "Screening for Osteopenia, Osteoporosis, and fragility fracture risk",
            "Assessment of immune resilience and recurrent respiratory tract infections",
            "Monitoring oral Vitamin D3 supplementation therapy"
        ],
        "biological_role": "Facilitates intestinal calcium and phosphorus absorption, maintains parathyroid hormone equilibrium, modulates cellular differentiation, and downregulates inflammatory cytokine cascades.",
        "preparation_guide": {
            "fasting_required": False,
            "fasting_hours": 0,
            "instructions": "No fasting required. Blood can be collected at any time of day.",
            "medication_advice": "Note your current weekly/daily Vitamin D3 dose (e.g., 60,000 IU)."
        },
        "interpretation_guide": {
            "high_levels": "Values > 100 ng/mL indicate Vitamin D toxicity (hypervitaminosis D), which can induce hypercalcemia, renal calcinosis, and nausea.",
            "low_levels": "< 20 ng/mL is Deficient (elevated fracture and rickets risk). 20-29 ng/mL is Insufficient. 30-100 ng/mL is Optimal clinical sufficiency."
        },
        "related_health_conditions": ["Vitamin D Deficiency", "Osteoporosis / Osteomalacia", "Secondary Hyperparathyroidism", "Musculoskeletal Fatigue"],
        "recommended_followups": ["Serum Calcium & Phosphorus", "Intact Parathyroid Hormone (iPTH)", "DEXA Bone Mineral Density Scan", "Vitamin B12"],
        "clinical_faqs": [
            {"q": "Why is 25-Hydroxy Vitamin D measured instead of 1,25-Dihydroxy?", "a": "25(OH)D has a long circulating half-life of 2-3 weeks, accurately reflecting total body reserves, unlike the transient active metabolite."},
            {"q": "How can I improve low Vitamin D levels?", "a": "Under physician guidance, therapeutic cholecalciferol (Vitamin D3) supplementation along with safe sunlight exposure and fortified foods is standard."}
        ]
    },
    "VITB12": {
        "overview": "Vitamin B12 (Cobalamin) is a water-soluble vitamin essential for normal neurological function, myelin sheath integrity, DNA synthesis, and red blood cell maturation in the bone marrow.",
        "why_prescribed": [
            "Investigation of tingling, numbness in hands/feet (peripheral neuropathy), and balance issues",
            "Evaluation of macrocytic anemia (elevated MCV) and unexplained cognitive fog",
            "Routine screening for strict vegetarians, vegans, elderly individuals, and bariatric patients",
            "Long-term Metformin or proton-pump inhibitor (PPI) users"
        ],
        "biological_role": "Acts as a cofactor for methionine synthase and methylmalonyl-CoA mutase, crucial for homocysteine metabolism, neurological myelination, and one-carbon metabolic transfers.",
        "preparation_guide": {
            "fasting_required": False,
            "fasting_hours": 0,
            "instructions": "8-hour fasting is preferred by some laboratories for baseline purity, but non-fasting is widely accepted.",
            "medication_advice": "Discontinue high-dose B-complex vitamin injectables or oral supplements for 48-72 hours prior to testing."
        },
        "interpretation_guide": {
            "high_levels": "Extremely high values (>1500 pg/mL) without supplementation may be observed in myeloproliferative disorders, liver disease, or renal failure.",
            "low_levels": "< 200 pg/mL indicates frank clinical deficiency causing megaloblastic anemia and progressive axonal neuropathy. 200-300 pg/mL is borderline."
        },
        "related_health_conditions": ["Pernicious Anemia", "Peripheral Neuropathy", "Megaloblastic Anemia", "Subacute Combined Degeneration of Spinal Cord"],
        "recommended_followups": ["Complete Blood Count (CBC) with MCV", "Serum Homocysteine & Methylmalonic Acid (MMA)", "Anti-Intrinsic Factor Antibodies", "Folate (Folic Acid)"],
        "clinical_faqs": [
            {"q": "Who is at highest risk for Vitamin B12 deficiency?", "a": "Vegetarians/vegans (since B12 is primarily found in animal sources), elderly adults with atrophic gastritis, and patients on prolonged antacids or Metformin."},
            {"q": "Can nerve damage from B12 deficiency be reversed?", "a": "Early treatment with therapeutic supplementation can completely reverse neuropathic symptoms; prolonged chronic deficiency can cause irreversible changes."}
        ]
    }
}


def is_groq_available() -> bool:
    """Checks if Groq API key is present and configured."""
    return bool(GROQ_API_KEY and GROQ_API_KEY.strip() not in ('', 'none', 'false', 'null'))


def _extract_groq_text(payload_json: dict) -> str:
    """Extracts raw text content from Groq OpenAI-compatible completion response."""
    if not isinstance(payload_json, dict):
        return ''
    if 'choices' in payload_json and len(payload_json['choices']) > 0:
        choice = payload_json['choices'][0]
        if isinstance(choice, dict):
            if 'message' in choice and isinstance(choice['message'], dict):
                msg = choice['message']
                content = msg.get('content')
                if content and str(content).strip():
                    return str(content)
                reasoning = msg.get('reasoning')
                if reasoning and str(reasoning).strip():
                    return str(reasoning)
            if 'text' in choice and choice['text']:
                return str(choice['text'])
    return ''


def get_groq_diagnostic_test_insight(test_code_or_name: str, test_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Invokes Groq API to retrieve structured, rich clinical insights for a diagnostic test.
    Gracefully falls back to comprehensive clinical knowledge base when API is offline.
    """
    code_upper = test_code_or_name.strip().upper()
    
    # 1. Look up test metadata from catalog if not passed
    if not test_data:
        test_data = get_test_by_code(code_upper)
        if not test_data:
            for t in MASTER_TESTS_CATALOG:
                if t['code'].upper() == code_upper or t['name'].lower() == test_code_or_name.lower():
                    test_data = t
                    break

    test_name = (test_data.get('name') or test_data.get('test_name') or test_code_or_name) if test_data else test_code_or_name
    category = test_data.get('category_name', 'Pathology & Diagnostics') if test_data else 'Pathology'
    sample_type = test_data.get('sample_type', 'Blood') if test_data else 'Blood'
    base_price = test_data.get('base_price_inr') or test_data.get('price') or 500 if test_data else 500

    # 2. Try Groq API Generation
    if is_groq_available():
        try:
            prompt = f"""
You are an expert Chief Clinical Pathologist and Medical Director at Spherix Diagnostic Network.
Provide a comprehensive, authoritative, patient-friendly, and scientifically rigorous explanation for the laboratory diagnostic test:
Test Name: {test_name} (Code: {code_upper})
Department / Category: {category}
Sample Type: {sample_type}

Return your response strictly in valid JSON format with the following exact keys:
{{
  "overview": "Clear 2-3 sentence clinical explanation of what the test is, what organ/pathway it investigates, and why it is indispensable.",
  "why_prescribed": ["List 4-5 clinical symptoms, indications, or disease states where physicians prescribe this test."],
  "biological_role": "Detailed paragraph explaining the physiological and cellular mechanisms, enzymes, hormones, or biomarkers measured.",
  "preparation_guide": {{
    "fasting_required": true/false,
    "fasting_hours": number (e.g. 0, 8, 10, 12),
    "instructions": "Specific pre-collection patient guidance (e.g. water intake, morning timing, physical activity, food restrictions).",
    "medication_advice": "Clear precautions regarding medications, vitamins, or supplements that may interfere with test accuracy."
  }},
  "interpretation_guide": {{
    "high_levels": "What high/elevated values mean, primary medical conditions associated, and potential complications.",
    "low_levels": "What low/depressed values mean, primary medical conditions associated, and potential complications."
  }},
  "side_effects_guide": {{
    "common_sensations": "Brief description of mild prick sensation during venipuncture or sample collection.",
    "rare_reactions": "Rare transient effects such as minor bruising (hematoma) or brief lightheadedness.",
    "safety_measures": "Pathology safety protocols including 100% sterile single-use vacutainers and alcohol swab disinfection.",
    "aftercare_advice": "Apply firm pressure on the puncture site for 3-5 minutes and maintain normal hydration."
  }},
  "related_health_conditions": ["List 4-6 specific medical conditions monitored or diagnosed with this test."],
  "recommended_followups": ["List 3-5 complementary diagnostic tests, imaging studies, or doctor consultations recommended for holistic evaluation."],
  "clinical_faqs": [
    {{"q": "Common patient question?", "a": "Precise, reassuring pathologist answer."}},
    {{"q": "Another common patient question?", "a": "Precise, reassuring pathologist answer."}},
    {{"q": "Third common patient question?", "a": "Precise, reassuring pathologist answer."}}
  ],
  "lifestyle_tips": ["List 3-4 proactive dietary, exercise, or lifestyle habits to maintain optimal levels for this biomarker."]
}}

Respond ONLY with the raw valid JSON object. Do not include markdown code block backticks.
"""
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            body = {
                'model': GROQ_API_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'You are the Spherix Clinical Pathology AI Engine. Output valid JSON only.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 2000
            }

            resp = requests.post(f"{GROQ_API_BASE}/chat/completions", headers=headers, json=body, timeout=12)
            if resp.status_code == 200:
                raw_text = _extract_groq_text(resp.json())
                # Clean markdown backticks if returned
                cleaned_text = re.sub(r'^```json\s*', '', raw_text.strip())
                cleaned_text = re.sub(r'^```\s*', '', cleaned_text)
                cleaned_text = re.sub(r'```$', '', cleaned_text.strip())

                parsed_json = json.loads(cleaned_text)
                parsed_json['ai_source'] = 'Groq Clinical Intelligence'
                parsed_json['test_code'] = code_upper
                parsed_json['test_name'] = test_name
                parsed_json['category'] = category
                parsed_json['sample_type'] = sample_type
                parsed_json['base_price_inr'] = base_price
                if 'side_effects_guide' not in parsed_json or not parsed_json['side_effects_guide']:
                    parsed_json['side_effects_guide'] = {
                        "common_sensations": "Brief, mild pinch during sterile needle insertion.",
                        "rare_reactions": "Minor localized hematoma or transient dizziness in sensitive individuals.",
                        "safety_measures": "Standardized ISO-certified sterile disposable single-use needles and vacutainers.",
                        "aftercare_advice": "Hold gauze firmly over the puncture site for 3-5 minutes; stay well-hydrated."
                    }
                return parsed_json

        except Exception as e:
            print(f"⚠️ Groq diagnostic AI call encountered exception: {e}. Utilizing clinical fallback.")

    # 3. Fallback to Local Knowledge Base
    if code_upper in FALLBACK_TEST_KNOWLEDGE:
        data = dict(FALLBACK_TEST_KNOWLEDGE[code_upper])
        data['ai_source'] = 'Spherix Clinical Reference Database'
        data['test_code'] = code_upper
        data['test_name'] = test_name
        data['category'] = category
        data['sample_type'] = sample_type
        data['base_price_inr'] = base_price
        return data

    # 4. Synthesize Dynamic Fallback for any other test in catalog
    desc = test_data.get('description', f'{test_name} is a standardized diagnostic investigation.') if test_data else f'{test_name} diagnostic investigation.'
    prep = test_data.get('preparation_instructions', 'Maintain normal hydration and follow standard laboratory guidelines.') if test_data else 'Standard pre-test guidelines.'
    fasting = test_data.get('fasting_required', False) if test_data else False
    fasting_hrs = test_data.get('fasting_hours', 0) if test_data else 0

    return {
        "ai_source": "Spherix Clinical Reference Database",
        "test_code": code_upper,
        "test_name": test_name,
        "category": category,
        "sample_type": sample_type,
        "base_price_inr": base_price,
        "overview": f"{test_name} is an advanced diagnostic evaluation in {category}. {desc}",
        "why_prescribed": [
            f"Screening and routine monitoring for {category.lower()} conditions",
            "Assessing physiological organ clearance and biomarker stability",
            "Evaluating unexplained clinical symptoms reported during physician consultation",
            "Monitoring patient response to targeted therapeutic regimens"
        ],
        "biological_role": f"Measures specific cellular concentrations, enzymatic activities, or hormonal titers within {sample_type.lower()} to assess organ function and cellular equilibrium.",
        "preparation_guide": {
            "fasting_required": fasting,
            "fasting_hours": fasting_hrs,
            "instructions": prep,
            "medication_advice": "Inform the phlebotomist about any daily prescribed medications or nutritional supplements before sample draw."
        },
        "side_effects_guide": {
            "common_sensations": "A brief, mild pinch during sterile needle insertion. Mild localized tenderness or small bruise (hematoma) at the puncture site may occur and typically resolves in 1-2 days.",
            "rare_reactions": "Mild, temporary dizziness or lightheadedness (vasovagal response), especially if anxious or fasting.",
            "safety_measures": "100% sterile single-use disposable vacuum needle systems and alcohol swab skin antisepsis performed by certified phlebotomists.",
            "aftercare_instructions": "Apply firm direct pressure with a sterile cotton pad for 2-3 minutes. Keep bandage on for 1 hour. Avoid heavy lifting with the sampled arm for 2 hours, and maintain good hydration."
        },
        "interpretation_guide": {
            "high_levels": f"Elevated levels in {test_name} typically indicate acute cellular release, hyperfunction, compensatory response, or reduced renal/hepatic elimination.",
            "low_levels": f"Depressed levels in {test_name} may suggest biosynthetic deficiency, increased consumption, nutritional insufficiency, or target organ hypofunction."
        },
        "related_health_conditions": [f"{category} Disorders", "Metabolic Imbalances", "Inflammatory Conditions", "Chronic Organ Strain"],
        "recommended_followups": ["Complete Blood Count (CBC)", "Metabolic Panel / LFT / KFT", "Consultation with Attending Specialist"],
        "clinical_faqs": [
            {"q": f"How long does {test_name} take to release reports?", "a": f"Standard turnaround time is {test_data.get('turnaround_hours', 12) if test_data else 12} hours from sample accessioning."},
            {"q": "Is home collection available for this test?", "a": "Yes, certified Spherix phlebotomists can collect this sample at your doorstep with cold-chain transport integrity."}
        ],
        "lifestyle_tips": [
            "Maintain balanced hydration and nutrient-dense whole foods.",
            "Engage in regular physical activity appropriate for your baseline health.",
            "Follow up periodically with your healthcare provider to review trend lines."
        ]
    }


def generate_pathologist_ai_summary(results_list: List[Dict[str, Any]], patient_meta: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Generates an automated pathologist summary and interpretation draft for released lab results.
    Leverages Groq AI when active, with high-accuracy clinical heuristics fallback.
    """
    abnormal_count = sum(1 for r in results_list if str(r.get('abnormal_flag', '')).upper() in ('HIGH', 'LOW', 'CRITICAL_HIGH', 'CRITICAL_LOW', 'POSITIVE'))
    results_summary_str = ", ".join([f"{r.get('parameter_name', 'Parameter')}: {r.get('result_value')} {r.get('unit', '')} (Ref: {r.get('reference_range', 'Normal')}, Flag: {r.get('abnormal_flag', 'NORMAL')})" for r in results_list[:15]])

    if is_groq_available() and results_list:
        try:
            prompt = f"""
You are a Board-Certified Senior Clinical Pathologist signing off a laboratory report at Spherix Diagnostic Network.
Review the following patient laboratory observations and draft a concise, professional Pathologist Impression and Clinical Recommendation:

Patient Info: Age {patient_meta.get('age', 'Adult') if patient_meta else 'Adult'}, Gender {patient_meta.get('gender', 'Unspecified') if patient_meta else 'Unspecified'}
Observations:
{results_summary_str}

Return ONLY valid JSON with two fields:
{{
  "summary": "2-3 sentences summarizing key findings, highlighting abnormal flags if any.",
  "interpretation": "1-2 sentences with clinical interpretation and physician correlation guidance."
}}
"""
            headers = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
            body = {
                'model': GROQ_API_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'You are a board-certified Pathologist. Return JSON only.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.1,
                'max_tokens': 600
            }
            resp = requests.post(f"{GROQ_API_BASE}/chat/completions", headers=headers, json=body, timeout=10)
            if resp.status_code == 200:
                raw_text = _extract_groq_text(resp.json())
                cleaned = re.sub(r'^```json\s*', '', raw_text.strip())
                cleaned = re.sub(r'^```\s*', '', cleaned)
                cleaned = re.sub(r'```$', '', cleaned.strip())
                return json.loads(cleaned)
        except Exception as e:
            print(f"⚠️ Groq pathologist AI summary error: {e}")

    # Fallback heuristic summary
    if abnormal_count == 0:
        return {
            "summary": "All evaluated biological parameters are within standard reference intervals. Normal hematological and biochemical profiles observed.",
            "interpretation": "No significant pathological abnormalities detected. Clinical correlation and periodic preventive screening recommended."
        }
    else:
        abnormal_names = [r.get('parameter_name', 'Parameter') for r in results_list if str(r.get('abnormal_flag', '')).upper() in ('HIGH', 'LOW', 'CRITICAL_HIGH', 'CRITICAL_LOW', 'POSITIVE')]
        return {
            "summary": f"Notable variation observed in {len(abnormal_names)} parameter(s): {', '.join(abnormal_names[:3])}. Remaining parameters are within normal physiological bounds.",
            "interpretation": "Findings warrant clinical correlation with patient symptoms and medication history. Follow-up consultation with the treating physician is advised."
        }
