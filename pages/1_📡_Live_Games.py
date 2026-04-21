# ============================================================
# FILE: pages/1_🏀_Todays_Games.py
# PURPOSE: Show tonight's NBA matchups as rich visual game cards.
#          Auto-loads games and lets user enter Vegas lines.
# CONNECTS TO: app.py (session state), Analysis page (uses games)
# ============================================================

import streamlit as st
import datetime
import html as _h
import os
import time

from data.data_manager import load_teams_data, get_all_team_abbreviations, find_players_by_team, load_players_data
from data.nba_data_service import get_todays_games, get_todays_players, get_all_todays_data
from styles.theme import get_team_colors, _TEAM_COLORS

try:
    from data.nba_data_service import refresh_from_etl as _lg_refresh_etl, full_refresh_from_etl as _lg_full_refresh_etl
    _ETL_AVAILABLE_LG = True
except ImportError:
    _ETL_AVAILABLE_LG = False

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# ── ESPN CDN base for team logos ──────────────────────────────
ESPN_LOGO_BASE_URL = "https://a.espncdn.com/i/teamlogos/nba/500"
NBA_LOGO_FALLBACK_URL = "https://cdn.nba.com/logos/leagues/logo-nba.svg"

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Live Games — SmartBetPro NBA",
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
track_page_view("Live Games")
from utils.seo import inject_page_seo
inject_page_seo("Live Games")

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html, get_logo_img_tag, GOLD_LOGO_PATH
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ───────────────────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating, render_sidebar_auth
render_joseph_hero_banner()
st.session_state["joseph_page_context"] = "page_live_games"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

# ─── Custom CSS ────────────────────────────────────────────
# Import ESPN ticker CSS from live_theme.py so we can reuse it
from styles.live_theme import get_live_sweat_css as _get_ticker_css
st.markdown(_get_ticker_css(), unsafe_allow_html=True)

st.markdown("""
<style>
/* Game card wrapper — enhanced dark glass with cyan glow */
.game-card {
    background: linear-gradient(135deg, rgba(13,18,40,0.95) 0%, rgba(11,18,35,0.98) 100%);
    border: 1px solid rgba(0,213,89,0.15);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 0 20px rgba(0,213,89,0.06), 0 4px 20px rgba(0,0,0,0.5);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.game-card:hover {
    border-color: rgba(0,213,89,0.35);
    box-shadow: 0 0 30px rgba(0,213,89,0.13), 0 6px 24px rgba(0,0,0,0.6);
    transform: translateY(-3px);
    transition: all 0.2s ease;
}
/* Team badge — dynamic team-color driven via inline style */
.team-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 1px;
    color: #ffffff;
    margin-right: 6px;
}
/* Team logo inside badge */
.team-badge img.team-logo {
    width: 24px; height: 24px;
    object-fit: contain;
    vertical-align: middle;
    border-radius: 2px;
}
/* Record text */
.record-text { color: #6B7A9A; font-size: 0.9rem; }
/* Streak positive/negative */
.streak-hot { color: #00D559; font-weight: 700; text-shadow: 0 0 6px rgba(0,213,89,0.5); }
.streak-cold { color: #F24336; font-weight: 700; }
.streak-neutral { color: rgba(255,255,255,0.85); font-weight: 600; }
/* Game meta info */
.game-meta { color: #6B7A9A; font-size: 0.85rem; margin-top: 4px; }
/* Side-by-side scoreboard layout */
.scoreboard-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
}
.scoreboard-team {
    flex: 1 1 0;
    min-width: 180px;
}
.scoreboard-team.away { text-align: right; }
.scoreboard-team.home { text-align: left; }
.scoreboard-at {
    font-size: 1.3rem;
    font-weight: 800;
    color: #F9C62B;
    text-shadow: 0 0 10px rgba(255,94,0,0.6);
    flex-shrink: 0;
}
/* Key players row */
.key-players { margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(0,213,89,0.10); }
.key-players-title { color: #6B7A9A; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; }
.player-stat { color: rgba(255,255,255,0.85); font-size: 0.9rem; }
/* Injury inline badges */
.injury-badge-out { display:inline-block; background:#F24336; color:#fff; font-size:0.65rem;
    font-weight:700; padding:1px 5px; border-radius:3px; margin-left:4px; vertical-align:middle; }
.injury-badge-gtd { display:inline-block; background:#F9C62B; color:#000; font-size:0.65rem;
    font-weight:700; padding:1px 5px; border-radius:3px; margin-left:4px; vertical-align:middle; }
/* Game attractiveness badges */
.signal-badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:0.72rem;
    font-weight:700; letter-spacing:0.5px; margin-left:8px; }
.signal-high { background:rgba(0,255,100,0.18); color:#00ff64; border:1px solid rgba(0,255,100,0.3); }
.signal-medium { background:rgba(255,200,0,0.15); color:#F9C62B; border:1px solid rgba(255,200,0,0.3); }
.signal-low { background:rgba(255,68,68,0.15); color:#F24336; border:1px solid rgba(255,68,68,0.3); }
/* Skeleton / shimmer loading cards */
@keyframes shimmer {
    0% { background-position: -400px 0; }
    100% { background-position: 400px 0; }
}
.skeleton-card {
    background: linear-gradient(135deg, rgba(13,18,40,0.95) 0%, rgba(11,18,35,0.98) 100%);
    border: 1px solid rgba(0,213,89,0.09);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
}
.skeleton-line {
    height: 14px;
    border-radius: 4px;
    background: linear-gradient(90deg, rgba(0,213,89,0.06) 25%, rgba(0,213,89,0.10) 50%, rgba(0,213,89,0.06) 75%);
    background-size: 400px 100%;
    animation: shimmer 1.5s ease-in-out infinite;
    margin-bottom: 10px;
}
.skeleton-line.wide { width: 80%; }
.skeleton-line.medium { width: 55%; }
.skeleton-line.narrow { width: 35%; height: 10px; }
/* Status dashboard */
.status-dash { display:flex; gap:12px; flex-wrap:wrap; margin:6px 0 10px 0; }
.status-pill { display:inline-flex; align-items:center; gap:4px; padding:3px 10px;
    border-radius:6px; font-size:0.78rem; font-weight:600; }
.status-pill.ok { background:rgba(0,255,100,0.12); color:#00ff64; border:1px solid rgba(0,255,100,0.2); }
.status-pill.empty { background:rgba(255,94,0,0.12); color:#F9C62B; border:1px solid rgba(255,94,0,0.2); }
</style>
""", unsafe_allow_html=True)

st.title("📡 Live Games")
st.markdown(f"**{datetime.date.today().strftime('%A, %B %d, %Y')}** — Tonight's NBA Slate")

# ── Auto-Refresh Toggle (Enhancement #6) ─────────────────────
_auto_ref_col, _auto_ref_info = st.columns([1, 3])
with _auto_ref_col:
    _auto_refresh_on = st.toggle("🔄 Auto-Refresh", value=False, key="lg_auto_refresh_toggle",
                                  help="Automatically refresh the page every 90 seconds to keep data current")
with _auto_ref_info:
    if _auto_refresh_on:
        st.caption("🟢 Auto-refresh **ON** — page reloads every 90 seconds")
    else:
        st.caption("Auto-refresh is off. Toggle on to keep live data current.")

if _auto_refresh_on:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=90_000, key="live_games_auto_refresh")
    except ImportError:
        st.caption("⚠️ `streamlit-autorefresh` not installed. Auto-refresh unavailable.")

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Live Games — Two Independent Workflows
    
    **🔄 Auto-Load Tonight's Games** (recommended first step):
    1. Click this button to load tonight's NBA schedule
    2. It automatically pulls current rosters, player stats, and team stats
    3. Props are auto-generated from season averages for all active players
    4. Takes ~30-60 seconds depending on the number of games
    
    **📊 Get Live Platform Props & Analyze** (for real prop lines):
    1. Select which platforms to include (all major sportsbooks via The Odds API)
    2. Optionally configure Smart Filter settings
    3. Click the button to get REAL live prop lines from those platforms
    4. The engine automatically runs Neural Analysis on all retrieved props
    5. Results are merged with any props from Auto-Load
    
    💡 **Pro Tips:**
    - Use Auto-Load first, then Get Platform Props for the most complete analysis
    - Smart Filter reduces noise by deduplicating props and removing injured players
    - Props from both sources are merged — no data is lost
    """)

# ── Status Dashboard (Enhancement #7) ────────────────────────
_lg_games_count = len(st.session_state.get("todays_games", []))
_lg_players_count = len(load_players_data())
_lg_props_count = len(st.session_state.get("current_props", []))

_status_pills = []
if _lg_games_count:
    _status_pills.append(f'<span class="status-pill ok">✅ Games: {_lg_games_count}</span>')
else:
    _status_pills.append('<span class="status-pill empty">⚠️ Games: 0</span>')
if _lg_players_count:
    _status_pills.append(f'<span class="status-pill ok">✅ Players: {_lg_players_count:,}</span>')
else:
    _status_pills.append('<span class="status-pill empty">⚠️ Players: 0</span>')
if _lg_props_count:
    _status_pills.append(f'<span class="status-pill ok">✅ Props: {_lg_props_count:,}</span>')
else:
    _status_pills.append('<span class="status-pill empty">⚠️ Props: 0</span>')

st.markdown(f'<div class="status-dash">{"".join(_status_pills)}</div>', unsafe_allow_html=True)

# ============================================================
# SECTION: Action Buttons — Unified Flow (Enhancement #7)
# ─────────────────────────────────────────────────────────────
# PRIMARY CTA: ⚡ One-Click Setup
# ADVANCED OPTIONS: Auto-Load, Load Players Only, ETL, Platform Props
# ============================================================

# ── ⚡ One-Click Setup — Primary CTA ─────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,rgba(0,213,89,0.09),rgba(45,158,255,0.08));
            border:2px solid rgba(0,213,89,0.30);border-radius:12px;
            padding:14px 20px;margin-bottom:14px;text-align:center;">
  <div style="font-family:'Inter', sans-serif;font-size:1.05rem;font-weight:800;
              color:#00D559;text-shadow:0 0 12px rgba(0,213,89,0.65);letter-spacing:1px;">
    ⚡ One-Click Setup — Recommended
  </div>
  <div style="color:#6B7A9A;font-size:0.84rem;margin-top:4px;">
    Loads tonight's games + retrieves live prop lines from all platforms in one step
  </div>
</div>
""", unsafe_allow_html=True)

_one_click_col, _one_click_info = st.columns([1, 3])
with _one_click_col:
    one_click_setup_clicked = st.button(
        "⚡ One-Click Setup",
        key="one_click_setup_btn",
        type="primary",
        width="stretch",
        help="Runs BOTH Auto-Load (tonight's games + rosters + stats) AND Get Live Props from all platforms in one click.",
    )
with _one_click_info:
    st.caption(
        "**⚡ One-Click Setup** = Auto-Load Tonight's Games **+** Get Live Props from all major sportsbooks. "
        "Best choice for a fresh session — everything in one click."
    )

