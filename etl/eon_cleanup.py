"""
etl/eon_cleanup.py
──────────────────
Standalone end-of-night cleanup script for use as a Railway cron job.

Railway cron config (railway.toml):
    [[cron]]
    schedule = "0 7 * * *"      # 7:00 UTC = 3:00 AM ET (mid-window, nightly)
    command   = "python -m etl.eon_cleanup"

The cron runs outside the Streamlit process, so even if the app pod
restarts or redeploys between 2–8 AM ET the cleanup still fires.
(Audit issue A-007)

Environment variables respected:
    DATABASE_URL        — PostgreSQL DSN (same as main app)
    EON_CLEANUP_DISABLED — set "1" to skip (emergency bypass)
    EON_WINDOW_START    — earliest ET hour to run (default 2)
    EON_WINDOW_END      — latest  ET hour to skip (default 8)

Exit codes:
    0   — cleanup ran successfully (or was already done today, or not yet in window)
    1   — cleanup ran but had non-fatal errors (bet resolution partial failures, etc.)
    2   — fatal error (DB unavailable, unexpected exception)
"""

from __future__ import annotations

import logging
import os
import sys

# ── ensure repo root is importable ──────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger("eon_cleanup")

# ── guard: allow emergency disable via env var ──────────────────────────────
if os.environ.get("EON_CLEANUP_DISABLED", "").strip() == "1":
    _logger.info("[EON standalone] EON_CLEANUP_DISABLED=1 — skipping.")
    sys.exit(0)


def _et_now():
    """Return current datetime in America/New_York."""
    import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        import datetime as _dt
        return _dt.datetime.now(_dt.timezone(datetime.timedelta(hours=-4)))


def main() -> int:
    """Run the EON cleanup and return an exit code."""
    try:
        et_now = _et_now()
        et_hour = et_now.hour

        eon_start = int(os.environ.get("EON_WINDOW_START", "2"))
        eon_end   = int(os.environ.get("EON_WINDOW_END",   "8"))

        if not (eon_start <= et_hour < eon_end):
            _logger.info(
                "[EON standalone] ET hour %d is outside EON window %d–%d. Nothing to do.",
                et_hour, eon_start, eon_end,
            )
            return 0

        # Derive the sports date (yesterday before the window boundary).
        # _nba_today_iso uses a 4 AM ET cutoff, so at 3 AM ET it returns yesterday.
        try:
            from tracking.database import _nba_today_iso
            sports_date = _nba_today_iso()
        except Exception as exc:
            _logger.warning(
                "[EON standalone] Could not import _nba_today_iso (%s); "
                "falling back to yesterday's UTC date.",
                exc,
            )
            import datetime
            sports_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        _logger.info(
            "[EON standalone] Running end-of-night cleanup for sports date %s (ET hour %d).",
            sports_date, et_hour,
        )

        # Check whether today's cleanup has already been done (idempotency guard).
        try:
            from tracking.database import _db_read
            rows = _db_read(
                "SELECT value FROM kv_meta WHERE key = 'last_eon_cleanup_date'",
            )
            if rows and rows[0].get("value") == sports_date:
                _logger.info(
                    "[EON standalone] Already ran for %s today. Skipping (idempotent).",
                    sports_date,
                )
                return 0
        except Exception:
            pass  # kv_meta may not exist yet — first run is fine

        # ── Run the cleanup ──────────────────────────────────────────────────
        from etl.scheduler import _run_end_of_night_cleanup
        summary = _run_end_of_night_cleanup(sports_date)

        # Mark this date as cleaned so re-runs are idempotent.
        try:
            from tracking.database import _db_write
            _db_write(
                """
                INSERT INTO kv_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                ("last_eon_cleanup_date", sports_date),
                caller="eon_standalone_mark",
            )
        except Exception as exc:
            _logger.warning("[EON standalone] Could not persist cleanup date marker: %s", exc)

        error_count = len(summary.get("errors", []))
        _logger.info(
            "[EON standalone] Done — bets_resolved=%d  picks_resolved=%d  errors=%d",
            summary.get("bets_resolved", 0),
            summary.get("picks_resolved", 0),
            error_count,
        )

        return 1 if error_count > 0 else 0

    except Exception as fatal:
        _logger.exception("[EON standalone] Fatal error: %s", fatal)
        return 2


if __name__ == "__main__":
    sys.exit(main())
