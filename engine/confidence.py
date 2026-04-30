# ============================================================
# FILE: engine/confidence.py
# PURPOSE: Calculate confidence scores and assign tiers
#          (Platinum, Gold, Silver, Bronze) to each prop pick.
#          Combines multiple factors into a single score.
# CONNECTS TO: edge_detection.py (edge values), simulation.py
# CONCEPTS COVERED: Weighted scoring, tier classification
# ============================================================

# No external imports needed — pure Python logic
import math        # For rounding and floor
import statistics  # For stdev in multi-source agreement bonus (3B)

from engine.math_helpers import _safe_float


# ============================================================
# SECTION: Confidence Score Constants
# Define the weights for each factor in our confidence model.
# Weights add up to 1.0 (100%).
# ============================================================

# How much each factor contributes to the overall confidence score
# BEGINNER NOTE: These weights reflect how important each factor is
# You can adjust these in Settings if you want to change the model
# NOTE (W2): Redistributed weights to improve accuracy — reduced raw probability
#            over-reliance, increased historical consistency, recent form, and
#            directional agreement which are stronger predictors of actual outcomes.
WEIGHT_PROBABILITY_STRENGTH = 0.20    # Raw probability (20% of score) — reduced; circular vs Quantum Matrix Engine 5.6
WEIGHT_EDGE_MAGNITUDE = 0.22          # How big the edge is (22%)
WEIGHT_DIRECTIONAL_AGREEMENT = 0.20  # Multiple factors agree (20%) — increased; strong predictor
WEIGHT_MATCHUP_FAVORABILITY = 0.10   # How good the matchup is (10%)
WEIGHT_HISTORICAL_CONSISTENCY = 0.12  # Player's track record (12%) — increased; consistency wins
WEIGHT_SAMPLE_SIZE = 0.06             # How many games played (6%)
WEIGHT_RECENT_FORM = 0.10             # Recent 5-game trend vs season (10%) — increased; recency matters

# Validate that weights sum to exactly 1.0 (they must — that's the rule for weights).
# This assertion catches any accidental edits that would break the model silently.
_ALL_WEIGHTS = (
    WEIGHT_PROBABILITY_STRENGTH
    + WEIGHT_EDGE_MAGNITUDE
    + WEIGHT_DIRECTIONAL_AGREEMENT
    + WEIGHT_MATCHUP_FAVORABILITY
    + WEIGHT_HISTORICAL_CONSISTENCY
    + WEIGHT_SAMPLE_SIZE
    + WEIGHT_RECENT_FORM
)
assert abs(_ALL_WEIGHTS - 1.0) < 1e-9, (
    f"Confidence weights must sum to 1.0, but got {_ALL_WEIGHTS:.4f}. "
    "Check the WEIGHT_* constants in confidence.py."
)

# Tier thresholds (0-100 scale) — W2: Recalibrated to match new weight distribution
# The reduced probability weight (0.30→0.20) lowers all scores by ~5-8 pts vs old weights,
# so thresholds are set to produce the correct tier distribution for real NBA prop scenarios.
# Target distribution: Platinum ~top 3%, Gold ~top 12%, Silver ~top 30%, rest Bronze/Avoid.
PLATINUM_TIER_MINIMUM_SCORE = 84  # Near-perfect conditions (raised from 80 pre-PR)
GOLD_TIER_MINIMUM_SCORE = 68      # Very strong clear edge (restored from 65; 65 let in too many marginal picks)
SILVER_TIER_MINIMUM_SCORE = 60    # Solid evidence above average (raised from 57; tightened based on audit)
# Anything below 60 = Bronze (lower confidence)

# Minimum edge gate (W2): picks below these thresholds get auto-demoted
PLATINUM_MIN_EDGE_PCT = 8.0    # Platinum requires ≥8% edge (lowered from 10%; 12% originally)
GOLD_MIN_EDGE_PCT = 6.0        # Gold requires ≥6% edge (restored from 5%; was 7% originally)
SILVER_MIN_EDGE_PCT = 3.0      # Silver requires ≥3% edge (lowered from 5%)
LOW_EDGE_THRESHOLD = 3.0       # Below 3% → add "Low edge" to avoid reasons (lowered from 5%)

# Hard kill-switch probability thresholds (C2)
PLATINUM_MIN_PROBABILITY = 0.62   # No Platinum below 62% win probability (was 0.60)
GOLD_MIN_PROBABILITY = 0.57       # No Gold below 57% win probability (was 0.55)

# Auto-AVOID: coefficient of variation above this → automatically avoid
AUTO_AVOID_CV_THRESHOLD = 0.50    # CV > 0.50 → auto-AVOID (loosened from 0.45; was 0.40 originally)

# Score below this threshold → "Do Not Bet" / Avoid tier.
# 35/100 corresponds roughly to a coin-flip bet with marginal edge that is unlikely
# to be profitable long-term after accounting for vig deduction. Based on analysis
# of historical pick performance where scores below 35 showed negative expected value.
DO_NOT_BET_SCORE_THRESHOLD = 35

# Combo-stat confidence penalty multiplier.
# Combo stats (points_rebounds, etc.) have more variance than simple stats.
COMBO_STAT_CONFIDENCE_MULTIPLIER = 0.90  # was 0.85 — softened penalty so combo stats aren't over-penalized

# Stats considered "combo" or "fantasy" for penalty purposes
COMBO_STAT_TYPES = {
    "points_rebounds", "points_assists", "rebounds_assists",
    "points_rebounds_assists", "blocks_steals",
    "fantasy_score", "fantasy_score_pp", "fantasy_score_dk", "fantasy_score_ud",
    "double_double", "triple_double",
}

# Binary / near-binary stat confidence penalty multiplier.
# Stats like dunks and blocked shots are effectively 0-or-1 outcomes per game.
# Their high intrinsic variance means projections are much less reliable than
# for continuous stats (points, rebounds, assists).  Applying a 0.75x penalty
# ensures these volatile props don't achieve Gold/Platinum tiers unless the
# underlying signals are extremely strong.
BINARY_STAT_CONFIDENCE_MULTIPLIER = 0.75

