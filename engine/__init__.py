# ============================================================
# FILE: engine/__init__.py
# PURPOSE: Shared constants for the SmartBetPro NBA engine.
#          Import these in any module that needs them.
# ============================================================

# Simple (single-stat) stat types.
SIMPLE_STAT_TYPES = frozenset({
    "points",
    "rebounds",
    "assists",
    "threes",
    "steals",
    "blocks",
    "turnovers",
    # Extended NBA stat types from mirror
    "ftm",
    "fga",
    "fgm",
    "fta",
    "minutes",
    "personal_fouls",
    "offensive_rebounds",
    "defensive_rebounds",
})

# Combo stat types (sum of 2+ simple stats).
COMBO_STAT_TYPES = frozenset({
    "points_rebounds",
    "points_assists",
    "rebounds_assists",
    "points_rebounds_assists",
    "blocks_steals",
})

# Fantasy score stat types (weighted sum using platform formula).
FANTASY_STAT_TYPES = frozenset({
    "fantasy_score_pp",   # Fantasy scoring (legacy)
    "fantasy_score_dk",   # DraftKings fantasy scoring
    "fantasy_score_ud",   # Fantasy scoring (legacy)
})

# Yes/No prop types.
YESNO_STAT_TYPES = frozenset({
    "double_double",
    "triple_double",
})

# Novelty / specialty stat types offered by PrizePicks and Underdog.
NOVELTY_STAT_TYPES = frozenset({
    # Shooting attempts
    "threes_attempted",       # 3-PT Attempted
    "two_pointers_made",      # Two Pointers Made
    "two_pointers_attempted", # Two Pointers Attempted
    # Segment/partial-game props (PP "- 1st 3 Minutes")
    "points_first_3min",
    "rebounds_first_3min",
    "assists_first_3min",
    # Quarter-based milestone props
    "quarters_3plus_points",  # Quarters with 3+ Points
    "quarters_5plus_points",  # Quarters with 5+ Points
    # Novelty plays
    "dunks",
    # Team/game props
    "margin_of_victory",
    # First-quarter props (Underdog)
    "1q_points",
    "1q_rebounds",
    # Underdog 3-point attempts
    "threes_attempted_ud",
})

# All supported stat types across the app.
# This is the single source of truth — don't define this elsewhere.
VALID_STAT_TYPES = SIMPLE_STAT_TYPES | COMBO_STAT_TYPES | FANTASY_STAT_TYPES | YESNO_STAT_TYPES | NOVELTY_STAT_TYPES

# Stat types that should NEVER appear in output — previously used to block dunks,
# but novelty stats are now preserved for Prop Scanner display.
BLOCKED_STAT_TYPES = frozenset()

# Substrings that indicate a period-specific prop (1st half, 2nd half,
# 1st quarter, etc.).  Any stat_type containing one of these tokens is
# blocked at all display and analysis layers.
_PERIOD_TOKENS = (
    "1st", "2nd", "3rd", "4th",
    "first", "second", "third", "fourth",
    "half", "quarter", "period",
    "1h", "2h", "1q", "2q", "3q", "4q",
    "overtime", "ot",
)

# Threshold for heuristic demon/goblin detection (% above/below season avg)
_DEMON_GOBLIN_LINE_THRESHOLD = 60.0


def is_unbettable_line(result: dict) -> bool:
    """Return True if a pick is an unbettable demon/goblin alternate line,
    a blocked stat type (e.g. dunks), or a period-specific prop.

    Checks:
    1. ``stat_type`` — blocked types like dunks, or period-specific tokens.
    2. ``odds_type`` field — if explicitly tagged as demon or goblin.
    3. Heuristic — if the line deviates > 60 % from season avg in the
       direction that makes the pick trivially obvious.
    """
    stat = str(result.get("stat_type", "")).lower().strip()

    # Block explicitly banned stat types
    if stat in BLOCKED_STAT_TYPES:
        return True

    # Novelty stat types are always allowed through — never period-block them
    if stat in NOVELTY_STAT_TYPES:
        return False

    # Block period-specific props (1st half, 2nd quarter, etc.)
    if any(tok in stat for tok in _PERIOD_TOKENS):
        return True

    # Block stat types not in the valid set (unknown / unverifiable)
    if stat and stat not in VALID_STAT_TYPES:
        return True

    ot = str(result.get("odds_type", "standard")).lower()
    if ot not in ("standard", ""):
        return True

    direction = str(result.get("direction", "")).upper()

    # Compute line_vs_avg from available data
    line_vs_avg = result.get("line_vs_avg_pct", 0) or 0
    if not line_vs_avg:
        line = float(result.get("line", 0) or 0)
        avg_key = f"season_{stat}_avg"
        season_avg = float(result.get(avg_key, 0) or 0)
        if not season_avg:
            season_avg = float(result.get(f"{stat}_avg", 0) or 0)
        if season_avg > 0 and line > 0:
            line_vs_avg = (line - season_avg) / season_avg * 100.0

    if line_vs_avg > _DEMON_GOBLIN_LINE_THRESHOLD and direction == "UNDER":
        return True
    if line_vs_avg < -_DEMON_GOBLIN_LINE_THRESHOLD and direction == "OVER":
        return True

    return False

# ============================================================
# SECTION: New High-Impact Feature Modules (v8)
# These modules are imported directly by pages; they are not
# re-exported from __init__.py to keep the namespace clean.
# Available modules:
#   engine.matchup_history       — Feature 2: Player-vs-team history
#   engine.platform_line_compare — Feature 3: Cross-platform line comparison
#   engine.bankroll              — Feature 5: Kelly Criterion sizing
#   engine.minutes_model         — Feature 6: Dedicated minutes projection
#   engine.game_script           — Feature 7: Quarter-by-quarter simulation
#   engine.market_movement       — Feature 9: Sharp money line movement
# ============================================================

# ============================================================
# SECTION: v9 Enhanced Engine Public API
# New public functions added by the comprehensive engine enhancement.
# These can be imported from engine.* modules directly or via these
# convenience re-exports.
# ============================================================

# simulation.py — Quantum Matrix Engine 6.0
from engine.simulation import (
    run_enhanced_simulation,          # QME + game-script blended simulation (1F)
)

# edge_detection.py — Advanced Edge Analysis
from engine.edge_detection import (
    estimate_closing_line_value,      # CLV estimation (2B)
    calculate_dynamic_vig,            # Dynamic vig by platform (2C)
)

# confidence.py — Precision Confidence Scoring
from engine.confidence import (
    calculate_risk_score,             # Composite 1-10 risk rating (3E)
    enforce_tier_distribution,        # Tier distribution guardrails (3F)
)

# correlation.py — Advanced Correlation Engine
from engine.correlation import (
    get_position_correlation_adjustment,  # Position-based correlation priors (4B)
    get_correlation_confidence,           # Parlay correlation confidence (4E)
    correlation_adjusted_kelly,           # Correlation-adjusted Kelly sizing (4F)
)
