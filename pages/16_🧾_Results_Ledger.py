# pages/16_🧾_Results_Ledger.py
# PUBLIC results ledger — no login required.
# Every win AND every loss. Date-stamped. Always verifiable.
# This is SmartPickPro's competitive weapon: radical transparency.

import streamlit as st
import sys
import os
from pathlib import Path
from datetime import date, timedelta

# ── Path setup ─────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

st.set_page_config(
    page_title="Results Ledger — Smart Pick Pro",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── SEO / Analytics ────────────────────────────────────────────
try:
    from utils.analytics import inject_ga4, track_page_view
    inject_ga4()
    track_page_view("Results Ledger")
    from utils.seo import inject_page_seo
    inject_page_seo("Results Ledger")
except Exception:
    pass

# ── Theme ──────────────────────────────────────────────────────
try:
    from styles.theme import get_global_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
except Exception:
    pass

# ── CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800;900&family=Bebas+Neue&family=JetBrains+Mono:wght@600;700&display=swap');

:root {
  --rl-bg:      #060810;
  --rl-panel:   #0E1420;
  --rl-a1:      #00D559;
  --rl-a2:      #00F0FF;
  --rl-red:     #F24336;
  --rl-gold:    #F9C62B;
  --rl-muted:   #8899BB;
  --rl-dim:     #445577;
  --rl-text:    #FFFFFF;
}

.rl-hero {
  background: linear-gradient(135deg, #060810 0%, #0a1628 100%);
  border: 1px solid rgba(0,240,255,0.10);
  border-top: 3px solid #00D559;
  border-radius: 12px;
  padding: 2.5rem 2.5rem 2rem;
  margin-bottom: 1.5rem;
  position: relative;
  overflow: hidden;
}
.rl-hero::before {
  content: '';
  position: absolute; top: 0; right: 0;
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(0,213,89,0.06) 0%, transparent 70%);
  pointer-events: none;
}
.rl-eyebrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.3em; color: #00F0FF;
  margin-bottom: 0.5rem; text-transform: uppercase;
}
.rl-headline {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 3.4rem; line-height: 1; letter-spacing: 0.04em;
  color: #FFFFFF; margin-bottom: 0.6rem;
}
.rl-subhead {
  font-size: 1rem; font-weight: 500; color: #8899BB;
  max-width: 600px; line-height: 1.5;
}
.rl-subhead strong { color: #00D559; }
.rl-verification {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem; color: #445577;
  margin-top: 1rem; letter-spacing: 0.1em;
}

/* Stat bar */
.rl-statbar {
  display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem;
}
.rl-stat {
  background: #0E1420;
  border: 1px solid rgba(0,240,255,0.08);
  border-radius: 10px;
  padding: 1rem 1.5rem;
  min-width: 130px; flex: 1;
  text-align: center;
}
.rl-stat-val {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 2.4rem; line-height: 1;
}
.rl-stat-val.wins  { color: #00D559; text-shadow: 0 0 20px rgba(0,213,89,0.40); }
.rl-stat-val.losses { color: #F24336; }
.rl-stat-val.rate  { color: #00F0FF; text-shadow: 0 0 20px rgba(0,240,255,0.30); }
.rl-stat-val.roi-pos { color: #00D559; }
.rl-stat-val.roi-neg { color: #F24336; }
.rl-stat-val.neutral { color: #F9C62B; }
.rl-stat-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem; color: #445577;
  letter-spacing: 0.15em; margin-top: 0.3rem;
}

/* Table */
.rl-table-wrap {
  background: #0E1420;
  border: 1px solid rgba(0,240,255,0.07);
  border-radius: 12px; overflow: hidden;
}
.rl-table {
  width: 100%; border-collapse: collapse;
  font-family: 'Barlow Condensed', sans-serif;
}
.rl-table th {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem; font-weight: 700; letter-spacing: 0.18em;
  text-transform: uppercase; color: #445577;
  padding: 0.9rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.04);
  text-align: left; background: #0B1018;
}
.rl-table td {
  padding: 0.75rem 1rem; font-size: 0.95rem; font-weight: 600;
  border-bottom: 1px solid rgba(255,255,255,0.025); color: #FFFFFF;
  vertical-align: middle;
}
.rl-table tr:last-child td { border-bottom: none; }
.rl-table tr:hover td { background: rgba(0,240,255,0.025); }
.td-date { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #8899BB; }
.td-player { font-weight: 800; font-size: 1rem; }
.td-line { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8899BB; }
.td-plat {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em;
  padding: 0.2rem 0.55rem; border-radius: 4px; display: inline-block;
  background: rgba(0,240,255,0.06); color: #00F0FF; border: 1px solid rgba(0,240,255,0.12);
}
.td-safe {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem; font-weight: 700; color: #00F0FF;
}
.result-win {
  display: inline-flex; align-items: center; gap: 0.3rem;
  color: #00D559; font-family: 'Bebas Neue', sans-serif;
  font-size: 1.1rem; letter-spacing: 0.08em;
  text-shadow: 0 0 12px rgba(0,213,89,0.50);
}
.result-loss {
  color: #F24336; font-family: 'Bebas Neue', sans-serif;
  font-size: 1.1rem; letter-spacing: 0.08em;
}
.result-push {
  color: #F9C62B; font-family: 'Bebas Neue', sans-serif;
  font-size: 1.1rem; letter-spacing: 0.08em;
}
.dir-over  { color: #00D559; font-weight: 700; }
.dir-under { color: #F24336; font-weight: 700; }

.rl-compliance {
  font-size: 0.65rem; color: #2a3550;
  text-align: center; margin-top: 2rem; letter-spacing: 0.05em;
}
.rl-no-data {
  text-align: center; padding: 4rem 2rem;
  font-family: 'JetBrains Mono', monospace;
  color: #445577; font-size: 0.85rem; letter-spacing: 0.1em;
}
</style>
""", unsafe_allow_html=True)

# ── Data ───────────────────────────────────────────────────────
_STAT_ABBR = {
    "Points": "PTS", "Assists": "AST", "Rebounds": "REB",
    "Steals": "STL", "Blocks": "BLK", "Turnovers": "TO",
    "3-Pointers Made": "3PM", "Fantasy Score": "FPTS",
}

from dataclasses import dataclass, field as _dc_field
from typing import Optional, List

@dataclass
class LedgerEntry:
    player_name: Optional[str] = None
    stat_type: Optional[str] = None
    prop_line: Optional[float] = None
    direction: Optional[str] = None
    platform: Optional[str] = None
    result: Optional[str] = None
    bet_date: Optional[str] = None
    confidence_score: Optional[float] = None
    edge_pct: Optional[float] = None

@dataclass
class LedgerSummary:
    entries: List[LedgerEntry] = _dc_field(default_factory=list)
    total_wins: int = 0
    total_losses: int = 0
    total_push: int = 0
    all_time_win_rate: float = 0.0
    all_time_roi: Optional[float] = None


def _load_ledger(start_date, end_date):
    """Load resolved bets from tracking.database for the given date range."""
    try:
        from tracking.database import load_bets_by_date_range
        rows = load_bets_by_date_range(str(start_date), str(end_date))
        entries = [
            LedgerEntry(
                player_name=r.get("player_name"),
                stat_type=r.get("stat_type"),
                prop_line=r.get("line_value") or r.get("prop_line"),
                direction=r.get("direction"),
                platform=r.get("platform"),
                result=(r.get("result") or "").upper() or None,
                bet_date=r.get("bet_date"),
                confidence_score=r.get("confidence_score"),
                edge_pct=r.get("edge_percentage"),
            )
            for r in rows
        ]
        resolved = [e for e in entries if e.result in ("WIN", "LOSS", "PUSH", "EVEN")]
        wins   = sum(1 for e in resolved if e.result == "WIN")
        losses = sum(1 for e in resolved if e.result == "LOSS")
        pushes = sum(1 for e in resolved if e.result in ("PUSH", "EVEN"))
        denom  = wins + losses
        wr     = (wins / denom * 100.0) if denom else 0.0
        return LedgerSummary(
            entries=entries,
            total_wins=wins,
            total_losses=losses,
            total_push=pushes,
            all_time_win_rate=wr,
            all_time_roi=None,
        )
    except Exception as _ex:
        st.error(f"Could not load ledger data: {_ex}")
        return None


def _result_html(result: str) -> str:
    r = (result or "").upper()
    if r == "WIN":
        return '<span class="result-win">✓ WIN</span>'
    if r == "LOSS":
        return '<span class="result-loss">✗ LOSS</span>'
    if r == "PUSH":
        return '<span class="result-push">~ PUSH</span>'
    return f'<span style="color:#445577">{r}</span>'


def _dir_html(direction: str) -> str:
    d = (direction or "").upper()
    cls = "dir-over" if d == "OVER" else "dir-under"
    return f'<span class="{cls}">{d}</span>'


# ── Hero ───────────────────────────────────────────────────────
st.markdown("""
<div class="rl-hero">
  <div class="rl-eyebrow">SMARTPICKPRO &nbsp;·&nbsp; VERIFIED RESULTS &nbsp;·&nbsp; NO ACCOUNT NEEDED</div>
  <div class="rl-headline">THE RECEIPTS.</div>
  <div class="rl-subhead">
    Every win <strong>and</strong> every loss. Date-stamped. Publicly posted.
    No cherry-picks. No hidden losses. Verify every single result yourself.
  </div>
  <div class="rl-verification">
    QUANTUM MATRIX ENGINE™ 5.6 &nbsp;·&nbsp; SAFE SCORE™ DRIVEN
    &nbsp;·&nbsp; ZERO BLACK BOXES &nbsp;·&nbsp; smartpickpro.ai
  </div>
</div>
""", unsafe_allow_html=True)

# ── Controls ───────────────────────────────────────────────────
from datetime import date as _date, timedelta as _td

_today = _date.today()

col_mode, col_b, col_c, _ = st.columns([2, 1, 1, 1])
with col_mode:
    date_mode = st.radio(
        "Date range",
        ["Preset", "Custom"],
        horizontal=True,
        key="rl_date_mode",
    )

if date_mode == "Preset":
    col_preset, col_b2, col_c2, _ = st.columns([2, 1, 1, 1])
    with col_preset:
        preset = st.selectbox(
            "Time window",
            ["Today", "Yesterday", "Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days", "Last 90 days", "All time"],
            index=2,
            key="rl_preset",
        )
    with col_b2:
        result_filter = st.selectbox("Result", ["All", "Wins only", "Losses only", "Push"])
    with col_c2:
        platform_filter = st.selectbox("Platform", ["All", "PrizePicks", "Underdog", "DK Pick6"])
    _preset_map = {
        "Today":        (_today, _today),
        "Yesterday":    (_today - _td(days=1), _today - _td(days=1)),
        "Last 7 days":  (_today - _td(days=6), _today),
        "Last 14 days": (_today - _td(days=13), _today),
        "Last 30 days": (_today - _td(days=29), _today),
        "Last 60 days": (_today - _td(days=59), _today),
        "Last 90 days": (_today - _td(days=89), _today),
        "All time":     (_date(2024, 1, 1), _today),
    }
    _start_date, _end_date = _preset_map[preset]
else:
    col_d1, col_d2, col_b2, col_c2 = st.columns([1, 1, 1, 1])
    with col_d1:
        _start_date = st.date_input("From", value=_today - _td(days=6), max_value=_today, key="rl_start")
    with col_d2:
        _end_date = st.date_input("To", value=_today, min_value=_start_date, max_value=_today, key="rl_end")
    with col_b2:
        result_filter = st.selectbox("Result", ["All", "Wins only", "Losses only", "Push"])
    with col_c2:
        platform_filter = st.selectbox("Platform", ["All", "PrizePicks", "Underdog", "DK Pick6"])

# ── Load & Filter ──────────────────────────────────────────────
ledger = _load_ledger(_start_date, _end_date)

if ledger is None:
    st.markdown("""
    <div class="rl-no-data">
      NO RESULTS DATA AVAILABLE YET<br>
      <span style="font-size:0.7rem;opacity:0.5">
        Connect DATABASE_URL in .env — results populate automatically after each night's games
      </span>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not ledger.entries:
    st.markdown("""
    <div class="rl-no-data">
      NO PICKS LOGGED FOR THIS DATE RANGE<br>
      <span style="font-size:0.7rem;opacity:0.5">
        Try a different date range — results appear after games are resolved
      </span>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

entries = ledger.entries

# Apply filters
if result_filter == "Wins only":
    entries = [e for e in entries if e.result == "WIN"]
elif result_filter == "Losses only":
    entries = [e for e in entries if e.result == "LOSS"]
elif result_filter == "Push":
    entries = [e for e in entries if e.result == "PUSH"]

if platform_filter != "All":
    entries = [e for e in entries if (e.platform or "").lower() == platform_filter.lower()]

# ── Summary Stats ──────────────────────────────────────────────
filtered_wins   = sum(1 for e in entries if e.result == "WIN")
filtered_losses = sum(1 for e in entries if e.result == "LOSS")
filtered_resolved = filtered_wins + filtered_losses
filtered_wr = (filtered_wins / filtered_resolved * 100.0) if filtered_resolved else 0.0
roi_display = (
    f"{ledger.all_time_roi:+.1f}%" if ledger.all_time_roi is not None
    else "N/A"
)

wr_class   = "rate"
roi_class  = "roi-pos" if (ledger.all_time_roi or 0) >= 0 else "roi-neg"
total_resolved = ledger.total_wins + ledger.total_losses

st.markdown(f"""
<div class="rl-statbar">
  <div class="rl-stat">
    <div class="rl-stat-val wins">{ledger.total_wins}</div>
    <div class="rl-stat-lbl">TOTAL WINS</div>
  </div>
  <div class="rl-stat">
    <div class="rl-stat-val losses">{ledger.total_losses}</div>
    <div class="rl-stat-lbl">TOTAL LOSSES</div>
  </div>
  <div class="rl-stat">
    <div class="rl-stat-val {wr_class}">{ledger.all_time_win_rate:.1f}%</div>
    <div class="rl-stat-lbl">WIN RATE</div>
  </div>
  <div class="rl-stat">
    <div class="rl-stat-val {roi_class}">{roi_display}</div>
    <div class="rl-stat-lbl">ALL-TIME ROI</div>
  </div>
  <div class="rl-stat">
    <div class="rl-stat-val neutral">{total_resolved}</div>
    <div class="rl-stat-lbl">RESOLVED PICKS</div>
  </div>
  <div class="rl-stat">
    <div class="rl-stat-val neutral">{ledger.total_push}</div>
    <div class="rl-stat-lbl">PUSHES</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.caption(f"Showing {len(entries)} picks · {_start_date} → {_end_date} · "
           f"filter: {result_filter} · platform: {platform_filter}")

# ── Results Table ──────────────────────────────────────────────
if not entries:
    st.markdown('<div class="rl-no-data">NO PICKS MATCH THIS FILTER</div>',
                unsafe_allow_html=True)
else:
    rows_html = ""
    for e in entries:
        stat = _STAT_ABBR.get(e.stat_type or "", e.stat_type or "")
        safe_str = (
            f'<span class="td-safe">{e.confidence_score:.0f}</span>'
            if e.confidence_score is not None else
            '<span style="color:#2a3550">—</span>'
        )
        edge_str = (
            f'<span class="td-safe" style="color:#F9C62B">{e.edge_pct:+.1f}%</span>'
            if e.edge_pct is not None else
            '<span style="color:#2a3550">—</span>'
        )
        plat = (e.platform or "Unknown").upper()
        rows_html += f"""
        <tr>
          <td class="td-date">{e.bet_date}</td>
          <td class="td-player">{e.player_name or '—'}</td>
          <td>{_dir_html(e.direction)} <span class="td-line">{e.prop_line or '?'} {stat}</span></td>
          <td><span class="td-plat">{plat}</span></td>
          <td>{safe_str}</td>
          <td>{edge_str}</td>
          <td>{_result_html(e.result)}</td>
        </tr>"""

    st.markdown(f"""
    <div class="rl-table-wrap">
      <table class="rl-table">
        <thead>
          <tr>
            <th>DATE</th>
            <th>PLAYER</th>
            <th>PICK</th>
            <th>PLATFORM</th>
            <th>SAFE SCORE™</th>
            <th>EDGE</th>
            <th>RESULT</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)

# ── Compliance ─────────────────────────────────────────────────
st.markdown("""
<div class="rl-compliance">
  For entertainment purposes only. Not financial or gambling advice.
  Must be 21+. Please play responsibly. Problem? Call 1-800-GAMBLER.
</div>
""", unsafe_allow_html=True)