# Stats treated as binary/near-binary for confidence penalty purposes.
# These are 0-or-1-per-game stats or derived stats with doubled variance.
# Also includes threes (3PM/3PA) and steals — both are low-frequency,
# high-CV events (~28% and 0% win rate in audit; model consistently over-picks them).
BINARY_STAT_TYPES = {
    "dunks",
    "blocked_shots", "blocked shots",
    "two_pointers_made", "two_pointers_attempted",
    "two pointers made", "two pointers attempted",
    "2pm", "2pa",
    "threes", "fg3m", "three_pointers_made", "three pointers made",
    "steals", "stl",
}
# Unrealistic Edge Penalty: edges above this threshold are almost certainly
# projection errors, not real market inefficiencies.  NBA prop edges rarely
# exceed 20%; anything beyond 20% is overwhelmingly a bad projection that
# would otherwise inflate tier assignments (root cause of Gold/Silver
# underperforming Bronze in historical backtests).
UNREALISTIC_EDGE_THRESHOLD     = 20.0  # Edge % above which penalty kicks in (lowered from 25% based on audit)
UNREALISTIC_EDGE_PENALTY_SCALE = 1.5   # Confidence pts deducted per 1% above threshold
UNREALISTIC_EDGE_PENALTY_MAX   = 15.0  # Maximum penalty for absurdly high edges

# Synergy bonus: multiplicative interaction between edge + consistency + probability.
# When all three strong signals align, a bonus is added to confidence score.
SYNERGY_EDGE_THRESHOLD        = 8.0   # Edge % required for synergy bonus
SYNERGY_CONSISTENCY_THRESHOLD = 70.0  # Historical score required for synergy bonus
SYNERGY_PROBABILITY_THRESHOLD = 0.60  # P(over) or P(under) required for synergy bonus
SYNERGY_BONUS_POINTS          = 3.0   # Bonus confidence points when all signals align

# CV penalty constants: high coefficient of variation means very unreliable projections
CV_PENALTY_THRESHOLD   = 0.40   # CV above this triggers a penalty
CV_PENALTY_SCALE       = 25.0   # Points penalty per 1.0 excess CV (e.g. CV=0.55 → 3.75 pts penalty)
CV_PENALTY_MAX         = 15.0   # Maximum penalty applied for extreme CV values

# Sample size correction: confidence scales with games played
SAMPLE_SIZE_FULL_GAMES  = 30.0  # Games for full confidence (sample_factor = 1.0)
SAMPLE_SIZE_FLOOR       = 0.50  # Minimum sample_factor (protects new players)

# Bayesian sample-size damping thresholds (3A).
# Early-season picks have less reliable season averages.
BAYESIAN_SAMPLE_MIN_GAMES = 15   # Below this: apply damping
BAYESIAN_TIER_CAP_SMALL    = 10  # Below this: cap tier at Silver
BAYESIAN_TIER_CAP_TINY     = 5   # Below this: cap tier at Bronze

# Multi-source probability agreement bonus (3B)
PROBABILITY_AGREEMENT_BONUS_MAX = 8.0   # Max bonus points when all models agree
PROBABILITY_DISAGREEMENT_PENALTY = 5.0  # Penalty when models disagree on direction

# Streak-adjusted confidence adjustments (3C)
STREAK_HOT_OVER_BONUS   =  3.0  # Hot streak + OVER: momentum bonus
STREAK_HOT_UNDER_PENALTY = -5.0  # Hot streak + UNDER: momentum contradiction
STREAK_COLD_UNDER_BONUS  =  3.0  # Cold streak + UNDER: momentum bonus
STREAK_COLD_OVER_PENALTY = -5.0  # Cold streak + OVER: momentum contradiction
STREAK_LENGTH_DOUBLE_THRESHOLD = 5  # Streak length above this doubles the bonus/penalty
STREAK_MAX_ADJUSTMENT   = 10.0  # Maximum absolute adjustment (±10)

# Platform-specific tier score premiums (3D).
# Higher premium = harder to achieve high tier on that platform.
# Standard sportsbooks: +3 (traditional vig makes each leg harder to beat).
# PrizePicks Power: +5 (all-or-nothing structure is harder).
PLATFORM_TIER_PREMIUMS = {
    "PrizePicks":        0,
    "PrizePicks Power":  5,
    "Underdog Fantasy":  0,
    "DraftKings Pick6":  3,
    # Backward-compat aliases
    "Underdog":          0,
    "DraftKings":        3,
}

# ============================================================
# END SECTION: Confidence Score Constants
# ============================================================


# ============================================================
# SECTION: Main Confidence Calculator
# ============================================================

