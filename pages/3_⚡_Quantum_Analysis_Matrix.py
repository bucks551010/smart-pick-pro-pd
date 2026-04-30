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

# ── Auth gate import (call deferred until after st.set_page_config) ──────────
try:
    from utils.auth_gate import require_login as _require_login
except ImportError:
    _require_login = None

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

# ── Auth gate (must come after set_page_config) ──────────────────────
if _require_login is not None and not _require_login():
    st.stop()

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

# ── Stale-pick guard: clear explicit prior-day picks restored from page_state ──
# _auto_restore_page_state() (called inside inject_joseph_floating above) can
# load slate-worker picks with an explicit prior-day pick_date when the SQLite
# page_state was saved across the midnight boundary.  Clear them here before the
# session-bridge block at line ~399 so QAM never silently renders yesterday's slate.
_qam_restored_ar = st.session_state.get("analysis_results")
if _qam_restored_ar and isinstance(_qam_restored_ar, list) and _qam_restored_ar:
    try:
        from tracking.database import _nba_today_iso as _qam_today_fn
        _qam_today = _qam_today_fn()
        _qam_first_pd = str(_qam_restored_ar[0].get("pick_date") or "")[:10]
        if _qam_first_pd and _qam_first_pd < _qam_today:
            for _k in ("analysis_results", "todays_games", "selected_picks"):
                st.session_state.pop(_k, None)
    except Exception:
        pass

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

# ── FAST PATH: load from analyzed_picks.json (<100 ms) ───────────────────────
# The scheduler writes cache/analyzed_picks.json after every successful run.
# Reading a local file is orders of magnitude faster than a DB round-trip, so
# we try this path first and skip the entire DB session-bridge below if the
# file exists and is dated today.  The DB bridge still runs as a fallback when
# the file is absent or stale (e.g. first deploy, cache cleared, different day).
if not st.session_state.get("analysis_results"):
    try:
        import json as _qam_json
        from pathlib import Path as _qam_Path
        _qam_cache_file = (
            _qam_Path(__file__).resolve().parent.parent / "cache" / "analyzed_picks.json"
        )
        if _qam_cache_file.exists():
            _qam_cache = _qam_json.loads(_qam_cache_file.read_text(encoding="utf-8"))
            from tracking.database import _nba_today_iso as _qam_today_fn
            if _qam_cache.get("date") == _qam_today_fn():
                _qam_file_picks = [
                    r for r in (_qam_cache.get("picks") or [])
                    if str(r.get("team", "")).strip()
                ]
                if _qam_file_picks:
                    st.session_state["analysis_results"] = _qam_file_picks
                    st.session_state["_qam_db_restored"] = True
                    st.session_state["_qam_cache_source"] = "file"
                    _logger.info(
                        "QAM fast-path: %d picks loaded from analyzed_picks.json in <100 ms.",
                        len(_qam_file_picks),
                    )
    except Exception as _qam_fp_err:
        _logger.debug("QAM file fast-path failed (non-fatal): %s", _qam_fp_err)
