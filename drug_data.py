# Expanded Clinical Drug Database with Multi-Drug & Food Interaction Matrix

DRUG_DATABASE = {
    "Aspirin (Acetylsalicylic Acid)": {
        "category": "Antiplatelet / NSAID",
        "description": "Aspirin is used to reduce pain, fever, or inflammation and as a blood thinner to prevent heart attacks, clot-related strokes, and transient ischemic attacks.",
        "primary_use": "Cardiovascular prevention, antiplatelet, pain & inflammation.",
        "common_side_effects": ["Stomach irritation", "Heartburn", "Easy bruising", "Nausea"],
        "caution": "Avoid in patients with active peptic ulcers, bleeding disorders, or children with viral infections (Reye syndrome risk).",
        "food_interactions": [
            {"food": "Alcohol", "risk": "High", "details": "Significantly increases gastrointestinal bleeding and ulceration risks."},
            {"food": "Ginkgo Biloba & Garlic Supplements", "risk": "Moderate", "details": "May enhance antiplatelet effect, raising bleeding propensity."}
        ]
    },
    "Warfarin (Coumadin)": {
        "category": "Anticoagulant",
        "description": "Vitamin K antagonist blood thinner used to treat and prevent blood clots in veins, arteries, lungs, and heart.",
        "primary_use": "Thromboembolism, Atrial Fibrillation, Deep Vein Thrombosis (DVT), Pulmonary Embolism.",
        "common_side_effects": ["Bleeding gums", "Prolonged bleeding from cuts", "Easy bruising"],
        "caution": "Requires regular INR blood monitoring. Highly sensitive to diet and concomitant medications.",
        "food_interactions": [
            {"food": "Green Leafy Vegetables (Spinach, Kale, Broccoli)", "risk": "High", "details": "Rich in Vitamin K; inconsistent intake can counteract Warfarin and cause clotting."},
            {"food": "Cranberry Juice", "risk": "Moderate", "details": "May inhibit Warfarin metabolism, causing dangerously elevated INR and bleeding."},
            {"food": "Alcohol", "risk": "High", "details": "Acute alcohol intake increases bleeding risk; chronic use impairs metabolism."}
        ]
    },
    "Clopidogrel (Plavix)": {
        "category": "Antiplatelet",
        "description": "Platelet aggregation inhibitor used to prevent atherothrombotic events in patients with acute coronary syndrome, stroke, or peripheral artery disease.",
        "primary_use": "Post-stent coronary care, secondary stroke prevention, myocardial infarction.",
        "common_side_effects": ["Bleeding", "Purpura", "Rash", "Diarrhea"],
        "caution": "Avoid combining with omeprazole or other CYP2C19 inhibitors which reduce active metabolite conversion.",
        "food_interactions": [
            {"food": "Grapefruit Juice", "risk": "Moderate", "details": "May slightly reduce antiplatelet efficacy via CYP3A4 modulation."},
            {"food": "High-dose Vitamin E", "risk": "Moderate", "details": "Amplifies bleeding risks."}
        ]
    },
    "Atorvastatin (Lipitor)": {
        "category": "HMG-CoA Reductase Inhibitor (Statin)",
        "description": "Cholesterol-lowering agent that lowers low-density lipoprotein (LDL) cholesterol and triglycerides while raising HDL.",
        "primary_use": "Hypercholesterolemia, dyslipidemia, primary and secondary cardiovascular risk reduction.",
        "common_side_effects": ["Myalgia (muscle ache)", "Joint pain", "Mild elevation in liver enzymes", "Nausea"],
        "caution": "Monitor for unexplained muscle pain, tenderness, or weakness (rhabdomyolysis warning).",
        "food_interactions": [
            {"food": "Grapefruit & Grapefruit Juice", "risk": "High", "details": "Inhibits CYP3A4 intestinal enzyme, causing statin accumulation, severe myopathy, and liver toxicity."},
            {"food": "Red Yeast Rice", "risk": "High", "details": "Contains natural monacolin K; combining leads to statin overdose toxicity."}
        ]
    },
    "Metformin (Glucophage)": {
        "category": "Biguanide (Antidiabetic)",
        "description": "First-line oral antidiabetic medicine that reduces hepatic glucose production and improves peripheral insulin sensitivity.",
        "primary_use": "Type 2 Diabetes Mellitus, Prediabetes, PCOS.",
        "common_side_effects": ["Diarrhea", "Abdominal discomfort", "Nausea", "Metallic taste", "Vitamin B12 deficiency"],
        "caution": "Withhold before iodinated contrast procedures. Monitor renal function eGFR for lactic acidosis prevention.",
        "food_interactions": [
            {"food": "Alcohol", "risk": "High", "details": "Significantly increases the risk of life-threatening Lactic Acidosis and hypoglycemia."},
            {"food": "High-Fiber Meals", "risk": "Low", "details": "Large amounts of soluble fiber may slightly delay Metformin absorption; take with meals."}
        ]
    },
    "Lisinopril (Prinivil, Zestril)": {
        "category": "ACE Inhibitor",
        "description": "Angiotensin-converting enzyme inhibitor that relaxes blood vessels, decreasing blood pressure and cardiac workload.",
        "primary_use": "Hypertension, Heart Failure with reduced ejection fraction, Post-MI cardioprotection.",
        "common_side_effects": ["Persistent dry tickly cough", "Dizziness", "Hyperkalemia", "Headache"],
        "caution": "Absolute contraindication in pregnancy (teratogenic). Watch for angioedema (swelling of lips/throat).",
        "food_interactions": [
            {"food": "Potassium-Rich Foods (Bananas, Potatoes, Salt Substitutes)", "risk": "High", "details": "Potassium retention can cause dangerous hyperkalemia and cardiac arrhythmias."}
        ]
    },
    "Amlodipine (Norvasc)": {
        "category": "Calcium Channel Blocker",
        "description": "Dihydropyridine calcium antagonist that causes peripheral and coronary vasodilation to lower blood pressure.",
        "primary_use": "Hypertension, Chronic Stable Angina, Vasospastic Angina.",
        "common_side_effects": ["Peripheral ankle edema", "Flushing", "Dizziness", "Fatigue"],
        "caution": "Use with caution in severe aortic stenosis or severe hepatic impairment.",
        "food_interactions": [
            {"food": "Grapefruit Juice", "risk": "Moderate", "details": "Increases systemic bioavailability and hypotensive peaks."}
        ]
    },
    "Metoprolol (Lopressor, Toprol XL)": {
        "category": "Beta-1 Selective Blocker",
        "description": "Cardioselective beta-blocker that reduces heart rate, blood pressure, and myocardial oxygen demand.",
        "primary_use": "Hypertension, Angina Pectoris, Heart Failure, Post-Myocardial Infarction, Arrhythmias.",
        "common_side_effects": ["Bradycardia (slow heart rate)", "Fatigue", "Cold extremities", "Dizziness"],
        "caution": "Do not abruptly discontinue (rebound hypertension risk). Caution in severe asthma or bradycardia.",
        "food_interactions": [
            {"food": "High-Protein Meals", "risk": "Low", "details": "Can slightly increase Metoprolol bioavailability; take consistently with meals."},
            {"food": "Alcohol", "risk": "Moderate", "details": "Additive hypotensive and sedating effects."}
        ]
    },
    "Omeprazole (Prilosec)": {
        "category": "Proton Pump Inhibitor (PPI)",
        "description": "Suppresses gastric acid secretion by inhibiting the H+/K+ ATPase enzyme system in gastric parietal cells.",
        "primary_use": "GERD, Peptic Ulcer Disease, H. pylori eradication, Zollinger-Ellison Syndrome.",
        "common_side_effects": ["Headache", "Abdominal pain", "Nausea", "Hypomagnesemia with prolonged use"],
        "caution": "Long-term use may reduce absorption of Vitamin B12, Calcium, and Iron.",
        "food_interactions": [
            {"food": "Food Timing", "risk": "Low", "details": "Best taken 30-60 minutes before breakfast for optimal acid suppression."}
        ]
    },
    "Ibuprofen (Advil, Motrin)": {
        "category": "NSAID",
        "description": "Nonsteroidal anti-inflammatory drug that inhibits COX-1 and COX-2 enzymes to reduce prostaglandins.",
        "primary_use": "Mild to moderate pain, fever, inflammation, arthritis.",
        "common_side_effects": ["Stomach upset", "Nausea", "Fluid retention", "Elevated blood pressure"],
        "caution": "Avoid in active GI bleeding, chronic kidney disease, and severe heart failure.",
        "food_interactions": [
            {"food": "Alcohol", "risk": "High", "details": "Multiplies gastric ulceration and gastrointestinal hemorrhage hazards."}
        ]
    },
    "Acetaminophen / Paracetamol (Tylenol)": {
        "category": "Analgesic / Antipyretic",
        "description": "Centrally acting pain reliever and fever reducer without peripheral anti-inflammatory effects.",
        "primary_use": "Headache, musculoskeletal pain, osteoarthritis, fever.",
        "common_side_effects": ["Generally well-tolerated at therapeutic doses (<4000mg/day)."],
        "caution": "Hepatotoxicity risk in overdose or severe chronic liver disease.",
        "food_interactions": [
            {"food": "Alcohol (Chronic or Binge)", "risk": "High", "details": "Depletes hepatic glutathione, inducing toxic NAPQI accumulation and acute liver necrosis."}
        ]
    },
    "Ciprofloxacin (Cipro)": {
        "category": "Fluoroquinolone Antibiotic",
        "description": "Broad-spectrum bactericidal antibiotic inhibiting bacterial DNA gyrase and topoisomerase IV.",
        "primary_use": "Urinary tract infections, infectious diarrhea, respiratory and intra-abdominal infections.",
        "common_side_effects": ["Nausea", "Diarrhea", "Headache", "Tendinopathy / tendon rupture risk", "QT prolongation"],
        "caution": "Black box warning for tendonitis and tendon rupture. Avoid in myasthenia gravis.",
        "food_interactions": [
            {"food": "Dairy Products (Milk, Yogurt, Cheese) & Calcium Fortified Juices", "risk": "High", "details": "Calcium chelates Ciprofloxacin in the gut, reducing antibiotic absorption by up to 70%. Take 2h before or 6h after dairy."},
            {"food": "Caffeine (Coffee, Energy Drinks)", "risk": "Moderate", "details": "Ciprofloxacin inhibits caffeine clearance, triggering tremors, tachycardia, and anxiety."}
        ]
    },
    "Levothyroxine (Synthroid)": {
        "category": "Thyroid Hormone",
        "description": "Synthetic T4 replacement hormone used to restore normal thyroid hormone concentrations in hypothyroidism.",
        "primary_use": "Primary, secondary, and tertiary hypothyroidism, goiter suppression, thyroid cancer.",
        "common_side_effects": ["Palpitations", "Weight loss", "Heat intolerance", "Insomnia (if dose excessive)"],
        "caution": "Narrow therapeutic index; take on an empty stomach with a full glass of water.",
        "food_interactions": [
            {"food": "Coffee & Espresso", "risk": "High", "details": "Significantly blocks intestinal absorption; wait at least 45-60 minutes after taking before drinking coffee."},
            {"food": "Soy Products & High Fiber", "risk": "Moderate", "details": "Reduces bioavailability; maintain consistent dietary patterns."},
            {"food": "Calcium & Iron Supplements", "risk": "High", "details": "Forms insoluble complexes; separate by at least 4 hours."}
        ]
    },
    "Sertraline (Zoloft)": {
        "category": "SSRI Antidepressant",
        "description": "Selective serotonin reuptake inhibitor that increases synaptic serotonin levels in the central nervous system.",
        "primary_use": "Major Depressive Disorder, Generalized Anxiety Disorder, OCD, PTSD, Panic Disorder.",
        "common_side_effects": ["Nausea", "Insomnia", "Drowsiness", "Dry mouth", "Sexual dysfunction"],
        "caution": "Black box warning for suicidal thoughts in young adults. Risk of Serotonin Syndrome when combined with other serotonergic agents.",
        "food_interactions": [
            {"food": "Alcohol", "risk": "High", "details": "Worsens depression and impairs motor skills."},
            {"food": "Grapefruit Juice", "risk": "Moderate", "details": "May modestly increase serum sertraline levels."}
        ]
    },
    "Spironolactone (Aldactone)": {
        "category": "Potassium-Sparing Diuretic / Aldosterone Antagonist",
        "description": "Aldosterone antagonist that increases sodium and water excretion while conserving potassium ions.",
        "primary_use": "Heart failure with reduced ejection fraction, resistant hypertension, ascites in cirrhosis.",
        "common_side_effects": ["Hyperkalemia", "Gynecomastia", "Dizziness", "Dehydration"],
        "caution": "Monitor serum potassium and renal function closely.",
        "food_interactions": [
            {"food": "High-Potassium Foods & Salt Substitutes (Potassium Chloride)", "risk": "High", "details": "Severe hyperkalemia risk leading to cardiac arrest."}
        ]
    }
}

