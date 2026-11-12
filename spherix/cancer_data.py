# ==================== CANCER CARE PORTAL — COMPREHENSIVE ONCOLOGY DATA ====================
"""
Clinically curated oncology monographs, biomarkers, screening protocols, 
treatment pathways, recovery guidelines, and evidence-based clinical references.
"""

CANCER_DATA = {
    "breast-cancer": {
        "name": "Breast Cancer",
        "category": "womens_health",
        "category_label": "Women's Health",
        "icon": "fa-ribbon",
        "image": "https://images.unsplash.com/photo-1579684385127-1ef15d508118?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Malignancy forming in breast ductal or lobular epithelium, predominantly affecting women and occasionally men. Highly treatable when diagnosed in early stages with multimodal precision therapy.",
        "symptoms": [
            "Painless palpable lump or thickening in breast or axilla",
            "Change in breast size, contour, or skin symmetry",
            "Nipple inversion, bloody discharge, or scaling/crusting",
            "Skin dimpling or orange-peel texture (peau d'orange)",
            "Persistent localized breast or chest wall discomfort"
        ],
        "risk_factors": [
            "Advancing age (≥50 years)",
            "First-degree family history of breast or ovarian malignancy",
            "Germline BRCA1, BRCA2, PALB2, or TP53 pathogenic variants",
            "Early menarche (<12 yrs) or late menopause (>55 yrs)",
            "Prolonged combined hormone replacement therapy (HRT)",
            "Dense breast tissue on mammographic evaluation"
        ],
        "prevention": [
            "Annual 3D Digital Mammography starting at age 40 (earlier if high risk)",
            "Clinical breast examination every 6-12 months for high-risk cohorts",
            "Maintain body mass index (BMI) within normal range (18.5 - 24.9)",
            "Engage in ≥150 minutes of weekly moderate aerobic physical activity",
            "Strictly limit or eliminate alcohol consumption"
        ],
        "screening_test": "Annual 3D Digital Mammogram + Supplemental Automated Breast Ultrasound (ABUS) for dense tissue",
        "diagnosis": [
            "Diagnostic Full-Field Digital Mammography with 3D Tomosynthesis",
            "Targeted High-Resolution Breast & Axillary Nodal Ultrasonography",
            "Ultrasound-Guided or Stereotactic Core Needle Biopsy",
            "Immunohistochemistry (IHC) & FISH for ER, PR, HER2, and Ki-67",
            "Contrast-Enhanced Breast MRI for multifocal assessment and BRCA carriers"
        ],
        "treatments": [
            "Breast-conserving surgery (Lumpectomy with Sentinel Lymph Node Biopsy) or Mastectomy",
            "Targeted Monoclonal Antibodies (Trastuzumab + Pertuzumab for HER2-positive tumors)",
            "Adjuvant or Neoadjuvant Chemotherapy (Anthracycline / Taxane protocols)",
            "Endocrine Hormonal Blockade (Tamoxifen or Aromatase Inhibitors for ER+/PR+ tumors)",
            "Whole-Breast Hypofractionated Intensity-Modulated Radiotherapy (IMRT)"
        ],
        "treatment_modalities": {
            "surgery": "Oncoplastic breast-conserving surgery with sentinel node mapping or skin/nipple-sparing mastectomy with immediate autologous/implant reconstruction.",
            "chemotherapy": "Neoadjuvant or adjuvant systemic regimens including AC-T (Doxorubicin, Cyclophosphamide followed by Paclitaxel) or Platinum-based combos for TNBC.",
            "radiotherapy": "Modern hypofractionated tangential 3D-CRT or IMRT delivering precise ionizing dose to chest wall and nodal basins while sparing heart and lungs.",
            "immunotherapy": "Immune checkpoint inhibitors such as Pembrolizumab indicated in high-risk early-stage or metastatic triple-negative breast cancer (TNBC).",
            "targeted_therapy": "Anti-HER2 dual blockade (Trastuzumab, Pertuzumab), antibody-drug conjugates (T-DXd / Enhertu), CDK4/6 inhibitors (Ribociclib, Abemaciclib), and PARP inhibitors (Olaparib).",
            "hormone_therapy": "Tamoxifen for premenopausal patients; Aromatase Inhibitors (Letrozole, Anastrozole, Exemestane) with ovarian suppression for postmenopausal or high-risk patients."
        },
        "recovery": [
            "Post-operative upper extremity physiotherapy to restore shoulder range of motion and prevent axillary web syndrome.",
            "Certified lymphedema compression sleeve fitting and manual lymphatic drainage education.",
            "Dual-energy X-ray absorptiometry (DEXA) scans every 1-2 years during aromatase inhibitor therapy to protect bone mineral density.",
            "Cardio-oncology echocardiographic surveillance during anti-HER2 therapy.",
            "Psycho-oncology survivorship counseling, body image adaptation, and cancer fatigue management."
        ],
        "key_biomarkers": ["HER2/neu (ERBB2)", "Estrogen Receptor (ER)", "Progesterone Receptor (PR)", "Ki-67 Proliferation Index", "BRCA1 / BRCA2 Germline", "PIK3CA Mutation"],
        "common_drugs": ["Trastuzumab (Herceptin)", "Tamoxifen", "Anastrozole", "Paclitaxel", "Pembrolizumab (Keytruda)", "Ribociclib (Kisqali)"],
        "survival_rate_5yr": "91% overall across all stages; >99% for localized early-stage disease",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Breast Cancer (Version 4.2025)",
            "American Society of Clinical Oncology (ASCO) Clinical Practice Guidelines",
            "European Society for Medical Oncology (ESMO) Early Breast Cancer Clinical Practice Guidelines",
            "WHO Classification of Tumours: Breast Tumours, 5th Edition"
        ]
    },

    "lung-cancer": {
        "name": "Lung Cancer (NSCLC / SCLC)",
        "category": "respiratory",
        "category_label": "Thoracic & Respiratory",
        "icon": "fa-lungs",
        "image": "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Primary pulmonary malignancy originating in bronchial or alveolar epithelium, categorized into Non-Small Cell Lung Cancer (NSCLC, ~85%) and Small Cell Lung Cancer (SCLC, ~15%).",
        "symptoms": [
            "Persistent dry or productive cough lasting longer than 3 weeks",
            "Hemoptysis (coughing up blood or blood-tinged sputum)",
            "Progressive dyspnea, wheezing, and pleuritic chest discomfort",
            "Persistent hoarseness, dysphagia, or recurrent bronchitis/pneumonia",
            "Unexplained weight loss (>10 lbs), systemic fatigue, and anorexia"
        ],
        "risk_factors": [
            "Active or heavy secondhand tobacco cigarette/bidi smoking (>20 pack-years)",
            "Indoor radon gas accumulation in residential basements",
            "Occupational inhalation of asbestos, crystalline silica, arsenic, or diesel exhaust",
            "Pre-existing chronic obstructive pulmonary disease (COPD) or pulmonary fibrosis",
            "First-degree family history of thoracic malignancy"
        ],
        "prevention": [
            "Structured smoking cessation and nicotine de-addiction programs",
            "Radon testing and remediation in residential properties",
            "Strict compliance with industrial respiratory protective gear (N95/HEPA)",
            "Annual Low-Dose CT (LDCT) for high-risk smokers aged 50-80 with ≥20 pack-year history"
        ],
        "screening_test": "Annual Low-Dose Computed Tomography (LDCT) Chest Scan for high-risk cohorts",
        "diagnosis": [
            "High-Resolution Contrast-Enhanced Computed Tomography (HRCT) of Chest & Upper Abdomen",
            "Whole-Body 18F-FDG PET-CT for nodal and distant metastatic staging",
            "Endobronchial Ultrasound with Transbronchial Needle Aspiration (EBUS-TBNA) for mediastinal staging",
            "CT-Guided Percutaneous Transthoracic Core Needle Biopsy for peripheral lesions",
            "Comprehensive Next-Generation Sequencing (NGS) 50+ gene thoracic panel including liquid biopsy ctDNA"
        ],
        "treatments": [
            "Video-Assisted Thoracoscopic Surgery (VATS) or Robotic Lobectomy with systematic nodal dissection",
            "Stereotactic Body Radiotherapy (SBRT / SABR) for early-stage medically inoperable disease",
            "Targeted Tyrosine Kinase Inhibitors (Osimertinib, Alectinib, Sotorasib)",
            "Immune Checkpoint Blockade (Pembrolizumab, Nivolumab + Ipilimumab)",
            "Platinum-doublet chemotherapy (Cisplatin/Carboplatin + Pemetrexed or Etoposide)"
        ],
        "treatment_modalities": {
            "surgery": "Minimally invasive VATS or robotic anatomical segmentectomy or lobectomy with mediastinal lymph node sampling.",
            "chemotherapy": "Cisplatin/Carboplatin combined with Pemetrexed (non-squamous NSCLC), Gemcitabine (squamous NSCLC), or Etoposide (SCLC).",
            "radiotherapy": "Image-Guided Radiotherapy (IGRT), 4D-CT respiratory gating, and SBRT delivering ablative doses to localized lung lesions.",
            "immunotherapy": "First-line PD-1/PD-L1 inhibitors (Pembrolizumab, Atezolizumab, Cemiplimab) with or without chemotherapy depending on tumor PD-L1 proportion score.",
            "targeted_therapy": "Third-generation EGFR TKIs (Osimertinib), ALK inhibitors (Alectinib, Brigatinib), ROS1 inhibitors, BRAF/MEK inhibitors, and KRAS G12C blockers.",
            "hormone_therapy": "Not routinely indicated in primary pulmonary carcinomas."
        },
        "recovery": [
            "Pulmonary rehabilitation program including incentive spirometry and progressive aerobic reconditioning.",
            "Chest physical therapy for clearance of bronchial secretions post-resection.",
            "Nutritional hypercaloric supplementation to reverse cancer-induced cachexia.",
            "Serial low-dose surveillance CT scans every 3-6 months for 3 years, then annually."
        ],
        "key_biomarkers": ["EGFR Mutation (Exons 19, 21 L858R)", "ALK Translocation", "ROS1 Fusion", "BRAF V600E", "KRAS G12C", "PD-L1 Tumor Proportion Score (%)"],
        "common_drugs": ["Osimertinib (Tagrisso)", "Pembrolizumab (Keytruda)", "Alectinib (Alecensa)", "Cisplatin", "Pemetrexed", "Etoposide"],
        "survival_rate_5yr": "25% overall; 63% for localized disease detected prior to mediastinal metastasis",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Non-Small Cell Lung Cancer (Version 3.2025)",
            "IASLC Staging Manual in Thoracic Oncology, 9th Edition",
            "ESMO Clinical Practice Guidelines: Metastatic Non-Small Cell Lung Cancer",
            "American College of Chest Physicians (CHEST) Lung Cancer Guidelines"
        ]
    },

    "prostate-cancer": {
        "name": "Prostate Cancer",
        "category": "mens_health",
        "category_label": "Men's Health",
        "icon": "fa-mars",
        "image": "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Adenocarcinoma arising in the glandular epithelium of the prostate peripheral zone, frequently indolent with exceptionally high cure rates when identified through proactive screening.",
        "symptoms": [
            "Urinary hesitancy, weak or interrupted stream, and terminal dribbling",
            "Nocturia (frequent nighttime awakening to urinate)",
            "Sudden urinary urgency or sensation of incomplete bladder emptying",
            "Hematuria (blood in urine) or hematospermia (blood in semen)",
            "Dull ache in lower back, pelvis, hips, or upper thighs (in advanced stages)"
        ],
        "risk_factors": [
            "Age > 50 years (risk increases progressively with each decade)",
            "African ancestry (higher baseline incidence and more aggressive phenotype)",
            "First-degree family history (father or brother diagnosed with prostate cancer)",
            "Germline DNA homologous recombination repair mutations (BRCA2, BRCA1, ATM, CHEK2)",
            "Diet high in saturated animal fats and red meats"
        ],
        "prevention": [
            "Baseline serum Total PSA test and Digital Rectal Examination starting at age 45-50 (age 40 if high risk)",
            "Adherence to a Mediterranean diet rich in dietary lycopene (cooked tomatoes), polyphenols, and green tea",
            "Regular aerobic and resistance physical exercise (≥3 sessions per week)",
            "Maintenance of a healthy waist-to-hip ratio and normal metabolic profile"
        ],
        "screening_test": "Serum Total & Free PSA (Prostate-Specific Antigen) + Digital Rectal Examination (DRE)",
        "diagnosis": [
            "Multiparametric Prostate MRI (mpMRI) with PI-RADS v2.1 scoring",
            "Cognitive or Software-Assisted MRI-Ultrasound Fusion Targeted Transperineal Biopsy",
            "Histopathologic Gleason Grading and ISUP Grade Group classification (1 through 5)",
            "68Ga-PSMA or 18F-DCFPyL PET-CT for high-risk primary staging and recurrence detection",
            "Germline and somatic homologous recombination repair (HRR) gene sequencing"
        ],
        "treatments": [
            "Active Surveillance with serial PSA, mpMRI, and repeat biopsies for Grade Group 1 tumors",
            "Robot-Assisted Laparoscopic Radical Prostatectomy (RARP) with nerve-sparing technique",
            "External Beam Radiation Therapy (IMRT / VMAT) combined with temporary Androgen Deprivation Therapy",
            "High-Dose-Rate (HDR) or Low-Dose-Rate (LDR) Prostate Brachytherapy",
            "Novel Androgen Receptor Pathway Inhibitors (Enzalutamide, Abiraterone, Apalutamide)",
            "177Lu-PSMA-617 Targeted Radioligand Therapy for metastatic castration-resistant prostate cancer"
        ],
        "treatment_modalities": {
            "surgery": "da Vinci Robot-Assisted Laparoscopic Radical Prostatectomy with bilateral pelvic lymphadenectomy and neurovascular bundle preservation.",
            "chemotherapy": "Docetaxel or Cabazitaxel indicated in metastatic hormone-sensitive or castration-resistant prostate cancer.",
            "radiotherapy": "Hypofractionated IMRT/IGRT or stereotactic body radiation (SBRT/CyberKnife) delivering high biological dose to prostate gland.",
            "immunotherapy": "Sipuleucel-T autologous cellular immunotherapy; Pembrolizumab for MSI-H/dMMR metastatic tumors.",
            "targeted_therapy": "PARP inhibitors (Olaparib, Rucaparib, Talazoparib) for tumors harboring homologous recombination repair (BRCA1/2, ATM) mutations.",
            "hormone_therapy": "GnRH agonists (Leuprolide, Goserelin), GnRH antagonists (Relugolix, Degarelix), and androgen synthesis inhibitors (Abiraterone acetate + Prednisone)."
        },
        "recovery": [
            "Structured pelvic floor muscle training (Kegel exercises) initiated prior to surgery to accelerate urinary continence recovery.",
            "Penile rehabilitation protocol utilizing phosphodiesterase-5 inhibitors and vacuum erection devices.",
            "Bone health maintenance with calcium, vitamin D3, and antiresorptive agents (Denosumab / Zoledronic acid) during ADT.",
            "Serial ultrasensitive PSA monitoring every 3 months post-prostatectomy."
        ],
        "key_biomarkers": ["Serum Total & Free PSA (ng/mL)", "Gleason Score / ISUP Grade Group", "PSMA Expression", "BRCA1 / BRCA2 / ATM Mutations", "PI-RADS Score"],
        "common_drugs": ["Leuprolide (Lupron)", "Enzalutamide (Xtandi)", "Abiraterone (Zytiga)", "Docetaxel", "Olaparib (Lynparza)", "Pluvicto (Lu-177 PSMA)"],
        "survival_rate_5yr": "97% overall; >99% when cancer is localized to the prostate or regional pelvic nodes",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Prostate Cancer (Version 1.2025)",
            "AUA / ASTRO / SUO Clinically Localized Prostate Cancer Guideline",
            "EAU - EANM - ESTRO - ESUR - SIOG Guidelines on Prostate Cancer",
            "WHO Classification of Tumours: Urinary and Male Genital Tumours"
        ]
    },

    "colorectal-cancer": {
        "name": "Colorectal Cancer",
        "category": "gastrointestinal",
        "category_label": "Gastrointestinal",
        "icon": "fa-dna",
        "image": "https://images.unsplash.com/photo-1559757175-5700dde675bc?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Malignant neoplasm arising from adenomatous or serrated epithelial polyps lining the inner lumen of the large intestine (colon or rectum). Highly preventable through screening polypectomy.",
        "symptoms": [
            "Persistent change in bowel habits (alternating diarrhea and constipation for >4 weeks)",
            "Occult or frank hematochezia (bright red blood or dark maroon melena in stool)",
            "Unexplained iron-deficiency anemia leading to severe fatigue and pallor",
            "Persistent cramping abdominal pain, bloating, or feeling of incomplete evacuation (tenesmus)",
            "Unintentional weight loss and progressive reduction in caliber of stool (pencil stools)"
        ],
        "risk_factors": [
            "Age ≥ 45 years (with rising incidence in young adults <50 years)",
            "Hereditary cancer syndromes: Lynch syndrome (HNPCC) and Familial Adenomatous Polyposis (FAP)",
            "Longstanding Inflammatory Bowel Disease (Ulcerative Colitis or Crohn's Disease >8-10 years)",
            "Diet heavy in red meat (beef, pork, lamb) and processed meats (bacon, sausages)",
            "Sedentary lifestyle, obesity, heavy alcohol intake, and cigarette smoking"
        ],
        "prevention": [
            "Routine screening optical colonoscopy every 10 years starting at age 45 (earlier if family history)",
            "Annual high-sensitivity Fecal Immunochemical Test (FIT) or stool DNA testing (Cologuard)",
            "Complete endoscopic polypectomy of all detected precancerous adenomas",
            "High-fiber diet (≥30g daily) with ample legumes, cruciferous vegetables, whole grains, and water",
            "Daily aspirin chemoprevention under specialized clinical guidance for elevated cardiovascular/CRC risk"
        ],
        "screening_test": "Optical Colonoscopy every 10 years (or annual Fecal Immunochemical Test) starting at age 45",
        "diagnosis": [
            "Complete Diagnostic Colonoscopy to terminal ileum with multiple mucosal biopsies",
            "Contrast-Enhanced CT Scan of Chest, Abdomen, and Pelvis with triphasic hepatic phase",
            "High-Resolution Pelvic MRI with thin-slice T2 sequences to assess Mesorectal Fascia (MRF) and CRM in rectal cancer",
            "Serum Carcinoembryonic Antigen (CEA) quantitative baseline measurement",
            "Molecular testing: Mismatch Repair (MMR) IHC, MSI by PCR/NGS, KRAS, NRAS, BRAF V600E, and HER2"
        ],
        "treatments": [
            "Minimally invasive laparoscopic or robotic hemicolectomy with complete mesocolic excision (CME)",
            "Total Mesorectal Excision (TME) with sphincter-preserving low anterior resection (LAR) for rectal lesions",
            "Total Neoadjuvant Therapy (TNT) combining short-course radiation and FOLFIRINOX for locally advanced rectal cancer",
            "Adjuvant FOLFOX (Oxaliplatin, 5-FU, Leucovorin) or CAPOX chemotherapy for node-positive stage III disease",
            "Targeted therapies: Anti-VEGF (Bevacizumab) and Anti-EGFR (Cetuximab/Panitumumab for RAS wild-type tumors)",
            "Immune checkpoint blockade (Pembrolizumab / Nivolumab) for MSI-H / dMMR colorectal tumors"
        ],
        "treatment_modalities": {
            "surgery": "Laparoscopic or robotic hemicolectomy or low anterior resection with tension-free colorectal/coloanal anastomosis and temporary protective loop ileostomy if indicated.",
            "chemotherapy": "FOLFOX, CAPOX, or FOLFIRI regimens delivered over 3-6 months based on IDEA risk stratification.",
            "radiotherapy": "Pelvic short-course radiotherapy (25 Gy in 5 fractions) or long-course chemoradiation (50.4 Gy with Capecitabine) for mid-to-low rectal cancer.",
            "immunotherapy": "Immune checkpoint inhibitors showing dramatic pathological complete response rates in dMMR / MSI-High tumors.",
            "targeted_therapy": "Monoclonal antibodies directed against vascular endothelial growth factor (VEGF) or epidermal growth factor receptor (EGFR).",
            "hormone_therapy": "Not indicated in colorectal adenocarcinoma."
        },
        "recovery": [
            "Enhanced Recovery After Surgery (ERAS) pathway: early enteral feeding, multimodal opioid-sparing analgesia, and early ambulation.",
            "Specialized stoma care education and wound-ostomy-continence nursing guidance for patients with temporary/permanent ostomies.",
            "Monitoring for oxaliplatin-induced cold dysesthesia and peripheral sensory neuropathy.",
            "Surveillance colonoscopy at 1 year post-resection, then every 3-5 years based on mucosal findings.",
            "Serum CEA monitoring every 3-6 months for the first 2 years, then every 6 months for years 3-5."
        ],
        "key_biomarkers": ["MSI / dMMR Status", "KRAS / NRAS Exons 2, 3, 4", "BRAF V600E", "HER2 Amplification", "Carcinoembryonic Antigen (CEA)"],
        "common_drugs": ["Oxaliplatin", "Fluorouracil (5-FU)", "Capecitabine (Xeloda)", "Bevacizumab (Avastin)", "Cetuximab (Erbitux)", "Pembrolizumab (Keytruda)"],
        "survival_rate_5yr": "65% overall; 91% if diagnosed at a localized stage before regional lymph node involvement",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Colon Cancer & Rectal Cancer (Version 1.2025)",
            "ESMO Consensus Guidelines for the Management of Patients with Metastatic Colorectal Cancer",
            "American Society of Colon and Rectal Surgeons (ASCRS) Clinical Practice Guidelines",
            "WHO Classification of Tumours: Digestive System Tumours, 5th Edition"
        ]
    },

    "skin-cancer-melanoma": {
        "name": "Melanoma & Skin Cancer",
        "category": "dermatology",
        "category_label": "Dermatology",
        "icon": "fa-sun",
        "image": "https://images.unsplash.com/photo-1559757148-5c350d0d3c56?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "High-grade neoplasm arising from epidermal melanocytes, capable of rapid metastatic dissemination, alongside non-melanoma skin cancers (Basal Cell and Squamous Cell Carcinoma).",
        "symptoms": [
            "Asymmetrical mole or pigmented skin lesion where halves do not match (ABCDE criteria - A)",
            "Border irregularity: scalloped, notched, indistinct, or poorly circumscribed edges (B)",
            "Color variation: multicolored lesions with shades of brown, black, blue, pink, red, or white (C)",
            "Diameter > 6mm (pencil eraser size) or rapidly expanding lesion (D)",
            "Evolving: lesion changing in shape, size, surface elevation, crusting, itching, or bleeding (E)"
        ],
        "risk_factors": [
            "Intermittent intense ultraviolet (UV) radiation and history of blistering sunburns in childhood",
            "Commercial indoor UV tanning bed use",
            "Fitzpatrick skin phototypes I and II (fair complexion, blonde/red hair, blue eyes, tendency to freckle)",
            "Presence of >50 common melanocytic nevi or multiple atypical/dysplastic nevi",
            "Personal or family history of malignant melanoma in first-degree relatives",
            "Chronic immunosuppression (organ transplant recipients, HIV)"
        ],
        "prevention": [
            "Apply broad-spectrum water-resistant sunscreen (SPF 50+ UVA/UVB) 20 minutes prior to sun exposure and reapply every 2 hours",
            "Wear UPF 50+ protective clothing, wide-brimmed hats, and UV-absorbing wrap-around sunglasses",
            "Seek shade during peak solar irradiance hours (10:00 AM to 4:00 PM)",
            "Perform monthly head-to-toe skin self-examinations utilizing full-length and hand mirrors",
            "Undergo annual clinical skin examination with digital dermatoscopic mole mapping"
        ],
        "screening_test": "Annual Full-Body Skin Exam + Digital Dermatoscopy & Total-Body Photomapping",
        "diagnosis": [
            "Polarized and Non-Polarized Digital Dermatoscopy with pattern recognition analysis",
            "Complete Excisional Biopsy with 1 to 2 mm normal tissue margins (punch/shave biopsies through lesion center avoided)",
            "Histopathologic assessment: Breslow tumor thickness (mm), Clark level, mitotic rate, ulceration, and peripheral margins",
            "Sentinel Lymph Node Biopsy (SLNB) for intermediate-thickness lesions (≥0.8mm or <0.8mm with adverse features)",
            "Molecular interrogation: BRAF V600E/V600K mutation analysis, NRAS, and c-KIT mutations"
        ],
        "treatments": [
            "Wide Local Excision (WLE) with 1cm or 2cm margins determined strictly by Breslow tumor depth",
            "Complete Lymph Node Dissection for gross clinically or radiologically involved nodal basins",
            "Dual Immune Checkpoint Inhibition: Nivolumab + Ipilimumab or single-agent PD-1 blockade",
            "Targeted Combination Therapy: BRAF inhibitor + MEK inhibitor (Dabrafenib + Trametinib or Encorafenib + Binimetinib)",
            "Adjuvant Immunotherapy for resected high-risk Stage IIB, IIC, III, and IV disease"
        ],
        "treatment_modalities": {
            "surgery": "Wide local re-excision of biopsy scar with margins tailored to Breslow thickness: in situ (0.5cm), ≤1.0mm (1.0cm), 1.01-2.0mm (1-2cm), >2.0mm (2.0cm).",
            "chemotherapy": "Dacarbazine or Temozolomide historical role largely replaced by modern checkpoint immunotherapies and targeted agents.",
            "radiotherapy": "Adjuvant hypofractionated radiation to primary site or nodal basin in cases of extracapsular extension or desmoplastic melanoma subtype.",
            "immunotherapy": "Anti-PD-1 (Nivolumab, Pembrolizumab) and Anti-CTLA-4 (Ipilimumab) producing durable long-term remissions.",
            "targeted_therapy": "Combination BRAF and MEK inhibitors delivering rapid tumor regression in BRAF V600-mutated melanoma.",
            "hormone_therapy": "Not applicable."
        },
        "recovery": [
            "Wound care and surgical scar optimization utilizing silicone gel sheets and UV barrier dressings.",
            "Dermatologic surveillance visits every 3-6 months for the first 2-3 years, then semi-annually.",
            "Immune-related adverse event (irAE) monitoring: thyroid function tests, liver panels, and early reporting of diarrhea or dyspnea.",
            "Total avoidance of future artificial tanning and strict lifelong sun safety discipline."
        ],
        "key_biomarkers": ["BRAF V600E / V600K Mutation", "NRAS Mutation", "c-KIT Mutation", "PD-L1 Status", "Breslow Depth (mm)"],
        "common_drugs": ["Nivolumab (Opdivo)", "Pembrolizumab (Keytruda)", "Ipilimumab (Yervoy)", "Dabrafenib (Tafinlar)", "Trametinib (Mekinist)"],
        "survival_rate_5yr": "94% overall across all melanoma stages; >99% if detected at Stage I",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Melanoma: Cutaneous (Version 2.2025)",
            "American Academy of Dermatology (AAD) Guidelines of Care for the Management of Primary Cutaneous Melanoma",
            "ESMO Consensus Guidelines on the Diagnosis and Treatment of Melanoma",
            "AJCC Cancer Staging Manual, 8th Edition: Melanoma of the Skin"
        ]
    },

    "leukemia": {
        "name": "Leukemia (AML / ALL / CML / CLL)",
        "category": "hematology",
        "category_label": "Hematology & Blood",
        "icon": "fa-droplet",
        "image": "https://images.unsplash.com/photo-1579154204601-01588f351e67?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Hematologic malignancies originating in bone marrow pluripotent stem cells, disrupting normal erythrocyte, leukocyte, and thrombocyte generation. Divided into acute and chronic myeloid and lymphoid subtypes.",
        "symptoms": [
            "Profound, refractory fatigue, pallor, and progressive weakness (anemia)",
            "Spontaneous petechiae, purpura, ecchymosis, or mucosal bleeding (thrombocytopenia)",
            "Recurrent, severe bacterial or opportunistic infections and unexplained febrile spikes (neutropenia)",
            "Painless cervical, axillary, or inguinal lymphadenopathy",
            "Hepatosplenomegaly causing left upper quadrant fullness and early satiety",
            "Bone and joint deep aching pain, especially in long bones and sternum"
        ],
        "risk_factors": [
            "Prior exposure to alkylating chemotherapy or topoisomerase II inhibitors (therapy-related myeloid neoplasms)",
            "High-dose ionizing radiation exposure",
            "Chronic occupational contact with benzene and industrial petrochemical solvents",
            "Congenital chromosomal anomalies (Down syndrome / Trisomy 21, Fanconi anemia, Bloom syndrome)",
            "Pre-existing clonal hematopoiesis of indeterminate potential (CHIP) or myelodysplastic syndromes (MDS)"
        ],
        "prevention": [
            "Minimization of benzene, toluene, and industrial aromatic hydrocarbon occupational exposure",
            "Strict adherence to occupational ionizing radiation shielding protocols",
            "Prompt comprehensive hematologic evaluation of unexplained chronic cytopenias or leukocytosis"
        ],
        "screening_test": "Complete Blood Count (CBC) with Differential + Automated Peripheral Blood Smear Examination",
        "diagnosis": [
            "Automated Complete Blood Count (CBC) revealing leukocytosis, cytopenias, or blast cells",
            "Manual Peripheral Blood Smear stained with Wright-Giemsa for blast morphological assessment",
            "Bone Marrow Aspiration and Core Trephine Biopsy from posterior superior iliac crest",
            "Multiparameter Flow Cytometry Immunophenotyping (CD34, CD33, CD19, CD20, CD3, etc.)",
            "Cytogenetics / Karyotyping and Fluorescent In Situ Hybridization (FISH) for translocation detection",
            "Myeloid / Lymphoid Next-Generation Sequencing (NGS) gene mutation panel (FLT3, NPM1, CEBPA, TP53, IDH1/2)"
        ],
        "treatments": [
            "Intensive Induction Chemotherapy ('7+3' Cytarabine + Daunorubicin) for acute myeloid leukemia",
            "Targeted Tyrosine Kinase Inhibitors (Imatinib, Dasatinib, Ponatinib) for BCR-ABL1 positive CML/ALL",
            "BCL-2 Inhibitors (Venetoclax) combined with hypomethylating agents (Azacitidine) for unfit AML/CLL",
            "Allogeneic Hematopoietic Stem Cell Transplantation (allo-HSCT) for intermediate/adverse risk acute leukemias",
            "Chimeric Antigen Receptor (CAR) T-Cell Cellular Immunotherapy targeting CD19 (Tisagenlecleucel)",
            "Bruton's Tyrosine Kinase (BTK) Inhibitors (Ibrutinib, Acalabrutinib, Zanubrutinib) for CLL"
        ],
        "treatment_modalities": {
            "surgery": "Bone marrow harvest and central venous access (Port-a-Cath / Hickman catheter insertion); splenectomy rarely indicated.",
            "chemotherapy": "High-dose consolidation cytarabine (HiDAC), multi-agent ALL induction protocols with intrathecal methotrexate prophylaxis.",
            "radiotherapy": "Total Body Irradiation (TBI) utilized as a conditioning modality prior to allogeneic stem cell transplantation.",
            "immunotherapy": "Bi-specific T-cell engagers (Blinatumomab), antibody-drug conjugates (Gemtuzumab ozogamicin), and autologous CAR-T cell infusions.",
            "targeted_therapy": "FLT3 inhibitors (Midostaurin, Gilteritinib), IDH1/2 inhibitors (Ivosidenib, Enasidenib), and BCR-ABL TKIs.",
            "hormone_therapy": "Corticosteroids (Dexamethasone, Prednisone) form an essential component of lymphoid leukemia protocols."
        },
        "recovery": [
            "HEPA-filtered positive-pressure protective isolation during periods of severe post-induction neutropenia.",
            "Antimicrobial prophylaxis (Fluconazole/Posaconazole, Acyclovir, Trimethoprim-Sulfamethoxazole).",
            "Graft-versus-Host Disease (GVHD) surveillance and immunosuppression management post-allogeneic transplant.",
            "Regular monitoring of minimal residual disease (MRD) by high-sensitivity flow cytometry or digital droplet PCR."
        ],
        "key_biomarkers": ["Philadelphia Chromosome (BCR-ABL1)", "FLT3-ITD / FLT3-TKD", "NPM1 Mutation", "TP53 Mutation", "IDH1 / IDH2", "Flow Cytometry Blasts %"],
        "common_drugs": ["Imatinib (Gleevec)", "Venetoclax (Venclexta)", "Azacitidine", "Cytarabine", "Gilteritinib (Xospata)", "Acalabrutinib (Calquence)"],
        "survival_rate_5yr": "66% overall across all leukemia types; >88% for CLL and >90% for CML with modern TKIs",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Acute Myeloid Leukemia & Chronic Lymphocytic Leukemia",
            "European LeukemiaNet (ELN) Recommendations for Diagnosis and Management of AML",
            "World Health Organization Classification of Haematolymphoid Tumours, 5th Edition",
            "ASH Guidelines for Treatment of Newly Diagnosed Acute Myeloid Leukemia"
        ]
    },

    "pancreatic-cancer": {
        "name": "Pancreatic Adenocarcinoma",
        "category": "gastrointestinal",
        "category_label": "Gastrointestinal",
        "icon": "fa-flask-vial",
        "image": "https://images.unsplash.com/photo-1576086213369-97a306d36557?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Highly aggressive malignancy predominantly arising in the ductal exocrine epithelium of the pancreatic head, body, or tail. Characterized by dense desmoplastic stroma and early systemic micrometastasis.",
        "symptoms": [
            "Painless, progressive obstructive jaundice (yellowing of sclera and skin) with dark cola urine and pale clay stools",
            "Midepigastric gnawing abdominal pain classically radiating through to the spine, worse when supine",
            "New-onset, atypical type 2 diabetes mellitus in non-obese individuals older than 50 years",
            "Profound anorexia, severe early satiety, and rapid involuntary cachexia (weight loss)",
            "Unexplained superficial migratory thrombophlebitis (Trousseau syndrome)"
        ],
        "risk_factors": [
            "Chronic pancreatitis and hereditary pancreatitis (PRSS1 gene mutations)",
            "Active tobacco smoking (responsible for ~20-25% of cases)",
            "Germline genetic alterations: BRCA2, PALB2, CDKN2A (Familial Atypical Mole Melanoma), ATM, and STK11 (Peutz-Jeghers)",
            "Pre-existing mucinous cystic neoplasms and Intraductal Papillary Mucinous Neoplasms (IPMN)",
            "Longstanding type 2 diabetes and adult obesity"
        ],
        "prevention": [
            "Complete cessation of all cigarette and tobacco products",
            "Surveillance protocol utilizing annual Endoscopic Ultrasound (EUS) and magnetic resonance cholangiopancreatography (MRCP) for hereditary carriers",
            "Limitation of saturated dietary lipids, processed meats, and alcohol consumption"
        ],
        "screening_test": "Endoscopic Ultrasound (EUS) & Contrast Pancreatic-Protocol MRI/MRCP for high-risk hereditary cohorts",
        "diagnosis": [
            "Pancreatic-Protocol Triphasic Thin-Slice Contrast CT Scan (Arterial, Pancreatic parenchymal, and Venous phases)",
            "Magnetic Resonance Cholangiopancreatography (MRCP) with high-resolution secretin enhancement",
            "Endoscopic Ultrasound (EUS) with Fine Needle Biopsy (FNB) utilizing ProCore or Acquire needles",
            "Serum CA 19-9 Quantitative Carbohydrate Antigen level (baseline and post-therapy kinetics)",
            "Germline and somatic NGS testing for homologous recombination deficiency (BRCA1/2, PALB2) and KRAS mutations"
        ],
        "treatments": [
            "Pancreaticoduodenectomy (Whipple Procedure) for tumors localized to pancreatic head with vascular reconstruction",
            "Distal Pancreatectomy with en-bloc Splenectomy for tumors of the pancreatic body and tail",
            "Neoadjuvant and Adjuvant FOLFIRINOX (5-FU, Leucovorin, Irinotecan, Oxaliplatin) chemotherapy",
            "Gemcitabine + Nab-Paclitaxel (Abraxane) systemic regimen",
            "Stereotactic Body Radiotherapy (SBRT) for borderline resectable or locally advanced disease",
            "PARP Inhibitor Maintenance (Olaparib) for patients with germline BRCA mutations following platinum induction"
        ],
        "treatment_modalities": {
            "surgery": "Classic or pylorus-preserving Whipple procedure with standardized retroperitoneal lymphadenectomy and superior mesenteric artery (SMA) adventitial dissection.",
            "chemotherapy": "Modified FOLFIRINOX for fit patients (ECOG 0-1) or Gemcitabine + Nab-Paclitaxel as first-line standard.",
            "radiotherapy": "High-precision SBRT delivering ablative doses to retroperitoneal margins while sparing adjacent duodenum and stomach.",
            "immunotherapy": "Pembrolizumab reserved exclusively for the rare subset (<1%) harboring MSI-H / dMMR alterations.",
            "targeted_therapy": "PARP inhibitors (Olaparib) in germline BRCA1/2 carriers; KRAS G12D/G12V inhibitors in clinical trial evaluation.",
            "hormone_therapy": "Not applicable."
        },
        "recovery": [
            "Exocrine pancreatic enzyme replacement therapy (PERT - Pancrelipase) administered with all meals and snacks to correct steatorrhea.",
            "Intensive blood glucose monitoring and insulin optimization following total or partial pancreatectomy.",
            "Nutritional rehabilitation with high-protein, medium-chain triglyceride supplementation.",
            "Comprehensive pain management including early CT-guided or EUS-guided celiac plexus neurolysis."
        ],
        "key_biomarkers": ["Serum CA 19-9", "KRAS Mutation Status (G12D, G12V)", "BRCA1 / BRCA2 Germline", "PALB2 Mutation", "MSI Status"],
        "common_drugs": ["Gemcitabine", "Nab-Paclitaxel (Abraxane)", "Olaparib (Lynparza)", "Oxaliplatin", "Irinotecan", "Pancrelipase (Creon)"],
        "survival_rate_5yr": "13% overall across all presentations; 44% when localized and completely resected with negative margins",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Pancreatic Adenocarcinoma (Version 1.2025)",
            "ASCO Clinical Practice Guideline: Locally Advanced and Metastatic Pancreatic Cancer",
            "ESMO Clinical Practice Guidelines: Cancer of the Pancreas",
            "International Association of Pancreatology (IAP) Evidence-Based Guidelines on IPMN"
        ]
    },

    "ovarian-cancer": {
        "name": "Ovarian & GYN Oncology",
        "category": "womens_health",
        "category_label": "Women's Health",
        "icon": "fa-venus",
        "image": "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "High-grade serous epithelial ovarian, fallopian tube, and primary peritoneal carcinomas. Frequently presents with insidious peritoneal carcinomatosis due to lack of an anatomic barrier.",
        "symptoms": [
            "Persistent abdominal distension, severe bloating, and increased abdominal girth (ascites)",
            "Early satiety and difficulty finishing small portions of meals",
            "Pelvic pressure or constant dull abdominal discomfort",
            "Urinary urgency, frequency, and changes in bowel habits without gastrointestinal etiology",
            "Unexplained postmenopausal vaginal spotting or bleeding"
        ],
        "risk_factors": [
            "Germline pathogenic variants in BRCA1 (39-44% lifetime risk) or BRCA2 (11-17% lifetime risk)",
            "Lynch syndrome (hereditary non-polyposis colorectal cancer - MLH1, MSH2, MSH6, PMS2)",
            "Nulliparity (never having carried a full-term pregnancy) or late age at first birth (>35 yrs)",
            "Personal history of severe pelvic endometriosis",
            "Postmenopausal hormone replacement therapy use >5 years"
        ],
        "prevention": [
            "Risk-reducing bilateral salpingo-oophorectomy (RRSO) between ages 35-40 for BRCA1, 40-45 for BRCA2 carriers",
            "Combined oral contraceptive pill use: ≥5 years of use confers up to a 50% lifetime risk reduction",
            "Genetic risk evaluation and comprehensive multi-gene panel testing for all first-degree relatives of affected patients",
            "Opportunistic bilateral salpingectomy during routine benign pelvic surgeries (e.g., tubal ligation or hysterectomy)"
        ],
        "screening_test": "Transvaginal Ultrasound (TVUS) + Serum CA-125 Quantitative Marker in high-risk hereditary cohorts",
        "diagnosis": [
            "High-Resolution Pelvic and Transvaginal Ultrasound (TVUS) with spectral color Doppler analysis",
            "Multiphasic Contrast-Enhanced CT Scan of Abdomen and Pelvis for peritoneal implants and omental caking",
            "Serum CA-125 and HE4 with computation of Risk of Ovarian Malignancy Algorithm (ROMA)",
            "Diagnostic Laparoscopy with Fagotti score calculation to assess surgical resectability",
            "Comprehensive Molecular Testing: Germline and Somatic BRCA1/2, and Homologous Recombination Deficiency (HRD) score"
        ],
        "treatments": [
            "Maximal Cytoreductive Debulking Surgery aiming for complete gross resection (R0, no residual visible disease)",
            "Hyperthermic Intraperitoneal Chemotherapy (HIPEC) with Cisplatin administered during primary or interval debulking",
            "Intravenous / Intraperitoneal Carboplatin + Paclitaxel systemic chemotherapy (6 cycles)",
            "PARP Inhibitor Maintenance (Olaparib, Niraparib) following response to platinum-based chemotherapy",
            "Anti-angiogenic Monoclonal Antibody therapy (Bevacizumab) in high-risk Stage III/IV presentations"
        ],
        "treatment_modalities": {
            "surgery": "Total abdominal hysterectomy, bilateral salpingo-oophorectomy, complete omentectomy, pelvic/paraaortic lymphadenectomy, and peritonectomy.",
            "chemotherapy": "Carboplatin (AUC 5-6) plus Paclitaxel (175 mg/m2) every 3 weeks, or dose-dense weekly paclitaxel regimens.",
            "radiotherapy": "Rarely employed in primary management; palliative stereotactic radiation utilized for focal symptomatic recurrence.",
            "immunotherapy": "Immune checkpoint blockade currently being investigated in combination with PARP inhibitors and anti-angiogenics.",
            "targeted_therapy": "PARP inhibitors delivering synthetic lethality in tumors with deficient homologous recombination repair DNA machinery.",
            "hormone_therapy": "Endocrine therapies (Tamoxifen, Letrozole) effective in recurrent low-grade serous or granulosa cell tumors."
        },
        "recovery": [
            "Post-operative venous thromboembolism (VTE) chemoprophylaxis with low-molecular-weight heparin for 28 days post-laparotomy.",
            "Aggressive bowel regimen and nutritional management following extensive bowel resections or stoma creation.",
            "Monitoring for PARP inhibitor-associated hematologic toxicity (anemia, thrombocytopenia) and secondary myelodysplasia.",
            "Surveillance pelvic exams and serum CA-125 monitoring every 3 months for the first 2 years, then every 6 months."
        ],
        "key_biomarkers": ["Serum CA-125", "Human Epididymis Protein 4 (HE4)", "BRCA1 / BRCA2 Mutations", "Homologous Recombination Deficiency (HRD)", "TP53 Mutation"],
        "common_drugs": ["Carboplatin", "Paclitaxel (Taxol)", "Olaparib (Lynparza)", "Niraparib (Zejula)", "Bevacizumab (Avastin)", "Doxorubicin (Liposomal)"],
        "survival_rate_5yr": "51% overall; >93% when diagnosed at Stage I confined strictly to the ovarian cortex",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Ovarian Cancer (Version 1.2025)",
            "ESMO - ESGO Consensus Conference Recommendations on Ovarian Cancer",
            "SGO Clinical Practice Statement: Screening and Prevention of Ovarian Cancer",
            "WHO Classification of Tumours: Female Genital Tumours, 5th Edition"
        ]
    },

    "lymphoma": {
        "name": "Lymphoma (Hodgkin & Non-Hodgkin)",
        "category": "hematology",
        "category_label": "Hematology & Blood",
        "icon": "fa-shield-halved",
        "image": "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Diverse clonal neoplasms originating in mature B, T, or Natural Killer (NK) lymphocytes within lymph nodes, spleen, bone marrow, or extranodal lymphoid tissues. Divided into Classical Hodgkin Lymphoma and Non-Hodgkin Lymphoma (NHL).",
        "symptoms": [
            "Painless, rubbery enlargement of lymph nodes in neck, supra-clavicular fossa, axilla, or groin",
            "Systemic B-Symptoms: Drenching night sweats requiring change of bed linens, unexplained fever >38°C, and involuntary weight loss >10% in 6 months",
            "Severe generalized pruritus (itching) without primary dermatologic eruption",
            "Persistent dry cough, substernal chest fullness, or facial swelling (superior vena cava compression from mediastinal adenopathy)",
            "Alcohol-induced lymph node pain (pathognomonic for Hodgkin lymphoma)"
        ],
        "risk_factors": [
            "Chronic viral infections: Epstein-Barr Virus (EBV), Hepatitis C Virus (HCV), Human T-cell Leukemia Virus (HTLV-1), and HIV",
            "Chronic bacterial colonization: Helicobacter pylori (associated with gastric MALT lymphoma)",
            "Long-term medical immunosuppression (post-organ transplantation, autoimmune therapies)",
            "Pre-existing autoimmune disorders: Rheumatoid Arthritis, Sjögren's Syndrome, Hashimoto's thyroiditis",
            "Environmental contact with agricultural organophosphate pesticides and phenoxy herbicides"
        ],
        "prevention": [
            "Eradication of active Helicobacter pylori infection with quadruple antibiotic therapy to prevent gastric MALT lymphoma",
            "Antiviral treatment of chronic Hepatitis C infection",
            "Safe chemical handling and personal protective equipment for agricultural workers",
            "Prompt surgical excisional biopsy evaluation of any painless lymph node persisting >4 weeks"
        ],
        "screening_test": "Excisional Whole Lymph Node Biopsy + Whole-Body 18F-FDG PET-CT Lugano Staging",
        "diagnosis": [
            "Complete Excisional Whole Lymph Node Biopsy (FNA and core biopsies are discouraged due to disruption of nodal architecture)",
            "Histopathology with Reed-Sternberg cell identification in Classical Hodgkin Lymphoma",
            "Immunohistochemistry Panel: CD20, CD3, CD30, CD15, PAX5, BCL2, BCL6, MYC, and Ki-67",
            "Whole-Body 18F-FDG PET-CT for Lugano classification staging and Deauville 5-point response grading",
            "Unilateral Bone Marrow Biopsy (not required if PET-CT shows clear bone marrow involvement in DLBCL/Hodgkin)"
        ],
        "treatments": [
            "ABVD Chemotherapy regimen (Doxorubicin, Bleomycin, Vinblastine, Dacarbazine) for Hodgkin Lymphoma",
            "R-CHOP Immunochemotherapy (Rituximab, Cyclophosphamide, Doxorubicin, Vincristine, Prednisone) for DLBCL",
            "Involved-Site Radiotherapy (ISRT) delivering targeted dose to original gross nodal sites",
            "Antibody-Drug Conjugates: Brentuximab Vedotin (anti-CD30) and Polatuzumab Vedotin (anti-CD79b)",
            "Autologous Stem Cell Transplantation (ASCT) for relapsed/refractory chemosensitive aggressive NHL",
            "Chimeric Antigen Receptor (CAR) T-Cell Therapies (Axicabtagene ciloleucel, Tisagenlecleucel, Lisocabtagene)"
        ],
        "treatment_modalities": {
            "surgery": "Diagnostic excisional lymph node biopsy; therapeutic surgical resection rarely indicated.",
            "chemotherapy": "Curative frontline multi-agent regimens adapted to histology, age, and International Prognostic Index (IPI).",
            "radiotherapy": "Modern deep-inspiration breath-hold ISRT minimizing radiation exposure to breast and cardiac tissues.",
            "immunotherapy": "Anti-CD20 monoclonal antibodies (Rituximab, Obinutuzumab) and immune checkpoint inhibitors (Nivolumab, Pembrolizumab).",
            "targeted_therapy": "BTK inhibitors (Zanubrutinib), BCL-2 inhibitors (Venetoclax), and EZH2 inhibitors.",
            "hormone_therapy": "Systemic corticosteroids (Prednisone, Dexamethasone) with direct lympholytic action."
        },
        "recovery": [
            "Pulmonary function testing (DLCO) surveillance for bleomycin-induced pneumonitis.",
            "Cardio-oncology follow-up and periodic echocardiography to assess anthracycline cumulative cardiotoxicity.",
            "Annual breast MRI screening for female patients who received mantle radiotherapy under age 30.",
            "Endocrine screening for hypothyroidism in patients who received cervical or mediastinal radiation.",
            "Immunization updates with non-live vaccines post-chemotherapy and B-cell reconstitution."
        ],
        "key_biomarkers": ["CD20 Expression", "CD30 / CD15", "MYC, BCL2, BCL6 Rearrangements (Double-Hit)", "Ki-67 Proliferation Index", "Deauville PET Score"],
        "common_drugs": ["Rituximab (Rituxan)", "Brentuximab Vedotin (Adcetris)", "Polatuzumab Vedotin", "Doxorubicin", "Bleomycin", "Axicabtagene (Yescarta)"],
        "survival_rate_5yr": "89% for Hodgkin Lymphoma; 74% across all Non-Hodgkin Lymphoma subtypes",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas & Hodgkin Lymphoma (Version 1.2025)",
            "Lugano Classification Criteria for Initial Staging and Response Assessment in Hodgkin and Non-Hodgkin Lymphoma",
            "ESMO Clinical Practice Guidelines for Newly Diagnosed and Relapsed Hodgkin Lymphoma",
            "WHO Classification of Tumours: Haematolymphoid Tumours, 5th Edition"
        ]
    },

    "brain-tumor-glioblastoma": {
        "name": "Brain & CNS Tumors (Glioblastoma)",
        "category": "neurology",
        "category_label": "Neurology & CNS",
        "icon": "fa-brain",
        "image": "https://images.unsplash.com/photo-1559757175-0eb30cd8c063?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Primary central nervous system malignancies including IDH-wildtype Glioblastoma (WHO Grade 4 Astrocytoma), marked by profound invasiveness, microvascular proliferation, and blood-brain barrier heterogeneity.",
        "symptoms": [
            "New-onset, unrelenting morning headaches exacerbated by Valsalva maneuvers, coughing, or bending over",
            "Nausea and projectile vomiting in the morning without gastrointestinal distress (increased ICP)",
            "Focal neurological deficits: hemiparesis, facial asymmetry, sensory loss, or visual field cuts (hemianopia)",
            "Unprovoked epileptic seizures (focal motor, sensory, or generalized tonic-clonic) in adult patients",
            "Progressive cognitive decline, personality changes, memory deficits, and expressive/receptive dysphasia"
        ],
        "risk_factors": [
            "High-dose ionizing cranial radiation exposure (e.g., prior treatment for childhood leukemia or tinea capitis)",
            "Rare hereditary tumor syndromes: Li-Fraumeni syndrome (TP53), Neurofibromatosis Type 1 and 2 (NF1/2), Turcot syndrome",
            "Peak incidence between 55 and 75 years of age",
            "No proven link to cellular telephone radiation, smoking, or residential power lines in rigorous epidemiologic trials"
        ],
        "prevention": [
            "Avoidance of unnecessary high-dose head and neck medical ionizing radiation",
            "Immediate, comprehensive neuroimaging workup for any adult presenting with new-onset unprovoked seizures or persistent progressive headaches"
        ],
        "screening_test": "Brain Magnetic Resonance Imaging (MRI) with and without Gadolinium Contrast + Perfusion Protocol",
        "diagnosis": [
            "High-Resolution 3T Brain MRI with Axial, Coronal, and Sagittal T1 pre/post-contrast, T2, FLAIR, and DWI sequences",
            "Magnetic Resonance Perfusion (DSC-MRI) to assess relative cerebral blood volume (rCBV) and tumor neoangiogenesis",
            "Magnetic Resonance Spectroscopy (MRS) evaluating Choline / Creatine and Choline / NAA ratios",
            "Neuronavigation-guided craniotomy with maximal safe tumor resection or stereotactic needle biopsy",
            "Neuropathology with WHO 2021 integrated diagnosis: IDH1/2 mutation status, 1p/19q co-deletion, MGMT promoter methylation, and TERT promoter mutation"
        ],
        "treatments": [
            "Maximal Safe Surgical Resection utilizing intraoperative 5-ALA fluorescence guidance (Gliolan) and functional cortical mapping",
            "Stupp Protocol: Concurrent Radiotherapy (60 Gy in 30 fractions) with daily Temozolomide (75 mg/m2)",
            "Adjuvant Temozolomide (150-200 mg/m2 for 5 days every 28 days) for 6 to 12 cycles",
            "Tumor Treating Fields (Optune TTFields): Low-intensity alternating electrical fields applied via scalp arrays",
            "Targeted Anti-VEGF Monoclonal Antibody (Bevacizumab) for symptomatic recurrence and steroid-sparing radiation necrosis management",
            "Stereotactic Radiosurgery (CyberKnife / Gamma Knife) for localized focal recurrences"
        ],
        "treatment_modalities": {
            "surgery": "Awake craniotomy with intraoperative neuro-monitoring for tumors in eloquent speech and motor cortices.",
            "chemotherapy": "Lipophilic alkylating agents (Temozolomide, Lomustine/CCNU) capable of penetrating the blood-brain barrier.",
            "radiotherapy": "Volumetric Modulated Arc Therapy (VMAT) with sub-millimeter stereotactic immobilization masks.",
            "immunotherapy": "Dendritic cell vaccines, oncolytic viruses, and checkpoint inhibitors under active neuro-oncology trial evaluation.",
            "targeted_therapy": "BRAF V600E inhibitors (Dabrafenib + Trametinib) for rare BRAF-mutated glioblastomas; EGFRvIII and NTRK inhibitors.",
            "hormone_therapy": "Dexamethasone high-potency glucocorticoid therapy for rapid control of vasogenic peritumoral cerebral edema."
        },
        "recovery": [
            "Neuro-rehabilitation program including specialized occupational therapy, speech language pathology, and cognitive retraining.",
            "Prophylactic antiepileptic drug (AED) management (Levetiracetam / Lacosamide) with therapeutic drug monitoring.",
            "Pneumocystis jirovecii pneumonia (PCP) prophylaxis with trimethoprim-sulfamethoxazole during concurrent chemoradiation and steroid therapy.",
            "Brain MRI surveillance every 2-3 months to distinguish true progression from pseudoprogression utilizing RANO criteria."
        ],
        "key_biomarkers": ["MGMT Promoter Methylation Status", "IDH1 R132H / IDH2 Mutations", "1p/19q Co-deletion", "TERT Promoter Mutation", "EGFR Amplification / EGFRvIII"],
        "common_drugs": ["Temozolomide (Temodar)", "Bevacizumab (Avastin)", "Lomustine (CCNU)", "Dexamethasone", "Levetiracetam (Keppra)"],
        "survival_rate_5yr": "5-Year Overall Survival ~7% for IDH-wildtype Glioblastoma; >60% for low-grade IDH-mutant 1p/19q co-deleted oligodendrogliomas",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Central Nervous System Cancers (Version 1.2025)",
            "WHO Classification of Tumours: Central Nervous System Tumours, 5th Edition (2021)",
            "EANO Guidelines on the Diagnosis and Treatment of Diffuse Gliomas of Adulthood",
            "RANO Criteria for Response Assessment in Neuro-Oncology"
        ]
    },

    "cervical-cancer": {
        "name": "Cervical Cancer",
        "category": "womens_health",
        "category_label": "Women's Health",
        "icon": "fa-female",
        "image": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Malignant neoplasm arising from the squamocolumnar transformation zone of the uterine cervix, overwhelmingly caused by persistent infection with high-risk human papillomavirus (HPV) genotypes.",
        "symptoms": [
            "Abnormal vaginal bleeding between menses or after sexual intercourse (post-coital bleeding)",
            "Post-menopausal vaginal bleeding or unusually heavy and prolonged menstrual periods",
            "Persistent, foul-smelling, or watery vaginal discharge tinged with blood",
            "Deep pelvic pain or lower back aching radiating down lower extremities",
            "Dysuria, hematuria, or rectal tenesmus in locally advanced disease"
        ],
        "risk_factors": [
            "Persistent high-risk Human Papillomavirus (HPV Types 16, 18, 31, 33, 45, 52, 58) infection",
            "Lack of routine Pap smear / HPV DNA screening",
            "Immunosuppression (HIV infection, solid organ transplant immunosuppression)",
            "Active cigarette smoking (doubles cervical cancer risk by concentrating carcinogens in cervical mucus)",
            "Early age at first sexual intercourse and multiple high-risk sexual partners",
            "Long-term use of combined oral contraceptives (>5 years without screening)"
        ],
        "prevention": [
            "Prophylactic 9-valent HPV Vaccination (Gardasil 9) recommended for girls and boys aged 9-14 years (catch-up to age 26-45)",
            "Routine Cervical Screening starting at age 21 with Pap smear, and HPV DNA co-testing every 5 years from age 25 to 65",
            "Prompt colposcopic evaluation and treatment of Cervical Intraepithelial Neoplasia (CIN 2/3) via LEEP or cold-knife conization",
            "Smoking cessation and barrier contraception (condom use) to reduce HPV transmission"
        ],
        "screening_test": "High-Risk HPV DNA Test + Liquid-Based Cytology (Pap Smear) co-testing every 3-5 years",
        "diagnosis": [
            "Diagnostic Colposcopy with acetic acid (3-5%) and Lugol's iodine application",
            "Targeted Cervical Punch Biopsies and Endocervical Curettage (ECC)",
            "Diagnostic Cold Knife Cone Biopsy (Conization) or Loop Electrosurgical Excision Procedure (LEEP)",
            "Pelvic Magnetic Resonance Imaging (MRI) with contrast to assess stromal invasion and parametrial extension",
            "Whole-Body 18F-FDG PET-CT for pelvic and para-aortic lymph node metastasis staging"
        ],
        "treatments": [
            "Radical Hysterectomy (Wertheim-Meigs operation) with bilateral pelvic lymphadenectomy for early-stage disease (FIGO IA2 - IB2)",
            "Radical Trachelectomy (fertility-sparing cervical excision with pelvic lymphadenectomy) for young women with small tumors",
            "Concurrent Chemoradiotherapy (CCRT): External beam radiation (EBRT) with concurrent weekly Cisplatin, followed by Image-Guided Adaptive Brachytherapy (IGABT)",
            "High-Dose-Rate (HDR) Intracavitary / Interstitial Brachytherapy for curative local tumor eradication",
            "Combination Immunotherapy (Pembrolizumab) + Platinum Chemotherapy + Bevacizumab for metastatic or recurrent PD-L1 positive disease"
        ],
        "treatment_modalities": {
            "surgery": "Open or robotic radical abdominal hysterectomy with resection of upper 2-3 cm of vagina and parametrial tissues.",
            "chemotherapy": "Weekly Cisplatin (40 mg/m2) radiosensitizing chemotherapy during definitive radiotherapy.",
            "radiotherapy": "Whole-pelvic IMRT (45-50 Gy) followed by MRI-guided 3D brachytherapy delivering >85 Gy total equivalent dose to tumor.",
            "immunotherapy": "Pembrolizumab approved in combination with chemotherapy for persistent, recurrent, or metastatic cervical cancer.",
            "targeted_therapy": "Bevacizumab (anti-VEGF) monoclonal antibody prolonging overall survival when added to chemotherapy.",
            "hormone_therapy": "Not applicable."
        },
        "recovery": [
            "Vaginal dilator therapy and topical estrogen counseling initiated post-brachytherapy to prevent vaginal stenosis.",
            "Monitoring and management of radiation enteritis and proctitis with dietary modifications.",
            "Bladder dysfunction management (transient urinary retention) following radical parametrial resection.",
            "Pelvic examination and Pap smear every 3 months for the first 2 years, then every 6 months for years 3-5."
        ],
        "key_biomarkers": ["High-Risk HPV Genotype (16/18/45)", "PD-L1 Combined Positive Score (CPS)", "p16INK4a Overexpression", "MSI / TMB Status"],
        "common_drugs": ["Cisplatin", "Paclitaxel", "Pembrolizumab (Keytruda)", "Bevacizumab (Avastin)", "Topotecan", "Tisotumab Vedotin (Tivdak)"],
        "survival_rate_5yr": "67% overall across all stages; >92% when diagnosed in early stages (FIGO Stage I)",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Cervical Cancer (Version 1.2025)",
            "FIGO Committee on Gynecologic Oncology: Staging and Treatment of Cervical Cancer",
            "ESGO - ESTRO - ESP Guidelines for the Management of Cervical Cancer",
            "WHO Global Strategy to Accelerate the Elimination of Cervical Cancer as a Public Health Problem"
        ]
    },

    "oral-cancer": {
        "name": "Oral & Head & Neck Cancer",
        "category": "head_neck",
        "category_label": "Head, Neck & Oral",
        "icon": "fa-teeth-open",
        "image": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Squamous cell carcinomas arising from mucosal lining of lips, oral tongue, floor of mouth, buccal mucosa, gingiva, and oropharynx. Highly prevalent in South Asia due to tobacco and betel quid habits.",
        "symptoms": [
            "Non-healing oral mucosal ulcer, sore, or erythroplakia lasting >2-3 weeks",
            "Painless or painful persistent white patch (leukoplakia) or red patch (erythroplakia) in oral cavity",
            "Indurated palpable lump or tissue thickening in cheek, tongue, or floor of mouth",
            "Difficulty or pain while chewing, swallowing (dysphagia), or moving jaw and tongue",
            "Unexplained tooth mobility without periodontal disease or persistent unilateral earache (referred otalgia)",
            "Painless, firm cervical lymph node swelling in upper neck"
        ],
        "risk_factors": [
            "Smokeless tobacco chewing (gutkha, khaini, zarda, pan masala, paan)",
            "Bidi and cigarette tobacco smoking",
            "Areca nut (betel nut) chewing, inducing Oral Submucous Fibrosis (OSF)",
            "Heavy chronic ethyl alcohol consumption (synergistic carcinogen with tobacco)",
            "Human Papillomavirus infection (especially HPV Type 16 in oropharyngeal / tonsillar cancer)",
            "Chronic mechanical irritation from sharp broken teeth or ill-fitting dentures"
        ],
        "prevention": [
            "Total cessation of all smokeless tobacco, gutkha, betel quid, and cigarette use",
            "Elimination of excessive alcohol consumption",
            "Dental examination every 6 months with thorough visual and tactile mucosal screening",
            "Prompt smoothing or extraction of sharp teeth and correction of traumatic dental prostheses",
            "HPV 9-valent vaccination in adolescents prior to sexual exposure"
        ],
        "screening_test": "Bi-Annual Oral Visual Examination (OVE) + High-Resolution Narrow-Band Imaging (NBI) / Toluidine Blue Staining",
        "diagnosis": [
            "Comprehensive Head and Neck Clinical Examination including flexible fiberoptic nasopharyngolaryngoscopy",
            "Incisional or Punch Biopsy of the advancing edge of suspicious mucosal lesions with histopathology",
            "Contrast-Enhanced CT or MRI of Head and Neck with soft tissue and bone algorithm to evaluate cortical mandibular erosion",
            "High-Resolution Ultrasound of the Neck with Fine-Needle Aspiration Cytology (FNAC) for cervical adenopathy",
            "Whole-Body 18F-FDG PET-CT for advanced stage primary staging and distant metastatic assessment",
            "p16 Immunohistochemistry (surrogate for HPV-driven oropharyngeal carcinomas)"
        ],
        "treatments": [
            "Wide Local Surgical Resection of primary tumor with 1.0 to 1.5 cm clear margins (including partial glossectomy, commando procedure, or composite resection)",
            "Marginal or Segmental Mandibulectomy if bone involvement is demonstrated",
            "Ipsilateral or Bilateral Selective Neck Dissection (Levels I to IV/V)",
            "Immediate Microvascular Free Tissue Transfer Reconstruction (Free Fibula, Anterolateral Thigh, or Radial Forearm flap)",
            "Post-operative Intensity-Modulated Radiotherapy (IMRT) with concurrent Cisplatin for high-risk pathological features (positive margins, extranodal extension)",
            "Immunotherapy (Pembrolizumab or Nivolumab) for recurrent or metastatic disease"
        ],
        "treatment_modalities": {
            "surgery": "Transoral robotic surgery (TORS) or open oncologic ablation with microvascular free flap reconstructive surgery.",
            "chemotherapy": "High-dose Cisplatin (100 mg/m2 every 3 weeks) radiosensitization or TPF induction chemotherapy.",
            "radiotherapy": "Image-Guided IMRT delivering 66-70 Gy to primary bed and high-risk nodal basins while sparing parotid glands to preserve salivation.",
            "immunotherapy": "Pembrolizumab with or without platinum/5-FU as first-line therapy for recurrent/metastatic PD-L1 positive head and neck cancer.",
            "targeted_therapy": "Cetuximab (anti-EGFR) monoclonal antibody indicated in radiotherapy sensitization or chemotherapy combination.",
            "hormone_therapy": "Not applicable."
        },
        "recovery": [
            "Intensive speech and swallowing therapy (dysphagia rehabilitation) with video fluoroscopic swallow study.",
            "Meticulous dental prophylaxis, fluoride gel trays, and xerostomia (dry mouth) management post-radiotherapy.",
            "Jaw physical therapy and Therabite exercises to prevent radiation-induced trismus (lockjaw).",
            "Nutritional feeding tube (PEG) weaning and progressive dietary transition to textured foods.",
            "Endocrine screening for hypothyroidism post-neck irradiation every 6-12 months."
        ],
        "key_biomarkers": ["p16INK4a Expression (HPV Surrogate)", "PD-L1 Combined Positive Score (CPS)", "EGFR Overexpression", "Depth of Invasion (DOI in mm)"],
        "common_drugs": ["Cisplatin", "Cetuximab (Erbitux)", "Pembrolizumab (Keytruda)", "Fluorouracil (5-FU)", "Docetaxel", "Nivolumab (Opdivo)"],
        "survival_rate_5yr": "68% overall; >85% for localized disease treated with timely surgical resection",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Head and Neck Cancers (Version 1.2025)",
            "American Head and Neck Society (AHNS) Consensus Guidelines",
            "ESMO Clinical Practice Guidelines: Squamous Cell Carcinoma of the Head and Neck",
            "WHO Classification of Tumours: Head and Neck Tumours, 5th Edition"
        ]
    },

    "stomach-cancer": {
        "name": "Stomach & Gastric Cancer",
        "category": "gastrointestinal",
        "category_label": "Gastrointestinal",
        "icon": "fa-utensils",
        "image": "https://images.unsplash.com/photo-1544717305-2782549b5136?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Adenocarcinoma arising from the glandular epithelium of the gastric mucosa, categorized into intestinal and diffuse types (Lauren classification). Highly curable when discovered early before muscularis propria invasion.",
        "symptoms": [
            "Persistent, non-responsive epigastric indigestion, dyspepsia, or heartburn",
            "Early satiety and postprandial upper abdominal fullness after eating small meals",
            "Unexplained nausea, vomiting, or vomiting of ingested food (gastric outlet obstruction)",
            "Hematemesis (vomiting blood or coffee-ground material) or dark tarry stools (melena)",
            "Involuntary weight loss, loss of appetite, and progressive iron-deficiency anemia",
            "Palpable left supraclavicular lymph node (Virchow's node) or umbilical nodule (Sister Mary Joseph nodule)"
        ],
        "risk_factors": [
            "Chronic Helicobacter pylori bacterial infection (Class 1 carcinogen leading to chronic atrophic gastritis)",
            "Diet high in salt-preserved foods, smoked meats, nitrates, and low in fresh fruits/vegetables",
            "Active tobacco smoking and alcohol abuse",
            "Pernicious anemia and autoimmune metaplastic atrophic gastritis",
            "Hereditary Diffuse Gastric Cancer (HDGC) associated with germline CDH1 (E-cadherin) mutations",
            "Prior partial gastrectomy for benign peptic ulcer disease (>15-20 years prior)"
        ],
        "prevention": [
            "Testing and prompt eradication of Helicobacter pylori infection with 14-day quadruple antibiotic therapy",
            "Drastic reduction of dietary salt, pickled items, and processed/smoked meats",
            "High dietary intake of fresh citrus fruits, raw vegetables, and dietary vitamin C",
            "Prophylactic total gastrectomy for confirmed CDH1 mutation carriers with hereditary diffuse gastric cancer risk",
            "Endoscopic surveillance in endemic regions or high-risk families starting at age 40"
        ],
        "screening_test": "Upper Gastrointestinal Endoscopy (Esophagogastroduodenoscopy - EGD) with mucosal biopsies",
        "diagnosis": [
            "Upper GI Endoscopy (EGD) with multiple (≥6-8) biopsies from suspicious ulcer edges and nodularities",
            "Histopathologic evaluation with Lauren classification (Intestinal vs Diffuse / Signet Ring Cell)",
            "Endoscopic Ultrasound (EUS) to determine depth of tumor invasion (T-stage) and perigastric lymph nodes",
            "Contrast-Enhanced CT Scan of Chest, Abdomen, and Pelvis with triphasic stomach distension protocol",
            "Diagnostic Staging Laparoscopy with Peritoneal Lavage Cytology to exclude occult peritoneal micrometastasis",
            "Biomarker interrogation: HER2 IHC / FISH, MMR / MSI status, and PD-L1 CPS"
        ],
        "treatments": [
            "Endoscopic Submucosal Dissection (ESD) for early mucosal cancers (T1a without ulceration)",
            "Subtotal Gastrectomy with D2 lymphadenectomy for distal gastric body and antral tumors",
            "Total Gastrectomy with Roux-en-Y esophagojejunostomy and D2 lymph node dissection for proximal gastric tumors",
            "Perioperative Chemotherapy (FLOT regimen: 5-FU, Leucovorin, Oxaliplatin, Docetaxel) - 4 cycles pre-op, 4 cycles post-op",
            "Targeted Anti-HER2 Monoclonal Antibody (Trastuzumab) combined with chemotherapy for HER2-positive gastric adenocarcinoma",
            "Immunotherapy (Nivolumab or Pembrolizumab) combined with chemotherapy in PD-L1 positive advanced disease",
            "Targeted Anti-Claudin 18.2 Monoclonal Antibody (Zolbetuximab) for Claudin 18.2-positive advanced gastric cancer"
        ],
        "treatment_modalities": {
            "surgery": "Laparoscopic or robotic D2 radical subtotal or total gastrectomy with tension-free Roux-en-Y reconstruction.",
            "chemotherapy": "Perioperative FLOT protocol showing superior overall survival over post-operative chemoradiation.",
            "radiotherapy": "Adjuvant chemoradiation reserved for patients who underwent inadequate D0/D1 lymph node dissection without neoadjuvant therapy.",
            "immunotherapy": "Nivolumab / Pembrolizumab checkpoint blockade providing durable overall survival gains in metastatic settings.",
            "targeted_therapy": "Trastuzumab (anti-HER2), Ramucirumab (anti-VEGFR2), Zolbetuximab (anti-Claudin 18.2), and Trastuzumab deruxtecan.",
            "hormone_therapy": "Not applicable."
        },
        "recovery": [
            "Lifelong intramuscular or sublingual Vitamin B12 supplementation following total gastrectomy.",
            "Post-gastrectomy dietary counseling: small, frequent (6-8 meals/day), nutrient-dense meals low in simple carbohydrates to prevent dumping syndrome.",
            "Monitoring and replacement of iron, calcium, and fat-soluble vitamins (A, D, E, K).",
            "Weight stabilization and dietary pancreatic enzyme support.",
            "Surveillance EGD and abdominopelvic CT every 6 months for the first 3 years."
        ],
        "key_biomarkers": ["HER2/neu (ERBB2) Overexpression", "PD-L1 Combined Positive Score (CPS)", "MSI / dMMR Status", "Claudin 18.2 Expression", "CDH1 Mutation"],
        "common_drugs": ["Trastuzumab (Herceptin)", "Docetaxel", "Oxaliplatin", "Fluorouracil (5-FU)", "Ramucirumab (Cyramza)", "Zolbetuximab (Vyloy)"],
        "survival_rate_5yr": "36% overall; 75% if diagnosed at early localized stage before muscular wall invasion",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Gastric Cancer (Version 1.2025)",
            "Japanese Gastric Cancer Treatment Guidelines (6th Edition)",
            "ESMO Clinical Practice Guidelines: Gastric Cancer",
            "WHO Classification of Tumours: Digestive System Tumours, 5th Edition"
        ]
    },

    "liver-cancer": {
        "name": "Liver Cancer (Hepatocellular Carcinoma)",
        "category": "gastrointestinal",
        "category_label": "Hepato-Biliary & GI",
        "icon": "fa-vial-virus",
        "image": "https://images.unsplash.com/photo-1530026405186-ed1f139313f8?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
        "description": "Primary liver malignancy predominantly comprising Hepatocellular Carcinoma (HCC, ~80%) and Intrahepatic Cholangiocarcinoma. Almost exclusively develops on a background of chronic hepatic injury, viral hepatitis, and cirrhosis.",
        "symptoms": [
            "Dull, persistent pain or heaviness in the right upper quadrant of abdomen or right shoulder",
            "Rapid onset or worsening of ascites (abdominal fluid accumulation) and lower extremity edema",
            "Jaundice (yellowing of skin and eyes) with dark urine and itching (pruritus)",
            "Unexplained rapid deterioration of hepatic function in a patient with compensated cirrhosis",
            "Easy bruising or bleeding, encephalopathy (confusion), and acute upper gastrointestinal bleeding from esophageal varices",
            "Profound fatigue, anorexia, and involuntary weight loss"
        ],
        "risk_factors": [
            "Chronic viral hepatitis: Hepatitis B Virus (HBV) infection (direct oncogenic DNA virus) and Hepatitis C Virus (HCV)",
            "Liver cirrhosis of any etiology (alcohol-related liver disease, NAFLD/NASH)",
            "Non-Alcoholic Steatohepatitis (NASH) associated with metabolic syndrome, diabetes, and obesity",
            "Dietary exposure to Aflatoxin B1 from contaminated groundnuts and stored grains",
            "Inherited metabolic conditions: Hereditary hemochromatosis, Wilson disease, alpha-1 antitrypsin deficiency"
        ],
        "prevention": [
            "Universal Hepatitis B infant vaccination and antiviral treatment of active HBV carriers",
            "Direct-Acting Antiviral (DAA) curative therapy for chronic Hepatitis C infection",
            "Strict abstinence from alcohol in individuals with liver disease",
            "Weight reduction, insulin sensitization, and exercise to reverse hepatic steatosis in NAFLD/NASH",
            "Rigorous surveillance with liver ultrasound and serum Alpha-Fetoprotein (AFP) every 6 months in all cirrhotic patients"
        ],
        "screening_test": "Abdominal Ultrasound + Serum Alpha-Fetoprotein (AFP) every 6 months for cirrhotic and high-risk HBV patients",
        "diagnosis": [
            "Triphasic Dynamic Contrast-Enhanced CT or MRI with extracellular or hepatobiliary contrast (Eovist/Primovist)",
            "Application of Liver Imaging Reporting and Data System (LI-RADS) diagnostic criteria: arterial phase hyperenhancement (APHE) with portal/delayed 'washout'",
            "Serum Alpha-Fetoprotein (AFP) quantitative measurement",
            "Targeted core needle biopsy reserved for non-cirrhotic patients or lesions with indeterminate LI-RADS category",
            "Assessment of underlying liver functional reserve utilizing Child-Pugh score and ALBI (Albumin-Bilirubin) grade",
            "Hepatic venous pressure gradient (HVPG) and upper endoscopy to assess portal hypertension and varices"
        ],
        "treatments": [
            "Orthotopic Liver Transplantation (OLT) within Milan Criteria (single tumor ≤5cm or up to 3 tumors each ≤3cm without vascular invasion)",
            "Anatomical Hepatic Resection (Partial hepatectomy) in non-cirrhotic or well-compensated cirrhotic patients (Child-Pugh A with normal portal pressure)",
            "Radiofrequency Ablation (RFA) or Microwave Ablation (MWA) for early tumors ≤3 cm",
            "Transarterial Chemoembolization (TACE) or Transarterial Radioembolization (TARE / Yttrium-90) for intermediate-stage disease",
            "First-line Combination Systemic Immunotherapy: Atezolizumab (anti-PD-L1) + Bevacizumab (anti-VEGF)",
            "Dual Immunotherapy: Tremelimumab (anti-CTLA-4) + Durvalumab (anti-PD-L1) (STRIDE regimen)",
            "Oral Multi-Kinase Tyrosine Kinase Inhibitors (Sorafenib, Lenvatinib, Regorafenib, Cabozantinib)"
        ],
        "treatment_modalities": {
            "surgery": "Liver transplantation providing curative oncologic clearance and replacement of cirrhotic parenchymal organ, or partial anatomical hepatectomy.",
            "chemotherapy": "Systemic cytotoxic chemotherapy possesses negligible efficacy in HCC and is not routinely indicated.",
            "radiotherapy": "Stereotactic Body Radiotherapy (SBRT) delivering targeted conformal radiation to unresectable liver tumors.",
            "immunotherapy": "Atezolizumab + Bevacizumab or Tremelimumab + Durvalumab establishing the current global gold standard for advanced HCC.",
            "targeted_therapy": "Small-molecule multi-kinase inhibitors (Lenvatinib, Sorafenib, Cabozantinib) targeting VEGFR, FGFR, and RET signaling cascades.",
            "hormone_therapy": "Not applicable."
        },
        "recovery": [
            "Post-transplant lifelong immunosuppressive drug monitoring (Tacrolimus, Mycophenolate mofetil) and infection prevention.",
            "Monitoring for upper gastrointestinal bleeding: routine screening endoscopy for esophageal varices prior to initiating anti-VEGF therapy.",
            "Low-sodium diet (≤2g/day) and spironolactone/furosemide therapy for ascites control.",
            "Abdominal ultrasound and triphasic liver CT/MRI every 3 months for the first 2 years, then every 6 months."
        ],
        "key_biomarkers": ["Serum Alpha-Fetoprotein (AFP)", "LI-RADS LR-5 Imaging Characteristics", "Child-Pugh Score", "ALBI Grade", "PD-L1 TPS / CPS"],
        "common_drugs": ["Atezolizumab (Tecentriq)", "Bevacizumab (Avastin)", "Durvalumab (Imfinzi)", "Tremelimumab (Imjudo)", "Lenvatinib (Lenvima)", "Sorafenib (Nexavar)"],
        "survival_rate_5yr": "21% overall; >36% when detected at early localized stage, reaching >70% with liver transplantation",
        "references": [
            "NCCN Clinical Practice Guidelines in Oncology: Hepatocellular Carcinoma (Version 1.2025)",
            "AASLD Practice Guidance: Prevention, Diagnosis, and Treatment of Hepatocellular Carcinoma",
            "EASL Clinical Practice Guidelines: Management of Hepatocellular Carcinoma",
            "LI-RADS v2018: Liver Imaging Reporting and Data System"
        ]
    }
}
