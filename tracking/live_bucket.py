"""
tracking/live_bucket.py
───────────────────────
CRUD layer for the per-user "Live Entry Bucket" — picks staged from the
Quantum Analysis Matrix (QAM) into a personal review bucket before
they get sent to the Entry Builder and locked into the user's tracked
bets.

Persists in the `live_entry_bucket` table (created in
`tracking/database.py`) so picks survive page refreshes and Railway
redeploys per user.

Public API
──────────
    add_to_bucket(user_email, pick_dict)  -> bucket_id|None
    remove_from_bucket(user_email, pick_key) -> bool
    remove_bucket_id(bucket_id)              -> bool
    get_bucket(user_email)                   -> list[dict]
    bucket_count(user_email)                 -> int
    clear_bucket(user_email)                 -> int
    pick_to_selected_format(bucket_row)      -> dict   (Entry Builder shape)
"""

from __future__ import annotations

import json
import logging
from typing import Iterable

from tracking.database import (
    initialize_database,
    _db_read,
    _db_write,
    _DATABASE_URL,
    _nba_today_iso,
    purge_stale_bucket_rows,
)

_logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _norm_email(user_email: str) -> str:
    return str(user_email or "").strip().lower()


def _build_pick_key(pick: dict) -> str:
    """Stable de-dupe key for a pick (per platform / line / direction)."""
    explicit = str(pick.get("key", "") or "").strip()
    if explicit:
        return explicit
    parts = [
        str(pick.get("player_name", "")).strip().lower(),
        str(pick.get("stat_type", "")).strip().lower(),
        str(pick.get("prop_line", pick.get("line", ""))).strip(),
        str(pick.get("direction", "")).strip().upper(),
        str(pick.get("platform", "")).strip().lower(),
    ]
    return "|".join(parts)


def _coerce_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ────────────────────────────────────────────────────────────────────
# Mutations
# ────────────────────────────────────────────────────────────────────

def add_to_bucket(user_email: str, pick: dict) -> int | None:
    """Insert pick into this user's bucket.  Returns bucket_id, or
    None on failure / duplicate."""
    initialize_database()
    email = _norm_email(user_email)
    if not email or not pick:
        return None

    pick_key = _build_pick_key(pick)
    line_val = _coerce_float(pick.get("prop_line", pick.get("line", 0.0)))
    direction = str(pick.get("direction", "OVER")).strip().upper()

    game_date = _nba_today_iso()

    insert_sql = """
        INSERT INTO live_entry_bucket
            (user_email, pick_key, player_name, team, stat_type, prop_line,
             direction, platform, tier, tier_emoji, confidence_score,
             probability_over, edge_percentage, bet_type, odds_type, game_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        email,
        pick_key,
        str(pick.get("player_name", "")).strip(),
        str(pick.get("team", "") or ""),
        str(pick.get("stat_type", "")).strip(),
        line_val,
        direction,
        str(pick.get("platform", "") or ""),
        str(pick.get("tier", "") or ""),
        str(pick.get("tier_emoji", "") or ""),
        _coerce_float(pick.get("confidence_score", 0.0)),
        _coerce_float(pick.get("probability_over", 0.0)),
        _coerce_float(pick.get("edge_percentage", 0.0)),
        str(pick.get("bet_type", "normal") or "normal"),
        str(pick.get("odds_type", "standard") or "standard"),
        game_date,
    )

    try:
        cursor = _db_write(insert_sql, values, caller="bucket_add")
        if cursor is None:
            return None
        return getattr(cursor, "lastrowid", None) or -1
    except Exception as exc:
        # Duplicate (unique constraint on user_email + pick_key) is fine
        _logger.debug("add_to_bucket: %s", exc)
        return None


def add_many_to_bucket(user_email: str, picks: Iterable[dict]) -> int:
    """Bulk-add picks; returns count of successful inserts (skipping
    duplicates)."""
    inserted = 0
    for p in picks or []:
        if add_to_bucket(user_email, p):
            inserted += 1
    return inserted


def remove_from_bucket(user_email: str, pick_key: str) -> bool:
    """Remove a pick from a user's bucket by pick_key."""
    initialize_database()
    email = _norm_email(user_email)
    if not email or not pick_key:
        return False
    cursor = _db_write(
        "DELETE FROM live_entry_bucket WHERE user_email = ? AND pick_key = ?",
        (email, str(pick_key)),
        caller="bucket_remove_key",
    )
    return cursor is not None and getattr(cursor, "rowcount", 0) > 0


def remove_bucket_id(bucket_id: int) -> bool:
    """Remove a single bucket row by ID."""
    initialize_database()
    try:
        bid = int(bucket_id)
    except (TypeError, ValueError):
        return False
    cursor = _db_write(
        "DELETE FROM live_entry_bucket WHERE bucket_id = ?",
        (bid,),
        caller="bucket_remove_id",
    )
    return cursor is not None and getattr(cursor, "rowcount", 0) > 0


