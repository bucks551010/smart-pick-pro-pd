# ============================================================
# FILE: pages/10_🗺️_Correlation_Matrix.py
# PURPOSE: Visualize pairwise Pearson correlations between
#          players' Quantum Matrix simulation arrays.  Renders an
#          interactive Plotly heatmap with the Quantum
#          Institutional aesthetic plus parlay-impact and
#          correlation-adjusted Kelly panels.
# CONNECTS TO: engine/correlation.py, engine/odds_engine.py,
#              session state analysis results
# ============================================================

import streamlit as st
import os
import html as _html

# ── App Logo (removed — only shown on key pages) ─────────────

from styles.theme import get_global_css

st.set_page_config(
    page_title="Correlation Matrix — Smart Pick Pro",
    page_icon="🗺️",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Hero Banner & Floating Widget ─────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating
st.session_state["joseph_page_context"] = "page_correlation"
inject_joseph_floating()

# ── Premium gate (graceful if module unavailable) ─────────────
try:
    from utils.premium_gate import premium_gate
    if not premium_gate("Correlation Matrix"):
        st.stop()
except ImportError:
    pass

# ── Import correlation engine ─────────────────────────────────
from engine.correlation import (
    pearson_sim_correlation,
    adjust_parlay_probability,
    correlation_adjusted_kelly,
)
from engine.math_helpers import clamp_probability


# ============================================================
# SECTION: Page Header
# ============================================================

st.title("🗺️ Correlation Matrix")
st.markdown(
    '<p style="color:#94a3b8;font-size:0.9rem;">'
    "Pairwise Pearson correlations between players' Quantum Matrix "
    "simulation distributions.  Positive correlation means their "
    "outcomes tend to move together; negative means they diverge."
    "</p>",
    unsafe_allow_html=True,
)

with st.expander("📖 How to Use the Correlation Matrix", expanded=False):
    st.markdown("""
### What This Page Does
The Correlation Matrix shows how the simulated stat outcomes of different
players **move together** (or apart).  This is critical for building
**parlays and DFS stacks** — combining correlated props amplifies upside,
while pairing uncorrelated props reduces overall variance.

### Understanding Correlation Values
| Value Range | Colour | Meaning |
|-------------|--------|---------|
| **+0.7 to +1.0** | 🟥 Strong red | Outcomes move tightly together (great for stacking) |
| **+0.3 to +0.7** | 🟧 Moderate | Moderate positive relationship |
| **−0.3 to +0.3** | ⬜ Neutral | Little-to-no relationship |
| **−0.7 to −0.3** | 🟦 Moderate blue | Outcomes tend to move in opposite directions |
| **−1.0 to −0.7** | 🟦 Strong blue | Strongly inversely related (good for hedging) |

### How to Read the Heatmap
- Each **cell** represents the Pearson correlation between two player-prop
  simulation distributions (from the Quantum Matrix Engine).
- **Diagonal cells** are always +1.0 (a prop is perfectly correlated with itself).
- Hover over a cell to see the exact correlation value.

### Practical Tips
- 💡 **Stacking teammates** (e.g. PG assists + SG points) often shows +0.4 to +0.7 —
  ideal for same-game parlays.
- 💡 **Opposite sides of the ball** (e.g. scorer vs. opposing defender) may show
  negative correlation — useful for hedging.
- 💡 Use the **🏀 Filter by Game** selector above to zoom into one matchup.
- 💡 The **Parlay Impact** panel below the heatmap shows how correlation adjusts
  your combo probability up or down compared to naïve multiplication.
- 💡 Run **⚡ Quantum Analysis Matrix** first — this page needs simulation arrays
  to compute correlations.
- 💡 Pearson correlation measures **linear** relationships. Non-linear dependencies
  (e.g. blowout effects) won't appear as high values, so always pair this with
  your game-script knowledge.
""")

# ============================================================
# SECTION: Pull analyzed results from session state
# ============================================================

_results = st.session_state.get("analysis_results", [])
if not _results:
    st.info(
        "Run **Neural Analysis** first to populate simulation data. "
        "Once analysis completes, return here to view the correlation matrix."
    )
    st.stop()

# Build lookup: label → simulated_results array  (+ full result dict)
_label_map = {}       # label → sim array
_result_map = {}      # label → full result dict
_game_groups = {}     # "TEAM vs OPP" → [labels]

for r in _results:
    sim = r.get("simulated_results", [])
    if not sim or len(sim) < 10:
        continue
    pname = r.get("player_name", "Unknown")
    stype = r.get("stat_type", "").title()
    label = f"{pname} — {stype}"
    _label_map[label] = sim
    _result_map[label] = r

    # Build game group
    team = (r.get("player_team") or r.get("team", "")).upper().strip()
    opp = (r.get("opponent", "") or "").upper().strip()
    if team and opp:
        game_key = " vs ".join(sorted([team, opp]))
    elif team:
        game_key = team
    else:
        game_key = "Unknown"
    _game_groups.setdefault(game_key, []).append(label)

if len(_label_map) < 2:
    st.warning(
        "At least **2 props with simulation data** are needed to "
        "build a correlation matrix.  Run a larger analysis batch."
    )
    st.stop()

# ============================================================
# SECTION: Game Filter + Prop Selector
# ============================================================

# Game-level filter
_game_keys = sorted(_game_groups.keys())
_game_filter = st.multiselect(
    "🏀 Filter by Game",
    options=_game_keys,
    default=_game_keys,
    help="Narrow the prop list to specific matchups.",
)

# Build filtered label list
_filtered_labels = []
for gk in (_game_filter or _game_keys):
    _filtered_labels.extend(_game_groups.get(gk, []))
_filtered_labels = sorted(set(_filtered_labels))

if len(_filtered_labels) < 2:
    st.info("Select games with at least 2 props to build a matrix.")
    st.stop()

_selected = st.multiselect(
    "Select props to correlate",
    options=_filtered_labels,
    default=_filtered_labels[:min(8, len(_filtered_labels))],
    help="Choose 2+ props.  Each prop's 1,000-run simulation array is compared pairwise.",
)

if len(_selected) < 2:
    st.info("Select at least 2 props above to generate the matrix.")
    st.stop()

# ============================================================
# SECTION: Compute Pairwise Correlation Matrix
# ============================================================

n = len(_selected)
corr_matrix = [[0.0] * n for _ in range(n)]

for i in range(n):
    for j in range(n):
        if i == j:
            corr_matrix[i][j] = 1.0
        elif j > i:
            r = pearson_sim_correlation(
                _label_map[_selected[i]],
                _label_map[_selected[j]],
            )
            corr_matrix[i][j] = r
            corr_matrix[j][i] = r

# ============================================================
# SECTION: Summary Statistics Bar
# ============================================================

_off_diag = []
for i in range(n):
    for j in range(i + 1, n):
        _off_diag.append(corr_matrix[i][j])

if _off_diag:
    _mean_r = sum(_off_diag) / len(_off_diag)
    _max_r_val = max(_off_diag)
    _min_r_val = min(_off_diag)
    _num_pairs = len(_off_diag)

    st.markdown(
        '<div class="corr-stats-bar">'
        # Mean
        '<div class="corr-stat-card" style="border:1px solid rgba(0,213,89,0.13);">'
        '<div class="corr-stat-label">Mean r</div>'
        f'<div class="corr-stat-value" style="color:#00D559;">{_mean_r:+.3f}</div></div>'
        # Max
        '<div class="corr-stat-card" style="border:1px solid rgba(0,213,89,0.18);">'
        '<div class="corr-stat-label">Max r</div>'
        f'<div class="corr-stat-value" style="color:#00D559;">{_max_r_val:+.3f}</div></div>'
        # Min
        '<div class="corr-stat-card" style="border:1px solid rgba(255,94,0,0.18);">'
        '<div class="corr-stat-label">Min r</div>'
        f'<div class="corr-stat-value" style="color:#F9C62B;">{_min_r_val:+.3f}</div></div>'
        # Pairs
        '<div class="corr-stat-card" style="border:1px solid rgba(148,163,184,0.12);">'
        '<div class="corr-stat-label">Pairs</div>'
        f'<div class="corr-stat-value" style="color:#EEF0F6;">{_num_pairs}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# SECTION: Plotly Heatmap Rendering
# ============================================================

try:
    import plotly.graph_objects as go

    # Stat abbreviations for shorter mobile-friendly labels
    _STAT_ABBR = {
        "Points": "PTS", "Rebounds": "REB", "Assists": "AST",
        "Threes": "3PM", "Three Pointers Made": "3PM",
        "Steals": "STL", "Blocks": "BLK", "Turnovers": "TO",
        "Pts+Reb+Ast": "PRA", "Pts+Reb": "P+R", "Pts+Ast": "P+A",
        "Reb+Ast": "R+A", "Fantasy Score": "FPTS",
        "Double Double": "DD", "Triple Double": "TD",
    }

    # Short labels (first name initial + last + abbreviated stat)
    short_labels = []
    for lbl in _selected:
        parts = lbl.split(" — ")
        name_parts = parts[0].split()
        short_name = (
            f"{name_parts[0][0]}. {name_parts[-1]}"
            if len(name_parts) > 1 else parts[0]
        )
        stat = parts[1] if len(parts) > 1 else ""
        stat = _STAT_ABBR.get(stat, stat)
        short_labels.append(f"{short_name} {stat}")

    # Scale annotation font size based on matrix size
    _annot_size = max(8, min(12, 14 - n))

    # Diverging color scale: red (negative) → slate (zero) → green (positive)
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=short_labels,
        y=short_labels,
        colorscale=[
            [0.0,  "#7f1d1d"],   # deep red     (r = -1.0)
            [0.25, "#991b1b"],   # medium red   (r = -0.5)
            [0.5,  "#1e293b"],   # dark slate   (r =  0.0)
            [0.75, "#059669"],   # emerald      (r = +0.5)
            [1.0,  "#00D559"],   # neon green   (r = +1.0)
        ],
        zmin=-1.0,
        zmax=1.0,
        text=[[f"{corr_matrix[i][j]:+.2f}" for j in range(n)] for i in range(n)],
        texttemplate="%{text}",
        textfont=dict(
            family="JetBrains Mono, monospace",
            size=_annot_size,
            color="#e2e8f0",
        ),
        hoverongaps=False,
        colorbar=dict(
            title=dict(text="Pearson r", font=dict(color="#94a3b8")),
            tickfont=dict(color="#64748b", family="JetBrains Mono, monospace"),
            thickness=12,
            len=0.8,
        ),
    ))

    # Dynamic tick font: shrink when many props
    _tick_size = max(8, min(10, 12 - n // 2))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#e2e8f0"),
        xaxis=dict(
            tickfont=dict(size=_tick_size, color="#94a3b8"),
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
            tickangle=-45,
        ),
        yaxis=dict(
            tickfont=dict(size=_tick_size, color="#94a3b8"),
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
            autorange="reversed",
        ),
        margin=dict(l=10, r=10, t=30, b=max(60, n * 8 + 20)),
        height=max(400, n * 55 + 120),
    )

    # Wrap in scrollable container for mobile
    st.markdown('<div class="corr-heatmap-wrap">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

except ImportError:
    st.error(
        "Plotly is required for the heatmap.  "
        "Install it with `pip install plotly`."
    )

# ============================================================
# SECTION: Dynamic Text Insights
# ============================================================

# Find highest and lowest off-diagonal correlations
_max_r, _min_r = -2.0, 2.0
_max_pair, _min_pair = ("", ""), ("", "")
for i in range(n):
    for j in range(i + 1, n):
        if corr_matrix[i][j] > _max_r:
            _max_r = corr_matrix[i][j]
            _max_pair = (_selected[i], _selected[j])
        if corr_matrix[i][j] < _min_r:
            _min_r = corr_matrix[i][j]
            _min_pair = (_selected[i], _selected[j])

if _max_r > 0.3:
    st.markdown(
        f'<div class="corr-insight" style="border:1px solid rgba(0,213,89,0.25);">'
        f'<span class="corr-insight-title" style="color:#00D559;">🔗 Positive Correlation Detected</span><br>'
        f'<span class="corr-insight-body">'
        f'<b>{_html.escape(_max_pair[0])}</b> and <b>{_html.escape(_max_pair[1])}</b> '
        f'show <span style="color:#00D559;font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
        f'r = {_max_r:+.2f}</span>.  Their simulation distributions move together — '
        f'combining them in a parlay amplifies variance.  Consider diversifying across games.</span></div>',
        unsafe_allow_html=True,
    )

if _min_r < -0.15:
    st.markdown(
        f'<div class="corr-insight" style="border:1px solid rgba(255,94,0,0.25);">'
        f'<span class="corr-insight-title" style="color:#F9C62B;">🔀 Negative Correlation Detected</span><br>'
        f'<span class="corr-insight-body">'
        f'<b>{_html.escape(_min_pair[0])}</b> and <b>{_html.escape(_min_pair[1])}</b> '
        f'show <span style="color:#F9C62B;font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
        f'r = {_min_r:+.2f}</span>.  These props tend to diverge — one going over '
        f'implies the other is more likely to go under.  Useful for hedging.</span></div>',
        unsafe_allow_html=True,
    )

if _max_r <= 0.3 and _min_r >= -0.15:
    st.markdown(
        '<div class="corr-insight" style="border:1px solid rgba(148,163,184,0.15);">'
        '<span class="corr-insight-title" style="color:#94a3b8;">📊 Low Correlation</span><br>'
        '<span class="corr-insight-body">'
        'No strong pairwise correlations detected.  These props appear '
        'largely independent — parlay math can treat their probabilities '
        'as multiplicative without a significant correlation penalty.</span></div>',
        unsafe_allow_html=True,
    )

# ============================================================
# SECTION: Parlay Impact Panel
# ============================================================

st.divider()
st.subheader("📐 Parlay Impact")
st.markdown(
    '<p style="color:#94a3b8;font-size:0.85rem;margin-top:-8px;">'
    "See how correlation affects the joint probability of parlaying "
    "these props together.  Positive correlation inflates the true "
    "joint probability; negative correlation reduces it.</p>",
    unsafe_allow_html=True,
)

# Gather directional probabilities for selected props
_parlay_probs = []
_parlay_labels = []
for lbl in _selected:
    res = _result_map.get(lbl, {})
    d = res.get("direction", "OVER")
    if d == "OVER":
        p = float(res.get("probability_over", 0.5))
    else:
        p = 1.0 - float(res.get("probability_over", 0.5))
    _parlay_probs.append(clamp_probability(p))
    _parlay_labels.append(lbl)

# Compute independent vs correlated joint probability
_naive_joint = 1.0
for p in _parlay_probs:
    _naive_joint *= p

_corr_joint = adjust_parlay_probability(_parlay_probs, corr_matrix)

_parlay_delta = _corr_joint - _naive_joint
_parlay_pct_change = ((_parlay_delta / _naive_joint) * 100) if _naive_joint > 0 else 0.0
_delta_color = "#00D559" if _parlay_delta >= 0 else "#F9C62B"

_pc1, _pc2, _pc3 = st.columns(3)
with _pc1:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(148,163,184,0.12);'
        'border-radius:8px;padding:12px 16px;text-align:center;">'
        '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
        'Independent Joint Prob</div>'
        f'<div style="color:#EEF0F6;font-size:1.3rem;font-weight:800;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
        f'">{_naive_joint * 100:.2f}%</div></div>',
        unsafe_allow_html=True,
    )
with _pc2:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(0,213,89,0.18);'
        'border-radius:8px;padding:12px 16px;text-align:center;">'
        '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
        'Correlation-Adjusted Prob</div>'
        f'<div style="color:#00D559;font-size:1.3rem;font-weight:800;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
        f'">{_corr_joint * 100:.2f}%</div></div>',
        unsafe_allow_html=True,
    )
