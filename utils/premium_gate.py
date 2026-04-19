# ============================================================
# FILE: utils/premium_gate.py
# PURPOSE: Reusable premium gate UI component for SmartBetPro NBA.
#          Shows a styled upgrade prompt when a non-premium user
#          tries to access a premium feature.
#
# USAGE:
#   from utils.premium_gate import premium_gate
#
#   if not premium_gate("Entry Builder"):
#       st.stop()   # ← Stop rendering the rest of the page
#
# DESIGN:
#   Matches the Quantum Design System (QDS) dark glass aesthetic:
#   dark background, cyan border, orange CTA button.
# ============================================================

import streamlit as st

from utils.auth import is_premium_user
try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
except Exception:
    _PREM_PATH = "/15_%F0%9F%92%8E_Subscription_Level"


# ============================================================
# SECTION: Premium Gate HTML Styling
# ============================================================

_GATE_CSS = """
<style>
/* ── Premium Gate Card ─────────────────────────────────── */
.premium-gate-card {
    background: rgba(14, 20, 40, 0.92);
    border: 1.5px solid rgba(0, 240, 255, 0.35);
    border-radius: 16px;
    padding: 36px 40px;
    text-align: center;
    max-width: 620px;
    margin: 40px auto;
    box-shadow:
        0 0 40px rgba(0, 240, 255, 0.12),
        0 8px 32px rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    position: relative;
    overflow: hidden;
}
.premium-gate-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg,
        #00f0ff 0%, #00ffd5 40%, #ff5e00 80%, #c800ff 100%);
    background-size: 200% 100%;
    animation: gateShimmer 3s ease infinite;
}
@keyframes gateShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
.gate-lock-icon {
    font-size: 3.2rem;
    margin-bottom: 10px;
    filter: drop-shadow(0 0 12px rgba(0,240,255,0.5));
    animation: gatePulse 2.5s ease-in-out infinite;
}
@keyframes gatePulse {
    0%, 100% { transform: scale(1.0); }
    50%       { transform: scale(1.08); }
}
.gate-title {
    font-family: 'Orbitron', 'Courier New', monospace;
    font-size: 1.55rem;
    font-weight: 700;
    color: #00f0ff;
    margin: 0 0 8px;
    text-shadow: 0 0 20px rgba(0,240,255,0.4);
}
.gate-subtitle {
    font-size: 0.95rem;
    color: #a0b4d0;
    margin: 0 0 20px;
    line-height: 1.6;
}
.gate-feature-name {
    display: inline-block;
    background: rgba(255, 94, 0, 0.15);
    border: 1px solid rgba(255, 94, 0, 0.35);
    color: #ff5e00;
    border-radius: 20px;
    padding: 3px 14px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 18px;
    letter-spacing: 0.5px;
}
.gate-benefits {
    text-align: left;
    margin: 16px 0 24px;
    padding: 0;
    list-style: none;
}
.gate-benefits li {
    color: #c8d8ee;
    font-size: 0.88rem;
    padding: 5px 0 5px 28px;
    position: relative;
    line-height: 1.5;
}
.gate-benefits li::before {
    content: '✦';
    position: absolute;
    left: 6px;
    color: #00f0ff;
    font-size: 0.7rem;
    top: 7px;
}
.gate-price-tag {
    color: #00ffd5;
    font-family: 'Orbitron', monospace;
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 6px;
}
.gate-disclaimer {
    font-size: 0.75rem;
    color: #607080;
    margin-top: 14px;
}
</style>
"""


# ============================================================
# SECTION: Premium Gate Component
# ============================================================

def premium_gate(feature_name: str) -> bool:
    """
    Check if the current user has premium access.

    If they do, return True immediately (no UI shown).
    If they don't, display a styled upgrade prompt and return False.

    The calling page should call st.stop() after a False return
    to prevent any premium content from rendering.

    Args:
        feature_name (str): Human-readable name of the feature
                            being gated (e.g., "Entry Builder",
                            "Risk Shield").

    Returns:
        bool: True if user is premium (or Stripe not configured),
              False if user needs to upgrade.

    Example:
        if not premium_gate("Entry Builder"):
            st.stop()
    """
    # ── Check premium status ───────────────────────────────────
    if is_premium_user():
        return True

    # ── Inject gate CSS ────────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    # ── Render the upgrade prompt ─────────────────────────────
    st.markdown(
        f"""
<div class="premium-gate-card">
  <div class="gate-lock-icon">💎</div>
  <p class="gate-title">Premium Feature</p>
  <p class="gate-subtitle">
    Unlock the full power of SmartBetPro NBA AI
    with a premium subscription.
  </p>
  <span class="gate-feature-name">🔒 {feature_name}</span>
  <ul class="gate-benefits">
    <li>Unlimited prop analysis — no caps on your edge hunting</li>
    <li>Full Entry Builder — optimal parlay construction with EV</li>
    <li>Risk Shield — avoid bad bets before they cost you</li>
    <li>Complete Game Reports — AI-generated matchup breakdowns</li>
    <li>Player Simulator — deep Quantum Matrix stat projections</li>
    <li>Bet Tracker — track ROI, model health &amp; auto-resolve</li>
  </ul>
  <p class="gate-price-tag">💳 Affordable Monthly Plan</p>
  <p style="color:#8a9ab8;font-size:0.82rem;margin:0 0 20px;">
    Cancel anytime. No contracts. Powered by Stripe.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

    # ── CTA Button — links to Premium page ────────────────────
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        if st.button(
            "🚀 Upgrade to Premium",
            type="primary",
            use_container_width=True,
            key=f"_gate_upgrade_{feature_name.replace(' ', '_')}",
        ):
            st.switch_page("pages/15_💎_Subscription_Level.py")

    st.markdown(
        f'<p class="gate-disclaimer" style="text-align:center;">'
        f"Already subscribed? "
        f'<a href="{_PREM_PATH}?restore=1" style="color:#00f0ff;">Restore your access →</a>'
        f"</p>",
        unsafe_allow_html=True,
    )

    return False
