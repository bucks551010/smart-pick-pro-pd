# ============================================================
# FILE: utils/analytics.py
# PURPOSE: Unified analytics layer for Smart Pick Pro.
#
#   1. Client-side: Google Analytics 4 (GA4) injection into the
#      Streamlit parent frame via st.html() script injection.
#   2. Server-side: Lightweight event tracking persisted to SQLite
#      for product analytics (page views, feature usage, funnels).
#
# USAGE:
#   from utils.analytics import inject_ga4, track_event, track_page_view
#
#   inject_ga4()                             # once per page render
#   track_event("analysis_run", {"model": "quantum", "picks": 12})
#   track_page_view("Prop Scanner")
# ============================================================

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

import streamlit as st

_logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "")


# ══════════════════════════════════════════════════════════════
# SECTION 1: Google Analytics 4 — Client-Side
# ══════════════════════════════════════════════════════════════

def inject_ga4() -> None:
    """Inject GA4 gtag.js into the Streamlit parent frame.

    Call once at the top of each page (after st.set_page_config).
    Uses the same parent-injection pattern as the auth gate nav JS:
    creates a <script> element and appends it to window.parent.document.head.

    No-ops if GA_MEASUREMENT_ID env var is not set.
    """
    ga_id = GA_MEASUREMENT_ID
    if not ga_id:
        return

    # Prevent double-injection within the same page render
    if st.session_state.get("_ga4_injected"):
        return
    st.session_state["_ga4_injected"] = True

    try:
        st.html(f"""<script>
(function() {{
  var pdoc = window.parent.document;
  if (pdoc.getElementById('spp-ga4')) return;

  // gtag.js loader
  var g = pdoc.createElement('script');
  g.id = 'spp-ga4';
  g.async = true;
  g.src = 'https://www.googletagmanager.com/gtag/js?id={ga_id}';
  pdoc.head.appendChild(g);

  // gtag config
  var s = pdoc.createElement('script');
  s.textContent = `
    window.dataLayer = window.dataLayer || [];
    function gtag(){{ dataLayer.push(arguments); }}
    gtag('js', new Date());
    gtag('config', '{ga_id}', {{
      page_location: window.parent.location.href,
      cookie_flags: 'SameSite=None;Secure'
    }});
  `;
  pdoc.head.appendChild(s);

  // Expose gtag globally for custom event firing from other st.html blocks
  window.parent.__spp_gtag = function() {{
    if (window.parent.gtag) window.parent.gtag.apply(null, arguments);
  }};
}})();
</script>""")
    except Exception as _ga4_exc:
        _logger.debug("GA4 inject_ga4 failed (non-fatal): %s", _ga4_exc)


def ga4_event(event_name: str, params: dict[str, Any] | None = None) -> None:
    """Fire a custom GA4 event from the server side via st.html injection.

    Use for high-value actions: signups, logins, analysis runs, prop clicks.
    """
    ga_id = GA_MEASUREMENT_ID
    if not ga_id:
        return
    params_json = json.dumps(params or {})
    try:
        st.html(f"""<script>
(function() {{
  var fn = window.parent.__spp_gtag || window.parent.gtag;
  if (fn) fn('event', '{event_name}', {params_json});
}})();
</script>""")
    except Exception as _ga4_evt_exc:
        _logger.debug("GA4 ga4_event '%s' failed (non-fatal): %s", event_name, _ga4_evt_exc)


# ══════════════════════════════════════════════════════════════
# SECTION 2: Server-Side Event Tracking (SQLite)
# ══════════════════════════════════════════════════════════════

_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analytics_events (
    event_id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    session_id TEXT,
    user_email TEXT,
    event_name TEXT NOT NULL,
    page TEXT,
    event_data TEXT,
    ip_hash TEXT,
    user_agent TEXT
);
"""

_EVENTS_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_ae_timestamp ON analytics_events (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_ae_event_name ON analytics_events (event_name)",
    "CREATE INDEX IF NOT EXISTS idx_ae_user ON analytics_events (user_email)",
    "CREATE INDEX IF NOT EXISTS idx_ae_page ON analytics_events (page)",
]

_table_ensured = False


def _ensure_table() -> None:
    """Create analytics_events table if it doesn't exist (idempotent)."""
    global _table_ensured
    if _table_ensured:
        return
    try:
        from tracking.database import _db_write, initialize_database
        initialize_database()
        _db_write(_EVENTS_TABLE_SQL.strip(), caller="analytics_ensure_table")
        for idx_sql in _EVENTS_INDEXES_SQL:
            _db_write(idx_sql, caller="analytics_ensure_index")
        _table_ensured = True
    except Exception as exc:
        _logger.debug("analytics table creation skipped: %s", exc)


def _get_session_id() -> str:
    """Return a stable session identifier for the current Streamlit session."""
    key = "_analytics_session_id"
    if key not in st.session_state:
        import secrets
        st.session_state[key] = secrets.token_hex(8)
    return st.session_state[key]


def _get_user_email() -> str:
    """Get the currently logged-in user's email (empty if not logged in)."""
    return st.session_state.get("_auth_user_email", "")


def track_event(
    event_name: str,
    data: dict[str, Any] | None = None,
    *,
    page: str | None = None,
) -> None:
    """Record a server-side analytics event.

    Parameters
    ----------
    event_name : str
        Short snake_case name, e.g. "analysis_run", "prop_click", "login".
    data : dict, optional
        Arbitrary JSON-serializable payload (model used, pick count, etc.).
    page : str, optional
        Override auto-detected page name.
    """
    _ensure_table()
    try:
        from tracking.database import _db_write
        now = datetime.now(timezone.utc).isoformat()
        session_id = _get_session_id()
        user_email = _get_user_email()
        event_json = json.dumps(data) if data else None

        _db_write(
            """INSERT INTO analytics_events
               (timestamp, session_id, user_email, event_name, page, event_data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (now, session_id, user_email or None, event_name, page, event_json),
            caller="track_event",
        )
    except Exception as exc:
        _logger.debug("analytics track_event failed: %s", exc)


def track_page_view(page_name: str) -> None:
    """Record a page view. Call once at the top of each page."""
    # Deduplicate within same session + page
    key = f"_av_{page_name}"
    if st.session_state.get(key):
        return
    st.session_state[key] = True
    track_event("page_view", {"page_name": page_name}, page=page_name)


def track_login(email: str, method: str = "password") -> None:
    """Record a login event."""
    track_event("login", {"method": method}, page="auth_gate")
    ga4_event("login", {"method": method})


def track_signup(email: str) -> None:
    """Record a signup event."""
    track_event("signup", {"email_domain": email.split("@")[-1] if "@" in email else ""}, page="auth_gate")
    ga4_event("sign_up", {"method": "email"})


def track_analysis_run(model: str, pick_count: int, platform: str = "") -> None:
    """Record an analysis/prediction run."""
    track_event("analysis_run", {
        "model": model,
        "pick_count": pick_count,
        "platform": platform,
    }, page="Quantum Analysis")
    ga4_event("analysis_run", {"model": model, "pick_count": pick_count})


def track_prop_view(player: str, stat_type: str, platform: str = "") -> None:
    """Record a prop being viewed/expanded."""
    track_event("prop_view", {
        "player": player,
        "stat_type": stat_type,
        "platform": platform,
    }, page="Prop Scanner")


def track_bet_logged(player: str, stat_type: str, platform: str = "", source: str = "manual") -> None:
    """Record a bet being logged."""
    track_event("bet_logged", {
        "player": player,
        "stat_type": stat_type,
        "platform": platform,
        "source": source,
    }, page="Bet Tracker")


def track_feature_use(feature_name: str, details: dict[str, Any] | None = None) -> None:
    """Generic feature usage tracker for miscellaneous actions."""
    track_event("feature_use", {"feature": feature_name, **(details or {})})


# ══════════════════════════════════════════════════════════════
# SECTION 3: Admin Reporting Helpers
# ══════════════════════════════════════════════════════════════

def get_event_counts(days: int = 30) -> dict[str, int]:
    """Return event counts grouped by event_name for the last N days."""
    _ensure_table()
    try:
        from tracking.database import _db_read
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        rows = _db_read(
            """SELECT event_name, COUNT(*) as cnt
               FROM analytics_events
               WHERE timestamp >= ?
               GROUP BY event_name
               ORDER BY cnt DESC""",
            (cutoff,),
        )
        return {row["event_name"]: row["cnt"] for row in rows}
    except Exception:
        return {}


def get_daily_active_users(days: int = 30) -> list[dict]:
    """Return daily active user counts."""
    _ensure_table()
    try:
        from tracking.database import _db_read
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        rows = _db_read(
            """SELECT CAST(timestamp AS DATE) as day,
                      COUNT(DISTINCT session_id) as sessions,
                      COUNT(DISTINCT user_email) as users
               FROM analytics_events
               WHERE timestamp >= ?
               GROUP BY day
               ORDER BY day DESC""",
            (cutoff,),
        )
        return rows
    except Exception:
        return []


def get_page_views(days: int = 30) -> dict[str, int]:
    """Return page view counts grouped by page name."""
    _ensure_table()
    try:
        from tracking.database import _db_read
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        rows = _db_read(
            """SELECT page, COUNT(*) as cnt
               FROM analytics_events
               WHERE event_name = 'page_view'
                 AND timestamp >= ?
               GROUP BY page
               ORDER BY cnt DESC""",
            (cutoff,),
        )
        return {row["page"]: row["cnt"] for row in rows}
    except Exception:
        return {}


def get_funnel(days: int = 30) -> dict[str, int]:
    """Return a simple acquisition funnel: page_view → signup → login → analysis_run."""
    _ensure_table()
    try:
        from tracking.database import _db_read
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]
        funnel = {}
        for step in ("page_view", "signup", "login", "analysis_run", "bet_logged"):
            rows = _db_read(
                """SELECT COUNT(DISTINCT session_id) as cnt
                   FROM analytics_events
                   WHERE event_name = ?
                     AND timestamp >= ?""",
                (step, cutoff),
            )
            funnel[step] = rows[0]["cnt"] if rows else 0
        return funnel
    except Exception:
        return {}
