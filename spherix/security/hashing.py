"""
Spherix Clinic — Advanced Password Security & Argon2id Hashing
==============================================================
Provides high-security Argon2id password hashing, constant-time verification,
and automatic upgrade of legacy hashes (PBKDF2/SHA256) upon successful login.
"""

import os
import re
import hmac
from typing import Tuple, Optional
import argon2
from werkzeug.security import check_password_hash as werkzeug_check_hash, generate_password_hash as werkzeug_gen_hash

# Configure enterprise-grade Argon2id parameters (OWASP / RFC 9106 recommendations)
# Memory cost: 64 MB (65536 KiB), Time cost: 2 iterations, Parallelism: 1 thread, Type: Argon2id
_argon2_hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID
)

# Common weak passwords to reject
COMMON_WEAK_PASSWORDS = {
    'password', 'password123', 'admin', 'admin123', 'spherix', 'spherix123',
    'hospital123', 'doctor123', 'patient123', 'welcome123', '12345678', 'qwerty1234'
}

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Argon2id.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    try:
        return _argon2_hasher.hash(password)
    except Exception as e:
        # Fallback to high-iteration PBKDF2 if Argon2 binding fails
        return werkzeug_gen_hash(password, method='pbkdf2:sha256:600000')

def verify_password(stored_hash: Optional[str], password: Optional[str]) -> Tuple[bool, bool]:
    """
    Verifies a password against the stored hash in constant time.
    Supports both modern Argon2id and legacy PBKDF2/scrypt hashes.
    
    Returns:
        (is_valid: bool, needs_rehash: bool)
    """
    if not stored_hash or not password:
        return False, False

    # 1. Check if stored hash is Argon2
    if stored_hash.startswith('$argon2'):
        try:
            _argon2_hasher.verify(stored_hash, password)
            needs_rehash = _argon2_hasher.check_needs_rehash(stored_hash)
            return True, needs_rehash
        except argon2.exceptions.VerifyMismatchError:
            return False, False
        except Exception:
            return False, False

    # 2. Check legacy Werkzeug/PBKDF2/scrypt hash
    try:
        if werkzeug_check_hash(stored_hash, password):
            # Valid match with legacy hash -> flag for rehash to Argon2id
            return True, True
    except Exception:
        pass

    # 3. Direct constant-time string comparison for legacy bootstrap passwords (fallback)
    try:
        if hmac.compare_digest(stored_hash.encode('utf-8'), password.encode('utf-8')):
            return True, True
    except Exception:
        pass

    return False, False

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Enforces healthcare-grade password complexity (NIST SP 800-63B & HIPAA):
    - Minimum 8 characters (12 recommended for admins)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one numeric digit
    - At least one special symbol
    - Not in known common weak dictionary
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False, "Password is too common and easily guessable. Please choose a stronger password."

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one numeric digit."

    if not re.search(r'[^A-Za-z0-9]', password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)."

    return True, "Password meets security requirements."

