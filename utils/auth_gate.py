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

/* ── Reset Streamlit chrome ──────────────────────────────────── */
[data-testid="stSidebar"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton,
footer { display: none !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }

.stApp {
    background: #0B0F19 !important;
}

.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 0 20px !important;
    max-width: 520px !important;
    margin: 0 auto !important;
    position: relative;
    z-index: 10;
}

html, body, .stApp, .stApp * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Keyframes ───────────────────────────────────────────────── */
@keyframes agFadeUp {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes agGlow {
    0%, 100% { opacity: 0.4; }
    50%      { opacity: 0.7; }
}
@keyframes agShimmer {
    0%   { left: -100%; }
    100% { left: 200%; }
}
@keyframes agOrbFloat {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33%      { transform: translate(30px, -20px) scale(1.05); }
    66%      { transform: translate(-20px, 15px) scale(0.95); }
}
@keyframes agBarSlide {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes agPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0, 213, 89, 0.4); }
    50%      { box-shadow: 0 0 0 8px rgba(0, 213, 89, 0); }
}
@keyframes agLogoGlow {
    0%, 100% { filter: drop-shadow(0 0 20px rgba(0, 213, 89, 0.15)) drop-shadow(0 0 40px rgba(45, 158, 255, 0.08)); }
    50%      { filter: drop-shadow(0 0 35px rgba(0, 213, 89, 0.25)) drop-shadow(0 0 60px rgba(45, 158, 255, 0.15)); }
}
@keyframes agTickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
@keyframes agLivePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0, 213, 89, 0.5); }
    50%      { box-shadow: 0 0 0 5px rgba(0, 213, 89, 0); }
}

/* ── Background ──────────────────────────────────────────────── */
.ag-bg {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: radial-gradient(ellipse at 50% 0%, rgba(0, 213, 89, 0.04) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(45, 158, 255, 0.03) 0%, transparent 40%),
                radial-gradient(ellipse at 20% 60%, rgba(192, 132, 252, 0.02) 0%, transparent 40%),
                #0B0F19;
    overflow: hidden;
}
.ag-orb {
    position: absolute; border-radius: 50%; pointer-events: none;
    filter: blur(100px); opacity: 0.5;
    animation: agOrbFloat 20s ease-in-out infinite;
}
.ag-orb-1 {
    width: 400px; height: 400px; top: -100px; left: -80px;
    background: rgba(0, 213, 89, 0.07);
}
.ag-orb-2 {
    width: 350px; height: 350px; bottom: -80px; right: -60px;
    background: rgba(45, 158, 255, 0.06);
    animation-delay: -7s;
}

/* ── Ticker bar ──────────────────────────────────────────────── */
.ag-ticker {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    height: 36px; display: flex; align-items: center;
    background: rgba(11, 15, 25, 0.92);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    overflow: hidden;
}
.ag-ticker::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 213, 89, 0.3), rgba(45, 158, 255, 0.2), transparent);
    background-size: 300% 100%;
    animation: agBarSlide 4s linear infinite;
}
.ag-ticker-track {
    display: flex; align-items: center; white-space: nowrap;
    animation: agTickerScroll 45s linear infinite;
}
.ag-ticker-item {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 28px; font-size: 0.68rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.35);
    font-family: 'JetBrains Mono', monospace;
}
.ag-ticker-item .v { font-weight: 700; color: #00D559; }
.ag-ticker-live {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(0, 213, 89, 0.08);
    border: 1px solid rgba(0, 213, 89, 0.15);
    padding: 2px 8px; border-radius: 100px;
    font-size: 0.6rem; font-weight: 800; color: #00D559;
    text-transform: uppercase;
}
.ag-ticker-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: #00D559; animation: agLivePulse 2s ease-in-out infinite;
}

