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
# QAM_ANALYSIS_HOUR_END is now DYNAMIC — see _get_games_cutoff_hour() below.
# Hardcoded fallback (used only if schedule cannot be fetched): 18 ET (6 PM).
_QAM_HOUR_END_FALLBACK = int(os.environ.get("QAM_ANALYSIS_HOUR_END", "18"))
_QAM_SIM_DEPTH = int(os.environ.get("QAM_SIM_DEPTH", "1000"))

# End-of-night cleanup config
# Runs once per calendar day during 2 AM–8 AM ET, after the last games finish.
# Resolves pending bets/picks for the completed sports day, clears the slate
# cache, and bumps data_version so running Streamlit sessions reset to a clean
# slate awaiting the next day's props and analysis.
_EON_DISABLED     = os.environ.get("EON_CLEANUP_DISABLED", "").strip() in ("1", "true", "yes")
_EON_WINDOW_START = int(os.environ.get("EON_WINDOW_START", "2"))   # 2 AM ET
_EON_WINDOW_END   = int(os.environ.get("EON_WINDOW_END",   "8"))   # 8 AM ET

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


def _et_sports_day() -> str:
    """Return the current NBA sports day as YYYY-MM-DD (4 AM ET boundary).

    Between midnight and 3:59 AM ET the sports day is still the *previous*
    calendar date — West-Coast games finishing at 1–2 AM ET belong to the
    slate that started the previous evening.
    """
    now = _et_now()
    if now.hour < 4:
        now = now - timedelta(hours=now.hour + 1)  # step back past midnight
    return now.strftime("%Y-%m-%d")


def _run_end_of_night_cleanup(sports_date: str) -> dict:
    """Resolve last night's bets/picks and reset the slate cache.

    Called automatically once per calendar day during the post-game
    cleanup window (2 AM – 8 AM ET):

    1. ``auto_resolve_bet_results(sports_date)``
       — Grades every pending row in the ``bets`` table for that night.
    2. ``resolve_all_analysis_picks(sports_date, include_today=True)``
       — Grades every pending row in ``all_analysis_picks`` for that night.
    3. Deletes ``cache/slate_cache.json`` and ``cache/latest_picks.json``
       — The next page load returns an empty slate ("awaiting next day").
    4. ``_bump_data_version`` — notifies all running Streamlit sessions to
       clear their session-state caches and reload from scratch.

    Args:
        sports_date: ISO date "YYYY-MM-DD" of the completed NBA sports day.

    Returns:
        Summary dict: ``{"bets_resolved": int, "picks_resolved": int, "errors": list}``.
    """
    summary: dict = {"bets_resolved": 0, "picks_resolved": 0, "errors": []}
    _logger.info("[EON] Starting end-of-night cleanup for sports date %s", sports_date)

    # 1. Resolve bets table
    try:
        from tracking.bet_tracker import auto_resolve_bet_results
        resolved, errors = auto_resolve_bet_results(date_str=sports_date)
        summary["bets_resolved"] = resolved
        if errors:
            summary["errors"].extend(errors[:10])  # cap noisy error lists
        _logger.info("[EON] Bets resolved: %d  (errors: %d)", resolved, len(errors))
    except Exception:
        _logger.exception("[EON] auto_resolve_bet_results failed (non-fatal)")
        summary["errors"].append("auto_resolve_bet_results raised an exception")

    # 2. Resolve analysis picks table
    try:
        from tracking.bet_tracker import resolve_all_analysis_picks
        result = resolve_all_analysis_picks(date_str=sports_date, include_today=True)
        summary["picks_resolved"] = result.get("resolved", 0)
        summary["errors"].extend(result.get("errors", [])[:10])
        _logger.info(
            "[EON] Analysis picks resolved: %d  (W:%d  L:%d  P:%d)",
            result.get("resolved", 0),
            result.get("wins", 0),
            result.get("losses", 0),
            result.get("evens", 0),
        )
    except Exception:
        _logger.exception("[EON] resolve_all_analysis_picks failed (non-fatal)")
        summary["errors"].append("resolve_all_analysis_picks raised an exception")

    # 3. Clear slate cache files so app shows a clean "awaiting next day" state
    try:
        import json as _json
        from pathlib import Path as _Path
        _cache_dir = _Path(__file__).resolve().parent.parent / "cache"
        for _fname in ("slate_cache.json", "latest_picks.json"):
            _f = _cache_dir / _fname
            if _f.exists():
                _f.unlink()
                _logger.info("[EON] Deleted %s", _fname)
        # Write an explicit "no picks" marker so _load_cached_slate returns []
        # and the date guard treats this as a stale slate from yesterday.
        _marker = {
            "date": sports_date,          # yesterday's date → stale tomorrow
            "written_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "picks": [],
            "_eon_cleared": True,
        }
        (_cache_dir / "slate_cache.json").write_text(
            _json.dumps(_marker, indent=2), encoding="utf-8"
        )
        _logger.info("[EON] Wrote empty slate_cache.json (date=%s)", sports_date)
    except Exception as exc:
        summary["errors"].append(f"cache_clear: {exc}")
        _logger.warning("[EON] Cache clear failed (non-fatal): %s", exc)

    # 4. Bump data_version so every running Streamlit session detects the change
    try:
        from tracking.database import _bump_data_version
        _bump_data_version(sports_date + "_eon")
        _logger.info("[EON] Bumped data_version — Streamlit sessions will rerun.")
    except Exception as exc:
        summary["errors"].append(f"bump_data_version: {exc}")
        _logger.warning("[EON] _bump_data_version failed (non-fatal): %s", exc)

    # 5. Prune prior-day analysis_sessions from DB so load_latest_analysis_session
    #    never returns a stale session after EON cleanup runs.
    try:
        from tracking.database import _db_write, _nba_today_iso as _eon_today
        _today_iso = _eon_today()
        _db_write(
            "DELETE FROM analysis_sessions WHERE analysis_timestamp < ?",
            (_today_iso,),
            caller="eon_prune_analysis_sessions",
        )
        _logger.info("[EON] Pruned prior-day analysis_sessions (before %s)", _today_iso)
    except Exception as exc:
        summary["errors"].append(f"prune_analysis_sessions: {exc}")
        _logger.warning("[EON] analysis_sessions prune failed (non-fatal): %s", exc)

    _logger.info(
        "[EON] Cleanup complete — bets=%d  picks=%d  errors=%d",
        summary["bets_resolved"], summary["picks_resolved"], len(summary["errors"]),
    )
    return summary


