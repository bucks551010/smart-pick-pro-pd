"""Reusable campaign builders — same code path used by UI, scheduler, and webhook."""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path

from core import data_source as ds
from core.llm_copy import CopyVariants, generate_copy
from distribute.base import PostResult
from distribute.campaign import deploy_campaign
from render.headless import render_to_images
from render.jinja_engine import render_html

_log = logging.getLogger(__name__)

_DEFAULT_CHANNELS = ("twitter", "facebook", "instagram", "threads", "tiktok")


def _channel_text_map(copy: CopyVariants, channels) -> dict[str, str]:
    """Map each channel to a tone-appropriate variant."""
    tone_map = {
        "twitter":   "direct_cta",   # short + punchy
        "facebook":  "analytical",   # longer-form audience
        "instagram": "hype",         # visual-first
        "threads":   "analytical",
        "tiktok":    "hype",
    }
    return {ch: copy.for_platform(ch, tone_map.get(ch, "analytical")) for ch in channels}


# ── MORNING RECAP ───────────────────────────────────────────

def build_and_post_morning_recap(channels=_DEFAULT_CHANNELS) -> list[PostResult]:
    summary = ds.get_results_for_date()  # yesterday
    if summary.total == 0:
        _log.info("Morning recap skipped: no resolved bets for %s", summary.bet_date)
        return []

    # Show ALL winning props so followers can verify each one
    wins_only = [
        b for b in summary.bets
        if (b.get("result") or "").upper() == "WIN"
    ]

    payload = {
        "wins": summary.wins, "losses": summary.losses,
        "win_rate": summary.win_rate, "roi_pct": summary.roi_pct,
        "winning_props": wins_only,
    }
    copy = generate_copy("results", payload)

    html = render_html(
        "results.html",
        context={
            "title":    f"{summary.wins}-{summary.losses} Last Night",
            "subtitle": "Receipts always shown.",
            "wins": summary.wins, "losses": summary.losses,
            "win_rate": summary.win_rate, "roi_pct": summary.roi_pct,
            "picks":    wins_only,   # all wins displayed for verification
            "cols":     2,
        },
        utm_source="recap",
        utm_campaign=f"morning_recap_{summary.bet_date}",
    )
    images = render_to_images(html, name_prefix=f"recap_{summary.bet_date}")
    return deploy_campaign(images, _channel_text_map(copy, channels), channels)


# ── PRE-GAME SLATE PUSH ─────────────────────────────────────

def build_and_post_pregame_slate(
    *,
    pick_filter: str = "platform_all",  # "platform_all" | "top3" | "qeg" | "platform:PrizePicks"
    channels=_DEFAULT_CHANNELS,
) -> list[PostResult]:
    if pick_filter == "platform_all":
        # All picks the app analyzed today, each labeled with their platform
        picks = ds.get_slate_for_date()
        title, sub = "Tonight's Platform Picks", "Powered by SmartPickPro analysis"
    elif pick_filter == "top3":
        picks = ds.get_top_n_picks(3)
        title, sub = "Tonight's Top 3", "Highest-confidence quant edges"
    elif pick_filter == "qeg":
        picks = ds.get_qeg_picks()
        title, sub = "Quantum Edge Gap", "Picks where projected > line by ≥5%"
    elif pick_filter.startswith("platform:"):
        plat = pick_filter.split(":", 1)[1]
        picks = ds.get_platform_picks(plat)
        title, sub = f"{plat} Picks", "Tonight's edge picks"
    else:
        picks = ds.get_slate_for_date()
        title, sub = "Tonight's Picks", ""

    if not picks:
        _log.info("Pre-game post skipped: no picks for filter=%s", pick_filter)
        return []

    payload = {
        "picks": picks[:12],
        "filter": pick_filter,
        # Group by platform so LLM can reference them by name
        "platforms": list({p.get("platform", "Unknown") for p in picks}),
    }
    copy = generate_copy("slate", payload)

    html = render_html(
        "slate.html",
        context={
            "eyebrow":  "TONIGHT'S PICKS",
            "title":    title,
            "subtitle": sub,
            "picks":    picks[:12],
            "cols":     2 if len(picks) > 1 else 1,
        },
        utm_source="pregame",
        utm_campaign=f"pregame_{pick_filter}_{date.today():%Y%m%d}",
    )
    images = render_to_images(html, name_prefix=f"slate_{pick_filter}_{date.today():%Y%m%d}")
    return deploy_campaign(images, _channel_text_map(copy, channels), channels)


# ── BRANDING / CTA ──────────────────────────────────────────

def build_and_post_branding(channels=_DEFAULT_CHANNELS) -> list[PostResult]:
    payload = {"product": "SmartPickPro NBA", "stage": "brand_awareness"}
    copy = generate_copy("brand", payload)

    html = render_html(
        "brand_cta.html",
        context={
            "title":        "Quant NBA Analytics",
            "headline":     "THE EDGE ISN'T LUCK. IT'S MATH.",
            "subheadline":  "1,000 Monte Carlo simulations per pick. Zero black boxes. Free trial.",
            "button_text":  "→ START FREE",
            "tagline":      "Quantitative NBA Analytics",
        },
        utm_source="brand",
        utm_campaign=f"brand_cta_{date.today():%Y%m%d}",
    )
    images = render_to_images(html, name_prefix=f"brand_{date.today():%Y%m%d}")
    return deploy_campaign(images, _channel_text_map(copy, channels), channels)
