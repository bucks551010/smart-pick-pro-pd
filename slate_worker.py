"""
slate_worker.py
===============
Standalone background worker — NO Streamlit dependency.

Purpose
-------
Runs the full "Tonight's Slate" ingestion and analysis pipeline,
then writes the results directly to the database so the Streamlit UI
can read pre-computed picks instantly on login without blocking.

Pipeline phases
---------------
1. Load environment (.env, Railway DATABASE_URL)
2. Initialize the database schema (idempotent)
3. Fetch today's games & active rosters
4. Fetch live props from PrizePicks + Underdog (DK skipped to save budget)
5. Run analyze_props_batch() — Quantum + ML ensemble
6. Persist picks to ``all_analysis_picks`` via insert_analysis_picks()
7. Write a summary record to ``slate_cache`` (for staleness checks)
8. Persist props to ``data/live_props.csv`` (so the CSV path also stays fresh)

Usage
-----
    python slate_worker.py                  # run once, exit 0 on success
    python slate_worker.py --dry-run        # analyse but do NOT write to DB
    python -m slate_worker                  # same as above

Environment variables
---------------------
    DATABASE_URL          PostgreSQL URL (auto-set by Railway).  If absent,
                          falls back to local SQLite at db/smartai_nba.db.
    ODDS_API_KEY          Optional — enriches props with The Odds API lines.
    QAM_SIM_DEPTH         Quantum depth (default 1000).
    DB_DIR                Override SQLite directory (default: db/).
    SLATE_WORKER_LOG      Log level for this script (default INFO).
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

# ── Load .env early so DATABASE_URL + ODDS_API_KEY are available ─────────
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_file = Path(__file__).resolve().parent / ".env"
    if _env_file.exists():
        _load_dotenv(_env_file)
except ImportError:
    pass  # dotenv optional — Railway sets env vars directly

# ── Logging setup ─────────────────────────────────────────────────────────
_LOG_LEVEL = os.environ.get("SLATE_WORKER_LOG", "INFO").upper()
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger("slate_worker")

# ── ET-anchored date helper ───────────────────────────────────────────────
def _et_today() -> str:
    """Return the current NBA 'sports day' in Eastern Time as YYYY-MM-DD.

    The sports day boundary is 4:00 AM ET (not midnight).  Between
    12:00 AM and 3:59 AM ET the date is still the *previous* calendar
    day, so West-Coast games finishing at 1–2 AM ET are attributed to
    the correct slate date.
    """
    try:
        from zoneinfo import ZoneInfo
        now_et = datetime.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Fallback: UTC-4 (EDT)
        now_et = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))
    # Sports day rolls over at 4 AM ET, not midnight
    if now_et.hour < 4:
        now_et = now_et - datetime.timedelta(days=1)
    return now_et.date().isoformat()


# ── Simulation depth ──────────────────────────────────────────────────────
_SIM_DEPTH = int(os.environ.get("QAM_SIM_DEPTH", "1000"))


def run_slate(dry_run: bool = False) -> int:
    """Execute the full slate pipeline.

    Args:
        dry_run: If True, skip all DB/file writes (analysis only).

    Returns:
        Number of picks persisted (or analysed in dry-run mode).
    """
    start_ts = time.perf_counter()
    today_str = _et_today()
    _logger.info("=== slate_worker START  date=%s  dry_run=%s ===", today_str, dry_run)

    # ── Step 0: DB init ───────────────────────────────────────────────────
    try:
        from tracking.database import initialize_database, record_slate_run
        initialize_database()
        _logger.info("[0] Database schema verified.")
    except Exception as exc:
        _logger.error("[0] DB init failed: %s", exc)
        return 0

    # ── Step 0b: Pre-warm cache from existing DB picks ────────────────────
    # Write whatever picks already exist in the DB to slate_cache.json right
    # away — before the full analysis runs.  This means users who visit the
    # app during the ~5-minute analysis window see yesterday/previous picks
    # instantly instead of a "preparing" spinner.
    if not dry_run:
        try:
            from tracking.database import get_slate_picks_for_today as _gsp
            _existing = _gsp()
            if _existing:
                import json as _json_pre
                _cache_dir = Path(__file__).resolve().parent / "cache"
                _cache_dir.mkdir(parents=True, exist_ok=True)
                (_cache_dir / "slate_cache.json").write_text(
                    _json_pre.dumps(
                        {
                            "date": today_str,
                            "written_at": datetime.datetime.utcnow().isoformat() + "Z",
                            "picks": _existing,
                            "_prewarm": True,
                        },
                        default=str,
                    ),
                    encoding="utf-8",
                )
                _logger.info("[0b] Pre-warmed slate_cache.json with %d existing picks.", len(_existing))
        except Exception as _pw_exc:
            _logger.debug("[0b] Pre-warm skipped (non-fatal): %s", _pw_exc)

    games: list = []
    props: list = []
    results: list = []
    error_msg: str | None = None

    try:
        # ── Step 1: Today's games ─────────────────────────────────────────
        _logger.info("[1] Fetching today's games…")
        from data.nba_data_service import get_todays_games, get_todays_players
        from data.data_manager import load_players_data, load_injury_status

        games = get_todays_games() or []
        if not games:
            _logger.warning(
                "[1] get_todays_games() returned empty for %s — continuing without game "
                "context (props will still be fetched and analysed).", today_str
            )
        _logger.info("[1] %d games today.", len(games))

        # ── Step 2: Active rosters + injury map ──────────────────────────
        _logger.info("[2] Loading rosters + injury map…")
        players_today = get_todays_players(games)
        # get_todays_players should return a list; guard against bool in case
        # the live fetcher path returns True/False instead of a player list.
        if isinstance(players_today, bool):
            _logger.warning("[2] get_todays_players returned bool (%s) — treating as empty list.", players_today)
            players_today = []
        players_data = load_players_data()
        # Merge game-day players so the engine finds all roster context.
        if players_today:
            _existing = {p.get("player_name", "").lower() for p in players_data}
            for p in players_today:
                if p.get("player_name", "").lower() not in _existing:
                    players_data.append(p)
        injury_map = load_injury_status() or {}
        _logger.info("[2] %d players loaded, %d injury entries.", len(players_data), len(injury_map))

        # ── Step 3: Fetch live props ──────────────────────────────────────
        _logger.info("[3] Fetching live props (PrizePicks + Underdog)…")
        from data.platform_fetcher import fetch_all_platform_props
        from data.data_manager import save_platform_props_to_csv, load_defensive_ratings_data, load_teams_data

        props = fetch_all_platform_props(
            include_prizepicks=True,
            include_underdog=True,
            include_draftkings=False,  # preserve API budget
        ) or []

        if not props:
            # Fall back to the cached CSV if the live API returned nothing.
            _logger.warning("[3] Live props API returned empty — trying live_props.csv fallback.")
            try:
                import pandas as _pd
                from pathlib import Path as _Path
                _csv_path = _Path(__file__).resolve().parent / "data" / "live_props.csv"
                if _csv_path.exists():
                    _df = _pd.read_csv(_csv_path)
                    if "game_date" in _df.columns:
                        _today_rows = _df[_df["game_date"] == today_str]
                        if not _today_rows.empty:
                            props = _today_rows.to_dict("records")
                            _logger.info("[3] CSV fallback: %d props loaded from live_props.csv.", len(props))
            except Exception as _csv_exc:
                _logger.debug("[3] CSV fallback failed (non-fatal): %s", _csv_exc)

        if not props:
            _logger.warning("[3] No props available (live API + CSV fallback) — exiting.")
            if not dry_run:
                record_slate_run(
                    for_date=today_str,
                    pick_count=0,
                    props_fetched=0,
                    games_count=len(games),
                    status="no_props",
                    duration_seconds=time.perf_counter() - start_ts,
                )
            return 0
        _logger.info("[3] %d props fetched.", len(props))

        # ── Step 3b: Filter props to tonight's playing teams only ────────
        # The prop platforms (PrizePicks, Underdog) list props for ALL
        # upcoming games this week, not just tonight's.  Without this filter,
        # the analysis engine processes props for teams not playing tonight
        # (e.g. POR, TOR, HOU), producing picks with empty opponents that
        # contaminate the QAM display and the DB.
        if games:
            _tonight_teams: set[str] = set()
            for _g in games:
                _t1 = str(_g.get("home_team", "") or "").upper().strip()
                _t2 = str(_g.get("away_team", "") or "").upper().strip()
                if _t1:
                    _tonight_teams.add(_t1)
                if _t2:
                    _tonight_teams.add(_t2)
            if _tonight_teams:
                _props_before = len(props)
                props = [
                    p for p in props
                    if str(p.get("team", "") or "").upper().strip() in _tonight_teams
                ]
                _logger.info(
                    "[3b] Filtered to tonight's teams %s: %d → %d props.",
                    sorted(_tonight_teams), _props_before, len(props),
                )

        # Write props CSV fresh so Prop Scanner page stays current.
        if not dry_run:
            try:
                save_platform_props_to_csv(props)
                _logger.info("[3] Props CSV updated.")
            except Exception as exc:
                _logger.warning("[3] Props CSV write failed (non-fatal): %s", exc)

        # ── Step 4: Supporting data ───────────────────────────────────────
        _logger.info("[4] Loading defensive ratings + teams…")
        defensive_ratings_data = load_defensive_ratings_data()
        teams_data = load_teams_data()

        # ── Step 5: Run analysis ──────────────────────────────────────────
        _logger.info("[5] Running analyze_props_batch (sim_depth=%d)…", _SIM_DEPTH)
        from engine.analysis_orchestrator import analyze_props_batch

        results = analyze_props_batch(
            props,
            players_data=players_data,
            todays_games=games,
            injury_map=injury_map,
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
            simulation_depth=_SIM_DEPTH,
        ) or []
        _logger.info("[5] Analysis complete — %d picks generated.", len(results))

    except Exception as exc:
        error_msg = str(exc)
        _logger.exception("[!] Pipeline error: %s", exc)

    # ── Step 6: Persist picks ─────────────────────────────────────────────
    # Extra guard: only persist results for players with a known game opponent.
    # This catches any non-playing-team props or synthetic game-total entries
    # that slipped through the step-3b team filter (e.g. props with no team
    # field set in the platform data).
    if results and games:
        _results_before = len(results)
        results = [r for r in results if r.get("opponent", "")]
        if len(results) < _results_before:
            _logger.info(
                "[6] Dropped %d no-opponent results (non-playing-team / synthetic). Keeping %d.",
                _results_before - len(results), len(results),
            )

    inserted = 0
    if results and not dry_run:
        try:
            from tracking.database import insert_analysis_picks
            inserted = insert_analysis_picks(results)
            _logger.info("[6] %d picks written to all_analysis_picks.", inserted)
        except Exception as exc:
            error_msg = error_msg or str(exc)
            _logger.error("[6] insert_analysis_picks failed: %s", exc)
        # Phase 4 — Cache Warming: write all picks to a JSON file so the first
        # Streamlit user after this run gets a file read instead of a DB query.
        if inserted > 0:
            try:
                import json as _json
                _cache_dir = Path(__file__).resolve().parent / "cache"
                _cache_dir.mkdir(parents=True, exist_ok=True)
                (_cache_dir / "slate_cache.json").write_text(
                    _json.dumps(
                        {
                            "date": today_str,
                            "written_at": datetime.datetime.utcnow().isoformat() + "Z",
                            "picks": results,
                        },
                        default=str,
                    ),
                    encoding="utf-8",
                )
                _logger.info("[6b] slate_cache.json warmed (%d picks).", inserted)
            except Exception as exc:
                _logger.debug("[6b] Cache file warm failed (non-fatal): %s", exc)
            # Bump data_version so all running Streamlit sessions (home page
            # 60-second poller) detect the fresh slate and auto-refresh.
            try:
                from tracking.database import _bump_data_version as _slw_bump
                _slw_bump(today_str)
                _logger.info("[6c] data_version bumped — running sessions will refresh.")
            except Exception as exc:
                _logger.debug("[6c] _bump_data_version failed (non-fatal): %s", exc)
        # Step 6d: Persist the full analysis session to DB so the web
        # container (separate filesystem) can load todays_games and
        # top picks without needing the local slate_cache.json file.
        # Runs whenever results exist — NOT gated on inserted > 0 — so that
        # runs where all picks are UPDATEs (already in DB) still push a fresh
        # session, preventing stale session 42-style hangovers.
        try:
            from tracking.database import save_analysis_session as _save_session
            # Include Platinum, Gold, and Silver picks in selected_picks so the
            # QAM and home page have a meaningful set of top picks to display.
            # Also require a non-empty opponent to exclude synthetic game-total
            # props (e.g. "DET @ ORL Total") and players from non-playing teams
            # that may have slipped through the props filter.
            _top_picks = [
                r for r in results
                if r.get("tier", "").lower() in ("platinum", "gold", "silver")
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
                and r.get("opponent", "")  # must have a valid game opponent
            ][:50]
            _session_id = _save_session(
                results, todays_games=games, selected_picks=_top_picks
            )
            _logger.info(
                "[6d] Analysis session saved (id=%s) — %d games, %d top picks.",
                _session_id, len(games), len(_top_picks),
            )
        except Exception as exc:
            _logger.debug("[6d] save_analysis_session failed (non-fatal): %s", exc)
    elif dry_run:
        inserted = len(results)
        _logger.info("[6] DRY RUN — would persist %d picks (no write).", inserted)

    # ── Step 7: Record run metadata ───────────────────────────────────────
    duration = time.perf_counter() - start_ts
    if not dry_run:
        try:
            record_slate_run(
                for_date=today_str,
                pick_count=inserted,
                props_fetched=len(props),
                games_count=len(games),
                status="ok" if not error_msg else "partial",
                error_message=error_msg,
                duration_seconds=duration,
            )
        except Exception as exc:
            _logger.warning("[7] record_slate_run failed (non-fatal): %s", exc)

    _logger.info(
        "=== slate_worker END  picks=%d  props=%d  games=%d  elapsed=%.1fs ===",
        inserted, len(props), len(games), duration,
    )
    return inserted


def _daemon_loop(dry_run: bool, interval_minutes: int) -> None:
    """Multi-job scheduler — replaces the legacy fixed-interval loop.

    Jobs (all ET-anchored, scheduled per "sports day"):
      • props_refresh   every  30 min (fetch props + analyze + persist picks)
      • etl_refresh     daily at 06:00 ET (advanced metrics + defensive ratings)
      • bet_logging     2h before first tip (qeg + smart_money + platform_ai + quantum)
      • auto_resolve    every 30 min during/after game window
                        + final sweep at 02:00 ET
      • nightly_sweep   02:30 ET (postponements + retry-cleanup + props_cache cleanup
                                  + daily snapshot)

    Catch-up: on startup, each job's worker_state is read; jobs whose last
    successful run is older than its interval (or whose target time today
    has already passed) run immediately.

    `interval_minutes` only controls the polling tick; individual jobs
    have their own schedules.
    """
    import signal as _signal

    _shutdown = threading.Event()

    def _handle_signal(signum, frame):  # noqa: ANN001
        _logger.info("Received signal %s — daemon shutting down cleanly.", signum)
        _shutdown.set()

    _signal.signal(_signal.SIGTERM, _handle_signal)
    try:
        _signal.signal(_signal.SIGINT, _handle_signal)
    except (ValueError, OSError):
        # SIGINT isn't always available in containerised threads.
        pass

    _logger.info(
        "=== slate_worker DAEMON v2  tick=%dm  dry_run=%s ===",
        interval_minutes, dry_run,
    )

    poll_sec = max(60, interval_minutes * 60)
    while not _shutdown.is_set():
        loop_start = time.monotonic()
        try:
            _run_due_jobs(dry_run=dry_run)
        except Exception as exc:
            _logger.error("Scheduler tick failed: %s", exc, exc_info=True)

        elapsed = time.monotonic() - loop_start
        wait_sec = max(0.0, poll_sec - elapsed)
        deadline = time.monotonic() + wait_sec
        _logger.debug("Next scheduler tick in %.0f s.", wait_sec)
        while not _shutdown.is_set() and time.monotonic() < deadline:
            time.sleep(min(5.0, deadline - time.monotonic()))

    _logger.info("=== slate_worker DAEMON exited cleanly. ===")


# =================================================================
# Multi-Job Scheduler
# =================================================================

def _now_et() -> datetime.datetime:
    """Return current Eastern Time as a tz-aware datetime."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))


