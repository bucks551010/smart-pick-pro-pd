# ============================================================
# FILE: pages/login.py
# PURPOSE: Premium login/signup portal — smartpickpro.ai/login
#          Split-panel immersive auth experience.
#          Authenticated visitors are immediately forwarded to the app.
# URL:     smartpickpro.ai/login
# ============================================================

import streamlit as st

st.set_page_config(
    page_title="Smart Pick Pro — Sign In",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── GA4 ───────────────────────────────────────────────────────
try:
    from utils.analytics import inject_ga4, track_page_view
    inject_ga4()
    track_page_view("Login")
except Exception:
    pass

# ── Quick session restore & redirect ─────────────────────────
from utils.auth_gate import (
    is_logged_in, require_login,
    _GATE_CSS, _get_logo_b64,
    _authenticate_user, _set_logged_in,
    _clear_failed_logins, _record_failed_login,
    _check_login_lockout, _valid_email,
    _generate_reset_token, _verify_reset_token,
    _reset_user_password, _valid_password,
    _create_user, _email_exists,
)

if is_logged_in():
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

# Try cookie / localStorage session restore silently via require_login()
# when no ?auth= param is set — this handles F5 reloads without showing
# the login page flicker.  We skip this if we want to force the portal.
_current_auth = st.query_params.get("auth", "")
if _current_auth not in ("login", "signup", ""):
    # Delegate unusual modes (verify / reset / verified) to require_login()
    if require_login():
        st.switch_page("Smart_Picks_Pro_Home.py")
        st.stop()
    st.stop()

# ── Base CSS from auth_gate (orbs, animations, form styles) ──
st.markdown(_GATE_CSS, unsafe_allow_html=True)

# ── Additional premium CSS for the split-panel layout ────────
st.markdown(r"""
<style>
/* ── Hide all default Streamlit chrome ──────────────────────── */
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton,
footer { display: none !important; }

/* ── Full-bleed page shell ───────────────────────────────────── */
html, body, .stApp {
    background: #03060E !important;
    overflow-x: hidden !important;
}
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 0 !important;
    max-width: 100% !important;
    margin: 0 !important;
}

/* ── Split portal wrapper ────────────────────────────────────── */
.spp-portal {
    display: grid;
    grid-template-columns: 1fr 520px;
    min-height: 100vh;
    position: relative;
    z-index: 10;
}

/* ── LEFT — hero panel ───────────────────────────────────────── */
.spp-hero {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px 64px 60px 72px;
    position: relative;
    overflow: hidden;
}
.spp-hero::after {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 1px; height: 100%;
    background: linear-gradient(180deg,
        transparent 0%,
        rgba(0,213,89,0.15) 30%,
        rgba(0,213,89,0.25) 50%,
        rgba(0,213,89,0.15) 70%,
        transparent 100%);
}

/* Logo / wordmark */
.spp-hero-logo {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 56px;
}
.spp-hero-logo img {
    width: 52px; height: 52px;
    object-fit: contain;
    filter: drop-shadow(0 0 16px rgba(0,213,89,0.4));
}
.spp-hero-wordmark {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.35rem; font-weight: 800;
    letter-spacing: -0.04em; color: #fff;
}
.spp-hero-wordmark .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Main headline */
.spp-hero-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 4rem; font-weight: 800;
    line-height: 0.97; letter-spacing: -0.055em;
    color: #fff; text-transform: uppercase;
    margin: 0 0 28px;
}
.spp-hero-headline .em {
    display: block;
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 40%, #c084fc 80%);
    background-size: 300% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 5s ease infinite;
}

/* Sub-copy */
.spp-hero-sub {
    font-size: 1rem;
    color: rgba(255,255,255,0.45);
    line-height: 1.75;
    max-width: 460px;
    margin-bottom: 44px;
}
.spp-hero-sub strong { color: rgba(255,255,255,0.82); font-weight: 700; }

/* 4 proof stats in a 2×2 grid */
.spp-proof-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    max-width: 440px;
    margin-bottom: 44px;
}
.spp-proof-card {
    background: linear-gradient(168deg, rgba(10,16,30,0.97), rgba(7,11,22,0.99));
    border: 1px solid rgba(0,213,89,0.1);
    border-top: 1px solid rgba(0,213,89,0.2);
    border-radius: 14px;
    padding: 20px 18px;
    position: relative; overflow: hidden;
    transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
}
.spp-proof-card:hover {
    border-color: rgba(0,213,89,0.3);
    transform: translateY(-4px);
    box-shadow: 0 16px 40px rgba(0,0,0,0.4), 0 0 30px rgba(0,213,89,0.07);
}
.spp-proof-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.5), transparent);
}
.spp-proof-card:nth-child(2)::before { background: linear-gradient(90deg, transparent, rgba(45,158,255,0.4), transparent); }
.spp-proof-card:nth-child(3)::before { background: linear-gradient(90deg, transparent, rgba(192,132,252,0.35), transparent); }
.spp-proof-card:nth-child(4)::before { background: linear-gradient(90deg, transparent, rgba(249,198,43,0.35), transparent); }
.spp-proof-big {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.6rem; font-weight: 800;
    letter-spacing: -0.04em; line-height: 1;
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.spp-proof-card:nth-child(2) .spp-proof-big { background: linear-gradient(135deg, #2D9EFF, #c084fc); -webkit-background-clip: text; background-clip: text; }
.spp-proof-card:nth-child(3) .spp-proof-big { background: linear-gradient(135deg, #c084fc, #F9C62B); -webkit-background-clip: text; background-clip: text; }
.spp-proof-card:nth-child(4) .spp-proof-big { background: linear-gradient(135deg, #F9C62B, #00D559); -webkit-background-clip: text; background-clip: text; }
.spp-proof-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem; font-weight: 700;
    color: rgba(255,255,255,0.45);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-top: 6px;
}
.spp-proof-sub {
    font-size: 0.58rem;
    color: rgba(255,255,255,0.2);
    margin-top: 3px; line-height: 1.4;
}

/* Testimonial */
.spp-testimonial {
    background: linear-gradient(168deg, rgba(0,213,89,0.05), rgba(45,158,255,0.03));
    border: 1px solid rgba(0,213,89,0.12);
    border-left: 3px solid #00D559;
    border-radius: 0 14px 14px 0;
    padding: 18px 22px;
    max-width: 440px;
}
.spp-testimonial-text {
    font-size: 0.88rem;
    color: rgba(255,255,255,0.65);
    font-style: italic;
    line-height: 1.7;
    margin: 0 0 10px;
}
.spp-testimonial-text strong { color: rgba(255,255,255,0.9); font-style: normal; }
.spp-testimonial-author {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; font-weight: 700;
    color: #00D559;
    text-transform: uppercase; letter-spacing: 0.08em;
}
.spp-testimonial-stars {
    color: #F9C62B; font-size: 0.68rem;
    margin-left: 8px; letter-spacing: 1px;
}

/* ── RIGHT — form panel ──────────────────────────────────────── */
.spp-form-panel {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 40px 40px 40px;
    background: rgba(255,255,255,0.012);
    backdrop-filter: blur(40px);
    -webkit-backdrop-filter: blur(40px);
    position: relative;
    min-height: 100vh;
    overflow-y: auto;
}
.spp-form-panel::before {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 0%,
        rgba(0,213,89,0.07) 0%, transparent 55%);
    pointer-events: none;
}
.spp-form-inner {
    width: 100%;
    max-width: 400px;
    position: relative; z-index: 2;
}

/* Logo at top of form panel */
.spp-form-logo {
    text-align: center;
    margin-bottom: 32px;
}
.spp-form-logo img {
    width: 68px; height: 68px;
    object-fit: contain;
    animation: agLogoGlow 4s ease-in-out infinite;
}
.spp-form-logo-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.15rem; font-weight: 800;
    letter-spacing: -0.04em; color: #fff;
    margin-top: 8px;
}
.spp-form-logo-title .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Headline + sub above form */
.spp-form-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.15rem; font-weight: 800;
    color: #fff; text-align: center;
    letter-spacing: -0.04em;
    text-transform: uppercase;
    margin: 0 0 6px;
    line-height: 1.05;
}
.spp-form-sub {
    font-size: 0.82rem;
    color: rgba(255,255,255,0.38);
    text-align: center;
    margin: 0 0 28px;
    line-height: 1.55;
}

/* AI badge above headline */
.spp-ai-badge {
    display: inline-flex; align-items: center; gap: 7px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem; font-weight: 800;
    color: #00D559;
    background: rgba(0,213,89,0.06);
    border: 1px solid rgba(0,213,89,0.2);
    padding: 6px 16px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 14px;
    position: relative; overflow: hidden;
}
.spp-ai-badge::after {
    content: '';
    position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.12), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
.spp-ai-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #00D559;
    box-shadow: 0 0 8px rgba(0,213,89,0.5);
    animation: agLivePulse 2s ease-in-out infinite;
}

/* Mode tabs */
.spp-mode-tabs {
    display: flex;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 4px;
    margin-bottom: 24px;
}
.spp-mode-tab {
    flex: 1; text-align: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.82rem; font-weight: 700;
    padding: 10px 0;
    border-radius: 9px;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s;
    color: rgba(255,255,255,0.3);
    border: 1px solid transparent;
}
.spp-mode-tab.active {
    background: rgba(0,213,89,0.08);
    border-color: rgba(0,213,89,0.2);
    color: #fff;
}
.spp-mode-tab:hover:not(.active) {
    color: rgba(255,255,255,0.6);
    background: rgba(255,255,255,0.02);
}

/* Back to home link */
.spp-back-link {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem; font-weight: 600;
    color: rgba(255,255,255,0.25);
    text-decoration: none;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 100px;
    padding: 5px 14px;
    background: rgba(255,255,255,0.02);
    transition: all 0.2s;
    margin-bottom: 28px;
}
.spp-back-link:hover {
    color: rgba(255,255,255,0.5);
    border-color: rgba(255,255,255,0.12);
}

/* Trust strip at bottom */
.spp-trust-strip {
    display: flex; justify-content: center; gap: 18px;
    flex-wrap: wrap;
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.04);
}
.spp-trust-item {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; font-weight: 600;
    color: rgba(255,255,255,0.18);
    display: flex; align-items: center; gap: 5px;
}

/* Responsive: hide hero panel on narrow screens */
@media (max-width: 960px) {
    .spp-portal {
        grid-template-columns: 1fr;
    }
    .spp-hero { display: none; }
    .spp-form-panel {
        padding: 36px 24px;
        min-height: 100vh;
        background: transparent;
    }
}
@media (max-width: 520px) {
    .spp-form-panel { padding: 28px 16px; }
    .spp-form-headline { font-size: 1.7rem; }
}

/* ── Streamlit form inside the panel ─────────────────────────── */
.spp-form-inner [data-testid="stForm"] {
    background: linear-gradient(168deg, rgba(10,16,30,0.98), rgba(7,11,22,0.99)) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-top: 1px solid rgba(0,213,89,0.22) !important;
    border-radius: 20px !important;
    padding: 32px 28px 28px !important;
    box-shadow:
        0 24px 80px rgba(0,0,0,0.6),
        0 0 0 1px rgba(0,213,89,0.04) inset,
        0 0 80px rgba(0,213,89,0.04) !important;
    backdrop-filter: blur(40px) !important;
}
.spp-form-inner [data-testid="stForm"]::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg,
        transparent,
        rgba(0,213,89,0.4),
        rgba(45,158,255,0.3),
        transparent);
    border-radius: 20px 20px 0 0;
}
/* Inputs inside the card */
.spp-form-inner input[type="text"],
.spp-form-inner input[type="email"],
.spp-form-inner input[type="password"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    color: #fff !important;
    font-size: 0.92rem !important;
    padding: 14px 16px !important;
    caret-color: #00D559 !important;
    transition: all 0.2s !important;
}
.spp-form-inner input:focus {
    border-color: rgba(0,213,89,0.45) !important;
    box-shadow: 0 0 0 3px rgba(0,213,89,0.1) !important;
    background: rgba(255,255,255,0.06) !important;
}
.spp-form-inner label {
    color: rgba(255,255,255,0.4) !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
/* Submit button */
.spp-form-inner button[kind="primaryFormSubmit"],
.spp-form-inner button[type="submit"] {
    background: linear-gradient(135deg, #00E865 0%, #00D559 45%, #00B74D 100%) !important;
    color: #020C07 !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    border-radius: 12px !important;
    padding: 16px 0 !important;
    margin-top: 10px !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    box-shadow:
        0 0 32px rgba(0,213,89,0.4),
        0 4px 20px rgba(0,213,89,0.2),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
    transition: all 0.25s cubic-bezier(0.16,1,0.3,1) !important;
}
.spp-form-inner button[kind="primaryFormSubmit"]:hover,
.spp-form-inner button[type="submit"]:hover {
    transform: translateY(-2px) !important;
    box-shadow:
        0 0 52px rgba(0,213,89,0.6),
        0 8px 32px rgba(0,213,89,0.3),
        inset 0 1px 0 rgba(255,255,255,0.22) !important;
    background: linear-gradient(135deg, #00FF75 0%, #00E865 45%, #00C04B 100%) !important;
}
/* Secondary buttons (forgot password, back) */
.spp-form-inner button[kind="secondary"] {
    color: rgba(255,255,255,0.35) !important;
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.spp-form-inner button[kind="secondary"]:hover {
    color: rgba(255,255,255,0.6) !important;
    border-color: rgba(255,255,255,0.12) !important;
    background: rgba(255,255,255,0.02) !important;
}
/* Horizontal rule inside forgot pw */
.spp-form-inner hr {
    border-color: rgba(255,255,255,0.05) !important;
    margin: 16px 0 !important;
}
/* Alert/error/success messages */
.spp-form-inner [data-testid="stAlert"] {
    border-radius: 10px !important;
    font-size: 0.8rem !important;
}
</style>
""", unsafe_allow_html=True)

# ── Determine current mode (login vs signup) ──────────────────
_mode = st.query_params.get("auth", "login")
if _mode not in ("login", "signup"):
    _mode = "login"

_other_mode  = "signup" if _mode == "login" else "login"
_other_label = "Create Account" if _mode == "login" else "Sign In"

# ── Render background orbs ────────────────────────────────────
st.markdown("""
<div class="ag-bg">
  <div class="ag-orb ag-orb-1"></div>
  <div class="ag-orb ag-orb-2"></div>
  <div class="ag-orb ag-orb-3"></div>
  <div class="ag-pulse-ring"></div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 1 — TICKER BAR + NAVBAR
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Ticker bar ──────────────────────────────────────────────── */
.lp-ticker {
    position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
    height: 34px;
    background: rgba(2,6,14,0.96);
    border-bottom: 1px solid rgba(255,255,255,0.05);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    display: flex; align-items: center;
    overflow: hidden;
}
.lp-ticker-track {
    display: flex; align-items: center;
    gap: 0;
    animation: tickerScroll 38s linear infinite;
    white-space: nowrap;
    flex-shrink: 0;
}
@keyframes tickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.lp-ticker-item {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 28px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; font-weight: 600;
    color: rgba(255,255,255,0.35);
    border-right: 1px solid rgba(255,255,255,0.06);
}
.lp-ticker-item:last-child { border-right: none; }
.lp-ticker-label { color: rgba(255,255,255,0.22); text-transform: uppercase; letter-spacing: .08em; }
.lp-ticker-val   { font-weight: 800; letter-spacing: -.02em; }
.lp-ticker-val.green  { color: #00D559; }
.lp-ticker-val.gold   { color: #F9C62B; }
.lp-ticker-val.blue   { color: #2D9EFF; }
.lp-ticker-val.purple { color: #c084fc; }
.lp-ticker-live {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(0,213,89,0.1); border: 1px solid rgba(0,213,89,0.25);
    border-radius: 100px; padding: 2px 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.56rem; font-weight: 800;
    color: #00D559; text-transform: uppercase; letter-spacing: .1em;
}
.lp-ticker-live-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: #00D559;
    box-shadow: 0 0 6px rgba(0,213,89,0.6);
    animation: agLivePulse 2s ease-in-out infinite;
}

/* ── Navbar ──────────────────────────────────────────────────── */
.lp-nav {
    position: fixed; top: 34px; left: 0; right: 0; z-index: 9998;
    height: 64px;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 40px;
    background: rgba(2,6,14,0.88);
    border-bottom: 1px solid rgba(255,255,255,0.06);
    backdrop-filter: blur(32px);
    -webkit-backdrop-filter: blur(32px);
    transition: background 0.3s;
}
.lp-nav-logo {
    display: flex; align-items: center; gap: 10px;
    text-decoration: none;
    flex-shrink: 0;
}
.lp-nav-logo-icon {
    width: 34px; height: 34px; border-radius: 8px;
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
    box-shadow: 0 0 18px rgba(0,213,89,0.3);
}
.lp-nav-logo-text {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem; font-weight: 800;
    color: #fff; letter-spacing: -.04em;
}
.lp-nav-logo-text .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.lp-nav-links {
    display: flex; align-items: center; gap: 2px;
    list-style: none; margin: 0; padding: 0;
}
.lp-nav-links a {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem; font-weight: 600;
    color: rgba(255,255,255,0.4);
    text-decoration: none;
    padding: 7px 14px; border-radius: 8px;
    transition: all 0.2s;
}
.lp-nav-links a:hover {
    color: #fff;
    background: rgba(255,255,255,0.05);
}
.lp-nav-ctas {
    display: flex; align-items: center; gap: 10px;
    flex-shrink: 0;
}
.lp-nav-login {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem; font-weight: 700;
    color: rgba(255,255,255,0.5);
    text-decoration: none;
    padding: 8px 18px;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 100px;
    transition: all 0.2s;
}
.lp-nav-login:hover {
    color: #fff;
    border-color: rgba(255,255,255,0.25);
    background: rgba(255,255,255,0.04);
}
.lp-nav-signup {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.8rem; font-weight: 800;
    color: #020C07;
    text-decoration: none;
    padding: 9px 22px;
    border-radius: 100px;
    background: linear-gradient(135deg, #00E865, #00D559);
    border: 1px solid rgba(255,255,255,0.15);
    box-shadow: 0 0 22px rgba(0,213,89,0.35), inset 0 1px 0 rgba(255,255,255,0.2);
    letter-spacing: .03em;
    transition: all 0.2s cubic-bezier(0.16,1,0.3,1);
    position: relative; overflow: hidden;
}
.lp-nav-signup::after {
    content: '';
    position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
.lp-nav-signup:hover {
    transform: translateY(-1px);
    box-shadow: 0 0 36px rgba(0,213,89,0.55), inset 0 1px 0 rgba(255,255,255,0.2);
}

/* ── Page offset so content clears fixed ticker+nav ─────────── */
.lp-page-offset {
    height: 98px; /* 34px ticker + 64px nav */
}

/* Hide on mobile */
@media (max-width: 760px) {
    .lp-nav-links { display: none; }
    .lp-nav { padding: 0 20px; }
}
@media (max-width: 480px) {
    .lp-nav-login { display: none; }
}
</style>
""", unsafe_allow_html=True)

# Ticker stats row (doubled for seamless loop)
_TICKER_ITEMS = """
  <span class="lp-ticker-item"><span class="lp-ticker-label">Props Scanned</span><span class="lp-ticker-val green">347</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Models Active</span><span class="lp-ticker-val blue">6/6</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">SAFE Score Avg</span><span class="lp-ticker-val gold">71.2</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Edge Detected</span><span class="lp-ticker-val green">+4.8%</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Bankroll ROI</span><span class="lp-ticker-val green">+18.3%</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">CLV Capture</span><span class="lp-ticker-val purple">92%</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Users Online</span><span class="lp-ticker-val blue">1,247</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-live"><span class="lp-ticker-live-dot"></span>LIVE</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Hit Rate</span><span class="lp-ticker-val green">62.4%</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Picks Tonight</span><span class="lp-ticker-val gold">23</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Avg Confidence</span><span class="lp-ticker-val blue">78.9</span></span>
  <span class="lp-ticker-item"><span class="lp-ticker-label">Sharps Following</span><span class="lp-ticker-val purple">2,418</span></span>
"""

st.markdown(f"""
<div class="lp-ticker" role="marquee" aria-label="Live platform stats">
  <div class="lp-ticker-track">
    {_TICKER_ITEMS}{_TICKER_ITEMS}
  </div>
</div>

<nav class="lp-nav" role="navigation" aria-label="Main navigation">
  <a class="lp-nav-logo" href="#">
    <div class="lp-nav-logo-icon">⚡</div>
    <span class="lp-nav-logo-text">Smart<span class="em">Pick</span>Pro</span>
  </a>

  <ul class="lp-nav-links">
    <li><a href="#lp-how">How It Works</a></li>
    <li><a href="#lp-features">Features</a></li>
    <li><a href="#lp-picks">Picks</a></li>
    <li><a href="#lp-pricing">Pricing</a></li>
    <li><a href="#lp-faq">FAQ</a></li>
  </ul>

  <div class="lp-nav-ctas">
    <a class="lp-nav-login"  href="?auth=login">🔒 Log In</a>
    <a class="lp-nav-signup" href="?auth=signup">Sign Up Free</a>
  </div>
</nav>

<!-- Push page content below fixed ticker+nav -->
<div class="lp-page-offset"></div>
""", unsafe_allow_html=True)

# ── Get logo ──────────────────────────────────────────────────
_logo_b64 = _get_logo_b64()
_logo_img_hero = (
    f'<img src="data:image/png;base64,{_logo_b64}" alt="SPP Logo">'
    if _logo_b64 else '<span style="font-size:2.2rem">⚡</span>'
)
_logo_img_form = (
    f'<img src="data:image/png;base64,{_logo_b64}" alt="SPP Logo">'
    if _logo_b64 else '<span style="font-size:2.6rem">⚡</span>'
)

# ════════════════════════════════════════════════════════════
# PHASE 2 — FULL-SCREEN CINEMATIC HERO
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Hero section ────────────────────────────────────────────── */
.lp-hero {
    position: relative;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 80px 24px 100px;
    overflow: hidden;
}

/* Animated grid mesh background */
.lp-hero::before {
    content: '';
    position: absolute; inset: 0;
    background-image:
        linear-gradient(rgba(0,213,89,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,213,89,0.04) 1px, transparent 1px);
    background-size: 60px 60px;
    mask-image: radial-gradient(ellipse 80% 80% at 50% 50%,
        black 0%, transparent 100%);
    -webkit-mask-image: radial-gradient(ellipse 80% 80% at 50% 50%,
        black 0%, transparent 100%);
    animation: heroGridPulse 8s ease-in-out infinite;
}
@keyframes heroGridPulse {
    0%,100% { opacity: 0.6; }
    50%      { opacity: 1.0; }
}

/* Radial green glow centre */
.lp-hero::after {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(ellipse 70% 60% at 50% 45%,
        rgba(0,213,89,0.09) 0%,
        rgba(45,158,255,0.05) 35%,
        transparent 70%);
    pointer-events: none;
}

/* Floating orbs behind hero */
.lp-hero-orb {
    position: absolute; border-radius: 50%;
    filter: blur(80px); pointer-events: none;
}
.lp-hero-orb-1 {
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(0,213,89,0.12), transparent 70%);
    top: -120px; left: 50%;
    transform: translateX(-50%);
    animation: heroOrbFloat1 14s ease-in-out infinite;
}
.lp-hero-orb-2 {
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(45,158,255,0.1), transparent 70%);
    bottom: -80px; right: 5%;
    animation: heroOrbFloat2 18s ease-in-out infinite;
}
.lp-hero-orb-3 {
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(192,132,252,0.07), transparent 70%);
    top: 30%; left: -60px;
    animation: heroOrbFloat1 22s ease-in-out infinite reverse;
}
@keyframes heroOrbFloat1 {
    0%,100% { transform: translateX(-50%) translateY(0px); }
    50%      { transform: translateX(-50%) translateY(-30px); }
}
@keyframes heroOrbFloat2 {
    0%,100% { transform: translateY(0px); }
    50%      { transform: translateY(-20px); }
}

