# ============================================================
# FILE: engine/projections.py
# PURPOSE: Build stat projections for players given tonight's
#          game context (opponent, pace, home/away, rest).
#          Takes raw player averages and adjusts them for
#          the specific matchup.
# CONNECTS TO: data_manager.py (gets player data),
#              simulation.py (gets the adjusted projections)
# CONCEPTS COVERED: Matchup adjustments, pace adjustments,
#                   per-game rate calculations
# ============================================================

# Standard library only
import math  # For rounding and calculation helpers
import logging

from engine.math_helpers import _safe_float

try:
    from engine.rotation_tracker import get_minutes_adjustment
    _ROTATION_TRACKER_AVAILABLE = True
except ImportError:
    _ROTATION_TRACKER_AVAILABLE = False

# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# League average game total (combined score of both teams).
# ~220 points per game as of the 2025-26 NBA season.
# Update this each season as pace/scoring trends shift.
LEAGUE_AVERAGE_GAME_TOTAL = 220.0

# League average possessions per game (pace baseline).
# Used to compute pace adjustment factors.
LEAGUE_AVERAGE_PACE = 98.5

# Recent form blending thresholds.
# When game log data is available the projection uses decay-weighted recency
# averaging instead of a flat season-average blend.
#
# ≥ RECENCY_FULL_THRESHOLD games  → use decay-weighted avg (75%) + season avg (25%)
# ≥ RECENCY_FALLBACK_THRESHOLD games → plain recent avg (60%) + season avg (40%)
# < RECENCY_FALLBACK_THRESHOLD games → season average only (Bayesian shrinkage still applies)
RECENCY_FULL_THRESHOLD   = 10   # games needed for full decay-weighted model
RECENCY_FALLBACK_THRESHOLD = 10  # match full threshold — no partial 5-game mode
RECENCY_WEIGHT   = 0.75   # weight of decay-weighted recent avg when ≥10 games
SEASON_WEIGHT_HI = 0.25   # weight of season avg when ≥10 games
SEASON_AVG_WEIGHT = 0.60  # weight of season avg when <10 games (legacy fallback)
RECENT_FORM_WEIGHT = 0.40 # weight of simple recent avg when <10 games

# Exponential decay factor for recency weighting.
# Decay of 0.85 means each additional game back is weighted 15% less than the game
# immediately after it.  A value of 1.0 would give equal weight to all games.
RECENCY_DECAY = 0.80

# Streak detection constants.
# If the last STREAK_WINDOW games are all above/below the weighted recent average
# by more than STREAK_THRESHOLD, apply a small multiplier to the projection.
STREAK_WINDOW    = 5     # consecutive games to confirm a streak (raised from 3)
STREAK_THRESHOLD = 0.12  # 12% above/below triggers streak detection
STREAK_MULTIPLIER_HOT  = 1.05  # +5% for a confirmed hot streak
STREAK_MULTIPLIER_COLD = 0.95  # −5% for a confirmed cold streak

# Back-to-back fatigue: applied to rest_factor when player played yesterday.
BACK_TO_BACK_FATIGUE_MULTIPLIER = 0.95  # 5% performance reduction

# Spread threshold above which a blowout minutes-risk note is added.
BLOWOUT_SPREAD_THRESHOLD = 10  # points

# Injury-status stat reduction multipliers
QUESTIONABLE_REDUCTION = 0.92    # 8% reduction for Questionable
DOUBTFUL_REDUCTION = 0.75        # 25% reduction for Doubtful
RUST_FACTOR_REDUCTION = 0.94     # 6% reduction for first game back after extended absence
RUST_FACTOR_GAMES_THRESHOLD = 3  # Minimum games missed to trigger rust factor

# ============================================================
# SECTION: Team Blowout Tendency Dictionary (W6)
# Different coaches have very different policies on when to pull
# starters in blowout games. Some teams (e.g., SAS) pull starters
# early at +15; others (e.g., OKC under SGA) keep them in longer.
# Values > 1.0 = team blows out MORE than average (increases risk)
# Values < 1.0 = team manages leads conservatively (star sits earlier)
# ============================================================

TEAM_BLOWOUT_TENDENCY = {
    # Teams that tend to keep starters in / run up scores (higher risk)
    "OKC": 1.15,   # SGA era: aggressive, plays to win big
    "BOS": 1.10,   # Aggressive offensive rotations
    "DEN": 1.10,   # Jokic+ keeps stats up in wins
    "MIL": 1.08,   # Giannis plays heavy minutes
    "PHX": 1.05,   # Up-tempo, doesn't coast
    # Teams that pull starters early / manage load (lower blowout risk for stars)
    "SAS": 0.82,   # Popovich coaching philosophy: rest early
    "MEM": 0.85,   # Development-first, rests stars
    "DET": 0.88,   # Rebuilding team — load management
    "UTA": 0.88,   # Building, rests stars
    "WAS": 0.90,   # Similar rebuilding approach
    # Neutral teams (most of the league)
    "LAL": 1.00, "GSW": 1.00, "LAC": 1.00, "PHI": 1.00,
    "BKN": 1.00, "NYK": 1.00, "MIA": 1.00, "ATL": 1.00,
    "CHI": 1.00, "CLE": 1.00, "IND": 1.00, "TOR": 1.00,
    "NOP": 1.00, "HOU": 1.00, "DAL": 1.00, "MIN": 1.00,
    "POR": 1.00, "SAC": 1.00, "CHA": 1.00, "ORL": 1.00,
}

# ============================================================
# END SECTION: Team Blowout Tendency Dictionary
# ============================================================


# ============================================================
# SECTION: Bayesian Positional Priors (C6)
# When a player has fewer than 25 games, blend their stats
# toward these positional league averages.
# ============================================================

BAYESIAN_SMALL_SAMPLE_THRESHOLD = 25  # games played below which to blend

POSITION_PRIORS = {
    "PG": {"points": 18.5, "rebounds": 4.0, "assists": 6.5, "threes": 2.2,
           "steals": 1.3, "blocks": 0.4, "turnovers": 2.5, "ftm": 3.5,
           "fga": 13.5, "fgm": 6.2, "fta": 4.5, "fta_made": 3.5,
           "offensive_rebounds": 0.5, "defensive_rebounds": 3.5, "personal_fouls": 2.0, "minutes": 30.0},
    "SG": {"points": 17.0, "rebounds": 3.8, "assists": 4.0, "threes": 2.0,
           "steals": 1.1, "blocks": 0.4, "turnovers": 1.8, "ftm": 3.2,
           "fga": 13.0, "fgm": 5.8, "fta": 4.0, "fta_made": 3.2,
           "offensive_rebounds": 0.5, "defensive_rebounds": 3.3, "personal_fouls": 2.0, "minutes": 30.0},
    "SF": {"points": 16.0, "rebounds": 5.5, "assists": 3.5, "threes": 1.5,
           "steals": 1.0, "blocks": 0.6, "turnovers": 1.5, "ftm": 2.8,
           "fga": 12.0, "fgm": 5.5, "fta": 3.5, "fta_made": 2.8,
           "offensive_rebounds": 0.8, "defensive_rebounds": 4.7, "personal_fouls": 2.1, "minutes": 29.0},
    "PF": {"points": 15.5, "rebounds": 7.0, "assists": 3.0, "threes": 1.0,
           "steals": 0.8, "blocks": 0.8, "turnovers": 1.5, "ftm": 3.1,
           "fga": 11.5, "fgm": 5.3, "fta": 4.0, "fta_made": 3.1,
           "offensive_rebounds": 1.5, "defensive_rebounds": 5.5, "personal_fouls": 2.4, "minutes": 28.0},
    "C":  {"points": 14.0, "rebounds": 9.0, "assists": 2.5, "threes": 0.5,
           "steals": 0.7, "blocks": 1.4, "turnovers": 1.8, "ftm": 2.9,
           "fga": 10.5, "fgm": 5.0, "fta": 3.8, "fta_made": 2.9,
           "offensive_rebounds": 2.5, "defensive_rebounds": 6.5, "personal_fouls": 2.8, "minutes": 27.0},
}
# Default prior for unknown positions
_DEFAULT_POSITION_PRIOR = POSITION_PRIORS["SF"]

# ============================================================
# END SECTION: Bayesian Positional Priors
# ============================================================


# ============================================================
# SECTION: Teammate-Out Usage Adjustment Constants (C4)
# When a high-usage teammate is OUT, remaining players absorb
# that usage. These bumps are applied before the simulation.
# ============================================================

# Bump factors for teammate absence
TEAMMATE_OUT_PRIMARY_BUMP = 0.08    # +8% for primary option (top scorer/assister) out
TEAMMATE_OUT_SECONDARY_BUMP = 0.05  # +5% for secondary option out
TEAMMATE_OUT_MAX_BOOST = 0.15       # Cap total teammate-out boost at +15%

# ============================================================
# END SECTION: Teammate-Out Usage Adjustment Constants
# ============================================================


# ============================================================
# SECTION: Recency Weighting Helpers
# ============================================================