def _parse_iso(ts: str | None) -> datetime.datetime | None:
    if not ts:
        return None
    try:
        # Strip trailing Z and parse as UTC.
        s = ts.rstrip("Z")
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def _job_due(
    job_name: str,
    *,
    interval_min: int | None = None,
    daily_at_hour: int | None = None,
    daily_at_minute: int = 0,
) -> bool:
    """Decide whether a job should run now.

    interval_min:  run if last_run_at older than `interval_min` minutes.
    daily_at_hour: run if today's scheduled time (ET) has passed and we
                   haven't run since.
    """
    try:
        from tracking.database import get_worker_state
        rows = get_worker_state(job_name)
    except Exception:
        rows = []
    last_run = _parse_iso(rows[0]["last_run_at"]) if rows else None

    now_et = _now_et()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    if interval_min is not None:
        if last_run is None:
            return True
        delta_min = (now_utc - last_run).total_seconds() / 60.0
        return delta_min >= interval_min

    if daily_at_hour is not None:
        target_et = now_et.replace(
            hour=daily_at_hour, minute=daily_at_minute, second=0, microsecond=0
        )
        if now_et < target_et:
            return False  # Not yet time today.
        if last_run is None:
            return True
        last_run_et = last_run.astimezone(now_et.tzinfo)
        return last_run_et < target_et

    return False