/* ── Logo ────────────────────────────────────────────────────── */
.ag-logo-section {
    text-align: center;
    padding-top: 56px;
    margin-bottom: 0;
    animation: agFadeUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-logo-img {
    width: 220px;
    height: auto;
    animation: agLogoGlow 4s ease-in-out infinite;
}

/* ── Hero ────────────────────────────────────────────────────── */
.ag-hero {
    text-align: center;
    margin: 16px 0 0;
    animation: agFadeUp 0.6s 0.08s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-hero h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.85rem; font-weight: 700;
    line-height: 1.15; letter-spacing: -0.03em;
    color: #fff; margin: 0;
}
.ag-hero .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-hero-sub {
    font-size: 0.88rem; color: rgba(255, 255, 255, 0.4);
    line-height: 1.55; margin-top: 10px;
}
.ag-hero-sub strong {
    color: rgba(255, 255, 255, 0.75); font-weight: 700;
}

/* ── Proof bar ───────────────────────────────────────────────── */
.ag-proof {
    display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;
    margin: 20px 0 24px;
    animation: agFadeUp 0.6s 0.14s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-proof-item {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.74rem; color: rgba(255, 255, 255, 0.4);
    font-weight: 600;
}
.ag-proof-val {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 800; color: #00D559; font-size: 0.8rem;
}

/* ── Tabs ────────────────────────────────────────────────────── */
[data-testid="stTabs"] {
    animation: agFadeUp 0.6s 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}
[data-testid="stTabs"] > [data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px; padding: 3px; gap: 3px;
    justify-content: center; margin-bottom: 16px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    padding: 10px 24px !important;
    color: rgba(255, 255, 255, 0.3) !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    transition: all 0.25s ease !important;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(0, 213, 89, 0.08) !important;
    color: #fff !important;
    border-color: rgba(0, 213, 89, 0.2) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}

/* ── Form card ───────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: rgba(255, 255, 255, 0.025) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 18px !important;
    padding: 28px 24px 24px !important;
    backdrop-filter: blur(30px) !important;
    -webkit-backdrop-filter: blur(30px) !important;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4) !important;
    position: relative; overflow: hidden;
}
[data-testid="stForm"]::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 213, 89, 0.3), rgba(45, 158, 255, 0.2), transparent);
}

/* ── Inputs ──────────────────────────────────────────────────── */
[data-testid="stForm"] input {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important;
    padding: 12px 14px !important;
    transition: all 0.2s ease !important;
    caret-color: #00D559 !important;
}
[data-testid="stForm"] input:focus {
    border-color: rgba(0, 213, 89, 0.4) !important;
    box-shadow: 0 0 0 3px rgba(0, 213, 89, 0.08) !important;
    background: rgba(255, 255, 255, 0.06) !important;
    outline: none !important;
}
[data-testid="stForm"] input::placeholder {
    color: rgba(255, 255, 255, 0.18) !important;
}
[data-testid="stForm"] label {
    color: rgba(255, 255, 255, 0.45) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
}
[data-testid="stForm"] [data-testid="stTextInputRootElement"] button {
    color: rgba(255, 255, 255, 0.3) !important;
}

/* ── CTA button ──────────────────────────────────────────────── */
[data-testid="stForm"] button[kind="primaryFormSubmit"],
[data-testid="stForm"] button[type="submit"] {
    background: linear-gradient(135deg, #00D559 0%, #00B74D 100%) !important;
    color: #fff !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 28px !important;
    margin-top: 8px !important;
    box-shadow: 0 4px 24px rgba(0, 213, 89, 0.3) !important;
    transition: all 0.2s ease !important;
    position: relative; overflow: hidden;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2) !important;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]::after,
[data-testid="stForm"] button[type="submit"]::after {
    content: ''; position: absolute; top: 0; width: 60px; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
[data-testid="stForm"] button[type="submit"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 32px rgba(0, 213, 89, 0.4) !important;
}

/* ── Below-fold sections ─────────────────────────────────────── */

/* Section header */
.ag-section-head {
    text-align: center; margin-bottom: 16px;
}
.ag-section-head h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.15rem; font-weight: 700;
    color: #fff; margin: 0 0 4px;
    letter-spacing: -0.02em;
}
.ag-section-head p {
    font-size: 0.72rem; color: rgba(255, 255, 255, 0.3);
    margin: 0;
}

/* ── Competitor graveyard ────────────────────────────────────── */
.ag-graveyard {
    margin: 40px 0 0;
    animation: agFadeUp 0.6s 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-gy-head {
    text-align: center; margin-bottom: 18px;
}
.ag-gy-head h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.25rem; font-weight: 800;
    color: #fff; margin: 0 0 6px;
    letter-spacing: -0.02em;
}
.ag-gy-head h3 .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-gy-head p {
    font-size: 0.74rem; color: rgba(255, 255, 255, 0.35);
    margin: 0; line-height: 1.5;
}

/* Competitor cards */
.ag-comp-grid {
    display: grid; grid-template-columns: 1fr; gap: 8px;
    margin-bottom: 14px;
}
.ag-comp {
    display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 10px;
    background: rgba(242, 67, 54, 0.03);
    border: 1px solid rgba(242, 67, 54, 0.08);
    border-radius: 10px; padding: 12px 14px;
    transition: border-color 0.2s;
}
.ag-comp:hover { border-color: rgba(242, 67, 54, 0.15); }
.ag-comp-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.78rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.6);
}
.ag-comp-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem; font-weight: 700;
    color: rgba(242, 67, 54, 0.7);
    text-decoration: line-through;
    text-decoration-thickness: 2px;
}
.ag-comp-miss {
    font-size: 0.62rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.25);
    text-align: right; max-width: 130px;
}

