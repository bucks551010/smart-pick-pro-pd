# ============================================================
# FILE: engine/ensemble.py
# PURPOSE: Ensemble Prediction System — blends 3 independent
#          projection models to produce a more accurate, robust
#          prediction than any single model.
#
#          World-class prediction systems never rely on a single
#          model. By blending models with different information
#          sources (season avg, recent form, matchup history),
#          we reduce prediction variance and improve accuracy.
#
# CONNECTS TO: engine/projections.py (base projection),
#              engine/simulation.py (probability engine)
# CONCEPTS COVERED: Ensemble learning, inverse-variance weighting,
#                   model disagreement, blended projection
# ============================================================

# Standard library only — no numpy/scipy/pandas
import math

from engine.math_helpers import _safe_float


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# Minimum games required for a model to contribute to the ensemble
MIN_GAMES_FOR_RECENT_MODEL = 5        # Recent form model needs ≥5 games
MIN_GAMES_FOR_MATCHUP_MODEL = 3       # Matchup history model needs ≥3 prior games

# Maximum model disagreement before confidence reduction kicks in
# If models disagree by more than this fraction, reduce confidence
MODEL_DISAGREEMENT_THRESHOLD = 0.15  # 15% disagreement triggers confidence penalty

# Disagreement penalty applied to confidence score
MODEL_DISAGREEMENT_PENALTY = 5.0    # Points subtracted per tier of disagreement

# Fallback weight when a model can't contribute (uniform)
_UNIFORM_WEIGHT = 1.0 / 3.0

# ============================================================
# END SECTION: Module-Level Constants
# ============================================================


# ============================================================
# SECTION: Model A — Season Average with Context Adjustments
# ============================================================

def _model_a_season_avg(player_data, game_context, game_logs):
    """
    Model A: Season average with context adjustments (the current base model).

    Uses the full-season average as the anchor point, adjusted for
    tonight's game context (pace, home/away, rest, defense).

    Args:
        player_data (dict): Player season stats and averages
        game_context (dict): Tonight's game context (spread, total, home/away, etc.)
        game_logs (list of dict): Player's game-by-game logs (any ordering)

    Returns:
        dict: {'projection': float, 'variance': float, 'weight_hint': float}
            projection: Projected stat value for tonight
            variance: Estimated variance of this model's projection
            weight_hint: Suggested weight (0-1) — higher means model is more reliable
    """
    # Extract player averages
    stat_type = game_context.get("stat_type", "points")
    avg_key = f"{stat_type}_avg"
    _prop_line = float(game_context.get("prop_line", 0) or 0)
    _fallback = _prop_line if _prop_line > 0 else 15.0
    season_avg = float(player_data.get(avg_key, _fallback) or _fallback)

    # Apply basic context adjustments
    is_home = bool(game_context.get("is_home", True))
    home_factor = 1.025 if is_home else 0.985

    # Pace factor (fast game = more stats)
    pace_factor = float(game_context.get("pace_factor", 1.0) or 1.0)
    defense_factor = float(game_context.get("defense_factor", 1.0) or 1.0)
    rest_factor = float(game_context.get("rest_factor", 1.0) or 1.0)

    projection = season_avg * home_factor * pace_factor * defense_factor * rest_factor

    # Variance: proportional to season std
    std_key = f"{stat_type}_std"
    season_std = float(player_data.get(std_key, season_avg * 0.35) or season_avg * 0.35)
    variance = season_std ** 2

    # Weight: higher for more games played (more stable season average)
    games_played = int(player_data.get("games_played", player_data.get("gp", 20)) or 20)
    weight_hint = min(1.0, games_played / 40.0)  # Full weight at 40+ games

    return {
        "projection": _safe_float(round(max(0.0, projection), 2), 0.0),
        "variance": _safe_float(round(max(0.1, variance), 4), 1.0),
        "weight_hint": _safe_float(round(weight_hint, 4), 0.5),
        "model": "season_avg",
    }


# ============================================================
# END SECTION: Model A
# ============================================================


# ============================================================
# SECTION: Model B — Recent Form Weighted Model
# ============================================================

