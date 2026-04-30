# ============================================================
# FILE: engine/calibration.py
# PURPOSE: Historical Calibration Engine (C10)
#          Loads historical bet results from the tracking database,
#          computes calibration curves (predicted probability vs actual
#          hit rate), and exports a get_calibration_adjustment() function.
#
#          If model says 70% but actual hit rate is 62%, this module
#          provides a calibration offset to apply to the confidence score.
#
#          Cold start: if no historical data exists yet, returns 0 adjustment.
#
# CONNECTS TO: tracking/database.py (historical results)
# CONCEPTS COVERED: Probability calibration, expected vs actual,
#                   reliability diagrams, calibration offset
# ============================================================

import math

from engine.math_helpers import _safe_float


# ============================================================
# SECTION: Calibration Constants
# ============================================================

# Minimum number of historical bets in a probability bucket before
# we trust the calibration estimate (otherwise cold start applies).
MIN_BETS_FOR_CALIBRATION = 20

# Probability bucket width for building the calibration curve.
# 0.10 = 10% buckets: [0.50-0.60), [0.60-0.70), [0.70-0.80), etc.
CALIBRATION_BUCKET_WIDTH = 0.10

# Maximum adjustment magnitude in confidence score points.
# Caps adjustments to avoid over-correcting on small samples.
# Increased from 10 to 15 for severely miscalibrated stat types.
MAX_CALIBRATION_ADJUSTMENT = 15.0

# Per-stat type cap: use a tighter cap for well-calibrated stats
# (points tends to be well-calibrated; blocks/steals may be worse)
STAT_TYPE_CALIBRATION_CAPS = {
    "points":    10.0,   # Well-calibrated — tighter cap
    "rebounds":  12.0,
    "assists":   12.0,
    "threes":    15.0,   # Highly variable — allow larger correction (binary penalty also applied)
    "fg3m":      15.0,   # alias for threes
    "steals":    15.0,   # Low-frequency, high-CV — allow larger correction
    "stl":       15.0,   # alias for steals
    "blocks":    15.0,
    "turnovers": 12.0,
}

# Fine-grained calibration bucket width for isotonic method.
# 0.05 = 5% buckets: [0.50-0.55), [0.55-0.60), ... [0.95-1.00)
FINE_CALIBRATION_BUCKET_WIDTH = 0.05

# Minimum records per fine bucket before using isotonic method;
# below this threshold falls back to coarse (10%) calibration.
MIN_RECORDS_FINE_BUCKET = 10

# Minimum total records before switching to isotonic calibration.
# Below this, always use the existing coarse method.
MIN_TOTAL_FOR_ISOTONIC = 200

# ============================================================
# END SECTION: Calibration Constants
# ============================================================


# ============================================================
# SECTION: Calibration Data Loading
# ============================================================

def _get_bucket_midpoint(prob, bucket_width):
    """
    Return the bucket midpoint for a given probability and bucket width.

    Args:
        prob (float): Probability value (0-1), already clamped to valid range.
        bucket_width (float): Width of each calibration bucket.

    Returns:
        float: Midpoint of the bucket containing prob.
    """
    bucket_idx = math.floor(prob / bucket_width) * bucket_width
    return round(bucket_idx + bucket_width / 2.0, 4)


