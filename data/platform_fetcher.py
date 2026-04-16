# ============================================================
# FILE: data/platform_fetcher.py
# PURPOSE: Fetch live player prop lines from betting platforms:
#          PrizePicks, Underdog Fantasy, and DraftKings Pick6
#          (via The Odds API). Also provides cross-platform
#          comparison logic and best-platform recommendation.
#
# PLATFORMS:
#   - PrizePicks  : public JSON API, no key required
#   - Underdog    : public JSON API, no key required
#   - DraftKings  : via The Odds API (free key, 500 req/month)
#
# USAGE:
#   from data.platform_fetcher import fetch_all_platform_props
#   props = fetch_all_platform_props()
#
# RETURN FORMAT for every prop dict:
#   {
#       "player_name": "LeBron James",
#       "team":        "LAL",
#       "stat_type":   "points",          # internal key (normalized)
#       "line":        24.5,
#       "platform":    "PrizePicks",
#       "game_date":   "2026-03-10",
#       "fetched_at":  "2026-03-10T01:00:00",
#   }
#
# DESIGN PRINCIPLES:
#   - Graceful degradation: if one platform fails, others still run
#   - Rate limiting: 1-2 second delays between calls (polite to APIs)
#   - Session caching: callers should store result in session state
#   - Beginner-friendly comments throughout
# ============================================================

# Standard library imports (built into Python — no install needed)
import time       # For delays between API calls (rate limiting)
import datetime   # For timestamps on fetched props
import os         # For reading environment variables (API keys)
import asyncio    # For concurrent fetching across platforms

# Third-party HTTP library — must be installed (pip install requests)
# 'requests' is used by roster_engine.py already and listed in requirements.
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Async HTTP library for concurrent platform fetching (pip install aiohttp)
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Import our platform stat-name normalizer
# This converts "3-Point Made" → "threes", "Pts+Rebs" → "points_rebounds", etc.
from data.platform_mappings import normalize_stat_type
from engine import VALID_STAT_TYPES

# Import odds math from the single source of truth — engine/odds_engine.py
from engine.odds_engine import (
    american_odds_to_implied_probability,
    implied_probability_to_american_odds,
    calculate_breakeven_probability,
)

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

import time as _time

# ── Simple time-based API response cache ─────────────────────────────────────
_API_CACHE: dict = {}
# TTL is configurable via API_CACHE_TTL_SECONDS env var; default 5 minutes.
_API_CACHE_TTL: int = int(os.environ.get("API_CACHE_TTL_SECONDS", "300"))


def _cache_get(url: str):
    """Return cached response for *url* if not expired, else None."""
    entry = _API_CACHE.get(url)
    if entry is None:
        return None
    payload, ts = entry
    if _time.time() - ts > _API_CACHE_TTL:
        _API_CACHE.pop(url, None)
        return None
    return payload


def _cache_set(url: str, payload) -> None:
    """Store *payload* in the cache keyed by *url*."""
    _API_CACHE[url] = (payload, _time.time())

# Import the rate limiter for polite API access with circuit breaker
try:
    from utils.rate_limiter import RateLimiter as _RateLimiter
    # Feature 10: 20 req/min, 200/hour — matches existing live_data_fetcher limits
    _platform_rate_limiter = _RateLimiter(max_requests_per_minute=20, max_requests_per_hour=200)
    _RATE_LIMITER_AVAILABLE = True
except ImportError:
    _RATE_LIMITER_AVAILABLE = False
    _platform_rate_limiter = None

# Import rotating-header helpers from the utility layer.
# These provide per-platform headers with rotating User-Agent strings
# to reduce 403 blocks.  Falls back to _BASE_HEADERS (defined below)
# if the utility module is unavailable.
try:
    from utils.headers import get_underdog_headers, get_odds_api_headers
    _HAS_PLATFORM_HEADERS = True
except ImportError:
    _HAS_PLATFORM_HEADERS = False

# ============================================================
# SECTION: Module-level constants
# ============================================================

# How long to wait between calls to the same platform (seconds).
# BEGINNER NOTE: APIs block you if you call too fast. 1.5s is polite
# and mirrors the pattern in live_data_fetcher.py.
API_DELAY_SECONDS = 1.5

# HTTP timeout for platform API requests (seconds).
REQUEST_TIMEOUT_SECONDS = 15

# Browser-like User-Agent header so APIs don't block automated requests.
# BEGINNER NOTE: Web servers often reject requests without a User-Agent.
# This mimics a real Chrome browser on Windows.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Shared headers used for every platform request
_BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# PrizePicks public projections endpoint (no API key required)
PRIZEPICKS_URL = "https://api.prizepicks.com/projections"

# PrizePicks data mirror (https://github.com/enkday/prizepicks-data-mirror)
# Published as raw JSON on GitHub — no rate limiting or API key required.
# Includes today's and tomorrow's NBA props with goblin/demon/standard oddsType.
PRIZEPICKS_MIRROR_TODAY_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/prizepicks-nba-today.json"
)
PRIZEPICKS_MIRROR_TOMORROW_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/prizepicks-nba-tomorrow.json"
)

# Normalized hierarchy — standard-only props with game/player/team metadata
PRIZEPICKS_HIERARCHY_PROPS_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/hierarchy/current_day/props.json"
)
PRIZEPICKS_HIERARCHY_GAMES_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/hierarchy/current_day/games.json"
)
PRIZEPICKS_HIERARCHY_PLAYERS_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/hierarchy/current_day/players.json"
)
PRIZEPICKS_HIERARCHY_TEAMS_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/hierarchy/current_day/teams.json"
)
PRIZEPICKS_HIERARCHY_SLATES_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/hierarchy/current_day/slates.json"
)

# Per-team NBA props base URL (append {team-slug}.json)
PRIZEPICKS_MIRROR_TEAM_BASE_URL = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/nba-today"
)

# Historical archive template — real PrizePicks lines from past dates
PRIZEPICKS_ARCHIVE_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/enkday/prizepicks-data-mirror"
    "/main/data/hierarchy/archive/{date}/props.json"
)

# Underdog Fantasy public over/under lines endpoint (no API key required)
UNDERDOG_URL = "https://api.underdogfantasy.com/beta/v3/over_under_lines"

# The Odds API base URL — used to fetch DraftKings player props
# Documentation: https://the-odds-api.com/liveapi/guides/v4/
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

# Default American odds for platforms without traditional juice (e.g. -110)
# BEGINNER NOTE: -110 is the standard American odds for prop bets on DraftKings.
# Breakeven at -110 = 52.38% win rate. PrizePicks/Underdog don't use odds,
# so we default to -110 for their implied probability calculations.
_DEFAULT_AMERICAN_ODDS = -110

# ── Data Quarantine Thresholds ─────────────────────────────────────────────
# Lines with odds worse than QUARANTINE_ODDS_FLOOR (heavy favorites) or
# better than QUARANTINE_ODDS_CEILING (long-shots) are extreme alternate
# lines — NOT the standard DFS board.  Strip them to prevent the engine
# from hallucinating "fake" bets on lines that no DFS platform actually
# offers as standard plays.
QUARANTINE_ODDS_FLOOR   = -300   # Drop any line with odds < -300
QUARANTINE_ODDS_CEILING = +250   # Drop any line with odds > +250
_EQUILIBRIUM_ODDS       = -110   # The "Main Line" target (closest to this wins)

# Retry configuration for API calls with exponential backoff
# BEGINNER NOTE: Networks fail occasionally. Retrying with increasing delays
# handles temporary blips without hammering the server.
MAX_API_RETRIES = 3          # Max retry attempts before giving up
RETRY_BASE_DELAY_SECONDS = 1.0  # Base delay: 1s, 2s, 4s (exponential backoff)

# ============================================================
# END SECTION: Module-level constants
# ============================================================


# ============================================================
# SECTION: Retry Helper
# ============================================================

def _fetch_with_retry(url, headers=None, params=None, timeout=None):
    """
    Perform an HTTP GET request with exponential backoff retry on failure.

    Retries up to MAX_API_RETRIES times with delays of 1s, 2s, 4s on:
    - Connection errors
    - Timeout errors
    - HTTP 429 (rate limited) or 5xx server errors

    BEGINNER NOTE: Exponential backoff means we wait longer after each
    failure. This avoids overwhelming a struggling API server.

    Args:
        url (str): The URL to GET.
        headers (dict or None): HTTP headers.
        params (dict or None): URL query parameters.
        timeout (int or None): Request timeout in seconds. Uses REQUEST_TIMEOUT_SECONDS if None.

    Returns:
        requests.Response or None: Response on success, None on all retries failed.
    """
    if not REQUESTS_AVAILABLE:
        return None

    timeout = timeout or REQUEST_TIMEOUT_SECONDS
    headers = headers or _BASE_HEADERS.copy()
    last_exc = None

    for attempt in range(MAX_API_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)

            # Retry on rate limit or server error
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < MAX_API_RETRIES:
                    delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)  # Cap at 10s
                    _logger.warning(
                        f"HTTP {response.status_code} on attempt {attempt+1}/{MAX_API_RETRIES+1} "
                        f"for {url} — retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                return None  # All retries exhausted

            return response  # Success (even if status is 404, caller handles it)

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_API_RETRIES:
                delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)  # Cap at 10s
                _logger.warning(
                    f"Request error on attempt {attempt+1}/{MAX_API_RETRIES+1} "
                    f"for {url}: {exc} — retrying in {delay:.1f}s"
                )
                time.sleep(delay)
            else:
                _logger.error(f"All retries exhausted for {url}: {last_exc}")

    return None


# ============================================================
# END SECTION: Retry Helper
# ============================================================


# ============================================================
# SECTION: Helper — today's date string
# ============================================================

def _today_str():
    """Return today's date as an ISO string ('YYYY-MM-DD'), anchored to US/Eastern.

    NBA prop markets are defined in Eastern Time — a server in UTC would
    shift the date boundary, potentially mis-matching props to the wrong day.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    (EDT = UTC-4). Install ``tzdata`` for correct DST handling.
    """
    try:
        from zoneinfo import ZoneInfo
        _eastern = ZoneInfo("America/New_York")
    except ImportError:
        _eastern = datetime.timezone(datetime.timedelta(hours=-5))
    return datetime.datetime.now(_eastern).date().isoformat()


