# ============================================================
# FILE: utils/auth_gate.py
# PURPOSE: Signup / Login gate for Smart Pick Pro.
#          Users must create an account or log in before they
#          can see ANY page in the app.
#
# HOW IT WORKS:
#   1. Call  require_login()  at the very top of every page
#      (after st.set_page_config).
#   2. If the user has NOT logged in this session, the function
#      renders a full-screen signup/login form and returns False.
#      The calling page should then call  st.stop().
#   3. Once the user signs up or logs in, the session-state flag
#      is set and require_login() returns True on all subsequent
#      reruns — no database hit on every page load.
#
# PASSWORD STORAGE:
#   • Passwords are hashed with bcrypt (or hashlib-based PBKDF2
#     fallback if bcrypt is not installed).
#   • Plaintext passwords are NEVER stored or logged.
# ============================================================

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import sqlite3

import streamlit as st

from tracking.database import initialize_database, get_database_connection

_logger = logging.getLogger(__name__)

# ── Session-state keys ────────────────────────────────────────
_SS_LOGGED_IN     = "_auth_logged_in"      # bool
_SS_USER_EMAIL    = "_auth_user_email"     # str
_SS_USER_NAME     = "_auth_user_name"      # str
_SS_USER_ID       = "_auth_user_id"        # int

# ── Password hashing helpers ──────────────────────────────────

try:
    import bcrypt as _bcrypt  # type: ignore
    _HAS_BCRYPT = True
except ImportError:
    _bcrypt = None  # type: ignore
    _HAS_BCRYPT = False


def _hash_password(plain: str) -> str:
    """Hash a plaintext password. Uses bcrypt if available, else PBKDF2."""
    if _HAS_BCRYPT:
        return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    # Fallback: PBKDF2-SHA256
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"pbkdf2:sha256:260000${salt}${dk.hex()}"


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    if _HAS_BCRYPT and hashed.startswith("$2"):
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    if hashed.startswith("pbkdf2:"):
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_hex = parts
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 260_000)
        return secrets.compare_digest(dk.hex(), expected_hex)
    return False


# ── Database helpers ──────────────────────────────────────────

def _create_user(email: str, password: str, display_name: str = "") -> bool:
    """Create a new user account. Returns True on success."""
    initialize_database()
    pw_hash = _hash_password(password)
    try:
        with get_database_connection() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                (email.strip().lower(), pw_hash, display_name.strip() or email.split("@")[0]),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Email already registered
    except Exception as exc:
        _logger.error("Failed to create user: %s", exc)
        return False