/* Logo badge above headline */
.lp-hero-logo-wrap {
    position: relative; z-index: 2;
    display: flex; flex-direction: column; align-items: center;
    margin-bottom: 36px;
    animation: heroFadeUp 0.8s cubic-bezier(0.16,1,0.3,1) both;
}
.lp-hero-logo-img {
    width: 110px; height: 110px;
    object-fit: contain;
    filter: drop-shadow(0 0 32px rgba(0,213,89,0.5))
            drop-shadow(0 0 60px rgba(45,158,255,0.2));
    animation: heroLogoPulse 4s ease-in-out infinite;
}
@keyframes heroLogoPulse {
    0%,100% { filter: drop-shadow(0 0 28px rgba(0,213,89,0.4)) drop-shadow(0 0 50px rgba(45,158,255,0.15)); }
    50%      { filter: drop-shadow(0 0 48px rgba(0,213,89,0.7)) drop-shadow(0 0 80px rgba(45,158,255,0.3)); }
}

/* Neural Engine badge */
.lp-hero-badge {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; font-weight: 800;
    color: #00D559;
    background: rgba(0,213,89,0.06);
    border: 1px solid rgba(0,213,89,0.22);
    padding: 8px 20px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 24px;
    position: relative; overflow: hidden;
    z-index: 2;
    animation: heroFadeUp 0.9s cubic-bezier(0.16,1,0.3,1) 0.1s both;
}
.lp-hero-badge::after {
    content: '';
    position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.14), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