def _load_historical_predictions(days=90, stat_type=None):
    """
    Load historical prediction records from the tracking database.

    Now supports filtering by stat_type for per-stat calibration curves.
    Applies exponential recency weighting: predictions from the last 30 days
    are duplicated (given 2x weight) vs older records.

    Args:
        days (int): Number of past days to include. Default 90.
        stat_type (str or None): If provided, only return records for this
            stat type (e.g. 'points', 'blocks'). None returns all stats.

    Returns:
        list of dict: Prediction records (with recency weighting applied).
            Each record has: 'probability_over', 'result', optionally 'stat_type', 'date'.
        Empty list on cold start or database errors.
    """
    try:
        from tracking.database import load_recent_predictions
        records = load_recent_predictions(days=days)
        # Filter to records with both probability and result
        records = [
            r for r in (records or [])
            if r.get("probability_over") is not None
            and r.get("result") is not None
        ]

        # Filter by stat type if requested
        if stat_type:
            stat_lower = stat_type.lower()
            records = [
                r for r in records
                if (r.get("stat_type") or "").lower() == stat_lower
            ]

        # Apply recency weighting: duplicate records from last 30 days
        # BEGINNER NOTE: More recent data is more representative of current
        # model performance. We give it 2x weight by duplicating recent records.
        weighted_records = []
        for r in records:
            weighted_records.append(r)
            # Check if record is recent (last 30 days)
            record_date = r.get("date", r.get("created_at", ""))
            if record_date:
                try:
                    from datetime import date as _date, timedelta
                    import datetime as _dt
                    if isinstance(record_date, str) and len(record_date) >= 10:
                        record_date_parsed = _dt.datetime.strptime(record_date[:10], "%Y-%m-%d").date()
                    elif not isinstance(record_date, str):
                        record_date_parsed = record_date
                    else:
                        record_date_parsed = None
                    if record_date_parsed is not None:
                        cutoff = _date.today() - timedelta(days=30)
                        if record_date_parsed >= cutoff:
                            weighted_records.append(r)   # 2x weight for recent records
                except (ValueError, TypeError, AttributeError):
                    pass

        return weighted_records
    except Exception:
        return []


def _build_calibration_curve(records):
    """
    Build a calibration curve from historical prediction records.

    Groups predictions into probability buckets and computes the actual
    hit rate within each bucket.

    Args:
        records (list of dict): Historical prediction records.

    Returns:
        dict: {bucket_midpoint: {'predicted': float, 'actual': float, 'count': int}}
        Empty dict if insufficient data.
    """
    if not records:
        return {}

    # Initialize buckets: [0.50-0.60), [0.60-0.70), ..., [0.90-1.00)
    buckets = {}
    for b in range(5, 10):  # b=5 → [0.50-0.60), ..., b=9 → [0.90-1.00)
        low = b * CALIBRATION_BUCKET_WIDTH
        mid = round(low + CALIBRATION_BUCKET_WIDTH / 2.0, 3)
        buckets[mid] = {"predicted": mid, "actual_sum": 0, "count": 0}

    # Fill buckets
    for record in records:
        prob = float(record.get("probability_over", 0.5) or 0.5)
        result = int(record.get("result", 0) or 0)

        # Normalize probability to [0.5, 1.0) — we only track high-confidence picks
        prob = max(0.5, min(0.999, prob))

        # Find the bucket
        mid = _get_bucket_midpoint(prob, CALIBRATION_BUCKET_WIDTH)

        if mid in buckets:
            buckets[mid]["actual_sum"] += result
            buckets[mid]["count"] += 1

    # Compute actual hit rates
    curve = {}
    for mid, data in buckets.items():
        if data["count"] >= MIN_BETS_FOR_CALIBRATION:
            curve[mid] = {
                "predicted": data["predicted"],
                "actual": data["actual_sum"] / data["count"],
                "count": data["count"],
            }

    return curve


# ============================================================
# END SECTION: Calibration Data Loading
# ============================================================


# ============================================================
# SECTION: Isotonic Calibration (Fine-Grained, PAVA Smoothed)
# ============================================================

