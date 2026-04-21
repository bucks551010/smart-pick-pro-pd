# ============================================================
# FILE: utils/tier_gate.py
# PURPOSE: Subscription-tier gating helper for Streamlit pages.
#
# Usage (at the top of any gated page):
#
#   from utils.tier_gate import require_tier
#   if not require_tier():
#       st.stop()
#
# The function auto-detects the current page filename, looks up
# the minimum tier in PAGE_TIER_REQUIREMENTS, and either returns
# True (access granted) or renders a blurred preview overlay with
# an upgrade prompt and returns False.
# ============================================================

import os
import streamlit as st

from utils.auth import (
    get_user_tier,
    tier_has_access,
    get_tier_label,
    PAGE_TIER_REQUIREMENTS,
    TIER_LABELS,
    _TIER_ORDER,
)

try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH
except Exception:
    _PREMIUM_PAGE_PATH = "/15_%F0%9F%92%8E_Subscription_Level"


def _current_page_key() -> str:
    """Extract the page filename stem (e.g. '4_💰_Smart_Money_Bets')
    from Streamlit's internal state or the script path."""
    try:
        # Streamlit >= 1.30 exposes the page script path
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        if ctx and hasattr(ctx, "page_script_hash"):
            pages = st.source_util.get_pages(ctx.main_script_path) if hasattr(st, "source_util") else {}
            for _hash, info in pages.items():
                if _hash == ctx.page_script_hash:
                    return os.path.splitext(info.get("page_name", ""))[0]
    except Exception:
        pass

    # Fallback: parse __file__ of the caller's caller
    import inspect
    for frame_info in inspect.stack():
        fname = os.path.basename(frame_info.filename)
        if fname.startswith(("0_", "1_", "2_", "3_", "4_", "5_",
                             "6_", "7_", "8_", "9_", "10_", "11_",
                             "12_", "13_", "14_", "15_")):
            return os.path.splitext(fname)[0]
    return ""


