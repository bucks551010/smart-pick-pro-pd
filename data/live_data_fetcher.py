# ============================================================
# FILE: data/live_data_fetcher.py
# PURPOSE: Fetch live, real NBA data from the nba_api library.
#          Pulls today's games, player stats, team stats, and
#          player game logs. Saves everything to CSV files so
#          the rest of the app works without any changes.
# CONNECTS TO: pages/8_🔄_Update_Data.py, data/data_manager.py
# CONCEPTS COVERED: APIs, rate limiting, CSV writing, error handling
#
# BEGINNER NOTE: An API (Application Programming Interface) is a
# way for programs to talk to each other. nba_api is a free Python
# library that talks to the NBA's official stats website for us.
# We never need an API key — it's completely free to use!
# ============================================================

# Standard library imports (no install needed — built into Python)
import csv          # For reading and writing CSV files
import json         # For reading and writing JSON files (timestamps, etc.)
import math         # For isfinite checks in safe_avg
import time         # For adding delays between API calls
import datetime     # For timestamps and date handling
import statistics   # For calculating standard deviations
from pathlib import Path  # Modern, cross-platform file path handling

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

try:
    from data.game_log_cache import save_game_logs_to_cache, load_game_logs_from_cache
    _GAME_LOG_CACHE_AVAILABLE = True
except ImportError:
    _GAME_LOG_CACHE_AVAILABLE = False

# Feature 12: SQLite game log persistence (write-through alongside JSON cache)
try:
    from tracking.database import (
        save_player_game_logs_to_db,
        load_player_game_logs_from_db,
        is_game_log_cache_stale,
    )
    _DB_GAME_LOG_AVAILABLE = True
except ImportError:
    _DB_GAME_LOG_AVAILABLE = False

try:
    from utils.rate_limiter import RateLimiter
    _rate_limiter = RateLimiter(max_requests_per_minute=15, max_requests_per_hour=150)
    _RATE_LIMITER_AVAILABLE = True
except ImportError:
    _RATE_LIMITER_AVAILABLE = False
    _rate_limiter = None

try:
    from utils.headers import get_espn_headers
    _HAS_HEADERS = True
except ImportError:
    _HAS_HEADERS = False

try:
    from utils.retry import retry_with_backoff
    _HAS_RETRY = True
except ImportError:
    _HAS_RETRY = False

try:
    from data.player_id_cache import PlayerIDCache
    _player_id_cache = PlayerIDCache()
    _HAS_PLAYER_ID_CACHE = True
except ImportError:
    _player_id_cache = None
    _HAS_PLAYER_ID_CACHE = False

# ============================================================
# SECTION: File Path Constants
# Same data directory as data_manager.py
# ============================================================

# Get the directory where this file lives (the 'data' folder)
DATA_DIRECTORY = Path(__file__).parent

# Paths to each CSV file we will write
PLAYERS_CSV_PATH = DATA_DIRECTORY / "players.csv"             # Player stats output
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"                   # Team stats output
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"  # Defensive ratings output

# Path to the JSON file that tracks when each data type was last updated
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"

# Path to the JSON file that caches the player injury/availability status map.
# Written by fetch_todays_players_only() via RosterEngine and read by data_manager.get_player_status().
INJURY_STATUS_JSON_PATH = DATA_DIRECTORY / "injury_status.json"

# How long to wait between API calls (in seconds) to avoid being blocked
# BEGINNER NOTE: Rate limiting means the NBA website limits how fast
# you can make requests. If you ask too fast, they block you temporarily.
# Adding a 1.5 second delay between calls keeps us polite and avoids blocks.
API_DELAY_SECONDS = 1.5

# ============================================================
# Standard deviation ratio constants for stat fallback estimates.
# These are used when game log data is unavailable for a player.
# Values are empirically derived from NBA stat distributions.
#
# NOTE (W10): The fixed ratios below are kept for backward compatibility.
# The new _dynamic_cv_for_live_fetch() function uses tier-based CV
# which is called at the point of fallback estimate computation.
# ============================================================
FALLBACK_POINTS_STD_RATIO = 0.3      # Points: ~30% CV is typical for scorers
FALLBACK_REBOUNDS_STD_RATIO = 0.4    # Rebounds: ~40% CV — more variable
FALLBACK_ASSISTS_STD_RATIO = 0.4     # Assists: ~40% CV — game-plan dependent
FALLBACK_THREES_STD_RATIO = 0.55     # 3-pointers: ~55% CV — streaky (minimum)
FALLBACK_STEALS_STD_RATIO = 0.5      # Steals: ~50% CV
FALLBACK_BLOCKS_STD_RATIO = 0.6      # Blocks: ~60% CV
FALLBACK_TURNOVERS_STD_RATIO = 0.4   # Turnovers: ~40% CV
FALLBACK_FTM_STD_RATIO = 0.45        # Free throws made: ~45% CV
FALLBACK_FTA_STD_RATIO = 0.45        # Free throws attempted: ~45% CV
FALLBACK_FGA_STD_RATIO = 0.35        # FG attempts: ~35% CV
FALLBACK_FGM_STD_RATIO = 0.38        # FG made: ~38% CV
FALLBACK_OREB_STD_RATIO = 0.52       # Offensive rebounds: ~52% CV
FALLBACK_DREB_STD_RATIO = 0.42       # Defensive rebounds: ~42% CV
FALLBACK_PF_STD_RATIO = 0.50         # Personal fouls: ~50% CV

# Minimum minutes threshold to include a player's stats.
# Players below this threshold are considered inactive/garbage-time only.
# Problem statement requires 15+ MPG for live fetch; we keep 10 for fallback.
MIN_MINUTES_THRESHOLD = 15.0

# Games-missed threshold for the recency proxy in fetch_todays_players_only().
# If a player has missed more than this many games relative to their team's max GP,
# they are likely on a long-term absence even if not explicitly in the injury report.
# 12 games ≈ 2-3 weeks of absence; requires the team to have played 20+ games first.
GP_ABSENT_THRESHOLD = 12
MIN_TEAM_GP_FOR_RECENCY_CHECK = 20

# Position map: nba_api START_POSITION codes → our position labels.
# Defined at module level to avoid re-creating the dict on every function call.
_POSITION_MAP = {
    "G":   "PG", "F":   "SF", "C":  "C",
    "G-F": "SF", "F-G": "SG", "F-C": "PF", "C-F": "PF", "": "SF",
}

# Recent-form trend thresholds: how much above/below season avg to be "hot"/"cold"
HOT_TREND_THRESHOLD = 1.1   # Last 3 games avg ≥ 110% of recent avg = hot
COLD_TREND_THRESHOLD = 0.9  # Last 3 games avg ≤ 90% of recent avg = cold

# ============================================================
# Game fetcher defaults (placeholder values used until live odds are added)
# ============================================================
DEFAULT_VEGAS_SPREAD = 0.0   # No live spread data yet; shown as 0 until integrated
DEFAULT_GAME_TOTAL = 220.0   # Typical NBA over/under baseline used as placeholder

# Timeout for the ESPN public scoreboard HTTP request (seconds)
ESPN_API_TIMEOUT_SECONDS = 10

# ── nba_api request timeouts (seconds) ───────────────────────
# Without explicit timeouts, nba_api calls can hang indefinitely
# and freeze the entire Streamlit app.  These are shorter than the
# ETL constants (etl/initial_pull.py) because live-page fetches
# must stay responsive.
NBA_API_BULK_TIMEOUT = 30        # LeagueDashPlayerStats, LeagueDashTeamStats
NBA_API_SCOREBOARD_TIMEOUT = 15  # ScoreboardV3
NBA_API_STANDINGS_TIMEOUT = 15   # LeagueStandingsV3
NBA_API_GAMELOG_TIMEOUT = 15     # PlayerGameLog

# Injury status values that indicate a player is unavailable.
# Used by fetch_todays_players_only() and fetch_player_stats() to
# filter out inactive players before writing to CSV.
#
# Note: "Doubtful" and "Questionable" are included here because
# players with these designations almost never play and including
# them in simulations/props would produce unreliable predictions.
# GTD (Game Time Decision) and Day-to-Day players are treated
# differently — they remain in the roster but receive a warning
# flag via GTD_INJURY_STATUSES below.
INACTIVE_INJURY_STATUSES = frozenset({
    "Out",
    "Doubtful",
    "Questionable",
    "Injured Reserve",
    "Out (No Recent Games)",
    "Suspended",
    "Not With Team",
    "G League - Two-Way",
    "G League - On Assignment",
    "G League",
})

# Statuses that are not fully removed but should be flagged separately
# (e.g., GTD players remain selectable but show a warning badge).
GTD_INJURY_STATUSES = frozenset({
    "GTD",
    "Day-to-Day",
})

# ============================================================
# END SECTION: File Path Constants
# ============================================================


def _safe_get_first_dataframe(endpoint, default=None):
    """Safely extract the first DataFrame from an nba_api endpoint.

    Guards against empty or missing results that would otherwise raise
    an ``IndexError`` when accessing ``get_data_frames()[0]``.  Any
    exception raised by ``get_data_frames()`` (network errors, JSON
    parse failures, etc.) is caught, logged at DEBUG level, and
    *default* is returned instead.

    Args:
        endpoint: An nba_api endpoint instance that supports
            ``get_data_frames()``.
        default: Value to return when no DataFrame is available
            (default ``None``).

    Returns:
        pandas.DataFrame or *default*.
    """
    try:
        dfs = endpoint.get_data_frames()
        if dfs and len(dfs) > 0 and not dfs[0].empty:
            return dfs[0]
    except Exception as exc:
        _logger.debug("_safe_get_first_dataframe: %s", exc)
    return default


def _nba_today_et():
    """Return today's date anchored to US/Eastern time.

    NBA defines game dates in Eastern Time. A server running in UTC
    would shift the date boundary by 5 hours, causing late West-Coast
    games (which tip off at 10:30 PM ET / 3:30 AM UTC) to be assigned
    to the wrong calendar day.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    (EDT = UTC-4). Install ``tzdata`` for correct DST handling.
    """
    try:
        from zoneinfo import ZoneInfo
        _eastern = ZoneInfo("America/New_York")
    except ImportError:
        _eastern = datetime.timezone(datetime.timedelta(hours=-5))
    return datetime.datetime.now(_eastern).date()


def _current_season() -> str:
    """Return the current NBA season string in 'YYYY-YY' format.

    The NBA season starts in October.  If the current month is October
    or later, the season is ``YYYY-(YY+1)``.  Otherwise it is
    ``(YYYY-1)-YY``.

    Example: March 2026 → ``'2025-26'``, November 2025 → ``'2025-26'``.
    """
    now = datetime.date.today()
    year = now.year if now.month >= 10 else now.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


# ============================================================
# SECTION: NBA Team Abbreviation Mapping
# nba_api uses team IDs internally; we need abbreviations.
# This maps the team full name to our 3-letter abbreviation.
# ============================================================

# Complete mapping of NBA team full names to abbreviations
# BEGINNER NOTE: This dictionary lets us look up an abbreviation
# by giving it the full team name as a key.
TEAM_NAME_TO_ABBREVIATION = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

# Map nba_api's team abbreviations to our abbreviations
# (nba_api sometimes uses slightly different codes, e.g. "GS" vs "GSW").
# Built dynamically from nba_api's local static teams list at import time
# so new teams (expansion) are covered automatically.  The hardcoded dict
# is used as the fallback when nba_api is unavailable.
_NBA_API_ABBREV_TO_OURS_FALLBACK: dict[str, str] = {
    "GS": "GSW",   # Golden State Warriors
    "NY": "NYK",   # New York Knicks
    "NO": "NOP",   # New Orleans Pelicans
    "SA": "SAS",   # San Antonio Spurs
    "OKC": "OKC",  # Oklahoma City Thunder (same)
    "PHX": "PHX",  # Phoenix Suns (same)
    "UTA": "UTA",  # Utah Jazz (same)
    "MEM": "MEM",  # Memphis Grizzlies (same)
    # ESPN aliases
    "UTAH": "UTA", # ESPN uses UTAH for Utah Jazz
    "WSH": "WAS",  # ESPN uses WSH for Washington Wizards
}


def _build_nba_abbrev_map() -> dict[str, str]:
    """Build a nba_api abbreviation → our abbreviation mapping.

    Uses ``nba_api.stats.static.teams.get_teams()`` — a local file read with
    no network call — to seed an identity mapping for all 30 current teams.
    The hardcoded alias pairs (GS→GSW, etc.) are then merged in so that
    short-form codes returned by some endpoints translate correctly.

    Returns
    -------
    dict[str, str]
        Mapping of nba_api abbreviation strings to our canonical abbreviations.
        Falls back to ``_NBA_API_ABBREV_TO_OURS_FALLBACK`` on any error.
    """
    try:
        from nba_api.stats.static import teams as _nba_teams_static
        nba_teams = _nba_teams_static.get_teams()
        # Build identity mapping: "GSW" → "GSW", "LAL" → "LAL", etc.
        mapping = {t["abbreviation"]: t["abbreviation"] for t in nba_teams}
        # Merge in the known short-form aliases (they override if present)
        mapping.update(_NBA_API_ABBREV_TO_OURS_FALLBACK)
        return mapping
    except Exception:
        return dict(_NBA_API_ABBREV_TO_OURS_FALLBACK)


NBA_API_ABBREV_TO_OURS: dict[str, str] = _build_nba_abbrev_map()

# Conference mapping by abbreviation.
# Intentionally hardcoded: NBA conference membership does not change
# during a season, and this lookup is faster than a DB query.
TEAM_CONFERENCE = {
    "ATL": "East", "BOS": "East", "BKN": "East", "CHA": "East",
    "CHI": "East", "CLE": "East", "DET": "East", "IND": "East",
    "MIA": "East", "MIL": "East", "NYK": "East", "ORL": "East",
    "PHI": "East", "TOR": "East", "WAS": "East",
    "DAL": "West", "DEN": "West", "GSW": "West", "HOU": "West",
    "LAC": "West", "LAL": "West", "MEM": "West", "MIN": "West",
    "NOP": "West", "OKC": "West", "PHX": "West", "POR": "West",
    "SAC": "West", "SAS": "West", "UTA": "West",
}