# ── END FAST PATH ─────────────────────────────────────────────────────────────

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
            get_slate_picks_for_today as _get_slate_today,
            _nba_today_iso as _nba_today,
        )
        _qam_sid_param = st.query_params.get("sid")
        if _qam_sid_param:
            _saved_session = _load_session_by_id(int(_qam_sid_param))
        else:
            _saved_session = _load_session()
        if _saved_session and _saved_session.get("analysis_results"):
            _raw_ar = _saved_session["analysis_results"] or []
            _games_loaded = (
                _saved_session.get("todays_games")
                or st.session_state.get("todays_games")
                or []
            )
            # Prefer the canonical today-only slate (deduped + 5/player capped)
            # over the raw analysis_results JSON, which can include stale
            # entries from earlier worker runs on the same NBA date.
            _today_iso = _nba_today()
            _slate_today = []
            try:
                _slate_today = _get_slate_today() or []
            except Exception:
                _slate_today = []
            # Only merge the saved session with today's slate when the session
            # date is KNOWN and matches today.  An unknown date (None/"") means
            # the session is from a stale/un-dated run — merging it would let
            # old opponent data bleed into today's picks and trigger the opponent
            # filter below, wiping all DB-sourced slate picks (which have no
            # opponent column).
            _saved_date = (_saved_session.get("analysis_date") or "")[:10]
            if _slate_today and _saved_date and _saved_date == _today_iso:
                # Build a slate index so we can carry over the rich analysis
                # fields from AR (confidence_score, std_devs, opponent, etc.)
                # but constrained to the deduped/capped set.
                def _key(p):
                    return (
                        str(p.get("player_name", "")).lower().strip(),
                        str(p.get("stat_type", "")).lower().strip(),
                        str(p.get("direction", "")).upper().strip(),
                        str(p.get("platform", "")).lower().strip(),
                        float(p.get("prop_line") or p.get("line") or 0),
                    )
                _ar_by_key = {}
                for r in _raw_ar:
                    _ar_by_key.setdefault(_key(r), r)
                _merged = []
                for sp in _slate_today:
                    k = _key(sp)
                    if k in _ar_by_key:
                        # Merge: slate row wins on identity, AR fills extras
                        m = dict(_ar_by_key[k])
                        m.update({kk: vv for kk, vv in sp.items() if vv is not None})
                        _merged.append(m)
                    else:
                        _merged.append(sp)
                _raw_ar = _merged
            elif _slate_today:
                # Session date unknown or stale — use today's slate directly
                # without merging so stale opponent/game data doesn't bleed in.
                _raw_ar = list(_slate_today)
            # Filter synthetic game-total props ONLY when the MAJORITY of picks
            # carry opponent metadata (≥50%).  Requiring a majority prevents a
            # handful of stale-session picks with opponent from accidentally
            # wiping hundreds of DB-sourced slate picks that have no opponent.
            _picks_with_opp = sum(1 for r in _raw_ar if r.get("opponent"))
            _any_has_opponent_ar = _picks_with_opp > 0 and _picks_with_opp >= len(_raw_ar) * 0.5
            if _games_loaded and _any_has_opponent_ar:
                _raw_ar = [r for r in _raw_ar if r.get("opponent", "")]
            # Always filter out game-total rows (empty team) — these are
            # matchup-level props like "ATL @ NYK Total" that have no team
            # and don't belong in the player-card matrix.
            _raw_ar = [r for r in _raw_ar if str(r.get("team", "")).strip()]
            st.session_state["analysis_results"] = _raw_ar
            # ── Validate session's todays_games against today's slate teams ──
            # The worker may store yesterday's games if the ETL DB hasn't been
            # updated yet (common at 4–8 AM ET before games are in the DB).
            # Detect staleness: if no session-game team appears in the slate,
            # the games are stale — re-fetch fresh or parse from game-total rows.
            _session_saved_games = _saved_session.get("todays_games") or []
            if not st.session_state.get("todays_games"):
                _slate_teams_set = {
                    str(r.get("team", "")).upper().strip()
                    for r in _raw_ar if str(r.get("team", "")).strip()
                }
                _session_game_teams: set = set()
                for _sg in _session_saved_games:
                    for _gk in ("home_team", "away_team"):
                        _t = str(_sg.get(_gk, "")).upper().strip()
                        if _t:
                            _session_game_teams.add(_t)
                _games_stale = bool(_session_game_teams) and not (_session_game_teams & _slate_teams_set)
                if _games_stale or not _session_saved_games:
                    # Session games are stale — try to get fresh game list
                    _fresh_games: list = []
                    try:
                        from data.nba_data_service import get_todays_games as _get_fresh_games
                        _candidate_games = _get_fresh_games() or []
                        # Only accept if teams overlap with today's picks
                        _candidate_teams: set = set()
                        for _cg in _candidate_games:
                            for _gk in ("home_team", "away_team"):
                                _t = str(_cg.get(_gk, "")).upper().strip()
                                if _t:
                                    _candidate_teams.add(_t)
                        if _candidate_teams & _slate_teams_set:
                            _fresh_games = _candidate_games
                    except Exception:
                        pass
                    # If live data still stale, parse matchups from game-total rows
                    # in the raw slate (e.g. player_name="ATL @ NYK Total", team="")
                    if not _fresh_games:
                        _seen_mu: set = set()
                        for _r in _slate_today:
                            _pn = str(_r.get("player_name", ""))
                            _rt = str(_r.get("team", "")).strip()
                            if not _rt and " @ " in _pn:
                                _mu = _pn.replace(" Total", "").strip()
                                if _mu not in _seen_mu:
                                    _seen_mu.add(_mu)
                                    _pts = _mu.split(" @ ")
                                    if len(_pts) == 2:
                                        _fresh_games.append({
                                            "away_team": _pts[0].strip().upper(),
                                            "home_team": _pts[1].strip().upper(),
                                        })
                    if _fresh_games:
                        st.session_state["todays_games"] = _fresh_games
                    # else: leave todays_games unset — better than stale games
                else:
                    st.session_state["todays_games"] = _session_saved_games
            if _saved_session.get("selected_picks") and not st.session_state.get("selected_picks"):
                _raw_sel = _saved_session["selected_picks"] or []
                _any_has_opponent_sel = any(p.get("opponent") for p in _raw_sel)
                if _any_has_opponent_sel:
                    _filtered_sel = [p for p in _raw_sel if p.get("opponent", "")]
                else:
                    _filtered_sel = list(_raw_sel)
                st.session_state["selected_picks"] = _filtered_sel
            # Record the timestamp so the UI can show when the session was saved
            st.session_state["_analysis_session_reloaded_at"] = _saved_session.get("analysis_timestamp", "")
            # Prevent the auto-run guard from re-triggering the engine when we
            # already have results from the DB.
            st.session_state["_qam_db_restored"] = True
    except Exception:
        pass  # Non-fatal — just show empty state

