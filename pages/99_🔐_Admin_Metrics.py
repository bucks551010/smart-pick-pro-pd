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
# ── Elite Admin Dashboard CSS ────────────────────────────
st.markdown("""
<style>
/* ═══════════════════════════════════════════════
   ADMIN DASHBOARD — ELITE DARK THEME
   Color palette:
     --bg-base:    #0a0d14   (deep navy black)
     --bg-card:    #0f1420   (card surface)
     --bg-glass:   rgba(15,20,40,0.85)
     --accent-1:   #2D9EFF   (electric blue)
     --accent-2:   #F9C62B   (gold)
     --accent-3:   #00D559   (green)
     --accent-4:   #B06EFF   (violet)
     --danger:     #F24336
     --text-hi:    #f0f4ff
     --text-lo:    #7a8499
═══════════════════════════════════════════════ */

/* ── Page background ─────────────────────────── */
[data-testid="stAppViewContainer"] > .main {
    background: radial-gradient(ellipse at 20% 0%, rgba(45,158,255,0.08) 0%, transparent 55%),
                radial-gradient(ellipse at 80% 100%, rgba(176,110,255,0.07) 0%, transparent 55%),
                #0a0d14 !important;
}
[data-testid="stSidebar"] {
    background: #070a10 !important;
    border-right: 1px solid rgba(45,158,255,0.12) !important;
}

/* ── Block container padding ─────────────────── */
.block-container { padding-top: 0 !important; max-width: 1400px !important; }

/* ── Hero header ─────────────────────────────── */
.adm-hero {
    background: linear-gradient(135deg, #0f1928 0%, #0a0d14 40%, #0d1020 100%);
    border: 1px solid rgba(45,158,255,0.18);
    border-radius: 16px;
    padding: 28px 36px 20px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.adm-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #2D9EFF 0%, #B06EFF 50%, #00D559 100%);
}
.adm-hero-title {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #f0f4ff;
    margin: 0 0 4px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.adm-hero-sub {
    font-size: 0.82rem;
    color: #7a8499;
    margin: 0 0 18px;
    letter-spacing: 0.4px;
}
.adm-hero-badges {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}
.adm-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.adm-badge-blue  { background: rgba(45,158,255,0.12); color: #2D9EFF; border: 1px solid rgba(45,158,255,0.25); }
.adm-badge-gold  { background: rgba(249,198,43,0.12); color: #F9C62B; border: 1px solid rgba(249,198,43,0.25); }
.adm-badge-green { background: rgba(0,213,89,0.10);   color: #00D559; border: 1px solid rgba(0,213,89,0.22); }
.adm-badge-red   { background: rgba(242,67,54,0.10);  color: #F24336; border: 1px solid rgba(242,67,54,0.22); }
.adm-badge-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: currentColor;
    animation: adm-pulse 2s ease-in-out infinite;
}
@keyframes adm-pulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:0.4; transform:scale(0.7); }
}

/* ── Section headers ─────────────────────────── */
.adm-section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 0 8px;
    margin-bottom: 12px;
    border-bottom: 1px solid rgba(45,158,255,0.1);
}
.adm-section-accent {
    width: 4px;
    height: 22px;
    border-radius: 3px;
    background: linear-gradient(180deg, #2D9EFF, #B06EFF);
    flex-shrink: 0;
}
.adm-section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #f0f4ff;
    margin: 0;
    letter-spacing: -0.2px;
}
.adm-section-sub {
    font-size: 0.75rem;
    color: #7a8499;
    margin-left: auto;
}

/* ── KPI metric cards ─────────────────────────── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(15,20,40,0.9) 0%, rgba(10,13,20,0.95) 100%) !important;
    border: 1px solid rgba(45,158,255,0.12) !important;
    border-radius: 12px !important;
    padding: 16px 20px 14px !important;
    position: relative !important;
    overflow: hidden !important;
    transition: border-color 0.2s, transform 0.15s !important;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(45,158,255,0.32) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stMetric"]::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(45,158,255,0.4), transparent);
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.7px !important;
    color: #7a8499 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.65rem !important;
    font-weight: 800 !important;
    color: #f0f4ff !important;
    line-height: 1.15 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.78rem !important; }

/* ── Dividers ─────────────────────────────────── */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(45,158,255,0.18), rgba(176,110,255,0.12), transparent) !important;
    margin: 28px 0 !important;
}

/* ── Expanders ────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(15,20,40,0.6) !important;
    border: 1px solid rgba(45,158,255,0.1) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(45,158,255,0.22) !important;
}
[data-testid="stExpanderToggleIcon"] { color: #2D9EFF !important; }

/* ── Dataframes ───────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(45,158,255,0.1) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── Buttons ──────────────────────────────────── */
[data-testid="stButton"] > button,
button[kind="primary"] {
    background: linear-gradient(135deg, #1a4a8a, #2D9EFF) !important;
    border: 1px solid rgba(45,158,255,0.4) !important;
    color: #fff !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
}
[data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, #2D9EFF, #5bb5ff) !important;
    border-color: #2D9EFF !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(45,158,255,0.3) !important;
}

/* ── Select/input fields ──────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div > input {
    background: rgba(15,20,40,0.8) !important;
    border-color: rgba(45,158,255,0.2) !important;
    color: #f0f4ff !important;
    border-radius: 8px !important;
}

/* ── Info / warning / success boxes ──────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* ── Download buttons ─────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: rgba(0,213,89,0.1) !important;
    border: 1px solid rgba(0,213,89,0.3) !important;
    color: #00D559 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: rgba(0,213,89,0.18) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,213,89,0.2) !important;
}

/* ── Tab nav ──────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid rgba(45,158,255,0.15) !important;
    gap: 4px !important;
}
[data-testid="stTabs"] [role="tab"] {
    border-radius: 8px 8px 0 0 !important;
    color: #7a8499 !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    transition: color 0.2s !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #2D9EFF !important;
    border-bottom: 2px solid #2D9EFF !important;
    background: rgba(45,158,255,0.06) !important;
}

/* ── Plotly chart containers ─────────────────── */
.js-plotly-plot {
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── Spinner ─────────────────────────────────── */
[data-testid="stSpinner"] > div { border-top-color: #2D9EFF !important; }

/* ── Caption text ─────────────────────────────── */
[data-testid="stCaptionContainer"] { color: #7a8499 !important; font-size: 0.78rem !important; }

/* ── Scrollbar ─────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0a0d14; }
::-webkit-scrollbar-thumb { background: rgba(45,158,255,0.3); border-radius: 6px; }
::-webkit-scrollbar-thumb:hover { background: #2D9EFF; }
</style>
""", unsafe_allow_html=True)

