# ============================================================
# FILE: tracking/joseph_diary.py
# PURPOSE: Joseph's persistent memory — "Joseph's Diary"
#          Stores his daily takes, wins/losses, and narrative arc
#          across sessions so he can reference yesterday's calls.
# CONNECTS TO: tracking/database.py, engine/joseph_bets.py
# ============================================================

import json
import os
import datetime
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# Optional DB layer — used when available (SQLite or Railway PostgreSQL)
try:
    from tracking.database import (
        save_joseph_diary_entry as _db_save_diary,
        load_joseph_diary_entry as _db_load_diary_entry,
        load_joseph_full_diary as _db_load_full_diary,
    )
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


# ── Diary file location ──────────────────────────────────────
_DIARY_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__)))
_DIARY_FILE = os.path.join(_DIARY_DIR, "joseph_diary.json")


def _load_diary() -> dict:
    """Load the full diary.

    Tries the DB layer first; falls back to the JSON file on disk.
    """
    if _DB_AVAILABLE:
        try:
            db_data = _db_load_full_diary()
            if db_data:
                return db_data
        except Exception as exc:
            _logger.debug("joseph_diary: DB full-load failed, using file — %s", exc)
    # File fallback
    try:
        if os.path.isfile(_DIARY_FILE):
            with open(_DIARY_FILE, "r") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
    except Exception as exc:
        _logger.debug("joseph_diary: file load error — %s", exc)
    return {}


def _save_diary(data: dict) -> bool:
    """Persist the full diary dict.

    Writes to both the DB layer and the JSON file for redundancy.
    """
    success = False
    if _DB_AVAILABLE:
        try:
            for date_key, entry in data.items():
                _db_save_diary(date_key, entry)
            success = True
        except Exception as exc:
            _logger.debug("joseph_diary: DB full-save failed — %s", exc)
    # Always mirror to file as backup
    try:
        with open(_DIARY_FILE, "w") as fh:
            json.dump(data, fh, indent=2, default=str)
        success = True
    except Exception as exc:
        _logger.warning("joseph_diary: file save error — %s", exc)
    return success


# ── Public API ────────────────────────────────────────────────

def diary_log_entry(date_str: str = None, entry: dict = None) -> bool:
    """Log a diary entry for the given date.

    Parameters
    ----------
    date_str : str or None
        ISO date string (e.g. ``"2026-04-08"``). Defaults to today.
    entry : dict
        Diary entry with keys like ``wins``, ``losses``, ``picks``,
        ``hot_takes``, ``mood``, ``narrative``.

    Returns
    -------
    bool — True if saved successfully.
    """
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    if entry is None:
        entry = {}

    diary = _load_diary()
    if "entries" not in diary:
        diary["entries"] = {}
    entry_data = {
        "date": date_str,
        "wins": entry.get("wins", 0),
        "losses": entry.get("losses", 0),
        "picks": entry.get("picks", []),
        "hot_takes": entry.get("hot_takes", []),
        "mood": entry.get("mood", "neutral"),
        "narrative": entry.get("narrative", ""),
        "timestamp": datetime.datetime.now().isoformat(),
    }
    diary["entries"][date_str] = entry_data

    # Fast path: write single entry directly to DB when available
    if _DB_AVAILABLE:
        try:
            _db_save_diary(date_str, entry_data)
        except Exception as exc:
            _logger.debug("joseph_diary: DB single-entry save failed — %s", exc)

    # Mirror full diary to file
    try:
        with open(_DIARY_FILE, "w") as fh:
            json.dump(diary, fh, indent=2, default=str)
        return True
    except Exception as exc:
        _logger.warning("joseph_diary: file save error — %s", exc)
        return False


def diary_get_entry(date_str: str = None) -> dict:
    """Get the diary entry for a specific date.

    Parameters
    ----------
    date_str : str or None
        ISO date string. Defaults to today.

    Returns
    -------
    dict — The diary entry, or empty dict if none exists.
    """
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    diary = _load_diary()
    return diary.get("entries", {}).get(date_str, {})


def diary_get_yesterday() -> dict:
    """Get yesterday's diary entry."""
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    return diary_get_entry(yesterday)


