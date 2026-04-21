"""api/routes/notifications.py — FastAPI notification endpoints.

Endpoints
─────────
POST /api/auth/forgot-password
    Request a password reset email.
    Body: { "email": "user@example.com" }
    Response: always { "ok": true, "message": "..." }  (prevents email enumeration)

POST /api/auth/reset-password
    Complete a password reset using a token received via email.
    Body: { "token": "<raw_token>", "new_password": "..." }
    Response: { "ok": true|false, "reason": "..." }

GET /api/auth/verify-email?token=<raw_token>
    Validate an email-verification link.
    On success: redirects to /?auth=verified  (Streamlit shows success toast)
    On failure: returns JSON { "ok": false, "reason": "..." }

POST /api/auth/verify-email
    JSON body: { "token": "<raw_token>" }
    Response: { "ok": true|false, "reason": "..." }
    (Used by AJAX callers; the GET form is for email link clicks)

Rate limiting
─────────────
The forgot-password endpoint enforces 3 requests/hour per IP + per email.
This is handled inside trigger_reset_flow() and is transparent to the route.

Audit logging
─────────────
All token operations are audit-logged in notification_audit_log via the
notifications module.  The FastAPI request IP is forwarded automatically.
"""
from __future__ import annotations

import re
from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse, RedirectResponse
    from pydantic import BaseModel, field_validator
    _FASTAPI_OK = True
except ImportError:
    _FASTAPI_OK = False

if not _FASTAPI_OK:
    # Provide a dummy router so main.py import does not fail
    class _DummyRouter:  # type: ignore[no-redef]
        def post(self, *a, **kw):
            return lambda f: f
        def get(self, *a, **kw):
            return lambda f: f
    router = _DummyRouter()  # type: ignore[assignment]
else:
    router = APIRouter(prefix="/api/auth", tags=["notifications"])

    _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", re.IGNORECASE)
    _MIN_PW   = 8

    # ── Request / Response models ──────────────────────────────────────────────

    class ForgotPasswordRequest(BaseModel):
        email: str

        @field_validator("email")
        @classmethod
        def validate_email(cls, v: str) -> str:
            v = v.strip().lower()
            if not _EMAIL_RE.match(v):
                raise ValueError("Invalid email address")
            return v

    class ResetPasswordRequest(BaseModel):
        token: str
        new_password: str

        @field_validator("token")
        @classmethod
        def validate_token(cls, v: str) -> str:
            v = v.strip()
            if len(v) < 10:
                raise ValueError("Invalid token")
            return v

        @field_validator("new_password")
        @classmethod
        def validate_password(cls, v: str) -> str:
            if len(v) < _MIN_PW:
                raise ValueError(f"Password must be at least {_MIN_PW} characters")
            if not any(c.isalpha() for c in v):
                raise ValueError("Password must contain at least one letter")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one number")
            return v

    class VerifyEmailRequest(BaseModel):
        token: str

        @field_validator("token")
        @classmethod
        def validate_token(cls, v: str) -> str:
            return v.strip()

    # ── Helper: extract real client IP ────────────────────────────────────────

    def _client_ip(request: Request) -> str | None:
        """Return the real client IP, respecting X-Forwarded-For from Caddy."""
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            # Take the leftmost (original client) address
            ip = xff.split(",")[0].strip()
            return ip if ip else None
        return getattr(request.client, "host", None)

    # ── Endpoints ──────────────────────────────────────────────────────────────

    @router.post("/forgot-password")
    async def forgot_password(body: ForgotPasswordRequest, request: Request) -> JSONResponse:
        """Trigger a password-reset email.

        Security:
        - ALWAYS returns the same success response regardless of whether the
          email exists in the database (prevents account enumeration).
        - Rate limited to 3 requests/hour per email and per IP.
        - The actual rate-limiting and token issuance happen inside
          trigger_reset_flow(), which silently no-ops if blocked.
        """
        ip = _client_ip(request)
        try:
            from utils.notifications import trigger_reset_flow
            trigger_reset_flow(body.email, ip=ip)
        except Exception as exc:
            _logger.warning("forgot_password handler error: %s", exc)

        # Generic response — never reveal whether email exists
        return JSONResponse({
            "ok": True,
            "message": (
                "If an account with that email exists, "
                "a password reset link has been sent."
            ),
        })

    @router.post("/reset-password")
    async def reset_password(body: ResetPasswordRequest, request: Request) -> JSONResponse:
        """Complete a password reset using the token from the email link."""
        ip = _client_ip(request)
        try:
            from utils.notifications import consume_reset_token
            ok = consume_reset_token(body.token, body.new_password, ip=ip)
        except Exception as exc:
            _logger.warning("reset_password handler error: %s", exc)
            ok = False

        if ok:
            return JSONResponse({"ok": True, "message": "Password updated successfully."})
        return JSONResponse(
            {"ok": False, "reason": "invalid_or_expired_token"},
            status_code=400,
        )

    @router.get("/verify-email")
    async def verify_email_get(token: str = "", request: Request = None) -> object:
        """Handle email-verification link clicks.

        On success: redirect to /?auth=verified so Streamlit can show a
        confirmation message and log the user in.
        On failure: return JSON error (Caddy will serve Streamlit for the /
        paths anyway, so we keep the redirect path clean).
        """
        ip = _client_ip(request) if request else None
        if not token:
            return JSONResponse({"ok": False, "reason": "missing_token"}, status_code=400)
        try:
            from utils.notifications import verify_email_token
            ok = verify_email_token(token.strip(), ip=ip)
        except Exception as exc:
            _logger.warning("verify_email_get handler error: %s", exc)
            ok = False

        if ok:
            # Redirect to Streamlit — require_login() will handle ?auth=verified
            return RedirectResponse(url="/?auth=verified", status_code=302)
        return JSONResponse(
            {"ok": False, "reason": "invalid_or_expired_token"},
            status_code=400,
        )

    @router.post("/verify-email")
    async def verify_email_post(body: VerifyEmailRequest, request: Request) -> JSONResponse:
        """Verify email via JSON POST (used by programmatic / AJAX callers)."""
        ip = _client_ip(request)
        try:
            from utils.notifications import verify_email_token
            ok = verify_email_token(body.token, ip=ip)
        except Exception as exc:
            _logger.warning("verify_email_post handler error: %s", exc)
            ok = False

        if ok:
            return JSONResponse({"ok": True, "message": "Email verified successfully."})
        return JSONResponse(
            {"ok": False, "reason": "invalid_or_expired_token"},
            status_code=400,
        )
