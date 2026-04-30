# ============================================================
# FILE: config/settings.py
# PURPOSE: Single source of truth for ALL app-wide configuration.
#
#          Environment variables are read here and ONLY here.
#          All other modules import from this file instead of
#          calling os.environ directly.
#
#          Supports .env file loading via python-dotenv (optional).
#
# Usage:
#   from config.settings import settings
#   db_path = settings.DB_PATH
#   is_prod = settings.IS_PRODUCTION
# ============================================================

from __future__ import annotations

import os
from pathlib import Path

# ── Optional .env loading ──────────────────────────────────────
# python-dotenv loads a .env file into os.environ if available.
# In production, env vars are set by Docker/Compose/Caddy instead.
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed — use raw os.environ


# ── Project root ───────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _bool_env(key: str, default: bool = False) -> bool:
    """Read an env var as a boolean (true/1/yes → True)."""
    val = os.environ.get(key, "").strip().lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


class _Settings:
    """Centralized app settings — reads from env vars once at import time.

    All attributes are plain Python types (str, int, float, bool, Path).
    No Pydantic dependency required.
    """

    # ── App Metadata ──────────────────────────────────────────
    APP_NAME: str = "SmartAI NBA"
    APP_VERSION: str = "2.0.0"
    PROJECT_ROOT: Path = _PROJECT_ROOT

    # ── Environment ───────────────────────────────────────────
    IS_PRODUCTION: bool = _bool_env("SMARTAI_PRODUCTION", False)
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

    # ── Database ──────────────────────────────────────────────
    DB_PATH: str = os.environ.get(
        "DB_PATH",
        str(Path(os.environ.get("DB_DIR", str(_PROJECT_ROOT / "db"))) / "smartai_nba.db"),
    )

    # ── Stripe / Payments ─────────────────────────────────────
    STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_PRICE_ID: str = os.environ.get("STRIPE_PRICE_ID", "")
    STRIPE_PRICE_SHARP_IQ: str = os.environ.get("STRIPE_PRICE_SHARP_IQ", "")
    STRIPE_PRICE_SMART_MONEY: str = os.environ.get("STRIPE_PRICE_SMART_MONEY", "")
    STRIPE_PRICE_INSIDER_CIRCLE: str = os.environ.get("STRIPE_PRICE_INSIDER_CIRCLE", "")
    STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    APP_URL: str = os.environ.get("APP_URL", "http://localhost:8501")

    # ── External APIs ─────────────────────────────────────────
    ODDS_API_KEY: str = os.environ.get("ODDS_API_KEY", "")
    API_CACHE_TTL_SECONDS: int = int(os.environ.get("API_CACHE_TTL_SECONDS", "300"))

    # ── Server ────────────────────────────────────────────────
    PORT: int = int(os.environ.get("PORT", "8501"))
    WEBHOOK_PORT: int = int(os.environ.get("WEBHOOK_PORT", "5000"))

    # ── Analysis Engine ───────────────────────────────────────
    # Number of Monte Carlo simulation trials per prop analysis.
    # Override via SIM_N env var (e.g. SIM_N=500 for faster dev runs,
    # SIM_N=2000 for higher-accuracy prod runs). (Audit A-021)
    SIM_N: int = int(os.environ.get("SIM_N", "1000"))
    # Max days of staleness before defensive_ratings.csv triggers a
    # QAM warning banner. Override via DEF_RATINGS_MAX_AGE_DAYS. (Audit A-013)
    DEF_RATINGS_MAX_AGE_DAYS: int = int(os.environ.get("DEF_RATINGS_MAX_AGE_DAYS", "3"))

    # ── Paths ─────────────────────────────────────────────────
    DATA_DIR: Path = _PROJECT_ROOT / "data"
    CACHE_DIR: Path = _PROJECT_ROOT / "cache"
    LOGS_DIR: Path = _PROJECT_ROOT / "logs"
    TRACKING_DIR: Path = _PROJECT_ROOT / "tracking"

    def __repr__(self) -> str:
        safe_attrs = {
            k: v for k, v in self.__class__.__dict__.items()
            if not k.startswith("_")
            and k not in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "ODDS_API_KEY")
            and not callable(v)
        }
        return f"Settings({safe_attrs})"


# Singleton — import this everywhere
settings = _Settings()