.lp-hero-badge-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #00D559;
    box-shadow: 0 0 10px rgba(0,213,89,0.7);
    animation: agLivePulse 2s ease-in-out infinite;
}

/* Main headline */
.lp-hero-h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(3.2rem, 8vw, 7.5rem);
    font-weight: 900;
    line-height: 0.92;
    letter-spacing: -0.06em;
    color: #fff;
    text-transform: uppercase;
    margin: 0 0 0;
    position: relative; z-index: 2;
    animation: heroFadeUp 0.9s cubic-bezier(0.16,1,0.3,1) 0.2s both;
}
.lp-hero-h1 .line-problem {
    display: block;
    background: linear-gradient(180deg, #ffffff 0%, rgba(255,255,255,0.75) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.lp-hero-h1 .line-us {
    display: block;
    background: linear-gradient(135deg, #00FF85 0%, #00D559 30%, #2D9EFF 60%, #c084fc 90%);
    background-size: 300% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 5s ease infinite;
    padding-bottom: 6px;
}

/* Sub-copy */
.lp-hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: clamp(0.95rem, 2vw, 1.15rem);
    color: rgba(255,255,255,0.42);
    line-height: 1.75;
    max-width: 560px;
    margin: 28px auto 44px;
    position: relative; z-index: 2;
    animation: heroFadeUp 0.9s cubic-bezier(0.16,1,0.3,1) 0.35s both;
}
.lp-hero-sub strong { color: rgba(255,255,255,0.8); font-weight: 700; }

/* CTA buttons */
.lp-hero-ctas {
    display: flex; align-items: center; justify-content: center;
    gap: 14px; flex-wrap: wrap;
    position: relative; z-index: 2;
    animation: heroFadeUp 0.9s cubic-bezier(0.16,1,0.3,1) 0.45s both;
}
.lp-cta-primary {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem; font-weight: 800;
    color: #020C07;
    text-decoration: none;
    padding: 16px 36px; border-radius: 100px;
    background: linear-gradient(135deg, #00FF85 0%, #00D559 50%, #00B74D 100%);
    border: 1px solid rgba(255,255,255,0.18);
    box-shadow:
        0 0 40px rgba(0,213,89,0.5),
        0 8px 32px rgba(0,213,89,0.25),
        inset 0 1px 0 rgba(255,255,255,0.25);
    letter-spacing: 0.02em;
    transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
    position: relative; overflow: hidden;
}
.lp-cta-primary::after {
    content: '';
    position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
.lp-cta-primary:hover {
    transform: translateY(-3px) scale(1.02);
    box-shadow:
        0 0 60px rgba(0,213,89,0.7),
        0 12px 48px rgba(0,213,89,0.35),
        inset 0 1px 0 rgba(255,255,255,0.25);
}
.lp-cta-secondary {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.95rem; font-weight: 700;
    color: rgba(255,255,255,0.7);
    text-decoration: none;
    padding: 15px 32px; border-radius: 100px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.12);
    letter-spacing: 0.02em;
    transition: all 0.25s;
}
.lp-cta-secondary:hover {
    color: #fff;
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.22);
    transform: translateY(-2px);
}

/* Scroll indicator */
.lp-hero-scroll {
    position: absolute; bottom: 32px; left: 50%;
    transform: translateX(-50%);
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    z-index: 2;
    animation: heroFadeUp 1s cubic-bezier(0.16,1,0.3,1) 0.7s both;
}
.lp-hero-scroll-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem; font-weight: 700;
    color: rgba(255,255,255,0.18);
    text-transform: uppercase; letter-spacing: 0.12em;
}
.lp-hero-scroll-line {
    width: 1px; height: 40px;
    background: linear-gradient(180deg, rgba(0,213,89,0.5), transparent);
    animation: scrollLinePulse 2s ease-in-out infinite;
}
@keyframes scrollLinePulse {
    0%,100% { opacity: 0.4; transform: scaleY(1); }
    50%      { opacity: 1;   transform: scaleY(1.1); }
}