def calculate_confidence_score(
    probability_over: float,
    edge_percentage: float,
    directional_forces: list,
    defense_factor: float,
    stat_standard_deviation: float,
    stat_average: float,
    simulation_results: list,
    games_played: int | None = None,
    recent_form_ratio: float | None = None,
    line_sharpness_penalty: float = 0.0,
    trap_line_penalty: float = 0.0,
    calibration_adjustment: float = 0.0,
    injury_status_penalty: float = 0.0,
    stat_type: str | None = None,
    games_played_season: int | None = None,
    alternative_probabilities: list | None = None,
    streak_info: dict | None = None,
    platform: str | None = None,
    on_off_data: dict | None = None,
    matchup_data: dict | None = None,
) -> dict:
    """
    Calculate a 0-100 SAFE Score (Statistical Analysis of Force & Edge) for a prop pick.

    Combines eight signal weights into a weighted score, applies four penalties,
    then assigns a tier label: Platinum, Gold, Silver, or Bronze.

    ## Weights (W1–W8)

    The base score is a weighted sum of seven independent factor scores (each 0–100),
    plus one optional penalty group, normalised to a 0–100 final score:

    | Signal | Weight | Variable |
    |--------|--------|----------|
    | W1 Line Sharpness Penalty | post-score deduction (0–8 pts) | ``line_sharpness_penalty`` |
    | W2 Edge Magnitude | 22% | ``WEIGHT_EDGE_MAGNITUDE`` |
    | W3 Directional Agreement | 20% | ``WEIGHT_DIRECTIONAL_AGREEMENT`` |
    | W4 Historical Consistency | 12% | ``WEIGHT_HISTORICAL_CONSISTENCY`` |
    | W5 Trap Line Penalty | post-score deduction (0–15 pts) | ``trap_line_penalty`` |
    | W6 Recent Form | 10% | ``WEIGHT_RECENT_FORM`` |
    | W7 Calibration Adjustment | post-score adjustment (±) | ``calibration_adjustment`` |
    | W8 Matchup Favorability | 10% | ``WEIGHT_MATCHUP_FAVORABILITY`` |

    Additional weighted inputs:
    - Probability Strength: 20% (``WEIGHT_PROBABILITY_STRENGTH``)
    - Sample Size (games played): 6% (``WEIGHT_SAMPLE_SIZE``)

    ## Penalties (P1–P4)

    | Penalty | Trigger | Effect |
    |---------|---------|--------|
    | P1 Low Edge | edge < SILVER_MIN_EDGE_PCT | Score capped below Silver |
    | P2 Low Probability | prob < tier minimum | Tier downgrade |
    | P3 High CV | CV > 0.45 | Variance penalty (5–15 pts) |
    | P4 Injury / availability | injury_status_penalty > 0 | Direct score reduction |

    Phase 1 C2/C3 additions:
    - Hard kill switches (C2): override tier after scoring based on
      probability and CV thresholds.
    - Raised tier thresholds + min edge gate (C3): higher bars for
      Platinum/Gold/Silver, and low-edge picks auto-flagged as avoid.

    Args:
        probability_over (float): P(over line), from simulation
        edge_percentage (float): How far from 50% in percentage
        directional_forces (dict): Forces pushing MORE vs LESS
            Keys: 'over_count', 'under_count', 'over_forces', 'under_forces'
        defense_factor (float): Opponent defense multiplier (< 1 = tough)
        stat_standard_deviation (float): Stat variability
        stat_average (float): Player's season average for this stat
        simulation_results (dict): Full Quantum Matrix Engine 5.6 output dict
        games_played (int, optional): Games in season (higher = more reliable)
        recent_form_ratio (float, optional): Last-5-game avg / season avg.
            > 1.0 means hot streak, < 1.0 means cold streak.
        line_sharpness_penalty (float, optional): Points to subtract when
            the line is set at the player's true average (W1 — sharp line).
            Typically 0-8 points. Passed in from edge_detection results.
        trap_line_penalty (float, optional): Points to subtract when a
            trap line is detected (W5 — bait line). Typically 0-15 points.
        calibration_adjustment (float, optional): Historical calibration
            offset in percentage points (W7). Positive = model overestimates,
            scores get reduced. Negative = model underestimates, scores go up.
        injury_status_penalty (float, optional): Points to subtract when the
            player has a concerning injury/availability status (e.g. Questionable,
            Doubtful). Typically 0-10 points. Default 0.0 (no penalty).
        stat_type (str, optional): The stat being evaluated (e.g. 'points',
            'points_rebounds'). Used to apply combo-stat confidence penalty.
        games_played_season (int, optional): Games played this season for
            Bayesian sample-size damping (3A). Distinct from games_played.
        alternative_probabilities (list of float, optional): Probabilities from
            other models/sources for multi-source agreement bonus (3B).
        streak_info (dict, optional): Streak context for momentum adjustment (3C).
            Keys: 'type' ('hot'|'cold'|'none'), 'length' (int).
        platform (str, optional): Betting platform name for tier premium (3D).
            E.g. 'FanDuel', 'DraftKings', 'PrizePicks Power'.

    Returns:
        dict: {
            'confidence_score': float (0-100),
            'tier': str ('Platinum', 'Gold', 'Silver', 'Bronze', 'Avoid'),
            'tier_emoji': str ('💎', '🥇', '🥈', '🥉', '⛔'),
            'score_breakdown': dict with individual factor scores,
            'direction': str ('OVER' or 'UNDER'),
            'recommendation': str (e.g., "Strong OVER play"),
            'should_avoid': bool (C2: auto-AVOID flag),
            'avoid_reasons': list of str (C2/C3: reasons for avoid flag),
            'sample_size_discount': float (3A: Bayesian damping factor applied),
            'probability_agreement_bonus': float (3B: bonus/penalty from model agreement),
            'streak_adjustment': float (3C: momentum adjustment applied),
        }

    Example:
        60% probability, 10% edge, good matchup, consistent player
        → score ≈ 72, tier = Gold, direction = OVER
    """
    # ============================================================
    # SECTION: Calculate Individual Factor Scores
    # Each factor is scored 0-100, then weighted
    # ============================================================

    # --- Factor 1: Probability Strength (0-100) ---
    # How far is the probability from the 50% baseline?
    # 50% = 0 score, 70% = 40 score, 90% = 80 score
    probability_distance_from_50 = abs(probability_over - 0.5)
    probability_score = min(100.0, probability_distance_from_50 * 200.0)

    # --- Factor 2: Edge Magnitude (0-100) ---
    # Larger edge = higher score.  Cap at 20% edge = 100 score.
    # 20% is the realistic ceiling for NBA props (matching _CWS_MAX_EDGE_PCT).
    # Previous 25% cap (4.0x multiplier) allowed impossibly-high edges to
    # inflate Gold-tier scores.  Using 5.0x now: 20% → 100, 10% → 50.
    _MAX_REALISTIC_EDGE_PCT = 20.0
    capped_edge = min(abs(edge_percentage), _MAX_REALISTIC_EDGE_PCT)
    edge_score = min(100.0, capped_edge * 5.0)

    # --- Factor 3: Directional Agreement (0-100) ---
    # How many forces agree on the direction vs disagree?
    directional_score = _calculate_directional_agreement_score(directional_forces)

    # --- Factor 4: Matchup Favorability (0-100) ---
    # defense_factor > 1.0 = weak defense = good for player
    # Scale: 1.0 = neutral (50), 1.10 = great (80), 0.90 = bad (20)
    matchup_score = 50.0 + (defense_factor - 1.0) * 300.0
    matchup_score = max(0.0, min(100.0, matchup_score))

    # Enrich matchup score with real On/Off court differential data when available.
    # on_off_data comes from fetch_player_on_off() via nba_live_fetcher.
    # A player whose team has a strong positive net rating when they are ON court
    # (vs OFF) signals genuine on-court impact which improves prediction quality.
    if on_off_data:
        try:
            on_rows = on_off_data.get("on_court", [])
            off_rows = on_off_data.get("off_court", [])
            if on_rows and off_rows:
                # Average net ratings on/off court across all players in the data
                on_net = [float(r.get("NET_RATING", r.get("netRating", 0)) or 0) for r in on_rows]
                off_net = [float(r.get("NET_RATING", r.get("netRating", 0)) or 0) for r in off_rows]
                if on_net and off_net:
                    avg_on = sum(on_net) / len(on_net)
                    avg_off = sum(off_net) / len(off_net)
                    on_off_diff = avg_on - avg_off
                    # Each +1 net-rating differential adds 2.5 pts to matchup score.
                    # This factor scales so that a league-average on/off split of ~+4
                    # (typical star player) moves the score by +10 pts — meaningful
                    # but not dominant relative to the defense_factor baseline.
                    _NET_RATING_ADJUSTMENT_FACTOR = 2.5
                    on_off_adjustment = on_off_diff * _NET_RATING_ADJUSTMENT_FACTOR
                    matchup_score = max(0.0, min(100.0, matchup_score + on_off_adjustment))
        except Exception:
            pass  # Degradation: use base matchup_score if on_off_data is malformed

    # Enrich matchup score with defensive assignment quality when matchup data available.
    # matchup_data comes from fetch_box_score_matchups() via nba_live_fetcher.
    # When the primary defender guarding this player allows a high points-per-possession,
    # the matchup is more favorable for the offensive player.
    if matchup_data:
        try:
            matchup_rows = matchup_data.get("player_stats", [])
            if matchup_rows:
                # Look for a composite defensive quality signal in the matchup rows.
                # PLAYER_GUARD_DIFF (how much the player outperforms when guarded by this
                # defender) is a direct signal of matchup favorability.
                guard_diffs = []
                for row in matchup_rows:
                    gd = row.get("PLAYER_GUARD_DIFF") or row.get("playerGuardDiff")
                    if gd is not None:
                        try:
                            guard_diffs.append(float(gd))
                        except (TypeError, ValueError):
                            pass
                if guard_diffs:
                    avg_guard_diff = sum(guard_diffs) / len(guard_diffs)
                    # Positive guard diff = defender gives up more than average → favorable
                    matchup_adjustment = avg_guard_diff * 3.0
                    matchup_score = max(0.0, min(100.0, matchup_score + matchup_adjustment))
        except Exception:
            pass  # Degradation: use base matchup_score if matchup_data is malformed

    # --- Factor 5: Historical Consistency (0-100) ---
    # Players with low coefficient of variation (low std/avg) are
    # more consistent and their projections are more reliable
    historical_score = _calculate_consistency_score(
        stat_standard_deviation, stat_average
    )

    # --- Factor 6: Sample Size (0-100) ---
    # More games played = more reliable season averages.
    # 0 games = 0 score, 41+ games = 100 score
    sample_size_score = _calculate_sample_size_score(games_played)

    # --- Factor 7: Recent Form (0-100) ---
    # Recent hot/cold streaks adjust the prediction reliability.
    # ratio ≈ 1.0 = neutral (50), >> 1 = hot (high score), << 1 = cold (low)
    recent_form_score = _calculate_recent_form_score(
        recent_form_ratio, probability_over
    )

    # ============================================================
    # END SECTION: Calculate Individual Factor Scores
    # ============================================================

    # ============================================================
    # SECTION: Combine Scores with Weights
    # ============================================================

    # Weighted sum of all factor scores
    combined_score = (
        probability_score * WEIGHT_PROBABILITY_STRENGTH
        + edge_score * WEIGHT_EDGE_MAGNITUDE
        + directional_score * WEIGHT_DIRECTIONAL_AGREEMENT
        + matchup_score * WEIGHT_MATCHUP_FAVORABILITY
        + historical_score * WEIGHT_HISTORICAL_CONSISTENCY
        + sample_size_score * WEIGHT_SAMPLE_SIZE
        + recent_form_score * WEIGHT_RECENT_FORM
    )

    # --- Synergy Bonus: multiplicative interaction between strong signals ---
    # BEGINNER NOTE: When edge, consistency, AND probability are all high,
    # the combination is more than the sum of its parts. This bonus captures
    # that interaction — a +3-point bonus when all three signals align.
    _abs_edge = abs(edge_percentage)
    _prob_in_dir = probability_over if probability_over >= 0.5 else (1.0 - probability_over)
    if (_abs_edge > SYNERGY_EDGE_THRESHOLD
            and historical_score > SYNERGY_CONSISTENCY_THRESHOLD
            and _prob_in_dir > SYNERGY_PROBABILITY_THRESHOLD):
        combined_score += SYNERGY_BONUS_POINTS  # Synergy bonus: all three strong signals align

    # --- Unrealistic Edge Penalty ---
    # Edges above UNREALISTIC_EDGE_THRESHOLD (25%) are almost certainly
    # projection errors.  Instead of rewarding them with max edge_score,
    # penalise the combined score so these picks do not reach Gold/Platinum.
    if _abs_edge > UNREALISTIC_EDGE_THRESHOLD:
        _edge_excess = _abs_edge - UNREALISTIC_EDGE_THRESHOLD
        _unrealistic_penalty = min(
            UNREALISTIC_EDGE_PENALTY_MAX,
            _edge_excess * UNREALISTIC_EDGE_PENALTY_SCALE,
        )
        combined_score -= _unrealistic_penalty

    # --- 3B: Multi-source probability agreement bonus ---
    probability_agreement_bonus = 0.0
    if alternative_probabilities and len(alternative_probabilities) >= 3:
        all_probs = list(alternative_probabilities)
        direction_over = sum(1 for p in all_probs if p > 0.5)
        direction_under = len(all_probs) - direction_over
        if direction_over == len(all_probs) or direction_under == len(all_probs):
            # All agree on direction — calculate agreement strength
            try:
                _std = statistics.stdev(all_probs) if len(all_probs) >= 2 else 0.0
            except statistics.StatisticsError:
                _std = 0.0
            agreement_strength = max(0.0, 1.0 - _std)
            probability_agreement_bonus = agreement_strength * PROBABILITY_AGREEMENT_BONUS_MAX
            combined_score += probability_agreement_bonus
        else:
            # Disagreement on direction — penalty
            probability_agreement_bonus = -PROBABILITY_DISAGREEMENT_PENALTY
            combined_score += probability_agreement_bonus

    # --- 3C: Streak-adjusted confidence ---
    streak_adjustment = 0.0
    if streak_info is not None:
        streak_type = streak_info.get("type", "none")
        streak_length = int(streak_info.get("length", 0))
        _is_over_bet = probability_over >= 0.5
        if streak_type == "hot":
            base_adj = STREAK_HOT_OVER_BONUS if _is_over_bet else STREAK_HOT_UNDER_PENALTY
        elif streak_type == "cold":
            base_adj = STREAK_COLD_UNDER_BONUS if not _is_over_bet else STREAK_COLD_OVER_PENALTY
        else:
            base_adj = 0.0
        if streak_length > STREAK_LENGTH_DOUBLE_THRESHOLD:
            base_adj *= 2.0
        streak_adjustment = max(-STREAK_MAX_ADJUSTMENT, min(STREAK_MAX_ADJUSTMENT, base_adj))
        combined_score += streak_adjustment

    # --- CV Penalty Scaling: harsh penalty for very high variance stats ---
    # BEGINNER NOTE: When a stat has CV > CV_PENALTY_THRESHOLD, the projection
    # is inherently unreliable regardless of other signals.
    if stat_average > 0:
        _cv = stat_standard_deviation / stat_average
        if _cv > CV_PENALTY_THRESHOLD:
            # CV penalty: (CV - threshold) * scale points subtracted
            _cv_penalty = (_cv - CV_PENALTY_THRESHOLD) * CV_PENALTY_SCALE
            combined_score -= min(CV_PENALTY_MAX, _cv_penalty)

    # --- Apply Post-Scoring Penalties ---
    # W1: Line Sharpness Penalty — deduct when book has accurately priced the line
    # W5: Trap Line Penalty — deduct when a bait line is detected
    # W7: Calibration Adjustment — correct for systematic model over/underconfidence
    # Injury Status Penalty — deduct when player has a concerning availability status
    combined_score -= line_sharpness_penalty
    combined_score -= trap_line_penalty
    combined_score -= calibration_adjustment  # positive = historically overconfident
    combined_score -= injury_status_penalty

    # Clamp score to non-negative before applying multipliers —
    # multiplying a negative score by 0.9 would BOOST it toward zero.
    combined_score = max(0.0, combined_score)

    # Apply combo-stat confidence penalty — combo/fantasy stats have more variance
    _stat_type_lower = str(stat_type).lower() if stat_type else ""
    if _stat_type_lower in COMBO_STAT_TYPES:
        combined_score *= COMBO_STAT_CONFIDENCE_MULTIPLIER

    # Apply binary-stat confidence penalty — dunks, blocked shots, two-pointers
    # are essentially 0-or-1 outcomes with very high inherent variance.  The
    # model's projection for these stats is much less reliable than for
    # continuous stats like points, so we penalize the confidence score.
    if _stat_type_lower in BINARY_STAT_TYPES:
        combined_score *= BINARY_STAT_CONFIDENCE_MULTIPLIER

    # W2: Recency Regression-to-Mean Correction
    # Extreme recent performance (hot or cold streaks) tends to revert to the season
    # average. If the last 5 games show >25% deviation from the season average,
    # apply a regression penalty — the model should not be highly confident on
    # predictions driven by temporary streaks that are likely to normalize.
    if recent_form_ratio is not None:
        form_deviation_abs = abs(recent_form_ratio - 1.0)
        if form_deviation_abs > 0.25:
            # Penalty: 20 points per 1.0 (100%) deviation beyond the 25% threshold.
            # Equivalently, 2 pts per 10% excess deviation.
            # E.g., ratio=1.40 → excess=0.15 → 20*0.15 = 3.0 point penalty
            #        ratio=1.60 → excess=0.35 → 20*0.35 = 7.0 point penalty (capped at 8)
            excess = form_deviation_abs - 0.25
            regression_penalty = min(8.0, excess * 20.0)
            combined_score -= regression_penalty

    # --- Sample Size Correction: confidence scales with effective sample ---
    # BEGINNER NOTE: A player with 10 games played has far less reliable stats
    # than one with 50 games. The sample_factor multiplier reduces confidence
    # proportionally for low-game-count players (e.g. 10 games → 0.33 factor).
    if games_played is not None and games_played > 0:
        _sample_factor = min(1.0, games_played / SAMPLE_SIZE_FULL_GAMES)
        # Blend: don't fully zero out scores for new players — floor at SAMPLE_SIZE_FLOOR
        _sample_factor = max(SAMPLE_SIZE_FLOOR, _sample_factor)
        combined_score *= _sample_factor

    # Round to nearest whole number, clamped to 0-100
    final_score = round(max(0.0, min(100.0, combined_score)), 1)

    # --- 3A: Bayesian sample-size damping ---
    sample_size_discount = 1.0
    if games_played_season and 0 < games_played_season < BAYESIAN_SAMPLE_MIN_GAMES:
        sample_size_discount = 0.6 + 0.4 * (games_played_season / BAYESIAN_SAMPLE_MIN_GAMES)
        final_score *= sample_size_discount
        final_score = round(max(0.0, min(100.0, final_score)), 1)

    # ============================================================
    # END SECTION: Combine Scores with Weights
    # ============================================================

    # ============================================================
    # SECTION: Assign Tier and Direction
    # ============================================================

    # Determine the bet direction (over or under)
    if probability_over >= 0.5:
        bet_direction = "OVER"
    else:
        bet_direction = "UNDER"

    # Effective probability in the recommended direction (always ≥ 0.5)
    prob_in_direction = probability_over if bet_direction == "OVER" else (1.0 - probability_over)
    abs_edge = abs(edge_percentage)

    # ── C2: Hard Kill Switches (applied AFTER weighted score) ────
    # These are non-negotiable overrides that fire regardless of the score.
    should_avoid = False
    avoid_reasons = []

    # NOTE: CV-based auto-avoid was previously checked here as well, but
    # this duplicated the same check in edge_detection.should_avoid_prop().
    # When the QAM page merged both sources (OR'ing the flags), a prop with
    # high CV was double-counted — flagged by BOTH engines — making it
    # impossible to unflag.  The CV check now lives exclusively in
    # should_avoid_prop() which is the canonical source for avoid logic.
    # confidence.py still uses CV for SCORING (the cv_penalty on
    # combined_score) but no longer sets should_avoid based on CV alone.

    # Kill switch 2: edge < SILVER_MIN_EDGE_PCT → auto-Bronze
    # (Force the score down to Bronze range if edge is too small to warrant higher tier)
    # Uses SILVER_MIN_EDGE_PCT (4%) to be consistent with tier gating logic.
    if abs_edge < SILVER_MIN_EDGE_PCT:
        final_score = min(final_score, SILVER_TIER_MINIMUM_SCORE - 1)

    # ── C3: Min Edge Gate — Low edge flag ────────────────────────
    if abs_edge < LOW_EDGE_THRESHOLD:
        avoid_reasons.append(f"Low edge ({abs_edge:.1f}% < {LOW_EDGE_THRESHOLD}% minimum)")

    # 3D: Apply platform-specific tier premium (lower score for harder platforms)
    _platform_premium = PLATFORM_TIER_PREMIUMS.get(platform or "", 0)
    # We subtract the premium from the score used for tier assignment only
    _score_for_tier = final_score - _platform_premium

    # ── Assign tier with C3 raised thresholds + edge gates ───────
    if (
        _score_for_tier >= PLATINUM_TIER_MINIMUM_SCORE
        and prob_in_direction >= PLATINUM_MIN_PROBABILITY  # C2: min 60%
        and abs_edge >= PLATINUM_MIN_EDGE_PCT              # C3: min 10% edge
    ):
        tier_name = "Platinum"
        tier_emoji = "💎"
        recommendation = f"Elite {bet_direction} play — highest confidence"
    elif (
        _score_for_tier >= GOLD_TIER_MINIMUM_SCORE
        and prob_in_direction >= GOLD_MIN_PROBABILITY      # C2: min 55%
        and abs_edge >= GOLD_MIN_EDGE_PCT                  # C3: min 7% edge
    ):
        tier_name = "Gold"
        tier_emoji = "🥇"
        recommendation = f"Strong {bet_direction} play — good confidence"
    elif _score_for_tier >= SILVER_TIER_MINIMUM_SCORE and abs_edge >= SILVER_MIN_EDGE_PCT:
        tier_name = "Silver"
        tier_emoji = "🥈"
        recommendation = f"Moderate {bet_direction} lean — use with others"
    else:
        tier_name = "Bronze"
        tier_emoji = "🥉"
        recommendation = f"Weak {bet_direction} signal — consider avoiding"

    # Do Not Bet: scores below DO_NOT_BET_SCORE_THRESHOLD are flagged as
    # "Avoid" tier but no longer block rendering (Zero-Filter Recovery).
    if _score_for_tier < DO_NOT_BET_SCORE_THRESHOLD:
        tier_name = "Avoid"
        tier_emoji = "⛔"
        recommendation = f"Low confidence ({final_score:.0f}/100) — proceed with caution"
        avoid_reasons.append(f"Score {final_score:.0f} below Do-Not-Bet threshold ({DO_NOT_BET_SCORE_THRESHOLD})")

    # ── C2: Kill switch — downgrade Platinum/Gold below probability floor ─
    # If the tier is Platinum but probability is below 60%, force to Gold.
    # If the tier is Gold but probability is below 55%, force to Silver.
    if tier_name == "Platinum" and prob_in_direction < PLATINUM_MIN_PROBABILITY:
        tier_name = "Gold"
        tier_emoji = "🥇"
        recommendation = f"Strong {bet_direction} play — good confidence"
        avoid_reasons.append(f"Downgraded Platinum→Gold (prob {prob_in_direction:.1%} < {PLATINUM_MIN_PROBABILITY:.0%})")
    if tier_name == "Gold" and prob_in_direction < GOLD_MIN_PROBABILITY:
        tier_name = "Silver"
        tier_emoji = "🥈"
        recommendation = f"Moderate {bet_direction} lean — use with others"
        avoid_reasons.append(f"Downgraded Gold→Silver (prob {prob_in_direction:.1%} < {GOLD_MIN_PROBABILITY:.0%})")

    # 3A: Bayesian tier caps for very small samples
    if games_played_season is not None:
        if games_played_season < BAYESIAN_TIER_CAP_TINY:
            if tier_name in ("Platinum", "Gold", "Silver"):
                tier_name = "Bronze"
                tier_emoji = "🥉"
                recommendation = f"Small sample (only {games_played_season} games) — treat with caution"
        elif games_played_season < BAYESIAN_TIER_CAP_SMALL:
            if tier_name in ("Platinum", "Gold"):
                tier_name = "Silver"
                tier_emoji = "🥈"
                recommendation = f"Limited sample ({games_played_season} games) — moderate confidence only"

    # ============================================================
    # END SECTION: Assign Tier and Direction
    # ============================================================

    # Determine should_avoid from accumulated kill-switch reasons.
    # Previously hardcoded to False ("Zero-Filter Recovery"), which meant the
    # confidence engine's own red flags (high CV, low edge, do-not-bet score)
    # were cosmetic only.  Now we respect them: any genuine avoid reason sets
    # the flag.  Downstream code merges this with should_avoid_prop() results.
    should_avoid = bool(avoid_reasons)

    return {
        "confidence_score": _safe_float(final_score, 0.0),
        "tier": tier_name,
        "tier_emoji": tier_emoji,
        "direction": bet_direction,
        "recommendation": recommendation,
        "should_avoid": should_avoid,
        "avoid_reasons": avoid_reasons,
        "sample_size_discount": _safe_float(round(sample_size_discount, 3), 1.0),
        "probability_agreement_bonus": _safe_float(round(probability_agreement_bonus, 2), 0.0),
        "streak_adjustment": _safe_float(round(streak_adjustment, 2), 0.0),
        "score_breakdown": {
            "probability_score": _safe_float(round(probability_score, 1), 0.0),
            "edge_score": _safe_float(round(edge_score, 1), 0.0),
            "directional_score": _safe_float(round(directional_score, 1), 50.0),
            "matchup_score": _safe_float(round(matchup_score, 1), 50.0),
            "historical_score": _safe_float(round(historical_score, 1), 50.0),
            "sample_size_score": _safe_float(round(sample_size_score, 1), 50.0),
            "recent_form_score": _safe_float(round(recent_form_score, 1), 50.0),
        },
    }


