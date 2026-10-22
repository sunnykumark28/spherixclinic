"""
Spherix Secure CAPTCHA Module
Production-conscious, high-security visual CAPTCHA engine for Spherix Clinic.
Integrates Pillow for anti-bot visual distortion and Redis for single-use,
expiring challenge verification.
"""

import os
import io
import math
import hmac
import random
import secrets
import hashlib
import logging
from typing import Optional, Tuple, Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger('spherix.security.captcha')

# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================

# Unambiguous 32-character alphabet (Strictly excludes 0, O, 1, I, and L)
CAPTCHA_CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CONFUSING_CHARS = set("0O1IL")
CAPTCHA_LENGTH = 6
DEFAULT_TTL_SECONDS = 180  # 3 minutes challenge lifetime

# Atomic challenge retrieval & deletion Lua script (Replay / concurrency attack prevention)
LUA_ATOMIC_CONSUME = """
local key = KEYS[1]
local val = redis.call('GET', key)
if val then
    redis.call('DEL', key)
end
return val
"""

def atomic_get_and_delete(client: Any, key: str) -> Optional[Any]:
    """
    Atomically retrieves and deletes a key from Redis / storage to prevent replay attacks.
    Prioritizes native Redis 6.2+ GETDEL, falling back to Lua script and pipeline.
    Propagates network / operational errors to allow fail-closed handling.
    """
    if client is None:
        return None

    last_error = None

    # 1. Native Redis 6.2+ / fakeredis GETDEL (O(1) single-roundtrip atomic operation)
    if hasattr(client, 'getdel'):
        try:
            return client.getdel(key)
        except Exception as e:
            if "unknown command" in str(e).lower():
                last_error = e
            else:
                raise e

    # 2. Lua Script atomic consumption
    if hasattr(client, 'eval'):
        try:
            return client.eval(LUA_ATOMIC_CONSUME, 1, key)
        except Exception as e:
            if "unknown command" in str(e).lower():
                last_error = e
            else:
                raise e

    # 3. MULTI / EXEC transaction pipeline fallback
    if hasattr(client, 'pipeline'):
        try:
            pipe = client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            res = pipe.execute()
            return res[0] if res else None
        except Exception as e:
            raise e

    if last_error is not None:
        raise last_error

    return None

_redis_client_instance = None
_redis_init_attempted = False


def get_captcha_secret() -> str:
    """Retrieves HMAC secret for hashing CAPTCHA answers."""
    secret = os.getenv('CAPTCHA_SECRET_KEY') or os.getenv('SECRET_KEY') or os.getenv('FLASK_SECRET')
    if not secret:
        secret = 'spherix-secure-captcha-default-secret-key-2026'
    return secret


def get_captcha_ttl() -> int:
    """Retrieves expiration window in seconds."""
    try:
        return int(os.getenv('CAPTCHA_TTL_SECONDS', DEFAULT_TTL_SECONDS))
    except (ValueError, TypeError):
        return DEFAULT_TTL_SECONDS


# ==============================================================================
# REDIS STORAGE & CONNECTION ENGINE
# ==============================================================================

def get_redis_client():
    """
    Returns configured Redis client with connection pooling and timeouts.
    Supports real Redis in production and isolated FakeRedis/memory during test mode.
    """
    global _redis_client_instance, _redis_init_attempted

    if _redis_client_instance is not None:
        return _redis_client_instance

    is_testing = os.getenv('FLASK_ENV') == 'testing' or os.getenv('TESTING', 'False').lower() == 'true'
    store_mode = os.getenv('SPHERIX_CAPTCHA_STORE', '').lower()

    # Isolated memory store for testing
    if is_testing or store_mode == 'memory':
        try:
            import fakeredis
            _redis_client_instance = fakeredis.FakeRedis()
            _redis_init_attempted = True
            logger.info("Spherix CAPTCHA initialized with FakeRedis in-memory store.")
            return _redis_client_instance
        except ImportError:
            pass

    redis_url = os.getenv('REDIS_URL')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD', None)

    try:
        import redis
        if redis_url:
            pool = redis.ConnectionPool.from_url(
                redis_url,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                decode_responses=False
            )
        else:
            pool = redis.ConnectionPool(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                decode_responses=False
            )
        client = redis.Redis(connection_pool=pool)
        # Test connection ping
        client.ping()
        _redis_client_instance = client
        _redis_init_attempted = True
        logger.info("Spherix CAPTCHA successfully connected to Redis server.")
        return _redis_client_instance
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
        # In non-production environments, gracefully fall back to in-memory FakeRedis
        # to ensure zero socket connection delays and instantaneous local development reloads
        is_production = os.getenv('FLASK_ENV') == 'production' or os.getenv('ENV') == 'production'
        if not is_production or is_testing or store_mode in ('test', 'fakeredis', 'memory'):
            try:
                import fakeredis
                _redis_client_instance = fakeredis.FakeRedis()
                _redis_init_attempted = True
                logger.info("Local development: initialized in-memory FakeRedis store.")
                return _redis_client_instance
            except Exception:
                pass
        return None


