# ============================================================
# FILE: pages/11_📈_Bet_Tracker.py
# PURPOSE: Unified Bet Tracker & Model Health hub combining
#          bet logging, auto-resolve, AI picks, performance
#          predictor, daily history, and per-platform views.
# TABS:
#   1. 📊 Model Health  — Overall metrics + win rate by tier/platform/stat
#   2. 📊 AI Picks      — Auto-logged picks from Neural Analysis
#   3. 📋 All Picks     — Every pick the app outputs (complete performance record)
#   4. 🤖 Auto-Resolve  — Get actual stats and mark results
#   5. 📋 My Bets       — Full bets as styled cards
#   6. ➕ Log a Bet     — Manual / analysis-prefilled bet entry
#   7. 🔮 Predictor     — Forward-looking bankroll / ROI forecasts
#   8. 📅 History       — 2-week rolling day-by-day timeline
# CONNECTS TO: tracking/bet_tracker.py, tracking/database.py
# ============================================================

import datetime
import json
import logging
import threading as _threading
import time as _time
import os

import streamlit as st

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

from tracking.bet_tracker import (
    auto_log_analysis_bets,
    auto_resolve_bet_results,
    resolve_all_pending_bets,
    resolve_all_analysis_picks,
    regrade_bets_for_date,
    get_model_performance_stats,
    log_new_bet,
    log_props_to_tracker,
    record_bet_result,
)
from tracking.database import (
    initialize_database,
    load_all_bets,
    load_bets_page,
    count_bets,
    get_bets_summary,
    load_daily_snapshots,
    get_rolling_stats,
    save_daily_snapshot,
    load_all_analysis_picks,
    load_analysis_picks_for_date,
    get_analysis_pick_dates,
    delete_bet,
    update_bet_fields,
    search_bets_by_player,
    load_bets_by_date_range,
    export_bets_csv,
    insert_entry,
    load_all_entries,
    update_entry_result,
    link_bets_to_entry,
    get_entry_legs,
    resolve_entry_from_legs,
    delete_entry,
)
from styles.theme import (
    get_global_css,
    get_qds_css,
    get_education_box_html,
    get_bet_card_css,
    get_bet_card_html,
    get_summary_cards_html,
    get_styled_stats_table_html,
)

# ── Joseph loading screen (shown during resolve operations) ──
try:
    from utils.joseph_loading import joseph_loading_placeholder
    _JOSEPH_LOADING_AVAILABLE = True
except ImportError:
    _JOSEPH_LOADING_AVAILABLE = False

# ── Lazy-loaded optional engine modules ──────────────────────────────────────
get_clv_summary = None
get_tier_accuracy_report = None
validate_model_edge = None
def _get_clv_fns():
    global get_clv_summary, get_tier_accuracy_report, validate_model_edge
    if get_clv_summary is None:
        try:
            from engine.clv_tracker import (
                get_clv_summary as _s,
                get_tier_accuracy_report as _t,
                validate_model_edge as _v,
            )
            get_clv_summary = _s
            get_tier_accuracy_report = _t
            validate_model_edge = _v
        except ImportError:
            get_clv_summary = False
            get_tier_accuracy_report = False
            validate_model_edge = False
    return get_clv_summary if get_clv_summary else None

get_calibration_summary = None
get_isotonic_calibration_curve = None
def _get_calibration_fns():
    global get_calibration_summary, get_isotonic_calibration_curve
    if get_calibration_summary is None:
        try:
            from engine.calibration import (
                get_calibration_summary as _cs,
                get_isotonic_calibration_curve as _ic,
            )
            get_calibration_summary = _cs
            get_isotonic_calibration_curve = _ic
        except ImportError:
            get_calibration_summary = False
            get_isotonic_calibration_curve = False
    return get_calibration_summary if get_calibration_summary else None

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Bet Tracker & Model Health — SmartBetPro NBA",
    page_icon="📈",
    layout="wide",
)

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)
st.markdown(get_bet_card_css(), unsafe_allow_html=True)

from pages.helpers.bet_tracker_helpers import (
    get_calendar_heatmap_html,
    get_achievement_ring_html,
    get_level_badge_html,
)

# ── Joseph M. Smith Floating Widget ───────────────────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating
render_joseph_hero_banner()
st.session_state["joseph_page_context"] = "page_bet_tracker"
inject_joseph_floating()

# ── Premium Gate ───────────────────────────────────────────────
from utils.premium_gate import premium_gate
if not premium_gate("Bet Tracker"):
    st.stop()
# ── End Premium Gate ───────────────────────────────────────────

# Ensure DB is initialised
initialize_database()

# ── Cached bets — loaded once and shared across all tabs (C14) ──
# Avoids 8+ redundant load_all_bets() calls per page render.
@st.cache_data(ttl=30)
def _cached_load_all_bets(limit=10000):
    return load_all_bets(limit=limit)

def _reload_bets():
    """Clear the bet cache so the next access returns fresh data."""
    _cached_load_all_bets.clear()


def _tracker_today_date() -> datetime.date:
    """Return today's date using Bet Tracker's NBA (ET) day boundary."""
    try:
        from tracking.bet_tracker import _nba_today_et
        return _nba_today_et()
    except Exception:
        return datetime.date.today()


def _tracker_today_iso() -> str:
    """Return today's Bet Tracker date as YYYY-MM-DD."""
    return _tracker_today_date().isoformat()


def _date_window_start(scope_label: str):
    """Return inclusive start date for a scope label, or None for all-time."""
    _today = _tracker_today_date()
    if scope_label == "Today":
        return _today
    if scope_label == "Last 7 Days":
        return _today - datetime.timedelta(days=6)
    if scope_label == "Last 30 Days":
        return _today - datetime.timedelta(days=29)
    return None


def _in_bet_date_window(row: dict, scope_label: str, date_key: str = "bet_date") -> bool:
    """Return True when row[date_key] is within the selected scope."""
    _start = _date_window_start(scope_label)
    _today = _tracker_today_date()
    if _start is None:
        return True
    _raw = str(row.get(date_key) or "")[:10]
    try:
        _d = datetime.date.fromisoformat(_raw)
    except ValueError:
        return False
    return _start <= _d <= _today


def _is_ai_auto_bet(row: dict) -> bool:
    """True for Smart Pick Pro auto-logged picks (excludes Joseph/manual)."""
    _source = str(row.get("source") or "").strip().lower()
    _platform = str(row.get("platform") or "").strip().lower()
    _notes = str(row.get("notes") or "").strip().lower()
    _auto = int(row.get("auto_logged", 0) or 0) == 1

    # Hard exclusions first: never classify Joseph or Smart Money rows here.
    if _source == "joseph" or "joseph" in _platform or "joseph" in _notes:
        return False
    if "smart money" in _platform or "smart money" in _notes:
        return False

    if _source in {"qeg_auto", "smart_pick_pro", "smart_pick_pro_platform", "smartpickpro_auto"}:
        return True
    if _platform in {"smartai-auto", "smartauto-ai", "smart pick pro", "smart pick pro platform picks", "smart pick pro platform"}:
        return True
    if (
        _notes.startswith("auto-logged by smartai")
        or _notes.startswith("auto-logged by smart pick pro")
        or _notes.startswith("auto-stored by smart pick pro")
        or _notes.startswith("auto-stored by smartai")
    ):
        return True
    if _notes.startswith("added from platform props"):
        return True

    # Legacy fallback: auto_logged rows that are clearly NOT Joseph/Smart Money.
    # This includes Platform Bets added from sportsbook feeds, which are
    # frequently tagged with source='manual' but still belong in this bucket.
    if _auto:
        return True
    return False


def _is_joseph_bet(row: dict) -> bool:
    """True for Joseph-authored picks across legacy/new tagging."""
    _source = str(row.get("source") or "").strip().lower()
    _platform = str(row.get("platform") or "").strip().lower()
    _notes = str(row.get("notes") or "").strip().lower()
    return (
        _source == "joseph"
        or "joseph" in _platform
        or "joseph" in _notes
    )


def _platform_display_name(platform_value: str) -> str:
    """Normalize platform labels for consistent Bet Tracker naming."""
    _plat = str(platform_value or "").strip()
    _norm = _plat.lower()
    if _norm in {"smartai-auto", "smartauto-ai", "smart pick pro", "smart pick pro platform picks", "smart pick pro platform"}:
        return "Smart Pick Pro Platform Picks"
    return _plat


def _is_pipeline_bet_for_all_picks(row: dict) -> bool:
    """True for bets that should be represented in All Picks."""
    _platform = str(row.get("platform") or "").strip().lower()
    _source = str(row.get("source") or "").strip().lower()
    _auto = int(row.get("auto_logged", 0) or 0) == 1
    return (
        _is_ai_auto_bet(row)
        or _is_joseph_bet(row)
        or (_platform == "smart money" and _auto)
        or (_source in {"qeg_auto", "joseph"})
    )


def _canonical_pick_date(row: dict) -> str:
    return str(row.get("pick_date") or row.get("bet_date") or _tracker_today_iso())[:10]


def _canonical_pick_key(row: dict, *, include_platform: bool = True):
    try:
        _line = str(round(float(row.get("prop_line") or row.get("line") or 0), 2))
    except (TypeError, ValueError):
        _line = "0"

    _base = (
        str(row.get("player_name") or "").strip().lower(),
        str(row.get("stat_type") or "").strip().lower(),
        _line,
        str(row.get("direction") or "").strip().upper(),
        _canonical_pick_date(row),
    )
    if include_platform:
        return _base + (str(row.get("platform") or "").strip().lower(),)
    return _base


def _normalized_bet_type(row: dict) -> str:
    _raw = str(row.get("bet_type") or "").strip().lower()
    _line_category = str(row.get("line_category") or "").strip().lower()
    _notes = str(row.get("notes") or "").strip().lower()

    if "smart money demon" in _notes:
        return "demon"
    if "smart money goblin" in _notes:
        return "goblin"

    if _raw in {"goblin", "demon", "50_50", "standard", "normal", "fantasy", "joseph_pick"}:
        return _raw
    if _line_category in {"goblin", "demon", "50_50"}:
        return _line_category
    if _raw:
        return _raw
    return "standard"


def _bet_type_display_name(bet_type: str) -> str:
    _bt = str(bet_type or "standard").strip().lower()
    return {
        "50_50": "50/50",
        "joseph_pick": "Joseph Pick",
    }.get(_bt, _bt.title())


def _bet_type_sort_key(bet_type: str):
    _order = {
        "goblin": 0,
        "demon": 1,
        "50_50": 2,
        "standard": 3,
        "normal": 4,
        "fantasy": 5,
        "joseph_pick": 6,
    }
    _bt = str(bet_type or "standard").strip().lower()
    return (_order.get(_bt, 99), _bt)


def _scope_history_days(scope_label: str) -> int:
    """Return how much history should be loaded for a scope label."""
    if scope_label == "Today":
        return 1
    if scope_label == "Last 7 Days":
        return 7
    if scope_label == "Last 30 Days":
        return 30
    return 3650


def _build_merged_pick_universe(scope_label: str) -> dict:
    """Build the shared merged pick universe used by Health and All Picks."""
    _history_days = _scope_history_days(scope_label)
    _analysis_all = load_all_analysis_picks(days=_history_days)
    _analysis_scope = [p for p in _analysis_all if _in_bet_date_window(p, scope_label, "pick_date")]

    _all_bets = _cached_load_all_bets(limit=50000)
    _health_side_bets = [b for b in _all_bets if _in_bet_date_window(b, scope_label, "bet_date")]
    _pipeline_candidates = [b for b in _health_side_bets if _is_pipeline_bet_for_all_picks(b)]

    _analysis_identity_keys = {
        _canonical_pick_key(_p, include_platform=False)
        for _p in _analysis_scope
    }

    _pipeline_added = []
    _pipeline_skip_ai_overlap = 0
    for _b in _pipeline_candidates:
        _mapped = dict(_b)
        _mapped["pick_date"] = _mapped.get("pick_date") or _mapped.get("bet_date")
        _mapped["prop_line"] = _mapped.get("prop_line", _mapped.get("line"))
        if _is_ai_auto_bet(_mapped) and _canonical_pick_key(_mapped, include_platform=False) in _analysis_identity_keys:
            _pipeline_skip_ai_overlap += 1
            continue
        _pipeline_added.append(_mapped)

    _combined_like = list(_analysis_scope) + _pipeline_added
    _combined_pre_dedup_count = len(_combined_like)
    _seen_keys: set = set()
    _combined: list = []
    for _pick in _combined_like:
        try:
            _line_key = str(round(float(_pick.get("prop_line") or _pick.get("line") or 0), 2))
        except (TypeError, ValueError):
            _line_key = "0"
        _key = (
            (str(_pick.get("player_name") or "")).strip().lower(),
            (str(_pick.get("stat_type") or "")).strip().lower(),
            _line_key,
            (str(_pick.get("direction") or "")).strip().upper(),
            _canonical_pick_date(_pick),
            (str(_pick.get("platform") or "")).strip().lower(),
            (str(_pick.get("source") or "")).strip().lower(),
            (str(_pick.get("tier") or "")).strip().lower(),
        )
        if _key in _seen_keys:
            continue
        _seen_keys.add(_key)
        _combined.append(_pick)

    _dedup_removed = max(0, _combined_pre_dedup_count - len(_combined))

    return {
        "analysis_rows": _analysis_scope,
        "health_side_bets": _health_side_bets,
        "pipeline_candidates": _pipeline_candidates,
        "pipeline_added": _pipeline_added,
        "pipeline_skip_ai_overlap": _pipeline_skip_ai_overlap,
        "combined_pre_dedup_count": _combined_pre_dedup_count,
        "dedup_removed": _dedup_removed,
        "combined": _combined,
    }

# Auto-resolve past bets AND today's completed bets on page load (best-effort, silent).
# Guarded by a session-state flag so this runs at most once per browser session,
# preventing repeated blocking API calls on every Streamlit rerun.
# Uses a background thread so the page renders immediately without blocking.

def _background_auto_resolve():
    """Run auto-resolve in a background thread so the page renders immediately.

    Uses a simple list (``_auto_resolve_messages``) on the session state
    to communicate results back to the main thread.  Only appends to the
    list (atomic in CPython) to avoid race conditions with the main thread.
    """
    _messages = []
    try:
        _today_str = _tracker_today_iso()
        _all_bets_check = load_all_bets(exclude_linked=False)

        # Resolve past pending bets (yesterday and older)
        _pending_old = [
            b for b in _all_bets_check
            if not b.get("result") and b.get("bet_date", "") < _today_str
        ]
        if _pending_old:
            _dates_to_resolve = sorted({b.get("bet_date", "") for b in _pending_old if b.get("bet_date")})
            _total_resolved = 0
            for _d in _dates_to_resolve:
                try:
                    _cnt, _ = auto_resolve_bet_results(date_str=_d)
                    _total_resolved += _cnt
                except Exception as _resolve_exc:
                    _logger.warning("Auto-resolve failed for %s: %s", _d, _resolve_exc)
            if _total_resolved > 0:
                _messages.append(f"🤖 Auto-resolved {_total_resolved} past bet(s).")

        # Silently attempt to resolve today's bets where games are Final
        try:
            from tracking.bet_tracker import resolve_todays_bets
            _today_result = resolve_todays_bets()
            if _today_result.get("resolved", 0) > 0:
                _messages.append(
                    f"⚡ Auto-resolved {_today_result['resolved']} of today's bet(s) "
                    f"({_today_result['wins']}W / {_today_result['losses']}L)."
                )
        except Exception as _today_exc:
            _logger.debug("Today's bet resolve skipped: %s", _today_exc)

        # Silently attempt to resolve pending analysis picks
        try:
            from tracking.bet_tracker import resolve_all_analysis_picks
            _picks_result = resolve_all_analysis_picks(include_today=False)
            _picks_resolved = _picks_result.get("resolved", 0)
            if _picks_resolved > 0:
                _messages.append(
                    f"📋 Auto-resolved {_picks_resolved} analysis pick(s) "
                    f"({_picks_result.get('wins', 0)}W / {_picks_result.get('losses', 0)}L)."
                )
        except Exception as _picks_exc:
            _logger.debug("Analysis picks resolve skipped: %s", _picks_exc)

        # Auto-update CLV closing lines using Odds API prop lines
        try:
            from engine.clv_tracker import auto_update_closing_lines as _auto_clv
            _clv_result = _auto_clv(days_back=1)
            if _clv_result.get("updated", 0) > 0:
                _messages.append(
                    f"📈 CLV updated: {_clv_result['updated']} record(s) closed "
                    f"with live closing lines."
                )
        except Exception as _clv_exc:
            _logger.debug("CLV auto-update skipped: %s", _clv_exc)

        # Prune old analysis sessions (keep last 30 days)
        try:
            from tracking.database import purge_old_sessions
            purge_old_sessions(days=30)
        except Exception as _purge_exc:
            _logger.debug("Session purge skipped: %s", _purge_exc)
    except Exception as _bg_exc:
        _logger.warning("Background auto-resolve error: %s", _bg_exc)

    # Store results for the main thread to pick up on next rerender
    st.session_state["_auto_resolve_messages"] = _messages
    st.session_state["_auto_resolve_done"] = True

_auto_resolve_today = _tracker_today_iso()
if st.session_state.get("_bet_tracker_auto_resolved_date") != _auto_resolve_today:
    st.session_state["_bet_tracker_auto_resolved_date"] = _auto_resolve_today
    st.session_state["_auto_resolve_done"] = False
    _resolve_thread = _threading.Thread(target=_background_auto_resolve, daemon=True)
    _resolve_thread.start()
    st.toast("🤖 Auto-resolving pending bets in the background…")

# Show deferred toast messages from background thread and refresh bet cache
if st.session_state.get("_auto_resolve_done"):
    _msgs = st.session_state.pop("_auto_resolve_messages", [])
    if _msgs:
        _reload_bets()  # Refresh cache now that resolve is done (main thread)
        for _toast_line in _msgs:
            if _toast_line.strip():
                st.toast(_toast_line.strip())
    st.session_state.pop("_auto_resolve_done", None)

