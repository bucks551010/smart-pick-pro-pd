"""
utils/session_guard.py
======================
Inactivity-based session timeout for Streamlit pages.

Security controls
-----------------
  CWE-613 – Insufficient Session Expiration : purges all sensitive
             session-state keys after the idle window expires
  CWE-312 – Cleartext Storage of Sensitive Data : wipes in-memory copies
             of credentials, tokens, and tier flags

Configuration
-------------
Set SESSION_IDLE_TIMEOUT_SECONDS in .streamlit/secrets.toml (or env var):

    SESSION_IDLE_TIMEOUT_SECONDS = 1800   # 30 minutes (default)

Usage
-----
Call enforce_session_timeout() at the TOP of every authenticated page,
*before* any content is rendered:

    from utils.session_guard import enforce_session_timeout
    enforce_session_timeout()

For a custom per-page timeout:

    enforce_session_timeout(idle_timeout_seconds=900)  # 15 min
"""

from __future__ import annotations

import os
import time

import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_IDLE_TIMEOUT_SECONDS = 1_800   # 30 minutes
_WARNING_LEAD_SECONDS         = 300     # show warning 5 min before expiry

# Session-state keys this module manages
_SS_LAST_ACTIVITY = "_guard_last_activity_ts"
_SS_WARNED        = "_guard_timeout_warned"

# All sensitive session-state key prefixes to purge on timeout
_SENSITIVE_SS_PREFIXES = ("_auth_", "_sub_", "_msal_")

# Additional explicit keys that don't follow the prefix pattern
_SENSITIVE_SS_EXTRA_KEYS = (
    "logged_in",          # legacy key used by some pages
    "user_id",
    "user_email",
    "plan_tier",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_idle_timeout() -> int:
    """
    Read SESSION_IDLE_TIMEOUT_SECONDS from secrets or env.
    Falls back to _DEFAULT_IDLE_TIMEOUT_SECONDS.
    """
    try:
        raw = st.secrets.get("SESSION_IDLE_TIMEOUT_SECONDS")
    except Exception:
        raw = None
    if raw is None:
        raw = os.environ.get("SESSION_IDLE_TIMEOUT_SECONDS")
    try:
        return max(60, int(raw))  # minimum 60 seconds
    except (TypeError, ValueError):
        return _DEFAULT_IDLE_TIMEOUT_SECONDS


def _touch_activity() -> None:
    """Record the current timestamp as the last user-activity time."""
    st.session_state[_SS_LAST_ACTIVITY] = time.time()


def _is_session_active() -> bool:
    """Return True when the user's session is within the idle window."""
    last = st.session_state.get(_SS_LAST_ACTIVITY)
    if last is None:
        return True   # brand-new session, not yet timed out
    return (time.time() - last) < _get_idle_timeout()


def _seconds_until_timeout() -> float:
    """Return remaining idle seconds; 0 if already expired."""
    last = st.session_state.get(_SS_LAST_ACTIVITY)
    if last is None:
        return float(_get_idle_timeout())
    elapsed  = time.time() - last
    timeout  = _get_idle_timeout()
    return max(0.0, timeout - elapsed)


def _purge_sensitive_state() -> None:
    """
    Remove all sensitive credential / identity keys from session state.

    Called when the session has timed out to prevent residual sensitive data
    from leaking to the next user of the browser tab (CWE-613, CWE-312).
    """
    keys_to_delete = [
        key for key in list(st.session_state.keys())
        if any(key.startswith(prefix) for prefix in _SENSITIVE_SS_PREFIXES)
        or key in _SENSITIVE_SS_EXTRA_KEYS
    ]
    for key in keys_to_delete:
        try:
            del st.session_state[key]
        except KeyError:
            pass  # already gone

    # Also clear MSAL session via its own helper if available
    try:
        from utils.msal_auth import _clear_msal_session  # noqa: PLC0415
        _clear_msal_session()
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_activity() -> None:
    """
    Explicitly record that the user performed an activity right now.

    Call this in response to meaningful user interactions (button clicks,
    form submissions) to keep the session alive.  enforce_session_timeout()
    also calls this implicitly when the session is still valid.
    """
    _touch_activity()
    st.session_state.pop(_SS_WARNED, None)  # reset warning flag after activity


def enforce_session_timeout(
    idle_timeout_seconds: int | None = None,
    *,
    require_auth: bool = True,
) -> None:
    """
    Enforce inactivity-based session timeout.

    This function should be called at the top of every page.  It will:
      1. Skip enforcement if the user is not logged in (unless require_auth).
      2. Expire and purge the session when the idle window has elapsed.
      3. Render a 5-minute warning toast before expiry (once per window).
      4. Reset the idle timer on each page load where the session is valid.

    Parameters
    ----------
    idle_timeout_seconds : int | None
        Override the configured timeout for this specific page.  If None,
        uses SESSION_IDLE_TIMEOUT_SECONDS from secrets / env / default.
    require_auth : bool
        When True (default), do nothing if the user is not authenticated.
        Set to False on public pages that still benefit from cleanup.
    """
    # ---- Guard: only enforce for authenticated users --------------------
    is_logged_in = bool(st.session_state.get("_auth_logged_in", False))
    if require_auth and not is_logged_in:
        return

    # ---- Override timeout if explicitly passed --------------------------
    if idle_timeout_seconds is not None:
        timeout = max(60, int(idle_timeout_seconds))
    else:
        timeout = _get_idle_timeout()

    last_activity = st.session_state.get(_SS_LAST_ACTIVITY)

    # Brand-new authenticated session: stamp activity and return
    if last_activity is None:
        _touch_activity()
        return

    elapsed  = time.time() - last_activity
    remaining = timeout - elapsed

    # ---- Session expired ------------------------------------------------
    if remaining <= 0:
        _purge_sensitive_state()
        # Clear guard keys themselves
        st.session_state.pop(_SS_LAST_ACTIVITY, None)
        st.session_state.pop(_SS_WARNED, None)

        st.warning(
            "⏱ Your session has expired due to inactivity. "
            "Please sign in again."
        )
        st.stop()
        return

    # ---- Approaching timeout: show one-time warning ---------------------
    if remaining <= _WARNING_LEAD_SECONDS and not st.session_state.get(_SS_WARNED, False):
        minutes_left = int(remaining // 60) + 1
        st.toast(
            f"⚠️ Your session will expire in {minutes_left} minute(s) "
            "due to inactivity.",
            icon="⏱",
        )
        st.session_state[_SS_WARNED] = True

    # ---- Session valid: refresh the activity timestamp -----------------
    _touch_activity()


def get_session_idle_seconds() -> float:
    """
    Return the number of seconds since the last recorded user activity.
    Returns 0 if activity has never been recorded.
    """
    last = st.session_state.get(_SS_LAST_ACTIVITY)
    if last is None:
        return 0.0
    return max(0.0, time.time() - last)


def get_session_remaining_seconds() -> float:
    """
    Return the number of seconds before the session will expire.
    Returns 0 when already expired.
    """
    return _seconds_until_timeout()
