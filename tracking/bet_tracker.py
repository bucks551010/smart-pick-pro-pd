# ============================================================
# FILE: tracking/bet_tracker.py
# PURPOSE: High-level interface for logging and reviewing bets.
#          Uses database.py for storage, adds business logic.
# CONNECTS TO: database.py (storage), pages/6_Model_Health.py
# CONCEPTS COVERED: Data validation, aggregation, reporting
# ============================================================

# Standard library imports only
import datetime  # For getting today's date
import os        # For DB_DIR environment variable
import time      # For retry delays in resolve_todays_bets
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# Import our database module (sibling file in tracking/)
from tracking.database import (
    insert_bet,
    update_bet_result,
    load_all_bets,
    get_performance_summary,
    initialize_database,
    save_daily_snapshot,
)

# Import shared constants from the engine package
# BEGINNER NOTE: We import from engine/__init__.py so there's
# only ONE place that defines what stat types are valid.
from engine import VALID_STAT_TYPES, FANTASY_STAT_TYPES


# ============================================================
# SECTION: Valid Values for Validation
# ============================================================

# Valid bet directions
VALID_DIRECTIONS = {"OVER", "UNDER"}

# Valid result values
VALID_RESULTS = {"WIN", "LOSS", "EVEN", "VOID"}

# Valid platforms
VALID_PLATFORMS = {
    "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
}

# Valid tier names
VALID_TIERS = {"Platinum", "Gold", "Silver", "Bronze"}

# Retry configuration for API calls in resolve_todays_bets
RESOLVE_MAX_RETRIES = 3
RESOLVE_RETRY_DELAY = 2  # seconds between retries

# NBA API call configuration
NBA_API_TIMEOUT = 60       # seconds Ã¢â‚¬â€ increased from default 30 to handle slow endpoints
_BACKOFF_BASE = 1.2        # initial delay in seconds between API attempts
_BACKOFF_INCREMENT = 0.8   # additional seconds per retry (1.2s, 2.0s, 2.8s)

# Tolerance for declaring a bet result as EVEN (exact tie within float epsilon)
EVEN_THRESHOLD_EPSILON = 0.01

# ============================================================
# END SECTION: Valid Values for Validation
# ============================================================


def _get_eastern_tz():
    """Return a US/Eastern timezone object for NBA game-date anchoring.

    NBA defines game dates in Eastern Time. This function prefers
    ``zoneinfo.ZoneInfo`` (DST-aware) and falls back to a fixed UTC-5
    offset when zoneinfo is unavailable.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    time (EDT = UTC-4, roughly MarchÃ¢â‚¬â€œNovember). During EDT, dates
    derived from this fallback may be one hour off near the midnight
    boundary. If your server runs in UTC and processes games near
    midnight ET, install ``tzdata`` (``pip install tzdata``) to ensure
    ``zoneinfo`` is available.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except ImportError:
        return datetime.timezone(datetime.timedelta(hours=-5))


def _nba_today_et():
    """Return the current NBA 'sports day' anchored to Eastern Time.

    The sports day boundary is 4:00 AM ET (not midnight). Between
    12:00 AM and 3:59 AM ET the running slate is still attributed to
    the *previous* calendar day, matching how sportsbooks treat
    West-Coast games that finish at 1–2 AM ET. This must match
    ``tracking.database._nba_today_iso`` so bet_date filters align
    with slate/analysis dates.
    """
    now_et = datetime.datetime.now(_get_eastern_tz())
    if now_et.hour < 4:
        now_et = now_et - datetime.timedelta(days=1)
    return now_et.date()


# Ordered list of date formats returned by upstream APIs.
# "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SSÃ¢â‚¬Â¦" ([:10] works).
# nba_api PlayerGameLog Ã¢â€ â€™ "MMM DD, YYYY" (e.g. "MAR 05, 2026").
_GAME_DATE_FORMATS = ["%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"]


def _parse_game_date(raw: str):
    """Parse a game-date string from any known API format into a ``date``.

    Tries ISO (YYYY-MM-DD), short-month (MAR 05, 2026), and long-month
    (March 05, 2026) formats so the caller does not need to know which
    data source supplied the log row.

    Returns:
        ``datetime.date`` on success, ``None`` when *raw* is empty/None
        or does not match any known format.
    """
    if not raw:
        return None
    # Fast path: ISO date is always the first 10 chars
    snippet = raw[:10].strip()
    for fmt in _GAME_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(
                snippet if fmt == "%Y-%m-%d" else raw.strip(), fmt
            ).date()
        except (ValueError, TypeError):
            continue
    return None


# ============================================================
# SECTION: Unified Stat Column Mapping
# Maps ALL known internal stat keys AND platform-native aliases
# to API-NBA game log field names (lowercase).
# ============================================================

# API-NBA game log uses lowercase keys: pts, reb, ast, stl, blk, tov, fg3m, minutes
_STAT_COL = {
    # Ã¢â€â‚¬Ã¢â€â‚¬ Internal canonical keys Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    "points":           "pts",
    "rebounds":         "reb",
    "assists":          "ast",
    "threes":           "fg3m",
    "steals":           "stl",
    "blocks":           "blk",
    "turnovers":        "tov",
    "three_pointers":   "fg3m",
    "minutes":          "minutes",
    "dunks":            "dunks",
    # Ã¢â€â‚¬Ã¢â€â‚¬ Platform name aliases Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    "pts":              "pts",
    "rebs":             "reb",
    "asts":             "ast",
    "blks":             "blk",
    "stls":             "stl",
    "tovs":             "tov",
    "3-pt made":        "fg3m",
    "3pm":              "fg3m",
    "blocked shots":    "blk",
    "free throws made": "ftm",
    "ftm":              "ftm",
    "fta":              "fta",
    "fga":              "fga",
    "fgm":              "fgm",
    "fg3a":             "fg3a",
    "personal_fouls":   "pf",
    "offensive_rebounds": "oreb",
    "defensive_rebounds": "dreb",
    # Ã¢â€â‚¬Ã¢â€â‚¬ Platform name aliases Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    "three pointers":   "fg3m",
    "3-pointers":       "fg3m",
    "three_point":      "fg3m",
    "fg3m":             "fg3m",
    "tov":              "tov",
    "stl":              "stl",
    "blk":              "blk",
    "reb":              "reb",
    "ast":              "ast",
    "min":              "minutes",
    # Ã¢â€â‚¬Ã¢â€â‚¬ 3-pt attempted aliases Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    "3-pt attempted":           "fg3a",
    "3pt attempted":            "fg3a",
    "three pointers attempted": "fg3a",
    "three_pointers_attempted": "fg3a",
    "3-pointers attempted":     "fg3a",
}

# Ã¢â€â‚¬Ã¢â€â‚¬ Computed stats: derived from multiple box-score columns Ã¢â€â‚¬Ã¢â€â‚¬
# Each entry maps a stat name to a tuple of (add_cols, subtract_cols)
# so that actual_value = sum(add_cols) - sum(subtract_cols).
_COMPUTED_STATS = {
    "two pointers made":      (("fgm",), ("fg3m",)),
    "two pointers attempted": (("fga",), ("fg3a",)),
    "2pm":                    (("fgm",), ("fg3m",)),
    "2pa":                    (("fga",), ("fg3a",)),
    "two_pointers_made":      (("fgm",), ("fg3m",)),
    "two_pointers_attempted": (("fga",), ("fg3a",)),
}

# Stats that exist on some platforms but CANNOT be resolved from a
# standard NBA box score (full-game totals).  Flagged gracefully.
# NOTE: "dunks" was removed Ã¢â‚¬â€ we now resolve it via play-by-play data.
_UNRESOLVABLE_STATS = frozenset()

# Game-segment prop patterns that CANNOT be resolved from PlayerGameLog
# (which only has full-game totals). These are flagged gracefully instead
# of dumped into the generic "unknown stat" error bucket.
_SEGMENT_PROP_PATTERNS = [
    "1st half",
    "2nd half",
    "1st quarter",
    "2nd quarter",
    "3rd quarter",
    "4th quarter",
    "1st 3 minutes",
    "1st 5 minutes",
    "1st 10 minutes",
]


def _is_segment_prop(stat_type: str) -> bool:
    """Return True if stat_type is a game-segment prop that can't be resolved."""
    lower = stat_type.lower()
    return any(pattern in lower for pattern in _SEGMENT_PROP_PATTERNS)


import re as _re_bt

# Regex to strip Underdog-style " Stat Description O/U" suffix from
# player names stored with corrupted data.  Longest patterns first so
# "Points + Rebounds" matches before "Points".
_UD_NAME_SUFFIX_RE = _re_bt.compile(
    r"\s+(?:"
    r"Pts\s*\+\s*Rebs\s*\+\s*Asts"
    r"|Points\s*\+\s*Rebounds\s*\+\s*Assists"
    r"|Points\s*\+\s*Rebounds"
    r"|Points\s*\+\s*Assists"
    r"|Rebounds\s*\+\s*Assists"
    r"|Fantasy\s+Points"
    r"|3-Pointers\s+Made"
    r"|FG\s+Attempted"
    r"|FT\s+Made"
    r"|Points"
    r"|Rebounds"
    r"|Assists"
    r"|Steals"
    r"|Blocks"
    r"|Turnovers"
    r"|Double\s+Double"
    r"|Triple\s+Double"
    r"|Blks\s*\+\s*Stls"
    r")\s*O/U\s*$",
    _re_bt.IGNORECASE,
)


def _clean_player_name(name: str) -> str:
    """Strip stat-type + 'O/U' suffix from player names that were stored
    with the full Underdog prop title (e.g. 'LeBron James Points O/U'
    → 'LeBron James').  No-op if the name is already clean."""
    if not name or "O/U" not in name:
        return name
    cleaned = _UD_NAME_SUFFIX_RE.sub("", name).strip()
    return cleaned if cleaned else name

# ============================================================
# END SECTION: Unified Stat Column Mapping
# ============================================================


# ============================================================
# SECTION: Per-Player Game Log Fetcher for Bet Resolution
# Uses ETL database first, nba_api as fallback.
# ============================================================

def _parse_minutes(raw) -> float:
    """Convert a MIN field (could be "MM:SS", float, or str) to a float."""
    if raw is None:
        return 0.0
    s = str(raw)
    try:
        if ":" in s:
            return float(s.split(":")[0])
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _fetch_resolve_game_log(player_id, last_n: int = 10) -> list[dict]:
    """Fetch game log for bet resolution Ã¢â‚¬â€ ETL primary, nba_api fallback.

    The ETL database is fast and already populated by the ETL pipeline;
    ``nba_api.PlayerGameLog`` is the online fallback when the ETL DB
    has no data.

    Returns a list of dicts with lowercase stat keys
    (``pts``, ``reb``, ``ast``, ``minutes``, ``fg3m``, ``ftm``, Ã¢â‚¬Â¦)
    ordered newest-first. ``game_date`` is always ISO ``YYYY-MM-DD``.
    """
    # Ã¢â€â‚¬Ã¢â€â‚¬ Source 1: local ETL database (fastest, no API call) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    try:
        from data.etl_data_service import get_player_game_logs as _etl_logs
        rows = _etl_logs(int(player_id), limit=last_n)
        if rows:
            normalised = []
            for r in rows:
                entry = dict(r)
                # Ensure 'minutes' key exists (ETL stores 'min')
                if "minutes" not in entry and "min" in entry:
                    entry["minutes"] = _parse_minutes(entry["min"])
                elif "minutes" not in entry:
                    entry["minutes"] = 0.0
                # ETL game_date is already YYYY-MM-DD
                normalised.append(entry)
            return normalised
    except Exception as _etl_exc:
        _logger.debug(
            "_fetch_resolve_game_log: ETL source failed for %s: %s",
            player_id, _etl_exc,
        )

    # Ã¢â€â‚¬Ã¢â€â‚¬ Source 2: nba_api PlayerGameLog (online) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    try:
        from nba_api.stats.endpoints import playergamelog
        game_log_endpoint = playergamelog.PlayerGameLog(
            player_id=player_id,
            season_type_all_star="Regular Season",
        )
        rows_raw = game_log_endpoint.get_data_frames()[0].to_dict("records")
        time.sleep(0.6)  # rate-limit courtesy

        formatted = []
        for g in rows_raw[:last_n]:
            # GAME_DATE from nba_api may be 'MMM DD, YYYY'; normalise
            raw_dt = g.get("GAME_DATE", "")
            parsed = _parse_game_date(raw_dt)
            iso_date = parsed.isoformat() if parsed else raw_dt
            formatted.append({
                "game_date": iso_date,
                "matchup":   g.get("MATCHUP", ""),
                "win_loss":  g.get("WL", ""),
                "minutes":   float(g.get("MIN", 0) or 0),
                "pts":       float(g.get("PTS", 0) or 0),
                "reb":       float(g.get("REB", 0) or 0),
                "ast":       float(g.get("AST", 0) or 0),
                "stl":       float(g.get("STL", 0) or 0),
                "blk":       float(g.get("BLK", 0) or 0),
                "tov":       float(g.get("TOV", 0) or 0),
                "fg3m":      float(g.get("FG3M", 0) or 0),
                "ftm":       float(g.get("FTM", 0) or 0),
                "fta":       float(g.get("FTA", 0) or 0),
                "fgm":       float(g.get("FGM", 0) or 0),
                "fga":       float(g.get("FGA", 0) or 0),
                "oreb":      float(g.get("OREB", 0) or 0),
                "dreb":      float(g.get("DREB", 0) or 0),
                "pf":        float(g.get("PF", 0) or 0),
            })
        return formatted
    except Exception as _api_exc:
        _logger.warning(
            "_fetch_resolve_game_log: nba_api failed for %s: %s",
            player_id, _api_exc,
        )
    return []

# ============================================================
# END SECTION: Per-Player Game Log Fetcher for Bet Resolution
# ============================================================


# ============================================================
# SECTION: 3-Tier Bulk Box Score Helpers
# Tier 1: nba_api BoxScore endpoints (bulk, fastest)
# Tier 2: engine/scrapers/basketball_ref_scraper.py (own scraper, replaces
#          the removed basketball_reference_web_scraper package)
# Tier 3: Legacy per-player PlayerGameLog (kept for compatibility)
# ============================================================


def _count_dunks_from_pbp(game_ids: list[str]) -> dict:
    """Count made dunks per player from play-by-play data.

    Fetches PlayByPlayV3 for each *game_id* and counts actions whose
    ``subType`` contains "dunk" and ``shotResult`` is "Made".

    Args:
        game_ids: list of NBA game ID strings.

    Returns:
        dict: ``{player_name_lower: int}`` Ã¢â‚¬â€ dunk counts keyed by lowercase
              player name.  Players with zero dunks are omitted.
    """
    dunk_counts: dict[str, int] = {}
    try:
        import time as _time
        from nba_api.stats.endpoints import playbyplayv3
    except ImportError:
        return dunk_counts

    for game_id in game_ids:
        try:
            _time.sleep(0.6)
            pbp = playbyplayv3.PlayByPlayV3(
                game_id=game_id, timeout=NBA_API_TIMEOUT,
            )
            norm = pbp.get_normalized_dict() or {}
            plays = norm.get("PlayByPlay", [])
            for play in plays:
                sub_type = str(play.get("subType", "") or "").lower()
                shot_result = str(play.get("shotResult", "") or "").lower()
                if "dunk" in sub_type and shot_result == "made":
                    # Build lowercase name from play data
                    first = str(play.get("playerName", "") or "").strip()
                    name_i = str(play.get("playerNameI", "") or "").strip()
                    pname = first.lower() if first else name_i.lower()
                    if pname:
                        dunk_counts[pname] = dunk_counts.get(pname, 0) + 1
        except Exception as _exc:
            _logger.debug(
                "[BetTracker] PBP dunk count failed for game %s: %s",
                game_id, _exc,
            )
            continue

    return dunk_counts


