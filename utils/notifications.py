"""utils/notifications.py — Notification infrastructure for Smart Pick Pro.

Provides four core services:

    1. Secure token management
       - SHA-256 hashed storage (plaintext NEVER written to DB)
       - Email verification tokens (UUID/256-bit, 24-hour TTL)
       - Password reset tokens (UUID/256-bit, 30-minute TTL, one-time use)
       - Automatic invalidation of previous tokens on re-issue

    2. Double opt-in email verification
       - trigger_welcome_flow()  — issue token + send welcome email
       - verify_email_token()    — validate + mark verified
       - is_email_verified()     — status check

    3. Password reset
       - trigger_reset_flow()        — rate-check + issue token + send email
       - verify_reset_token_valid()  — peek without consuming
       - consume_reset_token()       — validate + update password + invalidate

    4. Rate limiting & security audit log
       - check_rate_limit()   — max 3 per rolling hour per key
       - record_rate_event()  — record one event
       - record_audit()       — append to security audit log
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta

from utils.logger import get_logger

_logger = get_logger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
_APP_BASE_URL       = os.environ.get("APP_BASE_URL", "https://smartpickpro.ai")
_VERIFY_TTL_HOURS   = 24
_RESET_TTL_MINUTES  = 30
_RATE_LIMIT_MAX     = 3      # attempts allowed per window
_RATE_LIMIT_WINDOW  = 3600   # seconds (1 hour)

_tables_ensured = False

# ── Table DDL (SQLite / PostgreSQL compatible via _AuthConn translation) ───────
# _AuthConn converts:  ? → %s,  datetime('now') → NOW()
# So these DDL strings work for both engines unchanged.

_SQL_NOTIFICATION_TOKENS = """
CREATE TABLE IF NOT EXISTS notification_tokens (
    token_hash TEXT PRIMARY KEY,
    token_type TEXT NOT NULL,
    user_id    INTEGER NOT NULL,
    email      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at    TEXT,
    ip_address TEXT
)
"""

_SQL_RATE_LIMITS = """
CREATE TABLE IF NOT EXISTS notification_rate_limits (
    rate_key TEXT NOT NULL,
    event_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_SQL_RATE_LIMITS_IDX = (
    "CREATE INDEX IF NOT EXISTS idx_nrl_key_time "
    "ON notification_rate_limits(rate_key, event_at)"
)

_SQL_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS notification_audit_log (
    event_type TEXT NOT NULL,
    email      TEXT,
    ip_address TEXT,
    success    INTEGER DEFAULT 1,
    detail     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def _ensure_notification_tables() -> None:
    """Create notification tables and migrate the users table (idempotent)."""
    global _tables_ensured
    if _tables_ensured:
        return
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            db.execute(_SQL_NOTIFICATION_TOKENS)
            db.execute(_SQL_RATE_LIMITS)
            db.execute(_SQL_RATE_LIMITS_IDX)
            db.execute(_SQL_AUDIT_LOG)
            # Migration: add is_email_verified column to users (idempotent via try/except)
            try:
                db.execute(
                    "ALTER TABLE users ADD COLUMN is_email_verified INTEGER DEFAULT 0"
                )
            except Exception:
                pass  # Column already exists
        _tables_ensured = True
    except Exception as exc:
        _logger.warning("Failed to ensure notification tables: %s", exc)


# ── Low-level token helpers ────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    """SHA-256 hash of the raw token — the only value stored in the database."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires_iso(*, hours: int = 0, minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)).isoformat()


def _parse_dt(raw: object) -> datetime:
    if isinstance(raw, datetime):
        dt = raw
    else:
        dt = datetime.fromisoformat(str(raw))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── Rate limiting ──────────────────────────────────────────────────────────────

def check_rate_limit(
    key: str,
    max_count: int = _RATE_LIMIT_MAX,
    window_seconds: int = _RATE_LIMIT_WINDOW,
) -> bool:
    """Return True if the action is allowed (under limit), False if blocked.

    The key should encode both the action type and the limiting dimension, e.g.:
        "reset:email:user@example.com"
        "reset:ip:1.2.3.4"
        "verify:email:user@example.com"
    """
    _ensure_notification_tables()
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        window_start = (
            datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        ).isoformat()
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM notification_rate_limits "
                "WHERE rate_key = ? AND event_at >= ?",
                (key, window_start),
            )
            count = (row["cnt"] if row else 0) or 0
            return count < max_count
    except Exception as exc:
        _logger.debug("Rate limit check failed: %s", exc)
        return True  # Fail open — do not break the app if table is unavailable


def record_rate_event(key: str) -> None:
    """Record one rate-limit event for the given key."""
    _ensure_notification_tables()
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            db.execute(
                "INSERT INTO notification_rate_limits (rate_key, event_at) VALUES (?, ?)",
                (key, _now_iso()),
            )
    except Exception as exc:
        _logger.debug("Record rate event failed: %s", exc)


# ── Security audit log ────────────────────────────────────────────────────────

def record_audit(
    event_type: str,
    *,
    email: str | None = None,
    ip: str | None = None,
    success: bool = True,
    detail: str | None = None,
) -> None:
    """Append one entry to the security audit log (fire-and-forget)."""
    _ensure_notification_tables()
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            db.execute(
                "INSERT INTO notification_audit_log "
                "(event_type, email, ip_address, success, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (event_type, email, ip, int(success), detail, _now_iso()),
            )
    except Exception as exc:
        _logger.debug("Audit log write failed: %s", exc)


# ── Email verification tokens ─────────────────────────────────────────────────

def issue_verification_token(
    email: str,
    user_id: int,
    *,
    ip: str | None = None,
) -> str | None:
    """Issue a new email-verification token, invalidating any previous ones.

    Returns the raw 43-character URL-safe token to be embedded in the link.
    The SHA-256 hash of this token is stored in the database — the raw value
    is never persisted.

    Returns None on database error.
    """
    _ensure_notification_tables()
    email = email.strip().lower()
    raw = secrets.token_urlsafe(32)
    tok_hash = _hash_token(raw)
    expires = _expires_iso(hours=_VERIFY_TTL_HOURS)
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            # Invalidate all previous unused verification tokens for this user
            db.execute(
                "UPDATE notification_tokens SET used_at = ? "
                "WHERE email = ? AND token_type = 'email_verify' AND used_at IS NULL",
                (_now_iso(), email),
            )
            db.execute(
                "INSERT INTO notification_tokens "
                "(token_hash, token_type, user_id, email, expires_at, ip_address) "
                "VALUES (?, 'email_verify', ?, ?, ?, ?)",
                (tok_hash, user_id, email, expires, ip),
            )
        record_audit("verify_token_issued", email=email, ip=ip)
        return raw
    except Exception as exc:
        _logger.error("Failed to issue verification token: %s", exc)
        return None


def verify_email_token(raw_token: str, *, ip: str | None = None) -> bool:
    """Validate a verification token and mark the user's email as verified.

    Returns True on success, False if the token is invalid, expired, or
    already used.  This function is idempotent once it returns True (any
    subsequent call with the same token will return False due to used_at).
    """
    _ensure_notification_tables()
    tok_hash = _hash_token(raw_token.strip())
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT token_hash, email, user_id, expires_at, used_at "
                "FROM notification_tokens "
                "WHERE token_hash = ? AND token_type = 'email_verify'",
                (tok_hash,),
            )
            if not row:
                record_audit("verify_failed", ip=ip, success=False, detail="token_not_found")
                return False
            if row["used_at"]:
                record_audit(
                    "verify_failed", email=row["email"], ip=ip,
                    success=False, detail="already_used",
                )
                return False
            if datetime.now(timezone.utc) > _parse_dt(row["expires_at"]):
                record_audit(
                    "verify_failed", email=row["email"], ip=ip,
                    success=False, detail="expired",
                )
                return False
            now = _now_iso()
            db.execute(
                "UPDATE notification_tokens SET used_at = ? WHERE token_hash = ?",
                (now, tok_hash),
            )
            db.execute(
                "UPDATE users SET is_email_verified = 1 WHERE user_id = ?",
                (row["user_id"],),
            )
        record_audit("verify_success", email=row["email"], ip=ip)
        return True
    except Exception as exc:
        _logger.error("Failed to verify email token: %s", exc)
        return False


