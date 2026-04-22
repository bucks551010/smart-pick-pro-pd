# ============================================================
# FILE: engine/analysis_orchestrator.py
# PURPOSE: Pure-engine analysis orchestration extracted from QAM page.
#          No Streamlit dependency — takes data in, returns results out.
# ============================================================
from __future__ import annotations

import datetime
import logging
from typing import Any, Callable

from engine.simulation import (
    run_quantum_matrix_simulation,
    build_histogram_from_results,
    simulate_combo_stat,
    simulate_fantasy_score,
    simulate_double_double,
    simulate_triple_double,
    generate_alt_line_probabilities,
)
from engine import COMBO_STAT_TYPES, FANTASY_STAT_TYPES, is_unbettable_line
from engine.projections import (
    build_player_projection,
    get_stat_standard_deviation,
    calculate_teammate_out_boost,
    POSITION_PRIORS,
)
from engine.edge_detection import (
    analyze_directional_forces,
    should_avoid_prop,
    detect_correlated_props,
    detect_trap_line,
    detect_line_sharpness,
    classify_bet_type,
    calculate_composite_win_score,
)
from engine.confidence import calculate_confidence_score
from engine.math_helpers import (
    calculate_edge_percentage,
    _PLATFORM_BASELINE_PROBS,
    _DEFAULT_PLATFORM_BASELINE,
)
from engine.explainer import generate_pick_explanation
from engine.odds_engine import american_odds_to_implied_probability as _odds_to_implied_prob
from engine.calibration import get_calibration_adjustment
from engine.clv_tracker import store_opening_line, get_stat_type_clv_penalties

from data.data_manager import find_player_by_name, get_player_status
from data.platform_mappings import COMBO_STATS, FANTASY_SCORING
from pages.helpers.neural_analysis_helpers import find_game_context_for_player

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded optional modules (same pattern as the QAM page)
# ---------------------------------------------------------------------------
_rotation_tracker = None
_rotation_checked = False

def _get_track_minutes_trend():
    global _rotation_tracker, _rotation_checked
    if not _rotation_checked:
        try:
            from engine.rotation_tracker import track_minutes_trend as _fn
            _rotation_tracker = _fn
        except ImportError:
            _rotation_tracker = None
        _rotation_checked = True
    return _rotation_tracker


_ensemble_fn = None
_ensemble_checked = False

def _get_ensemble_projection():
    global _ensemble_fn, _ensemble_checked
    if not _ensemble_checked:
        try:
            from engine.ensemble import get_ensemble_projection as _fn
            _ensemble_fn = _fn
        except ImportError:
            _ensemble_fn = None
        _ensemble_checked = True
    return _ensemble_fn


_gs_sim_fn = None
_gs_blend_fn = None
_gs_checked = False

def _get_game_script_fns():
    global _gs_sim_fn, _gs_blend_fn, _gs_checked
    if not _gs_checked:
        try:
            from engine.game_script import (
                simulate_game_script as _sim,
                blend_with_flat_simulation as _blend,
            )
            _gs_sim_fn = _sim
            _gs_blend_fn = _blend
        except ImportError:
            _gs_sim_fn = None
            _gs_blend_fn = None
        _gs_checked = True
    return _gs_sim_fn, _gs_blend_fn


_minutes_fn = None
_minutes_checked = False

def _get_project_player_minutes():
    global _minutes_fn, _minutes_checked
    if not _minutes_checked:
        try:
            from engine.minutes_model import project_player_minutes as _fn
            _minutes_fn = _fn
        except ImportError:
            _minutes_fn = None
        _minutes_checked = True
    return _minutes_fn


_line_movement_fn = None
_line_movement_checked = False

def _get_detect_line_movement():
    global _line_movement_fn, _line_movement_checked
    if not _line_movement_checked:
        try:
            from engine.market_movement import detect_line_movement as _fn
            _line_movement_fn = _fn
        except ImportError:
            _line_movement_fn = None
        _line_movement_checked = True
    return _line_movement_fn


# ── Inactive statuses that skip full analysis ────────────────────────────
_INACTIVE_STATUSES = frozenset({
    "Out", "Injured Reserve", "Out (No Recent Games)",
    "Suspended", "Not With Team",
    "G League - Two-Way", "G League - On Assignment", "G League",
})

# Injury penalty constants
_DOUBTFUL_INJURY_PENALTY = 12.0
_QUESTIONABLE_INJURY_PENALTY = 5.0

# Stat-type → game-log key mapping
_STAT_LOG_KEY_MAP = {
    "points": "pts", "rebounds": "reb", "assists": "ast",
    "threes": "fg3m", "steals": "stl", "blocks": "blk",
    "turnovers": "tov",
    # Secondary stats: DB log key differs from stat_type name.
    # Without these, recent_game_log_values is always empty for these
    # stats and KDE sampling never activates, degrading simulation quality.
    "offensive_rebounds": "oreb",
    "defensive_rebounds": "dreb",
    "personal_fouls": "pf",
    "minutes": "min",
}

# ── Season avg field names for the result dict ───────────────────────────
_SEASON_AVG_FIELDS = [
    ("season_pts_avg", "points_avg"),
    ("season_reb_avg", "rebounds_avg"),
    ("season_ast_avg", "assists_avg"),
    ("season_threes_avg", "threes_avg"),
    ("season_stl_avg", "steals_avg"),
    ("season_blk_avg", "blocks_avg"),
    ("season_tov_avg", "turnovers_avg"),
    ("season_minutes_avg", "minutes_avg"),
    ("season_ftm_avg", "ftm_avg"),
    ("season_fga_avg", "fga_avg"),
    ("season_fgm_avg", "fgm_avg"),
    ("season_fta_avg", "fta_avg"),
    ("season_oreb_avg", "offensive_rebounds_avg"),
    ("season_dreb_avg", "defensive_rebounds_avg"),
    ("season_pf_avg", "personal_fouls_avg"),
]