def _fetch_all_boxscores_nba_api(date_str: str) -> dict:
    """
    TIER 1: Fetch all player box scores for a date via nba_api BoxScore endpoints.

    Uses ScoreboardV3 to find game IDs, then BoxScoreTraditionalV3 per game.
    This replaces N per-player calls with ~G game-level calls (~5-8 per night).

    Returns:
        dict: {player_name_lower: {pts, reb, ast, stl, blk, tov, fg3m, ...}}
              Empty dict on any failure.
    """
    try:
        import time as _time
        from nba_api.stats.endpoints import scoreboardv3, boxscoretraditionalv3

        sb = scoreboardv3.ScoreboardV3(
            game_date=date_str, league_id="00", timeout=NBA_API_TIMEOUT
        )
        game_header = sb.game_header.get_data_frame()
        if game_header.empty:
            return {}

        # Resolve accuracy guard: only include FINAL games.
        # ScoreboardV3 commonly marks final as 3 in gameStatus/gameStatusId.
        _final_df = game_header
        try:
            if "gameStatusId" in _final_df.columns:
                _final_df = _final_df[_final_df["gameStatusId"].astype(str) == "3"]
            elif "gameStatus" in _final_df.columns:
                _final_df = _final_df[_final_df["gameStatus"].astype(str) == "3"]
            elif "gameStatusText" in _final_df.columns:
                _final_df = _final_df[
                    _final_df["gameStatusText"].astype(str).str.lower().str.contains("final", na=False)
                ]
        except Exception as _status_exc:
            _logger.debug(
                "[BetTracker] Tier 1 final-game filtering fallback on %s: %s",
                date_str,
                _status_exc,
            )

        game_ids = _final_df["gameId"].tolist() if not _final_df.empty else []
        if not game_ids:
            return {}
        lookup: dict = {}

        for game_id in game_ids:
            try:
                _time.sleep(0.6)  # gentle rate limiting between game calls
                bx = boxscoretraditionalv3.BoxScoreTraditionalV3(
                    game_id=game_id, timeout=NBA_API_TIMEOUT
                )
                player_stats = bx.player_stats.get_data_frame()
                for _, row in player_stats.iterrows():
                    # V3 uses firstName + familyName instead of PLAYER_NAME
                    first = str(row.get("firstName") or "").strip()
                    last = str(row.get("familyName") or "").strip()
                    pname = f"{first} {last}".lower().strip()
                    if not pname:
                        continue
                    # Parse minutes field (V3 uses "minutes" in "PT00M00.00S" or "MM:SS" format)
                    min_raw = str(row.get("minutes") or "0")
                    try:
                        if min_raw.startswith("PT") and "M" in min_raw:
                            # ISO 8601 duration format: "PT36M12.00S"
                            mins = float(min_raw[2:].split("M")[0])
                        elif ":" in min_raw:
                            mins = float(min_raw.split(":")[0])
                        else:
                            mins = float(min_raw)
                    except (ValueError, TypeError):
                        mins = 0.0
                    # Skip players with no minutes AND all-zero stats — box
                    # score data likely hasn't been populated yet (game marked
                    # Final before detailed stats are loaded by the NBA API).
                    if mins == 0.0:
                        _has_any_stat = any(
                            float(row.get(c) or 0) > 0
                            for c in ("points", "reboundsTotal", "assists",
                                      "steals", "blocks", "turnovers",
                                      "fieldGoalsMade", "fieldGoalsAttempted",
                                      "freeThrowsMade", "freeThrowsAttempted")
                        )
                        if not _has_any_stat:
                            continue  # data not ready — skip this player
                    lookup[pname] = {
                        "pts":     float(row.get("points") or 0),
                        "reb":     float(row.get("reboundsTotal") or 0),
                        "ast":     float(row.get("assists") or 0),
                        "stl":     float(row.get("steals") or 0),
                        "blk":     float(row.get("blocks") or 0),
                        "tov":     float(row.get("turnovers") or 0),
                        "fg3m":    float(row.get("threePointersMade") or 0),
                        "fg3a":    float(row.get("threePointersAttempted") or 0),
                        "fgm":     float(row.get("fieldGoalsMade") or 0),
                        "fga":     float(row.get("fieldGoalsAttempted") or 0),
                        "ftm":     float(row.get("freeThrowsMade") or 0),
                        "fta":     float(row.get("freeThrowsAttempted") or 0),
                        "oreb":    float(row.get("reboundsOffensive") or 0),
                        "dreb":    float(row.get("reboundsDefensive") or 0),
                        "pf":      float(row.get("foulsPersonal") or 0),
                        "minutes": mins,
                    }
            except Exception as _game_exc:
                _logger.warning(
                    f"[BetTracker] Tier 1: box score fetch failed for game {game_id}: {_game_exc}"
                )
                continue

        # Ã¢â€â‚¬Ã¢â€â‚¬ Enrich with dunk counts from play-by-play data Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        try:
            dunk_counts = _count_dunks_from_pbp(game_ids)
            for pname, stats in lookup.items():
                stats["dunks"] = float(dunk_counts.get(pname, 0))
        except Exception as _dunk_exc:
            _logger.debug(
                "[BetTracker] PBP dunk enrichment failed: %s", _dunk_exc,
            )
            # Ensure every player row has a "dunks" key (0) even on failure
            for stats in lookup.values():
                stats.setdefault("dunks", 0.0)

        return lookup

    except Exception as exc:
        _logger.warning(f"[BetTracker] Tier 1 (nba_api BoxScore) failed: {exc}")
        return {}


def _fetch_all_boxscores_bbref(date_str: str) -> dict:
    """
    TIER 3 FALLBACK: Fetch all player box scores via the own Basketball Reference scraper.

    Uses ``engine.scrapers.basketball_ref_scraper.get_player_box_scores_for_date``
    which replaced the removed ``basketball_reference_web_scraper`` package.
    Returns empty dict if the scraper is unavailable or the request fails.

    Returns:
        dict: {player_name_lower: {pts, reb, ast, stl, blk, tov, fg3m, ...}}
              Empty dict on any failure.
    """
    try:
        from engine.scrapers.basketball_ref_scraper import get_player_box_scores_for_date
        lookup = get_player_box_scores_for_date(date_str)
        return lookup if lookup else {}
    except Exception as exc:
        _logger.warning(f"[BetTracker] Tier 3 (bbref scraper) failed: {exc}")
        return {}


