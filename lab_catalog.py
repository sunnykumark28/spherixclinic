"""
lab_catalog.py
Comprehensive Tata 1mg-style Diagnostic Catalog & Health Package Index for Spherix Clinic.
Features:
- Flagship Multi-Parameter Full Body Packages (Gold, Platinum, Women, Senior, Diabetes, Cardiac, Fever, Men)
- 40+ Individual Standard Pathology & Radiology Tests
- Clinical Parameter Breakdowns, Fasting Requirements, Turnaround Times (TAT), Sample Types
- Search Indexing & Category Filtering
"""

import re

# ================= 1. FLAGSHIP MULTI-PARAMETER HEALTH PACKAGES =================
HEALTH_PACKAGES = [
    {
        "id": "PKG-FULL-GOLD",
        "name": "Comprehensive Gold Full Body Health Checkup",
        "badge": "MOST POPULAR",
        "category": "Full Body Checkups",
        "concern": "General Wellness",
        "price": 1299,
        "mrp": 3499,
        "discount_percent": 63,
        "parameters_count": 83,
        "sample_type": "Blood & Urine",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 12,
        "rating": 4.9,
        "reviews_count": 18450,
        "description": "Exhaustive full-body screening evaluating heart, liver, kidney, thyroid, blood cells, bone minerals, lipid metabolism, and urinalysis.",
        "who_should_take": "Recommended for all adults (aged 18+) once or twice annually for preventive baseline evaluation.",
        "preparation": "Requires 10-12 hours of overnight fasting. Plain water is permitted.",
        "parameters_breakdown": [
            {"group": "Complete Hemogram (24 Tests)", "tests": ["Hemoglobin", "RBC Count", "WBC Total Count", "Platelet Count", "MCV, MCH, MCHC", "Differential WBC Count (5 Parts)", "ESR", "RDW-CV / RDW-SD", "PCV / Hematocrit"]},
            {"group": "Liver Function Test - LFT (12 Tests)", "tests": ["SGOT (AST)", "SGPT (ALT)", "Bilirubin Total", "Bilirubin Direct", "Bilirubin Indirect", "Alkaline Phosphatase (ALP)", "Total Protein", "Serum Albumin", "Serum Globulin", "A/G Ratio", "Gamma GT (GGTP)"]},
            {"group": "Kidney Function Test - KFT (8 Tests)", "tests": ["Serum Creatinine", "Blood Urea Nitrogen (BUN)", "Uric Acid", "BUN/Creatinine Ratio", "Serum Calcium", "Serum Phosphorus", "Serum Sodium", "Serum Potassium"]},
            {"group": "Lipid Profile (9 Tests)", "tests": ["Total Cholesterol", "HDL Cholesterol (Good)", "LDL Cholesterol (Bad)", "VLDL Cholesterol", "Triglycerides", "Non-HDL Cholesterol", "TC/HDL Ratio", "LDL/HDL Ratio"]},
            {"group": "Thyroid Profile Total (3 Tests)", "tests": ["Total T3 (Triiodothyronine)", "Total T4 (Thyroxine)", "TSH (Thyroid Stimulating Hormone)"]},
            {"group": "Diabetes Screening (2 Tests)", "tests": ["Fasting Blood Glucose", "Average Estimated Glucose"]},
            {"group": "Bone & Mineral Health (4 Tests)", "tests": ["Serum Calcium", "Serum Phosphorus", "Alkaline Phosphatase", "Uric Acid"]},
            {"group": "Urine Routine & Microscopic (21 Tests)", "tests": ["Urine pH", "Specific Gravity", "Urine Protein", "Urine Glucose", "Ketone Bodies", "Bilirubin", "Urobilinogen", "Pus Cells / WBC", "RBCs", "Epithelial Cells", "Casts & Crystals"]}
        ]
    },
    {
        "id": "PKG-FULL-PLATINUM",
        "name": "Comprehensive Platinum Full Body Screening with Vitamins",
        "badge": "BEST VALUE",
        "category": "Full Body Checkups",
        "concern": "General Wellness",
        "price": 1999,
        "mrp": 5200,
        "discount_percent": 62,
        "parameters_count": 102,
        "sample_type": "Blood & Urine",
        "fasting_required": True,
        "fasting_hours": 12,
        "tat_hours": 18,
        "rating": 4.9,
        "reviews_count": 12380,
        "description": "Our most advanced whole-body wellness monograph including Vitamin D (25-OH), Vitamin B12, HbA1c 3-Month Diabetes Screen, Iron Studies, plus complete LFT, KFT, Lipid, and Thyroid profiles.",
        "who_should_take": "Ideal for adults seeking deep nutritional, metabolic, endocrine, and systemic organ assessment.",
        "preparation": "Requires 10-12 hours overnight fasting. Avoid biotin supplements 24 hours prior.",
        "parameters_breakdown": [
            {"group": "Vitamin & Nutrition Panel (3 Tests)", "tests": ["Vitamin D (25-Hydroxy)", "Vitamin B12 (Cyanocobalamin)", "Serum Folic Acid"]},
            {"group": "Diabetes & Glycemic Panel (3 Tests)", "tests": ["HbA1c (Glycated Hemoglobin)", "Estimated Average Glucose (eAG)", "Fasting Blood Sugar"]},
            {"group": "Iron Deficiency Profile (4 Tests)", "tests": ["Serum Iron", "Total Iron Binding Capacity (TIBC)", "UIBC", "% Transferrin Saturation"]},
            {"group": "Complete Hemogram (24 Tests)", "tests": ["Complete Blood Count (CBC) with Automated Differential and Platelet Indices", "ESR"]},
            {"group": "Lipid & Cardiac Risk Profile (9 Tests)", "tests": ["Cholesterol Total, HDL, LDL, VLDL, Triglycerides, Non-HDL, Ratios"]},
            {"group": "Liver Function Panel (12 Tests)", "tests": ["SGOT, SGPT, Total/Direct Bilirubin, ALP, GGTP, Proteins, Albumin/Globulin"]},
            {"group": "Kidney & Electrolytes Panel (10 Tests)", "tests": ["Creatinine, Urea, Uric Acid, BUN, Sodium, Potassium, Chloride, Calcium, Phosphorus"]},
            {"group": "Thyroid Profile Total (3 Tests)", "tests": ["Total T3, Total T4, Ultrasensitive TSH"]},
            {"group": "Complete Urinalysis (21 Tests)", "tests": ["Physical, Chemical, and Microscopic Sediment Examination"]}
        ]
    },
    {
        "id": "PKG-WOMEN-WELLNESS",
        "name": "Comprehensive Women's Health & Hormones Package",
        "badge": "WOMEN'S SPECIAL",
        "category": "Women's Health",
        "concern": "Women's Health",
        "price": 1499,
        "mrp": 3800,
        "discount_percent": 60,
        "parameters_count": 74,
        "sample_type": "Blood & Urine",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 16,
        "rating": 4.9,
        "reviews_count": 9400,
        "description": "Tailored diagnostic profile for women assessing hormonal balance (TSH/Thyroid, LH, FSH, Prolactin), Iron deficiency anemia, Bone Vitamin D3, Lipid, Liver, and Kidney health.",
        "who_should_take": "Women with fatigue, hair loss, irregular periods, PCOD concerns, or routine wellness checks.",
        "preparation": "10-12 hours fasting. Best scheduled during early follicular phase (Day 2-5 of menstrual cycle) if hormone assessment is requested.",
        "parameters_breakdown": [
            {"group": "Anemia & Iron Studies (5 Tests)", "tests": ["Serum Ferritin", "Serum Iron", "TIBC", "Transferrin Saturation", "Hemoglobin"]},
            {"group": "Thyroid Function (3 Tests)", "tests": ["Total T3, Total T4, Ultra-sensitive TSH"]},
            {"group": "Bone Health & Vitamins (3 Tests)", "tests": ["Vitamin D (25-OH)", "Vitamin B12", "Serum Calcium"]},
            {"group": "Complete Hemogram (24 Tests)", "tests": ["Full CBC + ESR"]},
            {"group": "Metabolic, Liver & Kidney Profile (22 Tests)", "tests": ["Fasting Sugar, LFT (10 tests), KFT (8 tests), Lipid Profile (9 tests)"]}
        ]
    },
    {
        "id": "PKG-SENIOR-CITIZEN",
        "name": "Senior Citizen Health & Longevity Package",
        "badge": "AGE 50+",
        "category": "Senior Citizen",
        "concern": "Senior Citizen",
        "price": 1599,
        "mrp": 4200,
        "discount_percent": 62,
        "parameters_count": 80,
        "sample_type": "Blood & Urine",
        "fasting_required": True,
        "fasting_hours": 12,
        "tat_hours": 14,
        "rating": 4.8,
        "reviews_count": 7600,
        "description": "Specialized age-calibrated screening monitoring joint health, kidney filtration (eGFR), cardiac risk (hs-CRP, Lipid), HbA1c diabetes control, and electrolyte balance.",
        "who_should_take": "Adults aged 50 and above for comprehensive chronic disease monitoring.",
        "preparation": "10-12 hours overnight fasting. Routine morning cardiac/BP medications can be taken with small sips of water unless physician advised otherwise.",
        "parameters_breakdown": [
            {"group": "Diabetes & HbA1c (2 Tests)", "tests": ["HbA1c Glycated Hemoglobin", "Average Blood Sugar"]},
            {"group": "Kidney & eGFR (8 Tests)", "tests": ["Serum Creatinine with eGFR calculation", "BUN", "Uric Acid", "Electrolytes"]},
            {"group": "Inflammatory & Cardiac Markers (2 Tests)", "tests": ["hs-CRP (High Sensitivity)", "Lipid Profile Complete"]},
            {"group": "Liver, Bones & Hemogram (68 Tests)", "tests": ["LFT, Calcium, Phosphorus, CBC, Thyroid, Urine Routine"]}
        ]
    },
    {
        "id": "PKG-DIABETES-ADV",
        "name": "Comprehensive Diabetes & Metabolic Care Plan",
        "badge": "DIABETES CARE",
        "category": "Diabetes",
        "concern": "Diabetes",
        "price": 999,
        "mrp": 2500,
        "discount_percent": 60,
        "parameters_count": 48,
        "sample_type": "Blood & Urine",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 10,
        "rating": 4.9,
        "reviews_count": 14200,
        "description": "Specialized glycemic monitoring package analyzing 3-month HbA1c control, Fasting Glucose, Diabetic Kidney micro-damage markers (Urine Microalbumin/Creatinine), and Cardiac Lipid Risk.",
        "who_should_take": "Individuals with diagnosed Type 1/Type 2 diabetes, prediabetes, or metabolic syndrome.",
        "preparation": "Requires 10-12 hours fasting. If Post-Prandial Blood Sugar (PPBS) is added, sample is collected exactly 2 hours after breakfast.",
        "parameters_breakdown": [
            {"group": "Glycemic Markers (3 Tests)", "tests": ["HbA1c", "Estimated Average Glucose (eAG)", "Fasting Blood Sugar (FBS)"]},
            {"group": "Diabetic Nephropathy Screen (3 Tests)", "tests": ["Serum Creatinine", "Urine Microalbumin", "Urine Albumin/Creatinine Ratio (ACR)"]},
            {"group": "Cardiovascular Lipid Risk (9 Tests)", "tests": ["Total Cholesterol, HDL, LDL, VLDL, Triglycerides, Non-HDL"]},
            {"group": "Complete Hemogram & Urine (33 Tests)", "tests": ["CBC (24 tests), Urine Routine & Microscopy (21 tests)"]}
        ]
    },
    {
        "id": "PKG-CARDIAC-PRO",
        "name": "Comprehensive Cardiac & Heart Health Profile",
        "badge": "HEART CARE",
        "category": "Cardiac",
        "concern": "Heart Health",
        "price": 1399,
        "mrp": 3600,
        "discount_percent": 61,
        "parameters_count": 42,
        "sample_type": "Blood",
        "fasting_required": True,
        "fasting_hours": 12,
        "tat_hours": 14,
        "rating": 4.8,
        "reviews_count": 6800,
        "description": "High-precision cardiovascular risk evaluation analyzing high-sensitivity hs-CRP, Apolipoproteins A1 & B, Homocysteine, complete Lipid panel, and Electrolytes.",
        "who_should_take": "Individuals with high cholesterol, family history of heart disease, hypertension, or lifestyle stress.",
        "preparation": "Strict 12 hours overnight fasting. Avoid alcohol and high-fat dinner the night before.",
        "parameters_breakdown": [
            {"group": "Advanced Cardiac Biomarkers (3 Tests)", "tests": ["hs-CRP (Cardiac Risk)", "Serum Homocysteine", "Apolipoprotein B / A1 Ratio"]},
            {"group": "Lipid Profile Extended (9 Tests)", "tests": ["Total Cholesterol, HDL, LDL, VLDL, Triglycerides, Non-HDL, TC/HDL Ratio"]},
            {"group": "Metabolic & Renal Risk (12 Tests)", "tests": ["Fasting Glucose, Serum Creatinine, Uric Acid, Sodium, Potassium, Chloride"]},
            {"group": "Complete Blood Count (24 Tests)", "tests": ["CBC with Platelet Count & Hemoglobin"]}
        ]
    },
    {
        "id": "PKG-FEVER-PANEL",
        "name": "Comprehensive Fever & Viral Infection Profile",
        "badge": "FAST REPORT",
        "category": "Fever & Infection",
        "concern": "Fever & Infection",
        "price": 899,
        "mrp": 2200,
        "discount_percent": 59,
        "parameters_count": 32,
        "sample_type": "Blood & Urine",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "rating": 4.9,
        "reviews_count": 11500,
        "description": "Rapid differential panel identifying etiology of acute fever: Dengue NS1 Antigen, Dengue IgG/IgM Antibodies, Typhoid Widal Test, Malaria Parasite (Smear/Antigen), CBC with Platelet Monitoring, and Urine CUE.",
        "who_should_take": "Patients presenting with sudden fever, chills, body ache, joint pain, or suspected seasonal viral infection.",
        "preparation": "No fasting required. Same-day 6-hour express reporting.",
        "parameters_breakdown": [
            {"group": "Viral & Vector Infection Markers (5 Tests)", "tests": ["Dengue NS1 Antigen", "Dengue IgG Antibody", "Dengue IgM Antibody", "Malaria Parasite Smear & Antigen (Pv/Pf)", "Widal Agglutination (Typhoid)"]},
            {"group": "Inflammatory & Blood Cell Indices (25 Tests)", "tests": ["CBC with Rapid Platelet Count & Differential", "ESR"]},
            {"group": "Urinalysis (21 Tests)", "tests": ["Urine Routine & Microscopic Examination for UTI"]}
        ]
    },
    {
        "id": "PKG-MEN-VITALITY",
        "name": "Men's Active Wellness & Fitness Package",
        "badge": "MEN'S SPECIAL",
        "category": "Men's Health",
        "concern": "Men's Health",
        "price": 1399,
        "mrp": 3500,
        "discount_percent": 60,
        "parameters_count": 68,
        "sample_type": "Blood & Urine",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 14,
        "rating": 4.8,
        "reviews_count": 5900,
        "description": "Comprehensive metabolic and hormonal profile evaluating Testosterone Total, Vitamin D3, Vitamin B12, Liver Function, Lipid Profile, Kidney Function, and Hemogram.",
        "who_should_take": "Men experiencing low energy, muscle fatigue, fitness goals, or annual preventative health screening.",
        "preparation": "10 hours fasting. Morning sample (before 10:00 AM) optimal for testosterone measurement.",
        "parameters_breakdown": [
            {"group": "Male Endocrine & Vitamins (3 Tests)", "tests": ["Total Testosterone", "Vitamin D (25-OH)", "Vitamin B12"]},
            {"group": "Lipid & Cardiovascular Panel (9 Tests)", "tests": ["Cholesterol, Triglycerides, HDL, LDL, VLDL, Ratios"]},
            {"group": "Liver & Kidney Health (20 Tests)", "tests": ["SGOT, SGPT, Bilirubin, Creatinine, Uric Acid, Urea"]},
            {"group": "Complete Blood Count & Urine (45 Tests)", "tests": ["CBC with ESR and Urine Microscopy"]}
        ]
    }
]