def _first_tip_et_today() -> datetime.datetime | None:
    """Earliest scheduled tip-off for the current sports day, in ET.

    Returns None if no games scheduled or the schedule cannot be read.
    """
    try:
        from data.nba_data_service import get_todays_games
        games = get_todays_games() or []
    except Exception as exc:
        _logger.debug("first_tip lookup failed: %s", exc)
        return None
    if not games:
        return None
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
    except Exception:
        et = datetime.timezone(datetime.timedelta(hours=-4))
    earliest: datetime.datetime | None = None
    for g in games:
        ts = g.get("game_time_et") or g.get("start_time") or g.get("tip_off") or g.get("game_time")
        dt = _parse_iso(ts) if isinstance(ts, str) else None
        if dt is None:
            continue
        dt = dt.astimezone(et)
        if earliest is None or dt < earliest:
            earliest = dt
    return earliest


def _run_job(name: str, fn, *, dry_run: bool = False) -> None:
    """Wrap a job call with worker_state stamping."""
    if dry_run:
        _logger.info("[scheduler] DRY-RUN — would run job %s", name)
        return
    _logger.info("[scheduler] >>> %s", name)
    try:
        fn()
        try:
            from tracking.database import update_worker_state
            update_worker_state(name, status="ok")
        except Exception:
            pass
        _logger.info("[scheduler] <<< %s ok", name)
    except Exception as exc:
        _logger.exception("[scheduler] %s failed: %s", name, exc)
        try:
            from tracking.database import update_worker_state
            update_worker_state(name, status="error", error=str(exc)[:500])
        except Exception:
            pass