# ── Advanced Options (collapsed by default) ─────────────────
with st.expander("⚙️ Advanced Options — Individual Data Pipelines", expanded=False):
    st.markdown("""
    <div style="background:linear-gradient(90deg,rgba(0,213,89,0.06),rgba(45,158,255,0.04));
                border:1px solid rgba(0,213,89,0.12);border-radius:10px;
                padding:12px 18px;margin-bottom:14px;">
      <span style="color:#00D559;font-weight:700;font-size:0.95rem;">
        ⚡ Two independent data pipelines — choose based on your goal:
      </span><br>
      <span style="color:#6B7A9A;font-size:0.84rem;">
        <strong style="color:#e8f0ff;">🔄 Auto-Load</strong> = tonight's schedule + rosters + stats &nbsp;|&nbsp;
        <strong style="color:#e8f0ff;">📊 Get Platform Props</strong> = <em>real live lines</em> from all major sportsbooks → Neural Analysis
      </span>
    </div>
    """, unsafe_allow_html=True)

    auto_col, load_col, info_col = st.columns([1, 1, 2])

    with auto_col:
        auto_load_clicked = st.button(
            "🔄 Auto-Load Tonight's Games",
            width="stretch",
            type="primary",
            help="ONE CLICK: load tonight's games + current rosters + player stats + team stats",
        )

    with load_col:
        load_players_clicked = st.button(
            "⚡ Load Players Only",
            width="stretch",
            help="Re-load player stats for tonight's teams (games must already be loaded)",
        )

    with info_col:
        st.caption(
            "**Auto-Load** = games + rosters + stats. "
            "**Load Players Only** = refresh player data only."
        )

    # ── Platform Selector + Get Platform Props button ────────────────
    st.markdown("---")

    # Platform Props row — visually distinct section
    st.markdown("""
    <div style="margin-bottom:6px;">
      <span style="color:#2D9EFF;font-size:1.05rem;font-weight:800;font-family:'Inter', sans-serif;
                   text-shadow:0 0 10px rgba(45,158,255,0.5);">
        📊 Get Live Platform Props & Analyze
      </span>
      <span style="color:#6B7A9A;font-size:0.82rem;margin-left:10px;">
        — Retrieves <em>real</em> prop lines from live data, not season-average estimates
      </span>
    </div>
    """, unsafe_allow_html=True)

    _pp_col, _ud_col, _dk_col, _load_btn_col = st.columns([1, 1, 1, 2])

    with _pp_col:
        _include_pp = st.checkbox("🟢 PrizePicks", value=True, key="platform_pp_checkbox")
    with _ud_col:
        _include_ud = st.checkbox("🟡 Underdog Fantasy", value=True, key="platform_ud_checkbox")
    with _dk_col:
        _include_dk = st.checkbox("🔵 DraftKings Pick6", value=True, key="platform_dk_checkbox")

    # Smart Filter controls (collapsible)
    with st.expander("🧠 Smart Filter Settings", expanded=False):
        _sf_col1, _sf_col2, _sf_col3 = st.columns(3)
        with _sf_col1:
            _smart_filter_on = st.toggle(
                "🧠 Smart Filter",
                value=True,
                key="smart_filter_toggle",
                help="Deduplicate cross-platform props, filter to tonight's players, remove injured players, and cap props per player.",
            )
        with _sf_col2:
            _max_per_player = st.slider(
                "Max props per player",
                min_value=1, max_value=15, value=5,
                key="smart_filter_max_per_player",
                help="Cap the number of stat types analyzed per player.",
            )
        with _sf_col3:
            _all_stat_types = [
                "points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers",
                "ftm",
                "points_rebounds_assists", "points_rebounds", "points_assists", "rebounds_assists",
                "blocks_steals", "fantasy_score", "double_double", "triple_double",
            ]
            _selected_stats = st.multiselect(
                "Stat types to include",
                options=_all_stat_types,
                default=[
                    "points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers",
                    "ftm",
                    "points_rebounds_assists", "points_rebounds", "points_assists", "rebounds_assists",
                    "blocks_steals", "fantasy_score",
                ],
                key="smart_filter_stat_types",
                help="Only analyze these stat types. Deselect to include all.",
            )

    # ── Platform Preference ──────────────────────────────────────
    with st.expander("⚙️ Platform Settings", expanded=False):
        _PLATFORM_OPTIONS = [
            "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
        ]
        if "joseph_preferred_platform" not in st.session_state:
            st.session_state["joseph_preferred_platform"] = "PrizePicks"

        st.markdown(
            '<span style="color:#e2e8f0;font-size:0.88rem;font-family:Inter,sans-serif">'
            'What betting app are you using tonight?</span>',
            unsafe_allow_html=True,
        )
        _lg_platform = st.radio(
            "Preferred betting platform",
            _PLATFORM_OPTIONS,
            index=_PLATFORM_OPTIONS.index(st.session_state["joseph_preferred_platform"]),
            horizontal=True,
            label_visibility="collapsed",
            key="lg_platform_radio",
        )
        st.session_state["joseph_preferred_platform"] = _lg_platform

    with _load_btn_col:
        _any_platform_selected = _include_pp or _include_ud or _include_dk
        platform_props_clicked = st.button(
            "📊 Get Live Props & Analyze",
            width="stretch",
            type="primary",
            help="Get REAL live prop lines from selected platforms, then run full Neural Analysis. Works independently — no need to Auto-Load first.",
            disabled=not _any_platform_selected,
            key="platform_props_btn",
        )

    st.markdown("---")

    # ── ETL Data Pull Section ────────────────────────────────────────────────
    if _ETL_AVAILABLE_LG:
        with st.expander("🗄️ ETL Data Pull — Fresh Stats from Local Database", expanded=False):
            st.markdown(
                '<span style="color:#6B7A9A;font-size:0.84rem;">'
                'Pull the latest player stats into your local database before loading games. '
                '<strong style="color:#e8f0ff;">Smart Update</strong> fetches only new data (~30s). '
                '<strong style="color:#e8f0ff;">Full Pull</strong> refreshes the entire season (~60s).'
                '</span>',
                unsafe_allow_html=True,
            )
            _etl_col1, _etl_col2, _etl_col3 = st.columns([1, 1, 2])
            with _etl_col1:
                _etl_smart_clicked = st.button(
                    "⚡ Smart ETL Update",
                    key="lg_etl_smart_btn",
                    help="Incremental update — fetches only new games since the last stored date (~30 seconds)",
                )
            with _etl_col2:
                _etl_full_clicked = st.button(
                    "🔄 Full ETL Pull",
                    key="lg_etl_full_btn",
                    help="Re-pull entire season from nba_api and repopulate db/smartpicks.db (~60 seconds)",
                )
            with _etl_col3:
                st.caption(
                    "Run ETL **before** Auto-Load for the freshest stats. "
                    "One-Click Setup now includes a Smart ETL Update automatically."
                )

            if _etl_smart_clicked:
                _etl_bar = st.progress(0, text="Starting Smart ETL Update…")
                _etl_status = st.empty()
                try:
                    def _lg_etl_progress(current, total, message):
                        frac = current / max(total, 1)
                        _etl_bar.progress(frac, text=message)
                        _etl_status.caption(message)

                    result = _lg_refresh_etl(progress_callback=_lg_etl_progress)
                    _etl_bar.progress(1.0, text="Done!")
                    ng = result.get("new_games", 0)
                    nl = result.get("new_logs", 0)
                    err = result.get("error")
                    if err:
                        st.error(f"❌ Smart ETL Update failed: {err}")
                    else:
                        st.success(f"✅ Smart ETL Update complete! **{ng}** new game(s) · **{nl}** new log row(s).")
                    _etl_bar.empty()
                    _etl_status.empty()
                except Exception as _etl_err:
                    _etl_bar.empty()
                    _etl_status.empty()
                    st.error(f"❌ Smart ETL Update failed: {_etl_err}")

            if _etl_full_clicked:
                _etl_bar = st.progress(0, text="Starting Full ETL Pull…")
                _etl_status = st.empty()
                try:
                    def _lg_etl_full_progress(current, total, message):
                        frac = current / max(total, 1)
                        _etl_bar.progress(frac, text=message)
                        _etl_status.caption(message)

                    result = _lg_full_refresh_etl(progress_callback=_lg_etl_full_progress)
                    _etl_bar.progress(1.0, text="Done!")
                    np_ = result.get("players_inserted", 0)
                    ng = result.get("games_inserted", 0)
                    nl = result.get("logs_inserted", 0)
                    err = result.get("error")
                    if err:
                        st.error(f"❌ Full ETL Pull failed: {err}")
                    else:
                        st.success(
                            f"✅ Full ETL Pull complete! "
                            f"**{np_}** players · **{ng}** games · **{nl}** logs inserted."
                        )
                    _etl_bar.empty()
                    _etl_status.empty()
                except Exception as _etl_err:
                    _etl_bar.empty()
                    _etl_status.empty()
                    st.error(f"❌ Full ETL Pull failed: {_etl_err}")

st.markdown("---")

if auto_load_clicked:
    progress_bar = st.progress(0)
    status_text = st.empty()
    # ── Joseph Loading Screen — NBA fun facts while loading games ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _joseph_games_loader = joseph_loading_placeholder("Loading tonight's NBA games")
    except Exception:
        _joseph_games_loader = None

    try:
        status_text.text("⏳ Step 1/3 — Loading tonight's games...")
        progress_bar.progress(5)
        games = get_todays_games()

        if not games:
            progress_bar.empty()
            status_text.empty()
            st.warning(
                "⚠️ Could not auto-load games. Possible reasons:\n"
                "- No games scheduled tonight\n"
                "- No internet connection\n\n"
                "Please enter games manually using the form below."
            )
        else:
            st.session_state["todays_games"] = games

            status_text.text(f"⏳ Step 2/3 — Loading rosters, stats & injuries for {len(games)} game(s)...")
            progress_bar.progress(25)

            players_ok = get_todays_players(games)

            # Load the injury map written by get_todays_players
            injury_map = {}
            if players_ok:
                try:
                    from data.data_manager import load_injury_status as _load_inj
                    injury_map = _load_inj()
                    st.session_state["injury_status_map"] = injury_map
                except Exception as _inj_load_err:
                    _logger.warning(f"Auto-load: could not load injury map: {_inj_load_err}")

            # Step 3: Load team stats so teams.csv has real data
            status_text.text("⏳ Step 3/3 — Loading team stats & standings...")
            progress_bar.progress(65)
            teams_ok = False
            try:
                from data.nba_data_service import get_team_stats as _ldf_team_stats
                teams_ok = _ldf_team_stats()
            except Exception as _ts_err:
                _logger.warning(f"Auto-load: team stats load failed (non-fatal): {_ts_err}")

            # Pre-load standings into session state for other pages
            try:
                from data.nba_data_service import get_standings as _ldf_standings
                _al_standings = _ldf_standings()
                if _al_standings:
                    st.session_state["league_standings"] = _al_standings
            except Exception as _st_err:
                _logger.debug(f"Auto-load: standings pre-load skipped: {_st_err}")

            # Clear cached CSV loaders so freshly-written data is picked up
            try:
                from data.data_manager import clear_all_caches as _al_clear_caches
                _al_clear_caches()
            except Exception as _cache_err:
                _logger.debug(f"Auto-load: cache clear failed (non-fatal): {_cache_err}")

            status_text.text("⏳ Finalizing…")
            progress_bar.progress(90)

            time.sleep(0.3)
            progress_bar.progress(100)
            status_text.text("✅ Done! Tonight's slate is ready.")
            time.sleep(1)
            status_text.empty()
            progress_bar.empty()
            # Dismiss the Joseph loading screen
            if _joseph_games_loader is not None:
                try:
                    _joseph_games_loader.empty()
                except Exception:
                    pass

            st.success(
                f"✅ Loaded **{len(games)} game(s)** for tonight! "
                f"Players: {'✅' if players_ok else '⚠️ failed'} | "
                f"Teams: {'✅' if teams_ok else '⚠️ failed'} | "
                f"Injuries: {'✅' if injury_map else '⚠️ unavailable'}"
            )
            st.rerun()

    except Exception as _exc:
        progress_bar.empty()
        status_text.empty()
        if _joseph_games_loader is not None:
            try:
                _joseph_games_loader.empty()
            except Exception:
                pass
        _exc_str = str(_exc)
        if "WebSocketClosedError" in _exc_str or "StreamClosedError" in _exc_str:
            pass  # Connection closed — user navigated away
        else:
            st.error(f"❌ Auto-load failed: {_exc}")