def set_custom_redis_client(client):
    """Allows test fixtures to inject an isolated test Redis client."""
    global _redis_client_instance
    _redis_client_instance = client


# ==============================================================================
# CHALLENGE GENERATION & DIGEST
# ==============================================================================

def generate_captcha_text(length: int = CAPTCHA_LENGTH) -> str:
    """Generates a cryptographically random, unambiguous 6-character code."""
    return "".join(secrets.choice(CAPTCHA_CHARSET) for _ in range(length))


def compute_captcha_digest(text: str, secret: Optional[str] = None) -> str:
    """Computes a keyed HMAC-SHA256 digest of normalized CAPTCHA answer."""
    if not text:
        return ""
    key = (secret or get_captcha_secret()).encode('utf-8')
    normalized = text.strip().upper().encode('utf-8')
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()


# ==============================================================================
# IMAGE RENDERING WITH PILLOW (High-Contrast Medical Security Aesthetic)
# ==============================================================================

def get_bundled_font(size: int = 28) -> ImageFont.FreeTypeFont:
    """Resolves properly bundled licensed font DejaVuSans-Bold with fallbacks."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, 'static', 'fonts', 'DejaVuSans-Bold.ttf'),
        os.path.join(os.getcwd(), 'static', 'fonts', 'DejaVuSans-Bold.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/Library/Fonts/Arial.ttf',
        'DejaVuSans-Bold.ttf'
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_captcha_image_bytes(text: str) -> bytes:
    """
    Renders the 6-character code into a crisp PNG image on a clean light background
    with character rotation, variable spacing, vertical jitter, security grid,
    crossing sine wave interference, and noise speckles.
    """
    width, height = 210, 52
    
    # 1. Clean crisp light medical background for maximum readability (slate-50)
    bg_color = (248, 250, 252)
    img = Image.new('RGBA', (width, height), (*bg_color, 255))
    draw = ImageDraw.Draw(img)

    # 2. Subtle security background grid lines (slate-200)
    for x in range(12, width, 22):
        draw.line([(x, 0), (x, height)], fill=(226, 232, 240, 160), width=1)
    for y in range(8, height, 16):
        draw.line([(0, y), (width, y)], fill=(226, 232, 240, 160), width=1)

    # 3. High-contrast typography palette: deep charcoal, slate-900 & clinical navy
    char_palette = [
        (15, 23, 42),   # slate-900
        (30, 41, 59),   # slate-800
        (12, 35, 64),   # deep navy
        (2, 132, 199),  # sky-600
        (3, 105, 161),  # sky-700
        (51, 65, 85),   # slate-700
    ]

    font = get_bundled_font(size=27)

    # 4. Render each character with rotation & jitter
    text_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    total_chars = len(text)
    slot_width = (width - 24) / max(total_chars, 1)

    for i, char in enumerate(text):
        char_box_size = 46
        char_img = Image.new('RGBA', (char_box_size, char_box_size), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_color = (*random.choice(char_palette), 255)

        try:
            bbox = char_draw.textbbox((0, 0), char, font=font)
            cw, ch = bbox[2] - bbox[0], bbox[3] - bbox[1]
            cx = (char_box_size - cw) // 2
            cy = (char_box_size - ch) // 2
        except Exception:
            cx, cy = 8, 8

        # Subtle outline shadow for anti-segmentation
        char_draw.text((cx + 1, cy + 1), char, font=font, fill=(203, 213, 225, 200))
        char_draw.text((cx, cy), char, font=font, fill=char_color)

        # Distort angle (-20° to +20°)
        angle = random.randint(-20, 20)
        rotated = char_img.rotate(angle, expand=False, resample=Image.BILINEAR)

        pos_x = int(10 + i * slot_width + random.randint(-2, 2))
        pos_y = int(3 + random.randint(-2, 3))
        text_layer.paste(rotated, (pos_x, pos_y), rotated)

    img = Image.alpha_composite(img, text_layer)
    draw = ImageDraw.Draw(img)

    # 5. Crossing sine wave interference lines
    for _ in range(2):
        points = []
        phase = random.uniform(0, 2 * math.pi)
        freq = random.uniform(0.025, 0.045)
        amp = random.randint(5, 9)
        base_y = random.randint(16, height - 16)
        for x in range(0, width, 2):
            y = int(base_y + amp * math.sin(freq * x + phase))
            points.append((x, max(2, min(height - 2, y))))
        curve_color = (100, 116, 139, random.randint(140, 190))
        draw.line(points, fill=curve_color, width=2)

    # 6. Anti-bot noise speckles
    for _ in range(45):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(148, 163, 184, 180))

    final_img = img.convert('RGB')
    buf = io.BytesIO()
    final_img.save(buf, format='PNG')
    return buf.getvalue()


# ==============================================================================
# LIFECYCLE: CREATION & ATOMIC VERIFICATION
# ==============================================================================

def create_captcha_challenge(portal_type: str = "default", session_obj: Optional[Any] = None) -> Tuple[str, bytes]:
    """
    Creates a new CAPTCHA challenge:
    1. Generates 6-character code and challenge ID.
    2. Stores HMAC digest in Redis with 3-minute TTL.
    3. Binds challenge ID to user's session if session_obj is provided.
    4. Renders PNG image. Plaintext answer is NEVER stored or exposed.
    """
    code = generate_captcha_text(CAPTCHA_LENGTH)
    challenge_id = secrets.token_urlsafe(32)
    digest = compute_captcha_digest(code)
    ttl = get_captcha_ttl()

    client = get_redis_client()
    if client is not None:
        try:
            key = f"spherix:captcha:{challenge_id}"
            client.set(key, digest, ex=ttl)
        except Exception as e:
            logger.error(f"Failed to store CAPTCHA challenge in Redis: {e}")

    # Bind challenge ID to session if session_obj available
    if session_obj is not None:
        session_key = f"_captcha_challenge_{portal_type}"
        session_obj[session_key] = challenge_id

    image_bytes = generate_captcha_image_bytes(code)
    return challenge_id, image_bytes


def create_test_challenge(
    portal_type: str = "default",
    code: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
    client: Optional[Any] = None
) -> Tuple[str, str]:
    """
    Helper for automated tests to create a challenge and return (challenge_id, raw_code).
    Plaintext code is only returned to the test suite and never stored in Redis.
    """
    raw_code = code or generate_captcha_text(CAPTCHA_LENGTH)
    challenge_id = secrets.token_urlsafe(32)
    digest = compute_captcha_digest(raw_code)
    ttl = ttl_seconds if ttl_seconds is not None else get_captcha_ttl()

    redis_cli = client or get_redis_client()
    if redis_cli is not None:
        key = f"spherix:captcha:{challenge_id}"
        redis_cli.set(key, digest, ex=ttl)

    return challenge_id, raw_code


def verify_and_consume_challenge(
    user_answer: Any,
    portal_type: str = "default",
    challenge_id: Optional[str] = None,
    session_obj: Optional[Any] = None,
    client: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Atomically verifies and consumes a CAPTCHA challenge:
    1. Checks for missing or malformed input.
    2. Retrieves & atomically deletes challenge digest from Redis (Single-use).
    3. Performs constant-time comparison against computed HMAC digest.
    4. Fails closed if Redis is unavailable.
    """
    if user_answer is None or not isinstance(user_answer, str) or not user_answer.strip():
        return False, "Security verification code is required."

    cleaned_answer = user_answer.strip().upper()
    if len(cleaned_answer) < 4 or len(cleaned_answer) > 10:
        return False, "Invalid security verification code length."

    # Resolve challenge ID from argument or session
    target_id = challenge_id
    session_key = f"_captcha_challenge_{portal_type}"
    if not target_id and session_obj is not None:
        target_id = session_obj.get(session_key)

    if not target_id:
        return False, "Security verification challenge expired or missing. Please refresh the page."

    redis_cli = client if client is not None else get_redis_client()
    if redis_cli is None:
        # Fail closed: never allow login if verification store is down
        logger.critical("Security verification failed closed: Redis is unavailable.")
        return False, "Security verification service temporarily unavailable. Please try again."

    redis_key = f"spherix:captcha:{target_id}"

    try:
        # Atomic single-use consumption: get and delete in one operation
        raw_digest = atomic_get_and_delete(redis_cli, redis_key)
        
        # Clean up session challenge pointer immediately
        if session_obj is not None:
            session_obj.pop(session_key, None)

        if not raw_digest:
            return False, "Security verification challenge expired or already consumed. Please try again."

        if isinstance(raw_digest, bytes):
            stored_digest = raw_digest.decode('utf-8')
        else:
            stored_digest = str(raw_digest)

        # Constant-time comparison
        computed_digest = compute_captcha_digest(cleaned_answer)
        is_match = hmac.compare_digest(stored_digest, computed_digest)

        if not is_match:
            return False, "Incorrect security verification code. Please try again."

        return True, "Security verification successful."

    except Exception as e:
        logger.error(f"Error during CAPTCHA challenge consumption: {e}")
        # Fail closed
        return False, "Security verification service encountered an error. Please try again."


# Aliases for compatibility
generate_captcha_image = generate_captcha_image_bytes
hash_captcha_answer = compute_captcha_digest
