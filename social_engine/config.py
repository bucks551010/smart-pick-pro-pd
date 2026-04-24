"""Central config — brand palette, env vars, output specs."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Brand palette (Quantum Institutional) ────────────────────
BRAND = {
    "bg":        "#070A13",
    "panel":     "#0F172A",
    "panel_2":   "#1A2332",
    "accent":    "#00f0ff",
    "accent_2":  "#7C3AED",
    "text":      "#c8d8f0",
    "text_dim":  "#7a8aa3",
    "win":       "#00D559",
    "loss":      "#FF3B5C",
    "gold":      "#F5C518",
    "platinum":  "#E5E4E2",
}

# ── Output dimensions per platform ───────────────────────────
OUTPUT_SIZES = {
    "square":   (1080, 1080),  # IG feed, FB feed
    "landscape": (1200, 675),  # X / Twitter
    "portrait": (1080, 1920),  # IG/FB Story, Reels, TikTok
}

# ── Distribution channel → preferred size ────────────────────
CHANNEL_SIZE = {
    "twitter":   "landscape",
    "facebook":  "square",
    "instagram": "square",
    "threads":   "square",
    "tiktok":    "portrait",
}

# ── Compliance footer copy ───────────────────────────────────
COMPLIANCE_FOOTER = (
    "21+ • Play Responsibly • Not gambling advice • For entertainment only • "
    "Problem? Call 1-800-GAMBLER"
)


@dataclass(frozen=True)
class Settings:
    environment:        str = os.getenv("ENVIRONMENT", "development")
    timezone:           str = os.getenv("TIMEZONE", "America/New_York")
    brand_url:          str = os.getenv("BRAND_URL", "https://smartpickpro.app")
    watermark_text:     str = os.getenv("WATERMARK_TEXT", "SmartPickPro.app")
    database_url:       str = os.getenv("DATABASE_URL", "")
    gemini_api_key:     str = os.getenv("GEMINI_API_KEY", "")

    twitter_key:        str = os.getenv("TWITTER_API_KEY", "")
    twitter_secret:     str = os.getenv("TWITTER_API_SECRET", "")
    twitter_token:      str = os.getenv("TWITTER_ACCESS_TOKEN", "")
    twitter_token_sec:  str = os.getenv("TWITTER_ACCESS_SECRET", "")
    twitter_bearer:     str = os.getenv("TWITTER_BEARER_TOKEN", "")

    meta_token:         str = os.getenv("META_PAGE_ACCESS_TOKEN", "")
    meta_page_id:       str = os.getenv("META_PAGE_ID", "")
    meta_ig_id:         str = os.getenv("META_INSTAGRAM_BUSINESS_ID", "")
    meta_threads_id:    str = os.getenv("META_THREADS_USER_ID", "")

    tiktok_token:       str = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    tiktok_open_id:     str = os.getenv("TIKTOK_OPEN_ID", "")

    webhook_secret:     str = os.getenv("WEBHOOK_SHARED_SECRET", "")
    scheduler_enabled:  bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    recap_hour:         int  = int(os.getenv("RECAP_HOUR_LOCAL", "9"))
    pregame_lead_hours: int  = int(os.getenv("PREGAME_LEAD_HOURS", "2"))
    branding_cron:      str  = os.getenv("BRANDING_CRON", "0 14 * * 1,3,5")  # Mon/Wed/Fri 2pm


SETTINGS = Settings()
ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR   = ROOT / "_out"
OUTPUT_DIR.mkdir(exist_ok=True)
