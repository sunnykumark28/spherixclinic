"""
Spherix Diagnostic Network - Comprehensive Master Catalog & Reference Database
Defines standard biological categories, clinical diagnostic tests, parameters with reference ranges,
and multi-parameter health packages.
"""

from typing import Dict, List, Any

DIAGNOSTIC_MASTER_CATEGORIES = [
    {
        "id": "CAT-HEM",
        "code": "HEM",
        "name": "Hematology",
        "description": "Complete blood counts, cellular morphology, coagulation and bleeding profiles.",
        "icon": "fas fa-tint",
        "display_order": 1
    },
    {
        "id": "CAT-BIO",
        "code": "BIO",
        "name": "Biochemistry / Clinical Chemistry",
        "description": "Metabolic panels, renal/liver functions, glycemic controls, electrolytes and lipid profiles.",
        "icon": "fas fa-vial",
        "display_order": 2
    },
    {
        "id": "CAT-IMM",
        "code": "IMM",
        "name": "Immunology",
        "description": "Autoimmune assays, inflammatory markers, and immunoglobulin quantifications.",
        "icon": "fas fa-shield-virus",
        "display_order": 3
    },
    {
        "id": "CAT-SER",
        "code": "SER",
        "name": "Serology",
        "description": "Infectious antibodies, viral antigens (HIV, Hepatitis, Dengue, Typhoid).",
        "icon": "fas fa-microscope",
        "display_order": 4
    },
    {
        "id": "CAT-MIC",
        "code": "MIC",
        "name": "Microbiology",
        "description": "Bacterial and fungal culture with automated antibiotic sensitivity testing (AST).",
        "icon": "fas fa-bacterium",
        "display_order": 5
    },
    {
        "id": "CAT-CP",
        "code": "CP",
        "name": "Clinical Pathology",
        "description": "Routine & microscopic urinalysis, stool analysis, and body fluid examinations.",
        "icon": "fas fa-flask",
        "display_order": 6
    },
    {
        "id": "CAT-HISTO",
        "code": "HISTO",
        "name": "Histopathology",
        "description": "Tissue biopsy, surgical specimen evaluation, and immunohistochemistry.",
        "icon": "fas fa-dna",
        "display_order": 7
    },
    {
        "id": "CAT-CYTO",
        "code": "CYTO",
        "name": "Cytology",
        "description": "Liquid-based Pap smears (LBC), FNAC, and exfoliate cell cytology.",
        "icon": "fas fa-eye-dropper",
        "display_order": 8
    },
    {
        "id": "CAT-MOL",
        "code": "MOL",
        "name": "Molecular Diagnostics",
        "description": "Real-time PCR, RT-PCR viral load, and multiplex genomic amplifications.",
        "icon": "fas fa-atom",
        "display_order": 9
    },
    {
        "id": "CAT-GEN",
        "code": "GEN",
        "name": "Genetic Testing",
        "description": "Karyotyping, hereditary disease screening, and next-generation sequencing panels.",
        "icon": "fas fa-project-diagram",
        "display_order": 10
    },
    {
        "id": "CAT-ENDO",
        "code": "ENDO",
        "name": "Hormone / Endocrinology",
        "description": "Thyroid hormones, reproductive panels, cortisol, insulin, and fertility markers.",
        "icon": "fas fa-wave-square",
        "display_order": 11
    },
    {
        "id": "CAT-COAG",
        "code": "COAG",
        "name": "Coagulation",
        "description": "PT/INR, aPTT, D-Dimer, and fibrinogen hemostasis monitoring.",
        "icon": "fas fa-heartbeat",
        "display_order": 12
    },
    {
        "id": "CAT-TOX",
        "code": "TOX",
        "name": "Toxicology",
        "description": "Therapeutic drug monitoring, heavy metals, and occupational toxin screening.",
        "icon": "fas fa-biohazard",
        "display_order": 13
    },
    {
        "id": "CAT-ALLERGY",
        "code": "ALLERGY",
        "name": "Allergy Testing",
        "description": "Total IgE and comprehensive food, respiratory, and environmental allergen panels.",
        "icon": "fas fa-allergies",
        "display_order": 14
    },
    {
        "id": "CAT-BB",
        "code": "BB",
        "name": "Immunohematology / Blood Bank",
        "description": "ABO blood grouping, Rh typing, crossmatching, and direct/indirect Coombs assays.",
        "icon": "fas fa-hand-holding-medical",
        "display_order": 15
    },
    {
        "id": "CAT-TUMOR",
        "code": "TUMOR",
        "name": "Tumor / Cancer Markers",
        "description": "Quantitative oncological markers: PSA, CA-125, CEA, AFP, CA 19-9.",
        "icon": "fas fa-ribbon",
        "display_order": 16
    },
    {
        "id": "CAT-PRENATAL",
        "code": "PRENATAL",
        "name": "Prenatal / Maternal Tests",
        "description": "Double & quadruple marker screening, TORCH profile, and maternal-fetal assessments.",
        "icon": "fas fa-baby",
        "display_order": 17
    },
    {
        "id": "CAT-INFECT",
        "code": "INFECT",
        "name": "Infectious Disease Testing",
        "description": "Malaria, Tuberculosis (IGRA / Quantiferon), Typhoid, and vector-borne panels.",
        "icon": "fas fa-virus",
        "display_order": 18
    },
    {
        "id": "CAT-VITAMINS",
        "code": "VITAMINS",
        "name": "Vitamins & Micronutrients",
        "description": "Vitamin D 25-OH, Vitamin B12, Serum Ferritin, Iron, and essential mineral assays.",
        "icon": "fas fa-capsules",
        "display_order": 19
    }
]