_PROP_FAST_INTERVAL = int(os.environ.get("PROP_FAST_INTERVAL_MIN", "15")) * 60   # seconds
_PROP_SLOW_INTERVAL = int(os.environ.get("PROP_SLOW_INTERVAL_MIN", "60")) * 60  # seconds
_ETL_RUN_TIMEOUT = int(os.environ.get("ETL_RUN_TIMEOUT_SEC", "300"))  # wall-clock limit for run_update


_games_cutoff_cache: dict = {}  # {date_str: cutoff_hour_int}


def _get_games_cutoff_hour() -> int:
    """Return the ET hour 1 hour before tonight's earliest NBA game tip-off.

    Looks up today's schedule via ``get_todays_games()``, parses each
    ``game_time_et`` field (e.g. ``"7:30 PM ET"``), and returns
    ``earliest_tip_off_hour - 1``.  Result is cached per sports-day so the
    live schedule is only queried once per day.

    Falls back to ``_QAM_HOUR_END_FALLBACK`` (default 18 / 6 PM ET) when:
    - No games are scheduled today.
    - All ``game_time_et`` strings fail to parse.
    - The schedule fetch raises an exception.

    Override at any time by setting ``QAM_ANALYSIS_HOUR_END`` env var — that
    forces this function to return that fixed value instead.
    """
    # Hard override: if the operator set QAM_ANALYSIS_HOUR_END explicitly,
    # honour it and skip the dynamic lookup.
    if os.environ.get("QAM_ANALYSIS_HOUR_END"):
        return _QAM_HOUR_END_FALLBACK

    today = _et_sports_day()
    if today in _games_cutoff_cache:
        return _games_cutoff_cache[today]

    try:
        from data.nba_data_service import get_todays_games
        games = get_todays_games()
        earliest_hour = None
        for g in games:
            raw = g.get("game_time_et", "")
            if not raw:
                continue
            try:
                # Strip trailing " ET" and parse "7:30 PM" or "10:00 PM" etc.
                clean = raw.replace(" ET", "").strip()
                import datetime as _dt
                for fmt in ("%I:%M %p", "%I %p"):
                    try:
                        t = _dt.datetime.strptime(clean, fmt)
                        h = t.hour  # 24-h
                        if earliest_hour is None or h < earliest_hour:
                            earliest_hour = h
                        break
                    except ValueError:
                        continue
            except Exception:
                continue
        if earliest_hour is not None:
            cutoff = max(earliest_hour - 1, _QAM_HOUR_START + 1)  # never cut off before start+1h
            _logger.info(
                "[Scheduler] Earliest game ET hour=%d  →  cutoff=%d ET "
                "(QAM + props stop %d h before tip-off)",
                earliest_hour, cutoff, earliest_hour - cutoff,
            )
        else:
            cutoff = _QAM_HOUR_END_FALLBACK
            _logger.info(
                "[Scheduler] No parseable game times found — using fallback cutoff=%d ET",
                cutoff,
            )
    except Exception:
        cutoff = _QAM_HOUR_END_FALLBACK
        _logger.warning(
            "[Scheduler] _get_games_cutoff_hour() failed — using fallback cutoff=%d ET",
            cutoff,
        )

    _games_cutoff_cache[today] = cutoff
    return cutoff


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


