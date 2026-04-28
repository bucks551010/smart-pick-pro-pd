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
import time
from pathlib import Path

import streamlit as st

from tracking.database import initialize_database, get_database_connection
from utils.stripe_manager import is_stripe_configured, create_checkout_session
from utils.input_sanitizer import (
    sanitize_email,
    sanitize_display_name,
    sanitize_reset_code,
    validate_password_strength,
)

_logger = logging.getLogger(__name__)

_DB_RETRY_ATTEMPTS = 3
_DB_RETRY_DELAY_SECONDS = 0.15

# ── PostgreSQL / SQLite auto-detection ───────────────────────
# When Railway PostgreSQL plugin is added, DATABASE_URL is set automatically.
# The auth layer uses Postgres when available, SQLite otherwise.
# Railway provides URLs with the "postgres://" scheme; psycopg2 needs "postgresql://".
_DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
_HAS_PSYCOPG2 = False
if _DATABASE_URL:
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
        _HAS_PSYCOPG2 = True
        _logger.info("Auth DB: PostgreSQL mode active (DATABASE_URL is set)")
    except ImportError:
        _logger.warning(
            "DATABASE_URL is set but psycopg2 is not installed — "
            "falling back to SQLite. Add psycopg2-binary to requirements.txt."
        )

_PG_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    reset_token TEXT,
    reset_token_expires TIMESTAMPTZ,
    failed_login_count INTEGER DEFAULT 0,
    lockout_until TIMESTAMPTZ,
    is_admin INTEGER DEFAULT 0,
    plan_tier TEXT DEFAULT 'free'
);
"""
_pg_users_initialized = False


def _ensure_pg_users_table() -> None:
    """Create the users table in PostgreSQL if it doesn't exist (idempotent)."""
    global _pg_users_initialized
    if _pg_users_initialized:
        return
    try:
        conn = psycopg2.connect(_DATABASE_URL, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(_PG_USERS_TABLE_SQL)
                # Migration: add plan_tier column to existing tables
                try:
                    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_tier TEXT DEFAULT 'free'")
                except Exception:
                    pass
            conn.commit()
            _pg_users_initialized = True
        finally:
            conn.close()
    except Exception as exc:
        _logger.error("Failed to initialise PostgreSQL users table: %s", exc)


class _AuthConn:
    """Unified context-manager connection wrapper for SQLite or PostgreSQL.

    Usage::

        with _AuthConn() as db:
            row = db.fetchone("SELECT ... WHERE email = ?", (email,))
            db.execute("UPDATE users SET ... WHERE email = ?", (email,))
            # auto-committed on __exit__

    - SQLite: uses ``get_database_connection()`` from tracking.database.
    - PostgreSQL: opens a fresh psycopg2 connection, converts ``?`` → ``%s``
      and ``datetime('now')`` → ``NOW()``.
    """

    def __init__(self) -> None:
        self._pg = _HAS_PSYCOPG2
        self._conn = None
        self._sqlite_ctx = None

    def __enter__(self) -> "_AuthConn":
        if self._pg:
            _ensure_pg_users_table()
            self._conn = psycopg2.connect(
                _DATABASE_URL,
                cursor_factory=psycopg2.extras.RealDictCursor,
                connect_timeout=5,
            )
        else:
            initialize_database()
            self._sqlite_ctx = get_database_connection()
            self._conn = self._sqlite_ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._pg:
            try:
                if exc_type is None:
                    self._conn.commit()
                else:
                    self._conn.rollback()
            finally:
                self._conn.close()
        else:
            self._sqlite_ctx.__exit__(exc_type, exc_val, exc_tb)

    def _adapt(self, sql: str) -> str:
        """Translate SQLite SQL dialect to PostgreSQL when needed."""
        if not self._pg:
            return sql
        return (
            sql.replace("?", "%s")
               .replace("datetime('now')", "NOW()")
               .replace(" COLLATE NOCASE", "")
        )

    def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a write statement (INSERT / UPDATE / DELETE)."""
        adapted = self._adapt(sql)
        if self._pg:
            with self._conn.cursor() as cur:
                cur.execute(adapted, params)
        else:
            self._conn.execute(adapted, params)

    def fetchone(self, sql: str, params: tuple = ()):
        """Execute a SELECT and return the first row as a dict, or None."""
        adapted = self._adapt(sql)
        if self._pg:
            with self._conn.cursor() as cur:
                cur.execute(adapted, params)
                return cur.fetchone()  # RealDictCursor → dict or None
        else:
            row = self._conn.execute(adapted, params).fetchone()
            return dict(row) if row is not None else None

    def commit(self) -> None:
        """Explicit commit (usually handled by __exit__)."""
        self._conn.commit()

# ── Session-state keys ────────────────────────────────────────
_SS_LOGGED_IN     = "_auth_logged_in"      # bool
_SS_USER_EMAIL    = "_auth_user_email"     # str
_SS_USER_NAME     = "_auth_user_name"      # str
_SS_USER_ID       = "_auth_user_id"        # int

# ── Persistent login session (localStorage + DB) ─────────────
# When a user logs in we store a signed token in the browser's
# localStorage AND in the login_sessions table.  On every page
# load require_login() reads the token (via a hidden JS snippet)
# and looks it up in the DB so the user stays logged in across
# F5 reloads and page navigation.  No third-party package needed.

_LS_KEY            = "spp_tok"
# Long-lived access window: how long a freshly-issued token lives.
_SESSION_TTL_DAYS  = 30
# Sliding window: bump expires_at on every load if last_seen is older
# than this threshold.  Keeps active users perpetually logged in.
_SLIDING_RENEWAL_HOURS = 12
# Cookie max-age must match DB TTL (in seconds).
_COOKIE_MAX_AGE    = _SESSION_TTL_DAYS * 86400  # 2 592 000 s
_sessions_table_ok = False


def _ensure_sessions_table() -> None:
    global _sessions_table_ok
    if _sessions_table_ok:
        return
    # Step 1: CREATE TABLE in its own transaction so a failed migration below
    # cannot abort / roll back the table creation (critical for PostgreSQL where
    # any statement error aborts the entire transaction block).
    try:
        with _AuthConn() as db:
            # Use no DEFAULT clause on timestamp columns so the SQL is valid in
            # both SQLite and PostgreSQL (PostgreSQL rejects TEXT DEFAULT (NOW())).
            # Values are always passed explicitly in INSERT statements.
            db.execute("""
                CREATE TABLE IF NOT EXISTS login_sessions (
                    token        TEXT PRIMARY KEY,
                    user_id      INTEGER NOT NULL,
                    email        TEXT NOT NULL,
                    display_name TEXT,
                    is_admin     INTEGER DEFAULT 0,
                    expires_at   TEXT NOT NULL,
                    last_seen    TEXT,
                    created_at   TEXT,
                    plan_tier    TEXT DEFAULT 'free'
                )
            """)
    except Exception as _exc:
        _logger.error("Failed to create login_sessions table: %s", _exc)
        return
    # Step 2: Column migration in a SEPARATE transaction.  If the column already
    # exists (table was just created with it, or a previous run added it) the
    # ALTER TABLE fails and only this transaction is rolled back — the table
    # itself is unaffected.
    try:
        with _AuthConn() as db:
            db.execute("ALTER TABLE login_sessions ADD COLUMN last_seen TEXT")
    except Exception:
        pass  # Column already exists — safe to ignore.
    try:
        with _AuthConn() as db:
            db.execute("ALTER TABLE login_sessions ADD COLUMN plan_tier TEXT DEFAULT 'free'")
    except Exception:
        pass  # Column already exists — safe to ignore.
    _sessions_table_ok = True


def _save_login_session(token: str, user: dict) -> None:
    import datetime as _dt
    now     = _dt.datetime.utcnow()
    expires = (now + _dt.timedelta(days=_SESSION_TTL_DAYS)).isoformat()
    _ensure_sessions_table()
    try:
        with _AuthConn() as db:
            db.execute(
                """INSERT INTO login_sessions
                       (token, user_id, email, display_name, is_admin,
                        expires_at, last_seen, plan_tier)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(token) DO NOTHING""",
                (token, user.get("user_id", 0), user.get("email", ""),
                 user.get("display_name", ""), int(bool(user.get("is_admin", 0))),
                 expires, now.isoformat(), user.get("plan_tier", "free") or "free"),
            )
    except Exception as _exc:
        _logger.error("Failed to save login session: %s", _exc)


def _load_session_by_token(token: str) -> dict | None:
    """Load a valid session and apply sliding-window renewal.

    If ``last_seen`` is older than ``_SLIDING_RENEWAL_HOURS``, the
    ``expires_at`` timestamp is pushed forward by ``_SESSION_TTL_DAYS``
    and ``last_seen`` is updated.  This keeps active users perpetually
    logged in without ever hitting a hard expiry.
    """
    if not token:
        return None
    _ensure_sessions_table()
    try:
        import datetime as _dt
        # Compare expires_at using a Python ISO string so the query works in
        # both SQLite (string comparison) and PostgreSQL (no type mismatch).
        _now_iso = _dt.datetime.utcnow().isoformat()
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT * FROM login_sessions WHERE token = ? AND expires_at > ?",
                (token, _now_iso),
            )
        if not row:
            return None
        # Sliding window: extend expiry if the user has been active
        # within the renewal window.
        try:
            last_seen_raw = row.get("last_seen") or row.get("created_at") or ""
            if last_seen_raw:
                last_seen = _dt.datetime.fromisoformat(last_seen_raw)
                hours_since = (_dt.datetime.utcnow() - last_seen).total_seconds() / 3600
                if hours_since >= _SLIDING_RENEWAL_HOURS:
                    new_expires = (_dt.datetime.utcnow() + _dt.timedelta(days=_SESSION_TTL_DAYS)).isoformat()
                    now_iso     = _dt.datetime.utcnow().isoformat()
                    with _AuthConn() as db:
                        db.execute(
                            "UPDATE login_sessions SET expires_at = ?, last_seen = ? WHERE token = ?",
                            (new_expires, now_iso, token),
                        )
        except Exception:
            pass  # Non-critical — session is still valid even if renewal fails.
        return row
    except Exception as _exc:
        _logger.error("Failed to load session by token: %s", _exc)
    return None


def _delete_session_token(token: str) -> None:
    if not token:
        return
    try:
        with _AuthConn() as db:
            db.execute("DELETE FROM login_sessions WHERE token = ?", (token,))
    except Exception as _exc:
        _logger.error("Failed to delete session token: %s", _exc)


def _render_session_bridge() -> str | None:
    """Render a hidden JS component that reads/writes localStorage.

    Returns the stored token string on the SECOND Streamlit run
    (after the component posts back its value via query_params).
    Returns None if no token is stored or on the first run.

    We piggyback on st.query_params: the JS sets ?_st=<token>
    so Python can read it.  A one-time param is used so it
    doesn't accumulate on subsequent navigations.

    Also starts the silent-renewal heartbeat (fires every ~23 h)
    so returning users are seamlessly re-validated in the background
    without a redirect to the login screen.
    """
    import streamlit.components.v1 as _components
    # Read back whatever the JS posted last run
    tok = st.query_params.get("_st", "")
    if tok == "__clear__":
        tok = ""

    # Guard: if we already tried the localStorage bridge this session and it
    # didn't authenticate (token was invalid / expired), don't reload again —
    # that causes an infinite reload loop for users with a stale localStorage
    # entry and no valid cookie.
    _bridge_fired = st.session_state.get("_spp_bridge_fired", False)

    # Render the JS bridge (hidden, zero-height)
    _components.html(f"""
<script>
(function() {{
  var key    = "{_LS_KEY}";
  var stored = localStorage.getItem(key) || "";
  var bridgeFired = {"true" if _bridge_fired else "false"};

  // ── localStorage → query-param bridge (for initial session restore) ──
  // Only fire if:
  //   1. There's a token in localStorage
  //   2. It's not already in the URL (we haven't tried it yet)
  //   3. The Python side hasn't already tried and rejected this token
  var url = new URL(window.parent.location.href);
  if (stored && !bridgeFired && url.searchParams.get("_st") !== stored) {{
    url.searchParams.set("_st", stored);
    window.parent.history.replaceState(null, "", url.toString());
    window.parent.location.reload();
  }}

  // ── Silent renewal heartbeat ─────────────────────────────────────────
  // Ping /api/session/refresh every 23 hours while any tab is open.
  // This keeps the HttpOnly shadow cookie and the DB record alive as
  // long as the user has an active browser, implementing the sliding-
  // window 30-day session.  On a return visit after 12+ hours the
  // background refresh fires on the first page load; no redirect needed.
  if (!window.parent._sppHeartbeatStarted) {{
    window.parent._sppHeartbeatStarted = true;
    var _doRefresh = function() {{
      try {{
        fetch("/api/session/refresh", {{
          method: "POST",
          credentials: "include"
        }}).then(function(r) {{
          return r.json();
        }}).then(function(data) {{
          if (data && data.ok === false && data.reason === "expired") {{
            // Server confirmed the session is truly expired.
            // Clear localStorage so the user is prompted to log in
            // on next navigation rather than silently failing.
            try {{ localStorage.removeItem(key); }} catch(e) {{}}
          }}
        }}).catch(function() {{}});
      }} catch(e) {{}}
    }};
    // Fire once immediately on page load (handles the "12-hour return" case),
    // then repeat every 23 hours.
    _doRefresh();
    setInterval(_doRefresh, 23 * 60 * 60 * 1000);
  }}
}})();
</script>
""", height=0)
    return tok or None


def _write_session_to_storage(token: str) -> None:
    """Write the session token as a persistent cookie and to localStorage.

    Cookie flags used:
    - ``max-age=2592000``  — 30-day persistent cookie (survives browser restart)
    - ``SameSite=Strict``  — prevents CSRF via cross-site navigation
    - ``Secure``           — only sent over HTTPS (Caddy terminates TLS)

    Note: ``HttpOnly`` cannot be set from JavaScript; the FastAPI
    ``/api/session/issue`` endpoint sets an HttpOnly shadow cookie for
    environments that support server-side cookie issuance.
    """
    import streamlit.components.v1 as _components
    _components.html(f"""
<script>
(function() {{
  var token  = "{token}";
  var maxAge = {_COOKIE_MAX_AGE};   // 30 days
  var cookieStr = "spp_session=" + token
    + "; path=/"
    + "; max-age=" + maxAge
    + "; SameSite=Strict"
    + "; Secure";
  // Set on the parent page so the browser sends it with every request,
  // including F5 reloads and new tabs.
  try {{
    window.parent.document.cookie = cookieStr;
  }} catch(e) {{
    document.cookie = cookieStr;
  }}
  // localStorage fallback for cookie-blocked environments (e.g. Safari ITP).
  try {{ window.parent.localStorage.setItem("{_LS_KEY}", token); }} catch(e) {{}}

  // ── Notify FastAPI to issue an HttpOnly shadow cookie ──────
  // Fire-and-forget: failure doesn't block the user.
  try {{
    fetch("/api/session/issue", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      credentials: "include",
      body: JSON.stringify({{ token: token }})
    }}).catch(function() {{}});
  }} catch(e) {{}}

  // ── Silent renewal heartbeat ────────────────────────────────
  // Ping /api/session/refresh every 23 hours while the tab is open.
  // This keeps both the JS cookie and the DB record from expiring
  // as long as the user has an active browser session.
  if (!window._sppHeartbeatStarted) {{
    window._sppHeartbeatStarted = true;
    setInterval(function() {{
      try {{
        fetch("/api/session/refresh", {{
          method: "POST",
          credentials: "include"
        }}).catch(function() {{}});
      }} catch(e) {{}}
    }}, 23 * 60 * 60 * 1000);  // every 23 hours
  }}

  // Strip ?auth= and ?_st= from the address bar.
  try {{
    var cleanUrl = window.parent.location.origin + window.parent.location.pathname;
    window.parent.history.replaceState(null, "", cleanUrl);
  }} catch(e) {{}}
}})();
</script>
""", height=0)


def _clear_session_from_storage() -> None:
    """Expire the session cookie and clear localStorage."""
    import streamlit.components.v1 as _components
    _components.html(f"""
<script>
(function() {{
  var expiredCookie = "spp_session=; path=/; max-age=0; SameSite=Strict; Secure";
  try {{
    window.parent.document.cookie = expiredCookie;
  }} catch(e) {{
    document.cookie = expiredCookie;
  }}
  try {{ window.parent.localStorage.removeItem("{_LS_KEY}"); }} catch(e) {{}}
  // Also ask FastAPI to clear the HttpOnly shadow cookie.
  try {{
    fetch("/api/session/clear", {{ method: "POST", credentials: "include" }})
      .catch(function() {{}});
  }} catch(e) {{}}
  try {{
    var cleanUrl = window.parent.location.origin + window.parent.location.pathname;
    window.parent.history.replaceState(null, "", cleanUrl);
  }} catch(e) {{}}
}})();
</script>
""", height=0)


def _get_session_cookie() -> str:
    """Read the spp_session cookie (works on every F5 / new tab)."""
    # Primary: Streamlit 1.44+ proper cookie API
    try:
        return st.context.cookies.get("spp_session", "") or ""
    except Exception:
        pass
    # Fallback: parse Cookie header manually
    try:
        cookie_header = st.context.headers.get("Cookie", "")
        for _part in cookie_header.split(";"):
            _part = _part.strip()
            if _part.startswith("spp_session="):
                return _part[len("spp_session="):]
    except Exception:
        pass
    return ""


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
    if hashed.startswith("$2"):
        if not _HAS_BCRYPT:
            # Existing bcrypt-hashed accounts require bcrypt to be installed.
            _logger.error("bcrypt hash encountered but bcrypt is not installed")
            return False
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


@st.cache_data(ttl=300, show_spinner=False)
def _load_top_preview_picks(limit: int = 5) -> tuple[list[dict], str]:
    """Load today's top platform picks for the landing page preview.

    Cached for 5 minutes via @st.cache_data so concurrent users and reruns
    share a single DB query instead of hitting PostgreSQL on every render.

    Priority (first non-empty wins):
      1. Today's platform picks from the DB (platform IS NOT NULL).
      2. Today's any picks from the DB (no platform filter — catches runs
         where platform wasn't set on every prop).
      3. Today's picks from the JSON cache file (written by scheduler).
      4. Most recent platform picks (any date) from the DB — Railway fallback.
      5. Any JSON cache data regardless of date.

    Returns:
        (picks, pick_date) — list of pick dicts and the ISO date they belong to.
        Returns ([], today) when no data exists at all.
    """
    today = _nba_today_str()
    # Use a single query with COALESCE-style ordering: today's picks first,
    # then most recent. Avoids up to 4 sequential round-trips to PostgreSQL.
    _BEST_PICKS_SQL = """
        SELECT player_name, team, stat_type, prop_line, direction,
               platform, confidence_score, probability_over,
               edge_percentage, tier, pick_date
        FROM all_analysis_picks
        WHERE platform IS NOT NULL AND platform != ''
        ORDER BY
            CASE WHEN pick_date = ? THEN 0 ELSE 1 END,
            pick_date DESC,
            confidence_score DESC
        LIMIT ?"""
    _FALLBACK_SQL = """
        SELECT player_name, team, stat_type, prop_line, direction,
               platform, confidence_score, probability_over,
               edge_percentage, tier, pick_date
        FROM all_analysis_picks
        ORDER BY pick_date DESC, confidence_score DESC
        LIMIT ?"""
    try:
        from tracking.database import _db_read
        # ── Single query: today's platform picks, fallback to most recent ──
        rows = _db_read(_BEST_PICKS_SQL, (today, limit))
        if rows:
            row_date = rows[0].get("pick_date", today)
            return rows, row_date

        # ── Any picks regardless of platform ──────────────────────────
        rows = _db_read(_FALLBACK_SQL, (limit,))
        if rows:
            return rows, rows[0].get("pick_date", today)

        # ── JSON cache (written by slate_worker) ──────────────────────
        cache_result = _load_picks_from_cache(limit)
        if cache_result[0]:
            return cache_result

        return [], today
    except Exception as exc:
        _logger.debug("_load_top_preview_picks DB: %s", exc)

    # ── Final fallback: JSON cache ──────────────────────────────────────────
    return _load_picks_from_cache(limit)


def _load_picks_from_cache(limit: int = 5) -> tuple[list[dict], str]:
    """Read top picks from ``cache/latest_picks.json``.

    Returns:
        (picks, date_str) — picks list and the ISO date from the cache file.
        Returns ([], "") if the file doesn't exist or is malformed.
    """
    import json as _json
    try:
        cache_path = Path(__file__).resolve().parent.parent / "cache" / "latest_picks.json"
        if cache_path.exists():
            data = _json.loads(cache_path.read_text(encoding="utf-8"))
            picks = data.get("picks", [])
            date_str = data.get("date", "")
            if picks:
                _logger.debug("Loaded %d picks from cache/latest_picks.json (date=%s)", len(picks), date_str)
                return picks[:limit], date_str
    except Exception as exc:
        _logger.debug("_load_picks_from_cache: %s", exc)
    return [], ""


def _build_preview_section_html(picks: list[dict], pick_date: str = "") -> str:
    """Build the 'See What You Get' horizontally-scrolling platform-pick cards.

    Uses the same visual language as the QAM Platform AI Picks cards:
    headshot, team badge, big line number, direction, and metrics row.
    If *picks* is empty, returns a static "no picks yet" state.
    pick_date: ISO date string (YYYY-MM-DD) the picks belong to.
    """
    # ── CSS (self-contained inside the st.html iframe) ──
    # NOTE: No @import for Google Fonts — cross-origin font fetches inside
    # a sandboxed iframe are blocking on mobile and add 500ms-2s per render.
    # System-UI fonts render instantly and look identical on iOS/Android.
    css = """<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter','Space Grotesk',system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:rgba(255,255,255,.7);overflow-y:hidden}
/* Frame — DraftKings-style dark glass */
.pv-frame{background:linear-gradient(168deg,rgba(10,14,28,.98),rgba(8,12,24,.95));border:1px solid rgba(0,213,89,.12);border-radius:20px;overflow:hidden;box-shadow:0 0 60px rgba(0,213,89,.06),0 24px 80px rgba(0,0,0,.6)}
.pv-titlebar{display:flex;align-items:center;gap:6px;padding:10px 14px;background:linear-gradient(90deg,rgba(0,213,89,.04),rgba(45,158,255,.03),rgba(192,132,252,.02));border-bottom:1px solid rgba(0,213,89,.1)}
.pv-dot{width:7px;height:7px;border-radius:50%}.pv-dot.r{background:#f24336}.pv-dot.y{background:#F9C62B}.pv-dot.g{background:#00D559}
.pv-url{flex:1;text-align:center;font-family:'JetBrains Mono',monospace;font-size:.5rem;color:rgba(0,213,89,.3)}
.pv-header{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px}
.pv-title{font-family:'Space Grotesk',sans-serif;font-size:.82rem;font-weight:800;color:#fff;text-transform:uppercase;letter-spacing:.03em}
.pv-title .ai-tag{font-size:.48rem;font-weight:800;color:#080C18;background:linear-gradient(135deg,#00D559,#2D9EFF);padding:2px 8px;border-radius:100px;margin-left:8px;vertical-align:middle;letter-spacing:.08em}
.pv-live{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:800;color:#00D559;background:rgba(0,213,89,.1);border:1px solid rgba(0,213,89,.25);padding:3px 10px;border-radius:100px;text-shadow:0 0 10px rgba(0,213,89,.3);animation:pvLivePulse 2s ease-in-out infinite}
@keyframes pvLivePulse{0%,100%{box-shadow:0 0 0 0 rgba(0,213,89,.3)}50%{box-shadow:0 0 0 6px rgba(0,213,89,0)}}
/* Scroll track */
.pv-scroll{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;scrollbar-width:thin;scrollbar-color:rgba(0,213,89,.25) transparent;padding:6px 16px 16px}
.pv-scroll::-webkit-scrollbar{height:4px}
.pv-scroll::-webkit-scrollbar-track{background:rgba(255,255,255,.02);border-radius:100px}
.pv-scroll::-webkit-scrollbar-thumb{background:linear-gradient(90deg,#00D559,#2D9EFF);border-radius:100px}
.pv-track{display:inline-flex;gap:14px;padding:0}
/* Card — PrizePicks dark slab */
.pv-card{width:210px;flex-shrink:0;background:linear-gradient(168deg,rgba(15,20,35,.95),rgba(8,12,24,.98));border:1px solid rgba(255,255,255,.06);border-radius:18px;position:relative;overflow:hidden;transition:all .3s cubic-bezier(.22,1,.36,1)}
.pv-card:hover{border-color:rgba(0,213,89,.4);transform:translateY(-5px) scale(1.02);box-shadow:0 12px 40px rgba(0,0,0,.5),0 0 30px rgba(0,213,89,.1)}
.pv-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#00D559,#2D9EFF,#c084fc);opacity:.8}
.pv-card::after{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 0%,rgba(0,213,89,.04) 0%,transparent 60%);pointer-events:none}
/* Rank badge */
.pv-rank{position:absolute;top:10px;right:10px;font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:900;color:#080C18;background:linear-gradient(135deg,#00D559,#2D9EFF);padding:2px 8px;border-radius:100px;letter-spacing:.06em}
/* Platform badge */
.pv-status{padding:12px 12px 0;display:flex;align-items:center;gap:6px}
.pv-badge{font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:800;color:#00D559;display:flex;align-items:center;gap:4px;background:rgba(0,213,89,.06);border:1px solid rgba(0,213,89,.12);padding:2px 8px;border-radius:100px}
.pv-badge-icon{font-size:.55rem}
/* Headshot — neon ring glow */
.pv-hs-wrap{text-align:center;padding:10px 0 4px;position:relative}
.pv-hs-wrap::before{content:'';position:absolute;top:50%;left:50%;width:84px;height:84px;transform:translate(-50%,-50%);border-radius:50%;background:conic-gradient(from 0deg,#00D559,#2D9EFF,#c084fc,#00D559);opacity:.25;filter:blur(8px);animation:pvRingSpin 6s linear infinite}
@keyframes pvRingSpin{to{transform:translate(-50%,-50%) rotate(360deg)}}
.pv-headshot{width:76px;height:76px;border-radius:50%;object-fit:cover;border:3px solid rgba(0,213,89,.25);background:rgba(15,20,35,.9);position:relative;z-index:1;box-shadow:0 0 20px rgba(0,213,89,.1)}
/* Info */
.pv-team{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:rgba(0,213,89,.45);text-transform:uppercase;letter-spacing:.12em;text-align:center}
.pv-name{font-family:'Space Grotesk',sans-serif;font-size:.78rem;font-weight:800;color:#fff;text-align:center;line-height:1.2;margin:3px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 10px}
/* Line area */
.pv-line-area{text-align:center;padding:6px 0 8px}
.pv-line{font-family:'JetBrains Mono',monospace;font-size:1.7rem;font-weight:900;color:#fff;line-height:1;text-shadow:0 0 20px rgba(255,255,255,.1)}
.pv-stat{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.1em;margin-top:3px}
/* Direction — bold PrizePicks-style pills */
.pv-dir{text-align:center;padding:4px 0 10px}
.pv-dir span{font-family:'Space Grotesk',sans-serif;font-size:.62rem;font-weight:900;text-transform:uppercase;letter-spacing:.12em;padding:5px 16px;border-radius:8px;display:inline-block}
.pv-dir span.more{color:#fff;background:linear-gradient(135deg,#00D559,#00b84a);border:none;box-shadow:0 4px 16px rgba(0,213,89,.25);text-shadow:0 1px 2px rgba(0,0,0,.3)}
.pv-dir span.less{color:#fff;background:linear-gradient(135deg,#2D9EFF,#1a7de0);border:none;box-shadow:0 4px 16px rgba(45,158,255,.25);text-shadow:0 1px 2px rgba(0,0,0,.3)}
/* Metrics — DraftKings stat row */
.pv-metrics{display:flex;justify-content:space-around;padding:10px 8px;border-top:1px solid rgba(0,213,89,.08);background:rgba(0,213,89,.02)}
.pv-metric{text-align:center}
.pv-metric-val{font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:800;color:#00D559}
.pv-metric-label{font-family:'JetBrains Mono',monospace;font-size:.36rem;font-weight:700;color:rgba(255,255,255,.2);text-transform:uppercase;letter-spacing:.08em;margin-top:1px}
/* hint */
.pv-hint{text-align:center;margin-top:10px;font-size:.55rem;color:rgba(0,213,89,.25);font-style:normal;font-family:'JetBrains Mono',monospace;letter-spacing:.05em}
@media(max-width:520px){.pv-card{width:180px}.pv-line{font-size:1.3rem}.pv-name{font-size:.7rem}.pv-headshot{width:64px;height:64px}.pv-hs-wrap::before{width:72px;height:72px}.pv-header{padding:10px 12px 8px}.pv-title{font-size:.72rem}}
@media(max-width:380px){.pv-card{width:155px}.pv-line{font-size:1.1rem}.pv-name{font-size:.62rem}.pv-headshot{width:54px;height:54px}.pv-hs-wrap::before{width:62px;height:62px}.pv-metrics{padding:6px 4px}.pv-metric-val{font-size:.55rem}.pv-dir span{font-size:.52rem;padding:4px 12px}.pv-header{padding:8px 10px 6px}.pv-title{font-size:.65rem}.pv-scroll{padding:4px 10px 12px}}
</style>"""

    # ── Build cards ──
    if not picks:
        # No data yet — show "updating" state, never fake player names
        return (
            f'{css}'
            f'<div class="pv-frame">'
            f'<div class="pv-titlebar"><div class="pv-dot r"></div><div class="pv-dot y"></div>'
            f'<div class="pv-dot g"></div>'
            f'<div class="pv-url">smartpickspro.com &middot; Neural Engine v3.2</div></div>'
            f'<div class="pv-header"><div class="pv-title">&#9889; AI Picks Today</div>'
            f'<div class="pv-live">&#x23F3; UPDATING</div></div>'
            f'<div style="text-align:center;padding:48px 24px 52px;">'
            f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:2rem;margin-bottom:14px;opacity:.25;">&#9889;</div>'
            f'<div style="font-family:\'Space Grotesk\',sans-serif;font-weight:700;font-size:.85rem;color:rgba(255,255,255,.5);margin-bottom:8px;">Analysis runs tonight</div>'
            f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:.55rem;color:rgba(0,213,89,.3);letter-spacing:.08em;">QAM processes game lines each evening &mdash; check back after 6 PM ET</div>'
            f'</div>'
            f'</div>'
        )

    # NBA headshot lookup — comprehensive 2024-26 roster
    _PLAYER_IDS: dict[str, str] = {
        # ── A ──
        "bam adebayo": "1628389", "ochai agbaji": "1631106", "nickeil alexander-walker": "1629638",
        "grayson allen": "1628960", "jarrett allen": "1628386", "cole anthony": "1630175",
        "oc anunoby": "1628384", "og anunoby": "1628384", "d'angelo russell": "1626156",
        "deandre ayton": "1629028", "marvin bagley iii": "1628963",
        # ── B ──
        "scottie barnes": "1630567", "paolo banchero": "1631094",
        "desmond bane": "1630217", "harrison barnes": "1628397",
        "lamelo ball": "1630163", "lonzo ball": "1628366",
        "bradley beal": "203078", "malik beasley": "1627736",
        "jordan clarkson": "203903", "devin booker": "1626164",
        "mikal bridges": "1628969", "jaylen brown": "1627759",
        "jalen brunson": "1628973", "jimmy butler": "202710",
        "jalen green": "1630224", "dillon brooks": "1628415",
        # ── C ──
        "alex caruso": "1627936", "jevon carter": "1628975",
        "wendell carter jr.": "1628976", "wendell carter jr": "1628976",
        "brandon clarke": "1629634", "john collins": "1628381",
        "mike conley": "201144", "cade cunningham": "1630595",
        "stephen curry": "201939", "seth curry": "203552",
        "anthony davis": "203076",
        # ── D ──
        "demar derozan": "201942", "luguentz dort": "1629652", "lu dort": "1629652",
        "luka dončić": "1629029", "luka doncic": "1629029",
        "kevin durant": "201142", "jalen duren": "1631105",
        "anthony edwards": "1630162",
        # ── E-F ──
        "joel embiid": "203954",
        "de'aaron fox": "1628368", "deaaron fox": "1628368",
        "markelle fultz": "1628365", "evan fournier": "203095",
        "paolo banchero": "1631094",
        # ── G ──
        "darius garland": "1629636",
        "shai gilgeous-alexander": "1628983",
        "rudy gobert": "203497",
        "aaron gordon": "203932",
        "jerami grant": "203924",
        "josh giddey": "1630581",
        "paul george": "202331",
        "taj gibson": "201959",
        "eric gordon": "201569",
        "devonte' graham": "1628984",
        "jalen green": "1630224",
        "giannis antetokounmpo": "203507",
        # ── H ──
        "james harden": "201935", "tobias harris": "203086",
        "josh hart": "1628404", "tyler herro": "1629639",
        "buddy hield": "1627741", "jrue holiday": "201950",
        "chet holmgren": "1631096", "al horford": "201143",
        "de'andre hunter": "1629631",
        # ── I-J ──
        "brandon ingram": "1627742", "kyrie irving": "202681",
        "jaren jackson jr.": "1628991", "jaren jackson jr": "1628991",
        "lebron james": "2544", "lebron james jr": "1641730",
        "cam johnson": "1629661", "keldon johnson": "1629640",
        "jalen johnson": "1630552", "nikola jokić": "203999",
        "nikola jokic": "203999", "herbert jones": "1630529",
        "tre jones": "1630200", "derrick jones jr.": "1627884",
        "tyus jones": "1626145",
        # ── K ──
        "franz wagner": "1630532", "mitch wagner": "1630532",
        "walker kessler": "1631108",
        "coby white": "1629632",
        "karl-anthony towns": "1626157",
        "kawhi leonard": "202695",
        "zach lavine": "203897",
        # ── L ──
        "anfernee simons": "1629014",
        "damian lillard": "203081", "nassir little": "1629642",
        "kevon looney": "1626172", "brook lopez": "201572",
        "trey murphy iii": "1630530",
        # ── M ──
        "terance mann": "1629611", "lauri markkanen": "1628374",
        "tyrese maxey": "1630178", "bennedict mathurin": "1631097",
        "donovan mitchell": "1628378", "evan mobley": "1630596",
        "ja morant": "1629630", "dejounte murray": "1627749",
        "jamal murray": "1627750", "mike muscala": "203488",
        "khris middleton": "203114",
        # ── N-O ──
        "andrew nembhard": "1631109", "aaron nesmith": "1630174",
        "josh okogie": "1629006",
        "victor oladipo": "203506",
        "kelly oubre jr.": "1626162", "kelly oubre jr": "1626162",
        # ── P ──
        "chris paul": "101108", "jordan poole": "1629673",
        "bobby portis": "1626171", "kristaps porzingis": "204001",
        "julius randle": "203944", "austin reaves": "1630559",
        # ── R ──
        "cam reddish": "1629629",
        "terry rozier": "1626179",
        "domantas sabonis": "1627734",
        # ── S ──
        "pascal siakam": "1627783", "anfernee simons": "1629014",
        "jabari smith jr.": "1631095", "jabari smith jr": "1631095",
        "jalen smith": "1630188",
        "marcus smart": "203935",
        "jaden springer": "1630531",
        "jayson tatum": "1628369",
        "derrick white": "1628401",
        # ── T ──
        "trae young": "1629027", "thaddeus young": "201152",
        "andrew wiggins": "203952",
        # ── V-W ──
        "nikola vučević": "202696", "nikola vucevic": "202696",
        "moritz wagner": "1629021", "franz wagner": "1630532",
        "kemba walker": "202689",
        "victor wembanyama": "1641705",
        "russell westbrook": "201566",
        "coby white": "1629632",
        "derrick white": "1628401",
        "andrew wiggins": "203952",
        "zion williamson": "1629627",
        "jalen williams": "1631114",
        # ── Y-Z ──
        "trae young": "1629027",
        "ivica zubac": "1627826",
        # ── Additional veterans commonly found in props ──
        "tyrese haliburton": "1630169", "ben simmons": "1627732",
        "nicolas claxton": "1629651", "nic claxton": "1629651",
        "immanuel quickley": "1630193", "iq": "1630193",
        "rj barrett": "1629628", "r.j. barrett": "1629628",
        "naz reid": "1629675", "isaiah hartenstein": "1629631",
        "gary trent jr.": "1629018", "gary trent jr": "1629018",
        "donte divincenzo": "1629056", "donte di vincenzo": "1629056",
        "michael porter jr.": "1629008", "michael porter jr": "1629008",
        "peyton watson": "1631122", "christian braun": "1631102",
        "jaime jaquez jr.": "1641714", "jaime jaquez jr": "1641714",
        "scoot henderson": "1641711", "ausar thompson": "1641712",
        "amen thompson": "1641713", "bilal coulibaly": "1641715",
        "gradey dick": "1641716", "dereck lively ii": "1641717",
        "dereck lively": "1641717", "brandon miller": "1641718",
        "anthony black": "1641719", "jordan hawkins": "1641737",
        "keyonte george": "1641738", "g.g. jackson": "1641739",
        "gg jackson": "1641739", "cody williams": "1641740",
        "noah clowney": "1641742", "jarace walker": "1641743",
        "clint capela": "203991", "reggie jackson": "202704",
        "de'anthony melton": "1629001", "deanthony melton": "1629001",
        "precious achiuwa": "1630173", "matisse thybulle": "1629680",
        "shake milton": "1629003", "malaki branham": "1631120",
        "julian champagnie": "1631115", "jalen pickett": "1641744",
        "markquis nowell": "1641745", "svi mykhailiuk": "1629057",
        "pat connaughton": "1626192", "kyle lowry": "200768",
        "bogdan bogdanovic": "203992", "bojan bogdanovic": "202711",
        "reggie bullock": "1626161", "monte morris": "1628409",
        "quentin grimes": "1630534", "cam thomas": "1631111",
        "nick smith jr.": "1641746", "nick smith jr": "1641746",
        "toumani camara": "1641747", "maxwell lewis": "1641748",
        "leonard miller": "1641749", "ryan rollins": "1631125",
        # ── Rookies / recent call-ups 2025-26 ──
        "daniss jenkins": "1642250", "zach edey": "1641724",
        "reed sheppard": "1641722", "dalton knecht": "1641723",
        "stephon castle": "1641721", "ron holland ii": "1641725",
        "donovan clingan": "1641726", "rob dillingham": "1641727",
        "tidjane salaun": "1641728", "ja'kobe walter": "1641729",
        "matas buzelis": "1641731", "devin carter": "1641732",
        "carlton carrington": "1641733", "tristan da silva": "1641734",
        "kel'el ware": "1641735", "bub carrington": "1641733",
        "alex sarr": "1641720", "yves missi": "1641736",
    }

    # ── Build normalized lookup once per call (O(n) dict comprehension) ─────
    # Strips accents, apostrophes, periods, and suffixes so lookups are
    # resilient to "Nikola Jokić" vs "Nikola Jokic", "De'Aaron Fox" vs
    # "Deaaron Fox", "Jaren Jackson Jr." vs "Jaren Jackson Jr", etc.
    import unicodedata as _ucd
    import re as _re_mod

    def _norm_pname(n: str) -> str:
        n = _ucd.normalize("NFKD", n).encode("ASCII", "ignore").decode("ASCII")
        n = _re_mod.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv)$", "", n, flags=_re_mod.IGNORECASE)
        return _re_mod.sub(r"[.''\u2019-]", "", n).lower().strip()

    _PLAYER_IDS_NORM: dict[str, str] = {
        _norm_pname(k): v for k, v in _PLAYER_IDS.items()
    }

    def _lookup_pid(player_name: str, team: str = "") -> str:
        """Return NBA CDN player-ID string, '' if not found."""
        norm = _norm_pname(player_name)
        # 1. Exact normalized match
        if norm in _PLAYER_IDS_NORM:
            return _PLAYER_IDS_NORM[norm]
        # 2. Token-subset: every token in the input must appear in the lookup key
        #    handles "Shai" → "shai gilgeous alexander", partial names from DB
        tokens = set(norm.split())
        if tokens:
            for key, pid_val in _PLAYER_IDS_NORM.items():
                if tokens.issubset(set(key.split())):
                    return pid_val
        # 3. PlayerIDCache — overrides JSON + optional fuzzy (thefuzz)
        try:
            from data.player_id_cache import PlayerIDCache as _PIC
            _pic = _PIC()
            pid_int = _pic.get_player_id(player_name, team or None)
            if pid_int:
                return str(pid_int)
        except Exception:
            pass
        return ""

    # ── Clean player name (strip stat suffixes like "Lu Dort 3-Pointers Made O/U") ──
    _STAT_SUFFIX_RE = _re_mod.compile(
        r'\s+(?:points|rebounds|assists|steals|blocks|threes|3-pointers?|'
        r'field goals?|free throws?|turnovers?|fantasy|fpts|pts|reb|ast|'
        r'stl|blk|fgm|fga|ftm|fta|made|missed|o/?u|over/?under|'
        r'defensive.rebounds?|offensive.rebounds?).*$',
        _re_mod.IGNORECASE
    )

    cards_html = []
    for idx, pick in enumerate(picks):
        name_raw_full = pick.get("player_name", "Unknown")
        # Clean stat suffixes from name (e.g. "Lu Dort 3-Pointers Made O/U" → "Lu Dort")
        name_raw = _STAT_SUFFIX_RE.sub('', name_raw_full).strip() or name_raw_full
        name = _html_mod.escape(name_raw)
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

        # Always pre-compute initials — used as fallback when CDN image is
        # missing or fails to load (404 for newer/traded players).
        _parts = name_raw.split()
        _initials = (
            (_parts[0][0] + _parts[-1][0]).upper() if len(_parts) >= 2
            else name_raw[0].upper()
        )
        _initials_style = (
            "display:none;align-items:center;justify-content:center;"
            "background:linear-gradient(135deg,rgba(0,213,89,.12),rgba(45,158,255,.08));"
            "font-family:'Space Grotesk',sans-serif;font-size:1.2rem;"
            "font-weight:800;color:rgba(255,255,255,.35);letter-spacing:.03em;"
        )

        # Headshot URL — robust lookup: normalized dict → token-subset → PlayerIDCache
        team_str = (pick.get("team", "") or "").upper()
        pid = _lookup_pid(name_raw, team_str)
        if pid:
            hs_url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{pid}.png"
            hs_html = (
                f'<div class="pv-hs-wrap">'
                f'<img class="pv-headshot" src="{hs_url}" alt="{name}" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'inline-flex\'">'
                f'<div class="pv-headshot" style="{_initials_style}">{_initials}</div>'
                f'</div>'
            )
        else:
            # No player ID found — show initials placeholder
            hs_html = (
                f'<div class="pv-hs-wrap">'
                f'<div class="pv-headshot" style="{_initials_style.replace("display:none", "display:inline-flex")}">'
                f'{_initials}</div>'
                f'</div>'
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

    # Date display in header
    today = _nba_today_str()
    if pick_date == today:
        date_badge = '<span class="ai-tag">LIVE</span>'
        header_date = ""
    elif pick_date:
        try:
            from datetime import datetime as _dt
            _d = _dt.strptime(pick_date, "%Y-%m-%d")
            header_date = f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.42rem;color:rgba(255,255,255,.3);margin-left:8px;font-weight:600;">{_d.strftime("%b").upper()} {_d.day}</span>'
        except Exception:
            header_date = f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.42rem;color:rgba(255,255,255,.3);margin-left:8px;">{pick_date}</span>'
        date_badge = ''
    else:
        date_badge = ''
        header_date = ''

    live_badge = f'<div class="pv-live">&#x25CF; {num_picks} ACTIVE</div>' if pick_date == today else f'<div class="pv-live" style="color:rgba(255,200,50,.8);border-color:rgba(255,200,50,.2);background:rgba(255,200,50,.07);">&#x21BB; {num_picks} PICKS</div>'

    return (
        f'{css}'
        f'<div class="pv-frame">'
        f'<div class="pv-titlebar"><div class="pv-dot r"></div><div class="pv-dot y"></div>'
        f'<div class="pv-dot g"></div>'
        f'<div class="pv-url">smartpickspro.com &middot; Neural Engine v3.2</div></div>'
        f'<div class="pv-header"><div class="pv-title">&#9889; AI Picks Today {date_badge}{header_date}</div>'
        f'{live_badge}</div>'
        f'<div class="pv-scroll"><div class="pv-track">{cards_joined}</div></div>'
        f'</div>'
        f'<div class="pv-hint">&#x2190; SWIPE TO SEE ALL AI PICKS &#x2192;</div>'
    )


def _create_user(email: str, password: str, display_name: str = "") -> bool:
    """Create a new user account. Returns True on success."""
    pw_hash = _hash_password(password)
    clean_email = email.strip().lower()
    for attempt in range(_DB_RETRY_ATTEMPTS):
        try:
            with _AuthConn() as db:
                db.execute(
                    "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                    (clean_email, pw_hash, display_name.strip() or email.split("@")[0]),
                )
            # Mirror the new account into the subscriptions table so every
            # user has a row there regardless of Stripe activity.
            try:
                from utils.auth import _save_subscription_to_db as _save_sub
                _save_sub({
                    "subscription_id": f"acct_{clean_email}",
                    "customer_id":     f"cus_{clean_email}",
                    "customer_email":  clean_email,
                    "status":          "active",
                    "plan_name":       "Free",
                    "period_start":    "",
                    "period_end":      "",
                })
            except Exception as _sub_exc:
                _logger.debug("Subscription mirror failed (non-fatal): %s", _sub_exc)
            return True
        except Exception as exc:
            exc_str = str(exc).lower()
            if ("unique" in exc_str or "duplicate" in exc_str or "integrity" in exc_str):
                return False  # Email already registered
            if "locked" in exc_str and attempt < _DB_RETRY_ATTEMPTS - 1:
                time.sleep(_DB_RETRY_DELAY_SECONDS * (2 ** attempt))
                continue
            _logger.error("Failed to create user: %s", exc)
            return False
    return False


# ── Admin account helpers ─────────────────────────────────────

def seed_admin_account() -> None:
    """Create or update the admin account from environment variables.

    Reads ``ADMIN_EMAIL`` and ``ADMIN_PASSWORD`` from the environment.
    If both are set, ensures an admin user exists in the DB with the
    ``is_admin`` flag set to 1.  If the account already exists, the
    password hash and admin flag are updated.

    Call this once at app startup (idempotent).
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_email or not admin_password:
        return  # No admin env vars configured — nothing to do
    if len(admin_password) < 8:
        _logger.warning("ADMIN_PASSWORD is too short (< 8 chars) — skipping admin seed.")
        return
    pw_hash = _hash_password(admin_password)
    try:
        with _AuthConn() as db:
            existing = db.fetchone("SELECT user_id FROM users WHERE email = ?", (admin_email,))
            if existing:
                db.execute(
                    "UPDATE users SET password_hash = ?, is_admin = 1, plan_tier = 'insider_circle' WHERE email = ?",
                    (pw_hash, admin_email),
                )
            else:
                db.execute(
                    "INSERT INTO users (email, password_hash, display_name, is_admin, plan_tier) "
                    "VALUES (?, ?, ?, 1, 'insider_circle')",
                    (admin_email, pw_hash, "Admin"),
                )
        _logger.info("Admin account seeded for %s", admin_email)
    except Exception as exc:
        _logger.error("Failed to seed admin account: %s", exc)


def is_admin_user() -> bool:
    """Return True if the currently logged-in user has the admin flag."""
    if not is_logged_in():
        return False
    cached = st.session_state.get("_auth_is_admin")
    if cached is not None:
        return bool(cached)
    email = get_logged_in_email()
    if not email:
        return False
    try:
        with _AuthConn() as db:
            row = db.fetchone("SELECT is_admin FROM users WHERE email = ?", (email,))
            is_adm = bool(row and row["is_admin"])
            st.session_state["_auth_is_admin"] = is_adm
            return is_adm
    except Exception:
        return False


def _authenticate_user(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict on success, None on failure."""
    for attempt in range(_DB_RETRY_ATTEMPTS):
        try:
            with _AuthConn() as db:
                user = db.fetchone(
                    "SELECT user_id, email, password_hash, display_name, is_admin, plan_tier FROM users WHERE email = ?",
                    (email.strip().lower(),),
                )
                if not user:
                    return None
                if _verify_password(password, user["password_hash"]):
                    db.execute(
                        "UPDATE users SET last_login_at = datetime('now') WHERE user_id = ?",
                        (user["user_id"],),
                    )
                    return dict(user)
                return None
        except Exception as exc:
            if "locked" in str(exc).lower() and attempt < _DB_RETRY_ATTEMPTS - 1:
                time.sleep(_DB_RETRY_DELAY_SECONDS * (2 ** attempt))
                continue
            _logger.error("Authentication error: %s", exc)
            return None
    return None


def _email_exists(email: str) -> bool:
    """Check if an email is already registered."""
    for attempt in range(_DB_RETRY_ATTEMPTS):
        try:
            with _AuthConn() as db:
                row = db.fetchone("SELECT 1 FROM users WHERE email = ?", (email.strip().lower(),))
                return row is not None
        except Exception as exc:
            if "locked" in str(exc).lower() and attempt < _DB_RETRY_ATTEMPTS - 1:
                time.sleep(_DB_RETRY_DELAY_SECONDS * (2 ** attempt))
                continue
            return False
    return False


# ── Password Reset ────────────────────────────────────────────

def _generate_reset_token(email: str) -> str | None:
    """Generate a 6-digit reset code, store its hash, return the code.

    Token expires after 15 minutes. Returns None if email not found.
    """
    from datetime import datetime, timezone, timedelta
    email_lower = email.strip().lower()
    try:
        with _AuthConn() as db:
            row = db.fetchone("SELECT user_id FROM users WHERE email = ?", (email_lower,))
            if not row:
                return None
            code = f"{secrets.randbelow(900000) + 100000}"
            token_hash = hashlib.sha256(code.encode()).hexdigest()
            expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            db.execute(
                "UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE email = ?",
                (token_hash, expires, email_lower),
            )
            # Email the code to the user -- never display it in the UI
            try:
                from utils.notifications import send_reset_code_email as _send_code
                _send_code(email_lower, code)
            except Exception:
                pass
            return code
    except Exception as exc:
        _logger.error("Failed to generate reset token: %s", exc)
        return None


def _verify_reset_token(email: str, code: str) -> bool:
    """Check if the reset code is valid and not expired."""
    from datetime import datetime, timezone
    email_lower = email.strip().lower()
    try:
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT reset_token, reset_token_expires FROM users WHERE email = ?",
                (email_lower,),
            )
            if not row or not row["reset_token"] or not row["reset_token_expires"]:
                return False
            token_hash = hashlib.sha256(code.strip().encode()).hexdigest()
            if not secrets.compare_digest(token_hash, row["reset_token"]):
                return False
            expires_raw = row["reset_token_expires"]
            # Postgres returns a datetime object; SQLite returns a string
            if isinstance(expires_raw, str):
                expires = datetime.fromisoformat(expires_raw)
            else:
                expires = expires_raw
            if expires.tzinfo is None:
                from datetime import timezone as _tz
                expires = expires.replace(tzinfo=_tz.utc)
            if datetime.now(timezone.utc) > expires:
                return False
            return True
    except Exception:
        return False


def _reset_user_password(email: str, new_password: str) -> bool:
    """Set a new password and clear the reset token."""
    email_lower = email.strip().lower()
    try:
        pw_hash = _hash_password(new_password)
        with _AuthConn() as db:
            db.execute(
                "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL, "
                "failed_login_count = 0, lockout_until = NULL WHERE email = ?",
                (pw_hash, email_lower),
            )
        return True
    except Exception as exc:
        _logger.error("Failed to reset password: %s", exc)
        return False


def change_user_password(email: str, current_password: str, new_password: str) -> tuple[bool, str]:
    """Change password for a logged-in user after verifying current password.

    Returns (success: bool, message: str).
    """
    email_lower = email.strip().lower()
    try:
        with _AuthConn() as db:
            row = db.fetchone("SELECT password_hash FROM users WHERE email = ?", (email_lower,))
            if not row:
                return False, "Account not found."
            if not _verify_password(current_password, row["password_hash"]):
                return False, "Current password is incorrect."
            pw_err = _valid_password(new_password)
            if pw_err:
                return False, pw_err
            if current_password == new_password:
                return False, "New password must be different from your current password."
            pw_hash = _hash_password(new_password)
            db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email_lower))
        return True, "Password changed successfully!"
    except Exception as exc:
        _logger.error("Failed to change password: %s", exc)
        return False, "An unexpected error occurred. Please try again."


# ── Login Rate Limiting ───────────────────────────────────────
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _check_login_lockout(email: str) -> str | None:
    """Return a lockout message if user is rate-limited, else None."""
    from datetime import datetime, timezone
    email_lower = email.strip().lower()
    try:
        with _AuthConn() as db:
            row = db.fetchone(
                "SELECT failed_login_count, lockout_until FROM users WHERE email = ?",
                (email_lower,),
            )
            if not row:
                return None
            lockout_until = row["lockout_until"]
            if lockout_until:
                if isinstance(lockout_until, str):
                    lock_dt = datetime.fromisoformat(lockout_until)
                else:
                    lock_dt = lockout_until
                if lock_dt.tzinfo is None:
                    lock_dt = lock_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now < lock_dt:
                    mins_left = max(1, int((lock_dt - now).total_seconds() / 60))
                    return f"Too many failed attempts. Try again in {mins_left} minute{'s' if mins_left > 1 else ''}."
                # Lockout expired — reset
                db.execute(
                    "UPDATE users SET failed_login_count = 0, lockout_until = NULL WHERE email = ?",
                    (email_lower,),
                )
    except Exception:
        pass
    return None


def _record_failed_login(email: str) -> None:
    """Increment failed login count; lockout after threshold."""
    from datetime import datetime, timezone, timedelta
    email_lower = email.strip().lower()
    try:
        with _AuthConn() as db:
            db.execute(
                "UPDATE users SET failed_login_count = COALESCE(failed_login_count, 0) + 1 WHERE email = ?",
                (email_lower,),
            )
            row = db.fetchone("SELECT failed_login_count FROM users WHERE email = ?", (email_lower,))
            if row and (row["failed_login_count"] or 0) >= _MAX_LOGIN_ATTEMPTS:
                lockout = (datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)).isoformat()
                db.execute(
                    "UPDATE users SET lockout_until = ? WHERE email = ?",
                    (lockout, email_lower),
                )
    except Exception:
        pass


def _clear_failed_logins(email: str) -> None:
    """Reset failed login counter on successful login."""
    try:
        with _AuthConn() as db:
            db.execute(
                "UPDATE users SET failed_login_count = 0, lockout_until = NULL WHERE email = ?",
                (email.strip().lower(),),
            )
    except Exception:
        pass


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

def _set_logged_in(user: dict, _write_storage: bool = True) -> None:
    st.session_state[_SS_LOGGED_IN]  = True
    st.session_state[_SS_USER_EMAIL] = user.get("email", "")
    st.session_state[_SS_USER_NAME]  = user.get("display_name", "")
    st.session_state[_SS_USER_ID]    = user.get("user_id", 0)
    st.session_state["_auth_is_admin"] = bool(user.get("is_admin", 0))
    # Flag: after a fresh login, redirect the user to the Home page so they
    # always land on Smart Pick Pro Home rather than whatever page they were on.
    st.session_state["_redirect_to_home"] = True

    # ── Tier injection: prefer plan_tier column on the user row ──
    # This is the fast, reliable path — no separate subscriptions
    # table lookup needed.  Falls back to a direct users-table lookup
    # when plan_tier is absent (e.g. session restored from cookie where
    # login_sessions doesn't carry plan_tier), and finally to
    # restore_subscription_by_email for Stripe-purchased accounts.
    plan_tier = (user.get("plan_tier") or "").strip()

    # If plan_tier is missing from the session record (cookie restore path),
    # do a fast DB lookup so the user doesn't lose their tier on reload.
    if not plan_tier or plan_tier == "free":
        try:
            _uid = user.get("user_id", 0)
            _email = user.get("email", "")
            with _AuthConn() as _udb:
                if _uid:
                    _urow = _udb.fetchone(
                        "SELECT plan_tier FROM users WHERE user_id = ?", (_uid,)
                    )
                else:
                    _urow = _udb.fetchone(
                        "SELECT plan_tier FROM users WHERE email = ?", (_email,)
                    )
            if _urow:
                plan_tier = (_urow.get("plan_tier") or "").strip()
        except Exception:
            pass

    _TIER_KEY_TO_PLAN = {
        "sharp_iq":       "Sharp IQ",
        "smart_money":    "Smart Money",
        "insider_circle": "Insider Circle",
        "insider":        "Insider Circle",
    }
    if plan_tier and plan_tier != "free":
        plan_name = _TIER_KEY_TO_PLAN.get(plan_tier.lower(), plan_tier)
        st.session_state["_sub_is_premium"]      = True
        st.session_state["_sub_subscription_id"] = f"otp_{user.get('user_id', 0)}"
        st.session_state["_sub_customer_id"]     = f"cus_{user.get('user_id', 0)}"
        st.session_state["_sub_customer_email"]  = user.get("email", "")
        st.session_state["_sub_plan_name"]       = plan_name
        st.session_state["_sub_status"]          = "active"
        st.session_state["_sub_period_end"]      = ""
        import time as _time
        st.session_state["_sub_verified_at"]     = _time.time()
    else:
        # Fallback: look up the subscriptions table (Stripe / otp_ rows)
        try:
            from utils.auth import restore_subscription_by_email as _restore_sub
            _restore_sub(user.get("email", ""))
        except Exception:
            pass

    # Save a session token to session_state so require_login can write the
    # cookie on the NEXT Streamlit run (after st.rerun()).  Rendering the JS
    # component here then calling st.rerun() causes a race — the JS never
    # executes before the rerun discards the render.
    if _write_storage:
        try:
            _tok = secrets.token_urlsafe(32)
            _save_login_session(_tok, user)
            st.session_state["_pending_cookie_token"] = _tok
            # Belt-and-suspenders: write token to query params so it survives
            # any environment where cookies/localStorage are blocked.
            # require_login() will restore the session from ?_st= and then
            # remove it from the URL immediately after restoration.
            try:
                st.query_params["_st"] = _tok
            except Exception:
                pass
        except Exception:
            pass


def is_logged_in() -> bool:
    """Check if the user is logged into an account this session."""
    return bool(st.session_state.get(_SS_LOGGED_IN))


def get_logged_in_email() -> str:
    """Return the logged-in user's email, or ''."""
    return st.session_state.get(_SS_USER_EMAIL, "")


def logout_user() -> None:
    """Clear the login session."""
    # Use the token stored at session-restore time (reliable), falling back
    # to the cookie value (also reliable).  st.query_params["_st"] is only
    # present for <1 Streamlit run and will be empty at logout time.
    try:
        _tok = (
            st.session_state.get("_auth_session_token", "")
            or _get_session_cookie()
        )
        if _tok:
            _delete_session_token(_tok)
        _clear_session_from_storage()
    except Exception:
        pass
    for key in (_SS_LOGGED_IN, _SS_USER_EMAIL, _SS_USER_NAME, _SS_USER_ID,
                "_auth_is_admin", "_auth_session_token", "_spp_bridge_fired"):
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
@import url('https://fonts.googleapis.com/css2?family=Archivo+Black:ital@0;1&family=Syne:wght@700;800;900&family=Space+Grotesk:wght@300;400;500;600;700;800&family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,700;1,800;1,900&family=JetBrains+Mono:wght@400;500;700;800&display=swap');

/* ── Design tokens ───────────────────────────────────────────── */
:root {
    --c-bg:          #05070a;
    --c-surface:     rgba(10,15,20,0.70);
    --c-surface-2:   rgba(10,15,20,0.85);
    --c-border:      rgba(0,255,128,0.10);
    --c-border-hi:   rgba(0,255,128,0.22);
    --c-green:       #00ff80;
    --c-green-dim:   #00cc66;
    --c-green-hi:    #66ffb2;
    --c-green-glow:  rgba(0,255,128,0.20);
    --c-cyan:        #00e5ff;
    --c-cyan-glow:   rgba(0,229,255,0.18);
    --c-blue:        #3B9EFF;
    --c-blue-glow:   rgba(59,158,255,0.14);
    --c-purple:      #c084fc;
    --c-gold:        #F9C62B;
    --c-plasma:      #a3f7e0;
    --c-depth:       linear-gradient(135deg, #050a0f 0%, #020d07 100%);
    --font-head:     'Archivo Black', 'Syne', 'Space Grotesk', sans-serif;
    --font-body:     'Inter', sans-serif;
    --font-mono:     'JetBrains Mono', monospace;
    --glass-blur:    blur(15px);
    --glass-bg:      rgba(10,15,20,0.70);
    --glass-border:  rgba(0,255,128,0.10);
    --ease-spring:   cubic-bezier(0.16, 1, 0.3, 1);
    --ease-out:      cubic-bezier(0.22, 1, 0.36, 1);
    --r-card:        20px;
    --r-card-sm:     14px;
}

/* ── Reset Streamlit chrome ──────────────────────────────────── */
[data-testid="stSidebar"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton,
footer { display: none !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }

html, body {
    overflow-x: hidden !important;
    max-width: 100vw !important;
}

.stApp {
    background: var(--c-bg, #05070a) !important;
    overflow-x: hidden !important;
    max-width: 100% !important;
}
/* Elite AI matrix texture — dual-layer node grid */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        radial-gradient(circle, rgba(0,255,128,0.028) 0.5px, transparent 0.5px),
        radial-gradient(circle, rgba(0,229,255,0.016) 0.5px, transparent 0.5px);
    background-size: 28px 28px, 56px 56px;
    background-position: 0 0, 14px 14px;
    pointer-events: none;
    z-index: 0;
}
/* Global vignette — keeps focus on the central terminal data */
.stApp::after {
    content: '';
    position: fixed;
    inset: 0;
    background: radial-gradient(ellipse at 50% 50%, transparent 40%, rgba(0,0,0,0.72) 100%);
    pointer-events: none;
    z-index: 1;
}

.stApp > [data-testid="stAppViewContainer"] {
    overflow-x: hidden !important;
}

.stApp > [data-testid="stAppViewContainer"] > section.main {
    overflow-x: hidden !important;
}

.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 100px 0 0 0 !important;
    max-width: 100% !important;
    margin: 0 auto !important;
    position: relative;
    z-index: 10;
    overflow-x: hidden !important;
}

html, body, .stApp, .stApp * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Full-bleed wrapper ──────────────────────────────────────── */
.ag-section {
    width: 100%; max-width: 780px; margin: 0 auto;
    padding-left: 28px; padding-right: 28px;
    box-sizing: border-box;
}
.ag-full-bleed {
    width: 100vw; position: relative;
    left: 50%; transform: translateX(-50%);
    padding: 48px 0;
    overflow-x: hidden;
}
.ag-full-bleed .ag-section {
    max-width: 780px; margin: 0 auto;
    padding-left: 28px; padding-right: 28px;
    box-sizing: border-box;
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
    33%      { transform: translate(40px, -30px) scale(1.1); }
    66%      { transform: translate(-30px, 25px) scale(0.92); }
}
@keyframes agOrbFloat2 {
    0%, 100% { transform: translate(0, 0) scale(1) rotate(0deg); }
    50%      { transform: translate(-60px, 30px) scale(1.08) rotate(180deg); }
}
@keyframes agScanline {
    0%   { top: -8%; }
    100% { top: 108%; }
}
@keyframes agDataRain {
    0%   { transform: translateY(-100%); opacity: 0; }
    10%  { opacity: 0.6; }
    90%  { opacity: 0.6; }
    100% { transform: translateY(100vh); opacity: 0; }
}
@keyframes agPulseRing {
    0%   { transform: translate(-50%,-50%) scale(0.8); opacity: 0.4; }
    100% { transform: translate(-50%,-50%) scale(2.5); opacity: 0; }
}
@keyframes agHexFloat {
    0%, 100% { opacity: 0.03; transform: rotate(0deg); }
    50%      { opacity: 0.07; transform: rotate(3deg); }
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
    0%   { transform: scale(0.5) translateY(12px); opacity: 0; }
    60%  { transform: scale(1.08) translateY(-2px); }
    100% { transform: scale(1) translateY(0); opacity: 1; }
}
@keyframes agLogoGlow {
    0%, 100% { filter: drop-shadow(0 0 24px rgba(0, 213, 89, 0.2)) drop-shadow(0 0 50px rgba(45, 158, 255, 0.1)); transform: scale(1); }
    50%      { filter: drop-shadow(0 0 45px rgba(0, 213, 89, 0.35)) drop-shadow(0 0 80px rgba(45, 158, 255, 0.2)); transform: scale(1.03); }
}
@keyframes agTickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
@keyframes agLivePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0, 213, 89, 0.5); }
    50%      { box-shadow: 0 0 0 5px rgba(0, 213, 89, 0); }
}
@keyframes agHeroTextReveal {
    0%   { opacity: 0; transform: translateY(40px) scale(0.96); filter: blur(8px); }
    100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}
@keyframes agHeroGlowPulse {
    0%, 100% { text-shadow: 0 0 40px rgba(0, 213, 89, 0.15), 0 0 80px rgba(45, 158, 255, 0.08); }
    50%      { text-shadow: 0 0 60px rgba(0, 213, 89, 0.3), 0 0 120px rgba(45, 158, 255, 0.15); }
}
@keyframes agRingRotate {
    0%   { transform: translate(-50%, -50%) rotate(0deg); }
    100% { transform: translate(-50%, -50%) rotate(360deg); }
}
@keyframes agProofCardReveal {
    0%   { opacity: 0; transform: translateY(24px) scale(0.92); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes agStarFloat {
    0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.6; }
    50%      { transform: translateY(-10px) rotate(180deg); opacity: 1; }
}

/* ── Scroll-triggered fade-up animations ─────────────────────── */
@keyframes agRevealFallback {
    to { opacity: 1; transform: translateY(0); }
}
@keyframes agCursorBlink {
    0%, 49% { opacity: 1; }
    50%, 100% { opacity: 0; }
}
@keyframes agPlasmaFlow {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes agBeamSweep {
    0%   { transform: scaleX(0); opacity: 0; }
    15%  { transform: scaleX(1); opacity: 1; }
    85%  { transform: scaleX(1); opacity: 1; }
    100% { transform: scaleX(0); opacity: 0; }
}
.ag-reveal {
    opacity: 0;
    transform: translateY(32px);
    transition: opacity 0.7s cubic-bezier(0.22, 1, 0.36, 1),
                transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
    animation: agRevealFallback 0.6s 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.ag-reveal.ag-visible {
    opacity: 1;
    transform: translateY(0);
    animation: none;
}
.ag-reveal-delay-1 { transition-delay: 0.1s; animation-delay: 1.3s; }
.ag-reveal-delay-2 { transition-delay: 0.2s; animation-delay: 1.4s; }
.ag-reveal-delay-3 { transition-delay: 0.3s; animation-delay: 1.5s; }

/* ── Background ──────────────────────────────────────────────── */
.ag-bg {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(ellipse at 50% -5%,  rgba(0,255,128,0.22)   0%, transparent 42%),
        radial-gradient(ellipse at 88% 78%,  rgba(0,229,255,0.16)   0%, transparent 38%),
        radial-gradient(ellipse at 10% 52%,  rgba(0,255,128,0.10)   0%, transparent 38%),
        radial-gradient(ellipse at 50% 108%, rgba(0,229,255,0.07)   0%, transparent 30%),
        linear-gradient(135deg, #050a0f 0%, #020d07 100%);
    overflow: hidden;
}
/* Premium node-grid overlay */
.ag-bg::before {
    content: ''; position: absolute; inset: 0;
    background: url("data:image/svg+xml,%3Csvg width='48' height='48' xmlns='http://www.w3.org/2000/svg'%3E%3Cdefs%3E%3Cpattern id='p' width='48' height='48' patternUnits='userSpaceOnUse'%3E%3Cpath d='M48 0L0 0 0 48' stroke='rgba(255,255,255,0.022)' stroke-width='0.4' fill='none'/%3E%3Ccircle cx='0' cy='0' r='1.2' fill='rgba(0,232,122,0.09)'/%3E%3Ccircle cx='48' cy='0' r='0.8' fill='rgba(59,158,255,0.06)'/%3E%3Ccircle cx='0' cy='48' r='0.8' fill='rgba(59,158,255,0.06)'/%3E%3Ccircle cx='24' cy='24' r='0.6' fill='rgba(192,132,252,0.04)'/%3E%3C/pattern%3E%3C/defs%3E%3Crect fill='url(%23p)' width='100%25' height='100%25'/%3E%3C/svg%3E");
    opacity: 1;
}
/* Precision scanline — cinematic sweep */
.ag-bg::after {
    content: ''; position: absolute; left: 0; right: 0;
    height: 60px; top: -8%;
    background: linear-gradient(180deg,
        transparent 0%,
        rgba(0,232,122,0.02)   30%,
        rgba(163,247,224,0.06) 50%,
        rgba(0,232,122,0.02)   70%,
        transparent 100%);
    animation: agScanline 14s linear infinite;
    pointer-events: none;
}
.ag-orb {
    position: absolute; border-radius: 50%; pointer-events: none;
    filter: blur(130px); opacity: 0.9;
    animation: agOrbFloat 20s ease-in-out infinite;
}
.ag-orb-1 {
    width: 800px; height: 800px; top: -220px; left: -180px;
    background: radial-gradient(circle, rgba(0,255,128,0.28) 0%, rgba(0,204,102,0.10) 50%, transparent 70%);
}
.ag-orb-2 {
    width: 700px; height: 700px; bottom: -180px; right: -160px;
    background: radial-gradient(circle, rgba(0,229,255,0.22) 0%, rgba(0,160,200,0.08) 50%, transparent 70%);
    animation: agOrbFloat2 24s ease-in-out infinite;
}
.ag-orb-3 {
    width: 580px; height: 580px; top: 35%; left: 50%;
    transform: translateX(-50%);
    background: radial-gradient(circle, rgba(0,229,255,0.06) 0%, rgba(0,255,128,0.03) 60%, transparent 75%);
    animation-delay: -12s;
}
/* Pulse ring — AI "thinking" radar */
.ag-pulse-ring {
    position: absolute; top: 30%; left: 50%;
    width: 400px; height: 400px; border-radius: 50%;
    border: 1px solid rgba(0, 213, 89, 0.08);
    animation: agPulseRing 4s ease-out infinite;
    pointer-events: none;
}
.ag-pulse-ring-2 {
    position: absolute; top: 30%; left: 50%;
    width: 400px; height: 400px; border-radius: 50%;
    border: 1px solid rgba(45, 158, 255, 0.06);
    animation: agPulseRing 4s 2s ease-out infinite;
    pointer-events: none;
}

/* \u2500\u2500 Section divider \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */
.ag-divider {
    height: 1px; margin: 48px 40px; position: relative;
    background: linear-gradient(90deg, transparent, rgba(0,232,122,0.2), rgba(163,247,224,0.25), rgba(59,158,255,0.15), rgba(192,132,252,0.1), transparent);
    box-shadow: 0 0 24px rgba(0,232,122,0.06);
}
.ag-divider::after {
    content: ''; position: absolute; top: -3px; left: 50%; transform: translateX(-50%);
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--c-plasma); box-shadow: 0 0 16px rgba(163,247,224,0.5);
}

/* ── App Preview Mockup ──────────────────────────────────────── */
.ag-app-preview { margin: 0 20px 36px; }
.ag-mockup { max-width: 680px; margin: 0 auto; }
.ag-mockup-window {
    background: rgba(5, 7, 10, 0.96);
    border: 1px solid var(--glass-border);
    border-radius: 16px; overflow: hidden;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.8), 0 0 60px rgba(0,255,128,0.05), 0 0 0 1px rgba(0,255,128,0.04) inset;
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
}
.ag-mockup-titlebar {
    display: flex; align-items: center; gap: 6px;
    padding: 10px 14px;
    background: rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.ag-mockup-dot { width: 8px; height: 8px; border-radius: 50%; }
.ag-mockup-url {
    flex: 1; text-align: center;
    font-family: 'JetBrains Mono', monospace; font-size: 0.48rem;
    color: rgba(255,255,255,0.2);
}
.ag-mockup-body { display: flex; min-height: 280px; }
.ag-mockup-sidebar {
    width: 130px; flex-shrink: 0;
    background: rgba(255,255,255,0.015);
    border-right: 1px solid rgba(255,255,255,0.04);
    padding: 10px 0;
}
.ag-mockup-sb-item {
    font-family: 'Space Grotesk', sans-serif; font-size: 0.58rem; font-weight: 600;
    color: rgba(255,255,255,0.3); padding: 8px 12px;
    cursor: default; transition: all 0.2s;
    border-left: 2px solid transparent;
}
.ag-mockup-sb-item.active {
    color: #00D559; background: rgba(0,213,89,0.06);
    border-left-color: #00D559;
}
.ag-mockup-main { flex: 1; padding: 12px; overflow: hidden; }
.ag-mockup-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 10px;
}
.ag-mockup-badge-live {
    font-family: 'JetBrains Mono', monospace; font-size: 0.5rem; font-weight: 700;
    color: #00D559; background: rgba(0,213,89,0.08);
    border: 1px solid rgba(0,213,89,0.15);
    padding: 3px 10px; border-radius: 100px;
}
.ag-mockup-filter {
    font-family: 'JetBrains Mono', monospace; font-size: 0.45rem; font-weight: 700;
    color: #c084fc; background: rgba(192,132,252,0.08);
    border: 1px solid rgba(192,132,252,0.15);
    padding: 3px 10px; border-radius: 100px;
}
.ag-mockup-table { width: 100%; }
.ag-mockup-row {
    display: grid; grid-template-columns: 1.4fr 0.6fr 0.6fr 0.6fr 0.7fr 0.8fr;
    gap: 4px; padding: 6px 8px; font-size: 0.52rem;
    font-family: 'JetBrains Mono', monospace;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    color: rgba(255,255,255,0.5);
    align-items: center;
}
.ag-mockup-row.head {
    font-family: 'Space Grotesk', sans-serif; font-weight: 700;
    color: rgba(255,255,255,0.25); font-size: 0.45rem;
    text-transform: uppercase; letter-spacing: 0.06em;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.ag-mockup-row .player { color: rgba(255,255,255,0.8); font-weight: 600; font-family: 'Space Grotesk', sans-serif; }
.ag-mockup-row .safe { font-weight: 800; }
.ag-mockup-row .safe.high { color: #c084fc; }
.ag-mockup-row .safe.mid { color: #fbbf24; }
.ag-mockup-row .edge { color: #00D559; font-weight: 700; }
.ag-mockup-row .over { color: #00D559; font-weight: 800; }
.ag-mockup-row .under { color: #60a5fa; font-weight: 800; }
.ag-mockup-footer-note {
    text-align: center; font-size: 0.42rem; color: rgba(255,255,255,0.15);
    margin-top: 8px; font-style: italic;
}
.ag-mockup-caption {
    display: flex; justify-content: center; gap: 16px;
    margin-top: 14px; flex-wrap: wrap;
}
.ag-mockup-tag {
    font-family: 'Space Grotesk', sans-serif; font-size: 0.6rem; font-weight: 600;
    color: rgba(0,213,89,0.5);
    background: rgba(0,213,89,0.03);
    border: 1px solid rgba(0,213,89,0.08);
    padding: 4px 14px; border-radius: 100px;
}
@media (max-width: 520px) {
    .ag-mockup-sidebar { width: 80px; }
    .ag-mockup-sb-item { font-size: 0.45rem; padding: 6px 8px; }
    .ag-mockup-row { font-size: 0.42rem; grid-template-columns: 1.2fr 0.5fr 0.5fr 0.5fr 0.6fr 0.7fr; }
    .ag-mockup-body { min-height: 220px; }
}

/* ── Ticker bar — terminal-grade ────────────────────────────── */
.ag-ticker {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    height: 36px; display: flex; align-items: center;
    background: rgba(2, 5, 9, 0.97);
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border-bottom: 1px solid rgba(255,255,255,0.06);
    overflow: hidden;
    box-shadow: 0 1px 0 rgba(0,232,122,0.08), 0 4px 32px rgba(0,0,0,0.6);
}
.ag-ticker::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(0,232,122,0.5) 20%, rgba(59,158,255,0.35) 50%, rgba(192,132,252,0.25) 80%, transparent 100%);
}
.ag-ticker::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1.5px;
    background: linear-gradient(90deg, var(--c-green), var(--c-blue), var(--c-purple), var(--c-gold), var(--c-green));
    background-size: 400% 100%;
    animation: agBarSlide 8s linear infinite;
    opacity: 0.8;
}
.ag-ticker-track {
    display: flex; align-items: center; white-space: nowrap;
    animation: agTickerScroll 55s linear infinite;
}
.ag-ticker-item {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 28px; font-size: 0.6rem; font-weight: 500;
    color: rgba(255,255,255,0.28);
    font-family: var(--font-mono);
    letter-spacing: 0.03em;
}
.ag-ticker-item .sep { color: rgba(255,255,255,0.1); margin: 0 2px; }
.ag-ticker-item .v {
    font-weight: 700; color: var(--c-green);
    text-shadow: 0 0 14px rgba(0,255,128,0.30);
    font-variant-numeric: tabular-nums;
}
.ag-ticker-item .lbl { color: rgba(255,255,255,0.18); font-size: 0.52rem; text-transform: uppercase; letter-spacing: 0.08em; }
.ag-ticker-live {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(0,232,122,0.08);
    border: 1px solid rgba(0,232,122,0.22);
    padding: 2px 10px; border-radius: 4px;
    font-size: 0.52rem; font-weight: 800; color: var(--c-green);
    text-transform: uppercase; letter-spacing: 0.1em;
    text-shadow: 0 0 10px rgba(0,232,122,0.35);
    flex-shrink: 0;
}
.ag-ticker-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--c-green); animation: agLivePulse 2s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(0,232,122,0.6);
}

/* ── Logo ────────────────────────────────────────────────────── */
.ag-logo-section {
    text-align: center;
    padding-top: 64px;
    margin-bottom: 8px;
    animation: agFadeUp 0.6s var(--ease-out) both;
    position: relative;
}
.ag-logo-img {
    width: 220px;
    height: auto;
    animation: agLogoGlow 5s ease-in-out infinite;
    position: relative;
    z-index: 2;
    filter: drop-shadow(0 0 32px rgba(0,232,122,0.22)) drop-shadow(0 0 64px rgba(59,158,255,0.1));
}
/* Primary orbit ring */
.ag-logo-ring {
    position: absolute; top: 50%; left: 50%;
    width: 270px; height: 270px;
    border: 0.5px solid rgba(0,232,122,0.14);
    border-radius: 50%;
    animation: agRingRotate 28s linear infinite;
    pointer-events: none;
}
.ag-logo-ring::before {
    content: ''; position: absolute; top: -3px; left: 50%;
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--c-green);
    box-shadow: 0 0 16px rgba(0,232,122,0.7), 0 0 32px rgba(0,232,122,0.3);
}
/* Second counter-rotating ring */
.ag-logo-ring-2 {
    position: absolute; top: 50%; left: 50%;
    width: 310px; height: 310px; margin: -155px 0 0 -155px;
    border: 0.5px solid rgba(59,158,255,0.08);
    border-radius: 50%;
    animation: agRingRotate 45s linear infinite reverse;
    pointer-events: none;
}
.ag-logo-ring-2::before {
    content: ''; position: absolute; bottom: -3px; right: 20%;
    width: 4px; height: 4px; border-radius: 50%;
    background: var(--c-blue);
    box-shadow: 0 0 12px rgba(59,158,255,0.6);
}

/* ── Hero (Cinematic / Elite) ──────────────────────────────── */
@keyframes agHeroL1In {
    0%   { opacity: 0; transform: translateY(-60px) scale(1.05); filter: blur(16px); }
    100% { opacity: 1; transform: translateY(0)     scale(1);    filter: blur(0); }
}
@keyframes agHeroL2In {
    0%   { opacity: 0; transform: translateX(-50px); filter: blur(10px); }
    100% { opacity: 1; transform: translateX(0);     filter: blur(0); }
}
@keyframes agHeroItsUsIn {
    0%   { opacity: 0; transform: translateY(80px) scale(0.82); filter: blur(28px); }
    65%  { filter: blur(2px); }
    100% { opacity: 1; transform: translateY(0)    scale(1);    filter: blur(0); }
}
@keyframes agHeroDividerIn {
    0%   { transform: scaleX(0); opacity: 0; }
    100% { transform: scaleX(1); opacity: 1; }
}
@keyframes agHeroCinemaGlow {
    0%,100% { box-shadow: 0 0 0 1px rgba(0,232,122,0.15), 0 0 160px rgba(0,232,122,0.13), 0 80px 160px rgba(0,0,0,0.90), inset 0 1px 0 rgba(255,255,255,0.07); }
    50%      { box-shadow: 0 0 0 1px rgba(0,232,122,0.28), 0 0 240px rgba(0,232,122,0.22), 0 80px 160px rgba(0,0,0,0.90), inset 0 1px 0 rgba(255,255,255,0.10); }
}
@keyframes agHeroScan {
    0%   { top: 0%; opacity: 0; }
    5%   { opacity: 1; }
    95%  { opacity: 1; }
    100% { top: 100%; opacity: 0; }
}
.ag-hero {
    text-align: center;
    padding: 104px 56px 88px;
    max-width: 1280px; margin: 0 auto;
    position: relative;
    background:
        linear-gradient(180deg, rgba(0,18,12,0.98) 0%, rgba(3,10,20,0.99) 50%, rgba(4,8,16,1) 100%);
    border: 1px solid rgba(0,232,122,0.25);
    border-radius: 28px;
    overflow: hidden;
    animation: agHeroCinemaGlow 5s ease-in-out infinite;
}
/* Top accent bar */
.ag-hero::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, transparent 0%, var(--c-green) 25%, var(--c-plasma) 50%, var(--c-blue) 75%, transparent 100%);
    background-size: 300% 100%;
    animation: agPlasmaFlow 4s ease infinite;
}
/* Animated scan line */
.ag-hero::after {
    content: '';
    position: absolute; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(0,232,122,0.22) 50%, transparent 100%);
    animation: agHeroScan 8s linear infinite;
    pointer-events: none;
}
/* Ambient radial glows */
.ag-hero-bg {
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background:
        radial-gradient(ellipse 80% 70% at 10% 30%, rgba(0,232,122,0.13) 0%, transparent 55%),
        radial-gradient(ellipse 60% 80% at 90% 20%, rgba(59,158,255,0.10) 0%, transparent 50%),
        radial-gradient(ellipse 50% 50% at 50% 95%, rgba(0,232,122,0.08) 0%, transparent 55%),
        radial-gradient(ellipse 40% 40% at 50% 50%, rgba(59,158,255,0.04) 0%, transparent 70%);
    pointer-events: none;
}
.ag-hero-inner { position: relative; z-index: 1; }

.ag-hero-ai-badge {
    display: inline-flex; align-items: center; gap: 10px;
    font-family: var(--font-mono);
    font-size: 0.72rem; font-weight: 700;
    color: var(--c-plasma); background: rgba(163,247,224,0.06);
    border: 1px solid rgba(163,247,224,0.28);
    padding: 10px 28px; border-radius: 8px;
    text-transform: uppercase; letter-spacing: 0.18em;
    margin-bottom: 28px;
    animation: agHeroTextReveal 0.8s 0.05s var(--ease-out) both;
    box-shadow: 0 0 32px rgba(163,247,224,0.10), inset 0 0 0 1px rgba(163,247,224,0.05);
    position: relative; overflow: hidden;
}
.ag-hero-ai-badge::after {
    content: ''; position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(163,247,224,0.08), transparent);
    animation: agShimmer 4s ease-in-out infinite;
}
.ag-hero-ai-badge .ai-cursor {
    display: inline-block; width: 1px; height: 0.65em;
    background: var(--c-plasma); margin-left: 2px;
    animation: agCursorBlink 1.1s step-end infinite;
    vertical-align: middle;
}
.ag-hero-ai-badge .ai-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--c-green);
    box-shadow: 0 0 12px rgba(0,232,122,0.70);
    animation: agLivePulse 2s ease-in-out infinite;
}
.ag-hero h1 {
    font-family: var(--font-head);
    font-weight: 900;
    line-height: 0.88;
    color: #fff; margin: 0;
    text-transform: uppercase;
    will-change: transform;
}
.ag-hero h1 .hero-l1 {
    display: block;
    font-size: clamp(4.35rem, 10.9vw, 9.75rem);
    letter-spacing: -0.06em;
    text-shadow:
        0 0 220px rgba(0,232,122,0.16),
        0 0 480px rgba(59,158,255,0.08),
        0 8px 0 rgba(0,0,0,0.65);
    animation: agHeroL1In 1.0s 0.10s var(--ease-out) both;
    color: #fff;
}
.ag-hero h1 .hero-l2 {
    display: block;
    font-size: clamp(5.075rem, 12.7vw, 11.375rem);
    letter-spacing: -0.05em;
    color: rgba(195,215,240,0.72);
    text-shadow: 0 4px 0 rgba(0,0,0,0.5);
    animation: agHeroL2In 0.9s 0.40s var(--ease-out) both;
    margin-top: 2px;
}
.ag-hero-divider {
    width: 80px; height: 2px; margin: 18px auto 16px;
    background: linear-gradient(90deg, transparent, rgba(0,232,122,0.6), rgba(59,158,255,0.5), transparent);
    border-radius: 2px;
    animation: agHeroDividerIn 0.8s 0.58s cubic-bezier(0.22,1,0.36,1) both;
    box-shadow: 0 0 20px rgba(0,232,122,0.4);
    transform-origin: center;
}
.ag-hero-its-us {
    font-family: var(--font-head);
    font-weight: 900;
    text-transform: uppercase;
    font-size: clamp(5.8rem, 14.5vw, 13rem);
    letter-spacing: -0.03em;
    line-height: 0.95;
    background: linear-gradient(135deg, var(--c-green) 0%, var(--c-plasma) 30%, var(--c-blue) 55%, var(--c-purple) 78%, var(--c-gold) 100%);
    background-size: 300% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agPlasmaFlow 5s ease infinite, agHeroItsUsIn 1.1s 0.70s var(--ease-out) both;
    filter: drop-shadow(0 0 100px rgba(0,232,122,0.32)) drop-shadow(0 0 200px rgba(59,158,255,0.14));
    margin: 0; padding-bottom: 0.08em;
}
.ag-hero-sub {
    font-family: var(--font-body);
    font-size: clamp(1.0rem, 1.8vw, 1.30rem); font-weight: 400;
    color: rgba(200,215,235,0.80);
    line-height: 1.85; margin-top: 48px;
    max-width: 660px; margin-left: auto; margin-right: auto;
    animation: agHeroTextReveal 0.9s 0.65s var(--ease-out) both;
    letter-spacing: 0.01em;
}
.ag-hero-sub strong {
    color: #ffffff; font-weight: 700;
    background: linear-gradient(90deg, #fff, var(--c-plasma));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-hero-badges {
    display: flex; justify-content: center; gap: 10px; flex-wrap: wrap;
    margin-top: 32px;
    animation: agHeroTextReveal 0.9s 0.75s var(--ease-out) both;
}
.ag-hero-badge {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: var(--font-mono);
    font-size: 0.72rem; font-weight: 600;
    color: rgba(255,255,255,0.55);
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.12);
    padding: 10px 20px; border-radius: 8px;
    text-transform: uppercase; letter-spacing: 0.08em;
    transition: all 0.2s var(--ease-spring);
    backdrop-filter: blur(8px);
}
.ag-hero-badge:hover {
    border-color: rgba(0,232,122,0.38);
    background: rgba(0,232,122,0.06);
    color: rgba(255,255,255,0.85);
    box-shadow: 0 0 24px rgba(0,232,122,0.10);
    transform: translateY(-2px);
}
.ag-hero-badge .badge-ico { font-size: 1.0rem; }
.ag-hero-badge.primary {
    color: var(--c-green);
    background: rgba(0,232,122,0.08);
    border-color: rgba(0,232,122,0.32);
    box-shadow: 0 0 28px rgba(0,232,122,0.12);
}

/* ── Hero dual CTA row ──────────────────────────────────────── */
.ag-hero-cta {
    display: flex; justify-content: center; align-items: center;
    gap: 12px; flex-wrap: wrap; margin-top: 40px;
    animation: agHeroTextReveal 0.9s 0.9s var(--ease-out) both;
}
.ag-hero-cta-primary {
    display: inline-flex; align-items: center; gap: 10px;
    font-family: var(--font-head);
    font-size: 0.92rem; font-weight: 900; font-style: italic; color: #020509;
    background: linear-gradient(135deg, var(--c-green-hi) 0%, var(--c-green) 40%, var(--c-green-dim) 100%);
    padding: 18px 52px; border-radius: 10px;
    text-decoration: none; text-transform: uppercase; letter-spacing: 0.08em;
    border: 1px solid rgba(0,255,128,0.35);
    box-shadow:
        0 0 0 1px rgba(0,255,128,0.30),
        0 0 24px rgba(0,255,128,0.60),
        0 0 60px rgba(0,255,128,0.35),
        0 0 120px rgba(0,255,128,0.12),
        0 8px 32px rgba(0,255,128,0.25),
        inset 0 1px 0 rgba(255,255,255,0.28);
    transition: all 0.3s var(--ease-spring);
    position: relative; overflow: hidden; cursor: pointer;
    will-change: transform;
}
.ag-hero-cta-primary::before {
    content: ''; position: absolute; top: 0; left: -100%; width: 55%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
    transform: skewX(-20deg); animation: agShimmer 4s ease-in-out infinite;
}
.ag-hero-cta-primary:hover {
    transform: translateY(-5px) scale(1.02);
    box-shadow:
        0 0 0 1px rgba(0,255,128,0.55),
        0 0 40px rgba(0,255,128,0.85),
        0 0 90px rgba(0,255,128,0.55),
        0 0 180px rgba(0,255,128,0.18),
        0 16px 56px rgba(0,255,128,0.30),
        inset 0 1px 0 rgba(255,255,255,0.3);
    background: linear-gradient(135deg, #b3ffd9 0%, var(--c-green-hi) 40%, var(--c-green) 100%);
    color: #010304;
}
.ag-hero-cta-secondary {
    display: inline-flex; align-items: center; gap: 7px;
    font-family: var(--font-head);
    font-size: 0.85rem; font-weight: 700; font-style: italic;
    color: var(--c-cyan);
    background: rgba(0,229,255,0.04);
    padding: 17px 28px; border-radius: 10px;
    text-decoration: none; letter-spacing: 0.03em;
    border: 1px solid rgba(0,229,255,0.22);
    transition: all 0.25s var(--ease-spring);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    box-shadow: 0 0 18px rgba(0,229,255,0.12), inset 0 1px 0 rgba(0,229,255,0.06);
}
.ag-hero-cta-secondary:hover {
    color: #fff;
    border-color: rgba(0,229,255,0.5);
    background: rgba(0,229,255,0.08);
    transform: translateY(-3px);
    box-shadow:
        0 0 28px rgba(0,229,255,0.35),
        0 0 60px rgba(0,229,255,0.18),
        0 8px 24px rgba(0,0,0,0.3),
        inset 0 1px 0 rgba(0,229,255,0.1);
}
.ag-hero-cta-trust {
    width: 100%; text-align: center;
    font-family: var(--font-mono); font-size: 0.68rem; font-weight: 500;
    color: rgba(255,255,255,0.32); letter-spacing: 0.08em; margin-top: 10px;
}
@media (max-width: 520px) {
    .ag-hero { padding: 56px 24px 48px; border-radius: 20px; }
    .ag-hero-cta { gap: 10px; margin-top: 28px; }
    .ag-hero-cta-primary { padding: 15px 32px; font-size: 0.9rem; }
    .ag-hero-cta-secondary { padding: 14px 22px; font-size: 0.8rem; }
    .ag-hero-ai-badge { font-size: 0.60rem; padding: 8px 18px; }
    .ag-hero-badge { font-size: 0.62rem; padding: 8px 14px; }
    .ag-hero-sub { font-size: 1.0rem; }
    .ag-hero-divider { margin: 18px auto 16px; width: 56px; }
}
@media (max-width: 380px) {
    .ag-hero { padding: 44px 16px 36px; }
    .ag-hero-cta { flex-direction: column; gap: 8px; }
    .ag-hero-cta-primary, .ag-hero-cta-secondary { width: 100%; justify-content: center; }
}

/* ── Proof strip (4 glass cards) ──────────────────────────── */
.ag-proof-strip {
    width: 100vw; position: relative;
    left: 50%; transform: translateX(-50%);
    background:
        linear-gradient(180deg, rgba(0,232,122,0.05) 0%, transparent 100%);
    border-top: 1px solid rgba(0,232,122,0.12);
    border-bottom: 1px solid rgba(255,255,255,0.04);
    padding: 60px 0;
    margin: 40px 0 0;
    overflow-x: hidden;
    max-width: 100%;
    box-shadow: 0 0 120px rgba(0,232,122,0.03) inset;
}
.ag-proof-inner {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
    max-width: 840px; margin: 0 auto; padding: 0 20px;
}
.ag-proof-stat {
    text-align: center;
    padding: 32px 16px 26px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-top: 1px solid rgba(0,255,128,0.22);
    border-radius: var(--r-card);
    animation: agProofCardReveal 0.7s 0.2s var(--ease-out) both;
    transition: all 0.35s var(--ease-spring);
    position: relative; overflow: hidden;
    box-shadow:
        0 4px 24px rgba(0,0,0,0.5),
        inset 0 1px 0 rgba(0,255,128,0.06),
        inset 0 -1px 0 rgba(0,0,0,0.3);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
}
/* Top accent beam per card */
.ag-proof-stat::before {
    content: ''; position: absolute; top: 0; left: 15%; right: 15%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,232,122,0.7), transparent);
    transition: opacity 0.3s;
}
.ag-proof-stat::after {
    content: ''; position: absolute; inset: 0; border-radius: var(--r-card);
    background: radial-gradient(ellipse at 50% 0%, rgba(0,232,122,0.06) 0%, transparent 60%);
    opacity: 0; transition: opacity 0.35s; pointer-events: none;
}
.ag-proof-stat:hover::after { opacity: 1; }
.ag-proof-stat:hover {
    border-color: rgba(0,232,122,0.28);
    border-top-color: rgba(0,232,122,0.5);
    transform: translateY(-10px) scale(1.025);
    box-shadow:
        0 32px 80px rgba(0,0,0,0.55),
        0 0 60px rgba(0,232,122,0.1),
        inset 0 1px 0 rgba(255,255,255,0.1);
}
.ag-proof-stat:nth-child(2) { animation-delay: 0.35s; }
.ag-proof-stat:nth-child(3) { animation-delay: 0.5s; }
.ag-proof-stat:nth-child(4) { animation-delay: 0.65s; }
.ag-proof-stat:nth-child(2)::before { background: linear-gradient(90deg, transparent, rgba(59,158,255,0.6), transparent); }
.ag-proof-stat:nth-child(2):hover { border-color: rgba(59,158,255,0.28); border-top-color: rgba(59,158,255,0.5); }
.ag-proof-stat:nth-child(2)::after { background: radial-gradient(ellipse at 50% 0%, rgba(59,158,255,0.06) 0%, transparent 60%); }
.ag-proof-stat:nth-child(3)::before { background: linear-gradient(90deg, transparent, rgba(192,132,252,0.6), transparent); }
.ag-proof-stat:nth-child(3):hover { border-color: rgba(192,132,252,0.28); border-top-color: rgba(192,132,252,0.5); }
.ag-proof-stat:nth-child(3)::after { background: radial-gradient(ellipse at 50% 0%, rgba(192,132,252,0.06) 0%, transparent 60%); }
.ag-proof-stat:nth-child(4)::before { background: linear-gradient(90deg, transparent, rgba(249,198,43,0.6), transparent); }
.ag-proof-stat:nth-child(4):hover { border-color: rgba(249,198,43,0.28); border-top-color: rgba(249,198,43,0.5); }
.ag-proof-stat:nth-child(4)::after { background: radial-gradient(ellipse at 50% 0%, rgba(249,198,43,0.06) 0%, transparent 60%); }
.ag-proof-big {
    font-family: var(--font-mono);
    font-size: 4.2rem; font-weight: 900;
    letter-spacing: -0.045em; line-height: 1;
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum', 'salt';
    background: linear-gradient(135deg, var(--c-green) 0%, var(--c-cyan) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0 0 20px rgba(0,255,128,0.18));
}
.ag-proof-stat:nth-child(2) .ag-proof-big {
    background: linear-gradient(135deg, var(--c-blue), #a78bfa);
    -webkit-background-clip: text; background-clip: text;
    filter: drop-shadow(0 0 20px rgba(59,158,255,0.15));
}
.ag-proof-stat:nth-child(3) .ag-proof-big {
    background: linear-gradient(135deg, var(--c-purple), var(--c-gold));
    -webkit-background-clip: text; background-clip: text;
    filter: drop-shadow(0 0 20px rgba(192,132,252,0.15));
}
.ag-proof-stat:nth-child(4) .ag-proof-big {
    background: linear-gradient(135deg, var(--c-gold), var(--c-green));
    -webkit-background-clip: text; background-clip: text;
    filter: drop-shadow(0 0 20px rgba(249,198,43,0.15));
}
.ag-proof-label {
    font-family: var(--font-body);
    font-size: 0.72rem; font-weight: 700;
    color: rgba(255,255,255,0.55);
    text-transform: uppercase; letter-spacing: 0.12em;
    margin-top: 10px;
}
.ag-proof-sub {
    font-size: 0.6rem; color: rgba(255,255,255,0.2);
    margin-top: 5px; line-height: 1.5; font-family: var(--font-mono);
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
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 18px; padding: 24px 20px 20px;
    position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(0,255,128,0.04);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
}
.ag-inside-card:hover {
    border-color: rgba(0, 213, 89, 0.35);
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 30px rgba(0, 213, 89, 0.08);
}
.ag-inside-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #c084fc);
    opacity: 0.4; transition: opacity 0.3s;
}
.ag-inside-card:hover::before { opacity: 1; }
.ag-inside-ico {
    display: inline-flex; align-items: center; justify-content: center;
    width: 52px; height: 52px; border-radius: 14px;
    background: linear-gradient(135deg, rgba(0, 213, 89, 0.12), rgba(45, 158, 255, 0.08));
    border: 1px solid rgba(0, 213, 89, 0.15);
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
    color: #00D559; background: rgba(0, 213, 89, 0.08);
    border: 1px solid rgba(0, 213, 89, 0.15);
    padding: 4px 12px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.08em;
}

/* ── Tabs ────────────────────────────────────────────────────── */
[data-testid="stTabs"] {
    animation: agFadeUp 0.6s 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
    max-width: 520px; margin: 0 auto;
}
[data-testid="stTabs"] > [data-baseweb="tab-list"],
[data-testid="stTabs"] > [role="tablist"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px; padding: 3px; gap: 3px;
    justify-content: center; margin-bottom: 16px;
}
[data-testid="stTabs"] [data-baseweb="tab"],
[data-testid="stTabs"] button[role="tab"] {
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
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"],
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
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
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--r-card) !important;
    padding: 30px 26px 26px !important;
    backdrop-filter: var(--glass-blur) saturate(160%) !important;
    -webkit-backdrop-filter: var(--glass-blur) saturate(160%) !important;
    box-shadow: 0 24px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(0,255,128,0.06) !important;
    position: relative; overflow: hidden;
}
[data-testid="stForm"]::before {
    content: ''; position: absolute; top: 0; left: 10%; right: 10%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,232,122,0.45), rgba(163,247,224,0.3), transparent);
}

/* ── Inputs ──────────────────────────────────────────────────── */
[data-testid="stForm"] input {
    background: rgba(255,255,255,0.03) !important;
    border: 0.5px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.9) !important;
    font-family: var(--font-body) !important;
    font-size: 0.9rem !important;
    padding: 13px 16px !important;
    transition: all 0.2s var(--ease-spring) !important;
    caret-color: var(--c-green) !important;
    letter-spacing: 0.01em !important;
}
[data-testid="stForm"] input:focus {
    border-color: rgba(0,232,122,0.45) !important;
    box-shadow: 0 0 0 3px rgba(0,232,122,0.07), inset 0 0 0 1px rgba(0,232,122,0.1) !important;
    background: rgba(0,232,122,0.02) !important;
    outline: none !important;
}
[data-testid="stForm"] input::placeholder {
    color: rgba(255,255,255,0.14) !important;
    font-style: italic !important;
}
[data-testid="stForm"] label {
    color: rgba(255,255,255,0.35) !important;
    font-family: var(--font-mono) !important;
    font-weight: 600 !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="stForm"] [data-testid="stTextInputRootElement"] button {
    color: rgba(255,255,255,0.25) !important;
}

/* ── CTA button — True Neon glow ──────────────────────────────── */
[data-testid="stForm"] button[kind="primaryFormSubmit"],
[data-testid="stForm"] button[type="submit"] {
    background: linear-gradient(135deg, var(--c-green-hi) 0%, var(--c-green) 50%, var(--c-green-dim) 100%) !important;
    color: #010304 !important;
    font-family: var(--font-head) !important;
    font-weight: 800 !important;
    font-style: italic !important;
    font-size: 0.85rem !important;
    border: 1px solid rgba(0,255,128,0.3) !important;
    border-radius: 8px !important;
    padding: 14px 28px !important;
    margin-top: 10px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    box-shadow:
        0 0 0 1px rgba(0,255,128,0.25),
        0 0 24px rgba(0,255,128,0.55),
        0 0 60px rgba(0,255,128,0.30),
        0 0 120px rgba(0,255,128,0.12),
        0 4px 20px rgba(0,255,128,0.25),
        inset 0 1px 0 rgba(255,255,255,0.28) !important;
    transition: all 0.25s var(--ease-spring) !important;
    position: relative; overflow: hidden;
    will-change: transform;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]::after,
[data-testid="stForm"] button[type="submit"]::after {
    content: ''; position: absolute; top: 0; left: -100%; width: 55%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
    transform: skewX(-20deg);
    animation: agShimmer 4s ease-in-out infinite;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
[data-testid="stForm"] button[type="submit"]:hover {
    transform: translateY(-3px) scale(1.01) !important;
    box-shadow:
        0 0 0 1px rgba(0,255,128,0.5),
        0 0 32px rgba(0,255,128,0.75),
        0 0 80px rgba(0,255,128,0.45),
        0 0 160px rgba(0,255,128,0.18),
        0 8px 32px rgba(0,255,128,0.30),
        inset 0 1px 0 rgba(255,255,255,0.3) !important;
    background: linear-gradient(135deg, #80ffcc 0%, var(--c-green-hi) 50%, var(--c-green) 100%) !important;
}

/* ── Section header ─────────────────────────────────────────── */
.ag-section-head {
    text-align: center; margin-bottom: 36px;
    position: relative;
}
/* Precision beam — not a 4px bar, a razor-thin laser */
.ag-section-head::before {
    content: ''; display: block; width: 48px; height: 1.5px; margin: 0 auto 28px;
    background: linear-gradient(90deg, transparent, var(--c-green), var(--c-plasma), var(--c-blue), transparent);
    box-shadow: 0 0 20px rgba(0,232,122,0.6), 0 0 60px rgba(0,232,122,0.2);
    background-size: 200% 100%;
    animation: agBarSlide 4s linear infinite;
}
.ag-section-head h3 {
    font-family: var(--font-head);
    font-size: 2.8rem; font-weight: 900;
    font-style: italic;
    color: #fff; margin: 0 0 12px;
    letter-spacing: -0.04em;
    text-transform: uppercase;
    line-height: 0.95;
    text-shadow: 0 0 60px rgba(0,255,128,0.10), 0 0 120px rgba(0,229,255,0.05);
}
.ag-section-head h3 .em {
    background: linear-gradient(135deg, var(--c-green) 0%, var(--c-plasma) 40%, var(--c-blue) 80%);
    background-size: 250% 200%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agPlasmaFlow 6s ease infinite;
    filter: drop-shadow(0 0 24px rgba(0,232,122,0.12));
}
.ag-section-head p {
    font-family: var(--font-body);
    font-size: 0.88rem; color: rgba(255,255,255,0.38);
    margin: 0; line-height: 1.7; font-weight: 400;
    max-width: 480px; margin: 0 auto;
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
    content: ''; display: block; width: 72px; height: 2px; margin: 0 auto 20px;
    background: linear-gradient(90deg, #f24336, #F9C62B, #f24336);
    background-size: 200% 100%;
    animation: agPlasmaFlow 4s ease infinite;
    border-radius: 2px;
    box-shadow: 0 0 12px rgba(242,67,54,0.3);
}
.ag-gy-head h3 {
    font-family: var(--font-head);
    font-size: 2.8rem; font-weight: 900;
    font-style: italic;
    color: #fff; margin: 0 0 14px;
    letter-spacing: -0.04em;
    text-transform: uppercase; line-height: 1.0;
}
.ag-gy-head h3 .em {
    background: linear-gradient(135deg, #f24336 0%, #F9C62B 40%, #f24336 100%);
    background-size: 300% 300%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agPlasmaFlow 5s ease infinite;
}
.ag-gy-head p {
    font-size: 0.95rem; color: rgba(255,255,255,0.4);
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
    background: linear-gradient(168deg, rgba(242, 67, 54, 0.04), rgba(10, 16, 32, 0.95));
    border: 1px solid rgba(242, 67, 54, 0.1);
    border-radius: 16px; padding: 16px 22px;
    transition: border-color 0.3s, transform 0.3s, box-shadow 0.3s;
    position: relative; overflow: hidden;
}
.ag-comp:hover {
    border-color: rgba(242, 67, 54, 0.25);
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
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
    background: linear-gradient(168deg, rgba(0, 213, 89, 0.1), rgba(5, 9, 16, 0.97));
    border: 2px solid rgba(0, 213, 89, 0.4);
    border-radius: 24px; padding: 40px 28px 36px;
    text-align: center; position: relative;
    margin-top: 14px;
    animation: agPulse 3s ease-in-out infinite;
    box-shadow: 0 0 80px rgba(0, 213, 89, 0.12), 0 24px 64px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(0, 213, 89, 0.15);
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
/* ── AI Feature Grid (replaces old comparison table) ──────────── */
.ag-compare {
    margin: 56px 0 0;
    animation: agFadeUp 0.6s 0.32s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-fgrid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
}
.ag-fcard {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-card); padding: 28px 22px 24px;
    position: relative; overflow: hidden;
    transition: border-color 0.35s var(--ease-spring), transform 0.35s var(--ease-spring), box-shadow 0.35s;
    box-shadow:
        0 4px 32px rgba(0,0,0,0.55),
        inset 0 1px 0 rgba(0,255,128,0.06),
        inset 0 -1px 0 rgba(0,0,0,0.25);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
}
.ag-fcard::before {
    content: ''; position: absolute; top: 0; left: 15%; right: 15%; height: 1px;
    border-radius: 0 0 4px 4px; transition: opacity 0.4s;
    opacity: 0.6;
}
.ag-fcard::after {
    content: ''; position: absolute; inset: 0; border-radius: var(--r-card);
    opacity: 0; transition: opacity 0.4s; pointer-events: none;
}
.ag-fcard:hover {
    transform: translateY(-10px) scale(1.01);
    box-shadow:
        0 28px 72px rgba(0,0,0,0.6),
        0 0 60px var(--fc-glow, rgba(0,232,122,0.1)),
        inset 0 1px 0 rgba(255,255,255,0.1);
    border-color: rgba(255,255,255,0.14);
}
.ag-fcard:hover::after { opacity: 1; }
/* Color variants */
.ag-fcard.fc-grn { --fc-glow: rgba(0,213,89,0.1); }
.ag-fcard.fc-grn::before { background: linear-gradient(90deg, #00D559, #00B74D); }
.ag-fcard.fc-grn::after { background: radial-gradient(ellipse at 50% 0%, rgba(0,213,89,0.06), transparent 65%); }
.ag-fcard.fc-grn:hover { border-color: rgba(0,213,89,0.25); }
.ag-fcard.fc-blu { --fc-glow: rgba(45,158,255,0.1); }
.ag-fcard.fc-blu::before { background: linear-gradient(90deg, #2D9EFF, #1a7ad9); }
.ag-fcard.fc-blu::after { background: radial-gradient(ellipse at 50% 0%, rgba(45,158,255,0.06), transparent 65%); }
.ag-fcard.fc-blu:hover { border-color: rgba(45,158,255,0.25); }
.ag-fcard.fc-pur { --fc-glow: rgba(192,132,252,0.1); }
.ag-fcard.fc-pur::before { background: linear-gradient(90deg, #c084fc, #9333ea); }
.ag-fcard.fc-pur::after { background: radial-gradient(ellipse at 50% 0%, rgba(192,132,252,0.06), transparent 65%); }
.ag-fcard.fc-pur:hover { border-color: rgba(192,132,252,0.25); }
.ag-fcard.fc-amb { --fc-glow: rgba(249,198,43,0.1); }
.ag-fcard.fc-amb::before { background: linear-gradient(90deg, #F9C62B, #ff8c00); }
.ag-fcard.fc-amb::after { background: radial-gradient(ellipse at 50% 0%, rgba(249,198,43,0.06), transparent 65%); }
.ag-fcard.fc-amb:hover { border-color: rgba(249,198,43,0.25); }
.ag-fcard.fc-cyn { --fc-glow: rgba(34,211,238,0.1); }
.ag-fcard.fc-cyn::before { background: linear-gradient(90deg, #22d3ee, #06b6d4); }
.ag-fcard.fc-cyn::after { background: radial-gradient(ellipse at 50% 0%, rgba(34,211,238,0.06), transparent 65%); }
.ag-fcard.fc-cyn:hover { border-color: rgba(34,211,238,0.25); }
.ag-fcard.fc-red { --fc-glow: rgba(248,113,113,0.1); }
.ag-fcard.fc-red::before { background: linear-gradient(90deg, #f87171, #dc2626); }
.ag-fcard.fc-red::after { background: radial-gradient(ellipse at 50% 0%, rgba(248,113,113,0.06), transparent 65%); }
.ag-fcard.fc-red:hover { border-color: rgba(248,113,113,0.25); }
/* Card internals */
.ag-fc-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.ag-fc-badge {
    font-family: 'JetBrains Mono', monospace; font-size: 0.42rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.12em;
    padding: 3px 10px; border-radius: 100px;
    display: inline-flex; align-items: center; gap: 5px;
}
.ag-fc-badge .dot { width: 5px; height: 5px; border-radius: 50%; animation: agPulse 2s ease infinite; }
.fc-grn .ag-fc-badge { color: #00D559; background: rgba(0,213,89,0.08); border: 1px solid rgba(0,213,89,0.15); }
.fc-grn .ag-fc-badge .dot { background: #00D559; }
.fc-blu .ag-fc-badge { color: #2D9EFF; background: rgba(45,158,255,0.08); border: 1px solid rgba(45,158,255,0.15); }
.fc-blu .ag-fc-badge .dot { background: #2D9EFF; }
.fc-pur .ag-fc-badge { color: #c084fc; background: rgba(192,132,252,0.08); border: 1px solid rgba(192,132,252,0.15); }
.fc-pur .ag-fc-badge .dot { background: #c084fc; }
.fc-amb .ag-fc-badge { color: #F9C62B; background: rgba(249,198,43,0.08); border: 1px solid rgba(249,198,43,0.15); }
.fc-amb .ag-fc-badge .dot { background: #F9C62B; }
.fc-cyn .ag-fc-badge { color: #22d3ee; background: rgba(34,211,238,0.08); border: 1px solid rgba(34,211,238,0.15); }
.fc-cyn .ag-fc-badge .dot { background: #22d3ee; }
.fc-red .ag-fc-badge { color: #f87171; background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.15); }
.fc-red .ag-fc-badge .dot { background: #f87171; }
.ag-fc-metric {
    font-family: var(--font-mono); font-size: 1.6rem; font-weight: 800;
    letter-spacing: -0.04em; line-height: 1;
    font-feature-settings: 'tnum';
    will-change: transform;
}
.fc-grn .ag-fc-metric { color: var(--c-green); text-shadow: 0 0 24px rgba(0,232,122,0.25); }
.fc-blu .ag-fc-metric { color: var(--c-blue); text-shadow: 0 0 24px rgba(59,158,255,0.25); }
.fc-pur .ag-fc-metric { color: var(--c-purple); text-shadow: 0 0 24px rgba(192,132,252,0.25); }
.fc-amb .ag-fc-metric { color: var(--c-gold); text-shadow: 0 0 24px rgba(249,198,43,0.25); }
.fc-cyn .ag-fc-metric { color: #22d3ee; text-shadow: 0 0 24px rgba(34,211,238,0.25); }
.fc-red .ag-fc-metric { color: #f87171; text-shadow: 0 0 24px rgba(248,113,113,0.25); }
.ag-fc-name {
    font-family: var(--font-head); font-size: 1.05rem; font-weight: 800;
    color: rgba(255,255,255,0.92); margin-bottom: 6px; letter-spacing: -0.025em;
}
.ag-fc-desc {
    font-family: var(--font-body);
    font-size: 0.72rem; color: rgba(255,255,255,0.34); line-height: 1.65; margin-bottom: 14px;
    font-weight: 400;
}
.ag-fc-specs {
    display: flex; flex-wrap: wrap; gap: 5px; margin-top: auto;
}
.ag-fc-spec {
    font-family: var(--font-mono); font-size: 0.42rem; font-weight: 600;
    color: rgba(255,255,255,0.18); background: rgba(255,255,255,0.02);
    border: 0.5px solid rgba(255,255,255,0.06); padding: 3px 8px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.08em;
}
/* Staggered entry */
.ag-fcard:nth-child(1) { animation: agFadeUp 0.5s 0.1s cubic-bezier(0.22,1,0.36,1) both; }
.ag-fcard:nth-child(2) { animation: agFadeUp 0.5s 0.15s cubic-bezier(0.22,1,0.36,1) both; }
.ag-fcard:nth-child(3) { animation: agFadeUp 0.5s 0.2s cubic-bezier(0.22,1,0.36,1) both; }
.ag-fcard:nth-child(4) { animation: agFadeUp 0.5s 0.25s cubic-bezier(0.22,1,0.36,1) both; }
.ag-fcard:nth-child(5) { animation: agFadeUp 0.5s 0.3s cubic-bezier(0.22,1,0.36,1) both; }
.ag-fcard:nth-child(6) { animation: agFadeUp 0.5s 0.35s cubic-bezier(0.22,1,0.36,1) both; }
@keyframes agPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ── Feature cards (3-col) — legacy kept for backward compat ── */
.ag-features { display: none; }

/* ── Metric counters ─── full-bleed stats strip ──────────────── */
.ag-stats-strip {
    margin: 56px -40px 0; padding: 0 40px;
    background:
        linear-gradient(180deg, rgba(0,232,122,0.04) 0%, transparent 100%);
    border-top: 1px solid rgba(255,255,255,0.06);
    border-bottom: 1px solid rgba(255,255,255,0.03);
    animation: agFadeUp 0.6s 0.44s var(--ease-out) both;
    position: relative;
}
.ag-stats-strip::before {
    content: ''; position: absolute; top: 0; left: 5%; right: 5%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,232,122,0.3), rgba(163,247,224,0.2), transparent);
    box-shadow: 0 0 16px rgba(0,232,122,0.1);
}
.ag-stats {
    display: grid; grid-template-columns: repeat(6, 1fr); gap: 0;
    padding: 36px 0;
}
.ag-stat {
    text-align: center; position: relative; padding: 10px 4px;
    border-right: 1px solid rgba(255,255,255,0.04);
}
.ag-stat:last-child { border-right: none; }
.ag-stat-val {
    font-family: var(--font-mono);
    font-size: 3.4rem; font-weight: 900;
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum', 'salt';
    background: linear-gradient(135deg, var(--c-green) 0%, var(--c-cyan) 50%, var(--c-blue) 100%);
    background-size: 300% 300%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agPlasmaFlow 6s ease infinite;
    line-height: 1;
    filter: drop-shadow(0 0 24px rgba(0,255,128,0.15));
}
.ag-stat-label {
    font-family: var(--font-mono);
    font-size: 0.6rem; color: rgba(255,255,255,0.28);
    font-weight: 600; margin-top: 8px;
    text-transform: uppercase; letter-spacing: 0.12em;
}

/* ── Testimonials ────────────────────────────────────────────── */
.ag-reviews {
    margin: 56px 0 0;
    animation: agFadeUp 0.6s 0.48s var(--ease-out) both;
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
}
.ag-reviews .ag-section-head { grid-column: 1 / -1; }
.ag-review {
    background: linear-gradient(168deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
    border: 0.5px solid rgba(255,255,255,0.08);
    border-radius: var(--r-card); padding: 0;
    position: relative;
    transition: border-color 0.3s var(--ease-spring), transform 0.3s var(--ease-spring), box-shadow 0.3s;
    overflow: hidden;
    box-shadow: 0 4px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.05);
    backdrop-filter: blur(12px);
    display: flex; flex-direction: column;
}
@keyframes agReviewSlide { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.ag-review:nth-child(2) { animation: agReviewSlide 0.5s 0.1s var(--ease-spring) both; }
.ag-review:nth-child(3) { animation: agReviewSlide 0.5s 0.2s var(--ease-spring) both; }
.ag-review:nth-child(4) { animation: agReviewSlide 0.5s 0.3s var(--ease-spring) both; }
/* Accent top bar per card */
.ag-review::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1.5px;
    border-radius: 24px 24px 0 0;
}
.ag-review:nth-child(2)::before { background: linear-gradient(90deg, var(--c-green), var(--c-plasma)); }
.ag-review:nth-child(3)::before { background: linear-gradient(90deg, var(--c-blue), var(--c-purple)); }
.ag-review:nth-child(4)::before { background: linear-gradient(90deg, var(--c-purple), var(--c-gold)); }
.ag-review:hover {
    border-color: rgba(255,255,255,0.16);
    transform: translateY(-10px) scale(1.01);
    box-shadow: 0 32px 80px rgba(0,0,0,0.5), 0 0 56px rgba(0,232,122,0.08), inset 0 1px 0 rgba(255,255,255,0.08);
}
/* Inner content area */
.ag-review-body {
    padding: 32px 28px 24px; flex: 1; position: relative;
}
/* Decorative quote mark */
.ag-review-body::before {
    content: '\u201C'; position: absolute; top: 12px; right: 20px;
    font-family: Georgia, serif; font-size: 4.5rem;
    color: rgba(0,232,122,0.05); line-height: 1;
    pointer-events: none;
}
/* Highlight chip — what the review is about */
.ag-review-chip {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.56rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em;
    padding: 4px 12px; border-radius: 100px;
    margin-bottom: 14px;
}
.ag-review:nth-child(2) .ag-review-chip {
    color: var(--c-green); background: rgba(0,232,122,0.08); border: 0.5px solid rgba(0,232,122,0.18);
}
.ag-review:nth-child(3) .ag-review-chip {
    color: var(--c-blue); background: rgba(59,158,255,0.08); border: 0.5px solid rgba(59,158,255,0.18);
}
.ag-review:nth-child(4) .ag-review-chip {
    color: var(--c-purple); background: rgba(192,132,252,0.08); border: 0.5px solid rgba(192,132,252,0.18);
}
.ag-review-text {
    font-size: 1.05rem; color: rgba(255,255,255,0.8);
    font-style: italic; line-height: 1.8;
    position: relative;
}
.ag-review-text strong { color: rgba(255,255,255,0.95); font-weight: 700; font-style: normal; }
/* Stat callout inside review */
.ag-review-stat {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(0,232,122,0.06); border: 0.5px solid rgba(0,232,122,0.15);
    border-radius: 8px; padding: 6px 14px; margin-top: 14px;
    font-family: var(--font-mono);
    font-size: 0.72rem; font-weight: 700; color: var(--c-green);
}
.ag-review-stat .stat-num {
    font-size: 1.1rem; font-weight: 800;
    text-shadow: 0 0 12px rgba(0,232,122,0.25);
}
/* Footer / meta area */
.ag-review-footer {
    display: flex; align-items: center; gap: 12px;
    padding: 16px 28px; position: relative;
    border-top: 1px solid rgba(255,255,255,0.04);
    background: rgba(255,255,255,0.015);
}
.ag-review-avatar {
    width: 40px; height: 40px; border-radius: 50%;
    background: linear-gradient(135deg, rgba(0,232,122,0.15), rgba(59,158,255,0.12));
    border: 1px solid rgba(0,232,122,0.2);
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; flex-shrink: 0;
}
.ag-review-info { display: flex; flex-direction: column; }
.ag-review-author {
    font-family: var(--font-mono);
    font-size: 0.82rem; font-weight: 700;
    color: var(--c-green);
}
.ag-review-stars {
    color: #F9C62B; font-size: 0.72rem; margin-top: 2px;
    letter-spacing: 1px;
}
.ag-review-verified {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 0.52rem; font-weight: 700;
    color: rgba(0,232,122,0.55);
    background: rgba(0,232,122,0.06);
    border: 0.5px solid rgba(0,232,122,0.12);
    padding: 4px 12px; border-radius: 4px;
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
    background: linear-gradient(168deg, rgba(8, 14, 28, 0.98), rgba(5, 9, 16, 0.99));
    border: 1px solid rgba(0, 213, 89, 0.12);
    border-radius: 24px; padding: 36px 24px 30px;
    text-align: center; position: relative; overflow: hidden;
    transition: border-color 0.35s, transform 0.35s cubic-bezier(0.16,1,0.3,1), box-shadow 0.35s;
    box-shadow: 0 6px 32px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,0.03);
}
.ag-how-step:hover {
    border-color: rgba(0, 213, 89, 0.45);
    transform: translateY(-12px) scale(1.02);
    box-shadow: 0 28px 72px rgba(0, 0, 0, 0.55), 0 0 60px rgba(0, 213, 89, 0.14);
}
.ag-how-step::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #c084fc);
    opacity: 0.18; transition: opacity 0.35s;
}
.ag-how-step:hover::before { opacity: 1; }
.ag-how-step::after {
    content: ''; position: absolute; inset: 0; border-radius: 24px;
    background: radial-gradient(ellipse at 50% 0%, rgba(0,213,89,0.05) 0%, transparent 65%);
    opacity: 0; transition: opacity 0.35s; pointer-events: none;
}
.ag-how-step:hover::after { opacity: 1; }
.ag-how-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 62px; height: 62px; border-radius: 50%;
    background: linear-gradient(135deg, #00E865, #2D9EFF);
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.5rem; font-weight: 800; color: #0B0F19;
    margin-bottom: 16px;
    box-shadow: 0 8px 32px rgba(0, 213, 89, 0.35), 0 0 0 8px rgba(0,213,89,0.06);
}
.ag-how-ico { font-size: 2.4rem; display: block; margin-bottom: 12px; }
.ag-how-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.25rem; font-weight: 800;
    color: #fff;
    text-transform: uppercase; letter-spacing: -0.03em;
    text-shadow: 0 0 40px rgba(0,213,89,0.08);
}
.ag-how-desc {
    font-size: 0.76rem; color: rgba(255, 255, 255, 0.55);
    margin-top: 12px; line-height: 1.7;
}
.ag-how-arrow {
    position: absolute; top: 50%; right: -10px;
    transform: translateY(-50%);
    color: rgba(0, 213, 89, 0.35); font-size: 0.75rem; z-index: 2;
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
    background: linear-gradient(168deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    border: 0.5px solid rgba(255,255,255,0.1);
    border-radius: var(--r-card); padding: 48px 32px;
    text-align: center; margin: 40px 0 0;
    animation: agFadeUp 0.6s 0.62s var(--ease-out) both;
    position: relative; overflow: hidden;
    backdrop-filter: blur(24px) saturate(150%);
    box-shadow: 0 24px 80px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.07);
}
.ag-cta2::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(0,232,122,0.07) 0%, transparent 65%);
    pointer-events: none;
}
.ag-cta2::after {
    content: ''; position: absolute; top: 0; left: 15%; right: 15%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,232,122,0.4), rgba(163,247,224,0.3), transparent);
}
.ag-cta2-head {
    font-family: var(--font-head);
    font-size: 2.4rem; font-weight: 900;
    color: #fff; margin: 0 0 12px;
    text-transform: uppercase; letter-spacing: -0.04em;
    position: relative; line-height: 1.0;
}
.ag-cta2-head .em {
    background: linear-gradient(135deg, var(--c-green) 0%, var(--c-plasma) 40%, var(--c-blue) 100%);
    background-size: 300% 300%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: agPlasmaFlow 5s ease infinite;
}
.ag-cta2-sub {
    font-size: 0.88rem; color: rgba(255,255,255,0.38);
    margin: 0 0 24px; line-height: 1.65;
    position: relative;
}
.ag-cta2-btn {
    display: inline-block;
    font-family: var(--font-head);
    font-size: 0.9rem; font-weight: 800;
    color: #010304;
    background: linear-gradient(135deg, var(--c-green-hi) 0%, var(--c-green) 50%, var(--c-green-dim) 100%);
    padding: 18px 64px; border-radius: 10px;
    text-decoration: none; letter-spacing: 0.1em; text-transform: uppercase;
    border: 0.5px solid rgba(255,255,255,0.22);
    box-shadow:
        0 0 0 1px rgba(0,232,122,0.2),
        0 0 48px rgba(0,232,122,0.4),
        0 8px 32px rgba(0,232,122,0.2),
        inset 0 1px 0 rgba(255,255,255,0.3);
    transition: all 0.3s var(--ease-spring);
    position: relative; overflow: hidden;
    will-change: transform;
}
.ag-cta2-btn::before {
    content: '';
    position: absolute; top: 0; left: -100%; width: 55%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    transform: skewX(-20deg);
    transition: left 0.55s var(--ease-spring);
}
.ag-cta2-btn:hover {
    transform: translateY(-5px) scale(1.015);
    box-shadow:
        0 0 0 1px rgba(0,232,122,0.4),
        0 0 72px rgba(0,232,122,0.6),
        0 14px 56px rgba(0,232,122,0.3),
        inset 0 1px 0 rgba(255,255,255,0.3);
    background: linear-gradient(135deg, #00FFAA 0%, var(--c-green-hi) 50%, var(--c-green) 100%);
}
.ag-cta2-btn:hover::before { left: 150%; }
.ag-cta2-trust {
    font-size: 0.6rem; color: rgba(255,255,255,0.16);
    margin-top: 16px; position: relative;
    font-family: var(--font-mono);
    letter-spacing: 0.06em;
}

/* ── Trust + footer ──────────────────────────────────────────── */
.ag-trust {
    display: flex; justify-content: center; gap: 16px;
    margin: 28px 0 6px; flex-wrap: wrap;
    animation: agFadeUp 0.6s 0.58s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-trust-item {
    font-size: 0.62rem; font-weight: 600;
    color: rgba(255,255,255,0.2);
    display: flex; align-items: center; gap: 4px;
    font-family: var(--font-mono);
    letter-spacing: 0.04em;
}
.ag-footer {
    text-align: center; padding: 20px 0 40px;
    font-size: 0.55rem; color: rgba(255,255,255,0.08);
    line-height: 1.7;
    font-family: var(--font-mono);
    letter-spacing: 0.04em;
    animation: agFadeUp 0.6s 0.62s var(--ease-out) both;
}
.ag-footer a { color: rgba(255,255,255,0.14); text-decoration: none; border-bottom: 1px solid rgba(255,255,255,0.1); }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
    .stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
        padding: 90px 0 0 0 !important;
    }
    .ag-section { padding-left: 18px; padding-right: 18px; }
    .ag-full-bleed .ag-section { padding-left: 18px; padding-right: 18px; }
    .ag-full-bleed { padding: 36px 0; }
    .ag-hero h1 .hero-l1 { font-size: 3.375rem; }
    .ag-hero h1 .hero-l2 { font-size: 3.9375rem; }
    .ag-hero-its-us { font-size: 4.5rem; letter-spacing: -0.02em; }
    .ag-section-head h3, .ag-gy-head h3 { font-size: 2rem; }
    .ag-cta2-head { font-size: 1.9rem; }
    .ag-proof-big { font-size: 2.4rem; }
    .ag-proof-inner { grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .ag-proof-stat { padding: 22px 14px 18px; }
    .ag-inside-grid { grid-template-columns: 1fr; }
    .ag-fgrid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .ag-fcard { padding: 22px 18px 20px; }
    .ag-fc-metric { font-size: 1.3rem; }
    .ag-fc-name { font-size: 0.95rem; }
    .ag-fc-desc { font-size: 0.68rem; }
    .ag-fc-spec { font-size: 0.4rem; }
    .ag-how-steps { grid-template-columns: 1fr; gap: 12px; }
    .ag-how-arrow { display: none; }
    .ag-us-price { font-size: 3.5rem; }
    .ag-stat-val { font-size: 2.2rem; }
    .ag-stats { grid-template-columns: repeat(3, 1fr); }
    .ag-stats-strip { margin: 48px -18px 0; padding: 0 18px; }
    .ag-comp { grid-template-columns: auto 1fr auto; }
    .ag-comp-miss { display: none; }
    .ag-reviews { grid-template-columns: 1fr; }
    .ag-review-text { font-size: 0.92rem; }
    .ag-review-avatar { width: 32px; height: 32px; font-size: 0.78rem; }
    .ag-review-body { padding: 24px 20px 18px; }
    .ag-review-footer { padding: 14px 20px; }
    .ag-review-stat { margin-top: 10px; font-size: 0.65rem; }
    .ag-review-stat .stat-num { font-size: 0.95rem; }
    .ag-features { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 520px) {
    .stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
        padding: 84px 0 0 0 !important;
    }
    .ag-section { padding-left: 14px; padding-right: 14px; }
    .ag-full-bleed .ag-section { padding-left: 14px; padding-right: 14px; }
    .ag-full-bleed { padding: 28px 0; }
    .ag-hero h1 .hero-l1 { font-size: 2.25rem; line-height: 0.88; }
    .ag-hero h1 .hero-l2 { font-size: 2.625rem; }
    .ag-hero-its-us { font-size: 3.0rem; letter-spacing: -0.02em; }
    .ag-hero p { font-size: 0.82rem; padding: 0 8px; }
    .ag-section-head h3, .ag-gy-head h3 { font-size: 1.5rem; }
    .ag-section-head p { font-size: 0.78rem; padding: 0 4px; }
    .ag-logo-img { width: 160px; }
    .ag-logo-ring { width: 190px; height: 190px; }
    .ag-logo-section { padding-top: 40px; }
    .ag-hero-badges { gap: 6px; flex-wrap: wrap; justify-content: center; }
    .ag-hero-badge { padding: 8px 14px; font-size: 0.64rem; }
    .ag-hero-ai-badge { font-size: 0.60rem; padding: 8px 16px; letter-spacing: 0.12em; }
    .ag-proof-inner { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .ag-proof-big { font-size: 1.8rem; }
    .ag-proof-stat { padding: 16px 10px 14px; border-radius: 14px; }
    .ag-proof-label { font-size: 0.58rem; }
    .ag-features { grid-template-columns: 1fr 1fr; gap: 10px; }
    .ag-feat { padding: 22px 12px 18px; border-radius: 16px; }
    .ag-fgrid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .ag-fcard { padding: 18px 14px 16px; border-radius: 16px; }
    .ag-fc-metric { font-size: 1.1rem; }
    .ag-fc-name { font-size: 0.88rem; }
    .ag-fc-desc { font-size: 0.64rem; }
    .ag-fc-badge { font-size: 0.38rem; padding: 2px 8px; }
    .ag-fc-spec { font-size: 0.38rem; padding: 2px 6px; }
    .ag-feat-ico { width: 48px; height: 48px; font-size: 1.4rem; border-radius: 14px; }
    .ag-feat-name { font-size: 0.95rem; }
    .ag-feat-desc { font-size: 0.75rem; }
    .ag-stats { grid-template-columns: repeat(2, 1fr); gap: 0; }
    .ag-stats-strip { margin: 36px -14px 0; padding: 0 14px; }
    .ag-stat-val { font-size: 1.5rem; }
    .ag-stat-label { font-size: 0.55rem; }
    .ag-price-grid { grid-template-columns: 1fr; }
    .ag-cta2-head { font-size: 1.4rem; }
    .ag-pick-card { width: 152px; }
    .ag-pc-line { font-size: 1.2rem; }
    .ag-pc-player { font-size: 0.7rem; }
    .ag-us-price { font-size: 2.8rem; }
    .ag-us { padding: 32px 18px 28px; border-radius: 20px; }
    .ag-review::before { font-size: 3rem; }
    .ag-review-body { padding: 20px 16px 14px; }
    .ag-review-footer { padding: 12px 16px; }
    .ag-review-verified { display: none; }
    .ag-comp-x { width: 24px; height: 24px; font-size: 0.65rem; }
    .ag-comp { padding: 12px 14px; border-radius: 12px; gap: 10px; }
    .ag-comp-name { font-size: 0.82rem; }
    .ag-comp-price { font-size: 0.95rem; }
    .ag-how-step { padding: 22px 14px 18px; border-radius: 16px; }
    .ag-how-num { width: 38px; height: 38px; font-size: 0.95rem; }
    .ag-divider { margin: 28px 14px; }
    .ag-ticker { height: 34px; }
    .ag-ticker-item { padding: 0 14px; font-size: 0.56rem; }
    .ag-ticker-live { font-size: 0.56rem; padding: 2px 8px; }
    .ag-inside-card { padding: 18px 14px 16px; border-radius: 14px; }
}
@media (max-width: 380px) {
    .stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
        padding: 78px 0 0 0 !important;
    }
    .ag-section { padding-left: 10px; padding-right: 10px; }
    .ag-full-bleed .ag-section { padding-left: 10px; padding-right: 10px; }
    .ag-hero h1 .hero-l1 { font-size: 1.8rem; }
    .ag-hero h1 .hero-l2 { font-size: 2.1rem; }
    .ag-hero-its-us { font-size: 2.4rem; letter-spacing: -0.02em; }
    .ag-hero p { font-size: 0.78rem; }
    .ag-section-head h3, .ag-gy-head h3 { font-size: 1.2rem; }
    .ag-cta2-head { font-size: 1.1rem; }
    .ag-logo-img { width: 140px; }
    .ag-logo-ring { width: 170px; height: 170px; }
    .ag-section-head h3, .ag-gy-head h3 { font-size: 1.3rem; }
    .ag-proof-inner { grid-template-columns: 1fr 1fr; gap: 6px; }
    .ag-proof-big { font-size: 1.5rem; }
    .ag-proof-stat { padding: 14px 8px 12px; }
    .ag-features { grid-template-columns: 1fr; }
    .ag-fgrid { grid-template-columns: 1fr; gap: 8px; }
    .ag-fcard { padding: 16px 12px 14px; border-radius: 14px; }
    .ag-fc-top { margin-bottom: 10px; }
    .ag-fc-metric { font-size: 1rem; }
    .ag-fc-name { font-size: 0.82rem; }
    .ag-fc-desc { font-size: 0.62rem; margin-bottom: 10px; }
    .ag-fc-badge { font-size: 0.36rem; padding: 2px 7px; }
    .ag-fc-spec { font-size: 0.36rem; padding: 2px 5px; }
    .ag-stats { grid-template-columns: repeat(2, 1fr); }
    .ag-us-price { font-size: 2.4rem; }
    .ag-us { padding: 28px 14px 24px; }
    .ag-comp { grid-template-columns: auto 1fr; gap: 8px; }
    .ag-comp-price { display: none; }
    .ag-hero-badges { gap: 4px; }
    .ag-hero-badge { padding: 6px 12px; font-size: 0.60rem; }
    .ag-hero-ai-badge { font-size: 0.56rem; padding: 6px 12px; }
    .ag-ticker { height: 30px; }
    .ag-ticker-item { padding: 0 10px; font-size: 0.5rem; }
}
</style>
"""


# ── Form helpers (shared by landing-page tabs AND the auth portal) ───────────

def _render_signup_form() -> None:
    """Render the two-step sign-up form. Safe to call from any rendering context."""
    _SU_STAGE = "_signup_stage"
    _SU_EMAIL = "_signup_email"
    _SU_NAME  = "_signup_name"
    if _SU_STAGE not in st.session_state:
        st.session_state[_SU_STAGE] = 1

    _stage = st.session_state[_SU_STAGE]
    step1_color = "#00D559" if _stage >= 1 else "rgba(255,255,255,0.15)"
    step2_color = "#00D559" if _stage >= 2 else "rgba(255,255,255,0.15)"
    line_color  = "#00D559" if _stage >= 2 else "rgba(255,255,255,0.08)"
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:center;gap:0;margin:0 auto 18px;max-width:280px;">
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <div style="width:32px;height:32px;border-radius:50%;background:{step1_color};display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-size:0.75rem;font-weight:800;color:#0B0F19;transition:all 0.3s;">1</div>
        <span style="font-size:0.55rem;font-weight:700;color:{step1_color};font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:0.08em;">Info</span>
      </div>
      <div style="flex:1;height:2px;background:{line_color};margin:0 10px 16px;border-radius:2px;transition:all 0.3s;"></div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <div style="width:32px;height:32px;border-radius:50%;background:{step2_color};display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-size:0.75rem;font-weight:800;color:#0B0F19;transition:all 0.3s;">2</div>
        <span style="font-size:0.55rem;font-weight:700;color:{step2_color};font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:0.08em;">Secure</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if _stage == 1:
        st.markdown("""
        <div style="text-align:center;margin-bottom:14px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:4px;">Let&rsquo;s get you started</div>
          <div style="font-size:0.72rem;color:rgba(255,255,255,0.35);">Enter your name and email to create your free account.</div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("signup_step1", clear_on_submit=False):
            su_name  = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            step1_submit = st.form_submit_button("\u27A1 Continue", use_container_width=True, type="primary")
        if step1_submit:
            # CWE-20 / CWE-79 / CWE-89: sanitize inputs at form boundary
            try:
                su_name  = sanitize_display_name(su_name)
                su_email = sanitize_email(su_email)
            except ValueError as _san_err:
                st.error(str(_san_err))
                st.stop()
            if not su_name or len(su_name.strip()) < 2:
                st.error("Please enter your display name (at least 2 characters).")
            elif not su_email or not _valid_email(su_email):
                st.error("Please enter a valid email address.")
            elif _email_exists(su_email):
                st.error("An account with this email already exists. Please log in instead.")
            else:
                st.session_state[_SU_NAME]  = su_name.strip()
                st.session_state[_SU_EMAIL] = su_email.strip().lower()
                st.session_state[_SU_STAGE] = 2
                st.rerun()

    elif _stage == 2:
        _saved_name  = st.session_state.get(_SU_NAME, "")
        _saved_email = st.session_state.get(_SU_EMAIL, "")
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:14px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:4px;">Secure your account</div>
          <div style="font-size:0.72rem;color:rgba(255,255,255,0.35);">
            Creating account for <strong style="color:#00D559;">{_saved_email}</strong>
          </div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("signup_step2", clear_on_submit=False):
            su_pw  = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="_su_pw2")
            step2_submit = st.form_submit_button("\u26A1 Create Free Account", use_container_width=True, type="primary")
        col_back, _ = st.columns([1, 3])
        with col_back:
            if st.button("\u2190 Back", key="_su_back", use_container_width=True):
                st.session_state[_SU_STAGE] = 1
                st.rerun()
        if step2_submit:
            # CWE-20: enforce password complexity at signup boundary
            try:
                validate_password_strength(su_pw)
            except ValueError as _pw_err:
                st.error(str(_pw_err))
                st.stop()
            if pw_err := _valid_password(su_pw):
                st.error(pw_err)
            elif su_pw != su_pw2:
                st.error("Passwords don't match.")
            elif _email_exists(_saved_email):
                st.error("An account with this email already exists. Please log in instead.")
                st.session_state[_SU_STAGE] = 1
            else:
                ok = _create_user(_saved_email, su_pw, _saved_name)
                if ok:
                    user = _authenticate_user(_saved_email, su_pw)
                    if user:
                        _set_logged_in(user)
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
                        try:
                            from utils.email_utils import send_admin_new_user_alert
                            send_admin_new_user_alert(_saved_email, _saved_name)
                        except Exception:
                            pass
                        for k in (_SU_STAGE, _SU_EMAIL, _SU_NAME):
                            st.session_state.pop(k, None)
                        st.session_state["_show_onboarding_tour"] = True
                        st.session_state["_tour_step"] = 0
                        st.session_state["_just_signed_up"] = True
                        st.rerun()
                    else:
                        st.error("Account created but login failed. Please try logging in.")
                else:
                    st.error("Could not create account. Please try again.")


def _render_login_form() -> None:
    """Render the login form with forgot-password flow."""
    with st.form("login_form", clear_on_submit=False):
        li_email = st.text_input("Email Address", placeholder="you@example.com", key="_li_email")
        li_pw = st.text_input("Password", type="password", placeholder="Enter your password", key="_li_pw")
        li_submit = st.form_submit_button("\U0001F513 Log In", use_container_width=True, type="primary")

    if li_submit:
        # CWE-20 / CWE-79 / CWE-89: sanitize email at login boundary
        try:
            li_email = sanitize_email(li_email)
        except ValueError as _san_err:
            st.error(str(_san_err))
            st.stop()
        if not li_email or not _valid_email(li_email):
            st.error("Please enter a valid email address.")
        elif not li_pw:
            st.error("Please enter your password.")
        else:
            lockout_msg = _check_login_lockout(li_email)
            if lockout_msg:
                st.error(f"\U0001F512 {lockout_msg}")
            else:
                user = _authenticate_user(li_email, li_pw)
                if user:
                    _clear_failed_logins(li_email)
                    _set_logged_in(user)
                    try:
                        from utils.analytics import track_login
                        track_login(li_email)
                    except Exception:
                        pass
                    st.success(f"Welcome back, {user.get('display_name', '')}!")
                    st.rerun()
                else:
                    _record_failed_login(li_email)
                    st.error("Invalid email or password.")

    st.markdown("---")
    _reset_state = st.session_state.get("_pw_reset_stage", "idle")

    if _reset_state == "idle":
        if st.button("\U0001F511 Forgot Password?", key="_btn_forgot", use_container_width=True):
            st.session_state["_pw_reset_stage"] = "email"
            st.rerun()

    elif _reset_state == "email":
        st.info("\U0001F4E7 Enter your email and we'll generate a reset code.")
        with st.form("reset_email_form", clear_on_submit=False):
            rst_email = st.text_input("Email Address", placeholder="you@example.com", key="_rst_email")
            rst_send = st.form_submit_button("\U0001F4E8 Send Reset Code", use_container_width=True)
        if rst_send:
            # CWE-20: sanitize email before password-reset token generation
            try:
                rst_email = sanitize_email(rst_email)
            except ValueError as _san_err:
                st.error(str(_san_err))
                st.stop()
            if not rst_email or not _valid_email(rst_email):
                st.error("Enter a valid email address.")
            else:
                _code = _generate_reset_token(rst_email)
                # SECURITY: always show the same message regardless of whether the
                # email exists -- prevents account enumeration attacks.
                st.success("\U0001F4E7 If this email is registered, a reset code has been sent to your inbox.")
                # Always advance to code-entry; invalid/missing codes simply fail verification.
                st.session_state["_pw_reset_stage"] = "code"
                st.session_state["_pw_reset_email"] = rst_email.strip().lower()
                # Never store the raw code in session state -- it arrives via email only.
                st.session_state.pop("_pw_reset_code", None)
                st.rerun()
        if st.button("Cancel", key="_btn_rst_cancel1"):
            st.session_state["_pw_reset_stage"] = "idle"
            st.rerun()

    elif _reset_state == "code":
        _rst_em = st.session_state.get("_pw_reset_email", "")
        _rst_code = st.session_state.get("_pw_reset_code", "")
        st.info(f"\U0001F4E7 A reset code has been sent to **{_rst_em}** — check your inbox. Expires in 15 minutes.")
        with st.form("reset_code_form", clear_on_submit=False):
            entered_code = st.text_input("Enter 6-digit code", placeholder="123456", key="_rst_code_input")
            rst_verify = st.form_submit_button("\u2705 Verify Code", use_container_width=True)
        if rst_verify:
            # CWE-20: validate reset code format before DB lookup
            try:
                entered_code = sanitize_reset_code(entered_code)
            except ValueError as _san_err:
                st.error(str(_san_err))
                st.stop()
            if _verify_reset_token(_rst_em, entered_code):
                st.session_state["_pw_reset_stage"] = "newpw"
                st.rerun()
            else:
                st.error("Invalid or expired code. Try again.")
        if st.button("Cancel", key="_btn_rst_cancel2"):
            st.session_state["_pw_reset_stage"] = "idle"
            st.rerun()

    elif _reset_state == "newpw":
        _rst_em = st.session_state.get("_pw_reset_email", "")
        st.info(f"\U0001F512 Set a new password for `{_rst_em}`")
        with st.form("reset_newpw_form", clear_on_submit=False):
            new_pw = st.text_input("New Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_rst_new_pw")
            new_pw2 = st.text_input("Confirm New Password", type="password", placeholder="Re-enter password", key="_rst_new_pw2")
            rst_save = st.form_submit_button("\U0001F4BE Save New Password", use_container_width=True, type="primary")
        if rst_save:
            # CWE-20: enforce password complexity at reset boundary
            try:
                validate_password_strength(new_pw)
            except ValueError as _pw_err:
                st.error(str(_pw_err))
                st.stop()
            if pw_err := _valid_password(new_pw):
                st.error(pw_err)
            elif new_pw != new_pw2:
                st.error("Passwords don't match.")
            elif _reset_user_password(_rst_em, new_pw):
                st.success("\u2705 Password reset! You can now log in with your new password.")
                st.session_state["_pw_reset_stage"] = "idle"
                for k in ("_pw_reset_email", "_pw_reset_code"):
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Failed to reset password. Try again.")


def _render_auth_portal(mode: str, logo_b64: str) -> None:
    """Render a focused, full-screen sign-in / sign-up portal.

    Activated when ``?auth=signup`` or ``?auth=login`` appears in the URL.
    Shows only the background, a centred card header, and the relevant form —
    exactly like a real protected-website auth page.
    """
    other_mode  = "login" if mode == "signup" else "signup"
    other_label = "Log In" if mode == "signup" else "Sign Up Free"
    switch_msg  = "Already have an account?" if mode == "signup" else "Don't have an account?"
    headline    = "Create Account" if mode == "signup" else "Welcome Back"
    sub         = (
        "Free forever &mdash; no credit card required."
        if mode == "signup"
        else "Log in to your AI picks dashboard."
    )

    # Narrow centred layout — overrides the default block-container width
    st.markdown("""<style>
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 20px 0 60px !important;
    max-width: 500px !important;
    margin: 0 auto !important;
}
[data-testid="stTabs"] { max-width: 100% !important; }
</style>""", unsafe_allow_html=True)

    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        'style="width:360px;height:360px;object-fit:contain;'
        'animation:agLogoGlow 4s ease-in-out infinite;" alt="Smart Pick Pro">'
        if logo_b64
        else '<span style="font-size:3.5rem">&#x1F3AF;</span>'
    )

    # Animated background orbs (same theme as landing page)
    st.markdown("""<div class="ag-bg">
  <div class="ag-orb ag-orb-1"></div>
  <div class="ag-orb ag-orb-2"></div>
</div>""", unsafe_allow_html=True)

    # Portal header: back link → logo → brand wordmark → headline → sub-text
    st.markdown(f"""
<div style="text-align:center;padding-top:56px;margin-bottom:28px;">
  <div style="margin-bottom:28px;">
    <a href="."
       style="display:inline-flex;align-items:center;gap:6px;
              font-family:'Inter',sans-serif;font-size:0.78rem;font-weight:600;
              color:rgba(255,255,255,0.3);text-decoration:none;
              border:1px solid rgba(255,255,255,0.06);border-radius:100px;
              padding:6px 16px;background:rgba(255,255,255,0.02);
              transition:all 0.2s;">
      &#x2190; Back to Home
    </a>
  </div>
  {logo_html}
  <div style="font-family:'Space Grotesk',sans-serif;font-size:1.35rem;
              font-weight:800;color:#fff;letter-spacing:-0.04em;margin-top:10px;">
    Smart<span style="background:linear-gradient(135deg,#00D559,#2D9EFF);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;">Pick</span>Pro
  </div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:2rem;
              font-weight:800;color:#fff;letter-spacing:-0.04em;margin-top:20px;
              text-transform:uppercase;">{headline}</div>
  <div style="font-size:0.85rem;color:rgba(255,255,255,0.4);
              margin-top:6px;line-height:1.6;">{sub}</div>
</div>
""", unsafe_allow_html=True)

    # Render the appropriate form
    if mode == "signup":
        _render_signup_form()
    else:
        _render_login_form()

    # Mode-switch footer + trust badges
    st.markdown(f"""
<div style="text-align:center;margin-top:28px;
            font-size:0.82rem;color:rgba(255,255,255,0.35);
            font-family:'Inter',sans-serif;">
  {switch_msg}
  <a href="?auth={other_mode}"
     style="color:#00D559;font-weight:700;text-decoration:none;margin-left:6px;">
    {other_label}
  </a>
</div>
<div style="display:flex;justify-content:center;gap:20px;flex-wrap:wrap;
            margin-top:20px;font-size:0.65rem;color:rgba(255,255,255,0.18);
            font-family:'JetBrains Mono',monospace;">
  <span>&#x1F512; Encrypted &amp; Secure</span>
  <span>&#x26A1; Free Forever</span>
  <span>&#x1F6AB; No Credit Card</span>
</div>
""", unsafe_allow_html=True)


# ── Form helpers (shared by landing-page tabs AND the auth portal) ───────────
# NOTE: _render_signup_form is defined once here (the earlier definition above
# is superseded by this one in Python's module namespace).

def _render_signup_form() -> None:
    """Render the two-step sign-up form. Safe to call from any rendering context."""
    _SU_STAGE = "_signup_stage"
    _SU_EMAIL = "_signup_email"
    _SU_NAME  = "_signup_name"
    if _SU_STAGE not in st.session_state:
        st.session_state[_SU_STAGE] = 1

    _stage = st.session_state[_SU_STAGE]
    step1_color = "#00D559" if _stage >= 1 else "rgba(255,255,255,0.15)"
    step2_color = "#00D559" if _stage >= 2 else "rgba(255,255,255,0.15)"
    line_color  = "#00D559" if _stage >= 2 else "rgba(255,255,255,0.08)"
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:center;gap:0;margin:0 auto 18px;max-width:280px;">
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <div style="width:32px;height:32px;border-radius:50%;background:{step1_color};display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-size:0.75rem;font-weight:800;color:#0B0F19;transition:all 0.3s;">1</div>
        <span style="font-size:0.55rem;font-weight:700;color:{step1_color};font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:0.08em;">Info</span>
      </div>
      <div style="flex:1;height:2px;background:{line_color};margin:0 10px 16px;border-radius:2px;transition:all 0.3s;"></div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
        <div style="width:32px;height:32px;border-radius:50%;background:{step2_color};display:flex;align-items:center;justify-content:center;font-family:'Space Grotesk',sans-serif;font-size:0.75rem;font-weight:800;color:#0B0F19;transition:all 0.3s;">2</div>
        <span style="font-size:0.55rem;font-weight:700;color:{step2_color};font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:0.08em;">Secure</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if _stage == 1:
        st.markdown("""
        <div style="text-align:center;margin-bottom:14px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:4px;">Let&rsquo;s get you started</div>
          <div style="font-size:0.72rem;color:rgba(255,255,255,0.35);">Enter your name and email to create your free account.</div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("signup_step1", clear_on_submit=False):
            su_name  = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            step1_submit = st.form_submit_button("\u27A1 Continue", use_container_width=True, type="primary")
        if step1_submit:
            # CWE-20 / CWE-79 / CWE-89: sanitize inputs at form boundary
            try:
                su_name  = sanitize_display_name(su_name)
                su_email = sanitize_email(su_email)
            except ValueError as _san_err:
                st.error(str(_san_err))
                st.stop()
            if not su_name or len(su_name.strip()) < 2:
                st.error("Please enter your display name (at least 2 characters).")
            elif not su_email or not _valid_email(su_email):
                st.error("Please enter a valid email address.")
            elif _email_exists(su_email):
                st.error("An account with this email already exists. Please log in instead.")
            else:
                st.session_state[_SU_NAME]  = su_name.strip()
                st.session_state[_SU_EMAIL] = su_email.strip().lower()
                st.session_state[_SU_STAGE] = 2
                st.rerun()

    elif _stage == 2:
        _saved_name  = st.session_state.get(_SU_NAME, "")
        _saved_email = st.session_state.get(_SU_EMAIL, "")
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:14px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:4px;">Secure your account</div>
          <div style="font-size:0.72rem;color:rgba(255,255,255,0.35);">
            Creating account for <strong style="color:#00D559;">{_saved_email}</strong>
          </div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("signup_step2", clear_on_submit=False):
            su_pw  = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="_su_pw2")
            step2_submit = st.form_submit_button("\u26A1 Create Free Account", use_container_width=True, type="primary")
        col_back, _ = st.columns([1, 3])
        with col_back:
            if st.button("\u2190 Back", key="_su_back", use_container_width=True):
                st.session_state[_SU_STAGE] = 1
                st.rerun()
        if step2_submit:
            # CWE-20: enforce password complexity at signup boundary
            try:
                validate_password_strength(su_pw)
            except ValueError as _pw_err:
                st.error(str(_pw_err))
                st.stop()
            if pw_err := _valid_password(su_pw):
                st.error(pw_err)
            elif su_pw != su_pw2:
                st.error("Passwords don't match.")
            elif _email_exists(_saved_email):
                st.error("An account with this email already exists. Please log in instead.")
                st.session_state[_SU_STAGE] = 1
            else:
                ok = _create_user(_saved_email, su_pw, _saved_name)
                if ok:
                    user = _authenticate_user(_saved_email, su_pw)
                    if user:
                        _set_logged_in(user)
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
                        try:
                            from utils.email_utils import send_admin_new_user_alert
                            send_admin_new_user_alert(_saved_email, _saved_name)
                        except Exception:
                            pass
                        for k in (_SU_STAGE, _SU_EMAIL, _SU_NAME):
                            st.session_state.pop(k, None)
                        st.session_state["_show_onboarding_tour"] = True
                        st.session_state["_tour_step"] = 0
                        st.session_state["_just_signed_up"] = True
                        st.rerun()
                    else:
                        st.error("Account created but login failed. Please try logging in.")
                else:
                    st.error("Could not create account. Please try again.")


def _render_login_form() -> None:
    """Render the login form with forgot-password flow."""
    with st.form("login_form", clear_on_submit=False):
        li_email = st.text_input("Email Address", placeholder="you@example.com", key="_li_email")
        li_pw = st.text_input("Password", type="password", placeholder="Enter your password", key="_li_pw")
        li_submit = st.form_submit_button("\U0001F513 Log In", use_container_width=True, type="primary")

    if li_submit:
        # CWE-20 / CWE-79 / CWE-89: sanitize email at login boundary
        try:
            li_email = sanitize_email(li_email)
        except ValueError as _san_err:
            st.error(str(_san_err))
            st.stop()
        if not li_email or not _valid_email(li_email):
            st.error("Please enter a valid email address.")
        elif not li_pw:
            st.error("Please enter your password.")
        else:
            lockout_msg = _check_login_lockout(li_email)
            if lockout_msg:
                st.error(f"\U0001F512 {lockout_msg}")
            else:
                user = _authenticate_user(li_email, li_pw)
                if user:
                    _clear_failed_logins(li_email)
                    _set_logged_in(user)
                    try:
                        from utils.analytics import track_login
                        track_login(li_email)
                    except Exception:
                        pass
                    st.success(f"Welcome back, {user.get('display_name', '')}!")
                    st.rerun()
                else:
                    _record_failed_login(li_email)
                    st.error("Invalid email or password.")

    st.markdown("---")
    _reset_state = st.session_state.get("_pw_reset_stage", "idle")

    if _reset_state == "idle":
        if st.button("\U0001F511 Forgot Password?", key="_btn_forgot", use_container_width=True):
            st.session_state["_pw_reset_stage"] = "email"
            st.rerun()

    elif _reset_state == "email":
        st.info("\U0001F4E7 Enter your email and we'll generate a reset code.")
        with st.form("reset_email_form", clear_on_submit=False):
            rst_email = st.text_input("Email Address", placeholder="you@example.com", key="_rst_email")
            rst_send = st.form_submit_button("\U0001F4E8 Send Reset Code", use_container_width=True)
        if rst_send:
            # CWE-20: sanitize email before password-reset token generation
            try:
                rst_email = sanitize_email(rst_email)
            except ValueError as _san_err:
                st.error(str(_san_err))
                st.stop()
            if not rst_email or not _valid_email(rst_email):
                st.error("Enter a valid email address.")
            else:
                _code = _generate_reset_token(rst_email)
                # SECURITY: always show the same message regardless of whether the
                # email exists -- prevents account enumeration attacks.
                st.success("\U0001F4E7 If this email is registered, a reset code has been sent to your inbox.")
                # Always advance to code-entry; invalid/missing codes simply fail verification.
                st.session_state["_pw_reset_stage"] = "code"
                st.session_state["_pw_reset_email"] = rst_email.strip().lower()
                # Never store the raw code in session state -- it arrives via email only.
                st.session_state.pop("_pw_reset_code", None)
                st.rerun()
        if st.button("Cancel", key="_btn_rst_cancel1"):
            st.session_state["_pw_reset_stage"] = "idle"
            st.rerun()

    elif _reset_state == "code":
        _rst_em = st.session_state.get("_pw_reset_email", "")
        _rst_code = st.session_state.get("_pw_reset_code", "")
        st.info(f"\U0001F4E7 A reset code has been sent to **{_rst_em}** — check your inbox. Expires in 15 minutes.")
        with st.form("reset_code_form", clear_on_submit=False):
            entered_code = st.text_input("Enter 6-digit code", placeholder="123456", key="_rst_code_input")
            rst_verify = st.form_submit_button("\u2705 Verify Code", use_container_width=True)
        if rst_verify:
            # CWE-20: validate reset code format before DB lookup
            try:
                entered_code = sanitize_reset_code(entered_code)
            except ValueError as _san_err:
                st.error(str(_san_err))
                st.stop()
            if _verify_reset_token(_rst_em, entered_code):
                st.session_state["_pw_reset_stage"] = "newpw"
                st.rerun()
            else:
                st.error("Invalid or expired code. Try again.")
        if st.button("Cancel", key="_btn_rst_cancel2"):
            st.session_state["_pw_reset_stage"] = "idle"
            st.rerun()

    elif _reset_state == "newpw":
        _rst_em = st.session_state.get("_pw_reset_email", "")
        st.info(f"\U0001F512 Set a new password for `{_rst_em}`")
        with st.form("reset_newpw_form", clear_on_submit=False):
            new_pw = st.text_input("New Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_rst_new_pw")
            new_pw2 = st.text_input("Confirm New Password", type="password", placeholder="Re-enter password", key="_rst_new_pw2")
            rst_save = st.form_submit_button("\U0001F4BE Save New Password", use_container_width=True, type="primary")
        if rst_save:
            # CWE-20: enforce password complexity at reset boundary
            try:
                validate_password_strength(new_pw)
            except ValueError as _pw_err:
                st.error(str(_pw_err))
                st.stop()
            if pw_err := _valid_password(new_pw):
                st.error(pw_err)
            elif new_pw != new_pw2:
                st.error("Passwords don't match.")
            elif _reset_user_password(_rst_em, new_pw):
                st.success("\u2705 Password reset! You can now log in with your new password.")
                st.session_state["_pw_reset_stage"] = "idle"
                for k in ("_pw_reset_email", "_pw_reset_code"):
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Failed to reset password. Try again.")


def _render_auth_portal(mode: str, logo_b64: str) -> None:
    """Render a focused, full-screen sign-in / sign-up portal.

    Activated when ``?auth=signup`` or ``?auth=login`` appears in the URL.
    Shows only the background, a centred card header, and the relevant form —
    exactly like a real protected-website auth page.
    """
    other_mode  = "login" if mode == "signup" else "signup"
    other_label = "Log In" if mode == "signup" else "Sign Up Free"
    switch_msg  = "Already have an account?" if mode == "signup" else "Don't have an account?"
    headline    = "Create Account" if mode == "signup" else "Welcome Back"
    sub         = (
        "Free forever &mdash; no credit card required."
        if mode == "signup"
        else "Log in to your AI picks dashboard."
    )

    # Narrow centred layout — overrides the default block-container width
    st.markdown("""<style>
.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 20px 0 60px !important;
    max-width: 500px !important;
    margin: 0 auto !important;
}
[data-testid="stTabs"] { max-width: 100% !important; }
</style>""", unsafe_allow_html=True)

    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        'style="width:360px;height:360px;object-fit:contain;'
        'animation:agLogoGlow 4s ease-in-out infinite;" alt="Smart Pick Pro">'
        if logo_b64
        else '<span style="font-size:3.5rem">&#x1F3AF;</span>'
    )

    # Animated background orbs (same theme as landing page)
    st.markdown("""<div class="ag-bg">
  <div class="ag-orb ag-orb-1"></div>
  <div class="ag-orb ag-orb-2"></div>
</div>""", unsafe_allow_html=True)

    # Portal header: back link → logo → brand wordmark → headline → sub-text
    st.markdown(f"""
<div style="text-align:center;padding-top:56px;margin-bottom:28px;">
  <div style="margin-bottom:28px;">
    <a href="."
       style="display:inline-flex;align-items:center;gap:6px;
              font-family:'Inter',sans-serif;font-size:0.78rem;font-weight:600;
              color:rgba(255,255,255,0.3);text-decoration:none;
              border:1px solid rgba(255,255,255,0.06);border-radius:100px;
              padding:6px 16px;background:rgba(255,255,255,0.02);
              transition:all 0.2s;">
      &#x2190; Back to Home
    </a>
  </div>
  {logo_html}
  <div style="font-family:'Space Grotesk',sans-serif;font-size:1.35rem;
              font-weight:800;color:#fff;letter-spacing:-0.04em;margin-top:10px;">
    Smart<span style="background:linear-gradient(135deg,#00D559,#2D9EFF);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;">Pick</span>Pro
  </div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:2rem;
              font-weight:800;color:#fff;letter-spacing:-0.04em;margin-top:20px;
              text-transform:uppercase;">{headline}</div>
  <div style="font-size:0.85rem;color:rgba(255,255,255,0.4);
              margin-top:6px;line-height:1.6;">{sub}</div>
</div>
""", unsafe_allow_html=True)

    # Render the appropriate form
    if mode == "signup":
        _render_signup_form()
    else:
        _render_login_form()

    # Mode-switch footer + trust badges
    st.markdown(f"""
<div style="text-align:center;margin-top:28px;
            font-size:0.82rem;color:rgba(255,255,255,0.35);
            font-family:'Inter',sans-serif;">
  {switch_msg}
  <a href="?auth={other_mode}"
     style="color:#00D559;font-weight:700;text-decoration:none;margin-left:6px;">
    {other_label}
  </a>
</div>
<div style="display:flex;justify-content:center;gap:20px;flex-wrap:wrap;
            margin-top:20px;font-size:0.65rem;color:rgba(255,255,255,0.18);
            font-family:'JetBrains Mono',monospace;">
  <span>&#x1F512; Encrypted &amp; Secure</span>
  <span>&#x26A1; Free Forever</span>
  <span>&#x1F6AB; No Credit Card</span>
</div>
""", unsafe_allow_html=True)


# ── Main gate function ────────────────────────────────────────

def _render_email_verification_result(raw_token: str) -> None:
    """Render the result of an email-verification link click (?auth=verify&token=...)."""
    st.markdown(
        "<div style='display:flex;flex-direction:column;align-items:center;"
        "justify-content:center;min-height:55vh;padding:2rem;'>",
        unsafe_allow_html=True,
    )
    if not raw_token:
        st.error("\u26A0\uFE0F Invalid verification link \u2014 the token is missing.")
        if st.button("\u21A9 Back to Login", key="_verify_no_tok"):
            try:
                st.query_params.clear()
                st.query_params["auth"] = "login"
            except Exception:
                pass
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    try:
        from utils.notifications import verify_email_token as _vt
        _ok = _vt(raw_token)
    except Exception:
        _ok = False

    if _ok:
        st.success("\u2705 Email verified! Your account is fully activated.")
        st.balloons()
        # Fire the welcome-confirmed email (non-blocking, best-effort)
        try:
            _ve = st.session_state.get("_auth_user_email", "")
            _vn = st.session_state.get("_auth_user_name", "")
            if _ve:
                from utils.email_utils import send_welcome_confirmed_email
                send_welcome_confirmed_email(_ve, _vn)
        except Exception:
            pass
        if st.button("\U0001F513 Log In Now", key="_verify_login", type="primary"):
            try:
                st.query_params.clear()
                st.query_params["auth"] = "login"
            except Exception:
                pass
            st.rerun()
    else:
        st.error("\u274C This verification link is invalid or has expired.")
        st.caption(
            "Links expire after 24 hours. Log in and resend the verification "
            "email from your account settings."
        )
        if st.button("\u21A9 Back to Login", key="_verify_back"):
            try:
                st.query_params.clear()
                st.query_params["auth"] = "login"
            except Exception:
                pass
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_token_reset_form(raw_token: str) -> None:
    """Render the password-reset form for email-link resets (?auth=reset&token=...)."""
    if not raw_token:
        st.error("\u26A0\uFE0F Invalid reset link \u2014 the token is missing.")
        if st.button("\u21A9 Back to Login", key="_tr_no_tok"):
            try:
                st.query_params.clear()
                st.query_params["auth"] = "login"
            except Exception:
                pass
            st.rerun()
        return

    try:
        from utils.notifications import verify_reset_token_valid, consume_reset_token
        _user_info = verify_reset_token_valid(raw_token)
    except Exception:
        _user_info = None

    if not _user_info:
        st.error(
            "\u274C This password reset link is invalid or has expired "
            "(links expire after 30 minutes)."
        )
        if st.button("\u21A9 Back to Login", key="_tr_invalid"):
            try:
                st.query_params.clear()
                st.query_params["auth"] = "login"
            except Exception:
                pass
            st.rerun()
        return

    st.info(f"\U0001F512 Set a new password for `{_user_info['email']}`")

    with st.form("token_reset_form", clear_on_submit=False):
        _tr_pw  = st.text_input(
            "New Password", type="password",
            placeholder="Min 8 chars, 1 letter, 1 number", key="_tr_pw",
        )
        _tr_pw2 = st.text_input(
            "Confirm Password", type="password",
            placeholder="Re-enter new password", key="_tr_pw2",
        )
        _tr_btn = st.form_submit_button(
            "\U0001F4BE Save New Password", use_container_width=True, type="primary",
        )

    if _tr_btn:
        if pw_err := _valid_password(_tr_pw):
            st.error(pw_err)
        elif _tr_pw != _tr_pw2:
            st.error("Passwords don't match.")
        else:
            try:
                _tok_ok = consume_reset_token(raw_token, _tr_pw)
            except Exception:
                _tok_ok = False
            if _tok_ok:
                st.success("\u2705 Password updated! You can now log in.")
                if st.button("\U0001F513 Log In", key="_tr_success_login", type="primary"):
                    try:
                        st.query_params.clear()
                        st.query_params["auth"] = "login"
                    except Exception:
                        pass
                    st.rerun()
            else:
                st.error(
                    "Failed to reset password \u2014 "
                    "this link may have already been used."
                )


# ═══════════════════════════════════════════════════════════════════════════════
# POST-SUBSCRIPTION SUCCESS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

# Shepherd.js tour steps — reference JSON for the guided tour.
# In Streamlit this is implemented natively via session-state steps below.
# Tour steps keyed by min_tier: which tier is required to see this step.
# "free" = shown to everyone. "sharp_iq" = Sharp IQ+. etc.
SHEPHERD_TOUR_STEPS: list[dict] = [
    {
        "id": "step-welcome",
        "icon": "👋",
        "accent": "#00D559",
        "min_tier": "free",
        "page": "Home Dashboard",
        "nav_hint": "",
        "title": "Welcome to Smart Pick Pro",
        "text": (
            "You're now inside an AI-powered NBA prop betting platform. "
            "Every tool is driven by models trained on thousands of games. "
            "This tour walks you through exactly what you have access to "
            "based on your current plan — so you can start picking winners tonight."
        ),
    },
    {
        "id": "step-home",
        "icon": "🏠",
        "accent": "#00D559",
        "min_tier": "free",
        "page": "Home Dashboard",
        "nav_hint": "Smart Pick Pro Home",
        "title": "Your Home Dashboard",
        "text": (
            "The Home Dashboard shows tonight's top AI picks the moment you log in. "
            "Free members see a preview of the top 5 picks. "
            "Paid members see the full Quantum Edge Gap rankings and Platform AI Picks "
            "section — both refreshed automatically every 3 minutes."
        ),
    },
    {
        "id": "step-live-sweat",
        "icon": "💦",
        "accent": "#2D9EFF",
        "min_tier": "free",
        "page": "Live Sweat",
        "nav_hint": "Sidebar → 💦 Live Sweat",
        "title": "Live Sweat — Watch Picks In Real Time",
        "text": (
            "Available to all members. Once games tip off, Live Sweat becomes your "
            "most important screen. It shows every active pick, the current live stat line, "
            "and a color-coded HIT / MISS projection updating play by play. "
            "No need to check the box score — it's all here."
        ),
    },
    {
        "id": "step-live-games",
        "icon": "📡",
        "accent": "#2D9EFF",
        "min_tier": "free",
        "page": "Live Games",
        "nav_hint": "Sidebar → 📡 Live Games",
        "title": "Live Games — Real-Time Box Scores",
        "text": (
            "Available to all members. Live Games pulls real-time NBA box scores "
            "and stat projections from the official NBA data feed. "
            "Drill into any player's current pace, historical splits against tonight's "
            "opponent, and whether the game script is trending toward more or fewer stats."
        ),
    },
    {
        "id": "step-qam",
        "icon": "⚡",
        "accent": "#c084fc",
        "min_tier": "free",
        "page": "Quantum Analysis Matrix",
        "nav_hint": "Sidebar → ⚡ Quantum Analysis Matrix",
        "title": "QAM — The AI Props Engine",
        "text": (
            "The Quantum Analysis Matrix scans props across PrizePicks, DraftKings, "
            "and Underdog each night using 6 neural models. "
            "Free members see up to 12 picks. Sharp IQ sees 35. Smart Money and "
            "Insider Circle see unlimited. Each pick shows a SAFE Score (0–100), "
            "edge %, direction, and confidence tier."
        ),
    },
    {
        "id": "step-prop-scanner",
        "icon": "🔬",
        "accent": "#fbbf24",
        "min_tier": "sharp_iq",
        "page": "Prop Scanner",
        "nav_hint": "Sidebar → 🔬 Prop Scanner",
        "title": "Prop Scanner — Browse Every Line",
        "text": (
            "Sharp IQ+ feature. Browse and filter every prop line available tonight "
            "across all platforms. Filter by player, team, stat type, or platform. "
            "Lines that moved significantly since yesterday are highlighted — "
            "sharp line movement is one of the strongest signals that a prop is soft."
        ),
    },
    {
        "id": "step-game-report",
        "icon": "📋",
        "accent": "#a78bfa",
        "min_tier": "sharp_iq",
        "page": "Game Report",
        "nav_hint": "Sidebar → 📋 Game Report",
        "title": "Game Report — Deep Dive Any Matchup",
        "text": (
            "Sharp IQ+ feature. Select any game and get a full AI analysis: "
            "pace projections, defensive ratings, player usage trends, and the most "
            "exploitable stat categories for the matchup. "
            "Use this before building your lineup to validate each pick's context."
        ),
    },
    {
        "id": "step-entry-builder",
        "icon": "🧬",
        "accent": "#34d399",
        "min_tier": "sharp_iq",
        "page": "Entry Builder",
        "nav_hint": "Sidebar → 🧬 Entry Builder",
        "title": "Entry Builder — Build Your Lineup",
        "text": (
            "Sharp IQ+ feature. Assemble picks into a formatted PrizePicks or Underdog "
            "lineup. It automatically checks correlation between legs, warns about "
            "same-game exposure, and calculates the combined probability of hitting "
            "your full entry. Aim for legs with SAFE Score above 65 and edge above +3%."
        ),
    },
    {
        "id": "step-risk-shield",
        "icon": "🛡️",
        "accent": "#f87171",
        "min_tier": "sharp_iq",
        "page": "Risk Shield",
        "nav_hint": "Sidebar → 🛡️ Risk Shield",
        "title": "Risk Shield — Protect Your Bankroll",
        "text": (
            "Sharp IQ+ feature. Risk Shield flags picks the AI tagged as high-variance "
            "based on injury news, pace anomalies, or tough defensive matchups. "
            "Picks marked AVOID should be dropped from your lineup. "
            "It also tracks your 7-day exposure so you never over-bet a single slate."
        ),
    },
    {
        "id": "step-bet-tracker",
        "icon": "📈",
        "accent": "#60a5fa",
        "min_tier": "sharp_iq",
        "page": "Bet Tracker",
        "nav_hint": "Sidebar → 📈 Bet Tracker",
        "title": "Bet Tracker — Measure Your Real Edge",
        "text": (
            "Sharp IQ+ feature. Logs every pick and calculates your actual hit rate "
            "vs the AI's predicted probability. Over time this reveals which stat types "
            "and confidence tiers are most accurate for you personally. "
            "The Health tab shows ROI, streaks, and risky bet tracking."
        ),
    },
    {
        "id": "step-smart-money",
        "icon": "💰",
        "accent": "#00D559",
        "min_tier": "smart_money",
        "page": "Smart Money Bets",
        "nav_hint": "Sidebar → 💰 Smart Money Bets",
        "title": "Smart Money — Follow the Sharp Action",
        "text": (
            "Smart Money+ exclusive. This section surfaces props where all AI models "
            "agree AND the edge is widest — the picks sharp bettors prioritize. "
            "Each entry shows projected value vs the posted line, a confidence interval, "
            "and a recommended stake size based on Kelly Criterion."
        ),
    },
    {
        "id": "step-correlation",
        "icon": "🗺️",
        "accent": "#fb923c",
        "min_tier": "smart_money",
        "page": "Correlation Matrix",
        "nav_hint": "Sidebar → 🗺️ Correlation Matrix",
        "title": "Correlation Matrix — Stack Smarter",
        "text": (
            "Smart Money+ exclusive. The Correlation Matrix shows which props move "
            "together so your lineup legs reinforce each other. "
            "Green = positive correlation (stack these). Red = negative (avoid pairing). "
            "Building correlated entries is one of the biggest edges in prop betting."
        ),
    },
    {
        "id": "step-upgrade",
        "icon": "🔒",
        "accent": "#fbbf24",
        "min_tier": "free",
        "max_tier": "free",   # Only shown to free-tier users
        "page": "Unlock More",
        "nav_hint": "Sidebar → 💎 Subscription Level",
        "title": "Unlock the Full Platform",
        "text": (
            "You're on the free plan — you have Live Sweat, Live Games, and up to "
            "12 QAM props per night. Sharp IQ ($9.99/mo) adds Prop Scanner, "
            "Entry Builder, Risk Shield, Bet Tracker, and 35 QAM props. "
            "Smart Money ($24.99/mo) unlocks Smart Money Bets, Correlation Matrix, "
            "and unlimited props. Visit Subscription Level in the sidebar to upgrade."
        ),
    },
    {
        "id": "step-ready",
        "icon": "🚀",
        "accent": "#00D559",
        "min_tier": "free",
        "page": "You're Ready",
        "nav_hint": "",
        "title": "You're Ready to Pick Winners",
        "text": (
            "That's your platform. The nightly workflow: "
            "1) Run QAM to generate picks. "
            "2) Check Risk Shield to drop risky legs. "
            "3) Build your lineup in Entry Builder. "
            "4) Track it live in Live Sweat. "
            "5) Log results in Bet Tracker. "
            "Good luck tonight — the AI is already running."
        ),
    },
]


def _get_tour_steps_for_tier(tier: str) -> list[dict]:
    """Return the subset of SHEPHERD_TOUR_STEPS visible to the given tier.

    Tier hierarchy (lowest→highest): free < sharp_iq < smart_money < insider_circle.
    A step is shown when the user's tier >= step's min_tier.
    Steps with max_tier are only shown when user's tier <= max_tier.
    """
    _ORDER = ["free", "sharp_iq", "smart_money", "insider_circle"]
    try:
        user_idx = _ORDER.index(tier)
    except ValueError:
        user_idx = 0  # unknown tier → treat as free

    result = []
    for step in SHEPHERD_TOUR_STEPS:
        min_t = step.get("min_tier", "free")
        max_t = step.get("max_tier", "insider_circle")
        try:
            min_idx = _ORDER.index(min_t)
        except ValueError:
            min_idx = 0
        try:
            max_idx = _ORDER.index(max_t)
        except ValueError:
            max_idx = len(_ORDER) - 1
        if min_idx <= user_idx <= max_idx:
            result.append(step)
    return result


def render_subscription_success_page(plan_name: str = "Smart Pick Pro") -> bool:
    """Render the full-viewport post-payment success celebration page.

    Returns True if rendered (caller should st.stop()).
    """
    import streamlit as st

    if not st.session_state.get("_just_subscribed"):
        return False

    plan = st.session_state.get("_just_subscribed_plan", plan_name) or plan_name
    logo_b64 = _get_logo_b64()
    logo_tag = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'alt="Smart Pick Pro" class="spp-logo-img">'
        if logo_b64 else
        '<div class="spp-logo-text">⚡ Smart Pick Pro</div>'
    )

    _plan_lower = plan.lower()
    if "insider" in _plan_lower:
        tier_label = "👑 Insider Circle"
        tier_color = "#c084fc"
        tier_r, tier_g, tier_b = 192, 132, 252
        feature_list = [
            ("👑", "Unlimited QAM props", "Every pick the AI generates — zero caps"),
            ("⚡", "Full QEG + Platform Picks", "No blur, no limits, all sections open"),
            ("📊", "Priority analysis queue", "Your session runs first every night"),
            ("🔔", "SMS game-night alerts", "Best picks pushed 2 hours before tip-off"),
        ]
    elif "smart money" in _plan_lower or "smart_money" in _plan_lower:
        tier_label = "💎 Smart Money"
        tier_color = "#2D9EFF"
        tier_r, tier_g, tier_b = 45, 158, 255
        feature_list = [
            ("💎", "Unlimited QAM props", "No caps — full nightly analysis"),
            ("⚡", "Full QEG + Platform Picks", "All sections unlocked"),
            ("📊", "Advanced filters", "Edge %, tier, platform, direction"),
            ("📈", "Historical back-test", "AI track record by stat type"),
        ]
    elif "sharp" in _plan_lower:
        tier_label = "🔷 Sharp IQ"
        tier_color = "#00D559"
        tier_r, tier_g, tier_b = 0, 213, 89
        feature_list = [
            ("🔷", "35 QAM props per night", "Expanded nightly analysis"),
            ("⚡", "Full QEG Analysis", "Quantum Edge Generator unlocked"),
            ("🎯", "Platform AI Picks teaser", "Top 5 platform picks visible"),
            ("📊", "Confidence tier filters", "Filter by SAFE score tier"),
        ]
    else:
        tier_label = "🚀 Smart Pick Pro"
        tier_color = "#00D559"
        tier_r, tier_g, tier_b = 0, 213, 89
        feature_list = [
            ("⚡", "Quantum Analysis Matrix", "AI-powered nightly prop analysis"),
            ("🎯", "Platform AI Picks", "PrizePicks & Underdog recommendations"),
            ("📈", "SAFE Score + Edge %", "Confidence and edge on every pick"),
            ("🔄", "Auto-refresh every 3 min", "Live picks throughout game night"),
        ]

    feature_cards = "".join(
        f"""<div class="spp-feat-card">
              <div class="spp-feat-ico">{ico}</div>
              <div class="spp-feat-title">{title}</div>
              <div class="spp-feat-desc">{desc}</div>
            </div>"""
        for ico, title, desc in feature_list
    )

    # 30 varied confetti pieces
    _conf_colors = ["#00D559","#2D9EFF","#c084fc","#fbbf24","#f472b6",
                    "#34d399","#60a5fa","#a78bfa","#fb923c","#f87171"]
    confetti = "".join(
        f'<div class="spp-cc spp-cc-{i % 10}" style="left:{3 + i * 3.2}%;'
        f'animation-delay:{(i * 0.13):.2f}s;animation-duration:{2.2 + (i % 5) * 0.35:.2f}s;'
        f'background:{_conf_colors[i % 10]};width:{3 + i % 4}px;height:{7 + i % 5}px;'
        f'transform:rotate({i * 43 % 180}deg);"></div>'
        for i in range(30)
    )

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700;800;900&family=JetBrains+Mono:wght@600;700;800&display=swap');

/* ── Full-page reset ── */
[data-testid="stSidebar"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton, footer {{ display:none!important; }}
[data-testid="stAppViewContainer"] > div:first-child {{ padding:0!important; }}

/* ── Animations ── */
@keyframes sppConfetti {{
    0%   {{ transform:translateY(-5vh) rotate(0deg);   opacity:1; }}
    100% {{ transform:translateY(105vh) rotate(800deg); opacity:0; }}
}}
@keyframes sppSlideIn {{
    from {{ opacity:0; transform:translateY(40px) scale(.96); }}
    to   {{ opacity:1; transform:translateY(0)    scale(1);   }}
}}
@keyframes sppRingPulse {{
    0%,100% {{ transform:translate(-50%,-50%) scale(1);   opacity:.6; }}
    50%      {{ transform:translate(-50%,-50%) scale(1.12); opacity:.25; }}
}}
@keyframes sppRingPulse2 {{
    0%,100% {{ transform:translate(-50%,-50%) scale(1);   opacity:.35; }}
    50%      {{ transform:translate(-50%,-50%) scale(1.22); opacity:.1; }}
}}
@keyframes sppCheckBounce {{
    0%   {{ transform:scale(0)   rotate(-20deg); opacity:0; }}
    60%  {{ transform:scale(1.15) rotate(6deg);  opacity:1; }}
    80%  {{ transform:scale(.94) rotate(-2deg); }}
    100% {{ transform:scale(1)   rotate(0deg);  opacity:1; }}
}}
@keyframes sppLogoGlow {{
    0%,100% {{ filter:drop-shadow(0 0 24px rgba({tier_r},{tier_g},{tier_b},.3))
                      drop-shadow(0 0 50px rgba({tier_r},{tier_g},{tier_b},.12)); }}
    50%      {{ filter:drop-shadow(0 0 48px rgba({tier_r},{tier_g},{tier_b},.55))
                      drop-shadow(0 0 90px rgba({tier_r},{tier_g},{tier_b},.25)); }}
}}
@keyframes sppFeatIn {{
    from {{ opacity:0; transform:translateY(18px); }}
    to   {{ opacity:1; transform:translateY(0);    }}
}}
@keyframes sppOrbFloat {{
    0%,100% {{ transform:translateY(0);    }}
    50%      {{ transform:translateY(-30px); }}
}}

/* ── Page wrapper ── */
.spp-page {{
    position:relative;min-height:100vh;overflow:hidden;
    background:radial-gradient(ellipse at 50% 0%,   rgba({tier_r},{tier_g},{tier_b},.22) 0%, transparent 55%),
               radial-gradient(ellipse at 85% 80%,  rgba(45,158,255,.14) 0%,             transparent 45%),
               radial-gradient(ellipse at 10% 60%,  rgba(192,132,252,.10) 0%,            transparent 40%),
               #04070f;
    display:flex;align-items:center;justify-content:center;padding:32px 16px;
}}
/* Circuit grid overlay */
.spp-page::before {{
    content:'';position:absolute;inset:0;pointer-events:none;
    background-image:url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cdefs%3E%3Cpattern id='g' width='60' height='60' patternUnits='userSpaceOnUse'%3E%3Cpath d='M30 0v60M0 30h60' stroke='rgba(0,213,89,0.04)' stroke-width='.5' fill='none'/%3E%3Ccircle cx='30' cy='30' r='1.2' fill='rgba(0,213,89,0.07)'/%3E%3Ccircle cx='0'  cy='0'  r='.8' fill='rgba(45,158,255,0.05)'/%3E%3Ccircle cx='60' cy='60' r='.8' fill='rgba(45,158,255,0.05)'/%3E%3C/pattern%3E%3C/defs%3E%3Crect fill='url(%23g)' width='100%25' height='100%25'/%3E%3C/svg%3E");
    opacity:.6;
}}
/* Glow orbs */
.spp-orb {{
    position:absolute;border-radius:50%;pointer-events:none;filter:blur(110px);
    animation:sppOrbFloat 18s ease-in-out infinite;
}}
.spp-orb-1 {{ width:600px;height:600px;top:-180px;left:-120px;background:rgba({tier_r},{tier_g},{tier_b},.18); }}
.spp-orb-2 {{ width:500px;height:500px;bottom:-120px;right:-100px;background:rgba(45,158,255,.14);animation-delay:-9s; }}

/* Pulse rings behind checkmark */
.spp-ring {{
    position:absolute;top:50%;left:50%;border-radius:50%;pointer-events:none;
    border:1px solid rgba({tier_r},{tier_g},{tier_b},.35);
    animation:sppRingPulse 2.8s ease-out infinite;
}}
.spp-ring-1 {{ width:110px;height:110px; }}
.spp-ring-2 {{ width:150px;height:150px;border-color:rgba({tier_r},{tier_g},{tier_b},.18);animation:sppRingPulse2 2.8s .5s ease-out infinite; }}
.spp-ring-3 {{ width:190px;height:190px;border-color:rgba({tier_r},{tier_g},{tier_b},.08);animation:sppRingPulse2 2.8s 1s ease-out infinite; }}

/* ── Card ── */
.spp-card {{
    position:relative;z-index:10;max-width:620px;width:100%;
    background:rgba(8,12,25,.85);
    border:1px solid rgba({tier_r},{tier_g},{tier_b},.18);
    border-radius:24px;overflow:hidden;
    box-shadow:0 32px 80px rgba(0,0,0,.6),0 0 60px rgba({tier_r},{tier_g},{tier_b},.08),
               0 0 0 1px rgba({tier_r},{tier_g},{tier_b},.06) inset;
    animation:sppSlideIn .55s cubic-bezier(.22,1,.36,1) both;
}}
/* Top gradient bar */
.spp-card::before {{
    content:'';display:block;height:3px;
    background:linear-gradient(90deg,{tier_color},#2D9EFF,#c084fc,{tier_color});
    background-size:300% 100%;animation:sppBarShift 4s linear infinite;
}}
@keyframes sppBarShift {{ 0%{{background-position:0% 0%}} 100%{{background-position:300% 0%}} }}

/* Confetti layer */
.spp-confetti-wrap {{
    position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:20;
}}
.spp-cc {{
    position:absolute;top:-12px;border-radius:2px;
}}

/* ── Logo ── */
.spp-logo-wrap {{
    text-align:center;padding:36px 24px 0;
}}
.spp-logo-img {{
    width:120px;
    animation:sppLogoGlow 3s ease-in-out infinite;
    filter:drop-shadow(0 0 20px rgba({tier_r},{tier_g},{tier_b},.35));
}}
.spp-logo-text {{
    font-family:'Space Grotesk',sans-serif;font-size:1.2rem;font-weight:900;
    background:linear-gradient(135deg,{tier_color},#2D9EFF);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;
}}

/* ── Check circle ── */
.spp-check-wrap {{
    position:relative;width:90px;height:90px;margin:24px auto 0;
}}
.spp-check-circle {{
    width:90px;height:90px;border-radius:50%;
    background:linear-gradient(135deg,{tier_color},{tier_color}88);
    display:flex;align-items:center;justify-content:center;
    font-size:2.4rem;font-weight:900;color:#fff;
    box-shadow:0 0 40px rgba({tier_r},{tier_g},{tier_b},.45),0 0 80px rgba({tier_r},{tier_g},{tier_b},.2);
    animation:sppCheckBounce .6s .2s cubic-bezier(.34,1.56,.64,1) both;
    position:relative;z-index:2;
}}

/* ── Tier badge ── */
.spp-tier-badge {{
    display:inline-block;font-family:'JetBrains Mono',monospace;
    font-size:.52rem;font-weight:800;letter-spacing:.15em;text-transform:uppercase;
    padding:5px 18px;border-radius:100px;margin:20px auto 0;
    color:{tier_color};
    background:rgba({tier_r},{tier_g},{tier_b},.1);
    border:1px solid rgba({tier_r},{tier_g},{tier_b},.3);
}}

/* ── Headlines ── */
.spp-headline {{
    font-family:'Space Grotesk',sans-serif;font-size:2rem;font-weight:900;
    color:#fff;text-align:center;margin:12px 24px 6px;letter-spacing:-.5px;
    line-height:1.15;
}}
.spp-subtitle {{
    font-family:'Space Grotesk',sans-serif;font-size:.9rem;font-weight:500;
    color:rgba(255,255,255,.45);text-align:center;margin:0 24px 28px;line-height:1.6;
}}
.spp-subtitle strong {{ color:rgba({tier_r},{tier_g},{tier_b},.9); }}

/* ── Feature grid ── */
.spp-features {{
    display:grid;grid-template-columns:1fr 1fr;gap:10px;
    margin:0 24px 28px;
}}
.spp-feat-card {{
    background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);
    border-radius:14px;padding:14px 16px;
    animation:sppFeatIn .4s ease both;
}}
.spp-feat-card:nth-child(1) {{ animation-delay:.35s; }}
.spp-feat-card:nth-child(2) {{ animation-delay:.45s; }}
.spp-feat-card:nth-child(3) {{ animation-delay:.55s; }}
.spp-feat-card:nth-child(4) {{ animation-delay:.65s; }}
.spp-feat-ico  {{ font-size:1.3rem;margin-bottom:6px; }}
.spp-feat-title {{
    font-family:'Space Grotesk',sans-serif;font-size:.78rem;font-weight:800;
    color:#fff;margin-bottom:3px;
}}
.spp-feat-desc {{
    font-family:'Space Grotesk',sans-serif;font-size:.65rem;
    color:rgba(255,255,255,.38);line-height:1.5;
}}

/* ── CTA button (native Streamlit button override) ── */
.spp-cta-wrap {{ padding:0 24px 32px;text-align:center; }}
.stButton > button {{
    background:linear-gradient(135deg,{tier_color},{tier_color}cc)!important;
    border:none!important;color:#000!important;font-weight:800!important;
    font-size:.9rem!important;letter-spacing:.03em!important;
    border-radius:12px!important;padding:14px 32px!important;
    box-shadow:0 8px 28px rgba({tier_r},{tier_g},{tier_b},.35)!important;
    transition:all .2s!important;width:100%!important;
}}
.stButton > button:hover {{
    transform:translateY(-2px)!important;
    box-shadow:0 14px 40px rgba({tier_r},{tier_g},{tier_b},.5)!important;
}}

@media(max-width:500px) {{
    .spp-features {{ grid-template-columns:1fr; }}
    .spp-headline {{ font-size:1.6rem; }}
    .spp-logo-img {{ width:90px; }}
}}
</style>

<div class="spp-page">
  <div class="spp-orb spp-orb-1"></div>
  <div class="spp-orb spp-orb-2"></div>

  <div class="spp-card">
    <div class="spp-confetti-wrap">{confetti}</div>

    <!-- Logo -->
    <div class="spp-logo-wrap">
      {logo_tag}
    </div>

    <!-- Check circle with pulse rings -->
    <div class="spp-check-wrap" style="position:relative;width:90px;height:90px;margin:24px auto 0;">
      <div class="spp-ring spp-ring-3"></div>
      <div class="spp-ring spp-ring-2"></div>
      <div class="spp-ring spp-ring-1"></div>
      <div class="spp-check-circle">✓</div>
    </div>

    <!-- Tier badge -->
    <div style="text-align:center;">
      <div class="spp-tier-badge">{tier_label}</div>
    </div>

    <!-- Headlines -->
    <div class="spp-headline">You're in the inner circle</div>
    <div class="spp-subtitle">
      Your <strong>{plan}</strong> subscription is confirmed and active.<br>
      The AI is scanning tonight's slate right now.
    </div>

    <!-- Feature grid -->
    <div class="spp-features">
      {feature_cards}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # CTA button outside the card so Streamlit can intercept it cleanly
    _, col, _ = st.columns([1, 2, 1])
    with col:
        if st.button(
            "🚀 Launch My Dashboard →",
            key="_success_launch_btn",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.pop("_just_subscribed", None)
            st.session_state.pop("_just_subscribed_plan", None)
            st.session_state["_show_onboarding_tour"] = True
            st.session_state["_tour_step"] = 0
            try:
                st.query_params.clear()
            except Exception:
                pass
            st.rerun()

    return True


def render_onboarding_tour() -> None:
    """Render the guided onboarding tour as a sleek floating card.

    Filters steps based on the current user's tier so free users only see
    features they can access, and paid users see their unlocked tools.
    Persists via ``_show_onboarding_tour`` + ``_tour_step`` session state.
    """
    import streamlit as st

    if not st.session_state.get("_show_onboarding_tour"):
        return

    # Resolve current tier (safe import, fail to free)
    try:
        from utils.auth import get_user_tier as _gut
        _current_tier = _gut()
    except Exception:
        _current_tier = "free"

    steps = _get_tour_steps_for_tier(_current_tier)
    total = len(steps)
    if not total:
        st.session_state.pop("_show_onboarding_tour", None)
        st.session_state.pop("_tour_step", None)
        return

    step = int(st.session_state.get("_tour_step", 0))
    if step >= total:
        st.session_state.pop("_show_onboarding_tour", None)
        st.session_state.pop("_tour_step", None)
        return

    logo_b64 = _get_logo_b64()
    logo_tag = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'alt="Smart Pick Pro" style="height:32px;width:auto;'
        f'filter:drop-shadow(0 0 8px rgba(0,213,89,.4));">'
        if logo_b64 else
        '<span style="font-family:\'Space Grotesk\',sans-serif;font-weight:900;'
        'font-size:.8rem;background:linear-gradient(135deg,#00D559,#2D9EFF);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">⚡ Smart Pick Pro</span>'
    )

    step_data = steps[step]
    accent = step_data.get("accent", "#00D559")
    step_icon = step_data.get("icon", "✦")
    nav_hint = step_data.get("nav_hint", "")
    page_label = step_data.get("page", "")
    min_tier = step_data.get("min_tier", "free")

    # Tier badge label for locked steps shown to lower tiers (shouldn't happen
    # after filtering, but kept as safety display)
    _tier_labels = {
        "free": "Free",
        "sharp_iq": "Sharp IQ+",
        "smart_money": "Smart Money+",
        "insider_circle": "Insider Circle",
    }

    # Step dot indicators
    dots = "".join(
        f'<div style="width:{10 if i == step else 6}px;height:6px;border-radius:3px;'
        f'background:{"" + accent if i == step else "rgba(255,255,255,.15)"};'
        f'transition:all .3s;margin:0 2px;"></div>'
        for i in range(total)
    )

    # Nav hint chip
    nav_chip = (
        f'<div style="display:inline-flex;align-items:center;gap:6px;'
        f'background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);'
        f'border-radius:8px;padding:4px 10px;margin-bottom:10px;">'
        f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.5rem;'
        f'color:rgba(255,255,255,.4);letter-spacing:.06em;">'
        f'📍 {nav_hint}</span></div>'
        if nav_hint else ""
    )

    # Min-tier badge (shown so users know which plan unlocks this feature)
    tier_chip = (
        f'<div style="display:inline-flex;align-items:center;gap:5px;'
        f'background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);'
        f'border-radius:6px;padding:3px 9px;margin-left:8px;">'
        f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:.44rem;'
        f'font-weight:700;color:{accent};letter-spacing:.08em;">'
        f'{_tier_labels.get(min_tier, min_tier).upper()}</span></div>'
        if min_tier != "free" else ""
    )

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@700&display=swap');
@keyframes sppTourIn {{
    from {{ opacity:0; transform:translateY(20px) scale(.97); }}
    to   {{ opacity:1; transform:translateY(0)    scale(1);   }}
}}
@keyframes sppTourIconPulse {{
    0%,100% {{ box-shadow:0 0 0 0 {accent}66; }}
    50%      {{ box-shadow:0 0 0 8px {accent}00; }}
}}
.spp-tour-wrap {{
    background:linear-gradient(145deg,rgba(8,13,26,.98),rgba(12,18,38,.98));
    border:1px solid {accent}38;
    border-radius:20px;overflow:hidden;
    box-shadow:0 24px 64px rgba(0,0,0,.7),0 0 40px {accent}12,
               0 0 0 1px {accent}08 inset;
    animation:sppTourIn .3s cubic-bezier(.22,1,.36,1) both;
    max-width:500px;margin:0 auto 8px;
}}
.spp-tour-top-bar {{
    height:2px;
    background:linear-gradient(90deg,{accent},#2D9EFF,#c084fc,{accent});
    background-size:300% 100%;animation:sppBarShift 4s linear infinite;
}}
@keyframes sppBarShift {{ 0%{{background-position:0% 0%}} 100%{{background-position:300% 0%}} }}
.spp-tour-header {{
    display:flex;align-items:center;justify-content:space-between;
    padding:14px 18px 10px;
    border-bottom:1px solid rgba(255,255,255,.05);
}}
.spp-tour-step-label {{
    font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;
    color:{accent}99;text-transform:uppercase;letter-spacing:.12em;
}}
.spp-tour-body-area {{ padding:16px 20px; }}
.spp-tour-icon {{
    width:44px;height:44px;border-radius:12px;margin-bottom:10px;
    background:{accent}14;border:1px solid {accent}28;
    display:flex;align-items:center;justify-content:center;
    font-size:1.3rem;animation:sppTourIconPulse 2.5s ease-in-out infinite;
}}
.spp-tour-title {{
    font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:800;
    color:#fff;margin:0 0 6px;line-height:1.2;
    display:flex;align-items:center;flex-wrap:wrap;gap:4px;
}}
.spp-tour-desc {{
    font-family:'Space Grotesk',sans-serif;font-size:.78rem;font-weight:500;
    color:rgba(255,255,255,.52);line-height:1.65;margin:0 0 14px;
}}
.spp-tour-dots {{
    display:flex;align-items:center;margin-bottom:2px;
}}
</style>

<div class="spp-tour-wrap">
  <div class="spp-tour-top-bar"></div>
  <div class="spp-tour-header">
    <div>{logo_tag}</div>
    <div class="spp-tour-step-label">{page_label} &nbsp;·&nbsp; {step + 1}/{total}</div>
  </div>
  <div class="spp-tour-body-area">
    <div class="spp-tour-icon">{step_icon}</div>
    {nav_chip}
    <div class="spp-tour-title">{step_data["title"]}{tier_chip}</div>
    <div class="spp-tour-desc">{step_data["text"]}</div>
    <div class="spp-tour-dots">{dots}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    btn_cols = st.columns([1, 1, 3, 1, 2])
    with btn_cols[0]:
        if st.button("✕ Skip", key=f"_tour_skip_{step}", help="Close tour"):
            st.session_state.pop("_show_onboarding_tour", None)
            st.session_state.pop("_tour_step", None)
            st.rerun()
    with btn_cols[1]:
        if step > 0:
            if st.button("← Back", key=f"_tour_back_{step}"):
                st.session_state["_tour_step"] = step - 1
                st.rerun()
    with btn_cols[4]:
        if step < total - 1:
            if st.button("Next →", key=f"_tour_next_{step}", type="primary"):
                st.session_state["_tour_step"] = step + 1
                st.rerun()
        else:
            if st.button("Done  ✓", key="_tour_done", type="primary"):
                st.session_state.pop("_show_onboarding_tour", None)
                st.session_state.pop("_tour_step", None)
                st.rerun()


@st.fragment(run_every=180)
def _render_free_picks_fragment() -> None:
    """Auto-refreshing fragment: re-queries the DB every 3 minutes and renders
    the top 5 platform picks for today.  When the background scheduler writes
    new picks, visitors on the landing page see them within 3 minutes without
    needing to reload the page.
    """
    _picks, _date = _load_top_preview_picks(5)
    st.html(_build_preview_section_html(_picks, _date))


def require_login() -> bool:
    """Render the Smart Pick Pro auth gate.

    Returns True if authenticated, False otherwise (caller should st.stop()).
    """
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return True

    if is_logged_in():
        # ── Post-login: redirect to Home so user always lands on Smart Pick Pro Home ──
        # _set_logged_in() sets this flag on every fresh login. We consume it here
        # (pop = runs only once) and navigate to the Home page. Cookie-based restores
        # do NOT set this flag so existing sessions are unaffected.
        if st.session_state.pop("_redirect_to_home", False):
            try:
                st.switch_page("Smart_Picks_Pro_Home.py")
            except Exception:
                pass  # switch_page unavailable (older Streamlit) — fall through normally

        # Flush any pending cookie token.  This runs on the run AFTER login
        # (post-st.rerun()), so no st.rerun() follows — the JS executes cleanly.
        _pending = st.session_state.pop("_pending_cookie_token", None)
        if _pending:
            _write_session_to_storage(_pending)
        # Clean any stale auth/token params from the URL.
        try:
            _qp = st.query_params
            if _qp.get("auth") or _qp.get("_st"):
                _qp.pop("auth", None)
                _qp.pop("_st", None)
        except Exception:
            pass
        # ── JWT fetch interceptor ─────────────────────────────────────────────
        # Inject once per tab (idempotent via window.parent._sppInterceptorInstalled).
        # Gives all JS-initiated /api/* calls a short-lived Bearer token while
        # the long-lived HttpOnly refresh cookie stays invisible to JS.
        try:
            from utils.state_sync import inject_fetch_interceptor as _inject_interceptor
            _inject_interceptor()
        except Exception:
            pass
        # ── Email verification reminder (once per session, non-blocking) ─────
        try:
            from utils.notifications import show_verification_banner
            show_verification_banner(st.session_state.get("_auth_user_email", ""))
        except Exception:
            pass
        # ── First-login onboarding tour (triggered by new signups) ──────────
        if st.session_state.get("_just_signed_up"):
            st.session_state.pop("_just_signed_up", None)
            if not st.session_state.get("_show_onboarding_tour"):
                st.session_state["_show_onboarding_tour"] = True
                st.session_state["_tour_step"] = 0
        return True

    # ── Cookie-based session restore (survives F5 / new tab) ─────────────────
    # Python reads the spp_session cookie from the HTTP request headers on
    # every page load — no JS timing issues, no bridge reloads needed.
    _cookie_tok = _get_session_cookie()
    if _cookie_tok:
        _cookie_user = _load_session_by_token(_cookie_tok)
        if _cookie_user:
            _set_logged_in(_cookie_user, _write_storage=False)
            # Cookie restore is a silent re-auth — do NOT redirect to Home.
            # _set_logged_in() always sets _redirect_to_home=True (for fresh
            # logins), so we clear it here so sub-page users are not kicked
            # back to the homepage on their first widget interaction.
            st.session_state["_redirect_to_home"] = False
            # Store the active token in session_state so logout_user()
            # can delete it from the DB and expire the cookie properly.
            st.session_state["_auth_session_token"] = _cookie_tok
            try:
                st.query_params.pop("auth", None)
                st.query_params.pop("_st", None)
            except Exception:
                pass
            # Inject JWT interceptor for this restored session.
            try:
                from utils.state_sync import inject_fetch_interceptor as _inject_interceptor
                _inject_interceptor()
            except Exception:
                pass
            return True
        else:
            # Cookie token expired — clear it.
            _clear_session_from_storage()

    # ── Fallback: localStorage bridge for environments that block cookies ─────
    _render_session_bridge()
    try:
        _tok = st.query_params.get("_st", "")
        if _tok:
            # Mark that we've attempted the localStorage bridge this session
            # so the JS doesn't reload again if this token is rejected.
            st.session_state["_spp_bridge_fired"] = True
            _user = _load_session_by_token(_tok)
            if _user:
                _set_logged_in(_user, _write_storage=False)
                # localStorage bridge restore — do NOT redirect to Home.
                st.session_state["_redirect_to_home"] = False
                # Store the active token so logout_user() can delete it from DB.
                st.session_state["_auth_session_token"] = _tok
                try:
                    st.query_params.pop("_st", None)
                    st.query_params.pop("auth", None)
                except Exception:
                    pass
                # Inject JWT interceptor for this restored session.
                try:
                    from utils.state_sync import inject_fetch_interceptor as _inject_interceptor
                    _inject_interceptor()
                except Exception:
                    pass
                return True
            else:
                _clear_session_from_storage()
                st.query_params.pop("_st", None)
    except Exception:
        pass
    # ── Portal routing: dedicated sign-in / sign-up view ──────────────────
    # If ?auth=signup or ?auth=login is in the URL, show the focused portal
    # instead of the full marketing landing page.  This is the "Sign Up" /
    # "Log In" destination linked from the nav bar buttons.
    _auth_mode = st.query_params.get("auth", "")

    # ?????? Email verification link handler (?auth=verify&token=...) ???????????????????????????????????????
    if _auth_mode == "verify":
        _vtok = st.query_params.get("token", "")
        st.markdown(_GATE_CSS, unsafe_allow_html=True)
        _render_email_verification_result(_vtok)
        return False

    # ?????? Email-link password reset handler (?auth=reset&token=...) ????????????????????????????????????
    if _auth_mode == "reset":
        _rtok = st.query_params.get("token", "")
        st.markdown(_GATE_CSS, unsafe_allow_html=True)
        _render_token_reset_form(_rtok)
        return False

    # ?????? ?auth=verified: redirect from /api/auth/verify-email GET ???????????????????????????????????????
    if _auth_mode == "verified":
        try:
            st.query_params.pop("auth", None)
        except Exception:
            pass
        st.toast("✅ Email verified! Your account is fully activated.", icon="🎉")

    if _auth_mode in ("signup", "login"):
        st.markdown(_GATE_CSS, unsafe_allow_html=True)
        _render_auth_portal(_auth_mode, _get_logo_b64())
        return False

    # ── Inject CSS ────────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    # ── Logo base64 ───────────────────────────────────────
    _logo_b64 = _get_logo_b64()

    # ── Ticker items ──────────────────────────────────────
    _ticker = (
        '<span class="ag-ticker-live"><span class="ag-ticker-dot"></span> TERMINAL ACTIVE</span>'
        '<span class="ag-ticker-item"><span class="lbl">Neural Convergence</span> <span class="v">62.4%</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">Props Ingested</span> <span class="v">347</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">Ensemble Models</span> <span class="v">6/6</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">SAFE Score Avg</span> <span class="v">71.2</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">Edge Detected</span> <span class="v">+4.8%</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">Bankroll ROI</span> <span class="v">+18.3%</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">CLV Capture</span> <span class="v">92%</span></span>'
        '<span class="ag-ticker-item"><span class="lbl">Quants Online</span> <span class="v">1,247</span></span>'
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
      <div class="ag-pulse-ring"></div>
      <div class="ag-pulse-ring-2"></div>
    </div>

    <div class="ag-ticker">
      <div class="ag-ticker-track">{_ticker}{_ticker}</div>
    </div>

    <div class="ag-logo-section">{_logo_html}<div class="ag-logo-ring"></div></div>

    <div class="ag-hero">
      <div class="ag-hero-bg"></div>
      <div class="ag-hero-inner">
      <div class="ag-hero-ai-badge"><span class="ai-dot"></span> NEURAL ENGINE v6.0 &mdash; ENSEMBLE MODELING ACTIVE &mdash; 6/6 MODELS ONLINE</div>
      <h1><span class="hero-l1">The House</span><span class="hero-l2">Has a Problem.</span></h1>
      <div class="ag-hero-divider"></div>
      <div class="ag-hero-its-us">It&rsquo;s Us.</div>
      <div class="ag-hero-sub">
        <strong>A proprietary quantitative intelligence terminal. Not a tipster. Not a tout.</strong><br>
        Every night, 6 ensemble models execute a full Quantitative Simulation across 300+ props on
        PrizePicks, DraftKings &amp; Underdog &mdash; generating a <strong>SAFE Score&trade;</strong> (0&ndash;100)
        via Neural Convergence, real-time Edge Detection &amp; closing-line value analysis.
        The uninformed public bets on instinct. You bet on <strong>mathematical precision</strong>.
      </div>
      <div class="ag-hero-badges">
        <span class="ag-hero-badge primary"><span class="badge-ico">&#x26A1;</span> Free Terminal Access</span>
        <span class="ag-hero-badge"><span class="badge-ico">&#x25C6;</span> 62.4% Neural Convergence</span>
        <span class="ag-hero-badge"><span class="badge-ico">&#x2022;</span> SAFE Score&trade; Algorithm</span>
        <span class="ag-hero-badge"><span class="badge-ico">&#x25A0;</span> NBA Edge Detection</span>
      </div>
      <div class="ag-hero-cta">
        <a class="ag-hero-cta-primary" href="?auth=signup">&#x26A1; Access Free Terminal &mdash; Zero Cost</a>
        <a class="ag-hero-cta-secondary" href="?auth=login">Existing Operator? Log In &#x2192;</a>
        <div class="ag-hero-cta-trust">&#x1F512; No credit card &nbsp;&middot;&nbsp; 10-second deployment &nbsp;&middot;&nbsp; 2,400+ quants already extracting edge</div>
      </div>
      </div>
    </div>

    <!-- Proof strip: 4 oversized stats -->
    <div class="ag-proof-strip">
      <div class="ag-proof-inner">
        <div class="ag-proof-stat">
          <div class="ag-proof-big">62.4%</div>
          <div class="ag-proof-label">Neural Convergence Rate</div>
          <div class="ag-proof-sub">8,400+ quantified outputs</div>
        </div>
        <div class="ag-proof-stat">
          <div class="ag-proof-big">300+</div>
          <div class="ag-proof-label">Props Simulated / Night</div>
          <div class="ag-proof-sub">3 platforms, full market coverage</div>
        </div>
        <div class="ag-proof-stat">
          <div class="ag-proof-big">+18.3%</div>
          <div class="ag-proof-label">Verified ROI Edge</div>
          <div class="ag-proof-sub">Rolling 30-day sim window</div>
        </div>
        <div class="ag-proof-stat">
          <div class="ag-proof-big">$0</div>
          <div class="ag-proof-label">Terminal Access Cost</div>
          <div class="ag-proof-sub">Competitors charge $99&ndash;$299/mo</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Free Picks Today — shown BEFORE the login form ────────────────────────
    # Auto-refreshing fragment re-queries the DB every 3 min so visitors
    # see today's picks as soon as the background scheduler generates them.
    st.markdown(
        '<div id="sec-picks" data-section-id="picks" style="height:0;overflow:hidden;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown("""
<div style="text-align:center;padding:8px 0 4px;">
  <div style="display:inline-block;font-family:'JetBrains Mono',monospace;font-size:0.52rem;font-weight:800;
    color:#020509;background:linear-gradient(135deg,#00ff80,#00e5ff);padding:3px 14px;border-radius:4px;
    letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px;">&#x25C6; QUANTITATIVE SIMULATION OUTPUT</div>
  <h2 style="font-family:'Archivo Black','Syne',sans-serif;font-size:1.35rem;font-weight:900;font-style:italic;color:#fff;margin:0 0 6px;text-transform:uppercase;letter-spacing:-0.02em;">
    Tonight&rsquo;s Edge Detections &mdash; Unrestricted Access</h2>
  <p style="font-size:0.78rem;color:rgba(255,255,255,0.35);margin:0 0 4px;font-family:'JetBrains Mono',monospace;">
    Top 5 highest SAFE Score&trade; outputs from tonight&rsquo;s Ensemble Model pass. No paywall. Refreshed each simulation cycle.</p>
</div>""", unsafe_allow_html=True)
    _render_free_picks_fragment()

    st.markdown('<div style="margin:8px 0 4px;border-top:1px solid rgba(0,255,128,0.08);"></div>', unsafe_allow_html=True)

    # ── Auth tabs + forms ─────────────────────────────────
    tab_signup, tab_login = st.tabs(["\u26A1  Deploy Free Terminal", "\U0001F513  Operator Login"])

    with tab_signup:
        _render_signup_form()

    with tab_login:
        _render_login_form()

    # ── Sticky Navigation Bar ────────────────────────────────
    # Injected via st.markdown so it lives in the parent DOM (not an iframe)
    # and can use position:fixed to stick to the viewport.
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
/* Smooth scrolling for all Streamlit scroll containers */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
.main .block-container {{
  scroll-behavior: smooth !important;
}}
a.spp-nav-pill, a.spp-nav-cta, a.spp-btt {{
  text-decoration: none !important;
  color: inherit;
}}
@keyframes navSlideDown{{from{{opacity:0;transform:translateY(-100%)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes navPillGlow{{0%,100%{{box-shadow:0 0 0 0 rgba(0,213,89,0)}}50%{{box-shadow:0 0 16px 4px rgba(0,213,89,0.12)}}}}
@keyframes navLogoSpin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}

.spp-nav-dock{{
  position:fixed;top:50px;left:0;right:0;z-index:999999;
  display:flex;align-items:center;gap:4px;
  padding:6px 8px 6px 12px;
  width:fit-content;max-width:min(92vw, 960px);
  margin-left:auto;margin-right:auto;
  background:rgba(5,8,18,0.88);
  backdrop-filter:blur(48px) saturate(1.8);-webkit-backdrop-filter:blur(48px) saturate(1.8);
  border:1px solid rgba(255,255,255,0.1);
  border-top:1px solid rgba(0,213,89,0.18);
  border-radius:100px;
  scrollbar-width:none;
  box-shadow:0 8px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04) inset, 0 0 30px rgba(0,213,89,0.04);
  animation:navSlideDown 0.5s cubic-bezier(0.16,1,0.3,1) both;
  transition:transform 0.4s cubic-bezier(0.16,1,0.3,1), opacity 0.3s, box-shadow 0.3s;
}}
.spp-nav-dock:hover{{
  box-shadow:0 12px 48px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.07) inset, 0 0 40px rgba(0,213,89,0.06);
}}
.spp-nav-dock.nav-hidden{{transform:translateY(-140%);opacity:0}}
.spp-nav-dock::-webkit-scrollbar{{display:none}}

/* Brand */
.spp-nav-brand{{
  display:flex;align-items:center;gap:8px;
  flex-shrink:0;cursor:pointer;
  padding:2px 10px 2px 2px;
  border-right:1px solid rgba(255,255,255,0.06);
  margin-right:4px;
  transition:opacity 0.3s;
}}
.spp-nav-brand:hover{{opacity:0.8}}
.spp-nav-logo-wrap{{
  width:32px;height:32px;border-radius:10px;
  background:linear-gradient(135deg,rgba(0,213,89,0.15),rgba(45,158,255,0.1));
  border:1px solid rgba(0,213,89,0.2);
  display:flex;align-items:center;justify-content:center;
  overflow:hidden;flex-shrink:0;
  transition:all 0.3s;
}}
.spp-nav-brand:hover .spp-nav-logo-wrap{{
  border-color:rgba(0,213,89,0.4);
  box-shadow:0 0 16px rgba(0,213,89,0.15);
}}
.spp-nav-logo{{width:22px;height:22px;border-radius:6px;object-fit:contain;}}
.spp-nav-wordmark{{
  font-family:'Space Grotesk',sans-serif;font-size:0.82rem;font-weight:800;
  color:rgba(255,255,255,0.9);letter-spacing:-0.02em;white-space:nowrap;
}}
.spp-nav-wordmark .gr{{
  background:linear-gradient(135deg,#00D559,#2D9EFF);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}}

/* Pills container */
.spp-nav-pills{{
  display:flex;align-items:center;gap:3px;
  overflow-x:auto;scrollbar-width:none;flex:1;justify-content:center;
}}
.spp-nav-pills::-webkit-scrollbar{{display:none}}
.spp-nav-pill{{
  flex-shrink:0;
  font-family:'Space Grotesk',sans-serif;font-size:0.68rem;font-weight:600;
  color:rgba(255,255,255,0.5);
  background:transparent;
  border:1px solid transparent;
  border-radius:100px;padding:6px 14px;
  cursor:pointer;transition:all 0.2s cubic-bezier(0.16,1,0.3,1);
  text-decoration:none;white-space:nowrap;
  letter-spacing:0.02em;
  position:relative;
}}
.spp-nav-pill:hover{{
  color:rgba(255,255,255,0.9);
  background:rgba(255,255,255,0.06);
  border-color:rgba(255,255,255,0.08);
}}
.spp-nav-pill.active{{
  color:#fff;
  background:rgba(0,213,89,0.14);
  border-color:rgba(0,213,89,0.3);
  box-shadow:0 0 20px rgba(0,213,89,0.12), 0 0 0 1px rgba(0,213,89,0.1) inset;
  font-weight:700;
}}
.spp-nav-pill .ni{{margin-right:3px;font-size:0.68rem}}
/* Log In nav pill — outlined style */
#nav-login-cta{{
  color:rgba(255,255,255,0.65);
  border:1px solid rgba(255,255,255,0.14);
  background:rgba(255,255,255,0.03);
}}
#nav-login-cta:hover{{
  color:#fff;
  border-color:rgba(255,255,255,0.28);
  background:rgba(255,255,255,0.07);
}}

/* CTA pill — premium shimmer button */
.spp-nav-cta{{
  flex-shrink:0;
  font-family:'Space Grotesk',sans-serif;font-size:0.62rem;font-weight:800;
  color:#050910;
  background:linear-gradient(135deg,#00E865 0%,#00D559 50%,#00B74D 100%);
  border:1px solid rgba(255,255,255,0.18);
  border-radius:100px;
  padding:7px 18px;
  cursor:pointer;text-decoration:none;white-space:nowrap;
  letter-spacing:0.06em;text-transform:uppercase;
  box-shadow:0 0 18px rgba(0,213,89,0.4), 0 2px 8px rgba(0,213,89,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
  transition:all 0.25s;
  margin-left:6px;
  position:relative;overflow:hidden;
}}
.spp-nav-cta::after{{
  content:'';
  position:absolute;top:0;left:-100%;width:55%;height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.25),transparent);
  transform:skewX(-20deg);
  transition:left 0.45s;
}}
.spp-nav-cta:hover{{
  transform:translateY(-1px);
  box-shadow:0 0 28px rgba(0,213,89,0.55), 0 4px 16px rgba(0,213,89,0.3), inset 0 1px 0 rgba(255,255,255,0.2);
  background:linear-gradient(135deg,#00FF75 0%,#00E865 50%,#00C04B 100%);
}}
.spp-nav-cta:hover::after{{left:150%}}

/* Back to top */
.spp-btt{{
  position:fixed;bottom:28px;right:28px;z-index:999998;
  width:44px;height:44px;border-radius:14px;
  display:flex;align-items:center;justify-content:center;
  background:rgba(8,12,24,0.8);
  border:1px solid rgba(255,255,255,0.08);
  color:rgba(255,255,255,0.5);font-size:1rem;cursor:pointer;
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  box-shadow:0 4px 20px rgba(0,0,0,0.4);
  transition:all 0.3s cubic-bezier(0.16,1,0.3,1);
  opacity:0;pointer-events:none;
  transform:translateY(12px);
}}
.spp-btt.visible{{opacity:1;pointer-events:auto;transform:translateY(0)}}
.spp-btt:hover{{
  background:rgba(0,213,89,0.15);
  border-color:rgba(0,213,89,0.3);
  color:#00D559;
  transform:translateY(-3px);
  box-shadow:0 8px 32px rgba(0,213,89,0.2);
}}
@media(max-width:768px){{
  .spp-nav-dock{{
    top:42px;padding:4px 6px 4px 8px;gap:2px;
    max-width:97vw;border-radius:18px;
  }}
  .spp-nav-pill{{font-size:0.58rem;padding:5px 10px}}
  .spp-nav-wordmark{{display:none}}
  .spp-nav-brand{{padding:2px 6px 2px 2px;margin-right:2px}}
  .spp-nav-logo-wrap{{width:28px;height:28px;border-radius:8px}}
  .spp-nav-logo{{width:18px;height:18px}}
  .spp-nav-cta{{font-size:0.56rem;padding:5px 12px}}
  .spp-btt{{width:38px;height:38px;bottom:16px;right:12px;font-size:0.9rem;border-radius:12px}}
}}
@media(max-width:520px){{
  .spp-nav-dock{{
    top:38px;padding:3px 4px 3px 6px;gap:1px;
    max-width:98vw;border-radius:16px;
  }}
  .spp-nav-pill .ni{{display:none}}
  .spp-nav-pill{{padding:4px 8px;font-size:0.52rem}}
  .spp-nav-cta{{padding:4px 10px;font-size:0.5rem}}
  .spp-nav-brand{{padding:1px 4px 1px 1px;margin-right:1px;border-right:none}}
  .spp-nav-logo-wrap{{width:24px;height:24px;border-radius:7px}}
  .spp-nav-logo{{width:16px;height:16px}}
  .spp-btt{{width:36px;height:36px;bottom:14px;right:10px;font-size:0.85rem;border-radius:10px}}
}}
@media(max-width:380px){{
  .spp-nav-dock{{
    top:34px;padding:2px 3px 2px 4px;gap:0px;
    max-width:99vw;border-radius:14px;
    overflow-x:auto;-webkit-overflow-scrolling:touch;
  }}
  .spp-nav-pill{{padding:3px 6px;font-size:0.48rem;letter-spacing:-0.01em}}
  .spp-nav-cta{{padding:3px 8px;font-size:0.46rem;margin-left:2px}}
  .spp-nav-logo-wrap{{width:22px;height:22px;border-radius:6px}}
  .spp-nav-logo{{width:14px;height:14px}}
}}
</style>
<nav class="spp-nav-dock" id="spp-nav-dock">
  <div class="spp-nav-brand" id="nav-top-btn">
    <div class="spp-nav-logo-wrap">
      {'<img class="spp-nav-logo" src="data:image/png;base64,' + _logo_b64 + '" alt="SPP">' if _logo_b64 else '<span style="font-size:1rem">&#x1F3AF;</span>'}
    </div>
    <span class="spp-nav-wordmark">Smart<span class="gr">Pick</span>Pro</span>
  </div>
  <div class="spp-nav-pills">
    <a class="spp-nav-pill" id="nav-how" href="#sec-how-it-works"><span class="ni">&#x1F3AF;</span>How</a>
    <a class="spp-nav-pill" id="nav-features" href="#sec-features"><span class="ni">&#x26A1;</span>Features</a>
    <a class="spp-nav-pill" id="nav-picks" href="#sec-picks"><span class="ni">&#x1F4CA;</span>Picks</a>
    <a class="spp-nav-pill" id="nav-tracker" href="#sec-tracker"><span class="ni">&#x1F4C8;</span>Tracker</a>
    <a class="spp-nav-pill" id="nav-pricing" href="#sec-pricing"><span class="ni">&#x1F4B0;</span>Pricing</a>
    <a class="spp-nav-pill" id="nav-faq" href="#sec-faq"><span class="ni">&#x2753;</span>FAQ</a>
  </div>
  <a class="spp-nav-pill" id="nav-login-cta" href="?auth=login" style="flex-shrink:0;">&#x1F513; Log In</a>
  <a class="spp-nav-cta" id="nav-signup-cta" href="?auth=signup">Sign Up Free</a>
</nav>
<a class="spp-btt" id="spp-btt" href="#" title="Back to top">&#x2191;</a>
""", unsafe_allow_html=True)

    # ── Nav + Back-to-top JS ──
    # Injects a <script> into the parent document so handlers run in the
    # correct DOM context — avoids cross-frame access limitations.
    st.html("""<script>
(function(){
  try{
    var pdoc=window.parent.document;
    if(!pdoc||!pdoc.body) return;
    /* Avoid double-injection */
    if(pdoc.getElementById('spp-nav-js')) return;
    var s=pdoc.createElement('script');
    s.id='spp-nav-js';
    s.textContent=`
(function(){
  var MAX_TRIES=60, INTERVAL=120, tries=0;
  function init(){
    var dock=document.getElementById('spp-nav-dock');
    if(!dock){if(++tries<MAX_TRIES){setTimeout(init,INTERVAL);}return;}
    var sc=document.querySelector('[data-testid="stMain"]')
        ||document.querySelector('section.main')
        ||document.querySelector('[data-testid="stAppViewContainer"]');
    function getScrollY(){return sc?sc.scrollTop:(window.pageYOffset||document.documentElement.scrollTop);}
    function smoothTo(el){if(!el)return;if(sc){sc.scrollTo({top:el.offsetTop-80,behavior:'smooth'});}else{el.scrollIntoView({behavior:'smooth',block:'start'});}}
    function scrollTop(){if(sc){sc.scrollTo({top:0,behavior:'smooth'});}else{window.scrollTo({top:0,behavior:'smooth'});}}
    var map={'nav-how':'sec-how-it-works','nav-features':'sec-features','nav-picks':'sec-picks',
             'nav-tracker':'sec-tracker','nav-pricing':'sec-pricing','nav-faq':'sec-faq'};
    Object.keys(map).forEach(function(k){
      var b=document.getElementById(k);
      if(b){b.addEventListener('click',function(e){e.preventDefault();var t=document.getElementById(map[k]);if(t)smoothTo(t);});}
    });
    /* nav-signup-cta now uses a real URL (?auth=signup) — no JS override needed */
    var brand=document.getElementById('nav-top-btn');
    if(brand){brand.addEventListener('click',function(e){e.preventDefault();scrollTop();});}
    var btt=document.getElementById('spp-btt');
    if(btt){btt.addEventListener('click',function(e){e.preventDefault();scrollTop();});}
    var lastY=0;
    var sIds=['how-it-works','features','picks','tracker','pricing','faq'];
    var pMap={'how-it-works':'nav-how','features':'nav-features','picks':'nav-picks',
              'tracker':'nav-tracker','pricing':'nav-pricing','faq':'nav-faq'};
    function onScroll(){
      var sy=getScrollY();
      if(btt){if(sy>600){btt.classList.add('visible');}else{btt.classList.remove('visible');}}
      if(dock){if(sy>lastY&&sy>200){dock.classList.add('nav-hidden');}else{dock.classList.remove('nav-hidden');}}
      var aid='';
      for(var i=sIds.length-1;i>=0;i--){var el=document.querySelector('[data-section-id="'+sIds[i]+'"]');if(el&&el.getBoundingClientRect().top<=120){aid=sIds[i];break;}}
      document.querySelectorAll('.spp-nav-pill').forEach(function(p){p.classList.remove('active');});
      if(aid&&pMap[aid]){var ap=document.getElementById(pMap[aid]);if(ap){ap.classList.add('active');}}
      lastY=sy;
    }
    (sc||window).addEventListener('scroll',onScroll,{passive:true});
    onScroll();
    window.__sppScrollTop=scrollTop;
  }
  init();
})();
`;
    pdoc.body.appendChild(s);
  }catch(e){}
})();
</script>""")

    # ── Platform logos strip ──
    st.markdown("""
    <div style="text-align:center;padding:36px 0 20px">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.52rem;font-weight:800;
           color:rgba(255,255,255,0.18);text-transform:uppercase;letter-spacing:0.16em;
           margin-bottom:20px">Works&nbsp;with&nbsp;your&nbsp;platform</div>
      <div style="display:flex;justify-content:center;align-items:stretch;gap:16px;flex-wrap:wrap">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;
             padding:18px 28px;
             background:linear-gradient(168deg,rgba(8,14,28,0.97),rgba(5,9,16,0.99));
             border:1px solid rgba(45,158,255,0.18);border-radius:18px;
             box-shadow:0 0 40px rgba(45,158,255,0.08);transition:all 0.3s">
          <span style="font-size:1.8rem;filter:drop-shadow(0 0 12px rgba(45,158,255,0.3))">&#x1F3AF;</span>
          <span style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.9rem;
                color:#fff;letter-spacing:-0.01em">PrizePicks</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;
                color:rgba(45,158,255,0.6);letter-spacing:0.08em">DAILY FANTASY</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;
             padding:18px 28px;
             background:linear-gradient(168deg,rgba(8,14,28,0.97),rgba(5,9,16,0.99));
             border:1px solid rgba(249,198,43,0.18);border-radius:18px;
             box-shadow:0 0 40px rgba(249,198,43,0.06);transition:all 0.3s">
          <span style="font-size:1.8rem;filter:drop-shadow(0 0 12px rgba(249,198,43,0.3))">&#x1F43E;</span>
          <span style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.9rem;
                color:#fff;letter-spacing:-0.01em">Underdog</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;
                color:rgba(249,198,43,0.6);letter-spacing:0.08em">PICK &apos;EM</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;
             padding:18px 28px;
             background:linear-gradient(168deg,rgba(8,14,28,0.97),rgba(5,9,16,0.99));
             border:1px solid rgba(0,213,89,0.18);border-radius:18px;
             box-shadow:0 0 40px rgba(0,213,89,0.06);transition:all 0.3s">
          <span style="font-size:1.8rem;filter:drop-shadow(0 0 12px rgba(0,213,89,0.3))">&#x1F451;</span>
          <span style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.9rem;
                color:#fff;letter-spacing:-0.01em">DK&nbsp;Pick6</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:0.48rem;font-weight:700;
                color:rgba(0,213,89,0.6);letter-spacing:0.08em">DAILY FANTASY</span>
        </div>
      </div>
      <div style="font-family:'Inter',sans-serif;font-size:0.58rem;color:rgba(255,255,255,0.12);
           margin-top:14px;letter-spacing:0.02em">&#x2795; manual entry for any sportsbook or platform</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Social proof ticker ──
    st.markdown("""
    <style>
    @keyframes spPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.5;transform:scale(0.8)}}
    @keyframes spCount{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
    .sp-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;
      background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.1);
      border-radius:20px;overflow:hidden;margin:4px 0 28px;
      animation:spCount 0.6s 0.2s cubic-bezier(0.22,1,0.36,1) both}
    .sp-stat{text-align:center;padding:18px 12px;
      background:linear-gradient(168deg,rgba(8,14,28,0.97),rgba(5,9,16,0.99));
      position:relative}
    .sp-stat:not(:last-child)::after{content:'';position:absolute;right:0;top:20%;bottom:20%;
      width:1px;background:rgba(255,255,255,0.04)}
    .sp-val{font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:800;
      line-height:1;margin-bottom:4px}
    .sp-val.g{color:#00D559;text-shadow:0 0 24px rgba(0,213,89,0.25)}
    .sp-val.b{color:#2D9EFF;text-shadow:0 0 24px rgba(45,158,255,0.25)}
    .sp-val.y{color:#F9C62B;text-shadow:0 0 24px rgba(249,198,43,0.25)}
    .sp-val.w{color:#fff;text-shadow:0 0 24px rgba(255,255,255,0.1)}
    .sp-lbl{font-family:'JetBrains Mono',monospace;font-size:0.5rem;font-weight:700;
      color:rgba(255,255,255,0.28);text-transform:uppercase;letter-spacing:0.1em}
    @media(max-width:520px){
      .sp-strip{grid-template-columns:repeat(2,1fr)}
      .sp-val{font-size:1.25rem}
    }
    </style>
    <div class="sp-strip">
      <div class="sp-stat">
        <div class="sp-val g">2,400+</div>
        <div class="sp-lbl">Sharps Inside</div>
      </div>
      <div class="sp-stat">
        <div class="sp-val b">8,400+</div>
        <div class="sp-lbl">Picks Graded</div>
      </div>
      <div class="sp-stat">
        <div class="sp-val y">62.4%</div>
        <div class="sp-lbl">Verified Hit Rate</div>
      </div>
      <div class="sp-stat">
        <div class="sp-val w">$0</div>
        <div class="sp-lbl">Free Forever</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Section anchor: How It Works ──
    st.markdown('<div id="sec-how-it-works" data-section-id="how-it-works" style="height:0;overflow:hidden;"></div>', unsafe_allow_html=True)

    # ── Below-fold: How It Works + What's Inside + Product Preview ──
    st.markdown("""
    <!-- How It Works -->
    <div class="ag-section">
    <div class="ag-how">
      <div class="ag-section-head">
        <h3>From Zero to <span class="em">Quantifiable Edge</span> in 3 Deployments</h3>
        <p>Terminal initialization takes 30 seconds. Your first ensemble-graded outputs are ready immediately.</p>
      </div>
      <div class="ag-how-steps">
        <div class="ag-how-step">
          <span class="ag-how-num">1</span>
          <span class="ag-how-ico">&#x1F4DD;</span>
          <div class="ag-how-title">Initialize Your Free Terminal</div>
          <div class="ag-how-desc">Email and password &mdash; done. No credit card. No trial window. You receive full, permanent access to the Quantitative Simulation Matrix, all 6 ensemble models, and every SAFE Score output. Permanent. Zero cost.</div>
          <span class="ag-how-arrow">&#x25B6;</span>
        </div>
        <div class="ag-how-step">
          <span class="ag-how-num">2</span>
          <span class="ag-how-ico">&#x1F3AF;</span>
          <div class="ag-how-title">Execute on High-Confidence Edge Signals</div>
          <div class="ag-how-desc">Every prop receives a SAFE Score&trade; (0&ndash;100), edge %, neural convergence probability, and AI projection. Filter for 70+ scores and eliminate the noise. Ensemble modeling does the quantitative work for you.</div>
          <span class="ag-how-arrow">&#x25B6;</span>
        </div>
        <div class="ag-how-step">
          <span class="ag-how-num">3</span>
          <span class="ag-how-ico">&#x1F4B0;</span>
          <div class="ag-how-title">Extract ROI. Track Everything.</div>
          <div class="ag-how-desc">62.4% neural convergence rate across 8,400+ graded outputs. The built-in Bet Tracker auto-grades results, monitors bankroll trajectory, calculates ROI by platform, and identifies which SAFE Score thresholds are generating alpha for your strategy.</div>
        </div>
      </div>
    </div>
    </div><!-- /ag-section part 1 -->

    """, unsafe_allow_html=True)

    # ── SAFE Score Visual Explainer — rendered via st.html() to bypass
    #    Streamlit's markdown parser which chokes on deeply nested inline-style divs ──
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;overflow-y:hidden}
</style>
<div style="text-align:center;padding:48px 20px 32px;max-width:680px;margin:0 auto">
<div style="font-family:'Archivo Black','Space Grotesk',sans-serif;font-size:0.65rem;font-weight:900;font-style:italic;
           color:rgba(0,255,128,0.65);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px">
        Proprietary Intelligence Stack</div>
      <div style="font-family:'Archivo Black','Syne',sans-serif;font-size:1.15rem;font-weight:900;font-style:italic;
           color:rgba(255,255,255,0.9);margin-bottom:24px;text-transform:uppercase;letter-spacing:-0.02em">
        How the <span style="background:linear-gradient(135deg,#00ff80,#00e5ff);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">SAFE Score&trade;</span> Algorithm Executes</div>

  <div style="display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;margin-bottom:24px">
    <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:6px;max-width:360px">
      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           padding:5px 10px;border-radius:8px;background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.15);
           color:rgba(0,213,89,0.7)">XGBoost</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           padding:5px 10px;border-radius:8px;background:rgba(45,158,255,0.08);border:1px solid rgba(45,158,255,0.15);
           color:rgba(45,158,255,0.7)">LightGBM</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           padding:5px 10px;border-radius:8px;background:rgba(192,132,252,0.08);border:1px solid rgba(192,132,252,0.15);
           color:rgba(192,132,252,0.7)">Ridge</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           padding:5px 10px;border-radius:8px;background:rgba(249,198,43,0.08);border:1px solid rgba(249,198,43,0.15);
           color:rgba(249,198,43,0.7)">Bayesian</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           padding:5px 10px;border-radius:8px;background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.15);
           color:rgba(0,213,89,0.7)">LSTM</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           padding:5px 10px;border-radius:8px;background:rgba(45,158,255,0.08);border:1px solid rgba(45,158,255,0.15);
           color:rgba(45,158,255,0.7)">Random Forest</span>
    </div>

    <div style="font-size:1.2rem;color:rgba(255,255,255,0.2)">&#x2192;</div>

    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
         border-radius:12px;padding:12px 18px;text-align:center">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px">
        Ensemble Vote</div>
      <div style="font-size:1.2rem">&#x1F5F3;&#xFE0F;</div>
    </div>

    <div style="font-size:1.2rem;color:rgba(255,255,255,0.2)">&#x2192;</div>

    <div style="background:linear-gradient(135deg,rgba(0,213,89,0.1),rgba(45,158,255,0.08));
         border:1.5px solid rgba(0,213,89,0.2);border-radius:14px;padding:14px 20px;text-align:center;
         position:relative;overflow:hidden">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;
           color:rgba(0,213,89,0.5);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px">
        SAFE Score</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:1.6rem;font-weight:800;
           background:linear-gradient(135deg,#00D559,#2D9EFF);
           -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">84</div>
    </div>
  </div>

  <div style="max-width:440px;margin:0 auto 16px">
    <div style="height:8px;border-radius:4px;background:linear-gradient(90deg,
         #ff4444 0%,#ff8800 25%,#F9C62B 40%,#00D559 65%,#2D9EFF 100%);
         position:relative;overflow:visible">
      <div style="position:absolute;left:84%;top:-3px;width:14px;height:14px;
           background:#00D559;border:2px solid rgba(8,12,24,0.9);border-radius:50%;
           transform:translateX(-50%);box-shadow:0 0 10px rgba(0,213,89,0.4)"></div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:6px;
         font-family:'JetBrains Mono',monospace;font-size:0.5rem;color:rgba(255,255,255,0.25)">
      <span>0 &mdash; Skip</span><span>50 &mdash; Caution</span><span>70 &mdash; Play</span><span>100 &mdash; Lock</span>
    </div>
  </div>

  <p style="font-family:'Inter',sans-serif;font-size:0.7rem;color:rgba(255,255,255,0.35);
     max-width:460px;margin:0 auto;line-height:1.6">
    Six AI models independently analyze every prop. They vote, and the SAFE Score
    synthesizes their agreement, historical accuracy, matchup context, and line movement
    into a single number you can act on.</p>
</div>
""")

    # ── 60-Second Demo + rest of below-fold (continued st.markdown) ──
    st.markdown("""
    <div class="ag-section">
    <!-- ── 60-Second Demo ── -->
    <div class="ag-reveal" style="text-align:center;padding:40px 0 16px">
      <div style="font-family:'Archivo Black','Space Grotesk',sans-serif;font-size:0.65rem;font-weight:900;font-style:italic;
           color:rgba(0,255,128,0.6);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px">
        Intelligence Architecture</div>
      <div style="font-family:'Archivo Black','Syne',sans-serif;font-size:1.15rem;font-weight:900;font-style:italic;
           color:rgba(255,255,255,0.9);margin-bottom:8px;text-transform:uppercase;letter-spacing:-0.02em">
        What You&rsquo;ll Access in <span style="background:linear-gradient(135deg,#00ff80,#00e5ff);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">60 Seconds</span></div>
      <p style="font-family:'Inter',sans-serif;font-size:0.75rem;color:rgba(255,255,255,0.4);max-width:460px;margin:0 auto 24px">
        Deploy your terminal, configure your platform, and start receiving quantitative edge signals immediately. Zero configuration required.</p>
      <div style="display:flex;justify-content:center;gap:20px;flex-wrap:wrap;max-width:820px;margin:0 auto">
        <div style="flex:1;min-width:220px;max-width:260px;background:rgba(255,255,255,0.02);
             border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:20px 16px;
             text-align:center;transition:all 0.3s">
          <div style="font-size:2rem;margin-bottom:8px">&#x1F4CB;</div>
          <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.8rem;
               color:rgba(255,255,255,0.85);margin-bottom:6px">AI Prop Scanner</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.65rem;color:rgba(255,255,255,0.35);line-height:1.5">
            300+ props scored every night with SAFE ratings, edge %, and projections</div>
        </div>
        <div style="flex:1;min-width:220px;max-width:260px;background:rgba(255,255,255,0.02);
             border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:20px 16px;
             text-align:center;transition:all 0.3s">
          <div style="font-size:2rem;margin-bottom:8px">&#x1F50D;</div>
          <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.8rem;
               color:rgba(255,255,255,0.85);margin-bottom:6px">Player Deep Dive</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.65rem;color:rgba(255,255,255,0.35);line-height:1.5">
            Matchup analysis, game logs, defensive DNA, and minute projections</div>
        </div>
        <div style="flex:1;min-width:220px;max-width:260px;background:rgba(255,255,255,0.02);
             border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:20px 16px;
             text-align:center;transition:all 0.3s">
          <div style="font-size:2rem;margin-bottom:8px">&#x1F4C8;</div>
          <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.8rem;
               color:rgba(255,255,255,0.85);margin-bottom:6px">Live Bet Tracker</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.65rem;color:rgba(255,255,255,0.35);line-height:1.5">
            Auto-graded results, P&amp;L chart, bankroll tracking, and model health</div>
        </div>
      </div>
    </div>

    <!-- ── Live Pick Sample Card ── -->
    <div class="ag-reveal" style="text-align:center;padding:32px 20px 8px;max-width:440px;margin:0 auto">
      <div style="font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:700;
           color:rgba(0,213,89,0.5);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:14px">
        &#x1F50D; Sample AI Output</div>
      <div style="background:linear-gradient(168deg,rgba(10,16,32,0.98),rgba(6,10,20,0.98));
           border:1.5px solid rgba(0,213,89,0.1);border-radius:18px;padding:0;overflow:hidden;
           box-shadow:0 20px 60px rgba(0,0,0,0.4),0 0 40px rgba(0,213,89,0.04);text-align:left">
        <!-- Header bar -->
        <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;
             background:rgba(0,213,89,0.04);border-bottom:1px solid rgba(0,213,89,0.08)">
          <div style="display:flex;align-items:center;gap:10px">
            <div style="width:36px;height:36px;border-radius:10px;
                 background:linear-gradient(135deg,rgba(0,213,89,0.15),rgba(45,158,255,0.1));
                 display:flex;align-items:center;justify-content:center;font-size:1.1rem">&#x1F3C0;</div>
            <div>
              <div style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.8rem;
                   color:rgba(255,255,255,0.9)">Shai Gilgeous-Alexander</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;
                   color:rgba(255,255,255,0.3)">OKC Thunder &bull; vs LAL &bull; PrizePicks</div>
            </div>
          </div>
          <div style="background:linear-gradient(135deg,#00D559,#2D9EFF);border-radius:10px;
               padding:6px 12px;text-align:center">
            <div style="font-family:'JetBrains Mono',monospace;font-size:0.5rem;font-weight:700;
                 color:rgba(0,0,0,0.5);line-height:1">SAFE</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;font-weight:800;
                 color:#000;line-height:1.1">91</div>
          </div>
        </div>
        <!-- Prop line -->
        <div style="padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.04)">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <div>
              <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;font-weight:700;
                   color:rgba(0,213,89,0.8);background:rgba(0,213,89,0.08);padding:3px 8px;
                   border-radius:6px">&#x25B2; OVER</span>
              <span style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.85rem;
                   color:rgba(255,255,255,0.85);margin-left:8px">30.5 Points</span>
            </div>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;font-weight:700;
                 color:rgba(0,213,89,0.6)">+8.4% Edge</span>
          </div>
          <!-- Mini stats row -->
          <div style="display:flex;gap:16px;flex-wrap:wrap">
            <div style="text-align:center">
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;font-weight:800;
                   color:rgba(255,255,255,0.8)">33.1</div>
              <div style="font-family:'Inter',sans-serif;font-size:0.48rem;color:rgba(255,255,255,0.25)">
                AI Projection</div>
            </div>
            <div style="text-align:center">
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;font-weight:800;
                   color:rgba(255,255,255,0.8)">78%</div>
              <div style="font-family:'Inter',sans-serif;font-size:0.48rem;color:rgba(255,255,255,0.25)">
                Win Probability</div>
            </div>
            <div style="text-align:center">
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;font-weight:800;
                   color:rgba(255,255,255,0.8)">6/6</div>
              <div style="font-family:'Inter',sans-serif;font-size:0.48rem;color:rgba(255,255,255,0.25)">
                Models Agree</div>
            </div>
            <div style="text-align:center">
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;font-weight:800;
                   color:rgba(249,198,43,0.8)">&#x1F525; 5L10</div>
              <div style="font-family:'Inter',sans-serif;font-size:0.48rem;color:rgba(255,255,255,0.25)">
                Hit Streak</div>
            </div>
          </div>
        </div>
        <!-- Matchup note -->
        <div style="padding:12px 18px;font-family:'Inter',sans-serif;font-size:0.6rem;
             color:rgba(255,255,255,0.3);line-height:1.5">
          <strong style="color:rgba(0,213,89,0.6)">Matchup Note:</strong>
          LAL allows 28.6 PPG to opposing PGs (28th). SGA has hit O30.5 in 5 of last 10 vs LAL.
          Minutes projection: 36.2 min.</div>
      </div>
      <div style="font-family:'Inter',sans-serif;font-size:0.58rem;color:rgba(255,255,255,0.2);
           margin-top:12px">This is a sample output &mdash; real picks update nightly at 5 PM ET</div>
    </div>

    <div class="ag-divider"></div>
    <div class="ag-inside ag-reveal" id="sec-features" data-section-id="features">
      <div class="ag-section-head">
        <h3>What&rsquo;s Inside<br><span class="em">The Terminal</span></h3>
        <p>The complete quantitative intelligence stack &mdash; precision-built to extract edge the public can&rsquo;t see</p>
      </div>
      <div class="ag-inside-grid">
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x26A1;</div>
          <div class="ag-inside-name">Quantitative Simulation Matrix</div>
          <div class="ag-inside-desc">The core engine. Ingests 300+ player props nightly across PrizePicks, DraftKings, and Underdog. Each prop is independently processed by 6 ensemble models and converged into a SAFE Score (0&ndash;100), edge %, neural convergence probability, and adjusted line projection.</div>
          <div class="ag-inside-tag">CORE ENGINE</div>
        </div>
        <div class="ag-inside-card">
          <div class="ag-inside-ico">&#x1F9E0;</div>
          <div class="ag-inside-name">SAFE Score&trade; Algorithm</div>
          <div class="ag-inside-desc">Proprietary 0&ndash;100 edge-detection rating that fuses Neural Convergence outputs from Ridge regression, Random Forest, XGBoost, LSTM sequence modeling, LightGBM, and Bayesian ensemble networks. One signal. Maximum information density.</div>
          <div class="ag-inside-tag">NEURAL CONVERGENCE</div>
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

    <!-- ══ TOOL SHOWCASE v3: GAME REPORT + PLAYER SIMULATOR + DARK HORSE ══ -->
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,400;0,600;0,700;0,800;0,900;1,700;1,900&family=Barlow:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
    /* ── KEYFRAMES ── */
    @keyframes tsBarGrow{from{transform:scaleX(0);transform-origin:left}to{transform:scaleX(1);transform-origin:left}}
    @keyframes agLivePulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.5)}}
    @keyframes tsFloat{0%,100%{transform:perspective(1100px) rotateY(-5deg) rotateX(2deg) translateY(0)}50%{transform:perspective(1100px) rotateY(-5deg) rotateX(2deg) translateY(-8px)}}
    @keyframes tsFloatR{0%,100%{transform:perspective(1100px) rotateY(5deg) rotateX(2deg) translateY(0)}50%{transform:perspective(1100px) rotateY(5deg) rotateX(2deg) translateY(-8px)}}
    @keyframes dhScan{0%{transform:translateY(-100%);opacity:0}30%{opacity:.6}70%{opacity:.6}100%{transform:translateY(120%);opacity:0}}
    @keyframes dhPing{0%,100%{box-shadow:0 0 0 0 rgba(249,198,43,.5)}50%{box-shadow:0 0 0 10px rgba(249,198,43,0)}}
    /* ── SECTION WRAPPER ── */
    .ag-ts-wrap{position:relative;padding:90px 0 24px;overflow:hidden;font-family:'Barlow',sans-serif}
    .ag-ts-bg-dots{position:absolute;inset:0;background-image:radial-gradient(circle,rgba(255,255,255,.025) 1px,transparent 1px);background-size:28px 28px;pointer-events:none;mask-image:radial-gradient(ellipse 85% 85% at 50% 50%,#000 20%,transparent 100%)}
    .ag-ts-noise{position:absolute;inset:0;opacity:.025;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");pointer-events:none}
    .ag-ts-orb-l{position:absolute;top:-10%;left:-15%;width:760px;height:760px;border-radius:50%;background:radial-gradient(circle,rgba(0,213,89,.13) 0%,transparent 58%);filter:blur(30px);pointer-events:none}
    .ag-ts-orb-r{position:absolute;bottom:0;right:-15%;width:860px;height:860px;border-radius:50%;background:radial-gradient(circle,rgba(249,198,43,.1) 0%,transparent 58%);filter:blur(30px);pointer-events:none}
    /* ── INTRO ── */
    .ag-ts-intro{text-align:center;padding:0 0 72px;position:relative;z-index:1}
    .ag-ts-eyebrow{display:inline-flex;align-items:center;gap:9px;font-family:'JetBrains Mono',monospace;font-size:.54rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#00D559;background:rgba(0,213,89,.07);border:1px solid rgba(0,213,89,.22);padding:7px 20px;border-radius:100px;margin-bottom:28px}
    .ag-ts-eyebrow::before{content:'';width:6px;height:6px;border-radius:50%;background:#00D559;box-shadow:0 0 12px #00D559;animation:agLivePulse 2s ease-in-out infinite;flex-shrink:0}
    .ag-ts-h1{font-family:'Barlow Condensed',sans-serif;font-size:clamp(2.6rem,5.5vw,4.8rem);font-weight:900;font-style:italic;letter-spacing:-.02em;line-height:.98;color:#fff;text-transform:uppercase;margin-bottom:20px}
    .ag-ts-h1 .g{background:linear-gradient(90deg,#00D559 0%,#00FF99 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-style:normal}
    .ag-ts-sub{font-family:'Barlow',sans-serif;font-size:.96rem;font-weight:400;color:rgba(255,255,255,.32);max-width:540px;margin:0 auto 50px;line-height:1.82;letter-spacing:.01em}
    .ag-ts-kpis{display:flex;justify-content:center;gap:0;flex-wrap:wrap;background:rgba(255,255,255,.026);border:1px solid rgba(255,255,255,.07);border-radius:20px;overflow:hidden;width:fit-content;margin:0 auto;backdrop-filter:blur(10px)}
    .ag-ts-kpi{padding:20px 40px;text-align:center;border-right:1px solid rgba(255,255,255,.06)}
    .ag-ts-kpi:last-child{border-right:none}
    .ag-ts-kpi-n{font-family:'Barlow Condensed',sans-serif;font-size:2.0rem;font-weight:900;font-style:italic;letter-spacing:-.02em;color:#fff;line-height:1;margin-bottom:5px;text-transform:uppercase}
    .ag-ts-kpi-n em{font-style:italic;background:linear-gradient(90deg,#00D559,#00FF99);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
    .ag-ts-kpi-l{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:rgba(255,255,255,.2);text-transform:uppercase;letter-spacing:.1em}
    @media(max-width:620px){.ag-ts-kpi{padding:14px 22px}.ag-ts-kpi-n{font-size:1.5rem}}
    /* ── TOOL ROWS ── */
    .ag-ts-row{display:grid;grid-template-columns:1fr 1fr;gap:72px;align-items:center;margin-bottom:120px;position:relative;z-index:1}
    .ag-ts-row.rev{direction:rtl}
    .ag-ts-row.rev>*{direction:ltr}
    @media(max-width:900px){.ag-ts-row,.ag-ts-row.rev{grid-template-columns:1fr;direction:ltr;gap:40px;margin-bottom:72px}}
    /* ── COPY PANEL ── */
    .ag-ts-tag{display:inline-flex;align-items:center;gap:8px;font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--tc,#00D559);background:color-mix(in srgb,var(--tc,#00D559) 8%,transparent);border:1px solid color-mix(in srgb,var(--tc,#00D559) 24%,transparent);padding:5px 16px;border-radius:100px;margin-bottom:20px;width:fit-content}
    .ag-ts-tag-dot{width:6px;height:6px;border-radius:50%;background:var(--tc,#00D559);box-shadow:0 0 9px var(--tc,#00D559);animation:agLivePulse 2.4s ease-in-out infinite}
    .ag-ts-copy-h{font-family:'Barlow Condensed',sans-serif;font-size:clamp(2rem,3.4vw,3.2rem);font-weight:900;font-style:italic;letter-spacing:-.02em;line-height:1.0;color:#fff;text-transform:uppercase;margin-bottom:16px}
    .ag-ts-copy-h .em{background:linear-gradient(90deg,var(--tc,#00D559),var(--tc2,#00FF99));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-style:normal}
    .ag-ts-copy-p{font-family:'Barlow',sans-serif;font-size:.9rem;font-weight:400;color:rgba(255,255,255,.36);line-height:1.86;margin-bottom:30px;letter-spacing:.01em}
    .ag-ts-list{list-style:none;padding:0;margin:0 0 36px;display:flex;flex-direction:column}
    .ag-ts-li{display:flex;align-items:flex-start;gap:14px;padding:13px 0;border-bottom:1px solid rgba(255,255,255,.045);font-family:'Barlow',sans-serif;font-size:.87rem;font-weight:400;color:rgba(255,255,255,.42);line-height:1.65;letter-spacing:.01em}
    .ag-ts-li:first-child{padding-top:0}
    .ag-ts-li:last-child{border-bottom:none;padding-bottom:0}
    .ag-ts-li b{color:rgba(255,255,255,.94);font-weight:700;font-family:'Barlow',sans-serif}
    .ag-ts-li-num{min-width:26px;height:26px;border-radius:8px;background:color-mix(in srgb,var(--tc,#00D559) 12%,transparent);border:1px solid color-mix(in srgb,var(--tc,#00D559) 28%,transparent);display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:900;color:var(--tc,#00D559);flex-shrink:0;margin-top:2px}
    .ag-ts-btn{display:inline-flex;align-items:center;gap:10px;font-family:'Barlow Condensed',sans-serif;font-size:1.0rem;font-weight:800;font-style:italic;letter-spacing:.04em;text-transform:uppercase;color:var(--tc,#00D559);background:color-mix(in srgb,var(--tc,#00D559) 9%,transparent);border:1.5px solid color-mix(in srgb,var(--tc,#00D559) 30%,transparent);padding:13px 28px;border-radius:100px;text-decoration:none;transition:all .3s cubic-bezier(.16,1,.3,1);width:fit-content}
    .ag-ts-btn span{font-style:normal;transition:transform .3s}
    .ag-ts-btn:hover{background:color-mix(in srgb,var(--tc,#00D559) 17%,transparent);border-color:color-mix(in srgb,var(--tc,#00D559) 58%,transparent);box-shadow:0 0 36px color-mix(in srgb,var(--tc,#00D559) 26%,transparent),0 12px 32px rgba(0,0,0,.35)}
    .ag-ts-btn:hover span{transform:translateX(5px)}
    /* ── MOCKUP PANEL ── */
    .ag-ts-mk-wrap{position:relative}
    .ag-ts-mk-orb{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:90%;height:90%;border-radius:50%;background:radial-gradient(circle,color-mix(in srgb,var(--tc,#00D559) 20%,transparent) 0%,transparent 63%);filter:blur(60px);pointer-events:none;z-index:0}
    .ag-ts-mk{position:relative;z-index:1;background:linear-gradient(158deg,rgba(255,255,255,.052) 0%,rgba(255,255,255,.014) 100%);border:1px solid rgba(255,255,255,.1);border-radius:22px;overflow:hidden;box-shadow:0 40px 100px rgba(0,0,0,.7),0 0 0 1px rgba(255,255,255,.05),inset 0 1px 0 rgba(255,255,255,.08);transform:perspective(1100px) rotateY(-5deg) rotateX(2deg);animation:tsFloat 6s ease-in-out infinite;transition:box-shadow .6s}
    .ag-ts-row.rev .ag-ts-mk{transform:perspective(1100px) rotateY(5deg) rotateX(2deg);animation-name:tsFloatR}
    .ag-ts-mk:hover,.ag-ts-row.rev .ag-ts-mk:hover{animation-play-state:paused;transform:perspective(1100px) rotateY(0deg) rotateX(0deg) translateY(-12px) scale(1.02)!important;box-shadow:0 55px 120px rgba(0,0,0,.75),0 0 80px color-mix(in srgb,var(--tc,#00D559) 18%,transparent),0 0 0 1px color-mix(in srgb,var(--tc,#00D559) 26%,transparent)}
    .ag-ts-mk::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent 0%,var(--tc,#00D559) 28%,var(--tc2,#00FF99) 72%,transparent 100%);z-index:3}
    .ag-mk-chrome{display:flex;align-items:center;gap:8px;padding:12px 18px;background:rgba(0,0,0,.32);border-bottom:1px solid rgba(255,255,255,.07);backdrop-filter:blur(12px)}
    .ag-mk-dots{display:flex;gap:5px}
    .ag-mk-dots span{width:9px;height:9px;border-radius:50%}
    .ag-mk-dots span:nth-child(1){background:rgba(242,67,54,.75)}
    .ag-mk-dots span:nth-child(2){background:rgba(249,198,43,.75)}
    .ag-mk-dots span:nth-child(3){background:rgba(0,213,89,.75)}
    .ag-mk-url-bar{flex:1;font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:600;color:rgba(255,255,255,.2);background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.07);border-radius:7px;padding:4px 14px;text-align:center;letter-spacing:.02em}
    .ag-mk-body{padding:20px}
    /* ── GAME REPORT MOCK ── */
    .gr2-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
    .gr2-title{font-family:'Barlow Condensed',sans-serif;font-size:.95rem;font-weight:900;font-style:italic;color:#fff;letter-spacing:-.01em;text-transform:uppercase}
    .gr2-live{display:inline-flex;align-items:center;gap:5px;font-family:'JetBrains Mono',monospace;font-size:.45rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:#00D559;background:rgba(0,213,89,.1);border:1px solid rgba(0,213,89,.24);padding:3px 11px;border-radius:100px}
    .gr2-live::before{content:'';width:5px;height:5px;border-radius:50%;background:#00D559;box-shadow:0 0 8px #00D559;animation:agLivePulse 1.6s ease-in-out infinite;flex-shrink:0}
    .gr2-game{background:rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.09);border-radius:14px;padding:14px 18px;margin-bottom:13px;display:flex;align-items:center;justify-content:space-between;position:relative;overflow:hidden}
    .gr2-game::before{content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,213,89,.05) 0%,transparent 42%,transparent 58%,rgba(45,158,255,.05) 100%);pointer-events:none}
    .gr2-team{display:flex;flex-direction:column;align-items:center;gap:4px}
    .gr2-abbr{font-family:'Barlow Condensed',sans-serif;font-size:1.6rem;font-weight:900;font-style:italic;letter-spacing:-.02em;line-height:1;text-transform:uppercase}
    .gr2-rec{font-family:'JetBrains Mono',monospace;font-size:.42rem;font-weight:600;color:rgba(255,255,255,.2);letter-spacing:.04em}
    .gr2-mid{text-align:center;flex:1}
    .gr2-vs{font-family:'Barlow Condensed',sans-serif;font-size:.65rem;font-weight:900;font-style:italic;color:rgba(255,255,255,.14);letter-spacing:.1em;text-transform:uppercase}
    .gr2-spread{font-family:'Barlow',sans-serif;font-size:.72rem;font-weight:700;color:rgba(255,255,255,.5);margin:3px 0}
    .gr2-ou{font-family:'JetBrains Mono',monospace;font-size:.42rem;color:rgba(255,255,255,.2)}
    .gr2-pills{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:13px}
    .gr2-pill{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:3px 10px;border-radius:6px;color:rgba(255,255,255,.28);background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07)}
    .gr2-pill.g{color:#00D559;background:rgba(0,213,89,.08);border-color:rgba(0,213,89,.2)}
    .gr2-pill.b{color:#2D9EFF;background:rgba(45,158,255,.08);border-color:rgba(45,158,255,.2)}
    .gr2-pill.p{color:#c084fc;background:rgba(192,132,252,.08);border-color:rgba(192,132,252,.2)}
    .gr2-sec-lbl{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.16);margin-bottom:10px}
    .gr2-bars{display:flex;flex-direction:column;gap:9px}
    .gr2-brow{display:flex;align-items:center;gap:10px}
    .gr2-blbl{font-family:'Barlow',sans-serif;font-size:.6rem;font-weight:600;color:rgba(255,255,255,.26);width:82px;flex-shrink:0;text-align:right}
    .gr2-btrack{flex:1;height:7px;background:rgba(255,255,255,.07);border-radius:4px;overflow:hidden}
    .gr2-bfill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--bc1),var(--bc2));box-shadow:0 0 12px var(--bglow);width:var(--w,50%);animation:tsBarGrow .9s cubic-bezier(.34,1.56,.64,1) forwards}
    .gr2-bval{font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:900;color:var(--bc1);width:38px;text-align:right;flex-shrink:0}
    .gr2-alert{margin-top:14px;background:rgba(0,213,89,.06);border:1px solid rgba(0,213,89,.2);border-radius:11px;padding:10px 14px;display:flex;align-items:flex-start;gap:10px}
    .gr2-alert-ico{font-size:.9rem;flex-shrink:0;margin-top:1px}
    .gr2-alert-txt{font-family:'Barlow',sans-serif;font-size:.64rem;font-weight:600;color:rgba(255,255,255,.46);line-height:1.58;letter-spacing:.01em}
    .gr2-alert-txt b{color:#00D559;font-weight:800}
    /* ── PLAYER SIM MOCK ── */
    .ps2-hd{display:flex;align-items:center;gap:14px;background:rgba(0,0,0,.24);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:13px 16px;margin-bottom:13px;position:relative;overflow:hidden}
    .ps2-hd::before{content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(249,198,43,.07) 0%,transparent 55%);pointer-events:none}
    .ps2-av{width:42px;height:42px;border-radius:12px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-family:'Barlow Condensed',sans-serif;font-size:.82rem;font-weight:900;font-style:italic;color:#020C07;background:linear-gradient(135deg,#F9C62B,#FFE066);box-shadow:0 0 22px rgba(249,198,43,.6);text-transform:uppercase}
    .ps2-info{flex:1;min-width:0}
    .ps2-name{font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:900;font-style:italic;color:#fff;letter-spacing:-.01em;margin-bottom:2px;text-transform:uppercase;line-height:1}
    .ps2-meta{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:600;color:rgba(255,255,255,.2);letter-spacing:.05em;text-transform:uppercase}
    .ps2-dh{display:inline-flex;align-items:center;gap:4px;font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:#F9C62B;background:rgba(249,198,43,.1);border:1px solid rgba(249,198,43,.3);padding:3px 10px;border-radius:100px;flex-shrink:0;animation:dhPing 2.5s ease-in-out infinite}
    .ps2-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:13px}
    .ps2-stat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:10px 6px;text-align:center}
    .ps2-stat.hi{border-color:rgba(249,198,43,.38);background:rgba(249,198,43,.07);box-shadow:0 0 20px rgba(249,198,43,.14)}
    .ps2-sv{font-family:'Barlow Condensed',sans-serif;font-size:1.15rem;font-weight:900;font-style:italic;color:#fff;letter-spacing:-.02em;line-height:1;margin-bottom:3px;text-transform:uppercase}
    .ps2-stat.hi .ps2-sv{color:#F9C62B;text-shadow:0 0 18px rgba(249,198,43,.65)}
    .ps2-sl{font-family:'JetBrains Mono',monospace;font-size:.41rem;font-weight:700;color:rgba(255,255,255,.18);text-transform:uppercase;letter-spacing:.07em}
    .ps2-vs{display:flex;align-items:center;justify-content:space-between;background:rgba(249,198,43,.06);border:1px solid rgba(249,198,43,.16);border-radius:10px;padding:9px 13px;margin-bottom:13px}
    .ps2-vs-lbl{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:rgba(255,255,255,.24);text-transform:uppercase;letter-spacing:.08em}
    .ps2-vs-nums{display:flex;align-items:baseline;gap:8px}
    .ps2-vs-sim{font-family:'Barlow Condensed',sans-serif;font-size:1.0rem;font-weight:900;font-style:italic;color:#F9C62B;text-transform:uppercase}
    .ps2-vs-sep{font-family:'JetBrains Mono',monospace;font-size:.42rem;color:rgba(255,255,255,.14)}
    .ps2-vs-book{font-family:'Barlow Condensed',sans-serif;font-size:.85rem;font-weight:700;color:rgba(255,255,255,.28);text-decoration:line-through;font-style:italic}
    .ps2-edge{font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:900;color:#00D559;background:rgba(0,213,89,.1);border:1px solid rgba(0,213,89,.24);padding:2px 9px;border-radius:5px;margin-left:auto}
    .ps2-dist{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:11px;padding:12px 14px}
    .ps2-dist-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px}
    .ps2-dist-lbl{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;color:rgba(255,255,255,.17);text-transform:uppercase;letter-spacing:.07em}
    .ps2-dist-ceil{font-family:'JetBrains Mono',monospace;font-size:.5rem;font-weight:900;color:#F9C62B}
    .ps2-dist-chart{display:flex;align-items:flex-end;gap:3px;height:38px;margin-bottom:5px}
    .ps2-dc{flex:1;border-radius:3px 3px 0 0;background:rgba(255,255,255,.08)}
    .ps2-dc.pk{background:linear-gradient(180deg,#F9C62B,rgba(249,198,43,.28));box-shadow:0 0 10px rgba(249,198,43,.42)}
    .ps2-dc.dh{background:linear-gradient(180deg,#00D559,rgba(0,213,89,.28));box-shadow:0 0 10px rgba(0,213,89,.38)}
    .ps2-dist-foot{display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;font-size:.4rem;color:rgba(255,255,255,.13);padding:0 2px}
    /* ── DARK HORSE MOCK ── */
    .dh2-wrap{position:relative;overflow:hidden}
    .dh2-scan{position:absolute;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(249,198,43,.6),transparent);animation:dhScan 3s ease-in-out infinite;pointer-events:none;z-index:4}
    .dh2-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
    .dh2-title{font-family:'Barlow Condensed',sans-serif;font-size:.95rem;font-weight:900;font-style:italic;color:#fff;letter-spacing:-.01em;text-transform:uppercase}
    .dh2-badge{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#F9C62B;background:rgba(249,198,43,.1);border:1px solid rgba(249,198,43,.28);padding:3px 10px;border-radius:5px}
    .dh2-card{background:rgba(0,0,0,.24);border:1px solid rgba(255,255,255,.08);border-radius:13px;padding:13px 15px;margin-bottom:9px;display:flex;align-items:center;gap:13px;position:relative;overflow:hidden;transition:border-color .3s}
    .dh2-card.hot{border-color:rgba(249,198,43,.38);background:rgba(249,198,43,.05)}
    .dh2-card.hot::before{content:'';position:absolute;top:0;left:0;bottom:0;width:3px;background:linear-gradient(180deg,#F9C62B,rgba(249,198,43,.2));border-radius:3px 0 0 3px}
    .dh2-rank{font-family:'Barlow Condensed',sans-serif;font-size:1.4rem;font-weight:900;font-style:italic;color:rgba(255,255,255,.1);width:28px;flex-shrink:0;text-align:center;line-height:1;text-transform:uppercase}
    .dh2-card.hot .dh2-rank{color:rgba(249,198,43,.5)}
    .dh2-player{flex:1;min-width:0}
    .dh2-pname{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;color:#fff;letter-spacing:-.01em;text-transform:uppercase;line-height:1;margin-bottom:3px}
    .dh2-pmeta{font-family:'JetBrains Mono',monospace;font-size:.42rem;font-weight:600;color:rgba(255,255,255,.2);text-transform:uppercase;letter-spacing:.05em}
    .dh2-stat{text-align:right;flex-shrink:0}
    .dh2-sval{font-family:'Barlow Condensed',sans-serif;font-size:1.1rem;font-weight:900;font-style:italic;color:#fff;letter-spacing:-.02em;line-height:1;margin-bottom:2px;text-transform:uppercase}
    .dh2-card.hot .dh2-sval{color:#F9C62B;text-shadow:0 0 14px rgba(249,198,43,.55)}
    .dh2-slbl{font-family:'JetBrains Mono',monospace;font-size:.41rem;font-weight:700;color:rgba(255,255,255,.18);text-transform:uppercase;letter-spacing:.06em}
    .dh2-edge-row{display:flex;align-items:center;gap:7px;margin-bottom:12px}
    .dh2-edge-lbl{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;color:rgba(255,255,255,.2);text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}
    .dh2-edge-bar{flex:1;height:6px;background:rgba(255,255,255,.06);border-radius:4px;overflow:hidden}
    .dh2-edge-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#F9C62B,#FFE066);box-shadow:0 0 10px rgba(249,198,43,.5);animation:tsBarGrow .9s cubic-bezier(.34,1.56,.64,1) forwards}
    .dh2-edge-val{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:900;color:#F9C62B;white-space:nowrap}
    .dh2-footer{background:rgba(249,198,43,.05);border:1px solid rgba(249,198,43,.15);border-radius:10px;padding:8px 12px;display:flex;align-items:center;gap:8px}
    .dh2-footer-ico{font-size:.8rem;flex-shrink:0}
    .dh2-footer-txt{font-family:'Barlow',sans-serif;font-size:.62rem;font-weight:600;color:rgba(255,255,255,.4);line-height:1.5;letter-spacing:.01em}
    .dh2-footer-txt b{color:#F9C62B;font-weight:800}
    </style>

    <div class="ag-ts-wrap">
      <div class="ag-ts-bg-dots"></div>
      <div class="ag-ts-orb-l"></div>
      <div class="ag-ts-orb-r"></div>

      <!-- Section intro -->
      <div class="ag-ts-intro">
        <div class="ag-ts-eyebrow">Inside the Platform</div>
        <h2 class="ag-ts-h1">THREE TOOLS.<br><span class="g">ONE EDGE.</span></h2>
        <p class="ag-ts-sub">Not a black box. Every tool shows its work &mdash; so you own the edge, not just borrow it.</p>
        <div class="ag-ts-kpis">
          <div class="ag-ts-kpi"><div class="ag-ts-kpi-n"><em>10k</em></div><div class="ag-ts-kpi-l">Sims / Player</div></div>
          <div class="ag-ts-kpi"><div class="ag-ts-kpi-n"><em>6</em></div><div class="ag-ts-kpi-l">AI Models Fused</div></div>
          <div class="ag-ts-kpi"><div class="ag-ts-kpi-n"><em>347+</em></div><div class="ag-ts-kpi-l">Props / Night</div></div>
          <div class="ag-ts-kpi"><div class="ag-ts-kpi-n"><em>91%</em></div><div class="ag-ts-kpi-l">Model Accuracy</div></div>
        </div>
      </div>

      <!-- ── GAME REPORT ROW ── -->
      <div class="ag-ts-row" style="--tc:#00D559;--tc2:#00FF99;">
        <div>
          <div class="ag-ts-tag"><span class="ag-ts-tag-dot"></span>&#x1F4CB;&nbsp; Game Report</div>
          <h3 class="ag-ts-copy-h">Every Matchup.<br><span class="em">Fully Decoded.</span></h3>
          <p class="ag-ts-copy-p">Pick any game on tonight&rsquo;s slate and get a full AI briefing in seconds &mdash; win probability, pace factors, total projections, defensive mismatches, and the exact props carrying the sharpest edge.</p>
          <ul class="ag-ts-list">
            <li class="ag-ts-li"><span class="ag-ts-li-num">1</span><span><b>AI Win Probability</b> &mdash; 6-model consensus for each team, updated live as lines move.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">2</span><span><b>Pace &amp; Total Projection</b> &mdash; True game total vs. the posted line. Know when the book is wrong.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">3</span><span><b>Key Player Matchup Cards</b> &mdash; Head-to-head stats, def. rating exposure, and minute projections.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">4</span><span><b>Top Props for the Game</b> &mdash; Auto-sorted by SAFE Score with one-click Neural deep-dive.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">5</span><span><b>Entry Strategy Matrix</b> &mdash; Recommended parlay combos and singles for your risk profile.</span></li>
          </ul>
          <a href="?auth=signup" class="ag-ts-btn">Access Game Reports Free <span>&#x2192;</span></a>
        </div>
        <div class="ag-ts-mk-wrap">
          <div class="ag-ts-mk-orb"></div>
          <div class="ag-ts-mk">
            <div class="ag-mk-chrome">
              <div class="ag-mk-dots"><span></span><span></span><span></span></div>
              <div class="ag-mk-url-bar">smartpickpro.ai &nbsp;&middot;&nbsp; Game Report</div>
            </div>
            <div class="ag-mk-body">
              <div class="gr2-hd">
                <div class="gr2-title">&#x1F4CB; Game Report</div>
                <div class="gr2-live">Live Analysis</div>
              </div>
              <div class="gr2-game">
                <div class="gr2-team">
                  <div class="gr2-abbr" style="color:#00D559">BOS</div>
                  <div class="gr2-rec">47&ndash;22</div>
                </div>
                <div class="gr2-mid">
                  <div class="gr2-vs">VS</div>
                  <div class="gr2-spread">BOS &minus;5.5</div>
                  <div class="gr2-ou">O/U 218.5</div>
                </div>
                <div class="gr2-team">
                  <div class="gr2-abbr" style="color:#2D9EFF">MIA</div>
                  <div class="gr2-rec">31&ndash;38</div>
                </div>
              </div>
              <div class="gr2-pills">
                <span class="gr2-pill g">4 Sharp Plays</span>
                <span class="gr2-pill b">Pace 99.4</span>
                <span class="gr2-pill">TD Garden</span>
                <span class="gr2-pill p">7:30 PM ET</span>
              </div>
              <div class="gr2-sec-lbl">AI Consensus Metrics</div>
              <div class="gr2-bars">
                <div class="gr2-brow"><div class="gr2-blbl">BOS Win Prob</div><div class="gr2-btrack"><div class="gr2-bfill" style="--w:67%;--bc1:#00D559;--bc2:#00FF99;--bglow:rgba(0,213,89,.45)"></div></div><div class="gr2-bval" style="--bc1:#00D559">67%</div></div>
                <div class="gr2-brow"><div class="gr2-blbl">Tatum PTS Edge</div><div class="gr2-btrack"><div class="gr2-bfill" style="--w:82%;--bc1:#F9C62B;--bc2:#FFE066;--bglow:rgba(249,198,43,.45)"></div></div><div class="gr2-bval" style="--bc1:#F9C62B">+4.8%</div></div>
                <div class="gr2-brow"><div class="gr2-blbl">SAFE Consensus</div><div class="gr2-btrack"><div class="gr2-bfill" style="--w:88%;--bc1:#2D9EFF;--bc2:#60b4ff;--bglow:rgba(45,158,255,.45)"></div></div><div class="gr2-bval" style="--bc1:#2D9EFF">88</div></div>
                <div class="gr2-brow"><div class="gr2-blbl">Total Proj &Delta;</div><div class="gr2-btrack"><div class="gr2-bfill" style="--w:55%;--bc1:#c084fc;--bc2:#d8b4fe;--bglow:rgba(192,132,252,.45)"></div></div><div class="gr2-bval" style="--bc1:#c084fc">+3.2</div></div>
              </div>
              <div class="gr2-alert">
                <div class="gr2-alert-ico">&#x26A1;</div>
                <div class="gr2-alert-txt"><b>Sharp Money Alert</b> &mdash; 74% of handle on BOS &minus;5.5 with line movement from &minus;4.5. Strong consensus signal.</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── PLAYER SIMULATOR ROW ── -->
      <div class="ag-ts-row rev" style="--tc:#F9C62B;--tc2:#FFE066;">
        <div class="ag-ts-mk-wrap">
          <div class="ag-ts-mk-orb"></div>
          <div class="ag-ts-mk">
            <div class="ag-mk-chrome">
              <div class="ag-mk-dots"><span></span><span></span><span></span></div>
              <div class="ag-mk-url-bar">smartpickpro.ai &nbsp;&middot;&nbsp; Player Simulator</div>
            </div>
            <div class="ag-mk-body">
              <div class="ps2-hd">
                <div class="ps2-av">JT</div>
                <div class="ps2-info">
                  <div class="ps2-name">Jayson Tatum</div>
                  <div class="ps2-meta">BOS &middot; vs MIA &middot; Home &middot; 10,000 sims</div>
                </div>
                <div class="ps2-dh">&#x1F434; Dark Horse</div>
              </div>
              <div class="ps2-grid">
                <div class="ps2-stat"><div class="ps2-sv">28.4</div><div class="ps2-sl">PTS Med</div></div>
                <div class="ps2-stat hi"><div class="ps2-sv">9.2</div><div class="ps2-sl">REB &#x2191; DH</div></div>
                <div class="ps2-stat"><div class="ps2-sv">5.1</div><div class="ps2-sl">AST Med</div></div>
                <div class="ps2-stat"><div class="ps2-sv">3.8</div><div class="ps2-sl">3PM Med</div></div>
              </div>
              <div class="ps2-vs">
                <div class="ps2-vs-lbl">Sim vs. Book Line</div>
                <div class="ps2-vs-nums">
                  <span class="ps2-vs-sim">9.2</span>
                  <span class="ps2-vs-sep">vs</span>
                  <span class="ps2-vs-book">7.5</span>
                </div>
                <div class="ps2-edge">+1.7 Edge</div>
              </div>
              <div class="ps2-dist">
                <div class="ps2-dist-hd">
                  <div class="ps2-dist-lbl">REB Distribution &mdash; 10k sims</div>
                  <div class="ps2-dist-ceil">Ceiling: 14</div>
                </div>
                <div class="ps2-dist-chart">
                  <div class="ps2-dc" style="height:15%"></div>
                  <div class="ps2-dc" style="height:28%"></div>
                  <div class="ps2-dc" style="height:46%"></div>
                  <div class="ps2-dc pk" style="height:75%"></div>
                  <div class="ps2-dc pk" style="height:100%"></div>
                  <div class="ps2-dc pk" style="height:85%"></div>
                  <div class="ps2-dc" style="height:60%"></div>
                  <div class="ps2-dc dh" style="height:44%"></div>
                  <div class="ps2-dc dh" style="height:28%"></div>
                  <div class="ps2-dc" style="height:16%"></div>
                  <div class="ps2-dc" style="height:8%"></div>
                  <div class="ps2-dc" style="height:4%"></div>
                </div>
                <div class="ps2-dist-foot"><span>3</span><span>5</span><span>7</span><span>8</span><span>9</span><span>10</span><span>11</span><span>12</span><span>13</span><span>14</span><span>&nbsp;</span><span>&nbsp;</span></div>
              </div>
            </div>
          </div>
        </div>
        <div>
          <div class="ag-ts-tag"><span class="ag-ts-tag-dot"></span>&#x1F52E;&nbsp; Player Simulator</div>
          <h3 class="ag-ts-copy-h">10,000 Sims.<br><span class="em">One True Number.</span></h3>
          <p class="ag-ts-copy-p">The Quantum Matrix Engine runs 10,000 simulated game iterations per player, per stat, per night &mdash; producing a full outcome distribution so you know the actual probability of any prop hitting, not just a guess.</p>
          <ul class="ag-ts-list">
            <li class="ag-ts-li"><span class="ag-ts-li-num">1</span><span><b>Full Stat Line Projection</b> &mdash; Points, rebounds, assists, steals, blocks, threes, and turnovers. Every category, every night.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">2</span><span><b>Dark Horse Detection &#x1F434;</b> &mdash; Auto-flags props where the sim ceiling is meaningfully above the market line.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">3</span><span><b>Sim vs. Book Line</b> &mdash; See the exact gap between your simulated median and the posted prop. Mispriced props found instantly.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">4</span><span><b>Outcome Distribution Charts</b> &mdash; See exactly where outcomes cluster. High variance = better OVER. Low variance = better UNDER.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">5</span><span><b>Context-Aware Inputs</b> &mdash; Opponent, pace, home/away, game total, and defensive matchup auto-loaded for every player.</span></li>
          </ul>
          <a href="?auth=signup" class="ag-ts-btn">Run Your First Simulation Free <span>&#x2192;</span></a>
        </div>
      </div>

      <!-- ── DARK HORSE FINDER ROW ── -->
      <div class="ag-ts-row" style="--tc:#c084fc;--tc2:#d8b4fe;">
        <div>
          <div class="ag-ts-tag"><span class="ag-ts-tag-dot"></span>&#x1F434;&nbsp; Dark Horse Finder</div>
          <h3 class="ag-ts-copy-h">Hidden Edge.<br><span class="em">Spotted First.</span></h3>
          <p class="ag-ts-copy-p">Dark Horse Finder scans every prop on the board and surfaces players whose sim ceiling outpaces the market line by the widest margin &mdash; the undervalued names books haven&rsquo;t caught up with yet.</p>
          <ul class="ag-ts-list">
            <li class="ag-ts-li"><span class="ag-ts-li-num">1</span><span><b>Ceiling vs. Line Gap</b> &mdash; Ranks all active props by the distance between the 90th-percentile sim outcome and the posted book line.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">2</span><span><b>Dark Horse Score 0&ndash;100</b> &mdash; Proprietary composite of edge size, sim confidence, matchup quality, and recent form.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">3</span><span><b>Multi-Stat Coverage</b> &mdash; Finds dark horses across PTS, REB, AST, 3PM, BLK, STL &mdash; not just the obvious scoring props.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">4</span><span><b>Live Line-Movement Watch</b> &mdash; Alerts you when a Dark Horse prop line starts moving, so you grab it before it closes.</span></li>
            <li class="ag-ts-li"><span class="ag-ts-li-num">5</span><span><b>One-Click Deep Dive</b> &mdash; Jump straight into the full Player Simulator for any flagged name with context pre-loaded.</span></li>
          </ul>
          <a href="?auth=signup" class="ag-ts-btn">Find Tonight&rsquo;s Dark Horses <span>&#x2192;</span></a>
        </div>
        <div class="ag-ts-mk-wrap">
          <div class="ag-ts-mk-orb"></div>
          <div class="ag-ts-mk">
            <div class="ag-mk-chrome">
              <div class="ag-mk-dots"><span></span><span></span><span></span></div>
              <div class="ag-mk-url-bar">smartpickpro.ai &nbsp;&middot;&nbsp; Dark Horse Finder</div>
            </div>
            <div class="ag-mk-body">
              <div class="dh2-wrap">
                <div class="dh2-scan"></div>
                <div class="dh2-hd">
                  <div class="dh2-title">&#x1F434; Dark Horse Finder</div>
                  <div class="dh2-badge">LIVE &bull; 14 flagged</div>
                </div>
                <div class="dh2-card hot">
                  <div class="dh2-rank">1</div>
                  <div class="dh2-player">
                    <div class="dh2-pname">A. Edwards</div>
                    <div class="dh2-pmeta">MIN &middot; REB &middot; vs DEN</div>
                  </div>
                  <div class="dh2-stat">
                    <div class="dh2-sval">7.8</div>
                    <div class="dh2-slbl">Sim Ceiling</div>
                  </div>
                </div>
                <div class="dh2-card hot">
                  <div class="dh2-rank">2</div>
                  <div class="dh2-player">
                    <div class="dh2-pname">B. Beal</div>
                    <div class="dh2-pmeta">PHX &middot; PTS &middot; vs LAL</div>
                  </div>
                  <div class="dh2-stat">
                    <div class="dh2-sval">31.4</div>
                    <div class="dh2-slbl">Sim Ceiling</div>
                  </div>
                </div>
                <div class="dh2-card">
                  <div class="dh2-rank">3</div>
                  <div class="dh2-player">
                    <div class="dh2-pname">D. Mitchell</div>
                    <div class="dh2-pmeta">CLE &middot; AST &middot; vs CHI</div>
                  </div>
                  <div class="dh2-stat">
                    <div class="dh2-sval">8.1</div>
                    <div class="dh2-slbl">Sim Ceiling</div>
                  </div>
                </div>
                <div class="dh2-edge-row">
                  <div class="dh2-edge-lbl">Top Edge Score</div>
                  <div class="dh2-edge-bar"><div class="dh2-edge-fill" style="width:91%"></div></div>
                  <div class="dh2-edge-val">91 / 100</div>
                </div>
                <div class="dh2-footer">
                  <div class="dh2-footer-ico">&#x26A1;</div>
                  <div class="dh2-footer-txt"><b>A. Edwards REB &mdash; ceiling +2.8 above line.</b> Matchup vs DEN &mdash; 3rd in pace, bottom-5 reb def. rating this month.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div><!-- /ag-ts-wrap -->

    <div class="ag-divider"></div>

    </div><!-- /ag-section -->
    """, unsafe_allow_html=True)

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
.cd{width:220px;flex-shrink:0;background:linear-gradient(168deg,rgba(10,16,32,0.95) 0%,rgba(8,12,24,0.98) 100%);border:1px solid rgba(0,213,89,0.06);border-radius:18px;padding:0;position:relative;overflow:hidden;transition:border-color .3s,transform .3s,box-shadow .3s}
.cd:hover{border-color:rgba(0,213,89,0.35);transform:translateY(-6px);box-shadow:0 16px 48px rgba(0,0,0,0.5),0 0 30px rgba(0,213,89,0.08)}
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
@media(max-width:520px){.cd{width:152px}.ln{font-size:1.2rem}.pl{font-size:.7rem}.sh h3{font-size:1.1rem}.sh p{font-size:.68rem}}
@media(max-width:380px){.cd{width:132px}.ln{font-size:1rem}.pl{font-size:.62rem}.ch{padding:8px 8px 0}.cb{padding:8px 8px 6px}.cf{padding:4px 8px 8px}.sh h3{font-size:.95rem}}
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

    </div><!-- /ag-section graveyard part 1 -->
    """, unsafe_allow_html=True)

    # ── AI Systems Breakdown — rendered via st.html() to avoid
    #    Streamlit markdown parser sanitizing deeply nested divs ──
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7);overflow-y:hidden}
.em{background:linear-gradient(135deg,#00D559,#2D9EFF,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
@keyframes agFadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes agPulse{0%,100%{opacity:1}50%{opacity:0.4}}
.sh{text-align:center;margin-bottom:20px}
.sh::before{content:'';display:block;width:40px;height:3px;margin:0 auto 14px;background:linear-gradient(90deg,#00D559,#2D9EFF);border-radius:4px}
.sh h3{font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:800;color:#fff;margin-bottom:6px;letter-spacing:-0.03em}
.sh p{font-size:0.78rem;color:rgba(255,255,255,0.35);line-height:1.6}
.fg{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:0 4px}
.fc{background:linear-gradient(168deg,rgba(8,14,28,0.97),rgba(5,9,16,0.99));border:1.5px solid rgba(255,255,255,0.04);border-radius:20px;padding:28px 22px 24px;position:relative;overflow:hidden;transition:border-color .4s,transform .4s,box-shadow .4s;box-shadow:0 4px 24px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.02)}
.fc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0;transition:opacity .4s}
.fc::after{content:'';position:absolute;inset:0;border-radius:20px;opacity:0;transition:opacity .4s;pointer-events:none}
.fc:hover{transform:translateY(-6px);box-shadow:0 16px 48px rgba(0,0,0,0.5),0 0 40px var(--g,rgba(0,213,89,0.08))}
.fc:hover::after{opacity:1}
.fc.g{--g:rgba(0,213,89,0.1)}.fc.g::before{background:linear-gradient(90deg,#00D559,#00B74D)}.fc.g::after{background:radial-gradient(ellipse at 50% 0%,rgba(0,213,89,0.06),transparent 65%)}.fc.g:hover{border-color:rgba(0,213,89,0.25)}
.fc.b{--g:rgba(45,158,255,0.1)}.fc.b::before{background:linear-gradient(90deg,#2D9EFF,#1a7ad9)}.fc.b::after{background:radial-gradient(ellipse at 50% 0%,rgba(45,158,255,0.06),transparent 65%)}.fc.b:hover{border-color:rgba(45,158,255,0.25)}
.fc.p{--g:rgba(192,132,252,0.1)}.fc.p::before{background:linear-gradient(90deg,#c084fc,#9333ea)}.fc.p::after{background:radial-gradient(ellipse at 50% 0%,rgba(192,132,252,0.06),transparent 65%)}.fc.p:hover{border-color:rgba(192,132,252,0.25)}
.fc.a{--g:rgba(249,198,43,0.1)}.fc.a::before{background:linear-gradient(90deg,#F9C62B,#ff8c00)}.fc.a::after{background:radial-gradient(ellipse at 50% 0%,rgba(249,198,43,0.06),transparent 65%)}.fc.a:hover{border-color:rgba(249,198,43,0.25)}
.fc.c{--g:rgba(34,211,238,0.1)}.fc.c::before{background:linear-gradient(90deg,#22d3ee,#06b6d4)}.fc.c::after{background:radial-gradient(ellipse at 50% 0%,rgba(34,211,238,0.06),transparent 65%)}.fc.c:hover{border-color:rgba(34,211,238,0.25)}
.fc.r{--g:rgba(248,113,113,0.1)}.fc.r::before{background:linear-gradient(90deg,#f87171,#dc2626)}.fc.r::after{background:radial-gradient(ellipse at 50% 0%,rgba(248,113,113,0.06),transparent 65%)}.fc.r:hover{border-color:rgba(248,113,113,0.25)}
.ft{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.bd{font-family:'JetBrains Mono',monospace;font-size:.42rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;padding:3px 10px;border-radius:100px;display:inline-flex;align-items:center;gap:5px}
.bd .dt{width:5px;height:5px;border-radius:50%;animation:agPulse 2s ease infinite}
.g .bd{color:#00D559;background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.15)}.g .bd .dt{background:#00D559}
.b .bd{color:#2D9EFF;background:rgba(45,158,255,0.08);border:1px solid rgba(45,158,255,0.15)}.b .bd .dt{background:#2D9EFF}
.p .bd{color:#c084fc;background:rgba(192,132,252,0.08);border:1px solid rgba(192,132,252,0.15)}.p .bd .dt{background:#c084fc}
.a .bd{color:#F9C62B;background:rgba(249,198,43,0.08);border:1px solid rgba(249,198,43,0.15)}.a .bd .dt{background:#F9C62B}
.c .bd{color:#22d3ee;background:rgba(34,211,238,0.08);border:1px solid rgba(34,211,238,0.15)}.c .bd .dt{background:#22d3ee}
.r .bd{color:#f87171;background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.15)}.r .bd .dt{background:#f87171}
.mt{font-family:'JetBrains Mono',monospace;font-size:1.5rem;font-weight:800;letter-spacing:-.03em;line-height:1}
.g .mt{color:#00D559;text-shadow:0 0 20px rgba(0,213,89,0.2)}.b .mt{color:#2D9EFF;text-shadow:0 0 20px rgba(45,158,255,0.2)}.p .mt{color:#c084fc;text-shadow:0 0 20px rgba(192,132,252,0.2)}.a .mt{color:#F9C62B;text-shadow:0 0 20px rgba(249,198,43,0.2)}.c .mt{color:#22d3ee;text-shadow:0 0 20px rgba(34,211,238,0.2)}.r .mt{color:#f87171;text-shadow:0 0 20px rgba(248,113,113,0.2)}
.fn{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:800;color:#fff;margin-bottom:6px;letter-spacing:-.02em}
.fd{font-size:.72rem;color:rgba(255,255,255,0.38);line-height:1.6;margin-bottom:14px}
.fs{display:flex;flex-wrap:wrap;gap:6px}
.sp{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;color:rgba(255,255,255,0.2);background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.04);padding:3px 8px;border-radius:6px;text-transform:uppercase;letter-spacing:.06em}
.fc:nth-child(1){animation:agFadeUp .5s .1s cubic-bezier(.22,1,.36,1) both}
.fc:nth-child(2){animation:agFadeUp .5s .15s cubic-bezier(.22,1,.36,1) both}
.fc:nth-child(3){animation:agFadeUp .5s .2s cubic-bezier(.22,1,.36,1) both}
.fc:nth-child(4){animation:agFadeUp .5s .25s cubic-bezier(.22,1,.36,1) both}
.fc:nth-child(5){animation:agFadeUp .5s .3s cubic-bezier(.22,1,.36,1) both}
.fc:nth-child(6){animation:agFadeUp .5s .35s cubic-bezier(.22,1,.36,1) both}
@media(max-width:768px){.fg{grid-template-columns:repeat(2,1fr);gap:12px}.fc{padding:22px 18px 20px}.mt{font-size:1.3rem}.fn{font-size:.95rem}.fd{font-size:.68rem}.sp{font-size:.4rem}}
@media(max-width:520px){.fg{grid-template-columns:repeat(2,1fr);gap:10px}.fc{padding:18px 14px 16px;border-radius:16px}.mt{font-size:1.1rem}.fn{font-size:.88rem}.fd{font-size:.64rem}.bd{font-size:.38rem;padding:2px 8px}.sp{font-size:.38rem;padding:2px 6px}.sh h3{font-size:1.2rem}.sh p{font-size:.7rem}}
@media(max-width:380px){.fg{grid-template-columns:1fr;gap:8px}.fc{padding:16px 12px 14px;border-radius:14px}.ft{margin-bottom:10px}.mt{font-size:1rem}.fn{font-size:.82rem}.fd{font-size:.62rem;margin-bottom:10px}.bd{font-size:.36rem;padding:2px 7px}.sp{font-size:.36rem;padding:2px 5px}.sh h3{font-size:1rem}.sh p{font-size:.62rem}}
</style>
<div class="sh"><h3>AI Systems <span class="em">Breakdown</span></h3><p>Six autonomous engines working in parallel to find your edge</p></div>
<div class="fg">
<div class="fc g"><div class="ft"><span class="bd"><span class="dt"></span>CORE ENGINE</span><span class="mt">6</span></div><div class="fn">Quantum Ensemble</div><div class="fd">Six neural networks &mdash; XGBoost, LightGBM, Ridge, Bayesian, LSTM, and Random Forest &mdash; fused into a single weighted signal. Each model specializes in a different statistical dimension.</div><div class="fs"><span class="sp">Multi-Model Fusion</span><span class="sp">Auto-Calibrated</span><span class="sp">300+ Features</span></div></div>
<div class="fc b"><div class="ft"><span class="bd"><span class="dt"></span>INTELLIGENCE</span><span class="mt">0&ndash;100</span></div><div class="fn">SAFE Score&trade;</div><div class="fd">Multi-factor confidence index combining model agreement, historical accuracy, matchup context, line movement, and injury impact into a single actionable score.</div><div class="fs"><span class="sp">5-Factor Composite</span><span class="sp">Calibrated Daily</span><span class="sp">Threshold Alerts</span></div></div>
<div class="fc p"><div class="ft"><span class="bd"><span class="dt"></span>LIVE</span><span class="mt">RT</span></div><div class="fn">Sweat Tracker</div><div class="fd">Real-time in-game monitoring with pace projections, live stat accumulation, and probability updates every 30 seconds. Watch your bets resolve in real time.</div><div class="fs"><span class="sp">30s Refresh</span><span class="sp">Pace Projection</span><span class="sp">Live Probability</span></div></div>
<div class="fc a"><div class="ft"><span class="bd"><span class="dt"></span>ALPHA</span><span class="mt">300+</span></div><div class="fn">Edge Detection</div><div class="fd">Automated market scanner that identifies mispriced lines across sportsbooks. Compares AI projections to live odds and surfaces the highest expected-value props.</div><div class="fs"><span class="sp">Multi-Book Scan</span><span class="sp">EV Calculator</span><span class="sp">Props / Night</span></div></div>
<div class="fc c"><div class="ft"><span class="bd"><span class="dt"></span>ANALYTICS</span><span class="mt">450+</span></div><div class="fn">Defensive DNA</div><div class="fd">Matchup-aware profiling that decodes how each defense surrenders stats. Adjusts projections based on positional tendencies, pace, and scheme vulnerabilities.</div><div class="fs"><span class="sp">Positional Splits</span><span class="sp">Pace-Adjusted</span><span class="sp">Player Profiles</span></div></div>
<div class="fc r"><div class="ft"><span class="bd"><span class="dt"></span>VERIFIED</span><span class="mt">92%</span></div><div class="fn">CLV Capture</div><div class="fd">Closing line value engine that measures whether our picks beat the final market odds. 92% CLV capture rate proves sustained, quantifiable edge &mdash; not luck.</div><div class="fs"><span class="sp">Line Tracking</span><span class="sp">Market Validation</span><span class="sp">Edge Verified</span></div></div>
</div>
""")

    # ── Below-fold: stats + testimonials (continued) ─────────
    st.markdown("""
    <div class="ag-section">

    <!-- ── METRIC COUNTERS ── -->
    <div class="ag-stats-strip ag-visible" id="statsStrip">
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

    <!-- ── RECENT WINS TICKER ── -->
    <div style="margin:28px 0 8px;overflow:hidden;position:relative;border-radius:12px;
         background:rgba(0,213,89,0.03);border:1px solid rgba(0,213,89,0.06);padding:10px 0">
      <div style="display:flex;animation:tickerScroll 35s linear infinite;width:max-content">
        <div style="display:flex;gap:24px;padding:0 12px;white-space:nowrap;
             font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:rgba(255,255,255,0.4)">
          <span>&#x2705; Jayson Tatum <strong style="color:#00D559">O 27.5 pts</strong> &mdash; SAFE 84 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Luka Doncic <strong style="color:#00D559">O 8.5 ast</strong> &mdash; SAFE 79 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Anthony Edwards <strong style="color:#00D559">O 24.5 pts</strong> &mdash; SAFE 82 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Nikola Jokic <strong style="color:#00D559">O 11.5 reb</strong> &mdash; SAFE 88 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Tyrese Haliburton <strong style="color:#00D559">O 9.5 ast</strong> &mdash; SAFE 76 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Shai Gilgeous-Alexander <strong style="color:#00D559">O 30.5 pts</strong> &mdash; SAFE 91 &mdash; Hit &#x2714;</span>
          <span>&#x2705; De'Aaron Fox <strong style="color:#00D559">O 6.5 ast</strong> &mdash; SAFE 73 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Bam Adebayo <strong style="color:#00D559">O 9.5 reb</strong> &mdash; SAFE 77 &mdash; Hit &#x2714;</span>
        </div>
        <div style="display:flex;gap:24px;padding:0 12px;white-space:nowrap;
             font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:rgba(255,255,255,0.4)">
          <span>&#x2705; Jayson Tatum <strong style="color:#00D559">O 27.5 pts</strong> &mdash; SAFE 84 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Luka Doncic <strong style="color:#00D559">O 8.5 ast</strong> &mdash; SAFE 79 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Anthony Edwards <strong style="color:#00D559">O 24.5 pts</strong> &mdash; SAFE 82 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Nikola Jokic <strong style="color:#00D559">O 11.5 reb</strong> &mdash; SAFE 88 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Tyrese Haliburton <strong style="color:#00D559">O 9.5 ast</strong> &mdash; SAFE 76 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Shai Gilgeous-Alexander <strong style="color:#00D559">O 30.5 pts</strong> &mdash; SAFE 91 &mdash; Hit &#x2714;</span>
          <span>&#x2705; De'Aaron Fox <strong style="color:#00D559">O 6.5 ast</strong> &mdash; SAFE 73 &mdash; Hit &#x2714;</span>
          <span>&#x2705; Bam Adebayo <strong style="color:#00D559">O 9.5 reb</strong> &mdash; SAFE 77 &mdash; Hit &#x2714;</span>
        </div>
      </div>
      <style>
      @keyframes tickerScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
      </style>
    </div>

    <!-- ── TESTIMONIALS ── -->
    <div class="ag-reviews">
      <div class="ag-section-head">
        <h3>What Sharps Are <span class="em">Saying</span></h3>
      </div>

      <div class="ag-review">
        <div class="ag-review-body">
          <span class="ag-review-chip">&#x1F4B0; Bankroll Growth</span>
          <div class="ag-review-text">I was paying <strong>$99/mo</strong> for OddsJam and still losing. Switched to Smart Pick Pro &mdash; free, better AI, and my bankroll is <strong>up 22%</strong> in two months.</div>
          <div class="ag-review-stat"><span class="stat-num">+22%</span> bankroll in 60 days</div>
        </div>
        <div class="ag-review-footer">
          <div class="ag-review-avatar">&#x1F4B0;</div>
          <div class="ag-review-info">
            <div class="ag-review-author">@sharpbettor_mike</div>
            <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          </div>
          <span class="ag-review-verified">&#x2713; Verified</span>
        </div>
      </div>

      <div class="ag-review">
        <div class="ag-review-body">
          <span class="ag-review-chip">&#x1F3AF; SAFE Score</span>
          <div class="ag-review-text">SAFE Score is something <strong>no other platform</strong> has. I only play 80+ rated props now and my win rate went from <strong>48% to 63%</strong>.</div>
          <div class="ag-review-stat"><span class="stat-num">63%</span> win rate on 80+ picks</div>
        </div>
        <div class="ag-review-footer">
          <div class="ag-review-avatar">&#x1F4CA;</div>
          <div class="ag-review-info">
            <div class="ag-review-author">@datadrivendenver</div>
            <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          </div>
          <span class="ag-review-verified">&#x2713; Verified</span>
        </div>
      </div>

      <div class="ag-review">
        <div class="ag-review-body">
          <span class="ag-review-chip">&#x1F4E1; Live Sweat</span>
          <div class="ag-review-text">Live Sweat Mode is <strong>addictive</strong>. Watching props track in real-time with AI confidence updates &mdash; I cancelled <strong>Action Network</strong> the same day.</div>
          <div class="ag-review-stat"><span class="stat-num">Real-Time</span> prop tracking</div>
        </div>
        <div class="ag-review-footer">
          <div class="ag-review-avatar">&#x1F3C0;</div>
          <div class="ag-review-info">
            <div class="ag-review-author">@nightowl_picks</div>
            <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
          </div>
          <span class="ag-review-verified">&#x2713; Verified</span>
        </div>
      </div>
    </div>

    </div><!-- /ag-section graveyard -->
    """, unsafe_allow_html=True)

    # ── Built by Bettors / Founder Story ──
    st.markdown("""
    <div class="ag-reveal" style="text-align:center;padding:40px 24px 32px;max-width:640px;margin:0 auto">
      <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:16px">
        <div style="width:48px;height:48px;border-radius:50%;
             background:linear-gradient(135deg,rgba(0,213,89,0.2),rgba(45,158,255,0.15));
             border:2px solid rgba(0,213,89,0.2);display:flex;align-items:center;justify-content:center;
             font-size:1.4rem">&#x1F9E0;</div>
        <div style="text-align:left">
          <div style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.85rem;
               color:rgba(255,255,255,0.85)">Built by Bettors, for Bettors</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.62rem;color:rgba(255,255,255,0.3)">
            The Smart Pick Pro team</div>
        </div>
      </div>
      <p style="font-family:'Inter',sans-serif;font-size:0.78rem;color:rgba(255,255,255,0.45);
         line-height:1.7;margin:0 auto;max-width:520px">
        We got tired of paying $100/month for odds tools that couldn&rsquo;t even tell us <em>which</em>
        props to play. So we built an AI that fuses six models, grades every pick, and tracks
        every result &mdash; then gave the core away for free. If we can&rsquo;t beat the books with
        data, we don&rsquo;t deserve your money.</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Mobile responsiveness callout ──
    st.markdown("""
    <div style="text-align:center;padding:16px 0 40px">
      <div style="display:inline-flex;align-items:center;gap:20px;padding:20px 32px;
           background:rgba(255,255,255,0.015);border:1px solid rgba(255,255,255,0.05);
           border-radius:16px;max-width:600px;margin:0 auto">
        <div style="font-size:2.5rem">&#x1F4F1;</div>
        <div style="text-align:left">
          <div style="font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:0.85rem;
               color:rgba(255,255,255,0.85);margin-bottom:4px">
            Works on Every Device</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.68rem;color:rgba(255,255,255,0.35);
               line-height:1.5">
            Desktop, tablet, or phone &mdash; Smart Pick Pro adapts to your screen.
            Check picks on your couch, sweat games from the bar, review results anywhere.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── What's New / Recently Shipped — rendered via st.html() to bypass
    #    Streamlit's markdown parser which strips nested div structures ──
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;overflow-y:hidden}
</style>
<div style="text-align:center;padding:40px 20px 32px;max-width:600px;margin:0 auto">
  <div style="font-family:'Space Grotesk',sans-serif;font-size:0.65rem;font-weight:700;
       color:rgba(45,158,255,0.6);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px">
    &#x1F680; Recently Shipped</div>
  <div style="font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:800;
       color:rgba(255,255,255,0.9);margin-bottom:20px">
    What&rsquo;s <span style="background:linear-gradient(135deg,#2D9EFF,#c084fc);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">New</span></div>

  <div style="text-align:left;display:flex;flex-direction:column;gap:12px">
    <div style="display:flex;align-items:flex-start;gap:12px;padding:12px 16px;
         background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px">
      <div style="min-width:28px;height:28px;border-radius:8px;
           background:rgba(0,213,89,0.1);display:flex;align-items:center;justify-content:center;
           font-size:0.8rem">&#x2705;</div>
      <div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.72rem;
             color:rgba(255,255,255,0.8)">Parlay Optimizer &amp; Correlation Engine</div>
        <div style="font-family:'Inter',sans-serif;font-size:0.6rem;color:rgba(255,255,255,0.3);margin-top:2px">
          Multi-leg analysis with true correlation scoring between props</div>
      </div>
    </div>

    <div style="display:flex;align-items:flex-start;gap:12px;padding:12px 16px;
         background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px">
      <div style="min-width:28px;height:28px;border-radius:8px;
           background:rgba(45,158,255,0.1);display:flex;align-items:center;justify-content:center;
           font-size:0.8rem">&#x2705;</div>
      <div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.72rem;
             color:rgba(255,255,255,0.8)">Live Sweat Mode v2</div>
        <div style="font-family:'Inter',sans-serif;font-size:0.6rem;color:rgba(255,255,255,0.3);margin-top:2px">
          Real-time pace projection, live probability updates, and in-game alerts</div>
      </div>
    </div>

    <div style="display:flex;align-items:flex-start;gap:12px;padding:12px 16px;
         background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px">
      <div style="min-width:28px;height:28px;border-radius:8px;
           background:rgba(192,132,252,0.1);display:flex;align-items:center;justify-content:center;
           font-size:0.8rem">&#x2705;</div>
      <div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.72rem;
             color:rgba(255,255,255,0.8)">Defensive DNA Profiles</div>
        <div style="font-family:'Inter',sans-serif;font-size:0.6rem;color:rgba(255,255,255,0.3);margin-top:2px">
          Positional defense matchup data with pace-adjusted projections</div>
      </div>
    </div>

    <div style="display:flex;align-items:flex-start;gap:12px;padding:12px 16px;
         background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px">
      <div style="min-width:28px;height:28px;border-radius:8px;
           background:rgba(249,198,43,0.1);display:flex;align-items:center;justify-content:center;
           font-size:0.8rem">&#x1F527;</div>
      <div>
        <div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.72rem;
             color:rgba(255,255,255,0.8)">Coming Soon: MLB &amp; NFL Coverage</div>
        <div style="font-family:'Inter',sans-serif;font-size:0.6rem;color:rgba(255,255,255,0.3);margin-top:2px">
          Same 6-model ensemble pipeline expanding to new leagues</div>
      </div>
    </div>
  </div>
</div>
""")

    # ── Section anchor: Bet Tracker ──
    st.markdown('<div id="sec-tracker" data-section-id="tracker" style="height:0;overflow:hidden;"></div>', unsafe_allow_html=True)

    # ── Below-fold: Bet Tracker transparency ─────────────────
    # Uses st.html() to bypass Streamlit's markdown parser which
    # cannot handle deeply nested HTML structures.
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7)}
@keyframes btPulse{0%,100%{box-shadow:0 0 4px rgba(249,198,43,0.05)}50%{box-shadow:0 0 20px rgba(249,198,43,0.25)}}
@keyframes btGlow{0%,100%{opacity:0.5}50%{opacity:1}}
@keyframes btShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
@keyframes btFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes btFadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes btBarGrow{from{width:0}to{width:var(--bar-w)}}
@keyframes btLineGrow{from{stroke-dashoffset:800}to{stroke-dashoffset:0}}

/* ── Section heading ── */
.sh{text-align:center;margin-bottom:36px;position:relative;padding-top:8px}
.sh::before{content:'';display:block;width:60px;height:4px;margin:0 auto 20px;background:linear-gradient(90deg,#00D559,#2D9EFF,#c084fc);border-radius:4px;background-size:200% 100%;animation:btShimmer 4s ease infinite}
.sh h3{font-family:'Space Grotesk',sans-serif;font-size:2.6rem;font-weight:800;color:#fff;margin-bottom:12px;letter-spacing:-0.04em;line-height:1.15}
.sh h3 .em{background:linear-gradient(135deg,#00D559 0%,#2D9EFF 50%,#c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.sh p{font-size:0.92rem;color:rgba(255,255,255,0.45);line-height:1.7;max-width:600px;margin:0 auto}

/* ── Mock data banner ── */
.mock-banner{background:linear-gradient(135deg,rgba(249,198,43,0.08) 0%,rgba(249,198,43,0.02) 100%);border:1.5px solid rgba(249,198,43,0.25);border-radius:18px;padding:20px 28px;text-align:center;margin-bottom:28px;position:relative;overflow:hidden;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.mock-banner::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#F9C62B,transparent);background-size:200% 100%;animation:btShimmer 3s ease infinite}
.mock-banner-pill{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:800;color:#F9C62B;background:rgba(249,198,43,0.1);border:1px solid rgba(249,198,43,0.2);padding:5px 16px;border-radius:100px;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px}
.mock-banner-text{font-size:.8rem;color:rgba(255,255,255,0.4);line-height:1.7}
.mock-banner-text strong{color:rgba(255,255,255,0.8)}

/* ════════════════════════════════════════════════════════════
   BET TRACKER — ELITE UI  (Barlow Condensed · JetBrains Mono)
   ════════════════════════════════════════════════════════════ */

/* ── App frame ── */
.bt-app{background:linear-gradient(168deg,rgba(4,7,16,0.99) 0%,rgba(6,10,20,0.99) 60%,rgba(5,8,18,0.99) 100%);border:1px solid rgba(255,255,255,0.07);border-radius:24px;overflow:hidden;box-shadow:0 48px 120px rgba(0,0,0,0.85),0 0 0 1px rgba(0,213,89,0.05) inset,0 0 120px rgba(0,213,89,0.04);position:relative}
.bt-app::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#00D559 0%,#2D9EFF 35%,#c084fc 65%,#F9C62B 100%);background-size:300% 100%;animation:btShimmer 5s ease infinite;z-index:10}
.bt-app::after{content:'';position:absolute;bottom:-120px;left:-80px;width:500px;height:500px;border-radius:50%;background:radial-gradient(circle,rgba(0,213,89,0.05) 0%,transparent 65%);filter:blur(60px);pointer-events:none;z-index:0}

/* ── Title bar ── */
.bt-title-bar{display:flex;align-items:center;gap:16px;padding:20px 28px;background:rgba(255,255,255,0.025);border-bottom:1px solid rgba(255,255,255,0.07);position:relative;z-index:2;backdrop-filter:blur(8px)}
.bt-title-ico{font-size:1.5rem;animation:btFloat 3s ease-in-out infinite;filter:drop-shadow(0 0 8px rgba(0,213,89,0.5))}
.bt-title-txt{font-family:'Barlow Condensed',sans-serif;font-size:1.25rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.02em;background:linear-gradient(135deg,#fff 0%,rgba(255,255,255,0.6) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.bt-title-sub{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:700;color:rgba(255,255,255,0.22);margin-left:auto;display:flex;align-items:center;gap:8px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);padding:5px 14px;border-radius:100px;letter-spacing:.06em;text-transform:uppercase}
.bt-title-sub .live{color:#00D559;animation:btGlow 2s ease-in-out infinite;font-size:.75rem}

/* ── Tab bar ── */
.bt-tabs{display:flex;gap:0;border-bottom:1px solid rgba(255,255,255,0.07);overflow-x:auto;scrollbar-width:none;background:rgba(255,255,255,0.015);position:relative;z-index:2}
.bt-tabs::-webkit-scrollbar{display:none}
.bt-tab{padding:14px 18px;font-family:'Barlow Condensed',sans-serif;font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:rgba(255,255,255,0.22);white-space:nowrap;cursor:default;border-bottom:2px solid transparent;transition:all .22s;position:relative;top:1px}
.bt-tab.active{color:#00D559;border-bottom:2px solid #00D559;background:rgba(0,213,89,0.05);text-shadow:0 0 20px rgba(0,213,89,0.3)}
.bt-tab:hover{color:rgba(255,255,255,0.5);background:rgba(255,255,255,0.025)}

/* ── Filter bar ── */
.bt-filters{display:flex;gap:8px;padding:14px 24px;background:rgba(255,255,255,0.012);border-bottom:1px solid rgba(255,255,255,0.05);flex-wrap:wrap;align-items:center;position:relative;z-index:2}
.bt-filter{display:flex;align-items:center;gap:7px;font-family:'JetBrains Mono',monospace;font-size:.52rem;color:rgba(255,255,255,0.32);background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:7px 16px;transition:all .2s}
.bt-filter:hover{border-color:rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:rgba(255,255,255,0.55)}
.bt-filter-label{font-weight:800;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:.06em}
.bt-filter-val{color:rgba(255,255,255,0.22)}
.bt-resolve-btn{margin-left:auto;font-family:'Barlow Condensed',sans-serif;font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:#00D559;background:linear-gradient(135deg,rgba(0,213,89,0.12),rgba(0,213,89,0.05));border:1px solid rgba(0,213,89,0.28);border-radius:12px;padding:7px 18px;cursor:default;transition:all .22s}
.bt-resolve-btn:hover{background:rgba(0,213,89,0.18);box-shadow:0 0 24px rgba(0,213,89,0.15);transform:translateY(-1px)}

/* ── Summary cards — 8-col ── */
.bt-summary{display:grid;grid-template-columns:repeat(8,1fr);gap:0;border-bottom:1px solid rgba(255,255,255,0.06);background:rgba(255,255,255,0.012);position:relative;z-index:1}
.bt-sum{text-align:center;padding:26px 8px 22px;border-right:1px solid rgba(255,255,255,0.04);position:relative;transition:background .22s;overflow:hidden}
.bt-sum:last-child{border-right:none}
.bt-sum::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.06),transparent);opacity:0;transition:opacity .22s}
.bt-sum:hover{background:rgba(255,255,255,0.025)}
.bt-sum:hover::before{opacity:1}
.bt-sum-val{font-family:'Barlow Condensed',sans-serif;font-size:1.55rem;font-weight:900;font-style:italic;line-height:1;letter-spacing:-.01em}
.bt-sum-val.gr{color:#00D559;text-shadow:0 0 28px rgba(0,213,89,0.35)}.bt-sum-val.rd{color:#f24336;text-shadow:0 0 28px rgba(242,67,54,0.35)}.bt-sum-val.bl{color:#2D9EFF;text-shadow:0 0 28px rgba(45,158,255,0.35)}.bt-sum-val.gd{color:#F9C62B;text-shadow:0 0 28px rgba(249,198,43,0.35)}.bt-sum-val.wh{color:rgba(255,255,255,0.85)}.bt-sum-val.pk{color:#c084fc;text-shadow:0 0 28px rgba(192,132,252,0.35);font-size:1.1rem}
.bt-sum-lbl{font-family:'JetBrains Mono',monospace;font-size:.44rem;font-weight:700;text-transform:uppercase;letter-spacing:.10em;color:rgba(255,255,255,0.18);margin-top:7px}

/* ── Filter chips row ── */
.bt-chips{display:flex;gap:8px;padding:14px 24px;flex-wrap:wrap;border-bottom:1px solid rgba(255,255,255,0.04)}
.bt-chip{font-family:'Barlow Condensed',sans-serif;font-size:.62rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;padding:5px 16px;border-radius:100px;border:1px solid;cursor:default;transition:all .22s}
.bt-chip:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,0,0,0.25)}
.bt-chip.all{color:rgba(255,255,255,0.45);border-color:rgba(255,255,255,0.12);background:rgba(255,255,255,0.04)}
.bt-chip.wins{color:#00D559;border-color:rgba(0,213,89,0.28);background:rgba(0,213,89,0.07)}
.bt-chip.losses{color:#f24336;border-color:rgba(242,67,54,0.28);background:rgba(242,67,54,0.07)}
.bt-chip.pending{color:#F9C62B;border-color:rgba(249,198,43,0.28);background:rgba(249,198,43,0.07)}
.bt-chip.plat{color:#c084fc;border-color:rgba(192,132,252,0.28);background:rgba(192,132,252,0.07)}
.bt-chip.gold2{color:#F9C62B;border-color:rgba(249,198,43,0.28);background:rgba(249,198,43,0.07)}

/* ── Tier breakdown ── */
.bt-tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-bottom:1px solid rgba(255,255,255,0.05)}
.bt-tier{text-align:center;padding:22px 10px;border-right:1px solid rgba(255,255,255,0.04);transition:background .22s;position:relative;overflow:hidden}
.bt-tier:last-child{border-right:none}
.bt-tier::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;opacity:0;transition:opacity .22s}
.bt-tier:nth-child(1)::after{background:#c084fc}.bt-tier:nth-child(2)::after{background:#F9C62B}.bt-tier:nth-child(3)::after{background:#A0AABE}.bt-tier:nth-child(4)::after{background:#CD7F32}
.bt-tier:hover{background:rgba(255,255,255,0.02)}
.bt-tier:hover::after{opacity:1}
.bt-tier-name{font-family:'Barlow Condensed',sans-serif;font-size:.66rem;font-weight:900;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}
.bt-tier-name.pt{color:#c084fc}.bt-tier-name.gld{color:#F9C62B}.bt-tier-name.slv{color:#A0AABE}.bt-tier-name.brz{color:#CD7F32}
.bt-tier-wr{font-family:'Barlow Condensed',sans-serif;font-size:1.6rem;font-weight:900;font-style:italic;line-height:1}
.bt-tier-wr.pt{color:#c084fc;text-shadow:0 0 24px rgba(192,132,252,0.35)}.bt-tier-wr.gld{color:#F9C62B;text-shadow:0 0 24px rgba(249,198,43,0.35)}.bt-tier-wr.slv{color:#A0AABE}.bt-tier-wr.brz{color:#CD7F32}
.bt-tier-detail{font-family:'JetBrains Mono',monospace;font-size:.46rem;color:rgba(255,255,255,0.22);margin-top:5px;font-weight:700}
.bt-tier-bar{width:75%;height:4px;margin:10px auto 0;background:rgba(255,255,255,0.05);border-radius:2px;overflow:hidden}
.bt-tier-bar-fill{height:100%;border-radius:2px;animation:btBarGrow .9s cubic-bezier(.34,1.56,.64,1) forwards}
.bt-tier-bar-fill.pt{background:linear-gradient(90deg,#c084fc,#e0b0ff);box-shadow:0 0 8px rgba(192,132,252,0.4)}.bt-tier-bar-fill.gld{background:linear-gradient(90deg,#F9C62B,#ffe066);box-shadow:0 0 8px rgba(249,198,43,0.4)}.bt-tier-bar-fill.slv{background:linear-gradient(90deg,#A0AABE,#c8cdd5)}.bt-tier-bar-fill.brz{background:linear-gradient(90deg,#CD7F32,#e8a860)}

/* ── Model health section ── */
.bt-health{padding:24px 26px;border-bottom:1px solid rgba(255,255,255,0.05);background:linear-gradient(168deg,rgba(45,158,255,0.03),rgba(45,158,255,0.006))}
.bt-health-hdr{font-family:'Barlow Condensed',sans-serif;font-size:1.0rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.04em;color:rgba(255,255,255,0.75);margin-bottom:18px;display:flex;align-items:center;gap:12px}
.bt-health-hdr .badge{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:#00D559;background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.2);padding:4px 12px;border-radius:100px;text-transform:uppercase;letter-spacing:.08em;font-style:normal}
.bt-stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}
.bt-stat-item{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:18px 14px;text-align:center;transition:all .22s;position:relative;overflow:hidden}
.bt-stat-item::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(45,158,255,0.3),transparent);opacity:0;transition:opacity .22s}
.bt-stat-item:hover{border-color:rgba(255,255,255,0.12);background:rgba(255,255,255,0.04);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.2)}
.bt-stat-item:hover::before{opacity:1}
.bt-stat-item-name{font-family:'Barlow Condensed',sans-serif;font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,0.35);margin-bottom:8px}
.bt-stat-item-wr{font-family:'Barlow Condensed',sans-serif;font-size:1.5rem;font-weight:900;font-style:italic;line-height:1}
.bt-stat-item-wr.gr{color:#00D559;text-shadow:0 0 20px rgba(0,213,89,0.35)}.bt-stat-item-wr.gd{color:#F9C62B;text-shadow:0 0 20px rgba(249,198,43,0.35)}.bt-stat-item-wr.bl{color:#2D9EFF;text-shadow:0 0 20px rgba(45,158,255,0.35)}
.bt-stat-item-detail{font-family:'JetBrains Mono',monospace;font-size:.44rem;color:rgba(255,255,255,0.22);margin-top:5px;font-weight:700}
.bt-plat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.bt-plat-item{background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:18px 14px;text-align:center;transition:all .22s}
.bt-plat-item:hover{border-color:rgba(255,255,255,0.12);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.2)}
.bt-plat-item-name{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:700;padding:4px 12px;border-radius:10px;display:inline-block;margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em}
.bt-plat-item-name.pp{color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.18)}
.bt-plat-item-name.ud{color:#c084fc;background:rgba(192,132,252,0.1);border:1px solid rgba(192,132,252,0.18)}
.bt-plat-item-name.dk{color:#2D9EFF;background:rgba(45,158,255,0.1);border:1px solid rgba(45,158,255,0.18)}
.bt-plat-item-wr{font-family:'Barlow Condensed',sans-serif;font-size:1.5rem;font-weight:900;font-style:italic;color:#00D559;text-shadow:0 0 20px rgba(0,213,89,0.3);line-height:1}
.bt-plat-item-detail{font-family:'JetBrains Mono',monospace;font-size:.44rem;color:rgba(255,255,255,0.22);margin-top:5px;font-weight:700}

/* ── Calendar heatmap ── */
.bt-cal{padding:22px 26px;border-bottom:1px solid rgba(255,255,255,0.05)}
.bt-cal-hdr{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.04em;color:rgba(255,255,255,0.6);margin-bottom:14px}
.bt-cal-grid{display:grid;grid-template-columns:repeat(14,1fr);gap:6px}
.bt-cal-day{width:100%;aspect-ratio:1;border-radius:6px;position:relative;transition:all .18s;cursor:default}
.bt-cal-day:hover{transform:scale(1.2);z-index:2;box-shadow:0 4px 16px rgba(0,0,0,0.35)}
.bt-cal-day.green1{background:rgba(0,213,89,0.14)}.bt-cal-day.green2{background:rgba(0,213,89,0.32)}.bt-cal-day.green3{background:rgba(0,213,89,0.55);box-shadow:0 0 10px rgba(0,213,89,0.18)}.bt-cal-day.green4{background:rgba(0,213,89,0.78);box-shadow:0 0 16px rgba(0,213,89,0.25)}
.bt-cal-day.red1{background:rgba(242,67,54,0.22)}.bt-cal-day.red2{background:rgba(242,67,54,0.45)}
.bt-cal-day.empty{background:rgba(255,255,255,0.025)}
.bt-cal-day.today{outline:2px solid #F9C62B;outline-offset:2px;box-shadow:0 0 16px rgba(249,198,43,0.25)}
.bt-cal-legend{display:flex;gap:10px;align-items:center;margin-top:12px;justify-content:center}
.bt-cal-legend-item{font-family:'JetBrains Mono',monospace;font-size:.42rem;font-weight:700;color:rgba(255,255,255,0.22);display:flex;align-items:center;gap:5px;letter-spacing:.04em}
.bt-cal-legend-swatch{width:13px;height:13px;border-radius:4px}

/* ── SVG P&L chart ── */
.bt-pnl{padding:22px 26px;border-bottom:1px solid rgba(255,255,255,0.05);background:rgba(0,213,89,0.01)}
.bt-pnl-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.bt-pnl-lbl{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.04em;color:rgba(255,255,255,0.5)}
.bt-pnl-val{font-family:'JetBrains Mono',monospace;font-size:.84rem;font-weight:800;color:#00D559;text-shadow:0 0 20px rgba(0,213,89,0.3);background:rgba(0,213,89,0.07);border:1px solid rgba(0,213,89,0.15);padding:5px 16px;border-radius:100px}
.bt-pnl svg{width:100%;height:70px;display:block}

/* ── Date group header ── */
.bt-date-hdr{display:flex;align-items:center;gap:12px;padding:14px 26px;background:linear-gradient(90deg,rgba(255,255,255,0.02),rgba(255,255,255,0.006));border-bottom:1px solid rgba(255,255,255,0.05);border-top:1px solid rgba(255,255,255,0.03)}
.bt-date-label{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.04em;color:rgba(255,255,255,0.6)}
.bt-date-stats{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:700;color:rgba(255,255,255,0.2);margin-left:auto;letter-spacing:.05em}
.bt-date-stats .w{color:#00D559;font-weight:800}.bt-date-stats .l{color:#f24336;font-weight:800}.bt-date-stats .p{color:#F9C62B;font-weight:800}

/* ── Bet cards ── */
.bt-cards{padding:10px 18px 14px}
.bt-card{display:grid;grid-template-columns:auto 1fr auto auto auto auto;align-items:center;gap:14px;padding:15px 20px;margin:7px 0;border-radius:16px;border-left:3px solid;background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-left-width:3px;transition:all .22s;position:relative;overflow:hidden}
.bt-card::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.07),transparent);pointer-events:none}
.bt-card:hover{background:rgba(255,255,255,0.04);transform:translateX(5px);box-shadow:0 6px 28px rgba(0,0,0,0.2)}
.bt-card.win{border-color:#00D559;box-shadow:0 0 22px rgba(0,213,89,0.08);background:rgba(0,213,89,0.02)}
.bt-card.win::after{content:'';position:absolute;left:0;top:0;bottom:0;width:50px;background:linear-gradient(90deg,rgba(0,213,89,0.06),transparent);border-radius:16px 0 0 16px;pointer-events:none}
.bt-card.loss{border-color:#f24336;box-shadow:0 0 22px rgba(242,67,54,0.07);background:rgba(242,67,54,0.02)}
.bt-card.loss::after{content:'';position:absolute;left:0;top:0;bottom:0;width:50px;background:linear-gradient(90deg,rgba(242,67,54,0.06),transparent);border-radius:16px 0 0 16px;pointer-events:none}
.bt-card.pend{border-color:#F9C62B;animation:btPulse 2.8s ease-in-out infinite;background:rgba(249,198,43,0.02)}

.bt-card-tier{font-size:.9rem;width:30px;text-align:center;position:relative;z-index:1}
.bt-card-info{display:flex;flex-direction:column;gap:5px;min-width:0;position:relative;z-index:1}
.bt-card-player{font-family:'Barlow Condensed',sans-serif;font-size:.92rem;font-weight:800;color:rgba(255,255,255,0.82);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:.01em}
.bt-card-meta{display:flex;gap:8px;align-items:center}
.bt-card-platform{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;padding:3px 10px;border-radius:8px;text-transform:uppercase;letter-spacing:.06em}
.bt-card-platform.pp{color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.15)}
.bt-card-platform.ud{color:#c084fc;background:rgba(192,132,252,0.1);border:1px solid rgba(192,132,252,0.15)}
.bt-card-platform.dk{color:#2D9EFF;background:rgba(45,158,255,0.1);border:1px solid rgba(45,158,255,0.15)}
.bt-card-safe{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:rgba(255,255,255,0.18)}
.bt-card-safe .sc{color:#00D559;font-weight:800;text-shadow:0 0 10px rgba(0,213,89,0.4)}

.bt-card-line{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;text-align:center;min-width:60px}
.bt-card-line.ov{color:#00D559;text-shadow:0 0 12px rgba(0,213,89,0.4)}.bt-card-line.un{color:#2D9EFF;text-shadow:0 0 12px rgba(45,158,255,0.4)}

.bt-card-actual{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;text-align:center;min-width:38px}
.bt-card-actual.hit{color:#00D559;text-shadow:0 0 12px rgba(0,213,89,0.4)}.bt-card-actual.miss{color:#f24336;opacity:.8}.bt-card-actual.tbd{color:rgba(255,255,255,0.14)}

.bt-card-clv{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:700;text-align:center;min-width:46px}
.bt-card-clv.pos{color:#F9C62B}.bt-card-clv.neg{color:rgba(255,255,255,0.12)}

.bt-card-result{font-size:.95rem;text-align:center;min-width:26px;font-weight:700}
.bt-card-result.w{color:#00D559;text-shadow:0 0 14px rgba(0,213,89,0.5)}.bt-card-result.l{color:rgba(242,67,54,0.65)}.bt-card-result.pending{color:#F9C62B;animation:btPulse 2s ease-in-out infinite}

/* ── Bankroll section ── */
.bt-bankroll{padding:24px 26px;border-top:1px solid rgba(255,255,255,0.05);background:linear-gradient(168deg,rgba(0,213,89,0.03),rgba(0,213,89,0.007))}
.bt-bankroll-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.bt-bankroll-lbl{font-family:'Barlow Condensed',sans-serif;font-size:.9rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.04em;color:rgba(255,255,255,0.35)}
.bt-bankroll-val{font-family:'JetBrains Mono',monospace;font-size:.92rem;font-weight:800;color:#00D559;text-shadow:0 0 20px rgba(0,213,89,0.25)}
.bt-bankroll-sub{font-family:'JetBrains Mono',monospace;font-size:.54rem;color:#00D559;opacity:.6;margin-left:10px;background:rgba(0,213,89,0.1);padding:3px 10px;border-radius:100px;border:1px solid rgba(0,213,89,0.15)}
.bt-growth{height:56px;display:flex;align-items:flex-end;gap:3px;width:100%}
.bt-growth-bar{flex:1;border-radius:5px 5px 0 0;background:linear-gradient(180deg,rgba(0,213,89,0.7),rgba(0,213,89,0.18));transition:all .3s;cursor:default}
.bt-growth-bar:hover{opacity:.85;transform:scaleY(1.05);transform-origin:bottom;box-shadow:0 0 8px rgba(0,213,89,0.3)}
.bt-growth-bar.red{background:linear-gradient(180deg,rgba(242,67,54,0.6),rgba(242,67,54,0.14))}
.bt-growth-bar.red:hover{box-shadow:0 0 8px rgba(242,67,54,0.3)}

/* ── Pagination ── */
.bt-pag{display:flex;align-items:center;justify-content:center;gap:6px;padding:18px 0 14px;border-top:1px solid rgba(255,255,255,0.05)}
.bt-pag-btn{font-family:'JetBrains Mono',monospace;font-size:.54rem;font-weight:800;color:rgba(255,255,255,0.25);background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:6px 13px;cursor:default;transition:all .2s;letter-spacing:.04em}
.bt-pag-btn:hover{background:rgba(255,255,255,0.05);color:rgba(255,255,255,0.5)}
.bt-pag-btn.active{color:#00D559;border-color:rgba(0,213,89,0.3);background:rgba(0,213,89,0.1);box-shadow:0 0 16px rgba(0,213,89,0.12);text-shadow:0 0 12px rgba(0,213,89,0.4)}
.bt-pag-info{font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:700;color:rgba(255,255,255,0.15);margin:0 12px;letter-spacing:.05em}

/* ── How it works — card grid ── */
.bt-how{margin-top:28px}
.bt-how-hdr{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:800;color:rgba(255,255,255,0.85);margin:0 0 16px;text-align:center}
.bt-how-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.bt-how-card{background:linear-gradient(168deg,rgba(10,16,32,0.95),rgba(8,12,24,0.98));border:1px solid rgba(0,213,89,0.06);border-radius:16px;padding:20px 18px;text-align:center;transition:all .25s;position:relative;overflow:hidden}
.bt-how-card:hover{border-color:rgba(0,213,89,0.25);transform:translateY(-3px);box-shadow:0 12px 36px rgba(0,0,0,0.4),0 0 20px rgba(0,213,89,0.04)}
.bt-how-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(0,213,89,0.3),transparent);opacity:0;transition:opacity .25s}
.bt-how-card:hover::before{opacity:1}
.bt-how-card-ico{font-size:1.6rem;display:block;margin-bottom:10px}
.bt-how-card-title{font-family:'Space Grotesk',sans-serif;font-size:.72rem;font-weight:800;color:rgba(255,255,255,0.75);margin-bottom:6px}
.bt-how-card-desc{font-size:.62rem;color:rgba(255,255,255,0.35);line-height:1.6}

/* ── Footer note ── */
.bt-footer{text-align:center;margin-top:20px;padding:12px 0;position:relative}
.bt-footer-text{font-size:.62rem;color:rgba(255,255,255,0.25);display:inline-block;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:100px;padding:6px 20px}

/* ── Responsive ── */
@media(max-width:768px){
.bt-summary{grid-template-columns:repeat(4,1fr)}
.bt-tiers{grid-template-columns:repeat(2,1fr)}
.bt-card{grid-template-columns:auto 1fr auto auto;gap:8px;padding:10px 12px}
.bt-card-clv,.bt-card-safe{display:none}
.bt-tabs{gap:0}.bt-tab{padding:10px 12px;font-size:.56rem}
.bt-stat-grid,.bt-plat-grid{grid-template-columns:repeat(2,1fr)}
.bt-cal-grid{grid-template-columns:repeat(7,1fr)}
.bt-health{padding:14px 16px}
.bt-how-grid{grid-template-columns:1fr 1fr}
}
@media(max-width:520px){
.bt-summary{grid-template-columns:repeat(2,1fr)}
.bt-card{grid-template-columns:auto 1fr auto;gap:5px}
.bt-card-actual{display:none}
.bt-filters{flex-direction:column;gap:5px}
.sh h3{font-size:1.7rem}
.bt-stat-grid,.bt-plat-grid{grid-template-columns:1fr 1fr}
.bt-cal-grid{grid-template-columns:repeat(7,1fr)}
.bt-how-grid{grid-template-columns:1fr}
}
@media(max-width:380px){
.bt-summary{grid-template-columns:1fr 1fr;gap:6px}
.bt-card{grid-template-columns:auto 1fr;gap:4px;padding:8px 10px}
.bt-card-line,.bt-card-result{display:none}
.bt-card-player{font-size:.68rem}
.bt-cards{padding:6px 10px}
.sh h3{font-size:1.3rem}
.sh p{font-size:.66rem}
.bt-tabs{flex-wrap:wrap}.bt-tab{font-size:.5rem;padding:8px 8px}
.bt-how-grid{grid-template-columns:1fr}
.bt-bankroll{padding:14px 14px}
.bt-pnl{padding:14px 14px}
.bt-date-hdr{padding:10px 14px}
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

<!-- Tab bar -->
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

<!-- Filter bar -->
<div class="bt-filters">
<div class="bt-filter"><span class="bt-filter-label">Platform:</span><span class="bt-filter-val">All</span></div>
<div class="bt-filter"><span class="bt-filter-label">&#x1F50D; Player:</span><span class="bt-filter-val">Search...</span></div>
<div class="bt-filter"><span class="bt-filter-label">&#x1F4C5; Range:</span><span class="bt-filter-val">Last 30 Days</span></div>
<div class="bt-filter"><span class="bt-filter-label">Direction:</span><span class="bt-filter-val">All</span></div>
<div class="bt-resolve-btn">&#x1F504; Check Results Now</div>
</div>

<!-- Summary cards -->
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

<!-- Tier breakdown -->
<div class="bt-tiers">
<div class="bt-tier"><div class="bt-tier-name pt">&#x1F48E; Platinum</div><div class="bt-tier-wr pt">72.4%</div><div class="bt-tier-detail">21W / 8L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill pt" style="width:72.4%"></div></div></div>
<div class="bt-tier"><div class="bt-tier-name gld">&#x1F947; Gold</div><div class="bt-tier-wr gld">66.7%</div><div class="bt-tier-detail">28W / 14L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill gld" style="width:66.7%"></div></div></div>
<div class="bt-tier"><div class="bt-tier-name slv">&#x1F948; Silver</div><div class="bt-tier-wr slv">61.5%</div><div class="bt-tier-detail">24W / 15L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill slv" style="width:61.5%"></div></div></div>
<div class="bt-tier"><div class="bt-tier-name brz">&#x1F949; Bronze</div><div class="bt-tier-wr brz">60.0%</div><div class="bt-tier-detail">6W / 4L</div><div class="bt-tier-bar"><div class="bt-tier-bar-fill brz" style="width:60%"></div></div></div>
</div>

<!-- Model Health -->
<div class="bt-health">
<div class="bt-health-hdr">&#x1F4CA; Model Health Dashboard <span class="badge">CALIBRATED</span></div>
<div class="bt-stat-grid">
<div class="bt-stat-item"><div class="bt-stat-item-name">Points</div><div class="bt-stat-item-wr gr">68.3%</div><div class="bt-stat-item-detail">28W / 13L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Rebounds</div><div class="bt-stat-item-wr gr">66.7%</div><div class="bt-stat-item-detail">18W / 9L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Assists</div><div class="bt-stat-item-wr gd">63.0%</div><div class="bt-stat-item-detail">17W / 10L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">3-Pointers</div><div class="bt-stat-item-wr bl">61.5%</div><div class="bt-stat-item-detail">8W / 5L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Steals</div><div class="bt-stat-item-wr gr">70.0%</div><div class="bt-stat-item-detail">7W / 3L</div></div>
<div class="bt-stat-item"><div class="bt-stat-item-name">Blocks</div><div class="bt-stat-item-wr gd">66.7%</div><div class="bt-stat-item-detail">4W / 2L</div></div>
</div>
<div class="bt-plat-grid">
<div class="bt-plat-item"><div class="bt-plat-item-name pp">PrizePicks</div><div class="bt-plat-item-wr">68.2%</div><div class="bt-plat-item-detail">30W / 14L &middot; Best</div></div>
<div class="bt-plat-item"><div class="bt-plat-item-name ud">Underdog</div><div class="bt-plat-item-wr">63.6%</div><div class="bt-plat-item-detail">28W / 16L</div></div>
<div class="bt-plat-item"><div class="bt-plat-item-name dk">DK Pick6</div><div class="bt-plat-item-wr">65.6%</div><div class="bt-plat-item-detail">21W / 11L</div></div>
</div>
</div>

<!-- Calendar Heatmap -->
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

<!-- P&L Chart -->
<div class="bt-pnl">
<div class="bt-pnl-hdr">
<div class="bt-pnl-lbl">&#x1F4C8; Cumulative P&amp;L Curve</div>
<div class="bt-pnl-val">+$847 &middot; +84.7% ROI</div>
</div>
<svg viewBox="0 0 400 70" preserveAspectRatio="none">
<defs>
<linearGradient id="pnlGrad2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#00D559" stop-opacity="0.35"/><stop offset="0.7" stop-color="#00D559" stop-opacity="0.05"/><stop offset="1" stop-color="#00D559" stop-opacity="0"/></linearGradient>
<filter id="pnlGlow"><feGaussianBlur stdDeviation="2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<line x1="0" y1="65" x2="400" y2="65" stroke="rgba(255,255,255,0.04)" stroke-width="0.5"/>
<line x1="0" y1="45" x2="400" y2="45" stroke="rgba(255,255,255,0.02)" stroke-width="0.5" stroke-dasharray="4,4"/>
<line x1="0" y1="25" x2="400" y2="25" stroke="rgba(255,255,255,0.02)" stroke-width="0.5" stroke-dasharray="4,4"/>
<path d="M0,62 L14,59 L28,57 L42,55 L56,58 L70,53 L84,50 L98,51 L112,47 L126,44 L140,45 L154,41 L168,37 L182,39 L196,35 L210,32 L224,30 L238,33 L252,29 L266,26 L280,22 L294,23 L308,20 L322,17 L336,14 L350,12 L364,10 L378,8 L392,5 L400,3 L400,70 L0,70 Z" fill="url(#pnlGrad2)"/>
<path d="M0,62 L14,59 L28,57 L42,55 L56,58 L70,53 L84,50 L98,51 L112,47 L126,44 L140,45 L154,41 L168,37 L182,39 L196,35 L210,32 L224,30 L238,33 L252,29 L266,26 L280,22 L294,23 L308,20 L322,17 L336,14 L350,12 L364,10 L378,8 L392,5 L400,3" fill="none" stroke="#00D559" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" filter="url(#pnlGlow)" style="stroke-dasharray:800;stroke-dashoffset:800;animation:btLineGrow 2s ease forwards"/>
<circle cx="400" cy="3" r="4" fill="#00D559" opacity="0.9"><animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite"/></circle>
</svg>
</div>

<!-- Today -->
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

<!-- Yesterday -->
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

<!-- How it works — card grid -->
<div class="bt-how">
<div class="bt-how-hdr">&#x1F4D6; How the Bet Tracker Works</div>
<div class="bt-how-grid">
<div class="bt-how-card"><span class="bt-how-card-ico">&#x1F4DD;</span><div class="bt-how-card-title">Log Every Bet</div><div class="bt-how-card-desc">Record picks with one click. Platform, stake, odds &amp; SAFE Score saved automatically.</div></div>
<div class="bt-how-card"><span class="bt-how-card-ico">&#x1F4CA;</span><div class="bt-how-card-title">Auto-Grade Results</div><div class="bt-how-card-desc">Checks final box scores and marks every prop as HIT or MISS. No manual entry.</div></div>
<div class="bt-how-card"><span class="bt-how-card-ico">&#x1F4B0;</span><div class="bt-how-card-title">Track Your Bankroll</div><div class="bt-how-card-desc">ROI, win rate, CLV capture, profit/loss &amp; bankroll growth with real charts.</div></div>
<div class="bt-how-card"><span class="bt-how-card-ico">&#x1F50D;</span><div class="bt-how-card-title">Filter by Anything</div><div class="bt-how-card-desc">Platform, stat type, SAFE range, tier, date, or direction. Export to CSV anytime.</div></div>
<div class="bt-how-card"><span class="bt-how-card-ico">&#x1F6E1;&#xFE0F;</span><div class="bt-how-card-title">No Fake Screenshots</div><div class="bt-how-card-desc">Your Bet Tracker is YOUR data. Every win and loss, verifiable and auditable.</div></div>
<div class="bt-how-card"><span class="bt-how-card-ico">&#x1F3C6;</span><div class="bt-how-card-title">Achievements &amp; Streaks</div><div class="bt-how-card-desc">Earn badges for win streaks, ROI milestones &amp; volume. Track your progress.</div></div>
</div>
</div>

<div class="bt-footer"><span class="bt-footer-text">&#x2191; This is a demo preview with sample data. Sign up free to get your own live Bet Tracker.</span></div>
""")

    # ── Section anchor: Pricing ──
    st.markdown('<div id="sec-pricing" data-section-id="pricing" style="height:0;overflow:hidden;"></div>', unsafe_allow_html=True)

    # ── Below-fold: Pricing tiers, FAQ, CTA ──────────────────
    # Uses st.html() to bypass Streamlit's markdown parser which
    # cannot handle deeply nested HTML structures.
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7)}

@keyframes prShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
@keyframes prFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
@keyframes prPulse{0%,100%{box-shadow:0 0 0 0 rgba(0,213,89,0.2)}50%{box-shadow:0 0 30px 8px rgba(0,213,89,0.08)}}
@keyframes prGlow{0%,100%{opacity:0.6}50%{opacity:1}}
@keyframes prFadeUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
@keyframes prSeatPulse{0%,100%{color:#c084fc;text-shadow:0 0 10px rgba(192,132,252,0.3)}50%{color:#e9b3ff;text-shadow:0 0 30px rgba(192,132,252,0.6)}}
@keyframes prBarSlide{0%{background-position:300% 0}100%{background-position:-300% 0}}

.em{background:linear-gradient(135deg,#00D559 0%,#2D9EFF 50%,#c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}

/* ── Section Header ── */
.pr-head{text-align:center;margin-bottom:48px;position:relative;animation:prFadeUp 0.8s ease both}
.pr-head::before{content:'';display:block;width:80px;height:5px;margin:0 auto 24px;background:linear-gradient(90deg,#00D559,#2D9EFF,#c084fc);border-radius:6px;background-size:200% 100%;animation:prShimmer 4s ease infinite}
.pr-head h2{font-family:'Space Grotesk',sans-serif;font-size:3.6rem;font-weight:800;color:#fff;margin:0 0 12px;letter-spacing:-0.05em;line-height:1.05}
.pr-head p{font-size:1rem;color:rgba(255,255,255,0.4);margin:0;line-height:1.7;max-width:560px;margin:0 auto}

/* ── Tier Grid ── */
.pr-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}

/* ── Tier Card ── */
.tc2{background:linear-gradient(168deg,rgba(10,16,32,0.98) 0%,rgba(6,10,20,0.98) 100%);border:1.5px solid rgba(0,213,89,0.06);border-radius:20px;padding:32px 20px 28px;position:relative;overflow:hidden;transition:all 0.4s cubic-bezier(0.4,0,0.2,1);animation:prFadeUp 0.8s ease both}
.tc2:nth-child(1){animation-delay:0.1s}.tc2:nth-child(2){animation-delay:0.2s}.tc2:nth-child(3){animation-delay:0.3s}.tc2:nth-child(4){animation-delay:0.4s}
.tc2::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0}
.tc2::after{content:'';position:absolute;inset:0;border-radius:24px;opacity:0;transition:opacity 0.4s;pointer-events:none}
.tc2:hover{transform:translateY(-12px) scale(1.02);box-shadow:0 32px 80px rgba(0,0,0,0.5),0 0 60px rgba(0,213,89,0.06)}
.tc2:hover::after{opacity:1}

/* Tier color variants */
.tc2.tf::before{background:linear-gradient(90deg,#708090,#A0AABE)}
.tc2.tf:hover{border-color:rgba(160,170,190,0.3)}.tc2.tf::after{background:radial-gradient(ellipse at 50% 0%,rgba(160,170,190,0.06),transparent 70%)}
.tc2.ts::before{background:linear-gradient(90deg,#F9C62B,#ff8c00)}
.tc2.ts:hover{border-color:rgba(249,198,43,0.3)}.tc2.ts::after{background:radial-gradient(ellipse at 50% 0%,rgba(249,198,43,0.06),transparent 70%)}
.tc2.tm::before{background:linear-gradient(90deg,#00D559,#2D9EFF)}
.tc2.tm:hover{border-color:rgba(0,213,89,0.3)}.tc2.tm::after{background:radial-gradient(ellipse at 50% 0%,rgba(0,213,89,0.06),transparent 70%)}
.tc2.ti::before{background:linear-gradient(90deg,#c084fc,#9333ea)}
.tc2.ti:hover{border-color:rgba(192,132,252,0.3)}.tc2.ti::after{background:radial-gradient(ellipse at 50% 0%,rgba(192,132,252,0.06),transparent 70%)}

/* Popular badge */
.tc2-pop{position:absolute;top:16px;right:16px;font-family:'JetBrains Mono',monospace;font-size:0.5rem;font-weight:800;color:#0B0F19;background:linear-gradient(135deg,#00D559,#2D9EFF);padding:3px 10px;border-radius:100px;text-transform:uppercase;letter-spacing:0.1em}

/* Tier header */
.tc2-ico{font-size:2.4rem;margin-bottom:12px;display:block;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.3))}
.tc2-name{font-family:'Space Grotesk',sans-serif;font-size:0.82rem;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px}
.tf .tc2-name{color:#A0AABE}.ts .tc2-name{color:#F9C62B}.tm .tc2-name{color:#00D559}.ti .tc2-name{color:#c084fc}
.tc2-price{font-family:'JetBrains Mono',monospace;font-size:2rem;font-weight:800;color:#fff;margin-bottom:2px;line-height:1.2}
.tc2-price .sm{font-size:0.75rem;font-weight:500;color:rgba(255,255,255,0.3)}
.tc2-yearly{font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:rgba(255,255,255,0.25);margin-bottom:12px;display:block}
.tc2-quote{font-size:0.68rem;font-style:italic;color:rgba(255,255,255,0.2);margin-bottom:18px;line-height:1.5;min-height:2.5em}

/* Feature list */
.tc2-list{list-style:none;padding:0;margin:0}
.tc2-feat{display:flex;align-items:flex-start;gap:8px;padding:7px 0;border-top:1px solid rgba(255,255,255,0.03)}
.tc2-feat:first-child{border-top:none}
.tc2-fico{font-size:0.82rem;flex-shrink:0;line-height:1.3}
.tc2-ftxt{font-family:'Space Grotesk',sans-serif;font-size:0.7rem;font-weight:600;color:rgba(255,255,255,0.65);line-height:1.4}
.tc2-fdesc{font-size:0.58rem;color:rgba(255,255,255,0.28);line-height:1.5;margin-top:2px}

/* ── Comparison table ── */
.pr-compare{margin:0 0 28px;animation:prFadeUp 0.8s ease 0.5s both}
.pr-compare summary{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;background:linear-gradient(135deg,rgba(0,213,89,0.06),rgba(45,158,255,0.04),rgba(192,132,252,0.04));border:1.5px solid rgba(0,213,89,0.15);border-radius:16px;padding:18px 28px;text-align:center;cursor:pointer;font-family:'Space Grotesk',sans-serif;font-size:0.95rem;font-weight:700;color:#00D559;letter-spacing:0.01em;list-style:none;transition:all 0.3s}
.pr-compare summary::-webkit-details-marker{display:none}
.pr-compare summary::marker{display:none;content:''}
.pr-compare summary:hover{background:linear-gradient(135deg,rgba(0,213,89,0.12),rgba(45,158,255,0.08),rgba(192,132,252,0.06));border-color:rgba(0,213,89,0.3);box-shadow:0 8px 32px rgba(0,213,89,0.1);transform:translateY(-2px)}
.pr-compare summary .arrow{display:inline-block;transition:transform 0.3s}
.pr-compare[open] summary .arrow{transform:rotate(180deg)}

.pr-tw{margin:20px 0 0;overflow-x:auto;border-radius:20px;border:1.5px solid rgba(255,255,255,0.06);background:rgba(255,255,255,0.015);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.pr-tt{width:100%;border-collapse:separate;border-spacing:0;font-size:0.7rem}
.pr-tt thead th{padding:16px 12px;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:rgba(255,255,255,0.25);border-bottom:1px solid rgba(255,255,255,0.06);text-align:center;position:sticky;top:0;background:rgba(8,12,24,0.9);backdrop-filter:blur(8px)}
.pr-tt thead th:first-child{text-align:left;width:32%;padding-left:20px}
.pr-tt thead th.hf{color:#A0AABE}.pr-tt thead th.hs{color:#F9C62B}.pr-tt thead th.hm{color:#00D559}.pr-tt thead th.hi{color:#c084fc}
.pr-tt tbody td{padding:12px 12px;text-align:center;color:rgba(255,255,255,0.25);border-bottom:1px solid rgba(255,255,255,0.025);font-weight:500;transition:background 0.2s}
.pr-tt tbody td:first-child{text-align:left;padding-left:20px;color:rgba(255,255,255,0.55);font-weight:600;font-size:0.68rem}
.pr-tt tbody tr:hover td{background:rgba(255,255,255,0.02)}
.pr-tt tbody tr:last-child td{border-bottom:none}
.pr-tt .y{color:#00D559;font-weight:800;font-size:0.9rem}
.pr-tt .n{color:rgba(255,255,255,0.08);font-size:0.8rem}
.pr-tt .lim{color:#ff9d00;font-weight:700;font-size:0.65rem}
.pr-tt .cat td{color:rgba(0,213,89,0.45);font-weight:800;font-size:0.58rem;text-transform:uppercase;letter-spacing:0.08em;padding:10px 20px;background:rgba(0,213,89,0.02);border-bottom:1px solid rgba(0,213,89,0.06)}

/* ── Savings callout ── */
.pr-save{background:linear-gradient(135deg,rgba(249,198,43,0.06) 0%,rgba(249,198,43,0.02) 100%);border:1.5px solid rgba(249,198,43,0.15);border-radius:20px;padding:28px 24px;text-align:center;margin:0 0 24px;position:relative;overflow:hidden;animation:prFadeUp 0.8s ease 0.6s both}
.pr-save::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,#F9C62B,#ff8c00,transparent);background-size:200% 100%;animation:prShimmer 3s ease infinite}
.pr-save-big{font-family:'JetBrains Mono',monospace;font-size:2.4rem;font-weight:800;color:#F9C62B;display:block;margin-bottom:4px;text-shadow:0 0 30px rgba(249,198,43,0.2)}
.pr-save-txt{font-family:'Space Grotesk',sans-serif;font-size:0.95rem;font-weight:700;color:rgba(255,255,255,0.6);margin:0}
.pr-save-sub{font-size:0.72rem;color:rgba(255,255,255,0.28);margin:8px 0 0;line-height:1.6}

/* ── Responsive ── */
@media(max-width:900px){
  .pr-grid{grid-template-columns:repeat(2,1fr)}
  .pr-head h2{font-size:2.4rem}
}
@media(max-width:520px){
  .pr-grid{grid-template-columns:1fr}
  .pr-head h2{font-size:1.8rem}
  .tc2{padding:24px 16px 20px}
  .pr-save{padding:22px 16px}
  .pr-head p{font-size:.85rem}
}
@media(max-width:380px){
  .pr-head h2{font-size:1.4rem}
  .pr-head p{font-size:.75rem}
  .tc2{padding:20px 12px 18px;border-radius:16px}
  .tc2-name{font-size:.82rem}
  .pr-save-big{font-size:1.8rem}
  .pr-save-txt{font-size:.82rem}
  .pr-save{padding:18px 12px;border-radius:16px}
}
</style>

<!-- Pricing Section -->
<div class="pr-head">
  <h2>Choose Your <span class="em">Edge</span></h2>
  <p>Every tier includes the full AI engine. Upgrade when you want more coverage, more tools, more alpha.</p>
</div>

<div class="pr-grid">
<!-- Smart Rookie -->
<div class="tc2 tf">
  <span class="tc2-ico">&#x2B50;</span>
  <div class="tc2-name">Smart Rookie</div>
  <div class="tc2-price">$0 <span class="sm">/ forever</span></div>
  <span class="tc2-yearly">&nbsp;</span>
  <div class="tc2-quote">&ldquo;Welcome to the smart side.&rdquo;<br>No credit card required.</div>
  <ul class="tc2-list">
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4A6;</span><div><div class="tc2-ftxt">Live Sweat</div><div class="tc2-fdesc">Track active bets in real-time with live scoring &amp; AI confidence updates.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4E1;</span><div><div class="tc2-ftxt">Live Games</div><div class="tc2-fdesc">Real-time NBA scoreboard with box scores &amp; stat leaders.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x26A1;</span><div><div class="tc2-ftxt">Quantum Analysis Matrix (10 props)</div><div class="tc2-fdesc">6 fused AI models, SAFE Scores, edge detection. 10 props/session.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F52C;</span><div><div class="tc2-ftxt">Prop Scanner (5 manual)</div><div class="tc2-fdesc">Instant AI analysis on any player prop you enter.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4E1;</span><div><div class="tc2-ftxt">Smart NBA Data</div><div class="tc2-fdesc">Full stats dashboard &mdash; averages, rankings, defensive ratings.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x2699;&#xFE0F;</span><div><div class="tc2-ftxt">Settings</div><div class="tc2-fdesc">Customize platforms, display &amp; notification preferences.</div></div></li>
  </ul>
</div>

<!-- Sharp IQ -->
<div class="tc2 ts">
  <span class="tc2-ico">&#x1F525;</span>
  <div class="tc2-name">Sharp IQ</div>
  <div class="tc2-price">$9<span style="font-size:1rem">.99</span> <span class="sm">/ mo</span></div>
  <span class="tc2-yearly">$107.89 / year &mdash; save 10%</span>
  <div class="tc2-quote">&ldquo;Your IQ just passed the books.&rdquo;<br>Everything in Free, plus:</div>
  <ul class="tc2-list">
    <li class="tc2-feat"><span class="tc2-fico">&#x26A1;</span><div><div class="tc2-ftxt">QAM &mdash; 25 Props</div><div class="tc2-fdesc">More coverage = more edges before books adjust.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F52C;</span><div><div class="tc2-ftxt">Prop Scanner &mdash; Unlimited + CSV + Live</div><div class="tc2-fdesc">Scan unlimited, bulk-upload CSV, or auto-pull slips.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F9EC;</span><div><div class="tc2-ftxt">Entry Builder</div><div class="tc2-fdesc">Build optimized PrizePicks &amp; Pick6 entries by EV.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F6E1;&#xFE0F;</span><div><div class="tc2-ftxt">Risk Shield</div><div class="tc2-fdesc">Portfolio-level exposure analysis by player &amp; team.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4CB;</span><div><div class="tc2-ftxt">Game Report</div><div class="tc2-fdesc">Matchup reports: pace, defense, rest, AI game scripts.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F52E;</span><div><div class="tc2-ftxt">Player Simulator</div><div class="tc2-fdesc">Quantum: 10K+ scenarios for hit probability.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4C8;</span><div><div class="tc2-ftxt">Bet Tracker</div><div class="tc2-fdesc">ROI, win rate, CLV capture, bankroll growth tracking.</div></div></li>
  </ul>
</div>

<!-- Smart Money -->
<div class="tc2 tm">
  <span class="tc2-pop">MOST POPULAR</span>
  <span class="tc2-ico">&#x1F48E;</span>
  <div class="tc2-name">Smart Money</div>
  <div class="tc2-price">$24<span style="font-size:1rem">.99</span> <span class="sm">/ mo</span></div>
  <span class="tc2-yearly">$269.89 / year &mdash; save 10%</span>
  <div class="tc2-quote">&ldquo;You are the smart money.&rdquo;<br>Everything in Sharp IQ, plus:</div>
  <ul class="tc2-list">
    <li class="tc2-feat"><span class="tc2-fico">&#x26A1;</span><div><div class="tc2-ftxt">QAM &mdash; ALL 300+ Props</div><div class="tc2-fdesc">Full unrestricted access to every prop tonight.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4B0;</span><div><div class="tc2-ftxt">Smart Money Bets</div><div class="tc2-fdesc">AI-detected sharp money flow &amp; line movement.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F5FA;&#xFE0F;</span><div><div class="tc2-ftxt">Correlation Matrix</div><div class="tc2-fdesc">Find hidden +EV parlays with correlation heatmaps.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F4CA;</span><div><div class="tc2-ftxt">Proving Grounds</div><div class="tc2-fdesc">Backtest strategies against historical data.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F399;&#xFE0F;</span><div><div class="tc2-ftxt">The Studio</div><div class="tc2-fdesc">AI narrative reports &amp; shareable pick cards.</div></div></li>
  </ul>
</div>

<!-- Insider Circle -->
<div class="tc2 ti">
  <span class="tc2-ico">&#x1F451;</span>
  <div class="tc2-name">Insider Circle</div>
  <div class="tc2-price">$499<span style="font-size:1rem">.99</span></div>
  <span class="tc2-yearly">one-time &middot; lifetime access</span>
  <div class="tc2-quote">&ldquo;You knew before everyone.&rdquo;<br>Everything in Smart Money, plus:</div>
  <ul class="tc2-list">
    <li class="tc2-feat"><span class="tc2-fico">&#x1F451;</span><div><div class="tc2-ftxt">Lifetime Access &mdash; Never Pay Again</div><div class="tc2-fdesc">Every current &amp; future feature. No renewals.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F680;</span><div><div class="tc2-ftxt">Early Access to New Tools</div><div class="tc2-fdesc">Test new AI models &amp; pages before launch.</div></div></li>
    <li class="tc2-feat"><span class="tc2-fico">&#x1F3C6;</span><div><div class="tc2-ftxt">Founding Member Status</div><div class="tc2-fdesc">Limited to 75 members. Exclusive badge &amp; priority support.</div></div></li>
  </ul>
</div>
</div><!-- /pr-grid -->

<!-- Compare toggle -->
<details class="pr-compare">
<summary>&#x1F50D; Compare All Features Side-by-Side <span class="arrow">&#x25BC;</span></summary>
<div class="pr-tw"><table class="pr-tt">
<thead><tr><th>Page / Feature</th><th class="hf">&#x2B50; Free</th><th class="hs">&#x1F525; Sharp</th><th class="hm">&#x1F48E; Smart</th><th class="hi">&#x1F451; Insider</th></tr></thead>
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

<!-- Savings -->
<div class="pr-save">
  <span class="pr-save-big">$1,188/yr</span>
  <p class="pr-save-txt">That&rsquo;s what you&rsquo;d pay for OddsJam alone.</p>
  <p class="pr-save-sub">Smart Pick Pro gives you more features, more AI, more props &mdash; for <strong style="color:#00D559;">$0</strong>. Do the math.</p>
</div>

""")

    # ── Subscription Purchase Section ─────────────────────────
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
@keyframes subBarSlide{0%{background-position:300% 0}100%{background-position:-300% 0}}
@keyframes subGlow{0%,100%{box-shadow:0 0 0 0 rgba(0,213,89,0.08)}50%{box-shadow:0 0 40px 12px rgba(0,213,89,0.04)}}
@keyframes subFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes subPulseRing{0%{transform:scale(0.95);opacity:0.5}50%{transform:scale(1.05);opacity:0.2}100%{transform:scale(0.95);opacity:0.5}}
.sub-purchase-section {
    background: linear-gradient(168deg, rgba(0, 213, 89, 0.04) 0%, rgba(8, 12, 24, 0.95) 30%, rgba(8, 12, 24, 0.95) 70%, rgba(192, 132, 252, 0.04) 100%);
    border: 1.5px solid rgba(255, 255, 255, 0.06);
    border-radius: 32px;
    padding: 56px 32px 16px;
    margin: 12px 0 0;
    position: relative;
    overflow: hidden;
}
.sub-purchase-section::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #F9C62B, #2D9EFF, #c084fc, #00D559);
    background-size: 300% 100%;
    animation: subBarSlide 6s ease infinite;
}
.sub-purchase-section::after {
    content: '';
    position: absolute;
    top: -80px; left: 50%; transform: translateX(-50%);
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(0, 213, 89, 0.06), transparent 65%);
    pointer-events: none;
}
.sub-purchase-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.6rem;
    font-weight: 800;
    text-align: center;
    color: #fff;
    margin: 0 0 6px;
    letter-spacing: -0.04em;
    position: relative;
    line-height: 1.15;
}
.sub-purchase-title .sub-em {
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 50%, #c084fc 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.sub-purchase-sub {
    text-align: center;
    font-size: 0.95rem;
    color: rgba(255, 255, 255, 0.35);
    margin: 0 0 8px;
    line-height: 1.7;
    position: relative;
}
.sub-purchase-sub strong { color: #00D559; }
.sub-purchase-trust {
    display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;
    margin: 0 0 4px; position: relative;
}
.sub-purchase-trust span {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.6rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.2);
    display: flex; align-items: center; gap: 5px;
}
</style>
<div class="sub-purchase-section">
    <p class="sub-purchase-title">Get Your <span class="sub-em">Edge</span> Now</p>
    <p class="sub-purchase-sub">Subscribe instantly &mdash; <strong>secure Stripe checkout</strong>, cancel anytime, no commitment.</p>
    <div class="sub-purchase-trust">
      <span>&#x1F512; 256-bit encrypted</span>
      <span>&#x26A1; Instant access</span>
      <span>&#x1F6AB; Cancel anytime</span>
      <span>&#x1F4B3; Powered by Stripe</span>
    </div>
    <!-- Extended trust badges -->
    <div style="display:flex;justify-content:center;gap:24px;flex-wrap:wrap;margin-top:14px;padding-top:14px;
         border-top:1px solid rgba(255,255,255,0.04)">
      <div style="display:flex;align-items:center;gap:6px">
        <div style="width:32px;height:32px;border-radius:8px;background:rgba(0,213,89,0.06);
             display:flex;align-items:center;justify-content:center;font-size:0.9rem">&#x1F6E1;&#xFE0F;</div>
        <div>
          <div style="font-family:'Space Grotesk',sans-serif;font-size:0.55rem;font-weight:700;
               color:rgba(255,255,255,0.5)">SOC 2 Compliant</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.45rem;color:rgba(255,255,255,0.2)">
            Enterprise-grade security</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <div style="width:32px;height:32px;border-radius:8px;background:rgba(45,158,255,0.06);
             display:flex;align-items:center;justify-content:center;font-size:0.9rem">&#x23F1;&#xFE0F;</div>
        <div>
          <div style="font-family:'Space Grotesk',sans-serif;font-size:0.55rem;font-weight:700;
               color:rgba(255,255,255,0.5)">10-Second Signup</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.45rem;color:rgba(255,255,255,0.2)">
            No credit card for free tier</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <div style="width:32px;height:32px;border-radius:8px;background:rgba(192,132,252,0.06);
             display:flex;align-items:center;justify-content:center;font-size:0.9rem">&#x1F4C8;</div>
        <div>
          <div style="font-family:'Space Grotesk',sans-serif;font-size:0.55rem;font-weight:700;
               color:rgba(255,255,255,0.5)">2,400+ Active Sharps</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.45rem;color:rgba(255,255,255,0.2)">
            Trusted by winning bettors</div>
        </div>
      </div>
    </div>
</div>
""", unsafe_allow_html=True)

    _stripe_ready = is_stripe_configured()

    # ── Yearly billing toggle ──────────────────────────────────────────────
    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,700;0,800;0,900;1,700;1,800;1,900&family=JetBrains+Mono:wght@400;500;700;800&family=Inter:wght@400;500;600;700&display=swap');

/* ── Yearly toggle row ── */
.sub-toggle-row{display:flex;align-items:center;justify-content:center;gap:14px;padding:10px 0 22px}
.sub-toggle-label{font-family:'Barlow Condensed',sans-serif;font-size:.82rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,0.35)}
.sub-toggle-label.active{color:#00D559;text-shadow:0 0 16px rgba(0,213,89,0.35)}
.sub-save-badge{font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:800;color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.25);padding:3px 12px;border-radius:100px;letter-spacing:.05em;text-transform:uppercase;animation:scPulse 2.5s ease-in-out infinite}
@keyframes scPulse{0%,100%{box-shadow:0 0 8px rgba(0,213,89,0.2)}50%{box-shadow:0 0 18px rgba(0,213,89,0.45)}}

/* ── Column overrides ── */
[data-testid="stHorizontalBlock"]:has(.sub-card){gap:14px !important;padding:0 2px}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]{
    background:linear-gradient(168deg,rgba(8,13,26,0.99) 0%,rgba(5,9,18,0.99) 100%);
    border:1px solid rgba(255,255,255,0.07);
    border-radius:24px;padding:0 0 18px;position:relative;overflow:hidden;
    transition:all .35s cubic-bezier(.4,0,.2,1);
    box-shadow:0 20px 60px rgba(0,0,0,0.6)
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:hover{
    transform:translateY(-6px);
    box-shadow:0 28px 80px rgba(0,0,0,0.7),0 0 0 1px rgba(255,255,255,0.06) inset
}
/* col 1: gray/free */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(1):hover{border-color:rgba(160,170,190,0.25)}
/* col 2: amber/sharp */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(2){border-color:rgba(249,198,43,0.08)}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(2):hover{border-color:rgba(249,198,43,0.28);box-shadow:0 28px 80px rgba(0,0,0,0.7),0 0 40px rgba(249,198,43,0.08)}
/* col 3: green/smart — featured */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(3){
    border-color:rgba(0,213,89,0.22);
    box-shadow:0 0 40px rgba(0,213,89,0.08),0 20px 60px rgba(0,0,0,0.6),0 0 0 1px rgba(0,213,89,0.06) inset
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(3):hover{
    border-color:rgba(0,213,89,0.4);
    box-shadow:0 28px 80px rgba(0,213,89,0.15),0 0 60px rgba(0,213,89,0.1)
}
/* col 4: purple/insider */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(4){border-color:rgba(192,132,252,0.12)}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(4):hover{border-color:rgba(192,132,252,0.32);box-shadow:0 28px 80px rgba(192,132,252,0.1)}

/* ── Card header ── */
.sub-card{text-align:center;padding:28px 18px 16px;position:relative}
.sub-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background-size:200% 100%;animation:scShimmer 4s ease infinite}
@keyframes scShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.sub-card.free::before{background-image:linear-gradient(90deg,transparent,#A0AABE,rgba(160,170,190,0.6),#A0AABE,transparent)}
.sub-card.sharp::before{background-image:linear-gradient(90deg,transparent,#F9C62B,rgba(249,198,43,0.7),#F9C62B,transparent)}
.sub-card.smart::before{background-image:linear-gradient(90deg,transparent,#00D559,rgba(0,213,89,0.7),#00D559,transparent)}
.sub-card.insider::before{background-image:linear-gradient(90deg,transparent,#c084fc,rgba(192,132,252,0.7),#c084fc,transparent)}

.sub-card .sc-ico{font-size:2.8rem;display:block;margin:0 0 10px;filter:drop-shadow(0 6px 18px rgba(0,0,0,0.5))}
.sub-card .sc-name{
    font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:900;
    font-style:italic;text-transform:uppercase;letter-spacing:.04em;margin:0 0 10px
}
.sub-card .sc-price{
    font-family:'Barlow Condensed',sans-serif;font-size:3.0rem;font-weight:900;
    font-style:italic;line-height:1;margin:0 0 5px;letter-spacing:-.02em
}
.sub-card .sc-price .cents{font-size:1.4rem;font-weight:700;vertical-align:super;margin-left:-2px;font-style:normal}
.sub-card .sc-period{font-family:'JetBrains Mono',monospace;font-size:.54rem;color:rgba(255,255,255,0.22);letter-spacing:.05em}
.sub-card .sc-yearly{
    display:inline-block;margin-top:7px;
    font-family:'JetBrains Mono',monospace;font-size:.48rem;font-weight:700;
    color:#00D559;background:rgba(0,213,89,0.07);border:1px solid rgba(0,213,89,0.18);
    padding:3px 12px;border-radius:100px;letter-spacing:.04em
}
.sub-card .sc-save{
    display:inline-block;margin-top:6px;
    font-family:'JetBrains Mono',monospace;font-size:.46rem;font-weight:800;
    color:#0B0F19;background:#00D559;padding:2px 10px;border-radius:100px;
    letter-spacing:.05em;text-transform:uppercase;
    box-shadow:0 0 12px rgba(0,213,89,0.4)
}
.sub-card .sc-divider{
    width:48px;height:1px;margin:14px auto 12px;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,0.12),transparent)
}
.sub-card .sc-features{list-style:none;padding:0;margin:0;text-align:left}
.sub-card .sc-features li{
    font-family:'Inter',sans-serif;font-size:.66rem;color:rgba(255,255,255,0.45);
    padding:4px 0;display:flex;align-items:center;gap:8px;line-height:1.4
}
.sub-card .sc-features li .ck{
    color:#00D559;font-size:.62rem;flex-shrink:0;
    width:16px;height:16px;background:rgba(0,213,89,0.1);border-radius:50%;
    display:flex;align-items:center;justify-content:center;font-weight:800
}
.sub-card .sc-features li .nx{
    color:rgba(255,255,255,0.12);font-size:.62rem;flex-shrink:0;
    width:16px;height:16px;background:rgba(255,255,255,0.03);border-radius:50%;
    display:flex;align-items:center;justify-content:center
}
/* Popular badge */
.sub-card .sc-pop{
    position:absolute;top:14px;right:14px;
    font-family:'Barlow Condensed',sans-serif;font-size:.56rem;font-weight:900;
    font-style:italic;text-transform:uppercase;letter-spacing:.06em;
    color:#050910;background:linear-gradient(135deg,#00E865,#00D559);
    padding:4px 13px;border-radius:100px;
    box-shadow:0 0 20px rgba(0,213,89,0.5),0 2px 8px rgba(0,0,0,0.3)
}

/* Color assignments */
.sub-card.free .sc-name{color:#A0AABE}.sub-card.free .sc-price{color:#A0AABE}
.sub-card.sharp .sc-name{color:#F9C62B}.sub-card.sharp .sc-price{color:#F9C62B}
.sub-card.smart .sc-name{color:#00D559}.sub-card.smart .sc-price{color:#00D559}
.sub-card.insider .sc-name{color:#c084fc}.sub-card.insider .sc-price{color:#c084fc}

/* ── Streamlit input labels ── */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stTextInput"] label{
    font-family:'JetBrains Mono',monospace !important;
    font-size:.54rem !important;font-weight:700 !important;
    color:rgba(255,255,255,0.25) !important;
    text-transform:uppercase !important;letter-spacing:.08em !important
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stTextInput"] input{
    background:rgba(255,255,255,0.03) !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    border-radius:14px !important;
    font-family:'JetBrains Mono',monospace !important;
    font-size:.68rem !important;color:rgba(255,255,255,0.65) !important;
    padding:11px 16px !important
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stTextInput"] input:focus{
    border-color:rgba(0,213,89,0.3) !important;
    box-shadow:0 0 20px rgba(0,213,89,0.08) !important
}

/* ── Per-tier submit buttons ── */
/* ALL buttons: base reset */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stFormSubmitButton"] button{
    font-family:'Barlow Condensed',sans-serif !important;
    font-weight:900 !important;font-style:italic !important;
    font-size:.88rem !important;letter-spacing:.05em !important;
    text-transform:uppercase !important;
    border-radius:14px !important;padding:14px 20px !important;
    transition:all .25s cubic-bezier(.16,1,.3,1) !important;
    position:relative !important;overflow:hidden !important;width:100% !important
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stFormSubmitButton"] button:hover{
    transform:translateY(-3px) !important
}
/* col 2 = sharp: amber button */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(2) [data-testid="stFormSubmitButton"] button{
    background:linear-gradient(135deg,#FFD447 0%,#F9C62B 50%,#E8B020 100%) !important;
    color:#0B0F19 !important;
    border:1px solid rgba(249,198,43,0.4) !important;
    box-shadow:0 0 28px rgba(249,198,43,0.35),0 4px 16px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.25) !important
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(2) [data-testid="stFormSubmitButton"] button:hover{
    box-shadow:0 0 42px rgba(249,198,43,0.55),0 10px 28px rgba(0,0,0,0.4),inset 0 1px 0 rgba(255,255,255,0.25) !important;
    background:linear-gradient(135deg,#FFE066 0%,#FFD447 50%,#F9C62B 100%) !important
}
/* col 3 = smart: green button */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(3) [data-testid="stFormSubmitButton"] button{
    background:linear-gradient(135deg,#00FF85 0%,#00E865 40%,#00D559 100%) !important;
    color:#050910 !important;
    border:1px solid rgba(0,213,89,0.5) !important;
    box-shadow:0 0 32px rgba(0,213,89,0.4),0 4px 20px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.25) !important
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(3) [data-testid="stFormSubmitButton"] button:hover{
    box-shadow:0 0 50px rgba(0,213,89,0.6),0 12px 32px rgba(0,213,89,0.2),inset 0 1px 0 rgba(255,255,255,0.25) !important;
    background:linear-gradient(135deg,#00FFA0 0%,#00FF85 40%,#00E865 100%) !important
}
/* col 4 = insider: purple button */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(4) [data-testid="stFormSubmitButton"] button{
    background:linear-gradient(135deg,#d8b4fe 0%,#c084fc 50%,#a855f7 100%) !important;
    color:#0B0F19 !important;
    border:1px solid rgba(192,132,252,0.5) !important;
    box-shadow:0 0 28px rgba(192,132,252,0.4),0 4px 16px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.2) !important
}
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stColumn"]:nth-child(4) [data-testid="stFormSubmitButton"] button:hover{
    box-shadow:0 0 44px rgba(192,132,252,0.6),0 10px 28px rgba(0,0,0,0.4),inset 0 1px 0 rgba(255,255,255,0.2) !important;
    background:linear-gradient(135deg,#e9d5ff 0%,#d8b4fe 50%,#c084fc 100%) !important
}

/* ── Alert tweaks ── */
[data-testid="stHorizontalBlock"]:has(.sub-card) [data-testid="stAlert"]{
    border-radius:14px !important;font-size:.68rem !important
}

/* ── Footer ── */
.sub-footer{text-align:center;margin:20px 0 4px;padding:16px 0;border-top:1px solid rgba(255,255,255,0.05)}
.sub-footer-inner{display:inline-flex;align-items:center;gap:18px;flex-wrap:wrap;justify-content:center}
.sub-footer-inner span{
    font-family:'JetBrains Mono',monospace;font-size:.54rem;font-weight:700;
    color:rgba(255,255,255,0.16);display:flex;align-items:center;gap:5px;letter-spacing:.04em
}
.sub-footer-stripe{
    display:inline-flex;align-items:center;gap:6px;
    font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;
    color:rgba(255,255,255,0.28);
    background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
    padding:6px 16px;border-radius:100px
}
</style>""", unsafe_allow_html=True)

    # ── Yearly billing toggle ──────────────────────────────────────────────
    _t_col1, _t_col2, _t_col3 = st.columns([1, 2, 1])
    with _t_col2:
        st.markdown("""<div style="text-align:center;padding:4px 0 6px">
<span style="font-family:'Barlow Condensed',sans-serif;font-size:.85rem;font-weight:900;font-style:italic;text-transform:uppercase;letter-spacing:.06em;color:rgba(255,255,255,0.28)">
&#x1F4C5; Billing Cycle
</span></div>""", unsafe_allow_html=True)
        _yearly = st.toggle("Annual billing — save 10%", value=False, key="_pricing_toggle")
        if _yearly:
            st.markdown("""<div style="text-align:center;margin-top:-8px">
<span style="font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:800;color:#00D559;background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.25);padding:3px 14px;border-radius:100px;letter-spacing:.05em">
&#x2728; SAVE 10% — BILLED ANNUALLY
</span></div>""", unsafe_allow_html=True)

    # ── Pricing values (monthly vs yearly) ────────────────────────────────
    if _yearly:
        _sharp_price = "$8<span class='cents'>.99</span>"
        _sharp_period = "per month, billed annually"
        _sharp_yearly = "~$107.88/yr &middot; you save $11.88"
        _sharp_btn    = "&#x1F4C5; Subscribe &mdash; $107.88/yr"
        _sharp_lookup = "sharp_iq_annual"
        _smart_price  = "$22<span class='cents'>.49</span>"
        _smart_period = "per month, billed annually"
        _smart_yearly = "~$269.88/yr &middot; you save $30.00"
        _smart_btn    = "&#x1F4C5; Subscribe &mdash; $269.88/yr"
        _smart_lookup = "smart_money_annual"
    else:
        _sharp_price  = "$9<span class='cents'>.99</span>"
        _sharp_period = "per month"
        _sharp_yearly = "~$107/yr &middot; save 10% with annual"
        _sharp_btn    = "&#x1F680; Subscribe &mdash; $9.99/mo"
        _sharp_lookup = "sharp_iq"
        _smart_price  = "$24<span class='cents'>.99</span>"
        _smart_period = "per month"
        _smart_yearly = "~$269/yr &middot; save 10% with annual"
        _smart_btn    = "&#x1F680; Subscribe &mdash; $24.99/mo"
        _smart_lookup = "smart_money"

    sub_cols = st.columns(4)
    with sub_cols[0]:
        st.markdown("""<div class="sub-card free">
  <span class="sc-ico">&#x2B50;</span>
  <div class="sc-name">Smart Rookie</div>
  <div class="sc-price">$0</div>
  <div class="sc-period">free forever</div>
  <div class="sc-divider"></div>
  <ul class="sc-features">
    <li><span class="ck">&#x2713;</span> 10 AI-analyzed props</li>
    <li><span class="ck">&#x2713;</span> Live Sweat mode</li>
    <li><span class="ck">&#x2713;</span> SAFE Score system</li>
    <li><span class="ck">&#x2713;</span> Live Games &amp; NBA Data</li>
    <li><span class="nx">&#x2717;</span> Bet Tracker</li>
    <li><span class="nx">&#x2717;</span> Entry Builder</li>
  </ul>
</div>""", unsafe_allow_html=True)
        st.success("✅ **Free** — create an account above!")

    with sub_cols[1]:
        st.markdown(f"""<div class="sub-card sharp">
  <span class="sc-ico">&#x1F525;</span>
  <div class="sc-name">Sharp IQ</div>
  <div class="sc-price">{_sharp_price}</div>
  <div class="sc-period">{_sharp_period}</div>
  <span class="sc-yearly">{_sharp_yearly}</span>
  <div class="sc-divider"></div>
  <ul class="sc-features">
    <li><span class="ck">&#x2713;</span> 25 AI-analyzed props</li>
    <li><span class="ck">&#x2713;</span> Unlimited Prop Scanner</li>
    <li><span class="ck">&#x2713;</span> Bet Tracker + ROI</li>
    <li><span class="ck">&#x2713;</span> Entry Builder</li>
    <li><span class="ck">&#x2713;</span> Player Simulator</li>
    <li><span class="nx">&#x2717;</span> Smart Money Bets</li>
  </ul>
</div>""", unsafe_allow_html=True)
        if _stripe_ready:
            with st.form("gate_checkout_sharp", clear_on_submit=False):
                _email_s = st.text_input("Email", placeholder="you@example.com", key="_gate_email_sharp")
                if st.form_submit_button(_sharp_btn, type="primary", use_container_width=True):
                    with st.spinner("Creating secure checkout…"):
                        _res = create_checkout_session(customer_email=_email_s.strip() if _email_s else "", price_lookup=_sharp_lookup)
                    if _res["success"]:
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={_res["url"]}">', unsafe_allow_html=True)
                        st.info(f"Redirecting… [Click here if not redirected]({_res['url']})")
                    else:
                        st.error(f"Checkout error: {_res['error']}")
        else:
            st.info("💳 Stripe checkout — coming soon!")

    with sub_cols[2]:
        st.markdown(f"""<div class="sub-card smart">
  <span class="sc-pop">POPULAR</span>
  <span class="sc-ico">&#x1F48E;</span>
  <div class="sc-name">Smart Money</div>
  <div class="sc-price">{_smart_price}</div>
  <div class="sc-period">{_smart_period}</div>
  <span class="sc-yearly">{_smart_yearly}</span>
  <div class="sc-divider"></div>
  <ul class="sc-features">
    <li><span class="ck">&#x2713;</span> Unlimited AI props</li>
    <li><span class="ck">&#x2713;</span> Smart Money Bets</li>
    <li><span class="ck">&#x2713;</span> Arbitrage Scanner</li>
    <li><span class="ck">&#x2713;</span> Game Predictions</li>
    <li><span class="ck">&#x2713;</span> Bankroll Manager</li>
    <li><span class="ck">&#x2713;</span> All Sharp IQ features</li>
  </ul>
</div>""", unsafe_allow_html=True)
        if _stripe_ready:
            with st.form("gate_checkout_smart", clear_on_submit=False):
                _email_m = st.text_input("Email", placeholder="you@example.com", key="_gate_email_smart")
                if st.form_submit_button(_smart_btn, type="primary", use_container_width=True):
                    with st.spinner("Creating secure checkout…"):
                        _res = create_checkout_session(customer_email=_email_m.strip() if _email_m else "", price_lookup=_smart_lookup)
                    if _res["success"]:
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={_res["url"]}">', unsafe_allow_html=True)
                        st.info(f"Redirecting… [Click here if not redirected]({_res['url']})")
                    else:
                        st.error(f"Checkout error: {_res['error']}")
        else:
            st.info("💳 Stripe checkout — coming soon!")

    with sub_cols[3]:
        st.markdown("""<div class="sub-card insider">
  <span class="sc-ico">&#x1F451;</span>
  <div class="sc-name">Insider Circle</div>
  <div class="sc-price">$499<span class="cents">.99</span></div>
  <div class="sc-period">lifetime access</div>
  <span class="sc-yearly">One-time payment &middot; forever</span>
  <div class="sc-divider"></div>
  <ul class="sc-features">
    <li><span class="ck">&#x2713;</span> Everything, forever</li>
    <li><span class="ck">&#x2713;</span> Priority support</li>
    <li><span class="ck">&#x2713;</span> Early feature access</li>
    <li><span class="ck">&#x2713;</span> Custom alerts</li>
    <li><span class="ck">&#x2713;</span> Founder badge</li>
    <li><span class="ck">&#x2713;</span> All future updates</li>
  </ul>
</div>""", unsafe_allow_html=True)
        if _stripe_ready:
            with st.form("gate_checkout_insider", clear_on_submit=False):
                _email_i = st.text_input("Email", placeholder="you@example.com", key="_gate_email_insider")
                if st.form_submit_button("&#x1F451; Lifetime — $499.99", type="primary", use_container_width=True):
                    with st.spinner("Creating secure checkout…"):
                        _res = create_checkout_session(customer_email=_email_i.strip() if _email_i else "", price_lookup="insider_circle")
                    if _res["success"]:
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={_res["url"]}">', unsafe_allow_html=True)
                        st.info(f"Redirecting… [Click here if not redirected]({_res['url']})")
                    else:
                        st.error(f"Checkout error: {_res['error']}")
        else:
            st.info("💳 Stripe checkout — coming soon!")

    st.markdown("""<div class="sub-footer">
  <div class="sub-footer-inner">
    <span class="sub-footer-stripe">&#x1F512; Secure checkout by Stripe</span>
    <span>&#x1F504; Cancel anytime</span>
    <span>&#x2714;&#xFE0F; No hidden fees</span>
    <span>&#x26A1; Instant activation</span>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Competitor comparison table ──
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
.cmp-wrap{padding:48px 0 40px;text-align:center}
.cmp-badge{display:inline-block;font-family:'Space Grotesk',sans-serif;font-size:0.6rem;font-weight:700;
  color:#00D559;text-transform:uppercase;letter-spacing:0.14em;
  padding:5px 14px;border-radius:100px;border:1px solid rgba(0,213,89,0.15);
  background:rgba(0,213,89,0.05);margin-bottom:16px}
.cmp-h{font-family:'Space Grotesk',sans-serif;font-size:2.8rem;font-weight:800;color:#fff;
  margin:0 0 8px;letter-spacing:-0.04em}
.cmp-sub{font-family:'Inter',sans-serif;font-size:0.8rem;color:rgba(255,255,255,0.35);margin:0 0 32px}
.cmp-table{width:100%;max-width:720px;margin:0 auto;border-collapse:separate;border-spacing:0;
  border:1px solid rgba(255,255,255,0.06);border-radius:16px;overflow:hidden;
  background:rgba(255,255,255,0.01)}
.cmp-table th,.cmp-table td{padding:12px 18px;text-align:left;font-size:0.75rem;
  border-bottom:1px solid rgba(255,255,255,0.04)}
.cmp-table thead th{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:0.68rem;
  text-transform:uppercase;letter-spacing:0.06em;color:rgba(255,255,255,0.35);
  background:rgba(255,255,255,0.02)}
.cmp-table thead th:nth-child(2){color:#00D559}
.cmp-table thead th:nth-child(3),.cmp-table thead th:nth-child(4){color:rgba(255,255,255,0.2)}
.cmp-table td{font-family:'Inter',sans-serif;color:rgba(255,255,255,0.55)}
.cmp-table td:first-child{font-weight:600;color:rgba(255,255,255,0.7)}
.cmp-table tr:last-child td{border-bottom:none}
.cmp-g{color:#00D559;font-weight:700}
.cmp-r{color:rgba(255,80,80,0.6)}
.cmp-table tr:hover td{background:rgba(255,255,255,0.015)}
.cmp-save{margin-top:20px;display:inline-block;padding:8px 20px;border-radius:10px;
  background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.12);
  font-family:'Space Grotesk',sans-serif;font-size:0.72rem;font-weight:700;
  color:rgba(255,255,255,0.6)}
.cmp-save strong{color:#00D559}
@media(max-width:640px){.cmp-h{font-size:1.5rem}.cmp-table th,.cmp-table td{padding:9px 10px;font-size:0.65rem}}
</style>
<div class="cmp-wrap">
  <div class="cmp-badge">Side-by-Side</div>
  <div class="cmp-h">Why Sharps <span style="background:linear-gradient(135deg,#00D559,#2D9EFF);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Switch</span></div>
  <p class="cmp-sub">Feature-for-feature, no one comes close at any price</p>
  <table class="cmp-table">
    <thead><tr>
      <th>Feature</th><th>Smart Pick Pro</th><th>OddsJam</th><th>Action Network</th>
    </tr></thead>
    <tbody>
      <tr><td>Monthly Price</td><td class="cmp-g">$0 &ndash; $24.99</td><td class="cmp-r">$99/mo</td><td class="cmp-r">$59.99/mo</td></tr>
      <tr><td>AI Models</td><td class="cmp-g">6 Fused Models</td><td class="cmp-r">0</td><td class="cmp-r">0</td></tr>
      <tr><td>SAFE Confidence Score</td><td class="cmp-g">&#x2713;</td><td class="cmp-r">&#x2717;</td><td class="cmp-r">&#x2717;</td></tr>
      <tr><td>Live Sweat Tracker</td><td class="cmp-g">&#x2713;</td><td class="cmp-r">&#x2717;</td><td class="cmp-r">&#x2717;</td></tr>
      <tr><td>Auto-Graded Results</td><td class="cmp-g">&#x2713;</td><td class="cmp-r">&#x2717;</td><td class="cmp-r">&#x2717;</td></tr>
      <tr><td>Edge Detection</td><td class="cmp-g">&#x2713;</td><td class="cmp-r">Basic</td><td class="cmp-r">&#x2717;</td></tr>
      <tr><td>CLV Tracking</td><td class="cmp-g">92% Capture</td><td class="cmp-r">&#x2717;</td><td class="cmp-r">&#x2717;</td></tr>
      <tr><td>Bankroll Management</td><td class="cmp-g">&#x2713;</td><td class="cmp-r">&#x2717;</td><td class="cmp-r">Basic</td></tr>
      <tr><td>Backtesting</td><td class="cmp-g">&#x2713;</td><td class="cmp-r">&#x2717;</td><td class="cmp-r">&#x2717;</td></tr>
      <tr><td>DFS Platform Support</td><td class="cmp-g">PP + UD + DK</td><td>DK only</td><td class="cmp-r">&#x2717;</td></tr>
    </tbody>
  </table>
  <div class="cmp-save">You&rsquo;d pay <strong>$1,188/yr</strong> for OddsJam alone &mdash; and still not get SAFE Scores</div>
</div>
""")

    # ── Section anchor: FAQ ──
    st.markdown('<div id="sec-faq" data-section-id="faq" style="height:0;overflow:hidden;"></div>', unsafe_allow_html=True)

    # ── Below-fold: Performance, FAQ, CTA, Footer ─────────────
    st.html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;font-family:'Inter',sans-serif;color:rgba(255,255,255,0.7)}

@keyframes ftFadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes ftShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
@keyframes ftPulse{0%,100%{box-shadow:0 0 0 0 rgba(0,213,89,0.15)}50%{box-shadow:0 0 40px 12px rgba(0,213,89,0.06)}}
@keyframes ftBarGrow{from{height:4px}to{height:var(--h)}}

.em{background:linear-gradient(135deg,#00D559 0%,#2D9EFF 50%,#c084fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}

/* ── Performance section ── */
.ft-perf{margin:0 0 56px;animation:ftFadeUp 0.8s ease both}
.ft-perf-head{text-align:center;margin-bottom:28px}
.ft-perf-head::before{content:'';display:block;width:60px;height:4px;margin:0 auto 20px;background:linear-gradient(90deg,#00D559,#2D9EFF);border-radius:6px;background-size:200% 100%;animation:ftShimmer 4s ease infinite}
.ft-perf-head h2{font-family:'Space Grotesk',sans-serif;font-size:2.8rem;font-weight:800;color:#fff;margin:0 0 8px;letter-spacing:-0.04em}
.ft-perf-head p{font-size:0.88rem;color:rgba(255,255,255,0.35);margin:0}
.ft-perf-card{background:linear-gradient(168deg,rgba(10,16,32,0.95) 0%,rgba(8,12,24,0.98) 100%);border:1.5px solid rgba(0,213,89,0.1);border-radius:20px;padding:28px 24px 20px;position:relative;overflow:hidden}
.ft-perf-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#00D559,#2D9EFF);border-radius:3px 3px 0 0}
.ft-perf-stats{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.ft-perf-label{font-family:'Space Grotesk',sans-serif;font-size:0.85rem;font-weight:700;color:rgba(255,255,255,0.6)}
.ft-perf-val{display:flex;align-items:baseline;gap:8px}
.ft-perf-num{font-family:'JetBrains Mono',monospace;font-size:2rem;font-weight:800;color:#00D559;text-shadow:0 0 20px rgba(0,213,89,0.2)}
.ft-perf-tag{font-family:'JetBrains Mono',monospace;font-size:0.55rem;font-weight:700;color:#0B0F19;background:#00D559;padding:2px 8px;border-radius:100px}
.ft-bars{display:flex;align-items:flex-end;gap:4px;height:72px;width:100%}
.ft-bar{flex:1;border-radius:4px 4px 0 0;min-height:4px;transition:height 0.6s cubic-bezier(0.4,0,0.2,1);position:relative}
.ft-bar.w{background:linear-gradient(180deg,#00D559 0%,rgba(0,213,89,0.2) 100%)}
.ft-bar.w:hover{background:linear-gradient(180deg,#00ff66 0%,rgba(0,213,89,0.4) 100%);box-shadow:0 -4px 16px rgba(0,213,89,0.2)}
.ft-bar.l{background:linear-gradient(180deg,rgba(242,67,54,0.5) 0%,rgba(242,67,54,0.1) 100%)}
.ft-bar.l:hover{background:linear-gradient(180deg,rgba(242,67,54,0.7) 0%,rgba(242,67,54,0.2) 100%)}
.ft-bar-labels{display:flex;justify-content:space-between;margin-top:6px}
.ft-bar-labels span{font-family:'JetBrains Mono',monospace;font-size:0.48rem;color:rgba(255,255,255,0.15);font-weight:600}
.ft-perf-note{text-align:center;margin-top:12px;font-size:0.58rem;color:rgba(255,255,255,0.15);font-style:italic}

/* ── FAQ ── */
.ft-faq{margin:0 0 56px;animation:ftFadeUp 0.8s ease 0.2s both}
.ft-faq-head{text-align:center;margin-bottom:28px}
.ft-faq-head::before{content:'';display:block;width:60px;height:4px;margin:0 auto 20px;background:linear-gradient(90deg,#2D9EFF,#c084fc);border-radius:6px}
.ft-faq-head h2{font-family:'Space Grotesk',sans-serif;font-size:2.8rem;font-weight:800;color:#fff;margin:0 0 8px;letter-spacing:-0.04em}
.ft-faq-head p{font-size:0.88rem;color:rgba(255,255,255,0.35);margin:0}
.ft-qi{background:linear-gradient(168deg,rgba(10,16,32,0.95) 0%,rgba(8,12,24,0.98) 100%);border:1.5px solid rgba(0,213,89,0.06);border-radius:16px;margin-bottom:8px;overflow:hidden;transition:all 0.3s}
.ft-qi:hover{border-color:rgba(0,213,89,0.15);background:linear-gradient(168deg,rgba(12,18,34,0.95) 0%,rgba(10,14,28,0.98) 100%)}
.ft-qi summary{display:flex;align-items:center;justify-content:space-between;padding:20px 26px;cursor:pointer;font-family:'Space Grotesk',sans-serif;font-size:0.9rem;font-weight:700;color:rgba(255,255,255,0.6);list-style:none;transition:color 0.3s}
.ft-qi summary::-webkit-details-marker{display:none}
.ft-qi summary::marker{display:none;content:''}
.ft-qi summary:hover{color:rgba(255,255,255,0.85)}
.ft-qi summary .chevron{display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.12);color:#00D559;font-size:0.6rem;transition:all 0.3s;flex-shrink:0}
.ft-qi[open] summary .chevron{background:rgba(0,213,89,0.12);transform:rotate(180deg)}
.ft-qi[open] summary{color:#fff}
.ft-qi-ans{padding:0 26px 22px;font-size:0.78rem;color:rgba(255,255,255,0.45);line-height:1.75}

/* ── Final CTA ── */
.ft-cta{background:linear-gradient(168deg,rgba(0,213,89,0.08) 0%,rgba(10,16,32,0.97) 50%,rgba(8,12,24,0.99) 100%);border:2px solid rgba(0,213,89,0.25);border-radius:28px;padding:72px 40px;text-align:center;margin:0 0 36px;position:relative;overflow:hidden;animation:ftPulse 4s ease infinite;box-shadow:0 0 120px rgba(0,213,89,0.08) inset,0 32px 100px rgba(0,0,0,0.4)}
.ft-cta::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% 0%,rgba(0,213,89,0.1) 0%,transparent 50%);pointer-events:none}
.ft-cta::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,#00D559,#2D9EFF,#c084fc,transparent);background-size:200% 100%;animation:ftShimmer 3s ease infinite}
.ft-cta-h{font-family:'Space Grotesk',sans-serif;font-size:3.6rem;font-weight:800;color:#fff;margin:0 0 16px;letter-spacing:-0.05em;position:relative;line-height:1.1}
.ft-cta-s{font-size:1.02rem;color:rgba(255,255,255,0.5);margin:0 0 32px;line-height:1.7;position:relative;max-width:520px;margin-left:auto;margin-right:auto}
.ft-cta-btn{display:inline-block;font-family:'Space Grotesk',sans-serif;font-size:0.95rem;font-weight:800;color:#050910;background:linear-gradient(135deg,#00E865 0%,#00D559 45%,#00B74D 100%);padding:20px 62px;border-radius:12px;text-decoration:none;letter-spacing:0.07em;text-transform:uppercase;border:1px solid rgba(255,255,255,0.18);box-shadow:0 0 50px rgba(0,213,89,0.4),0 10px 40px rgba(0,213,89,0.22),inset 0 1px 0 rgba(255,255,255,0.22);position:relative;overflow:hidden;transition:all 0.3s cubic-bezier(0.16,1,0.3,1);cursor:pointer}
.ft-cta-btn::before{content:'';position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.22),transparent);transform:skewX(-20deg);transition:left 0.55s cubic-bezier(0.16,1,0.3,1)}
.ft-cta-btn:hover{transform:translateY(-5px) scale(1.01);background:linear-gradient(135deg,#00FF75 0%,#00E865 45%,#00C04B 100%);box-shadow:0 0 80px rgba(0,213,89,0.6),0 16px 60px rgba(0,213,89,0.32),inset 0 1px 0 rgba(255,255,255,0.25)}
.ft-cta-btn:hover::before{left:150%}
.ft-cta-trust{display:flex;justify-content:center;gap:18px;margin-top:20px;position:relative;flex-wrap:wrap}
.ft-cta-trust span{font-size:0.65rem;font-weight:600;color:rgba(255,255,255,0.2);display:flex;align-items:center;gap:4px}

/* ── Trust Strip ── */
.ft-trust{display:flex;justify-content:center;gap:24px;margin:0 0 8px;flex-wrap:wrap;animation:ftFadeUp 0.8s ease 0.5s both}
.ft-trust-item{font-size:0.65rem;font-weight:700;color:rgba(255,255,255,0.18);display:flex;align-items:center;gap:6px;background:rgba(255,255,255,0.015);border:1px solid rgba(255,255,255,0.04);padding:6px 14px;border-radius:100px}

/* ── Footer ── */
.ft-footer{text-align:center;padding:24px 0 48px;font-size:0.58rem;color:rgba(255,255,255,0.1);line-height:1.8;animation:ftFadeUp 0.8s ease 0.6s both}
.ft-footer a{color:rgba(255,255,255,0.15);text-decoration:underline;transition:color 0.3s}
.ft-footer a:hover{color:rgba(255,255,255,0.3)}
.ft-footer-line{width:60px;height:2px;margin:0 auto 16px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.06),transparent);border-radius:2px}

@media(max-width:520px){
  .ft-perf-head h2,.ft-faq-head h2{font-size:2rem}
  .ft-cta-h{font-size:2.4rem}
  .ft-cta{padding:44px 24px}
  .ft-cta-btn{padding:16px 40px;font-size:0.88rem}
  .ft-qi summary{padding:14px 16px;font-size:.76rem}
  .ft-qi-ans{padding:0 16px 14px;font-size:.7rem}
  .ft-cta-s{font-size:.85rem}
  .ft-trust{gap:10px}
  .ft-trust-item{font-size:.58rem;padding:4px 10px}
}
@media(max-width:380px){
  .ft-perf-head h2,.ft-faq-head h2{font-size:1.5rem}
  .ft-perf-head p,.ft-faq-head p{font-size:.78rem}
  .ft-cta-h{font-size:1.7rem}
  .ft-cta{padding:28px 14px;border-radius:18px}
  .ft-cta-btn{padding:14px 28px;font-size:.8rem;border-radius:10px}
  .ft-cta-s{font-size:.78rem}
  .ft-qi summary{padding:12px 12px;font-size:.7rem}
  .ft-qi-ans{padding:0 12px 12px;font-size:.66rem}
  .ft-qi summary .chevron{width:24px;height:24px;font-size:.5rem}
  .ft-perf-num{font-size:1.5rem}
  .ft-perf-card{padding:20px 14px 16px;border-radius:16px}
  .ft-trust-item{font-size:.52rem;padding:3px 8px}
}

/* ── Responsible Gaming ── */
.rg-section{text-align:center;padding:40px 20px 32px;margin:0 0 32px;
  border-top:1px solid rgba(255,255,255,0.04);border-bottom:1px solid rgba(255,255,255,0.04);
  animation:ftFadeUp 0.8s ease 0.5s both}
.rg-ico{font-size:1.6rem;margin-bottom:10px}
.rg-h{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:800;
  color:rgba(255,255,255,0.75);margin:0 0 10px}
.rg-p{font-family:'Inter',sans-serif;font-size:0.7rem;color:rgba(255,255,255,0.3);
  line-height:1.7;max-width:520px;margin:0 auto 16px}
.rg-links{display:flex;justify-content:center;gap:12px;flex-wrap:wrap}
.rg-link{display:inline-flex;align-items:center;gap:5px;padding:6px 14px;
  border-radius:10px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);
  font-family:'Space Grotesk',sans-serif;font-size:0.62rem;font-weight:600;
  color:rgba(255,255,255,0.35);text-decoration:none;transition:all 0.3s}
.rg-link:hover{border-color:rgba(255,255,255,0.12);color:rgba(255,255,255,0.55);
  background:rgba(255,255,255,0.04)}
</style>

<!-- Performance -->
<div class="ft-perf">
  <div class="ft-perf-head">
    <h2>Recent AI <span class="em">Performance</span></h2>
    <p>Last 14 days &mdash; SAFE Score 70+ picks only</p>
  </div>
  <div class="ft-perf-card">
    <div class="ft-perf-stats">
      <div class="ft-perf-label">Daily Win Rate</div>
      <div class="ft-perf-val">
        <span class="ft-perf-num">62.4%</span>
        <span class="ft-perf-tag">VERIFIED</span>
      </div>
    </div>
    <div class="ft-bars">
      <div class="ft-bar w" style="height:68%"></div>
      <div class="ft-bar w" style="height:54%"></div>
      <div class="ft-bar w" style="height:72%"></div>
      <div class="ft-bar l" style="height:38%"></div>
      <div class="ft-bar w" style="height:80%"></div>
      <div class="ft-bar w" style="height:62%"></div>
      <div class="ft-bar w" style="height:58%"></div>
      <div class="ft-bar l" style="height:42%"></div>
      <div class="ft-bar w" style="height:76%"></div>
      <div class="ft-bar w" style="height:64%"></div>
      <div class="ft-bar w" style="height:70%"></div>
      <div class="ft-bar w" style="height:60%"></div>
      <div class="ft-bar l" style="height:35%"></div>
      <div class="ft-bar w" style="height:74%"></div>
    </div>
    <div class="ft-bar-labels"><span>14d ago</span><span>7d ago</span><span>Today</span></div>
  </div>
  <div class="ft-perf-note">Win rate calculated from all SAFE 70+ picks tracked in the public Bet Tracker</div>
</div>

<!-- FAQ -->
<div class="ft-faq">
  <div class="ft-faq-head">
    <h2>Got <span class="em">Questions?</span></h2>
    <p>We&rsquo;ve got answers</p>
  </div>

  <details class="ft-qi">
    <summary>Is it really free? What&rsquo;s the catch? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">No catch. Smart Rookie gives you 10 AI-analyzed props, Live Sweat, Live Games, and SAFE Scores &mdash; free forever, no credit card required. We make money from optional upgrades (Sharp IQ &amp; Smart Money), not from locking basic features behind paywalls.</div>
  </details>

  <details class="ft-qi">
    <summary>How does the AI actually work? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">Our Quantum Analysis Matrix fuses 6 independent AI models &mdash; each trained on different data (player logs, matchup DNA, pace projections, defensive ratings, line movement, and injury impact). They vote on every prop and produce a SAFE Score from 0&ndash;100. Higher score = higher confidence = bigger edge.</div>
  </details>

  <details class="ft-qi">
    <summary>Can I cancel anytime? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">Absolutely. Sharp IQ and Smart Money are month-to-month with no commitment. Cancel from your Settings page in one click &mdash; no emails, no phone calls, no guilt trips. Your data stays yours.</div>
  </details>

  <details class="ft-qi">
    <summary>What platforms do you support? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">Our AI analyzes props from PrizePicks, DraftKings Pick6, Underdog Fantasy, and more. You can also manually enter any prop from any platform into the Prop Scanner for instant AI analysis.</div>
  </details>

  <details class="ft-qi">
    <summary>How is this better than OddsJam / Action Network? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">Those tools charge $60&ndash;$300/mo for basic odds comparison. Smart Pick Pro gives you 6 fused AI models, SAFE Scores, real-time live tracking, edge detection, bankroll tools, and backtesting &mdash; for free. They literally cannot compete on features or price.</div>
  </details>

  <details class="ft-qi">
    <summary>How often are picks updated? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">New AI-analyzed props drop every day at 5 PM ET, as soon as sportsbooks post their lines. SAFE Scores and projections continue to adjust in real time as injury reports, lineup confirmations, and line movement come in &mdash; right up until tip-off.</div>
  </details>

  <details class="ft-qi">
    <summary>Do you support parlays and multi-leg slips? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">Yes. Our Parlay Optimizer analyzes correlation between legs and calculates true expected value for your combos. You can also paste your full PrizePicks slip and get an instant AI score for the entire entry &mdash; not just individual legs.</div>
  </details>

  <details class="ft-qi">
    <summary>What sports do you cover? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">We currently cover the NBA with deep AI modeling (300+ features per prop). MLB, NFL, and NHL modules are on the roadmap. Our AI architecture is sport-agnostic &mdash; the same ensemble pipeline will extend to new leagues as we expand.</div>
  </details>

  <details class="ft-qi">
    <summary>How fast does the AI generate picks? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">Our 6-model ensemble runs a full analysis of 300+ props in under 30 seconds. When you load the Prop Scanner, every prop already has a SAFE Score, edge %, win probability, projection, and matchup note &mdash; no waiting, no spinning wheels.</div>
  </details>

  <details class="ft-qi">
    <summary>Is my data and payment info safe? <span class="chevron">&#x25BC;</span></summary>
    <div class="ft-qi-ans">100%. All payments are processed through Stripe &mdash; we never see or store your card number. Your account data is encrypted with 256-bit TLS, and we will never sell, share, or monetize your personal information. Period.</div>
  </details>
</div>

<!-- Final CTA -->
<div class="ft-cta">
  <div class="ft-cta-h">Ready to <span class="em">Beat the Books?</span></div>
  <p class="ft-cta-s">Join thousands of sharps using AI to find edges the books don&rsquo;t want you to see.</p>
  <a class="ft-cta-btn" href="?auth=signup">&#x26A1; Create Free Account</a>
  <div class="ft-cta-trust">
    <span>&#x1F512; No credit card</span>
    <span>&#x23F1;&#xFE0F; 10 second signup</span>
    <span>&#x1F6AB; Never sell your data</span>
  </div>
</div>

<!-- Trust -->
<div class="ft-trust">
  <span class="ft-trust-item">&#x1F512; 256-bit Encrypted</span>
  <span class="ft-trust-item">&#x1F4B3; No Credit Card</span>
  <span class="ft-trust-item">&#x1F6AB; Never Sell Data</span>
</div>

<!-- Responsible Gaming -->
<div class="rg-section">
  <div class="rg-ico">&#x1F6E1;&#xFE0F;</div>
  <div class="rg-h">Responsible Gaming</div>
  <p class="rg-p">
    Smart Pick Pro is a data and analytics tool for entertainment and educational purposes.
    We encourage responsible play. If you or someone you know has a gambling problem,
    help is available 24/7.
  </p>
  <div class="rg-links">
    <a class="rg-link" href="https://www.ncpgambling.org/" target="_blank" rel="noopener">
      &#x1F4DE; 1-800-GAMBLER</a>
    <a class="rg-link" href="https://www.ncpgambling.org/help-treatment/chat/" target="_blank" rel="noopener">
      &#x1F4AC; Live Chat Help</a>
    <a class="rg-link" href="https://www.ncpgambling.org/" target="_blank" rel="noopener">
      &#x1F310; NCPG Resources</a>
  </div>
</div>

<!-- Footer -->
<div class="ft-footer">
  <div class="ft-footer-line"></div>
  <div style="display:flex;justify-content:center;gap:16px;margin-bottom:10px;flex-wrap:wrap">
    <a href="javascript:void(0)" style="color:rgba(255,255,255,0.25);font-size:0.62rem;text-decoration:none;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:1px;transition:color 0.3s" onmouseover="this.style.color='rgba(255,255,255,0.5)'" onmouseout="this.style.color='rgba(255,255,255,0.25)'">Terms of Service</a>
    <a href="javascript:void(0)" style="color:rgba(255,255,255,0.25);font-size:0.62rem;text-decoration:none;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:1px;transition:color 0.3s" onmouseover="this.style.color='rgba(255,255,255,0.5)'" onmouseout="this.style.color='rgba(255,255,255,0.25)'">Privacy Policy</a>
    <a href="mailto:support@smartpickpro.ai" style="color:rgba(255,255,255,0.25);font-size:0.62rem;text-decoration:none;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:1px;transition:color 0.3s" onmouseover="this.style.color='rgba(255,255,255,0.5)'" onmouseout="this.style.color='rgba(255,255,255,0.25)'">Contact</a>
    <a href="https://www.ncpgambling.org/" target="_blank" style="color:rgba(255,255,255,0.25);font-size:0.62rem;text-decoration:none;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:1px;transition:color 0.3s" onmouseover="this.style.color='rgba(255,255,255,0.5)'" onmouseout="this.style.color='rgba(255,255,255,0.25)'">Responsible Gaming</a>
  </div>
  &copy; 2026 Smart Pick Pro &middot; All rights reserved.<br>
  For entertainment &amp; educational purposes only &middot; 21+ &middot; <a href="https://www.ncpgambling.org/" target="_blank">1-800-GAMBLER</a><br>
  <span style="font-size:0.5rem;color:rgba(255,255,255,0.06);margin-top:6px;display:inline-block">Smart Pick Pro is not affiliated with any sportsbook or DFS platform.</span>
</div>
""")

    return False
