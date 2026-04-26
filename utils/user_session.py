"""
utils/user_session.py
─────────────────────
Centralized helper for resolving the *current user's identifier* across
the Streamlit app. Used by the per-user Live Entry Bucket, Entry Builder
lock-in flow, and Bet Tracker filtering so every user only sees their
own bets and bucket picks.

Identity resolution order:
    1. Stripe-authenticated customer email (utils/auth._SS_CUSTOMER_EMAIL)
    2. Tournament module user_email session key (legacy)
    3. URL query param ?user= or ?email=
    4. Anonymous fallback "anonymous@local"  (dev mode without Stripe)

The fallback ensures the bucket / bet tracker remain functional when
SMARTAI_PRODUCTION is not set (developer / demo mode).
"""

from __future__ import annotations

import streamlit as st


_ANON_USER = "anonymous@local"

_SESSION_EMAIL_KEYS = (
    "_sub_customer_email",   # Stripe auth (utils/auth.py)
    "user_email",            # Tournament accounts module
    "email",                 # Generic fallback
)


def _normalize(value: str) -> str:
    return str(value or "").strip().lower()


def get_current_user_email() -> str:
    """Return the active user's email identifier (lowercased) with anonymous fallback."""
    # 1) session-state keys
    for key in _SESSION_EMAIL_KEYS:
        val = _normalize(st.session_state.get(key, ""))
        if val:
            return val

    # 2) query params (?user= / ?email=)
    try:
        qp = st.query_params
        for key in ("user", "email"):
            val = _normalize(qp.get(key, "") if hasattr(qp, "get") else "")
            if val:
                return val
    except Exception:
        pass

    # 3) anonymous default — keeps the app usable in dev / no-auth mode
    return _ANON_USER


def is_anonymous_user() -> bool:
    """True when the active user has no real authenticated email."""
    return get_current_user_email() == _ANON_USER


def get_user_display_label() -> str:
    """Short label for UI captions ('You · email' or 'Guest session')."""
    email = get_current_user_email()
    if email == _ANON_USER:
        return "👤 Guest session (sign in to sync across devices)"
    return f"👤 {email}"