# Known Critical Drug-Drug Interaction Pairs Matrix
KNOWN_INTERACTIONS = [
    {
        "drug1": "Warfarin (Coumadin)",
        "drug2": "Aspirin (Acetylsalicylic Acid)",
        "severity": "Severe / Contraindicated",
        "severity_level": "severe",
        "mechanism": "Synergistic anticoagulant and antiplatelet effects with gastric mucosal injury.",
        "risk_description": "Massively increased risk of major gastrointestinal and intracerebral hemorrhages.",
        "clinical_guidance": "Avoid combination unless strictly indicated for mechanical heart valves under specialist monitoring. Consider gastroprotection with PPI."
    },
    {
        "drug1": "Warfarin (Coumadin)",
        "drug2": "Ibuprofen (Advil, Motrin)",
        "severity": "Severe / Contraindicated",
        "severity_level": "severe",
        "mechanism": "NSAID causes gastric ulceration and impairs platelet aggregation while Warfarin prevents coagulation.",
        "risk_description": "Severe gastrointestinal bleeding, ulcer perforation, and prolonged prothrombin time.",
        "clinical_guidance": "Contraindicated. Use Acetaminophen for pain relief under safe dosing thresholds."
    },
    {
        "drug1": "Clopidogrel (Plavix)",
        "drug2": "Omeprazole (Prilosec)",
        "severity": "Major / Caution",
        "severity_level": "major",
        "mechanism": "Omeprazole competitively inhibits CYP2C19, blocking Clopidogrel conversion to its active antiplatelet form.",
        "risk_description": "Loss of antiplatelet protection leading to recurrent stent thrombosis and myocardial infarction.",
        "clinical_guidance": "Switch to Pantoprazole or H2-blocker (Famotidine) which exhibit minimal CYP2C19 inhibition."
    },
    {
        "drug1": "Lisinopril (Prinivil, Zestril)",
        "drug2": "Spironolactone (Aldactone)",
        "severity": "Major / Monitoring Required",
        "severity_level": "major",
        "mechanism": "Both agents decrease aldosterone production and potassium excretion in the distal renal tubules.",
        "risk_description": "Severe life-threatening Hyperkalemia (>5.5 mmol/L), cardiac conduction delays, and asystole.",
        "clinical_guidance": "Frequent serum potassium and creatinine monitoring within 1 week of initiation and dose changes."
    },
    {
        "drug1": "Lisinopril (Prinivil, Zestril)",
        "drug2": "Ibuprofen (Advil, Motrin)",
        "severity": "Moderate",
        "severity_level": "moderate",
        "mechanism": "NSAIDs inhibit renal prostaglandins, causing afferent arteriolar constriction while ACE inhibitors dilate efferent arterioles.",
        "risk_description": "Acute drop in glomerular filtration rate (Acute Kidney Injury) and blunted antihypertensive response.",
        "clinical_guidance": "Avoid chronic NSAIDs in hypertensive/renal patients. Use topical analgesics or acetaminophen."
    },
    {
        "drug1": "Atorvastatin (Lipitor)",
        "drug2": "Ciprofloxacin (Cipro)",
        "severity": "Moderate",
        "severity_level": "moderate",
        "mechanism": "CYP3A4 and OATP1B1 inhibition increasing statin systemic exposure.",
        "risk_description": "Elevated risk of myopathy, muscle breakdown, and elevated transaminases.",
        "clinical_guidance": "Monitor for muscle pain; temporarily reduce statin dose if long course antibiotic required."
    },
    {
        "drug1": "Sertraline (Zoloft)",
        "drug2": "Aspirin (Acetylsalicylic Acid)",
        "severity": "Moderate",
        "severity_level": "moderate",
        "mechanism": "SSRIs deplete platelet serotonin storage, impairing primary hemostasis.",
        "risk_description": "Elevated upper gastrointestinal bleeding risk.",
        "clinical_guidance": "Add PPI gastroprotection in elderly or ulcer-history patients."
    }
]

