"""
data/db_service.py
==================
Single gateway to the local SmartPicks ETL database (db/smartpicks.db).

Replaces: live_data_fetcher.py, nba_live_fetcher.py, nba_stats_service.py,
          nba_data_service.py, data_manager.py

All functions read directly from the local SQLite database — no live API
calls are made.  If the database does not exist yet (fresh install), every
function degrades gracefully and returns an empty result so the rest of
the app keeps working.
"""

from __future__ import annotations

import csv
import datetime
import json
import logging
import math
import os
import re
import sqlite3
import threading as _threading
import unicodedata
from pathlib import Path
from typing import Any

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# Streamlit import — optional so db_service works in non-Streamlit contexts
try:
    import streamlit as st
except ImportError:
    # Provide a no-op decorator mimicking @st.cache_data
    class _FakeCache:
        @staticmethod
        def cache_data(ttl=None, show_spinner=True):
            def decorator(fn):
                fn.clear = lambda: None
                return fn
            return decorator
    st = _FakeCache()  # type: ignore[assignment]

# ── DB path ───────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_DIR", str(_REPO_ROOT / "db"))) / "smartpicks.db"


# ── Connection helper ─────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection | None:
    """Return a read-only SQLite connection, or *None* if the DB doesn't exist."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as exc:
            _logger.warning("db_service: cannot open DB: %s", exc)
            return None


def _rows_to_dicts(rows) -> list[dict]:
    """Convert ``sqlite3.Row`` objects to plain dicts."""
    return [dict(row) for row in rows]


def _r(val, decimals: int = 1) -> float:
    """Safely round a value that may be ``None``."""
    try:
        return round(float(val or 0), decimals)
    except (TypeError, ValueError):
        return 0.0


def _safe_float(val) -> float:
    """Coerce to float, returning 0.0 on failure."""
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _parse_minutes(m) -> float:
    """Parse a minutes value that may be ``'MM:SS'`` or numeric."""
    if m is None:
        return 0.0
    m_str = str(m)
    try:
        if ":" in m_str:
            parts = m_str.split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        return float(m_str)
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE DATA FUNCTIONS (the new clean API)
# ═══════════════════════════════════════════════════════════════════════════════


def get_player_last_n_games(player_id: int, n: int = 10) -> list[dict]:
    """
    Return the last *n* game-log rows for a player, most-recent first.

    Each dict contains: game_date, matchup, pts, reb, ast, stl, blk, tov,
    min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct, oreb,
    dreb, pf, plus_minus, wl.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                g.game_date, g.matchup,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
            LIMIT ?
            """,
            (int(player_id), int(n)),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_player_last_n_games(%s, %s) failed: %s", player_id, n, exc)
        return []
    finally:
        conn.close()


def get_player_averages(player_id: int) -> dict:
    """
    Return season averages for a player from their game logs.

    Keys: gp, ppg, rpg, apg, spg, bpg, topg, mpg, fg3_avg, ftm_avg,
    fta_avg, ft_pct_avg, fgm_avg, fga_avg, fg_pct_avg, oreb_avg, dreb_avg,
    pf_avg, plus_minus_avg, points_std, rebounds_std, assists_std, threes_std.
    """
    from data.etl_data_service import _compute_averages, _get_conn as _etl_conn

    conn = _etl_conn()
    if conn is None:
        return {}
    try:
        return _compute_averages(int(player_id), conn)
    except Exception as exc:
        _logger.warning("get_player_averages(%s) failed: %s", player_id, exc)
        return {}
    finally:
        conn.close()


def get_team(team_id: int) -> dict:
    """
    Return team metadata from the Teams table.

    Keys: team_id, abbreviation, team_name, conference, division, pace,
    ortg, drtg.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        row = conn.execute(
            "SELECT * FROM Teams WHERE team_id = ?", (int(team_id),)
        ).fetchone()
        return dict(row) if row else {}
    except Exception as exc:
        _logger.warning("get_team(%s) failed: %s", team_id, exc)
        return {}
    finally:
        conn.close()


def get_defense_vs_position(
    team_abbrev: str,
    position: str | None = None,
    season: str | None = None,
) -> list[dict]:
    """
    Return defensive multipliers for a team from the Defense_Vs_Position table.

    If *position* is given only that row is returned; otherwise all positions
    for the team.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        if position:
            rows = conn.execute(
                """
                SELECT * FROM Defense_Vs_Position
                WHERE team_abbreviation = ? AND season = ? AND pos = ?
                """,
                (team_abbrev, season, position),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM Defense_Vs_Position
                WHERE team_abbreviation = ? AND season = ?
                """,
                (team_abbrev, season),
            ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_defense_vs_position(%s) failed: %s", team_abbrev, exc)
        return []
    finally:
        conn.close()


def get_team_recent_stats(team_id: int, n: int = 10) -> list[dict]:
    """
    Return the last *n* Team_Game_Stats rows for a team, most-recent first.

    Keys: game_id, team_id, opponent_team_id, is_home, points_scored,
    points_allowed, pace_est, ortg_est, drtg_est, game_date.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT tgs.*, g.game_date
            FROM Team_Game_Stats tgs
            JOIN Games g ON tgs.game_id = g.game_id
            WHERE tgs.team_id = ?
            ORDER BY g.game_date DESC
            LIMIT ?
            """,
            (int(team_id), int(n)),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_team_recent_stats(%s) failed: %s", team_id, exc)
        return []
    finally:
        conn.close()


def get_team_roster(team_id: int) -> list[dict]:
    """
    Return all players on a team's roster.

    Keys: team_id, player_id, first_name, last_name, position,
    is_two_way, is_g_league.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                tr.team_id, tr.player_id,
                p.first_name, p.last_name, p.position,
                tr.is_two_way, tr.is_g_league
            FROM Team_Roster tr
            JOIN Players p ON tr.player_id = p.player_id
            WHERE tr.team_id = ?
              AND tr.effective_end_date IS NULL
            ORDER BY p.last_name
            """,
            (int(team_id),),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_team_roster(%s) failed: %s", team_id, exc)
        return []
    finally:
        conn.close()


def get_injured_players(team_id: int | None = None) -> list[dict]:
    """
    Return current injury reports.

    If *team_id* is given, only that team's injuries are returned.
    Keys: player_id, first_name, last_name, team_id, status, reason, report_date.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if team_id is not None:
            rows = conn.execute(
                """
                SELECT i.player_id, p.first_name, p.last_name,
                       i.team_id, i.status, i.reason, i.report_date
                FROM Injury_Status i
                JOIN Players p ON i.player_id = p.player_id
                WHERE i.team_id = ?
                ORDER BY i.report_date DESC
                """,
                (int(team_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT i.player_id, p.first_name, p.last_name,
                       i.team_id, i.status, i.reason, i.report_date
                FROM Injury_Status i
                JOIN Players p ON i.player_id = p.player_id
                ORDER BY i.report_date DESC
                """,
            ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_injured_players failed: %s", exc)
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY WRAPPERS
#  Match the signatures of the old fetcher modules so engine code can switch
#  imports without any other changes.
# ═══════════════════════════════════════════════════════════════════════════════


# ── from data.nba_stats_service ──────────────────────────────────────────────

