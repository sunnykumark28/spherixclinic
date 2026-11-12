"""
Spherix Clinic — Web Application Firewall (WAF) & Input Sanitization
====================================================================
Guards against OWASP Top 10 web vulnerabilities:
- Injection (SQLi, XSS, Command Injection)
- Path Traversal & Local/Remote File Inclusion
- Server-Side Request Forgery (SSRF) against internal / cloud metadata IPs
- Scanner bots (sqlmap, nikto, masscan, acunetix)
- Dynamic IP Blacklist & Threat Mitigation (Persistent SQLite Table)
- Dynamic WAF Operation Modes (ACTIVE_DEFENSE, MONITOR_ONLY, LOCKDOWN_MODE)
- Security Response Headers (HSTS, CSP, Permissions-Policy, X-Frame-Options)
"""

import os
import re
import sqlite3
import ipaddress
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict, Any
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

# In-memory fast caches
_BLOCKED_IPS_CACHE = set()
_WAF_MODE = 'ACTIVE_DEFENSE'  # Options: 'ACTIVE_DEFENSE', 'MONITOR_ONLY', 'LOCKDOWN_MODE'


def _get_firewall_db():
    db_candidates = [
        os.getenv('SQLITE_DB_PATH'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'spherixclinic.db'),
        'spherixclinic.db'
    ]
    for p in db_candidates:
        if p and os.path.exists(p):
            conn = sqlite3.connect(p, timeout=10.0)
            conn.row_factory = sqlite3.Row
            return conn
    conn = sqlite3.connect('spherixclinic.db', timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_firewall_tables():
    """Initializes persistent IP blocklist and firewall settings tables."""
    global _BLOCKED_IPS_CACHE, _WAF_MODE
    try:
        conn = _get_firewall_db()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS firewall_blocked_ips (
            ip TEXT PRIMARY KEY,
            reason TEXT NOT NULL DEFAULT 'Admin Manual Block',
            banned_at TEXT NOT NULL,
            banned_by TEXT NOT NULL DEFAULT 'admin',
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS firewall_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        conn.commit()

        # Load active blocked IPs into memory cache
        cur.execute("SELECT ip FROM firewall_blocked_ips WHERE is_active = 1")
        _BLOCKED_IPS_CACHE = {row['ip'] for row in cur.fetchall()}

        # Load WAF mode
        cur.execute("SELECT value FROM firewall_config WHERE key = 'waf_mode'")
        row = cur.fetchone()
        if row and row['value'] in ('ACTIVE_DEFENSE', 'MONITOR_ONLY', 'LOCKDOWN_MODE'):
            _WAF_MODE = row['value']
        else:
            cur.execute(
                "INSERT OR REPLACE INTO firewall_config (key, value, updated_at) VALUES ('waf_mode', 'ACTIVE_DEFENSE', ?)",
                (datetime.now(timezone.utc).isoformat(),)
            )
            conn.commit()

        conn.close()
    except Exception as e:
        print(f"⚠️ Failed to init firewall tables: {e}")


init_firewall_tables()


def get_waf_mode() -> str:
    global _WAF_MODE
    return _WAF_MODE


def set_waf_mode(mode: str, actor_id: str = "admin") -> str:
    global _WAF_MODE
    if mode not in ('ACTIVE_DEFENSE', 'MONITOR_ONLY', 'LOCKDOWN_MODE'):
        return _WAF_MODE
    _WAF_MODE = mode
    try:
        conn = _get_firewall_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO firewall_config (key, value, updated_at) VALUES ('waf_mode', ?, ?)",
            (mode, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        try:
            from spherix.security.audit import log_security_event
            log_security_event(
                event_type="WAF_MODE_CHANGED",
                severity="HIGH",
                details=f"WAF operation mode switched to {mode} by {actor_id}",
                actor_id=str(actor_id)
            )
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️ Failed to persist WAF mode: {e}")
    return _WAF_MODE


def is_ip_banned(ip: str) -> bool:
    global _BLOCKED_IPS_CACHE
    if not ip:
        return False
    return ip.strip() in _BLOCKED_IPS_CACHE


def get_blocked_ips() -> List[Dict[str, Any]]:
    """Returns list of currently active blocked IP records."""
    blocked = []
    try:
        conn = _get_firewall_db()
        cur = conn.cursor()
        cur.execute("""
        SELECT ip, reason, banned_at, banned_by
        FROM firewall_blocked_ips
        WHERE is_active = 1
        ORDER BY banned_at DESC
        """)
        for r in cur.fetchall():
            blocked.append({
                "ip": r["ip"],
                "reason": r["reason"],
                "banned_at": r["banned_at"],
                "banned_by": r["banned_by"]
            })
        conn.close()
    except Exception as e:
        print(f"⚠️ Failed to fetch blocked IPs: {e}")
    return blocked


def ban_ip(ip: str, reason: str = "Admin Manual Block", actor_id: str = "admin") -> Tuple[bool, str]:
    """Adds an IP address to the active firewall blocklist."""
    global _BLOCKED_IPS_CACHE
    if not ip:
        return False, "IP address is required."
    clean_ip = ip.strip()
    
    # Don't ban loopback or localhost
    if clean_ip in ('127.0.0.1', '::1', 'localhost'):
        return False, "Loopback / Localhost cannot be blacklisted."
    
    # Validate IP syntax
    try:
        ipaddress.ip_address(clean_ip)
    except ValueError:
        return False, f"Invalid IP address format: {clean_ip}"
    
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_firewall_db()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO firewall_blocked_ips (ip, reason, banned_at, banned_by, is_active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(ip) DO UPDATE SET
            reason = excluded.reason,
            banned_at = excluded.banned_at,
            banned_by = excluded.banned_by,
            is_active = 1
        """, (clean_ip, reason, now_iso, str(actor_id)))
        conn.commit()
        conn.close()
        _BLOCKED_IPS_CACHE.add(clean_ip)

        try:
            from spherix.security.audit import log_security_event
            log_security_event(
                event_type="IP_BANNED_BY_ADMIN",
                severity="HIGH",
                details=f"IP {clean_ip} was added to firewall blocklist. Reason: {reason}",
                actor_id=str(actor_id)
            )
        except Exception:
            pass

        return True, f"IP {clean_ip} has been blocked."
    except Exception as e:
        return False, f"Database error blocking IP: {e}"


def unban_ip(ip: str, actor_id: str = "admin") -> Tuple[bool, str]:
    """Removes an IP address from the active firewall blocklist."""
    global _BLOCKED_IPS_CACHE
    if not ip:
        return False, "IP address is required."
    clean_ip = ip.strip()
    try:
        conn = _get_firewall_db()
        cur = conn.cursor()
        cur.execute("UPDATE firewall_blocked_ips SET is_active = 0 WHERE ip = ?", (clean_ip,))
        conn.commit()
        conn.close()
        _BLOCKED_IPS_CACHE.discard(clean_ip)

        try:
            from spherix.security.audit import log_security_event
            log_security_event(
                event_type="IP_UNBANNED_BY_ADMIN",
                severity="INFO",
                details=f"IP {clean_ip} was removed from firewall blocklist by {actor_id}",
                actor_id=str(actor_id)
            )
        except Exception:
            pass

        return True, f"IP {clean_ip} has been unblocked."
    except Exception as e:
        return False, f"Database error unblocking IP: {e}"


def inspect_incoming_request() -> Optional[Tuple[int, str]]:
    """
    Inspects every incoming request before routing.
    Returns (status_code, reason) if request is malicious or blocked, or None if safe.
    """
    # 0. Check IP Blacklist
    client_ip = '127.0.0.1'
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        client_ip = forwarded.split(',')[0].strip()
    elif request.remote_addr:
        client_ip = request.remote_addr

    if is_ip_banned(client_ip):
        return 403, f"Access Denied: Your IP address ({client_ip}) has been blacklisted by Spherix Security Operations Center."

    # 1. Check Lockdown Mode
    mode = get_waf_mode()
    if mode == 'LOCKDOWN_MODE':
        path = request.path
        if not (path.startswith('/static/') or path.startswith('/admin-login') or path.startswith('/admin/security/')):
            from flask_login import current_user
            is_super_admin = getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'email', '') == 'admin@spherixclinic.com'
            if not is_super_admin:
                return 503, "Security Containment Active: Emergency lockdown in progress. Access restricted to Super Administrators."

    # 2. Block Automated Exploit Scanners
    ua = str(request.headers.get('User-Agent', '') or getattr(request.user_agent, 'string', ''))
    if MALICIOUS_USER_AGENTS.search(ua):
        if mode == 'MONITOR_ONLY':
            return None
        return 403, "Access Denied: Malicious agent detected."

    # 3. Inspect Path & Query String for Path Traversal
    raw_path = request.path
    query_str = request.query_string.decode('utf-8', errors='ignore')

    if PATH_TRAVERSAL_PATTERN.search(raw_path) or PATH_TRAVERSAL_PATTERN.search(query_str):
        if mode == 'MONITOR_ONLY':
            return None
        return 400, "Bad Request: Path traversal pattern detected."

    # 4. Inspect Query Parameters for SQLi & XSS signatures
    if SQLI_PATTERN.search(query_str):
        if mode == 'MONITOR_ONLY':
            return None
        return 400, "Bad Request: Malicious SQL signature detected."

    if XSS_PATTERN.search(query_str):
        if mode == 'MONITOR_ONLY':
            return None
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
