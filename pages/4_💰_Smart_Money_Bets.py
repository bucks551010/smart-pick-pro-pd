# ============================================================
# FILE: pages/15_👹_Goblin_Demon_Zone.py
# PURPOSE: EASY MONEY (Goblin) & SMART RISK (Demon) — dedicated
#          spotlight for extreme-value alt-line props.
# ============================================================

import streamlit as st
import base64
import pathlib
import html as _html
import datetime
import time as _time

st.set_page_config(
    page_title="Smart Money Bets — SmartBetPro NBA",
    page_icon="💰",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Smart Money Bets")
from utils.seo import inject_page_seo
inject_page_seo("Smart Money Bets")

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

# ─── Global CSS ───────────────────────────────────────────────
from styles.theme import get_global_css
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── Joseph floating widget ──────────────────────────────────
from utils.components import inject_joseph_floating, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_goblin_demon"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

# ─── Data imports ─────────────────────────────────────────────
from data.data_manager import (
    load_players_data,
    enrich_prop_with_player_data,
    load_props_from_session,
)
from data.platform_fetcher import fetch_prizepicks_props
from data.platform_mappings import display_stat_name as _display_stat_name
from data.player_profile_service import get_headshot_url, get_team_logo_url
from tracking.bet_tracker import log_new_bet

# ── Thresholds ────────────────────────────────────────────────
_EASY_MONEY_MIN_DEV = 50.0    # Goblin: line_vs_avg_pct <= -50%
_SMART_RISK_MIN_DEV = 30.0    # Demon:  line_vs_avg_pct <= -30%
_SM_MIN_SEASON_MINUTES = 14.0
_SM_MAX_PICKS_PER_PLAYER = 2
_SM_MAX_PICKS_PER_TEAM = 4
_SM_MIN_STAT_AVG = {
    "points": 6.0,
    "rebounds": 3.0,
    "assists": 2.0,
    "turnovers": 1.2,
    "steals": 0.9,
    "blocks": 0.7,
    "blocks_steals": 1.2,
    "points_assists": 8.0,
    "points_rebounds": 10.0,
    "points_rebounds_assists": 14.0,
    "rebounds_assists": 5.0,
    "fta": 1.0,
    "ftm": 0.8,
    "fantasy_score_pp": 18.0,
}


# ============================================================
# SECTION: Load logos as base64 for inline HTML
# ============================================================

_ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"

@st.cache_data(ttl=3600)
def _load_logo_b64(filename: str) -> str:
    path = _ASSETS / filename
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode()
    return ""

_GOBLIN_B64 = _load_logo_b64("New_Goblin_Logo.png")
_DEMON_B64 = _load_logo_b64("New_Demon_Logo.png")

# ── Neural Network Matrix — static SVG + CSS-animated overlays ───────
# The SVG is baked into .stApp background-image (static but full-viewport).
# Animated life comes from real <div> elements with CSS keyframes —
# proven to work in Streamlit (orbs, scan lines, pulsing nodes).

_NEURAL_SVG_RAW = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 900" preserveAspectRatio="none">'
    '<style>'
    '.s15e{stroke:rgba(94,255,130,0.18);stroke-width:1;fill:none}'
    '.s15r{stroke:rgba(231,76,60,0.14);stroke-width:1;fill:none}'
    '.s15d{stroke:rgba(94,255,130,0.35);stroke-width:1.5;fill:none;stroke-dasharray:8 32}'
    '.s15x{stroke:rgba(231,76,60,0.28);stroke-width:1.5;fill:none;stroke-dasharray:8 32}'
    '.s15g{fill:rgba(94,255,130,0.55)}'
    '.s15q{fill:rgba(231,76,60,0.45)}'
    '</style>'
    # Layer 1 — top band
    '<line class="s15e" x1="60" y1="80" x2="220" y2="160"/>'
    '<line class="s15e" x1="220" y1="160" x2="400" y2="90"/>'
    '<line class="s15e" x1="400" y1="90" x2="580" y2="170"/>'
    '<line class="s15e" x1="580" y1="170" x2="760" y2="100"/>'
    '<line class="s15e" x1="760" y1="100" x2="940" y2="180"/>'
    '<line class="s15e" x1="940" y1="180" x2="1120" y2="110"/>'
    '<line class="s15e" x1="1120" y1="110" x2="1300" y2="170"/>'
    # Layer 2 — upper-mid
    '<line class="s15e" x1="120" y1="260" x2="300" y2="340"/>'
    '<line class="s15e" x1="300" y1="340" x2="480" y2="270"/>'
    '<line class="s15e" x1="480" y1="270" x2="660" y2="350"/>'
    '<line class="s15e" x1="660" y1="350" x2="840" y2="280"/>'
    '<line class="s15e" x1="840" y1="280" x2="1020" y2="350"/>'
    '<line class="s15e" x1="1020" y1="350" x2="1200" y2="280"/>'
    # Layer 3 — mid
    '<line class="s15e" x1="80" y1="440" x2="260" y2="520"/>'
    '<line class="s15e" x1="260" y1="520" x2="440" y2="450"/>'
    '<line class="s15e" x1="440" y1="450" x2="620" y2="530"/>'
    '<line class="s15e" x1="620" y1="530" x2="800" y2="460"/>'
    '<line class="s15e" x1="800" y1="460" x2="980" y2="530"/>'
    '<line class="s15e" x1="980" y1="530" x2="1160" y2="460"/>'
    '<line class="s15e" x1="1160" y1="460" x2="1340" y2="530"/>'
    # Layer 4 — lower-mid
    '<line class="s15e" x1="140" y1="620" x2="320" y2="700"/>'
    '<line class="s15e" x1="320" y1="700" x2="500" y2="630"/>'
    '<line class="s15e" x1="500" y1="630" x2="680" y2="710"/>'
    '<line class="s15e" x1="680" y1="710" x2="860" y2="640"/>'
    '<line class="s15e" x1="860" y1="640" x2="1040" y2="710"/>'
    '<line class="s15e" x1="1040" y1="710" x2="1220" y2="640"/>'
    # Layer 5 — bottom
    '<line class="s15e" x1="100" y1="800" x2="340" y2="850"/>'
    '<line class="s15e" x1="340" y1="850" x2="580" y2="790"/>'
    '<line class="s15e" x1="580" y1="790" x2="820" y2="850"/>'
    '<line class="s15e" x1="820" y1="850" x2="1060" y2="790"/>'
    '<line class="s15e" x1="1060" y1="790" x2="1300" y2="850"/>'
    # Cross-layer verticals — green
    '<line class="s15e" x1="220" y1="160" x2="300" y2="340"/>'
    '<line class="s15e" x1="580" y1="170" x2="660" y2="350"/>'
    '<line class="s15e" x1="940" y1="180" x2="1020" y2="350"/>'
    '<line class="s15e" x1="300" y1="340" x2="260" y2="520"/>'
    '<line class="s15e" x1="660" y1="350" x2="620" y2="530"/>'
    '<line class="s15e" x1="1020" y1="350" x2="980" y2="530"/>'
    '<line class="s15e" x1="260" y1="520" x2="320" y2="700"/>'
    '<line class="s15e" x1="620" y1="530" x2="680" y2="710"/>'
    '<line class="s15e" x1="980" y1="530" x2="1040" y2="710"/>'
    '<line class="s15e" x1="320" y1="700" x2="340" y2="850"/>'
    '<line class="s15e" x1="680" y1="710" x2="820" y2="850"/>'
    '<line class="s15e" x1="1040" y1="710" x2="1060" y2="790"/>'
    # Cross-layer diagonals — red
    '<line class="s15r" x1="60" y1="80" x2="300" y2="340"/>'
    '<line class="s15r" x1="400" y1="90" x2="660" y2="350"/>'
    '<line class="s15r" x1="760" y1="100" x2="1020" y2="350"/>'
    '<line class="s15r" x1="120" y1="260" x2="260" y2="520"/>'
    '<line class="s15r" x1="480" y1="270" x2="620" y2="530"/>'
    '<line class="s15r" x1="840" y1="280" x2="980" y2="530"/>'
    '<line class="s15r" x1="1200" y1="280" x2="1160" y2="460"/>'
    '<line class="s15r" x1="80" y1="440" x2="320" y2="700"/>'
    '<line class="s15r" x1="440" y1="450" x2="680" y2="710"/>'
    '<line class="s15r" x1="800" y1="460" x2="1040" y2="710"/>'
    '<line class="s15r" x1="260" y1="520" x2="500" y2="630"/>'
    '<line class="s15r" x1="620" y1="530" x2="860" y2="640"/>'
    # Signal dashes — green
    '<line class="s15d" x1="220" y1="160" x2="660" y2="350"/>'
    '<line class="s15d" x1="660" y1="350" x2="980" y2="530"/>'
    '<line class="s15d" x1="300" y1="340" x2="620" y2="530"/>'
    '<line class="s15d" x1="480" y1="270" x2="800" y2="460"/>'
    '<line class="s15d" x1="940" y1="180" x2="1160" y2="460"/>'
    '<line class="s15d" x1="80" y1="440" x2="500" y2="630"/>'
    # Signal dashes — red
    '<line class="s15x" x1="580" y1="170" x2="300" y2="340"/>'
    '<line class="s15x" x1="1120" y1="110" x2="840" y2="280"/>'
    '<line class="s15x" x1="760" y1="100" x2="480" y2="270"/>'
    '<line class="s15x" x1="1020" y1="350" x2="800" y2="460"/>'
    '<line class="s15x" x1="660" y1="350" x2="440" y2="450"/>'
    # Nodes — green
    '<circle class="s15g" cx="60" cy="80" r="3.5"/>'
    '<circle class="s15g" cx="220" cy="160" r="4"/>'
    '<circle class="s15g" cx="400" cy="90" r="3.5"/>'
    '<circle class="s15g" cx="580" cy="170" r="4"/>'
    '<circle class="s15g" cx="760" cy="100" r="3.5"/>'
    '<circle class="s15g" cx="940" cy="180" r="4"/>'
    '<circle class="s15g" cx="1120" cy="110" r="3.5"/>'
    '<circle class="s15g" cx="1300" cy="170" r="3"/>'
    '<circle class="s15g" cx="120" cy="260" r="3.5"/>'
    '<circle class="s15g" cx="300" cy="340" r="4.5"/>'
    '<circle class="s15g" cx="480" cy="270" r="3.5"/>'
    '<circle class="s15g" cx="660" cy="350" r="4.5"/>'
    '<circle class="s15g" cx="840" cy="280" r="3.5"/>'
    '<circle class="s15g" cx="1020" cy="350" r="4.5"/>'
    '<circle class="s15g" cx="1200" cy="280" r="3.5"/>'
    '<circle class="s15g" cx="80" cy="440" r="3.5"/>'
    '<circle class="s15g" cx="260" cy="520" r="4"/>'
    '<circle class="s15g" cx="440" cy="450" r="3.5"/>'
    '<circle class="s15g" cx="620" cy="530" r="4.5"/>'
    '<circle class="s15g" cx="800" cy="460" r="3.5"/>'
    '<circle class="s15g" cx="980" cy="530" r="4"/>'
    '<circle class="s15g" cx="1160" cy="460" r="3.5"/>'
    '<circle class="s15g" cx="1340" cy="530" r="3"/>'
    '<circle class="s15g" cx="100" cy="800" r="3"/>'
    '<circle class="s15g" cx="340" cy="850" r="3.5"/>'
    '<circle class="s15g" cx="580" cy="790" r="3"/>'
    '<circle class="s15g" cx="820" cy="850" r="3.5"/>'
    '<circle class="s15g" cx="1060" cy="790" r="3"/>'
    '<circle class="s15g" cx="1300" cy="850" r="3"/>'
    # Nodes — red
    '<circle class="s15q" cx="140" cy="620" r="4"/>'
    '<circle class="s15q" cx="320" cy="700" r="4.5"/>'
    '<circle class="s15q" cx="500" cy="630" r="4"/>'
    '<circle class="s15q" cx="680" cy="710" r="4.5"/>'
    '<circle class="s15q" cx="860" cy="640" r="4"/>'
    '<circle class="s15q" cx="1040" cy="710" r="4.5"/>'
    '<circle class="s15q" cx="1220" cy="640" r="4"/>'
    '</svg>'
)