if load_players_clicked:
    todays_games_to_load = st.session_state.get("todays_games", [])
    if not todays_games_to_load:
        st.warning(
            "⚠️ No games loaded yet. Click **Auto-Load Tonight's Games** first, "
            "or add games manually below."
        )
    else:
        progress_bar2 = st.progress(0, text="Loading player data for tonight's teams...")
        status_text2 = st.empty()

        def _on_players_progress(current, total, message):
            frac = current / max(total, 1)
            progress_bar2.progress(frac, text=message)
            status_text2.caption(message)

        try:
            with st.spinner("⚡ Loading current rosters and player stats..."):
                success = get_todays_players(
                    todays_games_to_load,
                    progress_callback=_on_players_progress,
                )

            if success:
                st.success("✅ Player stats refreshed for tonight's teams!")
                st.rerun()
            else:
                st.error(
                    "❌ Could not load player stats. Check your internet connection "
                    "or try the Update Data page."
                )
        except Exception as _lp_exc:
            _lp_err = str(_lp_exc)
            if "WebSocketClosedError" not in _lp_err and "StreamClosedError" not in _lp_err:
                st.error(f"❌ Failed to load player data: {_lp_exc}")
        finally:
            progress_bar2.empty()
            status_text2.empty()

# ============================================================
# SECTION: Platform Props & Analyze Button (INDEPENDENT PIPELINE)
# This is completely separate from Auto-Load. It:
# 1. Retrieves live props from selected platforms
# 2. Applies Smart Filter to reduce prop count
# 3. Runs each prop through the full Neural Analysis engine
# 4. Displays best bets grouped by platform
# 5. Auto-logs top picks to the Bet Tracker
# ============================================================