def diary_get_week_summary() -> dict:
    """Get the win/loss record and narrative arc for the current week.

    Joseph starts Monday humble, gets arrogant by Friday on a hot streak.

    Returns
    -------
    dict
        ``week_wins``, ``week_losses``, ``week_record``,
        ``streak``, ``narrative_arc``, ``brag_intensity`` (0-100).
    """
    diary = _load_diary()
    entries = diary.get("entries", {})

    today = datetime.date.today()
    # Start of week = Monday
    monday = today - datetime.timedelta(days=today.weekday())

    week_wins = 0
    week_losses = 0
    streak = 0
    last_result = None

    for i in range(7):
        day = (monday + datetime.timedelta(days=i)).isoformat()
        entry = entries.get(day, {})
        w = entry.get("wins", 0)
        l = entry.get("losses", 0)
        week_wins += w
        week_losses += l

        if w > l:
            if last_result == "win":
                streak += 1
            else:
                streak = 1
                last_result = "win"
        elif l > w:
            if last_result == "loss":
                streak -= 1
            else:
                streak = -1
                last_result = "loss"

    total = week_wins + week_losses
    win_rate = week_wins / max(total, 1)

    # Brag intensity: scales with wins and day-of-week
    # Monday = humble (max 30), Friday = arrogant (max 100)
    day_of_week = today.weekday()  # 0=Mon, 4=Fri
    day_multiplier = 0.4 + (day_of_week / 4.0) * 0.6  # 0.4 on Mon, 1.0 on Fri
    raw_brag = win_rate * 100.0 * day_multiplier
    brag_intensity = max(0.0, min(100.0, raw_brag))

    # Narrative arc
    if brag_intensity >= 80:
        arc = "PEAK_ARROGANCE"
        narrative = "Joseph is on an ABSOLUTE HEATER and he will NOT let you forget it."
    elif brag_intensity >= 60:
        arc = "CONFIDENT"
        narrative = "The week is going WELL and Joseph's swagger is building."
    elif brag_intensity >= 40:
        arc = "STEADY"
        narrative = "Joseph is grinding — wins and losses, but staying the course."
    elif brag_intensity >= 20:
        arc = "HUMBLE"
        narrative = "Joseph is keeping it low-key early in the week. The fire builds later."
    else:
        arc = "REFLECTIVE"
        narrative = "Tough stretch. Joseph is regrouping and recalibrating."

    return {
        "week_wins": week_wins,
        "week_losses": week_losses,
        "week_record": f"{week_wins}-{week_losses}",
        "streak": streak,
        "narrative_arc": arc,
        "narrative": narrative,
        "brag_intensity": round(brag_intensity, 1),
        "win_rate": round(win_rate, 3),
    }


def diary_get_yesterday_reference() -> str:
    """Generate a self-referential line about yesterday's performance.

    If Joseph was wrong yesterday, he references it today with either
    a redemption narrative or a defensive excuse.

    Returns
    -------
    str — A self-referential line, or empty string if no yesterday data.
    """
    yesterday = diary_get_yesterday()
    if not yesterday:
        return ""

    wins = yesterday.get("wins", 0)
    losses = yesterday.get("losses", 0)

    if wins == 0 and losses == 0:
        return ""

    if wins > losses:
        lines = [
            f"Yesterday I went {wins}-{losses}. That's what EXCELLENCE looks like.",
            f"Another winning day yesterday ({wins}-{losses}). The streak CONTINUES.",
            f"If you followed me yesterday, you're UP. {wins} wins, {losses} losses. You're WELCOME.",
        ]
    elif losses > wins:
        lines = [
            f"Yesterday was {wins}-{losses}. A ROUGH night — but the process was SOUND.",
            f"Look, yesterday didn't go our way ({wins}-{losses}). But EVERY great analyst has off nights.",
            f"Yesterday's {wins}-{losses}? The right calls at the WRONG time. Today we BOUNCE BACK.",
        ]
    else:
        lines = [
            f"Yesterday was a wash at {wins}-{losses}. Today we SEPARATE ourselves.",
            f"Split day yesterday ({wins}-{losses}). Not bad, not great. Today we go ALL IN.",
        ]

    import random
    return random.choice(lines)


def diary_update_from_track_record(track_record: dict) -> bool:
    """Update today's diary entry from the track record data.

    Parameters
    ----------
    track_record : dict
        From ``joseph_get_track_record()`` — has ``wins``, ``losses``, etc.

    Returns
    -------
    bool — True if saved successfully.
    """
    win_rate = track_record.get("win_rate", 0)
    if win_rate > 0.6:
        mood = "hot"
    elif win_rate < 0.4:
        mood = "cold"
    else:
        mood = "neutral"
    return diary_log_entry(entry={
        "wins": track_record.get("wins", 0),
        "losses": track_record.get("losses", 0),
        "mood": mood,
    })
