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


# ── 1. Deterministic CSS Pre-Loader ─────────────────────────────────────────

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
    from styles.theme import get_global_css, get_premium_ui_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
    st.markdown(get_premium_ui_css(), unsafe_allow_html=True)


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