def _run_auto_analysis(today_str: str, force: bool = False) -> int:
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
    _qam_cutoff = _get_games_cutoff_hour()
    if not force and not (_QAM_HOUR_START <= et_hour < _qam_cutoff):
        _logger.debug(
            "[ETL Scheduler] QAM auto-analysis skipped — ET hour %d outside window %d–%d.",
            et_hour, _QAM_HOUR_START, _qam_cutoff,
        )
        return 0
    if force:
        _logger.info(
            "[ETL Scheduler] QAM auto-analysis FORCED (startup/new-day) — bypassing hour window."
        )

    _logger.info("[ETL Scheduler] Starting QAM auto-analysis for %s …", today_str)
    injury_map = None
    try:
        # ── 1. Load game schedule ──
        from data.nba_data_service import get_todays_games
        todays_games = get_todays_games()
        if not todays_games:
            _logger.warning(
                "[ETL Scheduler] QAM auto-analysis: get_todays_games() returned empty — "
                "proceeding without game context (props will still be analysed)."
            )

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
    _last_cleanup_date = ""       # calendar date of last end-of-night cleanup run
    _first_loop = True            # forces QAM to run once on startup regardless of hour

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
        # Stop refreshing once the games-start cutoff hour is reached so picks and
        # bets shown to users remain consistent throughout the game window.
        prop_interval = _PROP_FAST_INTERVAL if game_window else _PROP_SLOW_INTERVAL
        since_last_prop = time.monotonic() - _last_prop_refresh
        _past_prop_cutoff = _et_now().hour >= _get_games_cutoff_hour()
        if since_last_prop >= prop_interval and not _past_prop_cutoff:
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

        # ── QAM auto-analysis (once per new day, then every 2 h while in window) ──
        # Runs after props are fresh to analyze the live slate.
        # On first loop after startup, bypasses the hour-window check so the app
        # always has picks immediately after a deploy — even if deployed outside
        # the normal 10AM–11PM ET analysis window.
        _analysis_stale = (
            _last_analysis_date != today_str
            or (time.monotonic() - _last_analysis_ts >= _ANALYSIS_RERUN_SEC)
        )
        if _analysis_stale or _first_loop:
            _force = _first_loop or (_last_analysis_date != today_str)
            _first_loop = False
            t0 = time.monotonic()
            inserted = _run_auto_analysis(today_str, force=_force)
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

        # ── End-of-night cleanup (once per calendar day, 2 AM–8 AM ET) ───
        # After the last games finish (~2 AM ET), resolve all pending bets
        # and analysis picks for the completed sports day, wipe the slate
        # cache, and bump data_version so every active Streamlit session
        # resets to a clean state awaiting the next day's data.
        if not _EON_DISABLED:
            et_hour = _et_now().hour
            _in_eon_window = _EON_WINDOW_START <= et_hour < _EON_WINDOW_END
            if _in_eon_window and _last_cleanup_date != today_str:
                sports_date = _et_sports_day()  # 4 AM boundary → yesterday's slate
                _logger.info(
                    "[EON] Post-game cleanup window detected "
                    "(ET hour=%d, sports_date=%s) — starting cleanup.",
                    et_hour, sports_date,
                )
                _run_end_of_night_cleanup(sports_date)
                _last_cleanup_date = today_str   # mark done for this calendar day

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