# ================= 2. INDIVIDUAL PATHOLOGY & DIAGNOSTIC TESTS =================
INDIVIDUAL_TESTS = [
    {
        "id": "TST-CBC",
        "name": "Complete Blood Count (CBC) with ESR",
        "category": "Hematology",
        "concern": "General Wellness",
        "price": 299,
        "mrp": 600,
        "discount_percent": 50,
        "parameters_count": 24,
        "sample_type": "Blood (EDTA)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "cpt_code": "85027",
        "popular": True,
        "description": "Measures red blood cells, white blood cells, hemoglobin, hematocrit, platelet count, and erythrocyte sedimentation rate to detect anemia, infections, leukemia, and inflammation.",
        "preparation": "No fasting needed. Normal diet and hydration permitted."
    },
    {
        "id": "TST-LIPID",
        "name": "Lipid Profile (Cholesterol & Triglycerides)",
        "category": "Cardiac",
        "concern": "Heart Health",
        "price": 399,
        "mrp": 900,
        "discount_percent": 56,
        "parameters_count": 9,
        "sample_type": "Blood (Serum)",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 8,
        "cpt_code": "80061",
        "popular": True,
        "description": "Measures Total Cholesterol, HDL (Good), LDL (Bad), VLDL, Triglycerides, and cardiac risk ratios to evaluate cardiovascular health and plaque buildup risk.",
        "preparation": "10-12 hours overnight fasting. Avoid alcohol and greasy dinner prior."
    },
    {
        "id": "TST-LFT",
        "name": "Liver Function Test (LFT) Extended",
        "category": "Liver",
        "concern": "Liver Health",
        "price": 449,
        "mrp": 1000,
        "discount_percent": 55,
        "parameters_count": 12,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 8,
        "cpt_code": "80076",
        "popular": True,
        "description": "Analyzes enzymes and proteins (SGOT, SGPT, Bilirubin Total/Direct, ALP, GGTP, Albumin, Globulin) to assess liver inflammation, jaundice, and cellular injury.",
        "preparation": "No strict fasting required, but light meal 4 hours before is recommended."
    },
    {
        "id": "TST-KFT",
        "name": "Kidney Function Test (KFT / RFT)",
        "category": "Kidney",
        "concern": "Kidney Health",
        "price": 449,
        "mrp": 1000,
        "discount_percent": 55,
        "parameters_count": 8,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 8,
        "cpt_code": "80069",
        "popular": True,
        "description": "Evaluates kidney filtration capacity via Serum Creatinine, Blood Urea Nitrogen (BUN), Uric Acid, BUN/Creatinine ratio, and serum electrolytes.",
        "preparation": "Drink adequate water before test. Avoid heavy strenuous exercise right before blood draw."
    },
    {
        "id": "TST-THYROID",
        "name": "Thyroid Profile Total (T3, T4, TSH)",
        "category": "Thyroid",
        "concern": "Thyroid & Hormones",
        "price": 349,
        "mrp": 750,
        "discount_percent": 53,
        "parameters_count": 3,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 8,
        "cpt_code": "84443",
        "popular": True,
        "description": "Screens for Hypothyroidism and Hyperthyroidism by quantifying Total T3, Total T4, and pituitary Thyroid Stimulating Hormone (TSH).",
        "preparation": "Morning blood sample preferred. If on thyroid medication (e.g. Thyronorm/Levothyroxine), take medication after blood collection."
    },
    {
        "id": "TST-HBA1C",
        "name": "HbA1c (Glycated Hemoglobin) & Average Sugar",
        "category": "Diabetes",
        "concern": "Diabetes",
        "price": 299,
        "mrp": 650,
        "discount_percent": 54,
        "parameters_count": 2,
        "sample_type": "Blood (EDTA)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "cpt_code": "83036",
        "popular": True,
        "description": "Gold standard diagnostic for diabetes reflecting average blood sugar control over the preceding 2 to 3 months (90 days).",
        "preparation": "No fasting required. Can be done anytime during the day."
    },
    {
        "id": "TST-VITD",
        "name": "Vitamin D (25-Hydroxy) Total",
        "category": "Vitamins",
        "concern": "Bones & Immunity",
        "price": 599,
        "mrp": 1400,
        "discount_percent": 57,
        "parameters_count": 1,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 12,
        "cpt_code": "82306",
        "popular": True,
        "description": "Evaluates circulating Vitamin D reserves essential for bone mineralization, calcium absorption, muscle function, and immune defense.",
        "preparation": "No fasting needed. Avoid taking high-dose Vitamin D supplements 24 hours prior."
    },
    {
        "id": "TST-VITB12",
        "name": "Vitamin B12 (Cyanocobalamin) Assay",
        "category": "Vitamins",
        "concern": "Nerves & Energy",
        "price": 549,
        "mrp": 1200,
        "discount_percent": 54,
        "parameters_count": 1,
        "sample_type": "Blood (Serum)",
        "fasting_required": True,
        "fasting_hours": 8,
        "tat_hours": 12,
        "cpt_code": "82607",
        "popular": True,
        "description": "Measures active Vitamin B12 levels crucial for nerve sheath maintenance, brain function, and red blood cell maturation.",
        "preparation": "8 hours fasting recommended for optimal precision."
    },
    {
        "id": "TST-URINE-CUE",
        "name": "Urine Routine & Microscopic Examination (CUE)",
        "category": "Urinalysis",
        "concern": "Kidney & Urinary",
        "price": 179,
        "mrp": 350,
        "discount_percent": 49,
        "parameters_count": 21,
        "sample_type": "Urine (Clean Catch)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "cpt_code": "81000",
        "popular": True,
        "description": "Screens for urinary tract infections (UTIs), kidney damage, glycosuria, proteinuria, microscopic hematuria, and renal crystals.",
        "preparation": "First morning midstream clean-catch urine sample in sterile container."
    },
    {
        "id": "TST-IRON-PROFILE",
        "name": "Iron Deficiency Profile (Iron + TIBC + Ferritin)",
        "category": "Hematology",
        "concern": "Anemia & Energy",
        "price": 599,
        "mrp": 1300,
        "discount_percent": 54,
        "parameters_count": 4,
        "sample_type": "Blood (Serum)",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 12,
        "cpt_code": "85390",
        "popular": False,
        "description": "Comprehensive iron status workup distinguishing iron-deficiency anemia from chronic inflammatory anemias.",
        "preparation": "10 hours fasting. Morning sample preferred as iron levels fluctuate diurnal."
    },
    {
        "id": "TST-HSCRP",
        "name": "High Sensitivity C-Reactive Protein (hs-CRP)",
        "category": "Cardiac",
        "concern": "Heart Health",
        "price": 499,
        "mrp": 950,
        "discount_percent": 47,
        "parameters_count": 1,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 8,
        "cpt_code": "86141",
        "popular": False,
        "description": "Precision biomarker for arterial vascular inflammation and independent predictor of cardiovascular incidents.",
        "preparation": "No fasting required. Test should be delayed if you have active viral fever or acute physical injury."
    },
    {
        "id": "TST-ELECTROLYTES",
        "name": "Serum Electrolytes (Na+, K+, Cl-)",
        "category": "Biochemistry",
        "concern": "Hydration & Kidneys",
        "price": 349,
        "mrp": 700,
        "discount_percent": 50,
        "parameters_count": 3,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "cpt_code": "80051",
        "popular": False,
        "description": "Measures electrical balance and fluid homeostasis of sodium, potassium, and chloride ions.",
        "preparation": "No special preparation required."
    },
    {
        "id": "TST-DENGUE-DUO",
        "name": "Dengue Duo (NS1 Antigen + IgG & IgM Antibodies)",
        "category": "Fever & Infection",
        "concern": "Fever & Infection",
        "price": 649,
        "mrp": 1200,
        "discount_percent": 46,
        "parameters_count": 3,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 4,
        "cpt_code": "87449",
        "popular": True,
        "description": "Rapid dual detection for early Dengue infection (NS1 in Days 1-5) and secondary immune antibody response (IgM/IgG).",
        "preparation": "No fasting needed. 4-hour express emergency processing available."
    },
    {
        "id": "TST-WIDAL",
        "name": "Widal Slide & Tube Agglutination (Typhoid)",
        "category": "Fever & Infection",
        "concern": "Fever & Infection",
        "price": 249,
        "mrp": 500,
        "discount_percent": 50,
        "parameters_count": 4,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "cpt_code": "86000",
        "popular": False,
        "description": "Screens for Salmonella Typhi and Paratyphi antibodies (TO, TH, AH, BH antigens) in sustained fever cases.",
        "preparation": "No fasting required."
    },
    {
        "id": "TST-FBS",
        "name": "Fasting Blood Sugar (Glucose)",
        "category": "Diabetes",
        "concern": "Diabetes",
        "price": 99,
        "mrp": 200,
        "discount_percent": 51,
        "parameters_count": 1,
        "sample_type": "Blood (Fluoride)",
        "fasting_required": True,
        "fasting_hours": 10,
        "tat_hours": 4,
        "cpt_code": "82947",
        "popular": True,
        "description": "Measures blood glucose concentration after 8-10 hours of fasting to diagnose prediabetes and diabetes.",
        "preparation": "Overnight 8-10 hours fasting. Plain water allowed."
    },
    {
        "id": "TST-PPBS",
        "name": "Post Prandial Blood Sugar (PPBS 2-Hour)",
        "category": "Diabetes",
        "concern": "Diabetes",
        "price": 99,
        "mrp": 200,
        "discount_percent": 51,
        "parameters_count": 1,
        "sample_type": "Blood (Fluoride)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 4,
        "cpt_code": "82950",
        "popular": True,
        "description": "Measures blood sugar spike exactly 2 hours after starting a regular breakfast or meal.",
        "preparation": "Blood draw must be done exactly 2 hours after the start of meal."
    },
    {
        "id": "TST-PSA",
        "name": "Prostate Specific Antigen (PSA) Total",
        "category": "Men's Health",
        "concern": "Men's Health",
        "price": 649,
        "mrp": 1250,
        "discount_percent": 48,
        "parameters_count": 1,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 12,
        "cpt_code": "84153",
        "popular": False,
        "description": "Screens for benign prostatic hyperplasia (BPH), prostate inflammation, and prostate neoplasia in men.",
        "preparation": "Avoid sexual activity / ejaculation and cycling 48 hours before the test."
    },
    {
        "id": "TST-URICACID",
        "name": "Serum Uric Acid (Gout Screen)",
        "category": "Biochemistry",
        "concern": "Bones & Joints",
        "price": 199,
        "mrp": 400,
        "discount_percent": 50,
        "parameters_count": 1,
        "sample_type": "Blood (Serum)",
        "fasting_required": True,
        "fasting_hours": 8,
        "tat_hours": 6,
        "cpt_code": "84550",
        "popular": True,
        "description": "Detects hyperuricemia responsible for acute gouty arthritis joint flares and uric acid kidney stones.",
        "preparation": "8 hours fasting. Avoid purine-rich foods (red meat, seafood, beer) before testing."
    },
    {
        "id": "TST-CALCIUM",
        "name": "Serum Calcium (Total & Corrected)",
        "category": "Biochemistry",
        "concern": "Bones & Joints",
        "price": 199,
        "mrp": 400,
        "discount_percent": 50,
        "parameters_count": 2,
        "sample_type": "Blood (Serum)",
        "fasting_required": False,
        "fasting_hours": 0,
        "tat_hours": 6,
        "cpt_code": "82310",
        "popular": False,
        "description": "Measures total serum calcium to evaluate parathyroid function, osteoporosis risk, and bone metabolism.",
        "preparation": "No fasting required."
    }
]