# Master Catalog of Standard Clinical Tests
MASTER_TESTS_CATALOG = [
    # --- HEMATOLOGY ---
    {
        "code": "CBC",
        "name": "Complete Blood Count (CBC) with Differential & Platelets",
        "category_code": "HEM",
        "category_name": "Hematology",
        "sample_type": "Whole Blood (EDTA)",
        "container_type": "Lavender Top Tube (K2-EDTA)",
        "required_quantity": "3.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 6,
        "base_price_usd": 15.0,
        "base_price_inr": 350.0,
        "description": "Evaluates overall health and detects a wide range of disorders including anemia, infection, and leukemia.",
        "preparation_instructions": "No special preparation needed. Maintain normal hydration.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Hemoglobin (Hb)", "unit": "g/dL", "ref_male": "13.5 - 17.5", "ref_female": "12.0 - 15.5", "ref_general": "12.0 - 17.5", "critical_low": 7.0, "critical_high": 20.0},
            {"name": "RBC Count", "unit": "mil/uL", "ref_male": "4.5 - 5.9", "ref_female": "4.1 - 5.1", "ref_general": "4.1 - 5.9"},
            {"name": "Packed Cell Volume (PCV / Hematocrit)", "unit": "%", "ref_male": "41 - 50", "ref_female": "36 - 44", "ref_general": "36 - 50"},
            {"name": "Total Leukocyte Count (WBC)", "unit": "cells/uL", "ref_male": "4000 - 11000", "ref_female": "4000 - 11000", "ref_general": "4000 - 11000", "critical_low": 2000, "critical_high": 30000},
            {"name": "Neutrophils", "unit": "%", "ref_general": "40 - 75"},
            {"name": "Lymphocytes", "unit": "%", "ref_general": "20 - 45"},
            {"name": "Monocytes", "unit": "%", "ref_general": "2 - 10"},
            {"name": "Eosinophils", "unit": "%", "ref_general": "1 - 6"},
            {"name": "Basophils", "unit": "%", "ref_general": "0 - 1"},
            {"name": "Absolute Neutrophil Count (ANC)", "unit": "/uL", "ref_general": "1500 - 8000"},
            {"name": "Platelet Count", "unit": "lakhs/uL", "ref_general": "1.5 - 4.5", "critical_low": 0.5, "critical_high": 10.0},
            {"name": "Mean Corpuscular Volume (MCV)", "unit": "fL", "ref_general": "80 - 100"},
            {"name": "Mean Corpuscular Hemoglobin (MCH)", "unit": "pg", "ref_general": "27 - 33"},
            {"name": "Mean Corpuscular Hb Conc (MCHC)", "unit": "g/dL", "ref_general": "32 - 36"},
            {"name": "Red Cell Distribution Width (RDW)", "unit": "%", "ref_general": "11.5 - 14.5"}
        ]
    },
    {
        "code": "ESR",
        "name": "Erythrocyte Sedimentation Rate (Westergren Method)",
        "category_code": "HEM",
        "category_name": "Hematology",
        "sample_type": "Whole Blood (Sodium Citrate / EDTA)",
        "container_type": "Black Top Tube",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 8.0,
        "base_price_inr": 180.0,
        "description": "Nonspecific measurement of systemic inflammation, infection, and autoimmune activity.",
        "preparation_instructions": "No specific fasting required.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "ESR (1st Hour)", "unit": "mm/hr", "ref_male": "0 - 15", "ref_female": "0 - 20", "ref_general": "0 - 20", "critical_high": 100}
        ]
    },
    {
        "code": "HB",
        "name": "Hemoglobin (Hb) Concentration",
        "category_code": "HEM",
        "category_name": "Hematology",
        "sample_type": "Whole Blood (EDTA)",
        "container_type": "Lavender Top Tube",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 3,
        "base_price_usd": 6.0,
        "base_price_inr": 120.0,
        "description": "Primary oxygen-carrying protein analysis for rapid anemia and polycythemia diagnosis.",
        "preparation_instructions": "Routine sample. Fasting not required.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Hemoglobin", "unit": "g/dL", "ref_male": "13.5 - 17.5", "ref_female": "12.0 - 15.5", "ref_general": "12.0 - 17.5"}
        ]
    },

    # --- BIOCHEMISTRY / CLINICAL CHEMISTRY ---
    {
        "code": "FBS",
        "name": "Fasting Blood Sugar (Glucose, Fasting)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Fluoride Plasma / Serum",
        "container_type": "Grey Top Tube (Sodium Fluoride + Potassium Oxalate)",
        "required_quantity": "2.0 mL",
        "fasting_required": True,
        "fasting_hours": 8,
        "turnaround_hours": 4,
        "base_price_usd": 7.0,
        "base_price_inr": 150.0,
        "description": "Measures circulating blood glucose following an overnight 8-10 hour fast to diagnose impaired fasting glucose and diabetes mellitus.",
        "preparation_instructions": "Strict 8 to 10 hours overnight fasting. Water permitted.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Fasting Blood Glucose", "unit": "mg/dL", "ref_general": "70 - 99", "critical_low": 50, "critical_high": 350}
        ]
    },
    {
        "code": "PPBS",
        "name": "Post-Prandial Blood Sugar (PPBS 2hr)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Fluoride Plasma / Serum",
        "container_type": "Grey Top Tube",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 7.0,
        "base_price_inr": 150.0,
        "description": "Evaluates glucose tolerance and insulin response exactly 2 hours after a standardized meal or glucose load.",
        "preparation_instructions": "Sample must be drawn exactly 2 hours after starting your meal.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Post-Prandial Blood Glucose", "unit": "mg/dL", "ref_general": "70 - 140", "critical_low": 50, "critical_high": 400}
        ]
    },
    {
        "code": "RBS",
        "name": "Random Blood Sugar (Glucose, Random)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Fluoride Plasma / Serum",
        "container_type": "Grey Top Tube",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 2,
        "base_price_usd": 6.0,
        "base_price_inr": 120.0,
        "description": "Immediate point-in-time blood glucose assessment without dietary restrictions.",
        "preparation_instructions": "No preparation necessary.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Random Blood Glucose", "unit": "mg/dL", "ref_general": "70 - 140", "critical_low": 50, "critical_high": 400}
        ]
    },
    {
        "code": "HBA1C",
        "name": "HbA1c (Glycated Hemoglobin) & Estimated Average Glucose",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Whole Blood (EDTA)",
        "container_type": "Lavender Top Tube",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 6,
        "base_price_usd": 20.0,
        "base_price_inr": 450.0,
        "description": "Gold-standard HPLC test reflecting average 3-month glycemic control and monitoring diabetes therapy efficacy.",
        "preparation_instructions": "Fasting not mandatory. Maintain regular diet and medications.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "HbA1c Glycated Hemoglobin", "unit": "%", "ref_general": "4.0 - 5.6", "critical_high": 12.0},
            {"name": "Estimated Average Glucose (eAG)", "unit": "mg/dL", "ref_general": "68 - 114"}
        ]
    },
    {
        "code": "LFT",
        "name": "Liver Function Test (Complete LFT Profile - 12 Parameters)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST / Clot Activator)",
        "required_quantity": "4.0 mL",
        "fasting_required": True,
        "fasting_hours": 8,
        "turnaround_hours": 8,
        "base_price_usd": 28.0,
        "base_price_inr": 650.0,
        "description": "Comprehensive hepatic panel assessing liver enzymes, synthetic capacity, cholestasis, and biliary excretion.",
        "preparation_instructions": "Overnight 8-10 hour fasting is recommended.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Bilirubin Total", "unit": "mg/dL", "ref_general": "0.2 - 1.2", "critical_high": 15.0},
            {"name": "Bilirubin Direct (Conjugated)", "unit": "mg/dL", "ref_general": "0.0 - 0.3"},
            {"name": "Bilirubin Indirect (Unconjugated)", "unit": "mg/dL", "ref_general": "0.1 - 0.9"},
            {"name": "SGOT / AST (Aspartate Aminotransferase)", "unit": "U/L", "ref_male": "0 - 40", "ref_female": "0 - 32", "ref_general": "0 - 40"},
            {"name": "SGPT / ALT (Alanine Aminotransferase)", "unit": "U/L", "ref_male": "0 - 45", "ref_female": "0 - 35", "ref_general": "0 - 45"},
            {"name": "AST / ALT Ratio", "unit": "Ratio", "ref_general": "0.8 - 1.5"},
            {"name": "Alkaline Phosphatase (ALP)", "unit": "U/L", "ref_general": "44 - 147"},
            {"name": "Gamma Glutamyl Transferase (GGT)", "unit": "U/L", "ref_male": "10 - 71", "ref_female": "6 - 42", "ref_general": "8 - 60"},
            {"name": "Total Protein", "unit": "g/dL", "ref_general": "6.4 - 8.3"},
            {"name": "Serum Albumin", "unit": "g/dL", "ref_general": "3.5 - 5.2"},
            {"name": "Serum Globulin", "unit": "g/dL", "ref_general": "2.0 - 3.5"},
            {"name": "A:G Ratio (Albumin:Globulin)", "unit": "Ratio", "ref_general": "1.2 - 2.2"}
        ]
    },
    {
        "code": "KFT",
        "name": "Kidney Function Test (KFT / RFT - 8 Parameters)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "3.5 mL",
        "fasting_required": True,
        "fasting_hours": 8,
        "turnaround_hours": 8,
        "base_price_usd": 25.0,
        "base_price_inr": 600.0,
        "description": "Assesses renal filtration efficiency, glomerular filtration rate (eGFR), nitrogenous clearance, and electrolyte homeostasis.",
        "preparation_instructions": "8-hour overnight fasting recommended. Avoid heavy meat meals prior to test.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Serum Creatinine", "unit": "mg/dL", "ref_male": "0.7 - 1.3", "ref_female": "0.5 - 1.1", "ref_general": "0.6 - 1.2", "critical_high": 4.0},
            {"name": "Estimated GFR (eGFR CKD-EPI)", "unit": "mL/min/1.73m2", "ref_general": "> 90", "critical_low": 15},
            {"name": "Blood Urea Nitrogen (BUN)", "unit": "mg/dL", "ref_general": "7 - 20"},
            {"name": "Blood Urea", "unit": "mg/dL", "ref_general": "15 - 45", "critical_high": 100},
            {"name": "BUN / Creatinine Ratio", "unit": "Ratio", "ref_general": "10:1 - 20:1"},
            {"name": "Serum Uric Acid", "unit": "mg/dL", "ref_male": "3.5 - 7.2", "ref_female": "2.6 - 6.0", "ref_general": "2.6 - 7.2"},
            {"name": "Serum Calcium", "unit": "mg/dL", "ref_general": "8.5 - 10.5", "critical_low": 6.5, "critical_high": 13.0},
            {"name": "Serum Phosphorus", "unit": "mg/dL", "ref_general": "2.5 - 4.5"}
        ]
    },
    {
        "code": "LIPID",
        "name": "Lipid Profile Complete (Cholesterol, HDL, LDL, VLDL, Triglycerides)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "3.0 mL",
        "fasting_required": True,
        "fasting_hours": 12,
        "turnaround_hours": 6,
        "base_price_usd": 22.0,
        "base_price_inr": 500.0,
        "description": "Cardiovascular risk stratification profiling atherogenic and cardioprotective lipid fractions.",
        "preparation_instructions": "Strict 10 to 12 hours overnight fast. Avoid alcohol for 24 hours.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Total Cholesterol", "unit": "mg/dL", "ref_general": "< 200", "critical_high": 300},
            {"name": "Triglycerides", "unit": "mg/dL", "ref_general": "< 150", "critical_high": 500},
            {"name": "HDL Cholesterol (Good Cholesterol)", "unit": "mg/dL", "ref_male": "> 40", "ref_female": "> 50", "ref_general": "> 40"},
            {"name": "LDL Cholesterol (Calculated)", "unit": "mg/dL", "ref_general": "< 100", "critical_high": 190},
            {"name": "VLDL Cholesterol", "unit": "mg/dL", "ref_general": "5 - 30"},
            {"name": "Non-HDL Cholesterol", "unit": "mg/dL", "ref_general": "< 130"},
            {"name": "Total Cholesterol / HDL Ratio", "unit": "Ratio", "ref_general": "3.3 - 4.4"},
            {"name": "LDL / HDL Ratio", "unit": "Ratio", "ref_general": "1.5 - 3.0"}
        ]
    },
    {
        "code": "CREATININE",
        "name": "Serum Creatinine with Estimated GFR (eGFR)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 8.0,
        "base_price_inr": 180.0,
        "description": "Primary biomarker of glomerular filtration function and baseline clearance.",
        "preparation_instructions": "Maintain good hydration.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Serum Creatinine", "unit": "mg/dL", "ref_male": "0.7 - 1.3", "ref_female": "0.5 - 1.1", "ref_general": "0.6 - 1.2"},
            {"name": "eGFR (CKD-EPI Formula)", "unit": "mL/min/1.73m2", "ref_general": "> 90"}
        ]
    },
    {
        "code": "UREA",
        "name": "Blood Urea & Blood Urea Nitrogen (BUN)",
        "category_code": "BIO",
        "category_name": "Biochemistry / Clinical Chemistry",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 8.0,
        "base_price_inr": 180.0,
        "description": "Evaluates protein metabolism waste clearance and uremic staging.",
        "preparation_instructions": "Fasting not strictly required.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Blood Urea", "unit": "mg/dL", "ref_general": "15 - 45"},
            {"name": "Blood Urea Nitrogen (BUN)", "unit": "mg/dL", "ref_general": "7 - 20"}
        ]
    },

    # --- HORMONE & ENDOCRINOLOGY ---
    {
        "code": "TSH",
        "name": "Thyroid Stimulating Hormone (Ultrasensitive TSH)",
        "category_code": "ENDO",
        "category_name": "Hormone / Endocrinology",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 6,
        "base_price_usd": 12.0,
        "base_price_inr": 280.0,
        "description": "Sensitive 3rd-generation chemiluminescent assay for hyperthyroidism and primary hypothyroidism screening.",
        "preparation_instructions": "Morning specimen preferred before taking thyroid medications.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "TSH 3rd Generation", "unit": "uIU/mL", "ref_general": "0.35 - 4.94", "critical_low": 0.05, "critical_high": 20.0}
        ]
    },
    {
        "code": "T3",
        "name": "Triiodothyronine Total (T3)",
        "category_code": "ENDO",
        "category_name": "Hormone / Endocrinology",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 6,
        "base_price_usd": 10.0,
        "base_price_inr": 220.0,
        "description": "Active thyroid hormone evaluation for thyrotoxicosis and T3-toxicosis diagnosis.",
        "preparation_instructions": "Morning blood collection recommended.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Total T3", "unit": "ng/dL", "ref_general": "60 - 200"}
        ]
    },
    {
        "code": "T4",
        "name": "Thyroxine Total (T4)",
        "category_code": "ENDO",
        "category_name": "Hormone / Endocrinology",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 6,
        "base_price_usd": 10.0,
        "base_price_inr": 220.0,
        "description": "Total circulating thyroxine circulating bound and free fractions.",
        "preparation_instructions": "No specific fasting required.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Total T4", "unit": "ug/dL", "ref_general": "4.5 - 12.0"}
        ]
    },

    # --- VITAMINS & MICRONUTRIENTS ---
    {
        "code": "VITD",
        "name": "Vitamin D 25-Hydroxy (Total 25-OH Vitamin D2 + D3)",
        "category_code": "VITAMINS",
        "category_name": "Vitamins & Micronutrients",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.5 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 12,
        "base_price_usd": 30.0,
        "base_price_inr": 900.0,
        "description": "Quantitative LC-MS/MS or CLIA determination of storage vitamin D for bone health and immune regulation.",
        "preparation_instructions": "Avoid taking vitamin D supplements 24 hours prior to sampling.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Total 25-OH Vitamin D", "unit": "ng/mL", "ref_general": "30.0 - 100.0", "critical_low": 10.0}
        ]
    },
    {
        "code": "VITB12",
        "name": "Vitamin B12 (Cyanocobalamin / Active Cobalamin)",
        "category_code": "VITAMINS",
        "category_name": "Vitamins & Micronutrients",
        "sample_type": "Serum",
        "container_type": "Gold Top / Red Top (SST)",
        "required_quantity": "2.5 mL",
        "fasting_required": True,
        "fasting_hours": 8,
        "turnaround_hours": 12,
        "base_price_usd": 26.0,
        "base_price_inr": 750.0,
        "description": "Crucial for erythrocyte maturation, nerve myelination, and cognitive neurological function.",
        "preparation_instructions": "8-hour overnight fasting recommended.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Vitamin B12 Concentration", "unit": "pg/mL", "ref_general": "211 - 911", "critical_low": 150}
        ]
    },

    # --- CLINICAL PATHOLOGY & URINALYSIS ---
    {
        "code": "URINE_R",
        "name": "Urine Routine & Microscopic Examination (Complete Urinalysis)",
        "category_code": "CP",
        "category_name": "Clinical Pathology",
        "sample_type": "Midstream Clean-Catch Urine",
        "container_type": "Sterile Urine Container",
        "required_quantity": "20.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 8.0,
        "base_price_inr": 180.0,
        "description": "Physical, chemical, and automated microscopic examination for UTI, hematuria, proteinuria, and crystalluria.",
        "preparation_instructions": "First morning mid-stream clean catch specimen is ideal.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Color", "unit": "Obs", "ref_general": "Pale Yellow"},
            {"name": "Appearance / Transparency", "unit": "Obs", "ref_general": "Clear"},
            {"name": "Specific Gravity", "unit": "Ratio", "ref_general": "1.005 - 1.030"},
            {"name": "pH", "unit": "pH", "ref_general": "4.6 - 8.0"},
            {"name": "Urine Protein / Albumin", "unit": "Strip", "ref_general": "Nil / Negative"},
            {"name": "Urine Glucose", "unit": "Strip", "ref_general": "Nil / Negative"},
            {"name": "Ketone Bodies", "unit": "Strip", "ref_general": "Negative"},
            {"name": "Bilirubin", "unit": "Strip", "ref_general": "Negative"},
            {"name": "Urobilinogen", "unit": "mg/dL", "ref_general": "0.1 - 1.0"},
            {"name": "Nitrite", "unit": "Strip", "ref_general": "Negative"},
            {"name": "Pus Cells (Leukocytes)", "unit": "/HPF", "ref_general": "0 - 5"},
            {"name": "RBCs (Erythrocytes)", "unit": "/HPF", "ref_general": "0 - 2"},
            {"name": "Epithelial Cells", "unit": "/HPF", "ref_general": "0 - 5"},
            {"name": "Casts", "unit": "/LPF", "ref_general": "Nil / Absent"},
            {"name": "Crystals", "unit": "Obs", "ref_general": "Nil / Absent"}
        ]
    },

    # --- MICROBIOLOGY ---
    {
        "code": "URINE_CULTURE",
        "name": "Urine Culture & Automated Antibiotic Sensitivity (AST)",
        "category_code": "MIC",
        "category_name": "Microbiology",
        "sample_type": "Sterile Midstream Urine",
        "container_type": "Sterile Boric Acid / Leakproof Cup",
        "required_quantity": "15.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 48,
        "base_price_usd": 24.0,
        "base_price_inr": 600.0,
        "description": "Quantifies bacterial colony count (CFU/mL) and provides automated MIC susceptibility panels for clinical antibiotic selection.",
        "preparation_instructions": "Collect before starting any antibiotic therapy. Clean genitals with water before sampling.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Colony Count", "unit": "CFU/mL", "ref_general": "< 10,000"},
            {"name": "Organism Isolated", "unit": "Text", "ref_general": "No significant growth after 48h"},
            {"name": "Antibiotic Sensitivity Panel", "unit": "Panel", "ref_general": "Standard AST Protocol"}
        ]
    },

    # --- IMMUNOLOGY & SEROLOGY ---
    {
        "code": "CRP",
        "name": "C-Reactive Protein (Quantitative hs-CRP)",
        "category_code": "IMM",
        "category_name": "Immunology",
        "sample_type": "Serum",
        "container_type": "Gold Top (SST)",
        "required_quantity": "2.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 6,
        "base_price_usd": 14.0,
        "base_price_inr": 350.0,
        "description": "High-sensitivity turbidimetric acute-phase reactant quantification for systemic inflammation and cardiovascular risk.",
        "preparation_instructions": "No specific fasting required.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "hs-CRP", "unit": "mg/L", "ref_general": "< 1.0 (Low Risk), 1.0-3.0 (Average)", "critical_high": 10.0}
        ]
    },
    {
        "code": "HIV_DUO",
        "name": "HIV 1&2 4th Generation Ag/Ab Duo Screen",
        "category_code": "SER",
        "category_name": "Serology",
        "sample_type": "Serum",
        "container_type": "Gold Top (SST)",
        "required_quantity": "3.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 8,
        "base_price_usd": 22.0,
        "base_price_inr": 550.0,
        "description": "Simultaneous qualitative detection of HIV-1 p24 antigen and antibodies to HIV-1 and HIV-2.",
        "preparation_instructions": "Strictly confidential testing protocol.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "HIV-1 p24 Antigen & HIV 1/2 Antibodies", "unit": "Index / S/CO", "ref_general": "Non-Reactive (< 0.90)"}
        ]
    },
    {
        "code": "DENGUE_COMBO",
        "name": "Dengue Duo Panel (NS1 Antigen + IgM + IgG Antibodies)",
        "category_code": "SER",
        "category_name": "Serology",
        "sample_type": "Serum",
        "container_type": "Gold Top (SST)",
        "required_quantity": "3.0 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 25.0,
        "base_price_inr": 650.0,
        "description": "Rapid and definitive differential diagnosis of acute early dengue (NS1) versus secondary infection (IgM/IgG).",
        "preparation_instructions": "No fasting needed.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Dengue NS1 Antigen", "unit": "Qualitative", "ref_general": "Negative"},
            {"name": "Dengue IgM Antibody", "unit": "Qualitative", "ref_general": "Negative"},
            {"name": "Dengue IgG Antibody", "unit": "Qualitative", "ref_general": "Negative"}
        ]
    },

    # --- COAGULATION ---
    {
        "code": "PT_INR",
        "name": "Prothrombin Time (PT) & International Normalized Ratio (INR)",
        "category_code": "COAG",
        "category_name": "Coagulation",
        "sample_type": "Citrated Plasma (3.2% Sodium Citrate)",
        "container_type": "Light Blue Top Tube",
        "required_quantity": "2.7 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 4,
        "base_price_usd": 12.0,
        "base_price_inr": 300.0,
        "description": "Evaluates the extrinsic coagulation pathway and monitors oral warfarin/anticoagulant therapy.",
        "preparation_instructions": "Inform the phlebotomist of current blood thinners.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Prothrombin Time (Patient)", "unit": "Seconds", "ref_general": "11.0 - 13.5"},
            {"name": "Control Time", "unit": "Seconds", "ref_general": "11.5 - 12.5"},
            {"name": "INR (International Normalized Ratio)", "unit": "Ratio", "ref_general": "0.8 - 1.2", "critical_high": 4.5}
        ]
    },

    # --- CANCER MARKERS ---
    {
        "code": "PSA",
        "name": "Prostate Specific Antigen Total (PSA)",
        "category_code": "TUMOR",
        "category_name": "Tumor / Cancer Markers",
        "sample_type": "Serum",
        "container_type": "Gold Top (SST)",
        "required_quantity": "2.5 mL",
        "fasting_required": False,
        "fasting_hours": 0,
        "turnaround_hours": 8,
        "base_price_usd": 25.0,
        "base_price_inr": 700.0,
        "description": "Primary biomarker for screening and therapeutic monitoring of prostate adenocarcinoma and benign prostatic hyperplasia.",
        "preparation_instructions": "Avoid vigorous cycling or digital rectal exam for 48 hours prior to test.",
        "home_collection_eligible": True,
        "walkin_eligible": True,
        "parameters": [
            {"name": "Total PSA", "unit": "ng/mL", "ref_male": "< 4.0", "ref_female": "N/A", "ref_general": "< 4.0", "critical_high": 10.0}
        ]
    }
]