# ── Final safety net: if analysis_results is STILL empty after rehydrate
# (e.g. fresh visit with no saved session, or rehydrate exception), seed
# directly from the canonical today-only deduped slate.  This guarantees the
# QAM page always renders today's picks even when there's no saved session.
if not st.session_state.get("analysis_results"):
    try:
        from tracking.database import get_slate_picks_for_today as _qam_seed_slate
        _qam_seed = _qam_seed_slate() or []
        # Filter game-total rows (empty team) before seeding
        _qam_seed = [r for r in _qam_seed if str(r.get("team", "")).strip()]
        if _qam_seed:
            st.session_state["analysis_results"] = _qam_seed
            st.session_state["_qam_db_restored"] = True
    except Exception as _qam_db_err:  # best-effort — log but don't crash
        _logger.debug("QAM DB session restore failed: %s", _qam_db_err)

# ── Seed todays_games if still missing after rehydrate ───────────────────────
if not st.session_state.get("todays_games") and st.session_state.get("analysis_results"):
    try:
        from data.nba_data_service import get_todays_games as _qam_games_seed
        _qam_games = _qam_games_seed() or []
        if _qam_games:
            # Validate against current picks
            _ar_teams = {
                str(r.get("team", "")).upper().strip()
                for r in st.session_state["analysis_results"]
                if str(r.get("team", "")).strip()
            }
            _gm_teams: set = set()
            for _qg in _qam_games:
                for _gk in ("home_team", "away_team"):
                    _t = str(_qg.get(_gk, "")).upper().strip()
                    if _t:
                        _gm_teams.add(_t)
            if _gm_teams & _ar_teams:
                st.session_state["todays_games"] = _qam_games
    except Exception as _qam_seed_err:  # best-effort — log but don't crash
        _logger.debug("QAM todays_games seed failed: %s", _qam_seed_err)

# ── Auto-populate selected_picks with top-tier picks if empty.
# Covers the case where the analysis session was saved without picks
# (e.g. a UI-triggered run that didn't reach the selection step) and
# the case where the worker saved an empty selected_picks list.
if not st.session_state.get("selected_picks") and st.session_state.get("analysis_results"):
    _qam_ar = st.session_state["analysis_results"]
    _any_has_opp_qa = any(r.get("opponent") for r in _qam_ar)
    _qam_auto = [
        r for r in _qam_ar
        if r.get("tier", "").lower() in ("platinum", "gold", "silver")
        and not r.get("player_is_out", False)
        and not r.get("should_avoid", False)
        and (not _any_has_opp_qa or r.get("opponent", ""))
    ][:20]
    if _qam_auto:
        st.session_state["selected_picks"] = _qam_auto

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

