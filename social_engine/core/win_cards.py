"""Win card renderer — generates a 1080×1080 shareable image for each winning pick.

A win card shows:
  - Player headshot (large, circular, glowing green)
  - Prop line (direction + line value + stat type)
  - Actual result value (when available)
  - SAFE Score™ bar
  - Platform badge
  - HIT ✓ stamp
  - SmartPickPro branding + compliance footer

Usage:
    from core.win_cards import render_win_cards_for_results
    cards = render_win_cards_for_results(results_summary, skin_class="skin-neural")
    # returns list[WinCard] — each has .image_path and .bet dict

Or render a single card:
    from core.win_cards import render_single_win_card
    card = render_single_win_card(bet_dict, skin_class="skin-neural")
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import SETTINGS, OUTPUT_DIR
from core.headshots import get_headshot_uri
from core.variants import pick_random_skin
from render.headless import render_png_bytes
from render.jinja_engine import render_html

_log = logging.getLogger(__name__)

_STAT_ABBR = {
    "Points": "PTS", "Assists": "AST", "Rebounds": "REB",
    "Steals": "STL", "Blocks": "BLK", "Turnovers": "TO",
    "3-Pointers Made": "3PM", "Fantasy Score": "FPTS",
}

# Win cards are always square — designed to be shared 1:1
_WIN_CARD_SIZE = (1080, 1080)

WIN_CARDS_DIR = OUTPUT_DIR / "win_cards"


@dataclass
class WinCard:
    player_name:      str
    prop_line:        float
    direction:        str
    stat_type:        str
    platform:         str
    confidence_score: float | None
    image_path:       Path
    bet:              dict[str, Any]


def render_single_win_card(
    bet: dict[str, Any],
    skin_class: str | None = None,
) -> WinCard | None:
    """Render one win card PNG for a single resolved WIN bet.

    Returns None if rendering fails (non-fatal — morning recap continues).
    """
    player = bet.get("player_name") or "Unknown"
    prop_line = float(bet.get("prop_line") or 0)
    direction = bet.get("direction") or "OVER"
    stat_type = bet.get("stat_type") or ""
    platform  = bet.get("platform") or ""
    score     = bet.get("confidence_score")
    actual    = bet.get("actual_value")
    team      = bet.get("team") or ""
    bet_date  = bet.get("bet_date") or ""
    skin      = skin_class or pick_random_skin()["class"]

    # Fetch headshot (cached)
    headshot_uri = get_headshot_uri(player)

    try:
        html = render_html(
            "win_card.html",
            context={
                "player_name":      player,
                "team":             team,
                "prop_line":        prop_line,
                "direction":        direction,
                "stat_type":        stat_type,
                "stat_abbr":        _STAT_ABBR,
                "platform":         platform,
                "confidence_score": score,
                "actual_value":     actual,
                "headshot_uri":     headshot_uri,
                "skin_class":       skin,
                "date_str":         bet_date,
                "eyebrow":          f"WIN — {platform.upper()} — RECEIPT ON FILE",
            },
            utm_source="win_card",
            utm_campaign=f"win_{bet_date}",
        )

        # Ensure output dir exists
        WIN_CARDS_DIR.mkdir(parents=True, exist_ok=True)

        # Slugify player name for filename
        slug = player.lower().replace(" ", "_").replace(".", "")
        stat_slug = _STAT_ABBR.get(stat_type, stat_type).lower()
        filename = f"{bet_date}_{slug}_{direction.lower()}_{prop_line}_{stat_slug}.png"
        out_path = WIN_CARDS_DIR / filename

        img_bytes = render_png_bytes(html, width=_WIN_CARD_SIZE[0], height=_WIN_CARD_SIZE[1])
        out_path.write_bytes(img_bytes)
        _log.info("Win card saved: %s", out_path.name)

        return WinCard(
            player_name=player, prop_line=prop_line, direction=direction,
            stat_type=stat_type, platform=platform, confidence_score=score,
            image_path=out_path, bet=bet,
        )

    except Exception as exc:
        _log.warning("Win card render failed for %s: %s", player, exc)
        return None


def render_win_cards_for_results(
    bets: list[dict[str, Any]],
    skin_class: str | None = None,
) -> list[WinCard]:
    """Render a win card for every WIN bet in the list.

    Uses the same skin for all cards in one batch (visual consistency
    for a single night's results story / carousel).
    """
    skin = skin_class or pick_random_skin()["class"]
    wins = [b for b in bets if (b.get("result") or "").upper() == "WIN"]
    if not wins:
        _log.info("No WIN bets — skipping win card generation")
        return []

    cards: list[WinCard] = []
    for bet in wins:
        card = render_single_win_card(bet, skin_class=skin)
        if card:
            cards.append(card)

    _log.info("Rendered %d/%d win cards for this batch", len(cards), len(wins))
    return cards