# Standard Health Packages
MASTER_PACKAGES_CATALOG = [
    {
        "code": "PKG-EXEC-FULL",
        "name": "Spherix Executive Comprehensive Full Body Package",
        "description": "85+ Parameters covering Complete Blood Picture, Liver, Kidney, Lipid, Thyroid, HbA1c, Vitamin D, Vitamin B12, and Complete Urinalysis.",
        "preparation_instructions": "Strict 10 to 12 hours overnight fasting required. Water permitted. First morning urine sample.",
        "fasting_required": True,
        "turnaround_hours": 24,
        "base_price_usd": 120.0,
        "base_price_inr": 2499.0,
        "discount_percent": 55,
        "test_codes": ["CBC", "ESR", "FBS", "HBA1C", "LFT", "KFT", "LIPID", "TSH", "VITD", "VITB12", "URINE_R"],
        "home_collection_eligible": True,
        "walkin_eligible": True
    },
    {
        "code": "PKG-DIABETES-ADV",
        "name": "Advanced Diabetic Metabolic & Glycemic Health Profile",
        "description": "Comprehensive diabetic monitoring: Fasting Sugar, HbA1c with eAG, Lipid Profile, Renal Serum Creatinine with eGFR, and Microscopic Urinalysis.",
        "preparation_instructions": "8 to 10 hours overnight fasting required.",
        "fasting_required": True,
        "turnaround_hours": 12,
        "base_price_usd": 65.0,
        "base_price_inr": 1299.0,
        "discount_percent": 45,
        "test_codes": ["FBS", "HBA1C", "LIPID", "CREATININE", "URINE_R"],
        "home_collection_eligible": True,
        "walkin_eligible": True
    },
    {
        "code": "PKG-HEART-LIPID",
        "name": "Cardio-Vascular & Lipid Risk Assessment",
        "description": "Stratifies cardiovascular disease risk: Extended Lipid Profile, hs-CRP Inflammation marker, Glucose, and Renal Function.",
        "preparation_instructions": "12 hours overnight fasting.",
        "fasting_required": True,
        "turnaround_hours": 12,
        "base_price_usd": 55.0,
        "base_price_inr": 1150.0,
        "discount_percent": 40,
        "test_codes": ["LIPID", "CRP", "FBS", "KFT"],
        "home_collection_eligible": True,
        "walkin_eligible": True
    },
    {
        "code": "PKG-SENIOR-WELL",
        "name": "Senior Citizen Vitality & Organ Health Package",
        "description": "Tailored for adults 50+: CBC, Comprehensive LFT, KFT, Thyroid TSH, Lipid, Vitamin D3, Vitamin B12, and Electrolytes.",
        "preparation_instructions": "Overnight 10-12 hr fasting.",
        "fasting_required": True,
        "turnaround_hours": 24,
        "base_price_usd": 95.0,
        "base_price_inr": 1999.0,
        "discount_percent": 50,
        "test_codes": ["CBC", "ESR", "FBS", "LFT", "KFT", "LIPID", "TSH", "VITD", "VITB12", "URINE_R"],
        "home_collection_eligible": True,
        "walkin_eligible": True
    }
]

def get_category_by_code(code: str) -> Dict[str, Any]:
    return next((c for c in DIAGNOSTIC_MASTER_CATEGORIES if c['code'].upper() == str(code).upper()), None)

def get_test_by_code(code: str) -> Dict[str, Any]:
    return next((t for t in MASTER_TESTS_CATALOG if t['code'].upper() == str(code).upper()), None)

def get_package_by_code(code: str) -> Dict[str, Any]:
    return next((p for p in MASTER_PACKAGES_CATALOG if p['code'].upper() == str(code).upper()), None)