def _authenticate_user(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict on success, None on failure."""
    initialize_database()
    try:
        with get_database_connection() as conn:
            cursor = conn.execute(
                "SELECT user_id, email, password_hash, display_name FROM users WHERE email = ?",
                (email.strip().lower(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            user = dict(row)
            if _verify_password(password, user["password_hash"]):
                # Update last_login_at
                conn.execute(
                    "UPDATE users SET last_login_at = datetime('now') WHERE user_id = ?",
                    (user["user_id"],),
                )
                conn.commit()
                return user
    except Exception as exc:
        _logger.error("Authentication error: %s", exc)
    return None


def _email_exists(email: str) -> bool:
    """Check if an email is already registered."""
    initialize_database()
    try:
        with get_database_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
            return row is not None
    except Exception:
        return False


# ── Validation ────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def _valid_password(pw: str) -> str | None:
    """Return an error message if password is weak, else None."""
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in pw):
        return "Password must contain at least one number."
    if not any(c.isalpha() for c in pw):
        return "Password must contain at least one letter."
    return None


# ── Session helpers ───────────────────────────────────────────

def _set_logged_in(user: dict) -> None:
    st.session_state[_SS_LOGGED_IN]  = True
    st.session_state[_SS_USER_EMAIL] = user.get("email", "")
    st.session_state[_SS_USER_NAME]  = user.get("display_name", "")
    st.session_state[_SS_USER_ID]    = user.get("user_id", 0)


def is_logged_in() -> bool:
    """Check if the user is logged into an account this session."""
    return bool(st.session_state.get(_SS_LOGGED_IN))


def get_logged_in_email() -> str:
    """Return the logged-in user's email, or ''."""
    return st.session_state.get(_SS_USER_EMAIL, "")


def logout_user() -> None:
    """Clear the login session."""
    for key in (_SS_LOGGED_IN, _SS_USER_EMAIL, _SS_USER_NAME, _SS_USER_ID):
        st.session_state.pop(key, None)


# ── Logo helper ───────────────────────────────────────────────

def _get_logo_b64() -> str:
    """Return base64-encoded SPP logo for inline embedding."""
    import base64 as _b64
    _logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Smart_Pick_Pro_Logo.png")
    try:
        with open(_logo_path, "rb") as f:
            return _b64.b64encode(f.read()).decode()
    except OSError:
        return ""


# ── CSS for the gate ──────────────────────────────────────────

_GATE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ═══════════════════════════════════════════════════════════════
   SMART PICK PRO — FULL-SCREEN AUTH GATE
   Cinematic conversion-optimised landing + signup/login
   ═══════════════════════════════════════════════════════════════ */

/* ── Reset Streamlit chrome ──────────────────────────────────── */
[data-testid="stSidebar"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton,
footer { display: none !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
.stApp { background: transparent !important; }
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 0 !important; max-width: 100% !important;
}

/* ── Keyframes ───────────────────────────────────────────────── */
@keyframes agFadeUp {
    from { opacity:0; transform:translateY(40px); }
    to   { opacity:1; transform:translateY(0); }
}
@keyframes agFadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes agSlideRight {
    from { opacity:0; transform:translateX(-30px); }
    to   { opacity:1; transform:translateX(0); }
}
@keyframes agGradShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes agPulse {
    0%,100% { opacity:0.5; transform:scale(1); }
    50%     { opacity:1;   transform:scale(1.04); }
}
@keyframes agOrbDrift1 {
    0%,100% { transform: translate(0,0) scale(1); }
    25%     { transform: translate(60px,-40px) scale(1.15); }
    50%     { transform: translate(-30px,50px) scale(0.9); }
    75%     { transform: translate(40px,30px) scale(1.08); }
}
@keyframes agOrbDrift2 {
    0%,100% { transform: translate(0,0) scale(1); }
    33%     { transform: translate(-50px,30px) scale(1.12); }
    66%     { transform: translate(40px,-45px) scale(0.88); }
}
@keyframes agOrbDrift3 {
    0%,100% { transform: translate(0,0) scale(1) rotate(0deg); }
    50%     { transform: translate(20px,-20px) scale(1.1) rotate(180deg); }
}
@keyframes agScanLine {
    0%   { top:-3px; opacity:0.6; }
    100% { top:100%; opacity:0; }
}
@keyframes agShimmer {
    0%   { left:-100%; }
    100% { left:200%; }
}
@keyframes agCountUp {
    from { opacity:0; transform:scale(0.5); }
    to   { opacity:1; transform:scale(1); }
}
@keyframes agTickerScroll {
    0%   { transform:translateX(0); }
    100% { transform:translateX(-50%); }
}
@keyframes agLogoRing {
    from { transform:rotate(0deg); }
    to   { transform:rotate(360deg); }
}
@keyframes agGlowPulse {
    0%,100% { box-shadow:0 0 30px rgba(0,213,89,0.06), 0 20px 60px rgba(0,0,0,0.4); }
    50%     { box-shadow:0 0 50px rgba(0,213,89,0.12), 0 20px 80px rgba(0,0,0,0.5); }
}
@keyframes agStarTwinkle {
    0%,100% { opacity:0.2; transform:scale(0.8); }
    50%     { opacity:1; transform:scale(1.2); }
}
@keyframes agFloat {
    0%,100% { transform:translateY(0); }
    50%     { transform:translateY(-8px); }
}
@keyframes agBarSlide {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes agLivePulse {
    0%,100% { box-shadow:0 0 0 0 rgba(0,213,89,0.5); }
    50%     { box-shadow:0 0 0 6px rgba(0,213,89,0); }
}

/* ── Full-screen canvas ──────────────────────────────────────── */
.ag-canvas {
    position:fixed; inset:0; z-index:9990;
    background: linear-gradient(165deg, #020408 0%, #05091a 20%, #08102a 45%, #0a0e20 70%, #030610 100%);
    background-size:400% 400%;
    animation: agGradShift 25s ease infinite;
    overflow:hidden;
}

/* Star field (CSS-only particles) */
.ag-stars { position:absolute; inset:0; overflow:hidden; }
.ag-star {
    position:absolute; border-radius:50%; background:#fff;
    animation: agStarTwinkle var(--dur) ease-in-out infinite;
    animation-delay: var(--delay);
}
/* 30 stars generated via inline style — see HTML */

/* Orbs */
.ag-orb { position:absolute; border-radius:50%; pointer-events:none; filter:blur(120px); }
.ag-orb-1 {
    width:600px; height:600px; top:-200px; left:-150px;
    background:radial-gradient(circle, rgba(0,213,89,0.12) 0%, transparent 70%);
    animation: agOrbDrift1 18s ease-in-out infinite;
}
.ag-orb-2 {
    width:500px; height:500px; bottom:-180px; right:-120px;
    background:radial-gradient(circle, rgba(45,158,255,0.10) 0%, transparent 70%);
    animation: agOrbDrift2 22s ease-in-out infinite;
}
.ag-orb-3 {
    width:350px; height:350px; top:35%; right:25%;
    background:radial-gradient(circle, rgba(192,132,252,0.07) 0%, transparent 70%);
    animation: agOrbDrift3 28s ease-in-out infinite;
}
.ag-orb-4 {
    width:280px; height:280px; bottom:20%; left:15%;
    background:radial-gradient(circle, rgba(249,198,43,0.06) 0%, transparent 70%);
    animation: agOrbDrift1 24s ease-in-out infinite reverse;
}

/* Scan line */
.ag-scan {
    position:absolute; left:0; width:100%; height:2px; z-index:9991;
    background:linear-gradient(90deg, transparent, rgba(0,213,89,0.3) 20%, rgba(45,158,255,0.25) 50%, rgba(192,132,252,0.2) 80%, transparent);
    animation: agScanLine 7s linear infinite;
    pointer-events:none;
}

/* Grid */
.ag-grid {
    position:absolute; inset:0; pointer-events:none;
    background-image:
        linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
    background-size:80px 80px;
    mask-image:radial-gradient(ellipse at 50% 40%, black 20%, transparent 75%);
    -webkit-mask-image:radial-gradient(ellipse at 50% 40%, black 20%, transparent 75%);
}

/* ── Scroll wrapper ──────────────────────────────────────────── */
.ag-scroll {
    position:fixed; inset:0; z-index:9992;
    overflow-y:auto; overflow-x:hidden;
    -webkit-overflow-scrolling:touch;
}

/* ── Inner page ──────────────────────────────────────────────── */
.ag-page {
    max-width:520px; margin:0 auto;
    padding:0 20px;
    font-family:'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color:#fff;
}

/* ── URGENCY BAR (fixed top) ─────────────────────────────────── */
.ag-urgency {
    position:fixed; top:0; left:0; right:0; z-index:9999;
    height:40px; display:flex; align-items:center; justify-content:center;
    background:linear-gradient(90deg, #0d1117, rgba(0,213,89,0.08) 30%, rgba(45,158,255,0.06) 70%, #0d1117);
    border-bottom:1px solid rgba(0,213,89,0.12);
    font-size:0.74rem; font-weight:700; letter-spacing:0.02em;
    color:rgba(255,255,255,0.8);
    overflow:hidden;
}
.ag-urgency::before {
    content:''; position:absolute; top:0; left:0; right:0; height:1px;
    background:linear-gradient(90deg, transparent, #00D559 20%, #2D9EFF 50%, #c084fc 80%, transparent);
    background-size:400% 100%;
    animation: agBarSlide 4s linear infinite;
}
.ag-urgency-live {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(0,213,89,0.12); border:1px solid rgba(0,213,89,0.25);
    padding:3px 10px; border-radius:100px; margin-right:12px;
    font-size:0.68rem; font-weight:800; color:#00D559;
}
.ag-urgency-dot {
    width:7px; height:7px; border-radius:50%; background:#00D559;
    animation: agLivePulse 2s ease-in-out infinite;
}

/* ── LOGO + BRAND ────────────────────────────────────────────── */
.ag-brand {
    text-align:center; padding-top:60px; margin-bottom:4px;
    animation: agFadeUp 0.8s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-logo-ring {
    display:inline-block; position:relative;
    width:88px; height:88px; margin-bottom:16px;
}
.ag-logo-ring::before {
    content:''; position:absolute; inset:-5px; border-radius:50%;
    background:conic-gradient(from 0deg, #00D559, #2D9EFF, #c084fc, #F9C62B, #00D559);
    animation:agLogoRing 8s linear infinite;
    mask:radial-gradient(farthest-side, transparent calc(100% - 2.5px), black calc(100% - 2.5px));
    -webkit-mask:radial-gradient(farthest-side, transparent calc(100% - 2.5px), black calc(100% - 2.5px));
}
.ag-logo-ring::after {
    content:''; position:absolute; inset:-12px; border-radius:50%;
    background:conic-gradient(from 90deg, transparent, rgba(0,213,89,0.15), transparent, rgba(45,158,255,0.1), transparent);
    animation:agLogoRing 12s linear infinite reverse;
    filter:blur(8px);
}
.ag-logo-ring img {
    width:88px; height:88px; border-radius:50%;
    position:relative; z-index:2;
    box-shadow:0 0 40px rgba(0,213,89,0.15);
}
.ag-brand-name {
    font-size:2rem; font-weight:900; letter-spacing:-0.04em; line-height:1;
    background:linear-gradient(135deg, #fff 0%, #00D559 45%, #2D9EFF 100%);
    background-size:300% 300%;
    animation:agGradShift 5s ease infinite;
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}
.ag-brand-tagline {
    font-size:0.68rem; font-weight:600; letter-spacing:0.22em;
    text-transform:uppercase; color:rgba(255,255,255,0.3);
    margin-top:6px;
}

/* ── HERO HEADLINE ───────────────────────────────────────────── */
.ag-hero {
    text-align:center; margin:30px 0 8px;
    animation: agFadeUp 0.8s 0.1s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-hero h1 {
    font-size:2.1rem; font-weight:900; line-height:1.12;
    letter-spacing:-0.04em; margin:0;
}
.ag-hero .accent {
    display:inline;
    background:linear-gradient(135deg, #00D559 0%, #2D9EFF 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}
.ag-hero-sub {
    font-size:0.92rem; color:rgba(255,255,255,0.5); line-height:1.55;
    margin-top:10px; font-weight:400;
}
.ag-hero-sub strong { color:rgba(255,255,255,0.85); font-weight:700; }

/* ── SOCIAL PROOF COUNTER BAR ────────────────────────────────── */
.ag-proof {
    display:flex; justify-content:center; gap:6px; flex-wrap:wrap;
    margin:24px 0 10px;
    animation: agFadeUp 0.8s 0.2s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-proof-chip {
    display:inline-flex; align-items:center; gap:6px;
    padding:8px 16px; border-radius:100px;
    background:rgba(255,255,255,0.035);
    border:1px solid rgba(255,255,255,0.06);
    font-size:0.76rem; font-weight:600; color:rgba(255,255,255,0.6);
    backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);
    transition:all 0.3s ease;
}
.ag-proof-chip:hover {
    border-color:rgba(0,213,89,0.2);
    background:rgba(0,213,89,0.06);
}
.ag-proof-val {
    font-weight:900; font-size:0.82rem;
    background:linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}

/* ── TESTIMONIAL STRIP ───────────────────────────────────────── */
.ag-testimonial {
    text-align:center; margin:20px 0 26px; padding:18px 24px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.05);
    border-radius:16px; position:relative;
    animation: agFadeUp 0.8s 0.28s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-testimonial::before {
    content:'\201C'; position:absolute; top:8px; left:16px;
    font-size:2.5rem; color:rgba(0,213,89,0.15); font-family:Georgia,serif; line-height:1;
}
.ag-testimonial-text {
    font-size:0.86rem; color:rgba(255,255,255,0.7);
    font-style:italic; line-height:1.55; margin-bottom:8px;
}
.ag-testimonial-author {
    font-size:0.72rem; font-weight:700; color:rgba(0,213,89,0.7);
    letter-spacing:0.02em;
}

/* ── FORM ZONE ───────────────────────────────────────────────── */
/* Tabs */
.ag-page [data-testid="stTabs"] {
    animation: agFadeUp 0.8s 0.35s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-page [data-testid="stTabs"] > [data-baseweb="tab-list"] {
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:16px; padding:4px; gap:4px;
    justify-content:center; margin-bottom:20px;
}
.ag-page [data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius:12px !important; font-weight:800 !important;
    font-size:0.88rem !important; padding:11px 28px !important;
    color:rgba(255,255,255,0.4) !important;
    background:transparent !important;
    border:1px solid transparent !important;
    transition:all 0.3s cubic-bezier(0.22,1,0.36,1) !important;
}
.ag-page [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background:linear-gradient(135deg, rgba(0,213,89,0.12), rgba(45,158,255,0.08)) !important;
    color:#fff !important;
    border-color:rgba(0,213,89,0.2) !important;
    box-shadow:0 4px 20px rgba(0,213,89,0.12) !important;
}
.ag-page [data-testid="stTabs"] [data-baseweb="tab-highlight"],
.ag-page [data-testid="stTabs"] [data-baseweb="tab-border"] {
    display:none !important;
}

/* Form card */
.ag-page [data-testid="stForm"] {
    background:linear-gradient(145deg, rgba(10,16,32,0.85), rgba(8,12,26,0.9)) !important;
    border:1px solid rgba(255,255,255,0.06) !important;
    border-radius:22px !important;
    padding:34px 30px 30px !important;
    backdrop-filter:blur(40px) saturate(1.3) !important;
    -webkit-backdrop-filter:blur(40px) saturate(1.3) !important;
    box-shadow:
        0 30px 100px rgba(0,0,0,0.5),
        0 0 0 1px rgba(255,255,255,0.03) inset,
        0 1px 0 rgba(255,255,255,0.06) inset !important;
    animation:agGlowPulse 8s ease-in-out infinite;
    position:relative; overflow:hidden;
}
/* Top shimmer bar on form */
.ag-page [data-testid="stForm"]::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background:linear-gradient(90deg, transparent, #00D559, #2D9EFF, #c084fc, transparent);
    background-size:400% 100%;
    animation: agBarSlide 3s linear infinite;
}

/* Inputs */
.ag-page [data-testid="stForm"] input {
    background:rgba(255,255,255,0.035) !important;
    border:1.5px solid rgba(255,255,255,0.07) !important;
    border-radius:14px !important;
    color:#FFFFFF !important;
    font-family:'Inter', sans-serif !important;
    font-size:0.92rem !important;
    padding:14px 18px !important;
    transition:all 0.3s cubic-bezier(0.22,1,0.36,1) !important;
    caret-color:#00D559 !important;
}
.ag-page [data-testid="stForm"] input:focus {
    border-color:rgba(0,213,89,0.5) !important;
    box-shadow:0 0 0 4px rgba(0,213,89,0.08), 0 0 30px rgba(0,213,89,0.06) !important;
    background:rgba(255,255,255,0.05) !important;
    outline:none !important;
}
.ag-page [data-testid="stForm"] input::placeholder {
    color:rgba(255,255,255,0.22) !important;
    font-weight:400 !important;
}
.ag-page [data-testid="stForm"] label {
    color:rgba(255,255,255,0.55) !important;
    font-weight:700 !important; font-size:0.8rem !important;
    letter-spacing:0.03em !important;
    text-transform:uppercase !important;
}
/* Password visibility toggles */
.ag-page [data-testid="stForm"] [data-testid="stTextInputRootElement"] button {
    color:rgba(255,255,255,0.3) !important;
}

/* CTA buttons */
.ag-page [data-testid="stForm"] button[kind="primaryFormSubmit"],
.ag-page [data-testid="stForm"] button[type="submit"] {
    background:linear-gradient(135deg, #00D559 0%, #00C04E 50%, #00A843 100%) !important;
    color:#fff !important;
    font-weight:900 !important; font-size:1.05rem !important;
    letter-spacing:-0.01em !important;
    border:none !important; border-radius:16px !important;
    padding:16px 36px !important;
    margin-top:12px !important;
    box-shadow:
        0 6px 30px rgba(0,213,89,0.35),
        0 1px 0 rgba(255,255,255,0.15) inset !important;
    transition:all 0.25s cubic-bezier(0.22,1,0.36,1) !important;
    position:relative; overflow:hidden;
    text-shadow:0 1px 2px rgba(0,0,0,0.2) !important;
}
.ag-page [data-testid="stForm"] button[kind="primaryFormSubmit"]::after,
.ag-page [data-testid="stForm"] button[type="submit"]::after {
    content:''; position:absolute; top:0; width:60px; height:100%;
    background:linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
.ag-page [data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
.ag-page [data-testid="stForm"] button[type="submit"]:hover {
    transform:translateY(-3px) scale(1.01) !important;
    box-shadow:
        0 10px 40px rgba(0,213,89,0.45),
        0 1px 0 rgba(255,255,255,0.2) inset !important;
}

/* ── COMPARISON TABLE ────────────────────────────────────────── */
.ag-compare {
    margin:28px 0 4px;
    animation: agFadeUp 0.8s 0.45s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-compare-title {
    text-align:center; font-size:0.72rem; font-weight:800;
    text-transform:uppercase; letter-spacing:0.15em;
    color:rgba(255,255,255,0.3); margin-bottom:12px;
}
.ag-compare-grid {
    display:grid; grid-template-columns:1fr 1fr; gap:10px;
}
.ag-compare-col {
    border-radius:16px; padding:20px 16px;
    text-align:center;
}
.ag-compare-col.them {
    background:rgba(242,67,54,0.05);
    border:1px solid rgba(242,67,54,0.12);
}
.ag-compare-col.us {
    background:rgba(0,213,89,0.05);
    border:1px solid rgba(0,213,89,0.15);
    position:relative;
}
.ag-compare-col.us::after {
    content:'RECOMMENDED'; position:absolute; top:-8px; left:50%; transform:translateX(-50%);
    font-size:0.55rem; font-weight:800; letter-spacing:0.12em;
    color:#0A0E14; background:#00D559;
    padding:2px 10px; border-radius:100px;
}
.ag-compare-header {
    font-size:0.78rem; font-weight:800; margin-bottom:14px;
    letter-spacing:0.02em;
}
.ag-compare-col.them .ag-compare-header { color:rgba(242,67,54,0.8); }
.ag-compare-col.us .ag-compare-header { color:#00D559; }
.ag-compare-item {
    font-size:0.72rem; color:rgba(255,255,255,0.5);
    padding:5px 0; line-height:1.4; display:flex; align-items:center; gap:6px;
}
.ag-compare-col.them .ag-compare-item::before {
    content:'✗'; color:rgba(242,67,54,0.6); font-weight:800; font-size:0.7rem; flex-shrink:0;
}
.ag-compare-col.us .ag-compare-item::before {
    content:'✓'; color:#00D559; font-weight:800; font-size:0.7rem; flex-shrink:0;
}

/* ── FEATURE PILLARS ─────────────────────────────────────────── */
.ag-pillars {
    display:grid; grid-template-columns:repeat(3, 1fr); gap:10px;
    margin:24px 0 0;
    animation: agFadeUp 0.8s 0.55s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-pillar {
    background:rgba(255,255,255,0.025);
    border:1px solid rgba(255,255,255,0.05);
    border-radius:16px; padding:18px 10px 14px;
    text-align:center;
    transition:all 0.3s cubic-bezier(0.22,1,0.36,1);
    position:relative; overflow:hidden;
}
.ag-pillar::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background:var(--pillar-color, rgba(0,213,89,0.3));
    opacity:0; transition:opacity 0.3s;
}
.ag-pillar:hover {
    border-color:rgba(255,255,255,0.1);
    transform:translateY(-4px);
    box-shadow:0 12px 32px rgba(0,0,0,0.3);
}
.ag-pillar:hover::before { opacity:1; }
.ag-pillar-icon { font-size:1.6rem; margin-bottom:6px; display:block; animation:agFloat 4s ease-in-out infinite; }
.ag-pillar-name {
    font-size:0.7rem; font-weight:800; color:rgba(255,255,255,0.8);
    letter-spacing:-0.01em; line-height:1.2;
}
.ag-pillar-desc {
    font-size:0.58rem; color:rgba(255,255,255,0.3);
    margin-top:3px; font-weight:500;
}

/* ── TRUST STRIP ─────────────────────────────────────────────── */
.ag-trust {
    display:flex; justify-content:center; align-items:center;
    gap:24px; margin:24px 0 8px; flex-wrap:wrap;
    animation: agFadeUp 0.8s 0.65s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-trust-item {
    display:flex; align-items:center; gap:6px;
    font-size:0.68rem; font-weight:600; color:rgba(255,255,255,0.3);
}
.ag-trust-icon {
    width:18px; height:18px; border-radius:50%;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:0.6rem;
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06);
}

/* ── USERS COUNTER ───────────────────────────────────────────── */
.ag-users {
    text-align:center; margin:20px 0;
    animation: agFadeUp 0.8s 0.7s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-users-avatars {
    display:inline-flex; margin-right:8px;
}
.ag-users-avatar {
    width:28px; height:28px; border-radius:50%;
    border:2px solid #0A0E14;
    margin-left:-8px;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:0.6rem; font-weight:700;
}
.ag-users-avatar:first-child { margin-left:0; }
.ag-users-avatar:nth-child(1) { background:linear-gradient(135deg,#00D559,#2D9EFF); color:#fff; }
.ag-users-avatar:nth-child(2) { background:linear-gradient(135deg,#c084fc,#2D9EFF); color:#fff; }
.ag-users-avatar:nth-child(3) { background:linear-gradient(135deg,#F9C62B,#FF6B35); color:#fff; }
.ag-users-avatar:nth-child(4) { background:linear-gradient(135deg,#2D9EFF,#00D559); color:#fff; }
.ag-users-text {
    font-size:0.74rem; color:rgba(255,255,255,0.45); font-weight:500;
    vertical-align:middle;
}
.ag-users-text strong {
    color:#00D559; font-weight:800;
}

/* ── FOOTER ──────────────────────────────────────────────────── */
.ag-footer {
    text-align:center; padding:24px 0 40px;
    font-size:0.62rem; color:rgba(255,255,255,0.15); line-height:1.7;
    animation: agFadeUp 0.8s 0.75s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-footer a { color:rgba(255,255,255,0.25); text-decoration:underline; }

/* ── RESPONSIVE ──────────────────────────────────────────────── */
@media (max-width:520px) {
    .ag-page { padding:0 14px; }
    .ag-brand { padding-top:52px; }
    .ag-hero h1 { font-size:1.55rem; }
    .ag-hero-sub { font-size:0.84rem; }
    .ag-logo-ring, .ag-logo-ring img { width:72px; height:72px; }
    .ag-brand-name { font-size:1.6rem; }
    .ag-compare-grid { gap:8px; }
    .ag-compare-col { padding:16px 12px; }
    .ag-pillars { grid-template-columns:repeat(2, 1fr); }
    .ag-page [data-testid="stForm"] { padding:26px 20px 24px !important; border-radius:18px !important; }
    .ag-proof-chip { padding:6px 12px; font-size:0.7rem; }
    .ag-urgency { font-size:0.66rem; height:36px; }
}
@media (max-width:360px) {
    .ag-pillars { grid-template-columns:1fr 1fr; }
    .ag-hero h1 { font-size:1.35rem; }
    .ag-compare-item { font-size:0.66rem; }
}
</style>
"""

# ── Main gate function ────────────────────────────────────────

def require_login() -> bool:
    """Render a signup/login gate if the user is not logged in.

    Returns True if the user is authenticated. Returns False (and
    renders the full-screen gate) if they are not — the caller
    should call ``st.stop()`` immediately.

    Non-production bypass: when ``SMARTAI_PRODUCTION`` is not
    "true", the gate is skipped entirely so local dev is
    friction-free.
    """
    # Dev bypass
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return True

    if is_logged_in():
        return True

    # ── Render the gate ───────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    # Logo base64
    _logo_b64 = _get_logo_b64()
    _logo_tag = (
        f'<img src="data:image/png;base64,{_logo_b64}" alt="Smart Pick Pro">'
        if _logo_b64
        else '<div style="font-size:2.8rem;">🏀</div>'
    )

    # ── Star-field particles (30 CSS-only stars) ──────────
    import random as _rnd
    _stars_html = ""
    for _i in range(30):
        _x = _rnd.randint(0, 100)
        _y = _rnd.randint(0, 100)
        _sz = _rnd.choice([1, 1, 1, 2, 2, 3])
        _dur = _rnd.uniform(2.5, 7)
        _delay = _rnd.uniform(0, 5)
        _stars_html += (
            f'<div class="ag-star" style="left:{_x}%;top:{_y}%;'
            f'width:{_sz}px;height:{_sz}px;'
            f'--dur:{_dur:.1f}s;--delay:{_delay:.1f}s;"></div>'
        )

    # ── Full-screen cinematic markup ──────────────────────
    st.markdown(f"""
    <!-- Full-screen canvas -->
    <div class="ag-canvas">
      <div class="ag-stars">{_stars_html}</div>
      <div class="ag-orb ag-orb-1"></div>
      <div class="ag-orb ag-orb-2"></div>
      <div class="ag-orb ag-orb-3"></div>
      <div class="ag-orb ag-orb-4"></div>
      <div class="ag-scan"></div>
      <div class="ag-grid"></div>
    </div>

    <!-- Urgency bar -->
    <div class="ag-urgency">
      <span class="ag-urgency-live"><span class="ag-urgency-dot"></span> LIVE</span>
      NBA Playoffs &mdash; tonight's slate is being analyzed right now
    </div>

    <!-- Scroll wrapper -->
    <div class="ag-scroll">
    <div class="ag-page">

    <!-- Brand -->
    <div class="ag-brand">
      <div class="ag-logo-ring">{_logo_tag}</div>
      <div class="ag-brand-name">Smart Pick Pro</div>
      <div class="ag-brand-tagline">AI-Powered Sports Intelligence</div>
    </div>

    <!-- Hero -->
    <div class="ag-hero">
      <h1>Stop Guessing.<br><span class="accent">Start Winning.</span></h1>
      <div class="ag-hero-sub">
        Join the sharpest prop bettors on the planet.<br>
        <strong>Free forever</strong> &mdash; no credit card, no catches.
      </div>
    </div>

    <!-- Social proof chips -->
    <div class="ag-proof">
      <div class="ag-proof-chip">🏀 <span class="ag-proof-val">300+</span>&nbsp;Props / Night</div>
      <div class="ag-proof-chip">🎯 <span class="ag-proof-val">62%</span>&nbsp;Verified Hit Rate</div>
      <div class="ag-proof-chip">🤖 <span class="ag-proof-val">6</span>&nbsp;AI Models</div>
    </div>

    <!-- Testimonial -->
    <div class="ag-testimonial">
      <div class="ag-testimonial-text">
        I went from randomly picking parlays to having a real edge. SPP&rsquo;s
        Quantum Matrix literally changed how I bet.
      </div>
      <div class="ag-testimonial-author">&mdash; @sharpbettor_mike &middot; SPP member since Jan 2025</div>
    </div>

    </div></div>
    """, unsafe_allow_html=True)

    # ── Tabs (Streamlit widgets) ──────────────────────────
    tab_signup, tab_login = st.tabs(["⚡  Get Instant Access", "🔓  Log In"])

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            su_name = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            su_pw = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password", key="_su_pw2")
            su_submit = st.form_submit_button("⚡ Create Free Account — It Takes 10 Seconds", use_container_width=True, type="primary")

        if su_submit:
            if not su_email or not _valid_email(su_email):
                st.error("Please enter a valid email address.")
            elif pw_err := _valid_password(su_pw):
                st.error(pw_err)
            elif su_pw != su_pw2:
                st.error("Passwords don't match.")
            elif _email_exists(su_email):
                st.error("An account with this email already exists. Please log in instead.")
            else:
                ok = _create_user(su_email, su_pw, su_name)
                if ok:
                    user = _authenticate_user(su_email, su_pw)
                    if user:
                        _set_logged_in(user)
                        st.success("Account created! Welcome to Smart Pick Pro.")
                        st.rerun()
                    else:
                        st.error("Account created but login failed. Please try logging in.")
                else:
                    st.error("Could not create account. Please try again.")

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            li_email = st.text_input("Email Address", placeholder="you@example.com", key="_li_email")
            li_pw = st.text_input("Password", type="password", placeholder="Enter your password", key="_li_pw")
            li_submit = st.form_submit_button("🔓 Log In", use_container_width=True, type="primary")

        if li_submit:
            if not li_email or not _valid_email(li_email):
                st.error("Please enter a valid email address.")
            elif not li_pw:
                st.error("Please enter your password.")
            else:
                user = _authenticate_user(li_email, li_pw)
                if user:
                    _set_logged_in(user)
                    st.success(f"Welcome back, {user.get('display_name', '')}!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    # ── Below-fold conversion content ─────────────────────
    st.markdown("""
    <!-- Comparison: Them vs Us -->
    <div class="ag-compare">
      <div class="ag-compare-title">Why Smart Bettors Switch</div>
      <div class="ag-compare-grid">
        <div class="ag-compare-col them">
          <div class="ag-compare-header">❌ Gut Feeling</div>
          <div class="ag-compare-item">Random parlays</div>
          <div class="ag-compare-item">No data backing</div>
          <div class="ag-compare-item">Chasing losses</div>
          <div class="ag-compare-item">Bankroll guesswork</div>
        </div>
        <div class="ag-compare-col us">
          <div class="ag-compare-header">Smart Pick Pro</div>
          <div class="ag-compare-item">AI-scored every prop</div>
          <div class="ag-compare-item">6 models per pick</div>
          <div class="ag-compare-item">SAFE Score™ system</div>
          <div class="ag-compare-item">Bankroll management</div>
        </div>
      </div>
    </div>

    <!-- Feature pillars -->
    <div class="ag-pillars">
      <div class="ag-pillar" style="--pillar-color:rgba(0,213,89,0.4);">
        <span class="ag-pillar-icon">🎯</span>
        <div class="ag-pillar-name">SAFE Score™</div>
        <div class="ag-pillar-desc">Every pick rated 0-100</div>
      </div>
      <div class="ag-pillar" style="--pillar-color:rgba(45,158,255,0.4);">
        <span class="ag-pillar-icon">🧠</span>
        <div class="ag-pillar-name">Quantum Engine</div>
        <div class="ag-pillar-desc">6 AI models fused</div>
      </div>
      <div class="ag-pillar" style="--pillar-color:rgba(192,132,252,0.4);">
        <span class="ag-pillar-icon">📡</span>
        <div class="ag-pillar-name">Live Sweat</div>
        <div class="ag-pillar-desc">Real-time tracking</div>
      </div>
      <div class="ag-pillar" style="--pillar-color:rgba(249,198,43,0.4);">
        <span class="ag-pillar-icon">🔬</span>
        <div class="ag-pillar-name">Prop Scanner</div>
        <div class="ag-pillar-desc">Find edge in seconds</div>
      </div>
      <div class="ag-pillar" style="--pillar-color:rgba(0,213,89,0.4);">
        <span class="ag-pillar-icon">🎙️</span>
        <div class="ag-pillar-name">The Studio</div>
        <div class="ag-pillar-desc">Joseph's AI brain</div>
      </div>
      <div class="ag-pillar" style="--pillar-color:rgba(45,158,255,0.4);">
        <span class="ag-pillar-icon">🛡️</span>
        <div class="ag-pillar-name">Risk Shield</div>
        <div class="ag-pillar-desc">Protect your roll</div>
      </div>
    </div>

    <!-- Trust strip -->
    <div class="ag-trust">
      <div class="ag-trust-item"><span class="ag-trust-icon">🔒</span> 256-bit Encrypted</div>
      <div class="ag-trust-item"><span class="ag-trust-icon">💳</span> No Credit Card</div>
      <div class="ag-trust-item"><span class="ag-trust-icon">🚫</span> Never Sell Data</div>
    </div>

    <!-- User counter -->
    <div class="ag-users">
      <span class="ag-users-avatars">
        <span class="ag-users-avatar">J</span>
        <span class="ag-users-avatar">M</span>
        <span class="ag-users-avatar">K</span>
        <span class="ag-users-avatar">A</span>
      </span>
      <span class="ag-users-text"><strong>500+</strong> bettors already signed up</span>
    </div>

    <!-- Footer -->
    <div class="ag-footer">
      &copy; 2025 Smart Pick Pro &middot; For entertainment &amp; educational purposes only &middot; 21+<br>
      <a href="https://www.ncpgambling.org/" target="_blank">National Council on Problem Gambling &middot; 1-800-GAMBLER</a>
    </div>
    """, unsafe_allow_html=True)

    return False