def _model_b_recent_form(player_data, game_context, game_logs):
    """
    Model B: Recent form model — uses only last 10 games (or fewer).

    BEGINNER NOTE: A player's last 10 games are more predictive than
    their full-season average because they reflect current form,
    role changes, and injury recovery. This model weights recency.

    Args:
        player_data (dict): Player season stats
        game_context (dict): Tonight's game context
        game_logs (list of dict): Player's recent game logs (most recent first)

    Returns:
        dict: {'projection': float, 'variance': float, 'weight_hint': float}
    """
    stat_type = game_context.get("stat_type", "points")

    # Map stat types to game log keys
    _key_map = {
        "points": "PTS", "rebounds": "REB", "assists": "AST",
        "steals": "STL", "blocks": "BLK", "threes": "FG3M", "turnovers": "TOV",
        # Secondary stats: DB log key differs from stat_type name.
        # The fallback chain (log_key → log_key_lower → log_key.lower()) means
        # PTS/REB etc. already work, but these 4 have no match without explicit mapping.
        "offensive_rebounds": "OREB",
        "defensive_rebounds": "DREB",
        "personal_fouls": "PF",
        "minutes": "MIN",
        "ftm": "FTM", "fga": "FGA", "fgm": "FGM", "fta": "FTA",
    }
    log_key = _key_map.get(stat_type.lower(), stat_type.upper())

    # Also try lowercase version
    _key_map_lower = {k: v.lower() for k, v in _key_map.items()}
    log_key_lower = _key_map_lower.get(stat_type.lower(), stat_type.lower())

    # Extract last 10 games
    recent_values = []
    for g in (game_logs or [])[:10]:
        v = g.get(log_key) or g.get(log_key_lower) or g.get(log_key.lower())
        if v is not None:
            try:
                recent_values.append(float(v))
            except (TypeError, ValueError):
                pass

    if len(recent_values) < MIN_GAMES_FOR_RECENT_MODEL:
        # Fall back to season average approach if not enough recent games
        avg_key = f"{stat_type}_avg"
        _prop_line = float(game_context.get("prop_line", 0) or 0)
        _fb = _prop_line if _prop_line > 0 else 15.0
        season_avg = float(player_data.get(avg_key, _fb) or _fb)
        std_key = f"{stat_type}_std"
        season_std = float(player_data.get(std_key, season_avg * 0.35) or season_avg * 0.35)
        return {
            "projection": _safe_float(round(max(0.0, season_avg), 2), 0.0),
            "variance": _safe_float(round(max(0.1, season_std ** 2), 4), 1.0),
            "weight_hint": _safe_float(0.0, 0.5),
            "model": "recent_form_fallback",
        }

    # Exponential decay weighting: most recent game weight = 1.0,
    # each prior game weighted by DECAY factor
    DECAY = 0.80
    weighted_sum = 0.0
    total_weight = 0.0
    for i, val in enumerate(recent_values):
        w = DECAY ** i
        weighted_sum += val * w
        total_weight += w

    recent_avg = weighted_sum / total_weight if total_weight > 0 else (sum(recent_values) / len(recent_values) if recent_values else 15.0)

    # Variance from recent games
    n = len(recent_values)
    mean_r = sum(recent_values) / n
    recent_var = sum((v - mean_r) ** 2 for v in recent_values) / max(1, n - 1)

    # Apply minimal context adjustments (home/away, rest)
    is_home = bool(game_context.get("is_home", True))
    home_factor = 1.020 if is_home else 0.985
    rest_factor = float(game_context.get("rest_factor", 1.0) or 1.0)

    projection = recent_avg * home_factor * rest_factor

    # Weight: recent form model is fully trusted when 10+ games available
    weight_hint = min(1.0, n / 10.0)

    return {
        "projection": _safe_float(round(max(0.0, projection), 2), 0.0),
        "variance": _safe_float(round(max(0.1, recent_var), 4), 1.0),
        "weight_hint": _safe_float(round(weight_hint, 4), 0.5),
        "model": "recent_form",
    }


# ============================================================
# END SECTION: Model B
# ============================================================


# ============================================================
# SECTION: Model C — Matchup History Model
# ============================================================