def _job_props_refresh() -> None:
    run_slate(dry_run=False)


def _job_etl_refresh() -> None:
    """Daily ETL refresh — defensive ratings, advanced metrics."""
    try:
        from etl.scheduler import run_daily_etl  # type: ignore
        run_daily_etl()
    except ImportError:
        # Fallback to whatever ETL entrypoint exists.
        try:
            from etl.scheduler import main as _etl_main  # type: ignore
            _etl_main()
        except Exception as exc:
            _logger.warning("ETL entrypoint not found, skipping: %s", exc)


def _job_bet_logging() -> None:
    """Auto-log all 4 bet sources from today's analysis_picks."""
    from tracking.database import _db_read
    from tracking.bet_tracker import (
        auto_log_analysis_bets,
        auto_log_qeg_bets,
        auto_log_smart_money_bets,
        auto_log_platform_ai_bets,
    )
    today = _et_today()
    rows = _db_read(
        "SELECT * FROM all_analysis_picks WHERE pick_date = ?", (today,)
    ) or []
    if not rows:
        _logger.warning("[bet_logging] no picks in all_analysis_picks for %s", today)
        return
    picks = [dict(r) for r in rows]
    n_qam = auto_log_analysis_bets(picks, source="quantum")
    n_qeg = auto_log_qeg_bets(picks)
    n_sm = auto_log_smart_money_bets(picks)
    n_pa = auto_log_platform_ai_bets(picks)
    _logger.info(
        "[bet_logging] quantum=%d qeg=%d smart_money=%d platform_ai=%d",
        n_qam, n_qeg, n_sm, n_pa,
    )