def _safe_float(val: Any, fallback: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return fallback


def _build_out_result(prop: dict, player_name: str, stat_type: str,
                      prop_line: float, platform: str,
                      player_status: str, injury_note: str) -> dict:
    """Build a minimal result dict for a player who is Out/IR."""
    return {
        "player_name": player_name,
        "team": prop.get("team", ""),
        "player_team": prop.get("team", ""),
        "player_position": "",
        "stat_type": stat_type,
        "line": prop_line,
        "platform": platform,
        **{k: 0 for k, _ in _SEASON_AVG_FIELDS},
        "season_pts_reb_avg": 0, "season_pts_ast_avg": 0,
        "season_reb_ast_avg": 0, "season_pra_avg": 0,
        "season_blk_stl_avg": 0,
        "points_avg": 0, "rebounds_avg": 0, "assists_avg": 0,
        "opponent": "",
        "is_home": None,
        "probability_over": 0.0, "probability_under": 1.0,
        "simulated_mean": 0.0, "simulated_std": 0.0,
        "percentile_10": 0.0, "percentile_50": 0.0, "percentile_90": 0.0,
        "adjusted_projection": 0.0, "overall_adjustment": 1.0,
        "recent_form_ratio": None, "games_played": None,
        "edge_percentage": -50.0, "confidence_score": 0,
        "tier": "Bronze", "tier_emoji": "🥉",
        "direction": "UNDER",
        "recommendation": f"SKIP — {player_name} is {player_status}",
        "forces": {"over_forces": [], "under_forces": []},
        "should_avoid": True,
        "avoid_reasons": [f"Player is {player_status}: {injury_note}"],
        "histogram": [], "score_breakdown": {},
        "line_vs_avg_pct": 0, "recent_form_results": [],
        "player_matched": False, "explanation": None,
        "line_sharpness_force": None, "line_sharpness_penalty": 0.0,
        "trap_line_result": {}, "trap_line_penalty": 0.0,
        "teammate_out_notes": [], "minutes_adjustment_factor": 1.0,
        "player_is_out": True,
        "player_status": player_status,
        "player_status_note": injury_note,
        "player_id": "",
        "odds_type": prop.get("odds_type", "standard"),
    }


def _build_error_result(prop: dict, error: Exception) -> dict:
    """Build a minimal result dict for a prop that failed analysis."""
    _err_name = prop.get("player_name", "")
    _err_stat = prop.get("stat_type", "points").lower()
    _err_line = _safe_float(prop.get("line", 0))
    return {
        "player_name": _err_name,
        "team": prop.get("team", ""),
        "player_team": prop.get("team", ""),
        "player_position": "",
        "stat_type": _err_stat,
        "line": _err_line,
        "platform": prop.get("platform", "DraftKings"),
        **{k: 0 for k, _ in _SEASON_AVG_FIELDS},
        "season_pts_reb_avg": 0, "season_pts_ast_avg": 0,
        "season_reb_ast_avg": 0, "season_pra_avg": 0,
        "season_blk_stl_avg": 0,
        "points_avg": 0, "rebounds_avg": 0, "assists_avg": 0,
        "opponent": "",
        "is_home": None,
        "probability_over": 0.5, "probability_under": 0.5,
        "simulated_mean": _err_line, "simulated_std": 0.0,
        "percentile_10": 0.0, "percentile_50": 0.0, "percentile_90": 0.0,
        "adjusted_projection": _err_line, "overall_adjustment": 1.0,
        "recent_form_ratio": None, "games_played": None,
        "edge_percentage": 0.0, "confidence_score": 0,
        "tier": "Bronze", "tier_emoji": "🥉",
        "direction": "OVER",
        "recommendation": f"⚠️ Analysis error for {_err_name} ({_err_stat})",
        "forces": {"over_forces": [], "under_forces": []},
        "should_avoid": True,
        "avoid_reasons": [f"Analysis error: {error}"],
        "histogram": [], "score_breakdown": {},
        "line_vs_avg_pct": 0, "recent_form_results": [],
        "player_matched": False, "explanation": None,
        "line_sharpness_force": None, "line_sharpness_penalty": 0.0,
        "trap_line_result": {}, "trap_line_penalty": 0.0,
        "teammate_out_notes": [], "minutes_adjustment_factor": 1.0,
        "player_is_out": False,
        "player_status": "Analysis Error",
        "player_status_note": str(error),
        "player_id": "",
        "odds_type": prop.get("odds_type", "standard"),
        "composite_win_score": 0.0,
        "win_score_grade": "F",
        "win_score_label": "Error",
    }


def _resolve_player_data(
    player_name: str,
    prop: dict,
    players_data: list[dict],
    stat_type: str,
    prop_line: float,
    prefetched_bios: dict,
) -> tuple[dict, bool]:
    """Resolve player data from DB or build a positional-prior fallback.

    Returns (player_data, player_matched).
    """
    player_data = find_player_by_name(players_data, player_name)
    player_matched = player_data is not None

    if player_data is not None:
        return player_data, True

    # ── Fallback: build from positional priors ────────────────────
    _pos = "SF"
    try:
        _bio = prefetched_bios.get(player_name)
        if _bio is None:
            from data.player_profile_service import get_player_bio
            _bio = get_player_bio(player_name)
        if _bio and _bio.get("position"):
            _bio_pos = _bio["position"].split("-")[0].strip()
            _BIO_POS_ALIAS = {"Guard": "PG", "Forward": "SF", "Center": "C"}
            _pos = _BIO_POS_ALIAS.get(_bio_pos, _bio_pos)
    except Exception:
        pass

    _prior = POSITION_PRIORS.get(_pos, POSITION_PRIORS["SF"])
    player_data = {
        "name": player_name,
        "team": prop.get("team", ""),
        "position": _pos,
        "games_played": 30,
        "minutes_avg": 28.0,
        "points_avg": str(_prior["points"]),
        "rebounds_avg": str(_prior["rebounds"]),
        "assists_avg": str(_prior["assists"]),
        "threes_avg": str(_prior["threes"]),
        "steals_avg": str(_prior["steals"]),
        "blocks_avg": str(_prior["blocks"]),
        "turnovers_avg": str(_prior["turnovers"]),
    }

    if stat_type in COMBO_STAT_TYPES:
        _components = COMBO_STATS.get(stat_type, [])
        _prior_sum = sum(_prior.get(s, 0.0) for s in _components)
        if _prior_sum > 0 and prop_line > 0:
            _scale = prop_line / _prior_sum
            for _c in _components:
                _est = round(_prior.get(_c, 0.0) * _scale, 1)
                player_data[f"{_c}_avg"] = str(_est)
                player_data[f"{_c}_std"] = str(round(max(0.5, _est * 0.35), 1))
        else:
            _split = round(prop_line / max(len(_components), 1), 1)
            for _c in _components:
                player_data[f"{_c}_avg"] = str(_split)
                player_data[f"{_c}_std"] = str(round(max(0.5, _split * 0.35), 1))

    elif stat_type in FANTASY_STAT_TYPES:
        _formula = FANTASY_SCORING.get(stat_type, {})
        _prior_fantasy = sum(_prior.get(s, 0.0) * w for s, w in _formula.items())
        if _prior_fantasy > 0 and prop_line > 0:
            _scale = prop_line / _prior_fantasy
            for _fs in _formula:
                _est = round(_prior.get(_fs, 0.0) * _scale, 1)
                player_data[f"{_fs}_avg"] = str(_est)
                player_data[f"{_fs}_std"] = str(round(max(0.5, _est * 0.35), 1))

    elif stat_type not in {"double_double", "triple_double"}:
        player_data[f"{stat_type}_avg"] = str(prop_line)
        player_data[f"{stat_type}_std"] = str(round(prop_line * 0.35, 1))

    return player_data, False


def _run_simulation(
    stat_type: str,
    prop_line: float,
    prop_target_line: float | None,
    platform: str,
    projected_stat: float,
    stat_std: float,
    player_data: dict,
    projection_result: dict,
    simulation_depth: int,
    game_context: dict,
    precise_minutes: float | None,
    recent_game_log_values: list[float],
) -> tuple[dict, float]:
    """Run the appropriate simulation variant and return (sim_output, projected_stat)."""
    _sim_kwargs = dict(
        blowout_risk_factor=projection_result.get("blowout_risk", 0.15),
        pace_adjustment_factor=projection_result.get("pace_factor", 1.0),
        matchup_adjustment_factor=projection_result.get("defense_factor", 1.0),
        home_away_adjustment=projection_result.get("home_away_factor", 0.0),
        rest_adjustment_factor=projection_result.get("rest_factor", 1.0),
    )
    _game_ctx = game_context if game_context.get("game_id") else None

    if stat_type in COMBO_STAT_TYPES:
        _combo_stat_components = COMBO_STATS.get(stat_type, [])
        _comp_proj = {
            s: projection_result.get(
                f"projected_{s}",
                _safe_float(player_data.get(f"{s}_avg", 0)),
            )
            for s in _combo_stat_components
        }
        _comp_std = {
            s: get_stat_standard_deviation(player_data, s)
            for s in _combo_stat_components
        }
        sim_output = simulate_combo_stat(
            component_projections=_comp_proj,
            component_std_devs=_comp_std,
            prop_line=prop_line,
            number_of_simulations=simulation_depth,
            game_context=_game_ctx,
            **_sim_kwargs,
        )
        projected_stat = sim_output.get("adjusted_projection", sum(_comp_proj.values()))

    elif stat_type in FANTASY_STAT_TYPES:
        _formula = FANTASY_SCORING.get(stat_type, {})
        _stat_proj = {
            s: projection_result.get(
                f"projected_{s}",
                _safe_float(player_data.get(f"{s}_avg", 0)),
            )
            for s in _formula
        }
        _stat_std = {
            s: get_stat_standard_deviation(player_data, s)
            for s in _formula
        }
        sim_output = simulate_fantasy_score(
            stat_projections=_stat_proj,
            stat_std_devs=_stat_std,
            fantasy_formula=_formula,
            prop_line=prop_line,
            number_of_simulations=simulation_depth,
            **_sim_kwargs,
        )
        projected_stat = sim_output.get("adjusted_projection", projected_stat)

    elif stat_type == "double_double":
        _dd_stats = ["points", "rebounds", "assists", "blocks", "steals"]
        _dd_proj = {
            s: projection_result.get(
                f"projected_{s}",
                _safe_float(player_data.get(f"{s}_avg", 0)),
            )
            for s in _dd_stats
        }
        _dd_std = {s: get_stat_standard_deviation(player_data, s) for s in _dd_stats}
        sim_output = simulate_double_double(
            stat_projections=_dd_proj,
            stat_std_devs=_dd_std,
            number_of_simulations=simulation_depth,
            **_sim_kwargs,
        )

    elif stat_type == "triple_double":
        _td_stats = ["points", "rebounds", "assists"]
        _td_proj = {
            s: projection_result.get(
                f"projected_{s}",
                _safe_float(player_data.get(f"{s}_avg", 0)),
            )
            for s in _td_stats
        }
        _td_std = {s: get_stat_standard_deviation(player_data, s) for s in _td_stats}
        sim_output = simulate_triple_double(
            stat_projections=_td_proj,
            stat_std_devs=_td_std,
            number_of_simulations=simulation_depth,
            **_sim_kwargs,
        )

    else:
        # Simple stat: standard QME 5.6
        _flat_sim_minutes = precise_minutes or projection_result.get("projected_minutes")
        sim_output = run_quantum_matrix_simulation(
            projected_stat_average=projected_stat,
            stat_standard_deviation=stat_std,
            prop_line=prop_line,
            number_of_simulations=simulation_depth,
            stat_type=stat_type,
            projected_minutes=_flat_sim_minutes,
            minutes_std=4.0,
            recent_game_logs=recent_game_log_values if len(recent_game_log_values) >= 15 else None,
            prop_target_line=prop_target_line,
            platform=platform,
            game_context=_game_ctx,
            **_sim_kwargs,
        )

        # Game Script Blend (30% game-script + 70% flat)
        _gs_sim, _gs_blend = _get_game_script_fns()
        if _gs_sim is not None:
            try:
                _gs_proj_dict = {
                    "projected_stat": projected_stat,
                    "projected_minutes": _flat_sim_minutes or 32.0,
                    "stat_std": stat_std,
                }
                _gs_ctx = {
                    "vegas_spread": game_context.get("vegas_spread", 0.0),
                    "game_total": game_context.get("game_total", 220.0),
                    "is_home": game_context.get("is_home", True),
                    "stat_type": stat_type,
                }
                _gs_result = _gs_sim(
                    player_projection=_gs_proj_dict,
                    game_context=_gs_ctx,
                    num_simulations=min(500, simulation_depth),
                )
                if _gs_result and _gs_result.get("simulated_values"):
                    _flat_for_blend = {
                        "mean": sim_output.get("simulated_mean", sim_output.get("mean", 0.0)),
                        "std": sim_output.get("simulated_std", sim_output.get("std", 0.0)),
                    }
                    _blended = _gs_blend(
                        game_script_results=_gs_result,
                        flat_simulation_results=_flat_for_blend,
                    )
                    if _blended and _blended.get("blended_mean", 0) > 0:
                        sim_output = dict(sim_output)
                        sim_output["simulated_mean"] = _blended["blended_mean"]
                        sim_output["simulated_std"] = _blended["blended_std"]
                        sim_output["game_script_applied"] = True
            except Exception:
                pass

    return sim_output, projected_stat


def analyze_single_prop(
    prop: dict,
    *,
    players_data: list[dict],
    todays_games: list[dict],
    injury_map: dict,
    defensive_ratings_data: Any,
    teams_data: Any,
    simulation_depth: int,
    prefetched_bios: dict,
    advanced_enrichment: dict,
    line_snapshots: dict,
) -> dict:
    """Analyze a single prop and return a full result dict.

    This is a pure-computation function with no Streamlit dependency.
    All external data is passed in via parameters.
    """
    player_name = prop.get("player_name", "")
    stat_type = prop.get("stat_type", "points").lower()
    prop_line = _safe_float(prop.get("line", 0))
    platform = prop.get("platform", "DraftKings")

    # Phase 2: quarantined target line
    prop_target_line = None
    _raw_target = prop.get("prop_target_line")
    if _raw_target is not None:
        try:
            _ptl = float(_raw_target)
            if _ptl > 0:
                prop_target_line = _ptl
        except (ValueError, TypeError):
            pass

    # ── Injury gate ───────────────────────────────────────────────
    player_status_info = get_player_status(player_name, injury_map)
    player_status = player_status_info.get("status", "Active")

    if player_status in _INACTIVE_STATUSES:
        injury_note = player_status_info.get("injury_note", "Player is not active")
        return _build_out_result(
            prop, player_name, stat_type, prop_line, platform,
            player_status, injury_note,
        )

    # ── Find / build player data ─────────────────────────────────
    player_data, player_matched = _resolve_player_data(
        player_name, prop, players_data, stat_type, prop_line, prefetched_bios,
    )

    player_team = player_data.get("team", prop.get("team", ""))
    game_context = find_game_context_for_player(player_team, todays_games)

    recent_form_games = prop.get("recent_form_results", [])

    # DB fallback for game logs
    if not recent_form_games:
        try:
            from data.etl_data_service import get_player_game_logs as _etl_get_logs
            _pid_for_logs = player_data.get("player_id", "")
            if _pid_for_logs:
                recent_form_games = _etl_get_logs(int(_pid_for_logs), limit=20) or []
        except Exception:
            pass

    # ── Minutes Trend ────────────────────────────────────────────
    _minutes_trend = None
    _minutes_trend_indicator = "➡️"
    _track_fn = _get_track_minutes_trend()
    if _track_fn and recent_form_games:
        try:
            _minutes_trend = _track_fn(recent_form_games, window=5)
            _td = _minutes_trend.get("trend_direction", "stable")
            _minutes_trend_indicator = "🔺" if _td == "up" else ("🔻" if _td == "down" else "➡️")
        except Exception:
            _minutes_trend = None

    # ── Teammate-Out Boost ───────────────────────────────────────
    teammate_boost, teammate_boost_notes = calculate_teammate_out_boost(
        player_data=player_data,
        injury_status_map=injury_map,
        teammates_data=players_data,
    )

    # ── Minutes Projection ───────────────────────────────────────
    _precise_minutes = None
    _minutes_proj_fn = _get_project_player_minutes()
    if _minutes_proj_fn is not None:
        try:
            _teammate_status = (
                {k: v.get("status", "Active") for k, v in injury_map.items()}
                if injury_map else None
            )
            _min_result = _minutes_proj_fn(
                player_data=player_data,
                game_context={
                    "opponent": game_context.get("opponent", ""),
                    "is_home": game_context.get("is_home", True),
                    "vegas_spread": game_context.get("vegas_spread", 0.0),
                    "game_total": game_context.get("game_total", 220.0),
                    "rest_days": game_context.get("rest_days", 2),
                    "back_to_back": game_context.get("back_to_back", False),
                    "game_id": game_context.get("game_id", ""),
                },
                teammate_status=_teammate_status,
                game_logs=recent_form_games if recent_form_games else None,
            )
            _precise_minutes = _min_result.get("projected_minutes")
        except Exception:
            _precise_minutes = None

    # ── Advanced context (usage_pct from deep fetch) ─────────────
    _advanced_context: dict | None = None
    try:
        _game_enr = advanced_enrichment.get(game_context.get("game_id", ""), {})
        _all_metrics = _game_enr.get("player_metrics", [])
        _player_id = player_data.get("player_id") or player_data.get("id")
        _player_name_lower = str(player_data.get("name", "")).lower()
        for _m in _all_metrics:
            _mid = _m.get("PLAYER_ID") or _m.get("playerId")
            _mname = str(_m.get("PLAYER_NAME") or _m.get("playerName") or "").lower()
            if (_player_id and _mid and int(_player_id) == int(_mid)) or (
                _player_name_lower and _mname and _player_name_lower in _mname
            ):
                _usg = _m.get("E_USG_PCT") or _m.get("USG_PCT") or _m.get("usage_pct")
                if _usg is not None:
                    try:
                        _usg_f = float(_usg)
                        _advanced_context = {
                            "usage_pct": _usg_f / 100.0 if _usg_f > 1.0 else _usg_f
                        }
                    except (TypeError, ValueError):
                        pass
                break
    except Exception:
        pass

    # Fall back to real usg_pct from Player_Bio (always available from DB)
    if _advanced_context is None:
        _db_usg = player_data.get("usg_pct") or player_data.get("usage_rate")
        if _db_usg:
            try:
                _db_usg_f = float(_db_usg)
                if _db_usg_f > 0:
                    _advanced_context = {
                        "usage_pct": _db_usg_f / 100.0 if _db_usg_f > 1.0 else _db_usg_f
                    }
            except (TypeError, ValueError):
                pass

    # ── Projection ───────────────────────────────────────────────
    projection_result = build_player_projection(
        player_data=player_data,
        opponent_team_abbreviation=game_context.get("opponent", ""),
        is_home_game=game_context.get("is_home", True),
        rest_days=game_context.get("rest_days", 2),
        game_total=game_context.get("game_total", 220.0),
        defensive_ratings_data=defensive_ratings_data,
        teams_data=teams_data,
        recent_form_games=recent_form_games if recent_form_games else None,
        vegas_spread=game_context.get("vegas_spread", 0.0),
        minutes_adjustment_factor=teammate_boost,
        teammate_out_notes=teammate_boost_notes,
        advanced_context=_advanced_context,
    )

    # ── Ensemble Override ────────────────────────────────────────
    _ensemble_result = None
    _ensemble_penalty = 0.0
    _ens_fn = _get_ensemble_projection()
    if _ens_fn is not None and stat_type not in ("double_double", "triple_double"):
        try:
            _ens_ctx = {
                "stat_type": stat_type,
                "opponent": game_context.get("opponent", ""),
                "is_home": game_context.get("is_home", True),
                "rest_factor": projection_result.get("rest_factor", 1.0),
                "pace_factor": projection_result.get("pace_factor", 1.0),
                "defense_factor": projection_result.get("defense_factor", 1.0),
            }
            _ensemble_result = _ens_fn(
                player_data=player_data,
                game_context=_ens_ctx,
                game_logs=recent_form_games if len(recent_form_games or []) >= 3 else None,
            )
            _ensemble_penalty = _ensemble_result.get("confidence_adjustment", 0.0)
        except Exception:
            _ensemble_result = None
            _ensemble_penalty = 0.0

    stat_std = get_stat_standard_deviation(player_data, stat_type)
    projected_stat = projection_result.get(
        f"projected_{stat_type}",
        _safe_float(player_data.get(f"{stat_type}_avg", prop_line)),
    )

    # Apply ensemble override for simple stats
    _ensemble_used = False
    if (
        _ensemble_result is not None
        and stat_type not in ("double_double", "triple_double")
        and stat_type not in list(COMBO_STAT_TYPES) + list(FANTASY_STAT_TYPES)
    ):
        _ens_proj = _ensemble_result.get("ensemble_projection", 0)
        _ens_std = _ensemble_result.get("ensemble_std", 0)
        if _ens_proj and _ens_proj > 0:
            projected_stat = _ens_proj
            _ensemble_used = True
            if _ens_std > 0:
                stat_std = (_ens_std + stat_std) / 2.0

    # ── Game log values for KDE ──────────────────────────────────
    _log_key = _STAT_LOG_KEY_MAP.get(stat_type, stat_type)
    recent_game_log_values: list[float] = []
    for _g in (recent_form_games or []):
        _v = _g.get(_log_key, _g.get(stat_type))
        if _v is not None:
            try:
                recent_game_log_values.append(float(_v))
            except (TypeError, ValueError):
                pass

    # ── Simulation ───────────────────────────────────────────────
    simulation_output, projected_stat = _run_simulation(
        stat_type=stat_type,
        prop_line=prop_line,
        prop_target_line=prop_target_line,
        platform=platform,
        projected_stat=projected_stat,
        stat_std=stat_std,
        player_data=player_data,
        projection_result=projection_result,
        simulation_depth=simulation_depth,
        game_context=game_context,
        precise_minutes=_precise_minutes,
        recent_game_log_values=recent_game_log_values,
    )

    # ── DD/TD Rate Blend: use actual historical rate from League_Dash ────────
    # For double_double / triple_double, blend 55% simulation (captures tonight's
    # opponent/pace/rest) with 45% historical season rate (player's actual DD/TD
    # frequency this year). This is significantly more accurate than pure simulation
    # because DDs depend heavily on the player's typical role and usage.
    if stat_type in ("double_double", "triple_double"):
        _rate_key = "double_double_rate" if stat_type == "double_double" else "triple_double_rate"
        _hist_rate = _safe_float(player_data.get(_rate_key, -1.0), -1.0)
        if _hist_rate >= 0:
            _sim_prob = _safe_float(simulation_output.get("probability_over", 0.5))
            _blended_prob = 0.55 * _sim_prob + 0.45 * _hist_rate
            _blended_prob = max(0.01, min(0.99, _blended_prob))
            simulation_output = dict(simulation_output)
            simulation_output["probability_over"] = _blended_prob
            simulation_output["simulated_mean"] = _blended_prob
            simulation_output["adjusted_projection"] = _blended_prob

    # ── Directional Forces ───────────────────────────────────────
    forces_result = analyze_directional_forces(
        player_data=player_data,
        prop_line=prop_line,
        stat_type=stat_type,
        projection_result=projection_result,
        game_context=game_context,
    )

    # ── Line Sharpness / Trap Line ───────────────────────────────
    season_avg_for_stat = _safe_float(player_data.get(f"{stat_type}_avg", 0))
    line_sharpness_force = detect_line_sharpness(
        prop_line=prop_line,
        season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
        stat_type=stat_type,
    )
    line_sharpness_penalty = 0.0
    if line_sharpness_force is not None:
        _lsf_name = line_sharpness_force.get("name", "")
        if (
            line_sharpness_force.get("direction") == "UNDER"
            and _lsf_name.startswith("Sharp Line")
        ):
            line_sharpness_penalty = min(8.0, line_sharpness_force.get("strength", 0) * 2.5)

    trap_line_result = detect_trap_line(
        prop_line=prop_line,
        season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
        defense_factor=projection_result.get("defense_factor", 1.0),
        rest_factor=projection_result.get("rest_factor", 1.0),
        game_total=game_context.get("game_total", 220.0),
        blowout_risk=projection_result.get("blowout_risk", 0.15),
        stat_type=stat_type,
    )
    trap_line_penalty = trap_line_result.get("confidence_penalty", 0.0)

    # ── Edge Calculation ─────────────────────────────────────────
    probability_over = simulation_output.get("probability_over", 0.5)
    _prop_over_odds = prop.get("over_odds", None)
    _platform_for_odds = prop.get("platform", "").lower().strip()

    if _prop_over_odds is not None:
        _implied_prob_for_edge = _odds_to_implied_prob(_prop_over_odds)
    else:
        _implied_prob_for_edge = _PLATFORM_BASELINE_PROBS.get(
            _platform_for_odds, _DEFAULT_PLATFORM_BASELINE,
        )

    edge_pct = calculate_edge_percentage(probability_over, _implied_prob_for_edge)

    # ── Calibration ──────────────────────────────────────────────
    calibration_adj = get_calibration_adjustment(probability_over)

    # ── On/Off + Matchup Data ────────────────────────────────────
    _on_off_data: dict | None = None
    _matchup_data: dict | None = None
    _game_id_ctx = game_context.get("game_id", "")
    _is_synthetic_game = game_context.get("is_synthetic", False) or "_vs_" in _game_id_ctx
    try:
        from data.nba_data_service import get_player_on_off, get_box_score_matchups
        _player_team_id = (
            game_context.get("home_team_id")
            if game_context.get("is_home")
            else game_context.get("away_team_id")
        )
        if _player_team_id and not _is_synthetic_game:
            _on_off_data = get_player_on_off(_player_team_id) or None
        if _game_id_ctx and not _is_synthetic_game:
            _matchup_data = get_box_score_matchups(_game_id_ctx) or None
    except Exception:
        pass

    if _on_off_data is None or _matchup_data is None:
        try:
            from data.etl_data_service import get_player_game_logs as _etl_logs_for_matchup
            _pid_matchup = player_data.get("player_id", "")
            if _pid_matchup and _on_off_data is None:
                _db_logs = _etl_logs_for_matchup(int(_pid_matchup), limit=10)
                if _db_logs:
                    _on_off_data = {"source": "db_game_logs", "games": len(_db_logs)}
        except Exception:
            pass

    # ── Injury penalty ───────────────────────────────────────────
    _injury_penalty = 0.0
    if player_status == "Doubtful":
        _injury_penalty = _DOUBTFUL_INJURY_PENALTY
    elif player_status in ("Questionable", "GTD"):
        _injury_penalty = _QUESTIONABLE_INJURY_PENALTY

    # ── Confidence Score ─────────────────────────────────────────
    confidence_output = calculate_confidence_score(
        probability_over=probability_over,
        edge_percentage=edge_pct,
        directional_forces=forces_result,
        defense_factor=projection_result.get("defense_factor", 1.0),
        stat_standard_deviation=stat_std,
        stat_average=season_avg_for_stat,
        simulation_results=simulation_output,
        games_played=int(player_data.get("games_played", 0) or 0) or None,
        recent_form_ratio=projection_result.get("recent_form_ratio"),
        line_sharpness_penalty=line_sharpness_penalty,
        trap_line_penalty=trap_line_penalty,
        calibration_adjustment=calibration_adj,
        injury_status_penalty=_injury_penalty,
        stat_type=stat_type,
        games_played_season=int(player_data.get("games_played", 0) or 0) or None,
        platform=platform,
        on_off_data=_on_off_data,
        matchup_data=_matchup_data,
    )

    if _ensemble_penalty > 0:
        _cur_conf = confidence_output.get("confidence_score", 50)
        confidence_output["confidence_score"] = max(0.0, _cur_conf - _ensemble_penalty)

    # ── CLV: store opening line ──────────────────────────────────
    try:
        store_opening_line(
            player_name=player_name,
            stat_type=stat_type,
            opening_line=prop_line,
            model_projection=projected_stat,
            model_direction=confidence_output.get("direction", "OVER"),
            confidence_score=confidence_output.get("confidence_score", 0.0),
            tier=confidence_output.get("tier", "Bronze"),
            edge_percentage=edge_pct,
        )
    except Exception:
        pass

    # ── Line snapshot for market movement ────────────────────────
    _snap_key = f"{player_name}_{stat_type}"
    if _snap_key not in line_snapshots:
        line_snapshots[_snap_key] = {
            "initial_line": prop_line,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    # ── Should Avoid ─────────────────────────────────────────────
    should_avoid_flag, avoid_reasons = should_avoid_prop(
        probability_over=probability_over,
        directional_forces_result=forces_result,
        edge_percentage=edge_pct,
        stat_standard_deviation=stat_std,
        stat_average=_safe_float(player_data.get(f"{stat_type}_avg", prop_line)),
        stat_type=stat_type,
        platform=prop.get("platform", ""),
        over_odds=prop.get("over_odds", -110),
    )

    if confidence_output.get("should_avoid"):
        should_avoid_flag = True
    for extra_reason in confidence_output.get("avoid_reasons", []):
        if extra_reason and extra_reason not in avoid_reasons:
            avoid_reasons.append(extra_reason)

    # ── Histogram ────────────────────────────────────────────────
    histogram_data = build_histogram_from_results(
        simulation_output.get("simulated_results", []),
        prop_line,
        number_of_buckets=15,
    )

    # ── Explanation ──────────────────────────────────────────────
    explanation = generate_pick_explanation(
        player_data=player_data,
        prop_line=prop_line,
        stat_type=stat_type,
        direction=confidence_output.get("direction", "OVER"),
        projection_result=projection_result,
        simulation_results=simulation_output,
        forces=forces_result,
        confidence_result=confidence_output,
        game_context=game_context,
        platform=platform,
        recent_form_games=prop.get("recent_form_results", []),
        should_avoid=should_avoid_flag,
        avoid_reasons=avoid_reasons,
        trap_line_result=trap_line_result,
        line_sharpness_info=line_sharpness_force,
        teammate_out_notes=projection_result.get("teammate_out_notes", []),
    )

    # ── Full Result Dict ─────────────────────────────────────────
    full_result: dict[str, Any] = {
        "player_name": player_name,
        "team": player_team,
        "player_team": player_team,
        "player_position": player_data.get("position", ""),
        "stat_type": stat_type,
        "line": prop_line,
        "platform": platform,
        "player_id": player_data.get("player_id", ""),
    }

    # Season averages
    for result_key, data_key in _SEASON_AVG_FIELDS:
        full_result[result_key] = _safe_float(player_data.get(data_key, 0))

    # Combo-stat season averages
    pts = _safe_float(player_data.get("points_avg", 0))
    reb = _safe_float(player_data.get("rebounds_avg", 0))
    ast = _safe_float(player_data.get("assists_avg", 0))
    blk = _safe_float(player_data.get("blocks_avg", 0))
    stl = _safe_float(player_data.get("steals_avg", 0))
    full_result["season_pts_reb_avg"] = pts + reb
    full_result["season_pts_ast_avg"] = pts + ast
    full_result["season_reb_ast_avg"] = reb + ast
    full_result["season_pra_avg"] = pts + reb + ast
    full_result["season_blk_stl_avg"] = blk + stl
    full_result["points_avg"] = pts
    full_result["rebounds_avg"] = reb
    full_result["assists_avg"] = ast

    full_result.update({
        "opponent": game_context.get("opponent", ""),
        "is_home": game_context.get("is_home"),
        "probability_over": round(probability_over, 4),
        "probability_under": round(1.0 - probability_over, 4),
        "simulated_mean": round(simulation_output.get("simulated_mean", 0), 1),
        "simulated_std": round(simulation_output.get("simulated_std", 0), 1),
        "percentile_10": round(simulation_output.get("percentile_10", 0), 1),
        "percentile_50": round(simulation_output.get("percentile_50", 0), 1),
        "percentile_90": round(simulation_output.get("percentile_90", 0), 1),
        "adjusted_projection": round(projected_stat, 1),
        "overall_adjustment": round(projection_result.get("overall_adjustment", 1.0), 3),
        "recent_form_ratio": projection_result.get("recent_form_ratio"),
        "games_played": int(player_data.get("games_played", 0) or 0) or None,
        "edge_percentage": round(edge_pct, 1),
        "confidence_score": confidence_output.get("confidence_score", 50),
        "tier": confidence_output.get("tier", "Bronze"),
        "tier_emoji": confidence_output.get("tier_emoji", "🥉"),
        "direction": confidence_output.get("direction", "OVER"),
        "recommendation": confidence_output.get("recommendation", ""),
        "forces": forces_result,
        "should_avoid": should_avoid_flag,
        "avoid_reasons": avoid_reasons,
        "histogram": histogram_data,
        "score_breakdown": confidence_output.get("score_breakdown", {}),
        "line_vs_avg_pct": prop.get("line_vs_avg_pct", 0),
        "recent_form_results": prop.get("recent_form_results", []),
        "player_matched": player_matched,
        "explanation": explanation,
        "line_sharpness_force": line_sharpness_force,
        "line_sharpness_penalty": round(line_sharpness_penalty, 1),
        "trap_line_result": trap_line_result,
        "trap_line_penalty": round(trap_line_penalty, 1),
        "teammate_out_notes": projection_result.get("teammate_out_notes", []),
        "minutes_adjustment_factor": round(projection_result.get("minutes_adjustment_factor", 1.0), 4),
        "minutes_trend": _minutes_trend,
        "minutes_trend_indicator": _minutes_trend_indicator,
        "projected_minutes": round(_precise_minutes, 1) if _precise_minutes else None,
        "player_is_out": False,
        "player_status": player_status,
        "player_status_note": player_status_info.get("injury_note", ""),
        # Ensemble metadata
        "ensemble_used": _ensemble_used,
        "ensemble_models": _ensemble_result.get("effective_models", 1) if _ensemble_result else 1,
        "ensemble_disagreement": (
            _ensemble_result.get("disagreement", {}).get("description", "")
            if _ensemble_result else ""
        ),
        "ensemble_model_weights": (
            _ensemble_result.get("model_weights", {}) if _ensemble_result else {}
        ),
        # Simulation array for fair-value odds explorer
        "simulated_results": simulation_output.get("simulated_results", []),
        "odds_type": prop.get("odds_type", "standard"),
    })

    # Phase 2: DFS Fixed-Payout Metrics
    if simulation_output.get("prop_target_line"):
        full_result["prop_target_line"] = simulation_output["prop_target_line"]
        full_result["probability_over_target"] = simulation_output.get(
            "probability_over_target", probability_over,
        )
    if simulation_output.get("dfs_breakevens"):
        full_result["dfs_breakevens"] = simulation_output["dfs_breakevens"]
    if simulation_output.get("dfs_parlay_ev"):
        full_result["dfs_parlay_ev"] = simulation_output["dfs_parlay_ev"]
    if simulation_output.get("dfs_platform"):
        full_result["dfs_platform"] = simulation_output["dfs_platform"]

    # ── Bet Classification ───────────────────────────────────────
    try:
        _season_avg_for_classify = _safe_float(player_data.get(f"{stat_type}_avg", 0)) or None
        _line_source = prop.get("platform") or prop.get("line_source") or "synthetic"
        _standard_line = prop.get("standard_line", None)
        _bet_classification = classify_bet_type(
            probability_over=probability_over,
            edge_percentage=edge_pct,
            stat_standard_deviation=stat_std,
            projected_stat=projected_stat,
            prop_line=prop_line,
            stat_type=stat_type,
            directional_forces_result=forces_result,
            rest_days=game_context.get("rest_days", 1),
            vegas_spread=game_context.get("vegas_spread", 0.0),
            recent_form_ratio=projection_result.get("recent_form_ratio"),
            season_average=_season_avg_for_classify,
            line_source=_line_source,
        )
        full_result["bet_type"] = _bet_classification.get("bet_type", "standard")
        full_result["bet_type_emoji"] = _bet_classification.get("bet_type_emoji", "")
        full_result["bet_type_label"] = _bet_classification.get("bet_type_label", "Standard Bet")
        full_result["bet_type_reasons"] = _bet_classification.get("reasons", [])
        full_result["std_devs_from_line"] = _bet_classification.get("std_devs_from_line", 0.0)
        full_result["line_verified"] = _bet_classification.get("line_verified", True)
        full_result["line_reliability_warning"] = _bet_classification.get("line_reliability_warning")
        full_result["standard_line"] = _standard_line
        full_result["risk_flags"] = _bet_classification.get("risk_flags", [])
        full_result["is_uncertain"] = _bet_classification.get("is_uncertain", False)
    except Exception:
        full_result["bet_type"] = "standard"
        full_result["bet_type_emoji"] = ""
        full_result["bet_type_label"] = "Standard Bet"
        full_result["bet_type_reasons"] = []
        full_result["std_devs_from_line"] = 0.0
        full_result["line_verified"] = True
        full_result["line_reliability_warning"] = None
        full_result["standard_line"] = None
        full_result["risk_flags"] = []
        full_result["is_uncertain"] = False

    # Capture raw odds
    full_result["over_odds"] = prop.get("over_odds", -110)
    full_result["under_odds"] = prop.get("under_odds", -110)

    # ── Alt-Line Probability Generation ──────────────────────────
    try:
        _alt_lines = generate_alt_line_probabilities(simulation_output, prop_line)
        full_result["alt_lines"] = _alt_lines
        _best_alt = _alt_lines.get("best_alt", {})
        full_result["prediction"] = _best_alt.get("prediction", "")
    except Exception:
        full_result["alt_lines"] = {}
        full_result["prediction"] = ""

    # ── CLV stat-type penalties ──────────────────────────────────
    try:
        _clv_penalties = get_stat_type_clv_penalties(days=90)
        _clv_stat_penalty = _clv_penalties.get(stat_type, 0.0)
        if _clv_stat_penalty > 0:
            full_result["confidence_score"] = max(0.0, full_result["confidence_score"] - _clv_stat_penalty)
            full_result["clv_stat_penalty"] = _clv_stat_penalty
    except Exception:
        pass

    # ── Market movement adjustment ───────────────────────────────
    _lm_fn = _get_detect_line_movement()
    if _lm_fn is not None:
        try:
            _opening_snap = line_snapshots.get(_snap_key, {})
            if _opening_snap:
                _mv = _lm_fn(
                    player_name, stat_type,
                    _opening_snap.get("initial_line", prop_line),
                    prop_line,
                    full_result.get("direction", "OVER"),
                )
                _mv_adj = _mv.get("confidence_adjustment", 0.0)
                if _mv_adj != 0.0:
                    full_result["confidence_score"] = max(
                        0.0, min(100.0, full_result["confidence_score"] + _mv_adj),
                    )
                    full_result["market_movement"] = _mv
        except Exception:
            pass

    # ── Composite Win Score ──────────────────────────────────────
    try:
        _dir = full_result.get("direction", "OVER")
        _prob_in_dir = (
            full_result.get("probability_over", 0.5)
            if _dir == "OVER"
            else full_result.get("probability_under", 0.5)
        )
        _streak_mult = projection_result.get("streak_multiplier", 1.0)
        _cws_result = calculate_composite_win_score(
            probability_in_direction=_prob_in_dir,
            confidence_score=full_result.get("confidence_score", 50),
            edge_percentage=full_result.get("edge_percentage", 0),
            directional_forces_result=full_result.get("forces"),
            streak_multiplier=_streak_mult,
            risk_score=5.0,
            is_coin_flip=full_result.get("is_coin_flip", False),
            should_avoid=full_result.get("should_avoid", False),
        )
        full_result["composite_win_score"] = _cws_result["composite_win_score"]
        full_result["win_score_grade"] = _cws_result["grade"]
        full_result["win_score_label"] = _cws_result["grade_label"]
    except Exception:
        full_result["composite_win_score"] = 0.0
        full_result["win_score_grade"] = "F"
        full_result["win_score_label"] = "Error"

    return full_result


def analyze_props_batch(
    props: list[dict],
    *,
    players_data: list[dict],
    todays_games: list[dict],
    injury_map: dict,
    defensive_ratings_data: Any,
    teams_data: Any,
    simulation_depth: int = 2000,
    prefetched_bios: dict | None = None,
    advanced_enrichment: dict | None = None,
    line_snapshots: dict | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """Analyze a batch of props and return a list of result dicts.

    Parameters
    ----------
    props : list[dict]
        List of prop dicts (player_name, stat_type, line, platform, ...).
    players_data : list[dict]
        Full player database.
    todays_games : list[dict]
        Today's game schedule.
    injury_map : dict
        Player name → {status, injury_note, ...}.
    defensive_ratings_data : any
        Loaded defensive ratings CSV data.
    teams_data : any
        Loaded teams data.
    simulation_depth : int
        Number of Monte Carlo simulations per prop.
    prefetched_bios : dict, optional
        Pre-fetched player bios {name: bio_dict}.
    advanced_enrichment : dict, optional
        Deep-fetch advanced enrichment data {game_id: {player_metrics: [...]}}.
    line_snapshots : dict, optional
        Mutable dict for tracking initial line snapshots for market movement.
        Will be populated during analysis.
    progress_callback : callable, optional
        Called with (current_index, total, player_name) for progress reporting.

    Returns
    -------
    list[dict]
        Analysis results sorted by composite_win_score (Out players at end).
    """
    if prefetched_bios is None:
        prefetched_bios = {}
    if advanced_enrichment is None:
        advanced_enrichment = {}
    if line_snapshots is None:
        line_snapshots = {}

    results: list[dict] = []
    total = len(props)

    # ── Pre-filter: drop non-standard odds types (demon/goblin) ──
    # These are PrizePicks alternate lines with different payouts
    # that should not be analyzed as standard bettable picks.
    props = [
        p for p in props
        if str(p.get("odds_type", "standard")).lower() in ("standard", "")
    ]
    total = len(props)

    for idx, prop in enumerate(props):
        if progress_callback is not None:
            progress_callback(idx, total, prop.get("player_name", "Player"))

        try:
            result = analyze_single_prop(
                prop,
                players_data=players_data,
                todays_games=todays_games,
                injury_map=injury_map,
                defensive_ratings_data=defensive_ratings_data,
                teams_data=teams_data,
                simulation_depth=simulation_depth,
                prefetched_bios=prefetched_bios,
                advanced_enrichment=advanced_enrichment,
                line_snapshots=line_snapshots,
            )
            results.append(result)
        except Exception as err:
            _logger.warning(
                "Prop #%d (%s/%s) analysis failed: %s",
                idx,
                prop.get("player_name", "?"),
                prop.get("stat_type", "?"),
                err,
            )
            results.append(_build_error_result(prop, err))

    # Correlation detection
    correlation_warnings = detect_correlated_props(results)
    for idx, warning in correlation_warnings.items():
        if idx < len(results):
            results[idx]["_correlation_warning"] = warning

    # Sort: active by composite_win_score desc, Out players at end
    out_results = [r for r in results if r.get("player_is_out", False)]
    active_results = [r for r in results if not r.get("player_is_out", False)]
    active_results.sort(key=lambda r: r.get("composite_win_score", 0), reverse=True)

    # Drop unbettable demon / goblin alternate lines from output
    active_results = [r for r in active_results if not is_unbettable_line(r)]

    # Enforce per-player cap: no player gets more than 5 picks in the output.
    # Results are already sorted by quality, so the first 5 per player are
    # the best ones.
    MAX_PICKS_PER_PLAYER = 5
    _player_counts: dict[str, int] = {}
    _capped: list[dict] = []
    for r in active_results:
        pname = r.get("player_name", "").lower()
        _player_counts[pname] = _player_counts.get(pname, 0) + 1
        if _player_counts[pname] <= MAX_PICKS_PER_PLAYER:
            _capped.append(r)
    active_results = _capped

    # Cap output to the 1000 best active picks.
    MAX_OUTPUT_PICKS = 1000
    active_results = active_results[:MAX_OUTPUT_PICKS]

    return active_results + out_results