# ── Hero header ───────────────────────────────────────────
_refresh_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
st.markdown(f"""
<div class="adm-hero">
  <div class="adm-hero-title">🔐 Admin Operations Center</div>
  <div class="adm-hero-sub">Smart Pick Pro · Internal Observability Dashboard · {_refresh_ts}</div>
  <div class="adm-hero-badges">
    <span class="adm-badge adm-badge-green"><span class="adm-badge-dot"></span>Live</span>
    <span class="adm-badge adm-badge-blue">18 Metric Sections</span>
    <span class="adm-badge adm-badge-gold">Insider Circle Access</span>
    <span class="adm-badge adm-badge-red">🔒 Admin Only</span>
  </div>
</div>
""", unsafe_allow_html=True)

_7D_AGO  = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
_14D_AGO = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(timespec="seconds")
_1H_AGO  = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")

# ── Tab navigation ───────────────────────────────────────
_tab_sys, _tab_users, _tab_intel, _tab_ops = st.tabs([
    "🖥️ System & Performance",
    "👥 Users & Revenue",
    "🧠 Model & Intelligence",
    "🔐 Security & Ops",
])


with _tab_sys:
    # ═══════════════════════════════════════════════════════════
    # ROW 1 — System Resource KPIs
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🖥️ System Resources</div><span class="adm-section-sub">CPU · Memory · Disk · Sessions</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">📊 Feature Utilisation</div><span class="adm-section-sub">Last 7 days</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">⚡ Execution Performance</div><span class="adm-section-sub">p50 · p95 · p99 latency — Last 7 days</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🚨 Error Rate</div><span class="adm-section-sub">Daily error count by type — Last 14 days</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">📋 Recent Error Log</div><span class="adm-section-sub">Last 50 exceptions · searchable</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🌍 Active Sessions by Page</div><span class="adm-section-sub">PII-free · last 60 min</span></div>', unsafe_allow_html=True)
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



with _tab_users:
    # ═══════════════════════════════════════════════════════════
    # ROW 7 — Website Analytics (analytics_events table)
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">📣 Website Analytics</div><span class="adm-section-sub">GA4 events · page views · top pages</span></div>', unsafe_allow_html=True)
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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">👥 User Management</div><span class="adm-section-sub">Tiers · roster · overrides · account controls</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🧠 Prediction / Model Health</div><span class="adm-section-sub">Calibration · hit rate · confidence · daily snapshots</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">💰 Business Metrics</div><span class="adm-section-sub">MRR · Stripe · churn risk · funnel</span></div>', unsafe_allow_html=True)

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



