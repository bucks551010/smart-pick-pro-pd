"""Fresh self-contained player card renderer for the QAM page  (v2).

Produces:
  - Compact one-line player rows (headshot, name, team, prop count, best edge, win grade)
  - Clicking a row expands to reveal expanded identity header + all prop cards
  - Each prop card shows: win grade, recommendation banner, tier + direction pill,
    true line vs season average, odds, confidence bar, std-devs-from-line,
    matchup factors row, metrics, distribution, recent form sparkline,
    risk / trap alerts, context pills, enhanced forces with descriptions,
    ensemble model info, score breakdown bars, and key factors.

All CSS is self-contained via ``PLAYER_CARD_CSS``.
"""

import html as _html
import re as _re
import logging as _logging

_logger = _logging.getLogger("smartai_nba.player_cards")

try:
    from data.player_profile_service import get_headshot_url as _get_headshot_url
except ImportError:
    def _get_headshot_url(name):
        return ""

try:
    from styles.theme import get_team_colors
except ImportError:
    def get_team_colors(team):
        return ("#4a5568", "#2d3748")

_FALLBACK_HEADSHOT = "https://cdn.nba.com/headshots/nba/latest/1040x760/fallback.png"

_e = _html.escape


# ===================================================================
#  CSS
# ===================================================================

PLAYER_CARD_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&family=Bebas+Neue&display=swap');

/* ── Page grid ───────────────────────────────────────────────── */
.pc-grid { display:flex; flex-direction:column; gap:14px; padding:8px 0; width:100%; max-width:100vw; overflow-x:hidden; }

/* ── Player section row ─────────────────────────────────────── */
.pc-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 50%, #131722 100%);
  border: 1.5px solid rgba(255,255,255,0.07);
  border-left: 3px solid transparent;
  border-radius: 18px;
  font-family: 'Inter', sans-serif;
  color: #e0eeff;
  overflow: hidden;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
  box-shadow: 0 2px 10px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.03);
}
.pc-card:hover { border-color: rgba(255,255,255,0.15); box-shadow: 0 6px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04); }
.pc-card[open] { border-color: rgba(0,213,89,0.25); box-shadow: 0 8px 32px rgba(0,213,89,0.06), 0 4px 20px rgba(0,0,0,0.5); }

/* ── Player summary row ─────────────────────────────────────── */
.pc-card > summary {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px; cursor: pointer;
  list-style: none; user-select: none;
  transition: background 0.15s;
}
.pc-card > summary::-webkit-details-marker { display:none; }
.pc-card > summary::marker { display:none; content:''; }
.pc-card > summary:hover { background: rgba(255,255,255,0.025); }
.pc-card[open] > summary { border-bottom: 1px solid rgba(255,255,255,0.06); }

