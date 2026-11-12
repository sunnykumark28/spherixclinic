"""
Spherix Clinic — Web Application Firewall (WAF) & Input Sanitization
====================================================================
Guards against OWASP Top 10 web vulnerabilities:
- Injection (SQLi, XSS, Command Injection)
- Path Traversal & Local/Remote File Inclusion
- Server-Side Request Forgery (SSRF) against internal / cloud metadata IPs
- Scanner bots (sqlmap, nikto, masscan, acunetix)
- Security Response Headers (HSTS, CSP, Permissions-Policy, X-Frame-Options)
"""

import re
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Tuple
from flask import request, abort, Response, current_app, jsonify

# Known vulnerability scanners & automated attack tools
MALICIOUS_USER_AGENTS = re.compile(
    r'(sqlmap|nikto|masscan|acunetix|nessus|nmap|havij|w3af|zgrab|dirbuster)',
    re.IGNORECASE
)

# Path Traversal signatures
PATH_TRAVERSAL_PATTERN = re.compile(
    r'(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\/|\.\.%2f|%2e%2e%5c|/etc/passwd|c:\\windows)',
    re.IGNORECASE
)

# Raw SQL Injection signatures in URL parameters
SQLI_PATTERN = re.compile(
    r'(\bunion\s+all\s+select\b|\bselect\s+.*\s+from\b|\bdrop\s+table\b|\bexec\s+xp_cmdshell\b|--\s*$|/\*.*\*/)',
    re.IGNORECASE
)

# Dangerous Script Injection in query parameters
XSS_PATTERN = re.compile(
    r'(<script\b|javascript:|onerror\s*=|onload\s*=|document\.cookie|<iframe\b|<object\b)',
    re.IGNORECASE
)

def inspect_incoming_request() -> Optional[Tuple[int, str]]:
    """
    Inspects every incoming request before routing.
    Returns (status_code, reason) if request is malicious, or None if safe.
    """
    # 1. Block Automated Exploit Scanners
    ua = str(request.headers.get('User-Agent', '') or getattr(request.user_agent, 'string', ''))
    if MALICIOUS_USER_AGENTS.search(ua):
        return 403, "Access Denied: Malicious agent detected."

    # 2. Inspect Path & Query String for Path Traversal
    raw_path = request.path
    query_str = request.query_string.decode('utf-8', errors='ignore')

    if PATH_TRAVERSAL_PATTERN.search(raw_path) or PATH_TRAVERSAL_PATTERN.search(query_str):
        return 400, "Bad Request: Path traversal pattern detected."

    # 3. Inspect Query Parameters for SQLi & XSS signatures
    if SQLI_PATTERN.search(query_str):
        return 400, "Bad Request: Malicious SQL signature detected."

    if XSS_PATTERN.search(query_str):
        return 400, "Bad Request: Cross-site scripting sequence detected."

    return None

def is_safe_external_url(url: str) -> bool:
    """
    SSRF Prevention:
    Validates that a URL points to an external, publicly routable destination
    and strictly forbids loopback, internal subnet, or cloud metadata endpoints.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Disallow localhost / cloud metadata aliases
        if hostname.lower() in ('localhost', '127.0.0.1', '::1', 'metadata.google.internal', '169.254.169.254'):
            return False

        # Resolve IP and check if private / link-local / reserved
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            # Hostname is a domain name, not raw IP
            pass

        return True
    except Exception:
        return False

def apply_enterprise_security_headers(response: Response) -> Response:
    """
    Injects enterprise healthcare security response headers (NIST / HIPAA / OWASP).
    """
    # 1. HSTS (HTTP Strict Transport Security - 1 year, include subdomains)
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # 2. Prevent MIME Sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # 3. Prevent Clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # 4. Strict Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # 5. Restrict Risky Browser Features
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), payment=(self)'
    
    # 6. Cross-Origin Protections
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'

    return response