def _now_str():
    """Return the current UTC datetime as an ISO string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ============================================================
# END SECTION: Helper — today's date string
# ============================================================


# ============================================================
# SECTION: PrizePicks Data Mirror Fetcher
# ============================================================

def _parse_prizepicks_mirror_props(data, today, fetched_at):
    """
    Parse the flat-array format from the enkday/prizepicks-data-mirror.

    The mirror publishes a simpler structure than the PrizePicks live API:
    ``{"props": [{"player": "...", "stat": "...", "line": 20.5,
                  "oddsType": "standard"|"goblin"|"demon",
                  "teamCode": "LAL", "startDateCST": "2026-03-24", ...}, ...]}``

    PrizePicks goblin/demon line types:
      - "goblin"   : lower line (easier to hit, favorable to bettors)
      - "demon"    : higher line (harder to hit, unfavorable to bettors)
      - "standard" : the main board line

    Args:
        data (dict): Parsed JSON from the mirror endpoint.
        today (str): Today's date string ("YYYY-MM-DD"), used as fallback.
        fetched_at (str): ISO timestamp for when the data was fetched.

    Returns:
        list[dict]: Props in the standard internal format (see module header).
    """
    props = []
    for item in data.get("props", []):
        player_name = item.get("player", "").strip()
        if not player_name:
            continue

        raw_stat = item.get("stat", "")
        stat_type = normalize_stat_type(raw_stat, "PrizePicks")

        try:
            true_line = float(item.get("line", 0))
        except (ValueError, TypeError):
            continue
        if true_line <= 0:
            continue

        team = item.get("teamCode", item.get("Team", "")).strip().upper()
        game_date = item.get("startDateCST", today)

        # oddsType identifies goblin / demon / standard lines
        odds_type = str(item.get("oddsType", "standard")).lower()

        props.append({
            "player_name": player_name,
            "team": team,
            "stat_type": stat_type,
            "line": true_line,
            "platform": "PrizePicks",
            "game_date": game_date,
            "fetched_at": fetched_at,
            "over_odds": _DEFAULT_AMERICAN_ODDS,
            "under_odds": _DEFAULT_AMERICAN_ODDS,
            "odds_type": odds_type,
        })
    return props


def fetch_prizepicks_props_from_mirror(include_tomorrow=False):
    """
    Fetch NBA props from the enkday/prizepicks-data-mirror GitHub repository.

    The mirror publishes today's (and optionally tomorrow's) PrizePicks NBA
    props as raw JSON hosted on GitHub.  It includes goblin and demon line
    variants alongside standard lines.  Because it is served via GitHub's
    CDN, it is highly available and never rate-limited.

    Args:
        include_tomorrow (bool): Also fetch tomorrow's props. Default False.

    Returns:
        list[dict]: Props in the standard format (see module header), or []
                    if the mirror is unavailable.
    """
    if not REQUESTS_AVAILABLE:
        return []

    today = _today_str()
    fetched_at = _now_str()
    all_props = []

    urls = [PRIZEPICKS_MIRROR_TODAY_URL]
    if include_tomorrow:
        urls.append(PRIZEPICKS_MIRROR_TOMORROW_URL)

    for url in urls:
        cached = _cache_get(url)
        if cached is not None:
            data = cached
        else:
            response = _fetch_with_retry(url, headers=_BASE_HEADERS)
            if response is None:
                _logger.warning(f"[PrizePicks Mirror] Could not fetch {url}.")
                continue
            try:
                response.raise_for_status()
                data = response.json()
                _cache_set(url, data)
            except Exception as err:
                _logger.warning(f"[PrizePicks Mirror] Error reading {url}: {err}")
                continue

        parsed = _parse_prizepicks_mirror_props(data, today, fetched_at)
        all_props.extend(parsed)
        _logger.info(
            f"[PrizePicks Mirror] {url.split('/')[-1]}: {len(parsed)} props "
            f"({sum(1 for p in parsed if p.get('odds_type') == 'goblin')} goblin, "
            f"{sum(1 for p in parsed if p.get('odds_type') == 'demon')} demon)."
        )

    return all_props


def _parse_hierarchy_props(props_list, players_lookup, today, fetched_at):
    """
    Parse the normalized hierarchy props.json from the mirror.

    The hierarchy format uses propId, playerId, stat, line, teamCode,
    opponentCode — different from the flat per-sport JSON files.
    Only standard-odds props appear in the hierarchy (no goblin/demon).

    Args:
        props_list (list): Raw props from hierarchy/current_day/props.json.
        players_lookup (dict): playerId → player info dict.
        today (str): "YYYY-MM-DD" fallback date.
        fetched_at (str): ISO timestamp.

    Returns:
        list[dict]: Props in the standard internal format.
    """
    result = []
    for p in props_list:
        player_id = p.get("playerId", "")
        player_info = players_lookup.get(player_id, {})
        player_name = player_info.get("playerName", "").strip()

        if not player_name:
            player_name = p.get("player", "").strip()
        if not player_name:
            continue

        raw_stat = p.get("stat", "")
        stat_type = normalize_stat_type(raw_stat, "PrizePicks")

        try:
            line = float(p.get("line", 0))
        except (ValueError, TypeError):
            continue
        if line <= 0:
            continue

        team = p.get("teamCode", "").upper().replace("-", " ")
        opponent = p.get("opponentCode", "").upper().replace("-", " ")
        game_date = p.get("startDateCST", today)
        start_time = p.get("startTime", "")

        result.append({
            "player_name": player_name,
            "team": team,
            "stat_type": stat_type,
            "line": line,
            "platform": "PrizePicks",
            "game_date": game_date,
            "fetched_at": fetched_at,
            "over_odds": _DEFAULT_AMERICAN_ODDS,
            "under_odds": _DEFAULT_AMERICAN_ODDS,
            "odds_type": "standard",
            "opponent": opponent,
            "game_id": p.get("gameId", ""),
            "start_time": start_time,
            "source": "hierarchy",
        })
    return result


def fetch_prizepicks_hierarchy_data():
    """
    Fetch the full normalized NBA hierarchy from the mirror:
    games, teams, players, props, slates.

    Returns standard-only props (no goblin/demon) with rich metadata
    including game IDs, opponent, start time, and slate classification.

    Returns:
        dict: {
            "games": [...],
            "teams": [...],
            "players": {...},
            "props": [...],
            "slates": [...],
            "raw_props": [...],
        }
    """
    if not REQUESTS_AVAILABLE:
        return {}

    today = _today_str()
    fetched_at = _now_str()
    result = {}

    endpoints = {
        "games": PRIZEPICKS_HIERARCHY_GAMES_URL,
        "teams": PRIZEPICKS_HIERARCHY_TEAMS_URL,
        "players": PRIZEPICKS_HIERARCHY_PLAYERS_URL,
        "raw_props": PRIZEPICKS_HIERARCHY_PROPS_URL,
        "slates": PRIZEPICKS_HIERARCHY_SLATES_URL,
    }

    for key, url in endpoints.items():
        cached = _cache_get(url)
        if cached is not None:
            result[key] = cached
        else:
            response = _fetch_with_retry(url, headers=_BASE_HEADERS)
            if response is None:
                result[key] = [] if key != "players" else {}
                continue
            try:
                response.raise_for_status()
                data = response.json()
                _cache_set(url, data)
                result[key] = data
            except Exception as err:
                _logger.warning(f"[Hierarchy] Error fetching {key}: {err}")
                result[key] = [] if key != "players" else {}

    # Build players lookup
    players_lookup = {}
    players_data = result.get("players", [])
    if isinstance(players_data, list):
        for p in players_data:
            pid = p.get("playerId", "")
            if pid:
                players_lookup[pid] = p
    elif isinstance(players_data, dict):
        players_lookup = players_data

    raw_props = result.get("raw_props", [])
    if isinstance(raw_props, list):
        result["props"] = _parse_hierarchy_props(
            raw_props, players_lookup, today, fetched_at
        )
    else:
        result["props"] = []

    _logger.info(
        f"[Hierarchy] Loaded {len(result.get('games', []))} games, "
        f"{len(result['props'])} props, "
        f"{len(players_lookup)} players."
    )

    return result


NBA_TEAM_SLUGS = {
    "ATL": "atlanta-hawks",      "BOS": "boston-celtics",
    "BKN": "brooklyn-nets",      "CHA": "charlotte-hornets",
    "CHI": "chicago-bulls",      "CLE": "cleveland-cavaliers",
    "DAL": "dallas-mavericks",   "DEN": "denver-nuggets",
    "DET": "detroit-pistons",    "GSW": "golden-state-warriors",
    "HOU": "houston-rockets",    "IND": "indiana-pacers",
    "LAC": "la-clippers",        "LAL": "los-angeles-lakers",
    "MEM": "memphis-grizzlies",  "MIA": "miami-heat",
    "MIL": "milwaukee-bucks",    "MIN": "minnesota-timberwolves",
    "NOP": "new-orleans-pelicans", "NYK": "new-york-knicks",
    "OKC": "oklahoma-city-thunder", "ORL": "orlando-magic",
    "PHI": "philadelphia-76ers",    "PHX": "phoenix-suns",
    "POR": "portland-trail-blazers", "SAC": "sacramento-kings",
    "SAS": "san-antonio-spurs",     "TOR": "toronto-raptors",
    "UTA": "utah-jazz",             "WAS": "washington-wizards",
}


def fetch_team_props_from_mirror(team_abbrev):
    """
    Fetch all PrizePicks NBA props for a specific team.

    Args:
        team_abbrev (str): Standard 3-letter abbreviation, e.g. "LAL".

    Returns:
        list[dict]: Props in standard internal format, or [].
    """
    slug = NBA_TEAM_SLUGS.get(team_abbrev.upper())
    if not slug:
        _logger.warning(f"[Team Mirror] Unknown team abbreviation: {team_abbrev}")
        return []

    url = f"{PRIZEPICKS_MIRROR_TEAM_BASE_URL}/{slug}.json"

    cached = _cache_get(url)
    if cached is not None:
        data = cached
    else:
        response = _fetch_with_retry(url, headers=_BASE_HEADERS)
        if response is None:
            return []
        try:
            response.raise_for_status()
            data = response.json()
            _cache_set(url, data)
        except Exception:
            return []

    today = _today_str()
    fetched_at = _now_str()
    return _parse_prizepicks_mirror_props(data, today, fetched_at)


def fetch_archived_nba_props(date_str):
    """
    Fetch historical PrizePicks NBA props for a past date.

    Uses the mirror's archive at hierarchy/archive/YYYY-MM-DD/props.json.

    Args:
        date_str (str): "YYYY-MM-DD" format.

    Returns:
        list[dict]: Props in standard internal format, or [].
    """
    url = PRIZEPICKS_ARCHIVE_URL_TEMPLATE.format(date=date_str)

    cached = _cache_get(url)
    if cached is not None:
        data = cached
    else:
        response = _fetch_with_retry(url, headers=_BASE_HEADERS, timeout=10)
        if response is None:
            return []
        try:
            response.raise_for_status()
            data = response.json()
            _cache_set(url, data)
        except Exception:
            return []

    today = date_str
    fetched_at = _now_str()

    if isinstance(data, list):
        return _parse_hierarchy_props(data, {}, today, fetched_at)
    elif isinstance(data, dict) and "props" in data:
        return _parse_prizepicks_mirror_props(data, today, fetched_at)
    return []


def get_slate_grouped_props():
    """
    Fetch NBA props and group by slate (Early / Late).

    Returns:
        dict: {"Early": [prop_dicts], "Late": [prop_dicts]}
    """
    hierarchy = fetch_prizepicks_hierarchy_data()
    games = hierarchy.get("games", [])
    props = hierarchy.get("props", [])

    game_slate_map = {}
    for g in games:
        gid = g.get("gameId", "")
        slate = g.get("slate", "Late")
        game_slate_map[gid] = slate

    slates = {"Early": [], "Late": []}
    for p in props:
        game_id = p.get("game_id", "")
        slate = game_slate_map.get(game_id, "Late")
        slates[slate].append(p)

    return slates


def get_same_game_prop_groups():
    """
    Group all NBA props by gameId for same-game correlation analysis.

    Returns:
        dict: gameId → list[prop_dicts]
    """
    hierarchy = fetch_prizepicks_hierarchy_data()
    props = hierarchy.get("props", [])

    by_game = {}
    for p in props:
        gid = p.get("game_id", "unknown")
        by_game.setdefault(gid, []).append(p)

    return by_game


# ============================================================
# END SECTION: PrizePicks Data Mirror Fetcher
# ============================================================


# ============================================================
# SECTION: PrizePicks Fetcher
# ============================================================

def fetch_prizepicks_props(league="NBA"):
    """
    Fetch live player prop lines from PrizePicks.

    Hits the PrizePicks live API first (returns the full dataset including
    goblin/demon lines).  Falls back to the enkday data mirror if the live
    API is unreachable or rate-limited.

    Args:
        league (str): Sport league filter. Default "NBA".

    Returns:
        list[dict]: List of prop dicts (see module header for format).
                    Includes ``odds_type`` key: "goblin", "demon", or "standard".
                    Returns [] on any error.

    Example:
        props = fetch_prizepicks_props()
        # → [{"player_name": "LeBron James", "stat_type": "points",
        #      "line": 24.5, "odds_type": "standard",
        #      "platform": "PrizePicks", ...}, ...]
    """
    if not REQUESTS_AVAILABLE:
        _logger.warning("Warning: 'requests' library not installed. Cannot fetch PrizePicks props.")
        return []

    # ── 1. Try the PrizePicks live API first ─────────────────────────────────
    # The live API returns the FULL dataset including goblin/demon lines.
    # The mirror often strips them, so we prefer the live API.
    _logger.info(f"[PrizePicks] Fetching from live API {PRIZEPICKS_URL} ...")

    # PrizePicks requires Referer header in addition to the base headers
    headers = dict(_BASE_HEADERS)
    headers["Referer"] = "https://app.prizepicks.com/"

    _cached = _cache_get(PRIZEPICKS_URL)
    if _cached is not None:
        data = _cached
    else:
        try:
            # Use _fetch_with_retry for exponential backoff on 429/5xx
            response = _fetch_with_retry(
                PRIZEPICKS_URL,
                headers=headers,
                params={"league_id": 7, "per_page": 250, "single_stat": "true"},
                # BEGINNER NOTE: league_id=7 is NBA on PrizePicks.
                # per_page=250 gets more projections in one call.
            )
            if response is None:
                _logger.warning("[PrizePicks] All retries exhausted — falling back to mirror.")
                mirror_props = fetch_prizepicks_props_from_mirror()
                return mirror_props if mirror_props else []
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
            data = response.json()
            _cache_set(PRIZEPICKS_URL, data)

        except requests.exceptions.Timeout:
            _logger.warning("[PrizePicks] Request timed out — falling back to mirror.")
            mirror_props = fetch_prizepicks_props_from_mirror()
            return mirror_props if mirror_props else []
        except requests.exceptions.ConnectionError as err:
            _logger.warning(f"[PrizePicks] Connection error: {err} — falling back to mirror.")
            mirror_props = fetch_prizepicks_props_from_mirror()
            return mirror_props if mirror_props else []
        except Exception as err:
            _logger.error(f"[PrizePicks] Unexpected error: {err} — falling back to mirror.")
            mirror_props = fetch_prizepicks_props_from_mirror()
            return mirror_props if mirror_props else []

    # ── Parse the response ────────────────────────────────────
    # PrizePicks returns two arrays:
    #   "data"     → list of projection objects (each has stat_type, line_score, etc.)
    #   "included" → list of player objects referenced by projections

    projections = data.get("data", [])
    included = data.get("included", [])

    # Build a lookup dict: player_id → player info dict
    # BEGINNER NOTE: Each projection links to a player via "relationships.new_player.data.id"
    player_lookup = {}
    for item in included:
        if item.get("type") == "new_player":
            pid = item.get("id", "")
            attrs = item.get("attributes", {})
            player_lookup[pid] = {
                "name": attrs.get("name", ""),
                "team": attrs.get("team", attrs.get("team_name", "")),
            }

    # Build game lookup so each prop can carry its real game start date.
    # This is required to prevent future games from being mislabeled as "today".
    game_lookup = {}
    for item in included:
        if item.get("type") == "game":
            game_lookup[item.get("id", "")] = item.get("attributes", {}) or {}

    def _game_date_from_start(start_value):
        raw = str(start_value or "").strip()
        if not raw:
            return ""
        if "T" in raw:
            raw = raw.split("T", 1)[0]
        if " " in raw:
            raw = raw.split(" ", 1)[0]
        try:
            return datetime.date.fromisoformat(raw[:10]).isoformat()
        except ValueError:
            return ""

    # Parse each projection into our standard prop format
    props = []
    today = _today_str()
    fetched_at = _now_str()

    for proj in projections:
        # Only process PrizePicks "projection" type objects
        if proj.get("type") != "projection":
            continue

        attrs = proj.get("attributes", {})

        # Filter to NBA only
        league_name = attrs.get("league", attrs.get("league_name", "")).upper()
        if league.upper() not in league_name and league_name != "":
            # Some projections don't have league on the projection itself;
            # we'll include them and rely on the player lookup for filtering
            if league_name:
                continue

        # Get the player id from the relationship link
        relationships = proj.get("relationships", {})
        player_rel = relationships.get("new_player", {}).get("data", {})
        player_id = player_rel.get("id", "")
        player_info = player_lookup.get(player_id, {})

        player_name = player_info.get("name", attrs.get("description", "")).strip()
        team = player_info.get("team", "").strip().upper()

        if not player_name:
            continue  # Skip projections with no player name

        # Normalize the stat type to our internal key
        raw_stat = attrs.get("stat_type", "")
        stat_type = normalize_stat_type(raw_stat, "PrizePicks")

        # Extract the sportsbook's true Over/Under projection line.
        # PrizePicks stores it under "line_score"; fall back to
        # "stat_projection" or "points" if present.
        try:
            _raw_line = attrs.get("line_score",
                                  attrs.get("stat_projection",
                                            attrs.get("points")))
            if _raw_line is None:
                continue  # No projection line available — silently discard
            true_line = float(_raw_line)
        except (ValueError, TypeError, KeyError):
            continue  # Skip if line is not a valid number

        if true_line <= 0:
            continue  # Skip invalid lines

        # Capture the PrizePicks odds_type: "standard", "goblin", or "demon"
        # Goblin = lower/easier line; Demon = higher/harder line.
        odds_type = str(attrs.get("odds_type", "standard")).lower()

        # Prefer relationship game.start_time; fallback to projection start_time.
        _game_rel = relationships.get("game", {}).get("data", {})
        _game_rel_id = _game_rel.get("id", "") if isinstance(_game_rel, dict) else ""
        _game_start = (game_lookup.get(_game_rel_id, {}) or {}).get("start_time")
        _proj_start = attrs.get("start_time")
        _resolved_game_date = _game_date_from_start(_game_start) or _game_date_from_start(_proj_start) or today

        props.append({
            "player_name": player_name,
            "team": team,
            "stat_type": stat_type,
            "line": true_line,
            "platform": "PrizePicks",
            "game_date": _resolved_game_date,
            "start_time": _game_start or _proj_start or "",
            "fetched_at": fetched_at,
            "over_odds": attrs.get("price", attrs.get("over_price", _DEFAULT_AMERICAN_ODDS)),
            "under_odds": attrs.get("under_price", _DEFAULT_AMERICAN_ODDS),
            "odds_type": odds_type,
        })

    _logger.info(f"[PrizePicks] Fetched {len(props)} NBA props from live API.")
    return props

# ============================================================
# END SECTION: PrizePicks Fetcher
# ============================================================


# ============================================================
# SECTION: Underdog Fantasy Fetcher
# ============================================================

def fetch_underdog_props(league="NBA"):
    """
    Fetch live player prop lines from Underdog Fantasy.

    Uses Underdog's public JSON API — no API key required.
    Filters to NBA only and normalizes stat types.

    Args:
        league (str): Sport league filter. Default "NBA".

    Returns:
        list[dict]: List of prop dicts in standard format.
                    Returns [] on any error.

    Example:
        props = fetch_underdog_props()
        # → [{"player_name": "Stephen Curry", "stat_type": "threes",
        #      "line": 3.5, "platform": "Underdog", ...}, ...]
    """
    if not REQUESTS_AVAILABLE:
        _logger.warning("Warning: 'requests' library not installed. Cannot fetch Underdog props.")
        return []

    _logger.info(f"[Underdog] Fetching NBA props from {UNDERDOG_URL} ...")

    _cached_ud = _cache_get(UNDERDOG_URL)
    if _cached_ud is not None:
        data = _cached_ud
    else:
        try:
            # Use _fetch_with_retry for exponential backoff on 429/5xx
            _ud_headers = get_underdog_headers() if _HAS_PLATFORM_HEADERS else _BASE_HEADERS
            response = _fetch_with_retry(
                UNDERDOG_URL,
                headers=_ud_headers,
            )
            if response is None:
                _logger.warning("[Underdog] All retries exhausted. Skipping.")
                return []
            response.raise_for_status()
            data = response.json()
            _cache_set(UNDERDOG_URL, data)

        except requests.exceptions.Timeout:
            _logger.warning("[Underdog] Request timed out. Skipping.")
            return []
        except requests.exceptions.ConnectionError as err:
            _logger.warning(f"[Underdog] Connection error: {err}. Skipping.")
            return []
        except Exception as err:
            _logger.error(f"[Underdog] Unexpected error: {err}. Skipping.")
            return []

    # ── Parse the response ────────────────────────────────────
    # Underdog returns a flat list in "over_under_lines"
    # Each entry has: title (player name), display_stat, stat_value,
    #                 sport_id, etc.
    # NOTE: sport_id may be a numeric ID (e.g. 7 for NBA) or a string.

    lines = data.get("over_under_lines", [])

    # Also build a player lookup from "appearances" or "players" if present
    # (some Underdog responses include more player details)
    appearances = {}
    for ap in data.get("appearances", []):
        ap_id = ap.get("id", "")
        appearances[ap_id] = ap

    # Numeric sport_id mapping — Underdog uses integer IDs in some API
    # versions instead of string sport names.
    _SPORT_ID_MAP = {7: "NBA", 2: "NFL", 3: "MLB", 4: "NHL", 10: "WNBA"}

    props = []
    today = _today_str()
    fetched_at = _now_str()

    for line_item in lines:
        # Underdog uses "sport_id" or similar for league filtering
        # Common values: "NBA", "nba", or numeric IDs (e.g. 7)
        raw_sport_id = line_item.get("sport_id", line_item.get("sport", ""))
        if isinstance(raw_sport_id, (int, float)):
            sport_id = _SPORT_ID_MAP.get(int(raw_sport_id), str(raw_sport_id)).upper()
        else:
            sport_id = str(raw_sport_id).upper()
        if league.upper() not in sport_id and sport_id:
            continue  # Skip non-NBA lines

        # Player name may be directly on line_item, or nested under
        # "over_under" (newer API versions nest the data).
        over_under = line_item.get("over_under", {}) or {}
        player_name = (
            line_item.get("title", "").strip()
            or over_under.get("title", "").strip()
        )

        # Try to get team from the appearance object
        ap_id = (
            line_item.get("appearance_id", "")
            or over_under.get("appearance_id", "")
        )
        ap_data = appearances.get(ap_id, {})
        team = ap_data.get("team_abbreviation", ap_data.get("team", "")).strip().upper()

        if not player_name:
            # Last resort: try the appearance lookup by name
            if ap_data:
                player_name = ap_data.get("title", ap_data.get("display_name", "")).strip()
            if not player_name:
                continue  # Skip entries with no player name

        # Normalize stat type — check nested over_under as well
        appearance_stat = over_under.get("appearance_stat", {}) or {}
        raw_stat = (
            line_item.get("display_stat",
                          line_item.get("stat_type", ""))
            or appearance_stat.get("display_stat",
                                   appearance_stat.get("stat_type", ""))
        )
        stat_type = normalize_stat_type(raw_stat, "Underdog")

        # Extract the sportsbook's true Over/Under projection line.
        # Underdog uses "stat_value" primarily; fall back to "o_u_value"
        # or "stat_projection" if present.
        try:
            _raw_line = line_item.get("stat_value",
                                      line_item.get("o_u_value",
                                                    line_item.get("stat_projection")))
            if _raw_line is None:
                continue  # No projection line available — silently discard
            true_line = float(_raw_line)
        except (ValueError, TypeError, KeyError):
            continue  # Skip invalid lines

        if true_line <= 0:
            continue

        props.append({
            "player_name": player_name,
            "team": team,
            "stat_type": stat_type,
            "line": true_line,
            "platform": "Underdog",
            "game_date": today,
            "fetched_at": fetched_at,
            "over_odds": line_item.get("price", line_item.get("over_price", _DEFAULT_AMERICAN_ODDS)),
            "under_odds": line_item.get("under_price", _DEFAULT_AMERICAN_ODDS),
        })

    _logger.info(f"[Underdog] Fetched {len(props)} NBA props.")
    return props

# ============================================================
# END SECTION: Underdog Fantasy Fetcher
# ============================================================


# ============================================================
# SECTION: DraftKings (via The Odds API) Fetcher
# ============================================================

def fetch_draftkings_props(api_key=None):
    """
    Fetch DraftKings Pick6 player prop lines via The Odds API.

    The Odds API aggregates DraftKings player props.
    Free tier: 500 requests/month. Get your key at https://the-odds-api.com

    The API key is looked up in this order:
      1. api_key argument (passed directly)
      2. st.session_state["odds_api_key"] (set on Settings page)
      3. ODDS_API_KEY environment variable

    Args:
        api_key (str, optional): The Odds API key. If None, reads from
            session state or environment variable.

    Returns:
        list[dict]: List of prop dicts in standard format.
                    Returns [] if no API key or on any error.

    Example:
        props = fetch_draftkings_props(api_key="your_key_here")
        # → [{"player_name": "Giannis Antetokounmpo", "stat_type": "points",
        #      "line": 28.5, "platform": "DraftKings", ...}, ...]
    """
    if not REQUESTS_AVAILABLE:
        _logger.warning("Warning: 'requests' library not installed. Cannot fetch DraftKings props.")
        return []

    # ── Resolve API key ────────────────────────────────────────
    # Try session state first (set via Settings page)
    if api_key is None:
        try:
            import streamlit as st
            api_key = st.session_state.get("odds_api_key", "").strip() or None
        except Exception:
            pass  # streamlit may not be available in some contexts

    # Try environment variable as final fallback
    if not api_key:
        api_key = os.environ.get("ODDS_API_KEY", "").strip() or None

    if not api_key:
        _logger.warning(
            "[DraftKings] No Odds API key configured. "
            "Add your key on the Settings page or set ODDS_API_KEY env var. "
            "Get a free key at https://the-odds-api.com"
        )
        return []

    _logger.info("[DraftKings] Fetching NBA events via The Odds API ...")

    # ── Step 1: Get list of today's NBA events ─────────────────
    events_url = f"{ODDS_API_BASE_URL}/sports/basketball_nba/events"
    try:
        # Use _fetch_with_retry for exponential backoff on 429/5xx
        _dk_headers = get_odds_api_headers() if _HAS_PLATFORM_HEADERS else _BASE_HEADERS
        events_resp = _fetch_with_retry(
            events_url,
            headers=_dk_headers,
            params={"apiKey": api_key},
        )
        if events_resp is None:
            _logger.warning("[DraftKings] All retries exhausted for events. Skipping.")
            return []
        events_resp.raise_for_status()
        events = events_resp.json()

    except requests.exceptions.HTTPError as err:
        # err.response is the Response object that raise_for_status() raised from
        status_code = err.response.status_code if err.response is not None else 0
        if status_code == 429:
            _logger.warning("[DraftKings] Rate limited (429). Backing off.")
            if _RATE_LIMITER_AVAILABLE and _platform_rate_limiter is not None:
                _platform_rate_limiter.handle_429_response(retry_after=60)
        elif status_code == 401:
            _logger.warning("[DraftKings] Invalid API key. Check your Odds API key on the Settings page.")
        elif status_code == 422:
            _logger.warning("[DraftKings] API quota exceeded for the month.")
        else:
            _logger.error(f"[DraftKings] HTTP error fetching events: {err}")
        return []
    except Exception as err:
        _logger.error(f"[DraftKings] Error fetching events: {err}. Skipping.")
        return []

    if not events:
        _logger.info("[DraftKings] No NBA events found today.")
        return []

    _logger.info(f"[DraftKings] Found {len(events)} NBA events. Fetching player props...")

    # ── Step 2: Fetch player props for each event ──────────────
    # BEGINNER NOTE: The Odds API charges per request, so we request
    # all common prop markets in one call per event to minimize API usage.
    # Markets: player_points, player_rebounds, player_assists, player_threes,
    #          player_blocks, player_steals, player_turnovers
    MARKETS = ",".join([
        "player_points",
        "player_rebounds",
        "player_assists",
        "player_threes",
        "player_blocks",
        "player_steals",
        "player_turnovers",
        "player_points_rebounds_assists",
        "player_points_rebounds",
        "player_points_assists",
    ])

    # Internal mapping from Odds API market keys → our internal stat types
    _MARKET_TO_STAT = {
        "player_points": "points",
        "player_rebounds": "rebounds",
        "player_assists": "assists",
        "player_threes": "threes",
        "player_blocks": "blocks",
        "player_steals": "steals",
        "player_turnovers": "turnovers",
        "player_points_rebounds_assists": "points_rebounds_assists",
        "player_points_rebounds": "points_rebounds",
        "player_points_assists": "points_assists",
    }

    props = []
    today = _today_str()
    fetched_at = _now_str()

    for event in events:
        event_id = event.get("id", "")
        if not event_id:
            continue

        # Add a short delay / rate limiting between event requests
        if _RATE_LIMITER_AVAILABLE and _platform_rate_limiter is not None:
            _platform_rate_limiter.acquire()
        else:
            time.sleep(0.5)

        props_url = (
            f"{ODDS_API_BASE_URL}/sports/basketball_nba/events/{event_id}/odds"
        )
        _cached_dk = _cache_get(props_url)
        if _cached_dk is not None:
            event_data = _cached_dk
        else:
            try:
                # Use _fetch_with_retry for exponential backoff on 429/5xx
                _dk_h = get_odds_api_headers() if _HAS_PLATFORM_HEADERS else _BASE_HEADERS
                props_resp = _fetch_with_retry(
                    props_url,
                    headers=_dk_h,
                    params={
                        "apiKey": api_key,
                        "regions": "us",
                        "markets": MARKETS,
                        "bookmakers": "draftkings",
                        "oddsFormat": "american",
                    },
                )
                if props_resp is None:
                    _logger.warning(f"[DraftKings] All retries exhausted for event {event_id}. Skipping.")
                    continue
                props_resp.raise_for_status()
                event_data = props_resp.json()
                _cache_set(props_url, event_data)

            except requests.exceptions.HTTPError as err:
                # err.response is the Response object that raise_for_status() raised from
                if err.response is not None and err.response.status_code == 422:
                    _logger.warning("[DraftKings] API quota exceeded. Stopping early.")
                    break
                _logger.error(f"[DraftKings] HTTP error for event {event_id}: {err}. Skipping.")
                continue
            except Exception as err:
                _logger.error(f"[DraftKings] Error for event {event_id}: {err}. Skipping.")
                continue

        # ── Parse bookmaker data ───────────────────────────────
        for bookmaker in event_data.get("bookmakers", []):
            bk_key = bookmaker.get("key", "")
            if not bk_key.startswith("draftkings"):
                continue

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                stat_type = _MARKET_TO_STAT.get(market_key)
                if not stat_type:
                    continue  # Skip markets we don't track

                # ── Pair Over and Under outcomes by player + line ──
                # The Odds API returns separate outcome objects for "Over" and
                # "Under". We first index every outcome by (player_name, line),
                # then combine them so under_odds comes from the real Under
                # outcome price instead of always falling back to _DEFAULT_AMERICAN_ODDS.
                over_map = {}   # (player_name, line) → over_price
                under_map = {}  # (player_name, line) → under_price

                for outcome in market.get("outcomes", []):
                    # The Odds API player props have:
                    #   name        → player name (e.g., "LeBron James")
                    #   point       → the line value (e.g., 24.5)
                    #   description → "Over" or "Under"
                    #   price       → American odds for this side

                    player_name = outcome.get("name", "").strip()
                    if not player_name:
                        continue

                    # Extract the sportsbook's true projection line.
                    # The Odds API uses "point" for the prop line value.
                    try:
                        _raw_line = outcome.get("point")
                        if _raw_line is None:
                            continue  # No projection line — silently discard
                        true_line = float(_raw_line)
                    except (ValueError, TypeError, KeyError):
                        continue

                    if true_line <= 0:
                        continue

                    direction = outcome.get("description", "").lower()
                    price = outcome.get("price", _DEFAULT_AMERICAN_ODDS)
                    key = (player_name, true_line)

                    if direction == "over":
                        over_map[key] = price
                    elif direction == "under":
                        under_map[key] = price

                # Build one prop dict per Over outcome, attaching the matching Under price
                for (player_name, true_line), over_price in over_map.items():
                    _has_under = (player_name, true_line) in under_map
                    under_price = under_map.get((player_name, true_line), _DEFAULT_AMERICAN_ODDS)
                    if not _has_under:
                        _logger.debug(
                            f"[DraftKings] No Under outcome found for {player_name} {stat_type} {true_line} "
                            f"— defaulting under_odds to {_DEFAULT_AMERICAN_ODDS}"
                        )
                    props.append({
                        "player_name": player_name,
                        "team": "",  # Odds API doesn't include team in player props
                        "stat_type": stat_type,
                        "line": true_line,
                        "platform": "DraftKings",
                        "game_date": today,
                        "fetched_at": fetched_at,
                        "over_odds": over_price,
                        "under_odds": under_price,
                    })

    if not props and events:
        _logger.info("[DraftKings] 0 props despite %d events — possible API format change or no player prop markets available", len(events))
    _logger.info(f"[DraftKings] Fetched {len(props)} NBA props.")
    return props

# ============================================================
# END SECTION: DraftKings Fetcher
# ============================================================


# ============================================================
# SECTION: Master Fetch Function
# ============================================================

def fetch_all_platform_props(
    include_prizepicks=True,
    include_underdog=True,
    include_draftkings=True,
    odds_api_key=None,
    progress_callback=None,
):
    """
    Fetch live prop lines from all enabled platforms.

    Calls each enabled platform fetcher in sequence, aggregates results,
    and stamps each prop with a fetched_at timestamp. If one platform
    fails, the others still run (graceful degradation).

    Args:
        include_prizepicks (bool): Fetch from PrizePicks. Default True.
        include_underdog (bool): Fetch from Underdog Fantasy. Default True.
        include_draftkings (bool): Fetch from DraftKings via The Odds API. Default True.
        odds_api_key (str, optional): The Odds API key for DraftKings. If None,
            reads from session state or ODDS_API_KEY env var.
        progress_callback (callable, optional): Called as
            progress_callback(current, total, message) to update a UI progress bar.

    Returns:
        list[dict]: All fetched props from all enabled platforms,
                    each with a "fetched_at" timestamp.

    Example:
        props = fetch_all_platform_props()
        # → 100+ props from PrizePicks + Underdog + DraftKings combined
    """
    all_props = []
    platforms_to_fetch = []

    # Build list of enabled platforms for progress tracking
    if include_prizepicks:
        platforms_to_fetch.append("PrizePicks")
    if include_underdog:
        platforms_to_fetch.append("Underdog")
    if include_draftkings:
        platforms_to_fetch.append("DraftKings")

    total_steps = len(platforms_to_fetch)
    current_step = 0

    # ── PrizePicks ─────────────────────────────────────────────
    if include_prizepicks:
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, "Fetching PrizePicks props...")
        try:
            pp_props = fetch_prizepicks_props()
            all_props.extend(pp_props)
            _logger.info(f"[Master] PrizePicks: {len(pp_props)} props added.")
        except Exception as err:
            _logger.error(f"[Master] PrizePicks fetch failed: {err}")

        # Be polite to APIs — rate limit before the next call
        if include_underdog or include_draftkings:
            if _RATE_LIMITER_AVAILABLE and _platform_rate_limiter is not None:
                _platform_rate_limiter.acquire()
            else:
                time.sleep(API_DELAY_SECONDS)

    # ── Underdog Fantasy ───────────────────────────────────────
    if include_underdog:
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, "Fetching Underdog Fantasy props...")
        try:
            ud_props = fetch_underdog_props()
            all_props.extend(ud_props)
            _logger.info(f"[Master] Underdog: {len(ud_props)} props added.")
        except Exception as err:
            _logger.error(f"[Master] Underdog fetch failed: {err}")

        # Rate limiting delay
        if include_draftkings:
            if _RATE_LIMITER_AVAILABLE and _platform_rate_limiter is not None:
                _platform_rate_limiter.acquire()
            else:
                time.sleep(API_DELAY_SECONDS)

    # ── DraftKings (via The Odds API) ──────────────────────────
    if include_draftkings:
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, "Fetching DraftKings props...")
        try:
            dk_props = fetch_draftkings_props(api_key=odds_api_key)
            all_props.extend(dk_props)
            _logger.info(f"[Master] DraftKings: {len(dk_props)} props added.")
        except Exception as err:
            _logger.error(f"[Master] DraftKings fetch failed: {err}")

    if progress_callback:
        progress_callback(total_steps, total_steps, f"Done! {len(all_props)} props fetched.")

    # ── Alt-line enrichment — no hard cap on raw intake ──────────
    # The pipeline no longer caps the number of fetched props at the
    # ingestion stage.  The 500-bet minimum-output quota is enforced
    # downstream in the analysis loop so that the engine processes as
    # many raw props as necessary until the target is reached.

    # ── Drop props with stat types the platform cannot verify ────
    _pre_filter_count = len(all_props)
    all_props = [
        p for p in all_props
        if str(p.get("stat_type", "")).lower() in VALID_STAT_TYPES
    ]
    _dropped = _pre_filter_count - len(all_props)
    if _dropped:
        _logger.info(f"[Master] Filtered out {_dropped} unverifiable props (stat_type not in VALID_STAT_TYPES)")

    # NOTE: Goblin / Demon props are now preserved so the Prop Scanner
    # can display them.  Downstream analysis pages use is_unbettable_line()
    # to exclude them from scoring / picks independently.

    # ── Enrich with standard_line ─────────────────────────────────
    # Stamp each prop with the standard_line (median line for its group).
    all_props = parse_alt_lines_from_platform_props(all_props)

    _logger.info(f"[Master] Total props fetched: {len(all_props)}")
    return all_props

# ============================================================
# END SECTION: Master Fetch Function
# ============================================================


# ============================================================
# SECTION: Asynchronous Multi-Platform Fetcher
# ============================================================

# Concurrency limiter — prevents IP rate-limiting while maintaining speed.
_ASYNC_SEMAPHORE_LIMIT = 5


async def _async_fetch_json(session, url, headers=None, params=None):
    """
    Fetch JSON from a URL using an aiohttp session with retry logic.

    Args:
        session (aiohttp.ClientSession): The shared HTTP session.
        url (str): Target URL.
        headers (dict, optional): HTTP headers.
        params (dict, optional): URL query parameters.

    Returns:
        dict or None: Parsed JSON on success, None on failure.
    """
    _headers = headers or dict(_BASE_HEADERS)
    for attempt in range(MAX_API_RETRIES + 1):
        try:
            async with session.get(
                url, headers=_headers, params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status == 429 or resp.status >= 500:
                    if attempt < MAX_API_RETRIES:
                        delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)
                        _logger.warning(
                            f"[Async] HTTP {resp.status} on attempt {attempt+1} "
                            f"for {url} — retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    return None
                resp.raise_for_status()
                return await resp.json()
        except Exception as exc:
            if attempt < MAX_API_RETRIES:
                delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)
                _logger.warning(
                    f"[Async] Error on attempt {attempt+1} for {url}: {exc} "
                    f"— retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
            else:
                _logger.error(f"[Async] All retries exhausted for {url}: {exc}")
    return None


async def _async_fetch_prizepicks(session, semaphore):
    """Fetch PrizePicks props asynchronously.

    Hits the PrizePicks live API first (full dataset with goblin/demon).
    Falls back to the enkday data mirror if the live API is unreachable.
    """
    # ── 1. Try PrizePicks live API first (includes goblin/demon) ─────────────
    async with semaphore:
        headers = dict(_BASE_HEADERS)
        headers["Referer"] = "https://app.prizepicks.com/"
        params = {"league_id": 7, "per_page": 250, "single_stat": "true"}

        data = await _async_fetch_json(session, PRIZEPICKS_URL, headers=headers, params=params)
        if not data:
            # ── 2. Fall back to mirror ───────────────────────────────────────
            _logger.info("[Async-PrizePicks] Live API unavailable — falling back to mirror.")
            mirror_props = await asyncio.get_event_loop().run_in_executor(
                None, fetch_prizepicks_props_from_mirror
            )
            return mirror_props if mirror_props else []

        projections = data.get("data", [])
        included = data.get("included", [])
        player_lookup = {}
        for item in included:
            if item.get("type") == "new_player":
                pid = item.get("id", "")
                attrs = item.get("attributes", {})
                player_lookup[pid] = {
                    "name": attrs.get("name", ""),
                    "team": attrs.get("team", attrs.get("team_name", "")),
                }

        props = []
        today = _today_str()
        fetched_at = _now_str()
        for proj in projections:
            if proj.get("type") != "projection":
                continue
            attrs = proj.get("attributes", {})
            league_name = attrs.get("league", attrs.get("league_name", "")).upper()
            if "NBA" not in league_name and league_name:
                continue
            relationships = proj.get("relationships", {})
            player_rel = relationships.get("new_player", {}).get("data", {})
            player_id = player_rel.get("id", "")
            player_info = player_lookup.get(player_id, {})
            player_name = player_info.get("name", attrs.get("description", "")).strip()
            team = player_info.get("team", "").strip().upper()
            if not player_name:
                continue
            raw_stat = attrs.get("stat_type", "")
            stat_type = normalize_stat_type(raw_stat, "PrizePicks")
            # TRUE LINE KILL SWITCH: extract line_score → fallback chain
            try:
                _raw_line = attrs.get("line_score",
                                      attrs.get("stat_projection",
                                                attrs.get("points")))
                if _raw_line is None:
                    continue  # KILL SWITCH: no line → discard
                true_line = float(_raw_line)
            except (ValueError, TypeError, KeyError):
                continue  # KILL SWITCH: invalid line → discard
            if true_line <= 0:
                continue  # KILL SWITCH: non-positive line → discard
            # Capture the PrizePicks odds_type: "standard", "goblin", or "demon"
            odds_type = str(attrs.get("odds_type", "standard")).lower()
            props.append({
                "player_name": player_name, "team": team,
                "stat_type": stat_type, "line": true_line,
                "platform": "PrizePicks", "game_date": today,
                "fetched_at": fetched_at,
                "over_odds": attrs.get("price", attrs.get("over_price", _DEFAULT_AMERICAN_ODDS)),
                "under_odds": attrs.get("under_price", _DEFAULT_AMERICAN_ODDS),
                "odds_type": odds_type,
            })
        _logger.info(f"[Async-PrizePicks] Fetched {len(props)} NBA props from live API.")
        return props


async def _async_fetch_underdog(session, semaphore):
    """Fetch Underdog Fantasy props asynchronously."""
    async with semaphore:
        _ud_h = get_underdog_headers() if _HAS_PLATFORM_HEADERS else None
        data = await _async_fetch_json(session, UNDERDOG_URL, headers=_ud_h)
        if not data:
            return []

        lines = data.get("over_under_lines", [])
        appearances = {}
        for ap in data.get("appearances", []):
            appearances[ap.get("id", "")] = ap

        # Numeric sport_id mapping (same as sync version)
        _SPORT_ID_MAP = {7: "NBA", 2: "NFL", 3: "MLB", 4: "NHL", 10: "WNBA"}

        props = []
        today = _today_str()
        fetched_at = _now_str()
        for line_item in lines:
            raw_sport_id = line_item.get("sport_id", line_item.get("sport", ""))
            if isinstance(raw_sport_id, (int, float)):
                sport_id = _SPORT_ID_MAP.get(int(raw_sport_id), str(raw_sport_id)).upper()
            else:
                sport_id = str(raw_sport_id).upper()
            if "NBA" not in sport_id and sport_id:
                continue
            over_under = line_item.get("over_under", {}) or {}
            player_name = (
                line_item.get("title", "").strip()
                or over_under.get("title", "").strip()
            )
            ap_id = (
                line_item.get("appearance_id", "")
                or over_under.get("appearance_id", "")
            )
            ap_data = appearances.get(ap_id, {})
            team = ap_data.get("team_abbreviation", ap_data.get("team", "")).strip().upper()
            if not player_name:
                if ap_data:
                    player_name = ap_data.get("title", ap_data.get("display_name", "")).strip()
                if not player_name:
                    continue
            appearance_stat = over_under.get("appearance_stat", {}) or {}
            raw_stat = (
                line_item.get("display_stat", line_item.get("stat_type", ""))
                or appearance_stat.get("display_stat", appearance_stat.get("stat_type", ""))
            )
            stat_type = normalize_stat_type(raw_stat, "Underdog")
            # TRUE LINE KILL SWITCH: stat_value → fallback chain
            try:
                _raw_line = line_item.get("stat_value",
                                          line_item.get("o_u_value",
                                                        line_item.get("stat_projection")))
                if _raw_line is None:
                    continue  # KILL SWITCH
                true_line = float(_raw_line)
            except (ValueError, TypeError, KeyError):
                continue  # KILL SWITCH
            if true_line <= 0:
                continue  # KILL SWITCH
            props.append({
                "player_name": player_name, "team": team,
                "stat_type": stat_type, "line": true_line,
                "platform": "Underdog", "game_date": today,
                "fetched_at": fetched_at,
                "over_odds": line_item.get("price", line_item.get("over_price", _DEFAULT_AMERICAN_ODDS)),
                "under_odds": line_item.get("under_price", _DEFAULT_AMERICAN_ODDS),
            })
        _logger.info(f"[Async-Underdog] Fetched {len(props)} NBA props.")
        return props


async def _async_fetch_draftkings(session, semaphore, api_key=None):
    """Fetch DraftKings Pick6 props asynchronously via The Odds API."""
    if not api_key:
        try:
            import streamlit as st
            api_key = st.session_state.get("odds_api_key", "").strip() or None
        except Exception:
            pass
    if not api_key:
        api_key = os.environ.get("ODDS_API_KEY", "").strip() or None
    if not api_key:
        _logger.warning("[Async-DraftKings] No Odds API key configured.")
        return []

    _dk_async_h = get_odds_api_headers() if _HAS_PLATFORM_HEADERS else None
    async with semaphore:
        events_url = f"{ODDS_API_BASE_URL}/sports/basketball_nba/events"
        events = await _async_fetch_json(
            session, events_url, headers=_dk_async_h, params={"apiKey": api_key}
        )
        if not events:
            return []

    MARKETS = ",".join([
        "player_points", "player_rebounds", "player_assists",
        "player_threes", "player_blocks", "player_steals",
        "player_turnovers", "player_points_rebounds_assists",
        "player_points_rebounds", "player_points_assists",
    ])
    _MARKET_TO_STAT = {
        "player_points": "points", "player_rebounds": "rebounds",
        "player_assists": "assists", "player_threes": "threes",
        "player_blocks": "blocks", "player_steals": "steals",
        "player_turnovers": "turnovers",
        "player_points_rebounds_assists": "points_rebounds_assists",
        "player_points_rebounds": "points_rebounds",
        "player_points_assists": "points_assists",
    }

    props = []
    today = _today_str()
    fetched_at = _now_str()

    for event in events:
        event_id = event.get("id", "")
        if not event_id:
            continue
        async with semaphore:
            props_url = (
                f"{ODDS_API_BASE_URL}/sports/basketball_nba/events/{event_id}/odds"
            )
            event_data = await _async_fetch_json(
                session, props_url, headers=_dk_async_h,
                params={
                    "apiKey": api_key, "regions": "us",
                    "markets": MARKETS, "bookmakers": "draftkings",
                    "oddsFormat": "american",
                },
            )
            if not event_data:
                continue

        for bookmaker in event_data.get("bookmakers", []):
            bk_key = bookmaker.get("key", "")
            if not bk_key.startswith("draftkings"):
                continue
            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                stat_type = _MARKET_TO_STAT.get(market_key)
                if not stat_type:
                    continue
                over_map = {}
                under_map = {}
                for outcome in market.get("outcomes", []):
                    player_name = outcome.get("name", "").strip()
                    if not player_name:
                        continue
                    # TRUE LINE KILL SWITCH: point → validate
                    try:
                        _raw_line = outcome.get("point")
                        if _raw_line is None:
                            continue  # KILL SWITCH
                        true_line = float(_raw_line)
                    except (ValueError, TypeError, KeyError):
                        continue  # KILL SWITCH
                    if true_line <= 0:
                        continue  # KILL SWITCH
                    direction = outcome.get("description", "").lower()
                    price = outcome.get("price", _DEFAULT_AMERICAN_ODDS)
                    key = (player_name, true_line)
                    if direction == "over":
                        over_map[key] = price
                    elif direction == "under":
                        under_map[key] = price
                for (player_name, true_line), over_price in over_map.items():
                    under_price = under_map.get(
                        (player_name, true_line), _DEFAULT_AMERICAN_ODDS
                    )
                    props.append({
                        "player_name": player_name, "team": "",
                        "stat_type": stat_type, "line": true_line,
                        "platform": "DraftKings", "game_date": today,
                        "fetched_at": fetched_at,
                        "over_odds": over_price, "under_odds": under_price,
                    })

    _logger.info(f"[Async-DraftKings] Fetched {len(props)} NBA props.")
    return props


async def fetch_all_platforms_async(
    include_prizepicks=True,
    include_underdog=True,
    include_draftkings=True,
    odds_api_key=None,
):
    """
    Fetch live prop lines from all enabled platforms concurrently
    using aiohttp and asyncio.

    Uses a Semaphore(5) to prevent IP rate-limiting while maintaining
    maximum speed. PrizePicks data comes from the enkday data mirror
    (includes goblin/demon lines) with live API as fallback.

    Args:
        include_prizepicks (bool): Fetch from PrizePicks. Default True.
        include_underdog (bool): Fetch from Underdog Fantasy. Default True.
        include_draftkings (bool): Fetch from DraftKings. Default True.
        odds_api_key (str, optional): The Odds API key for DraftKings.

    Returns:
        list[dict]: All fetched props from enabled platforms.
    """
    if not AIOHTTP_AVAILABLE:
        _logger.warning(
            "[Async] aiohttp not available, falling back to synchronous fetch."
        )
        return fetch_all_platform_props(
            include_prizepicks=include_prizepicks,
            include_underdog=include_underdog,
            include_draftkings=include_draftkings,
            odds_api_key=odds_api_key,
        )

    semaphore = asyncio.Semaphore(_ASYNC_SEMAPHORE_LIMIT)
    tasks = []

    async with aiohttp.ClientSession() as session:
        if include_prizepicks:
            tasks.append(_async_fetch_prizepicks(session, semaphore))
        if include_underdog:
            tasks.append(_async_fetch_underdog(session, semaphore))
        if include_draftkings:
            tasks.append(_async_fetch_draftkings(session, semaphore, api_key=odds_api_key))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_props = []
    for result in results:
        if isinstance(result, Exception):
            _logger.error(f"[Async] Platform fetch failed: {result}")
            continue
        if isinstance(result, list):
            all_props.extend(result)

    # ── Alt-line enrichment — no hard cap on raw intake ──────────
    # The pipeline no longer caps props at the ingestion stage.  The
    # 500-bet minimum-output quota is enforced downstream.
    all_props = parse_alt_lines_from_platform_props(all_props)

    # ── Drop props with stat types the platform cannot verify ──────
    _pre_filter_count = len(all_props)
    all_props = [
        p for p in all_props
        if str(p.get("stat_type", "")).lower() in VALID_STAT_TYPES
    ]
    _dropped = _pre_filter_count - len(all_props)
    if _dropped:
        _logger.info(f"[Async] Filtered out {_dropped} unverifiable props (stat_type not in VALID_STAT_TYPES)")

    # NOTE: Goblin / Demon props preserved for Prop Scanner display.

    _logger.info(f"[Async] Total props fetched: {len(all_props)}")
    return all_props


# ============================================================
# END SECTION: Asynchronous Multi-Platform Fetcher
# ============================================================


# ============================================================
# SECTION: Cross-Platform Comparison
# ============================================================

def build_cross_platform_comparison(all_props):
    """
    Build a cross-platform line comparison from a list of props.

    Groups props by (player_name, stat_type) and stores the line
    from each platform side-by-side so you can compare them at a glance.

    Args:
        all_props (list[dict]): All fetched props (from fetch_all_platform_props).

    Returns:
        dict: Keyed by (player_name, stat_type) tuples.
              Value is a dict mapping platform → line value.

    Example:
        comparison = build_cross_platform_comparison(props)
        # → {
        #     ("LeBron James", "points"): {
        #         "PrizePicks": 24.5,
        #         "Underdog": 25.5,
        #         "DraftKings": 24.5,
        #     },
        #     ...
        # }
    """
    comparison = {}

    for prop in all_props:
        player_name = prop.get("player_name", "").strip()
        stat_type = prop.get("stat_type", "").strip()
        platform = prop.get("platform", "").strip()
        line = prop.get("line")

        if not player_name or not stat_type or not platform or line is None:
            continue  # Skip incomplete props

        key = (player_name, stat_type)

        # Initialize this player+stat entry if it's new
        if key not in comparison:
            comparison[key] = {}

        # Store the line for this platform.
        # BEGINNER NOTE: If the same player+stat appears twice on one platform
        # (e.g., different game slates), we keep the first one we see.
        if platform not in comparison[key]:
            comparison[key][platform] = line

    return comparison


def recommend_best_platform(comparison, projected_value, direction):
    """
    Recommend the best platform to bet on for a given player+stat.

    Logic:
    - OVER bets: best platform has the LOWEST line (easiest to clear)
    - UNDER bets: best platform has the HIGHEST line (most room to fall under)

    Args:
        comparison (dict): Platform → line dict for one (player, stat_type) key.
            e.g., {"PrizePicks": 24.5, "Underdog": 25.5, "DraftKings": 24.5}
        projected_value (float): Model's projected stat value for this player.
        direction (str): "OVER" or "UNDER" (case-insensitive).

    Returns:
        dict: {
            "platform": "PrizePicks",    # Best platform name
            "line": 24.5,                # Best line on that platform
            "edge": 0.3,                 # projected_value - line (OVER) or line - projected_value (UNDER)
            "all_lines": {...}           # All platform lines for reference
        }
        Returns None if comparison is empty.

    Example:
        recommend_best_platform(
            {"PrizePicks": 24.5, "Underdog": 25.5},
            projected_value=25.8,
            direction="OVER"
        )
        # → {"platform": "PrizePicks", "line": 24.5, "edge": 1.3, ...}
    """
    if not comparison:
        return None

    direction_upper = direction.upper()

    # Find the best platform based on direction
    if direction_upper == "OVER":
        # For OVER: lowest line = easiest to beat = best value
        best_platform = min(comparison, key=lambda p: comparison[p])
    else:
        # For UNDER: highest line = most room to fall under = best value
        best_platform = max(comparison, key=lambda p: comparison[p])

    best_line = comparison[best_platform]

    # Calculate the edge: how much cushion does the best line give us?
    if direction_upper == "OVER":
        edge = round(float(projected_value) - float(best_line), 2)
    else:
        edge = round(float(best_line) - float(projected_value), 2)

    return {
        "platform": best_platform,
        "line": best_line,
        "edge": edge,
        "all_lines": dict(comparison),
    }

# ============================================================
# END SECTION: Cross-Platform Comparison
# ============================================================


# ============================================================
# SECTION: Player Name Matching
# ============================================================

def match_platform_player_to_csv(platform_name, players_data):
    """
    Match a player name from a betting platform to our CSV player database.

    Platforms often use shortened or alternate names (e.g., "Nic Claxton"
    instead of "Nicolas Claxton"). This function uses the existing fuzzy
    matching from data_manager.py to find the canonical name.

    Args:
        platform_name (str): Player name as returned by a platform API.
        players_data (list[dict]): Player list from load_players_data().

    Returns:
        str or None: Canonical player name from our CSV, or None if not found.

    Example:
        match_platform_player_to_csv("Nic Claxton", players_data)
        → "Nicolas Claxton"
    """
    if not platform_name or not players_data:
        return None

    # Use the fuzzy name matcher from data_manager.py
    # BEGINNER NOTE: We import here to avoid circular imports at module level.
    try:
        from data.data_manager import find_player_by_name_fuzzy
        player = find_player_by_name_fuzzy(players_data, platform_name)
        if player:
            return player.get("name", None)
    except Exception as err:
        _logger.warning(f"[NameMatch] Error matching '{platform_name}': {err}")

    return None


def enrich_props_with_csv_names(props, players_data):
    """
    Enrich fetched props by matching platform player names to CSV canonical names.

    Also fills in team abbreviation from the CSV if the platform didn't return one.

    Args:
        props (list[dict]): Props from fetch_all_platform_props().
        players_data (list[dict]): Player list from load_players_data().

    Returns:
        list[dict]: Same props with "player_name" replaced by canonical CSV name
                    where a match was found, and "team" filled in if missing.
    """
    enriched = []
    for prop in props:
        prop = dict(prop)  # Copy so we don't mutate the original
        platform_name = prop.get("player_name", "")

        try:
            from data.data_manager import find_player_by_name_fuzzy
            player = find_player_by_name_fuzzy(players_data, platform_name)
            if player:
                prop["player_name"] = player.get("name", platform_name)
                # Fill in team from CSV if missing
                if not prop.get("team"):
                    prop["team"] = player.get("team", "")
        except Exception:
            pass  # Keep original name if matching fails

        enriched.append(prop)

    return enriched

# ============================================================
# END SECTION: Player Name Matching
# ============================================================


# ============================================================
# SECTION: Roster Inference from Props
# ============================================================

def find_new_players_from_props(props, players_data):
    """
    Identify players from platform props who are NOT in our CSV database.

    Since betting platforms only list active players who are playing tonight,
    any player on a platform but NOT in our CSV is either new, traded, or
    a player we haven't fetched yet. These are flagged for a data update.

    Args:
        props (list[dict]): Props from fetch_all_platform_props().
        players_data (list[dict]): Player list from load_players_data().

    Returns:
        list[str]: List of platform player names not found in our CSV.

    Example:
        new_players = find_new_players_from_props(props, players_data)
        # → ["Marcus Morris Sr.", "Patrick Baldwin Jr."]
    """
    if not props or not players_data:
        return []

    try:
        from data.data_manager import find_player_by_name_fuzzy
    except Exception:
        return []

    not_found = []
    seen = set()  # Avoid duplicate names in the output

    for prop in props:
        player_name = prop.get("player_name", "").strip()
        if not player_name or player_name in seen:
            continue
        seen.add(player_name)

        match = find_player_by_name_fuzzy(players_data, player_name)
        if not match:
            not_found.append(player_name)

    return not_found


def extract_active_players_from_props(props):
    """
    Extract the set of active players implied by tonight's platform props.

    Since betting platforms (PrizePicks, Underdog, DraftKings) only list
    props for players who are CONFIRMED active and playing tonight, every
    player who appears in the props list is de-facto confirmed:
      1. Active (not injured/out)
      2. Playing tonight
      3. On an NBA roster

    Args:
        props (list[dict]): Props from fetch_all_platform_props().

    Returns:
        dict: Keyed by lower-cased player name.
              Value: {"name": str, "team": str, "platforms": list[str]}

    Example:
        active = extract_active_players_from_props(props)
        # → {
        #     "lebron james": {"name": "LeBron James", "team": "LAL",
        #                      "platforms": ["PrizePicks", "Underdog"]},
        #     ...
        # }
    """
    active = {}

    for prop in props:
        player_name = prop.get("player_name", "").strip()
        if not player_name:
            continue

        team = prop.get("team", "").strip()
        platform = prop.get("platform", "").strip()
        key = player_name.lower()

        if key not in active:
            active[key] = {
                "name": player_name,
                "team": team,
                "platforms": [],
            }
        else:
            # Update team if we got a better value
            if team and not active[key]["team"]:
                active[key]["team"] = team

        if platform and platform not in active[key]["platforms"]:
            active[key]["platforms"].append(platform)

    return active


def cross_reference_with_player_data(platform_players, players_data):
    """
    Compare platform-confirmed active players against our CSV player database.

    Identifies:
      - Players the platforms have props for that we have stats for (matched)
      - Players on platforms but NOT in our CSV (missing_from_csv) — need data update
      - Players in our CSV but NOT on any platform tonight (in_csv_but_not_on_platforms)
        — these players may be injured, resting, or not playing tonight

    Args:
        platform_players (dict): Output of extract_active_players_from_props().
        players_data (list[dict]): Player records from load_players_data().

    Returns:
        dict with keys:
          "matched"                   : list[dict] — players found in both
          "missing_from_csv"          : list[str]  — platform names not in CSV
          "in_csv_but_not_on_platforms": list[dict] — CSV players absent from platforms

    Example:
        result = cross_reference_with_player_data(active_players, players_data)
        result["missing_from_csv"]  # → ["Marcus Morris Sr."]
        result["matched"]           # → [{"name": "LeBron James", "team": "LAL", ...}]
    """
    try:
        from data.data_manager import normalize_player_name as _norm
    except ImportError:
        def _norm(n):
            return n.lower().strip()

    # Build a normalized-name set from our CSV for fast lookup
    csv_norm_map = {}
    for player in players_data:
        name = player.get("name", "").strip()
        if name:
            csv_norm_map[_norm(name)] = player

    matched = []
    missing_from_csv = []

    for key, info in platform_players.items():
        norm_key = _norm(info["name"])
        if norm_key in csv_norm_map:
            matched.append({
                "name": info["name"],
                "team": info["team"],
                "platforms": info["platforms"],
                "csv_name": csv_norm_map[norm_key].get("name", info["name"]),
            })
        else:
            missing_from_csv.append(info["name"])

    # Players in CSV but NOT confirmed on any platform tonight
    platform_norm_keys = {_norm(info["name"]) for info in platform_players.values()}
    in_csv_but_not_on_platforms = [
        player for player in players_data
        if _norm(player.get("name", "")) not in platform_norm_keys
    ]

    return {
        "matched": matched,
        "missing_from_csv": missing_from_csv,
        "in_csv_but_not_on_platforms": in_csv_but_not_on_platforms,
    }


def get_platform_confirmed_injuries(platform_players, players_data, todays_games):
    """
    Infer potential injuries from platform props — players on tonight's teams
    who do NOT appear in any platform's props may be out/inactive.

    Since platforms only list players who are active, a player who:
      - Is in our CSV database
      - Plays for a team with a game tonight
      - Does NOT appear in any platform props

    ...is likely injured, resting, or sitting out (even if not yet on the
    official injury report).

    Args:
        platform_players (dict): Output of extract_active_players_from_props().
        players_data (list[dict]): Player records from load_players_data().
        todays_games (list): Tonight's game list (each item has "home_team"
                             and "away_team" or similar fields).

    Returns:
        list[dict]: Each item: {"name": str, "team": str,
                                "reason": "Not listed on any platform props"}

    Example:
        possibly_out = get_platform_confirmed_injuries(active, players, games)
        # → [{"name": "Damian Lillard", "team": "MIL",
        #      "reason": "Not listed on any platform props"}, ...]
    """
    try:
        from data.data_manager import normalize_player_name as _norm
    except ImportError:
        def _norm(n):
            return n.lower().strip()

    # Collect team abbreviations playing tonight
    tonight_teams = set()
    for game in todays_games:
        home = game.get("home_team", game.get("homeTeam", ""))
        away = game.get("away_team", game.get("awayTeam", ""))
        if home:
            tonight_teams.add(str(home).upper())
        if away:
            tonight_teams.add(str(away).upper())

    if not tonight_teams:
        return []

    # Build normalized-name set from platform props (computed once)
    platform_norm_keys = {_norm(info["name"]) for info in platform_players.values()}

    # Pre-compute (name, team, norm_name) for players_data to avoid repeated normalization
    possibly_out = []
    for player in players_data:
        player_name = player.get("name", "").strip()
        player_team = str(player.get("team", "")).upper().strip()

        if not player_name or not player_team:
            continue

        # Only check players on teams playing tonight
        if player_team not in tonight_teams:
            continue

        # Flag if not seen on any platform
        if _norm(player_name) not in platform_norm_keys:
            possibly_out.append({
                "name": player_name,
                "team": player_team,
                "reason": "Not listed on any platform props",
            })

    return possibly_out

# ============================================================
# END SECTION: Roster Inference from Props
# ============================================================


# ============================================================
# SECTION: Per-Platform Summary Helper
# ============================================================

def summarize_props_by_platform(props):
    """
    Count how many props were fetched per platform.

    Args:
        props (list[dict]): All fetched props.

    Returns:
        dict: Platform name → count of props.

    Example:
        summarize_props_by_platform(props)
        # → {"PrizePicks": 84, "Underdog": 76, "DraftKings": 32}
    """
    summary = {}
    for prop in props:
        platform = prop.get("platform", "Unknown")
        summary[platform] = summary.get(platform, 0) + 1
    return summary

# ============================================================
# END SECTION: Per-Platform Summary Helper
# ============================================================


# ============================================================
# SECTION: Smart Prop Filter
# ============================================================

# Default stat types to keep when smart filtering is enabled.
# These are the most commonly offered and highest-value prop types.
_DEFAULT_STAT_TYPES = frozenset({
    "points", "rebounds", "assists", "threes",
    "steals", "blocks", "turnovers",
    "points_rebounds_assists", "points_rebounds",
    "points_assists", "rebounds_assists",
    "blocks_steals",
    # Fantasy / yes-no combo types
    "fantasy_score", "double_double", "triple_double",
    # Extended NBA stat types from mirror
    "ftm", "fga", "fgm", "fta",
    "minutes", "personal_fouls",
    "offensive_rebounds", "defensive_rebounds",
})


def quarantine_props(
    props,
    odds_floor=QUARANTINE_ODDS_FLOOR,
    odds_ceiling=QUARANTINE_ODDS_CEILING,
    equilibrium=_EQUILIBRIUM_ODDS,
):
    """
    Apply a strict Data Quarantine to raw props from any platform.

    The quarantine prevents the engine from analysing extreme alternate
    lines that no DFS platform actually offers as standard plays.  It
    enforces three rules:

    1. **Hard Drop** — Remove any line whose ``over_odds`` or
       ``under_odds`` fall outside the ``[odds_floor, odds_ceiling]``
       window (default -300 to +250).  These are extreme alt-lines, not
       standard DFS boards.

    2. **Main Line Lock** — For each unique (player, stat_type) pair,
       select the single line whose ``over_odds`` are closest to
       ``equilibrium`` (default -110).  This is the "Main Line" that
       DFS platforms display as their standard More/Less board.

    3. **prop_target_line** — The surviving line value is stamped on
       each prop as ``prop_target_line`` (float).  All downstream EV,
       simulation, and Kelly calculations MUST use this field.

    If a player+stat has **no** line surviving the hard-drop, the
    player is silently dropped for that stat type (prevents UI
    crashes from missing data).

    Args:
        props (list[dict]): Raw props (each must have ``over_odds``,
            ``under_odds``, ``line``, ``player_name``, ``stat_type``).
        odds_floor (int): Most-negative American odds allowed (default -300).
        odds_ceiling (int): Most-positive American odds allowed (default +250).
        equilibrium (int): Target equilibrium odds for main-line selection
            (default -110).

    Returns:
        tuple: (quarantined_props, quarantine_summary)
            quarantined_props (list[dict]): Props that pass quarantine,
                each enriched with ``prop_target_line``.
            quarantine_summary (dict): Counts at each step.
    """
    summary = {
        "input_count": len(props),
        "after_hard_drop": 0,
        "after_main_line_lock": 0,
        "dropped_no_valid_line": 0,
    }

    if not props:
        return [], summary

    # ── Step 1: Hard Drop — remove extreme odds ─────────────────────────
    surviving = []
    for p in props:
        try:
            over_o = float(p.get("over_odds", _DEFAULT_AMERICAN_ODDS))
        except (ValueError, TypeError):
            over_o = float(_DEFAULT_AMERICAN_ODDS)
        try:
            under_o = float(p.get("under_odds", _DEFAULT_AMERICAN_ODDS))
        except (ValueError, TypeError):
            under_o = float(_DEFAULT_AMERICAN_ODDS)

        # Odds worse than floor (e.g. -400 < -300) → drop
        if over_o < odds_floor or under_o < odds_floor:
            continue
        # Odds better than ceiling (e.g. +300 > +250) → drop
        if over_o > odds_ceiling or under_o > odds_ceiling:
            continue

        surviving.append(p)

    summary["after_hard_drop"] = len(surviving)

    # ── Step 2: Main Line Lock — select the line closest to equilibrium ──
    # Group by (player_name_lower, stat_type_lower)
    groups: dict = {}
    for p in surviving:
        key = (
            str(p.get("player_name", "")).lower().strip(),
            str(p.get("stat_type", "")).lower().strip(),
        )
        groups.setdefault(key, []).append(p)

    quarantined: list = []
    dropped_count = 0

    for _key, group in groups.items():
        # Pick the line whose over_odds are closest to equilibrium
        best = None
        best_distance = float("inf")
        for p in group:
            try:
                over_o = float(p.get("over_odds", _DEFAULT_AMERICAN_ODDS))
            except (ValueError, TypeError):
                over_o = float(_DEFAULT_AMERICAN_ODDS)
            distance = abs(over_o - equilibrium)
            if distance < best_distance:
                best_distance = distance
                best = p

        if best is None:
            dropped_count += 1
            continue

        # Stamp the surviving prop with prop_target_line
        enriched = dict(best)
        try:
            enriched["prop_target_line"] = float(best.get("line", 0))
        except (ValueError, TypeError):
            dropped_count += 1
            continue

        if enriched["prop_target_line"] <= 0:
            dropped_count += 1
            continue

        quarantined.append(enriched)

    summary["after_main_line_lock"] = len(quarantined)
    summary["dropped_no_valid_line"] = dropped_count

    return quarantined, summary


def smart_filter_props(
    all_props,
    players_data=None,
    todays_games=None,
    injury_map=None,
    max_props_per_player=5,
    stat_types=None,
    deduplicate_cross_platform=True,
):
    """
    Intelligently reduce a large prop set to high-signal picks.

    Runs the following pipeline in order:
      1. Filter to tonight's teams only (cross-reference todays_games).
      2. Remove injured/inactive players (cross-reference injury_map).
      3. Deduplicate cross-platform props — keep the best line for each
         player+stat combination (or a single representative if averaging).
         Tags the surviving prop with all platforms that offer it.
      4. Filter to selected stat types (defaults to core stats).
      5. Cap props per player at max_props_per_player (if set).

    Args:
        all_props (list[dict]): Full prop list from fetch_all_platform_props().
        players_data (list[dict], optional): Player records from load_players_data().
            Used to validate players exist in the database.
        todays_games (list[dict], optional): Tonight's game schedule.
            Each entry should have 'home_team' and 'away_team' keys.
        injury_map (dict, optional): Player-name → injury-status mapping.
            Keys are lowercase player names; values are status strings
            (e.g., "Out", "Injured Reserve", "Questionable").
        max_props_per_player (int or None): Maximum stat types to keep per
            player.  Default is 5. Range 1–15.  Pass None to skip the
            per-player cap entirely.
        stat_types (set or list, optional): Stat types to include.
            Defaults to None (accept ALL stat types). Pass a set/list to
            restrict to specific stat types only.
        deduplicate_cross_platform (bool): If True (default), collapse
            duplicate (player, stat_type) entries from multiple platforms
            into one record and tag it with all offering platforms.

    Returns:
        tuple: (filtered_props, filter_summary)
            filtered_props (list[dict]): Reduced, high-signal prop list.
            filter_summary (dict): Step-by-step count statistics.

    Example:
        filtered, summary = smart_filter_props(
            all_props=raw_props,
            todays_games=st.session_state.get("todays_games", []),
            injury_map=st.session_state.get("injury_status_map", {}),
        )
        print(f"Reduced {summary['original_count']} → {summary['final_count']} props "
              f"({summary['reduction_pct']:.0f}% reduction)")
    """
    # ── Statuses considered inactive/out ───────────────────────────────
    # NOTE: "doubtful" is intentionally excluded — Doubtful players are
    # analyzed with an injury_status_penalty applied to confidence
    # scoring rather than being dropped entirely.
    _INACTIVE_STATUSES = frozenset({
        "out", "injured reserve", "ir", "suspended",
        "not with team", "g league - two-way",
        "g league - on assignment", "g league",
    })

    # ── Resolve stat type filter set ────────────────────────────────────
    # When stat_types is None, accept ALL stat types (no filtering).
    # Expand "fantasy_score" to include all platform-specific variants.
    if stat_types is None:
        _allowed_stats = None  # sentinel: skip stat-type filtering entirely
    else:
        _raw_allowed = set(str(s).lower().strip() for s in stat_types)
        # "fantasy_score" is the UI label; expand to all platform variants
        if "fantasy_score" in _raw_allowed:
            from engine import FANTASY_STAT_TYPES
            _raw_allowed |= set(FANTASY_STAT_TYPES)
        _allowed_stats = frozenset(_raw_allowed)

    original_count = len(all_props)
    summary: dict = {
        "original_count": original_count,
        "after_quarantine": original_count,
        "after_team_filter": original_count,
        "after_injury_filter": original_count,
        "after_dedup": original_count,
        "after_stat_filter": original_count,
        "after_per_player_cap": original_count,
        "final_count": original_count,
        "reduction_pct": 0.0,
    }

    if not all_props:
        return [], summary

    # ── Step 0: Data Quarantine — hard-drop extreme odds + lock main line ─
    quarantined, q_summary = quarantine_props(all_props)
    summary["after_quarantine"] = len(quarantined)

    # NOTE: Goblin / Demon props are kept — downstream guards handle exclusion.

    # ── Step 1: Filter to tonight's teams ───────────────────────────────
    # Build the set of teams playing tonight (with common abbreviation aliases)
    _ABBREV_ALIASES = {
        "GS": "GSW", "GSW": "GS",
        "NY": "NYK", "NYK": "NY",
        "NO": "NOP", "NOP": "NO",
        "SA": "SAS", "SAS": "SA",
        "UTAH": "UTA", "UTA": "UTAH",
        "WSH": "WAS", "WAS": "WSH",
        "BKN": "BRK", "BRK": "BKN",
        "PHX": "PHO", "PHO": "PHX",
        "CHA": "CHO", "CHO": "CHA",
    }

    tonight_teams: set = set()
    if todays_games:
        for game in todays_games:
            for side in ("home_team", "away_team", "homeTeam", "awayTeam"):
                abbr = str(game.get(side, "")).upper().strip()
                if abbr:
                    tonight_teams.add(abbr)
                    alias = _ABBREV_ALIASES.get(abbr)
                    if alias:
                        tonight_teams.add(alias)
        tonight_teams.discard("")

    if tonight_teams:
        team_filtered = [
            p for p in quarantined
            if (
                not p.get("team")  # keep props with no team info (can't filter)
                or str(p.get("team", "")).upper().strip() in tonight_teams
            )
        ]
    else:
        # No game data — can't filter by team; keep all
        team_filtered = list(quarantined)

    summary["after_team_filter"] = len(team_filtered)

    # ── Step 2: Remove injured/inactive players ──────────────────────────
    if injury_map:
        def _is_active(prop):
            player_key = str(prop.get("player_name", "")).lower().strip()
            entry = injury_map.get(player_key, "")
            # Support both dict-valued maps ({"status": "Out", ...})
            # and plain string-valued maps ("Out").
            if isinstance(entry, dict):
                status = str(entry.get("status", "")).lower().strip()
            else:
                status = str(entry).lower().strip()
            if not status:
                return True  # No status known — assume active
            return status not in _INACTIVE_STATUSES

        injury_filtered = [p for p in team_filtered if _is_active(p)]
    else:
        injury_filtered = team_filtered

    summary["after_injury_filter"] = len(injury_filtered)

    # ── Step 3: Deduplicate cross-platform props ─────────────────────────
    if deduplicate_cross_platform:
        # Group by (player_name_lower, stat_type) key
        dedup_map: dict = {}  # key → list of props
        for prop in injury_filtered:
            pkey = (
                str(prop.get("player_name", "")).lower().strip(),
                str(prop.get("stat_type", "")).lower().strip(),
            )
            dedup_map.setdefault(pkey, []).append(prop)

        dedup_filtered: list = []
        for pkey, group in dedup_map.items():
            if len(group) == 1:
                dedup_filtered.append(group[0])
            else:
                # Use the lower median line (floor of midpoint for even-length groups),
                # which biases toward the lower line — better for OVER bettors.
                sorted_group = sorted(group, key=lambda p: float(p.get("line", 0) or 0))
                best = dict(sorted_group[(len(sorted_group) - 1) // 2])  # lower-median line
                all_platforms_for_prop = sorted({
                    str(p.get("platform", "")).strip()
                    for p in group
                    if p.get("platform")
                })
                best["platforms_offering"] = all_platforms_for_prop
                # Keep original platform name from the median entry
                dedup_filtered.append(best)
    else:
        dedup_filtered = injury_filtered

    summary["after_dedup"] = len(dedup_filtered)

    # ── Step 4: Filter to selected stat types ────────────────────────────
    if _allowed_stats is None:
        # No stat-type filtering — accept all stat types
        stat_filtered = dedup_filtered
    else:
        stat_filtered = [
            p for p in dedup_filtered
            if str(p.get("stat_type", "")).lower().strip() in _allowed_stats
        ]
    summary["after_stat_filter"] = len(stat_filtered)

    # ── Step 5: Cap props per player ────────────────────────────────────
    # Priority ordering within each player: prefer core stats first
    _STAT_PRIORITY = {
        "points": 0, "rebounds": 1, "assists": 2,
        "points_rebounds_assists": 3, "threes": 4,
        "points_rebounds": 5, "points_assists": 6,
        "rebounds_assists": 7, "steals": 8,
        "blocks": 9, "turnovers": 10,
        "blocks_steals": 11, "ftm": 12,
        "fantasy_score_pp": 13, "fantasy_score_dk": 13, "fantasy_score_ud": 13,
    }

    if max_props_per_player is None:
        # No per-player cap — pass all stat-filtered props through
        capped = stat_filtered
    else:
        # Clamp max_props_per_player to a reasonable range (1–100).
        # The docstring documents 1-15 as typical, but we allow up to 100
        # for power users who want to disable the cap without changing code.
        _MAX = min(100, max(1, int(max_props_per_player)))
        player_counts: dict = {}
        capped: list = []

        # Sort to ensure priority stat types come first for each player
        stat_filtered_sorted = sorted(
            stat_filtered,
            key=lambda p: _STAT_PRIORITY.get(
                str(p.get("stat_type", "")).lower().strip(), 99
            ),
        )

        for prop in stat_filtered_sorted:
            player_key = str(prop.get("player_name", "")).lower().strip()
            count = player_counts.get(player_key, 0)
            if count < _MAX:
                capped.append(prop)
                player_counts[player_key] = count + 1

    summary["after_per_player_cap"] = len(capped)
    summary["final_count"] = len(capped)

    # Calculate overall reduction percentage
    if original_count > 0:
        summary["reduction_pct"] = round(
            (1.0 - len(capped) / original_count) * 100.0, 1
        )
    else:
        summary["reduction_pct"] = 0.0

    return capped, summary

# ============================================================
# END SECTION: Smart Prop Filter
# ============================================================


# ============================================================
# SECTION: Alternate Line Categorization
# ============================================================

def parse_alt_lines_from_platform_props(props):
    """
    Parse a flat list of platform props and enrich each record with the
    standard (primary) O/U line for its (player, stat, platform) group.

    When the same (player_name, stat_type, platform) combination appears
    more than once in the props list, the MEDIAN of all available lines is
    treated as the standard line and stamped onto every entry as
    ``'standard_line'``.

    Statistical analysis should be triggered ONLY on actual bookmaker lines
    — never on hypothetical or generated values.  Pass the output of this
    function directly to the analysis pipeline to ensure only real lines
    are evaluated.

    Args:
        props (list[dict]): Props as returned by ``fetch_all_platform_props()``.
            Multiple entries for the same (player, stat, platform) tuple
            indicate that alternate lines are available.

    Returns:
        list[dict]: Same props enriched with one new key on every entry:
            ``'standard_line'``: float — the median line for this
                (player, stat, platform) group (the Standard_Line).

    Example::

        props = [
            {"player_name": "SGA", "stat_type": "points",
             "line": 28.5, "platform": "PrizePicks"},
            {"player_name": "SGA", "stat_type": "points",
             "line": 31.5, "platform": "PrizePicks"},
            {"player_name": "SGA", "stat_type": "points",
             "line": 34.5, "platform": "PrizePicks"},
        ]
        enriched = parse_alt_lines_from_platform_props(props)
        # → [
        #     {..."line": 28.5, "standard_line": 31.5},
        #     {..."line": 31.5, "standard_line": 31.5},
        #     {..."line": 34.5, "standard_line": 31.5},
        # ]
    """
    import statistics as _statistics

    # ── Step 1: Group all lines by (player_name, stat_type, platform) ────
    _groups = {}
    for prop in props:
        key = (
            str(prop.get("player_name", "")).lower().strip(),
            str(prop.get("stat_type", "")).lower().strip(),
            str(prop.get("platform", "")).lower().strip(),
        )
        _groups.setdefault(key, []).append(prop)

    # ── Step 2: Identify the Standard_Line for each group ────────────────
    _standard_lines = {}
    for key, group_props in _groups.items():
        valid_lines = []
        for p in group_props:
            try:
                val = float(p.get("line", 0) or 0)
                if val > 0:
                    valid_lines.append(val)
            except (ValueError, TypeError):
                pass
        if valid_lines:
            _standard_lines[key] = _statistics.median(valid_lines)
        else:
            _standard_lines[key] = None

    # ── Step 3: Stamp each prop with standard_line ────────────────────────
    enriched = []
    for prop in props:
        key = (
            str(prop.get("player_name", "")).lower().strip(),
            str(prop.get("stat_type", "")).lower().strip(),
            str(prop.get("platform", "")).lower().strip(),
        )
        std_line = _standard_lines.get(key)

        enriched_prop = dict(prop)
        enriched_prop["standard_line"] = std_line

        enriched.append(enriched_prop)

    return enriched

# ============================================================
# END SECTION: Alternate Line Categorization
# ============================================================