if platform_props_clicked:
    st.divider()
    st.subheader("📊 Platform Props & Neural Analysis")

    _platforms_label = ", ".join(filter(None, [
        "PrizePicks" if _include_pp else "",
        "Underdog Fantasy" if _include_ud else "",
        "DraftKings Pick6" if _include_dk else "",
    ]))
    st.markdown(f"Loading live props from **{_platforms_label}** and running Neural Analysis…")

    pp_bar = st.progress(0)
    pp_status = st.empty()

    try:
        # ── Step 0: Auto-load games if not already loaded ──────────────
        _todays_games = st.session_state.get("todays_games", [])
        if not _todays_games:
            pp_status.text("⏳ 0/5 — No games loaded. Auto-loading tonight's schedule…")
            pp_bar.progress(2)
            from data.nba_data_service import get_todays_games as _auto_get_games
            _todays_games = _auto_get_games()
            if _todays_games:
                st.session_state["todays_games"] = _todays_games
                st.info(f"🏟️ Auto-loaded **{len(_todays_games)} game(s)** for tonight.")
            else:
                st.warning("⚠️ No games found for tonight. Platform prop analysis may be limited.")

        # ── Step 0b: Auto-load player data if CSV is empty ─────────────
        from data.data_manager import load_players_data as _lp_check
        _check_players = _lp_check()
        if not _check_players and _todays_games:
            pp_status.text("⏳ 0/5 — No player data. Loading rosters for tonight's teams…")
            pp_bar.progress(5)
            from data.nba_data_service import get_todays_players as _auto_get_players
            _auto_get_players(_todays_games)

        # ── Step 1: Get props from selected platforms ────────────────
        pp_status.text("⏳ 1/5 — Retrieving props from selected platforms…")
        pp_bar.progress(10)

        from data.sportsbook_service import (
            get_all_sportsbook_props,
            smart_filter_props,
        )

        odds_api_key = st.session_state.get("odds_api_key") or ""
        all_platform_props = get_all_sportsbook_props(
            include_prizepicks=_include_pp,
            include_underdog=_include_ud,
            include_draftkings=_include_dk,
            odds_api_key=odds_api_key or None,
        )

        raw_count = len(all_platform_props)
        pp_status.text(f"⏳ 2/5 — Retrieved {raw_count:,} props. Applying Smart Filter…")
        pp_bar.progress(20)

        # ── Step 2: Smart Filter (optional) ───────────────────────────
        # Read controls from the UI (already rendered above)
        _smart_enabled = st.session_state.get("smart_filter_toggle", True)
        _max_pp = st.session_state.get("smart_filter_max_per_player", 5)
        _stat_sel = st.session_state.get("smart_filter_stat_types") or None

        if _smart_enabled:
            _injury_map = st.session_state.get("injury_status_map", {})
            props_to_analyze, _filter_summary = smart_filter_props(
                all_props=all_platform_props,
                todays_games=_todays_games if _todays_games else None,
                injury_map=_injury_map if _injury_map else None,
                max_props_per_player=_max_pp,
                stat_types=_stat_sel if _stat_sel else None,
            )
            st.info(
                f"🧠 **Smart Filter:** Retrieved **{raw_count:,}** props → "
                f"reduced to **{_filter_summary['final_count']:,}** high-signal props "
                f"(**{_filter_summary['reduction_pct']:.0f}% reduction**) | "
                f"After team filter: {_filter_summary['after_team_filter']:,} · "
                f"After injury filter: {_filter_summary['after_injury_filter']:,} · "
                f"After dedup: {_filter_summary['after_dedup']:,} · "
                f"After stat filter: {_filter_summary['after_stat_filter']:,} · "
                f"After player cap: {_filter_summary['after_per_player_cap']:,}"
            )
        else:
            props_to_analyze = all_platform_props
            st.info(f"ℹ️ Smart Filter is OFF. Analyzing all **{raw_count:,}** props.")

        # ── Persist filtered props to both session state keys and disk ──
        # Merge new platform props with existing props (don't replace).
        def _merge_props(existing: list, new_props: list) -> list:
            """Merge new_props into existing, deduplicating by player_name+stat_type+platform."""
            seen = set()
            merged = []
            for p in existing:
                key = (str(p.get("player_name","")).lower(), str(p.get("stat_type","")).lower(), str(p.get("platform","")).lower())
                if key not in seen:
                    seen.add(key)
                    merged.append(p)
            for p in new_props:
                key = (str(p.get("player_name","")).lower(), str(p.get("stat_type","")).lower(), str(p.get("platform","")).lower())
                if key not in seen:
                    seen.add(key)
                    merged.append(p)
            return merged

        try:
            from data.data_manager import (
                save_props_to_session as _save_current,
                save_platform_props_to_csv as _save_csv,
            )
            from data.data_manager import save_platform_props_to_session as _save_platform
            _existing_props = list(st.session_state.get("current_props", []))
            _merged_props = _merge_props(_existing_props, props_to_analyze)
            _save_current(_merged_props, st.session_state)
            _save_platform(props_to_analyze, st.session_state)
            _save_csv(props_to_analyze)
        except Exception as _save_err:
            # Best-effort — don't abort analysis if save fails (e.g. closed WS)
            try:
                _logger.warning(f"Live Games: non-fatal save error: {_save_err}")
            except Exception:
                pass

        pp_status.text(f"⏳ 3/5 — Loading player data for {len(props_to_analyze):,} props…")
        pp_bar.progress(25)

        # ── Step 3: Load player data for analysis ─────────────────────
        from data.data_manager import load_players_data as _lp
        players_data_for_analysis = _lp()

        # Fix 7: Enrich platform names → CSV canonical names before analysis
        # (e.g. "Nic Claxton" → "Nicolas Claxton" so stats look-up succeeds)
        try:
            from data.sportsbook_service import enrich_props_with_csv_names as _enrich
            props_to_analyze = _enrich(props_to_analyze, players_data_for_analysis)
        except Exception as _enrich_err:
            try:
                _logger.warning(f"Live Games: enrichment step failed (non-fatal): {_enrich_err}")
            except Exception:
                pass

        player_lookup: dict = {}
        for p in players_data_for_analysis:
            _n = str(p.get("name", "")).lower().strip()
            if _n:
                player_lookup[_n] = p

        # ── Step 4: Run Neural Analysis on filtered props ──────────────
        pp_status.text(f"⏳ 4/5 — Running Neural Analysis on {len(props_to_analyze):,} props…")
        pp_bar.progress(40)

        from engine.projections import build_player_projection, get_stat_standard_deviation, POSITION_PRIORS
        from engine.simulation import run_quantum_matrix_simulation, simulate_combo_stat, simulate_fantasy_score
        from engine import COMBO_STAT_TYPES, FANTASY_STAT_TYPES
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING
        from engine.edge_detection import analyze_directional_forces, should_avoid_prop, classify_bet_type
        from engine.confidence import calculate_confidence_score
        from data.data_manager import load_defensive_ratings_data, load_teams_data as _load_teams

        _defensive_ratings = load_defensive_ratings_data()
        _teams_data = _load_teams()

        analyzed_props: list = []
        games_context = _todays_games  # Use auto-loaded games from Step 0
        injury_map = st.session_state.get("injury_status_map", {})

        # Bio position strings → POSITION_PRIORS keys
        _BIO_POS_ALIAS = {"Guard": "PG", "Forward": "SF", "Center": "C"}

        _PLATFORM_STAT_MAP = {
            "pts": "points", "reb": "rebounds", "ast": "assists",
            "stl": "steals", "blk": "blocks", "to": "turnovers", "tov": "turnovers",
            "3pm": "threes", "fg3m": "threes", "ftm": "ftm",
            "pts+reb": "points_rebounds", "pts+ast": "points_assists",
            "reb+ast": "rebounds_assists", "pts+reb+ast": "points_rebounds_assists",
            "blk+stl": "blocks_steals", "blks+stls": "blocks_steals",
        }

        for prop in props_to_analyze:
            try:
                player_name = str(prop.get("player_name") or "").strip()
                raw_stat = str(prop.get("stat_type") or prop.get("stat") or "").lower().strip()
                stat_type = _PLATFORM_STAT_MAP.get(raw_stat, raw_stat)
                prop_line = float(prop.get("line") or prop.get("prop_line") or 0)
                platform_name = str(prop.get("platform") or "Unknown")
                if not player_name or not stat_type or prop_line <= 0:
                    continue

                player_data = player_lookup.get(player_name.lower())
                if not player_data:
                    # Platform props are the source of truth for active players.
                    # Build a minimal stub from POSITION_PRIORS so we can still analyze
                    # players that are active/playing but missing from the CSV
                    # (e.g., due to injury-filtered CSV from a previous auto-load).
                    player_team = str(prop.get("team") or prop.get("player_team") or "")

                    # Attempt to resolve position from player bio; default to SF
                    _pos = "SF"
                    try:
                        from data.player_profile_service import get_player_bio
                        _bio = get_player_bio(player_name)
                        if _bio.get("position"):
                            # Bio position may be multi-valued ("Guard-Forward"); take first token
                            _bio_pos = _bio["position"].split("-")[0].strip()
                            _pos = _BIO_POS_ALIAS.get(_bio_pos, _bio_pos)
                    except Exception:
                        pass

                    _prior = POSITION_PRIORS.get(_pos, POSITION_PRIORS["SF"])
                    _stub: dict = {
                        "name": player_name,
                        "team": player_team,
                        "position": _pos,
                        "games_played": 30,       # above Bayesian threshold (25) — trust prop_line anchor
                        "minutes_avg": 28.0,
                        "points_avg": _prior["points"],
                        "rebounds_avg": _prior["rebounds"],
                        "assists_avg": _prior["assists"],
                        "threes_avg": _prior["threes"],
                        "steals_avg": _prior["steals"],
                        "blocks_avg": _prior["blocks"],
                        "turnovers_avg": _prior["turnovers"],
                    }

                    # For the specific stat being analyzed, anchor to prop_line
                    if stat_type in _prior:
                        _stub[f"{stat_type}_avg"] = prop_line

                    player_data = _stub

                # Build game context — find this player's game in tonight's slate
                player_team = player_data.get("team", "")
                game_ctx: dict = {
                    "opponent": "",
                    "vegas_spread": 0.0,
                    "game_total": 220.0,
                    "is_home": True,
                    "rest_days": 2,
                    "moneyline_home": None,
                    "moneyline_away": None,
                    "consensus_spread": None,
                    "consensus_total": None,
                    "bookmaker_count": 0,
                }
                for g in games_context:
                    home_team = g.get("home_team", "")
                    away_team = g.get("away_team", "")
                    if player_team in (home_team, away_team):
                        is_home = player_team == home_team
                        _vs_raw = g.get("vegas_spread")
                        _gt_raw = g.get("game_total")
                        try:
                            _vs_val = float(_vs_raw) if _vs_raw is not None else 0.0
                        except (TypeError, ValueError):
                            _vs_val = 0.0
                        try:
                            _gt_val = float(_gt_raw) if _gt_raw is not None else 220.0
                        except (TypeError, ValueError):
                            _gt_val = 220.0
                        game_ctx = {
                            "opponent": away_team if is_home else home_team,
                            "home_team": home_team,
                            "away_team": away_team,
                            "vegas_spread": _vs_val,
                            "game_total": _gt_val,
                            "is_home": is_home,
                            "rest_days": 2,
                            "game_id": str(g.get("game_id") or ""),
                            "home_team_id": g.get("home_team_id"),
                            "away_team_id": g.get("away_team_id"),
                            # Odds API consensus fields (may be None if key not configured)
                            "moneyline_home": g.get("moneyline_home"),
                            "moneyline_away": g.get("moneyline_away"),
                            "consensus_spread": g.get("consensus_spread"),
                            "consensus_total": g.get("consensus_total"),
                            "bookmaker_count": g.get("bookmaker_count", 0),
                            "spread_range": g.get("spread_range", (None, None)),
                            "total_range": g.get("total_range", (None, None)),
                        }
                        # Fill in team IDs from abbreviation map when not explicit
                        if not game_ctx["home_team_id"] or not game_ctx["away_team_id"]:
                            try:
                                from data.player_profile_service import _TEAM_ABBREV_TO_ID as _TID
                                game_ctx["home_team_id"] = game_ctx["home_team_id"] or _TID.get(home_team.upper())
                                game_ctx["away_team_id"] = game_ctx["away_team_id"] or _TID.get(away_team.upper())
                            except Exception:
                                pass
                        break

                # ── Pull player advanced context from Deep Fetch enrichment ──
                _live_adv_context: dict | None = None
                try:
                    _lg_enr = st.session_state.get("advanced_enrichment", {}).get(
                        game_ctx.get("game_id", ""), {}
                    )
                    _lg_metrics = _lg_enr.get("player_metrics", [])
                    _lg_pid = player_data.get("player_id") or player_data.get("id")
                    _lg_pname = str(player_data.get("name", "")).lower()
                    for _lm in _lg_metrics:
                        _lmid = _lm.get("PLAYER_ID") or _lm.get("playerId")
                        _lmname = str(_lm.get("PLAYER_NAME") or _lm.get("playerName") or "").lower()
                        if (_lg_pid and _lmid and int(_lg_pid) == int(_lmid)) or (
                            _lg_pname and _lmname and _lg_pname in _lmname
                        ):
                            _usg = _lm.get("E_USG_PCT") or _lm.get("USG_PCT") or _lm.get("usage_pct")
                            if _usg is not None:
                                try:
                                    _usg_f = float(_usg)
                                    _live_adv_context = {
                                        "usage_pct": _usg_f / 100.0 if _usg_f > 1.0 else _usg_f
                                    }
                                except (TypeError, ValueError):
                                    pass
                            break
                except Exception:
                    pass

                # Projection — use proper signature matching build_player_projection
                # Fetch recent game logs from DB for projection context
                _recent_form_for_proj: list | None = None
                try:
                    from data.etl_data_service import get_player_game_logs as _etl_get_logs_live
                    _pid_live = player_data.get("player_id", "")
                    if _pid_live:
                        _recent_form_for_proj = _etl_get_logs_live(int(_pid_live), limit=20) or None
                except Exception:
                    pass

                proj = build_player_projection(
                    player_data=player_data,
                    opponent_team_abbreviation=game_ctx.get("opponent", ""),
                    is_home_game=game_ctx.get("is_home", True),
                    rest_days=game_ctx.get("rest_days", 2),
                    game_total=game_ctx.get("game_total", 220.0),
                    defensive_ratings_data=_defensive_ratings,
                    teams_data=_teams_data,
                    vegas_spread=game_ctx.get("vegas_spread", 0.0),
                    advanced_context=_live_adv_context,
                    recent_form_games=_recent_form_for_proj,
                )

                # ── Projection retrieval & simulation ────────────────────
                # Combo/fantasy stats need component-level projection;
                # simple stats read directly from build_player_projection().
                blowout_risk = proj.get("blowout_risk_factor", 0.1)
                _sim_kwargs = dict(
                    blowout_risk_factor=blowout_risk,
                    pace_adjustment_factor=proj.get("pace_factor", 1.0),
                    matchup_adjustment_factor=proj.get("defense_factor", 1.0),
                    home_away_adjustment=proj.get("home_away_factor", 0.0),
                    rest_adjustment_factor=proj.get("rest_factor", 1.0),
                )
                _game_ctx = game_ctx if game_ctx.get("game_id") else None

                if stat_type in COMBO_STAT_TYPES:
                    # Correlated simulation for combo stats (PRA, Pts+Reb, etc.)
                    _components = COMBO_STATS.get(stat_type, [])
                    _comp_proj = {
                        s: proj.get(f"projected_{s}", float(player_data.get(f"{s}_avg", 0) or 0))
                        for s in _components
                    }
                    _comp_std = {s: get_stat_standard_deviation(player_data, s) for s in _components}
                    projected_value = sum(_comp_proj.values())
                    std_dev = sum(_comp_std.values())  # conservative upper bound
                    if projected_value <= 0:
                        continue
                    sim = simulate_combo_stat(
                        component_projections=_comp_proj,
                        component_std_devs=_comp_std,
                        prop_line=prop_line,
                        number_of_simulations=1000,
                        game_context=_game_ctx,
                        **_sim_kwargs,
                    )
                    projected_value = sim.get("adjusted_projection", projected_value)

                elif stat_type in FANTASY_STAT_TYPES:
                    # Weighted-sum simulation for fantasy score props
                    _formula = FANTASY_SCORING.get(stat_type, {})
                    _stat_proj = {
                        s: proj.get(f"projected_{s}", float(player_data.get(f"{s}_avg", 0) or 0))
                        for s in _formula
                    }
                    _stat_std = {s: get_stat_standard_deviation(player_data, s) for s in _formula}
                    projected_value = sum(v * _formula[s] for s, v in _stat_proj.items())
                    std_dev = sum(abs(_formula[s]) * _stat_std[s] for s in _formula)
                    if projected_value <= 0:
                        continue
                    sim = simulate_fantasy_score(
                        stat_projections=_stat_proj,
                        stat_std_devs=_stat_std,
                        fantasy_formula=_formula,
                        prop_line=prop_line,
                        number_of_simulations=1000,
                        **_sim_kwargs,
                    )
                    projected_value = sim.get("adjusted_projection", projected_value)

                else:
                    # Simple stat: standard projection lookup + QME simulation
                    projected_value = proj.get(
                        f"projected_{stat_type}",
                        float(player_data.get(f"{stat_type}_avg", prop_line) or prop_line)
                    )
                    try:
                        projected_value = float(projected_value)
                    except (TypeError, ValueError):
                        projected_value = float(player_data.get(f"{stat_type}_avg", prop_line) or prop_line)

                    if projected_value <= 0:
                        continue

                    std_dev = get_stat_standard_deviation(player_data, stat_type)
                    if not std_dev or std_dev <= 0:
                        std_dev = projected_value * 0.25

                    sim = run_quantum_matrix_simulation(
                        projected_stat_average=projected_value,
                        stat_standard_deviation=std_dev,
                        prop_line=prop_line,
                        number_of_simulations=1000,
                        stat_type=stat_type,
                        projected_minutes=proj.get("projected_minutes"),
                        game_context=_game_ctx,
                        **_sim_kwargs,
                    )
                prob_over = sim.get("probability_over", 0.5)
                raw_edge = sim.get("edge_percentage", 0.0)

                if raw_edge is None:
                    raw_edge = 0.0

                # Edge analysis
                forces = analyze_directional_forces(
                    player_data=player_data,
                    prop_line=prop_line,
                    stat_type=stat_type,
                    projection_result=proj,
                    game_context=game_ctx,
                )
                should_skip, avoid_reasons = should_avoid_prop(
                    probability_over=prob_over,
                    directional_forces_result=forces,
                    edge_percentage=raw_edge,
                    stat_standard_deviation=std_dev,
                    stat_average=projected_value,
                    stat_type=stat_type,
                )
                if should_skip:
                    continue

                # Confidence
                # Fetch real matchup context when available (cached via nba_data_service)
                _lg_on_off: dict | None = None
                _lg_matchup: dict | None = None
                try:
                    from data.nba_data_service import get_player_on_off, get_box_score_matchups
                    _lg_tid = game_ctx.get("home_team_id") if game_ctx.get("is_home") else game_ctx.get("away_team_id")
                    if _lg_tid:
                        _lg_on_off = get_player_on_off(_lg_tid) or None
                    _lg_gid = game_ctx.get("game_id", "")
                    if _lg_gid:
                        _lg_matchup = get_box_score_matchups(_lg_gid) or None
                except Exception:
                    pass

                conf = calculate_confidence_score(
                    probability_over=prob_over,
                    edge_percentage=raw_edge,
                    directional_forces=forces,
                    defense_factor=proj.get("defense_factor", 1.0),
                    stat_standard_deviation=std_dev,
                    stat_average=projected_value,
                    simulation_results=sim,
                    games_played=int(player_data.get("games_played", 10) or 10),
                    stat_type=stat_type,
                    games_played_season=int(player_data.get("games_played", 10) or 10),
                    platform=platform_name,
                    on_off_data=_lg_on_off,
                    matchup_data=_lg_matchup,
                )
                confidence_score = conf.get("confidence_score", 0)
                tier = conf.get("tier", "Bronze")
                direction = conf.get("direction", "OVER")

                if tier == "Avoid":
                    continue

                # Skip props below the minimum edge threshold (Bug 3)
                if abs(raw_edge) < 5.0:
                    continue

                # Classify bet type (Bug 2)
                _bet_cls = classify_bet_type(
                    probability_over=prob_over,
                    edge_percentage=raw_edge,
                    stat_standard_deviation=std_dev,
                    projected_stat=projected_value,
                    prop_line=prop_line,
                    stat_type=stat_type,
                    directional_forces_result=forces,
                    rest_days=game_ctx.get("rest_days", 1),
                    vegas_spread=game_ctx.get("vegas_spread", 0.0),
                    season_average=float(player_data.get(f"{stat_type}_avg", projected_value) or projected_value),
                    line_source=prop.get("platform", platform_name),
                )

                analyzed_props.append({
                    "player_name": player_name,
                    "team": player_data.get("team", ""),
                    "player_team": player_data.get("team", ""),
                    "stat_type": stat_type,
                    "prop_line": prop_line,
                    "line": prop_line,
                    "projected_value": round(projected_value, 1),
                    "edge_percentage": round(raw_edge, 1),
                    "confidence_score": confidence_score,
                    "tier": tier,
                    "tier_emoji": conf.get("tier_emoji", "🥉"),
                    "direction": direction,
                    "platform": platform_name,
                    "over_odds": prop.get("over_odds", -110),
                    "under_odds": prop.get("under_odds", -110),
                    "bet_type": _bet_cls.get("bet_type", "normal"),
                    "bet_type_label": _bet_cls.get("bet_type_label", "Normal Bet"),
                    "probability_over": prob_over,
                    "line_source": prop.get("platform", platform_name),
                })
            except Exception as _prop_err:
                pass  # Skip props that fail analysis

        # Sort by confidence descending
        analyzed_props.sort(key=lambda x: x["confidence_score"], reverse=True)

        # Per-player cap: max 3 props per player, keeping highest confidence (Bug 3)
        _player_prop_counts: dict = {}
        _capped_props = []
        for _ap in analyzed_props:
            _pname = _ap.get("player_name", "")
            _count = _player_prop_counts.get(_pname, 0)
            if _count < 3:
                _capped_props.append(_ap)
                _player_prop_counts[_pname] = _count + 1
        analyzed_props = _capped_props

        # ── Save analyzed props to session state for downstream pages ─
        # Game Report (page 4), Entry Builder (page 6), and The Studio
        # (page 7) read from "analysis_results" in session state.
        if analyzed_props:
            st.session_state["analysis_results"] = analyzed_props

        pp_status.text(f"⏳ 5/5 — Analysis complete: {len(analyzed_props)} qualifying pick(s). Auto-logging top picks…")
        pp_bar.progress(75)

        # ── Step 5: Persist picks + auto-log top bets to Bet Tracker ──
        if analyzed_props:
            try:
                from tracking.database import initialize_database, insert_bet, insert_analysis_picks
                import sqlite3 as _sqlite3
                initialize_database()
                import datetime as _dt2
                _today = _dt2.date.today().isoformat()

                # 5a. Persist ALL analysed picks to all_analysis_picks (deduped inside)
                _picks_stored = insert_analysis_picks(analyzed_props)
                if _picks_stored:
                    st.toast(f"💾 Stored {_picks_stored} new pick(s) to All Analysis Picks.")

                # 5b. Build dedup set from today's existing bets to avoid duplicates
                _existing_bet_keys: set = set()
                try:
                    from tracking.database import DB_FILE_PATH as _DB_PATH_LG
                    with _sqlite3.connect(str(_DB_PATH_LG)) as _conn_lg:
                        for _row in _conn_lg.execute(
                            "SELECT lower(player_name), stat_type, prop_line, direction "
                            "FROM bets WHERE bet_date = ?", (_today,),
                        ).fetchall():
                            _existing_bet_keys.add((_row[0], _row[1], float(_row[2] or 0), _row[3]))
                except Exception:
                    pass  # If dedup query fails, log without dedup (same as before)

                _logged = 0
                # Log top 5 per platform — with dedup
                _by_plat: dict = {}
                for _ap in analyzed_props:
                    _pl = _ap["platform"]
                    _by_plat.setdefault(_pl, []).append(_ap)
                for _pl, _picks in _by_plat.items():
                    for _pick in _picks[:5]:
                        _bet_key = (
                            _pick["player_name"].lower(),
                            _pick["stat_type"],
                            float(_pick.get("prop_line") or 0),
                            _pick["direction"],
                        )
                        if _bet_key in _existing_bet_keys:
                            continue  # Already logged today — skip
                        insert_bet({
                            "player_name": _pick["player_name"],
                            "team": _pick.get("team", ""),
                            "stat_type": _pick["stat_type"],
                            "prop_line": _pick["prop_line"],
                            "direction": _pick["direction"],
                            "projected_value": _pick["projected_value"],
                            "edge_percentage": _pick["edge_percentage"],
                            "confidence_score": _pick["confidence_score"],
                            "tier": _pick["tier"],
                            "platform": _pl,
                            "bet_date": _today,
                            "auto_logged": 1,
                            "source": "live_games",
                            "notes": f"Auto-logged from Platform Props & Analyze",
                        })
                        _existing_bet_keys.add(_bet_key)
                        _logged += 1
                if _logged:
                    st.toast(f"📊 Auto-logged {_logged} platform prop pick(s) to Bet Tracker.")
            except Exception as _log_err:
                st.toast(f"⚠️ Could not auto-log picks: {_log_err}")

        pp_status.text("✅ 5/5 — Done!")
        pp_bar.progress(100)
        time.sleep(0.5)
        pp_bar.empty()
        pp_status.empty()

        # ── Step 5: Display results grouped by platform ──────────────────
        if not analyzed_props:
            st.warning(
                "⚠️ No qualifying picks found from platform props. "
                "This may mean:\n"
                "- No data returned from platforms (they may be temporarily unavailable)\n"
                "- All props were filtered out by the Neural Analysis edge/confidence gates\n"
                "- No player data loaded — try clicking **Auto-Load Tonight's Games** first"
            )
        else:
            st.success("✅ Props retrieved and merged! Go to ⚡ Neural Analysis to run analysis on all loaded props.")
            from styles.theme import get_bet_card_css, get_bet_card_html, get_summary_cards_html
            st.markdown(get_bet_card_css(), unsafe_allow_html=True)

            # Summary
            total_picks = len(analyzed_props)
            plat_count  = sum(1 for p in analyzed_props if p["tier"] == "Platinum")
            gold_count  = sum(1 for p in analyzed_props if p["tier"] == "Gold")
            st.success(
                f"✅ **{total_picks} qualifying picks** found across platforms | "
                f"💎 {plat_count} Platinum · 🥇 {gold_count} Gold"
            )

            # Group by platform
            platforms_order = [
                "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
            ]
            all_platforms = sorted({p["platform"] for p in analyzed_props})
            # Show known platforms first, then any others
            ordered_platforms = [pl for pl in platforms_order if pl in all_platforms]
            ordered_platforms += [pl for pl in all_platforms if pl not in platforms_order]

            for platform_name in ordered_platforms:
                plat_picks = [p for p in analyzed_props if p["platform"] == platform_name]
                if not plat_picks:
                    continue

                plat_lower = platform_name.lower()
                if "prize" in plat_lower:
                    icon = "🟢"
                    badge_color = "#00c853"
                elif "draft" in plat_lower:
                    icon = "🔵"
                    badge_color = "#2196f3"
                else:
                    icon = "🎰"
                    badge_color = "#607d8b"

                st.markdown(
                    f'<h3 style="color:{badge_color};margin-top:20px;">'
                    f'{icon} {platform_name} — {len(plat_picks)} Pick(s)</h3>',
                    unsafe_allow_html=True,
                )

                # Two-column grid of bet cards
                col_a, col_b = st.columns(2)
                for idx, pick in enumerate(plat_picks):
                    # Only show picks with positive edge
                    if pick["edge_percentage"] <= 0:
                        continue
                    col = col_a if idx % 2 == 0 else col_b
                    with col:
                        st.markdown(
                            get_bet_card_html(pick),
                            unsafe_allow_html=True,
                        )

    except Exception as _platform_err:
        pp_bar.empty()
        pp_status.empty()
        # Silently ignore WebSocket/stream errors caused by user navigating away
        # mid-load — these are not real failures, just closed connections.
        _err_str = str(_platform_err)
        if "WebSocketClosedError" in _err_str or "StreamClosedError" in _err_str:
            pass  # Connection closed — user navigated away; nothing to show
        else:
            try:
                st.error(
                    f"❌ Platform props pipeline failed: {_platform_err}\n\n"
                    "This is usually caused by a temporary data issue. "
                    "You can still use Auto-Load + Neural Analysis for model-generated props."
                )
            except Exception:
                pass  # Swallow any secondary UI error from closed WebSocket