def _job_auto_resolve() -> None:
    """Resolve finished games' bets with full CLV/distance tracking."""
    try:
        from tracking.bet_tracker import auto_resolve_bet_results
        n = auto_resolve_bet_results()
        _logger.info("[auto_resolve] resolved=%s", n)
    except Exception as exc:
        _logger.error("[auto_resolve] failed: %s", exc)


def _job_nightly_sweep() -> None:
    """Postponements + retry cleanup + props_cache cleanup + snapshot."""
    from tracking.bet_tracker import (
        detect_and_void_postponed_games,
        cleanup_unresolved_bets,
    )
    voided, postponed = detect_and_void_postponed_games()
    _logger.info("[sweep] postponements: voided=%d games=%s", voided, postponed)

    deleted = cleanup_unresolved_bets()
    _logger.info("[sweep] retry-cleanup deleted=%d", deleted)

    try:
        from tracking.database import cleanup_props_cache
        cleanup_props_cache(30)
    except Exception as exc:
        _logger.warning("[sweep] cleanup_props_cache failed: %s", exc)

    try:
        from tracking.database import save_daily_snapshot
        save_daily_snapshot()
    except Exception as exc:
        _logger.warning("[sweep] save_daily_snapshot failed: %s", exc)


def _run_due_jobs(*, dry_run: bool = False) -> None:
    """One scheduler tick — runs any job whose schedule is due.

    Order matters: ETL before bet_logging, bet_logging before auto_resolve.
    """
    # 1. ETL refresh — daily at 06:00 ET.
    if _job_due("etl_refresh", daily_at_hour=6, daily_at_minute=0):
        _run_job("etl_refresh", _job_etl_refresh, dry_run=dry_run)

    # 2. Props refresh + analysis — every 30 min.
    if _job_due("props_refresh", interval_min=30):
        _run_job("props_refresh", _job_props_refresh, dry_run=dry_run)

    # 3. Bet logging — fires once per day, 2h before first tip.
    first_tip = _first_tip_et_today()
    if first_tip is not None:
        log_target = first_tip - datetime.timedelta(hours=2)
        now_et = _now_et()
        if now_et >= log_target:
            # Run if we haven't run yet today.
            if _job_due("bet_logging", daily_at_hour=log_target.hour, daily_at_minute=log_target.minute):
                _run_job("bet_logging", _job_bet_logging, dry_run=dry_run)

    # 4. Auto-resolve — every 30 min.
    if _job_due("auto_resolve", interval_min=30):
        _run_job("auto_resolve", _job_auto_resolve, dry_run=dry_run)

    # 5. Nightly sweep — daily at 02:30 ET.
    if _job_due("nightly_sweep", daily_at_hour=2, daily_at_minute=30):
        _run_job("nightly_sweep", _job_nightly_sweep, dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Pick Pro — slate background worker")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis but skip all database and file writes.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help=(
            "Run continuously, repeating the pipeline on a fixed schedule. "
            "Useful as a Railway background-service alternative to GitHub Actions cron."
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("SLATE_WORKER_INTERVAL_MIN", "30")),
        metavar="MIN",
        help="Minutes between pipeline runs in daemon mode (default 30, or $SLATE_WORKER_INTERVAL_MIN).",
    )
    args = parser.parse_args()

    if args.daemon:
        _daemon_loop(dry_run=args.dry_run, interval_minutes=args.interval)
    else:
        picks = run_slate(dry_run=args.dry_run)
        sys.exit(0 if picks >= 0 else 1)


if __name__ == "__main__":
    main()
