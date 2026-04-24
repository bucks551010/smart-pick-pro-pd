"""NBA player headshot fetcher.

Resolves a player name → NBA player ID via nba_api static data,
fetches the headshot from the NBA CDN, and returns it as a base64
PNG data URI so Playwright can embed it without CORS issues.

Results are cached on disk at OUTPUT_DIR/_headshots/ by player_id
so each image is fetched only once per deployment.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

import requests
from nba_api.stats.static import players as nba_players

from config import OUTPUT_DIR

_log = logging.getLogger(__name__)

_CACHE_DIR = OUTPUT_DIR / "_headshots"
_CDN = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
_FALLBACK = "https://cdn.nba.com/headshots/nba/latest/1040x760/logoman.png"
_TIMEOUT = 6  # seconds


def _cache_path(player_id: int) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{player_id}.png"


def _fetch_bytes(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as exc:
        _log.debug("Headshot fetch failed for %s: %s", url, exc)
    return None


def _to_data_uri(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    return f"data:image/png;base64,{b64}"


def get_headshot_uri(player_name: str) -> str | None:
    """Return a base64 PNG data URI for *player_name*, or None on failure."""
    # Resolve name → player_id
    results = nba_players.find_players_by_full_name(player_name)
    if not results:
        # Try partial / fuzzy: match first token as first name, rest as last
        parts = player_name.strip().split()
        if len(parts) >= 2:
            results = nba_players.find_players_by_last_name(parts[-1])
            results = [r for r in results if parts[0].lower() in r["full_name"].lower()]
    if not results:
        _log.debug("No NBA player found for '%s'", player_name)
        return None

    # Prefer active players; fall back to first result
    active = [r for r in results if r.get("is_active")]
    player = (active or results)[0]
    player_id: int = player["id"]

    # Disk cache hit?
    cached = _cache_path(player_id)
    if cached.exists():
        return _to_data_uri(cached.read_bytes())

    # Fetch from CDN
    image_bytes = _fetch_bytes(_CDN.format(player_id=player_id))
    if not image_bytes:
        image_bytes = _fetch_bytes(_FALLBACK)
    if not image_bytes:
        return None

    cached.write_bytes(image_bytes)
    return _to_data_uri(image_bytes)


def enrich_picks_with_headshots(picks: list[dict]) -> list[dict]:
    """Return a new list of picks with 'headshot_uri' added to each dict."""
    enriched = []
    for pick in picks:
        p = dict(pick)
        name = p.get("player_name", "")
        if name and not p.get("headshot_uri"):
            p["headshot_uri"] = get_headshot_uri(name)
        enriched.append(p)
    return enriched
