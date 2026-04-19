"""Auto-Resolve tab for Bet Tracker."""
import logging
import time as _time
import streamlit as st
from styles.theme import get_bet_card_html
from tracking.bet_tracker import (
    auto_resolve_bet_results,
    resolve_all_pending_bets,
    regrade_bets_for_date,
)
from tracking.database import load_all_bets, save_daily_snapshot
from pages.helpers.bet_tracker_data import (
    cached_load_all_bets,
    reload_bets,
    tracker_today_iso,
    tracker_today_date,
    platform_filter_fn,
    render_bet_cards_chunked,
    JOSEPH_LOADING_AVAILABLE,
    joseph_loading_placeholder,
)

_logger = logging.getLogger(__name__)


def render(platform_selections, player_search, date_range, direction_filter):
    import datetime

    st.subheader("🤖 Auto-Resolve — Get Actual Stats & Mark Results")
    st.markdown("Automatically retrieve actual player stats and mark pending bets as WIN / LOSS / EVEN.")

    # ── Resolve Today ─────────────────────────────────────────
    st.markdown("### ⚡ Resolve Today's Bets")
    st.caption("Checks live scores for Final games and resolves today's pending bets immediately.")

    _rc1, _rc2 = st.columns([1, 1])
    with _rc1:
        resolve_today_btn = st.button("⚡ Resolve Now", type="primary", key="resolve_now_btn_tab")
    with _rc2:
        regrade_btn = st.button("🩹 Regrade Today's Results", key="regrade_today_btn_tab")

    if resolve_today_btn:
        _loader = joseph_loading_placeholder("Checking today's games") if JOSEPH_LOADING_AVAILABLE else None
        try:
            from tracking.bet_tracker import resolve_todays_bets
            _result = resolve_todays_bets()
            if _loader:
                _loader.empty()
            if _result["resolved"] > 0:
                st.success(
                    f"✅ Resolved **{_result['resolved']}** bet(s): "
                    f"**{_result['wins']}** WIN · **{_result['losses']}** LOSS · **{_result['evens']}** EVEN"
                )
                reload_bets()
                st.rerun()
            else:
                st.info(f"ℹ️ No bets resolved. Still pending: {_result.get('pending', 0)}")
            if _result.get("errors"):
                st.warning("⚠️ " + " | ".join(_result["errors"][:3]))
        except Exception as _err:
            if _loader:
                _loader.empty()
            st.error(f"❌ Resolve failed: {_err}")

    if regrade_btn:
        _loader = joseph_loading_placeholder("Regrading today's bets") if JOSEPH_LOADING_AVAILABLE else None
        try:
            _rg = regrade_bets_for_date(tracker_today_iso())
            if _loader:
                _loader.empty()
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
                                f"{_chg.get('old_result')} → {_chg.get('new_result')}"
                            )
                reload_bets()
                st.rerun()
            elif _rg.get("checked", 0) > 0:
                st.info(f"ℹ️ Regrade checked **{_rg['checked']}** bet(s). No corrections needed.")
            else:
                st.warning("⚠️ No graded bets could be rechecked yet.")
            if _rg.get("errors"):
                with st.expander(f"⚠️ {len(_rg['errors'])} issue(s)"):
                    for _e in _rg["errors"][:100]:
                        st.markdown(f"- {_e}")
        except Exception as _err:
            if _loader:
                _loader.empty()
            st.error(f"❌ Regrade failed: {_err}")

    st.divider()

    # ── Live Status ───────────────────────────────────────────
    st.markdown("### 🔄 Live Bet Status — Today's Picks")
    _today_str = tracker_today_iso()
    _today_bets_all = cached_load_all_bets(exclude_linked=False)
    _today_bets = [
        b for b in _today_bets_all
        if b.get("bet_date") == _today_str and platform_filter_fn(b, platform_selections)
    ]
    _today_pending = [b for b in _today_bets if not b.get("result")]

    auto_refresh = st.checkbox("🔁 Auto-refresh live status (every 60s)", value=False, key="auto_refresh_resolve")

    if _today_bets:
        if _today_pending:
            try:
                from tracking.bet_tracker import get_live_bet_status
                _live = get_live_bet_status(_today_pending)
            except Exception:
                _live = _today_pending
            render_bet_cards_chunked(_live, show_live_status=True)

            _resolved_today = [b for b in _today_bets if b.get("result")]
            if _resolved_today:
                st.markdown("**✅ Already Resolved Today:**")
                render_bet_cards_chunked(_resolved_today)
        else:
            st.markdown("**Today's Bets (All Resolved):**")
            render_bet_cards_chunked(_today_bets)
    else:
        st.info("No bets logged for today yet.")

    if auto_refresh:
        st.info("🔄 Auto-refresh enabled — page will refresh in ~60 seconds.")
        if st.session_state.get("_auto_refresh_ts", 0) == 0:
            st.session_state["_auto_refresh_ts"] = _time.time()
        _elapsed = _time.time() - st.session_state.get("_auto_refresh_ts", _time.time())
        if _elapsed >= 60:
            st.session_state["_auto_refresh_ts"] = _time.time()
            try:
                from tracking.bet_tracker import resolve_todays_bets as _rtr
                _r = _rtr()
                if _r.get("resolved", 0) > 0:
                    reload_bets()
                    st.toast(f"🔄 Auto-resolved {_r['resolved']} bet(s)")
            except Exception:
                pass
            st.rerun()
    else:
        st.session_state.pop("_auto_refresh_ts", None)

    st.divider()

    # ── Resolve Past Bets ─────────────────────────────────────
    st.markdown("### 🗓️ Resolve Past Bets")
    _past_all = cached_load_all_bets(exclude_linked=False)
    _pending_past = [
        b for b in _past_all
        if not b.get("result") and b.get("bet_date", "") < _today_str and platform_filter_fn(b, platform_selections)
    ]

    if not _pending_past:
        st.info("✅ No past pending bets found.")
    else:
        st.markdown(f"**{len(_pending_past)} past pending bet(s):**")
        render_bet_cards_chunked(_pending_past)

    _dc, _bc = st.columns([2, 1])
    with _dc:
        _yesterday = tracker_today_date() - datetime.timedelta(days=1)
        resolve_date = st.date_input("Date to resolve", value=_yesterday, key="resolve_date_input")
    with _bc:
        st.markdown("<br>", unsafe_allow_html=True)
        resolve_btn = st.button("🔄 Get Actual Stats & Auto-Resolve", type="primary", key="resolve_past_btn")

    if resolve_btn:
        _loader = joseph_loading_placeholder(f"Resolving for {resolve_date.isoformat()}") if JOSEPH_LOADING_AVAILABLE else None
        try:
            resolved, errors = auto_resolve_bet_results(date_str=resolve_date.isoformat())
        finally:
            if _loader:
                _loader.empty()
        if resolved > 0:
            try:
                save_daily_snapshot(resolve_date.isoformat())
            except Exception:
                pass
            st.success(f"✅ Auto-resolved **{resolved}** bet(s) for {resolve_date.isoformat()}.")
            reload_bets()
            st.rerun()
        else:
            st.warning(f"⚠️ No bets resolved for {resolve_date.isoformat()}.")
        if errors:
            with st.expander(f"⚠️ {len(errors)} error(s)"):
                for err in errors:
                    st.markdown(f"- {err}")

    st.divider()

    # ── Resolve All ───────────────────────────────────────────
    st.markdown("### 🔄 Resolve All Pending Bets")
    st.markdown("Resolves **every** unresolved bet — manual bets, AI picks, and bets from any platform or date.")
    if st.button("🔄 Resolve All Pending Bets", type="primary", key="resolve_all_pending_btn"):
        _loader = joseph_loading_placeholder("Resolving all pending bets") if JOSEPH_LOADING_AVAILABLE else None
        try:
            _result = resolve_all_pending_bets()
            if _loader:
                _loader.empty()
            _resolved = _result.get("resolved", 0)
            if _resolved > 0:
                st.success(
                    f"✅ Resolved **{_resolved}** bet(s) — "
                    f"{_result.get('wins', 0)} W / {_result.get('losses', 0)} L / {_result.get('evens', 0)} Even"
                )
                _by_date = _result.get("by_date", {})
                if _by_date:
                    for _d, _cnt in sorted(_by_date.items()):
                        st.markdown(f"  • **{_d}**: {_cnt} resolved")
                reload_bets()
                st.rerun()
            else:
                st.info("No pending bets found to resolve.")
            _errors = _result.get("errors", [])
            if _errors:
                st.warning("⚠️ " + " | ".join(_errors[:3]))
                if len(_errors) > 3:
                    with st.expander(f"See all {len(_errors)} error(s)"):
                        for err in _errors:
                            st.markdown(f"- {err}")
        except Exception as _err:
            if _loader:
                _loader.empty()
            _err_str = str(_err)
            if "WebSocketClosedError" not in _err_str and "StreamClosedError" not in _err_str:
                st.error(f"❌ Resolve all failed: {_err}")