def is_email_verified(email: str) -> bool:
    """Return True if this user's email address is verified.

    Fails open (returns True) if the column does not exist yet (pre-migration)
    to avoid blocking existing users who signed up before this feature.
    """
    _ensure_notification_tables()
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT is_email_verified FROM users WHERE email = ?",
                (email.strip().lower(),),
            )
        if row is None:
            return True  # User not found — gate handles this upstream
        val = row.get("is_email_verified")
        if val is None:
            return True  # Column not yet migrated — treat as verified
        return bool(val)
    except Exception:
        return True  # Fail open


# ── Password reset tokens ─────────────────────────────────────────────────────

def issue_reset_token(email: str, *, ip: str | None = None) -> str | None:
    """Issue a password-reset token for the given email address.

    - Invalidates ALL previous unused reset tokens for this user.
    - Also clears the legacy ``users.reset_token`` column.
    - Returns the raw token (to embed in the email link), or None if the
      email address is not registered.  The caller MUST NOT reveal the None
      result to end-users (prevents email enumeration).
    """
    _ensure_notification_tables()
    email = email.strip().lower()
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone("SELECT user_id FROM users WHERE email = ?", (email,))
            if not row:
                record_audit(
                    "reset_unknown_email", email=email, ip=ip,
                    success=False, detail="email_not_found",
                )
                return None
            user_id = row["user_id"]
            now = _now_iso()
            # Invalidate all previous unused reset tokens
            db.execute(
                "UPDATE notification_tokens SET used_at = ? "
                "WHERE email = ? AND token_type = 'password_reset' AND used_at IS NULL",
                (now, email),
            )
            # Clear legacy column
            db.execute(
                "UPDATE users SET reset_token = NULL, reset_token_expires = NULL "
                "WHERE email = ?",
                (email,),
            )
            raw = secrets.token_urlsafe(32)
            tok_hash = _hash_token(raw)
            expires = _expires_iso(minutes=_RESET_TTL_MINUTES)
            db.execute(
                "INSERT INTO notification_tokens "
                "(token_hash, token_type, user_id, email, expires_at, ip_address) "
                "VALUES (?, 'password_reset', ?, ?, ?, ?)",
                (tok_hash, user_id, email, expires, ip),
            )
        record_audit("reset_token_issued", email=email, ip=ip)
        return raw
    except Exception as exc:
        _logger.error("Failed to issue reset token: %s", exc)
        return None


