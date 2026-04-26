# ============================================================
# FILE: utils/page_bootstrap.py
# PURPOSE: Deterministic page lifecycle functions that resolve the
#          theme-flash, transient traceback, and state-hydration
#          glitches that occur during multipage navigation.
#
# CALL ORDER (top of every page, immediately after set_page_config):
#
#   st.set_page_config(...)
#   from utils.page_bootstrap import inject_theme_css, init_session_state
#   inject_theme_css()          # 1 — dark background BEFORE any rendering
#   require_login()             # 2 — login form now renders with dark theme
#   init_session_state()        # 3 — guarantee all state keys exist
#   ... rest of page content ...
#
# WHY THIS ORDER MATTERS:
#   Streamlit re-executes the entire page script top-to-bottom on every
#   navigation event.  If require_login() renders the login/signup form
#   before get_global_css() is injected, Streamlit momentarily paints the
#   form in its default light theme — the "white flash".  Calling
#   inject_theme_css() first ensures the <style> block lands in the DOM
#   before any visible widget or form is emitted.
#
#   Similarly, if a subpage accesses st.session_state["analysis_results"]
#   with bracket notation before the home page has seeded that key, the
#   script raises a KeyError that flashes as a red traceback before the
#   try/except swallows it.  init_session_state() places a setdefault
#   barrier for every shared key so those reads are always safe.
# ============================================================

import streamlit as st
import inspect
import os


# ── Page-script → SEO preset mapping ─────────────────────────────────────────
# Maps the basename of each Streamlit page script to the key used in
# utils.seo.SEO_PAGES.  inject_theme_css() walks the call stack, finds the
# outermost page script, and calls inject_page_seo() automatically — so
# every page gets full meta/OG/JSON-LD injection with zero per-page boilerplate.
_SEO_SCRIPT_MAP: dict[str, str] = {
    "Smart_Picks_Pro_Home.py":       "Home",
    "home.py":                        "Home",
    "0_💦_Live_Sweat.py":            "Live Sweat",
    "1_📡_Live_Games.py":            "Live Games",
    "2_🔬_Prop_Scanner.py":          "Prop Scanner",
    "3_⚡_Quantum_Analysis_Matrix.py": "Quantum Analysis",
    "4_💰_Smart_Money_Bets.py":      "Smart Money Bets",
    "5_🎙️_The_Studio.py":           "The Studio",
    "6_📋_Game_Report.py":           "Game Report",
    "7_🔮_Player_Simulator.py":      "Player Simulator",
    "8_🧬_Entry_Builder.py":         "Entry Builder",
    "9_🛡️_Risk_Shield.py":          "Risk Shield",
    "10_📡_Smart_NBA_Data.py":       "Smart NBA Data",
    "11_🗺️_Correlation_Matrix.py":  "Correlation Matrix",
    "12_📈_Bet_Tracker.py":          "Bet Tracker",
    "13_📊_Proving_Grounds.py":      "Proving Grounds",
    "14_⚙️_Settings.py":            "Settings",
    "15_💎_Subscription_Level.py":   "Subscription",
    "16_🧾_Results_Ledger.py":       "Results Ledger",
    "99_🔐_Admin_Metrics.py":        "Admin Metrics",
}


# ── Critical fallback CSS ─────────────────────────────────────────────────────
# Injected unconditionally so that even if the Python script halts before the
# full theme module is imported, the browser still renders the dark palette and
# Streamlit's native exception/error widgets adopt the app's visual language.
_CRITICAL_FALLBACK_CSS = """
<style>
/* ── Base palette guarantee ── */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
.main, section.main { background-color: #070A13 !important; color: #c8d8f0 !important; }

/* ── Streamlit native exception widget ── */
[data-testid="stException"] {
    background: rgba(7,10,19,0.96) !important;
    border: 1px solid rgba(0,240,255,0.25) !important;
    border-radius: 12px !important;
    color: #c8d8f0 !important;
}
[data-testid="stException"] summary {
    color: #ff6b6b !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}
[data-testid="stException"] pre,
[data-testid="stException"] code {
    background: rgba(15,23,42,0.85) !important;
    color: #ff6b6b !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,107,107,0.15) !important;
}
/* ── Alert / info / warning banners ── */
[data-testid="stAlert"] {
    background-color: rgba(15,23,42,0.92) !important;
    border-radius: 10px !important;
    color: #c8d8f0 !important;
}
/* ── Prevent white-flash on skeleton/placeholder frames ── */
[data-testid="stSkeleton"] { background: rgba(15,23,42,0.4) !important; }
</style>
"""


# ── 1. Deterministic CSS Pre-Loader ─────────────────────────────────────────

def _inject_admin_sidebar_guard() -> None:
    """Hide admin-only sidebar nav items for non-admin users.

    Uses CSS attribute selectors on the sidebar ``<a>`` links whose text
    matches the admin page names.  Runs every render; zero overhead for admins.
    """
    try:
        from utils.auth_gate import is_admin_user
        if is_admin_user():
            return  # admins see everything
    except Exception:
        return  # if auth not loaded yet, default to hiding

    # Names that appear in the Streamlit sidebar nav links
    _ADMIN_PAGE_NAMES = [
        "Admin Metrics",
        "DB Manager",
        "Social Post Studio",
    ]
    # Build a CSS selector that matches <a> elements whose trimmed text equals
    # one of the admin page names (Streamlit renders them as spans inside <a>).
    selectors = ", ".join(
        f'[data-testid="stSidebarNav"] a[href*="{name.replace(" ", "_")}"]'
        for name in _ADMIN_PAGE_NAMES
    )
    # Also match by visible text via :has() for browsers that support it
    text_selectors = " ".join(
        f'[data-testid="stSidebarNavItems"] li:has(span[title="{name}"]) {{ display: none !important; }}'
        for name in _ADMIN_PAGE_NAMES
    )
    st.markdown(
        f"<style>\n"
        f"/* Hide admin-only pages from non-admin sidebar */\n"
        f"{text_selectors}\n"
        f"[data-testid='stSidebarNavItems'] li:has(a[href*='Admin_Metrics']) {{ display: none !important; }}\n"
        f"[data-testid='stSidebarNavItems'] li:has(a[href*='DB_Manager']) {{ display: none !important; }}\n"
        f"[data-testid='stSidebarNavItems'] li:has(a[href*='Social_Post_Studio']) {{ display: none !important; }}\n"
        f"</style>",
        unsafe_allow_html=True,
    )


def inject_theme_css() -> None:
    """Inject the global dark theme CSS *before* any login gate or content.

    Call this as the very first Streamlit command after ``st.set_page_config()``.
    The underlying CSS builder functions are decorated with
    ``@functools.lru_cache(maxsize=1)`` in ``styles/theme.py``, so the
    string is constructed once per process and returned instantly on
    subsequent page renders — no overhead per navigation event.

    This function must be called on *every* render cycle (not guarded by a
    session-state flag) because Streamlit requires each page render to
    re-emit all ``st.markdown`` / ``st.html`` DOM patches.
    """
    # 1a. Critical fallback first — tiny, fast, covers the error-box case
    st.markdown(_CRITICAL_FALLBACK_CSS, unsafe_allow_html=True)
    # 1b. Full premium theme
    from styles.theme import get_global_css, get_premium_ui_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
    st.markdown(get_premium_ui_css(), unsafe_allow_html=True)
    # 1c. SEO meta/OG/JSON-LD injection (auto-detected from call stack)
    _inject_page_seo_auto()
    # 1d. Hide admin-only sidebar items for non-admin users
    _inject_admin_sidebar_guard()


def _inject_page_seo_auto() -> None:
    """
    Walk the Python call stack to identify the current Streamlit page script
    and inject its SEO preset (meta tags, OG, Twitter Card, JSON-LD) via
    utils.seo.inject_page_seo().

    Called automatically by inject_theme_css() — no per-page boilerplate needed.
    Silently no-ops if detection fails or the SEO module is unavailable.
    """
    try:
        page_name: str | None = None
        for frame_info in inspect.stack():
            basename = os.path.basename(frame_info.filename)
            if basename in _SEO_SCRIPT_MAP:
                page_name = _SEO_SCRIPT_MAP[basename]
                break
        if page_name:
            from utils.seo import inject_page_seo
            inject_page_seo(page_name)
    except Exception:
        pass  # SEO injection must never crash the page


# ── 2. State Hydration Barrier ───────────────────────────────────────────────

def init_session_state() -> None:
    """Guarantee every shared session-state key exists before any UI renders.

    Call this immediately after ``require_login()`` (so it only runs for
    authenticated sessions) and before any ``st.*`` component that reads
    from session state.

    Uses ``setdefault`` exclusively — existing values written by the home
    page auto-init block, the DB restore, or a previous subpage visit are
    never overwritten.  Missing keys receive safe zero/empty defaults that
    prevent ``KeyError`` tracebacks during the split-second before the
    home page has seeded the full state.
    """
    _defaults: dict = {
        # ── Engine configuration ──────────────────────────────────────────
        "simulation_depth":        1000,
        "minimum_edge_threshold":  5.0,
        "entry_fee":               10.0,
        "total_bankroll":          1000.0,
        "kelly_multiplier":        0.25,
        "selected_platforms":      ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"],
        # ── Per-session NBA data ──────────────────────────────────────────
        "todays_games":            [],
        "analysis_results":        [],
        "selected_picks":          [],
        "session_props":           [],
        "loaded_live_picks":       [],
        "current_props":           [],
        "platform_props":          [],
        "injury_status_map":       {},
        # ── Joseph M. Smith AI analyst ────────────────────────────────────
        "joseph_enabled":          True,
        "joseph_used_fragments":   set(),
        "joseph_bets_logged":      False,
        "joseph_results":          [],
        "joseph_widget_mode":      None,
        "joseph_widget_selection": None,
        "joseph_widget_response":  None,
        "joseph_ambient_line":     "",
        "joseph_ambient_context":  "idle",
        "joseph_last_commentary":  "",
        "joseph_entry_just_built": False,
    }
    for key, default in _defaults.items():
        st.session_state.setdefault(key, default)
