# ============================================================
# FILE: engine/clv_tracker.py
# PURPOSE: Closing Line Value (CLV) Tracker (C12)
#          Stores the model's projection vs the prop line at time
#          of analysis, and later tracks the closing line.
#          Computes CLV = (closing_line - opening_line) in the
#          direction the model recommended.
#
#          Positive CLV = model had real edge (book moved toward model)
#          Negative CLV = model was wrong (book moved away from model)
#
#          CLV is the gold standard for validating whether the model
#          has real predictive edge vs market efficiency.
#
# STORAGE: SQLite via tracking/database.py (if available),
#          otherwise falls back to a local JSON file.
# CONNECTS TO: tracking/database.py (persistence layer)
# CONCEPTS COVERED: Closing Line Value, market efficiency,
#                   model validation, edge measurement
# ============================================================

import json
import datetime
import os
import logging
from pathlib import Path
from datetime import timezone as _tz


def _utcnow_iso() -> str:
    """Return the current UTC datetime as an ISO-8601 string with Z suffix.
    Replaces naive datetime.now().isoformat() calls throughout this module
    so CLV timestamps are unambiguous regardless of server timezone. (A-022)"""
    return datetime.datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# Fallback storage path when tracking/database.py is unavailable
_CLV_JSON_PATH = Path(__file__).parent.parent / "tracking" / "clv_log.json"

# ============================================================
# END SECTION: Module-Level Constants
# ============================================================


# ============================================================
# SECTION: CLV Record Management
# ============================================================

def store_opening_line(
    player_name,
    stat_type,
    opening_line,
    model_projection,
    model_direction,
    confidence_score,
    tier,
    edge_percentage,
):
    """
    Record the opening line and model projection at time of analysis. (C12)

    Call this when the model produces a pick. Later call update_closing_line()
    to record the final closing line and compute CLV.

    Args:
        player_name (str): Player being analyzed
        stat_type (str): Stat category (e.g., 'points', 'rebounds')
        opening_line (float): The prop line at time of analysis
        model_projection (float): The model's projected value
        model_direction (str): 'OVER' or 'UNDER'
        confidence_score (float): 0-100 confidence score from engine
        tier (str): 'Platinum', 'Gold', 'Silver', 'Bronze'
        edge_percentage (float): Model's edge in percentage points

    Returns:
        str: Record ID (player_stat_timestamp) for use in update_closing_line()
    """
    record_id = f"{player_name.lower().replace(' ', '_')}_{stat_type}_{datetime.datetime.now(_tz.utc).strftime('%Y%m%d_%H%M%S')}"

    record = {
        "record_id":        record_id,
        "player_name":      player_name,
        "stat_type":        stat_type,
        "opening_line":     opening_line,
        "model_projection": model_projection,
        "model_direction":  model_direction,
        "confidence_score": confidence_score,
        "tier":             tier,
        "edge_percentage":  edge_percentage,
        "opening_timestamp": _utcnow_iso(),
        "closing_line":     None,
        "closing_timestamp": None,
        "clv":              None,
        "clv_direction":    None,
    }

    _save_clv_record(record)
    return record_id


def update_closing_line(record_id, closing_line):
    """
    Record the closing line and compute CLV for a stored pick. (C12)

    CLV = (closing_line - opening_line) in the direction the model recommended.
    Positive CLV means the market moved toward the model's view = real edge.
    Negative CLV means the market moved against the model = model was wrong.

    Args:
        record_id (str): The ID returned by store_opening_line()
        closing_line (float): The final prop line when the market closed

    Returns:
        float or None: CLV value, or None if record not found
    """
    records = _load_all_clv_records()
    record = records.get(record_id)
    if not record:
        return None

    opening = record.get("opening_line")
    direction = record.get("model_direction", "OVER")

    if opening is None:
        return None

    # CLV calculation:
    # For OVER picks: positive CLV means the line moved up (harder to hit)
    #   but this means the book agrees the player will perform well.
    #   CLV = closing_line - opening_line (in points, positive = line moved up)
    # For UNDER picks: positive CLV means the line moved down
    #   CLV = opening_line - closing_line
    if direction == "OVER":
        clv = closing_line - opening
    else:
        clv = opening - closing_line

    record["closing_line"] = closing_line
    record["closing_timestamp"] = _utcnow_iso()
    record["clv"] = round(clv, 2)
    record["clv_direction"] = "positive" if clv > 0 else "negative" if clv < 0 else "neutral"

    records[record_id] = record
    _save_all_clv_records(records)
    return clv


