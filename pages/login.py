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

# Also handle cookie-based session restore silently at the bottom
# This is a fallback for environments where the quick restore above fails
if require_login():
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

st.stop()
