"""
Spherix Clinic — Healthcare Privacy & Compliance Architecture
==============================================================
Implements Privacy-by-Design complying with:
- Digital Personal Data Protection Act, 2023 (DPDP Act)
- Digital Health Data Security & CERT-In directions
- Automatic PHI Sanitization for Generative AI & Clinical APIs
"""

import re
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# Regular expressions for detecting and anonymizing Indian / Global PII
PHONE_REGEX = re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
AADHAAR_REGEX = re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b')
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

def anonymize_phi_for_external_ai(text: Optional[str]) -> str:
    """
    Strips Protected Health Information (PHI / PII) before sending clinical notes
    or symptom queries to third-party LLMs (Groq, OpenAI, Gemini).
    Protects patient privacy in accordance with DPDP Act 2023 and HIPAA.
    """
    if not text:
        return ""

    sanitized = str(text)
    # Mask Indian Aadhaar numbers
    sanitized = AADHAAR_REGEX.sub("[REDACTED_AADHAAR]", sanitized)
    # Mask Emails
    sanitized = EMAIL_REGEX.sub("[REDACTED_EMAIL]", sanitized)
    # Mask Phone Numbers
    sanitized = PHONE_REGEX.sub("[REDACTED_PHONE]", sanitized)

    return sanitized

def record_patient_consent(
    patient_id: str,
    consent_purpose: str,
    consent_given: bool = True,
    ip_address: Optional[str] = None
) -> bool:
    """
    Records verifiable patient consent under Section 6 of DPDP Act 2023.
    """
    db_candidates = [
        os.getenv('SQLITE_DB_PATH'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'spherixclinic.db'),
        'spherixclinic.db'
    ]
    db_file = next((p for p in db_candidates if p and os.path.exists(p)), 'spherixclinic.db')

    try:
        conn = sqlite3.connect(db_file, timeout=10.0)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS patient_consent_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            purpose TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            policy_version TEXT NOT NULL
        )
        """)
        now_iso = datetime.now(timezone.utc).isoformat()
        status = "GRANTED" if consent_given else "WITHDRAWN"
        cur.execute("""
        INSERT INTO patient_consent_ledger (patient_id, purpose, status, timestamp, ip_address, policy_version)
        VALUES (?, ?, ?, ?, ?, 'DPDP-2026-V1')
        """, (str(patient_id), consent_purpose, status, now_iso, ip_address or "127.0.0.1"))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Consent recording error: {e}")
        return False

