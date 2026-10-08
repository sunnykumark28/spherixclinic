# 🏥 Spherix Clinic — AI-Powered Smart Healthcare & Hospital Management Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Groq AI](https://img.shields.io/badge/AI%20Engine-Groq%20LLaMA%203.3%2070B-F05A28?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)
[![Google Vision](https://img.shields.io/badge/Computer%20Vision-Google%20Cloud%20Vision-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/vision)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind%20CSS%20%2B%20Glassmorphism-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**Spherix Clinic** is an enterprise-grade, AI-driven healthcare intelligence and hospital operations ecosystem. Engineered with a modular Flask blueprint architecture, Spherix Clinic unifies multi-modal clinical AI diagnostics, comprehensive electronic health records (EHR), multi-role administrative workflows, real-time ICU and bed telemetry, pathology laboratory automation, e-pharmacy with 250k+ medicines, and international medical travel desks — wrapped in a modern, responsive glassmorphic user interface.

---

## 🌟 Key Highlights & Feature Matrix

### 🧠 1. Multi-Modal AI Clinical Diagnostic Suite
* **Interactive Symptom Checker**: Multi-step diagnostic workflow with body region mapping, pain intensity rating, duration qualifiers, secondary symptom refinement, and emergency triage warnings.
* **Radiology AI Scanner**: Preliminary automated classification and visual feature analysis of Chest X-Rays, CT Scans, and MRI imaging powered by Google Cloud Vision and Groq LLMs.
* **Dermatology AI Analysis**: Computer vision skin lesion classification, rash inspection, and clinical severity index estimation.
* **Prescription OCR & Drug Interaction Intelligence**: Instant extraction of medication names, dosages, and schedules from handwritten or printed prescriptions with cross-referenced openFDA/Groq drug conflict checks.
* **AyurGenix AI**: Evidence-backed synthesis of traditional Ayurvedic formulations with modern allopathic pharmaceutical profiles.
* **Cancer Screening Intelligence**: Early-risk indicator assessment across oncological symptom matrices.
* **Automated PDF Diagnostic Reports & Email Delivery**: Instant vector PDF report generation with QR verification and automatic transactional email dispatch to patients.

---

### 🔬 2. Pathology & Diagnostic Laboratory Management
* **Comprehensive Test Catalog**: Pre-configured registry of 500+ pathology, biochemistry, hematology, and radiology investigations with reference intervals.
* **Pathology Center Portal**: Dedicated dashboard for pathology centers to manage walk-in lab bookings, update sample statuses (Collected, Processing, Completed), and input test parameters.
* **AI-Assisted Lab Analysis**: Automatic abnormal value highlighting, flag markers (High/Low/Critical), and clinician-ready diagnostic summaries.
* **Downloadable Test Reports**: Standardized patient diagnostic slips and multi-panel PDF reports with electronic validation stamps.

---

### 🏛️ 3. Multi-Role Healthcare Workspaces

```
                               ┌─────────────────────────┐
                               │   Spherix Clinic Core   │
                               └────────────┬────────────┘
         ┌───────────────────┬──────────────┼──────────────┬───────────────────┐
         │                   │              │              │                   │
┌────────▼────────┐ ┌────────▼────────┐ ┌───▼────┐ ┌───────▼────────┐ ┌────────▼────────┐
│ Patient Portal  │ │ Doctor Desk     │ │ Admin  │ │ Hospital Desk  │ │ Pathology Lab   │
│ - Health Vitals │ │ - Live OPD Queue│ │ - Audit│ │ - Reception    │ │ - Test Booking  │
│ - Appointments  │ │ - e-Prescribe   │ │ - Roles│ │ - Nurse Station│ │ - Specimen Track│
│ - Lab Reports   │ │ - Consultations │ │ - Stats│ │ - Bed / ICU    │ │ - AI Lab Report │
│ - Medicine Cart │ │ - Clinical Notes│ │ - Sync │ │ - Blood / Organ│ │ - Verification  │
└─────────────────┘ └─────────────────┘ └────────┘ └────────────────┘ └─────────────────┘
```

* **Patient Portal**: Profile & medical history management, live vital signs tracking, appointment booking, e-prescription vault, and live queue status.
* **Doctor Workspace**: Interactive OPD appointment queues, telemedicine scheduling, digital e-prescriptions, clinical notes, and live chat telemetry.
* **Hospital & Staff Dashboards**:
  * **Reception Desk**: Walk-in token generation, real-time queue broadcasting with Web Speech API audio chimes, and instant print slips.
  * **Nursing Station**: Patient acuity stratification (Stable / Guarded / Critical), digital Medication Administration Record (MAR), and vitals telemetry.
  * **Bed & Ward Management**: Real-time room occupancy grid, ICU vs. General Ward availability meters, and 1-click bed transfers.
  * **Blood Bank & Donor Hub**: Real-time blood unit inventory by group (A+, B+, O+, AB+, etc.), surplus tracking, and donor registration.
  * **Organ Donor Registry**: Confidential matching registry for organ donors and recipient waitlists.
* **System Administrator (Root Portal)**: System health telemetry, role delegation, database migrations, security audit logs, and global emergency broadcast banners.

---

### 💊 4. Digital Pharmacy & Wellness E-Commerce
* **Extensive Drug Catalog**: Over 250,000+ indexed pharmaceutical products, composition mappings, side effects, and alternative generics.
* **Prescription Upload & Verification**: Digital verification flow for prescription-only pharmaceuticals.
* **Cart & Checkout Engine**: Multi-item cart, Razorpay payment gateway integration, and multi-currency formatting (USD, INR, EUR, GBP, AED).
* **Automated PDF Invoices**: Itemized tax invoices with unique order tracking numbers and automatic email receipts.
* **Zen Yoga & Holistic Health Hub**: Curated wellness routines, guided meditation timers, and AI-personalized nutrition & fitness planners.

---

### 🌍 5. Global Medical Travel & Hospital Discovery
* **International Hospital Directory**: Filter hospitals by specialty, accreditation, bed capacity, ICU availability, and daily tariffs.
* **Medical Visa & Travel Concierge**: Dedicated drawer for visa clearance assistance, multilingual translator requests, and airport transport coordination.

---

## 🏗️ Technical Stack & Architecture

| Layer | Technology | Details |
|---|---|---|
| **Backend Framework** | Python 3.11+, Flask 3.1.2 | Modular Blueprint architecture (`spherix/routes/`) |
| **Data & Persistence** | SQLite / SQLAlchemy Engine | Automated schema migrations, in-memory caching (`TEMP_DATA`) |
| **Realtime & Audio** | Flask-SocketIO & Web Speech API | Live OPD queue broadcast, token callouts, WebSocket updates |
| **AI & LLM Services** | Groq API (`llama-3.3-70b-versatile`) | Symptom analysis, differential diagnosis, medical summarization |
| **Computer Vision** | Google Cloud Vision API | Skin lesion analysis, X-ray scanning, Prescription OCR |
| **Document Engine** | FPDF2 | Clinical lab reports, e-prescriptions, and tax invoices |
| **Security & Auth** | Flask-Login, Flask-WTF (CSRF), Flask-Talisman, Flask-Limiter, PBKDF2/SHA-256 | HTTPS/TLS enforcement, OAuth (Google/Apple), rate limiting |
| **Frontend & UI** | Vanilla JS (ES6+), Tailwind CSS, FontAwesome 6, Animate.css | Glassmorphism UI, dual-currency switcher, responsive layout |

---

## 📂 Project Directory Structure

```plaintext
spherixclinic/
├── app.py                         # Application entrypoint & SSL / SocketIO bootstrap
├── config.py                      # Global configuration, currencies, exchange rates
├── extensions.py                  # Initialized Flask extensions (Login, SocketIO, CSRF, etc.)
├── requirements.txt               # Python package dependencies
├── .env.example                   # Environment configuration template
│
├── spherix/                       # Core Application Package
│   ├── __init__.py                # App factory (create_app), blueprints, filters & error handlers
│   ├── models/                    # Data models & schemas
│   │   ├── user.py                # Patient, Doctor, Staff, Hospital, Admin models
│   │   ├── clinical.py            # Appointment, Vitals, BedBooking, BloodDonor, OrganDonor
│   │   └── commerce.py            # Order, Review, Message, Notification, ActivityLog
│   ├── routes/                    # Modular Flask Blueprints
│   │   ├── admin.py               # Root admin operations & telemetry
│   │   ├── auth.py                # Multi-role authentication & OAuth
│   │   ├── blood_organ.py         # Blood bank & organ donor registry
│   │   ├── clinical_ai.py         # Symptom checker, Vision, OCR, AyurGenix, Cancer AI
│   │   ├── diagnostic.py          # Diagnostic test booking & reports
│   │   ├── doctor.py              # Doctor workspace, queue, e-prescriptions
│   │   ├── hospital.py            # Hospital profile & ward management
│   │   ├── main.py                # Public landing, medical travel, emergency SOS
│   │   ├── pathology.py           # Pathology center portal & test processing
│   │   ├── patient.py             # Patient dashboard & health records
│   │   ├── pharmacy.py            # E-Pharmacy storefront, cart & checkout
│   │   └── staff.py               # Reception, Nursing (MAR), and Bed desks
│   └── services/                  # Business logic & external integrations
│       ├── ai_service.py          # Groq AI LLM orchestration
│       ├── diagnostic_ai.py       # Diagnostic and radiology AI processing
│       ├── diagnostic_catalog.py  # 500+ diagnostic test catalog definitions
│       ├── diagnostic_db.py       # Pathology database operations
│       ├── mail_service.py        # Transactional email dispatcher (SMTP)
│       ├── nutrition_fitness_service.py # AI personalized diet & fitness plans
│       ├── payment_service.py     # Razorpay payment handler
│       ├── pdf_service.py         # FPDF2 clinical & invoice document builder
│       └── upload_service.py      # Secure file & image upload handler
│
├── static/                        # Static assets
│   ├── css/                       # Glassmorphism design system & utility stylesheets
│   ├── js/                        # Client-side scripts, WebSockets, OCR & queue chimes
│   └── uploads/                   # Radiographs, prescriptions & user attachments
│
└── templates/                     # 50+ Jinja2 Healthcare & Portal Templates
    ├── layout.html                # Base layout with navigation & glassmorphic theme
    ├── index.html                 # Homepage with live search & AI quick-check
    ├── doctor.html                # Doctor workspace & live consultation room
    ├── patient_dashboard.html     # Patient health profile & clinical records
    ├── pathology_dashboard.html   # Pathology lab management console
    ├── staff_reception_dashboard.html # Token desk & patient queue
    ├── staff_nursing_dashboard.html   # Nurse station with digital MAR
    ├── staff_bed_dashboard.html       # Live ICU & Ward bed grid
    ├── staff_blood_dashboard.html     # Blood bank inventory telemetry
    ├── symptom_checker.html       # Multi-step AI clinical symptom checker
    ├── medical_shop.html          # Online pharmacy catalog
    └── admin_dashboard.html       # Super admin analytics & system control
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* **Python**: `3.11`, `3.12`, or `3.13`
* **Git** & **Pip**

### 2. Clone the Repository
```bash
git clone https://github.com/sunnykumark28/spherixclinic.git
cd spherixclinic
```

### 3. Set Up Virtual Environment
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

### 5. Configure Environment Variables
Create a `.env` file in the root directory by copying `.env.example`:
```bash
cp .env.example .env
```

Configure your secrets in `.env`:
```env
# Core Flask Settings
SECRET_KEY=generate_a_secure_random_32_byte_secret_key
FLASK_ENV=development
FLASK_DEBUG=False
FLASK_PORT=5001

# AI & Multimodal Credentials
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_VISION_API_KEY=your_google_cloud_vision_key_here
ENABLE_IMAGE_ANALYSIS=true

# Security & HTTPS
USE_SSL=True
SSL_CERT_PATH=ssl/cert.pem
SSL_KEY_PATH=ssl/key.pem

# Email Service (Optional for transactional PDF dispatches)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-clinic-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password

# Payment Gateway (Optional for pharmacy checkouts)
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret

# Initial Portal Bootstrap Credentials
ADMIN_BOOTSTRAP_PASSWORD=your-super-admin-password
HOSPITAL_BOOTSTRAP_PASSWORD=your-hospital-admin-password
```

### 6. Run the Application
```bash
python app.py
```

* The system automatically provisions a self-signed SAN SSL certificate if missing.
* Access the platform at: **`https://localhost:5001`** (or `http://localhost:5001` if SSL is disabled).

---

## 🔑 Access Portals & Role Endpoints

| Portal | Role | Access URL | Description |
|---|---|---|---|
| **System Admin** | Super Administrator | `/admin/login` | Platform telemetry, audit trail, role provisioning |
| **Doctor Workspace** | Medical Practitioner | `/doctor/login` | OPD queue, consultations, e-prescriptions |
| **Patient Portal** | Patient / User | `/patient/login` | Health vitals, appointments, reports & orders |
| **Pathology Center** | Lab Technician / Center | `/pathology/login` | Diagnostic test queue, sample processing & reports |
| **Hospital Facility** | Hospital Administrator | `/hospital/login` | Ward occupancy, emergency bed bookings & staff |
| **Reception Desk** | Hospital Staff | `/staff/reception` | Walk-in tokens, public queue audio broadcaster |
| **Nursing Station** | Nursing Staff | `/staff/nursing` | Patient acuity, digital MAR, vital telemetry |
| **Bed Management** | Ward Staff | `/staff/beds` | ICU and general ward occupancy grid |
| **Blood Bank** | Blood Bank Manager | `/staff/blood` | Unit inventory by blood group & donor records |

---

## 🛡️ Security & Compliance Features
* **Encryption**: TLS 1.2 / TLS 1.3 HTTPS enforcement with HTTP Strict Transport Security (HSTS).
* **Password Hashing**: Cryptographically secure PBKDF2/SHA-256 password hashing via Werkzeug.
* **Request Guardrails**: CSRF token validation on all POST/PUT requests, Content Security Policy (CSP) headers, and IP-level rate limiting with Flask-Limiter.
* **Audit Trails**: Real-time logging of clinical actions, authentication events, and administrative overrides.

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).

---

<p align="center">
  <b>Spherix Clinic</b> — <i>Pioneering the Future of Intelligent Healthcare Systems.</i>
</p>
