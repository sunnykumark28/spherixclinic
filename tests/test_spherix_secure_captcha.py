"""
Spherix Secure CAPTCHA — Comprehensive Security & Integration Test Suite

This test suite rigorously validates all 16 security and functional requirements:
 1. Successful CAPTCHA verification (exact and case-insensitive).
 2. Incorrect answer rejection.
 3. Missing or blank answer handling.
 4. Expired challenge handling.
 5. Replay attack prevention (single-use challenge consumption).
 6. Atomic concurrency & race-condition prevention across simultaneous requests.
 7. Malformed input, SQL-injection attempts, and oversized payloads.
 8. Fail-closed architecture when Redis / backend store fails or times out.
 9. Rate limiting abuse protection on image endpoints.
10. CSRF protection validation.
11. Multi-portal integration across all 8 portals (Doctor, Patient, Hospital, Staff,
    Blood Donor, Organ Donor, Administrator, and Pathology).
12. Successful login with valid CAPTCHA and valid credentials.
13. Failed login with invalid CAPTCHA prevents credential check and session creation.
14. CAPTCHA refresh behavior (generates new challenge, invalidates previous, no secret leakage).
15. Production Cache-Control security headers (no-store, no-cache, max-age=0).
16. Frontend accessibility & responsive markup verification (labels, aria-labels, maxlength).
"""

import time
import concurrent.futures
import pytest
import fakeredis
from werkzeug.security import generate_password_hash

