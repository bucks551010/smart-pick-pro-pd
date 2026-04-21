"""
initial_pull.py
---------------
One-time seed script for the SmartPicksProAI database.

Fetches every player game log for the entire 2025-26 NBA regular season via
the nba_api LeagueGameLog endpoint, cleans and transforms the data with
Pandas, and loads it into the SQLite tables defined in setup_db.py.

Also seeds the Teams table from static data, populates Team_Game_Stats from
team-level game logs, loads Team_Roster / player positions via the
CommonTeamRoster endpoint, and populates advanced analytics tables including
career stats, clutch, hustle, shot chart, tracking, scoring, usage,
matchups, bio, estimated metrics, league dashboards, and league leaders.

Run this script exactly once to establish the historical baseline:
    python initial_pull.py
"""

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import (
    BoxScoreAdvancedV3,
    BoxScoreMatchupsV3,
    BoxScorePlayerTrackV3,
    BoxScoreScoringV3,
    BoxScoreUsageV3,
    CommonTeamRoster,
    LeagueDashPlayerBioStats,
    LeagueDashPlayerClutch,
    LeagueDashPlayerStats,
    LeagueDashTeamClutch,
    LeagueDashTeamStats,
    LeagueGameLog,
    LeagueHustleStatsPlayer,
    LeagueHustleStatsTeam,
    LeagueLeaders,
    LeagueStandingsV3,
    PlayerCareerStats,
    PlayerEstimatedMetrics,
    ShotChartDetail,
    TeamEstimatedMetrics,
)
from nba_api.stats.static import teams as static_teams

from . import setup_db
from .cbs_injuries import sync_cbs_injuries
from .rotowire_injuries import sync_rotowire_injuries
from .utils import get_new_rows, parse_matchup_abbreviations, upsert_dataframe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = setup_db.DB_PATH
SEASON = "2025-26"

# When True, skip all data-pull sections that come after Player_Career_Stats.
# This includes shot-chart fetches and per-game box-score loops (advanced,
# scoring, usage, tracking, matchups).
# Set to False when the app is upgraded to use this data.
SKIP_EXTENDED_PULLS = True

# Mapping from NBA API column names to Player_Game_Logs DB column names.
STAT_COLS_MAP = {
    "PLAYER_ID": "player_id",
    "GAME_ID":   "game_id",
    "WL":        "wl",
    "MIN":       "min",
    "PTS":       "pts",
    "REB":       "reb",
    "AST":       "ast",
    "STL":       "stl",
    "BLK":       "blk",
    "TOV":       "tov",
    "FGM":       "fgm",
    "FGA":       "fga",
    "FG_PCT":    "fg_pct",
    "FG3M":      "fg3m",
    "FG3A":      "fg3a",
    "FG3_PCT":   "fg3_pct",
    "FTM":       "ftm",
    "FTA":       "fta",
    "FT_PCT":    "ft_pct",
    "OREB":      "oreb",
    "DREB":      "dreb",
    "PF":        "pf",
    "PLUS_MINUS": "plus_minus",
}

# Integer stat columns (filled with 0 for DNP players).
_INT_STAT_COLS = [
    "pts", "reb", "ast", "stl", "blk", "tov",
    "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
    "oreb", "dreb", "pf",
]

# Float/percentage stat columns (filled with 0.0 for DNP players).
_FLOAT_STAT_COLS = ["fg_pct", "fg3_pct", "ft_pct", "plus_minus"]

# Conference and division lookup keyed by team abbreviation.
_TEAM_CONFERENCE_DIVISION: dict[str, tuple[str, str]] = {
    "ATL": ("East", "Southeast"), "BOS": ("East", "Atlantic"),
    "BKN": ("East", "Atlantic"),  "CHA": ("East", "Southeast"),
    "CHI": ("East", "Central"),   "CLE": ("East", "Central"),
    "DAL": ("West", "Southwest"), "DEN": ("West", "Northwest"),
    "DET": ("East", "Central"),   "GSW": ("West", "Pacific"),
    "HOU": ("West", "Southwest"), "IND": ("East", "Central"),
    "LAC": ("West", "Pacific"),   "LAL": ("West", "Pacific"),
    "MEM": ("West", "Southwest"), "MIA": ("East", "Southeast"),
    "MIL": ("East", "Central"),   "MIN": ("West", "Northwest"),
    "NOP": ("West", "Southwest"), "NYK": ("East", "Atlantic"),
    "OKC": ("West", "Northwest"), "ORL": ("East", "Southeast"),
    "PHI": ("East", "Atlantic"),  "PHX": ("West", "Pacific"),
    "POR": ("West", "Northwest"), "SAC": ("West", "Pacific"),
    "SAS": ("West", "Southwest"), "TOR": ("East", "Atlantic"),
    "UTA": ("West", "Northwest"), "WAS": ("East", "Southeast"),
}


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_MAX_RETRIES = 5
_MAX_RETRIES_PER_PLAYER = 3          # Retries for per-player endpoints.
_BULK_ENDPOINT_TIMEOUT = 120         # Seconds for bulk endpoints (LeagueGameLog etc.).
_SEASON_DASHBOARD_TIMEOUT = 60       # Seconds for season-level dashboard endpoints.
_PER_PLAYER_TIMEOUT = 45             # Seconds for per-player calls.
_CAREER_TIMEOUT = 20                 # Shorter timeout for career-stats (fail fast when throttled).
_PER_GAME_TIMEOUT = 30               # Seconds for per-game box-score calls.
_RATE_LIMIT_DELAY = 0.45             # Seconds between API calls (rate-limit).
_PLAYER_WORKERS = 8                  # Concurrent threads for per-player fetches.
_GAME_WORKERS = 3                    # Concurrent threads for per-game fetches.
_BOX_SCORE_TYPE_WORKERS = 5          # Concurrent threads for box-score types within one game.
_ADAPTIVE_COOLDOWN_DELAY = 5         # Seconds to pause every 100 players (adaptive cooldown).
_POST_ETL_COOLDOWN = 5               # Seconds to pause after full ETL before live API calls.
_MAX_BACKOFF_DELAY = 30              # Cap on exponential back-off delay (seconds).
_LOG_PROGRESS_INTERVAL = 50          # Log a progress line every N items.

# Career-stats-specific tuning.  The bulk fetch for all active players
# (578+) is the heaviest per-player ETL step.  We use conservative
# concurrency and rate-limiting to avoid triggering NBA API throttling.
_CAREER_WORKERS = 3                  # Concurrent threads for career-stats fetches.
_CAREER_RATE_DELAY = 0.75            # Seconds between career-stats API calls.
_CAREER_BATCH_SIZE = 40              # Players per batch.
_CAREER_BATCH_COOLDOWN = 8           # Seconds to pause between batches.
_CAREER_CIRCUIT_THRESHOLD = 15       # Consecutive failures before extended cooldown.
_CAREER_CIRCUIT_COOLDOWN = 30        # Extended cooldown after circuit breaker triggers.

# Thread-safe rate limiter to avoid triggering 429 / throttling.
_rate_lock = threading.Lock()
_last_call_time = 0.0


def _rate_limited_sleep() -> None:
    """Sleep just enough to maintain the global rate limit across threads."""
    global _last_call_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)
        _last_call_time = time.monotonic()


_CALL_WALL_TIMEOUT = 90  # seconds: hard wall-clock timeout per API call attempt


def _call_with_retries(
    api_callable: Callable[[], Any],
    description: str = "API call",
    max_retries: int = _MAX_RETRIES,
) -> Any:
    """Call *api_callable* up to *max_retries* times with exponential backoff.

    Each attempt is run in a ``ThreadPoolExecutor`` so that a hard wall-clock
    timeout (``_CALL_WALL_TIMEOUT``) is enforced even when the underlying
    ``requests`` socket timeout fails to fire (e.g. DNS hang, silent IP block).

    If all attempts fail, the last exception is re-raised so the caller can
    decide whether to abort or skip (``continue``).
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as _pool:
                _fut = _pool.submit(api_callable)
                try:
                    return _fut.result(timeout=_CALL_WALL_TIMEOUT)
                except _FutTimeout:
                    raise TimeoutError(
                        f"{description} exceeded {_CALL_WALL_TIMEOUT}s wall-clock timeout"
                    )
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = min(2 ** attempt, _MAX_BACKOFF_DELAY)
                logger.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %ds …",
                    description, attempt, max_retries, exc, delay,
                )
                time.sleep(delay)
    logger.warning(
        "%s failed after %d attempts.", description, max_retries
    )
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Data Extraction
# ---------------------------------------------------------------------------


def fetch_season_logs(season: str = SEASON) -> pd.DataFrame:
    """Fetch all player game logs for *season* from the NBA API.

    Uses LeagueGameLog with player_or_team_abbreviation='P' to retrieve
    per-player box scores.  The returned DataFrame contains columns::

        PLAYER_ID, PLAYER_NAME, SEASON_ID, TEAM_ID, TEAM_ABBREVIATION,
        TEAM_NAME, GAME_ID, GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG_PCT,
        FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL,
        BLK, TOV, PF, PTS, PLUS_MINUS, VIDEO_AVAILABLE

    Args:
        season: NBA season string, e.g. ``'2025-26'``.

    Returns:
        DataFrame of raw player game logs.
    """
    logger.info("Fetching player game logs for season %s …", season)
    df = _call_with_retries(
        lambda: LeagueGameLog(
            player_or_team_abbreviation="P",
            season=season,
            season_type_all_star="Regular Season",
            timeout=_BULK_ENDPOINT_TIMEOUT,
        ).get_data_frames()[0],
        description="LeagueGameLog(player)",
    )
    logger.info("Retrieved %d rows from the API.", len(df))
    return df


def fetch_team_season_logs(season: str = SEASON) -> pd.DataFrame:
    """Fetch all **team-level** game logs for *season* from the NBA API.

    Uses LeagueGameLog with ``player_or_team_abbreviation='T'`` to retrieve
    per-team box scores.  Returns two rows per game (one for each team).

    The returned DataFrame contains columns::

        SEASON_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GAME_ID,
        GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG_PCT, … PTS, PLUS_MINUS

    Args:
        season: NBA season string, e.g. ``'2025-26'``.

    Returns:
        DataFrame of raw team-level game logs.
    """
    logger.info("Fetching team game logs for season %s …", season)
    _rate_limited_sleep()
    df = _call_with_retries(
        lambda: LeagueGameLog(
            player_or_team_abbreviation="T",
            season=season,
            season_type_all_star="Regular Season",
            timeout=_BULK_ENDPOINT_TIMEOUT,
        ).get_data_frames()[0],
        description="LeagueGameLog(team)",
    )
    logger.info("Retrieved %d team-level rows from the API.", len(df))
    return df


# ---------------------------------------------------------------------------
# Data Transformation
# ---------------------------------------------------------------------------


def build_players_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Extract a de-duplicated Players table from the raw game-log DataFrame.

    Splits PLAYER_NAME (e.g. ``'LeBron James'``) into ``first_name`` and
    ``last_name`` columns.  When a name contains more than two tokens (e.g.
    ``'Trae Young Jr.'``) the first token becomes ``first_name`` and the
    remainder becomes ``last_name``.

    Also captures ``full_name`` and ``team_abbreviation`` from the raw data.
    ``position`` is set to ``None`` and ``is_active`` to ``1`` as placeholders
    (populate separately via CommonPlayerInfo or a roster endpoint).

    Args:
        raw: Raw DataFrame returned by :func:`fetch_season_logs`.

    Returns:
        DataFrame with columns ``player_id``, ``first_name``, ``last_name``,
        ``full_name``, ``team_id``, ``team_abbreviation``, ``position``,
        ``is_active``.
    """
    raw_subset = raw[["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION"]].copy()
    players = raw_subset.drop_duplicates(subset="PLAYER_ID").copy()

    name_parts = players["PLAYER_NAME"].str.split(" ", n=1, expand=True)
    players["first_name"] = name_parts[0].str.strip()
    players["last_name"] = name_parts[1].str.strip() if 1 in name_parts.columns else ""

    players = players.rename(columns={"PLAYER_ID": "player_id", "TEAM_ID": "team_id"})
    players["full_name"] = players["PLAYER_NAME"]
    players["team_abbreviation"] = players["TEAM_ABBREVIATION"]
    players["position"] = None
    players["is_active"] = 1

    players = players[
        ["player_id", "first_name", "last_name", "full_name",
         "team_id", "team_abbreviation", "position", "is_active"]
    ]
    logger.info("Built Players DataFrame: %d unique players.", len(players))
    return players