# ============================================================
# SECTION: Helper Score Functions
# ============================================================

def _calculate_directional_agreement_score(directional_forces):
    """
    Score how much the directional forces agree on a direction.

    If 5 forces push OVER and 1 pushes UNDER, strong agreement.
    If 3 vs 3, weak agreement (more uncertain).

    Args:
        directional_forces (dict): With keys:
            'over_count' (int): Number of forces pushing OVER
            'under_count' (int): Number of forces pushing UNDER
            'over_strength' (float): Cumulative strength of over forces
            'under_strength' (float): Cumulative strength of under forces

    Returns:
        float: Score 0-100 (higher = more agreement)
    """
    over_count = directional_forces.get("over_count", 0)
    under_count = directional_forces.get("under_count", 0)
    total_count = over_count + under_count

    if total_count == 0:
        return 50.0  # No data = neutral

    # Calculate dominance: how one-sided is the vote?
    # 100% one side = max agreement
    dominant_count = max(over_count, under_count)
    agreement_ratio = dominant_count / total_count  # 0.5 to 1.0

    # Convert to 0-100 score
    # 0.5 ratio (tie) = 0 score, 1.0 ratio (all agree) = 100 score
    directional_score = (agreement_ratio - 0.5) * 200.0

    # Also factor in the strength of the forces
    over_strength = directional_forces.get("over_strength", 0.0)
    under_strength = directional_forces.get("under_strength", 0.0)
    total_strength = over_strength + under_strength

    if total_strength > 0:
        dominant_strength = max(over_strength, under_strength)
        strength_ratio = dominant_strength / total_strength
        strength_score = (strength_ratio - 0.5) * 200.0
        # Blend count-based and strength-based scores
        directional_score = (directional_score * 0.5) + (strength_score * 0.5)

    return max(0.0, min(100.0, directional_score))