# ============================================================
# END SECTION: Platform Props & Analyze Button
# ============================================================

# ============================================================
# SECTION: One-Click Setup (Auto-Load + Get Live Props combined)
# ============================================================

if one_click_setup_clicked:
    st.divider()
    st.subheader("⚡ One-Click Setup")
    st.markdown("Running **Auto-Load** + **Get Live Props** in one step…")
    _oc_bar = st.progress(0)
    _oc_status = st.empty()

    try:
        # ── Phase 1: Auto-Load Tonight's Games ────────────────────────
        _oc_status.text("⏳ Phase 1/3 — Auto-loading tonight's games, rosters & stats…")
        _oc_bar.progress(5)
        from data.nba_data_service import (
            get_todays_games as _oc_get_games,
            get_todays_players as _oc_get_players,
            get_team_stats as _oc_get_teams,
            get_standings as _oc_get_standings,
        )
        from data.data_manager import (
            load_players_data as _oc_load_players,
            save_props_to_session as _oc_save_props,
            clear_all_caches as _oc_clear_caches,
            load_injury_status as _oc_load_inj,
        )

        _oc_games = _oc_get_games()
        if _oc_games:
            st.session_state["todays_games"] = _oc_games
        else:
            _oc_games = st.session_state.get("todays_games", [])

        _oc_bar.progress(25)
        _oc_status.text(f"⏳ Phase 1/3 — {len(_oc_games)} game(s) loaded. Loading player data…")

        _oc_players_ok = _oc_get_players(_oc_games) if _oc_games else False
        _oc_bar.progress(40)

        # Clear caches so freshly-written players.csv is read
        _oc_clear_caches()

        try:
            st.session_state["injury_status_map"] = _oc_load_inj()
        except Exception:
            pass

        # ── Phase 2: Load team stats & standings ─────────────────────
        _oc_status.text("⏳ Phase 2/3 — Loading team stats & standings…")
        _oc_bar.progress(50)

        try:
            _oc_get_teams()
        except Exception as _oc_ts_err:
            _logger.debug(f"One-Click: team stats load failed (non-fatal): {_oc_ts_err}")

        try:
            _oc_standings = _oc_get_standings()
            if _oc_standings:
                st.session_state["league_standings"] = _oc_standings
        except Exception as _oc_st_err:
            _logger.debug(f"One-Click: standings pre-load skipped: {_oc_st_err}")

        _oc_bar.progress(60)

        # ── Phase 3: Get Live Platform Props ────────────────────────
        _oc_status.text("⏳ Phase 3/3 — Retrieving live prop lines from all platforms…")

        try:
            from data.sportsbook_service import get_all_sportsbook_props as _oc_get_sportsbook_props
            from data.data_manager import (
                save_platform_props_to_session as _oc_save_platform,
                save_platform_props_to_csv as _oc_save_csv,
            )
            _oc_odds_key = st.session_state.get("odds_api_key") or ""
            _oc_platform_props = _oc_get_sportsbook_props(odds_api_key=_oc_odds_key or None)
            _oc_bar.progress(85)
            if _oc_platform_props:
                _oc_save_props(_oc_platform_props, st.session_state)
                _oc_save_platform(_oc_platform_props, st.session_state)
                try:
                    _oc_save_csv(_oc_platform_props)
                except Exception:
                    pass
                _oc_platform_msg = f"✅ {len(_oc_platform_props)} live props retrieved"
            else:
                _oc_platform_msg = "⚠️ No live platform props returned (data may be unavailable)"
        except Exception as _oc_plat_err:
            _oc_platform_msg = f"⚠️ Platform retrieval failed: {_oc_plat_err}"

        _oc_bar.progress(100)
        _oc_status.empty()
        _oc_bar.empty()

        _oc_total_props = len(st.session_state.get("current_props", []))
        st.success(
            f"✅ **One-Click Setup complete!** "
            f"Games: {'✅ ' + str(len(_oc_games)) if _oc_games else '⚠️ none'} | "
            f"Players: {'✅' if _oc_players_ok else '⚠️ check data'} | "
            f"Props: {_oc_platform_msg} | "
            f"Total props loaded: **{_oc_total_props}**\n\n"
            "👉 Go to **⚡ Neural Analysis** and click **Run Analysis** to analyze all loaded props."
        )
        time.sleep(1)
        st.rerun()

    except Exception as _oc_err:
        _oc_bar.empty()
        _oc_status.empty()
        _oc_err_str = str(_oc_err)
        if "WebSocketClosedError" in _oc_err_str or "StreamClosedError" in _oc_err_str:
            pass  # Connection closed — user navigated away
        else:
            st.error(f"❌ One-Click Setup failed: {_oc_err}")