def build_games_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Extract a de-duplicated Games table from the raw game-log DataFrame.

    Converts GAME_DATE from NBA format (e.g. ``'OCT 22, 2025'``) to ISO
    ``YYYY-MM-DD`` strings.  Parses ``home_abbrev`` and ``away_abbrev`` from
    the MATCHUP string:

    - ``'LAL vs. BOS'`` → home team is the left abbreviation (``LAL``).
    - ``'LAL @ BOS'``   → home team is the right abbreviation (``BOS``).

    ``home_team_id`` and ``away_team_id`` are derived from the MATCHUP and
    TEAM_ID columns in the raw data: a ``vs.`` matchup means the player's
    team is the home team, and an ``@`` matchup means the player's team is
    the away team.

    Args:
        raw: Raw DataFrame returned by :func:`fetch_season_logs`.

    Returns:
        DataFrame with columns ``game_id``, ``game_date``, ``season``,
        ``home_team_id``, ``away_team_id``, ``home_abbrev``, ``away_abbrev``,
        ``matchup``.
    """
    games = raw[["GAME_ID", "GAME_DATE", "MATCHUP"]].copy()
    games = games.drop_duplicates(subset="GAME_ID")

    games["GAME_DATE"] = (
        pd.to_datetime(games["GAME_DATE"], format="mixed", dayfirst=False)
        .dt.strftime("%Y-%m-%d")
    )

    games = games.rename(
        columns={"GAME_ID": "game_id", "GAME_DATE": "game_date", "MATCHUP": "matchup"}
    )

    games["season"] = SEASON

    home_abbrevs, away_abbrevs = zip(
        *games["matchup"].map(parse_matchup_abbreviations)
    ) if not games.empty else ([], [])
    games["home_abbrev"] = list(home_abbrevs)
    games["away_abbrev"] = list(away_abbrevs)

    # Normalise the matchup column to always use the home team's perspective
    # ("{HOME} vs. {AWAY}") so the value is deterministic regardless of which
    # raw row was kept by drop_duplicates above.
    if not games.empty:
        games["matchup"] = games["home_abbrev"] + " vs. " + games["away_abbrev"]

    # Derive home_team_id / away_team_id from the raw per-player rows.
    # A "vs." matchup means the row's TEAM_ID is the home team.
    home_ids = (
        raw.loc[raw["MATCHUP"].str.contains(" vs. ", na=False), ["GAME_ID", "TEAM_ID"]]
        .drop_duplicates("GAME_ID")
        .rename(columns={"GAME_ID": "game_id", "TEAM_ID": "home_team_id"})
    )
    away_ids = (
        raw.loc[raw["MATCHUP"].str.contains(" @ ", na=False), ["GAME_ID", "TEAM_ID"]]
        .drop_duplicates("GAME_ID")
        .rename(columns={"GAME_ID": "game_id", "TEAM_ID": "away_team_id"})
    )
    games = games.merge(home_ids, on="game_id", how="left")
    games = games.merge(away_ids, on="game_id", how="left")

    games = games[
        ["game_id", "game_date", "season", "home_team_id", "away_team_id",
         "home_abbrev", "away_abbrev", "matchup"]
    ]
    logger.info("Built Games DataFrame: %d unique games.", len(games))
    return games


def build_logs_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Extract the Player_Game_Logs table from the raw game-log DataFrame.

    Selects and renames the full set of stat columns defined in
    :data:`STAT_COLS_MAP`.

    **DNP handling:** Players who did not play (0 minutes, null/None stats)
    have their integer stat columns set to ``0``, float/percentage columns set
    to ``0.0``, and ``min`` set to ``'0:00'`` so downstream ML math never
    encounters NaN values.

    Args:
        raw: Raw DataFrame returned by :func:`fetch_season_logs`.

    Returns:
        DataFrame ready for insertion into ``Player_Game_Logs``.
    """
    available_cols = [c for c in STAT_COLS_MAP if c in raw.columns]
    logs = raw[available_cols].copy()
    logs = logs.rename(columns={k: v for k, v in STAT_COLS_MAP.items() if k in available_cols})

    # Deduplicate on the composite PK as a safety net — the NBA API should
    # return exactly one row per player-game, but duplicates have been
    # observed when raw data is merged from multiple partial fetches.
    logs = logs.drop_duplicates(subset=["player_id", "game_id"])

    # --- DNP / inactive edge-case handling ---
    for col in _INT_STAT_COLS:
        if col in logs.columns:
            logs[col] = pd.to_numeric(logs[col], errors="coerce").fillna(0).astype(int)
    for col in _FLOAT_STAT_COLS:
        if col in logs.columns:
            logs[col] = pd.to_numeric(logs[col], errors="coerce").fillna(0.0)
    if "min" in logs.columns:
        logs["min"] = logs["min"].fillna("0:00").replace("", "0:00")

    logger.info("Built Player_Game_Logs DataFrame: %d rows.", len(logs))
    return logs


