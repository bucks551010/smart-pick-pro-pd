# ============================================================
# FILE: data/nba_data_service.py
# PURPOSE: Thin delegation layer that routes all NBA data
#          retrieval through the local ETL database
#          (db/smartpicks.db).
#
#          This module preserves the public API that every page
#          and engine module imports (get_todays_games, etc.).
#
# POLICY: DB-ONLY — no live nba_api calls during predictions
#         or analysis.  Data must be populated by the ETL
#         initial pull *before* the app uses it.  If the data
#         is not in the database, an empty result is returned.
#
# DATA SOURCES:
#   1. Local SQLite DB (db/smartpicks.db) — populated by ETL
#   2. PrizePicks / Underdog / DraftKings (via platform_fetcher.py)
#      — props only, unchanged
# ============================================================

from pathlib import Path as _Path
import datetime as _datetime
import logging as _logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = _logging.getLogger(__name__)

# Import utility-layer cache helpers for cross-module cache management.
# FileCache provides file-based caching; used by clear_caches() to
# clear downstream caches in live_data_fetcher and roster_engine.
try:
    from utils.cache import FileCache as _FileCache
    _HAS_FILE_CACHE = True
except ImportError:
    _HAS_FILE_CACHE = False

# Import retry helper for the refresh_all_data convenience function.
try:
    from utils.retry import retry_with_backoff as _retry_with_backoff
    _HAS_RETRY = True
except ImportError:
    _HAS_RETRY = False

# ── Re-export every public symbol from live_data_fetcher ─────
# Pages import constants and path objects from this module;
# live_data_fetcher defines them identically.
from data.live_data_fetcher import (               # noqa: F401 – re-exports
    # Path constants
    DATA_DIRECTORY,
    PLAYERS_CSV_PATH,
    TEAMS_CSV_PATH,
    DEFENSIVE_RATINGS_CSV_PATH,
    LAST_UPDATED_JSON_PATH,
    INJURY_STATUS_JSON_PATH,
    # Tuning constants
    API_DELAY_SECONDS,
    FALLBACK_POINTS_STD_RATIO,
    FALLBACK_REBOUNDS_STD_RATIO,
    FALLBACK_ASSISTS_STD_RATIO,
    FALLBACK_THREES_STD_RATIO,
    FALLBACK_STEALS_STD_RATIO,
    FALLBACK_BLOCKS_STD_RATIO,
    FALLBACK_TURNOVERS_STD_RATIO,
    MIN_MINUTES_THRESHOLD,
    GP_ABSENT_THRESHOLD,
    MIN_TEAM_GP_FOR_RECENCY_CHECK,
    HOT_TREND_THRESHOLD,
    COLD_TREND_THRESHOLD,
    DEFAULT_VEGAS_SPREAD,
    DEFAULT_GAME_TOTAL,
    ESPN_API_TIMEOUT_SECONDS,
    INACTIVE_INJURY_STATUSES,
    GTD_INJURY_STATUSES,
    # Team lookups
    TEAM_NAME_TO_ABBREVIATION,
    NBA_API_ABBREV_TO_OURS,
    TEAM_CONFERENCE,
    # Timestamp functions
    save_last_updated,
    load_last_updated,
    # Staleness
    get_teams_staleness_warning,
    # Cached roster helper
    get_cached_roster,
    # Season helper
    _current_season,
)

# Import live_data_fetcher functions under private names so we can
# expose them with the current ``get_*`` naming convention.
from data.live_data_fetcher import (
    fetch_todays_games as _ldf_fetch_todays_games,
    fetch_todays_players_only as _ldf_fetch_todays_players,
    fetch_player_recent_form as _ldf_fetch_player_recent_form,
    fetch_player_stats as _ldf_fetch_player_stats,
    fetch_team_stats as _ldf_fetch_team_stats,
    fetch_defensive_ratings as _ldf_fetch_defensive_ratings,
    fetch_player_game_log as _ldf_fetch_player_game_log,
    fetch_all_data as _ldf_fetch_all_data,
    fetch_all_todays_data as _ldf_fetch_all_todays_data,
    fetch_active_rosters as _ldf_fetch_active_rosters,
    refresh_from_etl as _ldf_refresh_from_etl,          # noqa: F401
    full_refresh_from_etl as _ldf_full_refresh_from_etl, # noqa: F401
)


# ============================================================
# ETL DB helpers — DB-only, no live API fallback
# ============================================================

try:
    from data.etl_data_service import is_db_available as _is_db_available
except ImportError:
    def _is_db_available():          # type: ignore[misc]
        return False

# Optional Streamlit import — used for @st.cache_data on public data
# functions.  Falls back to an identity decorator when running outside
# the Streamlit server (ETL scripts, unit tests, etc.).
try:
    import streamlit as _st_nba_svc
    _cache_data = _st_nba_svc.cache_data
except ImportError:
    def _cache_data(ttl=None, show_spinner=True):  # type: ignore[misc]
        def _d(fn):
            fn.clear = lambda: None
            return fn
        return _d

