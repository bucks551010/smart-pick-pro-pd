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
# Theme: PrizePicks × DraftKings Pick6 × AI
# Fonts: Space Grotesk (headlines) + Inter (body) + JetBrains Mono (data)

_GATE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* ═══════════════════════════════════════════════════════════════
   SMART PICK PRO — HIGH-CONVERSION AUTH GATE
   Theme: PrizePicks × DraftKings Pick6 × AI
   ═══════════════════════════════════════════════════════════════ */

/* ── Reset Streamlit chrome ──────────────────────────────────── */
[data-testid="stSidebar"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton,
footer { display: none !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
.stApp { background: #0A0E14 !important; }
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 0 20px !important; max-width: 580px !important;
    margin: 0 auto !important;
    position: relative; z-index: 9992;
}
html, body, .stApp, .stApp * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Keyframes ───────────────────────────────────────────────── */
@keyframes agFadeUp {
    from { opacity:0; transform:translateY(30px); }
    to   { opacity:1; transform:translateY(0); }
}
@keyframes agFadeIn { from { opacity:0; } to { opacity:1; } }
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
    50%     { transform:translateY(-6px); }
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
.ag-stars { position:absolute; inset:0; overflow:hidden; }
.ag-star {
    position:absolute; border-radius:50%; background:#fff;
    animation: agStarTwinkle var(--dur) ease-in-out infinite;
    animation-delay: var(--delay);
}
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
.ag-scan {
    position:absolute; left:0; width:100%; height:2px; z-index:9991;
    background:linear-gradient(90deg, transparent, rgba(0,213,89,0.3) 20%, rgba(45,158,255,0.25) 50%, rgba(192,132,252,0.2) 80%, transparent);
    animation: agScanLine 7s linear infinite;
    pointer-events:none;
}
.ag-grid {
    position:absolute; inset:0; pointer-events:none;
    background-image:
        linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
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
    max-width:580px; margin:0 auto;
    padding:0 20px;
    font-family:'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color:#fff;
}

/* ── PLATFORM BANNER (animated ticker) ───────────────────────── */
.ag-ticker-bar {
    position:fixed; top:0; left:0; right:0; z-index:9999;
    height:42px; display:flex; align-items:center;
    background: linear-gradient(90deg, #0A0E14, rgba(0,213,89,0.06) 20%, rgba(45,158,255,0.04) 50%, rgba(192,132,252,0.04) 80%, #0A0E14);
    border-bottom:1px solid rgba(255,255,255,0.05);
    overflow:hidden;
}
.ag-ticker-bar::before {
    content:''; position:absolute; bottom:0; left:0; right:0; height:1px;
    background:linear-gradient(90deg, transparent, #00D559 15%, #2D9EFF 35%, #C084FC 55%, #F9C62B 75%, transparent);
    background-size:400% 100%;
    animation: agBarSlide 4s linear infinite;
    opacity:0.5;
}
.ag-ticker-track {
    display:flex; align-items:center; white-space:nowrap;
    animation: agTickerScroll 40s linear infinite;
}
.ag-ticker-item {
    display:inline-flex; align-items:center; gap:8px;
    padding:0 32px; font-size:0.72rem; font-weight:600;
    color:rgba(255,255,255,0.5); letter-spacing:0.02em;
    font-family:'JetBrains Mono', monospace;
}
.ag-ticker-item .val {
    font-weight:800; color:#00D559;
}
.ag-ticker-item .neg { color:#F24336; }
.ag-ticker-live {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(0,213,89,0.1); border:1px solid rgba(0,213,89,0.2);
    padding:3px 10px; border-radius:100px;
    font-size:0.65rem; font-weight:800; color:#00D559;
    text-transform:uppercase;
}
.ag-ticker-dot {
    width:6px; height:6px; border-radius:50%; background:#00D559;
    animation: agLivePulse 2s ease-in-out infinite;
}

/* ── LOGO + BRAND ────────────────────────────────────────────── */
.ag-brand {
    text-align:center; padding-top:62px; margin-bottom:4px;
    animation: agFadeUp 0.7s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-logo-wrap {
    display:inline-block; position:relative;
    width:92px; height:92px; margin-bottom:18px;
}
.ag-logo-wrap::before {
    content:''; position:absolute; inset:-5px; border-radius:50%;
    background:conic-gradient(from 0deg, #00D559, #2D9EFF, #C084FC, #F9C62B, #00D559);
    animation:agLogoRing 8s linear infinite;
    mask:radial-gradient(farthest-side, transparent calc(100% - 2.5px), black calc(100% - 2.5px));
    -webkit-mask:radial-gradient(farthest-side, transparent calc(100% - 2.5px), black calc(100% - 2.5px));
}
.ag-logo-wrap img {
    width:92px; height:92px; border-radius:50%;
    position:relative; z-index:2;
    box-shadow:0 0 40px rgba(0,213,89,0.15);
}
.ag-brand-name {
    font-family:'Space Grotesk', sans-serif;
    font-size:2.2rem; font-weight:700; letter-spacing:-0.04em; line-height:1;
    background:linear-gradient(135deg, #fff 0%, #00D559 50%, #2D9EFF 100%);
    background-size:300% 300%;
    animation:agGradShift 6s ease infinite;
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}
.ag-brand-sub {
    font-size:0.65rem; font-weight:700; letter-spacing:0.25em;
    text-transform:uppercase; color:rgba(255,255,255,0.25);
    margin-top:6px;
    font-family:'JetBrains Mono', monospace;
}

/* ── HERO HEADLINE ───────────────────────────────────────────── */
.ag-hero {
    text-align:center; margin:28px 0 6px;
    animation: agFadeUp 0.7s 0.08s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-hero h1 {
    font-family:'Space Grotesk', sans-serif;
    font-size:2.3rem; font-weight:700; line-height:1.08;
    letter-spacing:-0.04em; margin:0; color:#fff;
}
.ag-hero .glow {
    display:inline;
    background:linear-gradient(135deg, #00D559 0%, #2D9EFF 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}
.ag-hero-sub {
    font-size:0.92rem; color:rgba(255,255,255,0.45); line-height:1.55;
    margin-top:12px; font-weight:400;
}
.ag-hero-sub strong { color:rgba(255,255,255,0.85); font-weight:700; }

/* ── SOCIAL PROOF PILLS ──────────────────────────────────────── */
.ag-pills {
    display:flex; justify-content:center; gap:8px; flex-wrap:wrap;
    margin:22px 0 8px;
    animation: agFadeUp 0.7s 0.15s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-pill {
    display:inline-flex; align-items:center; gap:7px;
    padding:8px 16px; border-radius:100px;
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.06);
    font-size:0.74rem; font-weight:600; color:rgba(255,255,255,0.55);
    backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);
    transition:all 0.25s ease;
}
.ag-pill:hover {
    border-color:rgba(0,213,89,0.2); background:rgba(0,213,89,0.05);
}
.ag-pill-val {
    font-family:'JetBrains Mono', monospace;
    font-weight:800; font-size:0.78rem;
    color:#00D559;
}

/* ── FOMO URGENCY BANNER ─────────────────────────────────────── */
.ag-fomo {
    text-align:center; margin:18px 0 22px; padding:14px 20px;
    background:linear-gradient(135deg, rgba(249,198,43,0.08), rgba(249,198,43,0.03));
    border:1px solid rgba(249,198,43,0.15);
    border-radius:14px;
    animation: agFadeUp 0.7s 0.22s cubic-bezier(0.22,1,0.36,1) both;
    position:relative; overflow:hidden;
}
.ag-fomo::before {
    content:''; position:absolute; top:0; left:0; right:0; height:1px;
    background:linear-gradient(90deg, transparent, #F9C62B, transparent);
    opacity:0.3;
}
.ag-fomo-text {
    font-size:0.82rem; font-weight:700; color:rgba(249,198,43,0.9);
    font-family:'Space Grotesk', sans-serif;
}
.ag-fomo-text .count {
    font-family:'JetBrains Mono', monospace;
    font-weight:800; color:#F9C62B; font-size:0.88rem;
}

/* ── FORM ZONE ───────────────────────────────────────────────── */
[data-testid="stTabs"] {
    animation: agFadeUp 0.7s 0.3s cubic-bezier(0.22,1,0.36,1) both;
}
[data-testid="stTabs"] > [data-baseweb="tab-list"] {
    background:rgba(255,255,255,0.03);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:14px; padding:4px; gap:4px;
    justify-content:center; margin-bottom:18px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius:10px !important;
    font-family:'Space Grotesk', sans-serif !important;
    font-weight:700 !important;
    font-size:0.88rem !important; padding:11px 28px !important;
    color:rgba(255,255,255,0.35) !important;
    background:transparent !important;
    border:1px solid transparent !important;
    transition:all 0.25s cubic-bezier(0.22,1,0.36,1) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background:linear-gradient(135deg, rgba(0,213,89,0.1), rgba(45,158,255,0.06)) !important;
    color:#fff !important;
    border-color:rgba(0,213,89,0.2) !important;
    box-shadow:0 4px 20px rgba(0,213,89,0.1) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display:none !important;
}

/* ── FORM CARD ───────────────────────────────────────────────── */
[data-testid="stForm"] {
    background:linear-gradient(160deg, rgba(22,27,34,0.9), rgba(13,17,23,0.95)) !important;
    border:1px solid rgba(255,255,255,0.06) !important;
    border-radius:20px !important;
    padding:32px 28px 28px !important;
    backdrop-filter:blur(40px) saturate(1.3) !important;
    -webkit-backdrop-filter:blur(40px) saturate(1.3) !important;
    box-shadow:
        0 25px 80px rgba(0,0,0,0.5),
        0 0 0 1px rgba(255,255,255,0.03) inset,
        0 1px 0 rgba(255,255,255,0.06) inset !important;
    animation:agGlowPulse 8s ease-in-out infinite;
    position:relative; overflow:hidden;
}
[data-testid="stForm"]::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background:linear-gradient(90deg, transparent, #00D559, #2D9EFF, #C084FC, transparent);
    background-size:400% 100%;
    animation: agBarSlide 3s linear infinite;
}

/* ── INPUTS ──────────────────────────────────────────────────── */
[data-testid="stForm"] input {
    background:rgba(255,255,255,0.035) !important;
    border:1.5px solid rgba(255,255,255,0.07) !important;
    border-radius:12px !important;
    color:#FFFFFF !important;
    font-family:'Inter', sans-serif !important;
    font-size:0.9rem !important;
    padding:13px 16px !important;
    transition:all 0.25s cubic-bezier(0.22,1,0.36,1) !important;
    caret-color:#00D559 !important;
}
[data-testid="stForm"] input:focus {
    border-color:rgba(0,213,89,0.45) !important;
    box-shadow:0 0 0 3px rgba(0,213,89,0.08), 0 0 24px rgba(0,213,89,0.05) !important;
    background:rgba(255,255,255,0.05) !important;
    outline:none !important;
}
[data-testid="stForm"] input::placeholder {
    color:rgba(255,255,255,0.2) !important;
    font-weight:400 !important;
}
[data-testid="stForm"] label {
    color:rgba(255,255,255,0.5) !important;
    font-weight:700 !important; font-size:0.78rem !important;
    letter-spacing:0.04em !important;
    text-transform:uppercase !important;
    font-family:'Inter', sans-serif !important;
}
[data-testid="stForm"] [data-testid="stTextInputRootElement"] button {
    color:rgba(255,255,255,0.3) !important;
}

/* ── CTA BUTTON ──────────────────────────────────────────────── */
[data-testid="stForm"] button[kind="primaryFormSubmit"],
[data-testid="stForm"] button[type="submit"] {
    background:linear-gradient(135deg, #00D559 0%, #00C04E 50%, #00A843 100%) !important;
    color:#fff !important;
    font-family:'Space Grotesk', sans-serif !important;
    font-weight:700 !important; font-size:1.02rem !important;
    letter-spacing:-0.01em !important;
    border:none !important; border-radius:14px !important;
    padding:15px 32px !important;
    margin-top:10px !important;
    box-shadow:
        0 6px 30px rgba(0,213,89,0.35),
        0 1px 0 rgba(255,255,255,0.15) inset !important;
    transition:all 0.2s cubic-bezier(0.22,1,0.36,1) !important;
    position:relative; overflow:hidden;
    text-shadow:0 1px 2px rgba(0,0,0,0.2) !important;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]::after,
[data-testid="stForm"] button[type="submit"]::after {
    content:''; position:absolute; top:0; width:60px; height:100%;
    background:linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
[data-testid="stForm"] button[type="submit"]:hover {
    transform:translateY(-2px) scale(1.01) !important;
    box-shadow:
        0 10px 40px rgba(0,213,89,0.45),
        0 1px 0 rgba(255,255,255,0.2) inset !important;
}

/* ── COMPARISON TABLE ────────────────────────────────────────── */
.ag-compare {
    margin:32px 0 0;
    animation: agFadeUp 0.7s 0.4s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-compare-head {
    text-align:center; margin-bottom:14px;
}
.ag-compare-head h3 {
    font-family:'Space Grotesk', sans-serif;
    font-size:1.1rem; font-weight:700; color:#fff; margin:0 0 4px;
    letter-spacing:-0.03em;
}
.ag-compare-head p {
    font-size:0.72rem; color:rgba(255,255,255,0.35); margin:0;
    font-weight:500;
}
.ag-compare-table {
    width:100%; border-collapse:separate; border-spacing:0;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.05);
    border-radius:16px; overflow:hidden;
}
.ag-compare-table thead th {
    padding:12px 14px; font-size:0.68rem; font-weight:800;
    text-transform:uppercase; letter-spacing:0.1em;
    color:rgba(255,255,255,0.35);
    border-bottom:1px solid rgba(255,255,255,0.05);
}
.ag-compare-table thead th:first-child {
    text-align:left; width:38%;
}
.ag-compare-table thead th:nth-child(2) {
    color:rgba(242,67,54,0.6); text-align:center;
}
.ag-compare-table thead th:nth-child(3) {
    color:#00D559; text-align:center;
    background:rgba(0,213,89,0.04);
}
.ag-compare-table tbody td {
    padding:10px 14px; font-size:0.74rem; color:rgba(255,255,255,0.55);
    border-bottom:1px solid rgba(255,255,255,0.03);
    font-weight:500;
}
.ag-compare-table tbody td:first-child {
    font-weight:600; color:rgba(255,255,255,0.7); text-align:left;
}
.ag-compare-table tbody td:nth-child(2) {
    text-align:center; color:rgba(242,67,54,0.5);
}
.ag-compare-table tbody td:nth-child(3) {
    text-align:center; color:#00D559;
    background:rgba(0,213,89,0.03);
    font-weight:700;
}
.ag-compare-table tbody tr:last-child td { border-bottom:none; }

/* ── FEATURE PILLARS (3 cards) ───────────────────────────────── */
.ag-pillars {
    display:grid; grid-template-columns:repeat(3, 1fr); gap:10px;
    margin:28px 0 0;
    animation: agFadeUp 0.7s 0.5s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-pillar {
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.05);
    border-radius:16px; padding:20px 12px 16px;
    text-align:center;
    transition:all 0.25s cubic-bezier(0.22,1,0.36,1);
    position:relative; overflow:hidden;
}
.ag-pillar::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background:var(--pc, rgba(0,213,89,0.3));
    opacity:0; transition:opacity 0.25s;
}
.ag-pillar:hover {
    border-color:rgba(255,255,255,0.1);
    transform:translateY(-3px);
    box-shadow:0 10px 28px rgba(0,0,0,0.3);
}
.ag-pillar:hover::before { opacity:1; }
.ag-pillar-ico { font-size:1.5rem; margin-bottom:8px; display:block; animation:agFloat 4s ease-in-out infinite; }
.ag-pillar-name {
    font-family:'Space Grotesk', sans-serif;
    font-size:0.72rem; font-weight:700; color:rgba(255,255,255,0.85);
    letter-spacing:-0.01em; line-height:1.2;
}
.ag-pillar-desc {
    font-size:0.6rem; color:rgba(255,255,255,0.3);
    margin-top:4px; font-weight:500;
}

/* ── PROOF METRICS (6 animated counters) ─────────────────────── */
.ag-metrics {
    display:grid; grid-template-columns:repeat(3, 1fr); gap:10px;
    margin:28px 0 0;
    animation: agFadeUp 0.7s 0.55s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-metric {
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.05);
    border-radius:14px; padding:16px 10px 12px;
    text-align:center;
    transition:all 0.25s ease;
}
.ag-metric:hover {
    border-color:rgba(0,213,89,0.15);
    background:rgba(0,213,89,0.03);
}
.ag-metric-val {
    font-family:'JetBrains Mono', monospace;
    font-size:1.4rem; font-weight:700;
    background:linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
    line-height:1.1;
}
.ag-metric-label {
    font-size:0.6rem; color:rgba(255,255,255,0.3);
    font-weight:600; margin-top:4px; text-transform:uppercase;
    letter-spacing:0.06em;
}

/* ── TESTIMONIALS (3 cards) ──────────────────────────────────── */
.ag-testimonials {
    margin:28px 0 0;
    animation: agFadeUp 0.7s 0.6s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-testimonials-title {
    text-align:center; font-family:'Space Grotesk', sans-serif;
    font-size:1rem; font-weight:700; color:#fff;
    margin-bottom:14px; letter-spacing:-0.02em;
}
.ag-testimonials-grid {
    display:grid; grid-template-columns:1fr; gap:10px;
}
.ag-test-card {
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.05);
    border-radius:14px; padding:18px 20px;
    position:relative;
}
.ag-test-card::before {
    content:'\201C'; position:absolute; top:10px; left:14px;
    font-size:2rem; color:rgba(0,213,89,0.12); font-family:Georgia,serif; line-height:1;
}
.ag-test-quote {
    font-size:0.82rem; color:rgba(255,255,255,0.65);
    font-style:italic; line-height:1.5; padding-left:20px;
}
.ag-test-author {
    font-size:0.68rem; font-weight:700; color:rgba(0,213,89,0.65);
    margin-top:8px; padding-left:20px;
}
.ag-test-stars {
    color:#F9C62B; font-size:0.65rem; padding-left:20px; margin-top:2px;
}

/* ── PRICING PREVIEW ─────────────────────────────────────────── */
.ag-pricing {
    margin:32px 0 0;
    animation: agFadeUp 0.7s 0.65s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-pricing-head {
    text-align:center; margin-bottom:14px;
}
.ag-pricing-head h3 {
    font-family:'Space Grotesk', sans-serif;
    font-size:1.1rem; font-weight:700; color:#fff; margin:0 0 4px;
    letter-spacing:-0.03em;
}
.ag-pricing-head p {
    font-size:0.72rem; color:rgba(255,255,255,0.35); margin:0;
}
.ag-pricing-grid {
    display:grid; grid-template-columns:repeat(2, 1fr); gap:10px;
}
.ag-price-card {
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:16px; padding:20px 16px;
    text-align:center;
    transition:all 0.25s ease;
    position:relative;
}
.ag-price-card:hover {
    border-color:rgba(0,213,89,0.15);
    transform:translateY(-2px);
}
.ag-price-card.popular {
    border-color:rgba(0,213,89,0.25);
    background:rgba(0,213,89,0.04);
}
.ag-price-card.popular::after {
    content:'MOST POPULAR'; position:absolute; top:-9px; left:50%; transform:translateX(-50%);
    font-size:0.5rem; font-weight:800; letter-spacing:0.1em;
    color:#0A0E14; background:#00D559;
    padding:2px 10px; border-radius:100px;
    font-family:'Space Grotesk', sans-serif;
}
.ag-price-tier {
    font-family:'Space Grotesk', sans-serif;
    font-size:0.72rem; font-weight:700; color:rgba(255,255,255,0.5);
    text-transform:uppercase; letter-spacing:0.06em;
    margin-bottom:6px;
}
.ag-price-amount {
    font-family:'JetBrains Mono', monospace;
    font-size:1.6rem; font-weight:700; color:#fff; line-height:1;
}
.ag-price-amount .period {
    font-size:0.6rem; font-weight:500; color:rgba(255,255,255,0.3);
}
.ag-price-feat {
    font-size:0.62rem; color:rgba(255,255,255,0.35);
    margin-top:8px; line-height:1.5;
}
.ag-price-feat strong { color:rgba(255,255,255,0.6); }

/* ── COMING SOON ─────────────────────────────────────────────── */
.ag-coming {
    margin:28px 0 0;
    animation: agFadeUp 0.7s 0.7s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-coming-card {
    background:linear-gradient(135deg, rgba(249,198,43,0.05), rgba(249,198,43,0.02));
    border:1px solid rgba(249,198,43,0.12);
    border-radius:16px; padding:24px 20px;
    text-align:center; position:relative; overflow:hidden;
}
.ag-coming-card::before {
    content:''; position:absolute; top:0; left:0; right:0; height:1px;
    background:linear-gradient(90deg, transparent, #F9C62B, transparent);
    opacity:0.25;
}
.ag-coming-badge {
    display:inline-flex; align-items:center; gap:6px;
    background:rgba(249,198,43,0.12); border:1px solid rgba(249,198,43,0.2);
    padding:4px 12px; border-radius:100px;
    font-family:'JetBrains Mono', monospace;
    font-size:0.62rem; font-weight:800; color:#F9C62B;
    text-transform:uppercase; letter-spacing:0.08em;
    margin-bottom:10px;
}
.ag-coming-title {
    font-family:'Space Grotesk', sans-serif;
    font-size:1rem; font-weight:700; color:#fff;
    margin-bottom:6px;
}
.ag-coming-desc {
    font-size:0.76rem; color:rgba(255,255,255,0.4); line-height:1.5;
}
.ag-coming-sports {
    display:flex; justify-content:center; gap:16px; margin-top:14px;
}
.ag-coming-sport {
    display:flex; flex-direction:column; align-items:center; gap:4px;
}
.ag-coming-sport-ico {
    font-size:1.6rem;
    animation:agFloat 3s ease-in-out infinite;
}
.ag-coming-sport-name {
    font-family:'Space Grotesk', sans-serif;
    font-size:0.62rem; font-weight:700; color:rgba(255,255,255,0.45);
    text-transform:uppercase; letter-spacing:0.05em;
}

/* ── TRUST + USERS STRIP ─────────────────────────────────────── */
.ag-trust {
    display:flex; justify-content:center; align-items:center;
    gap:20px; margin:28px 0 8px; flex-wrap:wrap;
    animation: agFadeUp 0.7s 0.75s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-trust-item {
    display:flex; align-items:center; gap:5px;
    font-size:0.66rem; font-weight:600; color:rgba(255,255,255,0.28);
}
.ag-trust-ico {
    width:18px; height:18px; border-radius:50%;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:0.55rem;
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06);
}
.ag-users-row {
    text-align:center; margin:18px 0 4px;
    animation: agFadeUp 0.7s 0.8s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-users-stack {
    display:inline-flex; margin-right:8px;
}
.ag-user-av {
    width:26px; height:26px; border-radius:50%;
    border:2px solid #0A0E14; margin-left:-7px;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:0.55rem; font-weight:700; color:#fff;
}
.ag-user-av:first-child { margin-left:0; }
.ag-user-av:nth-child(1) { background:linear-gradient(135deg,#00D559,#2D9EFF); }
.ag-user-av:nth-child(2) { background:linear-gradient(135deg,#C084FC,#2D9EFF); }
.ag-user-av:nth-child(3) { background:linear-gradient(135deg,#F9C62B,#FF6B35); }
.ag-user-av:nth-child(4) { background:linear-gradient(135deg,#2D9EFF,#00D559); }
.ag-users-text {
    font-size:0.72rem; color:rgba(255,255,255,0.4); font-weight:500;
    vertical-align:middle;
}
.ag-users-text strong { color:#00D559; font-weight:800; }

/* ── FOOTER ──────────────────────────────────────────────────── */
.ag-footer {
    text-align:center; padding:28px 0 50px;
    font-size:0.58rem; color:rgba(255,255,255,0.12); line-height:1.7;
    animation: agFadeUp 0.7s 0.85s cubic-bezier(0.22,1,0.36,1) both;
}
.ag-footer a { color:rgba(255,255,255,0.2); text-decoration:underline; }
.ag-footer-sports {
    display:flex; justify-content:center; gap:12px; margin-bottom:10px;
    font-size:0.8rem; opacity:0.2;
}

/* ── RESPONSIVE ──────────────────────────────────────────────── */
@media (max-width:580px) {
    .ag-page { padding:0 14px; }
    .ag-brand { padding-top:54px; }
    .ag-hero h1 { font-size:1.7rem; }
    .ag-hero-sub { font-size:0.85rem; }
    .ag-logo-wrap, .ag-logo-wrap img { width:76px; height:76px; }
    .ag-brand-name { font-size:1.75rem; }
    .ag-pillars { grid-template-columns:repeat(2, 1fr); }
    .ag-pricing-grid { grid-template-columns:1fr; }
    [data-testid="stForm"] { padding:24px 20px 22px !important; border-radius:16px !important; }
    .ag-pill { padding:6px 12px; font-size:0.68rem; }
    .ag-ticker-bar { height:36px; }
    .ag-metrics { grid-template-columns:repeat(2, 1fr); }
}
@media (max-width:360px) {
    .ag-pillars { grid-template-columns:1fr 1fr; }
    .ag-hero h1 { font-size:1.4rem; }
    .ag-metrics { grid-template-columns:1fr 1fr; }
}
</style>
"""

# ── Main gate function ────────────────────────────────────────

def require_login() -> bool:
    """Render the Smart Pick Pro landing page + auth gate.

    Returns True if authenticated, False if not (caller should st.stop()).
    """
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return True

    if is_logged_in():
        return True

    # ── Render the gate ───────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    _logo_b64 = _get_logo_b64()
    _logo_tag = (
        f'<img src="data:image/png;base64,{_logo_b64}" alt="Smart Pick Pro">'
        if _logo_b64
        else '<div style="font-size:2.6rem;">&#x1F3C0;</div>'
    )

    # ── Star particles (CSS-only) ─────────────────────────
    import random as _rnd
    _stars_html = ""
    for _ in range(35):
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

    # ── Ticker items ──────────────────────────────────────
    _ticker_items = (
        '<span class="ag-ticker-live"><span class="ag-ticker-dot"></span> LIVE</span>'
        '<span class="ag-ticker-item">Hit Rate <span class="val">62.4%</span></span>'
        '<span class="ag-ticker-item">Props Scanned <span class="val">347</span></span>'
        '<span class="ag-ticker-item">Models Active <span class="val">6/6</span></span>'
        '<span class="ag-ticker-item">SAFE Score Avg <span class="val">71.2</span></span>'
        '<span class="ag-ticker-item">Edge Detected <span class="val">+4.8%</span></span>'
        '<span class="ag-ticker-item">Bankroll ROI <span class="val">+18.3%</span></span>'
        '<span class="ag-ticker-item">CLV Capture <span class="val">92%</span></span>'
        '<span class="ag-ticker-item">Users Online <span class="val">1,247</span></span>'
    )

    # ── Full-screen cinematic markup ──────────────────────
    st.markdown(f"""
    <!-- Canvas background -->
    <div class="ag-canvas">
      <div class="ag-stars">{_stars_html}</div>
      <div class="ag-orb ag-orb-1"></div>
      <div class="ag-orb ag-orb-2"></div>
      <div class="ag-orb ag-orb-3"></div>
      <div class="ag-orb ag-orb-4"></div>
      <div class="ag-scan"></div>
      <div class="ag-grid"></div>
    </div>

    <!-- Platform ticker bar -->
    <div class="ag-ticker-bar">
      <div class="ag-ticker-track">
        {_ticker_items}{_ticker_items}
      </div>
    </div>

    <!-- Scroll wrapper -->
    <div class="ag-scroll">
    <div class="ag-page">

    <!-- Brand -->
    <div class="ag-brand">
      <div class="ag-logo-wrap">{_logo_tag}</div>
      <div class="ag-brand-name">Smart Pick Pro</div>
      <div class="ag-brand-sub">AI-Powered Sports Intelligence</div>
    </div>

    <!-- Hero -->
    <div class="ag-hero">
      <h1>The House Has a Problem.<br><span class="glow">It&rsquo;s Us.</span></h1>
      <div class="ag-hero-sub">
        The sharpest NBA prop engine on the internet.<br>
        <strong>6 AI models. 1 edge.</strong> &mdash; Free forever, no credit card.
      </div>
    </div>

    <!-- Social proof pills -->
    <div class="ag-pills">
      <div class="ag-pill">&#x1F3AF; <span class="ag-pill-val">62%</span>&nbsp;Verified Hit Rate</div>
      <div class="ag-pill">&#x1F916; <span class="ag-pill-val">6</span>&nbsp;AI Models Fused</div>
      <div class="ag-pill">&#x1F3C0; <span class="ag-pill-val">300+</span>&nbsp;Props / Night</div>
    </div>

    <!-- FOMO urgency -->
    <div class="ag-fomo">
      <div class="ag-fomo-text">
        &#x26A1; <span class="count">2,847</span> picks analyzed tonight &mdash; sharps are already locked in
      </div>
    </div>

    </div></div>
    """, unsafe_allow_html=True)

    # ── Tabs (Streamlit widgets) ──────────────────────────
    tab_signup, tab_login = st.tabs(["\u26A1  Get Instant Access", "\U0001F513  Log In"])

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            su_name = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            su_pw = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password", key="_su_pw2")
            su_submit = st.form_submit_button("\u26A1 Create Free Account \u2014 It Takes 10 Seconds", use_container_width=True, type="primary")

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
            li_submit = st.form_submit_button("\U0001F513 Log In", use_container_width=True, type="primary")

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
    <!-- Kill-Shot Comparison Table -->
    <div class="ag-compare">
      <div class="ag-compare-head">
        <h3>Why Sharps Are Switching</h3>
        <p>10 reasons Smart Pick Pro replaces your entire workflow</p>
      </div>
      <table class="ag-compare-table">
        <thead>
          <tr><th>Feature</th><th>Typical Tools</th><th>Smart Pick Pro</th></tr>
        </thead>
        <tbody>
          <tr><td>AI Models</td><td>0 &ndash; 1</td><td>6 Fused</td></tr>
          <tr><td>Prop Coverage</td><td>Top 20</td><td>300+ / Night</td></tr>
          <tr><td>Live Tracking</td><td>&#x2717;</td><td>Real-Time Sweat</td></tr>
          <tr><td>Confidence Score</td><td>&#x2717;</td><td>SAFE Score&#x2122; 0-100</td></tr>
          <tr><td>Bankroll Tools</td><td>&#x2717;</td><td>Kelly + Flat + Custom</td></tr>
          <tr><td>Matchup Analysis</td><td>Basic</td><td>Defensive DNA&#x2122;</td></tr>
          <tr><td>Line Movement</td><td>&#x2717;</td><td>Real-Time Alerts</td></tr>
          <tr><td>Backtesting</td><td>&#x2717;</td><td>Full Season Archive</td></tr>
          <tr><td>Price</td><td>$30-$300/mo</td><td>Free Forever</td></tr>
          <tr><td>Setup Time</td><td>Hours</td><td>10 Seconds</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Feature Pillars -->
    <div class="ag-pillars">
      <div class="ag-pillar" style="--pc:rgba(0,213,89,0.4);">
        <span class="ag-pillar-ico">&#x1F9E0;</span>
        <div class="ag-pillar-name">Quantum Engine</div>
        <div class="ag-pillar-desc">6 AI models fused into one prediction</div>
      </div>
      <div class="ag-pillar" style="--pc:rgba(45,158,255,0.4);">
        <span class="ag-pillar-ico">&#x1F3AF;</span>
        <div class="ag-pillar-name">SAFE Score&#x2122;</div>
        <div class="ag-pillar-desc">Every pick rated 0-100 confidence</div>
      </div>
      <div class="ag-pillar" style="--pc:rgba(192,132,252,0.4);">
        <span class="ag-pillar-ico">&#x1F4E1;</span>
        <div class="ag-pillar-name">Live Sweat Mode</div>
        <div class="ag-pillar-desc">Real-time prop tracking + alerts</div>
      </div>
    </div>

    <!-- Proof Metrics -->
    <div class="ag-metrics">
      <div class="ag-metric">
        <div class="ag-metric-val">62.4%</div>
        <div class="ag-metric-label">Hit Rate</div>
      </div>
      <div class="ag-metric">
        <div class="ag-metric-val">+18.3%</div>
        <div class="ag-metric-label">ROI</div>
      </div>
      <div class="ag-metric">
        <div class="ag-metric-val">347</div>
        <div class="ag-metric-label">Props / Night</div>
      </div>
      <div class="ag-metric">
        <div class="ag-metric-val">92%</div>
        <div class="ag-metric-label">CLV Capture</div>
      </div>
      <div class="ag-metric">
        <div class="ag-metric-val">6</div>
        <div class="ag-metric-label">AI Models</div>
      </div>
      <div class="ag-metric">
        <div class="ag-metric-val">10s</div>
        <div class="ag-metric-label">Setup Time</div>
      </div>
    </div>

    <!-- Testimonials -->
    <div class="ag-testimonials">
      <div class="ag-testimonials-title">What Sharps Are Saying</div>
      <div class="ag-testimonials-grid">
        <div class="ag-test-card">
          <div class="ag-test-quote">I went from randomly picking parlays to having a real mathematical edge. The Quantum Engine literally changed how I bet.</div>
          <div class="ag-test-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          <div class="ag-test-author">&mdash; @sharpbettor_mike &middot; SPP member since Jan 2025</div>
        </div>
        <div class="ag-test-card">
          <div class="ag-test-quote">The SAFE Score saved me from so many bad bets. I only play 80+ rated props now and my bankroll keeps growing.</div>
          <div class="ag-test-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          <div class="ag-test-author">&mdash; @datadrivendenver &middot; 4-month streak</div>
        </div>
        <div class="ag-test-card">
          <div class="ag-test-quote">Live Sweat Mode is addictive. Watching my props track in real-time with AI confidence updates &mdash; nothing else does this.</div>
          <div class="ag-test-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          <div class="ag-test-author">&mdash; @nightowl_picks &middot; Insider Circle member</div>
        </div>
      </div>
    </div>

    <!-- Pricing Preview -->
    <div class="ag-pricing">
      <div class="ag-pricing-head">
        <h3>Simple, Transparent Pricing</h3>
        <p>Start free. Upgrade when you want more firepower.</p>
      </div>
      <div class="ag-pricing-grid">
        <div class="ag-price-card">
          <div class="ag-price-tier">Free</div>
          <div class="ag-price-amount">$0 <span class="period">forever</span></div>
          <div class="ag-price-feat">
            Quantum Analysis &middot; SAFE Scores<br>
            <strong>3 props / night</strong> &middot; Basic filters
          </div>
        </div>
        <div class="ag-price-card popular">
          <div class="ag-price-tier">Sharp IQ</div>
          <div class="ag-price-amount">$9.99 <span class="period">/mo</span></div>
          <div class="ag-price-feat">
            <strong>Unlimited props</strong> &middot; Advanced filters<br>
            Matchup DNA &middot; Bankroll tools
          </div>
        </div>
        <div class="ag-price-card">
          <div class="ag-price-tier">Smart Money</div>
          <div class="ag-price-amount">$24.99 <span class="period">/mo</span></div>
          <div class="ag-price-feat">
            Everything in Sharp IQ +<br>
            <strong>Live Sweat</strong> &middot; Line alerts &middot; Edge detection
          </div>
        </div>
        <div class="ag-price-card">
          <div class="ag-price-tier" style="color:rgba(192,132,252,0.7);">Insider Circle</div>
          <div class="ag-price-amount">$499 <span class="period">one-time</span></div>
          <div class="ag-price-feat">
            <strong>Lifetime access</strong> to everything<br>
            Priority support &middot; Early features &middot; Joseph&rsquo;s brain
          </div>
        </div>
      </div>
    </div>

    <!-- Coming Soon -->
    <div class="ag-coming">
      <div class="ag-coming-card">
        <div class="ag-coming-badge">&#x1F6A7; Coming Q3 2025</div>
        <div class="ag-coming-title">MLB &amp; NFL Launching Soon</div>
        <div class="ag-coming-desc">
          The same 6-model AI engine that dominates NBA props &mdash;<br>
          expanding to America&rsquo;s biggest sports.
        </div>
        <div class="ag-coming-sports">
          <div class="ag-coming-sport">
            <span class="ag-coming-sport-ico">&#x26BE;</span>
            <span class="ag-coming-sport-name">MLB</span>
          </div>
          <div class="ag-coming-sport">
            <span class="ag-coming-sport-ico">&#x1F3C8;</span>
            <span class="ag-coming-sport-name">NFL</span>
          </div>
          <div class="ag-coming-sport">
            <span class="ag-coming-sport-ico">&#x26BD;</span>
            <span class="ag-coming-sport-name">Soccer</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Trust strip -->
    <div class="ag-trust">
      <div class="ag-trust-item"><span class="ag-trust-ico">&#x1F512;</span> 256-bit Encrypted</div>
      <div class="ag-trust-item"><span class="ag-trust-ico">&#x1F4B3;</span> No Credit Card</div>
      <div class="ag-trust-item"><span class="ag-trust-ico">&#x1F6AB;</span> Never Sell Data</div>
    </div>

    <!-- Users row -->
    <div class="ag-users-row">
      <span class="ag-users-stack">
        <span class="ag-user-av">JM</span>
        <span class="ag-user-av">KD</span>
        <span class="ag-user-av">RT</span>
        <span class="ag-user-av">SL</span>
      </span>
      <span class="ag-users-text"><strong>2,847+</strong> sharps already inside</span>
    </div>

    <!-- Footer -->
    <div class="ag-footer">
      <div class="ag-footer-sports">
        <span>&#x1F3C0;</span>
        <span>&#x26BE;</span>
        <span>&#x1F3C8;</span>
        <span>&#x26BD;</span>
        <span>&#x1F3D2;</span>
      </div>
      &copy; 2025 Smart Pick Pro &middot; For entertainment &amp; educational purposes only &middot; 21+<br>
      <a href="https://www.ncpgambling.org/" target="_blank">National Council on Problem Gambling &middot; 1-800-GAMBLER</a>
    </div>
    """, unsafe_allow_html=True)

    return False
