# ============================================================
# FILE: Smart_Picks_Pro_Home.py
# PURPOSE: Main entry point for the SmartBetPro NBA Streamlit app.
#          Professional dark-themed landing page that sells outcomes,
#          guards the process, and converts first-time visitors.
# HOW TO RUN: streamlit run Smart_Picks_Pro_Home.py
# ============================================================

import streamlit as st
import datetime
import os
import base64
import logging

from data.data_manager import load_players_data, load_props_data, load_teams_data
from data.nba_data_service import load_last_updated
from tracking.database import initialize_database, load_user_settings, load_page_state
from styles.theme import get_global_css, get_quantum_card_matrix_css as _get_qcm_css
from pages.helpers.quantum_analysis_helpers import (
    QEG_EDGE_THRESHOLD as _QEG_EDGE_THRESHOLD,
    render_quantum_edge_gap_banner_html as _render_edge_gap_banner_html,
    render_quantum_edge_gap_grouped_html as _render_edge_gap_grouped_html,
    deduplicate_qeg_picks as _deduplicate_qeg_picks,
    filter_qeg_picks as _filter_qeg_picks,
    render_hero_section_html as _render_hero_section_html,
)

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="Smart Pick Pro Home",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="auto",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── Landing Page Theme CSS — page-level overrides ───────────
st.markdown("""
<style>

/* ===========================================================

   SMART PICK PRO â€” LANDING PAGE CSS

   PrizePicks + DraftKings Pick 6 AI Style  (Phase 1)

   =========================================================== */



/* â”€â”€ Landing Page Animations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

@keyframes lpFadeInUp   { from{ opacity:0; transform:translateY(28px); } to{ opacity:1; transform:translateY(0); } }

@keyframes lpSlideInLeft{ from{ opacity:0; transform:translateX(-24px); } to{ opacity:1; transform:translateX(0); } }

@keyframes lpOrbFloat  { 0%,100%{ transform:translate(0,0) scale(1); } 25%{ transform:translate(20px,-14px) scale(1.06); } 75%{ transform:translate(-18px,10px) scale(0.97); } }

@keyframes lpOrbFloat2 { 0%,100%{ transform:translate(0,0) scale(1); } 33%{ transform:translate(-28px,16px) scale(1.08); } 66%{ transform:translate(14px,-22px) scale(0.94); } }

@keyframes lpGradShift  { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }

@keyframes lpScanLine   { 0%{ top:-2px; } 100%{ top:100%; } }

@keyframes lpConnFlow   { 0%{ background-position:-200% 0; } 100%{ background-position:200% 0; } }

@keyframes lpSubtleFloat{ 0%,100%{ transform:translateY(0); } 50%{ transform:translateY(-5px); } }

@keyframes lpCheckBounce{ 0%{ transform:scale(0); } 50%{ transform:scale(1.2); } 100%{ transform:scale(1); } }



/* Staggered entrance helpers */

.lp-anim    { animation: lpFadeInUp 0.65s cubic-bezier(0.22,1,0.36,1) both; }

.lp-anim-d1 { animation-delay: 0.10s; }

.lp-anim-d2 { animation-delay: 0.20s; }

.lp-anim-d3 { animation-delay: 0.30s; }

.lp-anim-d4 { animation-delay: 0.40s; }

.lp-anim-d5 { animation-delay: 0.50s; }

.lp-anim-d6 { animation-delay: 0.60s; }



/* â”€â”€ Ambient Floating Orbs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.lp-orbs-container {

    position: fixed; top:0; left:0; width:100%; height:100vh;

    pointer-events:none; z-index:0; overflow:hidden;

}

.lp-orb { position:absolute; border-radius:50%; filter:blur(90px); opacity:0.06; }

.lp-orb-1 {

    width:420px; height:420px;

    background: radial-gradient(circle, #00D559 0%, transparent 70%);

    top:-100px; right:-60px;

    animation: lpOrbFloat 22s ease-in-out infinite;

}

.lp-orb-2 {

    width:360px; height:360px;

    background: radial-gradient(circle, #2D9EFF 0%, transparent 70%);

    bottom:8%; left:-80px;

    animation: lpOrbFloat2 28s ease-in-out infinite;

}

.lp-orb-3 {

    width:300px; height:300px;

    background: radial-gradient(circle, #F9C62B 0%, transparent 70%);

    top:42%; right:12%;

    animation: lpOrbFloat 32s ease-in-out infinite reverse;

    opacity: 0.04;

}



/* â”€â”€ Gradient Divider â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.lp-divider {

    height: 1px;

    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.20) 20%, rgba(45,158,255,0.16) 50%, rgba(249,198,43,0.12) 80%, transparent);

    border: none;

    margin: 36px 0;

    position: relative;

}

.lp-divider::after {

    content: '';

    position: absolute; top:-1px; left:50%; transform:translateX(-50%);

    width:6px; height:3px; background:#00D559; border-radius:2px;

    box-shadow: 0 0 8px rgba(0,213,89,0.5);

}



/* â”€â”€ Hero HUD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.hero-hud {

    background: linear-gradient(135deg, rgba(22,27,39,0.80) 0%, rgba(13,15,20,0.90) 100%);

    backdrop-filter: blur(28px) saturate(1.2);

    -webkit-backdrop-filter: blur(28px) saturate(1.2);

    border: 1px solid rgba(255,255,255,0.08);

    border-radius: 20px;

    padding: 40px 48px;

    margin-bottom: 16px;

    box-shadow: 0 20px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06);

    position: relative; overflow: hidden;

    display: flex; align-items: center; gap: 32px;

}

.hero-hud::before {

    content: '';

    position: absolute; top:0; left:0; right:0; height:3px;

    background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);

    background-size: 300% 100%;

    animation: lpGradShift 6s ease infinite;

}

.hero-hud::after {

    content: '';

    position: absolute; left:0; right:0; height:2px;

    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.06), transparent);

    animation: lpScanLine 5s linear infinite;

    pointer-events: none;

}

.hero-hud-inner-glow {

    position: absolute; top:0; left:0; right:0; bottom:0;

    background:

        radial-gradient(ellipse at 20% 50%, rgba(0,213,89,0.04) 0%, transparent 60%),

        radial-gradient(ellipse at 80% 50%, rgba(45,158,255,0.03) 0%, transparent 60%);

    pointer-events: none;

}

.hero-hud-text { flex:1; min-width:0; position:relative; z-index:1; }

.hero-tagline {

    font-size: clamp(1.5rem, 3vw, 2.4rem);

    font-weight: 900;

    font-family: 'Inter', sans-serif;

    background: linear-gradient(135deg, #FFFFFF 0%, #00D559 40%, #2D9EFF 70%, #F9C62B 100%);

    background-size: 200% 200%;

    -webkit-background-clip: text;

    -webkit-text-fill-color: transparent;

    background-clip: text;

    animation: lpGradShift 8s ease infinite;

    letter-spacing: -0.01em;

    margin: 0; line-height: 1.2;

}

.hero-subtext {

    font-size: clamp(0.9rem, 1.4vw, 1.05rem);

    color: rgba(255,255,255,0.82);

    font-family: 'Inter', sans-serif;

    letter-spacing: 0.01em;

    margin-top: 12px; line-height: 1.6;

}

.hero-subtext strong { color: #00D559; font-weight: 700; }

.hero-date {

    font-size: 0.80rem;

    color: rgba(107,122,154,0.85);

    margin-top: 12px;

    font-family: 'JetBrains Mono', monospace;

    font-variant-numeric: tabular-nums;

    letter-spacing: 0.03em;

}

.hero-date .game-count-live { color: #00D559; font-weight: 600; }

@media (max-width: 640px) {

    .hero-hud { flex-direction: column; text-align: center; padding: 28px 22px; gap: 20px; }

    .hero-tagline { font-size: 1.3rem; }

}



/* â”€â”€ Section Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.section-header {

    font-size: 1.1rem;

    font-weight: 800;

    font-family: 'Inter', sans-serif;

    color: #FFFFFF;

    letter-spacing: -0.01em;

    margin: 32px 0 16px;

    display: flex; align-items: center; gap: 10px;

}

.section-header::after {

    content: '';

    flex: 1; height: 1px;

    background: linear-gradient(90deg, rgba(0,213,89,0.22), transparent);

}



/* â”€â”€ Status Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.status-card {

    background: #161B27;

    border: 1px solid rgba(255,255,255,0.07);

    border-radius: 14px;

    padding: 20px 22px;

    text-align: center;

    box-shadow: 0 2px 14px rgba(0,0,0,0.35);

    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;

    position: relative; overflow: hidden;

}

.status-card::before {

    content: '';

    position: absolute; top:0; left:0; right:0; height:2px;

    background: linear-gradient(90deg, #00D559, #2D9EFF);

    opacity: 0; transition: opacity 0.25s ease;

}

.status-card:hover::before { opacity: 1; }

.status-card:hover {

    border-color: rgba(0,213,89,0.24);

    transform: translateY(-4px);

    box-shadow: 0 6px 24px rgba(0,213,89,0.10), 0 10px 30px rgba(0,0,0,0.45);

}

.status-card-value {

    font-size: 2.2rem; font-weight: 900; color: #FFFFFF;

    font-family: 'Bebas Neue', 'Inter', sans-serif;

    font-variant-numeric: tabular-nums;

}

.status-card-label {

    font-size: 0.72rem; color: #6B7A9A;

    text-transform: uppercase; letter-spacing: 1.2px;

    margin-top: 6px; font-weight: 600;

}



/* â”€â”€ Pillar Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.pillar-card {

    background: #161B27;

    border: 1px solid rgba(255,255,255,0.07);

    border-radius: 16px;

    padding: 24px 22px;

    height: 100%;

    box-shadow: 0 4px 18px rgba(0,0,0,0.35);

    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;

    position: relative; overflow: hidden;

    display: flex; flex-direction: column; gap: 10px;

}

.pillar-card::before {

    content: '';

    position: absolute; top:0; left:0; right:0; height:2px;

    background: linear-gradient(90deg, #00D559, #2D9EFF);

    opacity: 0; transition: opacity 0.25s ease;

}

.pillar-card:hover::before { opacity: 1; }

.pillar-card:hover {

    border-color: rgba(0,213,89,0.22);

    transform: translateY(-4px);

    box-shadow: 0 8px 28px rgba(0,213,89,0.08), 0 12px 36px rgba(0,0,0,0.45);

}

.pillar-icon {

    font-size: 1.8rem;

    width: 52px; height: 52px;

    display: flex; align-items: center; justify-content: center;

    background: rgba(0,213,89,0.08);

    border-radius: 14px;

    border: 1px solid rgba(0,213,89,0.18);

    flex-shrink: 0;

}

.pillar-title { font-size: 1.0rem; font-weight: 800; color: #FFFFFF; font-family: 'Inter', sans-serif; }

.pillar-body  { font-size: 0.84rem; color: #A0AABE; line-height: 1.55; }



/* â”€â”€ Proof Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.proof-card {

    background: #161B27;

    border: 1px solid rgba(255,255,255,0.07);

    border-radius: 14px;

    padding: 20px 22px;

    text-align: center;

    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;

    box-shadow: 0 2px 12px rgba(0,0,0,0.3);

}

.proof-card:hover {

    border-color: rgba(249,198,43,0.28);

    transform: translateY(-3px);

    box-shadow: 0 6px 24px rgba(249,198,43,0.08), 0 8px 28px rgba(0,0,0,0.4);

}

.proof-card-number {

    font-size: 2.4rem; font-weight: 900;

    font-family: 'Bebas Neue', 'Inter', sans-serif;

    color: #F9C62B;

    font-variant-numeric: tabular-nums; line-height: 1;

}

.proof-card-label { font-size: 0.72rem; color: #6B7A9A; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; font-weight: 600; }



/* â”€â”€ Pipeline / AI Steps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.pipeline-step {

    background: #161B27;

    border: 1px solid rgba(255,255,255,0.07);

    border-radius: 14px;

    padding: 18px 20px;

    display: flex; gap: 14px; align-items: flex-start;

    box-shadow: 0 2px 12px rgba(0,0,0,0.3);

    transition: border-color 0.22s ease, transform 0.22s ease;

    position: relative; overflow: hidden;

}

.pipeline-step::before {

    content: '';

    position: absolute; top:0; left:0; bottom:0; width:3px;

    background: linear-gradient(180deg, #00D559, #2D9EFF);

    opacity: 0.55;

}

.pipeline-step:hover { border-color: rgba(0,213,89,0.22); transform: translateX(3px); }

.pipeline-step-num   { font-family: 'Bebas Neue', 'Inter', sans-serif; font-size: 1.6rem; font-weight: 900; color: #00D559; line-height: 1; flex-shrink: 0; width: 32px; }

.pipeline-step-title { font-size: 0.92rem; font-weight: 700; color: #FFFFFF; }

.pipeline-step-body  { font-size: 0.80rem; color: #A0AABE; margin-top: 3px; line-height: 1.5; }



/* â”€â”€ Connector animated line â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.lp-connector {

    height: 2px;

    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.35), #2D9EFF, rgba(0,213,89,0.35), transparent);

    background-size: 200% 100%;

    animation: lpConnFlow 2.5s linear infinite;

    border-radius: 100px; margin: 4px 0;

}



/* â”€â”€ Matchup Chip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.matchup-chip {

    background: #161B27;

    border: 1px solid rgba(255,255,255,0.07);

    border-radius: 12px;

    padding: 10px 16px;

    font-size: 0.82rem; color: #A0AABE;

    transition: border-color 0.2s ease, background 0.2s ease;

}

.matchup-chip:hover { border-color: rgba(0,213,89,0.22); background: #1C2232; }

.matchup-vs { color: #6B7A9A; font-size: 0.72rem; margin: 0 4px; }



/* â”€â”€ Navigation Cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.nav-card {

    background: #161B27;

    border: 1px solid rgba(255,255,255,0.07);

    border-radius: 16px;

    padding: 22px 20px;

    text-align: center;

    box-shadow: 0 4px 16px rgba(0,0,0,0.35);

    transition: border-color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;

    cursor: pointer; text-decoration: none;

    display: block; height: 100%;

    position: relative; overflow: hidden;

}

.nav-card::before {

    content: '';

    position: absolute; top:0; left:0; right:0; height:2px;

    background: linear-gradient(90deg, #00D559, #2D9EFF);

    opacity: 0; transition: opacity 0.22s ease;

}

.nav-card:hover::before { opacity: 1; }

.nav-card:hover {

    border-color: rgba(0,213,89,0.28);

    transform: translateY(-5px);

    box-shadow: 0 8px 28px rgba(0,213,89,0.10), 0 12px 36px rgba(0,0,0,0.45);

}

.nav-card-icon  { font-size: 1.8rem; margin-bottom: 10px; display: block; filter: drop-shadow(0 0 8px rgba(0,213,89,0.25)); }

.nav-card-title { font-size: 0.96rem; font-weight: 800; color: #FFFFFF; font-family: 'Inter', sans-serif; }

.nav-card-desc  { font-size: 0.78rem; color: #6B7A9A; margin-top: 5px; line-height: 1.45; }



/* â”€â”€ Team chips + badges (LP override) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.team-chip {

    display: inline-block;

    background: rgba(45,158,255,0.08); color: rgba(255,255,255,0.90);

    border: 1px solid rgba(255,255,255,0.08);

    padding: 3px 10px; border-radius: 100px;

    font-size: 0.83rem; font-weight: 600; margin: 3px;

    transition: border-color 0.2s ease;

}

.team-chip:hover { border-color: rgba(0,213,89,0.25); }

.live-badge {

    display: inline-flex; align-items: center; gap: 6px;

    background: rgba(0,213,89,0.08); color: #00D559;

    border: 1px solid rgba(0,213,89,0.30);

    padding: 3px 10px; border-radius: 100px;

    font-size: 0.78rem; font-weight: 700;

}

.live-badge::before {

    content: '';

    display: inline-block; width: 7px; height: 7px; border-radius: 50%;

    background: #00D559;

    animation: thePulse 1.8s ease-in-out infinite;

    flex-shrink: 0;

}



/* â”€â”€ Comp Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.comp-table {

    width: 100%; border-collapse: collapse;

    border-radius: 12px; overflow: hidden;

    background: #161B27; border: 1px solid rgba(255,255,255,0.07);

}

.comp-table th { padding: 10px 14px; font-size: 0.70rem; font-weight: 700; color: #6B7A9A; text-transform: uppercase; letter-spacing: 1px; background: #0D0F14; border-bottom: 1px solid rgba(255,255,255,0.07); text-align: left; }

.comp-table td { padding: 10px 14px; font-size: 0.84rem; color: #E0E8FF; border-bottom: 1px solid rgba(255,255,255,0.04); font-variant-numeric: tabular-nums; }

.comp-table tr:hover td { background: rgba(0,213,89,0.04); }

.comp-table tr:last-child td { border-bottom: none; }

.comp-table .check   { color: #00D559; font-weight: 700; }

.comp-table .cross   { color: #F24336; font-weight: 700; }

.comp-table .partial { color: #F9C62B; font-weight: 700; }



/* â”€â”€ Joseph Welcome Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.joseph-welcome-card {

    background: linear-gradient(135deg, #161B27 0%, #1C2232 100%);

    border: 1px solid rgba(0,213,89,0.22);

    border-radius: 18px;

    padding: 22px 26px;

    display: flex; align-items: center; gap: 20px;

    margin-bottom: 18px;

    box-shadow: 0 4px 20px rgba(0,213,89,0.06), 0 4px 20px rgba(0,0,0,0.4);

    position: relative; overflow: hidden;

}

.joseph-welcome-card::before {

    content: '';

    position: absolute; top:0; left:0; right:0; height:2px;

    background: linear-gradient(90deg, #00D559, #2D9EFF);

}

.joseph-welcome-avatar {

    width: 60px; height: 60px; border-radius: 50%; object-fit: cover;

    border: 2px solid rgba(0,213,89,0.40);

    box-shadow: 0 0 14px rgba(0,213,89,0.25);

    flex-shrink: 0;

}

.joseph-welcome-text { flex: 1; min-width: 0; }

.joseph-welcome-greeting { font-size: 0.72rem; font-weight: 700; color: #00D559; text-transform: uppercase; letter-spacing: 0.08em; }

.joseph-welcome-msg { font-size: 0.90rem; color: #E0E8FF; margin-top: 4px; line-height: 1.55; }



/* â”€â”€ LP Footer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

.lp-footer { text-align: center; font-size: 0.72rem; color: #6B7A9A; padding: 28px 0 14px; border-top: 1px solid rgba(255,255,255,0.06); }

.lp-footer a { color: #2D9EFF; text-decoration: none; }

.lp-footer a:hover { text-decoration: underline; }



/* â”€â”€ Responsive â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

@media (max-width: 768px) {

    .hero-hud { padding: 26px 18px; gap: 16px; }

    .pillar-card, .nav-card, .proof-card { padding: 16px 14px; }

    .status-card { padding: 14px 12px; }

    .status-card-value { font-size: 1.6rem; }

    .pillar-icon { width: 42px; height: 42px; font-size: 1.4rem; border-radius: 10px; }

    .pipeline-step { padding: 12px 10px; }

    .matchup-chip { padding: 8px 10px; font-size: 0.78rem; }

    .lp-divider { margin: 20px 0; }

    .lp-footer { font-size: 0.68rem; }

    .joseph-welcome-card { padding: 16px 14px; gap: 14px; }

    .joseph-welcome-avatar { width: 48px; height: 48px; }

    .joseph-welcome-msg { font-size: 0.82rem; }

}

@media (max-width: 480px) {

    .joseph-welcome-card { flex-direction: column; text-align: center; }

    .comp-table th, .comp-table td { padding: 8px 8px; font-size: 0.78rem; }

}

</style>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Configuration
# ============================================================

# ============================================================
# SECTION: Initialize App on Startup
# ============================================================

initialize_database()

# ── SQLite production warning ─────────────────────────────────
# Warn if running in production mode with the default SQLite path.
# SQLite is not ideal for multi-user cloud deployments.
if os.environ.get("SMARTAI_PRODUCTION", "").lower() in ("true", "1", "yes"):
    _db_path = os.environ.get("DB_PATH", "db/smartai_nba.db")
    if os.path.basename(_db_path) == "smartai_nba.db":
        logging.getLogger(__name__).warning(
            "Running in production mode with SQLite (%s). "
            "SQLite is not recommended for multi-user cloud deployments. "
            "Consider PostgreSQL or persistent storage. See docs/database_migration.md",
            _db_path,
        )
        if "sqlite_warning_shown" not in st.session_state:
            st.session_state["sqlite_warning_shown"] = True
            st.warning(
                "⚠️ **SQLite in Production Mode** — This app is running with SQLite, "
                "which may not persist data on ephemeral cloud platforms (e.g., Streamlit Cloud). "
                "See `docs/database_migration.md` for migration options."
            )

# ── Premium Status — Check and display in sidebar ─────────────
# This runs silently on app load.  is_premium_user() is cached in
# session state so it won't make Stripe API calls on every rerun.
try:
    from utils.auth import is_premium_user as _is_premium, handle_checkout_redirect as _handle_checkout
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
    # Handle checkout redirects even on the home page
    _handle_checkout()
    _user_is_premium = _is_premium()
except Exception:
    _user_is_premium = True  # Fail open — don't block the home page
    _PREM_PATH = "/14_%F0%9F%92%8E_Subscription_Level"

with st.sidebar:
    if _user_is_premium:
        st.markdown(
            '<div style="background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.28);'
            'border-radius:10px;padding:10px 14px;text-align:center;margin-bottom:8px;">'
            '<span style="color:#00D559;font-weight:700;font-size:0.9rem;">💎 Premium Active</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:rgba(255,94,0,0.08);border:1px solid rgba(255,94,0,0.25);'
            f'border-radius:10px;padding:10px 14px;text-align:center;margin-bottom:8px;">'
            f'<span style="color:#a0b4d0;font-size:0.85rem;">⭐ Free Plan</span><br>'
            f'<a href="{_PREM_PATH}" style="color:#ff5e00;font-size:0.78rem;'
            f'font-weight:600;text-decoration:none;">Upgrade to Premium →</a>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Restore user settings from database before applying defaults ───────
# On a fresh browser reload st.session_state is empty.  We read the
# user's last-saved settings from SQLite so they don't have to
# reconfigure everything.  Keys not in the DB fall through to the
# hard-coded defaults below.
_persisted = load_user_settings()  # {} on first run or on error
for _key, _val in _persisted.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ── Restore page state from database ──────────────────────────────────
# Critical page data (analysis results, picks, games, props, etc.) is
# persisted to SQLite so that an idle session timeout doesn't wipe
# the user's work.  Restore once on a fresh session.
if not st.session_state.get("_page_state_restored"):
    st.session_state["_page_state_restored"] = True
    _page_state = load_page_state()  # {} on first run or on error
    for _key, _val in _page_state.items():
        if _key not in st.session_state:
            st.session_state[_key] = _val
        elif isinstance(st.session_state[_key], (list, dict)) and not st.session_state[_key] and _val:
            # Replace empty defaults with saved non-empty data
            st.session_state[_key] = _val

if "simulation_depth" not in st.session_state:
    st.session_state["simulation_depth"] = 1000
if "minimum_edge_threshold" not in st.session_state:
    st.session_state["minimum_edge_threshold"] = 5.0
if "entry_fee" not in st.session_state:
    st.session_state["entry_fee"] = 10.0
if "total_bankroll" not in st.session_state:
    st.session_state["total_bankroll"] = 1000.0
if "kelly_multiplier" not in st.session_state:
    st.session_state["kelly_multiplier"] = 0.25
if "selected_platforms" not in st.session_state:
    st.session_state["selected_platforms"] = [
        "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
    ]
if "todays_games" not in st.session_state:
    st.session_state["todays_games"] = []
if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = []
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "session_props" not in st.session_state:
    st.session_state["session_props"] = []
if "loaded_live_picks" not in st.session_state:
    st.session_state["loaded_live_picks"] = []

# ═══ Joseph M. Smith Session State ═══
st.session_state.setdefault("joseph_enabled", True)
st.session_state.setdefault("joseph_used_fragments", set())
st.session_state.setdefault("joseph_bets_logged", False)
st.session_state.setdefault("joseph_results", [])
st.session_state.setdefault("joseph_widget_mode", None)
st.session_state.setdefault("joseph_widget_selection", None)
st.session_state.setdefault("joseph_widget_response", None)
st.session_state.setdefault("joseph_ambient_line", "")
st.session_state.setdefault("joseph_ambient_context", "idle")
st.session_state.setdefault("joseph_last_commentary", "")
st.session_state.setdefault("joseph_entry_just_built", False)

# ── Global Settings Popover (accessible from sidebar) ─────────
from utils.components import render_global_settings, inject_joseph_floating, render_joseph_hero_banner
with st.sidebar:
    render_global_settings()
st.session_state["joseph_page_context"] = "page_home"
inject_joseph_floating()

# ============================================================
# END SECTION: Initialize App on Startup
# ============================================================

# ============================================================
# SECTION 1: Cinematic Hero — Joseph Banner + Hero HUD + CTA
# ============================================================

# Joseph M. Smith Hero Banner — full-width visual hook at absolute top
render_joseph_hero_banner()

today_str = datetime.date.today().strftime("%A, %B %d, %Y")
todays_games = st.session_state.get("todays_games", [])
game_count = len(todays_games)
game_count_text = (
    f"🏟️ {game_count} game{'s' if game_count != 1 else ''} tonight"
    if game_count
    else "🏟️ No games loaded yet"
)


# Ambient floating orbs behind the page
st.markdown("""
<div class="lp-orbs-container">
  <div class="lp-orb lp-orb-1"></div>
  <div class="lp-orb lp-orb-2"></div>
  <div class="lp-orb lp-orb-3"></div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero-hud lp-anim">
  <div class="hero-hud-inner-glow"></div>
  <div class="hero-hud-text">
    <div class="hero-tagline">THE SMARTEST NBA PLAYER PROP ENGINE ONLINE</div>
    <div class="hero-subtext"><strong>Find Tonight's Best Bets in 60 Seconds.</strong> Every Pick Tells You Why.</div>
    <div class="hero-date">📅 {today_str} &nbsp;&bull;&nbsp; <span class="game-count-live">{game_count_text}</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── ⚡ One-Click Setup CTA — Primary hero action ────────────────
_home_one_click = st.button(
    "⚡ LOAD TONIGHT'S SLATE — ONE CLICK",
    key="home_one_click_btn",
    type="primary",
    use_container_width=True,
    help="Loads tonight's games, rosters, injuries, and live props from all platforms in one click.",
)
if _home_one_click:
    import time as _hoc_time
    st.subheader("⚡ One-Click Setup")
    st.markdown("Running **Auto-Load** + **Get Live Props** in one step…")

    # ── Joseph Loading Screen — NBA fun facts while loading slate ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _hoc_joseph_loader = joseph_loading_placeholder("Loading tonight's slate")
    except Exception:
        _hoc_joseph_loader = None

    _hoc_bar = st.progress(0)
    _hoc_status = st.empty()

    try:
        # ── Phase 0: ETL Update for fresh local DB stats ──────────────
        try:
            from data.nba_data_service import refresh_from_etl as _hoc_refresh_etl
            _hoc_etl_available = True
        except ImportError:
            _hoc_etl_available = False

        if _hoc_etl_available:
            _hoc_status.text("⏳ Phase 0/4 — Running Smart ETL Update for fresh stats…")
            _hoc_bar.progress(2)
            try:
                _hoc_etl_result = _hoc_refresh_etl()
            except Exception:
                pass

        # ── Phase 1: Auto-Load Tonight's Games ────────────────────────
        _hoc_status.text("⏳ Phase 1/4 — Auto-loading tonight's games, rosters & stats…")
        _hoc_bar.progress(5)
        from data.nba_data_service import (
            get_todays_games as _hoc_fg,
            get_todays_players as _hoc_fp,
            get_team_stats as _hoc_ft,
            get_standings as _hoc_fs,
        )
        from data.data_manager import (
            clear_all_caches as _hoc_cc,
            load_injury_status as _hoc_li,
            save_props_to_session as _hoc_sp,
        )

        _hoc_games = _hoc_fg()
        if _hoc_games:
            st.session_state["todays_games"] = _hoc_games
        else:
            _hoc_games = st.session_state.get("todays_games", [])

        _hoc_bar.progress(25)
        _hoc_status.text(f"⏳ Phase 1/4 — {len(_hoc_games)} game(s) loaded. Loading player data…")

        _hoc_players_ok = _hoc_fp(_hoc_games) if _hoc_games else False
        _hoc_bar.progress(40)

        # Clear caches so freshly-written players.csv is read
        _hoc_cc()

        try:
            st.session_state["injury_status_map"] = _hoc_li()
        except Exception:
            pass

        # ── Phase 2: Load team stats & standings ─────────────────────
        _hoc_status.text("⏳ Phase 2/4 — Loading team stats & standings…")
        _hoc_bar.progress(50)

        try:
            _hoc_ft()
        except Exception:
            pass

        try:
            _hoc_standings = _hoc_fs()
            if _hoc_standings:
                st.session_state["league_standings"] = _hoc_standings
        except Exception:
            pass

        _hoc_bar.progress(60)

        # ── Phase 3: Get Live Platform Props ────────────────────────
        _hoc_status.text("⏳ Phase 3/4 — Retrieving live prop lines from all platforms…")

        try:
            from data.sportsbook_service import get_all_sportsbook_props as _hoc_fap
            from data.data_manager import (
                save_platform_props_to_session as _hoc_sps,
                save_platform_props_to_csv as _hoc_csv,
            )
            _hoc_odds_key = st.session_state.get("odds_api_key") or ""
            _hoc_live = _hoc_fap(odds_api_key=_hoc_odds_key or None)
            _hoc_bar.progress(85)
            if _hoc_live:
                _hoc_sp(_hoc_live, st.session_state)
                _hoc_sps(_hoc_live, st.session_state)
                try:
                    _hoc_csv(_hoc_live)
                except Exception:
                    pass
                _hoc_platform_msg = f"✅ {len(_hoc_live)} live props retrieved"
            else:
                _hoc_platform_msg = "⚠️ No live platform props returned (data may be unavailable)"
        except Exception as _hoc_plat_err:
            _hoc_platform_msg = f"⚠️ Platform retrieval failed: {_hoc_plat_err}"

        _hoc_bar.progress(100)
        _hoc_status.empty()
        _hoc_bar.empty()
        # Dismiss the Joseph loading screen
        if _hoc_joseph_loader is not None:
            try:
                _hoc_joseph_loader.empty()
            except Exception:
                pass

        _hoc_total = len(st.session_state.get("current_props", []))
        st.success(
            f"✅ **One-Click Setup complete!** "
            f"Games: {'✅ ' + str(len(_hoc_games)) if _hoc_games else '⚠️ none'} | "
            f"Players: {'✅' if _hoc_players_ok else '⚠️ check data'} | "
            f"Props: {_hoc_platform_msg} | "
            f"Total props loaded: **{_hoc_total}**\n\n"
            "👉 Go to **⚡ Neural Analysis** and click **Run Analysis** to analyze all loaded props."
        )
        _hoc_time.sleep(1)
        st.rerun()

    except Exception as _hoc_err:
        _hoc_bar.empty()
        _hoc_status.empty()
        # Dismiss the Joseph loading screen on error
        if _hoc_joseph_loader is not None:
            try:
                _hoc_joseph_loader.empty()
            except Exception:
                pass
        _hoc_err_str = str(_hoc_err)
        if "WebSocketClosedError" in _hoc_err_str or "StreamClosedError" in _hoc_err_str:
            pass
        else:
            st.error(f"❌ One-Click Setup failed: {_hoc_err}")

# ============================================================
# END SECTION 1: Cinematic Hero
# ============================================================

# ============================================================
# SECTION 1A: Top 3 Tonight — Hero Cards
# ============================================================

_home_analysis = st.session_state.get("analysis_results", [])

# Build Top 3 hero pool: Platinum/Gold, conf >= 65, not avoided/out
_hero_pool = [
    r for r in _home_analysis
    if not r.get("should_avoid", False)
    and not r.get("player_is_out", False)
    and r.get("tier", "Bronze") in {"Platinum", "Gold"}
    and float(r.get("confidence_score", 0) or 0) >= 65
]
_hero_pool = sorted(
    _hero_pool,
    key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
    reverse=True,
)[:3]

if _hero_pool:
    # Attach Joseph short takes if available
    _joseph_results = st.session_state.get("joseph_results", [])
    if _joseph_results:
        _joseph_lookup = {
            (jr.get("player_name", ""), (jr.get("stat_type", "") or "").lower()): jr
            for jr in _joseph_results
        }
        for _hp in _hero_pool:
            _jk = (_hp.get("player_name", ""), (_hp.get("stat_type", "") or "").lower())
            _jr = _joseph_lookup.get(_jk)
            if _jr:
                _hp["joseph_short_take"] = _jr.get("joseph_short_take", "") or _jr.get("joseph_take", "")

    st.markdown(_get_qcm_css(), unsafe_allow_html=True)
    st.markdown(
        _render_hero_section_html(_hero_pool),
        unsafe_allow_html=True,
    )
    st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 1A: Top 3 Tonight
# ============================================================

# ============================================================
# SECTION 1B: Quantum Edge Gap — Extreme-edge standard-line picks
#             (|edge| ≥ 20%, odds_type="standard" only, no goblins/demons)
# ============================================================

_home_edge_gap_picks = _filter_qeg_picks(_home_analysis)
_home_edge_gap_picks = _deduplicate_qeg_picks(_home_edge_gap_picks)
_home_edge_gap_picks = sorted(
    _home_edge_gap_picks,
    key=lambda r: abs(r.get("edge_percentage", 0)),
    reverse=True,
)

if _home_edge_gap_picks:
    st.markdown(_get_qcm_css(), unsafe_allow_html=True)
    st.markdown(
        _render_edge_gap_banner_html(_home_edge_gap_picks),
        unsafe_allow_html=True,
    )
    st.markdown(
        _render_edge_gap_grouped_html(_home_edge_gap_picks),
        unsafe_allow_html=True,
    )
    st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 1B: Quantum Edge Gap
# ============================================================

# ============================================================
# SECTION 2: Joseph's Welcome — The Personality Hook
# ============================================================

# Load Joseph avatar for welcome card
@st.cache_data(show_spinner=False)
def _load_joseph_avatar_b64() -> str:
    """Load the Joseph M Smith Avatar and return base64-encoded string."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    for name in ("Joseph M Smith Avatar.png", "Joseph M Smith Avatar Victory.png"):
        candidates.extend([
            os.path.join(_this, name),
            os.path.join(_this, "assets", name),
        ])
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            try:
                with open(norm, "rb") as fh:
                    return base64.b64encode(fh.read()).decode("utf-8")
            except Exception:
                pass
    return ""

_joseph_avatar_b64 = _load_joseph_avatar_b64()
_joseph_avatar_tag = (
    f'<img src="data:image/png;base64,{_joseph_avatar_b64}" class="joseph-welcome-avatar" alt="Joseph M. Smith" />'
    if _joseph_avatar_b64 else '<div class="joseph-welcome-avatar" style="background:#1e293b;display:flex;align-items:center;justify-content:center;font-size:1.5rem;">🎙️</div>'
)

# Dynamic message based on session state
_analysis_results = st.session_state.get("analysis_results", [])
_games_loaded = len(todays_games)

if _analysis_results:
    _platinum_count = sum(1 for r in _analysis_results if r.get("tier", "").lower() == "platinum")
    _gold_count = sum(1 for r in _analysis_results if r.get("tier", "").lower() == "gold")
    _avoid_count = sum(1 for r in _analysis_results if r.get("tier", "").lower() == "avoid")
    _joseph_msg = (
        f"We've got {_platinum_count} Platinum lock{'s' if _platinum_count != 1 else ''} "
        f"and {_gold_count} Gold play{'s' if _gold_count != 1 else ''} tonight. "
        f"I flagged {_avoid_count} trap{'s' if _avoid_count != 1 else ''} to skip. "
        f"The house doesn't know what's coming."
    )
elif _games_loaded:
    _joseph_msg = (
        f"I see {_games_loaded} game{'s' if _games_loaded != 1 else ''} on the board tonight. "
        f"The lines are up. Run the engine and let me show you where the sportsbooks made mistakes."
    )
else:
    _joseph_msg = (
        "The board is dark. Hit that button and load tonight's slate — "
        "I've been watching the lines ALL DAY and I already see where the books slipped up. "
        "Let's go to work."
    )

st.markdown(f"""
<div class="joseph-welcome-card lp-anim lp-anim-d1">
  {_joseph_avatar_tag}
  <div class="joseph-welcome-text">
    <div class="joseph-welcome-name">🎙️ Joseph M. Smith <span class="badge-ai">AI ANALYST</span></div>
    <div class="joseph-welcome-msg">"{_joseph_msg}"</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION 2: Joseph's Welcome
# ============================================================

# ============================================================
# SECTION 3: The Competitive Kill Shot — "Why Smart Pick Pro Wins"
# ============================================================

st.markdown("""
<div class="section-header lp-anim lp-anim-d2">Most Prop Tools Give You a Number. We Give You the Proof.</div>
<div class="section-subheader">Three things no other prop tool on the internet can match.</div>
""", unsafe_allow_html=True)

# ── 3A: Three Pillars ───────────────────────────────────────────
_p1, _p2, _p3 = st.columns(3)

with _p1:
    st.markdown("""
    <div class="pillar-card accent-cyan lp-anim lp-anim-d2">
      <div class="pillar-accent"></div>
      <div class="pillar-card-inner">
        <div class="pillar-icon-halo"><span class="pillar-icon">🎲</span></div>
        <div class="pillar-title">Quantum Matrix Engine</div>
        <div class="pillar-subtitle">Thousands of Simulated Games Per Prop</div>
        <div class="pillar-body">
          Every prop runs through thousands of simulated game scenarios — randomized
          minutes, game flow, momentum swings, and real-world chaos.
          <br><br>
          The result: a probability distribution built from YOUR player in TONIGHT'S
          specific matchup — not a generic average.
          <br><br>
          <strong>You choose the depth:</strong>
          <ul>
            <li>⚡ Fast (seconds)</li>
            <li>🎯 Standard (recommended)</li>
            <li>🔬 Deep Scan (maximum accuracy)</li>
          </ul>
          <ul>
            <li>Percentile ranges (10th–90th)</li>
            <li>Probability gauges</li>
            <li>Confidence intervals</li>
            <li>Distribution histograms</li>
          </ul>
        </div>
        <div class="pillar-footer">Other tools: one number. No context.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with _p2:
    st.markdown("""
    <div class="pillar-card accent-green lp-anim lp-anim-d3">
      <div class="pillar-accent"></div>
      <div class="pillar-card-inner">
        <div class="pillar-icon-halo"><span class="pillar-icon">🔬</span></div>
        <div class="pillar-title">Force Analysis</div>
        <div class="pillar-subtitle">Every Pick Tells You WHY</div>
        <div class="pillar-body">
          Every prop shows the exact factors pushing performance UP or DOWN:
          <br><br>
          ✅ Matchup quality<br>
          ✅ Game environment &amp; pace<br>
          ✅ Rest &amp; fatigue impact<br>
          ✅ Blowout / garbage time risk<br>
          ✅ Market consensus signals<br>
          ✅ Trend &amp; regression detection
          <br><br>
          Plus our proprietary <strong>Trap Line Detection</strong> system that catches lines
          designed to bait public money on the wrong side.
          <br><br>
          You see OVER forces vs UNDER forces, each with a strength rating.
          No black box. Full transparency.
        </div>
        <div class="pillar-footer">Other tools: "63% confidence." That's it.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with _p3:
    st.markdown("""
    <div class="pillar-card accent-gold lp-anim lp-anim-d4">
      <div class="pillar-accent"></div>
      <div class="pillar-card-inner">
        <div class="pillar-icon-halo"><span class="pillar-icon">🏆</span></div>
        <div class="pillar-title">SAFE Score™</div>
        <div class="pillar-subtitle">Institutional-Grade Scoring</div>
        <div class="pillar-body">
          <em>Statistical Analysis of Force &amp; Edge</em>
          <br><br>
          A proprietary 0–100 composite score that weighs multiple independent signals
          — probability, edge quality, matchup, consistency, momentum, and more —
          into one actionable number.
          <br><br>
          <strong>Built-in safeguards</strong> prevent the engine from being overconfident:
          <br><br>
          🛡️ Automatic tier demotion triggers<br>
          🛡️ Variance-aware scoring<br>
          🛡️ Sample-size adjustments<br>
          🛡️ Tier distribution enforcement
          <br><br>
          💎 Platinum · 🥇 Gold · 🥈 Silver · 🥉 Bronze · ⛔ Avoid
        </div>
        <div class="pillar-footer">Other tools: one number, no safeguards.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── 3B: Comparison Table ────────────────────────────────────────
st.markdown("""
<div style="margin-top:28px;">
<table class="comp-table">
  <thead>
    <tr>
      <th>What You Get</th>
      <th>Free Spreadsheet</th>
      <th>Typical Prop Tool</th>
      <th>Smart Pick Pro</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Simulation Engine</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Proprietary Quantum Matrix Simulation</td>
    </tr>
    <tr>
      <td>Why a Pick Wins</td>
      <td>❌ Guessing</td>
      <td>❌ "63% confidence"</td>
      <td class="spp-col">✅ Full force breakdown — every factor shown</td>
    </tr>
    <tr>
      <td>Trap Detection</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Proprietary multi-pattern trap system</td>
    </tr>
    <tr>
      <td>Scoring System</td>
      <td>❌ None</td>
      <td>❌ Single number</td>
      <td class="spp-col">✅ SAFE Score™ — multi-signal composite with tier safeguards</td>
    </tr>
    <tr>
      <td>AI Analyst</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Joseph M. Smith — pre-game, in-game, and post-game commentary</td>
    </tr>
    <tr>
      <td>Risk Assessment</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Risk ratings + auto-flagging on every pick</td>
    </tr>
    <tr>
      <td>Parlay Optimizer</td>
      <td>❌ Manual</td>
      <td>❌ Basic</td>
      <td class="spp-col">✅ EV-optimized Entry Builder across all major platforms</td>
    </tr>
    <tr>
      <td>Live Tracking</td>
      <td>❌ Box score</td>
      <td>❌ Box score</td>
      <td class="spp-col">✅ Live Sweat Room with real-time pace and projection tracking</td>
    </tr>
    <tr>
      <td>Performance Tracking</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Bet Tracker + Model Health Dashboard</td>
    </tr>
    <tr>
      <td>Platforms Supported</td>
      <td>❌ One</td>
      <td>❌ One or two</td>
      <td class="spp-col">✅ PrizePicks · Underdog · DraftKings Pick6 and more</td>
    </tr>
  </tbody>
</table>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# SECTION 4: The Proof Points — Animated Metric Cards
# ============================================================

st.markdown('<div class="section-header lp-anim lp-anim-d3">The Numbers Speak</div>', unsafe_allow_html=True)

_proof_cols = st.columns(5)

_proof_data = [
    ("THOUSANDS", "Simulated Games Per Prop"),
    ("MULTIPLE", "Analysis Models Blended"),
    ("EVERY", "Pick Explains WHY"),
    ("15", "Pages of Tools"),
    ("REAL TIME", "Live Props"),
]

_proof_colors = ["#00D559", "#2D9EFF", "#F9C62B", "#FFD700", "#F24336"]

for i, (_num, _label) in enumerate(_proof_data):
    with _proof_cols[i]:
        _color = _proof_colors[i]
        _delay_cls = f"lp-anim-d{i + 2}"
        st.markdown(f"""
        <div class="proof-card lp-anim {_delay_cls}">
          <div class="proof-card-number" style="color:{_color};">{_num}</div>
          <div class="proof-card-label">{_label}</div>
        </div>
        """, unsafe_allow_html=True)

# 6th dynamic card — tracked performance if data exists
try:
    from utils.joseph_widget import joseph_get_track_record
    _track_record = joseph_get_track_record()
    if _track_record.get("total", 0) > 10:
        st.metric(
            "Tracked Win Rate",
            f"{_track_record['win_rate']:.0f}%",
            delta=f"{_track_record['total']} picks tracked",
        )
except Exception:
    pass

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 4: The Proof Points
# ============================================================

# ============================================================
# SECTION 5: Session Readiness Pipeline
# ============================================================

st.markdown('<div class="section-header lp-anim lp-anim-d2">Your Session</div>', unsafe_allow_html=True)

_sess_games = len(st.session_state.get("todays_games", []))
_sess_props = len(st.session_state.get("current_props", []))
_sess_analysis = len(st.session_state.get("analysis_results", []))
_sess_entries = len(st.session_state.get("selected_picks", []))

def _step_class(done: bool) -> str:
    return "done" if done else "pending"

_s1_done = _sess_games > 0
_s2_done = _sess_props > 0
_s3_done = _sess_analysis > 0
_s4_done = _sess_entries > 0

_steps_data = [
    ("1", "Load Games", _s1_done,
     f"✅ {_sess_games} game{'s' if _sess_games != 1 else ''}" if _s1_done else f"⏳ {_sess_games} game{'s' if _sess_games != 1 else ''}"),
    ("2", "Load Props", _s2_done,
     f"✅ {_sess_props} prop{'s' if _sess_props != 1 else ''}" if _s2_done else f"⏳ {_sess_props} prop{'s' if _sess_props != 1 else ''}"),
    ("3", "Run Engine", _s3_done,
     f"✅ {_sess_analysis}" if _s3_done else "⏳ Not run"),
    ("4", "Build Entries", _s4_done,
     f"✅ {_sess_entries}" if _s4_done else "⏳ —"),
]

# Build an HTML-based connected pipeline for visual consistency
_pipeline_html_parts = []
for idx, (num, label, done, status_text) in enumerate(_steps_data):
    _cls = "done" if done else "pending"
    _status_cls = "green" if done else "amber"
    _pipeline_html_parts.append(
        f'<div class="pipeline-step {_cls}">'
        f'  <div class="pipeline-step-num">{num}</div>'
        f'  <div class="pipeline-step-label">{label}</div>'
        f'  <div class="pipeline-step-status {_status_cls}">{status_text}</div>'
        f'</div>'
    )
    if idx < 3:
        _active_cls = "active" if done else ""
        _pipeline_html_parts.append(f'<div class="pipeline-connector {_active_cls}"></div>')

st.markdown(
    '<div class="pipeline-row lp-anim lp-anim-d3">' + ''.join(_pipeline_html_parts) + '</div>',
    unsafe_allow_html=True,
)

# ── Consolidated warnings (stale data / validation) — single amber banner ──
_consolidated_warnings = []
try:
    from data.nba_data_service import load_last_updated as _load_lu
    _last_updated = _load_lu() or {}
    _teams_ts = _last_updated.get("teams_stats")
    if _teams_ts:
        import datetime as _dt
        _teams_date = _dt.datetime.fromisoformat(_teams_ts)
        _teams_age_days = (_dt.datetime.now() - _teams_date).days
        if _teams_age_days >= 7:
            _consolidated_warnings.append(
                f"Team stats are **{_teams_age_days} days old**. "
                f"Go to **📡 Smart NBA Data → Smart Update** to refresh."
            )
        elif _teams_age_days >= 3:
            _consolidated_warnings.append(
                f"Team stats last updated {_teams_age_days} days ago. "
                f"Consider refreshing on the Smart NBA Data page."
            )
    else:
        from data.data_manager import load_teams_data as _load_teams
        _teams_data_check = _load_teams()
        if not _teams_data_check:
            _consolidated_warnings.append(
                "No team stats found. Go to **📡 Smart NBA Data → Smart Update** "
                "to load team data for accurate analysis."
            )
except Exception as _exc:
    logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

try:
    from data.validators import validate_players_csv, validate_teams_csv
    from data.data_manager import load_players_data as _lp_val, load_teams_data as _lt_val
    _val_players = _lp_val()
    _val_teams = _lt_val()
    _p_errors = validate_players_csv(_val_players)
    _t_errors = validate_teams_csv(_val_teams)
    if _p_errors or _t_errors:
        for e in _p_errors:
            _consolidated_warnings.append(f"players.csv: {e}")
        for e in _t_errors:
            _consolidated_warnings.append(f"teams.csv: {e}")
except Exception as _exc:
    logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

try:
    from data.nba_data_service import get_teams_staleness_warning
    _staleness_warn = get_teams_staleness_warning()
    if _staleness_warn:
        st.sidebar.warning(_staleness_warn)
except Exception as _exc:
    logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

if _consolidated_warnings:
    with st.expander("⚠️ Data Warnings", expanded=False):
        for _w in _consolidated_warnings:
            st.warning(_w)

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 5: Session Readiness Pipeline
# ============================================================

# ============================================================
# SECTION 6: How It Works — High-Level 5-Stage Pipeline
# ============================================================

st.markdown("""
<div class="section-header lp-anim lp-anim-d2">How It Works</div>
<div class="section-subheader">Five stages. Full transparency on what happens. Zero implementation details exposed.</div>
""", unsafe_allow_html=True)

_hiw_stages = [
    ("📡", "Data Ingest",
     "We pull real-time NBA data from multiple sources — player stats, team ratings, injuries, and live prop lines from every major platform."),
    ("📐", "Smart Projections",
     "Our engine adjusts each player's baseline for tonight's specific matchup, game environment, rest, and real-time conditions."),
    ("🎲", "Quantum Matrix Engine",
     "Thousands of game simulations for each prop — every sim randomizes the chaos of a real NBA game to build a true probability distribution."),
    ("🔬", "Edge Analysis",
     "Every directional force is identified, strength-rated, and balanced against opposing signals. Trap lines are flagged. Coin-flip bets are caught."),
    ("🏆", "SAFE Score™",
     "A proprietary multi-signal composite score with built-in safeguards assigns every pick a tier: Platinum, Gold, Silver, Bronze, or Avoid."),
]

_hiw_cols = st.columns(len(_hiw_stages) * 2 - 1)  # stages + arrows between them
for idx, (icon, title, desc) in enumerate(_hiw_stages):
    col_idx = idx * 2
    with _hiw_cols[col_idx]:
        st.markdown(f"""
        <div class="hiw-stage lp-anim lp-anim-d{min(idx + 2, 6)}">
          <div class="hiw-stage-num">{idx + 1}</div>
          <div class="hiw-stage-icon">{icon}</div>
          <div class="hiw-stage-title">{title}</div>
          <div class="hiw-stage-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
    if idx < 4:
        with _hiw_cols[col_idx + 1]:
            st.markdown('<div class="hiw-connector" style="height:100%;">&#8203;</div>', unsafe_allow_html=True)

with st.expander("📖 How to Use Smart Pick Pro", expanded=False):
    st.markdown("""
    **Recommended Workflow**
    1. **📡 Live Games** — Click "⚡ Load Tonight's Slate" for a one-click setup
    2. **🔬 Prop Scanner** — Enter props manually or load live lines from all platforms
    3. **⚡ Quantum Analysis** — Run the engine on your props
    4. **🧬 Entry Builder** — Build EV-optimized parlays
    5. **📈 Bet Tracker** — Log results and track performance over time

    💡 **Pro Tip:** Use the one-click button at the top of this page to load games + props in a single action.
    Then head straight to ⚡ Quantum Analysis to run the engine.
    """)

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 6: How It Works
# ============================================================

# ============================================================
# SECTION 7: App Map — Interactive Navigation Cards
# ============================================================

st.markdown("""
<div class="section-header lp-anim lp-anim-d2">🗺️ Your Toolkit — 15 Pages of Analysis</div>
<div class="section-subheader">Every tool you need, from data loading to bet tracking.</div>
""", unsafe_allow_html=True)

# Row 1 — Tonight's Workflow
st.markdown('<div class="nav-row-label workflow">⚡ Tonight\'s Workflow</div>', unsafe_allow_html=True)
_nav_r1 = st.columns(4)
_nav_row1 = [
    ("📡", "Live Games", "Load tonight's slate in one click", "pages/1_📡_Live_Games.py"),
    ("🔬", "Prop Scanner", "Enter props manually or pull live lines", "pages/2_🔬_Prop_Scanner.py"),
    ("⚡", "Quantum Analysis", "Run the Quantum Matrix Engine", "pages/3_⚡_Quantum_Analysis_Matrix.py"),
    ("🧬", "Entry Builder", "Build EV-optimized parlays", "pages/6_🧬_Entry_Builder.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row1):
    with _nav_r1[i]:
        st.markdown(f"""
        <div class="nav-card cat-workflow lp-anim lp-anim-d{i + 2}">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

# Row 2 — Deep Analysis
st.markdown('<div class="nav-row-label analysis">🔬 Deep Analysis</div>', unsafe_allow_html=True)
_nav_r2 = st.columns(5)
_nav_row2 = [
    ("📋", "Game Report", "Full game breakdowns", "pages/4_📋_Game_Report.py"),
    ("🔮", "Player Simulator", "What-if scenarios", "pages/5_🔮_Player_Simulator.py"),
    ("🗺️", "Correlation Matrix", "Find correlated props", "pages/10_🗺️_Correlation_Matrix.py"),
    ("🛡️", "Risk Shield", "See what to avoid + why", "pages/8_🛡️_Risk_Shield.py"),
    ("🎙️", "The Studio", "Joseph's AI analysis room", "pages/7_🎙️_The_Studio.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row2):
    with _nav_r2[i]:
        st.markdown(f"""
        <div class="nav-card cat-analysis lp-anim lp-anim-d{min(i + 2, 6)}">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

# Row 3 — Track & Manage
st.markdown('<div class="nav-row-label manage">📊 Track &amp; Manage</div>', unsafe_allow_html=True)
_nav_r3 = st.columns(6)
_nav_row3 = [
    ("💦", "Live Sweat", "Track bets in real-time", "pages/0_💦_Live_Sweat.py"),
    ("📈", "Bet Tracker", "Log results, track ROI", "pages/11_📈_Bet_Tracker.py"),
    ("📊", "Proving Grounds", "Validate model accuracy", "pages/12_📊_Proving_Grounds.py"),
    ("📡", "Smart NBA Data", "Player stats, standings & more", "pages/9_📡_Smart_NBA_Data.py"),
    ("⚙️", "Settings", "Tune engine parameters", "pages/13_⚙️_Settings.py"),
    ("💎", "Premium", "Unlock everything", "pages/14_💎_Subscription_Level.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row3):
    with _nav_r3[i]:
        st.markdown(f"""
        <div class="nav-card cat-manage lp-anim lp-anim-d{min(i + 2, 6)}">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 7: App Map
# ============================================================

# ============================================================
# SECTION 8: Tonight's Slate — Enhanced Matchup Cards
# ============================================================

if todays_games:
    st.markdown('<div class="section-header lp-anim lp-anim-d2">🏟️ Tonight\'s Slate</div>', unsafe_allow_html=True)

    chips_html = ""
    for game in todays_games:
        away = game.get("away_team", "")
        home = game.get("home_team", "")
        aw = game.get("away_wins", 0)
        al = game.get("away_losses", 0)
        hw = game.get("home_wins", 0)
        hl = game.get("home_losses", 0)
        rec_a = f" ({aw}-{al})" if aw or al else ""
        rec_h = f" ({hw}-{hl})" if hw or hl else ""

        # Enhanced metadata line — spread, total, game time
        _spread = game.get("spread", "")
        _total = game.get("total", "")
        _game_time = game.get("game_time", "")
        _meta_parts = []
        if _spread:
            _meta_parts.append(f"Spread: {_spread}")
        if _total:
            _meta_parts.append(f"O/U: {_total}")
        if _game_time:
            _meta_parts.append(_game_time)
        _meta_line = f'<div class="matchup-meta">{" · ".join(_meta_parts)}</div>' if _meta_parts else ""

        chips_html += (
            f'<span class="matchup-chip">'
            f'<span>🚌 <strong>{away}</strong>{rec_a}</span>'
            f'<span style="color:#2D9EFF; font-weight:700; margin:0 6px;">vs</span>'
            f'<span>🏠 <strong>{home}</strong>{rec_h}</span>'
            f'{_meta_line}'
            f'</span> '
        )

    st.markdown(f'<div style="margin:8px 0 12px 0;display:flex;flex-wrap:wrap;gap:8px;">{chips_html}</div>', unsafe_allow_html=True)
    st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 8: Tonight's Slate
# ============================================================

# ============================================================
# SECTION 9: Status Dashboard — Streamlined (for returning users)
# ============================================================

players_data = load_players_data()
props_data = load_props_data()
teams_data = load_teams_data()

current_props = st.session_state.get("current_props", props_data)
number_of_current_props = len(current_props)
number_of_analysis_results = len(st.session_state.get("analysis_results", []))

# Live data status
live_data_timestamps = load_last_updated()
is_using_live_data = live_data_timestamps.get("is_live", False)
data_badge = '<span class="live-badge">LIVE</span>' if is_using_live_data else '<span class="sample-badge">📊 SAMPLE</span>'

with st.expander("📊 Status Dashboard", expanded=False):
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{len(players_data)}</div>
          <div class="status-card-label">👤 Players</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{number_of_current_props}</div>
          <div class="status-card-label">🎯 Props</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        val3 = str(game_count) if game_count else "—"
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{val3}</div>
          <div class="status-card-label">🏟️ Games Tonight</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        val4 = str(number_of_analysis_results) if number_of_analysis_results else "—"
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{val4}</div>
          <div class="status-card-label">📈 Analyzed</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value" style="font-size:1.1rem; padding-top:8px;">{data_badge}</div>
          <div class="status-card-label">Data Source</div>
        </div>
        """, unsafe_allow_html=True)

    # ── System Health — consolidated into status ───────────────────
    try:
        from data.data_manager import get_data_health_report
        _health = get_data_health_report()

        st.markdown("---")
        hc1, hc2, hc3, hc4 = st.columns(4)
        hc1.metric("👥 Players", _health["players_count"])
        hc2.metric("🏀 Teams", _health["teams_count"])
        hc3.metric("📋 Props", _health["props_count"])
        _freshness_label = f"{_health['days_old']}d old" if _health.get("last_updated") else "Never"
        hc4.metric("🕐 Data Age", _freshness_label,
                   delta="⚠️ Stale" if _health["is_stale"] else "✅ Fresh",
                   delta_color="inverse" if _health["is_stale"] else "normal")

        if _health["warnings"]:
            for w in _health["warnings"]:
                st.warning(w)
        else:
            st.success("✅ All data files present and fresh.")

        st.caption("Go to **📡 Smart NBA Data** to refresh data.")
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

    # ── Live Data Status ────────────────────────────────────────────
    if is_using_live_data:
        player_ts = live_data_timestamps.get("players")
        team_ts = live_data_timestamps.get("teams")

        def format_timestamp(ts_string):
            if not ts_string:
                return "never"
            try:
                dt = datetime.datetime.fromisoformat(ts_string)
                return dt.strftime("%b %d at %I:%M %p")
            except Exception:
                return "unknown"

        st.success(
            f"✅ **Using Live NBA Data** — "
            f"Players: {format_timestamp(player_ts)} | "
            f"Teams: {format_timestamp(team_ts)}"
        )
    else:
        st.info(
            "📊 **No live data loaded yet** — Go to the **📡 Smart NBA Data** page to pull "
            "real, up-to-date NBA stats for accurate predictions!"
        )

# ============================================================
# END SECTION 9: Status Dashboard
# ============================================================

# ============================================================
# SECTION 10: Legal Disclaimer + Footer
# ============================================================

with st.expander("⚠️ Important Legal Disclaimer — Please Read", expanded=False):
    st.markdown("""
    ## ⚠️ IMPORTANT DISCLAIMER
    
    **SmartBetPro NBA ("Smart Pick Pro")** is an analytical tool for **entertainment and educational purposes only**. This application does NOT guarantee profits or winning outcomes.
    
    - 📊 Past performance does not guarantee future results
    - 🔢 All predictions are based on statistical models that have inherent limitations  
    - 💰 Sports betting involves significant financial risk — **never bet more than you can afford to lose**
    - 🔞 You must be **21+** (or legal age in your jurisdiction) to participate in sports betting
    - ⚠️ This tool is **not affiliated** with the NBA or any sportsbook
    - 🆘 Always gamble responsibly. If you or someone you know has a gambling problem, call **1-800-GAMBLER (1-800-426-2537)**
    
    **By using this application, you acknowledge that all betting decisions are your own responsibility.**
    
    ---
    
    **Responsible Gaming Resources:**
    - 📞 **National Problem Gambling Helpline: 1-800-GAMBLER (1-800-426-2537)** — 24/7 confidential support
    - 📞 National Council on Problem Gambling: **1-800-522-4700** — crisis counseling & referrals
    - 🌐 [www.ncpgambling.org](https://www.ncpgambling.org)
    - 🌐 [www.begambleaware.org](https://www.begambleaware.org)
    """)

st.markdown(
    f'<div class="lp-footer">'
    f'© {datetime.datetime.now().year} Smart Pick Pro | NBA Edition | '
    f'For entertainment & educational purposes only. Not financial advice. '
    f'Bet responsibly. 21+ | 1-800-GAMBLER'
    f'</div>',
    unsafe_allow_html=True,
)

# ============================================================
# END SECTION 10: Footer
# ============================================================