with _pc3:
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#070A13,#0F172A);'
        f'border:1px solid {_delta_color}33;'
        f'border-radius:8px;padding:12px 16px;text-align:center;">'
        f'<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
        f'Correlation Shift</div>'
        f'<div style="color:{_delta_color};font-size:1.3rem;font-weight:800;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
        f'">{_parlay_pct_change:+.2f}%</div></div>',
        unsafe_allow_html=True,
    )

# ============================================================
# SECTION: Correlation-Adjusted Kelly
# ============================================================

st.divider()
st.subheader("🎯 Correlation-Adjusted Kelly")
st.markdown(
    '<p style="color:#94a3b8;font-size:0.85rem;margin-top:-8px;">'
    "Standard Kelly sizing assumes independent bets.  "
    "When picks are positively correlated, concentration risk increases — "
    "the Kelly fraction is discounted to protect your bankroll.</p>",
    unsafe_allow_html=True,
)

_bankroll = float(st.session_state.get("total_bankroll", 1000.0))

# Build picks list for correlation_adjusted_kelly
_kelly_picks = []
for lbl in _selected:
    res = _result_map.get(lbl, {})
    d = res.get("direction", "OVER")
    if d == "OVER":
        p = float(res.get("probability_over", 0.5))
        odds = float(res.get("over_odds", -110))
    else:
        p = 1.0 - float(res.get("probability_over", 0.5))
        odds = float(res.get("under_odds", -110))
    # Convert American odds to decimal
    if odds > 0:
        dec_odds = 1.0 + (odds / 100.0)
    elif odds < 0:
        dec_odds = 1.0 + (100.0 / abs(odds))
    else:
        dec_odds = 1.91  # fallback
    _kelly_picks.append({"win_probability": p, "odds_decimal": dec_odds})