_NEURAL_SVG_B64 = base64.b64encode(_NEURAL_SVG_RAW.encode()).decode()

_NEURAL_BG_CSS = (
    '<style>'
    '.stApp{'
    'background-color:#070A13 !important;'
    'background-image:url("data:image/svg+xml;base64,' + _NEURAL_SVG_B64 + '") !important;'
    'background-size:cover !important;'
    'background-position:center center !important;'
    'background-repeat:no-repeat !important;'
    '}'
    '[data-testid="stAppViewContainer"]{'
    'background:transparent !important;'
    '}'
    '[data-testid="stHeader"]{'
    'background:transparent !important;'
    '}'
    '</style>'
)

# ── Animated overlay — real <div> elements immune to Streamlit resets ──
_NEURAL_ANIM_HTML = """
<style>
/* ── Keyframes ── */
@keyframes s15OrbDrift1 {
  0%, 100% { transform: translate(0,0) scale(1); opacity: 0.12; }
  33%      { transform: translate(50px,-40px) scale(1.15); opacity: 0.22; }
  66%      { transform: translate(-30px,25px) scale(0.90); opacity: 0.07; }
}
@keyframes s15OrbDrift2 {
  0%, 100% { transform: translate(0,0) scale(1); opacity: 0.10; }
  33%      { transform: translate(-40px,30px) scale(1.18); opacity: 0.20; }
  66%      { transform: translate(25px,-20px) scale(0.85); opacity: 0.05; }
}
/* ── Runner path keyframes — nodes travel along network edges ── */
@keyframes s15RunA {
  0%{left:4.3%;top:8.9%} 14.3%{left:15.7%;top:17.8%} 28.6%{left:28.6%;top:10%}
  42.9%{left:41.4%;top:18.9%} 57.1%{left:54.3%;top:11.1%} 71.4%{left:67.1%;top:20%}
  85.7%{left:80%;top:12.2%} 100%{left:92.9%;top:18.9%}
}
@keyframes s15RunB {
  0%{left:8.6%;top:28.9%} 16.7%{left:21.4%;top:37.8%} 33.3%{left:34.3%;top:30%}
  50%{left:47.1%;top:38.9%} 66.7%{left:60%;top:31.1%} 83.3%{left:72.9%;top:38.9%}
  100%{left:85.7%;top:31.1%}
}
@keyframes s15RunC {
  0%{left:5.7%;top:48.9%} 14.3%{left:18.6%;top:57.8%} 28.6%{left:31.4%;top:50%}
  42.9%{left:44.3%;top:58.9%} 57.1%{left:57.1%;top:51.1%} 71.4%{left:70%;top:58.9%}
  85.7%{left:82.9%;top:51.1%} 100%{left:95.7%;top:58.9%}
}
@keyframes s15RunD {
  0%{left:10%;top:68.9%} 16.7%{left:22.9%;top:77.8%} 33.3%{left:35.7%;top:70%}
  50%{left:48.6%;top:78.9%} 66.7%{left:61.4%;top:71.1%} 83.3%{left:74.3%;top:78.9%}
  100%{left:87.1%;top:71.1%}
}
@keyframes s15RunE {
  0%{left:7.1%;top:88.9%} 20%{left:24.3%;top:94.4%} 40%{left:41.4%;top:87.8%}
  60%{left:58.6%;top:94.4%} 80%{left:75.7%;top:87.8%} 100%{left:92.9%;top:94.4%}
}
@keyframes s15RunF {
  0%{left:15.7%;top:17.8%} 25%{left:21.4%;top:37.8%} 50%{left:18.6%;top:57.8%}
  75%{left:22.9%;top:77.8%} 100%{left:24.3%;top:94.4%}
}
@keyframes s15RunG {
  0%{left:41.4%;top:18.9%} 25%{left:34.3%;top:30%} 50%{left:31.4%;top:50%}
  75%{left:35.7%;top:70%} 100%{left:41.4%;top:87.8%}
}
@keyframes s15RunH {
  0%{left:67.1%;top:20%} 25%{left:72.9%;top:38.9%} 50%{left:70%;top:58.9%}
  75%{left:74.3%;top:78.9%} 100%{left:75.7%;top:87.8%}
}
@keyframes s15RunI {
  0%{left:4.3%;top:8.9%} 33.3%{left:21.4%;top:37.8%}
  66.7%{left:44.3%;top:58.9%} 100%{left:58.6%;top:94.4%}
}
@keyframes s15RunJ {
  0%{left:54.3%;top:11.1%} 33.3%{left:72.9%;top:38.9%}
  66.7%{left:82.9%;top:51.1%} 100%{left:92.9%;top:94.4%}
}
@keyframes s15SignalRun {
  0%   { left: -4%; opacity: 0; }
  5%   { opacity: 1; }
  95%  { opacity: 1; }
  100% { left: 104%; opacity: 0; }
}
@keyframes s15SignalRunR {
  0%   { right: -4%; opacity: 0; }
  5%   { opacity: 1; }
  95%  { opacity: 1; }
  100% { right: 104%; opacity: 0; }
}
@keyframes s15DataFloat {
  0%   { transform: translateY(0) scale(1); opacity: 0; }
  10%  { opacity: 0.7; }
  90%  { opacity: 0.7; }
  100% { transform: translateY(-35vh) scale(0.3); opacity: 0; }
}

/* ── Container ── */
.s15-nn-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

/* ── Floating orbs ── */
.s15-orbA {
  position: absolute; left: 10%; top: 12%;
  width: 550px; height: 550px; border-radius: 50%;
  background: radial-gradient(circle, rgba(94,255,130,0.16) 0%, transparent 70%);
  filter: blur(70px);
  animation: s15OrbDrift1 9s ease-in-out infinite;
}
.s15-orbB {
  position: absolute; right: 6%; bottom: 10%;
  width: 500px; height: 500px; border-radius: 50%;
  background: radial-gradient(circle, rgba(231,76,60,0.13) 0%, transparent 70%);
  filter: blur(70px);
  animation: s15OrbDrift2 11s ease-in-out infinite 2s;
}
.s15-orbC {
  position: absolute; left: 45%; top: 35%;
  width: 420px; height: 420px; border-radius: 50%;
  background: radial-gradient(circle, rgba(94,255,130,0.08) 0%, transparent 70%);
  filter: blur(90px);
  animation: s15OrbDrift1 14s ease-in-out infinite 5s;
}

/* ── Runner nodes — travel along network edges ── */
.s15-runner {
  position: absolute; width:6px; height:6px; border-radius:50%;
  margin:-3px 0 0 -3px;
  will-change:left,top;
  animation-timing-function:linear;
  animation-iteration-count:infinite;
  animation-direction:alternate;
}
.s15-rg {
  background:rgba(94,255,130,0.9);
  box-shadow:0 0 8px 3px rgba(94,255,130,0.6),0 0 20px 8px rgba(94,255,130,0.2);
}
.s15-rr {
  background:rgba(231,76,60,0.9);
  box-shadow:0 0 8px 3px rgba(231,76,60,0.5),0 0 20px 8px rgba(231,76,60,0.15);
}

/* ── Horizontal signal streaks ── */
.s15-sig {
  position: absolute; height: 2px;
  border-radius: 2px;
}
.s15-sig-g {
  width: 60px;
  background: linear-gradient(90deg, transparent, rgba(94,255,130,0.25), transparent);
  box-shadow: 0 0 8px 2px rgba(94,255,130,0.06);
  animation: s15SignalRun 4s linear infinite;
}
.s15-sig-r {
  width: 50px;
  background: linear-gradient(90deg, transparent, rgba(231,76,60,0.2), transparent);
  box-shadow: 0 0 6px 2px rgba(231,76,60,0.05);
  animation: s15SignalRunR 5s linear infinite;
}

/* ── Data particles floating up ── */
.s15-particle {
  position: absolute; width: 3px; height: 3px;
  border-radius: 50%; background: rgba(94,255,130,0.6);
  animation: s15DataFloat 8s linear infinite;
}

/* ── Content on top ── */
[data-testid="stAppViewContainer"] > section {
  position: relative; z-index: 2;
}
</style>

<div class="s15-nn-overlay">
  <!-- Floating orbs -->
  <div class="s15-orbA"></div>
  <div class="s15-orbB"></div>
  <div class="s15-orbC"></div>

  <!-- Runner nodes — traveling along network edge paths -->
  <div class="s15-runner s15-rg" style="animation-name:s15RunA;animation-duration:12s;animation-delay:0s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunA;animation-duration:12s;animation-delay:6s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunB;animation-duration:10s;animation-delay:1s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunB;animation-duration:10s;animation-delay:6s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunC;animation-duration:12s;animation-delay:2s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunC;animation-duration:12s;animation-delay:8s"></div>
  <div class="s15-runner s15-rr" style="animation-name:s15RunD;animation-duration:11s;animation-delay:0.5s"></div>
  <div class="s15-runner s15-rr" style="animation-name:s15RunD;animation-duration:11s;animation-delay:5.5s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunE;animation-duration:9s;animation-delay:3s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunE;animation-duration:9s;animation-delay:7s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunF;animation-duration:8s;animation-delay:0s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunF;animation-duration:8s;animation-delay:4s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunG;animation-duration:9s;animation-delay:2s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunG;animation-duration:9s;animation-delay:6.5s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunH;animation-duration:8s;animation-delay:1s"></div>
  <div class="s15-runner s15-rg" style="animation-name:s15RunH;animation-duration:8s;animation-delay:5s"></div>
  <div class="s15-runner s15-rr" style="animation-name:s15RunI;animation-duration:7s;animation-delay:1.5s"></div>
  <div class="s15-runner s15-rr" style="animation-name:s15RunJ;animation-duration:7s;animation-delay:3.5s"></div>

  <!-- Horizontal signal streaks -->
  <div class="s15-sig s15-sig-g" style="top:18%;animation-duration:4s;animation-delay:0s"></div>
  <div class="s15-sig s15-sig-g" style="top:38%;animation-duration:5s;animation-delay:1.5s"></div>
  <div class="s15-sig s15-sig-g" style="top:58%;animation-duration:4.5s;animation-delay:3s"></div>
  <div class="s15-sig s15-sig-g" style="top:10%;animation-duration:3.5s;animation-delay:2s"></div>
  <div class="s15-sig s15-sig-g" style="top:50%;animation-duration:6s;animation-delay:0.5s"></div>
  <div class="s15-sig s15-sig-r" style="top:29%;animation-duration:5s;animation-delay:0.8s"></div>
  <div class="s15-sig s15-sig-r" style="top:69%;animation-duration:6s;animation-delay:2.5s"></div>
  <div class="s15-sig s15-sig-r" style="top:79%;animation-duration:4.5s;animation-delay:1s"></div>
  <div class="s15-sig s15-sig-r" style="top:45%;animation-duration:5.5s;animation-delay:3.5s"></div>

  <!-- Data particles floating up -->
  <div class="s15-particle" style="left:15%;bottom:20%;animation-delay:0s"></div>
  <div class="s15-particle" style="left:30%;bottom:15%;animation-delay:2s;animation-duration:10s"></div>
  <div class="s15-particle" style="left:50%;bottom:10%;animation-delay:4s;animation-duration:9s"></div>
  <div class="s15-particle" style="left:70%;bottom:25%;animation-delay:1s;animation-duration:11s"></div>
  <div class="s15-particle" style="left:85%;bottom:18%;animation-delay:3s"></div>
  <div class="s15-particle" style="left:22%;bottom:30%;animation-delay:5s;animation-duration:7s;background:rgba(231,76,60,0.5)"></div>
  <div class="s15-particle" style="left:60%;bottom:22%;animation-delay:6s;animation-duration:9s;background:rgba(231,76,60,0.5)"></div>
  <div class="s15-particle" style="left:42%;bottom:12%;animation-delay:1.5s;animation-duration:12s"></div>
</div>
"""





# ============================================================
# SECTION: CSS for this page
# ============================================================