# ============================================================
# END SECTION: One-Click Setup
# ============================================================

st.divider()

st.markdown(get_education_box_html(
    "📖 Understanding NBA Game Context",
    """
    <strong>Spread</strong>: The Vegas point spread. A spread of +5 means the home team is expected to win by 5 points. 
    Useful for estimating blowout risk — in a blowout, stars often sit the 4th quarter.<br><br>
    <strong>Game Total (O/U)</strong>: The Vegas over/under for combined score of both teams. 
    A high total (e.g., 230+) means Vegas expects a fast-paced, high-scoring game, boosting all players' stat projections.<br><br>
    <strong>Why it matters</strong>: These numbers adjust our AI projections — a high total gives players +5-8% stat boost, 
    while a large spread increases blowout risk and reduces projected minutes for stars.
    """
), unsafe_allow_html=True)

# ============================================================
# SECTION: Display Current Games as Rich Cards
# ============================================================

def _enrich_games_with_standings(games, standings):
    """Merge conference/rank/last_10 from standings into game dicts."""
    if not standings:
        return
    lookup = {}
    for s in standings:
        abbr = s.get("team_abbreviation", "")
        if abbr:
            lookup[abbr] = s
    for g in games:
        home_s = lookup.get(g.get("home_team", ""), {})
        away_s = lookup.get(g.get("away_team", ""), {})
        g.setdefault("home_conference_rank", home_s.get("conference_rank", 0))
        g.setdefault("home_conference", home_s.get("conference", ""))
        g.setdefault("home_last_10", home_s.get("last_10", ""))
        g.setdefault("away_conference_rank", away_s.get("conference_rank", 0))
        g.setdefault("away_conference", away_s.get("conference", ""))
        g.setdefault("away_last_10", away_s.get("last_10", ""))
        # Backfill basic records when the original fetch returned zeros
        if not g.get("home_wins") and home_s.get("wins"):
            g["home_wins"] = home_s["wins"]
            g["home_losses"] = home_s.get("losses", 0)
        if not g.get("away_wins") and away_s.get("wins"):
            g["away_wins"] = away_s["wins"]
            g["away_losses"] = away_s.get("losses", 0)

current_games = st.session_state.get("todays_games", [])
players_data = load_players_data()

# Enrich games with standings data (conference rank, conference, last 10)
_standings_for_enrich = st.session_state.get("league_standings", [])
if current_games and _standings_for_enrich:
    _enrich_games_with_standings(current_games, _standings_for_enrich)

