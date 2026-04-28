# ============================================================
# FILE: utils/components.py
# PURPOSE: Shared UI components for the SmartBetPro NBA app.
#          Contains the global settings popover that can be
#          injected into any page's sidebar or header.
# ============================================================

import os
import base64
import functools
import logging
import time as _time_mod
import streamlit as st

_components_logger = logging.getLogger(__name__)


# ── Cached Smart Pick Pro Logo Loader ──────────────────────────────────────
@functools.lru_cache(maxsize=1)
def _get_spp_logo_b64() -> str:
    """Load the Smart Pick Pro logo and return base64-encoded string (cached)."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "..", "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "Smart_Pick_Pro_Logo.png"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            try:
                with open(norm, "rb") as fh:
                    return base64.b64encode(fh.read()).decode("utf-8")
            except Exception:
                pass
    return ""


@functools.lru_cache(maxsize=1)
def _get_spp_logo_path() -> str:
    """Return the resolved file-system path to the Smart Pick Pro logo (cached)."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "..", "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "Smart_Pick_Pro_Logo.png"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            return norm
    return ""


# ── Cached Hero Banner Loader ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _get_hero_banner_b64() -> str:
    """Load the Joseph M Smith Hero Banner and return base64-encoded string."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "..", "Joseph M Smith Hero Banner.png"),
        os.path.join(os.getcwd(), "Joseph M Smith Hero Banner.png"),
        os.path.join(_this, "..", "assets", "Joseph M Smith Hero Banner.png"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            try:
                with open(norm, "rb") as fh:
                    _components_logger.debug("Hero banner loaded from %s", norm)
                    return base64.b64encode(fh.read()).decode("utf-8")
            except Exception:
                _components_logger.warning("Failed reading hero banner at %s", norm)
    _components_logger.warning("Joseph hero banner not found in any candidate path")
    return ""


def render_joseph_hero_banner() -> None:
    """Render the Joseph M Smith Hero Banner at the top of the page."""
    b64 = _get_hero_banner_b64()
    if not b64:
        return
    st.markdown(
        f'<div style="width:100%;margin-bottom:12px;">'
        f'<img src="data:image/png;base64,{b64}" '
        f'style="width:100%;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.4);" '
        f'alt="Joseph M Smith Hero Banner" />'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_sidebar_auth() -> None:
    """Render premium tier identity card + logout button in the sidebar.

    Safe to call once per page; does NOT use a session-state guard because
    the guard prevented rendering when navigating between pages (session
    state persists across Streamlit page switches).
    """
    import html as _html

    try:
        from utils.auth_gate import get_logged_in_email, logout_user, is_logged_in
        from utils.auth import get_user_tier, get_tier_label
    except Exception:
        return

    try:
        if not is_logged_in():
            return

        _PREM_PATH = "/15_%F0%9F%92%8E_Subscription_Level"
        _email = _html.escape(get_logged_in_email() or "")
        _tier = get_user_tier() or "free"
        _tier_label = get_tier_label(_tier)

        # Avatar initials
        _initial = (_email[0].upper()) if _email else "?"

        # Tier-specific palette
        _TIER_STYLES = {
            "insider_circle": {
                "bg":       "linear-gradient(135deg,rgba(168,85,247,0.20) 0%,rgba(99,102,241,0.16) 100%)",
                "border":   "rgba(168,85,247,0.60)",
                "glow":     "0 0 32px rgba(168,85,247,0.35),0 4px 20px rgba(0,0,0,0.60)",
                "badge_bg": "linear-gradient(90deg,#a855f7,#6366f1)",
                "badge_clr":"#fff",
                "icon":     "💎",
                "avatar_bg":"linear-gradient(135deg,#a855f7,#6366f1)",
                "avatar_glow":"0 0 14px rgba(168,85,247,0.70)",
                "top_bar":  "linear-gradient(90deg,#a855f7,#6366f1,#a855f7)",
            },
            "smart_money": {
                "bg":       "linear-gradient(135deg,rgba(249,198,43,0.16) 0%,rgba(245,158,11,0.12) 100%)",
                "border":   "rgba(249,198,43,0.60)",
                "glow":     "0 0 32px rgba(249,198,43,0.32),0 4px 20px rgba(0,0,0,0.60)",
                "badge_bg": "linear-gradient(90deg,#f9c62b,#f59e0b)",
                "badge_clr":"#1a1200",
                "icon":     "💰",
                "avatar_bg":"linear-gradient(135deg,#f9c62b,#f59e0b)",
                "avatar_glow":"0 0 14px rgba(249,198,43,0.65)",
                "top_bar":  "linear-gradient(90deg,#f9c62b,#f59e0b,#f9c62b)",
            },
            "sharp_iq": {
                "bg":       "linear-gradient(135deg,rgba(45,158,255,0.16) 0%,rgba(0,213,89,0.12) 100%)",
                "border":   "rgba(45,158,255,0.60)",
                "glow":     "0 0 32px rgba(45,158,255,0.32),0 4px 20px rgba(0,0,0,0.60)",
                "badge_bg": "linear-gradient(90deg,#2D9EFF,#00D559)",
                "badge_clr":"#fff",
                "icon":     "⚡",
                "avatar_bg":"linear-gradient(135deg,#2D9EFF,#00D559)",
                "avatar_glow":"0 0 14px rgba(45,158,255,0.65)",
                "top_bar":  "linear-gradient(90deg,#2D9EFF,#00D559,#2D9EFF)",
            },
            "free": {
                "bg":       "linear-gradient(135deg,rgba(255,255,255,0.05) 0%,rgba(160,180,208,0.04) 100%)",
                "border":   "rgba(160,180,208,0.25)",
                "glow":     "0 4px 18px rgba(0,0,0,0.50)",
                "badge_bg": "rgba(255,255,255,0.08)",
                "badge_clr":"#a0b4d0",
                "icon":     "⭐",
                "avatar_bg":"linear-gradient(135deg,#3a4560,#232c40)",
                "avatar_glow":"none",
                "top_bar":  "rgba(160,180,208,0.20)",
            },
        }
        _s = _TIER_STYLES.get(_tier, _TIER_STYLES["free"])

        # Shorten email for display
        _disp_email = _email if len(_email) <= 26 else _email[:24] + "…"

        st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,700;0,800;0,900;1,700;1,800;1,900&family=Inter:wght@400;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

/* ══════════════════════════════════════════════════════
   SMART PICK PRO — Elite Sidebar Identity Card v3
   Barlow Condensed / Nike-style upgrade
   ══════════════════════════════════════════════════════ */
.sb-card {{
  position: relative;
  border-radius: 22px;
  padding: 0;
  background: {_s['bg']};
  border: 1px solid {_s['border']};
  box-shadow: {_s['glow']};
  margin-bottom: 12px;
  overflow: hidden;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  transition: box-shadow .3s ease, transform .3s ease;
}}
.sb-card:hover {{
  transform: translateY(-2px);
  box-shadow: {_s['glow']}, 0 8px 32px rgba(0,0,0,0.4);
}}
/* Animated shimmer top bar */
.sb-card::before {{
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: {_s['top_bar']};
  background-size: 300% 100%;
  border-radius: 22px 22px 0 0;
  animation: sb-shimmer 3s linear infinite;
}}
/* Subtle inner glow overlay */
.sb-card::after {{
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(255,255,255,0.05) 0%, transparent 70%);
  pointer-events: none;
  border-radius: 22px;
}}
@keyframes sb-shimmer {{
  0%   {{ background-position: 200% center }}
  100% {{ background-position: -200% center }}
}}

/* Inner padding wrapper */
.sb-inner {{
  padding: 16px 14px 14px;
  position: relative; z-index: 1;
}}

/* Avatar — larger, prominent ring */
.sb-avatar {{
  width: 44px; height: 44px;
  border-radius: 50%;
  background: {_s['avatar_bg']};
  display: inline-flex; align-items: center; justify-content: center;
  font-family: 'Barlow Condensed', sans-serif;
  font-weight: 900; font-style: italic; font-size: 1.3rem;
  color: #fff; flex-shrink: 0;
  box-shadow: {_s['avatar_glow']}, 0 3px 12px rgba(0,0,0,0.55);
  border: 2px solid rgba(255,255,255,0.20);
  position: relative;
}}
/* Subtle pulse ring on the avatar */
.sb-avatar::after {{
  content: '';
  position: absolute; inset: -4px;
  border-radius: 50%;
  border: 1.5px solid {_s['border']};
  opacity: 0.55;
  animation: sb-pulse 3s ease-in-out infinite;
}}
@keyframes sb-pulse {{
  0%, 100% {{ transform: scale(1); opacity: 0.55; }}
  50%       {{ transform: scale(1.07); opacity: 0.22; }}
}}

/* Email — mono, readable */
.sb-email {{
  color: rgba(212,228,247,0.75);
  font-size: 0.68rem;
  font-weight: 500;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.01em;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 152px;
  line-height: 1.3;
}}

/* Tier badge — Barlow Condensed italic pill */
.sb-badge {{
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 12px 3px 9px;
  border-radius: 100px;
  background: {_s['badge_bg']};
  color: {_s['badge_clr']};
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 0.78rem; font-weight: 900; font-style: italic;
  letter-spacing: 0.04em; text-transform: uppercase;
  box-shadow: 0 2px 14px rgba(0,0,0,0.4), 0 0 10px rgba(0,0,0,0.2) inset;
  border: 1px solid rgba(255,255,255,0.14);
}}

/* Stats row — compact metrics below email */
.sb-stats {{
  display: flex; gap: 7px; margin-top: 11px;
}}
.sb-stat {{
  flex: 1;
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  padding: 6px 6px 5px;
  text-align: center;
  transition: background .2s ease;
}}
.sb-stat:hover {{
  background: rgba(255,255,255,0.04);
}}
.sb-stat-val {{
  font-family: 'Barlow Condensed', sans-serif;
  font-weight: 900; font-style: italic;
  font-size: 0.88rem;
  color: #fff; line-height: 1;
  letter-spacing: .02em;
}}
.sb-stat-lbl {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.42rem; font-weight: 700;
  color: rgba(255,255,255,0.30);
  text-transform: uppercase; letter-spacing: 0.1em;
  margin-top: 2px;
}}

/* Divider line inside card */
.sb-divider {{
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
  margin: 11px 0 10px;
}}

/* Upgrade CTA */
.sb-upgrade-btn {{
  display: flex; align-items: center; justify-content: center; gap: 7px;
  padding: 11px 0; border-radius: 13px;
  background: linear-gradient(135deg, #ff5e00 0%, #ff8c00 50%, #ffb300 100%);
  background-size: 200% 100%;
  text-align: center; color: #050910 !important;
  font-family: 'Barlow Condensed', sans-serif;
  font-weight: 900; font-style: italic; font-size: 0.86rem;
  letter-spacing: 0.05em; text-decoration: none !important;
  text-transform: uppercase;
  box-shadow: 0 0 28px rgba(255,94,0,0.50), 0 4px 14px rgba(0,0,0,0.45),
              inset 0 1px 0 rgba(255,255,255,0.22);
  transition: filter 0.2s, transform 0.18s, box-shadow 0.2s;
  animation: sb-upgrade-glow 2.5s ease-in-out infinite;
}}
@keyframes sb-upgrade-glow {{
  0%, 100% {{ box-shadow: 0 0 22px rgba(255,94,0,0.45), 0 3px 10px rgba(0,0,0,0.45); }}
  50%       {{ box-shadow: 0 0 44px rgba(255,140,0,0.70), 0 3px 10px rgba(0,0,0,0.45); }}
}}
.sb-upgrade-btn:hover {{
  filter: brightness(1.12);
  transform: translateY(-2px);
  box-shadow: 0 0 44px rgba(255,140,0,0.70), 0 8px 24px rgba(0,0,0,0.55) !important;
}}

/* ── Elite Log Out button ── */
[data-testid="stSidebar"] .stButton > button {{
  width: 100% !important;
  background: linear-gradient(135deg, rgba(242,67,54,0.05) 0%, rgba(180,30,20,0.07) 100%) !important;
  border: 1px solid rgba(242,67,54,0.25) !important;
  color: rgba(240,184,180,0.85) !important;
  font-family: 'Barlow Condensed', sans-serif !important;
  font-weight: 900 !important; font-style: italic !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.06em !important; text-transform: uppercase !important;
  border-radius: 13px !important;
  padding: 11px 20px !important; min-height: 44px !important;
  transition: all 0.22s cubic-bezier(0.16,1,0.3,1) !important;
  position: relative !important; overflow: hidden !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: linear-gradient(135deg, rgba(242,67,54,0.14) 0%, rgba(180,30,20,0.18) 100%) !important;
  border-color: rgba(242,67,54,0.60) !important;
  color: #ff7a72 !important;
  box-shadow: 0 0 28px rgba(242,67,54,0.25), inset 0 0 16px rgba(242,67,54,0.06) !important;
  transform: translateY(-1px) !important;
}}
</style>
<div class="sb-card">
  <div class="sb-inner">
    <div style="display:flex;align-items:center;gap:11px;">
      <div class="sb-avatar">{_initial}</div>
      <div style="min-width:0;flex:1;display:flex;flex-direction:column;gap:5px;">
        <div class="sb-email" title="{_email}">{_disp_email}</div>
        <span class="sb-badge">{_s['icon']} {_tier_label}</span>
      </div>
    </div>
    <div class="sb-stats">
      <div class="sb-stat"><div class="sb-stat-val">AI</div><div class="sb-stat-lbl">Engine</div></div>
      <div class="sb-stat"><div class="sb-stat-val">5.6</div><div class="sb-stat-lbl">Version</div></div>
      <div class="sb-stat"><div class="sb-stat-val">ON</div><div class="sb-stat-lbl">Live</div></div>
    </div>
    {f'<div class="sb-divider"></div><a href="{_PREM_PATH}" target="_self" class="sb-upgrade-btn"><span>🚀</span>Unlock Full Access</a>' if _tier == 'free' else ''}
  </div>
</div>
""", unsafe_allow_html=True)

        if st.button("🚪 Log Out", key="_global_sidebar_logout", use_container_width=True,
                     help="Sign out of your Smart Pick Pro account"):
            logout_user()
            st.rerun()
        # ── Attribution block — always visible at sidebar bottom ───
        render_sidebar_attribution()
        st.divider()
    except Exception:
        pass