st.title("📈 Bet Tracker & Model Health")
st.markdown(
    "Your unified hub for tracking model performance, logging bets, "
    "auto-resolving results, and forecasting ROI."
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Bet Tracker — Logging and Tracking Your Bets
    
    **Logging Bets:**
    - Bets are **auto-logged** when you run Neural Analysis (top picks are saved)
    - You can also manually log bets using the "Add Bet" form
    - Each bet records: player, stat, line, direction (over/under), confidence tier
    
    **Auto-Resolve:**
    - Click "Check Results Now" to automatically resolve today's bets
    - The system retrieves actual game stats and marks bets as Won/Lost
    - Player name matching uses fuzzy logic to handle name variations
    
    **Reading Stats:**
    - **Win Rate**: % of resolved bets that won
    - **ROI**: Return on investment (positive = profitable)
    - **CLV**: Closing Line Value — did you beat the closing line?
    
    💡 **Pro Tips:**
    - Run "Check Results Now" after games finish (usually 11 PM ET)
    - Check the "Model Health" section to see which tiers perform best
    - Use filters to analyze performance by platform or stat type
    """)

# ── Prominent "Check Results Now" button — always visible at top ──────────
_check_col, _check_info_col = st.columns([1, 3])
with _check_col:
    _check_now_btn = st.button(
        "🔄 Check Results Now",
        type="primary",
        width="stretch",
        help="Immediately check live NBA scoreboard for Final games and resolve today's pending bets.",
        key="top_check_results_btn",
    )
with _check_info_col:
    st.caption(
        "Checks the live NBA scoreboard for completed games and instantly resolves today's pending bets. "
        "Click any time — no need to wait until tomorrow."
    )

if _check_now_btn:
    _jl_loader_top = None
    if _JOSEPH_LOADING_AVAILABLE:
        _jl_loader_top = joseph_loading_placeholder("Checking live NBA games and resolving today's bets")
    try:
        from tracking.bet_tracker import resolve_todays_bets as _rtr_top
        _top_result = _rtr_top()
        if _jl_loader_top is not None:
            _jl_loader_top.empty()
        if _top_result.get("resolved", 0) > 0:
            st.success(
                f"✅ Resolved **{_top_result['resolved']}** bet(s): "
                f"**{_top_result['wins']}** WIN · **{_top_result['losses']}** LOSS · **{_top_result['evens']}** EVEN"
            )
            st.rerun()
        else:
            st.info(
                f"ℹ️ No bets resolved. Games may still be in progress or not started. "
                f"Pending: {_top_result.get('pending', 0)}"
            )
        if _top_result.get("errors"):
            st.warning("⚠️ " + " | ".join(_top_result["errors"][:3]))
            if len(_top_result["errors"]) > 3:
                with st.expander(f"See all {len(_top_result['errors'])} detail(s)"):
                    for _e in _top_result["errors"]:
                        st.markdown(f"- {_e}")
    except Exception as _top_err:
        if _jl_loader_top is not None:
            _jl_loader_top.empty()
        st.error(f"❌ Could not check results: {_top_err}")

# ============================================================
# SECTION: Top-Level Platform Selector
# ============================================================

st.divider()

# ── Enhanced Filter Bar (B12) ─────────────────────────────────────────
_filter_col1, _filter_col2, _filter_col3, _filter_col4 = st.columns([2, 2, 2, 1])

with _filter_col1:
    platform_filter_selections = st.multiselect(
        "Filter by Platform",
        ["🟢 PrizePicks", "🟣 Underdog Fantasy", "🔵 DraftKings Pick6", "🤖 Smart Pick Pro Platform Picks"],
        default=[],
        key="platform_multi_filter",
        help="Select platforms to filter. Leave empty for all platforms.",
    )

with _filter_col2:
    _player_search = st.text_input(
        "🔍 Search Player",
        placeholder="e.g., LeBron James",
        key="player_search_input",
        help="Search bets by player name across all tabs.",
    )

with _filter_col3:
    _date_range = st.date_input(
        "📅 Date Range",
        value=[],
        key="date_range_filter",
        help="Filter bets by date range. Leave empty for all dates.",
    )

with _filter_col4:
    _direction_filter = st.selectbox(
        "Direction",
        ["All", "OVER", "UNDER"],
        key="direction_filter",
        help="Filter by bet direction.",
    )


# Map multi-select platform filter to a filter function
def _platform_filter_fn(bet):
    """Return True if this bet matches the selected platform filter(s)."""
    if not platform_filter_selections:
        return True  # Empty = show all
    plat = str(bet.get("platform") or "").lower()
    for sel in platform_filter_selections:
        if sel == "🟢 PrizePicks" and "prizepicks" in plat:
            return True
        elif sel == "🟣 Underdog Fantasy" and "underdog" in plat:
            return True
        elif sel == "🔵 DraftKings Pick6" and ("draftkings" in plat or "pick6" in plat or plat == "dk"):
            return True
        elif sel == "🤖 Smart Pick Pro Platform Picks" and (
            _is_ai_auto_bet(bet) or "smartai-auto" in plat or "smartauto-ai" in plat or "smart pick pro" in plat
        ):
            return True
    return False


def _apply_global_filters(bets):
    """Apply player search, date range, and direction filters."""
    filtered = bets
    # Player search
    if _player_search and _player_search.strip():
        _q = _player_search.strip().lower()
        filtered = [b for b in filtered if _q in str(b.get("player_name", "")).lower()]
    # Date range (supports both bet_date and pick_date keys)
    if _date_range and len(_date_range) == 2:
        _start = _date_range[0].isoformat()
        _end = _date_range[1].isoformat()
        filtered = [b for b in filtered if _start <= (b.get("bet_date") or b.get("pick_date") or "") <= _end]
    # Direction
    if _direction_filter and _direction_filter != "All":
        filtered = [b for b in filtered if str(b.get("direction", "")).upper() == _direction_filter]
    return filtered

st.divider()

# ============================================================
# END SECTION: Top-Level Platform Selector
# ============================================================

# ============================================================
# SECTION: Tabs
# ============================================================

(
    tab_model_health,
    tab_ai_picks,
    tab_all_picks,
    tab_joseph_bets,
    tab_auto_resolve,
    tab_bets,
    tab_log,
    tab_parlays,
    tab_predict,
    tab_history,
    tab_achievements,
) = st.tabs([
    "📊 Health",
    "🤖 Platform Picks",
    "📋 All Picks",
    "🎙️ Joseph",
    "⚡ Resolve",
    "📋 My Bets",
    "➕ Log Bet",
    "🎰 Parlays",
    "🔮 Predict",
    "📅 History",
    "🏆 Awards",
])

# ============================================================
# END SECTION: Tabs
# ============================================================

# Shared result emoji map
_RESULT_EMOJI = {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄", "VOID": "🚫", None: "⏳", "": "⏳"}

# DFS payout ratio (standard: $0.909 profit per $1 risked on a winning bet)
_DFS_PAYOUT_RATIO = 0.909
# Win rate required to break even at this payout ratio: 1 / (1 + 0.909) ≈ 52.38%
_BREAKEVEN_WIN_RATE = 52.38

# ============================================================
# SECTION: Model Health Tab
# ============================================================

with tab_model_health:
    st.subheader("📊 Health — Shared Pick Universe")
    st.markdown(get_education_box_html(
        "📖 What is Model Health?",
        """
        <strong>Model Calibration</strong>: Are the model's probabilities accurate?
        If we say 70% probability, does the pick hit ~70% of the time?<br><br>
        <strong>Win Rate by Tier</strong>: Platinum picks should win more than Bronze picks.
        If Bronze is winning more than Platinum, the model needs recalibration.<br><br>
        <strong>Why track results?</strong>: The more bets you log, the better we can see
        if the model is making money over time. Track at least 50+ bets to see meaningful
        patterns.<br><br>
        <strong>ROI</strong>: Return on Investment = (profit / total wagered) × 100.
        Positive ROI means you're profitable long-term.
        """
    ), unsafe_allow_html=True)

    _health_scope_col1, _health_scope_col2 = st.columns([2, 5])
    if not st.session_state.get("_health_scope_default_migrated", False):
        if st.session_state.get("health_scope_filter") in (None, "Today"):
            st.session_state["health_scope_filter"] = "All Time"
        st.session_state["_health_scope_default_migrated"] = True
    with _health_scope_col1:
        _health_scope = st.selectbox(
            "Health Scope",
            ["Today", "Last 7 Days", "All Time"],
            index=2,
            key="health_scope_filter",
            help="Choose which date window feeds Model Health stats.",
        )
    with _health_scope_col2:
        st.caption("Health now uses the same merged pick universe as All Picks for matching totals under the same scope.")

    _health_universe = _build_merged_pick_universe(_health_scope)
    filtered_health = _apply_global_filters([p for p in _health_universe["combined"] if _platform_filter_fn(p)])
    resolved_health = [b for b in filtered_health if b.get("result") in ("WIN", "LOSS", "EVEN")]
    wins_h   = sum(1 for b in resolved_health if b.get("result") == "WIN")
    losses_h = sum(1 for b in resolved_health if b.get("result") == "LOSS")
    evens_h = sum(1 for b in resolved_health if b.get("result") == "EVEN")
    total_h  = len(resolved_health)
    win_rate_h = round(wins_h / max(wins_h + losses_h, 1) * 100, 1)
    pending_h = sum(1 for b in filtered_health if not b.get("result"))

    # Compute streak from the same merged source used for Health totals.
    streak_val = 0
    _health_resolved_sorted = sorted(
        [b for b in filtered_health if b.get("result") in ("WIN", "LOSS")],
        key=lambda b: _canonical_pick_date(b),
        reverse=True,
    )
    if _health_resolved_sorted:
        _health_first_result = _health_resolved_sorted[0].get("result")
        streak_val = 1 if _health_first_result == "WIN" else -1
        for _hb in _health_resolved_sorted[1:]:
            if _hb.get("result") == _health_first_result:
                streak_val += 1 if _health_first_result == "WIN" else -1
            else:
                break

    # Best platform
    _plat_wins: dict = {}
    for b in resolved_health:
        p = str(b.get("platform") or "Unknown")
        w = 1 if b.get("result") == "WIN" else 0
        l = 1 if b.get("result") == "LOSS" else 0
        if p not in _plat_wins:
            _plat_wins[p] = {"wins": 0, "total": 0}
        _plat_wins[p]["wins"] += w
        _plat_wins[p]["total"] += (w + l)
    best_platform = ""
    if _plat_wins:
        _sorted_plats = sorted(
            [(p, d["wins"] / max(d["total"], 1)) for p, d in _plat_wins.items() if d["total"] >= 3],
            key=lambda x: x[1], reverse=True,
        )
        if _sorted_plats:
            best_platform = _sorted_plats[0][0]

    # Summary cards
    st.markdown(
        get_summary_cards_html(
            total=len(filtered_health),
            wins=wins_h,
            losses=losses_h,
            evens=evens_h,
            pending=pending_h,
            win_rate=win_rate_h,
            streak=streak_val,
            best_platform=best_platform,
            total_label="Total Picks",
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "What this count means: Health uses the same merged pick universe as All Picks. "
        f"Scope source = {len(_health_universe['analysis_rows'])} persisted analysis rows + "
        f"{len(_health_universe['pipeline_added'])} pipeline/tracker rows "
        f"(-{_health_universe['pipeline_skip_ai_overlap']} SmartAI overlaps) "
        f"= {_health_universe.get('combined_pre_dedup_count', len(_health_universe['combined']))} pre-dedup rows "
        f"(-{_health_universe.get('dedup_removed', 0)} duplicate merge key collisions) "
        f"= {len(_health_universe['combined'])} merged picks before current platform/search/date/direction filters; "
        f"{len(filtered_health)} currently shown."
    )

    if total_h == 0:
        st.info(
            "📝 No resolved picks found in the shared Health view. Use **➕ Log a Bet** or run analysis, "
            "then record results to see performance stats here."
        )

    # ── Notifications & Alerts (B11) ──────────────────────────────────
    if total_h > 0:
        # Tilt detection: 3+ consecutive losses
        _recent_resolved = sorted(
            resolved_health, key=lambda b: b.get("bet_date", ""), reverse=True
        )
        _consec_losses = 0
        for _rb in _recent_resolved:
            if _rb.get("result") == "LOSS":
                _consec_losses += 1
            else:
                break
        if _consec_losses >= 3:
            st.warning(
                f"🧊 **Tilt Alert** — You've hit **{_consec_losses} consecutive losses**. "
                "Consider taking a break or reducing your unit size for the next few bets. "
                "Disciplined bankroll management is key to long-term profitability."
            )

        # Streak alert: 5+ consecutive wins
        _consec_wins = 0
        for _rb in _recent_resolved:
            if _rb.get("result") == "WIN":
                _consec_wins += 1
            else:
                break
        if _consec_wins >= 5:
            st.success(
                f"🔥 **Hot Streak Alert** — You're on a **{_consec_wins}-game win streak**! "
                "Consider locking in profits by reducing your next bet sizing slightly."
            )

        # Model drift alert: win rate below 50% for last 20 bets
        _last_20 = _recent_resolved[:20]
        if len(_last_20) >= 20:
            _l20_wins = sum(1 for b in _last_20 if b.get("result") == "WIN")
            _l20_wr = _l20_wins / 20 * 100
            if _l20_wr < 50:
                st.error(
                    f"📉 **Model Drift Warning** — Win rate over the last 20 bets is "
                    f"**{_l20_wr:.0f}%** (below breakeven). The model may need recalibration. "
                    "Check the tier performance below to identify which tiers are underperforming."
                )

    if total_h > 0:
        st.divider()

        performance_stats = get_model_performance_stats(bets_list=filtered_health)

        # Win rate by tier
        with st.expander("🏆 Win Rate by Tier", expanded=True):
            tier_perf = performance_stats.get("by_tier", {})
            if tier_perf:
                tier_order = ["Platinum", "Gold", "Silver", "Bronze"]
                tier_rows = [
                    {
                        "Tier": t,
                        "Total": tier_perf[t].get("total", 0),
                        "Wins":  tier_perf[t].get("wins", 0),
                        "Losses": tier_perf[t].get("losses", 0),
                        "Win Rate": f"{tier_perf[t].get('win_rate', 0):.1f}%",
                    }
                    for t in tier_order if t in tier_perf
                ]
                st.markdown(
                    get_styled_stats_table_html(
                        tier_rows,
                        ["Tier", "Total", "Wins", "Losses", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )
                # Tier spotlight metric cards
                _tier_spot_cols = st.columns(4)
                _tier_icons = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
                for _ti, _tn in enumerate(["Platinum", "Gold", "Silver", "Bronze"]):
                    if _tn in tier_perf:
                        _td = tier_perf[_tn]
                        _tier_spot_cols[_ti].metric(
                            f"{_tier_icons[_tn]} {_tn}",
                            f"{_td.get('win_rate', 0):.1f}%",
                            help=f"{_tn}: {_td.get('wins', 0)}W / {_td.get('losses', 0)}L "
                                 f"({_td.get('total', 0)} total bets)",
                        )

                # ── Tier Win Rate Bar Chart ───────────────────────────
                _tier_chart_data = []
                for _tn in tier_order:
                    if _tn in tier_perf and tier_perf[_tn].get("total", 0) > 0:
                        _tier_chart_data.append({
                            "Tier": f"{_tier_icons.get(_tn, '')} {_tn}",
                            "Win Rate": tier_perf[_tn].get("win_rate", 0),
                            "Sample Size": tier_perf[_tn].get("total", 0),
                        })
                if _tier_chart_data:
                    import pandas as _pd_tier
                    _tier_df = _pd_tier.DataFrame(_tier_chart_data)
                    st.markdown("##### Tier Win Rate Validation")
                    st.bar_chart(
                        _tier_df.set_index("Tier")["Win Rate"],
                        color="#ffd700",
                    )
                    # Tier inversion warning
                    _tier_wr = {d["Tier"]: d["Win Rate"] for d in _tier_chart_data}
                    _tier_names_ordered = [f"{_tier_icons.get(t, '')} {t}" for t in tier_order if f"{_tier_icons.get(t, '')} {t}" in _tier_wr]
                    for _i in range(len(_tier_names_ordered) - 1):
                        _higher = _tier_names_ordered[_i]
                        _lower = _tier_names_ordered[_i + 1]
                        if _tier_wr.get(_higher, 0) < _tier_wr.get(_lower, 0) - 5:
                            st.warning(
                                f"⚠️ **Tier Inversion**: {_higher} ({_tier_wr[_higher]:.1f}%) is "
                                f"underperforming {_lower} ({_tier_wr[_lower]:.1f}%). "
                                f"Higher tiers should consistently outperform lower ones."
                            )
            else:
                st.caption("No tier data yet.")

        # Win rate by platform
        with st.expander("🎰 Win Rate by Platform", expanded=True):
            plat_perf = performance_stats.get("by_platform", {})
            if plat_perf:
                plat_rows = [
                    {
                        "Platform": p,
                        "Total": d.get("total", 0),
                        "Wins":  d.get("wins", 0),
                        "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                    }
                    for p, d in plat_perf.items()
                ]
                st.markdown(
                    get_styled_stats_table_html(
                        plat_rows,
                        ["Platform", "Total", "Wins", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No platform data yet.")

        # Win rate by stat type
        with st.expander("📐 Win Rate by Stat Type", expanded=False):
            stat_perf = performance_stats.get("by_stat_type", {})
            if stat_perf:
                stat_rows = [
                    {
                        "Stat Type": s.capitalize(),
                        "Total": d.get("total", 0),
                        "Wins":  d.get("wins", 0),
                        "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                    }
                    for s, d in sorted(stat_perf.items())
                ]
                st.markdown(
                    get_styled_stats_table_html(
                        stat_rows,
                        ["Stat Type", "Total", "Wins", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No stat type data yet.")

        # Win rate by bet classification
        _health_bt_perf: dict = {}
        for _hb in resolved_health:
            _bt = _normalized_bet_type(_hb)
            if _bt not in _health_bt_perf:
                _health_bt_perf[_bt] = {"wins": 0, "losses": 0, "total": 0}
            _health_bt_perf[_bt]["total"] += 1
            if _hb.get("result") == "WIN":
                _health_bt_perf[_bt]["wins"] += 1
            elif _hb.get("result") == "LOSS":
                _health_bt_perf[_bt]["losses"] += 1

        if _health_bt_perf:
            with st.expander("Win Rate by Bet Classification", expanded=True):
                bt_rows = [
                    {
                        "Bet Type":  _bet_type_display_name(bt),
                        "Total":     d.get("total", 0),
                        "Wins":      d.get("wins", 0),
                        "Losses":    d.get("losses", 0),
                        "Win Rate":  f"{d.get('win_rate', 0):.1f}%",
                    }
                    for bt, d in sorted(
                        {
                            _bt: {
                                **_d,
                                "win_rate": round(_d["wins"] / max(_d["wins"] + _d["losses"], 1) * 100, 1)
                                if (_d["wins"] + _d["losses"]) > 0 else 0.0,
                            }
                            for _bt, _d in _health_bt_perf.items()
                        }.items(),
                        key=lambda item: _bet_type_sort_key(item[0]),
                    )
                ]
                st.markdown(
                    get_styled_stats_table_html(
                        bt_rows,
                        ["Bet Type", "Total", "Wins", "Losses", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )

        # ── Win Rate by Pick Source ───────────────────────────────────
        _ps_all = performance_stats.get("all_bets", [])
        _ps_resolved = [
            b for b in _ps_all
            if b.get("result") and b["result"] in ("WIN", "LOSS", "EVEN")
        ]
        if _ps_resolved:
            # Categorise each resolved bet into pick sources
            _ps_sources = {
                "QEG Picks": {"wins": 0, "losses": 0, "total": 0},
                "Joseph M Smith": {"wins": 0, "losses": 0, "total": 0},
                "Goblins": {"wins": 0, "losses": 0, "total": 0},
                "Smart Money": {"wins": 0, "losses": 0, "total": 0},
                "Smart Pick Pro Platform Picks": {"wins": 0, "losses": 0, "total": 0},
            }
            for _pb in _ps_resolved:
                _pb_auto = int(_pb.get("auto_logged", 0) or 0) == 1
                _pb_plat = (_pb.get("platform") or "").lower()
                _pb_notes = (_pb.get("notes") or "").lower()
                _pb_bt = (_pb.get("bet_type") or "").lower()
                _pb_is_joseph = _pb_plat in ("joseph m. smith", "joseph") or "joseph" in _pb_notes
                _pb_is_goblin = _pb_bt == "goblin"
                _pb_is_smart_money = "smart money" in _pb_plat
                _pb_result = _pb.get("result", "")

                def _ps_incr(bucket):
                    if _pb_result == "WIN":
                        bucket["wins"] += 1
                        bucket["total"] += 1
                    elif _pb_result == "LOSS":
                        bucket["losses"] += 1
                        bucket["total"] += 1

                # QEG = auto-logged picks that are NOT Joseph and NOT Smart Money
                if _pb_auto and not _pb_is_joseph and not _pb_is_smart_money:
                    _ps_incr(_ps_sources["QEG Picks"])
                # Joseph
                if _pb_is_joseph:
                    _ps_incr(_ps_sources["Joseph M Smith"])
                # Goblins (can overlap with QEG / Joseph)
                if _pb_is_goblin:
                    _ps_incr(_ps_sources["Goblins"])
                # Smart Money (page 15 auto-logged picks)
                if _pb_is_smart_money:
                    _ps_incr(_ps_sources["Smart Money"])
                # Smart Pick Pro Platform Picks = every auto-logged Smart Pick Pro pick
                if _pb_auto:
                    _ps_incr(_ps_sources["Smart Pick Pro Platform Picks"])

            # Remove empty categories
            _ps_sources = {k: v for k, v in _ps_sources.items() if v["total"] > 0}

            if _ps_sources:
                # Compute win rates
                for _psd in _ps_sources.values():
                    _psd["win_rate"] = round(
                        _psd["wins"] / _psd["total"] * 100, 1
                    ) if _psd["total"] > 0 else 0.0

                with st.expander("🎯 Win Rate by Pick Source", expanded=True):
                    _ps_rows = [
                        {
                            "Source": src,
                            "Total": d["total"],
                            "Wins": d["wins"],
                            "Losses": d["losses"],
                            "Win Rate": f"{d['win_rate']:.1f}%",
                        }
                        for src, d in _ps_sources.items()
                    ]
                    st.markdown(
                        get_styled_stats_table_html(
                            _ps_rows,
                            ["Source", "Total", "Wins", "Losses", "Win Rate"],
                        ),
                        unsafe_allow_html=True,
                    )

                    # Metric cards row
                    _ps_icons = {
                        "QEG Picks": "⚛️",
                        "Joseph M Smith": "🎙️",
                        "Goblins": "👺",
                        "Smart Money": "💰",
                        "Smart Pick Pro Platform Picks": "🤖",
                    }
                    _ps_cols = st.columns(len(_ps_sources))
                    for _pi, (src, d) in enumerate(_ps_sources.items()):
                        _ps_cols[_pi].metric(
                            f"{_ps_icons.get(src, '📊')} {src}",
                            f"{d['win_rate']:.1f}%",
                            help=f"{src}: {d['wins']}W / {d['losses']}L ({d['total']} total)",
                        )

        # Feature 1: Enhanced tier accuracy report
        try:
            _get_clv_fns()  # trigger lazy import
            if get_tier_accuracy_report:
                st.subheader("📊 Model Tier Accuracy")
                _tier_report = get_tier_accuracy_report(days=90)
                if _tier_report.get("has_data"):
                    for _tier, _stats in _tier_report.get("by_tier", {}).items():
                        _col_a, _col_b, _col_c = st.columns(3)
                        _col_a.metric(f"{_tier} — Avg CLV", f"{_stats.get('avg_clv', 0):.3f}")
                        _col_b.metric(f"Positive CLV Rate", f"{_stats.get('positive_clv_rate', 0)*100:.1f}%")
                        if _stats.get('win_rate') is not None:
                            _col_c.metric(f"Win Rate", f"{_stats['win_rate']*100:.1f}%")
                        else:
                            _col_c.caption("Win rate: no bet results recorded yet")
                else:
                    st.info("📊 Tier accuracy report will appear after recording bets and closing lines.")
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTrackerPage] Unexpected error: {_exc}")

        # Feature 4: Isotonic calibration curve
        try:
            _get_calibration_fns()  # trigger lazy import
            if get_isotonic_calibration_curve:
                st.subheader("📈 Isotonic Calibration Curve")
                _iso_curve = get_isotonic_calibration_curve(days=90)
                if _iso_curve.get("has_data"):
                    st.caption(f"Based on {_iso_curve['total_records']} historical predictions | "
                               f"{'Isotonic smoothing applied' if _iso_curve['is_isotonic'] else 'Coarse buckets (need 200+ records for isotonic)'}")
                    for _pt in _iso_curve.get("curve", []):
                        _gap = _pt["actual"] - _pt["predicted"]
                        _indicator = "✅" if abs(_gap) < 0.05 else ("📈" if _gap > 0 else "📉")
                        st.markdown(
                            f"{_indicator} **{_pt['predicted']*100:.0f}%** predicted → "
                            f"**{_pt['actual']*100:.1f}%** actual "
                            f"({'n=' + str(_pt['count'])})"
                        )
                else:
                    st.info("📈 Isotonic calibration curve will appear after recording enough bets (200+ for fine-grained view).")
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTrackerPage] Unexpected error: {_exc}")

        # CLV Summary — aggregate closing-line-value performance
        try:
            _get_clv_fns()  # trigger lazy import
            if get_clv_summary:
                st.subheader("📈 Closing Line Value (CLV) Summary")
                _clv_data = get_clv_summary()
                if _clv_data and _clv_data.get("has_data"):
                    _clv_c1, _clv_c2, _clv_c3 = st.columns(3)
                    _clv_c1.metric("Total CLV Records", _clv_data.get("total_records", 0))
                    _avg_clv = _clv_data.get("avg_clv", 0)
                    _clv_c2.metric(
                        "Average CLV",
                        f"{_avg_clv:+.3f}",
                        delta="Beating the market" if _avg_clv > 0 else "Behind the market",
                        delta_color="normal" if _avg_clv > 0 else "inverse",
                    )
                    _pos_rate = _clv_data.get("positive_clv_rate", 0)
                    _clv_c3.metric("Positive CLV Rate", f"{_pos_rate * 100:.1f}%")

                    _clv_by_tier = _clv_data.get("clv_by_tier", {})
                    if _clv_by_tier:
                        st.markdown("**CLV by Tier:**")
                        for _tier_name, _tier_clv in _clv_by_tier.items():
                            _t_avg = _tier_clv.get("avg_clv", 0)
                            _t_pos = _tier_clv.get("positive_clv_rate", 0)
                            _t_n = _tier_clv.get("count", 0)
                            _t_icon = "🟢" if _t_avg > 0 else "🔴"
                            st.markdown(
                                f"{_t_icon} **{_tier_name}**: avg CLV {_t_avg:+.3f} · "
                                f"positive rate {_t_pos * 100:.1f}% · {_t_n} record(s)"
                            )

                    _interpretation = _clv_data.get("interpretation", "")
                    if _interpretation:
                        st.info(f"💡 {_interpretation}")
                else:
                    st.info(
                        "📈 CLV summary will appear after recording bets and tracking closing lines. "
                        "Run **⚡ Neural Analysis** and allow auto-CLV updates to build your CLV history."
                    )
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTrackerPage] CLV summary error: {_exc}")

# ============================================================
# END SECTION: Model Health Tab
# ============================================================


# ============================================================
# SECTION: Platform Picks Tab
# ============================================================

with tab_ai_picks:
    st.subheader("📊 Platform Picks — Smart Pick Pro Platform Picks")
    st.markdown(
        "These bets were automatically logged by the Smart Pick Pro platform pipeline "
        "(formerly shown as SmartAI Auto)."
    )

    _ai_scope_col1, _ai_scope_col2 = st.columns([2, 5])
    if not st.session_state.get("_ai_scope_default_migrated", False):
        if st.session_state.get("ai_picks_scope") in (None, "Today"):
            st.session_state["ai_picks_scope"] = "All Time"
        st.session_state["_ai_scope_default_migrated"] = True
    with _ai_scope_col1:
        _ai_scope = st.selectbox(
            "Platform Picks Scope",
            ["Today", "Last 7 Days", "Last 30 Days", "All Time"],
            index=3,
            key="ai_picks_scope",
            help="Date window for Smart Pick Pro auto-logged picks.",
        )
    with _ai_scope_col2:
        st.caption("Platform Picks uses strict Smart Pick Pro source tagging to avoid mixing Joseph/manual bets.")

    all_bets_for_ai = _cached_load_all_bets()
    ai_bets_raw = [b for b in all_bets_for_ai if _is_ai_auto_bet(b)]
    ai_bets_raw = [b for b in ai_bets_raw if _in_bet_date_window(b, _ai_scope, "bet_date")]
    ai_bets = _apply_global_filters([b for b in ai_bets_raw if _platform_filter_fn(b)])

    # ── Tier Filter & Bet Classification Filter ───────────────────────────
    _ai_filter_col1, _ai_filter_col2 = st.columns(2)
    with _ai_filter_col1:
        _ai_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[],
            key="ai_tier_filter",
            help="Show only picks matching the selected tiers. Leave empty to show all tiers.",
        )
    with _ai_filter_col2:
        _ai_bet_type_filter = st.multiselect(
            "Bet Classification",
            ["Standard", "Goblin", "Normal", "Fantasy"],
            default=[],
            key="ai_bet_type_filter",
            help="Filter by bet classification. Leave empty to show all.",
        )
    if _ai_tier_filter:
        _ai_tier_names = [t.split(" ")[0] for t in _ai_tier_filter]
        ai_bets = [b for b in ai_bets if b.get("tier") in _ai_tier_names]
    if _ai_bet_type_filter:
        _bt_filter_set = {bt.lower() for bt in _ai_bet_type_filter}
        ai_bets = [b for b in ai_bets if (b.get("bet_type") or "standard").lower() in _bt_filter_set]

    if not ai_bets:
        st.info(
            "📭 No Smart Pick Pro platform picks yet. "
            "Run **⚡ Neural Analysis** or click **📊 Get Platform Props & Analyze** on the Live Games page."
        )
    else:
        ai_resolved = [b for b in ai_bets if b.get("result") in ("WIN", "LOSS", "EVEN")]
        ai_wins   = sum(1 for b in ai_resolved if b.get("result") == "WIN")
        ai_losses = sum(1 for b in ai_resolved if b.get("result") == "LOSS")
        ai_evens = sum(1 for b in ai_resolved if b.get("result") == "EVEN")
        ai_decided = ai_wins + ai_losses
        ai_rate   = round(ai_wins / max(ai_wins + ai_losses, 1) * 100, 1)

        st.markdown(
            get_summary_cards_html(
                total=len(ai_bets),
                wins=ai_wins,
                losses=ai_losses,
                evens=ai_evens,
                pending=sum(1 for b in ai_bets if not b.get("result")),
                win_rate=ai_rate,
                total_label="Total Picks",
            ),
            unsafe_allow_html=True,
        )
        st.caption("What this count means: Platform Picks counts only Smart Pick Pro platform auto-logged tracker bets from the bets table. It is a subset of Health.")

        if ai_decided > 0:
            st.success(
                f"🎯 **Model accuracy:** Predicted **{ai_wins}/{ai_decided}** correctly "
                f"(**{ai_rate:.1f}%**) — {ai_evens} even(s)"
            )

        st.divider()

        # Daily breakdown with bet cards
        _by_date: dict = {}
        for b in ai_bets:
            _by_date.setdefault(b.get("bet_date", "Unknown"), []).append(b)

        for _date in sorted(_by_date.keys(), reverse=True):
            _day_bets  = _by_date[_date]
            _day_res   = [b for b in _day_bets if b.get("result") in ("WIN", "LOSS", "EVEN")]
            _day_wins  = sum(1 for b in _day_res if b.get("result") == "WIN")
            _day_losses = sum(1 for b in _day_res if b.get("result") == "LOSS")
            _day_evens = sum(1 for b in _day_res if b.get("result") == "EVEN")
            _day_decided = _day_wins + _day_losses
            _day_rate  = round(_day_wins / max(_day_decided, 1) * 100, 1) if _day_decided > 0 else None

            _day_label = (
                f"📅 {_date} — {len(_day_bets)} picks"
                + (f" · {_day_wins}/{_day_decided} correct ({_day_rate:.0f}%)"
                   if _day_rate is not None else " · pending")
                + (f" · {_day_evens} even" if _day_evens else "")
            )
            with st.expander(_day_label, expanded=(_date == max(_by_date.keys()))):
                _col_a, _col_b = st.columns(2)
                for _idx, _b in enumerate(_day_bets):
                    _col = _col_a if _idx % 2 == 0 else _col_b
                    with _col:
                        _b_display = dict(_b)
                        _b_display["platform"] = _platform_display_name(_b_display.get("platform"))
                        st.markdown(get_bet_card_html(_b_display), unsafe_allow_html=True)

# ============================================================
# END SECTION: Platform Picks Tab
# ============================================================


# ============================================================
# SECTION: All Picks Tab
# ============================================================

with tab_all_picks:
    st.subheader("📋 All Picks — Shared Pick Universe")
    st.markdown(
        "Every pick the app outputs across persisted analysis rows and tracked pipeline bets. "
        "This tab now uses the same merged source as Health so totals align under the same scope."
    )

    _ap_scope_col1, _ap_scope_col2 = st.columns([2, 5])
    with _ap_scope_col1:
        _all_picks_scope = st.selectbox(
            "All Picks Scope",
            ["Today", "Last 7 Days", "Last 30 Days", "All Time"],
            index=0,
            key="all_picks_scope",
            help="Date window for all analysis picks.",
        )
    with _ap_scope_col2:
        st.caption("All Picks and Health now share the same merged pick universe inside the selected date window.")

    # ── 🔄 Resolve All Picks button ───────────────────────────────────
    _rap_col1, _rap_col2 = st.columns([1, 3])
    with _rap_col1:
        _resolve_all_picks_btn = st.button(
            "🔄 Resolve All Picks",
            key="resolve_all_picks_btn",
            type="primary",
            help="Retrieve actual NBA stats and auto-resolve ALL unresolved picks (manual and AI-logged).",
        )
    with _rap_col2:
        st.caption("Auto-resolves every pending pick using live NBA stats — includes both manual and AI-logged picks.")

    if _resolve_all_picks_btn:
        _jl_loader_rap = None
        if _JOSEPH_LOADING_AVAILABLE:
            _jl_loader_rap = joseph_loading_placeholder("Resolving all pending picks across all dates")
        try:
            # ── Step 1: Resolve all_analysis_picks table (what this tab displays) ──
            _picks_result  = resolve_all_analysis_picks(include_today=True)
            # ── Step 2: Also resolve the bets table (manual + AI bets) ──────────
            _bets_result   = resolve_all_pending_bets()

            if _jl_loader_rap is not None:
                _jl_loader_rap.empty()

            # Report each table separately to avoid inflating counts when
            # the same player-stat exists in both tables.
            _rap_picks_resolved = _picks_result.get("resolved", 0)
            _rap_bets_resolved  = _bets_result.get("resolved", 0)
            _rap_resolved       = _rap_picks_resolved + _rap_bets_resolved
            _rap_wins      = _picks_result.get("wins", 0)    + _bets_result.get("wins", 0)
            _rap_losses    = _picks_result.get("losses", 0)  + _bets_result.get("losses", 0)
            _rap_evens    = _picks_result.get("evens", 0)  + _bets_result.get("evens", 0)
            _rap_pending   = _picks_result.get("pending", 0) + _bets_result.get("pending", 0)
            _rap_errors    = _picks_result.get("errors", []) + _bets_result.get("errors", [])

            # Deduplicate errors (same player may appear in both tables)
            _rap_errors = list(dict.fromkeys(_rap_errors))

            if _rap_resolved > 0:
                st.success(
                    f"✅ Resolved **{_rap_picks_resolved}** AI pick(s) + **{_rap_bets_resolved}** tracked bet(s): "
                    f"✅ {_rap_wins} WIN · ❌ {_rap_losses} LOSS · 🔄 {_rap_evens} EVEN"
                    + (f" | ⏳ {_rap_pending} still pending (game may not be final)" if _rap_pending > 0 else "")
                )
                # Show per-date breakdown
                _combined_by_date = {}
                for _d, _n in {**_picks_result.get("by_date", {}), **_bets_result.get("by_date", {})}.items():
                    _combined_by_date[_d] = _combined_by_date.get(_d, 0) + _n
                if _combined_by_date:
                    for _d in sorted(_combined_by_date):
                        st.caption(f"  📅 {_d}: {_combined_by_date[_d]} resolved")
            elif _rap_errors and not _rap_pending:
                st.info("ℹ️ No picks were resolved. See errors below.")
            else:
                st.info(
                    "ℹ️ No pending picks found to resolve. "
                    "Either all picks are already resolved, today's games aren't final yet, "
                    "or no picks have been logged."
                )
            if _rap_errors:
                with st.expander(f"⚠️ {len(_rap_errors)} resolution error(s) (click to expand)"):
                    for _e in _rap_errors:
                        st.caption(_e)
        except Exception as _rap_exc:
            if _jl_loader_rap is not None:
                _jl_loader_rap.empty()
            st.error(f"❌ Resolution failed: {_rap_exc}")

    st.divider()

    # ── 🗓️ Resolve / Re-check by Date ────────────────────────────────
    st.markdown("### 🗓️ Resolve / Re-check Picks by Date")
    st.caption(
        "Select a past night to view its picks and re-verify results against "
        "actual NBA stats — useful when bets weren't resolved automatically."
    )

    _rbd_available_dates = get_analysis_pick_dates(days=30)
    _rbd_today = _tracker_today_iso()
    if _rbd_today not in _rbd_available_dates:
        _rbd_has_today = bool(load_analysis_picks_for_date(_rbd_today)) or bool(st.session_state.get("analysis_results"))
        if _rbd_has_today:
            _rbd_available_dates = [_rbd_today] + _rbd_available_dates

    if not _rbd_available_dates:
        st.info("ℹ️ No pick history found in the last 30 days. Run Neural Analysis to log picks.")
    else:
        _rbd_date_options = _rbd_available_dates  # already sorted newest-first
        _rbd_selected = st.selectbox(
            "📅 Select date",
            options=_rbd_date_options,
            index=0,
            key="rbd_date_selectbox",
            help="Choose a past night to inspect and resolve.",
        )

        # Load all picks for the selected date (pending AND already resolved)
        _rbd_picks = load_analysis_picks_for_date(_rbd_selected)

        if not _rbd_picks:
            st.info(f"No picks logged for {_rbd_selected}.")
        else:
            # Summary line
            _rbd_w = sum(1 for p in _rbd_picks if p.get("result") == "WIN")
            _rbd_l = sum(1 for p in _rbd_picks if p.get("result") == "LOSS")
            _rbd_even = sum(1 for p in _rbd_picks if p.get("result") == "EVEN")
            _rbd_pend = sum(1 for p in _rbd_picks if not p.get("result"))
            _rbd_res = _rbd_w + _rbd_l
            _rbd_wr_str = f" · **{_rbd_w / max(_rbd_res, 1) * 100:.0f}% win rate**" if _rbd_res > 0 else ""
            st.markdown(
                f"**{len(_rbd_picks)} picks** for {_rbd_selected}{_rbd_wr_str}  \n"
                f"✅ {_rbd_w} WIN · ❌ {_rbd_l} LOSS · 🔄 {_rbd_even} EVEN · ⏳ {_rbd_pend} Pending"
            )

            # Quick picks table
            _rbd_rows = []
            for _p in _rbd_picks:
                _res = _p.get("result") or "⏳ Pending"
                _res_icon = {"WIN": "✅ WIN", "LOSS": "❌ LOSS", "EVEN": "🔄 EVEN"}.get(_res, "⏳ Pending")
                _actual = _p.get("actual_value")
                _actual_str = f"{_actual:.1f}" if _actual is not None else "—"
                _rbd_rows.append({
                    "Player": _p.get("player_name", "—"),
                    "Stat": _p.get("stat_type", "—"),
                    "Line": _p.get("prop_line", "—"),
                    "Dir": _p.get("direction", "—"),
                    "Actual": _actual_str,
                    "Result": _res_icon,
                    "Tier": _p.get("tier", "—"),
                })
            st.dataframe(
                _rbd_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Player": st.column_config.TextColumn("Player", width="medium"),
                    "Stat":   st.column_config.TextColumn("Stat",   width="small"),
                    "Line":   st.column_config.NumberColumn("Line",  format="%.1f"),
                    "Dir":    st.column_config.TextColumn("Dir",    width="small"),
                    "Actual": st.column_config.TextColumn("Actual", width="small"),
                    "Result": st.column_config.TextColumn("Result", width="small"),
                    "Tier":   st.column_config.TextColumn("Tier",   width="small"),
                },
            )

            # Resolve / Re-check button for this date
            _rbd_resolve_btn = st.button(
                f"🔄 Resolve / Re-check {_rbd_selected}",
                key="rbd_resolve_btn",
                type="primary",
                help=f"Retrieve actual NBA stats for {_rbd_selected} and update WIN/LOSS/EVEN for all picks on that night.",
            )

            if _rbd_resolve_btn:
                _jl_loader_rbd = None
                if _JOSEPH_LOADING_AVAILABLE:
                    _jl_loader_rbd = joseph_loading_placeholder(f"Resolving picks for {_rbd_selected}")
                try:
                    # Resolve all_analysis_picks for this date (re-checks even resolved rows)
                    _rbd_picks_res  = resolve_all_analysis_picks(date_str=_rbd_selected)
                    # Also resolve the bets table for this date
                    _rbd_bets_cnt, _rbd_bets_errs = auto_resolve_bet_results(date_str=_rbd_selected)

                    if _jl_loader_rbd is not None:
                        _jl_loader_rbd.empty()

                    _rbd_picks_cnt = _rbd_picks_res.get("resolved", 0)
                    _rbd_total = _rbd_picks_cnt + _rbd_bets_cnt
                    _rbd_wins  = _rbd_picks_res.get("wins", 0)
                    _rbd_loss  = _rbd_picks_res.get("losses", 0)
                    _rbd_evn   = _rbd_picks_res.get("evens", 0)
                    _rbd_errs  = _rbd_picks_res.get("errors", []) + _rbd_bets_errs
                    _rbd_errs  = list(dict.fromkeys(_rbd_errs))

                    if _rbd_total > 0:
                        st.success(
                            f"✅ Resolved **{_rbd_picks_cnt}** AI pick(s) + **{_rbd_bets_cnt}** tracked bet(s) for {_rbd_selected}: "
                            f"✅ {_rbd_wins} WIN · ❌ {_rbd_loss} LOSS · 🔄 {_rbd_evn} EVEN"
                        )
                        st.rerun()
                    else:
                        st.warning(
                            f"⚠️ No picks were resolved for {_rbd_selected}. "
                            "The game log may not yet be available, or no matching players were found."
                        )
                    if _rbd_errs:
                        with st.expander(f"⚠️ {len(_rbd_errs)} error(s)"):
                            for _e in _rbd_errs:
                                st.caption(_e)
                except Exception as _rbd_exc:
                    if _jl_loader_rbd is not None:
                        _jl_loader_rbd.empty()
                    st.error(f"❌ Resolution failed: {_rbd_exc}")

    st.divider()

    # ── Shared merged pick universe (same source as Health) ───────────
    _all_picks_universe = _build_merged_pick_universe(_all_picks_scope)
    db_all_picks = list(_all_picks_universe["analysis_rows"])
    _pipeline_as_picks = list(_all_picks_universe["pipeline_added"])
    _pipeline_bets_raw = list(_all_picks_universe["health_side_bets"])
    _pipeline_skip_ai_overlap = _all_picks_universe["pipeline_skip_ai_overlap"]
    _combined_picks = list(_all_picks_universe["combined"])
    _today_str = _tracker_today_iso()

    def _safe_line_str(pick):
        """Normalise prop_line / line to a rounded string for dedup keys."""
        try:
            return str(round(float(pick.get("prop_line") or pick.get("line") or 0), 2))
        except (ValueError, TypeError):
            return "0"

    def _dedup_key(pick):
        return (
            (pick.get("player_name") or "").strip().lower(),
            (pick.get("stat_type") or "").strip().lower(),
            _safe_line_str(pick),
            (pick.get("direction") or "").strip().upper(),
            _canonical_pick_date(pick),
            (pick.get("platform") or "").strip().lower(),
            (pick.get("source") or "").strip().lower(),
            (pick.get("tier") or "").strip().lower(),
        )

    # ── Tier Filter & Bet Classification Filter ───────────────────────────
    _ap_filter_col1, _ap_filter_col2 = st.columns(2)
    with _ap_filter_col1:
        _ap_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[],
            key="ap_tier_filter",
            help="Show only picks matching the selected tiers. Leave empty to show all tiers.",
        )
    with _ap_filter_col2:
        _ap_bet_type_filter = st.multiselect(
            "Bet Classification",
            ["Goblin", "Demon", "50/50", "Standard", "Normal", "Fantasy", "Joseph Pick"],
            default=[],
            key="ap_bet_type_filter",
            help="Filter by bet classification. Leave empty to show all.",
        )

    _ap_bt_values = {
        "50_50" if bt == "50/50" else "joseph_pick" if bt == "Joseph Pick" else bt.lower()
        for bt in _ap_bet_type_filter
    }

    # Apply filters to the combined dataset used for aggregate metrics
    all_picks_data = _apply_global_filters([p for p in _combined_picks if _platform_filter_fn(p)])
    if _ap_tier_filter:
        _ap_tier_names = [t.split(" ")[0] for t in _ap_tier_filter]
        all_picks_data = [p for p in all_picks_data if p.get("tier") in _ap_tier_names]
    if _ap_bet_type_filter:
        _ap_bt_filter_set = set(_ap_bt_values)
        all_picks_data = [p for p in all_picks_data if _normalized_bet_type(p) in _ap_bt_filter_set]

    # Build today's live-session picks from current analysis results.
    session_picks = []
    for _r in st.session_state.get("analysis_results", []) or []:
        session_picks.append(
            {
                "player_name": _r.get("player_name", ""),
                "team": _r.get("player_team", _r.get("team", "")),
                "stat_type": _r.get("stat_type", ""),
                "prop_line": float(_r.get("line", 0) or 0),
                "direction": _r.get("direction", "OVER"),
                "platform": _r.get("platform", "SmartAI-Auto"),
                "confidence_score": float(_r.get("confidence_score", 0) or 0),
                "edge_percentage": float(_r.get("edge_percentage", 0) or 0),
                "tier": _r.get("tier", "Bronze"),
                "bet_type": _r.get("bet_type", "normal"),
                "pick_date": _today_str,
                "bet_date": _today_str,
                "result": None,
                "notes": "Live session pick (not yet persisted).",
            }
        )

    session_picks = [
        p for p in session_picks
        if _in_bet_date_window(p, _all_picks_scope, "pick_date")
    ]

    if not all_picks_data:
        st.info(
            "📭 No picks to display. Run **Neural Analysis** to generate picks — "
            "all outputs are automatically stored here for tracking."
        )
    else:
        # ── Compute summary stats ──────────────────────────────────────
        _ap_total   = len(all_picks_data)
        _ap_wins    = sum(1 for p in all_picks_data if p.get("result") == "WIN")
        _ap_losses  = sum(1 for p in all_picks_data if p.get("result") == "LOSS")
        _ap_evens  = sum(1 for p in all_picks_data if p.get("result") == "EVEN")
        _ap_pending = sum(1 for p in all_picks_data if not p.get("result"))
        _ap_resolved = _ap_wins + _ap_losses
        _ap_win_rate = round(_ap_wins / max(_ap_resolved, 1) * 100, 1) if _ap_resolved > 0 else 0.0
        _ap_avg_edge = (
            sum(abs(float(p.get("edge_percentage", 0) or 0)) for p in all_picks_data) / _ap_total
            if _ap_total > 0 else 0.0
        )
        _ap_avg_conf = (
            sum(float(p.get("confidence_score", 0) or 0) for p in all_picks_data) / _ap_total
            if _ap_total > 0 else 0.0
        )

        # Reconciliation diagnostics for source-count discrepancies.
        _dbg_db_scope = list(db_all_picks)
        _dbg_pipeline_scope = list(_pipeline_as_picks)
        _dbg_health_scope = list(_pipeline_bets_raw)
        with st.expander("🔎 Count Reconciliation", expanded=False):
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("Health-side Bets", len(_dbg_health_scope))
            _c2.metric("Analysis Rows", len(_dbg_db_scope))
            _c3.metric("Pipeline Added", len(_dbg_pipeline_scope))
            _c4.metric("Final All Picks", _ap_total)
            st.caption(
                "Final All Picks = deduplicated union of analysis rows + pipeline rows; "
                f"{_pipeline_skip_ai_overlap} SmartAI tracker rows were skipped because matching analysis rows already exist."
            )

        # Streak: walk most-recent resolved picks to find consecutive W/L run
        _ap_streak = 0
        _ap_resolved_sorted = sorted(
            [p for p in all_picks_data if p.get("result") in ("WIN", "LOSS")],
            key=lambda p: p.get("pick_date", ""),
            reverse=True,
        )
        if _ap_resolved_sorted:
            _ap_streak_result = _ap_resolved_sorted[0].get("result")
            _ap_streak = 1 if _ap_streak_result == "WIN" else -1
            for _ap_sp in _ap_resolved_sorted[1:]:
                if _ap_sp.get("result") == _ap_streak_result:
                    _ap_streak += 1 if _ap_streak_result == "WIN" else -1
                else:
                    break

        # Best platform by win rate (min 3 resolved picks)
        _ap_plat_perf: dict = {}
        for _p in all_picks_data:
            _plat = str(_p.get("platform") or "Unknown")
            _res  = _p.get("result")
            if _plat not in _ap_plat_perf:
                _ap_plat_perf[_plat] = {"wins": 0, "total": 0}
            if _res in ("WIN", "LOSS"):
                _ap_plat_perf[_plat]["total"] += 1
                if _res == "WIN":
                    _ap_plat_perf[_plat]["wins"] += 1
        _ap_best_platform = ""
        _ap_sorted_plats = sorted(
            [(p, d["wins"] / max(d["total"], 1)) for p, d in _ap_plat_perf.items() if d["total"] >= 3],
            key=lambda x: x[1], reverse=True,
        )
        if _ap_sorted_plats:
            _ap_best_platform = _ap_sorted_plats[0][0]

        # ── Summary Cards (same style as AI Picks / Model Health) ─────
        st.markdown(
            get_summary_cards_html(
                total=_ap_total,
                wins=_ap_wins,
                losses=_ap_losses,
                evens=_ap_evens,
                pending=_ap_pending,
                win_rate=_ap_win_rate,
                streak=_ap_streak,
                best_platform=_ap_best_platform,
                total_label="Total Picks",
            ),
            unsafe_allow_html=True,
        )
        st.caption(
            "What this count means: All Picks uses the same merged pick universe as Health. "
            f"Scope source = {len(_dbg_db_scope)} persisted analysis rows + {len(_dbg_pipeline_scope)} pipeline/tracker rows "
            f"(-{_pipeline_skip_ai_overlap} SmartAI overlaps) = {len(_combined_picks)} merged picks before current platform/search/date/direction filters; "
            f"{_ap_total} currently shown."
        )

        # Model accuracy banner
        if _ap_resolved > 0:
            st.success(
                f"🎯 **Model accuracy:** Predicted **{_ap_wins}/{_ap_resolved}** correctly "
                f"(**{_ap_win_rate:.1f}%**) — {_ap_evens} even(s)"
            )

        # Secondary pick-quality metrics (Avg Edge + Avg Confidence + direction counts)
        _apc1, _apc2, _apc3, _apc4, _apc5 = st.columns([1, 1, 1, 1, 1])
        _apc1.metric("⬆️ OVER", sum(1 for p in all_picks_data if p.get("direction") == "OVER"))
        _apc2.metric("⬇️ UNDER", sum(1 for p in all_picks_data if p.get("direction") == "UNDER"))
        _apc3.metric("Avg Edge", f"{_ap_avg_edge:.1f}%")
        _apc4.metric("Avg Confidence", f"{_ap_avg_conf:.0f}/100")
        with _apc5:
            if all_picks_data:
                _csv_picks = export_bets_csv(all_picks_data)
                st.download_button(
                    "📥 Export CSV",
                    data=_csv_picks,
                    file_name=f"smartai_all_picks_{_tracker_today_iso()}.csv",
                    mime="text/csv",
                    key="export_all_picks_csv",
                    help="Download all picks as a CSV file.",
                )

        st.divider()

        # ── Win Rate by Tier ──────────────────────────────────────────
        with st.expander("🏆 Win Rate by Tier", expanded=True):
            _tier_rows = []
            for _tn in ["Platinum", "Gold", "Silver", "Bronze"]:
                _t_picks = [p for p in all_picks_data if p.get("tier") == _tn]
                if not _t_picks:
                    continue
                _t_w = sum(1 for p in _t_picks if p.get("result") == "WIN")
                _t_l = sum(1 for p in _t_picks if p.get("result") == "LOSS")
                _t_res = _t_w + _t_l
                _tier_rows.append({
                    "Tier": _tn,
                    "Total": _t_res,
                    "Wins": _t_w,
                    "Losses": _t_l,
                    "Win Rate": f"{_t_w / max(_t_res, 1) * 100:.1f}%" if _t_res > 0 else "—",
                })
            if _tier_rows:
                st.markdown(
                    get_styled_stats_table_html(
                        _tier_rows,
                        ["Tier", "Total", "Wins", "Losses", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )
                _tier_spot_cols = st.columns(4)
                _tier_icons = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
                for _ti, _tn in enumerate(["Platinum", "Gold", "Silver", "Bronze"]):
                    _tr = next((r for r in _tier_rows if r["Tier"] == _tn), None)
                    if _tr:
                        _tier_spot_cols[_ti].metric(
                            f"{_tier_icons.get(_tn, '')} {_tn}",
                            _tr["Win Rate"],
                            help=f"{_tn}: {_tr['Wins']}W / {_tr['Losses']}L ({_tr['Total']} total picks)",
                        )
            else:
                st.caption("No tier data yet.")

        # ── Win Rate by Platform ──────────────────────────────────────
        _ap_plat_data: dict = {}
        for _p in all_picks_data:
            _plat = (
                "Smart Pick Pro Platform Picks"
                if _is_ai_auto_bet(_p)
                else _platform_display_name(_p.get("platform") or "Unknown")
            )
            _res  = _p.get("result")
            if _plat not in _ap_plat_data:
                _ap_plat_data[_plat] = {"wins": 0, "losses": 0, "total": 0}
            if _res == "WIN":
                _ap_plat_data[_plat]["wins"] += 1
                _ap_plat_data[_plat]["total"] += 1
            elif _res == "LOSS":
                _ap_plat_data[_plat]["losses"] += 1
                _ap_plat_data[_plat]["total"] += 1
        if _ap_plat_data:
            with st.expander("🎰 Win Rate by Platform", expanded=True):
                _plat_rows = [
                    {
                        "Platform": _plat,
                        "Total":    d["total"],
                        "Wins":     d["wins"],
                        "Win Rate": (
                            f"{d['wins'] / max(d['wins'] + d['losses'], 1) * 100:.1f}%"
                            if d["wins"] + d["losses"] > 0 else "—"
                        ),
                    }
                    for _plat, d in sorted(_ap_plat_data.items())
                ]
                st.markdown(
                    get_styled_stats_table_html(
                        _plat_rows,
                        ["Platform", "Total", "Wins", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )
        else:
            with st.expander("🎰 Win Rate by Platform", expanded=True):
                st.caption("No platform data yet.")

        # ── Win Rate by Stat Type ──────────────────────────────────────
        with st.expander("📐 Win Rate by Stat Type", expanded=False):
            _stat_rows = []
            for _stype in sorted({p.get("stat_type", "unknown") for p in all_picks_data}):
                _s_picks = [p for p in all_picks_data if p.get("stat_type") == _stype]
                _s_w = sum(1 for p in _s_picks if p.get("result") == "WIN")
                _s_l = sum(1 for p in _s_picks if p.get("result") == "LOSS")
                _s_res = sum(1 for p in _s_picks if p.get("result") in ("WIN", "LOSS"))
                _stat_rows.append({
                    "Stat Type": _stype.replace("_", " ").title(),
                    "Total": _s_w + _s_l,
                    "Wins": _s_w,
                    "Win Rate": f"{_s_w / max(_s_res, 1) * 100:.1f}%" if _s_res > 0 else "—",
                })
            if _stat_rows:
                st.markdown(
                    get_styled_stats_table_html(
                        _stat_rows,
                        ["Stat Type", "Total", "Wins", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No stat type data yet.")

        # ── Win Rate by Bet Classification ────────────────────────────
        _ap_bt_data: dict = {}
        for _p in all_picks_data:
            _bt = _normalized_bet_type(_p)
            _res = _p.get("result")
            if _bt not in _ap_bt_data:
                _ap_bt_data[_bt] = {"wins": 0, "losses": 0, "total": 0}
            if _res == "WIN":
                _ap_bt_data[_bt]["wins"] += 1
                _ap_bt_data[_bt]["total"] += 1
            elif _res == "LOSS":
                _ap_bt_data[_bt]["losses"] += 1
                _ap_bt_data[_bt]["total"] += 1
        if _ap_bt_data:
            with st.expander("Win Rate by Bet Classification", expanded=True):
                _bt_rows = [
                    {
                        "Bet Type": _bet_type_display_name(_bt),
                        "Total": d["total"],
                        "Wins": d["wins"],
                        "Losses": d["losses"],
                        "Win Rate": (
                            f"{d['wins'] / max(d['wins'] + d['losses'], 1) * 100:.1f}%"
                            if d["wins"] + d["losses"] > 0 else "—"
                        ),
                    }
                    for _bt, d in sorted(_ap_bt_data.items(), key=lambda item: _bet_type_sort_key(item[0]))
                ]
                st.markdown(
                    get_styled_stats_table_html(
                        _bt_rows,
                        ["Bet Type", "Total", "Wins", "Losses", "Win Rate"],
                    ),
                    unsafe_allow_html=True,
                )

        # ── Model Tier Accuracy placeholder ──────────────────────────
        with st.expander("📊 Model Tier Accuracy", expanded=False):
            st.info(
                "Coming soon — this section will compare predicted tier accuracy "
                "vs actual results over time."
            )

        st.divider()

        # ── Source toggle (controls per-day detail section only) ──────
        ap_source_radio = st.radio(
            "Show detailed picks:",
            ["30-Day History (database)", "Today's Analysis (live session)"],
            horizontal=True,
            key="ap_source_radio",
        )

        # ── Per-day sections ──────────────────────────────────────────
        if ap_source_radio == "30-Day History (database)":
            # Group DB picks by date
            _detail_picks = list(_combined_picks)
            _detail_picks = [
                p for p in _detail_picks
                if _in_bet_date_window(p, _all_picks_scope, "pick_date")
            ]
            if _ap_tier_filter:
                _detail_picks = [p for p in _detail_picks if p.get("tier") in _ap_tier_names]
            if _ap_bet_type_filter:
                _detail_picks = [
                    p for p in _detail_picks
                    if _normalized_bet_type(p) in _ap_bt_values
                ]
            if _detail_picks:
                _by_date_ap: dict = {}
                for _p in _detail_picks:
                    _d = _p.get("pick_date", "Unknown")
                    _by_date_ap.setdefault(_d, []).append(_p)
                for _ap_date in sorted(_by_date_ap.keys(), reverse=True):
                    _day_data = _by_date_ap[_ap_date]
                    _d_w = sum(1 for p in _day_data if p.get("result") == "WIN")
                    _d_l = sum(1 for p in _day_data if p.get("result") == "LOSS")
                    _d_res = _d_w + _d_l
                    _d_wr = f" — {_d_w / max(_d_res,1)*100:.0f}% win rate" if _d_res > 0 else ""
                    with st.expander(
                        f"📅 {_ap_date} · {len(_day_data)} picks · ✅{_d_w} ❌{_d_l}{_d_wr}"
                    ):
                        _ca, _cb = st.columns(2)
                        for _idx, _pick in enumerate(_day_data):
                            # Remap pick_date → bet_date so get_bet_card_html renders date correctly
                            _pick_card = dict(_pick)
                            if "bet_date" not in _pick_card:
                                _pick_card["bet_date"] = _pick_card.get("pick_date", "")
                            _col = _ca if _idx % 2 == 0 else _cb
                            with _col:
                                st.markdown(
                                    get_bet_card_html(_pick_card),
                                    unsafe_allow_html=True,
                                )
            else:
                st.info("📭 No database picks found for this time range.")
        else:
            # Session picks: show all in two-column grid
            _session_detail = list(session_picks)
            if _ap_tier_filter:
                _session_detail = [p for p in _session_detail if p.get("tier") in _ap_tier_names]
            if _ap_bet_type_filter:
                _session_detail = [
                    p for p in _session_detail
                    if _normalized_bet_type(p) in _ap_bt_values
                ]
            if _session_detail:
                _col_a, _col_b = st.columns(2)
                for _idx, _pick in enumerate(_session_detail):
                    _col = _col_a if _idx % 2 == 0 else _col_b
                    with _col:
                        st.markdown(get_bet_card_html(_pick), unsafe_allow_html=True)
            else:
                st.info(
                    "📭 No live session picks to display. Run **Neural Analysis** to generate picks."
                )

# ============================================================
# END SECTION: All Picks Tab
# ============================================================


# ============================================================
# SECTION: Joseph's Bets Tab
# ============================================================

with tab_joseph_bets:
    st.subheader("🎙️ Joseph M. Smith's Bets — Tracker Subset")
    st.markdown(
        "Track all bets placed by Joseph M. Smith — filtered from your bet database. "
        "Joseph's picks are auto-logged from **The Studio** page when he makes SMASH or LEAN calls."
    )

    _j_scope_col1, _j_scope_col2 = st.columns([2, 5])
    with _j_scope_col1:
        _joseph_scope = st.selectbox(
            "Joseph Scope",
            ["Today", "Last 7 Days", "Last 30 Days", "All Time"],
            index=0,
            key="joseph_scope_filter",
            help="Date window for Joseph picks.",
        )
    with _j_scope_col2:
        st.caption("Joseph tab only includes bets tagged as Joseph via source/platform/notes.")

    try:
        _jbt_all = _cached_load_all_bets()
        _jbt_joseph = [b for b in _jbt_all if _is_joseph_bet(b)]
        _jbt_joseph = [b for b in _jbt_joseph if _in_bet_date_window(b, _joseph_scope, "bet_date")]

        if _jbt_joseph:
            # Summary metrics
            _jbt_total = len(_jbt_joseph)
            _jbt_wins = sum(1 for b in _jbt_joseph if str(b.get("result", "")).upper() == "WIN")
            _jbt_losses = sum(1 for b in _jbt_joseph if str(b.get("result", "")).upper() == "LOSS")
            _jbt_pending = sum(1 for b in _jbt_joseph if not b.get("result") or str(b.get("result", "")).upper() not in ("WIN", "LOSS", "EVEN"))
            _jbt_wr = _jbt_wins / max(_jbt_wins + _jbt_losses, 1)

            _jbt_m1, _jbt_m2, _jbt_m3, _jbt_m4 = st.columns(4)
            _jbt_m1.metric("Total Bets", _jbt_total)
            _jbt_m2.metric("Win Rate", f"{_jbt_wr:.1%}" if (_jbt_wins + _jbt_losses) > 0 else "—")
            _jbt_m3.metric("Wins / Losses", f"{_jbt_wins}W / {_jbt_losses}L")
            _jbt_m4.metric("Pending", _jbt_pending)
            st.caption("What this count means: Joseph counts only Joseph-tagged tracker bets from the bets table. It is a subset of Health.")

            st.markdown("---")

            # Show bet cards
            st.markdown(get_bet_card_css(), unsafe_allow_html=True)
            for _jb in sorted(_jbt_joseph, key=lambda x: x.get("bet_date", ""), reverse=True)[:30]:
                _card = get_bet_card_html(_jb)
                if _card:
                    st.markdown(_card, unsafe_allow_html=True)
                else:
                    _jb_name = _jb.get("player_name", "Unknown")
                    _jb_stat = _jb.get("stat_type", "")
                    _jb_dir = _jb.get("direction", "")
                    _jb_line = _jb.get("prop_line", "")
                    _jb_result = _jb.get("result", "pending")
                    _jb_emoji = _RESULT_EMOJI.get(str(_jb_result).upper() if _jb_result else None, "⏳")
                    st.markdown(
                        f"**{_jb_name}** — {_jb_stat} {_jb_dir} {_jb_line} | "
                        f"Result: {_jb_emoji} {_jb_result or 'pending'}"
                    )
        else:
            st.info(
                "🎙️ No Joseph M. Smith bets found yet.\n\n"
                "Go to **🎙️ The Studio** and run Neural Analysis — "
                "Joseph's SMASH and LEAN picks will be auto-logged here."
            )
    except Exception as _jbt_err:
        _logger.warning("Failed to load Joseph's bets: %s", _jbt_err)
        st.warning("Could not load Joseph's bet history.")

# ============================================================
# END SECTION: Joseph's Bets Tab
# ============================================================

# ============================================================
# SECTION: Auto-Resolve Tab
# ============================================================

with tab_auto_resolve:
    st.subheader("🤖 Auto-Resolve — Get Actual Stats & Mark Results")
    st.markdown(
        "Automatically retrieve actual player stats and mark pending bets "
        "as WIN / LOSS / EVEN. Use **⚡ Resolve Now** to resolve today's completed games instantly."
    )

    # ── Resolve Now (today's bets) ────────────────────────────────────
    st.markdown("### ⚡ Resolve Today's Bets")
    st.caption("Checks live scores for Final games and resolves today's pending bets immediately.")

    _rt_col1, _rt_col2 = st.columns([1, 1])
    with _rt_col1:
        resolve_today_btn = st.button(
            "⚡ Resolve Now",
            type="primary",
            help="Get live game status and resolve today's bets where games are Final",
        )
    with _rt_col2:
        regrade_today_btn = st.button(
            "🩹 Regrade Today's Results",
            help="Recompute already graded bets from final stats and fix incorrect WIN/LOSS/EVEN results.",
        )

    if resolve_today_btn:
        _jl_loader_today = None
        if _JOSEPH_LOADING_AVAILABLE:
            _jl_loader_today = joseph_loading_placeholder("Checking today's games and resolving completed bets")
        try:
            from tracking.bet_tracker import resolve_todays_bets
            _result = resolve_todays_bets()
            if _jl_loader_today is not None:
                _jl_loader_today.empty()
            if _result["resolved"] > 0:
                st.success(
                    f"✅ Resolved **{_result['resolved']}** bet(s) today: "
                    f"**{_result['wins']}** WIN · **{_result['losses']}** LOSS · **{_result['evens']}** EVEN"
                )
                st.rerun()
            else:
                st.info(
                    f"ℹ️ No bets resolved. "
                    f"Games may still be in progress or not started. "
                    f"Still pending: {_result.get('pending', 0)}"
                )
            if _result.get("errors"):
                st.warning("⚠️ " + " | ".join(_result["errors"][:3]))
                if len(_result["errors"]) > 3:
                    with st.expander(f"See all {len(_result['errors'])} issue(s)"):
                        for err in _result["errors"]:
                            st.markdown(f"- {err}")
        except Exception as _err:
            if _jl_loader_today is not None:
                _jl_loader_today.empty()
            st.error(f"❌ Resolve failed: {_err}")

    if regrade_today_btn:
        _jl_loader_regrade = None
        if _JOSEPH_LOADING_AVAILABLE:
            _jl_loader_regrade = joseph_loading_placeholder("Regrading today's resolved bets against final box scores")
        try:
            _rg = regrade_bets_for_date(_tracker_today_iso())
            if _jl_loader_regrade is not None:
                _jl_loader_regrade.empty()

            if _rg.get("corrected", 0) > 0:
                st.success(
                    f"✅ Regraded **{_rg['checked']}** bet(s); corrected **{_rg['corrected']}**. "
                    f"Unchanged: {_rg.get('unchanged', 0)} · Skipped: {_rg.get('skipped', 0)}"
                )
                if _rg.get("changes"):
                    with st.expander(f"View {len(_rg['changes'])} correction(s)"):
                        for _chg in _rg["changes"][:100]:
                            st.markdown(
                                f"- #{_chg.get('bet_id')} {_chg.get('player')}: "
                                f"{_chg.get('old_result')} → {_chg.get('new_result')} "
                                f"({float(_chg.get('old_actual', 0)):.2f} → {float(_chg.get('new_actual', 0)):.2f})"
                            )
                _reload_bets()
                st.rerun()
            elif _rg.get("checked", 0) > 0:
                st.info(
                    f"ℹ️ Regrade checked **{_rg['checked']}** bet(s). "
                    "No corrections were needed."
                )
            else:
                st.warning(
                    "⚠️ No graded bets could be rechecked yet (likely waiting for final box scores)."
                )

            if _rg.get("errors"):
                with st.expander(f"⚠️ {len(_rg['errors'])} regrade issue(s)"):
                    for _err in _rg["errors"][:100]:
                        st.markdown(f"- {_err}")
        except Exception as _err:
            if _jl_loader_regrade is not None:
                _jl_loader_regrade.empty()
            st.error(f"❌ Regrade failed: {_err}")

    st.divider()

    # ── Live Status Section ────────────────────────────────────────────
    st.markdown("### 🔄 Live Bet Status — Today's Picks")
    _today_bets_all = load_all_bets(exclude_linked=False)
    _today_str_ar = _tracker_today_iso()
    _today_bets = [
        b for b in _today_bets_all
        if b.get("bet_date") == _today_str_ar and _platform_filter_fn(b)
    ]
    _today_pending = [b for b in _today_bets if not b.get("result")]

    auto_refresh = st.checkbox("🔁 Auto-refresh live status (every 60s)", value=False)

    if _today_bets:
        if _today_pending:
            try:
                from tracking.bet_tracker import get_live_bet_status
                _live_bets = get_live_bet_status(_today_pending)
            except Exception:
                _live_bets = _today_pending

            _col_a, _col_b = st.columns(2)
            for _idx, _lb in enumerate(_live_bets):
                _col = _col_a if _idx % 2 == 0 else _col_b
                with _col:
                    st.markdown(get_bet_card_html(_lb, show_live_status=True), unsafe_allow_html=True)

            # Already resolved today
            _today_resolved = [b for b in _today_bets if b.get("result")]
            if _today_resolved:
                st.markdown("**✅ Already Resolved Today:**")
                _cr_a, _cr_b = st.columns(2)
                for _idx, _rb in enumerate(_today_resolved):
                    _col = _cr_a if _idx % 2 == 0 else _cr_b
                    with _col:
                        st.markdown(get_bet_card_html(_rb), unsafe_allow_html=True)
        else:
            st.markdown("**Today's Bets (All Resolved):**")
            _cr_a, _cr_b = st.columns(2)
            for _idx, _rb in enumerate(_today_bets):
                _col = _cr_a if _idx % 2 == 0 else _cr_b
                with _col:
                    st.markdown(get_bet_card_html(_rb), unsafe_allow_html=True)
    else:
        st.info("No bets logged for today yet.")

    if auto_refresh:
        # Use a short countdown instead of blocking time.sleep(60) which
        # freezes the entire Streamlit app. st.empty + rerun achieves the
        # same periodic refresh without blocking the event loop.
        _refresh_placeholder = st.empty()
        _refresh_placeholder.info("🔄 Auto-refresh enabled — page will refresh in ~60 seconds. Uncheck to stop.")
        _refresh_start = _time.time()
        # Non-blocking: check every 5 seconds if 60s has elapsed
        # This allows Streamlit to remain responsive to user interactions
        if st.session_state.get("_auto_refresh_ts", 0) == 0:
            st.session_state["_auto_refresh_ts"] = _time.time()
        _elapsed = _time.time() - st.session_state.get("_auto_refresh_ts", _time.time())
        if _elapsed >= 60:
            st.session_state["_auto_refresh_ts"] = _time.time()
            # Attempt to resolve any new Final games before refreshing
            try:
                from tracking.bet_tracker import resolve_todays_bets as _rtr
                _rtr_result = _rtr()
                if _rtr_result.get("resolved", 0) > 0:
                    _reload_bets()
                    st.toast(
                        f"🔄 Auto-resolved {_rtr_result['resolved']} bet(s) "
                        f"({_rtr_result['wins']}W / {_rtr_result['losses']}L)"
                    )
                if _rtr_result.get("errors"):
                    for _rtr_err in _rtr_result["errors"]:
                        logging.getLogger(__name__).warning(f"[BetTrackerPage] resolve: {_rtr_err}")
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[BetTrackerPage] Unexpected error: {_exc}")
            st.rerun()
    else:
        st.session_state.pop("_auto_refresh_ts", None)

    st.divider()

    # ── Resolve Past Bets ─────────────────────────────────────────────
    st.markdown("### 🗓️ Resolve Past Bets")
    all_bets_for_resolve = load_all_bets(exclude_linked=False)
    pending_all = [
        b for b in all_bets_for_resolve
        if not b.get("result") and b.get("bet_date", "") < _today_str_ar and _platform_filter_fn(b)
    ]

    if not pending_all:
        st.info("✅ No past pending bets found.")
    else:
        st.markdown(f"**{len(pending_all)} past pending bet(s):**")
        _pa, _pb = st.columns(2)
        for _idx, _pb_bet in enumerate(pending_all):
            _col = _pa if _idx % 2 == 0 else _pb
            with _col:
                st.markdown(get_bet_card_html(_pb_bet), unsafe_allow_html=True)

    col_date, col_btn = st.columns([2, 1])
    with col_date:
        yesterday_dt = _tracker_today_date() - datetime.timedelta(days=1)
        resolve_date = st.date_input(
            "Date to resolve",
            value=yesterday_dt,
            help="Bets with this date that still have no result will be auto-resolved.",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        resolve_btn = st.button(
            "🔄 Get Actual Stats & Auto-Resolve",
            type="primary",
            width="stretch",
        )

    if resolve_btn:
        _jl_loader_date = None
        if _JOSEPH_LOADING_AVAILABLE:
            _jl_loader_date = joseph_loading_placeholder(f"Retrieving actual stats for {resolve_date.isoformat()}")
        try:
            resolved, errors = auto_resolve_bet_results(date_str=resolve_date.isoformat())
        finally:
            if _jl_loader_date is not None:
                _jl_loader_date.empty()

        if resolved > 0:
            try:
                save_daily_snapshot(resolve_date.isoformat())
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[BetTrackerPage] Unexpected error: {_exc}")
            st.success(f"✅ Auto-resolved **{resolved}** bet(s) for {resolve_date.isoformat()}.")
            st.rerun()
        else:
            st.warning(f"⚠️ No bets resolved for {resolve_date.isoformat()}.")

        if errors:
            with st.expander(f"⚠️ {len(errors)} error(s) during auto-resolve"):
                for err in errors:
                    st.markdown(f"- {err}")

    st.divider()
    st.markdown("### 🔄 Resolve All Pending Bets")
    st.markdown(
        "Resolves **every** unresolved bet in your tracker — manual bets, AI picks, "
        "and bets from any platform or date."
    )
    resolve_all_btn = st.button(
        "🔄 Resolve All Pending Bets",
        type="primary",
        help="Retrieve actual NBA stats for every pending bet regardless of date.",
    )

    if resolve_all_btn:
        _jl_loader_all = None
        if _JOSEPH_LOADING_AVAILABLE:
            _jl_loader_all = joseph_loading_placeholder("Resolving all pending bets — this may take a moment")
        try:
            _all_result = resolve_all_pending_bets()

            if _jl_loader_all is not None:
                _jl_loader_all.empty()

            _all_resolved = _all_result.get("resolved", 0)
            _all_errors   = _all_result.get("errors", [])
            _by_date      = _all_result.get("by_date", {})
            if _all_resolved > 0:
                st.success(
                    f"✅ Resolved **{_all_resolved}** bet(s) — "
                    f"{_all_result.get('wins', 0)} W / "
                    f"{_all_result.get('losses', 0)} L / "
                    f"{_all_result.get('evens', 0)} Even"
                )
                if _by_date:
                    for _d, _cnt in sorted(_by_date.items()):
                        st.markdown(f"  • **{_d}**: {_cnt} resolved")
                st.rerun()
            else:
                st.info("No pending bets found to resolve, or all bets are already resolved.")

            if _all_errors:
                st.warning("⚠️ " + " | ".join(_all_errors[:3]))
                if len(_all_errors) > 3:
                    with st.expander(f"See all {len(_all_errors)} error(s) during resolve-all"):
                        for err in _all_errors:
                            st.markdown(f"- {err}")
        except Exception as _resolve_all_err:
            if _jl_loader_all is not None:
                _jl_loader_all.empty()
            _resolve_err_str = str(_resolve_all_err)
            if "WebSocketClosedError" not in _resolve_err_str and "StreamClosedError" not in _resolve_err_str:
                st.error(f"❌ Resolve all failed: {_resolve_all_err}")

# ============================================================
# END SECTION: Auto-Resolve Tab
# ============================================================


# ============================================================
# SECTION: My Bets Tab (Styled Cards)
# ============================================================

with tab_bets:
    st.subheader("📋 My Bets")

    # ── Filter Pills ──────────────────────────────────────────────
    filter_choice = st.radio(
        "Filter bets",
        ["All", "Wins Only", "Losses Only", "Pending", "Platinum", "Gold", "Silver", "Bronze"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # ── Bet Classification Filter ─────────────────────────────────
    _bets_bet_type_filter = st.multiselect(
        "Bet Classification",
        ["Standard", "Goblin", "Normal", "Fantasy"],
        default=[],
        key="bets_bet_type_filter",
        help="Filter by bet classification. Leave empty to show all.",
    )

    _platform_terms = []
    for _sel in platform_filter_selections:
        if _sel == "🟢 PrizePicks":
            _platform_terms.append("prizepicks")
        elif _sel == "🟣 Underdog Fantasy":
            _platform_terms.append("underdog")
        elif _sel == "🔵 DraftKings Pick6":
            _platform_terms.extend(["draftkings", "pick6", "dk"])
        elif _sel == "🤖 Smart Pick Pro Platform Picks":
            _platform_terms.extend(["smartai-auto", "smart pick pro"])

    _start_date = None
    _end_date = None
    if _date_range and len(_date_range) == 2:
        _start_date = _date_range[0].isoformat()
        _end_date = _date_range[1].isoformat()

    _result_filter = None
    _tier_filter = None
    if filter_choice == "Wins Only":
        _result_filter = "WIN"
    elif filter_choice == "Losses Only":
        _result_filter = "LOSS"
    elif filter_choice == "Pending":
        _result_filter = "PENDING"
    elif filter_choice in ("Platinum", "Gold", "Silver", "Bronze"):
        _tier_filter = filter_choice

    _bet_type_filter_values = [bt.lower() for bt in _bets_bet_type_filter] if _bets_bet_type_filter else None

    _common_filter_args = {
        "exclude_linked": True,
        "player_search": _player_search.strip() if _player_search else None,
        "start_date": _start_date,
        "end_date": _end_date,
        "direction": None if _direction_filter == "All" else _direction_filter,
        "platform_terms": _platform_terms,
        "result_filter": _result_filter,
        "tier_filter": _tier_filter,
        "bet_types": _bet_type_filter_values,
    }

    _summary = get_bets_summary(**_common_filter_args)
    _w = _summary.get("wins", 0)
    _l = _summary.get("losses", 0)
    _p = _summary.get("evens", 0)
    _pend = _summary.get("pending", 0)
    _wr = round(_w / max(_w + _l, 1) * 100, 1)

    st.markdown(
        get_summary_cards_html(
            total=_summary.get("total", 0),
            wins=_w,
            losses=_l,
            evens=_p,
            pending=_pend,
            win_rate=_wr,
        ),
        unsafe_allow_html=True,
    )

    if _summary.get("total", 0) == 0:
        st.info("No bets match the current filters. Adjust filters or log a new bet.")
    else:
        _paging_col1, _paging_col2, _paging_col3 = st.columns([1, 1, 3])
        with _paging_col1:
            _page_size = st.selectbox("Rows per page", [25, 50, 100, 200], index=1, key="my_bets_page_size")

        _filter_signature = json.dumps(
            {
                "player": _common_filter_args["player_search"],
                "start": _start_date,
                "end": _end_date,
                "dir": _common_filter_args["direction"],
                "platform": _platform_terms,
                "result": _result_filter,
                "tier": _tier_filter,
                "types": _bet_type_filter_values,
                "page_size": _page_size,
            },
            sort_keys=True,
        )

        _prev_signature = st.session_state.get("my_bets_filter_signature")
        if _prev_signature != _filter_signature:
            st.session_state["my_bets_page"] = 1
            st.session_state["my_bets_filter_signature"] = _filter_signature

        _total_rows = int(_summary.get("total", 0))
        _total_pages = max(1, (_total_rows + _page_size - 1) // _page_size)
        _current_page = int(st.session_state.get("my_bets_page", 1))
        _current_page = max(1, min(_current_page, _total_pages))
        st.session_state["my_bets_page"] = _current_page

        with _paging_col2:
            _new_page = st.number_input(
                "Page",
                min_value=1,
                max_value=_total_pages,
                value=_current_page,
                step=1,
                key="my_bets_page_input",
            )
            if int(_new_page) != _current_page:
                st.session_state["my_bets_page"] = int(_new_page)
                st.rerun()

        _offset = (_current_page - 1) * _page_size
        filtered_bets = load_bets_page(limit=_page_size, offset=_offset, **_common_filter_args)

        with _paging_col3:
            _start_row = _offset + 1 if _total_rows > 0 else 0
            _end_row = min(_offset + len(filtered_bets), _total_rows)
            st.markdown(
                f"**Showing {_start_row}-{_end_row} of {_total_rows} bet(s)** "
                f"(page {_current_page}/{_total_pages}, filter: {filter_choice})"
            )

        # ── Export CSV & Edit/Delete buttons ──────────────────────────
        _export_col, _edit_col, _delete_col = st.columns([1, 1, 1])
        with _export_col:
            if filtered_bets:
                _csv_data = export_bets_csv(filtered_bets)
                st.download_button(
                    "📥 Export Page to CSV",
                    data=_csv_data,
                    file_name=f"smartai_bets_page_{_current_page}_{_tracker_today_iso()}.csv",
                    mime="text/csv",
                    key="export_my_bets_csv",
                    help="Download currently visible page bets as a CSV file.",
                )

        with _edit_col:
            _all_bet_labels = {
                b.get("id", b.get("bet_id", idx)): (
                    f"#{b.get('id', b.get('bet_id', idx))} — {b.get('player_name', '?')} "
                    f"{b.get('direction', '')} {b.get('prop_line', '')} {str(b.get('stat_type', '')).title()}"
                )
                for idx, b in enumerate(filtered_bets)
            }
            if _all_bet_labels:
                with st.expander("✏️ Edit a Bet", expanded=False):
                    with st.form("edit_bet_form_bt"):
                        _edit_bet_id = st.selectbox(
                            "Select Bet to Edit",
                            options=list(_all_bet_labels.keys()),
                            format_func=lambda x: _all_bet_labels[x],
                            key="edit_bet_select",
                        )
                        _edit_line = st.number_input("New Line", min_value=0.0, max_value=200.0, value=0.0, step=0.5, key="edit_line")
                        _edit_dir = st.selectbox("New Direction", ["—", "OVER", "UNDER"], key="edit_dir")
                        _edit_plat = st.selectbox(
                            "New Platform",
                            ["—", "PrizePicks", "Underdog Fantasy", "DraftKings Pick6"],
                            key="edit_plat",
                        )
                        _edit_notes = st.text_input("New Notes", key="edit_notes")
                        _edit_submit = st.form_submit_button("💾 Save Changes", type="primary")

                    if _edit_submit and _edit_bet_id:
                        _updates = {}
                        if _edit_line > 0:
                            _updates["prop_line"] = _edit_line
                        if _edit_dir != "—":
                            _updates["direction"] = _edit_dir
                        if _edit_plat != "—":
                            _updates["platform"] = _edit_plat
                        if _edit_notes.strip():
                            _updates["notes"] = _edit_notes.strip()
                        if _updates:
                            _ok, _msg = update_bet_fields(_edit_bet_id, _updates)
                            if _ok:
                                st.success(f"✅ {_msg}")
                                _reload_bets()
                                st.rerun()
                            else:
                                st.error(f"❌ {_msg}")
                        else:
                            st.warning("No fields to update. Enter at least one new value.")

        with _delete_col:
            if _all_bet_labels:
                with st.expander("🗑️ Delete a Bet", expanded=False):
                    with st.form("delete_bet_form_bt"):
                        _del_bet_id = st.selectbox(
                            "Select Bet to Delete",
                            options=list(_all_bet_labels.keys()),
                            format_func=lambda x: _all_bet_labels[x],
                            key="delete_bet_select",
                        )
                        st.warning("⚠️ This action cannot be undone. An audit record will be saved.")
                        _del_submit = st.form_submit_button("🗑️ Confirm Delete", type="primary")

                    if _del_submit and _del_bet_id:
                        _ok, _msg = delete_bet(_del_bet_id)
                        if _ok:
                            st.success(f"✅ {_msg}")
                            _reload_bets()
                            st.rerun()
                        else:
                            st.error(f"❌ {_msg}")

        st.divider()

        # ── Mark a Result ─────────────────────────────────────────────
        pending_bets = [b for b in filtered_bets if not b.get("result")]
        if pending_bets:
            with st.expander("✅ Mark a Result", expanded=False):
                pending_labels = {
                    b.get("id", b.get("bet_id", idx)): (
                        f"#{b.get('id', b.get('bet_id', idx))} — {b.get('player_name', '?')} "
                        f"{b.get('direction', '')} {b.get('prop_line', '')} {str(b.get('stat_type', '')).title()} "
                        f"({b.get('platform', '?')}, {b.get('bet_date', '')})"
                    )
                    for idx, b in enumerate(pending_bets)
                }
                with st.form("mark_result_form_bt"):
                    selected_bet_id = st.selectbox(
                        "Select Pending Bet",
                        options=list(pending_labels.keys()),
                        format_func=lambda x: pending_labels[x],
                    )
                    result_choice = st.radio("Result", ["WIN", "LOSS", "EVEN"], horizontal=True)
                    actual_value = st.number_input(
                        "Actual Stat Value",
                        min_value=0.0, max_value=200.0, value=0.0, step=0.5,
                    )
                    submit_result = st.form_submit_button("💾 Save Result", type="primary")

                if submit_result:
                    ok, msg = record_bet_result(selected_bet_id, result_choice, actual_value)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # ── Bet Cards Grid — grouped by date ─────────────────────────
        if not filtered_bets:
            st.info(f"No bets match the '{filter_choice}' filter on this page.")
        else:
            _today_str = _tracker_today_iso()
            _today_bets = [b for b in filtered_bets if b.get("bet_date", "") == _today_str]
            _past_bets_by_date: dict = {}
            for _b in filtered_bets:
                _bd = _b.get("bet_date", "Unknown")
                if _bd != _today_str:
                    _past_bets_by_date.setdefault(_bd, []).append(_b)

            if _today_bets:
                st.subheader("📅 Today's Bets")
                col_a, col_b = st.columns(2)
                for idx, bet in enumerate(_today_bets):
                    col = col_a if idx % 2 == 0 else col_b
                    with col:
                        st.markdown(get_bet_card_html(bet), unsafe_allow_html=True)

            for _past_date in sorted(_past_bets_by_date.keys(), reverse=True):
                _pd_bets = _past_bets_by_date[_past_date]
                _pd_w = sum(1 for b in _pd_bets if b.get("result") == "WIN")
                _pd_l = sum(1 for b in _pd_bets if b.get("result") == "LOSS")
                _pd_pend = sum(1 for b in _pd_bets if not b.get("result"))
                _pd_label = (
                    f"📅 {_past_date} — {len(_pd_bets)} bet(s) · ✅{_pd_w} ❌{_pd_l}"
                    + (f" ⏳{_pd_pend} pending" if _pd_pend else "")
                )
                with st.expander(_pd_label, expanded=False):
                    col_a, col_b = st.columns(2)
                    for idx, bet in enumerate(_pd_bets):
                        col = col_a if idx % 2 == 0 else col_b
                        with col:
                            st.markdown(get_bet_card_html(bet), unsafe_allow_html=True)

# ============================================================
# END SECTION: My Bets Tab
# ============================================================


# ============================================================
# SECTION: Log a Bet Tab
# ============================================================

with tab_log:
    st.subheader("➕ Log a New Bet")

    # ── Bulk-add platform props ────────────────────────────────────────
    _platform_props = st.session_state.get("platform_props", [])

    # Fall back to CSV on disk if session state is empty
    if not _platform_props:
        try:
            from data.data_manager import load_platform_props_from_csv
            _platform_props = load_platform_props_from_csv()
        except Exception:
            _platform_props = []

    if _platform_props:
        with st.expander(
            f"📋 Add Platform Props to Bet Tracker ({len(_platform_props)} props available)",
            expanded=False,
        ):
            st.caption(
                "These are today's live platform props loaded from all major sportsbooks. "
                "Click **Add All** to log them as "
                "PENDING bets so you can track their results."
            )

            # Summary by platform
            _by_plat: dict = {}
            for _p in _platform_props:
                _pl = str(_p.get("platform", "Unknown"))
                _by_plat[_pl] = _by_plat.get(_pl, 0) + 1
            _plat_cols = st.columns(max(len(_by_plat), 1))
            for _i, (_plname, _cnt) in enumerate(_by_plat.items()):
                _plat_cols[_i % len(_plat_cols)].metric(_plname, _cnt, help="Props from this platform")

            # Preview table
            import pandas as _pd_props
            _preview_rows = [
                {
                    "Player": _p.get("player_name", ""),
                    "Team": _p.get("team", ""),
                    "Stat": _p.get("stat_type", ""),
                    "Line": _p.get("line", ""),
                    "Platform": _p.get("platform", ""),
                    "Game Date": _p.get("game_date", ""),
                }
                for _p in _platform_props
            ]
            st.dataframe(
                _pd_props.DataFrame(_preview_rows),
                use_container_width=True,
                hide_index=True,
                height=min(250, 40 + len(_preview_rows) * 35),
            )

            _prop_dir = st.radio(
                "Default Direction",
                ["OVER", "UNDER"],
                horizontal=True,
                key="props_bulk_direction",
                help="Direction applied to props that don't have one set by the platform.",
            )

            if st.button(
                f"➕ Add All {len(_platform_props)} Props to Bet Tracker",
                type="primary",
                key="btn_add_all_props",
            ):
                with st.spinner("Adding props to bet tracker…"):
                    _saved, _skipped, _errs = log_props_to_tracker(
                        _platform_props, direction=_prop_dir
                    )
                if _saved:
                    st.success(
                        f"✅ Added **{_saved}** prop(s) to the Bet Tracker "
                        f"({_skipped} duplicate(s) skipped)."
                    )
                elif _skipped == len(_platform_props):
                    st.info("ℹ️ All props are already in the Bet Tracker for today.")
                else:
                    st.warning("⚠️ No new props were added.")
                if _errs:
                    with st.expander(f"⚠️ {len(_errs)} warning(s)"):
                        for _e in _errs[:20]:
                            st.caption(_e)
    else:
        st.info(
            "💡 No platform props loaded yet. Load live props from the "
            "**📡 Live Games** page and then return here to bulk-add them."
        )

    st.divider()
    analysis_results = st.session_state.get("analysis_results", [])
    player_options = ["— type manually —"]
    if analysis_results:
        player_options += sorted({
            r.get("player_name", "") for r in analysis_results
            if r.get("player_name")
        })

    with st.form("log_bet_form_bt", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            selected_player = st.selectbox(
                "Player (from tonight's analysis)", player_options
            )
            manual_player = st.text_input(
                "Or enter player name manually", placeholder="e.g., LeBron James"
            )
            stat_type  = st.selectbox(
                "Stat Type",
                ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"],
            )
            prop_line  = st.number_input("Line", min_value=0.0, max_value=200.0, value=24.5, step=0.5)
            direction  = st.radio("Direction", ["OVER", "UNDER"], horizontal=True)

        with col2:
            platform   = st.selectbox("Platform", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"])
            tier       = st.selectbox("Tier", ["Platinum", "Gold", "Silver", "Bronze"])
            entry_fee  = st.number_input("Entry Fee ($)", min_value=0.0, max_value=10000.0, value=10.0, step=5.0)
            team       = st.text_input("Team (optional)", placeholder="e.g., LAL")
            notes      = st.text_input("Notes (optional)", placeholder="e.g., revenge game")

        # Pre-fill confidence from analysis results
        confidence_score = 0.0
        probability_over = 0.5
        edge_percentage  = 0.0
        final_player = (
            manual_player.strip()
            if manual_player.strip()
            else (selected_player if selected_player != "— type manually —" else "")
        )
        if final_player and analysis_results:
            for r in analysis_results:
                if r.get("player_name", "").lower() == final_player.lower():
                    confidence_score = r.get("confidence_score", 0.0)
                    probability_over = r.get("probability_over", 0.5)
                    edge_percentage  = r.get("edge_percentage", 0.0)
                    if not tier or tier == "Bronze":
                        tier = r.get("tier", "Bronze")
                    break

        st.caption(
            f"Auto-filled from analysis: confidence={confidence_score:.1f}, "
            f"P(over)={probability_over:.2f}, edge={edge_percentage:+.1f}%"
            if confidence_score
            else "Enter player name to auto-fill from tonight's analysis."
        )

        submit_bet = st.form_submit_button(
            "📌 Log Bet", width="stretch", type="primary"
        )

    if submit_bet:
        if not final_player:
            st.error("Please enter or select a player name.")
        elif prop_line <= 0:
            st.error("Prop line must be greater than 0.")
        else:
            ok, msg = log_new_bet(
                player_name=final_player,
                stat_type=stat_type,
                prop_line=prop_line,
                direction=direction,
                platform=platform,
                confidence_score=confidence_score,
                probability_over=probability_over,
                edge_percentage=edge_percentage,
                tier=tier,
                entry_fee=entry_fee,
                team=team.strip().upper() if team else "",
                notes=notes.strip(),
            )
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

# ============================================================
# END SECTION: Log a Bet Tab
# ============================================================


# ============================================================
# SECTION: Parlays Tab — Multi-Leg Entry Tracker
# ============================================================

with tab_parlays:
    st.subheader("🎰 Parlay / Entry Tracker")
    st.markdown(
        "Track multi-leg entries as parlays. Group bets into entries and see parlay-level results. "
        "All legs must hit for a parlay WIN."
    )

    # ── Create New Parlay ─────────────────────────────────────────────
    with st.expander("➕ Create New Parlay Entry", expanded=False):
        with st.form("create_parlay_form"):
            _parlay_cols = st.columns([1, 1, 1])
            with _parlay_cols[0]:
                _parlay_date = st.date_input(
                    "Entry Date", value=_tracker_today_date(),
                    key="parlay_date_input",
                )
            with _parlay_cols[1]:
                _parlay_platform = st.selectbox(
                    "Platform",
                    ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6", "Other"],
                    key="parlay_platform_input",
                )
            with _parlay_cols[2]:
                _parlay_fee = st.number_input(
                    "Entry Fee ($)", min_value=0.0, max_value=5000.0,
                    value=10.0, step=5.0, key="parlay_fee_input",
                )

            _parlay_type = st.selectbox(
                "Entry Type",
                ["Parlay (All Must Hit)", "Flex Play (Some Can Miss)", "Power Play"],
                key="parlay_type_input",
            )

            # Select bets to include as legs
            _available_bets = _cached_load_all_bets()
            _unlinked_bets = [
                b for b in _available_bets
                if not b.get("entry_id")
                and b.get("bet_date", "") == _parlay_date.isoformat()
            ]
            _bet_labels = {
                b.get("bet_id", b.get("id", idx)): (
                    f"#{b.get('bet_id', b.get('id', idx))} — "
                    f"{b.get('player_name', '?')} "
                    f"{b.get('direction', '')} {b.get('prop_line', '')} "
                    f"{str(b.get('stat_type', '')).title()} "
                    f"({b.get('result') or 'Pending'})"
                )
                for idx, b in enumerate(_unlinked_bets)
            }
            _selected_legs = st.multiselect(
                "Select Legs (bets from same day)",
                options=list(_bet_labels.keys()),
                format_func=lambda x: _bet_labels.get(x, str(x)),
                key="parlay_legs_select",
                help="Pick 2+ bets to form a parlay. Only unlinked bets from the selected date are shown.",
            )

            _parlay_notes = st.text_input("Notes (optional)", key="parlay_notes_input")
            _parlay_submit = st.form_submit_button("🎰 Create Entry", type="primary")

        if _parlay_submit:
            if len(_selected_legs) < 2:
                st.warning("⚠️ Select at least 2 legs to create a parlay.")
            else:
                _entry_id = insert_entry({
                    "entry_date": _parlay_date.isoformat(),
                    "platform": _parlay_platform,
                    "entry_type": _parlay_type.split(" ")[0].lower(),
                    "entry_fee": _parlay_fee,
                    "expected_value": 0.0,
                    "pick_count": len(_selected_legs),
                    "notes": _parlay_notes,
                })
                if _entry_id:
                    _linked = link_bets_to_entry(_selected_legs, _entry_id)
                    # Auto-resolve if possible
                    resolve_entry_from_legs(_entry_id)
                    _reload_bets()
                    st.success(
                        f"✅ Created entry #{_entry_id} with {_linked} leg(s) on {_parlay_platform}."
                    )
                    st.rerun()
                else:
                    st.error("❌ Failed to create entry.")

    st.divider()

    # ── Existing Entries ──────────────────────────────────────────────
    _all_entries = load_all_entries()

    if not _all_entries:
        st.info(
            "📭 No parlay entries yet. Use the form above to group your bets into multi-leg entries, "
            "or build an entry in the **🧬 Entry Builder** page to auto-log it here."
        )
    else:
        # Summary
        _e_total = len(_all_entries)
        _e_resolved = [e for e in _all_entries if e.get("result") in ("WIN", "LOSS", "EVEN")]
        _e_wins = sum(1 for e in _e_resolved if e.get("result") == "WIN")
        _e_losses = sum(1 for e in _e_resolved if e.get("result") == "LOSS")
        _e_pending = sum(1 for e in _all_entries if not e.get("result"))
        _e_wr = round(_e_wins / max(_e_wins + _e_losses, 1) * 100, 1)
        _e_total_fees = sum(float(e.get("entry_fee") or 0) for e in _all_entries)
        _e_total_payout = sum(float(e.get("payout") or 0) for e in _e_resolved if e.get("result") == "WIN")
        _e_pnl = _e_total_payout - _e_total_fees

        st.markdown(
            get_summary_cards_html(
                total=_e_total,
                wins=_e_wins,
                losses=_e_losses,
                evens=sum(1 for e in _e_resolved if e.get("result") == "EVEN"),
                pending=_e_pending,
                win_rate=_e_wr,
            ),
            unsafe_allow_html=True,
        )

        _pnl_col1, _pnl_col2, _pnl_col3 = st.columns(3)
        _pnl_col1.metric("Total Wagered", f"${_e_total_fees:.2f}")
        _pnl_col2.metric("Total Payouts", f"${_e_total_payout:.2f}")
        _pnl_col3.metric(
            "Net P&L", f"${_e_pnl:+.2f}",
            delta="Profit" if _e_pnl > 0 else ("Break-even" if _e_pnl == 0 else "Loss"),
            delta_color="normal" if _e_pnl >= 0 else "inverse",
        )

        st.divider()

        # ── Resolve All Entries button ────────────────────────────────
        if st.button("🔄 Resolve All Entries", key="resolve_all_entries_btn", type="primary"):
            _resolved_count = 0
            for _e in _all_entries:
                if not _e.get("result"):
                    _r = resolve_entry_from_legs(_e["entry_id"])
                    if _r:
                        _resolved_count += 1
            if _resolved_count > 0:
                st.success(f"✅ Resolved {_resolved_count} entries.")
                st.rerun()
            else:
                st.info("No entries resolved — legs may still be pending.")

        st.divider()

        # ── Entry Cards ──────────────────────────────────────────────
        for _entry in _all_entries:
            _eid = _entry.get("entry_id", "?")
            _edate = _entry.get("entry_date", "")
            _eplat = _entry.get("platform", "?")
            _etype = _entry.get("entry_type", "parlay")
            _efee = float(_entry.get("entry_fee") or 0)
            _epayout = _entry.get("payout")
            _eresult = _entry.get("result")
            _epicks = _entry.get("pick_count", 0)
            _enotes = _entry.get("notes", "")

            # Result styling
            if _eresult == "WIN":
                _result_badge = '<span class="result-win">✅ WIN</span>'
                _border_color = "#00ff9d"
            elif _eresult == "LOSS":
                _result_badge = '<span class="result-loss">❌ LOSS</span>'
                _border_color = "#ff4444"
            elif _eresult == "EVEN":
                _result_badge = '<span class="result-even">🔄 EVEN</span>'
                _border_color = "#b0bec5"
            else:
                _result_badge = '<span class="result-pending">⏳ PENDING</span>'
                _border_color = "#ffcc00"

            _payout_str = f"${_epayout:.2f}" if _epayout is not None else "—"

            with st.expander(
                f"{'✅' if _eresult == 'WIN' else '❌' if _eresult == 'LOSS' else '⏳'} "
                f"Entry #{_eid} — {_epicks} legs on {_eplat} ({_edate})"
                + (f" — {_eresult}" if _eresult else " — Pending"),
                expanded=not _eresult,
            ):
                st.markdown(
                    f'<div style="border-left:4px solid {_border_color};'
                    f'background:rgba(13,17,23,0.85);border-radius:10px;padding:14px 18px;'
                    f'margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div>'
                    f'<strong style="color:#e8f0ff;font-family:Orbitron,sans-serif;">'
                    f'🎰 Entry #{_eid}</strong>'
                    f'<span style="color:#8a9bb8;margin-left:10px;">{_eplat} · {_etype}</span>'
                    f'</div>'
                    f'{_result_badge}'
                    f'</div>'
                    f'<div style="color:#8a9bb8;font-size:0.82rem;margin-top:6px;">'
                    f'Fee: <strong>${_efee:.2f}</strong> · '
                    f'Payout: <strong>{_payout_str}</strong> · '
                    f'{_epicks} leg(s)'
                    + (f' · <em>{_enotes}</em>' if _enotes else '')
                    + f'</div></div>',
                    unsafe_allow_html=True,
                )

                # Show linked legs
                _legs = get_entry_legs(_eid)
                if _legs:
                    st.markdown(f"**Legs ({len(_legs)}):**")
                    for _leg in _legs:
                        _leg_result = _leg.get("result") or "Pending"
                        _leg_icon = {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄"}.get(_leg_result, "⏳")
                        st.markdown(
                            f"&nbsp;&nbsp;{_leg_icon} **{_leg.get('player_name', '?')}** — "
                            f"{_leg.get('direction', '')} {_leg.get('prop_line', '')} "
                            f"{str(_leg.get('stat_type', '')).title()} "
                            f"({_leg_result})"
                        )
                else:
                    st.caption("No legs linked to this entry.")

                # Delete entry
                if st.button(
                    f"🗑️ Delete Entry #{_eid}",
                    key=f"del_entry_{_eid}",
                ):
                    _ok, _msg = delete_entry(_eid)
                    if _ok:
                        st.success(_msg)
                        _reload_bets()
                        st.rerun()
                    else:
                        st.error(_msg)

# ============================================================
# END SECTION: Parlays Tab
# ============================================================


# ============================================================
# SECTION: Performance Predictor Tab
# ============================================================

with tab_predict:
    st.subheader("🔮 Performance Predictor")
    st.markdown(
        "Based on tonight's analysis results, here is a forward-looking prediction "
        "for your slate's expected performance."
    )

    analysis_results = st.session_state.get("analysis_results", [])

    if not analysis_results:
        st.info(
            "💡 No analysis results found. "
            "Go to **⚡ Neural Analysis** and run analysis first, "
            "then return here for your performance forecast."
        )
    else:
        confidences  = [r.get("confidence_score", 0) for r in analysis_results]
        avg_conf     = sum(confidences) / len(confidences) if confidences else 0

        # Tier-weighted win-rate estimation
        _TIER_BASE_WIN_RATE = {
            "Platinum": 72.0,
            "Gold":     62.0,
            "Silver":   54.0,
            "Bronze":   46.0,
        }
        _tier_counts_wr: dict = {}
        for r in analysis_results:
            t = r.get("tier", "Bronze")
            _tier_counts_wr[t] = _tier_counts_wr.get(t, 0) + 1

        total_picks = len(analysis_results)
        tier_weighted_win_rate = 0.0
        if total_picks > 0:
            for tier_name, base_wr in _TIER_BASE_WIN_RATE.items():
                cnt = _tier_counts_wr.get(tier_name, 0)
                tier_weighted_win_rate += (cnt / total_picks) * base_wr

        conf_based = min(95.0, max(40.0, avg_conf * 0.9 + 5.0))
        est_win_rate = round(0.70 * tier_weighted_win_rate + 0.30 * conf_based, 1)
        est_win_rate = min(95.0, max(40.0, est_win_rate))

        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Props in Slate",  len(analysis_results))
        pc2.metric("Avg Confidence",  f"{avg_conf:.1f}")
        pc3.metric("Est. Win Rate",   f"{est_win_rate:.1f}%",
                   help="Tier-weighted estimate blended with model confidence")

        if _tier_counts_wr:
            st.markdown("**Per-Tier Expected Win Rates**")
            _TIER_EMOJI_WR = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
            tier_wr_rows = [
                {
                    "Tier":            f"{_TIER_EMOJI_WR.get(t, '')} {t}",
                    "Picks":           _tier_counts_wr[t],
                    "Est. Win Rate":   f"{_TIER_BASE_WIN_RATE.get(t, 50):.0f}%",
                }
                for t in ["Platinum", "Gold", "Silver", "Bronze"]
                if t in _tier_counts_wr
            ]
            st.markdown(
                get_styled_stats_table_html(
                    tier_wr_rows,
                    ["Tier", "Picks", "Est. Win Rate"],
                ),
                unsafe_allow_html=True,
            )

        st.divider()

        st.subheader("💰 Recommended Bankroll Allocation")
        st.markdown("Based on the SAFE Score™ tier distribution in tonight's slate.")

        _tier_counts: dict = {}
        for r in analysis_results:
            t = r.get("tier", "Bronze")
            _tier_counts[t] = _tier_counts.get(t, 0) + 1

        _TIER_PCT   = {"Platinum": 0.30, "Gold": 0.25, "Silver": 0.20, "Bronze": 0.10}
        _TIER_EMOJI = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        bankroll    = st.number_input(
            "Total Bankroll ($)", min_value=10.0, max_value=100000.0, value=100.0, step=10.0
        )
        alloc_rows = []
        for tier_name in ["Platinum", "Gold", "Silver", "Bronze"]:
            cnt = _tier_counts.get(tier_name, 0)
            if cnt > 0:
                alloc_pct = _TIER_PCT.get(tier_name, 0.10)
                alloc_amt = bankroll * alloc_pct
                alloc_rows.append({
                    "Tier":          f"{_TIER_EMOJI.get(tier_name, '')} {tier_name}",
                    "Picks":         cnt,
                    "Allocation %":  f"{alloc_pct * 100:.0f}%",
                    "Amount ($)":    f"${alloc_amt:.2f}",
                    "Per Pick ($)":  f"${alloc_amt / max(cnt, 1):.2f}",
                })
        if alloc_rows:
            st.markdown(
                get_styled_stats_table_html(
                    alloc_rows,
                    ["Tier", "Picks", "Allocation %", "Amount ($)", "Per Pick ($)"],
                ),
                unsafe_allow_html=True,
            )
        else:
            st.info("No tier data found in tonight's analysis results.")

        st.divider()

        platinum_picks = [
            r for r in analysis_results
            if r.get("tier", "") == "Platinum"
            and not r.get("should_avoid", False)
        ]
        if platinum_picks:
            st.subheader("🏆 Projected ROI — All Platinum Picks Hit")
            plat_alloc       = bankroll * 0.30
            projected_payout = plat_alloc * 2.0
            projected_roi    = (
                (projected_payout - plat_alloc) / max(plat_alloc, 1)
            ) * 100

            rp1, rp2, rp3 = st.columns(3)
            rp1.metric("Platinum Picks", len(platinum_picks))
            rp2.metric("Allocated",      f"${plat_alloc:.2f}")
            rp3.metric(
                "Projected Profit",
                f"${projected_payout - plat_alloc:.2f}",
                delta=f"{projected_roi:.1f}% ROI",
            )

            st.caption(
                "⚠️ Projections are illustrative estimates based on typical platform "
                "multipliers. Actual payouts vary by platform and entry type."
            )
        else:
            st.info(
                "No Platinum tier picks found in tonight's analysis. "
                "Run **⚡ Neural Analysis** for updated results."
            )

# ============================================================
# END SECTION: Performance Predictor Tab
# ============================================================


# ============================================================
# SECTION: History Tab — 2-Week Rolling Timeline
# ============================================================

with tab_history:
    st.subheader("📅 2-Week Rolling History")
    st.markdown(
        "Day-by-day breakdown of the last 14 days. "
        "Expand any day to see individual picks as styled cards."
    )

    rolling_stats = get_rolling_stats(days=14)
    snapshots = rolling_stats.get("snapshots", [])

    # ── Calendar Heatmap (A4) ──────────────────────────────────────────
    _heatmap_bets = _cached_load_all_bets()
    _heatmap_bets = _apply_global_filters([b for b in _heatmap_bets if _platform_filter_fn(b)])
    _heatmap_by_date: dict = {}
    for _hb in _heatmap_bets:
        _heatmap_by_date.setdefault(_hb.get("bet_date", "Unknown"), []).append(_hb)
    if _heatmap_by_date:
        with st.expander("🟩 Win Rate Heatmap (last 6 weeks)", expanded=True):
            st.markdown(
                get_calendar_heatmap_html(_heatmap_by_date, num_days=42),
                unsafe_allow_html=True,
            )
            st.caption("Hover over cells to see daily stats. Green = winning days, Red = losing days.")

    # ── Rolling Summary Bar ────────────────────────────────────────────
    if rolling_stats.get("total_bets", 0) > 0:
        streak_val = rolling_stats.get("streak", 0)
        streak_label = (
            f"🔥 W{streak_val}" if streak_val > 0
            else f"❄️ L{abs(streak_val)}" if streak_val < 0
            else "—"
        )
        best_d = rolling_stats.get("best_day", {})
        worst_d = rolling_stats.get("worst_day", {})
        best_day_str = f"{best_d.get('snapshot_date','—')} ({best_d.get('win_rate',0):.0f}%)" if best_d else "—"
        worst_day_str = f"{worst_d.get('snapshot_date','—')} ({worst_d.get('win_rate',0):.0f}%)" if worst_d else "—"

        rs1, rs2, rs3, rs4, rs5 = st.columns(5)
        rs1.metric("14-Day Bets",  rolling_stats.get("total_bets", 0))
        rs2.metric("Win Rate",     f"{rolling_stats.get('win_rate', 0):.1f}%")
        rs3.metric("Streak",       streak_label)
        rs4.metric("Best Day",     best_day_str)
        rs5.metric("Worst Day",    worst_day_str)
        st.divider()

    # ── Cumulative ROI Time-Series Chart ───────────────────────────────
    # Build a cumulative P&L series from all resolved bets over the
    # last 14 days to visualize the strategy's trend.
    _all_hist_bets = _cached_load_all_bets()
    _resolved_bets = [
        b for b in _all_hist_bets
        if b.get("result") in ("WIN", "LOSS", "EVEN")
        and _platform_filter_fn(b)
    ]
    _resolved_bets.sort(key=lambda b: (b.get("bet_date", ""), b.get("id", 0)))

    if len(_resolved_bets) >= 3:
        with st.expander("📈 Cumulative P&L Curve (resolved bets)", expanded=True):
            _HIST_PAYOUT = _DFS_PAYOUT_RATIO
            _cum_pnl = 0.0
            _total_dollar_pnl = 0.0  # B9: actual dollar P&L
            _pnl_vals = []
            _pnl_labels = []
            _daily_pnl: dict = {}  # date → cumulative at end of day
            _max_pnl = 0.0  # For drawdown tracking
            for _rb in _resolved_bets:
                _res = _rb.get("result", "")
                _fee = float(_rb.get("entry_fee") or 0)
                if _res == "WIN":
                    _cum_pnl += _HIST_PAYOUT
                    _total_dollar_pnl += _fee * _HIST_PAYOUT if _fee > 0 else 0
                elif _res == "LOSS":
                    _cum_pnl -= 1.0
                    _total_dollar_pnl -= _fee if _fee > 0 else 0
                # EVEN: no change
                _pnl_vals.append(round(_cum_pnl, 2))
                _pnl_labels.append(_rb.get("bet_date", ""))
                _daily_pnl[_rb.get("bet_date", "")] = round(_cum_pnl, 2)
                _max_pnl = max(_max_pnl, _cum_pnl)

            _wins_total = sum(1 for b in _resolved_bets if b.get("result") == "WIN")
            _losses_total = sum(1 for b in _resolved_bets if b.get("result") == "LOSS")
            _wr_total = _wins_total / max(_wins_total + _losses_total, 1) * 100

            # Drawdown calculation
            _drawdown = _max_pnl - _cum_pnl if _max_pnl > 0 else 0
            _drawdown_pct = (_drawdown / max(_max_pnl, 0.01)) * 100 if _max_pnl > 0 else 0

            _roi_cols = st.columns(5)
            _roi_cols[0].metric("Resolved Bets", len(_resolved_bets))
            _roi_cols[1].metric("Win Rate", f"{_wr_total:.1f}%",
                                delta=f"{_wr_total - _BREAKEVEN_WIN_RATE:+.1f}% vs breakeven")
            _roi_cols[2].metric("Unit P&L", f"{_cum_pnl:+.2f}u")
            if _total_dollar_pnl != 0:
                _roi_cols[3].metric("Dollar P&L", f"${_total_dollar_pnl:+.2f}",
                                    delta="positive = profitable" if _total_dollar_pnl > 0 else "negative = losing")
            else:
                _roi_cols[3].metric(
                    "ROI/bet",
                    f"{_cum_pnl / max(len(_resolved_bets), 1):+.3f}u",
                    delta="positive = profitable" if _cum_pnl > 0 else "negative = losing"
                )
            _roi_cols[4].metric(
                "Drawdown",
                f"{_drawdown_pct:.1f}%",
                delta=f"{_drawdown:+.2f}u from peak" if _drawdown > 0 else "At peak",
                delta_color="inverse" if _drawdown > 0 else "normal",
            )

            # Line chart of cumulative P&L
            st.line_chart({"Cumulative P&L (units)": _pnl_vals}, height=220)
            st.caption(
                f"📊 {len(_resolved_bets)} resolved bets · "
                f"{_wins_total}W / {_losses_total}L · "
                f"Final: {_cum_pnl:+.2f}u"
            )

            # Daily P&L mini-table
            if _daily_pnl:
                _dpnl_rows = [
                    {"Date": d, "End-of-Day P&L": f"{v:+.2f}u"}
                    for d, v in sorted(_daily_pnl.items(), reverse=True)[:14]
                ]
                st.dataframe(_dpnl_rows, hide_index=True, use_container_width=True)
        st.divider()

    # ── History Filter ─────────────────────────────────────────────────
    hist_filter = st.radio(
        "History filter",
        ["All", "Wins Only", "Losses Only", "Pending"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # ── Day-by-Day Timeline ────────────────────────────────────────────
    if not snapshots:
        # No snapshot data yet — fall back to grouping raw bets by date
        all_bets_hist = _cached_load_all_bets()
        all_bets_hist = [b for b in all_bets_hist if _platform_filter_fn(b)]
        _by_date_hist: dict = {}
        for _b in all_bets_hist:
            _by_date_hist.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)
        
        if not _by_date_hist:
            st.info("📭 No bets logged yet. Start logging bets to build your history.")
        else:
            for _date in sorted(_by_date_hist.keys(), reverse=True):
                _day_bets = _by_date_hist[_date]
                _day_w = sum(1 for b in _day_bets if b.get("result") == "WIN")
                _day_l = sum(1 for b in _day_bets if b.get("result") == "LOSS")
                _day_p = sum(1 for b in _day_bets if b.get("result") == "EVEN")
                _day_pend = sum(1 for b in _day_bets if not b.get("result"))
                _day_total_res = _day_w + _day_l
                _day_wr = round(_day_w / max(_day_total_res, 1) * 100, 1) if _day_total_res > 0 else None

                if _day_wr is not None and _day_wr >= 55:
                    _day_color = "🟢"
                    _day_card_class = "day-card-green"
                elif _day_wr is not None and _day_wr < 45:
                    _day_color = "🔴"
                    _day_card_class = "day-card-red"
                else:
                    _day_color = "🟡"
                    _day_card_class = "day-card-yellow"

                _wr_str = f" — {_day_wr:.0f}% win rate" if _day_wr is not None else " — ⏳ pending"
                _label = (
                    f"{_day_color} {_date} · {len(_day_bets)} picks · "
                    f"✅{_day_w} ❌{_day_l}" + _wr_str
                )

                # Apply history filter
                if hist_filter == "Wins Only":
                    _show_bets = [b for b in _day_bets if b.get("result") == "WIN"]
                elif hist_filter == "Losses Only":
                    _show_bets = [b for b in _day_bets if b.get("result") == "LOSS"]
                elif hist_filter == "Pending":
                    _show_bets = [b for b in _day_bets if not b.get("result")]
                else:
                    _show_bets = _day_bets

                if not _show_bets and hist_filter != "All":
                    continue

                with st.expander(_label, expanded=(_date == max(_by_date_hist.keys()))):
                    if not _show_bets:
                        st.info(f"No bets match '{hist_filter}' for this day.")
                    else:
                        _ha, _hb = st.columns(2)
                        for _idx, _hb_bet in enumerate(_show_bets):
                            _hcol = _ha if _idx % 2 == 0 else _hb
                            with _hcol:
                                st.markdown(get_bet_card_html(_hb_bet), unsafe_allow_html=True)
                        if len(_show_bets) > 6:
                            st.caption(f"*{len(_show_bets)} bets shown for {_date}.*")
    else:
        # Use daily_snapshots for summaries + load individual bets for expansion
        all_bets_hist = _cached_load_all_bets()
        all_bets_hist = [b for b in all_bets_hist if _platform_filter_fn(b)]
        _bets_by_date: dict = {}
        for _b in all_bets_hist:
            _bets_by_date.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)

        for snap in snapshots:
            _date = snap.get("snapshot_date", "")
            _w = snap.get("wins", 0)
            _l = snap.get("losses", 0)
            _pend = snap.get("pending", 0)
            _total = snap.get("total_picks", 0)
            _wr = snap.get("win_rate", 0.0)

            if _wr >= 55:
                _day_color = "🟢"
            elif _wr < 45 and (_w + _l) > 0:
                _day_color = "🔴"
            else:
                _day_color = "🟡"

            _wr_str = f" — {_wr:.0f}% win rate" if (_w + _l) > 0 else " — ⏳ all pending"
            _label = (
                f"{_day_color} {_date} · {_total} picks · "
                f"✅{_w} ❌{_l}" + _wr_str
            )

            _day_bets = _bets_by_date.get(_date, [])

            if hist_filter == "Wins Only":
                _show_bets = [b for b in _day_bets if b.get("result") == "WIN"]
            elif hist_filter == "Losses Only":
                _show_bets = [b for b in _day_bets if b.get("result") == "LOSS"]
            elif hist_filter == "Pending":
                _show_bets = [b for b in _day_bets if not b.get("result")]
            else:
                _show_bets = _day_bets

            if not _show_bets and hist_filter != "All" and _total == 0:
                continue

            with st.expander(_label):
                if not _show_bets:
                    if _total > 0:
                        st.info(f"No individual bets match '{hist_filter}' for this day.")
                    else:
                        st.info("No bets logged for this day.")
                else:
                    _ha, _hb = st.columns(2)
                    for _idx, _hb_bet in enumerate(_show_bets):
                        _hcol = _ha if _idx % 2 == 0 else _hb
                        with _hcol:
                            st.markdown(get_bet_card_html(_hb_bet), unsafe_allow_html=True)

# ============================================================
# END SECTION: History Tab
# ============================================================

# ============================================================
# SECTION: Achievements Tab
# Gamification panel: streaks, win-rate badges, milestones,
# personal bests, and a betting journal summary.
# ============================================================

with tab_achievements:
    st.subheader("🏆 Achievements & Streak Tracker")
    st.markdown(
        "Track your betting streaks, unlock milestones, and review your personal bests."
    )

    # ── Load all resolved bets (deduplicated) ─────────────────────
    # Analysis picks and bets may overlap (auto_log_analysis_bets copies
    # qualifying picks into the bets table while insert_analysis_picks
    # stores them in all_analysis_picks).  Deduplicate by a composite key
    # so the same pick is never counted twice.
    _ach_raw = load_all_analysis_picks() + load_all_bets()
    _ach_seen_keys: set = set()
    _ach_all_bets: list = []
    for _ab in _ach_raw:
        # all_analysis_picks uses "prop_line" and "pick_date";
        # bets table uses "prop_line" and "bet_date".  Fall back to
        # alternate field names ("line", "pick_date") for compatibility.
        # Normalize values (lowercase, rounded line, uppercase direction)
        # to ensure consistent dedup across both tables.
        try:
            _line_val = str(round(float(_ab.get("prop_line") or _ab.get("line") or 0), 2))
        except (ValueError, TypeError):
            _line_val = "0"
        _ak = (
            str(_ab.get("player_name", "")).strip().lower(),
            str(_ab.get("stat_type", "")).strip().lower(),
            _line_val,
            str(_ab.get("direction", "")).strip().upper(),
            str(_ab.get("bet_date") or _ab.get("pick_date", "")),
        )
        if _ak not in _ach_seen_keys:
            _ach_seen_keys.add(_ak)
            _ach_all_bets.append(_ab)
    _ach_resolved = [
        b for b in _ach_all_bets
        if b.get("result") in ("WIN", "LOSS", "EVEN")
    ]
    _ach_resolved.sort(key=lambda b: b.get("bet_date", ""), reverse=True)

    if not _ach_resolved:
        st.info(
            "No resolved bets yet. Log and resolve some bets to start earning achievements!"
        )
    else:
        total_bets   = len(_ach_resolved)
        total_wins   = sum(1 for b in _ach_resolved if b.get("result") == "WIN")
        total_losses = sum(1 for b in _ach_resolved if b.get("result") == "LOSS")
        overall_wr   = round(total_wins / max(total_bets, 1) * 100, 1)

        # ── Current hot/cold streak ────────────────────────────────
        _cur_streak = 0
        _cur_streak_type = ""
        if _ach_resolved:
            _first_result = _ach_resolved[0].get("result", "")
            _cur_streak_type = _first_result
            for _sb in _ach_resolved:
                if _sb.get("result") == _first_result:
                    _cur_streak += 1
                else:
                    break

        # ── Longest win/loss streak ────────────────────────────────
        _longest_win = 0
        _longest_loss = 0
        _run_w = 0
        _run_l = 0
        for _sb in reversed(_ach_resolved):
            if _sb.get("result") == "WIN":
                _run_w += 1
                _run_l = 0
            elif _sb.get("result") == "LOSS":
                _run_l += 1
                _run_w = 0
            else:
                _run_w = _run_l = 0
            _longest_win  = max(_longest_win,  _run_w)
            _longest_loss = max(_longest_loss, _run_l)

        # ── Best single-day win rate (min 3 bets) ──────────────────
        _day_groups: dict = {}
        for _sb in _ach_resolved:
            _d = _sb.get("bet_date", "Unknown")
            _day_groups.setdefault(_d, []).append(_sb)
        _best_day_wr = 0.0
        _best_day    = ""
        for _d, _dbets in _day_groups.items():
            if len(_dbets) >= 3:
                _dw = sum(1 for b in _dbets if b.get("result") == "WIN")
                _dwr = _dw / len(_dbets) * 100
                if _dwr > _best_day_wr:
                    _best_day_wr = _dwr
                    _best_day    = _d

        # ── Top stat type by win rate ──────────────────────────────
        _stat_groups: dict = {}
        for _sb in _ach_resolved:
            _st = _sb.get("stat_type", "unknown")
            _stat_groups.setdefault(_st, {"wins": 0, "total": 0})
            _stat_groups[_st]["total"] += 1
            if _sb.get("result") == "WIN":
                _stat_groups[_st]["wins"] += 1
        _stat_wr = {
            s: round(v["wins"] / max(v["total"], 1) * 100, 1)
            for s, v in _stat_groups.items()
            if v["total"] >= 3
        }
        _best_stat = max(_stat_wr, key=_stat_wr.get) if _stat_wr else ""
        _best_stat_wr = _stat_wr.get(_best_stat, 0.0)

        # ── Summary metrics row ────────────────────────────────────
        _ac1, _ac2, _ac3, _ac4 = st.columns(4)
        with _ac1:
            st.metric("Total Resolved", total_bets)
        with _ac2:
            st.metric("Overall Win Rate", f"{overall_wr:.1f}%",
                      delta=f"+{overall_wr - 50:.1f}% vs 50%" if overall_wr != 50 else None)
        with _ac3:
            _streak_label = (
                f"🔥 {_cur_streak} W" if _cur_streak_type == "WIN" and _cur_streak >= 2
                else f"❄️ {_cur_streak} L" if _cur_streak_type == "LOSS" and _cur_streak >= 2
                else f"{_cur_streak} {_cur_streak_type}"
            )
            st.metric("Current Streak", _streak_label)
        with _ac4:
            st.metric("Best Day W%", f"{_best_day_wr:.0f}%" if _best_day else "—",
                      help=f"Date: {_best_day}" if _best_day else "Need 3+ bets in one day")

        st.divider()

        # ── Level System (A5) ──────────────────────────────────────
        st.markdown("### 🎮 Your Level")
        st.markdown(
            get_level_badge_html(total_bets, overall_wr),
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Achievement badges with Progress Rings (A5) ───────────
        st.markdown("### 🎖️ Achievements")

        # Define all possible badges with thresholds
        _all_badges: list[dict] = []

        # Volume badges (progressive)
        _vol_thresholds = [
            (10, "🎯", "Getting Serious", "10+ resolved bets"),
            (50, "🥈", "Fifty Strong", "50+ resolved bets"),
            (100, "💯", "Century Club", "100+ resolved bets"),
            (250, "🏅", "Quarter Thousand", "250+ resolved bets"),
            (500, "🌟", "500 Club", "500+ resolved bets"),
        ]
        for _thresh, _icon, _name, _desc in _vol_thresholds:
            _progress = min(total_bets / _thresh, 1.0)
            _earned = total_bets >= _thresh
            _all_badges.append({
                "icon": _icon, "name": _name, "desc": _desc,
                "progress": _progress, "earned": _earned,
                "remaining": f"{max(_thresh - total_bets, 0)} more bets" if not _earned else "",
            })

        # Win rate badges
        if total_bets >= 10:
            for _wr_thresh, _icon, _name, _desc in [
                (55, "✅", "Consistent", f"{overall_wr:.0f}% win rate"),
                (60, "⭐", "Sharp", f"{overall_wr:.0f}% win rate (10+ bets)"),
                (70, "👑", "Elite Picker", f"{overall_wr:.0f}% win rate (20+ bets)"),
            ]:
                _progress = min(overall_wr / _wr_thresh, 1.0) if _wr_thresh > 0 else 0.0
                _earned = overall_wr >= _wr_thresh and (total_bets >= 20 if _wr_thresh >= 70 else total_bets >= 10)
                _all_badges.append({
                    "icon": _icon, "name": _name, "desc": _desc,
                    "progress": _progress, "earned": _earned,
                    "remaining": f"Need {_wr_thresh:.0f}% WR" if not _earned else "",
                })

        # Streak badges
        for _streak_thresh, _icon, _name, _desc in [
            (3, "⚡", "Warming Up", f"{_longest_win}-game win streak"),
            (5, "🔥", "Hot Streak", f"{_longest_win}-game win streak"),
            (10, "🔥🔥", "On Fire", f"{_longest_win}-game win streak"),
        ]:
            _progress = min(_longest_win / _streak_thresh, 1.0)
            _earned = _longest_win >= _streak_thresh
            _all_badges.append({
                "icon": _icon, "name": _name, "desc": _desc,
                "progress": _progress, "earned": _earned,
                "remaining": f"{max(_streak_thresh - _longest_win, 0)} more wins" if not _earned else "",
            })

        # Stat mastery
        if _best_stat and _best_stat_wr >= 50:
            _progress = min(_best_stat_wr / 65, 1.0)
            _earned = _best_stat_wr >= 65
            _all_badges.append({
                "icon": "🏆",
                "name": f"{_best_stat.replace('_',' ').title()} Master",
                "desc": f"{_best_stat_wr:.0f}% win rate on {_best_stat}",
                "progress": _progress, "earned": _earned,
                "remaining": f"Need 65% WR on {_best_stat}" if not _earned else "",
            })

        # Resilience
        if _longest_loss >= 5:
            _earned = _longest_loss >= 5 and overall_wr >= 55
            _all_badges.append({
                "icon": "💪", "name": "Resilient",
                "desc": "Bounced back from 5+ loss streak",
                "progress": min(overall_wr / 55, 1.0) if not _earned else 1.0,
                "earned": _earned,
                "remaining": "Need 55%+ WR after 5+ loss streak" if not _earned else "",
            })

        # Current streak
        if _cur_streak_type == "WIN" and _cur_streak >= 3:
            _progress = min(_cur_streak / 5, 1.0)
            _earned = _cur_streak >= 5
            _all_badges.append({
                "icon": "🌶️", "name": "White Hot",
                "desc": f"Current {_cur_streak}-game win streak!",
                "progress": _progress, "earned": _earned,
                "remaining": f"{max(5 - _cur_streak, 0)} more wins" if not _earned else "",
            })

        if not _all_badges:
            st.info("No badges available yet. Keep logging bets to unlock achievements!")
        else:
            # Show earned badges first, then locked ones
            _earned_badges = [b for b in _all_badges if b["earned"]]
            _locked_badges = [b for b in _all_badges if not b["earned"]]

            if _earned_badges:
                st.markdown(f"**🏅 Earned ({len(_earned_badges)})**")
                _badge_cols = st.columns(min(len(_earned_badges), 4))
                for _bi, _badge in enumerate(_earned_badges):
                    with _badge_cols[_bi % 4]:
                        st.markdown(
                            get_achievement_ring_html(
                                _badge["icon"], _badge["name"], _badge["desc"],
                                _badge["progress"], _badge["earned"],
                            ),
                            unsafe_allow_html=True,
                        )

            if _locked_badges:
                st.markdown(f"**🔒 Locked ({len(_locked_badges)})**")
                _locked_cols = st.columns(min(len(_locked_badges), 4))
                for _bi, _badge in enumerate(_locked_badges):
                    with _locked_cols[_bi % 4]:
                        st.markdown(
                            get_achievement_ring_html(
                                _badge["icon"], _badge["name"],
                                _badge.get("remaining", _badge["desc"]),
                                _badge["progress"], _badge["earned"],
                            ),
                            unsafe_allow_html=True,
                        )

        st.divider()

        # ── Streak history mini-chart (last 30 bets) ──────────────
        st.markdown("### 📈 Last 30 Results — Win/Loss Timeline")
        _last30 = _ach_resolved[:30]
        if _last30:
            _timeline_dots = []
            for _tb in reversed(_last30):
                _tr = _tb.get("result", "")
                if _tr == "WIN":
                    _timeline_dots.append('<span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#00d084;margin:2px;" title="WIN"></span>')
                elif _tr == "LOSS":
                    _timeline_dots.append('<span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#ff4d4d;margin:2px;" title="LOSS"></span>')
                else:
                    _timeline_dots.append('<span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:#444;margin:2px;" title="EVEN"></span>')
            st.markdown(
                '<div style="display:flex;flex-wrap:wrap;gap:3px;padding:8px;background:rgba(13,20,45,0.55);'
                'border:1px solid rgba(0,240,255,0.1);border-radius:8px;">'
                + "".join(_timeline_dots)
                + "<span style='color:#8a9bb8;font-size:0.72rem;margin-left:8px;align-self:center;'>"
                  "← oldest &nbsp; newest →</span>"
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("No timeline data available.")

        st.divider()

        # ── Personal bests table ───────────────────────────────────
        st.markdown("### 🥇 Personal Bests")
        _pb_col1, _pb_col2 = st.columns(2)
        with _pb_col1:
            st.metric("🔥 Longest Win Streak", f"{_longest_win} games")
            st.metric("📅 Best Single-Day Win %", f"{_best_day_wr:.0f}%" if _best_day else "—",
                      help=f"Date: {_best_day}" if _best_day else "")
        with _pb_col2:
            st.metric("🏆 Best Stat Type", f"{_best_stat.replace('_',' ').title()}" if _best_stat else "—",
                      delta=f"{_best_stat_wr:.0f}% WR" if _best_stat else None)
            st.metric("📊 Total Wins", total_wins)

        st.divider()

        # ── Win rate by stat type summary ─────────────────────────
        if _stat_wr:
            st.markdown("### 📊 Win Rate by Stat Type")
            _wr_rows = [
                {
                    "Stat Type": s.replace("_", " ").title(),
                    "Bets": _stat_groups[s]["total"],
                    "Wins": _stat_groups[s]["wins"],
                    "Win Rate": f"{wr:.1f}%",
                    "Grade": "A ✅" if wr >= 65 else ("B ✅" if wr >= 55 else ("C ➡️" if wr >= 50 else "D ❌")),
                }
                for s, wr in sorted(_stat_wr.items(), key=lambda x: x[1], reverse=True)
            ]
            st.dataframe(_wr_rows, hide_index=True, use_container_width=True)

# ============================================================
# END SECTION: Achievements Tab
# ============================================================

