#!/usr/bin/env python3
"""start.py – Railway entrypoint: seed persistent volume, run daily ETL update, launch Streamlit."""

import os
import shutil
import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
_logger = logging.getLogger("start")

_APP_DB_DIR = Path("/app/db")
_VOLUME_DIR = Path(os.environ.get("DB_DIR", ""))


def _seed_volume():
    """Copy seed databases from the Docker image to the persistent volume if missing."""
    if not _VOLUME_DIR or not _VOLUME_DIR.is_absolute():
        _logger.warning(
            "DB_DIR not set or not absolute — user accounts will NOT persist across restarts!"
        )
        return

    _VOLUME_DIR.mkdir(parents=True, exist_ok=True)

    # Persistence check: write a sentinel file and read it back to confirm
    # the directory is actually persistent (i.e., a real volume is mounted).
    _sentinel = _VOLUME_DIR / ".volume_check"
    try:
        _sentinel.write_text("ok")
        assert _sentinel.read_text() == "ok"
        _logger.info("Volume persistence check PASSED at %s", _VOLUME_DIR)
    except Exception as e:
        _logger.error(
            "Volume persistence check FAILED at %s: %s — "
            "user accounts will be lost on container restart. "
            "Make sure the Railway 'smartai_data' volume is created and mounted at /data.",
            _VOLUME_DIR, e,
        )

    for db_name in ("smartpicks.db", "smartai_nba.db"):
        src = _APP_DB_DIR / db_name
        dst = _VOLUME_DIR / db_name
        if dst.exists():
            _logger.info("Volume already has %s (%.1f MB)", db_name, dst.stat().st_size / 1e6)
            continue
        if src.exists():
            _logger.info("Seeding %s to volume...", db_name)
            shutil.copy2(str(src), str(dst))
            _logger.info("Seeded %s (%.1f MB)", db_name, dst.stat().st_size / 1e6)
        else:
            _logger.info("No seed %s in image — will be created on first use", db_name)


def _seed_user_from_env():
    """Create or reset a specific user account from env vars.

    Set these Railway environment variables to restore a user's access:
      SEED_USER_EMAIL    = their email address
      SEED_USER_PASSWORD = a temporary password (min 8 chars, 1 letter, 1 number)

    On next deploy the account will be created (if missing) or its password
    updated (if it already exists). Remove the env vars after the user logs in.
    """
    email = os.environ.get("SEED_USER_EMAIL", "").strip().lower()
    password = os.environ.get("SEED_USER_PASSWORD", "")
    if not email or not password:
        return
    if len(password) < 8:
        _logger.warning("SEED_USER_PASSWORD too short — skipping user seed for %s", email)
        return
    try:
        from utils.auth_gate import _hash_password, _AuthConn
        pw_hash = _hash_password(password)
        with _AuthConn() as db:
            existing = db.fetchone("SELECT user_id FROM users WHERE email = ?", (email,))
            if existing:
                db.execute(
                    "UPDATE users SET password_hash = ?, failed_login_count = 0, lockout_until = NULL WHERE email = ?",
                    (pw_hash, email),
                )
                _logger.info("SEED_USER: password reset for %s", email)
            else:
                db.execute(
                    "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                    (email, pw_hash, email.split("@")[0]),
                )
                _logger.info("SEED_USER: created account for %s", email)
    except Exception as exc:
        _logger.error("SEED_USER: failed for %s — %s", email, exc)


def _run_daily_update():
    """Run the ETL daily updater to refresh data on deploy."""
    try:
        from etl.data_updater import run_update
        _logger.info("Running ETL daily update...")
        run_update()
        _logger.info("ETL daily update complete.")
    except Exception as exc:
        _logger.warning("ETL daily update failed (non-fatal): %s", exc)


if __name__ == "__main__":
    _seed_volume()

    # Ensure PostgreSQL users table exists (runs instantly if already created)
    try:
        from utils.auth_gate import _ensure_pg_users_table, _HAS_PSYCOPG2
        if _HAS_PSYCOPG2:
            _ensure_pg_users_table()
            _logger.info("PostgreSQL users table ready.")
        else:
            _logger.info("Auth DB: SQLite mode (no DATABASE_URL).")
    except Exception as exc:
        _logger.error("Failed to initialise auth DB table: %s", exc)

    # Ensure PostgreSQL subscriptions table exists
    try:
        from utils.auth import _ensure_pg_subscriptions_table, _HAS_PG_SUB
        if _HAS_PG_SUB:
            _ensure_pg_subscriptions_table()
            _logger.info("PostgreSQL subscriptions table ready.")
    except Exception as exc:
        _logger.error("Failed to initialise PG subscriptions table: %s", exc)

    _seed_user_from_env()
    _run_daily_update()

    # Launch Streamlit
    _logger.info("Starting Streamlit...")
    sys.exit(subprocess.call([
        sys.executable, "-m", "streamlit", "run",
        "Smart_Picks_Pro_Home.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
    ]))
