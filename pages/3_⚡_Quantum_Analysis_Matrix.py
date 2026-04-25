# ============================================================
# FILE: pages/3_⚡_Quantum_Analysis_Matrix.py
# PURPOSE: The main analysis page. Runs Quantum Matrix Engine 5.6 simulation
#          for each prop and shows probability, edge, tier, and
#          directional forces in the Quantum Design System (QDS) UI.
# CONNECTS TO: engine/ (all modules), data_manager.py, session state
# ============================================================

import streamlit as st  # Main UI framework
import math             # For rounding in display
import html as _html   # For safe HTML escaping in inline cards
import datetime         # For analysis result freshness timestamps
import time             # For elapsed-time measurement
import os               # For logo path resolution
import hashlib          # For content-hash caching of simulation results
import concurrent.futures  # For parallel prop analysis

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# Import our engine modules
from engine.simulation import (
    run_quantum_matrix_simulation,
    build_histogram_from_results,
    simulate_combo_stat,
    simulate_fantasy_score,
    simulate_double_double,
    simulate_triple_double,
    generate_alt_line_probabilities,
)
from engine import COMBO_STAT_TYPES, FANTASY_STAT_TYPES, YESNO_STAT_TYPES, is_unbettable_line
from engine.projections import build_player_projection, get_stat_standard_deviation, calculate_teammate_out_boost, POSITION_PRIORS
from engine.edge_detection import analyze_directional_forces, should_avoid_prop, detect_correlated_props, detect_trap_line, detect_line_sharpness, classify_bet_type, calculate_composite_win_score

# ── Lazy-loaded optional engine modules ──────────────────────────────────────
# These are imported on first use rather than at module level to reduce the
# initial import chain when navigating to this page.  Each helper returns the
# callable (or None) and caches the result in a module-level variable.

_rotation_tracker_available = None  # sentinel; resolved on first call
track_minutes_trend = None          # lazy-loaded
def _get_track_minutes_trend():
    global _rotation_tracker_available, track_minutes_trend
    if _rotation_tracker_available is None:
        try:
            from engine.rotation_tracker import track_minutes_trend as _fn
            _rotation_tracker_available = _fn
            track_minutes_trend = _fn
        except ImportError:
            _rotation_tracker_available = False
    return _rotation_tracker_available if _rotation_tracker_available else None
from engine.confidence import calculate_confidence_score, get_tier_color
from engine.math_helpers import calculate_edge_percentage, clamp_probability
from engine.explainer import generate_pick_explanation
from engine.odds_engine import american_odds_to_implied_probability as _odds_to_implied_prob
from engine.calibration import get_calibration_adjustment   # C10: historical calibration
from engine.clv_tracker import store_opening_line, get_stat_type_clv_penalties  # C12: CLV + penalties

detect_line_movement = None  # lazy-loaded on first use
def _get_detect_line_movement():
    global detect_line_movement
    if detect_line_movement is None:
        try:
            from engine.market_movement import detect_line_movement as _fn
            detect_line_movement = _fn
        except ImportError:
            detect_line_movement = False
    return detect_line_movement if detect_line_movement else None

calculate_matchup_adjustment = None  # lazy-loaded
get_matchup_force_signal = None      # lazy-loaded
def _get_matchup_fns():
    global calculate_matchup_adjustment, get_matchup_force_signal
    if calculate_matchup_adjustment is None:
        try:
            from engine.matchup_history import (
                calculate_matchup_adjustment as _adj,
                get_matchup_force_signal as _sig,
            )
            calculate_matchup_adjustment = _adj
            get_matchup_force_signal = _sig
        except ImportError:
            calculate_matchup_adjustment = False
            get_matchup_force_signal = False
    return (
        calculate_matchup_adjustment if calculate_matchup_adjustment else None,
        get_matchup_force_signal if get_matchup_force_signal else None,
    )

get_ensemble_projection = None  # lazy-loaded
_ensemble_available = None      # sentinel; resolved on first call
def _get_ensemble_projection():
    global get_ensemble_projection, _ensemble_available
    if _ensemble_available is None:
        try:
            from engine.ensemble import get_ensemble_projection as _fn
            get_ensemble_projection = _fn
            _ensemble_available = True
        except ImportError:
            _ensemble_available = False
            get_ensemble_projection = False
    return get_ensemble_projection if get_ensemble_projection else None

simulate_game_script = None          # lazy-loaded
blend_with_flat_simulation = None    # lazy-loaded
_game_script_available = None        # sentinel
def _get_game_script_fns():
    global simulate_game_script, blend_with_flat_simulation, _game_script_available
    if _game_script_available is None:
        try:
            from engine.game_script import (
                simulate_game_script as _sim,
                blend_with_flat_simulation as _blend,
            )
            simulate_game_script = _sim
            blend_with_flat_simulation = _blend
            _game_script_available = True
        except ImportError:
            _game_script_available = False
            simulate_game_script = False
            blend_with_flat_simulation = False
    return (
        simulate_game_script if simulate_game_script else None,
        blend_with_flat_simulation if blend_with_flat_simulation else None,
    )

project_player_minutes = None    # lazy-loaded
_minutes_model_available = None  # sentinel
def _get_project_player_minutes():
    global project_player_minutes, _minutes_model_available
    if _minutes_model_available is None:
        try:
            from engine.minutes_model import project_player_minutes as _fn
            project_player_minutes = _fn
            _minutes_model_available = True
        except ImportError:
            _minutes_model_available = False
            project_player_minutes = False
    return project_player_minutes if project_player_minutes else None

# Import data loading functions
from data.data_manager import (
    load_players_data,
    load_defensive_ratings_data,
    load_teams_data,
    find_player_by_name,
    load_props_from_session,
    get_roster_health_report,
    validate_props_against_roster,
    get_player_status,
    get_status_badge_html,
    load_injury_status,
)

# Import the theme helpers — including new QDS generators
from styles.theme import (
    get_global_css,
    get_logo_img_tag,
    get_roster_health_html,
    get_best_bets_section_html,
    get_qds_css,
    get_qds_metrics_grid_html,
    get_qds_prop_card_html,
    get_qds_matchup_header_html,
    get_qds_team_card_html,
    get_qds_strategy_table_html,
    get_qds_framework_logic_html,
    get_qds_final_verdict_html,
    get_education_box_html,
    GLOSSARY,
)

from data.platform_mappings import COMBO_STATS, FANTASY_SCORING

from utils.renderers import compile_card_matrix as _compile_card_matrix
from utils.renderers import build_horizontal_card_html as _build_h_card
from utils.player_card_renderer import compile_player_card_matrix as _compile_player_cards
from utils.player_card_renderer import compile_player_cards_flat as _compile_cards_flat
from styles.theme import get_quantum_card_matrix_css as _get_qcm_css

# ── Glassmorphic Trading-Card imports ────────────────────────────────────────
from styles.theme import get_glassmorphic_card_css as _get_gm_css
from styles.theme import get_player_trading_card_html as _get_trading_card_html
from utils.data_grouper import group_props_by_player as _group_props
from utils.player_modal import show_player_spotlight as _show_spotlight

# ── Section logo paths ────────────────────────────────────────────────────────
# Logos are stored in assets/ and loaded via st.image() for efficient serving.
_ASSETS_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
# Legacy logo paths disabled – branding removed from UI
_GOLD_LOGO_PATH   = os.path.join(_ASSETS_DIR, "NewGold_Logo.png")


# ── Change 10: Content-Hash Cache for Simulation Results ─────────────────────
# When a user re-runs analysis with the same prop pool, unchanged props return
# instantly from this session-state cache.  Only new/modified props are
# re-computed.  Cache is keyed on (player_name, stat_type, line, sim_depth).
def _prop_cache_key(player_name: str, stat_type: str, line: float,
                    sim_depth: int) -> str:
    """Return a deterministic hash key for a prop's simulation cache."""
    raw = f"{player_name.strip().lower()}|{stat_type.strip().lower()}|{line:.1f}|{sim_depth}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_sim_cache() -> dict:
    """Return the mutable simulation cache dict from session state."""
    if "_sim_result_cache" not in st.session_state:
        st.session_state["_sim_result_cache"] = {}
    return st.session_state["_sim_result_cache"]


# ── Card renderer ─────────────────────────────────────────────────────────────
# Renders the unified card matrix and parlays natively via st.html() (non-
# iframe rendering).  This ensures normal page scrolling on desktop — iframes
# with scrolling=False captured mouse-wheel events and blocked scroll.
#
# Native rendering via st.html():
#   1. Eliminates scroll-capture — content is part of the normal page flow.
#   2. Expanded <details> cards grow naturally without height constraints.
#   3. Player cards are never cut off regardless of how many are expanded.
# ---------------------------------------------------------------------------

_LAZY_CHUNK_SIZE = 50          # players per st.html() call — larger chunks = fewer DOM injections
_MAX_BIO_PREFETCH_WORKERS = 8  # max threads for parallel bio pre-fetching
_MAX_TOP_PICKS = 3             # max props flagged as "Top Pick" in the summary bar
_MAX_UNCERTAIN_NAMES = 6       # max player names shown in the uncertain-picks banner

# Injury status confidence penalties (points deducted from SAFE Score)
_DOUBTFUL_INJURY_PENALTY = 8.0      # Doubtful: ~75% chance of sitting
_QUESTIONABLE_INJURY_PENALTY = 4.0  # Questionable/GTD: uncertain availability

# Tier → emoji mapping used in incremental rendering feedback
_TIER_EMOJI = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}


def _render_card_native(card_html):
    """Render *card_html* natively via ``st.html()`` — no iframe.

    Uses Streamlit 1.55+ ``st.html()`` which renders content directly in
    the page DOM (not in an iframe).  This ensures:

    1. **Normal page scrolling** — no iframe capturing wheel events on
       desktop.  Previously, iframes with ``scrolling=False`` swallowed
       mouse-wheel events when the cursor was over the parlay or player
       card sections, forcing users to scroll from the side of the page.
    2. **No content cutoff** — expanded player cards grow naturally
       within the page flow; there is no fixed iframe height to exceed.
    3. **Dynamic accommodation** — when a ``<details>`` card is expanded,
       the surrounding container grows to fit the content, exactly as
       the user reported worked in a previous fix.

    CSS classes (``.qam-*``, ``.qcm-*``, ``.upc-*``) are uniquely
    prefixed to avoid conflicts with Streamlit's own styles.

    Parameters
    ----------
    card_html : str
        Complete HTML (including ``<style>`` blocks) returned by
        :func:`utils.renderers.compile_unified_card_matrix` or the
        parlay rendering functions.
    """
    st.html(card_html)


st.set_page_config(
    page_title="Neural Analysis — SmartBetPro NBA",
    page_icon="⚡",
    layout="wide",
)

# Inject global CSS + QDS CSS
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)
st.markdown(_get_gm_css(), unsafe_allow_html=True)