def calculate_recency_weighted_average(game_log_values, decay=RECENCY_DECAY):
    """
    Compute an exponentially decay-weighted average of recent game values.

    More recent games receive higher weight.  The most recent game (index 0)
    has weight 1.0; each subsequent older game is multiplied by *decay*.

    Args:
        game_log_values (list[float]): Stat values ordered most-recent-first.
            Must contain at least one element.
        decay (float): Per-game decay factor in (0, 1].  Default: RECENCY_DECAY.

    Returns:
        float: Weighted average.  Falls back to the arithmetic mean if all
        weights are zero (should only happen with decay=0).
    """
    if not game_log_values:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    for i, val in enumerate(game_log_values):
        w = decay ** i
        weighted_sum += val * w
        total_weight += w

    if total_weight == 0:
        return sum(game_log_values) / len(game_log_values)
    return weighted_sum / total_weight


def detect_streak(game_log_values, reference_avg, threshold=STREAK_THRESHOLD):
    """
    Detect a hot or cold streak in the last STREAK_WINDOW game log values.

    A streak is confirmed when ALL of the last *STREAK_WINDOW* games are
    above (hot) or below (cold) *reference_avg* by more than *threshold*.

    Args:
        game_log_values (list[float]): Stat values ordered most-recent-first.
        reference_avg (float): The baseline to compare against (e.g., decay-
            weighted recent average).
        threshold (float): Fractional deviation required. Default: STREAK_THRESHOLD.

    Returns:
        float: STREAK_MULTIPLIER_HOT for hot, STREAK_MULTIPLIER_COLD for cold,
        or 1.0 if no streak is detected or data is insufficient.
    """
    if not game_log_values or reference_avg <= 0:
        return 1.0

    window = game_log_values[:STREAK_WINDOW]
    if len(window) < STREAK_WINDOW:
        return 1.0

    hot_threshold  = reference_avg * (1.0 + threshold)
    cold_threshold = reference_avg * (1.0 - threshold)

    if all(v > hot_threshold for v in window):
        return STREAK_MULTIPLIER_HOT
    if all(v < cold_threshold for v in window):
        return STREAK_MULTIPLIER_COLD
    return 1.0


# ============================================================
# END SECTION: Recency Weighting Helpers
# ============================================================


def compute_league_average_game_total(teams_data=None):
    """
    Compute league-average game total from live team data.
    Falls back to LEAGUE_AVERAGE_GAME_TOTAL constant if data unavailable.

    The league-average game total shifts as the season progresses and scoring
    trends change. When live teams_data is available this function derives the
    value dynamically; otherwise the hardcoded seasonal constant is returned.

    Args:
        teams_data (list of dict, optional): Team rows from teams.csv or the
            live data service. Each dict should contain at minimum one of:
            - "pts" (float): team points per game (offensive)
            - "opp_pts" or "pts_against" (float): opponent points per game

    Returns:
        float: Estimated league-average combined game total (both teams' scores).
    """
    if not teams_data:
        return LEAGUE_AVERAGE_GAME_TOTAL
    try:
        totals = []
        for team in teams_data:
            ppg = float(team.get("pts", 0) or 0)
            opp_ppg = float(team.get("opp_pts", 0) or team.get("pts_against", 0) or 0)
            if ppg > 0 and opp_ppg > 0:
                totals.append(ppg + opp_ppg)
        if totals:
            return sum(totals) / len(totals)
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[Projections] Unexpected error: {_exc}")
    return LEAGUE_AVERAGE_GAME_TOTAL


def get_live_league_context(teams_data=None) -> dict:
    """
    Fetch real league-level context values (pace, game total, blowout rates)
    from the NBA API, falling back to module-level constants on failure.

    Calls ``data.nba_data_service.get_player_estimated_metrics()`` to derive
    a live league-average pace from the season's estimated metrics.  When
    that call fails or returns nothing, the hardcoded ``LEAGUE_AVERAGE_PACE``
    and ``LEAGUE_AVERAGE_GAME_TOTAL`` constants are used instead.

    Parameters
    ----------
    teams_data : list[dict] | None
        Optional team-stats list (from teams.csv / data_manager) used to
        compute the game total via ``compute_league_average_game_total()``.

    Returns
    -------
    dict
        Keys:
          ``pace``        — float: league-average possessions per 48 min
          ``game_total``  — float: league-average combined score per game
          ``source``      — str: 'live' if derived from API, 'fallback' otherwise
    """
    pace = None

    # Attempt to derive pace from player estimated metrics (E_PACE column).
    try:
        from data.db_service import get_player_estimated_metrics as _get_metrics
        metrics = _get_metrics()
        if metrics:
            paces = []
            for row in metrics:
                p = row.get("E_PACE") or row.get("e_pace")
                if p is not None:
                    try:
                        paces.append(float(p))
                    except (TypeError, ValueError):
                        pass
            if paces:
                pace = round(sum(paces) / len(paces), 2)
    except Exception as _exc:
        logging.getLogger(__name__).debug(
            "get_live_league_context: estimated metrics unavailable — %s", _exc
        )

    game_total = compute_league_average_game_total(teams_data)
    source = "live" if pace is not None else "fallback"

    return {
        "pace": pace if pace is not None else LEAGUE_AVERAGE_PACE,
        "game_total": game_total,
        "source": source,
    }


def _compute_usage_boost(advanced_context: dict | None, base_projection: float) -> float:
    """
    Apply a usage-rate boost/penalty to a base projection.

    When real usage-rate data is available from the NBA API (via
    ``fetch_box_score_usage`` or ``enrich_simulation_with_advanced_stats``),
    this helper scales the base projection proportionally.

    A player with 30% usage receives a small positive nudge; a player with
    15% usage receives a small negative nudge.  League average usage is
    normalised to ~20% (1/5 of 5 on-court players).

    Parameters
    ----------
    advanced_context : dict | None
        Dict that may contain ``usage_pct`` (float, 0–1 scale) from the
        ``enrich_simulation_with_advanced_stats`` function or the
        ``fetch_box_score_usage`` endpoint.
    base_projection : float
        The pre-boost stat projection value.

    Returns
    -------
    float
        Adjusted projection value.  Returns *base_projection* unchanged when
        no valid usage data is available or when the boost would be negligible
        (|boost| < 0.5%).
    """
    if not advanced_context:
        return base_projection

    usage_raw = advanced_context.get("usage_pct") or advanced_context.get("USG_PCT")
    if usage_raw is None:
        return base_projection

    try:
        usage = float(usage_raw)
    except (TypeError, ValueError):
        return base_projection

    # Normalise from percentage (e.g. 27.4) or decimal (e.g. 0.274)
    if usage > 1.0:
        usage = usage / 100.0

    # League-average usage for an active player ≈ 0.20
    _LEAGUE_AVG_USAGE = 0.20
    if usage <= 0:
        return base_projection

    # Multiplier: usage at league avg → 1.0; each 1% above/below → ±1.5%
    # The 1.5 factor was calibrated so that a player with 30% usage (10pp above
    # league avg) receives a +15% boost — matching the ~15% TEAMMATE_OUT_MAX_BOOST
    # cap used in projections.py, creating a consistent scale across the model.
    _USAGE_MULTIPLIER_FACTOR = 1.5
    multiplier = 1.0 + (usage - _LEAGUE_AVG_USAGE) * _USAGE_MULTIPLIER_FACTOR

    # Cap the adjustment: ±12% maximum to avoid extremes from small-sample data
    multiplier = max(0.88, min(1.12, multiplier))

    # Only apply if the adjustment is meaningful (> 0.5%)
    if abs(multiplier - 1.0) < 0.005:
        return base_projection

    return _safe_float(base_projection * multiplier, base_projection)