def build_team_game_stats_df(raw_team: pd.DataFrame) -> pd.DataFrame:
    """Build the Team_Game_Stats table from team-level LeagueGameLog data.

    Each game produces **two rows** (one per participating team).  For each
    row the function determines:

    - ``is_home`` — ``1`` if the team's MATCHUP contains ``' vs. '``.
    - ``opponent_team_id`` — the other team's TEAM_ID in the same game.
    - ``points_allowed`` — the opponent's PTS in the same game.

    Also computes per-game estimates for ``pace_est``, ``ortg_est``, and
    ``drtg_est`` from the available box-score data::

        possessions ≈ FGA + 0.44 × FTA − OREB + TOV
        pace        = 48 × avg(poss, opp_poss) / (team_minutes / 5)
        ortg        = 100 × PTS / poss
        drtg        = 100 × opp_PTS / opp_poss

    Args:
        raw_team: Raw DataFrame returned by :func:`fetch_team_season_logs`.

    Returns:
        DataFrame with columns ``game_id``, ``team_id``, ``opponent_team_id``,
        ``is_home``, ``points_scored``, ``points_allowed``, ``pace_est``,
        ``ortg_est``, ``drtg_est``.
    """
    if raw_team.empty:
        return pd.DataFrame(
            columns=["game_id", "team_id", "opponent_team_id", "is_home",
                     "points_scored", "points_allowed", "pace_est",
                     "ortg_est", "drtg_est"]
        )

    needed = ["GAME_ID", "TEAM_ID", "MATCHUP", "PTS", "FGA", "FTA", "OREB", "TOV", "MIN"]
    df = raw_team[needed].copy()
    df = df.rename(columns={
        "GAME_ID": "game_id",
        "TEAM_ID": "team_id",
        "PTS": "points_scored",
        "FGA": "fga",
        "FTA": "fta",
        "OREB": "oreb",
        "TOV": "tov",
        "MIN": "min_played",
    })
    df["is_home"] = df["MATCHUP"].str.contains(" vs. ", na=False).astype(int)
    df = df.drop(columns=["MATCHUP"])

    # Coerce box-score columns to numeric for the pace calculations.
    for col in ("fga", "fta", "oreb", "tov"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # MIN from team logs can be int (240) or string ("240:00").
    min_raw = df["min_played"].astype(str)
    if min_raw.str.contains(":").any():
        min_raw = min_raw.str.split(":").str[0]
    df["min_played"] = pd.to_numeric(min_raw, errors="coerce").fillna(240)

    # Self-join to find opponent's team_id, PTS, and box-score data.
    opp = df[["game_id", "team_id", "points_scored",
              "fga", "fta", "oreb", "tov", "min_played"]].rename(columns={
        "team_id": "opponent_team_id",
        "points_scored": "points_allowed",
        "fga": "opp_fga",
        "fta": "opp_fta",
        "oreb": "opp_oreb",
        "tov": "opp_tov",
        "min_played": "opp_min",
    })
    merged = df.merge(opp, on="game_id")
    merged = merged[merged["team_id"] != merged["opponent_team_id"]]

    # Possession estimates.
    merged["poss"] = (
        merged["fga"] + 0.44 * merged["fta"] - merged["oreb"] + merged["tov"]
    )
    merged["opp_poss"] = (
        merged["opp_fga"] + 0.44 * merged["opp_fta"]
        - merged["opp_oreb"] + merged["opp_tov"]
    )

    # Guard against division by zero.
    safe_poss = merged["poss"].replace(0, float("nan"))
    safe_opp_poss = merged["opp_poss"].replace(0, float("nan"))
    game_min = (merged["min_played"] / 5).replace(0, float("nan"))

    merged["pace_est"] = (
        48 * (merged["poss"] + merged["opp_poss"]) / 2 / game_min
    ).round(1)
    merged["ortg_est"] = (100 * merged["points_scored"] / safe_poss).round(1)
    merged["drtg_est"] = (100 * merged["points_allowed"] / safe_opp_poss).round(1)

    result = merged[
        ["game_id", "team_id", "opponent_team_id", "is_home",
         "points_scored", "points_allowed", "pace_est", "ortg_est", "drtg_est"]
    ]
    logger.info("Built Team_Game_Stats DataFrame: %d rows.", len(result))
    return result


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


def load_players(players: pd.DataFrame, conn: sqlite3.Connection) -> None:
    """Upsert *players* into the Players table.

    Uses INSERT OR REPLACE so that rows whose ``team_id`` or
    ``team_abbreviation`` has changed (e.g. due to a trade) are updated in
    place rather than silently skipped.

    Args:
        players: DataFrame produced by :func:`build_players_df`.
        conn: Open SQLite connection.
    """
    upsert_dataframe(players, "Players", conn)


def seed_teams_from_api(conn: sqlite3.Connection) -> None:
    """Seed the Teams table from the ``nba_api`` static teams list.

    Uses :func:`nba_api.stats.static.teams.get_teams` to load all 30 NBA
    teams.  Rows whose ``team_id`` already exists in the table are skipped.

    Args:
        conn: Open SQLite connection.
    """
    all_teams = static_teams.get_teams()
    teams = pd.DataFrame(all_teams)
    teams = teams.rename(columns={"id": "team_id", "full_name": "team_name"})

    # Keep only columns that exist in the Teams schema.
    teams = teams[["team_id", "abbreviation", "team_name"]]
    teams["conference"] = teams["abbreviation"].map(
        lambda a: _TEAM_CONFERENCE_DIVISION.get(a, (None, None))[0]
    )
    teams["division"] = teams["abbreviation"].map(
        lambda a: _TEAM_CONFERENCE_DIVISION.get(a, (None, None))[1]
    )
    teams["pace"] = None
    teams["ortg"] = None
    teams["drtg"] = None

    existing = pd.read_sql("SELECT team_id FROM Teams", conn)
    new_rows = teams[~teams["team_id"].isin(existing["team_id"])]
    if new_rows.empty:
        logger.info("Teams table: no new rows to insert.")
        return
    new_rows.to_sql("Teams", conn, if_exists="append", index=False)
    logger.info("Teams table: inserted %d rows from nba_api.", len(new_rows))


def load_games(games: pd.DataFrame, conn: sqlite3.Connection) -> None:
    """Upsert *games* into the Games table, skipping existing rows.

    Args:
        games: DataFrame produced by :func:`build_games_df`.
        conn: Open SQLite connection.
    """
    existing = pd.read_sql("SELECT game_id FROM Games", conn)
    new_rows = games[~games["game_id"].isin(existing["game_id"])]
    if new_rows.empty:
        logger.info("Games table: no new rows to insert.")
        return
    new_rows.to_sql("Games", conn, if_exists="append", index=False)
    logger.info("Games table: inserted %d new rows.", len(new_rows))


def load_logs(logs: pd.DataFrame, conn: sqlite3.Connection) -> None:
    """Append *logs* into Player_Game_Logs, skipping duplicate (player, game) pairs.

    Args:
        logs: DataFrame produced by :func:`build_logs_df`.
        conn: Open SQLite connection.
    """
    existing = pd.read_sql(
        "SELECT player_id, game_id FROM Player_Game_Logs", conn
    )
    new_rows = get_new_rows(logs, existing, on_cols=["player_id", "game_id"])

    if new_rows.empty:
        logger.info("Player_Game_Logs table: no new rows to insert.")
        return
    new_rows.to_sql("Player_Game_Logs", conn, if_exists="append", index=False)
    logger.info("Player_Game_Logs table: inserted %d new rows.", len(new_rows))


def load_team_game_stats(
    stats: pd.DataFrame, conn: sqlite3.Connection
) -> None:
    """Append *stats* into Team_Game_Stats, skipping existing (game, team) pairs.

    Args:
        stats: DataFrame produced by :func:`build_team_game_stats_df`.
        conn: Open SQLite connection.
    """
    if stats.empty:
        logger.info("Team_Game_Stats table: no rows to insert.")
        return
    existing = pd.read_sql(
        "SELECT game_id, team_id FROM Team_Game_Stats", conn
    )
    new_rows = get_new_rows(stats, existing, on_cols=["game_id", "team_id"])

    if new_rows.empty:
        logger.info("Team_Game_Stats table: no new rows to insert.")
        return
    new_rows.to_sql("Team_Game_Stats", conn, if_exists="append", index=False)
    logger.info("Team_Game_Stats table: inserted %d new rows.", len(new_rows))


def populate_game_scores(conn: sqlite3.Connection) -> None:
    """Back-fill ``home_score`` and ``away_score`` in the Games table.

    Uses data already loaded in ``Team_Game_Stats`` to set the scores for
    every game whose ``home_team_id`` and ``away_team_id`` are known and
    whose scores have not yet been populated.

    Args:
        conn: Open SQLite connection.
    """
    updated = conn.execute(
        """
        UPDATE Games SET
            home_score = (
                SELECT tgs.points_scored
                FROM Team_Game_Stats tgs
                WHERE tgs.game_id = Games.game_id
                  AND tgs.team_id = Games.home_team_id
            ),
            away_score = (
                SELECT tgs.points_scored
                FROM Team_Game_Stats tgs
                WHERE tgs.game_id = Games.game_id
                  AND tgs.team_id = Games.away_team_id
            )
        WHERE home_team_id IS NOT NULL
          AND away_team_id IS NOT NULL
          AND home_score IS NULL
        """
    ).rowcount
    if updated:
        logger.info("Games: back-filled scores for %d rows.", updated)
    else:
        logger.info("Games: no scores to back-fill.")


def _parse_height_inches(height_str: str) -> float | None:
    """Convert a height string like ``'6-3'`` to total inches (75.0).

    Returns ``None`` when the string is missing or unparseable.
    """
    if not height_str or not isinstance(height_str, str):
        return None
    try:
        parts = height_str.replace("'", "-").replace('"', "").split("-")
        feet = int(parts[0])
        inches = int(parts[1]) if len(parts) > 1 else 0
        if not (5 <= feet <= 8) or not (0 <= inches <= 11):
            return None
        return float(feet * 12 + inches)
    except (ValueError, IndexError):
        return None


# Height thresholds (in inches) for splitting generic roster positions into
# the standard 5-position model.  Based on typical NBA position height
# distributions: PG averages ~6'2", SG ~6'4", SF ~6'7", PF ~6'9", C ~6'11".
# Cutoffs are set at the midpoint between adjacent position averages.
_PG_SG_CUTOFF = 76.0    # ≤ 6'4" → PG, > 6'4" → SG
_SF_PF_CUTOFF = 80.0    # ≤ 6'8" → SF, > 6'8" → PF
_GUARD_FWD_CUTOFF = 78.0  # Guard-Forward split: ≤ 6'6" → SG, else SF
_FWD_CTR_CUTOFF = 81.0    # Forward-Center split: ≤ 6'9" → PF, else C


def _map_to_five_position(
    generic_pos: str | None, height_inches: float | None
) -> str | None:
    """Map a generic roster position + height to one of PG/SG/SF/PF/C.

    ``generic_pos`` is the raw value from ``CommonTeamRoster.POSITION``
    (e.g. ``'G'``, ``'F'``, ``'C'``, ``'G-F'``, ``'F-C'``).

    If height is unavailable, sensible defaults are used (G→SG, F→SF, C→C).
    """
    if not generic_pos:
        return None
    p = generic_pos.strip().upper()
    h = height_inches

    if p in ("G",):
        if h is not None:
            return "PG" if h <= _PG_SG_CUTOFF else "SG"
        return "SG"  # default guard → SG
    if p in ("F",):
        if h is not None:
            return "SF" if h <= _SF_PF_CUTOFF else "PF"
        return "SF"  # default forward → SF
    if p in ("C",):
        return "C"
    # Compound positions
    if p in ("G-F", "F-G"):
        if h is not None:
            return "SG" if h <= _GUARD_FWD_CUTOFF else "SF"
        return "SF"  # default tweener → SF
    if p in ("F-C", "C-F"):
        if h is not None:
            return "PF" if h <= _FWD_CTR_CUTOFF else "C"
        return "PF"  # default big tweener → PF
    # Already a 5-position value?
    if p in ("PG", "SG", "SF", "PF"):
        return p
    return None


def fetch_and_load_rosters(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch current rosters for all teams and load into Team_Roster.

    Iterates over every team in the Teams table, calls the
    :class:`~nba_api.stats.endpoints.CommonTeamRoster` endpoint for each,
    and inserts new rows into ``Team_Roster``.

    As a side-effect, updates ``Players.position`` for every player found on
    a roster.  Positions are mapped to a **5-position** model
    (PG / SG / SF / PF / C) using the roster position and player height.

    Args:
        conn: Open SQLite connection.
        season: NBA season string, e.g. ``'2025-26'``.
    """
    team_ids = pd.read_sql("SELECT team_id FROM Teams", conn)["team_id"].tolist()
    if not team_ids:
        logger.warning("No teams in DB — cannot fetch rosters.")
        return

    all_roster_rows: list[dict] = []
    position_updates: list[tuple] = []

    def _fetch_roster(tid: int) -> tuple[int, pd.DataFrame | None]:
        """Fetch a single team's roster with rate limiting."""
        try:
            _rate_limited_sleep()
            df = _call_with_retries(
                lambda tid=tid: CommonTeamRoster(
                    team_id=tid, season=season,
                    timeout=_SEASON_DASHBOARD_TIMEOUT,
                ).get_data_frames()[0],
                description=f"CommonTeamRoster(team={tid})",
            )
            return tid, df
        except Exception:
            logger.warning(
                "Failed to fetch roster for team %d after %d attempts — skipping.",
                tid, _MAX_RETRIES,
            )
            return tid, None

    with ThreadPoolExecutor(max_workers=_PLAYER_WORKERS) as executor:
        futures = {executor.submit(_fetch_roster, tid): tid for tid in team_ids}
        for future in as_completed(futures):
            tid, df = future.result()
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                pid = row.get("PLAYER_ID")
                raw_pos = row.get("POSITION", None)
                height_str = row.get("HEIGHT", None)
                if pid is None:
                    continue
                all_roster_rows.append({
                    "team_id": tid,
                    "player_id": int(pid),
                    "effective_start_date": season,
                    "effective_end_date": None,
                    "is_two_way": 0,
                    "is_g_league": 0,
                })
                if raw_pos:
                    h_in = _parse_height_inches(height_str)
                    mapped = _map_to_five_position(raw_pos, h_in)
                    if mapped:
                        position_updates.append((mapped, int(pid)))

    # Load Team_Roster rows.
    if all_roster_rows:
        roster_df = pd.DataFrame(all_roster_rows)
        existing = pd.read_sql(
            "SELECT team_id, player_id, effective_start_date FROM Team_Roster",
            conn,
        )
        if existing.empty:
            new_rows = roster_df
        else:
            merged = roster_df.merge(
                existing,
                on=["team_id", "player_id", "effective_start_date"],
                how="left",
                indicator=True,
            )
            new_rows = roster_df[merged["_merge"] == "left_only"].copy()

        if not new_rows.empty:
            new_rows.to_sql("Team_Roster", conn, if_exists="append", index=False)
            logger.info("Team_Roster: inserted %d rows.", len(new_rows))
        else:
            logger.info("Team_Roster: no new rows to insert.")
    else:
        logger.info("Team_Roster: no roster data retrieved.")

    # Update Players.position where known.
    if position_updates:
        cursor = conn.cursor()
        cursor.executemany(
            "UPDATE Players SET position = ? WHERE player_id = ?",
            position_updates,
        )
        logger.info("Players.position: updated %d rows.", len(position_updates))


def update_team_season_stats(conn: sqlite3.Connection) -> None:
    """Refresh the Teams table ``pace``, ``ortg``, and ``drtg`` columns.

    Computes season-level averages from per-game estimates stored in
    ``Team_Game_Stats`` and writes them back into the ``Teams`` table so that
    the ``/api/teams`` endpoint can serve them directly.

    Args:
        conn: Open SQLite connection.
    """
    updated = conn.execute(
        """
        UPDATE Teams SET
            pace = (
                SELECT ROUND(AVG(tgs.pace_est), 1)
                FROM Team_Game_Stats tgs
                WHERE tgs.team_id = Teams.team_id
                  AND tgs.pace_est IS NOT NULL
            ),
            ortg = (
                SELECT ROUND(AVG(tgs.ortg_est), 1)
                FROM Team_Game_Stats tgs
                WHERE tgs.team_id = Teams.team_id
                  AND tgs.ortg_est IS NOT NULL
            ),
            drtg = (
                SELECT ROUND(AVG(tgs.drtg_est), 1)
                FROM Team_Game_Stats tgs
                WHERE tgs.team_id = Teams.team_id
                  AND tgs.drtg_est IS NOT NULL
            )
        WHERE EXISTS (
            SELECT 1 FROM Team_Game_Stats tgs
            WHERE tgs.team_id = Teams.team_id
        )
        """
    ).rowcount
    if updated:
        logger.info("Teams: refreshed pace/ortg/drtg for %d teams.", updated)
    else:
        logger.info("Teams: no Team_Game_Stats data to aggregate.")


def populate_defense_vs_position(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Compute and store Defense_Vs_Position multipliers from game-log data.

    For each opponent team and player position, this function calculates how
    players at that position perform **against** that team compared to the
    league-wide average for the same position.

    A multiplier **> 1.0** means the team allows *more* than average for that
    stat/position combo (i.e. weaker defense).  A multiplier **< 1.0** means
    the team is *tougher* than average.

    Positions use a **5-position** model (``PG``, ``SG``, ``SF``, ``PF``,
    ``C``).  The value is read directly from ``Players.position`` which is
    populated by :func:`fetch_and_load_rosters`.  Legacy single-character
    values (``G``, ``F``, ``C``) are mapped to a default 5-position value
    as a fallback.

    The opponent for each player-game is inferred from ``Players.team_id``
    compared to ``Games.home_team_id`` / ``away_team_id``.  This is an
    approximation for mid-season trades but is accurate for the vast majority
    of player-games.

    The table is fully refreshed (``DELETE`` + ``INSERT``) for the given
    *season* on each call.

    Args:
        conn: Open SQLite connection.
        season: NBA season string, e.g. ``'2025-26'``.
    """
    query = """
        SELECT
            l.pts, l.reb, l.ast, l.stl, l.blk, l.fg3m,
            CASE
                WHEN p.position IN ('PG','SG','SF','PF','C') THEN p.position
                WHEN UPPER(p.position) LIKE 'G%' THEN 'SG'
                WHEN UPPER(p.position) LIKE 'F%' THEN 'SF'
                WHEN UPPER(p.position) LIKE 'C%' THEN 'C'
                ELSE p.position
            END AS pos,
            CASE
                WHEN p.team_id = g.home_team_id THEN t_away.abbreviation
                WHEN p.team_id = g.away_team_id THEN t_home.abbreviation
            END AS opp_abbrev
        FROM Player_Game_Logs l
        JOIN Players p ON p.player_id = l.player_id
        JOIN Games g ON g.game_id = l.game_id
        LEFT JOIN Teams t_home ON t_home.team_id = g.home_team_id
        LEFT JOIN Teams t_away ON t_away.team_id = g.away_team_id
        WHERE p.position IS NOT NULL
          AND p.position != ''
          AND g.home_team_id IS NOT NULL
          AND g.away_team_id IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        logger.info("Defense_Vs_Position: no data available to compute.")
        return

    # Drop rows where the opponent could not be determined.
    df = df.dropna(subset=["opp_abbrev"])
    if df.empty:
        logger.info("Defense_Vs_Position: no opponent-matchable data.")
        return

    stat_cols = ["pts", "reb", "ast", "stl", "blk", "fg3m"]

    # League-wide averages by position.
    league_avg = df.groupby("pos")[stat_cols].mean()

    # Per-opponent-team per-position averages.
    team_avg = df.groupby(["opp_abbrev", "pos"])[stat_cols].mean()

    # Compute multipliers: team_avg / league_avg for each stat.
    stat_to_mult = {
        "pts": "vs_pts_mult",
        "reb": "vs_reb_mult",
        "ast": "vs_ast_mult",
        "stl": "vs_stl_mult",
        "blk": "vs_blk_mult",
        "fg3m": "vs_3pm_mult",
    }

    rows: list[dict] = []
    for (opp, pos), t_row in team_avg.iterrows():
        if pos not in league_avg.index:
            continue
        l_row = league_avg.loc[pos]
        row: dict = {
            "team_abbreviation": opp,
            "season": season,
            "pos": pos,
        }
        for stat, mult_col in stat_to_mult.items():
            league_val = l_row[stat]
            if league_val > 0:
                row[mult_col] = round(float(t_row[stat]) / float(league_val), 3)
            else:
                row[mult_col] = 1.0
        rows.append(row)

    if not rows:
        logger.info("Defense_Vs_Position: no multipliers computed.")
        return

    result = pd.DataFrame(rows)

    # Full refresh for the given season.
    conn.execute(
        "DELETE FROM Defense_Vs_Position WHERE season = ?", (season,)
    )
    result.to_sql("Defense_Vs_Position", conn, if_exists="append", index=False)
    logger.info("Defense_Vs_Position: inserted %d rows for season %s.", len(result), season)


# ---------------------------------------------------------------------------
# Season-level dashboard ETL pipelines
# ---------------------------------------------------------------------------


def _populate_season_table(
    conn: sqlite3.Connection,
    endpoint_factory: Callable[[], Any],
    col_map: dict[str, str],
    table_name: str,
    season: str = SEASON,
    *,
    description: str = "",
    season_col: str = "season",
    delete_filter: str | None = None,
    include_season: bool = True,
) -> None:
    """Generic helper: fetch one season-level NBA endpoint and load into SQLite.

    Handles rate limiting, retries, column renaming, delete-before-insert,
    and logging — the identical boilerplate shared by every ``populate_*``
    dashboard function.

    Args:
        conn: Open SQLite connection.
        endpoint_factory: Zero-arg callable returning an nba_api endpoint
            instance (already parameterised with *season* and *timeout*).
        col_map: Mapping from NBA API column names to DB column names.
        table_name: Target SQLite table name.
        season: NBA season string.
        description: Human-readable label for log messages.
        season_col: Column name for the season value in the result.
        delete_filter: SQL WHERE clause for the DELETE.  ``None`` (default)
            means ``WHERE {season_col} = ?``.  An empty string means
            ``DELETE FROM {table_name}`` with no filter.
        include_season: Whether to add a season column to the result.
    """
    desc = description or table_name
    logger.info("Fetching %s for season %s …", desc, season)
    try:
        _rate_limited_sleep()
        df = _call_with_retries(
            lambda: endpoint_factory().get_data_frames()[0],
            description=desc,
        )
    except Exception:
        logger.exception(
            "Failed to fetch %s after %d attempts — skipping.",
            desc, _MAX_RETRIES,
        )
        return

    if df.empty:
        logger.info("%s: no data returned.", table_name)
        return

    available = {k: v for k, v in col_map.items() if k in df.columns}
    result = df[list(available.keys())].rename(columns=available)

    if include_season:
        result[season_col] = season

    if delete_filter is None:
        conn.execute(
            f"DELETE FROM {table_name} WHERE {season_col} = ?", (season,)
        )
    elif delete_filter == "":
        conn.execute(f"DELETE FROM {table_name}")
    else:
        conn.execute(f"DELETE FROM {table_name} {delete_filter}", (season,))

    result.to_sql(table_name, conn, if_exists="append", index=False)
    logger.info("%s: inserted %d rows.", table_name, len(result))


def populate_player_clutch_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load season-level clutch stats for all players."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueDashPlayerClutch(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "PLAYER_ID": "player_id", "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team_abbreviation", "AGE": "age",
            "GP": "gp", "W": "w", "L": "l", "W_PCT": "w_pct",
            "MIN": "min", "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
            "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
            "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
            "OREB": "oreb", "DREB": "dreb", "REB": "reb",
            "AST": "ast", "TOV": "tov", "STL": "stl", "BLK": "blk",
            "BLKA": "blka", "PF": "pf", "PFD": "pfd",
            "PTS": "pts", "PLUS_MINUS": "plus_minus",
            "NBA_FANTASY_PTS": "nba_fantasy_pts", "DD2": "dd2", "TD3": "td3",
        },
        table_name="Player_Clutch_Stats",
        season=season,
        description="LeagueDashPlayerClutch",
    )


def populate_team_clutch_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load season-level clutch stats for all teams."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueDashTeamClutch(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "TEAM_ID": "team_id", "GP": "gp", "W": "w", "L": "l",
            "W_PCT": "w_pct", "MIN": "min",
            "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
            "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
            "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
            "OREB": "oreb", "DREB": "dreb", "REB": "reb",
            "AST": "ast", "TOV": "tov", "STL": "stl", "BLK": "blk",
            "BLKA": "blka", "PF": "pf", "PFD": "pfd",
            "PTS": "pts", "PLUS_MINUS": "plus_minus",
        },
        table_name="Team_Clutch_Stats",
        season=season,
        description="LeagueDashTeamClutch",
    )


