"""History tab for Bet Tracker."""
import streamlit as st
from utils.rbac import has_permission, permission_gate
from tracking.database import get_rolling_stats
from pages.helpers.bet_tracker_helpers import get_calendar_heatmap_html
from pages.helpers.bet_tracker_data import (
    cached_load_all_bets,
    platform_filter_fn,
    apply_global_filters,
    render_bet_cards_chunked,
    DFS_PAYOUT_RATIO,
    BREAKEVEN_WIN_RATE,
)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("📅 2-Week Rolling History")
    st.markdown("Day-by-day breakdown of the last 14 days.")

    rolling_stats = get_rolling_stats(days=14)
    snapshots = rolling_stats.get("snapshots", [])

    # Calendar heatmap
    _all = cached_load_all_bets()
    _filtered = apply_global_filters(
        [b for b in _all if platform_filter_fn(b, platform_selections)],
        player_search, date_range, direction_filter,
    )
    _by_date: dict = {}
    for _b in _filtered:
        _by_date.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)
    if _by_date:
        with st.expander("🟩 Win Rate Heatmap (last 6 weeks)", expanded=True):
            st.markdown(get_calendar_heatmap_html(_by_date, num_days=42), unsafe_allow_html=True)
            st.caption("Hover for daily stats. Green = winning, Red = losing.")

    # Rolling summary
    if rolling_stats.get("total_bets", 0) > 0:
        _streak = rolling_stats.get("streak", 0)
        _slabel = f"🔥 W{_streak}" if _streak > 0 else f"❄️ L{abs(_streak)}" if _streak < 0 else "—"
        _best = rolling_stats.get("best_day", {})
        _worst = rolling_stats.get("worst_day", {})
        _bs = f"{_best.get('snapshot_date', '—')} ({_best.get('win_rate', 0):.0f}%)" if _best else "—"
        _ws = f"{_worst.get('snapshot_date', '—')} ({_worst.get('win_rate', 0):.0f}%)" if _worst else "—"
        _c = st.columns(5)
        _c[0].metric("14-Day Bets", rolling_stats.get("total_bets", 0))
        _c[1].metric("Win Rate", f"{rolling_stats.get('win_rate', 0):.1f}%")
        _c[2].metric("Streak", _slabel)
        _c[3].metric("Best Day", _bs)
        _c[4].metric("Worst Day", _ws)

        # ── Shareable Report Card ─────────────────────────────
        from utils.components import generate_performance_report_html
        _report_html = generate_performance_report_html({
            "total": rolling_stats.get("total_bets", 0),
            "wins": rolling_stats.get("wins", 0),
            "losses": rolling_stats.get("losses", 0),
            "evens": 0,
            "pending": 0,
            "win_rate": rolling_stats.get("win_rate", 0),
            "streak": rolling_stats.get("streak", 0),
            "best_platform": "",
            "date_range": "Last 14 Days",
        })
        if has_permission("export_data"):
            st.download_button(
                "📊 Download Report Card",
                data=_report_html,
                file_name="smartbetpro_report_card.html",
                mime="text/html",
                key="download_report_card_history",
            )
        else:
            permission_gate("export_data", show_upgrade_button=False)
            st.caption("🔒 Report Card export requires **Smart Money** or above.")
        st.divider()

    # Cumulative P&L curve
    _all_hist = cached_load_all_bets()
    _resolved = sorted(
        [b for b in _all_hist if b.get("result") in ("WIN", "LOSS", "EVEN") and platform_filter_fn(b, platform_selections)],
        key=lambda b: (b.get("bet_date", ""), b.get("id", 0)),
    )

    if len(_resolved) >= 3:
        with st.expander("📈 Cumulative P&L Curve", expanded=True):
            _cum = 0.0
            _dollar = 0.0
            _vals = []
            _max_pnl = 0.0
            for _rb in _resolved:
                _res = _rb.get("result", "")
                _fee = float(_rb.get("entry_fee") or 0)
                if _res == "WIN":
                    _cum += DFS_PAYOUT_RATIO
                    _dollar += _fee * DFS_PAYOUT_RATIO if _fee > 0 else 0
                elif _res == "LOSS":
                    _cum -= 1.0
                    _dollar -= _fee if _fee > 0 else 0
                _vals.append(round(_cum, 2))
                _max_pnl = max(_max_pnl, _cum)

            _wins_t = sum(1 for b in _resolved if b.get("result") == "WIN")
            _losses_t = sum(1 for b in _resolved if b.get("result") == "LOSS")
            _wr_t = _wins_t / max(_wins_t + _losses_t, 1) * 100
            _dd = _max_pnl - _cum if _max_pnl > 0 else 0
            _dd_pct = (_dd / max(_max_pnl, 0.01)) * 100 if _max_pnl > 0 else 0

            _mc = st.columns(5)
            _mc[0].metric("Resolved Bets", len(_resolved))
            _mc[1].metric("Win Rate", f"{_wr_t:.1f}%", delta=f"{_wr_t - BREAKEVEN_WIN_RATE:+.1f}% vs breakeven")
            _mc[2].metric("Unit P&L", f"{_cum:+.2f}u")
            if _dollar != 0:
                _mc[3].metric("Dollar P&L", f"${_dollar:+.2f}",
                              delta="profitable" if _dollar > 0 else "losing")
            else:
                _mc[3].metric("ROI/bet", f"{_cum / max(len(_resolved), 1):+.3f}u",
                              delta="profitable" if _cum > 0 else "losing")
            _mc[4].metric("Drawdown", f"{_dd_pct:.1f}%",
                          delta=f"{_dd:+.2f}u from peak" if _dd > 0 else "At peak",
                          delta_color="inverse" if _dd > 0 else "normal")

            st.line_chart({"Cumulative P&L (units)": _vals}, height=220)
            st.caption(f"📊 {len(_resolved)} resolved · {_wins_t}W / {_losses_t}L · Final: {_cum:+.2f}u")

            # Daily P&L table
            _daily: dict = {}
            _cum2 = 0.0
            for _rb in _resolved:
                _res = _rb.get("result", "")
                if _res == "WIN":
                    _cum2 += DFS_PAYOUT_RATIO
                elif _res == "LOSS":
                    _cum2 -= 1.0
                _daily[_rb.get("bet_date", "")] = round(_cum2, 2)
            if _daily:
                _dr = [{"Date": d, "End-of-Day P&L": f"{v:+.2f}u"} for d, v in sorted(_daily.items(), reverse=True)[:14]]
                st.dataframe(_dr, hide_index=True, use_container_width=True)
        st.divider()

    # History filter
    hist_filter = st.radio("History filter", ["All", "Wins Only", "Losses Only", "Pending"],
                           horizontal=True, label_visibility="collapsed", key="history_filter_radio")

    # Day-by-day timeline (limit card rendering to most recent 5 dates)
    _MAX_CARD_DATES = 5
    if not snapshots:
        all_hist = cached_load_all_bets()
        all_hist = [b for b in all_hist if platform_filter_fn(b, platform_selections)]
        _bd: dict = {}
        for _b in all_hist:
            _bd.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)
        if not _bd:
            from utils.components import render_empty_state
            render_empty_state(
                "📅", "No Betting History",
                "Your daily bet history will appear here once you log or auto-track your first bets.",
                "💡 Run analysis on the ⚡ Quantum Analysis page to get started.",
            )
        else:
            _sorted_dates = sorted(_bd.keys(), reverse=True)
            for _idx, _date in enumerate(_sorted_dates):
                _day = _bd[_date]
                _w = sum(1 for b in _day if b.get("result") == "WIN")
                _l = sum(1 for b in _day if b.get("result") == "LOSS")
                _dd2 = _w + _l
                _wr2 = round(_w / max(_dd2, 1) * 100, 1) if _dd2 > 0 else None
                _color = "🟢" if _wr2 is not None and _wr2 >= 55 else "🔴" if _wr2 is not None and _wr2 < 45 else "🟡"
                _wrs = f" — {_wr2:.0f}% win rate" if _wr2 is not None else " — ⏳ pending"
                _label = f"{_color} {_date} · {len(_day)} picks · ✅{_w} ❌{_l}{_wrs}"

                if hist_filter == "Wins Only":
                    _show = [b for b in _day if b.get("result") == "WIN"]
                elif hist_filter == "Losses Only":
                    _show = [b for b in _day if b.get("result") == "LOSS"]
                elif hist_filter == "Pending":
                    _show = [b for b in _day if not b.get("result")]
                else:
                    _show = _day
                if not _show and hist_filter != "All":
                    continue
                with st.expander(_label, expanded=(_idx == 0)):
                    if not _show:
                        st.info(f"No bets match '{hist_filter}'.")
                    elif _idx < _MAX_CARD_DATES:
                        render_bet_cards_chunked(_show)
                    else:
                        _rows = [{"Player": b.get("player_name", "—"),
                                  "Stat": str(b.get("stat_type", "—")).replace("_", " ").title(),
                                  "Line": b.get("prop_line", "—"), "Dir": b.get("direction", "—"),
                                  "Result": {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄"}.get(b.get("result") or "", "⏳"),
                                  "Tier": b.get("tier", "—")} for b in _show]
                        st.dataframe(_rows, use_container_width=True, hide_index=True)
    else:
        all_hist = cached_load_all_bets()
        all_hist = [b for b in all_hist if platform_filter_fn(b, platform_selections)]
        _bd2: dict = {}
        for _b in all_hist:
            _bd2.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)
        for _idx2, snap in enumerate(snapshots):
            _date = snap.get("snapshot_date", "")
            _w = snap.get("wins", 0)
            _l = snap.get("losses", 0)
            _total = snap.get("total_picks", 0)
            _wr2 = snap.get("win_rate", 0.0)
            _color = "🟢" if _wr2 >= 55 else "🔴" if _wr2 < 45 and (_w + _l) > 0 else "🟡"
            _wrs = f" — {_wr2:.0f}% win rate" if (_w + _l) > 0 else " — ⏳ all pending"
            _label = f"{_color} {_date} · {_total} picks · ✅{_w} ❌{_l}{_wrs}"
            _day = _bd2.get(_date, [])
            if hist_filter == "Wins Only":
                _show = [b for b in _day if b.get("result") == "WIN"]
            elif hist_filter == "Losses Only":
                _show = [b for b in _day if b.get("result") == "LOSS"]
            elif hist_filter == "Pending":
                _show = [b for b in _day if not b.get("result")]
            else:
                _show = _day
            if not _show and hist_filter != "All" and _total == 0:
                continue
            with st.expander(_label):
                if not _show:
                    st.info(f"No bets match '{hist_filter}'." if _total > 0 else "No bets for this day.")
                elif _idx2 < _MAX_CARD_DATES:
                    render_bet_cards_chunked(_show)
                else:
                    _rows = [{"Player": b.get("player_name", "—"),
                              "Stat": str(b.get("stat_type", "—")).replace("_", " ").title(),
                              "Line": b.get("prop_line", "—"), "Dir": b.get("direction", "—"),
                              "Result": {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄"}.get(b.get("result") or "", "⏳"),
                              "Tier": b.get("tier", "—")} for b in _show]
                    st.dataframe(_rows, use_container_width=True, hide_index=True)
