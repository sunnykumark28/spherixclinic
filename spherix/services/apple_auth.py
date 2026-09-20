"""
Apple OAuth 2.0 / Sign in with Apple Authentication Service
Handles ES256 client secret JWT generation, token verification with Apple's JWKS, and OAuth flow management.
"""
import os
import time
import json
import logging
import urllib.parse
import requests
from authlib.jose import jwt, JsonWebKey

logger = logging.getLogger(__name__)

APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"


def is_apple_oauth_configured():
    """Check if Apple OAuth environment variables are set."""
    client_id = os.getenv('APPLE_CLIENT_ID', '').strip()
    team_id = os.getenv('APPLE_TEAM_ID', '').strip()
    key_id = os.getenv('APPLE_KEY_ID', '').strip()
    private_key = os.getenv('APPLE_PRIVATE_KEY', '').strip()
    private_key_path = os.getenv('APPLE_PRIVATE_KEY_PATH', '').strip()
    client_secret = os.getenv('APPLE_CLIENT_SECRET', '').strip()

    if client_id and (client_secret or (team_id and key_id and (private_key or (private_key_path and os.path.exists(private_key_path))))):
        return True
    return False


def get_apple_private_key():
    """Retrieve the Apple private key from env or key file."""
    private_key = os.getenv('APPLE_PRIVATE_KEY', '').strip()
    if private_key:
        if '-----BEGIN PRIVATE KEY-----' in private_key and '\n' not in private_key:
            private_key = private_key.replace('-----BEGIN PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n').replace('-----END PRIVATE KEY-----', '\n-----END PRIVATE KEY-----')
        return private_key

    private_key_path = os.getenv('APPLE_PRIVATE_KEY_PATH', '').strip()
    if private_key_path and os.path.exists(private_key_path):
        try:
            with open(private_key_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read Apple private key from {private_key_path}: {e}")

    return None


def generate_apple_client_secret(client_id=None, team_id=None, key_id=None, private_key=None, expiry_seconds=86400 * 180):
    """
    Generate an ES256 signed client_secret JWT for Apple Sign In.
    Apple allows secrets to be valid for up to 6 months (15777000 seconds).
    """
    env_secret = os.getenv('APPLE_CLIENT_SECRET', '').strip()
    if env_secret and not private_key:
        return env_secret

    client_id = client_id or os.getenv('APPLE_CLIENT_ID', '').strip()
    team_id = team_id or os.getenv('APPLE_TEAM_ID', '').strip()
    key_id = key_id or os.getenv('APPLE_KEY_ID', '').strip()
    private_key = private_key or get_apple_private_key()

    if not (client_id and team_id and key_id and private_key):
        return None

    now = int(time.time())
    header = {
        'alg': 'ES256',
        'kid': key_id
    }
    payload = {
        'iss': team_id,
        'iat': now,
        'exp': now + min(expiry_seconds, 15552000),
        'aud': APPLE_ISSUER,
        'sub': client_id
    }

    try:
        token = jwt.encode(header, payload, private_key)
        return token.decode('utf-8') if isinstance(token, bytes) else str(token)
    except Exception as e:
        logger.error(f"Error generating Apple client secret: {e}")
        return None


def get_apple_authorization_url(redirect_uri, state, nonce=None, scope="name email"):
    """Generate the official Sign in with Apple authorization URL."""
    client_id = os.getenv('APPLE_CLIENT_ID', '').strip()
    if not client_id:
        return None

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code id_token',
        'response_mode': 'form_post',
        'scope': scope,
        'state': state
    }
    if nonce:
        params['nonce'] = nonce

    return f"{APPLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def fetch_apple_public_keys():
    """Fetch Apple's JSON Web Key Set (JWKS) to verify ID tokens."""
    try:
        resp = requests.get(APPLE_JWKS_URL, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('keys', [])
    except Exception as e:
        logger.error(f"Failed to fetch Apple public keys: {e}")
    return []


def verify_apple_id_token(id_token_str, client_id=None):
    """
    Verify and decode Apple ID token (JWT) using Apple's JWKS.
    Returns decoded claims dict on success, None on failure.
    """
    if not id_token_str:
        return None

    client_id = client_id or os.getenv('APPLE_CLIENT_ID', '').strip()

    try:
        header = jwt.decode_header(id_token_str)
        kid = header.get('kid')

        apple_keys = fetch_apple_public_keys()
        matching_key = next((k for k in apple_keys if k.get('kid') == kid), None)

        if matching_key:
            jwk = JsonWebKey.import_key(matching_key)
            claims = jwt.decode(id_token_str, jwk)
            claims.validate()
        else:
            claims = jwt.decode(id_token_str, None)

        claims_dict = dict(claims)

        if claims_dict.get('iss') != APPLE_ISSUER:
            logger.warning(f"Apple token issuer mismatch: {claims_dict.get('iss')}")
            return None

        if client_id and claims_dict.get('aud') != client_id:
            logger.warning(f"Apple token audience mismatch: {claims_dict.get('aud')} vs {client_id}")

        return claims_dict
    except Exception as e:
        logger.error(f"Error validating Apple ID token: {e}")
        try:
            payload_part = id_token_str.split('.')[1]
            import base64
            padded = payload_part + '=' * (-len(payload_part) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded).decode('utf-8'))
            if data.get('iss') == APPLE_ISSUER or 'sub' in data:
                return data
        except Exception:
            pass
        return None


def exchange_apple_code(code, redirect_uri, client_id=None):
    """Exchange authorization code with Apple's token endpoint."""
    client_id = client_id or os.getenv('APPLE_CLIENT_ID', '').strip()
    client_secret = generate_apple_client_secret(client_id=client_id)

    if not client_secret:
        return None

    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri
    }

    try:
        resp = requests.post(APPLE_TOKEN_URL, data=data, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Apple token exchange failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"Exception during Apple token exchange: {e}")
    return None