def require_tier(page_key: str | None = None) -> bool:
    """Check if the current user's tier meets this page's requirement.

    Args:
        page_key: Override the auto-detected page key (e.g. for
                  gating individual *sections* within a page).

    Returns:
        True  → user has access, page should render normally.
        False → access denied, blur overlay + upgrade prompt rendered.
                Caller should call ``st.stop()``.
    """
    if page_key is None:
        page_key = _current_page_key()

    required_tier = PAGE_TIER_REQUIREMENTS.get(page_key)
    if required_tier is None:
        # Page not in the requirements map → open to everyone
        return True

    user_tier = get_user_tier()
    if tier_has_access(user_tier, required_tier):
        return True

    # ── Access denied — render blur overlay + upgrade CTA ──────
    required_label = get_tier_label(required_tier)
    user_label = get_tier_label(user_tier)

    # Which plans unlock this page?
    req_idx = _TIER_ORDER.index(required_tier)
    unlock_tiers = [
        get_tier_label(t) for t in _TIER_ORDER[req_idx:]
    ]

    st.markdown(_BLUR_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="tier-gate-overlay">
          <div class="tier-gate-card">
            <div class="tier-gate-lock">🔒</div>
            <p class="tier-gate-title">
              {required_label} Feature
            </p>
            <p class="tier-gate-subtitle">
              This page requires <strong>{required_label}</strong> or higher.<br>
              You're currently on <strong>{user_label}</strong>.
            </p>
            <div class="tier-gate-plans">
              <p class="tier-gate-plans-label">Available with:</p>
              {''.join(f'<span class="tier-gate-badge">{t}</span>' for t in unlock_tiers)}
            </div>
            <a class="tier-gate-cta" href="{_PREMIUM_PAGE_PATH}">
              ⚡ Upgrade Now
            </a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return False


def blur_section_html(inner_html: str, required_tier_label: str) -> str:
    """Wrap HTML in a blurred teaser with upgrade CTA overlay.

    Use this for sections that should be *visible but unreadable* to
    lower-tier users — the classic "teaser blur" UX pattern.

    Args:
        inner_html: The rendered HTML that should appear blurred.
        required_tier_label: Human-readable name of the minimum tier
                             that unlocks this section (e.g. "Sharp IQ").

    Returns:
        HTML string with blur wrapper + upgrade overlay.
    """
    upgrade_path = _PREMIUM_PAGE_PATH
    return (
        '<div style="position:relative;overflow:hidden;border-radius:12px;margin-bottom:8px;">'
        f'<div style="filter:blur(7px);pointer-events:none;user-select:none;opacity:0.75;">'
        f"{inner_html}"
        "</div>"
        '<div style="position:absolute;inset:0;display:flex;align-items:center;'
        'justify-content:center;background:rgba(10,13,20,0.55);z-index:10;">'
        '<div style="text-align:center;background:rgba(19,25,32,0.96);'
        'border:1px solid rgba(0,212,255,0.18);border-radius:16px;'
        'padding:28px 36px;box-shadow:0 16px 60px rgba(0,0,0,0.55);max-width:380px;">'
        '<div style="font-size:2.2rem;margin-bottom:10px;">🔒</div>'
        f'<p style="color:#00d4ff;font-size:1.1rem;font-weight:800;margin:0 0 6px;">'
        f"{required_tier_label} Feature</p>"
        '<p style="color:#a0b4d0;font-size:0.88rem;margin:0 0 18px;line-height:1.5;">'
        "Upgrade your plan to unlock this section.</p>"
        f'<a href="{upgrade_path}" style="display:inline-block;background:linear-gradient(135deg,#F9C62B,#FF8C00);'
        'color:#0a0e14;font-weight:800;font-size:0.95rem;padding:11px 28px;'
        'border-radius:10px;text-decoration:none;letter-spacing:-0.01em;">'
        "⚡ Upgrade Now</a>"
        "</div></div></div>"
    )


# ── Inline CSS for the blur gate ──────────────────────────────────────
_BLUR_CSS = """
<style>
/* Blur everything rendered AFTER this overlay */
.tier-gate-overlay {
    position: fixed;
    inset: 0;
    z-index: 9998;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(10, 14, 20, 0.82);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}
.tier-gate-card {
    background: linear-gradient(135deg, rgba(20, 27, 45, 0.97), rgba(15, 20, 35, 0.97));
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 48px 40px 40px;
    max-width: 480px;
    width: 90vw;
    text-align: center;
    box-shadow: 0 24px 80px rgba(0,0,0,0.6);
}
.tier-gate-lock {
    font-size: 3.2rem;
    margin-bottom: 12px;
}
.tier-gate-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #F9C62B;
    margin: 0 0 8px;
    letter-spacing: -0.02em;
}
.tier-gate-subtitle {
    font-size: 0.95rem;
    color: #A0B4D0;
    margin: 0 0 24px;
    line-height: 1.55;
}
.tier-gate-plans {
    margin-bottom: 28px;
}
.tier-gate-plans-label {
    font-size: 0.78rem;
    color: #667;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
}
.tier-gate-badge {
    display: inline-block;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 6px 14px;
    margin: 0 4px 6px;
    font-size: 0.85rem;
    color: #EEF0F6;
    font-weight: 600;
}
.tier-gate-cta {
    display: inline-block;
    background: linear-gradient(135deg, #F9C62B, #FF8C00);
    color: #0A0E14 !important;
    font-weight: 800;
    font-size: 1.05rem;
    padding: 14px 40px;
    border-radius: 12px;
    text-decoration: none !important;
    letter-spacing: -0.01em;
    transition: transform 0.15s, box-shadow 0.15s;
    box-shadow: 0 4px 20px rgba(249,198,43,0.3);
}
.tier-gate-cta:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(249,198,43,0.45);
}
</style>
"""