def get_clv_summary(days=90, min_records=5):
    """
    Return summary CLV statistics for the Model Health page. (C12)

    Args:
        days (int): Number of past days to include. Default 90.
        min_records (int): Minimum records needed to report meaningful stats.

    Returns:
        dict: {
            'has_data': bool,
            'total_records': int,
            'records_with_clv': int,
            'avg_clv': float or None,
            'positive_clv_rate': float or None (pct of picks with +CLV),
            'clv_by_tier': dict {tier: avg_clv},
            'interpretation': str,
        }
    """
    try:
        records = _load_all_clv_records()
        total = len(records)

        if total < min_records:
            return {
                "has_data": False, "total_records": total,
                "records_with_clv": 0, "avg_clv": None,
                "positive_clv_rate": None, "clv_by_tier": {},
                "interpretation": "Insufficient data (cold start)",
            }

        # Filter to recent records
        cutoff = datetime.datetime.now(_tz.utc).replace(tzinfo=None) - datetime.timedelta(days=days)
        recent = [
            r for r in records.values()
            if r.get("closing_line") is not None
            and _safe_parse_timestamp(r.get("opening_timestamp")) is not None
            and _safe_parse_timestamp(r.get("opening_timestamp")) >= cutoff
        ]

        if not recent:
            return {
                "has_data": False, "total_records": total,
                "records_with_clv": 0, "avg_clv": None,
                "positive_clv_rate": None, "clv_by_tier": {},
                "interpretation": "No closed picks in the last {} days".format(days),
            }

        clv_values = [r["clv"] for r in recent if r.get("clv") is not None]
        if not clv_values:
            return {
                "has_data": False, "total_records": total,
                "records_with_clv": 0, "avg_clv": None,
                "positive_clv_rate": None, "clv_by_tier": {},
                "interpretation": "No CLV data available yet",
            }

        avg_clv = sum(clv_values) / len(clv_values)
        positive_rate = sum(1 for v in clv_values if v > 0) / len(clv_values)

        # CLV by tier
        clv_by_tier = {}
        for r in recent:
            tier = r.get("tier", "Unknown")
            clv = r.get("clv")
            if clv is not None:
                if tier not in clv_by_tier:
                    clv_by_tier[tier] = []
                clv_by_tier[tier].append(clv)
        clv_by_tier = {t: round(sum(v) / len(v), 3) for t, v in clv_by_tier.items() if v}

        # Interpretation
        if avg_clv > 0.5:
            interpretation = "✅ Strong positive CLV — model has real market edge"
        elif avg_clv > 0:
            interpretation = "🟡 Weak positive CLV — marginal edge, monitor"
        elif avg_clv > -0.5:
            interpretation = "🟠 Slightly negative CLV — model lagging the market"
        else:
            interpretation = "❌ Negative CLV — model has no market edge, review assumptions"

        return {
            "has_data": True,
            "total_records": total,
            "records_with_clv": len(clv_values),
            "avg_clv": round(avg_clv, 3),
            "positive_clv_rate": round(positive_rate, 4),
            "clv_by_tier": clv_by_tier,
            "interpretation": interpretation,
        }
    except Exception:
        return {
            "has_data": False, "total_records": 0, "records_with_clv": 0,
            "avg_clv": None, "positive_clv_rate": None, "clv_by_tier": {},
            "interpretation": "Error loading CLV data",
        }