def _build_fine_calibration_curve(records):
    """
    Build a fine-grained calibration curve using 5% probability buckets.

    Same structure as _build_calibration_curve but uses FINE_CALIBRATION_BUCKET_WIDTH
    (0.05) instead of the coarse 0.10 width, yielding more precise calibration when
    sufficient data is available.

    Args:
        records (list of dict): Historical prediction records with 'probability_over'
            and 'result' keys.

    Returns:
        dict: {bucket_midpoint: {'predicted': float, 'actual': float, 'count': int}}
            Buckets with fewer than MIN_RECORDS_FINE_BUCKET records are excluded.
            Returns empty dict if no records provided.

    Example:
        curve = _build_fine_calibration_curve(records)
        # curve[0.525] → {'predicted': 0.525, 'actual': 0.51, 'count': 42}
    """
    if not records:
        return {}

    # Build 5% buckets from [0.50, 1.00) → midpoints at 0.525, 0.575, ..., 0.975
    buckets = {}
    bucket_count = int(round((1.0 - 0.5) / FINE_CALIBRATION_BUCKET_WIDTH))
    for i in range(bucket_count):
        low = 0.5 + i * FINE_CALIBRATION_BUCKET_WIDTH
        mid = round(low + FINE_CALIBRATION_BUCKET_WIDTH / 2.0, 4)
        buckets[mid] = {"predicted": mid, "actual_sum": 0, "count": 0}

    # Distribute records into buckets
    for record in records:
        prob = float(record.get("probability_over", 0.5) or 0.5)
        result = int(record.get("result", 0) or 0)
        prob = max(0.5, min(0.9999, prob))

        mid = _get_bucket_midpoint(prob, FINE_CALIBRATION_BUCKET_WIDTH)

        if mid in buckets:
            buckets[mid]["actual_sum"] += result
            buckets[mid]["count"] += 1

    # Only keep buckets with enough data for a reliable estimate
    curve = {}
    for mid, data in buckets.items():
        if data["count"] >= MIN_RECORDS_FINE_BUCKET:
            curve[mid] = {
                "predicted": data["predicted"],
                "actual": data["actual_sum"] / data["count"],
                "count": data["count"],
            }

    return curve


def _apply_monotonic_smoothing(curve):
    """
    Apply isotonic / PAVA-style monotonic smoothing to a calibration curve.

    Ensures calibrated probabilities are non-decreasing as predicted probability
    increases.  Without smoothing, sample noise can produce absurd inversions
    where the 70% bucket has a lower actual hit rate than the 65% bucket.

    Algorithm — Pool Adjacent Violators (PAVA):
        1. Sort all buckets by predicted probability (ascending).
        2. Scan left-to-right; when actual[i] > actual[i+1], merge those two
           groups and replace both with the count-weighted average actual rate.
        3. Repeat until no violations remain (one full pass suffices for PAVA).

    Args:
        curve (dict): Output from _build_fine_calibration_curve.
            Keys are bucket midpoints, values are dicts with 'predicted',
            'actual', and 'count'.

    Returns:
        dict: Same structure with smoothed 'actual' values.
            Returns an empty dict if curve is empty.

    Example:
        smoothed = _apply_monotonic_smoothing(curve)
        # Guaranteed: smoothed[0.575]['actual'] <= smoothed[0.625]['actual']
    """
    if not curve:
        return {}

    # Work on a sorted list of (midpoint, data) pairs so PAVA is straightforward
    sorted_keys = sorted(curve.keys())
    groups = []
    for k in sorted_keys:
        groups.append({
            "predicted": curve[k]["predicted"],
            "actual": curve[k]["actual"],
            "count": curve[k]["count"],
            "keys": [k],
        })

    # PAVA: merge adjacent groups that violate monotonicity
    changed = True
    while changed:
        changed = False
        new_groups = []
        i = 0
        while i < len(groups):
            if i + 1 < len(groups) and groups[i]["actual"] > groups[i + 1]["actual"]:
                # Violation: merge groups[i] and groups[i+1]
                merged_count = groups[i]["count"] + groups[i + 1]["count"]
                merged_actual = (
                    groups[i]["actual"] * groups[i]["count"]
                    + groups[i + 1]["actual"] * groups[i + 1]["count"]
                ) / merged_count
                merged_group = {
                    "predicted": groups[i]["predicted"],  # keep lower anchor
                    "actual": merged_actual,
                    "count": merged_count,
                    "keys": groups[i]["keys"] + groups[i + 1]["keys"],
                }
                new_groups.append(merged_group)
                i += 2
                changed = True
            else:
                new_groups.append(groups[i])
                i += 1
        groups = new_groups

    # Rebuild curve dict: every original key gets the smoothed actual of its group
    smoothed_curve = {}
    for group in groups:
        for k in group["keys"]:
            smoothed_curve[k] = {
                "predicted": curve[k]["predicted"],
                "actual": group["actual"],
                "count": curve[k]["count"],
            }

    return smoothed_curve