with _tab_intel:
    # ═══════════════════════════════════════════════════════════
    # ROW 11 — Bet Tracker Aggregate
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">📊 Bet Tracker Aggregate</div><span class="adm-section-sub">All users · platform breakdown · win rates</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🔐 Security & Audit Log</div><span class="adm-section-sub">Failed logins · resets · permission denials · bet audit</span></div>', unsafe_allow_html=True)

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

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🏗️ Infrastructure</div><span class="adm-section-sub">DB size · table counts · backups · maintenance</span></div>', unsafe_allow_html=True)

    try:
        from tracking.database import get_database_connection as _gdc5, DB_FILE_PATH as _DBP
        from tracking.database import create_database_backup as _cdb
        import os as _os
        import pathlib as _pl

        # ── DB file size ──────────────────────────────────────────────────────────
        _db_path = _pl.Path(_DBP)
        _db_size_mb = round(_db_path.stat().st_size / 1e6, 2) if _db_path.exists() else 0.0

        import os as _infra_os
        _is_pg = bool(_infra_os.environ.get("DATABASE_URL"))
        with _gdc5() as _ic:
            import sqlite3 as _sqlite3
            _ic.row_factory = _sqlite3.Row

            if _is_pg:
                # PostgreSQL: use information_schema
                _table_counts = [dict(r) for r in _ic.execute(
                    """
                    SELECT table_name AS name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                    """
                ).fetchall()]
            else:
                _table_counts = [dict(r) for r in _ic.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]

            _row_counts = []
            for _t in _table_counts:
                try:
                    _cnt = _ic.execute(f"SELECT COUNT(*) AS cnt FROM \"{_t['name']}\"").fetchone()
                    _row_counts.append({"table": _t["name"], "rows": (_cnt or {}).get("cnt", 0)})
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

    st.divider()


    # ═══════════════════════════════════════════════════════════
    # ROW 14 — Data Freshness & API Health
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">📡 Data Freshness & API Health</div><span class="adm-section-sub">Props · games · players · cache staleness · scanner output</span></div>', unsafe_allow_html=True)

    try:
        from data.nba_data_service import load_last_updated as _llu
        from tracking.database import get_database_connection as _gdc6, is_game_log_cache_stale as _icls

        _lu = _llu() or {}

        # ── Staleness check helpers ───────────────────────────────────────────────
        def _staleness_flag(ts_str):
            """Return (age_str, is_stale) for a timestamp string."""
            if not ts_str:
                return "never", True
            try:
                _ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                if _ts.tzinfo is None:
                    _ts = _ts.replace(tzinfo=timezone.utc)
                _age = datetime.now(timezone.utc) - _ts
                _h = int(_age.total_seconds() // 3600)
                _m = int((_age.total_seconds() % 3600) // 60)
                return (f"{_h}h {_m}m ago", _age.total_seconds() > 86400)
            except Exception:
                return str(ts_str)[:16], False

        # ── KPIs ─────────────────────────────────────────────────────────────────
        _df_c1, _df_c2, _df_c3, _df_c4 = st.columns(4)

        _props_ts = _lu.get("props") or _lu.get("prop_lines") or _lu.get("last_updated")
        _games_ts = _lu.get("games") or _lu.get("todays_games")
        _players_ts = _lu.get("players") or _lu.get("player_stats")

        _props_age, _props_stale = _staleness_flag(_props_ts)
        _games_age, _games_stale = _staleness_flag(_games_ts)
        _players_age, _players_stale = _staleness_flag(_players_ts)

        _df_c1.metric("Props Last Fetched",   _props_age,   delta="⚠️ STALE" if _props_stale else None,
                      delta_color="inverse")
        _df_c2.metric("Games Last Fetched",   _games_age,   delta="⚠️ STALE" if _games_stale else None,
                      delta_color="inverse")
        _df_c3.metric("Players Last Fetched", _players_age, delta="⚠️ STALE" if _players_stale else None,
                      delta_color="inverse")

        # ── Game log cache staleness ──────────────────────────────────────────────
        with _gdc6() as _dfc:
            import sqlite3 as _sqlite3
            _dfc.row_factory = _sqlite3.Row
            _cache_rows = [dict(r) for r in _dfc.execute(
                """
                SELECT player_id, player_name,
                       MAX(retrieved_at) AS last_fetched,
                       COUNT(*) AS log_rows
                FROM player_game_logs
                GROUP BY player_id
                ORDER BY last_fetched ASC
                LIMIT 20
                """
            ).fetchall()]

            _total_cached = (dict(_dfc.execute(
                "SELECT COUNT(DISTINCT player_id) AS cnt FROM player_game_logs"
            ).fetchone() or {}) or {}).get("cnt", 0)

            _stale_cached = (dict(_dfc.execute(
                "SELECT COUNT(DISTINCT player_id) AS cnt FROM player_game_logs "
                "WHERE retrieved_at < datetime('now','-24 hours')"
            ).fetchone() or {}) or {}).get("cnt", 0)

        _df_c4.metric("Cached Players", f"{_total_cached} ({_stale_cached} stale)")

        # ── All last_updated keys table ───────────────────────────────────────────
        if _lu:
            with st.expander("🕐 Full Data Freshness Log", expanded=False):
                _lu_rows = [{"data_type": k, "last_updated": v} for k, v in _lu.items()]
                st.dataframe(pd.DataFrame(_lu_rows), use_container_width=True, hide_index=True)

        # ── Stalest cached players ────────────────────────────────────────────────
        if _cache_rows:
            with st.expander("🏀 Stalest Game Log Cache Entries (oldest 20)", expanded=False):
                st.dataframe(pd.DataFrame(_cache_rows), use_container_width=True, hide_index=True)

        # ── API call telemetry ────────────────────────────────────────────────────
        _api_calls = query_telemetry(
            """
            SELECT SUBSTR(timestamp,1,10) AS day,
                   feature_name,
                   COUNT(*) AS calls
            FROM telemetry_features
            WHERE feature_name LIKE '%nba%' OR feature_name LIKE '%api%' OR feature_name LIKE '%fetch%'
              AND timestamp >= ?
            GROUP BY day, feature_name ORDER BY day DESC, calls DESC
            LIMIT 50
            """,
            (_7D_AGO,),
        )
        if _api_calls:
            with st.expander("📊 API-Related Feature Calls (7 d)", expanded=False):
                st.dataframe(pd.DataFrame(_api_calls), use_container_width=True, hide_index=True)

        # ── Prop scanner daily summary from all_analysis_picks ───────────────────
        with _gdc6() as _psc:
            _psc.row_factory = _sqlite3.Row
            _scan_daily = [dict(r) for r in _psc.execute(
                """
                SELECT SUBSTR(pick_date,1,10) AS day,
                       COUNT(*) AS picks_generated,
                       ROUND(AVG(COALESCE(edge_percentage,0)),1) AS avg_edge,
                       ROUND(AVG(COALESCE(confidence_score,0)),1) AS avg_confidence,
                       SUM(CASE WHEN LOWER(COALESCE(tier,'')) IN ('platinum','gold') THEN 1 ELSE 0 END) AS elite_picks
                FROM all_analysis_picks
                WHERE pick_date >= ?
                GROUP BY day ORDER BY day DESC
                """,
                (_14D_AGO[:10],),
            ).fetchall()]

        if _scan_daily:
            with st.expander("⚡ Prop Scanner Daily Output (14 d)", expanded=False):
                try:
                    import plotly.express as _px
                    _df_scan = pd.DataFrame(_scan_daily).sort_values("day")
                    _fig_scan = _px.bar(
                        _df_scan, x="day", y="picks_generated",
                        color="avg_edge", color_continuous_scale="Teal",
                        labels={"day": "Date", "picks_generated": "Picks", "avg_edge": "Avg Edge %"},
                        title="Daily Prop Scanner Output",
                        text_auto=True,
                    )
                    _fig_scan.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=280,
                    )
                    st.plotly_chart(_fig_scan, use_container_width=True)
                except ImportError:
                    st.dataframe(pd.DataFrame(_scan_daily), use_container_width=True, hide_index=True)

    except Exception as _df_exc:
        st.warning(f"Could not load data freshness info: {_df_exc}")

    st.divider()


    # ═══════════════════════════════════════════════════════════
    # ROW 15 — Deeper Model Intelligence
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🔬 Deeper Model Intelligence</div><span class="adm-section-sub">Backtests · edge dist · confidence · player leaderboard · bias</span></div>', unsafe_allow_html=True)

    try:
        from tracking.database import (
            load_backtest_results as _lbr,
            load_all_analysis_picks as _laap,
            load_recent_predictions as _lrp,
            get_database_connection as _gdc7,
        )

        # ── Backtest results table ────────────────────────────────────────────────
        _bt_results = _lbr(limit=20)
        if _bt_results:
            with st.expander("📈 Backtest Results (last 20 runs)", expanded=True):
                _df_bt = pd.DataFrame(_bt_results)
                _display_cols = [c for c in [
                    "run_timestamp","season","min_edge","tier_filter",
                    "total_picks","wins","losses","win_rate","roi","total_pnl"
                ] if c in _df_bt.columns]
                st.dataframe(_df_bt[_display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No backtest runs recorded yet. Run a backtest from the QAM page to populate this.")

        # ── Edge / confidence distribution ───────────────────────────────────────
        with _gdc7() as _mi_c:
            import sqlite3 as _sqlite3
            _mi_c.row_factory = _sqlite3.Row

            _edge_dist = [dict(r) for r in _mi_c.execute(
                """
                SELECT ROUND(COALESCE(edge_percentage,0)/5)*5 AS edge_bucket,
                       COUNT(*) AS picks
                FROM all_analysis_picks
                WHERE pick_date >= ?
                GROUP BY edge_bucket ORDER BY edge_bucket
                """,
                (_14D_AGO[:10],),
            ).fetchall()]

            _conf_dist = [dict(r) for r in _mi_c.execute(
                """
                SELECT ROUND(COALESCE(confidence_score,0)/5)*5 AS conf_bucket,
                       COUNT(*) AS picks
                FROM all_analysis_picks
                WHERE pick_date >= ?
                GROUP BY conf_bucket ORDER BY conf_bucket
                """,
                (_14D_AGO[:10],),
            ).fetchall()]

            # ── Player pick leaderboard (accuracy, min 10 graded) ─────────────────
            _player_lb = [dict(r) for r in _mi_c.execute(
                """
                SELECT player_name,
                       COUNT(*) AS total,
                       SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) AS wins,
                       SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
                       ROUND(
                           CAST(SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS REAL)
                           / NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS') THEN 1 ELSE 0 END),0) * 100
                       ,1) AS hit_rate_pct,
                       ROUND(AVG(COALESCE(edge_percentage,0)),1) AS avg_edge
                FROM all_analysis_picks
                WHERE result IN ('WIN','LOSS')
                GROUP BY player_name
                HAVING COUNT(*) >= 10
                ORDER BY hit_rate_pct DESC
                LIMIT 20
                """
            ).fetchall()]

            # ── Over/Under bias ───────────────────────────────────────────────────
            _ou_bias = [dict(r) for r in _mi_c.execute(
                """
                SELECT UPPER(COALESCE(direction,'?')) AS direction,
                       COUNT(*) AS picks,
                       ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(),1) AS pct
                FROM all_analysis_picks
                WHERE pick_date >= ?
                GROUP BY direction
                """,
                (_14D_AGO[:10],),
            ).fetchall()]

        # ── Edge distribution histogram ──────────────────────────────────────────
        if _edge_dist:
            with st.expander("📊 Edge Distribution (14 d)", expanded=False):
                try:
                    import plotly.express as _px
                    _fig_ed = _px.bar(
                        pd.DataFrame(_edge_dist), x="edge_bucket", y="picks",
                        labels={"edge_bucket": "Edge % (5-pt bucket)", "picks": "Picks"},
                        title="Distribution of Edge % Across All Picks",
                        color_discrete_sequence=["#2D9EFF"],
                    )
                    _fig_ed.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=280,
                    )
                    st.plotly_chart(_fig_ed, use_container_width=True)
                except ImportError:
                    st.dataframe(pd.DataFrame(_edge_dist), use_container_width=True, hide_index=True)

        # ── Confidence distribution ───────────────────────────────────────────────
        if _conf_dist:
            with st.expander("🎯 Confidence Score Distribution (14 d)", expanded=False):
                try:
                    import plotly.express as _px
                    _fig_cd = _px.bar(
                        pd.DataFrame(_conf_dist), x="conf_bucket", y="picks",
                        labels={"conf_bucket": "Confidence (5-pt bucket)", "picks": "Picks"},
                        title="Distribution of Confidence Scores",
                        color_discrete_sequence=["#00D559"],
                    )
                    _fig_cd.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=280,
                    )
                    st.plotly_chart(_fig_cd, use_container_width=True)
                except ImportError:
                    st.dataframe(pd.DataFrame(_conf_dist), use_container_width=True, hide_index=True)

        # ── Player pick leaderboard ───────────────────────────────────────────────
        if _player_lb:
            with st.expander("🏆 Player Prediction Leaderboard (min 10 graded)", expanded=False):
                _df_plb = pd.DataFrame(_player_lb)
                try:
                    import plotly.express as _px
                    _fig_plb = _px.bar(
                        _df_plb.head(15), x="player_name", y="hit_rate_pct",
                        color="hit_rate_pct", color_continuous_scale="RdYlGn",
                        range_color=[40, 75],
                        labels={"player_name": "Player", "hit_rate_pct": "Hit Rate %"},
                        title="Top 15 Players by Prediction Hit Rate",
                        text_auto=".1f",
                    )
                    _fig_plb.add_hline(y=52.4, line_dash="dot", line_color="#F9C62B",
                                       annotation_text="52.4% breakeven")
                    _fig_plb.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", coloraxis_showscale=False, height=320,
                    )
                    st.plotly_chart(_fig_plb, use_container_width=True)
                except ImportError:
                    pass
                st.dataframe(_df_plb, use_container_width=True, hide_index=True)

        # ── Over/Under bias ───────────────────────────────────────────────────────
        if _ou_bias:
            with st.expander("⚖️ Over/Under Recommendation Bias (14 d)", expanded=False):
                _df_ou = pd.DataFrame(_ou_bias)
                try:
                    import plotly.express as _px
                    _fig_ou = _px.pie(
                        _df_ou, names="direction", values="picks",
                        title="OVER vs UNDER Pick Distribution",
                        color_discrete_map={"OVER": "#00D559", "UNDER": "#F24336"},
                    )
                    _fig_ou.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=280,
                    )
                    st.plotly_chart(_fig_ou, use_container_width=True)
                except ImportError:
                    st.dataframe(_df_ou, use_container_width=True, hide_index=True)
                if len(_df_ou) == 2:
                    _over_pct = float(_df_ou[_df_ou["direction"] == "OVER"]["pct"].iloc[0]) if "OVER" in _df_ou["direction"].values else 50.0
                    if abs(_over_pct - 50) > 10:
                        st.warning(f"⚠️ Bias detected: model recommends OVER {_over_pct:.1f}% of the time (healthy range: 40–60%).")
                    else:
                        st.success(f"✅ Bias is within healthy range: OVER {_over_pct:.1f}% / UNDER {100-_over_pct:.1f}%.")

    except Exception as _mi_exc:
        st.warning(f"Could not load model intelligence data: {_mi_exc}")

    st.divider()