def render_global_settings():
    """Render an inline settings popover for edge threshold and simulation depth.

    Uses ``st.popover`` so users can adjust core engine parameters without
    leaving the current page.  Widget values are bound directly to
    ``st.session_state`` keys that the analysis engine already reads
    (``minimum_edge_threshold``, ``simulation_depth``), so changes
    propagate instantly on the next rerun.
    """
    with st.popover("⚙️ Settings"):
        st.markdown(
            "**Quantum Matrix Engine 5.6 — Quick Settings**"
        )

        # ── Simulation Depth ──────────────────────────────────────
        st.number_input(
            "Simulation Depth",
            min_value=100,
            max_value=10000,
            step=100,
            value=st.session_state.get("simulation_depth", 1000),
            key="sim_depth_widget",
            help="Number of Quantum Matrix simulations per prop. Higher = more accurate but slower.",
            on_change=_sync_sim_depth,
        )

        # ── Minimum Edge Threshold ────────────────────────────────
        st.number_input(
            "Min Edge Threshold (%)",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            value=float(st.session_state.get("minimum_edge_threshold", 5.0)),
            key="edge_threshold_widget",
            help="Only display props with an edge at or above this percentage.",
            on_change=_sync_edge_threshold,
        )

        # ── Entry Fee ─────────────────────────────────────────────
        st.number_input(
            "Entry Fee ($)",
            min_value=1.0,
            max_value=1000.0,
            step=1.0,
            value=float(st.session_state.get("entry_fee", 10.0)),
            key="entry_fee_widget",
            help="Default dollar amount per entry for EV calculations.",
            on_change=_sync_entry_fee,
        )

        st.divider()

        # ── Total Bankroll ────────────────────────────────────────
        st.number_input(
            "Total Bankroll ($)",
            min_value=10.0,
            max_value=1_000_000.0,
            step=50.0,
            value=float(st.session_state.get("total_bankroll", 1000.0)),
            key="total_bankroll_widget",
            help="Your total bankroll in dollars. Used for Kelly Criterion bet sizing.",
            on_change=_sync_total_bankroll,
        )

        # ── Kelly Multiplier ──────────────────────────────────────
        st.slider(
            "Kelly Multiplier",
            min_value=0.1,
            max_value=1.0,
            step=0.05,
            value=float(st.session_state.get("kelly_multiplier", 0.25)),
            key="kelly_multiplier_widget",
            help=(
                "Fraction of the full Kelly bet to use. "
                "0.25 = Quarter Kelly (conservative, recommended). "
                "1.0 = Full Kelly (aggressive, higher variance)."
            ),
            on_change=_sync_kelly_multiplier,
        )

        st.caption("Changes apply on next analysis run.")

    # ── Responsible Gambling Disclaimer ───────────────────────────
    render_sidebar_disclaimer()