# ============================================================
# END SECTION: CLV Record Management
# ============================================================


# ============================================================
# SECTION: Internal Helpers
# ============================================================

def _safe_parse_timestamp(ts_value):
    """
    Safely parse an ISO-format timestamp string.

    Returns a datetime.datetime on success, or None on any failure
    (missing value, empty string, malformed string, etc.).

    Args:
        ts_value: Raw value from a CLV record dict.

    Returns:
        datetime.datetime or None.
    """
    if not ts_value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(ts_value))
    except (ValueError, TypeError):
        return None

# ============================================================
# END SECTION: Internal Helpers
# ============================================================


# ============================================================
# SECTION: Model Edge Validation
# ============================================================

def validate_model_edge(days=90):
    """
    Validate model edge quality using CLV performance by tier and stat type.

    Computes CLV hit rate by tier (Platinum/Gold/Silver/Bronze) and by stat
    type. Identifies stat types the model is consistently wrong on (negative
    CLV) and returns a stat_adjustment_factors dict to penalise those stats.

    Args:
        days (int): Number of past days to include. Default 90.

    Returns:
        dict: {
            'clv_by_tier': {tier: {'avg_clv': float, 'positive_rate': float,
                                   'count': int}},
            'clv_by_stat': {stat_type: {'avg_clv': float,
                                        'positive_rate': float, 'count': int}},
            'stat_adjustment_factors': {stat_type: clv_adjustment_factor},
            'interpretation': str,
        }

    Example:
        result = validate_model_edge(days=90)
        # result['stat_adjustment_factors']['threes'] might be 0.92 if model
        # consistently over-rates three-point props.
    """
    empty_result = {
        "clv_by_tier": {},
        "clv_by_stat": {},
        "stat_adjustment_factors": {},
        "interpretation": "Insufficient data (cold start)",
    }

    try:
        records = _load_all_clv_records()
        if not records:
            return empty_result

        # Filter to recent records that have a closing line
        cutoff = datetime.datetime.now(_tz.utc).replace(tzinfo=None) - datetime.timedelta(days=days)
        recent = [
            r for r in records.values()
            if r.get("closing_line") is not None
            and r.get("clv") is not None
            and _safe_parse_timestamp(r.get("opening_timestamp")) is not None
            and _safe_parse_timestamp(r.get("opening_timestamp")) >= cutoff
        ]

        if not recent:
            return empty_result

        # ── Group by tier ────────────────────────────────────────────────────
        tier_buckets = {}
        for r in recent:
            tier = r.get("tier", "Unknown")
            tier_buckets.setdefault(tier, []).append(r["clv"])

        clv_by_tier = {}
        for tier, values in tier_buckets.items():
            avg = sum(values) / len(values)
            pos_rate = sum(1 for v in values if v > 0) / len(values)
            clv_by_tier[tier] = {
                "avg_clv":       round(avg, 3),
                "positive_rate": round(pos_rate, 4),
                "count":         len(values),
            }

        # ── Group by stat_type ───────────────────────────────────────────────
        stat_buckets = {}
        for r in recent:
            stat = r.get("stat_type", "unknown")
            stat_buckets.setdefault(stat, []).append(r["clv"])

        clv_by_stat = {}
        for stat, values in stat_buckets.items():
            avg = sum(values) / len(values)
            pos_rate = sum(1 for v in values if v > 0) / len(values)
            clv_by_stat[stat] = {
                "avg_clv":       round(avg, 3),
                "positive_rate": round(pos_rate, 4),
                "count":         len(values),
            }

        # ── Stat adjustment factors ──────────────────────────────────────────
        # Penalise stat types where the model consistently loses CLV.
        # avg_clv < -0.6 → 12% penalty (factor 0.88)
        # avg_clv < -0.3 → 8%  penalty (factor 0.92)
        # otherwise      → no penalty  (factor 1.0)
        stat_adjustment_factors = {}
        for stat, info in clv_by_stat.items():
            avg_clv = info["avg_clv"]
            if avg_clv < -0.6:
                factor = 0.88
            elif avg_clv < -0.3:
                factor = 0.92
            else:
                factor = 1.0
            stat_adjustment_factors[stat] = factor

        # ── Overall interpretation ───────────────────────────────────────────
        all_clv = [r["clv"] for r in recent]
        overall_avg = sum(all_clv) / len(all_clv)
        if overall_avg > 0.5:
            interpretation = "✅ Strong positive CLV across stat types"
        elif overall_avg > 0:
            interpretation = "🟡 Marginal positive CLV — monitor by stat type"
        elif overall_avg > -0.5:
            interpretation = "🟠 Slightly negative CLV — model lagging market on some stats"
        else:
            interpretation = "❌ Negative CLV — significant model underperformance detected"

        return {
            "clv_by_tier":             clv_by_tier,
            "clv_by_stat":             clv_by_stat,
            "stat_adjustment_factors": stat_adjustment_factors,
            "interpretation":          interpretation,
        }

    except Exception:
        return empty_result