def _calculate_consistency_score(stat_standard_deviation, stat_average):
    """
    Score a player's consistency for a given stat.

    Coefficient of variation (CV) = std / avg
    Lower CV = more consistent = more predictable = higher score.

    Args:
        stat_standard_deviation (float): Spread of the stat
        stat_average (float): Average value of the stat

    Returns:
        float: Score 0-100 (higher = more consistent)
    """
    if stat_average <= 0:
        return 50.0  # Can't calculate — return neutral

    # Coefficient of variation: std divided by mean
    coefficient_of_variation = stat_standard_deviation / stat_average

    # Scale: CV of 0.20 = very consistent (85 score)
    #        CV of 0.50 = average consistency (50 score)
    #        CV of 0.80 = very inconsistent (15 score)
    # Formula: score = 100 - (CV * 100)  capped at 0-100
    consistency_score = 100.0 - (coefficient_of_variation * 100.0)

    return max(0.0, min(100.0, consistency_score))


def _calculate_sample_size_score(games_played):
    """
    Score the reliability of season averages based on games played.

    More games = more reliable data = higher score.
    Uses a logistic-style curve so the score grows quickly early
    (0-20 games) and levels off after ~41 games (half a season).

    Args:
        games_played (int or None): Number of games played this season.
            None or 0 returns a neutral score of 50.

    Returns:
        float: Score 0-100 (higher = more reliable sample)
    """
    if not games_played or games_played <= 0:
        return 50.0  # No data — neutral

    # Cap benefit at 82 games (full season)
    games = min(games_played, 82)

    # Linearly scale: 0 games → 10, 41 games → 70, 82 games → 100
    # We use 41 as the "good enough" midpoint (half season)
    if games <= 41:
        score = 10.0 + (games / 41.0) * 60.0
    else:
        score = 70.0 + ((games - 41) / 41.0) * 30.0

    return max(0.0, min(100.0, score))


