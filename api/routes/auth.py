"""api/routes/auth.py — JWT access-token endpoints.

POST /api/auth/token    Issue a short-lived JWT by reading the HttpOnly
                        refresh cookie (spp_session_hi).  Called by the
                        browser's fetch interceptor on page load and after
                        any 401 response.

POST /api/auth/logout   Invalidate the DB session token, clear all cookies,
                        and return 200.  The JS layer clears localStorage.

These endpoints are the server side of the Zero-Friction auth strategy:
the fetch interceptor (injected by utils/state_sync.py) calls /api/auth/token
automatically so application code never handles raw JWT strings.
"""

from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    from fastapi import APIRouter, Request, Response
    router = APIRouter(prefix="/api/auth", tags=["auth"])
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    router = None  # type: ignore


if _FASTAPI_AVAILABLE:

    @router.post("/token")
    async def issue_token(request: Request, response: Response) -> dict:
        """Issue a JWT access token from the long-lived refresh session.

        Reads the ``spp_session_hi`` HttpOnly cookie (written by
        ``/api/session/issue`` after login) or falls back to the JS-readable
        ``spp_session`` cookie.  Validates the token against the DB and, if
        valid, returns a signed JWT access token.

        Response::

            {
                "ok":           true,
                "access_token": "<jwt>",
                "token_type":   "Bearer",
                "expires_in":   3600
            }

        On failure::

            { "ok": false, "reason": "no_session" | "expired" }
        """
        from utils.auth_gate import _load_session_by_token
        from utils.jwt_utils import issue_access_token, access_ttl_seconds

        # HttpOnly cookie (set by /api/session/issue) is preferred;
        # JS-readable cookie is the fallback for environments that
        # don't yet have the shadow cookie written.
        refresh_token = (
            request.cookies.get("spp_session_hi", "")
            or request.cookies.get("spp_session", "")
        ).strip()

        if not refresh_token:
            return {"ok": False, "reason": "no_session"}

        row = _load_session_by_token(refresh_token)
        if not row:
            # Refresh token expired — expire the stale cookie.
            response.delete_cookie("spp_session_hi", path="/")
            return {"ok": False, "reason": "expired"}

        access_token = issue_access_token(
            user_id=int(row.get("user_id", 0)),
            email=str(row.get("email", "")),
            is_admin=bool(row.get("is_admin", 0)),
        )
        return {
            "ok":           True,
            "access_token": access_token,
            "token_type":   "Bearer",
            "expires_in":   access_ttl_seconds(),
        }

    @router.post("/logout")
    async def logout(request: Request, response: Response) -> dict:
        """Invalidate the session and clear all auth cookies.

        Deletes the DB token record for both the HttpOnly and JS-readable
        cookies.  The JS layer is responsible for clearing localStorage.
        """
        from utils.auth_gate import _delete_session_token

        for cookie_name in ("spp_session_hi", "spp_session"):
            token = request.cookies.get(cookie_name, "").strip()
            if token:
                try:
                    _delete_session_token(token)
                except Exception as exc:
                    _logger.warning("Failed to delete session token: %s", exc)

        response.delete_cookie("spp_session_hi", path="/")
        response.delete_cookie("spp_session",    path="/")
        return {"ok": True}
