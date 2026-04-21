# ============================================================
# FILE: pages/8_🛡️_Risk_Shield.py
# PURPOSE: Display all props that should be avoided and explain
#          WHY each one is a bad bet. Helps the user avoid traps.
# CONNECTS TO: analysis results in session state
# CONCEPTS COVERED: Filtering, explanations, data display
# ============================================================

import streamlit as st  # Main UI framework

# ============================================================
# SECTION: Helpers — mirrors Prop Scanner display helpers
# ============================================================

_STAT_AVG_KEY_MAP = {
    "points": "season_pts_avg",
    "rebounds": "season_reb_avg",
    "assists": "season_ast_avg",
    "threes": "season_threes_avg",
    "steals": "season_stl_avg",
    "blocks": "season_blk_avg",
    "turnovers": "season_tov_avg",
    "pts+reb": "season_pts_reb_avg",
    "pts+ast": "season_pts_ast_avg",
    "reb+ast": "season_reb_ast_avg",
    "pts+reb+ast": "season_pra_avg",
    "blk+stl": "season_blk_stl_avg",
}


def _season_avg(result):
    """Pull season average for this result's stat type."""
    stat = result.get("stat_type", "").lower().replace("_", " ").strip()
    # Exact match first, then try partial
    key = _STAT_AVG_KEY_MAP.get(stat)
    if not key:
        for alias, k in _STAT_AVG_KEY_MAP.items():
            if alias in stat:
                key = k
                break
    return float(result.get(key, 0) or 0) if key else 0.0


def _value_line_label(avg, diff_pct):
    if avg and diff_pct < -12:
        return "🔥 Low Line"
    elif avg and diff_pct > 15:
        return "⚠️ High Line"
    elif avg:
        return "✅ Fair"
    return "—"


def _context_line_label(avg, diff_pct):
    if avg and diff_pct > 10:
        return f"↑{diff_pct:.0f}% above avg"
    elif avg and diff_pct < -10:
        return f"↓{abs(diff_pct):.0f}% below avg"
    elif avg:
        return "≈ near avg"
    return "—"


def _line_type_label(result):
    return {
        "goblin": "🟢 Goblin",
        "demon": "🔴 Demon",
    }.get(result.get("odds_type", "standard"), "⚪ Standard")


def _clamp_display_prob(raw_prob):
    """Defensive display clamp — ensure P(Over) stays within [0.05, 0.95]."""
    try:
        p = float(raw_prob)
    except (TypeError, ValueError):
        p = 0.5
    return max(0.05, min(0.95, p))


# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Risk Shield — SmartBetPro NBA",
    page_icon="🛡️",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Risk Shield")
from utils.seo import inject_page_seo
inject_page_seo("Risk Shield")

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Hero Banner & Floating Widget ─────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_risk_shield"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

# ── Premium Gate ───────────────────────────────────────────────
from utils.premium_gate import premium_gate
if not premium_gate("Risk Shield"):
    st.stop()
# ── End Premium Gate ───────────────────────────────────────────