def _calculate_recent_form_score(recent_form_ratio, probability_over):
    """
    Score how recent form aligns with the predicted direction.

    A hot player (ratio > 1) boosts confidence in OVER picks.
    A cold player (ratio < 1) boosts confidence in UNDER picks.
    A player whose recent form contradicts the pick reduces confidence.

    Args:
        recent_form_ratio (float or None): last_5_avg / season_avg.
            > 1.0 = hot streak, < 1.0 = cold streak, 1.0 = neutral.
            None means no recent form data available.
        probability_over (float): P(over), used to determine direction.

    Returns:
        float: Score 0-100
    """
    if recent_form_ratio is None:
        return 50.0  # No recent form data — neutral

    bet_direction_is_over = probability_over >= 0.5

    # How far from neutral (1.0) is the recent form?
    form_deviation = recent_form_ratio - 1.0  # positive = hot, negative = cold

    if bet_direction_is_over:
        # OVER pick: hot streak is good, cold streak is bad
        alignment = form_deviation  # positive when aligned
    else:
        # UNDER pick: cold streak is good, hot streak is bad
        alignment = -form_deviation  # positive when aligned

    # Scale to 0-100: strong alignment → high score, misalignment → low score
    # The multiplier 200.0 maps the alignment range of [-0.25, +0.25] to [-50, +50],
    # which when added to the base 50 gives a final score in [0, 100].
    # A ±25% recent form deviation is considered a strong signal.
    scaled = 50.0 + (alignment * 200.0)
    return max(0.0, min(100.0, scaled))