def build_player_projection(
    player_data: dict,
    opponent_team_abbreviation: str,
    is_home_game: bool,
    rest_days: int,
    game_total: float,
    defensive_ratings_data: list,
    teams_data: list,
    recent_form_games: list | None = None,
    vegas_spread: float = 0.0,
    minutes_adjustment_factor: float = 1.0,
    teammate_out_notes: str | None = None,
    played_yesterday: bool = False,
    rolling_defensive_data: list | None = None,
    game_context: dict | None = None,
    advanced_context: dict | None = None,
):
    """
    Build a complete stat projection for one player tonight.

    Adjusts their season averages based on:
    - Opponent defensive rating vs their position
    - Game pace (faster game = more possessions = more stats)
    - Home court advantage
    - Rest days (back-to-back fatigue)
    - Vegas total (high total = projected to be high-scoring game)
    - Vegas spread (used for smart blowout risk calculation)
    - Recent form: last 5 game averages weighted more heavily
    - Minutes adjustment for teammate injuries (W8/C4)
    - Rolling opponent defensive window (C9): blends 10-game rolling
      defensive data with season averages when available

    Args:
        player_data (dict): Player row from players.csv (live data retrieved via nba_api).
            Keys: name, team, position, points_avg, etc.
        opponent_team_abbreviation (str): e.g., "GSW", "BOS"
        is_home_game (bool): True if playing at home tonight
        rest_days (int): Days of rest since last game (0=back-to-back)
        game_total (float): Vegas over/under total for tonight's game
        defensive_ratings_data (list of dict): From defensive_ratings.csv
        teams_data (list of dict): From teams.csv
        recent_form_games (list of dict, optional): Last N game log rows.
            Each row should have numeric keys matching stat names
            (e.g., 'pts', 'reb', 'ast'). When provided, projections
            blend season averages 60% + recent-form averages 40%.
        vegas_spread (float, optional): Vegas point spread for tonight.
            Positive = player's team is favored by this many points.
            Used by the smart blowout risk formula (W6).
        minutes_adjustment_factor (float, optional): Multiplier for
            projected minutes due to teammate injury/absence (W8).
            > 1.0 = more minutes (teammate out), 1.0 = normal.
            Passed in from injury report analysis.
        teammate_out_notes (list of str, optional): Human-readable notes
            about which teammates are out and how it affects this player (W8).
            Included in the returned projection for display purposes.
        played_yesterday (bool, optional): True if this is a back-to-back
            game (player played yesterday). Applies a 0.94 fatigue multiplier
            to the rest adjustment factor. Default False.
        rolling_defensive_data (dict, optional): Rolling 10-game defensive
            window data keyed by team abbreviation. (C9)
            Format: {team_abbrev: {position: rolling_factor}}
            e.g., {"BOS": {"PG": 0.88, "SG": 0.91, ...}}
            When provided, blends rolling factor with season average factor:
              defense_factor = 0.5 * season_factor + 0.5 * rolling_factor
            When None or opponent not found, falls back to season average
            from defensive_ratings_data (current default behavior).
        advanced_context (dict, optional): Real advanced stats from the NBA
            API (via ``enrich_simulation_with_advanced_stats`` or
            ``fetch_box_score_usage``).  When provided, the following keys
            are used:
            - ``usage_pct`` (float): Player usage rate (0–1 or 0–100 scale).
              Applied as a multiplier to points, assists, and threes via
              ``_compute_usage_boost()``.
            Falls back gracefully if the dict is None or missing keys.

    Returns:
        dict: Projected stats for tonight with adjustment factors:
            - 'projected_points': float
            - 'projected_rebounds': float
            - 'projected_assists': float
            - 'projected_threes': float
            - 'projected_steals': float
            - 'projected_blocks': float
            - 'projected_turnovers': float
            - 'projected_minutes': float (C1: estimated minutes for tonight)
            - 'pace_factor': float (multiplier, ~0.9-1.1)
            - 'defense_factor': float (multiplier, ~0.88-1.12)
            - 'home_away_factor': float (small +/-)
            - 'rest_factor': float (multiplier, ~0.9-1.0)
            - 'blowout_risk': float (0.0-1.0)
            - 'overall_adjustment': float (combined multiplier)
            - 'recent_form_ratio': float or None (last5_avg / season_avg)
            - 'minutes_adjustment_factor': float (W8: teammate injury impact)
            - 'teammate_out_notes': list of str (W8/C4: teammate impact notes)
            - 'notes': list of str (game-context warnings, e.g. back-to-back)
            - 'bayesian_shrinkage_applied': bool (C6: True if sample < 25 games)

    Example:
        LeBron at home vs weak defense + fast pace →
        projected_points might be 27.1 instead of his 24.8 average
    """
    # ============================================================
    # SECTION: Extract Player's Season Averages
    # ============================================================

    # Get each stat average from the player data dictionary
    season_points_average = float(player_data.get("points_avg", 0))
    season_rebounds_average = float(player_data.get("rebounds_avg", 0))
    season_assists_average = float(player_data.get("assists_avg", 0))
    season_threes_average = float(player_data.get("threes_avg", 0))
    season_steals_average = float(player_data.get("steals_avg", 0))
    season_blocks_average = float(player_data.get("blocks_avg", 0))
    season_turnovers_average = float(player_data.get("turnovers_avg", 0))
    player_position = player_data.get("position", "SF")  # Default to SF if missing
    games_played = int(player_data.get("games_played", player_data.get("gp", 82)) or 82)
    season_minutes_average = float(player_data.get("minutes_avg", player_data.get("min", 30.0)) or 30.0)
    # Extended stat averages
    season_ftm_average                = float(player_data.get("ftm_avg", 0))
    season_fta_average                = float(player_data.get("fta_avg", 0))
    season_fga_average                = float(player_data.get("fga_avg", 0))
    season_fgm_average                = float(player_data.get("fgm_avg", 0))
    season_offensive_rebounds_average = float(player_data.get("offensive_rebounds_avg", 0))
    season_defensive_rebounds_average = float(player_data.get("defensive_rebounds_avg", 0))
    season_personal_fouls_average     = float(player_data.get("personal_fouls_avg", 0))

    # ============================================================
    # END SECTION: Extract Player's Season Averages
    # ============================================================

    # ============================================================
    # SECTION: Bayesian Shrinkage for Small Samples (C6)
    # When games_played < 25, blend player stats toward positional
    # league averages to avoid over-fitting to a small sample.
    # ============================================================

    bayesian_shrinkage_applied = False
    if games_played < BAYESIAN_SMALL_SAMPLE_THRESHOLD:
        # Weight formula: w = min(games_played / 25, 1.0)
        # At 0 games: 0% player, 100% prior
        # At 25+ games: 100% player, 0% prior
        w = min(games_played / BAYESIAN_SMALL_SAMPLE_THRESHOLD, 1.0)
        prior = POSITION_PRIORS.get(player_position, _DEFAULT_POSITION_PRIOR)

        season_points_average   = w * season_points_average   + (1 - w) * prior["points"]
        season_rebounds_average = w * season_rebounds_average + (1 - w) * prior["rebounds"]
        season_assists_average  = w * season_assists_average  + (1 - w) * prior["assists"]
        season_threes_average   = w * season_threes_average   + (1 - w) * prior["threes"]
        season_steals_average   = w * season_steals_average   + (1 - w) * prior["steals"]
        season_blocks_average   = w * season_blocks_average   + (1 - w) * prior["blocks"]
        season_turnovers_average= w * season_turnovers_average+ (1 - w) * prior["turnovers"]
        bayesian_shrinkage_applied = True

    # ============================================================
    # END SECTION: Bayesian Shrinkage for Small Samples
    # ============================================================

    # ============================================================
    # SECTION: Recent Form Blending
    # When game log data is available, use decay-weighted recency
    # averaging for a more responsive projection.
    #
    # ≥ RECENCY_FULL_THRESHOLD (10) games:
    #   decay-weighted recent avg (75%) + season avg (25%)
    #   + streak multiplier if last 3 games all above/below baseline by >15%
    # ≥ RECENCY_FALLBACK_THRESHOLD (5) games:
    #   plain recent avg (40%) + season avg (60%)  — legacy fallback
    # < RECENCY_FALLBACK_THRESHOLD games:
    #   season average only (Bayesian shrinkage still applies above)
    # ============================================================

    recent_form_ratio = None  # Will be set if we have game log data
    recent_form_ratios = None  # Per-stat form ratios dict

    if recent_form_games and len(recent_form_games) >= RECENCY_FALLBACK_THRESHOLD:
        # Map game-log keys to stat names
        form_key_map = {
            "points": "pts",
            "rebounds": "reb",
            "assists": "ast",
            "threes": "fg3m",
            "steals": "stl",
            "blocks": "blk",
            "turnovers": "tov",
        }

        def _extract_vals(games, log_key):
            """Extract numeric values for a stat from game logs (most-recent first)."""
            vals = []
            for g in games:
                v = g.get(log_key, g.get(log_key.lower(), None))
                if v is not None:
                    try:
                        vals.append(float(v))
                    except (TypeError, ValueError):
                        pass
            return vals

        def _recent_avg(games, log_key, fallback):
            """Simple arithmetic average for fallback use."""
            vals = _extract_vals(games, log_key)
            return sum(vals) / len(vals) if vals else fallback

        n_games = len(recent_form_games)

        if n_games >= RECENCY_FULL_THRESHOLD:
            # Full decay-weighted model
            def _blend_stat(season_val, log_key):
                vals = _extract_vals(recent_form_games, log_key)
                if not vals:
                    return season_val
                decay_avg = calculate_recency_weighted_average(vals)
                blended = RECENCY_WEIGHT * decay_avg + SEASON_WEIGHT_HI * season_val
                return blended

            # Compute per-stat recent form ratios so downstream confidence
            # calculations use the correct stat, not just points.
            def _form_ratio(log_key, season_avg):
                vals = _extract_vals(recent_form_games, log_key)
                if vals and season_avg > 0:
                    return round(calculate_recency_weighted_average(vals) / season_avg, 3)
                return None

            recent_form_ratio = _form_ratio(form_key_map["points"], season_points_average)
            recent_form_ratios = {
                "points":    recent_form_ratio,
                "rebounds":  _form_ratio(form_key_map["rebounds"], season_rebounds_average),
                "assists":   _form_ratio(form_key_map["assists"], season_assists_average),
                "threes":    _form_ratio(form_key_map["threes"], season_threes_average),
                "steals":    _form_ratio(form_key_map["steals"], season_steals_average),
                "blocks":    _form_ratio(form_key_map["blocks"], season_blocks_average),
                "turnovers": _form_ratio(form_key_map["turnovers"], season_turnovers_average),
            }

            season_points_average   = _blend_stat(season_points_average,   form_key_map["points"])
            season_rebounds_average = _blend_stat(season_rebounds_average, form_key_map["rebounds"])
            season_assists_average  = _blend_stat(season_assists_average,  form_key_map["assists"])
            season_threes_average   = _blend_stat(season_threes_average,   form_key_map["threes"])
            season_steals_average   = _blend_stat(season_steals_average,   form_key_map["steals"])
            season_blocks_average   = _blend_stat(season_blocks_average,   form_key_map["blocks"])
            season_turnovers_average= _blend_stat(season_turnovers_average,form_key_map["turnovers"])

        else:
            # Fallback: simple recent-average blend (5–9 games)
            pts_key = form_key_map["points"]
            recent_pts = _recent_avg(recent_form_games, pts_key, season_points_average)

            if season_points_average > 0:
                recent_form_ratio = round(recent_pts / season_points_average, 3)

            # Per-stat form ratios for the fallback path
            def _fallback_ratio(log_key, season_avg):
                val = _recent_avg(recent_form_games, log_key, season_avg)
                return round(val / season_avg, 3) if season_avg > 0 else None

            recent_form_ratios = {
                "points":    recent_form_ratio,
                "rebounds":  _fallback_ratio(form_key_map["rebounds"], season_rebounds_average),
                "assists":   _fallback_ratio(form_key_map["assists"], season_assists_average),
                "threes":    _fallback_ratio(form_key_map["threes"], season_threes_average),
                "steals":    _fallback_ratio(form_key_map["steals"], season_steals_average),
                "blocks":    _fallback_ratio(form_key_map["blocks"], season_blocks_average),
                "turnovers": _fallback_ratio(form_key_map["turnovers"], season_turnovers_average),
            }

            _blend = lambda season, recent: season * SEASON_AVG_WEIGHT + recent * RECENT_FORM_WEIGHT
            season_points_average   = _blend(season_points_average,   recent_pts)
            season_rebounds_average = _blend(season_rebounds_average,
                                             _recent_avg(recent_form_games, form_key_map["rebounds"], season_rebounds_average))
            season_assists_average  = _blend(season_assists_average,
                                             _recent_avg(recent_form_games, form_key_map["assists"],  season_assists_average))
            season_threes_average   = _blend(season_threes_average,
                                             _recent_avg(recent_form_games, form_key_map["threes"],   season_threes_average))
            season_steals_average   = _blend(season_steals_average,
                                             _recent_avg(recent_form_games, form_key_map["steals"],   season_steals_average))
            season_blocks_average   = _blend(season_blocks_average,
                                             _recent_avg(recent_form_games, form_key_map["blocks"],   season_blocks_average))
            season_turnovers_average= _blend(season_turnovers_average,
                                             _recent_avg(recent_form_games, form_key_map["turnovers"],season_turnovers_average))

    # ============================================================
    # END SECTION: Recent Form Blending
    # ============================================================

    # ============================================================
    # SECTION: Calculate Adjustment Factors
    # ============================================================

    notes = []  # Game-context notes and warnings displayed in the UI

    # --- Factor 1: Opponent Defensive Rating (C9: Rolling Window blend) ---
    # Season-long defensive factor from defensive_ratings.csv
    season_defense_factor = _get_defense_adjustment_factor(
        opponent_team_abbreviation,
        player_position,
        defensive_ratings_data,
    )

    # C9: If rolling_defensive_data is provided, blend 50/50 with season avg.
    # This captures teams on hot/cold defensive streaks over their last 10 games.
    # If rolling data is unavailable, fall back to season average (unchanged behavior).
    rolling_defense_factor = _get_rolling_defense_factor(
        opponent_team_abbreviation,
        player_position,
        rolling_defensive_data,
    )
    if rolling_defense_factor is not None:
        # 50% season-long, 50% rolling (last-10 game) defensive factor
        defense_factor = 0.5 * season_defense_factor + 0.5 * rolling_defense_factor
    else:
        defense_factor = season_defense_factor  # Fall back to season average

    # --- Factor 2: Game Pace ---
    # Faster game = more possessions = more stat opportunities
    pace_factor = _get_pace_adjustment_factor(
        opponent_team_abbreviation,
        player_data.get("team", ""),
        teams_data,
    )

    # --- Factor 3: Home Court Advantage (Stat-Specific) ---
    # Home teams historically shoot better and have more energy.
    # BEGINNER NOTE: The home advantage isn't uniform across stats.
    # Points benefit most (+3%), while steals/blocks barely change (±0.5%).
    # This replaces the old fixed +2.5%/-1.5% single constant.
    if is_home_game:
        home_away_factor = 0.025   # Default +2.5% for use in single-factor calcs
    else:
        home_away_factor = -0.015  # Default -1.5% for use in single-factor calcs

    # Stat-specific home/away factors (applied individually in projection calc below)
    # Points: biggest effect (crowd energy boosts scoring).
    # Rebounds: modest effect (home rim knowledge, crowd noise).
    # Assists: moderate effect (comfortable home environment).
    # Steals/blocks: minimal effect (defensive instincts don't change with venue).
    _HOME_FACTORS = {
        "points":    0.030,   # +3.0% home
        "rebounds":  0.015,   # +1.5% home
        "assists":   0.020,   # +2.0% home
        "threes":    0.025,   # +2.5% home (shooting benefits from home crowd)
        "steals":    0.005,   # +0.5% home
        "blocks":    0.005,   # +0.5% home
        "turnovers": 0.000,   # No change (turnovers don't follow home/away pattern)
    }
    _AWAY_FACTORS = {
        "points":    -0.020,  # -2.0% away
        "rebounds":  -0.010,  # -1.0% away
        "assists":   -0.015,  # -1.5% away
        "threes":    -0.020,  # -2.0% away
        "steals":    -0.005,  # -0.5% away
        "blocks":    -0.005,  # -0.5% away
        "turnovers":  0.000,  # No change
    }

    # --- Factor 3b: Altitude Adjustment ---
    # Denver (DEN / Nuggets) plays at 5,280 feet above sea level.
    # The thinner air slightly boosts pace (+2%) as players fatigue faster
    # and the pace tends to be more chaotic. Visiting teams get a fatigue penalty.
    # BEGINNER NOTE: Altitude doesn't change players' skills, but it does
    # increase pace in games played in Denver, and visiting teams tire faster.
    _ALTITUDE_TEAMS = {"DEN"}  # Nuggets home = altitude boost
    altitude_pace_boost = 0.0
    altitude_fatigue_penalty = 0.0
    player_team_raw = player_data.get("team", "").upper().strip()

    if opponent_team_abbreviation.upper().strip() in _ALTITUDE_TEAMS and not is_home_game:
        # Visiting team playing IN Denver → slight fatigue penalty
        altitude_fatigue_penalty = -0.015   # -1.5% for visiting team at altitude
        altitude_pace_boost = 0.02          # +2% pace boost for all players
        notes.append("⛰️ Denver altitude game — visiting team fatigue penalty applied")
    elif player_team_raw in _ALTITUDE_TEAMS and is_home_game:
        # Nuggets at home in Denver → same pace boost as visiting team
        altitude_pace_boost = 0.02   # +2% pace boost (unified for BOTH teams)
    elif opponent_team_abbreviation.upper().strip() in _ALTITUDE_TEAMS and is_home_game:
        # Nuggets visiting (away game at Denver) — handled by visiting team case above
        pass

    # Apply altitude boost to pace factor
    pace_factor = pace_factor * (1.0 + altitude_pace_boost)

    # --- Factor 3c: Travel / Timezone Fatigue ---
    # Cross-timezone road trips measurably hurt performance.
    # BEGINNER NOTE: Flying east-to-west is easier than west-to-east for
    # NBA players. Teams traveling 2+ timezones get a -1.5% penalty.
    # We estimate timezone using player's home team city.
    travel_fatigue_penalty = 0.0
    if not is_home_game and game_context is not None:
        # game_context may include timezone_diff if provided
        tz_diff = game_context.get("timezone_diff", None) if isinstance(game_context, dict) else None
        if tz_diff is None:
            # Estimate from team abbreviations using simple West/East/Central mapping
            tz_diff = _estimate_timezone_diff(player_team_raw, opponent_team_abbreviation)
        if tz_diff is not None and abs(tz_diff) >= 2:
            travel_fatigue_penalty = -0.015  # -1.5% for 2+ timezone travel
            notes.append(f"✈️ Long travel ({abs(tz_diff)} timezone change) — fatigue penalty applied")

    # --- Factor 4: Rest Adjustment ---
    # Back-to-back games cause fatigue; well-rested players perform better
    rest_factor = _get_rest_adjustment_factor(rest_days)

    # Back-to-back override: if the player literally played yesterday, apply
    # an additional 5% fatigue reduction on top of the rest-day factor.
    if played_yesterday:
        rest_factor *= BACK_TO_BACK_FATIGUE_MULTIPLIER  # 5% fatigue penalty for back-to-back
        notes.append("⚠️ Back-to-back game — fatigue factor applied")

    # Apply altitude and travel fatigue to rest factor
    rest_factor = rest_factor * (1.0 + altitude_fatigue_penalty + travel_fatigue_penalty)

    # --- Factor 5: Game Total / Scoring Environment ---
    # High-total games (230+ pts projected) are fast-paced, high scoring
    # Use compute_league_average_game_total() to get a dynamic league average
    # from live team data when available, falling back to the season constant.
    league_avg_total = compute_league_average_game_total(teams_data)
    if game_total > 0 and league_avg_total > 0:
        # BEGINNER NOTE: This creates a small boost/penalty based on
        # how far the total is from average. Capped at ±8% to properly
        # reflect high/low total games (e.g., a 240-total game is ~9% above
        # the 220 average — capping at 5% was too restrictive and lost edge
        # on extreme totals).
        game_total_factor = 1.0 + ((game_total - league_avg_total) / league_avg_total) * 0.5
        game_total_factor = max(0.92, min(1.08, game_total_factor))  # Cap at ±8%
    else:
        game_total_factor = 1.0  # Neutral if no total provided or league avg unavailable

    # --- Factor 6: Blowout Risk (W6: Smart Blowout Risk) ---
    # Now uses BOTH spread AND game total, plus team tendency,
    # instead of just the defensive rating.
    player_team = player_data.get("team", "")
    blowout_risk = _estimate_blowout_risk(
        player_team,
        opponent_team_abbreviation,
        teams_data,
        vegas_spread=vegas_spread,
        game_total=game_total,
    )

    # Warn when a large spread creates meaningful reduced-minutes risk.
    if abs(vegas_spread) > BLOWOUT_SPREAD_THRESHOLD:
        notes.append(
            f"⚠️ Spread > 10 ({vegas_spread:+.1f}) — star player may face reduced minutes in blowout"
        )

    # ============================================================
    # END SECTION: Calculate Adjustment Factors
    # ============================================================

    # ============================================================
    # SECTION: Per-Minute Rate Decomposition (C1)
    # Project tonight's minutes, then derive stats as
    #   projected_stat = per_minute_rate × projected_minutes × matchup_factor × pace_factor
    # This is more physically meaningful than applying a flat multiplier
    # to season averages, and enables the C8 minutes-first simulation.
    # ============================================================

    # Project tonight's minutes
    # Base: season average minutes, adjusted by rest/back-to-back, blowout risk,
    # and spread (potential blowout → reduced minutes for starters).
    spread_minutes_factor = 1.0
    if abs(vegas_spread) > 12:
        # High spread → genuine blowout risk → starters may sit garbage time
        spread_minutes_factor = 0.94
    elif abs(vegas_spread) > 8:
        spread_minutes_factor = 0.97

    # W4: Rotation tracker — adjust minutes based on recent trend
    if _ROTATION_TRACKER_AVAILABLE and recent_form_games:
        try:
            rotation_adjustment = get_minutes_adjustment(recent_form_games)
            if rotation_adjustment != 1.0:
                minutes_adjustment_factor = minutes_adjustment_factor * rotation_adjustment
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[Projections] Unexpected error: {_exc}")

    projected_minutes = round(
        season_minutes_average
        * rest_factor                # Back-to-back reduces minutes too
        * minutes_adjustment_factor  # Teammate injury (W8): more/fewer mins
        * spread_minutes_factor,     # Blowout risk (C1)
        1
    )
    # Clamp to realistic range
    projected_minutes = max(5.0, min(44.0, projected_minutes))

    # ============================================================
    # SECTION: Apply Adjustments to Get Tonight's Projections
    # ============================================================

    # Retrieve stat-specific home/away adjustment factors
    _home_factor_map = _HOME_FACTORS if is_home_game else _AWAY_FACTORS

    # Build per-stat defense factors using stat-specific defensive columns
    # (e.g., vs_PG_reb for rebounds, vs_PG_ast for assists).
    # Falls back to 1.0 (neutral) when the specific column is not available.
    _stat_defense_factors = {
        stat: _get_stat_defense_adjustment_factor(
            opponent_team_abbreviation, player_position, stat, defensive_ratings_data
        )
        for stat in ("points", "rebounds", "assists", "threes", "steals", "blocks")
    }

    # Combine all factors into one multiplier for offensive stats
    # W8/C1: minutes_adjustment_factor boosts projections when a key
    # teammate is OUT (more usage) or applies a slight discount when
    # the player themselves is on a restriction.
    def _off_mult(stat_name):
        """Build a stat-specific offensive multiplier using the per-stat home/away factor."""
        ha = _home_factor_map.get(stat_name, home_away_factor)
        stat_def = _stat_defense_factors.get(stat_name, defense_factor)
        return (
            stat_def
            * pace_factor
            * game_total_factor
            * (1.0 + ha)
            * rest_factor
            * minutes_adjustment_factor
        )

    # Project each stat using its stat-specific multiplier
    projected_points    = season_points_average    * _off_mult("points")
    projected_rebounds  = season_rebounds_average  * _off_mult("rebounds")
    projected_assists   = season_assists_average   * _off_mult("assists")
    projected_threes    = season_threes_average    * _off_mult("threes")

    # Apply usage-rate boost from advanced_context when available.
    # This scales points/assists/threes projections proportionally to
    # actual usage rate vs the league average — players with higher usage
    # typically produce more per-minute on offensive stats.
    if advanced_context:
        projected_points  = _compute_usage_boost(advanced_context, projected_points)
        projected_assists = _compute_usage_boost(advanced_context, projected_assists)
        projected_threes  = _compute_usage_boost(advanced_context, projected_threes)

    # Defensive stats (steals/blocks) scale with pace and have minimal home/away effect
    _def_ha_steals = _home_factor_map.get("steals", home_away_factor * 0.2)
    _def_ha_blocks = _home_factor_map.get("blocks", home_away_factor * 0.2)
    projected_steals = season_steals_average * (
        pace_factor * _stat_defense_factors.get("steals", defense_factor) * rest_factor
        * (1.0 + _def_ha_steals)
        * minutes_adjustment_factor
    )
    projected_blocks = season_blocks_average * (
        pace_factor * _stat_defense_factors.get("blocks", defense_factor) * rest_factor
        * (1.0 + _def_ha_blocks)
        * minutes_adjustment_factor
    )
    projected_turnovers = season_turnovers_average * pace_factor  # Turnovers up with pace

    # Extended stats — scale with pace, rest, and minutes adjustment.
    # FTM/FTA scale with offensive pace (more possessions → more FT opportunities).
    # FGA/FGM scale similarly. Rebounds split by type. Personal fouls are roughly
    # pace-independent but scale with minutes played.
    _base_mult = pace_factor * rest_factor * minutes_adjustment_factor
    projected_ftm                = season_ftm_average                * _base_mult
    projected_fta                = season_fta_average                * _base_mult
    projected_fga                = season_fga_average                * _base_mult
    projected_fgm                = season_fgm_average                * _base_mult
    projected_offensive_rebounds = season_offensive_rebounds_average * _base_mult
    projected_defensive_rebounds = season_defensive_rebounds_average * _base_mult
    projected_personal_fouls     = season_personal_fouls_average     * (pace_factor * rest_factor * minutes_adjustment_factor)

    # Keep single offensive_stat_multiplier for backward compatibility in return dict
    offensive_stat_multiplier = _off_mult("points")

    # Round to 1 decimal place for readability.
    # Every numeric field is funnelled through _safe_float() so that
    # NaN / ±inf never escapes to the simulation or UI layer.
    projections = {
        "projected_points": _safe_float(round(projected_points, 1)),
        "projected_rebounds": _safe_float(round(projected_rebounds, 1)),
        "projected_assists": _safe_float(round(projected_assists, 1)),
        "projected_threes": _safe_float(round(projected_threes, 1)),
        "projected_steals": _safe_float(round(projected_steals, 1)),
        "projected_blocks": _safe_float(round(projected_blocks, 1)),
        "projected_turnovers": _safe_float(round(projected_turnovers, 1)),
        # Extended stat projections
        "projected_ftm":                _safe_float(round(projected_ftm,                1)),
        "projected_fta":                _safe_float(round(projected_fta,                1)),
        "projected_fga":                _safe_float(round(projected_fga,                1)),
        "projected_fgm":                _safe_float(round(projected_fgm,                1)),
        "projected_offensive_rebounds": _safe_float(round(projected_offensive_rebounds, 1)),
        "projected_defensive_rebounds": _safe_float(round(projected_defensive_rebounds, 1)),
        "projected_personal_fouls":     _safe_float(round(projected_personal_fouls,     1)),
        # C1: Projected minutes for tonight (used by C8 minutes-first sim)
        "projected_minutes": _safe_float(projected_minutes),
        # Store all factors for transparency (shown in app)
        "pace_factor": _safe_float(round(pace_factor, 4), 1.0),
        "defense_factor": _safe_float(round(defense_factor, 4), 1.0),
        "home_away_factor": _safe_float(round(home_away_factor, 4)),
        "rest_factor": _safe_float(round(rest_factor, 4), 1.0),
        "game_total_factor": _safe_float(round(game_total_factor, 4), 1.0),
        "blowout_risk": _safe_float(round(blowout_risk, 4)),
        "overall_adjustment": _safe_float(round(offensive_stat_multiplier, 4), 1.0),
        # recent_form_ratio is None when recency data is unavailable; preserve
        # that sentinel so downstream code can distinguish "no data" from "0.0".
        "recent_form_ratio": _safe_float(recent_form_ratio) if recent_form_ratio is not None else None,
        # Per-stat form ratios so downstream confidence uses the right stat
        "recent_form_ratios": recent_form_ratios,
        # W8/C4: Minutes adjustment factors for injury/restriction transparency
        "minutes_adjustment_factor": _safe_float(round(minutes_adjustment_factor, 4), 1.0),
        "teammate_out_notes": teammate_out_notes or [],
        "notes": notes,
        # C6: Bayesian shrinkage metadata
        "bayesian_shrinkage_applied": bayesian_shrinkage_applied,
        "games_played": games_played,
    }

    return projections

    # ============================================================
    # END SECTION: Apply Adjustments to Get Tonight's Projections
    # ============================================================


