"""Log a Bet tab for Bet Tracker."""
import streamlit as st
from tracking.bet_tracker import log_new_bet, log_props_to_tracker
from pages.helpers.bet_tracker_data import tracker_today_iso


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("➕ Log a New Bet")

    # ── Bulk-add platform props ───────────────────────────────
    _props = st.session_state.get("platform_props", [])
    if not _props:
        try:
            from data.data_manager import load_platform_props_from_csv
            _props = load_platform_props_from_csv()
        except Exception:
            _props = []

    if _props:
        with st.expander(f"📋 Add Platform Props to Bet Tracker ({len(_props)} props)", expanded=False):
            st.caption("Today's live platform props. Click **Add All** to log them as PENDING bets.")
            _by_plat: dict = {}
            for _p in _props:
                _pl = str(_p.get("platform", "Unknown"))
                _by_plat[_pl] = _by_plat.get(_pl, 0) + 1
            _cols = st.columns(max(len(_by_plat), 1))
            for _i, (_pn, _cnt) in enumerate(_by_plat.items()):
                _cols[_i % len(_cols)].metric(_pn, _cnt)

            import pandas as _pd
            _rows = [{"Player": p.get("player_name", ""), "Team": p.get("team", ""),
                       "Stat": p.get("stat_type", ""), "Line": p.get("line", ""),
                       "Platform": p.get("platform", ""), "Game Date": p.get("game_date", "")}
                      for p in _props]
            st.dataframe(_pd.DataFrame(_rows), use_container_width=True, hide_index=True,
                         height=min(250, 40 + len(_rows) * 35))

            _dir = st.radio("Default Direction", ["OVER", "UNDER"], horizontal=True, key="props_bulk_direction")
            if st.button(f"➕ Add All {len(_props)} Props to Bet Tracker", type="primary", key="btn_add_all_props"):
                with st.spinner("Adding props…"):
                    _saved, _skipped, _errs = log_props_to_tracker(_props, direction=_dir)
                if _saved:
                    st.success(f"✅ Added **{_saved}** prop(s) ({_skipped} duplicates skipped).")
                elif _skipped == len(_props):
                    st.info("ℹ️ All props already in the Bet Tracker.")
                else:
                    st.warning("⚠️ No new props were added.")
                if _errs:
                    with st.expander(f"⚠️ {len(_errs)} warning(s)"):
                        for _e in _errs[:20]:
                            st.caption(_e)
    else:
        st.info("💡 No platform props loaded yet. Load props from **📡 Live Games** first.")

    st.divider()

    analysis_results = st.session_state.get("analysis_results", [])
    player_options = ["— type manually —"]
    if analysis_results:
        player_options += sorted({r.get("player_name", "") for r in analysis_results if r.get("player_name")})

    with st.form("log_bet_form_bt", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            selected_player = st.selectbox("Player (from tonight's analysis)", player_options)
            manual_player = st.text_input("Or enter player name manually", placeholder="e.g., LeBron James")
            stat_type = st.selectbox("Stat Type", ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"])
            prop_line = st.number_input("Line", min_value=0.0, max_value=200.0, value=24.5, step=0.5)
            direction = st.radio("Direction", ["OVER", "UNDER"], horizontal=True)
        with c2:
            platform = st.selectbox("Platform", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"])
            tier = st.selectbox("Tier", ["Platinum", "Gold", "Silver", "Bronze"])
            entry_fee = st.number_input("Entry Fee ($)", min_value=0.0, max_value=10000.0, value=10.0, step=5.0)
            team = st.text_input("Team (optional)", placeholder="e.g., LAL")
            notes = st.text_input("Notes (optional)", placeholder="e.g., revenge game")

        confidence_score = 0.0
        probability_over = 0.5
        edge_percentage = 0.0
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
                    edge_percentage = r.get("edge_percentage", 0.0)
                    if not tier or tier == "Bronze":
                        tier = r.get("tier", "Bronze")
                    break

        st.caption(
            f"Auto-filled: confidence={confidence_score:.1f}, P(over)={probability_over:.2f}, edge={edge_percentage:+.1f}%"
            if confidence_score else "Enter player name to auto-fill from analysis."
        )
        submit = st.form_submit_button("📌 Log Bet", width="stretch", type="primary")

    if submit:
        if not final_player:
            st.error("Please enter or select a player name.")
        elif prop_line <= 0:
            st.error("Prop line must be greater than 0.")
        else:
            ok, msg = log_new_bet(
                player_name=final_player, stat_type=stat_type, prop_line=prop_line,
                direction=direction, platform=platform, confidence_score=confidence_score,
                probability_over=probability_over, edge_percentage=edge_percentage,
                tier=tier, entry_fee=entry_fee, team=team.strip().upper() if team else "",
                notes=notes.strip(),
            )
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
