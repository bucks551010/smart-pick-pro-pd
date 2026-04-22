"""All Picks tab for Bet Tracker."""
import streamlit as st
from styles.theme import (
    get_summary_cards_html,
    get_styled_stats_table_html,
    get_bet_card_html,
)
from tracking.bet_tracker import (
    auto_resolve_bet_results,
    resolve_all_pending_bets,
    resolve_all_analysis_picks,
)
from tracking.database import (
    get_analysis_pick_dates,
    load_analysis_picks_for_date,
    export_bets_csv,
)
from pages.helpers.bet_tracker_data import (
    build_merged_pick_universe,
    cached_load_all_bets,
    reload_bets,
    platform_filter_fn,
    apply_global_filters,
    canonical_pick_date,
    in_bet_date_window,
    tracker_today_iso,
    is_ai_auto_bet,
    platform_display_name,
    normalized_bet_type,
    bet_type_display_name,
    bet_type_sort_key,
    render_bet_cards_chunked,
    JOSEPH_LOADING_AVAILABLE,
    joseph_loading_placeholder,
)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("📋 All Picks — Shared Pick Universe")
    st.markdown(
        "Every pick the app outputs across persisted analysis rows and tracked pipeline bets. "
        "This tab uses the same merged source as Health so totals align."
    )

    # ── Date / scope selector ─────────────────────────────────
    _col1, _col2 = st.columns([2, 5])
    with _col1:
        _dates = get_analysis_pick_dates(days=30)
        _today = tracker_today_iso()
        _today_has_picks = _today in _dates  # track before any prepend
        if not _today_has_picks:
            _dates = [_today] + _dates
        _options = _dates + ["Last 7 Days", "Last 30 Days", "All Time"]
        # Default to yesterday if today has no picks yet but yesterday does
        import datetime as _dt_mod2
        _yesterday = (_dt_mod2.date.today() - _dt_mod2.timedelta(days=1)).isoformat()
        _default_idx = _options.index(_yesterday) if not _today_has_picks and _yesterday in _options else 0
        _selected = st.selectbox("📅 Select Date / Scope", _options, index=_default_idx, key="all_picks_date_scope")
        _is_specific = _selected not in ("Last 7 Days", "Last 30 Days", "All Time")
        _scope = (
            "Today" if _is_specific and _selected == _today
            else _selected if not _is_specific
            else "Last 30 Days"
        )
        _filter_date = _selected if _is_specific else None
    with _col2:
        st.caption("Select a specific date to view its metrics, or choose a range for aggregate performance.")

    # ── Resolve All Picks button ──────────────────────────────
    _rc1, _rc2 = st.columns([1, 3])
    with _rc1:
        _resolve_btn = st.button("🔄 Resolve All Picks", key="resolve_all_picks_btn", type="primary")
    with _rc2:
        st.caption("Auto-resolves every pending pick using live NBA stats.")

    if _resolve_btn:
        _loader = joseph_loading_placeholder("Resolving all pending picks") if JOSEPH_LOADING_AVAILABLE else None
        try:
            _pr = resolve_all_analysis_picks(include_today=True)
            _br = resolve_all_pending_bets()
            if _loader:
                _loader.empty()
            _total = _pr.get("resolved", 0) + _br.get("resolved", 0)
            _wins = _pr.get("wins", 0) + _br.get("wins", 0)
            _losses = _pr.get("losses", 0) + _br.get("losses", 0)
            _evens = _pr.get("evens", 0) + _br.get("evens", 0)
            _pending = _pr.get("pending", 0) + _br.get("pending", 0)
            _errors = list(dict.fromkeys(_pr.get("errors", []) + _br.get("errors", [])))
            if _total > 0:
                st.success(
                    f"✅ Resolved **{_pr.get('resolved', 0)}** AI pick(s) + **{_br.get('resolved', 0)}** tracked bet(s): "
                    f"✅ {_wins} WIN · ❌ {_losses} LOSS · 🔄 {_evens} EVEN"
                    + (f" | ⏳ {_pending} still pending" if _pending > 0 else "")
                )
                reload_bets()
            elif _errors and not _pending:
                st.info("ℹ️ No picks were resolved. See errors below.")
            else:
                st.info("ℹ️ No pending picks found to resolve.")
            if _errors:
                with st.expander(f"⚠️ {len(_errors)} error(s)"):
                    for _e in _errors:
                        st.caption(_e)
        except Exception as _exc:
            if _loader:
                _loader.empty()
            st.error(f"❌ Resolution failed: {_exc}")

    st.divider()

    # ── Resolve / Re-check by Date ────────────────────────────
    st.markdown("### 🗓️ Resolve / Re-check Picks by Date")
    st.caption("Select a past night to view its picks and re-verify results.")
    _rbd_dates = get_analysis_pick_dates(days=30)
    _rbd_today = tracker_today_iso()
    if _rbd_today not in _rbd_dates:
        if load_analysis_picks_for_date(_rbd_today) or st.session_state.get("analysis_results"):
            _rbd_dates = [_rbd_today] + _rbd_dates
    if not _rbd_dates:
        from utils.components import render_empty_state
        render_empty_state(
            "📋", "No Pick History Yet",
            "Your daily pick history (last 30 days) will appear here after running Neural Analysis.",
            "💡 Load tonight's slate → Run Analysis → picks are saved automatically.",
        )
    else:
        _rbd_sel = st.selectbox("📅 Select date", _rbd_dates, index=0, key="rbd_date_selectbox")
        _rbd_picks = load_analysis_picks_for_date(_rbd_sel)

        # Fall back to bets table when all_analysis_picks has nothing for this date
        # (e.g. bets inserted directly via SQL / manual DB edits)
        from tracking.database import load_bets_page as _load_bets_page
        _rbd_bets = _load_bets_page(start_date=_rbd_sel, end_date=_rbd_sel, exclude_linked=False, limit=500)

        if not _rbd_picks and not _rbd_bets:
            st.info(f"No picks or bets logged for {_rbd_sel}.")
        else:
            # Show analysis picks if available
            if _rbd_picks:
                _rw = sum(1 for p in _rbd_picks if p.get("result") == "WIN")
                _rl = sum(1 for p in _rbd_picks if p.get("result") == "LOSS")
                _re = sum(1 for p in _rbd_picks if p.get("result") == "EVEN")
                _rp = sum(1 for p in _rbd_picks if not p.get("result"))
                _rr = _rw + _rl
                st.markdown(
                    f"**{len(_rbd_picks)} AI picks** for {_rbd_sel}"
                    + (f" · **{_rw / max(_rr, 1) * 100:.0f}% win rate**" if _rr > 0 else "")
                    + f"  \n✅ {_rw} WIN · ❌ {_rl} LOSS · 🔄 {_re} EVEN · ⏳ {_rp} Pending"
                )
                _rows = []
                for _p in _rbd_picks:
                    _actual = _p.get("actual_value")
                    _rows.append({
                        "Player": _p.get("player_name", "—"), "Stat": _p.get("stat_type", "—"),
                        "Line": _p.get("prop_line", "—"), "Dir": _p.get("direction", "—"),
                        "Actual": f"{_actual:.1f}" if _actual is not None else "—",
                        "Result": {"WIN": "✅ WIN", "LOSS": "❌ LOSS", "EVEN": "🔄 EVEN"}.get(
                            _p.get("result") or "", "⏳ Pending"),
                        "Tier": _p.get("tier", "—"),
                    })
                st.dataframe(_rows, use_container_width=True, hide_index=True)

            # Show tracked bets from bets table (may be the ONLY source for this date)
            if _rbd_bets:
                _bw = sum(1 for b in _rbd_bets if b.get("result") == "WIN")
                _bl = sum(1 for b in _rbd_bets if b.get("result") == "LOSS")
                _bp = sum(1 for b in _rbd_bets if not b.get("result"))
                st.markdown(
                    f"**{len(_rbd_bets)} tracked bet(s)** in Bet Tracker for {_rbd_sel}"
                    + f"  \n✅ {_bw} WIN · ❌ {_bl} LOSS · ⏳ {_bp} Pending"
                )
                _bet_rows = []
                for _b in _rbd_bets:
                    _actual = _b.get("actual_value")
                    _bet_rows.append({
                        "Player": _b.get("player_name", "—"),
                        "Stat": _b.get("stat_type", "—"),
                        "Line": _b.get("prop_line", "—"),
                        "Dir": _b.get("direction", "—"),
                        "Actual": f"{_actual:.1f}" if _actual is not None else "—",
                        "Result": {"WIN": "✅ WIN", "LOSS": "❌ LOSS", "EVEN": "🔄 EVEN"}.get(
                            _b.get("result") or "", "⏳ Pending"),
                        "Tier": _b.get("tier", "—"),
                        "Platform": _b.get("platform", "—"),
                    })
                st.dataframe(_bet_rows, use_container_width=True, hide_index=True)

            if st.button(f"🔄 Resolve / Re-check {_rbd_sel}", key="rbd_resolve_btn", type="primary"):
                _loader = joseph_loading_placeholder(f"Resolving picks for {_rbd_sel}") if JOSEPH_LOADING_AVAILABLE else None
                try:
                    _pr = resolve_all_analysis_picks(date_str=_rbd_sel)
                    _bc, _be = auto_resolve_bet_results(date_str=_rbd_sel)
                    if _loader:
                        _loader.empty()
                    _total = _pr.get("resolved", 0) + _bc
                    if _total > 0:
                        st.success(
                            f"✅ Resolved **{_pr.get('resolved', 0)}** AI pick(s) + **{_bc}** tracked bet(s) for {_rbd_sel}: "
                            f"✅ {_pr.get('wins', 0)} WIN · ❌ {_pr.get('losses', 0)} LOSS · 🔄 {_pr.get('evens', 0)} EVEN"
                        )
                        reload_bets()
                        st.rerun()
                    else:
                        st.warning(f"⚠️ No picks resolved for {_rbd_sel}.")
                    _errs = list(dict.fromkeys(_pr.get("errors", []) + _be))
                    if _errs:
                        with st.expander(f"⚠️ {len(_errs)} error(s)"):
                            for _e in _errs:
                                st.caption(_e)
                except Exception as _exc:
                    if _loader:
                        _loader.empty()
                    st.error(f"❌ Resolution failed: {_exc}")

    st.divider()

    # ── Merged pick universe ──────────────────────────────────
    _universe = build_merged_pick_universe(_scope)
    db_picks = list(_universe["analysis_rows"])
    _pipeline = list(_universe["pipeline_added"])
    _pipeline_bets = list(_universe["health_side_bets"])
    _skip_overlap = _universe["pipeline_skip_ai_overlap"]
    _combined = list(_universe["combined"])

    if _filter_date:
        _combined = [p for p in _combined if canonical_pick_date(p) == _filter_date]
        db_picks = [p for p in db_picks if canonical_pick_date(p) == _filter_date]
        _pipeline = [p for p in _pipeline if canonical_pick_date(p) == _filter_date]
        _pipeline_bets = [p for p in _pipeline_bets if canonical_pick_date(p) == _filter_date]

    # Filters
    _fc1, _fc2 = st.columns(2)
    with _fc1:
        _tier_filter = st.multiselect("Filter by Tier", ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"], default=[], key="ap_tier_filter")
    with _fc2:
        _bt_filter = st.multiselect("Bet Classification", ["Goblin", "Demon", "50/50", "Standard", "Normal", "Fantasy", "Joseph Pick"], default=[], key="ap_bet_type_filter")

    _bt_values = {
        "50_50" if bt == "50/50" else "joseph_pick" if bt == "Joseph Pick" else bt.lower()
        for bt in _bt_filter
    }

    all_picks_data = apply_global_filters(
        [p for p in _combined if platform_filter_fn(p, platform_selections)],
        player_search, date_range, direction_filter,
    )
    if _tier_filter:
        _tier_names = [t.split(" ")[0] for t in _tier_filter]
        all_picks_data = [p for p in all_picks_data if p.get("tier") in _tier_names]
    if _bt_filter:
        all_picks_data = [p for p in all_picks_data if normalized_bet_type(p) in _bt_values]

    # Session picks
    _today_str = tracker_today_iso()
    session_picks = []
    for _r in st.session_state.get("analysis_results", []) or []:
        session_picks.append({
            "player_name": _r.get("player_name", ""), "team": _r.get("player_team", _r.get("team", "")),
            "stat_type": _r.get("stat_type", ""), "prop_line": float(_r.get("line", 0) or 0),
            "direction": _r.get("direction", "OVER"), "platform": _r.get("platform", "SmartAI-Auto"),
            "confidence_score": float(_r.get("confidence_score", 0) or 0),
            "edge_percentage": float(_r.get("edge_percentage", 0) or 0),
            "tier": _r.get("tier", "Bronze"), "bet_type": _r.get("bet_type", "normal"),
            "pick_date": _today_str, "bet_date": _today_str, "result": None,
            "notes": "Live session pick (not yet persisted).",
        })
    if _filter_date:
        session_picks = [p for p in session_picks if canonical_pick_date(p) == _filter_date]
    else:
        session_picks = [p for p in session_picks if in_bet_date_window(p, _scope, "pick_date")]

    if not all_picks_data:
        st.info("📭 No picks to display. Run **Neural Analysis** to generate picks.")
        return

    # ── Summary stats ─────────────────────────────────────────
    _total = len(all_picks_data)
    _wins = sum(1 for p in all_picks_data if p.get("result") == "WIN")
    _losses = sum(1 for p in all_picks_data if p.get("result") == "LOSS")
    _evens = sum(1 for p in all_picks_data if p.get("result") == "EVEN")
    _pending = sum(1 for p in all_picks_data if not p.get("result"))
    _resolved = _wins + _losses
    _wr = round(_wins / max(_resolved, 1) * 100, 1) if _resolved > 0 else 0.0
    _avg_edge = sum(abs(float(p.get("edge_percentage", 0) or 0)) for p in all_picks_data) / _total if _total else 0.0
    _avg_conf = sum(float(p.get("confidence_score", 0) or 0) for p in all_picks_data) / _total if _total else 0.0

    with st.expander("🔎 Count Reconciliation", expanded=False):
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric("Health-side Bets", len(_pipeline_bets))
        _c2.metric("Analysis Rows", len(db_picks))
        _c3.metric("Pipeline Added", len(_pipeline))
        _c4.metric("Final All Picks", _total)

    # Streak
    _streak = 0
    _sorted_res = sorted(
        [p for p in all_picks_data if p.get("result") in ("WIN", "LOSS")],
        key=lambda p: p.get("pick_date", ""), reverse=True,
    )
    if _sorted_res:
        _first = _sorted_res[0].get("result")
        _streak = 1 if _first == "WIN" else -1
        for _sp in _sorted_res[1:]:
            if _sp.get("result") == _first:
                _streak += 1 if _first == "WIN" else -1
            else:
                break

    # Best platform
    _plat_perf: dict = {}
    for _p in all_picks_data:
        _plat = str(_p.get("platform") or "Unknown")
        _res = _p.get("result")
        if _plat not in _plat_perf:
            _plat_perf[_plat] = {"wins": 0, "total": 0}
        if _res in ("WIN", "LOSS"):
            _plat_perf[_plat]["total"] += 1
            if _res == "WIN":
                _plat_perf[_plat]["wins"] += 1
    _best_plat = ""
    _sp = sorted([(p, d["wins"] / max(d["total"], 1)) for p, d in _plat_perf.items() if d["total"] >= 3], key=lambda x: x[1], reverse=True)
    if _sp:
        _best_plat = _sp[0][0]

    st.markdown(
        get_summary_cards_html(
            total=_total, wins=_wins, losses=_losses, evens=_evens,
            pending=_pending, win_rate=_wr, streak=_streak,
            best_platform=_best_plat, total_label="Total Picks",
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        f"Scope source = {len(db_picks)} analysis rows + {len(_pipeline)} pipeline "
        f"(-{_skip_overlap} overlaps) = {len(_combined)} merged; {_total} shown."
    )

    if _resolved > 0:
        st.success(f"🎯 **Model accuracy:** **{_wins}/{_resolved}** correct (**{_wr:.1f}%**) — {_evens} even(s)")

    _mc = st.columns(5)
    _mc[0].metric("⬆️ OVER", sum(1 for p in all_picks_data if p.get("direction") == "OVER"))
    _mc[1].metric("⬇️ UNDER", sum(1 for p in all_picks_data if p.get("direction") == "UNDER"))
    _mc[2].metric("Avg Edge", f"{_avg_edge:.1f}%")
    _mc[3].metric("Avg Confidence", f"{_avg_conf:.0f}/100")
    with _mc[4]:
        if all_picks_data:
            st.download_button(
                "📥 Export CSV", data=export_bets_csv(all_picks_data),
                file_name=f"smartai_all_picks_{_today_str}.csv", mime="text/csv",
                key="export_all_picks_csv",
            )

    st.divider()

    # Win rate by tier
    with st.expander("🏆 Win Rate by Tier", expanded=True):
        _tr = []
        _icons = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        for _tn in ["Platinum", "Gold", "Silver", "Bronze"]:
            _tp = [p for p in all_picks_data if p.get("tier") == _tn]
            if not _tp:
                continue
            _tw = sum(1 for p in _tp if p.get("result") == "WIN")
            _tl = sum(1 for p in _tp if p.get("result") == "LOSS")
            _tres = _tw + _tl
            _tr.append({"Tier": _tn, "Total": _tres, "Wins": _tw, "Losses": _tl,
                        "Win Rate": f"{_tw / max(_tres, 1) * 100:.1f}%" if _tres > 0 else "—"})
        if _tr:
            st.markdown(get_styled_stats_table_html(_tr, ["Tier", "Total", "Wins", "Losses", "Win Rate"]), unsafe_allow_html=True)
            _cols = st.columns(4)
            for _i, _tn in enumerate(["Platinum", "Gold", "Silver", "Bronze"]):
                _row = next((r for r in _tr if r["Tier"] == _tn), None)
                if _row:
                    _cols[_i].metric(f"{_icons.get(_tn, '')} {_tn}", _row["Win Rate"],
                                     help=f"{_tn}: {_row['Wins']}W / {_row['Losses']}L ({_row['Total']} total)")
        else:
            st.caption("No tier data yet.")

    # Win rate by platform
    _pd: dict = {}
    for _p in all_picks_data:
        _plat = "Smart Pick Pro Platform Picks" if is_ai_auto_bet(_p) else platform_display_name(_p.get("platform") or "Unknown")
        _res = _p.get("result")
        if _plat not in _pd:
            _pd[_plat] = {"wins": 0, "losses": 0, "total": 0}
        if _res == "WIN":
            _pd[_plat]["wins"] += 1; _pd[_plat]["total"] += 1
        elif _res == "LOSS":
            _pd[_plat]["losses"] += 1; _pd[_plat]["total"] += 1
    with st.expander("🎰 Win Rate by Platform", expanded=True):
        if _pd:
            _pr = [{"Platform": p, "Total": d["total"], "Wins": d["wins"],
                     "Win Rate": f"{d['wins'] / max(d['wins'] + d['losses'], 1) * 100:.1f}%" if d["wins"] + d["losses"] > 0 else "—"}
                    for p, d in sorted(_pd.items())]
            st.markdown(get_styled_stats_table_html(_pr, ["Platform", "Total", "Wins", "Win Rate"]), unsafe_allow_html=True)
        else:
            st.caption("No platform data yet.")

    # Win rate by stat type
    with st.expander("📐 Win Rate by Stat Type", expanded=False):
        _sr = []
        for _st in sorted({p.get("stat_type", "unknown") for p in all_picks_data}):
            _sp2 = [p for p in all_picks_data if p.get("stat_type") == _st]
            _sw = sum(1 for p in _sp2 if p.get("result") == "WIN")
            _sl = sum(1 for p in _sp2 if p.get("result") == "LOSS")
            _sres = _sw + _sl
            _sr.append({"Stat Type": _st.replace("_", " ").title(), "Total": _sres, "Wins": _sw,
                         "Win Rate": f"{_sw / max(_sres, 1) * 100:.1f}%" if _sres > 0 else "—"})
        if _sr:
            st.markdown(get_styled_stats_table_html(_sr, ["Stat Type", "Total", "Wins", "Win Rate"]), unsafe_allow_html=True)
        else:
            st.caption("No stat type data yet.")

    # Win rate by bet classification
    _bd: dict = {}
    for _p in all_picks_data:
        _bt = normalized_bet_type(_p)
        _res = _p.get("result")
        if _bt not in _bd:
            _bd[_bt] = {"wins": 0, "losses": 0, "total": 0}
        if _res == "WIN":
            _bd[_bt]["wins"] += 1; _bd[_bt]["total"] += 1
        elif _res == "LOSS":
            _bd[_bt]["losses"] += 1; _bd[_bt]["total"] += 1
    if _bd:
        with st.expander("Win Rate by Bet Classification", expanded=True):
            _btr = [{"Bet Type": bet_type_display_name(bt), "Total": d["total"], "Wins": d["wins"],
                      "Losses": d["losses"],
                      "Win Rate": f"{d['wins'] / max(d['wins'] + d['losses'], 1) * 100:.1f}%" if d["wins"] + d["losses"] > 0 else "—"}
                     for bt, d in sorted(_bd.items(), key=lambda x: bet_type_sort_key(x[0]))]
            st.markdown(get_styled_stats_table_html(_btr, ["Bet Type", "Total", "Wins", "Losses", "Win Rate"]), unsafe_allow_html=True)

    with st.expander("📊 Model Tier Accuracy", expanded=False):
        st.info("Coming soon — this section will compare predicted tier accuracy vs actual results over time.")

    st.divider()

    # ── Source toggle ─────────────────────────────────────────
    _radio = st.radio(
        "Show detailed picks:",
        ["30-Day History (database)", "Today's Analysis (live session)"],
        horizontal=True, key="ap_source_radio",
    )

    if _radio == "30-Day History (database)":
        _detail = list(_combined)
        if _filter_date:
            _detail = [p for p in _detail if canonical_pick_date(p) == _filter_date]
        else:
            _detail = [p for p in _detail if in_bet_date_window(p, _scope, "pick_date")]
        if _tier_filter:
            _tier_names = [t.split(" ")[0] for t in _tier_filter]
            _detail = [p for p in _detail if p.get("tier") in _tier_names]
        if _bt_filter:
            _detail = [p for p in _detail if normalized_bet_type(p) in _bt_values]
        if _detail:
            _by_date: dict = {}
            for _p in _detail:
                _by_date.setdefault(_p.get("pick_date", "Unknown"), []).append(_p)
            _sorted_dates = sorted(_by_date.keys(), reverse=True)
            _MAX_CARD_DATES = 5
            for _idx, _d in enumerate(_sorted_dates):
                _dd = _by_date[_d]
                _dw = sum(1 for p in _dd if p.get("result") == "WIN")
                _dl = sum(1 for p in _dd if p.get("result") == "LOSS")
                _dr = _dw + _dl
                _dwr = f" — {_dw / max(_dr, 1) * 100:.0f}% win rate" if _dr > 0 else ""
                with st.expander(f"📅 {_d} · {len(_dd)} picks · ✅{_dw} ❌{_dl}{_dwr}",
                                  expanded=(_idx == 0)):
                    if _idx < _MAX_CARD_DATES:
                        _cards = []
                        for _pick in _dd:
                            _pc = dict(_pick)
                            if "bet_date" not in _pc:
                                _pc["bet_date"] = _pc.get("pick_date", "")
                            _cards.append(_pc)
                        render_bet_cards_chunked(_cards)
                    else:
                        # Older dates: lightweight dataframe instead of HTML cards
                        _rows = []
                        for _pick in _dd:
                            _actual = _pick.get("actual_value")
                            _rows.append({
                                "Player": _pick.get("player_name", "—"),
                                "Stat": str(_pick.get("stat_type", "—")).replace("_", " ").title(),
                                "Line": _pick.get("prop_line", _pick.get("line", "—")),
                                "Dir": _pick.get("direction", "—"),
                                "Actual": f"{_actual:.1f}" if _actual is not None else "—",
                                "Result": {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄"}.get(
                                    _pick.get("result") or "", "⏳"),
                                "Tier": _pick.get("tier", "—"),
                            })
                        st.dataframe(_rows, use_container_width=True, hide_index=True)
        else:
            st.info("📭 No database picks found for this time range.")
    else:
        _sd = list(session_picks)
        if _tier_filter:
            _tier_names = [t.split(" ")[0] for t in _tier_filter]
            _sd = [p for p in _sd if p.get("tier") in _tier_names]
        if _bt_filter:
            _sd = [p for p in _sd if normalized_bet_type(p) in _bt_values]
        if _sd:
            render_bet_cards_chunked(_sd)
        else:
            st.info("📭 No live session picks. Run **Neural Analysis** to generate picks.")