def _fetch_all_boxscores_espn(date_str: str) -> dict:
    """
    TIER 2: Fetch all player box scores for a date via ESPN's public API.

    Uses the ESPN scoreboard endpoint to find game/event IDs, then fetches
    the ``/summary`` endpoint for each game to extract player-level box
    scores.  This is a reliable fallback when ``nba_api`` is rate-limited
    or unavailable.

    Args:
        date_str: ISO date string "YYYY-MM-DD".

    Returns:
        dict: {player_name_lower: {pts, reb, ast, stl, blk, tov, fg3m, ...}}
              Empty dict on any failure.
    """
    try:
        import requests
        import time as _time

        try:
            from utils.headers import get_espn_headers
            _headers = get_espn_headers()
        except ImportError:
            _headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }

        # Convert "YYYY-MM-DD" Ã¢â€ â€™ "YYYYMMDD" for ESPN
        espn_date = date_str.replace("-", "")
        scoreboard_url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
            f"?dates={espn_date}"
        )
        resp = requests.get(scoreboard_url, headers=_headers, timeout=NBA_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return {}

        lookup: dict = {}

        for event in events:
            event_id = event.get("id")
            if not event_id:
                continue
            # Only process Final games (status type 3) for resolution accuracy
            status_type = (
                event.get("status", {}).get("type", {}).get("id", "")
            )
            if str(status_type) != "3":
                # Not final Ã¢â‚¬â€ skip; we only want completed games for resolution
                continue

            try:
                _time.sleep(0.4)  # gentle rate limiting between game calls
                summary_url = (
                    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
                    f"?event={event_id}"
                )
                summary_resp = requests.get(
                    summary_url, headers=_headers, timeout=NBA_API_TIMEOUT
                )
                summary_resp.raise_for_status()
                summary_data = summary_resp.json()

                boxscore = summary_data.get("boxscore", {})
                players_sections = boxscore.get("players", [])

                for team_section in players_sections:
                    statistics = team_section.get("statistics", [])
                    if not statistics:
                        continue

                    # Find the main stat category (usually the first one)
                    stat_block = statistics[0]
                    stat_labels = [
                        lbl.lower() for lbl in stat_block.get("labels", [])
                    ]
                    athletes = stat_block.get("athletes", [])

                    for athlete_entry in athletes:
                        if athlete_entry.get("didNotPlay", False):
                            continue
                        athlete = athlete_entry.get("athlete", {})
                        pname = str(
                            athlete.get("displayName", "")
                        ).lower().strip()
                        if not pname:
                            continue

                        stats_list = athlete_entry.get("stats", [])
                        if not stats_list or len(stats_list) != len(stat_labels):
                            continue

                        stat_dict = dict(zip(stat_labels, stats_list))

                        # Parse MIN field: ESPN gives "MM:SS" or "M" or "0"
                        min_raw = str(stat_dict.get("min", "0"))
                        try:
                            mins = (
                                float(min_raw.split(":")[0])
                                if ":" in min_raw
                                else float(min_raw)
                            )
                        except (ValueError, TypeError):
                            mins = 0.0

                        # Parse FG field "M-A" to fgm/fga
                        fg_raw = str(stat_dict.get("fg", "0-0"))
                        fg_parts = fg_raw.split("-")
                        fgm = float(fg_parts[0]) if fg_parts else 0.0
                        fga = float(fg_parts[1]) if len(fg_parts) >= 2 else 0.0

                        # Parse 3PT field "M-A" to fg3m/fg3a
                        fg3_raw = str(stat_dict.get("3pt", "0-0"))
                        fg3_parts = fg3_raw.split("-")
                        fg3m = float(fg3_parts[0]) if fg3_parts else 0.0
                        fg3a = float(fg3_parts[1]) if len(fg3_parts) >= 2 else 0.0

                        # Parse FT field "M-A" to ftm/fta
                        ft_raw = str(stat_dict.get("ft", "0-0"))
                        ft_parts = ft_raw.split("-")
                        ftm = float(ft_parts[0]) if ft_parts else 0.0
                        fta = float(ft_parts[1]) if len(ft_parts) >= 2 else 0.0

                        def _safe_float(val):
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                return 0.0

                        reb_val = _safe_float(stat_dict.get("reb", 0))
                        oreb_val = _safe_float(stat_dict.get("oreb", 0))
                        dreb_val = _safe_float(stat_dict.get("dreb", 0))

                        lookup[pname] = {
                            "pts":     _safe_float(stat_dict.get("pts", 0)),
                            "reb":     reb_val,
                            "ast":     _safe_float(stat_dict.get("ast", 0)),
                            "stl":     _safe_float(stat_dict.get("stl", 0)),
                            "blk":     _safe_float(stat_dict.get("blk", 0)),
                            "tov":     _safe_float(stat_dict.get("to", 0)),
                            "fg3m":    fg3m,
                            "fg3a":    fg3a,
                            "fgm":     fgm,
                            "fga":     fga,
                            "ftm":     ftm,
                            "fta":     fta,
                            "oreb":    oreb_val,
                            "dreb":    dreb_val,
                            "pf":      _safe_float(stat_dict.get("pf", 0)),
                            "minutes": mins,
                        }

            except Exception as _game_exc:
                _logger.warning(
                    f"[BetTracker] Tier 2 (ESPN): summary fetch failed for "
                    f"event {event_id}: {_game_exc}"
                )
                continue

        return lookup

    except Exception as exc:
        _logger.warning(f"[BetTracker] Tier 2 (ESPN) failed: {exc}")
        return {}


def _fetch_bulk_boxscores_etl(date_str: str) -> dict:
    """
    TIER 0: Fetch all player box scores for a date from the local ETL database.

    Queries Player_Game_Logs joined with Games on game_date.  Returns the
    same format as `_fetch_all_boxscores_nba_api` so callers are unaffected.

    Returns:
        dict: {player_name_lower: {pts, reb, ast, stl, blk, tov, fg3m, ...}}
              Empty dict if DB unavailable or no rows for this date.
    """
    try:
        import sqlite3 as _sqlite3
        from pathlib import Path as _Path

        _repo_root = _Path(__file__).resolve().parent.parent
        _db_path = _Path(
            os.environ.get("DB_DIR", str(_repo_root / "db"))
        ) / "smartpicks.db"
        if not _db_path.exists():
            return {}

        conn = _sqlite3.connect(f"file:{_db_path}?mode=ro", uri=True)
        conn.row_factory = _sqlite3.Row
        rows = conn.execute(
            """
            SELECT p.first_name, p.last_name,
                   l.pts, l.reb, l.ast, l.stl, l.blk, l.tov,
                   l.fg3m, l.fg3a, l.fgm, l.fga, l.ftm, l.fta,
                   l.oreb, l.dreb, l.pf, l.min
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            JOIN Players p ON l.player_id = p.player_id
            WHERE g.game_date = ?
            """,
            (date_str,),
        ).fetchall()
        conn.close()

        if not rows:
            return {}

        lookup: dict = {}
        for row in rows:
            d = dict(row)
            first = str(d.get("first_name") or "").strip()
            last = str(d.get("last_name") or "").strip()
            pname = f"{first} {last}".lower().strip()
            if not pname:
                continue
            # Parse minutes
            min_raw = str(d.get("min") or "0")
            try:
                if ":" in min_raw:
                    mins = float(min_raw.split(":")[0])
                else:
                    mins = float(min_raw)
            except (ValueError, TypeError):
                mins = 0.0
            lookup[pname] = {
                "pts":     float(d.get("pts") or 0),
                "reb":     float(d.get("reb") or 0),
                "ast":     float(d.get("ast") or 0),
                "stl":     float(d.get("stl") or 0),
                "blk":     float(d.get("blk") or 0),
                "tov":     float(d.get("tov") or 0),
                "fg3m":    float(d.get("fg3m") or 0),
                "fg3a":    float(d.get("fg3a") or 0),
                "fgm":     float(d.get("fgm") or 0),
                "fga":     float(d.get("fga") or 0),
                "ftm":     float(d.get("ftm") or 0),
                "fta":     float(d.get("fta") or 0),
                "oreb":    float(d.get("oreb") or 0),
                "dreb":    float(d.get("dreb") or 0),
                "pf":      float(d.get("pf") or 0),
                "minutes": mins,
            }
        return lookup

    except Exception as exc:
        _logger.debug("[BetTracker] Tier 0 (ETL DB) failed for %s: %s", date_str, exc)
        return {}


def _fetch_bulk_boxscores(date_str: str) -> dict:
    """
    Orchestrator: Try Tier 0 (ETL DB), Tier 1 (nba_api BoxScore), Tier 2 (ESPN), then Tier 3 (bbref).

    Returns the first non-empty lookup dict, or {} if all tiers fail
    (callers then fall through to the legacy Tier 4 per-player path).

    Returns:
        dict: {player_name_lower: {pts, reb, ast, ...}} or {}
    """
    # ── Tier 0: ETL database (instant, no network) ───────────────────────
    lookup = _fetch_bulk_boxscores_etl(date_str)
    if lookup:
        _logger.info(
            f"[BetTracker] Tier 0 (ETL DB) succeeded for {date_str}: "
            f"{len(lookup)} players"
        )
        return lookup

    lookup = _fetch_all_boxscores_nba_api(date_str)
    if lookup:
        _logger.info(
            f"[BetTracker] Tier 1 (nba_api BoxScore) succeeded for {date_str}: "
            f"{len(lookup)} players"
        )
        return lookup

    _logger.info(
        f"[BetTracker] Tier 1 (nba_api BoxScore) empty/failed for {date_str}, "
        f"trying Tier 2 (ESPN)..."
    )
    lookup = _fetch_all_boxscores_espn(date_str)
    if lookup:
        _logger.info(
            f"[BetTracker] Tier 2 (ESPN) succeeded for {date_str}: "
            f"{len(lookup)} players"
        )
        return lookup

    _logger.info(
        f"[BetTracker] Tier 2 (ESPN) empty/failed for {date_str}, "
        f"trying Tier 3 (bbref)..."
    )
    lookup = _fetch_all_boxscores_bbref(date_str)
    if lookup:
        _logger.info(
            f"[BetTracker] Tier 3 (bbref) succeeded for {date_str}: "
            f"{len(lookup)} players"
        )
        return lookup

    _logger.info(
        f"[BetTracker] All bulk tiers failed for {date_str}, "
        f"falling through to legacy per-player path"
    )
    return {}


def _compute_actual_value_from_row(
    row: dict,
    stat_type: str,
    stat_col,
    is_combo: bool,
    is_fantasy: bool,
    combo_stats: dict,
    fantasy_scoring: dict,
    is_computed: bool = False,
) -> float:
    """
    Compute the actual stat value for a bet from a box-score row dict.

    The row dict uses our internal lowercase keys (pts, reb, ast, Ã¢â‚¬Â¦) as
    returned by _fetch_bulk_boxscores or from an API-NBA game log.

    Args:
        row: dict with internal stat keys (pts, reb, ast, stl, blk, tov, Ã¢â‚¬Â¦)
        stat_type: normalized bet stat type string
        stat_col: value from _STAT_COL for simple stats (None for combo/fantasy)
        is_combo: True if stat_type is a combo stat (PRA, P+R, etc.)
        is_fantasy: True if stat_type is a fantasy scoring stat
        combo_stats: COMBO_STATS mapping from data.platform_mappings
        fantasy_scoring: FANTASY_SCORING mapping from data.platform_mappings
        is_computed: True if stat_type is in _COMPUTED_STATS (derived value)

    Returns:
        float: computed actual stat value
    """
    if is_combo:
        return sum(
            float(row.get(_STAT_COL.get(comp, comp), 0) or 0)
            for comp in combo_stats[stat_type]
            if _STAT_COL.get(comp)
        )
    if is_fantasy:
        return round(
            sum(
                weight * float(row.get(_STAT_COL.get(comp, comp), 0) or 0)
                for comp, weight in fantasy_scoring[stat_type].items()
                if _STAT_COL.get(comp)
            ),
            2,
        )
    if is_computed:
        add_cols, sub_cols = _COMPUTED_STATS[stat_type]
        total = sum(float(row.get(c, 0) or 0) for c in add_cols)
        total -= sum(float(row.get(c, 0) or 0) for c in sub_cols)
        return total
    return float(row.get(stat_col, 0) or 0)

def _lookup_bulk_row(bulk_lookup: dict, player_name: str, normalize_fn=None) -> dict | None:
    """
    Look up a player's bulk box score row from a date-level lookup dict.

    Tries exact lowercase match first, then normalized name against both the
    raw key and normalized keys (handles suffix mismatches like "Jr." / "III").

    Args:
        bulk_lookup: {player_name_lower: stat_dict} from _fetch_bulk_boxscores
        player_name: raw player name string from the bet record
        normalize_fn: optional callable for normalizing the name (e.g. normalize_player_name)

    Returns:
        dict of stats if found, or None if not found in the lookup
    """
    pname_lower = player_name.lower().strip()
    row = bulk_lookup.get(pname_lower)
    if row is not None:
        return row

    if normalize_fn is not None:
        norm_name = normalize_fn(player_name)
        # Try normalized bet name against raw lookup keys
        row = bulk_lookup.get(norm_name)
        if row is not None:
            return row
        # Try normalized bet name against normalized lookup keys
        # (handles "jaime jaquez" matching "jaime jaquez jr." and
        #  "robert williams" matching "robert williams iii")
        for raw_key, stats in bulk_lookup.items():
            if normalize_fn(raw_key) == norm_name:
                return stats

    return None

# ============================================================
# END SECTION: 3-Tier Bulk Box Score Helpers
# ============================================================


# ============================================================
# SECTION: Bet Logging
# ============================================================

def log_new_bet(
    player_name,
    stat_type,
    prop_line,
    direction,
    platform,
    confidence_score,
    probability_over,
    edge_percentage,
    tier,
    entry_fee=0.0,
    team="",
    notes="",
    auto_logged=0,
    bet_type="normal",
    std_devs_from_line=0.0,
    source="manual",
):
    """
    Log a new bet to track its outcome later.

    Validates input, adds today's date, and saves to database.

    Args:
        player_name (str): Player name (e.g., 'LeBron James')
        stat_type (str): 'points', 'rebounds', etc.
        prop_line (float): The line being bet (e.g., 24.5)
        direction (str): 'OVER' or 'UNDER'
        platform (str): Sportsbook name (e.g., 'FanDuel', 'DraftKings')
        confidence_score (float): 0-100 model confidence
        probability_over (float): Model's P(over), 0-1
        edge_percentage (float): Edge in percentage points
        tier (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'
        entry_fee (float): Dollar amount (default 0)
        team (str): Player's team abbreviation
        notes (str): Optional notes about this pick
        auto_logged (int): 1 if logged automatically by the engine, 0 if manual
        bet_type (str): 'goblin', '50_50', 'fantasy', 'demon' (legacy), or 'normal'
        std_devs_from_line (float): How many std devs projection is from line

    Returns:
        tuple: (success: bool, message: str)

    Example:
        success, msg = log_new_bet('LeBron James', 'points',
                                    24.5, 'OVER', 'FanDuel',
                                    72.3, 0.58, 8.0, 'Gold')
    """
    # ============================================================
    # SECTION: Validate Input
    # ============================================================

    errors = []  # Collect validation errors

    # Check player name
    if not player_name or not player_name.strip():
        errors.append("Player name cannot be empty")
    elif len(player_name.strip()) > 100:
        errors.append("Player name too long (max 100 characters)")

    # Check stat type — only full-game props are supported
    if _is_segment_prop(stat_type):
        errors.append(f"'{stat_type}' is a period/segment prop — only full-game bets are supported")
    elif stat_type not in VALID_STAT_TYPES:
        errors.append(f"Invalid stat type '{stat_type}'. Must be one of: {VALID_STAT_TYPES}")

    # Check prop line
    if prop_line <= 0:
        errors.append("Prop line must be greater than 0")
    elif prop_line > 1000:
        errors.append("Prop line unreasonably large (max 1000)")

    # Check direction
    if direction not in VALID_DIRECTIONS:
        errors.append(f"Direction must be 'OVER' or 'UNDER'")

    # Sanitize string lengths
    if len(str(notes)) > 2000:
        notes = str(notes)[:2000]
    if len(str(platform)) > 100:
        platform = str(platform)[:100]
    if len(str(team)) > 10:
        team = str(team)[:10]

    # If any validation errors, return failure
    if errors:
        return False, " | ".join(errors)

    # ============================================================
    # END SECTION: Validate Input
    # ============================================================

    # ============================================================
    # SECTION: Build and Save the Bet
    # ============================================================

    # Get today's date as a string in YYYY-MM-DD format.
    # Anchor to US/Eastern: NBA game dates are defined in ET, so a bet
    # logged at 1 AM UTC for a late West Coast game is still "today" in ET.
    today_date_string = _nba_today_et().isoformat()

    # Build the bet data dictionary
    bet_data = {
        "bet_date": today_date_string,
        "player_name": player_name.strip(),
        "team": team.strip(),
        "stat_type": stat_type.lower(),
        "prop_line": float(prop_line),
        "direction": direction.upper(),
        "platform": platform,
        "confidence_score": float(confidence_score),
        "probability_over": float(probability_over),
        "edge_percentage": float(edge_percentage),
        "tier": tier,
        "entry_fee": float(entry_fee),
        "notes": notes.strip(),
        "auto_logged": int(auto_logged),
        "bet_type": str(bet_type) if bet_type else "normal",
        "std_devs_from_line": float(std_devs_from_line or 0.0),
        "source": source,
    }

    # Save to database
    new_bet_id = insert_bet(bet_data)

    if new_bet_id:
        return True, f"Bet logged successfully! Bet ID: {new_bet_id}"
    else:
        return False, "Database error Ã¢â‚¬â€ could not save bet"

    # ============================================================
    # END SECTION: Build and Save the Bet
    # ============================================================


def record_bet_result(bet_id, result, actual_value, *, closing_line=None, void_reason=None):
    """
    Record the outcome of a previously logged bet.

    Call this after the game to track model performance.

    Args:
        bet_id (int): The bet's database ID
        result (str): 'WIN', 'LOSS', or 'EVEN'
        actual_value (float): What the player actually scored

    Returns:
        tuple: (success: bool, message: str)

    Example:
        record_bet_result(42, 'WIN', 27.3)
        # LeBron scored 27.3 vs 24.5 line Ã¢â€ â€™ WIN!
    """
    # Validate the result value
    if result.upper() not in VALID_RESULTS:
        return False, f"Result must be WIN, LOSS, EVEN, or VOID (got '{result}')"

    try:
        from tracking.database import update_bet_resolution_full
        success, _msg = update_bet_resolution_full(
            bet_id, result.upper(), float(actual_value),
            closing_line=closing_line, void_reason=void_reason,
        )
    except Exception as exc:
        _logger.warning('[BetTracker] full resolution unavailable, falling back: %s', exc)
        success = update_bet_result(bet_id, result.upper(), float(actual_value))

    if success:
        # Sync result to matching all_analysis_picks row
        try:
            from tracking.database import _db_read as _tdb_read, sync_picks_with_bet_result
            bet_rows = _tdb_read(
                "SELECT bet_date, player_name, stat_type, prop_line, direction FROM bets WHERE bet_id = ?",
                (bet_id,),
            )
            if bet_rows:
                b = bet_rows[0]
                sync_picks_with_bet_result(
                    b.get("bet_date", ""), b.get("player_name", ""),
                    b.get("stat_type", ""), b.get("prop_line", 0),
                    b.get("direction", "OVER"), result.upper(), float(actual_value),
                )
        except Exception:
            pass  # Non-fatal
        return True, f"Result recorded: Bet #{bet_id} → {result.upper()}"
    else:
        return False, f"Could not update bet #{bet_id} — not found?"


# ============================================================
# END SECTION: Bet Logging
# ============================================================


# ============================================================
# SECTION: Performance Analytics
# ============================================================

def get_model_performance_stats(bets_list=None):
    """
    Get comprehensive model performance statistics.

    Analyzes win rates by tier, platform, and stat type.

    Returns:
        dict: Performance data with multiple breakdowns
    """
    # Get all bets from the database unless a scoped list was provided.
    all_bets = list(bets_list) if bets_list is not None else load_all_bets()

    # Overall summary (scoped when bets_list is provided)
    if bets_list is None:
        overall_summary = get_performance_summary()
    else:
        _resolved = [b for b in all_bets if b.get("result") in ("WIN", "LOSS", "EVEN")]
        _wins = sum(1 for b in _resolved if b.get("result") == "WIN")
        _losses = sum(1 for b in _resolved if b.get("result") == "LOSS")
        _pushes = sum(1 for b in _resolved if b.get("result") == "EVEN")
        _den = _wins + _losses
        overall_summary = {
            "total_bets": len(_resolved),
            "wins": _wins,
            "losses": _losses,
            "pushes": _pushes,
            "win_rate": round((_wins / _den) * 100, 1) if _den > 0 else 0.0,
        }

    # Break down win rate by tier
    tier_performance = _calculate_win_rate_by_field(all_bets, "tier")

    # Break down win rate by platform
    platform_performance = _calculate_win_rate_by_field(all_bets, "platform")

    # Break down win rate by stat type
    stat_performance = _calculate_win_rate_by_field(all_bets, "stat_type")

    # Break down win rate by direction (OVER vs UNDER)
    direction_performance = _calculate_win_rate_by_field(all_bets, "direction")

    # Break down win rate by Goblin / Demon / Normal bet classification
    bet_type_performance = _calculate_win_rate_by_field(all_bets, "bet_type")

    return {
        "overall": overall_summary,
        "by_tier": tier_performance,
        "by_platform": platform_performance,
        "by_bet_type": bet_type_performance,
        "by_stat_type": stat_performance,
        "by_direction": direction_performance,
        "all_bets": all_bets,
    }


def _normalize_platform_for_stats(platform_value) -> str:
    """Normalize platform naming so equivalent SmartAI/SPP labels aggregate together."""
    _plat = str(platform_value or "Unknown").strip()
    _norm = _plat.lower()
    if _norm in {"smartai-auto", "smartauto-ai", "smart pick pro", "smart pick pro platform", "smart pick pro platform picks"}:
        return "Smart Pick Pro Platform Picks"
    return _plat


def _is_smart_pick_pro_platform_pick_for_stats(bet_row: dict) -> bool:
    """Return True when a row should count as Smart Pick Pro Platform Picks."""
    _source = str(bet_row.get("source") or "").strip().lower()
    _platform = str(bet_row.get("platform") or "").strip().lower()
    _notes = str(bet_row.get("notes") or "").strip().lower()
    _auto = int(bet_row.get("auto_logged", 0) or 0) == 1

    # Hard exclusions first: never classify Joseph or Smart Money rows here.
    if _source == "joseph" or "joseph" in _platform or "joseph" in _notes:
        return False
    if "smart money" in _platform or "smart money" in _notes:
        return False

    if _source in {"qeg_auto", "smart_pick_pro", "smart_pick_pro_platform", "smartpickpro_auto"}:
        return True
    if _platform in {"smartai-auto", "smartauto-ai", "smart pick pro", "smart pick pro platform", "smart pick pro platform picks"}:
        return True
    if (
        _notes.startswith("auto-logged by smartai")
        or _notes.startswith("auto-logged by smart pick pro")
        or _notes.startswith("auto-stored by smart pick pro")
        or _notes.startswith("auto-stored by smartai")
    ):
        return True
    if _notes.startswith("added from platform props"):
        return True
    if _auto:
        return True
    return False


def _calculate_win_rate_by_field(bets_list, field_name):
    """
    Calculate win rate broken down by a specific field.

    For example, win rate per tier (Platinum, Gold, Silver, Bronze).

    Args:
        bets_list (list of dict): All bets from database
        field_name (str): The field to group by (e.g., 'tier')

    Returns:
        dict: {field_value: {'wins': int, 'total': int, 'win_rate': float}}
    """
    performance_by_group = {}  # Will hold stats for each group

    # Only consider bets that have results (skip pending bets)
    bets_with_results = [
        bet for bet in bets_list
        if bet.get("result") and bet["result"] in VALID_RESULTS
    ]

    for bet in bets_with_results:
        field_value = bet.get(field_name, "Unknown")
        if field_name == "platform":
            if _is_smart_pick_pro_platform_pick_for_stats(bet):
                field_value = "Smart Pick Pro Platform Picks"
            else:
                field_value = _normalize_platform_for_stats(field_value)

        # Initialize this group if we haven't seen it.
        if field_value not in performance_by_group:
            performance_by_group[field_value] = {"wins": 0, "losses": 0, "total": 0}

        # Keep "total" aligned with win-rate denominator: decided bets only.
        if bet["result"] == "WIN":
            performance_by_group[field_value]["wins"] += 1
            performance_by_group[field_value]["total"] += 1
        elif bet["result"] == "LOSS":
            performance_by_group[field_value]["losses"] += 1
            performance_by_group[field_value]["total"] += 1

    # Calculate win rates for each group
    # Use wins / (wins + losses) Ã¢â‚¬â€ evens should NOT deflate the rate
    for group_data in performance_by_group.values():
        decided = group_data["wins"] + group_data["losses"]
        if decided > 0:
            group_data["win_rate"] = round(group_data["wins"] / decided * 100, 1)
        else:
            group_data["win_rate"] = 0.0

    return performance_by_group

# ============================================================
# END SECTION: Performance Analytics
# ============================================================


# ============================================================
# SECTION: Auto-Log Analysis Results
# ============================================================

_MAX_UNCERTAIN_REASONS = 2   # max risk_flags to include in notes for uncertain picks

def auto_log_analysis_bets(analysis_results, minimum_edge=5.0, max_bets=15, *, source="quantum", log_all=False):
    """
    Automatically log bet records for analysis results that have a positive
    edge in the model's recommended direction.

    Call this after Neural Analysis completes to populate the Bet Tracker
    with tonight's picks without any manual entry.

    Deduplication: a bet for the same (player, stat, line, direction, date)
    that was already logged today is skipped so re-running analysis does
    not create duplicate rows.  Only today's bets are loaded for the
    deduplication check to keep the query fast regardless of history size.

    Args:
        analysis_results (list[dict]): Full analysis result list from the
            Neural Analysis engine (as stored in session_state).
        minimum_edge (float): Fallback minimum edge for any tier not found
            in the per-tier threshold dict (unusual/custom tiers).
            Standard tiers use values from config.thresholds:
            Platinum ≥1%, Gold ≥2%, Silver ≥3%, Bronze ≥3%.
            Only picks with edge > 0 are ever logged.
            Ignored when log_all=True.
        max_bets (int): Maximum number of new bets to log in a single
            analysis run. Defaults to 15.
        source (str): System tag stored in `bets.source` so the tracker
            can split performance per system. One of:
            ``"quantum"`` (QAM full slate), ``"qeg"`` (Quantum Edge Gap),
            ``"smart_money"`` (Smart Money Bets), ``"platform_ai"``
            (Platform AI / Live Games Neural Analysis).
            Defaults to ``"quantum"``.
        log_all (bool): When True, skip all edge/tier threshold filtering
            and log every pick in analysis_results (still deduplicates).
            Use this when the full slate should be tracked regardless of
            edge quality (e.g. QAM full-slate logging). Defaults to False.

    Returns:
        int: Number of new bets logged.
    """
    import sqlite3 as _sqlite3
    import datetime as _dt
    from tracking.database import DB_FILE_PATH as _DB_PATH

    if not analysis_results:
        return 0

    today_str = _nba_today_et().isoformat()

    # Build today-scoped deduplication set.  Use _db_read so it works on
    # PostgreSQL (Railway) as well as local SQLite -- raw sqlite3.connect
    # would always read zero rows on Railway and create duplicates.
    # Dedup is source-scoped: only skip picks already logged with the SAME
    # source so that platform_ai and quantum can each log their own rows for
    # the same pick without blocking each other.
    existing_keys: set = set()
    try:
        from tracking.database import _db_read as _tdb_read
        _rows = _tdb_read(
            "SELECT player_name, stat_type, prop_line, direction FROM bets WHERE bet_date = ? AND source = ?",
            (today_str, source),
        )
        existing_keys = {
            (row["player_name"].lower(), row["stat_type"], float(row["prop_line"] or 0), row["direction"])
            for row in _rows
        }
    except Exception:
        pass  # If query fails, log without dedup (safe -- unique index protects)

    logged = 0
    # All tiers qualify for auto-logging.
    AUTO_LOG_TIERS = {"Gold", "Platinum", "Silver", "Bronze"}
    # Per-tier minimum edge requirements loaded from thresholds (single source of truth)
    try:
        from config.thresholds import (
            PLATINUM_AUTO_LOG_MIN_EDGE as _PT_EDGE,
            GOLD_AUTO_LOG_MIN_EDGE     as _GD_EDGE,
            SILVER_AUTO_LOG_MIN_EDGE   as _SV_EDGE,
            BRONZE_AUTO_LOG_MIN_EDGE   as _BZ_EDGE,
        )
    except ImportError:
        _PT_EDGE, _GD_EDGE, _SV_EDGE, _BZ_EDGE = 1.0, 2.0, 3.0, 3.0
    _TIER_MIN_EDGE = {
        "Platinum": _PT_EDGE,
        "Gold":     _GD_EDGE,
        "Silver":   _SV_EDGE,
        "Bronze":   _BZ_EDGE,
    }

    # Sort by confidence score descending so the highest-quality picks are logged first
    sorted_results = sorted(
        analysis_results,
        key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )

    for res in sorted_results:
        if logged >= max_bets:
            break
        edge = res.get("edge_percentage", 0)
        tier = res.get("tier", "Bronze")
        confidence = res.get("confidence_score", 0)
        bet_type = res.get("bet_type", "standard")
        stat_type = res.get("stat_type", "points")
        # Auto-classify fantasy score props as "fantasy" bet type
        if stat_type in FANTASY_STAT_TYPES:
            bet_type = "fantasy"
        if res.get("player_is_out", False):
            continue
        # When log_all=True, skip all edge/tier threshold checks so the
        # full QAM slate is tracked regardless of edge quality.
        if not log_all:
            if edge <= 0:
                continue
            # Only auto-log recognised tiers
            if tier not in AUTO_LOG_TIERS:
                continue
            # Apply tier-specific minimum edge thresholds (sourced from config.thresholds)
            min_required_edge = _TIER_MIN_EDGE.get(tier, minimum_edge)
            if edge < min_required_edge:
                continue

        dedup_key = (
            res.get("player_name", "").lower(),
            res.get("stat_type", ""),
            float(res.get("line", 0) or 0),
            res.get("direction", "OVER"),
        )
        if dedup_key in existing_keys:
            continue

        ok, _msg = log_new_bet(
            player_name=res.get("player_name", ""),
            stat_type=res.get("stat_type", "points"),
            prop_line=float(res.get("line", 0) or 0),
            direction=res.get("direction", "OVER"),
            platform=res.get("platform") or "SmartAI-Auto",
            confidence_score=float(res.get("confidence_score", 0) or 0),
            probability_over=float(res.get("probability_over", 0.5) or 0.5),
            edge_percentage=float(edge),
            tier=res.get("tier", "Bronze"),
            team=res.get("player_team", res.get("team", "")),
            notes=(
                f"Auto-logged by SmartAI. "
                f"SAFE Score: {res.get('confidence_score', 0):.0f}. "
                + (
                    " | ".join(
                        (res.get("risk_flags") or [])[:_MAX_UNCERTAIN_REASONS]
                    )
                    if res.get("risk_flags")
                    else ""
                )
            ),
            auto_logged=1,
            bet_type=bet_type,
            std_devs_from_line=float(res.get("std_devs_from_line", 0.0)),
            source=source,
        )
        if ok:
            existing_keys.add(dedup_key)
            logged += 1

    # ── Log all avoid/risky picks regardless of tier/edge thresholds ──────────
    # When log_all=True the main loop already processed every pick, so this
    # extra pass is skipped to avoid double-logging.
    if not log_all:
        for res in sorted_results:
            if not res.get("should_avoid", False):
                continue
            if res.get("player_is_out", False):
                continue
            dedup_key = (
                res.get("player_name", "").lower(),
                res.get("stat_type", ""),
                float(res.get("line", 0) or 0),
                res.get("direction", "OVER"),
            )
            if dedup_key in existing_keys:
                continue
            avoid_reasons = res.get("avoid_reasons") or []
            ok, _msg = log_new_bet(
                player_name=res.get("player_name", ""),
                stat_type=res.get("stat_type", "points"),
                prop_line=float(res.get("line", 0) or 0),
                direction=res.get("direction", "OVER"),
                platform=res.get("platform") or "SmartAI-Auto",
                confidence_score=float(res.get("confidence_score", 0) or 0),
                probability_over=float(res.get("probability_over", 0.5) or 0.5),
                edge_percentage=float(res.get("edge_percentage", 0) or 0),
                tier=res.get("tier", "Bronze"),
                team=res.get("player_team", res.get("team", "")),
                notes=(
                    "⚠️ RISKY/AVOID pick — Auto-logged for tracking. "
                    + (" | ".join(avoid_reasons[:3]) if avoid_reasons else "")
                ),
                auto_logged=1,
                bet_type="risky",
                std_devs_from_line=float(res.get("std_devs_from_line", 0.0)),
                source=source,
            )
            if ok:
                existing_keys.add(dedup_key)
                logged += 1

    return logged

# ============================================================
# END SECTION: Auto-Log Analysis Results
# ============================================================



def auto_resolve_bet_results(date_str=None):
    """
    For all pending bets on date_str (default: yesterday), retrieve actual
    player stats from API-NBA API and automatically mark WIN/LOSS/EVEN.

    Uses the ETL database (primary) or nba_api PlayerGameLog (fallback) to
    get actual stat values. Player IDs are resolved via
    data.player_profile_service.get_player_id().

    Args:
        date_str (str|None): ISO date string "YYYY-MM-DD".
                             Defaults to yesterday if None.

    Returns:
        tuple: (resolved_count: int, errors_list: list[str])
    """
    import datetime as _dt

    if date_str is None:
        # Anchor to US/Eastern Ã¢â‚¬â€ NBA game dates are defined in ET.
        _today_et = _nba_today_et()
        date_str = (_today_et - _dt.timedelta(days=1)).isoformat()

    resolved_count = 0
    errors_list = []

    # Load all pending bets for the target date (include parlay legs)
    all_bets = load_all_bets(exclude_linked=False)
    pending_bets = [
        b for b in all_bets
        if b.get("bet_date", "") == date_str and not b.get("result")
    ]

    if not pending_bets:
        return 0, [f"No pending bets found for {date_str}"]

    # Import combo/fantasy stat definitions and name normalizer
    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None
    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    # Player ID lookup: API-NBA API Ã¢â€ â€™ nba_api static list (local, no network)
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    # Target date as a date object (for robust date comparison)
    target_date = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()

    # Ã¢â€â‚¬Ã¢â€â‚¬ Pre-validate bets and collect unique player names Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _bet_prep = []  # (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line)
    _names_to_load: set = set()

    for bet in pending_bets:
        bet_id      = bet.get("bet_id")
        player_name = _clean_player_name(bet.get("player_name", ""))
        stat_type   = bet.get("stat_type", "").lower()
        prop_line   = float(bet.get("prop_line", 0) or 0)
        direction   = (bet.get("direction") or "OVER").upper()

        # Determine how to compute actual_value for this stat_type
        is_combo   = stat_type in COMBO_STATS
        is_fantasy = stat_type in FANTASY_SCORING
        is_computed = stat_type in _COMPUTED_STATS
        stat_col   = _STAT_COL.get(stat_type)

        # Fallback: try normalizing the platform-native name to an internal key
        if not stat_col and not is_combo and not is_fantasy and not is_computed and _norm_stat_type is not None:
            normalized = _norm_stat_type(stat_type)
            stat_col = _STAT_COL.get(normalized)
            if stat_col:
                stat_type = normalized
            elif normalized in COMBO_STATS:
                is_combo = True
                stat_type = normalized
            elif normalized in FANTASY_SCORING:
                is_fantasy = True
                stat_type = normalized
            elif normalized in _COMPUTED_STATS:
                is_computed = True
                stat_type = normalized

        if not stat_col and not is_combo and not is_fantasy and not is_computed:
            if _is_segment_prop(stat_type) or stat_type in _UNRESOLVABLE_STATS:
                _label = "period prop" if _is_segment_prop(stat_type) else "unresolvable"
                update_bet_result(bet_id, "VOID", 0.0)
                resolved_count += 1
                errors_list.append(
                    f"#{bet_id} {player_name}: '{stat_type}' {_label} \u2014 auto-VOID"
                )
                continue
            errors_list.append(f"#{bet_id} {player_name}: unknown stat type '{stat_type}'")
            continue

        _names_to_load.add(player_name)
        _bet_prep.append((bet, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line))

    if not _bet_prep:
        return resolved_count, errors_list

    # Ã¢â€â‚¬Ã¢â€â‚¬ Resolve player names Ã¢â€ â€™ API-NBA player IDs Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    # get_player_id() checks: cache Ã¢â€ â€™ API-NBA API Ã¢â€ â€™ nba_api static (local)
    _name_to_pid: dict = {}
    for pname in _names_to_load:
        if _lookup_pid is not None:
            pid = _lookup_pid(pname)
            # Also try normalized form (handles unicode/suffix differences)
            if not pid:
                pid = _lookup_pid(_normalize_name(pname))
        else:
            pid = None
        _name_to_pid[pname] = pid

    # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 1+2: Try bulk box score fetch Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _bulk_lookup = _fetch_bulk_boxscores(date_str)

    # Ã¢â€â‚¬Ã¢â€â‚¬ Retrieve game logs in parallel using ThreadPoolExecutor Ã¢â€â‚¬Ã¢â€â‚¬
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time

    # Group: player_name Ã¢â€ â€™ player_id (or None)
    _ids_to_load = {
        pid for pid in _name_to_pid.values() if pid
    }
    _game_log_cache: dict = {}  # player_id Ã¢â€ â€™ list[dict] of API-NBA game log rows

    def _get_player_log(pid):
        """Retrieve a single player's game log with retry + backoff."""
        for _attempt in range(RESOLVE_MAX_RETRIES):
            try:
                if _attempt > 0:
                    _time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                logs = _fetch_resolve_game_log(pid, last_n=5)
                return pid, logs
            except Exception:
                if _attempt == RESOLVE_MAX_RETRIES - 1:
                    return pid, []
        return pid, []

    _unique_ids = list(_ids_to_load)
    with ThreadPoolExecutor(max_workers=min(8, len(_unique_ids) or 1)) as executor:
        futures = {executor.submit(_get_player_log, pid): pid for pid in _unique_ids}
        for future in as_completed(futures):
            pid = futures[future]
            try:
                _, logs_result = future.result()
                _game_log_cache[pid] = logs_result or []
            except Exception:
                _game_log_cache[pid] = []

    _tier12_resolved = 0

    # Ã¢â€â‚¬Ã¢â€â‚¬ Resolve bets from cached game logs Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    for (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line) in _bet_prep:
        bet_id = bet.get("bet_id")

        try:
            # Ã¢â€â‚¬Ã¢â€â‚¬ Try Tier 1/2 bulk lookup first Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            bulk_row = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name)

            if bulk_row is not None:
                actual_value = _compute_actual_value_from_row(
                    bulk_row, stat_type, stat_col, is_combo, is_fantasy,
                    COMBO_STATS, FANTASY_SCORING, is_computed=is_computed,
                )
                if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                    result = "EVEN"
                elif direction == "OVER":
                    result = "WIN" if actual_value > prop_line else "LOSS"
                else:  # UNDER
                    result = "WIN" if actual_value < prop_line else "LOSS"
                success, msg = record_bet_result(bet_id, result, actual_value)
                if success:
                    resolved_count += 1
                    _tier12_resolved += 1
                else:
                    errors_list.append(f"#{bet_id} {player_name}: DB update failed Ã¢â‚¬â€ {msg}")
                continue  # Skip Tier 3 for this bet

            # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 3: Legacy per-player game log path Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            player_id = _name_to_pid.get(player_name)
            if not player_id:
                errors_list.append(f"#{bet_id} {player_name}: player ID not found")
                continue

            logs = _game_log_cache.get(player_id, [])
            if not logs:
                # Only VOID if the player IS in the bulk lookup (their game
                # has real data but they recorded 0 min — true DNP).
                # If they're simply absent from the lookup, their game's data
                # may not be ready yet — leave as pending.
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    success, msg = record_bet_result(bet_id, "VOID", 0.0)
                    if success:
                        resolved_count += 1
                    else:
                        errors_list.append(f"#{bet_id} {player_name}: VOID update failed — {msg}")
                else:
                    errors_list.append(f"#{bet_id} {player_name}: no game log found (game data may not be ready)")
                continue

            # Find the game on target date
            matching_log = None
            for log_row in logs:
                log_date = _parse_game_date(log_row.get("game_date", ""))
                if log_date == target_date:
                    matching_log = log_row
                    break

            if matching_log is None:
                # Only VOID if the player IS in the bulk lookup (confirmed
                # their game was played but they have no log entry — true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    success, msg = record_bet_result(bet_id, "VOID", 0.0)
                    if success:
                        resolved_count += 1
                    else:
                        errors_list.append(f"#{bet_id} {player_name}: VOID update failed — {msg}")
                else:
                    last_date = logs[0].get("game_date", "N/A") if logs else "N/A"
                    errors_list.append(
                        f"#{bet_id} {player_name}: no game found on {date_str} "
                        f"(last game: {last_date})"
                    )
                continue

            # Compute actual_value based on stat type
            if is_combo:
                components = COMBO_STATS[stat_type]
                actual_value = sum(
                    float(matching_log.get(_STAT_COL.get(comp, comp), 0) or 0)
                    for comp in components
                    if comp in _STAT_COL
                )
            elif is_fantasy:
                formula = FANTASY_SCORING[stat_type]
                actual_value = sum(
                    weight * float(matching_log.get(_STAT_COL.get(comp, comp), 0) or 0)
                    for comp, weight in formula.items()
                    if comp in _STAT_COL
                )
                actual_value = round(actual_value, 2)
            elif is_computed:
                add_cols, sub_cols = _COMPUTED_STATS[stat_type]
                actual_value = sum(float(matching_log.get(c, 0) or 0) for c in add_cols)
                actual_value -= sum(float(matching_log.get(c, 0) or 0) for c in sub_cols)
            else:
                actual_value = float(matching_log.get(stat_col, 0) or 0)

            # Determine WIN / LOSS / EVEN
            if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                result = "EVEN"
            elif direction == "OVER":
                result = "WIN" if actual_value > prop_line else "LOSS"
            else:  # UNDER
                result = "WIN" if actual_value < prop_line else "LOSS"

            success, msg = record_bet_result(bet_id, result, actual_value)
            if success:
                resolved_count += 1
            else:
                errors_list.append(f"#{bet_id} {player_name}: DB update failed Ã¢â‚¬â€ {msg}")

        except Exception as exc:
            errors_list.append(f"#{bet_id} {player_name}: {exc}")

    if _tier12_resolved:
        _logger.info(
            f"[BetTracker] auto_resolve_bet_results: resolved {_tier12_resolved} bet(s) "
            f"via Tier 1/2 (bulk BoxScore) for {date_str}"
        )

    # Auto-update daily snapshot after resolution
    if resolved_count > 0:
        try:
            from tracking.database import save_daily_snapshot as _save_snapshot
            _save_snapshot(date_str)
        except Exception as _snap_exc:
            _logger.debug("auto_resolve_bet_results: snapshot update failed: %s", _snap_exc)

    return resolved_count, errors_list

# ============================================================
# END SECTION: Auto-Resolve
# ============================================================


def resolve_todays_bets():
    """
    Resolve today's pending bets by checking live game status via API-NBA API.

    Uses bulk nba_api BoxScore endpoints for Tier 1/2 resolution,
    then the ETL database or nba_api PlayerGameLog for Tier 3.
    Player IDs are resolved via data.player_profile_service.get_player_id().

    Returns:
        dict: {
            "resolved": int,
            "wins": int,
            "losses": int,
            "evens": int,
            "pending": int,
            "errors": list[str],
        }
    """
    import datetime as _dt
    from tracking.database import (
        load_all_bets,
        update_bet_result,
        save_daily_snapshot,
    )

    today_str = _nba_today_et().isoformat()
    summary = {"resolved": 0, "wins": 0, "losses": 0, "evens": 0, "pending": 0, "errors": []}

    try:
        all_bets = load_all_bets(exclude_linked=False)
        todays_pending = [
            b for b in all_bets
            if b.get("bet_date") == today_str and not b.get("result")
        ]
    except Exception as exc:
        summary["errors"].append(f"Failed to load bets: {exc}")
        return summary

    if not todays_pending:
        return summary

    # Import combo/fantasy stat definitions
    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    # Normalizer for fuzzy matching
    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return str(n).lower().strip()

    # Player ID lookup via API-NBA Ã¢â€ â€™ nba_api static list (local)
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    # Ã¢â€â‚¬Ã¢â€â‚¬ Check live scores for finished games via ESPN Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _scoreboard_available = False
    has_final_games = False
    try:
        import requests
        try:
            from utils.headers import get_espn_headers
            _sb_headers = get_espn_headers()
        except ImportError:
            _sb_headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        _espn_date = today_str.replace("-", "")
        _sb_url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
            f"?dates={_espn_date}"
        )
        _sb_resp = requests.get(_sb_url, headers=_sb_headers, timeout=10)
        _sb_resp.raise_for_status()
        _sb_data = _sb_resp.json()
        _sb_events = _sb_data.get("events", [])
        _scoreboard_available = True
        has_final_games = any(
            str(ev.get("status", {}).get("type", {}).get("id", "")) == "3"
            for ev in _sb_events
        )
    except Exception as _sb_exc:
        _logger.debug(f"[BetTracker] ESPN scoreboard check failed: {_sb_exc}")

    # Short-circuit: if the scoreboard responded but no games are Final yet,
    # skip the expensive per-player API calls and tell the user clearly.
    if _scoreboard_available and not has_final_games:
        summary["pending"] = len(todays_pending)
        summary["errors"].append(
            "No games are Final yet today Ã¢â‚¬â€ try again after today's games finish."
        )
        return summary

    target_date = _dt.datetime.strptime(today_str, "%Y-%m-%d").date()

    # Ã¢â€â‚¬Ã¢â€â‚¬ Pre-validate bets and collect unique player names Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _bet_prep = []  # (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line)
    _names_to_load: set = set()

    for bet in todays_pending:
        bet_id      = bet.get("id") or bet.get("bet_id")
        player_name = _clean_player_name(bet.get("player_name", ""))
        stat_type   = str(bet.get("stat_type", "")).lower()
        prop_line   = float(bet.get("prop_line") or 0)
        direction   = str(bet.get("direction") or "OVER").upper()

        is_combo   = stat_type in COMBO_STATS
        is_fantasy = stat_type in FANTASY_SCORING
        is_computed = stat_type in _COMPUTED_STATS
        stat_col   = _STAT_COL.get(stat_type)

        # Fallback: try normalizing the platform-native name to an internal key
        if not stat_col and not is_combo and not is_fantasy and not is_computed and _norm_stat_type is not None:
            normalized = _norm_stat_type(stat_type)
            stat_col = _STAT_COL.get(normalized)
            if stat_col:
                stat_type = normalized
            elif normalized in COMBO_STATS:
                is_combo = True
                stat_type = normalized
            elif normalized in FANTASY_SCORING:
                is_fantasy = True
                stat_type = normalized
            elif normalized in _COMPUTED_STATS:
                is_computed = True
                stat_type = normalized

        if not stat_col and not is_combo and not is_fantasy and not is_computed:
            if _is_segment_prop(stat_type):
                summary["errors"].append(
                    f"#{bet_id} {player_name}: '{stat_type}' is a game-segment prop Ã¢â‚¬â€ "
                    f"cannot resolve from full-game box score"
                )
            elif stat_type in _UNRESOLVABLE_STATS:
                summary["errors"].append(
                    f"#{bet_id} {player_name}: '{stat_type}' is not available in "
                    f"standard box scores Ã¢â‚¬â€ cannot auto-resolve"
                )
            else:
                summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
            summary["pending"] += 1
            continue

        _names_to_load.add(player_name)
        _bet_prep.append((bet, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line))

    if not _bet_prep:
        return summary

    # Ã¢â€â‚¬Ã¢â€â‚¬ Resolve player names Ã¢â€ â€™ player IDs Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _name_to_pid: dict = {}
    for pname in _names_to_load:
        pid = None
        if _lookup_pid is not None:
            pid = _lookup_pid(pname)
            if not pid:
                pid = _lookup_pid(_normalize_name(pname))
        _name_to_pid[pname] = pid

    # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 1+2: Try bulk box score fetch Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    _bulk_lookup = _fetch_bulk_boxscores(today_str)

    # Ã¢â€â‚¬Ã¢â€â‚¬ Retrieve game logs in parallel using ThreadPoolExecutor Ã¢â€â‚¬Ã¢â€â‚¬
    from concurrent.futures import ThreadPoolExecutor, as_completed

    _ids_to_load = {pid for pid in _name_to_pid.values() if pid}
    _game_log_cache: dict = {}  # player_id Ã¢â€ â€™ list[dict] of API-NBA game log rows

    def _get_player_log(pid):
        """Retrieve a single player's game log with retry + backoff."""
        for _attempt in range(RESOLVE_MAX_RETRIES):
            try:
                if _attempt > 0:
                    time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                logs = _fetch_resolve_game_log(pid, last_n=5)
                return pid, logs
            except Exception as _retry_exc:
                _logger.warning(
                    f"  resolve_todays_bets: attempt {_attempt+1}/{RESOLVE_MAX_RETRIES} "
                    f"failed for player_id={pid}: {_retry_exc}"
                )
                if _attempt == RESOLVE_MAX_RETRIES - 1:
                    return pid, []
        return pid, []

    _unique_ids = list(_ids_to_load)
    if _unique_ids:
        with ThreadPoolExecutor(max_workers=min(8, len(_unique_ids))) as executor:
            futures = {executor.submit(_get_player_log, pid): pid for pid in _unique_ids}
            for future in as_completed(futures):
                pid = futures[future]
                try:
                    _, log_data = future.result()
                    _game_log_cache[pid] = log_data or []
                except Exception:
                    _game_log_cache[pid] = []

    _tier12_resolved = 0

    # Ã¢â€â‚¬Ã¢â€â‚¬ Resolve bets from cached game logs Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    for (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line) in _bet_prep:
        bet_id = bet.get("id") or bet.get("bet_id")

        try:
            # Ã¢â€â‚¬Ã¢â€â‚¬ Try Tier 1/2 bulk lookup first Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            bulk_row = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name)

            if bulk_row is not None:
                actual_value = _compute_actual_value_from_row(
                    bulk_row, stat_type, stat_col, is_combo, is_fantasy,
                    COMBO_STATS, FANTASY_SCORING, is_computed=is_computed,
                )
                if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                    result = "EVEN"
                elif direction == "OVER":
                    result = "WIN" if actual_value > prop_line else "LOSS"
                else:  # UNDER
                    result = "WIN" if actual_value < prop_line else "LOSS"
                success = update_bet_result(bet_id, result, actual_value)
                if success:
                    summary["resolved"] += 1
                    _tier12_resolved += 1
                    if result == "WIN":
                        summary["wins"] += 1
                    elif result == "LOSS":
                        summary["losses"] += 1
                    else:
                        summary["evens"] += 1
                else:
                    summary["errors"].append(f"#{bet_id} {player_name}: DB update failed")
                    summary["pending"] += 1
                continue  # Skip Tier 3 for this bet

            # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 3: Legacy per-player game log path Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            player_id = _name_to_pid.get(player_name)
            if not player_id:
                summary["errors"].append(f"#{bet_id} {player_name}: player ID not found")
                summary["pending"] += 1
                continue

            logs = _game_log_cache.get(player_id, [])
            if not logs:
                # Only VOID if player IS in the bulk lookup (true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    ok = update_bet_result(bet_id, "VOID", 0.0)
                    if ok:
                        summary["resolved"] += 1
                    else:
                        summary["errors"].append(f"#{bet_id} {player_name}: VOID update failed")
                        summary["pending"] += 1
                else:
                    summary["pending"] += 1
                continue

            # Find the game log entry for today
            latest = None
            for log_row in logs:
                log_date = _parse_game_date(log_row.get("game_date", ""))
                if log_date == target_date:
                    latest = log_row
                    break

            if latest is None:
                # Only VOID if player IS in the bulk lookup (true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    ok = update_bet_result(bet_id, "VOID", 0.0)
                    if ok:
                        summary["resolved"] += 1
                    else:
                        summary["errors"].append(f"#{bet_id} {player_name}: VOID update failed")
                        summary["pending"] += 1
                else:
                    summary["pending"] += 1
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ Compute actual value Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            if is_combo:
                component_keys = COMBO_STATS.get(stat_type, [])
                actual_value = sum(
                    float(latest.get(_STAT_COL.get(k, k), 0) or 0)
                    for k in component_keys
                    if _STAT_COL.get(k)
                )
            elif is_fantasy:
                scoring_weights = FANTASY_SCORING.get(stat_type, {})
                actual_value = sum(
                    float(latest.get(_STAT_COL.get(col, col), 0) or 0) * mult
                    for col, mult in scoring_weights.items()
                    if _STAT_COL.get(col)
                )
            elif is_computed:
                add_cols, sub_cols = _COMPUTED_STATS[stat_type]
                actual_value = sum(float(latest.get(c, 0) or 0) for c in add_cols)
                actual_value -= sum(float(latest.get(c, 0) or 0) for c in sub_cols)
            else:
                actual_value = float(latest.get(stat_col, 0) or 0)

            # Ã¢â€â‚¬Ã¢â€â‚¬ Determine WIN / LOSS / EVEN Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                result = "EVEN"
            elif direction == "OVER":
                result = "WIN" if actual_value > prop_line else "LOSS"
            else:  # UNDER
                result = "WIN" if actual_value < prop_line else "LOSS"

            success = update_bet_result(bet_id, result, actual_value)
            if success:
                summary["resolved"] += 1
                if result == "WIN":
                    summary["wins"] += 1
                elif result == "LOSS":
                    summary["losses"] += 1
                else:
                    summary["evens"] += 1
            else:
                summary["errors"].append(f"#{bet_id} {player_name}: DB update failed")
                summary["pending"] += 1

        except Exception as exc:
            summary["errors"].append(f"{player_name}: {exc}")
            summary["pending"] += 1

    if _tier12_resolved:
        _logger.info(
            f"[BetTracker] resolve_todays_bets: resolved {_tier12_resolved} bet(s) "
            f"via Tier 1/2 (bulk BoxScore) for {today_str}"
        )

    # Auto-save daily snapshot after resolving
    if summary["resolved"] > 0:
        try:
            save_daily_snapshot(today_str)
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    # Count remaining unresolved bets
    try:
        remaining = load_all_bets(exclude_linked=False)
        summary["pending"] = sum(
            1 for b in remaining
            if b.get("bet_date") == today_str and not b.get("result")
        )
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    return summary