st.title("🛡️ Risk Shield")
st.markdown(
    "These props have been flagged as **high-risk or low-edge** by the model. "
    "Understand WHY to make better decisions."
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Risk Shield — Protecting Your Bankroll
    
    The Risk Shield automatically flags props that **failed the model's quality checks**. These are picks you should avoid.
    
    **How It Works**
    1. Run analysis on the **⚡ Quantum Analysis Matrix** page
    2. The Risk Shield automatically collects all flagged props
    3. Each flagged pick shows WHY it was flagged (low edge, trap line, high variance, etc.)
    
    **Understanding Red Flags**
    - 🚩 **Low Edge**: Model probability is near 50/50 — essentially a coin flip
    - 🚩 **Trap Line**: Vegas set this line to bait bettors to the wrong side
    - 🚩 **Sharp Line**: The line matches the player's exact average — no value
    - 🚩 **High Variance**: The player's game-to-game stats are too unpredictable
    - 🚩 **Low Confidence**: Contradictory signals — the model isn't sure
    
    💡 **Pro Tips:**
    - If a pick appears here, skip it — even if the potential payout looks attractive
    - Check the "What would make this playable?" section for each flagged pick
    - Use this alongside the Entry Builder to avoid putting risky picks in parlays
    """)

st.divider()

st.markdown(get_education_box_html(
    "📖 Why We Avoid These Picks",
    """
    The Risk Shield flags props that have one or more red flags:<br><br>
    🚩 <strong>Low edge</strong>: The model's probability is too close to 50/50 — no real edge.<br>
    🚩 <strong>Trap line</strong>: The line is set at an unusual position to attract bettors to the wrong side.<br>
    🚩 <strong>Sharp line</strong>: Vegas has priced this line at the player's exact average — no value.<br>
    🚩 <strong>High variance</strong>: The player's stats are too unpredictable to bet with confidence.<br>
    🚩 <strong>Low confidence</strong>: Too many contradictory signals — the model isn't sure.<br><br>
    <em>Rule of thumb: If a pick is on this list, it's not worth the risk regardless of how tempting it looks.</em>
    """
), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Load Analysis Results
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

if not analysis_results:
    st.warning(
        "⚠️ No analysis results yet. Go to **⚡ Neural Analysis** and run analysis first!"
    )
    st.stop()

# ============================================================
# END SECTION: Load Analysis Results
# ============================================================

# ============================================================
# SECTION: Build Avoid List
# Separate picks into avoided vs non-avoided
# ============================================================

# Get all props that should be avoided
avoided_props = [
    result for result in analysis_results
    if result.get("should_avoid", False)
]

# Get low-edge props (edge below 5% but not explicitly avoided)
low_edge_props = [
    result for result in analysis_results
    if not result.get("should_avoid", False)
    and abs(result.get("edge_percentage", 0)) < 5.0
]

# Get conflicting direction props (over_count ≈ under_count)
conflicting_props = []
for result in analysis_results:
    forces = result.get("forces", {})
    over_strength = forces.get("over_strength", 0)
    under_strength = forces.get("under_strength", 0)
    total = over_strength + under_strength
    if total > 0:
        # If both sides are within 25% of each other, it's conflicting
        if min(over_strength, under_strength) / max(over_strength, under_strength) > 0.75:
            if result not in avoided_props:
                conflicting_props.append(result)

# ============================================================
# END SECTION: Build Avoid List
# ============================================================

# ============================================================
# SECTION: Summary Metrics
# ============================================================

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "🚫 Explicitly Avoided",
    len(avoided_props),
    help="Props that triggered avoid criteria in the model",
)
col2.metric(
    "⚠️ Low Edge",
    len(low_edge_props),
    help="Props with less than 5% edge — near coin flip",
)
col3.metric(
    "🔀 Conflicting Forces",
    len(conflicting_props),
    help="Props where OVER and UNDER forces are nearly equal",
)
col4.metric(
    "✅ Recommended Picks",
    len(analysis_results) - len(avoided_props),
    help="Props that passed the avoid criteria",
)

# ============================================================
# END SECTION: Summary Metrics
# ============================================================

st.divider()

# ============================================================
# SECTION: Avoided Props Detail
# ============================================================

if avoided_props:
    st.subheader(f"🚫 Explicitly Avoided Picks ({len(avoided_props)})")
    st.markdown(
        "These props were flagged by the model for specific reasons. "
        "Understanding why helps you become a better bettor."
    )

    avoided_rows = []
    for result in avoided_props:
        player = result.get("player_name", "Unknown")
        stat = result.get("stat_type", "").replace("_", " ").title()
        line = result.get("line", 0)
        platform = result.get("platform", "")
        edge = result.get("edge_percentage", 0)
        confidence = result.get("confidence_score", 0)
        prob = result.get("probability_over", 0.5)
        avoid_reasons = result.get("avoid_reasons", [])

        prob = _clamp_display_prob(prob)
        prob_under = 1.0 - prob

        _risk_score = max(0, min(100, round(100 - abs(edge) * 2.5 - confidence * 0.3)))
        if _risk_score > 70:
            _risk_label = "🔴 HIGH"
        elif _risk_score > 40:
            _risk_label = "🟡 MED"
        else:
            _risk_label = "🟢 LOW"

        reasons_str = " · ".join(avoid_reasons) if avoid_reasons else "—"

        avg = _season_avg(result)
        diff_pct = result.get("line_vs_avg_pct", None)
        if diff_pct is None and avg > 0:
            diff_pct = round((float(line) - avg) / avg * 100, 1)
        else:
            diff_pct = float(diff_pct or 0)
        projection = result.get("adjusted_projection", 0)

        avoided_rows.append({
            "Player": player,
            "Stat": stat,
            "Line": float(line),
            "Line Type": _line_type_label(result),
            "Season Avg": round(avg, 1) if avg else None,
            "Line vs Avg": f"{diff_pct:+.1f}%" if avg else "—",
            "Value Line": _value_line_label(avg, diff_pct),
            "Context Line": _context_line_label(avg, diff_pct),
            "Projection": round(projection, 1) if projection else None,
            "Platform": platform,
            "P(Over)": f"{prob * 100:.1f}%",
            "P(Under)": f"{prob_under * 100:.1f}%",
            "Edge": f"{edge:+.1f}%",
            "Confidence": confidence,
            "Direction": result.get("direction", "—"),
            "Risk": _risk_label,
            "Reasons": reasons_str,
        })

    st.dataframe(
        avoided_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Line": st.column_config.NumberColumn(format="%.1f"),
            "Season Avg": st.column_config.NumberColumn(format="%.1f"),
            "Projection": st.column_config.NumberColumn(format="%.1f"),
            "Line vs Avg": st.column_config.TextColumn(),
            "Value Line": st.column_config.TextColumn(),
            "Context Line": st.column_config.TextColumn(),
            "Confidence": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d",
            ),
            "Reasons": st.column_config.TextColumn(width="large"),
        },
    )

else:
    st.success("✅ No props explicitly flagged for avoidance — all picks passed!")

# ============================================================
# END SECTION: Avoided Props Detail
# ============================================================

# ============================================================
# SECTION: Low Edge Warnings
# ============================================================

if low_edge_props:
    st.divider()
    st.subheader(f"⚠️ Low-Edge Caution Zone ({len(low_edge_props)})")
    st.markdown(
        "These picks have less than **5% edge**. They're essentially coin flips. "
        "We suggest avoiding them unless you have other reasons to bet them."
    )

    # Display as a compact table
    low_edge_rows = []
    for result in low_edge_props:
        avg = _season_avg(result)
        diff_pct = result.get("line_vs_avg_pct", None)
        line_val = float(result.get("line", 0))
        if diff_pct is None and avg > 0:
            diff_pct = round((line_val - avg) / avg * 100, 1)
        else:
            diff_pct = float(diff_pct or 0)
        projection = result.get("adjusted_projection", 0)

        low_edge_rows.append({
            "Player": result.get("player_name", ""),
            "Stat": result.get("stat_type", "").replace("_", " ").title(),
            "Line": line_val,
            "Line Type": _line_type_label(result),
            "Season Avg": round(avg, 1) if avg else None,
            "Line vs Avg": f"{diff_pct:+.1f}%" if avg else "—",
            "Value Line": _value_line_label(avg, diff_pct),
            "Context Line": _context_line_label(avg, diff_pct),
            "Projection": round(projection, 1) if projection else None,
            "Platform": result.get("platform", ""),
            "P(Over)": f"{_clamp_display_prob(result.get('probability_over', 0.5)) * 100:.1f}%",
            "P(Under)": f"{(1.0 - _clamp_display_prob(result.get('probability_over', 0.5))) * 100:.1f}%",
            "Edge": f"{result.get('edge_percentage', 0):+.1f}%",
            "Confidence": result.get("confidence_score", 0),
            "Direction": result.get("direction", "—"),
            "Tier": f"{result.get('tier_emoji','')}{result.get('tier','')}",
        })

    st.dataframe(
        low_edge_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Line": st.column_config.NumberColumn(format="%.1f"),
            "Season Avg": st.column_config.NumberColumn(format="%.1f"),
            "Projection": st.column_config.NumberColumn(format="%.1f"),
            "Line vs Avg": st.column_config.TextColumn(),
            "Value Line": st.column_config.TextColumn(),
            "Context Line": st.column_config.TextColumn(),
            "Confidence": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d",
            ),
        },
    )

# ============================================================
# END SECTION: Low Edge Warnings
# ============================================================

# ============================================================
# SECTION: Conflicting Forces Section
# ============================================================

if conflicting_props:
    st.divider()
    st.subheader(f"🔀 Conflicting Forces ({len(conflicting_props)})")
    st.markdown(
        "These picks have nearly equal OVER and UNDER forces — the model is uncertain. "
        "Proceed with caution."
    )

    conflict_rows = []
    for result in conflicting_props:
        player = result.get("player_name", "Unknown")
        stat = result.get("stat_type", "").replace("_", " ").title()
        line = float(result.get("line", 0))
        forces = result.get("forces", {})
        over_forces = forces.get("over_forces", [])
        under_forces = forces.get("under_forces", [])
        over_str = ", ".join(f"{f['name']} ({f['strength']:.1f})" for f in over_forces) if over_forces else "—"
        under_str = ", ".join(f"{f['name']} ({f['strength']:.1f})" for f in under_forces) if under_forces else "—"
        net_dir = forces.get("net_direction", "")
        net_s = forces.get("net_strength", 0)

        avg = _season_avg(result)
        diff_pct = result.get("line_vs_avg_pct", None)
        if diff_pct is None and avg > 0:
            diff_pct = round((line - avg) / avg * 100, 1)
        else:
            diff_pct = float(diff_pct or 0)
        projection = result.get("adjusted_projection", 0)

        conflict_rows.append({
            "Player": player,
            "Stat": stat,
            "Line": line,
            "Line Type": _line_type_label(result),
            "Season Avg": round(avg, 1) if avg else "—",
            "Line vs Avg": f"{diff_pct:+.1f}%" if avg else "—",
            "Value Line": _value_line_label(avg, diff_pct),
            "Projection": round(projection, 1) if projection else "—",
            "Platform": result.get("platform", ""),
            "P(Over)": f"{_clamp_display_prob(result.get('probability_over', 0.5)) * 100:.1f}%",
            "P(Under)": f"{(1.0 - _clamp_display_prob(result.get('probability_over', 0.5))) * 100:.1f}%",
            "Edge": f"{result.get('edge_percentage', 0):+.1f}%",
            "Confidence": result.get("confidence_score", 0),
            "⬆️ OVER Forces": over_str,
            "⬇️ UNDER Forces": under_str,
            "Net": f"{net_dir} {net_s:.1f}",
        })

    st.dataframe(
        conflict_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Line": st.column_config.NumberColumn(format="%.1f"),
            "Season Avg": st.column_config.NumberColumn(format="%.1f"),
            "Projection": st.column_config.NumberColumn(format="%.1f"),
            "Line vs Avg": st.column_config.TextColumn(),
            "Value Line": st.column_config.TextColumn(),
            "Confidence": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d",
            ),
            "⬆️ OVER Forces": st.column_config.TextColumn(width="large"),
            "⬇️ UNDER Forces": st.column_config.TextColumn(width="large"),
        },
    )

# ============================================================
# END SECTION: Conflicting Forces Section
# ============================================================

# ============================================================
# SECTION: Avoid List Education
# ============================================================

st.divider()
with st.expander("📚 Understanding Why Picks Get Avoided"):
    st.markdown("""
    ### Why Props End Up on the Avoid List

    The model avoids props when it detects one or more of these conditions:

    ---

    #### 1. 🪙 Insufficient Edge (< 5%)
    The model's probability is within 5% of 50% (the fair coin flip line).
    At this level, the house edge makes it unprofitable long-term.

    #### 2. 📉 High Variance / Unpredictable Stat
    Some stats (like steals, blocks, 3-pointers) are inherently random.
    A player who averages 2.1 steals might have 0 in a game or 6.
    When variability is > 55% of the average, projections are unreliable.

    #### 3. 🔀 Conflicting Forces
    When OVER forces and UNDER forces are nearly equal in strength,
    it means there's no clear directional edge. Both sides cancel out.

    #### 4. ⚠️ Blowout Risk
    When a game is likely to be a blowout (large spread), stars get
    rested in garbage time. This kills your over bets!

    ---

    **Remember:** The avoid list isn't saying these are 0% — it's saying
    the edge isn't large enough to justify the risk. Save your bankroll
    for the Platinum and Gold tier picks!
    """)

# ============================================================
# END SECTION: Avoid List Education
# ============================================================