def get_player_game_logs(player_id: int, season: str | None = None) -> list[dict]:
    """
    Replacement for ``nba_stats_service.get_player_game_logs``.

    Returns game logs with **UPPERCASE** column names to match the nba_api
    ``PlayerGameLog`` format that engine code expects.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                g.game_date, g.matchup,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
            """,
            (int(player_id),),
        ).fetchall()
        # Map to UPPERCASE keys matching nba_api PlayerGameLog format
        result = []
        for row in rows:
            d = dict(row)
            result.append({
                "GAME_DATE": d.get("game_date", ""),
                "MATCHUP":   d.get("matchup", ""),
                "PTS":       d.get("pts", 0),
                "REB":       d.get("reb", 0),
                "AST":       d.get("ast", 0),
                "STL":       d.get("stl", 0),
                "BLK":       d.get("blk", 0),
                "TOV":       d.get("tov", 0),
                "MIN":       d.get("min", "0"),
                "FGM":       d.get("fgm", 0),
                "FGA":       d.get("fga", 0),
                "FG_PCT":    d.get("fg_pct", 0.0),
                "FG3M":      d.get("fg3m", 0),
                "FG3A":      d.get("fg3a", 0),
                "FG3_PCT":   d.get("fg3_pct", 0.0),
                "FTM":       d.get("ftm", 0),
                "FTA":       d.get("fta", 0),
                "FT_PCT":    d.get("ft_pct", 0.0),
                "OREB":      d.get("oreb", 0),
                "DREB":      d.get("dreb", 0),
                "PF":        d.get("pf", 0),
                "PLUS_MINUS": d.get("plus_minus", 0),
                "WL":        d.get("wl", ""),
            })
        return result
    except Exception as exc:
        _logger.warning("get_player_game_logs(%s) failed: %s", player_id, exc)
        return []
    finally:
        conn.close()


def get_defensive_matchup_data(
    season: str | None = None,
    per_mode: str = "PerGame",
) -> list[dict]:
    """
    Replacement for ``nba_stats_service.get_defensive_matchup_data``.

    Returns rows from the Defense_Vs_Position table formatted to resemble
    the nba_api ``LeagueDashPtDefend`` output.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        rows = conn.execute(
            "SELECT * FROM Defense_Vs_Position WHERE season = ?",
            (season,),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_defensive_matchup_data failed: %s", exc)
        return []
    finally:
        conn.close()


def get_player_splits(player_id: int, season: str | None = None) -> dict:
    """
    Replacement for ``nba_stats_service.get_player_splits``.

    Computes home/away and last-N splits from the local Player_Game_Logs
    table.  Returns a dict with keys: last_5_games, last_10_games, home,
    away — each a list of stat-summary dicts.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        all_logs = conn.execute(
            """
            SELECT
                g.game_date, g.matchup, g.home_team_id, g.away_team_id,
                p.team_id,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
            """,
            (int(player_id),),
        ).fetchall()

        logs = [dict(r) for r in all_logs]
        if not logs:
            return {}

        def _summarise(subset: list[dict]) -> list[dict]:
            if not subset:
                return []
            n = len(subset)
            return [{
                "GP":   n,
                "PTS":  _r(sum(_safe_float(g.get("pts")) for g in subset) / n),
                "REB":  _r(sum(_safe_float(g.get("reb")) for g in subset) / n),
                "AST":  _r(sum(_safe_float(g.get("ast")) for g in subset) / n),
                "STL":  _r(sum(_safe_float(g.get("stl")) for g in subset) / n),
                "BLK":  _r(sum(_safe_float(g.get("blk")) for g in subset) / n),
                "TOV":  _r(sum(_safe_float(g.get("tov")) for g in subset) / n),
                "FG3M": _r(sum(_safe_float(g.get("fg3m")) for g in subset) / n),
                "FTM":  _r(sum(_safe_float(g.get("ftm")) for g in subset) / n),
                "FTA":  _r(sum(_safe_float(g.get("fta")) for g in subset) / n),
                "FGM":  _r(sum(_safe_float(g.get("fgm")) for g in subset) / n),
                "FGA":  _r(sum(_safe_float(g.get("fga")) for g in subset) / n),
                "OREB": _r(sum(_safe_float(g.get("oreb")) for g in subset) / n),
                "PLUS_MINUS": _r(sum(_safe_float(g.get("plus_minus")) for g in subset) / n),
            }]

        # Determine home/away by comparing player's team_id to game's home/away
        player_team_id = logs[0].get("team_id")
        home_logs = [g for g in logs if g.get("home_team_id") == player_team_id]
        away_logs = [g for g in logs if g.get("away_team_id") == player_team_id]

        return {
            "last_5_games":  _summarise(logs[:5]),
            "last_10_games": _summarise(logs[:10]),
            "home":          _summarise(home_logs),
            "away":          _summarise(away_logs),
        }
    except Exception as exc:
        _logger.warning("get_player_splits(%s) failed: %s", player_id, exc)
        return {}
    finally:
        conn.close()