def regrade_bets_for_date(date_str=None):
    """
    Recompute results for already-graded bets on a date using final box scores.

    This is a corrective pass for cases where a bet may have been graded with
    in-progress stats. Only bets currently marked WIN/LOSS/EVEN are considered.

    Args:
        date_str (str|None): ISO date string YYYY-MM-DD. Defaults to today (ET).

    Returns:
        dict: {
            "date": str,
            "total_candidates": int,
            "checked": int,
            "corrected": int,
            "unchanged": int,
            "skipped": int,
            "errors": list[str],
            "changes": list[dict],
        }
    """
    import datetime as _dt
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if date_str is None:
        date_str = _nba_today_et().isoformat()

    summary = {
        "date": date_str,
        "total_candidates": 0,
        "checked": 0,
        "corrected": 0,
        "unchanged": 0,
        "skipped": 0,
        "errors": [],
        "changes": [],
    }

    try:
        target_date = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        summary["errors"].append(f"Invalid date format: {date_str}")
        return summary

    all_bets = load_all_bets(exclude_linked=False)
    candidates = [
        b for b in all_bets
        if b.get("bet_date") == date_str and b.get("result") in ("WIN", "LOSS", "EVEN")
    ]
    summary["total_candidates"] = len(candidates)
    if not candidates:
        return summary

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return str(n).lower().strip()

    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    _bulk_lookup = _fetch_bulk_boxscores(date_str)

    _names_to_load: set[str] = set()
    _bet_prep = []  # (bet, bet_id, player_name, stat_type, stat_col, is_combo, is_fantasy, is_computed, direction, prop_line, old_result, old_actual)

    for bet in candidates:
        bet_id = bet.get("bet_id") or bet.get("id")
        player_name = str(bet.get("player_name") or "").strip()
        stat_type = str(bet.get("stat_type") or "").lower().strip()
        direction = str(bet.get("direction") or "OVER").upper().strip()
        old_result = str(bet.get("result") or "").upper().strip()
        try:
            prop_line = float(bet.get("prop_line") or 0)
        except (TypeError, ValueError):
            prop_line = 0.0
        try:
            old_actual = float(bet.get("actual_value") or 0)
        except (TypeError, ValueError):
            old_actual = 0.0

        is_combo = stat_type in COMBO_STATS
        is_fantasy = stat_type in FANTASY_SCORING
        is_computed = stat_type in _COMPUTED_STATS
        stat_col = _STAT_COL.get(stat_type)

        if not stat_col and not is_combo and not is_fantasy and not is_computed and _norm_stat_type is not None:
            normalized = _norm_stat_type(stat_type)
            stat_col = _STAT_COL.get(normalized)
            if stat_col:
                stat_type = normalized
            elif normalized in COMBO_STATS:
                is_combo = True
                stat_type = normalized
            elif normalized in FANTASY_SCORING:
                is_fantasy = True
                stat_type = normalized
            elif normalized in _COMPUTED_STATS:
                is_computed = True
                stat_type = normalized

        if not stat_col and not is_combo and not is_fantasy and not is_computed:
            summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
            summary["skipped"] += 1
            continue

        _bet_prep.append((
            bet,
            bet_id,
            player_name,
            stat_type,
            stat_col,
            is_combo,
            is_fantasy,
            is_computed,
            direction,
            prop_line,
            old_result,
            old_actual,
        ))
        _names_to_load.add(player_name)

    _name_to_pid: dict = {}
    for pname in _names_to_load:
        pid = None
        if _lookup_pid is not None:
            pid = _lookup_pid(pname) or _lookup_pid(_normalize_name(pname))
        _name_to_pid[pname] = pid

    _ids_to_load = {pid for pid in _name_to_pid.values() if pid}
    _game_log_cache: dict = {}

    def _get_player_log(pid):
        for _attempt in range(RESOLVE_MAX_RETRIES):
            try:
                if _attempt > 0:
                    time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                logs = _fetch_resolve_game_log(pid, last_n=10)
                return pid, logs
            except Exception:
                if _attempt == RESOLVE_MAX_RETRIES - 1:
                    return pid, []
        return pid, []

    _unique_ids = list(_ids_to_load)
    if _unique_ids:
        with ThreadPoolExecutor(max_workers=min(8, len(_unique_ids))) as executor:
            futures = {executor.submit(_get_player_log, pid): pid for pid in _unique_ids}
            for future in as_completed(futures):
                pid = futures[future]
                try:
                    _, logs = future.result()
                    _game_log_cache[pid] = logs or []
                except Exception:
                    _game_log_cache[pid] = []

    for (
        _bet,
        bet_id,
        player_name,
        stat_type,
        stat_col,
        is_combo,
        is_fantasy,
        is_computed,
        direction,
        prop_line,
        old_result,
        old_actual,
    ) in _bet_prep:
        actual_value = None

        try:
            bulk_row = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name)
            if bulk_row is not None:
                actual_value = _compute_actual_value_from_row(
                    bulk_row,
                    stat_type,
                    stat_col,
                    is_combo,
                    is_fantasy,
                    COMBO_STATS,
                    FANTASY_SCORING,
                    is_computed=is_computed,
                )
            else:
                pid = _name_to_pid.get(player_name)
                logs = _game_log_cache.get(pid, []) if pid else []
                matching_log = None
                for log_row in logs:
                    log_date = _parse_game_date(log_row.get("game_date", ""))
                    if log_date == target_date:
                        matching_log = log_row
                        break

                if matching_log is not None:
                    if is_combo:
                        actual_value = sum(
                            float(matching_log.get(_STAT_COL.get(c, c), 0) or 0)
                            for c in COMBO_STATS.get(stat_type, [])
                            if _STAT_COL.get(c)
                        )
                    elif is_fantasy:
                        actual_value = round(
                            sum(
                                float(matching_log.get(_STAT_COL.get(c, c), 0) or 0) * w
                                for c, w in FANTASY_SCORING.get(stat_type, {}).items()
                                if _STAT_COL.get(c)
                            ),
                            2,
                        )
                    elif is_computed:
                        add_cols, sub_cols = _COMPUTED_STATS[stat_type]
                        actual_value = sum(float(matching_log.get(c, 0) or 0) for c in add_cols)
                        actual_value -= sum(float(matching_log.get(c, 0) or 0) for c in sub_cols)
                    else:
                        actual_value = float(matching_log.get(stat_col, 0) or 0)

            if actual_value is None:
                summary["skipped"] += 1
                continue

            summary["checked"] += 1

            if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                new_result = "EVEN"
            elif direction == "OVER":
                new_result = "WIN" if actual_value > prop_line else "LOSS"
            else:
                new_result = "WIN" if actual_value < prop_line else "LOSS"

            changed = (new_result != old_result) or (abs(float(actual_value) - float(old_actual)) > 1e-6)
            if not changed:
                summary["unchanged"] += 1
                continue

            success, msg = record_bet_result(bet_id, new_result, float(actual_value))
            if success:
                summary["corrected"] += 1
                summary["changes"].append({
                    "bet_id": bet_id,
                    "player": player_name,
                    "old_result": old_result,
                    "new_result": new_result,
                    "old_actual": round(float(old_actual), 2),
                    "new_actual": round(float(actual_value), 2),
                })
            else:
                summary["errors"].append(f"#{bet_id} {player_name}: DB update failed — {msg}")

        except Exception as exc:
            summary["errors"].append(f"#{bet_id} {player_name}: {exc}")

    if summary["corrected"] > 0:
        try:
            save_daily_snapshot(date_str)
        except Exception as _exc:
            _logger.warning("regrade_bets_for_date snapshot failed for %s: %s", date_str, _exc)

    return summary


