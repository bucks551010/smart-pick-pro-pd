"""
tests/test_live_bucket.py
─────────────────────────
Audit A-020: Unit tests for tracking.live_bucket — the persistent
per-user Live Entry Bucket (add, remove, dedup, get with date filter,
anonymous user isolation).
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

# ── repo root on path ────────────────────────────────────────────────────────
_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── mock streamlit ───────────────────────────────────────────────────────────
if "streamlit" not in sys.modules:
    _st = types.ModuleType("streamlit")
    _st.session_state = {}  # type: ignore[attr-defined]
    _st.cache_data = lambda **kw: (lambda f: f)  # type: ignore[attr-defined]
    _st.cache_resource = lambda **kw: (lambda f: f)  # type: ignore[attr-defined]
    sys.modules["streamlit"] = _st


_PICK_A = {
    "player_name": "LeBron James",
    "stat_type": "points",
    "prop_line": 25.5,
    "direction": "OVER",
    "platform": "PrizePicks",
    "tier": "ELITE",
    "tier_emoji": "🔥",
    "confidence_score": 88.0,
    "probability_over": 0.72,
    "edge_percentage": 12.5,
    "bet_type": "normal",
    "odds_type": "standard",
}

_PICK_B = {
    "player_name": "Steph Curry",
    "stat_type": "threes",
    "prop_line": 3.5,
    "direction": "OVER",
    "platform": "Underdog",
    "tier": "A",
    "tier_emoji": "⚡",
    "confidence_score": 76.0,
    "probability_over": 0.65,
    "edge_percentage": 8.0,
    "bet_type": "normal",
    "odds_type": "standard",
}


def _in_memory_db():
    """Return a temporary SQLite file path — live_bucket uses a file-backed DB."""
    tmp = tempfile.mktemp(suffix=".db")
    return tmp


class TestLiveBucket(unittest.TestCase):

    def setUp(self):
        """Redirect the bucket DB to a temp file and force re-initialisation."""
        self._tmp_db = _in_memory_db()
        # Patch the DB path used by tracking.database
        self._db_patcher = patch.dict(os.environ, {"DB_PATH": self._tmp_db})
        self._db_patcher.start()

        # Force fresh import state for the module under test.
        for mod in list(sys.modules.keys()):
            if mod in ("tracking.database", "tracking.live_bucket"):
                del sys.modules[mod]

        import tracking.live_bucket as lb
        self._lb = lb
        lb.initialize_database()  # create tables in the temp DB

    def tearDown(self):
        self._db_patcher.stop()
        try:
            os.unlink(self._tmp_db)
        except OSError:
            pass

    # ── 1. Add pick OK ───────────────────────────────────────────────────────
    def test_add_pick_returns_id(self):
        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            bid = self._lb.add_to_bucket("test@example.com", _PICK_A)
        self.assertIsNotNone(bid, "add_to_bucket must return a bucket_id on success")

    # ── 2. Duplicate is silently skipped ────────────────────────────────────
    def test_duplicate_pick_skipped(self):
        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            bid1 = self._lb.add_to_bucket("test@example.com", _PICK_A)
            bid2 = self._lb.add_to_bucket("test@example.com", _PICK_A)
        self.assertIsNotNone(bid1, "first insert must succeed")
        self.assertIsNone(bid2, "duplicate insert must return None")

    # ── 3. Remove pick ───────────────────────────────────────────────────────
    def test_remove_pick(self):
        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            self._lb.add_to_bucket("test@example.com", _PICK_A)
            pick_key = self._lb._build_pick_key(_PICK_A)
            removed = self._lb.remove_from_bucket("test@example.com", pick_key)
        self.assertTrue(removed, "remove_from_bucket must return True on success")
        bucket = self._lb.get_bucket("test@example.com")
        self.assertEqual(len(bucket), 0, "bucket must be empty after remove")

    # ── 4. get_bucket date filter ────────────────────────────────────────────
    def test_get_bucket_date_filter(self):
        with patch("tracking.database._nba_today_iso", return_value="2026-04-27"):
            self._lb.add_to_bucket("test@example.com", _PICK_A)

        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            self._lb.add_to_bucket("test@example.com", _PICK_B)

        today_bucket = self._lb.get_bucket("test@example.com", game_date="2026-04-28")
        self.assertEqual(len(today_bucket), 1)
        self.assertEqual(today_bucket[0]["player_name"], "Steph Curry")

    # ── 5. Anonymous user isolation ──────────────────────────────────────────
    def test_anonymous_users_are_isolated(self):
        """Two distinct anon session IDs must not share bucket contents."""
        anon1 = "anon-abc123@local"
        anon2 = "anon-def456@local"

        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            self._lb.add_to_bucket(anon1, _PICK_A)
            self._lb.add_to_bucket(anon2, _PICK_B)

        bucket1 = self._lb.get_bucket(anon1)
        bucket2 = self._lb.get_bucket(anon2)

        self.assertEqual(len(bucket1), 1)
        self.assertEqual(len(bucket2), 1)
        self.assertEqual(bucket1[0]["player_name"], "LeBron James")
        self.assertEqual(bucket2[0]["player_name"], "Steph Curry")

    # ── 6. get_bucket returns empty list for unknown user ────────────────────
    def test_unknown_user_returns_empty(self):
        result = self._lb.get_bucket("nobody@nowhere.com")
        self.assertEqual(result, [])

    # ── 7. add_many_to_bucket counts correctly ──────────────────────────────
    def test_add_many(self):
        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            count = self._lb.add_many_to_bucket("test@example.com",
                                                 [_PICK_A, _PICK_B])
        self.assertEqual(count, 2)

    # ── 8. add_many skips duplicates in same batch ───────────────────────────
    def test_add_many_dedup(self):
        with patch("tracking.database._nba_today_iso", return_value="2026-04-28"):
            count = self._lb.add_many_to_bucket("test@example.com",
                                                 [_PICK_A, _PICK_A])
        self.assertEqual(count, 1,
            "add_many must skip duplicate in same batch (UNIQUE constraint)")


if __name__ == "__main__":
    unittest.main()
