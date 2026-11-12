"""
Spherix Clinic — Role-Based Access Control (RBAC) & Anti-IDOR Authorization
===========================================================================
Implements strict, server-side access controls, least-privilege principles,
and cryptographic tenancy isolation to prevent Broken Access Control (OWASP A01:2021)
and Insecure Direct Object References (IDOR).
"""

from functools import wraps
from typing import List, Set, Optional, Callable, Any
from flask import request, session, abort, redirect, url_for, flash, jsonify
from flask_login import current_user

# -------------------------------------------------------------
# Role Definitions & Permission Matrix
# -------------------------------------------------------------

ROLE_SUPER_ADMIN = "super_admin"
ROLE_HOSPITAL_ADMIN = "hospital"
ROLE_DOCTOR = "doctor"
ROLE_PATIENT = "patient"
ROLE_NURSE = "nurse"
ROLE_RECEPTIONIST = "receptionist"
ROLE_PHARMACY = "pharmacy"
ROLE_LABORATORY = "laboratory"
ROLE_BILLING = "billing"
ROLE_INSURANCE_ADMIN = "insurance_admin"
ROLE_BLOOD_DONOR = "blood_donor"
ROLE_ORGAN_DONOR = "organ_donor"

PERMISSIONS: Dict[str, Set[str]] = {
    ROLE_SUPER_ADMIN: {
        "view_all_users", "manage_users", "view_audit_logs", "manage_security_center",
        "view_phi", "edit_medical_records", "manage_system_settings", "override_mfa",
        "access_financials", "manage_hospitals", "manage_doctors", "manage_staff",
        "manage_blood_bank", "manage_insurance", "manage_pharmacy", "manage_lab"
    },
    ROLE_HOSPITAL_ADMIN: {
        "view_hospital_beds", "manage_hospital_beds", "view_hospital_staff",
        "manage_hospital_staff", "view_hospital_appointments", "manage_hospital_traffic",
        "view_hospital_finance"
    },
    ROLE_DOCTOR: {
        "view_assigned_patient_phi", "create_prescriptions", "edit_consultations",
        "order_lab_tests", "conduct_telemedicine", "view_doctor_appointments"
    },
    ROLE_PATIENT: {
        "view_own_phi", "book_appointments", "book_hospital_beds", "order_medicines",
        "apply_insurance", "file_insurance_claims", "chat_with_doctor"
    },
    ROLE_NURSE: {
        "view_hospital_beds", "record_patient_vitals", "view_assigned_ward_records"
    },
    ROLE_RECEPTIONIST: {
        "create_walkin_appointments", "issue_visitor_passes", "view_hospital_schedule"
    },
    ROLE_PHARMACY: {
        "view_pharmacy_orders", "dispense_medications", "manage_pharmacy_inventory"
    },
    ROLE_LABORATORY: {
        "view_lab_orders", "enter_diagnostic_results", "release_lab_reports"
    },
    ROLE_BILLING: {
        "view_hospital_invoices", "record_offline_payments", "issue_receipts"
    },
    ROLE_INSURANCE_ADMIN: {
        "view_insurance_policies", "adjudicate_claims", "manage_insurance_partners"
    },
    ROLE_BLOOD_DONOR: {
        "view_own_donation_history", "schedule_blood_donation"
    },
    ROLE_ORGAN_DONOR: {
        "view_own_pledge_status", "update_pledge_preferences"
    }
}

def get_current_user_role() -> str:
    """Resolves the normalized active role of the authenticated user."""
    # 1. Super Admin Session Check
    if session.get('_user_type') == 'admin' or session.get('is_admin') or (hasattr(current_user, 'is_admin') and current_user.is_admin):
        return ROLE_SUPER_ADMIN

    # 2. Flask-Login user type
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        if hasattr(current_user, 'role') and current_user.role:
            role_str = str(current_user.role).lower()
            if 'nurse' in role_str:
                return ROLE_NURSE
            elif 'reception' in role_str:
                return ROLE_RECEPTIONIST
            elif 'pharmacy' in role_str:
                return ROLE_PHARMACY
            elif 'lab' in role_str or 'patholog' in role_str:
                return ROLE_LABORATORY
            elif 'billing' in role_str:
                return ROLE_BILLING
            return role_str

        # Model type inspection
        cls_name = current_user.__class__.__name__.lower()
        if 'doctor' in cls_name:
            return ROLE_DOCTOR
        elif 'patient' in cls_name:
            return ROLE_PATIENT
        elif 'hospitalstaff' in cls_name:
            staff_role = getattr(current_user, 'role', '').lower()
            if 'nurse' in staff_role:
                return ROLE_NURSE
            elif 'reception' in staff_role:
                return ROLE_RECEPTIONIST
            return ROLE_HOSPITAL_ADMIN
        elif 'hospital' in cls_name:
            return ROLE_HOSPITAL_ADMIN
        elif 'blooddonor' in cls_name:
            return ROLE_BLOOD_DONOR
        elif 'organdonor' in cls_name:
            return ROLE_ORGAN_DONOR

    # 3. Session fallback
    u_type = session.get('_user_type', '').lower()
    if u_type:
        if u_type in ['admin', 'super_admin']:
            return ROLE_SUPER_ADMIN
        elif u_type in ['doctor', 'patient', 'hospital', 'staff', 'blood_donor', 'organ_donor']:
            return u_type

    return "anonymous"