def populate_player_hustle_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load season-level hustle stats for all players."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueHustleStatsPlayer(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "PLAYER_ID": "player_id", "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team_abbreviation", "AGE": "age",
            "GP": "gp", "MIN": "min",
            "CONTESTED_SHOTS": "contested_shots",
            "CONTESTED_SHOTS_2PT": "contested_shots_2pt",
            "CONTESTED_SHOTS_3PT": "contested_shots_3pt",
            "DEFLECTIONS": "deflections", "CHARGES_DRAWN": "charges_drawn",
            "SCREEN_ASSISTS": "screen_assists",
            "SCREEN_AST_PTS": "screen_ast_pts",
            "OFF_LOOSE_BALLS_RECOVERED": "off_loose_balls",
            "DEF_LOOSE_BALLS_RECOVERED": "def_loose_balls",
            "LOOSE_BALLS_RECOVERED": "loose_balls",
            "PCT_LOOSE_BALLS_RECOVERED_OFF": "pct_loose_balls_off",
            "PCT_LOOSE_BALLS_RECOVERED_DEF": "pct_loose_balls_def",
            "OFF_BOXOUTS": "off_boxouts", "DEF_BOXOUTS": "def_boxouts",
            "BOX_OUT_PLAYER_TEAM_REBS": "boxout_team_rebs",
            "BOX_OUT_PLAYER_REBS": "boxout_player_rebs",
            "BOX_OUTS": "boxouts",
            "PCT_BOX_OUTS_OFF": "pct_boxouts_off",
            "PCT_BOX_OUTS_DEF": "pct_boxouts_def",
            "PCT_BOX_OUTS_TEAM_REB": "pct_boxouts_team_reb",
            "PCT_BOX_OUTS_REB": "pct_boxouts_reb",
        },
        table_name="Player_Hustle_Stats",
        season=season,
        description="LeagueHustleStatsPlayer",
    )