# ── Global Broadcast Ticker ──────────────────────────────────────

_TICKER_CSS = """<style>
.joseph-broadcast-ticker{
    position:relative;overflow:hidden;
    background:rgba(7,10,19,0.92);
    border-bottom:2px solid rgba(255,94,0,0.35);
    height:32px;margin-bottom:12px;
    font-family:'Montserrat',sans-serif;
}
.joseph-broadcast-ticker::before{
    content:'🎙️ JOSEPH M. SMITH — LIVE';
    position:absolute;left:0;top:0;z-index:2;
    background:linear-gradient(90deg,#ff5e00,#ff9e00);
    color:#070a13;font-weight:700;font-size:0.7rem;
    letter-spacing:0.5px;padding:7px 14px;
    white-space:nowrap;
}
.joseph-ticker-track{
    display:flex;animation:tickerScroll 45s linear infinite;
    padding-left:260px;height:100%;align-items:center;
}
.joseph-ticker-item{
    white-space:nowrap;color:#e2e8f0;font-size:0.78rem;
    padding:0 28px;flex-shrink:0;
}
.joseph-ticker-sep{
    color:#ff5e00;padding:0 4px;flex-shrink:0;font-size:0.65rem;
}
@keyframes tickerScroll{
    0%{transform:translateX(0)}
    100%{transform:translateX(-50%)}
}
</style>"""


def _render_broadcast_ticker():
    """Render Joseph's global broadcast ticker at the top of the page.

    Shows a scrolling marquee with ambient Joseph lines on every page.
    The ticker re-renders on each page navigation so it appears site-wide.
    Skipped on the home page, which has its own live-analysis-bar section.
    """
    # Home page has its own live-analysis-bar — skip the ticker there to
    # avoid rendering two near-identical "LIVE" bars at the top.
    if st.session_state.get("joseph_page_context") == "page_home":
        return
    # Build ticker items from analysis results or defaults
    ticker_items = []
    analysis = st.session_state.get("analysis_results", [])
    if analysis:
        for r in analysis[:8]:
            player = r.get("player_name", r.get("player", ""))
            verdict = r.get("verdict", "")
            stat = r.get("stat_type", "")
            if player and verdict:
                ticker_items.append(f"{player} — {stat} {verdict}")
    if not ticker_items:
        ticker_items = [
            "Joseph M. Smith is watching EVERY line on the board tonight",
            "The models are LOADED and the analysis is READY",
            "Trust the PROCESS — Joseph doesn't miss",
            "Stay locked in for LIVE updates throughout the night",
        ]

    # Duplicate for seamless loop
    items_html = ""
    for item in ticker_items * 2:
        items_html += (
            f'<span class="joseph-ticker-item">{item}</span>'
            f'<span class="joseph-ticker-sep">◆</span>'
        )

    st.markdown(_TICKER_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="joseph-broadcast-ticker">'
        f'<div class="joseph-ticker-track">{items_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_spp_nav_logo():
    """Render the Smart Pick Pro logo centered at the top of every page."""
    logo_b64 = _get_spp_logo_b64()
    if not logo_b64:
        return
    _NAV_LOGO_CSS = """
    <style>
    .spp-nav-logo-bar {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        padding: 8px 0 4px 0;
        margin-bottom: 4px;
    }
    .spp-nav-logo {
        height: 54px;
        width: auto;
        object-fit: contain;
        filter: drop-shadow(0 2px 8px rgba(0, 255, 213, 0.25));
        transition: transform 0.3s ease;
    }
    .spp-nav-logo:hover {
        transform: scale(1.05);
    }
    </style>
    """
    st.markdown(
        f'<div class="spp-nav-logo-bar">'
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'class="spp-nav-logo" alt="Smart Pick Pro" />'
        f'</div>'
        f'{_NAV_LOGO_CSS}',
        unsafe_allow_html=True,
    )


def inject_joseph_floating():
    """Render the Joseph M. Smith floating widget in the main content area.

    Delegates to :func:`utils.joseph_widget.render_joseph_floating_widget`
    so the widget appears on every page that calls this helper.
    Also renders the responsible gambling disclaimer in the sidebar,
    injects the session keep-alive script, auto-saves/restores
    critical page state, and shows the broadcast ticker.
    """
    # ── Keep session alive & restore/save page state ──────────
    _inject_session_keepalive()
    _auto_restore_page_state()
    _auto_save_page_state()

    # ── Sidebar nav CSS (active state + section labels + tooltips) ──
    # Must run on every page because Streamlit rebuilds the DOM on navigation.
    try:
        inject_sidebar_nav_tooltips()
    except Exception as exc:
        _components_logger.debug("inject_sidebar_nav_tooltips failed: %s", exc)

    # ── Global Broadcast Ticker ───────────────────────────────
    try:
        _render_broadcast_ticker()
    except Exception as exc:
        _components_logger.debug("broadcast ticker failed: %s", exc)

    try:
        from utils.joseph_widget import render_joseph_floating_widget
        render_joseph_floating_widget()
    except Exception as exc:
        _components_logger.debug("inject_joseph_floating failed: %s", exc)
    # Show the disclaimer on every page that calls this helper
    render_sidebar_disclaimer()


# ── Session Keep-Alive & Page State Persistence ──────────────────

def _inject_session_keepalive():
    """Inject JavaScript that keeps the Streamlit WebSocket alive and
    ensures the mobile sidebar toggle button is always accessible.

    Prevents session resets when the app tab is left open but idle
    for an extended period.  Uses periodic health-check fetches and
    visibility-change handlers to maintain the connection.

    Also injects a viewport meta tag (if missing) for proper mobile
    rendering and a MutationObserver that ensures the sidebar toggle
    button remains visible on mobile after the sidebar is closed.
    """
    if st.session_state.get("_keepalive_injected"):
        return
    st.session_state["_keepalive_injected"] = True
    st.markdown(
        """
        <script>
        (function() {
            if (window.__stKeepalive) return;
            window.__stKeepalive = true;

            /* ── Viewport meta — ensure proper mobile scaling ────── */
            if (!document.querySelector('meta[name="viewport"]')) {
                var meta = document.createElement('meta');
                meta.name = 'viewport';
                meta.content = 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes, viewport-fit=cover';
                document.head.appendChild(meta);
            }

            /* ── Periodic ping — keeps proxies / load-balancers ──── */
            var _ping = function() {
                fetch('./_stcore/health').catch(function(){});
            };
            setInterval(_ping, 90000);

            /* When the user returns to the tab after it was hidden,
               fire an immediate ping to re-establish activity. */
            document.addEventListener('visibilitychange', function() {
                if (!document.hidden) { _ping(); _resetIdleTimer(); }
            });

            /* ── Session Idle Warning ─────────────────────────────
               Show a non-blocking toast after 8 min of no interaction.
               Dismiss automatically once the user moves the mouse,
               taps, scrolls, or presses a key. */
            var _idleTimer = null;
            var _IDLE_WARN_MS = 8 * 60 * 1000;  /* 8 minutes */
            var _toastEl = null;

            function _showIdleToast() {
                if (_toastEl) return;
                _toastEl = document.createElement('div');
                _toastEl.id = 'spp-idle-toast';
                _toastEl.innerHTML = '⏰ <strong>Still there?</strong> Your session will stay active while this tab is open. Click anywhere to dismiss.';
                _toastEl.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;' +
                    'background:linear-gradient(135deg,#1a2332,#14192b);color:#c8d6e5;' +
                    'border:1px solid rgba(249,198,43,0.4);border-radius:12px;padding:14px 20px;' +
                    'font-size:0.85rem;max-width:380px;box-shadow:0 8px 32px rgba(0,0,0,0.5);' +
                    'animation:lpFadeInUp 0.4s ease;cursor:pointer;';
                _toastEl.onclick = function() { _dismissIdleToast(); };
                document.body.appendChild(_toastEl);
            }

            function _dismissIdleToast() {
                if (_toastEl) { _toastEl.remove(); _toastEl = null; }
            }

            function _resetIdleTimer() {
                _dismissIdleToast();
                clearTimeout(_idleTimer);
                _idleTimer = setTimeout(_showIdleToast, _IDLE_WARN_MS);
            }

            ['mousemove','mousedown','keydown','touchstart','scroll'].forEach(function(evt) {
                document.addEventListener(evt, _resetIdleTimer, {passive:true});
            });
            _resetIdleTimer();

            /* ── Mobile sidebar toggle fix ────────────────────────
               Streamlit sometimes hides the sidebar toggle button
               or nests it inside an invisible parent. This observer
               ensures the toggle button is always visible and
               tappable on mobile (≤768px).

               THROTTLED to avoid feedback loops: the style mutations
               we apply (display/visibility/opacity) would re-trigger
               the MutationObserver without the throttle guard.  A
               rAF-debounced check runs at most once per animation
               frame (~16ms). */
            var _sidebarPending = false;
            function ensureSidebarToggle() {
                if (window.innerWidth > 768) return;
                if (_sidebarPending) return;
                _sidebarPending = true;
                requestAnimationFrame(function() {
                    _sidebarPending = false;
                    var selectors = [
                        '[data-testid="stSidebarCollapsedControl"]',
                        '[data-testid="collapsedControl"]'
                    ];
                    selectors.forEach(function(sel) {
                        var btn = document.querySelector(sel);
                        if (btn) {
                            btn.style.display = 'flex';
                            btn.style.visibility = 'visible';
                            btn.style.opacity = '1';
                            btn.style.pointerEvents = 'auto';
                        }
                    });
                });
            }
            /* Run once and observe DOM mutations — scoped to the
               header element for performance (avoids monitoring the
               entire body subtree). Falls back to body childList-only
               if the header is not yet rendered. */
            ensureSidebarToggle();
            var headerEl = document.querySelector('header[data-testid="stHeader"]');
            if (headerEl) {
                var obs = new MutationObserver(function() { ensureSidebarToggle(); });
                obs.observe(headerEl, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'aria-expanded'] });
            } else {
                /* Header not yet in DOM — watch body childList only
                   (lightweight) until we can scope to the header. */
                var bodyObs = new MutationObserver(function() {
                    var h = document.querySelector('header[data-testid="stHeader"]');
                    if (h) {
                        bodyObs.disconnect();
                        var obs2 = new MutationObserver(function() { ensureSidebarToggle(); });
                        obs2.observe(h, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'aria-expanded'] });
                    }
                    ensureSidebarToggle();
                });
                bodyObs.observe(document.body, { childList: true, subtree: false });
            }

            /* Also run on resize in case the user rotates their phone */
            window.addEventListener('resize', ensureSidebarToggle);
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def _auto_restore_page_state():
    """Restore persisted page state from SQLite on a fresh session.

    Called once per session (guarded by ``_page_state_restored`` flag).
    Only populates keys that are not already present in session state,
    so it never overwrites data the user has generated in this session.
    """
    if st.session_state.get("_page_state_restored"):
        return
    st.session_state["_page_state_restored"] = True
    try:
        from tracking.database import load_page_state
        saved = load_page_state()
        for key, value in saved.items():
            if key not in st.session_state:
                st.session_state[key] = value
            elif isinstance(st.session_state[key], (list, dict)) and not st.session_state[key] and value:
                # Replace empty defaults with saved non-empty data
                st.session_state[key] = value
    except Exception as exc:
        _components_logger.debug("_auto_restore_page_state failed: %s", exc)


def _auto_save_page_state():
    """Persist critical page state to SQLite, debounced to at most once per 30 seconds.

    This avoids heavy SQLite writes on every single rerender while still
    ensuring data is saved frequently enough to survive session resets.
    """
    _SAVE_INTERVAL = 30  # seconds
    _now = _time_mod.time()
    _last = st.session_state.get("_page_state_last_save_ts", 0)
    if _now - _last < _SAVE_INTERVAL:
        return  # Skip — too soon since last save
    try:
        from tracking.database import save_page_state
        save_page_state(st.session_state)
        st.session_state["_page_state_last_save_ts"] = _now
    except Exception as exc:
        _components_logger.debug("_auto_save_page_state failed: %s", exc)


def render_sidebar_disclaimer():
    """Render a collapsed responsible gambling disclaimer in the sidebar.

    Uses a session-state flag to avoid rendering the same disclaimer
    twice on pages that call both ``render_global_settings()`` and
    ``inject_joseph_floating()``.
    """
    if st.session_state.get("_disclaimer_rendered"):
        return
    st.session_state["_disclaimer_rendered"] = True
    with st.sidebar:
        with st.expander("⚠️ Responsible Gambling", expanded=False):
            st.caption(
                "This app is for **personal entertainment and analysis** only. "
                "Always gamble responsibly. Past model performance does not guarantee "
                "future results. Prop betting involves risk. Never bet more than you "
                "can afford to lose."
            )


# ── on_change callbacks ──────────────────────────────────────────
# These propagate widget values into the canonical session-state keys
# that the rest of the app reads (simulation_depth, minimum_edge_threshold,
# entry_fee).  Each uses .get() with a safe default in case the widget
# key hasn't been registered yet (avoids KeyError on first render).

def _sync_sim_depth():
    st.session_state["simulation_depth"] = st.session_state.get(
        "sim_depth_widget", st.session_state.get("simulation_depth", 1000)
    )
    _persist_settings()


def _sync_edge_threshold():
    st.session_state["minimum_edge_threshold"] = st.session_state.get(
        "edge_threshold_widget", st.session_state.get("minimum_edge_threshold", 5.0)
    )
    _persist_settings()


def _sync_entry_fee():
    st.session_state["entry_fee"] = st.session_state.get(
        "entry_fee_widget", st.session_state.get("entry_fee", 10.0)
    )
    _persist_settings()


def _sync_total_bankroll():
    st.session_state["total_bankroll"] = st.session_state.get(
        "total_bankroll_widget", st.session_state.get("total_bankroll", 1000.0)
    )
    _persist_settings()


def _sync_kelly_multiplier():
    st.session_state["kelly_multiplier"] = st.session_state.get(
        "kelly_multiplier_widget", st.session_state.get("kelly_multiplier", 0.25)
    )
    _persist_settings()


def _persist_settings():
    """Save the current session state settings to the database."""
    try:
        from tracking.database import save_user_settings
        save_user_settings(st.session_state)
    except Exception as exc:
        _components_logger.debug("_persist_settings failed (non-fatal): %s", exc)


# ── Friendly Error Display ────────────────────────────────────────

_ERROR_MAP = {
    "ConnectionError": ("🌐 Connection Problem", "We couldn't reach the data source. Check your internet connection and try again."),
    "TimeoutError": ("⏱️ Request Timed Out", "The data source took too long to respond. Please try again in a moment."),
    "Timeout": ("⏱️ Request Timed Out", "The data source took too long to respond. Please try again in a moment."),
    "JSONDecodeError": ("📦 Data Format Error", "The data we received was in an unexpected format. This is usually temporary — try again."),
    "OperationalError": ("🗄️ Database Busy", "The database is temporarily busy. Please wait a moment and try again."),
    "WebSocketClosedError": ("🔄 Session Reconnecting", "Your session briefly disconnected. The page will reload automatically."),
    "StreamClosedError": ("🔄 Session Reconnecting", "Your session briefly disconnected. The page will reload automatically."),
    "RateLimitError": ("⏳ Rate Limited", "Too many requests. Please wait a minute before trying again."),
    "HTTPError": ("🌐 Server Error", "The external service returned an error. This is usually temporary — try again."),
}


def show_friendly_error(exc: Exception, context: str = "") -> None:
    """Display a user-friendly error message instead of raw tracebacks.

    Args:
        exc: The caught exception.
        context: Optional description of what was happening (e.g. "loading props").
    """
    exc_type = type(exc).__name__
    title, message = _ERROR_MAP.get(exc_type, ("❌ Something Went Wrong", ""))
    if not message:
        # Generic fallback — hide raw traceback from users
        message = "An unexpected error occurred. Please try again or reload the page."
    if context:
        message = f"Error while {context}: {message}"
    st.error(f"**{title}**\n\n{message}")
    _components_logger.error("Friendly error (%s): %s — %s", context or "general", exc_type, exc)


# ── Designed Empty State ──────────────────────────────────────────

def render_empty_state(icon: str, title: str, message: str, cta: str = "") -> None:
    """Render a styled empty-state card with icon, title, message, and optional CTA hint."""
    _cta_html = f'<div style="color:#00D559;font-size:0.82rem;font-weight:600;margin-top:12px;">{cta}</div>' if cta else ""
    st.markdown(
        f'<div style="text-align:center;padding:48px 24px;background:rgba(255,255,255,0.02);'
        f'border:1px dashed rgba(255,255,255,0.08);border-radius:14px;margin:16px 0;">'
        f'<div style="font-size:2.8rem;margin-bottom:10px;opacity:0.5;">{icon}</div>'
        f'<div style="font-size:1.05rem;font-weight:700;color:#c8d6e5;margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:0.85rem;color:#6B7A9A;max-width:420px;margin:0 auto;line-height:1.5;">{message}</div>'
        f'{_cta_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Sidebar Nav Tooltips ─────────────────────────────────────────

_SIDEBAR_NAV_DESCRIPTIONS = {
    "Live Games": "Load tonight's schedule & rosters",
    "Prop Scanner": "Enter or pull live prop lines",
    "Quantum Analysis Matrix": "Run AI analysis on all props",
    "Smart Money Bets": "See top-ranked picks tonight",
    "The Studio": "Joseph's AI commentary room",
    "Game Report": "Full game-by-game breakdowns",
    "Player Simulator": "What-if stat simulations",
    "Entry Builder": "Build optimized DFS entries",
    "Risk Shield": "Identify risky props to avoid",
    "Smart NBA Data": "Player stats & team standings",
    "Correlation Matrix": "Find correlated prop combos",
    "Bet Tracker": "Track bets, ROI & model health",
    "Proving Grounds": "Backtest & validate accuracy",
    "Settings": "Tune engine + manage account",
    "Subscription Level": "Manage your premium plan",
    "Live Sweat": "Track active bets in real-time",
}


def inject_sidebar_nav_tooltips() -> None:
    """Inject elite nav CSS + tooltips on sidebar nav items via JavaScript."""
    # NOTE: No session-state guard here.  The CSS must be re-emitted on every
    # page navigation because Streamlit rebuilds the full DOM when switching
    # pages and does not carry over st.markdown() output from the previous
    # page.  The JS block is guarded by window.__sppNavTooltips so the
    # MutationObserver is only registered once per browser tab.

    # Build JS map of page name → tooltip
    import json as _json_mod
    _map_js = _json_mod.dumps(_SIDEBAR_NAV_DESCRIPTIONS)

    # Section groupings — emoji prefix → label shown above that group
    _SECTION_LABELS = {
        "0_": ("", None),              # Live Sweat — top of list, no label
        "1_": ("ANALYSIS", "#3A4A6A"),  # Live Games starts analysis block
        "4_": ("PICKS", "#3A4A6A"),     # Smart Money starts picks block
        "8_": ("TOOLS", "#3A4A6A"),     # Entry Builder starts tools block
        "10_": ("DATA & RESEARCH", "#3A4A6A"),
        "12_": ("PERFORMANCE", "#3A4A6A"),
        "14_": ("ACCOUNT", "#3A4A6A"),
    }

    # Inject late-binding CSS that runs after Streamlit renders nav
    _elite_nav_css = """
<style>
/* ── Elite nav overrides (late-inject to beat Streamlit specificity) ── */
[data-testid="stSidebarNavItems"] li {
  list-style: none !important;
  margin: 0 !important;
  padding: 0 !important;
}
/* Ensure nav text inherits proper color and doesn't get overridden */
[data-testid="stSidebarNavLink"] p,
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavItems"] a p,
[data-testid="stSidebarNavItems"] a span {
  color: inherit !important;
  font-size: inherit !important;
  font-weight: inherit !important;
  letter-spacing: inherit !important;
}
/* ── "You are here" active page indicator ── */
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
  background: linear-gradient(90deg,rgba(0,213,89,0.13) 0%,rgba(0,213,89,0.04) 100%) !important;
  border-left: 3px solid #00D559 !important;
  border-radius: 0 6px 6px 0 !important;
  padding-left: calc(1rem - 3px) !important;
  color: #00D559 !important;
  font-weight: 700 !important;
  text-shadow: 0 0 18px rgba(0,213,89,0.55) !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] p,
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {
  color: #00D559 !important;
  font-weight: 700 !important;
}
/* Section header labels injected by JS */
.spp-nav-section-label {
  font-family: 'Inter', sans-serif;
  font-size: 0.60rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #3A4A6A !important;
  padding: 14px 20px 4px 22px;
  display: block;
  pointer-events: none;
  user-select: none;
}
/* Thin divider above section labels (except first) */
.spp-nav-section-divider {
  height: 1px;
  background: rgba(255,255,255,0.05);
  margin: 4px 14px 0;
}
</style>
"""
    st.markdown(_elite_nav_css, unsafe_allow_html=True)

    _section_labels_js = _json_mod.dumps(_SECTION_LABELS)
    _tooltip_script = (
        '<script>\n'
        '(function() {\n'
        '    if (window.__sppNavTooltips) return;\n'
        '    window.__sppNavTooltips = true;\n'
        '    var tipMap = ' + _map_js + ';\n'
        '    var sectionMap = ' + _section_labels_js + ';\n'
        '\n'
        '    function addTooltips() {\n'
        '        var links = document.querySelectorAll(\'[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavItems"] a\');\n'
        '        links.forEach(function(a) {\n'
        '            var spans = a.querySelectorAll("span");\n'
        '            var text = "";\n'
        '            spans.forEach(function(s) { text += s.textContent; });\n'
        '            text = text.trim();\n'
        '            var clean = text.replace(/^\\S+\\s*/, "").trim();\n'
        '            if (!clean) clean = text;\n'
        '            var tip = tipMap[clean];\n'
        '            if (tip && !a.getAttribute("title")) {\n'
        '                a.setAttribute("title", tip);\n'
        '            }\n'
        '        });\n'
        '    }\n'
        '\n'
        '    function addSectionLabels() {\n'
        '        var items = document.querySelectorAll(\'[data-testid="stSidebarNavItems"] li\');\n'
        '        items.forEach(function(li) {\n'
        '            if (li.dataset.sppLabeled) return;\n'
        '            var a = li.querySelector("a");\n'
        '            if (!a) return;\n'
        '            var href = a.getAttribute("href") || "";\n'
        '            var slug = href.replace(/^.*\\//, "").replace(/%[0-9A-Fa-f]{2}/g, "_");\n'
        '            var label = null;\n'
        '            Object.keys(sectionMap).forEach(function(prefix) {\n'
        '                if (slug.startsWith(prefix) && sectionMap[prefix][0]) {\n'
        '                    label = sectionMap[prefix][0];\n'
        '                }\n'
        '            });\n'
        '            if (label) {\n'
        '                var divider = document.createElement("div");\n'
        '                divider.className = "spp-nav-section-divider";\n'
        '                var labelEl = document.createElement("span");\n'
        '                labelEl.className = "spp-nav-section-label";\n'
        '                labelEl.textContent = label;\n'
        '                li.parentNode.insertBefore(divider, li);\n'
        '                li.parentNode.insertBefore(labelEl, li);\n'
        '            }\n'
        '            li.dataset.sppLabeled = "1";\n'
        '        });\n'
        '    }\n'
        '\n'
        '    function init() { addTooltips(); addSectionLabels(); }\n'
        '    setTimeout(init, 1200);\n'
        '    var obs = new MutationObserver(function() { setTimeout(init, 300); });\n'
        '    var sidebar = document.querySelector(\'[data-testid="stSidebar"]\');\n'
        '    if (sidebar) obs.observe(sidebar, { childList: true, subtree: true });\n'
        '})();\n'
        '</script>'
    )
    st.markdown(_tooltip_script, unsafe_allow_html=True)


# ── Notification Center ──────────────────────────────────────────

_NOTIF_LEVEL_STYLES = {
    "info": {"bg": "rgba(0,150,255,0.12)", "border": "#2196F3", "icon": "ℹ️"},
    "success": {"bg": "rgba(0,213,89,0.12)", "border": "#00D559", "icon": "✅"},
    "warning": {"bg": "rgba(255,193,7,0.12)", "border": "#FFC107", "icon": "⚠️"},
    "error": {"bg": "rgba(255,68,68,0.12)", "border": "#FF4444", "icon": "🚨"},
}


def add_notification(title: str, message: str, level: str = "info") -> None:
    """Add a notification to the in-session notification center.

    Args:
        title: Short headline (e.g. "Tilt Alert").
        message: Full notification body.
        level: One of "info", "success", "warning", "error".
    """
    import datetime as _dt_mod
    notifs = st.session_state.setdefault("_spp_notifications", [])
    notifs.insert(0, {
        "title": title,
        "message": message,
        "level": level,
        "ts": _dt_mod.datetime.now().strftime("%I:%M %p"),
        "read": False,
    })
    # Keep the list bounded
    if len(notifs) > 50:
        st.session_state["_spp_notifications"] = notifs[:50]


def render_notification_center() -> None:
    """Render a notification inbox in the sidebar."""
    notifs = st.session_state.get("_spp_notifications", [])
    unread = sum(1 for n in notifs if not n.get("read"))
    badge = f" ({unread})" if unread else ""

    with st.sidebar:
        with st.expander(f"🔔 Notifications{badge}", expanded=False):
            if not notifs:
                st.caption("No notifications yet.")
                return

            if unread and st.button("Mark all read", key="_notif_mark_read"):
                for n in notifs:
                    n["read"] = True
                st.rerun()

            if len(notifs) > 5 and st.button("Clear all", key="_notif_clear"):
                st.session_state["_spp_notifications"] = []
                st.rerun()

            for idx, n in enumerate(notifs[:20]):
                _s = _NOTIF_LEVEL_STYLES.get(n.get("level", "info"), _NOTIF_LEVEL_STYLES["info"])
                _weight = "600" if not n.get("read") else "400"
                _opacity = "1" if not n.get("read") else "0.65"
                st.markdown(
                    f'<div role="status" aria-label="Notification" style="padding:8px 10px;margin-bottom:6px;'
                    f'background:{_s["bg"]};border-left:3px solid {_s["border"]};'
                    f'border-radius:6px;opacity:{_opacity};">'
                    f'<div style="font-size:0.78rem;font-weight:{_weight};color:#E0E6F0;">'
                    f'{_s["icon"]} {n["title"]}'
                    f'<span style="float:right;font-size:0.65rem;color:#6B7A9A;">{n.get("ts", "")}</span></div>'
                    f'<div style="font-size:0.72rem;color:#A0AABE;margin-top:2px;">{n["message"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if not n.get("read"):
                    n["read"] = True


# ── Shareable Performance Report Card ────────────────────────────

def generate_performance_report_html(stats: dict) -> str:
    """Generate a self-contained HTML performance report card.

    Args:
        stats: Dict with keys: total, wins, losses, evens, pending,
               win_rate, streak, best_platform, date_range.

    Returns:
        A standalone HTML string suitable for download.
    """
    import datetime as _dt_mod
    _now = _dt_mod.datetime.now().strftime("%B %d, %Y %I:%M %p")
    _total = stats.get("total", 0)
    _wins = stats.get("wins", 0)
    _losses = stats.get("losses", 0)
    _wr = stats.get("win_rate", 0)
    _streak = stats.get("streak", 0)
    _streak_label = f"{_streak}W" if _streak > 0 else f"{abs(_streak)}L" if _streak < 0 else "—"
    _best_plat = stats.get("best_platform", "—") or "—"
    _scope = stats.get("date_range", "All Time")

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartBetPro Performance Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
background:#0E1117;color:#E0E6F0;display:flex;justify-content:center;padding:40px 16px}}
.card{{background:linear-gradient(135deg,#161B22 0%,#1A1F2B 100%);
border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:32px;
max-width:480px;width:100%;box-shadow:0 8px 32px rgba(0,0,0,0.4)}}
.header{{text-align:center;margin-bottom:24px}}
.header h1{{font-size:1.4rem;color:#00D559;margin-bottom:4px}}
.header p{{font-size:0.78rem;color:#6B7A9A}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
.stat{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
border-radius:10px;padding:14px;text-align:center}}
.stat .val{{font-size:1.6rem;font-weight:700;color:#F9C62B}}
.stat .lbl{{font-size:0.72rem;color:#6B7A9A;margin-top:4px;text-transform:uppercase}}
.wr .val{{color:#00D559}}
.footer{{text-align:center;font-size:0.68rem;color:#3A4460;margin-top:16px;
border-top:1px solid rgba(255,255,255,0.06);padding-top:12px}}
</style></head>
<body><div class="card">
<div class="header"><h1>🏀 SmartBetPro Report Card</h1>
<p>{_scope} &middot; Generated {_now}</p></div>
<div class="grid">
<div class="stat wr"><div class="val">{_wr:.1f}%</div><div class="lbl">Win Rate</div></div>
<div class="stat"><div class="val">{_total}</div><div class="lbl">Total Picks</div></div>
<div class="stat"><div class="val">{_wins}</div><div class="lbl">Wins</div></div>
<div class="stat"><div class="val">{_losses}</div><div class="lbl">Losses</div></div>
<div class="stat"><div class="val">{_streak_label}</div><div class="lbl">Streak</div></div>
<div class="stat"><div class="val" style="font-size:1rem;">{_best_plat}</div><div class="lbl">Best Platform</div></div>
</div>
<div class="footer">Powered by Smart Pick Pro &middot; smartbetpro.com</div>
</div></body></html>"""


# ── Mobile Responsive CSS ────────────────────────────────────────

def inject_mobile_responsive_css() -> None:
    """Inject additional mobile-responsive CSS for key pages."""
    if st.session_state.get("_mobile_css_injected"):
        return
    st.session_state["_mobile_css_injected"] = True
    st.markdown("""<style>
/* ── SmartBetPro Mobile Responsive Overrides ─────────── */
@media (max-width: 768px) {
    /* Stack column layouts vertically */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stHorizontalBlock"] > div {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
    /* Compact metrics */
    [data-testid="stMetric"] {
        padding: 8px 6px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
    }
    /* Readable tables */
    [data-testid="stDataFrame"] {
        font-size: 0.78rem !important;
    }
    /* Sidebar overlay */
    [data-testid="stSidebar"] {
        min-width: 260px !important;
        max-width: 85vw !important;
    }
    /* Account management section */
    .stTabs [data-baseweb="tab-panel"] {
        padding: 8px 4px !important;
    }
    /* Form inputs full width */
    .stTextInput, .stSelectbox, .stNumberInput {
        width: 100% !important;
    }
    /* Bet cards */
    [data-testid="stExpander"] {
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
}
@media (max-width: 480px) {
    /* Smaller headings on phones */
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.15rem !important; }
    h3 { font-size: 1rem !important; }
    /* Tighter padding */
    .block-container {
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
    /* Download buttons full width */
    .stDownloadButton > button {
        width: 100% !important;
    }
}
</style>""", unsafe_allow_html=True)


# ── ARIA Accessibility Helpers ───────────────────────────────────

def inject_aria_enhancements() -> None:
    """Inject JavaScript that adds ARIA attributes to custom HTML blocks."""
    if st.session_state.get("_aria_injected"):
        return
    st.session_state["_aria_injected"] = True
    _aria_script = (
        '<script>\n'
        '(function(){\n'
        '  if(window.__sppAria) return;\n'
        '  window.__sppAria=true;\n'
        '  function addAria(){\n'
        '    document.querySelectorAll("[data-testid=\\"stMetric\\"]").forEach(function(el){\n'
        '      if(!el.getAttribute("role")) el.setAttribute("role","status");\n'
        '    });\n'
        '    document.querySelectorAll("[data-testid=\\"stSidebar\\"] nav").forEach(function(el){\n'
        '      if(!el.getAttribute("aria-label")) el.setAttribute("aria-label","Page navigation");\n'
        '    });\n'
        '    document.querySelectorAll("[data-testid=\\"stExpander\\"]").forEach(function(el){\n'
        '      if(!el.getAttribute("role")) el.setAttribute("role","region");\n'
        '    });\n'
        '    document.querySelectorAll(".stTabs [role=\\"tablist\\"]").forEach(function(el){\n'
        '      if(!el.getAttribute("aria-label")) el.setAttribute("aria-label","Page sections");\n'
        '    });\n'
        '    document.querySelectorAll("[data-testid=\\"stDataFrame\\"]").forEach(function(el){\n'
        '      if(!el.getAttribute("role")) el.setAttribute("role","table");\n'
        '      if(!el.getAttribute("aria-label")) el.setAttribute("aria-label","Data table");\n'
        '    });\n'
        '  }\n'
        '  setTimeout(addAria,2000);\n'
        '  var obs=new MutationObserver(function(){setTimeout(addAria,500);});\n'
        '  obs.observe(document.body,{childList:true,subtree:true});\n'
        '})();\n'
        '</script>'
    )
    st.markdown(_aria_script, unsafe_allow_html=True)


# ── Lazy-loading pagination helpers ──────────────────────────────────────────
# Prevents browser OOM / slow renders when the bets table has 10 000+ rows.
# Uses session_state to persist the current page across Streamlit reruns, and
# delegates the actual DB fetch to a caller-supplied load_fn / count_fn pair.
#
# Usage (Tracking page example):
#
#   from utils.components import render_paginated_table
#   from tracking.database import load_bets_page, count_bets
#
#   def _load(offset, limit, filters):
#       return load_bets_page(offset=offset, limit=limit, **filters)
#
#   def _count(filters):
#       return count_bets(**filters)
#
#   render_paginated_table(_load, _count, filters, page_key="bets_page")

def render_paginated_table(
    load_fn,
    count_fn,
    filters: dict,
    *,
    page_size: int = 50,
    page_key: str = "paginated_table_page",
    df_height: int = 600,
) -> None:
    """Render a paginated dataframe using DB-side LIMIT / OFFSET queries.

    Fetches only *page_size* rows at a time so the Streamlit frontend never
    materialises the full result set in browser memory.

    Args:
        load_fn:   Callable(offset: int, limit: int, filters: dict) → list[dict]
                   Should map to database.load_bets_page() or equivalent.
        count_fn:  Callable(filters: dict) → int
                   Returns total row count matching *filters* (for page math).
        filters:   Arbitrary filter kwargs forwarded verbatim to both callables.
        page_size: Rows per page (default 50).
        page_key:  Unique session_state key for this table's current page index.
                   Override when multiple paginated tables appear on one page.
        df_height: Pixel height passed to st.dataframe (default 600).
    """
    import pandas as _pd

    # ── Page state ──────────────────────────────────────────────────────────
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    current_page: int = int(st.session_state[page_key])

    # ── Total row count (cheap COUNT(*) query) ───────────────────────────────
    try:
        total_rows = int(count_fn(filters) or 0)
    except Exception as _e:
        st.warning(f"Could not count rows: {_e}")
        total_rows = 0

    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    # Clamp page index in case filters changed and shrunk the result set
    current_page = min(current_page, total_pages - 1)
    st.session_state[page_key] = current_page

    # ── Load current page ────────────────────────────────────────────────────
    offset = current_page * page_size
    try:
        rows = load_fn(offset, page_size, filters)
    except Exception as _e:
        st.error(f"Failed to load data: {_e}")
        return

    if not rows:
        st.info("No data found for the selected filters.")
        return

    # ── Render dataframe ─────────────────────────────────────────────────────
    df = _pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=df_height)

    # ── Pagination controls ──────────────────────────────────────────────────
    col_prev, col_info, col_next = st.columns([1, 3, 1])

    with col_prev:
        if st.button("← Prev", key=f"{page_key}_prev", disabled=(current_page == 0)):
            st.session_state[page_key] = current_page - 1
            st.rerun()

    with col_info:
        start_row = offset + 1
        end_row = min(offset + len(rows), total_rows)
        st.markdown(
            f"<div style='text-align:center;font-size:0.8rem;color:#6B7A9A;padding-top:6px;'>"
            f"Rows {start_row}–{end_row} of {total_rows:,} &nbsp;|&nbsp; "
            f"Page {current_page + 1} of {total_pages}"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.button("Next →", key=f"{page_key}_next", disabled=(current_page >= total_pages - 1)):
            st.session_state[page_key] = current_page + 1
            st.rerun()


def reset_paginated_table(page_key: str = "paginated_table_page") -> None:
    """Reset a paginated table back to page 0.

    Call this whenever the user changes a filter so the view returns to the
    first page instead of landing mid-way through a stale result set.

    Args:
        page_key: Must match the page_key used when calling render_paginated_table().
    """
    st.session_state[page_key] = 0


# ============================================================
# SECTION: Attribution Components
# Consistent executive branding blocks for footer, sidebar,
# and page headers.  All credit the platform architect and
# lead analyst: Joseph M. Smith.
# ============================================================

def render_sidebar_attribution() -> None:
    """Render a compact Joseph M. Smith attribution card in the sidebar.

    Placed at the bottom of render_sidebar_auth() so it appears
    consistently across every authenticated page without extra
    per-page wiring.  Uses .spp-sidebar-attr CSS from get_premium_ui_css().
    """
    # Inject the premium CSS quietly — harmless duplicate if already injected
    try:
        from styles.theme import get_premium_ui_css as _puicss
        st.markdown(_puicss(), unsafe_allow_html=True)
    except Exception:
        pass

    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,700;0,800;0,900;1,700;1,800;1,900&family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');
.spp-sidebar-attr {
  position: relative;
  background: linear-gradient(135deg, rgba(0,213,89,0.05) 0%, rgba(45,158,255,0.04) 100%);
  border: 1px solid rgba(0,213,89,0.14);
  border-radius: 14px;
  padding: 12px 13px 11px;
  margin: 8px 0 6px;
  text-align: center;
  overflow: hidden;
}
.spp-sidebar-attr::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0,213,89,0.40), rgba(45,158,255,0.30), transparent);
}
.spp-sidebar-attr-label {
  color: rgba(255,255,255,0.22);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.48rem; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase;
  margin-bottom: 5px;
}
.spp-sidebar-attr-name {
  color: #E8F0FC;
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 1.0rem; font-weight: 900; font-style: italic;
  letter-spacing: 0.04em; text-transform: uppercase;
}
.spp-sidebar-attr-role {
  color: rgba(255,255,255,0.28);
  font-family: 'Inter', sans-serif;
  font-size: 0.60rem; font-weight: 500;
  margin-top: 2px; letter-spacing: 0.02em;
}
.spp-sidebar-attr-badge {
  display: inline-block;
  background: linear-gradient(90deg, rgba(0,213,89,0.10), rgba(45,158,255,0.08));
  color: #00D559;
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 0.68rem; font-weight: 900; font-style: italic;
  padding: 3px 12px; border-radius: 100px;
  border: 1px solid rgba(0,213,89,0.20);
  margin-top: 7px; letter-spacing: 0.05em; text-transform: uppercase;
  box-shadow: 0 0 14px rgba(0,213,89,0.12);
}
</style>
<div class="spp-sidebar-attr">
  <div class="spp-sidebar-attr-label">Platform Architecture</div>
  <div class="spp-sidebar-attr-name">Joseph M. Smith</div>
  <div class="spp-sidebar-attr-role">Lead AI Solutions Architect</div>
  <div class="spp-sidebar-attr-badge">⚡ Quantum Matrix Engine 5.6</div>
</div>
""", unsafe_allow_html=True)


def render_attribution_footer() -> None:
    """Render a full-width executive attribution footer.

    Injects the .spp-footer CSS block and renders a branded footer
    crediting Joseph M. Smith as the platform architect and analytics
    lead.  Call this at the end of any page's main content block so
    it appears consistently across the product.

    Usage::

        from utils.components import render_attribution_footer
        # ... page content ...
        render_attribution_footer()
    """
    import datetime as _dt

    try:
        from styles.theme import get_premium_ui_css as _puicss
        st.markdown(_puicss(), unsafe_allow_html=True)
    except Exception:
        pass

    _year = _dt.datetime.now().year
    st.markdown(f"""
<div class="spp-footer">
  <div class="spp-footer-logo">⚡ Smart Pick Pro</div>
  <div class="spp-footer-rule">
    <span class="spp-footer-rule-label">Platform Architecture &amp; Analytics</span>
  </div>
  <div class="spp-footer-name">Joseph M. Smith</div>
  <div class="spp-footer-title">
    Lead AI Solutions Architect &nbsp;·&nbsp; Platform Engineer &nbsp;·&nbsp; Head Analyst
  </div>
  <div class="spp-footer-badges">
    <span class="spp-footer-badge">🏀 NBA Prop Analytics</span>
    <span class="spp-footer-badge">⚡ Quantum Matrix Engine 5.6</span>
    <span class="spp-footer-badge">🔬 Quantum Simulation</span>
    <span class="spp-footer-badge">🛡️ Risk-Adjusted Betting Intelligence</span>
  </div>
  <div class="spp-footer-copy">
    © {_year} Smart Pick Pro · NBA Edition · For entertainment &amp; educational purposes only ·
    Not financial advice · Bet responsibly · 21+ · 1-800-GAMBLER
  </div>
</div>
""", unsafe_allow_html=True)