def verify_reset_token_valid(raw_token: str) -> dict | None:
    """Peek at a reset token without consuming it.

    Returns ``{"email": ..., "display_name": ...}`` if valid, else None.
    Used to pre-validate before showing the password form to the user.
    """
    _ensure_notification_tables()
    tok_hash = _hash_token(raw_token.strip())
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT nt.email, nt.expires_at, nt.used_at, u.display_name "
                "FROM notification_tokens nt "
                "JOIN users u ON u.email = nt.email "
                "WHERE nt.token_hash = ? AND nt.token_type = 'password_reset'",
                (tok_hash,),
            )
        if not row or row["used_at"]:
            return None
        if datetime.now(timezone.utc) > _parse_dt(row["expires_at"]):
            return None
        return {"email": row["email"], "display_name": row["display_name"]}
    except Exception:
        return None


def consume_reset_token(
    raw_token: str,
    new_password: str,
    *,
    ip: str | None = None,
) -> bool:
    """Validate a reset token, update the user's password, and invalidate the token.

    On success:
    - Marks the token as used (one-time use enforced).
    - Invalidates ALL other unused reset tokens for this user.
    - Updates the password hash.
    - Clears failed login count and lockout.

    Returns True on success, False on invalid/expired/already-used token.
    """
    _ensure_notification_tables()
    tok_hash = _hash_token(raw_token.strip())
    try:
        from utils.auth_gate import _AuthConn, _hash_password  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT token_hash, email, user_id, expires_at, used_at "
                "FROM notification_tokens "
                "WHERE token_hash = ? AND token_type = 'password_reset'",
                (tok_hash,),
            )
            if not row:
                record_audit("reset_failed", ip=ip, success=False, detail="token_not_found")
                return False
            if row["used_at"]:
                record_audit(
                    "reset_failed", email=row["email"], ip=ip,
                    success=False, detail="already_used",
                )
                return False
            if datetime.now(timezone.utc) > _parse_dt(row["expires_at"]):
                record_audit(
                    "reset_failed", email=row["email"], ip=ip,
                    success=False, detail="expired",
                )
                return False
            email = row["email"]
            now = _now_iso()
            new_hash = _hash_password(new_password)
            # Mark this token as used
            db.execute(
                "UPDATE notification_tokens SET used_at = ? WHERE token_hash = ?",
                (now, tok_hash),
            )
            # Invalidate all other unused reset tokens for this user
            db.execute(
                "UPDATE notification_tokens SET used_at = ? "
                "WHERE email = ? AND token_type = 'password_reset' AND used_at IS NULL",
                (now, email),
            )
            # Update password + clear lockout state
            db.execute(
                "UPDATE users SET password_hash = ?, reset_token = NULL, "
                "reset_token_expires = NULL, failed_login_count = 0, lockout_until = NULL "
                "WHERE email = ?",
                (new_hash, email),
            )
        record_audit("reset_success", email=row["email"], ip=ip)
        return True
    except Exception as exc:
        _logger.error("Failed to consume reset token: %s", exc)
        return False