.pc-arrow { font-size:0.52rem; color:#3A4460; flex-shrink:0; transition:transform 0.22s,color 0.18s; }
.pc-card[open] .pc-arrow { transform:rotate(90deg); color:#00D559; }

.pc-head { width:48px; height:48px; border-radius:50%; border:2px solid rgba(255,255,255,0.12); object-fit:cover; flex-shrink:0; background:#1C2232; transition:border-color 0.25s, box-shadow 0.25s; box-shadow:0 3px 10px rgba(0,0,0,0.35); }
.pc-card[open] .pc-head { border-color:rgba(0,213,89,0.40); box-shadow:0 3px 14px rgba(0,213,89,0.12); }

.pc-name { font-size:0.96rem; font-weight:800; color:#FFFFFF; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; letter-spacing:-0.01em; }
.pc-sum-team { font-size:0.60rem; font-weight:700; padding:2px 7px; border-radius:100px; color:#fff; white-space:nowrap; }
.pc-sum-props { font-size:0.68rem; color:#6B7A9A; white-space:nowrap; }
.pc-sum-edge { font-size:0.68rem; font-weight:700; padding:2px 9px; border-radius:100px; white-space:nowrap; background:rgba(0,213,89,0.09); color:#00D559; border:1px solid rgba(0,213,89,0.22); margin-left:auto; flex-shrink:0; }
.pc-sum-grade { font-family:'JetBrains Mono',monospace; font-size:0.70rem; font-weight:800; padding:3px 9px; border-radius:7px; flex-shrink:0; }

/* ── Expanded body ───────────────────────────────────────────── */
@keyframes pcSlideIn { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
.pc-body { padding:0 14px 16px; animation:pcSlideIn 0.22s cubic-bezier(0.22,1,0.36,1); }

/* Identity header */
.pc-identity { display:flex; align-items:center; gap:12px; padding:14px 2px 12px; border-bottom:1px solid rgba(255,255,255,0.05); margin-bottom:10px; background:linear-gradient(180deg, rgba(255,255,255,0.01) 0%, transparent 100%); }
.pc-id-avatar { width:70px; height:70px; border-radius:50%; border:2px solid rgba(0,213,89,0.28); object-fit:cover; background:#1C2232; flex-shrink:0; box-shadow:0 4px 16px rgba(0,0,0,0.4), 0 0 10px rgba(0,213,89,0.06); transition:box-shadow 0.25s; }
.pc-id-info { display:flex; flex-direction:column; gap:2px; min-width:0; }
.pc-id-name { font-size:1.05rem; font-weight:800; color:#FFFFFF; }
.pc-id-sub { font-size:0.66rem; color:#6B7A9A; display:flex; align-items:center; gap:5px; flex-wrap:wrap; }
.pc-id-team-badge { font-size:0.56rem; font-weight:700; padding:2px 7px; border-radius:100px; color:#fff; }
.pc-id-opp { font-size:0.60rem; color:#6B7A9A; }
.pc-id-status { font-size:0.56rem; font-weight:700; padding:2px 7px; border-radius:100px; background:rgba(242,67,54,0.14); color:#F24336; border:1px solid rgba(242,67,54,0.26); }
.pc-id-stats { display:flex; gap:6px; margin-left:auto; flex-shrink:0; flex-wrap:wrap; }
.pc-stat-pill { display:flex; flex-direction:column; align-items:center; padding:4px 9px; border-radius:9px; background:linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%); border:1px solid rgba(255,255,255,0.07); box-shadow:inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 3px rgba(0,0,0,0.12); }
.pc-stat-pill-val { font-family:'JetBrains Mono',monospace; font-size:0.78rem; font-weight:700; color:#FFFFFF; }
.pc-stat-pill-lbl { font-size:0.44rem; color:#6B7A9A; text-transform:uppercase; letter-spacing:0.05em; margin-top:1px; }

/* ── Horizontal prop scroll strip ───────────────────────────── */
.pc-props-scroll {
  display: flex; gap: 12px; align-items: flex-start;
  flex-wrap: nowrap;
  overflow-x: auto !important; overflow-y: visible;
  -webkit-overflow-scrolling: touch;
  padding: 10px 2px 16px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  scrollbar-width: thin; scrollbar-color: rgba(99,102,241,0.60) transparent;
}
.pc-props-scroll::-webkit-scrollbar { height: 6px; }
.pc-props-scroll::-webkit-scrollbar-track { background: rgba(99,102,241,0.06); border-radius: 100px; }
.pc-props-scroll::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.60); border-radius: 100px; }
.pc-props-scroll::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.85); }

/* ── PP-style prop card (fixed width, expands vertically on click) ── */
.pc-prop {
  flex-shrink: 0;
  width: min(238px, 85vw);
  background: linear-gradient(168deg, #1E2336 0%, #1A1F2E 35%, #161B27 100%);
  border: 1.5px solid rgba(255,255,255,0.08);
  border-radius: 22px;
  overflow: hidden;
  position: relative;
  transition: border-color 0.25s, transform 0.22s cubic-bezier(.22,1,.36,1), box-shadow 0.25s;
  box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
}
.pc-prop:hover { border-color:rgba(255,255,255,0.20); transform:translateY(-4px) scale(1.015); box-shadow:0 16px 40px rgba(0,0,0,0.6), 0 0 24px rgba(45,158,255,0.06), inset 0 1px 0 rgba(255,255,255,0.06); }
.pc-prop[open] { width:min(357px, 92vw); border-color:rgba(0,213,89,0.28); box-shadow:0 8px 28px rgba(0,213,89,0.08); transform:none; }
.pc-prop-platinum { border-color:rgba(0,213,89,0.35) !important; box-shadow:0 0 24px rgba(0,213,89,0.14), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(0,213,89,0.06); }
.pc-prop-gold     { border-color:rgba(249,198,43,0.30) !important; box-shadow:0 0 22px rgba(249,198,43,0.12), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(249,198,43,0.05); }

/* gradient top bar */
.pc-prop::before { content:''; display:block; height:3.5px; background:linear-gradient(90deg,#00D559,#2D9EFF); opacity:0.85; }
.pc-prop-platinum::before { background:linear-gradient(90deg,#00D559,#2D9EFF,#00D559); opacity:1; }
.pc-prop-gold::before     { background:linear-gradient(90deg,#F9C62B,#F24336); opacity:1; }

/* ── Card face (summary = what you see before clicking) ─────── */
.pc-prop > summary {
  display: flex; flex-direction: column; align-items: center;
  list-style: none; cursor: pointer; user-select: none;
  padding-bottom: 4px; outline: none;
  position: relative; z-index: 0;
}
.pc-prop > summary::-webkit-details-marker { display:none; }
.pc-prop > summary::marker { display:none; content:''; }
.pc-prop > summary::after { content:''; position:absolute; top:0; left:10%; right:10%; height:55%; background:radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.025) 0%, transparent 70%); pointer-events:none; z-index:-1; }

/* status bar */
.pc-prop-status { display:flex; align-items:center; justify-content:space-between; width:100%; padding:10px 14px 6px; }

/* tier badge */
.pc-tier { font-size:0.62rem; font-weight:800; letter-spacing:0.07em; padding:2px 7px; border-radius:100px; text-transform:uppercase; white-space:nowrap; }
.pc-tier-platinum { background:rgba(0,213,89,0.12); color:#00D559; border:1px solid rgba(0,213,89,0.26); }
.pc-tier-gold     { background:rgba(249,198,43,0.12); color:#F9C62B; border:1px solid rgba(249,198,43,0.26); }
.pc-tier-silver   { background:rgba(160,170,190,0.10); color:#A0AABE; border:1px solid rgba(160,170,190,0.20); }
.pc-tier-bronze   { background:rgba(107,122,154,0.10); color:#6B7A9A; border:1px solid rgba(107,122,154,0.20); }
.pc-tier-avoid    { background:rgba(242,67,54,0.12); color:#F24336; border:1px solid rgba(242,67,54,0.26); }
.pc-platform { font-size:0.52rem; color:#3A4460; font-family:'JetBrains Mono',monospace; }

/* headshot */
.pc-prop-hs-wrap { position:relative; margin:4px auto 10px; width:100px; height:100px; }
.pc-prop-hs { width:100px; height:100px; border-radius:50%; border:2.5px solid rgba(255,255,255,0.14); object-fit:cover; background:#1C2232; display:block; transition:border-color 0.25s, box-shadow 0.25s; box-shadow:0 4px 16px rgba(0,0,0,0.45); }
.pc-prop:hover .pc-prop-hs { border-color:rgba(45,158,255,0.35); box-shadow:0 4px 20px rgba(45,158,255,0.12), 0 4px 16px rgba(0,0,0,0.4); }
.pc-prop[open] .pc-prop-hs { border-color:rgba(0,213,89,0.40); box-shadow:0 4px 20px rgba(0,213,89,0.12); }

/* player info */
.pc-prop-team-pos { font-size:0.68rem; font-weight:600; color:#6B7A9A; text-align:center; margin-bottom:4px; }
.pc-prop-player-name { font-size:1.10rem; font-weight:800; color:#FFFFFF; text-align:center; letter-spacing:-0.01em; margin-bottom:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px; }
.pc-prop[open] .pc-prop-player-name { white-space:normal; max-width:400px; }
.pc-prop-game-info { font-size:0.60rem; color:#4A5568; text-align:center; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px; }

/* line block */
.pc-prop-line-area { width:100%; text-align:center; padding:14px 14px 6px; background:linear-gradient(180deg, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.12) 100%); margin:4px 0; border-top:1px solid rgba(255,255,255,0.03); border-bottom:1px solid rgba(255,255,255,0.03); }
.pc-prop-cur-label { font-size:0.58rem; color:#6B7A9A; margin-bottom:2px; }
.pc-prop-big-line { font-size:3.2rem; font-weight:900; color:#FFFFFF; font-family:'Bebas Neue','Inter',sans-serif; line-height:1; font-variant-numeric:tabular-nums; letter-spacing:-0.01em; text-shadow:0 2px 10px rgba(0,0,0,0.35); }
.pc-prop-stat-name { font-size:0.85rem; font-weight:600; color:#A0AABE; margin-top:4px; padding-bottom:8px; }

/* mini prob bar */
.pc-prop-prob-bar { width:calc(100% - 20px); margin:4px 10px 2px; height:5px; border-radius:100px; background:rgba(255,255,255,0.06); overflow:hidden; box-shadow:inset 0 1px 2px rgba(0,0,0,0.2); }
.pc-prop-prob-fill-over  { height:100%; border-radius:100px; background:linear-gradient(90deg,#00D559,#2D9EFF); }
.pc-prop-prob-fill-under { height:100%; border-radius:100px; background:linear-gradient(90deg,#F24336,#F9C62B); }
.pc-prop-prob-label { font-size:0.56rem; font-weight:700; text-align:center; margin-bottom:4px; }
.pc-prop-prob-label-over  { color:#00D559; }
.pc-prop-prob-label-under { color:#F24336; }

/* Less / More buttons */
.pc-btn-row { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:8px 16px 16px; width:100%; box-sizing:border-box; }
.pc-btn { display:flex; align-items:center; justify-content:center; gap:6px; padding:12px 6px; border-radius:12px; font-weight:800; font-size:1.0rem; letter-spacing:0.03em; border:1.5px solid transparent; transition:box-shadow 0.2s, transform 0.15s, filter 0.15s; white-space:nowrap; }
.pc-btn:hover { transform:translateY(-1px); filter:brightness(1.08); }
.pc-btn-over-active   { background:linear-gradient(180deg, #0FE868, #00C44E); color:#0D0F14; border-color:#00D559; box-shadow:0 3px 14px rgba(0,213,89,0.45), inset 0 1px 0 rgba(255,255,255,0.18); }
.pc-btn-over-inactive { background:rgba(0,213,89,0.06); color:rgba(0,213,89,0.45); border-color:rgba(0,213,89,0.15); box-shadow:inset 0 1px 3px rgba(0,0,0,0.15); }
.pc-btn-under-active  { background:linear-gradient(180deg, #F65B4F, #E02E24); color:#FFFFFF; border-color:#F24336; box-shadow:0 3px 14px rgba(242,67,54,0.40), inset 0 1px 0 rgba(255,255,255,0.12); }
.pc-btn-under-inactive{ background:rgba(242,67,54,0.06); color:rgba(242,67,54,0.45); border-color:rgba(242,67,54,0.15); box-shadow:inset 0 1px 3px rgba(0,0,0,0.15); }

/* ── Expanded detail panel (appears when card is clicked) ────── */
@keyframes pcPropExpand { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
.pc-prop-expanded {
  border-top: 1px solid rgba(255,255,255,0.07);
  padding: 12px 12px 14px;
  display: flex; flex-direction: column; gap: 10px;
  animation: pcPropExpand 0.22s cubic-bezier(0.22,1,0.36,1);
  background: linear-gradient(180deg, rgba(0,0,0,0.08) 0%, transparent 40%);
}

/* detail player header */
.pc-detail-hdr { display:flex; gap:10px; align-items:flex-start; padding-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.06); background:linear-gradient(135deg, rgba(255,255,255,0.015) 0%, transparent 60%); border-radius:10px; padding:10px; margin:-2px -2px 0; }
.pc-detail-hs { width:52px; height:52px; border-radius:50%; border:2px solid rgba(0,213,89,0.30); object-fit:cover; flex-shrink:0; background:#1C2232; box-shadow:0 3px 12px rgba(0,0,0,0.4), 0 0 8px rgba(0,213,89,0.06); }
.pc-detail-info { display:flex; flex-direction:column; gap:2px; min-width:0; }
.pc-detail-name { font-size:0.88rem; font-weight:800; color:#FFFFFF; }
.pc-detail-sub  { font-size:0.60rem; color:#6B7A9A; display:flex; flex-wrap:wrap; gap:4px; align-items:center; }
.pc-detail-team-badge { font-size:0.56rem; font-weight:700; padding:1px 7px; border-radius:100px; color:#fff; }

/* section labels */
.pc-sec-label { font-size:0.54rem; font-weight:700; color:#3A4460; text-transform:uppercase; letter-spacing:0.10em; margin-bottom:3px; }

/* win grade */
.pc-grade-row { display:flex; align-items:center; gap:6px; }
.pc-grade-badge { font-family:'JetBrains Mono',monospace; font-size:0.92rem; font-weight:900; width:34px; height:34px; display:flex; align-items:center; justify-content:center; border-radius:8px; flex-shrink:0; text-shadow:0 1px 6px currentColor; box-shadow:inset 0 1px 0 rgba(255,255,255,0.08), 0 2px 8px rgba(0,0,0,0.25); }
.pc-grade-info { display:flex; flex-direction:column; gap:1px; flex:1; min-width:0; }
.pc-grade-label { font-size:0.62rem; font-weight:700; color:#FFFFFF; }
.pc-grade-rec   { font-size:0.54rem; color:#6B7A9A; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pc-safe { display:flex; flex-direction:column; align-items:center; flex-shrink:0; }
.pc-safe-val { font-family:'JetBrains Mono',monospace; font-size:0.88rem; font-weight:800; color:#2D9EFF; }
.pc-safe-lbl { font-size:0.44rem; color:#3A4460; text-transform:uppercase; letter-spacing:0.06em; font-weight:700; }

/* alert badges */
.pc-badges { display:flex; gap:3px; flex-wrap:wrap; }
.pc-badge { font-size:0.54rem; font-weight:700; padding:2px 6px; border-radius:100px; white-space:nowrap; box-shadow:0 1px 3px rgba(0,0,0,0.15); transition:transform 0.15s; }
.pc-badge:hover { transform:translateY(-1px); }
.pc-badge-best      { background:rgba(249,198,43,0.12); color:#F9C62B; border:1px solid rgba(249,198,43,0.24); }
.pc-badge-uncertain { background:rgba(249,198,43,0.10); color:#F9C62B; border:1px solid rgba(249,198,43,0.20); }
.pc-badge-avoid     { background:rgba(242,67,54,0.12); color:#F24336; border:1px solid rgba(242,67,54,0.24); }
.pc-badge-trap      { background:rgba(242,67,54,0.14); color:#F24336; border:1px solid rgba(242,67,54,0.28); }
.pc-badge-risk      { background:rgba(249,198,43,0.10); color:#F9C62B; border:1px solid rgba(249,198,43,0.20); }
.pc-badge-line-warn { background:rgba(249,198,43,0.10); color:#F9C62B; border:1px solid rgba(249,198,43,0.18); }
.pc-badge-injury    { background:rgba(242,67,54,0.12); color:#F24336; border:1px solid rgba(242,67,54,0.24); }

/* rec banner */
.pc-rec-banner { font-size:0.60rem; font-weight:600; padding:5px 8px; border-radius:7px; background:linear-gradient(135deg, rgba(45,158,255,0.06) 0%, rgba(45,158,255,0.02) 100%); border:1px solid rgba(45,158,255,0.14); color:#A0AABE; text-align:center; box-shadow:inset 0 1px 0 rgba(255,255,255,0.02); }

/* trueline */
.pc-trueline { display:flex; justify-content:space-between; align-items:center; padding:5px 8px; border-radius:7px; background:linear-gradient(135deg, rgba(45,158,255,0.07) 0%, rgba(45,158,255,0.03) 100%); border:1px solid rgba(45,158,255,0.14); box-shadow:inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 4px rgba(0,0,0,0.12); }
.pc-trueline-lbl { font-size:0.60rem; color:#6B7A9A; }
.pc-trueline-val { font-family:'JetBrains Mono',monospace; font-size:0.82rem; font-weight:800; color:#2D9EFF; }

/* line compare */
.pc-line-compare { display:flex; align-items:center; gap:6px; padding:3px 8px; border-radius:6px; background:rgba(255,255,255,0.02); flex-wrap:wrap; }
.pc-lc-item { font-family:'JetBrains Mono',monospace; font-size:0.58rem; display:flex; align-items:center; gap:3px; }
.pc-lc-label { font-size:0.46rem; color:#3A4460; text-transform:uppercase; }
.pc-lc-val { font-weight:700; }
.pc-lc-sep { color:#1C2232; }

/* prob row */
.pc-prob-row { display:flex; align-items:center; gap:8px; }
.pc-prob-track { flex:1; height:5px; background:rgba(255,255,255,0.07); border-radius:100px; overflow:hidden; box-shadow:inset 0 1px 2px rgba(0,0,0,0.2); }
.pc-prob-fill-over  { height:100%; border-radius:100px; background:linear-gradient(90deg,#00D559,#2D9EFF); }
.pc-prob-fill-under { height:100%; border-radius:100px; background:linear-gradient(90deg,#F24336,#F9C62B); }
.pc-prob-pct { font-size:0.72rem; font-weight:800; color:#FFFFFF; min-width:32px; text-align:right; font-variant-numeric:tabular-nums; }
.pc-edge { display:inline-flex; align-items:center; padding:1px 6px; border-radius:100px; font-size:0.62rem; font-weight:700; }
.pc-edge-pos { background:rgba(0,213,89,0.10); color:#00D559; border:1px solid rgba(0,213,89,0.24); }
.pc-edge-neg { background:rgba(242,67,54,0.10); color:#F24336; border:1px solid rgba(242,67,54,0.24); }

/* prediction */
.pc-pred { font-size:0.64rem; font-weight:700; padding:3px 8px; border-radius:7px; text-align:center; }
.pc-pred-over    { background:rgba(0,213,89,0.08); color:#00D559; border:1px solid rgba(0,213,89,0.20); }
.pc-pred-under   { background:rgba(242,67,54,0.08); color:#F24336; border:1px solid rgba(242,67,54,0.20); }
.pc-pred-neutral { background:rgba(107,122,154,0.08); color:#6B7A9A; border:1px solid rgba(107,122,154,0.16); }

/* odds */
.pc-odds { display:flex; gap:5px; align-items:center; justify-content:center; flex-wrap:wrap; }
.pc-odds-chip { font-family:'JetBrains Mono',monospace; font-size:0.56rem; font-weight:700; padding:2px 7px; border-radius:5px; background:linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%); border:1px solid rgba(255,255,255,0.08); box-shadow:inset 0 1px 0 rgba(255,255,255,0.03); transition:transform 0.15s, background 0.15s; }
.pc-odds-chip:hover { transform:translateY(-1px); background:rgba(255,255,255,0.06); }
.pc-odds-over  { color:#00D559; }
.pc-odds-under { color:#F24336; }
.pc-odds-lbl   { font-size:0.44rem; color:#3A4460; margin-right:1px; }

/* confidence bar */
.pc-conf-hdr { display:flex; justify-content:space-between; font-size:0.60rem; color:#6B7A9A; }
.pc-conf-pct { font-weight:700; }
.pc-conf-track { height:5px; border-radius:3px; background:rgba(255,255,255,0.06); overflow:hidden; margin-top:3px; box-shadow:inset 0 1px 2px rgba(0,0,0,0.2); }
.pc-conf-fill { height:100%; border-radius:3px; transition:width 0.35s; box-shadow:0 0 6px currentColor; }

/* stdev */
.pc-stdev-row { display:flex; align-items:center; gap:6px; }
.pc-stdev-bar-wrap { flex:1; height:12px; position:relative; border-radius:3px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); overflow:hidden; }
.pc-stdev-marker { position:absolute; top:0; width:3px; height:100%; border-radius:1px; }
.pc-stdev-label { font-family:'JetBrains Mono',monospace; font-size:0.58rem; font-weight:700; flex-shrink:0; }
.pc-stdev-sublbl { font-size:0.44rem; color:#3A4460; flex-shrink:0; }

/* metrics */
.pc-metrics { display:grid; grid-template-columns:repeat(2,1fr); gap:5px; }
.pc-m { display:flex; flex-direction:column; align-items:center; background:linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02)); border-radius:8px; padding:6px 4px; border:1px solid rgba(255,255,255,0.06); box-shadow:inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 3px rgba(0,0,0,0.12); }
.pc-m-val { font-family:'JetBrains Mono',monospace; font-size:0.80rem; font-weight:700; color:#FFFFFF; }
.pc-m-lbl { font-size:0.48rem; color:#6B7A9A; text-transform:uppercase; letter-spacing:0.04em; margin-top:1px; }

/* matchup pills */
.pc-mx-row { display:flex; gap:3px; flex-wrap:wrap; }
.pc-mx-pill { font-family:'JetBrains Mono',monospace; font-size:0.52rem; font-weight:600; padding:2px 6px; border-radius:5px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); display:flex; align-items:center; gap:2px; }
.pc-mx-pill-lbl { font-size:0.44rem; color:#3A4460; }
.pc-mx-good    { color:#00D559; border-color:rgba(0,213,89,0.18); }
.pc-mx-bad     { color:#F24336; border-color:rgba(242,67,54,0.18); }
.pc-mx-neutral { color:#6B7A9A; }

/* distribution */
.pc-dist { display:flex; gap:3px; justify-content:space-around; flex-wrap:wrap; }
.pc-d { display:flex; flex-direction:column; align-items:center; padding:3px 6px; border-radius:6px; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.04); transition:background 0.15s; }
.pc-d:hover { background:rgba(255,255,255,0.04); }
.pc-d-val { font-family:'JetBrains Mono',monospace; font-size:0.66rem; font-weight:700; color:#6B7A9A; }
.pc-d-lbl { font-size:0.44rem; color:#3A4460; text-transform:uppercase; }
.pc-d-med  .pc-d-val { color:#FFFFFF; text-shadow:0 1px 4px rgba(255,255,255,0.15); }
.pc-d-proj .pc-d-val { color:#2D9EFF; text-shadow:0 1px 4px rgba(45,158,255,0.25); }

/* sparkline */
.pc-spark { display:flex; align-items:flex-end; gap:2px; height:26px; padding:3px 0; }
.pc-spark-bar { min-width:5px; flex:1; border-radius:2px 2px 0 0; box-shadow:0 0 3px currentColor; transition:opacity 0.15s; }
.pc-spark-bar:hover { opacity:0.85; }
.pc-spark-wrap { position:relative; }
.pc-spark-line { position:absolute; left:0; right:0; height:1px; border-top:1px dashed rgba(45,158,255,0.4); }
.pc-spark-lbl { font-size:0.44rem; color:#3A4460; text-align:center; margin-top:2px; }

/* context pills */
.pc-ctx { display:flex; flex-wrap:wrap; gap:3px; }
.pc-ctx-pill { font-size:0.52rem; padding:2px 6px; border-radius:5px; background:linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.015) 100%); border:1px solid rgba(255,255,255,0.07); color:#6B7A9A; font-family:'JetBrains Mono',monospace; box-shadow:inset 0 1px 0 rgba(255,255,255,0.02); transition:background 0.15s, transform 0.15s; }
.pc-ctx-pill:hover { background:rgba(255,255,255,0.05); transform:translateY(-1px); }

/* forces */
.pc-forces-bar-wrap { position:relative; margin-bottom:5px; }
.pc-forces-bar { display:flex; height:7px; border-radius:100px; overflow:hidden; background:rgba(255,255,255,0.04); box-shadow:inset 0 1px 2px rgba(0,0,0,0.2); }
.pc-forces-over-fill  { background:linear-gradient(90deg,#00D559,#2D9EFF); box-shadow:0 0 6px rgba(0,213,89,0.3); }
.pc-forces-under-fill { background:linear-gradient(90deg,#F9C62B,#F24336); box-shadow:0 0 6px rgba(242,67,54,0.3); }
.pc-forces-pct-row { display:flex; justify-content:space-between; margin-top:2px; }
.pc-forces-pct { font-family:'JetBrains Mono',monospace; font-size:0.50rem; font-weight:700; }
.pc-forces-pct-over  { color:#00D559; }
.pc-forces-pct-under { color:#F24336; }
.pc-forces-conflict { font-size:0.50rem; color:#F9C62B; text-align:center; margin-top:2px; }
.pc-forces { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:4px; }
.pc-forces-lbl { font-size:0.52rem; font-weight:700; margin-bottom:2px; }
.pc-forces-lbl-over  { color:#00D559; }
.pc-forces-lbl-under { color:#F24336; }
.pc-force-item { font-size:0.54rem; color:#6B7A9A; margin-bottom:2px; }
.pc-force-name { font-weight:600; color:#A0AABE; }
.pc-force-desc { font-size:0.46rem; color:#3A4460; margin-left:4px; }
.pc-force-none { font-size:0.52rem; color:#1C2232; font-style:italic; }

/* ensemble */
.pc-ensemble { display:flex; align-items:center; gap:6px; padding:4px 8px; border-radius:7px; background:linear-gradient(135deg, rgba(45,158,255,0.06) 0%, rgba(45,158,255,0.02) 100%); border:1px solid rgba(45,158,255,0.14); box-shadow:inset 0 1px 0 rgba(255,255,255,0.02), 0 1px 4px rgba(0,0,0,0.1); }
.pc-ens-icon { font-size:0.68rem; }
.pc-ens-text { font-size:0.54rem; color:#2D9EFF; }
.pc-ens-models { font-family:'JetBrains Mono',monospace; font-weight:700; }

/* breakdown */
.pc-breakdown { display:flex; flex-direction:column; gap:3px; }
.pc-bd-row { display:flex; align-items:center; gap:5px; }
.pc-bd-label { font-size:0.52rem; color:#6B7A9A; width:60px; flex-shrink:0; text-align:right; }
.pc-bd-score { font-family:'JetBrains Mono',monospace; font-size:0.52rem; font-weight:700; color:#FFFFFF; width:20px; text-align:right; flex-shrink:0; }
.pc-bd-track { flex:1; height:3px; border-radius:2px; background:rgba(255,255,255,0.06); overflow:hidden; box-shadow:inset 0 1px 2px rgba(0,0,0,0.15); }
.pc-bd-fill { height:100%; border-radius:2px; box-shadow:0 0 4px currentColor; }

/* key factors */
.pc-factors { display:flex; flex-direction:column; gap:2px; }
.pc-factors-title { font-size:0.56rem; font-weight:700; color:#6B7A9A; text-transform:uppercase; letter-spacing:0.04em; }
.pc-factor-item { font-size:0.54rem; color:#6B7A9A; }
.pc-factor-item::before { content:'\2713 '; color:#00D559; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width:768px) {
  .pc-card > summary { gap:10px; padding:12px 14px; }
  .pc-head { width:42px; height:42px; }
  .pc-name { font-size:0.95rem; }
  .pc-prop { width:220px; }
  .pc-prop[open] { width:340px; }
  .pc-prop-big-line { font-size:2.6rem; }
  .pc-prop-hs-wrap { width:80px; height:80px; }
  .pc-prop-hs { width:80px; height:80px; }
  .pc-identity { flex-wrap:wrap; }
  .pc-id-avatar { width:56px; height:56px; }
  .pc-id-stats { width:100%; justify-content:center; }
  .pc-prop-player-name { font-size:0.95rem; }
  .pc-btn { font-size:0.85rem; padding:8px 0; }
}
@media (max-width:480px) {
  .pc-head { width:36px; height:36px; }
  .pc-prop { width:170px; }
  .pc-prop[open] { width:280px; border-radius:16px; }
  .pc-prop-big-line { font-size:2.2rem; }
  .pc-prop-hs-wrap { width:64px; height:64px; }
  .pc-prop-hs { width:64px; height:64px; }
  .pc-prop-player-name { font-size:0.82rem; }
  .pc-prop-stat-name { font-size:0.62rem; }
  .pc-prop-team-pos { font-size:0.56rem; }
  .pc-btn { font-size:0.78rem; padding:6px 0; border-radius:8px; }
}
@media (max-width:360px) {
  .pc-prop { width:155px; }
  .pc-prop[open] { width:260px; }
  .pc-prop-big-line { font-size:1.9rem; }
  .pc-prop-hs-wrap { width:56px; height:56px; }
  .pc-prop-hs { width:56px; height:56px; }
  .pc-prop-player-name { font-size:0.76rem; }
}
"""


# ===================================================================
#  HELPERS
# ===================================================================

def _fmt(val, fallback="\u2014"):
    try:
        return f"{float(val):.1f}"
    except (TypeError, ValueError):
        return fallback


def _conf_color(pct):
    if pct >= 80: return "#00f0ff"
    if pct >= 65: return "#FFD700"
    if pct >= 50: return "#00b4ff"
    return "#94A3B8"


def _bd_color(score):
    if score >= 70: return "#00f0ff"
    if score >= 40: return "#ff5e00"
    return "#ff4444"


_STAT_EMOJI = {
    "points": "\U0001f3c0", "rebounds": "\U0001f4ca", "assists": "\U0001f3af",
    "threes": "\U0001f3af", "steals": "\u26a1", "blocks": "\U0001f6e1\ufe0f",
    "turnovers": "\u274c",
}

# Win-score grade colors
_GRADE_COLORS = {
    "A+": ("#00f0ff", "rgba(0,240,255,0.15)"),
    "A":  ("#00d4ff", "rgba(0,212,255,0.12)"),
    "B+": ("#5eead4", "rgba(94,234,212,0.12)"),
    "B":  ("#a3e635", "rgba(163,230,53,0.12)"),
    "C":  ("#fbbf24", "rgba(251,191,36,0.12)"),
    "D":  ("#fb923c", "rgba(251,146,60,0.12)"),
    "F":  ("#ef4444", "rgba(239,68,68,0.12)"),
}

# Stat type -> season avg key
_STAT_TO_SEASON_KEY = {
    "points": "season_pts_avg",
    "rebounds": "season_reb_avg",
    "assists": "season_ast_avg",
    "threes": "season_threes_avg",
    "steals": "season_stl_avg",
    "blocks": "season_blk_avg",
    "turnovers": "season_tov_avg",
    "pts_reb": "season_pts_reb_avg",
    "pts_ast": "season_pts_ast_avg",
    "reb_ast": "season_reb_ast_avg",
    "pts_reb_ast": "season_pra_avg",
    "blk_stl": "season_blk_stl_avg",
}

_TIER_BORDER = {
    "platinum": "#c800ff", "gold": "#ff5e00",
    "silver": "#b0c0d8", "bronze": "#64748b",
}
_TIER_RANK = {"platinum": 4, "gold": 3, "silver": 2, "bronze": 1, "avoid": 0}


def _mx_cls(val, neutral=1.0, threshold=0.03):
    """Return matchup pill CSS class based on factor value."""
    try:
        v = float(val)
        if v > neutral + threshold:
            return "pc-mx-good"
        if v < neutral - threshold:
            return "pc-mx-bad"
    except (TypeError, ValueError):
        pass
    return "pc-mx-neutral"


def _mx_cls_inv(val, neutral=1.0, threshold=0.03):
    """Inverse: lower = better (defense factor)."""
    try:
        v = float(val)
        if v < neutral - threshold:
            return "pc-mx-good"
        if v > neutral + threshold:
            return "pc-mx-bad"
    except (TypeError, ValueError):
        pass
    return "pc-mx-neutral"


# ===================================================================
#  SINGLE PROP CARD
# ===================================================================

def _build_prop_card(result, player_info=None):
    """Build HTML for one PP-style prop card (horizontal scroll, expand on click)."""
    r = result
    pi = player_info or {}

    # -- Player display info ------------------------------------------
    headshot = pi.get("headshot_url") or _FALLBACK_HEADSHOT
    p_team = _e(str(pi.get("team") or ""))
    p_pos  = _e(str(pi.get("position") or ""))
    p_name = _e(str(pi.get("name") or ""))
    team_bg = pi.get("team_bg") or "#2A3350"
    team_pos_str = " - ".join(filter(None, [p_team, p_pos]))

    # -- Core values --------------------------------------------------
    tier = (r.get("tier") or "Bronze").strip()
    tier_lower = tier.lower()
    confidence = float(r.get("confidence_score") or 0)
    safe_score = f"{min(10.0, confidence / 10.0):.1f}"
    stat_type = (r.get("stat_type") or "").replace("_", " ").title()
    _line_raw = r.get("line")
    if _line_raw is None:
        _line_raw = r.get("prop_line")
    line = _fmt(_line_raw)
    true_line = _fmt(r.get("adjusted_projection"))
    prob_over = float(r.get("probability_over") or 0.5)
    edge = float(r.get("edge_percentage") or 0)
    platform = _e(str(r.get("platform") or ""))
    if platform == "PrizePicks":
        platform = "Smart Pick"

    direction = (r.get("direction") or "").upper()
    if not direction:
        direction = "OVER" if prob_over >= 0.5 else "UNDER"

    stat_lower = (r.get("stat_type") or "").lower()

    # Glow class
    glow = ""
    if tier_lower in ("platinum", "gold"):
        glow = f" pc-prop-{tier_lower}"

    # Game info
    opponent = _e(str(r.get("opponent") or ""))
    is_home  = r.get("is_home")
    if opponent:
        ha = "vs" if is_home else "@"
        game_info = f"{ha} {opponent}"
    else:
        game_info = ""

    # Current value label
    cur_val = r.get("current_value")
    cur_label = ""
    if cur_val is not None:
        try:
            cur_label = f'<div class="pc-prop-cur-label">Cur. {float(cur_val):.0f}</div>'
        except (ValueError, TypeError):
            pass

    # OVER/UNDER button & prob setup
    over_pct  = f"{prob_over * 100:.0f}%"
    under_pct = f"{(1 - prob_over) * 100:.0f}%"
    over_btn_cls  = "pc-btn-over-active"  if direction == "OVER"  else "pc-btn-over-inactive"
    under_btn_cls = "pc-btn-under-active" if direction == "UNDER" else "pc-btn-under-inactive"
    prob_fill_cls = "pc-prop-prob-fill-over" if direction == "OVER" else "pc-prop-prob-fill-under"
    prob_w = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
    prob_lbl_cls = "pc-prop-prob-label-over" if direction == "OVER" else "pc-prop-prob-label-under"
    disp_pct = over_pct if direction == "OVER" else under_pct

    # == CARD FACE (summary — the PP card front) =======================
    face_html = (
        f'<div class="pc-prop-status">'
        f'<span class="pc-tier pc-tier-{tier_lower}">{_e(tier)}</span>'
        f'{("<span class=\"pc-platform\">" + platform + "</span>") if platform else ""}'
        f'</div>'
        f'<div class="pc-prop-hs-wrap">'
        f'<img class="pc-prop-hs" src="{_e(headshot)}" alt="{p_name}" '
        f'onerror="this.onerror=null;this.src=\'{_FALLBACK_HEADSHOT}\'">'
        f'</div>'
        f'<div class="pc-prop-team-pos">{team_pos_str}</div>'
        f'<div class="pc-prop-player-name">{p_name}</div>'
        f'<div class="pc-prop-game-info">{game_info}</div>'
        f'<div class="pc-prop-line-area">'
        f'{cur_label}'
        f'<div class="pc-prop-big-line">{line}</div>'
        f'<div class="pc-prop-stat-name">{_e(stat_type)}</div>'
        f'</div>'
        f'<div class="pc-prop-prob-bar">'
        f'<div class="{prob_fill_cls}" style="width:{prob_w:.1f}%;"></div>'
        f'</div>'
        f'<div class="pc-prop-prob-label {prob_lbl_cls}">{disp_pct}</div>'
        f'<div class="pc-btn-row">'
        f'<div class="pc-btn {under_btn_cls}">&#8595; Less</div>'
        f'<div class="pc-btn {over_btn_cls}">&#8593; More</div>'
        f'</div>'
    )

    # == Win Grade + Recommendation ====================================
    grade = _e(r.get("win_score_grade") or "")
    grade_label = _e(r.get("win_score_label") or "")
    recommendation = _e(str(r.get("recommendation") or ""))
    gc = _GRADE_COLORS.get(grade, ("#94a3b8", "rgba(148,163,184,0.12)"))

    grade_row = ""
    if grade:
        grade_row = (
            f'<div class="pc-grade-row">'
            f'<div class="pc-grade-badge" style="color:{gc[0]};background:{gc[1]};">{grade}</div>'
            f'<div class="pc-grade-info">'
            f'<span class="pc-grade-label">{grade_label}</span>'
            f'<span class="pc-grade-rec">{recommendation}</span>'
            f'</div>'
            f'<div class="pc-safe"><span class="pc-safe-val">{safe_score}</span>'
            f'<span class="pc-safe-lbl">SAFE</span></div>'
            f'</div>'
        )

    # == Recommendation banner =========================================
    rec_html = f'<div class="pc-rec-banner">{recommendation}</div>' if recommendation else ""

    # Detail player header (shown inside expanded panel)
    detail_hdr = (
        f'<div class="pc-detail-hdr">'
        f'<img class="pc-detail-hs" src="{_e(headshot)}" alt="{p_name}" '
        f'onerror="this.onerror=null;this.src=\'{_FALLBACK_HEADSHOT}\'">'
        f'<div class="pc-detail-info">'
        f'<div class="pc-detail-name">{p_name}</div>'
        f'<div class="pc-detail-sub">'
        f'<span class="pc-detail-team-badge" style="background:{team_bg};">{p_team}</span>'
        f'{(" \u00b7 " + p_pos) if p_pos else ""}'
        f'{(" \u00b7 " + game_info) if game_info else ""}'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    badges = ""
    if r.get("_is_best_pick"):
        badges += '<span class="pc-badge pc-badge-best">\u2b50 Top Pick</span>'
    if r.get("is_uncertain"):
        badges += '<span class="pc-badge pc-badge-uncertain">\u26a0\ufe0f Uncertain</span>'
    if r.get("should_avoid"):
        badges += '<span class="pc-badge pc-badge-avoid">\U0001f6ab Caution</span>'

    # Trap line alert
    trap = r.get("trap_line_result") or {}
    if trap.get("is_trap"):
        trap_msg = _e(str(trap.get("warning_message") or "Trap line detected"))
        badges += f'<span class="pc-badge pc-badge-trap">\U0001f6a8 {trap_msg}</span>'

    # Risk flags
    risk_flags = r.get("risk_flags") or []
    for rf in risk_flags[:3]:
        badges += f'<span class="pc-badge pc-badge-risk">\u26a0 {_e(str(rf))}</span>'

    # Line reliability warning
    line_warn = r.get("line_reliability_warning")
    if line_warn:
        badges += f'<span class="pc-badge pc-badge-line-warn">\U0001f4cb {_e(str(line_warn))}</span>'

    # Injury/status
    p_status = r.get("player_status")
    p_note = r.get("player_status_note")
    if p_status and "healthy" not in str(p_status).lower():
        stext = _e(str(p_status))
        if p_note:
            stext += f" - {_e(str(p_note))}"
        badges += f'<span class="pc-badge pc-badge-injury">\U0001f3e5 {stext}</span>'

    badges_html = f'<div class="pc-badges">{badges}</div>' if badges else ""

    # == True line + season avg comparison ============================
    season_key = _STAT_TO_SEASON_KEY.get(stat_lower)
    season_avg = None
    if season_key:
        season_avg = r.get(season_key)

    trueline = (
        f'<div class="pc-trueline">'
        f'<span class="pc-trueline-lbl">True Line ({_e(direction)})</span>'
        f'<span class="pc-trueline-val">{true_line}</span>'
        f'</div>'
    )

    line_compare = ""
    if season_avg is not None:
        try:
            sa = float(season_avg)
            sa_str = f"{sa:.1f}"
            line_compare = (
                f'<div class="pc-line-compare">'
                f'<div class="pc-lc-item"><span class="pc-lc-label">Book</span>'
                f'<span class="pc-lc-val" style="color:#e2e8f0;">{line}</span></div>'
                f'<span class="pc-lc-sep">|</span>'
                f'<div class="pc-lc-item"><span class="pc-lc-label">Avg</span>'
                f'<span class="pc-lc-val" style="color:#5eead4;">{sa_str}</span></div>'
                f'<span class="pc-lc-sep">|</span>'
                f'<div class="pc-lc-item"><span class="pc-lc-label">Proj</span>'
                f'<span class="pc-lc-val" style="color:#00f0ff;">{true_line}</span></div>'
                f'</div>'
            )
        except (ValueError, TypeError):
            pass

    # == Odds display =================================================
    odds_html = ""
    o_odds = r.get("over_odds")
    u_odds = r.get("under_odds")
    if o_odds is not None or u_odds is not None:
        o_str = f"{int(o_odds):+d}" if o_odds is not None else "\u2014"
        u_str = f"{int(u_odds):+d}" if u_odds is not None else "\u2014"
        odds_html = (
            f'<div class="pc-odds">'
            f'<span class="pc-odds-chip pc-odds-over"><span class="pc-odds-lbl">O</span>{_e(o_str)}</span>'
            f'<span class="pc-odds-chip pc-odds-under"><span class="pc-odds-lbl">U</span>{_e(u_str)}</span>'
            f'</div>'
        )

    # == Prediction pill =============================================
    prediction = _e(str(r.get("prediction") or ""))
    if "over" in prediction.lower():
        pred_cls = "pc-pred-over"
    elif "under" in prediction.lower():
        pred_cls = "pc-pred-under"
    else:
        pred_cls = "pc-pred-neutral"
    pred_html = f'<div class="pc-pred {pred_cls}">{prediction}</div>' if prediction else ""

    # == Confidence bar ==============================================
    conf_pct = max(0.0, min(100.0, confidence))
    cc = _conf_color(conf_pct)
    conf = (
        f'<div class="pc-conf-hdr"><span>Confidence</span>'
        f'<span class="pc-conf-pct" style="color:{cc};">{conf_pct:.0f}%</span></div>'
        f'<div class="pc-conf-track">'
        f'<div class="pc-conf-fill" style="width:{conf_pct}%;background:{cc};"></div>'
        f'</div>'
    )

    # == Std devs from line indicator ================================
    stdev_html = ""
    std_devs = r.get("std_devs_from_line")
    if std_devs is not None:
        try:
            sd = float(std_devs)
            # Scale: -3..+3 mapped to 0..100%
            pct = max(0, min(100, (sd + 3) / 6 * 100))
            sd_color = "#00ff9d" if sd > 0.5 else ("#ff5e00" if sd < -0.5 else "#94a3b8")
            stdev_html = (
                f'<div class="pc-stdev-row">'
                f'<span class="pc-stdev-sublbl">LINE</span>'
                f'<div class="pc-stdev-bar-wrap">'
                f'<div class="pc-stdev-marker" style="left:50%;background:rgba(255,255,255,0.15);"></div>'
                f'<div class="pc-stdev-marker" style="left:{pct:.1f}%;background:{sd_color};"></div>'
                f'</div>'
                f'<span class="pc-stdev-label" style="color:{sd_color};">{sd:+.2f}\u03c3</span>'
                f'</div>'
            )
        except (ValueError, TypeError):
            pass

    # == Matchup factors row =========================================
    mx_items = []
    pace = r.get("pace_factor")
    if pace is not None:
        try:
            mx_items.append(("Pace", f"{float(pace):.2f}x", _mx_cls(pace)))
        except (ValueError, TypeError):
            pass
    defense = r.get("defense_factor")
    if defense is not None:
        try:
            mx_items.append(("Def", f"{float(defense):.2f}x", _mx_cls_inv(defense)))
        except (ValueError, TypeError):
            pass
    home_away = r.get("home_away_factor")
    if home_away is not None:
        try:
            mx_items.append(("H/A", f"{float(home_away):.2f}x", _mx_cls(home_away)))
        except (ValueError, TypeError):
            pass
    rest = r.get("rest_factor")
    if rest is not None:
        try:
            mx_items.append(("Rest", f"{float(rest):.2f}x", _mx_cls(rest)))
        except (ValueError, TypeError):
            pass
    blowout = r.get("blowout_risk")
    if blowout is not None:
        try:
            bv = float(blowout)
            bcls = "pc-mx-bad" if bv >= 0.20 else ("pc-mx-neutral" if bv >= 0.10 else "pc-mx-good")
            mx_items.append(("Blowout", f"{bv * 100:.0f}%", bcls))
        except (ValueError, TypeError):
            pass

    mx_html = ""
    if mx_items:
        pills = "".join(
            f'<span class="pc-mx-pill {cls}"><span class="pc-mx-pill-lbl">{_e(lbl)}</span> {_e(val)}</span>'
            for lbl, val, cls in mx_items
        )
        mx_html = f'<div class="pc-mx-row">{pills}</div>'

    # == Metrics =====================================================
    prob_pct = f"{prob_over * 100:.0f}%"
    edge_disp = f"{edge:+.1f}%"
    comp_win = r.get("composite_win_score")
    comp_str = f"{float(comp_win):.0f}" if comp_win is not None else "\u2014"
    metrics = (
        f'<div class="pc-metrics">'
        f'<div class="pc-m"><span class="pc-m-val">{prob_pct}</span><span class="pc-m-lbl">Prob</span></div>'
        f'<div class="pc-m"><span class="pc-m-val">{confidence:.0f}</span><span class="pc-m-lbl">SAFE</span></div>'
        f'<div class="pc-m"><span class="pc-m-val">{edge_disp}</span><span class="pc-m-lbl">Edge</span></div>'
        f'<div class="pc-m"><span class="pc-m-val">{comp_str}</span><span class="pc-m-lbl">Win</span></div>'
        f'</div>'
    )

    # == Distribution ================================================
    p10 = _fmt(r.get("percentile_10"))
    p50 = _fmt(r.get("percentile_50"))
    p90 = _fmt(r.get("percentile_90"))
    std = _fmt(r.get("simulated_std"))
    proj = _fmt(r.get("adjusted_projection"))
    dist = (
        f'<div class="pc-dist">'
        f'<div class="pc-d"><span class="pc-d-val">{p10}</span><span class="pc-d-lbl">P10</span></div>'
        f'<div class="pc-d pc-d-med"><span class="pc-d-val">{p50}</span><span class="pc-d-lbl">MED</span></div>'
        f'<div class="pc-d"><span class="pc-d-val">{p90}</span><span class="pc-d-lbl">P90</span></div>'
        f'<div class="pc-d"><span class="pc-d-val">{std}</span><span class="pc-d-lbl">&sigma;</span></div>'
        f'<div class="pc-d pc-d-proj"><span class="pc-d-val">{proj}</span><span class="pc-d-lbl">Proj</span></div>'
        f'</div>'
    )

    # == Recent form sparkline =======================================
    spark_html = ""
    recent_results = r.get("recent_form_results") or []
    if recent_results and len(recent_results) >= 3:
        try:
            vals = [float(v) for v in recent_results[-10:]]
            mx = max(vals) if vals else 1
            if mx <= 0:
                mx = 1
            line_val = float(r.get("line") or 0)
            line_pct_pos = min(100, max(0, (line_val / mx) * 100)) if mx > 0 else 50

            bars = []
            for v in vals:
                h = max(2, (v / mx) * 28)
                color = "#00ff9d" if v >= line_val else "#ff5e00"
                bars.append(f'<div class="pc-spark-bar" style="height:{h:.0f}px;background:{color};"></div>')
            spark_html = (
                f'<div class="pc-spark-wrap">'
                f'<div class="pc-spark">{"".join(bars)}</div>'
                f'<div class="pc-spark-line" style="bottom:{line_pct_pos:.0f}%;"></div>'
                f'</div>'
                f'<div class="pc-spark-lbl">Last {len(vals)} games (line={line})</div>'
            )
        except (ValueError, TypeError):
            pass

    # == Context pills ===============================================
    ctx_items = []
    form = r.get("recent_form_ratio")
    if form is not None:
        try:
            fv = float(form)
            tag = "\U0001f525 Hot" if fv >= 1.05 else ("\u2744\ufe0f Cold" if fv <= 0.95 else "\u27a1\ufe0f Neutral")
            ctx_items.append(f"{tag} ({fv:.2f}x)")
        except (ValueError, TypeError):
            pass
    adj = r.get("overall_adjustment")
    if adj is not None:
        try:
            ctx_items.append(f"Matchup {float(adj):.2f}x")
        except (ValueError, TypeError):
            pass
    gp = r.get("games_played")
    if gp is not None:
        ctx_items.append(f"{gp} GP")
    mins = r.get("projected_minutes")
    if mins is not None:
        try:
            ctx_items.append(f"{float(mins):.0f} min proj")
        except (ValueError, TypeError):
            pass
    min_trend = r.get("minutes_trend_indicator")
    if min_trend:
        ctx_items.append(f"Min: {_e(str(min_trend))}")

    ctx_html = ""
    if ctx_items:
        pills = "".join(f'<span class="pc-ctx-pill">{_e(c)}</span>' for c in ctx_items)
        ctx_html = f'<div class="pc-ctx">{pills}</div>'

    # == Forces ======================================================
    forces = r.get("forces") or {}
    over_forces = forces.get("over_forces") or []
    under_forces = forces.get("under_forces") or []
    o_str_ = sum(float(f.get("strength", 1)) for f in over_forces if isinstance(f, dict))
    u_str_ = sum(float(f.get("strength", 1)) for f in under_forces if isinstance(f, dict))
    total = o_str_ + u_str_
    o_pct = (o_str_ / total * 100) if total > 0 else 50
    u_pct = 100 - o_pct

    conflict = forces.get("conflict_severity")
    conflict_html = ""
    if conflict is not None:
        try:
            cv = float(conflict)
            if cv >= 0.6:
                conflict_html = f'<div class="pc-forces-conflict">\u26a0 High conflict ({cv:.0%})</div>'
            elif cv >= 0.4:
                conflict_html = f'<div class="pc-forces-conflict">Moderate conflict ({cv:.0%})</div>'
        except (ValueError, TypeError):
            pass

    def _fi(flist):
        if not flist:
            return '<span class="pc-force-none">None</span>'
        items = []
        for f in flist:
            if not isinstance(f, dict):
                continue
            s = max(1, min(5, round(float(f.get("strength", 1)))))
            name = _e(str(f.get("name", "")))
            desc = f.get("description") or ""
            desc_html = f'<span class="pc-force-desc">{_e(str(desc))}</span>' if desc else ""
            items.append(
                f'<div class="pc-force-item">'
                f'{"\u2b50" * s} <span class="pc-force-name">{name}</span>'
                f'{desc_html}</div>'
            )
        return "".join(items) or '<span class="pc-force-none">None</span>'

    forces_html = (
        f'<div class="pc-forces-bar-wrap">'
        f'<div class="pc-forces-bar">'
        f'<div class="pc-forces-over-fill" style="width:{o_pct:.1f}%;"></div>'
        f'<div class="pc-forces-under-fill" style="width:{u_pct:.1f}%;"></div>'
        f'</div>'
        f'<div class="pc-forces-pct-row">'
        f'<span class="pc-forces-pct pc-forces-pct-over">{o_pct:.0f}%</span>'
        f'<span class="pc-forces-pct pc-forces-pct-under">{u_pct:.0f}%</span>'
        f'</div>{conflict_html}</div>'
        f'<div class="pc-forces">'
        f'<div><div class="pc-forces-lbl pc-forces-lbl-over">\u25b2 OVER ({len(over_forces)})</div>{_fi(over_forces)}</div>'
        f'<div><div class="pc-forces-lbl pc-forces-lbl-under">\u25bc UNDER ({len(under_forces)})</div>{_fi(under_forces)}</div>'
        f'</div>'
    )

    # == Ensemble info ================================================
    ens_html = ""
    if r.get("ensemble_used"):
        em = r.get("ensemble_models") or "?"
        ed = _e(str(r.get("ensemble_disagreement") or ""))
        ens_html = (
            f'<div class="pc-ensemble">'
            f'<span class="pc-ens-icon">\U0001f9e0</span>'
            f'<span class="pc-ens-text">'
            f'<span class="pc-ens-models">{em} models</span>'
        )
        if ed:
            ens_html += f' &middot; {ed}'
        ens_html += '</span></div>'

    # == Breakdown bars ==============================================
    breakdown = r.get("score_breakdown") or {}
    bd_html = ""
    if breakdown:
        rows = []
        for factor, score in breakdown.items():
            try:
                sv = float(score or 0)
            except (ValueError, TypeError):
                continue
            label = _e(factor.replace("_score", "").replace("_", " ").title())
            w = min(100, max(0, sv))
            rows.append(
                f'<div class="pc-bd-row">'
                f'<span class="pc-bd-label">{label}</span>'
                f'<span class="pc-bd-score">{sv:.0f}</span>'
                f'<div class="pc-bd-track"><div class="pc-bd-fill" style="width:{w:.1f}%;background:{_bd_color(sv)};"></div></div>'
                f'</div>'
            )
        if rows:
            bd_html = f'<div class="pc-breakdown">{"".join(rows)}</div>'

    # == Key factors =================================================
    factors_html = ""
    bonus_factors = []
    if r.get("ensemble_used"):
        bonus_factors.append(f"Ensemble model ({r.get('ensemble_models', '?')} models)")
    gp_val = r.get("games_played")
    if gp_val:
        try:
            if int(gp_val) >= 30:
                bonus_factors.append(f"Large sample ({gp_val} games)")
        except (ValueError, TypeError):
            pass
    if r.get("line_verified"):
        bonus_factors.append("Line verified across books")
    teammate_notes = r.get("teammate_out_notes") or []
    for tn in teammate_notes[:3]:
        bonus_factors.append(str(tn))
    # Include avoid reasons too
    avoid_reasons = r.get("avoid_reasons") or []
    for ar in avoid_reasons[:2]:
        bonus_factors.append(f"\u26a0 {str(ar)}")
    if bonus_factors:
        items = "".join(f'<div class="pc-factor-item">{_e(bf)}</div>' for bf in bonus_factors)
        factors_html = f'<div class="pc-factors"><div class="pc-factors-title">Key Factors</div>{items}</div>'

    # == Prob row (full version for expanded) ========================
    edge_cls = "pc-edge-pos" if edge >= 0 else "pc-edge-neg"
    edge_disp = f"{edge:+.1f}%"
    prob_row_html = (
        f'<div class="pc-prob-row">'
        f'<div class="pc-prob-track">'
        f'<div class="pc-prob-fill-{"over" if direction == "OVER" else "under"}" '
        f'style="width:{prob_w:.1f}%;"></div>'
        f'</div>'
        f'<span class="pc-prob-pct">{disp_pct}</span>'
        f'<span class="pc-edge {edge_cls}">{edge_disp}</span>'
        f'</div>'
    )

    # == EXPANDED DETAIL PANEL ========================================
    expanded_html = (
        f'<div class="pc-prop-expanded">'
        f'{detail_hdr}'
        f'{grade_row}'
        f'{badges_html}'
        f'{rec_html}'
        f'<div class="pc-sec-label">Line &amp; Projection</div>'
        f'{trueline}{line_compare}'
        f'<div class="pc-sec-label">Probability &amp; Edge</div>'
        f'{prob_row_html}{odds_html}{pred_html}'
        f'<div style="padding:2px 0;">{conf}</div>'
        f'{stdev_html}'
        f'<div class="pc-sec-label">Analysis</div>'
        f'{metrics}{mx_html}{dist}{spark_html}{ctx_html}'
        f'<div class="pc-sec-label">Forces</div>'
        f'{forces_html}'
        f'{ens_html}{bd_html}{factors_html}'
        f'</div>'
    )

    return (
        f'<details class="pc-prop{glow}">'
        f'<summary>{face_html}</summary>'
        f'{expanded_html}'
        f'</details>'
    )


# ===================================================================
#  PLAYER ROW (SUMMARY + EXPANDABLE BODY)
# ===================================================================

def build_player_card(player_name, vitals, props):
    """Build one expandable player row."""
    safe_name = _e(player_name)
    headshot = _e((vitals.get("headshot_url") or "") or "")
    if not headshot:
        headshot = _e(_get_headshot_url(player_name) or "")
    team = _e(vitals.get("team") or "N/A")

    prop_count = len(props)
    prop_label = f"{prop_count} prop{'s' if prop_count != 1 else ''}"

    best_edge = 0.0
    best_grade = ""
    best_grade_label = ""
    for p in props:
        try:
            e = abs(float(p.get("edge_percentage") or p.get("edge") or 0))
            if e > best_edge:
                best_edge = e
        except (ValueError, TypeError):
            pass
        g = p.get("win_score_grade") or ""
        if g and (not best_grade or _grade_rank(g) > _grade_rank(best_grade)):
            best_grade = g
            best_grade_label = p.get("win_score_label") or ""

    best_edge_str = f"{best_edge:.1f}%"

    # Determine best tier for accent border
    best_tier = "bronze"
    for p in props:
        pt = (p.get("tier") or "bronze").strip().lower()
        if _TIER_RANK.get(pt, 0) > _TIER_RANK.get(best_tier, 0):
            best_tier = pt
    border_color = _TIER_BORDER.get(best_tier, "#64748b")

    # Expanded identity header — compute team_bg first so player_info can use it
    position = _e(vitals.get("position") or "")
    pos_label = f" \u00b7 {position}" if position else ""
    team_colors = get_team_colors(vitals.get("team") or "")
    team_bg = team_colors[0] if team_colors else "#4a5568"

    # Build prop cards with player_info so each PP card face shows headshot + name
    player_info = {
        "name": player_name,
        "headshot_url": headshot,
        "team": vitals.get("team") or "",
        "position": vitals.get("position") or "",
        "team_bg": team_bg,
    }
    cards = "".join(_build_prop_card(p, player_info=player_info) for p in props)

    # Summary win grade badge
    sum_grade_html = ""
    if best_grade:
        gc = _GRADE_COLORS.get(best_grade, ("#94a3b8", "rgba(148,163,184,0.12)"))
        sum_grade_html = f'<span class="pc-sum-grade" style="color:{gc[0]};background:{gc[1]};">{_e(best_grade)}</span>'

    # Opponent + home/away from first prop
    opponent = ""
    is_home = None
    if props:
        opponent = _e(str(props[0].get("opponent") or ""))
        is_home = props[0].get("is_home")
    opp_html = ""
    if opponent:
        ha = "Home" if is_home else ("Away" if is_home is not None else "")
        ha_label = f" ({ha})" if ha else ""
        opp_html = f'<span class="pc-id-opp">vs {opponent}{ha_label}</span>'

    # Injury/status from first prop
    status_html = ""
    if props:
        ps = props[0].get("player_status") or ""
        if ps and "healthy" not in ps.lower():
            pn = props[0].get("player_status_note") or ""
            stxt = _e(ps)
            if pn:
                stxt += f" - {_e(pn)}"
            status_html = f'<span class="pc-id-status">{stxt}</span>'

    season = vitals.get("season_stats") or {}
    stat_pills = ""
    for key, label in [("ppg", "PPG"), ("rpg", "RPG"), ("apg", "APG"), ("avg_minutes", "MIN")]:
        val = season.get(key)
        if val is not None:
            try:
                stat_pills += (
                    f'<div class="pc-stat-pill">'
                    f'<span class="pc-stat-pill-val">{float(val):.1f}</span>'
                    f'<span class="pc-stat-pill-lbl">{label}</span></div>'
                )
            except (ValueError, TypeError):
                pass

    stats_section = f'<div class="pc-id-stats">{stat_pills}</div>' if stat_pills else ""
    id_header = (
        f'<div class="pc-identity">'
        f'<img class="pc-id-avatar" src="{headshot}" alt="{safe_name}" '
        f'onerror="this.onerror=null;this.src=\'{_FALLBACK_HEADSHOT}\'">'
        f'<div class="pc-id-info">'
        f'<span class="pc-id-name">{safe_name}</span>'
        f'<span class="pc-id-sub">'
        f'<span class="pc-id-team-badge" style="background:{team_bg};color:#fff;">{team}</span>'
        f'{pos_label} {opp_html} {status_html}</span>'
        f'</div>'
        f'{stats_section}'
        f'</div>'
    )

    # PP/DK-style team badge for summary (reuse team_bg already set above)
    return (
        f'<details class="pc-card" style="border-left-color:{border_color};">'
        f'<summary>'
        f'<span class="pc-arrow">&#9654;</span>'
        f'<img class="pc-head" src="{headshot}" alt="{safe_name}" '
        f'onerror="this.onerror=null;this.src=\'{_FALLBACK_HEADSHOT}\'">'
        f'<div style="display:flex;flex-direction:column;gap:2px;min-width:0;flex:1;">'
        f'<span class="pc-name">{safe_name}</span>'
        f'<div style="display:flex;align-items:center;gap:5px;">'
        f'<span class="pc-sum-team" style="background:{team_bg};">{team}</span>'
        f'<span class="pc-sum-props">{prop_label}</span>'
        f'</div>'
        f'</div>'
        f'<span class="pc-sum-edge">Edge {best_edge_str}</span>'
        f'{sum_grade_html}'
        f'</summary>'
        f'<div class="pc-body">{id_header}<div class="pc-props-scroll">{cards}</div></div>'
        f'</details>'
    )


def _grade_rank(g):
    """Return numeric rank for a letter grade."""
    return {"A+": 7, "A": 6, "B+": 5, "B": 4, "C": 3, "D": 2, "F": 1}.get(g, 0)


# ===================================================================
#  FULL MATRIX COMPILER
# ===================================================================

def compile_player_card_matrix(grouped_players):
    """Compile all players into a complete HTML block with embedded CSS."""
    if not grouped_players:
        return (
            f"<style>{PLAYER_CARD_CSS}</style>"
            '<div style="text-align:center;color:#64748b;padding:40px;">'
            "No analysis results to display.</div>"
        )

    cards = []
    for name, data in grouped_players.items():
        vitals = data.get("vitals") or {}
        props = data.get("props") or []
        if props:
            cards.append(build_player_card(name, vitals, props))

    return (
        f"<style>{PLAYER_CARD_CSS}</style>"
        f'<div class="pc-grid">{"".join(cards)}</div>'
    )


def compile_player_cards_flat(grouped_players):
    """Compile all players' prop cards into a single horizontal scroll row.

    Unlike ``compile_player_card_matrix`` which nests props inside collapsible
    per-player rows, this outputs every prop card side-by-side in one
    horizontal strip — no collapsibles at all.
    """
    if not grouped_players:
        return (
            f"<style>{PLAYER_CARD_CSS}</style>"
            '<div style="text-align:center;color:#64748b;padding:40px;">'
            "No analysis results to display.</div>"
        )

    all_cards = []
    for name, data in grouped_players.items():
        vitals = data.get("vitals") or {}
        props = data.get("props") or []
        if not props:
            continue

        headshot = (vitals.get("headshot_url") or "") or _get_headshot_url(name) or ""
        team_colors_pair = get_team_colors(vitals.get("team") or "")
        team_bg = team_colors_pair[0] if team_colors_pair else "#4a5568"
        player_info = {
            "name": name,
            "headshot_url": headshot,
            "team": vitals.get("team") or "",
            "position": vitals.get("position") or "",
            "team_bg": team_bg,
        }
        for p in props:
            all_cards.append(_build_prop_card(p, player_info=player_info))

    return (
        f"<style>{PLAYER_CARD_CSS}</style>"
        '<div style="overflow-x:auto;overflow-y:visible;width:100%;max-width:100%;">'
        f'<div class="pc-props-scroll" style="padding:10px 0 16px;">{"".join(all_cards)}</div>'
        '</div>'
    )