def populate_team_hustle_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load season-level hustle stats for all teams."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueHustleStatsTeam(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "TEAM_ID": "team_id", "MIN": "min",
            "CONTESTED_SHOTS": "contested_shots",
            "CONTESTED_SHOTS_2PT": "contested_shots_2pt",
            "CONTESTED_SHOTS_3PT": "contested_shots_3pt",
            "DEFLECTIONS": "deflections", "CHARGES_DRAWN": "charges_drawn",
            "SCREEN_ASSISTS": "screen_assists",
            "SCREEN_AST_PTS": "screen_ast_pts",
            "OFF_LOOSE_BALLS_RECOVERED": "off_loose_balls",
            "DEF_LOOSE_BALLS_RECOVERED": "def_loose_balls",
            "LOOSE_BALLS_RECOVERED": "loose_balls",
            "PCT_LOOSE_BALLS_RECOVERED_OFF": "pct_loose_balls_off",
            "PCT_LOOSE_BALLS_RECOVERED_DEF": "pct_loose_balls_def",
            "OFF_BOXOUTS": "off_boxouts", "DEF_BOXOUTS": "def_boxouts",
            "BOX_OUTS": "boxouts",
            "PCT_BOX_OUTS_OFF": "pct_boxouts_off",
            "PCT_BOX_OUTS_DEF": "pct_boxouts_def",
        },
        table_name="Team_Hustle_Stats",
        season=season,
        description="LeagueHustleStatsTeam",
    )


def populate_player_bio(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load player bio information for all players."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueDashPlayerBioStats(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "PLAYER_ID": "player_id", "PLAYER_NAME": "player_name",
            "TEAM_ID": "team_id", "TEAM_ABBREVIATION": "team_abbreviation",
            "AGE": "age", "PLAYER_HEIGHT": "player_height",
            "PLAYER_HEIGHT_INCHES": "player_height_inches",
            "PLAYER_WEIGHT": "player_weight",
            "COLLEGE": "college", "COUNTRY": "country",
            "DRAFT_YEAR": "draft_year", "DRAFT_ROUND": "draft_round",
            "DRAFT_NUMBER": "draft_number",
            "GP": "gp", "PTS": "pts", "REB": "reb", "AST": "ast",
            "NET_RATING": "net_rating", "OREB_PCT": "oreb_pct",
            "DREB_PCT": "dreb_pct", "USG_PCT": "usg_pct",
            "TS_PCT": "ts_pct", "AST_PCT": "ast_pct",
        },
        table_name="Player_Bio",
        season=season,
        description="LeagueDashPlayerBioStats",
        include_season=False,
        delete_filter="",
    )


def populate_player_estimated_metrics(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load player estimated advanced metrics."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: PlayerEstimatedMetrics(
            season=season, season_type="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "PLAYER_ID": "player_id", "GP": "gp", "W": "w", "L": "l",
            "W_PCT": "w_pct", "MIN": "min",
            "E_OFF_RATING": "e_off_rating", "E_DEF_RATING": "e_def_rating",
            "E_NET_RATING": "e_net_rating", "E_AST_RATIO": "e_ast_ratio",
            "E_OREB_PCT": "e_oreb_pct", "E_DREB_PCT": "e_dreb_pct",
            "E_REB_PCT": "e_reb_pct", "E_TOV_PCT": "e_tov_pct",
            "E_USG_PCT": "e_usg_pct", "E_PACE": "e_pace",
        },
        table_name="Player_Estimated_Metrics",
        season=season,
        description="PlayerEstimatedMetrics",
    )


def populate_team_estimated_metrics(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load team estimated advanced metrics."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: TeamEstimatedMetrics(
            season=season, season_type="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "TEAM_ID": "team_id", "GP": "gp", "W": "w", "L": "l",
            "W_PCT": "w_pct", "MIN": "min",
            "E_OFF_RATING": "e_off_rating", "E_DEF_RATING": "e_def_rating",
            "E_NET_RATING": "e_net_rating", "E_PACE": "e_pace",
            "E_AST_RATIO": "e_ast_ratio", "E_OREB_PCT": "e_oreb_pct",
            "E_DREB_PCT": "e_dreb_pct", "E_REB_PCT": "e_reb_pct",
            "E_TM_TOV_PCT": "e_tm_tov_pct",
        },
        table_name="Team_Estimated_Metrics",
        season=season,
        description="TeamEstimatedMetrics",
    )


def populate_league_dash_player_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load league dashboard player stats."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueDashPlayerStats(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "PLAYER_ID": "player_id", "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team_abbreviation", "AGE": "age",
            "GP": "gp", "W": "w", "L": "l", "W_PCT": "w_pct",
            "MIN": "min", "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
            "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
            "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
            "OREB": "oreb", "DREB": "dreb", "REB": "reb",
            "AST": "ast", "TOV": "tov", "STL": "stl", "BLK": "blk",
            "BLKA": "blka", "PF": "pf", "PFD": "pfd",
            "PTS": "pts", "PLUS_MINUS": "plus_minus",
            "NBA_FANTASY_PTS": "nba_fantasy_pts", "DD2": "dd2", "TD3": "td3",
        },
        table_name="League_Dash_Player_Stats",
        season=season,
        description="LeagueDashPlayerStats",
    )


def populate_league_dash_team_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load league dashboard team stats."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueDashTeamStats(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "TEAM_ID": "team_id", "GP": "gp", "W": "w", "L": "l",
            "W_PCT": "w_pct", "MIN": "min",
            "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
            "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
            "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
            "OREB": "oreb", "DREB": "dreb", "REB": "reb",
            "AST": "ast", "TOV": "tov", "STL": "stl", "BLK": "blk",
            "BLKA": "blka", "PF": "pf", "PFD": "pfd",
            "PTS": "pts", "PLUS_MINUS": "plus_minus",
        },
        table_name="League_Dash_Team_Stats",
        season=season,
        description="LeagueDashTeamStats",
    )


