"""Reusable campaign builders — same code path used by UI, scheduler, and webhook."""
from __future__ import annotations
import logging
from datetime import date
from itertools import groupby
from pathlib import Path

from core import data_source as ds
from core.brand_voice import pick_cta_rotation
from core.llm_copy import CopyVariants, generate_copy
from core.variants import pick_random_skin
from core.win_cards import render_win_cards_for_results
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
    skin = pick_random_skin()

    html = render_html(
        "results.html",
        context={
            "title":      f"{summary.wins}-{summary.losses} Last Night",
            "subtitle":   "Receipts always shown.",
            "wins":       summary.wins, "losses": summary.losses,
            "win_rate":   summary.win_rate, "roi_pct": summary.roi_pct,
            "picks":      wins_only,   # all wins displayed for verification
            "cols":       2,
            "skin_class": skin["class"],
        },
        utm_source="recap",
        utm_campaign=f"morning_recap_{summary.bet_date}",
    )
    images = render_to_images(html, name_prefix=f"recap_{summary.bet_date}")
    results = deploy_campaign(images, _channel_text_map(copy, channels), channels)

    # Render individual win cards for each winning prop and post to Instagram/TikTok
    win_card_channels = tuple(c for c in channels if c in ("instagram", "tiktok", "threads"))
    if win_card_channels and summary.wins > 0:
        win_cards = render_win_cards_for_results(summary.bets, skin_class=skin["class"])
        for card in win_cards:
            # Each win card gets its own caption line: "Player OVER X.X PTS ✓ WIN"
            stat_abbr = {"Points":"PTS","Assists":"AST","Rebounds":"REB","Steals":"STL",
                         "Blocks":"BLK","Turnovers":"TO","3-Pointers Made":"3PM","Fantasy Score":"FPTS"}
            stat = stat_abbr.get(card.stat_type, card.stat_type)
            card_caption = (
                f"✅ {card.player_name.upper()} {card.direction.upper()} "
                f"{card.prop_line:.1f} {stat} — WIN. "
                f"SAFE Score™ {card.confidence_score:.0f}/100. "
                f"Receipts on file. @smartpickpro"
            ) if card.confidence_score else (
                f"✅ {card.player_name.upper()} {card.direction.upper()} "
                f"{card.prop_line:.1f} {stat} — WIN. Receipts on file."
            )
            card_images = {"square": card.image_path}
            text_map = {ch: card_caption for ch in win_card_channels}
            card_results = deploy_campaign(card_images, text_map, win_card_channels)
            results.extend(card_results)

    return results


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
    skin = pick_random_skin()

    html = render_html(
        "slate.html",
        context={
            "eyebrow":    "TONIGHT'S PICKS",
            "title":      title,
            "subtitle":   sub,
            "picks":      picks[:12],
            "cols":       2 if len(picks) > 1 else 1,
            "skin_class": skin["class"],
        },
        utm_source="pregame",
        utm_campaign=f"pregame_{pick_filter}_{date.today():%Y%m%d}",
    )
    images = render_to_images(html, name_prefix=f"slate_{pick_filter}_{date.today():%Y%m%d}")
    return deploy_campaign(images, _channel_text_map(copy, channels), channels)


# ── WEEKLY SCORECARD ────────────────────────────────────────

def build_and_post_weekly_scorecard(channels=_DEFAULT_CHANNELS) -> list[PostResult]:
    """Sunday post: wins-only scorecard for the past 7 days."""
    summary = ds.get_results_for_week()
    if summary.wins == 0:
        _log.info("Weekly scorecard skipped: no wins for week ending %s", summary.week_end)
        return []

    payload = {
        "wins": summary.wins,
        "losses": summary.losses,
        "win_rate": summary.win_rate,
        "roi_pct": summary.roi_pct,
        "week_start": summary.week_start,
        "week_end": summary.week_end,
        "winning_props": summary.winning_bets,
    }
    copy = generate_copy("weekly", payload)
    skin = pick_random_skin()

    html = render_html(
        "results.html",
        context={
            "title":      f"Week of {summary.week_start}",
            "subtitle":   f"{summary.wins}W - {summary.losses}L | {summary.win_rate:.0f}% Win Rate",
            "wins":       summary.wins,
            "losses":     summary.losses,
            "win_rate":   summary.win_rate,
            "roi_pct":    summary.roi_pct,
            "picks":      summary.winning_bets,  # winning props only
            "cols":       2,
            "skin_class": skin["class"],
        },
        utm_source="weekly",
        utm_campaign=f"weekly_scorecard_{summary.week_end}",
    )
    images = render_to_images(html, name_prefix=f"weekly_{summary.week_end}")
    return deploy_campaign(images, _channel_text_map(copy, channels), channels)


# ── BRANDING / CTA ──────────────────────────────────────────

def build_and_post_branding(channels=_DEFAULT_CHANNELS) -> list[PostResult]:
    # Rotate headline based on day-of-week so Mon/Wed/Fri each look different
    day_index = date.today().weekday()  # 0=Mon, 2=Wed, 4=Fri → different index each time
    headline, subheadline, button_text = pick_cta_rotation(day_index)

    payload = {"product": "SmartPickPro NBA", "stage": "brand_awareness", "headline": headline}
    copy = generate_copy("brand", payload)
    skin = pick_random_skin()

    html = render_html(
        "brand_cta.html",
        context={
            "title":        "Quant NBA Analytics",
            "headline":     headline,
            "subheadline":  subheadline,
            "button_text":  button_text,
            "tagline":      "Quantum Matrix Engine™ 5.6",
            "skin_class":   skin["class"],
        },
        utm_source="brand",
        utm_campaign=f"brand_cta_{date.today():%Y%m%d}",
    )
    images = render_to_images(html, name_prefix=f"brand_{date.today():%Y%m%d}")
    return deploy_campaign(images, _channel_text_map(copy, channels), channels)
