"""
engine/parlay_suggester.py
==========================
Auto-suggest parlay combinations from today's qualified picks.

Per the Phase-3 design decision, parlays are ranked by **SAFE score**
(a correlation-adjusted blend of independent probability and expected
value).  The user no longer has to hand-pick legs — the suggester
returns the top-K parlays of `n_legs` size, sorted by SAFE score
descending.

Public API
----------
    suggest_parlays(picks, n_legs=3, top_k=3, ...) -> list[dict]
        Each result dict contains:
            • legs: list[pick]
            • independent_prob: float
            • correlation_adjusted_prob: float
            • avg_edge_pct: float
            • avg_confidence: float
            • avg_correlation: float    (mean off-diagonal corr)
            • safe_score: float
            • payout_multiplier: float  (PrizePicks/Underdog default)

The implementation reuses the existing `engine/correlation.py`
infrastructure so results are consistent with the rest of the app
(Bet Slip Builder, Joseph engine, etc.).
"""

from __future__ import annotations

import itertools
import logging
import math
from typing import Any, Iterable

from engine.correlation import (
    build_correlation_matrix,
    adjust_parlay_probability,
)

_logger = logging.getLogger(__name__)

# Default PrizePicks/Underdog Power-Play payouts (2-leg through 6-leg).
_DEFAULT_PAYOUTS: dict[int, float] = {
    2: 3.0,
    3: 5.0,
    4: 10.0,
    5: 20.0,
    6: 35.0,
}

# Hard cap on legs we'll combinatorially explore — keeps the suggester
# fast even on big slates.
_MAX_LEGS = 6
# Cap on how many top picks feed into the combinatorial step.  100 picks
# at 3 legs = ~161 700 combos which we score quickly; bigger n_legs needs
# a smaller pool.
_POOL_SIZE_BY_LEGS: dict[int, int] = {2: 60, 3: 40, 4: 25, 5: 18, 6: 14}


def _qualifying_pool(picks: list[dict[str, Any]], pool_size: int) -> list[dict[str, Any]]:
    """Pre-filter and rank picks before combinatorial scoring.

    Filters:
      • exclude `player_is_out`
      • require positive edge_percentage
      • require confidence_score >= 60
      • require probability_over (or implied) >= 0.55

    Then sorts by (confidence_score * edge_percentage) DESC and keeps
    the top `pool_size`.
    """
    qualified: list[dict[str, Any]] = []
    for p in picks:
        if p.get("player_is_out"):
            continue
        edge = float(p.get("edge_percentage", 0) or 0)
        conf = float(p.get("confidence_score", 0) or 0)
        prob = float(p.get("probability_over", p.get("probability", 0)) or 0)
        if edge <= 0 or conf < 60.0 or prob < 0.55:
            continue
        qualified.append(p)

    qualified.sort(
        key=lambda r: (
            float(r.get("confidence_score", 0) or 0)
            * float(r.get("edge_percentage", 0) or 0)
        ),
        reverse=True,
    )
    return qualified[:pool_size]


def _independent_probability(legs: Iterable[dict[str, Any]]) -> float:
    prob = 1.0
    for leg in legs:
        p = float(leg.get("probability_over", leg.get("probability", 0)) or 0)
        if p <= 0:
            return 0.0
        prob *= p
    return prob


def _avg_off_diagonal(matrix, indices: list[int]) -> float:
    n = len(indices)
    if n < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            try:
                total += float(matrix[indices[i]][indices[j]])
                count += 1
            except (IndexError, TypeError, ValueError):
                continue
    return total / count if count else 0.0


def _safe_score(
    *,
    adjusted_prob: float,
    independent_prob: float,
    avg_edge_pct: float,
    avg_correlation: float,
    payout: float,
) -> float:
    """Blend probability, edge, correlation penalty, and payout into [0, 100].

    Higher = safer/better. The formula:

        ev = adjusted_prob * payout - 1.0          (expected ROI per $1 stake)
        prob_score = adjusted_prob * 100
        edge_score = avg_edge_pct                  (already a %)
        corr_pen   = 30 * max(0, avg_correlation)  (cannibalisation penalty)
        ev_score   = clip(ev * 50, -25, 50)

        safe_score = 0.45*prob_score + 0.25*ev_score + 0.20*edge_score - corr_pen
    """
    ev = adjusted_prob * payout - 1.0
    prob_score = adjusted_prob * 100.0
    ev_score = max(-25.0, min(50.0, ev * 50.0))
    edge_score = avg_edge_pct
    corr_pen = 30.0 * max(0.0, avg_correlation)
    raw = 0.45 * prob_score + 0.25 * ev_score + 0.20 * edge_score - corr_pen
    # Bonus for hitting independent_prob >= 70% (high-confidence floor).
    if independent_prob >= 0.70:
        raw += 5.0
    return round(raw, 2)


