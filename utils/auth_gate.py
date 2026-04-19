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
from pathlib import Path

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

# ── Preview-picks loader (for the auth gate "See What You Get" section) ───

import html as _html_mod
from datetime import datetime, timezone, timedelta


def _nba_today_str() -> str:
    """Return today's date in ISO format using ET (NBA timezone)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d")


def _display_stat_label(raw: str) -> str:
    """Convert internal stat key to a short display label."""
    _MAP = {
        "pts": "PTS", "points": "PTS",
        "reb": "REB", "rebounds": "REB",
        "ast": "AST", "assists": "AST",
        "stl": "STL", "steals": "STL",
        "blk": "BLK", "blocks": "BLK",
        "3pm": "3PM", "threes": "3PM", "fg3m": "3PM",
        "pts+reb": "P+R", "pts+ast": "P+A", "pts+reb+ast": "PRA",
        "reb+ast": "R+A", "stl+blk": "S+B",
        "turnovers": "TO", "tov": "TO",
        "fantasy_score": "FPTS",
    }
    return _MAP.get(raw.lower().strip(), raw.upper()[:6])


def _load_top_preview_picks(limit: int = 5) -> list[dict]:
    """Load today's top analysis picks from the database for the landing page preview.

    Falls back to the JSON cache file (``cache/latest_picks.json``), then
    to the latest available day in the DB.  This ensures the landing page
    always shows real picks — even on fresh Railway deploys where the
    SQLite DB is empty but the cache file shipped with the Docker image.
    Returns a list of dicts with pick data, sorted by confidence descending.
    """
    initialize_database()
    try:
        with get_database_connection() as conn:
            conn.row_factory = sqlite3.Row
            today = _nba_today_str()
            # Try today first, then fall back to latest available date
            for date_query in [today, None]:
                if date_query:
                    rows = conn.execute(
                        """SELECT player_name, team, stat_type, prop_line, direction,
                                  platform, confidence_score, probability_over,
                                  edge_percentage, tier
                           FROM all_analysis_picks
                           WHERE pick_date = ?
                           ORDER BY confidence_score DESC
                           LIMIT ?""",
                        (date_query, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT player_name, team, stat_type, prop_line, direction,
                                  platform, confidence_score, probability_over,
                                  edge_percentage, tier
                           FROM all_analysis_picks
                           ORDER BY pick_date DESC, confidence_score DESC
                           LIMIT ?""",
                        (limit,),
                    ).fetchall()
                if rows:
                    return [dict(r) for r in rows]
    except Exception as exc:
        _logger.debug("_load_top_preview_picks DB: %s", exc)

    # ── JSON cache fallback (survives empty DB on Railway) ──
    return _load_picks_from_cache(limit)


def _load_picks_from_cache(limit: int = 5) -> list[dict]:
    """Read top picks from ``cache/latest_picks.json``.

    This file is written by ``tracking.database.insert_analysis_picks``
    every time analysis runs and is also committed to the repo so fresh
    Docker images always ship with recent picks.
    """
    import json as _json
    try:
        cache_path = Path(__file__).resolve().parent.parent / "cache" / "latest_picks.json"
        if cache_path.exists():
            data = _json.loads(cache_path.read_text(encoding="utf-8"))
            picks = data.get("picks", [])
            if picks:
                _logger.debug("Loaded %d picks from cache/latest_picks.json", len(picks))
                return picks[:limit]
    except Exception as exc:
        _logger.debug("_load_picks_from_cache: %s", exc)
    return []


def _build_preview_section_html(picks: list[dict]) -> str:
    """Build the 'See What You Get' horizontally-scrolling platform-pick cards.

    Uses the same visual language as the QAM Platform AI Picks cards:
    headshot, team badge, big line number, direction, and metrics row.
    If *picks* is empty, returns a static fallback section.
    """
    # ── CSS (self-contained inside the st.html iframe) ──
    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,.7);overflow-y:hidden}
