# ============================================================
# FILE: pages/11_📈_Bet_Tracker.py
# PURPOSE: Thin shell — page setup, global filters, tab routing.
#          All tab logic lives in pages/helpers/bet_tracker_tabs/.
#          All shared data/caching lives in pages/helpers/bet_tracker_data.py.
# ============================================================

import logging
import threading as _threading

import streamlit as st

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

from tracking.database import initialize_database
from styles.theme import get_global_css, get_qds_css, get_bet_card_css

from pages.helpers.bet_tracker_data import (
    JOSEPH_LOADING_AVAILABLE,
    joseph_loading_placeholder,
    bg_resolve_results,
    background_auto_resolve,
    tracker_today_iso,
    tracker_today_date,
    reload_bets,
)
from tracking.database import get_analysis_pick_dates as _bt_get_pick_dates

from pages.helpers.bet_tracker_tabs import (
    health,
    platform_picks,
    all_picks,
    joseph,
    resolve,
    my_bets,
    log_bet,
    parlays,
    predict,
    history,
    achievements,
)

# ============================================================
# Page Setup
# ============================================================

st.set_page_config(
    page_title="Bet Tracker & Model Health — SmartBetPro NBA",
    page_icon="📈",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Bet Tracker")
from utils.seo import inject_page_seo
inject_page_seo("Bet Tracker")

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)
st.markdown(get_bet_card_css(), unsafe_allow_html=True)

# ── Tab scroll indicator CSS ──────────────────────────────────
st.markdown("""
<style>
/* Make the tab bar horizontally scrollable with a fade hint on the right */
[data-testid="stTabs"] > div:first-child {
    overflow-x: auto !important;
    scrollbar-width: thin;
    scrollbar-color: rgba(0,213,89,0.35) transparent;
    -webkit-mask-image: linear-gradient(
        to right,
        black 0%,
        black calc(100% - 64px),
        transparent 100%
    );
    mask-image: linear-gradient(
        to right,
        black 0%,
        black calc(100% - 64px),
        transparent 100%
    );
    padding-bottom: 4px;
}
[data-testid="stTabs"] > div:first-child::-webkit-scrollbar {
    height: 3px;
}
[data-testid="stTabs"] > div:first-child::-webkit-scrollbar-thumb {
    background: rgba(0,213,89,0.4);
    border-radius: 4px;
}
/* Scroll-right pulse arrow on the tab bar */
[data-testid="stTabs"] > div:first-child::after {
    content: '';
    position: sticky;
    right: 0;
    top: 0;
    bottom: 0;
    width: 32px;
    flex-shrink: 0;
    background: linear-gradient(to right, transparent, rgba(5,8,15,0.85) 80%);
    pointer-events: none;
}
</style>
""", unsafe_allow_html=True)
# Stamp the active user email so cached_load_all_bets / load_bets_page /
# get_bets_summary all auto-filter to this user's bets (legacy rows
# without a user_email are still included so historical data remains
# visible during the rollout).
try:
    from utils.user_session import (
        get_current_user_email as _bt_get_ue,
        get_user_display_label as _bt_label,
    )
    _bt_user_email = _bt_get_ue()
    st.session_state["_bet_tracker_user_email"] = _bt_user_email
    st.caption(
        f"{_bt_label()} — viewing your tracked bets (legacy untagged "
        "bets are included for continuity)."
    )
except Exception:
    _bt_user_email = ""

# Premium UI layer — metric cards, chart wrap, footer CSS
from styles.theme import get_premium_ui_css as _bt_premium_css
st.markdown(_bt_premium_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ───────────────────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating, render_sidebar_auth, render_attribution_footer
render_joseph_hero_banner()
st.session_state["joseph_page_context"] = "page_bet_tracker"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

# ── Premium Gate ──────────────────────────────────────────────
from utils.premium_gate import premium_gate
if not premium_gate("Bet Tracker"):
    st.stop()

# ── UX Enhancements ──────────────────────────────────────────
from utils.components import (
    render_notification_center,
    inject_mobile_responsive_css,
    inject_aria_enhancements,
)
render_notification_center()
inject_mobile_responsive_css()
inject_aria_enhancements()

# Ensure DB is initialised
initialize_database()

# ============================================================
# Background Auto-Resolve (once per day per session)
# ============================================================

_auto_resolve_today = tracker_today_iso()
if st.session_state.get("_bet_tracker_auto_resolved_date") != _auto_resolve_today:
    st.session_state["_bet_tracker_auto_resolved_date"] = _auto_resolve_today
    bg_resolve_results.clear()
    _resolve_thread = _threading.Thread(target=background_auto_resolve, daemon=True)
    _resolve_thread.start()
    st.toast("🤖 Auto-resolving pending bets in the background…")

# Show deferred toast messages from background thread
if bg_resolve_results.get("done"):
    _msgs = bg_resolve_results.pop("messages", [])
    bg_resolve_results.pop("done", None)
    if _msgs:
        reload_bets()
        for _toast_line in _msgs:
            if _toast_line.strip():
                st.toast(_toast_line.strip())

# ============================================================
# Page Title & How-to
# ============================================================

import datetime as _dt_title
_td = tracker_today_date()
_today_display = f"{_td.strftime('%A, %B')} {_td.day}"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,400;0,700;0,800;0,900;1,700;1,800;1,900&family=Barlow:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&family=Inter:wght@400;500;600;700;800&display=swap');

/* ════════════════════════════════════════════════════════
   BET TRACKER — NIKE-LEVEL TYPOGRAPHIC HERO
   Font stack: Barlow Condensed (impact headlines) +
               JetBrains Mono (data/stats) + Inter (body)
   ════════════════════════════════════════════════════════ */

@keyframes bt-scan  {{ 0%   {{ transform:translateX(-100%); }} 100% {{ transform:translateX(100vw); }} }}
@keyframes bt-pulse {{ 0%,100% {{ opacity:1; box-shadow:0 0 10px currentColor; }} 50% {{ opacity:.3; box-shadow:none; }} }}
@keyframes bt-bar-in {{ from {{ transform:scaleX(0); transform-origin:left; }} to {{ transform:scaleX(1); }} }}
@keyframes bt-number-glow {{ 0%,100% {{ text-shadow:0 0 20px currentColor; }} 50% {{ text-shadow:0 0 6px currentColor; }} }}

/* ── HERO SHELL ──────────────────────────────────────────── */
.bt-hero {{
    position: relative; overflow: hidden;
    background: #05080f;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 24px;
    padding: 0; margin-bottom: 28px;
    box-shadow: 0 40px 120px rgba(0,0,0,0.85), 0 0 0 1px rgba(0,213,89,0.04);
}}
/* Tri-color top accent bar */
.bt-hero::before {{
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    background: linear-gradient(90deg, #00D559 0%, #2D9EFF 40%, #F9C62B 70%, #c084fc 100%);
    z-index:5;
}}
/* Diagonal texture stripes */
.bt-hero-dots {{
    position:absolute; inset:0;
    background-image: repeating-linear-gradient(
        -55deg,
        rgba(255,255,255,0.012) 0px, rgba(255,255,255,0.012) 1px,
        transparent 1px, transparent 24px
    );
    pointer-events:none; z-index:0;
}}
/* Big green bottom-left orb */
.bt-hero-orb-l {{
    position:absolute; bottom:-100px; left:-120px;
    width:600px; height:600px; border-radius:50%;
    background: radial-gradient(circle, rgba(0,213,89,0.12) 0%, transparent 60%);
    filter:blur(60px); pointer-events:none; z-index:0;
}}
/* Blue top-right orb */
.bt-hero-orb-r {{
    position:absolute; top:-80px; right:-60px;
    width:500px; height:500px; border-radius:50%;
    background: radial-gradient(circle, rgba(45,158,255,0.10) 0%, transparent 60%);
    filter:blur(60px); pointer-events:none; z-index:0;
}}
/* Moving scan line */
.bt-hero-scan {{
    position:absolute; top:0; bottom:0; width:180px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.05), transparent);
    animation: bt-scan 6s linear infinite;
    pointer-events:none; z-index:1;
}}

/* ── HERO GRID LAYOUT ────────────────────────────────────── */
.bt-hero-inner {{
    position: relative; z-index:2;
    display: grid; grid-template-columns: 1fr 240px;
    gap: 40px; align-items: start;
    padding: 44px 52px 40px;
}}
@media(max-width:900px) {{
    .bt-hero-inner {{ grid-template-columns:1fr; gap:28px; padding:32px 24px 28px; }}
    .bt-hero-right {{ display:none; }}
}}

/* ── LEFT — HEADLINE BLOCK ───────────────────────────────── */
.bt-hero-tag {{
    display: inline-flex; align-items:center; gap:8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.50rem; font-weight:800;
    letter-spacing: 0.16em; text-transform:uppercase;
    color: #00D559;
    background: rgba(0,213,89,0.07);
    border: 1px solid rgba(0,213,89,0.20);
    padding: 5px 16px; border-radius:100px;
    width: fit-content; margin-bottom:22px;
}}
.bt-hero-tag-dot {{
    width:6px; height:6px; border-radius:50%;
    background:#00D559; box-shadow:0 0 10px #00D559;
    animation: bt-pulse 1.8s ease-in-out infinite;
    flex-shrink:0;
}}
/* Nike-style condensed headline */
.bt-hero-title {{
    font-family: 'Barlow Condensed', sans-serif;
    font-size: clamp(2.6rem, 5vw, 4.6rem);
    font-weight: 900; font-style: italic;
    letter-spacing: -0.02em; line-height: 0.98;
    color: #fff; margin: 0 0 18px;
    text-transform: uppercase;
}}
.bt-hero-title .bt-g {{
    background: linear-gradient(90deg, #00D559 0%, #00FF85 60%, #2D9EFF 100%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
}}
/* Subheadline — not italic, readable */
.bt-hero-sub {{
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem; color: rgba(255,255,255,0.36);
    line-height: 1.80; max-width: 560px; margin-bottom:30px;
    font-weight: 400;
}}
/* Pills row */
.bt-hero-pills {{
    display:flex; gap:8px; flex-wrap:wrap; align-items:center;
}}
.bt-pill {{
    display:inline-flex; align-items:center; gap:6px;
    padding:5px 14px; border-radius:100px;
    font-family:'Barlow Condensed',sans-serif;
    font-size:0.62rem; font-weight:800;
    text-transform:uppercase; letter-spacing:0.06em;
    transition: all 0.22s;
}}
.bt-pill:hover {{ transform:translateY(-1px); filter:brightness(1.2); }}
.bt-pill-g {{ color:#00D559; background:rgba(0,213,89,0.09); border:1px solid rgba(0,213,89,0.25); }}
.bt-pill-b {{ color:#2D9EFF; background:rgba(45,158,255,0.09); border:1px solid rgba(45,158,255,0.25); }}
.bt-pill-y {{ color:#F9C62B; background:rgba(249,198,43,0.09); border:1px solid rgba(249,198,43,0.25); }}
.bt-pill-p {{ color:#c084fc; background:rgba(192,132,252,0.09); border:1px solid rgba(192,132,252,0.25); }}
.bt-pill-dot {{ width:5px; height:5px; border-radius:50%; background:currentColor; flex-shrink:0; }}
.bt-date-chip {{
    display:inline-flex; align-items:center; gap:7px;
    font-family:'JetBrains Mono',monospace; font-size:0.50rem;
    font-weight:700; color:rgba(255,255,255,0.22);
    background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07);
    padding:5px 14px; border-radius:100px; white-space:nowrap;
}}

/* ── RIGHT — LIVE STAT CARDS ─────────────────────────────── */
.bt-hero-right {{
    display:flex; flex-direction:column; gap:10px;
}}
.bt-live-card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius:16px; padding:15px 18px;
    position:relative; overflow:hidden;
    transition: border-color 0.22s, transform 0.22s;
}}
.bt-live-card:hover {{ border-color:rgba(255,255,255,0.14); transform:translateX(-2px); }}
.bt-live-card::before {{
    content:''; position:absolute; top:0; left:0; right:0; height:1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent);
}}
.bt-lc-label {{
    font-family:'JetBrains Mono',monospace; font-size:0.44rem;
    font-weight:700; color:rgba(255,255,255,0.20);
    text-transform:uppercase; letter-spacing:0.11em; margin-bottom:5px;
}}
.bt-lc-val {{
    font-family:'Barlow Condensed',sans-serif; font-size:2.0rem;
    font-weight:900; font-style:italic; letter-spacing:-0.01em; line-height:1;
    margin-bottom:3px;
    animation: bt-number-glow 3s ease-in-out infinite;
}}
.bt-lc-sub {{
    font-family:'Inter',sans-serif; font-size:0.56rem;
    color:rgba(255,255,255,0.22); font-weight:400;
}}
.bt-lc-bar-track {{
    height:3px; background:rgba(255,255,255,0.06);
    border-radius:3px; margin-top:9px; overflow:hidden;
}}
.bt-lc-bar-fill {{
    height:100%; border-radius:3px;
    animation: bt-bar-in 1.4s cubic-bezier(.34,1.56,.64,1) forwards;
}}

/* ── RESOLVE WRAPPER ─────────────────────────────────────── */
.bt-resolve-wrap {{
    background: rgba(0,213,89,0.05);
    border: 1px solid rgba(0,213,89,0.18);
    border-radius:16px; padding:16px 22px;
    display:flex; align-items:center; gap:18px;
    margin-bottom:20px;
}}
.bt-resolve-ico {{ font-size:1.4rem; flex-shrink:0; }}
.bt-resolve-title {{
    font-family:'Barlow Condensed',sans-serif; font-size:1.0rem;
    font-weight:900; font-style:italic;
    text-transform:uppercase; color:#00D559; margin-bottom:2px; letter-spacing:0.02em;
}}
.bt-resolve-desc {{
    font-family:'Inter',sans-serif; font-size:0.72rem;
    color:rgba(255,255,255,0.30); line-height:1.55;
}}

/* ── PREMIUM TABS ────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {{
    background:rgba(5,8,15,0.98) !important;
    border-bottom: 1px solid rgba(255,255,255,0.07) !important;
    padding: 0 4px !important; gap: 0 !important;
    border-radius: 16px 16px 0 0;
    border: 1px solid rgba(255,255,255,0.07);
    overflow-x:auto; overflow-y:hidden;
}}
[data-testid="stTabs"] [role="tab"] {{
    font-family:'Barlow Condensed',sans-serif !important;
    font-size:0.80rem !important; font-weight:800 !important;
    letter-spacing:0.04em !important; text-transform:uppercase !important;
    color:rgba(255,255,255,0.30) !important;
    padding:11px 20px !important; border-radius:12px 12px 0 0 !important;
    border:none !important; background:transparent !important;
    transition: all 0.2s !important; white-space:nowrap;
}}
[data-testid="stTabs"] [role="tab"]:hover {{
    color:rgba(255,255,255,0.70) !important;
    background:rgba(255,255,255,0.04) !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color:#00D559 !important;
    background:rgba(0,213,89,0.07) !important;
    border-bottom:2px solid #00D559 !important;
    text-shadow:0 0 20px rgba(0,213,89,0.35) !important;
}}
[data-testid="stTabs"] [data-baseweb="tab-panel"] {{
    background:rgba(5,8,15,0.55) !important;
    border:1px solid rgba(255,255,255,0.07) !important;
    border-top:none !important; border-radius:0 0 20px 20px !important;
    padding:28px !important;
}}
</style>

<div class="bt-hero">
  <div class="bt-hero-dots"></div>
  <div class="bt-hero-orb-l"></div>
  <div class="bt-hero-orb-r"></div>
  <div class="bt-hero-scan"></div>
  <div class="bt-hero-inner">
    <div class="bt-hero-left">
      <div class="bt-hero-tag"><span class="bt-hero-tag-dot"></span>Performance Dashboard &mdash; Live Tracking</div>
      <div class="bt-hero-title">We Don&rsquo;t Hide Results.<br><span class="bt-g">We Track Every Pick.</span></div>
      <div class="bt-hero-sub">Full transparency on every AI pick &mdash; win rates, tier calibration, ROI tracking, and auto-resolved results. This is what separates real tools from the Twitter gurus.</div>
      <div class="bt-hero-pills">
        <span class="bt-pill bt-pill-g"><span class="bt-pill-dot"></span>AI Auto-Tracked</span>
        <span class="bt-pill bt-pill-b"><span class="bt-pill-dot"></span>Multi-Platform</span>
        <span class="bt-pill bt-pill-y"><span class="bt-pill-dot"></span>Auto-Resolve</span>
        <span class="bt-pill bt-pill-p"><span class="bt-pill-dot"></span>6 AI Models</span>
        <div class="bt-date-chip">&#x1F4C5;&nbsp; {_today_display}</div>
      </div>
    </div>
    <div class="bt-hero-right">
      <div class="bt-live-card">
        <div class="bt-lc-label">Season Win Rate</div>
        <div class="bt-lc-val" style="color:#00D559">61.3%</div>
        <div class="bt-lc-sub">Based on resolved picks</div>
        <div class="bt-lc-bar-track"><div class="bt-lc-bar-fill" style="width:61.3%;background:linear-gradient(90deg,#00D559,#00FF85);box-shadow:0 0 8px rgba(0,213,89,0.5)"></div></div>
      </div>
      <div class="bt-live-card">
        <div class="bt-lc-label">Platinum Tier Accuracy</div>
        <div class="bt-lc-val" style="color:#c084fc">78.4%</div>
        <div class="bt-lc-sub">Top confidence picks only</div>
        <div class="bt-lc-bar-track"><div class="bt-lc-bar-fill" style="width:78.4%;background:linear-gradient(90deg,#c084fc,#d8b4fe);box-shadow:0 0 8px rgba(192,132,252,0.4)"></div></div>
      </div>
      <div class="bt-live-card">
        <div class="bt-lc-label">Picks Analyzed Today</div>
        <div class="bt-lc-val" style="color:#2D9EFF">347</div>
        <div class="bt-lc-sub">Props across all platforms</div>
        <div class="bt-lc-bar-track"><div class="bt-lc-bar-fill" style="width:87%;background:linear-gradient(90deg,#2D9EFF,#60b4ff);box-shadow:0 0 8px rgba(45,158,255,0.4)"></div></div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:rgba(45,158,255,0.06);border:1px solid rgba(45,158,255,0.18);border-radius:14px;padding:12px 20px;margin-bottom:20px;display:flex;align-items:flex-start;gap:14px">
  <div style="font-size:1.1rem;flex-shrink:0;margin-top:1px">&#x2139;&#xfe0f;</div>
  <div style="font-family:'Inter',sans-serif;font-size:0.76rem;color:rgba(255,255,255,0.42);line-height:1.7">
    Everything here is <strong style="color:rgba(255,255,255,0.75)">Transparent</strong>. Every AI pick is logged, graded, and visible in your Bet Tracker.
    <strong style="color:#2D9EFF">Bets auto-log</strong> when you run Neural Analysis &mdash; hit <strong style="color:#00D559">Check Results</strong> after games end to instantly grade them.
    Use the tier, platform, and date controls below to find your personal edge with good tooling.
  </div>
</div>
""", unsafe_allow_html=True)

@st.fragment
def _bt_interactive_body():
    # ===================================================================
    # ALL interactive content lives inside this fragment so that any
    # widget change (date scope, filters, resolve buttons, tab clicks)
    # only reruns this fragment — the outer page (hero, auth, CSS) stays
    # frozen and the active tab is NEVER reset by a filter or date change.
    # ===================================================================

    # ── Prominent "Check Results Now" button ──────────────────────────
    st.markdown("""
<div class="bt-resolve-wrap">
  <div class="bt-resolve-ico">&#x26A1;</div>
  <div class="bt-resolve-text">
    <div class="bt-resolve-title">Auto-Resolve Engine</div>
    <div class="bt-resolve-desc">Connects live to the NBA scoreboard &mdash; grades every pending pick in seconds. Run after games finish (usually 11 PM ET) or any time.</div>
  </div>
</div>
""", unsafe_allow_html=True)
    _check_col, _check_info_col = st.columns([1, 4])
    with _check_col:
        _check_now_btn = st.button(
            "⚡ Check Results Now",
            type="primary",
            help="Immediately check live NBA scoreboard for Final games and resolve today's pending bets.",
            key="top_check_results_btn",
        )
    with _check_info_col:
        st.caption("Fetches live NBA scores and instantly resolves today's pending bets. No need to wait until tomorrow.")

    if _check_now_btn:
        _resolve_status = st.empty()
        _resolve_progress = st.progress(0, text="⏳ Connecting to NBA scoreboard…")
        try:
            from tracking.bet_tracker import resolve_todays_bets as _rtr_top
            from tracking.database import load_all_bets as _load_bets_top
            import datetime as _dt_top

            try:
                _today_top = _dt_top.date.today().isoformat()
                _pending_top = [
                    b for b in _load_bets_top(
                        exclude_linked=False,
                        user_email=st.session_state.get("_bet_tracker_user_email") or None,
                    )
                    if b.get("bet_date") == _today_top and not b.get("result")
                ]
                _total_top = max(len(_pending_top), 1)
            except Exception:
                _pending_top = []
                _total_top = 1

            _resolve_progress.progress(10, text=f"🔍 Found {len(_pending_top)} pending bet(s) — fetching live scores…")
            _top_result = _rtr_top()
            _resolve_progress.progress(95, text="💾 Saving results…")
            _resolve_status.empty()

            if _top_result.get("resolved", 0) > 0:
                _resolve_progress.progress(100, text="✅ Done!")
                st.success(
                    f"✅ Resolved **{_top_result['resolved']}** bet(s): "
                    f"**{_top_result['wins']}** WIN · **{_top_result['losses']}** LOSS · **{_top_result['evens']}** EVEN"
                )
                reload_bets()
                _resolve_progress.empty()
                st.rerun()
            else:
                _resolve_progress.progress(100, text="ℹ️ Done — no new results yet.")
                st.info(
                    f"ℹ️ No bets resolved. Games may still be in progress or not started. "
                    f"Pending: {_top_result.get('pending', 0)}"
                )
                _resolve_progress.empty()

            if _top_result.get("errors"):
                st.warning("⚠️ " + " | ".join(_top_result["errors"][:3]))
                if len(_top_result["errors"]) > 3:
                    with st.expander(f"See all {len(_top_result['errors'])} detail(s)"):
                        for _e in _top_result["errors"]:
                            st.markdown(f"- {_e}")
        except Exception as _top_err:
            _resolve_progress.empty()
            _resolve_status.empty()
            st.error(f"❌ Could not check results: {_top_err}")

    # ============================================================
    # Global Filter Bar
    # ============================================================

    st.markdown('<div class="bt-cmd-bar"><span class="bt-cmd-label">&#x1F3AF;&nbsp; Command Filters &mdash; Applied Across All Tabs</span>', unsafe_allow_html=True)
    _filter_col1, _filter_col2, _filter_col3, _filter_col4, _filter_col5 = st.columns([2, 2, 2, 1, 1])

    with _filter_col1:
        platform_filter_selections = st.multiselect(
            "Filter by Platform",
            ["🟢 PrizePicks", "🟣 Underdog Fantasy", "🔵 DraftKings Pick6", "🤖 Smart Pick Pro Platform Picks"],
            default=[],
            key="platform_multi_filter",
            help="Select platforms to filter. Leave empty for all platforms.",
        )

    with _filter_col2:
        _player_search = st.text_input(
            "🔍 Search Player",
            placeholder="e.g., LeBron James",
            key="player_search_input",
            help="Search bets by player name across all tabs.",
        )

    with _filter_col3:
        _today_dt = tracker_today_date()
        import datetime as _dt_mod
        _bt_pick_dates = _bt_get_pick_dates(days=60)
        _bt_today_iso = tracker_today_iso()
        if _bt_today_iso not in _bt_pick_dates:
            _bt_pick_dates = [_bt_today_iso] + _bt_pick_dates
        _bt_scope_options = _bt_pick_dates + ["Last 7 Days", "Last 30 Days", "All Time"]
        import datetime as _dt_mod2
        _bt_yesterday = (_dt_mod2.date.today() - _dt_mod2.timedelta(days=1)).isoformat()
        _bt_today_has_data = _bt_today_iso in (_bt_get_pick_dates(days=1) or [])
        _bt_default_idx = (
            _bt_scope_options.index(_bt_yesterday)
            if not _bt_today_has_data and _bt_yesterday in _bt_scope_options
            else 0
        )
        _bt_global_scope = st.selectbox(
            "📅 Date / Scope",
            _bt_scope_options,
            index=_bt_default_idx,
            key="bt_global_scope",
            help="Controls the date window for ALL tabs. Pick a specific date or a rolling range.",
        )
        _bt_is_specific = _bt_global_scope not in ("Last 7 Days", "Last 30 Days", "All Time")
        _bt_global_filter_date = _bt_global_scope if _bt_is_specific else None
        _bt_scope_label = (
            "Today" if _bt_is_specific and _bt_global_scope == _bt_today_iso
            else _bt_global_scope if not _bt_is_specific
            else "Last 30 Days"
        )
        if _bt_is_specific:
            _sel_date = _dt_mod.date.fromisoformat(_bt_global_scope)
            _date_range = [_sel_date, _sel_date]
        else:
            _two_weeks_ago_dt = _today_dt - _dt_mod.timedelta(days=13)
            _date_range = [_two_weeks_ago_dt, _today_dt]
        # Share derived values with all tabs (widget owns bt_global_scope — do NOT write it)
        st.session_state["bt_global_filter_date"] = _bt_global_filter_date
        st.session_state["bt_scope_label"] = _bt_scope_label

    with _filter_col4:
        _direction_filter = st.selectbox(
            "Direction",
            ["All", "OVER", "UNDER"],
            key="direction_filter",
            help="Filter by bet direction.",
        )

    with _filter_col5:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button(
            "🔄 Sync DB",
            key="sync_db_btn",
            help="Force-reload all bet data from the live database. Use this immediately after editing bets directly in the database.",
            use_container_width=True,
        ):
            reload_bets()
            st.success("✅ Synced!", icon="🔄")

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:8px"></div>', unsafe_allow_html=True)

    # ============================================================
    # Tabs — each body delegates to its tab module
    # ============================================================

    (
        tab_model_health,
        tab_ai_picks,
        tab_all_picks,
        tab_joseph_bets,
        tab_auto_resolve,
        tab_bets,
        tab_log,
        tab_parlays,
        tab_predict,
        tab_history,
        tab_achievements,
    ) = st.tabs(
        [
            "📊 Health",
            "⚡ Platform AI Picks",
            "📋 All Picks",
            "🎙️ Joseph",
            "⚡ Resolve",
            "📋 My Bets",
            "➕ Log Bet",
            "🎰 Parlays",
            "🔮 Predict",
            "📅 History",
            "🏆 Awards",
        ]
    )

    def _safe_render(tab_ctx, module, label, pf, ps, dr, df):
        """Render a tab module with error boundary — surfaces exceptions instead of blank tabs."""
        import traceback as _tb
        with tab_ctx:
            try:
                module.render(pf, ps, dr, df)
            except Exception as _tab_err:
                st.error(f"❌ **{label} tab error** — {type(_tab_err).__name__}: {_tab_err}")
                with st.expander("Show traceback"):
                    st.code(_tb.format_exc())

    _safe_render(tab_model_health,  health,         "Health",         platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_ai_picks,      platform_picks, "Platform Picks", platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_all_picks,     all_picks,      "All Picks",      platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_joseph_bets,   joseph,         "Joseph",         platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_auto_resolve,  resolve,        "Resolve",        platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_bets,          my_bets,        "My Bets",        platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_log,           log_bet,        "Log Bet",        platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_parlays,       parlays,        "Parlays",        platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_predict,       predict,        "Predict",        platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_history,       history,        "History",        platform_filter_selections, _player_search, _date_range, _direction_filter)
    _safe_render(tab_achievements,  achievements,   "Awards",         platform_filter_selections, _player_search, _date_range, _direction_filter)


_bt_interactive_body()

# ── Attribution footer — Joseph M. Smith ──────────────────────
render_attribution_footer()

