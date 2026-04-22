"""Model Health tab for Bet Tracker."""
import logging
import streamlit as st
from styles.theme import (
    get_education_box_html,
    get_summary_cards_html,
    get_styled_stats_table_html,
)
from tracking.bet_tracker import get_model_performance_stats
import pages.helpers.bet_tracker_data as btd
from pages.helpers.bet_tracker_data import (
    build_merged_pick_universe,
    platform_filter_fn,
    apply_global_filters,
    canonical_pick_date,
    normalized_bet_type,
    bet_type_display_name,
    bet_type_sort_key,
    is_ai_auto_bet,
    get_clv_fns,
    get_calibration_fns,
)

_logger = logging.getLogger(__name__)


def render(platform_selections, player_search, date_range, direction_filter):
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

    _col1, _col2 = st.columns([2, 5])
    st.session_state.setdefault("health_scope_filter", "Today")
    with _col1:
        _health_scope = st.selectbox(
            "Health Scope",
            ["Today", "Last 7 Days", "All Time"],
            key="health_scope_filter",
            help="Choose which date window feeds Model Health stats.",
        )
    with _col2:
        st.caption("Health now uses the same merged pick universe as All Picks for matching totals under the same scope.")

    _health_universe = build_merged_pick_universe(_health_scope)
    # Do NOT apply the global date_range here — the Health Scope selectbox above
    # is the date control for this tab.  Passing date_range would override the
    # scope and restrict results to whatever day the global picker is set to.
    filtered_health = apply_global_filters(
        [p for p in _health_universe["combined"] if platform_filter_fn(p, platform_selections)],
        player_search, None, direction_filter,
    )
    resolved_health = [b for b in filtered_health if b.get("result") in ("WIN", "LOSS", "EVEN")]
    wins_h = sum(1 for b in resolved_health if b.get("result") == "WIN")
    losses_h = sum(1 for b in resolved_health if b.get("result") == "LOSS")
    evens_h = sum(1 for b in resolved_health if b.get("result") == "EVEN")
    total_h = len(resolved_health)
    win_rate_h = round(wins_h / max(wins_h + losses_h, 1) * 100, 1)
    pending_h = sum(1 for b in filtered_health if not b.get("result"))

    # Streak
    streak_val = 0
    _sorted_res = sorted(
        [b for b in filtered_health if b.get("result") in ("WIN", "LOSS")],
        key=lambda b: canonical_pick_date(b), reverse=True,
    )
    if _sorted_res:
        _first = _sorted_res[0].get("result")
        streak_val = 1 if _first == "WIN" else -1
        for _hb in _sorted_res[1:]:
            if _hb.get("result") == _first:
                streak_val += 1 if _first == "WIN" else -1
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

    st.markdown(
        get_summary_cards_html(
            total=len(filtered_health), wins=wins_h, losses=losses_h,
            evens=evens_h, pending=pending_h, win_rate=win_rate_h,
            streak=streak_val, best_platform=best_platform,
            total_label="Total Picks",
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        f"Scope source = {len(_health_universe['analysis_rows'])} persisted analysis rows + "
        f"{len(_health_universe['pipeline_added'])} pipeline/tracker rows "
        f"(-{_health_universe['pipeline_skip_ai_overlap']} SmartAI overlaps) "
        f"= {_health_universe.get('combined_pre_dedup_count', len(_health_universe['combined']))} pre-dedup rows "
        f"(-{_health_universe.get('dedup_removed', 0)} duplicates) "
        f"= {len(_health_universe['combined'])} merged picks; "
        f"{len(filtered_health)} currently shown."
    )

    if total_h == 0:
        from utils.components import render_empty_state
        render_empty_state(
            "📊", "No Model Health Data Yet",
            "Win rates, tier breakdowns, and calibration charts will appear here once you have resolved bets.",
            "💡 Run analysis → auto-resolve after games finish → see model performance here.",
        )

    # ── Notifications ─────────────────────────────────────────
    if total_h > 0:
        from utils.components import add_notification as _add_notif
        _recent = sorted(resolved_health, key=lambda b: b.get("bet_date", ""), reverse=True)
        _consec_losses = 0
        for _rb in _recent:
            if _rb.get("result") == "LOSS":
                _consec_losses += 1
            else:
                break
        if _consec_losses >= 3:
            st.warning(
                f"🧊 **Tilt Alert** — **{_consec_losses} consecutive losses**. "
                "Consider reducing unit size."
            )
            _add_notif("Tilt Alert", f"{_consec_losses} consecutive losses — consider reducing unit size.", "warning")
        _consec_wins = 0
        for _rb in _recent:
            if _rb.get("result") == "WIN":
                _consec_wins += 1
            else:
                break
        if _consec_wins >= 5:
            st.success(f"🔥 **Hot Streak Alert** — **{_consec_wins}-game win streak**!")
            _add_notif("Hot Streak", f"{_consec_wins}-game win streak!", "success")
        _last_20 = _recent[:20]
        if len(_last_20) >= 20:
            _l20_wr = sum(1 for b in _last_20 if b.get("result") == "WIN") / 20 * 100
            if _l20_wr < 50:
                st.error(f"📉 **Model Drift Warning** — Last 20 bets win rate: **{_l20_wr:.0f}%**.")
                _add_notif("Model Drift", f"Last 20 bets win rate: {_l20_wr:.0f}%.", "error")

    if total_h > 0:
        st.divider()
        performance_stats = get_model_performance_stats(bets_list=filtered_health)

        # Win rate by tier
        with st.expander("🏆 Win Rate by Tier", expanded=True):
            tier_perf = performance_stats.get("by_tier", {})
            if tier_perf:
                tier_order = ["Platinum", "Gold", "Silver", "Bronze"]
                tier_rows = [
                    {"Tier": t, "Total": tier_perf[t].get("total", 0),
                     "Wins": tier_perf[t].get("wins", 0),
                     "Losses": tier_perf[t].get("losses", 0),
                     "Win Rate": f"{tier_perf[t].get('win_rate', 0):.1f}%"}
                    for t in tier_order if t in tier_perf
                ]
                st.markdown(get_styled_stats_table_html(tier_rows, ["Tier", "Total", "Wins", "Losses", "Win Rate"]), unsafe_allow_html=True)
                _icons = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
                _cols = st.columns(4)
                for _i, _tn in enumerate(["Platinum", "Gold", "Silver", "Bronze"]):
                    if _tn in tier_perf:
                        _td = tier_perf[_tn]
                        _cols[_i].metric(
                            f"{_icons[_tn]} {_tn}", f"{_td.get('win_rate', 0):.1f}%",
                            help=f"{_tn}: {_td.get('wins', 0)}W / {_td.get('losses', 0)}L ({_td.get('total', 0)} total)",
                        )
                # Bar chart
                _chart_data = []
                for _tn in tier_order:
                    if _tn in tier_perf and tier_perf[_tn].get("total", 0) > 0:
                        _chart_data.append({"Tier": f"{_icons.get(_tn, '')} {_tn}", "Win Rate": tier_perf[_tn].get("win_rate", 0)})
                if _chart_data:
                    import pandas as _pd
                    st.markdown("##### Tier Win Rate Validation")
                    st.bar_chart(_pd.DataFrame(_chart_data).set_index("Tier")["Win Rate"], color="#F9C62B")
                    _tier_wr = {d["Tier"]: d["Win Rate"] for d in _chart_data}
                    _names = [f"{_icons.get(t, '')} {t}" for t in tier_order if f"{_icons.get(t, '')} {t}" in _tier_wr]
                    for _i in range(len(_names) - 1):
                        _h, _lo = _names[_i], _names[_i + 1]
                        if _tier_wr.get(_h, 0) < _tier_wr.get(_lo, 0) - 5:
                            st.warning(f"⚠️ **Tier Inversion**: {_h} ({_tier_wr[_h]:.1f}%) < {_lo} ({_tier_wr[_lo]:.1f}%)")
            else:
                st.caption("No tier data yet.")

        # Win rate by platform
        with st.expander("🎰 Win Rate by Platform", expanded=True):
            plat_perf = performance_stats.get("by_platform", {})
            if plat_perf:
                plat_rows = [
                    {"Platform": p, "Total": d.get("total", 0), "Wins": d.get("wins", 0),
                     "Win Rate": f"{d.get('win_rate', 0):.1f}%"}
                    for p, d in plat_perf.items()
                ]
                st.markdown(get_styled_stats_table_html(plat_rows, ["Platform", "Total", "Wins", "Win Rate"]), unsafe_allow_html=True)
            else:
                st.caption("No platform data yet.")

        # Win rate by stat type
        with st.expander("📐 Win Rate by Stat Type", expanded=False):
            stat_perf = performance_stats.get("by_stat_type", {})
            if stat_perf:
                stat_rows = [
                    {"Stat Type": s.capitalize(), "Total": d.get("total", 0), "Wins": d.get("wins", 0),
                     "Win Rate": f"{d.get('win_rate', 0):.1f}%"}
                    for s, d in sorted(stat_perf.items())
                ]
                st.markdown(get_styled_stats_table_html(stat_rows, ["Stat Type", "Total", "Wins", "Win Rate"]), unsafe_allow_html=True)
            else:
                st.caption("No stat type data yet.")

        # Win rate by bet classification
        _bt_perf: dict = {}
        for _hb in resolved_health:
            _bt = normalized_bet_type(_hb)
            if _bt not in _bt_perf:
                _bt_perf[_bt] = {"wins": 0, "losses": 0, "total": 0}
            _bt_perf[_bt]["total"] += 1
            if _hb.get("result") == "WIN":
                _bt_perf[_bt]["wins"] += 1
            elif _hb.get("result") == "LOSS":
                _bt_perf[_bt]["losses"] += 1
        if _bt_perf:
            with st.expander("Win Rate by Bet Classification", expanded=True):
                bt_rows = [
                    {"Bet Type": bet_type_display_name(bt),
                     "Total": d.get("total", 0), "Wins": d.get("wins", 0),
                     "Losses": d.get("losses", 0),
                     "Win Rate": f"{round(d['wins'] / max(d['wins'] + d['losses'], 1) * 100, 1):.1f}%"}
                    for bt, d in sorted(_bt_perf.items(), key=lambda item: bet_type_sort_key(item[0]))
                ]
                st.markdown(get_styled_stats_table_html(bt_rows, ["Bet Type", "Total", "Wins", "Losses", "Win Rate"]), unsafe_allow_html=True)

        # ── Risky/Avoid Bets tracker ─────────────────────────────────────────
        _risky_all = [
            b for b in filtered_health
            if normalized_bet_type(b) == "risky"
            or int(b.get("is_risky", 0) or 0) == 1
        ]
        _risky_resolved = [b for b in _risky_all if b.get("result") in ("WIN", "LOSS", "EVEN")]
        _risky_wins = sum(1 for b in _risky_resolved if b.get("result") == "WIN")
        _risky_losses = sum(1 for b in _risky_resolved if b.get("result") == "LOSS")
        _risky_pending = len(_risky_all) - len(_risky_resolved)
        _risky_win_pct = round(_risky_wins / max(_risky_wins + _risky_losses, 1) * 100, 1)
        with st.expander(f"⚠️ Risky/Avoid Bets — {len(_risky_all)} logged", expanded=True):
            if not _risky_all:
                st.caption("No risky/avoid picks logged yet. Run analysis and avoid picks will be tracked here automatically.")
            else:
                _rc1, _rc2, _rc3, _rc4 = st.columns(4)
                _rc1.metric("⚠️ Total Risky", len(_risky_all), help="Picks flagged as Avoid by the analysis engine")
                _rc2.metric("✅ Wins", _risky_wins)
                _rc3.metric("❌ Losses", _risky_losses)
                _rc4.metric("Win %", f"{_risky_win_pct:.1f}%", help=f"Pending: {_risky_pending}")
                if _risky_resolved:
                    st.markdown(get_styled_stats_table_html(
                        [{"Metric": "Total Logged", "Value": len(_risky_all)},
                         {"Metric": "Resolved", "Value": len(_risky_resolved)},
                         {"Metric": "Wins", "Value": _risky_wins},
                         {"Metric": "Losses", "Value": _risky_losses},
                         {"Metric": "Pending", "Value": _risky_pending},
                         {"Metric": "Win %", "Value": f"{_risky_win_pct:.1f}%"},
                         {"Metric": "Loss %", "Value": f"{round(_risky_losses / max(_risky_wins + _risky_losses, 1) * 100, 1):.1f}%"}],
                        ["Metric", "Value"]
                    ), unsafe_allow_html=True)
                    st.caption("💡 If Risky picks are winning at >50%, the avoid signal may be over-conservative for your slate.")

        # Win rate by pick source
        _ps_all = performance_stats.get("all_bets", [])
        _ps_resolved = [b for b in _ps_all if b.get("result") in ("WIN", "LOSS", "EVEN")]
        if _ps_resolved:
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

                def _incr(bucket, result=_pb_result):
                    if result == "WIN":
                        bucket["wins"] += 1
                        bucket["total"] += 1
                    elif result == "LOSS":
                        bucket["losses"] += 1
                        bucket["total"] += 1

                if _pb_auto and not _pb_is_joseph and not _pb_is_smart_money:
                    _incr(_ps_sources["QEG Picks"])
                if _pb_is_joseph:
                    _incr(_ps_sources["Joseph M Smith"])
                if _pb_is_goblin:
                    _incr(_ps_sources["Goblins"])
                if _pb_is_smart_money:
                    _incr(_ps_sources["Smart Money"])
                if _pb_auto:
                    _incr(_ps_sources["Smart Pick Pro Platform Picks"])

            _ps_sources = {k: v for k, v in _ps_sources.items() if v["total"] > 0}
            if _ps_sources:
                for _psd in _ps_sources.values():
                    _psd["win_rate"] = round(_psd["wins"] / _psd["total"] * 100, 1) if _psd["total"] > 0 else 0.0
                with st.expander("🎯 Win Rate by Pick Source", expanded=True):
                    _ps_rows = [
                        {"Source": src, "Total": d["total"], "Wins": d["wins"],
                         "Losses": d["losses"], "Win Rate": f"{d['win_rate']:.1f}%"}
                        for src, d in _ps_sources.items()
                    ]
                    st.markdown(get_styled_stats_table_html(_ps_rows, ["Source", "Total", "Wins", "Losses", "Win Rate"]), unsafe_allow_html=True)
                    _ps_icons = {"QEG Picks": "⚛️", "Joseph M Smith": "🎙️", "Goblins": "👺",
                                 "Smart Money": "💰", "Smart Pick Pro Platform Picks": "🤖"}
                    _ps_cols = st.columns(len(_ps_sources))
                    for _pi, (src, d) in enumerate(_ps_sources.items()):
                        _ps_cols[_pi].metric(
                            f"{_ps_icons.get(src, '📊')} {src}", f"{d['win_rate']:.1f}%",
                            help=f"{src}: {d['wins']}W / {d['losses']}L ({d['total']} total)",
                        )

        # CLV, tier accuracy, calibration
        try:
            get_clv_fns()
            if btd.get_tier_accuracy_report:
                st.subheader("📊 Model Tier Accuracy")
                _report = btd.get_tier_accuracy_report(days=90)
                if _report.get("has_data"):
                    for _tier, _stats in _report.get("by_tier", {}).items():
                        _ca, _cb, _cc = st.columns(3)
                        _ca.metric(f"{_tier} — Avg CLV", f"{_stats.get('avg_clv', 0):.3f}")
                        _cb.metric("Positive CLV Rate", f"{_stats.get('positive_clv_rate', 0)*100:.1f}%")
                        if _stats.get("win_rate") is not None:
                            _cc.metric("Win Rate", f"{_stats['win_rate']*100:.1f}%")
                        else:
                            _cc.caption("Win rate: no bet results recorded yet")
                else:
                    st.info("📊 Tier accuracy report will appear after recording bets and closing lines.")
        except Exception as _exc:
            _logger.warning("[Health] tier accuracy: %s", _exc)

        try:
            get_calibration_fns()
            if btd.get_isotonic_calibration_curve:
                st.subheader("📈 Isotonic Calibration Curve")
                _iso = btd.get_isotonic_calibration_curve(days=90)
                if _iso.get("has_data"):
                    st.caption(f"Based on {_iso['total_records']} predictions | "
                               f"{'Isotonic smoothing' if _iso['is_isotonic'] else 'Coarse buckets (need 200+)'}")
                    for _pt in _iso.get("curve", []):
                        _gap = _pt["actual"] - _pt["predicted"]
                        _ind = "✅" if abs(_gap) < 0.05 else ("📈" if _gap > 0 else "📉")
                        st.markdown(
                            f"{_ind} **{_pt['predicted']*100:.0f}%** predicted → "
                            f"**{_pt['actual']*100:.1f}%** actual (n={_pt['count']})"
                        )
                else:
                    st.info("📈 Isotonic calibration curve will appear after 200+ bets.")
        except Exception as _exc:
            _logger.warning("[Health] calibration: %s", _exc)

        try:
            get_clv_fns()
            _gcs = btd.get_clv_summary
            if _gcs:
                st.subheader("📈 Closing Line Value (CLV) Summary")
                _clv = _gcs()
                if _clv and _clv.get("has_data"):
                    _c1, _c2, _c3 = st.columns(3)
                    _c1.metric("Total CLV Records", _clv.get("total_records", 0))
                    _avg = _clv.get("avg_clv", 0)
                    _c2.metric("Average CLV", f"{_avg:+.3f}",
                               delta="Beating the market" if _avg > 0 else "Behind the market",
                               delta_color="normal" if _avg > 0 else "inverse")
                    _pos = _clv.get("positive_clv_rate", 0)
                    _c3.metric("Positive CLV Rate", f"{_pos * 100:.1f}%")
                    _by_tier = _clv.get("clv_by_tier", {})
                    if _by_tier:
                        st.markdown("**CLV by Tier:**")
                        for _tn, _tc in _by_tier.items():
                            _ta = _tc.get("avg_clv", 0)
                            _tp = _tc.get("positive_clv_rate", 0)
                            _tn_cnt = _tc.get("count", 0)
                            _icon = "🟢" if _ta > 0 else "🔴"
                            st.markdown(f"{_icon} **{_tn}**: avg CLV {_ta:+.3f} · positive rate {_tp * 100:.1f}% · {_tn_cnt} record(s)")
                    _interp = _clv.get("interpretation", "")
                    if _interp:
                        st.info(f"💡 {_interp}")
                else:
                    st.info("📈 CLV summary will appear after recording bets and tracking closing lines.")
        except Exception as _exc:
            _logger.warning("[Health] CLV summary: %s", _exc)
