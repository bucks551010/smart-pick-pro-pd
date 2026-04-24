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
            _logger.warning("[1] No NBA games scheduled for %s — exiting.", today_str)
            if not dry_run:
                record_slate_run(
                    for_date=today_str,
                    pick_count=0,
                    props_fetched=0,
                    games_count=0,
                    status="no_games",
                    duration_seconds=time.perf_counter() - start_ts,
                )
            return 0
        _logger.info("[1] %d games today.", len(games))

        # ── Step 2: Active rosters + injury map ──────────────────────────
        _logger.info("[2] Loading rosters + injury map…")
        players_today = get_todays_players(games)
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
            _logger.warning("[3] No props returned — exiting.")
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
                _logger.debug("[6b] Cache file warm failed (non-fatal): %s", exc)    elif dry_run:
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
    """Run the slate pipeline on a fixed schedule until interrupted.

    Designed for Railway deployments where GitHub Actions cron is not
    available or needs a warm-standby companion process.  Gracefully
    handles SIGTERM so Railway can shut it down cleanly.

    Args:
        dry_run:           Passed through to every ``run_slate()`` call.
        interval_minutes:  Seconds between pipeline runs (default 30 min).
    """
    import signal

    _shutdown = threading.Event()

    def _handle_signal(signum, frame):  # noqa: ANN001
        _logger.info("Received signal %s — daemon shutting down cleanly.", signum)
        _shutdown.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    interval_sec = interval_minutes * 60
    _logger.info(
        "=== slate_worker DAEMON  interval=%dm  dry_run=%s ===",
        interval_minutes, dry_run,
    )

    while not _shutdown.is_set():
        run_start = time.monotonic()
        try:
            run_slate(dry_run=dry_run)
        except Exception as exc:
            _logger.error("Daemon run-slate failed: %s", exc, exc_info=True)

        elapsed = time.monotonic() - run_start
        wait_sec = max(0.0, interval_sec - elapsed)
        _logger.info("Next run in %.0f s  (ctrl-C or SIGTERM to stop).", wait_sec)

        # Sleep in short increments so SIGTERM is noticed promptly.
        deadline = time.monotonic() + wait_sec
        while not _shutdown.is_set() and time.monotonic() < deadline:
            time.sleep(min(5.0, deadline - time.monotonic()))

    _logger.info("=== slate_worker DAEMON exited cleanly. ===")


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
