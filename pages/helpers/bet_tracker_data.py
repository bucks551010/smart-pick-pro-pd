# ============================================================
# FILE: pages/helpers/bet_tracker_data.py
# PURPOSE: Shared data loading, caching, helper functions for
#          all Bet Tracker tabs.  Centralises heavy data
#          operations so multiple tabs never repeat expensive
#          DB queries or O(n²) deduplication.
# ============================================================

import datetime
import logging
import threading
import time

import streamlit as st

from tracking.bet_tracker import (
    auto_resolve_bet_results,
    resolve_all_analysis_picks,
)
from tracking.database import (
    load_all_bets,
    load_all_analysis_picks,
)
from styles.theme import get_bet_card_html

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Joseph loading screen ─────────────────────────────────────
try:
    from utils.joseph_loading import joseph_loading_placeholder
    JOSEPH_LOADING_AVAILABLE = True
except ImportError:
    JOSEPH_LOADING_AVAILABLE = False
    joseph_loading_placeholder = None  # type: ignore[assignment]

# ── Constants ─────────────────────────────────────────────────
RESULT_EMOJI = {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄", None: "⏳"}
DFS_PAYOUT_RATIO = 1.82
BREAKEVEN_WIN_RATE = 54.95

# ── Lazy-loaded CLV / Calibration modules ─────────────────────
get_clv_summary = None
get_tier_accuracy_report = None
validate_model_edge = None


def get_clv_fns():
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


def get_calibration_fns():
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


# ── Date helpers ──────────────────────────────────────────────

def tracker_today_date() -> datetime.date:
    try:
        from tracking.bet_tracker import _nba_today_et
        return _nba_today_et()
    except Exception:
        return datetime.date.today()


def tracker_today_iso() -> str:
    return tracker_today_date().isoformat()


def date_window_start(scope_label: str):
    _today = tracker_today_date()
    if scope_label == "Today":
        return _today
    if scope_label == "Last 7 Days":
        return _today - datetime.timedelta(days=6)
    if scope_label == "Last 30 Days":
        return _today - datetime.timedelta(days=29)
    return None


def in_bet_date_window(row: dict, scope_label: str, date_key: str = "bet_date") -> bool:
    _start = date_window_start(scope_label)
    _today = tracker_today_date()
    if _start is None:
        return True
    _raw = str(row.get(date_key) or "")[:10]
    try:
        _d = datetime.date.fromisoformat(_raw)
    except ValueError:
        return False
    return _start <= _d <= _today


# ── Classification helpers ────────────────────────────────────

def is_ai_auto_bet(row: dict) -> bool:
    _source = str(row.get("source") or "").strip().lower()
    _platform = str(row.get("platform") or "").strip().lower()
    _notes = str(row.get("notes") or "").strip().lower()
    _auto = int(row.get("auto_logged", 0) or 0) == 1
    if _source == "joseph" or "joseph" in _platform or "joseph" in _notes:
        return False
    if "smart money" in _platform or "smart money" in _notes:
        return False
    if _source in {"qeg_auto", "smart_pick_pro", "smart_pick_pro_platform", "smartpickpro_auto"}:
        return True
    if _platform in {"smartai-auto", "smartauto-ai", "smart pick pro",
                      "smart pick pro platform picks", "smart pick pro platform"}:
        return True
    if (_notes.startswith("auto-logged by smartai")
            or _notes.startswith("auto-logged by smart pick pro")
            or _notes.startswith("auto-stored by smart pick pro")
            or _notes.startswith("auto-stored by smartai")):
        return True
    if _notes.startswith("added from platform props"):
        return True
    if _auto:
        return True
    return False


def is_joseph_bet(row: dict) -> bool:
    _source = str(row.get("source") or "").strip().lower()
    _platform = str(row.get("platform") or "").strip().lower()
    _notes = str(row.get("notes") or "").strip().lower()
    return _source == "joseph" or "joseph" in _platform or "joseph" in _notes


def platform_display_name(platform_value: str) -> str:
    _plat = str(platform_value or "").strip()
    _norm = _plat.lower()
    if _norm in {"smartai-auto", "smartauto-ai", "smart pick pro",
                  "smart pick pro platform picks", "smart pick pro platform"}:
        return "Smart Pick Pro Platform Picks"
    return _plat


def is_pipeline_bet_for_all_picks(row: dict) -> bool:
    _platform = str(row.get("platform") or "").strip().lower()
    _source = str(row.get("source") or "").strip().lower()
    _auto = int(row.get("auto_logged", 0) or 0) == 1
    return (
        is_ai_auto_bet(row)
        or is_joseph_bet(row)
        or (_platform == "smart money" and _auto)
        or (_source in {"qeg_auto", "joseph"})
    )


# ── Key / normalisation helpers ───────────────────────────────

def canonical_pick_date(row: dict) -> str:
    return str(row.get("pick_date") or row.get("bet_date") or tracker_today_iso())[:10]


def canonical_pick_key(row: dict, *, include_platform: bool = True):
    try:
        _line = str(round(float(row.get("prop_line") or row.get("line") or 0), 2))
    except (TypeError, ValueError):
        _line = "0"
    _base = (
        str(row.get("player_name") or "").strip().lower(),
        str(row.get("stat_type") or "").strip().lower(),
        _line,
        str(row.get("direction") or "").strip().upper(),
        canonical_pick_date(row),
    )
    if include_platform:
        return _base + (str(row.get("platform") or "").strip().lower(),)
    return _base


def normalized_bet_type(row: dict) -> str:
    _raw = str(row.get("bet_type") or "").strip().lower()
    _line_category = str(row.get("line_category") or "").strip().lower()
    _notes = str(row.get("notes") or "").strip().lower()
    if "smart money demon" in _notes:
        return "demon"
    if "smart money goblin" in _notes:
        return "goblin"
    if _raw in {"goblin", "demon", "50_50", "standard", "normal", "fantasy", "joseph_pick", "risky"}:
        return _raw
    if _line_category in {"goblin", "demon", "50_50"}:
        return _line_category
    if _raw:
        return _raw
    return "standard"


def bet_type_display_name(bet_type: str) -> str:
    _bt = str(bet_type or "standard").strip().lower()
    return {"50_50": "50/50", "joseph_pick": "Joseph Pick", "risky": "⚠️ Risky (Avoid)"}.get(_bt, _bt.title())


def bet_type_sort_key(bet_type: str):
    _order = {
        "goblin": 0, "demon": 1, "50_50": 2, "standard": 3,
        "normal": 4, "fantasy": 5, "joseph_pick": 6, "risky": 7,
    }
    _bt = str(bet_type or "standard").strip().lower()
    return (_order.get(_bt, 99), _bt)


# ── Cached data loading ──────────────────────────────────────

@st.cache_data(ttl=10)
def cached_load_all_bets(limit: int = 10000, exclude_linked: bool = True):
    """Load bets from the live database. TTL=10s so DB edits appear within 10 seconds."""
    return load_all_bets(limit=limit, exclude_linked=exclude_linked)


def reload_bets():
    """Force-clear every data cache so the very next access returns fresh DB data."""
    cached_load_all_bets.clear()
    build_merged_pick_universe.clear()


def scope_history_days(scope_label: str) -> int:
    if scope_label == "Today":
        return 1
    if scope_label == "Last 7 Days":
        return 7
    if scope_label == "Last 30 Days":
        return 30
    # "All Time" legacy value — treat as 30 days max to avoid loading all history
    return 30


@st.cache_data(ttl=10, show_spinner=False)
def build_merged_pick_universe(scope_label: str) -> dict:
    """Build the shared merged pick universe used by Health and All Picks.

    Cached (TTL 10 s) so the second call with the same scope is fast
    while still reflecting live DB edits within 10 seconds.
    """
    _history_days = scope_history_days(scope_label)
    _analysis_all = load_all_analysis_picks(days=_history_days)
    _analysis_scope = [p for p in _analysis_all if in_bet_date_window(p, scope_label, "pick_date")]

    _all_bets = cached_load_all_bets(limit=50000)
    _health_side_bets = [b for b in _all_bets if in_bet_date_window(b, scope_label, "bet_date")]
    _pipeline_candidates = [b for b in _health_side_bets if is_pipeline_bet_for_all_picks(b)]

    _analysis_identity_keys = {
        canonical_pick_key(_p, include_platform=False)
        for _p in _analysis_scope
    }

    _pipeline_added = []
    _pipeline_skip_ai_overlap = 0
    for _b in _pipeline_candidates:
        _mapped = dict(_b)
        _mapped["pick_date"] = _mapped.get("pick_date") or _mapped.get("bet_date")
        _mapped["prop_line"] = _mapped.get("prop_line", _mapped.get("line"))
        if is_ai_auto_bet(_mapped) and canonical_pick_key(_mapped, include_platform=False) in _analysis_identity_keys:
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
        # Dedup on player/stat/line/direction/date only — collapse same prop
        # across different platforms, sources, or tiers to avoid inflating counts.
        _key = (
            str(_pick.get("player_name") or "").strip().lower(),
            str(_pick.get("stat_type") or "").strip().lower(),
            _line_key,
            str(_pick.get("direction") or "").strip().upper(),
            canonical_pick_date(_pick),
        )
        if _key in _seen_keys:
            continue
        _seen_keys.add(_key)
        _combined.append(_pick)

    return {
        "analysis_rows": _analysis_scope,
        "health_side_bets": _health_side_bets,
        "pipeline_candidates": _pipeline_candidates,
        "pipeline_added": _pipeline_added,
        "pipeline_skip_ai_overlap": _pipeline_skip_ai_overlap,
        "combined_pre_dedup_count": _combined_pre_dedup_count,
        "dedup_removed": max(0, _combined_pre_dedup_count - len(_combined)),
        "combined": _combined,
    }


# ── Filtering ─────────────────────────────────────────────────

def platform_filter_fn(bet, platform_selections):
    if not platform_selections:
        return True
    plat = str(bet.get("platform") or "").lower()
    for sel in platform_selections:
        if sel == "🟢 PrizePicks" and "prizepicks" in plat:
            return True
        if sel == "🟣 Underdog Fantasy" and "underdog" in plat:
            return True
        if sel == "🔵 DraftKings Pick6" and ("draftkings" in plat or "pick6" in plat or plat == "dk"):
            return True
        if sel == "🤖 Smart Pick Pro Platform Picks" and (
            is_ai_auto_bet(bet) or "smartai-auto" in plat or "smartauto-ai" in plat or "smart pick pro" in plat
        ):
            return True
    return False


def apply_global_filters(bets, player_search, date_range, direction_filter):
    filtered = bets
    if player_search and player_search.strip():
        _q = player_search.strip().lower()
        filtered = [b for b in filtered if _q in str(b.get("player_name", "")).lower()]
    if date_range and len(date_range) == 2:
        _start = date_range[0].isoformat()
        _end = date_range[1].isoformat()
        filtered = [b for b in filtered if _start <= (b.get("bet_date") or b.get("pick_date") or "") <= _end]
    if direction_filter and direction_filter != "All":
        filtered = [b for b in filtered if str(b.get("direction", "")).upper() == direction_filter]
    return filtered


def platform_selection_to_terms(platform_selections):
    terms = []
    for sel in platform_selections:
        if sel == "🟢 PrizePicks":
            terms.append("prizepicks")
        elif sel == "🟣 Underdog Fantasy":
            terms.append("underdog")
        elif sel == "🔵 DraftKings Pick6":
            terms.extend(["draftkings", "pick6", "dk"])
        elif sel == "🤖 Smart Pick Pro Platform Picks":
            terms.extend(["smartai-auto", "smart pick pro"])
    return terms


# ── HTML rendering helpers ────────────────────────────────────

_MAX_CARDS_PER_CHUNK = 10
_MAX_CARDS_TOTAL = 40


def render_bet_cards_chunked(bets, chunk_size=_MAX_CARDS_PER_CHUNK,
                              max_total=_MAX_CARDS_TOTAL,
                              show_live_status=False):
    """Render bet cards in two columns, chunked to avoid WebSocket overflow.

    ``max_total`` caps how many cards are rendered in a single call.
    Any bets beyond the cap are summarised as a count message.
    """
    if not bets:
        return
    display = bets[:max_total]
    truncated = len(bets) - len(display)
    for start in range(0, len(display), chunk_size * 2):
        chunk = display[start:start + chunk_size * 2]
        col_a_cards = [get_bet_card_html(b, show_live_status=show_live_status) for i, b in enumerate(chunk) if i % 2 == 0]
        col_b_cards = [get_bet_card_html(b, show_live_status=show_live_status) for i, b in enumerate(chunk) if i % 2 == 1]
        col_a, col_b = st.columns(2)
        with col_a:
            if col_a_cards:
                st.markdown("\n".join(col_a_cards), unsafe_allow_html=True)
        with col_b:
            if col_b_cards:
                st.markdown("\n".join(col_b_cards), unsafe_allow_html=True)
    if truncated > 0:
        st.caption(f"Showing {max_total} of {len(bets)} cards. Use filters to narrow results.")


# ── Background auto-resolve ───────────────────────────────────

bg_resolve_results: dict = {}


def background_auto_resolve():
    _messages = []
    try:
        _today_str = tracker_today_iso()
        _all_bets_check = load_all_bets(exclude_linked=False)

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
                except Exception as _exc:
                    _logger.warning("Auto-resolve failed for %s: %s", _d, _exc)
            if _total_resolved > 0:
                _messages.append(f"🤖 Auto-resolved {_total_resolved} past bet(s).")

        try:
            from tracking.bet_tracker import resolve_todays_bets
            _today_result = resolve_todays_bets()
            if _today_result.get("resolved", 0) > 0:
                _messages.append(
                    f"⚡ Auto-resolved {_today_result['resolved']} of today's bet(s) "
                    f"({_today_result['wins']}W / {_today_result['losses']}L)."
                )
        except Exception as _exc:
            _logger.debug("Today's bet resolve skipped: %s", _exc)

        try:
            _picks_result = resolve_all_analysis_picks(include_today=False)
            _picks_resolved = _picks_result.get("resolved", 0)
            if _picks_resolved > 0:
                _messages.append(
                    f"📋 Auto-resolved {_picks_resolved} analysis pick(s) "
                    f"({_picks_result.get('wins', 0)}W / {_picks_result.get('losses', 0)}L)."
                )
        except Exception as _exc:
            _logger.debug("Analysis picks resolve skipped: %s", _exc)

        try:
            from engine.clv_tracker import auto_update_closing_lines as _auto_clv
            _clv_result = _auto_clv(days_back=1)
            if _clv_result.get("updated", 0) > 0:
                _messages.append(
                    f"📈 CLV updated: {_clv_result['updated']} record(s) closed "
                    f"with live closing lines."
                )
        except Exception as _exc:
            _logger.debug("CLV auto-update skipped: %s", _exc)

        try:
            from tracking.database import purge_old_sessions
            purge_old_sessions(days=30)
        except Exception:
            pass
    except Exception as _exc:
        _logger.warning("Background auto-resolve error: %s", _exc)

    bg_resolve_results["messages"] = _messages
    bg_resolve_results["done"] = True