# Build a reverse lookup: abbreviation → team full name
_ABBREVIATION_TO_TEAM_NAME: dict[str, str] = {
    v: k for k, v in TEAM_NAME_TO_ABBREVIATION.items()
}


def _normalize_db_games(db_games: list[dict]) -> list[dict]:
    """
    Convert ETL DB game dicts to the format Streamlit pages expect.

    DB format:  {game_id, game_date, matchup, home_score, away_score}
    App format: {game_id, game_date, home_team, away_team,
                 home_team_name, away_team_name, vegas_spread, game_total, ...}
    """
    normalised: list[dict] = []
    for g in (db_games or []):
        matchup = g.get("matchup", "") or ""
        away_team = ""
        home_team = ""

        # Parse matchup: "ATL vs. NYK" or "ATL @ NYK"
        for sep in (" vs. ", " vs ", " @ "):
            if sep in matchup:
                parts = matchup.split(sep, 1)
                away_team = parts[0].strip()
                home_team = parts[1].strip()
                break

        normalised.append({
            "game_id":        str(g.get("game_id", "")),
            "game_date":      str(g.get("game_date", "")),
            "home_team":      home_team,
            "away_team":      away_team,
            "home_team_name": _ABBREVIATION_TO_TEAM_NAME.get(home_team, home_team),
            "away_team_name": _ABBREVIATION_TO_TEAM_NAME.get(away_team, away_team),
            "matchup":        matchup,
            "home_score":     g.get("home_score", 0),
            "away_score":     g.get("away_score", 0),
            "vegas_spread":   g.get("vegas_spread", DEFAULT_VEGAS_SPREAD),
            "game_total":     g.get("game_total", DEFAULT_GAME_TOTAL),
        })
    return normalised


def _normalize_db_player(p: dict) -> dict:
    """
    Convert an ETL DB player dict to the CSV-format keys the engine expects.

    DB keys:  first_name, last_name, team_abbreviation, ppg, rpg, apg, …
    App keys: name, team, points_avg, rebounds_avg, assists_avg, …
    """
    return {
        "player_id":       p.get("player_id"),
        "name":            f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
        "team":            p.get("team_abbreviation", ""),
        "position":        p.get("position") or "",
        "gp":              p.get("gp", 0),
        # Season averages
        "points_avg":      p.get("ppg", 0.0),
        "rebounds_avg":    p.get("rpg", 0.0),
        "assists_avg":     p.get("apg", 0.0),
        "steals_avg":      p.get("spg", 0.0),
        "blocks_avg":      p.get("bpg", 0.0),
        "turnovers_avg":   p.get("topg", 0.0),
        "minutes_avg":     p.get("mpg", 0.0),
        "threes_avg":      p.get("fg3_avg", 0.0),
        "ftm_avg":         p.get("ftm_avg", 0.0),
        "fta_avg":         p.get("fta_avg", 0.0),
        "ft_pct":          p.get("ft_pct_avg", 0.0),
        "fgm_avg":         p.get("fgm_avg", 0.0),
        "fga_avg":         p.get("fga_avg", 0.0),
        "fg_pct":          p.get("fg_pct_avg", 0.0),
        "oreb_avg":        p.get("oreb_avg", 0.0),
        "dreb_avg":        p.get("dreb_avg", 0.0),
        "pf_avg":          p.get("pf_avg", 0.0),
        "plus_minus_avg":  p.get("plus_minus_avg", 0.0),
        # Standard deviations — pass through
        "points_std":      p.get("points_std", 0.0),
        "rebounds_std":    p.get("rebounds_std", 0.0),
        "assists_std":     p.get("assists_std", 0.0),
        "threes_std":      p.get("threes_std", 0.0),
        "steals_std":      p.get("steals_std", 0.0),
        "blocks_std":      p.get("blocks_std", 0.0),
        "turnovers_std":   p.get("turnovers_std", 0.0),
        "ftm_std":         p.get("ftm_std", 0.0),
        "oreb_std":        p.get("oreb_std", 0.0),
        "plus_minus_std":  p.get("plus_minus_std", 0.0),
    }


# ============================================================
# Public API — DB-only wrappers (no live API fallback)
# ============================================================

@_cache_data(ttl=60, show_spinner=False)
def get_todays_games():
    """Retrieve tonight's NBA games.

    Tries the local DB first (for games already played today).  If the DB
    has no rows for today — the common case for *scheduled* games that
    haven't tipped off yet — falls back to the live fetcher which queries
    ScoreboardV3 / ESPN / Live Scoreboard.
    """
    if _is_db_available():
        try:
            from data.etl_data_service import get_todays_games as _db_get_games
            db_result = _db_get_games()
            if db_result:
                _logger.info("get_todays_games: loaded %d game(s) from DB", len(db_result))
                return _normalize_db_games(db_result)
        except Exception as exc:
            _logger.debug("get_todays_games DB path failed: %s", exc)

    # DB has no games for today — fall back to live fetcher
    # (scheduled games won't be in the Games table until they're played)
    try:
        live_games = _ldf_fetch_todays_games()
        if live_games:
            _logger.info("get_todays_games: loaded %d game(s) from live fetcher", len(live_games))
            return live_games
    except Exception as exc:
        _logger.warning("get_todays_games live fetcher failed: %s", exc)

    _logger.warning("get_todays_games: no games from DB or live — returning empty list")
    return []