# ============================================================
# SECTION: Individual Adjustment Factor Functions
# ============================================================

def _get_defense_adjustment_factor(
    opponent_team_abbreviation,
    player_position,
    defensive_ratings_data,
):
    """
    Look up how well the opponent defends this player's position.

    A factor of 1.1 means the opponent allows 10% more points
    to this position (weak defense = good for the player).
    A factor of 0.9 means the opponent is 10% tougher than average.

    Args:
        opponent_team_abbreviation (str): 3-letter team code
        player_position (str): PG, SG, SF, PF, or C
        defensive_ratings_data (list of dict): Defensive rating rows

    Returns:
        float: Adjustment multiplier (typically 0.88 to 1.12)
    """
    # Find the opponent's row in defensive ratings data
    if not defensive_ratings_data:
        logging.getLogger(__name__).warning(
            "_get_defense_adjustment_factor: defensive_ratings_data is empty — "
            "returning neutral 1.0 for %s vs %s",
            opponent_team_abbreviation, player_position,
        )
        return 1.0
    for team_row in defensive_ratings_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            # Build the column name: "vs_PG_pts", "vs_C_pts", etc.
            column_name = f"vs_{player_position}_pts"
            factor_value = team_row.get(column_name, "1.0")
            return float(factor_value)

    # If opponent not found, return 1.0 (neutral)
    return 1.0


