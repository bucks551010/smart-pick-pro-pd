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


def _run_daily_update():
    """Run the ETL daily updater to refresh data on deploy."""
    try:
        from etl.data_updater import run_daily_update
        _logger.info("Running ETL daily update...")
        run_daily_update()
        _logger.info("ETL daily update complete.")
    except Exception as exc:
        _logger.warning("ETL daily update failed (non-fatal): %s", exc)


if __name__ == "__main__":
    _seed_volume()
    _run_daily_update()

    # Launch Streamlit
    _logger.info("Starting Streamlit...")
    sys.exit(subprocess.call([
        sys.executable, "-m", "streamlit", "run",
        "Smart_Picks_Pro_Home.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
    ]))