/* Entry animation */
@keyframes heroFadeUp {
    from { opacity: 0; transform: translateY(28px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Platform logos strip */
.lp-hero-platforms {
    display: flex; align-items: center; justify-content: center;
    gap: 6px; flex-wrap: wrap;
    margin-top: 44px;
    position: relative; z-index: 2;
    animation: heroFadeUp 0.9s cubic-bezier(0.16,1,0.3,1) 0.55s both;
}
.lp-hero-platform-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; font-weight: 700;
    color: rgba(255,255,255,0.2);
    text-transform: uppercase; letter-spacing: .1em;
    margin-right: 6px;
}
.lp-hero-platform-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; font-weight: 800;
    padding: 5px 14px; border-radius: 100px;
    letter-spacing: .06em;
    text-transform: uppercase;
}
.lp-hp-pp   { color: #00D559; background: rgba(0,213,89,0.08);   border: 1px solid rgba(0,213,89,0.2);   }
.lp-hp-dk   { color: #2D9EFF; background: rgba(45,158,255,0.08); border: 1px solid rgba(45,158,255,0.2); }
.lp-hp-ud   { color: #F9C62B; background: rgba(249,198,43,0.08); border: 1px solid rgba(249,198,43,0.2); }
.lp-hp-pa   { color: #c084fc; background: rgba(192,132,252,0.08);border: 1px solid rgba(192,132,252,0.2);}
</style>
""", unsafe_allow_html=True)

_logo_hero_big = (
    f'<img class="lp-hero-logo-img" src="data:image/png;base64,{_logo_b64}" alt="Smart Pick Pro">'
    if _logo_b64 else '<span style="font-size:5rem;line-height:1;">⚡</span>'
)

# ── Phase 1 v2: Aurora Hero Enhancement ─────────────────────
st.markdown("""
<style>
/* ── Enhanced orbs: bigger, more vivid ─────────────────────── */
.lp-hero-orb-1 {
    background: radial-gradient(circle,
        rgba(0,255,133,0.22) 0%,
        rgba(0,213,89,0.10) 30%,
        transparent 65%) !important;
    width: 900px !important; height: 900px !important;
    filter: blur(52px) !important;
}
.lp-hero-orb-2 {
    background: radial-gradient(circle,
        rgba(45,158,255,0.2) 0%,
        rgba(0,80,255,0.07) 30%,
        transparent 65%) !important;
    width: 720px !important; height: 720px !important;
    filter: blur(62px) !important;
}
.lp-hero-orb-3 {
    background: radial-gradient(circle,
        rgba(192,132,252,0.18) 0%,
        transparent 65%) !important;
    width: 560px !important; height: 560px !important;
    filter: blur(55px) !important;
}

/* ── Scan line ──────────────────────────────────────────────── */
.lp-hero-scan {
    position: absolute;
    width: 100%; height: 2px;
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(0,213,89,0.5) 25%,
        rgba(45,158,255,0.4) 50%,
        rgba(0,213,89,0.5) 75%,
        transparent 100%);
    top: 0; left: 0;
    animation: heroScanMove 14s linear infinite;
    z-index: 1; pointer-events: none;
    filter: blur(1px);
}
@keyframes heroScanMove {
    0%   { top: 0%;   opacity: 0; }
    4%   { opacity: 1; }
    96%  { opacity: 0.5; }
    100% { top: 100%; opacity: 0; }
}

/* ── Corner bracket decorations ────────────────────────────── */
.lp-hero-corner {
    position: absolute;
    width: 52px; height: 52px;
    border-color: rgba(0,213,89,0.22);
    border-style: solid;
    z-index: 2; pointer-events: none;
}
.lp-hero-corner-tl { top: 28px; left: 28px;  border-width: 1px 0 0 1px; }
.lp-hero-corner-tr { top: 28px; right: 28px; border-width: 1px 1px 0 0; }
.lp-hero-corner-bl { bottom: 28px; left: 28px;  border-width: 0 0 1px 1px; }
.lp-hero-corner-br { bottom: 28px; right: 28px; border-width: 0 1px 1px 0; }

/* ── Floating glass stat cards ──────────────────────────────── */
.lp-hero-stat {
    position: absolute;
    background: rgba(8,18,12,0.72);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 14px 20px;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    z-index: 3;
    min-width: 122px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
}
.lp-hero-stat-row {
    display: flex; align-items: center; gap: 7px;
    margin-bottom: 7px;
}
.lp-hero-stat-live {
    width: 6px; height: 6px; border-radius: 50%;
    background: currentColor; flex-shrink: 0;
    animation: agLivePulse 2s ease-in-out infinite;
}
.lp-hero-stat-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.5rem; font-weight: 800;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase; letter-spacing: .11em;
}
.lp-hero-stat-val {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.55rem; font-weight: 900;
    letter-spacing: -0.05em;
    line-height: 1;
    color: currentColor;
    text-shadow: 0 0 30px currentColor;
}
/* Card 1 — green (Hit Rate) — top-left */
.lp-hs-1 {
    top: 22%; left: 3%;
    color: #00D559;
    border-color: rgba(0,213,89,0.22);
    box-shadow: 0 0 40px rgba(0,213,89,0.08), 0 8px 32px rgba(0,0,0,0.4);
    animation: heroFadeUp 0.9s 0.6s both, lp-float-a 7s ease-in-out infinite;
}
/* Card 2 — blue (ROI) — top-right */
.lp-hs-2 {
    top: 22%; right: 3%;
    color: #2D9EFF;
    border-color: rgba(45,158,255,0.22);
    box-shadow: 0 0 40px rgba(45,158,255,0.08), 0 8px 32px rgba(0,0,0,0.4);
    animation: heroFadeUp 0.9s 0.7s both, lp-float-b 8s ease-in-out infinite;
}
/* Card 3 — gold (Props) — bottom-left */
.lp-hs-3 {
    bottom: 28%; left: 3%;
    color: #F9C62B;
    border-color: rgba(249,198,43,0.22);
    box-shadow: 0 0 40px rgba(249,198,43,0.08), 0 8px 32px rgba(0,0,0,0.4);
    animation: heroFadeUp 0.9s 0.8s both, lp-float-a 9s ease-in-out infinite reverse;
}
/* Card 4 — purple (Members) — bottom-right */
.lp-hs-4 {
    bottom: 28%; right: 3%;
    color: #c084fc;
    border-color: rgba(192,132,252,0.22);
    box-shadow: 0 0 40px rgba(192,132,252,0.08), 0 8px 32px rgba(0,0,0,0.4);
    animation: heroFadeUp 0.9s 0.9s both, lp-float-b 10s ease-in-out infinite reverse;
}
@keyframes lp-float-a {
    0%, 100% { transform: translateY(0px) rotate(-0.5deg); }
    50%       { transform: translateY(-14px) rotate(0.5deg); }
}
@keyframes lp-float-b {
    0%, 100% { transform: translateY(0px) rotate(0.5deg); }
    50%       { transform: translateY(-10px) rotate(-0.5deg); }
}
/* Hide stat cards on narrow screens */
@media (max-width: 1080px) {
    .lp-hero-stat { display: none !important; }
}

/* ── Enhanced grid mesh ─────────────────────────────────────── */
.lp-hero::before {
    background-image:
        linear-gradient(rgba(0,213,89,0.065) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,213,89,0.065) 1px, transparent 1px) !important;
    background-size: 48px 48px !important;
}

/* ── "IT'S US." headline glow enhancement ───────────────────── */
.lp-hero-h1 .line-us {
    filter: drop-shadow(0 0 50px rgba(0,213,89,0.35)) !important;
}

/* ── Badge boost ────────────────────────────────────────────── */
.lp-hero-badge {
    font-size: 0.65rem !important;
    padding: 10px 26px !important;
    box-shadow: 0 0 30px rgba(0,213,89,0.14), inset 0 1px 0 rgba(255,255,255,0.07) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<section class="lp-hero" id="lp-hero">

  <!-- Scan line sweep -->
  <div class="lp-hero-scan"></div>

  <!-- Floating orbs -->
  <div class="lp-hero-orb lp-hero-orb-1"></div>
  <div class="lp-hero-orb lp-hero-orb-2"></div>
  <div class="lp-hero-orb lp-hero-orb-3"></div>

  <!-- Corner brackets -->
  <div class="lp-hero-corner lp-hero-corner-tl"></div>
  <div class="lp-hero-corner lp-hero-corner-tr"></div>
  <div class="lp-hero-corner lp-hero-corner-bl"></div>
  <div class="lp-hero-corner lp-hero-corner-br"></div>

  <!-- Floating stat cards -->
  <div class="lp-hero-stat lp-hs-1">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Hit Rate</span>
    </div>
    <div class="lp-hero-stat-val">62.4%</div>
  </div>
  <div class="lp-hero-stat lp-hs-2">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Avg ROI</span>
    </div>
    <div class="lp-hero-stat-val">+18.3%</div>
  </div>
  <div class="lp-hero-stat lp-hs-3">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Props / Night</span>
    </div>
    <div class="lp-hero-stat-val">300+</div>
  </div>
  <div class="lp-hero-stat lp-hs-4">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Members</span>
    </div>
    <div class="lp-hero-stat-val">2,400+</div>
  </div>

  <!-- Logo -->
  <div class="lp-hero-logo-wrap">
    {_logo_hero_big}
  </div>

  <!-- Badge -->
  <div class="lp-hero-badge">
    <span class="lp-hero-badge-dot"></span>
    Neural Engine v6.0 &mdash; 6 AI Models Active
  </div>

  <!-- Main headline -->
  <h1 class="lp-hero-h1">
    <span class="line-problem">The House<br>Has a Problem.</span>
    <span class="line-us">It&rsquo;s&nbsp;Us.</span>
  </h1>

  <!-- Sub-copy -->
  <p class="lp-hero-sub">
    <strong>6 AI models. 300+ nightly props. One SAFE Score&trade;.</strong><br>
    Every night our Neural Engine scans PrizePicks, DraftKings &amp; Underdog
    and delivers the highest-edge plays — ranked, explained, and ready to deploy.
    Stop guessing. Start winning with a <strong>verifiable edge</strong>.
  </p>

  <!-- CTAs -->
  <div class="lp-hero-ctas">
    <a class="lp-cta-primary" href="?auth=signup">
      ⚡ Start Free — No Card Needed
    </a>
    <a class="lp-cta-secondary" href="?auth=login">
      🔒 Sign In
    </a>
  </div>

  <!-- Platform coverage -->
  <div class="lp-hero-platforms">
    <span class="lp-hero-platform-label">Covers</span>
    <span class="lp-hero-platform-pill lp-hp-pp">PrizePicks</span>
    <span class="lp-hero-platform-pill lp-hp-dk">DraftKings</span>
    <span class="lp-hero-platform-pill lp-hp-ud">Underdog</span>
    <span class="lp-hero-platform-pill lp-hp-pa">Parlayapp</span>
  </div>

  <!-- Scroll indicator -->
  <div class="lp-hero-scroll" aria-hidden="true">
    <span class="lp-hero-scroll-text">Scroll</span>
    <div class="lp-hero-scroll-line"></div>
  </div>
</section>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 3 — SOCIAL PROOF BAR + HOW IT WORKS + FEATURES GRID
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Shared section scaffolding ─────────────────────────────── */
.lp-section {
    position: relative;
    padding: 100px 24px;
    max-width: 1180px;
    margin: 0 auto;
}
.lp-section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; font-weight: 800;
    color: #00D559;
    text-transform: uppercase; letter-spacing: .14em;
    display: flex; align-items: center; gap: 10px;
    justify-content: center;
    margin-bottom: 18px;
}
.lp-section-label::before,
.lp-section-label::after {
    content: '';
    height: 1px; width: 44px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.35));
}
.lp-section-label::after {
    background: linear-gradient(270deg, transparent, rgba(0,213,89,0.35));
}
.lp-section-h2 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(2rem, 4vw, 3.2rem);
    font-weight: 900; text-align: center;
    color: #fff; letter-spacing: -0.04em;
    margin: 0 0 16px;
}
.lp-section-sub {
    font-family: 'Inter', sans-serif;
    font-size: 1rem; color: rgba(255,255,255,0.38);
    text-align: center; max-width: 520px;
    margin: 0 auto 64px; line-height: 1.75;
}