def populate_league_leaders(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load league leaders."""
    _populate_season_table(
        conn,
        endpoint_factory=lambda: LeagueLeaders(
            season=season, season_type_all_star="Regular Season",
            timeout=_SEASON_DASHBOARD_TIMEOUT,
        ),
        col_map={
            "PLAYER_ID": "player_id", "RANK": "rank", "TEAM": "team",
            "GP": "gp", "MIN": "min",
            "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
            "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
            "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
            "OREB": "oreb", "DREB": "dreb", "REB": "reb",
            "AST": "ast", "STL": "stl", "BLK": "blk", "TOV": "tov",
            "PF": "pf", "PTS": "pts", "EFF": "eff",
            "AST_TOV": "ast_tov", "STL_TOV": "stl_tov",
        },
        table_name="League_Leaders",
        season=season,
        description="LeagueLeaders",
    )


def populate_standings(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load league standings.

    Uses :class:`LeagueStandingsV3` — one API call returns all teams.

    Args:
        conn: Open SQLite connection.
        season: NBA season string.
    """
    logger.info("Fetching standings for season %s …", season)
    try:
        _rate_limited_sleep()
        df = _call_with_retries(
            lambda: LeagueStandingsV3(
                season=season, season_type="Regular Season",
                timeout=_SEASON_DASHBOARD_TIMEOUT,
            ).get_data_frames()[0],
            description="LeagueStandingsV3",
        )
    except Exception:
        logger.exception("Failed to fetch standings after %d attempts — skipping.", _MAX_RETRIES)
        return

    if df.empty:
        logger.info("Standings: no data returned.")
        return

    col_map = {
        "SeasonID": "season_id", "TeamID": "team_id",
        "Conference": "conference", "ConferenceRecord": "conference_record",
        "PlayoffRank": "playoff_rank", "ClinchIndicator": "clinch_indicator",
        "Division": "division", "DivisionRecord": "division_record",
        "DivisionRank": "division_rank",
        "WINS": "wins", "LOSSES": "losses", "WinPCT": "win_pct",
        "LeagueRank": "league_rank", "Record": "record",
        "HOME": "home", "ROAD": "road", "L10": "l10",
        "Last10Home": "last10_home", "Last10Road": "last10_road",
        "OT": "ot", "ThreePTSOrLess": "three_pts_or_less",
        "TenPTSOrMore": "ten_pts_or_more",
        "LongHomeStreak": "long_home_streak",
        "LongRoadStreak": "long_road_streak",
        "LongWinStreak": "long_win_streak",
        "LongLossStreak": "long_loss_streak",
        "CurrentHomeStreak": "current_home_streak",
        "CurrentRoadStreak": "current_road_streak",
        "CurrentStreak": "current_streak",
        "strCurrentStreak": "str_current_streak",
        "ConferenceGamesBack": "conference_games_back",
        "DivisionGamesBack": "division_games_back",
        "ClinchedConferenceTitle": "clinched_conf_title",
        "ClinchedDivisionTitle": "clinched_div_title",
        # NBA API misspells "Berth" as "Birth" — keep to match upstream.
        "ClinchedPlayoffBirth": "clinched_playoff",
        "EliminatedConference": "eliminated_conf",
        "EliminatedDivision": "eliminated_div",
        "AheadAtHalf": "ahead_at_half",
        "BehindAtHalf": "behind_at_half",
        "TiedAtHalf": "tied_at_half",
        "AheadAtThird": "ahead_at_third",
        "BehindAtThird": "behind_at_third",
        "TiedAtThird": "tied_at_third",
        "Score100PTS": "score_100pts",
        "OppScore100PTS": "opp_score_100pts",
        "OppOver500": "opp_over_500",
        "LeadInFGPCT": "lead_in_fg_pct",
        "LeadInReb": "lead_in_reb",
        "FewerTurnovers": "fewer_turnovers",
        "PointsPG": "points_pg", "OppPointsPG": "opp_points_pg",
        "DiffPointsPG": "diff_points_pg",
        "vsEast": "vs_east", "vsAtlantic": "vs_atlantic",
        "vsCentral": "vs_central", "vsSoutheast": "vs_southeast",
        "vsWest": "vs_west", "vsNorthwest": "vs_northwest",
        "vsPacific": "vs_pacific", "vsSouthwest": "vs_southwest",
    }
    available = {k: v for k, v in col_map.items() if k in df.columns}
    result = df[list(available.keys())].rename(columns=available)

    # Derive season_id if not in response
    if "season_id" not in result.columns:
        result["season_id"] = season

    # Deduplicate in case the API returns the same team twice
    result = result.drop_duplicates(subset=["season_id", "team_id"], keep="last")

    # DELETE using the actual season_id values in the data (the API may return
    # a numeric code like "22025" instead of "2025-26", so we can't rely on the
    # season parameter matching what's already stored).
    season_ids = result["season_id"].dropna().unique().tolist()
    if season_ids:
        placeholders = ",".join("?" * len(season_ids))
        conn.execute(
            f"DELETE FROM Standings WHERE season_id IN ({placeholders})",
            season_ids,
        )
    else:
        conn.execute("DELETE FROM Standings WHERE season_id = ?", (season,))
    conn.commit()

    result.to_sql("Standings", conn, if_exists="append", index=False)
    logger.info("Standings: inserted %d rows.", len(result))


# ---------------------------------------------------------------------------
# Per-player ETL pipelines
# ---------------------------------------------------------------------------


def populate_player_career_stats(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load career stats for active players (incremental).

    Only the **current season** and the **previous season** are kept —
    older historical rows are discarded to minimise storage and speed up
    queries.  On subsequent runs most players already have data; only
    those **missing** from ``Player_Career_Stats`` or who have **played
    in the last 3 days** are re-fetched.

    Uses batched thread-pool processing with a dedicated rate limiter
    and progressive cooldowns to avoid NBA API throttling.  A circuit
    breaker pauses longer after ``_CAREER_CIRCUIT_THRESHOLD``
    consecutive failures.  Players that fail the first pass are
    retried in a single-threaded second pass.

    Args:
        conn: Open SQLite connection.
        season: NBA season string (used to filter to current-season players).
    """
    # Compute which two seasons to keep.  The NBA API encodes season_id as
    # e.g. "22025" for the 2025-26 season (prefix '2' + start year).
    _start_year = int(season.split("-")[0])
    _keep_season_ids = {f"2{_start_year}", f"2{_start_year - 1}"}
    all_active = pd.read_sql(
        "SELECT DISTINCT player_id FROM Players WHERE is_active = 1",
        conn,
    )["player_id"].tolist()

    if not all_active:
        logger.info("Player_Career_Stats: no active players found.")
        return

    # ── Incremental: determine which players actually need fetching ───────
    # 1. Players with NO rows at all in Player_Career_Stats.
    existing_pids = set(
        pd.read_sql(
            "SELECT DISTINCT player_id FROM Player_Career_Stats",
            conn,
        )["player_id"].tolist()
    )
    missing_pids = [p for p in all_active if p not in existing_pids]

    # 2. Players who played a game in the last 3 days (stats may have changed).
    recently_active = set(
        pd.read_sql(
            "SELECT DISTINCT player_id FROM Player_Game_Logs "
            "WHERE game_date >= date('now', '-3 days')",
            conn,
        )["player_id"].tolist()
    )
    stale_pids = [p for p in all_active if p in recently_active and p in existing_pids]

    player_ids = list(dict.fromkeys(missing_pids + stale_pids))  # dedupe, preserve order

    if not player_ids:
        logger.info(
            "Player_Career_Stats: all %d active players already up-to-date — nothing to fetch.",
            len(all_active),
        )
        return

    logger.info(
        "Fetching career stats for %d players (%d missing, %d recently active) …",
        len(player_ids), len(missing_pids), len(stale_pids),
    )

    col_map = {
        "PLAYER_ID": "player_id", "SEASON_ID": "season_id",
        "TEAM_ID": "team_id", "TEAM_ABBREVIATION": "team_abbreviation",
        "PLAYER_AGE": "player_age",
        "GP": "gp", "GS": "gs", "MIN": "min",
        "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
        "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
        "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
        "OREB": "oreb", "DREB": "dreb", "REB": "reb",
        "AST": "ast", "STL": "stl", "BLK": "blk",
        "TOV": "tov", "PF": "pf", "PTS": "pts",
    }

    # Career-stats-specific rate limiter (independent of the global one)
    # to keep concurrent connections low during this bulk fetch.
    _career_lock = threading.Lock()
    _career_last_call_time = 0.0

    def _career_rate_sleep() -> None:
        nonlocal _career_last_call_time
        with _career_lock:
            now = time.monotonic()
            elapsed = now - _career_last_call_time
            if elapsed < _CAREER_RATE_DELAY:
                time.sleep(_CAREER_RATE_DELAY - elapsed)
            _career_last_call_time = time.monotonic()

    def _fetch_career_df(pid: int) -> pd.DataFrame | None:
        """Call NBA API for *pid* and return a column-mapped DataFrame or None."""
        try:
            df = _call_with_retries(
                lambda: PlayerCareerStats(
                    player_id=pid,
                    timeout=_CAREER_TIMEOUT,
                ).get_data_frames()[0],
                description=f"PlayerCareerStats(player={pid})",
                max_retries=_MAX_RETRIES_PER_PLAYER,
            )
        except Exception:
            logger.warning(
                "Failed to fetch career stats for player %d after %d attempts — skipping.",
                pid, _MAX_RETRIES_PER_PLAYER,
            )
            return None
        if df.empty:
            return None
        available = {k: v for k, v in col_map.items() if k in df.columns}
        mapped = df[list(available.keys())].rename(columns=available)
        # Keep only current + previous season rows.
        if "season_id" in mapped.columns:
            mapped["season_id"] = mapped["season_id"].astype(str)
            mapped = mapped[mapped["season_id"].isin(_keep_season_ids)]
        return mapped if not mapped.empty else None

    def _fetch_career(pid: int) -> tuple[int, pd.DataFrame | None]:
        """Rate-limited wrapper returning ``(pid, df | None)``."""
        _career_rate_sleep()
        return pid, _fetch_career_df(pid)

    # ── First pass: batched thread-pool fetch ────────────────────────────
    all_rows: list[pd.DataFrame] = []
    failed_pids: list[int] = []
    done = 0
    consecutive_failures = 0
    total_batches = (len(player_ids) + _CAREER_BATCH_SIZE - 1) // _CAREER_BATCH_SIZE

    for batch_idx, batch_start in enumerate(
        range(0, len(player_ids), _CAREER_BATCH_SIZE), start=1
    ):
        batch = player_ids[batch_start : batch_start + _CAREER_BATCH_SIZE]
        logger.info(
            "  Career stats batch %d/%d (%d players) …",
            batch_idx, total_batches, len(batch),
        )

        with ThreadPoolExecutor(max_workers=_CAREER_WORKERS) as pool:
            futures = {pool.submit(_fetch_career, pid): pid for pid in batch}
            for future in as_completed(futures):
                pid, mapped = future.result()
                if mapped is not None:
                    all_rows.append(mapped)
                    consecutive_failures = 0
                else:
                    failed_pids.append(pid)
                    consecutive_failures += 1
                done += 1

        logger.info(
            "  … progress: %d/%d processed (%d ok, %d failed).",
            done, len(player_ids), len(all_rows), len(failed_pids),
        )

        # Cooldown between batches (skip after the last batch).
        if batch_start + _CAREER_BATCH_SIZE < len(player_ids):
            if consecutive_failures >= _CAREER_CIRCUIT_THRESHOLD:
                logger.warning(
                    "  … circuit breaker: %d consecutive failures, cooling down %ds.",
                    consecutive_failures, _CAREER_CIRCUIT_COOLDOWN,
                )
                time.sleep(_CAREER_CIRCUIT_COOLDOWN)
                consecutive_failures = 0
            else:
                # Progressive cooldown: increase delay as we go deeper
                # to reduce likelihood of NBA API throttling.
                progress_ratio = done / len(player_ids)
                cooldown = _CAREER_BATCH_COOLDOWN
                if progress_ratio > 0.75:
                    cooldown = _CAREER_BATCH_COOLDOWN * 3
                elif progress_ratio > 0.5:
                    cooldown = _CAREER_BATCH_COOLDOWN * 2
                time.sleep(cooldown)

    # ── Second pass: retry failed players one-by-one ─────────────────────
    if failed_pids:
        logger.info(
            "  Retrying %d failed players (single-threaded) after %ds cooldown …",
            len(failed_pids), _CAREER_CIRCUIT_COOLDOWN,
        )
        time.sleep(_CAREER_CIRCUIT_COOLDOWN)
        recovered = 0
        for pid in failed_pids:
            _career_rate_sleep()
            mapped = _fetch_career_df(pid)
            if mapped is not None:
                all_rows.append(mapped)
                recovered += 1
        logger.info(
            "  Retry pass recovered %d / %d players.", recovered, len(failed_pids),
        )

    if not all_rows:
        logger.info("Player_Career_Stats: no career data retrieved.")
        return

    result = pd.concat(all_rows, ignore_index=True)
    result = result.drop_duplicates(subset=["player_id", "season_id", "team_id"])

    # Delete only the rows for players we re-fetched, then insert fresh data.
    fetched_pids = result["player_id"].unique().tolist()
    if fetched_pids:
        placeholders = ",".join("?" * len(fetched_pids))
        conn.execute(
            f"DELETE FROM Player_Career_Stats WHERE player_id IN ({placeholders})",
            fetched_pids,
        )
    result.to_sql("Player_Career_Stats", conn, if_exists="append", index=False)

    total_rows = conn.execute("SELECT COUNT(*) FROM Player_Career_Stats").fetchone()[0]
    total_players = conn.execute(
        "SELECT COUNT(DISTINCT player_id) FROM Player_Career_Stats"
    ).fetchone()[0]
    logger.info(
        "Player_Career_Stats: upserted %d rows for %d players (table total: %d rows, %d players).",
        len(result), len(fetched_pids), total_rows, total_players,
    )



def populate_shot_chart(
    conn: sqlite3.Connection, season: str = SEASON
) -> None:
    """Fetch and load shot chart data for all active players.

    Uses a thread pool to fetch multiple players concurrently while
    respecting the NBA API rate limit via :func:`_rate_limited_sleep`.

    Args:
        conn: Open SQLite connection.
        season: NBA season string.
    """
    player_ids = pd.read_sql(
        "SELECT DISTINCT player_id FROM Players WHERE is_active = 1",
        conn,
    )["player_id"].tolist()

    if not player_ids:
        logger.info("Shot_Chart: no active players found.")
        return

    logger.info("Fetching shot chart for %d players …", len(player_ids))

    col_map = {
        "GAME_ID": "game_id", "GAME_EVENT_ID": "game_event_id",
        "PLAYER_ID": "player_id", "PLAYER_NAME": "player_name",
        "TEAM_ID": "team_id", "TEAM_NAME": "team_name",
        "PERIOD": "period",
        "MINUTES_REMAINING": "minutes_remaining",
        "SECONDS_REMAINING": "seconds_remaining",
        "EVENT_TYPE": "event_type", "ACTION_TYPE": "action_type",
        "SHOT_TYPE": "shot_type",
        "SHOT_ZONE_BASIC": "shot_zone_basic",
        "SHOT_ZONE_AREA": "shot_zone_area",
        "SHOT_ZONE_RANGE": "shot_zone_range",
        "SHOT_DISTANCE": "shot_distance",
        "LOC_X": "loc_x", "LOC_Y": "loc_y",
        "SHOT_ATTEMPTED_FLAG": "shot_attempted_flag",
        "SHOT_MADE_FLAG": "shot_made_flag",
        "GAME_DATE": "game_date", "HTM": "htm", "VTM": "vtm",
    }

    def _fetch_shots(pid: int) -> pd.DataFrame | None:
        _rate_limited_sleep()
        try:
            df = _call_with_retries(
                lambda: ShotChartDetail(
                    team_id=0,
                    player_id=pid,
                    season_nullable=season,
                    season_type_all_star="Regular Season",
                    context_measure_simple="FGA",
                    timeout=_PER_PLAYER_TIMEOUT,
                ).get_data_frames()[0],
                description=f"ShotChartDetail(player={pid})",
                max_retries=_MAX_RETRIES_PER_PLAYER,
            )
        except Exception:
            logger.warning(
                "Failed to fetch shot chart for player %d after %d attempts — skipping.",
                pid, _MAX_RETRIES_PER_PLAYER,
            )
            return None
        if df.empty:
            return None
        available = {k: v for k, v in col_map.items() if k in df.columns}
        mapped = df[list(available.keys())].rename(columns=available)
        mapped["season"] = season
        return mapped

    all_rows: list[pd.DataFrame] = []
    done = 0

    with ThreadPoolExecutor(max_workers=_PLAYER_WORKERS) as pool:
        futures = {pool.submit(_fetch_shots, pid): pid for pid in player_ids}
        for future in as_completed(futures):
            mapped = future.result()
            if mapped is not None:
                all_rows.append(mapped)
            done += 1
            if done % _LOG_PROGRESS_INTERVAL == 0:
                logger.info("  … shot chart: %d / %d players processed.", done, len(player_ids))

    if not all_rows:
        logger.info("Shot_Chart: no shot data retrieved.")
        return

    result = pd.concat(all_rows, ignore_index=True)
    result = result.drop_duplicates(subset=["game_id", "game_event_id", "player_id"])

    conn.execute("DELETE FROM Shot_Chart WHERE season = ?", (season,))
    result.to_sql("Shot_Chart", conn, if_exists="append", index=False)
    logger.info("Shot_Chart: inserted %d rows.", len(result))


# ---------------------------------------------------------------------------
# Per-game advanced box score ETL pipelines
# ---------------------------------------------------------------------------

# Column mapping dicts for each box-score endpoint.  Extracted here as
# module-level constants so ``_fetch_single_game_box_scores`` stays concise.

_COL_MAP_ADVANCED: dict[str, str] = {
    "gameId": "game_id", "personId": "person_id",
    "teamId": "team_id", "position": "position",
    "minutes": "minutes",
    "estimatedOffensiveRating": "est_off_rating",
    "offensiveRating": "off_rating",
    "estimatedDefensiveRating": "est_def_rating",
    "defensiveRating": "def_rating",
    "estimatedNetRating": "est_net_rating",
    "netRating": "net_rating",
    "assistPercentage": "ast_pct",
    "assistToTurnover": "ast_to_tov",
    "assistRatio": "ast_ratio",
    "offensiveReboundPercentage": "oreb_pct",
    "defensiveReboundPercentage": "dreb_pct",
    "reboundPercentage": "reb_pct",
    "turnoverRatio": "tov_ratio",
    "effectiveFieldGoalPercentage": "efg_pct",
    "trueShootingPercentage": "ts_pct",
    "usagePercentage": "usg_pct",
    "estimatedUsagePercentage": "est_usg_pct",
    "estimatedPace": "est_pace",
    "pace": "pace", "pacePerGame": "pace_per40",
    "possessions": "possessions", "PIE": "pie",
}

_COL_MAP_SCORING: dict[str, str] = {
    "gameId": "game_id", "personId": "person_id",
    "teamId": "team_id", "minutes": "minutes",
    "percentageFieldGoalsAttempted2pt": "pct_fga_2pt",
    "percentageFieldGoalsAttempted3pt": "pct_fga_3pt",
    "percentagePoints2pt": "pct_pts_2pt",
    "percentagePointsMidrange2pt": "pct_pts_mid2pt",
    "percentagePoints3pt": "pct_pts_3pt",
    "percentagePointsFastBreak": "pct_pts_fast_break",
    "percentagePointsFreeThrow": "pct_pts_ft",
    "percentagePointsOffTurnovers": "pct_pts_off_tov",
    "percentagePointsPaint": "pct_pts_paint",
    "percentageAssisted2pt": "pct_assisted_2pt",
    "percentageUnassisted2pt": "pct_unassisted_2pt",
    "percentageAssisted3pt": "pct_assisted_3pt",
    "percentageUnassisted3pt": "pct_unassisted_3pt",
    "percentageAssistedFGM": "pct_assisted_fgm",
    "percentageUnassistedFGM": "pct_unassisted_fgm",
}

_COL_MAP_USAGE: dict[str, str] = {
    "gameId": "game_id", "personId": "person_id",
    "teamId": "team_id", "minutes": "minutes",
    "usagePercentage": "usg_pct",
    "percentageFieldGoalsMade": "pct_fgm",
    "percentageFieldGoalsAttempted": "pct_fga",
    "percentageThreePointersMade": "pct_fg3m",
    "percentageThreePointersAttempted": "pct_fg3a",
    "percentageFreeThrowsMade": "pct_ftm",
    "percentageFreeThrowsAttempted": "pct_fta",
    "percentageOffensiveRebounds": "pct_oreb",
    "percentageDefensiveRebounds": "pct_dreb",
    "percentageRebounds": "pct_reb",
    "percentageAssists": "pct_ast",
    "percentageTurnovers": "pct_tov",
    "percentageSteals": "pct_stl",
    "percentageBlocks": "pct_blk",
    "percentageBlocksAllowed": "pct_blka",
    "percentagePersonalFouls": "pct_pf",
    "percentagePersonalFoulsDrawn": "pct_pfd",
    "percentagePoints": "pct_pts",
}

_COL_MAP_TRACKING: dict[str, str] = {
    "gameId": "game_id", "personId": "person_id",
    "teamId": "team_id", "teamTricode": "team_tricode",
    "firstName": "first_name", "familyName": "family_name",
    "position": "position", "comment": "comment",
    "jerseyNum": "jersey_num", "minutes": "minutes",
    "speed": "speed", "distance": "distance",
    "reboundChancesOffensive": "rebound_chances_offensive",
    "reboundChancesDefensive": "rebound_chances_defensive",
    "reboundChancesTotal": "rebound_chances_total",
    "touches": "touches",
    "secondaryAssists": "secondary_assists",
    "freeThrowAssists": "free_throw_assists",
    "passes": "passes", "assists": "assists",
    "contestedFieldGoalsMade": "contested_fg_made",
    "contestedFieldGoalsAttempted": "contested_fg_attempted",
    "contestedFieldGoalPercentage": "contested_fg_pct",
    "uncontestedFieldGoalsMade": "uncontested_fg_made",
    "uncontestedFieldGoalsAttempted": "uncontested_fg_attempted",
    "uncontestedFieldGoalPercentage": "uncontested_fg_pct",
    "fieldGoalPercentage": "fg_pct",
    "defendedAtRimFieldGoalsMade": "defended_at_rim_fg_made",
    "defendedAtRimFieldGoalsAttempted": "defended_at_rim_fg_attempted",
    "defendedAtRimFieldGoalPercentage": "defended_at_rim_fg_pct",
}

_COL_MAP_MATCHUPS: dict[str, str] = {
    "gameId": "game_id",
    "personIdOff": "person_id_off",
    "personIdDef": "person_id_def",
    "teamId": "team_id",
    "matchupMinutes": "matchup_min",
    "matchupMinutesSort": "matchup_min_sort",
    "partialPossessions": "partial_poss",
    "percentageDefenderTotalTime": "pct_def_total_time",
    "percentageOffensiveTotalTime": "pct_off_total_time",
    "percentageTotalTimeBothOn": "pct_total_time_both_on",
    "switchesOn": "switches_on",
    "playerPoints": "player_pts",
    "teamPoints": "team_pts",
    "matchupAssists": "matchup_ast",
    "matchupPotentialAssists": "matchup_potential_ast",
    "matchupTurnovers": "matchup_tov",
    "matchupBlocks": "matchup_blk",
    "matchupFieldGoalsMade": "matchup_fgm",
    "matchupFieldGoalsAttempted": "matchup_fga",
    "matchupFieldGoalPercentage": "matchup_fg_pct",
    "matchupThreePointersMade": "matchup_fg3m",
    "matchupThreePointersAttempted": "matchup_fg3a",
    "matchupThreePointerPercentage": "matchup_fg3_pct",
    "helpBlocks": "help_blk",
    "helpFieldGoalsMade": "help_fgm",
    "helpFieldGoalsAttempted": "help_fga",
    "helpFieldGoalPercentage": "help_fg_pct",
    "matchupFreeThrowsMade": "matchup_ftm",
    "matchupFreeThrowsAttempted": "matchup_fta",
    "shootingFouls": "shooting_fouls",
}

# Tuple of (endpoint_class, col_map, table_name, description) for each
# box-score type.  Used by ``_fetch_single_game_box_scores``.
_BOX_SCORE_ENDPOINTS: tuple[tuple[Any, dict[str, str], str, str], ...] = (
    (BoxScoreAdvancedV3,     _COL_MAP_ADVANCED,  "Box_Score_Advanced",     "BoxScoreAdvancedV3"),
    (BoxScoreScoringV3,      _COL_MAP_SCORING,   "Box_Score_Scoring",      "BoxScoreScoringV3"),
    (BoxScoreUsageV3,        _COL_MAP_USAGE,     "Box_Score_Usage",        "BoxScoreUsageV3"),
    (BoxScorePlayerTrackV3,  _COL_MAP_TRACKING,  "Player_Tracking_Stats",  "BoxScorePlayerTrackV3"),
    (BoxScoreMatchupsV3,     _COL_MAP_MATCHUPS,  "Box_Score_Matchups",     "BoxScoreMatchupsV3"),
)


def _get_game_ids_for_season(conn: sqlite3.Connection, season: str = SEASON) -> list[str]:
    """Return all game_ids for *season* that have scores (completed games).

    Args:
        conn: Open SQLite connection.
        season: NBA season string.

    Returns:
        List of game_id strings.
    """
    rows = conn.execute(
        "SELECT game_id FROM Games WHERE season = ? AND home_score IS NOT NULL",
        (season,),
    ).fetchall()
    return [r[0] for r in rows]


def populate_game_advanced_box_scores(
    conn: sqlite3.Connection, season: str = SEASON,
    game_ids: list[str] | None = None,
) -> None:
    """Fetch and load advanced, scoring, usage, tracking, and matchup box
    scores for games.

    Uses a thread pool to fetch multiple games concurrently.  Within each
    game the five box-score types are also fetched in parallel.  Skips
    games whose ``game_id`` is already present in ``Box_Score_Advanced`` to
    avoid redundant fetches.

    Args:
        conn: Open SQLite connection.
        season: NBA season string.
        game_ids: If provided, only process these game_ids.  Otherwise,
            processes all completed games for *season*.
    """
    if game_ids is None:
        game_ids = _get_game_ids_for_season(conn, season)

    if not game_ids:
        logger.info("Game box scores: no completed games to process.")
        return

    # Determine which games already have advanced box score data.
    existing = set()
    try:
        rows = conn.execute("SELECT DISTINCT game_id FROM Box_Score_Advanced").fetchall()
        existing = {r[0] for r in rows}
    except Exception:
        pass

    new_game_ids = [gid for gid in game_ids if gid not in existing]
    if not new_game_ids:
        logger.info("Game box scores: all games already processed.")
        return

    logger.info("Fetching advanced box scores for %d games …", len(new_game_ids))

    done = 0
    with ThreadPoolExecutor(max_workers=_GAME_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_single_game_box_scores, game_id=gid, season=season): gid
            for gid in new_game_ids
        }
        for future in as_completed(futures):
            results = future.result()
            # Write all returned DataFrames to the database (main thread).
            for table_name, df in results.items():
                df.to_sql(table_name, conn, if_exists="append", index=False)
            done += 1
            if done % 25 == 0:
                logger.info("  … box scores: %d / %d games processed.", done, len(new_game_ids))
                conn.commit()  # Periodic commit to avoid losing progress.

    logger.info("Game box scores: completed processing %d games.", len(new_game_ids))


def _fetch_single_game_box_scores(
    game_id: str, season: str,
) -> dict[str, pd.DataFrame]:
    """Fetch all 5 advanced box score types for a single game concurrently.

    Each box score endpoint call is wrapped in a try/except so a failure
    on one type does not block the others.  Returns a mapping of
    table-name → DataFrame for the caller to insert.

    Args:
        game_id: NBA game ID string.
        season: NBA season string.

    Returns:
        Dict mapping SQL table names to DataFrames ready for insertion.
    """
    results: dict[str, pd.DataFrame] = {}
    # Each worker writes to a unique key, so the lock only protects the
    # dict from concurrent mutation — not from key-level races.
    results_lock = threading.Lock()

    def _make_fetcher(
        endpoint_class: Any,
        col_map: dict[str, str],
        table_name: str,
        desc_name: str,
    ) -> Callable[[], None]:
        """Return a closure that fetches one box-score type for this game."""
        def _fetcher() -> None:
            _rate_limited_sleep()
            try:
                df = _call_with_retries(
                    lambda: endpoint_class(
                        game_id=game_id, timeout=_PER_GAME_TIMEOUT,
                    ).get_data_frames()[0],
                    description=f"{desc_name}(game={game_id})",
                )
                if not df.empty:
                    available = {k: v for k, v in col_map.items() if k in df.columns}
                    result = df[list(available.keys())].rename(columns=available)
                    result["season"] = season
                    if "game_id" not in result.columns:
                        result["game_id"] = game_id
                    with results_lock:
                        results[table_name] = result
            except Exception:
                logger.debug(
                    "%s failed for game %s after %d attempts.",
                    desc_name, game_id, _MAX_RETRIES,
                )
        return _fetcher

    # Build a fetcher for each box-score endpoint from the module-level
    # ``_BOX_SCORE_ENDPOINTS`` registry and run them all concurrently.
    fetchers = [
        _make_fetcher(cls, cmap, tbl, desc)
        for cls, cmap, tbl, desc in _BOX_SCORE_ENDPOINTS
    ]

    with ThreadPoolExecutor(max_workers=_BOX_SCORE_TYPE_WORKERS) as pool:
        futs = [pool.submit(fn) for fn in fetchers]
        for f in as_completed(futs):
            f.result()  # Propagate unexpected errors; expected ones handled inside.

    return results


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_initial_pull(db_path: str = DB_PATH, season: str = SEASON) -> dict:
    """Orchestrate the full initial data pull and database seed.

    1. Ensures the database schema exists (calls :func:`setup_db.create_tables`).
    2. Seeds the Teams table from ``nba_api`` static team data.
    3. Fetches all player game logs for *season*.
    4. Builds and loads the Players, Games, and Player_Game_Logs tables.
    5. Fetches team-level game logs and populates Team_Game_Stats.
    6. Fetches rosters for every team and populates Team_Roster and
       Players.position.
    7. Computes Defense_Vs_Position multipliers from the loaded data.
    8. Populates season-level dashboards (clutch, hustle, bio, estimated
       metrics, league dash stats, league leaders, standings).
    9. Populates per-player data (career stats, shot chart).
    10. Populates per-game advanced box scores (advanced, scoring, usage,
        tracking, matchups).

    Args:
        db_path: Path to the SQLite database file.
        season: NBA season string, e.g. ``'2025-26'``.

    Returns:
        dict with keys ``players_inserted``, ``games_inserted``,
        ``logs_inserted``.
    """
    logger.info("=== SmartPicksProAI — Initial Data Pull ===")
    setup_db.create_tables(db_path)

    conn = sqlite3.connect(db_path)
    try:
        seed_teams_from_api(conn)
        conn.commit()
    finally:
        conn.close()

    # --- Player game logs ---
    raw = fetch_season_logs(season)

    players_df = build_players_df(raw)
    games_df = build_games_df(raw)
    logs_df = build_logs_df(raw)

    # --- Team game logs ---
    raw_team = fetch_team_season_logs(season)
    team_stats_df = build_team_game_stats_df(raw_team)

    conn = sqlite3.connect(db_path)
    try:
        load_players(players_df, conn)
        load_games(games_df, conn)
        load_logs(logs_df, conn)
        load_team_game_stats(team_stats_df, conn)

        # Back-fill home/away scores from Team_Game_Stats into Games.
        populate_game_scores(conn)

        # Refresh season-level pace/ortg/drtg on the Teams table.
        update_team_season_stats(conn)
        conn.commit()

        # --- Rosters (rate-limited: 1 req / team) ---
        fetch_and_load_rosters(conn, season)
        conn.commit()

        # --- Defense vs Position multipliers ---
        # Must run after rosters are loaded (Players.position is needed).
        populate_defense_vs_position(conn, season)
        conn.commit()

        # --- Season-level dashboards (one API call each) ---
        logger.info("--- Populating season-level dashboard tables ---")
        populate_player_clutch_stats(conn, season)
        conn.commit()
        populate_team_clutch_stats(conn, season)
        conn.commit()
        populate_player_hustle_stats(conn, season)
        conn.commit()
        populate_team_hustle_stats(conn, season)
        conn.commit()
        populate_player_bio(conn, season)
        conn.commit()
        populate_player_estimated_metrics(conn, season)
        conn.commit()
        populate_team_estimated_metrics(conn, season)
        conn.commit()
        populate_league_dash_player_stats(conn, season)
        conn.commit()
        populate_league_dash_team_stats(conn, season)
        conn.commit()
        populate_league_leaders(conn, season)
        conn.commit()
        populate_standings(conn, season)
        conn.commit()

        # --- RotoWire injury data ---
        logger.info("--- Syncing RotoWire injury report ---")
        try:
            injury_count = sync_rotowire_injuries(db_path)
            logger.info("RotoWire injury sync: %d rows upserted.", injury_count)
        except Exception:
            logger.exception(
                "RotoWire injury sync failed — continuing without injury data."
            )
        conn.commit()

        # --- CBS Sports injury data ---
        logger.info("--- Syncing CBS Sports injury report ---")
        try:
            cbs_count = sync_cbs_injuries(db_path)
            logger.info("CBS injury sync: %d rows upserted.", cbs_count)
        except Exception:
            logger.exception(
                "CBS injury sync failed — continuing without CBS injury data."
            )
        conn.commit()

        # --- Per-player data (rate-limited: 1 req / player) ---
        logger.info("--- Populating per-player tables ---")
        populate_player_career_stats(conn, season)
        conn.commit()

        if SKIP_EXTENDED_PULLS:
            logger.info(
                "SKIP_EXTENDED_PULLS is enabled — skipping shot chart, "
                "per-game box scores, and remaining extended data pulls."
            )
        else:
            populate_shot_chart(conn, season)
            conn.commit()

            # --- Per-game advanced box scores ---
            logger.info("--- Populating per-game advanced box scores ---")
            populate_game_advanced_box_scores(conn, season)
            conn.commit()

        # Read actual row counts to return to callers.
        p_count = conn.execute("SELECT COUNT(*) FROM Players").fetchone()[0]
        g_count = conn.execute("SELECT COUNT(*) FROM Games").fetchone()[0]
        l_count = conn.execute(
            "SELECT COUNT(*) FROM Player_Game_Logs"
        ).fetchone()[0]

        logger.info(
            "=== Initial pull complete. %d players, %d games, %d logs. ===",
            p_count, g_count, l_count,
        )
        # Allow NBA API rate-limit window to reset before the app makes live calls
        time.sleep(_POST_ETL_COOLDOWN)
        return {
            "players_inserted": p_count,
            "games_inserted": g_count,
            "logs_inserted": l_count,
        }
    finally:
        conn.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    run_initial_pull()