def resolve_all_pending_bets():
    """
    Resolve ALL pending bets regardless of date Ã¢â‚¬â€ manual bets, AI picks, any platform.

    Queries every bet with no ``result`` set, groups them by date for efficient
    API calls, and resolves WIN/LOSS/EVEN for each using API-NBA game logs.
    Has rate limiting (1 second between API calls per player).

    Returns:
        dict: {
            "resolved": int,
            "wins": int,
            "losses": int,
            "evens": int,
            "pending": int,
            "errors": list[str],
            "by_date": dict[str, int],  # resolved count per date
        }
    """
    import datetime as _dt
    import time as _time

    summary = {
        "resolved": 0, "wins": 0, "losses": 0,
        "evens": 0, "pending": 0, "errors": [], "by_date": {},
    }

    # Try importing required modules
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    # Load all pending bets (no result set) regardless of date
    try:
        all_bets = load_all_bets(limit=2000, exclude_linked=False)
    except Exception as exc:
        summary["errors"].append(f"Failed to load bets: {exc}")
        return summary

    pending_bets = [b for b in all_bets if not b.get("result")]
    if not pending_bets:
        return summary

    # Group by date for efficient caching
    from collections import defaultdict as _defaultdict
    by_date = _defaultdict(list)
    for bet in pending_bets:
        d = bet.get("bet_date") or bet.get("game_date") or ""
        by_date[d].append(bet)

    # Player game log cache: player_id Ã¢â€ â€™ list[dict]
    _log_cache: dict = {}

    for date_str, bets in sorted(by_date.items()):
        if not date_str:
            summary["pending"] += len(bets)
            continue

        try:
            target_date = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            summary["pending"] += len(bets)
            continue

        date_resolved = 0
        # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 1+2: Try bulk box score fetch for this date Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        _bulk_lookup = _fetch_bulk_boxscores(date_str)
        _date_tier12 = 0

        for bet in bets:
            bet_id      = bet.get("bet_id") or bet.get("id")
            player_name = _clean_player_name(bet.get("player_name", ""))
            stat_type   = str(bet.get("stat_type", "")).lower()
            prop_line   = float(bet.get("prop_line") or 0)
            direction   = str(bet.get("direction") or "OVER").upper()

            is_combo   = stat_type in COMBO_STATS
            is_fantasy = stat_type in FANTASY_SCORING
            is_computed = stat_type in _COMPUTED_STATS
            stat_col   = _STAT_COL.get(stat_type)

            # Fallback: try normalizing the platform-native name to an internal key
            if not stat_col and not is_combo and not is_fantasy and not is_computed and _norm_stat_type is not None:
                normalized = _norm_stat_type(stat_type)
                stat_col = _STAT_COL.get(normalized)
                if stat_col:
                    stat_type = normalized
                elif normalized in COMBO_STATS:
                    is_combo = True
                    stat_type = normalized
                elif normalized in FANTASY_SCORING:
                    is_fantasy = True
                    stat_type = normalized
                elif normalized in _COMPUTED_STATS:
                    is_computed = True
                    stat_type = normalized

            if not stat_col and not is_combo and not is_fantasy and not is_computed:
                if _is_segment_prop(stat_type) or stat_type in _UNRESOLVABLE_STATS:
                    _label = "period prop" if _is_segment_prop(stat_type) else "unresolvable"
                    update_bet_result(bet_id, "VOID", 0.0)
                    summary["resolved"] = summary.get("resolved", 0) + 1
                    summary["errors"].append(
                        f"#{bet_id} {player_name}: '{stat_type}' {_label} \u2014 auto-VOID"
                    )
                else:
                    summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
                    summary["pending"] += 1
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ Try Tier 1/2 bulk lookup first Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            bulk_row = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name)

            if bulk_row is not None:
                try:
                    actual_value = _compute_actual_value_from_row(
                        bulk_row, stat_type, stat_col, is_combo, is_fantasy,
                        COMBO_STATS, FANTASY_SCORING, is_computed=is_computed,
                    )
                    if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                        result = "EVEN"
                    elif direction == "OVER":
                        result = "WIN" if actual_value > prop_line else "LOSS"
                    else:
                        result = "WIN" if actual_value < prop_line else "LOSS"
                    success, msg = record_bet_result(bet_id, result, actual_value)
                    if success:
                        summary["resolved"] += 1
                        date_resolved += 1
                        _date_tier12 += 1
                        if result == "WIN":
                            summary["wins"] += 1
                        elif result == "LOSS":
                            summary["losses"] += 1
                        else:
                            summary["evens"] += 1
                    else:
                        summary["errors"].append(f"#{bet_id} {player_name}: DB update failed Ã¢â‚¬â€ {msg}")
                        summary["pending"] += 1
                except Exception as exc:
                    summary["errors"].append(f"#{bet_id} {player_name}: {exc}")
                    summary["pending"] += 1
                continue  # Skip Tier 3 for this bet

            # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 3: Legacy per-player game log path Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # Player ID lookup: API-NBA Ã¢â€ â€™ nba_api static (local)
            player_id = None
            if _lookup_pid is not None:
                player_id = _lookup_pid(player_name)
                if not player_id:
                    player_id = _lookup_pid(_normalize_name(player_name))
            if not player_id:
                summary["errors"].append(f"#{bet_id} {player_name}: player ID not found")
                summary["pending"] += 1
                continue

            if player_id not in _log_cache:
                _api_exc = None
                for _attempt in range(RESOLVE_MAX_RETRIES):
                    try:
                        if _attempt > 0:
                            _time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                        logs = _fetch_resolve_game_log(player_id, last_n=10)
                        _log_cache[player_id] = logs or []
                        _api_exc = None
                        break
                    except Exception as exc:
                        _api_exc = exc
                        continue
                if _api_exc is not None:
                    summary["errors"].append(f"#{bet_id} {player_name}: API error Ã¢â‚¬â€ {_api_exc}")
                    summary["pending"] += 1
                    continue

            logs = _log_cache.get(player_id, [])
            if not logs:
                # Only VOID if player IS in the bulk lookup (true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    ok = update_bet_result(bet_id, "VOID", 0.0)
                    if ok:
                        summary["resolved"] += 1
                        date_resolved += 1
                    else:
                        summary["errors"].append(f"#{bet_id} {player_name}: VOID update failed")
                        summary["pending"] += 1
                else:
                    summary["errors"].append(f"#{bet_id} {player_name}: no game log available")
                    summary["pending"] += 1
                continue

            # Find the game on target date
            matching_log = None
            for log_row in logs:
                log_date = _parse_game_date(log_row.get("game_date", ""))
                if log_date == target_date:
                    matching_log = log_row
                    break

            if matching_log is None:
                # Only VOID if player IS in the bulk lookup (true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    ok = update_bet_result(bet_id, "VOID", 0.0)
                    if ok:
                        summary["resolved"] += 1
                        date_resolved += 1
                    else:
                        summary["errors"].append(f"#{bet_id} {player_name}: VOID update failed")
                        summary["pending"] += 1
                else:
                    _last = logs[0].get("game_date", "N/A") if logs else "N/A"
                    summary["errors"].append(
                        f"#{bet_id} {player_name}: no game found on {date_str} "
                        f"(last game: {_last})"
                    )
                    summary["pending"] += 1
                continue

            try:
                if is_combo:
                    actual_value = sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0)
                        for c in COMBO_STATS[stat_type]
                        if _STAT_COL.get(c)
                    )
                elif is_fantasy:
                    actual_value = round(sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0) * w
                        for c, w in FANTASY_SCORING[stat_type].items()
                        if _STAT_COL.get(c)
                    ), 2)
                elif is_computed:
                    add_cols, sub_cols = _COMPUTED_STATS[stat_type]
                    actual_value = sum(float(matching_log.get(c, 0) or 0) for c in add_cols)
                    actual_value -= sum(float(matching_log.get(c, 0) or 0) for c in sub_cols)
                else:
                    actual_value = float(matching_log.get(stat_col, 0) or 0)

                if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                    result = "EVEN"
                elif direction == "OVER":
                    result = "WIN" if actual_value > prop_line else "LOSS"
                else:
                    result = "WIN" if actual_value < prop_line else "LOSS"

                success, msg = record_bet_result(bet_id, result, actual_value)
                if success:
                    summary["resolved"] += 1
                    date_resolved += 1
                    if result == "WIN":
                        summary["wins"] += 1
                    elif result == "LOSS":
                        summary["losses"] += 1
                    else:
                        summary["evens"] += 1
                else:
                    summary["errors"].append(f"#{bet_id} {player_name}: DB update failed Ã¢â‚¬â€ {msg}")
                    summary["pending"] += 1
            except Exception as exc:
                summary["errors"].append(f"#{bet_id} {player_name}: {exc}")
                summary["pending"] += 1

        if _date_tier12:
            _logger.info(
                f"[BetTracker] resolve_all_pending_bets: resolved {_date_tier12} bet(s) "
                f"via Tier 1/2 (bulk BoxScore) for {date_str}"
            )

        if date_resolved > 0:
            summary["by_date"][date_str] = date_resolved
            try:
                from tracking.database import save_daily_snapshot
                save_daily_snapshot(date_str)
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    return summary


