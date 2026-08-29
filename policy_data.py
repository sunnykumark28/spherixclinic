# This file contains the data for the legal/policy pages.
# The content is written in Markdown format and rendered in the Legal Center.

POLICY_DATA = {
    "privacy-policy": {
        "title": "Privacy Policy",
        "icon": "fa-shield-halved",
        "content": """
### 1. General Policy & Global Privacy Commitment
Welcome to Spherix Clinic ("Company", "we", "our", "us"). We are committed to protecting your personal health information and your fundamental right to privacy. This comprehensive Privacy Policy explains how we collect, process, encrypt, disclose, and safeguard your data when you access our web applications, AI diagnostic engines, telemedicine infrastructure, and clinical networks.

### 2. Information We Collect

**A. Personal Identity & Contact Data**
*   **Identity Data:** Full names, usernames, biological sex, age, date of birth, and identity credentials.
*   **Contact Information:** Email addresses, phone numbers, and physical residential/billing addresses.
*   **Authentication Data:** Passwords, cryptographic hashes, security questions, and multi-factor authentication tokens.

**B. Protected Health Information (PHI) & Clinical Intake**
*   **Symptom & Diagnostic Intake:** Descriptions of current physical symptoms, duration, severity, anatomical location, and clinical notes.
*   **Medical & Family History:** Previous diagnoses, surgical histories, chronic illnesses, familial oncology histories, and lifestyle risk factors (tobacco, alcohol, occupational exposures).
*   **Diagnostic & Laboratory Reports:** Uploaded medical imaging notes (e.g. Mammograms, CT/MRI scans, Ultrasound), pathology biopsies, blood panels, and PSA/tumor marker values.

**C. Precision Genomic & Biomarker Queries**
*   Inquiries regarding genetic mutations (e.g. *BRCA1/2, EGFR, HER2, KRAS, BRAF, MSI-H/dMMR*) are processed in isolated ephemeral sessions and are strictly protected under the Genetic Information Nondiscrimination Act (GINA).

**D. Technical & Telemetry Data**
*   Device identifiers, browser types, operating systems, encrypted session cookies, and anonymized access logs to prevent malicious automated access.

### 3. Role-Specific Data Processing & Protections

**A. For Patients**
*   **Clinical Consultation:** Your health data is processed solely to provide AI diagnostic triage insights and facilitate specialist appointment bookings.
*   **Doctor Access:** Your health profile is only accessible to a licensed medical provider when you explicitly confirm an appointment or virtual consultation.
*   **Zero Sale of Data:** We never sell, monetize, or license your personal health data to insurance brokers or third-party advertisers.

**B. For Doctors & Healthcare Providers**
*   **Verification:** Professional medical registration numbers, board certifications, affiliations, and specialties are verified before public listing.
*   **Clinical Confidentiality:** Doctors agree to uphold standard medical ethics, HIPAA standards, and patient confidentiality for all records accessed.

**C. For Hospitals & Medical Centers**
*   **Operational Management:** Facility capacities, department staff rosters, and bed availability are managed under strict institutional access control.
*   **Data Processing Agreement (DPA):** Hospitals act as institutional data controllers and agree to uphold all statutory health data obligations.

**D. For Blood & Organ Donors**
*   **Registry Privacy:** Donor blood groups, organ pledges, and geographic locations are protected. Contact details are never publicly exposed and are only shared with verified transplant centers when an active match occurs.

**E. For Hospital & Department Staff**
*   **Access Control:** Staff access is restricted strictly to authorized administrative workflows with immutable audit logging.

### 4. Encryption & Security Standards
*   **In-Transit:** 256-bit TLS 1.3 encryption across all web application routes, API endpoints, and real-time streaming sockets.
*   **At-Rest:** AES-256 database-level encryption for all sensitive health records and credentials.
*   **Role-Based Access Control (RBAC):** Least-privilege access enforcement across all administrative and staff tiers.

### 5. Patient Rights under HIPAA, GDPR & CCPA
Depending on your applicable legal jurisdiction, you retain the following unconditional rights:
*   **Right to Access:** Obtain a complete digital copy of your health records and session logs.
*   **Right to Rectification:** Request immediate correction of erroneous or outdated clinical data.
*   **Right to Erasure ("Right to Be Forgotten"):** Request permanent deletion of your account and personal identifiers from our databases.
*   **Right to Restrict Processing:** Limit or withdraw consent for automated AI symptom analysis.

### 6. Contact Our Data Protection Officer (DPO)
For inquiries regarding our privacy standards or to exercise your data rights:
*   **Email:** privacy@spherixclinic.com / dpo@spherixclinic.com
*   **Mailing Address:** Spherix Clinic Global Compliance Office, Medical Technology Park.
"""
    },
    "terms-of-service": {
        "title": "Terms of Service",
        "icon": "fa-file-contract",
        "content": """
### 1. Acceptance of Terms
By accessing or using the Spherix Clinic platform, AI diagnostic utilities, telemedicine portals, or oncology hubs, you agree to be bound by these legally enforceable Terms of Service. If you disagree with any portion of these terms, you must immediately terminate use of the platform.

### 2. Nature of Platform & Services
Spherix Clinic provides a multi-dimensional digital healthcare technology ecosystem. The platform serves as an informational triage tool, clinical decision-support engine, and connection gateway between patients, healthcare providers, and accredited medical institutions.

### 3. User Representations & Responsibilities
By using our services, you warrant and represent that:
*   All registration and intake information you submit is accurate, truthful, and up-to-date.
*   You possess the legal capacity to agree to these Terms in your jurisdiction.
*   You will not use automated scrapers, bots, or unauthorized scripts to extract clinical data or overwhelm our server infrastructure.
*   You will not reverse engineer or attempt to extract the underlying weights, source code, or proprietary algorithms of our AI diagnostic engines.

### 4. Role-Specific Terms & Conditions

**A. Patients**
*   You acknowledge that AI symptom outputs and oncology assessments represent educational decision-support tools and do not establish a formal doctor-patient relationship until an appointment is conducted.
*   You agree to arrive on time or provide at least 24 hours cancellation notice for confirmed specialist bookings.

**B. Physicians & Medical Specialists**
*   You warrant that you maintain an active, unencumbered medical license in good standing in your jurisdiction.
*   You retain full, independent clinical responsibility for all medical diagnoses, prescription orders, and patient care decisions.

**C. Hospitals & Facilities**
*   You agree to maintain accurate reporting of bed availability, critical care capacity, and specialist schedules.

**D. Donors**
*   Registration as a blood or organ donor represents a voluntary expression of compassionate intent. Final donation eligibility is determined through institutional clinical evaluation.

### 5. Intellectual Property Rights
All software, algorithms, UI designs, medical encyclopedias, branding, and content are the exclusive proprietary property of Spherix Clinic and protected by international intellectual property treaties.

### 6. Limitation of Liability
TO THE MAXIMUM EXTENT PERMITTED BY LAW, SPHERIX CLINIC AND ITS DIRECTORS, EMPLOYEES, AFFILIATES, AND AGENTS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, CONSEQUENTIAL, SPECIAL, OR PUNITIVE DAMAGES ARISING FROM YOUR USE OF OR INABILITY TO USE THE SERVICES.

### 7. Governing Law & Dispute Resolution
These Terms are governed by and construed in accordance with applicable medical technology and commercial laws, without regard to conflict of law principles.
"""
    },
    "doctor-agreement": {
        "title": "Doctor & Healthcare Provider Agreement",
        "icon": "fa-user-doctor",
        "content": """
### 1. Professional Scope & Provider Standards
This Doctor & Healthcare Provider Agreement ("Agreement") governs all licensed physicians, surgeons, oncologists, and healthcare practitioners registered on the Spherix Clinic platform. By creating a professional account or accepting patient appointments, you agree to these clinical and ethical obligations.

### 2. Medical Licensure & Credential Verification
*   **Active Credentialing:** You warrant that you hold an active, valid, and unrestricted license to practice medicine in your registered jurisdiction.
*   **Verification Authority:** You grant Spherix Clinic the right to verify your credentials with national medical boards, councils, and institutional affiliations.
*   **Mandatory Status Update:** You must notify Spherix Clinic within 24 hours of any disciplinary inquiry, license suspension, restriction, or malpractice judgment.

### 3. Independent Clinical Judgment & Standard of Care
*   **Clinical Autonomy:** Spherix Clinic is a digital technology platform and does not interfere with, dictate, or direct your professional medical judgment.
*   **Standard of Care:** You agree that all medical advice, diagnostic evaluations, treatment plans, and prescriptions delivered via in-person visits or telemedicine meet standard-of-care guidelines established by relevant medical governing bodies.
*   **Prescription Governance:** You agree to prescribe medications strictly within legal statutory frameworks and comply with all prohibitions regarding controlled substances via telehealth.

### 4. Patient Confidentiality & HIPAA Obligations
*   **Data Protection:** You are legally bound under HIPAA, GDPR, and medical confidentiality laws to protect all patient health records accessed through the physician portal.
*   **Access Limitation:** You may access patient records only when a direct clinical consultation or appointment has been initiated by the patient.
*   **Device Security:** You agree to maintain passcode and biometric protection on all personal devices used to access the Spherix Physician Dashboard.

### 5. Telehealth Video Consultations
*   Virtual video appointments must be conducted in private, confidential clinical settings free from unauthorized third-party observation.
*   You agree not to record audio or video feeds of patient consultations without explicit, documented written consent.
*   If a patient presents with unstable vital signs or red-flag emergency symptoms, you agree to immediately direct the patient to emergency department services.

### 6. Ethical Compliance & Anti-Kickback Prohibitions
*   You affirm strict adherence to medical ethics prohibiting fee-splitting, unearned referral fees, or commercial kickbacks.
"""
    },
    "hospital-agreement": {
        "title": "Hospital & Institutional Partner Agreement",
        "icon": "fa-hospital",
        "content": """
### 1. Institutional Partnership Scope
This Hospital & Institutional Partner Agreement ("Agreement") governs all accredited hospitals, medical centers, surgical institutes, and clinics utilizing the Spherix Clinic institutional dashboard and network.

### 2. Institutional Accreditation & Authority
*   **Institutional Verification:** The hospital warrants that it is a fully accredited healthcare institution licensed by state and federal health ministries.
*   **Authorized Representation:** The administrator creating the hospital profile warrants full institutional authority to enter into this operational agreement.

### 3. Real-Time Resource & Bed Availability Reporting
*   **Capacity Transparency:** The hospital agrees to maintain real-time, accurate reporting of ICU beds, general ward availability, emergency room capacity, and active specialty departments.
*   **Emergency Dispatch Reliability:** In critical trauma or triage events, the hospital agrees to promptly update its operational status to prevent misdirected emergency patient transfers.

### 4. Staff Management & Access Governance
*   **Staff Provisioning:** Hospital administrators are responsible for creating, assigning, and de-provisioning staff credentials for department coordinators, nurses, and administrative personnel.
*   **De-authorization Mandate:** Upon the termination or reassignment of any staff member, the hospital must immediately revoke their access credentials within the hospital portal.

### 5. Institutional Data Protection & Compliance
*   **Joint Controller Obligations:** The hospital agrees to execute a Business Associate Agreement (BAA) and Data Processing Agreement (DPA) with Spherix Clinic.
*   **Electronic Health Record (EHR) Integrity:** The hospital warrants that all patient admissions, discharge summaries, and diagnostic test uploads comply with statutory data protection standards.
*   **Audit Cooperation:** The hospital agrees to cooperate with scheduled security compliance audits and maintain immutable electronic audit logs of all patient record access.
"""
    },
    "donor-policy": {
        "title": "Blood & Organ Donor Voluntary Policy",
        "icon": "fa-hand-holding-heart",
        "content": """
### 1. Purpose & Humanitarian Nature of the Registry
The Spherix Blood & Organ Donor Registry is a dedicated humanitarian initiative designed to connect voluntary life-saving donors with accredited blood banks, trauma centers, and certified organ transplant networks during critical medical emergencies.

### 2. Voluntary Expression of Compassionate Intent
*   **Non-Binding Humanitarian Pledge:** Registering as a blood or organ donor represents a voluntary expression of philanthropic intent. It does not constitute a legally binding commercial contract or compulsory medical obligation.
*   **Unconditional Right to Revoke:** Donors retain the absolute right to update, modify, or delete their donor registration from the Spherix Registry at any time without justification.

### 3. Strict Donor Privacy & Identity Shielding
*   **Confidential Contact Details:** A donor's direct telephone number, email, and home address are **never** displayed publicly on search results or unverified public web pages.
*   **Verified Medical Match Routing:** When an urgent compatibility match is identified for a patient in critical need, contact is facilitated exclusively through verified hospital transplant coordinators or accredited regional blood banks.

### 4. Prohibition on Commercialization of Human Organs
*   Spherix Clinic strictly adheres to the National Organ Transplant Act (NOTA) and World Health Organization (WHO) Guiding Principles on Human Cell, Tissue and Organ Transplantation.
*   **Zero Financial Compensation:** Any attempt to buy, sell, barter, or commercially trade human blood, organs, or tissues on this platform is strictly illegal, results in immediate ban, and is reported to law enforcement agencies.

### 5. Medical Safety & Screening Protocol
*   Final donation eligibility is determined through rigorous clinical screening, serological testing, and physiological evaluations conducted directly by licensed medical professionals at certified collection centers.
"""
    },
    "staff-agreement": {
        "title": "Hospital & Department Staff Security Agreement",
        "icon": "fa-id-badge",
        "content": """
### 1. Scope & Staff Accountability
This Staff Security & Operational Agreement applies to all department coordinators, administrative personnel, triage nurses, and medical clerks granted access to Spherix Clinic institutional dashboards.

### 2. Credential Security & Authorized Access
*   **Individual Credentials:** Staff members must use only their assigned individual login credentials. Account sharing or credential pooling is strictly prohibited.
*   **Immediate Reporting:** Staff must immediately report any suspected credential compromise or unauthorized login attempts to their hospital security administrator.

### 3. Electronic Health Record (EHR) Data Confidentiality
*   **Need-to-Know Principle:** Staff may access patient diagnostic records, appointment files, and bed allocation profiles strictly on a "need-to-know" basis directly required for active patient care or hospital operations.
*   **Prohibition on Exfiltration:** Staff are strictly prohibited from copying, downloading, exporting, photographing, or disseminating confidential patient health records to external personal devices or unauthorized third parties.

### 4. Immutable Audit Logging & Monitoring
*   All actions performed within staff portals—including viewing patient lists, updating bed status, altering doctor schedules, and generating receipts—are recorded in immutable audit logs capturing timestamps, user IDs, and IP addresses.
*   Audit logs are routinely reviewed by hospital compliance officers and regulatory bodies.

### 5. Disciplinary Actions & Legal Penalties
*   Violations of patient privacy or unauthorized data access will result in immediate termination of platform access, institutional disciplinary termination, and potential civil or criminal prosecution under HIPAA and regional healthcare data protection statutes.
"""
    },
    "patient-terms": {
        "title": "Patient Terms of Care & Diagnostic Agreement",
        "icon": "fa-user",
        "content": """
### 1. Scope of Patient Services
This Patient Terms of Care Agreement governs all individuals accessing Spherix Clinic symptom checkers, AI diagnostic tools, oncology hubs, doctor directory, and telemedicine services.

### 2. Informational & Triage Nature of AI Tools
*   **Diagnostic Support:** The AI Symptom Checker, Oncology Risk Screener, and TNM Staging Simulator provide algorithmic decision-support and educational triage recommendations based on current clinical literature.
*   **No Substitute for Doctor Visit:** Automated outputs do not replace an in-person physical clinical examination, cross-sectional radiological imaging, or histological biopsy by a certified physician.

### 3. Truthful Clinical Disclosure
*   To receive accurate AI triage recommendations and safe physician care, you agree to provide truthful, accurate, and comprehensive information regarding your symptoms, medical history, age, and medications.

### 4. Appointment Etiquette & Cancellation Policy
*   When booking specialist consultations, you agree to attend scheduled appointments promptly or provide cancellation notice at least 24 hours in advance.

### 5. Emergency Situations
*   In any life-threatening emergency, you agree to immediately bypass online tools and call emergency services (911) or proceed directly to an emergency department.
"""
    },
    "medical-disclaimer": {
        "title": "Medical Disclaimer",
        "icon": "fa-user-doctor",
        "content": """
### 1. Educational & Triage Information Only
The content, text, diagnostic tools, risk calculators, staging simulators, and AI outputs provided across Spherix Clinic ("Content") are intended strictly for educational, informational, and clinical triage support purposes. The Content is **NOT** a substitute for direct professional medical advice, clinical examination, physical histopathology, or formal medical diagnosis.

### 2. Artificial Intelligence Diagnostic Limitations
Our platform employs sophisticated artificial intelligence and machine learning models calibrated against international clinical guidelines (including NCCN, ASCO, and WHO). However:
*   AI models synthesize statistical and pattern-based associations and cannot replace physical palpation, radiological biopsy, or clinical judgment.
*   Outputs may not account for rare comorbidities, novel genetic variants, or atypical clinical presentations.
*   **Never disregard professional medical advice or delay seeking evaluation because of information presented on Spherix Clinic.**

### 3. Emergency Medical Situations (Red Flag Warning)
**SPHERIX CLINIC IS NOT AN EMERGENCY MEDICAL DISPATCHER.**
If you are experiencing any life-threatening symptoms, including:
*   Severe chest pain, pressure, or radiating pain to the arm or jaw
*   Sudden weakness, facial drooping, difficulty speaking, or signs of stroke
*   Severe acute shortness of breath or severe hemoptysis (coughing blood)
*   **Oncology Fever Alert:** Oral temperature ≥ 100.4°F (38.0°C) during active chemotherapy (Suspected Febrile Neutropenia)

**IMMEDIATELY CALL EMERGENCY SERVICES (911 OR YOUR LOCAL EMERGENCY NUMBER) OR GO TO THE NEAREST HOSPITAL EMERGENCY DEPARTMENT.**
"""
    },
    "oncology-policy": {
        "title": "Oncology Intelligence & Cancer Care Policy",
        "icon": "fa-ribbon",
        "content": """
### 1. Clinical Scope & NCCN 2026 Guidelines Alignment
The Spherix Comprehensive Oncology Network and Cancer Care Hub provide specialized intelligence across 10 major malignancy categories. All disease atlas profiles, diagnostic roadmaps, and biomarker associations are referenced against the National Comprehensive Cancer Network (NCCN) Clinical Practice Guidelines in Oncology and American Society of Clinical Oncology (ASCO) standards.

### 2. AI Cancer Diagnostic Evaluation Policy
*   **Pattern-Recognition Triage:** The "Check Cancer" AI intake system analyzes patient-reported symptoms, anatomical locations, duration, smoking exposure, and red flags against oncological disease criteria.
*   **Non-Definitive Nature:** An AI diagnostic match is a probabilistic estimate designed to expedite specialist referral and recommended diagnostic workups (e.g. 3D Digital Mammography, Core Needle Biopsy, Endoscopy, PET-CT).
*   **Biopsy Mandate:** Definitive confirmation of any solid or hematologic neoplasm strictly requires microscopic tissue examination by a board-certified pathologist.

### 3. TNM Staging & Prognostic Simulator Governance
*   Staging algorithms adhere to the American Joint Committee on Cancer (AJCC) 8th Edition and UICC criteria.
*   **Clinical vs. Pathological Staging:** Users are advised that Clinical Stage ($cTNM$) derived prior to surgical intervention is subject to revision following surgical resection and histological margin assessment ($pTNM$).
*   **Survival Benchmarks:** 5-year relative survival curves represent broad epidemiological population registries (SEER / NCDB) and do not predict individual patient trajectories, which are significantly influenced by molecular targeted therapy and immunotherapy response.

### 4. Supportive Oncology & Chemotherapy Safety
*   Side-effect management recommendations (antiemetics, neutropenia hygiene, cryotherapy for neuropathy) must be cleared with your treating medical oncologist.
*   **Contraindicated Supplements:** Patients must never initiate high-dose antioxidant supplements, herbal infusions, or unprescribed over-the-counter medications during active chemotherapy or radiation without oncology approval due to cytochrome P450 and therapeutic antagonism risks.
"""
    },
    "genomics-privacy": {
        "title": "Genomic Privacy & GINA Compliance Policy",
        "icon": "fa-dna",
        "content": """
### 1. Genetic Information Nondiscrimination Act (GINA) Safeguards
In strict compliance with the federal Genetic Information Nondiscrimination Act (Public Law 110-233, 42 U.S.C. 2000ff):
*   **Health Insurance Protection:** Health insurers and group health plans are legally prohibited from using genetic test results or molecular biomarker queries (e.g. *BRCA1/2, EGFR, Lynch syndrome*) to deny health coverage, increase premiums, or impose pre-existing condition exclusions.
*   **Employment Protection:** Employers may not use genetic information to make hiring, firing, promotion, or compensation decisions.

### 2. Molecular Data Isolation & Confidentiality
*   **Ephemeral Processing:** All genomic target queries and mutation matching evaluations conducted on Spherix Clinic are processed in isolated ephemeral memory buffers.
*   **No Commercial Data Sharing:** Your genomic inquiries and hereditary cancer screening responses are never linked to commercial marketing IDs or shared with consumer data brokers.

### 3. Somatic vs. Germline Testing Advisory
*   **Somatic Mutations:** Acquired mutations found strictly within tumor tissue (e.g. *EGFR Exon 19 del, KRAS G12C*) dictate targeted therapeutic drugs and are not inherited by offspring.
*   **Germline Mutations:** Inherited mutations (e.g. *BRCA1/2, Lynch MLH1/MSH2*) carry familial implications. Spherix Clinic strongly advocates for pre-test and post-test genetic counseling with a certified genetic counselor.
"""
    },
    "clinical-trials-policy": {
        "title": "Clinical Trials Ethics & IRB Policy",
        "icon": "fa-microscope",
        "content": """
### 1. Declaration of Helsinki & Institutional Review Board (IRB) Oversight
Every active oncology and therapeutic clinical trial cataloged within the Spherix Clinic Directory has received formal ethical review and approval from an accredited Institutional Review Board (IRB) or Independent Ethics Committee (IEC). All listed protocols strictly conform to the World Medical Association Declaration of Helsinki.

### 2. Voluntary Informed Consent Charter
*   **Full Disclosure:** Prior to enrollment in any trial (Phase I, II, or III), participants receive detailed written documentation outlining experimental mechanisms, potential toxicities, administration schedules, and alternative treatment options.
*   **Unconditional Right to Withdraw:** Enrolled participants retain the absolute legal and ethical right to withdraw from any clinical trial at any time, for any reason, without penalty or forfeiture of standard-of-care medical treatments.

### 3. Patient Data Pseudonymization & Confidentiality
*   All trial telemetry, biomarker data, and clinical response logs are strictly pseudonymized using unique trial participant IDs.
*   Direct personal identifiers are safeguarded under clinical research data protection regulations.
"""
    },
    "telemedicine-policy": {
        "title": "Telemedicine & Virtual Care Policy",
        "icon": "fa-video",
        "content": """
### 1. End-to-End Encrypted Telehealth Architecture
All virtual medical consultations, second-opinion video calls, and real-time clinical chats are conducted over WebRTC connections protected by end-to-end 256-bit encryption.

### 2. Audio & Video Recording Prohibitions
*   Spherix Clinic does not record, store, or monitor video or audio transmissions between patients and physicians.
*   Neither patient nor doctor may record telehealth sessions without explicit, documented mutual written consent.

### 3. Jurisdictional Medical Licensing Standards
*   Physicians conducting telemedicine consultations on Spherix Clinic hold verified, active medical licenses in corresponding jurisdictions.
*   Virtual consultations are intended for clinical review, treatment pathway explanation, second opinions, and follow-up guidance.
*   Where in-person physical examination is clinically indicated, the consulting physician will advise immediate in-person referral.
"""
    },
    "ai-ethics-governance": {
        "title": "AI Ethics & Algorithmic Safety Policy",
        "icon": "fa-brain",
        "content": """
### 1. Algorithmic Transparency & Model Safety
Spherix Clinic employs medical language models and clinical decision-support heuristics that undergo continuous validation against peer-reviewed clinical guidelines.

### 2. Bias Mitigation & Demographic Equity
Our AI training architectures incorporate diverse clinical demographic cohorts to ensure high diagnostic precision across all biological sexes, age brackets, and ethnic backgrounds, mitigating healthcare disparity risks.

### 3. Human-in-the-Loop Clinical Validation
Artificial intelligence within Spherix Clinic is engineered as an augmentative clinical assistant. Critical pathways—including definitive oncology diagnoses, surgical recommendations, and prescription authorizations—strictly require licensed human physician oversight.
"""
    },
    "cookie-policy": {
        "title": "Cookie & Local Storage Policy",
        "icon": "fa-cookie-bite",
        "content": """
### 1. What Are Cookies & Local Storage
Cookies and local browser storage are small data files stored on your device that allow our web applications to preserve your secure login state, remember UI preferences, and deliver responsive interactions.

### 2. How Spherix Clinic Utilizes Storage
*   **Essential Security Cookies:** Necessary for session management, user authentication, CSRF protection, and account access. These cannot be disabled.
*   **Functional Cookies:** Store user interface preferences (such as dark mode preferences and active filter selections).
*   **Analytics Storage:** Aggregated, anonymized performance metrics to measure page loading speeds and optimize clinical tool accessibility.
*   **Zero Third-Party Advertising Trackers:** Spherix Clinic does not use third-party behavioral advertising tracking cookies.

### 3. Managing Your Cookie Preferences
You can modify your browser settings to decline non-essential cookies. However, disabling essential session cookies will prevent secure login to patient, doctor, and hospital dashboards.
"""
    },
    "acceptable-use": {
        "title": "Acceptable Use & Platform Security Policy",
        "icon": "fa-check-double",
        "content": """
### 1. Scope of Acceptable Use
This Acceptable Use Policy applies to all registered users, patients, healthcare professionals, hospital administrators, and general visitors across the Spherix Clinic platform.

### 2. Strictly Prohibited Activities
You agree that you will not use Spherix Clinic to:
*   **Harmful Content:** Generate, transmit, or solicit content promoting self-harm, suicide, violence, or illegal distribution of pharmaceuticals.
*   **System Disruption:** Introduce viruses, trojans, worms, or malicious code designed to disrupt platform integrity or compromise server security.
*   **Automated Abuse:** Deploy automated scrapers, crawl bots, or volumetric DDoS attacks against our diagnostic APIs.
*   **Impersonation:** Falsely claim medical qualifications, physician credentials, or institutional hospital authority.
*   **Security Probing:** Attempt unauthorized penetration testing, vulnerability scanning, or reverse engineering of proprietary AI diagnostic models without prior written consent.

### 3. Enforcement & Legal Penalties
Violations of this Acceptable Use Policy will result in immediate account termination, IP-level access restrictions, and legal prosecution to the fullest extent of applicable civil and criminal laws.
"""
    }
}