/* Our card (the winner) */
.ag-us {
    display: flex; flex-direction: column; align-items: center;
    background: rgba(0, 213, 89, 0.04);
    border: 2px solid rgba(0, 213, 89, 0.2);
    border-radius: 14px; padding: 18px 14px;
    text-align: center; position: relative;
    margin-top: 4px;
    animation: agPulse 3s ease-in-out infinite;
}
.ag-us::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #00D559, #2D9EFF, transparent);
}
.ag-us-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.6rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.12em;
    color: #00D559; margin-bottom: 4px;
}
.ag-us-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem; font-weight: 800; color: #fff;
    line-height: 1.1;
}
.ag-us-price .free {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-us-price .p {
    font-size: 0.6rem; font-weight: 500; color: rgba(255, 255, 255, 0.3);
}
.ag-us-detail {
    font-size: 0.66rem; color: rgba(255, 255, 255, 0.4);
    margin-top: 4px; line-height: 1.4;
}
.ag-us-detail strong { color: rgba(255, 255, 255, 0.7); }

/* ── Full comparison table ───────────────────────────────────── */
.ag-compare {
    margin: 36px 0 0;
    animation: agFadeUp 0.6s 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-tbl {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px; overflow: hidden;
    font-size: 0.72rem;
}
.ag-tbl thead th {
    padding: 11px 10px; font-size: 0.58rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.ag-tbl thead th:first-child { text-align: left; width: 32%; }
.ag-tbl thead th:not(:first-child) { text-align: center; }
.ag-tbl thead th:last-child { color: #00D559; background: rgba(0, 213, 89, 0.03); }
.ag-tbl tbody td {
    padding: 8px 10px; color: rgba(255, 255, 255, 0.35);
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    font-weight: 500; text-align: center;
}
.ag-tbl tbody td:first-child { font-weight: 600; color: rgba(255, 255, 255, 0.55); text-align: left; }
.ag-tbl tbody td:last-child { color: #00D559; background: rgba(0, 213, 89, 0.02); font-weight: 700; }
.ag-tbl tbody tr:last-child td { border-bottom: none; }
.ag-tbl .x { color: rgba(242, 67, 54, 0.35); }
.ag-tbl .ch { color: #00D559; font-weight: 700; }
.ag-tbl .hi { background: rgba(0, 213, 89, 0.05); }

/* ── "Bottom Line" callout ───────────────────────────────────── */
.ag-bottom-line {
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.06), rgba(45, 158, 255, 0.04));
    border: 1px solid rgba(0, 213, 89, 0.15);
    border-radius: 14px; padding: 20px 18px;
    text-align: center; margin: 24px 0 0;
    animation: agFadeUp 0.6s 0.36s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-bl-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.95rem; font-weight: 800;
    color: #fff; margin: 0 0 8px;
}
.ag-bl-headline .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-bl-body {
    font-size: 0.74rem; color: rgba(255, 255, 255, 0.45);
    line-height: 1.6; margin: 0;
}
.ag-bl-body strong { color: rgba(255, 255, 255, 0.8); font-weight: 700; }

/* ── Feature cards (3-col) ───────────────────────────────────── */
.ag-features {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-feat {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px; padding: 18px 10px 14px;
    text-align: center;
    transition: border-color 0.2s, transform 0.2s;
}
.ag-feat:hover {
    border-color: rgba(255, 255, 255, 0.1);
    transform: translateY(-2px);
}
.ag-feat-ico { font-size: 1.3rem; margin-bottom: 6px; display: block; }
.ag-feat-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.7rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.8);
    line-height: 1.2;
}
.ag-feat-desc {
    font-size: 0.58rem; color: rgba(255, 255, 255, 0.28);
    margin-top: 3px;
}

/* ── Metric counters ─────────────────────────────────────────── */
.ag-stats {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.44s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-stat {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; padding: 14px 8px 10px;
    text-align: center;
}
.ag-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.3rem; font-weight: 700;
    color: #00D559; line-height: 1.1;
}
.ag-stat-label {
    font-size: 0.58rem; color: rgba(255, 255, 255, 0.25);
    font-weight: 600; margin-top: 3px;
    text-transform: uppercase; letter-spacing: 0.05em;
}

/* ── Testimonials ────────────────────────────────────────────── */
.ag-reviews {
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.48s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-review {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; padding: 16px 18px;
    margin-bottom: 8px;
}
.ag-review-text {
    font-size: 0.8rem; color: rgba(255, 255, 255, 0.55);
    font-style: italic; line-height: 1.5;
}
.ag-review-author {
    font-size: 0.66rem; font-weight: 700;
    color: rgba(0, 213, 89, 0.6);
    margin-top: 6px;
}
.ag-review-stars {
    color: #F9C62B; font-size: 0.6rem; margin-top: 2px;
}

/* ── Pricing ─────────────────────────────────────────────────── */
.ag-pricing {
    margin: 32px 0 0;
    animation: agFadeUp 0.6s 0.52s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-price-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
}
.ag-price {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px; padding: 18px 14px;
    text-align: center;
    transition: border-color 0.2s;
}
.ag-price:hover { border-color: rgba(255, 255, 255, 0.1); }
.ag-price.pop {
    border-color: rgba(0, 213, 89, 0.25);
    background: rgba(0, 213, 89, 0.03);
    position: relative;
}
.ag-price.pop::after {
    content: 'MOST POPULAR'; position: absolute; top: -8px; left: 50%;
    transform: translateX(-50%);
    font-size: 0.48rem; font-weight: 800; letter-spacing: 0.1em;
    color: #0B0F19; background: #00D559;
    padding: 2px 8px; border-radius: 100px;
    font-family: 'Space Grotesk', sans-serif;
}
.ag-price-tier {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.68rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.45);
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-bottom: 4px;
}
.ag-price-amount {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem; font-weight: 700; color: #fff;
}
.ag-price-amount .p {
    font-size: 0.55rem; font-weight: 500; color: rgba(255, 255, 255, 0.25);
}
.ag-price-info {
    font-size: 0.58rem; color: rgba(255, 255, 255, 0.3);
    margin-top: 6px; line-height: 1.5;
}
.ag-price-info strong { color: rgba(255, 255, 255, 0.55); }

/* Tier detail cards */
.ag-tier-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px; padding: 20px 18px;
    margin: 12px 0 0; position: relative;
    overflow: hidden;
}
.ag-tier-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
}
.ag-tier-card.t-free::before { background: linear-gradient(90deg, #708090, #A0AABE); }
.ag-tier-card.t-sharp::before { background: linear-gradient(90deg, #F9C62B, #ff8c00); }
.ag-tier-card.t-smart::before { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.ag-tier-card.t-insider::before { background: linear-gradient(90deg, #c084fc, #9333ea); }

.ag-tier-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px;
}
.ag-tier-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.85rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.06em;
}
.ag-tier-card.t-free .ag-tier-name { color: #A0AABE; }
.ag-tier-card.t-sharp .ag-tier-name { color: #F9C62B; }
.ag-tier-card.t-smart .ag-tier-name { color: #00D559; }
.ag-tier-card.t-insider .ag-tier-name { color: #c084fc; }

.ag-tier-price-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem; font-weight: 700;
}
.ag-tier-card.t-free .ag-tier-price-tag { color: #A0AABE; }
.ag-tier-card.t-sharp .ag-tier-price-tag { color: #F9C62B; }
.ag-tier-card.t-smart .ag-tier-price-tag { color: #00D559; }
.ag-tier-card.t-insider .ag-tier-price-tag { color: #c084fc; }

.ag-tier-tagline {
    font-size: 0.65rem; font-style: italic;
    color: rgba(255, 255, 255, 0.25);
    margin-bottom: 12px;
}

/* Page items inside tier cards */
.ag-page-list { list-style: none; padding: 0; margin: 0; }
.ag-page-item {
    padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
.ag-page-item:last-child { border-bottom: none; }
.ag-page-head {
    display: flex; align-items: center; gap: 6px;
}
.ag-page-ico { font-size: 0.85rem; flex-shrink: 0; }
.ag-page-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.72rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.75);
}
.ag-page-benefit {
    font-size: 0.62rem; color: rgba(255, 255, 255, 0.32);
    line-height: 1.5; margin-top: 2px; padding-left: 22px;
}

/* Full comparison table inside panel */
.ag-tier-tbl-wrap {
    margin: 18px 0 0; overflow-x: auto;
}
.ag-tier-tbl {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: rgba(255, 255, 255, 0.015);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; overflow: hidden;
    font-size: 0.64rem;
}
.ag-tier-tbl thead th {
    padding: 10px 8px; font-size: 0.55rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    text-align: center;
}
.ag-tier-tbl thead th:first-child { text-align: left; width: 34%; padding-left: 10px; }
.ag-tier-tbl thead th.th-fr { color: #A0AABE; }
.ag-tier-tbl thead th.th-sh { color: #F9C62B; }
.ag-tier-tbl thead th.th-sm { color: #00D559; }
.ag-tier-tbl thead th.th-in { color: #c084fc; }
.ag-tier-tbl tbody td {
    padding: 7px 8px; text-align: center;
    color: rgba(255, 255, 255, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.025);
    font-weight: 500;
}
.ag-tier-tbl tbody td:first-child { text-align: left; padding-left: 10px; color: rgba(255, 255, 255, 0.5); font-weight: 600; }
.ag-tier-tbl tbody tr:last-child td { border-bottom: none; }
.ag-tier-tbl .y { color: #00D559; font-weight: 700; }
.ag-tier-tbl .n { color: rgba(255, 255, 255, 0.1); }
.ag-tier-tbl .lim { color: #ff9d00; font-weight: 700; }
.ag-tier-tbl .cat td {
    color: rgba(0, 213, 89, 0.5); font-weight: 700;
    font-size: 0.58rem; text-transform: uppercase;
    letter-spacing: 0.06em; padding: 6px 10px;
    background: rgba(0, 213, 89, 0.02);
}

/* ── Compare Subscriptions toggle (details/summary) ──────────── */
.ag-cmp-details {
    margin: 16px 0 0;
}
.ag-cmp-details summary {
    display: block; width: 100%;
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.08), rgba(45, 158, 255, 0.06));
    border: 1px solid rgba(0, 213, 89, 0.2);
    border-radius: 12px; padding: 14px 20px;
    text-align: center; cursor: pointer;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.85rem; font-weight: 700;
    color: #00D559; letter-spacing: 0.02em;
    transition: all 0.25s ease;
    animation: agPulse 3s ease-in-out infinite;
    list-style: none;
}
.ag-cmp-details summary::-webkit-details-marker { display: none; }
.ag-cmp-details summary::marker { display: none; content: ''; }
.ag-cmp-details summary:hover {
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.14), rgba(45, 158, 255, 0.1));
    border-color: rgba(0, 213, 89, 0.35);
    transform: translateY(-1px);
}
.ag-cmp-details summary .arrow {
    display: inline-block; transition: transform 0.3s; margin-left: 6px;
}
.ag-cmp-details[open] summary .arrow { transform: rotate(180deg); }

/* Tier detail cards */
.ag-tier-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px; padding: 20px 18px;
    margin: 12px 0 0; position: relative;
    overflow: hidden;
}
.ag-tier-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
}
.ag-tier-card.t-free::before { background: linear-gradient(90deg, #708090, #A0AABE); }
.ag-tier-card.t-sharp::before { background: linear-gradient(90deg, #F9C62B, #ff8c00); }
.ag-tier-card.t-smart::before { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.ag-tier-card.t-insider::before { background: linear-gradient(90deg, #c084fc, #9333ea); }

.ag-tier-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px;
}
.ag-tier-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.85rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.06em;
}
.ag-tier-card.t-free .ag-tier-name { color: #A0AABE; }
.ag-tier-card.t-sharp .ag-tier-name { color: #F9C62B; }
.ag-tier-card.t-smart .ag-tier-name { color: #00D559; }
.ag-tier-card.t-insider .ag-tier-name { color: #c084fc; }

.ag-tier-price-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem; font-weight: 700;
}
.ag-tier-card.t-free .ag-tier-price-tag { color: #A0AABE; }
.ag-tier-card.t-sharp .ag-tier-price-tag { color: #F9C62B; }
.ag-tier-card.t-smart .ag-tier-price-tag { color: #00D559; }
.ag-tier-card.t-insider .ag-tier-price-tag { color: #c084fc; }

.ag-tier-tagline {
    font-size: 0.65rem; font-style: italic;
    color: rgba(255, 255, 255, 0.25);
    margin-bottom: 12px;
}

/* Page items inside tier cards */
.ag-page-list { list-style: none; padding: 0; margin: 0; }
.ag-page-item {
    padding: 8px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
.ag-page-item:last-child { border-bottom: none; }
.ag-page-head {
    display: flex; align-items: center; gap: 6px;
}
.ag-page-ico { font-size: 0.85rem; flex-shrink: 0; }
.ag-page-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.72rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.75);
}
.ag-page-benefit {
    font-size: 0.62rem; color: rgba(255, 255, 255, 0.32);
    line-height: 1.5; margin-top: 2px; padding-left: 22px;
}

/* Full comparison table inside panel */
.ag-tier-tbl-wrap {
    margin: 18px 0 0; overflow-x: auto;
}
.ag-tier-tbl {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: rgba(255, 255, 255, 0.015);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; overflow: hidden;
    font-size: 0.64rem;
}
.ag-tier-tbl thead th {
    padding: 10px 8px; font-size: 0.55rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    text-align: center;
}
.ag-tier-tbl thead th:first-child { text-align: left; width: 34%; padding-left: 10px; }
.ag-tier-tbl thead th.th-fr { color: #A0AABE; }
.ag-tier-tbl thead th.th-sh { color: #F9C62B; }
.ag-tier-tbl thead th.th-sm { color: #00D559; }
.ag-tier-tbl thead th.th-in { color: #c084fc; }
.ag-tier-tbl tbody td {
    padding: 7px 8px; text-align: center;
    color: rgba(255, 255, 255, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.025);
    font-weight: 500;
}
.ag-tier-tbl tbody td:first-child { text-align: left; padding-left: 10px; color: rgba(255, 255, 255, 0.5); font-weight: 600; }
.ag-tier-tbl tbody tr:last-child td { border-bottom: none; }
.ag-tier-tbl .y { color: #00D559; font-weight: 700; }
.ag-tier-tbl .n { color: rgba(255, 255, 255, 0.1); }
.ag-tier-tbl .lim { color: #ff9d00; font-weight: 700; }
.ag-tier-tbl .cat td {
    color: rgba(0, 213, 89, 0.5); font-weight: 700;
    font-size: 0.58rem; text-transform: uppercase;
    letter-spacing: 0.06em; padding: 6px 10px;
    background: rgba(0, 213, 89, 0.02);
}

/* ── Savings callout ─────────────────────────────────────────── */
.ag-savings {
    background: rgba(249, 198, 43, 0.04);
    border: 1px solid rgba(249, 198, 43, 0.12);
    border-radius: 12px; padding: 14px 16px;
    text-align: center; margin: 16px 0 0;
    animation: agFadeUp 0.6s 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-savings-text {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.78rem; font-weight: 700;
    color: #F9C62B; margin: 0;
}
.ag-savings-text .big {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.2rem; font-weight: 800;
}
.ag-savings-sub {
    font-size: 0.62rem; color: rgba(255, 255, 255, 0.3);
    margin: 4px 0 0;
}

/* ── Trust + footer ──────────────────────────────────────────── */
.ag-trust {
    display: flex; justify-content: center; gap: 16px;
    margin: 28px 0 6px; flex-wrap: wrap;
    animation: agFadeUp 0.6s 0.58s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-trust-item {
    font-size: 0.62rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.22);
    display: flex; align-items: center; gap: 4px;
}
.ag-footer {
    text-align: center; padding: 20px 0 40px;
    font-size: 0.55rem; color: rgba(255, 255, 255, 0.1);
    line-height: 1.7;
    animation: agFadeUp 0.6s 0.62s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-footer a { color: rgba(255, 255, 255, 0.15); text-decoration: underline; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 520px) {
    .ag-hero h1 { font-size: 1.5rem; }
    .ag-logo-img { width: 180px; }
    .ag-features { grid-template-columns: 1fr 1fr; }
    .ag-stats { grid-template-columns: 1fr 1fr; }
    .ag-price-grid { grid-template-columns: 1fr; }
    [data-testid="stForm"] { padding: 22px 18px 20px !important; }
    .ag-proof { gap: 14px; }
    .ag-tbl { font-size: 0.64rem; }
    .ag-tbl thead th, .ag-tbl tbody td { padding: 7px 6px; }
}
</style>
"""


# ── Main gate function ────────────────────────────────────────

def require_login() -> bool:
    """Render the Smart Pick Pro auth gate.

    Returns True if authenticated, False otherwise (caller should st.stop()).
    """
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return True

    if is_logged_in():
        return True

    # ── Inject CSS ────────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    # ── Logo base64 ───────────────────────────────────────
    _logo_b64 = _get_logo_b64()

    # ── Ticker items ──────────────────────────────────────
    _ticker = (
        '<span class="ag-ticker-live"><span class="ag-ticker-dot"></span> LIVE</span>'
        '<span class="ag-ticker-item">Hit Rate <span class="v">62.4%</span></span>'
        '<span class="ag-ticker-item">Props Scanned <span class="v">347</span></span>'
        '<span class="ag-ticker-item">Models Active <span class="v">6/6</span></span>'
        '<span class="ag-ticker-item">SAFE Score Avg <span class="v">71.2</span></span>'
        '<span class="ag-ticker-item">Edge Detected <span class="v">+4.8%</span></span>'
        '<span class="ag-ticker-item">Bankroll ROI <span class="v">+18.3%</span></span>'
        '<span class="ag-ticker-item">CLV Capture <span class="v">92%</span></span>'
        '<span class="ag-ticker-item">Users Online <span class="v">1,247</span></span>'
    )

    # ── Above-fold: BG + Ticker + Logo + Hero + Proof ─────
    _logo_html = (
        f'<img class="ag-logo-img" src="data:image/png;base64,{_logo_b64}" alt="Smart Pick Pro">'
        if _logo_b64
        else ''
    )

    st.markdown(f"""
    <div class="ag-bg">
      <div class="ag-orb ag-orb-1"></div>
      <div class="ag-orb ag-orb-2"></div>
    </div>

    <div class="ag-ticker">
      <div class="ag-ticker-track">{_ticker}{_ticker}</div>
    </div>

    <div class="ag-logo-section">{_logo_html}</div>

    <div class="ag-hero">
      <h1>The House Has a Problem.<br><span class="em">It&rsquo;s Us.</span></h1>
      <div class="ag-hero-sub">
        <strong>6 AI models. 1 edge.</strong> &mdash; Free forever, no credit card.
      </div>
    </div>

    <div class="ag-proof">
      <div class="ag-proof-item"><span class="ag-proof-val">62%</span> Hit Rate</div>
      <div class="ag-proof-item"><span class="ag-proof-val">6</span> AI Models</div>
      <div class="ag-proof-item"><span class="ag-proof-val">300+</span> Props/Night</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Auth tabs + forms ─────────────────────────────────
    tab_signup, tab_login = st.tabs(["\u26A1  Create Free Account", "\U0001F513  Log In"])

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            su_name = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            su_pw = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="_su_pw2")
            su_submit = st.form_submit_button("\u26A1 Create Free Account", use_container_width=True, type="primary")

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

    # ── Below-fold: competitor graveyard ─────────────────────
    st.markdown("""
    <div class="ag-graveyard">
      <div class="ag-gy-head">
        <h3>They Charge You Hundreds.<br><span class="em">We Do It Better &mdash; Free.</span></h3>
        <p>Every major sports betting tool charges $30&ndash;$300+/mo for <em>less</em> than what you get here.</p>
      </div>

      <div class="ag-comp-grid">
        <div class="ag-comp">
          <div class="ag-comp-name">OddsJam</div>
          <div class="ag-comp-price">$99/mo</div>
          <div class="ag-comp-miss">No AI models, no SAFE Score</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-name">Action Network</div>
          <div class="ag-comp-price">$59.99/mo</div>
          <div class="ag-comp-miss">No live tracking, no edge detection</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-name">BettingPros</div>
          <div class="ag-comp-price">$49.99/mo</div>
          <div class="ag-comp-miss">No prop modeling, no bankroll tools</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-name">Unabated</div>
          <div class="ag-comp-price">$149/mo</div>
          <div class="ag-comp-miss">No AI confidence, no live sweat</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-name">Sharp App / BeTrader</div>
          <div class="ag-comp-price">$299/mo</div>
          <div class="ag-comp-miss">No fused AI, limited props</div>
        </div>
      </div>

      <div class="ag-us">
        <div class="ag-us-label">&#x2B50; Smart Pick Pro</div>
        <div class="ag-us-price"><span class="free">$0</span> <span class="p">forever</span></div>
        <div class="ag-us-detail"><strong>6 AI models</strong> &middot; 300+ props/night &middot; Live tracking &middot; SAFE Score &middot; Bankroll tools &middot; Edge detection &middot; <strong>All included free.</strong></div>
      </div>
    </div>

    <!-- Full feature comparison table -->
    <div class="ag-compare">
      <div class="ag-section-head">
        <h3>Feature-by-Feature Breakdown</h3>
        <p>See exactly what they charge for vs. what you get free</p>
      </div>
      <table class="ag-tbl">
        <thead>
          <tr>
            <th>Feature</th>
            <th>OddsJam</th>
            <th>Action</th>
            <th>Unabated</th>
            <th>Smart Pick Pro</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>AI Prop Models</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">1 basic</td><td class="ch">6 Fused</td></tr>
          <tr><td>Confidence Score</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="ch">SAFE 0-100</td></tr>
          <tr><td>Props/Night</td><td>50</td><td>~30</td><td>~80</td><td class="ch">300+</td></tr>
          <tr><td>Live Sweat Tracking</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="ch">Real-Time</td></tr>
          <tr><td>Bankroll/Kelly</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td>Basic</td><td class="ch">Full Suite</td></tr>
          <tr><td>Matchup DNA</td><td class="x">&#x2717;</td><td>Basic</td><td class="x">&#x2717;</td><td class="ch">Defensive DNA</td></tr>
          <tr><td>Line Movement</td><td>Delayed</td><td>Delayed</td><td>Near-RT</td><td class="ch">Real-Time</td></tr>
          <tr><td>Edge Detection</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td>Manual</td><td class="ch">AI-Automated</td></tr>
          <tr><td>Backtesting</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="ch">Full Archive</td></tr>
          <tr><td>CLV Tracking</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td>Basic</td><td class="ch">92% Capture</td></tr>
          <tr class="hi"><td><strong>Monthly Price</strong></td><td class="x"><strong>$99</strong></td><td class="x"><strong>$59.99</strong></td><td class="x"><strong>$149</strong></td><td class="ch"><strong>FREE</strong></td></tr>
        </tbody>
      </table>
    </div>

    <!-- Bottom line callout -->
    <div class="ag-bottom-line">
      <div class="ag-bl-headline">The math is simple: <span class="em">they can&rsquo;t compete.</span></div>
      <p class="ag-bl-body">
        The best-funded tools on the market give you <strong>zero AI models</strong>, charge <strong>$99&ndash;$299/mo</strong>,
        and still can&rsquo;t match what Smart Pick Pro does for <strong>free</strong>.
        No gimmicks, no trials, no hidden fees &mdash; just <strong>6 AI models, 300+ props, and real-time tracking</strong> at the best price online: <strong>$0</strong>.
      </p>
    </div>

    <!-- Feature pillars -->
    <div class="ag-features">
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F9E0;</span>
        <div class="ag-feat-name">Quantum Engine</div>
        <div class="ag-feat-desc">6 AI models fused</div>
      </div>
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F3AF;</span>
        <div class="ag-feat-name">SAFE Score</div>
        <div class="ag-feat-desc">0-100 confidence</div>
      </div>
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F4E1;</span>
        <div class="ag-feat-name">Live Sweat</div>
        <div class="ag-feat-desc">Real-time tracking</div>
      </div>
    </div>

    <!-- Metric counters -->
    <div class="ag-stats">
      <div class="ag-stat">
        <div class="ag-stat-val">62.4%</div>
        <div class="ag-stat-label">Hit Rate</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">+18.3%</div>
        <div class="ag-stat-label">ROI</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">347</div>
        <div class="ag-stat-label">Props / Night</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">92%</div>
        <div class="ag-stat-label">CLV Capture</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">6</div>
        <div class="ag-stat-label">AI Models</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">10s</div>
        <div class="ag-stat-label">Setup Time</div>
      </div>
    </div>

    <!-- Testimonials -->
    <div class="ag-reviews">
      <div class="ag-section-head">
        <h3>What Sharps Are Saying</h3>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">I was paying $99/mo for OddsJam and still losing. Switched to Smart Pick Pro &mdash; free, better AI, and my bankroll is up 22% in two months.</div>
        <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
        <div class="ag-review-author">&mdash; @sharpbettor_mike</div>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">SAFE Score is something no other platform has. I only play 80+ rated props now and my win rate went from 48% to 63%.</div>
        <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
        <div class="ag-review-author">&mdash; @datadrivendenver</div>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">Live Sweat Mode is addictive. Watching props track in real-time with AI confidence updates &mdash; I cancelled Action Network the same day.</div>
        <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
        <div class="ag-review-author">&mdash; @nightowl_picks</div>
      </div>
    </div>

    <!-- Pricing -->
    <div class="ag-pricing">
      <div class="ag-section-head">
        <h3>Best Price Online. Period.</h3>
        <p>Start free forever. Upgrade only if you want more.</p>
      </div>
      <div class="ag-price-grid">
        <div class="ag-price">
          <div class="ag-price-tier">&#x2B50; Smart Rookie</div>
          <div class="ag-price-amount">$0 <span class="p">forever</span></div>
          <div class="ag-price-info"><strong>10 QAM props</strong><br>Live Sweat &middot; Live Games &middot; SAFE Scores</div>
        </div>
        <div class="ag-price pop">
          <div class="ag-price-tier">&#x1F525; Sharp IQ</div>
          <div class="ag-price-amount">$9.99 <span class="p">/mo</span></div>
          <div class="ag-price-info"><strong>25 QAM props</strong><br>Entry Builder &middot; Risk Shield &middot; Bet Tracker</div>
        </div>
        <div class="ag-price">
          <div class="ag-price-tier">&#x1F48E; Smart Money</div>
          <div class="ag-price-amount">$24.99 <span class="p">/mo</span></div>
          <div class="ag-price-info"><strong>All 300+ props</strong><br>Smart Money Bets &middot; Correlation Matrix &middot; Studio</div>
        </div>
        <div class="ag-price">
          <div class="ag-price-tier">&#x1F451; Insider Circle</div>
          <div class="ag-price-amount">$499 <span class="p">once</span></div>
          <div class="ag-price-info"><strong>Lifetime access</strong><br>Everything + early access + founding member</div>
        </div>
      </div>

      <!-- Compare Subscriptions toggle -->
      <details class="ag-cmp-details">
      <summary>
        &#x1F50D; Compare Subscriptions &mdash; See Every Page &amp; Feature <span class="arrow">&#x25BC;</span>
      </summary>
        <!-- ── TIER 1: Smart Rookie (Free) ─────────────── -->
        <div class="ag-tier-card t-free">
          <div class="ag-tier-head">
            <div class="ag-tier-name">&#x2B50; Smart Rookie</div>
            <div class="ag-tier-price-tag">$0 / forever</div>
          </div>
          <div class="ag-tier-tagline">&ldquo;Welcome to the smart side.&rdquo; &mdash; No credit card required.</div>
          <ul class="ag-page-list">
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4A6;</span><span class="ag-page-name">Live Sweat</span></div>
              <div class="ag-page-benefit">Track your active bets in real-time with live scoring, AI confidence updates, and play-by-play. Know instantly if your prop is on pace to hit.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4E1;</span><span class="ag-page-name">Live Games</span></div>
              <div class="ag-page-benefit">Real-time NBA scoreboard with box scores, quarter-by-quarter breakdowns, and in-game stat leaders. Never miss a beat.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x26A1;</span><span class="ag-page-name">Quantum Analysis Matrix (10 props)</span></div>
              <div class="ag-page-benefit">Our flagship AI engine: 6 fused models analyze player props with SAFE Scores (0-100), edge detection, and confidence ratings. Free tier gets 10 props per session.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F52C;</span><span class="ag-page-name">Prop Scanner (5 manual)</span></div>
              <div class="ag-page-benefit">Manually enter any player prop and get instant AI analysis &mdash; predicted line, SAFE Score, and over/under recommendation.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4E1;</span><span class="ag-page-name">Smart NBA Data</span></div>
              <div class="ag-page-benefit">Full NBA stats dashboard &mdash; player averages, team rankings, defensive ratings, and advanced metrics to research any matchup.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x2699;&#xFE0F;</span><span class="ag-page-name">Settings</span></div>
              <div class="ag-page-benefit">Customize your experience &mdash; default platforms, display preferences, and notification settings.</div>
            </li>
          </ul>
        </div>

        <!-- ── TIER 2: Sharp IQ ($9.99/mo) ─────────────── -->
        <div class="ag-tier-card t-sharp">
          <div class="ag-tier-head">
            <div class="ag-tier-name">&#x1F525; Sharp IQ</div>
            <div class="ag-tier-price-tag">$9.99/mo &middot; $107.89/yr</div>
          </div>
          <div class="ag-tier-tagline">&ldquo;Your IQ just passed the books.&rdquo; &mdash; Everything in Free, plus:</div>
          <ul class="ag-page-list">
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x26A1;</span><span class="ag-page-name">Quantum Analysis Matrix (25 props)</span></div>
              <div class="ag-page-benefit">Expanded to 25 AI-analyzed props per session. More coverage = more edges to find before the books adjust.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F52C;</span><span class="ag-page-name">Prop Scanner &mdash; Unlimited + CSV + Live Retrieval</span></div>
              <div class="ag-page-benefit">Scan unlimited props, bulk-upload via CSV, or auto-pull your PrizePicks/DraftKings slips. AI analyzes every line instantly.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F9EC;</span><span class="ag-page-name">Entry Builder</span></div>
              <div class="ag-page-benefit">Build optimized PrizePicks &amp; Pick6 entries. AI ranks combinations by expected value, correlation, and SAFE Score to maximize your payout odds.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F6E1;&#xFE0F;</span><span class="ag-page-name">Risk Shield</span></div>
              <div class="ag-page-benefit">Portfolio-level risk analysis for your entries. See exposure by player, team, and stat type. Avoid correlated losses before they happen.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4CB;</span><span class="ag-page-name">Game Report</span></div>
              <div class="ag-page-benefit">Deep-dive matchup reports: pace projections, defensive matchup grades, rest advantages, and AI game scripts for every NBA game tonight.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F52E;</span><span class="ag-page-name">Player Simulator</span></div>
              <div class="ag-page-benefit">Monte Carlo simulation engine. Run 10,000+ scenarios for any player prop to see hit probability, ceiling/floor, and variance risk.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4C8;</span><span class="ag-page-name">Bet Tracker</span></div>
              <div class="ag-page-benefit">Log every bet and track your ROI, win rate, CLV capture, and bankroll growth over time. See which strategies actually make money.</div>
            </li>
          </ul>
        </div>

        <!-- ── TIER 3: Smart Money ($24.99/mo) ──────────── -->
        <div class="ag-tier-card t-smart">
          <div class="ag-tier-head">
            <div class="ag-tier-name">&#x1F48E; Smart Money</div>
            <div class="ag-tier-price-tag">$24.99/mo &middot; $269.89/yr</div>
          </div>
          <div class="ag-tier-tagline">&ldquo;You are the smart money.&rdquo; &mdash; Everything in Sharp IQ, plus:</div>
          <ul class="ag-page-list">
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x26A1;</span><span class="ag-page-name">Quantum Analysis Matrix &mdash; ALL 300+ Props</span></div>
              <div class="ag-page-benefit">Full, unrestricted access to every prop the AI analyzes tonight. See the complete board &mdash; no limits, no waiting.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4B0;</span><span class="ag-page-name">Smart Money Bets</span></div>
              <div class="ag-page-benefit">See where the sharp money is flowing. AI-detected line movement + volume anomalies show you which side the professionals are on.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F5FA;&#xFE0F;</span><span class="ag-page-name">Correlation Matrix</span></div>
              <div class="ag-page-benefit">Visual correlation heatmap between player props. Find hidden +EV parlays where props move together &mdash; or hedge with negative correlations.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F4CA;</span><span class="ag-page-name">Proving Grounds</span></div>
              <div class="ag-page-benefit">Backtest any strategy against historical data. See how your filters, SAFE Score thresholds, and entry styles would have performed last season.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F399;&#xFE0F;</span><span class="ag-page-name">The Studio</span></div>
              <div class="ag-page-benefit">AI-generated analysis reports with narrative breakdowns, data visualizations, and shareable pick cards for your best plays.</div>
            </li>
          </ul>
        </div>

        <!-- ── TIER 4: Insider Circle ($499 one-time) ──── -->
        <div class="ag-tier-card t-insider">
          <div class="ag-tier-head">
            <div class="ag-tier-name">&#x1F451; Insider Circle</div>
            <div class="ag-tier-price-tag">$499.99 one-time &middot; lifetime</div>
          </div>
          <div class="ag-tier-tagline">&ldquo;You knew before everyone.&rdquo; &mdash; Everything in Smart Money, plus:</div>
          <ul class="ag-page-list">
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F451;</span><span class="ag-page-name">Lifetime Access &mdash; Never Pay Again</span></div>
              <div class="ag-page-benefit">One payment, permanent access to every current feature and every future feature we build. No subscriptions, no renewals, no surprise charges.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F680;</span><span class="ag-page-name">Early Access to New Tools</span></div>
              <div class="ag-page-benefit">Be the first to test new AI models, pages, and features before they launch to the public. Your feedback shapes what we build next.</div>
            </li>
            <li class="ag-page-item">
              <div class="ag-page-head"><span class="ag-page-ico">&#x1F3C6;</span><span class="ag-page-name">Founding Member Status</span></div>
              <div class="ag-page-benefit">Limited to 75 members. Exclusive badge, priority support, and recognition as an original Smart Pick Pro insider.</div>
            </li>
          </ul>
        </div>

        <!-- Full tier comparison table -->
        <div class="ag-tier-tbl-wrap">
          <table class="ag-tier-tbl">
            <thead>
              <tr>
                <th>Page / Feature</th>
                <th class="th-fr">&#x2B50; Free</th>
                <th class="th-sh">&#x1F525; Sharp</th>
                <th class="th-sm">&#x1F48E; Smart</th>
                <th class="th-in">&#x1F451; Insider</th>
              </tr>
            </thead>
            <tbody>
              <tr class="cat"><td colspan="5">Core Pages (All Tiers)</td></tr>
              <tr><td>&#x1F4A6; Live Sweat</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F4E1; Live Games</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F4E1; Smart NBA Data</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x2699;&#xFE0F; Settings</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr class="cat"><td colspan="5">Prop Analysis Engine</td></tr>
              <tr><td>&#x26A1; Quantum Analysis Matrix</td><td class="lim">10 props</td><td class="lim">25 props</td><td class="y">All 300+</td><td class="y">All 300+</td></tr>
              <tr><td>&#x1F52C; Prop Scanner &mdash; Manual</td><td class="lim">5 props</td><td class="y">Unlimited</td><td class="y">Unlimited</td><td class="y">Unlimited</td></tr>
              <tr><td>&#x1F52C; Prop Scanner &mdash; CSV Upload</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F52C; Prop Scanner &mdash; Live Retrieval</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr class="cat"><td colspan="5">Premium Tools (Sharp IQ+)</td></tr>
              <tr><td>&#x1F9EC; Entry Builder</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F6E1;&#xFE0F; Risk Shield</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F4CB; Game Report</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F52E; Player Simulator</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F4C8; Bet Tracker</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr class="cat"><td colspan="5">Elite Tools (Smart Money+)</td></tr>
              <tr><td>&#x1F4B0; Smart Money Bets</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F5FA;&#xFE0F; Correlation Matrix</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F4CA; Proving Grounds</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F399;&#xFE0F; The Studio</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td><td class="y">&#x2713;</td></tr>
              <tr class="cat"><td colspan="5">Insider Exclusive</td></tr>
              <tr><td>&#x1F451; Lifetime Access</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F680; Early Access to New Tools</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td></tr>
              <tr><td>&#x1F3C6; Founding Member (75 seats)</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="n">&#x2717;</td><td class="y">&#x2713;</td></tr>
            </tbody>
          </table>
        </div>
      </details><!-- end ag-cmp-details -->
    </div>

    <!-- Savings callout -->
    <div class="ag-savings">
      <p class="ag-savings-text">You&rsquo;d pay <span class="big">$1,188/yr</span> for OddsJam alone.</p>
      <p class="ag-savings-sub">Smart Pick Pro gives you more features, more AI, more props &mdash; for $0. Do the math.</p>
    </div>

    <div class="ag-trust">
      <div class="ag-trust-item">&#x1F512; 256-bit Encrypted</div>
      <div class="ag-trust-item">&#x1F4B3; No Credit Card</div>
      <div class="ag-trust-item">&#x1F6AB; Never Sell Data</div>
    </div>

    <div class="ag-footer">
      &copy; 2026 Smart Pick Pro &middot; For entertainment &amp; educational purposes only &middot; 21+<br>
      <a href="https://www.ncpgambling.org/" target="_blank">National Council on Problem Gambling &middot; 1-800-GAMBLER</a>
    </div>
    """, unsafe_allow_html=True)

    return False