# ============================================================
# END SECTION: NBA Team Abbreviation Mapping
# ============================================================


# ============================================================
# SECTION: Timestamp Functions
# Track when each piece of data was last fetched.
# ============================================================

def save_last_updated(data_type):
    """
    Save the current timestamp to last_updated.json for a given data type.

    This lets the app display "Last updated: 2026-03-06 14:30" so the
    user knows how fresh their data is.

    Args:
        data_type (str): What was updated, e.g. 'players', 'teams', 'games'
    """
    # Load existing timestamps if the file exists
    existing_timestamps = {}  # Start with empty dict

    # Check if the file already exists
    if LAST_UPDATED_JSON_PATH.exists():
        try:
            # Open and read the existing JSON file
            with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
                existing_timestamps = json.load(json_file)  # Parse JSON into dict
        except Exception:
            existing_timestamps = {}  # If file is broken, start fresh

    # Add/update the timestamp for this data type (always UTC).
    # Using UTC avoids ambiguity when the server timezone differs from ET.
    existing_timestamps[data_type] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Also save an "is_live" flag to indicate real data is loaded
    existing_timestamps["is_live"] = True

    # Write the updated timestamps back to the file
    try:
        with open(LAST_UPDATED_JSON_PATH, "w") as json_file:
            # indent=2 makes the JSON file human-readable with indentation
            json.dump(existing_timestamps, json_file, indent=2)
    except Exception as error:
        # If we can't save, just print a warning — it's not critical
        _logger.warning(f"Warning: Could not save timestamp: {error}")


def _invalidate_data_caches():
    """
    Bust all st.cache_data caches for CSV loaders in data_manager.py.

    Called after writing fresh data to disk so the next Streamlit read
    picks up the new file content instead of a stale in-memory copy.
    Imported lazily to avoid circular imports (live_data_fetcher is
    loaded early in the Python import chain).

    BEGINNER NOTE: Streamlit's @st.cache_data caches function results
    in memory.  We must call .clear() after writing new CSV data
    so the cache doesn't serve the old data.
    """
    try:
        from data.data_manager import (  # noqa: C0415 (lazy import intentional)
            load_players_data,
            load_teams_data,
            load_defensive_ratings_data,
            load_props_data,
            load_injury_status,
        )
        load_players_data.clear()
        load_teams_data.clear()
        load_defensive_ratings_data.clear()
        load_props_data.clear()
        load_injury_status.clear()
        _logger.debug("Streamlit data caches cleared after CSV update.")
    except Exception:
        pass  # Cache clearing is best-effort — never block a data fetch


def load_last_updated():
    """
    Load all timestamps from last_updated.json.

    Returns:
        dict: Timestamps for each data type, or empty dict if no file.

    Example return value:
        {
            "players": "2026-03-06T14:30:00",
            "teams": "2026-03-06T14:31:30",
            "is_live": True
        }
    """
    # If no file exists, return empty dict (no data has been fetched)
    if not LAST_UPDATED_JSON_PATH.exists():
        return {}  # Empty dict means no live data yet

    try:
        # Open and parse the JSON file
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            return json.load(json_file)  # Returns a dictionary
    except Exception:
        return {}  # If file is broken, return empty dict

# ============================================================
# END SECTION: Timestamp Functions
# ============================================================


# ============================================================
# SECTION: Helper Utilities
# Small internal helpers used by multiple fetcher functions.
# ============================================================

def _parse_win_loss_record(record_str):
    """
    Parse a win-loss record string like '15-8' into (wins, losses).

    Args:
        record_str (str): A string in the format 'W-L', e.g. '15-8'

    Returns:
        tuple: (wins: int, losses: int). Returns (0, 0) on failure.
    """
    try:
        parts = str(record_str or "0-0").split("-")
        wins = int(parts[0]) if parts else 0
        losses = int(parts[1]) if len(parts) > 1 else 0
        return wins, losses
    except (ValueError, IndexError):
        return 0, 0


def _utc_to_et_display(game_time_utc):
    """
    Convert a UTC ISO timestamp string to Eastern Time display string.

    Determines whether to apply EST (-5) or EDT (-4) offset based on
    the current date using Python's time module DST flag.

    Args:
        game_time_utc (str): ISO timestamp like '2026-03-06T23:30:00Z'

    Returns:
        str: Time string like '7:30 PM ET', or '' on failure.
    """
    if not game_time_utc:
        return ""
    try:
        # Determine current ET offset using DST flag
        import time as _time_mod
        dst_active = bool(_time_mod.localtime().tm_isdst)
        et_offset_hours = -4 if dst_active else -5  # EDT or EST

        utc_dt = datetime.datetime.fromisoformat(
            game_time_utc.replace("Z", "+00:00")
        )
        et_dt = utc_dt + datetime.timedelta(hours=et_offset_hours)
        # Use %I:%M %p for cross-platform compatibility (no %-I)
        time_str = et_dt.strftime("%I:%M %p ET").lstrip("0")
        return time_str
    except Exception:
        return ""

# ============================================================
# END SECTION: Helper Utilities
# ============================================================


# ============================================================
# SECTION: Today's Games Fetcher
# Fetches which NBA games are being played today using a
# 3-layer fallback system for maximum reliability.
# ============================================================

def _fetch_team_records():
    """
    Fetch team records (W-L, streak, home/away splits) from the NBA standings.

    Shared helper used by all three game-fetching layers so standings are
    only pulled once regardless of which layer succeeds.

    Returns:
        dict: Maps team abbreviation → {wins, losses, streak,
              home_record, away_record, conf_rank}.
              Returns empty dict if all sources fail.
    """
    team_records = {}

    # ── DB first ──────────────────────────────────────────────
    try:
        from data.etl_data_service import _get_conn
        conn = _get_conn()
        if conn is not None:
            try:
                rows = conn.execute(
                    "SELECT t.abbreviation, s.wins, s.losses, "
                    "       s.str_current_streak, s.home, s.road, "
                    "       s.playoff_rank "
                    "FROM Standings s "
                    "JOIN Teams t ON t.team_id = s.team_id"
                ).fetchall()
                for r in rows:
                    abbrev = str(r["abbreviation"] or "")
                    if not abbrev:
                        continue
                    streak_raw = str(r["str_current_streak"] or "")
                    if streak_raw and len(streak_raw) >= 2:
                        streak_dir = streak_raw[0]
                        streak_num = streak_raw[1:].strip()
                        streak_display = f"{streak_dir}{streak_num}"
                    else:
                        streak_display = ""
                    home_w, home_l = _parse_win_loss_record(r["home"] or "0-0")
                    away_w, away_l = _parse_win_loss_record(r["road"] or "0-0")
                    team_records[abbrev] = {
                        "wins": int(r["wins"] or 0),
                        "losses": int(r["losses"] or 0),
                        "streak": streak_display,
                        "home_record": f"{home_w}-{home_l}",
                        "away_record": f"{away_w}-{away_l}",
                        "conf_rank": int(r["playoff_rank"] or 0),
                    }
                if team_records:
                    _logger.info("_fetch_team_records: loaded %d teams from DB.", len(team_records))
                    return team_records
            finally:
                conn.close()
    except Exception as db_err:
        _logger.debug("_fetch_team_records DB fallback failed: %s", db_err)

    # ── nba_api (live API fallback) ───────────────────────────
    try:
        from nba_api.stats.endpoints import leaguestandingsv3
        standings_endpoint = leaguestandingsv3.LeagueStandingsV3(
            season=_current_season(),
            season_type="Regular Season",
            timeout=NBA_API_STANDINGS_TIMEOUT,
        )
        _standings_df = _safe_get_first_dataframe(standings_endpoint)
        if _standings_df is None:
            raise RuntimeError("LeagueStandingsV3 returned no data")
        standings_data = _standings_df.to_dict("records")
        time.sleep(API_DELAY_SECONDS)

        for row in standings_data:
            abbrev = row.get("TeamSlug", "").upper()
            # nba_api standings use TeamAbbreviation
            abbrev = row.get("TeamAbbreviation", abbrev)
            abbrev = NBA_API_ABBREV_TO_OURS.get(abbrev, abbrev)
            if not abbrev:
                continue

            wins = int(row.get("WINS", 0) or 0)
            losses = int(row.get("LOSSES", 0) or 0)

            # Parse streak: e.g. "W 3" or "L 2"
            streak_raw = str(row.get("strCurrentStreak", "") or "")
            if streak_raw and len(streak_raw) >= 2:
                streak_dir = streak_raw[0]   # "W" or "L"
                streak_num = streak_raw[1:].strip()
                streak_display = f"{streak_dir}{streak_num}"
            else:
                streak_display = ""

            # Home and away records — use helper to avoid duplicated parsing
            home_wins_s, home_losses_s = _parse_win_loss_record(row.get("HOME", "0-0"))
            away_wins_s, away_losses_s = _parse_win_loss_record(row.get("ROAD", "0-0"))

            conf_rank = int(row.get("PlayoffRank", 0) or 0)

            team_records[abbrev] = {
                "wins": wins,
                "losses": losses,
                "streak": streak_display,
                "home_record": f"{home_wins_s}-{home_losses_s}",
                "away_record": f"{away_wins_s}-{away_losses_s}",
                "conf_rank": conf_rank,
            }
    except Exception as standings_error:
        _logger.warning(f"Could not fetch standings (non-fatal): {standings_error}")

    return team_records


def _build_formatted_game(home_abbrev, away_abbrev, home_team_name, away_team_name,
                           game_time_et, arena_display, team_records,
                           game_id=""):
    """
    Build the standardised game dict used throughout the app.

    Args:
        home_abbrev (str): Home team abbreviation (our format).
        away_abbrev (str): Away team abbreviation (our format).
        home_team_name (str): Full display name for the home team.
        away_team_name (str): Full display name for the away team.
        game_time_et (str): Game time in Eastern Time, e.g. "7:30 PM ET".
        arena_display (str): Arena name and city string.
        team_records (dict): Standings data from _fetch_team_records().
        game_id (str): Official NBA game ID (10-digit numeric string).
            Falls back to ``"HOME_vs_AWAY"`` when unavailable.

    Returns:
        dict: Standardised game record.
    """
    home_rec = team_records.get(home_abbrev, {})
    away_rec = team_records.get(away_abbrev, {})

    actual_id = game_id if game_id and game_id not in ("0", "", "0000000000") else ""
    is_synthetic = not actual_id
    if is_synthetic:
        actual_id = f"{home_abbrev}_vs_{away_abbrev}"
        _logger.info(
            "_build_formatted_game: no real game_id for %s vs %s, using synthetic=%r",
            away_abbrev, home_abbrev, actual_id,
        )
    return {
        "game_id": actual_id,
        "is_synthetic": is_synthetic,
        "home_team": home_abbrev,
        "away_team": away_abbrev,
        "home_team_full": f"{home_abbrev} — {home_team_name}",
        "away_team_full": f"{away_abbrev} — {away_team_name}",
        "home_team_name": home_team_name,
        "away_team_name": away_team_name,
        "vegas_spread": DEFAULT_VEGAS_SPREAD,
        "game_total": DEFAULT_GAME_TOTAL,
        "game_date": _nba_today_et().isoformat(),
        "game_time_et": game_time_et,
        "arena": arena_display,
        # Team records
        "home_wins": home_rec.get("wins", 0),
        "home_losses": home_rec.get("losses", 0),
        "home_streak": home_rec.get("streak", ""),
        "home_home_record": home_rec.get("home_record", ""),
        "home_conf_rank": home_rec.get("conf_rank", 0),
        "away_wins": away_rec.get("wins", 0),
        "away_losses": away_rec.get("losses", 0),
        "away_streak": away_rec.get("streak", ""),
        "away_away_record": away_rec.get("away_record", ""),
        "away_conf_rank": away_rec.get("conf_rank", 0),
    }