# ── High-level flow triggers ──────────────────────────────────────────────────

def trigger_welcome_flow(
    email: str,
    display_name: str = "",
    *,
    ip: str | None = None,
) -> None:
    """Issue an email-verification token and send the welcome + verify email.

    Non-blocking — called immediately after successful account creation.
    All errors are logged but never raised, so signup always succeeds even
    if the email provider is temporarily unavailable.
    """
    _ensure_notification_tables()
    email = email.strip().lower()
    display_name = display_name.strip() or email.split("@")[0]
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone("SELECT user_id FROM users WHERE email = ?", (email,))
        if not row:
            return
        raw = issue_verification_token(email, row["user_id"], ip=ip)
        if not raw:
            return
        verify_url = f"{_APP_BASE_URL}/?auth=verify&token={raw}"
        from utils.email_utils import send_verification_email
        send_verification_email(email, display_name, verify_url)
    except Exception as exc:
        _logger.warning("trigger_welcome_flow error: %s", exc)


def trigger_reset_flow(email: str, *, ip: str | None = None) -> None:
    """Issue a reset token and send the password-reset email.

    Rate-limited to _RATE_LIMIT_MAX requests per hour per email/IP.
    Always returns None — the caller should display a GENERIC success message
    regardless of whether the email exists, to prevent enumeration.
    """
    email = email.strip().lower()

    # Per-email rate limit
    rl_email = f"reset:email:{email}"
    if not check_rate_limit(rl_email):
        record_audit(
            "reset_rate_limited", email=email, ip=ip,
            success=False, detail="email_rate_limit",
        )
        return  # Silent drop — generic message shown by caller

    # Per-IP rate limit (if IP is available)
    if ip:
        rl_ip = f"reset:ip:{ip}"
        if not check_rate_limit(rl_ip):
            record_audit(
                "reset_rate_limited", email=email, ip=ip,
                success=False, detail="ip_rate_limit",
            )
            return
        record_rate_event(rl_ip)

    record_rate_event(rl_email)

    raw = issue_reset_token(email, ip=ip)
    if not raw:
        return  # Email not registered — silent drop, generic message to caller

    reset_url = f"{_APP_BASE_URL}/?auth=reset&token={raw}"
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone("SELECT display_name FROM users WHERE email = ?", (email,))
        dn = (row["display_name"] if row else None) or email.split("@")[0]
        from utils.email_utils import send_password_reset_email
        send_password_reset_email(email, dn, reset_url)
    except Exception as exc:
        _logger.warning("trigger_reset_flow email send failed: %s", exc)


def send_reset_code_email(email: str, code: str) -> None:
    """Email a 6-digit reset code — adapter for the existing in-app code flow.

    Called from ``_generate_reset_token`` so both login-form code paths
    automatically email the code without UI changes to the form renderer.
    """
    try:
        from utils.auth_gate import _AuthConn  # type: ignore[reportPrivateUsage]
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT display_name FROM users WHERE email = ?",
                (email.strip().lower(),),
            )
        dn = (row["display_name"] if row else None) or email.split("@")[0]
        from utils.email_utils import send_reset_code_only_email
        send_reset_code_only_email(email, dn, code)
        record_audit("reset_code_emailed", email=email)
    except Exception as exc:
        _logger.warning("send_reset_code_email error: %s", exc)


# ── In-app verification banner ────────────────────────────────────────────────

def show_verification_banner(email: str) -> None:
    """Show a non-blocking toast reminder once per session if email is unverified.

    Safe to call on every authenticated page load — guarded by session state.
    """
    if not email:
        return
    import streamlit as st  # Import here to stay FastAPI-safe at module level
    _ss_key = "_verify_banner_shown"
    if st.session_state.get(_ss_key):
        return
    try:
        if not is_email_verified(email):
            st.session_state[_ss_key] = True
            st.toast(
                "📧 Verify your email — check your inbox for a confirmation link.",
                icon="⚠️",
            )
    except Exception:
        pass
