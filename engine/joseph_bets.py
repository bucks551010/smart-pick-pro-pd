# ============================================================
# FILE: engine/joseph_bets.py
# PURPOSE: Connect Joseph M. Smith's analysis to the bet tracker.
#          Log his picks, retrieve his track record, measure accuracy.
# CONNECTS TO: tracking/bet_tracker.py, tracking/database.py
# LAYER: 8 — Joseph Bet Tracker Integration
# ============================================================
"""Connect Joseph M. Smith's analysis picks to the bet tracking system.

Logs Joseph's picks to the database, retrieves his historical track
record, and calculates win-rate / accuracy metrics per verdict tier
(SMASH, LEAN) and for override calls.

Functions
---------
joseph_auto_log_bets
    Persist Joseph's picks from a completed analysis run.
joseph_get_track_record
    Aggregate win/loss/pending stats and ROI estimate.
joseph_get_accuracy_by_verdict
    Break down accuracy by verdict tier.
joseph_get_override_accuracy
    Measure how often Joseph's overrides beat the model.
"""

import datetime
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Tracking imports (each wrapped for resilience) ───────────
try:
    from tracking.bet_tracker import log_new_bet
except ImportError:
    def log_new_bet(*args, **kwargs):
        return (False, "log_new_bet unavailable")

try:
    from tracking.database import load_all_bets, _nba_today_iso
except ImportError:
    def load_all_bets(**kwargs):
        return []
    def _nba_today_iso():
        import datetime as _d
        return _d.date.today().isoformat()


# ============================================================
# SECTION: joseph_auto_log_bets
# ============================================================

def joseph_auto_log_bets(joseph_results: list) -> tuple:
    """
    Log Joseph M. Smith's analysis picks to the bet tracker.

    For each result with a verdict of SMASH or LEAN, call
    ``tracking.bet_tracker.log_new_bet`` with Joseph-specific
    metadata.  Duplicate bets for the same player + stat + line
    on the same day are skipped.

    Args:
        joseph_results (list[dict]): Analysis results produced by
            the Joseph engine.  Each dict is expected to contain at
            minimum: ``player_name``, ``stat_type``, ``line``,
            ``direction``, and ``verdict``.

    Returns:
        tuple[int, str]: (count_logged, summary_message).
            On failure returns (0, error_message).
    """
    try:
        if not joseph_results:
            return (0, "Joseph logged 0 bets tonight")

        # Build dedup set from today's existing bets.
        # IMPORTANT: use ET-anchored date (_nba_today_iso) so Railway's
        # UTC server doesn't tag 8 PM-midnight ET picks as tomorrow.
        today_str = _nba_today_iso()
        all_today = load_all_bets(exclude_linked=False)
        existing_keys: set = set()
        for b in all_today:
            bet_date = str(b.get("bet_date", ""))
            if bet_date == today_str:
                key = (
                    str(b.get("player_name", "")).strip().lower(),
                    str(b.get("stat_type", "")).strip().lower(),
                    float(b.get("prop_line", 0)),
                    str(b.get("direction", "OVER")).upper(),
                )
                existing_keys.add(key)

        count_logged = 0

        for result in joseph_results:
            verdict = str(result.get("verdict", "")).upper()
            if verdict not in ("LOCK", "SMASH", "LEAN"):
                continue

            player_name = str(result.get("player_name", ""))
            stat_type = str(result.get("stat_type", ""))
            line = float(result.get("line", 0))
            direction = str(result.get("direction", "OVER"))

            # Dedup check
            dedup_key = (
                player_name.strip().lower(),
                stat_type.strip().lower(),
                line,
                direction.upper(),
            )
            if dedup_key in existing_keys:
                continue

            nerd_stats = result.get("nerd_stats", {}) or {}
            one_liner = result.get("one_liner", "")

            ok, _msg = log_new_bet(
                player_name=player_name,
                stat_type=stat_type,
                prop_line=line,
                direction=direction,
                platform="Joseph M. Smith",
                confidence_score=float(result.get("confidence_pct", 0)),
                probability_over=float(nerd_stats.get("joseph_probability", 0)),
                edge_percentage=float(result.get("joseph_edge", 0)),
                tier=verdict,
                entry_fee=0.0,
                team=str(result.get("player_team", "")),
                notes=f"\U0001f399\ufe0f Joseph M. Smith \u2014 {verdict} \u2014 {one_liner}",
                auto_logged=1,
                bet_type="joseph_pick",
                std_devs_from_line=0.0,
                source="joseph",
            )

            if ok:
                existing_keys.add(dedup_key)
                count_logged += 1

        return (count_logged, f"Joseph logged {count_logged} bets tonight")

    except Exception as exc:
        _logger.error("joseph_auto_log_bets error: %s", exc)
        return (0, f"Error logging Joseph bets: {exc}")


