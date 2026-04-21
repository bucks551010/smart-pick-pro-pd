"""
data_updater.py
---------------
On-demand incremental update module for the SmartPicksProAI database.

Exposes a single public function, :func:`run_update`, which fetches only the
game logs that have occurred since the last date already stored in the
``Games`` table.  Also refreshes season-level dashboards and advanced box
scores for newly added games.

There are **no scheduling loops, no cron jobs, and no ``while True`` blocks**
— the caller decides when to trigger an update (e.g. via the FastAPI
endpoint in api.py).

Usage::

    from etl.data_updater import run_update
    new_records = run_update()
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from nba_api.stats.endpoints import LeagueGameLog, ScoreboardV3

from . import initial_pull
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

# NBA API date format for the date_from_nullable / date_to_nullable params.
_NBA_DATE_FMT = "%m/%d/%Y"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_last_game_date(conn: sqlite3.Connection) -> Optional[date]:
    """Return the most recent ``game_date`` stored in the Games table.

    Args:
        conn: Open SQLite connection.

    Returns:
        A :class:`datetime.date` object, or ``None`` if the table is empty.
    """
    row = conn.execute("SELECT MAX(game_date) FROM Games").fetchone()
    if row and row[0]:
        return datetime.strptime(row[0], "%Y-%m-%d").date()
    return None


def _fetch_logs_for_range(
    date_from: date,
    date_to: date,
    player_or_team: str = "P",
) -> pd.DataFrame:
    """Fetch game logs between *date_from* and *date_to* (inclusive).

    Converts dates to the NBA API's expected ``MM/DD/YYYY`` format before
    calling the endpoint.

    Args:
        date_from: Start date (inclusive).
        date_to:   End date (inclusive).
        player_or_team: ``'P'`` for player logs, ``'T'`` for team logs.

    Returns:
        Raw DataFrame from the LeagueGameLog endpoint, or an empty DataFrame
        if the API returns no data.
    """
    kind = "player" if player_or_team == "P" else "team"
    str_from = date_from.strftime(_NBA_DATE_FMT)
    str_to = date_to.strftime(_NBA_DATE_FMT)
    logger.info(
        "Fetching %s logs from %s to %s …", kind, str_from, str_to
    )

    initial_pull._rate_limited_sleep()
    df = initial_pull._call_with_retries(
        lambda: LeagueGameLog(
            player_or_team_abbreviation=player_or_team,
            season=SEASON,
            season_type_all_star="Regular Season",
            date_from_nullable=str_from,
            date_to_nullable=str_to,
            timeout=initial_pull._BULK_ENDPOINT_TIMEOUT,
        ).get_data_frames()[0],
        description=f"LeagueGameLog({kind}, {str_from}–{str_to})",
    )
    logger.info("%s-level API returned %d rows.", kind.capitalize(), len(df))
    return df


def _parse_game_date(series: pd.Series) -> pd.Series:
    """Convert a Series of NBA-formatted date strings to ``YYYY-MM-DD``.

    Args:
        series: Series containing date strings (e.g. ``'OCT 22, 2025'``).

    Returns:
        Series of ISO-format date strings.
    """
    return (
        pd.to_datetime(series, format="mixed", dayfirst=False)
        .dt.strftime("%Y-%m-%d")
    )


# ---------------------------------------------------------------------------
# Upsert helpers (shared logic with initial_pull.py)
# ---------------------------------------------------------------------------


def _upsert_players(raw: pd.DataFrame, conn: sqlite3.Connection) -> None:
    """Insert or update players from *raw* in the Players table.

    Delegates player DataFrame construction to
    :func:`initial_pull.build_players_df` (shared logic) and then performs
    ``INSERT OR REPLACE`` to handle trade updates.

    Args:
        raw: Raw game-log DataFrame.
        conn: Open SQLite connection.
    """
    players = initial_pull.build_players_df(raw)
    upsert_dataframe(players, "Players", conn)


def _upsert_games(raw: pd.DataFrame, conn: sqlite3.Connection) -> None:
    """Insert any games from *raw* that are not already in the Games table.

    Parses ``home_abbrev`` and ``away_abbrev`` from the MATCHUP string:

    - ``'LAL vs. BOS'`` → home is left abbreviation (``LAL``).
    - ``'LAL @ BOS'``   → home is right abbreviation (``BOS``).

    ``home_team_id`` and ``away_team_id`` are derived from the MATCHUP and
    TEAM_ID columns in the raw data.

    Args:
        raw: Raw game-log DataFrame.
        conn: Open SQLite connection.
    """
    games = raw[["GAME_ID", "GAME_DATE", "MATCHUP"]].drop_duplicates("GAME_ID").copy()
    games["GAME_DATE"] = _parse_game_date(games["GAME_DATE"])
    games = games.rename(
        columns={"GAME_ID": "game_id", "GAME_DATE": "game_date", "MATCHUP": "matchup"}
    )

    games["season"] = SEASON

    if not games.empty:
        home_abbrevs, away_abbrevs = zip(*games["matchup"].map(parse_matchup_abbreviations))
        games["home_abbrev"] = list(home_abbrevs)
        games["away_abbrev"] = list(away_abbrevs)
        # Normalise matchup to always use "{HOME} vs. {AWAY}" format.
        games["matchup"] = games["home_abbrev"] + " vs. " + games["away_abbrev"]
    else:
        games["home_abbrev"] = []
        games["away_abbrev"] = []

    # Derive home_team_id / away_team_id from the raw per-player rows.
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

    existing = pd.read_sql("SELECT game_id FROM Games", conn)
    new_rows = games[~games["game_id"].isin(existing["game_id"])]
    if not new_rows.empty:
        new_rows.to_sql("Games", conn, if_exists="append", index=False)
        logger.info("Games: inserted %d new rows.", len(new_rows))


def _upsert_logs(raw: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """Insert new player-game log rows that are not already in the database.

    Delegates DataFrame construction to :func:`initial_pull.build_logs_df`
    (shared DNP handling, column mapping, and deduplication).

    Args:
        raw: Raw game-log DataFrame.
        conn: Open SQLite connection.

    Returns:
        Number of new rows inserted into ``Player_Game_Logs``.
    """
    logs = initial_pull.build_logs_df(raw)

    existing = pd.read_sql("SELECT player_id, game_id FROM Player_Game_Logs", conn)
    new_rows = get_new_rows(logs, existing, on_cols=["player_id", "game_id"])

    if new_rows.empty:
        logger.info("Player_Game_Logs: no new rows to insert.")
        return 0

    new_rows.to_sql("Player_Game_Logs", conn, if_exists="append", index=False)
    logger.info("Player_Game_Logs: inserted %d new rows.", len(new_rows))
    return len(new_rows)


def _upsert_team_game_stats(
    raw_team: pd.DataFrame, conn: sqlite3.Connection
) -> None:
    """Insert new Team_Game_Stats rows from team-level game log data.

    Delegates to :func:`initial_pull.build_team_game_stats_df` and
    :func:`initial_pull.load_team_game_stats` to reuse the shared transform
    and load logic.

    Args:
        raw_team: Raw team-level game-log DataFrame.
        conn: Open SQLite connection.
    """
    if raw_team.empty:
        logger.info("Team_Game_Stats: no team data to process.")
        return
    stats = initial_pull.build_team_game_stats_df(raw_team)
    initial_pull.load_team_game_stats(stats, conn)


# ---------------------------------------------------------------------------
# Today's schedule helper
# ---------------------------------------------------------------------------


def sync_todays_games(conn: sqlite3.Connection) -> int:
    """Fetch today's scheduled games via ``ScoreboardV3`` and insert them.

    Only games whose ``game_id`` is not already in the ``Games`` table are
    inserted.  This ensures that ``GET /api/games/today`` can be answered
    entirely from the database without a live API fallback.

    Args:
        conn: Open SQLite connection (caller is responsible for committing).

    Returns:
        Number of new game rows inserted into the ``Games`` table.
    """
    # Use Eastern Time — NBA API uses ET dates for scheduling.
    try:
        from zoneinfo import ZoneInfo as _ZI
        from datetime import datetime as _dt
        today_str = _dt.now(_ZI("America/New_York")).date().isoformat()
    except Exception:
        today_str = date.today().isoformat()
    logger.info("Syncing today's schedule (%s) via ScoreboardV3 …", today_str)

    try:
        def _fetch_scoreboard():
            sb = ScoreboardV3(
                game_date=today_str,
                timeout=initial_pull._SEASON_DASHBOARD_TIMEOUT,
            )
            return sb.game_header.get_data_frame(), sb.line_score.get_data_frame()

        initial_pull._rate_limited_sleep()
        game_header, line_score = initial_pull._call_with_retries(
            _fetch_scoreboard,
            description=f"ScoreboardV3({today_str})",
        )
    except Exception:  # Broad: _call_with_retries re-raises whatever the NBA API raises.
        logger.exception(
            "Failed to fetch ScoreboardV3 for %s after %d attempts.",
            today_str, initial_pull._MAX_RETRIES,
        )
        return 0

    if game_header.empty:
        logger.info("ScoreboardV3 returned no games for %s.", today_str)
        return 0

    # V3 uses camelCase columns: gameId, teamId, teamTricode, gameCode, etc.
    # Pre-convert gameId column to string once to avoid repeated conversions.
    line_score_game_ids = line_score["gameId"].astype(str)

    inserted = 0
    cursor = conn.cursor()
    for _, game_row in game_header.iterrows():
        game_id = str(game_row.get("gameId", ""))
        if not game_id:
            continue

        # Skip if already stored.
        existing = cursor.execute(
            "SELECT 1 FROM Games WHERE game_id = ?", (game_id,)
        ).fetchone()
        if existing:
            continue

        # V3 GameHeader does not contain team IDs directly; derive from
        # LineScore where each game has two rows (away first, home second).
        teams = line_score[line_score_game_ids == game_id]
        home_team_id = None
        away_team_id = None
        home_tri = ""
        away_tri = ""
        if len(teams) >= 2:
            away_row = teams.iloc[0]
            home_row = teams.iloc[1]
            home_team_id = int(home_row.get("teamId")) if home_row.get("teamId") is not None else None
            away_team_id = int(away_row.get("teamId")) if away_row.get("teamId") is not None else None
            home_tri = str(home_row.get("teamTricode", ""))
            away_tri = str(away_row.get("teamTricode", ""))

        if home_tri and away_tri:
            matchup = f"{home_tri} vs. {away_tri}"
        else:
            matchup = game_row.get("gameCode", "TBD")

        cursor.execute(
            "INSERT INTO Games (game_id, game_date, season, home_team_id, "
            "away_team_id, home_abbrev, away_abbrev, matchup) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (game_id, today_str, SEASON, home_team_id, away_team_id,
             home_tri, away_tri, matchup),
        )
        inserted += 1

    logger.info("Today's schedule: inserted %d new games for %s.", inserted, today_str)
    return inserted


def _refresh_season_dashboards(
    conn: sqlite3.Connection, season: str,
) -> None:
    """Refresh all season-level dashboard tables.

    This is a lightweight operation — each call is a single NBA API request
    that returns data for all players/teams at once.

    Args:
        conn: Open SQLite connection.
        season: NBA season string.
    """
    logger.info("Refreshing season-level dashboard tables …")
    initial_pull.populate_player_clutch_stats(conn, season)
    initial_pull.populate_team_clutch_stats(conn, season)
    initial_pull.populate_player_hustle_stats(conn, season)
    initial_pull.populate_team_hustle_stats(conn, season)
    initial_pull.populate_player_bio(conn, season)
    initial_pull.populate_player_estimated_metrics(conn, season)
    initial_pull.populate_team_estimated_metrics(conn, season)
    initial_pull.populate_league_dash_player_stats(conn, season)
    initial_pull.populate_league_dash_team_stats(conn, season)
    initial_pull.populate_league_leaders(conn, season)
    initial_pull.populate_standings(conn, season)
    logger.info("Season-level dashboard tables refreshed.")


def _get_completed_game_ids_in_range(
    conn: sqlite3.Connection, date_from: "date", date_to: "date",
) -> list[str]:
    """Return game_ids for completed games in the given date range.

    Args:
        conn: Open SQLite connection.
        date_from: Start date (inclusive).
        date_to: End date (inclusive).

    Returns:
        List of game_id strings.
    """
    rows = conn.execute(
        "SELECT game_id FROM Games "
        "WHERE game_date >= ? AND game_date <= ? AND home_score IS NOT NULL",
        (date_from.isoformat(), date_to.isoformat()),
    ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_update(db_path: str = DB_PATH) -> int:
    """Fetch and append game logs that have occurred since the last DB update.

    Steps:

    1. Opens the database and queries for the most recent ``game_date`` in
       the ``Games`` table.
    2. If no date is found the database is empty — automatically runs the
       initial pull to seed the database, then returns the number of log
       rows inserted.
    3. Fetches all player game logs between ``last_date + 1 day`` and
       yesterday using the NBA API.
    4. De-duplicates and appends new rows to Players, Games,
       Player_Game_Logs, and Team_Game_Stats.
    5. Refreshes season-level dashboards (clutch, hustle, bio, estimated
       metrics, league dash stats, league leaders, standings).
    6. Fetches advanced box scores for any new games.
    7. Returns the total count of new ``Player_Game_Logs`` rows inserted.

    There are **no loops, no scheduling, and no ``while True`` blocks**.
    A single rate-limited sleep is called inside each fetch helper before
    every API request.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Number of new records added to ``Player_Game_Logs``.
    """
    logger.info("=== SmartPicksProAI — Incremental Update ===")
    setup_db.create_tables(db_path)

    conn = sqlite3.connect(db_path)
    try:
        last_date = _get_last_game_date(conn)
        if last_date is None:
            logger.info(
                "Games table is empty — running initial pull to seed the database."
            )
            conn.close()
            result = initial_pull.run_initial_pull(db_path)
            count = (result or {}).get("logs_inserted", 0)
            # Re-open so the finally block can close it cleanly.
            conn = sqlite3.connect(db_path)
            logger.info(
                "=== Initial seed complete. %d log records loaded. ===", count
            )
            return count

        yesterday = date.today() - timedelta(days=1)
        date_from = last_date + timedelta(days=1)

        if date_from > yesterday:
            logger.info(
                "Database is already up to date (last game date: %s).", last_date
            )
            # Still sync today's schedule so the games/today endpoint works.
            sync_todays_games(conn)
            conn.commit()
            # Refresh season dashboards even when no new games (standings etc change).
            _refresh_season_dashboards(conn, SEASON)
            conn.commit()
            try:
                injury_count = sync_rotowire_injuries(db_path)
                logger.info("RotoWire injury sync: %d rows upserted.", injury_count)
            except Exception:
                logger.exception(
                    "RotoWire injury sync failed — continuing without injury data."
                )
            try:
                cbs_count = sync_cbs_injuries(db_path)
                logger.info("CBS injury sync: %d rows upserted.", cbs_count)
            except Exception:
                logger.exception(
                    "CBS injury sync failed — continuing without CBS injury data."
                )
            return 0

        logger.info(
            "Updating from %s to %s.", date_from.isoformat(), yesterday.isoformat()
        )

        raw = _fetch_logs_for_range(date_from, yesterday)

        if raw.empty:
            logger.info("No new game data found for the requested date range.")
            # Still sync today's schedule so the games/today endpoint works.
            sync_todays_games(conn)
            conn.commit()
            _refresh_season_dashboards(conn, SEASON)
            conn.commit()
            try:
                injury_count = sync_rotowire_injuries(db_path)
                logger.info("RotoWire injury sync: %d rows upserted.", injury_count)
            except Exception:
                logger.exception(
                    "RotoWire injury sync failed — continuing without injury data."
                )
            try:
                cbs_count = sync_cbs_injuries(db_path)
                logger.info("CBS injury sync: %d rows upserted.", cbs_count)
            except Exception:
                logger.exception(
                    "CBS injury sync failed — continuing without CBS injury data."
                )
            return 0

        _upsert_players(raw, conn)
        _upsert_games(raw, conn)
        new_log_count = _upsert_logs(raw, conn)

        # Also update Team_Game_Stats from team-level logs.
        raw_team = _fetch_logs_for_range(date_from, yesterday, player_or_team="T")
        _upsert_team_game_stats(raw_team, conn)

        # Back-fill home/away scores from Team_Game_Stats into Games.
        initial_pull.populate_game_scores(conn)

        # Refresh season-level pace/ortg/drtg on the Teams table.
        initial_pull.update_team_season_stats(conn)

        # Refresh Defense_Vs_Position multipliers.
        initial_pull.populate_defense_vs_position(conn, SEASON)

        # Pre-populate today's scheduled games so GET /api/games/today
        # can be served entirely from the database.
        sync_todays_games(conn)

        conn.commit()

        # --- Refresh season-level dashboards ---
        _refresh_season_dashboards(conn, SEASON)
        conn.commit()

        # --- Fetch advanced box scores for new games ---
        new_game_ids = _get_completed_game_ids_in_range(conn, date_from, yesterday)
        if new_game_ids:
            logger.info("Fetching advanced box scores for %d new games.", len(new_game_ids))
            initial_pull.populate_game_advanced_box_scores(conn, SEASON, new_game_ids)
            conn.commit()

        logger.info(
            "=== Update complete. %d new log records added. ===", new_log_count
        )

        # --- Sync RotoWire injury report ---
        try:
            injury_count = sync_rotowire_injuries(db_path)
            logger.info("RotoWire injury sync: %d rows upserted.", injury_count)
        except Exception:
            logger.exception(
                "RotoWire injury sync failed — continuing without injury data."
            )

        # --- Sync CBS Sports injury report ---
        try:
            cbs_count = sync_cbs_injuries(db_path)
            logger.info("CBS injury sync: %d rows upserted.", cbs_count)
        except Exception:
            logger.exception(
                "CBS injury sync failed — continuing without CBS injury data."
            )

        return new_log_count
    finally:
        conn.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    run_update()