with _tab_ops:
    # ═══════════════════════════════════════════════════════════
    # ROW 16 — User Engagement Depth
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">📈 User Engagement Depth</div><span class="adm-section-sub">Active sessions · peak-usage heatmap · page time · scores</span></div>', unsafe_allow_html=True)

    try:
        from tracking.database import get_database_connection as _gdc8

        # ── Top 10 most active users ──────────────────────────────────────────────
        _top_users = query_telemetry(
            """
            SELECT session_id,
                   COUNT(*) AS interactions,
                   COUNT(DISTINCT feature_name) AS unique_features,
                   COUNT(DISTINCT page) AS pages_visited,
                   MAX(timestamp) AS last_seen
            FROM telemetry_features
            WHERE timestamp >= ?
            GROUP BY session_id
            ORDER BY interactions DESC
            LIMIT 10
            """,
            (_14D_AGO,),
        )

        if _top_users:
            with st.expander("🔝 Top 10 Most Active Sessions (14 d)", expanded=True):
                st.dataframe(pd.DataFrame(_top_users), use_container_width=True, hide_index=True)

        # ── Peak usage heatmap (hour × weekday) ───────────────────────────────────
        _heatmap_rows = query_telemetry(
            """
            SELECT
                CAST(strftime('%H', timestamp) AS INTEGER) AS hour_of_day,
                CAST(strftime('%w', timestamp) AS INTEGER) AS day_of_week,
                COUNT(*) AS events
            FROM telemetry_features
            WHERE timestamp >= ?
            GROUP BY hour_of_day, day_of_week
            """,
            (_14D_AGO,),
        )

        if _heatmap_rows:
            with st.expander("🕐 Peak Usage Heatmap — Hour × Weekday (14 d)", expanded=False):
                try:
                    import plotly.graph_objects as _go
                    import numpy as _np
                    _dow_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                    _matrix = [[0] * 24 for _ in range(7)]
                    for _hr in _heatmap_rows:
                        _d = int(_hr.get("day_of_week", 0) or 0)
                        _h = int(_hr.get("hour_of_day", 0) or 0)
                        if 0 <= _d < 7 and 0 <= _h < 24:
                            _matrix[_d][_h] = int(_hr.get("events", 0) or 0)
                    _fig_hm = _go.Figure(data=_go.Heatmap(
                        z=_matrix,
                        x=[f"{h:02d}:00" for h in range(24)],
                        y=_dow_labels,
                        colorscale="Teal",
                        colorbar=dict(title="Events"),
                    ))
                    _fig_hm.update_layout(
                        title="Activity by Hour of Day × Day of Week",
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=320,
                        xaxis_title="Hour (UTC)", yaxis_title="Day",
                    )
                    st.plotly_chart(_fig_hm, use_container_width=True)
                except ImportError:
                    st.dataframe(pd.DataFrame(_heatmap_rows), use_container_width=True, hide_index=True)

        # ── Session duration / time-on-page estimate ──────────────────────────────
        _page_duration = query_telemetry(
            """
            SELECT page,
                   COUNT(*) AS total_events,
                   COUNT(DISTINCT session_id) AS sessions,
                   ROUND(CAST(COUNT(*) AS REAL) / COUNT(DISTINCT session_id), 1) AS events_per_session
            FROM telemetry_features
            WHERE timestamp >= ?
            GROUP BY page ORDER BY events_per_session DESC
            LIMIT 15
            """,
            (_7D_AGO,),
        )

        if _page_duration:
            with st.expander("⏱️ Engagement by Page (events/session as proxy for time-on-page)", expanded=False):
                try:
                    import plotly.express as _px
                    _fig_pd = _px.bar(
                        pd.DataFrame(_page_duration), x="page", y="events_per_session",
                        color="events_per_session", color_continuous_scale="Blues",
                        labels={"page": "Page", "events_per_session": "Events / Session"},
                        title="Events per Session by Page (engagement proxy)",
                        text_auto=".1f",
                    )
                    _fig_pd.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", coloraxis_showscale=False, height=300,
                    )
                    st.plotly_chart(_fig_pd, use_container_width=True)
                except ImportError:
                    st.dataframe(pd.DataFrame(_page_duration), use_container_width=True, hide_index=True)

        # ── Per-user engagement score from analytics_events ───────────────────────
        with _gdc8() as _eng_c:
            import sqlite3 as _sqlite3
            _eng_c.row_factory = _sqlite3.Row
            _eng_scores = [dict(r) for r in _eng_c.execute(
                """
                SELECT user_email,
                       COUNT(*) AS total_events,
                       SUM(CASE WHEN event_name='login'         THEN 3 ELSE 0 END) +
                       SUM(CASE WHEN event_name='analysis_run'  THEN 5 ELSE 0 END) +
                       SUM(CASE WHEN event_name='bet_logged'     THEN 4 ELSE 0 END) +
                       SUM(CASE WHEN event_name='page_view'     THEN 1 ELSE 0 END) AS engagement_score,
                       SUM(CASE WHEN event_name='analysis_run'  THEN 1 ELSE 0 END) AS analysis_runs,
                       SUM(CASE WHEN event_name='bet_logged'     THEN 1 ELSE 0 END) AS bets_logged,
                       MAX(SUBSTR(timestamp,1,10)) AS last_active
                FROM analytics_events
                WHERE user_email IS NOT NULL AND user_email != ''
                  AND timestamp >= ?
                GROUP BY user_email
                ORDER BY engagement_score DESC
                LIMIT 25
                """,
                (_14D_AGO,),
            ).fetchall()]

        if _eng_scores:
            with st.expander("🏅 Top 25 Users by Engagement Score (14 d)", expanded=False):
                st.caption("Scoring: login=3, analysis_run=5, bet_logged=4, page_view=1")
                st.dataframe(pd.DataFrame(_eng_scores), use_container_width=True, hide_index=True)

    except Exception as _eng_exc:
        st.warning(f"Could not load engagement data: {_eng_exc}")

    st.divider()


    # ═══════════════════════════════════════════════════════════
    # ROW 17 — Revenue / Subscription Operations
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">💳 Revenue & Subscriptions</div><span class="adm-section-sub">MRR trend · expiring subs · funnel · resets</span></div>', unsafe_allow_html=True)

    try:
        from tracking.database import get_database_connection as _gdc9

        with _gdc9() as _rev_c:
            import sqlite3 as _sqlite3
            _rev_c.row_factory = _sqlite3.Row

            # ── MRR trend by month ────────────────────────────────────────────────
            _mrr_trend = [dict(r) for r in _rev_c.execute(
                """
                SELECT SUBSTR(created_at,1,7) AS month,
                       LOWER(COALESCE(plan_tier,'free')) AS tier,
                       COUNT(*) AS subscribers
                FROM users
                WHERE LOWER(COALESCE(plan_tier,'free')) NOT IN ('free','admin')
                GROUP BY month, tier
                ORDER BY month
                """
            ).fetchall()]

            # ── Upcoming subscription expirations (7 days) ───────────────────────
            _expiring = [dict(r) for r in _rev_c.execute(
                """
                SELECT customer_email, plan_name, status,
                       SUBSTR(current_period_end,1,10) AS expires
                FROM subscriptions
                WHERE current_period_end IS NOT NULL
                  AND current_period_end <= datetime('now','+7 days')
                  AND current_period_end >= datetime('now')
                  AND status = 'active'
                ORDER BY current_period_end
                LIMIT 50
                """
            ).fetchall()]

            # ── Password reset completion rate ────────────────────────────────────
            _rst_issued = (dict(_rev_c.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE reset_token IS NOT NULL"
            ).fetchone() or {}) or {}).get("cnt", 0)
            _rst_completed = (dict(_rev_c.execute(
                "SELECT COUNT(*) AS cnt FROM analytics_events WHERE event_name='password_reset_complete'"
            ).fetchone() or {}) or {}).get("cnt", 0)
            _rst_requested = (dict(_rev_c.execute(
                "SELECT COUNT(*) AS cnt FROM analytics_events WHERE event_name IN ('password_reset','reset_requested')"
            ).fetchone() or {}) or {}).get("cnt", 0)

            # ── Signup funnel drop-off ────────────────────────────────────────────
            _step1_starts = (dict(_rev_c.execute(
                "SELECT COUNT(*) AS cnt FROM analytics_events WHERE event_name IN ('signup_step1','signup_start')"
            ).fetchone() or {}) or {}).get("cnt", 0)
            _step2_done = (dict(_rev_c.execute(
                "SELECT COUNT(*) AS cnt FROM analytics_events WHERE event_name IN ('signup_complete','signup')"
            ).fetchone() or {}) or {}).get("cnt", 0)
            _total_users_count = (dict(_rev_c.execute(
                "SELECT COUNT(*) AS cnt FROM users"
            ).fetchone() or {}) or {}).get("cnt", 0)

        # ── KPI row ───────────────────────────────────────────────────────────────
        _rv_c1, _rv_c2, _rv_c3, _rv_c4 = st.columns(4)
        _rv_c1.metric("Expiring Subs (7 d)",  len(_expiring))
        _rv_c2.metric("Pending Resets",       _rst_issued)
        _rv_c3.metric("Reset Completions",    _rst_completed)
        _rv_c4.metric("Total Registered",     _total_users_count)

        # ── MRR trend chart ───────────────────────────────────────────────────────
        if _mrr_trend:
            with st.expander("📅 Monthly Paid Subscriber Trend", expanded=True):
                _TIER_PRICES2 = {"sharp_iq": 9.99, "smart_money": 19.99, "insider_circle": 39.99}
                _df_mrr = pd.DataFrame(_mrr_trend)
                _df_mrr["mrr_contrib"] = _df_mrr.apply(
                    lambda r: r["subscribers"] * _TIER_PRICES2.get(r["tier"], 0), axis=1
                )
                try:
                    import plotly.express as _px
                    _fig_mrr = _px.bar(
                        _df_mrr, x="month", y="mrr_contrib", color="tier",
                        barmode="stack",
                        labels={"month": "Month", "mrr_contrib": "Est. MRR ($)", "tier": "Tier"},
                        title="Estimated MRR by Tier per Month",
                        color_discrete_map={
                            "sharp_iq": "#2D9EFF",
                            "smart_money": "#F9C62B",
                            "insider_circle": "#00D559",
                        },
                    )
                    _fig_mrr.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0", height=320,
                    )
                    st.plotly_chart(_fig_mrr, use_container_width=True)
                except ImportError:
                    st.dataframe(_df_mrr, use_container_width=True, hide_index=True)

        # ── Expiring subscriptions ────────────────────────────────────────────────
        if _expiring:
            with st.expander(f"⏰ Subscriptions Expiring Within 7 Days ({len(_expiring)})", expanded=True):
                st.dataframe(pd.DataFrame(_expiring), use_container_width=True, hide_index=True)
        else:
            st.caption("✅ No active subscriptions expiring in the next 7 days.")

        # ── Signup funnel ─────────────────────────────────────────────────────────
        with st.expander("🔄 Signup Funnel Drop-off", expanded=False):
            _funnel_steps = [
                {"step": "Started signup (step 1)", "count": _step1_starts or _total_users_count},
                {"step": "Completed signup",        "count": _step2_done or _total_users_count},
                {"step": "Total registered users",  "count": _total_users_count},
            ]
            try:
                import plotly.express as _px
                _fig_sf = _px.funnel(
                    pd.DataFrame(_funnel_steps), x="count", y="step",
                    title="Signup Funnel",
                    color_discrete_sequence=["#2D9EFF"],
                )
                _fig_sf.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0", height=280,
                )
                st.plotly_chart(_fig_sf, use_container_width=True)
            except ImportError:
                st.dataframe(pd.DataFrame(_funnel_steps), use_container_width=True, hide_index=True)

    except Exception as _rev_exc:
        st.warning(f"Could not load revenue data: {_rev_exc}")

    st.divider()


    # ═══════════════════════════════════════════════════════════
    # ROW 18 — Operations & Alerts
    # ═══════════════════════════════════════════════════════════

    st.markdown('<div class="adm-section-header"><div class="adm-section-accent"></div><div class="adm-section-title">🚨 Operations & Anomaly Alerts</div><span class="adm-section-sub">Error spikes · login surges · brute-force · data exports</span></div>', unsafe_allow_html=True)

    try:
        from tracking.database import get_database_connection as _gdc10

        with _gdc10() as _ops_c:
            import sqlite3 as _sqlite3
            _ops_c.row_factory = _sqlite3.Row

            # ── Error spike detection ─────────────────────────────────────────────
            _err_1h = query_telemetry(
                "SELECT COUNT(*) AS cnt FROM telemetry_errors WHERE timestamp >= ?",
                (_1H_AGO,),
            )
            _err_1h_count = (_err_1h[0]["cnt"] if _err_1h else 0) or 0
            _err_24h = query_telemetry(
                "SELECT COUNT(*) AS cnt FROM telemetry_errors WHERE timestamp >= ?",
                ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds"),),
            )
            _err_24h_count = (_err_24h[0]["cnt"] if _err_24h else 0) or 0

            # ── Login surge detection ─────────────────────────────────────────────
            _logins_1h = (dict(_ops_c.execute(
                "SELECT COUNT(*) AS cnt FROM analytics_events "
                "WHERE event_name='login' AND timestamp >= datetime('now','-1 hour')"
            ).fetchone() or {}) or {}).get("cnt", 0)

            _logins_24h = (dict(_ops_c.execute(
                "SELECT COUNT(*) AS cnt FROM analytics_events "
                "WHERE event_name='login' AND timestamp >= datetime('now','-24 hours')"
            ).fetchone() or {}) or {}).get("cnt", 0)

            # ── Brute-force candidates (5+ fails, not yet locked) ─────────────────
            _brute_candidates = [dict(r) for r in _ops_c.execute(
                """
                SELECT email, failed_login_count,
                       COALESCE(lockout_until,'—') AS lockout_until
                FROM users
                WHERE failed_login_count >= 5
                  AND (lockout_until IS NULL OR lockout_until <= datetime('now'))
                ORDER BY failed_login_count DESC
                LIMIT 20
                """
            ).fetchall()]

        # ── Anomaly flag panel ────────────────────────────────────────────────────
        _alerts = []
        if _err_1h_count > 10:
            _alerts.append(f"🔴 **Error spike**: {_err_1h_count} errors in the last hour")
        if _logins_1h > 50:
            _alerts.append(f"🟡 **Login surge**: {_logins_1h} logins in the last hour")
        if _brute_candidates:
            _alerts.append(f"🔴 **Brute-force risk**: {len(_brute_candidates)} account(s) with 5+ failed logins, not yet locked")

        if _alerts:
            for _alert in _alerts:
                st.warning(_alert)
        else:
            st.success("✅ No anomalies detected right now.")

        # ── Alert metric row ──────────────────────────────────────────────────────
        _op_c1, _op_c2, _op_c3, _op_c4 = st.columns(4)
        _op_c1.metric("Errors (1 h)",   _err_1h_count,  delta="⚠️" if _err_1h_count > 10 else None, delta_color="inverse")
        _op_c2.metric("Errors (24 h)",  _err_24h_count)
        _op_c3.metric("Logins (1 h)",   _logins_1h,     delta="⚠️" if _logins_1h > 50 else None, delta_color="inverse")
        _op_c4.metric("Logins (24 h)",  _logins_24h)

        # ── Brute-force candidates ────────────────────────────────────────────────
        if _brute_candidates:
            with st.expander(f"🔐 Brute-force Risk Accounts ({len(_brute_candidates)})", expanded=True):
                st.dataframe(pd.DataFrame(_brute_candidates), use_container_width=True, hide_index=True)

        # ── Data export buttons ───────────────────────────────────────────────────
        with st.expander("⬇️ Data Exports (CSV)", expanded=False):
            _ex_c1, _ex_c2, _ex_c3 = st.columns(3)

            try:
                from tracking.database import get_database_connection as _gdc_ex
                with _gdc_ex() as _ex_c:
                    import sqlite3 as _sqlite3
                    _ex_c.row_factory = _sqlite3.Row

                    _users_csv = pd.DataFrame([dict(r) for r in _ex_c.execute(
                        "SELECT user_id,email,display_name,plan_tier,created_at,last_login_at,is_admin FROM users ORDER BY created_at DESC"
                    ).fetchall()])
                    _bets_csv = pd.DataFrame([dict(r) for r in _ex_c.execute(
                        "SELECT bet_id,bet_date,player_name,stat_type,direction,platform,tier,result,edge_percentage,confidence_score FROM bets ORDER BY created_at DESC LIMIT 5000"
                    ).fetchall()])
                    _picks_csv = pd.DataFrame([dict(r) for r in _ex_c.execute(
                        "SELECT pick_id,pick_date,player_name,stat_type,direction,platform,tier,result,edge_percentage,confidence_score FROM all_analysis_picks ORDER BY created_at DESC LIMIT 5000"
                    ).fetchall()])

                _ex_c1.download_button(
                    "👥 User Roster CSV",
                    data=_users_csv.to_csv(index=False).encode("utf-8"),
                    file_name=f"user_roster_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="_admin_export_users",
                )
                _ex_c2.download_button(
                    "📊 Bet History CSV",
                    data=_bets_csv.to_csv(index=False).encode("utf-8"),
                    file_name=f"bet_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="_admin_export_bets",
                )
                _ex_c3.download_button(
                    "⚡ Analysis Picks CSV",
                    data=_picks_csv.to_csv(index=False).encode("utf-8"),
                    file_name=f"analysis_picks_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="_admin_export_picks",
                )
            except Exception as _exp_err:
                st.warning(f"Export error: {_exp_err}")

    except Exception as _ops_exc:
        st.warning(f"Could not load operations data: {_ops_exc}")
