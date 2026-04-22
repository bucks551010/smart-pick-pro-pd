# ============================================================
# FILE: data/data_manager.py
# PURPOSE: Load, save, and manage all CSV data files for the app.
#          Handles player stats, prop lines, and team data.
# CONNECTS TO: All pages use this to load data
# CONCEPTS COVERED: CSV reading/writing, file paths, caching
# ============================================================

# Standard library imports only
import csv        # Built-in CSV reader/writer
import os         # File path operations
import json       # For session state persistence
import datetime   # For timestamp handling
import unicodedata  # For normalizing unicode characters in names
import re           # For regex-based suffix stripping
import warnings
from pathlib import Path  # Modern file path handling

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

import streamlit as st


# ============================================================
# SECTION: File Path Constants
# Define paths to all data files relative to the project root.
# Using pathlib.Path makes this work on Windows, Mac, and Linux.
# ============================================================

# Get the directory where this file lives (the 'data' folder)
DATA_DIRECTORY = Path(__file__).parent

# Build full paths to each CSV file
PLAYERS_CSV_PATH = DATA_DIRECTORY / "players.csv"
PROPS_CSV_PATH = DATA_DIRECTORY / "props.csv"
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"

# Path to the live data timestamp file
# BEGINNER NOTE: This JSON file is created by nba_data_service.py
# when real data is downloaded. Its existence tells us if live data is loaded.
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"

# Path to the persisted injury/availability status cache written by
# get_todays_players() via RosterEngine in nba_data_service.py.
INJURY_STATUS_JSON_PATH = DATA_DIRECTORY / "injury_status.json"

# ============================================================
# END SECTION: File Path Constants
# ============================================================


# ============================================================
# SECTION: CSV Loading Functions
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def load_players_data():
    """
    Load all player data.

    Primary source: ETL SQLite database (db/smartpicks.db) when available.
    Fallback: players.csv (legacy / manually-loaded data).

    Returns a list of dictionaries, where each dictionary represents one
    player with all their stats as keys.
    Returns an empty list if neither the database nor the CSV file exists.

    Returns:
        list of dict: Player rows, e.g.:
            [{'name': 'LeBron James', 'team': 'LAL', 'points_avg': 24.8, ...}, ...]

    Example:
        players = load_players_data()
        if not players:
            # Prompt user to retrieve live data from the Smart NBA Data page
            pass
        else:
            lebron = players[0]
            print(lebron['points_avg'])  # → '24.8'
    """
    # ── Try ETL database first ────────────────────────────────────────────────
    try:
        from data.etl_data_service import get_all_players as _etl_get_all_players
        etl_players = _etl_get_all_players()
        if etl_players:
            return _convert_etl_players_to_app_format(etl_players)
    except Exception as _etl_err:
        _logger.debug("load_players_data: ETL source unavailable (%s), falling back to CSV.", _etl_err)

    # ── Fallback: CSV file ────────────────────────────────────────────────────
    return _load_csv_file(PLAYERS_CSV_PATH)


def _convert_etl_players_to_app_format(etl_players: list) -> list:
    """
    Convert ETL player dicts to the format expected by the rest of the app.

    ETL format:  player_id, first_name, last_name, team_id, team_abbreviation,
                 position, gp, ppg, rpg, apg, spg, bpg, topg, mpg,
                 fg3_avg, ftm_avg, fta_avg, ft_pct_avg, fgm_avg, fga_avg,
                 fg_pct_avg, oreb_avg, dreb_avg, pf_avg, plus_minus_avg,
                 points_std, rebounds_std, assists_std, threes_std
    App format:  player_id, name, team, position, minutes_avg, points_avg,
                 rebounds_avg, assists_avg, steals_avg, blocks_avg,
                 turnovers_avg, threes_avg, ft_pct, usage_rate,
                 points_std, rebounds_std, assists_std, ...
    """
    result = []
    for p in etl_players:
        ppg  = float(p.get("ppg",  0) or 0)
        rpg  = float(p.get("rpg",  0) or 0)
        apg  = float(p.get("apg",  0) or 0)
        spg  = float(p.get("spg",  0) or 0)
        bpg  = float(p.get("bpg",  0) or 0)
        topg = float(p.get("topg", 0) or 0)
        mpg  = float(p.get("mpg",  0) or 0)

        # Real computed values from the DB (fall back to estimates when 0/missing)
        fg3_avg    = float(p.get("fg3_avg",    0) or 0)
        ftm_avg    = float(p.get("ftm_avg",    0) or 0)
        fta_avg    = float(p.get("fta_avg",    0) or 0)
        ft_pct_avg = float(p.get("ft_pct_avg", 0) or 0)
        fgm_avg    = float(p.get("fgm_avg",    0) or 0)
        fga_avg    = float(p.get("fga_avg",    0) or 0)
        oreb_avg   = float(p.get("oreb_avg",   0) or 0)
        dreb_avg   = float(p.get("dreb_avg",   0) or 0)
        pf_avg     = float(p.get("pf_avg",     0) or 0)

        # Real standard deviations from DB; fall back to CV-ratio estimates
        points_std   = float(p.get("points_std",   0) or 0) or round(ppg  * 0.30, 1)
        rebounds_std = float(p.get("rebounds_std", 0) or 0) or round(rpg  * 0.40, 1)
        assists_std  = float(p.get("assists_std",  0) or 0) or round(apg  * 0.40, 1)
        threes_std   = float(p.get("threes_std",   0) or 0)
        steals_std   = float(p.get("steals_std",   0) or 0) or round(spg  * 0.50, 1)
        blocks_std   = float(p.get("blocks_std",   0) or 0) or round(bpg  * 0.60, 1)
        turnovers_std = float(p.get("turnovers_std", 0) or 0) or round(topg * 0.40, 1)
        ftm_std      = float(p.get("ftm_std",      0) or 0)
        oreb_std     = float(p.get("oreb_std",     0) or 0)
        plus_minus_std = float(p.get("plus_minus_std", 0) or 0)

        result.append({
            "player_id":               str(p.get("player_id", "")),
            "name":                    f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "team":                    p.get("team_abbreviation", "") or "",
            # Use real position from DB; fall back to "SF" only when NULL/absent
            "position":                p.get("position") or "SF",
            "minutes_avg":             round(mpg, 1),
            "points_avg":              round(ppg, 1),
            "rebounds_avg":            round(rpg, 1),
            "assists_avg":             round(apg, 1),
            "steals_avg":              round(spg, 1),
            "blocks_avg":              round(bpg, 1),
            "turnovers_avg":           round(topg, 1),
            "threes_avg":              round(fg3_avg, 1),
            "ft_pct":                  round(ft_pct_avg, 3),
            # usage_rate is not available from LeagueGameLog — requires advanced stats endpoint
            "usage_rate":              float(p.get("usg_pct", 0) or 0),
            # Real usage and efficiency from Player_Bio (NBA-tracked)
            "usg_pct":                 float(p.get("usg_pct", 0) or 0),
            "ts_pct":                  float(p.get("ts_pct", 0) or 0),
            "oreb_pct":                float(p.get("oreb_pct", 0) or 0),
            "dreb_pct":                float(p.get("dreb_pct", 0) or 0),
            "net_rating":              float(p.get("net_rating", 0) or 0),
            # Actual DD/TD rates from League_Dash_Player_Stats (dd2/td3 ÷ gp)
            "double_double_rate":      float(p.get("double_double_rate", 0) or 0),
            "triple_double_rate":      float(p.get("triple_double_rate", 0) or 0),
            "points_std":              round(points_std, 1),
            "rebounds_std":            round(rebounds_std, 1),
            "assists_std":             round(assists_std, 1),
            "threes_std":              round(threes_std, 1),
            "steals_std":              round(steals_std, 1),
            "blocks_std":              round(blocks_std, 1),
            "turnovers_std":           round(turnovers_std, 1),
            "ftm_avg":                 round(ftm_avg, 1),
            "fta_avg":                 round(fta_avg, 1),
            "fga_avg":                 round(fga_avg, 1),
            "fgm_avg":                 round(fgm_avg, 1),
            "offensive_rebounds_avg":  round(oreb_avg, 1),
            "defensive_rebounds_avg":  round(dreb_avg, 1),
            "personal_fouls_avg":      round(pf_avg, 1),
            "ftm_std":                 round(ftm_std, 1),
            "fta_std":                 0.0,
            "fga_std":                 0.0,
            "fgm_std":                 0.0,
            "offensive_rebounds_std":  round(oreb_std, 1),
            "defensive_rebounds_std":  0.0,
            "personal_fouls_std":      0.0,
            "plus_minus_std":          round(plus_minus_std, 1),
            # Games played (bonus field used by some analysis pages)
            "games_played":            str(p.get("gp", 0)),
        })
    return result


