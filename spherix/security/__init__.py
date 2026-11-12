"""
Spherix Clinic Enterprise Cybersecurity Suite
=============================================
Unified export interface for hashing, MFA, encryption, RBAC,
audit logging, WAF firewall, session management, file guard, and compliance.
"""

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
    ROLE_NURSE,
    ROLE_RECEPTIONIST,
    ROLE_PHARMACY,
    ROLE_LABORATORY,
    ROLE_BILLING,
    ROLE_INSURANCE_ADMIN,
    get_current_user_role,
    has_permission,
    require_role,
    require_permission,
    verify_patient_ownership,
    verify_hospital_ownership
)
from spherix.security.audit import (
    log_security_event,
    get_security_command_center_telemetry,
    prune_audit_logs
)
from spherix.security.session_manager import (
    register_new_session,
    validate_active_session,
    revoke_session,
    revoke_all_user_sessions,
    get_user_active_sessions,
    purge_expired_sessions
)
from spherix.security.firewall import (
    inspect_incoming_request,
    is_safe_external_url,
    apply_enterprise_security_headers,
    ban_ip,
    unban_ip,
    get_blocked_ips,
    is_ip_banned,
    get_waf_mode,
    set_waf_mode
)
from spherix.security.file_guard import (
    validate_medical_upload,
    generate_secure_storage_filename,
    store_private_medical_document
)
from spherix.security.compliance import (
    anonymize_phi_for_external_ai,
    record_patient_consent
)

__all__ = [
    'hash_password',
    'verify_password',
    'validate_password_strength',
    'generate_mfa_secret',
    'get_totp_uri',
    'generate_mfa_qr_base64',
    'generate_backup_recovery_codes',
    'verify_totp_token',
    'verify_and_consume_recovery_code',
    'is_mfa_mandatory_for_role',
    'encrypt_field',
    'decrypt_field',
    'encrypt_sensitive_dict',
    'decrypt_sensitive_dict',
    'create_encrypted_database_backup',
    'verify_backup_integrity',
    'ROLE_SUPER_ADMIN',
    'ROLE_HOSPITAL_ADMIN',
    'ROLE_DOCTOR',
    'ROLE_PATIENT',
    'ROLE_NURSE',
    'ROLE_RECEPTIONIST',
    'ROLE_PHARMACY',
    'ROLE_LABORATORY',
    'ROLE_BILLING',
    'ROLE_INSURANCE_ADMIN',
    'get_current_user_role',
    'has_permission',
    'require_role',
    'require_permission',
    'verify_patient_ownership',
    'verify_hospital_ownership',
    'log_security_event',
    'get_security_command_center_telemetry',
    'prune_audit_logs',
    'register_new_session',
    'validate_active_session',
    'revoke_session',
    'revoke_all_user_sessions',
    'get_user_active_sessions',
    'purge_expired_sessions',
    'inspect_incoming_request',
    'is_safe_external_url',
    'apply_enterprise_security_headers',
    'ban_ip',
    'unban_ip',
    'get_blocked_ips',
    'is_ip_banned',
    'get_waf_mode',
    'set_waf_mode',
    'validate_medical_upload',
    'generate_secure_storage_filename',
    'store_private_medical_document',
    'anonymize_phi_for_external_ai',
    'record_patient_consent'
]

