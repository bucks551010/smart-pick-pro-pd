"""utils/jwt_utils.py — JWT access-token utilities for Smart Pick Pro.

Issues short-lived (60-minute) signed JSON Web Tokens for FastAPI route
protection.  The long-lived "refresh" session is the opaque DB token managed
by auth_gate.py.  The JWT lives only in the browser's JS memory — it is never
written to localStorage, sessionStorage, or a cookie.

Production requirement
----------------------
Set ``JWT_SECRET`` in your Railway environment variables to a long, random
string (e.g. ``openssl rand -hex 48``).  If the variable is absent, an
ephemeral secret is generated on startup — tokens will invalidate on every
server restart (acceptable in dev, NOT in production).

PyJWT vs. built-in fallback
----------------------------
PyJWT is the preferred backend.  If it is not installed, a pure-stdlib
HMAC-SHA256 implementation is used.  Both produce RFC 7519 compliant tokens.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from utils.logger import get_logger

_logger = get_logger(__name__)

# ── Secret key ─────────────────────────────────────────────────
_SECRET = os.environ.get("JWT_SECRET", "").strip()
if not _SECRET:
    _SECRET = secrets.token_urlsafe(48)
    _logger.warning(
        "JWT_SECRET env var not set — using ephemeral secret. "
        "Set JWT_SECRET in Railway environment variables."
    )

_ALG          = "HS256"
_ACCESS_TTL_S = 3600          # 60 minutes
_ISSUER       = "smartpickpro"
_AUDIENCE     = "spp-api"

# ── PyJWT detection ────────────────────────────────────────────
try:
    import jwt as _pyjwt
    _HAS_PYJWT = True
except ImportError:
    _pyjwt = None          # type: ignore
    _HAS_PYJWT = False
    _logger.info("PyJWT not installed — using built-in HMAC-SHA256 JWT fallback.")


# ── Low-level helpers ──────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data)


def _sign(payload: str, secret: str) -> str:
    return _b64url_encode(
        hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    )


# ── Public API ─────────────────────────────────────────────────

def issue_access_token(user_id: int, email: str, is_admin: bool) -> str:
    """Issue a signed JWT access token.

    The payload includes:

    - ``sub``   — ``str(user_id)``
    - ``email`` — user email address
    - ``admin`` — admin flag (bool)
    - ``iat``   — issued-at (epoch seconds)
    - ``exp``   — expiry (iat + 60 min)
    - ``jti``   — unique token ID (enables one-shot revocation if needed)
    - ``iss`` / ``aud`` — issuer / audience for strict validation

    Returns a compact JWT string.
    """
    now = int(time.time())
    payload = {
        "sub":   str(user_id),
        "email": email,
        "admin": bool(is_admin),
        "iat":   now,
        "exp":   now + _ACCESS_TTL_S,
        "jti":   secrets.token_urlsafe(12),
        "iss":   _ISSUER,
        "aud":   _AUDIENCE,
    }

    if _HAS_PYJWT:
        try:
            return _pyjwt.encode(payload, _SECRET, algorithm=_ALG)
        except Exception as exc:
            _logger.error("PyJWT encode failed: %s — using fallback", exc)

    # ── Manual HMAC-SHA256 fallback ────────────────────────────
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body   = _b64url_encode(json.dumps(payload).encode())
    sig    = _sign(f"{header}.{body}", _SECRET)
    return f"{header}.{body}.{sig}"


def verify_access_token(token: str) -> dict | None:
    """Verify a JWT and return the decoded payload dict, or None on failure.

    Checks:
    - HMAC signature
    - Expiry (``exp``)
    - Issuer (``iss``)
    - Audience (``aud``)

    Returns ``None`` for any validation failure (expired, tampered, malformed).
    """
    if not token or len(token) > 4096:
        return None

    if _HAS_PYJWT:
        try:
            return _pyjwt.decode(
                token,
                _SECRET,
                algorithms=[_ALG],
                issuer=_ISSUER,
                audience=_AUDIENCE,
            )
        except _pyjwt.ExpiredSignatureError:
            return None
        except Exception:
            return None

    # ── Manual fallback ────────────────────────────────────────
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected = _sign(f"{header}.{body}", _SECRET)
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        if payload.get("iss") != _ISSUER:
            return None
        if payload.get("aud") != _AUDIENCE:
            return None
        return payload
    except Exception:
        return None


def access_ttl_seconds() -> int:
    """Return the configured access token TTL in seconds (60 min)."""
    return _ACCESS_TTL_S