@st.cache_data(ttl=900, show_spinner=False)
def load_props_data():
    """
    Load all prop lines from the props.csv file.

    Returns an empty list if the file does not exist yet (first run before
    a live data retrieval has been performed).

    Returns:
        list of dict: Prop rows, e.g.:
            [{'player_name': 'LeBron James', 'stat_type': 'points',
              'line': '24.5', 'platform': 'PrizePicks', ...}, ...]
    """
    return _load_csv_file(PROPS_CSV_PATH)


@st.cache_data(ttl=900, show_spinner=False)
def load_teams_data():
    """
    Load all 30 NBA teams.

    Primary source: ETL SQLite database (db/smartpicks.db) when available.
    Fallback: teams.csv (legacy / manually-loaded data).

    Returns:
        list of dict: Team rows with pace, ortg, drtg, etc.
    """
    try:
        from data.etl_data_service import get_all_teams as _etl_get_all_teams
        etl_teams = _etl_get_all_teams()
        if etl_teams:
            return etl_teams
    except Exception as _etl_err:
        _logger.debug("load_teams_data: ETL source unavailable (%s), falling back to CSV.", _etl_err)
    return _load_csv_file(TEAMS_CSV_PATH)


@st.cache_data(ttl=900, show_spinner=False)
def load_defensive_ratings_data():
    """
    Load team defensive ratings by position.

    Primary source: ETL SQLite database (db/smartpicks.db) when available.
    Fallback: defensive_ratings.csv (legacy / manually-loaded data).

    Returns:
        list of dict: Defensive rating rows with vs_PG_pts, etc.
    """
    try:
        from data.etl_data_service import get_all_defense_vs_position as _etl_get_dvp
        etl_dvp = _etl_get_dvp()
        if etl_dvp:
            return etl_dvp
    except Exception as _etl_err:
        _logger.debug("load_defensive_ratings_data: ETL source unavailable (%s), falling back to CSV.", _etl_err)
    return _load_csv_file(DEFENSIVE_RATINGS_CSV_PATH)


