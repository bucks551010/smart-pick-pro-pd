# ============================================================
# FILE: pages/11_📈_Bet_Tracker.py
# PURPOSE: Thin shell — page setup, global filters, tab routing.
#          All tab logic lives in pages/helpers/bet_tracker_tabs/.
#          All shared data/caching lives in pages/helpers/bet_tracker_data.py.
# ============================================================

import logging
import threading as _threading

import streamlit as st

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

from tracking.database import initialize_database
from styles.theme import get_global_css, get_qds_css, get_bet_card_css

from pages.helpers.bet_tracker_data import (
    JOSEPH_LOADING_AVAILABLE,
    joseph_loading_placeholder,
    bg_resolve_results,
    background_auto_resolve,
    tracker_today_iso,
    reload_bets,
)

from pages.helpers.bet_tracker_tabs import (
    health,
    platform_picks,
    all_picks,
    joseph,
    resolve,
    my_bets,
    log_bet,
    parlays,
    predict,
    history,
    achievements,
)

# ============================================================
# Page Setup
# ============================================================

st.set_page_config(
    page_title="Bet Tracker & Model Health — SmartBetPro NBA",
    page_icon="📈",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)
st.markdown(get_bet_card_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ───────────────────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating
render_joseph_hero_banner()
st.session_state["joseph_page_context"] = "page_bet_tracker"
inject_joseph_floating()

# ── Premium Gate ──────────────────────────────────────────────
from utils.premium_gate import premium_gate
if not premium_gate("Bet Tracker"):
    st.stop()

# ── UX Enhancements ──────────────────────────────────────────
from utils.components import (
    render_notification_center,
    inject_mobile_responsive_css,
    inject_aria_enhancements,
)
render_notification_center()
inject_mobile_responsive_css()
inject_aria_enhancements()

# Ensure DB is initialised
initialize_database()

# ============================================================
# Background Auto-Resolve (once per day per session)
# ============================================================

_auto_resolve_today = tracker_today_iso()
if st.session_state.get("_bet_tracker_auto_resolved_date") != _auto_resolve_today:
    st.session_state["_bet_tracker_auto_resolved_date"] = _auto_resolve_today
    bg_resolve_results.clear()
    _resolve_thread = _threading.Thread(target=background_auto_resolve, daemon=True)
    _resolve_thread.start()
    st.toast("🤖 Auto-resolving pending bets in the background…")

# Show deferred toast messages from background thread
if bg_resolve_results.get("done"):
    _msgs = bg_resolve_results.pop("messages", [])
    bg_resolve_results.pop("done", None)
    if _msgs:
        reload_bets()
        for _toast_line in _msgs:
            if _toast_line.strip():
                st.toast(_toast_line.strip())

# ============================================================
# Page Title & How-to
# ============================================================

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

# ── Prominent "Check Results Now" button ──────────────────────
_check_col, _check_info_col = st.columns([1, 3])
with _check_col:
    _check_now_btn = st.button(
        "🔄 Check Results Now",
        type="primary",
        help="Immediately check live NBA scoreboard for Final games and resolve today's pending bets.",
        key="top_check_results_btn",
    )
with _check_info_col:
    st.caption(
        "Checks the live NBA scoreboard for completed games and instantly resolves today's pending bets. "
        "Click any time — no need to wait until tomorrow."
    )

if _check_now_btn:
    _resolve_status = st.empty()
    _resolve_progress = st.progress(0, text="⏳ Connecting to NBA scoreboard…")
    try:
        from tracking.bet_tracker import resolve_todays_bets as _rtr_top
        from tracking.database import load_all_bets as _load_bets_top
        import datetime as _dt_top

        # Count pending bets so the bar reflects real work
        try:
            _today_top = _dt_top.date.today().isoformat()
            _pending_top = [
                b for b in _load_bets_top(exclude_linked=False)
                if b.get("bet_date") == _today_top and not b.get("result")
            ]
            _total_top = max(len(_pending_top), 1)
        except Exception:
            _pending_top = []
            _total_top = 1

        _resolve_progress.progress(10, text=f"🔍 Found {len(_pending_top)} pending bet(s) — fetching live scores…")

        # Run resolve (synchronous — fills the 10→90 range while it runs)
        _top_result = _rtr_top()

        _resolve_progress.progress(95, text="💾 Saving results…")
        _resolve_status.empty()

        if _top_result.get("resolved", 0) > 0:
            _resolve_progress.progress(100, text="✅ Done!")
            st.success(
                f"✅ Resolved **{_top_result['resolved']}** bet(s): "
                f"**{_top_result['wins']}** WIN · **{_top_result['losses']}** LOSS · **{_top_result['evens']}** EVEN"
            )
            reload_bets()
            _resolve_progress.empty()
            st.rerun()
        else:
            _resolve_progress.progress(100, text="ℹ️ Done — no new results yet.")
            st.info(
                f"ℹ️ No bets resolved. Games may still be in progress or not started. "
                f"Pending: {_top_result.get('pending', 0)}"
            )
            _resolve_progress.empty()

        if _top_result.get("errors"):
            st.warning("⚠️ " + " | ".join(_top_result["errors"][:3]))
            if len(_top_result["errors"]) > 3:
                with st.expander(f"See all {len(_top_result['errors'])} detail(s)"):
                    for _e in _top_result["errors"]:
                        st.markdown(f"- {_e}")
    except Exception as _top_err:
        _resolve_progress.empty()
        _resolve_status.empty()
        st.error(f"❌ Could not check results: {_top_err}")

# ============================================================
# Global Filter Bar
# ============================================================

st.divider()

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

st.divider()

# ============================================================
# Tabs — each body delegates to its tab module
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
) = st.tabs(
    [
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
    ],
    key="bet_tracker_tabs",
)

with tab_model_health:
    health.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_ai_picks:
    platform_picks.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_all_picks:
    all_picks.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_joseph_bets:
    joseph.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_auto_resolve:
    resolve.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_bets:
    my_bets.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_log:
    log_bet.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_parlays:
    parlays.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_predict:
    predict.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_history:
    history.render(platform_filter_selections, _player_search, _date_range, _direction_filter)

with tab_achievements:
    achievements.render(platform_filter_selections, _player_search, _date_range, _direction_filter)