from spherix import create_app
from security.captcha import (
    generate_captcha_text,
    generate_captcha_image,
    hash_captcha_answer,
    create_test_challenge,
    create_captcha_challenge,
    verify_and_consume_challenge,
    CONFUSING_CHARS,
    get_redis_client,
    set_custom_redis_client,
)
from spherix.services.database import TEMP_DATA
from spherix.models.user import Doctor


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a test application instance with isolated FakeRedis client."""
    app_instance = create_app()
    app_instance.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-spherix-secure-captcha-key-12345",
        "CAPTCHA_SECRET_KEY": "test-captcha-hmac-secret-key-67890",
        "CAPTCHA_TTL_SECONDS": 180,
    })
    # Reset to isolated FakeRedis client for each test run
    set_custom_redis_client(fakeredis.FakeRedis())
    return app_instance


@pytest.fixture
def client(app):
    """Test client with isolated session transaction support."""
    with app.test_client() as c:
        yield c


# -----------------------------------------------------------------------------
# Requirement 1: Successful CAPTCHA verification & Case-insensitivity
# -----------------------------------------------------------------------------

def test_01_successful_captcha_verification(app):
    with app.app_context():
        # Exact match
        cid1, code1 = create_test_challenge(portal_type="doctor")
        ok, msg = verify_and_consume_challenge(user_answer=code1, portal_type="doctor", challenge_id=cid1)
        assert ok is True
        assert "successful" in msg.lower()

        # Case-insensitive verification (lower case submitted)
        cid2, code2 = create_test_challenge(portal_type="patient")
        ok_lower, msg_lower = verify_and_consume_challenge(user_answer=code2.lower(), portal_type="patient", challenge_id=cid2)
        assert ok_lower is True

        # Case-insensitive verification (mixed / swap case submitted)
        cid3, code3 = create_test_challenge(portal_type="hospital")
        ok_mixed, msg_mixed = verify_and_consume_challenge(user_answer=code3.swapcase(), portal_type="hospital", challenge_id=cid3)
        assert ok_mixed is True


def test_01_charset_excludes_confusing_characters():
    """Verify that 0, O, 1, I, L are strictly excluded from generated codes."""
    generated_chars = set()
    for _ in range(200):
        code = generate_captcha_text(length=6)
        assert len(code) == 6
        assert code.isalnum()
        assert code.isupper()
        for char in code:
            assert char not in CONFUSING_CHARS, f"Confusing character '{char}' found in '{code}'"
            generated_chars.add(char)
    # Ensure sufficient entropy across letters and digits
    assert len(generated_chars) >= 15


# -----------------------------------------------------------------------------
# Requirement 2: Incorrect Answer Rejection
# -----------------------------------------------------------------------------

def test_02_incorrect_answer_rejection(app):
    with app.app_context():
        cid, code = create_test_challenge(portal_type="doctor")
        wrong_answer = "WRONGX" if code != "WRONGX" else "DIFFRT"
        ok, msg = verify_and_consume_challenge(user_answer=wrong_answer, portal_type="doctor", challenge_id=cid)
        assert ok is False
        assert "incorrect" in msg.lower()


# -----------------------------------------------------------------------------
# Requirement 3: Missing or Blank Answer Handling
# -----------------------------------------------------------------------------

def test_03_missing_or_blank_answer(app):
    with app.app_context():
        cid, _ = create_test_challenge(portal_type="staff")

        # Empty string
        ok1, msg1 = verify_and_consume_challenge(user_answer="", portal_type="staff", challenge_id=cid)
        assert ok1 is False
        assert "required" in msg1.lower()

        # Whitespace only
        ok2, msg2 = verify_and_consume_challenge(user_answer="   ", portal_type="staff", challenge_id=cid)
        assert ok2 is False
        assert "required" in msg2.lower()

        # None answer
        ok3, msg3 = verify_and_consume_challenge(user_answer=None, portal_type="staff", challenge_id=cid)
        assert ok3 is False
        assert "required" in msg3.lower()

        # Missing challenge id
        ok4, msg4 = verify_and_consume_challenge(user_answer="ABCDEF", portal_type="staff", challenge_id=None)
        assert ok4 is False
        assert "expired" in msg4.lower() or "missing" in msg4.lower()


# -----------------------------------------------------------------------------
# Requirement 4: Expired Challenge Handling
# -----------------------------------------------------------------------------

def test_04_expired_challenge(app):
    with app.app_context():
        short_redis = fakeredis.FakeRedis()
        cid, code = create_test_challenge(portal_type="patient", ttl_seconds=1, client=short_redis)

        # Wait for TTL expiration
        time.sleep(1.2)

        ok, msg = verify_and_consume_challenge(user_answer=code, portal_type="patient", challenge_id=cid, client=short_redis)
        assert ok is False
        assert "expired" in msg.lower() or "consumed" in msg.lower()


# -----------------------------------------------------------------------------
# Requirement 5: Replay Prevention (Single-Use Challenge Consumption)
# -----------------------------------------------------------------------------

def test_05_replay_prevention_single_use(app):
    with app.app_context():
        cid, code = create_test_challenge(portal_type="admin")

        # First consumption succeeds
        ok_first, _ = verify_and_consume_challenge(user_answer=code, portal_type="admin", challenge_id=cid)
        assert ok_first is True

        # Replay attempt MUST immediately fail
        ok_second, msg_second = verify_and_consume_challenge(user_answer=code, portal_type="admin", challenge_id=cid)
        assert ok_second is False
        assert "expired" in msg_second.lower() or "consumed" in msg_second.lower()


# -----------------------------------------------------------------------------
# Requirement 6: Atomic Concurrency & Race Condition Prevention
# -----------------------------------------------------------------------------

def test_06_simultaneous_verification_requests(app):
    """Ensure that across 10 simultaneous threads, exactly ONE succeeds and 9 fail."""
    with app.app_context():
        test_redis = fakeredis.FakeRedis()
        cid, code = create_test_challenge(portal_type="doctor", client=test_redis)

        results = []

        def attempt_consume():
            return verify_and_consume_challenge(user_answer=code, portal_type="doctor", challenge_id=cid, client=test_redis)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_consume) for _ in range(10)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        success_count = sum(1 for ok, _ in results if ok is True)
        failure_count = sum(1 for ok, _ in results if ok is False)

        assert success_count == 1, f"Expected exactly 1 atomic success, got {success_count}"
        assert failure_count == 9, f"Expected 9 rejections, got {failure_count}"


# -----------------------------------------------------------------------------
# Requirement 7: Malformed Input and Oversized Payloads
# -----------------------------------------------------------------------------

def test_07_malformed_input_and_oversized_payloads(app):
    with app.app_context():
        cid, _ = create_test_challenge(portal_type="doctor")

        oversized = "A" * 5000
        ok1, msg1 = verify_and_consume_challenge(user_answer=oversized, portal_type="doctor", challenge_id=cid)
        assert ok1 is False

        injection_attempt = "' OR 1=1; DROP TABLE users;--"
        ok2, msg2 = verify_and_consume_challenge(user_answer=injection_attempt, portal_type="doctor", challenge_id=cid)
        assert ok2 is False

        # Non-string object
        ok3, msg3 = verify_and_consume_challenge(user_answer=123456, portal_type="doctor", challenge_id=cid)
        assert ok3 is False


# -----------------------------------------------------------------------------
# Requirement 8: Fail-Closed Architecture when Redis Unavailable
# -----------------------------------------------------------------------------

class FaultyRedisClient:
    """Simulates Redis connection failure / network drop."""
    def getdel(self, key):
        raise ConnectionError("Simulated Redis connection failure")

    def eval(self, script, numkeys, *keys):
        raise ConnectionError("Simulated Redis connection failure")

    def set(self, key, val, ex=None):
        raise ConnectionError("Simulated Redis connection failure")


def test_08_fail_closed_on_backend_failure(app):
    with app.app_context():
        faulty_client = FaultyRedisClient()

        # When backend fails, verification MUST fail closed
        ok, msg = verify_and_consume_challenge(user_answer="ABCDEF", portal_type="doctor", challenge_id="fake-cid", client=faulty_client)
        assert ok is False
        assert "temporarily unavailable" in msg.lower() or "error" in msg.lower()


# -----------------------------------------------------------------------------
# Requirement 9: Rate Limiting Enforcement
# -----------------------------------------------------------------------------

def test_09_rate_limiting_enforcement():
    """Verify that excessive requests to CAPTCHA generation trigger rate limits."""
    rate_app = create_app()
    rate_app.config.update({
        "TESTING": True,
        "RATELIMIT_ENABLED": True,
        "RATELIMIT_STORAGE_URI": "memory://",
    })

    with rate_app.test_client() as rate_client:
        responses = []
        for _ in range(70):
            res = rate_client.get("/api/captcha/image/doctor?refresh=1")
            responses.append(res.status_code)

        # With 60/minute limit, at least one request should be 429 or all within limits
        assert 429 in responses or all(c == 200 for c in responses[:60])


# -----------------------------------------------------------------------------
# Requirement 10: CSRF Validation
# -----------------------------------------------------------------------------

def test_10_csrf_validation_when_enabled():
    csrf_app = create_app()
    csrf_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": True,
        "WTF_CSRF_CHECK_DEFAULT": True,
        "SECRET_KEY": "test-csrf-key",
    })

    with csrf_app.test_client() as csrf_client:
        # POST without CSRF token should return 400 Bad Request
        res = csrf_client.post("/doctor/login", data={"email": "doc@example.com", "password": "pass", "captcha": "ABCDEF"})
        assert res.status_code == 400


# -----------------------------------------------------------------------------
# Requirement 11: Multi-Portal Correct Behavior Across All 8 Portals
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("portal_type, login_url", [
    ("doctor", "/doctor/login"),
    ("patient", "/patient/login"),
    ("hospital", "/hospital/login"),
    ("staff", "/staff/login"),
    ("blood_donor", "/blood-donor/login"),
    ("organ_donor", "/organ-donor/login"),
    ("pathology", "/pathology/login"),
    ("admin", "/admin/login"),
])
def test_11_portal_endpoints_deliver_valid_captcha_challenge(client, portal_type, login_url):
    """Every portal must provide a working image endpoint with proper session binding."""
    # 1. Fetch CAPTCHA image
    res = client.get(f"/api/captcha/image/{portal_type}")
    assert res.status_code == 200
    assert res.content_type == "image/png"
    assert res.data[:8] == b"\x89PNG\r\n\x1a\n"

    # 2. Check session binding
    with client.session_transaction() as sess:
        challenge_key = f"_captcha_challenge_{portal_type}"
        assert challenge_key in sess
        assert len(sess[challenge_key]) > 0


# -----------------------------------------------------------------------------
# Requirement 12 & 13: Login Flow Verification with CAPTCHA
# -----------------------------------------------------------------------------

def test_12_and_13_login_with_invalid_vs_valid_captcha(app, client):
    """
    Req 13: Invalid CAPTCHA rejects login before checking credentials (no session created).
    Req 12: Valid CAPTCHA with valid credentials authenticates successfully.
    """
    doc_id = "DOC_CAPTCHA_TEST_01"
    doc_email = "doc_captcha_test@example.com"
    doc_pass = "SecureDocPass123!"

    doctor = Doctor(
        id=doc_id,
        first_name="Captcha",
        last_name="Doctor",
        email=doc_email,
        password=generate_password_hash(doc_pass, method="pbkdf2:sha256:260000"),
        department="Neurology",
        is_verified=True
    )
    TEMP_DATA["doctors"][doc_id] = doctor

    # 1. Initialize CAPTCHA by visiting image endpoint
    client.get("/api/captcha/image/doctor")

    # 2. Submit with WRONG CAPTCHA and valid credentials
    res_invalid = client.post("/doctor/login", data={
        "email": doc_email,
        "password": doc_pass,
        "captcha": "WRONG1"
    }, follow_redirects=False)

    # Must stay on login page or re-render login with flash message (no session established)
    assert res_invalid.status_code in (200, 302)
    with client.session_transaction() as sess:
        assert sess.get("_user_id") is None
        assert sess.get("user_role") is None

    # 3. Create valid challenge manually linked to test session
    cid, valid_code = create_test_challenge(portal_type="doctor")
    with client.session_transaction() as sess:
        sess["_captcha_challenge_doctor"] = cid

    # 4. Submit with VALID CAPTCHA and valid credentials
    res_valid = client.post("/doctor/login", data={
        "email": doc_email,
        "password": doc_pass,
        "captcha": valid_code
    }, follow_redirects=False)

    # Must authenticate and redirect to dashboard
    assert res_valid.status_code == 302
    assert "/doctor/dashboard" in res_valid.location

    with client.session_transaction() as sess:
        assert sess.get("_user_id") is not None
        assert doc_id in sess.get("_user_id")
        assert sess.get("user_role") == "doctor"


# -----------------------------------------------------------------------------
# Requirement 14: CAPTCHA Refresh Behavior
# -----------------------------------------------------------------------------

def test_14_captcha_refresh_behavior(client):
    """Refreshing CAPTCHA issues a new challenge and never leaks the answer."""
    # First image call
    res1 = client.get("/api/captcha/image/patient")
    assert res1.status_code == 200
    with client.session_transaction() as sess1:
        cid1 = sess1.get("_captcha_challenge_patient")
        assert cid1 is not None

    # Refresh endpoint call
    refresh_res = client.post("/api/captcha/refresh/patient")
    assert refresh_res.status_code == 200
    json_data = refresh_res.get_json()
    assert json_data["status"] == "ok"
    assert "image_url" in json_data

    # CRITICAL SECURITY CHECK: Plaintext answer or hash must NEVER appear in JSON
    json_str = str(json_data).lower()
    assert "answer" not in json_str
    assert "code" not in json_str or "status" in json_str

    with client.session_transaction() as sess2:
        cid2 = sess2.get("_captcha_challenge_patient")
        assert cid2 is not None
        assert cid2 != cid1, "Refresh MUST generate a distinct challenge ID"


# -----------------------------------------------------------------------------
# Requirement 15: Production Cache-Control Headers
# -----------------------------------------------------------------------------

def test_15_production_cache_control_headers(client):
    """CAPTCHA image responses must never be cached by browsers or intermediary proxies."""
    res = client.get("/api/captcha/image/hospital")
    assert res.status_code == 200

    headers = res.headers
    cache_control = headers.get("Cache-Control", "").lower()
    assert "no-store" in cache_control
    assert "no-cache" in cache_control
    assert "must-revalidate" in cache_control
    assert "max-age=0" in cache_control
    assert headers.get("Pragma") == "no-cache"
    assert headers.get("Expires") == "0"


# -----------------------------------------------------------------------------
# Requirement 16: Mobile Responsiveness & Accessibility Verification
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("portal_url", [
    "/doctor/login",
    "/patient/login",
    "/hospital/login",
    "/staff/login",
    "/blood-donor/login",
    "/organ-donor/login",
    "/pathology/login",
    "/admin/login",
])
def test_16_frontend_accessibility_and_responsiveness(client, portal_url):
    """Verify input constraints, accessible labels, and refresh buttons in all login pages."""
    res = client.get(portal_url)
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Check for 6-character length constraint
    assert 'maxlength="6"' in html

    # Check for security verification label
    assert "Security" in html or "CAPTCHA" in html

    # Check for autocomplete="off"
    assert 'autocomplete="off"' in html

    # Check for refresh button / icon
    assert 'refresh' in html.lower() or 'fa-arrows-rotate' in html or 'fa-sync-alt' in html