def _get_stat_defense_adjustment_factor(
    opponent_team_abbreviation,
    player_position,
    stat_type,
    defensive_ratings_data,
):
    """
    Look up how well the opponent defends this player's position for a SPECIFIC stat.

    Uses per-stat defensive columns (e.g., vs_PG_reb for a PG's rebounds,
    vs_PG_ast for assists) rather than the single vs_{pos}_pts column used by
    _get_defense_adjustment_factor.  Falls back to 1.0 (neutral) — NOT the
    points multiplier — when the stat-specific column is absent.

    Args:
        opponent_team_abbreviation (str): 3-letter team code
        player_position (str): PG, SG, SF, PF, or C
        stat_type (str): Stat name — 'points', 'rebounds', 'assists', 'threes',
                         'steals', or 'blocks'
        defensive_ratings_data (list of dict): Defensive rating rows

    Returns:
        float: Adjustment multiplier (1.0 = neutral)
    """
    # Map internal stat names to defensive CSV column suffixes
    _STAT_COL_MAP = {
        "points":   "pts",
        "rebounds": "reb",
        "assists":  "ast",
        "steals":   "stl",
        "blocks":   "blk",
    }
    # Note: 'threes' has no per-stat defensive column in the CSV, so it falls
    # through to the 1.0 neutral return below (no cross-contamination with pts).

    col_suffix = _STAT_COL_MAP.get(stat_type)
    if col_suffix is None:
        return 1.0  # Unknown stat — neutral

    column_name = f"vs_{player_position}_{col_suffix}"

    for team_row in defensive_ratings_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            raw = team_row.get(column_name)
            if raw is None:
                # Stat-specific column not present → neutral (do NOT use pts column)
                return 1.0
            try:
                return float(raw)
            except (TypeError, ValueError):
                return 1.0

    # Opponent not found → neutral
    return 1.0