def _model_c_matchup_history(player_data, game_context, game_logs):
    """
    Model C: Matchup history model — performance against this specific opponent.

    BEGINNER NOTE: Some players consistently dominate certain opponents
    (e.g., a guard who always torches a weak perimeter defense). Historical
    matchup data is a strong predictor when the sample size is large enough.

    Args:
        player_data (dict): Player season stats
        game_context (dict): Tonight's game context (must include 'opponent')
        game_logs (list of dict): Player's historical game logs with opponent info

    Returns:
        dict: {'projection': float, 'variance': float, 'weight_hint': float}
    """
    stat_type = game_context.get("stat_type", "points")
    opponent = game_context.get("opponent", "").upper().strip()

    _key_map = {
        "points": "PTS", "rebounds": "REB", "assists": "AST",
        "steals": "STL", "blocks": "BLK", "threes": "FG3M", "turnovers": "TOV",
        "offensive_rebounds": "OREB", "defensive_rebounds": "DREB",
        "personal_fouls": "PF", "minutes": "MIN",
        "ftm": "FTM", "fga": "FGA", "fgm": "FGM", "fta": "FTA",
    }
    log_key = _key_map.get(stat_type.lower(), stat_type.upper())
    log_key_lower = log_key.lower()

    # Filter to games against this opponent
    matchup_values = []
    if opponent:
        for g in (game_logs or []):
            game_opponent = str(g.get("MATCHUP", g.get("matchup", g.get("opponent", ""))))
            # NBA matchup format: "LAL vs. GSW" or "LAL @ GSW"
            if opponent in game_opponent.upper():
                v = g.get(log_key) or g.get(log_key_lower) or g.get(log_key.lower())
                if v is not None:
                    try:
                        matchup_values.append(float(v))
                    except (TypeError, ValueError):
                        pass

    if len(matchup_values) < MIN_GAMES_FOR_MATCHUP_MODEL:
        # Not enough matchup history — fall back to season average
        avg_key = f"{stat_type}_avg"
        _prop_line = float(game_context.get("prop_line", 0) or 0)
        _fb = _prop_line if _prop_line > 0 else 15.0
        season_avg = float(player_data.get(avg_key, _fb) or _fb)
        std_key = f"{stat_type}_std"
        season_std = float(player_data.get(std_key, season_avg * 0.35) or season_avg * 0.35)
        return {
            "projection": _safe_float(round(max(0.0, season_avg), 2), 0.0),
            "variance": _safe_float(round(max(0.1, season_std ** 2), 4), 1.0),
            "weight_hint": _safe_float(0.0, 0.5),
            "model": "matchup_fallback",
        }

    matchup_avg = sum(matchup_values) / len(matchup_values)
    n = len(matchup_values)
    matchup_var = sum((v - matchup_avg) ** 2 for v in matchup_values) / max(1, n - 1)

    # Weight: diminishing value with more matchup games (small sample is noisy)
    # 3 games → 0.30, 5 games → 0.50, 10+ games → 0.80
    weight_hint = min(0.80, n * 0.08)

    return {
        "projection": _safe_float(round(max(0.0, matchup_avg), 2), 0.0),
        "variance": _safe_float(round(max(0.1, matchup_var), 4), 1.0),
        "weight_hint": _safe_float(round(weight_hint, 4), 0.5),
        "model": "matchup_history",
    }


# ============================================================
# END SECTION: Model C
# ============================================================


# ============================================================
# SECTION: Inverse-Variance Blending
# ============================================================