if current_games:
    st.subheader(f"🏟️ Tonight's Slate — {len(current_games)} Game(s)")

    # ── ESPN-style Score Ticker at top (Enhancement #4) ──────────
    _ticker_cards: list[str] = []
    for _tg in current_games:
        _t_away = _h.escape(str(_tg.get("away_team", "?")))
        _t_home = _h.escape(str(_tg.get("home_team", "?")))
        _aw = _tg.get("away_wins", 0)
        _al = _tg.get("away_losses", 0)
        _hw = _tg.get("home_wins", 0)
        _hl = _tg.get("home_losses", 0)
        _gt = _tg.get("game_time_et", "")
        _status_lbl = _h.escape(str(_gt)) if _gt else "SCHEDULED"
        _ticker_cards.append(
            f'<div class="espn-game-card">'
            f'<div class="espn-game-status espn-status-sched">{_status_lbl}</div>'
            f'<div class="espn-team-row">'
            f'<span class="espn-team-abbr">{_t_away}</span>'
            f'<span class="espn-team-score espn-team-winning">({_aw}-{_al})</span></div>'
            f'<div class="espn-team-row">'
            f'<span class="espn-team-abbr">{_t_home}</span>'
            f'<span class="espn-team-score espn-team-winning">({_hw}-{_hl})</span></div>'
            f'</div>'
        )

    _ticker_cards_html = ''.join(_ticker_cards)
    _n_ticker = len(current_games)
    _scroll_dur = max(15, _n_ticker * 5)

    if _n_ticker >= 3:
        _ticker_inner = (
            f'<div class="espn-ticker-scroll" '
            f'style="--scroll-duration:{_scroll_dur}s;">'
            f'{_ticker_cards_html}{_ticker_cards_html}</div>'
        )
    else:
        _ticker_inner = f'<div class="espn-ticker-track">{_ticker_cards_html}</div>'

    _ticker_header = f"🏀 TONIGHT'S SLATE — {datetime.date.today().strftime('%b %d, %Y')}"
    st.markdown(
        f'<div class="espn-ticker-container">'
        f'<div class="espn-ticker-header">{_ticker_header}</div>'
        f'<div class="espn-ticker-track">{_ticker_inner}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Quick-Filter / Sort Bar (Enhancement #9) ──────────────────
    _sort_col, _filter_col = st.columns([1, 2])
    with _sort_col:
        _sort_option = st.selectbox(
            "Sort by",
            ["Default (API order)", "Time", "Spread (closest)", "Total (highest)", "Total (lowest)"],
            key="lg_sort_option",
        )
    with _filter_col:
        _filter_options = st.multiselect(
            "Filter",
            ["Show only games with injuries", "Show only primetime (after 7 PM ET)"],
            key="lg_filter_options",
            default=[],
        )

    # Apply sorting
    _display_games = list(current_games)
    if _sort_option == "Spread (closest)":
        _display_games.sort(key=lambda g: abs(float(g.get("vegas_spread") or 0)))
    elif _sort_option == "Total (highest)":
        _display_games.sort(key=lambda g: float(g.get("game_total") or 220), reverse=True)
    elif _sort_option == "Total (lowest)":
        _display_games.sort(key=lambda g: float(g.get("game_total") or 220))
    elif _sort_option == "Time":
        _display_games.sort(key=lambda g: str(g.get("game_time_et") or ""))

    # Apply filters
    _inj_map_filter = st.session_state.get("injury_status_map", {})
    _inj_statuses_filter = {"Out", "Doubtful", "Injured Reserve", "Game Time Decision"}
    if "Show only games with injuries" in _filter_options:
        def _has_injuries(g):
            for _t in [g.get("home_team", ""), g.get("away_team", "")]:
                for _p in find_players_by_team(players_data, _t)[:10]:
                    if _inj_map_filter.get(_p.get("name", ""), {}).get("status", "Active") in _inj_statuses_filter:
                        return True
            return False
        _display_games = [g for g in _display_games if _has_injuries(g)]

    if "Show only primetime (after 7 PM ET)" in _filter_options:
        def _is_primetime(g):
            gt = str(g.get("game_time_et") or "")
            # Check for times like "7:00 PM", "8:30 PM" etc.
            if "PM" in gt.upper():
                try:
                    hour = int(gt.split(":")[0].strip())
                    return hour >= 7 and hour != 12
                except (ValueError, IndexError):
                    pass
            return False
        _display_games = [g for g in _display_games if _is_primetime(g)]

    for game in _display_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_name = game.get("home_team_name", home)
        away_name = game.get("away_team_name", away)

        home_w = game.get("home_wins", 0)
        home_l = game.get("home_losses", 0)
        away_w = game.get("away_wins", 0)
        away_l = game.get("away_losses", 0)

        home_streak = game.get("home_streak") or ""
        away_streak = game.get("away_streak") or ""

        # Extended standings fields (populated by _enrich_games_with_standings)
        home_rank   = game.get("home_conference_rank", 0)
        home_conf   = (game.get("home_conference") or "")[:1].upper()
        home_l10    = game.get("home_last_10") or ""
        away_rank   = game.get("away_conference_rank", 0)
        away_conf   = (game.get("away_conference") or "")[:1].upper()
        away_l10    = game.get("away_last_10") or ""

        def _conf_badge(rank, conf):
            if rank and conf:
                return f'<span style="color:#6B7A9A;font-size:0.75rem;">#{rank} {conf}</span>'
            return ""

        def _l10_badge(l10):
            if l10:
                return f'<span style="color:#718096;font-size:0.75rem;">L10: {l10}</span>'
            return ""

        game_time = game.get("game_time_et", "")
        arena = game.get("arena", "")
        try:
            _spread_raw = game.get("vegas_spread")
            spread = float(_spread_raw) if _spread_raw is not None else 0.0
        except (TypeError, ValueError):
            spread = 0.0
        try:
            _total_raw = game.get("game_total")
            total = float(_total_raw) if _total_raw is not None else 220.0
        except (TypeError, ValueError):
            total = 220.0

        # Format streak with color class
        def streak_html(s):
            if not s:
                return ""
            if s.startswith("W"):
                return f'<span class="streak-hot">🔥 {s} streak</span>'
            elif s.startswith("L"):
                return f'<span class="streak-cold">❄️ {s} streak</span>'
            return f'<span class="streak-neutral">{s}</span>'

        # Top 2 players for each team
        home_players = find_players_by_team(players_data, home)[:2]
        away_players = find_players_by_team(players_data, away)[:2]

        # Enhancement #10: Inline injury badges on player names
        def player_line_with_injuries(players):
            if not players:
                return "<em style='color:#718096'>No data loaded</em>"
            parts = []
            for p in players:
                name_parts = p.get("name", "").split()
                short_name = f"{name_parts[0][0]}. {' '.join(name_parts[1:])}" if len(name_parts) > 1 else p.get("name", "")
                pts = _h.escape(str(p.get("points_avg", "—")))
                inj_status = _inj_map_filter.get(p.get("name", ""), {}).get("status", "Active")
                inj_badge = ""
                if inj_status in {"Out", "Injured Reserve"}:
                    inj_badge = '<span class="injury-badge-out">OUT</span>'
                elif inj_status in {"Doubtful", "Game Time Decision"}:
                    inj_badge = '<span class="injury-badge-gtd">GTD</span>'
                parts.append(f"<span class='player-stat'>{_h.escape(short_name)} ({pts} PPG){inj_badge}</span>")
            return " &nbsp;|&nbsp; ".join(parts)

        # Spread display
        if spread > 0:
            spread_text = f"{home} -{spread}"
        elif spread < 0:
            spread_text = f"{away} -{abs(spread)}"
        else:
            spread_text = "Pick'em"

        # Moneyline / consensus display from Odds API
        ml_home_raw = game.get("moneyline_home")
        ml_away_raw = game.get("moneyline_away")
        bk_count     = game.get("bookmaker_count", 0)
        cons_spread  = game.get("consensus_spread")

        def _fmt_ml(ml):
            if ml is None:
                return "—"
            ml_val = round(float(ml))
            return f"+{ml_val}" if ml_val > 0 else str(ml_val)

        ml_home_str = _fmt_ml(ml_home_raw)
        ml_away_str = _fmt_ml(ml_away_raw)
        has_odds_data = bk_count > 0

        # Build game meta line
        meta_parts = []
        if game_time:
            meta_parts.append(f"🕐 {game_time}")
        if arena:
            meta_parts.append(f"📍 {arena}")
        meta_line = " &nbsp;•&nbsp; ".join(meta_parts) if meta_parts else ""

        # Lines info
        lines_parts = []
        if spread != 0:
            lines_parts.append(f"Spread: {spread_text}")
        lines_parts.append(f"O/U: {total}")
        lines_line = " &nbsp;|&nbsp; ".join(lines_parts)

        # Moneyline info (only shown when Odds API has data)
        ml_line = ""
        if has_odds_data:
            bk_note = f" <span style='color:#718096;font-size:0.75rem;'>({bk_count} books)</span>"
            ml_line = (
                f'<div class="game-meta" style="margin-top:4px;">'
                f'💰 ML: <strong>{_h.escape(away)} {ml_away_str}</strong> &nbsp;|&nbsp; '
                f'<strong>{_h.escape(home)} {ml_home_str}</strong>'
                f'{bk_note}</div>'
            )

        # ── Team colors & logos (Enhancement #1, #3) ──────────────
        away_color, _ = get_team_colors(away)
        home_color, _ = get_team_colors(home)
        away_logo_url = _h.escape(f"{ESPN_LOGO_BASE_URL}/{away.lower()}.png")
        home_logo_url = _h.escape(f"{ESPN_LOGO_BASE_URL}/{home.lower()}.png")
        _logo_onerror = f"onerror=\"this.src='{_h.escape(NBA_LOGO_FALLBACK_URL)}'\""

        _BADGE_FALLBACK_RGB = (0, 240, 255)  # cyan fallback

        def _hex_to_rgb(hex_color):
            """Convert '#RRGGBB' hex to (r, g, b) tuple, with fallback."""
            try:
                if len(hex_color) >= 7:
                    return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            except (ValueError, IndexError, TypeError):
                pass
            return _BADGE_FALLBACK_RGB

        def _team_badge_html(abbrev, color, logo_url, is_home=False):
            r, g, b = _hex_to_rgb(color)
            safe_color = _h.escape(color) if color else "#00D559"
            return (
                f'<span class="team-badge" style="background:rgba({r},{g},{b},0.18);'
                f'border:1px solid {safe_color}40;">'
                f'<img class="team-logo" src="{logo_url}" alt="{_h.escape(abbrev)}" {_logo_onerror}>'
                f'{_h.escape(abbrev)}</span>'
            )

        # Render card — Enhancement #2: Side-by-side scoreboard layout
        _expander_label = f"🏀  {away} ({away_w}-{away_l}) @ {home} ({home_w}-{home_l})  •  {lines_line.replace('&nbsp;', ' ')}"
        with st.expander(_expander_label, expanded=True):
            card_html = (
                '<div class="game-card">'
                '<div class="scoreboard-row">'
                # Away team (left-aligned when wide, centered when wrapped)
                '<div class="scoreboard-team away">'
                f'<div style="display:flex;align-items:center;gap:8px;justify-content:flex-end;flex-wrap:wrap;">'
                f'{_team_badge_html(away, away_color, away_logo_url)}'
                f'<span style="color:#a0aec0;font-size:0.95rem;">{_h.escape(away_name)}</span>'
                f'<span style="color:#718096;font-size:0.85rem;">({away_w}-{away_l})</span>'
                f'{_conf_badge(away_rank, away_conf)}'
                f'{streak_html(away_streak)}'
                f'{_l10_badge(away_l10)}'
                '</div></div>'
                # Center "@" divider
                '<div class="scoreboard-at">@</div>'
                # Home team (right side)
                '<div class="scoreboard-team home">'
                f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
                f'{_team_badge_html(home, home_color, home_logo_url, is_home=True)}'
                f'<span style="color:#a0aec0;font-size:0.95rem;">{_h.escape(home_name)}</span>'
                f'<span style="color:#718096;font-size:0.85rem;">({home_w}-{home_l})</span>'
                f'{_conf_badge(home_rank, home_conf)}'
                f'{streak_html(home_streak)}'
                f'{_l10_badge(home_l10)}'
                '</div></div>'
                '</div>'  # end scoreboard-row
                + (f'<div class="game-meta" style="text-align:center;margin-top:6px;">{meta_line}</div>' if meta_line else '')
                + f'<div class="game-meta" style="text-align:center;margin-top:4px;">📊 {lines_line}</div>'
                + ml_line
                # Enhancement #10: Key players with inline injury badges
                + '<div class="key-players">'
                '<div class="key-players-title">Key Players</div>'
                '<div style="margin-top:6px; display:flex; gap:20px; flex-wrap:wrap;">'
                f'<div><span style="color:{away_color}; font-weight:600;">{_h.escape(away)}:</span> {player_line_with_injuries(away_players)}</div>'
                f'<div><span style="color:{home_color}; font-weight:600;">{_h.escape(home)}:</span> {player_line_with_injuries(home_players)}</div>'
                '</div></div></div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

            # ── Game Environment Card (Enhancement #5: Game Attractiveness) ──
            _pace_adj = "Fast 🚀" if total > 230 else ("Slow 🐢" if total < 210 else "Normal ⚖️")
            _blowout_risk = abs(spread)
            _blowout_lbl = "Low" if _blowout_risk < 5 else ("Medium" if _blowout_risk < 10 else "HIGH ⚠️")
            _blowout_clr = "#00D559" if _blowout_risk < 5 else ("#F9C62B" if _blowout_risk < 10 else "#F24336")
            _o_u_lbl = "OVER-Friendly 📈" if total > 225 else ("UNDER-Friendly 📉" if total < 210 else "Neutral")
            _o_u_clr = "#00D559" if total > 225 else ("#8b949e" if total < 210 else "#EEF0F6")

            # Enhancement #5: Game Attractiveness composite score
            _attract_score = 0
            if total > 225:
                _attract_score += 2
            elif total > 215:
                _attract_score += 1
            if _blowout_risk < 5:
                _attract_score += 2
            elif _blowout_risk < 8:
                _attract_score += 1

            # Injury impact
            _inj_map = st.session_state.get("injury_status_map", {})
            _inj_statuses = {"Out", "Doubtful", "Injured Reserve"}
            _home_out = [
                p.get("name", "?")
                for p in find_players_by_team(players_data, home)[:10]
                if _inj_map.get(p.get("name", ""), {}).get("status", "Active") in _inj_statuses
            ]
            _away_out = [
                p.get("name", "?")
                for p in find_players_by_team(players_data, away)[:10]
                if _inj_map.get(p.get("name", ""), {}).get("status", "Active") in _inj_statuses
            ]

            if not _home_out and not _away_out:
                _attract_score += 1  # No major injuries = more predictable

            if _attract_score >= 4:
                _attract_lbl = '🟢 HIGH'
                _attract_cls = 'signal-high'
            elif _attract_score >= 2:
                _attract_lbl = '🟡 MEDIUM'
                _attract_cls = 'signal-medium'
            else:
                _attract_lbl = '🔴 LOW'
                _attract_cls = 'signal-low'

            def _format_injury_text(team_abbrev, out_players):
                if not out_players:
                    return ""
                escaped = ", ".join(_h.escape(n) for n in out_players[:3])
                return f'<span style="color:#F24336;">🏥 {_h.escape(team_abbrev)}: {escaped}</span>'

            _inj_txt_parts = []
            _home_inj_html = _format_injury_text(home, _home_out)
            _away_inj_html = _format_injury_text(away, _away_out)
            if _home_inj_html:
                _inj_txt_parts.append(_home_inj_html)
            if _away_inj_html:
                _inj_txt_parts.append(_away_inj_html)
            _inj_txt = "&nbsp;&nbsp;".join(_inj_txt_parts) if _inj_txt_parts else '<span style="color:#00D559;">✅ No major injuries reported</span>'

            # Bookmaker consensus row (only shown when Odds API data available)
            _bk_count = game.get("bookmaker_count", 0)
            _consensus_html = ""
            if _bk_count > 0:
                _cons_spread = game.get("consensus_spread")
                _cons_total  = game.get("consensus_total")
                _sr = game.get("spread_range", (None, None)) or (None, None)
                _tr = game.get("total_range", (None, None)) or (None, None)
                _cs_txt = f"{_cons_spread:+.1f}" if _cons_spread is not None else "—"
                _ct_txt = f"{_cons_total:.1f}" if _cons_total is not None else "—"
                _spread_rng_txt = (
                    f" ({_sr[0]:+.1f} to {_sr[1]:+.1f})" if _sr[0] is not None else ""
                )
                _total_rng_txt = (
                    f" ({_tr[0]:.1f} to {_tr[1]:.1f})" if _tr[0] is not None else ""
                )
                _consensus_html = (
                    f'<div style="margin-top:6px;font-size:0.8rem;">'
                    f'📚 <strong style="color:#6B7A9A;">Consensus ({_bk_count} books):</strong> '
                    f'Spread <strong style="color:#63b3ed;">{_cs_txt}{_spread_rng_txt}</strong>'
                    f' &nbsp;|&nbsp; '
                    f'O/U <strong style="color:#63b3ed;">{_ct_txt}{_total_rng_txt}</strong>'
                    f'</div>'
                )

            st.markdown(
                f'<div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:12px 16px;'
                f'margin:-4px 0 16px 0;border:1px solid rgba(0,213,89,0.09);">'
                f'<div style="font-size:0.78rem;color:#6B7A9A;font-weight:600;margin-bottom:8px;'
                f'letter-spacing:0.5px;">⚙️ GAME ENVIRONMENT'
                f'<span class="signal-badge {_attract_cls}">{_attract_lbl}</span></div>'
                f'<div style="display:flex;gap:20px;flex-wrap:wrap;font-size:0.82rem;">'
                f'<div><span style="color:#6B7A9A;">Pace:</span> '
                f'<strong style="color:#EEF0F6;">{_pace_adj}</strong></div>'
                f'<div><span style="color:#6B7A9A;">O/U {total}:</span> '
                f'<strong style="color:{_o_u_clr};">{_o_u_lbl}</strong></div>'
                f'<div><span style="color:#6B7A9A;">Blowout Risk:</span> '
                f'<strong style="color:{_blowout_clr};">{_blowout_lbl} ({_blowout_risk:.0f} pts)</strong></div>'
                f'</div>'
                f'{_consensus_html}'
                f'<div style="margin-top:8px;font-size:0.8rem;">🏥 <strong style="color:#6B7A9A;">Injury Impact:</strong> {_inj_txt}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Enhancement #12: Quick Analyze button ─────────────────────
            _game_id = game.get("game_id", f"{away}_vs_{home}")
            if st.button(f"⚡ Analyze {away} @ {home}", key=f"analyze_btn_{_game_id}"):
                st.session_state["quick_analyze_game"] = game
                try:
                    st.switch_page("pages/3_⚡_Quantum_Analysis_Matrix.py")
                except Exception:
                    st.info("Navigate to ⚡ Quantum Analysis Matrix to view this matchup.")
    with st.expander("✏️ Edit Spreads & Totals", expanded=False):
        st.markdown("Adjust Vegas lines for each game:")
        updated_games = []
        for i, game in enumerate(current_games):
            col_label, col_spread, col_total = st.columns([3, 2, 2])
            with col_label:
                st.markdown(f"**{game.get('away_team', '')} @ {game.get('home_team', '')}**")
            with col_spread:
                _spread_raw = game.get("vegas_spread")
                try:
                    _spread_val = float(_spread_raw) if _spread_raw is not None else 0.0
                except (TypeError, ValueError):
                    _spread_val = 0.0
                _spread_val = max(-30.0, min(30.0, _spread_val))
                new_spread = st.number_input(
                    "Spread (Home)",
                    min_value=-30.0, max_value=30.0,
                    value=_spread_val, step=0.5,
                    key=f"edit_spread_{i}",
                )
            with col_total:
                _total_raw = game.get("game_total")
                try:
                    _total_val = float(_total_raw) if _total_raw is not None else 220.0
                except (TypeError, ValueError):
                    _total_val = 220.0
                _total_val = max(180.0, min(270.0, _total_val))
                new_total = st.number_input(
                    "Total (O/U)",
                    min_value=180.0, max_value=270.0,
                    value=_total_val, step=0.5,
                    key=f"edit_total_{i}",
                )
            updated_game = dict(game)
            updated_game["vegas_spread"] = new_spread
            updated_game["game_total"] = new_total
            updated_games.append(updated_game)

        col_save, col_clear = st.columns([1, 1])
        with col_save:
            if st.button("💾 Save Changes", type="primary"):
                st.session_state["todays_games"] = updated_games
                st.success("✅ Lines updated!")
                st.rerun()
        with col_clear:
            if st.button("🗑️ Clear All Games"):
                st.session_state["todays_games"] = []
                st.rerun()

else:
    # Enhancement #8: Skeleton / shimmer loading cards
    st.markdown(
        '<div style="background:linear-gradient(135deg,rgba(255,94,0,0.12),rgba(45,158,255,0.08));'
        'border:1px solid rgba(255,94,0,0.35);border-radius:10px;padding:16px 24px;margin:8px 0 16px 0;">'
        '<div style="font-size:1.1rem;font-weight:700;color:#F9C62B;margin-bottom:6px;">'
        '🚫 No Games Loaded Tonight</div>'
        '<div style="color:#EEF0F6;">'
        'No NBA games have been loaded yet. Click <strong>⚡ One-Click Setup</strong> above to '
        'automatically load tonight\'s slate, player stats, injury reports, and props in one click.<br>'
        '<span style="color:#8b949e;font-size:0.85rem;">Or expand <strong>⚙️ Advanced Options</strong> '
        'to manually add games.</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Shimmer skeleton placeholders
    _skeleton_html = ""
    for _ in range(3):
        _skeleton_html += (
            '<div class="skeleton-card">'
            '<div class="skeleton-line wide"></div>'
            '<div class="skeleton-line medium"></div>'
            '<div class="skeleton-line narrow"></div>'
            '<div style="height:8px;"></div>'
            '<div class="skeleton-line wide"></div>'
            '<div class="skeleton-line narrow"></div>'
            '</div>'
        )
    st.markdown(_skeleton_html, unsafe_allow_html=True)

st.divider()

# ============================================================
# SECTION: Manual Game Entry Form
# ============================================================

with st.expander("➕ Manually Add Games", expanded=not bool(current_games)):
    all_teams_data = load_teams_data()
    team_options = []
    for team in all_teams_data:
        abbreviation = team.get("abbreviation", "")
        full_name = team.get("team_name", "")
        if abbreviation and full_name:
            team_options.append(f"{abbreviation} — {full_name}")
    team_options.sort()

    with st.form("games_entry_form"):
        st.markdown("**How many games tonight?**")
        number_of_games = st.number_input(
            "Number of games",
            min_value=1, max_value=8, value=3, step=1,
        )
        st.divider()

        game_entries_from_form = []
        for game_index in range(int(number_of_games)):
            st.markdown(f"**Game {game_index + 1}**")
            col_home, col_away, col_lines = st.columns([2, 2, 3])

            with col_home:
                home_team_selection = st.selectbox(
                    "Home Team",
                    options=["— Select —"] + team_options,
                    key=f"home_team_{game_index}",
                )
            with col_away:
                away_team_selection = st.selectbox(
                    "Away Team",
                    options=["— Select —"] + team_options,
                    key=f"away_team_{game_index}",
                )
            with col_lines:
                col_spread, col_total = st.columns(2)
                with col_spread:
                    vegas_spread = st.number_input(
                        "Spread (Home)",
                        min_value=-30.0, max_value=30.0,
                        value=0.0, step=0.5,
                        key=f"spread_{game_index}",
                    )
                with col_total:
                    game_total = st.number_input(
                        "Total (O/U)",
                        min_value=180.0, max_value=270.0,
                        value=220.0, step=0.5,
                        key=f"total_{game_index}",
                    )

            game_entries_from_form.append({
                "game_index": game_index,
                "home_team_selection": home_team_selection,
                "away_team_selection": away_team_selection,
                "vegas_spread": vegas_spread,
                "game_total": game_total,
            })

            if game_index < int(number_of_games) - 1:
                st.markdown("---")

        submit_games_button = st.form_submit_button(
            "✅ Save Tonight's Games",
            width="stretch",
            type="primary",
        )

    if submit_games_button:
        valid_games = []
        validation_warnings = []

        for entry in game_entries_from_form:
            home = entry["home_team_selection"]
            away = entry["away_team_selection"]

            if home == "— Select —" or away == "— Select —":
                continue
            if home == away:
                validation_warnings.append(
                    f"Game {entry['game_index'] + 1}: Home and away team are the same!"
                )
                continue

            home_abbrev = home.split(" — ")[0]
            away_abbrev = away.split(" — ")[0]

            clean_game = {
                "game_id": f"{home_abbrev}_vs_{away_abbrev}",
                "home_team": home_abbrev,
                "away_team": away_abbrev,
                "home_team_full": home,
                "away_team_full": away,
                "home_team_name": home.split(" — ")[1] if " — " in home else home,
                "away_team_name": away.split(" — ")[1] if " — " in away else away,
                "vegas_spread": float(entry["vegas_spread"]),
                "game_total": float(entry["game_total"]),
                "game_date": datetime.date.today().isoformat(),
                "home_wins": 0, "home_losses": 0, "home_streak": "",
                "away_wins": 0, "away_losses": 0, "away_streak": "",
            }
            valid_games.append(clean_game)

        for warning in validation_warnings:
            st.warning(f"⚠️ {warning}")

        if valid_games:
            existing = st.session_state.get("todays_games", [])
            combined = existing + valid_games
            st.session_state["todays_games"] = combined
            st.success(f"✅ Added {len(valid_games)} game(s)!")
            st.rerun()
        else:
            st.error("No valid games entered. Please select home and away teams.")

# ============================================================
# SECTION: Tips
# ============================================================

with st.expander("💡 Tips for Best Results"):
    st.markdown("""
    - **Vegas Spread:** Positive = home favored, negative = away favored.
      E.g., +5.5 means the home team is favored by 5.5 points.

    - **Total (O/U):** The Vegas over/under for the game (usually 210–235).

    - **Auto-Load**: Retrieves live game data + team records (W-L, streaks, standings),
      then enriches with consensus lines from multiple bookmakers.

    - **Key Players**: Loaded from your player database. Go to **Update Data** to
      refresh with today's team rosters.
    """)