_PAGE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ═══════════════════════════════════════════════════════════
   KEYFRAME ANIMATIONS
   ═══════════════════════════════════════════════════════════ */
@keyframes s15Scanline {
    0%   { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}
@keyframes s15GridScroll {
    0%   { background-position: 0 0; }
    100% { background-position: 40px 40px; }
}
@keyframes s15BorderGlowG {
    0%, 100% { box-shadow: 0 0 30px rgba(46,204,64,0.12), inset 0 0 40px rgba(46,204,64,0.04); }
    50%      { box-shadow: 0 0 60px rgba(46,204,64,0.35), inset 0 0 70px rgba(46,204,64,0.08), 0 0 100px rgba(46,204,64,0.08); }
}
@keyframes s15BorderGlowD {
    0%, 100% { box-shadow: 0 0 30px rgba(231,76,60,0.12), inset 0 0 40px rgba(231,76,60,0.04); }
    50%      { box-shadow: 0 0 60px rgba(231,76,60,0.35), inset 0 0 70px rgba(231,76,60,0.08), 0 0 100px rgba(231,76,60,0.08); }
}
@keyframes s15CardSlideIn {
    from { opacity: 0; transform: translateY(24px) scale(0.94); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes s15LogoFloat {
    0%, 100% { transform: translateY(0) scale(1); }
    50%      { transform: translateY(-10px) scale(1.08); }
}
@keyframes s15LogoPulseG {
    0%, 100% { filter: drop-shadow(0 0 22px rgba(46,204,64,0.55)) drop-shadow(0 0 55px rgba(46,204,64,0.22)); }
    50%      { filter: drop-shadow(0 0 42px rgba(46,204,64,0.90)) drop-shadow(0 0 90px rgba(46,204,64,0.45)) drop-shadow(0 0 140px rgba(46,204,64,0.18)); }
}
@keyframes s15LogoPulseD {
    0%, 100% { filter: drop-shadow(0 0 22px rgba(231,76,60,0.55)) drop-shadow(0 0 55px rgba(231,76,60,0.22)); }
    50%      { filter: drop-shadow(0 0 42px rgba(231,76,60,0.90)) drop-shadow(0 0 90px rgba(231,76,60,0.45)) drop-shadow(0 0 140px rgba(231,76,60,0.18)); }
}
@keyframes s15Shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes s15GaugeFill {
    from { stroke-dashoffset: 226; }
}
@keyframes s15CountPulse {
    0%, 100% { transform: scale(1); }
    50%      { transform: scale(1.08); }
}
@keyframes s15PillGlowG {
    0%, 100% { box-shadow: 0 0 8px rgba(46,204,64,0.06); }
    50%      { box-shadow: 0 0 24px rgba(46,204,64,0.28); }
}
@keyframes s15PillGlowD {
    0%, 100% { box-shadow: 0 0 8px rgba(231,76,60,0.06); }
    50%      { box-shadow: 0 0 24px rgba(231,76,60,0.28); }
}
@keyframes s15HeadshotRingG {
    0%, 100% { border-color: rgba(46,204,64,0.30); box-shadow: 0 0 16px rgba(46,204,64,0.10); }
    50%      { border-color: rgba(46,204,64,0.65); box-shadow: 0 0 30px rgba(46,204,64,0.30); }
}
@keyframes s15HeadshotRingD {
    0%, 100% { border-color: rgba(231,76,60,0.30); box-shadow: 0 0 16px rgba(231,76,60,0.10); }
    50%      { border-color: rgba(231,76,60,0.65); box-shadow: 0 0 30px rgba(231,76,60,0.30); }
}
@keyframes s15EdgePulse {
    0%, 100% { opacity: 0.5; }
    50%      { opacity: 1; }
}
@keyframes s15BarFill {
    from { width: 0%; }
}
@keyframes s15HeroOrb {
    0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
    33%      { transform: translate(-50%, -50%) scale(1.3); opacity: 0.7; }
    66%      { transform: translate(-50%, -50%) scale(0.9); opacity: 0.4; }
}
@keyframes s15TierPulse {
    0%, 100% { box-shadow: none; }
    50%      { box-shadow: 0 0 16px currentColor; }
}
@keyframes s15FloatParticle {
    0%   { transform: translateY(0) translateX(0); opacity: 0; }
    15%  { opacity: 0.6; }
    85%  { opacity: 0.6; }
    100% { transform: translateY(-180px) translateX(30px); opacity: 0; }
}

/* Neural dot-grid texture — applied via background on the element itself
   so it doesn't conflict with ::before or ::after pseudo-elements */
.s15-neural-texture {
    background-image:
        radial-gradient(circle at 20% 30%, rgba(94,255,130,0.06) 1.5px, transparent 1.5px),
        radial-gradient(circle at 50% 65%, rgba(231,76,60,0.05) 1.5px, transparent 1.5px),
        radial-gradient(circle at 80% 25%, rgba(94,255,130,0.04) 1px, transparent 1px),
        radial-gradient(circle at 90% 80%, rgba(231,76,60,0.04) 1px, transparent 1px),
        radial-gradient(circle at 35% 90%, rgba(94,255,130,0.03) 1px, transparent 1px),
        radial-gradient(circle at 65% 10%, rgba(231,76,60,0.03) 1px, transparent 1px) !important;
    background-size: 120px 120px, 150px 150px, 100px 100px, 130px 130px, 90px 90px, 110px 110px !important;
}

/* ═══════════════════════════════════════════════════════════
   PAGE HERO
   ═══════════════════════════════════════════════════════════ */
.s15-page-hero {
    text-align: center;
    padding: 60px 24px 28px;
    position: relative;
    margin-bottom: 8px;
    overflow: hidden;
    background:
        radial-gradient(circle at 20% 30%, rgba(94,255,130,0.06) 1.5px, transparent 1.5px),
        radial-gradient(circle at 55% 60%, rgba(231,76,60,0.05) 1.5px, transparent 1.5px),
        radial-gradient(circle at 80% 20%, rgba(94,255,130,0.04) 1px, transparent 1px),
        radial-gradient(circle at 40% 85%, rgba(231,76,60,0.04) 1px, transparent 1px),
        radial-gradient(ellipse at 50% 40%, rgba(46,204,64,0.05) 0%, rgba(231,76,60,0.035) 30%, transparent 60%);
    background-size: 120px 120px, 150px 150px, 100px 100px, 130px 130px, 100% 100%;
}
.s15-page-hero::before {
    content: '';
    position: absolute; top: 25%; left: 50%;
    transform: translate(-50%, -50%);
    width: 800px; height: 500px;
    background: radial-gradient(circle, rgba(46,204,64,0.12) 0%, rgba(231,76,60,0.08) 30%, transparent 60%);
    pointer-events: none; z-index: 0;
    filter: blur(60px);
    animation: s15HeroOrb 12s ease-in-out infinite;
}
.s15-page-hero::after {
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent 2%, rgba(46,204,64,0.30) 25%, rgba(255,255,255,0.12) 50%, rgba(231,76,60,0.30) 75%, transparent 98%);
    z-index: 1;
}
.s15-page-hero h1 {
    font-family: 'Inter', sans-serif;
    font-size: 3.4rem;
    font-weight: 900;
    letter-spacing: 0.18em;
    background: linear-gradient(135deg, #5eff82 0%, #2ecc40 25%, #ffffff 50%, #ff6b5b 75%, #e74c3c 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: s15Shimmer 5s linear infinite;
    margin: 0 auto;
    line-height: 1.15;
    text-transform: uppercase;
    text-align: center;
    position: relative; z-index: 1;
}
.s15-page-hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.92rem;
    color: rgba(255,255,255,0.42);
    margin: 18px auto 0;
    max-width: 700px;
    letter-spacing: 0.01em;
    line-height: 1.70;
    position: relative; z-index: 1;
    text-align: center;
    display: block;
    margin-left: auto !important;
    margin-right: auto !important;
}
.s15-page-hero-sub strong {
    color: rgba(255,255,255,0.70);
    font-weight: 700;
}
.s15-page-stats {
    display: inline-flex;
    gap: 20px;
    margin-top: 20px;
    padding: 10px 28px;
    border-radius: 14px;
    background: rgba(255,255,255,0.015);
    border: 1px solid rgba(255,255,255,0.05);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: rgba(255,255,255,0.50);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    position: relative; z-index: 1;
}
.s15-page-stats strong {
    color: rgba(255,255,255,0.85);
    font-weight: 800;
}

/* ═══════════════════════════════════════════════════════════
   SECTION DIVIDER
   ═══════════════════════════════════════════════════════════ */
.s15-divider {
    height: 2px;
    margin: 36px 0;
    position: relative;
    overflow: hidden;
    border: none;
    border-radius: 2px;
}
.s15-divider-goblin {
    background: linear-gradient(90deg, transparent 0%, rgba(46,204,64,0.15) 15%, rgba(46,204,64,0.50) 50%, rgba(46,204,64,0.15) 85%, transparent 100%);
    box-shadow: 0 0 20px rgba(46,204,64,0.15);
}
.s15-divider-demon {
    background: linear-gradient(90deg, transparent 0%, rgba(231,76,60,0.15) 15%, rgba(231,76,60,0.50) 50%, rgba(231,76,60,0.15) 85%, transparent 100%);
    box-shadow: 0 0 20px rgba(231,76,60,0.15);
}

/* ═══════════════════════════════════════════════════════════
   SECTION BANNER
   ═══════════════════════════════════════════════════════════ */
.s15-banner {
    position: relative;
    border-radius: 26px;
    padding: 0;
    margin-bottom: 28px;
    overflow: hidden;
    border: 1.5px solid;
}
.s15-banner-inner {
    position: relative; z-index: 1;
    padding: 36px 38px 30px;
}
.s15-banner::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
    background-size: 36px 36px;
    animation: s15GridScroll 35s linear infinite;
    pointer-events: none;
    mask-image: radial-gradient(ellipse at 50% 50%, black 25%, transparent 68%);
    -webkit-mask-image: radial-gradient(ellipse at 50% 50%, black 25%, transparent 68%);
    z-index: 0;
}
.s15-banner-scan {
    position: absolute; top: 0; left: 0; right: 0; height: 200%;
    pointer-events: none; z-index: 0;
    animation: s15Scanline 7s linear infinite;
}
.s15-banner::after {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background-size: 200% 100%;
    animation: s15Shimmer 3.5s linear infinite;
    z-index: 2;
}

/* Goblin banner */
.s15-banner-goblin {
    background: linear-gradient(145deg, #010d03 0%, #041c08 18%, #072a10 40%, #0c3a1a 60%, #072010 80%, #010d03 100%);
    border-color: rgba(46,204,64,0.28);
    animation: s15BorderGlowG 4.5s ease-in-out infinite;
}
.s15-banner-goblin .s15-banner-scan {
    background: linear-gradient(180deg, transparent 0%, rgba(46,204,64,0.015) 46%, rgba(46,204,64,0.05) 50%, rgba(46,204,64,0.015) 54%, transparent 100%);
}
.s15-banner-goblin::after {
    background: linear-gradient(90deg, transparent, rgba(46,204,64,0.40), transparent);
    background-size: 200% 100%;
}
/* Demon banner */
.s15-banner-demon {
    background: linear-gradient(145deg, #0d0102 0%, #1c0406 18%, #2a070c 40%, #3a0a14 60%, #200608 80%, #0d0102 100%);
    border-color: rgba(231,76,60,0.28);
    animation: s15BorderGlowD 4.5s ease-in-out infinite;
}
.s15-banner-demon .s15-banner-scan {
    background: linear-gradient(180deg, transparent 0%, rgba(231,76,60,0.015) 46%, rgba(231,76,60,0.05) 50%, rgba(231,76,60,0.015) 54%, transparent 100%);
}
.s15-banner-demon::after {
    background: linear-gradient(90deg, transparent, rgba(231,76,60,0.40), transparent);
    background-size: 200% 100%;
}

/* Banner Header with center-focused layout */
.s15-banner-header {
    display: flex;
    align-items: center;
    gap: 28px;
    margin-bottom: 26px;
}
.s15-banner-logo {
    width: 180px; height: 180px;
    border-radius: 20px;
    object-fit: contain;
    border: none;
    flex-shrink: 0;
    background: transparent;
    animation: s15LogoFloat 3.5s ease-in-out infinite;
}
.s15-banner-goblin .s15-banner-logo {
    animation: s15LogoFloat 3.5s ease-in-out infinite, s15LogoPulseG 2.5s ease-in-out infinite;
}
.s15-banner-demon .s15-banner-logo {
    animation: s15LogoFloat 3.5s ease-in-out infinite, s15LogoPulseD 2.5s ease-in-out infinite;
}
.s15-banner-title {
    font-family: 'Inter', sans-serif;
    font-size: 2.2rem;
    font-weight: 900;
    letter-spacing: 0.22em;
    margin: 0;
    text-transform: uppercase;
    line-height: 1.1;
}
.s15-banner-goblin .s15-banner-title {
    color: #5eff82;
    text-shadow: 0 0 40px rgba(46,204,64,0.60), 0 0 80px rgba(46,204,64,0.25), 0 2px 4px rgba(0,0,0,0.9);
}
.s15-banner-demon .s15-banner-title {
    color: #ff6b5b;
    text-shadow: 0 0 40px rgba(231,76,60,0.60), 0 0 80px rgba(231,76,60,0.25), 0 2px 4px rgba(0,0,0,0.9);
}
.s15-banner-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    color: rgba(255,255,255,0.45);
    margin: 10px 0 0;
    letter-spacing: 0.01em;
    line-height: 1.55;
    max-width: 500px;
}

/* Banner Metrics */
.s15-banner-metrics {
    display: flex;
    align-items: stretch;
    gap: 16px;
    margin-top: 24px;
    flex-wrap: wrap;
}
.s15-count-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 100px;
    padding: 18px 26px;
    border-radius: 18px;
    position: relative;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}
.s15-banner-goblin .s15-count-block {
    background: linear-gradient(160deg, rgba(46,204,64,0.06), rgba(46,204,64,0.18));
    border: 1.5px solid rgba(46,204,64,0.28);
}
.s15-banner-demon .s15-count-block {
    background: linear-gradient(160deg, rgba(231,76,60,0.06), rgba(231,76,60,0.18));
    border: 1.5px solid rgba(231,76,60,0.28);
}
.s15-count-block::after {
    content: '';
    position: absolute; top: 0; left: 10%; right: 10%; height: 1px;
}
.s15-banner-goblin .s15-count-block::after { background: linear-gradient(90deg, transparent, rgba(46,204,64,0.35), transparent); }
.s15-banner-demon .s15-count-block::after { background: linear-gradient(90deg, transparent, rgba(231,76,60,0.35), transparent); }
.s15-count-num {
    font-family: 'Inter', sans-serif;
    font-size: 2.8rem;
    font-weight: 900;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    animation: s15CountPulse 3s ease-in-out infinite;
}
.s15-banner-goblin .s15-count-num { color: #5eff82; text-shadow: 0 0 28px rgba(46,204,64,0.50); }
.s15-banner-demon .s15-count-num { color: #ff6b5b; text-shadow: 0 0 28px rgba(231,76,60,0.50); }
.s15-count-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem;
    font-weight: 700;
    letter-spacing: 0.24em;
    margin-top: 6px;
    text-transform: uppercase;
}
.s15-banner-goblin .s15-count-lbl { color: rgba(94,255,130,0.55); }
.s15-banner-demon .s15-count-lbl { color: rgba(255,107,91,0.55); }

/* Metric pills */
.s15-metric-pill {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 16px 24px;
    border-radius: 18px;
    font-family: 'JetBrains Mono', monospace;
    gap: 6px;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}
.s15-banner-goblin .s15-metric-pill {
    background: rgba(46,204,64,0.04);
    border: 1.5px solid rgba(46,204,64,0.16);
    animation: s15PillGlowG 4s ease-in-out infinite;
}
.s15-banner-demon .s15-metric-pill {
    background: rgba(231,76,60,0.04);
    border: 1.5px solid rgba(231,76,60,0.16);
    animation: s15PillGlowD 4s ease-in-out infinite;
}
.s15-metric-val {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 1.35rem;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}
.s15-banner-goblin .s15-metric-val { color: #5eff82; text-shadow: 0 0 18px rgba(46,204,64,0.32); }
.s15-banner-demon .s15-metric-val { color: #ff6b5b; text-shadow: 0 0 18px rgba(231,76,60,0.32); }
.s15-metric-lbl {
    font-size: 0.50rem;
    font-weight: 700;
    letter-spacing: 0.20em;
    text-transform: uppercase;
}
.s15-banner-goblin .s15-metric-lbl { color: rgba(94,255,130,0.48); }
.s15-banner-demon .s15-metric-lbl { color: rgba(255,107,91,0.48); }

/* Direction badge */
.s15-dir-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 18px;
    font-family: 'Inter', sans-serif;
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.18em;
}
.s15-banner-goblin .s15-dir-badge {
    background: linear-gradient(135deg, rgba(46,204,64,0.10), rgba(46,204,64,0.24));
    border: 1.5px solid rgba(46,204,64,0.36);
    color: #5eff82;
}
.s15-banner-demon .s15-dir-badge {
    background: linear-gradient(135deg, rgba(231,76,60,0.10), rgba(231,76,60,0.24));
    border: 1.5px solid rgba(231,76,60,0.36);
    color: #ff6b5b;
}
.s15-dir-arrow { font-size: 1.10rem; }

/* ═══════════════════════════════════════════════════════════
   PICK CARDS — SLIM SINGLE-ROW NEURAL LAYOUT
   ═══════════════════════════════════════════════════════════ */
.s15-card {
    position: relative;
    border-radius: 22px;
    padding: 0;
    margin-bottom: 14px;
    overflow: hidden;
    font-family: 'Inter', sans-serif;
    color: #c8d8e0;
    animation: s15CardSlideIn 0.55s ease both;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1.5px solid;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}
.s15-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
}
.s15-card::after {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1.5px;
    pointer-events: none;
}
.s15-card:hover {
    transform: translateY(-5px) scale(1.005);
}

/* Goblin card */
.s15-card-goblin {
    background: linear-gradient(160deg, rgba(3,14,5,0.97) 0%, rgba(6,24,12,0.95) 50%, rgba(4,18,8,0.96) 100%);
    border-color: rgba(46,204,64,0.14);
    box-shadow: 0 4px 24px rgba(0,0,0,0.55), 0 0 1px rgba(46,204,64,0.14);
}
.s15-card-goblin::before { background: radial-gradient(ellipse at -5% 50%, rgba(46,204,64,0.08) 0%, transparent 50%); }
.s15-card-goblin::after { background: linear-gradient(90deg, rgba(46,204,64,0.28), rgba(46,204,64,0.06) 40%, transparent 80%); }
.s15-card-goblin:hover {
    border-color: rgba(46,204,64,0.35);
    box-shadow: 0 12px 48px rgba(0,0,0,0.65), 0 0 40px rgba(46,204,64,0.16);
}
/* Demon card */
.s15-card-demon {
    background: linear-gradient(160deg, rgba(14,3,3,0.97) 0%, rgba(24,6,8,0.95) 50%, rgba(18,4,5,0.96) 100%);
    border-color: rgba(231,76,60,0.14);
    box-shadow: 0 4px 24px rgba(0,0,0,0.55), 0 0 1px rgba(231,76,60,0.14);
}
.s15-card-demon::before { background: radial-gradient(ellipse at -5% 50%, rgba(231,76,60,0.08) 0%, transparent 50%); }
.s15-card-demon::after { background: linear-gradient(90deg, rgba(231,76,60,0.28), rgba(231,76,60,0.06) 40%, transparent 80%); }
.s15-card-demon:hover {
    border-color: rgba(231,76,60,0.35);
    box-shadow: 0 12px 48px rgba(0,0,0,0.65), 0 0 40px rgba(231,76,60,0.16);
}

/* Card single-row — slim layout */
.s15-card-top {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 20px;
    position: relative;
    z-index: 1;
}

/* Rank badge */
.s15-rank {
    flex: 0 0 auto;
    width: 40px; height: 40px;
    display: flex;
    align-items: center; justify-content: center;
    border-radius: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 800;
}
.s15-card-goblin .s15-rank {
    background: linear-gradient(145deg, rgba(46,204,64,0.18), rgba(46,204,64,0.06));
    border: 1.5px solid rgba(46,204,64,0.34);
    color: #5eff82;
    text-shadow: 0 0 10px rgba(46,204,64,0.35);
}
.s15-card-demon .s15-rank {
    background: linear-gradient(145deg, rgba(231,76,60,0.18), rgba(231,76,60,0.06));
    border: 1.5px solid rgba(231,76,60,0.34);
    color: #ff6b5b;
    text-shadow: 0 0 10px rgba(231,76,60,0.35);
}

/* Headshot + team logo */
.s15-headshot-wrap {
    position: relative;
    flex-shrink: 0;
    width: 72px; height: 72px;
}
.s15-card-headshot {
    width: 72px; height: 72px;
    border-radius: 50%;
    object-fit: cover;
    border: 2.5px solid;
    background: linear-gradient(145deg, #0a0e0c, #060906);
    box-shadow: 0 6px 20px rgba(0,0,0,0.55);
}
.s15-card-goblin .s15-card-headshot {
    border-color: rgba(46,204,64,0.25);
    animation: s15HeadshotRingG 3.5s ease-in-out infinite;
}
.s15-card-demon .s15-card-headshot {
    border-color: rgba(231,76,60,0.25);
    animation: s15HeadshotRingD 3.5s ease-in-out infinite;
}
.s15-card-team-logo {
    position: absolute;
    bottom: -2px; right: -4px;
    width: 28px; height: 28px;
    background: rgba(0,0,0,0.80);
    border-radius: 50%;
    padding: 3px;
    object-fit: contain;
    border: 1.5px solid rgba(255,255,255,0.12);
    box-shadow: 0 3px 10px rgba(0,0,0,0.50);
}

/* Player info (top row) */
.s15-card-info { flex: 1; min-width: 0; }
.s15-card-player {
    font-weight: 800;
    font-size: 1.08rem;
    color: #e8f0f8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
    letter-spacing: 0.01em;
}
.s15-card-meta {
    font-size: 0.68rem;
    color: rgba(255,255,255,0.38);
    margin-top: 4px;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.02em;
}

/* Edge tier badge */
.s15-card-tier {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 12px;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 0.52rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-top: 6px;
    animation: s15TierPulse 4s ease-in-out infinite;
}
.s15-card-goblin .s15-card-tier {
    background: rgba(46,204,64,0.08);
    border: 1px solid rgba(46,204,64,0.20);
    color: #5eff82;
}
.s15-card-demon .s15-card-tier {
    background: rgba(231,76,60,0.08);
    border: 1px solid rgba(231,76,60,0.20);
    color: #ff6b5b;
}
.s15-tier-dot {
    width: 5px; height: 5px;
    border-radius: 50%;
    animation: s15EdgePulse 2s ease-in-out infinite;
}
.s15-card-goblin .s15-tier-dot { background: #5eff82; box-shadow: 0 0 8px rgba(46,204,64,0.60); }
.s15-card-demon .s15-tier-dot { background: #ff6b5b; box-shadow: 0 0 8px rgba(231,76,60,0.60); }

/* Neural synapse line on cards */
.s15-card .s15-card-synapse {
    position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent 5%, currentColor 50%, transparent 95%);
    opacity: 0.08;
    z-index: 0;
}
.s15-card-goblin .s15-card-synapse { color: #2ecc40; }
.s15-card-demon .s15-card-synapse { color: #e74c3c; }

/* Neural dots texture on cards */
.s15-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        radial-gradient(circle, rgba(94,255,130,0.04) 1px, transparent 1px),
        radial-gradient(circle, rgba(94,255,130,0.02) 1px, transparent 1px);
    background-size: 40px 40px, 80px 80px;
    background-position: 0 0, 20px 20px;
    pointer-events: none;
    opacity: 0.5;
    animation: s15GridScroll 30s ease-in-out infinite;
}
.s15-card-demon::before {
    background-image:
        radial-gradient(circle, rgba(231,76,60,0.04) 1px, transparent 1px),
        radial-gradient(circle, rgba(231,76,60,0.02) 1px, transparent 1px);
    background-size: 40px 40px, 80px 80px;
    background-position: 0 0, 20px 20px;
}

/* Prop pill — inline in the single row */
.s15-card-prop {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    padding: 5px 14px;
    border-radius: 9px;
    flex-shrink: 0;
    margin-left: auto;
}
.s15-card-goblin .s15-card-prop {
    color: #5eff82;
    background: linear-gradient(135deg, rgba(46,204,64,0.06), rgba(46,204,64,0.14));
    border: 1.5px solid rgba(46,204,64,0.18);
}
.s15-card-demon .s15-card-prop {
    color: #ff6b5b;
    background: linear-gradient(135deg, rgba(231,76,60,0.06), rgba(231,76,60,0.14));
    border: 1.5px solid rgba(231,76,60,0.18);
}
.s15-prop-dir {
    font-size: 1rem;
    line-height: 1;
}

/* Compact AVG/LINE data inline */
.s15-card-data {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-left: 4px;
    flex-shrink: 0;
}
.s15-data-chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 3px 10px;
    border-radius: 8px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    min-width: 52px;
}
.s15-data-chip-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
}
.s15-card-goblin .s15-data-chip-val { color: #5eff82; }
.s15-card-demon .s15-data-chip-val { color: #ff6b5b; }
.s15-data-chip-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.42rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.28);
}

/* SVG Gap Gauge — compact */
.s15-gauge-wrap {
    position: relative;
    width: 56px; height: 56px;
    flex-shrink: 0;
}
.s15-gauge-svg { width: 100%; height: 100%; }
.s15-gauge-bg {
    fill: none;
    stroke: rgba(255,255,255,0.04);
    stroke-width: 5;
}
.s15-gauge-ring {
    fill: none;
    stroke-width: 5;
    stroke-linecap: round;
    transform: rotate(-90deg);
    transform-origin: center;
    animation: s15GaugeFill 1.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}
.s15-card-goblin .s15-gauge-ring { stroke: #2ecc40; filter: drop-shadow(0 0 8px rgba(46,204,64,0.55)); }
.s15-card-demon .s15-gauge-ring  { stroke: #e74c3c; filter: drop-shadow(0 0 8px rgba(231,76,60,0.55)); }
.s15-gauge-text {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 900;
    text-anchor: middle;
    dominant-baseline: central;
}
.s15-card-goblin .s15-gauge-text { fill: #5eff82; }
.s15-card-demon .s15-gauge-text  { fill: #ff6b5b; }
.s15-gauge-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 5.5px;
    font-weight: 700;
    text-anchor: middle;
    fill: rgba(255,255,255,0.35);
    letter-spacing: 0.14em;
}

/* Empty state */
.s15-empty {
    text-align: center;
    padding: 65px 24px;
    color: rgba(255,255,255,0.28);
    font-size: 1rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.03em;
    border: 1.5px dashed rgba(255,255,255,0.06);
    border-radius: 22px;
    background: rgba(255,255,255,0.006);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
}
.s15-empty-icon { font-size: 2.4rem; display: block; margin-bottom: 14px; opacity: 0.5; }

/* ═══════════════════════════════════════════════════════════
   EDUCATION — INTELLIGENCE BRIEFING
   ═══════════════════════════════════════════════════════════ */
@keyframes s15EduSlideDown {
    from { opacity: 0; transform: translateY(-22px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes s15EduPulse {
    0%, 100% { opacity: 0.6; }
    50%      { opacity: 1; }
}
@keyframes s15TickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
@keyframes s15EduGlow {
    0%, 100% { box-shadow: 0 4px 50px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.06); }
    50%      { box-shadow: 0 4px 70px rgba(0,0,0,0.55), 0 0 40px rgba(94,255,130,0.05), 0 0 0 1px rgba(255,255,255,0.09); }
}
.s15-edu {
    position: relative;
    border-radius: 26px;
    padding: 42px 38px 34px;
    margin: 0 0 36px;
    overflow: hidden;
    background:
        radial-gradient(circle at 1px 1px, rgba(255,255,255,0.022) 1px, transparent 0),
        radial-gradient(circle at 20% 30%, rgba(94,255,130,0.04) 1.5px, transparent 1.5px),
        radial-gradient(circle at 70% 65%, rgba(231,76,60,0.03) 1.5px, transparent 1.5px),
        linear-gradient(160deg, rgba(6,10,18,0.97) 0%, rgba(12,20,32,0.94) 50%, rgba(6,10,18,0.97) 100%) !important;
    background-size: 30px 30px, 100px 100px, 120px 120px, 100% 100% !important;
    border: 1.5px solid rgba(255,255,255,0.08);
    animation: s15EduSlideDown 0.6s ease-out, s15EduGlow 8s ease-in-out infinite;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}
.s15-edu::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background-image: radial-gradient(circle at 1px 1px, rgba(255,255,255,0.020) 1px, transparent 0);
    background-size: 30px 30px;
    pointer-events: none; z-index: 0;
}
.s15-edu::after {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent 0%, rgba(94,255,130,0.32) 25%, rgba(255,255,255,0.18) 50%, rgba(255,107,91,0.32) 75%, transparent 100%);
    background-size: 200% 100%;
    animation: s15Shimmer 4.5s linear infinite;
    z-index: 2;
}
.s15-edu-inner { position: relative; z-index: 1; text-align: center; display: flex; flex-direction: column; align-items: center; }
.s15-edu-badge {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 18px; border-radius: 22px;
    background: linear-gradient(135deg, rgba(94,255,130,0.07), rgba(255,107,91,0.07));
    border: 1px solid rgba(255,255,255,0.08);
    font-family: 'Inter', sans-serif;
    font-size: 0.56rem; font-weight: 800;
    letter-spacing: 0.22em; color: rgba(255,255,255,0.52);
    text-transform: uppercase; margin-bottom: 18px;
}
.s15-edu-badge-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #5eff82; box-shadow: 0 0 12px rgba(94,255,130,0.60);
    animation: s15EduPulse 2s ease-in-out infinite;
}
.s15-edu h2 {
    font-family: 'Inter', sans-serif;
    font-size: 1.6rem; font-weight: 900;
    letter-spacing: 0.16em; color: #ffffff;
    margin: 0 0 12px; text-transform: uppercase; line-height: 1.15;
}
.s15-edu-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem; color: rgba(255,255,255,0.44);
    margin: 0 auto 32px; max-width: 760px; line-height: 1.70;
}
.s15-edu-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px; margin-bottom: 28px;
    width: 100%;
}
.s15-edu-card {
    text-align: left;
    padding: 28px 22px; border-radius: 18px;
    background: rgba(255,255,255,0.014);
    border: 1.5px solid rgba(255,255,255,0.05);
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative; overflow: hidden;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
}
.s15-edu-card:hover {
    transform: translateY(-6px);
    border-color: rgba(255,255,255,0.16);
    box-shadow: 0 16px 48px rgba(0,0,0,0.40);
}
.s15-edu-card::after {
    content: ''; position: absolute;
    bottom: 0; left: 18%; right: 18%; height: 1.5px;
    transition: all 0.35s ease;
}
.s15-edu-card:hover::after { left: 5%; right: 5%; }
.s15-edu-card-green { border-color: rgba(46,204,64,0.10); }
.s15-edu-card-green:hover { border-color: rgba(46,204,64,0.26); box-shadow: 0 16px 48px rgba(0,0,0,0.40), 0 0 24px rgba(46,204,64,0.08); }
.s15-edu-card-green::after { background: linear-gradient(90deg, transparent, rgba(46,204,64,0.45), transparent); }
.s15-edu-card-red { border-color: rgba(231,76,60,0.10); }
.s15-edu-card-red:hover { border-color: rgba(231,76,60,0.26); box-shadow: 0 16px 48px rgba(0,0,0,0.40), 0 0 24px rgba(231,76,60,0.08); }
.s15-edu-card-red::after { background: linear-gradient(90deg, transparent, rgba(231,76,60,0.45), transparent); }
.s15-edu-card-blue { border-color: rgba(52,152,219,0.10); }
.s15-edu-card-blue:hover { border-color: rgba(52,152,219,0.26); box-shadow: 0 16px 48px rgba(0,0,0,0.40), 0 0 24px rgba(52,152,219,0.08); }
.s15-edu-card-blue::after { background: linear-gradient(90deg, transparent, rgba(52,152,219,0.45), transparent); }
.s15-edu-card-gold { border-color: rgba(241,196,15,0.10); }
.s15-edu-card-gold:hover { border-color: rgba(241,196,15,0.26); box-shadow: 0 16px 48px rgba(0,0,0,0.40), 0 0 24px rgba(241,196,15,0.08); }
.s15-edu-card-gold::after { background: linear-gradient(90deg, transparent, rgba(241,196,15,0.45), transparent); }
.s15-edu-card-icon { font-size: 2.2rem; margin-bottom: 16px; display: block; line-height: 1; }
.s15-edu-card-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem; font-weight: 800;
    letter-spacing: 0.14em; text-transform: uppercase;
    margin: 0 0 12px; line-height: 1.2;
}
.s15-edu-card-green .s15-edu-card-title { color: #5eff82; }
.s15-edu-card-red .s15-edu-card-title { color: #ff6b5b; }
.s15-edu-card-blue .s15-edu-card-title { color: #5dade2; }
.s15-edu-card-gold .s15-edu-card-title { color: #f1c40f; }
.s15-edu-card-text {
    font-family: 'Inter', sans-serif;
    font-size: 0.76rem; color: rgba(255,255,255,0.40);
    line-height: 1.70; margin: 0;
}
.s15-edu-card-text strong { color: rgba(255,255,255,0.68); font-weight: 700; }
.s15-edu-example {
    padding: 16px 24px; border-radius: 16px;
    background: linear-gradient(135deg, rgba(94,255,130,0.02) 0%, rgba(255,255,255,0.008) 50%, rgba(255,107,91,0.02) 100%);
    border: 1.5px solid rgba(255,255,255,0.05);
    display: flex; align-items: center; gap: 18px; overflow: hidden;
    width: 100%;
    box-sizing: border-box;
}
.s15-edu-example-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.56rem; font-weight: 800;
    letter-spacing: 0.18em; color: rgba(255,255,255,0.35);
    text-transform: uppercase; flex-shrink: 0; white-space: nowrap;
}
.s15-edu-ticker-wrap {
    flex: 1; overflow: hidden;
    mask-image: linear-gradient(90deg, transparent 0%, black 6%, black 94%, transparent 100%);
    -webkit-mask-image: linear-gradient(90deg, transparent 0%, black 6%, black 94%, transparent 100%);
}
.s15-edu-ticker {
    display: flex; gap: 56px; white-space: nowrap;
    animation: s15TickerScroll 38s linear infinite;
}
.s15-edu-ticker span {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem; color: rgba(255,255,255,0.48);
    letter-spacing: 0.02em;
}
.s15-edu-ticker strong { color: #5eff82; font-weight: 700; }
.s15-edu-ticker em { color: #ff6b5b; font-style: normal; font-weight: 700; }

/* ═══════════════════════════════════════════════════════════
   RESPONSIVE
   ═══════════════════════════════════════════════════════════ */

/* ── Tablet / small desktop (≤ 900px) ── */
@media (max-width: 900px) {
    .s15-card-player { font-size: 0.96rem; }
    .s15-card-prop { font-size: 0.76rem; padding: 5px 12px; }
    .s15-banner-logo { width: 140px; height: 140px; }
    .s15-banner-title { font-size: 1.8rem !important; }
}

/* ── Mobile landscape / large phones (≤ 720px) ── */
@media (max-width: 720px) {
    /* Hero */
    .s15-page-hero { padding: 32px 16px 14px; }
    .s15-page-hero h1 { font-size: 1.8rem; letter-spacing: 0.08em; }
    .s15-page-hero-sub { font-size: 0.82rem; margin-top: 12px; }

    /* Stats bar */
    .s15-page-stats { gap: 12px; padding: 8px 16px; font-size: 0.64rem; flex-wrap: wrap; justify-content: center; }

    /* Banner — stack logo + text vertically, center */
    .s15-banner-header { flex-direction: column; align-items: center; text-align: center; gap: 16px; }
    .s15-banner-logo { width: 110px; height: 110px; }
    .s15-banner-title { font-size: 1.35rem !important; letter-spacing: 0.12em !important; }
    .s15-banner-subtitle { max-width: 100%; text-align: center; }
    .s15-banner-inner { padding: 24px 18px 20px; }
    .s15-banner-metrics { flex-direction: column; gap: 10px; align-items: stretch; }
    .s15-count-block { padding: 14px 20px; }
    .s15-count-num { font-size: 2rem; }
    .s15-metric-pill { padding: 12px 18px; }
    .s15-dir-badge { justify-content: center; }

    /* Cards — 2-row layout on mobile: top row = rank + headshot + info, bottom row = prop + data + gauge */
    .s15-card-top {
        flex-wrap: wrap;
        gap: 10px;
        padding: 14px 16px;
    }
    .s15-rank { width: 34px; height: 34px; font-size: 0.64rem; border-radius: 10px; }
    .s15-headshot-wrap, .s15-card-headshot { width: 56px; height: 56px; }
    .s15-card-team-logo { width: 22px; height: 22px; }
    .s15-card-player { font-size: 0.92rem; }
    .s15-card-meta { font-size: 0.60rem; }
    .s15-card-tier { font-size: 0.46rem; padding: 2px 8px; }
    .s15-card-info { flex: 1 1 0; min-width: 120px; }
    /* Prop + data + gauge go to next row */
    .s15-card-prop {
        margin-left: 0;
        flex-basis: auto;
        font-size: 0.74rem;
        padding: 4px 10px;
        order: 10;
    }
    .s15-card-data {
        margin-left: 0;
        gap: 6px;
        order: 11;
    }
    .s15-data-chip { min-width: 44px; padding: 3px 8px; }
    .s15-data-chip-val { font-size: 0.74rem; }
    .s15-gauge-wrap {
        width: 46px; height: 46px;
        order: 12;
        margin-left: auto;
    }

    /* Education */
    .s15-edu { padding: 24px 18px 20px; }
    .s15-edu h2 { font-size: 1.2rem; letter-spacing: 0.08em; }
    .s15-edu-subtitle { font-size: 0.80rem; }
    .s15-edu-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .s15-edu-card { padding: 20px 16px; }
    .s15-edu-example { flex-direction: column; gap: 10px; }
}

/* ── Phones (≤ 480px) ── */
@media (max-width: 480px) {
    /* Hero */
    .s15-page-hero { padding: 24px 12px 10px; }
    .s15-page-hero h1 { font-size: 1.4rem; letter-spacing: 0.06em; }
    .s15-page-hero-sub { font-size: 0.76rem; line-height: 1.55; }
    .s15-page-stats { gap: 8px; padding: 6px 12px; font-size: 0.58rem; }

    /* Banner */
    .s15-banner { border-radius: 18px; }
    .s15-banner-inner { padding: 20px 14px 16px; }
    .s15-banner-logo { width: 90px; height: 90px; border-radius: 14px; }
    .s15-banner-title { font-size: 1.15rem !important; letter-spacing: 0.08em !important; }
    .s15-banner-subtitle { font-size: 0.72rem; }
    .s15-count-block { min-width: unset; padding: 12px 16px; }
    .s15-count-num { font-size: 1.6rem; }
    .s15-metric-pill { padding: 10px 14px; }
    .s15-metric-val { font-size: 1.1rem; }
    .s15-dir-badge { font-size: 0.62rem; padding: 8px 16px; }

    /* Cards — fully stacked */
    .s15-card { border-radius: 16px; margin-bottom: 10px; }
    .s15-card-top { padding: 12px 14px; gap: 8px; }
    .s15-rank { width: 30px; height: 30px; font-size: 0.58rem; border-radius: 8px; }
    .s15-headshot-wrap, .s15-card-headshot { width: 48px; height: 48px; }
    .s15-card-team-logo { width: 20px; height: 20px; bottom: -3px; right: -3px; }
    .s15-card-player { font-size: 0.84rem; }
    .s15-card-meta { font-size: 0.56rem; }
    .s15-card-tier { font-size: 0.42rem; padding: 2px 6px; letter-spacing: 0.10em; }
    .s15-card-info { min-width: 100px; }
    .s15-card-prop { font-size: 0.68rem; padding: 3px 8px; border-radius: 7px; }
    .s15-data-chip { min-width: 38px; padding: 2px 6px; }
    .s15-data-chip-val { font-size: 0.68rem; }
    .s15-data-chip-lbl { font-size: 0.36rem; }
    .s15-gauge-wrap { width: 40px; height: 40px; }
    .s15-gauge-text { font-size: 9px; }
    .s15-gauge-lbl { font-size: 4.5px; }

    /* Education */
    .s15-edu { padding: 20px 14px 16px; border-radius: 18px; }
    .s15-edu-badge { font-size: 0.48rem; padding: 4px 12px; }
    .s15-edu h2 { font-size: 1rem; letter-spacing: 0.06em; }
    .s15-edu-subtitle { font-size: 0.74rem; margin-bottom: 20px; }
    .s15-edu-grid { grid-template-columns: 1fr; gap: 10px; }
    .s15-edu-card { padding: 18px 14px; }
    .s15-edu-card-icon { font-size: 1.8rem; margin-bottom: 12px; }
    .s15-edu-card-title { font-size: 0.64rem; }
    .s15-edu-card-text { font-size: 0.70rem; }
    .s15-edu-example { padding: 12px 14px; border-radius: 12px; }
    .s15-edu-ticker span { font-size: 0.60rem; }

    /* Divider */
    .s15-divider { margin: 24px 0; }

    /* Empty state */
    .s15-empty { padding: 40px 16px; font-size: 0.86rem; border-radius: 16px; }
    .s15-empty-icon { font-size: 2rem; }
}

/* ── Ultra-narrow phones (≤ 360px) ── */
@media (max-width: 360px) {
    .s15-page-hero h1 { font-size: 1.15rem; letter-spacing: 0.04em; }
    .s15-page-hero-sub { font-size: 0.70rem; }
    .s15-banner-logo { width: 72px; height: 72px; }
    .s15-banner-title { font-size: 0.95rem !important; }
    .s15-card-top { padding: 10px 10px; gap: 6px; }
    .s15-rank { width: 26px; height: 26px; font-size: 0.50rem; }
    .s15-headshot-wrap, .s15-card-headshot { width: 40px; height: 40px; }
    .s15-card-player { font-size: 0.76rem; }
    .s15-card-prop { font-size: 0.60rem; }
    .s15-gauge-wrap { width: 36px; height: 36px; }
}

/* ═══════════════════════════════════════════════════════════
   STREAMLIT TAB OVERRIDES
   ═══════════════════════════════════════════════════════════ */

/* Tab bar container */
div[data-testid="stTabs"] > div[role="tablist"] {
    background: linear-gradient(135deg, rgba(6,10,18,0.92) 0%, rgba(12,20,32,0.88) 100%);
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 6px 8px;
    gap: 6px;
    margin-bottom: 24px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 4px 30px rgba(0,0,0,0.50), inset 0 1px 0 rgba(255,255,255,0.04);
    justify-content: center;
}

/* Remove the default bottom border Streamlit adds */
div[data-testid="stTabs"] > div[role="tablist"]::after {
    display: none !important;
}

/* Individual tab buttons */
div[data-testid="stTabs"] button[role="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.10em !important;
    text-transform: uppercase !important;
    color: rgba(255,255,255,0.40) !important;
    background: transparent !important;
    border: 1.5px solid rgba(255,255,255,0.06) !important;
    border-radius: 14px !important;
    padding: 12px 28px !important;
    margin: 0 !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative;
    cursor: pointer;
    white-space: nowrap;
}

/* Hover state */
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: rgba(255,255,255,0.75) !important;
    background: rgba(255,255,255,0.04) !important;
    border-color: rgba(255,255,255,0.16) !important;
    box-shadow: 0 0 20px rgba(94,255,130,0.08), 0 0 20px rgba(255,107,91,0.08);
    transform: translateY(-1px);
}

/* Active / selected tab  */
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #ffffff !important;
    background: linear-gradient(135deg, rgba(46,204,64,0.14) 0%, rgba(231,76,60,0.14) 100%) !important;
    border-color: rgba(94,255,130,0.35) !important;
    box-shadow:
        0 0 24px rgba(46,204,64,0.20),
        0 0 24px rgba(231,76,60,0.12),
        inset 0 1px 0 rgba(255,255,255,0.08) !important;
}

/* Active tab glow line at bottom */
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]::after {
    content: '';
    position: absolute;
    bottom: -1px; left: 12%; right: 12%;
    height: 2px;
    background: linear-gradient(90deg, rgba(46,204,64,0.60), rgba(255,255,255,0.20), rgba(231,76,60,0.60));
    border-radius: 2px;
    box-shadow: 0 0 10px rgba(94,255,130,0.40), 0 0 10px rgba(255,107,91,0.30);
}

/* Remove Streamlit default underline / highlight bar */
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    display: none !important;
}

/* Tab label text inside Streamlit's p tag */
div[data-testid="stTabs"] button[role="tab"] p {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.10em !important;
    text-transform: uppercase !important;
    color: inherit !important;
    margin: 0 !important;
    padding: 0 !important;
    white-space: nowrap !important;
}

/* Focus ring override */
div[data-testid="stTabs"] button[role="tab"]:focus {
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(94,255,130,0.25) !important;
}

/* Tab content panel — remove top gap */
div[data-testid="stTabs"] > div[data-testid="stTabContent"] {
    padding-top: 0 !important;
}

/* ── Tab responsive ── */
@media (max-width: 720px) {
    div[data-testid="stTabs"] > div[role="tablist"] {
        padding: 5px 6px;
        gap: 4px;
        border-radius: 16px;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        font-size: 0.62rem !important;
        letter-spacing: 0.06em !important;
        padding: 10px 14px !important;
        border-radius: 12px !important;
    }
}
@media (max-width: 480px) {
    div[data-testid="stTabs"] > div[role="tablist"] {
        flex-wrap: wrap;
        padding: 4px 5px;
        border-radius: 14px;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        font-size: 0.54rem !important;
        letter-spacing: 0.04em !important;
        padding: 8px 10px !important;
        border-radius: 10px !important;
        flex: 1 1 auto;
        text-align: center;
        justify-content: center;
    }
}

/* ── Full-page centering overrides ────────────────────────── */
[data-testid="stMainBlockContainer"] {
    max-width: 1100px !important;
    width: 100% !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
.s15-page-hero,
.s15-edu,
.s15-section-hdr {
    text-align: center !important;
    margin-left: auto !important;
    margin-right: auto !important;
}
</style>
"""


# ============================================================
# SECTION: Filtering helpers
# ============================================================


def _extract_iso_date(value) -> str:
    """Best-effort YYYY-MM-DD extraction from date/datetime-like values."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = raw.replace("/", "-")
    if "T" in raw:
        raw = raw.split("T", 1)[0]
    if " " in raw:
        raw = raw.split(" ", 1)[0]
    try:
        return datetime.date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return ""


def _is_today_game_prop(prop: dict, today_iso: str) -> bool:
    """True when a prop belongs to today's NBA/ET game slate."""
    game_iso = _extract_iso_date(prop.get("game_date") or prop.get("start_date") or prop.get("date"))
    return game_iso == today_iso


def _stat_season_avg(enriched: dict, stat_type: str) -> float:
    _pts = float(enriched.get("season_pts_avg", 0) or 0)
    _reb = float(enriched.get("season_reb_avg", 0) or 0)
    _ast = float(enriched.get("season_ast_avg", 0) or 0)
    _blk = float(enriched.get("season_blk_avg", 0) or 0)
    _stl = float(enriched.get("season_stl_avg", 0) or 0)
    _base = {
        "points": _pts,
        "rebounds": _reb,
        "assists": _ast,
        "threes": float(enriched.get("season_threes_avg", 0) or 0),
        "steals": _stl,
        "blocks": _blk,
        "turnovers": float(enriched.get("season_tov_avg", 0) or 0),
        "minutes": float(enriched.get("season_minutes_avg", 0) or 0),
        "ftm": float(enriched.get("season_ftm_avg", 0) or 0),
        "fga": float(enriched.get("season_fga_avg", 0) or 0),
        "fgm": float(enriched.get("season_fgm_avg", 0) or 0),
        "fta": float(enriched.get("season_fta_avg", 0) or 0),
        "offensive_rebounds": float(enriched.get("season_oreb_avg", 0) or 0),
        "defensive_rebounds": float(enriched.get("season_dreb_avg", 0) or 0),
        "personal_fouls": float(enriched.get("season_pf_avg", 0) or 0),
        "points_rebounds": _pts + _reb,
        "points_assists": _pts + _ast,
        "rebounds_assists": _reb + _ast,
        "points_rebounds_assists": _pts + _reb + _ast,
        "blocks_steals": _blk + _stl,
        "fantasy_score_pp": (
            _pts
            + 1.2 * _reb
            + 1.5 * _ast
            + 3.0 * (_stl + _blk)
            - float(enriched.get("season_tov_avg", 0) or 0)
        ),
    }
    return float(_base.get(stat_type, 0) or 0)


def _passes_smart_money_quality_gate(enriched: dict) -> bool:
    stat_type = str(enriched.get("stat_type", "") or "").lower().replace(" ", "_")
    season_minutes = float(enriched.get("season_minutes_avg", 0) or 0)
    if season_minutes < _SM_MIN_SEASON_MINUTES:
        return False
    season_avg = _stat_season_avg(enriched, stat_type)
    min_avg = float(_SM_MIN_STAT_AVG.get(stat_type, 0.0) or 0.0)
    if min_avg > 0 and season_avg < min_avg:
        return False
    return True

def _filter_zone_picks(all_props: list, players_data: dict,
                       odds_type: str, min_dev: float) -> list:
    """Filter props by odds_type and line_vs_avg_pct deviation.

    Returns enriched prop dicts sorted by deviation (most extreme first).
    Only OVER direction (line below avg → negative deviation).
    """
    results = []
    for p in all_props:
        if p.get("odds_type", "standard") != odds_type:
            continue
        enriched = enrich_prop_with_player_data(p, players_data)
        dev = float(enriched.get("line_vs_avg_pct", 0) or 0)
        # Only negative deviation (line below avg) → OVER opportunity
        if dev <= -min_dev:
            enriched.update({
                "player_name": p.get("player_name", ""),
                "stat_type": p.get("stat_type", ""),
                "line": float(p.get("line", 0)),
                "platform": p.get("platform", ""),
                "odds_type": p.get("odds_type", ""),
                "line_vs_avg_pct": dev,
            })
            if not _passes_smart_money_quality_gate(enriched):
                continue
            results.append(enriched)
    results.sort(key=lambda x: x.get("line_vs_avg_pct", 0))
    limited = []
    by_player = {}
    by_team = {}
    for pick in results:
        p_name = str(pick.get("player_name", "") or "").strip().lower()
        p_team = str(pick.get("player_team", pick.get("team", "")) or "").strip().upper()
        if by_player.get(p_name, 0) >= _SM_MAX_PICKS_PER_PLAYER:
            continue
        if by_team.get(p_team, 0) >= _SM_MAX_PICKS_PER_TEAM:
            continue
        limited.append(pick)
        by_player[p_name] = by_player.get(p_name, 0) + 1
        by_team[p_team] = by_team.get(p_team, 0) + 1
    return limited


# ============================================================
# SECTION: Render helpers
# ============================================================


def _render_education_section() -> str:
    """Build the educational Intelligence Briefing section."""
    return (
        '<div class="s15-edu">'
        '<div class="s15-edu-inner">'
        # Badge
        '<div class="s15-edu-badge">'
        '<span class="s15-edu-badge-dot"></span>'
        'INTELLIGENCE BRIEFING'
        '</div>'
        # Title
        '<h2>How Smart Money Bets Work</h2>'
        '<p class="s15-edu-subtitle">'
        'Our system scans every PrizePicks prop in real-time, comparing alt-lines '
        'against actual season production. When a line drops dramatically below '
        'what a player actually averages, we flag it as a high-value OVER opportunity.'
        '</p>'
        # Grid
        '<div class="s15-edu-grid">'
        # Card 1 — The Edge
        '<div class="s15-edu-card s15-edu-card-blue">'
        '<span class="s15-edu-card-icon">\U0001f4ca</span>'
        '<h3 class="s15-edu-card-title">The Edge</h3>'
        '<p class="s15-edu-card-text">'
        'PrizePicks offers special alt-lines&mdash;Goblin &amp; Demon odds&mdash;that '
        'are set significantly lower than standard props. Our AI detects when these '
        'lines create a <strong>mathematical edge</strong> for the OVER.'
        '</p></div>'
        # Card 2 — Easy Money (Goblin)
        '<div class="s15-edu-card s15-edu-card-green">'
        '<span class="s15-edu-card-icon">\U0001f4b0</span>'
        '<h3 class="s15-edu-card-title">Easy Money</h3>'
        '<p class="s15-edu-card-text">'
        'Goblin lines that drop <strong>50&ndash;100%</strong> below the player\'s '
        'season average. These are the safest OVER bets on the board&mdash;the book '
        'is practically handing you free money.'
        '</p></div>'
        # Card 3 — Smart Risk (Demon)
        '<div class="s15-edu-card s15-edu-card-red">'
        '<span class="s15-edu-card-icon">\U0001f525</span>'
        '<h3 class="s15-edu-card-title">Smart Risk</h3>'
        '<p class="s15-edu-card-text">'
        'Demon lines <strong>30&ndash;100%</strong> below average. Higher reward '
        'potential, but the book prices them riskier. Still mathematically '
        'favored based on recent production.'
        '</p></div>'
        # Card 4 — How to Read
        '<div class="s15-edu-card s15-edu-card-gold">'
        '<span class="s15-edu-card-icon">\U0001f3af</span>'
        '<h3 class="s15-edu-card-title">Reading the Cards</h3>'
        '<p class="s15-edu-card-text">'
        '<strong>GAP%</strong> = how far below average the line sits. '
        '<strong>AVG</strong> = player\'s season number. '
        '<strong>LINE</strong> = the book\'s prop number. '
        'Higher GAP% = better edge.'
        '</p></div>'
        '</div>'
        # Scrolling ticker
        '<div class="s15-edu-example">'
        '<span class="s15-edu-example-label">\u26a1 PRO TIPS</span>'
        '<div class="s15-edu-ticker-wrap"><div class="s15-edu-ticker">'
        '<span>\u26a1 GAP% measures how far below the season average the line is set</span>'
        '<span>\U0001f4b0 Higher GAP% = more value &mdash; look for <strong>-60%</strong> or higher</span>'
        '<span>\U0001f3af OVER ONLY &mdash; we always bet the over on lowered lines</span>'
        '<span>\U0001f4ca Example: <strong>Line 12.5</strong> PTS vs <strong>AVG 25.2</strong> PTS = <em>-50.4% GAP</em></span>'
        '<span>\U0001f525 Demon lines are riskier but offer bigger payout potential</span>'
        '<span>\U0001f48e Easy Money signals have 50%+ gap &mdash; the book is giving it away</span>'
        '<span>\u26a1 GAP% measures how far below the season average the line is set</span>'
        '<span>\U0001f4b0 Higher GAP% = more value &mdash; look for <strong>-60%</strong> or higher</span>'
        '<span>\U0001f3af OVER ONLY &mdash; we always bet the over on lowered lines</span>'
        '<span>\U0001f4ca Example: <strong>Line 12.5</strong> PTS vs <strong>AVG 25.2</strong> PTS = <em>-50.4% GAP</em></span>'
        '<span>\U0001f525 Demon lines are riskier but offer bigger payout potential</span>'
        '<span>\U0001f48e Easy Money signals have 50%+ gap &mdash; the book is giving it away</span>'
        '</div></div></div>'
        '</div></div>'
    )

def _render_banner(title: str, subtitle: str, logo_b64: str,
                   css_class: str, picks: list) -> str:
    """Build the section banner HTML with premium holographic layout."""
    total = len(picks)
    devs = [abs(p.get("line_vs_avg_pct", 0)) for p in picks]
    avg_dev = sum(devs) / total if total else 0
    peak_dev = max(devs) if devs else 0

    logo_html = (
        f'<img class="s15-banner-logo" '
        f'src="data:image/png;base64,{logo_b64}" alt="{_html.escape(title)}">'
        if logo_b64 else ""
    )

    return (
        f'<div class="s15-banner {css_class}">'
        f'<div class="s15-banner-scan"></div>'
        f'<div class="s15-banner-inner">'
        f'<div class="s15-banner-header">'
        f'{logo_html}'
        f'<div>'
        f'<h2 class="s15-banner-title">{_html.escape(title)}</h2>'
        f'<p class="s15-banner-subtitle">{_html.escape(subtitle)}</p>'
        f'</div>'
        f'</div>'
        f'<div class="s15-banner-metrics">'
        # Count block
        f'<div class="s15-count-block">'
        f'<span class="s15-count-num">{total}</span>'
        f'<span class="s15-count-lbl">SIGNALS</span>'
        f'</div>'
        # Avg gap pill
        f'<div class="s15-metric-pill">'
        f'<span class="s15-metric-val">{avg_dev:.1f}%</span>'
        f'<span class="s15-metric-lbl">AVG GAP</span>'
        f'</div>'
        # Peak pill
        f'<div class="s15-metric-pill">'
        f'<span class="s15-metric-val">{peak_dev:.1f}%</span>'
        f'<span class="s15-metric-lbl">PEAK</span>'
        f'</div>'
        # Direction badge
        f'<div class="s15-dir-badge">'
        f'<span class="s15-dir-arrow">▲</span>'
        f'OVER ONLY'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_card(pick: dict, card_class: str, rank: int) -> str:
    """Build a premium 2-row pick card with edge tier, stat bars, and SVG gauge."""
    player = _html.escape(pick.get("player_name", "Unknown"))
    stat_raw = pick.get("stat_type", "")
    stat = _html.escape(_display_stat_name(stat_raw))
    team = _html.escape(str(pick.get("player_team", pick.get("team", ""))))
    platform = _html.escape(pick.get("platform", ""))
    line = pick.get("line", 0)
    dev = abs(pick.get("line_vs_avg_pct", 0))

    # Season avg
    season_avg = 0
    _stat_avg_keys = {
        "points": "season_pts_avg", "rebounds": "season_reb_avg",
        "assists": "season_ast_avg", "threes": "season_threes_avg",
        "steals": "season_stl_avg", "blocks": "season_blk_avg",
        "turnovers": "season_tov_avg", "minutes": "season_minutes_avg",
        "ftm": "season_ftm_avg", "fga": "season_fga_avg",
        "fgm": "season_fgm_avg", "fta": "season_fta_avg",
        "offensive_rebounds": "season_oreb_avg", "defensive_rebounds": "season_dreb_avg",
        "personal_fouls": "season_pf_avg",
        "points_rebounds": "season_pts_reb_avg", "points_assists": "season_pts_ast_avg",
        "rebounds_assists": "season_reb_ast_avg",
        "points_rebounds_assists": "season_pra_avg", "blocks_steals": "season_blk_stl_avg",
    }
    avg_key = _stat_avg_keys.get(stat_raw.lower().replace(" ", "_"), "")
    if avg_key:
        try:
            season_avg = float(pick.get(avg_key, 0) or 0)
        except (ValueError, TypeError):
            season_avg = 0
    avg_display = f"{season_avg:.1f}" if season_avg > 0 else "\u2014"

    # Edge tier label
    if dev >= 80:
        tier_label = "ELITE EDGE"
    elif dev >= 65:
        tier_label = "PREMIUM EDGE"
    elif dev >= 50:
        tier_label = "STRONG EDGE"
    else:
        tier_label = "EDGE DETECTED"

    # Headshot
    player_name_raw = pick.get("player_name", "")
    headshot_url = get_headshot_url(player_name_raw) if player_name_raw else ""
    headshot_html = (
        f'<img class="s15-card-headshot" '
        f'src="{_html.escape(headshot_url)}" '
        f'alt="{player}" loading="lazy">'
        if headshot_url else
        '<div class="s15-card-headshot"></div>'
    )

    # Team logo
    team_raw = str(pick.get("player_team", pick.get("team", "")))
    team_logo_url = get_team_logo_url(team_raw) if team_raw else ""
    team_logo_html = (
        f'<img class="s15-card-team-logo" '
        f'src="{_html.escape(team_logo_url)}" alt="{team}" loading="lazy">'
        if team_logo_url else ""
    )

    # SVG gauge (r=36, circumference=226)
    circumference = 226
    gauge_pct = min(dev, 100) / 100
    dash_offset = circumference * (1 - gauge_pct)

    delay = f' style="animation-delay:{rank * 0.07:.2f}s;"'

    return (
        f'<div class="s15-card {card_class}"{delay}>'
        f'<div class="s15-card-synapse"></div>'
        # ─── Single row: rank + headshot + info + prop + data chips + gauge ───
        f'<div class="s15-card-top">'
        f'<div class="s15-rank">#{rank + 1}</div>'
        f'<div class="s15-headshot-wrap">'
        f'{headshot_html}'
        f'{team_logo_html}'
        f'</div>'
        f'<div class="s15-card-info">'
        f'<div class="s15-card-player">{player}</div>'
        f'<div class="s15-card-meta">{team} \u00b7 {platform}</div>'
        f'<div class="s15-card-tier"><span class="s15-tier-dot"></span>{tier_label}</div>'
        f'</div>'
        f'<div class="s15-card-prop"><span class="s15-prop-dir">\u25b2</span> OVER {line:g} {stat}</div>'
        f'<div class="s15-card-data">'
        f'<div class="s15-data-chip">'
        f'<span class="s15-data-chip-val">{avg_display}</span>'
        f'<span class="s15-data-chip-lbl">AVG</span>'
        f'</div>'
        f'<div class="s15-data-chip">'
        f'<span class="s15-data-chip-val">{line:g}</span>'
        f'<span class="s15-data-chip-lbl">LINE</span>'
        f'</div>'
        f'</div>'
        # Compact SVG Gauge
        f'<div class="s15-gauge-wrap">'
        f'<svg class="s15-gauge-svg" viewBox="0 0 80 80">'
        f'<circle class="s15-gauge-bg" cx="40" cy="40" r="36"/>'
        f'<circle class="s15-gauge-ring" cx="40" cy="40" r="36" '
        f'stroke-dasharray="{circumference}" '
        f'stroke-dashoffset="{dash_offset:.1f}"/>'
        f'<text class="s15-gauge-text" x="40" y="36">-{dev:.0f}%</text>'
        f'<text class="s15-gauge-lbl" x="40" y="50">GAP</text>'
        f'</svg>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


# ============================================================
# SECTION: Page content
# ============================================================

st.markdown(_PAGE_CSS, unsafe_allow_html=True)

# Neural network matrix — static SVG background + animated overlays
st.markdown(_NEURAL_BG_CSS, unsafe_allow_html=True)
st.markdown(_NEURAL_ANIM_HTML, unsafe_allow_html=True)

# ── Custom hero title (replaces st.title) ─────────────────────
st.markdown(
    '<div class="s15-page-hero">'
    '<h1>Smart Money Bets</h1>'
    '<p class="s15-page-hero-sub">'
    'Real-time AI scanning of <strong>every PrizePicks alt-line</strong> &mdash; '
    'instantly flagging extreme-value OVER opportunities where the book '
    'has set lines <strong>dramatically below</strong> actual player '
    'production. Powered by live data, season stats, and edge detection.'
    '</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Education / Intelligence Briefing ───────────────────────
st.markdown(_render_education_section(), unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────
with st.spinner("Fetching live PrizePicks props…"):
    all_props = fetch_prizepicks_props()
    players_data = load_players_data()

try:
    from tracking.bet_tracker import _nba_today_et
    _today_str = _nba_today_et().isoformat()
except Exception:
    _today_str = datetime.date.today().isoformat()

all_props = [p for p in all_props if _is_today_game_prop(p, _today_str)]

total_goblin = sum(1 for p in all_props if p.get("odds_type") == "goblin")
total_demon = sum(1 for p in all_props if p.get("odds_type") == "demon")

st.markdown(
    f'<div style="text-align:center;">'
    f'<div class="s15-page-stats">'
    f'<span><strong>{len(all_props):,}</strong> total props</span>'
    f'<span><strong>{total_goblin:,}</strong> goblin</span>'
    f'<span><strong>{total_demon:,}</strong> demon</span>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ── Filter picks ──────────────────────────────────────────────
easy_money_picks = _filter_zone_picks(all_props, players_data, "goblin", _EASY_MONEY_MIN_DEV)
smart_risk_picks = _filter_zone_picks(all_props, players_data, "demon", _SMART_RISK_MIN_DEV)

# ── Auto-log Smart Money picks to Bet Tracker ─────────────────
# Sync every page load so today's tracker rows always mirror today's slate.
import sqlite3 as _sqlite3
from tracking.database import DB_FILE_PATH as _DB_PATH

# Keep Smart Money auto-logs synced to today's slate only.
# This clears stale pending rows (including future-game leftovers logged as today)
# and then rehydrates from the current today-only slate.
_sync_ok = False
for _attempt in range(3):
    try:
        with _sqlite3.connect(str(_DB_PATH), timeout=30) as _conn:
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute(
                "DELETE FROM bets "
                "WHERE bet_date = ? "
                "AND auto_logged = 1 "
                "AND platform = 'Smart Money' "
                "AND (bet_type IN ('goblin', 'demon') OR notes LIKE 'Smart Money %') "
                "AND (result IS NULL OR result = '')",
                (_today_str,),
            )
            _conn.commit()
        _sync_ok = True
        break
    except Exception:
        _time.sleep(0.25 * (2 ** _attempt))

_existing: set = set()
if _sync_ok:
    try:
        with _sqlite3.connect(str(_DB_PATH), timeout=30) as _conn:
            _rows = _conn.execute(
                "SELECT player_name, stat_type, prop_line, direction "
                "FROM bets WHERE bet_date = ?",
                (_today_str,),
            ).fetchall()
        _existing = {
            (r[0].lower(), r[1], float(r[2] or 0), r[3]) for r in _rows
        }
    except Exception:
        _existing = set()

_sm_logged = 0
for _pick in easy_money_picks + smart_risk_picks:
    # Safety gate: never log Smart Money props for non-today game dates.
    if not _is_today_game_prop(_pick, _today_str):
        continue
    _p_name = _pick.get("player_name", "")
    _p_stat = (_pick.get("stat_type", "") or "").lower().replace(" ", "_")
    _p_line = float(_pick.get("line", 0))
    _p_dir = "OVER"
    _dk = (_p_name.lower(), _p_stat, _p_line, _p_dir)
    if _dk in _existing:
        continue
    _dev = abs(_pick.get("line_vs_avg_pct", 0))
    _bt = _pick.get("odds_type", "goblin")
    _tier = "Platinum" if _dev >= 80 else "Gold" if _dev >= 65 else "Silver" if _dev >= 50 else "Bronze"
    _conf = min(99.0, 50 + _dev * 0.5)
    _prob = min(0.99, 0.5 + _dev / 200)
    ok, _ = log_new_bet(
        player_name=_p_name,
        stat_type=_p_stat,
        prop_line=_p_line,
        direction=_p_dir,
        platform="Smart Money",
        confidence_score=_conf,
        probability_over=_prob,
        edge_percentage=_dev,
        tier=_tier,
        team=str(_pick.get("player_team", _pick.get("team", ""))),
        notes=f"Smart Money {_bt.title()} | GAP: -{_dev:.1f}%",
        auto_logged=1,
        bet_type=_bt,
        std_devs_from_line=_dev / 15.0,
    )
    if ok:
        _existing.add(_dk)
        _sm_logged += 1


# ============================================================
# TABBED SECTIONS — Easy Money / Smart Risk / Both
# ============================================================

tab_easy, tab_risk, tab_all = st.tabs([
    f"\U0001f4b0 Easy Money ({len(easy_money_picks)})",
    f"\U0001f525 Smart Risk ({len(smart_risk_picks)})",
    f"\U0001f4ca All Signals ({len(easy_money_picks) + len(smart_risk_picks)})",
])

with tab_easy:
    st.markdown('<div class="s15-divider s15-divider-goblin"></div>', unsafe_allow_html=True)
    banner_html = _render_banner(
        title="EASY MONEY",
        subtitle=f"Goblin lines {_EASY_MONEY_MIN_DEV:.0f}\u2013100% below season average. The book is practically handing you free money. Every signal below is a statistically favored OVER.",
        logo_b64=_GOBLIN_B64,
        css_class="s15-banner-goblin",
        picks=easy_money_picks,
    )
    st.markdown(banner_html, unsafe_allow_html=True)
    if easy_money_picks:
        for i, pick in enumerate(easy_money_picks):
            st.markdown(
                _render_card(pick, "s15-card-goblin", i),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="s15-empty">'
            '<span class="s15-empty-icon">\U0001f4b0</span>'
            'No Easy Money signals right now &mdash; '
            'check back when more goblin lines drop.</div>',
            unsafe_allow_html=True,
        )

with tab_risk:
    st.markdown('<div class="s15-divider s15-divider-demon"></div>', unsafe_allow_html=True)
    banner_html = _render_banner(
        title="SMART RISK",
        subtitle=f"Demon lines {_SMART_RISK_MIN_DEV:.0f}\u2013100% below season average. Higher reward, higher risk \u2014 but the math says these OVERs still have edge.",
        logo_b64=_DEMON_B64,
        css_class="s15-banner-demon",
        picks=smart_risk_picks,
    )
    st.markdown(banner_html, unsafe_allow_html=True)
    if smart_risk_picks:
        for i, pick in enumerate(smart_risk_picks):
            st.markdown(
                _render_card(pick, "s15-card-demon", i),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="s15-empty">'
            '<span class="s15-empty-icon">\U0001f525</span>'
            'No Smart Risk signals right now &mdash; '
            'check back when more demon lines drop.</div>',
            unsafe_allow_html=True,
        )

with tab_all:
    # ── Easy Money section ──
    st.markdown('<div class="s15-divider s15-divider-goblin"></div>', unsafe_allow_html=True)
    banner_html = _render_banner(
        title="EASY MONEY",
        subtitle=f"Goblin lines {_EASY_MONEY_MIN_DEV:.0f}\u2013100% below season average.",
        logo_b64=_GOBLIN_B64,
        css_class="s15-banner-goblin",
        picks=easy_money_picks,
    )
    st.markdown(banner_html, unsafe_allow_html=True)
    if easy_money_picks:
        for i, pick in enumerate(easy_money_picks):
            st.markdown(
                _render_card(pick, "s15-card-goblin", i),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="s15-empty">'
            '<span class="s15-empty-icon">\U0001f4b0</span>'
            'No Easy Money signals right now.</div>',
            unsafe_allow_html=True,
        )
    # ── Smart Risk section ──
    st.markdown('<div class="s15-divider s15-divider-demon"></div>', unsafe_allow_html=True)
    banner_html = _render_banner(
        title="SMART RISK",
        subtitle=f"Demon lines {_SMART_RISK_MIN_DEV:.0f}\u2013100% below season average.",
        logo_b64=_DEMON_B64,
        css_class="s15-banner-demon",
        picks=smart_risk_picks,
    )
    st.markdown(banner_html, unsafe_allow_html=True)
    if smart_risk_picks:
        for i, pick in enumerate(smart_risk_picks):
            st.markdown(
                _render_card(pick, "s15-card-demon", i),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="s15-empty">'
            '<span class="s15-empty-icon">\U0001f525</span>'
            'No Smart Risk signals right now.</div>',
            unsafe_allow_html=True,
        )