def _blend_models_inverse_variance(model_outputs):
    """
    Blend multiple model projections using inverse-variance weighting.

    BEGINNER NOTE: Inverse-variance weighting gives MORE weight to
    models with LOWER variance (more consistent predictions) and less
    weight to high-variance models (noisy or uncertain predictions).
    This is a mathematically optimal way to combine independent estimates.

    Formula:
        w_i = (1 / var_i) / sum(1 / var_j for all j)
        blended = sum(w_i * projection_i)

    Args:
        model_outputs (list of dict): Each dict has 'projection', 'variance',
            'weight_hint' keys. Models with weight_hint=0 are excluded.

    Returns:
        dict: {
            'blended_projection': float,
            'blended_variance': float,
            'model_weights': dict (model_name → weight),
            'effective_models': int (number of models with non-zero weight),
        }
    """
    # Filter out models with zero weight_hint (insufficient data)
    active_models = [m for m in model_outputs if m.get("weight_hint", 0) > 0]

    if not active_models:
        # No active models — use the first model's output directly
        m = model_outputs[0] if model_outputs else {}
        return {
            "blended_projection": _safe_float(m.get("projection", 0.0), 0.0),
            "blended_variance": _safe_float(m.get("variance", 1.0), 1.0),
            "model_weights": {},
            "effective_models": 0,
        }

    if len(active_models) == 1:
        m = active_models[0]
        return {
            "blended_projection": _safe_float(m.get("projection", 0.0), 0.0),
            "blended_variance": _safe_float(m.get("variance", 1.0), 1.0),
            "model_weights": {m.get("model", "?"): 1.0},
            "effective_models": 1,
        }

    # Compute inverse-variance weights, modified by weight_hint
    # Combined weight = (1 / variance) * weight_hint
    raw_weights = []
    for m in active_models:
        var = max(0.001, float(m.get("variance", 1.0)))
        hint = float(m.get("weight_hint", 1.0))
        raw_weights.append((1.0 / var) * hint)

    total_weight = sum(raw_weights)
    if total_weight <= 0:
        # Fallback: equal weights
        normalized = [1.0 / len(active_models)] * len(active_models)
    else:
        normalized = [w / total_weight for w in raw_weights]

    # Compute blended projection and variance
    blended_proj = sum(
        normalized[i] * float(active_models[i].get("projection", 0))
        for i in range(len(active_models))
    )

    # Blended variance: weighted sum of variances
    blended_var = sum(
        normalized[i] * float(active_models[i].get("variance", 1.0))
        for i in range(len(active_models))
    )

    model_weights = {
        m.get("model", f"model_{i}"): round(normalized[i], 4)
        for i, m in enumerate(active_models)
    }

    return {
        "blended_projection": _safe_float(round(max(0.0, blended_proj), 2), 0.0),
        "blended_variance": _safe_float(round(max(0.01, blended_var), 4), 1.0),
        "model_weights": model_weights,
        "effective_models": len(active_models),
    }


# ============================================================
# END SECTION: Inverse-Variance Blending
# ============================================================


# ============================================================
# SECTION: Model Disagreement Score
# ============================================================

def calculate_model_disagreement(model_outputs):
    """
    Compute how much the 3 models disagree with each other.

    BEGINNER NOTE: When all models agree (e.g., all predict 25 points),
    confidence is high. When models strongly disagree (one says 20,
    another says 30), something unusual is happening and confidence
    should be reduced.

    Args:
        model_outputs (list of dict): List of model output dicts
            with 'projection' keys.

    Returns:
        dict: {
            'disagreement_score': float (0-1, higher = more disagreement),
            'max_divergence': float (max absolute difference between any two models),
            'confidence_penalty': float (points to subtract from confidence score),
            'description': str (human-readable explanation),
        }
    """
    projections = [
        float(m.get("projection", 0))
        for m in model_outputs
        if m.get("weight_hint", 0) > 0
    ]

    if len(projections) < 2:
        return {
            "disagreement_score": _safe_float(0.0, 0.0),
            "max_divergence": _safe_float(0.0, 0.0),
            "confidence_penalty": _safe_float(0.0, 0.0),
            "description": "Only one model — no disagreement to measure",
        }

    mean_proj = sum(projections) / len(projections)
    if mean_proj <= 0:
        return {
            "disagreement_score": _safe_float(0.0, 0.0),
            "max_divergence": _safe_float(0.0, 0.0),
            "confidence_penalty": _safe_float(0.0, 0.0),
            "description": "Zero mean projection — cannot compute disagreement",
        }

    # Max pairwise divergence (relative to mean)
    max_div = 0.0
    for i in range(len(projections)):
        for j in range(i + 1, len(projections)):
            div = abs(projections[i] - projections[j]) / mean_proj
            max_div = max(max_div, div)

    # Disagreement score: 0 = perfect agreement, 1 = 100% relative spread
    disagreement_score = min(1.0, max_div)

    # Confidence penalty: starts at 0, ramps up above threshold
    if disagreement_score > MODEL_DISAGREEMENT_THRESHOLD:
        excess = disagreement_score - MODEL_DISAGREEMENT_THRESHOLD
        # Penalty scales linearly: 15% excess → 5 pt penalty, 30% excess → 10 pts
        confidence_penalty = min(10.0, excess * MODEL_DISAGREEMENT_PENALTY / MODEL_DISAGREEMENT_THRESHOLD)
    else:
        confidence_penalty = 0.0

    # Human-readable description
    if disagreement_score < 0.05:
        desc = "✅ Models in strong agreement — high confidence signal"
    elif disagreement_score < 0.15:
        desc = "ℹ️ Models broadly agree — minor variations within range"
    elif disagreement_score < 0.30:
        desc = "⚠️ Models show moderate disagreement — some uncertainty"
    else:
        desc = "🚨 Models strongly disagree — significant uncertainty, lower confidence"

    return {
        "disagreement_score": _safe_float(round(disagreement_score, 4), 0.0),
        "max_divergence": _safe_float(round(max_div, 4), 0.0),
        "confidence_penalty": _safe_float(round(confidence_penalty, 2), 0.0),
        "description": desc,
    }


