"""Platform Picks tab for Bet Tracker."""
import streamlit as st
from styles.theme import get_summary_cards_html, get_bet_card_html
from pages.helpers.bet_tracker_data import (
    cached_load_all_bets,
    is_ai_auto_bet,
    in_bet_date_window,
    platform_filter_fn,
    apply_global_filters,
    platform_display_name,
    render_bet_cards_chunked,
)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("📊 Platform Picks — Smart Pick Pro Platform Picks")
    st.markdown(
        "These bets were automatically logged by the Smart Pick Pro platform pipeline "
        "(formerly shown as SmartAI Auto)."
    )

    _col1, _col2 = st.columns([2, 5])
    st.session_state.setdefault("ai_picks_scope", "All Time")
    with _col1:
        _ai_scope = st.selectbox(
            "Platform Picks Scope",
            ["Today", "Last 7 Days", "Last 30 Days", "All Time"],
            key="ai_picks_scope",
            help="Date window for Smart Pick Pro auto-logged picks.",
        )
    with _col2:
        st.caption("Platform Picks uses strict Smart Pick Pro source tagging to avoid mixing Joseph/manual bets.")

    all_bets = cached_load_all_bets()
    ai_bets_raw = [b for b in all_bets if is_ai_auto_bet(b)]
    ai_bets_raw = [b for b in ai_bets_raw if in_bet_date_window(b, _ai_scope, "bet_date")]
    ai_bets = apply_global_filters(
        [b for b in ai_bets_raw if platform_filter_fn(b, platform_selections)],
        player_search, date_range, direction_filter,
    )

    _fc1, _fc2 = st.columns(2)
    with _fc1:
        _ai_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[], key="ai_tier_filter",
        )
    with _fc2:
        _ai_bt_filter = st.multiselect(
            "Bet Classification",
            ["Standard", "Goblin", "Normal", "Fantasy"],
            default=[], key="ai_bet_type_filter",
        )
    if _ai_tier_filter:
        _names = [t.split(" ")[0] for t in _ai_tier_filter]
        ai_bets = [b for b in ai_bets if b.get("tier") in _names]
    if _ai_bt_filter:
        _bt_set = {bt.lower() for bt in _ai_bt_filter}
        ai_bets = [b for b in ai_bets if (b.get("bet_type") or "standard").lower() in _bt_set]

    if not ai_bets:
        st.info("📭 No Smart Pick Pro platform picks yet. Run **⚡ Neural Analysis**.")
        return

    ai_resolved = [b for b in ai_bets if b.get("result") in ("WIN", "LOSS", "EVEN")]
    ai_wins = sum(1 for b in ai_resolved if b.get("result") == "WIN")
    ai_losses = sum(1 for b in ai_resolved if b.get("result") == "LOSS")
    ai_evens = sum(1 for b in ai_resolved if b.get("result") == "EVEN")
    ai_decided = ai_wins + ai_losses
    ai_rate = round(ai_wins / max(ai_decided, 1) * 100, 1)

    st.markdown(
        get_summary_cards_html(
            total=len(ai_bets), wins=ai_wins, losses=ai_losses, evens=ai_evens,
            pending=sum(1 for b in ai_bets if not b.get("result")),
            win_rate=ai_rate, total_label="Total Picks",
        ),
        unsafe_allow_html=True,
    )
    st.caption("Platform Picks counts only Smart Pick Pro platform auto-logged tracker bets. It is a subset of Health.")

    if ai_decided > 0:
        st.success(f"🎯 **Model accuracy:** **{ai_wins}/{ai_decided}** correct (**{ai_rate:.1f}%**) — {ai_evens} even(s)")

    st.divider()

    _by_date: dict = {}
    for b in ai_bets:
        _by_date.setdefault(b.get("bet_date", "Unknown"), []).append(b)

    _MAX_CARD_DATES = 5
    _sorted_dates = sorted(_by_date.keys(), reverse=True)
    for _idx, _date in enumerate(_sorted_dates):
        _day = _by_date[_date]
        _dw = sum(1 for b in _day if b.get("result") == "WIN")
        _dl = sum(1 for b in _day if b.get("result") == "LOSS")
        _de = sum(1 for b in _day if b.get("result") == "EVEN")
        _dd = _dw + _dl
        _dr = round(_dw / max(_dd, 1) * 100, 1) if _dd > 0 else None
        _label = (
            f"📅 {_date} — {len(_day)} picks"
            + (f" · {_dw}/{_dd} correct ({_dr:.0f}%)" if _dr is not None else " · pending")
            + (f" · {_de} even" if _de else "")
        )
        with st.expander(_label, expanded=(_idx == 0)):
            if _idx < _MAX_CARD_DATES:
                _display = []
                for b in _day:
                    _bd = dict(b)
                    _bd["platform"] = platform_display_name(_bd.get("platform"))
                    _display.append(_bd)
                render_bet_cards_chunked(_display)
            else:
                _rows = [{"Player": b.get("player_name", "—"),
                          "Stat": str(b.get("stat_type", "—")).replace("_", " ").title(),
                          "Line": b.get("prop_line", "—"), "Dir": b.get("direction", "—"),
                          "Result": {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄"}.get(b.get("result") or "", "⏳"),
                          "Tier": b.get("tier", "—")} for b in _day]
                st.dataframe(_rows, use_container_width=True, hide_index=True)