def get_todays_players(todays_games, progress_callback=None,
                       precomputed_injury_map=None):
    """Retrieve players for tonight's games.

    Tries the local DB first.  Falls back to the live fetcher (which
    writes players.csv and returns a bool) when the DB has no player
    data for the teams playing tonight.
    """
    if _is_db_available() and todays_games:
        try:
            from data.etl_data_service import get_players_for_teams as _db_get_players

            team_abbrevs = set()
            for g in todays_games:
                for key in ("home_team", "away_team"):
                    t = str(g.get(key, "")).upper().strip()
                    if t:
                        team_abbrevs.add(t)

            if team_abbrevs:
                db_players = _db_get_players(list(team_abbrevs))
                if db_players:
                    normalised = [_normalize_db_player(p) for p in db_players]
                    _logger.info(
                        "get_todays_players: loaded %d player(s) from DB for %d team(s)",
                        len(normalised), len(team_abbrevs),
                    )
                    return normalised
        except Exception as exc:
            _logger.debug("get_todays_players DB path failed: %s", exc)

    # DB has no player data — fall back to live fetcher
    if todays_games:
        try:
            result = _ldf_fetch_todays_players(
                todays_games,
                progress_callback=progress_callback,
                precomputed_injury_map=precomputed_injury_map,
            )
            # fetch_todays_players_only returns True/False (bool) on success/failure,
            # NOT a list.  It writes players.csv as a side-effect.  When it
            # succeeds, reload from CSV so callers always get an iterable list.
            if isinstance(result, bool):
                if result:
                    _logger.info("get_todays_players: live fetcher wrote players.csv — reloading")
                    try:
                        from data.data_manager import load_players_data as _ldp
                        loaded = _ldp()
                        if loaded:
                            return loaded
                    except Exception as _reload_exc:
                        _logger.debug("get_todays_players reload failed: %s", _reload_exc)
                else:
                    _logger.warning("get_todays_players: live fetcher returned False")
            elif result:
                _logger.info("get_todays_players: live fetcher returned %d players", len(result))
                return result
        except Exception as exc:
            _logger.warning("get_todays_players live fetcher failed: %s", exc)

    _logger.warning("get_todays_players: no players from DB or live — returning empty")
    return []


def get_player_recent_form(player_id, last_n_games=10):
    """Get a player's recent-form stats from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_player_last_n_games
            db_rows = get_player_last_n_games(int(player_id), n=last_n_games)
            if db_rows:
                _logger.info("get_player_recent_form(%s): loaded %d game(s) from DB",
                             player_id, len(db_rows))
                return db_rows
        except Exception as exc:
            _logger.debug("get_player_recent_form DB path failed: %s", exc)

    _logger.debug("get_player_recent_form(%s): no data in DB", player_id)
    return []


@_cache_data(ttl=300, show_spinner=False)
def get_player_stats(progress_callback=None):
    """Retrieve all active player season stats from the local DB only."""
    if _is_db_available():
        try:
            from data.etl_data_service import get_all_players as _db_get_all
            db_players = _db_get_all()
            if db_players:
                normalised = [_normalize_db_player(p) for p in db_players]
                _logger.info("get_player_stats: loaded %d player(s) from DB", len(normalised))
                return normalised
        except Exception as exc:
            _logger.debug("get_player_stats DB path failed: %s", exc)

    _logger.warning("get_player_stats: no players in DB — returning empty list")
    return []


@_cache_data(ttl=300, show_spinner=False)
def get_team_stats(progress_callback=None):
    """Retrieve team-level stats from the local DB only."""
    if _is_db_available():
        try:
            from data.etl_data_service import get_all_teams as _db_get_teams
            db_teams = _db_get_teams()
            if db_teams:
                _logger.info("get_team_stats: loaded %d team(s) from DB", len(db_teams))
                return db_teams
        except Exception as exc:
            _logger.debug("get_team_stats DB path failed: %s", exc)

    _logger.warning("get_team_stats: no teams in DB — returning empty list")
    return []


def get_defensive_ratings(force=False, progress_callback=None):
    """Retrieve defensive ratings from the local DB only.

    Note: The *force* parameter is retained for backward compatibility
    with existing callers but has no effect — data is always read from
    the DB without any live API call.
    """
    if _is_db_available():
        try:
            from data.etl_data_service import get_all_defense_vs_position as _db_get_dvp
            db_dvp = _db_get_dvp()
            if db_dvp:
                _logger.info("get_defensive_ratings: loaded %d row(s) from DB", len(db_dvp))
                return db_dvp
        except Exception as exc:
            _logger.debug("get_defensive_ratings DB path failed: %s", exc)

    _logger.warning("get_defensive_ratings: no data in DB — returning empty list")
    return []


def get_player_game_log(player_id, last_n_games=20):
    """Retrieve a player's game log from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_player_game_logs as _db_get_game_logs
            db_logs = _db_get_game_logs(int(player_id))
            if db_logs:
                # Honour last_n_games limit
                result = db_logs[:last_n_games] if last_n_games else db_logs
                _logger.info("get_player_game_log(%s): loaded %d log(s) from DB",
                             player_id, len(result))
                return result
        except Exception as exc:
            _logger.debug("get_player_game_log DB path failed: %s", exc)

    _logger.debug("get_player_game_log(%s): no game log in DB", player_id)
    return []


