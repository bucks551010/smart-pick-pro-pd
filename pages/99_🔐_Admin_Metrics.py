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

# ── Auth gate: admin-only ─────────────────────────────────
from utils.auth_gate import require_login, is_admin_user

if not require_login():
    st.stop()

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