def clear_bucket(user_email: str) -> int:
    """Empty a user's bucket. Returns rows deleted."""
    initialize_database()
    email = _norm_email(user_email)
    if not email:
        return 0
    cursor = _db_write(
        "DELETE FROM live_entry_bucket WHERE user_email = ?",
        (email,),
        caller="bucket_clear",
    )
    return getattr(cursor, "rowcount", 0) if cursor else 0


# ────────────────────────────────────────────────────────────────────
# Reads
# ────────────────────────────────────────────────────────────────────

def get_bucket(user_email: str, game_date: str | None = None) -> list[dict]:
    """Return the user's staged picks for the given date, newest first.

    Args:
        user_email: The authenticated user's e-mail address.
        game_date:  ISO-8601 date string (``"YYYY-MM-DD"``).  Defaults to
                    today's NBA ET date (see ``_nba_today_iso()``) so that
                    stale prior-day picks are never surfaced by default.
    """
    initialize_database()
    email = _norm_email(user_email)
    if not email:
        return []
    target_date = str(game_date).strip() if game_date else _nba_today_iso()
    return _db_read(
        "SELECT * FROM live_entry_bucket WHERE user_email = ? AND game_date = ? "
        "ORDER BY added_at DESC, bucket_id DESC",
        (email, target_date),
    )


def bucket_count(user_email: str) -> int:
    """Quick count of today's picks in this user's bucket."""
    email = _norm_email(user_email)
    if not email:
        return 0
    today = _nba_today_iso()
    rows = _db_read(
        "SELECT COUNT(*) AS n FROM live_entry_bucket WHERE user_email = ? AND game_date = ?",
        (email, today),
    )
    if not rows:
        return 0
    row = rows[0]
    return int(row.get("n") or list(row.values())[0] or 0)


# ────────────────────────────────────────────────────────────────────
# Conversion helpers
# ────────────────────────────────────────────────────────────────────

def pick_to_selected_format(bucket_row: dict) -> dict:
    """Convert a bucket DB row into the dict shape used by
    `st.session_state["selected_picks"]` and the Entry Builder.

    ``pick_date`` is explicitly set to today's ET date so the Entry
    Builder's date-boundary filter never accidentally drops these picks.
    """
    if not bucket_row:
        return {}
    return {
        "key": bucket_row.get("pick_key", ""),
        "player_name": bucket_row.get("player_name", ""),
        "team": bucket_row.get("team", ""),
        "stat_type": bucket_row.get("stat_type", ""),
        "line": _coerce_float(bucket_row.get("prop_line", 0.0)),
        "prop_line": _coerce_float(bucket_row.get("prop_line", 0.0)),
        "direction": bucket_row.get("direction", "OVER"),
        "platform": bucket_row.get("platform", ""),
        "tier": bucket_row.get("tier", ""),
        "tier_emoji": bucket_row.get("tier_emoji", ""),
        "confidence_score": _coerce_float(bucket_row.get("confidence_score", 0.0)),
        "probability_over": _coerce_float(bucket_row.get("probability_over", 0.0)),
        "edge_percentage": _coerce_float(bucket_row.get("edge_percentage", 0.0)),
        "bet_type": bucket_row.get("bet_type", "normal"),
        "odds_type": bucket_row.get("odds_type", "standard"),
        # pick_date must match today's ET date so Entry Builder date filter
        # never discards bucket-promoted picks (see pages/8_🧬_Entry_Builder.py).
        "pick_date": bucket_row.get("game_date") or _nba_today_iso(),
        "_from_bucket": True,
        "_bucket_id": bucket_row.get("bucket_id"),
    }


def get_bucket_as_selected_picks(user_email: str) -> list[dict]:
    """Return the user's bucket already shaped for the Entry Builder."""
    return [pick_to_selected_format(row) for row in get_bucket(user_email)]


# ────────────────────────────────────────────────────────────────────
# Maintenance helpers
# ────────────────────────────────────────────────────────────────────

def purge_non_playing_players(inactive_player_names: set[str]) -> int:
    """Remove all bucket rows for players who are not playing today.

    Called by ``slate_worker`` (Step 6e) after each analysis run so
    that late scratches, Doubtful players, and Out/IR players can never
    linger in a user's staged bucket.

    Args:
        inactive_player_names: Lowercase-normalised set of player names
            whose status is Out / IR / Doubtful / Suspended / G-League
            (built from the injury_map in slate_worker Step 2b).

    Returns:
        Total number of rows deleted across all users.
    """
    if not inactive_player_names:
        return 0

    initialize_database()
    total_deleted = 0
    for raw_name in inactive_player_names:
        name_lower = str(raw_name or "").strip().lower()
        if not name_lower:
            continue
        try:
            # Match case-insensitively; SQLite LOWER() is ASCII-only but
            # player names in the bucket are already stored as-entered
            # (mixed case).  We match on LOWER(player_name) for safety.
            cursor = _db_write(
                "DELETE FROM live_entry_bucket WHERE LOWER(player_name) = ?",
                (name_lower,),
                caller="bucket_purge",
            )
            if cursor is not None:
                total_deleted += getattr(cursor, "rowcount", 0) or 0
        except Exception as exc:
            _logger.debug("purge_non_playing_players(%s): %s", name_lower, exc)

    return total_deleted
