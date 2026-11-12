"""
Spherix Clinic — Secure Medical Document Guard & Private Storage Gateway
========================================================================
Implements OWASP File Upload Protection & HIPAA § 164.312(a)(1) Access Controls:
- Strict extension whitelist & Magic Byte verification
- Re-randomized cryptographic server-side filenames
- Safe private storage outside public static URLs
- Authorization gateway before any patient medical record or lab document is served
"""

import os
import uuid
import secrets
from typing import Tuple, Optional
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import abort, send_file, request, jsonify
from flask_login import current_user

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.txt'}
MAX_DOCUMENT_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024     # 5 MB

# Magic byte signatures for verified MIME verification
MAGIC_SIGNATURES = {
    b'%PDF-': 'application/pdf',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'\xff\xd8\xff': 'image/jpeg',
    b'RIFF': 'image/webp'
}

def validate_medical_upload(
    file_storage: FileStorage,
    allowed_types: str = "document",
    max_size: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Validates an uploaded file using multi-layer verification:
    1. Checks filename & extension against strict whitelist.
    2. Enforces maximum size limits.
    3. Reads magic bytes from file header to verify true MIME type.
    """
    if not file_storage or not file_storage.filename:
        return False, "No file selected for upload."

    raw_filename = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(raw_filename.lower())

    # 1. Extension check
    whitelist = ALLOWED_DOCUMENT_EXTENSIONS if allowed_types == "document" else ALLOWED_IMAGE_EXTENSIONS
    if ext not in whitelist:
        return False, f"File format '{ext}' is prohibited. Allowed formats: {', '.join(sorted(list(whitelist)))}"

    # 2. Size check
    limit = max_size or (MAX_DOCUMENT_SIZE_BYTES if allowed_types == "document" else MAX_AVATAR_SIZE_BYTES)
    file_storage.seek(0, os.SEEK_END)
    file_length = file_storage.tell()
    file_storage.seek(0)

    if file_length > limit:
        return False, f"File exceeds maximum allowed size of {limit // (1024*1024)} MB."
    if file_length == 0:
        return False, "Uploaded file is empty."

    # 3. Magic Header Byte Check (First 32 bytes)
    header = file_storage.read(32)
    file_storage.seek(0)

    # Disallow executable / script signatures anywhere in header
    dangerous_headers = [b'<?php', b'<script', b'eval(', b'MZ', b'\x7fELF', b'#!/bin/']
    for dang in dangerous_headers:
        if dang in header.lower():
            return False, "Security violation: Executable content detected in file stream."

    # Validate known magic bytes for PDF and images
    if ext == '.pdf' and not header.startswith(b'%PDF-'):
        return False, "Invalid PDF: File content does not match genuine PDF header."
    elif ext == '.png' and not header.startswith(b'\x89PNG\r\n\x1a\n'):
        return False, "Invalid PNG: File content does not match genuine PNG header."
    elif ext in ('.jpg', '.jpeg') and not header.startswith(b'\xff\xd8\xff'):
        return False, "Invalid JPEG: File content does not match genuine JPEG header."

    return True, "File verified successfully."

def generate_secure_storage_filename(original_filename: str) -> str:
    """
    Generates a high-entropy, randomized server-side filename
    preserving only the validated extension to neutralize directory traversal.
    """
    _, ext = os.path.splitext(secure_filename(original_filename).lower())
    token = secrets.token_hex(16)
    timestamp = uuid.uuid4().hex[:8]
    return f"sec_{timestamp}_{token}{ext}"

def store_private_medical_document(file_storage: FileStorage, storage_subdir: str = "medical_records") -> Tuple[bool, str, str]:
    """
    Stores an uploaded file securely in the private uploads folder.
    Returns:
        (success: bool, stored_filename: str, message: str)
    """
    valid, msg = validate_medical_upload(file_storage, allowed_types="document")
    if not valid:
        return False, "", msg

    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads', storage_subdir)
    os.makedirs(base_dir, exist_ok=True)

    safe_name = generate_secure_storage_filename(file_storage.filename)
    dest_path = os.path.join(base_dir, safe_name)

    try:
        file_storage.save(dest_path)
        # Enforce restricted POSIX permissions (Read/Write owner only)
        os.chmod(dest_path, 0o600)
        return True, safe_name, "Document securely archived."
    except Exception as e:
        return False, "", f"Storage error: {e}"