# ============================================================
# SECTION: joseph_get_track_record
# ============================================================

def _is_joseph_bet(bet: dict) -> bool:
    """Return True if *bet* was placed by/through Joseph M. Smith."""
    notes = str(bet.get("notes", ""))
    platform = str(bet.get("platform", ""))
    return "Joseph M. Smith" in notes or platform == "Joseph M. Smith"


def joseph_get_track_record() -> dict:
    """
    Load all Joseph M. Smith bets and compute a comprehensive
    track-record summary.

    Returns:
        dict: Keys — total, wins, losses, pending, win_rate,
              roi_estimate, accuracy_by_verdict, streak,
              best_pick, worst_pick.
              On error returns a dict with all zeroes.
    """
    _zero = {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "pending": 0,
        "win_rate": 0.0,
        "roi_estimate": 0.0,
        "accuracy_by_verdict": {
            "LOCK": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
            "SMASH": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
            "LEAN": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0},
        },
        "streak": 0,
        "best_pick": "",
        "worst_pick": "",
    }

    try:
        all_bets = load_all_bets(limit=2000)
        joseph_bets = [b for b in all_bets if _is_joseph_bet(b)]

        if not joseph_bets:
            return _zero

        total = len(joseph_bets)
        wins = 0
        losses = 0
        pending = 0

        # Per-verdict accumulators
        verdict_stats: dict = {
            "LOCK": {"total": 0, "wins": 0, "losses": 0},
            "SMASH": {"total": 0, "wins": 0, "losses": 0},
            "LEAN": {"total": 0, "wins": 0, "losses": 0},
        }

        # For best/worst pick tracking
        best_edge_won = -999.0
        best_pick = ""
        worst_conf_lost = -1.0
        worst_pick = ""

        # For streak calculation (most-recent first, which is the
        # default sort from load_all_bets ORDER BY created_at DESC)
        results_sequence: list = []

        for bet in joseph_bets:
            result = str(bet.get("result", "") or "").strip()
            tier = str(bet.get("tier", "")).upper()

            # Classify outcome
            if result.upper() in ("WIN", "W"):
                wins += 1
                results_sequence.append("W")
            elif result.upper() in ("LOSS", "L"):
                losses += 1
                results_sequence.append("L")
            else:
                pending += 1

            # Verdict grouping
            if tier in verdict_stats:
                verdict_stats[tier]["total"] += 1
                if result.upper() in ("WIN", "W"):
                    verdict_stats[tier]["wins"] += 1
                elif result.upper() in ("LOSS", "L"):
                    verdict_stats[tier]["losses"] += 1

            # Best pick: highest edge that won
            edge = float(bet.get("edge_percentage", 0) or 0)
            if result.upper() in ("WIN", "W") and edge > best_edge_won:
                best_edge_won = edge
                best_pick = f"{bet.get('player_name', '')} {bet.get('stat_type', '')} ({edge:.1f}% edge)"

            # Worst pick: highest confidence that lost
            conf = float(bet.get("confidence_score", 0) or 0)
            if result.upper() in ("LOSS", "L") and conf > worst_conf_lost:
                worst_conf_lost = conf
                worst_pick = f"{bet.get('player_name', '')} {bet.get('stat_type', '')} ({conf:.0f} confidence)"

        decided = wins + losses
        win_rate = (wins / max(decided, 1)) * 100
        roi_estimate = ((wins * 0.909 - losses) / max(decided, 1)) * 100

        # Streak: count consecutive identical outcomes from the front
        # of results_sequence (most recent first)
        streak = 0
        if results_sequence:
            first = results_sequence[0]
            for r in results_sequence:
                if r == first:
                    streak += 1
                else:
                    break
            if first == "L":
                streak = -streak

        # Build accuracy_by_verdict
        accuracy_by_verdict = {}
        for v in ("LOCK", "SMASH", "LEAN"):
            vt = verdict_stats[v]["total"]
            vw = verdict_stats[v]["wins"]
            vl = verdict_stats[v]["losses"]
            vd = vw + vl
            accuracy_by_verdict[v] = {
                "total": vt,
                "wins": vw,
                "losses": vl,
                "win_rate": round((vw / max(vd, 1)) * 100, 1),
            }

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "win_rate": round(win_rate, 1),
            "roi_estimate": round(roi_estimate, 1),
            "accuracy_by_verdict": accuracy_by_verdict,
            "streak": streak,
            "best_pick": best_pick,
            "worst_pick": worst_pick,
        }

    except Exception as exc:
        _logger.error("joseph_get_track_record error: %s", exc)
        return _zero