# ── Reduce excessive bottom padding / blank space ─────────────
# Also disable pull-to-refresh on mobile to prevent accidental reloads
# when scrolling through player bets.  The overscroll-behavior rule must
# cover EVERY scrollable ancestor Streamlit renders — not just html/body
# — because the actual scrolling container is a nested <div> (e.g.
# .main, [data-testid="stAppViewContainer"]).  Without this the mobile
# browser still triggers its native pull-to-refresh gesture and
# "restarts" the app mid-scroll.
st.markdown(
    '<style>'
    '.main .block-container{padding-bottom:1rem !important}'
    'html,body,.stApp,[data-testid="stAppViewContainer"],'
    'section[data-testid="stMain"],.main,.block-container'
    '{overscroll-behavior-y:contain !important;'
    '-webkit-overflow-scrolling:touch}'
    # ── Mobile: prevent accidental widget taps while scrolling ──
    # ``touch-action:manipulation`` disables double-tap-to-zoom and
    # fast-tap on interactive widgets, reducing the chance that a
    # scroll gesture accidentally triggers a Streamlit rerun.
    # ``min-height:48px`` meets mobile touch-target guidelines.
    # Applied to ALL interactive Streamlit widget containers.
    '[data-testid="stToggle"],'
    '[data-testid="stRadio"],'
    '[data-testid="stCheckbox"],'
    '[data-testid="stButton"],'
    '[data-testid="stSelectbox"],'
    '[data-testid="stMultiSelect"]'
    '{touch-action:manipulation;min-height:48px}'
    # ── During active scroll: disable pointer events on widgets ──
    # The JS scroll-guard adds ``.qam-scrolling`` to ``<body>`` while
    # the user is actively scrolling.  This prevents accidental taps
    # on Streamlit buttons/toggles that would trigger a full-page rerun.
    '.qam-scrolling [data-testid="stButton"] button,'
    '.qam-scrolling [data-testid="stToggle"] label,'
    '.qam-scrolling [data-testid="stRadio"] label,'
    '.qam-scrolling [data-testid="stCheckbox"] label,'
    '.qam-scrolling [data-testid="stSelectbox"] div[data-baseweb],'
    '.qam-scrolling [data-testid="stMultiSelect"] div[data-baseweb]'
    '{pointer-events:none !important}'
    # ── Ensure st.html() containers expand fully (no clipping) ──
    # Cards are now rendered natively via st.html(), so ensure the
    # wrapper elements don't impose height constraints.
    '[data-testid="stHtml"]'
    '{overflow:visible !important;max-height:none !important}'
    '[data-testid="stHtml"] > div'
    '{overflow:visible !important;max-height:none !important}'
    # ── Ensure expander content doesn't clip ──
    '.stExpander [data-testid="stExpanderDetails"]'
    '{overflow:visible !important;max-height:none !important}'
    '</style>',
    unsafe_allow_html=True,
)

# ── JavaScript: Scroll guard for widget pointer events ────────────────────────
# When the user is actively scrolling on mobile, this script adds a
# ``.qam-scrolling`` class to ``<body>`` which disables pointer-events on
# interactive Streamlit widgets (via the CSS above).  This prevents
# accidental taps during scroll that would trigger full-page reruns.
#
# Cards are no longer rendered in iframes (they use st.html() natively),
# so the iframe pointer-events guard is removed.
#
# The touchmove pull-to-refresh prevention uses {passive:true}
# with CSS overscroll-behavior instead of e.preventDefault().
st.markdown(
    """<script>
    (function(){
        if(window.__qamScrollGuard) return;
        window.__qamScrollGuard=true;
        var tid=0;
        function onScroll(){
            document.body.classList.add('qam-scrolling');
            clearTimeout(tid);
            tid=setTimeout(function(){
                document.body.classList.remove('qam-scrolling');
            },500);
        }
        /* Use the Streamlit main scroll container if available */
        var sc=document.querySelector('[data-testid="stAppViewContainer"]')||window;
        sc.addEventListener('scroll',onScroll,{passive:true});
        sc.addEventListener('touchmove',onScroll,{passive:true});
    })();
    </script>""",
    unsafe_allow_html=True,
)

# ── Global Settings Popover (accessible from sidebar) ─────────
from utils.components import render_global_settings, inject_joseph_floating, render_joseph_hero_banner
with st.sidebar:
    render_global_settings()
st.session_state.setdefault("joseph_page_context", "page_analysis")
inject_joseph_floating()
render_joseph_hero_banner()

# ── Premium Status (partial gate — free users capped at 3 props) ──
from utils.auth import is_premium_user as _is_premium_user
try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
except Exception:
    _PREM_PATH = "/14_%F0%9F%92%8E_Subscription_Level"
_FREE_ANALYSIS_LIMIT = 3   # Free users can analyze up to 3 props
_user_is_premium = _is_premium_user()
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "injury_status_map" not in st.session_state:
    try:
        st.session_state["injury_status_map"] = load_injury_status()
    except Exception:
        st.session_state["injury_status_map"] = {}

st.session_state.setdefault("joseph_enabled", True)
st.session_state.setdefault("joseph_used_fragments", set())
st.session_state.setdefault("joseph_bets_logged", False)

# ── Analysis Session Persistence — Rehydrate from DB if session empty ──────
# Session Bridge: checks st.query_params["sid"] first so that a page refresh
# or tab-switch recovers the EXACT run the user was viewing, not just the
# latest DB row.  Falls back to load_latest_analysis_session when no sid is
# present (e.g. first visit or bookmarked URL without params).
if not st.session_state.get("analysis_results"):
    try:
        from tracking.database import (
            load_latest_analysis_session as _load_session,
            load_analysis_session_by_id as _load_session_by_id,
        )
        _qam_sid_param = st.query_params.get("sid")
        if _qam_sid_param:
            _saved_session = _load_session_by_id(int(_qam_sid_param))
        else:
            _saved_session = _load_session()
        if _saved_session and _saved_session.get("analysis_results"):
            st.session_state["analysis_results"] = _saved_session["analysis_results"]
            if _saved_session.get("todays_games") and not st.session_state.get("todays_games"):
                st.session_state["todays_games"] = _saved_session["todays_games"]
            if _saved_session.get("selected_picks") and not st.session_state.get("selected_picks"):
                st.session_state["selected_picks"] = _saved_session["selected_picks"]
            # Record the timestamp so the UI can show when the session was saved
            st.session_state["_analysis_session_reloaded_at"] = _saved_session.get("analysis_timestamp", "")
            # Prevent the auto-run guard from re-triggering the engine when we
            # already have results from the DB.
            st.session_state["_qam_db_restored"] = True
    except Exception:
        pass  # Non-fatal — just show empty state

# ─── Restore todays_games independently if still missing ────────────────────
# The session bridge above only fires when analysis_results is absent.
# But the home page now seeds analysis_results from get_slate_picks_for_today()
# without also setting todays_games.  When the user navigates directly to QAM
# after the home-page slate seed, analysis_results is populated but
# todays_games is empty → all players fall into "Other" with no game headers.
# This block repairs that by loading games from the latest saved session
# whenever todays_games is missing, independently of analysis_results state.
if not st.session_state.get("todays_games"):
    try:
        from tracking.database import (
            load_latest_analysis_session as _load_session_for_games,
            load_analysis_session_by_id as _load_session_by_id_for_games,
        )
        _qam_sid_games = st.query_params.get("sid")
        if _qam_sid_games:
            _games_session = _load_session_by_id_for_games(int(_qam_sid_games))
        else:
            _games_session = _load_session_for_games()
        if _games_session and _games_session.get("todays_games"):
            st.session_state["todays_games"] = _games_session["todays_games"]
    except Exception:
        pass  # Non-fatal

# ─── Auto-refresh injury data if empty or stale (>4 hours) ──
# Use a 30-minute in-session cooldown to avoid re-loading on every
# page navigation, while still updating when data is genuinely stale.
# A short-circuit flag prevents redundant stat() calls on rapid
# reruns (e.g. scroll-triggered reruns that happen seconds apart).
_INJURY_STALE_HOURS = 4
_INJURY_REFRESH_COOLDOWN_SECS = 1800  # 30 minutes

# Short-circuit: if we already checked in this page load cycle
# (i.e. within the last 120 seconds), skip the entire block.
# This prevents repeated file-stat calls during rapid reruns
# (e.g. scroll-triggered reruns on mobile that happen seconds apart).
import time as _time_mod
_injury_check_ts = st.session_state.get("_injury_check_ts", 0)
_secs_since_check = _time_mod.time() - _injury_check_ts

if _secs_since_check < 120:
    _should_auto_refresh_injuries = False
else:
    # Record the check so subsequent rapid reruns (within 120s) skip it
    st.session_state["_injury_check_ts"] = _time_mod.time()
    if not st.session_state["injury_status_map"]:
        _should_auto_refresh_injuries = True
    else:
        _should_auto_refresh_injuries = False
        # Check if we already refreshed recently in this session
        _last_refresh_ts = st.session_state.get("_injury_last_refreshed_at")
        if _last_refresh_ts is not None:
            _mins_since = (_time_mod.time() - _last_refresh_ts) / 60
            if _mins_since < 30:
                _should_auto_refresh_injuries = False
            else:
                # Been 30+ minutes since last refresh — re-check file age
                try:
                    import datetime as _dt
                    from pathlib import Path as _Path
                    _inj_json_path = _Path(__file__).parent.parent / "data" / "injury_status.json"
                    if _inj_json_path.exists():
                        _inj_age_hours = (
                            _dt.datetime.now().timestamp() - _inj_json_path.stat().st_mtime
                        ) / 3600.0
                        _should_auto_refresh_injuries = _inj_age_hours > _INJURY_STALE_HOURS
                except Exception:
                    pass
        else:
            # No record of a refresh this session — check file age
            try:
                import datetime as _dt
                from pathlib import Path as _Path
                _inj_json_path = _Path(__file__).parent.parent / "data" / "injury_status.json"
                if _inj_json_path.exists():
                    _inj_age_hours = (
                        _dt.datetime.now().timestamp() - _inj_json_path.stat().st_mtime
                    ) / 3600.0
                    _should_auto_refresh_injuries = _inj_age_hours > _INJURY_STALE_HOURS
            except Exception:
                pass  # Staleness check is best-effort

if _should_auto_refresh_injuries:
    try:
        import time as _time_mod
        from data.roster_engine import RosterEngine as _RosterEngine
        _re = _RosterEngine()
        _re.refresh()
        _scraped_inj = _re.get_injury_report()
        if _scraped_inj:
            _auto_status_map = {
                _k: {
                    "status":        _v.get("status", "Active"),
                    "injury_note":   _v.get("injury", ""),
                    "games_missed":  0,
                    "return_date":   _v.get("return_date", ""),
                    "last_game_date": "",
                    "gp_ratio":      1.0,
                    "injury":        _v.get("injury", ""),
                    "source":        _v.get("source", ""),
                    "comment":       _v.get("comment", ""),
                }
                for _k, _v in _scraped_inj.items()
            }
            st.session_state["injury_status_map"] = _auto_status_map
        # Record this refresh so subsequent page navigations skip it
        st.session_state["_injury_last_refreshed_at"] = _time_mod.time()
    except Exception:
        pass  # Non-fatal — analysis page works without auto-refresh

# ============================================================
# END SECTION: Page Setup
# ============================================================


# ============================================================
# SECTION: Helper Functions (extracted to pages/helpers/neural_analysis_helpers.py)
# ============================================================
from pages.helpers.neural_analysis_helpers import (
    find_game_context_for_player,
    _build_result_metrics,
    _build_bonus_factors,
    _build_entry_strategy,
    _render_qds_full_breakdown_html,
    render_inline_breakdown_html as _render_inline_breakdown,
    display_prop_analysis_card_qds,
)
from pages.helpers.quantum_analysis_helpers import (
    JOSEPH_DESK_SIZE_CSS as _JOSEPH_DESK_SIZE_CSS,
    QEG_EDGE_THRESHOLD as _QEG_EDGE_THRESHOLD,
    render_dfs_flex_edge_html as _render_dfs_flex_edge_html,
    render_tier_distribution_html as _render_tier_distribution_html,
    render_news_alert_html as _render_news_alert_html,
    render_market_movement_html as _render_market_movement_html,
    render_uncertain_header_html as _render_uncertain_header_html,
    render_uncertain_pick_html as _render_uncertain_pick_html,
    render_gold_tier_banner_html as _render_gold_tier_banner_html,
    render_best_single_bets_header_html as _render_best_single_bets_header_html,
    render_parlays_header_html as _render_parlays_header_html,
    render_parlay_card_html as _render_parlay_card_html,
    render_game_matchup_card_html as _render_game_matchup_card_html,
    render_quantum_edge_gap_banner_html as _render_edge_gap_banner_html,
    render_quantum_edge_gap_grouped_html as _render_edge_gap_grouped_html,
    deduplicate_qeg_picks as _deduplicate_qeg_picks,
    filter_qeg_picks as _filter_qeg_picks,
    render_hero_section_html as _render_hero_section_html,
    render_platform_picks_html as _render_platform_picks_html,
    render_quick_view_html as _render_quick_view_html,
    IMPACT_COLORS as _IMP_COLORS,
    CATEGORY_EMOJI as _CAT_EMOJI,
)
# ============================================================
# END SECTION: Helper Functions
# ============================================================

