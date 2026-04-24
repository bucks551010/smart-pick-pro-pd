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
    width: 100px; height: 100px;
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

/* Hamburger button — hidden on desktop */
.lp-nav-hamburger {
    display: none;
    background: none;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 7px 10px;
    cursor: pointer;
    color: rgba(255,255,255,0.7);
    font-size: 1.1rem;
    line-height: 1;
    transition: all 0.2s;
    flex-shrink: 0;
}
.lp-nav-hamburger:hover {
    background: rgba(255,255,255,0.07);
    color: #fff;
    border-color: rgba(255,255,255,0.3);
}

/* Mobile dropdown menu */
.lp-nav-mobile {
    display: none;
    position: fixed;
    top: 98px; /* below ticker + nav */
    left: 0; right: 0;
    background: rgba(2,6,14,0.97);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border-bottom: 1px solid rgba(0,213,89,0.15);
    padding: 16px 20px 20px;
    z-index: 9997;
    animation: lpMobileMenuIn 0.22s cubic-bezier(0.16,1,0.3,1) both;
}
.lp-nav-mobile.open { display: block; }
@keyframes lpMobileMenuIn {
    from { opacity: 0; transform: translateY(-10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.lp-nav-mobile ul {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 4px;
}
.lp-nav-mobile ul li a {
    display: block;
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem; font-weight: 600;
    color: rgba(255,255,255,0.6);
    text-decoration: none;
    padding: 11px 14px;
    border-radius: 10px;
    transition: all 0.18s;
}
.lp-nav-mobile ul li a:hover {
    color: #fff;
    background: rgba(255,255,255,0.06);
}
.lp-nav-mobile-ctas {
    display: flex; gap: 10px; margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.lp-nav-mobile-ctas a {
    flex: 1; text-align: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.82rem; font-weight: 700;
    text-decoration: none;
    padding: 11px 18px;
    border-radius: 100px;
    transition: all 0.2s;
}
.lp-nav-mobile-ctas .m-login {
    color: rgba(255,255,255,0.6);
    border: 1px solid rgba(255,255,255,0.15);
}
.lp-nav-mobile-ctas .m-signup {
    color: #020C07;
    background: linear-gradient(135deg, #00E865, #00D559);
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 0 18px rgba(0,213,89,0.3);
}

/* Hide on mobile */
@media (max-width: 760px) {
    .lp-nav-links { display: none; }
    .lp-nav { padding: 0 20px; }
    .lp-nav-hamburger { display: flex; align-items: center; justify-content: center; }
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
    <button class="lp-nav-hamburger" id="lp-hamburger" aria-label="Open menu" aria-expanded="false">☰</button>
  </div>
</nav>

<!-- Mobile dropdown menu -->
<div class="lp-nav-mobile" id="lp-nav-mobile" role="navigation" aria-label="Mobile navigation">
  <ul>
    <li><a href="#lp-how" onclick="lpCloseMobile()">How It Works</a></li>
    <li><a href="#lp-features" onclick="lpCloseMobile()">Features</a></li>
    <li><a href="#lp-picks" onclick="lpCloseMobile()">Picks</a></li>
    <li><a href="#lp-pricing" onclick="lpCloseMobile()">Pricing</a></li>
    <li><a href="#lp-faq" onclick="lpCloseMobile()">FAQ</a></li>
  </ul>
  <div class="lp-nav-mobile-ctas">
    <a class="m-login" href="?auth=login">🔒 Log In</a>
    <a class="m-signup" href="?auth=signup">⚡ Sign Up Free</a>
  </div>
</div>

<!-- Push page content below fixed ticker+nav -->
<div class="lp-page-offset"></div>
""", unsafe_allow_html=True)

st.markdown("""
<script>
/* ── Navbar scroll behaviour ───────────────────────────── */
(function(){
  var NAV_OFFSET = 98; /* 34px ticker + 64px nav */
  function getNav(doc){ return doc.querySelector('.lp-nav'); }

  function applyScroll(doc){
    var nav = getNav(doc);
    if(!nav) return;
    var scrolled = (doc.scrollingElement || doc.documentElement).scrollTop > 24;
    nav.style.background  = scrolled
      ? 'rgba(2,6,14,0.97)'
      : 'rgba(2,6,14,0.88)';
    nav.style.boxShadow   = scrolled
      ? '0 1px 0 rgba(255,255,255,0.05), 0 8px 32px rgba(0,0,0,0.4)'
      : 'none';
    nav.style.borderBottomColor = scrolled
      ? 'rgba(0,213,89,0.1)'
      : 'rgba(255,255,255,0.06)';
  }

  function initNav(){
    [document, window.parent && window.parent.document].forEach(function(doc){
      if(!doc) return;
      try{
        applyScroll(doc);
        doc.addEventListener('scroll', function(){ applyScroll(doc); });
      }catch(e){}
    });
  }

  /* ── Smooth scroll with fixed-nav offset ──────────────── */
  function initSmoothScroll(doc){
    doc.querySelectorAll('a[href^="#"]').forEach(function(a){
      a.addEventListener('click', function(e){
        var id = a.getAttribute('href').slice(1);
        var target = doc.getElementById(id);
        if(!target) return;
        e.preventDefault();
        var top = target.getBoundingClientRect().top
                  + (doc.scrollingElement||doc.documentElement).scrollTop
                  - NAV_OFFSET - 12;
        (doc.scrollingElement||doc.documentElement).scrollTo({top:top, behavior:'smooth'});
      });
    });
  }

  function tryAll(){
    initNav();
    try{ initSmoothScroll(document); }catch(e){}
    try{ initSmoothScroll(window.parent.document); }catch(e){}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', tryAll);
  else tryAll();
  setTimeout(tryAll, 700);
})();

/* ── Hamburger toggle ──────────────────────────────── */
function lpToggleMobile() {
  var btn  = document.getElementById('lp-hamburger');
  var menu = document.getElementById('lp-nav-mobile');
  if (!btn || !menu) {
    try {
      btn  = window.parent.document.getElementById('lp-hamburger');
      menu = window.parent.document.getElementById('lp-nav-mobile');
    } catch(e) { return; }
  }
  if (!btn || !menu) return;
  var open = menu.classList.toggle('open');
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  btn.textContent = open ? '✕' : '☰';
}
function lpCloseMobile() {
  var btn  = document.getElementById('lp-hamburger');
  var menu = document.getElementById('lp-nav-mobile');
  try {
    if (!btn) btn  = window.parent.document.getElementById('lp-hamburger');
    if (!menu) menu = window.parent.document.getElementById('lp-nav-mobile');
  } catch(e) {}
  if (menu) menu.classList.remove('open');
  if (btn)  { btn.setAttribute('aria-expanded','false'); btn.textContent = '☰'; }
}
(function attachHamburger(){
  function bind(doc){
    if (!doc) return;
    try {
      var b = doc.getElementById('lp-hamburger');
      if (b && !b._lpBound) {
        b._lpBound = true;
        b.addEventListener('click', lpToggleMobile);
        /* Close menu when clicking outside */
        doc.addEventListener('click', function(e){
          if (!e.target.closest('#lp-hamburger') && !e.target.closest('#lp-nav-mobile')) lpCloseMobile();
        });
      }
    } catch(e){}
  }
  function tryBind(){
    bind(document);
    try { bind(window.parent.document); } catch(e){}
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', tryBind);
  else tryBind();
  setTimeout(tryBind, 700);
})();
</script>
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
@media (max-width: 767px) {
    .lp-hero {
        padding: 48px 20px 56px;
        min-height: 100svh; /* small viewport height avoids mobile browser chrome */
    }
    .lp-hero-h1 { font-size: clamp(2.6rem, 12vw, 4rem) !important; letter-spacing: -0.04em !important; }
    .lp-hero-sub { font-size: 0.95rem !important; margin: 20px auto 32px !important; }
    .lp-hero-logo-img { width: 80px !important; height: 80px !important; }
    .lp-hero-ctas { gap: 10px; }
    .lp-hero-corner { display: none; }
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
    <div class="lp-hero-stat-val" data-countup data-target="62.4" data-suffix="%" data-decimals="1">62.4%</div>
  </div>
  <div class="lp-hero-stat lp-hs-2">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Avg ROI</span>
    </div>
    <div class="lp-hero-stat-val" data-countup data-target="18.3" data-prefix="+" data-suffix="%" data-decimals="1">+18.3%</div>
  </div>
  <div class="lp-hero-stat lp-hs-3">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Props / Night</span>
    </div>
    <div class="lp-hero-stat-val" data-countup data-target="300" data-suffix="+">300+</div>
  </div>
  <div class="lp-hero-stat lp-hs-4">
    <div class="lp-hero-stat-row">
      <span class="lp-hero-stat-live"></span>
      <span class="lp-hero-stat-lbl">Members</span>
    </div>
    <div class="lp-hero-stat-val" data-countup data-target="2400" data-suffix="+" data-comma>2,400+</div>
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
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 28px;
    margin: 0 auto;
    position: relative;
}
/* Connector line between steps on desktop */
.lp-steps::before {
    content: '';
    position: absolute;
    top: 52px; left: calc(33% - 14px); right: calc(33% - 14px);
    height: 1px;
    background: linear-gradient(90deg,
        rgba(0,213,89,0.3), rgba(45,158,255,0.3), rgba(192,132,252,0.3));
    pointer-events: none;
    display: none; /* enabled via JS media query */
}
@media (min-width: 780px) {
    .lp-steps::before { display: block; }
}
.lp-step {
    position: relative;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 24px;
    padding: 40px 28px 36px;
    text-align: center;
    transition: border-color 0.35s, transform 0.35s, box-shadow 0.35s, background 0.35s;
    overflow: hidden;
}
/* Accent top bar per step */
.lp-step:nth-child(1) { --step-color: #00D559; --step-glow: rgba(0,213,89,0.35); }
.lp-step:nth-child(2) { --step-color: #2D9EFF; --step-glow: rgba(45,158,255,0.35); }
.lp-step:nth-child(3) { --step-color: #c084fc; --step-glow: rgba(192,132,252,0.35); }
.lp-step::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--step-color), transparent);
    opacity: 0.5;
    transition: opacity 0.3s, height 0.3s;
}
.lp-step:hover {
    border-color: var(--step-color, rgba(0,213,89,0.2));
    border-color: color-mix(in srgb, var(--step-color) 30%, transparent);
    transform: translateY(-6px);
    background: rgba(255,255,255,0.04);
    box-shadow: 0 20px 60px rgba(0,0,0,0.4), 0 0 40px var(--step-glow, rgba(0,213,89,0.1));
}
.lp-step:hover::before { opacity: 1; height: 3px; }
/* Step number — glowing filled circle */
.lp-step-num-wrap {
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 22px;
    width: 64px; height: 64px;
    border-radius: 18px;
    background: linear-gradient(135deg,
        color-mix(in srgb, var(--step-color) 16%, transparent),
        color-mix(in srgb, var(--step-color) 6%, transparent));
    border: 1px solid color-mix(in srgb, var(--step-color) 30%, transparent);
    box-shadow: 0 0 24px color-mix(in srgb, var(--step-color) 20%, transparent);
    transition: box-shadow 0.35s, transform 0.35s;
}
.lp-step:hover .lp-step-num-wrap {
    transform: scale(1.08);
    box-shadow: 0 0 44px color-mix(in srgb, var(--step-color) 40%, transparent);
}
.lp-step-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem; font-weight: 900;
    line-height: 1;
    color: var(--step-color);
    display: block;
    text-shadow: 0 0 20px var(--step-glow);
}
.lp-step-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.08rem; font-weight: 800;
    color: #fff; margin-bottom: 12px;
    letter-spacing: -0.02em;
}
.lp-step-desc {
    font-family: 'Inter', sans-serif;
    font-size: 0.83rem; color: rgba(255,255,255,0.38);
    line-height: 1.72;
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
    /* Staggered entrance */
    opacity: 0;
    transform: translateY(32px);
}
.lp-feat-card.lp-revealed {
    animation: lp-card-in 0.7s cubic-bezier(0.16,1,0.3,1) both;
}
@keyframes lp-card-in {
    from { opacity: 0; transform: translateY(32px); }
    to   { opacity: 1; transform: translateY(0); }
}
/* Animated rotating perimeter border via conic-gradient pseudo */
.lp-feat-card::after {
    content: '';
    position: absolute; inset: -1px;
    border-radius: 21px;
    background: conic-gradient(
        from var(--lp-rot, 0deg),
        transparent 0deg,
        var(--accent-color, #00D559) 20deg,
        transparent 40deg
    );
    opacity: 0;
    z-index: -1;
    transition: opacity 0.4s;
}
.lp-feat-card:hover::after {
    opacity: 0.45;
    animation: lpRotateBorder 4s linear infinite;
}
@property --lp-rot {
    syntax: '<angle>';
    initial-value: 0deg;
    inherits: false;
}
@keyframes lpRotateBorder {
    to { --lp-rot: 360deg; }
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
    transform: translateY(-6px) scale(1.01);
    background: rgba(255,255,255,0.044);
    border-color: rgba(255,255,255,0.0);
    box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 40px var(--accent-glow, rgba(0,213,89,0.12));
}
.lp-feat-card:hover::before { opacity: 1; height: 3px; }
.lp-feat-icon {
    font-size: 2.2rem; line-height: 1;
    margin-bottom: 18px; display: block;
    filter: drop-shadow(0 0 16px var(--accent-glow));
    transition: filter 0.3s, transform 0.3s;
}
.lp-feat-card:hover .lp-feat-icon {
    filter: drop-shadow(0 0 28px var(--accent-glow));
    transform: scale(1.12);
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

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<!-- ══ STATS TRUST BAR ═══════════════════════════════════════ -->
<div style="padding: 80px 24px 0; background: transparent;">
  <div class="lp-trust-bar">
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-green" data-countup data-target="62.4" data-suffix="%" data-decimals="1">62.4%</span>
      <span class="lp-trust-label">Overall Hit Rate</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-blue" data-countup data-target="18.3" data-prefix="+" data-suffix="%" data-decimals="1">+18.3%</span>
      <span class="lp-trust-label">Average ROI</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-gold" data-countup data-target="300" data-suffix="+">300+</span>
      <span class="lp-trust-label">Props / Night</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-purple" data-countup data-target="6">6</span>
      <span class="lp-trust-label">AI Models Active</span>
    </div>
    <div class="lp-trust-stat">
      <span class="lp-trust-big c-green" data-countup data-target="2400" data-suffix="+" data-comma>2,400+</span>
      <span class="lp-trust-label">Active Members</span>
    </div>
  </div>
</div>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<!-- ══ HOW IT WORKS ══════════════════════════════════════════ -->
<div id="lp-how" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">How It Works</div>
    <h2 class="lp-section-h2">Three Steps.<br>One Edge.</h2>
    <p class="lp-section-sub">Our Neural Engine does the heavy lifting — you just pick your plays.</p>
    <div class="lp-steps">
      <div class="lp-step">
        <div class="lp-step-num-wrap"><span class="lp-step-num">01</span></div>
        <div class="lp-step-title">Load Tonight's Slate</div>
        <p class="lp-step-desc">One click pulls live props from PrizePicks, DraftKings &amp; Underdog. Lines, totals, and injury data refreshed in real-time.</p>
      </div>
      <div class="lp-step">
        <div class="lp-step-num-wrap"><span class="lp-step-num">02</span></div>
        <div class="lp-step-title">AI Scores Every Prop</div>
        <p class="lp-step-desc">6 AI models — ensemble, Bayesian, Monte Carlo, regression, CLV tracker &amp; line movement mirror — converge on a single SAFE Score™.</p>
      </div>
      <div class="lp-step">
        <div class="lp-step-num-wrap"><span class="lp-step-num">03</span></div>
        <div class="lp-step-title">Pick Your Plays</div>
        <p class="lp-step-desc">Ranked by edge, filtered by your bankroll strategy. Green lights only. Track results live in your Bet Tracker dashboard.</p>
      </div>
    </div>
  </div>
</div>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

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
<script>
/* Phase 3 – staggered feature card reveal */
(function() {
  function revealCards(doc) {
    var cards = doc.querySelectorAll('.lp-feat-card:not(.lp-revealed)');
    if (!cards.length) return;
    var io = new IntersectionObserver(function(entries) {
      entries.forEach(function(e, i) {
        if (e.isIntersecting) {
          var delay = (Array.prototype.indexOf.call(cards, e.target) % 3) * 90;
          setTimeout(function() {
            e.target.classList.add('lp-revealed');
            e.target.style.animationDelay = delay + 'ms';
          }, delay);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    cards.forEach(function(c) { io.observe(c); });
  }
  function tryReveal() {
    revealCards(document);
    try { revealCards(window.parent.document); } catch(e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tryReveal);
  else tryReveal();
  setTimeout(tryReveal, 600);
  setTimeout(tryReveal, 1800);
})();
</script>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# AI MODEL PERFORMANCE SECTION
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Model Performance Section ──────────────────────────── */
.lp-models-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 18px;
    max-width: 1100px;
    margin: 0 auto;
}
.lp-model-card {
    background: rgba(255,255,255,0.022);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 22px;
    padding: 28px 24px;
    position: relative;
    overflow: hidden;
    transition: border-color .35s, transform .35s, background .35s, box-shadow .35s;
}
.lp-model-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--mc-color), transparent);
    opacity: .5;
    transition: opacity .3s, height .3s;
}
.lp-model-card:hover {
    border-color: color-mix(in srgb, var(--mc-color) 30%, transparent);
    transform: translateY(-5px);
    background: rgba(255,255,255,0.04);
    box-shadow: 0 20px 60px rgba(0,0,0,.45), 0 0 40px color-mix(in srgb, var(--mc-color) 12%, transparent);
}
.lp-model-card:hover::before { opacity: 1; height: 3px; }
.lp-model-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 18px;
}
.lp-model-icon {
    font-size: 1.6rem; line-height: 1;
    filter: drop-shadow(0 0 12px var(--mc-glow));
    transition: filter .3s, transform .3s;
}
.lp-model-card:hover .lp-model-icon {
    filter: drop-shadow(0 0 22px var(--mc-glow));
    transform: scale(1.12) rotate(-3deg);
}
.lp-model-accuracy {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.4rem; font-weight: 900;
    letter-spacing: -0.05em;
    color: var(--mc-color);
    text-shadow: 0 0 18px var(--mc-glow);
}
.lp-model-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: .97rem; font-weight: 800;
    color: #fff; margin-bottom: 6px;
    letter-spacing: -.02em;
}
.lp-model-desc {
    font-family: 'Inter', sans-serif;
    font-size: .8rem; color: rgba(255,255,255,.32);
    line-height: 1.65; margin-bottom: 18px;
}
.lp-model-bar-wrap {
    height: 6px;
    background: rgba(255,255,255,.07);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 6px;
}
.lp-model-bar {
    height: 100%; width: 0%;
    border-radius: 3px;
    background: linear-gradient(90deg, var(--mc-color), var(--mc-color2, var(--mc-color)));
    box-shadow: 0 0 8px var(--mc-glow);
    transition: width 1.4s cubic-bezier(.16,1,.3,1);
}
.lp-model-bar-label {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: .52rem; font-weight: 700;
    color: rgba(255,255,255,.2);
    text-transform: uppercase; letter-spacing: .08em;
}
.lp-model-tag {
    display: inline-flex; align-items: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: .5rem; font-weight: 800;
    color: var(--mc-color);
    background: color-mix(in srgb, var(--mc-color) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--mc-color) 22%, transparent);
    padding: 3px 10px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: .09em;
    margin-bottom: 12px;
}
</style>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<div id="lp-models" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding:0;">
    <div class="lp-section-label">Under the Hood</div>
    <h2 class="lp-section-h2">6 Models.<br>Zero Bias.</h2>
    <p class="lp-section-sub">Every prop runs through 6 independent AI models. They vote. The SAFE Score™ is the verdict.</p>

    <div class="lp-models-grid">

      <div class="lp-model-card" style="--mc-color:#00D559;--mc-glow:rgba(0,213,89,.45);--mc-color2:#00FF85;"
           data-model-pct="68">
        <div class="lp-model-tag">Core Model</div>
        <div class="lp-model-header">
          <span class="lp-model-icon">🧠</span>
          <span class="lp-model-accuracy">68.4%</span>
        </div>
        <div class="lp-model-name">Ensemble Neural Network</div>
        <p class="lp-model-desc">The anchor model. Multi-layer perceptron trained on 3+ years of prop outcomes, game logs, and situational context. Highest single-model accuracy.</p>
        <div class="lp-model-bar-wrap"><div class="lp-model-bar" data-target-pct="68.4"></div></div>
        <div class="lp-model-bar-label"><span>Accuracy</span><span>68.4%</span></div>
      </div>

      <div class="lp-model-card" style="--mc-color:#2D9EFF;--mc-glow:rgba(45,158,255,.45);--mc-color2:#60b4ff;"
           data-model-pct="64">
        <div class="lp-model-tag">Probabilistic</div>
        <div class="lp-model-header">
          <span class="lp-model-icon">📐</span>
          <span class="lp-model-accuracy">64.1%</span>
        </div>
        <div class="lp-model-name">Bayesian Inference</div>
        <p class="lp-model-desc">Updates prop probabilities dynamically as new data arrives — injuries, lineup changes, sharp money flow. Strongest on same-day news events.</p>
        <div class="lp-model-bar-wrap"><div class="lp-model-bar" data-target-pct="64.1"></div></div>
        <div class="lp-model-bar-label"><span>Accuracy</span><span>64.1%</span></div>
      </div>

      <div class="lp-model-card" style="--mc-color:#c084fc;--mc-glow:rgba(192,132,252,.45);--mc-color2:#d8b4fe;"
           data-model-pct="62">
        <div class="lp-model-tag">Simulation</div>
        <div class="lp-model-header">
          <span class="lp-model-icon">🎲</span>
          <span class="lp-model-accuracy">62.8%</span>
        </div>
        <div class="lp-model-name">Monte Carlo Simulation</div>
        <p class="lp-model-desc">Runs 10,000+ game simulations per prop. Maps outcome distributions, calculates true fair probability, exposes mispriced lines with precision.</p>
        <div class="lp-model-bar-wrap"><div class="lp-model-bar" data-target-pct="62.8"></div></div>
        <div class="lp-model-bar-label"><span>Accuracy</span><span>62.8%</span></div>
      </div>

      <div class="lp-model-card" style="--mc-color:#F9C62B;--mc-glow:rgba(249,198,43,.45);--mc-color2:#fde68a;"
           data-model-pct="61">
        <div class="lp-model-tag">Regression</div>
        <div class="lp-model-header">
          <span class="lp-model-icon">📊</span>
          <span class="lp-model-accuracy">61.3%</span>
        </div>
        <div class="lp-model-name">Linear Regression</div>
        <p class="lp-model-desc">Classic statistical approach with modern feature engineering. Stable, interpretable, and best at flagging line discrepancies vs. long-term averages.</p>
        <div class="lp-model-bar-wrap"><div class="lp-model-bar" data-target-pct="61.3"></div></div>
        <div class="lp-model-bar-label"><span>Accuracy</span><span>61.3%</span></div>
      </div>

      <div class="lp-model-card" style="--mc-color:#00D559;--mc-glow:rgba(0,213,89,.45);--mc-color2:#2D9EFF;"
           data-model-pct="66">
        <div class="lp-model-tag">Sharp Money</div>
        <div class="lp-model-header">
          <span class="lp-model-icon">📈</span>
          <span class="lp-model-accuracy">66.2%</span>
        </div>
        <div class="lp-model-name">CLV Tracker</div>
        <p class="lp-model-desc">Monitors closing line value in real-time. Bets that close on the right side of the number generate CLV — the truest signal of a winning bet.</p>
        <div class="lp-model-bar-wrap"><div class="lp-model-bar" data-target-pct="66.2"></div></div>
        <div class="lp-model-bar-label"><span>Accuracy</span><span>66.2%</span></div>
      </div>

      <div class="lp-model-card" style="--mc-color:#2D9EFF;--mc-glow:rgba(45,158,255,.45);--mc-color2:#c084fc;"
           data-model-pct="63">
        <div class="lp-model-tag">Sharp Signal</div>
        <div class="lp-model-header">
          <span class="lp-model-icon">🔭</span>
          <span class="lp-model-accuracy">63.5%</span>
        </div>
        <div class="lp-model-name">Line Movement Mirror</div>
        <p class="lp-model-desc">Tracks bet percentage vs. money percentage splits to detect sharp vs. public action. When sharp money diverges from public — it wins 3 to 1.</p>
        <div class="lp-model-bar-wrap"><div class="lp-model-bar" data-target-pct="63.5"></div></div>
        <div class="lp-model-bar-label"><span>Accuracy</span><span>63.5%</span></div>
      </div>

    </div><!-- /lp-models-grid -->
  </div>
</div>

<script>
/* Animate model accuracy bars on scroll-in */
(function(){
  function animateBars(doc){
    var bars = doc.querySelectorAll('.lp-model-bar[data-target-pct]');
    if(!bars.length) return;
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){
          var pct = parseFloat(e.target.dataset.targetPct) || 0;
          e.target.style.width = pct + '%';
          io.unobserve(e.target);
        }
      });
    }, {threshold: .2});
    bars.forEach(function(b){ io.observe(b); });
  }
  function tryBars(){
    animateBars(document);
    try{ animateBars(window.parent.document); }catch(e){}
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', tryBars);
  else tryBars();
  setTimeout(tryBars, 700);
  setTimeout(tryBars, 2000);
})();
</script>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# GAME REPORT + PLAYER SIMULATOR SHOWCASE
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══ Tool Showcase — shared layout ════════════════════════ */
.lp-tool-showcase {
    max-width: 1100px;
    margin: 0 auto;
}
/* Section label + headline already defined globally */

/* ── Split layout: description left, mock right ─────────── */
.lp-tool-split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 48px;
    align-items: center;
    margin-bottom: 80px;
}
.lp-tool-split.reverse { direction: rtl; }
.lp-tool-split.reverse > * { direction: ltr; }
@media (max-width: 860px) {
    .lp-tool-split, .lp-tool-split.reverse { grid-template-columns: 1fr; direction: ltr; gap: 36px; }
}

/* Left panel — copy */
.lp-tool-copy { display: flex; flex-direction: column; gap: 0; }
.lp-tool-eyebrow {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: .52rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase;
    color: var(--tool-color, #00D559);
    background: color-mix(in srgb, var(--tool-color, #00D559) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--tool-color, #00D559) 22%, transparent);
    padding: 4px 14px; border-radius: 100px;
    width: fit-content; margin-bottom: 22px;
}
.lp-tool-h {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(1.6rem, 2.6vw, 2.4rem);
    font-weight: 900; letter-spacing: -.04em; line-height: 1.18;
    color: #fff; margin-bottom: 16px;
}
.lp-tool-h span {
    background: linear-gradient(90deg, var(--tool-color, #00D559), var(--tool-color2, #00FF85));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.lp-tool-p {
    font-family: 'Inter', sans-serif;
    font-size: .95rem; color: rgba(255,255,255,.42);
    line-height: 1.78; margin-bottom: 28px;
}
.lp-tool-bullets {
    list-style: none; padding: 0; margin: 0 0 32px; display: flex; flex-direction: column; gap: 12px;
}
.lp-tool-bullets li {
    display: flex; align-items: flex-start; gap: 12px;
    font-family: 'Inter', sans-serif;
    font-size: .88rem; color: rgba(255,255,255,.62);
    line-height: 1.6;
}
.lp-tool-bullets li::before {
    content: '';
    width: 18px; height: 18px; border-radius: 6px; flex-shrink: 0; margin-top: 1px;
    background: color-mix(in srgb, var(--tool-color, #00D559) 15%, transparent);
    border: 1px solid color-mix(in srgb, var(--tool-color, #00D559) 35%, transparent);
    display: flex; align-items: center; justify-content: center;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 10 8' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 4l2.5 2.5L9 1' stroke='%2300D559' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: center; background-size: 10px;
}
.lp-tool-bullets li b { color: #fff; font-weight: 700; }
.lp-tool-cta-link {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: .85rem; font-weight: 800; letter-spacing: -.01em;
    color: var(--tool-color, #00D559);
    border-bottom: 1px solid color-mix(in srgb, var(--tool-color, #00D559) 30%, transparent);
    padding-bottom: 2px; text-decoration: none;
    transition: gap .25s, border-color .25s;
    width: fit-content;
}
.lp-tool-cta-link:hover { gap: 14px; border-color: var(--tool-color, #00D559); text-decoration: none; color: var(--tool-color, #00D559); }
.lp-tool-cta-link::after { content: '→'; font-size: .9rem; }

/* Right panel — mock UI card */
.lp-tool-mockup {
    position: relative;
    background: rgba(255,255,255,0.022);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 22px;
    overflow: hidden;
    box-shadow: 0 24px 80px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,0.04);
    transition: transform .4s cubic-bezier(0.16,1,0.3,1), box-shadow .4s;
}
.lp-tool-mockup:hover {
    transform: translateY(-8px) scale(1.015);
    box-shadow: 0 40px 100px rgba(0,0,0,.6),
                0 0 60px color-mix(in srgb, var(--tool-color, #00D559) 14%, transparent),
                0 0 0 1px color-mix(in srgb, var(--tool-color, #00D559) 18%, transparent);
}
/* Chromatic top glow bar */
.lp-tool-mockup::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--tool-color, #00D559), var(--tool-color2, #00FF85), transparent);
    z-index: 2;
}
/* Mock browser chrome */
.lp-mock-chrome {
    display: flex; align-items: center; gap: 8px;
    padding: 12px 16px;
    background: rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.lp-mock-dots { display: flex; gap: 5px; }
.lp-mock-dots span {
    width: 8px; height: 8px; border-radius: 50%;
    background: rgba(255,255,255,0.12);
}
.lp-mock-url {
    flex: 1;
    font-family: 'JetBrains Mono', monospace;
    font-size: .55rem; font-weight: 600;
    color: rgba(255,255,255,0.2);
    letter-spacing: .04em;
    background: rgba(255,255,255,0.04);
    border-radius: 6px; padding: 4px 12px;
    text-align: center;
}
.lp-mock-body { padding: 20px; }

/* ── Game Report mock UI ────────────────────────────────── */
.gr-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px;
}
.gr-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: .82rem; font-weight: 900; color: #fff; letter-spacing: -.02em;
}
.gr-live-badge {
    display: flex; align-items: center; gap: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: .48rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
    color: #00D559;
    background: rgba(0,213,89,0.1); border: 1px solid rgba(0,213,89,0.22);
    padding: 3px 10px; border-radius: 100px;
}
.gr-live-badge::before {
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: #00D559; box-shadow: 0 0 6px #00D559;
    animation: agLivePulse 1.8s ease-in-out infinite;
}
/* Matchup card */
.gr-matchup {
    display: flex; align-items: center; justify-content: space-between;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px; padding: 14px 18px;
    margin-bottom: 14px;
}
.gr-team {
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    font-family: 'Space Grotesk', sans-serif;
}
.gr-team-abbrev {
    font-size: 1.1rem; font-weight: 900; color: #fff; letter-spacing: -.03em;
}
.gr-team-name { font-size: .52rem; color: rgba(255,255,255,.3); letter-spacing: .04em; }
.gr-vs {
    font-family: 'JetBrains Mono', monospace;
    font-size: .62rem; font-weight: 800; color: rgba(255,255,255,.2);
    letter-spacing: .1em;
}
.gr-meta {
    display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px;
}
.gr-meta-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: .5rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
    padding: 3px 10px; border-radius: 6px;
    color: rgba(255,255,255,.4);
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
}
.gr-meta-pill.hi { color: #00D559; background: rgba(0,213,89,.08); border-color: rgba(0,213,89,.18); }
.gr-meta-pill.blue { color: #2D9EFF; background: rgba(45,158,255,.08); border-color: rgba(45,158,255,.18); }
/* Confidence bars */
.gr-bars { display: flex; flex-direction: column; gap: 8px; }
.gr-bar-row { display: flex; align-items: center; gap: 10px; }
.gr-bar-label {
    font-family: 'Inter', sans-serif; font-size: .6rem; font-weight: 600;
    color: rgba(255,255,255,.3); width: 80px; flex-shrink: 0; text-align: right;
}
.gr-bar-track {
    flex: 1; height: 5px; background: rgba(255,255,255,.07); border-radius: 3px; overflow: hidden;
}
.gr-bar-fill {
    height: 100%; border-radius: 3px;
    background: linear-gradient(90deg, var(--gb-c1), var(--gb-c2));
    box-shadow: 0 0 6px var(--gb-glow);
}
.gr-bar-val {
    font-family: 'JetBrains Mono', monospace; font-size: .6rem; font-weight: 800;
    color: var(--gb-c1); width: 32px; text-align: right; flex-shrink: 0;
}

/* ── Player Simulator mock UI ───────────────────────────── */
.ps-player-row {
    display: flex; align-items: center; gap: 14px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px; padding: 14px 16px;
    margin-bottom: 14px;
}
.ps-avatar {
    width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: .72rem; font-weight: 900; color: #020C07;
    background: var(--ps-av-bg, linear-gradient(135deg,#00FF85,#00D559));
    box-shadow: 0 0 14px var(--ps-av-glow, rgba(0,213,89,.4));
}
.ps-info { flex: 1; min-width: 0; }
.ps-name {
    font-family: 'Space Grotesk', sans-serif; font-size: .85rem; font-weight: 800;
    color: #fff; letter-spacing: -.02em; margin-bottom: 3px;
}
.ps-detail {
    font-family: 'JetBrains Mono', monospace; font-size: .5rem; font-weight: 600;
    color: rgba(255,255,255,.28); letter-spacing: .05em; text-transform: uppercase;
}
.ps-dark-horse-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: .47rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
    color: #F9C62B;
    background: rgba(249,198,43,0.1); border: 1px solid rgba(249,198,43,0.25);
    padding: 3px 9px; border-radius: 100px; flex-shrink: 0;
}
.ps-stat-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px;
}
.ps-stat-box {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 10px 8px; text-align: center;
}
.ps-stat-box.dh {
    border-color: rgba(249,198,43,0.3);
    background: rgba(249,198,43,0.06);
    box-shadow: 0 0 14px rgba(249,198,43,0.12);
}
.ps-stat-val {
    font-family: 'Space Grotesk', sans-serif; font-size: .95rem; font-weight: 900;
    color: #fff; letter-spacing: -.03em; line-height: 1;
    margin-bottom: 3px;
}
.ps-stat-box.dh .ps-stat-val { color: #F9C62B; text-shadow: 0 0 12px rgba(249,198,43,.5); }
.ps-stat-label {
    font-family: 'JetBrains Mono', monospace; font-size: .46rem; font-weight: 700;
    color: rgba(255,255,255,.22); text-transform: uppercase; letter-spacing: .07em;
}
.ps-sim-bar-wrap {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 12px 14px;
}
.ps-sim-bar-label {
    display: flex; justify-content: space-between;
    font-family: 'JetBrains Mono', monospace; font-size: .5rem; font-weight: 700;
    color: rgba(255,255,255,.2); text-transform: uppercase; letter-spacing: .07em;
    margin-bottom: 8px;
}
.ps-sim-bar-label span { color: #F9C62B; font-size: .6rem; }
.ps-dist-bar { display: flex; align-items: flex-end; gap: 3px; height: 32px; }
.ps-dist-col {
    flex: 1; border-radius: 3px 3px 0 0;
    background: rgba(255,255,255,0.1);
    transition: background .3s;
}
.ps-dist-col.peak { background: linear-gradient(180deg, #F9C62B, rgba(249,198,43,.4)); box-shadow: 0 0 8px rgba(249,198,43,.3); }
.ps-dist-col.dark-horse { background: linear-gradient(180deg, #00D559, rgba(0,213,89,.4)); box-shadow: 0 0 8px rgba(0,213,89,.3); }
</style>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<div id="lp-tools" style="padding: 100px 24px 0;">
  <div class="lp-tool-showcase">

    <div class="lp-section" style="padding:0;margin-bottom:72px;">
      <div class="lp-section-label">Inside the Platform</div>
      <h2 class="lp-section-h2">See Exactly<br>What You Get.</h2>
      <p class="lp-section-sub">Not a black box. Every tool is built to show its work — so you understand the edge, not just follow it blindly.</p>
    </div>

    <!-- ═══ GAME REPORT ════════════════════════════ -->
    <div class="lp-tool-split lp-reveal">
      <!-- Copy -->
      <div class="lp-tool-copy" style="--tool-color:#00D559;--tool-color2:#00FF85;">
        <div class="lp-tool-eyebrow">📋 Game Report</div>
        <h3 class="lp-tool-h">Every Matchup.<br><span>Fully Decoded.</span></h3>
        <p class="lp-tool-p">
          The Game Report is your pre-game intelligence briefing. Pick any matchup on tonight's slate
          and the platform generates a comprehensive AI breakdown in seconds — covering win probability,
          key player mismatches, pace factors, total projections, and the exact props with the most edge.
        </p>
        <ul class="lp-tool-bullets">
          <li><b>AI Win Probability</b> — 6-model consensus probability for each team, updated as lines move.</li>
          <li><b>Pace &amp; Total Projection</b> — True game total estimate vs. the posted line. Know when the book has it wrong.</li>
          <li><b>Key Player Matchup Cards</b> — Player A vs. Defender B, head-to-head stats, defensive rating exposure.</li>
          <li><b>Top Props for the Matchup</b> — Auto-sorted by SAFE Score™. One click to run full Neural analysis on any prop.</li>
          <li><b>Entry Strategy Matrix</b> — Recommended parlays and single-leg bets based on your risk tolerance.</li>
        </ul>
        <a href="?auth=signup" class="lp-tool-cta-link" style="--tool-color:#00D559;">Access Game Reports Free</a>
      </div>

      <!-- Mock UI -->
      <div class="lp-tool-mockup" style="--tool-color:#00D559;--tool-color2:#00FF85;">
        <div class="lp-mock-chrome">
          <div class="lp-mock-dots"><span></span><span></span><span></span></div>
          <div class="lp-mock-url">smartpickpro.ai · Game Report</div>
        </div>
        <div class="lp-mock-body">
          <div class="gr-header">
            <div class="gr-title">📋 Game Report</div>
            <div class="gr-live-badge">Live Analysis</div>
          </div>

          <!-- Matchup -->
          <div class="gr-matchup">
            <div class="gr-team">
              <div class="gr-team-abbrev" style="color:#00D559;">BOS</div>
              <div class="gr-team-name">Celtics</div>
            </div>
            <div style="text-align:center;">
              <div class="gr-vs">VS</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:.5rem;color:rgba(255,255,255,.18);margin-top:4px;">O/U 218.5</div>
            </div>
            <div class="gr-team">
              <div class="gr-team-abbrev" style="color:#2D9EFF;">MIA</div>
              <div class="gr-team-name">Heat</div>
            </div>
          </div>

          <!-- Meta pills -->
          <div class="gr-meta">
            <span class="gr-meta-pill hi">BOS −5.5</span>
            <span class="gr-meta-pill blue">Pace 99.4</span>
            <span class="gr-meta-pill">TD Garden</span>
            <span class="gr-meta-pill hi">4 Sharp Plays</span>
          </div>

          <!-- Confidence bars -->
          <div class="gr-bars">
            <div class="gr-bar-row">
              <div class="gr-bar-label">BOS Win Prob</div>
              <div class="gr-bar-track">
                <div class="gr-bar-fill" style="width:67%;--gb-c1:#00D559;--gb-c2:#00FF85;--gb-glow:rgba(0,213,89,.4);"></div>
              </div>
              <div class="gr-bar-val" style="--gb-c1:#00D559;">67%</div>
            </div>
            <div class="gr-bar-row">
              <div class="gr-bar-label">Tatum PTS Edge</div>
              <div class="gr-bar-track">
                <div class="gr-bar-fill" style="width:82%;--gb-c1:#F9C62B;--gb-c2:#FFE066;--gb-glow:rgba(249,198,43,.4);"></div>
              </div>
              <div class="gr-bar-val" style="--gb-c1:#F9C62B;">+4.8%</div>
            </div>
            <div class="gr-bar-row">
              <div class="gr-bar-label">SAFE Consensus</div>
              <div class="gr-bar-track">
                <div class="gr-bar-fill" style="width:88%;--gb-c1:#2D9EFF;--gb-c2:#60b4ff;--gb-glow:rgba(45,158,255,.4);"></div>
              </div>
              <div class="gr-bar-val" style="--gb-c1:#2D9EFF;">88</div>
            </div>
            <div class="gr-bar-row">
              <div class="gr-bar-label">Total Proj Δ</div>
              <div class="gr-bar-track">
                <div class="gr-bar-fill" style="width:55%;--gb-c1:#c084fc;--gb-c2:#d8b4fe;--gb-glow:rgba(192,132,252,.4);"></div>
              </div>
              <div class="gr-bar-val" style="--gb-c1:#c084fc;">+3.2</div>
            </div>
          </div>
        </div>
      </div>
    </div><!-- /lp-tool-split -->

    <!-- Divider between tools -->
    <div style="margin-bottom:80px;"><div class="lp-divider"></div></div>

    <!-- ═══ PLAYER SIMULATOR + DARK HORSE ═════════════════ -->
    <div class="lp-tool-split reverse lp-reveal">
      <!-- Mock UI -->
      <div class="lp-tool-mockup" style="--tool-color:#F9C62B;--tool-color2:#FFE066;">
        <div class="lp-mock-chrome">
          <div class="lp-mock-dots"><span></span><span></span><span></span></div>
          <div class="lp-mock-url">smartpickpro.ai · Player Simulator</div>
        </div>
        <div class="lp-mock-body">

          <!-- Player header -->
          <div class="ps-player-row">
            <div class="ps-avatar" style="--ps-av-bg:linear-gradient(135deg,#F9C62B,#FFE066);--ps-av-glow:rgba(249,198,43,.45);">JT</div>
            <div class="ps-info">
              <div class="ps-name">Jayson Tatum</div>
              <div class="ps-detail">BOS · vs MIA · Home · 10,000 sims</div>
            </div>
            <div class="ps-dark-horse-badge">🐴 Dark Horse</div>
          </div>

          <!-- Stat projection grid -->
          <div class="ps-stat-grid">
            <div class="ps-stat-box">
              <div class="ps-stat-val">28.4</div>
              <div class="ps-stat-label">PTS Med</div>
            </div>
            <div class="ps-stat-box dh">
              <div class="ps-stat-val">9.2</div>
              <div class="ps-stat-label">REB ↑ DH</div>
            </div>
            <div class="ps-stat-box">
              <div class="ps-stat-val">5.1</div>
              <div class="ps-stat-label">AST Med</div>
            </div>
            <div class="ps-stat-box">
              <div class="ps-stat-val">3.8</div>
              <div class="ps-stat-label">3PM Med</div>
            </div>
          </div>

          <!-- Distribution chart for highlighted stat -->
          <div class="ps-sim-bar-wrap">
            <div class="ps-sim-bar-label">
              <span>REB Distribution — 10k sims</span>
              <span>Ceiling: 14</span>
            </div>
            <div class="ps-dist-bar">
              <div class="ps-dist-col" style="height:18%;"></div>
              <div class="ps-dist-col" style="height:35%;"></div>
              <div class="ps-dist-col" style="height:55%;"></div>
              <div class="ps-dist-col peak" style="height:90%;"></div>
              <div class="ps-dist-col peak" style="height:100%;"></div>
              <div class="ps-dist-col peak" style="height:82%;"></div>
              <div class="ps-dist-col" style="height:60%;"></div>
              <div class="ps-dist-col dark-horse" style="height:45%;"></div>
              <div class="ps-dist-col dark-horse" style="height:32%;"></div>
              <div class="ps-dist-col" style="height:18%;"></div>
              <div class="ps-dist-col" style="height:10%;"></div>
              <div class="ps-dist-col" style="height:5%;"></div>
            </div>
          </div>

        </div>
      </div>

      <!-- Copy -->
      <div class="lp-tool-copy" style="--tool-color:#F9C62B;--tool-color2:#FFE066;">
        <div class="lp-tool-eyebrow">🔮 Player Simulator</div>
        <h3 class="lp-tool-h">10,000 Sims.<br><span>One True Number.</span></h3>
        <p class="lp-tool-p">
          The Player Simulator runs the Quantum Matrix Engine 5.6 — 10,000 simulated game iterations
          per player, per stat, per night. The result is a full distribution of outcomes: floor, median,
          mean, ceiling, and standard deviation — giving you the actual probability of hitting any prop line,
          not just a gut feeling.
        </p>
        <ul class="lp-tool-bullets" style="--tool-color:#F9C62B;">
          <li><b>Full Stat Line Projection</b> — Points, rebounds, assists, steals, blocks, threes, and turnovers. Every category simulated simultaneously.</li>
          <li><b>Dark Horse Detection 🐴</b> — Automatically flags props where a player's simulated ceiling is meaningfully above the market line. Hidden upside, surfaced for you.</li>
          <li><b>Context-Aware Inputs</b> — Auto-detects tonight's opponent, pace, home/away status, game total, and defensive matchup for each player.</li>
          <li><b>Outcome Distribution Charts</b> — See exactly where outcomes cluster. High variance = better OVER. Low variance = better UNDER.</li>
          <li><b>Compare to Prop Lines</b> — Simulator output syncs with Prop Scanner lines. Spot the gap between projected median and the posted number instantly.</li>
        </ul>
        <a href="?auth=signup" class="lp-tool-cta-link" style="--tool-color:#F9C62B;">Run Your First Simulation Free</a>
      </div>
    </div><!-- /lp-tool-split -->

    <!-- Divider between tools -->
    <div style="margin-bottom:80px;"><div class="lp-divider"></div></div>

    <!-- ═══ BET TRACKER DASHBOARD ════════════════════════════ -->
    <div class="lp-tool-split lp-reveal">
      <!-- Copy -->
      <div class="lp-tool-copy" style="--tool-color:#c084fc;--tool-color2:#d8b4fe;">
        <div class="lp-tool-eyebrow">📊 Bet Tracker Dashboard</div>
        <h3 class="lp-tool-h">Every Bet.<br><span>Full Accountability.</span></h3>
        <p class="lp-tool-p">
          Stop guessing if you're profitable. The Bet Tracker logs every pick the Neural Engine
          surfaces — platform, stat type, line, direction, and result — and builds your full
          P&amp;L history automatically. Filter by tier, platform, date, or player. Know exactly
          where your edge is coming from.
        </p>
        <ul class="lp-tool-bullets" style="--tool-color:#c084fc;">
          <li><b>Auto-Logged Picks</b> — Every qualifying AI analysis result is stored instantly. No manual entry.</li>
          <li><b>Model Health Tab</b> — Win rate by tier (Platinum → Bronze) with tilt alerts and streak detection.</li>
          <li><b>Platform Picks Tab</b> — Filter by PrizePicks, DraftKings, or Underdog. See which book gives you the most edge.</li>
          <li><b>Full P&amp;L History</b> — ROI over time, rolling 14-day win rate, and a calendar heatmap of your results.</li>
          <li><b>Auto-Resolve</b> — Results are pulled from live game logs. Wins and losses recorded without lifting a finger.</li>
        </ul>
        <a href="?auth=signup" class="lp-tool-cta-link" style="--tool-color:#c084fc;">Track Your First Picks Free</a>
      </div>

      <!-- Mock UI -->
      <div class="lp-tool-mockup" style="--tool-color:#c084fc;--tool-color2:#d8b4fe;">
        <div class="lp-mock-chrome">
          <div class="lp-mock-dots"><span></span><span></span><span></span></div>
          <div class="lp-mock-url">smartpickpro.ai · Bet Tracker</div>
        </div>
        <div class="lp-mock-body" style="padding:16px;">

          <!-- Stat summary grid -->
          <div style="
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:8px;
            margin-bottom:14px;
          ">
            <div style="background:rgba(192,132,252,0.07);border:1px solid rgba(192,132,252,0.18);border-radius:10px;padding:10px 12px;text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:900;color:#c084fc;letter-spacing:-0.04em;line-height:1;">62.4%</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:.09em;margin-top:4px;">Win Rate</div>
            </div>
            <div style="background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.18);border-radius:10px;padding:10px 12px;text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:900;color:#00D559;letter-spacing:-0.04em;line-height:1;">127</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:.09em;margin-top:4px;">Total Picks</div>
            </div>
            <div style="background:rgba(0,213,89,0.05);border:1px solid rgba(0,213,89,0.14);border-radius:10px;padding:10px 12px;text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:900;color:#00D559;letter-spacing:-0.04em;line-height:1;">✅ 79</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:.09em;margin-top:4px;">Wins</div>
            </div>
            <div style="background:rgba(255,68,68,0.05);border:1px solid rgba(255,68,68,0.14);border-radius:10px;padding:10px 12px;text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:900;color:#ff6b6b;letter-spacing:-0.04em;line-height:1;">❌ 48</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:.09em;margin-top:4px;">Losses</div>
            </div>
          </div>

          <!-- Filters toggle row -->
          <div style="
            display:flex;align-items:center;justify-content:space-between;
            background:rgba(255,255,255,0.03);
            border:1px solid rgba(255,255,255,0.07);
            border-radius:8px;padding:7px 12px;
            margin-bottom:12px;cursor:pointer;
          ">
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:.08em;">⚙️ Filters</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:rgba(255,255,255,0.2);">▼</span>
          </div>

          <!-- Tab row — horizontal scrollable -->
          <div style="
            display:flex;gap:6px;
            overflow-x:auto;
            scrollbar-width:none;
            padding-bottom:2px;
            margin-bottom:12px;
            white-space:nowrap;
            -webkit-overflow-scrolling:touch;
          ">
            <div style="flex-shrink:0;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:800;padding:5px 12px;border-radius:100px;background:rgba(192,132,252,0.15);border:1px solid rgba(192,132,252,0.3);color:#c084fc;letter-spacing:.04em;text-transform:uppercase;">📊 Health</div>
            <div style="flex-shrink:0;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:700;padding:5px 12px;border-radius:100px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.35);letter-spacing:.04em;text-transform:uppercase;">🤖 AI Picks</div>
            <div style="flex-shrink:0;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:700;padding:5px 12px;border-radius:100px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.35);letter-spacing:.04em;text-transform:uppercase;">📋 All Picks</div>
            <div style="flex-shrink:0;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:700;padding:5px 12px;border-radius:100px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.35);letter-spacing:.04em;text-transform:uppercase;">🎙️ Joseph</div>
            <div style="flex-shrink:0;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:700;padding:5px 12px;border-radius:100px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.35);letter-spacing:.04em;text-transform:uppercase;">📅 History</div>
          </div>

          <!-- Recent picks rows -->
          <div style="display:flex;flex-direction:column;gap:6px;">
            <div style="display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;background:rgba(0,213,89,0.04);border:1px solid rgba(0,213,89,0.12);border-radius:8px;padding:8px 10px;">
              <div>
                <div style="font-family:'Space Grotesk',sans-serif;font-size:0.68rem;font-weight:800;color:#fff;">J. Tatum — Points</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.5rem;color:rgba(255,255,255,0.3);margin-top:2px;">OVER 27.5 · PrizePicks</div>
              </div>
              <span style="font-family:'Space Grotesk',sans-serif;font-size:0.62rem;font-weight:800;color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.2);border-radius:6px;padding:3px 8px;">✅ WIN</span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:rgba(255,255,255,0.2);">92</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;background:rgba(255,68,68,0.04);border:1px solid rgba(255,68,68,0.10);border-radius:8px;padding:8px 10px;">
              <div>
                <div style="font-family:'Space Grotesk',sans-serif;font-size:0.68rem;font-weight:800;color:#fff;">N. Jokic — Rebounds</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.5rem;color:rgba(255,255,255,0.3);margin-top:2px;">OVER 12.5 · DraftKings</div>
              </div>
              <span style="font-family:'Space Grotesk',sans-serif;font-size:0.62rem;font-weight:800;color:#ff6b6b;background:rgba(255,68,68,0.1);border:1px solid rgba(255,68,68,0.2);border-radius:6px;padding:3px 8px;">❌ LOSS</span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:rgba(255,255,255,0.2);">87</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;background:rgba(0,213,89,0.04);border:1px solid rgba(0,213,89,0.12);border-radius:8px;padding:8px 10px;">
              <div>
                <div style="font-family:'Space Grotesk',sans-serif;font-size:0.68rem;font-weight:800;color:#fff;">S. Curry — Threes</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.5rem;color:rgba(255,255,255,0.3);margin-top:2px;">UNDER 3.5 · Underdog</div>
              </div>
              <span style="font-family:'Space Grotesk',sans-serif;font-size:0.62rem;font-weight:800;color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.2);border-radius:6px;padding:3px 8px;">✅ WIN</span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:rgba(255,255,255,0.2);">84</span>
            </div>
          </div>

        </div>
      </div>
    </div><!-- /lp-tool-split -->

  </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# LIVE PICKS PREVIEW SECTION  (#lp-picks)
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Live Picks Preview ─────────────────────────────────── */
.lp-picks-grid {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-width: 820px;
    margin: 0 auto;
}
.lp-pick-row {
    display: grid;
    grid-template-columns: 44px 1fr auto auto 110px;
    align-items: center;
    gap: 20px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 18px 22px;
    transition: border-color 0.3s, transform 0.3s, background 0.3s, box-shadow 0.3s;
    position: relative;
    overflow: hidden;
}
.lp-pick-row::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--pick-color, #00D559);
    border-radius: 18px 0 0 18px;
    box-shadow: 0 0 14px var(--pick-glow, rgba(0,213,89,0.5));
}
.lp-pick-row:hover {
    border-color: rgba(255,255,255,0.12);
    transform: translateX(4px);
    background: rgba(255,255,255,0.04);
    box-shadow: 0 8px 32px rgba(0,0,0,0.35), 0 0 30px var(--pick-glow, rgba(0,213,89,0.08));
}
/* Rank badge */
.lp-pick-rank {
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; font-weight: 900;
    color: var(--pick-color, #00D559);
    background: color-mix(in srgb, var(--pick-color, #00D559) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--pick-color, #00D559) 25%, transparent);
    flex-shrink: 0;
}
/* Player info */
.lp-pick-info { min-width: 0; }
.lp-pick-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.95rem; font-weight: 800;
    color: #fff; margin-bottom: 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.lp-pick-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; font-weight: 600;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase; letter-spacing: .08em;
    display: flex; align-items: center; gap: 8px;
}
.lp-pick-meta-sep { color: rgba(255,255,255,0.12); }
/* Prop */
.lp-pick-prop {
    text-align: right;
}
.lp-pick-prop-val {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem; font-weight: 900;
    color: #fff;
    letter-spacing: -0.03em;
}
.lp-pick-prop-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem; font-weight: 700;
    color: rgba(255,255,255,0.25);
    text-transform: uppercase; letter-spacing: .08em;
    margin-top: 3px;
}
/* Direction badge */
.lp-pick-dir {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.75rem; font-weight: 800;
    padding: 6px 14px; border-radius: 100px;
    letter-spacing: .04em; text-transform: uppercase;
    flex-shrink: 0;
}
.lp-pick-dir.over  { color:#00D559; background:rgba(0,213,89,0.1);  border:1px solid rgba(0,213,89,0.25);  }
.lp-pick-dir.under { color:#2D9EFF; background:rgba(45,158,255,0.1);border:1px solid rgba(45,158,255,0.25);}
/* SAFE Score meter */
.lp-pick-safe {
    text-align: right;
}
.lp-pick-safe-score {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.25rem; font-weight: 900;
    letter-spacing: -0.04em;
    color: var(--pick-color, #00D559);
    text-shadow: 0 0 16px var(--pick-glow, rgba(0,213,89,0.5));
    line-height: 1;
}
.lp-pick-safe-bar-wrap {
    width: 80px; height: 4px;
    background: rgba(255,255,255,0.08);
    border-radius: 2px;
    margin: 6px 0 0 auto;
    overflow: hidden;
}
.lp-pick-safe-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--pick-color), var(--pick-color-2, var(--pick-color)));
    border-radius: 2px;
    box-shadow: 0 0 8px var(--pick-glow);
    transition: width 1.2s cubic-bezier(0.16,1,0.3,1);
}
.lp-pick-safe-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.48rem; font-weight: 700;
    color: rgba(255,255,255,0.22);
    text-transform: uppercase; letter-spacing: .09em;
    text-align: right; margin-top: 4px;
}
/* Platform pill inside meta */
.lp-pick-plat {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem; font-weight: 800;
    padding: 2px 8px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: .06em;
}
.lp-plat-pp   { color: #00D559; background: rgba(0,213,89,0.08);  }
.lp-plat-dk   { color: #2D9EFF; background: rgba(45,158,255,0.08);}
.lp-plat-ud   { color: #F9C62B; background: rgba(249,198,43,0.08);}
/* Blurred locked rows */
.lp-pick-row.locked {
    filter: blur(3px);
    opacity: 0.45;
    pointer-events: none;
}
.lp-picks-lock-overlay {
    text-align: center;
    padding: 36px 24px 28px;
    background: rgba(3,6,14,0.7);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 20px;
    backdrop-filter: blur(12px);
    max-width: 420px;
    margin: 8px auto 0;
}
.lp-picks-lock-icon {
    font-size: 2rem; margin-bottom: 14px;
}
.lp-picks-lock-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem; font-weight: 800;
    color: #fff; margin-bottom: 8px;
}
.lp-picks-lock-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem; color: rgba(255,255,255,0.35);
    line-height: 1.6; margin-bottom: 20px;
}
/* Player headshot avatar */
.lp-pick-headshot {
    width: 40px; height: 40px;
    border-radius: 50%;
    object-fit: cover;
    border: 1.5px solid color-mix(in srgb, var(--pick-color, #00D559) 35%, transparent);
    background: rgba(255,255,255,0.04);
    flex-shrink: 0;
    display: block;
}

/* Responsive: collapse prop + dir on small screens */
@media (max-width: 680px) {
    .lp-pick-row {
        grid-template-columns: 36px 1fr auto 88px;
    }
    .lp-pick-dir { display: none; }
    .lp-pick-headshot { width: 32px; height: 32px; }
}
@media (max-width: 480px) {
    .lp-pick-row { grid-template-columns: 1fr auto; padding: 14px 16px; }
    .lp-pick-headshot { display: none; }
    .lp-pick-safe-bar-wrap { width: 56px; }
}
</style>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<!-- ══ LIVE PICKS PREVIEW ════════════════════════════════════ -->
<div id="lp-picks" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding:0;">
    <div class="lp-section-label">Sample Picks</div>
    <h2 class="lp-section-h2">Tonight's<br>Top Plays.</h2>
    <p class="lp-section-sub">A live snapshot of what members see every night — scored, ranked, and ready to deploy.</p>

    <div class="lp-picks-grid">

      <!-- Pick 1 — green, top SAFE -->
      <div class="lp-pick-row" style="--pick-color:#00D559;--pick-glow:rgba(0,213,89,0.3);--pick-color-2:#00FF85;">
        <img class="lp-pick-headshot" src="https://cdn.nba.com/headshots/nba/latest/1040x760/1628369.png" alt="Jayson Tatum" onerror="this.style.display='none'">
        <div class="lp-pick-info">
          <div class="lp-pick-name">Jayson Tatum — Points</div>
          <div class="lp-pick-meta">
            <span class="lp-pick-plat lp-plat-pp">PP</span>
            <span class="lp-pick-meta-sep">|</span>
            <span>BOS vs MIA · Game 3</span>
            <span class="lp-pick-meta-sep">|</span>
            <span>+4.8% CLV edge</span>
          </div>
        </div>
        <div class="lp-pick-prop">
          <div class="lp-pick-prop-val">27.5</div>
          <div class="lp-pick-prop-label">Line</div>
        </div>
        <span class="lp-pick-dir over">▲ Over</span>
        <div class="lp-pick-safe">
          <div class="lp-pick-safe-score">91</div>
          <div class="lp-pick-safe-bar-wrap"><div class="lp-pick-safe-bar" style="width:91%;"></div></div>
          <div class="lp-pick-safe-label">SAFE Score™</div>
        </div>
      </div>

      <!-- Pick 2 — gold -->
      <div class="lp-pick-row" style="--pick-color:#F9C62B;--pick-glow:rgba(249,198,43,0.3);--pick-color-2:#FFE066;">
        <img class="lp-pick-headshot" src="https://cdn.nba.com/headshots/nba/latest/1040x760/203999.png" alt="Nikola Jokic" onerror="this.style.display='none'">
        <div class="lp-pick-info">
          <div class="lp-pick-name">Nikola Jokic — Rebounds</div>
          <div class="lp-pick-meta">
            <span class="lp-pick-plat lp-plat-dk">DK</span>
            <span class="lp-pick-meta-sep">|</span>
            <span>DEN vs MIN · Reg Season</span>
            <span class="lp-pick-meta-sep">|</span>
            <span>Sharp line movement</span>
          </div>
        </div>
        <div class="lp-pick-prop">
          <div class="lp-pick-prop-val">12.5</div>
          <div class="lp-pick-prop-label">Line</div>
        </div>
        <span class="lp-pick-dir over">▲ Over</span>
        <div class="lp-pick-safe">
          <div class="lp-pick-safe-score">87</div>
          <div class="lp-pick-safe-bar-wrap"><div class="lp-pick-safe-bar" style="width:87%;"></div></div>
          <div class="lp-pick-safe-label">SAFE Score™</div>
        </div>
      </div>

      <!-- Pick 3 — blue -->
      <div class="lp-pick-row" style="--pick-color:#2D9EFF;--pick-glow:rgba(45,158,255,0.3);--pick-color-2:#60b4ff;">
        <img class="lp-pick-headshot" src="https://cdn.nba.com/headshots/nba/latest/1040x760/201939.png" alt="Stephen Curry" onerror="this.style.display='none'">
        <div class="lp-pick-info">
          <div class="lp-pick-name">Stephen Curry — 3-Pointers Made</div>
          <div class="lp-pick-meta">
            <span class="lp-pick-plat lp-plat-ud">UD</span>
            <span class="lp-pick-meta-sep">|</span>
            <span>GSW vs LAL · Playoffs</span>
            <span class="lp-pick-meta-sep">|</span>
            <span>6-model consensus</span>
          </div>
        </div>
        <div class="lp-pick-prop">
          <div class="lp-pick-prop-val">3.5</div>
          <div class="lp-pick-prop-label">Line</div>
        </div>
        <span class="lp-pick-dir under">▼ Under</span>
        <div class="lp-pick-safe">
          <div class="lp-pick-safe-score">84</div>
          <div class="lp-pick-safe-bar-wrap"><div class="lp-pick-safe-bar" style="width:84%;"></div></div>
          <div class="lp-pick-safe-label">SAFE Score™</div>
        </div>
      </div>

      <!-- Locked rows -->
      <div class="lp-pick-row locked" style="--pick-color:#c084fc;--pick-glow:rgba(192,132,252,0.3);">
        <img class="lp-pick-headshot" src="https://cdn.nba.com/headshots/nba/latest/1040x760/1629029.png" alt="Luka Doncic" onerror="this.style.display='none'">
        <div class="lp-pick-info">
          <div class="lp-pick-name">Luka Doncic — Assists</div>
          <div class="lp-pick-meta"><span class="lp-pick-plat lp-plat-pp">PP</span><span class="lp-pick-meta-sep">|</span><span>DAL vs OKC</span></div>
        </div>
        <div class="lp-pick-prop"><div class="lp-pick-prop-val">8.5</div></div>
        <span class="lp-pick-dir over">▲ Over</span>
        <div class="lp-pick-safe"><div class="lp-pick-safe-score">81</div></div>
      </div>
      <div class="lp-pick-row locked" style="--pick-color:#00D559;--pick-glow:rgba(0,213,89,0.2);">
        <img class="lp-pick-headshot" src="https://cdn.nba.com/headshots/nba/latest/1040x760/1630162.png" alt="Anthony Edwards" onerror="this.style.display='none'">
        <div class="lp-pick-info">
          <div class="lp-pick-name">Anthony Edwards — Points + Rebounds</div>
          <div class="lp-pick-meta"><span class="lp-pick-plat lp-plat-dk">DK</span><span class="lp-pick-meta-sep">|</span><span>MIN vs DEN</span></div>
        </div>
        <div class="lp-pick-prop"><div class="lp-pick-prop-val">34.5</div></div>
        <span class="lp-pick-dir over">▲ Over</span>
        <div class="lp-pick-safe"><div class="lp-pick-safe-score">79</div></div>
      </div>

    </div><!-- /lp-picks-grid -->

    <!-- Unlock CTA -->
    <div class="lp-picks-lock-overlay">
      <div class="lp-picks-lock-icon">🔒</div>
      <div class="lp-picks-lock-headline">+297 More Props Waiting</div>
      <p class="lp-picks-lock-sub">
        Free members see the top 3. Sign up free — no card required —
        and unlock tonight's full 300+ prop Neural Engine scan.
      </p>
      <a class="lp-cta-primary" href="?auth=signup" style="display:inline-flex;font-size:.88rem;padding:13px 32px;">
        ⚡ Unlock All Picks Free
      </a>
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
/* ── Popular card: elevated 3D treatment ─────────────────── */
.lp-price-card.popular {
    border-color: transparent;
    background: rgba(0,213,89,0.045);
    box-shadow:
        0 0 0 1px rgba(0,213,89,0.18),
        0 0 80px rgba(0,213,89,0.14),
        0 32px 80px rgba(0,0,0,0.5),
        inset 0 1px 0 rgba(0,213,89,0.12);
    transform: scale(1.025);
    z-index: 1;
}
.lp-price-card.popular:hover {
    transform: scale(1.025) translateY(-8px);
    box-shadow:
        0 0 0 1px rgba(0,213,89,0.3),
        0 0 120px rgba(0,213,89,0.22),
        0 40px 100px rgba(0,0,0,0.55),
        inset 0 1px 0 rgba(0,213,89,0.18);
}
/* Moving perimeter glow border on popular card */
.lp-price-card.popular::after {
    content: '';
    position: absolute; inset: -1px;
    border-radius: 25px;
    background: conic-gradient(
        from var(--pc-rot, 0deg),
        transparent 0deg,
        #00FF85 20deg,
        #2D9EFF 50deg,
        #00D559 80deg,
        transparent 100deg
    );
    z-index: -1;
    opacity: 0.5;
    animation: pcRotateBorder 6s linear infinite;
}
@property --pc-rot {
    syntax: '<angle>';
    initial-value: 0deg;
    inherits: false;
}
@keyframes pcRotateBorder {
    to { --pc-rot: 360deg; }
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
    box-shadow: 0 0 28px rgba(0,213,89,0.55);
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

/* ── Testimonials – infinite marquee ─────────────────────── */
.lp-testi-marquee-wrap {
    overflow: hidden;
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    /* fade edges */
    -webkit-mask-image: linear-gradient(90deg, transparent 0%, black 8%, black 92%, transparent 100%);
    mask-image: linear-gradient(90deg, transparent 0%, black 8%, black 92%, transparent 100%);
}
.lp-testi-marquee-track {
    display: flex;
    gap: 20px;
    width: max-content;
    animation: testiScroll 42s linear infinite;
}
.lp-testi-marquee-track:hover { animation-play-state: paused; }
@keyframes testiScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.lp-testimonials {
    display: contents; /* replaced by marquee */
}
.lp-testi-card {
    background: rgba(255,255,255,0.028);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 22px;
    padding: 28px 26px;
    width: 320px;
    flex-shrink: 0;
    transition: transform 0.35s, border-color 0.35s, box-shadow 0.35s, background 0.35s;
    position: relative;
    overflow: hidden;
}
.lp-testi-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.4), transparent);
    opacity: 0;
    transition: opacity 0.35s;
}
.lp-testi-card:hover {
    transform: translateY(-6px) scale(1.015);
    border-color: rgba(0,213,89,0.2);
    background: rgba(0,213,89,0.025);
    box-shadow: 0 0 50px rgba(0,213,89,0.08), 0 20px 50px rgba(0,0,0,0.5);
}
.lp-testi-card:hover::before { opacity: 1; }
.lp-testi-stars {
    color: #F9C62B;
    font-size: 0.85rem;
    letter-spacing: 2px;
    margin-bottom: 14px;
}
.lp-testi-quote {
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem; line-height: 1.78;
    color: rgba(255,255,255,0.52);
    margin-bottom: 20px;
    font-style: italic;
}
.lp-testi-quote::before { content: '\\201C'; color: #00D559; font-style: normal; font-size: 1.2rem; }
.lp-testi-quote::after  { content: '\\201D'; color: #00D559; font-style: normal; font-size: 1.2rem; }
.lp-testi-author {
    display: flex; align-items: center; gap: 12px;
}
.lp-testi-avatar {
    width: 40px; height: 40px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.75rem; font-weight: 800;
    color: #020C07;
    background: var(--av-bg, linear-gradient(135deg, #00FF85, #00D559));
    flex-shrink: 0;
    box-shadow: 0 0 18px var(--av-glow, rgba(0,213,89,0.4));
}
.lp-testi-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.84rem; font-weight: 700;
    color: #fff;
}
.lp-testi-handle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; color: rgba(255,255,255,0.25);
    letter-spacing: .04em;
    margin-top: 2px;
}
.lp-testi-stat {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.56rem; font-weight: 800;
    color: #00D559;
    background: rgba(0,213,89,0.08);
    border: 1px solid rgba(0,213,89,0.18);
    border-radius: 100px;
    padding: 3px 10px;
    margin-bottom: 14px;
}
</style>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<!-- ══ PRICING ══════════════════════════════════════════════ -->
<div id="lp-pricing" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">Pricing</div>
    <h2 class="lp-section-h2">Start Free.<br>Scale Your Edge.</h2>
    <p class="lp-section-sub">No credit card to start. Upgrade when you're ready to unlock the full Neural Engine.</p>

    <!-- Billing toggle -->
    <div style="display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:44px;">
      <span id="lp-toggle-mo-label" style="font-family:'Space Grotesk',sans-serif;font-size:.85rem;
            font-weight:700;color:#fff;transition:color .25s;">Monthly</span>
      <div id="lp-billing-toggle"
           onclick="lpToggleBilling()"
           style="width:52px;height:28px;border-radius:100px;background:rgba(0,213,89,0.15);
                  border:1px solid rgba(0,213,89,0.3);position:relative;cursor:pointer;
                  transition:background .3s;flex-shrink:0;">
        <div id="lp-toggle-knob"
             style="position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;
                    background:#00D559;box-shadow:0 0 10px rgba(0,213,89,0.6);
                    transition:transform .3s cubic-bezier(0.34,1.56,0.64,1);"></div>
      </div>
      <span id="lp-toggle-an-label" style="font-family:'Space Grotesk',sans-serif;font-size:.85rem;
            font-weight:700;color:rgba(255,255,255,0.38);transition:color .25s;">
        Annual
        <span id="lp-annual-badge" style="
          font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:800;
          color:#020C07;background:#00D559;border-radius:100px;padding:2px 8px;
          margin-left:6px;letter-spacing:.06em;vertical-align:middle;opacity:0.85;">
          SAVE 20%
        </span>
      </span>
    </div>

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

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<!-- ══ TESTIMONIALS ═════════════════════════════════════════ -->
<div id="lp-testimonials" style="padding: 80px 24px 0;">
  <div class="lp-section" style="padding: 0;">
    <div class="lp-section-label">Member Results</div>
    <h2 class="lp-section-h2">The Numbers<br>Don't Lie.</h2>
    <p class="lp-section-sub">Real members. Real results. No cherry-picked picks — full P&amp;L tracked in the dashboard.</p>
  </div>

  <!-- Infinite marquee — hover to pause -->
  <div class="lp-testi-marquee-wrap">
    <div class="lp-testi-marquee-track">

      <!-- Card 1 -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">📈 +23% ROI This Month</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Hit 8 of my last 10 PrizePicks entries using the SAFE Score filter. ROI sitting at +23% for the month. Nothing else comes close.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#00FF85,#00D559);--av-glow:rgba(0,213,89,0.4);">MR</div>
          <div><div class="lp-testi-name">Marcus R.</div><div class="lp-testi-handle">Smart Money · 4 months</div></div>
        </div>
      </div>

      <!-- Card 2 -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">⚡ CLV +4.1% last week</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">The line movement alerts alone paid for 6 months of the sub. Caught a massive CLV swing on Tatum points last week. This tool is ridiculous.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#60b4ff,#2D9EFF);--av-glow:rgba(45,158,255,0.4);">JT</div>
          <div><div class="lp-testi-name">Jake T.</div><div class="lp-testi-handle">Sharp IQ · 7 months</div></div>
        </div>
      </div>

      <!-- Card 3 -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">🎯 64% hit rate / 200+ picks</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">I was skeptical — now I don't touch a prop without the Neural Engine first. 64% hit rate over 200+ tracked picks. It's not even close.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#d8b4fe,#c084fc);--av-glow:rgba(192,132,252,0.4);">AL</div>
          <div><div class="lp-testi-name">Alex L.</div><div class="lp-testi-handle">Smart Money · 2 months</div></div>
        </div>
      </div>

      <!-- Card 4 -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">💰 +$1,840 net in 30 days</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Was losing money every week before this. First month using Smart Pick Pro I tracked +$1,840 net. The bankroll optimizer alone is worth the price.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#fde68a,#F9C62B);--av-glow:rgba(249,198,43,0.4);">RK</div>
          <div><div class="lp-testi-name">Ryan K.</div><div class="lp-testi-handle">Smart Money · 3 months</div></div>
        </div>
      </div>

      <!-- Card 5 -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">🔥 9/10 on last slate</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Went 9 for 10 on my last DraftKings slate using nothing but the top-10 SAFE Score picks. I actually screenshotted it because I didn't believe it.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#00FF85,#00D559);--av-glow:rgba(0,213,89,0.4);">TW</div>
          <div><div class="lp-testi-name">Tyler W.</div><div class="lp-testi-handle">Sharp IQ · 5 months</div></div>
        </div>
      </div>

      <!-- Card 6 -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">📊 Verified 18.6% ROI</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">The Bet Tracker dashboard showing my 18.6% ROI with full P&amp;L history is the first time I've ever had proof that my process actually works. This is it.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#60b4ff,#2D9EFF);--av-glow:rgba(45,158,255,0.4);">SN</div>
          <div><div class="lp-testi-name">Sarah N.</div><div class="lp-testi-handle">Smart Money · 6 months</div></div>
        </div>
      </div>

      <!-- Duplicate set for seamless loop -->
      <div class="lp-testi-card">
        <div class="lp-testi-stat">📈 +23% ROI This Month</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Hit 8 of my last 10 PrizePicks entries using the SAFE Score filter. ROI sitting at +23% for the month. Nothing else comes close.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#00FF85,#00D559);--av-glow:rgba(0,213,89,0.4);">MR</div>
          <div><div class="lp-testi-name">Marcus R.</div><div class="lp-testi-handle">Smart Money · 4 months</div></div>
        </div>
      </div>
      <div class="lp-testi-card">
        <div class="lp-testi-stat">⚡ CLV +4.1% last week</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">The line movement alerts alone paid for 6 months of the sub. Caught a massive CLV swing on Tatum points last week. This tool is ridiculous.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#60b4ff,#2D9EFF);--av-glow:rgba(45,158,255,0.4);">JT</div>
          <div><div class="lp-testi-name">Jake T.</div><div class="lp-testi-handle">Sharp IQ · 7 months</div></div>
        </div>
      </div>
      <div class="lp-testi-card">
        <div class="lp-testi-stat">🎯 64% hit rate / 200+ picks</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">I was skeptical — now I don't touch a prop without the Neural Engine first. 64% hit rate over 200+ tracked picks. It's not even close.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#d8b4fe,#c084fc);--av-glow:rgba(192,132,252,0.4);">AL</div>
          <div><div class="lp-testi-name">Alex L.</div><div class="lp-testi-handle">Smart Money · 2 months</div></div>
        </div>
      </div>
      <div class="lp-testi-card">
        <div class="lp-testi-stat">💰 +$1,840 net in 30 days</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Was losing money every week before this. First month using Smart Pick Pro I tracked +$1,840 net. The bankroll optimizer alone is worth the price.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#fde68a,#F9C62B);--av-glow:rgba(249,198,43,0.4);">RK</div>
          <div><div class="lp-testi-name">Ryan K.</div><div class="lp-testi-handle">Smart Money · 3 months</div></div>
        </div>
      </div>
      <div class="lp-testi-card">
        <div class="lp-testi-stat">🔥 9/10 on last slate</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">Went 9 for 10 on my last DraftKings slate using nothing but the top-10 SAFE Score picks. I actually screenshotted it because I didn't believe it.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#00FF85,#00D559);--av-glow:rgba(0,213,89,0.4);">TW</div>
          <div><div class="lp-testi-name">Tyler W.</div><div class="lp-testi-handle">Sharp IQ · 5 months</div></div>
        </div>
      </div>
      <div class="lp-testi-card">
        <div class="lp-testi-stat">📊 Verified 18.6% ROI</div>
        <div class="lp-testi-stars">★★★★★</div>
        <p class="lp-testi-quote">The Bet Tracker dashboard showing my 18.6% ROI with full P&amp;L history is the first time I've ever had proof that my process actually works. This is it.</p>
        <div class="lp-testi-author">
          <div class="lp-testi-avatar" style="--av-bg:linear-gradient(135deg,#60b4ff,#2D9EFF);--av-glow:rgba(45,158,255,0.4);">SN</div>
          <div><div class="lp-testi-name">Sarah N.</div><div class="lp-testi-handle">Smart Money · 6 months</div></div>
        </div>
      </div>

    </div><!-- /lp-testi-marquee-track -->
  </div><!-- /lp-testi-marquee-wrap -->
</div>

<script>
/* ── Pricing billing toggle ───────────────────────────── */
(function(){
  var annual = false;
  var prices = {
    sharp:  { mo: '$9<span class="lp-price-amount-sub">.99 / mo</span>',  an: '$7<span class="lp-price-amount-sub">.99 / mo</span>' },
    smart:  { mo: '$24<span class="lp-price-amount-sub">.99 / mo</span>', an: '$19<span class="lp-price-amount-sub">.99 / mo</span>' }
  };

  function updatePricing(doc){
    var sharpAmt = doc.querySelectorAll('.lp-pc-sharp .lp-price-amount');
    var smartAmt = doc.querySelectorAll('.lp-pc-smart .lp-price-amount');
    var sharpPer = doc.querySelectorAll('.lp-pc-sharp .lp-price-period');
    var smartPer = doc.querySelectorAll('.lp-pc-smart .lp-price-period');
    var knob    = doc.getElementById('lp-toggle-knob');
    var moLabel = doc.getElementById('lp-toggle-mo-label');
    var anLabel = doc.getElementById('lp-toggle-an-label');

    if(sharpAmt.length) sharpAmt[0].innerHTML = annual ? prices.sharp.an : prices.sharp.mo;
    if(smartAmt.length) smartAmt[0].innerHTML = annual ? prices.smart.an : prices.smart.mo;
    if(sharpPer.length) sharpPer[0].textContent = annual ? 'billed annually · 2 months free' : 'billed monthly';
    if(smartPer.length) smartPer[0].textContent = annual ? 'billed annually · 2 months free' : 'billed monthly · save 20% annual';

    if(knob) knob.style.transform = annual ? 'translateX(24px)' : 'translateX(0)';
    if(moLabel) moLabel.style.color = annual ? 'rgba(255,255,255,0.35)' : '#fff';
    if(anLabel) anLabel.style.color = annual ? '#fff' : 'rgba(255,255,255,0.38)';
  }

  window.lpToggleBilling = function(){
    annual = !annual;
    updatePricing(document);
    try{ updatePricing(window.parent.document); }catch(e){}
  };

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', function(){ updatePricing(document); });
  else updatePricing(document);
  setTimeout(function(){ updatePricing(document); try{ updatePricing(window.parent.document); }catch(e){} }, 600);
})();
</script>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# FAQ SECTION (#lp-faq)
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── FAQ Accordion ──────────────────────────────────────── */
.lp-faq-list {
    max-width: 760px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.lp-faq-item {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 18px;
    overflow: hidden;
    transition: border-color 0.3s, background 0.3s;
}
.lp-faq-item.open {
    border-color: rgba(0,213,89,0.2);
    background: rgba(0,213,89,0.02);
}
.lp-faq-q {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 22px 26px;
    cursor: pointer;
    user-select: none;
    gap: 16px;
}
.lp-faq-q-text {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.97rem;
    font-weight: 700;
    color: #fff;
    line-height: 1.4;
    flex: 1;
}
.lp-faq-icon {
    width: 28px; height: 28px; border-radius: 8px;
    background: rgba(0,213,89,0.08);
    border: 1px solid rgba(0,213,89,0.18);
    color: #00D559;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; font-weight: 900;
    flex-shrink: 0;
    transition: transform 0.3s, background 0.3s;
    line-height: 1;
}
.lp-faq-item.open .lp-faq-icon {
    transform: rotate(45deg);
    background: rgba(0,213,89,0.14);
}
.lp-faq-a {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.4s cubic-bezier(0.16,1,0.3,1), padding 0.3s;
    padding: 0 26px;
}
.lp-faq-a-inner {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    color: rgba(255,255,255,0.45);
    line-height: 1.8;
    padding-bottom: 22px;
    border-top: 1px solid rgba(255,255,255,0.05);
    padding-top: 16px;
}
.lp-faq-a-inner strong { color: rgba(255,255,255,0.75); font-weight: 700; }
.lp-faq-a-inner a { color: #00D559; text-decoration: none; }
.lp-faq-item.open .lp-faq-a {
    max-height: 400px;
}
</style>

<!-- section divider -->
<div style="padding:0 24px;"><div class="lp-divider"></div></div>

<!-- ══ FAQ ════════════════════════════════════════════════ -->
<div id="lp-faq" style="padding: 100px 24px 0;">
  <div class="lp-section" style="padding:0;">
    <div class="lp-section-label">FAQ</div>
    <h2 class="lp-section-h2">Got Questions?<br>We've Got Answers.</h2>
    <p class="lp-section-sub">Everything you need to know about Smart Pick Pro and the Neural Engine.</p>

    <div class="lp-faq-list">

      <div class="lp-faq-item open">
        <div class="lp-faq-q" onclick="lpToggleFaq(this)">
          <span class="lp-faq-q-text">What is the SAFE Score™ and how is it calculated?</span>
          <span class="lp-faq-icon">+</span>
        </div>
        <div class="lp-faq-a">
          <div class="lp-faq-a-inner">
            The <strong>SAFE Score™</strong> is our proprietary 0–100 confidence rating for every prop. It aggregates outputs from 6 AI models — Ensemble Neural Network, Bayesian Inference, Monte Carlo Simulation, Linear Regression, CLV Tracker, and Line Movement Mirror — weighted by each model's recent accuracy. A score above <strong>70 is a strong signal</strong>; above 85 is our highest-confidence tier.
          </div>
        </div>
      </div>

      <div class="lp-faq-item">
        <div class="lp-faq-q" onclick="lpToggleFaq(this)">
          <span class="lp-faq-q-text">Is Smart Pick Pro actually free to start?</span>
          <span class="lp-faq-icon">+</span>
        </div>
        <div class="lp-faq-a">
          <div class="lp-faq-a-inner">
            Yes — <strong>completely free, no credit card required</strong>. Free accounts get the top 3 daily picks with SAFE Scores visible. Upgrade to Sharp IQ or Smart Money to unlock the full 300+ prop nightly slate, line movement alerts, and the Bet Tracker dashboard.
          </div>
        </div>
      </div>

      <div class="lp-faq-item">
        <div class="lp-faq-q" onclick="lpToggleFaq(this)">
          <span class="lp-faq-q-text">Which platforms does the Neural Engine cover?</span>
          <span class="lp-faq-icon">+</span>
        </div>
        <div class="lp-faq-a">
          <div class="lp-faq-a-inner">
            Smart Pick Pro ingests live lines from <strong>PrizePicks, DraftKings, Underdog Fantasy, and ParlayApp</strong>. Props are pulled, normalized, and scored across all platforms simultaneously — so you always see the best available line for each play.
          </div>
        </div>
      </div>

      <div class="lp-faq-item">
        <div class="lp-faq-q" onclick="lpToggleFaq(this)">
          <span class="lp-faq-q-text">How is the 62.4% hit rate verified?</span>
          <span class="lp-faq-icon">+</span>
        </div>
        <div class="lp-faq-a">
          <div class="lp-faq-a-inner">
            Our hit rate is calculated from <strong>4,200+ tracked picks</strong> stored in the Bet Tracker database, logged with the line at time of pick, the final result, and the SAFE Score threshold used. Members can filter by model, tier, prop type, and date range inside their dashboard to verify independently. We don't cherry-pick — every scored pick above threshold is logged.
          </div>
        </div>
      </div>

      <div class="lp-faq-item">
        <div class="lp-faq-q" onclick="lpToggleFaq(this)">
          <span class="lp-faq-q-text">Can I cancel or change my plan at any time?</span>
          <span class="lp-faq-icon">+</span>
        </div>
        <div class="lp-faq-a">
          <div class="lp-faq-a-inner">
            Yes. You can <strong>upgrade, downgrade, or cancel at any time</strong> from your account settings — no penalties, no fees, no tricks. Your access continues until the end of your current billing period. Downgrading to Free keeps your account and pick history intact forever.
          </div>
        </div>
      </div>

      <div class="lp-faq-item">
        <div class="lp-faq-q" onclick="lpToggleFaq(this)">
          <span class="lp-faq-q-text">Does this work for casual bettors or only pros?</span>
          <span class="lp-faq-icon">+</span>
        </div>
        <div class="lp-faq-a">
          <div class="lp-faq-a-inner">
            Both. <strong>The Neural Engine does all the heavy lifting</strong> — you don't need to understand the math. Casual members use the top-ranked green picks and the Bankroll Optimizer to manage stake sizes safely. Advanced users can drill into individual model breakdowns, set custom SAFE Score thresholds, and configure their own filter presets.
          </div>
        </div>
      </div>

    </div><!-- /lp-faq-list -->
  </div>
</div>

<script>
function lpToggleFaq(el) {
  var item = el.closest('.lp-faq-item');
  var isOpen = item.classList.contains('open');
  /* Close all others */
  document.querySelectorAll('.lp-faq-item.open').forEach(function(x) { x.classList.remove('open'); });
  try { window.parent.document.querySelectorAll('.lp-faq-item.open').forEach(function(x){x.classList.remove('open');}); } catch(e){}
  if (!isOpen) { item.classList.add('open'); }
}
</script>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 2 — JS COUNTUP ANIMATIONS (IntersectionObserver)
# ════════════════════════════════════════════════════════════
st.markdown("""
<script>
(function() {
  function lerp(a, b, t) { return a + (b - a) * t; }

  function animateCount(el) {
    if (el.dataset.animated) return;
    el.dataset.animated = '1';

    var target   = parseFloat(el.dataset.target)  || 0;
    var prefix   = el.dataset.prefix  || '';
    var suffix   = el.dataset.suffix  || '';
    var decimals = parseInt(el.dataset.decimals)   || 0;
    var useComma = el.hasAttribute('data-comma');
    var duration = 1800;
    var start    = null;
    var startVal = 0;

    function fmt(v) {
      var s = v.toFixed(decimals);
      if (useComma) s = parseFloat(s).toLocaleString('en-US', {maximumFractionDigits: decimals});
      return prefix + s + suffix;
    }

    function step(ts) {
      if (!start) start = ts;
      var elapsed = ts - start;
      var progress = Math.min(elapsed / duration, 1);
      // ease-out-expo
      var ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      var current = startVal + (target - startVal) * ease;
      el.textContent = fmt(current);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = fmt(target);
    }
    requestAnimationFrame(step);
  }

  function initObserver(doc) {
    var els = doc.querySelectorAll('[data-countup]');
    if (!els.length) return;

    var io = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          animateCount(e.target);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.25 });

    els.forEach(function(el) { io.observe(el); });
  }

  // Streamlit wraps pages in an iframe — run in both contexts
  function tryInit() {
    initObserver(document);
    try { initObserver(window.parent.document); } catch(e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryInit);
  } else {
    tryInit();
  }

  // Re-run after a short delay to catch Streamlit's late-render pass
  setTimeout(tryInit, 800);
  setTimeout(tryInit, 2200);
})();
</script>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# PHASE 6 — SCROLL REVEAL + GLOBAL POLISH
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Scroll reveal base state ──────────────────────────────── */
.lp-reveal {
    opacity: 0;
    transform: translateY(40px);
    transition: opacity 0.75s cubic-bezier(0.16,1,0.3,1),
                transform 0.75s cubic-bezier(0.16,1,0.3,1);
}
.lp-reveal.lp-visible {
    opacity: 1;
    transform: translateY(0);
}
.lp-reveal-delay-1 { transition-delay: 0.1s; }
.lp-reveal-delay-2 { transition-delay: 0.2s; }
.lp-reveal-delay-3 { transition-delay: 0.3s; }
.lp-reveal-delay-4 { transition-delay: 0.4s; }
.lp-reveal-delay-5 { transition-delay: 0.5s; }

/* ── Section dividers ──────────────────────────────────────── */
.lp-divider {
    width: 100%; max-width: 900px; margin: 0 auto;
    height: 1px;
    background: linear-gradient(90deg,
        transparent,
        rgba(0,213,89,0.12) 20%,
        rgba(45,158,255,0.1) 50%,
        rgba(0,213,89,0.12) 80%,
        transparent);
}

/* ── Section heading glow on scroll in ──────────────────────── */
.lp-section-h2 {
    transition: text-shadow 0.8s ease;
}
.lp-visible .lp-section-h2,
.lp-visible.lp-section-h2 {
    text-shadow: 0 0 60px rgba(0,213,89,0.15);
}

/* ── Trust bar reveal ──────────────────────────────────────── */
.lp-trust-bar {
    transition: opacity 0.8s ease, transform 0.8s cubic-bezier(0.16,1,0.3,1),
                box-shadow 0.6s ease !important;
}
.lp-trust-bar.lp-visible {
    box-shadow:
        0 0 0 1px rgba(255,255,255,0.06),
        0 0 60px rgba(0,213,89,0.06),
        0 24px 60px rgba(0,0,0,0.3) !important;
}

/* ── Testimonial card hover polish ──────────────────────────── */
.lp-testi-card {
    transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s !important;
}
.lp-testi-card:hover {
    transform: translateY(-5px) !important;
    border-color: rgba(0,213,89,0.2) !important;
    box-shadow: 0 0 40px rgba(0,213,89,0.07), 0 16px 40px rgba(0,0,0,0.4) !important;
}

/* ── Step cards hover ──────────────────────────────────────── */
.lp-step {
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s !important;
}
.lp-step:hover {
    box-shadow: 0 0 40px rgba(0,213,89,0.07), 0 16px 40px rgba(0,0,0,0.4) !important;
}
.lp-step-num {
    transition: -webkit-text-stroke 0.3s !important;
}
.lp-step:hover .lp-step-num {
    -webkit-text-stroke: 1px rgba(0,213,89,0.7) !important;
}

/* ── Footer polish ─────────────────────────────────────────── */
.lp-footer {
    padding-bottom: 72px !important;
}
.lp-footer-bottom {
    position: relative;
}
.lp-footer-bottom::before {
    content: '';
    position: absolute; top: -1px; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.15), rgba(45,158,255,0.1), transparent);
}

/* ── Scroll-to-top button ──────────────────────────────────── */
#lp-back-top {
    position: fixed;
    bottom: 32px; right: 32px;
    width: 44px; height: 44px;
    border-radius: 12px;
    background: rgba(0,213,89,0.12);
    border: 1px solid rgba(0,213,89,0.25);
    color: #00D559;
    font-size: 1.1rem;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; text-decoration: none;
    opacity: 0; pointer-events: none;
    transition: opacity 0.3s, transform 0.3s, background 0.3s;
    z-index: 9000;
    backdrop-filter: blur(12px);
}
#lp-back-top.visible {
    opacity: 1; pointer-events: auto;
}
#lp-back-top:hover {
    background: rgba(0,213,89,0.2);
    transform: translateY(-3px);
}
</style>

<a id="lp-back-top" href="#lp-hero" aria-label="Back to top">↑</a>

<script>
/* Phase 6 — scroll reveal + back-to-top */
(function() {
  function addRevealClasses(doc) {
    /* Mark trust bar, step cards, testi cards, section wrappers */
    var selectors = [
      '.lp-trust-bar',
      '.lp-step',
      '.lp-testi-card',
      '.lp-section-label',
      '.lp-section-h2',
      '.lp-section-sub',
      '.lp-price-card',
      '.lp-footer-col-label'
    ];
    selectors.forEach(function(sel) {
      doc.querySelectorAll(sel + ':not(.lp-reveal)').forEach(function(el) {
        el.classList.add('lp-reveal');
      });
    });

    /* Apply staggered delays inside grids */
    doc.querySelectorAll('.lp-step, .lp-testi-card, .lp-price-card').forEach(function(el, i) {
      el.classList.add('lp-reveal-delay-' + ((i % 5) + 1));
    });
  }

  function initReveal(doc) {
    addRevealClasses(doc);
    var io = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          e.target.classList.add('lp-visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    doc.querySelectorAll('.lp-reveal').forEach(function(el) { io.observe(el); });
  }

  /* Back-to-top visibility */
  function initBackTop(doc) {
    var btn = doc.getElementById('lp-back-top');
    if (!btn) return;
    (doc.scrollingElement || doc.documentElement).addEventListener
      ? null : null; // no-op guard
    var scrollEl = doc.scrollingElement || doc.documentElement;
    doc.addEventListener('scroll', function() {
      btn.classList.toggle('visible', scrollEl.scrollTop > 600);
    });
  }

  function tryAll() {
    try { initReveal(document); } catch(e) {}
    try { initReveal(window.parent.document); } catch(e) {}
    try { initBackTop(document); } catch(e) {}
    try { initBackTop(window.parent.document); } catch(e) {}
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tryAll);
  else tryAll();
  setTimeout(tryAll, 700);
  setTimeout(tryAll, 2000);
})();
</script>
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
    background: rgba(6,14,10,0.82) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    border-radius: 28px !important;
    box-shadow:
        0 0 0 1px rgba(0,213,89,0.07),
        0 0 80px rgba(0,213,89,0.08),
        0 32px 100px rgba(0,0,0,0.55),
        inset 0 1px 0 rgba(255,255,255,0.06) !important;
    padding: 44px 40px 40px !important;
    backdrop-filter: blur(32px) !important;
    -webkit-backdrop-filter: blur(32px) !important;
    position: relative !important;
    overflow: hidden;
}
/* Animated top bar on form card */
.spp-form-wrapper::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #c084fc, #00D559);
    background-size: 300% 100%;
    animation: agGradientShift 6s ease infinite;
    opacity: 0.85;
}
/* Subtle inner glow at top */
.spp-form-wrapper::after {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 120px;
    background: linear-gradient(180deg, rgba(0,213,89,0.04), transparent);
    pointer-events: none;
}

/* Enhanced Streamlit text input styling */
.spp-form-wrapper .stTextInput > label {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: rgba(255,255,255,0.45) !important;
    text-transform: uppercase !important;
    letter-spacing: .08em !important;
    margin-bottom: 6px !important;
}
.spp-form-wrapper .stTextInput > div > div > input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    color: #fff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 14px 16px !important;
    transition: border-color 0.25s, box-shadow 0.25s, background 0.25s !important;
}
.spp-form-wrapper .stTextInput > div > div > input:focus {
    border-color: rgba(0,213,89,0.5) !important;
    background: rgba(0,213,89,0.04) !important;
    box-shadow: 0 0 0 3px rgba(0,213,89,0.1), 0 0 20px rgba(0,213,89,0.12) !important;
}
.spp-form-wrapper .stTextInput > div > div > input::placeholder {
    color: rgba(255,255,255,0.2) !important;
}
/* Submit button enhancement */
.spp-form-wrapper .stFormSubmitButton > button[kind="primary"],
.spp-form-wrapper .stFormSubmitButton > button[data-testid="baseButton-primary"] {
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 800 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.04em !important;
    border-radius: 14px !important;
    padding: 14px 28px !important;
    background: linear-gradient(135deg, #00FF85 0%, #00D559 50%, #00B74D 100%) !important;
    color: #020C07 !important;
    border: none !important;
    box-shadow: 0 0 40px rgba(0,213,89,0.4), 0 8px 24px rgba(0,213,89,0.2) !important;
    transition: all 0.3s cubic-bezier(0.16,1,0.3,1) !important;
    position: relative; overflow: hidden;
}
.spp-form-wrapper .stFormSubmitButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 0 60px rgba(0,213,89,0.6), 0 12px 36px rgba(0,213,89,0.3) !important;
}
/* Forgot password / secondary buttons */
.spp-form-wrapper .stButton > button {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem !important;
    color: rgba(255,255,255,0.35) !important;
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    transition: all 0.2s !important;
}
.spp-form-wrapper .stButton > button:hover {
    color: #fff !important;
    border-color: rgba(255,255,255,0.2) !important;
    background: rgba(255,255,255,0.04) !important;
}
/* Mode tabs upgrade */
.spp-mode-tabs {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 14px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.spp-mode-tab {
    border-radius: 10px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.25s !important;
}
.spp-mode-tab.active {
    background: linear-gradient(135deg, #00FF85, #00D559) !important;
    color: #020C07 !important;
    box-shadow: 0 0 24px rgba(0,213,89,0.4) !important;
}
/* Error / success message styling */
.spp-form-wrapper .stAlert {
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important;
}
</style>

<!-- Section anchor + label -->
<div id="lp-auth">
  <!-- divider above auth -->
  <div style="padding:0 24px 0;"><div class="lp-divider"></div></div>
  <div style="padding: 100px 24px 0; text-align:center; position:relative; overflow:hidden;">
    <!-- Subtle glow orb behind auth section -->
    <div style="position:absolute;top:-80px;left:50%;transform:translateX(-50%);
                width:600px;height:400px;border-radius:50%;
                background:radial-gradient(ellipse,rgba(0,213,89,0.07) 0%,transparent 70%);
                pointer-events:none;"></div>
    <div class="lp-section-label">Get Access</div>
    <h2 class="lp-section-h2" style="font-size:clamp(2.4rem,5vw,4rem);">Join 2,400+<br>Winning Sharps.</h2>
    <p class="lp-section-sub" style="margin-bottom: 48px; font-size:1.05rem;">
      Free forever. No credit card required.<br>
      <strong style="color:rgba(255,255,255,0.7);">Start picking smarter tonight.</strong>
    </p>
    <!-- Mini trust badges -->
    <div style="display:flex;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap;margin-bottom:0;">
      <span style="font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;
                   color:rgba(255,255,255,0.25);text-transform:uppercase;letter-spacing:.08em;
                   display:flex;align-items:center;gap:6px;">
        <span style="color:#00D559;">✓</span> 256-bit Encryption</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;
                   color:rgba(255,255,255,0.25);text-transform:uppercase;letter-spacing:.08em;
                   display:flex;align-items:center;gap:6px;">
        <span style="color:#00D559;">✓</span> No Credit Card</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;
                   color:rgba(255,255,255,0.25);text-transform:uppercase;letter-spacing:.08em;
                   display:flex;align-items:center;gap:6px;">
        <span style="color:#00D559;">✓</span> Cancel Anytime</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;
                   color:rgba(255,255,255,0.25);text-transform:uppercase;letter-spacing:.08em;
                   display:flex;align-items:center;gap:6px;">
        <span style="color:#00D559;">✓</span> Free Forever</span>
    </div>
  </div>
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
# PRE-FOOTER CTA BANNER
# ════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Pre-footer CTA Banner ──────────────────────────────── */
.lp-prefooter-cta {
    position: relative;
    overflow: hidden;
    border-radius: 28px;
    max-width: 1100px;
    margin: 100px auto 0;
    padding: 80px 48px;
    background: linear-gradient(135deg,
        rgba(0,213,89,0.12) 0%,
        rgba(2,6,14,0.97) 50%,
        rgba(45,158,255,0.10) 100%);
    border: 1px solid rgba(0,213,89,0.2);
    text-align: center;
    isolation: isolate;
}
.lp-prefooter-cta::before {
    content: '';
    position: absolute; inset: 0;
    background:
        radial-gradient(ellipse 70% 50% at 20% 50%, rgba(0,213,89,0.12), transparent),
        radial-gradient(ellipse 50% 60% at 80% 50%, rgba(45,158,255,0.10), transparent);
    z-index: 0;
    pointer-events: none;
}
/* grid mesh */
.lp-prefooter-cta::after {
    content: '';
    position: absolute; inset: 0;
    background-image:
        linear-gradient(rgba(0,213,89,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,213,89,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
    z-index: 0;
    mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black, transparent);
    -webkit-mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black, transparent);
    pointer-events: none;
}
.lp-pfcta-inner { position: relative; z-index: 1; }
.lp-pfcta-badge {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: .55rem; font-weight: 800;
    color: #00D559;
    background: rgba(0,213,89,0.1);
    border: 1px solid rgba(0,213,89,0.22);
    padding: 5px 14px; border-radius: 100px;
    letter-spacing: .1em; text-transform: uppercase;
    margin-bottom: 26px;
}
.lp-pfcta-badge::before {
    content: '';
    width: 7px; height: 7px; border-radius: 50%;
    background: #00D559;
    box-shadow: 0 0 8px #00D559;
    animation: agLivePulse 1.8s ease-in-out infinite;
}
.lp-pfcta-h {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(2rem, 4vw, 3.2rem);
    font-weight: 900; letter-spacing: -.04em;
    color: #fff; line-height: 1.15;
    margin-bottom: 18px;
}
.lp-pfcta-h span {
    background: linear-gradient(90deg, #00D559, #00FF85);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.lp-pfcta-sub {
    font-family: 'Inter', sans-serif;
    font-size: 1.05rem; font-weight: 400;
    color: rgba(255,255,255,0.48);
    max-width: 560px; margin: 0 auto 38px;
    line-height: 1.7;
}
.lp-pfcta-btns {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; flex-wrap: wrap;
}
.lp-pfcta-primary {
    display: inline-flex; align-items: center; gap: 10px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem; font-weight: 800; letter-spacing: -.02em;
    color: #020C07;
    background: linear-gradient(135deg, #00D559, #00FF85);
    padding: 16px 38px; border-radius: 12px;
    text-decoration: none;
    box-shadow: 0 6px 30px rgba(0,213,89,0.40), 0 0 0 0 rgba(0,213,89,0);
    transition: transform .25s, box-shadow .25s;
}
.lp-pfcta-primary:hover {
    transform: translateY(-3px) scale(1.03);
    box-shadow: 0 14px 40px rgba(0,213,89,0.55), 0 0 60px rgba(0,213,89,0.2);
    color: #020C07; text-decoration: none;
}
.lp-pfcta-secondary {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: .9rem; font-weight: 700;
    color: rgba(255,255,255,0.55);
    background: transparent;
    border: 1px solid rgba(255,255,255,0.1);
    padding: 15px 28px; border-radius: 12px;
    text-decoration: none;
    transition: color .25s, border-color .25s, background .25s;
}
.lp-pfcta-secondary:hover {
    color: #fff; border-color: rgba(255,255,255,0.25);
    background: rgba(255,255,255,0.05);
    text-decoration: none;
}
.lp-pfcta-micro {
    margin-top: 22px;
    font-family: 'Inter', sans-serif;
    font-size: .72rem;
    color: rgba(255,255,255,0.2);
    letter-spacing: .03em;
}
.lp-pfcta-micro span {
    color: rgba(0,213,89,0.5);
    margin: 0 8px;
}
@media (max-width: 600px) {
    .lp-prefooter-cta { padding: 56px 24px; border-radius: 20px; }
}
</style>

<div class="lp-prefooter-cta lp-reveal">
  <div class="lp-pfcta-inner">
    <div class="lp-pfcta-badge">Live Picks Ready</div>
    <h2 class="lp-pfcta-h">Stop Guessing.<br><span>Start Winning.</span></h2>
    <p class="lp-pfcta-sub">
      Join thousands of sharp bettors using AI-powered props analysis every single night.
      Free to start — upgrade when the results speak for themselves.
    </p>
    <div class="lp-pfcta-btns">
      <a href="?auth=signup" class="lp-pfcta-primary">⚡ Get Free Access Now</a>
      <a href="#lp-pricing" class="lp-pfcta-secondary">See Pricing →</a>
    </div>
    <p class="lp-pfcta-micro">
      No credit card required <span>·</span> Free plan forever <span>·</span> Cancel anytime
    </p>
  </div>
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