def resolve_all_analysis_picks(date_str=None, include_today=False):
    """
    Resolve pending rows in the ``all_analysis_picks`` table.

    This is the counterpart to ``resolve_all_pending_bets()`` for the
    **All Picks** tab, which displays data from ``all_analysis_picks``
    (not the ``bets`` table).  Without this function the "Resolve All
    Picks" button would never actually update what the user sees.

    Uses the same API-NBA game log approach as
    ``resolve_all_pending_bets()``:
      - Loads every row in ``all_analysis_picks`` where result is NULL
      - Groups by date, retrieves game logs per player per season
      - Computes WIN / LOSS / EVEN using prop_line + direction
      - Writes result & actual_value back via
        ``update_analysis_pick_result()``

    Args:
        date_str (str | None): When provided (ISO "YYYY-MM-DD"), only picks
            for that specific date are processed Ã¢â‚¬â€ even if they were already
            resolved (allows re-checking a past night's results).
            When ``None`` (default), all pending picks across all dates are
            resolved.
        include_today (bool): When ``True`` and ``date_str`` is ``None``,
            today's picks are included even if games may not be final yet.
            Defaults to ``False`` (today is skipped on automatic runs).

    Returns:
        dict: {
            "resolved": int,
            "wins": int,
            "losses": int,
            "evens": int,
            "pending": int,
            "errors": list[str],
            "by_date": dict[str, int],
        }
    """
    import datetime as _dt
    import time as _time

    summary = {
        "resolved": 0, "wins": 0, "losses": 0,
        "evens": 0, "pending": 0, "errors": [], "by_date": {},
    }

    # Ã¢â€â‚¬Ã¢â€â‚¬ Import dependencies Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    from tracking.database import (
        load_pending_analysis_picks,
        update_analysis_pick_result,
    )

    # Ã¢â€â‚¬Ã¢â€â‚¬ Load picks from all_analysis_picks Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    try:
        if date_str:
            from tracking.database import load_analysis_picks_for_date
            pending_picks = load_analysis_picks_for_date(date_str)
        else:
            pending_picks = load_pending_analysis_picks(limit=2000)
    except Exception as exc:
        summary["errors"].append(f"Failed to load pending picks: {exc}")
        return summary

    if not pending_picks:
        return summary

    # Ã¢â€â‚¬Ã¢â€â‚¬ Group by date Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    from collections import defaultdict as _defaultdict
    by_date = _defaultdict(list)
    for pick in pending_picks:
        d = pick.get("pick_date") or ""
        by_date[d].append(pick)

    # Player game log cache: player_id Ã¢â€ â€™ list[dict]
    _log_cache: dict = {}

    for _loop_date, picks in sorted(by_date.items()):
        if not _loop_date:
            summary["pending"] += len(picks)
            continue

        try:
            target_date = _dt.datetime.strptime(_loop_date, "%Y-%m-%d").date()
        except ValueError:
            summary["pending"] += len(picks)
            continue

        # When no specific date was requested, skip today Ã¢â‚¬â€ games may not
        # be final yet.  When the user explicitly asks for a date (even
        # today) we trust them and proceed.  The `include_today` flag
        # allows callers (e.g. an explicit "Resolve All" button) to opt in.
        should_skip_today = date_str is None and not include_today and target_date >= _nba_today_et()
        if should_skip_today:
            summary["pending"] += len(picks)
            continue

        date_resolved = 0
        # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 1+2: Try bulk box score fetch for this date Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        _bulk_lookup = _fetch_bulk_boxscores(_loop_date)
        _date_tier12 = 0

        for pick in picks:
            pick_id     = pick.get("pick_id")
            player_name = _clean_player_name(pick.get("player_name", ""))
            stat_type   = str(pick.get("stat_type", "")).lower()
            prop_line   = float(pick.get("prop_line") or 0)
            direction   = str(pick.get("direction") or "OVER").upper()

            is_combo   = stat_type in COMBO_STATS
            is_fantasy = stat_type in FANTASY_SCORING
            is_computed = stat_type in _COMPUTED_STATS
            stat_col   = _STAT_COL.get(stat_type)

            # Fallback: try normalizing the platform-native name to an internal key
            if not stat_col and not is_combo and not is_fantasy and not is_computed and _norm_stat_type is not None:
                normalized = _norm_stat_type(stat_type)
                stat_col = _STAT_COL.get(normalized)
                if stat_col:
                    stat_type = normalized
                elif normalized in COMBO_STATS:
                    is_combo = True
                    stat_type = normalized
                elif normalized in FANTASY_SCORING:
                    is_fantasy = True
                    stat_type = normalized
                elif normalized in _COMPUTED_STATS:
                    is_computed = True
                    stat_type = normalized

            if not stat_col and not is_combo and not is_fantasy and not is_computed:
                if _is_segment_prop(stat_type) or stat_type in _UNRESOLVABLE_STATS:
                    _label = "period prop" if _is_segment_prop(stat_type) else "unresolvable"
                    update_analysis_pick_result(pick_id, "VOID", 0.0)
                    summary["resolved"] = summary.get("resolved", 0) + 1
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: '{stat_type}' {_label} \u2014 auto-VOID"
                    )
                else:
                    summary["errors"].append(f"#{pick_id} {player_name}: unknown stat '{stat_type}'")
                    summary["pending"] += 1
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ Try Tier 1/2 bulk lookup first Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            bulk_row = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name)

            if bulk_row is not None:
                try:
                    actual_value = _compute_actual_value_from_row(
                        bulk_row, stat_type, stat_col, is_combo, is_fantasy,
                        COMBO_STATS, FANTASY_SCORING, is_computed=is_computed,
                    )
                    if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                        result = "EVEN"
                    elif direction == "OVER":
                        result = "WIN" if actual_value > prop_line else "LOSS"
                    else:
                        result = "WIN" if actual_value < prop_line else "LOSS"
                    ok = update_analysis_pick_result(pick_id, result, actual_value)
                    if ok:
                        summary["resolved"] += 1
                        date_resolved += 1
                        _date_tier12 += 1
                        if result == "WIN":
                            summary["wins"] += 1
                        elif result == "LOSS":
                            summary["losses"] += 1
                        else:
                            summary["evens"] += 1
                    else:
                        summary["errors"].append(
                            f"#{pick_id} {player_name}: DB update failed"
                        )
                        summary["pending"] += 1
                except Exception as exc:
                    summary["errors"].append(f"#{pick_id} {player_name}: {exc}")
                    summary["pending"] += 1
                continue  # Skip Tier 3 for this pick

            # Ã¢â€â‚¬Ã¢â€â‚¬ Tier 3: Legacy per-player game log path Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # Ã¢â€â‚¬Ã¢â€â‚¬ Player ID lookup: API-NBA Ã¢â€ â€™ nba_api static (local) Ã¢â€â‚¬Ã¢â€â‚¬
            player_id = None
            if _lookup_pid is not None:
                player_id = _lookup_pid(player_name)
                if not player_id:
                    player_id = _lookup_pid(_normalize_name(player_name))
            if not player_id:
                summary["errors"].append(
                    f"#{pick_id} {player_name}: player ID not found"
                )
                summary["pending"] += 1
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ Retrieve game log (cached per player) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            if player_id not in _log_cache:
                _api_exc = None
                for _attempt in range(RESOLVE_MAX_RETRIES):
                    try:
                        if _attempt > 0:
                            _time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                        logs = _fetch_resolve_game_log(player_id, last_n=10)
                        _log_cache[player_id] = logs or []
                        _api_exc = None
                        break
                    except Exception as exc:
                        _api_exc = exc
                        continue
                if _api_exc is not None:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: API error Ã¢â‚¬â€ {_api_exc}"
                    )
                    summary["pending"] += 1
                    continue

            logs = _log_cache.get(player_id, [])
            if not logs:
                # Only VOID if player IS in the bulk lookup (true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    ok = update_analysis_pick_result(pick_id, "VOID", 0.0)
                    if ok:
                        summary["resolved"] += 1
                        date_resolved += 1
                    else:
                        summary["errors"].append(f"#{pick_id} {player_name}: VOID update failed")
                        summary["pending"] += 1
                else:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: no game log available"
                    )
                    summary["pending"] += 1
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ Match game by date Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            matching_log = None
            for log_row in logs:
                log_date = _parse_game_date(log_row.get("game_date", ""))
                if log_date == target_date:
                    matching_log = log_row
                    break

            if matching_log is None:
                # Only VOID if player IS in the bulk lookup (true DNP).
                _player_in_bulk = _lookup_bulk_row(_bulk_lookup, player_name, _normalize_name) is not None
                if _player_in_bulk:
                    ok = update_analysis_pick_result(pick_id, "VOID", 0.0)
                    if ok:
                        summary["resolved"] += 1
                        date_resolved += 1
                    else:
                        summary["errors"].append(f"#{pick_id} {player_name}: VOID update failed")
                        summary["pending"] += 1
                else:
                    _last = logs[0].get("game_date", "N/A") if logs else "N/A"
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: no game found on {_loop_date} "
                        f"(last game: {_last})"
                    )
                    summary["pending"] += 1
                continue

            # Ã¢â€â‚¬Ã¢â€â‚¬ Compute actual stat value Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            try:
                if is_combo:
                    actual_value = sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0)
                        for c in COMBO_STATS[stat_type]
                        if _STAT_COL.get(c)
                    )
                elif is_fantasy:
                    actual_value = round(sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0) * w
                        for c, w in FANTASY_SCORING[stat_type].items()
                        if _STAT_COL.get(c)
                    ), 2)
                elif is_computed:
                    add_cols, sub_cols = _COMPUTED_STATS[stat_type]
                    actual_value = sum(float(matching_log.get(c, 0) or 0) for c in add_cols)
                    actual_value -= sum(float(matching_log.get(c, 0) or 0) for c in sub_cols)
                else:
                    actual_value = float(matching_log.get(stat_col, 0) or 0)

                # Ã¢â€â‚¬Ã¢â€â‚¬ Determine WIN / LOSS / EVEN Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
                if abs(actual_value - prop_line) < EVEN_THRESHOLD_EPSILON:
                    result = "EVEN"
                elif direction == "OVER":
                    result = "WIN" if actual_value > prop_line else "LOSS"
                else:
                    result = "WIN" if actual_value < prop_line else "LOSS"

                # Ã¢â€â‚¬Ã¢â€â‚¬ Write result to all_analysis_picks Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
                ok = update_analysis_pick_result(pick_id, result, actual_value)
                if ok:
                    summary["resolved"] += 1
                    date_resolved += 1
                    if result == "WIN":
                        summary["wins"] += 1
                    elif result == "LOSS":
                        summary["losses"] += 1
                    else:
                        summary["evens"] += 1
                else:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: DB update failed"
                    )
                    summary["pending"] += 1

            except Exception as exc:
                summary["errors"].append(f"#{pick_id} {player_name}: {exc}")
                summary["pending"] += 1

        if _date_tier12:
            _logger.info(
                f"[BetTracker] resolve_all_analysis_picks: resolved {_date_tier12} pick(s) "
                f"via Tier 1/2 (bulk BoxScore) for {_loop_date}"
            )

        if date_resolved > 0:
            summary["by_date"][_loop_date] = date_resolved

    return summary


