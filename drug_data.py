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