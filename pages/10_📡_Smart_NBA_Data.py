# ============================================================
# FILE: pages/9_📡_Smart_NBA_Data.py
# PURPOSE: Streamlit page — Smart NBA Data hub.
#          Consolidated data refresh control panel with readiness
#          scoring, activity log, pre-flight checks, player stats,
#          stat leaders, team stats, standings, playoff picture,
#          and export / explorer tools.
# ============================================================

import datetime
import json
import os
import sqlite3
import io
import zipfile
import contextlib
import traceback

import streamlit as st
from utils.rbac import has_permission, permission_gate
import pandas as pd

# ── Data layer imports ─────────────────────────────────────────
from data.data_manager import (
    load_players_data,
    load_teams_data,
)
from data.nba_data_service import (
    get_todays_games,
    get_player_stats,
    get_team_stats,
    get_all_data,
    get_todays_players,
    get_all_todays_data,
    load_last_updated,
)

# ETL refresh functions
try:
    from data.nba_data_service import refresh_from_etl, full_refresh_from_etl
    _ETL_AVAILABLE = True
except ImportError:
    _ETL_AVAILABLE = False

# ETL database status
try:
    from data.etl_data_service import is_db_available, get_db_counts, get_db_freshness
    _ETL_DB_AVAILABLE = is_db_available()
    _ETL_DB_COUNTS = get_db_counts() if _ETL_DB_AVAILABLE else {}
    _ETL_DB_FRESHNESS = get_db_freshness() if _ETL_DB_AVAILABLE else {}
except Exception:
    _ETL_DB_AVAILABLE = False
    _ETL_DB_COUNTS = {}
    _ETL_DB_FRESHNESS = {}

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Smart NBA Data — SmartBetPro NBA",
    page_icon="📡",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Smart NBA Data")
from utils.seo import inject_page_seo
inject_page_seo("Smart NBA Data")

from styles.theme import (
    get_global_css,
    get_neural_header_html,
    get_education_box_html,
    get_action_card_html,
    get_health_card_html,
    get_readiness_bar_html,
    get_freshness_timeline_html,
    get_preflight_checklist_html,
    get_data_feed_css,
)

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_data_feed_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Hero Banner + Floating Widget ─────────────
from utils.components import inject_joseph_floating, render_joseph_hero_banner, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_smart_nba_data"
render_joseph_hero_banner()
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()


# ============================================================
# SECTION: Unified Error Handler
# ============================================================

def _add_activity(msg: str) -> None:
    """Append a timestamped message to the activity log."""
    log = st.session_state.setdefault("_df_activity_log", [])
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    log.append(f"[{ts}] {msg}")
    # Keep last 100 entries
    if len(log) > 100:
        st.session_state["_df_activity_log"] = log[-100:]


@contextlib.contextmanager
def safe_action(action_name: str, status_container=None):
    """Context manager for unified error handling around data actions."""
    _add_activity(f"▶ Started: {action_name}")
    errors = st.session_state.setdefault("_df_errors", [])
    try:
        yield
        _add_activity(f"✅ Completed: {action_name}")
    except Exception as exc:
        err_str = str(exc)
        # Ignore WebSocket errors (Streamlit connection drops)
        if "WebSocketClosedError" in err_str or "StreamClosedError" in err_str:
            return
        error_msg = f"❌ {action_name} failed: {err_str}"
        errors.append(error_msg)
        _add_activity(error_msg)
        if status_container:
            status_container.error(error_msg)
        else:
            st.error(error_msg)


# ============================================================
# SECTION: Staleness Helpers
# ============================================================

def _staleness_badge(timestamp_str, warn_hours=4.0, error_hours=24.0):
    """Return (badge_html, age_hours) for a data timestamp."""
    if not timestamp_str:
        return ('<span style="display:inline-flex;align-items:center;gap:4px;'
                'background:rgba(85,60,154,0.25);color:#b794f4;padding:3px 10px;'
                'border-radius:20px;font-size:0.75rem;font-weight:700;'
                'font-family:\'JetBrains Mono\',monospace;'
                'border:1px solid rgba(85,60,154,0.3);">'
                '<span class="df-dot-stale" style="width:6px;height:6px;background:#b794f4;'
                'box-shadow:0 0 4px rgba(183,148,244,0.6);"></span>NEVER</span>'), None
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str)
        age_h = (datetime.datetime.now() - dt).total_seconds() / 3600
        if age_h < warn_hours:
            bg, color, dot_cls = "rgba(0,213,89,0.10)", "#00D559", "df-dot-live"
            border_c = "rgba(0,213,89,0.25)"
            label = f"FRESH — {age_h:.0f}h ago"
        elif age_h < error_hours:
            bg, color, dot_cls = "rgba(255,204,0,0.10)", "#F9C62B", "df-dot-warn"
            border_c = "rgba(255,204,0,0.25)"
            label = f"AGING — {age_h:.0f}h ago"
        else:
            bg, color, dot_cls = "rgba(255,68,68,0.10)", "#F24336", "df-dot-stale"
            border_c = "rgba(255,68,68,0.25)"
            label = f"STALE — {age_h:.1f}h ago"
        badge = (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{bg};color:{color};padding:3px 10px;'
            f'border-radius:20px;font-size:0.75rem;font-weight:700;'
            f'font-family:\'JetBrains Mono\',monospace;'
            f'border:1px solid {border_c};">'
            f'<span class="{dot_cls}" style="width:6px;height:6px;"></span>{label}</span>'
        )
        return badge, age_h
    except Exception:
        return ('<span style="display:inline-flex;align-items:center;gap:4px;'
                'background:rgba(85,60,154,0.25);color:#b794f4;padding:3px 10px;'
                'border-radius:20px;font-size:0.75rem;font-weight:700;'
                'font-family:\'JetBrains Mono\',monospace;'
                'border:1px solid rgba(85,60,154,0.3);">'
                'UNKNOWN</span>'), None


def _health_bar(age_h, max_age=24.0):
    """Return a colored health bar HTML string with glow effect."""
    if age_h is None:
        pct, color = 0, "#553c9a"
    else:
        freshness = max(0.0, 1.0 - age_h / max_age)
        pct = round(freshness * 100)
        color = "#00D559" if pct > 70 else ("#F9C62B" if pct > 30 else "#F24336")
    return (
        f'<div style="height:6px;background:rgba(13,18,32,0.80);border-radius:3px;'
        f'margin:8px 0;border:1px solid rgba(0,213,89,0.04);">'
        f'<div style="height:6px;width:{pct}%;background:{color};border-radius:3px;'
        f'box-shadow:0 0 6px {color};transition:width 0.4s ease;"></div>'
        f'</div>'
        f'<div style="font-size:0.72rem;color:rgba(192,208,232,0.50);'
        f'font-family:\'JetBrains Mono\',monospace;">Health: {pct}%</div>'
    )


def _compute_readiness():
    """Compute a session readiness score (0-100) from data freshness."""
    timestamps = load_last_updated()

    # When last_updated.json is empty but the ETL DB has data, derive
    # freshness timestamps from the database so the Data Source Status
    # section populates correctly.
    if not timestamps and _ETL_DB_FRESHNESS:
        timestamps = dict(_ETL_DB_FRESHNESS)

    todays_games = st.session_state.get("todays_games", [])

    scores = []
    source_ages = []

    # Players
    p_badge, p_age = _staleness_badge(timestamps.get("players"), 6.0, 24.0)
    p_count = len(load_players_data())
    if p_age is not None and p_count > 0:
        scores.append(max(0, 100 - p_age * 4))
    elif p_count > 0:
        # DB has players but no timestamp — treat as moderately fresh
        scores.append(60)
        p_age = 12.0  # synthetic age for display
    else:
        scores.append(0)
    source_ages.append(("Players", "👤", p_age if p_count > 0 or p_age is not None else None))

    # Teams
    t_badge, t_age = _staleness_badge(timestamps.get("teams"), 12.0, 48.0)
    t_count = len(load_teams_data())
    if t_age is not None and t_count > 0:
        scores.append(max(0, 100 - t_age * 2))
    elif t_count > 0:
        scores.append(60)
        t_age = 12.0
    else:
        scores.append(0)
    source_ages.append(("Teams", "🏟️", t_age if t_count > 0 or t_age is not None else None))

    # Games
    if todays_games:
        scores.append(100)
        source_ages.append(("Tonight's Games", "🏀", 0.0))
    else:
        scores.append(0)
        source_ages.append(("Tonight's Games", "🏀", None))

    # Injuries
    inj_badge, inj_age = _staleness_badge(timestamps.get("injuries"), 4.0, 12.0)
    if inj_age is not None:
        scores.append(max(0, 100 - inj_age * 6))
    else:
        scores.append(0)
    source_ages.append(("Injuries", "🏥", inj_age))

    # Props
    cached_props = st.session_state.get("platform_props", [])
    if cached_props:
        scores.append(80)
        source_ages.append(("Props", "📊", 1.0))
    else:
        scores.append(0)
        source_ages.append(("Props", "📊", None))

    readiness = int(sum(scores) / max(len(scores), 1))
    return readiness, source_ages, timestamps


# ============================================================
# SECTION: Page Header — Neural Network Header
# ============================================================

st.markdown(get_neural_header_html(
    "📡 SMART NBA DATA",
    "REAL-TIME NBA DATA PIPELINE • PLAYER STATS • STANDINGS • STAT LEADERS • SPORTSBOOK PROPS"
), unsafe_allow_html=True)