/* ── Trust / Stats bar ──────────────────────────────────────── */
.lp-trust-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    flex-wrap: wrap;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 32px 40px;
    margin: 0 auto 20px;
    max-width: 1000px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}
.lp-trust-stat {
    display: flex; flex-direction: column;
    align-items: center; gap: 6px;
    padding: 0 40px;
    flex: 1; min-width: 140px;
}
.lp-trust-stat + .lp-trust-stat {
    border-left: 1px solid rgba(255,255,255,0.07);
}
.lp-trust-big {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(1.8rem, 3vw, 2.6rem);
    font-weight: 900;
    letter-spacing: -0.04em;
    line-height: 1;
}
.lp-trust-big.c-green  { color: #00D559; text-shadow: 0 0 28px rgba(0,213,89,0.45); }
.lp-trust-big.c-blue   { color: #2D9EFF; text-shadow: 0 0 28px rgba(45,158,255,0.4); }
.lp-trust-big.c-gold   { color: #F9C62B; text-shadow: 0 0 28px rgba(249,198,43,0.35); }
.lp-trust-big.c-purple { color: #c084fc; text-shadow: 0 0 28px rgba(192,132,252,0.35); }
.lp-trust-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem; font-weight: 600;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase; letter-spacing: .07em;
    text-align: center;
}

/* ── How It Works ───────────────────────────────────────────── */
.lp-steps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 24px;
    margin: 0 auto;
}
.lp-step {
    position: relative;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 36px 28px;
    text-align: center;
    transition: border-color 0.3s, transform 0.3s;
}
.lp-step:hover {
    border-color: rgba(0,213,89,0.2);
    transform: translateY(-4px);
}
.lp-step-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 3rem; font-weight: 900;
    line-height: 1;
    -webkit-text-stroke: 1px rgba(0,213,89,0.4);
    color: transparent;
    margin-bottom: 16px;
    display: block;
}
.lp-step-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem; font-weight: 800;
    color: #fff; margin-bottom: 10px;
}
.lp-step-desc {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem; color: rgba(255,255,255,0.35);
    line-height: 1.7;
}