@st.cache_data(ttl=900, show_spinner=False)
def load_injury_status():
    """
    Load the persisted player injury/availability status map from disk.

    The status map is written by ``get_todays_players()`` via
    RosterEngine in ``nba_data_service.py`` after each data-update cycle.
    This function provides a fast, no-API-call way for the Analysis and
    Prop Scanner pages to check player availability on startup.

    Returns:
        dict: player_name_lower → {
            "status": str,          # "Active"|"Out"|"GTD"|"Questionable"|"Day-to-Day"|"Injured Reserve"
            "injury_note": str,     # human-readable reason from nba_api signals
            "games_missed": int,
            "return_date": str,     # ISO date or "" (populated by web scraper when available)
            "last_game_date": str,
            "gp_ratio": float,
            # Optional fields added by Layer 5 web scraping:
            "injury": str,          # specific body part/reason, e.g. "Knee – soreness"
            "source": str,          # scraper that provided this entry, e.g. "NBA.com"
            "comment": str,         # additional notes from the official injury report
        }
        Returns an empty dict if the file does not exist or cannot be parsed.
    """
    if not INJURY_STATUS_JSON_PATH.exists():
        return {}
    try:
        with open(INJURY_STATUS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # Defensive copy: @st.cache_data caches the return value by reference.
        # If a caller mutates the returned dict (e.g., popping a player key),
        # the cached copy is corrupted for every Streamlit session.
        return {k: dict(v) if isinstance(v, dict) else v for k, v in data.items()}
    except Exception as err:
        _logger.warning("load_injury_status: could not read %s: %s", INJURY_STATUS_JSON_PATH, err)
        return {}


def _load_csv_file(file_path):
    """
    Internal helper: load any CSV file and return list of dicts.

    Each row becomes a dictionary mapping column name → value.
    CSV headers become the dictionary keys.

    Args:
        file_path (Path or str): Path to the CSV file

    Returns:
        list of dict: Rows as dictionaries, or empty list if error
    """
    # Convert to Path object if it's a string
    file_path = Path(file_path)

    # Check if the file exists before trying to open it
    if not file_path.exists():
        # Return empty list instead of crashing
        return []

    rows = []  # Will hold all the row dictionaries

    try:
        # Open the file for reading
        # encoding='utf-8' handles special characters
        # newline='' is required by Python's csv module
        with open(file_path, encoding="utf-8", newline="") as csv_file:
            # DictReader automatically uses the first row as column names
            # BEGINNER NOTE: csv.DictReader is like a spreadsheet reader —
            # it maps each row's values to its column header names
            reader = csv.DictReader(csv_file)

            for row in reader:
                # Strip whitespace from all values
                # BEGINNER NOTE: dict comprehension builds a new dict
                # by looping over key-value pairs and stripping spaces
                cleaned_row = {
                    key.strip(): value.strip()
                    for key, value in row.items()
                    if key is not None  # Skip None keys (empty columns)
                }
                rows.append(cleaned_row)

    except Exception as error:
        # If anything goes wrong, return empty list
        # The app will show a message asking user to check the file
        _logger.warning("Error loading %s: %s", file_path, error)
        return []

    # Return a defensive copy.  @st.cache_data caches by reference —
    # if a caller mutates the returned list or inner dicts, the cache
    # is permanently corrupted for every Streamlit session.
    # Building new dicts via the comprehension above already creates
    # fresh row dicts, but we still need a fresh outer list to prevent
    # callers from appending/popping rows on the cached object.
    return list(rows)


# ============================================================
# END SECTION: CSV Loading Functions
# ============================================================


# ============================================================
# SECTION: Player Lookup Functions
# ============================================================

def find_player_by_name(players_list, player_name):
    """
    Find a player by their name in the players list.

    Uses fuzzy/normalized matching so slight name differences
    (suffixes, unicode, nicknames) are handled automatically.

    Args:
        players_list (list of dict): Loaded player data
        player_name (str): Player name to search for

    Returns:
        dict or None: Player data dict, or None if not found

    Example:
        player = find_player_by_name(players, "LeBron James")
        print(player['points_avg'])  # → '24.8'
    """
    # Delegate to the fuzzy matcher which handles all matching strategies
    return find_player_by_name_fuzzy(players_list, player_name)


# ============================================================
# SECTION: Player Name Normalization & Fuzzy Matching
# These helpers ensure props from sportsbook platforms
# match our internal player database even when names differ in
# capitalization, unicode accents, Jr./III suffixes, or nicknames.
# ============================================================

# Common nickname / alias mismatches between prop platforms and nba_api.
# Key = variant used by prop sites, Value = canonical name in our DB.
NAME_ALIASES = {
    "nic claxton": "nicolas claxton",
    "nicolas claxton": "nicolas claxton",
    "og anunoby": "o.g. anunoby",
    "o.g. anunoby": "o.g. anunoby",
    "mo bamba": "mohamed bamba",
    "tj mcconnell": "t.j. mcconnell",
    "t.j. mcconnell": "t.j. mcconnell",
    "tj warren": "t.j. warren",
    "cj mccollum": "c.j. mccollum",
    "c.j. mccollum": "c.j. mccollum",
    "pj tucker": "p.j. tucker",
    "p.j. tucker": "p.j. tucker",
    "rj barrett": "r.j. barrett",
    "r.j. barrett": "r.j. barrett",
    "aj green": "a.j. green",
    "nah'shon hyland": "bones hyland",
    "bones hyland": "bones hyland",
    "gary trent jr": "gary trent jr.",
    "gary trent jr.": "gary trent jr.",
    "wendell carter jr": "wendell carter jr.",
    "wendell carter jr.": "wendell carter jr.",
    "jaren jackson jr": "jaren jackson jr.",
    "jaren jackson jr.": "jaren jackson jr.",
    "kenyon martin jr": "kenyon martin jr.",
    "kenyon martin jr.": "kenyon martin jr.",
    "kevin porter jr": "kevin porter jr.",
    "larry nance jr": "larry nance jr.",
    "otto porter jr": "otto porter jr.",
    "derrick jones jr": "derrick jones jr.",
    "marcus morris sr": "marcus morris sr.",
    "naji marshall": "naji marshall",
    "alex len": "alex len",
    "alexandre sarr": "alexandre sarr",
    "goga bitadze": "goga bitadze",
    "giddey": "josh giddey",
    "josh giddey": "josh giddey",
    "sga": "shai gilgeous-alexander",
    "shai": "shai gilgeous-alexander",
    "shai gilgeous-alexander": "shai gilgeous-alexander",
    "kt": "karl-anthony towns",
    "karl-anthony towns": "karl-anthony towns",
    "zion": "zion williamson",
    "zion williamson": "zion williamson",
    "kd": "kevin durant",
    "kevin durant": "kevin durant",
    "kyrie": "kyrie irving",
    "kyrie irving": "kyrie irving",
    "steph": "stephen curry",
    "stephen curry": "stephen curry",
    "lebron": "lebron james",
    "lebron james": "lebron james",
    "bron": "lebron james",
    "ad": "anthony davis",
    "anthony davis": "anthony davis",
    "joker": "nikola jokic",
    "nikola jokic": "nikola jokic",
    "embiid": "joel embiid",
    "joel embiid": "joel embiid",
    "luka": "luka doncic",
    "luka doncic": "luka doncic",
    "tatum": "jayson tatum",
    "jayson tatum": "jayson tatum",
    "ja": "ja morant",
    "ja morant": "ja morant",
    "jrue holiday": "jrue holiday",
    "demar derozan": "demar derozan",
    "pascal siakam": "pascal siakam",
    "darius garland": "darius garland",
    "donovan mitchell": "donovan mitchell",
    "damian lillard": "damian lillard",
    "dam lillard": "damian lillard",
    "dame": "damian lillard",
    "khris middleton": "khris middleton",
    "giannis": "giannis antetokounmpo",
    "giannis antetokounmpo": "giannis antetokounmpo",
    "bam": "bam adebayo",
    "bam adebayo": "bam adebayo",
    "jimmy butler": "jimmy butler",
    "jimmy": "jimmy butler",
    "trae": "trae young",
    "trae young": "trae young",
    "devin booker": "devin booker",
    "book": "devin booker",
    "ayton": "deandre ayton",
    "deandre ayton": "deandre ayton",
}

# Suffixes to strip when normalizing player names for matching
_NAME_SUFFIXES_TO_STRIP = re.compile(
    r'\s+(jr\.?|sr\.?|ii|iii|iv|v)$',
    flags=re.IGNORECASE,
)


def normalize_player_name(name):
    """
    Normalize a player name for fuzzy matching.

    Steps:
    1. Strip leading/trailing whitespace
    2. Lowercase
    3. Normalize unicode (NFD → ASCII where possible, e.g., é → e)
    4. Remove trailing suffixes (Jr., Sr., II, III, IV)
    5. Collapse multiple spaces

    Args:
        name (str): Raw player name (e.g., "LeBron James Jr.")

    Returns:
        str: Normalized name (e.g., "lebron james")

    Example:
        normalize_player_name("Nikola Jokić") → "nikola jokic"
        normalize_player_name("Jaren Jackson Jr.") → "jaren jackson"
    """
    if not name:
        return ""

    # Step 1: Strip and lowercase
    name = name.strip().lower()

    # Step 2: Normalize unicode characters (e.g., ć → c, é → e)
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Step 3: Strip common suffixes (Jr., Sr., II, III, etc.)
    name = _NAME_SUFFIXES_TO_STRIP.sub("", name).strip()

    # Step 4: Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def _build_player_index(players_list):
    """
    Build pre-computed lookup indices for a players list.

    Returns three dicts so that find_player_by_name_fuzzy() can resolve
    most lookups in O(1) instead of scanning the entire list per call.
    This is critical when matching 6,000+ props against 500+ players.

    Returns:
        tuple: (lower_index, alias_index, normalized_index) where each maps
        a string key → player dict.
    """
    lower_index = {}       # lowered name → player
    normalized_index = {}  # normalized name → player

    for player in players_list:
        if not isinstance(player, dict):
            continue
        raw_name = player.get("name", "")
        lname = raw_name.lower().strip()
        nname = normalize_player_name(raw_name)

        # First player wins for each key (stable ordering)
        if lname and lname not in lower_index:
            lower_index[lname] = player
        if nname and nname not in normalized_index:
            normalized_index[nname] = player

    # Alias index: resolve each alias target to a player via the lower index
    alias_index = {}
    for alias_key, canonical in NAME_ALIASES.items():
        if alias_key not in alias_index and canonical in lower_index:
            alias_index[alias_key] = lower_index[canonical]

    return lower_index, alias_index, normalized_index


# Module-level cache for the player index. Invalidated when the
# players_list identity (id) changes (e.g., after a data reload).
import threading as _threading
_player_index_lock = _threading.Lock()
_player_index_cache = {"list_id": None, "index": (None, None, None)}


def find_player_by_name_fuzzy(players_list, player_name):
    """
    Find a player using fuzzy / normalized name matching.

    Matching order (first match wins):
    1. Exact case-insensitive match (O(1) via index)
    2. Alias lookup (O(1) via index)
    3. Normalized name match (O(1) via index)
    4. Partial / substring match on normalized names (O(n) fallback)

    The first three passes use pre-computed dict indices built once per
    players_list, making repeated calls (e.g., matching 6,000 props)
    close to O(m) instead of O(m × n).

    Args:
        players_list (list of dict): Loaded player data
        player_name (str): Player name from prop (may be a nickname/alias)

    Returns:
        dict or None: Player data dict, or None if not found

    Example:
        find_player_by_name_fuzzy(players, "Nic Claxton")
        → same result as find_player_by_name(players, "Nicolas Claxton")
    """
    if not player_name:
        return None

    # ── Lazily build / cache the index for this players_list ──
    list_id = id(players_list)
    with _player_index_lock:
        if _player_index_cache["list_id"] != list_id:
            _player_index_cache["index"] = _build_player_index(players_list)
            _player_index_cache["list_id"] = list_id

    lower_index, alias_index, normalized_index = _player_index_cache["index"]

    search_lower = player_name.lower().strip()

    # --- Pass 1: Exact case-insensitive (O(1)) ---
    match = lower_index.get(search_lower)
    if match is not None:
        return match

    # --- Pass 2: Alias lookup (O(1)) ---
    match = alias_index.get(search_lower)
    if match is not None:
        return match

    # --- Pass 3: Normalized name match (O(1)) ---
    search_normalized = normalize_player_name(player_name)
    match = normalized_index.get(search_normalized)
    if match is not None and search_normalized:
        return match

    # --- Pass 4: Partial / substring match on normalized names (O(n) fallback) ---
    if len(search_normalized) > 3:
        for player in players_list:
            if not isinstance(player, dict):
                continue
            stored_normalized = normalize_player_name(player.get("name", ""))
            if (search_normalized in stored_normalized or stored_normalized in search_normalized):
                return player

    return None


def get_roster_health_report(props_list, players_list):
    """
    Check which props have matching players in the database and report
    on injury / availability status per matched player.

    Returns a report showing matched vs unmatched props so the user
    can identify name mismatches before running analysis.  Also counts
    unavailable (Out/Doubtful/Questionable/IR) and GTD players so the
    Roster Health widget in Neural Analysis is accurate.

    Args:
        props_list (list of dict): Current props (with 'player_name')
        players_list (list of dict): Loaded player data

    Returns:
        dict: {
            'matched': list of str (player names that matched),
            'unmatched': list of str (player names not found),
            'match_count': int,
            'total_count': int,
            'match_rate': float (0.0–1.0),
            'unavailable_count': int,  # Out / Doubtful / Questionable / IR
            'gtd_count': int,          # GTD / Day-to-Day
            'unavailable_players': list of str,
            'gtd_players': list of str,
        }

    Example:
        report = get_roster_health_report(props, players)
        if report['unmatched']:
            st.warning(f"Unmatched: {report['unmatched']}")
    """
    matched = []
    unmatched = []
    seen = set()  # Deduplicate player names in report

    for prop in props_list:
        name = prop.get("player_name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)

        player = find_player_by_name_fuzzy(players_list, name)
        if player:
            matched.append(name)
        else:
            unmatched.append(name)

    total = len(matched) + len(unmatched)
    match_rate = len(matched) / total if total > 0 else 1.0

    # ── Injury status counts ─────────────────────────────────────────
    injury_map = load_injury_status()
    unavailable_players = []
    gtd_players = []
    if injury_map:
        for name in matched:
            status_info = get_player_status(name, injury_map)
            status = status_info.get("status", "Active")
            if status in ("Out", "Doubtful", "Questionable", "Injured Reserve"):
                unavailable_players.append(name)
            elif status in ("GTD", "Day-to-Day"):
                gtd_players.append(name)

    return {
        "matched": sorted(matched),
        "unmatched": sorted(unmatched),
        "match_count": len(matched),
        "total_count": total,
        "match_rate": round(match_rate, 3),
        "unavailable_count": len(unavailable_players),
        "gtd_count": len(gtd_players),
        "unavailable_players": sorted(unavailable_players),
        "gtd_players": sorted(gtd_players),
    }


def validate_props_against_roster(props_list, players_list):
    """
    Validate every prop against the player database with detailed status.

    Returns three categories:
    - matched:       props with a definitive name match (exact or normalized)
    - fuzzy_matched: props where we found a probable match (partial/alias)
    - unmatched:     props where no match was found

    For each unmatched prop, a suggestion is provided (closest player name).

    Args:
        props_list (list of dict): Prop dicts with 'player_name'
        players_list (list of dict): Player dicts with 'name'

    Returns:
        dict: {
            'matched':       list of {prop, matched_name},
            'fuzzy_matched': list of {prop, matched_name, suggestion},
            'unmatched':     list of {prop, suggestion or None},
            'total':         int,
            'matched_count': int,
        }

    Example:
        report = validate_props_against_roster(props, players)
        for item in report['unmatched']:
            print(f"No match: {item['prop']['player_name']} → suggest: {item['suggestion']}")
    """
    matched = []
    fuzzy_matched = []
    unmatched = []

    # ── Build O(1) lookup indices once for the entire prop batch ─────────────
    # Previously the "normalized match" pass iterated all_player_names_list for
    # every prop: O(m × n) with m=props, n=players (~300k comparisons on a full
    # slate).  Using the pre-computed normalized_index from _build_player_index
    # reduces that to O(1) per prop — same as the exact-match pass.
    _roster_list_id = id(players_list)
    with _player_index_lock:
        if _player_index_cache["list_id"] != _roster_list_id:
            _player_index_cache["index"] = _build_player_index(players_list)
            _player_index_cache["list_id"] = _roster_list_id
    _lower_idx, _alias_idx, _normalized_idx = _player_index_cache["index"]

    # Keep exact_name_index (raw canonical name string) for the return value
    exact_name_index = {
        p.get("name", "").lower().strip(): p.get("name", "")
        for p in players_list
        if p.get("name")
    }
    all_player_names_list = [p.get("name", "") for p in players_list if p.get("name")]

    for prop in props_list:
        raw_name = prop.get("player_name", "").strip()
        if not raw_name:
            continue

        # --- Try exact match (O(1)) ---
        if raw_name.lower() in exact_name_index:
            matched.append({
                "prop": prop,
                "matched_name": exact_name_index[raw_name.lower()],
                "match_type": "exact",
            })
            continue

        # --- Try alias lookup (O(1)) ---
        alias_target = NAME_ALIASES.get(raw_name.lower())
        if alias_target and alias_target in exact_name_index:
            matched.append({
                "prop": prop,
                "matched_name": exact_name_index[alias_target],
                "match_type": "alias",
            })
            continue

        # --- Try normalized match (O(1) via pre-built index) ─────────────────
        # Previously: O(n) scan of all_player_names_list per prop.
        # Now: O(1) dict lookup using the normalized_index from _build_player_index.
        normalized_search = normalize_player_name(raw_name)
        norm_player = _normalized_idx.get(normalized_search) if normalized_search else None
        if norm_player:
            matched.append({
                "prop": prop,
                "matched_name": norm_player.get("name", raw_name),
                "match_type": "normalized",
            })
            continue

        # --- Try partial / substring match (O(n) fallback — unavoidable) ---
        partial_match = None
        for p_name in all_player_names_list:
            stored_norm = normalize_player_name(p_name)
            if (normalized_search in stored_norm or stored_norm in normalized_search) \
                    and len(normalized_search) > 3:
                partial_match = p_name
                break

        if partial_match:
            fuzzy_matched.append({
                "prop": prop,
                "matched_name": partial_match,
                "match_type": "partial",
                "suggestion": f"Did you mean '{partial_match}'?",
            })
            continue

        # --- No match: find closest suggestion via simple edit distance ---
        suggestion = _find_closest_name(raw_name, all_player_names_list)
        unmatched.append({
            "prop": prop,
            "suggestion": suggestion,
        })

    total = len(matched) + len(fuzzy_matched) + len(unmatched)

    # Post-process matched/fuzzy_matched to flag any OUT/injured players.
    # Load injury status once for the whole batch.
    # NOTE: These status sets mirror INACTIVE_INJURY_STATUSES and
    # GTD_INJURY_STATUSES defined in data/nba_data_service.py.
    # If those constants change, update these checks accordingly.
    _UNAVAILABLE = frozenset({"Out", "Doubtful", "Questionable", "Injured Reserve"})
    _GTD = frozenset({"GTD", "Day-to-Day"})
    injury_map = load_injury_status()
    if injury_map:
        for item in matched + fuzzy_matched:
            matched_name = item.get("matched_name", "")
            status_info = get_player_status(matched_name, injury_map)
            player_status = status_info.get("status", "Active")
            item["player_status"] = player_status
            if player_status in _UNAVAILABLE:
                note = status_info.get("injury_note", "")
                item["out_warning"] = (
                    f"⛔ {matched_name} is {player_status}"
                    + (f" — {note}" if note else "")
                    + " — remove this prop"
                )
            elif player_status in _GTD:
                note = status_info.get("injury_note", "")
                item["status_warning"] = (
                    f"⚠️ {matched_name} is {player_status}"
                    + (f" — {note}" if note else "")
                )

    return {
        "matched": matched,
        "fuzzy_matched": fuzzy_matched,
        "unmatched": unmatched,
        "total": total,
        "matched_count": len(matched) + len(fuzzy_matched),
    }


def _find_closest_name(search_name, candidates_list, max_results=1):
    """
    Find the closest player name using simple edit-distance scoring.

    Implements a lightweight similarity metric without external libraries:
    - Letter overlap ratio (Dice coefficient)

    Args:
        search_name (str): The name to search for
        candidates_list (list of str): All known player names
        max_results (int): How many candidates to return (default 1)

    Returns:
        str or None: Best matching name, or None if list is empty
    """
    if not candidates_list:
        return None

    search_norm = normalize_player_name(search_name)
    if not search_norm:
        return None

    def _dice_similarity(a, b):
        """Dice coefficient: 2 * |bigrams(a) ∩ bigrams(b)| / (|bigrams(a)| + |bigrams(b)|)

        Handles single-character strings by treating the character itself as the bigram.
        """
        if not a or not b:
            return 0.0
        # Exact match short-circuit
        if a == b:
            return 1.0
        # For very short strings (len 1), use character set overlap
        if len(a) == 1 or len(b) == 1:
            return 1.0 if a[0] == b[0] else 0.0
        bigrams_a = {a[i:i+2] for i in range(len(a) - 1)}
        bigrams_b = {b[i:i+2] for i in range(len(b) - 1)}
        intersection = bigrams_a & bigrams_b
        total = len(bigrams_a) + len(bigrams_b)
        return 2.0 * len(intersection) / total if total > 0 else 0.0

    scored = []
    for name in candidates_list:
        norm = normalize_player_name(name)
        score = _dice_similarity(search_norm, norm)
        scored.append((score, name))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored or scored[0][0] < 0.3:
        return None
    return scored[0][1]

# ============================================================
# END SECTION: Player Name Normalization & Fuzzy Matching
# ============================================================


def get_all_player_names(players_list):
    """
    Get a sorted list of all player names.

    Args:
        players_list (list of dict): Loaded player data

    Returns:
        list of str: Sorted player names

    Example:
        names = get_all_player_names(players)
        # → ['Anthony Davis', 'Bam Adebayo', ...]
    """
    # Extract the 'name' field from each player dictionary
    # BEGINNER NOTE: List comprehension = compact way to build a list
    names = [player.get("name", "") for player in players_list if player.get("name")]
    return sorted(names)  # Sort alphabetically


def get_all_team_abbreviations(teams_list):
    """
    Get all 30 NBA team abbreviations.

    Args:
        teams_list (list of dict): Loaded teams data

    Returns:
        list of str: Team abbreviations like ['ATL', 'BOS', ...]
    """
    abbreviations = [
        team.get("abbreviation", "") for team in teams_list
        if team.get("abbreviation")
    ]
    return sorted(abbreviations)


def get_team_by_abbreviation(teams_list, abbreviation):
    """
    Find a team by its abbreviation (e.g., 'LAL', 'BOS').

    Args:
        teams_list (list of dict): Loaded teams data
        abbreviation (str): 3-letter team code

    Returns:
        dict or None: Team data, or None if not found
    """
    for team in teams_list:
        if team.get("abbreviation", "").upper() == abbreviation.upper():
            return team
    return None


def find_players_by_team(players_list, team_abbrev):
    """
    Return all players on a given team.

    Args:
        players_list (list of dict): Loaded player data
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        list of dict: All players on that team, sorted by points avg (desc)
    """
    abbrev_upper = team_abbrev.upper().strip()
    matches = [p for p in players_list if p.get("team", "").upper() == abbrev_upper]
    # Sort by points average descending (stars first)
    try:
        matches.sort(key=lambda p: float(p.get("points_avg", 0) or 0), reverse=True)
    except Exception as _exc:
        _logger.warning(f"[DataManager] Unexpected error: {_exc}")
    return matches


def get_todays_active_players(players_list, todays_games):
    """
    Return only players whose team is playing today and who are not
    flagged as injured/inactive by the saved injury status data.

    Args:
        players_list (list of dict): Loaded player data
        todays_games (list of dict): Tonight's games (from session state)

    Returns:
        list of dict: Players on teams playing today who are available
    """
    if not todays_games:
        return players_list  # Fall back to all players if no games set

    # Build set of teams playing today
    playing_teams = set()
    for game in todays_games:
        playing_teams.add(game.get("home_team", "").upper())
        playing_teams.add(game.get("away_team", "").upper())
    playing_teams.discard("")

    # Step 1: filter by team membership
    on_tonight = [p for p in players_list if p.get("team", "").upper() in playing_teams]

    # Step 2: apply injury filtering using saved status (best-effort)
    try:
        from data.roster_engine import EXCLUDE_STATUSES as _EXCL
        injury_map = load_injury_status()
        if injury_map:
            def _is_available(p):
                key = p.get("player_name", "").lower().strip()
                entry = injury_map.get(key, {})
                return entry.get("status", "Active") not in _EXCL
            return [p for p in on_tonight if _is_available(p)]
    except Exception as exc:
        _logger.debug("get_active_players_tonight: injury filter failed — %s", exc)

    return on_tonight


def get_player_status(player_name, status_map):
    """
    Look up a player's injury/availability status from a status map.

    If ``status_map`` is empty or None, the function automatically tries
    to load the persisted status from INJURY_STATUS_JSON_PATH so callers
    don't need to manage the file path themselves.

    Args:
        player_name (str): Player name to look up
        status_map (dict): Map from normalize_player_name -> status_dict
                           (as returned by RosterEngine.get_injury_report() via
                           get_todays_players).
                           Pass an empty dict or None to auto-load from disk.

    Returns:
        dict: Status dict with keys:
            'status', 'injury_note', 'games_missed', 'return_date',
            'last_game_date', 'gp_ratio'
            — plus optional Layer 5 fields when available:
            'injury' (specific body part/reason),
            'source' (which data source provided the entry),
            'comment' (additional notes from the official injury report).
            Returns default "Active" status if not found.
    """
    _default = {
        "status": "Active",
        "injury_note": "",
        "games_missed": 0,
        "return_date": "",
        "last_game_date": "",
        "gp_ratio": 1.0,
        "injury": "",
        "source": "",
        "comment": "",
    }

    if not player_name:
        return _default

    # Auto-load from disk when no in-memory map is provided
    if not status_map:
        status_map = load_injury_status()

    if not status_map:
        return _default

    # Try exact lowercase match first
    key = player_name.lower().strip()
    if key in status_map:
        entry = dict(_default)
        entry.update(status_map[key])
        return entry

    # Try normalized name match
    normalized = normalize_player_name(player_name)
    if normalized in status_map:
        entry = dict(_default)
        entry.update(status_map[normalized])
        return entry

    # Default to Active if not found
    return _default


def get_status_badge_html(status):
    """
    Return an HTML badge string for a player's injury/availability status.

    Args:
        status (str): Player status string (e.g., 'Active', 'Out', 'GTD', etc.)

    Returns:
        str: HTML span element with colored badge for the status.
    """
    badges = {
        "Active":         '<span style="background:#00ff88;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟢 Active</span>',
        "Probable":       '<span style="background:#00cc66;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟢 Probable</span>',
        "Questionable":   '<span style="background:#ffd700;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟡 Questionable</span>',
        "GTD":            '<span style="background:#ffd700;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟡 GTD</span>',
        "Day-to-Day":     '<span style="background:#ffa500;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟡 Day-to-Day</span>',
        "Doubtful":       '<span style="background:#ff6600;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟠 Doubtful</span>',
        "Out":            '<span style="background:#ff3366;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🔴 Out</span>',
        "Injured Reserve":'<span style="background:#cc0033;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🔴 IR</span>',
    }
    return badges.get(status, '<span style="background:#8b949e;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">⚪ Unknown</span>')


def get_source_attribution_html(source):
    """
    Return a small HTML badge showing which data source provided an
    injury/availability entry (e.g. "Source: Rotowire").

    Args:
        source (str): Data source identifier, e.g. "RotoWire", "NBA.com",
                      "NBA.com+RotoWire", "espn", "nba_api".

    Returns:
        str: HTML span element with source badge, or empty string if source
             is blank.
    """
    if not source:
        return ""

    source_styles = {
        "rotowire":         ("#e8a900", "#000", "RotoWire"),
        "rotoWire":         ("#e8a900", "#000", "RotoWire"),
        "nba.com":          ("#006bb6", "#fff", "NBA.com"),
        "nba_official":     ("#006bb6", "#fff", "NBA.com"),
        "nba.com+rotowire": ("#006bb6", "#fff", "NBA.com+RotoWire"),
        "espn":             ("#c8102e", "#fff", "ESPN"),
        "espn+rotowire":    ("#c8102e", "#fff", "ESPN+RotoWire"),
        "nba_api":          ("#17408b", "#fff", "nba_api"),
    }

    key = source.lower().strip()
    bg, fg, label = source_styles.get(key, ("#555", "#fff", source))
    return (
        f'<span style="background:{bg};color:{fg};padding:1px 6px;'
        f'border-radius:4px;font-size:0.68rem;font-weight:600;'
        f'vertical-align:middle;">Source: {label}</span>'
    )


def enrich_prop_with_player_data(prop, players_list):
    """
    Add player season averages and team info to a prop dictionary.

    Looks up the player in the players list and adds season stats
    as extra fields on the prop dict for display purposes.

    Args:
        prop (dict): A prop dict with at least 'player_name'
        players_list (list of dict): Loaded player data

    Returns:
        dict: The prop dict with added player stats (non-destructive copy)
    """
    enriched = dict(prop)  # Copy so we don't mutate the original

    player = find_player_by_name(players_list, prop.get("player_name", ""))
    if player:
        enriched["player_team"] = player.get("team", prop.get("team", ""))
        enriched["player_position"] = player.get("position", "")
        enriched["season_pts_avg"] = float(player.get("points_avg", 0) or 0)
        enriched["season_reb_avg"] = float(player.get("rebounds_avg", 0) or 0)
        enriched["season_ast_avg"] = float(player.get("assists_avg", 0) or 0)
        enriched["season_threes_avg"] = float(player.get("threes_avg", 0) or 0)
        enriched["season_stl_avg"] = float(player.get("steals_avg", 0) or 0)
        enriched["season_blk_avg"] = float(player.get("blocks_avg", 0) or 0)
        enriched["season_tov_avg"] = float(player.get("turnovers_avg", 0) or 0)
        enriched["season_minutes_avg"] = float(player.get("minutes_avg", 0) or 0)
        enriched["season_ftm_avg"] = float(player.get("ftm_avg", 0) or 0)
        enriched["season_fga_avg"] = float(player.get("fga_avg", 0) or 0)
        enriched["season_fgm_avg"] = float(player.get("fgm_avg", 0) or 0)
        enriched["season_fta_avg"] = float(player.get("fta_avg", 0) or 0)
        enriched["season_oreb_avg"] = float(player.get("offensive_rebounds_avg", 0) or 0)
        enriched["season_dreb_avg"] = float(player.get("defensive_rebounds_avg", 0) or 0)
        enriched["season_pf_avg"] = float(player.get("personal_fouls_avg", 0) or 0)

        # Calculate how the prop line compares to the season average
        stat_type = prop.get("stat_type", "").lower()
        stat_avg_map = {
            "points": enriched["season_pts_avg"],
            "rebounds": enriched["season_reb_avg"],
            "assists": enriched["season_ast_avg"],
            "threes": enriched["season_threes_avg"],
            "steals": enriched["season_stl_avg"],
            "blocks": enriched["season_blk_avg"],
            "turnovers": enriched["season_tov_avg"],
            "minutes": enriched["season_minutes_avg"],
            "ftm": enriched["season_ftm_avg"],
            "fga": enriched["season_fga_avg"],
            "fgm": enriched["season_fgm_avg"],
            "fta": enriched["season_fta_avg"],
            "offensive_rebounds": enriched["season_oreb_avg"],
            "defensive_rebounds": enriched["season_dreb_avg"],
            "personal_fouls": enriched["season_pf_avg"],
        }
        # Compute combo-stat season averages from their components
        _pts = enriched["season_pts_avg"]
        _reb = enriched["season_reb_avg"]
        _ast = enriched["season_ast_avg"]
        _blk = enriched["season_blk_avg"]
        _stl = enriched["season_stl_avg"]
        _combo_avg_map = {
            "points_rebounds": _pts + _reb,
            "points_assists": _pts + _ast,
            "rebounds_assists": _reb + _ast,
            "points_rebounds_assists": _pts + _reb + _ast,
            "blocks_steals": _blk + _stl,
        }
        stat_avg_map.update(_combo_avg_map)
        season_avg = stat_avg_map.get(stat_type, 0)
        prop_line = float(prop.get("line", 0) or 0)

        if season_avg > 0 and prop_line > 0:
            diff_pct = round((prop_line - season_avg) / season_avg * 100, 1)
            enriched["line_vs_avg_pct"] = diff_pct  # + means line is higher than avg
        else:
            enriched["line_vs_avg_pct"] = 0.0

    return enriched


def enrich_props_batch(props_list: list, players_list: list) -> list:
    """
    Vectorized batch enrichment of all props with player season stats.

    Performance profile vs. calling enrich_prop_with_player_data() in a loop:
    - Index build: O(n) once per batch, not O(n) × p times (p = prop count).
    - Stat map build: O(1) per unique player; players with multiple props reuse
      the memoised result — saves ~20 float() calls per duplicate player entry.
    - Overall: O(p + n) instead of O(p × n) for the index scan hot path.
    - Typical saving on a 600-prop NBA slate: ~3–5× fewer object allocations.

    Args:
        props_list: Props to enrich (each needs 'player_name', 'stat_type', 'line').
        players_list: Loaded player data from load_players_data().

    Returns:
        List of enriched prop dicts (non-destructive copies of each input prop).
    """
    if not props_list:
        return []
    if not players_list:
        # No player data — return shallow copies with line_vs_avg_pct = 0
        return [{**p, "line_vs_avg_pct": 0.0} for p in props_list]

    # ── Ensure the shared player index is warm for this players_list ──────────
    # _build_player_index() is O(n); it is cached by list identity so repeated
    # calls within the same Streamlit run are free.
    list_id = id(players_list)
    with _player_index_lock:
        if _player_index_cache["list_id"] != list_id:
            _player_index_cache["index"] = _build_player_index(players_list)
            _player_index_cache["list_id"] = list_id
    lower_index, alias_index, normalized_index = _player_index_cache["index"]

    # ── Per-batch player stats memo ───────────────────────────────────────────
    # Keyed by lowercased player name; populated lazily on first encounter.
    # Players with many props (e.g. stars with 4–5 stat types) only pay the
    # stats-computation cost once per batch call rather than once per prop.
    _memo: dict = {}  # name_key → (fields_dict, stat_avg_map)

    def _build_stats(player: dict) -> tuple:
        key = player.get("name", "").lower().strip()
        if key in _memo:
            return _memo[key]

        # Extract all numeric averages in a single pass — avoids repeated
        # dict.get() calls in the inner loop below.
        pts  = float(player.get("points_avg",              0) or 0)
        reb  = float(player.get("rebounds_avg",            0) or 0)
        ast  = float(player.get("assists_avg",             0) or 0)
        stl  = float(player.get("steals_avg",              0) or 0)
        blk  = float(player.get("blocks_avg",              0) or 0)
        tov  = float(player.get("turnovers_avg",           0) or 0)
        mins = float(player.get("minutes_avg",             0) or 0)
        ftm  = float(player.get("ftm_avg",                 0) or 0)
        fg3  = float(player.get("threes_avg",              0) or 0)
        fga  = float(player.get("fga_avg",                 0) or 0)
        fgm  = float(player.get("fgm_avg",                 0) or 0)
        fta  = float(player.get("fta_avg",                 0) or 0)
        oreb = float(player.get("offensive_rebounds_avg",  0) or 0)
        dreb = float(player.get("defensive_rebounds_avg",  0) or 0)
        pf   = float(player.get("personal_fouls_avg",      0) or 0)

        # Stat-type → season-average lookup table (built once per player).
        # Combo stats are derived from their components — no extra DB columns needed.
        stat_avg_map = {
            "points":                    pts,
            "rebounds":                  reb,
            "assists":                   ast,
            "threes":                    fg3,
            "steals":                    stl,
            "blocks":                    blk,
            "turnovers":                 tov,
            "minutes":                   mins,
            "ftm":                       ftm,
            "fga":                       fga,
            "fgm":                       fgm,
            "fta":                       fta,
            "offensive_rebounds":        oreb,
            "defensive_rebounds":        dreb,
            "personal_fouls":            pf,
            # Combo stats — derived from components, not separate DB columns
            "points_rebounds":           pts + reb,
            "points_assists":            pts + ast,
            "rebounds_assists":          reb + ast,
            "points_rebounds_assists":   pts + reb + ast,
            "blocks_steals":             blk + stl,
        }

        # Fields to merge directly onto the enriched prop dict
        fields = {
            "player_team":        player.get("team", ""),
            "player_position":    player.get("position", ""),
            "season_pts_avg":     pts,
            "season_reb_avg":     reb,
            "season_ast_avg":     ast,
            "season_threes_avg":  fg3,
            "season_stl_avg":     stl,
            "season_blk_avg":     blk,
            "season_tov_avg":     tov,
            "season_minutes_avg": mins,
            "season_ftm_avg":     ftm,
            "season_fga_avg":     fga,
            "season_fgm_avg":     fgm,
            "season_fta_avg":     fta,
            "season_oreb_avg":    oreb,
            "season_dreb_avg":    dreb,
            "season_pf_avg":      pf,
        }
        _memo[key] = (fields, stat_avg_map)
        return _memo[key]

    # ── Main enrichment pass ──────────────────────────────────────────────────
    results = []
    for prop in props_list:
        enriched = dict(prop)  # non-destructive shallow copy

        raw_name = prop.get("player_name", "")
        search_lower = raw_name.lower().strip()

        # O(1) lookup: mirrors passes 1-3 of find_player_by_name_fuzzy.
        # Pass 4 (substring scan) is deliberately skipped here for performance;
        # near-misses fall back to line_vs_avg_pct = 0 — the quality gate will
        # discard low-minutes players anyway.
        player = (
            lower_index.get(search_lower)
            or alias_index.get(search_lower)
            or normalized_index.get(normalize_player_name(raw_name))
        )

        if player:
            fields, stat_avg_map = _build_stats(player)
            enriched.update(fields)

            stat_type   = str(prop.get("stat_type", "")).lower()
            season_avg  = float(stat_avg_map.get(stat_type, 0) or 0)
            prop_line   = float(prop.get("line", 0) or 0)

            if season_avg > 0 and prop_line > 0:
                # Percentage deviation of the sportsbook line from season average.
                # Negative value → line is BELOW average → OVER opportunity.
                enriched["line_vs_avg_pct"] = round(
                    (prop_line - season_avg) / season_avg * 100, 1
                )
            else:
                enriched["line_vs_avg_pct"] = 0.0
        else:
            enriched["line_vs_avg_pct"] = 0.0

        results.append(enriched)

    return results


# ============================================================
# END SECTION: Player Lookup Functions
# ============================================================


# ============================================================
# SECTION: Props Management
# ============================================================

def save_props_to_session(props_list, session_state):
    """
    Save a list of props to Streamlit's session state.

    Streamlit session state persists data between page interactions.
    This lets us keep the prop list as the user navigates pages.

    Args:
        props_list (list of dict): The props to save
        session_state: Streamlit's st.session_state object
    """
    # Store the list under a known key in session state
    session_state["current_props"] = props_list


def load_props_from_session(session_state):
    """
    Load props from Streamlit's session state.

    Checks keys in priority order:
      1. ``current_props``  — user-entered or platform-filtered props
      2. ``platform_props`` — live-retrieved platform props (fallback)
      3. ``props.csv``      — on-disk fallback (empty on fresh installs)

    Args:
        session_state: Streamlit's st.session_state object

    Returns:
        list of dict: Current props (entered, platform-retrieved, or disk)
    """
    # 1. Check user/filtered props
    if session_state.get("current_props"):
        return session_state["current_props"]

    # 2. Fall back to live-retrieved platform props saved by Live Games /
    #    Smart NBA Data pages so Neural Analysis always finds real data.
    if session_state.get("platform_props"):
        return session_state["platform_props"]

    # 3. Last resort — on-disk props.csv (empty list on fresh installs)
    return load_props_data()


def generate_props_for_todays_players(players_data, todays_games, platforms=None):
    """
    Deprecated: Synthetic prop generation from season averages has been removed.

    This function previously auto-generated prop entries using season averages
    as estimated lines. It now returns an empty list immediately. Use the
    platform prop service (data/sportsbook_service.py) to load real live lines.

    Args:
        players_data: Unused.
        todays_games: Unused.
        platforms: Unused.

    Returns:
        list: Always an empty list.
    """
    warnings.warn(
        "generate_props_for_todays_players() is deprecated and returns []. "
        "Use data.sportsbook_service.get_all_sportsbook_props() for real live lines.",
        DeprecationWarning,
        stacklevel=2,
    )
    return []


def filter_props_to_platform_players(
    generated_props: list,
    platform_props: list,
) -> list:
    """
    Filter auto-generated props to only include players that appear in
    real platform data (sportsbook platforms).

    Players whose name matches one in platform_props will have their
    generated props returned.  Players not found on any platform are
    dropped entirely — we never want synthetic props for players who
    are not active on a betting app today.

    Args:
        generated_props: List of auto-generated prop dicts (may be synthetic).
        platform_props: List of real platform prop dicts retrieved from APIs.

    Returns:
        List of props limited to platform-present players. If platform_props
        is empty or None, returns generated_props unchanged (graceful fallback).
    """
    if not platform_props:
        return generated_props

    _logger_filter = _logger

    # Build a set of normalised player names present on any platform
    platform_player_names: set = set()
    for p in platform_props:
        raw_name = (p.get("player_name") or "").strip().lower()
        if raw_name:
            platform_player_names.add(raw_name)

    if not platform_player_names:
        return generated_props

    filtered = []
    dropped_names: set = set()
    for prop in generated_props:
        name = (prop.get("player_name") or "").strip()
        if name.lower() in platform_player_names:
            filtered.append(prop)
        else:
            dropped_names.add(name)

    if dropped_names:
        _logger_filter.info(
            f"[DataManager] Filtered out {len(dropped_names)} players not on any betting platform: "
            + ", ".join(sorted(dropped_names)[:10])
            + (" ..." if len(dropped_names) > 10 else "")
        )

    return filtered


def parse_props_from_csv_text(csv_text):
    """
    Parse prop lines from CSV text (uploaded by user).

    Handles files uploaded via Streamlit's file uploader.
    Expected columns: player_name, team, stat_type, line, platform

    Args:
        csv_text (str): Raw CSV text content

    Returns:
        tuple: (list of valid prop dicts, list of error messages)

    Example:
        text = "LeBron James,LAL,points,24.5,PrizePicks"
        props, errors = parse_props_from_csv_text(text)
    """
    parsed_props = []   # Successfully parsed props
    error_messages = []  # Any parsing errors

    # Required columns that must be present
    required_columns = {"player_name", "stat_type", "line", "platform"}

    try:
        # Use csv.DictReader to parse the text
        # io.StringIO lets us treat a string as a file
        import io
        reader = csv.DictReader(io.StringIO(csv_text))

        for row_number, row in enumerate(reader, start=2):  # Start at 2 (row 1 = header)
            # Check that required columns are present
            row_lower = {k.lower().strip(): v.strip() for k, v in row.items()}

            missing_columns = required_columns - set(row_lower.keys())
            if missing_columns:
                error_messages.append(
                    f"Row {row_number}: Missing columns: {missing_columns}"
                )
                continue

            # Validate the line value is a number
            try:
                line_value = float(row_lower["line"])
            except ValueError:
                error_messages.append(
                    f"Row {row_number}: 'line' must be a number, got '{row_lower['line']}'"
                )
                continue

            # Build a clean prop dictionary
            prop = {
                "player_name": row_lower.get("player_name", ""),
                "team": row_lower.get("team", ""),
                "stat_type": row_lower.get("stat_type", "points").lower(),
                "line": line_value,
                "platform": row_lower.get("platform", "PrizePicks"),
                "game_date": row_lower.get("game_date", ""),
            }
            parsed_props.append(prop)

    except Exception as error:
        error_messages.append(f"CSV parsing error: {error}")

    return parsed_props, error_messages


def get_csv_template():
    """
    Return a CSV template string for users to download.

    Returns:
        str: CSV content with headers and one example row
    """
    # Template with headers and one example row
    template_lines = [
        "player_name,team,stat_type,line,platform,game_date",
        "LeBron James,LAL,points,24.5,PrizePicks,2026-03-05",
        "Stephen Curry,GSW,threes,3.5,DraftKings Pick6,2026-03-05",
    ]
    return "\n".join(template_lines)

# ============================================================
# END SECTION: Props Management
# ============================================================


# ============================================================
# SECTION: Platform Props — Save / Load helpers
# These functions save and load live props retrieved from betting
# platforms (sportsbook platforms) to/from both
# session state and an optional CSV file on disk.
# ============================================================

# Path for saving live platform-retrieved props (separate from user-entered props)
LIVE_PROPS_CSV_PATH = DATA_DIRECTORY / "live_props.csv"

# CSV columns for platform props
_PLATFORM_PROPS_COLUMNS = [
    "player_name", "team", "stat_type", "line", "platform", "game_date", "retrieved_at",
    "line_category", "standard_line",
]


def save_platform_props_to_session(props_list, session_state):
    """
    Save platform-retrieved props to Streamlit session state.

    These are separate from the user-entered "current_props" so that
    platform-retrieved data can be used for cross-platform comparison
    without overwriting manually entered props.

    Args:
        props_list (list[dict]): Props from get_all_sportsbook_props().
        session_state: Streamlit's st.session_state object.
    """
    session_state["platform_props"] = props_list


def load_platform_props_from_session(session_state):
    """
    Load platform-retrieved props from Streamlit session state.

    Args:
        session_state: Streamlit's st.session_state object.

    Returns:
        list[dict]: Previously retrieved platform props, or [].
    """
    return session_state.get("platform_props", [])


def save_platform_props_to_csv(props_list, file_path=None):
    """
    Save platform-retrieved props to a CSV file on disk.

    Overwrites the existing file each time. This is intentional —
    platform props are always "today's live data", so old data
    should be replaced.

    Args:
        props_list (list[dict]): Props from get_all_sportsbook_props().
        file_path (Path, optional): Where to save. Defaults to
            data/live_props.csv.

    Returns:
        bool: True if saved successfully, False on error.
    """
    if file_path is None:
        file_path = LIVE_PROPS_CSV_PATH

    if not props_list:
        return False  # Nothing to save

    try:
        with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=_PLATFORM_PROPS_COLUMNS,
                extrasaction="ignore",  # Ignore extra keys in prop dicts
            )
            writer.writeheader()
            writer.writerows(props_list)
        # Bump the shared data-version stamp so running Streamlit sessions
        # detect fresh props and clear their stale session-state cache.
        try:
            from tracking.database import _bump_data_version as _bv
            import datetime as _dt_bv
            _bv(_dt_bv.date.today().isoformat())
        except Exception:
            pass
        return True
    except Exception as error:
        _logger.warning("Could not save platform props to CSV: %s", error)
        return False


def load_platform_props_from_csv(file_path=None):
    """
    Load platform-retrieved props from a CSV file on disk.

    Args:
        file_path (Path, optional): Where to read from. Defaults to
            data/live_props.csv.

    Returns:
        list[dict]: Props loaded from file, or [] if file not found.
    """
    if file_path is None:
        file_path = LIVE_PROPS_CSV_PATH

    if not Path(file_path).exists():
        return []  # File not yet created

    return _load_csv_file(file_path)

# ============================================================
# END SECTION: Platform Props — Save / Load helpers
# ============================================================


# ============================================================
# SECTION: Live Data Detection Functions
# Check if live data has been loaded, and when it was last updated.
# ============================================================

def is_using_live_data():
    """
    Check whether the app has retrieved live NBA data from real APIs.

    Looks for the last_updated.json file created by nba_data_service.py.
    If the file exists and has the 'is_live' flag, we're using live data.

    Returns:
        bool: True if live data is loaded, False if no live retrieval has occurred.

    Example:
        if is_using_live_data():
            st.success("Using live data!")
        else:
            st.info("No live data loaded — go to Smart NBA Data to update.")
    """
    # Check if the timestamp file exists
    if not LAST_UPDATED_JSON_PATH.exists():
        return False  # File doesn't exist = no live data has been retrieved

    try:
        # Read the JSON file
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            timestamps = json.load(json_file)  # Parse JSON into dict

        # Check the 'is_live' flag
        # BEGINNER NOTE: .get() returns False if 'is_live' key doesn't exist
        return bool(timestamps.get("is_live", False))

    except Exception as exc:
        _logger.debug("is_using_live_data: check failed — %s", exc)
        return False  # If file is broken, assume no live data


def get_data_last_updated(data_type="players"):
    """
    Get the timestamp when a specific data type was last updated.

    Args:
        data_type (str): Which data to check. One of:
                         'players', 'teams', or 'games'

    Returns:
        str or None: ISO format timestamp string if available, None if never updated.

    Example:
        timestamp = get_data_last_updated("players")
        if timestamp:
            print(f"Players last updated: {timestamp}")
    """
    # Check if the timestamp file exists
    if not LAST_UPDATED_JSON_PATH.exists():
        return None  # Never been updated

    try:
        # Read and parse the JSON file
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            timestamps = json.load(json_file)

        # Return the timestamp for the requested data type
        # Returns None if this data type was never updated
        return timestamps.get(data_type, None)

    except Exception as exc:
        _logger.debug("get_data_last_updated: read failed — %s", exc)
        return None  # If any error, return None


def save_last_updated_timestamp(data_type):
    """
    Save the current time as the last-updated timestamp for a data type.

    This is called by nba_data_service.py after each successful retrieval,
    but can also be called manually if data is updated another way.

    Args:
        data_type (str): Which data was updated, e.g. 'players', 'teams'
    """
    # Load existing timestamps if the file exists
    existing_timestamps = {}  # Start empty

    if LAST_UPDATED_JSON_PATH.exists():
        try:
            with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
                existing_timestamps = json.load(json_file)
        except Exception as exc:
            _logger.debug("save_last_updated_timestamp: read failed — %s", exc)
            existing_timestamps = {}  # If broken, start fresh

    # Set the current time as the timestamp for this data type
    existing_timestamps[data_type] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    existing_timestamps["is_live"] = True  # Mark that live data is loaded

    # Save back to the file
    try:
        with open(LAST_UPDATED_JSON_PATH, "w") as json_file:
            json.dump(existing_timestamps, json_file, indent=2)
    except Exception as error:
        _logger.warning("Could not save timestamp: %s", error)

# ============================================================
# END SECTION: Live Data Detection Functions
# ============================================================


# ============================================================
# SECTION: Cache Management & Data Health
# ============================================================

def clear_all_caches():
    """
    Clear all st.cache_data caches for data loading functions.

    Call this after a successful data retrieval to force fresh reads.
    """
    try:
        load_players_data.clear()
        load_teams_data.clear()
        load_defensive_ratings_data.clear()
        load_props_data.clear()
        load_injury_status.clear()
    except Exception as _exc:
        _logger.warning(f"[DataManager] Unexpected error: {_exc}")


def get_data_health_report():
    """
    Return a summary of the current data health status.

    Checks file existence, row counts, and data freshness.

    Returns:
        dict: {
            'players_count': int,
            'teams_count': int,
            'props_count': int,
            'is_live': bool,
            'last_updated': str or None,
            'days_old': int,
            'is_stale': bool,
            'files_present': dict,
            'warnings': list of str,
        }
    """
    warnings = []

    # Check file existence
    files_present = {
        "players.csv": PLAYERS_CSV_PATH.exists(),
        "teams.csv": TEAMS_CSV_PATH.exists(),
        "props.csv": PROPS_CSV_PATH.exists(),
        "defensive_ratings.csv": DEFENSIVE_RATINGS_CSV_PATH.exists(),
        "last_updated.json": LAST_UPDATED_JSON_PATH.exists(),
    }

    for fname, exists in files_present.items():
        if not exists:
            warnings.append(f"Missing file: {fname}")

    # Row counts
    try:
        players = load_players_data()
        players_count = len(players)
    except Exception as exc:
        _logger.debug("data_health_check: players load failed — %s", exc)
        players_count = 0
        warnings.append("Could not load players.csv")

    try:
        teams = load_teams_data()
        teams_count = len(teams)
    except Exception as exc:
        _logger.debug("data_health_check: teams load failed — %s", exc)
        teams_count = 0
        warnings.append("Could not load teams.csv")

    try:
        props = load_props_data()
        props_count = len(props)
    except Exception as exc:
        _logger.debug("data_health_check: props load failed — %s", exc)
        props_count = 0

    # Freshness
    is_live = is_using_live_data()
    last_updated = get_data_last_updated("players")

    days_old = 0
    is_stale = True
    if last_updated:
        try:
            ts = datetime.datetime.fromisoformat(last_updated)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            # Ensure both sides are tz-aware (UTC) for safe arithmetic
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            age = now_utc - ts
            days_old = age.days
            is_stale = days_old > 3
            if is_stale:
                warnings.append(f"Data is {days_old} day(s) old — consider refreshing")
        except Exception as _exc:
            _logger.warning(f"[DataManager] Unexpected error: {_exc}")

    if players_count == 0:
        warnings.append("No players loaded — run Smart NBA Data to populate")
    if teams_count < 30:
        warnings.append(f"Only {teams_count}/30 teams loaded")

    return {
        "players_count": players_count,
        "teams_count": teams_count,
        "props_count": props_count,
        "is_live": is_live,
        "last_updated": last_updated,
        "days_old": days_old,
        "is_stale": is_stale,
        "files_present": files_present,
        "warnings": warnings,
    }

# ============================================================
# END SECTION: Cache Management & Data Health
# ============================================================