# ============================================================
# END SECTION: Model Disagreement Score
# ============================================================


# ============================================================
# SECTION: Main Ensemble Interface
# ============================================================

def get_ensemble_projection(player_data, game_context, game_logs=None):
    """
    Run all 3 ensemble models and return the blended projection.

    This is the main entry point for the ensemble system. It runs:
    - Model A: Season average with context adjustments (stable, conservative)
    - Model B: Recent form weighted model (responsive to current form)
    - Model C: Matchup history model (opponent-specific performance)

    Then blends them using inverse-variance weighting so reliable
    models get higher influence than noisy ones.

    BEGINNER NOTE: Think of this like getting 3 different scouting
    reports and combining them proportionally based on how much
    you trust each scout's data quality.

    Args:
        player_data (dict): Player season stats from players.csv.
            Expected keys: '{stat}_avg', '{stat}_std', 'games_played', 'position'
        game_context (dict): Tonight's game context:
            - 'stat_type' (str): 'points', 'rebounds', etc.
            - 'opponent' (str): Opponent team abbreviation
            - 'is_home' (bool): True if home game
            - 'rest_factor' (float): Rest adjustment (1.0 = normal)
            - 'pace_factor' (float): Pace adjustment (1.0 = average)
            - 'defense_factor' (float): Matchup defense (1.0 = average)
        game_logs (list of dict, optional): Player's historical game logs.
            Each dict should have GAME_DATE, PTS/REB/AST/etc., MATCHUP.
            If None, only Model A (season average) is used.

    Returns:
        dict: {
            'ensemble_projection': float,   # Blended projection
            'ensemble_std': float,          # Estimated std dev of projection
            'model_outputs': list of dict,  # Individual model results
            'model_weights': dict,          # Weight given to each model
            'effective_models': int,        # How many models contributed
            'disagreement': dict,           # Model disagreement details
            'confidence_adjustment': float, # Penalty to apply to confidence score
        }

    Example:
        result = get_ensemble_projection(
            player_data={'points_avg': 24.5, 'points_std': 5.2, 'games_played': 35},
            game_context={'stat_type': 'points', 'opponent': 'BOS', 'is_home': True,
                          'pace_factor': 1.02, 'defense_factor': 0.95, 'rest_factor': 1.0},
            game_logs=[{'GAME_DATE': '2025-01-15', 'PTS': 28, 'MATCHUP': 'LAL vs. BOS'}, ...]
        )
    """
    game_logs = game_logs or []

    # ---- Run all 3 models ----
    model_a = _model_a_season_avg(player_data, game_context, game_logs)
    model_b = _model_b_recent_form(player_data, game_context, game_logs)
    model_c = _model_c_matchup_history(player_data, game_context, game_logs)

    model_outputs = [model_a, model_b, model_c]

    # ---- Blend with inverse-variance weighting ----
    blend_result = _blend_models_inverse_variance(model_outputs)

    # ---- Compute model disagreement ----
    disagreement = calculate_model_disagreement(model_outputs)

    # ---- Compute ensemble std ----
    # Use the blended variance, adding extra uncertainty if models disagree
    blended_var = float(blend_result["blended_variance"])
    extra_var_from_disagreement = (
        (disagreement["max_divergence"] * blend_result["blended_projection"]) ** 2
    )
    total_var = blended_var + extra_var_from_disagreement
    ensemble_std = math.sqrt(max(0.01, total_var))

    # ---- Total confidence adjustment ----
    confidence_adjustment = disagreement["confidence_penalty"]

    return {
        "ensemble_projection": _safe_float(blend_result["blended_projection"], 0.0),
        "ensemble_std": _safe_float(round(ensemble_std, 3), 1.0),
        "model_outputs": model_outputs,
        "model_weights": blend_result["model_weights"],
        "effective_models": blend_result["effective_models"],
        "disagreement": disagreement,
        "confidence_adjustment": _safe_float(round(confidence_adjustment, 2), 0.0),
    }


# ============================================================
# END SECTION: Main Ensemble Interface
# ============================================================