def suggest_parlays(
    picks: list[dict[str, Any]],
    *,
    n_legs: int = 3,
    top_k: int = 3,
    game_logs_by_player: dict | None = None,
    payouts: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    """Return the top-K parlays of `n_legs` legs ranked by SAFE score.

    Args:
        picks: today's analysis_picks (each with player_name, stat_type,
            prop_line, direction, probability_over, edge_percentage,
            confidence_score, etc.)
        n_legs: legs per parlay (2..6).
        top_k: how many parlays to return.
        game_logs_by_player: optional dict[name -> list[game_log]] used by
            the correlation engine for empirical correlations.
        payouts: optional dict mapping n_legs -> payout multiplier; defaults
            to PrizePicks/Underdog Power-Play.

    Returns:
        list[dict]: each with keys legs, independent_prob,
        correlation_adjusted_prob, avg_edge_pct, avg_confidence,
        avg_correlation, safe_score, payout_multiplier.  Sorted by
        safe_score DESC.
    """
    if n_legs < 2 or n_legs > _MAX_LEGS:
        raise ValueError(f"n_legs must be 2..{_MAX_LEGS}, got {n_legs}")
    if not picks:
        return []

    pool_size = _POOL_SIZE_BY_LEGS.get(n_legs, 25)
    pool = _qualifying_pool(picks, pool_size)
    if len(pool) < n_legs:
        _logger.info(
            "[parlay_suggester] only %d qualifying picks (need %d) — returning empty.",
            len(pool), n_legs,
        )
        return []

    payout = (payouts or _DEFAULT_PAYOUTS).get(n_legs, _DEFAULT_PAYOUTS.get(n_legs, 5.0))

    # Build correlation matrix once for the entire pool.
    try:
        matrix = build_correlation_matrix(pool, game_logs_by_player=game_logs_by_player)
    except Exception as exc:
        _logger.warning("[parlay_suggester] correlation matrix failed: %s", exc)
        matrix = [[0.0] * len(pool) for _ in range(len(pool))]

    scored: list[dict[str, Any]] = []
    pool_indices = list(range(len(pool)))
    for combo_idx in itertools.combinations(pool_indices, n_legs):
        legs = [pool[i] for i in combo_idx]

        # Skip parlays that double up on the same player (PrizePicks rule).
        names = {(leg.get("player_name") or "").lower() for leg in legs}
        if len(names) != n_legs:
            continue

        ind_prob = _independent_probability(legs)
        if ind_prob <= 0:
            continue

        # Pull individual probabilities and the relevant sub-matrix for correlation adjustment.
        individual_probs = [
            float(leg.get("probability_over", leg.get("probability", 0)) or 0)
            for leg in legs
        ]
        sub_matrix = [
            [matrix[i][j] for j in combo_idx] for i in combo_idx
        ]
        try:
            adjusted_prob = adjust_parlay_probability(individual_probs, sub_matrix)
        except Exception:
            adjusted_prob = ind_prob

        avg_corr = _avg_off_diagonal(matrix, list(combo_idx))
        avg_edge = sum(float(l.get("edge_percentage", 0) or 0) for l in legs) / n_legs
        avg_conf = sum(float(l.get("confidence_score", 0) or 0) for l in legs) / n_legs

        safe = _safe_score(
            adjusted_prob=adjusted_prob,
            independent_prob=ind_prob,
            avg_edge_pct=avg_edge,
            avg_correlation=avg_corr,
            payout=payout,
        )

        scored.append(
            {
                "legs": legs,
                "independent_prob": round(ind_prob, 4),
                "correlation_adjusted_prob": round(adjusted_prob, 4),
                "avg_edge_pct": round(avg_edge, 2),
                "avg_confidence": round(avg_conf, 2),
                "avg_correlation": round(avg_corr, 4),
                "safe_score": safe,
                "payout_multiplier": payout,
            }
        )

    scored.sort(key=lambda r: r["safe_score"], reverse=True)
    return scored[:top_k]


def suggest_parlays_multi(
    picks: list[dict[str, Any]],
    *,
    leg_sizes: tuple[int, ...] = (2, 3, 4),
    top_k_each: int = 3,
    game_logs_by_player: dict | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """Convenience wrapper that returns top-K parlays for several leg sizes."""
    out: dict[int, list[dict[str, Any]]] = {}
    for n in leg_sizes:
        try:
            out[n] = suggest_parlays(
                picks,
                n_legs=n,
                top_k=top_k_each,
                game_logs_by_player=game_logs_by_player,
            )
        except Exception as exc:
            _logger.warning("[parlay_suggester] %d-leg failed: %s", n, exc)
            out[n] = []
    return out


__all__ = ["suggest_parlays", "suggest_parlays_multi"]