def _get_rolling_defense_factor(
    opponent_team_abbreviation,
    player_position,
    rolling_defensive_data,
):
    """
    Look up the rolling 10-game defensive factor for an opponent. (C9)

    This captures teams on hot/cold defensive streaks that the season-long
    rating doesn't reflect. For example, if a team has been defending PGs
    much better over the last 10 games, this factor will be < 1.0.

    Falls back gracefully (returns None) when:
    - rolling_defensive_data is None (caller will use season average)
    - The opponent is not found in the rolling data
    - The position is not in the rolling data

    Args:
        opponent_team_abbreviation (str): 3-letter team code
        player_position (str): PG, SG, SF, PF, or C
        rolling_defensive_data (dict or None): Rolling data dict.
            Format: {team_abbrev: {position_key: factor}}
            Supported position key formats:
              - Simple: {"BOS": {"PG": 0.88, "SG": 0.92}}
              - CSV-style: {"BOS": {"vs_PG_pts": 0.88, "vs_SG_pts": 0.92}}
            Both formats are handled transparently.
            When None, always returns None.

    Returns:
        float or None: Rolling defensive factor, or None if unavailable.
    """
    if not rolling_defensive_data:
        return None

    team_rolling = rolling_defensive_data.get(opponent_team_abbreviation)
    if not team_rolling:
        return None

    # Support both direct position key and full column key
    factor = team_rolling.get(player_position)
    if factor is None:
        factor = team_rolling.get(f"vs_{player_position}_pts")
    if factor is None:
        return None

    try:
        return float(factor)
    except (TypeError, ValueError):
        return None


def _get_pace_adjustment_factor(
    opponent_team_abbreviation,
    player_team_abbreviation,
    teams_data,
):
    """
    Calculate the pace adjustment for tonight's game.

    Game pace = average of both teams' pace ratings.
    League average pace ≈ 98.5 possessions per game.
    Faster pace = more stat opportunities.

    Args:
        opponent_team_abbreviation (str): Opponent 3-letter code
        player_team_abbreviation (str): Player's team 3-letter code
        teams_data (list of dict): Team data rows from teams.csv

    Returns:
        float: Pace multiplier (typically 0.93 to 1.07)
    """
    league_average_pace = LEAGUE_AVERAGE_PACE  # From module-level constant

    if not teams_data:
        logging.getLogger(__name__).warning(
            "_get_pace_adjustment_factor: teams_data is empty — "
            "returning neutral 1.0 for %s vs %s",
            player_team_abbreviation, opponent_team_abbreviation,
        )
        return 1.0

    player_team_pace = league_average_pace   # Default if not found
    opponent_team_pace = league_average_pace  # Default if not found

    # Find each team's pace rating
    for team_row in teams_data:
        abbreviation = team_row.get("abbreviation", "")
        if abbreviation == player_team_abbreviation:
            player_team_pace = float(team_row.get("pace", league_average_pace))
        if abbreviation == opponent_team_abbreviation:
            opponent_team_pace = float(team_row.get("pace", league_average_pace))

    # Tonight's expected pace = average of both teams
    expected_game_pace = (player_team_pace + opponent_team_pace) / 2.0

    # Convert to a multiplier relative to league average
    pace_factor = expected_game_pace / league_average_pace

    return pace_factor


def _get_rest_adjustment_factor(rest_days):
    """
    Calculate performance adjustment based on rest.

    Back-to-back games (0 rest days) cause fatigue and reduce
    performance. More rest generally helps, up to a point.

    Args:
        rest_days (int): Days of rest (0 = back-to-back, 3+ = well rested)

    Returns:
        float: Multiplier (0.92 for back-to-back, up to 1.02 well rested)
    """
    # BEGINNER NOTE: This dictionary maps rest days to performance multipliers
    rest_to_factor_map = {
        0: 0.92,   # Back-to-back: significant fatigue
        1: 0.97,   # One day rest: minor fatigue
        2: 1.00,   # Two days rest: normal performance
        3: 1.01,   # Three days: slightly better than average
        4: 1.02,   # Four or more: well rested
    }

    # Get factor for the given rest days (cap at 4 since 5 = 4 essentially)
    capped_rest_days = min(rest_days, 4)
    return rest_to_factor_map.get(capped_rest_days, 1.00)


