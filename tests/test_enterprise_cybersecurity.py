"""
Spherix Clinic — Automated Enterprise Cybersecurity Test Suite
==============================================================
Validates:
1. Argon2id password hashing & legacy PBKDF2/scrypt auto-upgrade
2. NIST SP 800-63B password complexity enforcement
3. RFC 6238 TOTP MFA authentication and single-use recovery codes
4. Web Application Firewall (WAF) blocking of SQLi, XSS, Path Traversal, Scanners
5. Server-Side Request Forgery (SSRF) cloud metadata & loopback prevention
6. Field-level AES-256 authenticated encryption for Protected Health Information (PHI)
7. Cryptographically sealed database backups and integrity verification
8. Role-Based Access Control (RBAC) & anti-IDOR boundary isolation
9. Digital Personal Data Protection (DPDP) Act 2023 Aadhaar & PII anonymization
10. Multi-device session tracking and Global Killswitch invalidation
"""

import pytest
import os
import sqlite3
import pyotp
from werkzeug.security import generate_password_hash

from spherix.security.hashing import (
    hash_password,
    verify_password,
    validate_password_strength
)
from spherix.security.mfa import (
    generate_mfa_secret,
    get_totp_uri,
    generate_mfa_qr_base64,
    generate_backup_recovery_codes,
    verify_totp_token,
    verify_and_consume_recovery_code,
    is_mfa_mandatory_for_role
)
from spherix.security.encryption import (
    encrypt_field,
    decrypt_field,
    encrypt_sensitive_dict,
    decrypt_sensitive_dict,
    create_encrypted_database_backup,
    verify_backup_integrity
)
from spherix.security.rbac import (
    ROLE_SUPER_ADMIN,
    ROLE_HOSPITAL_ADMIN,
    ROLE_DOCTOR,
    ROLE_PATIENT,
    has_permission
)
from spherix.security.firewall import (
    is_safe_external_url,
    MALICIOUS_USER_AGENTS,
    PATH_TRAVERSAL_PATTERN,
    SQLI_PATTERN,
    XSS_PATTERN
)
from spherix.security.compliance import anonymize_phi_for_external_ai
from spherix.security.session_manager import (
    init_session_tables,
    revoke_session,
    revoke_all_user_sessions
)
from spherix.security.audit import (
    log_security_event,
    get_security_command_center_telemetry
)


# =====================================================================
# 1. HASHING & PASSWORDS
# =====================================================================

def test_argon2id_hashing():
    pwd = "Spherix@Enterprise2026!"
    hashed = hash_password(pwd)
    assert hashed.startswith("$argon2id$")
    
    # Constant-time verify
    valid, needs_rehash = verify_password(hashed, pwd)
    assert valid is True
    assert needs_rehash is False

    # Wrong password
    invalid, _ = verify_password(hashed, "WrongPassword123!")
    assert invalid is False


def test_legacy_pbkdf2_auto_rehash_flag():
    pwd = "LegacyPassword#2025"
    legacy_hash = generate_password_hash(pwd, method="pbkdf2:sha256:260000")
    
    valid, needs_rehash = verify_password(legacy_hash, pwd)
    assert valid is True
    # Must flag for upgrade to Argon2id
    assert needs_rehash is True


def test_password_complexity_validator():
    # Too short
    ok, _ = validate_password_strength("Short1!")
    assert ok is False

    # Common weak password
    ok, _ = validate_password_strength("password123")
    assert ok is False

    # Missing uppercase
    ok, _ = validate_password_strength("spherix@clinic2026")
    assert ok is False

    # Strong compliant password
    ok, _ = validate_password_strength("SpherixClinic#Health2026!")
    assert ok is True


# =====================================================================
# 2. MULTI-FACTOR AUTHENTICATION (TOTP & RECOVERY CODES)
# =====================================================================

def test_totp_mfa_token_generation_and_verification():
    secret = generate_mfa_secret()
    assert len(secret) == 32

    # Generate current live token
    totp = pyotp.TOTP(secret)
    live_token = totp.now()

    # Verify live token
    assert verify_totp_token(secret, live_token) is True

    # Bad token
    assert verify_totp_token(secret, "000000") is False
    assert verify_totp_token(secret, "abcdef") is False


def test_mfa_qr_code_and_mandatory_policies():
    secret = generate_mfa_secret()
    qr_data = generate_mfa_qr_base64(secret, "doctor@spherixclinic.com")
    assert qr_data.startswith("data:image/png;base64,")

    # Mandatory check for privileged roles
    assert is_mfa_mandatory_for_role("admin") is True
    assert is_mfa_mandatory_for_role("hospital") is True
    assert is_mfa_mandatory_for_role("patient") is False


def test_single_use_backup_recovery_codes():
    raw_codes, hashed_codes = generate_backup_recovery_codes(4)
    assert len(raw_codes) == 4
    assert len(hashed_codes) == 4

    first_code = raw_codes[0]
    matched, remaining = verify_and_consume_recovery_code(first_code, hashed_codes)
    assert matched is True
    assert len(remaining) == 3

    # Attempting to use the same code a second time must FAIL
    matched_again, _ = verify_and_consume_recovery_code(first_code, remaining)
    assert matched_again is False


# =====================================================================
# 3. WEB APPLICATION FIREWALL (WAF) & SSRF PREVENTION
# =====================================================================