def get_tier_color(tier_name):
    """
    Get the display color for each tier (for Streamlit UI).

    Args:
        tier_name (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'

    Returns:
        str: Hex color code
    """
    # Color map for each tier
    tier_color_map = {
        "Platinum": "#E5E4E2",  # Platinum silver
        "Gold": "#FFD700",      # Gold yellow
        "Silver": "#C0C0C0",    # Silver grey
        "Bronze": "#CD7F32",    # Bronze brown
    }
    return tier_color_map.get(tier_name, "#FFFFFF")  # White default


def calculate_risk_score(confidence_result, edge_pct, cv, platform=None) -> dict:
    """
    Calculate a composite 1-10 risk rating for a prop pick. (3E)

    Combines confidence score, edge percentage, and coefficient of variation
    into a single risk rating. Lower scores = safer bets.

    BEGINNER NOTE: A "risk score" of 1-3 means the pick has strong confidence,
    good edge, and low variance. A score of 7-10 means high uncertainty —
    the pick might win, but the risk/reward isn't favorable.

    Args:
        confidence_result (dict): Output of calculate_confidence_score()
        edge_pct (float): Edge percentage (e.g. 12.5 for 12.5%)
        cv (float): Coefficient of variation (std/mean, e.g. 0.35)
        platform (str, optional): Platform name for context

    Returns:
        dict: {
            'risk_score': float (1-10),
            'risk_label': str ('Low Risk', 'Medium Risk', 'High Risk'),
            'risk_factors': list[str],
        }

    Example:
        confidence=75, edge=10%, cv=0.30 → risk_score ≈ 3.5 (Low Risk)
        confidence=45, edge=3%, cv=0.55 → risk_score ≈ 7.2 (High Risk)
    """
    confidence = float(confidence_result.get("confidence_score", 50.0))
    abs_edge = abs(float(edge_pct))
    safe_cv = max(0.0, min(1.0, float(cv)))

    # Risk formula: risk = 10 - (confidence/10 * 0.4 + edge_pct * 0.3 + (1-cv)*10 * 0.3)
    risk = 10.0 - (
        (confidence / 10.0) * 0.4
        + abs_edge * 0.3
        + (1.0 - safe_cv) * 10.0 * 0.3
    )
    risk = round(max(1.0, min(10.0, risk)), 2)

    if risk <= 3:
        risk_label = "Low Risk"
    elif risk <= 6:
        risk_label = "Medium Risk"
    else:
        risk_label = "High Risk"

    risk_factors = []
    if confidence < 55:
        risk_factors.append(f"Low confidence score ({confidence:.0f}/100)")
    if abs_edge < 5.0:
        risk_factors.append(f"Thin edge ({abs_edge:.1f}%)")
    if cv > 0.40:
        risk_factors.append(f"High variance stat (CV={cv:.2f})")
    tier = confidence_result.get("tier", "")
    if tier in ("Bronze", "Avoid"):
        risk_factors.append(f"Low tier ({tier})")

    return {
        "risk_score": _safe_float(risk, 5.0),
        "risk_label": risk_label,
        "risk_factors": risk_factors,
    }