def _estimate_blowout_risk(
    player_team_abbreviation,
    opponent_team_abbreviation,
    teams_data,
    vegas_spread=0.0,
    game_total=0.0,
):
    """
    Estimate the probability tonight's game becomes a blowout. (W6)

    Now uses a three-factor formula that combines:
    1. Vegas spread — the primary blowout predictor
    2. Game total — high spread + low total = slow blowout (maximum risk)
    3. Team blowout tendency — some coaches pull stars early, others don't

    Formula:
        blowout_risk = base_risk × spread_factor × total_factor × team_tendency

    Args:
        player_team_abbreviation (str): Player's team 3-letter code
        opponent_team_abbreviation (str): Opponent 3-letter code
        teams_data (list of dict): Team data rows
        vegas_spread (float): Today's point spread (positive = player's team favored)
        game_total (float): Vegas over/under total for tonight's game

    Returns:
        float: Blowout risk probability (0.05 to 0.45)
    """
    # ---- Base blowout risk from defensive ratings (legacy fallback) ----
    # Find the opponent's defensive rating for spread-independent baseline
    if not teams_data:
        logging.getLogger(__name__).warning(
            "_estimate_blowout_risk: teams_data is empty — "
            "returning base risk 0.15 for %s vs %s",
            player_team_abbreviation, opponent_team_abbreviation,
        )
        return 0.15
    opponent_drtg = 115.0  # League average if not found
    for team_row in teams_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            opponent_drtg = float(team_row.get("drtg", 115.0))
            break

    base_blowout_risk = 0.15  # 15% base in any NBA game

    # ---- Factor 1: Spread Factor ----
    # Larger spread → higher blowout probability
    # Use abs() to treat both favorite and underdog scenarios equally
    # (a 14-point favorite or 14-point underdog both imply a lopsided game)
    abs_spread = abs(vegas_spread) if vegas_spread != 0.0 else abs(
        (opponent_drtg - 115.0) * 0.8  # Estimate from drtg if no spread
    )
    if abs_spread <= 3.0:
        # Close game — very low blowout risk
        spread_factor = 0.6
    elif abs_spread <= 7.0:
        # Moderate favorite/underdog
        spread_factor = 0.85
    elif abs_spread <= 12.0:
        # Clear favorite — moderate blowout risk
        spread_factor = 1.2
    elif abs_spread <= 18.0:
        # Heavy favorite — high blowout risk
        spread_factor = 1.6
    else:
        # Massive favorite — very high blowout risk
        spread_factor = 2.0

    # ---- Factor 2: Game Total Factor (W6: high spread + low total = max blowout risk) ----
    # High spread + low total = one team wins a slow, controlled game = worst case
    # High spread + high total = fast game but still one-sided = moderate risk
    if game_total <= 0:
        total_factor = 1.0  # No data — neutral
    elif game_total < 210:
        total_factor = 1.25  # Very low total = defensive slog = blowout stays close
    elif game_total < 218:
        total_factor = 1.10  # Below-average pace = slightly higher blowout risk
    elif game_total <= 226:
        total_factor = 1.00  # Average game total — neutral
    elif game_total <= 232:
        total_factor = 0.88  # High-scoring game — blowouts less frequent
    else:
        total_factor = 0.78  # Very high total — run-and-gun, close games common

    # ---- Factor 3: Team Blowout Tendency ----
    # Some coaches pull starters early (low tendency = lower risk for the PLAYER
    # because coach pulls them sooner = less stats, but that's already captured
    # in the minutes model). Here we track the OPPONENT's tendency to collapse.
    # Use the PLAYER's team tendency (affects whether the player gets full mins).
    team_tendency = TEAM_BLOWOUT_TENDENCY.get(player_team_abbreviation, 1.0)

    # ---- Combine ----
    blowout_risk = base_blowout_risk * spread_factor * total_factor * team_tendency

    # Cap between 5% and 45%
    return max(0.05, min(0.45, blowout_risk))


# ============================================================
# SECTION: Timezone Estimation Helper
# ============================================================

# Approximate timezone offset from Eastern Time for each NBA team.
# Positive = ahead of Eastern (or further west), Negative = behind Eastern.
# These are used to estimate cross-timezone travel fatigue.
_TEAM_TIMEZONE_OFFSETS = {
    # Eastern Time (UTC-5 / UTC-4 DST) → offset 0
    "ATL": 0, "BOS": 0, "BKN": 0, "CHA": 0, "CHI": -1,  # CHI = Central = -1
    "CLE": 0, "DET": 0, "IND": 0, "MIA": 0, "MIL": -1,
    "NYK": 0, "ORL": 0, "PHI": 0, "TOR": 0, "WAS": 0,
    # Central Time (UTC-6 / UTC-5 DST) → offset -1 from Eastern
    "DAL": -1, "HOU": -1, "MEM": -1, "MIN": -1, "NOP": -1, "SAS": -1,
    # Mountain Time (UTC-7 / UTC-6 DST) → offset -2 from Eastern
    "DEN": -2, "OKC": -1, "UTA": -2,
    # Pacific Time (UTC-8 / UTC-7 DST) → offset -3 from Eastern
    "GSW": -3, "LAC": -3, "LAL": -3, "PHX": -2, "POR": -3, "SAC": -3, "SEA": -3,
}


def _estimate_timezone_diff(player_team, opponent_team):
    """
    Estimate the timezone difference when a team travels for an away game.

    BEGINNER NOTE: When a West Coast team plays at an East Coast venue,
    they may have traveled 3 timezones which can cause fatigue and
    affect sleep schedules. The direction matters too: traveling east
    (earlier wake up) tends to hurt more than traveling west.

    Args:
        player_team (str): Player's home team abbreviation (e.g. 'GSW')
        opponent_team (str): Opponent's abbreviation (where the game is played)

    Returns:
        int or None: Timezone difference in hours (positive = going east),
            None if either team is not found in the mapping.

    Example:
        _estimate_timezone_diff('GSW', 'BOS') → 3 (Pacific → Eastern: +3 hours east)
        _estimate_timezone_diff('BOS', 'LAL') → -3 (Eastern → Pacific: -3 hours west)
    """
    p_tz = _TEAM_TIMEZONE_OFFSETS.get(player_team.upper().strip())
    o_tz = _TEAM_TIMEZONE_OFFSETS.get(opponent_team.upper().strip())

    if p_tz is None or o_tz is None:
        return None

    # Positive = traveling east (earlier wake up = harder)
    # Negative = traveling west (later schedule = easier)
    return o_tz - p_tz


# ============================================================
# END SECTION: Timezone Estimation Helper
# ============================================================


_COMBO_STAT_COMPONENTS: dict = {
    "points_rebounds": ("points", "rebounds"),
    "points_assists": ("points", "assists"),
    "rebounds_assists": ("rebounds", "assists"),
    "points_rebounds_assists": ("points", "rebounds", "assists"),
    "blocks_steals": ("blocks", "steals"),
}


def get_stat_standard_deviation(player_data, stat_type):
    """
    Get the pre-stored standard deviation for a stat type.

    The CSV includes std values for main stats. For others,
    we estimate based on the average (coefficient of variation).
    CV estimates are now DYNAMIC based on the player's tier (W10):
    - Stars (high avg) have LOWER CV — they always get their shots
    - Role players have HIGHER CV — usage is more situational
    - Threes always get at least 0.55 CV (most streaky stat)

    For combo stats (points_rebounds, points_assists, etc.) the std is
    computed as the quadrature sum of component stds so that
    std_devs_from_line reflects a meaningful number instead of inflating
    to nonsensical values caused by the minimum 0.5 fallback.

    Args:
        player_data (dict): Player row from CSV
        stat_type (str): 'points', 'rebounds', 'assists', etc.

    Returns:
        float: Standard deviation for this stat
    """
    # Combo stats: compute as quadrature sum of component stds
    if stat_type in _COMBO_STAT_COMPONENTS:
        import math
        components = _COMBO_STAT_COMPONENTS[stat_type]
        sum_sq = sum(
            get_stat_standard_deviation(player_data, c) ** 2
            for c in components
        )
        return max(0.5, math.sqrt(sum_sq))

    # Try to get the stored std from the CSV first
    std_column = f"{stat_type}_std"
    stored_std = player_data.get(std_column, None)

    if stored_std is not None and stored_std != "":
        _std_val = float(stored_std)
        if _std_val > 0:
            return _std_val

    # BEGINNER NOTE: If we don't have a stored std, estimate it
    # using the "coefficient of variation" — most basketball stats
    # have about 30-50% variability relative to their average
    average_column = f"{stat_type}_avg"
    stored_avg = float(player_data.get(average_column, 0))

    # W10: Dynamic CV based on player tier and stat type
    # Stars (25+ PPG) are more consistent; role players are more volatile
    cv = _get_dynamic_cv(stat_type, stored_avg)

    estimated_std = stored_avg * cv

    # Minimum std of 0.5 to avoid divide-by-zero issues
    return max(0.5, estimated_std)