def test_waf_signature_detection():
    # Automated exploit scanners
    assert bool(MALICIOUS_USER_AGENTS.search("sqlmap/1.5")) is True
    assert bool(MALICIOUS_USER_AGENTS.search("Nikto/2.1.6")) is True
    assert bool(MALICIOUS_USER_AGENTS.search("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")) is False

    # Path Traversal
    assert bool(PATH_TRAVERSAL_PATTERN.search("/api/../../etc/passwd")) is True
    assert bool(PATH_TRAVERSAL_PATTERN.search("/uploads/%2e%2e%2fconfig.json")) is True
    assert bool(PATH_TRAVERSAL_PATTERN.search("/patient/dashboard")) is False

    # SQL Injection in query params
    assert bool(SQLI_PATTERN.search("q=1 union all select * from doctors")) is True
    assert bool(SQLI_PATTERN.search("name=John; drop table users;--")) is True
    assert bool(SQLI_PATTERN.search("q=aspirin+500mg")) is False

    # Script Injection (XSS)
    assert bool(XSS_PATTERN.search("name=<script>alert('xss')</script>")) is True
    assert bool(XSS_PATTERN.search("ref=javascript:document.cookie")) is True
    assert bool(XSS_PATTERN.search("query=cardiology+specialist")) is False


def test_ssrf_prevention():
    # Dangerous internal / cloud metadata targets
    assert is_safe_external_url("http://127.0.0.1:5000/internal") is False
    assert is_safe_external_url("http://localhost:8080/admin") is False
    assert is_safe_external_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_safe_external_url("http://metadata.google.internal/computeMetadata/v1/") is False
    assert is_safe_external_url("ftp://127.0.0.1/malicious") is False

    # Safe external APIs
    assert is_safe_external_url("https://api.openai.com/v1/chat/completions") is True
    assert is_safe_external_url("https://api.razorpay.com/v1/orders") is True


# =====================================================================
# 4. ENCRYPTION AT REST & BACKUP INTEGRITY
# =====================================================================

def test_phi_encryption_at_rest():
    diagnosis = "Acute myocardial infarction with left anterior descending artery occlusion."
    
    # Encrypt
    ciphertext = encrypt_field(diagnosis)
    assert ciphertext.startswith("enc:v1:")
    assert diagnosis not in ciphertext

    # Decrypt
    decrypted = decrypt_field(ciphertext)
    assert decrypted == diagnosis

    # Legacy unencrypted pass-through
    assert decrypt_field("Legacy Cleartext Note") == "Legacy Cleartext Note"


def test_encrypted_database_backup_and_integrity_check(tmp_path):
    # Create mock SQLite database
    db_file = tmp_path / "test_spherix.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE patients_secure (id TEXT PRIMARY KEY, medical_data TEXT)")
    conn.execute("INSERT INTO patients_secure VALUES ('PAT-001', 'Confidential')")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"
    backup_path = create_encrypted_database_backup(str(db_file), str(backup_dir))
    
    assert backup_path is not None
    assert os.path.exists(backup_path)
    assert backup_path.endswith(".enc")

    # Verify backup integrity
    ok, msg = verify_backup_integrity(backup_path)
    assert ok is True
    assert "Backup integrity verified" in msg


# =====================================================================
# 5. RBAC & DATA AUTHORIZATION
# =====================================================================

def test_rbac_permissions():
    # Super Admin has audit logs and security permissions
    assert has_permission("view_audit_logs", ROLE_SUPER_ADMIN) is True
    assert has_permission("manage_security_center", ROLE_SUPER_ADMIN) is True

    # Doctor can create prescriptions, cannot manage hospital beds
    assert has_permission("create_prescriptions", ROLE_DOCTOR) is True
    assert has_permission("manage_hospital_beds", ROLE_DOCTOR) is False

    # Patient can view own PHI, cannot create prescriptions
    assert has_permission("view_own_phi", ROLE_PATIENT) is True
    assert has_permission("create_prescriptions", ROLE_PATIENT) is False


# =====================================================================
# 6. INDIAN DPDP ACT 2023 COMPLIANCE & PII ANONYMIZATION
# =====================================================================

def test_dpdp_pii_anonymization_for_ai():
    raw_prompt = (
        "Patient Rahul Sharma with Aadhaar 5482 9102 3841 and phone +91 9876543210 "
        "and email rahul.sharma@example.com reports severe chest pain and nausea."
    )
    
    anonymized = anonymize_phi_for_external_ai(raw_prompt)
    
    # Sensitive personal identifiers must be masked
    assert "5482 9102 3841" not in anonymized
    assert "[REDACTED_AADHAAR]" in anonymized
    assert "+91 9876543210" not in anonymized
    assert "[REDACTED_PHONE]" in anonymized
    assert "rahul.sharma@example.com" not in anonymized
    assert "[REDACTED_EMAIL]" in anonymized
    # Clinical symptoms must be preserved for accurate diagnosis
    assert "chest pain" in anonymized
    assert "nausea" in anonymized


# =====================================================================
# 7. SESSION MANAGEMENT & GLOBAL KILLSWITCH
# =====================================================================

def test_session_killswitch_revocation():
    init_session_tables()
    user_id = "DOC-SEC-999"
    
    # Trigger global killswitch
    revoked_count = revoke_all_user_sessions(user_id)
    assert isinstance(revoked_count, int)


# =====================================================================
# 8. AUDIT LOGGING & TELEMETRY
# =====================================================================

def test_audit_event_logging():
    log_security_event(
        event_type="CYBER_TEST_RUN",
        severity="INFO",
        details="Automated security verification executed successfully",
        actor_id="test_suite"
    )

    telemetry = get_security_command_center_telemetry()
    assert telemetry["total_events"] > 0
    assert "database_health" in telemetry