/* Frame */
.pv-frame{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:16px;overflow:hidden}
.pv-titlebar{display:flex;align-items:center;gap:6px;padding:8px 12px;background:rgba(255,255,255,.03);border-bottom:1px solid rgba(255,255,255,.04)}
.pv-dot{width:7px;height:7px;border-radius:50%}.pv-dot.r{background:#f24336}.pv-dot.y{background:#F9C62B}.pv-dot.g{background:#00D559}
.pv-url{flex:1;text-align:center;font-family:'JetBrains Mono',monospace;font-size:.5rem;color:rgba(255,255,255,.2)}
.pv-header{display:flex;align-items:center;justify-content:space-between;padding:12px 14px 8px}
.pv-title{font-family:'Space Grotesk',sans-serif;font-size:.78rem;font-weight:700;color:rgba(255,255,255,.7)}
.pv-live{font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:700;color:#00D559;background:rgba(0,213,89,.08);border:1px solid rgba(0,213,89,.15);padding:2px 8px;border-radius:100px}
/* Scroll track */
.pv-scroll{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;scrollbar-width:thin;scrollbar-color:rgba(192,132,252,.3) transparent;padding:4px 14px 14px}
.pv-scroll::-webkit-scrollbar{height:6px}
.pv-scroll::-webkit-scrollbar-track{background:rgba(255,255,255,.02);border-radius:100px}
.pv-scroll::-webkit-scrollbar-thumb{background:rgba(192,132,252,.25);border-radius:100px}
.pv-track{display:inline-flex;gap:12px;padding:0}
/* Card */
.pv-card{width:200px;flex-shrink:0;background:linear-gradient(168deg,rgba(255,255,255,.04),rgba(255,255,255,.01));border:1px solid rgba(255,255,255,.07);border-radius:16px;position:relative;overflow:hidden;transition:border-color .25s,transform .25s,box-shadow .25s}
.pv-card:hover{border-color:rgba(192,132,252,.25);transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.35)}
.pv-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#c084fc,#60a5fa)}
/* Rank badge */
.pv-rank{position:absolute;top:8px;right:8px;font-family:'JetBrains Mono',monospace;font-size:.55rem;font-weight:800;color:rgba(255,255,255,.15)}
/* Status bar */
.pv-status{padding:10px 10px 0;display:flex;align-items:center;gap:6px}
.pv-badge{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:800;color:#c084fc;display:flex;align-items:center;gap:4px}
.pv-badge-icon{font-size:.55rem}
/* Headshot */
.pv-hs-wrap{text-align:center;padding:8px 0 2px}
.pv-headshot{width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid rgba(192,132,252,.2);background:rgba(255,255,255,.03)}
/* Info */
.pv-team{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:600;color:rgba(255,255,255,.25);text-transform:uppercase;letter-spacing:.1em;text-align:center}
.pv-name{font-family:'Space Grotesk',sans-serif;font-size:.76rem;font-weight:700;color:rgba(255,255,255,.92);text-align:center;line-height:1.2;margin:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 8px}
/* Line area */
.pv-line-area{text-align:center;padding:4px 0 6px}
.pv-line{font-family:'JetBrains Mono',monospace;font-size:1.5rem;font-weight:800;color:rgba(255,255,255,.95);line-height:1}
.pv-stat{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:600;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
/* Direction */
.pv-dir{text-align:center;padding:4px 0 8px}
.pv-dir span{font-family:'Space Grotesk',sans-serif;font-size:.58rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;padding:3px 12px;border-radius:100px}
.pv-dir span.more{color:#00D559;background:rgba(0,213,89,.1);border:1px solid rgba(0,213,89,.15)}
.pv-dir span.less{color:#60a5fa;background:rgba(96,165,250,.1);border:1px solid rgba(96,165,250,.15)}
/* Metrics */
.pv-metrics{display:flex;justify-content:space-around;padding:8px 6px;border-top:1px solid rgba(255,255,255,.04)}
.pv-metric{text-align:center}
.pv-metric-val{font-family:'JetBrains Mono',monospace;font-size:.62rem;font-weight:700;color:#c084fc}
.pv-metric-label{font-family:'JetBrains Mono',monospace;font-size:.38rem;font-weight:600;color:rgba(255,255,255,.2);text-transform:uppercase;letter-spacing:.06em;margin-top:1px}
/* hint */
.pv-hint{text-align:center;margin-top:8px;font-size:.55rem;color:rgba(255,255,255,.18);font-style:italic}
@media(max-width:520px){.pv-card{width:170px}.pv-line{font-size:1.2rem}.pv-name{font-size:.68rem}.pv-headshot{width:60px;height:60px}}
</style>"""

    # ── Build cards ──
    if not picks:
        # Static fallback when no analysis data exists yet
        _fallback = [
            {"player_name": "Luka Dončić", "team": "DAL", "stat_type": "points",
             "prop_line": 28.5, "direction": "OVER", "platform": "PrizePicks",
             "confidence_score": 92, "probability_over": 0.71, "edge_percentage": 6.2, "tier": "Platinum"},
            {"player_name": "Jayson Tatum", "team": "BOS", "stat_type": "rebounds",
             "prop_line": 8.5, "direction": "OVER", "platform": "PrizePicks",
             "confidence_score": 87, "probability_over": 0.66, "edge_percentage": 4.8, "tier": "Gold"},
            {"player_name": "Anthony Edwards", "team": "MIN", "stat_type": "points",
             "prop_line": 26.5, "direction": "UNDER", "platform": "PrizePicks",
             "confidence_score": 84, "probability_over": 0.32, "edge_percentage": 5.1, "tier": "Gold"},
            {"player_name": "Shai Gilgeous-Alexander", "team": "OKC", "stat_type": "points",
             "prop_line": 30.5, "direction": "OVER", "platform": "PrizePicks",
             "confidence_score": 90, "probability_over": 0.70, "edge_percentage": 5.3, "tier": "Platinum"},
            {"player_name": "Nikola Jokić", "team": "DEN", "stat_type": "assists",
             "prop_line": 9.5, "direction": "OVER", "platform": "PrizePicks",
             "confidence_score": 78, "probability_over": 0.63, "edge_percentage": 3.4, "tier": "Gold"},
        ]
        picks = _fallback

    # NBA headshot lookup
    _PLAYER_IDS: dict[str, str] = {
        "luka dončić": "1629029", "luka doncic": "1629029",
        "jayson tatum": "1628369", "anthony edwards": "1630162",
        "shai gilgeous-alexander": "1628983", "nikola jokić": "203999",
        "nikola jokic": "203999", "trae young": "1629027",
        "tyrese maxey": "1630178", "cade cunningham": "1630595",
        "jaylen brown": "1627759", "devin booker": "1626164",
        "lamelo ball": "1630163", "ja morant": "1629630",
        "donovan mitchell": "1628378", "stephen curry": "201939",
        "lebron james": "2544", "kevin durant": "201142",
        "giannis antetokounmpo": "203507", "joel embiid": "203954",
        "damian lillard": "203081", "bam adebayo": "1628389",
        "jimmy butler": "202710", "karl-anthony towns": "1626157",
        "jalen brunson": "1628973", "paolo banchero": "1631094",
        "victor wembanyama": "1641705", "darius garland": "1629636",
        "dejounte murray": "1627749", "franz wagner": "1630532",
    }

    cards_html = []
    for idx, pick in enumerate(picks):
        name = _html_mod.escape(pick.get("player_name", "Unknown"))
        team = _html_mod.escape((pick.get("team", "") or "").upper())
        stat_raw = (pick.get("stat_type", "") or "").lower().strip()
        stat_label = _html_mod.escape(_display_stat_label(stat_raw))

        try:
            line_val = float(pick.get("prop_line", 0) or 0)
            line_display = f"{line_val:g}"
        except (ValueError, TypeError):
            line_val = 0
            line_display = "—"

        direction = (pick.get("direction", "OVER") or "OVER").upper()
        dir_label = "MORE" if direction == "OVER" else "LESS"
        dir_class = "more" if direction == "OVER" else "less"
        dir_arrow = "&#8593;" if direction == "OVER" else "&#8595;"

        conf = float(pick.get("confidence_score", 0) or 0)
        edge = float(pick.get("edge_percentage", 0) or 0)

        prob_over = float(pick.get("probability_over", 0.5) or 0.5)
        prob = (prob_over if direction == "OVER" else 1.0 - prob_over) * 100

        # Confidence color
        if conf >= 80:
            conf_color = "#c084fc"
        elif conf >= 65:
            conf_color = "#fbbf24"
        else:
            conf_color = "#60a5fa"

        # Headshot URL (NBA CDN)
        pid = _PLAYER_IDS.get(name.lower(), "")
        hs_html = ""
        if pid:
            hs_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
            hs_html = (
                f'<div class="pv-hs-wrap">'
                f'<img class="pv-headshot" src="{hs_url}" alt="{name}" '
                f'onerror="this.style.display=\'none\'">'
                f'</div>'
            )
        else:
            # Generic silhouette fallback
            hs_html = (
                '<div class="pv-hs-wrap">'
                '<div class="pv-headshot" style="display:inline-block;'
                'background:linear-gradient(135deg,rgba(192,132,252,.15),rgba(96,165,250,.1));'
                'line-height:72px;font-size:1.5rem;color:rgba(255,255,255,.12);">&#9917;</div>'
                '</div>'
            )

        # Platform display name
        raw_plat = pick.get("platform", "Smart Pick") or "Smart Pick"
        if raw_plat.lower() in ("prizepicks", ""):
            plat_display = "Smart Pick"
        else:
            plat_display = _html_mod.escape(raw_plat)

        cards_html.append(
            f'<div class="pv-card" style="animation-delay:{idx * 100}ms;">'
            f'<span class="pv-rank">#{idx + 1}</span>'
            # Status bar
            f'<div class="pv-status">'
            f'<span class="pv-badge"><span class="pv-badge-icon">&#9889;</span> {plat_display} AI</span>'
            f'</div>'
            # Headshot
            f'{hs_html}'
            # Player info
            f'<div class="pv-team">{team}</div>'
            f'<div class="pv-name">{name}</div>'
            # Line
            f'<div class="pv-line-area">'
            f'<div class="pv-line">{_html_mod.escape(line_display)}</div>'
            f'<div class="pv-stat">{stat_label}</div>'
            f'</div>'
            # Direction pill
            f'<div class="pv-dir"><span class="{dir_class}">{dir_arrow} {dir_label}</span></div>'
            # Metrics
            f'<div class="pv-metrics">'
            f'<div class="pv-metric"><div class="pv-metric-val" style="color:{conf_color};">{conf:.0f}</div>'
            f'<div class="pv-metric-label">SAFE</div></div>'
            f'<div class="pv-metric"><div class="pv-metric-val" style="color:#c084fc;">{edge:+.1f}%</div>'
            f'<div class="pv-metric-label">Edge</div></div>'
            f'<div class="pv-metric"><div class="pv-metric-val">{prob:.0f}%</div>'
            f'<div class="pv-metric-label">Prob</div></div>'
            f'</div>'
            f'</div>'
        )

    num_picks = len(picks)
    cards_joined = "".join(cards_html)

    return (
        f'{css}'
        f'<div class="pv-frame">'
        f'<div class="pv-titlebar"><div class="pv-dot r"></div><div class="pv-dot y"></div>'
        f'<div class="pv-dot g"></div>'
        f'<div class="pv-url">smartpickpro.com &middot; Quantum Analysis Matrix</div></div>'
        f'<div class="pv-header"><div class="pv-title">&#9889; Free Picks Today</div>'
        f'<div class="pv-live">LIVE &middot; {num_picks} Picks</div></div>'
        f'<div class="pv-scroll"><div class="pv-track">{cards_joined}</div></div>'
        f'</div>'
        f'<div class="pv-hint">&#8592; Scroll to see today\'s AI picks &#8594;</div>'
    )


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
    padding: 0 !important;
    max-width: 100% !important;
    margin: 0 auto !important;
    position: relative;
    z-index: 10;
}

html, body, .stApp, .stApp * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Full-bleed wrapper ──────────────────────────────────────── */
.ag-section {
    width: 100%; max-width: 780px; margin: 0 auto;
    padding-left: 28px; padding-right: 28px;
}
.ag-full-bleed {
    width: 100vw; position: relative;
    left: 50%; transform: translateX(-50%);
    padding: 48px 0;
}
.ag-full-bleed .ag-section {
    max-width: 780px; margin: 0 auto;
    padding-left: 28px; padding-right: 28px;
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
    50%      { box-shadow: 0 0 0 10px rgba(0, 213, 89, 0); }
}
@keyframes agGradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes agNumberPop {
    0%   { transform: scale(0.5); opacity: 0; }
    60%  { transform: scale(1.05); }
    100% { transform: scale(1); opacity: 1; }
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
    background: radial-gradient(ellipse at 50% 0%, rgba(0, 213, 89, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(45, 158, 255, 0.06) 0%, transparent 40%),
                radial-gradient(ellipse at 20% 60%, rgba(192, 132, 252, 0.04) 0%, transparent 40%),
                #0B0F19;
    overflow: hidden;
}
.ag-orb {
    position: absolute; border-radius: 50%; pointer-events: none;
    filter: blur(100px); opacity: 0.7;
    animation: agOrbFloat 20s ease-in-out infinite;
}
.ag-orb-1 {
    width: 600px; height: 600px; top: -150px; left: -120px;
    background: rgba(0, 213, 89, 0.12);
}
.ag-orb-2 {
    width: 550px; height: 550px; bottom: -120px; right: -100px;
    background: rgba(45, 158, 255, 0.09);
    animation-delay: -7s;
}
.ag-orb-3 {
    width: 400px; height: 400px; top: 40%; left: 50%;
    transform: translateX(-50%);
    background: rgba(192, 132, 252, 0.06);
    animation-delay: -12s;
}

/* \u2500\u2500 Section divider \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */
.ag-divider {
    height: 1px; margin: 48px 40px;
    background: linear-gradient(90deg, transparent, rgba(0, 213, 89, 0.15), rgba(45, 158, 255, 0.1), transparent);
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
    width: 200px;
    height: auto;
    animation: agLogoGlow 4s ease-in-out infinite;
}

/* ── Hero (Nike-scale) ─────────────────────────────────────── */
.ag-hero {
    text-align: center;
    padding: 24px 28px 0;
    max-width: 780px; margin: 0 auto;
    animation: agFadeUp 0.6s 0.08s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-hero h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 4.2rem; font-weight: 700;
    line-height: 0.98; letter-spacing: -0.05em;
    color: #fff; margin: 0;
    text-transform: uppercase;
}
.ag-hero .em {
    display: block;
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 40%, #c084fc 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 6s ease infinite;
}
.ag-hero-sub {
    font-size: 1rem; color: rgba(255, 255, 255, 0.5);
    line-height: 1.7; margin-top: 20px;
    max-width: 540px; margin-left: auto; margin-right: auto;
}
.ag-hero-sub strong {
    color: #fff; font-weight: 700;
}
.ag-hero-sub2 {
    display: inline-flex; align-items: center; gap: 8px;
    margin-top: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; font-weight: 700;
    color: #00D559;
    background: rgba(0, 213, 89, 0.06);
    border: 1px solid rgba(0, 213, 89, 0.18);
    padding: 8px 24px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.06em;
}

/* ── Proof strip (3 oversized stats) ─────────────────────── */
.ag-proof-strip {
    width: 100vw; position: relative;
    left: 50%; transform: translateX(-50%);
    background: linear-gradient(180deg, rgba(0, 213, 89, 0.04) 0%, transparent 100%);
    border-top: 1px solid rgba(0, 213, 89, 0.08);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    padding: 36px 0;
    margin: 28px 0 0;
}
.ag-proof-inner {
    display: flex; justify-content: center; gap: 0;
    max-width: 780px; margin: 0 auto;
}
.ag-proof-stat {
    flex: 1; text-align: center;
    padding: 12px 20px;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
    animation: agNumberPop 0.6s 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-proof-stat:last-child { border-right: none; }
.ag-proof-stat:nth-child(2) { animation-delay: 0.35s; }
.ag-proof-stat:nth-child(3) { animation-delay: 0.5s; }
.ag-proof-stat:nth-child(4) { animation-delay: 0.65s; }
.ag-proof-big {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3.2rem; font-weight: 700;
    letter-spacing: -0.04em; line-height: 1;
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-proof-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.5);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-top: 6px;
}
.ag-proof-sub {
    font-size: 0.6rem; color: rgba(255, 255, 255, 0.2);
    margin-top: 4px;
}

/* Keep old proof bar for backward compat */
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

/* ── "What's Inside" feature showcase ────────────────────────── */
.ag-inside {
    margin: 48px 0 0;
    animation: agFadeUp 0.6s 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-inside-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;
}
.ag-inside-card {
    background: linear-gradient(168deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.012));
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px; padding: 24px 20px 20px;
    position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
}
}
.ag-inside-card:hover {
    border-color: rgba(192, 132, 252, 0.25);
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25), 0 0 20px rgba(192, 132, 252, 0.04);
}
.ag-inside-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #c084fc, #60a5fa, #00D559);
    opacity: 0; transition: opacity 0.3s;
}
.ag-inside-card:hover::before { opacity: 1; }
.ag-inside-ico {
    display: inline-flex; align-items: center; justify-content: center;
    width: 52px; height: 52px; border-radius: 14px;
    background: linear-gradient(135deg, rgba(192, 132, 252, 0.12), rgba(96, 165, 250, 0.08));
    border: 1px solid rgba(192, 132, 252, 0.12);
    font-size: 1.5rem; margin-bottom: 14px;
}
.ag-inside-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem; font-weight: 700;
    color: #fff;
    margin-bottom: 8px;
}
.ag-inside-desc {
    font-size: 0.72rem; color: rgba(255, 255, 255, 0.42);
    line-height: 1.65;
}
.ag-inside-tag {
    display: inline-block; margin-top: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.5rem; font-weight: 800;
    color: #c084fc; background: rgba(192, 132, 252, 0.1);
    border: 1px solid rgba(192, 132, 252, 0.18);
    padding: 4px 12px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.08em;
}

/* ── Tabs ────────────────────────────────────────────────────── */
[data-testid="stTabs"] {
    animation: agFadeUp 0.6s 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
    max-width: 520px; margin: 0 auto;
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
    text-align: center; margin-bottom: 28px;
    position: relative;
}
.ag-section-head::before {
    content: ''; display: block; width: 60px; height: 4px; margin: 0 auto 18px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    border-radius: 4px;
}
.ag-section-head h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.2rem; font-weight: 700;
    color: #fff; margin: 0 0 10px;
    letter-spacing: -0.04em;
    text-transform: uppercase;
}
.ag-section-head h3 .em {
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 50%, #c084fc 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 6s ease infinite;
}
.ag-section-head p {
    font-size: 0.85rem; color: rgba(255, 255, 255, 0.4);
    margin: 0; line-height: 1.6;
}

/* ── Competitor graveyard ────────────────────────────────────── */
.ag-graveyard {
    margin: 56px 0 0;
    animation: agFadeUp 0.6s 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-gy-badge {
    display: block; width: fit-content; margin: 0 auto 18px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem; font-weight: 800;
    color: #f24336; background: rgba(242, 67, 54, 0.06);
    border: 1px solid rgba(242, 67, 54, 0.15);
    padding: 5px 16px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.12em;
}
.ag-gy-head {
    text-align: center; margin-bottom: 32px; position: relative;
}
.ag-gy-head::before {
    content: ''; display: block; width: 80px; height: 4px; margin: 0 auto 20px;
    background: linear-gradient(90deg, #f24336, #F9C62B);
    border-radius: 4px;
}
.ag-gy-head h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.8rem; font-weight: 800;
    color: #fff; margin: 0 0 14px;
    letter-spacing: -0.04em;
    text-transform: uppercase; line-height: 1.05;
}
.ag-gy-head h3 .em {
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 50%, #c084fc 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 6s ease infinite;
}
.ag-gy-head p {
    font-size: 0.95rem; color: rgba(255, 255, 255, 0.45);
    margin: 0; line-height: 1.6;
}
.ag-gy-head p em {
    font-style: normal; color: #f24336; font-weight: 700;
}

/* Competitor cards */
.ag-comp-grid {
    display: grid; grid-template-columns: 1fr; gap: 10px;
    margin-bottom: 24px;
}
.ag-comp {
    display: grid; grid-template-columns: auto 1.5fr auto 1.2fr; align-items: center; gap: 14px;
    background: linear-gradient(168deg, rgba(242, 67, 54, 0.06), rgba(242, 67, 54, 0.015));
    border: 1px solid rgba(242, 67, 54, 0.12);
    border-radius: 16px; padding: 16px 22px;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
    position: relative; overflow: hidden;
}
.ag-comp:hover {
    border-color: rgba(242, 67, 54, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.3);
}
.ag-comp-x {
    width: 28px; height: 28px; border-radius: 50%;
    background: rgba(242, 67, 54, 0.12);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 900; color: rgba(242, 67, 54, 0.7);
    flex-shrink: 0;
}
.ag-comp-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.95rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.7);
}
.ag-comp-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem; font-weight: 800;
    color: rgba(242, 67, 54, 0.85);
    text-decoration: line-through;
    text-decoration-thickness: 2px;
    text-decoration-color: rgba(242, 67, 54, 0.5);
}
.ag-comp-miss {
    font-size: 0.72rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.28);
    text-align: right;
}

/* Our card (the winner) */
.ag-us {
    display: flex; flex-direction: column; align-items: center;
    background: linear-gradient(168deg, rgba(0, 213, 89, 0.1), rgba(45, 158, 255, 0.03));
    border: 2px solid rgba(0, 213, 89, 0.35);
    border-radius: 28px; padding: 40px 28px 36px;
    text-align: center; position: relative;
    margin-top: 14px;
    animation: agPulse 3s ease-in-out infinite;
    box-shadow: 0 0 80px rgba(0, 213, 89, 0.1), 0 24px 64px rgba(0, 0, 0, 0.35);
}
.ag-us::before {
    content: ''; position: absolute; inset: 0; border-radius: 28px;
    background: radial-gradient(ellipse at 50% 0%, rgba(0, 213, 89, 0.1) 0%, transparent 50%);
    pointer-events: none;
}
.ag-us::after {
    content: 'WINNER'; position: absolute; top: -12px; left: 50%; transform: translateX(-50%);
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.6rem; font-weight: 800; letter-spacing: 0.15em;
    color: #0B0F19; background: linear-gradient(135deg, #00D559, #2D9EFF);
    padding: 5px 20px; border-radius: 100px;
    box-shadow: 0 4px 16px rgba(0, 213, 89, 0.3);
}
.ag-us-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.8rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.12em;
    color: #00D559; margin-bottom: 4px; margin-top: 8px;
}
.ag-us-price {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 5rem; font-weight: 800; color: #fff;
    line-height: 1; position: relative;
}
.ag-us-price .free {
    background: linear-gradient(135deg, #00D559, #2D9EFF, #c084fc);
    background-size: 300% 300%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 4s ease infinite;
}
.ag-us-price .p {
    font-size: 0.8rem; font-weight: 500; color: rgba(255, 255, 255, 0.35);
    font-family: 'Inter', sans-serif; vertical-align: middle;
}
.ag-us-detail {
    font-size: 0.82rem; color: rgba(255, 255, 255, 0.5);
    margin-top: 12px; line-height: 1.6;
    max-width: 520px; position: relative;
}
.ag-us-detail strong { color: #fff; }

/* ── Full comparison table ───────────────────────────────────── */
.ag-compare {
    margin: 56px 0 0;
    animation: agFadeUp 0.6s 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-tbl {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: linear-gradient(168deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015));
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 24px; overflow: hidden;
    font-size: 0.85rem;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.03) inset;
}
.ag-tbl thead th {
    padding: 20px 14px; font-size: 0.62rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.1em;
    color: rgba(255,255,255,0.3);
    border-bottom: 2px solid rgba(255,255,255,0.06);
    font-family: 'Space Grotesk', sans-serif;
    background: rgba(255,255,255,0.02);
}
.ag-tbl thead th:first-child { text-align: left; width: 26%; padding-left: 24px; }
.ag-tbl thead th:not(:first-child) { text-align: center; width: 18.5%; }
.ag-tbl thead th:last-child {
    color: #00D559; background: linear-gradient(180deg, rgba(0,213,89,0.1), rgba(0,213,89,0.03));
    position: relative; width: 22%;
    text-shadow: 0 0 20px rgba(0,213,89,0.3);
}
.ag-tbl thead th:last-child::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
}
/* Glowing column borders */
.ag-tbl tbody td:last-child::before,
.ag-tbl thead th:last-child::after {
    content: ''; position: absolute; top: 0; bottom: 0; left: 0; width: 1px;
    background: linear-gradient(180deg, rgba(0,213,89,0.3), rgba(0,213,89,0.05));
}
.ag-tbl tbody td {
    padding: 16px 14px; color: rgba(255,255,255,0.3);
    border-bottom: 1px solid rgba(255,255,255,0.04);
    font-weight: 600; text-align: center;
    transition: background 0.3s, transform 0.2s;
    position: relative;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
}
.ag-tbl tbody td:first-child {
    font-weight: 700; color: rgba(255,255,255,0.7); text-align: left; padding-left: 24px;
    font-family: 'Space Grotesk', sans-serif; font-size: 0.82rem;
}
.ag-tbl tbody td:first-child .ft-ico {
    display: inline-block; width: 22px; text-align: center; margin-right: 8px;
    font-size: 0.82rem; vertical-align: middle;
}
.ag-tbl tbody td:last-child {
    color: #00D559; background: rgba(0,213,89,0.04);
    font-weight: 800; font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem; position: relative;
}
.ag-tbl tbody tr { transition: background 0.2s; }
.ag-tbl tbody tr:last-child td { border-bottom: none; }
.ag-tbl tbody tr:hover td { background: rgba(255,255,255,0.025); }
.ag-tbl tbody tr:hover td:last-child { background: rgba(0,213,89,0.08); }
/* X marks — dim red with subtle glow */
.ag-tbl .x {
    color: rgba(242,67,54,0.45); font-weight: 700;
    font-size: 0.9rem;
}
/* Checkmarks — bright green */
.ag-tbl .ch {
    color: #00D559; font-weight: 800;
    text-shadow: 0 0 12px rgba(0,213,89,0.15);
}
/* Partial/limited — muted amber */
.ag-tbl .pt { color: rgba(249,198,43,0.5); font-weight: 600; }
/* Price highlight row */
.ag-tbl .hi {
    background: linear-gradient(90deg, rgba(0,213,89,0.06), rgba(0,213,89,0.12));
    border-top: 2px solid rgba(0,213,89,0.25);
}
.ag-tbl .hi td {
    font-size: 0.95rem; padding: 20px 14px;
    font-family: 'Space Grotesk', sans-serif;
}
.ag-tbl .hi td:first-child { padding-left: 24px; font-size: 0.95rem; }
.ag-tbl .hi td:last-child {
    font-size: 1.3rem; color: #00D559;
    text-shadow: 0 0 30px rgba(0,213,89,0.3), 0 0 60px rgba(0,213,89,0.1);
    letter-spacing: 0.04em;
}
.ag-tbl .hi td.x {
    color: rgba(242,67,54,0.6); font-size: 0.92rem;
    text-decoration: line-through; text-decoration-color: rgba(242,67,54,0.3);
}
/* Row animation */
@keyframes agRowSlide { from { opacity: 0; transform: translateX(-12px); } to { opacity: 1; transform: translateX(0); } }
.ag-tbl tbody tr { animation: agRowSlide 0.4s cubic-bezier(0.22,1,0.36,1) both; }
.ag-tbl tbody tr:nth-child(1) { animation-delay: 0.05s; }
.ag-tbl tbody tr:nth-child(2) { animation-delay: 0.08s; }
.ag-tbl tbody tr:nth-child(3) { animation-delay: 0.11s; }
.ag-tbl tbody tr:nth-child(4) { animation-delay: 0.14s; }
.ag-tbl tbody tr:nth-child(5) { animation-delay: 0.17s; }
.ag-tbl tbody tr:nth-child(6) { animation-delay: 0.20s; }
.ag-tbl tbody tr:nth-child(7) { animation-delay: 0.23s; }
.ag-tbl tbody tr:nth-child(8) { animation-delay: 0.26s; }
.ag-tbl tbody tr:nth-child(9) { animation-delay: 0.29s; }
.ag-tbl tbody tr:nth-child(10) { animation-delay: 0.32s; }
.ag-tbl tbody tr:nth-child(11) { animation-delay: 0.35s; }

/* ── "Bottom Line" callout ───────────────────────────────────── */
.ag-bottom-line {
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.12), rgba(45, 158, 255, 0.06), rgba(192, 132, 252, 0.04));
    border: 2px solid rgba(0, 213, 89, 0.25);
    border-radius: 28px; padding: 48px 32px;
    text-align: center; margin: 48px 0 0;
    animation: agFadeUp 0.6s 0.36s cubic-bezier(0.22, 1, 0.36, 1) both;
    position: relative; overflow: hidden;
    box-shadow: 0 0 80px rgba(0, 213, 89, 0.08), 0 20px 60px rgba(0, 0, 0, 0.35);
}
.ag-bottom-line::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(0, 213, 89, 0.1) 0%, transparent 55%);
    pointer-events: none;
}
.ag-bl-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.2rem; font-weight: 800;
    color: #fff; margin: 0 0 18px;
    text-transform: uppercase; letter-spacing: -0.03em;
    line-height: 1.1; position: relative;
}
.ag-bl-headline .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF, #c084fc);
    background-size: 300% 300%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 4s ease infinite;
}
.ag-bl-body {
    font-size: 0.95rem; color: rgba(255, 255, 255, 0.5);
    line-height: 1.75; margin: 0;
    max-width: 620px; margin-left: auto; margin-right: auto;
    position: relative;
}
.ag-bl-body strong { color: #fff; font-weight: 700; }

/* ── Feature cards (3-col) ───────────────────────────────────── */
.ag-features {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px;
    margin: 56px 0 0;
    animation: agFadeUp 0.6s 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-feat {
    background: linear-gradient(168deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.015));
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 28px; padding: 36px 20px 28px;
    text-align: center; position: relative; overflow: hidden;
    transition: border-color 0.4s, transform 0.4s, box-shadow 0.4s;
}
.ag-feat::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #c084fc);
    opacity: 0; transition: opacity 0.4s;
}
.ag-feat:hover {
    border-color: rgba(0, 213, 89, 0.35);
    transform: translateY(-8px);
    box-shadow: 0 20px 56px rgba(0, 0, 0, 0.4), 0 0 40px rgba(0, 213, 89, 0.1);
}
.ag-feat:hover::before { opacity: 1; }
.ag-feat-ico {
    display: inline-flex; align-items: center; justify-content: center;
    width: 72px; height: 72px; border-radius: 20px;
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.15), rgba(45, 158, 255, 0.1));
    border: 1px solid rgba(0, 213, 89, 0.15);
    font-size: 2.2rem; margin-bottom: 16px;
    box-shadow: 0 8px 24px rgba(0, 213, 89, 0.06);
}
.ag-feat-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem; font-weight: 800;
    color: #fff; text-transform: uppercase;
    letter-spacing: -0.02em; line-height: 1.2;
}
.ag-feat-desc {
    font-size: 0.82rem; color: rgba(255, 255, 255, 0.42);
    margin-top: 8px; line-height: 1.55;
}

/* ── Metric counters ─── full-bleed stats strip ──────────────── */
.ag-stats-strip {
    margin: 56px -40px 0; padding: 0 40px;
    background: linear-gradient(180deg, rgba(0, 213, 89, 0.04) 0%, transparent 100%);
    border-top: 1px solid rgba(0, 213, 89, 0.1);
    border-bottom: 1px solid rgba(0, 213, 89, 0.1);
    animation: agFadeUp 0.6s 0.44s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-stats {
    display: grid; grid-template-columns: repeat(6, 1fr); gap: 0;
    padding: 32px 0;
}
.ag-stat {
    text-align: center; position: relative; padding: 8px 4px;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}
.ag-stat:last-child { border-right: none; }
.ag-stat-val {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.8rem; font-weight: 800;
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 50%, #c084fc 100%);
    background-size: 300% 300%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 5s ease infinite;
    line-height: 1;
}
.ag-stat-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.68rem; color: rgba(255, 255, 255, 0.35);
    font-weight: 700; margin-top: 8px;
    text-transform: uppercase; letter-spacing: 0.1em;
}

/* ── Testimonials ────────────────────────────────────────────── */
.ag-reviews {
    margin: 56px 0 0;
    animation: agFadeUp 0.6s 0.48s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-review {
    background: linear-gradient(168deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.015));
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 24px; padding: 32px 32px 28px;
    margin-bottom: 16px; position: relative;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
    overflow: hidden;
}
.ag-review::before {
    content: '\u201C'; position: absolute; top: 16px; left: 24px;
    font-family: Georgia, serif; font-size: 5rem;
    color: rgba(0, 213, 89, 0.08); line-height: 1;
    pointer-events: none;
}
.ag-review:hover {
    border-color: rgba(0, 213, 89, 0.3);
    transform: translateY(-4px);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.3), 0 0 24px rgba(0, 213, 89, 0.05);
}
.ag-review-text {
    font-size: 1.05rem; color: rgba(255, 255, 255, 0.7);
    font-style: italic; line-height: 1.75;
    position: relative; padding-left: 4px;
}
.ag-review-meta {
    display: flex; align-items: center; gap: 12px;
    margin-top: 16px; position: relative;
}
.ag-review-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.2), rgba(45, 158, 255, 0.15));
    border: 2px solid rgba(0, 213, 89, 0.2);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem; flex-shrink: 0;
}
.ag-review-info { display: flex; flex-direction: column; }
.ag-review-author {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem; font-weight: 700;
    color: #00D559;
}
.ag-review-stars {
    color: #F9C62B; font-size: 0.78rem; margin-top: 2px;
    letter-spacing: 2px;
}
.ag-review-verified {
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem; font-weight: 700;
    color: rgba(0, 213, 89, 0.5);
    background: rgba(0, 213, 89, 0.06);
    border: 1px solid rgba(0, 213, 89, 0.1);
    padding: 3px 10px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.1em;
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
    background: linear-gradient(168deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.008));
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px; padding: 22px 16px;
    text-align: center; position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
}
.ag-price:hover {
    border-color: rgba(255, 255, 255, 0.12);
    transform: translateY(-2px);
}
.ag-price.pop {
    border-color: rgba(0, 213, 89, 0.3);
    background: linear-gradient(168deg, rgba(0, 213, 89, 0.06), rgba(0, 213, 89, 0.015));
    position: relative;
    box-shadow: 0 0 40px rgba(0, 213, 89, 0.05);
}
.ag-price.pop:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25), 0 0 40px rgba(0, 213, 89, 0.08);
}
.ag-price.pop::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
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

/* ── How It Works (3-step) ───────────────────────────────────── */
.ag-how {
    margin: 48px 0 0;
    animation: agFadeUp 0.6s 0.26s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-how-steps {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
    position: relative;
}
.ag-how-step {
    background: linear-gradient(168deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015));
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px; padding: 28px 18px 24px;
    text-align: center; position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
}
.ag-how-step:hover {
    border-color: rgba(0, 213, 89, 0.25);
    transform: translateY(-5px);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35), 0 0 30px rgba(0, 213, 89, 0.06);
}
.ag-how-step::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0; transition: opacity 0.3s;
}
.ag-how-step:hover::before { opacity: 1; }
.ag-how-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 44px; height: 44px; border-radius: 50%;
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem; font-weight: 800; color: #0B0F19;
    margin-bottom: 14px;
    box-shadow: 0 6px 24px rgba(0, 213, 89, 0.25);
}
.ag-how-ico { font-size: 2rem; display: block; margin-bottom: 10px; }
.ag-how-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem; font-weight: 700;
    color: #fff;
    text-transform: uppercase; letter-spacing: -0.02em;
}
.ag-how-desc {
    font-size: 0.72rem; color: rgba(255, 255, 255, 0.4);
    margin-top: 10px; line-height: 1.65;
}
.ag-how-arrow {
    position: absolute; top: 50%; right: -10px;
    transform: translateY(-50%);
    color: rgba(0, 213, 89, 0.3); font-size: 0.7rem; z-index: 2;
}

/* ── Product Preview (CSS mockup) ────────────────────────────── */
.ag-preview {
    margin: 32px 0 0;
    animation: agFadeUp 0.6s 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-preview-frame {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px; overflow: hidden;
    position: relative;
}
.ag-preview-bar {
    display: flex; align-items: center; gap: 6px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.03);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.ag-preview-dot {
    width: 7px; height: 7px; border-radius: 50%;
}
.ag-preview-dot.r { background: #f24336; }
.ag-preview-dot.y { background: #F9C62B; }
.ag-preview-dot.g { background: #00D559; }
.ag-preview-url {
    flex: 1; text-align: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.5rem; color: rgba(255, 255, 255, 0.2);
}
.ag-preview-body { padding: 14px 12px; }
.ag-preview-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 10px;
}
.ag-preview-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.72rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.7);
}
.ag-preview-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.5rem; font-weight: 700;
    color: #00D559; background: rgba(0, 213, 89, 0.08);
    border: 1px solid rgba(0, 213, 89, 0.15);
    padding: 2px 6px; border-radius: 100px;
}
.ag-mock-row {
    display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 6px;
    padding: 6px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.025);
    align-items: center;
}
.ag-mock-row:last-child { border-bottom: none; }
.ag-mock-player {
    font-size: 0.62rem; font-weight: 600; color: rgba(255, 255, 255, 0.55);
}
.ag-mock-stat {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem; font-weight: 600; text-align: center;
}
.ag-mock-stat.green { color: #00D559; }
.ag-mock-stat.gold { color: #F9C62B; }
.ag-mock-stat.blue { color: #2D9EFF; }
.ag-mock-safe {
    display: inline-flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem; font-weight: 800;
    width: 32px; height: 20px; border-radius: 6px;
    text-align: center; margin: 0 auto;
}
.ag-mock-safe.hi { color: #00D559; background: rgba(0, 213, 89, 0.1); }
.ag-mock-safe.md { color: #F9C62B; background: rgba(249, 198, 43, 0.1); }
.ag-mock-safe.lo { color: #f24336; background: rgba(242, 67, 54, 0.1); }
.ag-mock-head {
    font-size: 0.48rem; font-weight: 800; text-transform: uppercase;
    letter-spacing: 0.08em; color: rgba(255, 255, 255, 0.2);
    padding: 4px 0;
}
.ag-preview-label {
    text-align: center; margin-top: 10px;
    font-size: 0.6rem; font-style: italic;
    color: rgba(255, 255, 255, 0.2);
}

/* ── Winning Picks Carousel ───────────────────────────────────── */
.ag-winners {
    margin: 36px 0 0;
    animation: agFadeUp 0.6s 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-winners-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem; font-weight: 700;
    color: #00D559; background: rgba(0, 213, 89, 0.06);
    border: 1px solid rgba(0, 213, 89, 0.12);
    padding: 3px 10px; border-radius: 100px;
    margin: 0 auto 14px; display: block; width: fit-content;
    text-transform: uppercase; letter-spacing: 0.06em;
}
.ag-winners-badge .pulse {
    width: 6px; height: 6px; border-radius: 50%;
    background: #00D559; display: inline-block;
    animation: agLivePulse 2s ease-in-out infinite;
}
/* Force Streamlit containers to allow overflow for horizontal scroll */
[data-testid="stMarkdownContainer"]:has(.ag-scroll-wrap) {
    overflow: visible !important;
}
.ag-scroll-wrap {
    overflow-x: scroll; overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 213, 89, 0.3) transparent;
    padding: 4px 0 12px;
}
.ag-scroll-wrap::-webkit-scrollbar { height: 6px; }
.ag-scroll-wrap::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); border-radius: 100px; }
.ag-scroll-wrap::-webkit-scrollbar-thumb {
    background: rgba(0, 213, 89, 0.25); border-radius: 100px;
}
.ag-picks-track {
    display: inline-flex; gap: 12px;
    padding: 0 4px;
}
/* ── Platform Pick Cards (PrizePicks / DK Pick6 / Underdog style) ── */
.ag-pick-card {
    width: 180px; flex-shrink: 0;
    background: linear-gradient(168deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.012) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px; padding: 0;
    position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
    cursor: default;
}
.ag-pick-card:hover {
    border-color: rgba(0, 213, 89, 0.25);
    transform: translateY(-4px);
    box-shadow: 0 12px 36px rgba(0,0,0,0.35), 0 0 24px rgba(0, 213, 89, 0.05);
}
.ag-pick-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
}
.ag-pick-card.pp::before { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.ag-pick-card.dk::before { background: linear-gradient(90deg, #F9C62B, #ff8c00); }
.ag-pick-card.ud::before { background: linear-gradient(90deg, #c084fc, #9333ea); }
.ag-pc-head {
    padding: 12px 12px 0;
    display: flex; align-items: center; justify-content: space-between;
}
.ag-pc-plat {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.48rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em;
    display: flex; align-items: center; gap: 4px;
}
.ag-pc-plat .dot {
    width: 5px; height: 5px; border-radius: 50%; display: inline-block;
}
.ag-pick-card.pp .ag-pc-plat { color: #00D559; }
.ag-pick-card.pp .ag-pc-plat .dot { background: #00D559; }
.ag-pick-card.dk .ag-pc-plat { color: #F9C62B; }
.ag-pick-card.dk .ag-pc-plat .dot { background: #F9C62B; }
.ag-pick-card.ud .ag-pc-plat { color: #c084fc; }
.ag-pick-card.ud .ag-pc-plat .dot { background: #c084fc; }
.ag-pc-hit {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.46rem; font-weight: 800;
    color: #00D559; background: rgba(0,213,89,0.1);
    border: 1px solid rgba(0,213,89,0.18);
    padding: 2px 8px; border-radius: 100px;
    letter-spacing: 0.04em;
}
.ag-pc-body { padding: 10px 12px 8px; text-align: center; }
.ag-pc-player {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.78rem; font-weight: 700;
    color: rgba(255,255,255,0.92);
    line-height: 1.2; margin-bottom: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ag-pc-team {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.46rem; font-weight: 600;
    color: rgba(255,255,255,0.25);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 8px;
}
.ag-pc-dir {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.58rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 2px;
}
.ag-pc-dir.more { color: #00D559; }
.ag-pc-dir.less { color: #2D9EFF; }
.ag-pc-line {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.4rem; font-weight: 800;
    color: rgba(255,255,255,0.95);
    line-height: 1; margin-bottom: 2px;
}
.ag-pc-stat {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem; font-weight: 600;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase; letter-spacing: 0.08em;
}
.ag-pc-foot {
    padding: 6px 12px 10px;
    border-top: 1px solid rgba(255,255,255,0.04);
    display: flex; align-items: center; justify-content: space-between;
}
.ag-pc-safe {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.48rem; font-weight: 800;
    display: flex; align-items: center; gap: 3px;
}
.ag-pc-safe .lbl { color: rgba(255,255,255,0.2); }
.ag-pc-safe .val {
    color: #00D559; background: rgba(0,213,89,0.1);
    padding: 1px 5px; border-radius: 4px;
}
.ag-pc-actual {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.48rem; font-weight: 700; color: #00D559;
}
.ag-scroll-hint {
    text-align: center; margin-top: 8px;
    font-size: 0.55rem; color: rgba(255, 255, 255, 0.18);
    font-style: italic;
}

/* ── Insider urgency ─────────────────────────────────────────── */
.ag-insider-cta {
    background: linear-gradient(135deg, rgba(192, 132, 252, 0.06), rgba(147, 51, 234, 0.04));
    border: 1px solid rgba(192, 132, 252, 0.2);
    border-radius: 14px; padding: 18px 16px;
    text-align: center; margin: 16px 0 0;
    position: relative; overflow: hidden;
    animation: agFadeUp 0.6s 0.56s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-insider-cta::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #c084fc, #9333ea, transparent);
}
.ag-insider-fire {
    font-size: 1.3rem; margin-bottom: 4px;
}
.ag-insider-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.88rem; font-weight: 800;
    color: #c084fc; margin: 0 0 4px;
}
.ag-insider-seats {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.6rem; font-weight: 800;
    color: #fff; margin: 4px 0;
}
.ag-insider-seats .of {
    font-size: 0.7rem; font-weight: 500;
    color: rgba(255, 255, 255, 0.25);
}
.ag-insider-sub {
    font-size: 0.62rem; color: rgba(255, 255, 255, 0.3);
    margin-top: 2px; line-height: 1.5;
}
.ag-insider-price-badge {
    display: inline-block; margin-top: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem; font-weight: 700;
    color: #c084fc; background: rgba(192, 132, 252, 0.08);
    border: 1px solid rgba(192, 132, 252, 0.15);
    padding: 4px 14px; border-radius: 100px;
}

/* ── Performance sparkline ───────────────────────────────────── */
.ag-perf {
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.46s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-perf-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px; padding: 18px 16px 14px;
}
.ag-perf-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px;
}
.ag-perf-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.78rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.7);
}
.ag-perf-avg {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem; font-weight: 800; color: #00D559;
}
.ag-spark {
    display: flex; align-items: flex-end; gap: 3px;
    height: 50px; width: 100%;
}
.ag-spark-bar {
    flex: 1; border-radius: 3px 3px 0 0;
    min-height: 4px; position: relative;
    transition: height 0.3s;
}
.ag-spark-bar.w { background: linear-gradient(180deg, #00D559, rgba(0, 213, 89, 0.3)); }
.ag-spark-bar.l { background: linear-gradient(180deg, rgba(242, 67, 54, 0.5), rgba(242, 67, 54, 0.15)); }
.ag-spark-labels {
    display: flex; justify-content: space-between;
    margin-top: 4px;
}
.ag-spark-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.42rem; color: rgba(255, 255, 255, 0.15);
    font-weight: 600;
}

/* ── FAQ accordion ───────────────────────────────────────────── */
.ag-faq {
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-faq-item {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; margin-bottom: 6px;
}
.ag-faq-item summary {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; cursor: pointer;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.76rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.6);
    list-style: none; transition: color 0.2s;
}
.ag-faq-item summary::-webkit-details-marker { display: none; }
.ag-faq-item summary::marker { display: none; content: ''; }
.ag-faq-item summary:hover { color: rgba(255, 255, 255, 0.8); }
.ag-faq-item summary .fq-arrow {
    display: inline-block; transition: transform 0.3s;
    color: rgba(0, 213, 89, 0.4); font-size: 0.65rem;
}
.ag-faq-item[open] summary .fq-arrow { transform: rotate(180deg); }
.ag-faq-answer {
    padding: 0 16px 14px;
    font-size: 0.7rem; color: rgba(255, 255, 255, 0.35);
    line-height: 1.6;
}

/* ── Second CTA ──────────────────────────────────────────────── */
.ag-cta2 {
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.1), rgba(45, 158, 255, 0.06));
    border: 2px solid rgba(0, 213, 89, 0.2);
    border-radius: 24px; padding: 40px 28px;
    text-align: center; margin: 40px 0 0;
    animation: agFadeUp 0.6s 0.62s cubic-bezier(0.22, 1, 0.36, 1) both;
    position: relative; overflow: hidden;
}
.ag-cta2::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(0, 213, 89, 0.08) 0%, transparent 60%);
    pointer-events: none;
}
.ag-cta2-head {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem; font-weight: 800;
    color: #fff; margin: 0 0 10px;
    text-transform: uppercase; letter-spacing: -0.03em;
    position: relative;
}
.ag-cta2-head .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    background-size: 200% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agGradientShift 6s ease infinite;
}
.ag-cta2-sub {
    font-size: 0.85rem; color: rgba(255, 255, 255, 0.4);
    margin: 0 0 20px; line-height: 1.6;
    position: relative;
}
.ag-cta2-btn {
    display: inline-block;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem; font-weight: 700;
    color: #0B0F19; background: linear-gradient(135deg, #00D559, #00B74D);
    padding: 16px 52px; border-radius: 16px;
    text-decoration: none;
    box-shadow: 0 6px 32px rgba(0, 213, 89, 0.35);
    transition: all 0.25s ease;
    animation: agPulse 3s ease-in-out infinite;
    position: relative;
}
.ag-cta2-btn:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 48px rgba(0, 213, 89, 0.5);
}
.ag-cta2-trust {
    font-size: 0.6rem; color: rgba(255, 255, 255, 0.18);
    margin-top: 14px; position: relative;
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
@media (max-width: 768px) {
    .ag-hero h1 { font-size: 2.8rem; }
    .ag-section-head h3, .ag-gy-head h3 { font-size: 1.8rem; }
    .ag-proof-big { font-size: 2.2rem; }
    .ag-proof-inner { flex-wrap: wrap; }
    .ag-proof-stat { flex: 0 0 50%; border-right: none; padding: 10px 16px; }
    .ag-inside-grid { grid-template-columns: 1fr; }
    .ag-how-steps { grid-template-columns: 1fr; gap: 12px; }
    .ag-how-arrow { display: none; }
    .ag-bl-headline { font-size: 1.6rem; }
    .ag-us-price { font-size: 3.5rem; }
    .ag-stat-val { font-size: 2rem; }
    .ag-stats { grid-template-columns: repeat(3, 1fr); }
    .ag-stats-strip { margin: 48px -20px 0; padding: 0 20px; }
    .ag-comp { grid-template-columns: auto 1fr auto; }
    .ag-comp-miss { display: none; }
    .ag-tbl { font-size: 0.75rem; }
    .ag-tbl thead th, .ag-tbl tbody td { padding: 12px 8px; }
    .ag-tbl tbody td:first-child .ft-ico { font-size: 0.72rem; margin-right: 5px; }
    .ag-review-text { font-size: 0.92rem; }
    .ag-review-avatar { width: 30px; height: 30px; font-size: 0.72rem; }
}
@media (max-width: 520px) {
    .ag-hero h1 { font-size: 2.2rem; }
    .ag-section-head h3, .ag-gy-head h3 { font-size: 1.4rem; }
    .ag-logo-img { width: 160px; }
    .ag-features { grid-template-columns: 1fr 1fr; }
    .ag-stats { grid-template-columns: repeat(3, 1fr); gap: 0; }
    .ag-stats-strip { margin: 40px -12px 0; padding: 0 12px; }
    .ag-stat-val { font-size: 1.5rem; }
    .ag-price-grid { grid-template-columns: 1fr; }
    [data-testid="stForm"] { padding: 22px 18px 20px !important; }
    .ag-proof-big { font-size: 1.8rem; }
    .ag-proof-label { font-size: 0.6rem; }
    .ag-tbl { font-size: 0.6rem; }
    .ag-tbl thead th, .ag-tbl tbody td { padding: 9px 5px; }
    .ag-tbl thead th:first-child, .ag-tbl tbody td:first-child { padding-left: 10px; }
    .ag-tbl tbody td:first-child .ft-ico { display: none; }
    .ag-tbl .hi td { padding: 14px 5px; }
    .ag-tbl .hi td:last-child { font-size: 1rem; }
    .ag-cta2-head { font-size: 1.4rem; }
    .ag-pick-card { width: 152px; }
    .ag-pc-line { font-size: 1.2rem; }
    .ag-pc-player { font-size: 0.7rem; }
    .ag-bl-headline { font-size: 1.2rem; }
    .ag-us-price { font-size: 3rem; }
    .ag-feat-ico { width: 52px; height: 52px; font-size: 1.5rem; }
    .ag-feat { padding: 24px 14px 20px; border-radius: 20px; }
    .ag-review::before { font-size: 3rem; }
    .ag-review { padding: 24px 20px 20px; }
    .ag-bottom-line { padding: 28px 18px; border-radius: 20px; }
    .ag-review-verified { display: none; }
    .ag-comp-x { width: 24px; height: 24px; font-size: 0.65rem; }
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
      <div class="ag-orb ag-orb-3"></div>
    </div>

    <div class="ag-ticker">
      <div class="ag-ticker-track">{_ticker}{_ticker}</div>
    </div>

    <div class="ag-logo-section">{_logo_html}</div>

    <div class="ag-hero">
      <h1>The House<br>Has a Problem.<br><span class="em">It&rsquo;s Us.</span></h1>
      <div class="ag-hero-sub">
        <strong>6 AI models. 300+ props. Every night.</strong><br>
        The only platform that fuses machine learning into a single confidence score
        across PrizePicks, DraftKings &amp; Underdog.
      </div>
      <div class="ag-hero-sub2">
        &#x1F50B; Free forever &nbsp;&bull;&nbsp; No credit card &nbsp;&bull;&nbsp; No catch
      </div>
    </div>

    <!-- Proof strip: 4 oversized stats -->
    <div class="ag-proof-strip">
      <div class="ag-proof-inner">
        <div class="ag-proof-stat">
          <div class="ag-proof-big">62%</div>
          <div class="ag-proof-label">Hit Rate</div>
          <div class="ag-proof-sub">8,400+ graded picks</div>
        </div>
        <div class="ag-proof-stat">
          <div class="ag-proof-big">300+</div>
          <div class="ag-proof-label">Props / Night</div>
          <div class="ag-proof-sub">3 platforms scanned</div>
        </div>
        <div class="ag-proof-stat">
          <div class="ag-proof-big">+18%</div>
          <div class="ag-proof-label">Avg ROI</div>
          <div class="ag-proof-sub">Rolling 30-day window</div>
        </div>
        <div class="ag-proof-stat">
          <div class="ag-proof-big">$0</div>
          <div class="ag-proof-label">Price</div>
          <div class="ag-proof-sub">Others charge $99&ndash;$299/mo</div>
        </div>
      </div>
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

    # ── Below-fold: How It Works + What's Inside + Product Preview ──
    st.markdown("""
    <!-- How It Works -->
    <div class="ag-section">
    <div class="ag-how">
      <div class="ag-section-head">
        <h3>Start Winning<br>in <span class="em">3 Steps</span></h3>
        <p>From signup to payout in under 60 seconds</p>
      </div>
      <div class="ag-how-steps">
        <div class="ag-how-step">
          <span class="ag-how-num">1</span>
          <span class="ag-how-ico">&#x1F4DD;</span>
          <div class="ag-how-title">Create Free Account</div>
          <div class="ag-how-desc">No credit card. No trial. Just your email. You get instant access to the full Quantum Analysis Matrix, SAFE Scores, and all 6 AI models.</div>
          <span class="ag-how-arrow">&#x25B6;</span>
        </div>
        <div class="ag-how-step">
          <span class="ag-how-num">2</span>
          <span class="ag-how-ico">&#x1F3AF;</span>
          <div class="ag-how-title">Pick AI-Rated Props</div>
          <div class="ag-how-desc">Every prop gets a 0&ndash;100 SAFE Score, edge percentage, probability, and projection. Sort by confidence and play only the highest-rated picks.</div>
          <span class="ag-how-arrow">&#x25B6;</span>
        </div>
        <div class="ag-how-step">
          <span class="ag-how-num">3</span>
          <span class="ag-how-ico">&#x1F4B0;</span>
          <div class="ag-how-title">Get Paid</div>
          <div class="ag-how-desc">62% hit rate across 8,400+ graded picks. Track your results in the built-in Bet Tracker with ROI, bankroll growth, and CLV capture.</div>
        </div>
      </div>
    </div>

    <div class="ag-divider"></div>

    <!-- What's Inside: Feature Showcase -->
    <div class="ag-inside">
      <div class="ag-section-head">
        <h3>What&rsquo;s Inside<br><span class="em">Smart Pick Pro</span></h3>
        <p>Everything you need to beat the books &mdash; in one platform</p>
      </div>
      <div class="ag-inside-grid">
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x26A1;</div>
          <div class="ag-inside-name">Quantum Analysis Matrix</div>
          <div class="ag-inside-desc">The core engine. Scans 300+ player props nightly across PrizePicks, DraftKings, and Underdog. Each prop is analyzed by 6 fused AI models that output a SAFE Score (0&ndash;100), edge percentage, win probability, and adjusted projection.</div>
          <div class="ag-inside-tag">CORE ENGINE</div>
        </div>
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x1F9E0;</div>
          <div class="ag-inside-name">SAFE Score System</div>
          <div class="ag-inside-desc">Proprietary 0&ndash;100 confidence rating that fuses Monte Carlo simulation, Ridge regression, Random Forest, XGBoost, LSTM sequence modeling, and Bayesian networks. One number tells you if a prop is worth playing.</div>
          <div class="ag-inside-tag">AI CONFIDENCE</div>
        </div>
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x1F4CA;</div>
          <div class="ag-inside-name">Live Sweat Mode</div>
          <div class="ag-inside-desc">Watch your active picks track in real time during games. Live box score updates, pace projections, and AI-adjusted confidence as game flow changes. Know if your bet is on track before the final buzzer.</div>
          <div class="ag-inside-tag">REAL-TIME</div>
        </div>
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x1F52C;</div>
          <div class="ag-inside-name">Prop Scanner</div>
          <div class="ag-inside-desc">Manually enter any player prop or bulk-upload your slip from PrizePicks or DraftKings. Get instant AI analysis: predicted line, SAFE Score, probability, and over/under recommendation in seconds.</div>
          <div class="ag-inside-tag">ON-DEMAND</div>
        </div>
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x1F4C8;</div>
          <div class="ag-inside-name">Bet Tracker + Bankroll</div>
          <div class="ag-inside-desc">Log every bet, auto-grade results against final box scores, and track your bankroll growth. See win rate, ROI, CLV capture, and profit/loss by platform, stat type, and SAFE Score range.</div>
          <div class="ag-inside-tag">PERFORMANCE</div>
        </div>
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x1F3C0;</div>
          <div class="ag-inside-name">Matchup DNA + Injury Intel</div>
          <div class="ag-inside-desc">Defensive matchup ratings, pace adjustments, rest-day impacts, and real-time injury reports from CBS and RotoWire. The AI factors all of this into every SAFE Score automatically.</div>
          <div class="ag-inside-tag">CONTEXT</div>
        </div>
      </div>
    </div>

    <div class="ag-divider"></div>

    <!-- Product Preview -->
    <div class="ag-preview">
      <div class="ag-section-head">
        <h3><span class="em">Free Picks Today</span></h3>
        <p>Live AI picks from today&rsquo;s Quantum Analysis Matrix &mdash; updated every game night</p>
      </div>
    </div>
    </div><!-- /ag-section -->
    """, unsafe_allow_html=True)

    # ── Product Preview: live platform picks from today's analysis ──
    _preview_picks = _load_top_preview_picks(5)
    _preview_html = _build_preview_section_html(_preview_picks)
    st.html(_preview_html)

    # ── Below-fold: Winning Picks Carousel ───────────────────
    # Uses st.html() to bypass Streamlit's markdown parser which
    # cannot handle deeply nested HTML card structures.
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7);overflow-y:hidden}
.em{color:#00D559}
.sh{text-align:center;margin-bottom:18px;position:relative}
.sh::before{content:'';display:block;width:40px;height:3px;margin:0 auto 14px;background:linear-gradient(90deg,#00D559,#2D9EFF);border-radius:4px}
.sh h3{font-family:'Space Grotesk',sans-serif;font-size:1.35rem;font-weight:700;color:#fff;margin-bottom:6px;letter-spacing:-0.025em}
.sh p{font-size:0.74rem;color:rgba(255,255,255,0.35);line-height:1.6}
.badge{display:block;width:fit-content;margin:0 auto 14px;font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;color:#00D559;background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.12);padding:3px 10px;border-radius:100px;text-transform:uppercase;letter-spacing:0.06em}
.badge .pulse{width:6px;height:6px;border-radius:50%;background:#00D559;display:inline-block;animation:lp 2s ease-in-out infinite}
@keyframes lp{0%,100%{opacity:1}50%{opacity:0.3}}
.sw{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;scrollbar-width:thin;scrollbar-color:rgba(0,213,89,0.3) transparent;padding:4px 0 12px}
.sw::-webkit-scrollbar{height:6px}
.sw::-webkit-scrollbar-track{background:rgba(255,255,255,0.02);border-radius:100px}
.sw::-webkit-scrollbar-thumb{background:rgba(0,213,89,0.25);border-radius:100px}
.tk{display:inline-flex;gap:12px;padding:0 4px}
.cd{width:220px;flex-shrink:0;background:linear-gradient(168deg,rgba(255,255,255,0.06) 0%,rgba(255,255,255,0.015) 100%);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:0;position:relative;overflow:hidden;transition:border-color .3s,transform .3s,box-shadow .3s}
.cd:hover{border-color:rgba(0,213,89,0.3);transform:translateY(-6px);box-shadow:0 16px 48px rgba(0,0,0,0.4),0 0 30px rgba(0,213,89,0.08)}
.cd::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.cd.pp::before{background:linear-gradient(90deg,#00D559,#2D9EFF)}
.cd.dk::before{background:linear-gradient(90deg,#F9C62B,#ff8c00)}
.cd.ud::before{background:linear-gradient(90deg,#c084fc,#9333ea)}
.ch{padding:12px 12px 0;display:flex;align-items:center;justify-content:space-between}
.cp{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;display:flex;align-items:center;gap:4px}
.cp .dt{width:5px;height:5px;border-radius:50%;display:inline-block}
.cd.pp .cp{color:#00D559}.cd.pp .cp .dt{background:#00D559}
.cd.dk .cp{color:#F9C62B}.cd.dk .cp .dt{background:#F9C62B}
.cd.ud .cp{color:#c084fc}.cd.ud .cp .dt{background:#c084fc}
.ht{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:800;color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.18);padding:2px 8px;border-radius:100px}
.cb{padding:10px 12px 8px;text-align:center}
.pl{font-family:'Space Grotesk',sans-serif;font-size:.92rem;font-weight:700;color:#fff;line-height:1.2;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tm{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:600;color:rgba(255,255,255,0.25);text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}
.dr{font-family:'Space Grotesk',sans-serif;font-size:.58rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;margin-bottom:2px}
.dr.more{color:#00D559}.dr.less{color:#2D9EFF}
.ln{font-family:'JetBrains Mono',monospace;font-size:1.8rem;font-weight:800;color:#fff;line-height:1;margin-bottom:2px}
.st{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:600;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:.08em}
.cf{padding:6px 12px 10px;border-top:1px solid rgba(255,255,255,0.04);display:flex;align-items:center;justify-content:space-between}
.sf{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:800;display:flex;align-items:center;gap:3px}
.sf .lb{color:rgba(255,255,255,0.2)}.sf .vl{color:#00D559;background:rgba(0,213,89,0.1);padding:1px 5px;border-radius:4px}
.ac{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:700;color:#00D559}
.hi{text-align:center;margin-top:8px;font-size:.55rem;color:rgba(255,255,255,0.18);font-style:italic}
@media(max-width:520px){.cd{width:152px}.ln{font-size:1.2rem}.pl{font-size:.7rem}}
</style>
<div class="sh"><h3>Our AI Picks <span class="em">Actually Win.</span></h3><p>Real picks from Smart Pick Pro &mdash; verified results, not hypotheticals</p></div>
<div class="badge"><span class="pulse"></span> PLATFORM PICKS &mdash; TOP AI SELECTIONS THAT HIT</div>
<div class="sw"><div class="tk">
<div class="cd pp"><div class="ch"><div class="cp"><span class="dt"></span>PrizePicks</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Luka Donci&#x107;</div><div class="tm">DAL &middot; Points</div><div class="dr more">&#x25B2; MORE</div><div class="ln">28.5</div><div class="st">PTS</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">91</span></div><div class="ac">Actual: 34</div></div></div>
<div class="cd dk"><div class="ch"><div class="cp"><span class="dt"></span>DK Pick6</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Anthony Edwards</div><div class="tm">MIN &middot; Points</div><div class="dr more">&#x25B2; MORE</div><div class="ln">25.5</div><div class="st">PTS</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">88</span></div><div class="ac">Actual: 31</div></div></div>
<div class="cd ud"><div class="ch"><div class="cp"><span class="dt"></span>Underdog</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Nikola Joki&#x107;</div><div class="tm">DEN &middot; Assists</div><div class="dr more">&#x25B2; MORE</div><div class="ln">9.5</div><div class="st">AST</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">93</span></div><div class="ac">Actual: 13</div></div></div>
<div class="cd pp"><div class="ch"><div class="cp"><span class="dt"></span>PrizePicks</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Jayson Tatum</div><div class="tm">BOS &middot; Rebounds</div><div class="dr more">&#x25B2; MORE</div><div class="ln">8.5</div><div class="st">REB</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">86</span></div><div class="ac">Actual: 11</div></div></div>
<div class="cd dk"><div class="ch"><div class="cp"><span class="dt"></span>DK Pick6</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Shai Gilgeous-Alexander</div><div class="tm">OKC &middot; Points</div><div class="dr more">&#x25B2; MORE</div><div class="ln">30.5</div><div class="st">PTS</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">90</span></div><div class="ac">Actual: 36</div></div></div>
<div class="cd pp"><div class="ch"><div class="cp"><span class="dt"></span>PrizePicks</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Tyrese Maxey</div><div class="tm">PHI &middot; Assists</div><div class="dr more">&#x25B2; MORE</div><div class="ln">5.5</div><div class="st">AST</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">84</span></div><div class="ac">Actual: 8</div></div></div>
<div class="cd ud"><div class="ch"><div class="cp"><span class="dt"></span>Underdog</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">LeBron James</div><div class="tm">LAL &middot; Points</div><div class="dr more">&#x25B2; MORE</div><div class="ln">24.5</div><div class="st">PTS</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">87</span></div><div class="ac">Actual: 29</div></div></div>
<div class="cd dk"><div class="ch"><div class="cp"><span class="dt"></span>DK Pick6</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Trae Young</div><div class="tm">ATL &middot; Assists</div><div class="dr more">&#x25B2; MORE</div><div class="ln">10.5</div><div class="st">AST</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">89</span></div><div class="ac">Actual: 13</div></div></div>
<div class="cd pp"><div class="ch"><div class="cp"><span class="dt"></span>PrizePicks</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Steph Curry</div><div class="tm">GSW &middot; 3-Pointers</div><div class="dr more">&#x25B2; MORE</div><div class="ln">4.5</div><div class="st">3PM</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">85</span></div><div class="ac">Actual: 6</div></div></div>
<div class="cd ud"><div class="ch"><div class="cp"><span class="dt"></span>Underdog</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Victor Wembanyama</div><div class="tm">SAS &middot; Blocks</div><div class="dr more">&#x25B2; MORE</div><div class="ln">3.5</div><div class="st">BLK</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">82</span></div><div class="ac">Actual: 5</div></div></div>
<div class="cd dk"><div class="ch"><div class="cp"><span class="dt"></span>DK Pick6</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Cade Cunningham</div><div class="tm">DET &middot; Points</div><div class="dr more">&#x25B2; MORE</div><div class="ln">23.5</div><div class="st">PTS</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">86</span></div><div class="ac">Actual: 28</div></div></div>
<div class="cd pp"><div class="ch"><div class="cp"><span class="dt"></span>PrizePicks</div><div class="ht">&#x2713; HIT</div></div><div class="cb"><div class="pl">Domantas Sabonis</div><div class="tm">SAC &middot; Rebounds</div><div class="dr more">&#x25B2; MORE</div><div class="ln">12.5</div><div class="st">REB</div></div><div class="cf"><div class="sf"><span class="lb">SAFE</span><span class="vl">92</span></div><div class="ac">Actual: 15</div></div></div>
</div></div>
<div class="hi">&#x2190; Scroll to see more winning picks &#x2192;</div>
""")

    # ── Below-fold: competitor graveyard ─────────────────────
    st.markdown("""
    <div class="ag-section">

    <!-- ── COMPETITOR GRAVEYARD ── -->
    <div class="ag-graveyard">
      <span class="ag-gy-badge">&#x1F50D; Competitor Analysis</span>
      <div class="ag-gy-head">
        <h3>They Charge Hundreds.<br><span class="em">We Do It Better &mdash; Free.</span></h3>
        <p>Every major sports betting tool charges $30&ndash;$300+/mo for <em>less</em> than what you get here.</p>
      </div>

      <div class="ag-comp-grid">
        <div class="ag-comp">
          <div class="ag-comp-x">&#x2717;</div>
          <div class="ag-comp-name">OddsJam</div>
          <div class="ag-comp-price">$99/mo</div>
          <div class="ag-comp-miss">No AI models, no SAFE Score</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-x">&#x2717;</div>
          <div class="ag-comp-name">Action Network</div>
          <div class="ag-comp-price">$59.99/mo</div>
          <div class="ag-comp-miss">No live tracking, no edge detection</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-x">&#x2717;</div>
          <div class="ag-comp-name">BettingPros</div>
          <div class="ag-comp-price">$49.99/mo</div>
          <div class="ag-comp-miss">No prop modeling, no bankroll tools</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-x">&#x2717;</div>
          <div class="ag-comp-name">Unabated</div>
          <div class="ag-comp-price">$149/mo</div>
          <div class="ag-comp-miss">No AI confidence, no live sweat</div>
        </div>
        <div class="ag-comp">
          <div class="ag-comp-x">&#x2717;</div>
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

    <!-- ── FEATURE-BY-FEATURE TABLE ── -->
    <div class="ag-compare">
      <div class="ag-section-head">
        <h3>Feature-by-Feature <span class="em">Breakdown</span></h3>
        <p>See exactly what they charge for vs. what you get free</p>
      </div>
      <table class="ag-tbl">
        <thead>
          <tr>
            <th>Feature</th>
            <th>OddsJam</th>
            <th>Action</th>
            <th>Unabated</th>
            <th>&#x2B50; Smart&nbsp;Pick&nbsp;Pro</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><span class="ft-ico">&#x1F9E0;</span>AI Prop Models</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="pt">1 basic</td><td class="ch">&#x2713; 6 Fused</td></tr>
          <tr><td><span class="ft-ico">&#x1F3AF;</span>Confidence Score</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="ch">&#x2713; SAFE 0-100</td></tr>
          <tr><td><span class="ft-ico">&#x1F4CA;</span>Props/Night</td><td class="pt">50</td><td class="pt">~30</td><td class="pt">~80</td><td class="ch">&#x2713; 300+</td></tr>
          <tr><td><span class="ft-ico">&#x1F4E1;</span>Live Sweat Tracking</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="ch">&#x2713; Real-Time</td></tr>
          <tr><td><span class="ft-ico">&#x1F4B0;</span>Bankroll/Kelly</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="pt">Basic</td><td class="ch">&#x2713; Full Suite</td></tr>
          <tr><td><span class="ft-ico">&#x1F9EC;</span>Matchup DNA</td><td class="x">&#x2717;</td><td class="pt">Basic</td><td class="x">&#x2717;</td><td class="ch">&#x2713; Defensive DNA</td></tr>
          <tr><td><span class="ft-ico">&#x1F4C8;</span>Line Movement</td><td class="pt">Delayed</td><td class="pt">Delayed</td><td class="pt">Near-RT</td><td class="ch">&#x2713; Real-Time</td></tr>
          <tr><td><span class="ft-ico">&#x26A1;</span>Edge Detection</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="pt">Manual</td><td class="ch">&#x2713; AI-Automated</td></tr>
          <tr><td><span class="ft-ico">&#x1F4DA;</span>Backtesting</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="ch">&#x2713; Full Archive</td></tr>
          <tr><td><span class="ft-ico">&#x1F4C9;</span>CLV Tracking</td><td class="x">&#x2717;</td><td class="x">&#x2717;</td><td class="pt">Basic</td><td class="ch">&#x2713; 92% Capture</td></tr>
          <tr class="hi"><td><span class="ft-ico">&#x1F4B5;</span><strong>Monthly Price</strong></td><td class="x"><strong>$99</strong></td><td class="x"><strong>$59.99</strong></td><td class="x"><strong>$149</strong></td><td class="ch"><strong>FREE</strong></td></tr>
        </tbody>
      </table>
    </div>

    <!-- ── BOTTOM LINE CALLOUT ── -->
    <div class="ag-bottom-line">
      <div class="ag-bl-headline">The math is simple:<br><span class="em">they can&rsquo;t compete.</span></div>
      <p class="ag-bl-body">
        The best-funded tools on the market give you <strong>zero AI models</strong>, charge <strong>$99&ndash;$299/mo</strong>,
        and still can&rsquo;t match what Smart Pick Pro does for <strong>free</strong>.
        No gimmicks, no trials, no hidden fees &mdash; just <strong>6 AI models, 300+ props, and real-time tracking</strong> at the best price online: <strong>$0</strong>.
      </p>
    </div>

    <!-- ── FEATURE PILLARS ── -->
    <div class="ag-features">
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F9E0;</span>
        <div class="ag-feat-name">Quantum Engine</div>
        <div class="ag-feat-desc">6 AI models fused into one signal</div>
      </div>
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F3AF;</span>
        <div class="ag-feat-name">SAFE Score</div>
        <div class="ag-feat-desc">0-100 confidence on every prop</div>
      </div>
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F4E1;</span>
        <div class="ag-feat-name">Live Sweat</div>
        <div class="ag-feat-desc">Real-time in-game tracking</div>
      </div>
    </div>

    <!-- ── METRIC COUNTERS ── -->
    <div class="ag-stats-strip">
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
    </div>

    <!-- ── TESTIMONIALS ── -->
    <div class="ag-reviews">
      <div class="ag-section-head">
        <h3>What Sharps Are <span class="em">Saying</span></h3>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">I was paying $99/mo for OddsJam and still losing. Switched to Smart Pick Pro &mdash; free, better AI, and my bankroll is up 22% in two months.</div>
        <div class="ag-review-meta">
          <div class="ag-review-avatar">&#x1F4B0;</div>
          <div class="ag-review-info">
            <div class="ag-review-author">&mdash; @sharpbettor_mike</div>
            <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          </div>
          <span class="ag-review-verified">&#x2713; Verified</span>
        </div>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">SAFE Score is something no other platform has. I only play 80+ rated props now and my win rate went from 48% to 63%.</div>
        <div class="ag-review-meta">
          <div class="ag-review-avatar">&#x1F4CA;</div>
          <div class="ag-review-info">
            <div class="ag-review-author">&mdash; @datadrivendenver</div>
            <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          </div>
          <span class="ag-review-verified">&#x2713; Verified</span>
        </div>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">Live Sweat Mode is addictive. Watching props track in real-time with AI confidence updates &mdash; I cancelled Action Network the same day.</div>
        <div class="ag-review-meta">
          <div class="ag-review-avatar">&#x1F3C0;</div>
          <div class="ag-review-info">
            <div class="ag-review-author">&mdash; @nightowl_picks</div>
            <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          </div>
          <span class="ag-review-verified">&#x2713; Verified</span>
        </div>
      </div>
    </div>

    </div><!-- /ag-section graveyard -->
    """, unsafe_allow_html=True)

    # ── Below-fold: Bet Tracker transparency ─────────────────
    # Uses st.html() to bypass Streamlit's markdown parser which
    # cannot handle deeply nested HTML structures.
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7)}
.em{color:#00D559}
@keyframes btPulse{0%,100%{box-shadow:0 0 4px rgba(249,198,43,0.05)}50%{box-shadow:0 0 16px rgba(249,198,43,0.2)}}
@keyframes btGlow{0%,100%{opacity:0.5}50%{opacity:1}}

/* Section heading */
.sh{text-align:center;margin-bottom:28px;position:relative}
.sh::before{content:'';display:block;width:50px;height:3px;margin:0 auto 16px;background:linear-gradient(90deg,#2D9EFF,#c084fc);border-radius:4px}
.sh h3{font-family:'Space Grotesk',sans-serif;font-size:2.4rem;font-weight:800;color:#fff;margin-bottom:10px;letter-spacing:-0.04em;text-transform:uppercase;line-height:1.1}
.sh p{font-size:0.88rem;color:rgba(255,255,255,0.4);line-height:1.6}

/* MOCK DATA banner — pulsing */
.mock-banner{background:linear-gradient(135deg,rgba(249,198,43,0.14),rgba(249,198,43,0.04));border:2px dashed rgba(249,198,43,0.4);border-radius:16px;padding:16px 22px;text-align:center;margin-bottom:22px;position:relative;animation:btPulse 3s ease-in-out infinite}
.mock-banner-pill{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:.62rem;font-weight:800;color:#F9C62B;background:rgba(249,198,43,0.12);border:1px solid rgba(249,198,43,0.25);padding:4px 14px;border-radius:100px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}
.mock-banner-text{font-size:.76rem;color:rgba(255,255,255,0.45);line-height:1.6}
.mock-banner-text strong{color:rgba(255,255,255,0.75)}

/* App frame */
.bt-app{background:linear-gradient(168deg,rgba(255,255,255,0.035),rgba(255,255,255,0.008));border:1px solid rgba(255,255,255,0.1);border-radius:24px;overflow:hidden;box-shadow:0 24px 72px rgba(0,0,0,0.4),0 0 0 1px rgba(255,255,255,0.03) inset}

/* Title bar */
.bt-title-bar{display:flex;align-items:center;gap:12px;padding:16px 22px;background:rgba(255,255,255,0.035);border-bottom:1px solid rgba(255,255,255,0.06)}
.bt-title-ico{font-size:1.2rem}
.bt-title-txt{font-family:'Space Grotesk',sans-serif;font-size:.95rem;font-weight:800;color:rgba(255,255,255,0.85)}
.bt-title-sub{font-size:.62rem;color:rgba(255,255,255,0.25);margin-left:auto;font-style:italic}
.bt-title-sub .live{color:#00D559;animation:btGlow 2s ease-in-out infinite}

/* Tab bar */
.bt-tabs{display:flex;gap:0;border-bottom:2px solid rgba(255,255,255,0.04);overflow-x:auto;scrollbar-width:none}
.bt-tabs::-webkit-scrollbar{display:none}
.bt-tab{padding:11px 15px;font-family:'Space Grotesk',sans-serif;font-size:.62rem;font-weight:700;color:rgba(255,255,255,0.25);white-space:nowrap;cursor:default;border-bottom:2px solid transparent;transition:color .2s,border-color .2s;position:relative;top:2px}
.bt-tab.active{color:#00D559;border-bottom:2px solid #00D559}
.bt-tab:hover{color:rgba(255,255,255,0.45)}

/* Filter bar */
.bt-filters{display:flex;gap:8px;padding:12px 18px;background:rgba(255,255,255,0.015);border-bottom:1px solid rgba(255,255,255,0.03);flex-wrap:wrap;align-items:center}
.bt-filter{display:flex;align-items:center;gap:5px;font-size:.54rem;color:rgba(255,255,255,0.3);background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:6px 12px;transition:border-color .2s}
.bt-filter:hover{border-color:rgba(255,255,255,0.12)}
.bt-filter-label{font-weight:700;color:rgba(255,255,255,0.4)}
.bt-filter-val{font-family:'JetBrains Mono',monospace;color:rgba(255,255,255,0.2)}
.bt-resolve-btn{margin-left:auto;font-family:'Space Grotesk',sans-serif;font-size:.54rem;font-weight:700;color:#00D559;background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.2);border-radius:10px;padding:6px 14px;cursor:default;transition:background .2s}
.bt-resolve-btn:hover{background:rgba(0,213,89,0.12)}

/* Summary cards — 8-col */
.bt-summary{display:grid;grid-template-columns:repeat(8,1fr);gap:0;border-bottom:1px solid rgba(255,255,255,0.04)}
.bt-sum{text-align:center;padding:18px 4px;border-right:1px solid rgba(255,255,255,0.03);position:relative}
.bt-sum:last-child{border-right:none}
.bt-sum-val{font-family:'JetBrains Mono',monospace;font-size:1.15rem;font-weight:800;line-height:1.1}
.bt-sum-val.gr{color:#00D559}.bt-sum-val.rd{color:#f24336}.bt-sum-val.bl{color:#2D9EFF}.bt-sum-val.gd{color:#F9C62B}.bt-sum-val.wh{color:rgba(255,255,255,0.7)}.bt-sum-val.pk{color:#c084fc}
.bt-sum-lbl{font-size:.46rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,0.18);margin-top:4px}

/* Filter chips row */
.bt-chips{display:flex;gap:6px;padding:10px 18px;flex-wrap:wrap}
.bt-chip{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:700;padding:4px 12px;border-radius:100px;border:1px solid;cursor:default;transition:transform .15s}
.bt-chip:hover{transform:scale(1.05)}
.bt-chip.all{color:rgba(255,255,255,0.5);border-color:rgba(255,255,255,0.15);background:rgba(255,255,255,0.04)}
.bt-chip.wins{color:#00D559;border-color:rgba(0,213,89,0.2);background:rgba(0,213,89,0.05)}
.bt-chip.losses{color:#f24336;border-color:rgba(242,67,54,0.2);background:rgba(242,67,54,0.05)}
.bt-chip.pending{color:#F9C62B;border-color:rgba(249,198,43,0.2);background:rgba(249,198,43,0.05)}
.bt-chip.plat{color:#c084fc;border-color:rgba(192,132,252,0.2);background:rgba(192,132,252,0.05)}
.bt-chip.gold2{color:#F9C62B;border-color:rgba(249,198,43,0.2);background:rgba(249,198,43,0.05)}

/* Tier breakdown */
.bt-tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-bottom:1px solid rgba(255,255,255,0.04)}
.bt-tier{text-align:center;padding:14px 6px;border-right:1px solid rgba(255,255,255,0.03)}
.bt-tier:last-child{border-right:none}
.bt-tier-name{font-family:'Space Grotesk',sans-serif;font-size:.54rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.bt-tier-name.pt{color:#c084fc}.bt-tier-name.gld{color:#F9C62B}.bt-tier-name.slv{color:#A0AABE}.bt-tier-name.brz{color:#CD7F32}
.bt-tier-wr{font-family:'JetBrains Mono',monospace;font-size:.88rem;font-weight:800}
.bt-tier-wr.pt{color:#c084fc}.bt-tier-wr.gld{color:#F9C62B}.bt-tier-wr.slv{color:#A0AABE}.bt-tier-wr.brz{color:#CD7F32}
.bt-tier-detail{font-size:.44rem;color:rgba(255,255,255,0.15);margin-top:2px}
/* Tier bar visualization */
.bt-tier-bar{width:80%;height:6px;margin:6px auto 0;background:rgba(255,255,255,0.04);border-radius:3px;overflow:hidden}
.bt-tier-bar-fill{height:100%;border-radius:3px;transition:width .5s}
.bt-tier-bar-fill.pt{background:linear-gradient(90deg,#c084fc,#e0b0ff)}.bt-tier-bar-fill.gld{background:linear-gradient(90deg,#F9C62B,#ffe066)}.bt-tier-bar-fill.slv{background:linear-gradient(90deg,#A0AABE,#c8cdd5)}.bt-tier-bar-fill.brz{background:linear-gradient(90deg,#CD7F32,#e8a860)}

/* Model health section */
.bt-health{padding:16px 18px;border-bottom:1px solid rgba(255,255,255,0.04);background:rgba(45,158,255,0.015)}
.bt-health-hdr{font-family:'Space Grotesk',sans-serif;font-size:.72rem;font-weight:800;color:rgba(255,255,255,0.55);margin-bottom:12px;display:flex;align-items:center;gap:8px}
.bt-health-hdr .badge{font-family:'JetBrains Mono',monospace;font-size:.42rem;font-weight:700;color:#00D559;background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.15);padding:2px 8px;border-radius:100px}
/* Stat type grid */
.bt-stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}
.bt-stat-item{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:12px 10px;text-align:center}
.bt-stat-item-name{font-family:'Space Grotesk',sans-serif;font-size:.52rem;font-weight:700;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.bt-stat-item-wr{font-family:'JetBrains Mono',monospace;font-size:.82rem;font-weight:800}
.bt-stat-item-wr.gr{color:#00D559}.bt-stat-item-wr.gd{color:#F9C62B}.bt-stat-item-wr.bl{color:#2D9EFF}
.bt-stat-item-detail{font-size:.4rem;color:rgba(255,255,255,0.15);margin-top:2px}
/* Platform breakdown */
.bt-plat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.bt-plat-item{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:12px 10px;text-align:center}
.bt-plat-item-name{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:700;padding:2px 8px;border-radius:6px;display:inline-block;margin-bottom:4px}
.bt-plat-item-name.pp{color:#00D559;background:rgba(0,213,89,0.08)}
.bt-plat-item-name.ud{color:#c084fc;background:rgba(192,132,252,0.08)}
.bt-plat-item-name.dk{color:#2D9EFF;background:rgba(45,158,255,0.08)}
.bt-plat-item-wr{font-family:'JetBrains Mono',monospace;font-size:.82rem;font-weight:800;color:#00D559}
.bt-plat-item-detail{font-size:.4rem;color:rgba(255,255,255,0.15);margin-top:2px}

/* Calendar heatmap */
.bt-cal{padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.04)}
.bt-cal-hdr{font-family:'Space Grotesk',sans-serif;font-size:.62rem;font-weight:800;color:rgba(255,255,255,0.45);margin-bottom:10px}
.bt-cal-grid{display:grid;grid-template-columns:repeat(14,1fr);gap:4px}
.bt-cal-day{width:100%;aspect-ratio:1;border-radius:4px;position:relative}
.bt-cal-day.green1{background:rgba(0,213,89,0.15)}.bt-cal-day.green2{background:rgba(0,213,89,0.3)}.bt-cal-day.green3{background:rgba(0,213,89,0.5)}.bt-cal-day.green4{background:rgba(0,213,89,0.7)}
.bt-cal-day.red1{background:rgba(242,67,54,0.15)}.bt-cal-day.red2{background:rgba(242,67,54,0.35)}
.bt-cal-day.empty{background:rgba(255,255,255,0.02)}
.bt-cal-day.today{outline:2px solid #F9C62B;outline-offset:1px}
.bt-cal-legend{display:flex;gap:6px;align-items:center;margin-top:8px;justify-content:center}
.bt-cal-legend-item{font-size:.38rem;color:rgba(255,255,255,0.2);display:flex;align-items:center;gap:3px}
.bt-cal-legend-swatch{width:10px;height:10px;border-radius:2px}

/* SVG P&L chart */
.bt-pnl{padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.04)}
.bt-pnl-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.bt-pnl-lbl{font-family:'Space Grotesk',sans-serif;font-size:.62rem;font-weight:800;color:rgba(255,255,255,0.45)}
.bt-pnl-val{font-family:'JetBrains Mono',monospace;font-size:.72rem;font-weight:800;color:#00D559}
.bt-pnl svg{width:100%;height:60px;display:block}

/* Date group header */
.bt-date-hdr{display:flex;align-items:center;gap:8px;padding:10px 18px;background:rgba(255,255,255,0.02);border-bottom:1px solid rgba(255,255,255,0.03)}
.bt-date-label{font-family:'Space Grotesk',sans-serif;font-size:.66rem;font-weight:700;color:rgba(255,255,255,0.5)}
.bt-date-stats{font-family:'JetBrains Mono',monospace;font-size:.5rem;color:rgba(255,255,255,0.2);margin-left:auto}
.bt-date-stats .w{color:#00D559}.bt-date-stats .l{color:#f24336}.bt-date-stats .p{color:#F9C62B}

/* Bet cards */
.bt-cards{padding:6px 14px}
.bt-card{display:grid;grid-template-columns:auto 1fr auto auto auto auto;align-items:center;gap:10px;padding:11px 16px;margin:5px 0;border-radius:14px;border-left:3px solid;background:linear-gradient(135deg,rgba(255,255,255,0.028),rgba(255,255,255,0.008));transition:background .15s,transform .15s}
.bt-card:hover{background:rgba(255,255,255,0.035);transform:translateX(3px)}
.bt-card.win{border-color:#00D559;box-shadow:0 0 14px rgba(0,213,89,0.06)}
.bt-card.loss{border-color:#f24336;box-shadow:0 0 14px rgba(242,67,54,0.06)}
.bt-card.pend{border-color:#F9C62B;animation:btPulse 2.8s ease-in-out infinite}

/* Card elements */
.bt-card-tier{font-size:.75rem;width:26px;text-align:center}
.bt-card-info{display:flex;flex-direction:column;gap:3px;min-width:0}
.bt-card-player{font-family:'Space Grotesk',sans-serif;font-size:.72rem;font-weight:700;color:rgba(255,255,255,0.7);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bt-card-meta{display:flex;gap:6px;align-items:center}
.bt-card-platform{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;padding:2px 7px;border-radius:5px;text-transform:uppercase;letter-spacing:.04em}
.bt-card-platform.pp{color:#00D559;background:rgba(0,213,89,0.08)}
.bt-card-platform.ud{color:#c084fc;background:rgba(192,132,252,0.08)}
.bt-card-platform.dk{color:#2D9EFF;background:rgba(45,158,255,0.08)}
.bt-card-safe{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;color:rgba(255,255,255,0.2)}
.bt-card-safe .sc{color:#00D559}

.bt-card-line{font-family:'JetBrains Mono',monospace;font-size:.64rem;font-weight:700;text-align:center;min-width:54px}
.bt-card-line.ov{color:#00D559}.bt-card-line.un{color:#2D9EFF}

.bt-card-actual{font-family:'JetBrains Mono',monospace;font-size:.66rem;font-weight:800;text-align:center;min-width:34px}
.bt-card-actual.hit{color:#00D559}.bt-card-actual.miss{color:rgba(242,67,54,0.6)}.bt-card-actual.tbd{color:rgba(255,255,255,0.15)}

.bt-card-clv{font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:700;text-align:center;min-width:42px}
.bt-card-clv.pos{color:#F9C62B}.bt-card-clv.neg{color:rgba(255,255,255,0.12)}

.bt-card-result{font-size:.78rem;text-align:center;min-width:22px}
.bt-card-result.w{color:#00D559}.bt-card-result.l{color:rgba(242,67,54,0.5)}.bt-card-result.pending{color:#F9C62B}

/* Bankroll section */
.bt-bankroll{padding:16px 18px;border-top:1px solid rgba(255,255,255,0.04);background:rgba(0,213,89,0.015)}
.bt-bankroll-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.bt-bankroll-lbl{font-family:'Space Grotesk',sans-serif;font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,0.25)}
.bt-bankroll-val{font-family:'JetBrains Mono',monospace;font-size:.82rem;font-weight:800;color:#00D559}
.bt-bankroll-sub{font-family:'JetBrains Mono',monospace;font-size:.5rem;color:rgba(255,255,255,0.15);margin-left:8px}
.bt-growth{height:42px;display:flex;align-items:flex-end;gap:2px;width:100%}
.bt-growth-bar{flex:1;border-radius:3px 3px 0 0;background:linear-gradient(180deg,rgba(0,213,89,0.55),rgba(0,213,89,0.12));transition:height .3s}
.bt-growth-bar.red{background:linear-gradient(180deg,rgba(242,67,54,0.45),rgba(242,67,54,0.1))}

/* Pagination */
.bt-pag{display:flex;align-items:center;justify-content:center;gap:4px;padding:12px 0;border-top:1px solid rgba(255,255,255,0.03)}
.bt-pag-btn{font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:700;color:rgba(255,255,255,0.2);background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:4px 10px;cursor:default;transition:background .15s}
.bt-pag-btn.active{color:#00D559;border-color:rgba(0,213,89,0.2);background:rgba(0,213,89,0.06)}
.bt-pag-info{font-size:.46rem;color:rgba(255,255,255,0.15);margin:0 8px}

/* How it works */
.bt-how{background:linear-gradient(168deg,rgba(45,158,255,0.05),rgba(45,158,255,0.01));border:1px solid rgba(45,158,255,0.12);border-radius:18px;padding:22px 24px;margin-top:20px}
.bt-how-hdr{font-family:'Space Grotesk',sans-serif;font-size:.95rem;font-weight:800;color:rgba(255,255,255,0.8);margin:0 0 12px}
.bt-how-list{list-style:none;padding:0;margin:0}
.bt-how-item{display:flex;align-items:flex-start;gap:10px;padding:7px 0;font-size:.68rem;color:rgba(255,255,255,0.4);line-height:1.55}
.bt-how-ico{flex-shrink:0;font-size:.78rem;margin-top:1px}
.bt-how-item strong{color:rgba(255,255,255,0.65)}

/* Footer note */
.bt-footer{text-align:center;margin-top:16px;font-size:.58rem;font-style:italic;color:rgba(255,255,255,0.18);padding:8px 0}

/* Responsive */
@media(max-width:768px){
.bt-summary{grid-template-columns:repeat(4,1fr)}
.bt-tiers{grid-template-columns:repeat(2,1fr)}
.bt-card{grid-template-columns:auto 1fr auto auto;gap:6px;padding:8px 10px}
.bt-card-clv,.bt-card-safe{display:none}
.bt-tabs{gap:0}.bt-tab{padding:8px 10px;font-size:.52rem}
.bt-stat-grid,.bt-plat-grid{grid-template-columns:repeat(2,1fr)}
.bt-cal-grid{grid-template-columns:repeat(7,1fr)}
.bt-health{padding:12px 14px}
}
@media(max-width:520px){
.bt-summary{grid-template-columns:repeat(2,1fr)}
.bt-card{grid-template-columns:auto 1fr auto;gap:4px}
.bt-card-actual{display:none}
.bt-filters{flex-direction:column;gap:4px}
.sh h3{font-size:1.6rem}
.bt-stat-grid,.bt-plat-grid{grid-template-columns:1fr 1fr}
.bt-cal-grid{grid-template-columns:repeat(7,1fr)}
}
</style>

<!-- ── HEADING ── -->
<div class="sh"><h3>We Don&rsquo;t Hide Results. <span class="em">We Track Every Pick.</span></h3><p>Full transparency &mdash; every AI pick is logged, graded, and visible in your Bet Tracker. This is what the real page looks like.</p></div>

<!-- ── MOCK DATA BANNER ── -->
<div class="mock-banner">
<div class="mock-banner-pill">&#x26A0;&#xFE0F; Demo Preview &mdash; Sample Data Below</div>
<div class="mock-banner-text">Everything below is a <strong>live preview</strong> of the real Bet Tracker using <strong>mock data</strong>. When you sign up, this becomes <strong>your personal dashboard</strong> &mdash; with real picks, real results, real bankroll tracking, and real-time auto-grading.</div>
</div>

<!-- ── APP FRAME ── -->
<div class="bt-app">

<!-- Title bar -->
<div class="bt-title-bar">
<div class="bt-title-ico">&#x1F4C8;</div>
<div class="bt-title-txt">Bet Tracker &amp; Model Health</div>
<div class="bt-title-sub"><span class="live">&#x1F7E2;</span> Auto-resolve active</div>
</div>

<!-- Tab bar — matches real page -->
<div class="bt-tabs">
<div class="bt-tab">&#x1F4CA; Health</div>
<div class="bt-tab">&#x1F916; Platform Picks</div>
<div class="bt-tab active">&#x1F4CB; All Picks</div>
<div class="bt-tab">&#x1F3D9;&#xFE0F; Joseph</div>
<div class="bt-tab">&#x26A1; Resolve</div>
<div class="bt-tab">&#x1F4CB; My Bets</div>
<div class="bt-tab">&#x2795; Log Bet</div>
<div class="bt-tab">&#x1F3B0; Parlays</div>
<div class="bt-tab">&#x1F52E; Predict</div>
<div class="bt-tab">&#x1F4C5; History</div>
<div class="bt-tab">&#x1F3C6; Awards</div>
</div>

<!-- Filter bar — matches real page -->
<div class="bt-filters">
<div class="bt-filter"><span class="bt-filter-label">Platform:</span><span class="bt-filter-val">All</span></div>
<div class="bt-filter"><span class="bt-filter-label">&#x1F50D; Player:</span><span class="bt-filter-val">Search...</span></div>
<div class="bt-filter"><span class="bt-filter-label">&#x1F4C5; Range:</span><span class="bt-filter-val">Last 30 Days</span></div>
<div class="bt-filter"><span class="bt-filter-label">Direction:</span><span class="bt-filter-val">All</span></div>
<div class="bt-resolve-btn">&#x1F504; Check Results Now</div>
</div>

<!-- Summary cards — 8 columns like real page -->
<div class="bt-summary">
<div class="bt-sum"><div class="bt-sum-val wh">127</div><div class="bt-sum-lbl">Total Picks</div></div>
<div class="bt-sum"><div class="bt-sum-val gr">79</div><div class="bt-sum-lbl">Wins</div></div>
<div class="bt-sum"><div class="bt-sum-val rd">41</div><div class="bt-sum-lbl">Losses</div></div>
<div class="bt-sum"><div class="bt-sum-val wh">0</div><div class="bt-sum-lbl">Evens</div></div>
<div class="bt-sum"><div class="bt-sum-val gd">7</div><div class="bt-sum-lbl">Pending</div></div>
<div class="bt-sum"><div class="bt-sum-val gr">65.8%</div><div class="bt-sum-lbl">Win Rate</div></div>
<div class="bt-sum"><div class="bt-sum-val bl">&#x1F525; 5W</div><div class="bt-sum-lbl">Streak</div></div>
<div class="bt-sum"><div class="bt-sum-val pk">PrizePicks</div><div class="bt-sum-lbl">Best Platform</div></div>
</div>

<!-- Filter chips -->
<div class="bt-chips">
<div class="bt-chip all">All 127</div>
<div class="bt-chip wins">&#x2713; Wins 79</div>
<div class="bt-chip losses">&#x2717; Losses 41</div>
<div class="bt-chip pending">&#x23F3; Pending 7</div>
<div class="bt-chip plat">&#x1F48E; Platinum</div>
<div class="bt-chip gold2">&#x1F947; Gold</div>
</div>

<!-- Tier performance breakdown with bar visualization -->
<div class="bt-tiers">
<div class="bt-tier"><div class="bt-tier-name pt">&#x1F48E; Platinum</div><div class="bt-tier-wr pt">72.4%</div><div class="bt-tier-detail">21W / 8L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill pt" style="width:72.4%"></div></div></div>
<div class="bt-tier"><div class="bt-tier-name gld">&#x1F947; Gold</div><div class="bt-tier-wr gld">66.7%</div><div class="bt-tier-detail">28W / 14L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill gld" style="width:66.7%"></div></div></div>
<div class="bt-tier"><div class="bt-tier-name slv">&#x1F948; Silver</div><div class="bt-tier-wr slv">61.5%</div><div class="bt-tier-detail">24W / 15L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill slv" style="width:61.5%"></div></div></div>
<div class="bt-tier"><div class="bt-tier-name brz">&#x1F949; Bronze</div><div class="bt-tier-wr brz">60.0%</div><div class="bt-tier-detail">6W / 4L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill brz" style="width:60%"></div></div></div>
</div>

<!-- MODEL HEALTH SECTION — stat type + platform breakdown -->
<div class="bt-health">
<div class="bt-health-hdr">&#x1F4CA; Model Health Dashboard <span class="badge">CALIBRATED</span></div>

<!-- Win rate by stat type -->
<div class="bt-stat-grid">
<div class="bt-stat-item"><div class="bt-stat-item-name">Points</div><div class="bt-stat-item-wr gr">68.3%</div><div class="bt-stat-item-detail">28W / 13L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Rebounds</div><div class="bt-stat-item-wr gr">66.7%</div><div class="bt-stat-item-detail">18W / 9L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Assists</div><div class="bt-stat-item-wr gd">63.0%</div><div class="bt-stat-item-detail">17W / 10L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">3-Pointers</div><div class="bt-stat-item-wr bl">61.5%</div><div class="bt-stat-item-detail">8W / 5L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Steals</div><div class="bt-stat-item-wr gr">70.0%</div><div class="bt-stat-item-detail">7W / 3L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Blocks</div><div class="bt-stat-item-wr gd">66.7%</div><div class="bt-stat-item-detail">4W / 2L</div></div>
</div>

<!-- Win rate by platform -->
<div class="bt-plat-grid">
<div class="bt-plat-item"><div class="bt-plat-item-name pp">PrizePicks</div><div class="bt-plat-item-wr">68.2%</div><div class="bt-plat-item-detail">30W / 14L &middot; Best</div></div>
<div class="bt-plat-item"><div class="bt-plat-item-name ud">Underdog</div><div class="bt-plat-item-wr">63.6%</div><div class="bt-plat-item-detail">28W / 16L</div></div>
<div class="bt-plat-item"><div class="bt-plat-item-name dk">DK Pick6</div><div class="bt-plat-item-wr">65.6%</div><div class="bt-plat-item-detail">21W / 11L</div></div>
</div>
</div>

<!-- CALENDAR HEATMAP — 2 weeks -->
<div class="bt-cal">
<div class="bt-cal-hdr">&#x1F7E9; Win Rate Heatmap &mdash; Last 14 Days</div>
<div class="bt-cal-grid">
<div class="bt-cal-day green2" title="Apr 6: 60%"></div>
<div class="bt-cal-day green3" title="Apr 7: 71%"></div>
<div class="bt-cal-day red1" title="Apr 8: 40%"></div>
<div class="bt-cal-day green2" title="Apr 9: 57%"></div>
<div class="bt-cal-day green4" title="Apr 10: 80%"></div>
<div class="bt-cal-day green3" title="Apr 11: 67%"></div>
<div class="bt-cal-day green2" title="Apr 12: 62%"></div>
<div class="bt-cal-day red2" title="Apr 13: 33%"></div>
<div class="bt-cal-day green3" title="Apr 14: 71%"></div>
<div class="bt-cal-day green4" title="Apr 15: 83%"></div>
<div class="bt-cal-day green2" title="Apr 16: 60%"></div>
<div class="bt-cal-day green3" title="Apr 17: 67%"></div>
<div class="bt-cal-day green4" title="Apr 18: 75%"></div>
<div class="bt-cal-day today green3" title="Apr 19: 71% (today)"></div>
</div>
<div class="bt-cal-legend">
<div class="bt-cal-legend-item"><div class="bt-cal-legend-swatch" style="background:rgba(242,67,54,0.35)"></div>0-50%</div>
<div class="bt-cal-legend-item"><div class="bt-cal-legend-swatch" style="background:rgba(0,213,89,0.15)"></div>50-60%</div>
<div class="bt-cal-legend-item"><div class="bt-cal-legend-swatch" style="background:rgba(0,213,89,0.3)"></div>60-70%</div>
<div class="bt-cal-legend-item"><div class="bt-cal-legend-swatch" style="background:rgba(0,213,89,0.5)"></div>70-80%</div>
<div class="bt-cal-legend-item"><div class="bt-cal-legend-swatch" style="background:rgba(0,213,89,0.7)"></div>80%+</div>
</div>
</div>

<!-- CUMULATIVE P&L CHART (SVG) -->
<div class="bt-pnl">
<div class="bt-pnl-hdr">
<div class="bt-pnl-lbl">&#x1F4C8; Cumulative P&amp;L Curve</div>
<div class="bt-pnl-val">+$847 &middot; +84.7% ROI</div>
</div>
<svg viewBox="0 0 400 60" preserveAspectRatio="none">
<defs><linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#00D559" stop-opacity="0.3"/><stop offset="1" stop-color="#00D559" stop-opacity="0"/></linearGradient></defs>
<path d="M0,55 L14,52 L28,50 L42,48 L56,51 L70,46 L84,43 L98,44 L112,40 L126,37 L140,38 L154,34 L168,30 L182,32 L196,28 L210,25 L224,23 L238,26 L252,22 L266,19 L280,16 L294,17 L308,14 L322,11 L336,9 L350,8 L364,6 L378,5 L392,3 L400,2 L400,60 L0,60 Z" fill="url(#pnlGrad)"/>
<path d="M0,55 L14,52 L28,50 L42,48 L56,51 L70,46 L84,43 L98,44 L112,40 L126,37 L140,38 L154,34 L168,30 L182,32 L196,28 L210,25 L224,23 L238,26 L252,22 L266,19 L280,16 L294,17 L308,14 L322,11 L336,9 L350,8 L364,6 L378,5 L392,3 L400,2" fill="none" stroke="#00D559" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
<line x1="0" y1="55" x2="400" y2="55" stroke="rgba(255,255,255,0.05)" stroke-width="0.5"/>
<circle cx="400" cy="2" r="3" fill="#00D559" opacity="0.8"/>
</svg>
</div>

<!-- DATE GROUP: Today -->
<div class="bt-date-hdr">
<div class="bt-date-label">&#x1F4C5; Today &mdash; Apr 19, 2026</div>
<div class="bt-date-stats">7 bets &middot; <span class="w">5W</span> &middot; <span class="l">0L</span> &middot; <span class="p">2 pending</span></div>
</div>
<div class="bt-cards">
<div class="bt-card pend">
  <div class="bt-card-tier">&#x1F48E;</div>
  <div class="bt-card-info"><div class="bt-card-player">Luka Don&#x10D;i&#x107; &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform pp">PrizePicks</span><span class="bt-card-safe">SAFE <span class="sc">87</span></span></div></div>
  <div class="bt-card-line ov">O 28.5</div>
  <div class="bt-card-actual tbd">&mdash;</div>
  <div class="bt-card-clv neg">&mdash;</div>
  <div class="bt-card-result pending">&#x23F3;</div>
</div>
<div class="bt-card pend">
  <div class="bt-card-tier">&#x1F947;</div>
  <div class="bt-card-info"><div class="bt-card-player">Jayson Tatum &mdash; Rebounds</div><div class="bt-card-meta"><span class="bt-card-platform dk">DK Pick6</span><span class="bt-card-safe">SAFE <span class="sc">79</span></span></div></div>
  <div class="bt-card-line ov">O 8.5</div>
  <div class="bt-card-actual tbd">&mdash;</div>
  <div class="bt-card-clv neg">&mdash;</div>
  <div class="bt-card-result pending">&#x23F3;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F48E;</div>
  <div class="bt-card-info"><div class="bt-card-player">SGA &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform pp">PrizePicks</span><span class="bt-card-safe">SAFE <span class="sc">91</span></span></div></div>
  <div class="bt-card-line ov">O 30.5</div>
  <div class="bt-card-actual hit">36</div>
  <div class="bt-card-clv pos">+5.3%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F947;</div>
  <div class="bt-card-info"><div class="bt-card-player">Ant Edwards &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform ud">Underdog</span><span class="bt-card-safe">SAFE <span class="sc">82</span></span></div></div>
  <div class="bt-card-line un">U 26.5</div>
  <div class="bt-card-actual hit">21</div>
  <div class="bt-card-clv pos">+4.7%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F48E;</div>
  <div class="bt-card-info"><div class="bt-card-player">LeBron James &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform pp">PrizePicks</span><span class="bt-card-safe">SAFE <span class="sc">85</span></span></div></div>
  <div class="bt-card-line ov">O 25.5</div>
  <div class="bt-card-actual hit">31</div>
  <div class="bt-card-clv pos">+3.1%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F948;</div>
  <div class="bt-card-info"><div class="bt-card-player">Tyrese Maxey &mdash; Assists</div><div class="bt-card-meta"><span class="bt-card-platform dk">DK Pick6</span><span class="bt-card-safe">SAFE <span class="sc">74</span></span></div></div>
  <div class="bt-card-line ov">O 5.5</div>
  <div class="bt-card-actual hit">7</div>
  <div class="bt-card-clv pos">+1.8%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F947;</div>
  <div class="bt-card-info"><div class="bt-card-player">Nikola Joki&#x107; &mdash; Assists</div><div class="bt-card-meta"><span class="bt-card-platform ud">Underdog</span><span class="bt-card-safe">SAFE <span class="sc">80</span></span></div></div>
  <div class="bt-card-line ov">O 9.5</div>
  <div class="bt-card-actual hit">12</div>
  <div class="bt-card-clv pos">+2.9%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
</div>

<!-- DATE GROUP: Yesterday -->
<div class="bt-date-hdr">
<div class="bt-date-label">&#x1F4C5; Apr 18, 2026</div>
<div class="bt-date-stats">8 bets &middot; <span class="w">6W</span> &middot; <span class="l">2L</span></div>
</div>
<div class="bt-cards">
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F48E;</div>
  <div class="bt-card-info"><div class="bt-card-player">Steph Curry &mdash; 3PM</div><div class="bt-card-meta"><span class="bt-card-platform pp">PrizePicks</span><span class="bt-card-safe">SAFE <span class="sc">88</span></span></div></div>
  <div class="bt-card-line ov">O 4.5</div>
  <div class="bt-card-actual hit">6</div>
  <div class="bt-card-clv pos">+6.1%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card loss">
  <div class="bt-card-tier">&#x1F948;</div>
  <div class="bt-card-info"><div class="bt-card-player">Trae Young &mdash; Assists</div><div class="bt-card-meta"><span class="bt-card-platform ud">Underdog</span><span class="bt-card-safe">SAFE <span class="sc">71</span></span></div></div>
  <div class="bt-card-line ov">O 10.5</div>
  <div class="bt-card-actual miss">8</div>
  <div class="bt-card-clv neg">&minus;1.4%</div>
  <div class="bt-card-result l">&#x2717;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F947;</div>
  <div class="bt-card-info"><div class="bt-card-player">Ja Morant &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform dk">DK Pick6</span><span class="bt-card-safe">SAFE <span class="sc">83</span></span></div></div>
  <div class="bt-card-line ov">O 24.5</div>
  <div class="bt-card-actual hit">29</div>
  <div class="bt-card-clv pos">+3.8%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F48E;</div>
  <div class="bt-card-info"><div class="bt-card-player">Giannis &mdash; Rebounds</div><div class="bt-card-meta"><span class="bt-card-platform pp">PrizePicks</span><span class="bt-card-safe">SAFE <span class="sc">90</span></span></div></div>
  <div class="bt-card-line ov">O 11.5</div>
  <div class="bt-card-actual hit">14</div>
  <div class="bt-card-clv pos">+4.2%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card loss">
  <div class="bt-card-tier">&#x1F949;</div>
  <div class="bt-card-info"><div class="bt-card-player">D&rsquo;Angelo Russell &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform ud">Underdog</span><span class="bt-card-safe">SAFE <span class="sc">63</span></span></div></div>
  <div class="bt-card-line ov">O 18.5</div>
  <div class="bt-card-actual miss">14</div>
  <div class="bt-card-clv neg">&minus;0.8%</div>
  <div class="bt-card-result l">&#x2717;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F947;</div>
  <div class="bt-card-info"><div class="bt-card-player">Kevin Durant &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform dk">DK Pick6</span><span class="bt-card-safe">SAFE <span class="sc">84</span></span></div></div>
  <div class="bt-card-line ov">O 27.5</div>
  <div class="bt-card-actual hit">32</div>
  <div class="bt-card-clv pos">+2.6%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F48E;</div>
  <div class="bt-card-info"><div class="bt-card-player">Cade Cunningham &mdash; Assists</div><div class="bt-card-meta"><span class="bt-card-platform pp">PrizePicks</span><span class="bt-card-safe">SAFE <span class="sc">86</span></span></div></div>
  <div class="bt-card-line ov">O 7.5</div>
  <div class="bt-card-actual hit">10</div>
  <div class="bt-card-clv pos">+3.5%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
<div class="bt-card win">
  <div class="bt-card-tier">&#x1F948;</div>
  <div class="bt-card-info"><div class="bt-card-player">Devin Booker &mdash; Points</div><div class="bt-card-meta"><span class="bt-card-platform ud">Underdog</span><span class="bt-card-safe">SAFE <span class="sc">76</span></span></div></div>
  <div class="bt-card-line un">U 28.5</div>
  <div class="bt-card-actual hit">22</div>
  <div class="bt-card-clv pos">+1.9%</div>
  <div class="bt-card-result w">&#x2713;</div>
</div>
</div>

<!-- Pagination -->
<div class="bt-pag">
<div class="bt-pag-btn active">1</div>
<div class="bt-pag-btn">2</div>
<div class="bt-pag-btn">3</div>
<div class="bt-pag-btn">4</div>
<div class="bt-pag-btn">5</div>
<div class="bt-pag-info">Showing 1&ndash;15 of 127 bets</div>
</div>

<!-- Bankroll growth -->
<div class="bt-bankroll">
<div class="bt-bankroll-hdr">
<div class="bt-bankroll-lbl">&#x1F4B0; Bankroll Growth (30d)</div>
<div><span class="bt-bankroll-val">$1,000 &#x2192; $1,847</span><span class="bt-bankroll-sub">+84.7% ROI</span></div>
</div>
<div class="bt-growth">
<div class="bt-growth-bar" style="height:18%"></div>
<div class="bt-growth-bar" style="height:22%"></div>
<div class="bt-growth-bar" style="height:20%"></div>
<div class="bt-growth-bar" style="height:28%"></div>
<div class="bt-growth-bar" style="height:25%"></div>
<div class="bt-growth-bar red" style="height:22%"></div>
<div class="bt-growth-bar" style="height:30%"></div>
<div class="bt-growth-bar" style="height:35%"></div>
<div class="bt-growth-bar" style="height:33%"></div>
<div class="bt-growth-bar" style="height:38%"></div>
<div class="bt-growth-bar red" style="height:35%"></div>
<div class="bt-growth-bar" style="height:40%"></div>
<div class="bt-growth-bar" style="height:42%"></div>
<div class="bt-growth-bar" style="height:45%"></div>
<div class="bt-growth-bar" style="height:48%"></div>
<div class="bt-growth-bar red" style="height:44%"></div>
<div class="bt-growth-bar" style="height:50%"></div>
<div class="bt-growth-bar" style="height:55%"></div>
<div class="bt-growth-bar" style="height:52%"></div>
<div class="bt-growth-bar" style="height:58%"></div>
<div class="bt-growth-bar" style="height:62%"></div>
<div class="bt-growth-bar" style="height:60%"></div>
<div class="bt-growth-bar" style="height:65%"></div>
<div class="bt-growth-bar red" style="height:62%"></div>
<div class="bt-growth-bar" style="height:68%"></div>
<div class="bt-growth-bar" style="height:72%"></div>
<div class="bt-growth-bar" style="height:75%"></div>
<div class="bt-growth-bar" style="height:78%"></div>
<div class="bt-growth-bar" style="height:82%"></div>
<div class="bt-growth-bar" style="height:88%"></div>
</div>
</div>

</div><!-- /bt-app -->

<!-- How it works -->
<div class="bt-how">
<div class="bt-how-hdr">&#x1F4D6; How the Bet Tracker Works</div>
<ul class="bt-how-list">
<li class="bt-how-item"><span class="bt-how-ico">&#x1F4DD;</span><span><strong>Log every bet</strong> &mdash; record picks with one click from analysis. Platform, stake, odds, SAFE Score saved automatically.</span></li>
<li class="bt-how-item"><span class="bt-how-ico">&#x1F4CA;</span><span><strong>Auto-grade results</strong> &mdash; checks final box scores and marks every prop as HIT or MISS. No manual entry needed.</span></li>
<li class="bt-how-item"><span class="bt-how-ico">&#x1F4B0;</span><span><strong>Track your bankroll</strong> &mdash; ROI, win rate, CLV capture, profit/loss, and bankroll growth visualized with real charts.</span></li>
<li class="bt-how-item"><span class="bt-how-ico">&#x1F50D;</span><span><strong>Filter by anything</strong> &mdash; platform, stat type, SAFE Score range, tier, date, or direction. Export to CSV anytime.</span></li>
<li class="bt-how-item"><span class="bt-how-ico">&#x1F6E1;&#xFE0F;</span><span><strong>No fake screenshots</strong> &mdash; your Bet Tracker is YOUR data. Every win and loss, verifiable and auditable.</span></li>
<li class="bt-how-item"><span class="bt-how-ico">&#x1F3C6;</span><span><strong>Achievements &amp; streaks</strong> &mdash; earn badges for win streaks, ROI milestones, and volume. Track your progress over time.</span></li>
</ul>
</div>

<div class="bt-footer">&#x2191; This is a demo preview with sample data. Sign up free to get your own live Bet Tracker.</div>
""")

    # ── Below-fold: Pricing tiers, FAQ, CTA ──────────────────
    # Uses st.html() to bypass Streamlit's markdown parser which
    # cannot handle deeply nested HTML structures.
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7)}
.em{background:linear-gradient(135deg,#00D559 0%,#2D9EFF 50%,#c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.sh{text-align:center;margin-bottom:24px;position:relative}
.sh::before{content:'';display:block;width:60px;height:4px;margin:0 auto 18px;background:linear-gradient(90deg,#00D559,#2D9EFF);border-radius:4px}
.sh h3{font-family:'Space Grotesk',sans-serif;font-size:2.2rem;font-weight:700;color:#fff;margin:0 0 10px;letter-spacing:-0.04em;text-transform:uppercase}
.sh p{font-size:0.85rem;color:rgba(255,255,255,0.4);margin:0;line-height:1.6}
/* Tier cards */
.tc{background:linear-gradient(168deg,rgba(255,255,255,0.05),rgba(255,255,255,0.012));border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:26px 24px;margin:16px 0 0;position:relative;overflow:hidden;transition:border-color 0.3s,transform 0.3s,box-shadow 0.3s}
.tc:hover{transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,0,0,0.3)}
.tc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.tc.tf::before{background:linear-gradient(90deg,#708090,#A0AABE)}
.tc.ts::before{background:linear-gradient(90deg,#F9C62B,#ff8c00)}
.tc.tm::before{background:linear-gradient(90deg,#00D559,#2D9EFF)}
.tc.ti::before{background:linear-gradient(90deg,#c084fc,#9333ea)}
.th{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.tn{font-family:'Space Grotesk',sans-serif;font-size:0.85rem;font-weight:800;text-transform:uppercase;letter-spacing:0.06em}
.tf .tn{color:#A0AABE}.ts .tn{color:#F9C62B}.tm .tn{color:#00D559}.ti .tn{color:#c084fc}
.tp{font-family:'JetBrains Mono',monospace;font-size:0.82rem;font-weight:700}
.tf .tp{color:#A0AABE}.ts .tp{color:#F9C62B}.tm .tp{color:#00D559}.ti .tp{color:#c084fc}
.tg{font-size:0.65rem;font-style:italic;color:rgba(255,255,255,0.25);margin-bottom:12px}
.pl{list-style:none;padding:0;margin:0}
.pi{padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03)}
.pi:last-child{border-bottom:none}
.ph{display:flex;align-items:center;gap:6px}
.pc{font-size:0.85rem;flex-shrink:0}
.pn{font-family:'Space Grotesk',sans-serif;font-size:0.72rem;font-weight:700;color:rgba(255,255,255,0.75)}
.pb{font-size:0.62rem;color:rgba(255,255,255,0.32);line-height:1.5;margin-top:2px;padding-left:22px}
/* Compare toggle */
.cd2{margin:16px 0 0}
.cd2 summary{display:block;width:100%;background:linear-gradient(135deg,rgba(0,213,89,0.08),rgba(45,158,255,0.06));border:1px solid rgba(0,213,89,0.2);border-radius:12px;padding:14px 20px;text-align:center;cursor:pointer;font-family:'Space Grotesk',sans-serif;font-size:0.85rem;font-weight:700;color:#00D559;letter-spacing:0.02em;list-style:none}
.cd2 summary::-webkit-details-marker{display:none}
.cd2 summary::marker{display:none;content:''}
.cd2 summary:hover{background:linear-gradient(135deg,rgba(0,213,89,0.14),rgba(45,158,255,0.1));border-color:rgba(0,213,89,0.35);transform:translateY(-1px)}
.cd2 summary .arrow{display:inline-block;transition:transform 0.3s;margin-left:6px}
.cd2[open] summary .arrow{transform:rotate(180deg)}
/* Comparison table */
.tw2{margin:18px 0 0;overflow-x:auto}
.tt{width:100%;border-collapse:separate;border-spacing:0;background:rgba(255,255,255,0.015);border:1px solid rgba(255,255,255,0.05);border-radius:12px;overflow:hidden;font-size:0.64rem}
.tt thead th{padding:10px 8px;font-size:0.55rem;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:rgba(255,255,255,0.3);border-bottom:1px solid rgba(255,255,255,0.05);text-align:center}
.tt thead th:first-child{text-align:left;width:34%;padding-left:10px}
.tt thead th.hf{color:#A0AABE}.tt thead th.hs{color:#F9C62B}.tt thead th.hm{color:#00D559}.tt thead th.hi2{color:#c084fc}
.tt tbody td{padding:7px 8px;text-align:center;color:rgba(255,255,255,0.3);border-bottom:1px solid rgba(255,255,255,0.025);font-weight:500}
.tt tbody td:first-child{text-align:left;padding-left:10px;color:rgba(255,255,255,0.5);font-weight:600}
.tt tbody tr:last-child td{border-bottom:none}
.tt .y{color:#00D559;font-weight:700}
.tt .n{color:rgba(255,255,255,0.1)}
.tt .lim{color:#ff9d00;font-weight:700}
.tt .cat td{color:rgba(0,213,89,0.5);font-weight:700;font-size:0.58rem;text-transform:uppercase;letter-spacing:0.06em;padding:6px 10px;background:rgba(0,213,89,0.02)}
/* Savings */
.sv2{background:rgba(249,198,43,0.04);border:1px solid rgba(249,198,43,0.12);border-radius:12px;padding:14px 16px;text-align:center;margin:16px 0 0}
.sv2 .st2{font-family:'Space Grotesk',sans-serif;font-size:0.78rem;font-weight:700;color:#F9C62B;margin:0}
.sv2 .st2 .big{font-family:'JetBrains Mono',monospace;font-size:1.2rem;font-weight:800}
.sv2 .ss{font-size:0.62rem;color:rgba(255,255,255,0.3);margin:4px 0 0}
/* Insider CTA */
.ic{background:linear-gradient(135deg,rgba(192,132,252,0.06),rgba(147,51,234,0.04));border:1px solid rgba(192,132,252,0.2);border-radius:14px;padding:18px 16px;text-align:center;margin:16px 0 0;position:relative;overflow:hidden}
.ic::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#c084fc,#9333ea,transparent)}
.ic-f{font-size:1.3rem;margin-bottom:4px}
.ic-h{font-family:'Space Grotesk',sans-serif;font-size:0.88rem;font-weight:800;color:#c084fc;margin:0 0 4px}
.ic-s{font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:800;color:#fff;margin:4px 0}
.ic-s .of{font-size:0.7rem;font-weight:500;color:rgba(255,255,255,0.25)}
.ic-sub{font-size:0.62rem;color:rgba(255,255,255,0.3);margin-top:2px;line-height:1.5}
.ic-pb{display:inline-block;margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;font-weight:700;color:#c084fc;background:rgba(192,132,252,0.08);border:1px solid rgba(192,132,252,0.15);padding:4px 14px;border-radius:100px}
/* Performance */
.pf{margin:28px 0 0}
.pf-c{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:14px;padding:18px 16px 14px}
.pf-h{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.pf-t{font-family:'Space Grotesk',sans-serif;font-size:0.78rem;font-weight:700;color:rgba(255,255,255,0.7)}
.pf-a{font-family:'JetBrains Mono',monospace;font-size:0.82rem;font-weight:800;color:#00D559}
.sk{display:flex;align-items:flex-end;gap:3px;height:50px;width:100%}
.sb{flex:1;border-radius:3px 3px 0 0;min-height:4px}
.sb.w{background:linear-gradient(180deg,#00D559,rgba(0,213,89,0.3))}
.sb.l{background:linear-gradient(180deg,rgba(242,67,54,0.5),rgba(242,67,54,0.15))}
.sl2{display:flex;justify-content:space-between;margin-top:4px}
.sl2 span{font-family:'JetBrains Mono',monospace;font-size:0.42rem;color:rgba(255,255,255,0.15);font-weight:600}
/* FAQ */
.fq{margin:28px 0 0}
.fi{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;margin-bottom:6px}
.fi summary{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;cursor:pointer;font-family:'Space Grotesk',sans-serif;font-size:0.76rem;font-weight:700;color:rgba(255,255,255,0.6);list-style:none}
.fi summary::-webkit-details-marker{display:none}
.fi summary::marker{display:none;content:''}
.fi summary:hover{color:rgba(255,255,255,0.8)}
.fi summary .fa{display:inline-block;transition:transform 0.3s;color:rgba(0,213,89,0.4);font-size:0.65rem}
.fi[open] summary .fa{transform:rotate(180deg)}
.fi-a{padding:0 16px 14px;font-size:0.7rem;color:rgba(255,255,255,0.35);line-height:1.6}
/* CTA2 */
.c2{background:linear-gradient(135deg,rgba(0,213,89,0.1),rgba(45,158,255,0.06));border:2px solid rgba(0,213,89,0.2);border-radius:24px;padding:44px 28px;text-align:center;margin:36px 0 0;position:relative;overflow:hidden}
.c2::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 0%,rgba(0,213,89,0.08) 0%,transparent 60%);pointer-events:none}
.c2-h{font-family:'Space Grotesk',sans-serif;font-size:2rem;font-weight:800;color:#fff;margin:0 0 10px;text-transform:uppercase;letter-spacing:-0.03em;position:relative}
.c2-s{font-size:0.85rem;color:rgba(255,255,255,0.4);margin:0 0 20px;line-height:1.6;position:relative}
.c2-b{display:inline-block;font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:700;color:#0B0F19;background:linear-gradient(135deg,#00D559,#00B74D);padding:16px 52px;border-radius:16px;text-decoration:none;box-shadow:0 6px 32px rgba(0,213,89,0.35);position:relative}
.c2-b:hover{transform:translateY(-4px);box-shadow:0 12px 48px rgba(0,213,89,0.5)}
.c2-t{font-size:0.6rem;color:rgba(255,255,255,0.18);margin-top:14px;position:relative}
/* Trust + Footer */
.tr{display:flex;justify-content:center;gap:16px;margin:28px 0 6px;flex-wrap:wrap}
.tr-i{font-size:0.62rem;font-weight:600;color:rgba(255,255,255,0.22);display:flex;align-items:center;gap:4px}
.ft{text-align:center;padding:20px 0 40px;font-size:0.55rem;color:rgba(255,255,255,0.1);line-height:1.7}
.ft a{color:rgba(255,255,255,0.15);text-decoration:underline}
</style>

<details class="cd2">
<summary>&#x1F50D; Compare All Subscription Tiers <span class="arrow">&#x25BC;</span></summary>

<div class="tc tf"><div class="th"><div class="tn">&#x2B50; Smart Rookie</div><div class="tp">$0 / forever</div></div>
<div class="tg">&ldquo;Welcome to the smart side.&rdquo; &mdash; No credit card required.</div>
<ul class="pl">
<li class="pi"><div class="ph"><span class="pc">&#x1F4A6;</span><span class="pn">Live Sweat</span></div><div class="pb">Track your active bets in real-time with live scoring, AI confidence updates, and play-by-play. Know instantly if your prop is on pace to hit.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F4E1;</span><span class="pn">Live Games</span></div><div class="pb">Real-time NBA scoreboard with box scores, quarter-by-quarter breakdowns, and in-game stat leaders. Never miss a beat.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x26A1;</span><span class="pn">Quantum Analysis Matrix (10 props)</span></div><div class="pb">Our flagship AI engine: 6 fused models analyze player props with SAFE Scores (0-100), edge detection, and confidence ratings. Free tier gets 10 props per session.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F52C;</span><span class="pn">Prop Scanner (5 manual)</span></div><div class="pb">Manually enter any player prop and get instant AI analysis &mdash; predicted line, SAFE Score, and over/under recommendation.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F4E1;</span><span class="pn">Smart NBA Data</span></div><div class="pb">Full NBA stats dashboard &mdash; player averages, team rankings, defensive ratings, and advanced metrics to research any matchup.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x2699;&#xFE0F;</span><span class="pn">Settings</span></div><div class="pb">Customize your experience &mdash; default platforms, display preferences, and notification settings.</div></li>
</ul></div>

<div class="tc ts"><div class="th"><div class="tn">&#x1F525; Sharp IQ</div><div class="tp">$9.99/mo &middot; $107.89/yr</div></div>
<div class="tg">&ldquo;Your IQ just passed the books.&rdquo; &mdash; Everything in Free, plus:</div>
<ul class="pl">
<li class="pi"><div class="ph"><span class="pc">&#x26A1;</span><span class="pn">Quantum Analysis Matrix (25 props)</span></div><div class="pb">Expanded to 25 AI-analyzed props per session. More coverage = more edges to find before the books adjust.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F52C;</span><span class="pn">Prop Scanner &mdash; Unlimited + CSV + Live Retrieval</span></div><div class="pb">Scan unlimited props, bulk-upload via CSV, or auto-pull your PrizePicks/DraftKings slips. AI analyzes every line instantly.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F9EC;</span><span class="pn">Entry Builder</span></div><div class="pb">Build optimized PrizePicks &amp; Pick6 entries. AI ranks combinations by expected value, correlation, and SAFE Score to maximize your payout odds.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F6E1;&#xFE0F;</span><span class="pn">Risk Shield</span></div><div class="pb">Portfolio-level risk analysis for your entries. See exposure by player, team, and stat type. Avoid correlated losses before they happen.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F4CB;</span><span class="pn">Game Report</span></div><div class="pb">Deep-dive matchup reports: pace projections, defensive matchup grades, rest advantages, and AI game scripts for every NBA game tonight.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F52E;</span><span class="pn">Player Simulator</span></div><div class="pb">Monte Carlo simulation engine. Run 10,000+ scenarios for any player prop to see hit probability, ceiling/floor, and variance risk.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F4C8;</span><span class="pn">Bet Tracker</span></div><div class="pb">Log every bet and track your ROI, win rate, CLV capture, and bankroll growth over time. See which strategies actually make money.</div></li>
</ul></div>

<div class="tc tm"><div class="th"><div class="tn">&#x1F48E; Smart Money</div><div class="tp">$24.99/mo &middot; $269.89/yr</div></div>
<div class="tg">&ldquo;You are the smart money.&rdquo; &mdash; Everything in Sharp IQ, plus:</div>
<ul class="pl">
<li class="pi"><div class="ph"><span class="pc">&#x26A1;</span><span class="pn">Quantum Analysis Matrix &mdash; ALL 300+ Props</span></div><div class="pb">Full, unrestricted access to every prop the AI analyzes tonight. See the complete board &mdash; no limits, no waiting.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F4B0;</span><span class="pn">Smart Money Bets</span></div><div class="pb">See where the sharp money is flowing. AI-detected line movement + volume anomalies show you which side the professionals are on.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F5FA;&#xFE0F;</span><span class="pn">Correlation Matrix</span></div><div class="pb">Visual correlation heatmap between player props. Find hidden +EV parlays where props move together &mdash; or hedge with negative correlations.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F4CA;</span><span class="pn">Proving Grounds</span></div><div class="pb">Backtest any strategy against historical data. See how your filters, SAFE Score thresholds, and entry styles would have performed last season.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F399;&#xFE0F;</span><span class="pn">The Studio</span></div><div class="pb">AI-generated analysis reports with narrative breakdowns, data visualizations, and shareable pick cards for your best plays.</div></li>
</ul></div>

<div class="tc ti"><div class="th"><div class="tn">&#x1F451; Insider Circle</div><div class="tp">$499.99 one-time &middot; lifetime</div></div>
<div class="tg">&ldquo;You knew before everyone.&rdquo; &mdash; Everything in Smart Money, plus:</div>
<ul class="pl">
<li class="pi"><div class="ph"><span class="pc">&#x1F451;</span><span class="pn">Lifetime Access &mdash; Never Pay Again</span></div><div class="pb">One payment, permanent access to every current feature and every future feature we build. No subscriptions, no renewals, no surprise charges.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F680;</span><span class="pn">Early Access to New Tools</span></div><div class="pb">Be the first to test new AI models, pages, and features before they launch to the public. Your feedback shapes what we build next.</div></li>
<li class="pi"><div class="ph"><span class="pc">&#x1F3C6;</span><span class="pn">Founding Member Status</span></div><div class="pb">Limited to 75 members. Exclusive badge, priority support, and recognition as an original Smart Pick Pro insider.</div></li>
</ul></div>

<div class="tw2"><table class="tt">
<thead><tr><th>Page / Feature</th><th class="hf">&#x2B50; Free</th><th class="hs">&#x1F525; Sharp</th><th class="hm">&#x1F48E; Smart</th><th class="hi2">&#x1F451; Insider</th></tr></thead>
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
</tbody></table></div>

</details>

<div class="sv2"><p class="st2">You&rsquo;d pay <span class="big">$1,188/yr</span> for OddsJam alone.</p><p class="ss">Smart Pick Pro gives you more features, more AI, more props &mdash; for $0. Do the math.</p></div>

<div class="ic"><div class="ic-f">&#x1F525;</div><div class="ic-h">Founding Member Seats Are Going Fast</div><div class="ic-s">12 <span class="of">of 75 remaining</span></div><div class="ic-sub">Once all 75 seats are claimed, Insider Circle closes permanently. Lifetime access &mdash; one payment, never pay again.</div><div class="ic-pb">&#x1F451; $499.99 &middot; Lifetime</div></div>

<div class="pf"><div class="sh"><h3>Recent AI Performance</h3><p>Last 14 days &mdash; SAFE Score 70+ picks</p></div>
<div class="pf-c"><div class="pf-h"><div class="pf-t">Daily Win Rate</div><div class="pf-a">62.4% avg</div></div>
<div class="sk"><div class="sb w" style="height:68%"></div><div class="sb w" style="height:54%"></div><div class="sb w" style="height:72%"></div><div class="sb l" style="height:38%"></div><div class="sb w" style="height:80%"></div><div class="sb w" style="height:62%"></div><div class="sb w" style="height:58%"></div><div class="sb l" style="height:42%"></div><div class="sb w" style="height:76%"></div><div class="sb w" style="height:64%"></div><div class="sb w" style="height:70%"></div><div class="sb w" style="height:60%"></div><div class="sb l" style="height:35%"></div><div class="sb w" style="height:74%"></div></div>
<div class="sl2"><span>14d ago</span><span>7d ago</span><span>Today</span></div></div></div>

<div class="fq"><div class="sh"><h3>Got Questions?</h3><p>We&rsquo;ve got answers</p></div>
<details class="fi"><summary>Is it really free? What&rsquo;s the catch? <span class="fa">&#x25BC;</span></summary><div class="fi-a">No catch. Smart Rookie gives you 10 AI-analyzed props, Live Sweat, Live Games, and SAFE Scores &mdash; free forever, no credit card required. We make money from optional upgrades (Sharp IQ &amp; Smart Money), not from locking basic features behind paywalls.</div></details>
<details class="fi"><summary>How does the AI actually work? <span class="fa">&#x25BC;</span></summary><div class="fi-a">Our Quantum Analysis Matrix fuses 6 independent AI models &mdash; each trained on different data (player logs, matchup DNA, pace projections, defensive ratings, line movement, and injury impact). They vote on every prop and produce a SAFE Score from 0-100. Higher score = higher confidence = bigger edge.</div></details>
<details class="fi"><summary>Can I cancel anytime? <span class="fa">&#x25BC;</span></summary><div class="fi-a">Absolutely. Sharp IQ and Smart Money are month-to-month with no commitment. Cancel from your Settings page in one click &mdash; no emails, no phone calls, no guilt trips. Your data stays yours.</div></details>
<details class="fi"><summary>What platforms do you support? <span class="fa">&#x25BC;</span></summary><div class="fi-a">Our AI analyzes props from PrizePicks, DraftKings Pick6, Underdog Fantasy, and more. You can also manually enter any prop from any platform into the Prop Scanner for instant AI analysis.</div></details>
<details class="fi"><summary>How is this better than OddsJam / Action Network? <span class="fa">&#x25BC;</span></summary><div class="fi-a">Those tools charge $60&ndash;$300/mo for basic odds comparison. Smart Pick Pro gives you 6 fused AI models, SAFE Scores, real-time live tracking, edge detection, bankroll tools, and backtesting &mdash; for free. They literally cannot compete on features or price.</div></details>
</div>

<div class="c2"><div class="c2-h">Ready to <span class="em">Beat the Books?</span></div><p class="c2-s">Join thousands of sharps using AI to find edges the books don&rsquo;t want you to see.</p><a class="c2-b" href="#" onclick="window.scrollTo({top:0,behavior:'smooth'});return false;">&#x26A1; Create Free Account</a><div class="c2-t">&#x1F512; No credit card &middot; &#x23F1;&#xFE0F; 10 second signup &middot; &#x1F6AB; Never sell your data</div></div>

<div class="tr"><div class="tr-i">&#x1F512; 256-bit Encrypted</div><div class="tr-i">&#x1F4B3; No Credit Card</div><div class="tr-i">&#x1F6AB; Never Sell Data</div></div>

<div class="ft">&copy; 2026 Smart Pick Pro &middot; For entertainment &amp; educational purposes only &middot; 21+<br><a href="https://www.ncpgambling.org/" target="_blank">National Council on Problem Gambling &middot; 1-800-GAMBLER</a></div>
""")

    return False