def isotonic_calibrate(raw_probability, historical_records):
    """
    Return a calibrated probability using isotonic (5% bucket) calibration.

    Uses fine-grained 5% buckets with monotonic smoothing via PAVA.
    Falls back to coarse 10% calibration when fewer than MIN_RECORDS_FINE_BUCKET
    records exist in the relevant fine bucket.

    Args:
        raw_probability (float): The model's raw predicted P(over), 0-1.
        historical_records (list of dict): Records with 'probability_over' and 'result'.

    Returns:
        float: Calibrated probability (0.0-1.0).

    Example:
        Model says 0.72 but in history 72% bucket only hits 65%:
        → isotonic_calibrate(0.72, records) returns ~0.65
    """
    try:
        prob = max(0.5, min(0.9999, float(raw_probability)))

        # Build fine curve and apply monotonic smoothing
        fine_curve = _build_fine_calibration_curve(historical_records)
        if fine_curve:
            smoothed = _apply_monotonic_smoothing(fine_curve)
        else:
            smoothed = {}

        # Find the 5% bucket for this probability
        mid = _get_bucket_midpoint(prob, FINE_CALIBRATION_BUCKET_WIDTH)

        bucket_data = smoothed.get(mid)
        if bucket_data is not None:
            return round(bucket_data["actual"], 6)

        # Fine bucket not found — fall back to coarse calibration
        coarse_curve = _build_calibration_curve(historical_records)
        coarse_mid = _get_bucket_midpoint(prob, CALIBRATION_BUCKET_WIDTH)
        coarse_data = coarse_curve.get(coarse_mid)
        if coarse_data is not None:
            return round(coarse_data["actual"], 6)

        # No calibration data at all — return raw probability unchanged
        return round(prob, 6)

    except Exception:
        return round(float(raw_probability), 6)


def get_isotonic_calibration_curve(days=90):
    """
    Return the full isotonic calibration curve for display on the Model Health page.

    Args:
        days (int): Days of history to include. Default 90.

    Returns:
        dict: {
            'has_data': bool,
            'curve': list of {
                'predicted': float,
                'actual': float,
                'count': int,
                'gap': float,  # actual - predicted (positive = underconfident)
            },
            'is_isotonic': bool,  # True if PAVA smoothing was applied
            'total_records': int,
        }

    Example:
        curve = get_isotonic_calibration_curve()
        for pt in curve['curve']:
            print(f"{pt['predicted']:.0%} predicted → {pt['actual']:.0%} actual")
    """
    try:
        records = _load_historical_predictions(days=days)
        total_records = len(records)

        if not records:
            return {"has_data": False, "curve": [], "is_isotonic": False, "total_records": 0}

        fine_curve = _build_fine_calibration_curve(records)
        is_isotonic = bool(fine_curve)

        if is_isotonic:
            smoothed = _apply_monotonic_smoothing(fine_curve)
            source_curve = smoothed
        else:
            # Not enough data for fine buckets — use coarse curve
            source_curve = _build_calibration_curve(records)

        if not source_curve:
            return {"has_data": False, "curve": [], "is_isotonic": False, "total_records": total_records}

        curve_list = []
        for mid in sorted(source_curve.keys()):
            data = source_curve[mid]
            curve_list.append({
                "predicted": _safe_float(data["predicted"], 0.5),
                "actual": _safe_float(round(data["actual"], 4), 0.5),
                "count": data["count"],
                "gap": _safe_float(round(data["actual"] - data["predicted"], 4), 0.0),
            })

        return {
            "has_data": True,
            "curve": curve_list,
            "is_isotonic": is_isotonic,
            "total_records": total_records,
        }

    except Exception:
        return {"has_data": False, "curve": [], "is_isotonic": False, "total_records": 0}


# ============================================================
# END SECTION: Isotonic Calibration (Fine-Grained, PAVA Smoothed)
# ============================================================


# ============================================================
# SECTION: Calibration Adjustment Function
# ============================================================