_kelly_result = correlation_adjusted_kelly(_kelly_picks, _bankroll, corr_matrix)
_kelly_frac = _kelly_result.get("kelly_fraction", 0.0)
_kelly_bet = _kelly_result.get("recommended_bet", 0.0)
_kelly_discount = _kelly_result.get("correlation_discount", 1.0)

_kc1, _kc2, _kc3 = st.columns(3)
with _kc1:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(0,198,255,0.20);'
        'border-radius:8px;padding:12px 16px;text-align:center;">'
        '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
        'Adjusted Kelly %</div>'
        f'<div style="color:#00C6FF;font-size:1.3rem;font-weight:800;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
        f'">{_kelly_frac * 100:.2f}%</div></div>',
        unsafe_allow_html=True,
    )
with _kc2:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(0,198,255,0.25);'
        'border-radius:8px;padding:12px 16px;text-align:center;">'
        '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
        'Recommended Wager</div>'
        f'<div style="color:#00C6FF;font-size:1.3rem;font-weight:800;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
        f'">${_kelly_bet:,.2f}</div></div>',
        unsafe_allow_html=True,
    )
with _kc3:
    _disc_color = "#00D559" if _kelly_discount >= 0.9 else ("#F9C62B" if _kelly_discount >= 0.7 else "#F9C62B")
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#070A13,#0F172A);'
        f'border:1px solid {_disc_color}33;'
        f'border-radius:8px;padding:12px 16px;text-align:center;">'
        f'<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
        f'Correlation Discount</div>'
        f'<div style="color:{_disc_color};font-size:1.3rem;font-weight:800;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
        f'">{_kelly_discount:.2f}×</div></div>',
        unsafe_allow_html=True,
    )

st.caption(
    f"Based on ${_bankroll:,.0f} bankroll.  "
    f"Adjust bankroll in the ⚙️ Settings popover."
)
