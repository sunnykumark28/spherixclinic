# 🏥 Spherix Clinic — AI-Powered Smart Healthcare & Hospital Management Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Groq AI](https://img.shields.io/badge/AI%20Engine-Groq%20LLaMA%203.3%2070B-F05A28?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)
[![Google Vision](https://img.shields.io/badge/Computer%20Vision-Google%20Cloud%20Vision-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/vision)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind%20CSS%20%2B%20Glassmorphism-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**Spherix Clinic** is a next-generation, AI-driven digital healthcare and hospital management ecosystem. Combining multi-modal AI clinical diagnostics (Groq LLMs + Google Vision Computer Vision), comprehensive electronic health records (EHR), multi-role administrative portals, real-time hospital bed & ICU telemetry, an online pharmacy, and international medical travel desks — all wrapped in an ultra-modern glassmorphic UI.

---

## 🌟 Key Highlights & Feature Matrix

### 🧠 1. Multi-Modal AI Clinical Diagnostic Suite
* **Interactive Symptom Checker**: Multi-step diagnostic workflow with body region mapping, pain intensity sliders, duration qualifiers, and secondary symptom refinement.
* **Google Cloud Vision Multimodal Analysis**: Visual inspection of dermatological issues, wounds, rashes, and document OCR.
* **Radiology AI Scanner**: Automated classification and preliminary interpretation of Chest X-Rays, CT Scans, and MRI imagery.
* **Prescription OCR & Drug Interaction Intelligence**: Instant extraction of medication schedules from doctor handwriting and automated openFDA/Groq safety cross-checks.
* **Automated PDF Diagnostic Reports & Email Delivery**: Instant generation of official PDF medical reports with a 1-click option to automatically email the document to the patient's registered inbox.

### 🏛️ 2. Multi-Role Portal Architecture
* **Patient Portal**: Profile management, digital vitals logging, appointment scheduling, prescription archives, live consultation queue tracking, and pharmacy order histories.
* **Doctor Workspace**: Consultation scheduler, live OPD queue management, digital e-prescriptions, clinical notes, and live telemetry chat widget.
* **Hospital & Staff Dashboards**:
  * **Reception Desk**: Walk-in token generator, live queue broadcast with Web Speech API audio chimes, and instant prescription slip printing.
  * **Nursing Station**: Patient acuity classification (Stable/Guarded/Critical), digital Medication Administration Record (MAR), and vitals telemetry charting.
  * **Bed & Ward Management**: Real-time room occupancy grids, ICU vs. General Ward utilization bars, and 1-click bed transfers.
  * **Blood Bank & Donation**: Live blood inventory gauges by blood group (A+, B+, O+, AB+, etc.), surplus tracking, and donor registration.
  * **Organ Donor Registry**: Confidential organ donor registration and matching hub.
* **System Administrator (Root Portal)**: System-wide platform metrics, role delegations, audit logging, emergency announcements, and database sync utilities.

### 🏥 3. Hospital Discovery & Global Medical Travel
* **Live Hospital Bed & ICU Tracker**: Real-time hospital directory with available general bed count, ICU availability percentage, and daily admission tariffs.
* **Medical Travel & Visa Desk Drawer**: Slide-over international patient drawer for visa assistance, airport transfers, translator bookings, and cross-border doctor consultations.

### 💊 4. Digital Pharmacy & Wellness
* **Medical Shop E-Commerce**: Searchable medicine catalog with categories, dosage recommendations, cart management, and downloadable PDF tax invoices.
* **Zen Yoga & Holistic Wellness Hub**: Interactive guided meditation and therapeutic yoga programs tailored to stress and chronic ailment recovery.

---

## 🏗️ Technical Stack

| Component | Technology |
|---|---|
| **Backend Framework** | Python 3.11+, Flask 3.1.2 |
| **Database & Persistence** | SQLite (SQLAlchemy / Raw SQL Engine) with automatic sync & in-memory caching |
| **Realtime WebSockets** | Flask-SocketIO & Web Speech API |
| **AI & LLM Services** | Groq API (`llama-3.3-70b-versatile`), Google Cloud Vision API |
| **PDF Generation** | FPDF2 & Custom Vector Rendering |
| **Security & Auth** | Flask-Login, Werkzeug Security (PBKDF2/SHA256), CSRF Protection, HTTPS/SSL |
| **Frontend & UI** | Vanilla JS (ES6+), Tailwind CSS CDN, FontAwesome 6 Pro, Animate.css, Glassmorphism design |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.10+ (Recommended: Python 3.11, 3.12, or 3.13)
* `git` and `pip`

### 2. Clone the Repository
```bash
git clone https://github.com/your-username/spherixclinic.git
cd spherixclinic
```

### 3. Create & Activate Virtual Environment
```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Configuration
Create a `.env` file in the root directory (or copy from `.env.example`):
```env
# Flask Settings
SECRET_KEY=spherix_super_secure_key_2026
FLASK_ENV=development
DEBUG=True

# Groq AI Key (Required for Symptom Checker & AI Doctors)
GROQ_API_KEY=your_groq_api_key_here

# Google Cloud Vision (Optional for Computer Vision & Radiology)
GOOGLE_VISION_API_KEY=your_google_vision_api_key_here
ENABLE_IMAGE_ANALYSIS=true

# Email Service (Optional for auto-sending PDF reports)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### 6. Run the Application
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Default Portal Credentials (Demo Mode)

| Portal | Email / Identifier | Password | Access URL |
|---|---|---|---|
| **System Administrator (Dr. Sunny Kushwaha)** | `admin@spherixclinic.com` | `Admin@123` | `/admin/login` or `/doctor/login` |
| **Hospital Facility (SMCH)** | `hospital@spherixclinic.com` | `hospital123` | `/hospital/login` |
| **Staff (Reception)** | `staff@spherixclinic.com` | `Staff@123` | `/staff/login` |
| **Patient Portal** | *(Register instant account)* | *(Self-set)* | `/patient/login` |

---

## 📂 Project Directory Structure

```plaintext
spherixclinic/
├── app.py                     # Main Flask Application & Route Controllers
├── requirements.txt           # Python Package Dependencies
├── .env.example               # Sample Environment Variables
├── audit_logger.py            # Clinical & Administrative Audit Logger
├── symptoms_analyzer.py       # Groq & Heuristic Clinical Symptom Engine
├── drug_data.py               # Pharmaceutical Database & Dosage Index
├── countries_data.py          # Medical Visa & Travel Desk Registry
├── knowledge_base.json        # 48+ Indexed Diseases & Condition Mapping
├── static/
│   ├── css/                   # Stylesheets & Glassmorphism Utilities
│   ├── js/                    # Client-side Controllers & SocketIO
│   └── uploads/               # User Radiographs & Clinical Uploads
└── templates/                 # 40+ Jinja2 Healthcare Templates
    ├── login_landing.html     # Multi-Role Access Gateway
    ├── patient_dashboard.html # Patient Health Record & Telemetry
    ├── admin_dashboard.html   # Root Administrator Analytics
    ├── staff_reception_dashboard.html # Reception & Token Desk
    ├── staff_nursing_dashboard.html   # Nurse Station & MAR
    ├── staff_bed_dashboard.html       # Bed Allocation Matrix
    ├── staff_blood_dashboard.html     # Blood Bank Telemetry
    ├── hospital_detail.html   # Hospital Profile & Travel Sidebar
    ├── symptom_result.html    # AI Clinical Diagnostic Assessment
    └── medical_shop.html      # Digital Pharmacy Storefront
```

---

## 🛡️ License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

## 🩺 Developed for Next-Gen Healthcare
**Spherix Clinic** — *Empowering patients and clinicians with cutting-edge artificial intelligence and unified hospital operations.*