# ============================================================
# SECTION: joseph_get_accuracy_by_verdict
# ============================================================

def joseph_get_accuracy_by_verdict() -> dict:
    """
    Return Joseph's accuracy grouped by verdict tier (LOCK / SMASH / LEAN).

    Returns:
        dict: ``{"LOCK": {total, wins, pct}, "SMASH": {total, wins, pct}, "LEAN": {total, wins, pct}}``
    """
    try:
        all_bets = load_all_bets(limit=2000)
        joseph_bets = [b for b in all_bets if _is_joseph_bet(b)]

        output: dict = {}
        for verdict in ("LOCK", "SMASH", "LEAN"):
            subset = [
                b for b in joseph_bets
                if str(b.get("tier", "")).upper() == verdict
            ]
            total = len(subset)
            wins = sum(
                1 for b in subset
                if str(b.get("result", "") or "").strip().upper() in ("WIN", "W")
            )
            decided = sum(
                1 for b in subset
                if str(b.get("result", "") or "").strip().upper() in ("WIN", "W", "LOSS", "L")
            )
            pct = round((wins / max(decided, 1)) * 100, 1)
            output[verdict] = {"total": total, "wins": wins, "pct": pct}

        return output

    except Exception as exc:
        _logger.error("joseph_get_accuracy_by_verdict error: %s", exc)
        return {
            "SMASH": {"total": 0, "wins": 0, "pct": 0.0},
            "LEAN": {"total": 0, "wins": 0, "pct": 0.0},
        }


# ============================================================
# SECTION: joseph_get_override_accuracy
# ============================================================

def joseph_get_override_accuracy() -> dict:
    """
    Calculate how often Joseph's overrides (disagreements with QME)
    turned out to be correct.

    Returns:
        dict: Keys — overrides_total, overrides_correct,
              override_accuracy, summary.
              If no overrides found, returns a message string
              under the ``summary`` key.
    """
    try:
        all_bets = load_all_bets(limit=2000)
        joseph_bets = [b for b in all_bets if _is_joseph_bet(b)]

        override_bets = [
            b for b in joseph_bets
            if "OVERRIDE" in str(b.get("notes", "")).upper()
        ]

        overrides_total = len(override_bets)

        if overrides_total == 0:
            return {
                "overrides_total": 0,
                "overrides_correct": 0,
                "override_accuracy": 0.0,
                "summary": "No overrides recorded yet.",
            }

        overrides_correct = sum(
            1 for b in override_bets
            if str(b.get("result", "") or "").strip().upper() in ("WIN", "W")
        )
        override_accuracy = round(
            (overrides_correct / max(overrides_total, 1)) * 100, 1
        )

        return {
            "overrides_total": overrides_total,
            "overrides_correct": overrides_correct,
            "override_accuracy": override_accuracy,
            "summary": (
                f"When Joseph disagreed with QME, he was right "
                f"{override_accuracy}% of the time"
            ),
        }

    except Exception as exc:
        _logger.error("joseph_get_override_accuracy error: %s", exc)
        return {
            "overrides_total": 0,
            "overrides_correct": 0,
            "override_accuracy": 0.0,
            "summary": f"Error calculating override accuracy: {exc}",
        }