def _get_dynamic_cv(stat_type, stat_avg):
    """
    Get a dynamic coefficient of variation based on player tier and stat type. (W10)

    High-usage stars have LOWER CV% because they always get their shots
    and their production floor is higher. Low-usage role players have
    HIGHER CV% because their production is more situational.
    Three-point shooting is inherently streaky — always use at least 0.55 CV.

    Args:
        stat_type (str): 'points', 'rebounds', 'assists', 'threes', etc.
        stat_avg (float): The player's average for this stat

    Returns:
        float: Coefficient of variation (0.0-1.0)

    Example:
        'points', avg=28.0 → 0.25 (star, very consistent)
        'points', avg=5.0  → 0.50 (deep bench, very unpredictable)
        'threes', avg=2.5  → 0.60 (minimum 0.55 always applied)
    """
    if stat_type == "points":
        # Stars get guaranteed shots → lower variability
        if stat_avg >= 25.0:
            cv = 0.25   # Elite scorer — very consistent
        elif stat_avg >= 15.0:
            cv = 0.30   # Regular starter
        elif stat_avg >= 8.0:
            cv = 0.40   # Role player — situational production
        else:
            cv = 0.50   # Deep bench — very unpredictable

    elif stat_type == "rebounds":
        if stat_avg >= 10.0:
            cv = 0.28   # Elite rebounder — positional, very consistent
        elif stat_avg >= 6.0:
            cv = 0.35
        elif stat_avg >= 3.0:
            cv = 0.42
        else:
            cv = 0.50

    elif stat_type == "assists":
        if stat_avg >= 8.0:
            cv = 0.32   # Primary playmaker — fairly consistent
        elif stat_avg >= 4.0:
            cv = 0.40
        else:
            cv = 0.50

    elif stat_type == "threes":
        # Three-point shooting is inherently streaky — always minimum 0.55
        # A 3-point specialist has slightly lower CV than a non-shooter
        if stat_avg >= 3.0:
            cv = 0.58   # Volume shooter — streaky but consistent volume
        elif stat_avg >= 1.5:
            cv = 0.65
        else:
            cv = 0.75   # Non-shooter attempting threes — very unpredictable
        # Minimum 0.55 for all three-point props
        cv = max(cv, 0.55)

    elif stat_type == "steals":
        cv = 0.60  # Steals are always high variance

    elif stat_type == "blocks":
        cv = 0.65  # Blocks are always high variance

    elif stat_type == "turnovers":
        if stat_avg >= 3.0:
            cv = 0.42   # High-usage players have somewhat predictable turnovers
        else:
            cv = 0.50

    elif stat_type in ("ftm", "fta"):
        cv = 0.50 if stat_avg < 3.0 else 0.40

    elif stat_type in ("fga", "fgm"):
        cv = 0.35 if stat_avg >= 10.0 else 0.45

    elif stat_type == "minutes":
        cv = 0.20  # Minutes are relatively stable game-to-game

    elif stat_type == "personal_fouls":
        cv = 0.55  # High variance

    elif stat_type in ("offensive_rebounds", "defensive_rebounds"):
        cv = 0.50 if stat_avg < 2.0 else 0.42

    else:
        cv = 0.40  # Default for unknown stat types

    return cv

# ============================================================
# END SECTION: Individual Adjustment Factor Functions
# ============================================================


# ============================================================
# SECTION: Teammate-Out Usage Adjustment (C4)
# When a high-usage teammate is OUT, boost the current player's
# projection by a configurable usage bump factor.
# ============================================================

def calculate_teammate_out_boost(
    player_data,
    injury_status_map,
    teammates_data=None,
):
    """
    Calculate a usage-boost multiplier for when key teammates are OUT. (C4)

    Checks the injury status map for teammates on the same team.
    If a high-usage teammate is OUT (top 3 scorer/assist leader),
    boosts the current player's projection.

    Args:
        player_data (dict): Current player's data row.
        injury_status_map (dict): {player_name_lower: {status, ...}}
            Typically from RosterEngine.get_injury_report() or session state.
        teammates_data (list of dict, optional): Rows of all players on the
            same team from players CSV. When None, no teammate analysis is done.

    Returns:
        tuple: (boost_multiplier: float, notes: list of str)
            boost_multiplier: 1.0 (no boost) to 1.15 (max +15%)
            notes: Human-readable explanations of any boosts applied
    """
    if not teammates_data or not injury_status_map:
        return 1.0, []

    player_name = player_data.get("name", "").lower()
    player_team = player_data.get("team", "").upper()

    # Find teammates on the same team
    team_players = [
        p for p in (teammates_data or [])
        if p.get("team", "").upper() == player_team
        and p.get("name", "").lower() != player_name
    ]

    if not team_players:
        return 1.0, []

    # Sort teammates by points average (primary usage metric)
    team_players_sorted = sorted(
        team_players,
        key=lambda p: float(p.get("points_avg", 0) or 0),
        reverse=True,
    )

    # Check top 3 scorers / assist leaders for OUT status
    top_options = team_players_sorted[:3]
    total_boost = 0.0
    notes = []

    for rank, teammate in enumerate(top_options):
        t_name = teammate.get("name", "")
        t_name_lower = t_name.lower()
        t_status_entry = injury_status_map.get(t_name_lower, {})
        t_status = t_status_entry.get("status", "Active")

        if t_status in ("Out", "Injured Reserve", "IR", "Inactive"):
            if rank == 0:
                bump = TEAMMATE_OUT_PRIMARY_BUMP    # +8%
                tier_label = "primary option"
            else:
                bump = TEAMMATE_OUT_SECONDARY_BUMP  # +5%
                tier_label = "secondary option"

            total_boost = min(total_boost + bump, TEAMMATE_OUT_MAX_BOOST)
            notes.append(
                f"📈 {t_name} ({tier_label}, {t_status}) OUT → "
                f"+{bump*100:.0f}% usage boost"
            )

    boost_multiplier = 1.0 + total_boost
    return round(boost_multiplier, 4), notes

# ============================================================
# END SECTION: Teammate-Out Usage Adjustment
# ============================================================


# ============================================================
# SECTION: Injury / Status Adjustment
# ============================================================

def apply_injury_status_adjustment(projection_dict, player_status, games_missed=0):
    """
    Apply injury/status impact factors to a player projection.

    Reduces projected stats based on the player's availability status
    and, if they missed several games, applies a rust-factor penalty
    for the first game back.

    Args:
        projection_dict (dict): Return value of build_player_projection().
            Modified in-place (via a shallow copy) and returned.
        player_status (str): Player availability label, e.g.:
            'Active', 'Questionable', 'Doubtful', 'Out', 'Injured Reserve'
        games_missed (int, optional): Consecutive games missed before
            tonight. If > 3, a 6% rust-factor reduction is applied.
            Default 0 (no games missed).

    Returns:
        dict or None:
            - None if player_status is 'Out' or 'Injured Reserve'
            - Adjusted projection_dict otherwise (shallow copy, not mutated)

    Examples:
        apply_injury_status_adjustment(proj, "Questionable")   → -8%
        apply_injury_status_adjustment(proj, "Doubtful")        → -25%
        apply_injury_status_adjustment(proj, "Out")             → None
        apply_injury_status_adjustment(proj, "Active", 4)       → -6% rust
        apply_injury_status_adjustment(proj, "Questionable", 5) → -8% + -6%
    """
    if player_status in ("Out", "Injured Reserve"):
        return None

    if projection_dict is None:
        return None

    # Work on a shallow copy so the original is not mutated
    adjusted = dict(projection_dict)
    notes = list(adjusted.get("notes", []))

    # Stat keys that represent player output (not factors/metadata)
    _STAT_KEYS = [
        "projected_points",
        "projected_rebounds",
        "projected_assists",
        "projected_threes",
        "projected_steals",
        "projected_blocks",
        "projected_turnovers",
    ]

    # Determine status-based reduction factor
    reduction = 1.0
    if player_status == "Questionable":
        reduction *= QUESTIONABLE_REDUCTION  # 8% reduction
        notes.append("⚠️ Questionable status — projected stats reduced 8%")
    elif player_status == "Doubtful":
        reduction *= DOUBTFUL_REDUCTION  # 25% reduction
        notes.append("⚠️ Doubtful status — projected stats reduced 25%")

    # Rust factor: reduction for first game back after missing 3+ games
    if games_missed > RUST_FACTOR_GAMES_THRESHOLD:
        reduction *= RUST_FACTOR_REDUCTION
        notes.append(
            f"⚠️ Rust factor — {games_missed} games missed, first game back (−6%)"
        )

    # Apply reduction to all output stats
    for key in _STAT_KEYS:
        if key in adjusted:
            adjusted[key] = round(adjusted[key] * reduction, 1)

    adjusted["notes"] = notes
    return adjusted

# ============================================================
# END SECTION: Injury / Status Adjustment
# ============================================================