def get_all_data(progress_callback=None, targeted=False, todays_games=None):
    """Retrieve all NBA data (games, players, teams) via nba_api."""
    return _ldf_fetch_all_data(
        progress_callback=progress_callback,
        targeted=targeted,
        todays_games=todays_games,
    )


def get_all_todays_data(progress_callback=None):
    """One-click: retrieve games → players → props for tonight (DB-first sub-calls)."""
    return _ldf_fetch_all_todays_data(progress_callback=progress_callback)


def get_active_rosters(team_abbrevs=None, progress_callback=None):
    """Retrieve active rosters from the local DB only."""
    if _is_db_available() and team_abbrevs:
        try:
            from data.etl_data_service import get_rosters_for_teams as _db_get_rosters
            db_rosters = _db_get_rosters(list(team_abbrevs))
            if db_rosters and any(db_rosters.values()):
                _logger.info("get_active_rosters: loaded rosters for %d team(s) from DB",
                             sum(1 for v in db_rosters.values() if v))
                return db_rosters
        except Exception as exc:
            _logger.debug("get_active_rosters DB path failed: %s", exc)

    _logger.warning("get_active_rosters: no rosters in DB — returning empty dict")
    return {}


# ============================================================
# Functions that exist only in the current codebase (no old
# live_data_fetcher equivalent).  Kept with graceful fallbacks.
# ============================================================

def get_standings(progress_callback=None) -> list:
    """
    Retrieve current NBA standings from the local DB only.

    Returns an empty list if no standings data is in the DB.
    """
    if progress_callback:
        progress_callback(0, 10, "Retrieving NBA standings…")

    # ── DB only ──────────────────────────────────────────────
    if _is_db_available():
        try:
            from data.etl_data_service import get_standings as _db_get_standings
            db_standings = _db_get_standings()
            if db_standings:
                _logger.info("get_standings: loaded %d row(s) from DB", len(db_standings))
                if progress_callback:
                    progress_callback(10, 10, f"Standings loaded ({len(db_standings)} teams).")
                return db_standings
        except Exception as exc:
            _logger.debug("get_standings DB path failed: %s", exc)

    _logger.warning("get_standings: no standings in DB — returning empty list")
    return []


def get_player_news(player_name=None, limit=20) -> list:
    """
    Retrieve recent NBA news.

    Primary source: ETL database (derives news from game logs, injuries,
    and standings data).
    Returns an empty list if the DB is unavailable.
    """
    if _is_db_available():
        try:
            from data.etl_data_service import get_player_news_from_db
            db_news = get_player_news_from_db(limit=limit)
            if db_news:
                # If player_name filter is specified, filter results
                if player_name:
                    name_lower = player_name.strip().lower()
                    db_news = [
                        n for n in db_news
                        if name_lower in (n.get("player_name", "") or "").lower()
                    ]
                _logger.info("get_player_news: loaded %d item(s) from DB", len(db_news))
                return db_news
        except Exception as exc:
            _logger.debug("get_player_news DB path failed: %s", exc)

    return []


# ============================================================
# nba_live_fetcher.py wrappers — new NBA API Gateway
# These functions delegate to data/nba_live_fetcher.py, which
# wraps the full breadth of stats.nba.com endpoints.
# ============================================================

try:
    from data.nba_live_fetcher import (
        fetch_player_game_logs as _nlf_fetch_player_game_logs,
        fetch_box_score_traditional as _nlf_fetch_box_score_traditional,
        fetch_box_score_advanced as _nlf_fetch_box_score_advanced,
        fetch_box_score_usage as _nlf_fetch_box_score_usage,
        fetch_player_on_off as _nlf_fetch_player_on_off,
        fetch_player_estimated_metrics as _nlf_fetch_player_estimated_metrics,
        fetch_player_fantasy_profile as _nlf_fetch_player_fantasy_profile,
        fetch_rotations as _nlf_fetch_rotations,
        fetch_schedule as _nlf_fetch_schedule,
        fetch_todays_scoreboard as _nlf_fetch_todays_scoreboard,
        fetch_box_score_matchups as _nlf_fetch_box_score_matchups,
        fetch_hustle_box_score as _nlf_fetch_hustle_box_score,
        fetch_defensive_box_score as _nlf_fetch_defensive_box_score,
        fetch_scoring_box_score as _nlf_fetch_scoring_box_score,
        fetch_tracking_box_score as _nlf_fetch_tracking_box_score,
        fetch_four_factors_box_score as _nlf_fetch_four_factors_box_score,
        fetch_player_shooting_splits as _nlf_fetch_player_shooting_splits,
        fetch_shot_chart as _nlf_fetch_shot_chart,
        fetch_player_clutch_stats as _nlf_fetch_player_clutch_stats,
        fetch_team_lineups as _nlf_fetch_team_lineups,
        fetch_team_dashboard as _nlf_fetch_team_dashboard,
        fetch_standings as _nlf_fetch_standings,
        fetch_team_game_logs as _nlf_fetch_team_game_logs,
        fetch_player_year_over_year as _nlf_fetch_player_year_over_year,
        fetch_player_vs_player as _nlf_fetch_player_vs_player,
        fetch_win_probability as _nlf_fetch_win_probability,
        fetch_play_by_play as _nlf_fetch_play_by_play,
        fetch_game_summary as _nlf_fetch_game_summary,
        fetch_league_leaders as _nlf_fetch_league_leaders,
        fetch_team_streak_finder as _nlf_fetch_team_streak_finder,
    )
    _NLF_AVAILABLE = True
