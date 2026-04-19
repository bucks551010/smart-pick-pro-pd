"""Performance Predictor tab for Bet Tracker."""
import streamlit as st
from styles.theme import get_styled_stats_table_html


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("🔮 Performance Predictor")
    st.markdown("Forward-looking prediction based on tonight's analysis results.")

    analysis_results = st.session_state.get("analysis_results", [])
    if not analysis_results:
        st.info("💡 No analysis results found. Run **⚡ Neural Analysis** first.")
        return

    confidences = [r.get("confidence_score", 0) for r in analysis_results]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    _TIER_WR = {"Platinum": 72.0, "Gold": 62.0, "Silver": 54.0, "Bronze": 46.0}
    _tier_counts: dict = {}
    for r in analysis_results:
        t = r.get("tier", "Bronze")
        _tier_counts[t] = _tier_counts.get(t, 0) + 1

    total_picks = len(analysis_results)
    tier_wr = 0.0
    if total_picks > 0:
        for tn, bwr in _TIER_WR.items():
            tier_wr += (_tier_counts.get(tn, 0) / total_picks) * bwr

    conf_based = min(95.0, max(40.0, avg_conf * 0.9 + 5.0))
    est_wr = round(0.70 * tier_wr + 0.30 * conf_based, 1)
    est_wr = min(95.0, max(40.0, est_wr))

    _c1, _c2, _c3 = st.columns(3)
    _c1.metric("Props in Slate", len(analysis_results))
    _c2.metric("Avg Confidence", f"{avg_conf:.1f}")
    _c3.metric("Est. Win Rate", f"{est_wr:.1f}%")

    if _tier_counts:
        st.markdown("**Per-Tier Expected Win Rates**")
        _icons = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        _rows = [
            {"Tier": f"{_icons.get(t, '')} {t}", "Picks": _tier_counts[t],
             "Est. Win Rate": f"{_TIER_WR.get(t, 50):.0f}%"}
            for t in ["Platinum", "Gold", "Silver", "Bronze"] if t in _tier_counts
        ]
        st.markdown(get_styled_stats_table_html(_rows, ["Tier", "Picks", "Est. Win Rate"]), unsafe_allow_html=True)

    st.divider()
    st.subheader("💰 Recommended Bankroll Allocation")

    _TIER_PCT = {"Platinum": 0.30, "Gold": 0.25, "Silver": 0.20, "Bronze": 0.10}
    _TIER_EMOJI = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
    bankroll = st.number_input("Total Bankroll ($)", min_value=10.0, max_value=100000.0, value=100.0, step=10.0)

    _alloc = []
    for tn in ["Platinum", "Gold", "Silver", "Bronze"]:
        cnt = _tier_counts.get(tn, 0)
        if cnt > 0:
            pct = _TIER_PCT.get(tn, 0.10)
            amt = bankroll * pct
            _alloc.append({
                "Tier": f"{_TIER_EMOJI.get(tn, '')} {tn}", "Picks": cnt,
                "Allocation %": f"{pct * 100:.0f}%", "Amount ($)": f"${amt:.2f}",
                "Per Pick ($)": f"${amt / max(cnt, 1):.2f}",
            })
    if _alloc:
        st.markdown(get_styled_stats_table_html(_alloc, ["Tier", "Picks", "Allocation %", "Amount ($)", "Per Pick ($)"]), unsafe_allow_html=True)
    else:
        st.info("No tier data found.")

    st.divider()

    plat_picks = [r for r in analysis_results if r.get("tier") == "Platinum" and not r.get("should_avoid")]
    if plat_picks:
        st.subheader("🏆 Projected ROI — All Platinum Picks Hit")
        plat_alloc = bankroll * 0.30
        projected = plat_alloc * 2.0
        roi = ((projected - plat_alloc) / max(plat_alloc, 1)) * 100
        _r1, _r2, _r3 = st.columns(3)
        _r1.metric("Platinum Picks", len(plat_picks))
        _r2.metric("Allocated", f"${plat_alloc:.2f}")
        _r3.metric("Projected Profit", f"${projected - plat_alloc:.2f}", delta=f"{roi:.1f}% ROI")
        st.caption("⚠️ Projections are illustrative. Actual payouts vary by platform and entry type.")
    else:
        st.info("No Platinum picks found. Run **⚡ Neural Analysis** for results.")