def get_advanced_box_score(game_id: str) -> dict:
    """
    Replacement for ``nba_stats_service.get_advanced_box_score``.

    Computes approximate advanced stats from the local Player_Game_Logs.
    Returns dict with keys: player_stats, team_stats.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT
                l.player_id, p.first_name, p.last_name, p.team_id,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.game_id = ?
            """,
            (str(game_id),),
        ).fetchall()

        if not rows:
            return {}

        player_stats = []
        for row in rows:
            d = dict(row)
            mins = _parse_minutes(d.get("min"))
            fga = _safe_float(d.get("fga"))
            fgm = _safe_float(d.get("fgm"))
            fg3m = _safe_float(d.get("fg3m"))
            fta = _safe_float(d.get("fta"))
            ftm = _safe_float(d.get("ftm"))
            pts = _safe_float(d.get("pts"))
            tov = _safe_float(d.get("tov"))

            # Approximate advanced metrics
            efg_pct = ((fgm + 0.5 * fg3m) / fga) if fga > 0 else 0.0
            ts_denom = 2 * (fga + 0.44 * fta)
            ts_pct = (pts / ts_denom) if ts_denom > 0 else 0.0
            # Usage estimate: (FGA + 0.44*FTA + TOV) / minutes-share
            # Simplified: we don't have team totals per-game so just store raw
            usg_pct = 0.0

            player_stats.append({
                "PLAYER_NAME": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "playerName":  f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "PLAYER_ID":   d.get("player_id"),
                "TEAM_ID":     d.get("team_id"),
                "MIN":         mins,
                "EFG_PCT":     round(efg_pct, 3),
                "efgPct":      round(efg_pct, 3),
                "TS_PCT":      round(ts_pct, 3),
                "tsPct":       round(ts_pct, 3),
                "USG_PCT":     usg_pct,
                "usgPct":      usg_pct,
                "PTS":         pts,
                "REB":         _safe_float(d.get("reb")),
                "AST":         _safe_float(d.get("ast")),
            })

        # Aggregate team-level stats
        from collections import defaultdict
        team_agg: dict[int, dict] = defaultdict(lambda: {
            "pts": 0.0, "fgm": 0.0, "fga": 0.0, "fg3m": 0.0,
            "fta": 0.0, "ftm": 0.0, "tov": 0.0, "count": 0,
        })
        for row in rows:
            d = dict(row)
            tid = d.get("team_id")
            if tid is None:
                continue
            agg = team_agg[tid]
            agg["pts"] += _safe_float(d.get("pts"))
            agg["fgm"] += _safe_float(d.get("fgm"))
            agg["fga"] += _safe_float(d.get("fga"))
            agg["fg3m"] += _safe_float(d.get("fg3m"))
            agg["fta"] += _safe_float(d.get("fta"))
            agg["ftm"] += _safe_float(d.get("ftm"))
            agg["tov"] += _safe_float(d.get("tov"))
            agg["count"] += 1

        team_stats = []
        for tid, agg in team_agg.items():
            fga_t = agg["fga"]
            fgm_t = agg["fgm"]
            fg3m_t = agg["fg3m"]
            fta_t = agg["fta"]
            efg = ((fgm_t + 0.5 * fg3m_t) / fga_t) if fga_t > 0 else 0.0
            to_rate = (agg["tov"] / (fga_t + 0.44 * fta_t + agg["tov"])) if (fga_t + agg["tov"]) > 0 else 0.0
            team_stats.append({
                "TEAM_ID":  tid,
                "EFG_PCT":  round(efg, 3),
                "TOV_PCT":  round(to_rate, 3),
                "FTA_RATE": round(fta_t / fga_t, 3) if fga_t > 0 else 0.0,
                "PTS":      agg["pts"],
            })

        return {"player_stats": player_stats, "team_stats": team_stats}
    except Exception as exc:
        _logger.warning("get_advanced_box_score(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


# ── from data.nba_data_service ───────────────────────────────────────────────

def get_player_estimated_metrics(season: str | None = None) -> list:
    """
    Replacement for ``nba_data_service.get_player_estimated_metrics``.

    Returns estimated advanced metrics from the Player_Bio table, enriched
    with team-level pace/ratings from the Teams table.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT pb.*, t.pace AS team_pace, t.ortg AS team_ortg, t.drtg AS team_drtg
            FROM Player_Bio pb
            LEFT JOIN Teams t ON pb.team_id = t.team_id
            """
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # E_PACE comes from the player's team pace (possessions per game)
            team_pace = _safe_float(d.get("team_pace"))
            team_ortg = _safe_float(d.get("team_ortg"))
            team_drtg = _safe_float(d.get("team_drtg"))
            result.append({
                "PLAYER_ID":    d.get("player_id"),
                "PLAYER_NAME":  d.get("player_name", ""),
                "TEAM_ID":      d.get("team_id"),
                "GP":           d.get("gp", 0),
                "E_PACE":       team_pace,
                "e_pace":       team_pace,
                "E_OFF_RATING": team_ortg,
                "E_DEF_RATING": team_drtg,
                "USG_PCT":      d.get("usg_pct", 0),
                "TS_PCT":       d.get("ts_pct", 0),
                "AST_PCT":      d.get("ast_pct", 0),
            })
        return result
    except Exception as exc:
        _logger.warning("get_player_estimated_metrics failed: %s", exc)
        return []
    finally:
        conn.close()


def get_rotations(game_id: str) -> dict:
    """
    Replacement for ``nba_data_service.get_rotations``.

    Returns rotation stint data from the Play_By_Play table.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM Play_By_Play
            WHERE game_id = ?
            ORDER BY period, action_number
            """,
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"play_by_play": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.warning("get_rotations(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_team_game_logs(
    team_id: int,
    season: str | None = None,
    last_n: int = 0,
) -> list:
    """
    Replacement for ``nba_data_service.get_team_game_logs``.

    Returns per-game stats for a team from Team_Game_Stats joined with Games.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        query = """
            SELECT
                tgs.game_id, g.game_date, g.matchup,
                tgs.points_scored, tgs.points_allowed,
                tgs.pace_est, tgs.ortg_est, tgs.drtg_est,
                tgs.is_home, tgs.opponent_team_id
            FROM Team_Game_Stats tgs
            JOIN Games g ON tgs.game_id = g.game_id
            WHERE tgs.team_id = ?
            ORDER BY g.game_date DESC
        """
        params: list[Any] = [int(team_id)]
        if last_n and last_n > 0:
            query += " LIMIT ?"
            params.append(int(last_n))

        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_team_game_logs(%s) failed: %s", team_id, exc)
        return []
    finally:
        conn.close()


def get_four_factors_box_score(game_id: str) -> dict:
    """
    Replacement for ``nba_data_service.get_four_factors_box_score``.

    Computes four-factors (eFG%, TO%, ORB%, FT rate) from Team_Game_Stats
    or Player_Game_Logs.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        # Try Team_Game_Stats first
        rows = conn.execute(
            """
            SELECT team_id, points_scored, points_allowed,
                   pace_est, ortg_est, drtg_est
            FROM Team_Game_Stats
            WHERE game_id = ?
            """,
            (str(game_id),),
        ).fetchall()

        if rows:
            team_stats = []
            for row in rows:
                d = dict(row)
                team_stats.append({
                    "TEAM_ID":  d.get("team_id"),
                    "PTS":      d.get("points_scored", 0),
                    "PACE":     d.get("pace_est", 0),
                    "EFG_PCT":  0.0,  # Not directly available without shot data
                    "FTA_RATE": 0.0,
                    "TM_TOV_PCT": 0.0,
                    "OREB_PCT": 0.0,
                })
            return {"team_stats": team_stats}

        # Fallback: compute from Player_Game_Logs
        plogs = conn.execute(
            """
            SELECT p.team_id,
                   SUM(l.fgm) AS fgm, SUM(l.fga) AS fga,
                   SUM(l.fg3m) AS fg3m,
                   SUM(l.ftm) AS ftm, SUM(l.fta) AS fta,
                   SUM(l.tov) AS tov, SUM(l.oreb) AS oreb,
                   SUM(l.dreb) AS dreb, SUM(l.pts) AS pts
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.game_id = ?
            GROUP BY p.team_id
            """,
            (str(game_id),),
        ).fetchall()

        if not plogs:
            return {}

        team_stats = []
        for row in plogs:
            d = dict(row)
            fga = _safe_float(d.get("fga"))
            fgm = _safe_float(d.get("fgm"))
            fg3m = _safe_float(d.get("fg3m"))
            fta = _safe_float(d.get("fta"))
            tov = _safe_float(d.get("tov"))
            oreb = _safe_float(d.get("oreb"))
            dreb = _safe_float(d.get("dreb"))

            efg = ((fgm + 0.5 * fg3m) / fga) if fga > 0 else 0.0
            fta_rate = (fta / fga) if fga > 0 else 0.0
            possessions = fga + 0.44 * fta + tov
            tov_pct = (tov / possessions) if possessions > 0 else 0.0
            total_reb = oreb + dreb
            oreb_pct = (oreb / total_reb) if total_reb > 0 else 0.0

            team_stats.append({
                "TEAM_ID":     d.get("team_id"),
                "PTS":         _safe_float(d.get("pts")),
                "EFG_PCT":     round(efg, 3),
                "FTA_RATE":    round(fta_rate, 3),
                "TM_TOV_PCT":  round(tov_pct, 3),
                "OREB_PCT":    round(oreb_pct, 3),
            })
        return {"team_stats": team_stats}
    except Exception as exc:
        _logger.warning("get_four_factors_box_score(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_todays_games():
    """
    Replacement for ``nba_data_service.get_todays_games``.

    Reads from the Games table for today's date.
    """
    from data.etl_data_service import get_todays_games as _etl_todays

    return _etl_todays()


def get_player_stats(progress_callback=None) -> list:
    """
    Replacement for ``nba_data_service.get_player_stats``.

    Returns all players with season averages from the local DB.
    """
    from data.etl_data_service import get_all_players

    return get_all_players()


# ═══════════════════════════════════════════════════════════════════════════════
#  DB-first query functions for Tier 1/2/3 endpoints
#  These read directly from ETL tables when data exists, avoiding live API.
# ═══════════════════════════════════════════════════════════════════════════════


def get_box_score_usage_from_db(game_id: str) -> dict:
    """Read Box_Score_Usage for a game.  Returns {player_stats: [...]}."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Box_Score_Usage WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"player_stats": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.debug("get_box_score_usage_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_player_clutch_stats_from_db(season: str | None = None) -> list:
    """Read Player_Clutch_Stats for a season."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        rows = conn.execute(
            "SELECT * FROM Player_Clutch_Stats WHERE season = ?",
            (season,),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.debug("get_player_clutch_stats_from_db failed: %s", exc)
        return []
    finally:
        conn.close()


def get_shot_chart_from_db(player_id: int, season: str | None = None) -> list:
    """Read Shot_Chart data for a player."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        rows = conn.execute(
            "SELECT * FROM Shot_Chart WHERE player_id = ? AND season = ?",
            (int(player_id), season),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.debug("get_shot_chart_from_db(%s) failed: %s", player_id, exc)
        return []
    finally:
        conn.close()


def get_schedule_from_db(game_date: str | None = None) -> list:
    """Read Schedule table for a date."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if game_date is None:
            game_date = datetime.date.today().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT * FROM Schedule WHERE game_date = ?",
            (game_date,),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.debug("get_schedule_from_db(%s) failed: %s", game_date, exc)
        return []
    finally:
        conn.close()


def get_hustle_box_score_from_db(game_id: str) -> dict:
    """Read Box_Score_Hustle for a game."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Box_Score_Hustle WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"player_stats": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.debug("get_hustle_box_score_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_scoring_box_score_from_db(game_id: str) -> dict:
    """Read Box_Score_Scoring for a game."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Box_Score_Scoring WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"player_stats": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.debug("get_scoring_box_score_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_box_score_matchups_from_db(game_id: str) -> dict:
    """Read Box_Score_Matchups for a game."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Box_Score_Matchups WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"matchups": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.debug("get_box_score_matchups_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_win_probability_from_db(game_id: str) -> dict:
    """Read Win_Probability_PBP for a game."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Win_Probability_PBP WHERE game_id = ? ORDER BY event_num",
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"game_id": game_id, "data": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.debug("get_win_probability_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_play_by_play_from_db(game_id: str) -> list:
    """Read Play_By_Play for a game."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT * FROM Play_By_Play WHERE game_id = ? ORDER BY period, action_number",
            (str(game_id),),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.debug("get_play_by_play_from_db(%s) failed: %s", game_id, exc)
        return []
    finally:
        conn.close()


def get_league_leaders_from_db(stat_category: str = "PTS", season: str | None = None) -> list:
    """Read League_Leaders for a season.

    Note: The League_Leaders table is populated by ETL with the default
    stat category (PTS).  The *stat_category* parameter is accepted for
    API-compatibility but the table does not store multiple categories.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        rows = conn.execute(
            "SELECT * FROM League_Leaders WHERE season = ? ORDER BY rank ASC",
            (season,),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.debug("get_league_leaders_from_db failed: %s", exc)
        return []
    finally:
        conn.close()


def get_player_career_stats_from_db(player_id: int) -> list:
    """Read Player_Career_Stats for a player (current + previous season only)."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT * FROM Player_Career_Stats
            WHERE player_id = ?
            ORDER BY season_id DESC
            LIMIT 2
            """,
            (int(player_id),),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.debug("get_player_career_stats_from_db(%s) failed: %s", player_id, exc)
        return []
    finally:
        conn.close()


def get_box_score_traditional_from_db(game_id: str) -> dict:
    """Read traditional box score from Player_Game_Logs for a game."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT
                l.player_id, p.first_name, p.last_name, p.team_id,
                p.team_abbreviation, l.pts, l.reb, l.ast, l.stl, l.blk,
                l.tov, l.min, l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a,
                l.fg3_pct, l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.game_id = ?
            """,
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}

        player_stats = []
        for row in rows:
            d = dict(row)
            player_stats.append({
                "PLAYER_ID":      d.get("player_id"),
                "PLAYER_NAME":    f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "TEAM_ID":        d.get("team_id"),
                "TEAM_ABBREVIATION": d.get("team_abbreviation", ""),
                "MIN":            d.get("min", "0"),
                "PTS":            d.get("pts", 0),
                "REB":            d.get("reb", 0),
                "AST":            d.get("ast", 0),
                "STL":            d.get("stl", 0),
                "BLK":            d.get("blk", 0),
                "TOV":            d.get("tov", 0),
                "FGM":            d.get("fgm", 0),
                "FGA":            d.get("fga", 0),
                "FG_PCT":         d.get("fg_pct", 0.0),
                "FG3M":           d.get("fg3m", 0),
                "FG3A":           d.get("fg3a", 0),
                "FG3_PCT":        d.get("fg3_pct", 0.0),
                "FTM":            d.get("ftm", 0),
                "FTA":            d.get("fta", 0),
                "FT_PCT":         d.get("ft_pct", 0.0),
                "OREB":           d.get("oreb", 0),
                "DREB":           d.get("dreb", 0),
                "PF":             d.get("pf", 0),
                "PLUS_MINUS":     d.get("plus_minus", 0),
            })
        return {"player_stats": player_stats}
    except Exception as exc:
        _logger.debug("get_box_score_traditional_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_tracking_box_score_from_db(game_id: str) -> dict:
    """Read Player_Tracking_Stats for a game."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Player_Tracking_Stats WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"player_stats": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.debug("get_tracking_box_score_from_db(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_box_score_advanced_from_db(game_id: str) -> dict:
    """Read Box_Score_Advanced table directly for a game.

    Falls back to the computed approximation from Player_Game_Logs
    via get_advanced_box_score() if the dedicated table is empty.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Box_Score_Advanced WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if rows:
            return {"player_stats": _rows_to_dicts(rows)}
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    # Fall back to the approximation-based function
    return get_advanced_box_score(game_id)


def get_box_score_four_factors_from_db(game_id: str) -> dict:
    """Read Box_Score_Four_Factors table directly for a game.

    Falls back to the computed approximation via
    get_four_factors_box_score() if the dedicated table is empty.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT * FROM Box_Score_Four_Factors WHERE game_id = ?",
            (str(game_id),),
        ).fetchall()
        if rows:
            return {"player_stats": _rows_to_dicts(rows)}
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    # Fall back to the computed approximation
    return get_four_factors_box_score(game_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _current_season() -> str:
    """Return the current NBA season string, e.g. ``'2025-26'``."""
    today = datetime.date.today()
    year = today.year if today.month >= 10 else today.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Constants (from live_data_fetcher.py)
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIRECTORY = Path(__file__).parent
PLAYERS_CSV_PATH = DATA_DIRECTORY / "players.csv"
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"
INJURY_STATUS_JSON_PATH = DATA_DIRECTORY / "injury_status.json"
PROPS_CSV_PATH = DATA_DIRECTORY / "props.csv"
LIVE_PROPS_CSV_PATH = DATA_DIRECTORY / "live_props.csv"

API_DELAY_SECONDS = 1.5
FALLBACK_POINTS_STD_RATIO = 0.3
FALLBACK_REBOUNDS_STD_RATIO = 0.4
FALLBACK_ASSISTS_STD_RATIO = 0.4
FALLBACK_THREES_STD_RATIO = 0.55
FALLBACK_STEALS_STD_RATIO = 0.5
FALLBACK_BLOCKS_STD_RATIO = 0.6
FALLBACK_TURNOVERS_STD_RATIO = 0.4
MIN_MINUTES_THRESHOLD = 15.0
GP_ABSENT_THRESHOLD = 12
MIN_TEAM_GP_FOR_RECENCY_CHECK = 20
HOT_TREND_THRESHOLD = 1.1
COLD_TREND_THRESHOLD = 0.9
DEFAULT_VEGAS_SPREAD = 0.0
DEFAULT_GAME_TOTAL = 220.0
ESPN_API_TIMEOUT_SECONDS = 10

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

GTD_INJURY_STATUSES = frozenset({
    "GTD",
    "Day-to-Day",
})

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

_NBA_API_ABBREV_TO_OURS_FALLBACK: dict[str, str] = {
    "GS": "GSW",
    "NY": "NYK",
    "NO": "NOP",
    "SA": "SAS",
    "OKC": "OKC",
    "PHX": "PHX",
    "UTA": "UTA",
    "MEM": "MEM",
    # ESPN aliases
    "UTAH": "UTA",
    "WSH": "WAS",
}


def _build_nba_abbrev_map() -> dict[str, str]:
    """Build nba_api abbreviation → our abbreviation mapping."""
    try:
        from nba_api.stats.static import teams as _nba_teams_static
        nba_teams = _nba_teams_static.get_teams()
        mapping = {t["abbreviation"]: t["abbreviation"] for t in nba_teams}
        mapping.update(_NBA_API_ABBREV_TO_OURS_FALLBACK)
        return mapping
    except Exception:
        return dict(_NBA_API_ABBREV_TO_OURS_FALLBACK)


NBA_API_ABBREV_TO_OURS: dict[str, str] = _build_nba_abbrev_map()

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


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Timestamp Functions (from live_data_fetcher.py)
# ═══════════════════════════════════════════════════════════════════════════════

def save_last_updated(data_type):
    """Save the current timestamp to last_updated.json for a given data type."""
    existing_timestamps = {}
    if LAST_UPDATED_JSON_PATH.exists():
        try:
            with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
                existing_timestamps = json.load(json_file)
        except Exception:
            existing_timestamps = {}

    existing_timestamps[data_type] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    existing_timestamps["is_live"] = True

    try:
        with open(LAST_UPDATED_JSON_PATH, "w") as json_file:
            json.dump(existing_timestamps, json_file, indent=2)
    except Exception as error:
        _logger.warning("Warning: Could not save timestamp: %s", error)


def load_last_updated():
    """Load all timestamps from last_updated.json."""
    if not LAST_UPDATED_JSON_PATH.exists():
        return {}
    try:
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            return json.load(json_file)
    except Exception:
        return {}


def _invalidate_data_caches():
    """Bust all @st.cache_data caches for CSV/DB loaders."""
    try:
        load_players_data.clear()
        load_teams_data.clear()
        load_defensive_ratings_data.clear()
        load_props_data.clear()
        load_injury_status.clear()
        _logger.debug("Streamlit data caches cleared after CSV update.")
    except Exception:
        pass  # Cache clearing is best-effort


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: CSV Loading Functions (from data_manager.py)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_csv_file(file_path):
    """Internal helper: load any CSV file and return list of dicts."""
    file_path = Path(file_path)
    if not file_path.exists():
        return []

    rows = []
    try:
        with open(file_path, encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                cleaned_row = {
                    key.strip(): value.strip()
                    for key, value in row.items()
                    if key is not None
                }
                rows.append(cleaned_row)
    except Exception as error:
        _logger.warning("Error loading %s: %s", file_path, error)
        return []

    return list(rows)


def _convert_etl_players_to_app_format(etl_players: list) -> list:
    """Convert ETL player dicts to the format expected by the rest of the app."""
    result = []
    for p in etl_players:
        ppg  = float(p.get("ppg",  0) or 0)
        rpg  = float(p.get("rpg",  0) or 0)
        apg  = float(p.get("apg",  0) or 0)
        spg  = float(p.get("spg",  0) or 0)
        bpg  = float(p.get("bpg",  0) or 0)
        topg = float(p.get("topg", 0) or 0)
        mpg  = float(p.get("mpg",  0) or 0)

        fg3_avg    = float(p.get("fg3_avg",    0) or 0)
        ftm_avg    = float(p.get("ftm_avg",    0) or 0)
        fta_avg    = float(p.get("fta_avg",    0) or 0)
        ft_pct_avg = float(p.get("ft_pct_avg", 0) or 0)
        fgm_avg    = float(p.get("fgm_avg",    0) or 0)
        fga_avg    = float(p.get("fga_avg",    0) or 0)
        oreb_avg   = float(p.get("oreb_avg",   0) or 0)
        dreb_avg   = float(p.get("dreb_avg",   0) or 0)
        pf_avg     = float(p.get("pf_avg",     0) or 0)

        points_std   = float(p.get("points_std",   0) or 0) or round(ppg  * FALLBACK_POINTS_STD_RATIO, 1)
        rebounds_std = float(p.get("rebounds_std", 0) or 0) or round(rpg  * FALLBACK_REBOUNDS_STD_RATIO, 1)
        assists_std  = float(p.get("assists_std",  0) or 0) or round(apg  * FALLBACK_ASSISTS_STD_RATIO, 1)
        threes_std   = float(p.get("threes_std",   0) or 0)
        steals_std   = float(p.get("steals_std",   0) or 0) or round(spg  * FALLBACK_STEALS_STD_RATIO, 1)
        blocks_std   = float(p.get("blocks_std",   0) or 0) or round(bpg  * FALLBACK_BLOCKS_STD_RATIO, 1)
        turnovers_std = float(p.get("turnovers_std", 0) or 0) or round(topg * FALLBACK_TURNOVERS_STD_RATIO, 1)
        ftm_std      = float(p.get("ftm_std",      0) or 0)
        oreb_std     = float(p.get("oreb_std",     0) or 0)
        plus_minus_std = float(p.get("plus_minus_std", 0) or 0)

        result.append({
            "player_id":               str(p.get("player_id", "")),
            "name":                    f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "team":                    p.get("team_abbreviation", "") or "",
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
            "usage_rate":              0.0,
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
            "games_played":            str(p.get("gp", 0)),
        })
    return result


@st.cache_data(ttl=900, show_spinner=False)
def load_players_data() -> list:
    """
    Load all player data.

    Primary source: ETL SQLite database (db/smartpicks.db) when available.
    Fallback: players.csv (legacy / manually-loaded data).
    Returns an empty list if neither source is available.
    """
    try:
        from data.etl_data_service import get_all_players as _etl_get_all_players
        etl_players = _etl_get_all_players()
        if etl_players:
            return _convert_etl_players_to_app_format(etl_players)
    except Exception as _etl_err:
        _logger.debug("load_players_data: ETL source unavailable (%s), falling back to CSV.", _etl_err)

    return _load_csv_file(PLAYERS_CSV_PATH)


@st.cache_data(ttl=900, show_spinner=False)
def load_props_data():
    """Load all prop lines from props.csv."""
    return _load_csv_file(PROPS_CSV_PATH)


@st.cache_data(ttl=900, show_spinner=False)
def load_teams_data() -> list:
    """Load all 30 NBA teams — tries ETL database first, then CSV fallback."""
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
    """Load team defensive ratings by position — tries ETL database first, then CSV fallback."""
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
    """Load the persisted player injury/availability status map from disk."""
    if not INJURY_STATUS_JSON_PATH.exists():
        return {}
    try:
        with open(INJURY_STATUS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: dict(v) if isinstance(v, dict) else v for k, v in data.items()}
    except Exception as err:
        _logger.warning("load_injury_status: could not read %s: %s", INJURY_STATUS_JSON_PATH, err)
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Player Name Normalization & Fuzzy Matching (from data_manager.py)
# ═══════════════════════════════════════════════════════════════════════════════

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

_NAME_SUFFIXES_TO_STRIP = re.compile(
    r'\s+(jr\.?|sr\.?|ii|iii|iv|v)$',
    flags=re.IGNORECASE,
)


def normalize_player_name(name):
    """Normalize a player name for fuzzy matching."""
    if not name:
        return ""
    name = name.strip().lower()
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    name = _NAME_SUFFIXES_TO_STRIP.sub("", name).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _build_player_index(players_list):
    """Build pre-computed lookup indices for a players list."""
    lower_index = {}
    normalized_index = {}

    for player in players_list:
        if not isinstance(player, dict):
            continue
        raw_name = player.get("name", "")
        lname = raw_name.lower().strip()
        nname = normalize_player_name(raw_name)

        if lname and lname not in lower_index:
            lower_index[lname] = player
        if nname and nname not in normalized_index:
            normalized_index[nname] = player

    alias_index = {}
    for alias_key, canonical in NAME_ALIASES.items():
        if alias_key not in alias_index and canonical in lower_index:
            alias_index[alias_key] = lower_index[canonical]

    return lower_index, alias_index, normalized_index


_player_index_lock = _threading.Lock()
_player_index_cache: dict = {"list_id": None, "index": (None, None, None)}


def find_player_by_name_fuzzy(players_list, player_name):
    """Find a player using fuzzy / normalized name matching."""
    if not player_name:
        return None

    list_id = id(players_list)
    with _player_index_lock:
        if _player_index_cache["list_id"] != list_id:
            _player_index_cache["index"] = _build_player_index(players_list)
            _player_index_cache["list_id"] = list_id

    lower_index, alias_index, normalized_index = _player_index_cache["index"]

    search_lower = player_name.lower().strip()

    # Pass 1: Exact case-insensitive
    match = lower_index.get(search_lower)
    if match is not None:
        return match

    # Pass 2: Alias lookup
    match = alias_index.get(search_lower)
    if match is not None:
        return match

    # Pass 3: Normalized name match
    search_normalized = normalize_player_name(player_name)
    match = normalized_index.get(search_normalized)
    if match is not None and search_normalized:
        return match

    # Pass 4: Partial / substring match (O(n) fallback)
    if len(search_normalized) > 3:
        for player in players_list:
            if not isinstance(player, dict):
                continue
            stored_normalized = normalize_player_name(player.get("name", ""))
            if (search_normalized in stored_normalized or stored_normalized in search_normalized):
                return player

    return None


def find_player_by_name(players_list, player_name):
    """Find a player by name (delegates to fuzzy matcher)."""
    return find_player_by_name_fuzzy(players_list, player_name)


def find_players_by_team(players_list, team_abbrev):
    """Return all players on a given team, sorted by points avg desc."""
    abbrev_upper = team_abbrev.upper().strip()
    matches = [p for p in players_list if p.get("team", "").upper() == abbrev_upper]
    try:
        matches.sort(key=lambda p: float(p.get("points_avg", 0) or 0), reverse=True)
    except Exception:
        pass
    return matches


def get_all_team_abbreviations(teams_list):
    """Get all 30 NBA team abbreviations."""
    abbreviations = [
        team.get("abbreviation", "") for team in teams_list
        if team.get("abbreviation")
    ]
    return sorted(abbreviations)


def get_player_status(player_name, status_map):
    """Look up a player's injury/availability status from a status map."""
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

    if not status_map:
        status_map = load_injury_status()

    if not status_map:
        return _default

    key = player_name.lower().strip()
    if key in status_map:
        entry = dict(_default)
        entry.update(status_map[key])
        return entry

    normalized = normalize_player_name(player_name)
    if normalized in status_map:
        entry = dict(_default)
        entry.update(status_map[normalized])
        return entry

    return _default


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Props / Session helpers (from data_manager.py)
# ═══════════════════════════════════════════════════════════════════════════════

def save_props_to_session(props_list, session_state):
    """Save a list of props to Streamlit session state."""
    session_state["current_props"] = props_list


def load_props_from_session(session_state):
    """Load props from Streamlit session state."""
    if session_state.get("current_props"):
        return session_state["current_props"]
    if session_state.get("platform_props"):
        return session_state["platform_props"]
    return load_props_data()


def save_platform_props_to_session(props_list, session_state):
    """Save platform-retrieved props to Streamlit session state."""
    session_state["platform_props"] = props_list


def load_platform_props_from_csv(file_path=None):
    """Load platform-retrieved props from a CSV file on disk."""
    if file_path is None:
        file_path = LIVE_PROPS_CSV_PATH
    if not Path(file_path).exists():
        return []
    return _load_csv_file(file_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Cache Management & Data Health (from data_manager.py)
# ═══════════════════════════════════════════════════════════════════════════════

def clear_all_caches():
    """Clear all @st.cache_data caches for data loading functions."""
    try:
        load_players_data.clear()
        load_teams_data.clear()
        load_defensive_ratings_data.clear()
        load_props_data.clear()
        load_injury_status.clear()
    except Exception as _exc:
        _logger.warning("clear_all_caches: %s", _exc)


def get_data_health_report():
    """Return a summary of the current data health status."""
    warnings_list: list[str] = []

    files_present = {
        "players.csv": PLAYERS_CSV_PATH.exists(),
        "teams.csv": TEAMS_CSV_PATH.exists(),
        "props.csv": PROPS_CSV_PATH.exists(),
        "defensive_ratings.csv": DEFENSIVE_RATINGS_CSV_PATH.exists(),
        "last_updated.json": LAST_UPDATED_JSON_PATH.exists(),
    }

    for fname, exists in files_present.items():
        if not exists:
            warnings_list.append(f"Missing file: {fname}")

    try:
        players = load_players_data()
        players_count = len(players)
    except Exception:
        players_count = 0
        warnings_list.append("Could not load players.csv")

    try:
        teams = load_teams_data()
        teams_count = len(teams)
    except Exception:
        teams_count = 0
        warnings_list.append("Could not load teams.csv")

    try:
        props = load_props_data()
        props_count = len(props)
    except Exception:
        props_count = 0

    is_live = False
    last_updated = None
    if LAST_UPDATED_JSON_PATH.exists():
        try:
            with open(LAST_UPDATED_JSON_PATH, "r") as f:
                timestamps = json.load(f)
            is_live = bool(timestamps.get("is_live", False))
            last_updated = timestamps.get("players")
        except Exception:
            pass

    days_old = 0
    is_stale = True
    if last_updated:
        try:
            ts = datetime.datetime.fromisoformat(last_updated)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            age = now_utc - ts
            days_old = age.days
            is_stale = days_old > 3
            if is_stale:
                warnings_list.append(f"Data is {days_old} day(s) old — consider refreshing")
        except Exception:
            pass

    if players_count == 0:
        warnings_list.append("No players loaded — run Smart NBA Data to populate")
    if teams_count < 30:
        warnings_list.append(f"Only {teams_count}/30 teams loaded")

    return {
        "players_count": players_count,
        "teams_count": teams_count,
        "props_count": props_count,
        "is_live": is_live,
        "last_updated": last_updated,
        "days_old": days_old,
        "is_stale": is_stale,
        "files_present": files_present,
        "warnings": warnings_list,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Staleness warning (from live_data_fetcher.py)
# ═══════════════════════════════════════════════════════════════════════════════

def get_teams_staleness_warning():
    """Return a warning string if teams.csv/defensive_ratings.csv are stale."""
    _WARN_DAYS  = 7
    _STALE_DAYS = 14

    timestamps = load_last_updated()
    teams_ts_str = timestamps.get("teams")

    if not teams_ts_str:
        return "⚠️ teams.csv has never been updated — run Smart NBA Data → Fetch Team Stats."

    try:
        teams_ts = datetime.datetime.fromisoformat(str(teams_ts_str))
        _now_utc = datetime.datetime.now(datetime.timezone.utc)
        if teams_ts.tzinfo is None:
            teams_ts = teams_ts.replace(tzinfo=datetime.timezone.utc)
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

    return None


def get_cached_roster(team_abbrev):
    """Return the active roster for a team via RosterEngine."""
    try:
        from data.roster_engine import RosterEngine
        engine = RosterEngine()
        return engine.get_active_roster(team_abbrev.upper())
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: NBADataService class & refresh functions (from nba_data_service.py)
# ═══════════════════════════════════════════════════════════════════════════════

class NBADataService:
    """Class-based service wrapping module-level functions."""

    def __init__(self):
        self.cache = None
        try:
            from utils.cache import FileCache as _FileCache
            self.cache = _FileCache(cache_dir="cache/service", ttl_hours=1)
        except Exception:
            pass

        self.roster_engine = None
        try:
            from data.roster_engine import RosterEngine
            self.roster_engine = RosterEngine()
        except Exception:
            pass

    def get_todays_games(self):
        return get_todays_games()

    def get_todays_players(self, games, progress_callback=None,
                           precomputed_injury_map=None):
        _logger.debug("NBADataService.get_todays_players: not implemented in db_service")
        return []

    def get_team_stats(self, progress_callback=None):
        _logger.debug("NBADataService.get_team_stats: not implemented in db_service")
        return None

    def get_injuries(self):
        if self.roster_engine:
            try:
                return self.roster_engine.refresh()
            except Exception:
                pass
        return {}

    def clear_caches(self):
        clear_caches()

    def refresh_all_data(self, progress_callback=None):
        return refresh_all_data(progress_callback=progress_callback)


def clear_caches() -> None:
    """Clear file-based and in-memory caches across the data layer."""
    cleared = []

    try:
        from utils.cache import cache_clear
        cache_clear()
        cleared.append("in-memory")
    except Exception:
        pass

    try:
        from utils.cache import FileCache as _FileCache
        for cache_dir in ("cache/service", "cache/props", "cache/rosters"):
            try:
                fc = _FileCache(cache_dir=cache_dir, ttl_hours=0)
                fc.clear()
                cleared.append(cache_dir)
            except Exception:
                pass
    except Exception:
        pass

    _invalidate_data_caches()
    _logger.info("clear_caches: cleared %s", ", ".join(cleared) if cleared else "(none)")


def refresh_all_data(progress_callback=None) -> dict:
    """Refresh all core data sources with per-source error isolation."""
    result: dict[str, Any] = {
        "games": [],
        "players": [],
        "team_stats": None,
        "injuries": None,
        "errors": [],
    }
    total_steps = 4
    step = 0

    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching today's games…")
    try:
        result["games"] = get_todays_games()
    except Exception as exc:
        _logger.error("refresh_all_data — games failed: %s", exc)
        result["errors"].append(f"Games: {exc}")

    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching players…")
    if result["games"]:
        try:
            result["players"] = get_player_stats(progress_callback=None)
        except Exception as exc:
            _logger.error("refresh_all_data — players failed: %s", exc)
            result["errors"].append(f"Players: {exc}")

    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching team stats…")
    # Team stats are available from CSV / DB already

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


def refresh_from_etl(progress_callback=None) -> dict:
    """Incremental ETL update — fetch only new game logs since the last stored date."""
    if progress_callback:
        progress_callback(0, 4, "Connecting to ETL database…")

    try:
        from data.etl_data_service import refresh_data as _etl_refresh
        if progress_callback:
            progress_callback(1, 4, "Running incremental update…")

        result = _etl_refresh()

        if progress_callback:
            ng = result.get("new_games", 0)
            nl = result.get("new_logs",  0)
            progress_callback(3, 4, f"Update complete — {ng} new games, {nl} new logs.")

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
    """Full ETL pull — re-fetches the entire season and repopulates the DB."""
    if progress_callback:
        progress_callback(0, 4, "Starting full ETL pull from nba_api…")

    try:
        from etl.initial_pull import run_initial_pull
        kwargs: dict[str, Any] = {}
        if season:
            kwargs["season"] = season

        if progress_callback:
            progress_callback(1, 4, "Fetching all game logs (this may take ~30 s)…")

        result = run_initial_pull(**kwargs)

        if result is None:
            result = {"players_inserted": 0, "games_inserted": 0, "logs_inserted": 0}

        if progress_callback:
            pi = result.get("players_inserted", 0)
            gi = result.get("games_inserted",   0)
            li = result.get("logs_inserted",    0)
            progress_callback(3, 4, f"DB populated — {pi} players, {gi} games, {li} logs.")

        _invalidate_data_caches()

        if progress_callback:
            progress_callback(4, 4, "✅ Full ETL pull done!")

        return result
    except Exception as exc:
        _logger.error("full_refresh_from_etl failed: %s", exc)
        if progress_callback:
            progress_callback(4, 4, f"❌ Full ETL pull failed: {exc}")
        return {"players_inserted": 0, "games_inserted": 0, "logs_inserted": 0, "error": str(exc)}


def refresh_historical_data_for_tonight(
    games=None,
    last_n_games=30,
    progress_callback=None,
) -> dict:
    """Auto-retrieve historical game logs for tonight's players."""
    results: dict[str, int] = {"players_refreshed": 0, "clv_updated": 0, "errors": 0}

    if games is None:
        try:
            import streamlit as _st
            games = _st.session_state.get("todays_games", [])
        except Exception:
            games = []

    if not games:
        _logger.debug("refresh_historical_data_for_tonight: no games — skipping")
        return results

    playing_teams: set[str] = set()
    for g in games:
        for key in ("home_team", "away_team"):
            t = str(g.get(key, "")).upper().strip()
            if t:
                playing_teams.add(t)

    if not playing_teams:
        return results

    try:
        all_players = load_players_data()
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
            logs = get_player_last_n_games(int(player_id), n=last_n_games)
            if logs:
                results["players_refreshed"] += 1
        except Exception:
            results["errors"] += 1
        if progress_callback:
            progress_callback(idx + 1, total, f"Cached logs for {player_name}")

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


def get_standings(progress_callback=None) -> list:
    """Retrieve current NBA standings (ETL DB → nba_api fallback)."""
    if progress_callback:
        progress_callback(0, 10, "Retrieving NBA standings…")

    try:
        from data.etl_data_service import get_standings as _etl_standings
        standings = _etl_standings()
        if standings:
            if progress_callback:
                progress_callback(10, 10, f"Standings loaded ({len(standings)} teams).")
            return standings
    except Exception:
        pass

    try:
        from nba_api.stats.endpoints import leaguestandingsv3
        import time
        time.sleep(API_DELAY_SECONDS)
        raw = leaguestandingsv3.LeagueStandingsV3(season=_current_season())
        df = raw.get_data_frames()[0]
        standings = []
        for _, row in df.iterrows():
            abbr = TEAM_NAME_TO_ABBREVIATION.get(
                f"{row.get('TeamCity', '')} {row.get('TeamName', '')}".strip(),
                row.get("TeamAbbreviation", ""),
            )
            standings.append({
                "team_abbreviation": abbr,
                "conference": row.get("Conference", ""),
                "conference_rank": int(row.get("PlayoffRank", 0)),
                "wins": int(row.get("WINS", 0)),
                "losses": int(row.get("LOSSES", 0)),
                "win_pct": float(row.get("WinPCT", 0.0)),
                "streak": str(row.get("strCurrentStreak", "")),
                "last_10": str(row.get("L10", "")),
            })
        if progress_callback:
            progress_callback(10, 10, f"Standings loaded ({len(standings)} teams).")
        return standings
    except Exception as exc:
        _logger.warning("get_standings failed: %s", exc)

    return []


def get_player_news(player_name=None, limit=20) -> list:
    """Return recent NBA news. Placeholder — returns empty list."""
    return []


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: Live NBA API thin wrappers (from nba_data_service.py)
# ═══════════════════════════════════════════════════════════════════════════════

def get_player_on_off(team_id: int, season: str | None = None) -> dict:
    """Player on/off court data via nba_api (live call)."""
    _logger.debug("get_player_on_off(%s): not implemented in db_service — returning empty", team_id)
    return {}


def get_box_score_matchups(game_id: str) -> dict:
    """Defensive matchup data (who guarded whom) — live call stub."""
    _logger.debug("get_box_score_matchups(%s): not implemented in db_service — returning empty", game_id)
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: nba_stats_service wrappers for player_profile_service.py
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_players(active_only: bool = True) -> list[dict]:
    """Return all players — ETL DB first, nba_api fallback only if DB is empty."""
    # ── DB-first path (no API call) ──────────────────────────────────────
    try:
        from data.etl_data_service import get_all_players as _etl_all
        etl_rows = _etl_all()
        if etl_rows:
            players = [
                {
                    "id": int(p.get("player_id", 0)),
                    "full_name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                    "first_name": str(p.get("first_name", "")),
                    "last_name": str(p.get("last_name", "")),
                    "is_active": True,
                    "team_id": p.get("team_id"),
                    "team_abbreviation": str(p.get("team_abbreviation", "")),
                }
                for p in etl_rows
            ]
            _logger.info("get_all_players: loaded %d player(s) from ETL DB.", len(players))
            return players
    except Exception as exc:
        _logger.debug("get_all_players ETL path failed: %s", exc)

    # ── Fallback: live nba_api (only when DB has no players) ─────────────
    try:
        from nba_api.stats.endpoints import commonallplayers
        import time
        time.sleep(API_DELAY_SECONDS)
        endpoint = commonallplayers.CommonAllPlayers(
            is_only_current_season=1 if active_only else 0,
            league_id="00",
        )
        norm = endpoint.get_normalized_dict() or {}
        rows = norm.get("CommonAllPlayers", [])
        players = [
            {
                "id": int(r.get("PERSON_ID", 0)),
                "full_name": str(r.get("DISPLAY_FIRST_LAST", "")),
                "first_name": (lambda parts: parts[0] if parts else "")(
                    str(r.get("DISPLAY_FIRST_LAST", "")).split()
                ),
                "last_name": str(r.get("DISPLAY_LAST_COMMA_FIRST", "")).split(",")[0].strip() if r.get("DISPLAY_LAST_COMMA_FIRST") else "",
                "is_active": bool(r.get("ROSTERSTATUS", 0)),
                "team_id": r.get("TEAM_ID"),
                "team_abbreviation": str(r.get("TEAM_ABBREVIATION", "")),
            }
            for r in rows
        ]
        return players
    except Exception as exc:
        _logger.warning("get_all_players failed: %s", exc)
        return []


def get_player_info(player_id: int) -> dict:
    """Return player bio — ETL DB first, nba_api fallback only if DB miss."""
    # ── DB-first path (no API call) ──────────────────────────────────────
    conn = _get_conn()
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT player_id, first_name, last_name, team_id, "
                "team_abbreviation, position FROM Players WHERE player_id = ?",
                (int(player_id),),
            ).fetchone()
            if row:
                d = dict(row)
                _logger.info("get_player_info(%s): served from DB.", player_id)
                return {
                    "id": d.get("player_id", player_id),
                    "full_name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                    "position": d.get("position", "") or "",
                    "height": "",
                    "weight": "",
                    "country": "",
                    "birthdate": "",
                    "draft_year": None,
                    "draft_round": None,
                    "draft_number": None,
                    "school": "",
                    "team_id": d.get("team_id"),
                    "team_abbreviation": d.get("team_abbreviation", "") or "",
                    "jersey": "",
                    "from_year": None,
                    "to_year": None,
                }
        except Exception as exc:
            _logger.debug("get_player_info DB path failed: %s", exc)
        finally:
            conn.close()

    # ── Fallback: live nba_api (only when player not in DB) ──────────────
    try:
        from nba_api.stats.endpoints import commonplayerinfo
        import time
        time.sleep(API_DELAY_SECONDS)
        endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        norm = endpoint.get_normalized_dict() or {}
        rows = norm.get("CommonPlayerInfo", [])
        if not rows:
            return {}
        r = rows[0]
        return {
            "id": player_id,
            "full_name": str(r.get("DISPLAY_FIRST_LAST", "")),
            "position": str(r.get("POSITION", "")),
            "height": str(r.get("HEIGHT", "")),
            "weight": str(r.get("WEIGHT", "")),
            "country": str(r.get("COUNTRY", "")),
            "birthdate": str(r.get("BIRTHDATE", "")),
            "draft_year": r.get("DRAFT_YEAR"),
            "draft_round": r.get("DRAFT_ROUND"),
            "draft_number": r.get("DRAFT_NUMBER"),
            "school": str(r.get("SCHOOL", "")),
            "team_id": r.get("TEAM_ID"),
            "team_abbreviation": str(r.get("TEAM_ABBREVIATION", "")),
            "jersey": str(r.get("JERSEY", "")),
            "from_year": r.get("FROM_YEAR"),
            "to_year": r.get("TO_YEAR"),
        }
    except Exception as exc:
        _logger.warning("get_player_info(%s) failed: %s", player_id, exc)
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: game_log_cache stubs
# ═══════════════════════════════════════════════════════════════════════════════

def save_game_logs_to_cache(player_name, logs):
    """No-op — DB is the cache now."""
    pass


def load_game_logs_from_cache(player_name, **kwargs):
    """No-op — DB is the cache now."""
    return []


def get_defensive_ratings_from_db(season: str | None = None) -> list[dict]:
    """
    Return per-position defensive multipliers from Defense_Vs_Position table
    in the wide format expected by engine/projections.py.

    Returns a list of dicts with keys:
        abbreviation, vs_PG_pts, vs_PG_reb, vs_PG_ast, vs_PG_stl, vs_PG_blk, vs_PG_3pm,
        vs_SG_pts, ..., vs_C_pts, ...

    Falls back to an empty list when the table has no data.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        rows = conn.execute(
            """
            SELECT team_abbreviation, pos,
                   vs_pts_mult, vs_reb_mult, vs_ast_mult,
                   vs_stl_mult, vs_blk_mult, vs_3pm_mult
            FROM Defense_Vs_Position
            WHERE season = ?
            """,
            (season,),
        ).fetchall()
        if not rows:
            return []

        # Pivot long → wide: one dict per team with all position columns
        from collections import defaultdict
        team_data: dict[str, dict] = defaultdict(lambda: {"abbreviation": ""})
        for row in rows:
            d = dict(row)
            abbrev = d["team_abbreviation"]
            pos = d["pos"].upper()  # PG, SG, SF, PF, C
            team_data[abbrev]["abbreviation"] = abbrev
            team_data[abbrev][f"vs_{pos}_pts"] = float(d.get("vs_pts_mult") or 1.0)
            team_data[abbrev][f"vs_{pos}_reb"] = float(d.get("vs_reb_mult") or 1.0)
            team_data[abbrev][f"vs_{pos}_ast"] = float(d.get("vs_ast_mult") or 1.0)
            team_data[abbrev][f"vs_{pos}_stl"] = float(d.get("vs_stl_mult") or 1.0)
            team_data[abbrev][f"vs_{pos}_blk"] = float(d.get("vs_blk_mult") or 1.0)
            team_data[abbrev][f"vs_{pos}_3pm"] = float(d.get("vs_3pm_mult") or 1.0)

        return list(team_data.values())
    except Exception as exc:
        _logger.warning("get_defensive_ratings_from_db failed: %s", exc)
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION: PlayerIDCache stub (replaces data/player_id_cache.py)
# ═══════════════════════════════════════════════════════════════════════════════

class PlayerIDCache:
    """Stub replacement — use db_service.search_players() instead."""

    def get(self, name):
        return None

    def set(self, name, player_id):
        pass