# ============================================================
# SECTION: Load All Required Data
# ============================================================

players_data           = load_players_data()
teams_data             = load_teams_data()
defensive_ratings_data = load_defensive_ratings_data()

current_props  = load_props_from_session(st.session_state)
todays_games   = st.session_state.get("todays_games", [])

# ── Safety net: enrich with alt-line categories if missing ──────
# Props saved before the enrichment pipeline was wired may lack
# line_category.  Re-enrich to stamp all props as "standard".
if current_props and not any(p.get("line_category") for p in current_props):
    try:
        from data.sportsbook_service import parse_alt_lines_from_platform_props
        current_props = parse_alt_lines_from_platform_props(current_props)
    except ImportError:
        _logger.warning("parse_alt_lines_from_platform_props unavailable — line categories may be missing")
simulation_depth = st.session_state.get("simulation_depth", 2000)
minimum_edge     = st.session_state.get("minimum_edge_threshold", 5.0)

# ============================================================
# END SECTION: Load All Required Data
# ============================================================

# ============================================================
# SECTION: QDS Page Header
# ============================================================

st.markdown(
    '<h2 style="font-family:\'Orbitron\',sans-serif;color:#00ffd5;'
    'margin-bottom:4px;">⚡ Neural Analysis</h2>'
    '<p style="color:#a0b4d0;margin-top:0;font-size:0.82rem;">Quantum Matrix Engine 5.6 — Powered by N.A.N. (Neural Analysis Network)</p>',
    unsafe_allow_html=True,
)