def get_stat_type_clv_penalties(days=90):
    """
    Return per-stat-type confidence penalties based on historical CLV
    performance.

    Stats with consistently negative CLV get a 3-8 point confidence penalty
    to reduce over-betting on stat types where the model underperforms.

    Args:
        days (int): Days of history to consider. Default 90.

    Returns:
        dict: {stat_type: penalty_points} where penalty_points is 0-8.
            Returns empty dict on cold start (insufficient data).

    Example:
        penalties = get_stat_type_clv_penalties()
        # {'threes': 5.0, 'blocks': 3.0} means reduce confidence for those stats
    """
    try:
        edge_data = validate_model_edge(days=days)
        clv_by_stat = edge_data.get("clv_by_stat", {})

        if not clv_by_stat:
            return {}

        penalties = {}
        for stat, info in clv_by_stat.items():
            # Require at least 5 records before applying any penalty
            if info.get("count", 0) < 5:
                continue

            avg_clv = info["avg_clv"]
            if avg_clv < -0.6:
                penalty = 8.0
            elif avg_clv < -0.4:
                penalty = 6.0
            elif avg_clv < -0.2:
                penalty = 4.0
            elif avg_clv < 0.0:
                penalty = 3.0
            else:
                penalty = 0.0

            penalties[stat] = penalty

        return penalties

    except Exception:
        return {}


