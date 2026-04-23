# ============================================================
# FILE: Smart_Picks_Pro_Home.py
# PURPOSE: Main entry point for the SmartBetPro NBA Streamlit app.
#          Professional dark-themed landing page that sells outcomes,
#          guards the process, and converts first-time visitors.
# HOW TO RUN: streamlit run Smart_Picks_Pro_Home.py
# ============================================================

import streamlit as st
import datetime
import html as _html
import os
import base64
import logging

# ─── Load .env into os.environ early (before any env var reads) ───
try:
    from dotenv import load_dotenv as _load_dotenv
    from pathlib import Path as _DotenvPath
    _env_file = _DotenvPath(__file__).resolve().parent / ".env"
    if _env_file.exists():
        _load_dotenv(_env_file)
except ImportError:
    pass

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

# ─── Theme CSS — injected BEFORE login gate to prevent white flash ────────
from utils.page_bootstrap import inject_theme_css, init_session_state
inject_theme_css()

# ─── Global exception safety net ────────────────────────────────────────────
# Streamlit's script runner catches *most* exceptions and shows a native
# traceback widget.  This hook fires for exceptions that leak past that layer
# (e.g. during module-level imports, thread callbacks, etc.).  It:
#   1. Logs the full traceback to the server log (ops-visible, not user-visible)
#   2. Re-injects the theme CSS so the page stays dark even in failure state
#   3. Renders a user-friendly styled banner instead of a raw traceback
import sys as _sys

_original_excepthook = _sys.excepthook

def _smartai_excepthook(exc_type, exc_value, exc_tb):
    import traceback as _tb_mod
    logging.getLogger("smartai.global").error(
        "Unhandled top-level exception:\n%s",
        "".join(_tb_mod.format_exception(exc_type, exc_value, exc_tb)),
    )
    try:
        inject_theme_css()
    except Exception:
        pass
    try:
        st.error(
            "⚠️ **An unexpected error occurred.** Our team has been notified. "
            "Please refresh the page or navigate to another section."
        )
    except Exception:
        _original_excepthook(exc_type, exc_value, exc_tb)

_sys.excepthook = _smartai_excepthook

# ─── Verify DB volume is persistent (log once per session) ───
if not st.session_state.get("_db_volume_checked"):
    import logging as _logging, os as _os
    _db_logger = _logging.getLogger("smartai.startup")
    _db_dir = _os.environ.get("DB_DIR", "")
    from tracking.database import DB_FILE_PATH as _DB_FILE_PATH
    _db_logger.info(
        "DB path: %s | exists: %s | size: %s bytes",
        _DB_FILE_PATH,
        _DB_FILE_PATH.exists(),
        _DB_FILE_PATH.stat().st_size if _DB_FILE_PATH.exists() else 0,
    )
    if _db_dir and not _os.path.ismount(_db_dir):
        _db_logger.warning(
            "DB_DIR=%s is NOT a mount point — user data will be lost on container restart. "
            "Create a Railway volume named 'smartai_data' mounted at /data.",
            _db_dir,
        )
    st.session_state["_db_volume_checked"] = True

# ─── Seed admin account from env vars (idempotent) ────────────
try:
    from utils.auth_gate import seed_admin_account as _seed_admin
    _seed_admin()
except Exception:
    pass

# ─── Login / Signup Gate — must be before ANY content ─────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ─── State hydration barrier — guarantee all shared keys exist ─
init_session_state()

# ─── Analytics: GA4 injection + server-side page view ─────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Home")

# ─── SEO: Meta tags, OG, JSON-LD, canonical ──────────────────
from utils.seo import inject_page_seo
inject_page_seo("Home")

# ─── Background ETL staleness guard (once per session) ────────
# If the ETL database is more than 1 day stale, kick off an
# incremental update in a background thread so users always
# see fresh data — without blocking the UI.
if not st.session_state.get("_etl_staleness_checked"):
    st.session_state["_etl_staleness_checked"] = True
    try:
        import sqlite3 as _sq
        from pathlib import Path as _Path
        from datetime import date as _date, datetime as _dt, timedelta as _td
        _etl_db = _Path(os.environ.get(
            "DB_DIR", str(_Path(__file__).resolve().parent / "db")
        )) / "smartpicks.db"
        if _etl_db.exists():
            _conn = _sq.connect(str(_etl_db))
            _row = _conn.execute("SELECT MAX(game_date) FROM Games").fetchone()
            _conn.close()
            _last = _dt.strptime(_row[0], "%Y-%m-%d").date() if _row and _row[0] else None
            if _last is None or (_date.today() - _last) > _td(days=1):
                import threading as _thr
                def _bg_etl_refresh():
                    try:
                        from etl.data_updater import run_update
                        run_update()
                    except Exception:
                        pass  # non-critical background task
                _thr.Thread(target=_bg_etl_refresh, daemon=True).start()
                logging.getLogger(__name__).info(
                    "ETL staleness guard: DB last_date=%s — background refresh started.", _last
                )
    except Exception:
        pass  # never block the UI for a staleness check

# ─── Recurring ETL scheduler (daemon thread, runs once per process) ───
try:
    from etl.scheduler import start as _start_etl_scheduler
    _start_etl_scheduler()
except Exception:
    pass  # non-critical — staleness guard above is the safety net

# ─── Data-version check: clear stale session cache when scheduler writes fresh data ───
# The background scheduler calls _bump_data_version() every time it writes new
# picks or props to disk.  We read cache/data_version.json on every Streamlit
# render cycle (it's a tiny file).  When the version has advanced beyond what
# this session last saw, we reset _picks_seeded so the block below re-reads
# the DB — giving users live data without a manual page reload.
try:
    import json as _jv
    from pathlib import Path as _Pv
    _version_path = _Pv(__file__).resolve().parent / "cache" / "data_version.json"
    if _version_path.exists():
        _ver_data = _jv.loads(_version_path.read_text(encoding="utf-8"))
        _new_ver = _ver_data.get("version", 0)
        _seen_ver = st.session_state.get("_data_version_seen", 0)
        if _new_ver > _seen_ver:
            # New data written by scheduler — clear stale session state so
            # the seed block below picks up fresh picks and props from DB.
            st.session_state["_data_version_seen"] = _new_ver
            st.session_state.pop("_picks_seeded", None)
            st.session_state.pop("analysis_results", None)
            st.session_state.pop("current_props", None)
            st.session_state.pop("platform_props", None)
            st.session_state.pop("todays_games", None)
            st.session_state.pop("_auto_init_date", None)
except Exception:
    pass

# ─── Auto-seed picks & props into session on first load ───────
# Reads ONLY from the database (pre-populated by slate_worker.py).
# Never calls external APIs or runs analysis — instant for the user.
@st.cache_data(ttl=300, show_spinner=False)
def _load_cached_slate() -> tuple[list, list]:
    """Read today's pre-computed picks + props from the DB.

    Wrapped in @st.cache_data(ttl=300) so concurrent logins share a
    single DB round-trip for up to 5 minutes, preventing thundering-herd
    hammering during peak evening traffic.

    Returns:
        (picks, props) — both may be empty lists if the worker hasn't run
        yet for today.
    """
    from tracking.database import get_slate_picks_for_today
    from data.data_manager import load_platform_props_from_csv as _lpc
    picks = get_slate_picks_for_today()
    try:
        props = _lpc() or []
    except Exception:
        props = []
    return picks, props

if not st.session_state.get("_picks_seeded"):
    st.session_state["_picks_seeded"] = True
    try:
        _cached_picks, _cached_props = _load_cached_slate()
        if _cached_props:
            st.session_state.setdefault("current_props", _cached_props)
            st.session_state.setdefault("platform_props", _cached_props)
        if _cached_picks and not st.session_state.get("analysis_results"):
            st.session_state["analysis_results"] = _cached_picks
    except Exception:
        pass

# ─── No picks yet — slate_worker hasn't run today ─────────────────────────
# Show a non-blocking info banner instead of triggering a live pipeline run.
# The etl.scheduler daemon (already running) will populate picks within its
# next cycle; or an admin can trigger slate_worker.py manually.
if not st.session_state.get("analysis_results"):
    st.info(
        "⏳ Tonight's slate analysis is being prepared in the background. "
        "Picks will appear automatically within a few minutes — no action needed.",
        icon="🔄",
    )

# ─── Landing Page Theme CSS — page-level overrides ───────────
from styles.theme import get_home_page_css as _get_home_page_css
st.markdown(_get_home_page_css(), unsafe_allow_html=True)

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
    _db_path = os.environ.get("DB_PATH", os.path.join(os.environ.get("DB_DIR", "db"), "smartai_nba.db"))
    if os.path.basename(_db_path) == "smartai_nba.db":
        logging.getLogger(__name__).warning(
            "Running in production mode with SQLite (%s). "
            "SQLite is not recommended for multi-user cloud deployments. "
            "Consider PostgreSQL or persistent storage. See docs/database_migration.md",
            _db_path,
        )
        # SQLite production warning removed — acceptable for single-instance Railway deploy.

# ── Premium Status — Check and display in sidebar ─────────────
# This runs silently on app load.  is_premium_user() is cached in
# session state so it won't make Stripe API calls on every rerun.
try:
    from utils.auth import (
        is_premium_user as _is_premium,
        handle_checkout_redirect as _handle_checkout,
        get_user_tier as _get_user_tier,
        get_tier_label as _get_tier_label,
        TIER_FREE,
    )
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
    # Handle checkout redirects even on the home page
    _checkout_ok = _handle_checkout()
    _user_is_premium = _is_premium()
    _user_tier = _get_user_tier()
    _user_tier_label = _get_tier_label(_user_tier)
    from utils.auth_gate import render_subscription_success_page, render_onboarding_tour
    if _checkout_ok:
        # Show rich success celebration page + launch tour
        if render_subscription_success_page(_user_tier_label):
            st.stop()
    # Show onboarding tour for new signups (flag set by _render_signup_form)
    render_onboarding_tour()
except Exception:
    _user_is_premium = True  # Fail open — don't block the home page
    _user_tier = "insider_circle"
    _user_tier_label = "👑 Insider Circle"
    _PREM_PATH = "/15_%F0%9F%92%8E_Subscription_Level"
    TIER_FREE = "free"

from utils.components import render_sidebar_auth as _render_sb_auth
with st.sidebar:
    _render_sb_auth()

# ── Restore user settings from database before applying defaults ───────
# On a fresh browser reload st.session_state is empty.  We read the
# user's last-saved settings from SQLite so they don't have to
# reconfigure everything.  Keys not in the DB fall through to the
# hard-coded defaults below.
if not st.session_state.get("_user_settings_loaded"):
    st.session_state["_user_settings_loaded"] = True
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
from utils.components import render_global_settings, inject_joseph_floating, render_joseph_hero_banner, inject_sidebar_nav_tooltips, render_notification_center, inject_mobile_responsive_css, inject_aria_enhancements
with st.sidebar:
    render_global_settings()
st.session_state["joseph_page_context"] = "page_home"
inject_joseph_floating()
inject_sidebar_nav_tooltips()
render_notification_center()
inject_mobile_responsive_css()
inject_aria_enhancements()

# ============================================================
# END SECTION: Initialize App on Startup
# ============================================================

# ─── Theme re-injection guard ─────────────────────────────────────────────
# Executing a second inject_theme_css() here guarantees the full CSS suite
# is in the DOM even if an exception fired in the setup block above and
# Streamlit skipped the first injection's render pass.
inject_theme_css()

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
<div class="neural-grid"></div>
<div class="lp-orbs-container">
  <div class="lp-orb lp-orb-1"></div>
  <div class="lp-orb lp-orb-2"></div>
  <div class="lp-orb lp-orb-3"></div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="live-analysis-bar lp-anim">
  <span class="live-dot"></span>
  <span class="lab-accent">LIVE</span>
  <span class="lab-dim">&nbsp;&mdash;&nbsp;</span>
  <span>NBA prop engine active &nbsp;&bull;&nbsp; {game_count_text} &nbsp;&bull;&nbsp; <span class="lab-accent">Monte Carlo online</span></span>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero-hud lp-anim">
  <div class="hero-hud-inner-glow"></div>
  <div class="hero-hud-text">
    <div class="hero-badge-row">
      <span class="hero-badge hero-badge-ai">🤖 Monte Carlo AI</span>
      <span class="hero-badge hero-badge-free">✅ Free Picks Daily</span>
      <span class="hero-badge hero-badge-dfs">🏀 PrizePicks + Underdog</span>
    </div>
    <div class="hero-tagline">THE NBA PROP ENGINE THAT SHOWS ITS WORK</div>
    <div class="hero-subtext"><strong>5,000+ Live Props. 1,000 Simulations Each. Zero Black Boxes.</strong> Know the edge before you enter.</div>
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
        # ── Phase 1: Auto-Load Tonight's Games ────────────────────────
        _hoc_status.text("⏳ Phase 1/3 — Auto-loading tonight's games, rosters & stats…")
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
        _hoc_status.text(f"⏳ Phase 1/3 — {len(_hoc_games)} game(s) loaded. Loading player data…")

        _hoc_players_ok = _hoc_fp(_hoc_games) if _hoc_games else False
        _hoc_bar.progress(40)

        # Clear caches so freshly-written players.csv is read
        _hoc_cc()

        try:
            st.session_state["injury_status_map"] = _hoc_li()
        except Exception:
            pass

        # ── Phase 2: Load team stats & standings ─────────────────────
        _hoc_status.text("⏳ Phase 2/3 — Loading team stats & standings…")
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
        _hoc_status.text("⏳ Phase 3/3 — Retrieving live prop lines from all platforms…")

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

        # ── Phase 4: Run Neural Analysis on all loaded props ─────────
        _hoc_analysis_msg = ""
        try:
            _hoc_status2 = st.empty()
            _hoc_bar2 = st.progress(0)
            _hoc_status2.text("⏳ Phase 4/4 — Running Neural Analysis on all loaded props…")
            _hoc_bar2.progress(10)
            from data.data_manager import (
                load_props_from_session as _hoc_lps,
                load_players_data as _hoc_lpd,
                load_teams_data as _hoc_ltd,
                load_defensive_ratings_data as _hoc_ldr,
            )
            from engine.analysis_orchestrator import analyze_props_batch as _hoc_analyze
            _hoc_aprops   = _hoc_lps(st.session_state)
            _hoc_aplayers = _hoc_lpd()
            _hoc_ateams   = _hoc_ltd()
            _hoc_aratings = _hoc_ldr()
            _hoc_agames   = st.session_state.get("todays_games", [])
            _hoc_bar2.progress(20)
            if _hoc_aprops and _hoc_aplayers:
                _hoc_results = _hoc_analyze(
                    _hoc_aprops,
                    players_data=_hoc_aplayers,
                    todays_games=_hoc_agames,
                    injury_map=st.session_state.get("injury_status_map", {}),
                    defensive_ratings_data=_hoc_aratings,
                    teams_data=_hoc_ateams,
                    simulation_depth=1000,
                )
                _hoc_bar2.progress(90)
                if _hoc_results:
                    st.session_state["analysis_results"] = _hoc_results
                    import datetime as _hoc_dt
                    st.session_state["analysis_timestamp"] = _hoc_dt.datetime.now()
                    try:
                        from tracking.database import (
                            save_analysis_session as _hoc_sas,
                            insert_analysis_picks as _hoc_iap,
                        )
                        _hoc_sas(
                            analysis_results=_hoc_results,
                            todays_games=_hoc_agames,
                            selected_picks=st.session_state.get("selected_picks", []),
                        )
                        _hoc_iap(_hoc_results)
                    except Exception:
                        pass
                    _hoc_analysis_msg = f"✅ {len(_hoc_results)} picks analyzed"
                else:
                    _hoc_analysis_msg = "⚠️ Analysis returned no results"
            else:
                _hoc_analysis_msg = "⚠️ No props or player data to analyze"
            _hoc_bar2.progress(100)
            _hoc_bar2.empty()
            _hoc_status2.empty()
        except Exception as _hoc_ae:
            _hoc_analysis_msg = f"⚠️ Analysis failed: {_hoc_ae}"

        _hoc_total = len(st.session_state.get("current_props", []))
        st.success(
            f"✅ **One-Click Setup complete!** "
            f"Games: {'✅ ' + str(len(_hoc_games)) if _hoc_games else '⚠️ none'} | "
            f"Players: {'✅' if _hoc_players_ok else '⚠️ check data'} | "
            f"Props: {_hoc_platform_msg} | "
            f"Analysis: {_hoc_analysis_msg}"
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
            from utils.components import show_friendly_error
            show_friendly_error(_hoc_err, context="loading tonight's slate")

# ============================================================
# END SECTION 1: Cinematic Hero
# ============================================================

# ── Social Proof Strip — credibility numbers under the CTA ────
st.markdown("""
<div class="spp-proof-strip lp-anim lp-anim-d2">
  <div class="spp-proof-item">
    <div class="spp-proof-num green">5,000+</div>
    <div class="spp-proof-label">Live Props Nightly</div>
  </div>
  <div class="spp-proof-divider"></div>
  <div class="spp-proof-item">
    <div class="spp-proof-num blue">1,000</div>
    <div class="spp-proof-label">Sims Per Prop</div>
  </div>
  <div class="spp-proof-divider"></div>
  <div class="spp-proof-item">
    <div class="spp-proof-num gold">16</div>
    <div class="spp-proof-label">NBA Signals</div>
  </div>
  <div class="spp-proof-divider"></div>
  <div class="spp-proof-item">
    <div class="spp-proof-num">100%</div>
    <div class="spp-proof-label">Transparent Reasoning</div>
  </div>
  <div class="spp-proof-divider"></div>
  <div class="spp-proof-item">
    <div class="spp-proof-num green">FREE</div>
    <div class="spp-proof-label">Top Picks Every Night</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECTION 1-ONBOARD: First-Time User Getting Started Guide
# ============================================================

_has_analysis = bool(st.session_state.get("analysis_results"))
_onboard_dismissed = st.session_state.get("_onboarding_dismissed", False)

if not _has_analysis and not _onboard_dismissed:
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(0,213,89,0.06),rgba(249,198,43,0.06));
         border:1px solid rgba(0,213,89,0.2);border-radius:14px;padding:28px 24px;margin:18px 0 24px 0;">
      <div style="font-size:1.4rem;font-weight:800;color:#F9C62B;margin-bottom:6px;">
        🚀 Welcome to Smart Pick Pro!
      </div>
      <div style="color:#c8d6e5;font-size:0.92rem;margin-bottom:18px;">
        Get your first AI-powered picks in <strong>3 easy steps</strong>:
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:14px;">
        <div style="flex:1;min-width:200px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
             border-radius:10px;padding:16px;">
          <div style="font-size:1.6rem;margin-bottom:4px;">1️⃣</div>
          <div style="color:#00D559;font-weight:700;font-size:0.9rem;">Load Tonight's Slate</div>
          <div style="color:#8b949e;font-size:0.8rem;margin-top:4px;">
            Click the <strong>⚡ LOAD TONIGHT'S SLATE</strong> button above. This fetches games, rosters, injuries, and live prop lines automatically.
          </div>
        </div>
        <div style="flex:1;min-width:200px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
             border-radius:10px;padding:16px;">
          <div style="font-size:1.6rem;margin-bottom:4px;">2️⃣</div>
          <div style="color:#00D559;font-weight:700;font-size:0.9rem;">Run Neural Analysis</div>
          <div style="color:#8b949e;font-size:0.8rem;margin-top:4px;">
            Go to the <strong>⚡ Neural Analysis</strong> page in the sidebar and click <strong>Run Analysis</strong>. The AI engine will score every prop.
          </div>
        </div>
        <div style="flex:1;min-width:200px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
             border-radius:10px;padding:16px;">
          <div style="font-size:1.6rem;margin-bottom:4px;">3️⃣</div>
          <div style="color:#00D559;font-weight:700;font-size:0.9rem;">Review Your Picks</div>
          <div style="color:#8b949e;font-size:0.8rem;margin-top:4px;">
            Come back here to see your <strong>Top 3 Tonight</strong> hero cards, or visit <strong>📋 Smart Picks</strong> for the full ranked list.
          </div>
        </div>
      </div>
      <div style="color:#6b7280;font-size:0.75rem;margin-top:14px;text-align:center;">
        💡 Tip: Visit <strong>⚙️ Settings</strong> to customize your edge threshold, simulation depth, and platform preferences.
      </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("✕ Dismiss Guide", key="_dismiss_onboarding"):
        st.session_state["_onboarding_dismissed"] = True
        st.rerun()

# ============================================================
# END SECTION 1-ONBOARD
# ============================================================

# ============================================================
# SECTION 1A: Top 3 Tonight — Hero Cards
# ============================================================

_home_analysis = st.session_state.get("analysis_results", [])

if _user_tier == TIER_FREE:
    _cta_html = (
        "<div style='text-align:center;padding:36px 20px;"
        "background:rgba(19,25,32,0.7);border:1px solid rgba(0,212,255,0.15);"
        "border-radius:16px;margin-bottom:24px;'>"
        "<div style='font-size:2.4rem;margin-bottom:10px;'>🔒</div>"
        "<p style='color:#00d4ff;font-size:1.2rem;font-weight:800;margin:0 0 8px;'>"
        "Tonight's Top Picks</p>"
        "<p style='color:#a0b4d0;font-size:0.92rem;margin:0 0 18px;'>"
        "Upgrade to unlock the AI nightly Platinum &amp; Gold picks.</p>"
        f"<a href='{_PREM_PATH}' style='display:inline-block;"
        "background:linear-gradient(135deg,#F9C62B,#FF8C00);color:#0a0e14;"
        "font-weight:800;font-size:0.95rem;padding:12px 32px;border-radius:10px;"
        "text-decoration:none;'>⚡ Upgrade Now</a></div>"
    )
    st.markdown(_cta_html, unsafe_allow_html=True)

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

if _user_tier != TIER_FREE and _hero_pool:
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

if _user_tier != TIER_FREE and _home_edge_gap_picks:
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
        "I've been watching the lines all day and I already know where the books made mistakes. "
        "Let's run the engine and find your edge."
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
<div class="section-eyebrow lp-anim lp-anim-d1">The Unfair Advantage</div>
<div class="section-header-xl lp-anim lp-anim-d2">Other Tools Guess. <span class="xl-accent">We Simulate.</span></div>
<div class="section-subheader-center lp-anim lp-anim-d3">The only prop engine purpose-built for NBA DFS — live data from PrizePicks &amp; Underdog, Monte Carlo simulation, and full transparent reasoning. No human bias. No black box.</div>
""", unsafe_allow_html=True)

# ── 3A: Three Pillars ───────────────────────────────────────────
_p1, _p2, _p3 = st.columns(3)

with _p1:
    st.markdown("""
    <div class="pillar-card accent-cyan lp-anim lp-anim-d2">
      <div class="pillar-accent"></div>
      <div class="pillar-card-inner">
        <div class="pillar-icon-halo"><span class="pillar-icon">🎲</span></div>
        <div class="pillar-title">Monte Carlo Simulation Engine</div>
        <div class="pillar-subtitle">Up to 1,000 Simulated Games Per Prop — Tonight's Matchup, Not a Generic Average</div>
        <div class="pillar-body">
          Every prop runs through up to 1,000 simulated game scenarios —
          randomized minutes, real NBA pace data, matchup-specific defensive
          ratings, fatigue, and game-flow volatility.
          <br><br>
          The result: a <strong>probability distribution</strong> built for
          YOUR player in TONIGHT'S specific context — not recycled season averages.
          <br><br>
          <strong>Choose simulation depth:</strong>
          <ul>
            <li>⚡ Fast — instant results</li>
            <li>🎯 Standard — recommended balance</li>
            <li>🔬 Deep Scan — maximum accuracy</li>
          </ul>
          Every result includes percentile ranges, confidence intervals,
          and visual histograms — so you see the full picture, not just a number.
        </div>
        <div class="pillar-footer">Dimers, Action Network: editorial picks. No simulation depth.</div>
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
        <div class="pillar-subtitle">16 NBA-Specific Signals. Every Pick Tells You Exactly WHY.</div>
        <div class="pillar-body">
          Every prop shows the exact forces pushing performance UP or DOWN —
          pulled from live NBA data no other prop tool integrates:
          <br><br>
          ✅ Defensive matchup ratings &amp; hustle stats<br>
          ✅ Clutch-time performance splits<br>
          ✅ Pace, game environment &amp; blowout risk<br>
          ✅ Rest, back-to-back fatigue &amp; load signals<br>
          ✅ Injury impact on usage share<br>
          ✅ Trap Line Detection — catches lines designed to bait the public
          <br><br>
          You see OVER forces vs UNDER forces with strength ratings.
          No "trust us" scores. <strong>Full transparency on every single pick.</strong>
        </div>
        <div class="pillar-footer">Other tools give you a score. We show you the actual math.</div>
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
        <div class="pillar-subtitle">Statistical Analysis of Force &amp; Edge — Not a Capper's Opinion</div>
        <div class="pillar-body">
          A proprietary 0–100 composite score that blends multiple independent
          signals — simulation probability, edge magnitude, matchup quality,
          consistency, momentum, and market consensus — into one actionable number.
          <br><br>
          <strong>Built-in anti-overconfidence safeguards:</strong>
          <br><br>
          🛡️ Automatic tier demotion triggers<br>
          🛡️ Variance-aware scoring<br>
          🛡️ Sample-size adjustments<br>
          🛡️ Tier distribution enforcement<br>
          🛡️ No picks inflated by narrative or recency bias
          <br><br>
          💎 Platinum · 🥇 Gold · 🥈 Silver · 🥉 Bronze · ⛔ Avoid
          <br><br>
          No pay-per-pick capper. No guru with a hot streak.
          Pure statistical rigor, automated every night.
        </div>
        <div class="pillar-footer">StatSalt cappers charge $30–$89 per pick. This runs free.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── 3B: Comparison Table ────────────────────────────────────────
st.markdown("""
<div style="margin-top:28px;">
<table class="comp-table">
  <thead>
    <tr>
      <th>Feature</th>
      <th>Dimers / Action Network</th>
      <th>StatSalt / Cappers</th>
      <th>Smart Pick Pro</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>NBA-Specific Depth</td>
      <td class="cross">✗ Multi-sport, spread thin</td>
      <td class="cross">✗ Generic sports coverage</td>
      <td class="check">✓ Hustle stats, clutch splits, defensive ratings, bio data</td>
    </tr>
    <tr>
      <td>Simulation Engine</td>
      <td class="cross">✗ Editorial picks, no simulation</td>
      <td class="cross">✗ Human handicapper opinion</td>
      <td class="check">✓ Monte Carlo — up to 1,000 sims per prop</td>
    </tr>
    <tr>
      <td>PrizePicks + Underdog Integration</td>
      <td class="cross">✗ Not integrated</td>
      <td class="cross">✗ Not integrated</td>
      <td class="check">✓ Live 5,000+ props pulled directly from both platforms</td>
    </tr>
    <tr>
      <td>Transparent Reasoning</td>
      <td class="partial">⚠ Article with opinion</td>
      <td class="cross">✗ "Trust my record"</td>
      <td class="check">✓ Force breakdown — every factor shown with strength rating</td>
    </tr>
    <tr>
      <td>Automated Daily Pipeline</td>
      <td class="cross">✗ Human writers, not automated</td>
      <td class="cross">✗ Manual picks posted per game</td>
      <td class="check">✓ Auto-runs ETL → simulation → picks every day at 5pm ET</td>
    </tr>
    <tr>
      <td>Trap Line Detection</td>
      <td class="cross">✗ None</td>
      <td class="cross">✗ None</td>
      <td class="check">✓ Proprietary multi-pattern trap detection system</td>
    </tr>
    <tr>
      <td>Risk Shield + Avoid Flags</td>
      <td class="cross">✗ No auto-avoidance</td>
      <td class="cross">✗ No auto-avoidance</td>
      <td class="check">✓ Auto-flags injured, DNP risk, trap, and garbage-time props</td>
    </tr>
    <tr>
      <td>Entry Builder (Parlay Optimizer)</td>
      <td class="partial">⚠ Basic parlay picker</td>
      <td class="cross">✗ None</td>
      <td class="check">✓ EV-optimized builder for PrizePicks, Underdog, Pick6</td>
    </tr>
    <tr>
      <td>Live In-Game Sweat Tracking</td>
      <td class="cross">✗ Box score only</td>
      <td class="cross">✗ Box score only</td>
      <td class="check">✓ Live Sweat Room — real-time pace and projection updates</td>
    </tr>
    <tr>
      <td>Cost Per Pick</td>
      <td class="partial">⚠ $29.99/month (all sports)</td>
      <td class="cross">✗ $15–$89 per pick</td>
      <td class="check">✓ Free top picks daily. No per-pick fees.</td>
    </tr>
  </tbody>
</table>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="urgency-block lp-anim lp-anim-d3">
  <div class="urgency-title">⚡ Tonight's Edge Window Closes at Tip-Off</div>
  <div class="urgency-subtitle">
    Prop lines shift as lineups confirm and sharp money moves.
    <strong>Load tonight's slate now</strong> to lock in the best edges
    before the books adjust. <span class="blue">Free. No credit card. No per-pick fees.</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# SECTION 4: The Proof Points — Animated Metric Cards
# ============================================================

st.markdown("""
<div class="section-eyebrow lp-anim lp-anim-d1">By the Numbers</div>
<div class="section-header-xl lp-anim lp-anim-d2">Built Different. <span class="xl-accent">Proven By Design.</span></div>
""", unsafe_allow_html=True)

_proof_cols = st.columns(5)

_proof_data = [
    ("5,000+", "Live Props Analyzed Daily"),
    ("1,000", "Monte Carlo Sims Per Prop"),
    ("16", "NBA-Specific Data Signals"),
    ("100%", "Transparent Reasoning"),
    ("FREE", "Top Picks Every Night"),
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
        _wr6 = _track_record["win_rate"]
        _tot6 = _track_record["total"]
        _color6 = "#00D559" if _wr6 >= 60 else "#F9C62B" if _wr6 >= 50 else "#F24336"
        st.markdown(f"""
        <div class="proof-card lp-anim lp-anim-d6">
          <div class="proof-card-number" style="color:{_color6};">{_wr6:.0f}%</div>
          <div class="proof-card-label">Tracked Win Rate ({_tot6} picks)</div>
        </div>
        """, unsafe_allow_html=True)
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
        # Route staleness info to the notification center instead of bare st.warning()
        try:
            from utils.components import add_notification
            add_notification("Data Refresh Needed", _staleness_warn, level="warning")
        except Exception:
            pass
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
<div class="section-eyebrow lp-anim lp-anim-d1">The Pipeline</div>
<div class="section-header-xl lp-anim lp-anim-d2">From Raw Data to <span class="xl-accent">Ranked Picks</span></div>
<div class="section-subheader-center lp-anim lp-anim-d3">From raw NBA data to ranked, explained picks — automated every night, no human bias involved.</div>
""", unsafe_allow_html=True)

_hiw_stages = [
    ("📡", "Live Data Pull",
     "Real-time NBA data ingested: player stats, hustle metrics, clutch splits, defensive ratings, injuries, and 5,000+ live prop lines from PrizePicks and Underdog."),
    ("📐", "Matchup Projection",
     "Each player's baseline is adjusted for tonight's specific opponent, pace, game environment, rest days, and injury-impacted usage — no generic season averages."),
    ("🎲", "Monte Carlo Simulation",
     "Up to 1,000 simulated games per prop. Every sim randomizes real NBA game chaos — minutes volatility, momentum swings, blowout risk — to build a true probability distribution."),
    ("🔬", "Force Analysis",
     "16 NBA-specific signals are measured, strength-rated, and balanced. Trap lines are flagged. Coin-flip props are caught and filtered before they reach your picks list."),
    ("🏆", "SAFE Score™ + Tier Assignment",
     "A proprietary multi-signal composite with anti-overconfidence safeguards assigns every prop a ranked tier: Platinum, Gold, Silver, Bronze, or Avoid — with full reasoning attached."),
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
            st.markdown('<div class="hiw-connector">→</div>', unsafe_allow_html=True)

with st.expander("📖 How to Use Smart Pick Pro — Getting Started in 60 Seconds", expanded=False):
    st.markdown("""
    **The 3-Step Workflow**
    1. **📡 Load Tonight's Slate** — Click "⚡ Load Tonight's Slate" above. Auto-fetches games, rosters, injuries, and 5,000+ live props from PrizePicks and Underdog.
    2. **⚡ Run the Engine** — Go to **⚡ Quantum Analysis** in the sidebar and click **Run Analysis**. The engine simulates each prop up to 1,000 times and ranks every one.
    3. **🏆 Review Your Edge** — Your top picks appear here with full Force Analysis reasoning — know exactly WHY each pick is rated, not just a score.

    💡 **Pro Tip:** Use the one-click button above to load everything in a single action, then head to Quantum Analysis to run the engine.
    
    ⚙️ Visit **Settings** to tune simulation depth, edge threshold, and platform preferences for your betting style.
    """)

st.markdown('<div class="lp-divider"></div>', unsafe_allow_html=True)

# ============================================================
# END SECTION 6: How It Works
# ============================================================

# ============================================================
# SECTION 7: App Map — Interactive Navigation Cards
# ============================================================

st.markdown("""
<div class="section-eyebrow lp-anim lp-anim-d1">Navigate the Platform</div>
<div class="section-header-xl lp-anim lp-anim-d2">Your <span class="xl-accent">Command Center</span></div>
<div class="section-subheader-center lp-anim lp-anim-d3">Every tool built to take you from raw lines to confident, edge-verified entries — all in one place.</div>
""", unsafe_allow_html=True)

# Row 1 — Tonight's Workflow
st.markdown('<div class="nav-row-label workflow">⚡ Tonight\'s Workflow</div>', unsafe_allow_html=True)
_nav_r1 = st.columns(4)
_nav_row1 = [
    ("📡", "Live Games", "Load tonight's slate in one click", "pages/1_📡_Live_Games.py"),
    ("🔬", "Prop Scanner", "Enter props manually or pull live lines", "pages/2_🔬_Prop_Scanner.py"),
    ("⚡", "Quantum Analysis", "Run the Quantum Matrix Engine", "pages/3_⚡_Quantum_Analysis_Matrix.py"),
    ("🧬", "Entry Builder", "Build EV-optimized parlays", "pages/8_🧬_Entry_Builder.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row1):
    with _nav_r1[i]:
        st.markdown(f"""
        <div class="nav-card cat-workflow lp-anim lp-anim-d{i + 2}">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
          <div class="nav-card-cta">Open →</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

# Row 2 — Deep Analysis
st.markdown('<div class="nav-row-label analysis">🔬 Deep Analysis</div>', unsafe_allow_html=True)
_nav_r2 = st.columns(5)
_nav_row2 = [
    ("📋", "Game Report", "Full game breakdowns", "pages/6_📋_Game_Report.py"),
    ("🔮", "Player Simulator", "What-if scenarios", "pages/7_🔮_Player_Simulator.py"),
    ("🗺️", "Correlation Matrix", "Find correlated props", "pages/11_🗺️_Correlation_Matrix.py"),
    ("🛡️", "Risk Shield", "See what to avoid + why", "pages/9_🛡️_Risk_Shield.py"),
    ("🎙️", "The Studio", "Joseph's AI analysis room", "pages/5_🎙️_The_Studio.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row2):
    with _nav_r2[i]:
        st.markdown(f"""
        <div class="nav-card cat-analysis lp-anim lp-anim-d{min(i + 2, 6)}">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
          <div class="nav-card-cta">Open →</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

# Row 3 — Track & Manage
st.markdown('<div class="nav-row-label manage">📊 Track &amp; Manage</div>', unsafe_allow_html=True)
_nav_r3 = st.columns(6)
_nav_row3 = [
    ("💦", "Live Sweat", "Track bets in real-time", "pages/0_💦_Live_Sweat.py"),
    ("📈", "Bet Tracker", "Log results, track ROI", "pages/12_📈_Bet_Tracker.py"),
    ("📊", "Proving Grounds", "Validate model accuracy", "pages/13_📊_Proving_Grounds.py"),
    ("📡", "Smart NBA Data", "Player stats, standings & more", "pages/10_📡_Smart_NBA_Data.py"),
    ("⚙️", "Settings", "Tune engine parameters", "pages/14_⚙️_Settings.py"),
    ("💎", "Premium", "Unlock everything", "pages/15_💎_Subscription_Level.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row3):
    with _nav_r3[i]:
        st.markdown(f"""
        <div class="nav-card cat-manage lp-anim lp-anim-d{min(i + 2, 6)}">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
          <div class="nav-card-cta">Open →</div>
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
        away = _html.escape(str(game.get("away_team", "")))
        home = _html.escape(str(game.get("home_team", "")))
        aw = game.get("away_wins", 0)
        al = game.get("away_losses", 0)
        hw = game.get("home_wins", 0)
        hl = game.get("home_losses", 0)
        rec_a = f" ({aw}-{al})" if aw or al else ""
        rec_h = f" ({hw}-{hl})" if hw or hl else ""

        # Enhanced metadata line — spread, total, game time
        _spread = _html.escape(str(game.get("spread", "") or ""))
        _total = _html.escape(str(game.get("total", "") or ""))
        _game_time = _html.escape(str(game.get("game_time", "") or ""))
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

# ── Full JMS attribution footer (replaces static lp-footer) ─
from utils.components import render_attribution_footer as _render_home_footer
_render_home_footer()

# ============================================================
# END SECTION 10: Footer
# ============================================================