# ── Sidebar: How to Use, Settings, Roster Health, Framework Logic ──
# Moved out of the main column to reduce pre-flight scroll distance.
with st.sidebar:
    with st.expander("📖 How to Use", expanded=False):
        st.markdown("""
        **Quick Start:** Load props → Click Run Analysis → View results.
        
        **Reading Results:**
        - **Confidence Score**: 0-100 composite (70+ = high confidence)
        - **Edge**: Advantage over 50/50 (higher = better value)
        - **Tier**: 💎 Platinum (85+) > 🥇 Gold (70+) > 🥈 Silver (55+) > 🥉 Bronze
        
        💡 Focus on Platinum and Gold tier picks for best results.
        """)

    with st.expander("📖 Framework Logic", expanded=False):
        st.markdown(get_qds_framework_logic_html(), unsafe_allow_html=True)

    st.caption(f"⚙️ Sims: **{simulation_depth:,}** · Min Edge: **{minimum_edge}%**")
    _shown_platforms = st.session_state.get("selected_platforms", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"])
    st.caption(f"⚙️ Platforms: **{', '.join(_shown_platforms)}**")

    if current_props and players_data:
        validation     = validate_props_against_roster(current_props, players_data)
        total          = validation["total"]
        matched_count  = validation["matched_count"]
        if validation["unmatched"] or validation["fuzzy_matched"]:
            with st.expander(
                f"⚠️ Roster: {matched_count}/{total} matched "
                f"({int(matched_count / max(total, 1) * 100)}%)"
            ):
                st.markdown(
                    get_roster_health_html(
                        validation["matched"],
                        validation["fuzzy_matched"],
                        validation["unmatched"],
                    ),
                    unsafe_allow_html=True,
                )

# ── Data Freshness Banner (kept in main — important signal) ───
try:
    import os as _os_check
    _players_csv = _os_check.path.join(
        _os_check.path.dirname(_os_check.path.dirname(__file__)), "data", "players.csv"
    )
    if _os_check.path.exists(_players_csv):
        _players_age_h = (
            datetime.datetime.now().timestamp()
            - _os_check.path.getmtime(_players_csv)
        ) / 3600.0
        if _players_age_h > 48:
            st.error(
                f"🚨 **Player data is {_players_age_h:.0f}h old!** "
                "Go to **📡 Smart NBA Data** → Smart Update to refresh."
            )
        elif _players_age_h > 24:
            st.warning(
                f"⚠️ **Player data is {_players_age_h:.0f}h old.** "
                "Run a **Smart Update** for the most accurate projections."
            )
except Exception:
    pass  # Non-critical check

# ── Compact status line + Run Analysis ─────────────────────────
_status_parts = []
if current_props:
    _status_parts.append(f"📋 **{len(current_props)} props** loaded")
else:
    st.warning(
        "⚠️ No props loaded. Go to **🔬 Prop Scanner** → "
        "**🤖 Auto-Generate Props for Tonight's Games** or import props manually."
    )
if todays_games:
    _status_parts.append(f"🏟️ **{len(todays_games)} game{'s' if len(todays_games) != 1 else ''}** tonight")
else:
    st.warning(
        "⚠️ No games loaded. Click **🔄 Auto-Load Tonight's Games** "
        "on the Live Games page first."
    )
if _status_parts:
    st.markdown(" · ".join(_status_parts), unsafe_allow_html=True)

# ============================================================
# SECTION: Prop Pool (all available props passed to engine)
# ============================================================

# All available props are sent to the engine — no stat-type filtering or
# intake cap.  The analysis loop will process every prop until all are
# exhausted, outputting as many high-confidence bets as possible.

# ── Change 9: Smart Prop De-duplication Before Analysis ──────
# If a user loads props from multiple sources (Prop Scanner + Live Games),
# duplicate player/stat/line combos will be analyzed twice.  De-dup on
# (player_name, stat_type, line, platform) before sending to the engine.
_seen_keys: set = set()
_deduped_props: list = []
for _p in current_props:
    _dedup_key = (
        (_p.get("player_name") or "").strip().lower(),
        (_p.get("stat_type") or "").strip().lower(),
        round(float(_p.get("line", 0) or 0), 1),
        (_p.get("platform") or "").strip(),
    )
    if _dedup_key not in _seen_keys:
        _seen_keys.add(_dedup_key)
        _deduped_props.append(_p)
_dedup_removed = len(current_props) - len(_deduped_props)
final_props = _deduped_props

if _dedup_removed > 0:
    st.caption(f"🔁 {_dedup_removed} duplicate(s) removed · **{len(final_props)}** props ready")

# ============================================================
# END SECTION: Prop Pool
# ============================================================

# ============================================================
# SECTION: Analysis Runner
# ============================================================

# ── Auto-trigger: run analysis immediately if props exist but no results ──
_qam_auto_triggered = False
if (final_props
        and not st.session_state.get("analysis_results")
        and not st.session_state.get("_qam_analysis_requested")
        and not st.session_state.get("_qam_db_restored")):
    try:
        from zoneinfo import ZoneInfo as _ZI_qam
        import datetime as _dt_qam
        _qam_today = _dt_qam.datetime.now(_ZI_qam("America/New_York")).date().isoformat()
    except Exception:
        import datetime as _dt_qam
        _qam_today = _dt_qam.date.today().isoformat()
    if st.session_state.get("_qam_auto_run_date") != _qam_today:
        st.session_state["_qam_auto_run_date"] = _qam_today
        st.session_state["_qam_analysis_requested"] = True
        _qam_auto_triggered = True

run_analysis = st.button(
    "🚀 Run Analysis",
    type="primary",
    disabled=(len(final_props) == 0),
    help=f"Analyze {len(final_props)} props with Quantum Matrix Engine 5.6",
) or _qam_auto_triggered

# ── Feature 14: Quick Filter Chips ──────────────────────────────
# Initialise session-state keys for filter chips (persist across reruns).
for _chip_key in ("chip_platinum", "chip_gold_plus", "chip_high_edge",
                  "chip_hot_form", "chip_hide_avoids"):
    if _chip_key not in st.session_state:
        st.session_state[_chip_key] = False

# ── Feature 15: Sort selector ───────────────────────────────────
if "qam_sort_key" not in st.session_state:
    st.session_state["qam_sort_key"] = "Confidence Score ↓"

# Default for the show-all/top radio (rendered inside the results fragment).
st.session_state.setdefault("qam_show_mode", "All picks")

if run_analysis:
    # Set a flag so that if the user navigates away during analysis
    # and comes back, the page knows to offer a re-run.
    st.session_state["_qam_analysis_requested"] = True
    _analysis_start_time = time.time()
    # ── Joseph Loading Screen — NBA fun facts while analysis runs ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _joseph_loader = joseph_loading_placeholder("Running Quantum Matrix Analysis")
    except Exception:
        _joseph_loader = None
    _progress_status = st.empty()
    _progress_status.caption("Starting analysis…")
    progress_bar         = st.progress(0)

    # ── Show Joseph's animated loading screen with NBA fun facts ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _joseph_loading = joseph_loading_placeholder("🔬 Analyzing props — hang tight…")
    except Exception:
        _joseph_loading = None

    analysis_results_list = []

    # Clear stale Joseph results so fresh ones are generated after this run.
    st.session_state.pop("joseph_results", None)
    st.session_state["joseph_bets_logged"] = False

    try:
        # ── Filter props to only tonight's teams (with abbreviation aliases) ──
        # Build expanded playing-teams set that covers all known alias variants
        # (e.g. "GS" ↔ "GSW", "NY" ↔ "NYK") so team-abbreviation mismatches
        # don't silently drop valid props.
        ABBREV_ALIASES = {
            "GS": "GSW", "GSW": "GS",
            "NY": "NYK", "NYK": "NY",
            "NO": "NOP", "NOP": "NO",
            "SA": "SAS", "SAS": "SA",
            "UTAH": "UTA", "UTA": "UTAH",
            "WSH": "WAS", "WAS": "WSH",
            "BKN": "BRK", "BRK": "BKN",
            "PHX": "PHO", "PHO": "PHX",
            "CHA": "CHO", "CHO": "CHA",
            "NJ": "BKN",
        }

        # Full team name → abbreviation mapping for platform props that use
        # full names or nicknames instead of standard 3-letter codes.
        try:
            from data.nba_data_service import TEAM_NAME_TO_ABBREVIATION as _TEAM_FULL_MAP
        except ImportError:
            _TEAM_FULL_MAP = {}

        # Build reverse lookups: nickname → abbrev
        _TEAM_NICKNAME_MAP: dict = {}   # e.g. "LAKERS" → "LAL"
        for _full_name, _abbr in _TEAM_FULL_MAP.items():
            parts = _full_name.rsplit(" ", 1)
            if len(parts) == 2:
                _TEAM_NICKNAME_MAP[parts[1].upper()] = _abbr
            _TEAM_NICKNAME_MAP[_full_name.upper()] = _abbr

        def _normalize_team_to_abbrev(raw_team: str) -> str:
            """Convert any team representation to a standard abbreviation.

            Handles: 3-letter codes, full names, nicknames, common aliases.
            Returns the uppercased team string unchanged if no mapping found.
            """
            team_upper = raw_team.upper().strip()
            if not team_upper:
                return ""
            # Already a known abbreviation or alias?
            if len(team_upper) <= 4:
                return ABBREV_ALIASES.get(team_upper, team_upper)
            # Full name or nickname match? (e.g. "Los Angeles Lakers", "Lakers")
            mapped = _TEAM_NICKNAME_MAP.get(team_upper)
            if mapped:
                return mapped
            # Last word might be nickname (e.g. "LA Lakers" → "Lakers")
            last_word = team_upper.rsplit(" ", 1)[-1] if " " in team_upper else ""
            if last_word:
                mapped = _TEAM_NICKNAME_MAP.get(last_word)
                if mapped:
                    return mapped
            return team_upper

        playing_teams_expanded: set = set()
        for _g in todays_games:
            for _abbrev in (
                _g.get("home_team", "").upper().strip(),
                _g.get("away_team", "").upper().strip(),
            ):
                if not _abbrev:
                    continue
                playing_teams_expanded.add(_abbrev)
                # Add known alias for this abbreviation (if any)
                _alias = ABBREV_ALIASES.get(_abbrev)
                if _alias:
                    playing_teams_expanded.add(_alias)
        playing_teams_expanded.discard("")

        if playing_teams_expanded:
            props_to_analyze = [
                p for p in final_props
                if (
                    _normalize_team_to_abbrev(p.get("team", "")) in playing_teams_expanded
                    or not p.get("team", "").strip()  # include props with no team set
                )
            ]
            skipped_count = len(final_props) - len(props_to_analyze)
            if skipped_count > 0:
                st.info(
                    f"ℹ️ Skipping **{skipped_count}** prop(s) for teams not playing tonight. "
                    f"Analyzing **{len(props_to_analyze)}** prop(s) for tonight's {len(todays_games)} game(s)."
                )

            # ── Fallback: if ALL props were filtered out, analyze them all ──
            # This prevents a dead-end where a team-name format mismatch
            # between platforms and the games list silently drops every prop.
            if len(props_to_analyze) == 0 and len(final_props) > 0:
                st.warning(
                    f"⚠️ All **{len(final_props)}** props were filtered out by tonight's team list. "
                    f"This usually means the team names in your props don't match the loaded games. "
                    f"**Proceeding with all {len(final_props)} props** so your analysis isn't blocked."
                )
                props_to_analyze = list(final_props)
        else:
            props_to_analyze = list(final_props)  # Fallback: no games loaded

        # ── Also skip confirmed Out/IR players via injury map ────────────
        # If injury_map_pre is empty (failed to load), do NOT filter — just proceed.
        # NOTE: "Doubtful" and "Questionable" players are NOT filtered here —
        # they pass through to full analysis with an injury_status_penalty
        # applied to the confidence score.  This matches the in-analysis
        # injury gate which only skips clearly inactive statuses.
        injury_map_pre = st.session_state.get("injury_status_map", {})
        _INACTIVE_STATUSES = frozenset({
            "Out", "Injured Reserve", "Out (No Recent Games)",
            "Suspended", "Not With Team",
            "G League - Two-Way", "G League - On Assignment", "G League",
        })
        if injury_map_pre:
            before_inj = len(props_to_analyze)
            props_to_analyze = [
                p for p in props_to_analyze
                if injury_map_pre.get(
                    p.get("player_name", "").lower().strip(), {}
                ).get("status", "Active") not in _INACTIVE_STATUSES
            ]
            inj_skipped = before_inj - len(props_to_analyze)
            if inj_skipped > 0:
                st.info(f"ℹ️ Skipping **{inj_skipped}** prop(s) for confirmed Out/IR players.")

        # ── Filter to selected platforms (from ⚙️ Settings) ──────────────
        _selected_platforms = st.session_state.get(
            "selected_platforms", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"]
        )
        if _selected_platforms:
            before_plat = len(props_to_analyze)
            props_to_analyze = [
                p for p in props_to_analyze
                if not p.get("platform", "").strip()          # include props with no platform
                or p.get("platform", "") in _selected_platforms
            ]
            plat_skipped = before_plat - len(props_to_analyze)
            if plat_skipped > 0:
                st.info(
                    f"ℹ️ Skipping **{plat_skipped}** prop(s) for platforms not in your "
                    f"selection ({', '.join(_selected_platforms)}). "
                    "Change platforms on the ⚙️ Settings page."
                )

        # ── Show per-platform prop count summary ─────────────────────────
        if props_to_analyze:
            _plat_counts = {}
            for _p in props_to_analyze:
                _plat = _p.get("platform", "Unknown")
                _plat_counts[_plat] = _plat_counts.get(_plat, 0) + 1
            _plat_summary = " · ".join(
                f"**{_plat}**: {_n}" for _plat, _n in sorted(_plat_counts.items())
            )
            st.caption(f"📊 Analyzing: {_plat_summary}")

        total_props_count    = len(props_to_analyze)
        if total_props_count == 0:
            st.warning("⚠️ No props remain after filtering to tonight's teams / injury status. Check your games and props.")
            _progress_status.empty()
            progress_bar.empty()
            st.stop()

        # ── Analysis proceeds with all available props (no cap) ────

        # ── Change 7: Parallel data pre-fetching ────────────────────
        # Pre-fetch player bios in parallel so the main loop doesn't
        # block on I/O for each unmatched player.  Each prop's
        # simulation is independent, but the loop body accesses
        # Streamlit session state (not thread-safe), so we parallelise
        # the pure-I/O pre-fetch step instead of the whole loop.
        _prefetched_bios: dict = {}
        _names_to_prefetch = list({
            p.get("player_name", "") for p in props_to_analyze
            if p.get("player_name") and not find_player_by_name(players_data, p.get("player_name", ""))
        })
        if _names_to_prefetch:
            try:
                from data.player_profile_service import get_player_bio as _get_bio
                _max_workers = min(_MAX_BIO_PREFETCH_WORKERS, len(_names_to_prefetch))
                with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as _pool:
                    _bio_futures = {
                        _pool.submit(_get_bio, name): name
                        for name in _names_to_prefetch
                    }
                    for _fut in concurrent.futures.as_completed(_bio_futures):
                        _fname = _bio_futures[_fut]
                        try:
                            _prefetched_bios[_fname] = _fut.result()
                        except Exception:
                            pass
            except ImportError:
                pass  # player_profile_service not available

        # ── Delegate to analysis orchestrator ──────────────────────────
        # The entire per-prop analysis loop has been extracted to
        # engine.analysis_orchestrator.analyze_props_batch() — a pure
        # engine function with no Streamlit dependency.
        from engine.analysis_orchestrator import analyze_props_batch as _analyze_batch

        _line_snapshots = st.session_state.setdefault("line_snapshots", {})

        def _progress_cb(idx: int, total: int, name: str):
            _progress_status.caption(f"Analyzing {name}… ({idx + 1}/{total})")
            progress_bar.progress((idx + 1) / total)

        analysis_results_list = _analyze_batch(
            props_to_analyze,
            players_data=players_data,
            todays_games=todays_games,
            injury_map=st.session_state.get("injury_status_map", {}),
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
            simulation_depth=simulation_depth,
            prefetched_bios=_prefetched_bios,
            advanced_enrichment=st.session_state.get("advanced_enrichment", {}),
            line_snapshots=_line_snapshots,
            progress_callback=_progress_cb,
        )

        # Free working memory used during analysis before rendering results
        import gc as _gc
        del players_data, defensive_ratings_data, teams_data, _prefetched_bios
        _gc.collect()
        # ── Auto-trigger Smart Update if >20% of players are unmatched ─
        # Unmatched players use skeleton stats which reduces accuracy.
        # Loading fresh rosters resolves most mismatches without user action.
        _unmatched_players = list(dict.fromkeys(
            r.get("player_name", "")
            for r in analysis_results_list
            if not r.get("player_matched", True) and not r.get("player_is_out", False)
        ))
        _total_non_out = sum(
            1 for r in analysis_results_list if not r.get("player_is_out", False)
        )
        _unmatched_ratio = len(_unmatched_players) / max(_total_non_out, 1)
        if (
            _unmatched_ratio > 0.20
            and todays_games
            and not st.session_state.get("_smart_update_attempted")
        ):
            # Guard: only attempt the auto-update once per session to
            # prevent an infinite rerun loop when the fetch always fails
            # or the mismatch persists after updating.
            st.session_state["_smart_update_attempted"] = True
            st.info(
                f"🔄 **{len(_unmatched_players)} player(s) not found** in local database "
                f"({_unmatched_ratio*100:.0f}% of props). Triggering Smart Roster Update…"
            )
            try:
                from data.nba_data_service import get_todays_players as _get_today
                _roster_result = _get_today(todays_games, progress_callback=None)
                if _roster_result:
                    try:
                        load_players_data.clear()  # bust Streamlit's CSV cache
                    except Exception:
                        pass
                    st.success(
                        f"✅ Smart Roster Update complete — fresh player data loaded "
                        f"for {len(_unmatched_players)} player(s). Results below use "
                        f"the best available data."
                    )
                    # NOTE: st.rerun() was intentionally REMOVED here.
                    # The rerun forced the entire ~3000-line page to re-execute,
                    # which on mobile cascaded into an infinite rerun loop
                    # (scroll → widget touch → rerun → re-render → scroll → …).
                    # The current analysis results are already computed and will
                    # be stored in session_state below.  The updated roster will
                    # be used automatically on the NEXT analysis run.
            except Exception as _su_err:
                # Non-fatal — proceed with existing results
                _logger.warning(f"Smart Update error (non-fatal): {_su_err}")

        # Sorting and correlation detection handled by analyze_props_batch()
        _total_analyzed = len(analysis_results_list)
        _out_results = [r for r in analysis_results_list if r.get("player_is_out", False)]
        _selected_active = [r for r in analysis_results_list if not r.get("player_is_out", False)]

        # NOTE: analysis_results_list is already sorted (active by composite_win_score
        # desc, Out at end) via analyze_props_batch(). The sort block that was here
        # has been removed — it was duplicate work.
        _logger.info(
            "QME 5.6 Output: %d analyzed → %d active + %d Out = %d total",
            _total_analyzed, len(_selected_active), len(_out_results), len(analysis_results_list),
        )

        st.session_state["analysis_results"] = analysis_results_list
        st.session_state["analysis_timestamp"] = datetime.datetime.now()
        # Clear the requested flag — analysis completed successfully.
        st.session_state.pop("_qam_analysis_requested", None)

        # ── Persist analysis session to SQLite (survives page refresh/inactivity) ──
        try:
            from tracking.database import save_analysis_session as _save_session
            _qam_new_sid = _save_session(
                analysis_results=analysis_results_list,
                todays_games=st.session_state.get("todays_games", []),
                selected_picks=st.session_state.get("selected_picks", []),
            )
            # Session Bridge: write the new session_id into the URL so that
            # a page refresh or tab-switch recovers exactly this run from DB
            # instead of defaulting to a fresh analysis.
            if _qam_new_sid and _qam_new_sid > 0:
                st.query_params["sid"] = str(_qam_new_sid)
                # Clear the DB-restored flag — this is now a brand-new run.
                st.session_state.pop("_qam_db_restored", None)
        except Exception as _persist_err:
            pass  # Non-fatal — session state still has results
        _progress_status.empty()
        progress_bar.empty()
        # Dismiss the Joseph loading screen
        if _joseph_loader is not None:
            try:
                _joseph_loader.empty()
            except Exception:
                pass
        _analysis_elapsed = time.time() - _analysis_start_time
        st.success(
            f"✅ Analysis complete! Analyzed and displaying **{len(_selected_active)}** picks "
            f"(+ {len(_out_results)} out) in **{_analysis_elapsed:.1f}s**."
        )

        # ── Store ALL picks to all_analysis_picks table ──────────────
        try:
            from tracking.database import insert_analysis_picks as _insert_picks
            _stored = _insert_picks(analysis_results_list)
            if _stored > 0:
                _logger.info(f"Stored {_stored} analysis picks to all_analysis_picks table.")
        except Exception as _store_err:
            _logger.warning(f"Store analysis picks error (non-fatal): {_store_err}")

        # ── Auto-log all qualifying picks to the Bet Tracker ────────
        try:
            from tracking.bet_tracker import auto_log_analysis_bets as _auto_log
            _auto_logged = _auto_log(analysis_results_list, minimum_edge=minimum_edge, max_bets=len(analysis_results_list))
            if _auto_logged > 0:
                st.info(
                    f"📊 Auto-logged **{_auto_logged}** qualifying pick(s) to the Bet Tracker."
                )
        except Exception as _auto_log_err:
            # Auto-logging is best-effort — never block the main analysis flow
            _logger.warning(f"Auto-log error (non-fatal): {_auto_log_err}")

        # NOTE: st.rerun() was removed here.  The results are already
        # stored in st.session_state["analysis_results"] and will render
        # naturally when the script continues past the ``if run_analysis:``
        # block.  The rerun was forcing a double-render which, on mobile,
        # cascaded into an infinite rerun loop (scroll → widget touch →
        # rerun → re-render → scroll → …).
    except Exception as _analysis_err:
        _err_str = str(_analysis_err)
        if "WebSocketClosedError" not in _err_str and "StreamClosedError" not in _err_str:
            st.error(f"❌ Analysis failed: {_analysis_err}")
    finally:_progress_status.empty()
            
        try:
            progress_bar.empty()
        except Exception:
            pass
        if _joseph_loader is not None:
            try:
                _joseph_loader.empty()
            except Exception:
                pass

# ============================================================
# END SECTION: Analysis Runner
# ============================================================

# ── Auto-retry notice: if user navigated away during analysis ──
if (
    st.session_state.get("_qam_analysis_requested")
    and not st.session_state.get("analysis_results")
    and not run_analysis
):
    st.warning(
        "⚠️ **Analysis was interrupted** (you may have navigated away before it finished). "
        "Click **🚀 Run Analysis** above to restart."
    )
    st.session_state.pop("_qam_analysis_requested", None)

# ============================================================
# SECTION: Display Analysis Results
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

# NOTE: _player_news_lookup was previously built here and captured by the
# results fragment via closure.  It is now built inside the fragment itself
# to avoid closure dependencies.  Keeping a top-level reference for any
# non-fragment code that might still use it.
_player_news_lookup: dict = {}  # {player_name_lower: [news_item, ...]}
for _ni in st.session_state.get("player_news", []):
    _ni_player = _ni.get("player_name", "").strip().lower()
    if _ni_player:
        _player_news_lookup.setdefault(_ni_player, []).append(_ni)

# Show a notice if results were reloaded from the saved session
if analysis_results and st.session_state.get("_analysis_session_reloaded_at"):
    _reloaded_ts = st.session_state["_analysis_session_reloaded_at"]
    st.info(
        f"💾 **Analysis restored from saved session** (last run: {_reloaded_ts}). "
        "Results are preserved from your last analysis run — click **🚀 Run Analysis** above to refresh."
    )

# ── ⚡ Platform AI Picks (own section, above Joseph Broadcast Desk) ──────────
if analysis_results:
    _outer_plat_ai_pool = [
        r for r in analysis_results
        if r.get("platform", "").strip()
        and not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and float(r.get("confidence_score", 0)) >= 60
    ]
    _outer_plat_ai_pool = sorted(
        _outer_plat_ai_pool,
        key=lambda r: float(r.get("confidence_score", 0)),
        reverse=True,
    )[:8]
    if _outer_plat_ai_pool:
        _outer_players_data = locals().get("players_data") or globals().get("players_data")
        if not _outer_players_data:
            try:
                from data.data_manager import load_players_data as _lpd_outer
                _outer_players_data = _lpd_outer() or []
            except Exception:
                _outer_players_data = []
        if _outer_players_data and any(not r.get("player_id") for r in _outer_plat_ai_pool):
            _outer_pid_lookup = {
                str(p.get("name", "")).lower(): str(p.get("player_id", ""))
                for p in _outer_players_data
                if p.get("player_id")
            }
            for _op in _outer_plat_ai_pool:
                if not _op.get("player_id"):
                    _op["player_id"] = _outer_pid_lookup.get(
                        str(_op.get("player_name", "")).lower(), ""
                    )
        st.markdown(
            _render_platform_picks_html(_outer_plat_ai_pool),
            unsafe_allow_html=True,
        )
# ── END Platform AI Picks ─────────────────────────────────────────────────────

# ════ JOSEPH M. SMITH LIVE BROADCAST DESK ════
# Reduce Joseph's container size by 60% on this page per design requirements.
# CSS extracted to pages/helpers/quantum_analysis_helpers.py
# Wrapped in @st.fragment so the heavy enrichment loop does NOT re-execute
# on every scroll-triggered rerun — only when the fragment itself reruns.
if analysis_results and st.session_state.get("joseph_enabled", True):
    st.markdown(_JOSEPH_DESK_SIZE_CSS, unsafe_allow_html=True)

    @st.fragment
    def _render_joseph_desk():
        """Render Joseph's Live Broadcast Desk in an isolated fragment.

        The ``enrich_player_god_mode`` loop is expensive — running it on
        every full-page rerun (triggered by mobile scroll events) was a
        major contributor to the rerun cascade.  As a fragment, this
        section only re-executes when a widget *inside* it is touched.

        Reads ``analysis_results`` from session state directly so the
        fragment stays independent of outer-scope closures.
        """
        _desk_analysis_results = st.session_state.get("analysis_results", [])
        try:
            from pages.helpers.joseph_live_desk import render_joseph_live_desk
            from data.advanced_metrics import enrich_player_god_mode
            from data.data_manager import load_players_data, load_teams_data
            from engine.joseph_bets import joseph_auto_log_bets
            from utils.joseph_widget import inject_joseph_inline_commentary

            _players = load_players_data()
            _teams = {t.get("abbreviation", "").upper(): t for t in load_teams_data()}
            _games = st.session_state.get("todays_games", [])

            _enriched = []
            for _p in _players:
                try:
                    _enriched.append(enrich_player_god_mode(_p, _games, _teams))
                except Exception:
                    _enriched.append(_p)
            _enriched_lookup = {str(p.get("name", "")).lower().strip(): p for p in _enriched}

            with st.container():
                render_joseph_live_desk(
                    analysis_results=_desk_analysis_results,
                    enriched_players=_enriched_lookup,
                    teams_data=_teams,
                    todays_games=_games,
                )

            # Use joseph_results (enriched with verdicts) for inline commentary
            # when available; fall back to raw analysis_results.
            _joseph_results = st.session_state.get("joseph_results", [])
            inject_joseph_inline_commentary(
                _joseph_results if _joseph_results else _desk_analysis_results,
                "analysis_results",
            )

            if not st.session_state.get("joseph_bets_logged", False):
                if _joseph_results:
                    _logged_count, _logged_msg = joseph_auto_log_bets(_joseph_results)
                    if _logged_count > 0:
                        st.toast(f"🎙️ {_logged_msg}")
                    st.session_state["joseph_bets_logged"] = True

            st.divider()
        except Exception as _joseph_err:
            import logging
            logging.getLogger(__name__).warning(f"Joseph Live Desk error: {_joseph_err}")

    _render_joseph_desk()
# ════ END JOSEPH LIVE DESK ════


# ── Fragment: isolate results display so widget interactions (toggles,
#    filter chips, multiselect, sort selectbox) only re-render this
#    section — NOT the entire ~2900-line page.  This is the single
#    highest-impact fix for the mobile rerun cascade.
@st.fragment
def _render_results_fragment():
    """Display analysis results inside a Streamlit fragment.

    Widgets inside this fragment (filter chips, sort controls, tier
    multiselect, etc.) will only re-run *this* function on interaction,
    preventing full-page reruns that cascade on mobile.

    All data is read from ``st.session_state`` (or via cached loaders)
    so the fragment remains **independent of outer-scope closures**
    during fragment-only re-runs.  NO outer variables are captured.
    """
    # ── Read ALL needed state directly inside the fragment ────────
    # This ensures values are fresh on every fragment re-run AND
    # eliminates closure captures that would tie the fragment to the
    # full-page execution scope.
    _frag_analysis_results = st.session_state.get("analysis_results", [])

    # ── Purge stale error results from previous code versions ─────
    # If any result contains the old game_context TypeError, the entire
    # batch is from a pre-fix run and must be discarded so the user
    # isn't stuck viewing zombie error cards.
    if _frag_analysis_results:
        _has_stale_errors = any(
            "game_context" in str(r.get("player_status_note", ""))
            or "game_context" in str(r.get("recommendation", ""))
            or (r.get("player_status") == "Analysis Error"
                and "game_context" in str(r.get("avoid_reasons", [])))
            for r in _frag_analysis_results
        )
        if _has_stale_errors:
            st.session_state.pop("analysis_results", None)
            _frag_analysis_results = []

    # ── Scrub results to today's active teams ─────────────────────
    # Runs before any rendering so stale picks (from a prior analysis
    # run that included teams not playing today) are dropped at the
    # earliest possible point — before counts, filters, or cards.
    if _frag_analysis_results:
        try:
            from data.nba_data_service import get_todays_games as _get_tg_scrub
            _scrub_games = st.session_state.get("todays_games") or _get_tg_scrub() or []
            _scrub_abbrs: set[str] = set()
            for _sg in _scrub_games:
                _sh = (_sg.get("home_team") or "").upper().strip()
                _sa = (_sg.get("away_team") or "").upper().strip()
                if _sh:
                    _scrub_abbrs.add(_sh)
                if _sa:
                    _scrub_abbrs.add(_sa)
            if _scrub_abbrs:
                _frag_analysis_results = [
                    r for r in _frag_analysis_results
                    if (
                        (r.get("player_team") or r.get("team") or "")
                        .upper().strip()
                    ) in _scrub_abbrs
                ]
                st.session_state["analysis_results"] = _frag_analysis_results
        except Exception:
            pass

    _frag_current_props = load_props_from_session(st.session_state)
    _frag_minimum_edge = st.session_state.get("minimum_edge_threshold", 5.0)
    _frag_todays_games = st.session_state.get("todays_games", [])
    # Fallback: if session state has no game data, fetch directly so game
    # banners always render even when the user navigates straight to QAM.
    if not _frag_todays_games:
        try:
            from data.nba_data_service import get_todays_games as _get_games_direct
            _frag_todays_games = _get_games_direct() or []
            if _frag_todays_games:
                st.session_state["todays_games"] = _frag_todays_games
        except Exception:
            pass
    _frag_players_data = load_players_data()

    # Build player → news lookup inside the fragment (was a closure before).
    _frag_player_news_lookup: dict = {}
    for _ni in st.session_state.get("player_news", []):
        _ni_player = _ni.get("player_name", "").strip().lower()
        if _ni_player:
            _frag_player_news_lookup.setdefault(_ni_player, []).append(_ni)

    if not _frag_analysis_results:
        # ``run_analysis`` is a momentary button — always False after the
        # initial page run, so we check the session-state flag instead.
        _analysis_running = st.session_state.get("_qam_analysis_requested", False)
        if not _analysis_running:
            if _frag_current_props:
                st.info("👆 Click **Run Analysis** to analyze all loaded props.")
            else:
                _has_games = bool(_frag_todays_games)
                if _has_games:
                    st.warning(
                        "⚠️ No props loaded yet. "
                        "Go to **🔬 Prop Scanner** and click **🤖 Auto-Generate Props for Tonight** "
                        "to instantly create props for all active players on tonight's teams — "
                        "or click **🔄 Auto-Load Tonight's Games** on the **📡 Live Games** page "
                        "to reload games and auto-generate props in one step."
                    )
                else:
                    st.warning(
                        "⚠️ No props loaded and no games found. "
                        "Start on the **📡 Live Games** page — click **🔄 Auto-Load Tonight's Games** "
                        "to load tonight's schedule and auto-generate props for all active players."
                    )
        return

    st.divider()

    # ── Show mode radio (moved here from top-level to avoid full-page reruns) ──
    _SHOW_MODE_OPTIONS = ["All picks", "Top picks only (edge ≥ threshold)"]
    _show_mode = st.radio(
        "Show:",
        _SHOW_MODE_OPTIONS,
        horizontal=True,
        index=_SHOW_MODE_OPTIONS.index(
            st.session_state.get("qam_show_mode", "Top picks only (edge ≥ threshold)")
        ),
        key="_qam_show_mode_radio",
    )
    st.session_state["qam_show_mode"] = _show_mode

    # Filter results
    if _show_mode == "Top picks only (edge ≥ threshold)":
        displayed_results = [
            r for r in _frag_analysis_results
            if abs(r.get("edge_percentage", 0)) >= _frag_minimum_edge
        ]
    else:
        displayed_results = _frag_analysis_results

    # ── Drop unbettable demon / goblin alternate lines ──────────────
    displayed_results = [r for r in displayed_results if not is_unbettable_line(r)]

    # ── Feature 14: Quick Filter Chips ──────────────────────────────
    # Render filter chips as Streamlit columns of toggle buttons.
    _chip_col1, _chip_col2, _chip_col3, _chip_col4, _chip_col5 = st.columns(5)
    with _chip_col1:
        st.session_state["chip_platinum"] = st.toggle(
            "💎 Platinum Only", value=st.session_state.get("chip_platinum", False),
            key="_chip_platinum_toggle",
        )
    with _chip_col2:
        st.session_state["chip_gold_plus"] = st.toggle(
            "🥇 Gold+", value=st.session_state.get("chip_gold_plus", False),
            key="_chip_gold_plus_toggle",
        )
    with _chip_col3:
        st.session_state["chip_high_edge"] = st.toggle(
            "⚡ High Edge (≥10%)", value=st.session_state.get("chip_high_edge", False),
            key="_chip_high_edge_toggle",
        )
    with _chip_col4:
        st.session_state["chip_hot_form"] = st.toggle(
            "🔥 Hot Form", value=st.session_state.get("chip_hot_form", False),
            key="_chip_hot_form_toggle",
        )
    with _chip_col5:
        st.session_state["chip_hide_avoids"] = st.toggle(
            "❌ Hide Avoids", value=st.session_state.get("chip_hide_avoids", True),
            key="_chip_hide_avoids_toggle",
        )

    # Apply chip filters (chips are additive — if multiple are active
    # the result is the union so the user can combine Platinum + High Edge).
    _any_tier_chip = (
        st.session_state.get("chip_platinum", False)
        or st.session_state.get("chip_gold_plus", False)
    )
    if _any_tier_chip:
        _allowed_tiers: set = set()
        if st.session_state.get("chip_platinum"):
            _allowed_tiers.add("Platinum")
        if st.session_state.get("chip_gold_plus"):
            _allowed_tiers.update({"Platinum", "Gold"})
        displayed_results = [
            r for r in displayed_results if r.get("tier") in _allowed_tiers
        ]
    if st.session_state.get("chip_high_edge"):
        displayed_results = [
            r for r in displayed_results
            if abs(r.get("edge_percentage", 0)) >= 10.0
        ]
    if st.session_state.get("chip_hot_form"):
        displayed_results = [
            r for r in displayed_results
            if (r.get("recent_form_ratio") or 0) >= 1.05
        ]
    if st.session_state.get("chip_hide_avoids"):
        # Only hide avoids when the user explicitly toggles this ON.
        _avoid_count = sum(1 for r in displayed_results if r.get("should_avoid", False))
        displayed_results = [
            r for r in displayed_results
            if not r.get("should_avoid", False)
        ]
        if _avoid_count > 0:
            st.caption(
                f"ℹ️ {_avoid_count} pick(s) hidden (flagged as avoid due to "
                "low edge, high variance, or conflicting signals). "
                "Disable **❌ Hide Avoids** to reveal them."
            )

    # ── Legacy tier multiselect (still useful for multi-tier combos) ──
    _na_filter_col1, _na_filter_col2 = st.columns(2)
    with _na_filter_col1:
        _na_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[],
            key="na_tier_filter",
            help="Show only picks matching the selected tiers. Leave empty to show all tiers.",
        )
    with _na_filter_col2:
        # ── Feature 15: Sort Controls ────────────────────────────────
        _sort_options = [
            "Confidence Score ↓",
            "Edge % ↓",
            "Composite Win Score ↓",
            "Alphabetical (A→Z)",
        ]
        _qam_sort_key = st.selectbox(
            "Sort by",
            _sort_options,
            index=_sort_options.index(
                st.session_state.get("qam_sort_key", "Confidence Score ↓")
            ),
            key="_qam_sort_select",
            help="Choose how to order the analysis results.",
        )
        st.session_state["qam_sort_key"] = _qam_sort_key

    if _na_tier_filter:
        _na_tier_names = [t.split(" ")[0] for t in _na_tier_filter]
        displayed_results = [r for r in displayed_results if r.get("tier") in _na_tier_names]

    # ── Quality floor: hide Bronze / Avoid by default & low-confidence picks ──
    # Unless user explicitly selected Bronze or toggled "All picks", strip them out.
    _user_wants_bronze = "Bronze 🥉" in (_na_tier_filter or [])
    if not _user_wants_bronze and _show_mode != "All picks":
        displayed_results = [
            r for r in displayed_results
            if r.get("tier") not in ("Bronze", "Avoid", None)
            and r.get("confidence_score", 0) >= 50
        ]

    # ── Feature 15: Apply sort ───────────────────────────────────────
    if _qam_sort_key == "Confidence Score ↓":
        displayed_results.sort(key=lambda r: r.get("confidence_score", 0), reverse=True)
    elif _qam_sort_key == "Edge % ↓":
        displayed_results.sort(key=lambda r: abs(r.get("edge_percentage", 0)), reverse=True)
    elif _qam_sort_key == "Composite Win Score ↓":
        displayed_results.sort(key=lambda r: r.get("composite_win_score", 0), reverse=True)
    elif _qam_sort_key == "Alphabetical (A→Z)":
        displayed_results.sort(key=lambda r: r.get("player_name", "").lower())

    # ── Deduplicate by (player_name, stat_type, line, direction) ──
    # Prevents duplicate player cards and duplicate Streamlit element keys
    # when the same prop appears multiple times (e.g. from multiple platforms).
    _seen_result_keys: set = set()
    _deduped: list = []
    for _r in displayed_results:
        _rkey = (
            _r.get("player_name", ""),
            _r.get("stat_type", ""),
            _r.get("line", 0),
            _r.get("direction", "OVER"),
        )
        if _rkey not in _seen_result_keys:
            _seen_result_keys.add(_rkey)
            _deduped.append(_r)
    displayed_results = _deduped

    # ── Filter to today's active teams only ──────────────────────
    # Prevents stale results from previous days (e.g. CHI, ATL) from
    # bleeding through when the DB session is older than today's schedule.
    if _frag_todays_games:
        _todays_abbrs: set[str] = set()
        for _tg in _frag_todays_games:
            _tg_h = (_tg.get("home_team") or "").upper().strip()
            _tg_a = (_tg.get("away_team") or "").upper().strip()
            if _tg_h:
                _todays_abbrs.add(_tg_h)
            if _tg_a:
                _todays_abbrs.add(_tg_a)
        if _todays_abbrs:
            displayed_results = [
                r for r in displayed_results
                if (
                    (r.get("player_team") or r.get("team") or "")
                    .upper().strip()
                ) in _todays_abbrs
            ]

    # ── Summary metrics ────────────────────────────────────────
    total_analyzed   = len(_frag_analysis_results)
    total_over_picks = sum(1 for r in displayed_results if r.get("direction") == "OVER")
    total_under_picks= sum(1 for r in displayed_results if r.get("direction") == "UNDER")
    platinum_count   = sum(1 for r in displayed_results if r.get("tier") == "Platinum")
    gold_count       = sum(1 for r in displayed_results if r.get("tier") == "Gold")
    avg_edge         = (
        sum(abs(r.get("edge_percentage", 0)) for r in displayed_results) / len(displayed_results)
        if displayed_results else 0
    )
    unmatched_count  = sum(1 for r in _frag_analysis_results if not r.get("player_matched", True))

    # Phase 3: DFS aggregate metrics
    _dfs_results = [r for r in displayed_results if r.get("dfs_parlay_ev")]
    _beats_be_count = sum(
        1 for r in _dfs_results
        if (r.get("dfs_parlay_ev") or {}).get("best_tier") is not None
    )

    st.subheader(f"📊 Results: {len(displayed_results)} picks (of {total_analyzed} analyzed)")

    sum_col1, sum_col2, sum_col3, sum_col4, sum_col5 = st.columns(5)
    sum_col1.metric("Showing",     len(displayed_results))
    sum_col2.metric("⬆️ MORE",    total_over_picks)
    sum_col3.metric("⬇️ LESS",   total_under_picks)
    sum_col4.metric("💎 Platinum", platinum_count)
    sum_col5.metric("Gold 🥇",     gold_count)

    # ── Feature 13: Summary Dashboard ──────────────────────────────
    # DFS Edge + Tier Distribution rendered inside a styled container.
    # NOTE: Previously used split st.markdown('<div class="qam-sticky-summary">')
    # and st.markdown('</div>') which risked orphaned tags if an exception
    # occurred between them, producing malformed HTML that forced Streamlit
    # to re-render and contributed to the "page restart" issue.

    # Build the summary HTML block as a single unit
    _summary_parts: list[str] = []

    # Phase 3: DFS Edge row (only shown when DFS metrics exist)
    if _dfs_results:
        _avg_dfs_edge = sum(
            (r.get("dfs_parlay_ev") or {}).get("tiers", {}).get(
                (r.get("dfs_parlay_ev") or {}).get("best_tier", 3), {}
            ).get("edge_vs_breakeven", 0) * 100
            for r in _dfs_results
            if (r.get("dfs_parlay_ev") or {}).get("best_tier") is not None
        ) / max(_beats_be_count, 1)
        _summary_parts.append(
            _render_dfs_flex_edge_html(_beats_be_count, len(_dfs_results), _avg_dfs_edge)
        )

    # ── Slate Summary Dashboard ────────────────────────────────
    silver_count  = sum(1 for r in displayed_results if r.get("tier") == "Silver")
    bronze_count  = sum(1 for r in displayed_results if r.get("tier") == "Bronze")
    best_pick     = max(
        (r for r in displayed_results if not r.get("player_is_out", False)),
        key=lambda r: r.get("confidence_score", 0),
        default=None,
    )
    _summary_parts.append(
        _render_tier_distribution_html(
            platinum_count, gold_count, silver_count, bronze_count,
            avg_edge, best_pick,
        )
    )

    # Emit as a single st.markdown call with the wrapper div
    st.markdown(
        '<div class="qam-sticky-summary">'
        + "".join(_summary_parts)
        + '</div>',
        unsafe_allow_html=True,
    )

    # ── 🏆 Top 3 Tonight — Hero Cards ─────────────────────────────
    # Prominent hero section so quick-picks users see the best bets
    # immediately without scrolling through filters and card grids.
    _hero_pool = [
        r for r in displayed_results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and r.get("tier", "Bronze") in {"Platinum", "Gold"}
        and float(r.get("confidence_score", 0)) >= 65
    ]
    _hero_pool = sorted(
        _hero_pool,
        key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )[:3]
    if _hero_pool:
        # ── Enrich hero pool with player_id for headshots ─────────────
        # Picks loaded from the DB lack player_id; look it up from players_data
        # using a name-keyed dict so the NBA CDN headshot URL can be resolved.
        _hero_players_data = locals().get("players_data") or globals().get("players_data")
        if not _hero_players_data:
            try:
                from data.data_manager import load_players_data as _lpd_hero
                _hero_players_data = _lpd_hero() or []
            except Exception:
                _hero_players_data = []
        if _hero_players_data and any(not r.get("player_id") for r in _hero_pool):
            _pid_lookup = {
                str(p.get("name", "")).lower(): str(p.get("player_id", ""))
                for p in _hero_players_data
                if p.get("player_id")
            }
            for _hp in _hero_pool:
                if not _hp.get("player_id"):
                    _hp["player_id"] = _pid_lookup.get(
                        str(_hp.get("player_name", "")).lower(), ""
                    )

        # Try to attach Joseph short takes to hero picks
        _joseph_results = st.session_state.get("joseph_results", [])
        if _joseph_results:
            _joseph_lookup = {
                (jr.get("player_name", ""), (jr.get("stat_type", "") or "").lower()): jr
                for jr in _joseph_results
            }
            for _hp in _hero_pool:
                _jk = (_hp.get("player_name", ""), (_hp.get("stat_type", "") or "").lower())
                _jr = _joseph_lookup.get(_jk)
                if _jr:
                    _hp["joseph_short_take"] = _jr.get("joseph_short_take", "") or _jr.get("joseph_take", "")

        st.markdown(
            _render_hero_section_html(_hero_pool),
            unsafe_allow_html=True,
        )

    # ── Quick-select buttons ───────────────────────────────────
    _qb_col1, _qb_col2, _qb_col3 = st.columns([1, 1, 2])
    with _qb_col1:
        if st.button("💎 Select All Platinum", help="Add all Platinum tier picks to Entry Builder"):
            _plat_picks = [
                r for r in displayed_results
                if r.get("tier") == "Platinum"
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
            ]
            _existing_keys = {p.get("key") for p in st.session_state.get("selected_picks", [])}
            _added = 0
            for r in _plat_picks:
                _stat     = r.get("stat_type", "").lower()
                _line     = r.get("line", 0)
                _dir      = r.get("direction", "OVER")
                _pick_key = f"{r.get('player_name', '')}_{_stat}_{_line}_{_dir}"
                if _pick_key not in _existing_keys:
                    st.session_state.setdefault("selected_picks", []).append({
                        "key":             _pick_key,
                        "player_name":     r.get("player_name", ""),
                        "stat_type":       _stat,
                        "line":            _line,
                        "direction":       _dir,
                        "confidence_score": r.get("confidence_score", 0),
                        "tier":            r.get("tier", "Platinum"),
                        "tier_emoji":      "💎",
                        "platform":        r.get("platform", ""),
                        "edge_percentage": r.get("edge_percentage", 0),
                    })
                    _added += 1
            if _added:
                st.toast(f"✅ Added {_added} Platinum pick(s).")
            else:
                st.info("All Platinum picks already added.")
    with _qb_col2:
        if st.button("🥇 Select All Gold+", help="Add all Gold and Platinum tier picks to Entry Builder"):
            _gold_picks = [
                r for r in displayed_results
                if r.get("tier") in ("Platinum", "Gold")
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
            ]
            _existing_keys = {p.get("key") for p in st.session_state.get("selected_picks", [])}
            _added = 0
            for r in _gold_picks:
                _stat     = r.get("stat_type", "").lower()
                _line     = r.get("line", 0)
                _dir      = r.get("direction", "OVER")
                _pick_key = f"{r.get('player_name', '')}_{_stat}_{_line}_{_dir}"
                if _pick_key not in _existing_keys:
                    _t_emoji = "💎" if r.get("tier") == "Platinum" else "🥇"
                    st.session_state.setdefault("selected_picks", []).append({
                        "key":             _pick_key,
                        "player_name":     r.get("player_name", ""),
                        "stat_type":       _stat,
                        "line":            _line,
                        "direction":       _dir,
                        "confidence_score": r.get("confidence_score", 0),
                        "tier":            r.get("tier", "Gold"),
                        "tier_emoji":      _t_emoji,
                        "platform":        r.get("platform", ""),
                        "edge_percentage": r.get("edge_percentage", 0),
                    })
                    _added += 1
            if _added:
                st.toast(f"✅ Added {_added} Gold+ pick(s).")
            else:
                st.info("All Gold+ picks already added.")

    if unmatched_count > 0:
        # Deduplicate: same player may have multiple stat types, each flagged separately.
        # Only count and list each unique player name once.
        unmatched_names_deduped = list(dict.fromkeys(
            r.get("player_name", "") for r in _frag_analysis_results
            if not r.get("player_matched", True)
            and not r.get("player_is_out", False)  # exclude confirmed-out players
        ))
        unmatched_unique_count = len(unmatched_names_deduped)
        if unmatched_unique_count > 0:
            _display_names = unmatched_names_deduped[:10]
            _overflow = unmatched_unique_count - len(_display_names)
            _inline = ", ".join(_display_names) + (f" and {_overflow} more" if _overflow > 0 else "")
            st.warning(
                f"⚠️ **{unmatched_unique_count} player(s) not found** in database — "
                + _inline
                + " — results may be less accurate. Run a **Smart Update** on the Smart NBA Data page to refresh roster data."
            )
            if _overflow > 0:
                with st.expander(f"See all {unmatched_unique_count} unmatched players"):
                    st.write(", ".join(unmatched_names_deduped))

    st.divider()

    if not displayed_results:
        st.warning(
            "📭 **No picks match the current filters.** All analyzed props were filtered out. "
            "Try switching to **All picks** above, or loosen the Tier / Bet Classification filters."
        )

    # ============================================================
    # SECTION: Player News Alerts (API-NBA)
    # Show injury/trade/performance news for players in today's slate.
    # ============================================================
    _slate_players = {
        str(r.get("player_name", "")).strip().lower()
        for r in displayed_results
        if r.get("player_name")
    }
    _slate_news: list = []
    for _pname_lower in _slate_players:
        for _news_item in _frag_player_news_lookup.get(_pname_lower, []):
            _slate_news.append(_news_item)
    # Sort by impact (high > medium > low) then by published date
    _imp_order = {"high": 0, "medium": 1, "low": 2}
    _slate_news.sort(key=lambda x: (_imp_order.get(x.get("impact", "low"), 3), x.get("published_at", "")))

    if _slate_news:
        with st.expander(
            f"📰 Player News Alerts — {len(_slate_news)} item(s) for tonight's slate",
            expanded=any(n.get("impact") == "high" for n in _slate_news),
        ):
            for _na in _slate_news[:15]:
                if not _na.get("title"):
                    continue
                st.markdown(
                    _render_news_alert_html(_na),
                    unsafe_allow_html=True,
                )

    # ============================================================
    # SECTION: Market Movement Alerts (Odds API line snapshots)
    # Shows sharp-money / line-movement signals detected during analysis.
    # ============================================================
    _mm_results = [
        r for r in displayed_results
        if r.get("market_movement") and not r.get("player_is_out", False)
    ]
    if _mm_results:
        with st.expander(
            f"📉 Market Movement Alerts — {len(_mm_results)} line shift(s) detected",
            expanded=False,
        ):
            for _mm_r in _mm_results:
                st.markdown(
                    _render_market_movement_html(_mm_r),
                    unsafe_allow_html=True,
                )

    # ============================================================
    # SECTION B: Uncertain Picks — flagged inline in player cards
    # ============================================================
    # Instead of a separate section that duplicates player entries,
    # uncertain picks are now flagged with is_uncertain in their
    # analysis result dict.  The unified player cards display a
    # "⚠️ Uncertain" badge on the affected prop cards inline.
    # A compact summary count is shown here for awareness.
    _uncertain_picks = [
        r for r in _frag_analysis_results
        if r.get("is_uncertain", False)
        and not r.get("player_is_out", False)
    ]
    if _uncertain_picks:
        _unc_names = list(dict.fromkeys(
            r.get("player_name", "Unknown") for r in _uncertain_picks
        ))[:_MAX_UNCERTAIN_NAMES]
        _unc_overflow = len(_uncertain_picks) - len(_unc_names)
        _unc_summary = ", ".join(_html.escape(n) for n in _unc_names)
        if _unc_overflow > 0:
            _unc_summary += f" +{_unc_overflow} more"
        st.markdown(
            f'<div class="qam-uncertain-banner">'
            f'<span class="qam-uncertain-icon">⚠️</span>'
            f'<span class="qam-uncertain-text">'
            f'{len(_uncertain_picks)} uncertain prop(s) with conflicting signals — '
            f'{_unc_summary}'
            f' — flagged inline below</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── ⚡ Quantum Edge Gap (standard-line picks where line deviates ≥ 20% from avg
    #    OR edge_percentage ≥ 20%).
    # OVER: line 20–100% below season avg. UNDER: line 20–100% above avg.
    # Only standard odds_type; exclude goblin / demon.
    _edge_gap_picks = _filter_qeg_picks(displayed_results)
    _edge_gap_picks = _deduplicate_qeg_picks(_edge_gap_picks)
    _edge_gap_picks = sorted(
        _edge_gap_picks,
        key=lambda r: max(abs(r.get("line_vs_avg_pct", 0)), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )

    if _edge_gap_picks:
        st.markdown(_get_qcm_css(), unsafe_allow_html=True)
        st.markdown(
            _render_edge_gap_banner_html(_edge_gap_picks),
            unsafe_allow_html=True,
        )
        st.markdown(
            _render_edge_gap_grouped_html(_edge_gap_picks),
            unsafe_allow_html=True,
        )
        st.divider()

    # ── 🏆 Best Single Bets — mark inline (no separate duplicate cards) ─
    # Instead of rendering separate horizontal cards (which duplicates
    # player entries), we flag the top picks with _is_best_pick so the
    # unified player cards show a "⭐ Top Pick" badge inline.
    _single_bet_pool = [
        r for r in displayed_results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and r.get("tier", "Bronze") in {"Platinum", "Gold"}
        and float(r.get("confidence_score", 0)) >= 70
    ]
    _single_bet_pool = sorted(
        _single_bet_pool,
        key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )[:_MAX_TOP_PICKS]  # Top picks get the badge

    # Flag each top pick in the original results list
    _best_pick_keys: set = set()
    for _sb in _single_bet_pool:
        _bk = (
            _sb.get("player_name", ""),
            (_sb.get("stat_type", "") or "").lower(),
            _sb.get("prop_line", _sb.get("line", 0)),
        )
        _best_pick_keys.add(_bk)
    for _r in displayed_results:
        _rk = (
            _r.get("player_name", ""),
            (_r.get("stat_type", "") or "").lower(),
            _r.get("prop_line", _r.get("line", 0)),
        )
        if _rk in _best_pick_keys:
            _r["_is_best_pick"] = True

    st.divider()

    # ── Quick View / Full Analysis toggle ─────────────────────────
    _qv_col1, _qv_col2 = st.columns([1, 3])
    with _qv_col1:
        _quick_view = st.toggle(
            "⚡ Quick View",
            value=st.session_state.get("qam_quick_view", False),
            key="_qam_quick_view_toggle",
            help="Compact one-line-per-pick table for fast scanning",
        )
        st.session_state["qam_quick_view"] = _quick_view
    with _qv_col2:
        if _quick_view:
            st.caption("Showing compact table — toggle off for full card analysis")
        else:
            st.caption("Showing full analysis cards — toggle on for quick scan")

    if _quick_view:
        # ── Quick View: compact table ──────────────────────────────
        _qv_html = _render_quick_view_html(displayed_results, _best_pick_keys)
        st.markdown(_qv_html, unsafe_allow_html=True)

    else:
        # ── Full Analysis view ─────────────────────────────────────

        # ── 🎯 Strongly Suggested Parlays (at TOP for maximum visibility) ─
        # Grouped by game with horizontal scrolling for each matchup
        strategy_entries = _build_entry_strategy(displayed_results)
        if strategy_entries:
            # Group parlays by game matchup
            _parlays_by_game = {}
            for entry in strategy_entries:
                # Extract teams from raw_picks
                teams = set()
                for pick in entry.get("raw_picks", []):
                    team = (pick.get("player_team") or pick.get("team") or "").upper().strip()
                    if team:
                        teams.add(team)
                
                # Use teams as game key; if no teams found, use "Mixed" as fallback
                if len(teams) >= 2:
                    game_key = " vs ".join(sorted(teams))
                elif len(teams) == 1:
                    game_key = list(teams)[0]
                else:
                    game_key = "Mixed"
                
                if game_key not in _parlays_by_game:
                    _parlays_by_game[game_key] = []
                _parlays_by_game[game_key].append(entry)
            
            # Render header and game-by-game sections with horizontal scrolling
            st.markdown(
                _render_parlays_header_html(),
                unsafe_allow_html=True,
            )
            
            # Render each game's parlays in a horizontally scrollable container
            _global_card_idx = 0
            for _game_idx, (_game_key, _game_parlays) in enumerate(_parlays_by_game.items()):
                _game_cards = ""
                for _i, entry in enumerate(_game_parlays):
                    _game_cards += _render_parlay_card_html(entry, _global_card_idx)
                    _global_card_idx += 1
                
                # Horizontal scroll container for this game's parlays
                _game_html = (
                    f'<div class="qam-game-section">'
                    f'  <div class="qam-game-title">{_html.escape(_game_key)}</div>'
                    f'  <div class="qam-parlay-scroll-container">'
                    f'    <div class="qam-parlay-container">{_game_cards}</div>'
                    f'  </div>'
                    f'</div>'
                )
                _parlay_css = _get_qcm_css() + """
                <style>
                .qam-game-section {
                    margin: 16px 0;
                    border-radius: 8px;
                    background: rgba(255,255,255,0.02);
                    padding: 12px;
                }
                .qam-game-title {
                    font-weight: 600;
                    font-size: 14px;
                    margin-bottom: 8px;
                    color: #a78bfa;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .qam-parlay-scroll-container {
                    overflow-x: auto;
                    overflow-y: hidden;
                    -webkit-overflow-scrolling: touch;
                    padding-bottom: 8px;
                    scrollbar-width: thin;
                    scrollbar-color: rgba(167,139,250,0.4) rgba(255,255,255,0.05);
                }
                .qam-parlay-scroll-container::-webkit-scrollbar {
                    height: 6px;
                }
                .qam-parlay-scroll-container::-webkit-scrollbar-track {
                    background: rgba(255,255,255,0.02);
                    border-radius: 3px;
                }
                .qam-parlay-scroll-container::-webkit-scrollbar-thumb {
                    background: rgba(167,139,250,0.4);
                    border-radius: 3px;
                }
                .qam-parlay-scroll-container::-webkit-scrollbar-thumb:hover {
                    background: rgba(167,139,250,0.6);
                }
                </style>
                """
                _render_card_native(_parlay_css + _game_html)
        else:
            st.info("Not enough high-edge picks to build parlay combinations. Lower the edge threshold or add more props.")

    # ── Team Breakdown (when single game) ────────────────────────
    if not _quick_view and len(_frag_todays_games) == 1:
        g = _frag_todays_games[0]
        home_t = g.get("home_team", "")
        away_t = g.get("away_team", "")
        if home_t and away_t:
            with st.expander("🏀 Team Matchup Breakdown"):
                tc1, tc2 = st.columns(2)
                from styles.theme import get_team_colors
                home_color, _ = get_team_colors(home_t)
                away_color, _ = get_team_colors(away_t)
                hw = g.get("home_wins"); hl = g.get("home_losses")
                aw = g.get("away_wins"); al = g.get("away_losses")
                home_record = f"{hw}-{hl}" if hw is not None and hl is not None and (hw > 0 or hl > 0) else "N/A"
                away_record = f"{aw}-{al}" if aw is not None and al is not None and (aw > 0 or al > 0) else "N/A"

                home_players = [
                    r.get("player_name", "") for r in _frag_analysis_results
                    if r.get("player_team") == home_t and not r.get("player_is_out", False)
                ][:5]
                away_players = [
                    r.get("player_name", "") for r in _frag_analysis_results
                    if r.get("player_team") == away_t and not r.get("player_is_out", False)
                ][:5]

                with tc1:
                    st.markdown(
                        get_qds_team_card_html(
                            team_name=home_t,
                            team_abbrev=home_t,
                            record=home_record,
                            stats=[
                                {"label": "Game Total", "value": str(g.get("game_total", "N/A"))},
                                {"label": "Spread",     "value": str(g.get("vegas_spread", "N/A"))},
                            ],
                            key_players=home_players,
                            team_color=home_color,
                        ),
                        unsafe_allow_html=True,
                    )
                with tc2:
                    st.markdown(
                        get_qds_team_card_html(
                            team_name=away_t,
                            team_abbrev=away_t,
                            record=away_record,
                            stats=[
                                {"label": "Game Total", "value": str(g.get("game_total", "N/A"))},
                                {"label": "Spread",     "value": str(g.get("vegas_spread", "N/A"))},
                            ],
                            key_players=away_players,
                            team_color=away_color,
                        ),
                        unsafe_allow_html=True,
                    )

    # ── Player Analysis Cards ────────────────────────────────────
    # Compact expandable rows: click to reveal full prop analysis.
    if not _quick_view:
        _active_results = [r for r in displayed_results if not r.get("player_is_out", False)]
        _grouped = _group_props(_active_results, _frag_players_data, _frag_todays_games)

        if _grouped:
            # Inject QCM CSS for matchup card styling
            st.markdown(_get_qcm_css(), unsafe_allow_html=True)
            st.markdown(
                '<h3 style="font-family:\'Orbitron\',sans-serif;color:#00C6FF;'
                'margin-bottom:8px;">🃏 Quantum Analysis Matrix</h3>'
                '<p style="color:#94A3B8;font-size:0.82rem;margin-bottom:12px;">'
                'Click any player to expand and view their full prop analysis.</p>',
                unsafe_allow_html=True,
            )

            # Build team -> game-matchup label mapping
            _team_to_game: dict[str, str] = {}
            _game_meta_map: dict[str, dict] = {}
            for _g in (_frag_todays_games or []):
                _ht = (_g.get("home_team") or "").upper().strip()
                _at = (_g.get("away_team") or "").upper().strip()
                if _ht and _at:
                    _matchup_label = f"{_at} @ {_ht}"
                    _team_to_game[_ht] = _matchup_label
                    _team_to_game[_at] = _matchup_label
                    _game_meta_map[_matchup_label] = _g

            # Group players by game matchup
            _game_groups: dict[str, dict[str, dict]] = {}
            _no_game = "Other"
            for _pname, _pdata in _grouped.items():
                _vitals_team = (_pdata.get("vitals") or {}).get("team", "") or ""
                # "N/A" is returned when enrich_player_data can't find the player —
                # treat it as missing and fall back to the raw prop team fields.
                if _vitals_team.upper().strip() in ("", "N/A", "NA"):
                    _vitals_team = ""
                _pteam = (
                    _vitals_team
                    or (_pdata["props"][0].get("player_team", "") if _pdata.get("props") else "")
                    or (_pdata["props"][0].get("team", "") if _pdata.get("props") else "")
                ).upper().strip()
                _game_label = _team_to_game.get(_pteam, _no_game)
                _game_groups.setdefault(_game_label, {})[_pname] = _pdata

            # Render each game group
            for _game_idx, (_game_label, _game_players) in enumerate(_game_groups.items()):
                _gp_count = len(_game_players)
                _gp_prop_count = sum(len(d.get("props", [])) for d in _game_players.values())

                _gm = _game_meta_map.get(_game_label)
                if _gm and _game_label != _no_game:
                    _mc_ht = (_gm.get("home_team") or "").upper().strip()
                    _mc_at = (_gm.get("away_team") or "").upper().strip()
                    _hw = _gm.get("home_wins"); _hl = _gm.get("home_losses")
                    _aw = _gm.get("away_wins"); _al = _gm.get("away_losses")
                    _mc_h_rec = f"{_hw}-{_hl}" if _hw is not None and _hl is not None and (_hw > 0 or _hl > 0) else ""
                    _mc_a_rec = f"{_aw}-{_al}" if _aw is not None and _al is not None and (_aw > 0 or _al > 0) else ""
                    st.markdown(
                        _render_game_matchup_card_html(
                            away_team=_mc_at,
                            home_team=_mc_ht,
                            away_record=_mc_a_rec,
                            home_record=_mc_h_rec,
                            n_players=_gp_count,
                            n_props=_gp_prop_count,
                        ),
                        unsafe_allow_html=True,
                    )

                # Render player cards as horizontal scroll rows (one row per team — no collapsible).
                _team_lbl_css = (
                    'font-size:0.78rem;font-weight:700;color:#94A3B8;'
                    'text-transform:uppercase;letter-spacing:0.08em;margin:10px 0 4px;'
                )
                # Group players by actual team from player data (robust — no reliance on meta match)
                _teams_in_group: dict = {}
                for _pn, _pd in _game_players.items():
                    _vt = (_pd.get("vitals") or {}).get("team", "") or ""
                    if _vt.upper().strip() in ("", "N/A", "NA"):
                        _vt = ""
                    _pt = (
                        _vt
                        or (_pd["props"][0].get("player_team", "") if _pd.get("props") else "")
                        or (_pd["props"][0].get("team", "") if _pd.get("props") else "")
                    ).upper().strip() or "UNK"
                    _teams_in_group.setdefault(_pt, {})[_pn] = _pd

                # Order: away team first, home team second (when game meta known), then others alpha
                _t_order: list = []
                if _gm and _game_label != _no_game:
                    for _t_pref in [_mc_at, _mc_ht]:
                        if _t_pref in _teams_in_group:
                            _t_order.append(_t_pref)
                for _t in sorted(_teams_in_group.keys()):
                    if _t not in _t_order:
                        _t_order.append(_t)

                for _t in _t_order:
                    _t_players = _teams_in_group[_t]
                    st.markdown(f'<div style="{_team_lbl_css}">{_t}</div>', unsafe_allow_html=True)
                    _render_card_native(_compile_cards_flat(_t_players))

    # Show OUT players in a separate collapsed section
    _out_display = [r for r in displayed_results if r.get("player_is_out", False)]
    if _out_display:
        _out_grouped = _group_props(_out_display, _frag_players_data, _frag_todays_games)
        if _out_grouped:
            st.markdown(
                '<div style="font-size:0.78rem;color:#64748b;margin:12px 0 4px;">'
                '⚠️ OUT / Inactive Players</div>',
                unsafe_allow_html=True,
            )
            _render_card_native(_compile_player_cards(_out_grouped))

    # ── Final Verdict ─────────────────────────────────────────────
    st.divider()
    with st.expander("🏁 Final Verdict", expanded=True):
        top_picks_for_verdict = [
            r for r in displayed_results
            if not r.get("player_is_out", False)
            and not r.get("should_avoid", False)
        ][:3]

        if top_picks_for_verdict:
            top_names  = ", ".join(r.get("player_name", "") for r in top_picks_for_verdict)
            avg_conf   = round(
                sum(r.get("confidence_score", 0) for r in top_picks_for_verdict)
                / len(top_picks_for_verdict), 1
            )
            summary    = (
                f"The Quantum Matrix Engine 5.6 identified {len(top_picks_for_verdict)} high-confidence "
                f"props led by {top_names}, with a composite confidence score of {avg_conf}/100. "
                f"Layer 5 injury validation and Quantum Matrix Engine 5.6 simulation align on these selections."
            )
        else:
            summary = (
                "No high-confidence picks were identified in the current analysis. "
                "Review injury status updates and consider adjusting your prop list."
            )

        recs = [
            "Focus on Platinum and Gold tier picks for maximum confidence.",
            "Avoid props flagged on the avoid list or with active GTD designations.",
            "Use the Entry Strategy Matrix to build 2-, 3-, or 5-leg combos.",
            "Confirm injury status via 📡 Smart NBA Data before placing bets.",
        ]
        st.markdown(
            get_qds_final_verdict_html(summary, recs),
            unsafe_allow_html=True,
        )

    # ── Floating selected-picks counter ──────────────────────────
    selected_count = len(st.session_state.get("selected_picks", []))
    if selected_count > 0:
        st.success(
            f"✅ {selected_count} pick(s) selected for Entry Builder → "
            "Go to 🧬 Entry Builder to build your entry!"
        )

    if st.session_state.get("selected_picks"):
        if st.button("🗑️ Clear Selected Picks"):
            st.session_state["selected_picks"] = []
            st.toast("🗑️ Selected picks cleared.")


_render_results_fragment()

# ============================================================
# END SECTION: Display Analysis Results
# ============================================================
