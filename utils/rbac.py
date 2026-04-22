"""
utils/rbac.py
=============
Role-Based Access Control (RBAC) for Smart Pick Pro.

Wraps the existing subscription-tier system and Azure AD group membership
with a uniform permission model.  All authorization decisions go through
this module to prevent scattered ad-hoc tier checks (CWE-285).

Permission model
----------------
Tier hierarchy (ascending):
    free < sharp_iq < smart_money < insider_circle

Each tier inherits all permissions from the tier(s) below it.

Usage examples
--------------
Decorator (Streamlit page function):

    from utils.rbac import require_permission, require_role

    @require_permission("advanced_filters")
    def render_advanced_filters():
        ...

    @require_role("admin")
    def render_admin_panel():
        ...

Inline guard:

    from utils.rbac import permission_gate, has_permission

    if has_permission("export_data"):
        st.download_button(...)
    else:
        permission_gate("export_data")   # renders upgrade CTA
"""

from __future__ import annotations

import functools
from typing import Callable

import streamlit as st

# ---------------------------------------------------------------------------
# Permission registry
# ---------------------------------------------------------------------------

# Each set lists the permissions granted *at that tier*.
# Lower tiers' permissions are NOT automatically included here; inclusion is
# handled in has_permission() via the _TIER_ORDER hierarchy.

_TIER_ORDER: list[str] = ["free", "sharp_iq", "smart_money", "insider_circle"]

PERMISSIONS: dict[str, set[str]] = {
    "free": {
        "view_dashboard",
        "view_player_props",
        "view_bet_tracker",
        "basic_search",
    },
    "sharp_iq": {
        "view_qam",           # Q-Score / AI Match analysis
        "advanced_filters",
        "view_trends",
        "view_line_movement",
    },
    "smart_money": {
        "export_data",        # CSV / PDF downloads
        "view_correlated",    # correlated picks
        "api_access",         # external API read
        "view_insider",       # insider intel tab
    },
    "insider_circle": {
        "*",                  # wildcard – all permissions
    },
    "admin": {
        "*",                  # wildcard – all permissions
    },
}

# Human-readable upgrade requirements shown in permission_gate()
_UPGRADE_LABELS: dict[str, str] = {
    "view_qam":           "Sharp IQ",
    "advanced_filters":   "Sharp IQ",
    "view_trends":        "Sharp IQ",
    "view_line_movement": "Sharp IQ",
    "export_data":        "Smart Money",
    "view_correlated":    "Smart Money",
    "api_access":         "Smart Money",
    "view_insider":       "Smart Money",
}


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

def _get_current_role() -> str:
    """
    Resolve the calling user's effective role.

    Priority:
      1. Admin flag set by auth_gate.py  (_auth_is_admin)
      2. Azure AD admin group membership  (from msal_auth)
      3. Subscription tier               (_sub_plan_name / _auth_plan_tier)

    Returns one of: "admin", "insider_circle", "smart_money", "sharp_iq",
    "free", or "anonymous".
    """
    # --- 1. admin flag set by auth system --------------------------------
    if st.session_state.get("_auth_is_admin", False):
        return "admin"

    # --- 2. Azure AD admin group (lazy import to avoid circular deps) ----
    try:
        from utils.msal_auth import is_msal_admin  # noqa: PLC0415
        if is_msal_admin():
            return "admin"
    except ImportError:
        pass

    # --- 3. Subscription tier -------------------------------------------
    tier = (
        st.session_state.get("_sub_plan_name")
        or st.session_state.get("_auth_plan_tier")
        or "free"
    )
    # Normalise legacy or unexpected values
    if tier not in _TIER_ORDER and tier != "admin":
        tier = "free"
    return tier


def get_user_tier() -> str:
    """Public accessor for the resolved subscription tier string."""
    return _get_current_role()


# ---------------------------------------------------------------------------
# Core permission checks
# ---------------------------------------------------------------------------

def has_permission(permission: str) -> bool:
    """
    Return True when the current user holds *permission*.

    Algorithm:
      - admin and insider_circle hold the "*" wildcard → always True
      - Otherwise walk up _TIER_ORDER from "free" to the user's tier,
        accumulating all permissions granted at each level
    """
    role = _get_current_role()

    # Wildcard roles
    if role in ("admin", "insider_circle"):
        return True

    # Accumulate permissions up to and including the user's tier
    granted: set[str] = set()
    for tier in _TIER_ORDER:
        granted |= PERMISSIONS.get(tier, set())
        if tier == role:
            break  # stop at the user's own tier

    if "*" in granted:
        return True
    return permission in granted


def has_role(role: str) -> bool:
    """
    Return True when the user's effective role equals *role* (exact match).
    Use has_permission() for feature-level checks; use has_role() only when
    you need to verify the specific tier/role label.
    """
    return _get_current_role() == role


def permission_gate(
    permission: str,
    *,
    message: str | None = None,
    show_upgrade_button: bool = True,
) -> None:
    """
    Render a locked-feature placeholder when the user lacks *permission*.

    Call this after an ``if has_permission(...)`` guard:

        if not has_permission("export_data"):
            permission_gate("export_data")
            return
    """
    required_plan = _UPGRADE_LABELS.get(permission, "a higher plan")
    default_msg   = f"🔒 This feature requires **{required_plan}** or above."
    st.info(message or default_msg)
    if show_upgrade_button:
        if st.button(f"Upgrade to {required_plan}", key=f"_rbac_upgrade_{permission}"):
            st.switch_page("pages/pricing.py")  # adjust target page as needed


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def require_permission(permission: str) -> Callable:
    """
    Decorator that renders a permission gate and returns early when the
    decorated function is called without the required permission.

    Example::

        @require_permission("export_data")
        def render_export_section():
            st.download_button(...)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                permission_gate(permission)
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: str) -> Callable:
    """
    Decorator that blocks access unless the user's resolved role exactly
    matches *role*.  Primarily used for "admin"-only pages.

    Example::

        @require_role("admin")
        def render_admin_panel():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not has_role(role):
                st.error("You do not have permission to access this section.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator
