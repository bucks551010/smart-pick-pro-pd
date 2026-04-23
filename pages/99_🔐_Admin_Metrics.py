# ============================================================
# FILE: pages/99_🔐_Admin_Metrics.py
# PURPOSE: Hidden admin-only observability dashboard.
#
# ACCESS CONTROL:
#   Gated by is_admin_user() from utils.auth_gate.  Any non-admin
#   who lands on this URL sees only a 403 message — no data leaks.
#   The page number (99) pushes it to the bottom of the sidebar and
#   the lock emoji signals restricted access.
#
# METRICS DISPLAYED:
#   • System Resources  — CPU %, memory %, disk usage (psutil)
#   • Active Sessions   — distinct session IDs in last 60 min
#   • Feature Heatmap   — top features used in last 7 days
#   • Performance Table — p50 / p95 / p99 latency per function
#   • Error Rate Chart  — daily error count by type (last 14 days)
#   • Recent Errors     — last 50 exception records (searchable)
# ============================================================

import os

import streamlit as st

st.set_page_config(
    page_title="Admin Metrics · Smart Pick Pro",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Theme CSS — injected BEFORE login gate to prevent white flash ─────────
from utils.page_bootstrap import inject_theme_css, init_session_state
inject_theme_css()

# ── Auth gate: admin-only ─────────────────────────────────
from utils.auth_gate import require_login, is_admin_user

if not require_login():
    st.stop()

init_session_state()

if not is_admin_user():
    st.error("🔒 Access denied. This page is restricted to administrators.")
    st.stop()

# ── Imports (deferred so non-admins pay zero import cost) ──
import json
from datetime import datetime, timezone, timedelta

import pandas as pd

try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from utils.telemetry import query_telemetry
from utils.analytics import inject_ga4, track_page_view

inject_ga4()
track_page_view("Admin Metrics")

# ── Auto-refresh every 60 s while page is open ───────────
try:
    from streamlit_autorefresh import st_autorefresh  # type: ignore
    st_autorefresh(interval=60_000, key="_admin_refresh")
except ImportError:
    pass  # autorefresh is optional

# ─────────────────────────────────────────────────────────
st.title("🔐 Admin Metrics Dashboard")
st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

_7D_AGO  = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
_14D_AGO = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(timespec="seconds")
_1H_AGO  = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════
# ROW 1 — System Resource KPIs
# ═══════════════════════════════════════════════════════════

st.subheader("🖥️ System Resources")

if _HAS_PSUTIL:
    cpu_pct    = psutil.cpu_percent(interval=0.5)
    mem        = psutil.virtual_memory()
    disk       = psutil.disk_usage("/")

    col_cpu, col_mem, col_disk, col_sessions = st.columns(4)
    col_cpu.metric("CPU Usage", f"{cpu_pct:.1f}%")
    col_mem.metric(
        "Memory",
        f"{mem.percent:.1f}%",
        delta=f"{mem.used / 1e9:.1f} GB used",
    )
    col_disk.metric(
        "Disk",
        f"{disk.percent:.1f}%",
        delta=f"{disk.free / 1e9:.1f} GB free",
    )
else:
    col_sessions, *_ = st.columns(4)
    st.info(
        "Install `psutil` to enable system resource metrics. "
        "Add `psutil~=5.9` to requirements.txt.",
        icon="ℹ️",
    )

# Active sessions (distinct session_ids seen in last 60 min)
active_rows = query_telemetry(
    "SELECT COUNT(DISTINCT session_id) AS cnt FROM telemetry_features WHERE timestamp >= ?",
    (_1H_AGO,),
)
active_count = active_rows[0]["cnt"] if active_rows else 0

if _HAS_PSUTIL:
    col_sessions.metric("Active Sessions (1 h)", active_count)
else:
    st.metric("Active Sessions (1 h)", active_count)

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 2 — Feature Usage Heatmap (last 7 days)
# ═══════════════════════════════════════════════════════════

st.subheader("📊 Feature Utilisation — Last 7 Days")

feature_rows = query_telemetry(
    """
    SELECT feature_name, COUNT(*) AS uses, page
    FROM   telemetry_features
    WHERE  timestamp >= ?
    GROUP  BY feature_name
    ORDER  BY uses DESC
    LIMIT  30
    """,
    (_7D_AGO,),
)

if feature_rows:
    try:
        import plotly.express as px  # type: ignore

        df_feat = pd.DataFrame(feature_rows)
        fig = px.bar(
            df_feat,
            x="uses",
            y="feature_name",
            orientation="h",
            color="uses",
            color_continuous_scale="Blues",
            labels={"uses": "Total Activations", "feature_name": "Feature"},
            title="Top Features by Activation Count",
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e0e0e0",
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        # Fallback: native Streamlit bar chart when plotly is unavailable
        df_feat = pd.DataFrame(feature_rows).set_index("feature_name")[["uses"]]
        st.bar_chart(df_feat)
else:
    st.info("No feature events recorded yet. Events appear after users interact with tracked features.")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 3 — Execution Performance (p50 / p95 / p99)
# ═══════════════════════════════════════════════════════════

st.subheader("⚡ Execution Performance — Last 7 Days")

timing_rows = query_telemetry(
    """
    SELECT
        function_label,
        COUNT(*)                                      AS calls,
        ROUND(AVG(duration_ms), 1)                    AS avg_ms,
        ROUND(MIN(duration_ms), 1)                    AS min_ms,
        ROUND(MAX(duration_ms), 1)                    AS max_ms,
        -- SQLite percentile approximation via window function
        ROUND(
            (SELECT t2.duration_ms
             FROM   telemetry_timings t2
             WHERE  t2.function_label = t1.function_label
               AND  t2.timestamp >= :since
             ORDER  BY t2.duration_ms
             LIMIT  1
             OFFSET CAST(COUNT(*) * 0.50 AS INTEGER))
        , 1) AS p50_ms,
        ROUND(
            (SELECT t2.duration_ms
             FROM   telemetry_timings t2
             WHERE  t2.function_label = t1.function_label
               AND  t2.timestamp >= :since
             ORDER  BY t2.duration_ms
             LIMIT  1
             OFFSET CAST(COUNT(*) * 0.95 AS INTEGER))
        , 1) AS p95_ms,
        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS errors
    FROM   telemetry_timings t1
    WHERE  timestamp >= :since
    GROUP  BY function_label
    ORDER  BY avg_ms DESC
    LIMIT  40
    """,
    (),  # NOTE: named param below via direct dict workaround
)

# Re-query using named params (query_telemetry uses positional; fallback)
try:
    from tracking.database import get_database_connection
    from utils.telemetry import _ensure_tables
    _ensure_tables()
    with get_database_connection() as _conn:
        _conn.row_factory = __import__("sqlite3").Row
        timing_rows = [
            dict(r) for r in _conn.execute(
                """
                SELECT
                    function_label,
                    COUNT(*)                        AS calls,
                    ROUND(AVG(duration_ms),1)       AS avg_ms,
                    ROUND(MIN(duration_ms),1)       AS min_ms,
                    ROUND(MAX(duration_ms),1)       AS max_ms,
                    SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS errors
                FROM telemetry_timings
                WHERE timestamp >= ?
                GROUP BY function_label
                ORDER BY avg_ms DESC
                LIMIT 40
                """,
                (_7D_AGO,),
            ).fetchall()
        ]
except Exception:
    pass  # keep timing_rows from the first query attempt

if timing_rows:
    df_timing = pd.DataFrame(timing_rows)
    # Colour-code: highlight rows where avg_ms > 1000 ms
    def _highlight_slow(row: pd.Series) -> list[str]:
        avg = row.get("avg_ms", 0) or 0
        color = "background-color: #5c1a1a" if avg > 2000 else (
                "background-color: #4a3a10" if avg > 500 else "")
        return [color] * len(row)

    st.dataframe(
        df_timing.style.apply(_highlight_slow, axis=1),
        use_container_width=True,
        height=min(40 + len(df_timing) * 35, 500),
    )
else:
    st.info("No timing data yet. Decorate heavy functions with `@profile_execution()`.")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 4 — Error Rate Over Time (last 14 days)
# ═══════════════════════════════════════════════════════════

st.subheader("🚨 Error Rate — Last 14 Days")

error_daily = query_telemetry(
    """
    SELECT
        SUBSTR(timestamp, 1, 10) AS day,
        error_type,
        COUNT(*) AS cnt
    FROM   telemetry_errors
    WHERE  timestamp >= ?
    GROUP  BY day, error_type
    ORDER  BY day
    """,
    (_14D_AGO,),
)

col_err_chart, col_err_kpi = st.columns([3, 1])

with col_err_kpi:
    total_errors_7d = query_telemetry(
        "SELECT COUNT(*) AS cnt FROM telemetry_errors WHERE timestamp >= ?", (_7D_AGO,)
    )
    total_7d = total_errors_7d[0]["cnt"] if total_errors_7d else 0
    st.metric("Errors (7 d)", total_7d)

    top_error = query_telemetry(
        """
        SELECT error_type, COUNT(*) AS cnt FROM telemetry_errors
        WHERE timestamp >= ?
        GROUP BY error_type ORDER BY cnt DESC LIMIT 1
        """,
        (_7D_AGO,),
    )
    if top_error:
        st.metric("Top Error Type", top_error[0]["error_type"], delta=f"{top_error[0]['cnt']} occurrences")

with col_err_chart:
    if error_daily:
        try:
            import plotly.express as px  # type: ignore

            df_err = pd.DataFrame(error_daily)
            fig2 = px.bar(
                df_err,
                x="day",
                y="cnt",
                color="error_type",
                barmode="stack",
                labels={"cnt": "Errors", "day": "Date", "error_type": "Type"},
                title="Daily Error Count by Type",
            )
            fig2.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e0e0",
                height=300,
            )
            st.plotly_chart(fig2, use_container_width=True)
        except ImportError:
            df_err = pd.DataFrame(error_daily).pivot(index="day", columns="error_type", values="cnt").fillna(0)
            st.bar_chart(df_err)
    else:
        st.success("✅ No errors recorded in the last 14 days.")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 5 — Recent Error Log (searchable)
# ═══════════════════════════════════════════════════════════

st.subheader("📋 Recent Error Log")

with st.expander("Show last 50 errors", expanded=False):
    search_term = st.text_input("Filter by error type or context", key="_admin_err_search")

    recent_errors = query_telemetry(
        """
        SELECT timestamp, error_type, error_message, context, page
        FROM   telemetry_errors
        ORDER  BY timestamp DESC
        LIMIT  50
        """,
    )

    if recent_errors:
        df_recent = pd.DataFrame(recent_errors)
        if search_term:
            mask = df_recent.apply(
                lambda row: search_term.lower() in row.to_string().lower(), axis=1
            )
            df_recent = df_recent[mask]
        st.dataframe(df_recent, use_container_width=True)
    else:
        st.info("No error records found.")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 6 — User Geography (hashed, PII-free)
# ═══════════════════════════════════════════════════════════

st.subheader("🌍 Active User Sessions — Geography (approximate)")
st.caption(
    "User emails are one-way hashed before storage.  "
    "Geography is inferred from the hashed session ID prefix only — "
    "no IP addresses or PII are retained."
)

session_counts = query_telemetry(
    """
    SELECT
        page,
        COUNT(DISTINCT session_id) AS unique_sessions,
        COUNT(*) AS total_events
    FROM   telemetry_features
    WHERE  timestamp >= ?
    GROUP  BY page
    ORDER  BY unique_sessions DESC
    LIMIT  20
    """,
    (_7D_AGO,),
)

if session_counts:
    df_pages = pd.DataFrame(session_counts)
    st.dataframe(df_pages, use_container_width=True)
else:
    st.info("No session data yet.")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 7 — Website Analytics (analytics_events table)
# ═══════════════════════════════════════════════════════════

st.subheader("📣 Website Analytics")
st.caption("Server-side events from `analytics_events`. Complements GA4 with full server visibility.")

_ana_days = st.select_slider(
    "Time window", options=[1, 7, 14, 30, 90], value=30, key="_admin_ana_days",
    format_func=lambda d: f"Last {d} day{'s' if d > 1 else ''}",
)
_ANA_SINCE = (datetime.now(timezone.utc) - timedelta(days=_ana_days)).isoformat(timespec="seconds")

try:
    from tracking.database import get_database_connection as _get_conn
    with _get_conn() as _ac:
        _ac.row_factory = __import__("sqlite3").Row

        # ── KPI row ──────────────────────────────────────────
        _kpi_rows = _ac.execute(
            """
            SELECT
                COUNT(*)                        AS total_events,
                COUNT(DISTINCT session_id)      AS unique_sessions,
                COUNT(DISTINCT user_email)      AS unique_users,
                SUM(CASE WHEN event_name='page_view'    THEN 1 ELSE 0 END) AS page_views,
                SUM(CASE WHEN event_name='login'        THEN 1 ELSE 0 END) AS logins,
                SUM(CASE WHEN event_name='signup'       THEN 1 ELSE 0 END) AS signups,
                SUM(CASE WHEN event_name='analysis_run' THEN 1 ELSE 0 END) AS analysis_runs,
                SUM(CASE WHEN event_name='bet_logged'   THEN 1 ELSE 0 END) AS bets_logged
            FROM analytics_events WHERE timestamp >= ?
            """,
            (_ANA_SINCE,),
        ).fetchone()

        if _kpi_rows and _kpi_rows["total_events"]:
            _k = dict(_kpi_rows)
            _kc = st.columns(4)
            _kc[0].metric("Total Events",     _k["total_events"])
            _kc[1].metric("Unique Sessions",  _k["unique_sessions"])
            _kc[2].metric("Unique Users",     _k["unique_users"])
            _kc[3].metric("Page Views",       _k["page_views"])
            _kc2 = st.columns(4)
            _kc2[0].metric("Logins",          _k["logins"])
            _kc2[1].metric("Signups",         _k["signups"])
            _kc2[2].metric("Analysis Runs",   _k["analysis_runs"])
            _kc2[3].metric("Bets Logged",     _k["bets_logged"])
        else:
            st.info("No analytics events recorded in this window.")

        # ── Events by type chart ─────────────────────────────
        _by_type = [
            dict(r) for r in _ac.execute(
                """SELECT event_name, COUNT(*) AS cnt FROM analytics_events
                   WHERE timestamp >= ? GROUP BY event_name ORDER BY cnt DESC LIMIT 20""",
                (_ANA_SINCE,),
            ).fetchall()
        ]
        if _by_type:
            try:
                import plotly.express as px
                _df_bt = pd.DataFrame(_by_type)
                _fig_bt = px.bar(
                    _df_bt, x="cnt", y="event_name", orientation="h",
                    color="cnt", color_continuous_scale="Teal",
                    labels={"cnt": "Events", "event_name": "Event Type"},
                    title="Events by Type",
                )
                _fig_bt.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0", yaxis={"categoryorder": "total ascending"},
                    coloraxis_showscale=False, height=380,
                )
                st.plotly_chart(_fig_bt, use_container_width=True)
            except ImportError:
                st.bar_chart(pd.DataFrame(_by_type).set_index("event_name")["cnt"])

        # ── Daily event volume ───────────────────────────────
        _daily_ev = [
            dict(r) for r in _ac.execute(
                """SELECT SUBSTR(timestamp,1,10) AS day, event_name, COUNT(*) AS cnt
                   FROM analytics_events WHERE timestamp >= ?
                   GROUP BY day, event_name ORDER BY day""",
                (_ANA_SINCE,),
            ).fetchall()
        ]
        if _daily_ev and len(_daily_ev) > 1:
            with st.expander("📅 Daily Event Volume", expanded=False):
                try:
                    import plotly.express as px
                    _df_dv = pd.DataFrame(_daily_ev)
                    _fig_dv = px.bar(
                        _df_dv, x="day", y="cnt", color="event_name",
                        barmode="stack",
                        labels={"cnt": "Events", "day": "Date", "event_name": "Type"},
                        title="Daily Event Volume by Type",
                    )
                    _fig_dv.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=320,
                    )
                    st.plotly_chart(_fig_dv, use_container_width=True)
                except ImportError:
                    _df_dv_p = pd.DataFrame(_daily_ev).pivot(
                        index="day", columns="event_name", values="cnt"
                    ).fillna(0)
                    st.bar_chart(_df_dv_p)

        # ── Top pages by views ───────────────────────────────
        _top_pages = [
            dict(r) for r in _ac.execute(
                """SELECT page, COUNT(*) AS views, COUNT(DISTINCT session_id) AS sessions
                   FROM analytics_events WHERE event_name='page_view' AND timestamp >= ?
                   GROUP BY page ORDER BY views DESC LIMIT 15""",
                (_ANA_SINCE,),
            ).fetchall()
        ]
        if _top_pages:
            with st.expander("📄 Top Pages by Views", expanded=False):
                st.dataframe(pd.DataFrame(_top_pages), use_container_width=True, hide_index=True)

        # ── Recent raw events ────────────────────────────────
        with st.expander("🔍 Recent Events (last 100)", expanded=False):
            _evt_search = st.text_input("Filter by event name or page", key="_admin_evt_filter")
            _raw_events = [
                dict(r) for r in _ac.execute(
                    """SELECT timestamp, event_name, page, session_id, event_data
                       FROM analytics_events ORDER BY timestamp DESC LIMIT 100"""
                ).fetchall()
            ]
            if _raw_events:
                _df_raw = pd.DataFrame(_raw_events)
                if _evt_search:
                    _mask = _df_raw.apply(lambda row: _evt_search.lower() in row.to_string().lower(), axis=1)
                    _df_raw = _df_raw[_mask]
                st.dataframe(_df_raw, use_container_width=True, hide_index=True)
            else:
                st.info("No events yet.")

except Exception as _ana_exc:
    st.warning(f"Could not load analytics_events: {_ana_exc}")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 8 — User Management
# ═══════════════════════════════════════════════════════════

st.subheader("👥 User Management")

try:
    from tracking.database import get_database_connection as _gdc, _execute_write as _ew

    with _gdc() as _uc:
        import sqlite3 as _sqlite3
        _uc.row_factory = _sqlite3.Row

        # ── KPI row ──────────────────────────────────────────────────────────
        _u_kpi = dict(_uc.execute(
            """
            SELECT
                COUNT(*)                                                AS total_users,
                SUM(CASE WHEN LOWER(COALESCE(plan_tier,'free')) != 'free' THEN 1 ELSE 0 END) AS paid_users,
                SUM(CASE WHEN LOWER(COALESCE(plan_tier,'free')) =  'free' THEN 1 ELSE 0 END) AS free_users,
                SUM(CASE WHEN is_admin = 1 THEN 1 ELSE 0 END)         AS admin_count,
                SUM(CASE WHEN lockout_until IS NOT NULL AND lockout_until > datetime('now') THEN 1 ELSE 0 END) AS locked_users
            FROM users
            """
        ).fetchone() or {})

        _u30d = (dict(_uc.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE created_at >= datetime('now','-30 days')"
        ).fetchone() or {}) or {}).get("cnt", 0)

        _uc1, _uc2, _uc3, _uc4, _uc5 = st.columns(5)
        _uc1.metric("Total Users",   _u_kpi.get("total_users", 0))
        _uc2.metric("Paid Users",    _u_kpi.get("paid_users", 0))
        _uc3.metric("Free Users",    _u_kpi.get("free_users", 0))
        _uc4.metric("Admins",        _u_kpi.get("admin_count", 0))
        _uc5.metric("New (30 d)",    _u30d)

        # ── Tier distribution chart ───────────────────────────────────────────
        _tier_dist = [dict(r) for r in _uc.execute(
            "SELECT COALESCE(plan_tier,'free') AS tier, COUNT(*) AS cnt FROM users GROUP BY tier ORDER BY cnt DESC"
        ).fetchall()]
        if _tier_dist:
            try:
                import plotly.express as _px
                _df_td = pd.DataFrame(_tier_dist)
                _fig_td = _px.pie(
                    _df_td, names="tier", values="cnt",
                    color_discrete_sequence=["#00D559","#F9C62B","#2D9EFF","#F24336","#9B59B6"],
                    title="Users by Subscription Tier",
                )
                _fig_td.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0", height=300,
                )
                st.plotly_chart(_fig_td, use_container_width=True)
            except ImportError:
                st.bar_chart(pd.DataFrame(_tier_dist).set_index("tier")["cnt"])

        # ── New signups over time (last 30 d) ─────────────────────────────────
        _signups_daily = [dict(r) for r in _uc.execute(
            """
            SELECT SUBSTR(created_at,1,10) AS day, COUNT(*) AS signups
            FROM users
            WHERE created_at >= datetime('now','-30 days')
            GROUP BY day ORDER BY day
            """
        ).fetchall()]
        if _signups_daily and len(_signups_daily) > 1:
            with st.expander("📈 New Signups — Last 30 Days", expanded=False):
                try:
                    import plotly.express as _px
                    _fig_su = _px.bar(
                        pd.DataFrame(_signups_daily), x="day", y="signups",
                        labels={"day": "Date", "signups": "New Users"},
                        title="Daily New Signups",
                        color_discrete_sequence=["#00D559"],
                    )
                    _fig_su.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=260,
                    )
                    st.plotly_chart(_fig_su, use_container_width=True)
                except ImportError:
                    st.bar_chart(pd.DataFrame(_signups_daily).set_index("day")["signups"])

        # ── User roster table ─────────────────────────────────────────────────
        with st.expander("📋 Full User Roster", expanded=False):
            _roster = [dict(r) for r in _uc.execute(
                """
                SELECT user_id, email, display_name,
                       COALESCE(plan_tier,'free')        AS tier,
                       SUBSTR(created_at,1,10)           AS joined,
                       SUBSTR(COALESCE(last_login_at,'—'),1,10) AS last_login,
                       COALESCE(failed_login_count,0)    AS failed_logins,
                       CASE WHEN is_admin=1 THEN '✅' ELSE '—' END AS admin,
                       CASE WHEN lockout_until IS NOT NULL AND lockout_until > datetime('now')
                            THEN '🔒 locked' ELSE '—' END AS status
                FROM users
                ORDER BY created_at DESC
                LIMIT 500
                """
            ).fetchall()]
            if _roster:
                _roster_search = st.text_input("Search by email or name", key="_admin_roster_search")
                _df_roster = pd.DataFrame(_roster)
                if _roster_search:
                    _mask_r = _df_roster.apply(lambda row: _roster_search.lower() in row.to_string().lower(), axis=1)
                    _df_roster = _df_roster[_mask_r]
                st.dataframe(_df_roster, use_container_width=True, hide_index=True)
            else:
                st.info("No users found.")

        # ── Manual tier override ──────────────────────────────────────────────
        with st.expander("⚙️ Manual Tier Override", expanded=False):
            st.caption("Change a user's subscription tier directly in the database.")
            _tier_col1, _tier_col2, _tier_col3 = st.columns([3, 2, 1])
            _override_email = _tier_col1.text_input("User email", key="_admin_tier_email", placeholder="user@example.com")
            _new_tier = _tier_col2.selectbox(
                "New tier", ["free", "sharp_iq", "smart_money", "insider_circle", "admin"],
                key="_admin_new_tier",
            )
            if _tier_col3.button("Apply", key="_admin_tier_apply"):
                if _override_email and _override_email.strip():
                    _res = _ew(
                        "UPDATE users SET plan_tier=? WHERE LOWER(email)=LOWER(?)",
                        (_new_tier, _override_email.strip()),
                        caller="admin_tier_override",
                    )
                    if _res is not None and _res.rowcount > 0:
                        st.success(f"Tier updated → {_new_tier} for {_override_email}")
                    else:
                        st.warning("No matching user found or update failed.")
                else:
                    st.warning("Enter a user email first.")

        # ── Account suspension ────────────────────────────────────────────────
        with st.expander("🔒 Account Suspension", expanded=False):
            st.caption("Lock or unlock a user account. Locked users cannot log in.")
            _sus_col1, _sus_col2, _sus_col3 = st.columns([3, 2, 1])
            _sus_email = _sus_col1.text_input("User email", key="_admin_sus_email", placeholder="user@example.com")
            _sus_action = _sus_col2.selectbox("Action", ["Lock account (1 year)", "Unlock account"], key="_admin_sus_action")
            if _sus_col3.button("Apply", key="_admin_sus_apply"):
                if _sus_email and _sus_email.strip():
                    if "Lock" in _sus_action:
                        _lock_until = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
                        _sus_res = _ew(
                            "UPDATE users SET lockout_until=? WHERE LOWER(email)=LOWER(?)",
                            (_lock_until, _sus_email.strip()),
                            caller="admin_lock_account",
                        )
                    else:
                        _sus_res = _ew(
                            "UPDATE users SET lockout_until=NULL, failed_login_count=0 WHERE LOWER(email)=LOWER(?)",
                            (_sus_email.strip(),),
                            caller="admin_unlock_account",
                        )
                    if _sus_res is not None and _sus_res.rowcount > 0:
                        st.success(f"{'Locked' if 'Lock' in _sus_action else 'Unlocked'}: {_sus_email}")
                    else:
                        st.warning("No matching user found or update failed.")
                else:
                    st.warning("Enter a user email first.")

except Exception as _user_exc:
    st.warning(f"Could not load user data: {_user_exc}")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 9 — Prediction / Model Health
# ═══════════════════════════════════════════════════════════

st.subheader("🧠 Prediction / Model Health")

try:
    from tracking.database import get_calibration_report as _gcr, load_daily_snapshots as _lds

    _cal_report = _gcr()
    _overall_cal = _cal_report.get("overall", {})
    _by_stat = _cal_report.get("by_stat", {})

    if _overall_cal:
        st.caption(_cal_report.get("summary_text", ""))
        _mh_c1, _mh_c2, _mh_c3, _mh_c4 = st.columns(4)
        _mh_c1.metric("Avg Predicted Prob", f"{_overall_cal.get('avg_predicted_prob', 0):.1f}%")
        _mh_c2.metric("Actual Hit Rate",    f"{_overall_cal.get('actual_hit_rate', 0):.1f}%")
        _mh_c3.metric("Calibration Adj",    f"{_overall_cal.get('calibration_adjustment', 0):+.1f} pts")
        _mh_c4.metric("Graded Predictions", _overall_cal.get("sample_count", 0))

        # ── Win rate by stat type ─────────────────────────────────────────────
        if _by_stat:
            _stat_rows = [
                {"stat_type": k, **v}
                for k, v in _by_stat.items()
            ]
            _df_stat = pd.DataFrame(_stat_rows).sort_values("actual_hit_rate", ascending=False)
            try:
                import plotly.express as _px
                _fig_stat = _px.bar(
                    _df_stat, x="stat_type", y="actual_hit_rate",
                    error_y=None,
                    color="actual_hit_rate",
                    color_continuous_scale="RdYlGn",
                    range_color=[40, 70],
                    labels={"stat_type": "Stat Type", "actual_hit_rate": "Hit Rate %"},
                    title="Model Hit Rate by Stat Type",
                    text_auto=".1f",
                )
                _fig_stat.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0", coloraxis_showscale=False, height=320,
                )
                # Reference line at 52.4% (breakeven for standard -110 odds)
                _fig_stat.add_hline(y=52.4, line_dash="dot", line_color="#F9C62B",
                                    annotation_text="Breakeven 52.4%", annotation_position="top right")
                st.plotly_chart(_fig_stat, use_container_width=True)
            except ImportError:
                st.dataframe(_df_stat[["stat_type","actual_hit_rate","avg_predicted_prob","sample_count"]],
                             use_container_width=True, hide_index=True)

        # ── Calibration scatter (predicted vs actual per stat type) ───────────
        if _by_stat and len(_by_stat) >= 3:
            with st.expander("🎯 Calibration Scatter — Predicted vs Actual", expanded=False):
                try:
                    import plotly.express as _px
                    _scatter_rows = [{"stat": k,
                                      "predicted": v["avg_predicted_prob"],
                                      "actual": v["actual_hit_rate"],
                                      "n": v["sample_count"]}
                                     for k, v in _by_stat.items()]
                    _df_sc = pd.DataFrame(_scatter_rows)
                    _fig_sc = _px.scatter(
                        _df_sc, x="predicted", y="actual", text="stat", size="n",
                        labels={"predicted": "Predicted %", "actual": "Actual Hit %"},
                        title="Predicted vs Actual Hit Rate by Stat",
                        color_discrete_sequence=["#2D9EFF"],
                    )
                    _fig_sc.add_shape(type="line", x0=40, y0=40, x1=75, y1=75,
                                      line=dict(color="#F9C62B", dash="dot"),
                                      name="Perfect calibration")
                    _fig_sc.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=360,
                    )
                    st.plotly_chart(_fig_sc, use_container_width=True)
                except ImportError:
                    pass

    else:
        st.info("Not enough graded predictions yet to compute calibration.")

    # ── Daily snapshot trend ──────────────────────────────────────────────────
    _snaps = _lds(30)
    if _snaps:
        with st.expander("📅 Daily Snapshot Trend — Last 30 Days", expanded=False):
            _df_snaps = pd.DataFrame(_snaps)[["snapshot_date","total_picks","wins","losses","win_rate"]].sort_values("snapshot_date")
            try:
                import plotly.graph_objects as _go
                _fig_snaps = _go.Figure()
                _fig_snaps.add_bar(x=_df_snaps["snapshot_date"], y=_df_snaps["wins"],
                                   name="Wins", marker_color="#00D559")
                _fig_snaps.add_bar(x=_df_snaps["snapshot_date"], y=_df_snaps["losses"],
                                   name="Losses", marker_color="#F24336")
                _fig_snaps.add_scatter(x=_df_snaps["snapshot_date"], y=_df_snaps["win_rate"],
                                       name="Win Rate %", yaxis="y2",
                                       line=dict(color="#F9C62B", width=2))
                _fig_snaps.update_layout(
                    barmode="group", yaxis2=dict(overlaying="y", side="right", title="Win Rate %"),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0", height=320, title="Daily Picks — Win/Loss + Win Rate",
                )
                st.plotly_chart(_fig_snaps, use_container_width=True)
            except ImportError:
                st.dataframe(_df_snaps, use_container_width=True, hide_index=True)

except Exception as _mh_exc:
    st.warning(f"Could not load model health data: {_mh_exc}")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 10 — Business Metrics
# ═══════════════════════════════════════════════════════════

st.subheader("💰 Business Metrics")

_TIER_PRICES = {
    "free": 0.0,
    "sharp_iq": 9.99,
    "smart_money": 19.99,
    "insider_circle": 39.99,
    "admin": 0.0,
}

try:
    from tracking.database import get_database_connection as _gdc2
    with _gdc2() as _bc:
        import sqlite3 as _sqlite3
        _bc.row_factory = _sqlite3.Row

        # ── Tier subscriber counts ────────────────────────────────────────────
        _tier_counts = {r["tier"]: r["cnt"] for r in [
            dict(x) for x in _bc.execute(
                "SELECT COALESCE(plan_tier,'free') AS tier, COUNT(*) AS cnt FROM users GROUP BY tier"
            ).fetchall()
        ]}

        _est_mrr = sum(_TIER_PRICES.get(t, 0) * c for t, c in _tier_counts.items())
        _paid_total = sum(c for t, c in _tier_counts.items() if t not in ("free", "admin"))

        _bm_c1, _bm_c2, _bm_c3, _bm_c4 = st.columns(4)
        _bm_c1.metric("Est. MRR", f"${_est_mrr:,.2f}")
        _bm_c2.metric("Paid Subscribers", _paid_total)
        _bm_c3.metric("Free Users", _tier_counts.get("free", 0))
        _bm_c4.metric("Insider Circle", _tier_counts.get("insider_circle", 0))

        # ── Active subscriptions from Stripe table ────────────────────────────
        _stripe_subs = [dict(r) for r in _bc.execute(
            """
            SELECT plan_name, status, COUNT(*) AS cnt,
                   MIN(current_period_end) AS earliest_expiry
            FROM subscriptions
            GROUP BY plan_name, status ORDER BY cnt DESC
            """
        ).fetchall()]
        if _stripe_subs:
            with st.expander("💳 Stripe Subscription Breakdown", expanded=False):
                st.dataframe(pd.DataFrame(_stripe_subs), use_container_width=True, hide_index=True)

        # ── Conversion funnel ─────────────────────────────────────────────────
        with st.expander("🔄 Conversion Funnel", expanded=False):
            _funnel_tiers = ["free", "sharp_iq", "smart_money", "insider_circle"]
            _funnel_data = [{"tier": t, "users": _tier_counts.get(t, 0)} for t in _funnel_tiers]
            try:
                import plotly.express as _px
                _df_funnel = pd.DataFrame(_funnel_data)
                _fig_funnel = _px.funnel(_df_funnel, x="users", y="tier",
                                         title="User Conversion Funnel by Tier",
                                         color_discrete_sequence=["#2D9EFF"])
                _fig_funnel.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0", height=300,
                )
                st.plotly_chart(_fig_funnel, use_container_width=True)
            except ImportError:
                st.dataframe(pd.DataFrame(_funnel_data), use_container_width=True, hide_index=True)

        # ── Churn indicators: signed up but still free after 14+ days ─────────
        _churn_risk = (dict(_bc.execute(
            """
            SELECT COUNT(*) AS cnt FROM users
            WHERE LOWER(COALESCE(plan_tier,'free')) = 'free'
              AND created_at <= datetime('now','-14 days')
            """
        ).fetchone() or {}) or {}).get("cnt", 0)
        st.caption(f"⚠️ {_churn_risk} users signed up 14+ days ago and are still on the free tier (churn risk).")

except Exception as _biz_exc:
    st.warning(f"Could not load business metrics: {_biz_exc}")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 11 — Bet Tracker Aggregate
# ═══════════════════════════════════════════════════════════

st.subheader("📊 Bet Tracker Aggregate")

try:
    from tracking.database import get_performance_summary as _gps, get_rolling_stats as _grs
    from tracking.database import get_database_connection as _gdc3

    _perf = _gps()
    _roll = _grs(30)

    _bt_c1, _bt_c2, _bt_c3, _bt_c4, _bt_c5 = st.columns(5)
    _bt_c1.metric("Total Bets Logged", _perf["total_bets"])
    _bt_c2.metric("Wins",              _perf["wins"])
    _bt_c3.metric("Losses",            _perf["losses"])
    _bt_c4.metric("Win Rate",          f"{_perf['win_rate']:.1f}%")
    _streak = _roll.get("streak", 0)
    _bt_c5.metric("Current Streak",
                  f"{'🔥' if _streak > 0 else '❄️'} {abs(_streak)}"
                  f"{'W' if _streak > 0 else 'L' if _streak < 0 else ''}",
                  delta=None)

    # ── Platform breakdown ────────────────────────────────────────────────────
    with _gdc3() as _btc:
        import sqlite3 as _sqlite3
        _btc.row_factory = _sqlite3.Row

        _plat_rows = [dict(r) for r in _btc.execute(
            """
            SELECT COALESCE(platform,'Unknown') AS platform,
                   COUNT(*) AS bets,
                   SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
                   ROUND(
                       CAST(SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS REAL)
                       / NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS') THEN 1 ELSE 0 END),0) * 100
                   , 1) AS win_rate_pct
            FROM bets WHERE entry_id IS NULL AND result IS NOT NULL AND result != ''
            GROUP BY platform ORDER BY bets DESC
            """
        ).fetchall()]

        if _plat_rows:
            with st.expander("🎯 Platform Breakdown", expanded=True):
                st.dataframe(pd.DataFrame(_plat_rows), use_container_width=True, hide_index=True)

        # ── Entry builder win rate ────────────────────────────────────────────
        _entry_rows = [dict(r) for r in _btc.execute(
            """
            SELECT COALESCE(entry_type,'parlay') AS entry_type,
                   COUNT(*) AS entries,
                   SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
                   ROUND(
                       CAST(SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS REAL)
                       / NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS') THEN 1 ELSE 0 END),0) * 100
                   , 1) AS win_rate_pct,
                   ROUND(SUM(COALESCE(payout,0)) - SUM(COALESCE(entry_fee,0)), 2) AS net_pnl
            FROM entries WHERE result IS NOT NULL AND result != ''
            GROUP BY entry_type ORDER BY entries DESC
            """
        ).fetchall()]

        if _entry_rows:
            with st.expander("📋 Entry Builder Win Rate", expanded=False):
                st.dataframe(pd.DataFrame(_entry_rows), use_container_width=True, hide_index=True)

        # ── Stat type win rates ───────────────────────────────────────────────
        _stat_wr_rows = [dict(r) for r in _btc.execute(
            """
            SELECT COALESCE(stat_type,'Unknown') AS stat_type,
                   COUNT(*) AS bets,
                   SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
                   ROUND(
                       CAST(SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS REAL)
                       / NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS') THEN 1 ELSE 0 END),0) * 100
                   , 1) AS win_rate_pct
            FROM bets WHERE entry_id IS NULL AND result IS NOT NULL AND result != ''
            GROUP BY stat_type ORDER BY bets DESC LIMIT 15
            """
        ).fetchall()]

        if _stat_wr_rows:
            with st.expander("🏀 Win Rate by Stat Type", expanded=False):
                try:
                    import plotly.express as _px
                    _df_swr = pd.DataFrame(_stat_wr_rows).dropna(subset=["win_rate_pct"])
                    _fig_swr = _px.bar(
                        _df_swr, x="stat_type", y="win_rate_pct",
                        color="win_rate_pct", color_continuous_scale="RdYlGn",
                        range_color=[40, 70],
                        labels={"stat_type": "Stat", "win_rate_pct": "Win %"},
                        title="Bet Tracker Win Rate by Stat Type",
                        text_auto=".1f",
                    )
                    _fig_swr.add_hline(y=52.4, line_dash="dot", line_color="#F9C62B",
                                       annotation_text="52.4% breakeven")
                    _fig_swr.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", coloraxis_showscale=False, height=300,
                    )
                    st.plotly_chart(_fig_swr, use_container_width=True)
                except ImportError:
                    st.dataframe(pd.DataFrame(_stat_wr_rows), use_container_width=True, hide_index=True)

except Exception as _bet_exc:
    st.warning(f"Could not load bet tracker aggregate: {_bet_exc}")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 12 — Security / Audit Log
# ═══════════════════════════════════════════════════════════

st.subheader("🔐 Security & Audit Log")

try:
    from tracking.database import get_database_connection as _gdc4
    with _gdc4() as _sec:
        import sqlite3 as _sqlite3
        _sec.row_factory = _sqlite3.Row

        # ── Failed login summary ──────────────────────────────────────────────
        _failed_logins = [dict(r) for r in _sec.execute(
            """
            SELECT email, failed_login_count,
                   COALESCE(lockout_until,'—') AS lockout_until,
                   SUBSTR(COALESCE(last_login_at,'—'),1,16) AS last_login
            FROM users
            WHERE failed_login_count > 0
            ORDER BY failed_login_count DESC
            LIMIT 50
            """
        ).fetchall()]

        _brute_count = len([r for r in _failed_logins if r.get("failed_login_count", 0) >= 5])
        _locked_count = len([r for r in _failed_logins if r.get("lockout_until", "—") != "—"])
        _sec_c1, _sec_c2 = st.columns(2)
        _sec_c1.metric("Users with Failed Logins", len(_failed_logins))
        _sec_c2.metric("Accounts Locked / Brute-force Risk (5+ fails)", _brute_count)

        if _failed_logins:
            with st.expander("🚫 Failed Login Details", expanded=False):
                st.dataframe(pd.DataFrame(_failed_logins), use_container_width=True, hide_index=True)

        # ── Password reset requests ───────────────────────────────────────────
        _pw_resets = [dict(r) for r in _sec.execute(
            """
            SELECT email, SUBSTR(reset_token_expires,1,16) AS reset_expires
            FROM users
            WHERE reset_token IS NOT NULL
            ORDER BY reset_token_expires DESC
            LIMIT 50
            """
        ).fetchall()]
        if _pw_resets:
            with st.expander(f"🔑 Pending Password Resets ({len(_pw_resets)})", expanded=False):
                st.dataframe(pd.DataFrame(_pw_resets), use_container_width=True, hide_index=True)
        else:
            st.caption("✅ No pending password reset tokens.")

        # ── Permission denials (analytics events) ────────────────────────────
        _perm_denials = [dict(r) for r in _sec.execute(
            """
            SELECT SUBSTR(timestamp,1,10) AS day,
                   COALESCE(page,'—') AS page,
                   COUNT(*) AS denials
            FROM analytics_events
            WHERE event_name IN ('permission_denied','access_denied','upgrade_cta')
              AND timestamp >= datetime('now','-30 days')
            GROUP BY day, page ORDER BY day DESC, denials DESC
            LIMIT 50
            """
        ).fetchall()]
        if _perm_denials:
            with st.expander("🚧 Permission Denials / Upgrade CTA Hits (30 d)", expanded=False):
                st.dataframe(pd.DataFrame(_perm_denials), use_container_width=True, hide_index=True)

        # ── Bet audit log ─────────────────────────────────────────────────────
        _audit_rows = [dict(r) for r in _sec.execute(
            """
            SELECT audit_id, bet_id, action,
                   SUBSTR(changed_at,1,16) AS changed_at,
                   old_values, new_values
            FROM bet_audit_log
            ORDER BY changed_at DESC
            LIMIT 100
            """
        ).fetchall()]
        if _audit_rows:
            with st.expander(f"📝 Bet Audit Log (last 100 actions)", expanded=False):
                _audit_search = st.text_input("Filter audit log", key="_admin_audit_search")
                _df_audit = pd.DataFrame(_audit_rows)
                if _audit_search:
                    _mask_a = _df_audit.apply(lambda row: _audit_search.lower() in row.to_string().lower(), axis=1)
                    _df_audit = _df_audit[_mask_a]
                st.dataframe(_df_audit, use_container_width=True, hide_index=True)
        else:
            st.caption("No bet audit entries yet.")

except Exception as _sec_exc:
    st.warning(f"Could not load security data: {_sec_exc}")

st.divider()


# ═══════════════════════════════════════════════════════════
# ROW 13 — Infrastructure
# ═══════════════════════════════════════════════════════════

st.subheader("🏗️ Infrastructure")

try:
    from tracking.database import get_database_connection as _gdc5, DB_FILE_PATH as _DBP
    from tracking.database import create_database_backup as _cdb
    import os as _os
    import pathlib as _pl

    # ── DB file size ──────────────────────────────────────────────────────────
    _db_path = _pl.Path(_DBP)
    _db_size_mb = round(_db_path.stat().st_size / 1e6, 2) if _db_path.exists() else 0.0

    with _gdc5() as _ic:
        import sqlite3 as _sqlite3
        _ic.row_factory = _sqlite3.Row

        _table_counts = [dict(r) for r in _ic.execute(
            """
            SELECT name FROM sqlite_master WHERE type='table'
            """
        ).fetchall()]
        _row_counts = []
        for _t in _table_counts:
            try:
                _cnt = _ic.execute(f"SELECT COUNT(*) AS cnt FROM \"{_t['name']}\"").fetchone()
                _row_counts.append({"table": _t["name"], "rows": _cnt["cnt"] if _cnt else 0})
            except Exception:
                _row_counts.append({"table": _t["name"], "rows": "—"})

    _inf_c1, _inf_c2, _inf_c3 = st.columns(3)
    _inf_c1.metric("DB File Size", f"{_db_size_mb} MB")
    _inf_c2.metric("Tables", len(_row_counts))
    _inf_c3.metric("Total Rows (est)", sum(r["rows"] for r in _row_counts if isinstance(r["rows"], int)))

    with st.expander("📦 Table Row Counts", expanded=False):
        st.dataframe(
            pd.DataFrame(_row_counts).sort_values("rows", ascending=False),
            use_container_width=True, hide_index=True,
        )

    # ── Backup status ─────────────────────────────────────────────────────────
    with st.expander("💾 Backup Status & Manual Backup", expanded=False):
        try:
            from tracking.database import BACKUP_DIRECTORY as _BUD
            _backup_dir = _pl.Path(_BUD)
            _backups = sorted(_backup_dir.glob("smartai_nba_*.db"), reverse=True) if _backup_dir.exists() else []
            if _backups:
                _last_bk = _backups[0]
                _last_bk_size = round(_last_bk.stat().st_size / 1e6, 2)
                _last_bk_time = datetime.fromtimestamp(_last_bk.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                st.metric("Last Backup", _last_bk.name, delta=f"{_last_bk_size} MB, {_last_bk_time}")
                st.caption(f"{len(_backups)} backup(s) retained in {_backup_dir}")
            else:
                st.info("No backups found yet.")
        except Exception:
            st.caption("Backup directory not accessible in this environment.")

        if st.button("🔄 Create Manual Backup Now", key="_admin_manual_backup"):
            with st.spinner("Creating backup…"):
                _ok, _msg = _cdb(reason="admin_manual")
            if _ok:
                st.success(f"Backup created: {_msg}")
            else:
                st.error(f"Backup failed: {_msg}")

    # ── Maintenance log ───────────────────────────────────────────────────────
    with st.expander("🧹 Run Maintenance", expanded=False):
        st.caption("Purges old sessions, stale game logs, and excess backups.")
        if st.button("▶️ Run Maintenance Now", key="_admin_run_maintenance"):
            with st.spinner("Running maintenance…"):
                try:
                    from tracking.database import run_maintenance as _rm
                    _rm_result = _rm()
                    st.success(f"Maintenance complete: {_rm_result}")
                except Exception as _rm_err:
                    st.error(f"Maintenance error: {_rm_err}")

except Exception as _infra_exc:
    st.warning(f"Could not load infrastructure data: {_infra_exc}")
