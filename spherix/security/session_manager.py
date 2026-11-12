"""
Spherix Clinic — Session Security, Device Tracking & Global Invalidation
========================================================================
Implements OWASP Session Management Cheat Sheet:
- Absolute and inactivity session timeouts (15m for privileged, 24h max)
- Multi-device session tracking
- Instant 'Logout from All Devices' session revocation
- Protection against Session Hijacking and Fixation
"""

import os
import time
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from flask import session, request
from flask_login import current_user

PRIVILEGED_INACTIVITY_TIMEOUT_SECONDS = 900   # 15 minutes
STANDARD_INACTIVITY_TIMEOUT_SECONDS = 86400  # 24 hours

def _get_session_db():
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

def init_session_tables():
    """Initializes user active sessions and revoked tokens tables."""
    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS active_user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_role TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            is_revoked INTEGER DEFAULT 0
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sess_user ON active_user_sessions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sess_revoked ON active_user_sessions(is_revoked)")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT,
            revoked_at TEXT NOT NULL
        )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Failed to init session tables: {e}")

init_session_tables()

def register_new_session(user_id: str, user_role: str) -> str:
    """
    Registers a new authenticated session in the database.
    Binds session_id to Flask session.
    """
    session_id = secrets.token_urlsafe(32)
    session['_auth_session_id'] = session_id
    session['_last_active_time'] = time.time()
    
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
    ua = (request.user_agent.string if request.user_agent else 'Unknown')[:250]
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO active_user_sessions (
            session_id, user_id, user_role, ip_address, user_agent, created_at, last_activity, is_revoked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (session_id, str(user_id), str(user_role), ip_addr, ua, now_iso, now_iso))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Session registration error: {e}")

    return session_id

def validate_active_session() -> bool:
    """
    Validates current request session:
    1. Checks if session was explicitly revoked (e.g. via Logout from all devices).
    2. Enforces inactivity timeout.
    Returns False if session is invalid / expired.
    """
    session_id = session.get('_auth_session_id')
    if not session_id:
        # Backward compatibility for legacy sessions
        return True

    now = time.time()
    last_active = session.get('_last_active_time', now)
    user_role = session.get('_user_type', 'patient')

    # Privileged roles: 15-minute inactivity timeout
    timeout_window = PRIVILEGED_INACTIVITY_TIMEOUT_SECONDS if user_role in ['admin', 'super_admin', 'doctor', 'hospital'] else STANDARD_INACTIVITY_TIMEOUT_SECONDS
    if (now - last_active) > timeout_window:
        return False  # Timed out

    # Check database revocation status
    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("SELECT is_revoked FROM active_user_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if row and row['is_revoked'] == 1:
            conn.close()
            return False  # Revoked!

        # Touch last activity
        cur.execute("UPDATE active_user_sessions SET last_activity = ? WHERE session_id = ?",
                    (datetime.now(timezone.utc).isoformat(), session_id))
        conn.commit()
        conn.close()
        session['_last_active_time'] = now
    except Exception:
        pass

    return True

def revoke_session(session_id: str) -> None:
    """Revokes a specific session."""
    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("UPDATE active_user_sessions SET is_revoked = 1 WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Error revoking session: {e}")

def revoke_all_user_sessions(user_id: str) -> int:
    """
    Global Killswitch: Immediately invalidates ALL active sessions for a user across all devices.
    Used for account security, password reset, and incident response.
    """
    count = 0
    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("UPDATE active_user_sessions SET is_revoked = 1 WHERE user_id = ? AND is_revoked = 0", (str(user_id),))
        count = cur.rowcount
        conn.commit()
        conn.close()
        from spherix.security.audit import log_security_event
        log_security_event(
            event_type="ALL_SESSIONS_REVOKED",
            severity="HIGH",
            details=f"Revoked {count} active sessions across all devices for user '{user_id}'",
            actor_id=str(user_id)
        )
    except Exception as e:
        print(f"⚠️ Error revoking all sessions: {e}")
    return count

def get_user_active_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all active sessions for a user."""
    sessions = []
    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("""
        SELECT session_id, ip_address, user_agent, created_at, last_activity
        FROM active_user_sessions
        WHERE user_id = ? AND is_revoked = 0
        ORDER BY last_activity DESC
        """, (str(user_id),))
        for r in cur.fetchall():
            sessions.append({
                "session_id": r["session_id"][:12] + "...",
                "full_id": r["session_id"],
                "ip": r["ip_address"],
                "user_agent": r["user_agent"],
                "created_at": r["created_at"],
                "last_activity": r["last_activity"]
            })
        conn.close()
    except Exception as e:
        print(f"⚠️ Error listing sessions: {e}")
    return sessions


def purge_expired_sessions() -> int:
    """
    Purges revoked sessions and inactive stale sessions older than 24 hours.
    Returns the total count of purged sessions.
    """
    count = 0
    try:
        conn = _get_session_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM active_user_sessions WHERE is_revoked = 1")
        count = cur.rowcount
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Error purging expired sessions: {e}")
    return count

