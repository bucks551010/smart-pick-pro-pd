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

def _load_ledger(days_back: int):
    """Try social_engine data_source first, fall back to tracking DB."""
    try:
        _se = _ROOT / "social_engine"
        sys.path.insert(0, str(_se))
        import importlib, os as _os
        _os.environ.setdefault("PYTHONPATH", str(_se))
        from social_engine.core.data_source import get_public_ledger
        return get_public_ledger(days_back=days_back)
    except Exception:
        pass
    try:
        # fallback: read directly from tracking.database
        from tracking.database import get_bet_history
        rows = get_bet_history(days_back=days_back)
        from social_engine.core.data_source import LedgerEntry, LedgerSummary
        entries = [LedgerEntry(**r) for r in rows]
        wins   = sum(1 for e in entries if e.result == "WIN")
        losses = sum(1 for e in entries if e.result == "LOSS")
        resolved = wins + losses
        wr = (wins / resolved * 100.0) if resolved else 0.0
        return LedgerSummary(entries=entries, total_wins=wins, total_losses=losses,
                             all_time_win_rate=wr)
    except Exception:
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
col_a, col_b, col_c, _ = st.columns([1, 1, 1, 3])
with col_a:
    days_back = st.selectbox("Time window", [7, 14, 30, 60, 90], index=2,
                             format_func=lambda d: f"Last {d} days")
with col_b:
    result_filter = st.selectbox("Result", ["All", "Wins only", "Losses only", "Push"])
with col_c:
    platform_filter = st.selectbox("Platform", ["All", "PrizePicks", "Underdog", "DK Pick6"])

# ── Load & Filter ──────────────────────────────────────────────
ledger = _load_ledger(days_back)

if ledger is None or not ledger.entries:
    st.markdown("""
    <div class="rl-no-data">
      NO RESULTS DATA AVAILABLE YET<br>
      <span style="font-size:0.7rem;opacity:0.5">
        Connect DATABASE_URL in .env — results populate automatically after each night's games
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

st.caption(f"Showing {len(entries)} picks · last {days_back} days · "
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
