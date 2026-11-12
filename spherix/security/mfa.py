"""
Spherix Clinic — Multi-Factor Authentication (MFA / 2FA Engine)
==============================================================
Implements RFC 6238 Time-based One-Time Password (TOTP) algorithm,
QR code provisioning, cryptographic backup recovery codes, and mandatory
MFA policies for Super Admins and privileged healthcare personnel.
"""

import io
import base64
import secrets
from typing import Tuple, List, Optional, Dict, Any
import pyotp
import qrcode
from qrcode.image.pil import PilImage

ISSUER_NAME = "Spherix Clinic"

def generate_mfa_secret() -> str:
    """Generates a secure 32-character base32 secret for TOTP."""
    return pyotp.random_base32()

def get_totp_uri(secret: str, user_email: str) -> str:
    """Generates the RFC 6238 standard TOTP provisioning URI."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=user_email, issuer_name=ISSUER_NAME)

def generate_mfa_qr_base64(secret: str, user_email: str) -> str:
    """
    Renders a PNG QR Code as a data URL for scanning by Google Authenticator,
    Microsoft Authenticator, Apple Passwords, or Authy.
    """
    uri = get_totp_uri(secret, user_email)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="#0c2340", back_color="#ffffff")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64_img = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_img}"

def generate_backup_recovery_codes(count: int = 8) -> Tuple[List[str], List[str]]:
    """
    Generates single-use cryptographic recovery codes.
    Returns:
        (raw_codes: List[str], hashed_codes: List[str])
    The user sees raw_codes once. Only cryptographic hashes are stored.
    """
    from spherix.security.hashing import hash_password
    raw_codes = []
    hashed_codes = []
    for _ in range(count):
        # Format: XXXX-XXXX (e.g. A3F8-9D2B)
        code = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        raw_codes.append(code)
        hashed_codes.append(hash_password(code))
    return raw_codes, hashed_codes

def verify_totp_token(secret: str, token: str, valid_window: int = 1) -> bool:
    """
    Verifies a 6-digit TOTP token against the user's secret.
    Allows a 30-second clock skew window (valid_window=1) to prevent false rejections.
    """
    if not secret or not token:
        return False
    
    clean_token = str(token).strip().replace(" ", "").replace("-", "")
    if len(clean_token) != 6 or not clean_token.isdigit():
        return False

    totp = pyotp.TOTP(secret)
    return bool(totp.verify(clean_token, valid_window=valid_window))

def verify_and_consume_recovery_code(entered_code: str, stored_hashed_codes: List[str]) -> Tuple[bool, List[str]]:
    """
    Verifies an entered backup code against stored hashes.
    If valid, burns (removes) the consumed backup code and returns the remaining list.
    """
    from spherix.security.hashing import verify_password
    if not entered_code or not stored_hashed_codes:
        return False, stored_hashed_codes

    clean_code = str(entered_code).strip().upper()
    remaining = []
    matched = False

    for stored_hash in stored_hashed_codes:
        if not matched:
            valid, _ = verify_password(stored_hash, clean_code)
            if valid:
                matched = True
                continue  # Exclude consumed code
        remaining.append(stored_hash)

    return matched, remaining

def is_mfa_mandatory_for_role(user_type: str) -> bool:
    """
    Enforces HIPAA & ISO 27001 standard:
    Super Admin, Hospital Admin, and Pharmacy/Lab administrative roles
    require mandatory MFA.
    """
    mandatory_roles = {'admin', 'super_admin', 'hospital_admin', 'doctor', 'hospital'}
    return str(user_type).lower() in mandatory_roles

