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


# ── CSS for the gate ──────────────────────────────────────────

_GATE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

/* Hide Streamlit sidebar + default header while on gate */
[data-testid="stSidebar"], header[data-testid="stHeader"] {
    display: none !important;
}
[data-testid="stAppViewContainer"] {
    padding-top: 0 !important;
}

.auth-gate-bg {
    position: fixed; inset: 0; z-index: 9998;
    background: linear-gradient(135deg, #070a13 0%, #0d1117 40%, #111827 100%);
    overflow-y: auto;
}
.auth-gate-bg::before {
    content: '';
    position: fixed; inset: 0;
    background:
        radial-gradient(ellipse at 20% 30%, rgba(0,213,89,0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 70%, rgba(45,158,255,0.05) 0%, transparent 50%);
    pointer-events: none;
}

.auth-gate-container {
    position: relative; z-index: 9999;
    max-width: 440px; margin: 0 auto; padding: 60px 24px 40px;
    font-family: 'Inter', sans-serif;
}

.auth-logo {
    text-align: center; margin-bottom: 12px;
}
.auth-logo-text {
    font-size: 2rem; font-weight: 900;
    background: linear-gradient(135deg, #FFFFFF, #00D559 60%, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
}
.auth-logo-sub {
    font-size: 0.82rem; color: rgba(255,255,255,0.45);
    letter-spacing: 0.08em; text-transform: uppercase;
    margin-top: 4px;
}

.auth-headline {
    text-align: center; margin: 28px 0 8px;
    font-size: 1.5rem; font-weight: 800; color: #FFFFFF;
    line-height: 1.3;
}
.auth-subheadline {
    text-align: center; font-size: 0.92rem;
    color: rgba(255,255,255,0.55); margin-bottom: 28px;
    line-height: 1.5;
}

.auth-card {
    background: rgba(22,27,39,0.85);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px; padding: 32px 28px;
    backdrop-filter: blur(24px);
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.auth-divider {
    display: flex; align-items: center; gap: 12px;
    margin: 20px 0; color: rgba(255,255,255,0.25);
    font-size: 0.78rem; text-transform: uppercase;
    letter-spacing: 0.1em;
}
.auth-divider::before, .auth-divider::after {
    content: ''; flex: 1; height: 1px;
    background: rgba(255,255,255,0.08);
}

.auth-features {
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    margin-top: 28px;
}
.auth-feature {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.78rem; color: rgba(255,255,255,0.55);
}
.auth-feature-icon {
    color: #00D559; font-size: 0.9rem; flex-shrink: 0;
}

.auth-trust {
    text-align: center; margin-top: 24px;
    font-size: 0.72rem; color: rgba(255,255,255,0.3);
}

.auth-banner {
    text-align: center; padding: 10px;
    background: linear-gradient(90deg, rgba(0,213,89,0.08), rgba(45,158,255,0.08));
    border: 1px solid rgba(0,213,89,0.15);
    border-radius: 10px; margin-bottom: 20px;
    font-size: 0.82rem; color: rgba(255,255,255,0.7);
}

@media (max-width: 520px) {
    .auth-gate-container { padding: 40px 16px 30px; }
    .auth-card { padding: 24px 18px; }
    .auth-features { grid-template-columns: 1fr; }
    .auth-headline { font-size: 1.25rem; }
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

    st.markdown("""
    <div class="auth-gate-bg"></div>
    <div class="auth-gate-container">
      <div class="auth-logo">
        <div class="auth-logo-text">Smart Pick Pro</div>
        <div class="auth-logo-sub">The Sharpest Prop Engine on the Internet</div>
      </div>
      <div class="auth-headline">The House Has a Problem. It's Us.</div>
      <div class="auth-subheadline">Create your free account to access the platform.<br>No credit card required.</div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs for signup / login
    tab_signup, tab_login = st.tabs(["Create Account", "Log In"])

    with tab_signup:
        st.markdown('<div class="auth-banner">🏀 NBA IS LIVE · ⚾ MLB COMING SOON · 🏈 NFL COMING SOON</div>', unsafe_allow_html=True)

        with st.form("signup_form", clear_on_submit=False):
            su_name = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email", placeholder="you@example.com", key="_su_email")
            su_pw = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="_su_pw2")
            su_submit = st.form_submit_button("⚡ Create Free Account", use_container_width=True, type="primary")

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

        st.markdown("""
        <div class="auth-features">
          <div class="auth-feature"><span class="auth-feature-icon">✅</span> 300+ props analyzed nightly</div>
          <div class="auth-feature"><span class="auth-feature-icon">✅</span> Quantum Matrix Engine</div>
          <div class="auth-feature"><span class="auth-feature-icon">✅</span> SAFE Score™ on every pick</div>
          <div class="auth-feature"><span class="auth-feature-icon">✅</span> AI Analyst Joseph M. Smith</div>
          <div class="auth-feature"><span class="auth-feature-icon">✅</span> PrizePicks · Underdog · DK</div>
          <div class="auth-feature"><span class="auth-feature-icon">✅</span> Free tier — no card needed</div>
        </div>
        <div class="auth-trust">🔒 256-bit SSL · Passwords are encrypted · We never share your data</div>
        """, unsafe_allow_html=True)

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            li_email = st.text_input("Email", placeholder="you@example.com", key="_li_email")
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

    st.markdown("""
    <div style="text-align:center;margin-top:32px;font-size:0.72rem;color:rgba(255,255,255,0.25);">
      © 2026 Smart Pick Pro · For entertainment & educational purposes only · 21+ · 1-800-GAMBLER
    </div>
    """, unsafe_allow_html=True)

    return False
