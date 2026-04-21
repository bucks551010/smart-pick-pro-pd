"""api/routes/session.py – HttpOnly session cookie endpoints.

These endpoints are the server-side half of the session management
strategy.  The Streamlit JS layer issues JS-accessible cookies for
localStorage fallback, then POSTs to these endpoints so the API can
set HttpOnly / Secure / SameSite=Strict mirror cookies that
JavaScript cannot read or tamper with.

Endpoints:
  POST /api/session/issue    – write HttpOnly cookie from a provided token
  POST /api/session/refresh  – extend an existing HttpOnly cookie
  POST /api/session/clear    – expire the HttpOnly cookie on logout
"""
import datetime
from utils.logger import get_logger

_logger = get_logger(__name__)

_COOKIE_NAME    = "spp_session_hi"   # "hi" = HttpOnly; distinct from the JS cookie
_TTL_SECONDS    = 30 * 86400         # 30 days

try:
    from fastapi import APIRouter, Request, Response
    from pydantic import BaseModel
    router = APIRouter(prefix="/api/session", tags=["session"])
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    router = None


if _FASTAPI_AVAILABLE:

    class _IssueBody(BaseModel):
        token: str

    def _set_httponly_cookie(response: Response, token: str, max_age: int = _TTL_SECONDS) -> None:
        """Attach the HttpOnly session cookie to a FastAPI response."""
        response.set_cookie(
            key=_COOKIE_NAME,
            value=token,
            max_age=max_age,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )

    def _validate_token(token: str) -> bool:
        """Return True iff the token exists and has not expired."""
        if not token or len(token) > 256:
            return False
        try:
            from utils.auth_gate import _load_session_by_token
            return _load_session_by_token(token) is not None
        except Exception:
            return False

    @router.post("/issue")
    async def issue_session(body: _IssueBody, response: Response) -> dict:
        """Accept a token from the JS layer and mirror it as an HttpOnly cookie.

        The JS cookie (``spp_session``) is already set by the Streamlit
        component.  This endpoint creates a server-controlled shadow
        cookie (``spp_session_hi``) with ``HttpOnly`` so the token
        cannot be exfiltrated by XSS.
        """
        token = (body.token or "").strip()
        if not _validate_token(token):
            return {"ok": False, "reason": "invalid_token"}
        _set_httponly_cookie(response, token)
        return {"ok": True}

    @router.post("/refresh")
    async def refresh_session(request: Request, response: Response) -> dict:
        """Extend both the HttpOnly cookie and the DB expiry for active users.

        Called by the JS heartbeat every ~23 hours.  Returns 200 even if
        the token is absent (the client can recover via localStorage).
        """
        token = request.cookies.get(_COOKIE_NAME, "").strip()
        if not token:
            # Also accept the JS-readable cookie as fallback.
            token = request.cookies.get("spp_session", "").strip()
        if not token:
            return {"ok": False, "reason": "no_token"}
        if not _validate_token(token):
            # Token expired — tell the client to re-login.
            response.delete_cookie(_COOKIE_NAME, path="/")
            return {"ok": False, "reason": "expired"}
        # _load_session_by_token already applied sliding window; re-issue cookie.
        _set_httponly_cookie(response, token)
        return {"ok": True}

    @router.post("/clear")
    async def clear_session(response: Response) -> dict:
        """Expire the HttpOnly cookie on logout."""
        response.delete_cookie(_COOKIE_NAME, path="/")
        return {"ok": True}