# =========================================================================
# PILL & CAPSULE PHYSICAL CHARACTERISTICS & USAGE GUIDE DATABASE
# =========================================================================
PILL_CHARACTERISTICS_DATABASE = [
    {
        "id": "PILL-DOLO-650",
        "brand_name": "Dolo 650",
        "generic_name": "Paracetamol (Acetaminophen)",
        "strength": "650 mg",
        "form_type": "Tablet",
        "color": "White",
        "color_hex": "#ffffff",
        "secondary_color_hex": None,
        "shape": "Oval / Oblong",
        "imprint": "DOLO 650",
        "score": "Single Score Line",
        "coating": "Uncoated",
        "primary_use": "Fever reduction, headache, body pain, post-vaccine pyrexia, osteoarthritis discomfort.",
        "drug_class": "Analgesic & Antipyretic",
        "how_to_use": {
            "administration": "Take orally with a full glass of water. Can be taken with or without food; take with food or milk if mild stomach upset occurs.",
            "timing": "Every 4 to 6 hours as needed. Do NOT exceed 4,000 mg (maximum 6 tablets of 650mg) in a 24-hour period.",
            "what_to_avoid": "Strictly avoid Alcohol (combining increases severe acute liver toxicity/hepatotoxicity risk). Avoid concurrent OTC cold & cough syrups containing acetaminophen to prevent accidental overdose.",
            "missed_dose": "Take as soon as remembered if pain/fever persists. Skip if almost time for the next scheduled dose. Never take two doses together.",
            "overdose_warning": "Early symptoms include nausea, vomiting, loss of appetite, sweating, and abdominal pain. Seek immediate emergency medical care (antidote: N-acetylcysteine / NAC within 8 hours).",
            "storage": "Store below 25°C in a dry place away from direct heat and moisture.",
            "special_precautions": "Caution in chronic alcoholics, G6PD deficiency, or severe liver/kidney disease."
        }
    },
    {
        "id": "PILL-AUG-625",
        "brand_name": "Augmentin 625 Duo",
        "generic_name": "Amoxicillin + Potassium Clavulanate",
        "strength": "500 mg + 125 mg",
        "form_type": "Film-coated Tablet",
        "color": "White",
        "color_hex": "#f8fafc",
        "secondary_color_hex": None,
        "shape": "Oval / Oblong",
        "imprint": "AC 625",
        "score": "Unscored",
        "coating": "Film-coated",
        "primary_use": "Bacterial respiratory tract infections, sinusitis, otitis media, skin & urinary tract infections.",
        "drug_class": "Penicillin Antibiotic with Beta-Lactamase Inhibitor",
        "how_to_use": {
            "administration": "Take at the start of a meal or with a light snack to maximize clavulanate absorption and minimize gastrointestinal distress.",
            "timing": "Twice daily (every 12 hours) at evenly spaced intervals. Complete the full prescribed course even if symptoms resolve earlier.",
            "what_to_avoid": "Avoid taking with high-fat meals. Avoid alcohol while taking antibiotics. Space probiotic supplements by at least 2 hours.",
            "missed_dose": "Take as soon as you remember. If it is almost time for your next dose, skip the missed dose and resume normal schedule.",
            "overdose_warning": "Nausea, vomiting, diarrhea, crystalluria (crystals in urine). Maintain heavy fluid hydration and seek medical assistance.",
            "storage": "Store in moisture-resistant original blister pack below 25°C.",
            "special_precautions": "Contraindicated in patients with severe penicillin allergy or history of amoxicillin-associated cholestatic jaundice."
        }
    },
    {
        "id": "PILL-LIP-20",
        "brand_name": "Lipitor 20mg (Atorva)",
        "generic_name": "Atorvastatin Calcium",
        "strength": "20 mg",
        "form_type": "Film-coated Tablet",
        "color": "White",
        "color_hex": "#ffffff",
        "secondary_color_hex": None,
        "shape": "Oval / Oblong",
        "imprint": "PD 156 / 20",
        "score": "Unscored",
        "coating": "Film-coated",
        "primary_use": "Lowering bad LDL cholesterol, triglycerides and preventing cardiovascular events/strokes.",
        "drug_class": "HMG-CoA Reductase Inhibitor (Statin)",
        "how_to_use": {
            "administration": "Swallow whole with water. Can be taken with or without food at any time of day, though evening/bedtime is standard.",
            "timing": "Once daily, preferably at the same time each evening when cholesterol synthesis peaks.",
            "what_to_avoid": "Strictly avoid Grapefruit and Grapefruit Juice (potently inhibits CYP3A4, causing statin accumulation and rhabdomyolysis). Limit alcohol consumption.",
            "missed_dose": "If more than 12 hours have passed since the missed dose, skip it and take your next dose at normal time. Do not take a double dose.",
            "overdose_warning": "Severe muscle breakdown, dark tea-colored urine, extreme weakness. Seek emergency medical care immediately.",
            "storage": "Store at 20°C to 25°C away from humidity.",
            "special_precautions": "Absolute contraindication in pregnancy (Category X) and active liver disease. Report any unexplained muscle soreness."
        }
    },
    {
        "id": "PILL-PAN-40",
        "brand_name": "Pan 40 (Pantocid)",
        "generic_name": "Pantoprazole Sodium",
        "strength": "40 mg",
        "form_type": "Enteric-Coated Tablet",
        "color": "Yellow",
        "color_hex": "#facc15",
        "secondary_color_hex": None,
        "shape": "Oval / Oblong",
        "imprint": "PAN 40",
        "score": "Unscored",
        "coating": "Enteric-Coated",
        "primary_use": "Acid reflux (GERD), heartburn, gastric ulcers, Zollinger-Ellison syndrome, gastroprotection with NSAIDs.",
        "drug_class": "Proton Pump Inhibitor (PPI)",
        "how_to_use": {
            "administration": "Swallow WHOLE with water. DO NOT chew, crush, or split the tablet; the enteric coating protects the active ingredient from stomach acid.",
            "timing": "Take once daily in the morning, 30 to 60 minutes BEFORE your first meal (breakfast).",
            "what_to_avoid": "Avoid spicy, acidic, citrus, caffeinated foods and late-night heavy meals that trigger acid hypersecretion.",
            "missed_dose": "Take as soon as you remember before your next meal. If it is already dinner time, take 30 min before dinner.",
            "overdose_warning": "Somnolence, dizziness, flushing, nausea. Generally well tolerated; seek medical advice if large quantity consumed.",
            "storage": "Store protected from moisture and light below 25°C.",
            "special_precautions": "Prolonged use (>1 year) may decrease magnesium, vitamin B12, and bone mineral density."
        }
    },
    {
        "id": "PILL-MET-500",
        "brand_name": "Glucophage 500 (Glycomet)",
        "generic_name": "Metformin Hydrochloride",
        "strength": "500 mg",
        "form_type": "Tablet",
        "color": "White",
        "color_hex": "#f1f5f9",
        "secondary_color_hex": None,
        "shape": "Round",
        "imprint": "M 500 / BMS",
        "score": "Single Score Line",
        "coating": "Film-coated",
        "primary_use": "First-line management of Type 2 Diabetes Mellitus, insulin resistance, PCOS.",
        "drug_class": "Biguanide Antidiabetic",
        "how_to_use": {
            "administration": "Take with meals (during or immediately after breakfast/dinner) to reduce gastrointestinal side effects like nausea and diarrhea.",
            "timing": "1 to 2 times daily as prescribed with morning and evening meals.",
            "what_to_avoid": "Avoid excessive alcohol intake (potentiates risk of life-threatening Lactic Acidosis). Withhold for 48 hours before and after CT scans using iodinated contrast dye.",
            "missed_dose": "Take with your next meal. Do not take an extra dose to make up for a forgotten dose.",
            "overdose_warning": "Lactic acidosis (deep rapid breathing, muscle cramping, severe fatigue, hypothermia, low BP). Urgent emergency ER admission required.",
            "storage": "Store at room temperature 15°C - 30°C in a tightly closed container.",
            "special_precautions": "Requires routine monitoring of kidney function (eGFR) and serum Vitamin B12 levels."
        }
    },
    {
        "id": "PILL-AMOX-500",
        "brand_name": "Amoxil 500 (Mox 500)",
        "generic_name": "Amoxicillin Trihydrate",
        "strength": "500 mg",
        "form_type": "Hard Gelatin Capsule",
        "color": "Two-Tone (Maroon / Pink)",
        "color_hex": "#881337",
        "secondary_color_hex": "#f472b6",
        "shape": "Capsule",
        "imprint": "AMOX 500 / GS",
        "score": "Unscored",
        "coating": "Gelatin Shell",
        "primary_use": "Bacterial throat infections, streptococcal pharyngitis, dental abscesses, skin infections.",
        "drug_class": "Aminopenicillin Antibiotic",
        "how_to_use": {
            "administration": "Swallow capsule whole with a full glass of water. Can be taken with or without food.",
            "timing": "Every 8 hours (three times daily) or every 12 hours as prescribed. Maintain consistent timing for constant therapeutic blood levels.",
            "what_to_avoid": "Do not skip doses. Avoid taking expired tetracyclines or mixing with oral contraceptives without barrier backup.",
            "missed_dose": "Take as soon as possible. If it is within 2 hours of next dose, skip and proceed normally.",
            "overdose_warning": "Severe gastrointestinal upset, oliguria, interstitial nephritis. Seek immediate medical support.",
            "storage": "Store capsules in a tightly closed container below 20°C in a dry environment.",
            "special_precautions": "Contraindicated in infectious mononucleosis (causes generalized erythematous rash) and penicillin allergy."
        }
    },
    {
        "id": "PILL-OMEP-20",
        "brand_name": "Prilosec 20 (Omez)",
        "generic_name": "Omeprazole",
        "strength": "20 mg",
        "form_type": "Hard Gelatin Capsule",
        "color": "Two-Tone (Pink / Brown)",
        "color_hex": "#f472b6",
        "secondary_color_hex": "#78350f",
        "shape": "Capsule",
        "imprint": "OMEZ 20 / DR REDDY",
        "score": "Unscored",
        "coating": "Pellets inside capsule",
        "primary_use": "Duodenal ulcers, gastric hyperacidity, Barrett esophagus, erosive esophagitis.",
        "drug_class": "Proton Pump Inhibitor",
        "how_to_use": {
            "administration": "Swallow capsule whole with water. If swallowing difficulty exists, capsule can be opened and enteric pellets sprinkled on 1 tbsp of applesauce (swallow immediately without chewing).",
            "timing": "Take first thing in the morning 30-60 minutes before breakfast.",
            "what_to_avoid": "Do NOT crush or chew the small inner enteric-coated pellets. Avoid concomitant Clopidogrel (Plavix).",
            "missed_dose": "Take as soon as remembered before your next meal. Do not take double capsules.",
            "overdose_warning": "Blurred vision, confusion, diaphoresis, tachycardia, dry mouth.",
            "storage": "Keep in original protective blister away from light and moisture.",
            "special_precautions": "May interact with Digoxin, Methotrexate, and antifungal azoles (Ketoconazole)."
        }
    },
    {
        "id": "PILL-ADV-200",
        "brand_name": "Advil 200 (Brufen)",
        "generic_name": "Ibuprofen",
        "strength": "200 mg",
        "form_type": "Softgel / Coated Tablet",
        "color": "Brown / Orange",
        "color_hex": "#c2410c",
        "secondary_color_hex": None,
        "shape": "Round / Oval",
        "imprint": "Advil / I-2",
        "score": "Unscored",
        "coating": "Sugar-coated",
        "primary_use": "Relief of inflammatory pain, arthritis, menstrual cramps, toothache, muscular sprains.",
        "drug_class": "Non-Steroidal Anti-Inflammatory Drug (NSAID)",
        "how_to_use": {
            "administration": "ALWAYS take with food, milk, or immediately after a substantial meal to shield the gastric lining.",
            "timing": "1 to 2 tablets every 4 to 6 hours as needed. Do NOT exceed 1,200 mg OTC or 2,400 mg prescription daily.",
            "what_to_avoid": "Avoid Alcohol (multiplies stomach bleeding risk). Avoid combining with Aspirin, Warfarin, or other NSAIDs (Naproxen).",
            "missed_dose": "Take as soon as remembered if pain is present. Skip if close to next scheduled dose.",
            "overdose_warning": "GI bleeding (black tarry stools, vomiting blood), tinnitus (ringing in ears), acute renal failure, respiratory depression.",
            "storage": "Store at 20°C to 25°C away from excessive heat.",
            "special_precautions": "Contraindicated in 3rd trimester of pregnancy (premature closure of ductus arteriosus), heart failure, and active peptic ulcer."
        }
    },
    {
        "id": "PILL-AML-5",
        "brand_name": "Norvasc 5mg (Amlong)",
        "generic_name": "Amlodipine Besylate",
        "strength": "5 mg",
        "form_type": "Tablet",
        "color": "White",
        "color_hex": "#ffffff",
        "secondary_color_hex": None,
        "shape": "Diamond / Octagonal",
        "imprint": "AML 5 / Pfizer",
        "score": "Single Score Line",
        "coating": "Uncoated",
        "primary_use": "High blood pressure (Hypertension), chronic stable angina, coronary vasospasm.",
        "drug_class": "Dihydropyridine Calcium Channel Blocker",
        "how_to_use": {
            "administration": "Swallow with a glass of water, with or without food. Maintain regular daily compliance.",
            "timing": "Once daily at the same time each morning or evening.",
            "what_to_avoid": "Avoid Grapefruit Juice in large quantities. Avoid sudden standing up from sitting/lying position to prevent postural dizziness.",
            "missed_dose": "Take as soon as you remember. If it has been more than 12 hours since scheduled time, skip and take next dose at regular time.",
            "overdose_warning": "Severe peripheral vasodilation with marked hypotension, reflex tachycardia, and shock. Seek immediate ER assistance.",
            "storage": "Store below 30°C in a dry location.",
            "special_precautions": "Commonly causes benign ankle swelling (peripheral edema). Report severe dizziness or palpitations."
        }
    },
    {
        "id": "PILL-LIS-10",
        "brand_name": "Zestril 10 (Lipril)",
        "generic_name": "Lisinopril",
        "strength": "10 mg",
        "form_type": "Tablet",
        "color": "Pink",
        "color_hex": "#f472b6",
        "secondary_color_hex": None,
        "shape": "Round",
        "imprint": "10 / LIS",
        "score": "Single Score Line",
        "coating": "Uncoated",
        "primary_use": "Hypertension, post-heart attack cardiac protection, congestive heart failure, diabetic nephropathy.",
        "drug_class": "Angiotensin Converting Enzyme (ACE) Inhibitor",
        "how_to_use": {
            "administration": "Take with a full glass of water, with or without meals.",
            "timing": "Once daily at the same time every day.",
            "what_to_avoid": "Strictly avoid Potassium Supplements and Salt Substitutes containing potassium chloride (causes dangerous hyperkalemia). Avoid NSAID painkillers like Ibuprofen.",
            "missed_dose": "Take as soon as you remember. Skip if it is close to your next scheduled dose.",
            "overdose_warning": "Severe low blood pressure, stupor, circulatory shock, hyperkalemia.",
            "storage": "Store at controlled room temperature 15°C to 30°C.",
            "special_precautions": "Absolute contraindication in pregnancy (fetal death risk). If facial/lip/tongue swelling occurs (angioedema), call emergency immediately."
        }
    },
    {
        "id": "PILL-WAR-5",
        "brand_name": "Coumadin 5mg (Warf 5)",
        "generic_name": "Warfarin Sodium",
        "strength": "5 mg",
        "form_type": "Tablet",
        "color": "Peach / Pink",
        "color_hex": "#fb923c",
        "secondary_color_hex": None,
        "shape": "Round",
        "imprint": "COUMADIN 5 / BMS",
        "score": "Single Score Line",
        "coating": "Uncoated",
        "primary_use": "Prevention and treatment of venous thrombosis, pulmonary embolism, stroke prevention in atrial fibrillation and mechanical heart valves.",
        "drug_class": "Vitamin K Antagonist Anticoagulant",
        "how_to_use": {
            "administration": "Take orally with water at the exact same time every day, preferably in the evening.",
            "timing": "Once daily in the evening (allows same-day INR blood test dosage adjustments by doctor).",
            "what_to_avoid": "Keep dietary Vitamin K consistent (spinach, kale, broccoli, brussels sprouts). Avoid Cranberry Juice, Ginkgo Biloba, and alcohol.",
            "missed_dose": "Take as soon as possible on the same day. Do NOT take a double dose the next day. Note the missed dose on your INR logbook.",
            "overdose_warning": "Uncontrolled bleeding, blood in urine/stool, extensive bruising, sudden severe headache. Antidote: Vitamin K1 (Phytonadione).",
            "storage": "Store protected from light and moisture at 15°C - 30°C.",
            "special_precautions": "Requires strict regular INR blood test monitoring (target typically 2.0 - 3.0 or 2.5 - 3.5 for mechanical valves)."
        }
    },
    {
        "id": "PILL-AZI-500",
        "brand_name": "Zithromax 500 (Azithral)",
        "generic_name": "Azithromycin Dihydrate",
        "strength": "500 mg",
        "form_type": "Film-coated Tablet",
        "color": "White / Light Blue",
        "color_hex": "#e0f2fe",
        "secondary_color_hex": None,
        "shape": "Oval / Oblong",
        "imprint": "AZ 500 / PFIZER",
        "score": "Unscored",
        "coating": "Film-coated",
        "primary_use": "Community-acquired pneumonia, acute bacterial sinusitis, strep throat, chlamydia, traveler's diarrhea.",
        "drug_class": "Macrolide Antibiotic (Azalide)",
        "how_to_use": {
            "administration": "Take with a full glass of water. Can be taken with food to reduce stomach cramps or nausea.",
            "timing": "Once daily for 3 to 5 days as prescribed. Complete the entire course.",
            "what_to_avoid": "Do NOT take antacids containing Aluminum or Magnesium within 2 hours of Azithromycin (reduces peak absorption).",
            "missed_dose": "Take the missed dose as soon as remembered, then continue your normal schedule.",
            "overdose_warning": "Severe diarrhea, hearing loss, nausea, vomiting. Contact hospital or poison control.",
            "storage": "Store below 30°C in original packaging.",
            "special_precautions": "Caution in patients with prolonged QT interval, bradycardia, or low potassium/magnesium levels."
        }
    },
    {
        "id": "PILL-THY-50",
        "brand_name": "Synthroid 50mcg (Eltroxin)",
        "generic_name": "Levothyroxine Sodium",
        "strength": "50 mcg (0.05 mg)",
        "form_type": "Tablet",
        "color": "White",
        "color_hex": "#ffffff",
        "secondary_color_hex": None,
        "shape": "Round",
        "imprint": "SYNTHROID 50 / CAP",
        "score": "Unscored",
        "coating": "Uncoated",
        "primary_use": "Hypothyroidism (underactive thyroid hormone replacement), goiter suppression.",
        "drug_class": "Synthetic Thyroid Hormone (T4)",
        "how_to_use": {
            "administration": "Take with a full glass of plain water ONLY. Take on an EMPTY STOMACH at least 30 to 60 minutes before breakfast.",
            "timing": "Once daily, first thing in the morning upon waking.",
            "what_to_avoid": "Separate Calcium, Iron supplements, Multivitamins, Soy products, and Antacids by at least 4 hours (drastically inhibit levothyroxine absorption). Avoid coffee/tea for 60 min after taking.",
            "missed_dose": "Take as soon as remembered if stomach is empty. If it is already midday, take 2 hours after food or resume next morning.",
            "overdose_warning": "Thyrotoxicosis: Palpitations, chest pain, anxiety, tremors, insomnia, excessive sweating, weight loss.",
            "storage": "Store in a light-resistant container between 15°C and 30°C.",
            "special_precautions": "Requires periodic serum TSH blood tests (every 6-12 weeks initially) to titrate exact dose."
        }
    },
    {
        "id": "PILL-VIT-D3",
        "brand_name": "Calcirol 60K (D-Rise)",
        "generic_name": "Cholecalciferol (Vitamin D3)",
        "strength": "60,000 IU",
        "form_type": "Softgel Capsule",
        "color": "Yellow / Translucent Gold",
        "color_hex": "#f59e0b",
        "secondary_color_hex": None,
        "shape": "Round / Oval Softgel",
        "imprint": "60K / SUN",
        "score": "Unscored",
        "coating": "Soft Gelatin",
        "primary_use": "Severe Vitamin D deficiency, bone health, osteoporosis prevention, immune optimization.",
        "drug_class": "Fat-Soluble Secosteroid Vitamin",
        "how_to_use": {
            "administration": "Take with the largest or fattiest meal of the day (e.g. lunch or dinner with healthy fats, milk, or ghee) to boost absorption by up to 50%.",
            "timing": "Typically taken ONCE WEEKLY for 6-8 weeks, followed by monthly maintenance.",
            "what_to_avoid": "Avoid taking with mineral oil or Orlistat (weight loss pills) which block fat-soluble vitamin absorption.",
            "missed_dose": "Take on the day you remember, then adjust your weekly schedule to that new day of the week.",
            "overdose_warning": "Hypercalcemia (nausea, confusion, kidney stones, extreme thirst, frequent urination).",
            "storage": "Store in a cool dry place below 25°C away from direct sunlight.",
            "special_precautions": "Monitor serum 25-hydroxy Vitamin D and serum calcium levels periodically."
        }
    },
    {
        "id": "PILL-CIP-500",
        "brand_name": "Cipro 500 (Ciplox)",
        "generic_name": "Ciprofloxacin",
        "strength": "500 mg",
        "form_type": "Film-coated Tablet",
        "color": "White",
        "color_hex": "#ffffff",
        "secondary_color_hex": None,
        "shape": "Oval / Oblong",
        "imprint": "CIPRO 500 / BAYER",
        "score": "Single Score Line",
        "coating": "Film-coated",
        "primary_use": "Complicated urinary tract infections, infectious diarrhea, prostatitis, bone & joint infections.",
        "drug_class": "Fluoroquinolone Antibiotic",
        "how_to_use": {
            "administration": "Drink plenty of fluids (at least 2-3 liters of water daily) to prevent crystalluria. Can be taken with or without meals.",
            "timing": "Every 12 hours (twice daily) at evenly spaced intervals for the duration prescribed.",
            "what_to_avoid": "Do NOT take with Dairy products (Milk, Yogurt) or Calcium-fortified juices alone; separate by 2 hours. Avoid antacids, iron, and zinc.",
            "missed_dose": "Take as soon as remembered if >6 hours before next dose. Do not double up.",
            "overdose_warning": "Renal toxicity, seizures, tremors, QT prolongation.",
            "storage": "Store below 25°C in original blister.",
            "special_precautions": "Black box warning for tendinitis and tendon rupture (especially Achilles tendon) and peripheral neuropathy."
        }
    }
]