/* ── Features Grid ──────────────────────────────────────────── */
.lp-features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin: 0 auto;
}
.lp-feat-card {
    position: relative;
    background: rgba(255,255,255,0.022);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 32px 28px;
    overflow: hidden;
    transition: border-color 0.3s, transform 0.3s, background 0.3s;
}
/* Top gradient accent bar */
.lp-feat-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent-grad);
    opacity: 0.6;
    transition: opacity 0.3s;
}
.lp-feat-card:hover {
    transform: translateY(-4px);
    background: rgba(255,255,255,0.038);
}
.lp-feat-card:hover::before { opacity: 1; }
.lp-feat-icon {
    font-size: 2rem; line-height: 1;
    margin-bottom: 18px; display: block;
    filter: drop-shadow(0 0 12px var(--accent-glow));
}
.lp-feat-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem; font-weight: 800;
    color: #fff; margin-bottom: 10px;
    letter-spacing: -0.02em;
}
.lp-feat-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.5rem; font-weight: 800;
    color: var(--accent-color);
    background: var(--accent-bg);
    border: 1px solid var(--accent-border);
    padding: 3px 10px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: .1em;
    margin-left: 8px;
    vertical-align: middle;
}
.lp-feat-desc {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem; color: rgba(255,255,255,0.32);
    line-height: 1.7;
}
/* Accent color variables per card */
.lf-green  { --accent-grad: linear-gradient(90deg,#00FF85,#00D559); --accent-glow: rgba(0,213,89,0.4);   --accent-color:#00D559; --accent-bg:rgba(0,213,89,0.06);   --accent-border:rgba(0,213,89,0.2); }
.lf-blue   { --accent-grad: linear-gradient(90deg,#60b4ff,#2D9EFF); --accent-glow: rgba(45,158,255,0.4); --accent-color:#2D9EFF; --accent-bg:rgba(45,158,255,0.06); --accent-border:rgba(45,158,255,0.2); }
.lf-purple { --accent-grad: linear-gradient(90deg,#d8b4fe,#c084fc); --accent-glow: rgba(192,132,252,0.4);--accent-color:#c084fc; --accent-bg:rgba(192,132,252,0.06);--accent-border:rgba(192,132,252,0.2); }
.lf-gold   { --accent-grad: linear-gradient(90deg,#fde68a,#F9C62B); --accent-glow: rgba(249,198,43,0.4); --accent-color:#F9C62B; --accent-bg:rgba(249,198,43,0.06); --accent-border:rgba(249,198,43,0.2); }
</style>

<!-- ══ STATS TRUST BAR ═══════════════════════════════════════ -->
<div style="padding: 80px 24px 0; background: transparent;">
  <div class="lp-trust-bar">
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-green">62.4%</span>
      <span class="lp-trust-label">Overall Hit Rate</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-blue">+18.3%</span>
      <span class="lp-trust-label">Average ROI</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-gold">300+</span>
      <span class="lp-trust-label">Props / Night</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-purple">6</span>
      <span class="lp-trust-label">AI Models Active</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-green">2,400+</span>
      <span class="lp-trust-label">Active Members</span>
    </div>
  </div>
</div>

<!-- ══ HOW IT WORKS ══════════════════════════════════════════ -->
<div id="lp-how" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">How It Works</div>
    <h2 class="lp-section-h2">Three Steps.<br>One Edge.</h2>
    <p class="lp-section-sub">Our Neural Engine does the heavy lifting — you just pick your plays.</p>
    <div class="lp-steps">
      <div class="lp-step">
        <span class="lp-step-num">01</span>
        <div class="lp-step-title">Load Tonight's Slate</div>
        <p class="lp-step-desc">One click pulls live props from PrizePicks, DraftKings &amp; Underdog. Lines, totals, and injury data refreshed in real-time.</p>
      </div>
      <div class="lp-step">
        <span class="lp-step-num">02</span>
        <div class="lp-step-title">AI Scores Every Prop</div>
        <p class="lp-step-desc">6 AI models — ensemble, Bayesian, Monte Carlo, regression, CLV tracker &amp; line movement mirror — converge on a single SAFE Score™.</p>
      </div>
      <div class="lp-step">
        <span class="lp-step-num">03</span>
        <div class="lp-step-title">Pick Your Plays</div>
        <p class="lp-step-desc">Ranked by edge, filtered by your bankroll strategy. Green lights only. Track results live in your Bet Tracker dashboard.</p>
      </div>
    </div>
  </div>
</div>

<!-- ══ FEATURES GRID ════════════════════════════════════════ -->
<div id="lp-features" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">Platform Features</div>
    <h2 class="lp-section-h2">Built Different.<br>By Design.</h2>
    <p class="lp-section-sub">Every tool inside Smart Pick Pro exists for one reason — to give you a mathematical edge over the house.</p>
    <div class="lp-features">

      <div class="lp-feat-card lf-green">
        <span class="lp-feat-icon">🛡️</span>
        <div class="lp-feat-title">SAFE Score™ <span class="lp-feat-badge">Core</span></div>
        <p class="lp-feat-desc">Our proprietary 0–100 confidence rating. Aggregates all 6 AI model outputs, line sharpness, and historical hit rate into a single go/no-go number.</p>
      </div>

      <div class="lp-feat-card lf-blue">
        <span class="lp-feat-icon">🧠</span>
        <div class="lp-feat-title">Neural Engine v6.0 <span class="lp-feat-badge">AI</span></div>
        <p class="lp-feat-desc">Six parallel models run on every prop: Ensemble, Bayesian, Monte Carlo, Linear Regression, Neural Net, and Game Script. Zero human bias.</p>
      </div>

      <div class="lp-feat-card lf-purple">
        <span class="lp-feat-icon">📈</span>
        <div class="lp-feat-title">Line Movement Mirror <span class="lp-feat-badge">Sharp</span></div>
        <p class="lp-feat-desc">Tracks where sharp money is moving minutes before lock. When the line moves in your direction after our pick — that's CLV. We track it automatically.</p>
      </div>

      <div class="lp-feat-card lf-gold">
        <span class="lp-feat-icon">⚡</span>
        <div class="lp-feat-title">Live Props Engine <span class="lp-feat-badge">Live</span></div>
        <p class="lp-feat-desc">Real-time prop ingestion from all major platforms. Lines update as books adjust. Injury alerts auto-invalidate affected picks before you lock.</p>
      </div>

      <div class="lp-feat-card lf-green">
        <span class="lp-feat-icon">💰</span>
        <div class="lp-feat-title">Bankroll Optimizer <span class="lp-feat-badge">Pro</span></div>
        <p class="lp-feat-desc">Kelly Criterion sizing + custom risk profiles. Flat bet, fractional Kelly, or aggressive — the optimizer sets stake size based on your edge and bankroll.</p>
      </div>

      <div class="lp-feat-card lf-blue">
        <span class="lp-feat-icon">📊</span>
        <div class="lp-feat-title">Bet Tracker Dashboard <span class="lp-feat-badge">Pro</span></div>
        <p class="lp-feat-desc">Full P&amp;L history, ROI by platform, hit rate by prop type, and CLV tracking. Your personal analytics suite to prove your edge over time.</p>
      </div>

    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 4 — PRICING TEASER + TESTIMONIALS
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Pricing Section ─────────────────────────────────────── */
.lp-pricing-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    max-width: 1000px;
    margin: 0 auto;
}
.lp-price-card {
    position: relative;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 24px;
    padding: 36px 28px 32px;
    display: flex; flex-direction: column;
    transition: transform 0.3s, border-color 0.3s, background 0.3s;
    overflow: hidden;
}
.lp-price-card:hover {
    transform: translateY(-6px);
}
.lp-price-card.popular {
    border-color: rgba(0,213,89,0.25);
    background: rgba(0,213,89,0.04);
    box-shadow: 0 0 50px rgba(0,213,89,0.1), inset 0 1px 0 rgba(0,213,89,0.1);
}
/* Top gradient bar */
.lp-price-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--pc-grad);
}
.lp-price-popular-badge {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem; font-weight: 800;
    color: #020C07;
    background: linear-gradient(135deg, #00FF85, #00D559);
    padding: 5px 14px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: .1em;
    margin-bottom: 20px;
    align-self: flex-start;
    box-shadow: 0 0 20px rgba(0,213,89,0.4);
    position: relative; overflow: hidden;
}
.lp-price-popular-badge::after {
    content: '';
    position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
    animation: agShimmer 2.5s ease-in-out infinite;
}
.lp-price-tier {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; font-weight: 800;
    color: var(--pc-color);
    text-transform: uppercase; letter-spacing: .12em;
    margin-bottom: 16px;
}
.lp-price-amount {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3rem; font-weight: 900;
    color: #fff; letter-spacing: -0.06em;
    line-height: 1;
    margin-bottom: 4px;
}
.lp-price-amount span {
    font-size: 1.1rem;
    font-weight: 700;
    color: rgba(255,255,255,0.4);
    letter-spacing: 0;
}
.lp-price-period {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem; color: rgba(255,255,255,0.28);
    margin-bottom: 28px;
}
.lp-price-features {
    list-style: none; padding: 0; margin: 0 0 32px;
    display: flex; flex-direction: column; gap: 12px;
    flex: 1;
}
.lp-price-features li {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem; color: rgba(255,255,255,0.5);
    display: flex; align-items: flex-start; gap: 10px;
    line-height: 1.5;
}
.lp-price-features li .chk {
    color: var(--pc-color);
    font-size: 0.75rem; margin-top: 2px; flex-shrink: 0;
}
.lp-price-features li.dim .chk { color: rgba(255,255,255,0.15); }
.lp-price-features li.dim { color: rgba(255,255,255,0.2); }
.lp-price-cta {
    display: block; width: 100%;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.88rem; font-weight: 800;
    text-align: center; text-decoration: none;
    padding: 14px 24px; border-radius: 100px;
    letter-spacing: .02em;
    background: var(--pc-cta-bg);
    color: var(--pc-cta-color);
    border: 1px solid var(--pc-cta-border);
    transition: all 0.25s;
}
.lp-price-cta:hover {
    transform: translateY(-2px);
    filter: brightness(1.15);
}
/* Card themes */
.lp-pc-free    { --pc-grad: linear-gradient(90deg,rgba(255,255,255,0.12),rgba(255,255,255,0.04)); --pc-color: rgba(255,255,255,0.4); --pc-cta-bg: rgba(255,255,255,0.05); --pc-cta-color: rgba(255,255,255,0.5); --pc-cta-border: rgba(255,255,255,0.1); }
.lp-pc-sharp   { --pc-grad: linear-gradient(90deg,#60b4ff,#2D9EFF); --pc-color: #2D9EFF; --pc-cta-bg: rgba(45,158,255,0.1); --pc-cta-color: #2D9EFF; --pc-cta-border: rgba(45,158,255,0.25); }
.lp-pc-smart   { --pc-grad: linear-gradient(90deg,#00FF85,#00D559); --pc-color: #00D559; --pc-cta-bg: linear-gradient(135deg,#00FF85,#00D559); --pc-cta-color: #020C07; --pc-cta-border: transparent; }

/* ── Testimonials ─────────────────────────────────────────── */
.lp-testimonials {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    max-width: 1000px;
    margin: 0 auto;
}
.lp-testi-card {
    background: rgba(255,255,255,0.022);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 28px 24px;
    transition: transform 0.3s, border-color 0.3s;
}
.lp-testi-card:hover {
    transform: translateY(-3px);
    border-color: rgba(0,213,89,0.15);
}
.lp-testi-stars {
    color: #F9C62B;
    font-size: 0.85rem;
    letter-spacing: 2px;
    margin-bottom: 14px;
}
.lp-testi-quote {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem; line-height: 1.75;
    color: rgba(255,255,255,0.55);
    margin-bottom: 20px;
    font-style: italic;
}
.lp-testi-quote::before { content: '\\201C'; color: #00D559; font-style: normal; font-size: 1.2rem; }
.lp-testi-quote::after  { content: '\\201D'; color: #00D559; font-style: normal; font-size: 1.2rem; }
.lp-testi-author {
    display: flex; align-items: center; gap: 12px;
}
.lp-testi-avatar {
    width: 38px; height: 38px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.75rem; font-weight: 800;
    color: #020C07;
    background: linear-gradient(135deg, #00FF85, #00D559);
    flex-shrink: 0;
}
.lp-testi-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.82rem; font-weight: 700;
    color: #fff;
}
.lp-testi-handle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; color: rgba(255,255,255,0.25);
    letter-spacing: .04em;
}
</style>

<!-- ══ PRICING ══════════════════════════════════════════════ -->
<div id="lp-pricing" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">Pricing</div>
    <h2 class="lp-section-h2">Start Free.<br>Scale Your Edge.</h2>
    <p class="lp-section-sub">No credit card to start. Upgrade when you're ready to unlock the full Neural Engine.</p>

    <div class="lp-pricing-grid">

      <!-- FREE -->
      <div class="lp-price-card lp-pc-free">
        <div class="lp-price-tier">Free Rookie</div>
        <div class="lp-price-amount">$0<span></span></div>
        <div class="lp-price-period">forever free</div>
        <ul class="lp-price-features">
          <li><span class="chk">✓</span> Daily top 3 picks preview</li>
          <li><span class="chk">✓</span> SAFE Score™ visible</li>
          <li><span class="chk">✓</span> Basic prop analysis</li>
          <li class="dim"><span class="chk">✗</span> Full 300+ prop slate</li>
          <li class="dim"><span class="chk">✗</span> Line movement alerts</li>
          <li class="dim"><span class="chk">✗</span> Bet Tracker dashboard</li>
        </ul>
        <a class="lp-price-cta" href="?auth=signup">Get Started Free</a>
      </div>

      <!-- SHARP IQ -->
      <div class="lp-price-card lp-pc-sharp">
        <div class="lp-price-tier">Sharp IQ</div>
        <div class="lp-price-amount">$9<span>.99 / mo</span></div>
        <div class="lp-price-period">billed monthly</div>
        <ul class="lp-price-features">
          <li><span class="chk">✓</span> Full nightly prop slate</li>
          <li><span class="chk">✓</span> All 6 AI model scores</li>
          <li><span class="chk">✓</span> Line movement tracker</li>
          <li><span class="chk">✓</span> Bankroll optimizer</li>
          <li><span class="chk">✓</span> Bet Tracker dashboard</li>
          <li class="dim"><span class="chk">✗</span> Custom AI thresholds</li>
        </ul>
        <a class="lp-price-cta" href="?auth=signup">Start Sharp IQ</a>
      </div>

      <!-- SMART MONEY -->
      <div class="lp-price-card lp-pc-smart popular">
        <div class="lp-price-popular-badge">⚡ Most Popular</div>
        <div class="lp-price-tier">Smart Money</div>
        <div class="lp-price-amount">$24<span>.99 / mo</span></div>
        <div class="lp-price-period">billed monthly · save 20% annual</div>
        <ul class="lp-price-features">
          <li><span class="chk">✓</span> Everything in Sharp IQ</li>
          <li><span class="chk">✓</span> Custom AI thresholds</li>
          <li><span class="chk">✓</span> Arbitrage scanner</li>
          <li><span class="chk">✓</span> Tournament optimizer</li>
          <li><span class="chk">✓</span> Priority prop alerts</li>
          <li><span class="chk">✓</span> Discord VIP access</li>
        </ul>
        <a class="lp-price-cta" href="?auth=signup">Unlock Smart Money</a>
      </div>

    </div>
  </div>
</div>

<!-- ══ TESTIMONIALS ═════════════════════════════════════════ -->
<div id="lp-testimonials" style="padding: 80px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">Member Results</div>
    <h2 class="lp-section-h2">The Numbers<br>Don't Lie.</h2>
    <p class="lp-section-sub">Real members. Real results. No cherry-picked picks — full P&amp;L tracked in the dashboard.</p>

    <div class="lp-testimonials">

      <div class="lp-testi-card">
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Hit 8 of my last 10 PrizePicks entries using the SAFE Score filter. ROI is sitting at +23% for the month. Nothing else comes close.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar">MR</div>
          <div>
            <div class="lp-testi-name">Marcus R.</div>
            <div class="lp-testi-handle">Smart Money · 4 months</div>
          </div>
        </div>
      </div>

      <div class="lp-testi-card">
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">The line movement alerts alone paid for 6 months. Caught a huge CLV swing on Tatum points last week. This tool is ridiculous.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar">JT</div>
          <div>
            <div class="lp-testi-name">Jake T.</div>
            <div class="lp-testi-handle">Sharp IQ · 7 months</div>
          </div>
        </div>
      </div>

      <div class="lp-testi-card">
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">I was skeptical — now I don't touch a prop without running it through the Neural Engine first. 64% hit rate over 200+ tracked picks.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar">AL</div>
          <div>
            <div class="lp-testi-name">Alex L.</div>
            <div class="lp-testi-handle">Smart Money · 2 months</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 5 — INLINE AUTH SECTION (centered premium card)
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Section header above the form ─────────────────────────── */
#lp-auth {
    padding: 100px 24px 0;
    text-align: center;
}
/* Hide the old split-panel LEFT hero — we have the hero above */
.spp-hero { display: none !important; }
/* Remove the fixed-height portal grid */
.spp-portal {
    display: block !important;
    background: transparent !important;
    min-height: unset !important;
    padding: 0 !important;
    max-width: 540px;
    margin: 0 auto;
}
.spp-form-panel#spp-form-panel-bg { display: none !important; }

/* Centre the form — override old right-align trick */
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container > div {
    align-items: center !important;
}
/* Premium centered form card */
.spp-form-wrapper {
    width: 100% !important;
    max-width: 500px !important;
    min-height: unset !important;
    background: rgba(255,255,255,0.028) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 24px !important;
    box-shadow:
        0 0 60px rgba(0,213,89,0.06),
        0 24px 80px rgba(0,0,0,0.4),
        inset 0 1px 0 rgba(255,255,255,0.06) !important;
    padding: 40px 36px 36px !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    position: relative !important;
    overflow: hidden;
}
/* Green glow top bar on form card */
.spp-form-wrapper::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #00D559, #2D9EFF, transparent);
    opacity: 0.6;
}
</style>

<!-- Section anchor + label -->
<div id="lp-auth">
  <div class="lp-section-label">Get Access</div>
  <h2 class="lp-section-h2">Join 2,400+<br>Winning Sharps.</h2>
  <p class="lp-section-sub" style="margin-bottom: 48px;">
    Free forever. No credit card required.<br>
    Start picking smarter tonight.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Split-panel outer wrapper: hero LEFT, form RIGHT ──────────
st.markdown(f"""
<div class="spp-portal">

  <!-- ════════ LEFT: HERO PANEL ════════ -->
  <div class="spp-hero">

    <!-- Logo + wordmark -->
    <div class="spp-hero-logo">
      {_logo_img_hero}
      <span class="spp-hero-wordmark">Smart<span class="em">Pick</span>Pro</span>
    </div>

    <!-- Main headline -->
    <h1 class="spp-hero-headline">
      The House<br>Has a Problem.<br>
      <span class="em">It&rsquo;s&nbsp;Us.</span>
    </h1>

    <!-- Sub-copy -->
    <p class="spp-hero-sub">
      <strong>6 AI models. 300+ nightly props. One SAFE Score&trade;.</strong><br>
      Every morning our Neural Engine v6.0 scans PrizePicks, DraftKings &amp;
      Underdog and hands you the highest-edge opportunities — ranked, explained,
      and ready to deploy. Stop guessing. Start winning with a verifiable edge.
    </p>

    <!-- 2×2 proof stats -->
    <div class="spp-proof-grid">
      <div class="spp-proof-card">
        <div class="spp-proof-big">62.4%</div>
        <div class="spp-proof-label">Hit Rate</div>
        <div class="spp-proof-sub">Verified over 4,200+ picks</div>
      </div>
      <div class="spp-proof-card">
        <div class="spp-proof-big">300+</div>
        <div class="spp-proof-label">Props Scanned</div>
        <div class="spp-proof-sub">Every night, all major platforms</div>
      </div>
      <div class="spp-proof-card">
        <div class="spp-proof-big">6</div>
        <div class="spp-proof-label">AI Models</div>
        <div class="spp-proof-sub">Ensemble + Monte Carlo</div>
      </div>
      <div class="spp-proof-card">
        <div class="spp-proof-big">2,400+</div>
        <div class="spp-proof-label">Members Inside</div>
        <div class="spp-proof-sub">Sharps already in the edge loop</div>
      </div>
    </div>

    <!-- Testimonial -->
    <div class="spp-testimonial">
      <p class="spp-testimonial-text">
        &ldquo;I&rsquo;ve tried every tout service out there. Smart Pick Pro is the
        <strong>first one that actually shows its math</strong>. The SAFE Score is
        genuinely different — up 22% since January.&rdquo;
      </p>
      <span class="spp-testimonial-author">— Marcus T., Vegas Sharp
        <span class="spp-testimonial-stars">★★★★★</span>
      </span>
    </div>

  </div><!-- /spp-hero -->

  <!-- ════════ RIGHT: FORM PANEL placeholder (filled by Streamlit below) ════════ -->
  <div class="spp-form-panel" id="spp-form-panel-bg"></div>

</div><!-- /spp-portal -->
""", unsafe_allow_html=True)

# ── Streamlit renders form content into a column on the right ─
# We use CSS to visually place the Streamlit block-container content
# as a centred panel over the right half of the screen.
st.markdown("""
<style>
/* Float Streamlit form content to the right side of the split */
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container > div {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
}
/* Inner form wrapper: fixed width, centred in right column */
.spp-form-wrapper {
    width: 100%;
    max-width: 480px;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 40px 40px 40px;
    position: relative;
}
@media (max-width: 960px) {
    .stApp > [data-testid="stAppViewContainer"] > section.main .block-container > div {
        align-items: center;
    }
    .spp-form-wrapper {
        max-width: 440px;
        min-height: unset;
        padding: 32px 20px 40px;
    }
}
</style>
""", unsafe_allow_html=True)

# Wrap all form content in the right-panel div
st.markdown("""
<div class="spp-form-wrapper spp-form-inner">
  <!-- Back link -->
  <a class="spp-back-link" href=".">&#8592; Back to Home</a>

  <!-- Logo (shown on mobile / inside form panel) -->
  <div class="spp-form-logo" style="display:none" id="spp-mobile-logo"></div>
</div>
<script>
// Show mobile logo when hero panel is hidden
(function(){
  var mq = window.matchMedia('(max-width: 960px)');
  function check(e){ document.getElementById('spp-mobile-logo').style.display = e.matches ? 'block' : 'none'; }
  check(mq); mq.addEventListener('change', check);
})();
</script>
""", unsafe_allow_html=True)

# ── AI badge, headline and mode tabs ─────────────────────────
_headline   = "Welcome Back" if _mode == "login" else "Create Account"
_sub        = "Sign in to your AI picks dashboard." if _mode == "login" else "Free forever — no credit card required."
_tab_login  = "active" if _mode == "login"  else ""
_tab_signup = "active" if _mode == "signup" else ""

st.markdown(f"""
<div style="text-align:center; margin-bottom:4px;">
  <div class="spp-ai-badge">
    <span class="spp-ai-dot"></span>
    Neural Engine v6.0 &mdash; 6 AI Models Active
  </div>
</div>
<h2 class="spp-form-headline">{_headline}</h2>
<p class="spp-form-sub">{_sub}</p>

<div class="spp-mode-tabs">
  <a href="?auth=login"  class="spp-mode-tab {_tab_login}">&#x1F513; Sign In</a>
  <a href="?auth=signup" class="spp-mode-tab {_tab_signup}">&#x26A1; Create Free Account</a>
</div>
""", unsafe_allow_html=True)

# ── The actual Streamlit form ─────────────────────────────────
# We wrap in spp-form-inner for the premium CSS to apply.
st.markdown('<div class="spp-form-inner">', unsafe_allow_html=True)

if _mode == "login":
    # ── LOGIN FORM ────────────────────────────────────────────
    with st.form("spp_login_form", clear_on_submit=False):
        _li_email = st.text_input("Email Address", placeholder="you@example.com", key="_spp_li_email")
        _li_pw    = st.text_input("Password", type="password", placeholder="Enter your password", key="_spp_li_pw")
        _li_sub   = st.form_submit_button("🔓 Sign In", use_container_width=True, type="primary")

    if _li_sub:
        if not _li_email or not _valid_email(_li_email):
            st.error("Please enter a valid email address.")
        elif not _li_pw:
            st.error("Please enter your password.")
        else:
            _lock = _check_login_lockout(_li_email)
            if _lock:
                st.error(f"🔒 {_lock}")
            else:
                _user = _authenticate_user(_li_email, _li_pw)
                if _user:
                    _clear_failed_logins(_li_email)
                    _set_logged_in(_user)
                    try:
                        from utils.analytics import track_login
                        track_login(_li_email)
                    except Exception:
                        pass
                    st.success(f"Welcome back, {_user.get('display_name', '')}! Redirecting…")
                    st.switch_page("Smart_Picks_Pro_Home.py")
                else:
                    _record_failed_login(_li_email)
                    st.error("Invalid email or password.")

    # Forgot password expander
    st.markdown("---")
    _rst = st.session_state.get("_spp_rst_stage", "idle")

    if _rst == "idle":
        if st.button("🔑 Forgot Password?", key="_spp_forgot", use_container_width=True):
            st.session_state["_spp_rst_stage"] = "email"
            st.rerun()

    elif _rst == "email":
        st.info("📧 Enter your email and we'll send a reset code.")
        with st.form("spp_rst_email", clear_on_submit=False):
            _rst_em = st.text_input("Email Address", placeholder="you@example.com", key="_spp_rst_em")
            _rst_send = st.form_submit_button("📨 Send Reset Code", use_container_width=True)
        if _rst_send:
            if not _rst_em or not _valid_email(_rst_em):
                st.error("Enter a valid email address.")
            else:
                _generate_reset_token(_rst_em)
                st.success("📧 If this email is registered, a reset code has been sent.")
                st.session_state["_spp_rst_stage"] = "code"
                st.session_state["_spp_rst_email"] = _rst_em.strip().lower()
                st.rerun()
        if st.button("Cancel", key="_spp_rst_cancel1"):
            st.session_state["_spp_rst_stage"] = "idle"
            st.rerun()

    elif _rst == "code":
        _rst_em_saved = st.session_state.get("_spp_rst_email", "")
        st.info(f"📧 Reset code sent to **{_rst_em_saved}** — expires in 15 min.")
        with st.form("spp_rst_code", clear_on_submit=False):
            _code_in = st.text_input("6-digit Code", placeholder="123456", key="_spp_rst_code_in")
            _code_sub = st.form_submit_button("✅ Verify Code", use_container_width=True)
        if _code_sub:
            if _verify_reset_token(_rst_em_saved, _code_in):
                st.session_state["_spp_rst_stage"] = "newpw"
                st.rerun()
            else:
                st.error("Invalid or expired code.")
        if st.button("Cancel", key="_spp_rst_cancel2"):
            st.session_state["_spp_rst_stage"] = "idle"
            st.rerun()

    elif _rst == "newpw":
        _rst_em_saved = st.session_state.get("_spp_rst_email", "")
        st.info(f"🔒 Set a new password for `{_rst_em_saved}`")
        with st.form("spp_rst_newpw", clear_on_submit=False):
            _new_pw  = st.text_input("New Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_spp_np")
            _new_pw2 = st.text_input("Confirm", type="password", placeholder="Re-enter new password", key="_spp_np2")
            _pw_sub  = st.form_submit_button("💾 Save New Password", use_container_width=True, type="primary")
        if _pw_sub:
            if pw_err := _valid_password(_new_pw):
                st.error(pw_err)
            elif _new_pw != _new_pw2:
                st.error("Passwords don't match.")
            elif _reset_user_password(_rst_em_saved, _new_pw):
                st.success("✅ Password reset! Sign in with your new password.")
                for k in ("_spp_rst_stage", "_spp_rst_email"):
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Reset failed — please try again.")

else:
    # ── SIGNUP FORM ───────────────────────────────────────────
    _SU_STAGE = "_spp_su_stage"
    _SU_EMAIL = "_spp_su_email"
    _SU_NAME  = "_spp_su_name"
    if _SU_STAGE not in st.session_state:
        st.session_state[_SU_STAGE] = 1

    _stage = st.session_state[_SU_STAGE]
    _s1c = "#00D559" if _stage >= 1 else "rgba(255,255,255,0.15)"
    _s2c = "#00D559" if _stage >= 2 else "rgba(255,255,255,0.15)"
    _lc  = "#00D559" if _stage >= 2 else "rgba(255,255,255,0.08)"

    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:center;
                gap:0;margin:0 auto 20px;max-width:240px;">
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <div style="width:32px;height:32px;border-radius:50%;
                    background:{_s1c};display:flex;align-items:center;justify-content:center;
                    font-family:'Space Grotesk',sans-serif;font-size:.75rem;font-weight:800;
                    color:#0B0F19;">1</div>
        <span style="font-size:.52rem;font-weight:700;color:{_s1c};
                     font-family:'JetBrains Mono',monospace;text-transform:uppercase;
                     letter-spacing:.08em;">Info</span>
      </div>
      <div style="flex:1;height:2px;background:{_lc};margin:0 10px 16px;
                  border-radius:2px;"></div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <div style="width:32px;height:32px;border-radius:50%;
                    background:{_s2c};display:flex;align-items:center;justify-content:center;
                    font-family:'Space Grotesk',sans-serif;font-size:.75rem;font-weight:800;
                    color:#0B0F19;">2</div>
        <span style="font-size:.52rem;font-weight:700;color:{_s2c};
                     font-family:'JetBrains Mono',monospace;text-transform:uppercase;
                     letter-spacing:.08em;">Secure</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if _stage == 1:
        st.markdown("""
        <div style="text-align:center;margin-bottom:14px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1rem;
                      font-weight:800;color:#fff;margin-bottom:4px;">Let&rsquo;s get you started</div>
          <div style="font-size:.7rem;color:rgba(255,255,255,.35);">
            Enter your name and email to create your free account.
          </div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("spp_signup_step1", clear_on_submit=False):
            _su_name  = st.text_input("Display Name", placeholder="e.g. Joseph", key="_spp_su_name")
            _su_email = st.text_input("Email Address", placeholder="you@example.com", key="_spp_su_email")
            _su_sub1  = st.form_submit_button("➡ Continue", use_container_width=True, type="primary")
        if _su_sub1:
            if not _su_name or len(_su_name.strip()) < 2:
                st.error("Display name must be at least 2 characters.")
            elif not _su_email or not _valid_email(_su_email):
                st.error("Please enter a valid email address.")
            elif _email_exists(_su_email):
                st.error("This email is already registered. Sign in instead.")
            else:
                st.session_state[_SU_NAME]  = _su_name.strip()
                st.session_state[_SU_EMAIL] = _su_email.strip().lower()
                st.session_state[_SU_STAGE] = 2
                st.rerun()

    elif _stage == 2:
        _saved_name  = st.session_state.get(_SU_NAME, "")
        _saved_email = st.session_state.get(_SU_EMAIL, "")
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:14px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1rem;
                      font-weight:800;color:#fff;margin-bottom:4px;">Secure your account</div>
          <div style="font-size:.7rem;color:rgba(255,255,255,.35);">
            Creating account for <strong style="color:#00D559;">{_saved_email}</strong>
          </div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("spp_signup_step2", clear_on_submit=False):
            _su_pw  = st.text_input("Password", type="password",
                                    placeholder="Min 8 chars, 1 letter, 1 number", key="_spp_su_pw")
            _su_pw2 = st.text_input("Confirm Password", type="password",
                                    placeholder="Re-enter password", key="_spp_su_pw2")
            _su_sub2 = st.form_submit_button("⚡ Create Free Account", use_container_width=True, type="primary")
        _cb, _ = st.columns([1, 3])
        with _cb:
            if st.button("← Back", key="_spp_su_back", use_container_width=True):
                st.session_state[_SU_STAGE] = 1
                st.rerun()
        if _su_sub2:
            if pw_err := _valid_password(_su_pw):
                st.error(pw_err)
            elif _su_pw != _su_pw2:
                st.error("Passwords don't match.")
            elif _email_exists(_saved_email):
                st.error("Email already registered. Please sign in.")
                st.session_state[_SU_STAGE] = 1
            else:
                _ok = _create_user(_saved_email, _su_pw, _saved_name)
                if _ok:
                    _new_user = _authenticate_user(_saved_email, _su_pw)
                    if _new_user:
                        _set_logged_in(_new_user)
                        try:
                            from utils.analytics import track_signup
                            track_signup(_saved_email)
                        except Exception:
                            pass
                        try:
                            from utils.notifications import trigger_welcome_flow
                            trigger_welcome_flow(_saved_email, _saved_name)
                        except Exception:
                            pass
                        for k in (_SU_STAGE, _SU_EMAIL, _SU_NAME):
                            st.session_state.pop(k, None)
                        st.session_state["_show_onboarding_tour"] = True
                        st.session_state["_tour_step"] = 0
                        st.session_state["_just_signed_up"] = True
                        st.switch_page("Smart_Picks_Pro_Home.py")
                    else:
                        st.error("Account created but login failed. Please sign in.")
                else:
                    st.error("Could not create account — please try again.")

st.markdown("</div>", unsafe_allow_html=True)  # /spp-form-inner

# ── Trust strip ───────────────────────────────────────────────
st.markdown("""
<div class="spp-trust-strip">
  <span class="spp-trust-item">🔒 256-bit Encryption</span>
  <span class="spp-trust-item">⚡ Free Forever</span>
  <span class="spp-trust-item">🚫 No Credit Card</span>
  <span class="spp-trust-item">❌ Cancel Nothing</span>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 6 — FOOTER
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Footer ─────────────────────────────────────────────────── */
.lp-footer {
    margin-top: 100px;
    border-top: 1px solid rgba(255,255,255,0.06);
    padding: 64px 40px 48px;
    max-width: 1180px;
    margin-left: auto; margin-right: auto;
}
.lp-footer-top {
    display: grid;
    grid-template-columns: 1.8fr repeat(3, 1fr);
    gap: 48px;
    margin-bottom: 56px;
}
@media (max-width: 760px) {
    .lp-footer-top { grid-template-columns: 1fr 1fr; gap: 32px; }
}
@media (max-width: 480px) {
    .lp-footer-top { grid-template-columns: 1fr; }
}
.lp-footer-brand-tagline {
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem; color: rgba(255,255,255,0.28);
    line-height: 1.7;
    margin: 12px 0 24px;
    max-width: 220px;
}
.lp-footer-wordmark {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem; font-weight: 900;
    color: #fff; letter-spacing: -0.04em;
}
.lp-footer-wordmark em { color: #00D559; font-style: normal; }
.lp-footer-social {
    display: flex; gap: 10px;
}
.lp-footer-social a {
    display: flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 10px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    color: rgba(255,255,255,0.35);
    font-size: 0.85rem; text-decoration: none;
    transition: all 0.2s;
}
.lp-footer-social a:hover {
    background: rgba(0,213,89,0.08);
    border-color: rgba(0,213,89,0.2);
    color: #00D559;
    transform: translateY(-2px);
}
.lp-footer-col-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem; font-weight: 800;
    color: rgba(255,255,255,0.25);
    text-transform: uppercase; letter-spacing: .14em;
    margin-bottom: 18px;
}
.lp-footer-links {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 12px;
}
.lp-footer-links li a {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem; color: rgba(255,255,255,0.32);
    text-decoration: none;
    transition: color 0.2s;
}
.lp-footer-links li a:hover { color: #fff; }
.lp-footer-bottom {
    display: flex;
    align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 12px;
    border-top: 1px solid rgba(255,255,255,0.05);
    padding-top: 28px;
}
.lp-footer-copy {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem; color: rgba(255,255,255,0.18);
}
.lp-footer-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem; font-weight: 800;
    color: #00D559;
    background: rgba(0,213,89,0.06);
    border: 1px solid rgba(0,213,89,0.18);
    padding: 4px 12px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: .1em;
}
</style>

<footer>
<div class="lp-footer">
  <div class="lp-footer-top">

    <!-- Brand -->
    <div>
      <div class="lp-footer-wordmark">Smart<em>Pick</em>Pro</div>
      <p class="lp-footer-brand-tagline">
        AI-powered prop picks built for serious players.
        6 models. One edge. Zero guesswork.
      </p>
      <div class="lp-footer-social">
        <a href="#" aria-label="Twitter / X">𝕏</a>
        <a href="#" aria-label="Discord">⚡</a>
        <a href="#" aria-label="Telegram">✈</a>
      </div>
    </div>

    <!-- Product -->
    <div>
      <div class="lp-footer-col-label">Product</div>
      <ul class="lp-footer-links">
        <li><a href="#lp-features">Features</a></li>
        <li><a href="#lp-pricing">Pricing</a></li>
        <li><a href="#lp-how">How It Works</a></li>
        <li><a href="?auth=signup">Start Free</a></li>
      </ul>
    </div>

    <!-- Support -->
    <div>
      <div class="lp-footer-col-label">Support</div>
      <ul class="lp-footer-links">
        <li><a href="#">FAQ</a></li>
        <li><a href="#">Contact Us</a></li>
        <li><a href="#">Discord Community</a></li>
        <li><a href="#">Responsible Play</a></li>
      </ul>
    </div>

    <!-- Legal -->
    <div>
      <div class="lp-footer-col-label">Legal</div>
      <ul class="lp-footer-links">
        <li><a href="#">Terms of Service</a></li>
        <li><a href="#">Privacy Policy</a></li>
        <li><a href="#">Disclaimer</a></li>
        <li><a href="#">Cookie Policy</a></li>
      </ul>
    </div>

  </div>

  <div class="lp-footer-bottom">
    <span class="lp-footer-copy">
      &copy; 2026 Smart Pick Pro. All rights reserved. For entertainment purposes only.
      Not affiliated with DraftKings, PrizePicks, or Underdog Fantasy.
    </span>
    <span class="lp-footer-badge">Neural Engine v6.0</span>
  </div>
</div>
</footer>
""", unsafe_allow_html=True)

# Also handle cookie-based session restore silently at the bottom
# This is a fallback for environments where the quick restore above fails
if require_login():
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

st.stop()
