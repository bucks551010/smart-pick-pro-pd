"""Direct DB reader for slate / results / QEG picks / top-3 / platform picks.

Reads from the same database the main Smart Pick Pro app writes to.
Schema reference (from `tracking/database.py`):
  - all_analysis_picks(pick_date, player_name, team, opponent, stat_type,
                        prop_line, direction, confidence_score, edge_pct,
                        platform, tier, headshot_url, ...)
  - bets(bet_id, bet_date, player_name, stat_type, prop_line, direction,
         platform, tier, result, payout, ...)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import create_engine, text

from config import SETTINGS

_engine = create_engine(SETTINGS.database_url, future=True) if SETTINGS.database_url else None


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in rows]


# ── SLATE READERS ────────────────────────────────────────────

def get_slate_for_date(pick_date: date | None = None) -> list[dict[str, Any]]:
    """All analysis picks for the given date (default: today)."""
    if _engine is None:
        return []
    pick_date = pick_date or date.today()
    sql = text(
        "SELECT * FROM all_analysis_picks "
        "WHERE pick_date = :d ORDER BY confidence_score DESC"
    )
    with _engine.connect() as conn:
        return _rows_to_dicts(conn.execute(sql, {"d": pick_date.isoformat()}))


def get_top_n_picks(n: int = 3, pick_date: date | None = None) -> list[dict[str, Any]]:
    """Top-N picks by confidence_score for the given date."""
    return get_slate_for_date(pick_date)[:n]


def get_qeg_picks(
    edge_threshold: float = 5.0,
    pick_date: date | None = None,
) -> list[dict[str, Any]]:
    """Quantum Edge Gap picks — picks with edge_pct above threshold."""
    rows = get_slate_for_date(pick_date)
    return [r for r in rows if (r.get("edge_pct") or 0) >= edge_threshold]


def get_platform_picks(
    platform: str,
    pick_date: date | None = None,
) -> list[dict[str, Any]]:
    """All picks for a specific platform (PrizePicks / Underdog / DK Pick6)."""
    rows = get_slate_for_date(pick_date)
    return [r for r in rows if (r.get("platform") or "").lower() == platform.lower()]


# ── RESULTS READERS ──────────────────────────────────────────

@dataclass
class ResultsSummary:
    bet_date:  str
    wins:      int = 0
    losses:    int = 0
    pending:   int = 0
    total:     int = 0
    win_rate:  float = 0.0
    roi_pct:   float | None = None
    bets:      list[dict[str, Any]] = field(default_factory=list)


def get_results_for_date(bet_date: date | None = None) -> ResultsSummary:
    """Aggregate W/L/ROI for all bets resolved on the given date."""
    bet_date = bet_date or (date.today() - timedelta(days=1))
    if _engine is None:
        return ResultsSummary(bet_date=bet_date.isoformat())

    sql = text(
        "SELECT * FROM bets WHERE bet_date = :d "
        "ORDER BY result DESC, bet_id ASC"
    )
    with _engine.connect() as conn:
        bets = _rows_to_dicts(conn.execute(sql, {"d": bet_date.isoformat()}))

    wins   = sum(1 for b in bets if (b.get("result") or "").upper() == "WIN")
    losses = sum(1 for b in bets if (b.get("result") or "").upper() == "LOSS")
    pending = sum(1 for b in bets if (b.get("result") or "").upper() in ("", "PENDING"))
    resolved = wins + losses
    win_rate = (wins / resolved * 100.0) if resolved else 0.0

    # Naïve ROI: sum payouts where present, assume 1u stake otherwise
    stake_total = resolved  # 1 unit per resolved bet
    payout_total = sum(float(b.get("payout") or 0) for b in bets if (b.get("result") or "").upper() == "WIN")
    roi_pct = ((payout_total - stake_total) / stake_total * 100.0) if stake_total else None

    return ResultsSummary(
        bet_date=bet_date.isoformat(),
        wins=wins, losses=losses, pending=pending,
        total=len(bets), win_rate=win_rate, roi_pct=roi_pct,
        bets=bets,
    )


# ── PRE-GAME TRIGGER HELPER ──────────────────────────────────

def get_games_starting_in(hours_window: tuple[int, int] = (1, 3)) -> list[dict[str, Any]]:
    """Games tipping off between hours_window[0] and hours_window[1] from now.

    Used by scheduler to know when to fire pre-game posts. Schema assumed:
      games(game_id, game_date, tipoff_utc, home_team, away_team)
    Returns [] silently if table doesn't exist (graceful degradation).
    """
    if _engine is None:
        return []
    sql = text(
        "SELECT * FROM games "
        "WHERE tipoff_utc BETWEEN :lo AND :hi "
        "ORDER BY tipoff_utc"
    )
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    lo = (now + timedelta(hours=hours_window[0])).isoformat()
    hi = (now + timedelta(hours=hours_window[1])).isoformat()
    try:
        with _engine.connect() as conn:
            return _rows_to_dicts(conn.execute(sql, {"lo": lo, "hi": hi}))
    except Exception:
        return []