st.markdown(
    '<div style="text-align:center;color:rgba(192,208,232,0.60);font-size:0.88rem;'
    'margin:-12px 0 16px;line-height:1.6;">'
    'Your complete NBA data hub — pull real-time stats, browse league leaders, '
    'view standings, playoff picture, and live prop lines from '
    '<span style="color:#00D559;font-weight:600;">PrizePicks</span>, '
    '<span style="color:#F9C62B;font-weight:600;">Underdog Fantasy</span>, and '
    '<span style="color:#00a0ff;font-weight:600;">DraftKings Pick6</span>. '
    'Update before each betting session for maximum accuracy.</div>',
    unsafe_allow_html=True,
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Smart NBA Data — Your Complete NBA Data Hub
    
    Smart NBA Data connects to **live NBA data sources** to keep your analysis accurate and current.
    Browse player stats, stat leaders, team stats, standings, and the playoff picture — all in one place.
    
    **Recommended Daily Workflow**
    1. **Quick Setup tab** → Click "One-Click Full Setup" or "Smart ETL Update"
    2. **Props & Enrichment tab** → Load live prop lines from sportsbooks
    3. **NBA Data Hub tab** → Browse player stats, stat leaders, team stats, standings & playoff picture
    4. Check the **Session Readiness** score at the top — aim for 80%+
    
    **Data Sources**
    - Real-time NBA player stats, team metrics, and game logs
    - League leaders across all stat categories
    - Conference standings and playoff picture
    - Live odds from PrizePicks, Underdog Fantasy, and DraftKings Pick6
    
    💡 **Pro Tips:**
    - Always update data BEFORE running analysis — stale data leads to bad predictions
    - The readiness score and freshness timeline show exactly what needs updating
    - Use "Fix All" to quickly bring stale data up to date
    """)

st.markdown("")  # spacing

# ============================================================
# SECTION: Session Readiness + Freshness Timeline
# ============================================================

readiness_score, source_ages, timestamps = _compute_readiness()

st.markdown(get_readiness_bar_html(readiness_score), unsafe_allow_html=True)

# Data freshness timeline
st.markdown(
    '<div class="df-section-head" style="margin-top:16px;">DATA SOURCE STATUS</div>'
    '<div class="df-section-sub">Real-time freshness monitoring across all data pipelines</div>',
    unsafe_allow_html=True,
)
st.markdown(get_freshness_timeline_html(source_ages), unsafe_allow_html=True)

# Show ETL DB summary when available
if _ETL_DB_AVAILABLE and _ETL_DB_COUNTS:
    _p_cnt = _ETL_DB_COUNTS.get("players", 0)
    _g_cnt = _ETL_DB_COUNTS.get("games", 0)
    _l_cnt = _ETL_DB_COUNTS.get("logs", 0)
    if _p_cnt > 0 or _g_cnt > 0:
        st.markdown(
            f'<div style="text-align:center;color:rgba(192,208,232,0.55);font-size:0.78rem;'
            f'margin:4px 0 8px;font-family:\'JetBrains Mono\',monospace;">'
            f'ETL DB: <span style="color:#00D559;">{_p_cnt:,}</span> players · '
            f'<span style="color:#00D559;">{_g_cnt:,}</span> games · '
            f'<span style="color:#00D559;">{_l_cnt:,}</span> logs</div>',
            unsafe_allow_html=True,
        )

# ── Staleness warning ──────────────────────────────────────────
try:
    from data.nba_data_service import get_teams_staleness_warning
    _stale_warning = get_teams_staleness_warning()
    if _stale_warning:
        st.warning(f"⏰ {_stale_warning}")
except Exception:
    pass


# ── Notification / Alert banner ────────────────────────────────
_alert_threshold = st.session_state.get("_df_alert_threshold_hours", None)
if _alert_threshold is not None:
    # Check if any source exceeds threshold
    stale_sources = [label for label, _, age in source_ages if age is not None and age > _alert_threshold]
    never_sources = [label for label, _, age in source_ages if age is None]
    if stale_sources or never_sources:
        msg_parts = []
        if stale_sources:
            msg_parts.append(f"**{', '.join(stale_sources)}** older than {_alert_threshold}h")
        if never_sources:
            msg_parts.append(f"**{', '.join(never_sources)}** never loaded")
        st.warning(f"🔔 Data Alert: {' · '.join(msg_parts)} — update recommended before analyzing!")
st.markdown("")  # spacing


# ── Pre-Flight Check ──────────────────────────────────────────
todays_games = st.session_state.get("todays_games", [])
players_data = load_players_data()
teams_data = load_teams_data()

p_badge, p_age = _staleness_badge(timestamps.get("players"), 6.0)
t_badge, t_age = _staleness_badge(timestamps.get("teams"), 12.0)
inj_badge, inj_age = _staleness_badge(timestamps.get("injuries"), 4.0)

checks = [
    ("Games loaded", bool(todays_games), f"{len(todays_games)} game(s)" if todays_games else "No games loaded"),
    ("Players fresh", p_age is not None and p_age < 6, f"{len(players_data)} players" + (f" ({p_age:.0f}h ago)" if p_age else "")),
    ("Teams fresh", t_age is not None and t_age < 12, f"{len(teams_data)} teams" + (f" ({t_age:.0f}h ago)" if t_age else "")),
    ("Injuries current", inj_age is not None and inj_age < 4, f"{inj_age:.0f}h ago" if inj_age else "Never loaded"),
]

all_ok = all(ok for _, ok, _ in checks)
if not all_ok:
    with st.expander("🔍 Pre-Flight Check" + (" ⚠️" if not all_ok else " ✅"), expanded=not all_ok):
        st.markdown(get_preflight_checklist_html(checks), unsafe_allow_html=True)
        if st.button("🔧 Fix All — Run One-Click Setup", key="preflight_fix_all"):
            st.session_state["update_action"] = "one_click"
            st.rerun()

st.markdown("")  # spacing


# ============================================================
# SECTION: Workflow Wizard (Tabbed Interface)
# ============================================================

st.markdown(
    '<div class="df-section-head">WORKFLOW WIZARD</div>'
    '<div class="df-section-sub">Select a tab below to configure and execute data operations</div>',
    unsafe_allow_html=True,
)

if "update_action" not in st.session_state:
    st.session_state["update_action"] = None

tab_quick, tab_advanced, tab_props, tab_nba_data = st.tabs([
    "⚡ Quick Setup",
    "🔧 Advanced",
    "📊 Props & Enrichment",
    "🏀 NBA Data Hub",
])


# ── TAB 1: Quick Setup ──────────────────────────────────────
with tab_quick:
    st.markdown(get_education_box_html(
        "📖 Quick Setup",
        """
        <strong>One-Click Full Setup</strong>: Games → rosters → player stats → team stats in one click.<br><br>
        <strong>Smart ETL Update</strong>: Fastest option — pulls only new game logs from the database (~30 seconds).<br><br>
        <strong>Smart Update (Today's Teams)</strong>: Retrieves stats for only tonight's teams (~1-2 min).
        """
    ), unsafe_allow_html=True)

    # ── One-Click Full Setup ─────────────────────────────────────
    st.markdown(get_action_card_html(
        "🏀 ONE-CLICK FULL SETUP",
        "Retrieves tonight's games → current rosters → player stats → team stats. "
        "<strong>Everything in one click.</strong> The best choice for daily setup.",
        icon_color="#e94560",
    ), unsafe_allow_html=True)

    oc_c1, oc_c2 = st.columns([1, 3])
    with oc_c1:
        if st.button("🏀 One-Click Full Setup", type="primary", key="btn_one_click", use_container_width=True):
            st.session_state["update_action"] = "one_click"
            st.rerun()
    with oc_c2:
        st.caption("Best for first-time setup each day. Retrieves games first, then only tonight's team players (~1-3 min).")

    st.markdown("")

    # ── ETL Database Section (Primary Path) ──────────────────────
    if _ETL_DB_AVAILABLE:
        _p = _ETL_DB_COUNTS.get("players", 0)
        _g = _ETL_DB_COUNTS.get("games", 0)
        _l = _ETL_DB_COUNTS.get("logs", 0)
        st.markdown(get_action_card_html(
            "🗄️ ETL DATABASE — ACTIVE",
            f"<span style='font-family:JetBrains Mono,monospace;'><strong>{_p:,}</strong> players · "
            f"<strong>{_g:,}</strong> games · <strong>{_l:,}</strong> logs</span>. "
            f"Use <em>Smart ETL Update</em> to add new games, or <em>Full ETL Pull</em> to rebuild from scratch.",
            icon_color="#00D559",
        ), unsafe_allow_html=True)
    else:
        st.markdown(get_action_card_html(
            "🗄️ ETL DATABASE — EMPTY",
            "No ETL data yet. Run <strong>Full ETL Pull</strong> or <code>python -m etl.initial_pull</code> to populate.",
            icon_color="#F9C62B",
        ), unsafe_allow_html=True)

    etl_c1, etl_c2, etl_c3 = st.columns([1, 1, 2])
    with etl_c1:
        if st.button("⚡ Smart ETL Update", type="primary", key="btn_etl_smart", use_container_width=True,
                      help="Incremental update — fetches only new games since last stored date"):
            st.session_state["update_action"] = "etl_smart"
            st.rerun()
    with etl_c2:
        if st.button("🔄 Full ETL Pull", key="btn_etl_full", use_container_width=True,
                      help="Re-pull entire season from nba_api and repopulate db/smartai_nba.db"):
            st.session_state["update_action"] = "etl_full"
            st.rerun()
    with etl_c3:
        st.caption(
            "**Smart ETL** is the fastest update (~30s). **Full ETL** rebuilds the entire season (~60s)."
        )

    st.markdown("")

    # ── Smart Update (Today's Teams) ─────────────────────────────
    st.markdown(get_action_card_html(
        "⚡ SMART UPDATE — TODAY'S TEAMS ONLY",
        "Retrieves team rosters using <code>CommonTeamRoster</code> (current, post-trade) "
        "then game logs for only those players. Takes <strong>1–2 minutes</strong> instead of 10–15.",
        icon_color="#00D559",
    ), unsafe_allow_html=True)

    sm_c1, sm_c2 = st.columns([1, 3])
    with sm_c1:
        if st.button("⚡ Smart Update (Today's Teams)", key="btn_smart", use_container_width=True,
                      help="Fastest: retrieves only players on teams playing tonight"):
            # Pre-flight: auto-load games if missing
            if not st.session_state.get("todays_games"):
                st.session_state["update_action"] = "smart_with_games"
            else:
                st.session_state["update_action"] = "smart"
            st.rerun()
    with sm_c2:
        _tg_hint = st.session_state.get("todays_games", [])
        if _tg_hint:
            teams_playing = set()
            for g in _tg_hint:
                teams_playing.add(g.get("home_team", ""))
                teams_playing.add(g.get("away_team", ""))
            teams_playing.discard("")
            st.caption(f"Tonight's teams: {', '.join(sorted(teams_playing))}")
        else:
            st.caption("ℹ️ Games will be auto-loaded before Smart Update runs.")


# ── TAB 2: Advanced ──────────────────────────────────────────
with tab_advanced:
    st.markdown(
        '<div style="color:rgba(192,208,232,0.65);font-size:0.88rem;margin-bottom:12px;">'
        'Granular controls — use when you need to update a specific data type.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="df-section-head" style="font-size:0.95rem;">INDIVIDUAL DATA UPDATES</div>',
        unsafe_allow_html=True,
    )
    btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)

    with btn_c1:
        if st.button("🏟️ Get Tonight's Games", key="btn_games", use_container_width=True):
            st.session_state["update_action"] = "games"
            st.rerun()
    with btn_c2:
        if st.button("👤 Update All Players (Slow)", key="btn_players", use_container_width=True,
                      help="Pull current season averages for ALL NBA players (~500, 5-15 min)"):
            st.session_state["update_action"] = "players"
            st.rerun()
    with btn_c3:
        if st.button("🏆 Update Team Stats", key="btn_teams", use_container_width=True):
            st.session_state["update_action"] = "teams"
            st.rerun()
    with btn_c4:
        if st.button("🔄 Update Everything (Full)", key="btn_all", use_container_width=True,
                      help="Update all data: games, all players, teams (slow, 10-15 min)"):
            st.session_state["update_action"] = "all"
            st.rerun()

    st.markdown("")

    # ── Injury Report ────────────────────────────────────────────
    st.markdown(get_action_card_html(
        "🏥 REAL-TIME INJURY REPORT",
        "Retrieves live injury designations with NBA CDN feed as fallback — "
        "real-time GTD/Out/Doubtful status, specific injury details, and expected return dates.",
        icon_color="#2D9EFF",
    ), unsafe_allow_html=True)

    inj_c1, inj_c2 = st.columns([1, 3])
    with inj_c1:
        if st.button("🔄 Refresh Injury Report", key="btn_injury", use_container_width=True):
            st.session_state["update_action"] = "injury_report"
            st.rerun()
    with inj_c2:
        _last_scraped = st.session_state.get("injury_report_last_scraped")
        if _last_scraped:
            st.caption(f"Last retrieved: {_last_scraped}")
        else:
            st.caption("Click to pull real-time injury designations.")

    st.markdown("")

    # ── Standings & News ─────────────────────────────────────────
    st.markdown(get_action_card_html(
        "📊 NBA STANDINGS & PLAYER NEWS",
        "Retrieves current NBA standings and recent player/team news — "
        "conference ranks, W-L records, streaks, injury news, and trade updates.",
        icon_color="#00c9ff",
    ), unsafe_allow_html=True)

    sn_c1, sn_c2 = st.columns([1, 3])
    with sn_c1:
        if st.button("📊 Refresh Standings & News", key="btn_standings", use_container_width=True):
            st.session_state["update_action"] = "standings_news"
            st.rerun()
    with sn_c2:
        _last_sn = st.session_state.get("standings_news_last_loaded")
        if _last_sn:
            st.caption(f"Last retrieved: {_last_sn}")
        else:
            st.caption("Retrieves conference standings and recent player/team news.")

    st.markdown("")

    # ── Auto-Refresh / Scheduling ────────────────────────────────
    st.markdown(
        '<div class="df-section-head" style="font-size:0.95rem;">⏰ AUTO-REFRESH SETTINGS</div>',
        unsafe_allow_html=True,
    )
    ar_c1, ar_c2, ar_c3 = st.columns(3)
    with ar_c1:
        auto_refresh = st.toggle(
            "Auto-refresh reminder",
            value=st.session_state.get("_df_auto_refresh_enabled", False),
            key="toggle_auto_refresh",
            help="Show a reminder when data is older than the threshold",
        )
        st.session_state["_df_auto_refresh_enabled"] = auto_refresh
    with ar_c2:
        threshold = st.number_input(
            "Alert threshold (hours)",
            min_value=1, max_value=48, value=st.session_state.get("_df_alert_threshold_hours_val", 6),
            key="auto_refresh_hours",
        )
        if auto_refresh:
            st.session_state["_df_alert_threshold_hours"] = threshold
            st.session_state["_df_alert_threshold_hours_val"] = threshold
        else:
            st.session_state["_df_alert_threshold_hours"] = None
    with ar_c3:
        _last_check = st.session_state.get("_df_last_auto_check")
        if _last_check:
            st.caption(f"Last check: {_last_check}")
        else:
            st.caption("No auto-checks yet.")
        if st.button("🔄 Run Check Now", key="btn_run_check"):
            st.session_state["_df_last_auto_check"] = datetime.datetime.now().strftime("%H:%M:%S")
            st.rerun()

    # ── Notification Alerts ────────────────────────────────────
    st.markdown(
        '<div class="df-section-head" style="font-size:0.95rem;">🔔 NOTIFICATION SETTINGS</div>',
        unsafe_allow_html=True,
    )
    notif_c1, notif_c2 = st.columns(2)
    with notif_c1:
        notif_stale = st.toggle(
            "Alert when data is stale",
            value=st.session_state.get("_df_notif_stale", False),
            key="toggle_notif_stale",
        )
        st.session_state["_df_notif_stale"] = notif_stale
        if notif_stale:
            st.session_state["_df_alert_threshold_hours"] = st.session_state.get("_df_alert_threshold_hours_val", 6)
    with notif_c2:
        notif_injury = st.toggle(
            "Alert on new injuries for tracked players",
            value=st.session_state.get("_df_notif_injury", False),
            key="toggle_notif_injury",
        )
        st.session_state["_df_notif_injury"] = notif_injury


# ── TAB 3: Props & Enrichment ────────────────────────────────
with tab_props:
    # ── Platform Props Section ────────────────────────────────
    st.markdown(
        '<div class="df-section-head" style="font-size:0.95rem;">📊 LIVE PLATFORM PROPS</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:rgba(192,208,232,0.60);font-size:0.88rem;margin-bottom:12px;">'
        'Pull <strong style="color:#00D559;">live prop lines</strong> directly from betting platforms. '
        'Platforms only list active players playing tonight — so this also '
        'acts as a real-time active roster check.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(get_education_box_html(
        "📖 How Platform Prop Loading Works",
        """
        <strong>Sportsbook Lines</strong>: Retrieves tonight's NBA prop lines from 
        PrizePicks, Underdog Fantasy, and DraftKings Pick6.<br><br>
        <strong>Cross-platform comparison</strong>: After loading, the app shows all lines 
        side-by-side so you can see which platform has the best line for each pick.
        """
    ), unsafe_allow_html=True)

    # Import platform service
    try:
        from data.sportsbook_service import (
            get_all_sportsbook_props,
            summarize_props_by_platform,
            find_new_players_from_props,
            build_cross_platform_comparison,
            refresh_props_if_stale,
        )
        from data.data_manager import (
            save_platform_props_to_session,
            load_platform_props_from_session,
            save_platform_props_to_csv,
        )
        _SPORTSBOOK_SERVICE_AVAILABLE = True
    except ImportError as _pf_err:
        _SPORTSBOOK_SERVICE_AVAILABLE = False
        st.warning(f"⚠️ Platform service not available: {_pf_err}")

    # ── Auto-refresh stale props on page load ─────────────────
    if _SPORTSBOOK_SERVICE_AVAILABLE:
        try:
            refresh_props_if_stale(st.session_state)
        except Exception:
            pass  # Best-effort

    if _SPORTSBOOK_SERVICE_AVAILABLE:
        _dk_on = st.session_state.get("load_draftkings_enabled", True)
        _dk_key = st.session_state.get("odds_api_key", "").strip()

        _df_pp_col, _df_ud_col, _df_dk_col = st.columns(3)
        with _df_pp_col:
            _pp_on = st.checkbox("🟢 PrizePicks", value=True, key="datafeed_pp_checkbox")
        with _df_ud_col:
            _ud_on = st.checkbox("🟡 Underdog Fantasy", value=True, key="datafeed_ud_checkbox")
        with _df_dk_col:
            _dk_cb_on = st.checkbox(
                "🔵 DraftKings Pick6",
                value=_dk_on and bool(_dk_key),
                key="datafeed_dk_checkbox",
                disabled=not (_dk_on and bool(_dk_key)),
                help="Requires Odds API key — configure on ⚙️ Settings page." if not (_dk_on and bool(_dk_key)) else "",
            )

        # Platform status badges
        _pp_cls = "df-platform-badge df-badge-pp" if _pp_on else "df-platform-badge df-badge-off"
        _ud_cls = "df-platform-badge df-badge-ud" if _ud_on else "df-platform-badge df-badge-off"
        _dk_cls = "df-platform-badge df-badge-dk" if _dk_cb_on else "df-platform-badge df-badge-off"
        _pp_badge = f'<span class="{_pp_cls}"><span class="df-dot-live" style="width:6px;height:6px;"></span> PrizePicks</span>' if _pp_on else f'<span class="{_pp_cls}">⏸️ PrizePicks</span>'
        _ud_badge = f'<span class="{_ud_cls}"><span class="df-dot-live" style="width:6px;height:6px;background:#F9C62B;box-shadow:0 0 6px rgba(255,204,0,0.7);"></span> Underdog</span>' if _ud_on else f'<span class="{_ud_cls}">⏸️ Underdog</span>'
        _dk_badge = f'<span class="{_dk_cls}"><span class="df-dot-live" style="width:6px;height:6px;background:#00a0ff;box-shadow:0 0 6px rgba(0,160,255,0.7);"></span> DraftKings</span>' if _dk_cb_on else f'<span class="{_dk_cls}">⏸️ DraftKings</span>'
        st.markdown(f'<div style="margin:8px 0 14px;">{_pp_badge}{_ud_badge}{_dk_badge}</div>', unsafe_allow_html=True)
        st.caption("Toggle platforms above. DraftKings requires an Odds API key (⚙️ Settings page).")

        # Cached props info
        _cached_platform_props = load_platform_props_from_session(st.session_state)
        if _cached_platform_props:
            _cached_summary = summarize_props_by_platform(_cached_platform_props)
            _total_cached = sum(_cached_summary.values())
            st.info(
                f"📦 **{_total_cached} props cached** from last load: "
                + " | ".join(f"{plat}: {cnt}" for plat, cnt in _cached_summary.items())
            )

        # Load buttons
        _any_platform_on = _pp_on or _ud_on or _dk_cb_on
        _load_col1, _load_col2 = st.columns(2)
        with _load_col1:
            _load_dk = st.button(
                "🔵 Get DraftKings Only",
                disabled=not _dk_cb_on,
                key="btn_dk_only",
                use_container_width=True,
            )
        with _load_col2:
            _load_all = st.button(
                "🔄 Refresh All Props",
                type="primary",
                key="btn_refresh_props",
                use_container_width=True,
                disabled=not _any_platform_on,
            )

        # Execute prop loads
        _load_triggered = _load_all or _load_dk
        _load_dk_only = _load_dk and not _load_all

        if _load_triggered:
            with st.status("Loading live props from betting platforms...", expanded=True) as prop_status:
                with safe_action("Load Platform Props", prop_status):
                    _new_props = get_all_sportsbook_props(
                        include_prizepicks=_pp_on and not _load_dk_only,
                        include_underdog=_ud_on and not _load_dk_only,
                        include_draftkings=_dk_cb_on and (_load_all or _load_dk_only),
                        odds_api_key=_dk_key or None,
                    )

                    if _new_props:
                        save_platform_props_to_session(_new_props, st.session_state)
                        from data.data_manager import save_props_to_session
                        save_props_to_session(_new_props, st.session_state)
                        _saved_ok = save_platform_props_to_csv(_new_props)

                        _new_summary = summarize_props_by_platform(_new_props)
                        prop_status.update(label="✅ Props loaded!", state="complete")
                        st.success(
                            f"✅ Retrieved **{len(_new_props)} props** from "
                            + ", ".join(f"**{plat}** ({cnt})" for plat, cnt in _new_summary.items())
                            + (". Saved to `data/live_props.csv`." if _saved_ok else ".")
                        )
                        _add_activity(f"Props loaded: {len(_new_props)} total")

                        # Warn about new players
                        _players_check = load_players_data()
                        _new_players = find_new_players_from_props(_new_props, _players_check)
                        if _new_players:
                            with st.expander(f"⚠️ {len(_new_players)} players from platforms not in local database"):
                                st.markdown(
                                    "Consider running a **Smart Update** to retrieve their season stats."
                                )
                                for _np in _new_players[:20]:
                                    st.markdown(f"- {_np}")
                                if len(_new_players) > 20:
                                    st.caption(f"... and {len(_new_players) - 20} more")
                    else:
                        st.warning("⚠️ No props were returned. Check your internet connection and try again.")

        # ── Platform Props Comparison Dashboard ──────────────────
        _display_props = load_platform_props_from_session(st.session_state) if _SPORTSBOOK_SERVICE_AVAILABLE else []
        if _display_props:
            st.markdown("")
            st.markdown(
                '<div class="df-section-head" style="font-size:0.95rem;">📊 PROPS COMPARISON DASHBOARD</div>'
                '<div class="df-section-sub">Cross-platform line analysis and edge detection</div>',
                unsafe_allow_html=True,
            )

            # Grouped view by player — show cross-platform comparison
            try:
                _comparison = build_cross_platform_comparison(_display_props)
                if _comparison:
                    with st.expander(f"🔀 Cross-Platform Line Comparison ({len(_comparison)} players)", expanded=False):
                        _comp_rows = []
                        for item in _comparison:
                            _comp_rows.append({
                                "Player": item.get("player_name", ""),
                                "Stat": item.get("stat_type", ""),
                                "PrizePicks": item.get("prizepicks_line", "—"),
                                "Underdog": item.get("underdog_line", "—"),
                                "DraftKings": item.get("draftkings_line", "—"),
                                "Max Diff": item.get("max_difference", 0),
                            })
                        if _comp_rows:
                            _comp_df = pd.DataFrame(_comp_rows)
                            _comp_df = _comp_df.sort_values("Max Diff", ascending=False)
                            st.dataframe(_comp_df, hide_index=True, use_container_width=True)
            except Exception:
                pass

            with st.expander(f"📋 All Props ({len(_display_props)} total)", expanded=False):
                _preview_rows = []
                for _p in _display_props:
                    _preview_rows.append({
                        "Player": _p.get("player_name", ""),
                        "Team": _p.get("team", ""),
                        "Stat": _p.get("stat_type", ""),
                        "Line": _p.get("line", ""),
                        "Platform": _p.get("platform", ""),
                        "Date": _p.get("game_date", ""),
                    })
                st.dataframe(_preview_rows, hide_index=True, use_container_width=True)

    st.markdown("")

    # ── Deep Fetch: Advanced Stats Enrichment ────────────────────
    st.markdown(
        '<div class="df-section-head" style="font-size:0.95rem;">🔬 ADVANCED STATS ENRICHMENT</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:rgba(192,208,232,0.60);font-size:0.88rem;margin-bottom:12px;">'
        'Pre-fetch full advanced NBA data for tonight\'s games: team dashboards, '
        '5-man lineups, player estimated metrics, rotation data, and standings context.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("📖 What Does Deep Fetch Do?", expanded=False):
        st.markdown("""
        **🔬 Deep Fetch** pre-loads the following for each of tonight's games:

        | Data Type | Source | Benefit |
        |---|---|---|
        | Team game logs (last 10) | NBA Stats API | Recent blowout frequency, pace trends |
        | 5-man lineup stats | NBA Stats API | Rotation patterns, +/- data |
        | Player estimated metrics | NBA Stats API | Real pace, ortg, drtg, net rating |
        | Team dashboards | NBA Stats API | Home/away splits, rest-day performance |
        | League standings | NBA Stats API | Opponent record context |
        | Today's scoreboard | NBA Stats API | Live game status |

        **Note:** Deep Fetch respects the NBA API rate limit (1.5s delay per call).
        """)

    # Pre-flight: check ETL data before deep fetch
    _deep_fetch_games = st.session_state.get("todays_games", [])

    if st.button("🔬 Deep Fetch: Advanced Stats", key="btn_deep_fetch",
                  help="Pre-fetch advanced enrichment data for tonight's games"):
        if not _deep_fetch_games:
            # Auto-suggest loading games first
            if _ETL_DB_AVAILABLE:
                st.info("💡 No games loaded. Consider running **Smart ETL Update** first to load data, then try Deep Fetch.")
            st.warning("⚠️ No games loaded yet. Click **One-Click Full Setup** in the Quick Setup tab first.")
        else:
            st.session_state["update_action"] = "deep_fetch"
            st.rerun()


# ── TAB 4: NBA Data Hub ──────────────────────────────────────
with tab_nba_data:
    st.markdown(
        '<div style="color:rgba(192,208,232,0.65);font-size:0.88rem;margin-bottom:12px;">'
        'Browse live NBA data — player stats, stat leaders, team stats, conference standings, '
        'and the playoff picture.</div>',
        unsafe_allow_html=True,
    )

    _nba_sub_tab1, _nba_sub_tab2, _nba_sub_tab3, _nba_sub_tab4, _nba_sub_tab5 = st.tabs([
        "👤 Player Stats",
        "🏆 Stat Leaders",
        "🏟️ Team Stats",
        "📊 Standings",
        "🏀 Playoff Picture",
    ])

    # ── Sub-Tab: Player Stats ────────────────────────────────
    with _nba_sub_tab1:
        st.markdown(
            '<div class="df-section-head" style="font-size:0.95rem;">👤 PLAYER STATS</div>'
            '<div class="df-section-sub">Current season averages for all loaded players</div>',
            unsafe_allow_html=True,
        )

        _ps_players = load_players_data()
        if _ps_players:
            # Search / filter
            _ps_search = st.text_input("🔍 Search player by name:", key="nba_hub_player_search")
            _ps_filtered = _ps_players
            if _ps_search:
                _ps_filtered = [
                    p for p in _ps_players
                    if _ps_search.lower() in p.get("name", "").lower()
                ]

            # Sort options
            _ps_sort_col, _ps_sort_dir = st.columns([2, 1])
            with _ps_sort_col:
                _ps_sort = st.selectbox(
                    "Sort by:",
                    ["points_avg", "rebounds_avg", "assists_avg", "steals_avg", "blocks_avg",
                     "threes_avg", "minutes_avg", "name"],
                    index=0,
                    key="nba_hub_player_sort",
                )
            with _ps_sort_dir:
                _ps_dir = st.selectbox("Order:", ["Descending", "Ascending"], key="nba_hub_player_dir")

            _ps_reverse = _ps_dir == "Descending"
            try:
                _ps_filtered = sorted(
                    _ps_filtered,
                    key=lambda p: float(p.get(_ps_sort, 0) or 0) if _ps_sort != "name" else p.get("name", "").lower(),
                    reverse=_ps_reverse if _ps_sort != "name" else not _ps_reverse,
                )
            except (ValueError, TypeError):
                pass

            # Build display table
            _ps_rows = []
            for _p in _ps_filtered[:100]:
                _ps_rows.append({
                    "Player": _p.get("name", ""),
                    "Team": _p.get("team", ""),
                    "GP": _p.get("games_played", ""),
                    "MIN": _p.get("minutes_avg", ""),
                    "PTS": _p.get("points_avg", ""),
                    "REB": _p.get("rebounds_avg", ""),
                    "AST": _p.get("assists_avg", ""),
                    "STL": _p.get("steals_avg", ""),
                    "BLK": _p.get("blocks_avg", ""),
                    "3PM": _p.get("threes_avg", ""),
                    "TOV": _p.get("turnovers_avg", ""),
                    "FG%": _p.get("fg_pct", ""),
                })
            if _ps_rows:
                st.dataframe(_ps_rows, hide_index=True, use_container_width=True)
                st.caption(f"Showing {len(_ps_rows)} of {len(_ps_filtered)} players (max 100).")
            elif _ps_search:
                st.info(f"No players matching '{_ps_search}'.")
        else:
            st.info("No player data loaded yet. Use the **Quick Setup** tab to pull player stats.")

    # ── Sub-Tab: Stat Leaders ────────────────────────────────
    with _nba_sub_tab2:
        st.markdown(
            '<div class="df-section-head" style="font-size:0.95rem;">🏆 LEAGUE STAT LEADERS</div>'
            '<div class="df-section-sub">Top performers across key statistical categories</div>',
            unsafe_allow_html=True,
        )

        _sl_players = load_players_data()
        if _sl_players:
            _LEADER_CATEGORIES = [
                ("points_avg", "🔥 Scoring Leaders", "PTS"),
                ("rebounds_avg", "💪 Rebounding Leaders", "REB"),
                ("assists_avg", "🎯 Assist Leaders", "AST"),
                ("steals_avg", "🖐️ Steals Leaders", "STL"),
                ("blocks_avg", "🚫 Blocks Leaders", "BLK"),
                ("threes_avg", "🎯 Three-Point Leaders", "3PM"),
            ]

            _sl_top_n = st.slider("Show top N players:", min_value=5, max_value=25, value=10, key="nba_hub_leaders_n")

            for _cat_key, _cat_title, _cat_abbr in _LEADER_CATEGORIES:
                # Sort and get top N
                _sl_sorted = sorted(
                    [p for p in _sl_players if float(p.get(_cat_key, 0) or 0) > 0],
                    key=lambda p: float(p.get(_cat_key, 0) or 0),
                    reverse=True,
                )[:_sl_top_n]

                if _sl_sorted:
                    with st.expander(_cat_title, expanded=False):
                        _sl_rows = []
                        for _rank, _p in enumerate(_sl_sorted, 1):
                            _sl_rows.append({
                                "Rank": _rank,
                                "Player": _p.get("name", ""),
                                "Team": _p.get("team", ""),
                                _cat_abbr: _p.get(_cat_key, ""),
                                "GP": _p.get("games_played", ""),
                                "MIN": _p.get("minutes_avg", ""),
                            })
                        st.dataframe(_sl_rows, hide_index=True, use_container_width=True)
        else:
            st.info("No player data loaded yet. Use the **Quick Setup** tab to pull player stats.")

    # ── Sub-Tab: Team Stats ──────────────────────────────────
    with _nba_sub_tab3:
        st.markdown(
            '<div class="df-section-head" style="font-size:0.95rem;">🏟️ TEAM STATS</div>'
            '<div class="df-section-sub">Current season team metrics and performance data</div>',
            unsafe_allow_html=True,
        )

        _ts_teams = load_teams_data()
        if _ts_teams:
            _ts_sort = st.selectbox(
                "Sort by:",
                ["team_name", "pace", "ortg", "drtg", "net_rating", "wins", "losses"],
                index=0,
                key="nba_hub_team_sort",
            )
            _ts_dir = st.selectbox("Order:", ["Ascending", "Descending"], key="nba_hub_team_dir")
            _ts_reverse = _ts_dir == "Descending"

            try:
                _ts_sorted = sorted(
                    _ts_teams,
                    key=lambda t: (
                        float(t.get(_ts_sort, 0) or 0) if _ts_sort != "team_name"
                        else t.get("team_name", "").lower()
                    ),
                    reverse=_ts_reverse if _ts_sort != "team_name" else not _ts_reverse,
                )
            except (ValueError, TypeError):
                _ts_sorted = _ts_teams

            _ts_rows = []
            for _t in _ts_sorted:
                _ts_rows.append({
                    "Team": _t.get("team_name", "") or _t.get("abbreviation", ""),
                    "Abbrev": _t.get("abbreviation", ""),
                    "W": _t.get("wins", ""),
                    "L": _t.get("losses", ""),
                    "Pace": _t.get("pace", ""),
                    "ORTG": _t.get("ortg", ""),
                    "DRTG": _t.get("drtg", ""),
                    "Net Rtg": _t.get("net_rating", ""),
                    "FG%": _t.get("fg_pct", ""),
                    "3P%": _t.get("fg3_pct", ""),
                    "FT%": _t.get("ft_pct", ""),
                    "REB": _t.get("reb", ""),
                    "AST": _t.get("ast", ""),
                    "TOV": _t.get("tov", ""),
                })
            if _ts_rows:
                st.dataframe(_ts_rows, hide_index=True, use_container_width=True)
                st.caption(f"{len(_ts_rows)} teams loaded.")
        else:
            st.info("No team data loaded yet. Use the **Quick Setup** tab to pull team stats.")

    # ── Sub-Tab: Standings ───────────────────────────────────
    with _nba_sub_tab4:
        st.markdown(
            '<div class="df-section-head" style="font-size:0.95rem;">📊 NBA STANDINGS</div>'
            '<div class="df-section-sub">Conference standings with W-L records, streaks, and rankings</div>',
            unsafe_allow_html=True,
        )

        _st_data = st.session_state.get("league_standings", [])
        if not _st_data:
            # Try loading from data service
            try:
                from data.nba_data_service import get_standings as _hub_get_standings
                _st_data = _hub_get_standings()
                if _st_data:
                    st.session_state["league_standings"] = _st_data
            except Exception:
                pass

        if _st_data:
            _st_east = [t for t in _st_data if "east" in str(t.get("conference", "")).lower()]
            _st_west = [t for t in _st_data if "west" in str(t.get("conference", "")).lower()]
            _st_other = [t for t in _st_data if t not in _st_east and t not in _st_west]
            if _st_other:
                _st_east += _st_other

            def _hub_standings_table(teams_list, title):
                if not teams_list:
                    return
                st.markdown(f"**{title}**")
                rows = []
                for t in sorted(teams_list, key=lambda x: x.get("conference_rank", 99)):
                    w = t.get("wins", 0)
                    l_val = t.get("losses", 0)
                    rows.append({
                        "Rank": t.get("conference_rank", "—"),
                        "Team": t.get("team_abbreviation", "") or t.get("team_name", ""),
                        "W": w, "L": l_val,
                        "W%": f"{t.get('win_pct', 0):.3f}",
                        "GB": f"{t.get('games_back', 0):.1f}" if t.get("games_back") else "—",
                        "Home": f"{t.get('home_wins', 0)}-{t.get('home_losses', 0)}",
                        "Away": f"{t.get('away_wins', 0)}-{t.get('away_losses', 0)}",
                        "L10": t.get("last_10", "—"),
                        "Streak": t.get("streak", ""),
                    })
                st.dataframe(rows, hide_index=True, use_container_width=True)

            _st_col_e, _st_col_w = st.columns(2)
            with _st_col_e:
                _hub_standings_table(_st_east, "🏀 Eastern Conference")
            with _st_col_w:
                _hub_standings_table(_st_west, "🏀 Western Conference")
        else:
            st.info(
                "No standings loaded yet. Click **📊 Refresh Standings & News** "
                "in the Advanced tab, or run **One-Click Full Setup**."
            )

    # ── Sub-Tab: Playoff Picture ─────────────────────────────
    with _nba_sub_tab5:
        st.markdown(
            '<div class="df-section-head" style="font-size:0.95rem;">🏀 PLAYOFF PICTURE</div>'
            '<div class="df-section-sub">Playoff seedings, play-in tournament positions, and elimination status</div>',
            unsafe_allow_html=True,
        )

        _pp_data = st.session_state.get("league_standings", [])
        if not _pp_data:
            try:
                from data.nba_data_service import get_standings as _pp_get_standings
                _pp_data = _pp_get_standings()
                if _pp_data:
                    st.session_state["league_standings"] = _pp_data
            except Exception:
                pass

        if _pp_data:
            _pp_east = sorted(
                [t for t in _pp_data if "east" in str(t.get("conference", "")).lower()],
                key=lambda x: x.get("conference_rank", 99),
            )
            _pp_west = sorted(
                [t for t in _pp_data if "west" in str(t.get("conference", "")).lower()],
                key=lambda x: x.get("conference_rank", 99),
            )

            def _playoff_section(teams_list, conf_name):
                if not teams_list:
                    return
                st.markdown(f"### {conf_name}")

                # Playoff-locked (seeds 1-6)
                _locked = [t for t in teams_list if t.get("conference_rank", 99) <= 6]
                _playin = [t for t in teams_list if 7 <= t.get("conference_rank", 99) <= 10]
                _out = [t for t in teams_list if t.get("conference_rank", 99) > 10]

                if _locked:
                    st.markdown("**✅ Playoff Seeds (1-6)**")
                    _lock_rows = []
                    for t in _locked:
                        _lock_rows.append({
                            "Seed": t.get("conference_rank", ""),
                            "Team": t.get("team_abbreviation", "") or t.get("team_name", ""),
                            "W": t.get("wins", 0),
                            "L": t.get("losses", 0),
                            "W%": f"{t.get('win_pct', 0):.3f}",
                            "Streak": t.get("streak", ""),
                            "L10": t.get("last_10", "—"),
                        })
                    st.dataframe(_lock_rows, hide_index=True, use_container_width=True)

                if _playin:
                    st.markdown("**🔄 Play-In Tournament (7-10)**")
                    _pi_rows = []
                    for t in _playin:
                        _pi_rows.append({
                            "Seed": t.get("conference_rank", ""),
                            "Team": t.get("team_abbreviation", "") or t.get("team_name", ""),
                            "W": t.get("wins", 0),
                            "L": t.get("losses", 0),
                            "W%": f"{t.get('win_pct', 0):.3f}",
                            "Streak": t.get("streak", ""),
                            "L10": t.get("last_10", "—"),
                        })
                    st.dataframe(_pi_rows, hide_index=True, use_container_width=True)

                if _out:
                    st.markdown("**❌ Lottery Bound (11+)**")
                    _out_rows = []
                    for t in _out:
                        _out_rows.append({
                            "Seed": t.get("conference_rank", ""),
                            "Team": t.get("team_abbreviation", "") or t.get("team_name", ""),
                            "W": t.get("wins", 0),
                            "L": t.get("losses", 0),
                            "W%": f"{t.get('win_pct', 0):.3f}",
                            "Streak": t.get("streak", ""),
                            "L10": t.get("last_10", "—"),
                        })
                    st.dataframe(_out_rows, hide_index=True, use_container_width=True)

            _pp_col_e, _pp_col_w = st.columns(2)
            with _pp_col_e:
                _playoff_section(_pp_east, "🏀 Eastern Conference")
            with _pp_col_w:
                _playoff_section(_pp_west, "🏀 Western Conference")
        else:
            st.info(
                "No standings data available for playoff picture. Click **📊 Refresh Standings & News** "
                "in the Advanced tab, or run **One-Click Full Setup**."
            )


# ============================================================
# SECTION: Execute the Selected Action
# ============================================================

current_action = st.session_state.get("update_action")

if current_action:
    st.divider()

    # ── Helper to record data diff ─────────────────────────────
    def _snapshot_counts():
        """Capture current data counts for diff reporting."""
        return {
            "players": len(load_players_data()),
            "teams": len(load_teams_data()),
            "games": len(st.session_state.get("todays_games", [])),
        }

    _before_counts = _snapshot_counts()

    # ── Action: Smart ETL Update ─────────────────────────────────
    if current_action == "etl_smart":
        with st.status("⚡ Smart ETL Update", expanded=True) as status:
            with safe_action("Smart ETL Update", status):
                result = refresh_from_etl()
                st.session_state["update_action"] = None
                ng = result.get("new_games", 0)
                nl = result.get("new_logs", 0)
                err = result.get("error")
                if err:
                    st.error(f"❌ Smart ETL Update failed: {err}")
                else:
                    st.success(
                        f"✅ Smart ETL Update complete! "
                        f"**{ng}** new game(s) · **{nl}** new log row(s) added."
                    )
                    _add_activity(f"ETL Smart: +{ng} games, +{nl} logs")
                    if ng == 0 and nl == 0:
                        st.info("ℹ️ Database is already up to date.")
                    try:
                        from data.etl_data_service import get_db_counts as _fresh_counts
                        counts = _fresh_counts()
                        st.caption(
                            f"DB: **{counts['players']:,}** players · "
                            f"**{counts['games']:,}** games · **{counts['logs']:,}** logs"
                        )
                    except Exception:
                        pass
                    status.update(label="✅ Smart ETL Update complete", state="complete")

    # ── Action: Full ETL Pull ────────────────────────────────────
    elif current_action == "etl_full":
        with st.status("🔄 Full ETL Pull — re-fetching entire season...", expanded=True) as status:
            with safe_action("Full ETL Pull", status):
                result = full_refresh_from_etl()
                st.session_state["update_action"] = None
                pi = result.get("players_inserted", 0)
                gi = result.get("games_inserted", 0)
                li = result.get("logs_inserted", 0)
                err = result.get("error")
                if err:
                    st.error(f"❌ Full ETL Pull failed: {err}")
                else:
                    st.success(
                        f"✅ Full ETL Pull complete! "
                        f"**{pi:,}** players · **{gi:,}** games · **{li:,}** logs."
                    )
                    _add_activity(f"ETL Full: {pi:,} players, {gi:,} games, {li:,} logs")
                    status.update(label="✅ Full ETL Pull complete", state="complete")

    # ── Action: One-Click Full Setup ─────────────────────────────
    elif current_action == "one_click":
        with st.status("🏀 One-Click Full Setup — loading everything...", expanded=True) as status:
            with safe_action("One-Click Full Setup", status):
                result = get_all_todays_data()
                st.session_state["update_action"] = None
                games = result.get("games", [])
                players_ok = result.get("players_updated", False)
                teams_ok = result.get("teams_updated", False)
                if games:
                    st.session_state["todays_games"] = games
                    updated_players = load_players_data()
                    st.success(
                        f"✅ One-Click Setup complete! "
                        f"**{len(games)} game(s)** | **{len(updated_players)} players** | "
                        f"Teams: {'✅' if teams_ok else '⚠️ failed'}"
                    )
                    _add_activity(f"One-Click: {len(games)} games, {len(updated_players)} players")
                    _bonus = []
                    if result.get("standings"):
                        _bonus.append(f"📊 Standings ({len(result['standings'])} teams)")
                    if result.get("news"):
                        _bonus.append(f"📰 News ({len(result['news'])} items)")
                    if _bonus:
                        st.caption("**Bonus data:** " + " · ".join(_bonus))
                    status.update(label="✅ One-Click Setup complete", state="complete")
                else:
                    st.warning("⚠️ Could not retrieve tonight's games. Try again or load manually.")

    # ── Action: Smart Update with auto-game-load ─────────────────
    elif current_action == "smart_with_games":
        with st.status("⚡ Smart Update — auto-loading games first...", expanded=True) as status:
            with safe_action("Smart Update (with auto-load)", status):
                st.write("Loading tonight's games...")
                _auto_games = get_todays_games()
                if _auto_games:
                    st.session_state["todays_games"] = _auto_games
                    st.write(f"✅ Found {len(_auto_games)} game(s). Now loading player stats...")
                    success = get_todays_players(_auto_games)
                    st.session_state["update_action"] = None
                    if success:
                        updated = load_players_data()
                        st.success(
                            f"✅ Smart Update complete! **{len(updated)} players** "
                            f"from {len(_auto_games)} game(s)."
                        )
                        _add_activity(f"Smart Update: {len(updated)} players from {len(_auto_games)} games")
                        status.update(label="✅ Smart Update complete", state="complete")
                    else:
                        st.error("❌ Smart Update failed. Try One-Click Full Setup as fallback.")
                else:
                    st.session_state["update_action"] = None
                    st.warning("⚠️ No games found tonight. Smart Update requires active games.")

    # ── Action: Smart Update (games already loaded) ──────────────
    elif current_action == "smart":
        with st.status("⚡ Smart Update — today's teams only", expanded=True) as status:
            with safe_action("Smart Update", status):
                _smart_games = st.session_state.get("todays_games", [])
                if not _smart_games:
                    st.warning("⚠️ No games loaded. Use One-Click Full Setup instead.")
                    st.session_state["update_action"] = None
                else:
                    teams_set = set()
                    for g in _smart_games:
                        teams_set.add(g.get("home_team", ""))
                        teams_set.add(g.get("away_team", ""))
                    teams_set.discard("")
                    st.write(f"Loading rosters for: {', '.join(sorted(teams_set))}")
                    success = get_todays_players(_smart_games)
                    st.session_state["update_action"] = None
                    if success:
                        updated = load_players_data()
                        st.success(f"✅ Smart Update complete! **{len(updated)} players** loaded.")
                        _add_activity(f"Smart Update: {len(updated)} players")
                        status.update(label="✅ Smart Update complete", state="complete")
                    else:
                        st.error("❌ Smart Update failed. Try full update as fallback.")

    # ── Action: Get Tonight's Games ──────────────────────────────
    elif current_action == "games":
        with st.status("🏟️ Loading Tonight's Games...", expanded=True) as status:
            with safe_action("Get Tonight's Games", status):
                _new_games = get_todays_games()
                st.session_state["update_action"] = None
                if _new_games:
                    st.session_state["todays_games"] = _new_games
                    st.success(f"✅ Found **{len(_new_games)} game(s)** for tonight!")
                    _add_activity(f"Games loaded: {len(_new_games)}")
                    games_display = []
                    for game in _new_games:
                        games_display.append({
                            "Away Team": game.get("away_team", ""),
                            "Home Team": game.get("home_team", ""),
                            "Game Date": game.get("game_date", ""),
                            "Total (O/U)": game.get("consensus_total") or game.get("game_total", ""),
                            "Spread": game.get("consensus_spread") or game.get("vegas_spread", ""),
                        })
                    st.dataframe(games_display, use_container_width=True, hide_index=True)
                    status.update(label=f"✅ {len(_new_games)} games loaded", state="complete")
                else:
                    st.warning("⚠️ No games found for tonight.")

    # ── Action: Update Player Stats ──────────────────────────────
    elif current_action == "players":
        with st.status("👤 Updating Player Stats (this takes a few minutes)...", expanded=True) as status:
            with safe_action("Update Player Stats", status):
                success = get_player_stats()
                st.session_state["update_action"] = None
                if success:
                    updated_players = load_players_data()
                    st.success(f"✅ **{len(updated_players)} players** updated!")
                    _add_activity(f"Players updated: {len(updated_players)}")
                    players_display = []
                    for player in updated_players[:20]:
                        players_display.append({
                            "Name": player.get("name", ""),
                            "Team": player.get("team", ""),
                            "PTS": player.get("points_avg", ""),
                            "REB": player.get("rebounds_avg", ""),
                            "AST": player.get("assists_avg", ""),
                        })
                    st.dataframe(players_display, use_container_width=True, hide_index=True)
                    st.caption(f"Showing 20 of {len(updated_players)} players.")
                    status.update(label="✅ Player stats updated", state="complete")
                else:
                    st.error("❌ Failed to update player stats.")

    # ── Action: Update Team Stats ────────────────────────────────
    elif current_action == "teams":
        with st.status("🏆 Updating Team Stats...", expanded=True) as status:
            with safe_action("Update Team Stats", status):
                success = get_team_stats()
                st.session_state["update_action"] = None
                if success:
                    updated_teams = load_teams_data()
                    st.success(f"✅ **{len(updated_teams)} teams** updated!")
                    _add_activity(f"Teams updated: {len(updated_teams)}")
                    teams_display = []
                    for team in updated_teams:
                        teams_display.append({
                            "Team": team.get("team_name", ""),
                            "Abbrev": team.get("abbreviation", ""),
                            "Pace": team.get("pace", ""),
                            "ORTG": team.get("ortg", ""),
                            "DRTG": team.get("drtg", ""),
                        })
                    st.dataframe(teams_display, use_container_width=True, hide_index=True)
                    status.update(label="✅ Team stats updated", state="complete")
                else:
                    st.error("❌ Failed to update team stats.")

    # ── Action: Update Everything ────────────────────────────────
    elif current_action == "all":
        with st.status("🔄 Updating All Data (this may take several minutes)...", expanded=True) as status:
            with safe_action("Update Everything", status):
                results = get_all_data()
                st.session_state["update_action"] = None
                players_ok = results.get("players", False)
                teams_ok = results.get("teams", False)
                if players_ok and teams_ok:
                    st.success("✅ **All data updated successfully!**")
                elif players_ok or teams_ok:
                    st.warning(
                        f"⚠️ Partial update. Players: {'✅' if players_ok else '❌'} | "
                        f"Teams: {'✅' if teams_ok else '❌'}"
                    )
                else:
                    st.error("❌ Update failed for all data types.")
                if players_ok:
                    up = load_players_data()
                    st.metric("👤 Players Updated", len(up))
                if teams_ok:
                    ut = load_teams_data()
                    st.metric("🏆 Teams Updated", len(ut))

                st.write("Loading tonight's games...")
                _new_games = get_todays_games()
                if _new_games:
                    st.session_state["todays_games"] = _new_games
                    st.success(f"🏟️ Found **{len(_new_games)} game(s)** for tonight!")
                _add_activity(f"Full update: P={'✅' if players_ok else '❌'} T={'✅' if teams_ok else '❌'}")
                status.update(label="✅ Full update complete", state="complete")

    # ── Action: Injury Report ────────────────────────────────────
    elif current_action == "injury_report":
        with st.status("🏥 Refreshing Injury Report...", expanded=True) as status:
            st.session_state["update_action"] = None
            with safe_action("Refresh Injury Report", status):
                from data.roster_engine import RosterEngine as _RE
                _re = _RE()
                _re.refresh()
                scraped_data = _re.get_injury_report()

                if scraped_data:
                    _now_str = datetime.datetime.now().strftime("%b %d, %Y at %I:%M %p")
                    st.session_state["injury_report_last_scraped"] = _now_str
                    st.session_state["injury_report_data"] = scraped_data

                    out_count = sum(1 for v in scraped_data.values() if v.get("status") == "Out")
                    gtd_count = sum(
                        1 for v in scraped_data.values()
                        if v.get("status") in ("GTD", "Questionable", "Doubtful", "Day-to-Day")
                    )
                    total_count = len(scraped_data)

                    if total_count == 0:
                        st.warning("⚠️ 0 injuries found — data source may be temporarily unavailable.")
                    else:
                        st.success(
                            f"✅ **Injury report refreshed** ({_now_str})  \n"
                            f"Found **{total_count}** players — "
                            f"**{out_count}** Out, **{gtd_count}** GTD/Questionable/Doubtful"
                        )
                        _add_activity(f"Injuries: {total_count} total, {out_count} Out, {gtd_count} GTD")

                    # ── Sortable/filterable injury table ─────────────────
                    st.markdown("### 📋 Injury Data")
                    _STATUS_ORDER = {
                        "Out": 0, "Injured Reserve": 0,
                        "Doubtful": 1, "GTD": 2, "Questionable": 2,
                        "Day-to-Day": 3, "Probable": 4,
                    }
                    display_rows = [
                        {
                            "Player": key.title(),
                            "Team": v.get("team", ""),
                            "Status": v.get("status", ""),
                            "Injury": v.get("injury", "") or v.get("comment", ""),
                            "Return Date": v.get("return_date", ""),
                            "Source": v.get("source", ""),
                        }
                        for key, v in scraped_data.items()
                        if v.get("status", "Active") not in ("Active", "Unknown")
                    ]

                    if display_rows:
                        inj_df = pd.DataFrame(display_rows)

                        # Team filter
                        _all_teams = sorted(inj_df["Team"].unique().tolist())
                        _tonight_teams = set()
                        for g in st.session_state.get("todays_games", []):
                            _tonight_teams.add(g.get("home_team", ""))
                            _tonight_teams.add(g.get("away_team", ""))
                        _tonight_teams.discard("")

                        filter_options = ["All Teams"]
                        if _tonight_teams:
                            filter_options.append("Tonight's Teams Only")
                        filter_options.extend(_all_teams)

                        team_filter = st.selectbox(
                            "Filter by team:",
                            filter_options,
                            key="injury_team_filter",
                        )

                        if team_filter == "Tonight's Teams Only":
                            inj_df = inj_df[inj_df["Team"].isin(_tonight_teams)]
                        elif team_filter != "All Teams":
                            inj_df = inj_df[inj_df["Team"] == team_filter]

                        st.dataframe(
                            inj_df,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Status": st.column_config.TextColumn("Status", width="small"),
                                "Player": st.column_config.TextColumn("Player", width="medium"),
                            },
                        )
                    else:
                        st.info("No injured / non-Active players found.")
                    status.update(label="✅ Injury report refreshed", state="complete")
                else:
                    st.warning("⚠️ No injury data was returned.")

    # ── Action: Standings & News ─────────────────────────────────
    elif current_action == "standings_news":
        with st.status("📊 Refreshing Standings & News...", expanded=True) as status:
            st.session_state["update_action"] = None
            with safe_action("Refresh Standings & News", status):
                from data.nba_data_service import get_standings as _get_standings_svc
                _standings_data = _get_standings_svc()
                st.session_state["league_standings"] = _standings_data

                from data.nba_data_service import get_player_news as _get_news_svc
                _news_data = _get_news_svc(limit=30)
                st.session_state["player_news"] = _news_data

                _now_sn = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state["standings_news_last_loaded"] = _now_sn

                if _standings_data:
                    st.success(
                        f"✅ Standings loaded: **{len(_standings_data)} teams** · "
                        f"News: **{len(_news_data)} items**"
                    )
                    _add_activity(f"Standings: {len(_standings_data)} teams, News: {len(_news_data)} items")
                    status.update(label="✅ Standings & News loaded", state="complete")
                else:
                    st.warning("No standings returned.")

    # ── Action: Deep Fetch ───────────────────────────────────────
    elif current_action == "deep_fetch":
        with st.status("🔬 Deep Fetch: Advanced Stats Enrichment...", expanded=True) as status:
            with safe_action("Deep Fetch: Advanced Stats", status):
                _df_games = st.session_state.get("todays_games", [])
                from data.advanced_fetcher import enrich_tonights_slate, build_enrichment_summary

                _enriched = enrich_tonights_slate(_df_games)
                st.session_state["advanced_enrichment"] = _enriched
                st.session_state["update_action"] = None

                _summary = build_enrichment_summary(_enriched)
                st.success("✅ Advanced Stats Loaded!")
                _add_activity(f"Deep Fetch: {_summary.get('games_enriched', 0)} games enriched")

                _c1, _c2, _c3 = st.columns(3)
                with _c1:
                    st.metric("Games Enriched", _summary.get("games_enriched", 0))
                    st.metric("Team Game Logs", _summary.get("game_logs_fetched", 0))
                with _c2:
                    st.metric("5-Man Lineups", _summary.get("lineups_fetched", 0))
                    st.metric("Team Dashboards", _summary.get("dashboards_fetched", 0))
                with _c3:
                    st.metric("Standing Rows", _summary.get("standings_rows", 0))
                    st.metric("Player Metrics", _summary.get("player_metrics_rows", 0))

                if _enriched:
                    with st.expander("📋 Per-Game Enrichment Details"):
                        for _gid, _gdata in _enriched.items():
                            st.markdown(
                                f"**Game {_gid}** — "
                                f"Home logs: {len(_gdata.get('home_game_logs', []))} | "
                                f"Away logs: {len(_gdata.get('away_game_logs', []))} | "
                                f"Dashboard: {'✅' if _gdata.get('home_dashboard') else '—'}"
                            )
                status.update(label="✅ Deep Fetch complete", state="complete")

    # ── Data Diff / Changelog ────────────────────────────────────
    _after_counts = _snapshot_counts()
    diffs = []
    for key, label in [("players", "players"), ("teams", "teams"), ("games", "games")]:
        before = _before_counts.get(key, 0)
        after = _after_counts.get(key, 0)
        if after != before:
            diff = after - before
            sign = "+" if diff > 0 else ""
            count_info = f"now {after}" if after else ""
            diffs.append(f"{sign}{diff} {label} ({count_info})")
    if diffs:
        st.info("📝 **What changed:** " + " · ".join(diffs))


# ============================================================
# SECTION: Platform Roster Insights
# ============================================================

try:
    from data.sportsbook_service import (
        extract_active_players_from_props,
        cross_reference_with_player_data,
        get_platform_confirmed_injuries,
    )
    from data.data_manager import load_platform_props_from_session as _load_pp
    _ROSTER_INSIGHTS_AVAILABLE = True
except ImportError:
    _ROSTER_INSIGHTS_AVAILABLE = False

if _ROSTER_INSIGHTS_AVAILABLE:
    _roster_props = _load_pp(st.session_state)
    if _roster_props:
        st.divider()
        st.markdown(
            '<div class="df-section-head" style="font-size:0.95rem;">🏥 PLATFORM ROSTER INSIGHTS</div>'
            '<div class="df-section-sub">Cross-referencing platform props against your player database</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            "Cross-reference tonight's platform props against your player database "
            "to spot **missing players** and **potential injuries**."
        )

        try:
            _ri_players_data = load_players_data()
            _ri_active = extract_active_players_from_props(_roster_props)
            _ri_xref = cross_reference_with_player_data(_ri_active, _ri_players_data)

            _ri_c1, _ri_c2, _ri_c3 = st.columns(3)
            with _ri_c1:
                st.metric("✅ Platform-Confirmed Active", len(_ri_active))
            with _ri_c2:
                st.metric("⚠️ Missing from DB", len(_ri_xref["missing_from_csv"]))
            with _ri_c3:
                st.metric("🔴 Potentially Out", len(_ri_xref["in_csv_but_not_on_platforms"]))

            if _ri_xref["missing_from_csv"]:
                with st.expander(f"⚠️ {len(_ri_xref['missing_from_csv'])} players on platforms but NOT in DB"):
                    st.markdown("Run a **Smart Update** to retrieve their stats.")
                    for _mp in _ri_xref["missing_from_csv"][:25]:
                        st.markdown(f"- {_mp}")

            _todays_games_ri = st.session_state.get("todays_games", [])
            _ri_injuries = get_platform_confirmed_injuries(_ri_active, _ri_players_data, _todays_games_ri)
            if _ri_injuries:
                with st.expander(f"🔴 {len(_ri_injuries)} players potentially out"):
                    _inj_rows = [
                        {"Player": p["name"], "Team": p["team"], "Status": p["reason"]}
                        for p in _ri_injuries[:30]
                    ]
                    st.dataframe(_inj_rows, use_container_width=True, hide_index=True)
            elif _todays_games_ri:
                st.success("✅ All players in your database appear on at least one platform.")
        except Exception as _ri_err:
            st.warning(f"⚠️ Could not load roster insights: {_ri_err}")


# ============================================================
# SECTION: Standings & News Display
# ============================================================

# Auto-load standings and news from DB if not in session state
_standings_display = st.session_state.get("league_standings", [])
_news_display = st.session_state.get("player_news", [])

if not _standings_display:
    try:
        from data.nba_data_service import get_standings as _auto_get_standings
        _standings_display = _auto_get_standings()
        if _standings_display:
            st.session_state["league_standings"] = _standings_display
    except Exception:
        pass

if not _news_display:
    try:
        from data.nba_data_service import get_player_news as _auto_get_news
        _news_display = _auto_get_news(limit=30)
        if _news_display:
            st.session_state["player_news"] = _news_display
    except Exception:
        pass

if _standings_display or _news_display:
    st.divider()
    st.markdown(
        '<div class="df-section-head" style="font-size:0.95rem;">📊 NBA STANDINGS & NEWS</div>'
        '<div class="df-section-sub">Conference standings and player/team news feed</div>',
        unsafe_allow_html=True,
    )

    _sn_tab1, _sn_tab2 = st.tabs(["🏆 Standings", "📰 Player & Team News"])

    with _sn_tab1:
        if _standings_display:
            _east = [t for t in _standings_display if "east" in str(t.get("conference", "")).lower()]
            _west = [t for t in _standings_display if "west" in str(t.get("conference", "")).lower()]
            _other = [t for t in _standings_display if t not in _east and t not in _west]
            if _other:
                _east += _other

            def _standings_table(teams_list, title):
                if not teams_list:
                    return
                st.markdown(f"**{title}**")
                rows = []
                for t in sorted(teams_list, key=lambda x: x.get("conference_rank", 99)):
                    w = t.get("wins", 0)
                    l = t.get("losses", 0)
                    rows.append({
                        "Rank": t.get("conference_rank", "—"),
                        "Team": t.get("team_abbreviation", "") or t.get("team_name", ""),
                        "W": w, "L": l,
                        "W%": f"{t.get('win_pct', 0):.3f}",
                        "GB": f"{t.get('games_back', 0):.1f}" if t.get("games_back") else "—",
                        "Home": f"{t.get('home_wins',0)}-{t.get('home_losses',0)}",
                        "Away": f"{t.get('away_wins',0)}-{t.get('away_losses',0)}",
                        "L10": t.get("last_10", "—"),
                        "Streak": t.get("streak", ""),
                    })
                st.dataframe(rows, hide_index=True, use_container_width=True)

            _c_e, _c_w = st.columns(2)
            with _c_e:
                _standings_table(_east, "🏀 Eastern Conference")
            with _c_w:
                _standings_table(_west, "🏀 Western Conference")
        else:
            st.info("No standings loaded yet. Click **📊 Refresh Standings & News** in the Advanced tab.")

    with _sn_tab2:
        if _news_display:
            _imp_colors = {"high": "rgba(255,68,68,0.15)", "medium": "rgba(255,204,0,0.15)", "low": "rgba(0,213,89,0.15)"}
            _imp_text_colors = {"high": "#F24336", "medium": "#F9C62B", "low": "#00D559"}
            _cat_emoji = {
                "injury": "🏥", "trade": "🔄", "performance": "📈",
                "suspension": "🚫", "contract": "💰", "roster": "📋",
            }
            for _item in _news_display[:25]:
                _title = _item.get("title", "")
                _body = _item.get("body", "")
                _cat = _item.get("category", "")
                _imp = _item.get("impact", "").lower()
                _pub = _item.get("published_at", "")[:10]
                if not _title:
                    continue
                _imp_badge = (
                    f'<span style="background:{_imp_colors.get(_imp, "rgba(100,100,120,0.15)")};'
                    f'color:{_imp_text_colors.get(_imp, "#6e7681")};border-radius:20px;padding:2px 8px;'
                    f'font-size:0.72rem;font-weight:700;font-family:\'JetBrains Mono\',monospace;'
                    f'border:1px solid {_imp_text_colors.get(_imp, "#6e7681")}20;">{_imp.upper()}</span>'
                    if _imp else ""
                )
                _who = f"**{_item.get('player_name', '')}**" if _item.get("player_name") else ""
                with st.expander(
                    f"{_cat_emoji.get(_cat, '📰')} {_title[:80]}" + (f"  ·  {_pub}" if _pub else ""),
                    expanded=False,
                ):
                    _cat_label = _cat_emoji.get(_cat, "📰") + " " + _cat.title() if _cat else "📰 News"
                    if _who:
                        st.markdown(f"{_who} · {_cat_label} {_imp_badge}", unsafe_allow_html=True)
                    if _body:
                        st.markdown(_body)
        else:
            st.info("No news loaded yet.")


# ============================================================
# SECTION: ETL Health Monitor
# ============================================================

st.markdown("")

with st.expander("🔧 ETL Health Monitor", expanded=False):
    try:
        from pathlib import Path as _Path
        _db_path = _Path("db") / "smartai_nba.db"

        if _db_path.exists():
            _db_size_mb = _db_path.stat().st_size / (1024 * 1024)
            st.markdown(f"**Database file:** `{_db_path}` — **{_db_size_mb:.1f} MB**")

            # Table row counts for all tables
            _health_conn = sqlite3.connect(str(_db_path))
            try:
                _tables = [
                    row[0] for row in
                    _health_conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                # Whitelist: only count tables whose names are
                # simple identifiers (alphanumeric + underscore).  This
                # prevents any injected names from reaching the query.
                import re as _re_mod
                _safe_tables = [t for t in _tables if _re_mod.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t)]
                if _safe_tables:
                    _table_rows = []
                    for _tbl in _safe_tables:
                        try:
                            _cnt = _health_conn.execute(
                                f"SELECT COUNT(*) FROM [{_tbl}]"
                            ).fetchone()[0]
                            _table_rows.append({"Table": _tbl, "Rows": f"{_cnt:,}"})
                        except Exception:
                            _table_rows.append({"Table": _tbl, "Rows": "error"})
                    st.dataframe(_table_rows, hide_index=True, use_container_width=True)
            finally:
                _health_conn.close()

            # Vacuum button
            if st.button("🔧 Vacuum Database", key="btn_vacuum",
                          help="Compact the SQLite file to reclaim unused space"):
                try:
                    _vac_conn = sqlite3.connect(str(_db_path))
                    _vac_conn.execute("VACUUM")
                    _vac_conn.close()
                    _new_size = _db_path.stat().st_size / (1024 * 1024)
                    st.success(f"✅ Database vacuumed! New size: {_new_size:.1f} MB")
                    _add_activity(f"Database vacuumed: {_new_size:.1f} MB")
                except Exception as _vac_err:
                    st.error(f"❌ Vacuum failed: {_vac_err}")
        else:
            st.info("No ETL database found. Run an ETL pull to create it.")
    except Exception as _health_err:
        st.warning(f"Could not load health data: {_health_err}")


# ============================================================
# SECTION: Database Explorer / Query Tool
# ============================================================

with st.expander("🔍 Explore Your Data", expanded=False):
    _explore_tab1, _explore_tab2, _explore_tab3 = st.tabs([
        "👤 Player Search", "🏟️ Team Lookup", "🔧 SQL Query"
    ])

    with _explore_tab1:
        _search_name = st.text_input("Search player by name:", key="player_search_input")
        if _search_name:
            try:
                from data.etl_data_service import get_player_by_name
                _found = get_player_by_name(_search_name)
                if _found:
                    st.json(_found)
                else:
                    # Fallback: search in loaded CSV data
                    _csv_players = load_players_data()
                    _matches = [p for p in _csv_players if _search_name.lower() in p.get("name", "").lower()]
                    if _matches:
                        st.dataframe(_matches[:10], use_container_width=True, hide_index=True)
                    else:
                        st.info(f"No player found matching '{_search_name}'")
            except Exception as _search_err:
                st.warning(f"Search error: {_search_err}")

    with _explore_tab2:
        _teams_list = load_teams_data()
        if _teams_list:
            _team_names = sorted(set(t.get("team_name", "") or t.get("abbreviation", "") for t in _teams_list))
            _team_names = [n for n in _team_names if n]
            _selected_team = st.selectbox("Select team:", [""] + _team_names, key="team_explore_select")
            if _selected_team:
                _team_data = [t for t in _teams_list if t.get("team_name") == _selected_team or t.get("abbreviation") == _selected_team]
                if _team_data:
                    st.json(_team_data[0])
        else:
            st.info("No team data loaded. Run an update first.")

    with _explore_tab3:
        st.caption("⚠️ Read-only queries only. Use with caution.")
        _sql_query = st.text_area(
            "SQL Query:",
            value="SELECT * FROM Players LIMIT 5",
            key="sql_query_input",
            height=80,
        )
        if st.button("▶ Run Query", key="btn_run_sql"):
            try:
                from pathlib import Path as _SqlPath
                _sql_db = _SqlPath("db") / "smartai_nba.db"
                if not _sql_db.exists():
                    st.warning("No database file found.")
                else:
                    # Safety: only allow SELECT queries — block dangerous keywords
                    _clean = _sql_query.strip().upper()
                    _BLOCKED_KEYWORDS = (
                        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
                        "ATTACH", "DETACH", "PRAGMA", "REPLACE", "GRANT", "REVOKE",
                    )
                    if not _clean.startswith("SELECT"):
                        st.error("❌ Only SELECT queries are allowed.")
                    elif any(kw in _clean for kw in _BLOCKED_KEYWORDS):
                        st.error("❌ Query contains a disallowed keyword. Only pure SELECT queries are allowed.")
                    else:
                        _sql_conn = sqlite3.connect(f"file:{_sql_db}?mode=ro", uri=True)
                        try:
                            _result_df = pd.read_sql_query(_sql_query, _sql_conn)
                            st.dataframe(_result_df, use_container_width=True, hide_index=True)
                            st.caption(f"{len(_result_df)} row(s) returned")
                        finally:
                            _sql_conn.close()
            except Exception as _sql_err:
                st.error(f"❌ Query error: {_sql_err}")


# ============================================================
# SECTION: Export / Backup
# ============================================================

with st.expander("📥 Export & Backup", expanded=False):
    _exp_c1, _exp_c2, _exp_c3 = st.columns(3)

    with _exp_c1:
        st.markdown("**📥 Export Database**")
        st.caption("Download the SQLite database file.")
        try:
            from pathlib import Path as _ExpPath
            _exp_db = _ExpPath("db") / "smartai_nba.db"
            if _exp_db.exists():
                with open(_exp_db, "rb") as _db_file:
                    if has_permission("export_data"):
                        st.download_button(
                            "📥 Download smartai_nba.db",
                            data=_db_file.read(),
                            file_name="smartai_nba.db",
                            mime="application/octet-stream",
                            key="btn_export_db",
                        )
                    else:
                        permission_gate("export_data", show_upgrade_button=False)
                        st.caption("🔒 DB export requires **Smart Money** or above.")
                if st.button("🧰 Create Backup Snapshot", key="btn_create_db_backup"):
                    try:
                        from tracking.database import create_database_backup
                        _ok_backup, _backup_msg = create_database_backup(reason="manual")
                        if _ok_backup:
                            st.success(f"✅ Backup created: {_backup_msg}")
                            _add_activity(f"Database backup created: {_backup_msg}")
                        else:
                            st.warning(f"Backup did not run: {_backup_msg}")
                    except Exception as _backup_err:
                        st.error(f"❌ Backup failed: {_backup_err}")
            else:
                st.info("No database file to export.")
        except Exception as _exp_err:
            st.warning(f"Export error: {_exp_err}")

    with _exp_c2:
        st.markdown("**📥 Export CSVs**")
        st.caption("Download all data CSVs as a zip.")
        if st.button("📥 Export All CSVs", key="btn_export_csvs"):
            try:
                from pathlib import Path as _CsvPath
                _data_dir = _CsvPath("data")
                _csv_files = list(_data_dir.glob("*.csv"))
                if _csv_files:
                    _zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for cf in _csv_files:
                            zf.write(cf, cf.name)
                    if has_permission("export_data"):
                        st.download_button(
                            "📥 Download CSVs.zip",
                            data=_zip_buffer.getvalue(),
                            file_name="smartpicks_csvs.zip",
                            mime="application/zip",
                            key="btn_download_csvs_zip",
                        )
                    else:
                        permission_gate("export_data", show_upgrade_button=False)
                        st.caption("🔒 CSV export requires **Smart Money** or above.")
                else:
                    st.info("No CSV files found in the data directory.")
            except Exception as _csv_err:
                st.warning(f"Export error: {_csv_err}")

    with _exp_c3:
        st.markdown("**📤 Import Database**")
        st.caption("Upload a .db file to restore from backup.")
        _uploaded = st.file_uploader(
            "Upload .db file",
            type=["db"],
            key="upload_db_file",
        )
        if _uploaded:
            try:
                from pathlib import Path as _ImpPath
                _imp_db = _ImpPath("db") / "smartai_nba.db"
                _imp_db.parent.mkdir(parents=True, exist_ok=True)
                with open(_imp_db, "wb") as _imp_f:
                    _imp_f.write(_uploaded.read())
                st.success("✅ Database imported successfully! Refresh the page to use new data.")
                _add_activity("Database imported from upload")
            except Exception as _imp_err:
                st.error(f"❌ Import failed: {_imp_err}")


# ============================================================
# SECTION: Activity Log + Error Summary
# ============================================================

st.markdown("")

# Error summary
_errors = st.session_state.get("_df_errors", [])
if _errors:
    with st.expander(f"⚠️ Errors ({len(_errors)})", expanded=False):
        for _err in _errors:
            st.markdown(
                f'<div style="color:#F24336;font-size:0.85rem;padding:3px 0;'
                f'font-family:\'JetBrains Mono\',monospace;">• {_err}</div>',
                unsafe_allow_html=True,
            )
        if st.button("🗑️ Clear Errors", key="btn_clear_errors"):
            st.session_state["_df_errors"] = []
            st.rerun()

# Activity log
_activity_log = st.session_state.get("_df_activity_log", [])
if _activity_log:
    with st.expander(f"📋 Activity Log ({len(_activity_log)} entries)", expanded=False):
        _log_text = "\n".join(reversed(_activity_log))
        st.code(_log_text, language="text")
        if st.button("🗑️ Clear Log", key="btn_clear_log"):
            st.session_state["_df_activity_log"] = []
            st.rerun()


# ============================================================
# SECTION: Help and Tips
# ============================================================

with st.expander("💡 Tips & FAQ", expanded=False):
    st.markdown("""
    ### Frequently Asked Questions

    **Q: How often should I update?**
    A: Update **before each betting session**. Updating once per day before you bet is ideal.

    ---

    **Q: Why does the update take so long?**
    A: We add a 1.5-second delay between requests to avoid being blocked. With 500+ players,
    this is normal and necessary!

    ---

    **Q: What happens if the update fails?**
    A: Nothing breaks! The app keeps using existing data. Try again in a few minutes.

    ---

    **Q: Where does the data come from?**
    A: Player stats, team stats, rosters, injuries, standings, and live scores from
    professional sports data providers. Prop lines from all major sportsbooks.

    ---

    **Q: How do I get DraftKings props?**
    A: Enable DraftKings on the ⚙️ Settings page, then use the Props & Enrichment tab.

    ---

    **Q: Which tab should I use?**
    A: **Quick Setup** for daily workflow (90% of users). **Advanced** for granular control.
    **Props & Enrichment** for betting lines and deep stats.
    """)