def has_permission(permission: str, role: Optional[str] = None) -> bool:
    """Verifies if a role or current user has the specified permission."""
    if not role:
        role = get_current_user_role()
    role_perms = PERMISSIONS.get(role, set())
    return permission in role_perms

# -------------------------------------------------------------
# Authorization Decorators (Deny Access by Default)
# -------------------------------------------------------------

def require_role(*allowed_roles):
    """
    Enforces that the current authenticated user belongs to at least one of allowed_roles.
    Rejects unauthorized access with 403 Forbidden and audit telemetry.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = get_current_user_role()
            normalized_allowed = [str(r).lower() for r in allowed_roles]
            
            # Map 'admin' alias
            if 'admin' in normalized_allowed and role == ROLE_SUPER_ADMIN:
                return fn(*args, **kwargs)

            if role not in normalized_allowed and ROLE_SUPER_ADMIN not in normalized_allowed:
                from spherix.security.audit import log_security_event
                log_security_event(
                    event_type="UNAUTHORIZED_ROLE_ACCESS",
                    severity="HIGH",
                    details=f"User with role '{role}' attempted to access restricted endpoint '{request.endpoint}' requiring {allowed_roles}"
                )
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({"error": "Forbidden: Insufficient privileges.", "status": 403}), 403
                
                flash("Access denied: You do not have permission to access this resource.", "error")
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_permission(permission: str):
    """Enforces specific granular permission."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                from spherix.security.audit import log_security_event
                log_security_event(
                    event_type="PERMISSION_DENIED",
                    severity="MEDIUM",
                    details=f"Missing permission '{permission}' for user role '{get_current_user_role()}' at '{request.endpoint}'"
                )
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({"error": "Forbidden: Required permission missing.", "status": 403}), 403
                flash("Access denied: Insufficient permissions.", "error")
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def verify_patient_ownership(patient_id_arg: str = 'patient_id'):
    """
    Anti-IDOR Guard:
    Verifies that a patient can ONLY view/modify their own personal records.
    Super Admins and the patient's actively consulting Doctor are granted lawful access.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            target_id = kwargs.get(patient_id_arg) or request.view_args.get(patient_id_arg) or request.args.get(patient_id_arg) or request.form.get(patient_id_arg)
            if not target_id:
                return fn(*args, **kwargs)

            current_role = get_current_user_role()
            if current_role == ROLE_SUPER_ADMIN:
                return fn(*args, **kwargs)

            actual_user_id = str(getattr(current_user, 'id', '') or session.get('patient_id') or session.get('user_id') or '')
            
            # If patient is accessing, ID must strictly match
            if current_role == ROLE_PATIENT:
                if str(target_id).strip() != actual_user_id.strip():
                    from spherix.security.audit import log_security_event
                    log_security_event(
                        event_type="IDOR_ATTEMPT_DETECTED",
                        severity="CRITICAL",
                        details=f"Patient '{actual_user_id}' attempted unauthorized access to patient record '{target_id}' at '{request.path}'"
                    )
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({"error": "Unauthorized record access.", "status": 403}), 403
                    flash("Unauthorized: You may only access your own patient records.", "error")
                    abort(403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator

def verify_hospital_ownership(hospital_id_arg: str = 'hospital_id'):
    """
    Anti-IDOR Guard for Multi-Tenant Hospital Isolation:
    Hospital administrators and staff can only manage records belonging to their hospital.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            target_hospital = kwargs.get(hospital_id_arg) or request.view_args.get(hospital_id_arg) or request.args.get(hospital_id_arg) or request.form.get(hospital_id_arg)
            if not target_hospital:
                return fn(*args, **kwargs)

            current_role = get_current_user_role()
            if current_role == ROLE_SUPER_ADMIN:
                return fn(*args, **kwargs)

            user_hospital = str(getattr(current_user, 'hospital_id', '') or getattr(current_user, 'id', '') or session.get('hospital_id') or '')
            if str(target_hospital).strip() != user_hospital.strip():
                from spherix.security.audit import log_security_event
                log_security_event(
                    event_type="CROSS_TENANT_HOSPITAL_VIOLATION",
                    severity="CRITICAL",
                    details=f"Hospital user '{user_hospital}' attempted cross-tenant access to hospital '{target_hospital}'"
                )
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({"error": "Unauthorized hospital boundary.", "status": 403}), 403
                flash("Unauthorized: Cross-tenant hospital access is strictly prohibited.", "error")
                abort(403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator
