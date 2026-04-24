"""
etl/scheduler.py
----------------
Lightweight in-process scheduler that keeps the ETL database fresh while
the Streamlit app is running.

**How it works**

* A single daemon thread sleeps in a loop and calls
  ``etl.data_updater.run_update()`` at configurable intervals.
* During the NBA window (roughly 6 PM → 2 AM ET, when games are live)
  the refresh runs every **30 minutes** so bet resolution and live pages
  see recent box scores.
* Outside that window (daytime / early morning) it runs every **4 hours**
  — just enough to catch overnight finalizations and injury updates.
* ``start()`` is safe to call multiple times; only one background thread
  is ever created per process.

**QAM Auto-Analysis**

* Once per day, after the nightly ETL refresh completes, the scheduler
  automatically runs the full Quantum Analysis Matrix over today's live
  props slate and writes the top picks to ``all_analysis_picks`` and
  ``cache/latest_picks.json``.
* Runs only during the analysis window (env ``QAM_ANALYSIS_HOUR_START``
  to ``QAM_ANALYSIS_HOUR_END``, default 17–23 ET) so the cache always
  has that day's picks by game time.
* DraftKings props are excluded to preserve The Odds API budget.

**Environment knobs** (all optional)

``ETL_FAST_INTERVAL_MIN``    — minutes between refreshes during game window  (default 30)
``ETL_SLOW_INTERVAL_MIN``    — minutes between refreshes outside game window (default 240)
``ETL_GAME_WINDOW_START``    — ET hour when fast cadence begins               (default 18)
``ETL_GAME_WINDOW_END``      — ET hour when fast cadence ends                 (default 2)
``ETL_SCHEDULER_DISABLED``   — set to ``1`` to completely disable             (default off)
``QAM_AUTO_ANALYSIS_DISABLED`` — set to ``1`` to skip auto QAM runs          (default off)
``QAM_ANALYSIS_HOUR_START``  — ET hour to begin allowing QAM runs            (default 17)
``QAM_ANALYSIS_HOUR_END``    — ET hour after which QAM runs are skipped      (default 23)
``QAM_SIM_DEPTH``            — Quantum simulation depth for auto runs     (default 1000)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
from datetime import datetime, timezone, timedelta

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Configuration (env-overridable) ───────────────────────────────────────

_FAST_INTERVAL = int(os.environ.get("ETL_FAST_INTERVAL_MIN", "30")) * 60   # seconds
_SLOW_INTERVAL = int(os.environ.get("ETL_SLOW_INTERVAL_MIN", "240")) * 60  # seconds
_GAME_WINDOW_START = int(os.environ.get("ETL_GAME_WINDOW_START", "18"))     # ET hour
_GAME_WINDOW_END = int(os.environ.get("ETL_GAME_WINDOW_END", "2"))         # ET hour
_DISABLED = os.environ.get("ETL_SCHEDULER_DISABLED", "").strip() in ("1", "true", "yes")

# QAM auto-analysis config
_QAM_DISABLED = os.environ.get("QAM_AUTO_ANALYSIS_DISABLED", "").strip() in ("1", "true", "yes")
_QAM_HOUR_START = int(os.environ.get("QAM_ANALYSIS_HOUR_START", "10"))   # 10 AM ET — props often available by 10 AM
_QAM_HOUR_END = int(os.environ.get("QAM_ANALYSIS_HOUR_END", "23"))       # 11 PM ET
_QAM_SIM_DEPTH = int(os.environ.get("QAM_SIM_DEPTH", "1000"))

# DST-aware Eastern Time via zoneinfo (falls back to UTC-4 hardcoded if unavailable).
# Using a fixed offset like UTC-5 would shift QAM/game-window checks by 1 hour during EDT.
try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    def _et_now() -> datetime:
        return datetime.now(_ZoneInfo("America/New_York"))
except Exception:
    _ET_FALLBACK = timezone(timedelta(hours=-4))  # EDT
    def _et_now() -> datetime:
        return datetime.now(_ET_FALLBACK)

# Keep _ET for any legacy references below
_ET = timezone(timedelta(hours=-4))

# ── Singleton guard ───────────────────────────────────────────────────────

_started = False
_lock = threading.Lock()


def _in_game_window() -> bool:
    """Return True if the current ET hour falls inside the NBA game window."""
    et_hour = _et_now().hour
    if _GAME_WINDOW_START < _GAME_WINDOW_END:
        # e.g. 10 AM → 6 PM (unlikely but handled)
        return _GAME_WINDOW_START <= et_hour < _GAME_WINDOW_END
    else:
        # Wraps midnight: e.g. 6 PM → 2 AM  ⇒  hour >= 18 OR hour < 2
        return et_hour >= _GAME_WINDOW_START or et_hour < _GAME_WINDOW_END


_PROP_FAST_INTERVAL = int(os.environ.get("PROP_FAST_INTERVAL_MIN", "15")) * 60   # seconds
_PROP_SLOW_INTERVAL = int(os.environ.get("PROP_SLOW_INTERVAL_MIN", "60")) * 60  # seconds
_ETL_RUN_TIMEOUT = int(os.environ.get("ETL_RUN_TIMEOUT_SEC", "300"))  # wall-clock limit for run_update


def _refresh_props() -> int:
    """Fetch fresh props from FREE platforms (PrizePicks + Underdog) and
    write to ``data/live_props.csv``.  DraftKings is skipped because The
    Odds API has a 500 req/month cap — DK is refreshed only on user demand.

    Returns the number of props written, or 0 on failure.
    """
    try:
        from data.platform_fetcher import fetch_all_platform_props
        from data.data_manager import save_platform_props_to_csv

        props = fetch_all_platform_props(
            include_prizepicks=True,
            include_underdog=True,
            include_draftkings=False,   # Preserve DK API budget
        )
        if props:
            save_platform_props_to_csv(props)
            return len(props)
        return 0
    except Exception:
        _logger.exception("[ETL Scheduler] prop refresh failed")
        return 0


def _run_auto_analysis(today_str: str) -> int:
    """Run the full QAM analysis pipeline over today's live props slate.

    Steps:
      1. Load today's games schedule.
      2. Load today's players on active rosters.
      3. Fetch live props (PrizePicks + Underdog, no DK to preserve budget).
      4. Load supporting data: injuries, defensive ratings, teams.
      5. Call ``analyze_props_batch`` over the full props list.
      6. Write results to ``all_analysis_picks`` via ``insert_analysis_picks``
         (which also auto-updates ``cache/latest_picks.json``).

    Returns:
        Number of picks inserted, or 0 on failure / no props.
    """
    if _QAM_DISABLED:
        _logger.info("[ETL Scheduler] QAM auto-analysis disabled via env var.")
        return 0

    et_hour = _et_now().hour
    if not (_QAM_HOUR_START <= et_hour < _QAM_HOUR_END):
        _logger.debug(
            "[ETL Scheduler] QAM auto-analysis skipped — ET hour %d outside window %d–%d.",
            et_hour, _QAM_HOUR_START, _QAM_HOUR_END,
        )
        return 0

    _logger.info("[ETL Scheduler] Starting QAM auto-analysis for %s …", today_str)
    injury_map = None
    try:
        # ── 1. Load game schedule ──
        from data.nba_data_service import get_todays_games
        todays_games = get_todays_games()
        if not todays_games:
            _logger.info("[ETL Scheduler] QAM auto-analysis: no games today, skipping.")
            return 0

        # ── 2. Load players on today's rosters ──
        from data.nba_data_service import get_todays_players
        from data.data_manager import load_players_data
        players_data = load_players_data()
        players_today = get_todays_players(todays_games)
        # Merge today's active players into the full players list so the
        # engine can find game-context even for players not in the CSV.
        if players_today:
            _existing_names = {p.get("player_name", "").lower() for p in players_data}
            for p in players_today:
                if p.get("player_name", "").lower() not in _existing_names:
                    players_data.append(p)

        # ── 3. Fetch live props ──
        from data.platform_fetcher import fetch_all_platform_props
        from data.data_manager import save_platform_props_to_csv
        props = fetch_all_platform_props(
            include_prizepicks=True,
            include_underdog=True,
            include_draftkings=False,  # preserve DK API budget
        )
        if not props:
            _logger.info("[ETL Scheduler] QAM auto-analysis: no props fetched, skipping.")
            return 0
        save_platform_props_to_csv(props)  # keep CSV fresh too
        _logger.info("[ETL Scheduler] QAM auto-analysis: %d props loaded.", len(props))

        # ── 4. Load supporting data ──
        from data.data_manager import (
            load_defensive_ratings_data,
            load_teams_data,
            load_injury_status,
        )
        defensive_ratings_data = load_defensive_ratings_data()
        teams_data = load_teams_data()
        if not injury_map:
            injury_map = load_injury_status()

        # ── 5. Run analysis ──
        from engine.analysis_orchestrator import analyze_props_batch
        results = analyze_props_batch(
            props,
            players_data=players_data,
            todays_games=todays_games,
            injury_map=injury_map,
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
            simulation_depth=_QAM_SIM_DEPTH,
        )
        if not results:
            _logger.info("[ETL Scheduler] QAM auto-analysis: analysis returned no results.")
            return 0

        # ── 6. Persist picks ──
        from tracking.database import insert_analysis_picks
        inserted = insert_analysis_picks(results)
        _logger.info(
            "[ETL Scheduler] QAM auto-analysis complete — %d picks inserted for %s.",
            inserted, today_str,
        )
        return inserted

    except Exception:
        _logger.exception("[ETL Scheduler] QAM auto-analysis failed (non-fatal)")
        return 0


def _loop() -> None:
    """Infinite loop: sleep → ETL refresh → prop refresh → QAM analysis → repeat."""
    # Initial delay — let the app finish booting before the first refresh.
    # Reduced from 60s to 20s so picks are loaded faster on container start.
    time.sleep(20)

    _last_prop_refresh = 0.0      # monotonic timestamp of last prop refresh
    _last_analysis_date = ""      # ISO date of last successful QAM auto-analysis
    _last_analysis_ts = 0.0       # monotonic timestamp of last successful QAM run
    _ANALYSIS_RERUN_SEC = int(os.environ.get("QAM_RERUN_INTERVAL_MIN", "120")) * 60  # re-run every 2 h (was 4 h)

    while True:
        game_window = _in_game_window()
        interval = _FAST_INTERVAL if game_window else _SLOW_INTERVAL
        today_str = _et_now().strftime("%Y-%m-%d")

        # ── ETL database refresh (game logs, standings, injuries) ──
        # Wrapped in a thread executor so a hung nba_api call cannot block
        # the loop forever and prevent props / QAM from running.
        try:
            from etl.data_updater import run_update
            t0 = time.monotonic()
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="etl-run") as _pool:
                _fut = _pool.submit(run_update)
                try:
                    new_rows = _fut.result(timeout=_ETL_RUN_TIMEOUT)
                except _FutTimeout:
                    new_rows = 0
                    _logger.warning(
                        "[ETL Scheduler] run_update() exceeded %ds wall-clock timeout "
                        "— props + QAM will still run this cycle.",
                        _ETL_RUN_TIMEOUT,
                    )
            elapsed = round(time.monotonic() - t0, 1)
            _logger.info(
                "[ETL Scheduler] refresh done — %d new rows in %.1f s "
                "(next in %d min, game_window=%s)",
                new_rows, elapsed, interval // 60, game_window,
            )
        except Exception:
            _logger.exception("[ETL Scheduler] refresh failed — will retry next cycle")

        # ── Live props refresh (PrizePicks + Underdog only) ────────
        prop_interval = _PROP_FAST_INTERVAL if game_window else _PROP_SLOW_INTERVAL
        since_last_prop = time.monotonic() - _last_prop_refresh
        if since_last_prop >= prop_interval:
            t0 = time.monotonic()
            count = _refresh_props()
            elapsed = round(time.monotonic() - t0, 1)
            _last_prop_refresh = time.monotonic()
            _logger.info(
                "[ETL Scheduler] prop refresh — %d props written in %.1f s "
                "(next prop refresh in %d min)",
                count, elapsed, prop_interval // 60,
            )
            # Bump the shared data-version stamp so running Streamlit sessions
            # detect the fresh props and re-seed their session state from disk.
            if count > 0:
                try:
                    from tracking.database import _bump_data_version as _bv
                    import datetime as _dt_bv
                    _bv(_dt_bv.date.today().isoformat())
                except Exception:
                    pass

        # ── QAM auto-analysis (once per new day, then every 4 h while in window) ──
        # Runs after props are fresh to analyze the live slate.
        # Re-runs every 4 h (configurable via QAM_RERUN_INTERVAL_MIN) so that
        # picks stay current as prop lines shift throughout the day.
        _analysis_stale = (
            _last_analysis_date != today_str
            or (time.monotonic() - _last_analysis_ts >= _ANALYSIS_RERUN_SEC)
        )
        if _analysis_stale:
            t0 = time.monotonic()
            inserted = _run_auto_analysis(today_str)
            if inserted > 0:
                _last_analysis_date = today_str
                _last_analysis_ts = time.monotonic()
                _logger.info(
                    "[ETL Scheduler] QAM auto-analysis: %d picks persisted in %.1f s.",
                    inserted, round(time.monotonic() - t0, 1),
                )

        # ── Drip email sender (slow cycle only — runs ~every 4 hours off-peak) ─
        # Fires scheduled welcome drip emails for new subscribers.
        if not game_window:
            try:
                from utils.notifications import send_pending_drip_emails
                _drip_sent = send_pending_drip_emails()
                if _drip_sent:
                    _logger.info("[ETL Scheduler] Drip emails sent: %d", _drip_sent)
            except Exception:
                _logger.debug("[ETL Scheduler] send_pending_drip_emails skipped", exc_info=True)

        time.sleep(interval)


def start() -> bool:
    """Start the background ETL scheduler (idempotent).

    Returns ``True`` if the thread was started for the first time,
    ``False`` if it was already running or is disabled.
    """
    global _started

    if _DISABLED:
        _logger.info("[ETL Scheduler] disabled via ETL_SCHEDULER_DISABLED env var.")
        return False

    with _lock:
        if _started:
            return False
        _started = True

    t = threading.Thread(target=_loop, name="etl-scheduler", daemon=True)
    t.start()
    _logger.info(
        "[ETL Scheduler] started — fast=%d min (game window %d:00–%d:00 ET), "
        "slow=%d min (outside window), QAM auto-analysis=%s (window %d:00–%d:00 ET, sim_depth=%d)",
        _FAST_INTERVAL // 60, _GAME_WINDOW_START, _GAME_WINDOW_END,
        _SLOW_INTERVAL // 60,
        "disabled" if _QAM_DISABLED else "enabled",
        _QAM_HOUR_START, _QAM_HOUR_END, _QAM_SIM_DEPTH,
    )
    return True