# ── QAM is scheduler-driven: all simulation runs in slate_worker (background). ──
# No auto-trigger here — the Refresh Picks button reads precomputed results only.
_qam_auto_triggered = False  # kept for downstream compat; never set True

run_analysis = st.button(
    "🔄 Refresh Picks",
    type="primary",
    help="Reload the latest precomputed picks from the scheduler (< 1 s)",
)

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
    # ── Read-only refresh: reload precomputed picks from the scheduler DB ──
    # All simulation runs in slate_worker.py (background scheduler).
    # Try the local cache file first (< 100ms); fall back to a DB query.
    _prev_results = st.session_state.get("analysis_results") or []
    _refresh_picks: list = []
    # 1️⃣ Try cache file (fastest path — local file read, no DB round-trip)
    try:
        import json as _ref_json
        from pathlib import Path as _ref_Path
        _ref_cache = _ref_Path(__file__).resolve().parent.parent / "cache" / "analyzed_picks.json"
        if _ref_cache.exists():
            _ref_data = _ref_json.loads(_ref_cache.read_text(encoding="utf-8"))
            from tracking.database import _nba_today_iso as _ref_today_fn
            if _ref_data.get("date") == _ref_today_fn():
                _refresh_picks = [
                    r for r in (_ref_data.get("picks") or [])
                    if str(r.get("team", "")).strip()
                ]
    except Exception as _ref_file_err:
        _logger.debug("Refresh file read failed (non-fatal): %s", _ref_file_err)
    # 2️⃣ Fall back to DB query when file path unavailable or stale
    if not _refresh_picks:
        try:
            from tracking.database import get_slate_picks_for_today as _qam_refresh_today
            _raw_refresh = _qam_refresh_today() or []
            _refresh_picks = [r for r in _raw_refresh if str(r.get("team", "")).strip()]
        except Exception as _refresh_err:
            st.error(f"⚠️ Could not load picks from scheduler: {_refresh_err}")
    if _refresh_picks:
        st.session_state["analysis_results"] = _refresh_picks
        st.session_state["_qam_db_restored"] = True
        st.session_state["_qam_cache_source"] = "refresh"
        st.session_state.pop("_qam_analysis_requested", None)
        st.session_state.pop("_analysis_session_reloaded_at", None)
        _logger.info("QAM refresh: loaded %d precomputed picks from scheduler.", len(_refresh_picks))
    else:
        # No picks yet — restore previous results if any so the page stays populated
        if _prev_results:
            st.session_state["analysis_results"] = _prev_results
        st.info(
            "⏳ **No picks available yet for today.** "
            "The scheduler runs a full Quantum analysis automatically every 30 minutes. "
            "Check back shortly."
        )

    # Placeholder list — used by display code below that checks len()
    analysis_results_list = st.session_state.get("analysis_results", [])

# ============================================================
# END SECTION: Analysis Runner
# ============================================================