except Exception as _nlf_import_err:
    _logger.debug("nba_live_fetcher not available: %s", _nlf_import_err)
    _NLF_AVAILABLE = False


def _nlf_unavailable_list(*_args, **_kwargs):
    return []


def _nlf_unavailable_dict(*_args, **_kwargs):
    return {}


# ── TIER 1: Critical endpoints ───────────────────────────────────────────────

def get_player_game_logs_v2(player_id: int, season: str | None = None, last_n: int = 0) -> list:
    """Return per-game stats from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_player_game_logs as _db_get_logs
            db_logs = _db_get_logs(int(player_id), season=season)
            if db_logs:
                result = db_logs[:last_n] if last_n else db_logs
                _logger.info("get_player_game_logs_v2(%s): loaded %d log(s) from DB",
                             player_id, len(result))
                return result
        except Exception as exc:
            _logger.debug("get_player_game_logs_v2 DB path failed: %s", exc)
    return []


def get_box_score_traditional(game_id: str, period: int = 0) -> dict:
    """Return the traditional box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_box_score_traditional_from_db
            db_result = get_box_score_traditional_from_db(game_id)
            if db_result:
                _logger.info("get_box_score_traditional(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_box_score_traditional DB path failed: %s", exc)
    return {}


def get_box_score_advanced(game_id: str) -> dict:
    """Return the advanced box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_box_score_advanced_from_db
            db_result = get_box_score_advanced_from_db(game_id)
            if db_result:
                _logger.info("get_box_score_advanced(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_box_score_advanced DB path failed: %s", exc)
    return {}


def get_box_score_usage(game_id: str) -> dict:
    """Return usage statistics box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_box_score_usage_from_db
            db_result = get_box_score_usage_from_db(game_id)
            if db_result:
                _logger.info("get_box_score_usage(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_box_score_usage DB path failed: %s", exc)
    return {}


def get_player_on_off(team_id: int, season: str | None = None) -> dict:
    """Return On/Off court differential stats — not available in local DB."""
    return {}


def get_player_estimated_metrics(season: str | None = None) -> list:
    """Return estimated advanced metrics from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_player_estimated_metrics as _db_get_est
            db_result = _db_get_est(season=season)
            if db_result:
                _logger.info("get_player_estimated_metrics: loaded %d row(s) from DB",
                             len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_player_estimated_metrics DB path failed: %s", exc)
    return []


def get_player_fantasy_profile(player_id: int, season: str | None = None) -> dict:
    """Return fantasy-relevant stat splits — not available in local DB."""
    return {}


def get_rotations(game_id: str) -> dict:
    """Return in/out rotation data from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_rotations as _db_get_rotations
            db_result = _db_get_rotations(game_id)
            if db_result:
                _logger.info("get_rotations(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_rotations DB path failed: %s", exc)
    return {}


def get_schedule(game_date: str | None = None) -> list:
    """Return the game schedule from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_schedule_from_db
            db_result = get_schedule_from_db(game_date=game_date)
            if db_result:
                _logger.info("get_schedule: loaded %d game(s) from DB", len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_schedule DB path failed: %s", exc)
    return []


def get_todays_scoreboard() -> dict:
    """Return today's full scoreboard — not available in local DB."""
    return {}


# ── TIER 2: High-value endpoints ─────────────────────────────────────────────

def get_box_score_matchups(game_id: str) -> dict:
    """Return defensive matchup data from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_box_score_matchups_from_db
            db_result = get_box_score_matchups_from_db(game_id)
            if db_result:
                _logger.info("get_box_score_matchups(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_box_score_matchups DB path failed: %s", exc)
    return {}


def get_hustle_box_score(game_id: str) -> dict:
    """Return hustle stats box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_hustle_box_score_from_db
            db_result = get_hustle_box_score_from_db(game_id)
            if db_result:
                _logger.info("get_hustle_box_score(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_hustle_box_score DB path failed: %s", exc)
    return {}


def get_defensive_box_score(game_id: str) -> dict:
    """Return defensive statistics box score — not available in local DB."""
    return {}


