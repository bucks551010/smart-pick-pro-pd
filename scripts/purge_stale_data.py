"""
One-time DB cleanup: delete stale analysis_sessions and all_analysis_picks
that predate today's ET sports day.

Run once after deploying the stale-data fixes:
    python scripts/purge_stale_data.py

Safe to re-run — DELETE WHERE pick_date < today is idempotent.
"""
import os
import sys
import datetime

# ── ET sports-day boundary (4 AM ET = new day) ──────────────────────────────
try:
    from zoneinfo import ZoneInfo
    _eastern = ZoneInfo("America/New_York")
except ImportError:
    _eastern = None


def _today_et() -> str:
    if _eastern:
        import datetime as _dt
        now_et = _dt.datetime.now(_eastern)
    else:
        now_et = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
    if now_et.hour < 4:
        now_et -= datetime.timedelta(days=1)
    return now_et.date().isoformat()


TODAY = _today_et()
print(f"ET sports day today: {TODAY}")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── PostgreSQL (Railway production) ─────────────────────────────────────────
if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # 1. Delete all analysis_sessions whose content pre-dates today.
    #    The date guard in load_latest_analysis_session now handles this
    #    at read-time, but a clean table starts fresh.
    cur.execute(
        "DELETE FROM analysis_sessions WHERE analysis_timestamp::date < %s",
        (TODAY,),
    )
    sessions_deleted = cur.rowcount
    print(f"Deleted {sessions_deleted} stale analysis_sessions (before {TODAY})")

    # 2. Delete all all_analysis_picks older than today.
    cur.execute(
        "DELETE FROM all_analysis_picks WHERE pick_date < %s",
        (TODAY,),
    )
    picks_deleted = cur.rowcount
    print(f"Deleted {picks_deleted} stale all_analysis_picks (before {TODAY})")

    conn.commit()
    cur.close()
    conn.close()
    print("Done (PostgreSQL).")

# ── SQLite (local dev) ───────────────────────────────────────────────────────
else:
    import sqlite3
    from pathlib import Path

    DB_PATH = Path(__file__).resolve().parents[1] / "data" / "smart_pick_pro.db"
    if not DB_PATH.exists():
        # Try common alt locations
        for alt in [
            Path(__file__).resolve().parents[1] / "smart_pick_pro.db",
            Path(__file__).resolve().parents[1] / "db" / "smart_pick_pro.db",
        ]:
            if alt.exists():
                DB_PATH = alt
                break

    if not DB_PATH.exists():
        print(f"SQLite DB not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM analysis_sessions WHERE substr(analysis_timestamp, 1, 10) < ?",
        (TODAY,),
    )
    sessions_deleted = cur.rowcount
    print(f"Deleted {sessions_deleted} stale analysis_sessions (before {TODAY})")

    cur.execute(
        "DELETE FROM all_analysis_picks WHERE pick_date < ?",
        (TODAY,),
    )
    picks_deleted = cur.rowcount
    print(f"Deleted {picks_deleted} stale all_analysis_picks (before {TODAY})")

    conn.commit()
    conn.close()
    print("Done (SQLite).")