def _fetch_espn_live_boxscores() -> dict:
    """Fetch live/in-progress player box scores from ESPN scoreboard + summary.

    Returns:
        dict: {player_name_lower: {pts, reb, ast, ..., is_live, is_final}}
              Empty dict on any failure.
    """
    try:
        import requests

        try:
            from utils.headers import get_espn_headers
            _headers = get_espn_headers()
        except ImportError:
            _headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

        # Today's scoreboard
        today_str = _nba_today_et().isoformat().replace("-", "")
        scoreboard_url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
            f"?dates={today_str}"
        )
        resp = requests.get(scoreboard_url, headers=_headers, timeout=NBA_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return {}

        lookup: dict = {}

        for event in events:
            event_id = event.get("id")
            if not event_id:
                continue

            status_obj = event.get("status", {}).get("type", {})
            status_id = str(status_obj.get("id", ""))
            # ESPN status: 1=Scheduled, 2=In Progress, 3=Final
            is_live = status_id == "2"
            is_final = status_id == "3"

            if not is_live and not is_final:
                continue  # Skip scheduled games

            try:
                import time as _time
                _time.sleep(0.3)
                summary_url = (
                    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
                    f"?event={event_id}"
                )
                summary_resp = requests.get(
                    summary_url, headers=_headers, timeout=NBA_API_TIMEOUT
                )
                summary_resp.raise_for_status()
                summary_data = summary_resp.json()

                boxscore = summary_data.get("boxscore", {})
                for team_section in boxscore.get("players", []):
                    statistics = team_section.get("statistics", [])
                    if not statistics:
                        continue
                    stat_block = statistics[0]
                    stat_labels = [lbl.lower() for lbl in stat_block.get("labels", [])]
                    for athlete_entry in stat_block.get("athletes", []):
                        if athlete_entry.get("didNotPlay", False):
                            continue
                        athlete = athlete_entry.get("athlete", {})
                        pname = str(athlete.get("displayName", "")).lower().strip()
                        if not pname:
                            continue
                        stats_list = athlete_entry.get("stats", [])
                        if not stats_list or len(stats_list) != len(stat_labels):
                            continue
                        sd = dict(zip(stat_labels, stats_list))

                        def _sf(val):
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                return 0.0

                        lookup[pname] = {
                            "pts":      _sf(sd.get("pts", 0)),
                            "reb":      _sf(sd.get("reb", 0)),
                            "ast":      _sf(sd.get("ast", 0)),
                            "stl":      _sf(sd.get("stl", 0)),
                            "blk":      _sf(sd.get("blk", 0)),
                            "tov":      _sf(sd.get("to", 0)),
                            "fg3m":     _sf(str(sd.get("3pt", "0-0")).split("-")[0]),
                            "ftm":      _sf(str(sd.get("ft", "0-0")).split("-")[0]),
                            "is_live":  is_live,
                            "is_final": is_final,
                        }
            except Exception as _exc:
                _logger.debug(f"[BetTracker] ESPN live box fetch error for event {event_id}: {_exc}")
                continue

        return lookup

    except Exception as exc:
        _logger.warning(f"[BetTracker] ESPN live box score fetch failed: {exc}")
        return {}


def get_live_bet_status(bets_list):
    """
    Check live box scores for today's pending bets via ESPN live scores.

    Args:
        bets_list (list[dict]): Today's pending bets from the database.

    Returns:
        list[dict]: Each bet dict augmented with:
            - current_value (float | None)
            - live_status ("Ã°Å¸Å¸Â¢ Winning" | "Ã°Å¸â€Â´ Losing" | "Ã¢ÂÂ³ In Progress" |
                           "Ã°Å¸â€¢Â Not Started" | "Ã¢Å“â€¦ Final")
    """
    augmented = []

    # Retrieve live box scores from ESPN
    live_box = _fetch_espn_live_boxscores()

    STAT_TO_BOX = {
        "points": "pts",
        "rebounds": "reb",
        "assists": "ast",
        "steals": "stl",
        "blocks": "blk",
        "turnovers": "tov",
        "threes": "fg3m",
        "three_pointers": "fg3m",
        "3-pt made": "fg3m",
        "3pm": "fg3m",
        "three pointers": "fg3m",
        "3-pointers": "fg3m",
        "3-pt attempted": "fg3a",
        "fg3a": "fg3a",
        "free throws made": "ftm",
        "ftm": "ftm",
        "fta": "fta",
        "fga": "fga",
        "fgm": "fgm",
        "blocked shots": "blk",
        "personal_fouls": "pf",
        "offensive_rebounds": "oreb",
        "defensive_rebounds": "dreb",
        "minutes": "minutes",
    }

    # Computed stats for live tracking (derived from multiple box cols)
    _LIVE_COMPUTED = {
        "two pointers made":      lambda b: b.get("fgm", 0.0) - b.get("fg3m", 0.0),
        "two pointers attempted": lambda b: b.get("fga", 0.0) - b.get("fg3a", 0.0),
    }

    for bet in bets_list:
        bet_copy = dict(bet)
        player_name = _clean_player_name(bet.get("player_name", ""))
        stat_type   = str(bet.get("stat_type") or "").lower()
        prop_line   = float(bet.get("prop_line") or 0)
        direction   = str(bet.get("direction") or "OVER").upper()

        pname_lower = player_name.lower()
        box_entry = live_box.get(pname_lower)

        if box_entry is None:
            bet_copy["current_value"] = None
            bet_copy["live_status"] = "Ã°Å¸â€¢Â Not Started"
        else:
            box_key = STAT_TO_BOX.get(stat_type)
            if box_key:
                current_value = box_entry.get(box_key, 0.0)
            elif stat_type in _LIVE_COMPUTED:
                current_value = _LIVE_COMPUTED[stat_type](box_entry)
            elif stat_type == "points_rebounds":
                current_value = box_entry.get("pts", 0.0) + box_entry.get("reb", 0.0)
            elif stat_type == "points_assists":
                current_value = box_entry.get("pts", 0.0) + box_entry.get("ast", 0.0)
            elif stat_type == "rebounds_assists":
                current_value = box_entry.get("reb", 0.0) + box_entry.get("ast", 0.0)
            elif stat_type == "points_rebounds_assists":
                current_value = box_entry.get("pts", 0.0) + box_entry.get("reb", 0.0) + box_entry.get("ast", 0.0)
            else:
                current_value = None

            bet_copy["current_value"] = current_value

            if box_entry.get("is_final"):
                bet_copy["live_status"] = "Ã¢Å“â€¦ Final"
            elif box_entry.get("is_live") and current_value is not None:
                if direction == "OVER":
                    bet_copy["live_status"] = "Ã°Å¸Å¸Â¢ Winning" if current_value > prop_line else "Ã°Å¸â€Â´ Losing"
                else:
                    bet_copy["live_status"] = "Ã°Å¸Å¸Â¢ Winning" if current_value < prop_line else "Ã°Å¸â€Â´ Losing"
            else:
                bet_copy["live_status"] = "Ã¢ÂÂ³ In Progress"

        augmented.append(bet_copy)

    return augmented


# ============================================================
# SECTION: Auto-Save Top Picks from Neural Analysis
# ============================================================

def save_top_picks_from_analysis(analysis_results):
    """
    Save top picks from Neural Analysis into the bet tracker as AI-logged picks.

    Uses log_new_bet() for schema compliance. Only saves Platinum/Gold picks
    with probability_over >= 0.60.

    Args:
        analysis_results (list of dict): Results from Neural Analysis.

    Returns:
        int: Number of picks successfully saved.
    """
    if not analysis_results:
        return 0

    AUTO_TIERS = {"Platinum", "Gold"}
    MIN_PROBABILITY = 0.60

    import datetime as _dt
    # Anchor to US/Eastern Ã¢â‚¬â€ NBA game dates are defined in ET.
    today_str = _nba_today_et().isoformat()

    existing_bets = load_all_bets(exclude_linked=False)
    existing_keys = set()
    for b in existing_bets:
        key = (
            str(b.get("player_name", "")).lower(),
            str(b.get("stat_type", "")).lower(),
            str(b.get("bet_date", ""))[:10],
        )
        existing_keys.add(key)

    saved_count = 0
    for result in analysis_results:
        tier = result.get("tier", "")
        prob = float(result.get("probability_over", 0) or 0)

        if tier not in AUTO_TIERS or prob < MIN_PROBABILITY:
            continue

        player_name = str(result.get("player_name", "")).strip()
        stat_type = str(result.get("stat_type", "")).strip().lower()
        if not player_name or not stat_type:
            continue

        dup_key = (player_name.lower(), stat_type, today_str)
        if dup_key in existing_keys:
            continue

        direction = str(result.get("direction", "OVER")).upper()
        prop_line = float(result.get("line", 0) or 0)
        platform = str(result.get("platform", "PrizePicks"))
        edge = float(result.get("edge_percentage", result.get("edge", 0)) or 0)
        confidence = float(result.get("confidence_score", 0) or 0)
        bet_type = str(result.get("bet_type", "normal"))
        std_devs = float(result.get("std_devs_from_line", 0.0))
        team = str(result.get("player_team", result.get("team", "")))

        try:
            ok, _msg = log_new_bet(
                player_name=player_name,
                stat_type=stat_type,
                prop_line=prop_line,
                direction=direction,
                platform=platform,
                confidence_score=confidence,
                probability_over=prob,
                edge_percentage=edge,
                tier=tier,
                entry_fee=0.0,
                team=team,
                notes=f"AI auto-logged | edge={edge:.1f}% | prob={prob:.1%}",
                auto_logged=1,
                bet_type=bet_type,
                std_devs_from_line=std_devs,
            )
            if ok:
                existing_keys.add(dup_key)
                saved_count += 1
        except Exception as _exc:
            logging.getLogger(__name__).warning(
                f"[BetTracker] save_top_picks error for {player_name}: {_exc}"
            )

    return saved_count


# ============================================================
# SECTION: Bulk-Log Platform Props
# ============================================================

def log_props_to_tracker(props_list, direction="OVER"):
    """
    Bulk-log a list of platform props into the bet tracker as PENDING bets.

    Each prop becomes one bet entry with:
      - direction defaulting to OVER (unless the prop dict already has
        a "direction" key, e.g. from DraftKings odds data)
      - confidence_score / probability_over / edge_percentage = 0 / 0.5 / 0.0
        (no model output available Ã¢â‚¬â€ user can update after analysis)
      - tier = "Bronze" (lowest tier since no model output)
      - auto_logged = 1 (flagged as system-added, not manually entered)

    Duplicate detection: skips any prop whose (player_name, stat_type,
    today) triple is already in the ``bets`` table.

    Stat-type normalisation: platform prop stat_type values are already
    normalised to internal keys by ``data.sportsbook_service`` (e.g.
    "3-Point Made" Ã¢â€ â€™ "threes"). If a value is still unrecognised it is
    skipped and reported in ``errors``.

    Args:
        props_list (list[dict]): Props from ``platform_props`` session
            state or ``data/live_props.csv``. Each dict must have at
            least ``player_name``, ``stat_type``, ``line``, and
            ``platform``.
        direction (str): Default direction ("OVER" or "UNDER") to use
            when the prop dict has no "direction" key. Defaults to
            "OVER".

    Returns:
        tuple[int, int, list[str]]: (saved, skipped, errors)
            saved   Ã¢â‚¬â€ number of props successfully logged
            skipped Ã¢â‚¬â€ number of duplicates skipped
            errors  Ã¢â‚¬â€ list of human-readable error strings
    """
    if not props_list:
        return 0, 0, []

    import datetime as _dt

    today_str = _nba_today_et().isoformat()

    # Load existing bets to detect duplicates
    existing_bets = load_all_bets(limit=2000, exclude_linked=False)
    existing_keys: set = set()
    for b in existing_bets:
        key = (
            str(b.get("player_name", "")).lower(),
            str(b.get("stat_type", "")).lower(),
            float(b.get("prop_line", 0) or 0),
            str(b.get("direction", "OVER")).upper(),
            str(b.get("bet_date", ""))[:10],
        )
        existing_keys.add(key)

    # Normaliser: convert any un-normalised platform name to internal key
    try:
        from data.platform_mappings import normalize_stat_type as _norm_stat_type
    except ImportError:
        _norm_stat_type = None

    saved = 0
    skipped = 0
    errors: list = []

    for prop in props_list:
        player_name = str(prop.get("player_name", "")).strip()
        if not player_name:
            errors.append("Skipped prop with missing player name")
            continue

        # Normalise stat_type: sportsbook_service already does this, but guard
        # against manually-built or CSV-loaded props that may still be raw.
        stat_type = str(prop.get("stat_type", "")).strip().lower()
        if not stat_type:
            errors.append(f"{player_name}: missing stat_type Ã¢â‚¬â€ skipped")
            continue
        if stat_type not in VALID_STAT_TYPES and _norm_stat_type is not None:
            stat_type = _norm_stat_type(stat_type).lower()
        if stat_type not in VALID_STAT_TYPES:
            errors.append(
                f"{player_name}: unrecognised stat type '{prop.get('stat_type', '')}' Ã¢â‚¬â€ skipped"
            )
            continue

        prop_line = float(prop.get("line", prop.get("prop_line", 0)) or 0)
        if prop_line <= 0:
            errors.append(f"{player_name} ({stat_type}): invalid line {prop_line!r} Ã¢â‚¬â€ skipped")
            continue

        bet_direction = str(prop.get("direction", direction)).upper()
        if bet_direction not in VALID_DIRECTIONS:
            bet_direction = direction.upper()

        # Duplicate check (must match existing_keys: name, stat, line, direction, date)
        dup_key = (player_name.lower(), stat_type, prop_line, bet_direction, today_str)
        if dup_key in existing_keys:
            skipped += 1
            continue

        platform = str(prop.get("platform", "PrizePicks"))
        team = str(prop.get("team", prop.get("player_team", "")))
        game_date = str(prop.get("game_date", today_str))

        try:
            ok, msg = log_new_bet(
                player_name=player_name,
                stat_type=stat_type,
                prop_line=prop_line,
                direction=bet_direction,
                platform=platform,
                confidence_score=0.0,
                probability_over=0.5,
                edge_percentage=0.0,
                tier="Bronze",
                entry_fee=0.0,
                team=team,
                notes=f"Added from platform props | game: {game_date}",
                auto_logged=1,
                bet_type="normal",
                std_devs_from_line=0.0,
                source="smart_pick_pro_platform",
            )
            if ok:
                existing_keys.add(dup_key)
                saved += 1
            else:
                errors.append(f"{player_name} ({stat_type}): {msg}")
        except Exception as _exc:
            errors.append(f"{player_name} ({stat_type}): {_exc}")
            logging.getLogger(__name__).warning(
                f"[BetTracker] log_props_to_tracker error for {player_name}: {_exc}"
            )

    return saved, skipped, errors

# ============================================================
# END SECTION: Bulk-Log Platform Props
# ============================================================


# ============================================================
# SECTION: Pipeline Overhaul — Per-System Auto-Logging,
#          Postponement Handling, Retry-Window Cleanup
# ============================================================

# Default 3-day retry window before deleting unresolved bets.
PENDING_RETRY_DAYS = int(os.environ.get("BET_PENDING_RETRY_DAYS", "3"))


def auto_log_qeg_bets(analysis_results, *, max_bets=15):
    """Filter QAM analysis_results to QEG picks and log them with source='qeg'.

    QEG = Quantum Edge Gap: standard-line picks where the line deviates
    >=20% from the season average in the qualifying direction OR
    |edge_percentage| >= 20%.  Goblins/demons are excluded.
    """
    try:
        from pages.helpers.quantum_analysis_helpers import (
            filter_qeg_picks,
            deduplicate_qeg_picks,
        )
    except ImportError as exc:
        _logger.warning("auto_log_qeg_bets: helper import failed: %s", exc)
        return 0
    qeg = deduplicate_qeg_picks(filter_qeg_picks(analysis_results or []))
    return auto_log_analysis_bets(
        qeg, max_bets=max_bets, source="qeg"
    )


def auto_log_smart_money_bets(analysis_results, *, max_bets=20):
    """Filter analysis_results to Smart Money picks and log with source='smart_money'.

    Reuses the Smart Money page's _filter_zone_picks if available so the
    auto-logged picks match exactly what the page renders.  Falls back to
    a deviation-based filter if the page module can't be imported (worker
    runs outside Streamlit).
    """
    if not analysis_results:
        return 0
    smart_picks: list = []
    try:
        # Page module is only importable inside Streamlit; guard with a
        # broad except so the worker doesn't crash if Streamlit is absent.
        # The deviation-based fallback below covers that case.
        from pages.helpers.smart_money_helpers import filter_smart_money_picks  # type: ignore
        smart_picks = filter_smart_money_picks(analysis_results) or []
    except Exception:
        # Fallback: deviation-based standard-line filter (line >=10% from avg
        # OR |edge| >= 10%, exclude player_is_out, min 14 season minutes).
        for r in analysis_results:
            if r.get("player_is_out"):
                continue
            odds_type = str(r.get("odds_type", "standard")).strip().lower()
            if odds_type not in ("standard", ""):
                # Goblin/demon picks go through here too — line deviation
                # already captures them, but allow the page-helper path to
                # be the source of truth when available.
                pass
            line_dev = abs(float(r.get("line_vs_avg_pct", 0) or 0))
            edge_pct = abs(float(r.get("edge_percentage", 0) or 0))
            season_min = float(r.get("season_minutes", 0) or 0)
            if season_min and season_min < 14.0:
                continue
            if line_dev >= 10.0 or edge_pct >= 10.0:
                smart_picks.append(r)
    return auto_log_analysis_bets(
        smart_picks, max_bets=max_bets, source="smart_money"
    )


def auto_log_platform_ai_bets(analysis_results, *, max_bets=8, prizepicks_only=False):
    """Auto-log Platform AI picks with source='platform_ai'.

    Filter MUST match the "⚡ Platform AI Picks" section on the QAM page
    (Smart_Picks_Pro_Home / Quantum_Analysis_Matrix) so the Bet Tracker's
    Platform Picks tab tracks exactly what the user sees rendered there:
      - platform value present (any platform)
      - not should_avoid
      - not player_is_out
      - confidence_score >= 60
      - top 8 by confidence_score (matches the displayed cards)
    """
    if not analysis_results:
        return 0
    filtered: list = []
    for r in analysis_results:
        plat = (r.get("platform") or "").strip()
        if not plat:
            continue
        if prizepicks_only:
            _pl = plat.lower()
            if "prizepicks" not in _pl and "prize picks" not in _pl:
                continue
        if r.get("should_avoid"):
            continue
        if r.get("player_is_out"):
            continue
        if float(r.get("confidence_score", 0) or 0) < 60:
            continue
        filtered.append(r)
    # Top N by confidence_score — matches QAM display ordering exactly
    filtered.sort(
        key=lambda r: float(r.get("confidence_score", 0) or 0),
        reverse=True,
    )
    filtered = filtered[:max_bets]
    return auto_log_analysis_bets(
        filtered, max_bets=max_bets, source="platform_ai"
    )


def detect_and_void_postponed_games(date_str=None):
    """Detect NBA games that never reached Final on date_str and VOID their bets.

    A game is treated as postponed if ESPN reports the date had scheduled
    games but specific games never reached status=Final by the time this
    runs (worker runs the daily sweep). For each postponed game, both
    teams' pending bets on that date are marked VOID with reason
    "postponed".

    Returns:
        tuple: (voided_count: int, postponed_games: list[(home, away)])
    """
    import datetime as _dt
    if date_str is None:
        date_str = (_nba_today_et() - _dt.timedelta(days=1)).isoformat()

    # ESPN scoreboard
    try:
        import requests
        try:
            from utils.headers import get_espn_headers
            headers = get_espn_headers()
        except ImportError:
            headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
            f"?dates={date_str.replace('-', '')}"
        )
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        events = resp.json().get("events", []) or []
    except Exception as exc:
        _logger.warning("[BetTracker] postponement check failed: %s", exc)
        return 0, []

    postponed: list = []
    for ev in events:
        status_id = str(ev.get("status", {}).get("type", {}).get("id", ""))
        status_name = str(ev.get("status", {}).get("type", {}).get("name", "")).upper()
        # ESPN status: 1=scheduled, 2=in progress, 3=final, 5=cancelled, 6=postponed
        is_postponed = status_id in {"5", "6"} or "POSTPONE" in status_name or "CANCEL" in status_name
        if not is_postponed:
            continue
        comps = ev.get("competitions", [{}])[0].get("competitors", []) or []
        teams = [
            c.get("team", {}).get("abbreviation") or c.get("team", {}).get("displayName", "")
            for c in comps
        ]
        teams = [t for t in teams if t]
        if teams:
            postponed.append(tuple(teams))

    if not postponed:
        return 0, []

    flat_teams = list({t for pair in postponed for t in pair})
    try:
        from tracking.database import void_team_bets
        voided = void_team_bets(date_str, flat_teams, reason="postponed")
    except Exception as exc:
        _logger.error("[BetTracker] void_team_bets failed: %s", exc)
        voided = 0

    _logger.info(
        "[BetTracker] postponement sweep: %s — %d games postponed, %d bets VOIDED (%s)",
        date_str, len(postponed), voided, flat_teams,
    )
    return voided, postponed


