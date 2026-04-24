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


# ── WEEKLY RESULTS READER ───────────────────────────────────────────

@dataclass
class WeeklySummary:
    week_start:   str
    week_end:     str
    wins:         int = 0
    losses:       int = 0
    win_rate:     float = 0.0
    roi_pct:      float | None = None
    winning_bets: list[dict[str, Any]] = field(default_factory=list)


def get_results_for_week(end_date: date | None = None) -> WeeklySummary:
    """Aggregate W/L/ROI for the 7-day window ending on end_date (default: yesterday).
    Only winning bets are returned for social display.
    """
    end_date = end_date or (date.today() - timedelta(days=1))
    start_date = end_date - timedelta(days=6)  # Mon–Sun or rolling 7 days

    if _engine is None:
        return WeeklySummary(
            week_start=start_date.isoformat(),
            week_end=end_date.isoformat(),
        )

    sql = text(
        "SELECT * FROM bets "
        "WHERE bet_date BETWEEN :start AND :end "
        "ORDER BY result DESC, bet_date ASC"
    )
    with _engine.connect() as conn:
        bets = _rows_to_dicts(
            conn.execute(sql, {"start": start_date.isoformat(), "end": end_date.isoformat()})
        )

    wins   = [b for b in bets if (b.get("result") or "").upper() == "WIN"]
    losses = [b for b in bets if (b.get("result") or "").upper() == "LOSS"]
    resolved = len(wins) + len(losses)
    win_rate = (len(wins) / resolved * 100.0) if resolved else 0.0

    stake_total  = resolved
    payout_total = sum(float(b.get("payout") or 0) for b in wins)
    roi_pct = ((payout_total - stake_total) / stake_total * 100.0) if stake_total else None

    return WeeklySummary(
        week_start=start_date.isoformat(),
        week_end=end_date.isoformat(),
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        roi_pct=roi_pct,
        winning_bets=wins,  # full detail so post can list each prop
    )


# ── PRE-GAME TRIGGER HELPER ──────────────────────────────────

# ── PUBLIC RESULTS LEDGER ────────────────────────────────────

@dataclass
class LedgerEntry:
    bet_date:         str
    player_name:      str
    stat_type:        str
    direction:        str
    prop_line:        float
    platform:         str
    result:           str   # WIN | LOSS | PUSH | PENDING
    confidence_score: float | None = None
    edge_pct:         float | None = None
    payout:           float | None = None
    headshot_url:     str | None = None


@dataclass
class LedgerSummary:
    entries:     list[LedgerEntry]
    total_wins:  int = 0
    total_losses: int = 0
    total_push:  int = 0
    all_time_win_rate: float = 0.0
    all_time_roi:      float | None = None


def get_public_ledger(
    days_back: int = 30,
    limit: int = 500,
) -> LedgerSummary:
    """Full bet history for public results ledger — no auth required.

    Returns up to `limit` bets from the last `days_back` days, most
    recent first. All W/L results shown — wins AND losses, always.
    """
    if _engine is None:
        return LedgerSummary(entries=[])

    since = (date.today() - timedelta(days=days_back)).isoformat()
    sql = text(
        "SELECT bet_date, player_name, stat_type, direction, prop_line, "
        "       platform, result, confidence_score, edge_pct, payout, headshot_url "
        "FROM bets "
        "WHERE bet_date >= :since AND result IN ('WIN','LOSS','PUSH') "
        "ORDER BY bet_date DESC, bet_id DESC "
        "LIMIT :lim"
    )
    with _engine.connect() as conn:
        rows = _rows_to_dicts(conn.execute(sql, {"since": since, "lim": limit}))

    entries = [LedgerEntry(**{k: r.get(k) for k in LedgerEntry.__dataclass_fields__}) for r in rows]
    wins   = sum(1 for e in entries if e.result == "WIN")
    losses = sum(1 for e in entries if e.result == "LOSS")
    resolved = wins + losses
    win_rate = (wins / resolved * 100.0) if resolved else 0.0

    stake_total  = resolved
    payout_total = sum((e.payout or 0.0) for e in entries if e.result == "WIN")
    roi = ((payout_total - stake_total) / stake_total * 100.0) if stake_total else None

    return LedgerSummary(
        entries=entries,
        total_wins=wins, total_losses=losses,
        total_push=sum(1 for e in entries if e.result == "PUSH"),
        all_time_win_rate=win_rate,
        all_time_roi=roi,
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