# ── Auto-retry notice: if user navigated away during analysis ──
if (
    st.session_state.get("_qam_analysis_requested")
    and not st.session_state.get("analysis_results")
    and not run_analysis
):
    st.info(
        "⏳ No picks loaded. Click **🔄 Refresh Picks** above to load the latest "
        "precomputed results from the scheduler."
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
@st.fragment
def _render_platform_ai_picks():
    """Render Platform AI Picks only after analysis is fully complete.

    Wrapped in a fragment so it renders as an atomic block and is never
    partially visible during a running analysis.  Guards against showing
    stale results while a new analysis is in progress.
    """
    # Never render during an in-progress analysis run.
    if st.session_state.get("_qam_analysis_requested", False):
        return

    _ar = st.session_state.get("analysis_results", [])
    if not _ar:
        return

    _plat_ai_pool = [
        r for r in _ar
        if r.get("platform", "").strip()
        and not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and float(r.get("confidence_score", 0)) >= 60
    ]
    _plat_ai_pool = sorted(
        _plat_ai_pool,
        key=lambda r: float(r.get("confidence_score", 0)),
        reverse=True,
    )[:8]
    if not _plat_ai_pool:
        return

    _pd_outer = []
    try:
        from data.data_manager import load_players_data as _lpd_outer
        _pd_outer = _lpd_outer() or []
    except Exception:
        pass
    if _pd_outer and any(not r.get("player_id") for r in _plat_ai_pool):
        _pid_lookup = {
            str(p.get("name", "")).lower(): str(p.get("player_id", ""))
            for p in _pd_outer
            if p.get("player_id")
        }
        for _op in _plat_ai_pool:
            if not _op.get("player_id"):
                _op["player_id"] = _pid_lookup.get(
                    str(_op.get("player_name", "")).lower(), ""
                )

    st.markdown(
        _render_platform_picks_html(_plat_ai_pool),
        unsafe_allow_html=True,
    )

_render_platform_ai_picks()
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

    _frag_current_props = load_props_from_session(st.session_state)
    _frag_minimum_edge = st.session_state.get("minimum_edge_threshold", 5.0)
    _frag_todays_games = st.session_state.get("todays_games", [])
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
    _qeg_teams = {
        t
        for g in st.session_state.get("todays_games", [])
        for t in (g.get("home_team", ""), g.get("away_team", ""))
        if t
    }
    _edge_gap_picks = _filter_qeg_picks(displayed_results, todays_teams=_qeg_teams or None)
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
        # Rendered natively via st.html() so content is part of the normal
        # page flow — no iframe to capture scroll events on desktop.
        strategy_entries = _build_entry_strategy(displayed_results)
        if strategy_entries:
            st.markdown(
                _render_parlays_header_html(),
                unsafe_allow_html=True,
            )
            _parlay_cards = "".join(
                _render_parlay_card_html(entry, _i)
                for _i, entry in enumerate(strategy_entries)
            )
            _parlay_html = (
                f'<div class="qam-parlay-container">{_parlay_cards}</div>'
            )
            _parlay_css = _get_qcm_css()
            _render_card_native(_parlay_css + _parlay_html)
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
            def _extract_player_team(pdata):
                """Return the player's team abbreviation, skipping sentinel values like N/A."""
                for _src in (
                    (pdata.get("vitals") or {}).get("team", ""),
                    pdata["props"][0].get("player_team", "") if pdata.get("props") else "",
                    pdata["props"][0].get("team", "") if pdata.get("props") else "",
                ):
                    _t = str(_src).upper().strip()
                    if _t and _t != "N/A":
                        return _t
                return ""

            for _pname, _pdata in _grouped.items():
                _pteam = _extract_player_team(_pdata)
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
                if _gm and _game_label != _no_game:
                    # Split players into away-team row and home-team row
                    _away_row: dict = {}
                    _home_row: dict = {}
                    _other_row: dict = {}
                    for _pn, _pd in _game_players.items():
                        _pt = _extract_player_team(_pd)
                        if _pt == _mc_at:
                            _away_row[_pn] = _pd
                        elif _pt == _mc_ht:
                            _home_row[_pn] = _pd
                        else:
                            _other_row[_pn] = _pd
                    if _away_row:
                        st.markdown(f'<div style="{_team_lbl_css}">{_mc_at}</div>', unsafe_allow_html=True)
                        _render_card_native(_compile_cards_flat(_away_row))
                    if _home_row:
                        st.markdown(f'<div style="{_team_lbl_css}">{_mc_ht}</div>', unsafe_allow_html=True)
                        _render_card_native(_compile_cards_flat(_home_row))
                    if _other_row:
                        _render_card_native(_compile_cards_flat(_other_row))
                else:
                    # No game meta — render all players in one flat row
                    st.markdown(
                        f'<div style="{_team_lbl_css}">{_game_label}</div>',
                        unsafe_allow_html=True,
                    )
                    _render_card_native(_compile_cards_flat(_game_players))

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