def cleanup_unresolved_bets(retry_days=None):
    """Delete pending bets whose bet_date is older than the retry window.

    Implements "if we couldn't resolve it, it never happened". Default
    window = PENDING_RETRY_DAYS (env BET_PENDING_RETRY_DAYS, default 3).
    """
    if retry_days is None:
        retry_days = PENDING_RETRY_DAYS
    try:
        from tracking.database import delete_unresolved_bets_older_than
        return delete_unresolved_bets_older_than(retry_days)
    except Exception as exc:
        _logger.error("[BetTracker] cleanup_unresolved_bets failed: %s", exc)
        return 0


def get_pipeline_performance_stats():
    """Per-source performance: WIN/LOSS/EVEN/VOID + win-rate per system.

    Returns a dict keyed by source ('quantum', 'qeg', 'smart_money',
    'platform_ai', 'manual', 'qeg_auto') with totals + win_rate.
    """
    from tracking.database import _db_read
    rows = _db_read(
        "SELECT COALESCE(source, 'manual') AS source, "
        "       UPPER(COALESCE(result, 'PENDING')) AS result, "
        "       COUNT(*) AS n "
        "FROM bets "
        "GROUP BY COALESCE(source, 'manual'), UPPER(COALESCE(result, 'PENDING'))",
        (),
    ) or []
    by_source: dict = {}
    for r in rows:
        src = r["source"]
        res = r["result"]
        n = int(r["n"] or 0)
        bucket = by_source.setdefault(
            src,
            {"wins": 0, "losses": 0, "evens": 0, "voids": 0, "pending": 0, "total": 0},
        )
        bucket["total"] += n
        if res == "WIN":
            bucket["wins"] += n
        elif res == "LOSS":
            bucket["losses"] += n
        elif res == "EVEN":
            bucket["evens"] += n
        elif res == "VOID":
            bucket["voids"] += n
        else:
            bucket["pending"] += n
    for src, b in by_source.items():
        decided = b["wins"] + b["losses"]
        b["win_rate"] = (b["wins"] / decided) if decided else 0.0
    return by_source


# ============================================================
# END SECTION: Pipeline Overhaul
# ============================================================

