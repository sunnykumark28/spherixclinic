"""
Spherix Insurance Database Layer - Financial Protection Division of Spherix Clinic
Multi-tenant, thread-safe SQLite schema and data service for Life Insurance Partners,
Products, Quotations, Applications, Nominees, Documents, Consents, Policies, Payments,
Transactions, Claims Assistance, Grievances, and Regulatory Audit Logs.
"""

import os
import json
import sqlite3
import secrets
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

def get_db_path() -> str:
    """Returns the configured database file path, honoring test and custom environments."""
    is_serverless = bool(os.getenv('VERCEL') or os.getenv('SERVERLESS') or os.getenv('AWS_LAMBDA_FUNCTION_NAME') or os.getenv('LAMBDA_TASK_ROOT'))
    if is_serverless and os.path.exists('/tmp/spherixclinic.db'):
        return '/tmp/spherixclinic.db'
    return (
        os.getenv('INSURANCE_DB_PATH') or
        os.getenv('DIAGNOSTIC_DB_PATH') or
        os.getenv('SQLITE_DB_PATH') or
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'spherixclinic.db')
    )

def get_insurance_db() -> sqlite3.Connection:
    """Returns a SQLite connection with row factory configured as dictionary-like Row."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=60.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 60000")
        conn.execute("PRAGMA synchronous = NORMAL")
    except Exception:
        pass
    return conn

def dict_from_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)

def dict_list_from_rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]

# ==============================================================================
# 1. DATABASE INITIALIZATION & SCHEMA CREATION
# ==============================================================================

def init_insurance_schema():
    """Initializes and migrates all Life Insurance tables, indexes, and constraints."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    # 1. Insurance Partners (Authorized IRDAI Life Insurers)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_partners (
        id TEXT PRIMARY KEY,
        legal_name TEXT NOT NULL,
        brand_name TEXT NOT NULL,
        irda_reg_no TEXT NOT NULL,
        cin_number TEXT,
        logo_url TEXT,
        website TEXT,
        contact_email TEXT,
        phone TEXT,
        toll_free TEXT,
        claim_settlement_ratio REAL DEFAULT 99.0,
        solvency_ratio REAL DEFAULT 2.0,
        grievance_email TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Insurance Products
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_products (
        id TEXT PRIMARY KEY,
        partner_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        product_code TEXT UNIQUE NOT NULL,
        uin_number TEXT NOT NULL,
        category TEXT NOT NULL, -- 'Term Life', 'Whole Life', 'Savings', 'Family Protection'
        tagline TEXT,
        min_sum_insured REAL DEFAULT 2500000.0,
        max_sum_insured REAL DEFAULT 100000000.0,
        default_sum_insured REAL DEFAULT 10000000.0,
        min_entry_age INTEGER DEFAULT 18,
        max_entry_age INTEGER DEFAULT 65,
        max_maturity_age INTEGER DEFAULT 85,
        min_term_years INTEGER DEFAULT 10,
        max_term_years INTEGER DEFAULT 40,
        allowed_frequencies TEXT DEFAULT 'ANNUAL,SEMI_ANNUAL,QUARTERLY,MONTHLY',
        base_annual_rate_per_lakh REAL NOT NULL,
        smoker_surcharge_pct REAL DEFAULT 45.0,
        female_discount_pct REAL DEFAULT 10.0,
        key_benefits TEXT, -- JSON array
        exclusions TEXT,   -- JSON array
        important_conditions TEXT, -- JSON array
        brochure_url TEXT,
        terms_url TEXT,
        is_active INTEGER DEFAULT 1,
        is_featured INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (partner_id) REFERENCES insurance_partners(id) ON DELETE CASCADE
    )
    """)

    # 3. Insurance Product Versions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_product_versions (
        id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        version_number TEXT NOT NULL,
        effective_from DATE,
        effective_to DATE,
        rules_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES insurance_products(id) ON DELETE CASCADE
    )
    """)

    # 4. Insurance Quotations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_quotations (
        id TEXT PRIMARY KEY,
        quote_number TEXT UNIQUE NOT NULL,
        patient_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        partner_id TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        is_smoker INTEGER DEFAULT 0,
        annual_income REAL DEFAULT 0.0,
        sum_insured REAL NOT NULL,
        policy_term_years INTEGER NOT NULL,
        premium_frequency TEXT NOT NULL,
        base_premium REAL NOT NULL,
        gst_amount REAL NOT NULL,
        total_premium REAL NOT NULL,
        breakdown_json TEXT,
        is_confirmed INTEGER DEFAULT 0,
        valid_until TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES insurance_products(id) ON DELETE CASCADE,
        FOREIGN KEY (partner_id) REFERENCES insurance_partners(id) ON DELETE CASCADE
    )
    """)

    # 5. Insurance Applications
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_applications (
        id TEXT PRIMARY KEY,
        application_number TEXT UNIQUE NOT NULL,
        patient_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        partner_id TEXT NOT NULL,
        quotation_id TEXT,
        status TEXT DEFAULT 'DRAFT', -- 'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'ADDITIONAL_INFO_REQUIRED', 'APPROVED', 'PAYMENT_PENDING', 'ACTIVE', 'REJECTED', 'EXPIRED', 'CANCELLED'
        current_step INTEGER DEFAULT 1,
        personal_info_json TEXT,
        insurance_details_json TEXT,
        nominee_info_json TEXT,
        declarations_json TEXT,
        insurer_application_ref TEXT,
        underwriting_decision TEXT,
        insurer_remarks TEXT,
        rejection_reason TEXT,
        submitted_at TIMESTAMP,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES insurance_products(id) ON DELETE CASCADE,
        FOREIGN KEY (partner_id) REFERENCES insurance_partners(id) ON DELETE CASCADE
    )
    """)

    # 6. Insurance Nominees
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_nominees (
        id TEXT PRIMARY KEY,
        application_id TEXT NOT NULL,
        policy_id TEXT,
        patient_id TEXT NOT NULL,
        full_name TEXT NOT NULL,
        relationship TEXT NOT NULL,
        date_of_birth TEXT NOT NULL,
        contact_phone TEXT,
        contact_email TEXT,
        share_percentage REAL DEFAULT 100.0,
        is_minor INTEGER DEFAULT 0,
        appointee_name TEXT,
        appointee_relation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (application_id) REFERENCES insurance_applications(id) ON DELETE CASCADE
    )
    """)

    # 7. Insurance Documents
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_documents (
        id TEXT PRIMARY KEY,
        application_id TEXT,
        policy_id TEXT,
        patient_id TEXT NOT NULL,
        doc_type TEXT NOT NULL, -- 'IDENTITY_PROOF', 'ADDRESS_PROOF', 'INCOME_PROOF', 'MEDICAL_REPORT', 'POLICY_SCHEDULE', 'RECEIPT'
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        original_name TEXT,
        mime_type TEXT,
        file_size INTEGER,
        verification_status TEXT DEFAULT 'PENDING',
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Insurance Consents
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_consents (
        id TEXT PRIMARY KEY,
        application_id TEXT NOT NULL,
        patient_id TEXT NOT NULL,
        consent_type TEXT NOT NULL,
        consent_text TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        is_accepted INTEGER DEFAULT 1,
        accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (application_id) REFERENCES insurance_applications(id) ON DELETE CASCADE
    )
    """)

    # 9. Insurance Policies (Migrate existing table safely or create if missing)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_insurance_policies (
        id TEXT PRIMARY KEY,
        policy_number TEXT UNIQUE NOT NULL,
        uin_number TEXT NOT NULL,
        application_id TEXT,
        patient_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        partner_id TEXT NOT NULL,
        sum_insured REAL NOT NULL,
        premium_amount REAL NOT NULL,
        premium_frequency TEXT DEFAULT 'ANNUAL',
        policy_start_date DATE NOT NULL,
        policy_expiry_date DATE NOT NULL,
        next_premium_due_date DATE NOT NULL,
        status TEXT DEFAULT 'ACTIVE', -- 'ACTIVE', 'EXPIRED', 'CANCELLED', 'SURRENDERED'
        insurer_policy_ref TEXT,
        policy_document_path TEXT,
        verification_hash TEXT,
        nominee_name TEXT,
        nominee_relation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES insurance_products(id),
        FOREIGN KEY (partner_id) REFERENCES insurance_partners(id)
    )
    """)

    # Also ensure legacy insurance_policies table has compatibility columns
    try:
        cursor.execute("SELECT id FROM insurance_policies LIMIT 1")
    except Exception:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS insurance_policies (
            id TEXT PRIMARY KEY,
            policy_name TEXT,
            provider TEXT,
            sum_insured REAL,
            annual_premium REAL,
            network_hospitals_count INTEGER,
            claim_settlement_ratio REAL,
            key_benefits TEXT
        )
        """)

    # 10. Insurance Payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_payments (
        id TEXT PRIMARY KEY,
        payment_number TEXT UNIQUE NOT NULL,
        policy_id TEXT,
        application_id TEXT,
        patient_id TEXT NOT NULL,
        transaction_ref TEXT NOT NULL,
        gateway_order_id TEXT,
        gateway_payment_id TEXT,
        amount REAL NOT NULL,
        gst_amount REAL DEFAULT 0.0,
        total_amount REAL NOT NULL,
        payment_frequency TEXT DEFAULT 'ANNUAL',
        payment_method TEXT DEFAULT 'ONLINE',
        status TEXT DEFAULT 'PENDING', -- 'PENDING', 'SUCCESS', 'FAILED', 'REFUNDED'
        gateway_response_json TEXT,
        receipt_number TEXT UNIQUE,
        paid_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 11. Insurance Transactions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_transactions (
        id TEXT PRIMARY KEY,
        payment_id TEXT NOT NULL,
        transaction_type TEXT DEFAULT 'PREMIUM',
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        gateway_ref TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (payment_id) REFERENCES insurance_payments(id) ON DELETE CASCADE
    )
    """)

    # 12. Insurance Claim Assistances
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_claim_assistances (
        id TEXT PRIMARY KEY,
        claim_number TEXT UNIQUE NOT NULL,
        policy_id TEXT NOT NULL,
        patient_id TEXT NOT NULL,
        claimant_name TEXT NOT NULL,
        claimant_relation TEXT NOT NULL,
        claimant_phone TEXT NOT NULL,
        claimant_email TEXT,
        claim_type TEXT NOT NULL, -- 'DEATH_CLAIM', 'CRITICAL_ILLNESS', 'TERMINAL_ILLNESS', 'ACCIDENTAL_DISABILITY'
        incident_date DATE NOT NULL,
        hospital_name TEXT,
        diagnosis_summary TEXT,
        status TEXT DEFAULT 'REQUESTED', -- 'REQUESTED', 'DOCUMENTS_PENDING', 'UNDER_INSURER_REVIEW', 'APPROVED', 'SETTLED', 'REJECTED'
        insurer_claim_ref TEXT,
        tracking_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (policy_id) REFERENCES patient_insurance_policies(id)
    )
    """)

    # 13. Insurance Complaints / Grievance Redressal
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_complaints (
        id TEXT PRIMARY KEY,
        ticket_number TEXT UNIQUE NOT NULL,
        patient_id TEXT NOT NULL,
        policy_id TEXT,
        subject TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'OPEN', -- 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'
        resolution_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 14. Insurance Webhook Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_webhook_events (
        id TEXT PRIMARY KEY,
        partner_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        signature TEXT,
        processed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 15. Insurance Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_audit_logs (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        action TEXT NOT NULL,
        details_json TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create Performance Indexes
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_app_patient ON insurance_applications (patient_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_app_number ON insurance_applications (application_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_pol_patient ON patient_insurance_policies (patient_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_pol_number ON patient_insurance_policies (policy_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_pay_patient ON insurance_payments (patient_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_claim_patient ON insurance_claim_assistances (patient_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ins_audit_entity ON insurance_audit_logs (entity_type, entity_id)")
    except Exception as idx_err:
        print(f"Insurance index creation note: {idx_err}")

    # Seed verified IRDAI partners and life products
    seed_insurance_partners_and_products(cursor)

    conn.commit()
    conn.close()

# ==============================================================================
# 2. SEED DATA: AUTHORIZED IRDAI LIFE INSURERS & VERIFIED PRODUCTS
# ==============================================================================

SEED_PARTNERS = [
    {
        "id": "INS-PARTNER-SLIC",
        "legal_name": "Spherix Life Insurance Corporation Limited",
        "brand_name": "Spherix Life Insurance Corporation (SLIC)",
        "irda_reg_no": "SLIC-IRDAI-2026-888",
        "cin_number": "U66010DL2026PLC987654",
        "logo_url": "/static/images/spherix-logo.png",
        "website": "https://slic.spherixclinic.com",
        "contact_email": "care@slic.spherixclinic.com",
        "phone": "+91 11 4988 7700",
        "toll_free": "1800 266 8888",
        "claim_settlement_ratio": 99.85,
        "solvency_ratio": 2.25,
        "grievance_email": "gro@slic.spherixclinic.com"
    }
]

SEED_PRODUCTS = [
    {
        "id": "PROD-SLIC-SHIELD",
        "partner_id": "INS-PARTNER-SLIC",
        "product_name": "SLIC Suraksha Supreme Term Shield",
        "product_code": "SLIC-TERM-SHIELD-01",
        "uin_number": "SLIC101N001V01",
        "category": "Term Life",
        "tagline": "Pure risk high-cover financial protection with built-in critical illness cover and zero-cost return of premium option.",
        "min_sum_insured": 5000000.0,
        "max_sum_insured": 100000000.0,
        "default_sum_insured": 10000000.0,
        "min_entry_age": 18,
        "max_entry_age": 65,
        "max_maturity_age": 85,
        "min_term_years": 10,
        "max_term_years": 40,
        "allowed_frequencies": "ANNUAL,SEMI_ANNUAL,QUARTERLY,MONTHLY",
        "base_annual_rate_per_lakh": 9.50, # ~9500 INR for 1 Crore at age 30
        "smoker_surcharge_pct": 50.0,
        "female_discount_pct": 10.0,
        "key_benefits": [
            "Up to ₹10 Crore pure life protection backed directly by Spherix Life Insurance Corporation (SLIC)",
            "Instant cashless hospitalization integration at all Spherix Network Hospitals & Partner Centers",
            "Zero-Cost Life Option: exit policy and receive 100% of standard premiums paid back at retirement",
            "Built-in Terminal Illness Benefit releasing up to ₹2 Crore upfront upon medical certification",
            "Tax exemption on premiums under Sec 80C and death claim payouts under Sec 10(10D)"
        ],
        "exclusions": [
            "Suicide exclusion within 12 months from policy inception or revival date",
            "Intentional self-inflicted injury or participation in unlawful acts",
            "Active engagement in armed hostilities or hazardous adventure sports without prior disclosure"
        ],
        "important_conditions": [
            "30-day statutory Free-Look period with 100% full refund guarantee",
            "Grace period of 30 days for annual, half-yearly and quarterly modes (15 days for monthly mode)",
            "Section 45 indisputability clause applies after 3 years from commencement"
        ],
        "brochure_url": "/patient/insurance/brochure/PROD-SLIC-SHIELD",
        "terms_url": "/patient/insurance/terms/PROD-SLIC-SHIELD",
        "is_featured": 1
    },
    {
        "id": "PROD-SLIC-PARIVAR",
        "partner_id": "INS-PARTNER-SLIC",
        "product_name": "SLIC Parivar Smart Protection Shield",
        "product_code": "SLIC-PARIVAR-SMART-02",
        "uin_number": "SLIC101N002V01",
        "category": "Family Protection",
        "tagline": "Comprehensive family financial security shielding primary earner, spouse, and child higher education milestones.",
        "min_sum_insured": 5000000.0,
        "max_sum_insured": 100000000.0,
        "default_sum_insured": 15000000.0,
        "min_entry_age": 18,
        "max_entry_age": 65,
        "max_maturity_age": 85,
        "min_term_years": 10,
        "max_term_years": 40,
        "allowed_frequencies": "ANNUAL,SEMI_ANNUAL,MONTHLY",
        "base_annual_rate_per_lakh": 9.20,
        "smoker_surcharge_pct": 48.0,
        "female_discount_pct": 12.0,
        "key_benefits": [
            "Covers both primary life insured and spouse under a single unified policy schedule",
            "Automatic waiver of premium on diagnosis of covered critical medical conditions",
            "Guaranteed monthly income benefit option for surviving family nominees",
            "Milestone life-stage protection increase on marriage and childbirth without fresh medical tests"
        ],
        "exclusions": [
            "Suicide within 12 months from the date of risk inception",
            "Drug or substance abuse, civil commotion, or nuclear contamination",
            "Breach of criminal law with malicious intent"
        ],
        "important_conditions": [
            "30-day Free-Look cancellation with full premium refund less stamp duty charges",
            "Mandatory identity and financial underwriting verification before risk inception",
            "Digital KYC and tele-medical examination available for eligible applicants"
        ],
        "brochure_url": "/patient/insurance/brochure/PROD-SLIC-PARIVAR",
        "terms_url": "/patient/insurance/terms/PROD-SLIC-PARIVAR",
        "is_featured": 1
    },
    {
        "id": "PROD-SLIC-AROGYA",
        "partner_id": "INS-PARTNER-SLIC",
        "product_name": "SLIC Arogya Raksha Dual Health & Life Shield",
        "product_code": "SLIC-AROGYA-DUAL-03",
        "uin_number": "SLIC101N003V01",
        "category": "Term Life",
        "tagline": "Dual shield covering 64 critical medical emergencies with lump-sum payout while retaining 100% life protection.",
        "min_sum_insured": 5000000.0,
        "max_sum_insured": 50000000.0,
        "default_sum_insured": 10000000.0,
        "min_entry_age": 18,
        "max_entry_age": 60,
        "max_maturity_age": 85,
        "min_term_years": 10,
        "max_term_years": 40,
        "allowed_frequencies": "ANNUAL,SEMI_ANNUAL,MONTHLY",
        "base_annual_rate_per_lakh": 9.80,
        "smoker_surcharge_pct": 45.0,
        "female_discount_pct": 10.0,
        "key_benefits": [
            "Integrated critical illness coverage for 64 critical medical conditions including cardiac and oncology",
            "Lump sum critical illness payout without reducing policyholder life cover death benefit",
            "Return of Premium (ROP) feature that returns 100% of standard premiums at maturity",
            "Direct emergency claim financial assistance within 48 hours for verified claims"
        ],
        "exclusions": [
            "Suicide claim within 1 year of policy issuance",
            "Aviation accident unless flying as a commercial fare-paying passenger",
            "Pre-existing illnesses not disclosed at the time of proposal"
        ],
        "important_conditions": [
            "Proof of income mandatory for sum insured exceeding ₹1 Crore",
            "30-day Free-Look provision for online and tele-sale policies",
            "Prompt notification to insurer within 90 days of claim incident"
        ],
        "brochure_url": "/patient/insurance/brochure/PROD-SLIC-AROGYA",
        "terms_url": "/patient/insurance/terms/PROD-SLIC-AROGYA",
        "is_featured": 0
    },
    {
        "id": "PROD-SLIC-JEEVAN",
        "partner_id": "INS-PARTNER-SLIC",
        "product_name": "SLIC Jeevan Amrit Whole Life Cover",
        "product_code": "SLIC-JEEVAN-WHOLE-04",
        "uin_number": "SLIC101N004V01",
        "category": "Whole Life",
        "tagline": "Lifetime financial protection safeguarding your family up to 100 years of age with inheritance estate transfer.",
        "min_sum_insured": 5000000.0,
        "max_sum_insured": 50000000.0,
        "default_sum_insured": 10000000.0,
        "min_entry_age": 18,
        "max_entry_age": 65,
        "max_maturity_age": 100,
        "min_term_years": 15,
        "max_term_years": 50,
        "allowed_frequencies": "ANNUAL,SEMI_ANNUAL,MONTHLY",
        "base_annual_rate_per_lakh": 14.20,
        "smoker_surcharge_pct": 40.0,
        "female_discount_pct": 8.0,
        "key_benefits": [
            "Whole Life option ensuring financial legacy and family security up to age 100",
            "Tax-free wealth inheritance payout to designated nominees under Section 10(10D)",
            "Inbuilt Terminal Illness Benefit providing up to 50% accelerated sum assured",
            "Premium payment term flexibility (Pay for 5, 10, 12 years or regular pay)"
        ],
        "exclusions": [
            "Suicide committed within 12 months from policy inception",
            "Self-inflicted harm or injury while sane or insane",
            "Active service in military or naval operations during declared warfare"
        ],
        "important_conditions": [
            "Nominee details and KYC required at time of application",
            "30-day Free Look cancellation rights",
            "Grace period applicable for non-forfeiture benefits"
        ],
        "brochure_url": "/patient/insurance/brochure/PROD-SLIC-JEEVAN",
        "terms_url": "/patient/insurance/terms/PROD-SLIC-JEEVAN",
        "is_featured": 1
    },
    {
        "id": "PROD-SLIC-BHAVISHYA",
        "partner_id": "INS-PARTNER-SLIC",
        "product_name": "SLIC Bhavishya Dhan Guaranteed Savings Plan",
        "product_code": "SLIC-BHAVISHYA-SAVINGS-05",
        "uin_number": "SLIC101N005V01",
        "category": "Savings",
        "tagline": "Non-participating savings life insurance providing guaranteed life cover and assured regular returns.",
        "min_sum_insured": 1000000.0,
        "max_sum_insured": 20000000.0,
        "default_sum_insured": 2500000.0,
        "min_entry_age": 18,
        "max_entry_age": 60,
        "max_maturity_age": 80,
        "min_term_years": 10,
        "max_term_years": 30,
        "allowed_frequencies": "ANNUAL,SEMI_ANNUAL,QUARTERLY,MONTHLY",
        "base_annual_rate_per_lakh": 42.00,
        "smoker_surcharge_pct": 10.0,
        "female_discount_pct": 5.0,
        "key_benefits": [
            "Guaranteed financial protection with life cover throughout the policy term",
            "Guaranteed regular income payout up to 25 to 30 years after premium paying term",
            "Optional Return of Premium (ROP) upon completion of payout phase",
            "Tax-efficient dual benefit of insurance protection and guaranteed savings"
        ],
        "exclusions": [
            "Suicide exclusion clause within 12 months of commencement",
            "Non-disclosure of material medical history at proposal stage"
        ],
        "important_conditions": [
            "Fixed premium paying terms: 5, 6, 7, 8, 10 or 12 years",
            "Guaranteed additions accrue at the end of each policy year",
            "Surrender value available after payment of full premiums for at least two years"
        ],
        "brochure_url": "/patient/insurance/brochure/PROD-SLIC-BHAVISHYA",
        "terms_url": "/patient/insurance/terms/PROD-SLIC-BHAVISHYA",
        "is_featured": 0
    },
    {
        "id": "PROD-SLIC-DIGITAL",
        "partner_id": "INS-PARTNER-SLIC",
        "product_name": "SLIC Digital e-Shield Instant Term",
        "product_code": "SLIC-DIGITAL-ESHIELD-06",
        "uin_number": "SLIC101N006V01",
        "category": "Family Protection",
        "tagline": "100% digital tele-underwritten life cover designed for fast, paperless approval on Spherix Clinic.",
        "min_sum_insured": 5000000.0,
        "max_sum_insured": 50000000.0,
        "default_sum_insured": 10000000.0,
        "min_entry_age": 18,
        "max_entry_age": 65,
        "max_maturity_age": 85,
        "min_term_years": 10,
        "max_term_years": 35,
        "allowed_frequencies": "ANNUAL,SEMI_ANNUAL,MONTHLY",
        "base_annual_rate_per_lakh": 9.10,
        "smoker_surcharge_pct": 46.0,
        "female_discount_pct": 10.0,
        "key_benefits": [
            "Three plan options: Level Cover, Increasing Cover, and Level Cover with Future-Proofing",
            "Nominee monthly pension payout option for steady post-loss household maintenance",
            "Built-in terminal illness benefit for financial relief during critical palliative care",
            "Direct cryptographic policy issuance with instant PDF certificate download"
        ],
        "exclusions": [
            "Suicide committed within 12 months of policy issuance",
            "Breach of statutory laws or illegal activities",
            "War, invasion, civil unrest, or foreign enemy hostility"
        ],
        "important_conditions": [
            "Medical checkup based on applicant age, smoking status, and sum insured",
            "30-day Free-Look provision with direct refund to bank account",
            "Reinstatement permitted within 5 years from date of default"
        ],
        "brochure_url": "/patient/insurance/brochure/PROD-SLIC-DIGITAL",
        "terms_url": "/patient/insurance/terms/PROD-SLIC-DIGITAL",
        "is_featured": 0
    }
]

PRODUCT_ID_ALIASES = {
    # Core SLIC Product IDs
    'PROD-SLIC-SHIELD': 'PROD-SLIC-SHIELD',
    'PROD-SLIC-SURAKSHA': 'PROD-SLIC-SHIELD',
    'PROD-SLIC-PARIVAR': 'PROD-SLIC-PARIVAR',
    'PROD-SLIC-JEEVAN': 'PROD-SLIC-JEEVAN',
    'PROD-SLIC-BHAVISHYA': 'PROD-SLIC-BHAVISHYA',
    'PROD-SLIC-AROGYA': 'PROD-SLIC-AROGYA',
    'PROD-SLIC-DIGITAL': 'PROD-SLIC-DIGITAL',

    # Aliases mapping prior third-party insurer codes directly to SLIC plans:
    'PROD-HDFC-C2P': 'PROD-SLIC-SHIELD',
    'PROD-HDFC-CLICK2PROTECT': 'PROD-SLIC-SHIELD',
    'PROD-ICICI-IPROT': 'PROD-SLIC-PARIVAR',
    'PROD-ICICI-IPROTECT': 'PROD-SLIC-PARIVAR',
    'PROD-MAX-SECURE': 'PROD-SLIC-AROGYA',
    'PROD-MAX-SMART-WEALTH': 'PROD-SLIC-AROGYA',
    'PROD-TATAAIA-WHOLE': 'PROD-SLIC-JEEVAN',
    'PROD-TATA-SAMPOORNA': 'PROD-SLIC-JEEVAN',
    'PROD-HDFC-SANCHAY': 'PROD-SLIC-BHAVISHYA',
    'PROD-HDFC-SANCHAY-PAR': 'PROD-SLIC-BHAVISHYA',
    'PROD-SBILIFE-ESHIELD': 'PROD-SLIC-DIGITAL',
    'PROD-SBI-ESHIELD-NEXT': 'PROD-SLIC-DIGITAL',
}

def seed_insurance_partners_and_products(cursor=None):
    """Seeds Spherix Life Insurance Corporation (SLIC) and its verified life insurance products."""
    close_after = False
    if cursor is None:
        conn = get_insurance_db()
        cursor = conn.cursor()
        close_after = True

    # Migrate any foreign keys from old partners and products to SLIC
    cursor.execute("UPDATE insurance_quotations SET partner_id = 'INS-PARTNER-SLIC' WHERE partner_id != 'INS-PARTNER-SLIC'")
    cursor.execute("UPDATE insurance_applications SET partner_id = 'INS-PARTNER-SLIC' WHERE partner_id != 'INS-PARTNER-SLIC'")
    cursor.execute("UPDATE patient_insurance_policies SET partner_id = 'INS-PARTNER-SLIC' WHERE partner_id != 'INS-PARTNER-SLIC'")

    for old_id, new_id in PRODUCT_ID_ALIASES.items():
        if old_id != new_id:
            cursor.execute("UPDATE insurance_quotations SET product_id = ? WHERE product_id = ?", (new_id, old_id))
            cursor.execute("UPDATE insurance_applications SET product_id = ? WHERE product_id = ?", (new_id, old_id))
            cursor.execute("UPDATE patient_insurance_policies SET product_id = ? WHERE product_id = ?", (new_id, old_id))

    # Remove all third-party insurers (HDFC, ICICI, SBI, Tata AIA, Max Life)
    cursor.execute("DELETE FROM insurance_partners WHERE id != 'INS-PARTNER-SLIC'")
    cursor.execute("DELETE FROM insurance_products WHERE partner_id != 'INS-PARTNER-SLIC'")

    # Seed Spherix Life Insurance Corporation (SLIC)
    for p in SEED_PARTNERS:
        cursor.execute("""
        INSERT OR REPLACE INTO insurance_partners (
            id, legal_name, brand_name, irda_reg_no, cin_number, logo_url,
            website, contact_email, phone, toll_free, claim_settlement_ratio,
            solvency_ratio, grievance_email, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            p["id"], p["legal_name"], p["brand_name"], p["irda_reg_no"],
            p["cin_number"], p["logo_url"], p["website"], p["contact_email"],
            p["phone"], p["toll_free"], p["claim_settlement_ratio"],
            p["solvency_ratio"], p["grievance_email"]
        ))

    # Seed SLIC Products
    for pr in SEED_PRODUCTS:
        cursor.execute("""
        INSERT OR REPLACE INTO insurance_products (
            id, partner_id, product_name, product_code, uin_number, category,
            tagline, min_sum_insured, max_sum_insured, default_sum_insured,
            min_entry_age, max_entry_age, max_maturity_age, min_term_years, max_term_years,
            allowed_frequencies, base_annual_rate_per_lakh, smoker_surcharge_pct,
            female_discount_pct, key_benefits, exclusions, important_conditions,
            brochure_url, terms_url, is_active, is_featured
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            pr["id"], pr["partner_id"], pr["product_name"], pr["product_code"],
            pr["uin_number"], pr["category"], pr["tagline"], pr["min_sum_insured"],
            pr["max_sum_insured"], pr["default_sum_insured"], pr["min_entry_age"],
            pr["max_entry_age"], pr["max_maturity_age"], pr["min_term_years"],
            pr["max_term_years"], pr["allowed_frequencies"], pr["base_annual_rate_per_lakh"],
            pr["smoker_surcharge_pct"], pr["female_discount_pct"],
            json.dumps(pr["key_benefits"]), json.dumps(pr["exclusions"]),
            json.dumps(pr["important_conditions"]), pr["brochure_url"],
            pr["terms_url"], pr["is_featured"]
        ))

        # Add initial version
        cursor.execute("""
        INSERT OR IGNORE INTO insurance_product_versions (
            id, product_id, version_number, effective_from, effective_to, rules_json
        ) VALUES (?, ?, 'v1.0', '2026-01-01', '2030-12-31', ?)
        """, (
            f"VER-{pr['id']}-V1", pr["id"], json.dumps({"min_age": pr["min_entry_age"], "max_age": pr["max_entry_age"]})
        ))

    if close_after:
        conn.commit()
        conn.close()

class QuoteResult(dict):
    """Quotation result that can be unpacked as (ok, msg, quote) or accessed directly as a dict."""
    def __iter__(self):
        yield self.get('success', True)
        yield self.get('message', 'Quotation calculated successfully.')
        yield dict(self)

    def __getitem__(self, item):
        if item == 'annual_gst':
            return self.get('gst_amount', 0.0)
        if item == 'annual_net_premium':
            return self.get('base_premium', 0.0)
        if item == 'total_periodic_premium':
            return self.get('total_premium', 0.0)
        return super().get(item)

def calculate_life_insurance_quotation(
    product_id: str,
    age: int = 30,
    gender: str = 'Male',
    is_smoker: bool = False,
    sum_insured: float = 10000000.0,
    term_years: Optional[int] = None,
    frequency: Optional[str] = None,
    annual_income: float = 800000.0,
    policy_term_years: Optional[int] = None,
    premium_frequency: Optional[str] = None,
    **kwargs
) -> QuoteResult:
    """
    Computes an exact, compliant life insurance premium quotation based on verified
    product actuarial base rates, age brackets, smoker status, gender discounts, and payment frequency.
    """
    resolved_prod_id = PRODUCT_ID_ALIASES.get(product_id, product_id)
    effective_term = policy_term_years if policy_term_years is not None else (term_years if term_years is not None else 30)
    effective_freq = (premium_frequency or frequency or 'ANNUAL').upper()

    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT p.*, ip.brand_name as partner_name, ip.irda_reg_no
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    WHERE p.id = ? AND p.is_active = 1
    """, (resolved_prod_id,))
    prod = dict_from_row(cursor.fetchone())
    conn.close()

    if not prod:
        return QuoteResult({"success": False, "message": "Selected insurance product was not found or is currently inactive."})

    # Eligibility Validations
    if age < prod['min_entry_age']:
        return QuoteResult({"success": False, "message": f"Applicant age ({age}) is below minimum entry age of {prod['min_entry_age']} years."})
    if age > prod['max_entry_age']:
        return QuoteResult({"success": False, "message": f"Applicant age ({age}) exceeds maximum entry age of {prod['max_entry_age']} years."})
    if (age + effective_term) > prod['max_maturity_age']:
        max_possible_term = prod['max_maturity_age'] - age
        return QuoteResult({"success": False, "message": f"Policy maturity age cannot exceed {prod['max_maturity_age']} years. Maximum available term is {max_possible_term} years."})
    if effective_term < prod['min_term_years'] or effective_term > prod['max_term_years']:
        return QuoteResult({"success": False, "message": f"Policy term must be between {prod['min_term_years']} and {prod['max_term_years']} years."})
    if sum_insured < prod['min_sum_insured'] or sum_insured > prod['max_sum_insured']:
        return QuoteResult({"success": False, "message": f"Sum insured must be between ₹{prod['min_sum_insured']:,.0f} and ₹{prod['max_sum_insured']:,.0f}."})

    # Actuarial Premium Calculation Formula
    # Base rate is per 1 Lakh (100,000 INR) of Sum Insured for a reference 30-year-old.
    units_in_lakh = sum_insured / 100000.0
    base_rate = float(prod['base_annual_rate_per_lakh'])

    # Age Factor: Premiums scale exponentially with biological mortality curves
    # Baseline is age 30 (factor 1.0)
    if age <= 25:
        age_factor = 0.82
    elif age <= 30:
        age_factor = 0.88 + ((age - 25) * 0.024)
    elif age <= 40:
        age_factor = 1.0 + ((age - 30) * 0.045)
    elif age <= 50:
        age_factor = 1.45 + ((age - 40) * 0.08)
    else:
        age_factor = 2.25 + ((age - 50) * 0.12)

    # Term Factor: Longer terms slightly increase the annual risk reserve
    term_factor = 0.95 + (effective_term * 0.002)

    # Annual base calculation
    raw_annual = units_in_lakh * base_rate * age_factor * term_factor

    # Smoker Surcharge
    smoker_surcharge = 0.0
    if is_smoker:
        smoker_surcharge = raw_annual * (float(prod['smoker_surcharge_pct']) / 100.0)

    # Female Discount
    gender_discount = 0.0
    if str(gender).strip().lower() in ['female', 'f']:
        gender_discount = raw_annual * (float(prod['female_discount_pct']) / 100.0)

    net_annual_premium = raw_annual + smoker_surcharge - gender_discount

    # Frequency factor
    freq_multipliers = {
        'ANNUAL': 1.0,
        'SEMI_ANNUAL': 0.51,
        'QUARTERLY': 0.26,
        'MONTHLY': 0.088
    }
    if effective_freq not in freq_multipliers:
        effective_freq = 'ANNUAL'

    base_period_premium = round(net_annual_premium * freq_multipliers[effective_freq], 2)
    gst_rate = 0.18 # Statutory 18% GST on pure protection / life products
    gst_amount = round(base_period_premium * gst_rate, 2)
    total_period_premium = round(base_period_premium + gst_amount, 2)

    quote_id = f"QTE-{secrets.token_hex(4).upper()}"
    quote_number = f"SPX-QTE-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    breakdown = {
        "units_in_lakh": units_in_lakh,
        "base_rate_per_lakh": base_rate,
        "age_factor": round(age_factor, 3),
        "term_factor": round(term_factor, 3),
        "raw_annual": round(raw_annual, 2),
        "smoker_surcharge": round(smoker_surcharge, 2),
        "gender_discount": round(gender_discount, 2),
        "net_annual_premium": round(net_annual_premium, 2),
        "frequency": effective_freq,
        "frequency_multiplier": freq_multipliers[effective_freq],
        "base_period_premium": base_period_premium,
        "gst_amount": gst_amount,
        "total_period_premium": total_period_premium
    }

    quote_data = {
        "id": quote_id,
        "quote_number": quote_number,
        "product_id": resolved_prod_id,
        "product_name": prod['product_name'],
        "partner_id": prod['partner_id'],
        "partner_name": prod['partner_name'],
        "uin_number": prod['uin_number'],
        "category": prod['category'],
        "age": age,
        "gender": gender,
        "is_smoker": 1 if is_smoker else 0,
        "sum_insured": sum_insured,
        "policy_term_years": effective_term,
        "premium_frequency": effective_freq,
        "base_premium": base_period_premium,
        "gst_amount": gst_amount,
        "total_premium": total_period_premium,
        "breakdown": breakdown,
        "valid_until": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    }

    res = QuoteResult(quote_data)
    res['success'] = True
    res['message'] = "Quotation calculated successfully."
    return res

def save_insurance_quotation(patient_id: str, quote_data: Dict[str, Any]) -> str:
    """Stores an insurance quotation record in the database."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO insurance_quotations (
        id, quote_number, patient_id, product_id, partner_id, age, gender,
        is_smoker, annual_income, sum_insured, policy_term_years, premium_frequency,
        base_premium, gst_amount, total_premium, breakdown_json, is_confirmed, valid_until
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        quote_data['id'], quote_data['quote_number'], str(patient_id), quote_data['product_id'],
        quote_data['partner_id'], quote_data['age'], quote_data['gender'], quote_data['is_smoker'],
        quote_data.get('annual_income', 0.0), quote_data['sum_insured'], quote_data['policy_term_years'],
        quote_data['premium_frequency'], quote_data['base_premium'], quote_data['gst_amount'],
        quote_data['total_premium'], json.dumps(quote_data.get('breakdown', {})),
        quote_data.get('valid_until')
    ))

    conn.commit()
    conn.close()
    return quote_data['id']

# ==============================================================================
# 4. INSURANCE APPLICATION WORKFLOW (MULTI-STEP)
# ==============================================================================

def create_or_update_insurance_application(
    patient_id: str,
    product_id: str,
    quotation_data: Optional[Dict[str, Any]] = None,
    personal_info: Optional[Dict[str, Any]] = None,
    insurance_details: Optional[Dict[str, Any]] = None,
    nominee_info: Optional[Dict[str, Any]] = None,
    declarations: Optional[Dict[str, Any]] = None,
    current_step: int = 1,
    status: str = 'DRAFT',
    application_id: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """Creates a new application or updates existing draft progress."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    resolved_prod_id = PRODUCT_ID_ALIASES.get(product_id, product_id)

    # Get product partner
    cursor.execute("SELECT partner_id FROM insurance_products WHERE id = ?", (resolved_prod_id,))
    prod_row = cursor.fetchone()
    if not prod_row:
        conn.close()
        return False, "Insurance product does not exist.", {}
    partner_id = prod_row['partner_id']

    if not application_id:
        app_id = f"APP-SPX-{secrets.token_hex(4).upper()}"
        app_number = f"SPX-INS-{datetime.now().strftime('%Y%m')}-{secrets.token_hex(3).upper()}"
    else:
        app_id = application_id
        cursor.execute("SELECT application_number, patient_id FROM insurance_applications WHERE id = ?", (app_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return False, "Application record not found.", {}
        if str(existing['patient_id']) != str(patient_id):
            conn.close()
            return False, "Unauthorized access to application.", {}
        app_number = existing['application_number']

    cursor.execute("""
    INSERT OR REPLACE INTO insurance_applications (
        id, application_number, patient_id, product_id, partner_id, quotation_id,
        status, current_step, personal_info_json, insurance_details_json, nominee_info_json,
        declarations_json, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        app_id, app_number, str(patient_id), resolved_prod_id, partner_id,
        quotation_data.get('id') if quotation_data else None, status, current_step,
        json.dumps(personal_info or {}), json.dumps(insurance_details or {}),
        json.dumps(nominee_info or {}), json.dumps(declarations or {})
    ))

    # Also save Nominee if provided
    if nominee_info and nominee_info.get('full_name'):
        cursor.execute("DELETE FROM insurance_nominees WHERE application_id = ?", (app_id,))
        nom_id = f"NOM-{secrets.token_hex(4).upper()}"
        cursor.execute("""
        INSERT INTO insurance_nominees (
            id, application_id, patient_id, full_name, relationship, date_of_birth,
            contact_phone, contact_email, share_percentage, is_minor, appointee_name, appointee_relation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nom_id, app_id, str(patient_id), nominee_info['full_name'],
            nominee_info.get('relationship', 'Spouse'), nominee_info.get('date_of_birth', '1990-01-01'),
            nominee_info.get('contact_phone', ''), nominee_info.get('contact_email', ''),
            float(nominee_info.get('share_percentage', 100.0)),
            1 if nominee_info.get('is_minor') else 0,
            nominee_info.get('appointee_name', ''), nominee_info.get('appointee_relation', '')
        ))

    # Log Audit Event
    log_insurance_audit(
        entity_type="APPLICATION",
        entity_id=app_id,
        actor_id=str(patient_id),
        actor_role="patient",
        action=f"UPDATE_STEP_{current_step}",
        details={"status": status, "step": current_step}
    )

    conn.commit()
    conn.close()

    return True, "Application progress saved successfully.", {
        "application_id": app_id,
        "application_number": app_number,
        "status": status,
        "current_step": current_step
    }

class SubmitResult(dict):
    """Result object for application submission that behaves as both a dict and an unpackable (bool, str, dict) tuple."""
    def __iter__(self):
        yield self.get('success', True)
        yield self.get('message', 'Application submitted')
        yield dict(self)

    def __getitem__(self, item):
        return super().get(item)

def submit_insurance_application(application_id: str, patient_id: Optional[str] = None, ip_address: str = "127.0.0.1") -> SubmitResult:
    """Submits the completed application for underwriting review."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    if patient_id is not None:
        cursor.execute("""
        SELECT a.*, p.product_name, ip.brand_name as partner_name
        FROM insurance_applications a
        JOIN insurance_products p ON a.product_id = p.id
        JOIN insurance_partners ip ON a.partner_id = ip.id
        WHERE a.id = ? AND a.patient_id = ?
        """, (application_id, str(patient_id)))
    else:
        cursor.execute("""
        SELECT a.*, p.product_name, ip.brand_name as partner_name
        FROM insurance_applications a
        JOIN insurance_products p ON a.product_id = p.id
        JOIN insurance_partners ip ON a.partner_id = ip.id
        WHERE a.id = ?
        """, (application_id,))
    app = dict_from_row(cursor.fetchone())

    if not app:
        conn.close()
        return SubmitResult({'success': False, 'message': 'Application not found or unauthorized.', 'status': 'NOT_FOUND'})

    patient_id = app['patient_id']

    if app['status'] not in ['DRAFT', 'ADDITIONAL_INFO_REQUIRED']:
        conn.close()
        return SubmitResult({'success': False, 'message': f"Application cannot be submitted because it is currently in '{app['status']}' state.", 'status': app['status']})

    # Verify declarations and consent
    declarations = json.loads(app.get('declarations_json') or '{}')
    if not declarations.get('consent_accepted') and not declarations.get('statutory_consent'):
        conn.close()
        return SubmitResult({'success': False, 'message': "Statutory consent and declaration acceptance is required before submitting.", 'status': app['status']})

    # Store formal statutory consent record
    consent_id = f"CNS-{secrets.token_hex(4).upper()}"
    cursor.execute("""
    INSERT INTO insurance_consents (
        id, application_id, patient_id, consent_type, consent_text, ip_address, is_accepted
    ) VALUES (?, ?, ?, 'INSURER_TRANSFER_AND_DECLARATION', ?, ?, 1)
    """, (
        consent_id, application_id, str(patient_id),
        "Applicant confirmed accuracy of personal and health statements, explicit consent to transfer application data to authorized partner insurer for underwriting.",
        ip_address
    ))

    # Transition state to UNDER_REVIEW
    cursor.execute("""
    UPDATE insurance_applications
    SET status = 'UNDER_REVIEW', submitted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (application_id,))

    # Log Audit
    log_insurance_audit(
        entity_type="APPLICATION",
        entity_id=application_id,
        actor_id=str(patient_id),
        actor_role="patient",
        action="SUBMIT_APPLICATION",
        details={"app_number": app['application_number']},
        ip_address=ip_address
    )

    conn.commit()
    conn.close()

    # Automatically trigger insurer underwriting adapter
    try:
        from spherix.services.insurance_integration import get_insurer_adapter
        app_full = get_insurance_application_by_id(application_id, patient_id=str(patient_id))
        adapter = get_insurer_adapter(app['partner_id'])
        ok_uw, msg_uw, uw_res = adapter.submit_application(app_full or app)
        final_status = uw_res.get('status', 'UNDER_REVIEW')
        decision = uw_res.get('underwriting_decision', 'PENDING')
        remarks = uw_res.get('remarks', '')
        return SubmitResult({
            'success': True,
            'message': msg_uw or f"Application {app['application_number']} submitted successfully.",
            'application_id': application_id,
            'application_number': app['application_number'],
            'status': final_status,
            'insurer_decision': decision,
            'remarks': remarks
        })
    except Exception as e:
        return SubmitResult({
            'success': True,
            'message': f"Application {app['application_number']} submitted successfully.",
            'application_id': application_id,
            'application_number': app['application_number'],
            'status': 'UNDER_REVIEW',
            'insurer_decision': 'PENDING'
        })

def get_patient_insurance_applications(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieves all insurance applications filed by a specific patient."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT a.*, p.product_name, p.category, p.uin_number, ip.brand_name as partner_name, ip.logo_url as partner_logo
    FROM insurance_applications a
    JOIN insurance_products p ON a.product_id = p.id
    JOIN insurance_partners ip ON a.partner_id = ip.id
    WHERE a.patient_id = ?
    ORDER BY a.created_at DESC
    """, (str(patient_id),))

    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()

    for r in rows:
        r['personal_info'] = json.loads(r.get('personal_info_json') or '{}')
        ins_details = json.loads(r.get('insurance_details_json') or '{}')
        r['insurance_details'] = ins_details
        r['nominee_info'] = json.loads(r.get('nominee_info_json') or '{}')
        r['declarations'] = json.loads(r.get('declarations_json') or '{}')
        r['sum_insured'] = r.get('sum_insured') or ins_details.get('sum_insured') or 0.0
        r['quoted_premium'] = r.get('quoted_premium') or ins_details.get('quoted_premium') or ins_details.get('base_premium') or ins_details.get('total_premium') or 0.0
        r['premium_frequency'] = r.get('premium_frequency') or ins_details.get('premium_frequency') or 'ANNUAL'
        r['insurer_name'] = r.get('insurer_name') or r.get('partner_name') or ''
    return rows

def get_insurance_application_by_id(application_id: str, patient_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves single application with ownership verification."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    query = """
    SELECT a.*, p.product_name, p.category, p.uin_number, p.tagline,
           ip.brand_name as partner_name, ip.legal_name as partner_legal_name,
           ip.irda_reg_no, ip.logo_url as partner_logo, ip.toll_free as partner_toll_free
    FROM insurance_applications a
    JOIN insurance_products p ON a.product_id = p.id
    JOIN insurance_partners ip ON a.partner_id = ip.id
    WHERE a.id = ?
    """
    params = [application_id]
    if patient_id is not None:
        query += " AND a.patient_id = ?"
        params.append(str(patient_id))

    cursor.execute(query, params)
    row = dict_from_row(cursor.fetchone())
    conn.close()

    if not row:
        return None

    row['personal_info'] = json.loads(row.get('personal_info_json') or '{}')
    ins_details = json.loads(row.get('insurance_details_json') or '{}')
    row['insurance_details'] = ins_details
    row['nominee_info'] = json.loads(row.get('nominee_info_json') or '{}')
    row['declarations'] = json.loads(row.get('declarations_json') or '{}')
    row['sum_insured'] = row.get('sum_insured') or ins_details.get('sum_insured') or 0.0
    row['quoted_premium'] = row.get('quoted_premium') or ins_details.get('quoted_premium') or ins_details.get('base_premium') or ins_details.get('total_premium') or 0.0
    row['premium_frequency'] = row.get('premium_frequency') or ins_details.get('premium_frequency') or 'ANNUAL'
    row['insurer_name'] = row.get('insurer_name') or row.get('partner_name') or ''
    return row

# ==============================================================================
# 5. PATIENT POLICIES & CLAIMS MANAGEMENT
# ==============================================================================

def get_patient_insurance_policies(patient_id: str) -> List[Dict[str, Any]]:
    """Returns all verified issued policies belonging to the patient."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT pol.*, p.product_name, p.category, ip.brand_name as partner_name,
           ip.legal_name as partner_legal_name, ip.irda_reg_no, ip.logo_url as partner_logo,
           ip.claim_settlement_ratio, ip.toll_free as partner_toll_free
    FROM patient_insurance_policies pol
    JOIN insurance_products p ON pol.product_id = p.id
    JOIN insurance_partners ip ON pol.partner_id = ip.id
    WHERE pol.patient_id = ?
    ORDER BY pol.policy_start_date DESC
    """, (str(patient_id),))

    policies = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return policies

def get_patient_policy_by_id(policy_id: str, patient_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Returns single policy record ensuring strict data isolation."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    query = """
    SELECT pol.*, p.product_name, p.category, p.tagline, p.key_benefits, p.exclusions, p.important_conditions,
           ip.brand_name as partner_name, ip.legal_name as partner_legal_name, ip.irda_reg_no,
           ip.cin_number, ip.logo_url as partner_logo, ip.contact_email as partner_email,
           ip.toll_free as partner_toll_free, ip.claim_settlement_ratio
    FROM patient_insurance_policies pol
    JOIN insurance_products p ON pol.product_id = p.id
    JOIN insurance_partners ip ON pol.partner_id = ip.id
    WHERE (pol.id = ? OR pol.policy_number = ?)
    """
    params = [policy_id, policy_id]
    if patient_id is not None:
        query += " AND pol.patient_id = ?"
        params.append(str(patient_id))

    cursor.execute(query, params)
    policy = dict_from_row(cursor.fetchone())
    conn.close()

    if not policy:
        return None

    policy['key_benefits'] = json.loads(policy.get('key_benefits') or '[]')
    policy['exclusions'] = json.loads(policy.get('exclusions') or '[]')
    policy['important_conditions'] = json.loads(policy.get('important_conditions') or '[]')
    return policy

def create_claim_assistance_request(
    policy_id: str,
    patient_id: str,
    claimant_data: Dict[str, Any]
) -> Tuple[bool, str, Dict[str, Any]]:
    """Creates a dedicated Spherix Insurance claim assistance file."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    # Verify policy ownership
    cursor.execute("SELECT id, policy_number FROM patient_insurance_policies WHERE id = ? AND patient_id = ?", (policy_id, str(patient_id)))
    pol = cursor.fetchone()
    if not pol:
        conn.close()
        return False, "Policy not found or unauthorized.", {}

    claim_id = f"CLM-{secrets.token_hex(4).upper()}"
    claim_number = f"SPX-CLM-{datetime.now().strftime('%Y%m')}-{secrets.token_hex(3).upper()}"

    cursor.execute("""
    INSERT INTO insurance_claim_assistances (
        id, claim_number, policy_id, patient_id, claimant_name, claimant_relation,
        claimant_phone, claimant_email, claim_type, incident_date, hospital_name,
        diagnosis_summary, status, tracking_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REQUESTED', ?)
    """, (
        claim_id, claim_number, policy_id, str(patient_id),
        claimant_data['claimant_name'], claimant_data['claimant_relation'],
        claimant_data['claimant_phone'], claimant_data.get('claimant_email', ''),
        claimant_data['claim_type'], claimant_data['incident_date'],
        claimant_data.get('hospital_name', ''), claimant_data.get('diagnosis_summary', ''),
        f"Claim assistance initiated by {claimant_data['claimant_name']}. Spherix claim coordinator assigned."
    ))

    # Log Audit
    log_insurance_audit(
        entity_type="CLAIM",
        entity_id=claim_id,
        actor_id=str(patient_id),
        actor_role="patient",
        action="REQUEST_CLAIM_ASSISTANCE",
        details={"claim_number": claim_number, "policy_id": policy_id}
    )

    conn.commit()
    conn.close()

    return True, f"Claim assistance request {claim_number} logged successfully. A dedicated Spherix Insurance claims specialist will contact you within 2 business hours.", {
        "claim_id": claim_id,
        "claim_number": claim_number,
        "status": "REQUESTED"
    }

def get_patient_claims(patient_id: str) -> List[Dict[str, Any]]:
    """Returns list of all claims assistance tickets filed by patient."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.*, pol.policy_number, p.product_name, ip.brand_name as partner_name
    FROM insurance_claim_assistances c
    JOIN patient_insurance_policies pol ON c.policy_id = pol.id
    JOIN insurance_products p ON pol.product_id = p.id
    JOIN insurance_partners ip ON pol.partner_id = ip.id
    WHERE c.patient_id = ?
    ORDER BY c.created_at DESC
    """, (str(patient_id),))

    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return rows

# ==============================================================================
# 6. PAYMENTS, RECEIPTS & TRANSACTIONS
# ==============================================================================

def get_patient_insurance_payments(patient_id: str) -> List[Dict[str, Any]]:
    """Returns premium payment ledger for patient."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT pay.*, pol.policy_number, app.application_number, p.product_name, ip.brand_name as partner_name
    FROM insurance_payments pay
    LEFT JOIN patient_insurance_policies pol ON pay.policy_id = pol.id
    LEFT JOIN insurance_applications app ON pay.application_id = app.id
    LEFT JOIN insurance_products p ON (pol.product_id = p.id OR app.product_id = p.id)
    LEFT JOIN insurance_partners ip ON (pol.partner_id = ip.id OR app.partner_id = ip.id)
    WHERE pay.patient_id = ?
    ORDER BY pay.created_at DESC
    """, (str(patient_id),))

    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return rows

# ==============================================================================
# 7. AUDIT LOGGING & SECURITY
# ==============================================================================

def log_insurance_audit(
    entity_type: str,
    entity_id: str,
    actor_id: str,
    actor_role: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    ip_address: str = "127.0.0.1"
):
    """Enforces immutable audit logging for all insurance lifecycle transactions."""
    try:
        conn = get_insurance_db()
        cursor = conn.cursor()
        log_id = f"AUD-{secrets.token_hex(6).upper()}"
        cursor.execute("""
        INSERT INTO insurance_audit_logs (
            id, entity_type, entity_id, actor_id, actor_role, action, details_json, ip_address
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_id, entity_type, str(entity_id), str(actor_id), actor_role, action,
            json.dumps(details or {}), ip_address
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Insurance audit logging notice: {e}")

# ==============================================================================
# 8. CATALOG & WORKFLOW HIGH-LEVEL HELPERS
# ==============================================================================

def normalize_product_record(r: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not r:
        return None
    uin = r.get('uin_number', '')
    if not uin.startswith('IRDAI/NL/'):
        r['uin'] = f"IRDAI/NL/{uin}"
    else:
        r['uin'] = uin
    cat = r.get('category', '')
    cat_map = {
        'Term Life': 'TERM_LIFE',
        'Whole Life': 'WHOLE_LIFE',
        'Savings': 'SAVINGS_LINKED',
        'Family Protection': 'FAMILY_PROTECTION'
    }
    if cat in cat_map:
        r['category_display'] = cat
        r['category'] = cat_map[cat]
    else:
        r['category_display'] = cat.replace('_', ' ').title()
    return r

def get_all_insurance_products(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all active life insurance products with partner details."""
    conn = get_insurance_db()
    cursor = conn.cursor()
    query = """
    SELECT p.*, ip.brand_name as insurer_name, ip.legal_name as partner_legal_name,
           ip.irda_reg_no, ip.claim_settlement_ratio, ip.logo_url as partner_logo
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    WHERE p.is_active = 1
    """
    params = []
    if category and category != 'all':
        inv_map = {'TERM_LIFE': 'Term Life', 'WHOLE_LIFE': 'Whole Life', 'SAVINGS_LINKED': 'Savings', 'FAMILY_PROTECTION': 'Family Protection'}
        alt_cat = inv_map.get(category, category)
        query += " AND (p.category = ? OR p.category = ?)"
        params.extend([category, alt_cat])
    query += " ORDER BY p.is_featured DESC, ip.claim_settlement_ratio DESC"
    cursor.execute(query, params)
    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return [normalize_product_record(r) for r in rows]

def get_insurance_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single verified product by its ID."""
    resolved_id = PRODUCT_ID_ALIASES.get(product_id, product_id)
    conn = get_insurance_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.*, ip.brand_name as insurer_name, ip.legal_name as partner_legal_name,
           ip.irda_reg_no, ip.claim_settlement_ratio, ip.logo_url as partner_logo
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    WHERE p.id = ?
    """, (resolved_id,))
    row = dict_from_row(cursor.fetchone())
    conn.close()
    return normalize_product_record(row)

def save_insurance_application_draft(
    patient_id: str,
    product_id: str,
    sum_insured: float = 10000000.0,
    policy_term_years: int = 30,
    premium_frequency: str = "ANNUAL",
    quoted_premium: float = 9500.0,
    applicant_data: Optional[Dict[str, Any]] = None,
    nominee_data: Optional[Dict[str, Any]] = None,
    declarations: Optional[Dict[str, Any]] = None,
    application_id: Optional[str] = None
) -> str:
    """Helper to initialize or update a proposal draft."""
    resolved_prod_id = PRODUCT_ID_ALIASES.get(product_id, product_id)
    insurance_details = {
        "product_id": resolved_prod_id,
        "sum_insured": sum_insured,
        "policy_term_years": policy_term_years,
        "premium_frequency": premium_frequency,
        "quoted_premium": quoted_premium,
        "base_premium": quoted_premium
    }
    decl = declarations or {}
    if 'statutory_consent' in decl:
        decl['consent_accepted'] = decl['statutory_consent']
    ok, msg, res = create_or_update_insurance_application(
        patient_id=str(patient_id),
        product_id=resolved_prod_id,
        current_step=5,
        personal_info=applicant_data or {},
        insurance_details=insurance_details,
        nominee_info=nominee_data or {},
        declarations=decl,
        application_id=application_id,
        status="DRAFT"
    )
    if not ok:
        raise ValueError(msg)
    return res['application_id']

def issue_verified_policy_for_application(
    application_id: str,
    payment_ref: str,
    amount_paid: float,
    payment_method: str = "GATEWAY"
) -> Dict[str, Any]:
    """Issues a verified policy for an application following payment verification."""
    from spherix.services.insurance_integration import get_insurer_adapter
    app = get_insurance_application_by_id(application_id)
    if not app:
        raise ValueError(f"Application {application_id} not found.")
    adapter = get_insurer_adapter(app['partner_id'])
    payment_data = {
        "payment_ref": payment_ref,
        "amount": amount_paid,
        "payment_method": payment_method
    }
    ok, msg, pol_res = adapter.verify_payment_and_issue_policy(payment_data, app)
    if not ok:
        raise ValueError(msg)
    pol_res['success'] = True
    return pol_res
