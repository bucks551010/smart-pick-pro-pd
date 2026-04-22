"""
utils/msal_auth.py
==================
Azure AD SSO via MSAL (Microsoft Authentication Library) for Streamlit.

Security controls:
  CWE-287 – Improper Authentication   : OIDC id_token claims validated
  CWE-352 – CSRF                       : cryptographically random `state` param
  CWE-613 – Insufficient Session Expiration: _clear_msal_session() wipes all
                                         sensitive MSAL keys on logout/timeout
  CWE-522 – Credentials in code        : secrets loaded from st.secrets only

Required secrets (.streamlit/secrets.toml):
    AZURE_TENANT_ID         = "your-tenant-id"
    AZURE_CLIENT_ID         = "your-client-id"
    AZURE_CLIENT_SECRET     = "your-client-secret"
    AZURE_REDIRECT_URI      = "https://your-app-url/callback"
    AZURE_ADMIN_GROUP_ID    = "optional-aad-group-object-id"  # optional

Usage in pages:
    from utils.msal_auth import render_msal_login_button, is_msal_authenticated
    render_msal_login_button()
    if is_msal_authenticated():
        st.write("Hello", get_msal_email())
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import streamlit as st

# ---------------------------------------------------------------------------
# Optional MSAL import – feature degrades gracefully if package not installed
# ---------------------------------------------------------------------------
try:
    import msal  # pip install msal
    _MSAL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MSAL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Session-state key constants (all prefixed _msal_ to ease bulk purge)
# ---------------------------------------------------------------------------
_SS_MSAL_AUTHENTICATED = "_msal_authenticated"
_SS_MSAL_EMAIL         = "_msal_email"
_SS_MSAL_NAME          = "_msal_name"
_SS_MSAL_GROUPS        = "_msal_groups"
_SS_MSAL_ID_TOKEN      = "_msal_id_token"
_SS_MSAL_STATE         = "_msal_state"
_SS_MSAL_NONCE         = "_msal_nonce"
_SS_MSAL_NONCE_TS      = "_msal_nonce_ts"

_NONCE_TTL_SECONDS = 600  # nonce expires after 10 minutes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_secret(key: str, default: str | None = None) -> str | None:
    """Read from st.secrets with env-var fallback; never raises."""
    try:
        return st.secrets[key]
    except Exception:
        # Catches KeyError, AttributeError, and StreamlitSecretNotFoundError
        # (raised when no secrets.toml file exists, e.g. on Railway/Docker).
        return os.environ.get(key, default)


def _build_msal_app() -> "msal.ConfidentialClientApplication | None":
    """
    Construct a server-side MSAL ConfidentialClientApplication.
    Returns None when MSAL package is absent or secrets are not configured.
    """
    if not _MSAL_AVAILABLE:
        return None
    tenant_id     = _get_secret("AZURE_TENANT_ID")
    client_id     = _get_secret("AZURE_CLIENT_ID")
    client_secret = _get_secret("AZURE_CLIENT_SECRET")
    if not all([tenant_id, client_id, client_secret]):
        return None

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    return msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_msal_configured() -> bool:
    """Return True only when all required secrets are present."""
    required = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID",
                "AZURE_CLIENT_SECRET", "AZURE_REDIRECT_URI")
    return all(_get_secret(k) for k in required)


def is_msal_authenticated() -> bool:
    """Return True when the session holds a verified MSAL identity."""
    return bool(st.session_state.get(_SS_MSAL_AUTHENTICATED, False))


def get_msal_email() -> str | None:
    """Return the verified email claim from the MSAL id_token."""
    return st.session_state.get(_SS_MSAL_EMAIL)


def get_msal_display_name() -> str | None:
    """Return the display name claim from the MSAL id_token."""
    return st.session_state.get(_SS_MSAL_NAME)


def get_msal_groups() -> list[str]:
    """Return the list of Azure AD group object-IDs the user belongs to."""
    return st.session_state.get(_SS_MSAL_GROUPS, [])


def is_msal_admin() -> bool:
    """
    Return True when the user is a member of the configured admin AAD group.
    Falls back to False when AZURE_ADMIN_GROUP_ID is not set.
    """
    admin_group = _get_secret("AZURE_ADMIN_GROUP_ID")
    if not admin_group:
        return False
    return admin_group in get_msal_groups()


def get_auth_url() -> str | None:
    """
    Build the Microsoft /authorize URL.
    Stores a cryptographically random `state` and `nonce` in session state
    to prevent CSRF and replay attacks (CWE-352).
    Returns None when MSAL is not configured.
    """
    if not is_msal_configured():
        return None

    app = _build_msal_app()
    if app is None:
        return None

    redirect_uri = _get_secret("AZURE_REDIRECT_URI")
    scopes       = ["openid", "email", "profile"]

    # --- CSRF / replay prevention -----------------------------------------
    # secrets.token_urlsafe uses os.urandom, which is cryptographically strong
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    st.session_state[_SS_MSAL_STATE]    = state
    st.session_state[_SS_MSAL_NONCE]    = hashlib.sha256(nonce.encode()).hexdigest()
    st.session_state[_SS_MSAL_NONCE_TS] = time.time()

    auth_url_info = app.get_authorization_request_url(
        scopes=scopes,
        state=state,
        nonce=nonce,
        redirect_uri=redirect_uri,
    )
    return auth_url_info


def handle_auth_callback(code: str, returned_state: str) -> bool:
    """
    Exchange an authorization code for tokens, validate claims, and populate
    session state with the verified identity.

    Returns True on success, False on any validation failure.

    Security checks performed:
      1. state parameter equality   (CWE-352 CSRF)
      2. nonce TTL expiry           (replay window bounded to _NONCE_TTL_SECONDS)
      3. nonce hash comparison      (replay attack prevention)
      4. required claims present    (CWE-20 input validation)
    """
    if not is_msal_configured():
        return False

    # ------------------------------------------------------------------
    # 1. Validate CSRF state (constant-time compare)
    # ------------------------------------------------------------------
    expected_state = st.session_state.get(_SS_MSAL_STATE, "")
    if not secrets.compare_digest(expected_state, returned_state):
        st.error("Authentication failed: invalid state parameter.")
        _clear_msal_session()
        return False

    # ------------------------------------------------------------------
    # 2. Nonce TTL check
    # ------------------------------------------------------------------
    nonce_ts = st.session_state.get(_SS_MSAL_NONCE_TS, 0)
    if time.time() - nonce_ts > _NONCE_TTL_SECONDS:
        st.error("Authentication session expired. Please try again.")
        _clear_msal_session()
        return False

    app = _build_msal_app()
    if app is None:
        return False

    redirect_uri = _get_secret("AZURE_REDIRECT_URI")

    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=["openid", "email", "profile"],
        redirect_uri=redirect_uri,
    )

    if "error" in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        st.error(f"Authentication error: {error_desc}")
        _clear_msal_session()
        return False

    id_token_claims: dict[str, Any] = result.get("id_token_claims", {})

    # ------------------------------------------------------------------
    # 3. Nonce hash verification (replay prevention)
    # ------------------------------------------------------------------
    returned_nonce_hash = hashlib.sha256(
        id_token_claims.get("nonce", "").encode()
    ).hexdigest()
    stored_nonce_hash   = st.session_state.get(_SS_MSAL_NONCE, "")
    if not secrets.compare_digest(stored_nonce_hash, returned_nonce_hash):
        st.error("Authentication failed: nonce mismatch.")
        _clear_msal_session()
        return False

    # ------------------------------------------------------------------
    # 4. Required claims
    # ------------------------------------------------------------------
    email = (
        id_token_claims.get("email")
        or id_token_claims.get("preferred_username")
        or id_token_claims.get("upn")
    )
    if not email:
        st.error("Authentication failed: email claim missing from token.")
        _clear_msal_session()
        return False

    # ------------------------------------------------------------------
    # 5. Populate verified session state
    # ------------------------------------------------------------------
    st.session_state[_SS_MSAL_AUTHENTICATED] = True
    st.session_state[_SS_MSAL_EMAIL]         = email.lower().strip()
    st.session_state[_SS_MSAL_NAME]          = id_token_claims.get("name", "")
    st.session_state[_SS_MSAL_GROUPS]        = id_token_claims.get("groups", [])
    st.session_state[_SS_MSAL_ID_TOKEN]      = result.get("id_token", "")

    # Clear CSRF/nonce state after successful auth
    for key in (_SS_MSAL_STATE, _SS_MSAL_NONCE, _SS_MSAL_NONCE_TS):
        st.session_state.pop(key, None)

    return True


def logout_msal() -> None:
    """
    Sign the user out of the MSAL session and redirect to Microsoft's logout
    endpoint.  Also clears all sensitive MSAL session-state keys (CWE-613).
    """
    _clear_msal_session()

    tenant_id    = _get_secret("AZURE_TENANT_ID")
    redirect_uri = _get_secret("AZURE_REDIRECT_URI", "/")
    if tenant_id:
        logout_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={redirect_uri}"
        )
        st.markdown(
            f'<meta http-equiv="refresh" content="0; URL={logout_url}" />',
            unsafe_allow_html=True,
        )


def _clear_msal_session() -> None:
    """
    Purge all MSAL-related keys from session state.
    Called on logout and session timeout to prevent residual credential leakage
    (CWE-613 Insufficient Session Expiration).
    """
    msal_keys = [
        _SS_MSAL_AUTHENTICATED,
        _SS_MSAL_EMAIL,
        _SS_MSAL_NAME,
        _SS_MSAL_GROUPS,
        _SS_MSAL_ID_TOKEN,
        _SS_MSAL_STATE,
        _SS_MSAL_NONCE,
        _SS_MSAL_NONCE_TS,
    ]
    for key in msal_keys:
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# UI component
# ---------------------------------------------------------------------------

def render_msal_login_button(label: str = "Sign in with Microsoft") -> None:
    """
    Render a styled 'Sign in with Microsoft' button that redirects to Azure AD.
    Falls back to a warning message when MSAL is not configured.
    """
    if not is_msal_configured():
        st.warning(
            "Azure AD SSO is not configured. "
            "Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, "
            "and AZURE_REDIRECT_URI in your secrets."
        )
        return

    auth_url = get_auth_url()
    if not auth_url:
        st.error("Could not generate authentication URL.")
        return

    st.markdown(
        f"""
        <a href="{auth_url}" target="_self" style="
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background-color: #2f2f2f;
            color: #ffffff;
            padding: 10px 20px;
            border-radius: 4px;
            text-decoration: none;
            font-family: 'Segoe UI', sans-serif;
            font-size: 15px;
            font-weight: 600;
            border: 1px solid #555;
            cursor: pointer;
        ">
            <svg xmlns="http://www.w3.org/2000/svg" width="21" height="21" viewBox="0 0 21 21">
                <rect x="1"  y="1"  width="9" height="9" fill="#F25022"/>
                <rect x="11" y="1"  width="9" height="9" fill="#7FBA00"/>
                <rect x="1"  y="11" width="9" height="9" fill="#00A4EF"/>
                <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
            </svg>
            {label}
        </a>
        """,
        unsafe_allow_html=True,
    )


def process_callback_from_query_params() -> bool:
    """
    Convenience helper: detect OAuth callback query params and handle them.
    Call this at the top of the page that serves as AZURE_REDIRECT_URI.

    Returns True when a callback was detected and processed (success or fail),
    False when no callback params are present.
    """
    params = st.query_params
    code  = params.get("code")
    state = params.get("state")
    error = params.get("error")

    if error:
        error_desc = params.get("error_description", error)
        st.error(f"Azure AD returned an error: {error_desc}")
        _clear_msal_session()
        # Clear query params to prevent re-processing on rerun
        st.query_params.clear()
        return True

    if code and state:
        success = handle_auth_callback(code=code, returned_state=state)
        # Clear query params so the code cannot be replayed on page refresh
        st.query_params.clear()
        return True  # callback was handled (result checked via is_msal_authenticated())

    return False
