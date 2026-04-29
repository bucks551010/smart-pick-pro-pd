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
)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("📊 Platform Picks — Smart Pick Pro Platform Picks")
    st.markdown(
        "These bets were automatically logged by the Smart Pick Pro platform pipeline "
        "(formerly shown as SmartAI Auto)."
    )

    # ── Scope — reads from global selector in filter bar ──────────────────────
    _ai_scope = st.session_state.get("bt_scope_label", "Last 30 Days")
    st.caption(f"📅 Showing: **{st.session_state.get('bt_global_scope', 'Last 30 Days')}** — change the Date / Scope selector above to update all tabs.")

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
        from utils.components import render_empty_state
        render_empty_state(
            "🤖", "No Platform Picks Yet",
            "AI-generated platform picks will appear here after you run Neural Analysis.",
            "💡 Go to ⚡ Quantum Analysis Matrix → Run Analysis to generate picks.",
        )
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
            pending=sum(1 for b in ai_bets if b.get("result") not in ("WIN", "LOSS", "EVEN")),
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

    st.markdown("#### 📋 Platform Picks by Date")
    _sorted_dates = sorted(_by_date.keys(), reverse=True)
    for _idx, _date in enumerate(_sorted_dates):
        _day = _by_date[_date]
        _dw = sum(1 for b in _day if b.get("result") == "WIN")
        _dl = sum(1 for b in _day if b.get("result") == "LOSS")
        _de = sum(1 for b in _day if b.get("result") == "EVEN")
        _dv = sum(1 for b in _day if b.get("result") == "VOID")
        _dp = sum(1 for b in _day if b.get("result") not in ("WIN", "LOSS", "EVEN", "VOID"))
        _dr_total = _dw + _dl
        _dr_pct = round(_dw / max(_dr_total, 1) * 100, 1) if _dr_total > 0 else None
        _label = (
            f"📅 {_date} — {len(_day)} picks"
            + (f" · {_dw}/{_dr_total} correct ({_dr_pct:.0f}%)" if _dr_pct is not None else "")
            + (f" · 🔄{_de}" if _de else "")
            + (f" · 🚫{_dv}" if _dv else "")
            + (f" · ⏳{_dp} pending" if _dp else "")
        )
        with st.expander(_label, expanded=(_idx == 0)):
            _rows = []
            for b in _day:
                _actual = b.get("actual_value")
                _res_raw = b.get("result") or ""
                _rows.append({
                    "Player": b.get("player_name", "—"),
                    "Team": b.get("team", "—"),
                    "Stat": str(b.get("stat_type", "—")).replace("_", " ").title(),
                    "Line": b.get("prop_line", "—"),
                    "Dir": b.get("direction", "—"),
                    "Conf": f"{float(b.get('confidence_score') or 0):.0f}",
                    "Tier": b.get("tier", "—"),
                    "Platform": platform_display_name(b.get("platform") or "—"),
                    "Actual": f"{_actual:.1f}" if _actual is not None else "—",
                    "Result": {"WIN": "✅ WIN", "LOSS": "❌ LOSS", "EVEN": "🔄 EVEN", "VOID": "🚫 VOID"}.get(_res_raw, "⏳ Pending"),
                })
            st.dataframe(_rows, use_container_width=True, hide_index=True)
