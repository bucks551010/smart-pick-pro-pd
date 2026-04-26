# ============================================================
# FILE: config/thresholds.py
# PURPOSE: Centralized named constants for all thresholds used
#          in tier classification, edge detection, and confidence scoring.
#
# Usage:
#   from config.thresholds import PLATINUM_THRESHOLD, GOLD_THRESHOLD, ...
# ============================================================

# ── Confidence tier thresholds (0–100 SAFE Score) ────────────────────────────
PLATINUM_THRESHOLD = 84   # Near-perfect conditions
GOLD_THRESHOLD     = 65   # Very strong, clear edge
SILVER_THRESHOLD   = 57   # Solid evidence above average
BRONZE_THRESHOLD   = 35   # Minimum viable confidence (below = Do Not Bet)

DO_NOT_BET_THRESHOLD = 35  # Alias for BRONZE_THRESHOLD floor

# ── Minimum edge % required per tier ──────────────────────────────────────────
# NOTE: These must match the values in engine/confidence.py.
PLATINUM_MIN_EDGE_PCT = 8.0   # (lowered from 10% per engine tuning)
GOLD_MIN_EDGE_PCT     = 5.0   # (lowered from 7% per engine tuning)
SILVER_MIN_EDGE_PCT   = 3.0
BRONZE_MIN_EDGE_PCT   = 1.0

# ── Minimum win probability per tier ─────────────────────────────────────────
PLATINUM_MIN_PROBABILITY = 0.62
GOLD_MIN_PROBABILITY     = 0.57

# ── Risk-flag thresholds (Uncertain detection) ──────────────────────────────
UNCERTAIN_CONFLICT_RATIO_THRESHOLD = 0.80   # Forces within 20% = conflicting
UNCERTAIN_HIGH_VAR_MAX_EDGE        = 8.0    # High-variance stats with edge <8%
UNCERTAIN_BLOWOUT_SPREAD_THRESHOLD = 10.0   # Spread >10 pts on back-to-back
UNCERTAIN_HOT_STREAK_RATIO         = 1.25   # Line ≥125% of season avg

# ── Auto-log thresholds (per tier) ───────────────────────────────────────────
# Minimum edge % required for a pick to be auto-logged to the Bet Tracker.
# Higher tiers already encode high confidence so they need less raw edge.
# Confidence gates are all 0 — the tier classification itself is the gate.
PLATINUM_AUTO_LOG_MIN_EDGE       = 1.0   # Near-certain: low edge still worthwhile
GOLD_AUTO_LOG_MIN_EDGE           = 2.0   # Strong signal: 2% floor
SILVER_AUTO_LOG_MIN_EDGE         = 3.0   # Solid edge floor
BRONZE_AUTO_LOG_MIN_EDGE         = 3.0   # Same floor as Silver
PLATINUM_AUTO_LOG_MIN_CONFIDENCE = 0.0   # Tier encodes confidence — no extra gate
GOLD_AUTO_LOG_MIN_CONFIDENCE     = 0.0
SILVER_AUTO_LOG_MIN_CONFIDENCE   = 0.0
BRONZE_AUTO_LOG_MIN_CONFIDENCE   = 0.0

# ── Simulation defaults ───────────────────────────────────────────────────────
DEFAULT_NUM_SIMULATIONS = 2000
CONVERGENCE_THRESHOLD   = 0.001
CONVERGENCE_CHECK_INTERVAL = 200

# ── Sensitivity analysis defaults ────────────────────────────────────────────
SENSITIVITY_BLOWOUT_DELTA = 0.10   # ±10% blowout risk
SENSITIVITY_PACE_DELTA    = 0.05   # ±5% pace adjustment
SENSITIVITY_MATCHUP_DELTA = 0.05   # ±5% matchup adjustment
