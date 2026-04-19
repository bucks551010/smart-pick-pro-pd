#!/usr/bin/env python3
"""start.py – Railway entrypoint: run daily ETL update then launch Streamlit."""

import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
_logger = logging.getLogger("start")


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
    _run_daily_update()

    # Launch Streamlit
    _logger.info("Starting Streamlit...")
    sys.exit(subprocess.call([
        sys.executable, "-m", "streamlit", "run",
        "Smart_Picks_Pro_Home.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
    ]))
