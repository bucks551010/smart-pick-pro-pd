# pages/12_📊_Proving_Grounds.py
# Historical backtesting UI for Smart Pick Pro ("Proving Grounds").
# Runs the prediction model against historical game log data to validate accuracy.

import streamlit as st

st.set_page_config(
    page_title="Proving Grounds — Smart Pick Pro",
    page_icon="📊",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Proving Grounds")
from utils.seo import inject_page_seo
inject_page_seo("Proving Grounds")

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

from styles.theme import get_global_css
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_proving_grounds"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

from utils.premium_gate import premium_gate
if not premium_gate("Proving Grounds"):
    st.stop()

import html as _html
import json as _json
import csv as _csv
import io as _io
from datetime import datetime as _datetime

# ── Proving Grounds CSS ───────────────────────────────────────
st.markdown("""
<style>
/* ─── Animations ─────────────────────────────────────────── */
@keyframes pg-glow-pulse {
    0%, 100% { box-shadow: 0 0 15px rgba(0,213,89,0.09), 0 4px 24px rgba(0,213,89,0.06); }
    50%      { box-shadow: 0 0 30px rgba(0,213,89,0.22), 0 4px 30px rgba(0,213,89,0.10); }
}
@keyframes pg-fade-up {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes pg-shimmer {
    0%   { background-position: -300px 0; }
    100% { background-position: 300px 0; }
}
@keyframes pg-border-flow {
    0%   { border-color: rgba(0,213,89,0.18); }
    50%  { border-color: rgba(0,213,89,0.40); }
    100% { border-color: rgba(0,213,89,0.18); }
}

/* ─── Page Title ─────────────────────────────────────────── */
.pg-page-title {
    font-family: 'Inter', 'Inter', sans-serif;
    font-size: 1.85rem;
    font-weight: 900;
    letter-spacing: 2px;
    color: #00D559;
    text-shadow: 0 0 20px rgba(0,213,89,0.45), 0 0 40px rgba(0,213,89,0.18);
    margin-bottom: 2px;
    line-height: 1.3;
}
.pg-page-subtitle {
    font-size: 0.88rem;
    color: #6B7A9A;
    letter-spacing: 0.3px;
    line-height: 1.5;
}
.pg-title-bar {
    background: linear-gradient(135deg, rgba(0,213,89,0.07) 0%, rgba(45,158,255,0.04) 100%);
    border: 1px solid rgba(0,213,89,0.15);
    border-radius: 14px;
    padding: 20px 28px 16px 28px;
    margin-bottom: 20px;
    animation: pg-fade-up 0.5s ease-out;
}
.pg-title-accent {
    height: 3px;
    width: 60px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    border-radius: 2px;
    margin-top: 10px;
}

/* ─── Glass Metric Cards ─────────────────────────────────── */
.pg-glass-card {
    background: linear-gradient(145deg, rgba(13,18,40,0.92) 0%, rgba(7,10,19,0.96) 100%);
    border: 1px solid rgba(0,213,89,0.16);
    border-radius: 14px;
    padding: 16px 14px 14px 14px;
    text-align: center;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.40), 0 0 12px rgba(0,213,89,0.04);
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    min-height: 105px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    animation: pg-fade-up 0.4s ease-out both;
    position: relative;
    overflow: hidden;
}
.pg-glass-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.35), transparent);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.pg-glass-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.50), 0 0 24px rgba(0,213,89,0.10);
    border-color: rgba(0,213,89,0.30);
}
.pg-glass-card:hover::before { opacity: 1; }
.pg-glass-label {
    font-size: 0.68rem;
    color: rgba(255,255,255,0.48);
    text-transform: uppercase;
    letter-spacing: 1.8px;
    margin-bottom: 6px;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
}
.pg-glass-value {
    font-size: 1.55rem;
    font-weight: 800;
    color: #00D559;
    line-height: 1.15;
    font-family: 'JetBrains Mono', 'Inter', monospace;
    text-shadow: 0 0 10px rgba(0,213,89,0.22);
}
.pg-glass-delta {
    font-size: 0.70rem;
    margin-top: 5px;
    color: rgba(255,255,255,0.38);
    font-weight: 500;
}
.pg-glass-delta.positive { color: #00e676; text-shadow: 0 0 6px rgba(0,230,118,0.3); }
.pg-glass-delta.negative { color: #ff5252; text-shadow: 0 0 6px rgba(255,82,82,0.3); }

/* Card value color variants */
.pg-glass-value.green { color: #00e676; text-shadow: 0 0 10px rgba(0,230,118,0.25); }
.pg-glass-value.red { color: #ff5252; text-shadow: 0 0 10px rgba(255,82,82,0.25); }
.pg-glass-value.gold { color: #ffd740; text-shadow: 0 0 10px rgba(255,215,64,0.25); }
.pg-glass-value.white { color: #e8f0ff; text-shadow: none; }

/* ─── Hero Results Banner ────────────────────────────────── */
.pg-hero-banner {
    background: linear-gradient(135deg, rgba(13,18,40,0.95) 0%, rgba(7,10,19,0.98) 100%);
    border: 1px solid rgba(0,213,89,0.20);
    border-radius: 16px;
    padding: 24px 30px;
    margin-bottom: 22px;
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    box-shadow: 0 0 30px rgba(0,213,89,0.07), 0 8px 32px rgba(0,0,0,0.50);
    animation: pg-glow-pulse 4s ease-in-out infinite, pg-fade-up 0.5s ease-out;
    position: relative;
    overflow: hidden;
}
.pg-hero-banner::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent 0%, #00D559 30%, #2D9EFF 70%, transparent 100%);
    background-size: 300px 3px;
    animation: pg-shimmer 3s linear infinite;
}
.pg-hero-title {
    font-family: 'Inter', 'Inter', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    color: #00D559;
    text-shadow: 0 0 14px rgba(0,213,89,0.45);
    margin-bottom: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
}
.pg-hero-subtitle {
    font-size: 0.88rem;
    color: rgba(255,255,255,0.65);
    line-height: 1.8;
}
.pg-hero-stat {
    display: inline-block;
    margin-right: 18px;
    margin-bottom: 4px;
    font-weight: 600;
    color: rgba(255,255,255,0.85);
    font-size: 0.88rem;
}
.pg-hero-stat .hl {
    color: #00D559;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    text-shadow: 0 0 8px rgba(0,213,89,0.4);
}
.pg-hero-stat .gold {
    color: #ffd740;
    font-weight: 800;
    text-shadow: 0 0 8px rgba(255,215,64,0.4);
}
.pg-hero-stat .green {
    color: #00e676;
    font-weight: 800;
    text-shadow: 0 0 8px rgba(0,230,118,0.4);
}
.pg-hero-stat .red {
    color: #ff5252;
    font-weight: 800;
    text-shadow: 0 0 8px rgba(255,82,82,0.4);
}
.pg-hero-divider {
    color: rgba(0,213,89,0.22);
    margin: 0 4px;
    font-weight: 300;
}

/* ─── Tier Cards ─────────────────────────────────────────── */
.pg-tier-card {
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    animation: pg-fade-up 0.35s ease-out both;
}
.pg-tier-card:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.pg-tier-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 72px;
    padding: 5px 12px;
    border-radius: 6px;
    font-family: 'Inter', sans-serif;
    font-size: 0.70rem;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    flex-shrink: 0;
}
.pg-tier-meta {
    flex: 1;
    font-size: 0.86rem;
    color: rgba(255,255,255,0.70);
}
.pg-tier-meta strong { color: #e8f0ff; }
.pg-tier-wr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.15rem;
    font-weight: 800;
    min-width: 65px;
    text-align: right;
    flex-shrink: 0;
}
.pg-tier-bar-wrap {
    width: 100px;
    height: 6px;
    background: rgba(255,255,255,0.06);
    border-radius: 3px;
    overflow: hidden;
    flex-shrink: 0;
}
.pg-tier-bar {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s ease-out;
}

.pg-tier-elite {
    background: linear-gradient(135deg, rgba(255,215,64,0.10) 0%, rgba(13,18,40,0.90) 100%);
    border-left: 4px solid #ffd740;
    box-shadow: 0 0 12px rgba(255,215,64,0.08);
}
.pg-tier-elite .pg-tier-badge {
    background: linear-gradient(135deg, rgba(255,215,64,0.25), rgba(255,215,64,0.10));
    color: #ffd740;
    border: 1px solid rgba(255,215,64,0.35);
}
.pg-tier-strong {
    background: linear-gradient(135deg, rgba(0,213,89,0.06) 0%, rgba(13,18,40,0.90) 100%);
    border-left: 4px solid #00D559;
    box-shadow: 0 0 12px rgba(0,213,89,0.04);
}
.pg-tier-strong .pg-tier-badge {
    background: linear-gradient(135deg, rgba(0,213,89,0.18), rgba(0,213,89,0.07));
    color: #00D559;
    border: 1px solid rgba(0,213,89,0.26);
}
.pg-tier-value {
    background: linear-gradient(135deg, rgba(200,200,255,0.04) 0%, rgba(13,18,40,0.90) 100%);
    border-left: 4px solid rgba(200,200,255,0.30);
}
.pg-tier-value .pg-tier-badge {
    background: rgba(200,200,255,0.08);
    color: rgba(200,200,255,0.70);
    border: 1px solid rgba(200,200,255,0.18);
}
.pg-tier-lean {
    background: linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(13,18,40,0.90) 100%);
    border-left: 4px solid rgba(255,255,255,0.12);
}
.pg-tier-lean .pg-tier-badge {
    background: rgba(255,255,255,0.04);
    color: rgba(255,255,255,0.40);
    border: 1px solid rgba(255,255,255,0.10);
}

/* ─── Section Headers ────────────────────────────────────── */
.pg-section-hdr {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
    animation: pg-fade-up 0.4s ease-out both;
}
.pg-section-icon {
    font-size: 1.3rem;
    line-height: 1;
}
.pg-section-text {
    font-family: 'Inter', 'Inter', sans-serif;
    font-size: 0.95rem;
    font-weight: 700;
    color: #00D559;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    text-shadow: 0 0 8px rgba(0,213,89,0.3);
}
.pg-section-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(0,213,89,0.22), transparent);
}

/* ─── Status Pills ───────────────────────────────────────── */
.pg-status-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin: 8px 0 12px 0;
    padding: 10px 16px;
    background: linear-gradient(135deg, rgba(13,18,40,0.80) 0%, rgba(7,10,19,0.90) 100%);
    border: 1px solid rgba(0,213,89,0.09);
    border-radius: 10px;
    animation: pg-fade-up 0.4s ease-out both;
}
.pg-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.pg-pill.ok { background: rgba(0,230,118,0.12); color: #00e676; border: 1px solid rgba(0,230,118,0.22); }
.pg-pill.warn { background: rgba(255,94,0,0.12); color: #F9C62B; border: 1px solid rgba(255,94,0,0.22); }
.pg-pill.info { background: rgba(0,213,89,0.09); color: #00D559; border: 1px solid rgba(0,213,89,0.18); }
.pg-pill.stale { background: rgba(255,200,0,0.10); color: #F9C62B; border: 1px solid rgba(255,200,0,0.20); }

/* ─── Empty State ────────────────────────────────────────── */
.pg-empty-state {
    text-align: center;
    padding: 48px 32px;
    background: linear-gradient(135deg, rgba(13,18,40,0.60) 0%, rgba(7,10,19,0.75) 100%);
    border: 1px dashed rgba(0,213,89,0.15);
    border-radius: 16px;
    margin: 20px 0;
    animation: pg-fade-up 0.5s ease-out;
}
.pg-empty-icon {
    font-size: 3rem;
    margin-bottom: 12px;
    opacity: 0.7;
}
.pg-empty-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: rgba(0,213,89,0.65);
    letter-spacing: 1.5px;
    margin-bottom: 8px;
}
.pg-empty-desc {
    font-size: 0.86rem;
    color: #6B7A9A;
    max-width: 500px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ─── Comparison Winner Highlight ────────────────────────── */
.pg-winner-card {
    background: linear-gradient(135deg, rgba(0,230,118,0.08) 0%, rgba(13,18,40,0.92) 100%);
    border: 1px solid rgba(0,230,118,0.25);
    border-radius: 12px;
    padding: 14px 18px;
    text-align: center;
    box-shadow: 0 0 16px rgba(0,230,118,0.08);
    animation: pg-fade-up 0.4s ease-out both;
}
.pg-winner-label {
    font-size: 0.68rem;
    color: rgba(255,255,255,0.45);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
    margin-bottom: 4px;
}
.pg-winner-vals {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.92rem;
    color: #e8f0ff;
    margin-bottom: 4px;
}
.pg-winner-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 1px;
}
.pg-winner-a {
    background: rgba(0,213,89,0.13);
    color: #00D559;
    border: 1px solid rgba(0,213,89,0.26);
}
.pg-winner-b {
    background: rgba(45,158,255,0.15);
    color: #2D9EFF;
    border: 1px solid rgba(45,158,255,0.30);
}
.pg-winner-tie {
    background: rgba(255,255,255,0.08);
    color: rgba(255,255,255,0.55);
    border: 1px solid rgba(255,255,255,0.15);
}
</style>
""", unsafe_allow_html=True)


def _glass_card(label, value, delta="", delta_class="", value_class=""):
    """Return HTML for a glassmorphism metric card."""
    safe_label = _html.escape(str(label))
    safe_value = _html.escape(str(value))
    safe_delta = _html.escape(str(delta))
    _vc = f" {_html.escape(value_class)}" if value_class else ""
    delta_html = (
        f'<div class="pg-glass-delta {_html.escape(delta_class)}">{safe_delta}</div>'
        if delta else ""
    )
    return f"""<div class="pg-glass-card">
        <div class="pg-glass-label">{safe_label}</div>
        <div class="pg-glass-value{_vc}">{safe_value}</div>
        {delta_html}
    </div>"""


def _section_header(icon, text):
    """Return HTML for a styled section header with accent line."""
    safe_text = _html.escape(str(text))
    return f"""<div class="pg-section-hdr">
        <span class="pg-section-icon">{icon}</span>
        <span class="pg-section-text">{safe_text}</span>
        <div class="pg-section-line"></div>
    </div>"""


st.markdown("""
<div class="pg-title-bar">
    <div class="pg-page-title">📊 PROVING GROUNDS</div>
    <div class="pg-page-subtitle">
        Validate the model against real game logs — win rates, ROI, tier-by-tier performance, and per-player breakdowns.
    </div>
    <div class="pg-title-accent"></div>
</div>
""", unsafe_allow_html=True)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Proving Grounds — Validate Before You Bet
    
    The Proving Grounds runs the prediction model against **real historical game logs** to measure accuracy.
    
    **How to Run a Backtest**
    1. Select players (or use all cached players)
    2. Choose the stat types to backtest (points, rebounds, assists, etc.)
    3. Set the date range and minimum edge threshold
    4. Click "Run Backtest" and watch the real-time progress
    
    **Understanding Results**
    - **Win Rate**: Percentage of picks that would have been correct
    - **ROI**: Return on investment assuming flat unit bets at -110 odds
    - **Tier Breakdown**: How each confidence tier (ELITE/STRONG/VALUE/LEAN) performed
    - **By Stat Type**: Which stat categories the model predicts best
    - **Per-Player**: Top/bottom performers with best/worst stat breakdown
    
    **What Good Results Look Like**
    - Overall win rate above 55% is strong
    - ELITE tier should have the highest win rate
    - If LEAN tier beats ELITE, the confidence model needs recalibration
    - Sharpe ratio > 1.0 indicates consistent profitability
    
    💡 **Pro Tips:**
    - Run "Refresh Game Logs" on the Smart NBA Data page first to load historical data
    - Use **A/B Comparison Mode** to test different edge thresholds side-by-side
    - Use date range filtering to analyze specific stretches (post All-Star, playoffs, etc.)
    - Export results to CSV for deeper Excel analysis
    """)

st.divider()

# ── Imports ──────────────────────────────────────────────────
try:
    from engine.backtester import run_backtest
    _BACKTESTER_AVAILABLE = True
except ImportError:
    _BACKTESTER_AVAILABLE = False

try:
    from data.game_log_cache import (
        get_all_cached_players,
        load_game_logs_from_cache,
        save_game_logs_to_cache,
    )
    _CACHE_AVAILABLE = True
except ImportError:
    _CACHE_AVAILABLE = False

try:
    from data.nba_data_service import refresh_historical_data_for_tonight as _refresh_hist
    _HIST_REFRESH_AVAILABLE = True
except ImportError:
    _HIST_REFRESH_AVAILABLE = False

try:
    from engine.clv_tracker import get_clv_summary, validate_model_edge
    _CLV_AVAILABLE = True
except ImportError:
    _CLV_AVAILABLE = False

try:
    from tracking.database import save_backtest_result, load_backtest_results
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

# ── Load cached game logs (needed for sidebar player list) ────
game_logs_by_player = {}
stale_count = 0
if _CACHE_AVAILABLE:
    cached_players = get_all_cached_players()
    if cached_players:
        for pname in cached_players:
            logs, is_stale = load_game_logs_from_cache(pname)
            if logs:
                game_logs_by_player[pname] = logs
                if is_stale:
                    stale_count += 1

# Also check session state (set by Player Simulator page)
session_logs = st.session_state.get("game_logs_by_player", {})
for pname, logs in session_logs.items():
    if logs and pname not in game_logs_by_player:
        game_logs_by_player[pname] = logs

# ── Sidebar Controls ─────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Proving Grounds Settings")

    season = st.selectbox("Season", ["2025-26", "2024-25", "2023-24", "2022-23"], index=0)

    stat_options = [
        "points", "rebounds", "assists", "steals", "blocks", "threes", "turnovers",
        "ftm", "fta", "fgm", "fga", "minutes", "personal_fouls",
        "offensive_rebounds", "defensive_rebounds",
    ]
    selected_stats = st.multiselect(
        "Stat Types",
        stat_options,
        default=["points", "rebounds", "assists"],
    )

    min_edge = st.slider("Min Edge (%)", min_value=1, max_value=20, value=5, step=1) / 100.0

    tier_filter = st.selectbox(
        "Tier Filter (optional)",
        ["All Tiers", "ELITE", "STRONG", "VALUE", "LEAN"],
        index=0,
    )
    tier_filter_val = None if tier_filter == "All Tiers" else tier_filter

    # ── Date range filtering ──────────────────────────────────
    st.divider()
    st.subheader("📅 Date Range")
    start_date = st.date_input(
        "Start Date",
        value=_datetime(2024, 10, 22),
        help="Only include game logs on or after this date.",
    )
    end_date = st.date_input(
        "End Date",
        value=_datetime.today(),
        help="Only include game logs on or before this date.",
    )
    start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None

    # ── Player selection ──────────────────────────────────────
    st.divider()
    st.subheader("👤 Player Filter")
    all_players = sorted(game_logs_by_player.keys())
    selected_players = st.multiselect(
        "Filter Players (optional)",
        all_players,
        default=[],
        help="Leave empty to backtest all cached players.",
    )

    # ── Simulation depth from Settings ────────────────────────
    sim_depth = st.session_state.get("simulation_depth", 500)
    st.caption(f"Simulation depth: **{sim_depth:,}** (set in ⚙️ Settings)")

    use_real_lines = st.checkbox(
        "📦 Use Real PrizePicks Lines (archive)",
        value=True,
        help="When available, use actual PrizePicks prop lines from the "
             "mirror archive instead of synthetic season-average lines. "
             "Only available for dates the archive has captured.",
    )

    # ── A/B Comparison Mode ───────────────────────────────────
    st.divider()
    ab_mode = st.checkbox(
        "🔀 A/B Comparison Mode",
        value=False,
        help="Run two backtests with different settings side-by-side "
             "to compare which configuration performs best.",
    )
    if ab_mode:
        min_edge_b = st.slider(
            "Config B — Min Edge (%)",
            min_value=1, max_value=20, value=10, step=1,
            help="Edge threshold for the comparison (Config B).",
        ) / 100.0
        tier_filter_b = st.selectbox(
            "Config B — Tier Filter",
            ["All Tiers", "ELITE", "STRONG", "VALUE", "LEAN"],
            index=0,
            key="tier_filter_b",
        )
        tier_filter_val_b = None if tier_filter_b == "All Tiers" else tier_filter_b

    st.divider()
    run_btn = st.button("▶ Run Backtest", type="primary", use_container_width=True)

    st.divider()

    # ── Historical data refresh ───────────────────────────────
    st.subheader("📡 Historical Data")
    st.caption(
        "Auto-load game logs for tonight's players "
        "and update CLV closing lines."
    )
    refresh_hist_btn = st.button(
        "🔄 Refresh Historical Data",
        use_container_width=True,
        disabled=not _HIST_REFRESH_AVAILABLE,
        help="Retrieves the last 30 games per player for all teams playing tonight.",
    )

# ── Info if backtester not available ─────────────────────────
if not _BACKTESTER_AVAILABLE:
    st.error("⚠️ Backtester engine not available. Check engine/backtester.py.")
    st.stop()

# ── Historical Data Refresh Handler ──────────────────────────
if refresh_hist_btn and _HIST_REFRESH_AVAILABLE:
    _prog = st.progress(0, text="Loading historical game logs…")
    def _prog_cb(current, total, msg):
        _prog.progress(min(current / max(total, 1), 1.0), text=msg)

    # ── Joseph Loading Screen — NBA fun facts while loading ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _joseph_hist_loader = joseph_loading_placeholder("Loading historical game data")
    except Exception:
        _joseph_hist_loader = None
    with st.spinner("Loading historical game logs from API-NBA…"):
        todays_games = st.session_state.get("todays_games", [])
        hist_result = _refresh_hist(games=todays_games, last_n_games=30, progress_callback=_prog_cb)

    _prog.empty()
    if _joseph_hist_loader is not None:
        try:
            _joseph_hist_loader.empty()
        except Exception:
            pass
    refreshed  = hist_result.get("players_refreshed", 0)
    clv_closed = hist_result.get("clv_updated", 0)
    errs       = hist_result.get("errors", 0)

    if refreshed > 0:
        st.success(
            f"✅ Historical data refreshed: **{refreshed} player(s)** cached"
            + (f", **{clv_closed} CLV record(s)** updated" if clv_closed else "")
            + (f", {errs} error(s)" if errs else "")
        )
    elif not todays_games:
        st.warning(
            "⚠️ No tonight's games loaded. Go to **📡 Live Games** and click "
            "**Auto-Load Tonight's Games** first, then refresh historical data."
        )
    else:
        st.info(
            "ℹ️ No game logs retrieved. This typically means the data source is "
            "temporarily unavailable, or players don't have IDs in the loaded data."
        )

# ── Status ────────────────────────────────────────────────────
_fresh = len(game_logs_by_player) - stale_count
if game_logs_by_player:
    _pills = [
        f'<span class="pg-pill ok">✅ {len(game_logs_by_player)} Players Cached</span>',
        f'<span class="pg-pill info">📁 {_fresh} Fresh</span>',
    ]
    if stale_count:
        _pills.append(f'<span class="pg-pill stale">⏳ {stale_count} Stale</span>')
    st.markdown(
        f'<div class="pg-status-bar">{"".join(_pills)}'
        f'<span style="color:#6B7A9A;font-size:0.78rem;margin-left:auto;">'
        f'Use <strong>🔄 Refresh Historical Data</strong> in the sidebar to update</span></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown("""
    <div class="pg-status-bar">
        <span class="pg-pill warn">⚠️ No Game Logs Found</span>
        <span style="color:#6B7A9A;font-size:0.78rem;">
            Click <strong>🔄 Refresh Historical Data</strong> in the sidebar
            or go to <strong>🔮 Player Simulator</strong> to cache player logs
        </span>
    </div>
    """, unsafe_allow_html=True)
    if not _HIST_REFRESH_AVAILABLE:
        st.stop()

# ── CLV Model Validation Panel ────────────────────────────────
if _CLV_AVAILABLE:
    clv_summary = get_clv_summary(days=90)
    clv_records_count = clv_summary.get("total_records", 0)
    if clv_records_count > 0:
        with st.expander(
            f"🎯 CLV Model Validation — {clv_records_count} records (last 90 days)",
            expanded=False,
        ):
            avg_clv = clv_summary.get("avg_clv") or 0.0
            pos_rate = clv_summary.get("positive_clv_rate") or 0.0
            clv_c1, clv_c2, clv_c3 = st.columns(3)
            clv_c1.metric(
                "Avg CLV",
                f"{avg_clv:+.2f}",
                help="Positive = model consistently beat the closing line (real edge). "
                     "Negative = market moved away from model (no edge).",
            )
            clv_c2.metric(
                "Positive CLV Rate",
                f"{pos_rate*100:.1f}%",
                delta="✅ Sharp" if pos_rate > 0.55 else "⚠️ Below sharp threshold",
                delta_color="off",
                help="% of picks where the market moved in our direction (beat close).",
            )
            clv_c3.metric(
                "Total Records",
                clv_records_count,
                help="Number of picks with both opening and closing lines recorded.",
            )

            # Per-stat breakdown
            edge_data = validate_model_edge(days=90)
            clv_by_stat = edge_data.get("clv_by_stat", {})
            if clv_by_stat:
                st.markdown("**CLV by Stat Type:**")
                _clv_rows = []
                for stat, info in sorted(clv_by_stat.items()):
                    cnt = info.get("count", 0)
                    if cnt >= 3:
                        _info_avg_clv = info.get('avg_clv') or 0
                        _info_pos_rate = info.get('positive_clv_rate') or 0
                        _clv_rows.append({
                            "Stat": stat.capitalize(),
                            "Picks": cnt,
                            "Avg CLV": f"{_info_avg_clv:+.2f}",
                            "Positive Rate": f"{_info_pos_rate*100:.1f}%",
                            "Signal": "✅ Edge" if _info_avg_clv > 0 else "❌ No Edge",
                        })
                if _clv_rows:
                    st.dataframe(_clv_rows, hide_index=True, use_container_width=True)

        st.divider()

# ── Past Backtest Runs ────────────────────────────────────────
if _DB_AVAILABLE:
    past_runs = load_backtest_results(limit=10)
    if past_runs:
        with st.expander(f"📜 Past Backtest Runs ({len(past_runs)} saved)", expanded=False):
            _run_rows = []
            for r in past_runs:
                _run_rows.append({
                    "Date": str(r.get("run_timestamp", r.get("created_at", "")))[:19],
                    "Season": r.get("season", ""),
                    "Picks": r.get("total_picks", 0),
                    "Win Rate": f"{(r.get('win_rate') or 0)*100:.1f}%",
                    "ROI": f"{(r.get('roi') or 0)*100:.2f}%",
                    "P&L": f"{(r.get('total_pnl') or 0):+.2f}",
                    "Min Edge": f"{(r.get('min_edge') or 0)*100:.0f}%",
                })
            st.dataframe(_run_rows, hide_index=True, use_container_width=True)

if not game_logs_by_player:
    st.stop()


# ── Helper: Run one backtest with progress ────────────────────
def _run_single_backtest(label, edge, tier_filt, progress_placeholder):
    """Run a single backtest with animated progress bar."""
    _prog = progress_placeholder.progress(0, text=f"[{label}] Initializing…")

    def _bt_progress(current, total, msg):
        frac = min(current / max(total, 1), 1.0)
        _prog.progress(frac, text=f"[{label}] {msg}")

    res = run_backtest(
        season=season,
        stat_types=selected_stats,
        min_edge=edge,
        tier_filter=tier_filt,
        game_logs_by_player=game_logs_by_player,
        progress_callback=_bt_progress,
        number_of_simulations=sim_depth,
        start_date=start_date_str,
        end_date=end_date_str,
        selected_players=selected_players if selected_players else None,
    )
    _prog.progress(1.0, text=f"[{label}] Complete ✅")
    return res


# ── Run Backtest ──────────────────────────────────────────────
if run_btn:
    if not selected_stats:
        st.error("Please select at least one stat type.")
        st.stop()

    try:
        prog_a = st.empty()
        result_a = _run_single_backtest("Config A", min_edge, tier_filter_val, prog_a)

        result_b = None
        if ab_mode:
            prog_b = st.empty()
            result_b = _run_single_backtest("Config B", min_edge_b, tier_filter_val_b, prog_b)
            prog_b.empty()

        prog_a.empty()
        st.session_state["backtest_result"] = result_a

        # Auto-save to database
        if _DB_AVAILABLE and result_a.get("status") == "ok":
            save_backtest_result(result_a)

        if result_b:
            st.session_state["backtest_result_b"] = result_b
            if _DB_AVAILABLE and result_b.get("status") == "ok":
                save_backtest_result(result_b)
        else:
            st.session_state.pop("backtest_result_b", None)

    except Exception as _bt_err:
        st.error(f"❌ Backtest failed: {_bt_err}")


# ── Helper: Render results for one config ─────────────────────
def _render_results(result, config_label=""):
    """Render all result sections for a single backtest result."""
    if not result:
        st.markdown("""
        <div class="pg-empty-state">
            <div class="pg-empty-icon">🎯</div>
            <div class="pg-empty-title">READY TO TEST</div>
            <div class="pg-empty-desc">
                Configure settings and click <strong style="color:#00D559;">▶ Run Backtest</strong> to see results.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    if result.get("status") == "no_data":
        st.warning(result.get("message", "No data available."))
        return

    # ── Hero Summary Banner ───────────────────────────────────
    _wr = result.get("win_rate", 0)
    _tp = result.get("total_picks", 0)
    _roi = result.get("roi", 0)
    _sharpe = result.get("sharpe_ratio", 0)
    _elite_wr = result.get("tier_win_rates", {}).get("ELITE", {}).get("win_rate", 0)
    _ws = result.get("longest_win_streak", 0)
    _ls = result.get("longest_loss_streak", 0)
    _season = _html.escape(str(result.get("season", "")))
    _prefix = f"<strong>{_html.escape(config_label)}</strong> · " if config_label else ""

    st.markdown(f"""
    <div class="pg-hero-banner">
        <div class="pg-hero-title">📊 BACKTEST RESULTS</div>
        <div class="pg-hero-subtitle">
            {_prefix}Season {_season}
            <span class="pg-hero-divider">|</span>
            <span class="pg-hero-stat"><span class="hl">{_tp:,}</span> Picks</span>
            <span class="pg-hero-divider">·</span>
            <span class="pg-hero-stat"><span class="hl">{_wr*100:.1f}%</span> Win Rate</span>
            <span class="pg-hero-divider">·</span>
            <span class="pg-hero-stat">ELITE: <span class="gold">{_elite_wr*100:.0f}%</span> WR</span>
            <span class="pg-hero-divider">·</span>
            <span class="pg-hero-stat">ROI: <span class="{'green' if _roi >= 0 else 'red'}">{_roi*100:+.1f}%</span></span>
            <span class="pg-hero-divider">·</span>
            <span class="pg-hero-stat">Sharpe: <span class="hl">{_sharpe:.2f}</span></span>
            <span class="pg-hero-divider">·</span>
            <span class="pg-hero-stat">🔥 {_ws}W <span style="opacity:0.4">/</span> ❄️ {_ls}L streaks</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Glassmorphism Metric Cards ────────────────────────────
    _dd = result.get("max_drawdown", 0.0)
    _be_delta = (_wr - 0.5238) * 100

    # Cards: (label, value, delta, delta_class, value_class)
    cards = [
        ("Total Picks", f"{_tp:,}", "", "", "white"),
        ("Wins", str(result["wins"]), "", "", "green"),
        ("Losses", str(result["losses"]), "", "", "red"),
        ("Win Rate", f"{_wr*100:.1f}%",
         f"{_be_delta:+.1f}% vs breakeven",
         "positive" if _be_delta > 0 else "negative", ""),
        ("ROI", f"{_roi*100:.2f}%",
         f"${result['total_pnl']:.2f} P&L",
         "positive" if _roi > 0 else "negative",
         "green" if _roi > 0 else "red"),
        ("Sharpe Ratio", f"{_sharpe:.3f}",
         "✅ Good" if _sharpe > 1.0 else ("⚠️ Fair" if _sharpe > 0 else "❌ Bad"), "", ""),
        ("Max Drawdown", f"{_dd:.2f}u", "Peak-to-trough", "", "red" if _dd < -3 else ""),
        ("Win Streak", str(_ws), "🔥 Best run", "positive", "green"),
        ("Loss Streak", str(_ls), "❄️ Worst run", "negative" if _ls > 5 else "", "red" if _ls > 5 else ""),
    ]

    # Render 9 cards in rows of 5 + 4
    _row1_cols = st.columns(5)
    for i, col in enumerate(_row1_cols):
        if i < len(cards):
            col.markdown(_glass_card(*cards[i]), unsafe_allow_html=True)
    _row2_cols = st.columns(4)
    for i, col in enumerate(_row2_cols):
        idx = i + 5
        if idx < len(cards):
            col.markdown(_glass_card(*cards[idx]), unsafe_allow_html=True)

    st.divider()

    # ── Sharpe / Drawdown / OOS Explainer ─────────────────────
    with st.expander("📖 Understanding Sharpe Ratio, Drawdown & Out-of-Sample", expanded=False):
        st.markdown("""
        **Sharpe Ratio** measures return-per-unit-of-risk (consistency).
        - > 2.0 = Excellent (consistent profitable edge)
        - 1.0–2.0 = Good
        - 0–1.0 = Fair (profitable but with variance)
        - < 0 = Strategy is losing money

        **Max Drawdown** is the worst peak-to-trough decline in cumulative units.
        - -5 means the strategy fell 5 units from its best point before recovering.
        - Smaller (less negative) is better.

        **Win/Loss Streaks** track longest consecutive wins and losses.
        - Long loss streaks mean higher bankroll risk.
        - Consistent short streaks indicate stable variance.

        **Out-of-Sample (OOS) Split**: The pick log is split 70% in-sample / 30% OOS.
        - If OOS win rate ≈ in-sample win rate, the model generalizes well.
        - If OOS is significantly lower, the model may be overfit to historical data.
        """)

    # ── In-Sample vs Out-of-Sample ────────────────────────────
    oos = result.get("oos_metrics", {})
    if oos and oos.get("oos_picks", 0) > 0:
        st.markdown(_section_header("🔬", "In-Sample vs Out-of-Sample"), unsafe_allow_html=True)
        _oos_wr = oos.get("oos_win_rate", 0)
        _is_wr = oos.get("is_win_rate", 0)
        _wr_gap = (_oos_wr - _is_wr) * 100
        _oos_cols = st.columns(4)
        _oos_cols[0].markdown(_glass_card("In-Sample Picks", str(oos.get("is_picks", 0)), "", "", "white"), unsafe_allow_html=True)
        _oos_cols[1].markdown(_glass_card("In-Sample WR", f"{_is_wr*100:.1f}%", "", "", ""), unsafe_allow_html=True)
        _oos_cols[2].markdown(_glass_card("OOS Picks", str(oos.get("oos_picks", 0)), "", "", "white"), unsafe_allow_html=True)
        _oos_cols[3].markdown(_glass_card(
            "OOS Win Rate", f"{_oos_wr*100:.1f}%",
            f"{_wr_gap:+.1f}% vs in-sample",
            "positive" if _wr_gap >= 0 else "negative",
            "green" if _wr_gap >= -2 else ("" if _wr_gap >= -5 else "red"),
        ), unsafe_allow_html=True)
        if abs(_wr_gap) < 3:
            st.success("✅ Model generalizes well — OOS win rate is within 3% of in-sample rate.")
        elif _wr_gap < -5:
            st.warning(
                f"⚠️ OOS win rate is {abs(_wr_gap):.1f}% below in-sample. "
                "The model may be overfit — check if thresholds need adjustment."
            )
        else:
            st.info(f"ℹ️ OOS win rate gap: {_wr_gap:+.1f}%")

    st.divider()

    # ── Cumulative P&L Chart (Plotly) ─────────────────────────
    pick_log = result.get("pick_log", [])
    if pick_log:
        st.markdown(_section_header("📈", "Cumulative P&L Curve"), unsafe_allow_html=True)
        _PAYOUT = 0.909
        _cumulative = 0.0
        _pnl_series = []
        _peak_series = []
        _dates_list = []
        _players_list = []
        _stats_list = []
        _peak = 0.0

        for _p in pick_log:
            _cumulative += _PAYOUT if _p["correct"] else -1.0
            _pnl_series.append(round(_cumulative, 2))
            if _cumulative > _peak:
                _peak = _cumulative
            _peak_series.append(round(_peak, 2))
            _dates_list.append(_p.get("date", ""))
            _players_list.append(_p.get("player", ""))
            _stats_list.append(_p.get("stat", "").capitalize())

        if _PLOTLY_AVAILABLE:
            fig = go.Figure()

            # Determine fill color based on final P&L
            _fill_color = "rgba(0,230,118,0.12)" if _cumulative >= 0 else "rgba(255,82,82,0.12)"
            _line_color = "#00D559"

            # Build hover text
            _hover = [
                f"Pick #{i+1}<br>{_dates_list[i]}<br>"
                f"{_players_list[i]} — {_stats_list[i]}<br>"
                f"P&L: {_pnl_series[i]:+.2f}u"
                for i in range(len(_pnl_series))
            ]

            # Use spline smoothing only for smaller datasets to avoid overhead
            _line_shape = "spline" if len(_pnl_series) <= 200 else "linear"
            _line_smooth = 0.3 if _line_shape == "spline" else None
            _line_kw = dict(color=_line_color, width=2.5, shape=_line_shape)
            if _line_smooth is not None:
                _line_kw["smoothing"] = _line_smooth

            fig.add_trace(go.Scatter(
                x=list(range(1, len(_pnl_series) + 1)),
                y=_pnl_series,
                mode="lines",
                name="Cumulative P&L",
                line=_line_kw,
                fill="tozeroy",
                fillcolor=_fill_color,
                hovertext=_hover,
                hoverinfo="text",
            ))

            # Drawdown shading (peak line)
            fig.add_trace(go.Scatter(
                x=list(range(1, len(_peak_series) + 1)),
                y=_peak_series,
                mode="lines",
                name="Peak",
                line=dict(color="rgba(255,215,64,0.25)", width=1, dash="dot"),
                hoverinfo="skip",
            ))

            # Final P&L annotation
            fig.add_annotation(
                x=len(_pnl_series),
                y=_cumulative,
                text=f"<b>{_cumulative:+.2f}u</b>",
                showarrow=True,
                arrowhead=2,
                arrowcolor="rgba(0,213,89,0.45)",
                font=dict(color="#00D559", size=12, family="JetBrains Mono"),
                bgcolor="rgba(7,10,19,0.85)",
                bordercolor="rgba(0,213,89,0.3)",
                borderwidth=1,
                ax=-40,
                ay=-25,
            )

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(7,10,19,0.6)",
                height=320,
                margin=dict(l=45, r=25, t=35, b=45),
                xaxis=dict(
                    title=dict(text="Pick #", font=dict(size=11, color="rgba(255,255,255,0.45)")),
                    gridcolor="rgba(255,255,255,0.04)",
                    tickfont=dict(size=10, color="rgba(255,255,255,0.40)"),
                ),
                yaxis=dict(
                    title=dict(text="Units", font=dict(size=11, color="rgba(255,255,255,0.45)")),
                    gridcolor="rgba(255,255,255,0.04)",
                    zeroline=True,
                    zerolinecolor="rgba(0,213,89,0.13)",
                    zerolinewidth=1.5,
                    tickfont=dict(size=10, color="rgba(255,255,255,0.40)"),
                ),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1,
                    font=dict(size=10, color="rgba(255,255,255,0.50)"),
                    bgcolor="rgba(0,0,0,0)",
                ),
                font=dict(color="rgba(255,255,255,0.65)", size=11),
                hoverlabel=dict(
                    bgcolor="rgba(7,10,19,0.92)",
                    bordercolor="rgba(0,213,89,0.26)",
                    font=dict(color="#e8f0ff", size=12),
                ),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Fallback to built-in chart if Plotly not installed
            st.line_chart({"Cumulative P&L (units)": _pnl_series}, height=260)

        st.caption(
            f"📊 {len(pick_log)} picks · "
            f"Final: {_cumulative:+.2f} units · "
            f"ROI: {result['roi']*100:+.2f}% per pick"
        )

        st.divider()

    # ── By Tier (color-coded) ─────────────────────────────────
    with st.expander("📊 Win Rate & ROI by Model Tier", expanded=True):
        tier_data = result.get("tier_win_rates", {})
        if tier_data:
            _tier_order = ["ELITE", "STRONG", "VALUE", "LEAN"]
            _tier_css = {"ELITE": "pg-tier-elite", "STRONG": "pg-tier-strong",
                         "VALUE": "pg-tier-value", "LEAN": "pg-tier-lean"}
            _tier_icons = {"ELITE": "👑", "STRONG": "⚡", "VALUE": "📊", "LEAN": "📉"}
            for tier in _tier_order:
                d = tier_data.get(tier)
                if not d or d["picks"] == 0:
                    continue
                _roi_pct = d.get("roi", 0.0) * 100
                _pnl = d.get("pnl", 0.0)
                _wr_pct = d["win_rate"] * 100
                _css_class = _tier_css.get(tier, "")
                _icon = _tier_icons.get(tier, "")
                # Color scale for win rate
                if _wr_pct >= 55:
                    _wr_color = "#00e676"
                    _bar_color = "#00e676"
                elif _wr_pct >= 50:
                    _wr_color = "#ffd740"
                    _bar_color = "#ffd740"
                else:
                    _wr_color = "#ff5252"
                    _bar_color = "#ff5252"
                _bar_width = min(_wr_pct, 100)
                _safe_tier = _html.escape(tier)
                st.markdown(f"""
                <div class="pg-tier-card {_html.escape(_css_class)}">
                    <span class="pg-tier-badge">{_icon} {_safe_tier}</span>
                    <div class="pg-tier-meta">
                        <strong>{d['picks']}</strong> picks · 
                        <strong>{d['wins']}</strong>W / <strong>{d['picks'] - d['wins']}</strong>L ·
                        ROI: {_roi_pct:+.2f}% ·
                        P&amp;L: {_pnl:+.2f}u
                        {"✅" if _roi_pct > 0 else "❌"}
                    </div>
                    <div class="pg-tier-bar-wrap">
                        <div class="pg-tier-bar" style="width:{_bar_width}%;background:{_bar_color};"></div>
                    </div>
                    <span class="pg-tier-wr" style="color:{_wr_color};">{_wr_pct:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No tier data available.")

    # ── By Stat Type (color-coded) ────────────────────────────
    with st.expander("📈 Win Rate by Stat Type", expanded=True):
        stat_data = result.get("stat_win_rates", {})
        if stat_data:
            rows = []
            for stat, d in sorted(stat_data.items(), key=lambda x: -x[1]["wins"]):
                if d["picks"] > 0:
                    _wr_val = d["win_rate"] * 100
                    rows.append({
                        "Stat": stat.capitalize(),
                        "Picks": d["picks"],
                        "Wins": d["wins"],
                        "Losses": d["picks"] - d["wins"],
                        "Win Rate": f"{_wr_val:.1f}%",
                        "Above 52%": "✅" if d["win_rate"] > 0.52 else "❌",
                    })
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.caption("No picks met the criteria.")
        else:
            st.caption("No stat data available.")

    # ── By Edge Bucket ────────────────────────────────────────
    with st.expander("🎯 Win Rate by Edge Bucket", expanded=True):
        edge_bdata = result.get("edge_win_rates", {})
        if edge_bdata:
            rows = []
            for label, d in edge_bdata.items():
                if d["picks"] > 0:
                    rows.append({
                        "Edge Range": label,
                        "Picks": d["picks"],
                        "Wins": d["wins"],
                        "Win Rate": f"{d['win_rate']*100:.1f}%",
                        "Insight": (
                            "✅ Higher edge = higher win rate (healthy)" if d["win_rate"] > 0.55
                            else "⚠️ Expected >55% win rate at this edge level"
                        ),
                    })
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.caption("No picks in any edge bucket.")

    # ── Per-Player Breakdown ──────────────────────────────────
    player_data = result.get("player_win_rates", {})
    if player_data:
        with st.expander(f"👤 Per-Player Breakdown ({len(player_data)} players)", expanded=False):
            _player_rows = []
            for pname, pd in sorted(player_data.items(), key=lambda x: -x[1]["picks"]):
                if pd["picks"] > 0:
                    _player_rows.append({
                        "Player": pname,
                        "Picks": pd["picks"],
                        "Win Rate": f"{pd['win_rate']*100:.1f}%",
                        "ROI": f"{pd['roi']*100:.2f}%",
                        "P&L": f"{pd['pnl']:+.2f}",
                        "Best Stat": pd.get("best_stat", "N/A"),
                        "Worst Stat": pd.get("worst_stat", "N/A"),
                    })
            if _player_rows:
                st.markdown("**Top Performers** (sorted by pick count):")
                st.dataframe(_player_rows[:20], hide_index=True, use_container_width=True)
                if len(_player_rows) > 20:
                    with st.expander("Show all players"):
                        st.dataframe(_player_rows, hide_index=True, use_container_width=True)

    st.divider()

    # ── Pick Log ──────────────────────────────────────────────
    with st.expander("📋 Full Pick Log (last 200)", expanded=False):
        if pick_log:
            display = []
            for p in reversed(pick_log):
                display.append({
                    "Date": p["date"],
                    "Player": p["player"],
                    "Stat": p["stat"].capitalize(),
                    "Line": p["line"],
                    "Actual": p["actual"],
                    "Direction": p["direction"],
                    "Result": "✅ WIN" if p["correct"] else "❌ LOSS",
                    "Prob": f"{p['model_prob']*100:.1f}%",
                    "Tier": p["tier"],
                    "Edge": f"{p['edge']*100:.1f}%",
                })
            st.dataframe(display, hide_index=True, use_container_width=True)

            # Download buttons — JSON and CSV
            _dl_col1, _dl_col2 = st.columns(2)
            _log_json = _json.dumps(pick_log, indent=2)
            _dl_col1.download_button(
                "⬇️ Download Pick Log (JSON)",
                data=_log_json,
                file_name=f"backtest_pick_log_{result.get('season','')}.json",
                mime="application/json",
            )

            # CSV export
            _csv_buffer = _io.StringIO()
            if pick_log:
                _writer = _csv.DictWriter(_csv_buffer, fieldnames=pick_log[0].keys())
                _writer.writeheader()
                _writer.writerows(pick_log)
            _dl_col2.download_button(
                "⬇️ Download Pick Log (CSV)",
                data=_csv_buffer.getvalue(),
                file_name=f"backtest_pick_log_{result.get('season','')}.csv",
                mime="text/csv",
            )
        else:
            st.caption("No picks in the log.")


# ── Display Results ───────────────────────────────────────────
result = st.session_state.get("backtest_result")
result_b = st.session_state.get("backtest_result_b")

if not result and not result_b:
    st.markdown("""
    <div class="pg-empty-state">
        <div class="pg-empty-icon">🎯</div>
        <div class="pg-empty-title">READY TO TEST</div>
        <div class="pg-empty-desc">
            Configure your backtest settings in the sidebar and click
            <strong style="color:#00D559;">▶ Run Backtest</strong> to validate the model
            against historical data.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if result_b:
    # A/B Comparison mode — show side by side
    st.markdown(_section_header("🔀", "A/B Comparison Results"), unsafe_allow_html=True)
    tab_a, tab_b = st.tabs(["⚙️ Config A", "⚙️ Config B"])
    with tab_a:
        _render_results(result, config_label="Config A")
    with tab_b:
        _render_results(result_b, config_label="Config B")

    # Comparison summary
    if (result and result.get("status") == "ok" and
            result_b and result_b.get("status") == "ok"):
        st.divider()
        st.markdown(_section_header("📊", "Head-to-Head Comparison"), unsafe_allow_html=True)
        _cmp_cols = st.columns(5)
        _metrics_cmp = [
            ("Win Rate", result["win_rate"]*100, result_b["win_rate"]*100, "%", ".1f"),
            ("ROI", result["roi"]*100, result_b["roi"]*100, "%", ".1f"),
            ("Sharpe", result.get("sharpe_ratio", 0), result_b.get("sharpe_ratio", 0), "", ".2f"),
            ("Picks", result["total_picks"], result_b["total_picks"], "", ".0f"),
            ("P&L", result["total_pnl"], result_b["total_pnl"], "u", ".1f"),
        ]
        for i, (name, val_a, val_b, unit, fmt) in enumerate(_metrics_cmp):
            with _cmp_cols[i]:
                _winner = "A" if val_a >= val_b else "B"
                _badge_cls = "pg-winner-a" if _winner == "A" else "pg-winner-b"
                if val_a == val_b:
                    _badge_cls = "pg-winner-tie"
                    _winner = "Tie"
                _fa = f"{val_a:{fmt}}"
                _fb = f"{val_b:{fmt}}"
                st.markdown(f"""
                <div class="pg-winner-card">
                    <div class="pg-winner-label">{_html.escape(name)}</div>
                    <div class="pg-winner-vals">
                        A: {_html.escape(_fa)}{_html.escape(unit)} · B: {_html.escape(_fb)}{_html.escape(unit)}
                    </div>
                    <span class="pg-winner-badge {_badge_cls}">
                        {"🏆 " if _winner != "Tie" else ""}Config {_winner}
                    </span>
                </div>
                """, unsafe_allow_html=True)
else:
    _render_results(result)