def enforce_tier_distribution(all_picks_results, max_platinum_pct=0.10, max_gold_pct=0.25) -> list:
    """
    Enforce a healthy tier distribution to prevent overconfidence inflation. (3F)

    If more picks than expected are classified at high tiers, downgrade
    the weakest ones to maintain realistic tier proportions.

    BEGINNER NOTE: If the model gives 40% of picks a Platinum rating,
    something is wrong — real Platinums should be rare. This function
    enforces realistic maximums: ≤10% Platinum, ≤25% Gold.

    Args:
        all_picks_results (list of dict): Each dict is the output of
            calculate_confidence_score() for one pick.
        max_platinum_pct (float): Maximum fraction of picks allowed to be Platinum.
            Default 0.10 (10%).
        max_gold_pct (float): Maximum fraction of picks allowed to be Gold or better.
            Default 0.25 (25%).

    Returns:
        tuple: (adjusted_results: list of dict, any_downgrades_occurred: bool)

    Example:
        If 5 of 10 picks are Platinum (50% > 10% max):
        → downgrade the 4 weakest Platinums to Gold
        → return adjusted list + True (downgrades occurred)
    """
    if not all_picks_results:
        return all_picks_results, False

    results = [dict(r) for r in all_picks_results]  # shallow copy
    n = len(results)
    any_downgrades = False

    max_platinum = max(1, int(math.floor(n * max_platinum_pct)))
    max_gold_total = max(1, int(math.floor(n * max_gold_pct)))

    # Sort by confidence score descending (strongest picks first)
    platinums = sorted(
        [r for r in results if r.get("tier") == "Platinum"],
        key=lambda r: r.get("confidence_score", 0),
        reverse=True,
    )
    golds = sorted(
        [r for r in results if r.get("tier") == "Gold"],
        key=lambda r: r.get("confidence_score", 0),
        reverse=True,
    )

    # Downgrade excess Platinums to Gold
    if len(platinums) > max_platinum:
        excess = platinums[max_platinum:]  # Weakest Platinums (already sorted desc)
        for pick in excess:
            for r in results:
                if r is pick or (
                    r.get("confidence_score") == pick.get("confidence_score")
                    and r.get("tier") == "Platinum"
                ):
                    r["tier"] = "Gold"
                    r["tier_emoji"] = "Gold"
                    r["recommendation"] = (
                        r.get("recommendation", "").replace("Elite", "Strong")
                        or "Strong play — good confidence"
                    )
                    any_downgrades = True
                    break

    # Re-count golds after Platinum downgrades
    current_gold_count = sum(1 for r in results if r.get("tier") in ("Platinum", "Gold"))
    if current_gold_count > max_gold_total:
        # Find the weakest Golds to downgrade
        all_golds_now = sorted(
            [r for r in results if r.get("tier") == "Gold"],
            key=lambda r: r.get("confidence_score", 0),
            reverse=True,
        )
        excess_gold = max(0, current_gold_count - max_gold_total)
        for pick in all_golds_now[-excess_gold:]:  # Weakest Golds
            pick["tier"] = "Silver"
            pick["tier_emoji"] = "🥈"
            pick["recommendation"] = (
                pick.get("recommendation", "").replace("Strong", "Moderate")
                or "Moderate lean — use with others"
            )
            any_downgrades = True

    return results, any_downgrades

# ============================================================
# END SECTION: Helper Score Functions
# ============================================================