def _fetch_games_layer1_scoreboard_v2(team_records):
    """
    Layer 1: Fetch today's games via the NBA Stats ScoreboardV3 endpoint.

    ScoreboardV3 replaces the deprecated ScoreboardV2 and is fully backward
    compatible.  It exposes ``game_header`` and ``line_score`` DataSets whose
    DataFrames use camelCase column names.

    Args:
        team_records (dict): Pre-fetched standings data from _fetch_team_records().

    Returns:
        list of dict: Formatted game records, or empty list on failure.
    """
    try:
        import concurrent.futures
        from nba_api.stats.endpoints import scoreboardv3

        today_str = _nba_today_et().strftime("%Y-%m-%d")  # V3 uses YYYY-MM-DD

        # Wrap in a thread so the OS-level TCP timeout is enforced.
        # nba_api's own `timeout` param only sets the requests session
        # read-timeout but can still block on DNS / connect indefinitely.
        def _call_scoreboard():
            return scoreboardv3.ScoreboardV3(
                game_date=today_str,
                timeout=NBA_API_SCOREBOARD_TIMEOUT,
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
                _fut = _ex.submit(_call_scoreboard)
                sb = _fut.result(timeout=NBA_API_SCOREBOARD_TIMEOUT)
        except concurrent.futures.TimeoutError:
            _logger.warning(
                "Layer 1 (ScoreboardV3) timed out after %ds — skipping to Layer 2",
                NBA_API_SCOREBOARD_TIMEOUT,
            )
            return []

        time.sleep(API_DELAY_SECONDS)

        # ── Game headers (gameId, gameStatusText, …) ────────
        try:
            game_header_df = sb.game_header.get_data_frame()
        except Exception:
            game_header_df = None
        if game_header_df is None or game_header_df.empty:
            return []

        # ── Line scores contain team info per game ──────────
        try:
            line_score_df = sb.line_score.get_data_frame()
        except Exception:
            line_score_df = None

        # Build gameId → {home_*, away_*} mapping from line scores.
        # Each game has two rows (one per team); the second row is
        # typically the home team, but we use index position to be safe.
        game_teams: dict = {}
        if line_score_df is not None and not line_score_df.empty:
            for gid, grp in line_score_df.groupby("gameId"):
                rows = grp.to_dict("records")
                if len(rows) >= 2:
                    away_row, home_row = rows[0], rows[1]
                    away_tc = NBA_API_ABBREV_TO_OURS.get(
                        away_row.get("teamTricode", ""),
                        away_row.get("teamTricode", ""),
                    )
                    home_tc = NBA_API_ABBREV_TO_OURS.get(
                        home_row.get("teamTricode", ""),
                        home_row.get("teamTricode", ""),
                    )
                    game_teams[str(gid)] = {
                        "home_abbrev": home_tc,
                        "away_abbrev": away_tc,
                        "home_team_name": f"{home_row.get('teamCity', '')} {home_row.get('teamName', '')}".strip(),
                        "away_team_name": f"{away_row.get('teamCity', '')} {away_row.get('teamName', '')}".strip(),
                    }

        formatted_games = []
        for row in game_header_df.to_dict("records"):
            gid = str(row.get("gameId") or "")
            info = game_teams.get(gid, {})

            home_abbrev = info.get("home_abbrev", "")
            away_abbrev = info.get("away_abbrev", "")
            if not home_abbrev or not away_abbrev:
                continue

            game_time_et = str(row.get("gameStatusText", "") or "").strip()

            formatted_games.append(_build_formatted_game(
                home_abbrev, away_abbrev,
                info.get("home_team_name", ""),
                info.get("away_team_name", ""),
                game_time_et, "",
                team_records,
                game_id=gid,
            ))

        return formatted_games

    except Exception as error:
        _logger.warning(f"Layer 1 (ScoreboardV3) failed: {error}")
        return []


def _fetch_games_layer2_espn(team_records):
    """
    Layer 2: Fetch today's games via the ESPN public scoreboard API.

    ESPN provides a free, unauthenticated JSON endpoint that returns the
    current day's NBA schedule.  No API key required.

    Args:
        team_records (dict): Pre-fetched standings data from _fetch_team_records().

    Returns:
        list of dict: Formatted game records, or empty list on failure.
    """
    try:
        import requests

        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        _espn_headers = get_espn_headers() if _HAS_HEADERS else {}
        resp = requests.get(url, headers=_espn_headers, timeout=ESPN_API_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return []

        # ESPN returns multi-day slates and uses UTC dates.
        # West-Coast games (e.g. 10 PM ET = 02:00 UTC next day) would be
        # tagged as "tomorrow" in UTC. Convert each event's UTC timestamp
        # to ET before comparing against today's ET date.
        import time as _time_mod
        _dst_active = bool(_time_mod.localtime().tm_isdst)
        _et_offset = datetime.timedelta(hours=-4 if _dst_active else -5)
        _today_et = _nba_today_et()

        def _event_et_date(ev):
            raw = (ev.get("date", "") or "")
            try:
                utc_dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return (utc_dt + _et_offset).date()
            except Exception:
                return None

        events = [ev for ev in events if _event_et_date(ev) == _today_et]
        if not events:
            _logger.warning(
                "Layer 2 (ESPN): no events matched today (%s) after ET date filter",
                _today_et,
            )
            return []

        formatted_games = []
        for event in events:
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            comp = competitions[0]

            competitors = comp.get("competitors", [])
            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home_comp or not away_comp:
                continue

            home_team = home_comp.get("team", {})
            away_team = away_comp.get("team", {})

            home_abbrev = home_team.get("abbreviation", "")
            away_abbrev = away_team.get("abbreviation", "")

            # Normalise ESPN abbreviations to our internal codes
            home_abbrev = NBA_API_ABBREV_TO_OURS.get(home_abbrev, home_abbrev)
            away_abbrev = NBA_API_ABBREV_TO_OURS.get(away_abbrev, away_abbrev)

            if not home_abbrev or not away_abbrev:
                continue

            # Game time — ESPN uses ISO 8601 UTC in startDate
            start_date = comp.get("startDate", event.get("date", ""))
            game_time_et = _utc_to_et_display(start_date)

            # Venue
            venue = comp.get("venue", {})
            arena_name = venue.get("fullName", "")
            arena_city = venue.get("address", {}).get("city", "")
            arena_display = f"{arena_name}, {arena_city}".strip(", ") if arena_name else ""

            home_team_name = home_team.get("displayName", "")
            away_team_name = away_team.get("displayName", "")

            formatted_games.append(_build_formatted_game(
                home_abbrev, away_abbrev,
                home_team_name, away_team_name,
                game_time_et, arena_display,
                team_records,
            ))

        return formatted_games

    except Exception as error:
        _logger.warning(f"Layer 2 (ESPN API) failed: {error}")
        return []


def _fetch_games_layer3_live_scoreboard(team_records):
    """
    Layer 3: Fetch today's games via the nba_api live ScoreBoard endpoint.

    This is the original single-source implementation, retained as the
    final fallback when both ScoreboardV3 and the ESPN API are unavailable.

    Args:
        team_records (dict): Pre-fetched standings data from _fetch_team_records().

    Returns:
        list of dict: Formatted game records, or empty list on failure.
    """
    try:
        from nba_api.live.nba.endpoints import scoreboard as live_scoreboard

        board = live_scoreboard.ScoreBoard()
        games_data = board.games.get_dict()

        formatted_games = []

        for game in games_data:
            home_team_info = game.get("homeTeam", {})
            away_team_info = game.get("awayTeam", {})

            home_abbrev = home_team_info.get("teamTricode", "")
            away_abbrev = away_team_info.get("teamTricode", "")

            home_abbrev = NBA_API_ABBREV_TO_OURS.get(home_abbrev, home_abbrev)
            away_abbrev = NBA_API_ABBREV_TO_OURS.get(away_abbrev, away_abbrev)

            if not home_abbrev or not away_abbrev:
                continue

            game_time_et = _utc_to_et_display(game.get("gameTimeUTC", ""))

            arena = game.get("arenaName", "")
            arena_city = game.get("arenaCity", "")
            arena_display = f"{arena}, {arena_city}".strip(", ") if arena else ""

            home_team_name = f"{home_team_info.get('teamCity', '')} {home_team_info.get('teamName', '')}".strip()
            away_team_name = f"{away_team_info.get('teamCity', '')} {away_team_info.get('teamName', '')}".strip()

            nba_game_id = str(game.get("gameId") or "")

            formatted_games.append(_build_formatted_game(
                home_abbrev, away_abbrev,
                home_team_name, away_team_name,
                game_time_et, arena_display,
                team_records,
                game_id=nba_game_id,
            ))

        # ── ET date filter ────────────────────────────────────────────────
        # The live scoreboard keeps completed games in its buffer for hours
        # after they finish.  Filter to today's ET sports day only — same
        # guard that Layer 2 (ESPN) already applies.
        _today_iso = _nba_today_et().isoformat()
        formatted_games = [
            g for g in formatted_games
            if g.get("game_date", _today_iso) == _today_iso
        ]
        if not formatted_games:
            _logger.info(
                "Layer 3 (Live ScoreBoard): all games filtered out (not today %s) — returning []",
                _today_iso,
            )

        time.sleep(API_DELAY_SECONDS)
        return formatted_games

    except Exception as error:
        _logger.warning(f"Layer 3 (Live ScoreBoard) failed: {error}")
        return []


def _deduplicate_games(games: list) -> list:
    """Return *games* with duplicate matchups removed.

    Two entries are considered duplicates when they share the same
    home_team + away_team pair (case-insensitive).  The first occurrence
    is kept and any subsequent duplicate is silently dropped.  A unique
    game_id (if present) is also used as an alternative deduplication key.
    """
    seen_matchups: set = set()
    seen_game_ids: set = set()
    deduped: list = []
    for g in (games or []):
        game_id = g.get("game_id", "")
        home = g.get("home_team", "").upper().strip()
        away = g.get("away_team", "").upper().strip()
        matchup_key = (home, away)
        if game_id and game_id in seen_game_ids:
            continue
        if home and away and matchup_key in seen_matchups:
            continue
        if game_id:
            seen_game_ids.add(game_id)
        if home and away:
            seen_matchups.add(matchup_key)
        deduped.append(g)
    return deduped


def fetch_todays_games():
    """
    Fetch tonight's NBA games using a 4-layer fallback system.

    Attempts each source in order, falling through to the next if a layer
    fails or returns no games.

    Layers:
        1. ScoreboardV3        — NBA Stats API
        2. ESPN Public API     — free unauthenticated endpoint (fallback)
        3. Live ScoreBoard     — nba_api live endpoint (final fallback)

    Returns:
        list of dict: Tonight's games, each with home_team, away_team,
                      team records, streak info, and default Vegas lines.
                      Returns empty list if all layers fail or no games today.
    """
    # Fetch team records once — shared by all layers

    team_records = _fetch_team_records()

    # --------------------------------------------------------
    # Layer 1: ScoreboardV3
    # --------------------------------------------------------
    _logger.info("Trying Layer 1: ScoreboardV3...")
    layer1_games = _fetch_games_layer1_scoreboard_v2(team_records)

    if layer1_games:
        _logger.info(f"Layer 1 success: {len(layer1_games)} game(s) found.")
        # Cross-validate against Layer 2 — if Layer 2 finds MORE games, merge
        # so that late-added games (e.g. a 3rd game that hadn't appeared in
        # ScoreboardV3 yet) are included.
        try:
            layer2_games = _fetch_games_layer2_espn(team_records)
            if layer2_games and len(layer2_games) != len(layer1_games):
                _logger.info(
                    f"Cross-validation: Layer 1 found {len(layer1_games)} game(s), "
                    f"Layer 2 found {len(layer2_games)} game(s). Merging results."
                )
            if layer2_games and len(layer2_games) > len(layer1_games):
                # Merge: prefer Layer 1 entries (have real game_id), fill in
                # any extra games from Layer 2 that Layer 1 missed.
                merged: dict = {}
                for g in layer1_games:
                    key = g.get("game_id", f"{g['home_team']}_vs_{g['away_team']}")
                    merged[key] = g
                for g in layer2_games:
                    # Match by team pair regardless of game_id format
                    pair_key = f"{g['home_team']}_vs_{g['away_team']}"
                    already_present = any(
                        existing.get("home_team") == g["home_team"]
                        and existing.get("away_team") == g["away_team"]
                        for existing in merged.values()
                    )
                    if not already_present:
                        _logger.info(
                            "Merge: adding Layer 2 game %s @ %s missing from Layer 1",
                            g["away_team"], g["home_team"],
                        )
                        merged[pair_key] = g
                return _deduplicate_games(list(merged.values()))
        except Exception as cv_error:
            _logger.warning(f"Cross-validation check failed (non-fatal): {cv_error}")
        return _deduplicate_games(layer1_games)

    # --------------------------------------------------------
    # Layer 2: ESPN Public API
    # --------------------------------------------------------
    _logger.info("Layer 1 failed. Trying Layer 2: ESPN Public API...")
    layer2_games = _fetch_games_layer2_espn(team_records)

    if layer2_games:
        _logger.info(f"Layer 2 success: {len(layer2_games)} game(s) found.")
        return _deduplicate_games(layer2_games)

    # --------------------------------------------------------
    # Layer 3: Live ScoreBoard
    # --------------------------------------------------------
    _logger.info("Layer 2 failed. Trying Layer 3: Live ScoreBoard...")
    layer3_games = _fetch_games_layer3_live_scoreboard(team_records)

    if layer3_games:
        _logger.info(f"Layer 3 success: {len(layer3_games)} game(s) found.")
    else:
        _logger.warning("All layers failed. No games available.")

    return _deduplicate_games(layer3_games or [])

# ============================================================
# END SECTION: Today's Games Fetcher
# ============================================================


# ============================================================
# SECTION: Targeted Roster-Based Data Fetcher
# Only fetches players on teams that are playing today.
# This is MUCH faster than fetching all 500+ NBA players.
# ============================================================

def fetch_todays_players_only(todays_games, progress_callback=None, precomputed_injury_map=None):
    """
    Fetch player stats ONLY for teams playing today.

    Streamlined pipeline:
    1. Identifies the teams playing today from todays_games
    2. Uses RosterEngine to get current rosters + live injury data in one pass
    3. Fetches ALL player season averages in ONE bulk LeagueDashPlayerStats call
    4. Pre-filters injured/inactive players using RosterEngine data before any
       further processing, avoiding wasted work
    5. Computes std devs from dynamic CV estimates — no per-player game log calls

    This approach reduces API calls from 380+ (one per player) to just 2-3 calls
    total and completes in seconds rather than 3-5+ minutes.

    Args:
        todays_games (list of dict): Tonight's games from fetch_todays_games()
        progress_callback (callable, optional): Called with (current, total, msg)
        precomputed_injury_map (dict, optional): Deprecated — no longer used.
            Injury data is sourced directly from RosterEngine inside this
            function. This parameter is kept for backward API compatibility
            but is silently ignored.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
    except ImportError:
        _logger.error("ERROR: nba_api is not installed. Run: pip install nba_api")
        return False

    if not todays_games:
        _logger.info("No games provided — nothing to fetch.")
        return False

    try:
        # --------------------------------------------------------
        # Step 1: Identify which teams are playing today
        # --------------------------------------------------------
        playing_team_abbrevs = set()
        for game in todays_games:
            playing_team_abbrevs.add(game.get("home_team", ""))
            playing_team_abbrevs.add(game.get("away_team", ""))
        playing_team_abbrevs.discard("")  # Remove empty strings

        _logger.info(f"Fetching rosters for {len(playing_team_abbrevs)} teams: {sorted(playing_team_abbrevs)}")

        if progress_callback:
            progress_callback(0, 10, f"Found {len(playing_team_abbrevs)} teams playing today. Fetching rosters...")

        # --------------------------------------------------------
        # Step 2: Use RosterEngine to get rosters + live injury data in one pass
        # --------------------------------------------------------
        all_roster_players = []  # {player_id, player_name, team, position}
        _roster_engine = None
        seen_pids = set()  # Deduplication: avoid processing the same player twice

        try:
            from data.roster_engine import RosterEngine as _RosterEngine
            from nba_api.stats.static import players as _nba_players_static

            _roster_engine = _RosterEngine()
            _roster_engine.refresh(list(playing_team_abbrevs))

            # Build name → nba_api player_id lookup (case-insensitive)
            _all_nba_players = _nba_players_static.get_players()
            _name_to_id = {p["full_name"].lower(): p["id"] for p in _all_nba_players}

            # Load player names into PlayerIDCache for fuzzy matching fallback
            if _HAS_PLAYER_ID_CACHE and _player_id_cache is not None:
                _player_id_cache.load_nba_player_names(
                    [{"full_name": p["full_name"], "id": p["id"], "team": ""} for p in _all_nba_players]
                )

            teams_fetched = 0
            for abbrev in sorted(playing_team_abbrevs):
                if progress_callback:
                    progress_callback(1 + teams_fetched, 10, f"Processing roster for {abbrev}...")

                full_names = _roster_engine.get_full_roster(abbrev)
                added = 0
                for player_name in full_names:
                    pid = _name_to_id.get(player_name.lower())
                    if not pid:
                        # Try partial first+last name match to handle suffix variants
                        parts = player_name.lower().split()
                        if len(parts) >= 2:
                            pid = next(
                                (
                                    p["id"] for p in _all_nba_players
                                    if parts[0] in p["full_name"].lower()
                                    and parts[-1] in p["full_name"].lower()
                                ),
                                None,
                            )
                    if not pid and _HAS_PLAYER_ID_CACHE and _player_id_cache is not None:
                        # Fuzzy matching via PlayerIDCache as final fallback
                        pid = _player_id_cache.get_player_id(player_name, team=abbrev)
                        if pid:
                            _logger.debug(f"  PlayerIDCache resolved {player_name} → {pid}")
                    if pid:
                        if pid in seen_pids:
                            continue  # Deduplicate: skip players already added
                        seen_pids.add(pid)
                        all_roster_players.append({
                            "player_id":   pid,
                            "player_name": player_name,
                            "team":        abbrev,
                            "position":    "SF",  # refined from bulk stats below
                        })
                        added += 1
                    else:
                        _logger.warning(f"  Could not find nba_api id for {player_name} ({abbrev}) — skipping")

                teams_fetched += 1
                _logger.info(f"  {abbrev}: {len(full_names)} players on roster ({added} matched by id)")

        except Exception as roster_error:
            _logger.warning(f"  RosterEngine error in fetch_todays_players_only: {roster_error}")

        _logger.info(f"Total players on today's rosters: {len(all_roster_players)}")

        if progress_callback:
            progress_callback(3, 10, f"Got {len(all_roster_players)} roster players. Fetching bulk season stats...")

        # --------------------------------------------------------
        # Step 3: Fetch ALL player season averages in ONE bulk API call.
        # LeagueDashPlayerStats returns stats for every player in the league,
        # so we get all the averages we need with a single request instead of
        # one PlayerGameLog call per player (380+ individual calls → 1 call).
        # --------------------------------------------------------
        bulk_stats = {}    # player_id (int) → row dict from LeagueDashPlayerStats
        team_max_gp = {}   # nba_api team abbrev → highest GP on that team
        try:
            if progress_callback:
                progress_callback(4, 10, "Fetching bulk player season averages (1 API call)...")
            stats_ep = leaguedashplayerstats.LeagueDashPlayerStats(
                per_mode_detailed="PerGame",
                season=_current_season(),
                season_type_all_star="Regular Season",
                timeout=NBA_API_BULK_TIMEOUT,
            )
            time.sleep(API_DELAY_SECONDS)
            _bulk_df = _safe_get_first_dataframe(stats_ep)
            if _bulk_df is None:
                raise RuntimeError("LeagueDashPlayerStats returned no data")
            for row in _bulk_df.to_dict("records"):
                pid = row.get("PLAYER_ID")
                if pid:
                    bulk_stats[int(pid)] = row
                    # Track per-team maximum GP for recency proxy
                    t_abbrev = row.get("TEAM_ABBREVIATION", "")
                    gp = int(row.get("GP", 0) or 0)
                    if t_abbrev and gp > team_max_gp.get(t_abbrev, 0):
                        team_max_gp[t_abbrev] = gp
            _logger.info(f"  Bulk stats: {len(bulk_stats)} players loaded")
        except Exception as bulk_err:
            _logger.warning(f"  WARNING: Bulk stats fetch failed: {bulk_err}. Falling back to ETL database.")
            try:
                from data.etl_data_service import get_all_players as _db_get_all
                db_players = _db_get_all()
                if db_players:
                    bulk_stats = {p["player_id"]: p for p in db_players}
                    _logger.info(f"  DB fallback: {len(bulk_stats)} players loaded from ETL database")
            except Exception as db_err:
                _logger.warning(f"  DB fallback also failed: {db_err}. Will use zero defaults for missing players.")

        # --------------------------------------------------------
        # Step 4: Build formatted players from bulk stats.
        # Pre-filter with injury data BEFORE any per-player work.
        # --------------------------------------------------------
        # Get injury data from the RosterEngine already populated in Step 2.
        injury_data = {}
        if _roster_engine is not None:
            injury_data = _roster_engine.get_injury_report()
            _logger.info(f"  RosterEngine supplied {len(injury_data)} injury entries")
        else:
            # RosterEngine failed — fall back to cached JSON
            try:
                if INJURY_STATUS_JSON_PATH.exists():
                    with open(INJURY_STATUS_JSON_PATH, "r", encoding="utf-8") as _jf:
                        injury_data = json.load(_jf)
            except Exception as _cache_err:
                _logger.warning(f"  WARNING: Cached injury data unavailable: {_cache_err}")

        formatted_players = []

        if progress_callback:
            progress_callback(5, 10, f"Building player stats from bulk data...")

        for player_info in all_roster_players:
            player_id   = player_info["player_id"]
            player_name = player_info["player_name"]
            team_abbrev = player_info["team"]

            # ── Pre-filter: skip injured / inactive players immediately ──
            injury_key = player_name.lower().strip()
            inj_status = injury_data.get(injury_key, {}).get("status", "Active")
            if inj_status in INACTIVE_INJURY_STATUSES:
                continue

            # ── Look up bulk stats by player_id ──────────────────────────
            row = bulk_stats.get(player_id)
            if row is None:
                # Not in bulk stats → new signing / two-way not yet tracked; skip
                continue

            # ── Recency proxy via GP gap ──────────────────────────────────
            # If a player has missed significantly more games than their teammates,
            # they are likely on a long-term absence even if not in the injury report.
            api_team  = row.get("TEAM_ABBREVIATION", team_abbrev)
            player_gp = int(row.get("GP", 0) or 0)
            t_max_gp  = team_max_gp.get(api_team, player_gp)
            games_missed = max(0, t_max_gp - player_gp)
            if games_missed > GP_ABSENT_THRESHOLD and t_max_gp > MIN_TEAM_GP_FOR_RECENCY_CHECK:
                _logger.info(f"  Skipping {player_name}: missed {games_missed}/{t_max_gp} games (likely long-term out)")
                continue

            # ── Extract season averages ───────────────────────────────────
            position    = row.get("START_POSITION", "SF") or "SF"
            mapped_pos  = _POSITION_MAP.get(position, position)
            api_team_norm = NBA_API_ABBREV_TO_OURS.get(api_team, api_team)

            points_avg    = float(row.get("PTS",    0) or 0)
            rebounds_avg  = float(row.get("REB",    0) or 0)
            assists_avg   = float(row.get("AST",    0) or 0)
            threes_avg    = float(row.get("FG3M",   0) or 0)
            steals_avg    = float(row.get("STL",    0) or 0)
            blocks_avg    = float(row.get("BLK",    0) or 0)
            turnovers_avg = float(row.get("TOV",    0) or 0)
            ft_pct        = float(row.get("FT_PCT", 0) or 0)
            minutes_avg   = float(row.get("MIN",    0) or 0)
            usage_rate    = min(35.0, max(10.0, minutes_avg * 0.8))
            # Extended stat averages (from nba_api LeagueDashPlayerStats)
            ftm_avg                = float(row.get("FTM",  0) or 0)
            fta_avg                = float(row.get("FTA",  0) or 0)
            fga_avg                = float(row.get("FGA",  0) or 0)
            fgm_avg                = float(row.get("FGM",  0) or 0)
            offensive_rebounds_avg = float(row.get("OREB", 0) or 0)
            defensive_rebounds_avg = float(row.get("DREB", 0) or 0)
            personal_fouls_avg     = float(row.get("PF",   0) or 0)

            # Skip bench / DNP players (< MIN_MINUTES_THRESHOLD)
            if minutes_avg < MIN_MINUTES_THRESHOLD:
                continue

            # ── Std devs from dynamic CV fallbacks (no per-player API call) ──
            points_std    = max(1.0, points_avg    * _dynamic_cv_for_live_fetch("points",    points_avg))
            rebounds_std  = max(0.5, rebounds_avg  * _dynamic_cv_for_live_fetch("rebounds",  rebounds_avg))
            assists_std   = max(0.5, assists_avg   * _dynamic_cv_for_live_fetch("assists",   assists_avg))
            threes_std    = max(0.3, threes_avg    * _dynamic_cv_for_live_fetch("threes",    threes_avg))
            steals_std    = max(0.1, steals_avg    * FALLBACK_STEALS_STD_RATIO)
            blocks_std    = max(0.1, blocks_avg    * FALLBACK_BLOCKS_STD_RATIO)
            turnovers_std = max(0.1, turnovers_avg * FALLBACK_TURNOVERS_STD_RATIO)
            ftm_std                = max(0.1, ftm_avg                * FALLBACK_FTM_STD_RATIO)
            fta_std                = max(0.1, fta_avg                * FALLBACK_FTA_STD_RATIO)
            # FGA/FGM use a 0.5 absolute floor (higher than other stats) because
            # field goal attempts/makes are high-volume (10-20+/game).
            fga_std                = max(0.5, fga_avg                * FALLBACK_FGA_STD_RATIO)
            fgm_std                = max(0.5, fgm_avg                * FALLBACK_FGM_STD_RATIO)
            offensive_rebounds_std = max(0.1, offensive_rebounds_avg * FALLBACK_OREB_STD_RATIO)
            defensive_rebounds_std = max(0.3, defensive_rebounds_avg * FALLBACK_DREB_STD_RATIO)
            personal_fouls_std     = max(0.1, personal_fouls_avg     * FALLBACK_PF_STD_RATIO)

            formatted_players.append({
                "player_id":    player_id if player_id else "",
                "name":         player_name,
                "team":         api_team_norm or team_abbrev,
                "position":     mapped_pos,
                "minutes_avg":  round(minutes_avg,   1),
                "points_avg":   round(points_avg,    1),
                "rebounds_avg": round(rebounds_avg,  1),
                "assists_avg":  round(assists_avg,   1),
                "threes_avg":   round(threes_avg,    1),
                "steals_avg":   round(steals_avg,    1),
                "blocks_avg":   round(blocks_avg,    1),
                "turnovers_avg":round(turnovers_avg, 1),
                "ft_pct":       round(ft_pct,        3),
                "usage_rate":   round(usage_rate,    1),
                "points_std":   round(points_std,    2),
                "rebounds_std": round(rebounds_std,  2),
                "assists_std":  round(assists_std,   2),
                "threes_std":   round(threes_std,    2),
                "steals_std":   round(steals_std,    2),
                "blocks_std":   round(blocks_std,    2),
                "turnovers_std":round(turnovers_std, 2),
                # Extended stat averages
                "ftm_avg":                  round(ftm_avg,                1),
                "fta_avg":                  round(fta_avg,                1),
                "fga_avg":                  round(fga_avg,                1),
                "fgm_avg":                  round(fgm_avg,                1),
                "offensive_rebounds_avg":   round(offensive_rebounds_avg, 1),
                "defensive_rebounds_avg":   round(defensive_rebounds_avg, 1),
                "personal_fouls_avg":       round(personal_fouls_avg,     1),
                "ftm_std":                  round(ftm_std,                2),
                "fta_std":                  round(fta_std,                2),
                "fga_std":                  round(fga_std,                2),
                "fgm_std":                  round(fgm_std,                2),
                "offensive_rebounds_std":   round(offensive_rebounds_std, 2),
                "defensive_rebounds_std":   round(defensive_rebounds_std, 2),
                "personal_fouls_std":       round(personal_fouls_std,     2),
            })

        # Sort by points average (stars appear first)
        formatted_players.sort(key=lambda p: p["points_avg"], reverse=True)

        # --------------------------------------------------------
        # Step 5: Save injury data to JSON and write players CSV.
        # All players stay in the CSV so platform props can match them.
        # The injury JSON is the single source of truth for availability.
        # --------------------------------------------------------
        if injury_data:
            try:
                with open(INJURY_STATUS_JSON_PATH, "w", encoding="utf-8") as _jf:
                    json.dump(injury_data, _jf, indent=2, default=str)
                _logger.info(f"  Saved {len(injury_data)} injury entries to {INJURY_STATUS_JSON_PATH}")
            except Exception as _save_err:
                _logger.warning(f"  WARNING: Could not save injury data: {_save_err}")

        _logger.info(f"  Writing {len(formatted_players)} players to CSV (injury data stored separately)")

        if progress_callback:
            progress_callback(9, 10, f"Saving {len(formatted_players)} players to CSV...")

        # Write to the CSV file (same format as full fetch)
        fieldnames = [
            "player_id", "name", "team", "position", "minutes_avg",
            "points_avg", "rebounds_avg", "assists_avg", "threes_avg",
            "steals_avg", "blocks_avg", "turnovers_avg", "ft_pct",
            "usage_rate", "points_std", "rebounds_std", "assists_std",
            "threes_std", "steals_std", "blocks_std", "turnovers_std",
            "ftm_avg", "fta_avg", "fga_avg", "fgm_avg",
            "offensive_rebounds_avg", "defensive_rebounds_avg",
            "personal_fouls_avg",
            "ftm_std", "fta_std", "fga_std", "fgm_std",
            "offensive_rebounds_std", "defensive_rebounds_std",
            "personal_fouls_std",
        ]

        with open(PLAYERS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(formatted_players)

        save_last_updated("players")

        if progress_callback:
            progress_callback(10, 10, f"✅ Saved {len(formatted_players)} players (today's teams only)!")

        _logger.info(f"Saved {len(formatted_players)} players for today's games to {PLAYERS_CSV_PATH}")
        _invalidate_data_caches()  # Feature 9: bust stale Streamlit caches
        return True

    except Exception as error:
        _logger.error(f"Error in fetch_todays_players_only: {error}")
        return False

# ============================================================
# END SECTION: Targeted Roster-Based Data Fetcher
# ============================================================


# ============================================================
# SECTION: Recent Form Fetcher
# Fetch the last N games for a player and compute trend/averages.
# ============================================================

def fetch_player_recent_form(player_id, last_n_games=10):
    """
    Fetch recent form data for a specific player via nba_api.

    Returns the last N game logs along with:
    - Recent averages (last N games)
    - Trend indicator: 'hot' if last 3 games avg > season avg, else 'cold'
    - Game-by-game breakdown for sparkline display

    Args:
        player_id (int or str): The NBA player's unique ID
        last_n_games (int): Number of recent games to analyze (default: 10)

    Returns:
        dict: Recent form data with keys:
              'games' (list), 'recent_pts_avg', 'recent_reb_avg',
              'recent_ast_avg', 'trend', 'game_results'
              Returns empty dict if fetch fails.
    """
    # ── nba_api ──────────────────────────────────────────────
    try:
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        return {}

    try:
        game_log_endpoint = playergamelog.PlayerGameLog(
            player_id=player_id,
            season_type_all_star="Regular Season",
            timeout=NBA_API_GAMELOG_TIMEOUT,
        )
        _gl_df = _safe_get_first_dataframe(game_log_endpoint)
        if _gl_df is None:
            return {}
        game_log_data = _gl_df.to_dict("records")
        time.sleep(API_DELAY_SECONDS)

        recent = game_log_data[:last_n_games]

        if not recent:
            return {}

        def safe_avg(values):
            """Average a list of numeric values, ignoring None/NaN entries."""
            clean = [v for v in values if v is not None and isinstance(v, (int, float)) and math.isfinite(v)]
            return round(sum(clean) / len(clean), 1) if clean else 0.0

        pts_list = [float(g.get("PTS", 0) or 0) for g in recent]
        reb_list = [float(g.get("REB", 0) or 0) for g in recent]
        ast_list = [float(g.get("AST", 0) or 0) for g in recent]
        fg3m_list = [float(g.get("FG3M", 0) or 0) for g in recent]

        # Trend: compare last 5 games vs prior 5 games
        last_5_pts_vals = pts_list[:5]
        prior_5_pts_vals = pts_list[5:10]
        last5_avg = safe_avg(last_5_pts_vals)
        prev5_avg = safe_avg(prior_5_pts_vals) if prior_5_pts_vals else last5_avg

        if prev5_avg > 0:
            trend = "hot" if last5_avg >= prev5_avg * HOT_TREND_THRESHOLD else (
                "cold" if last5_avg <= prev5_avg * COLD_TREND_THRESHOLD else "neutral"
            )
        else:
            trend = "neutral"

        trend_emoji_map = {"hot": "🔥", "cold": "❄️", "neutral": "➡️"}
        trend_emoji = trend_emoji_map.get(trend, "➡️")

        # Build game-by-game results list (newest first)
        game_results = []
        for g in recent:
            game_results.append({
                "date": g.get("GAME_DATE", ""),
                "matchup": g.get("MATCHUP", ""),
                "wl": g.get("WL", ""),
                "pts": float(g.get("PTS", 0) or 0),
                "reb": float(g.get("REB", 0) or 0),
                "ast": float(g.get("AST", 0) or 0),
                "fg3m": float(g.get("FG3M", 0) or 0),
                "min": float(g.get("MIN", 0) or 0),
            })

        return {
            "games": recent,
            "recent_pts_avg": safe_avg(pts_list),
            "recent_reb_avg": safe_avg(reb_list),
            "recent_ast_avg": safe_avg(ast_list),
            "recent_fg3m_avg": safe_avg(fg3m_list),
            "trend": trend,
            "trend_emoji": trend_emoji,
            "last_5_pts": last_5_pts_vals,
            "last_5_pts_avg": last5_avg,
            "game_results": game_results,
            "games_played": len(recent),
        }

    except Exception as error:
        _logger.error(f"Error fetching recent form for player {player_id}: {error}")
        return {}

# ============================================================
# END SECTION: Recent Form Fetcher
# ============================================================


# ============================================================
# SECTION: Player Stats Fetcher
# Fetches current season averages for all NBA players.
# ============================================================

def fetch_player_stats(progress_callback=None):
    """
    Fetch current season player stats for all NBA players.

    Uses LeagueDashPlayerStats to get PPG, RPG, APG, etc. for
    every player who has played this season. Then fetches game logs
    to calculate standard deviations (how consistent each player is).

    BEGINNER NOTE: LeagueDashPlayerStats is the same data you see on
    basketball-reference.com or ESPN — season averages per game.

    Args:
        progress_callback (callable, optional): A function to call with
            progress updates. Called with (current, total, message).
            Used by the Streamlit page to update the progress bar.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    # Import inside the function for graceful failure if not installed
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players as nba_players_static
    except ImportError:
        _logger.error("ERROR: nba_api is not installed. Run: pip install nba_api")
        return False

    try:
        # --------------------------------------------------------
        # Step 1: Fetch season averages for all players
        # --------------------------------------------------------

        # Call the LeagueDashPlayerStats endpoint
        # BEGINNER NOTE: PerGame means we get per-game averages (not totals)
        # season_type_all_star is the parameter name in nba_api that controls
        # the season type. Despite the parameter name containing "all_star",
        # it accepts values like "Regular Season", "Playoffs", "Pre Season", etc.
        _logger.info("Fetching player season averages from NBA API...")

        # Signal progress to the UI if a callback was provided
        if progress_callback:
            progress_callback(1, 10, "Connecting to NBA API for player stats...")

        # Make the API call — this fetches ALL players' stats at once
        stats_endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
            per_mode_detailed="PerGame",      # We want per-game averages
            season=_current_season(),
            season_type_all_star="Regular Season",  # Only regular season
            timeout=NBA_API_BULK_TIMEOUT,
        )

        # Wait a moment before the next call
        time.sleep(API_DELAY_SECONDS)

        # Get the data as a list of dictionaries
        # BEGINNER NOTE: nba_api returns a DataFrame object.
        # .get_data_frames() converts it to a list of DataFrames.
        # [0] gets the first (and only) DataFrame.
        # .to_dict('records') converts rows to a list of dicts.
        _stats_df = _safe_get_first_dataframe(stats_endpoint)
        if _stats_df is None:
            _logger.error("LeagueDashPlayerStats returned no data")
            return False
        player_stats_list = _stats_df.to_dict("records")

        if progress_callback:
            progress_callback(2, 10, f"Got stats for {len(player_stats_list)} players. Calculating standard deviations...")

        _logger.info(f"Got stats for {len(player_stats_list)} players.")

        # --------------------------------------------------------
        # Step 2: Map nba_api column names to our column names
        # --------------------------------------------------------

        # BEGINNER NOTE: nba_api uses column names like "PTS" (points),
        # but our app uses "points_avg". We need to map between them.
        # This list will hold our formatted player rows.
        formatted_players = []

        # Process each player — fetch game logs for std dev calculation
        total_players = len(player_stats_list)

        for player_index, player_row in enumerate(player_stats_list):
            # Show progress every 10 players
            if player_index % 10 == 0 and progress_callback:
                progress_message = f"Processing player {player_index + 1} of {total_players}..."
                progress_callback(2 + int(7 * player_index / total_players), 10, progress_message)

            # Extract the player's season averages from the nba_api format
            # BEGINNER NOTE: .get(key, default) returns the value for 'key',
            # or 'default' if the key doesn't exist.
            player_name = player_row.get("PLAYER_NAME", "")          # Full name
            team_abbrev = player_row.get("TEAM_ABBREVIATION", "")    # 3-letter team code
            position = player_row.get("START_POSITION", "G")          # Starting position

            # Skip players with no name or team
            if not player_name or not team_abbrev:
                continue

            # Map position codes (nba_api sometimes uses just "G", "F", "C")
            # Our app uses PG, SG, SF, PF, C — we default to a generic position
            position_map = {
                "G": "PG",   # Guard → Point Guard (best guess)
                "F": "SF",   # Forward → Small Forward (best guess)
                "C": "C",    # Center stays Center
                "G-F": "SF", # Guard-Forward hybrid
                "F-G": "SG", # Forward-Guard hybrid
                "F-C": "PF", # Forward-Center hybrid
                "C-F": "PF", # Center-Forward hybrid
                "": "SF",    # Unknown → Small Forward (safe default)
            }
            mapped_position = position_map.get(position, position)  # Map or keep original

            # Normalize team abbreviation to match our format
            team_abbrev = NBA_API_ABBREV_TO_OURS.get(team_abbrev, team_abbrev)

            # Get season averages (these come as numbers from nba_api)
            points_avg = float(player_row.get("PTS", 0) or 0)        # Points per game
            rebounds_avg = float(player_row.get("REB", 0) or 0)      # Rebounds per game
            assists_avg = float(player_row.get("AST", 0) or 0)       # Assists per game
            threes_avg = float(player_row.get("FG3M", 0) or 0)       # 3-pointers made per game
            steals_avg = float(player_row.get("STL", 0) or 0)        # Steals per game
            blocks_avg = float(player_row.get("BLK", 0) or 0)        # Blocks per game
            turnovers_avg = float(player_row.get("TOV", 0) or 0)     # Turnovers per game
            ft_pct = float(player_row.get("FT_PCT", 0) or 0)         # Free throw percentage (0-1)
            minutes_avg = float(player_row.get("MIN", 0) or 0)       # Minutes per game

            # Usage rate is not directly in LeagueDashPlayerStats basic call
            # We estimate it from minutes played as a rough proxy:
            # NBA average usage rate ≈ 20% (equal sharing across 5 players).
            # Stars who play 35+ min tend to have usage ≈ 28-35%.
            # The 0.8 multiplier maps minutes (10-38 range) to a plausible
            # usage range (8-30%) that correlates with observed NBA data.
            # This estimate is only used if live usage data isn't available.
            usage_rate = min(35.0, max(10.0, minutes_avg * 0.8))  # Rough estimate

            # --------------------------------------------------------
            # Step 3: Calculate standard deviations from game logs
            # --------------------------------------------------------
            # BEGINNER NOTE: Standard deviation measures how consistent
            # a player is. A player who always scores exactly 20 has
            # std dev of 0. A player who scores anywhere from 5-35
            # has a high std dev. Higher std dev = harder to predict.

            # Fetch the player's game log to calculate std dev
            player_id = player_row.get("PLAYER_ID")  # Unique NBA player ID

            # Default std devs if we can't fetch the game log.
            # W10: Use dynamic tier-based CV instead of fixed ratios.
            # Stars (high avg) are more consistent; role players are more volatile.
            points_std = max(1.0, points_avg * _dynamic_cv_for_live_fetch("points", points_avg))
            rebounds_std = max(0.5, rebounds_avg * _dynamic_cv_for_live_fetch("rebounds", rebounds_avg))
            assists_std = max(0.5, assists_avg * _dynamic_cv_for_live_fetch("assists", assists_avg))
            threes_std = max(0.3, threes_avg * _dynamic_cv_for_live_fetch("threes", threes_avg))

            # Initialize steals/blocks/turnovers std devs with CV-based defaults.
            # These will be overwritten with game-log-calculated values if available.
            steals_std_from_log = None    # Will hold game-log std dev if fetched
            blocks_std_from_log = None    # Will hold game-log std dev if fetched
            turnovers_std_from_log = None  # Will hold game-log std dev if fetched

            # Only fetch game log if the player has played meaningful minutes
            # This avoids wasting API calls on end-of-bench players
            if player_id and minutes_avg >= 10.0:
                try:
                    # Check cache first to avoid redundant API calls
                    _cached_logs = None
                    if _GAME_LOG_CACHE_AVAILABLE:
                        _cached_logs, _is_stale = load_game_logs_from_cache(player_name)
                        if _cached_logs and not _is_stale:
                            game_log_data = _cached_logs
                            recent_games = game_log_data[:20]
                        else:
                            _cached_logs = None  # Force fresh fetch

                    if _cached_logs is None:
                        # Fetch the last 20 games for this player
                        # BEGINNER NOTE: The game log shows stats game-by-game,
                        # e.g., "March 1: 22 pts, March 3: 18 pts, March 5: 30 pts"
                        if _RATE_LIMITER_AVAILABLE and _rate_limiter:
                            _rate_limiter.acquire()
                        game_log_endpoint = playergamelog.PlayerGameLog(
                            player_id=player_id,        # Which player
                            season_type_all_star="Regular Season",  # Only regular season
                            timeout=NBA_API_GAMELOG_TIMEOUT,
                        )

                        # Get the game log data
                        _gl_df = _safe_get_first_dataframe(game_log_endpoint)
                        game_log_data = _gl_df.to_dict("records") if _gl_df is not None else []
                        if _RATE_LIMITER_AVAILABLE and _rate_limiter:
                            _rate_limiter.record_request()

                        # Cache the result for future calls (JSON + SQLite write-through)
                        if _GAME_LOG_CACHE_AVAILABLE and game_log_data:
                            save_game_logs_to_cache(player_name, game_log_data)
                        # Feature 12: also persist to SQLite DB for cross-session durability
                        if _DB_GAME_LOG_AVAILABLE and game_log_data:
                            try:
                                save_player_game_logs_to_db(
                                    player_id=player_id,
                                    player_name=player_name,
                                    game_logs=game_log_data,
                                )
                            except Exception:
                                _logger.debug("SQLite game log persist failed (non-fatal)")

                        # Take only the last 20 games for recency
                        recent_games = game_log_data[:20]

                    # Calculate std dev if we have at least 5 games
                    if len(recent_games) >= 5:
                        # Extract lists of each stat across all games
                        pts_list = [float(g.get("PTS", 0) or 0) for g in recent_games]
                        reb_list = [float(g.get("REB", 0) or 0) for g in recent_games]
                        ast_list = [float(g.get("AST", 0) or 0) for g in recent_games]
                        fg3m_list = [float(g.get("FG3M", 0) or 0) for g in recent_games]
                        stl_list = [float(g.get("STL", 0) or 0) for g in recent_games]
                        blk_list = [float(g.get("BLK", 0) or 0) for g in recent_games]
                        tov_list = [float(g.get("TOV", 0) or 0) for g in recent_games]

                        # statistics.stdev calculates standard deviation
                        # BEGINNER NOTE: We need at least 2 values for stdev
                        if len(pts_list) >= 2:
                            points_std = round(statistics.stdev(pts_list), 2)
                        if len(reb_list) >= 2:
                            rebounds_std = round(statistics.stdev(reb_list), 2)
                        if len(ast_list) >= 2:
                            assists_std = round(statistics.stdev(ast_list), 2)
                        if len(fg3m_list) >= 2:
                            threes_std = round(statistics.stdev(fg3m_list), 2)
                        # Calculate steals/blocks/turnovers std from game logs
                        # This replaces the CV-based defaults for better accuracy
                        steals_std_from_log = round(statistics.stdev(stl_list), 2) if len(stl_list) >= 2 else None
                        blocks_std_from_log = round(statistics.stdev(blk_list), 2) if len(blk_list) >= 2 else None
                        turnovers_std_from_log = round(statistics.stdev(tov_list), 2) if len(tov_list) >= 2 else None
                    else:
                        steals_std_from_log = None
                        blocks_std_from_log = None
                        turnovers_std_from_log = None

                    # IMPORTANT: Always sleep between API calls to avoid rate limiting
                    time.sleep(API_DELAY_SECONDS)

                except Exception as game_log_error:
                    # If game log fetch fails, use the default std devs calculated above
                    # This is not fatal — we just use less accurate std devs
                    _logger.warning(f"  Could not fetch game log for {player_name}: {game_log_error}")

            # --------------------------------------------------------
            # Step 4: Build the formatted player dictionary
            # --------------------------------------------------------

            # Build the row in our CSV format
            # BEGINNER NOTE: All values are rounded to 2 decimal places
            # for clean CSV output
            formatted_player = {
                "player_id": player_id if player_id else "",  # NBA unique player ID
                "name": player_name,                          # Player full name
                "team": team_abbrev,                          # 3-letter team code
                "position": mapped_position,                  # PG/SG/SF/PF/C
                "minutes_avg": round(minutes_avg, 1),         # Minutes per game
                "points_avg": round(points_avg, 1),           # Points per game
                "rebounds_avg": round(rebounds_avg, 1),       # Rebounds per game
                "assists_avg": round(assists_avg, 1),         # Assists per game
                "threes_avg": round(threes_avg, 1),           # 3PM per game
                "steals_avg": round(steals_avg, 1),           # Steals per game
                "blocks_avg": round(blocks_avg, 1),           # Blocks per game
                "turnovers_avg": round(turnovers_avg, 1),     # Turnovers per game
                "ft_pct": round(ft_pct, 3),                   # Free throw % (0-1)
                "usage_rate": round(usage_rate, 1),           # Usage rate %
                "points_std": round(points_std, 2),           # Points std dev
                "rebounds_std": round(rebounds_std, 2),       # Rebounds std dev
                "assists_std": round(assists_std, 2),         # Assists std dev
                "threes_std": round(threes_std, 2),           # 3PM std dev
                # Use game-log std devs when available; fall back to ratio-based estimates
                "steals_std": round(steals_std_from_log if steals_std_from_log is not None else max(0.1, steals_avg * FALLBACK_STEALS_STD_RATIO), 2),
                "blocks_std": round(blocks_std_from_log if blocks_std_from_log is not None else max(0.1, blocks_avg * FALLBACK_BLOCKS_STD_RATIO), 2),
                "turnovers_std": round(turnovers_std_from_log if turnovers_std_from_log is not None else max(0.1, turnovers_avg * FALLBACK_TURNOVERS_STD_RATIO), 2),
            }

            # Skip players who aren't getting meaningful minutes.
            # They won't have props and pollute the database with noise.
            if minutes_avg < MIN_MINUTES_THRESHOLD:
                continue

            formatted_players.append(formatted_player)

        # --------------------------------------------------------
        # Step 5: Sort by points average (stars appear first)
        # --------------------------------------------------------

        # Sort players so the best scorers appear at the top
        formatted_players.sort(key=lambda p: p["points_avg"], reverse=True)

        # --------------------------------------------------------
        # Step 5b: Filter out injured / inactive players
        # Cross-reference with nba_api injury data (via RosterEngine)
        # to remove players confirmed as Out or on IR
        # before writing to CSV.
        # --------------------------------------------------------
        try:
            from data.roster_engine import RosterEngine as _RE
            _inj_engine = _RE()
            _inj_engine.refresh()
            scraped_injuries = _inj_engine.get_injury_report()
            if scraped_injuries:
                before_count = len(formatted_players)
                formatted_players = [
                    p for p in formatted_players
                    if scraped_injuries.get(
                        p["name"].lower().strip(), {}
                    ).get("status", "Active") not in INACTIVE_INJURY_STATUSES
                ]
                removed_count = before_count - len(formatted_players)
                if removed_count:
                    _logger.info(
                        f"  Injury filter: removed {removed_count} Out/IR players "
                        f"from player stats ({len(formatted_players)} remain)"
                    )
        except Exception as _inj_err:
            # RosterEngine injury fetch failed — fall back to the cached injury_status.json
            # written by a previous fetch_todays_players_only() run.
            _logger.info(f"  Injury fetch (RosterEngine) failed in fetch_player_stats: {_inj_err}")
            try:
                cached_injuries = {}
                if INJURY_STATUS_JSON_PATH.exists():
                    with open(INJURY_STATUS_JSON_PATH, "r", encoding="utf-8") as _jf:
                        cached_injuries = json.load(_jf)
                if cached_injuries:
                    before_count = len(formatted_players)
                    formatted_players = [
                        p for p in formatted_players
                        if cached_injuries.get(
                            p["name"].lower().strip(), {}
                        ).get("status", "Active") not in INACTIVE_INJURY_STATUSES
                    ]
                    removed_count = before_count - len(formatted_players)
                    _logger.info(
                        f"  Injury fallback (cached JSON): removed {removed_count} "
                        f"players ({len(formatted_players)} remain)"
                    )
                else:
                    _logger.info(
                        "  WARNING: RosterEngine failed and no cached injury data "
                        "available — no injury filter applied"
                    )
            except Exception as _cache_err:
                _logger.warning(f"  WARNING: All injury filter methods failed: {_cache_err}")

        if progress_callback:
            progress_callback(9, 10, f"Saving {len(formatted_players)} players to CSV...")

        # --------------------------------------------------------
        # Step 6: Write the CSV file
        # --------------------------------------------------------

        # Define the column order (must match players.csv exactly)
        fieldnames = [
            "player_id", "name", "team", "position", "minutes_avg",
            "points_avg", "rebounds_avg", "assists_avg", "threes_avg",
            "steals_avg", "blocks_avg", "turnovers_avg", "ft_pct",
            "usage_rate", "points_std", "rebounds_std", "assists_std",
            "threes_std", "steals_std", "blocks_std", "turnovers_std",
        ]

        # Write to the CSV file (overwrites any existing data)
        # BEGINNER NOTE: 'w' means write mode (overwrites existing file)
        # newline='' is required by Python's csv module on Windows
        with open(PLAYERS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()      # Write the column names row
            writer.writerows(formatted_players)  # Write all player rows

        # Save timestamp so we know when this was last updated
        save_last_updated("players")

        if progress_callback:
            progress_callback(10, 10, f"✅ Saved {len(formatted_players)} players!")

        _logger.info(f"Successfully saved {len(formatted_players)} players to {PLAYERS_CSV_PATH}")
        _invalidate_data_caches()  # Feature 9: bust stale Streamlit caches
        return True  # Signal success

    except Exception as error:
        # Catch-all error handler — show what went wrong
        _logger.error(f"Error fetching player stats: {error}")
        return False  # Signal failure

# ============================================================
# END SECTION: Player Stats Fetcher
# ============================================================


# ============================================================
# SECTION: Team Stats Fetcher
# Fetches current season team stats (pace, ratings, etc.)
# ============================================================

def fetch_team_stats(progress_callback=None):
    """
    Fetch current season team stats using LeagueDashTeamStats.

    Pulls pace, offensive rating (ORTG), and defensive rating (DRTG)
    for all 30 NBA teams. Also builds basic defensive ratings by position.

    BEGINNER NOTE: Pace is how many possessions a team uses per 48 minutes.
    A high pace team (like the Warriors) plays fast, meaning more shots and
    more counting stats. ORTG = points scored per 100 possessions. DRTG =
    points allowed per 100 possessions. Lower DRTG = better defense.

    Args:
        progress_callback (callable, optional): Progress update function.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    # Import inside the function for graceful failure
    try:
        from nba_api.stats.endpoints import leaguedashteamstats
    except ImportError:
        _logger.error("ERROR: nba_api is not installed. Run: pip install nba_api")
        return False

    try:
        if progress_callback:
            progress_callback(1, 6, "Fetching team stats from NBA API...")

        # --------------------------------------------------------
        # Step 1: Fetch team stats (pace, ortg, drtg)
        # --------------------------------------------------------

        # LeagueDashTeamStats with PerPossession gives us ratings
        # BEGINNER NOTE: Per possession stats (like ORTG/DRTG) normalize
        # for pace — they tell you how efficient a team is regardless of
        # whether they play fast or slow.
        team_stats_endpoint = leaguedashteamstats.LeagueDashTeamStats(
            per_mode_detailed="PerGame",          # Get per-game stats
            season=_current_season(),
            season_type_all_star="Regular Season",
            timeout=NBA_API_BULK_TIMEOUT,
        )

        # Get the data
        _ts_df = _safe_get_first_dataframe(team_stats_endpoint)
        if _ts_df is None:
            _logger.error("LeagueDashTeamStats returned no data")
            return False
        team_stats_list = _ts_df.to_dict("records")

        time.sleep(API_DELAY_SECONDS)  # Be polite — wait between calls

        if progress_callback:
            progress_callback(2, 6, "Fetching team advanced stats (pace, ratings)...")

        # Also fetch advanced stats for pace and ratings
        # BEGINNER NOTE: "Advanced" stats include efficiency metrics
        # that regular box scores don't show
        from nba_api.stats.endpoints import leaguedashteamstats as advanced_stats_module

        # Fetch advanced (per-possession) stats for ORTG/DRTG/Pace
        advanced_endpoint = advanced_stats_module.LeagueDashTeamStats(
            per_mode_detailed="Per100Possessions",    # Per 100 possessions = normalized
            measure_type_detailed_defense="Advanced",  # Advanced stats mode
            season=_current_season(),
            season_type_all_star="Regular Season",
            timeout=NBA_API_BULK_TIMEOUT,
        )

        _adv_df = _safe_get_first_dataframe(advanced_endpoint)
        if _adv_df is None:
            _logger.warning("LeagueDashTeamStats (advanced) returned no data; continuing without advanced stats")
            advanced_list = []
        else:
            advanced_list = _adv_df.to_dict("records")

        time.sleep(API_DELAY_SECONDS)

        # Build a lookup dict: team_id → advanced stats
        # BEGINNER NOTE: A dictionary lets us quickly look up a team's
        # advanced stats by their team ID
        advanced_by_team_id = {}
        for row in advanced_list:
            team_id = row.get("TEAM_ID")           # Unique team ID number
            if team_id:
                advanced_by_team_id[team_id] = row  # Store advanced stats

        if progress_callback:
            progress_callback(3, 6, "Building team CSV rows...")

        # --------------------------------------------------------
        # Step 2: Build formatted team rows
        # --------------------------------------------------------

        formatted_teams = []

        for team_row in team_stats_list:
            # Get the team name and ID
            team_name = team_row.get("TEAM_NAME", "")   # Full name e.g. "Los Angeles Lakers"
            team_id = team_row.get("TEAM_ID")            # Numeric ID

            # Skip teams with no name
            if not team_name:
                continue

            # Look up abbreviation from our mapping
            team_abbrev = TEAM_NAME_TO_ABBREVIATION.get(team_name, "")
            if not team_abbrev:
                # Try to get abbreviation from the raw data
                team_abbrev = team_row.get("TEAM_ABBREVIATION", "")
                team_abbrev = NBA_API_ABBREV_TO_OURS.get(team_abbrev, team_abbrev)

            # Skip if we still don't have an abbreviation
            if not team_abbrev:
                continue

            # Get conference for this team
            conference = TEAM_CONFERENCE.get(team_abbrev, "West")  # Default to West

            # Get advanced stats for this team (if available)
            advanced_row = advanced_by_team_id.get(team_id, {})

            # Extract pace — PACE is in the advanced stats
            # If not available, use a reasonable NBA average (98-103)
            pace = float(advanced_row.get("PACE", 0) or 0)
            if pace == 0:
                pace = 100.0  # League average default

            # Extract ORTG (offensive rating) from advanced stats
            ortg = float(advanced_row.get("OFF_RATING", 0) or 0)
            if ortg == 0:
                # Fall back to calculating from basic stats
                # Points per game × 100 / pace ≈ rough ORTG estimate
                pts = float(team_row.get("PTS", 110) or 110)
                ortg = round(pts, 1)  # Use raw points as rough proxy

            # Extract DRTG (defensive rating) from advanced stats
            drtg = float(advanced_row.get("DEF_RATING", 0) or 0)
            if drtg == 0:
                drtg = 113.0  # League average default

            # Build the team row in our CSV format
            formatted_team = {
                "team_name": team_name,             # Full name
                "abbreviation": team_abbrev,         # 3-letter code
                "conference": conference,             # East or West
                "division": "",                       # We don't use division in the engine
                "pace": round(pace, 1),              # Possessions per 48 minutes
                "ortg": round(ortg, 1),              # Offensive rating
                "drtg": round(drtg, 1),              # Defensive rating
            }

            formatted_teams.append(formatted_team)

        # Sort by team name alphabetically
        formatted_teams.sort(key=lambda t: t["team_name"])

        if progress_callback:
            progress_callback(4, 6, f"Saving {len(formatted_teams)} teams to CSV...")

        # --------------------------------------------------------
        # Step 3: Write the teams CSV
        # --------------------------------------------------------

        # Column order must match existing teams.csv exactly
        team_fieldnames = [
            "team_name", "abbreviation", "conference", "division",
            "pace", "ortg", "drtg",
        ]

        with open(TEAMS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=team_fieldnames)
            writer.writeheader()
            writer.writerows(formatted_teams)

        # Save timestamp
        save_last_updated("teams")

        if progress_callback:
            progress_callback(5, 6, "Building defensive ratings by position...")

        # --------------------------------------------------------
        # Step 4: Build defensive_ratings.csv
        # --------------------------------------------------------
        # BEGINNER NOTE: The defensive_ratings.csv tracks how good or bad
        # each team is at defending each position (PG, SG, SF, PF, C).
        # A value > 1.0 means the team allows MORE than average to that position
        # (bad defense). A value < 1.0 means they allow LESS (good defense).
        #
        # The nba_api doesn't directly give us position-by-position defensive
        # ratings. So we calculate them from overall defensive rating:
        # - Teams with good overall defense (low drtg) get values below 1.0
        # - Teams with bad defense (high drtg) get values above 1.0
        # - The adjustment varies slightly by position for realism

        defensive_rows = []

        # League average defensive rating (used for normalization)
        # BEGINNER NOTE: We calculate the average drtg across all teams
        all_drtg_values = [t["drtg"] for t in formatted_teams if t["drtg"] > 0]
        avg_drtg = sum(all_drtg_values) / len(all_drtg_values) if all_drtg_values else 113.0

        for team in formatted_teams:
            team_drtg = team["drtg"]              # This team's defensive rating
            team_abbrev = team["abbreviation"]     # 3-letter team code
            team_name_full = team["team_name"]     # Full team name

            # Calculate how much above/below average this team's defense is
            # A team with drtg = avg_drtg gets a ratio of exactly 1.0
            # A team with higher drtg (worse defense) gets ratio > 1.0
            # A team with lower drtg (better defense) gets ratio < 1.0
            if avg_drtg > 0:
                defense_ratio = team_drtg / avg_drtg  # Normalized defense rating
            else:
                defense_ratio = 1.0  # Default if no data

            # Apply small positional adjustments for realism
            # (Better defenses tend to suppress guards more than centers,
            # since most offensive schemes feature guard play)
            pg_factor = round(defense_ratio * 1.01, 3)   # PG: slightly above ratio
            sg_factor = round(defense_ratio * 1.00, 3)   # SG: same as ratio
            sf_factor = round(defense_ratio * 0.99, 3)   # SF: slightly below
            pf_factor = round(defense_ratio * 0.98, 3)   # PF: below
            c_factor = round(defense_ratio * 0.97, 3)    # C: most below (bigs harder to guard)

            # Build the defensive ratings row
            defensive_row = {
                "team_name": team_name_full,    # Full team name
                "abbreviation": team_abbrev,     # 3-letter code
                "vs_PG_pts": pg_factor,          # Multiplier vs PG (pts)
                "vs_SG_pts": sg_factor,          # Multiplier vs SG (pts)
                "vs_SF_pts": sf_factor,          # Multiplier vs SF (pts)
                "vs_PF_pts": pf_factor,          # Multiplier vs PF (pts)
                "vs_C_pts": c_factor,            # Multiplier vs C (pts)
                "vs_PG_reb": round(defense_ratio * 0.99, 3),   # Rebound factors
                "vs_SG_reb": round(defense_ratio * 0.98, 3),
                "vs_SF_reb": round(defense_ratio * 0.97, 3),
                "vs_PF_reb": round(defense_ratio * 1.01, 3),
                "vs_C_reb": round(defense_ratio * 1.02, 3),
                "vs_PG_ast": round(defense_ratio * 1.02, 3),   # Assist factors
                "vs_SG_ast": round(defense_ratio * 1.00, 3),
                "vs_SF_ast": round(defense_ratio * 0.99, 3),
                "vs_PF_ast": round(defense_ratio * 0.97, 3),
                "vs_C_ast": round(defense_ratio * 0.96, 3),
            }

            defensive_rows.append(defensive_row)

        # Write the defensive ratings CSV
        defensive_fieldnames = [
            "team_name", "abbreviation",
            "vs_PG_pts", "vs_SG_pts", "vs_SF_pts", "vs_PF_pts", "vs_C_pts",
            "vs_PG_reb", "vs_SG_reb", "vs_SF_reb", "vs_PF_reb", "vs_C_reb",
            "vs_PG_ast", "vs_SG_ast", "vs_SF_ast", "vs_PF_ast", "vs_C_ast",
        ]

        with open(DEFENSIVE_RATINGS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=defensive_fieldnames)
            writer.writeheader()
            writer.writerows(defensive_rows)

        # Save timestamps
        save_last_updated("teams")

        if progress_callback:
            progress_callback(6, 6, f"✅ Saved {len(formatted_teams)} teams and defensive ratings!")

        _logger.info(f"Successfully saved {len(formatted_teams)} teams and defensive ratings.")
        _invalidate_data_caches()  # Feature 9: bust stale Streamlit caches
        return True  # Signal success

    except Exception as error:
        _logger.error(f"Error fetching team stats: {error}")
        return False  # Signal failure

# ============================================================
# END SECTION: Team Stats Fetcher
# ============================================================


# ============================================================
# SECTION: Defensive Ratings Auto-Update (Feature 11)
# A standalone wrapper so callers can refresh just defensive
# ratings without re-fetching all team stats from scratch.
# BEGINNER NOTE: defensive_ratings.csv is built as a byproduct
# of fetch_team_stats(). This function checks staleness first
# and only re-fetches when the file is more than 7 days old.
# ============================================================

def fetch_defensive_ratings(force=False, progress_callback=None):
    """
    Refresh defensive_ratings.csv from the NBA API.

    Checks whether the existing file is stale (> 7 days old).
    If stale (or force=True), runs fetch_team_stats() which rebuilds
    both teams.csv and defensive_ratings.csv in one pass.

    Args:
        force (bool): If True, always refresh even if data is fresh.
            Defaults to False (only refresh if stale).
        progress_callback: Optional function(step, total, msg) for UI.

    Returns:
        dict: {
            'refreshed': bool — True if a fetch was performed,
            'reason': str   — why refreshed/skipped,
            'teams_path': str,
            'defensive_path': str,
        }
    """
    _STALE_DAYS = 7  # Refresh if data is older than this many days

    timestamps = load_last_updated()
    teams_ts_str = timestamps.get("teams")

    if not force and teams_ts_str:
        try:
            import datetime as _dt
            teams_ts = _dt.datetime.fromisoformat(str(teams_ts_str))
            _now_utc = _dt.datetime.now(_dt.timezone.utc)
            if teams_ts.tzinfo is None:
                teams_ts = teams_ts.replace(tzinfo=_dt.timezone.utc)
            age_days = (_now_utc - teams_ts).total_seconds() / 86400.0
            if age_days < _STALE_DAYS:
                _logger.info(
                    f"[DefensiveRatings] Data is fresh ({age_days:.1f}d old, "
                    f"threshold {_STALE_DAYS}d). Skipping fetch."
                )
                return {
                    "refreshed": False,
                    "reason": f"Data is fresh ({age_days:.1f} days old)",
                    "teams_path": str(TEAMS_CSV_PATH),
                    "defensive_path": str(DEFENSIVE_RATINGS_CSV_PATH),
                }
        except Exception:
            pass  # If timestamp parse fails, refresh anyway

    _logger.info("[DefensiveRatings] Data stale or force-refresh. Running fetch_team_stats()...")
    ok = fetch_team_stats(progress_callback=progress_callback)

    return {
        "refreshed": ok,
        "reason": "Fetched from NBA API" if ok else "Fetch failed — see logs",
        "teams_path": str(TEAMS_CSV_PATH),
        "defensive_path": str(DEFENSIVE_RATINGS_CSV_PATH),
    }


def get_teams_staleness_warning():
    """
    Return a warning string if teams.csv/defensive_ratings.csv are stale.

    Used by app.py and the Analysis page to show a prominent banner
    when the team data is old.

    Returns:
        str or None: Warning message, or None if data is fresh enough.
    """
    _WARN_DAYS  = 7   # Yellow warning after 7 days
    _STALE_DAYS = 14  # Red warning after 14 days

    timestamps = load_last_updated()
    teams_ts_str = timestamps.get("teams")

    if not teams_ts_str:
        return "⚠️ teams.csv has never been updated — run Smart NBA Data → Fetch Team Stats."

    try:
        import datetime as _dt
        teams_ts = _dt.datetime.fromisoformat(str(teams_ts_str))
        _now_utc = _dt.datetime.now(_dt.timezone.utc)
        if teams_ts.tzinfo is None:
            teams_ts = teams_ts.replace(tzinfo=_dt.timezone.utc)
        age_days = (_now_utc - teams_ts).total_seconds() / 86400.0
        if age_days >= _STALE_DAYS:
            return (
                f"🔴 Team data is **{age_days:.0f} days old** — seriously stale! "
                "Go to 📡 Smart NBA Data → Fetch Team Stats to refresh defensive ratings."
            )
        if age_days >= _WARN_DAYS:
            return (
                f"🟡 Team data is **{age_days:.0f} days old**. "
                "Consider refreshing via 📡 Smart NBA Data → Fetch Team Stats."
            )
    except Exception:
        return "⚠️ Could not determine team data age — check last_updated.json."

    return None  # Fresh enough — no warning


# ============================================================
# END SECTION: Defensive Ratings Auto-Update
# ============================================================


# ============================================================
# SECTION: Player Game Log Fetcher
# Fetches the last N games for a specific player.
# ============================================================

def fetch_player_game_log(player_id, last_n_games=20):
    """
    Fetch the last N game logs for a specific player via nba_api.

    This is useful for analyzing recent form (hot/cold streaks) and
    calculating how consistent (or inconsistent) a player has been lately.

    Args:
        player_id (int or str): The NBA player's unique ID
        last_n_games (int): How many recent games to return (default: 20)

    Returns:
        list of dict: Recent game stats, newest game first.
                      Returns empty list if the fetch fails.

    Example return value:
        [
            {'game_date': '2026-03-05', 'pts': 28, 'reb': 7, 'ast': 5, ...},
            {'game_date': '2026-03-03', 'pts': 14, 'reb': 4, 'ast': 8, ...},
        ]
    """
    # ── nba_api ──────────────────────────────────────────────
    # Import inside function for graceful failure
    try:
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        _logger.error("ERROR: nba_api is not installed. Run: pip install nba_api")
        return []

    try:
        # Fetch the player's game log
        if _RATE_LIMITER_AVAILABLE and _rate_limiter:
            _rate_limiter.acquire()
        game_log_endpoint = playergamelog.PlayerGameLog(
            player_id=player_id,
            season_type_all_star="Regular Season",
            timeout=NBA_API_GAMELOG_TIMEOUT,
        )

        # Convert to list of dicts
        _gl_df = _safe_get_first_dataframe(game_log_endpoint)
        if _gl_df is None:
            if _RATE_LIMITER_AVAILABLE and _rate_limiter:
                _rate_limiter.record_request()
            return []
        game_log_data = _gl_df.to_dict("records")
        if _RATE_LIMITER_AVAILABLE and _rate_limiter:
            _rate_limiter.record_request()

        # Add API delay
        time.sleep(API_DELAY_SECONDS)

        # Take only the most recent N games
        recent_games = game_log_data[:last_n_games]

        # Build a clean list of game dictionaries
        formatted_games = []
        for game in recent_games:
            # Map nba_api column names to friendly names
            formatted_game = {
                "game_date": game.get("GAME_DATE", ""),     # Date of the game
                "matchup": game.get("MATCHUP", ""),          # e.g. "LAL vs. GSW"
                "win_loss": game.get("WL", ""),              # "W" or "L"
                "minutes": float(game.get("MIN", 0) or 0),  # Minutes played
                "pts": float(game.get("PTS", 0) or 0),       # Points
                "reb": float(game.get("REB", 0) or 0),       # Rebounds
                "ast": float(game.get("AST", 0) or 0),       # Assists
                "stl": float(game.get("STL", 0) or 0),       # Steals
                "blk": float(game.get("BLK", 0) or 0),       # Blocks
                "tov": float(game.get("TOV", 0) or 0),       # Turnovers
                "fg3m": float(game.get("FG3M", 0) or 0),     # 3-pointers made
                "ft_pct": float(game.get("FT_PCT", 0) or 0), # Free throw %
                "ftm": float(game.get("FTM", 0) or 0),       # Free throws made
                "fta": float(game.get("FTA", 0) or 0),       # Free throws attempted
                "fgm": float(game.get("FGM", 0) or 0),       # Field goals made
                "fga": float(game.get("FGA", 0) or 0),       # Field goals attempted
                "oreb": float(game.get("OREB", 0) or 0),     # Offensive rebounds
                "dreb": float(game.get("DREB", 0) or 0),     # Defensive rebounds
                "pf": float(game.get("PF", 0) or 0),         # Personal fouls
            }
            formatted_games.append(formatted_game)

        return formatted_games  # Return the list of recent games

    except Exception as error:
        _logger.error(f"Error fetching game log for player {player_id}: {error}")
        return []  # Return empty list on failure

# ============================================================
# END SECTION: Player Game Log Fetcher
# ============================================================


# ============================================================
# SECTION: Full Update Function
# Runs all fetchers in sequence to update everything at once.
# ============================================================

def fetch_all_data(progress_callback=None, targeted=False, todays_games=None):
    """
    Fetch ALL live data: player stats, team stats, and defensive ratings.

    Args:
        progress_callback (callable, optional): Progress function.
            Called with (current_step, total_steps, message).
        targeted (bool): If True and todays_games is provided, only fetch
            players on teams playing today (faster, uses current rosters).
        todays_games (list, optional): Required when targeted=True.

    Returns:
        dict: Results showing what succeeded and what failed.
            Example: {'players': True, 'teams': True}
    """
    results = {
        "players": False,
        "teams": False,
    }

    _logger.info("Starting full data update...")

    # --------------------------------------------------------
    # Step 1: Fetch player stats (targeted or full)
    # --------------------------------------------------------

    if progress_callback:
        progress_callback(0, 20, "Starting player stats update...")

    if targeted and todays_games:
        # Targeted fetch: only players on today's teams
        def player_progress(current, total, message):
            if progress_callback:
                progress_callback(current, 20, f"[Players] {message}")
        results["players"] = fetch_todays_players_only(
            todays_games, progress_callback=player_progress
        )
    else:
        # Full fetch: all ~500 NBA players
        def player_progress(current, total, message):
            if progress_callback:
                progress_callback(current, 20, f"[Players] {message}")
        results["players"] = fetch_player_stats(progress_callback=player_progress)

    _logger.info("Player stats update complete. Starting team stats update...")

    # --------------------------------------------------------
    # Step 2: Fetch team stats
    # --------------------------------------------------------

    def team_progress(current, total, message):
        if progress_callback:
            progress_callback(10 + int(10 * current / max(total, 1)), 20, f"[Teams] {message}")

    results["teams"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(20, 20, "✅ All data updated!")

    _logger.info(f"Full update complete. Results: {results}")
    return results

# ============================================================
# END SECTION: Full Update Function
# ============================================================


# ============================================================
# SECTION: One-Click Today's Data Fetcher
# Fetches games, today's team rosters+stats, and team stats
# in a single call — the "Auto-Load" button entry point.
# ============================================================

def fetch_all_todays_data(progress_callback=None):
    """
    One-click function: fetch tonight's games, player stats for those
    teams, team stats, and player injury/availability status.

    Steps:
        1. Fetch tonight's games (ScoreBoard)
        2. Fetch current rosters + player stats (includes injury data via
           RosterEngine — no separate injury fetch step needed)
        3. Fetch team stats for the analysis engine

    Args:
        progress_callback (callable, optional): Called with (current, total, msg).

    Returns:
        dict: {
            "games": list of game dicts (empty list if none),
            "players_updated": bool,
            "teams_updated": bool,
            "injury_status": dict,  # player_name_lower → status_dict
        }
    """
    results = {
        "games": [],
        "players_updated": False,
        "teams_updated": False,
        "injury_status": {},
    }

    # --------------------------------------------------------
    # Step 1: Fetch tonight's games
    # --------------------------------------------------------
    if progress_callback:
        progress_callback(0, 40, "Step 1/3 — Fetching tonight's games...")

    games = fetch_todays_games()
    results["games"] = games

    if not games:
        _logger.info("fetch_all_todays_data: No games found for tonight.")
        return results

    if progress_callback:
        progress_callback(2, 40, f"Step 1/3 ✅ Found {len(games)} game(s). Fetching players + injury data...")

    # --------------------------------------------------------
    # Step 2: Fetch player stats for tonight's teams.
    # RosterEngine.refresh() is called inside fetch_todays_players_only(),
    # providing injury data and rosters in one pass.  The injury map is
    # written to INJURY_STATUS_JSON_PATH so it can be loaded after this call.
    # --------------------------------------------------------
    def player_progress(current, total, message):
        if progress_callback:
            # Progress range for Step 2: steps 2-29 out of 40
            scaled = 2 + int(27 * current / max(total, 1))
            progress_callback(scaled, 40, f"Step 2/3 — {message}")

    results["players_updated"] = fetch_todays_players_only(
        games,
        progress_callback=player_progress,
    )

    # Load the injury map written by fetch_todays_players_only
    if results["players_updated"]:
        try:
            from data.data_manager import load_injury_status as _load_inj
            results["injury_status"] = _load_inj()
        except Exception as _inj_load_err:
            _logger.info(f"fetch_all_todays_data: could not load injury map after player fetch: {_inj_load_err}")

    if progress_callback:
        status = "✅" if results["players_updated"] else "⚠️"
        progress_callback(29, 40, f"Step 2/3 {status} Player stats done. Fetching team stats...")

    # --------------------------------------------------------
    # Step 3: Fetch team stats
    # --------------------------------------------------------
    def team_progress(current, total, message):
        if progress_callback:
            # Progress range for Step 3: steps 29-40 out of 40
            scaled = 29 + int(11 * current / max(total, 1))
            progress_callback(scaled, 40, f"Step 3/3 — {message}")

    results["teams_updated"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(40, 40, "✅ All done! Games, players, team stats, and injury status loaded.")

    players_updated = results["players_updated"]
    teams_updated = results["teams_updated"]
    games_count = len(results["games"])
    _logger.info(f"fetch_all_todays_data complete: players_updated={players_updated}, "
          f"teams_updated={teams_updated}, games={games_count}")
    return results

# ============================================================
# END SECTION: One-Click Today's Data Fetcher
# ============================================================


# ============================================================
# SECTION: Team Roster Cache
# Delegates entirely to RosterEngine — the single authoritative
# source for all roster data (nba_api CommonTeamRoster).
# ============================================================


def fetch_active_rosters(team_abbrevs=None, progress_callback=None):
    """
    Fetch current active rosters for the given teams.

    Delegates to RosterEngine (nba_api CommonTeamRoster) — the single
    authoritative source — replacing the old direct CommonTeamRoster calls.

    Args:
        team_abbrevs (list of str, optional): Team abbreviations to fetch.
            If None, returns an empty dict (caller should specify teams).
        progress_callback (callable, optional): Accepted for API compatibility
            but not used (RosterEngine handles its own progress internally).

    Returns:
        dict: {team_abbrev: [player_name, ...]}
    """
    from data.roster_engine import RosterEngine
    engine = RosterEngine()
    engine.refresh(team_abbrevs)
    result = {}
    for abbrev in (team_abbrevs or []):
        result[abbrev] = engine.get_active_roster(abbrev)
    return result


def get_cached_roster(team_abbrev):
    """
    Return the active roster for a team via RosterEngine.

    Args:
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        list of str: Player names on the active roster, or empty list.
    """
    return fetch_active_rosters([team_abbrev]).get(team_abbrev.upper(), [])

# ============================================================
# END SECTION: Team Roster Cache
# ============================================================


# ============================================================
# SECTION: Dynamic CV Estimation Helper (W10)
# Returns tier-based coefficients of variation for fallback
# std deviation estimates when live game logs are unavailable.
# ============================================================

def _dynamic_cv_for_live_fetch(stat_type, stat_avg):
    """
    Get a dynamic coefficient of variation for fallback std estimation. (W10)

    Delegates to `_get_dynamic_cv()` in projections.py to avoid duplicating
    the tier-threshold logic. This ensures both the live fetcher and the
    projection engine use identical CV tiers.

    Args:
        stat_type (str): 'points', 'rebounds', 'assists', 'threes', etc.
        stat_avg (float): Player's season average for this stat.

    Returns:
        float: Coefficient of variation to multiply against stat_avg.
    """
    # Import here to avoid a circular import at module load time.
    # (live_data_fetcher is imported by data_manager which may be imported
    # before engine.projections, so this lazy import is intentional.)
    from engine.projections import _get_dynamic_cv
    return _get_dynamic_cv(stat_type, stat_avg)

# ============================================================
# END SECTION: Dynamic CV Estimation Helper
# ============================================================


# ============================================================
# SECTION: ETL-Backed Refresh Functions
# These functions use the pre-populated SQLite database
# (db/smartpicks.db) instead of making live API calls.
# "Smart Update" → incremental pull; "Full Update" → full season pull.
# ============================================================


def refresh_from_etl(progress_callback=None) -> dict:
    """
    Smart Update via ETL: fetch only game logs added since the last
    stored date in db/smartpicks.db.

    If the database is empty (no games loaded yet), automatically performs
    a full initial pull instead of an incremental update.

    Args:
        progress_callback (callable | None):
            Called with (current, total, message).

    Returns:
        dict: {new_games, new_logs, new_players, error (optional)}
    """
    if progress_callback:
        progress_callback(0, 4, "Connecting to ETL database…")

    try:
        # Check whether the database needs a full initial seed.
        from data.etl_data_service import get_db_counts
        counts = get_db_counts()
        if counts.get("games", 0) == 0:
            _logger.info(
                "Database has no games — running full initial pull."
            )
            if progress_callback:
                progress_callback(1, 4,
                    "Database is empty — running full initial pull…")
            result = full_refresh_from_etl(
                progress_callback=progress_callback,
            )
            # Normalise to the dict keys the Smart-ETL UI handler expects.
            return {
                "new_games": result.get("games_inserted", 0),
                "new_logs": result.get("logs_inserted", 0),
                "new_players": result.get("players_inserted", 0),
                "error": result.get("error"),
            }

        from data.etl_data_service import refresh_data as _etl_refresh
        if progress_callback:
            progress_callback(1, 4, "Running incremental update…")

        result = _etl_refresh()

        if progress_callback:
            ng = result.get("new_games", 0)
            nl = result.get("new_logs",  0)
            progress_callback(3, 4, f"Update complete — {ng} new games, {nl} new logs.")

        # Bust Streamlit caches so load_players_data() re-reads the DB
        _invalidate_data_caches()

        if progress_callback:
            progress_callback(4, 4, "✅ Smart ETL update done!")

        return result
    except Exception as exc:
        _logger.error("refresh_from_etl failed: %s", exc)
        if progress_callback:
            progress_callback(4, 4, f"❌ ETL update failed: {exc}")
        return {"new_games": 0, "new_logs": 0, "new_players": 0, "error": str(exc)}


def full_refresh_from_etl(season: str | None = None, progress_callback=None) -> dict:
    """
    Full Update via ETL: re-pull the entire season of game logs from
    nba_api.stats.endpoints.LeagueGameLog and repopulate db/smartpicks.db.

    Args:
        season (str | None): Season string e.g. '2025-26'.  Defaults to
            current season as determined by etl/initial_pull.py.
        progress_callback (callable | None):
            Called with (current, total, message).

    Returns:
        dict: {players_inserted, games_inserted, logs_inserted, error (optional)}
    """
    if progress_callback:
        progress_callback(0, 4, "Starting full ETL pull from nba_api…")

    try:
        from etl.initial_pull import run_initial_pull
        kwargs = {}
        if season:
            kwargs["season"] = season

        if progress_callback:
            progress_callback(1, 4, "Fetching all game logs (this may take ~60 s)…")

        result = run_initial_pull(**kwargs)

        # run_initial_pull() now returns a counts dict.  Fall back to
        # reading the DB if it ever returns None (legacy safety).
        if result is None:
            import sqlite3
            from etl.setup_db import DB_PATH as _etl_db_path
            conn = sqlite3.connect(_etl_db_path)
            try:
                result = {
                    "players_inserted": conn.execute(
                        "SELECT COUNT(*) FROM Players"
                    ).fetchone()[0],
                    "games_inserted": conn.execute(
                        "SELECT COUNT(*) FROM Games"
                    ).fetchone()[0],
                    "logs_inserted": conn.execute(
                        "SELECT COUNT(*) FROM Player_Game_Logs"
                    ).fetchone()[0],
                }
            finally:
                conn.close()

        if progress_callback:
            pi = result.get("players_inserted", 0)
            gi = result.get("games_inserted",   0)
            li = result.get("logs_inserted",    0)
            progress_callback(3, 4, f"DB populated — {pi} players, {gi} games, {li} logs.")

        # Bust Streamlit caches
        _invalidate_data_caches()

        if progress_callback:
            progress_callback(4, 4, "✅ Full ETL pull done!")

        return result
    except Exception as exc:
        _logger.error("full_refresh_from_etl failed: %s", exc)
        if progress_callback:
            progress_callback(4, 4, f"❌ Full ETL pull failed: {exc}")
        return {"players_inserted": 0, "games_inserted": 0, "logs_inserted": 0, "error": str(exc)}

# ============================================================
# END SECTION: ETL-Backed Refresh Functions
# ============================================================