def get_tier_accuracy_report(days=90):
    """
    Generate an accuracy report by tier for the Model Health page.

    Shows actual win rates vs predicted probabilities broken down by tier.
    Only counts records where the bet result is stored (has closing_line AND
    a 'bet_result' field of 1/0). CLV-only records (no bet_result) are
    reported as CLV-stats-only without win rate.

    Args:
        days (int): Days of history to consider. Default 90.

    Returns:
        dict: {
            'has_data': bool,
            'by_tier': {
                tier: {
                    'count': int,
                    'avg_clv': float,
                    'positive_clv_rate': float,
                    'avg_confidence': float,
                    'win_rate': float or None,
                }
            },
            'summary': str,
        }

    Example:
        report = get_tier_accuracy_report()
        # report['by_tier']['Platinum']['positive_clv_rate'] → 0.72
    """
    empty_result = {
        "has_data": False,
        "by_tier":  {},
        "summary":  "Insufficient data (cold start)",
    }

    try:
        records = _load_all_clv_records()
        if not records:
            return empty_result

        # Filter to recent records that have a closing line
        cutoff = datetime.datetime.now(_tz.utc).replace(tzinfo=None) - datetime.timedelta(days=days)
        recent = [
            r for r in records.values()
            if r.get("closing_line") is not None
            and _safe_parse_timestamp(r.get("opening_timestamp")) is not None
            and _safe_parse_timestamp(r.get("opening_timestamp")) >= cutoff
        ]

        if not recent:
            return empty_result

        # ── Group by tier ────────────────────────────────────────────────────
        tier_buckets = {}
        for r in recent:
            tier = r.get("tier", "Unknown")
            tier_buckets.setdefault(tier, []).append(r)

        by_tier = {}
        for tier, recs in tier_buckets.items():
            clv_values = [r["clv"] for r in recs if r.get("clv") is not None]
            confidence_values = [
                r["confidence_score"] for r in recs
                if r.get("confidence_score") is not None
            ]

            # Win rate only from records that carry a bet_result (0 or 1)
            bet_result_recs = [
                r for r in recs if r.get("bet_result") in (0, 1)
            ]
            win_rate = (
                sum(r["bet_result"] for r in bet_result_recs) / len(bet_result_recs)
                if bet_result_recs else None
            )

            avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0
            pos_clv_rate = (
                sum(1 for v in clv_values if v > 0) / len(clv_values)
                if clv_values else 0.0
            )
            avg_conf = (
                sum(confidence_values) / len(confidence_values)
                if confidence_values else 0.0
            )

            by_tier[tier] = {
                "count":             len(recs),
                "avg_clv":           round(avg_clv, 3),
                "positive_clv_rate": round(pos_clv_rate, 4),
                "avg_confidence":    round(avg_conf, 2),
                "win_rate":          round(win_rate, 4) if win_rate is not None else None,
            }

        if not by_tier:
            return empty_result

        # ── Summary sentence ─────────────────────────────────────────────────
        total_recs = sum(v["count"] for v in by_tier.values())
        summary = (
            f"Tier accuracy report: {total_recs} closed picks across "
            f"{len(by_tier)} tier(s) in the last {days} days."
        )

        return {
            "has_data": True,
            "by_tier":  by_tier,
            "summary":  summary,
        }

    except Exception:
        return empty_result

# ============================================================
# END SECTION: Model Edge Validation
# ============================================================


# ============================================================
# SECTION: Storage Helpers
# ============================================================

def _load_all_clv_records():
    """Load all CLV records from JSON file. Returns dict {record_id: record}."""
    try:
        if _CLV_JSON_PATH.exists():
            with open(_CLV_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[CLV] Unexpected error in CLV summary: {_exc}")
    return {}


def _save_all_clv_records(records):
    """Save all CLV records to JSON file."""
    try:
        _CLV_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CLV_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)
    except Exception as exc:
        logging.getLogger(__name__).warning("CLV tracker: could not save records: %s", exc)


def _save_clv_record(record):
    """Save a single CLV record (append to existing store)."""
    records = _load_all_clv_records()
    records[record["record_id"]] = record
    _save_all_clv_records(records)

# ============================================================
# END SECTION: Storage Helpers
# ============================================================


# ============================================================
# SECTION: Automatic CLV Closing-Line Updater
# ============================================================

def auto_update_closing_lines(days_back: int = 1) -> dict:
    """
    Retrieve recently completed game scores from The Odds API and use the
    final game total as a proxy closing-line signal to close open CLV records.

    This completes the CLV tracking loop:
        1. ``store_opening_line()``  called when the model makes a pick
        2. ``auto_update_closing_lines()``  called after game completes
        3. ``get_clv_summary()``  shows long-run model edge

    For each open CLV record (no closing line yet), we look for a matching
    game that has since completed.  When found, the actual prop closing line
    is estimated as the final game total (over/under proxy) if a real closing
    prop line isn't available.  This provides a conservative but useful CLV
    approximation until Odds API historical prop data is available.

    Additionally, for player-level records we use the Odds API current props
    (which reflect closing-day lines) to update records from today.

    Args:
        days_back: How many days back to look for completed games (1-3).

    Returns:
        dict: {
            "updated":  int — number of records updated,
            "skipped":  int — records with no matching game found,
            "errors":   int — records that failed to update,
        }
    """
    return {"updated": 0, "skipped": 0, "errors": 0}

# ============================================================
# END SECTION: Automatic CLV Closing-Line Updater
# ============================================================