def get_scoring_box_score(game_id: str) -> dict:
    """Return scoring breakdown box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_scoring_box_score_from_db
            db_result = get_scoring_box_score_from_db(game_id)
            if db_result:
                _logger.info("get_scoring_box_score(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_scoring_box_score DB path failed: %s", exc)
    return {}


def get_tracking_box_score(game_id: str) -> dict:
    """Return player-tracking box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_tracking_box_score_from_db
            db_result = get_tracking_box_score_from_db(game_id)
            if db_result:
                _logger.info("get_tracking_box_score(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_tracking_box_score DB path failed: %s", exc)
    return {}


def get_four_factors_box_score(game_id: str) -> dict:
    """Return four-factors box score from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_box_score_four_factors_from_db
            db_result = get_box_score_four_factors_from_db(game_id)
            if db_result:
                _logger.info("get_four_factors_box_score(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_four_factors_box_score DB path failed: %s", exc)
    return {}


def get_player_shooting_splits(player_id: int, season: str | None = None) -> dict:
    """Return detailed shooting splits — not available in local DB."""
    return {}


def get_shot_chart_v2(player_id: int, season: str | None = None) -> list:
    """Return shot chart data from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_shot_chart_from_db
            db_result = get_shot_chart_from_db(int(player_id), season=season)
            if db_result:
                _logger.info("get_shot_chart_v2(%s): loaded %d shot(s) from DB",
                             player_id, len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_shot_chart_v2 DB path failed: %s", exc)
    return []


def get_player_clutch_stats(season: str | None = None) -> list:
    """Return clutch-time stats from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_player_clutch_stats_from_db
            db_result = get_player_clutch_stats_from_db(season=season)
            if db_result:
                _logger.info("get_player_clutch_stats: loaded %d row(s) from DB",
                             len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_player_clutch_stats DB path failed: %s", exc)
    return []


def get_team_lineups(team_id: int, season: str | None = None) -> list:
    """Return 5-man lineup stats — not available in local DB."""
    return []


def get_team_dashboard(team_id: int, season: str | None = None) -> dict:
    """Return team dashboard stats — not available in local DB."""
    return {}


def get_team_game_logs(team_id: int, season: str | None = None, last_n: int = 0) -> list:
    """Return per-game stats for a team from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_team_game_logs as _db_get_tlogs
            db_result = _db_get_tlogs(int(team_id), season=season, last_n=last_n)
            if db_result:
                _logger.info("get_team_game_logs(%s): loaded %d game(s) from DB",
                             team_id, len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_team_game_logs DB path failed: %s", exc)
    return []


def get_player_year_over_year(player_id: int) -> list:
    """Return year-over-year career stats from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_player_career_stats_from_db
            db_result = get_player_career_stats_from_db(int(player_id))
            if db_result:
                _logger.info("get_player_year_over_year(%s): loaded %d season(s) from DB",
                             player_id, len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_player_year_over_year DB path failed: %s", exc)
    return []


# ── TIER 3: Reference & context endpoints ────────────────────────────────────

def get_player_vs_player(
    player1_id: int,
    player2_id: int,
    season: str | None = None,
) -> dict:
    """Return head-to-head stats — not available in local DB."""
    return {}


def get_win_probability(game_id: str) -> dict:
    """Return win probability data from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_win_probability_from_db
            db_result = get_win_probability_from_db(game_id)
            if db_result:
                _logger.info("get_win_probability(%s): loaded from DB", game_id)
                return db_result
        except Exception as exc:
            _logger.debug("get_win_probability DB path failed: %s", exc)
    return {}


def get_play_by_play_v2(game_id: str) -> list:
    """Return play-by-play events from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_play_by_play_from_db
            db_result = get_play_by_play_from_db(game_id)
            if db_result:
                _logger.info("get_play_by_play_v2(%s): loaded %d event(s) from DB",
                             game_id, len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_play_by_play_v2 DB path failed: %s", exc)
    return []


def get_game_summary(game_id: str) -> dict:
    """Return high-level game summary — not available in local DB."""
    return {}


def get_league_leaders(stat_category: str = "PTS", season: str | None = None) -> list:
    """Return top players for a given stat category from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_league_leaders_from_db
            db_result = get_league_leaders_from_db(stat_category=stat_category, season=season)
            if db_result:
                _logger.info("get_league_leaders: loaded %d row(s) from DB", len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_league_leaders DB path failed: %s", exc)
    return []


def get_team_streak_finder(team_id: int, season: str | None = None) -> list:
    """Return full season game log for a team from the local DB only."""
    if _is_db_available():
        try:
            from data.db_service import get_team_game_logs as _db_get_tlogs
            db_result = _db_get_tlogs(int(team_id), season=season)
            if db_result:
                _logger.info("get_team_streak_finder(%s): loaded %d game(s) from DB",
                             team_id, len(db_result))
                return db_result
        except Exception as exc:
            _logger.debug("get_team_streak_finder DB path failed: %s", exc)
    return []


# ── End nba_live_fetcher.py wrappers ─────────────────────────────────────────


def get_standings_from_nba_api(season: str | None = None) -> list:
    """
    Retrieve NBA standings via nba_stats_service.

    Parameters
    ----------
    season : str | None
        Season string (e.g. "2024-25").  Defaults to current season.

    Returns
    -------
    list[dict]
        Standings rows with keys: team_abbreviation, team_name,
        conference, conference_rank, wins, losses, win_pct, streak,
        last_10.
    """
    try:
        from data.nba_stats_service import get_league_standings
        return get_league_standings(season=season)
    except Exception as exc:
        _logger.warning("get_standings_from_nba_api failed: %s", exc)
    return []


def get_game_logs_from_nba_api(
    player_name: str,
    season: str | None = None,
) -> list:
    """
    Resolve *player_name* to a player ID and fetch game logs via
    nba_stats_service.

    Parameters
    ----------
    player_name : str
        Full player name (case-insensitive).
    season : str | None
        Season string (e.g. "2024-25").  Defaults to current season.

    Returns
    -------
    list[dict]
        Per-game stat dicts with nba_api column names (PTS, REB, …).
        Returns [] if the player cannot be found or the call fails.
    """
    try:
        from data.player_profile_service import get_player_id
        from data.nba_stats_service import get_player_game_logs

        player_id = get_player_id(player_name)
        if not player_id:
            _logger.debug("get_game_logs_from_nba_api: no player ID for %r", player_name)
            return []

        return get_player_game_logs(player_id, season=season)
    except Exception as exc:
        _logger.warning("get_game_logs_from_nba_api(%r) failed: %s", player_name, exc)
    return []


def refresh_historical_data_for_tonight(
    games=None,
    last_n_games=30,
    progress_callback=None,
) -> dict:
    """
    Auto-retrieve historical game logs for tonight's players and
    update CLV closing lines.

    Uses nba_api for player game logs.  Stores results in the game
    log cache for the Backtester page.
    """
    results = {"players_refreshed": 0, "clv_updated": 0, "errors": 0}

    if games is None:
        try:
            import streamlit as _st
            games = _st.session_state.get("todays_games", [])
        except Exception:
            games = []

    if not games:
        _logger.debug("refresh_historical_data_for_tonight: no games — skipping")
        return results

    playing_teams = set()
    for g in games:
        for key in ("home_team", "away_team"):
            t = str(g.get(key, "")).upper().strip()
            if t:
                playing_teams.add(t)

    if not playing_teams:
        return results

    try:
        from data.data_manager import load_players_data as _load_players
        all_players = _load_players()
    except Exception as exc:
        _logger.warning("refresh_historical_data_for_tonight: could not load players — %s", exc)
        return results

    tonight_players = [
        p for p in all_players
        if str(p.get("team", "")).upper().strip() in playing_teams
        and p.get("player_id")
    ]

    if not tonight_players:
        _logger.debug("refresh_historical_data_for_tonight: no players with IDs found")
        return results

    total = len(tonight_players)
    if progress_callback:
        progress_callback(0, total, f"Retrieving historical logs for {total} player(s)…")

    for idx, p in enumerate(tonight_players):
        player_id = p.get("player_id")
        player_name = p.get("name", f"ID-{player_id}")
        try:
            # DB-only: use local Player_Game_Logs only
            logs = None
            if _is_db_available():
                try:
                    from data.db_service import get_player_game_logs as _db_gl
                    db_logs = _db_gl(int(player_id))
                    if db_logs:
                        logs = db_logs[:last_n_games]
                except Exception:
                    pass
            if logs:
                try:
                    from data.game_log_cache import save_game_logs_to_cache as _save_cache
                    _save_cache(player_name, logs)
                    results["players_refreshed"] += 1
                except Exception:
                    results["errors"] += 1
        except Exception:
            results["errors"] += 1
        if progress_callback:
            progress_callback(idx + 1, total, f"Cached logs for {player_name}")

    # Auto-update CLV closing lines
    try:
        from engine.clv_tracker import auto_update_closing_lines as _clv_update
        clv_result = _clv_update(days_back=1)
        results["clv_updated"] = clv_result.get("updated", 0)
    except Exception as exc:
        _logger.debug("refresh_historical_data_for_tonight: CLV update skipped — %s", exc)

    _logger.info(
        "refresh_historical_data_for_tonight: players_refreshed=%d, clv_updated=%d, errors=%d",
        results["players_refreshed"], results["clv_updated"], results["errors"],
    )
    return results


# ============================================================
# NBADataService — class-based API wrapper
# ============================================================

class NBADataService:
    """
    Class-based service for NBA data operations.

    Wraps the existing module-level functions in an OOP interface,
    providing cache management and bulk-refresh convenience methods.
    All callers can continue using the module-level functions directly;
    this class is offered for callers that prefer dependency injection.
    """

    def __init__(self):
        if _HAS_FILE_CACHE:
            self.cache = _FileCache(cache_dir="cache/service", ttl_hours=1)
        else:
            self.cache = None

        try:
            from data.roster_engine import RosterEngine
            self.roster_engine = RosterEngine()
        except Exception:
            self.roster_engine = None

    # ── Core data methods ─────────────────────────────────────

    def get_todays_games(self):
        """Get today's NBA games."""
        return get_todays_games()

    def get_todays_players(self, games, progress_callback=None,
                           precomputed_injury_map=None):
        """Get players for teams playing today."""
        return get_todays_players(
            games,
            progress_callback=progress_callback,
            precomputed_injury_map=precomputed_injury_map,
        )

    def get_team_stats(self, progress_callback=None):
        """Get team statistics."""
        return get_team_stats(progress_callback=progress_callback)

    def get_injuries(self):
        """Get current injury data via RosterEngine."""
        if self.roster_engine:
            return self.roster_engine.refresh()
        return {}

    # ── Cache & refresh ───────────────────────────────────────

    def clear_caches(self):
        """Clear all caches (delegates to module-level clear_caches)."""
        clear_caches()

    def refresh_all_data(self, progress_callback=None):
        """Refresh all data (delegates to module-level refresh_all_data)."""
        return refresh_all_data(progress_callback=progress_callback)


# ============================================================
# Utility-layer integration — cache management & bulk refresh
# ============================================================

def clear_caches() -> None:
    """
    Clear file-based and in-memory caches across the data layer.

    Clears caches in live_data_fetcher, roster_engine, and the
    in-memory tiered cache used by utils.cache.  Safe to call even
    if some modules are unavailable (graceful no-ops).
    """
    cleared = []

    # 1. In-memory tiered cache (utils.cache.cache_clear)
    try:
        from utils.cache import cache_clear
        cache_clear()
        cleared.append("in-memory")
    except Exception:
        pass

    # 2. File-based cache directories
    if _HAS_FILE_CACHE:
        for cache_dir in ("cache/service", "cache/props", "cache/rosters"):
            try:
                fc = _FileCache(cache_dir=cache_dir, ttl_hours=0)
                fc.clear()
                cleared.append(cache_dir)
            except Exception:
                pass

    _logger.info("clear_caches: cleared %s", ", ".join(cleared) if cleared else "(none)")


def refresh_all_data(progress_callback=None) -> dict:
    """
    Refresh all core data sources with per-source error isolation.

    Fetches games, players, team stats, and injury data.  Each source
    is wrapped in its own try/except so a single failure does not
    block the others.

    Parameters
    ----------
    progress_callback : callable or None
        Called as ``progress_callback(current, total, message)`` to
        report incremental progress (e.g. to a Streamlit progress bar).

    Returns
    -------
    dict
        Keys: ``games``, ``players``, ``team_stats``, ``injuries``,
        ``errors`` (list of error strings for any source that failed).
    """
    result = {
        "games": [],
        "players": [],
        "team_stats": None,
        "injuries": None,
        "errors": [],
    }
    total_steps = 4
    step = 0

    # ── Games ──────────────────────────────────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching today's games…")
    try:
        result["games"] = get_todays_games()
    except Exception as exc:
        _logger.error("refresh_all_data — games failed: %s", exc)
        result["errors"].append(f"Games: {exc}")

    # ── Players (only if games available) ──────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching players…")
    if result["games"]:
        try:
            result["players"] = get_todays_players(result["games"])
        except Exception as exc:
            _logger.error("refresh_all_data — players failed: %s", exc)
            result["errors"].append(f"Players: {exc}")

    # ── Team stats ─────────────────────────────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching team stats…")
    try:
        result["team_stats"] = get_team_stats()
    except Exception as exc:
        _logger.error("refresh_all_data — team stats failed: %s", exc)
        result["errors"].append(f"Team stats: {exc}")

    # ── Injuries ───────────────────────────────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching injury data…")
    try:
        from data.roster_engine import RosterEngine as _RE
        _re = _RE()
        result["injuries"] = _re.refresh()
    except Exception as exc:
        _logger.error("refresh_all_data — injuries failed: %s", exc)
        result["errors"].append(f"Injuries: {exc}")

    _logger.info(
        "refresh_all_data: games=%d, players=%d, errors=%d",
        len(result["games"]),
        len(result["players"]),
        len(result["errors"]),
    )
    return result


# ============================================================
# ETL refresh helpers — thin wrappers around live_data_fetcher
# ============================================================

def refresh_from_etl(progress_callback=None) -> dict:
    """
    Incremental ETL update — fetch only new game logs since the last
    stored date in db/smartpicks.db.

    Args:
        progress_callback (callable | None): (current, total, message).

    Returns:
        dict: {new_games, new_logs, new_players, error (optional)}
    """
    return _ldf_refresh_from_etl(progress_callback=progress_callback)


def full_refresh_from_etl(season: str | None = None, progress_callback=None) -> dict:
    """
    Full ETL pull — re-fetches the entire season from nba_api and
    repopulates db/smartpicks.db.

    Args:
        season (str | None): Season string, e.g. '2025-26'.
        progress_callback (callable | None): (current, total, message).

    Returns:
        dict: {players_inserted, games_inserted, logs_inserted, error (optional)}
    """
    return _ldf_full_refresh_from_etl(season=season, progress_callback=progress_callback)