def get_calibration_adjustment(raw_probability, days=90, stat_type=None):
    """
    Compute the calibration adjustment for a given raw probability. (C10)

    Compares the model's predicted probability to the historical hit rate
    at that probability level. Returns an offset in confidence score points
    to subtract (positive adjustment = model overestimates confidence).

    Now supports stat-type-specific calibration curves — blocks/steals may
    be poorly calibrated while points/rebounds are well-calibrated. Per-stat
    calibration curves catch these differences.

    Cold start behavior:
        If fewer than MIN_BETS_FOR_CALIBRATION bets exist for the relevant
        probability bucket, returns 0.0 (no adjustment applied).

    Args:
        raw_probability (float): The model's predicted P(over), 0-1.
        days (int): Days of historical data to consider. Default 90.
        stat_type (str or None): Stat type for per-stat calibration.
            If None, uses all historical data (global calibration).

    Returns:
        float: Calibration offset in confidence score points.
            Positive = model is overconfident → reduce score.
            Negative = model is underconfident → increase score.
            0.0 if insufficient historical data (cold start).

    Example:
        Model says 70% → historical hit rate at that bucket is 62%
        → calibration gap = 8% → adjustment = +4.0 pts (reduce confidence)
    """
    try:
        # Per-stat calibration cap
        _stat_cap = STAT_TYPE_CALIBRATION_CAPS.get(
            (stat_type or "").lower(), MAX_CALIBRATION_ADJUSTMENT
        )

        # Try stat-specific records first; fall back to all records
        records = _load_historical_predictions(days=days, stat_type=stat_type)
        if not records:
            records = _load_historical_predictions(days=days)
        if not records:
            return 0.0  # Cold start: no historical data

        # ── Isotonic path: use fine-grained PAVA calibration when enough data ──
        if len(records) >= MIN_TOTAL_FOR_ISOTONIC:
            calibrated_prob = isotonic_calibrate(raw_probability, records)
            raw = max(0.5, min(0.9999, float(raw_probability)))
            # Convert probability difference to confidence-score points (same scale)
            adjustment = (raw - calibrated_prob) * 100.0
            adjustment = max(-_stat_cap, min(_stat_cap, adjustment))
            return _safe_float(round(adjustment, 2), 0.0)

        # ── Coarse fallback: original 10% bucket logic ──
        curve = _build_calibration_curve(records)
        if not curve:
            return 0.0  # Insufficient data in all buckets

        # Find the bucket for this probability
        prob = max(0.5, min(0.999, float(raw_probability)))
        mid = _get_bucket_midpoint(prob, CALIBRATION_BUCKET_WIDTH)

        bucket_data = curve.get(mid)
        if bucket_data is None:
            return 0.0  # No calibration data for this bucket

        predicted = bucket_data["predicted"]
        actual = bucket_data["actual"]

        # Calibration gap: positive = model overestimates
        calibration_gap = predicted - actual

        # Convert probability gap to score adjustment
        # A 10% calibration gap maps to roughly 5 confidence score points
        adjustment = calibration_gap * 50.0  # 0.10 gap → 5 pts

        # Cap the adjustment using per-stat cap
        adjustment = max(-_stat_cap, min(_stat_cap, adjustment))

        return _safe_float(round(adjustment, 2), 0.0)

    except Exception:
        return 0.0  # Always safe to return 0 on any error


def get_calibration_summary(days=90):
    """
    Return a summary of calibration statistics for the Model Health page.

    Args:
        days (int): Days of historical data to consider.

    Returns:
        dict: {
            'has_data': bool,
            'total_bets': int,
            'calibration_curve': dict,
            'overall_accuracy': float or None,
            'overconfidence_buckets': list of float (midpoints that are overconfident),
        }
    """
    try:
        records = _load_historical_predictions(days=days)
        if not records:
            return {"has_data": False, "total_bets": 0, "calibration_curve": {},
                    "overall_accuracy": None, "overconfidence_buckets": []}

        curve = _build_calibration_curve(records)

        total = len(records)
        hits = sum(int(r.get("result", 0) or 0) for r in records)
        overall_accuracy = hits / total if total > 0 else None

        overconfident = [
            mid for mid, data in curve.items()
            if data["predicted"] > data["actual"] + 0.05  # 5%+ overconfident
        ]

        return {
            "has_data": bool(curve),
            "total_bets": total,
            "calibration_curve": curve,
            "overall_accuracy": _safe_float(round(overall_accuracy, 4), None) if overall_accuracy else None,
            "overconfidence_buckets": overconfident,
        }
    except Exception:
        return {"has_data": False, "total_bets": 0, "calibration_curve": {},
                "overall_accuracy": None, "overconfidence_buckets": []}

# ============================================================
# END SECTION: Calibration Adjustment Function
# ============================================================