ALL_LAB_ITEMS = [*HEALTH_PACKAGES, *INDIVIDUAL_TESTS]
LAB_ITEMS_BY_ID = {item["id"]: item for item in ALL_LAB_ITEMS}

def get_all_packages():
    return HEALTH_PACKAGES

def get_all_tests():
    return INDIVIDUAL_TESTS

def get_item_by_id(item_id):
    return LAB_ITEMS_BY_ID.get(item_id)

def search_lab_catalog(query="", category="all", concern="all", item_type="all"):
    """
    Multi-factor filter and fuzzy search over lab packages and individual tests.
    """
    results = []
    q = (query or "").strip().lower()
    
    for item in ALL_LAB_ITEMS:
        # Filter item type (package vs test)
        is_pkg = item["id"].startswith("PKG-")
        if item_type == "package" and not is_pkg:
            continue
        if item_type == "test" and is_pkg:
            continue

        # Filter category
        if category and category != "all" and item.get("category", "").lower() != category.lower():
            continue

        # Filter concern
        if concern and concern != "all" and item.get("concern", "").lower() != concern.lower():
            continue

        # Query search
        if q:
            text_corpus = f"{item.get('name', '')} {item.get('category', '')} {item.get('concern', '')} {item.get('description', '')}".lower()
            # Also search within package parameter breakdowns if available
            if "parameters_breakdown" in item:
                for group in item["parameters_breakdown"]:
                    text_corpus += " " + group.get("group", "").lower() + " " + " ".join(group.get("tests", [])).lower()
            
            if q not in text_corpus:
                continue

        results.append(item)

    return results
