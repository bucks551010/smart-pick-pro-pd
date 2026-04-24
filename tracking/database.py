# ============================================================
# FILE: tracking/database.py
# PURPOSE: SQLite database wrapper for storing bet history
#          and tracking model performance over time.
# CONNECTS TO: bet_tracker.py (uses these functions)
# CONCEPTS COVERED: SQLite, database CRUD operations,
#                   context managers, SQL queries
#
# NOTE: check_same_thread=False is set on ALL connections for
# Streamlit Server compatibility where multiple user sessions may
# access the database concurrently. SQLite handles this safely in
# WAL mode for read-heavy workloads (WAL mode is enabled below).
# ============================================================

# Standard library imports only
import sqlite3    # Built-in SQLite database (no install needed!)
import json       # For serializing/deserializing analysis session data
import csv        # For CSV export
import io         # For in-memory CSV buffer
import os         # For file path operations
import time       # For retry backoff delays
import datetime   # For timestamps in analysis session persistence
from pathlib import Path  # Modern file path handling

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)


# ============================================================
# SECTION: Database Configuration
# ============================================================

# Path to the SQLite database file
# It will be created automatically on first run
# Use DB_DIR env var (set on Railway to the persistent volume) or default to local db/
DB_DIRECTORY = Path(os.environ.get("DB_DIR", str(Path(__file__).parent.parent / "db")))
DB_FILE_PATH = DB_DIRECTORY / "smartai_nba.db"

# Automatic backup configuration.
BACKUP_DIRECTORY = DB_DIRECTORY / "backups"
_AUTO_BACKUP_RETENTION = 14
_AUTO_BACKUP_INTERVAL_SECONDS = 12 * 60 * 60
_AUTO_BACKUP_SENTINEL = BACKUP_DIRECTORY / ".last_auto_backup"

# Retry configuration for concurrent write safety.
# SQLite can throw "database is locked" when multiple Streamlit sessions
# attempt concurrent writes. Retrying with back-off avoids data loss.
_WRITE_RETRY_ATTEMPTS = 3
_WRITE_RETRY_DELAY = 0.25  # seconds between retries (doubles each attempt)


# ============================================================
# SECTION: PostgreSQL Adapter
# Routes all DB operations to PostgreSQL when DATABASE_URL is
# set (e.g. on Railway), falling back to SQLite for local dev.
# psycopg2-binary is already in requirements.txt.
# ============================================================

_DATABASE_URL: str = os.environ.get("DATABASE_URL", "")


def _normalize_pg_url(url: str) -> str:
    """Convert postgres:// -> postgresql:// for psycopg2."""
    return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url


def _pg_conn():
    """Return a new psycopg2 connection. Caller must close."""
    import psycopg2
    return psycopg2.connect(_normalize_pg_url(_DATABASE_URL))


def _to_pg_sql(sql: str) -> str:
    """Convert SQLite-style ? placeholders to psycopg2 %s."""
    return sql.replace("?", "%s")


def _pg_execute_write(sql: str, params=(), *, caller: str = "write"):
    """Run a write statement on PostgreSQL with retry. Returns cursor or None."""
    import psycopg2
    pg_sql = _to_pg_sql(sql)
    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        conn = None
        try:
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(pg_sql, params)
            conn.commit()
            conn.close()
            return cur
        except psycopg2.Error as err:
            _logger.error(f"{caller} PG write error (attempt {_attempt + 1}): {err}")
            try:
                if conn:
                    conn.rollback()
                    conn.close()
            except Exception:
                pass
            if _attempt >= _WRITE_RETRY_ATTEMPTS - 1:
                return None
            time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
    return None


def _pg_execute_read(sql: str, params=()) -> list:
    """Run a SELECT on PostgreSQL and return a list of dicts."""
    import psycopg2
    import psycopg2.extras
    pg_sql = _to_pg_sql(sql)
    try:
        conn = _pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(pg_sql, params if params else ())
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as err:
        _logger.warning(f"PG read error: {err}")
        return []


def _execute_read(sql: str, params=()) -> list:
    """Route a SELECT to PostgreSQL (if DATABASE_URL set) or SQLite."""
    if _DATABASE_URL:
        return _pg_execute_read(sql, params)
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, tuple(params) if params else ())
            return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as err:
        _logger.warning(f"SQLite read error: {err}")
        return []


def _pg_insert_analysis_picks(analysis_results: list, today_str: str) -> int:
    """PostgreSQL UPSERT for all_analysis_picks (ON CONFLICT DO UPDATE)."""
    if not analysis_results:
        return 0
    inserted = 0
    conn = None
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        for r in analysis_results:
            _line = round(float(r.get("line", 0) or 0), 2)
            _platform = str(r.get("platform", "") or "").strip()
            cur.execute(
                """
                INSERT INTO all_analysis_picks
                    (pick_date, player_name, team, stat_type, prop_line, direction,
                     platform, confidence_score, probability_over, edge_percentage,
                     tier, notes, bet_type, std_devs_from_line, is_risky)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pick_date, LOWER(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))
                DO UPDATE SET
                    confidence_score   = EXCLUDED.confidence_score,
                    probability_over   = EXCLUDED.probability_over,
                    edge_percentage    = EXCLUDED.edge_percentage,
                    tier               = EXCLUDED.tier,
                    notes              = EXCLUDED.notes,
                    bet_type           = EXCLUDED.bet_type,
                    std_devs_from_line = EXCLUDED.std_devs_from_line,
                    is_risky           = EXCLUDED.is_risky
                """,
                (
                    today_str,
                    r.get("player_name", ""),
                    r.get("player_team", r.get("team", "")),
                    r.get("stat_type", ""),
                    _line,
                    r.get("direction", "OVER"),
                    _platform,
                    float(r.get("confidence_score", 0) or 0),
                    float(r.get("probability_over", 0.5) or 0.5),
                    float(r.get("edge_percentage", 0) or 0),
                    r.get("tier", "Bronze"),
                    f"Auto-stored by Smart Pick Pro. SAFE Score: {r.get('confidence_score', 0):.0f}",
                    r.get("bet_type", "normal"),
                    float(r.get("std_devs_from_line", 0.0)),
                    1 if r.get("should_avoid", False) else 0,
                ),
            )
            inserted += 1
        conn.commit()
        conn.close()
    except Exception as err:
        _logger.warning(f"_pg_insert_analysis_picks error: {err}")
        try:
            if conn:
                conn.rollback()
                conn.close()
        except Exception:
            pass
    return inserted


def _initialize_pg_database() -> bool:
    """Create all tables and indexes in PostgreSQL (idempotent, includes all migrations)."""
    pg_ddl = [
        """CREATE TABLE IF NOT EXISTS bets (
            bet_id SERIAL PRIMARY KEY,
            bet_date TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT,
            stat_type TEXT NOT NULL,
            prop_line REAL NOT NULL,
            direction TEXT NOT NULL,
            platform TEXT,
            confidence_score REAL,
            probability_over REAL,
            edge_percentage REAL,
            tier TEXT,
            entry_type TEXT,
            entry_fee REAL,
            result TEXT,
            actual_value REAL,
            notes TEXT,
            auto_logged INTEGER DEFAULT 0,
            bet_type TEXT DEFAULT 'normal',
            std_devs_from_line REAL DEFAULT 0.0,
            line_category TEXT DEFAULT '50_50',
            standard_line REAL,
            entry_id INTEGER,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS entries (
            entry_id SERIAL PRIMARY KEY,
            entry_date TEXT NOT NULL,
            platform TEXT NOT NULL,
            entry_type TEXT,
            entry_fee REAL,
            expected_value REAL,
            result TEXT,
            payout REAL,
            pick_count INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS all_analysis_picks (
            pick_id SERIAL PRIMARY KEY,
            pick_date TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT,
            stat_type TEXT NOT NULL,
            prop_line REAL NOT NULL,
            direction TEXT NOT NULL,
            platform TEXT,
            confidence_score REAL,
            probability_over REAL,
            edge_percentage REAL,
            tier TEXT,
            result TEXT,
            actual_value REAL,
            notes TEXT,
            bet_type TEXT DEFAULT 'normal',
            std_devs_from_line REAL DEFAULT 0.0,
            is_risky INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS analysis_sessions (
            session_id SERIAL PRIMARY KEY,
            analysis_timestamp TEXT NOT NULL,
            analysis_results_json TEXT NOT NULL,
            todays_games_json TEXT,
            selected_picks_json TEXT,
            prop_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            last_login_at TEXT,
            reset_token TEXT,
            reset_token_expires TEXT,
            failed_login_count INTEGER DEFAULT 0,
            lockout_until TEXT,
            is_admin INTEGER DEFAULT 0,
            plan_tier TEXT DEFAULT 'free'
        )""",
        """CREATE TABLE IF NOT EXISTS subscriptions (
            subscription_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            customer_email TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            plan_name TEXT DEFAULT 'Premium',
            current_period_start TEXT,
            current_period_end TEXT,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS prediction_history (
            prediction_id SERIAL PRIMARY KEY,
            prediction_date TEXT NOT NULL,
            player_name TEXT NOT NULL,
            stat_type TEXT NOT NULL,
            prop_line REAL NOT NULL,
            direction TEXT NOT NULL,
            confidence_score REAL,
            probability_predicted REAL,
            was_correct INTEGER,
            actual_value REAL,
            notes TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS daily_snapshots (
            snapshot_id SERIAL PRIMARY KEY,
            snapshot_date TEXT NOT NULL UNIQUE,
            total_picks INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            pushes INTEGER DEFAULT 0,
            pending INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            platform_breakdown TEXT,
            tier_breakdown TEXT,
            stat_type_breakdown TEXT,
            best_pick TEXT,
            worst_pick TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS backtest_results (
            backtest_id SERIAL PRIMARY KEY,
            run_timestamp TEXT NOT NULL,
            season TEXT NOT NULL,
            stat_types_json TEXT NOT NULL,
            min_edge REAL NOT NULL,
            tier_filter TEXT,
            total_picks INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            win_rate REAL NOT NULL DEFAULT 0.0,
            roi REAL NOT NULL DEFAULT 0.0,
            total_pnl REAL NOT NULL DEFAULT 0.0,
            tier_win_rates_json TEXT,
            stat_win_rates_json TEXT,
            edge_win_rates_json TEXT,
            pick_log_json TEXT,
            created_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS user_settings (
            settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
            settings_json TEXT NOT NULL,
            updated_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS page_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            state_json TEXT NOT NULL,
            updated_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS user_profiles (
            profile_id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT,
            favorite_team TEXT,
            preferred_platforms TEXT,
            experience_level TEXT,
            betting_style TEXT,
            daily_budget TEXT,
            profile_complete INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (NOW()::text),
            updated_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS slate_cache (
            id SERIAL PRIMARY KEY,
            for_date TEXT NOT NULL,
            run_at TEXT NOT NULL,
            pick_count INTEGER NOT NULL DEFAULT 0,
            props_fetched INTEGER NOT NULL DEFAULT 0,
            games_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            error_message TEXT,
            duration_seconds REAL
        )""",
        """CREATE TABLE IF NOT EXISTS bet_audit_log (
            audit_id SERIAL PRIMARY KEY,
            bet_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            changed_at TEXT DEFAULT (NOW()::text)
        )""",
        """CREATE TABLE IF NOT EXISTS analytics_events (
            event_id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            user_email TEXT,
            event_name TEXT NOT NULL,
            page TEXT,
            event_data TEXT,
            ip_hash TEXT,
            user_agent TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ]
    pg_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_bets_player ON bets (player_name)",
        "CREATE INDEX IF NOT EXISTS idx_bets_date ON bets (bet_date)",
        "CREATE INDEX IF NOT EXISTS idx_bets_date_result ON bets (bet_date, result)",
        "CREATE INDEX IF NOT EXISTS idx_bets_created ON bets (created_at)",
        # Compound index for save_daily_snapshot & load_bets_page: the two most
        # frequent query predicates are (bet_date, entry_id IS NULL).  A covering
        # index on both columns lets SQLite satisfy the WHERE clause with a single
        # B-tree seek instead of a full bet_date scan + Python filter.
        "CREATE INDEX IF NOT EXISTS idx_bets_date_entry ON bets (bet_date, entry_id)",
        "CREATE INDEX IF NOT EXISTS idx_aap_date ON all_analysis_picks (pick_date)",
        "CREATE INDEX IF NOT EXISTS idx_aap_player ON all_analysis_picks (player_name)",
        "CREATE INDEX IF NOT EXISTS idx_aap_date_result ON all_analysis_picks (pick_date, result)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_aap_unique_v2 ON all_analysis_picks (pick_date, LOWER(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))",
        "CREATE INDEX IF NOT EXISTS idx_ae_timestamp ON analytics_events (timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_ae_user ON analytics_events (user_email)",
        "CREATE INDEX IF NOT EXISTS idx_ph_date ON prediction_history (prediction_date)",
    ]
    conn = None
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        for ddl in pg_ddl:
            cur.execute(ddl)
        conn.commit()
        for idx_sql in pg_indexes:
            try:
                cur = conn.cursor()
                cur.execute(idx_sql)
                conn.commit()
            except Exception as idx_err:
                _logger.debug(f"PG index skipped (may already exist): {idx_err}")
                conn.rollback()
        conn.close()
        _logger.info("[database] PostgreSQL tables initialized successfully")
        return True
    except Exception as err:
        _logger.error(f"[database] PostgreSQL init error: {err}")
        try:
            if conn:
                conn.rollback()
                conn.close()
        except Exception:
            pass
        return False

# ============================================================
# END SECTION: PostgreSQL Adapter
# ============================================================


def _get_eastern_tz():
    """Return America/New_York timezone, with UTC-5 fallback."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except ImportError:
        return datetime.timezone(datetime.timedelta(hours=-5))


def _nba_today_iso() -> str:
    """Return today's date anchored to NBA's ET day boundary."""
    return datetime.datetime.now(_get_eastern_tz()).date().isoformat()


def _extract_iso_date(value) -> str:
    """Best-effort YYYY-MM-DD extraction from a timestamp/date value."""
    if not value:
        return ""
    text = str(value).strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return ""


def _execute_write(sql, params=(), *, caller="write"):
    """Execute a single INSERT / UPDATE with locked-database retry.

    Centralises the retry-with-backoff loop that was previously inlined
    in ``insert_bet`` and ``update_bet_result``, so every write path
    gets the same concurrency protection.

    Args:
        sql (str): The SQL statement to execute.
        params (tuple): Bind parameters.
        caller (str): Label for log messages.

    Returns:
        sqlite3.Cursor | None: The cursor on success, or *None* after
        all retries are exhausted.
    """
    if _DATABASE_URL:
        return _pg_execute_write(sql, params, caller=caller)
    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            conn = sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
            return cursor
        except sqlite3.OperationalError as op_err:
            if "locked" in str(op_err).lower() and _attempt < _WRITE_RETRY_ATTEMPTS - 1:
                _logger.warning(
                    f"{caller}: database locked, retry "
                    f"{_attempt + 1}/{_WRITE_RETRY_ATTEMPTS}"
                )
                time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
                continue
            _logger.error(f"{caller} error: {op_err}")
            return None
        except sqlite3.Error as db_err:
            _logger.error(f"{caller} error: {db_err}")
            return None
    return None


# SQL to create the bets table (runs once when app starts)
# BEGINNER NOTE: SQL is a language for managing databases.
# CREATE TABLE IF NOT EXISTS = only create if it doesn't exist yet
CREATE_BETS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bets (
    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_date TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT,
    stat_type TEXT NOT NULL,
    prop_line REAL NOT NULL,
    direction TEXT NOT NULL,
    platform TEXT,
    confidence_score REAL,
    probability_over REAL,
    edge_percentage REAL,
    tier TEXT,
    entry_type TEXT,
    entry_fee REAL,
    result TEXT,
    actual_value REAL,
    notes TEXT,
    auto_logged INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the entries table (for tracking parlay entries)
CREATE_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    platform TEXT NOT NULL,
    entry_type TEXT,
    entry_fee REAL,
    expected_value REAL,
    result TEXT,
    payout REAL,
    pick_count INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the prediction_history table for model calibration (W7)
# Tracks each prediction made and whether it was correct.
# Used to compute calibration adjustments that self-correct model overconfidence.
CREATE_PREDICTION_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_history (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_date TEXT NOT NULL,
    player_name TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    prop_line REAL NOT NULL,
    direction TEXT NOT NULL,
    confidence_score REAL,
    probability_predicted REAL,
    was_correct INTEGER,
    actual_value REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the daily_snapshots table for per-day performance tracking.
# Stores aggregated bet outcomes, win rates, and breakdowns per day.
CREATE_DAILY_SNAPSHOTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    total_picks INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    pushes INTEGER DEFAULT 0,
    pending INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    platform_breakdown TEXT,
    tier_breakdown TEXT,
    stat_type_breakdown TEXT,
    best_pick TEXT,
    worst_pick TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the all_analysis_picks table.
# Stores EVERY pick output by Neural Analysis (not just AI-auto-logged ones)
# so users can track the complete performance record of the app's predictions.
CREATE_ALL_ANALYSIS_PICKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS all_analysis_picks (
    pick_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pick_date TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT,
    stat_type TEXT NOT NULL,
    prop_line REAL NOT NULL,
    direction TEXT NOT NULL,
    platform TEXT,
    confidence_score REAL,
    probability_over REAL,
    edge_percentage REAL,
    tier TEXT,
    result TEXT,
    actual_value REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the subscriptions table.
# Stores Stripe subscription records for premium access tracking.
# Each row represents one subscriber; status reflects the current
# Stripe subscription status (active, trialing, cancelled, etc.).
CREATE_SUBSCRIPTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    customer_email TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    plan_name TEXT DEFAULT 'Premium',
    current_period_start TEXT,
    current_period_end TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the users table.
# Stores registered user accounts for the signup/login gate.
# Passwords are stored as bcrypt hashes (never plaintext).
CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    last_login_at TEXT
);
"""

# SQL to create the analysis_sessions table.
# Persists Neural Analysis results so users never lose their analysis
# after inactivity. On page load, session state is rehydrated from here.
CREATE_ANALYSIS_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analysis_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_timestamp TEXT NOT NULL,
    analysis_results_json TEXT NOT NULL,
    todays_games_json TEXT,
    selected_picks_json TEXT,
    prop_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the backtest_results table.
# Stores historical backtesting runs so results persist across sessions.
CREATE_BACKTEST_RESULTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TEXT NOT NULL,
    season TEXT NOT NULL,
    stat_types_json TEXT NOT NULL,
    min_edge REAL NOT NULL,
    tier_filter TEXT,
    total_picks INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    win_rate REAL NOT NULL DEFAULT 0.0,
    roi REAL NOT NULL DEFAULT 0.0,
    total_pnl REAL NOT NULL DEFAULT 0.0,
    tier_win_rates_json TEXT,
    stat_win_rates_json TEXT,
    edge_win_rates_json TEXT,
    pick_log_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the player_game_logs cache table.
# Feature 12: Game Log Persistence Across Sessions.
# Stores per-player game log rows retrieved from nba_api so browser
# refreshes and session resets don't lose expensive API data.
# Cache invalidation: re-retrieve if most recent game is > 24 hours old.
CREATE_PLAYER_GAME_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS player_game_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    game_date TEXT NOT NULL,
    opponent TEXT,
    minutes REAL,
    points INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    threes INTEGER,
    steals INTEGER,
    blocks INTEGER,
    turnovers INTEGER,
    fg_pct REAL,
    ft_pct REAL,
    plus_minus INTEGER,
    retrieved_at TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);
"""

# SQL to create the bet audit log table.
# Tracks all edit/delete operations on bets for accountability.
CREATE_BET_AUDIT_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bet_audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_values TEXT,
    new_values TEXT,
    changed_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the user_settings table.
# Persists user-configurable settings (simulation depth, edge threshold,
# platform selections, tuning sliders, bankroll, etc.) so they survive
# browser reloads.  A single row (settings_id=1) stores the latest values.
CREATE_USER_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_settings (
    settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
    settings_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the page_state table.
# Persists critical page data (analysis results, selected picks, today's
# games, props, etc.) so they survive Streamlit session resets that occur
# when the browser tab is idle for an extended period.  A single row
# (state_id=1) stores the latest values as a JSON blob.
CREATE_PAGE_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS page_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    state_json TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the user_profiles table.
# Stores premium subscriber profile preferences collected during
# the post-checkout onboarding wizard.  Keyed by email (NOCASE)
# so it survives session resets.
CREATE_USER_PROFILES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT,
    favorite_team TEXT,
    preferred_platforms TEXT,
    experience_level TEXT,
    betting_style TEXT,
    daily_budget TEXT,
    profile_complete INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

# ── slate_cache — one row per slate_worker run ───────────────────────────
# Written exclusively by slate_worker.py (background job).
# Read by the Streamlit UI to surface worker health and staleness info.
CREATE_SLATE_CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS slate_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    for_date TEXT NOT NULL,
    run_at TEXT NOT NULL,
    pick_count INTEGER NOT NULL DEFAULT 0,
    props_fetched INTEGER NOT NULL DEFAULT 0,
    games_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ok',
    error_message TEXT,
    duration_seconds REAL
);
"""

# ============================================================
# END SECTION: Database Configuration
# ============================================================


# ============================================================
# SECTION: Database Initialization
# ============================================================

_DB_INITIALIZED = False


def initialize_database():
    """
    Create the database and tables if they don't exist.

    Call this once when the app starts. It's safe to call
    multiple times â€” CREATE TABLE IF NOT EXISTS won't
    overwrite existing tables.  After the first successful
    initialization the heavy work (PRAGMA integrity_check,
    CREATE TABLE, ALTER TABLE migrations) is skipped.

    Returns:
        bool: True if successful, False if error occurred
    """
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return True

    if _DATABASE_URL:
        ok = _initialize_pg_database()
        _DB_INITIALIZED = ok
        return ok

    # Make sure the db directory exists
    # exist_ok=True means don't error if it already exists
    DB_DIRECTORY.mkdir(parents=True, exist_ok=True)

    try:
        # Connect to the SQLite database file
        # BEGINNER NOTE: sqlite3.connect() opens (or creates) the DB file
        # 'with' statement ensures the connection is properly closed
        # check_same_thread=False: required for Streamlit Server multi-session access
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30) as connection:
            # Enable WAL mode for safe concurrent read access
            connection.execute("PRAGMA journal_mode=WAL")
            # Enforce foreign key constraints (disabled by default in SQLite)
            connection.execute("PRAGMA foreign_keys=ON")
            # Run integrity check on startup
            try:
                integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
                if integrity_result and integrity_result[0] != "ok":
                    _logger.warning(
                        "Database integrity check returned: %s. "
                        "Consider restoring from backup or reinitializing the database.",
                        integrity_result[0],
                    )
                else:
                    _logger.debug("Database integrity check passed")
            except Exception as _ic_err:
                _logger.warning("Database integrity check failed: %s", _ic_err)
            cursor = connection.cursor()  # A cursor lets us run SQL commands

            # Create the tables
            cursor.execute(CREATE_BETS_TABLE_SQL)
            cursor.execute(CREATE_ENTRIES_TABLE_SQL)
            cursor.execute(CREATE_PREDICTION_HISTORY_TABLE_SQL)  # W7: calibration
            cursor.execute(CREATE_DAILY_SNAPSHOTS_TABLE_SQL)      # daily performance tracking
            cursor.execute(CREATE_ALL_ANALYSIS_PICKS_TABLE_SQL)   # all Neural Analysis outputs
            cursor.execute(CREATE_SUBSCRIPTIONS_TABLE_SQL)        # Stripe subscription records
            cursor.execute(CREATE_USERS_TABLE_SQL)                    # User account records
            cursor.execute(CREATE_ANALYSIS_SESSIONS_TABLE_SQL)    # analysis session persistence
            cursor.execute(CREATE_BACKTEST_RESULTS_TABLE_SQL)     # historical backtesting results
            cursor.execute(CREATE_PLAYER_GAME_LOGS_TABLE_SQL)     # Feature 12: game log persistence
            cursor.execute(CREATE_BET_AUDIT_LOG_TABLE_SQL)         # Bet edit/delete audit log
            cursor.execute(CREATE_USER_SETTINGS_TABLE_SQL)        # User settings persistence
            cursor.execute(CREATE_PAGE_STATE_TABLE_SQL)             # Page state persistence
            cursor.execute(CREATE_USER_PROFILES_TABLE_SQL)          # Premium profile onboarding
            cursor.execute(CREATE_SLATE_CACHE_TABLE_SQL)             # slate_worker run metadata
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS app_state "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)"
            )

            # â”€â”€ Indexes for performance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _TRACKING_INDEXES = (
                ("idx_pgl_player_id", "player_game_logs", "(player_id)"),
                ("idx_pgl_game_date", "player_game_logs", "(game_date)"),
                ("idx_pgl_player_date", "player_game_logs", "(player_id, game_date)"),
                ("idx_bets_player", "bets", "(player_name)"),
                ("idx_bets_date", "bets", "(bet_date)"),
                ("idx_bets_created", "bets", "(created_at)"),
                ("idx_bets_stat_type", "bets", "(stat_type)"),
                ("idx_bets_platform", "bets", "(platform)"),
                ("idx_bets_date_result", "bets", "(bet_date, result)"),
                # Compound covering index for the most common filter pattern:
                # WHERE bet_date = ? AND entry_id IS NULL.  Eliminates a full
                # bet_date scan followed by Python-side entry_id filtering.
                ("idx_bets_date_entry", "bets", "(bet_date, entry_id)"),
                ("idx_ph_date", "prediction_history", "(prediction_date)"),
                ("idx_ph_stat", "prediction_history", "(stat_type)"),
                ("idx_aap_date", "all_analysis_picks", "(pick_date)"),
                ("idx_aap_player", "all_analysis_picks", "(player_name)"),
                ("idx_aap_stat_type", "all_analysis_picks", "(stat_type)"),
                ("idx_aap_date_result", "all_analysis_picks", "(pick_date, result)"),
            )
            for idx_name, table, columns in _TRACKING_INDEXES:
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} {columns}"
                )

            # â”€â”€ Schema migrations for existing databases â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Add auto_logged column if it doesn't exist yet
            # (ALTER TABLE is idempotent-safe via the try/except)
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN auto_logged INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            # Ensure actual_value column exists (older schema may not have it)
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN actual_value REAL"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            # â”€â”€ Subscriptions table migration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # If the subscriptions table was created without updated_at
            # (e.g., from an older version of the schema), add it now.
            try:
                cursor.execute(
                    "ALTER TABLE subscriptions ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            # â”€â”€ Goblin/Demon bet_type column migrations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Add bet_type and std_devs_from_line to bets table
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN bet_type TEXT DEFAULT 'normal'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN std_devs_from_line REAL DEFAULT 0.0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add is_risky flag to all_analysis_picks (1 = avoid/risky pick)
            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN is_risky INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add bet_type to all_analysis_picks table
            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN bet_type TEXT DEFAULT 'normal'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN std_devs_from_line REAL DEFAULT 0.0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            # â”€â”€ Line category column migration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Add line_category and standard_line columns for the three-tier
            # Goblin / 50_50 / Demon classification system.
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN line_category TEXT DEFAULT '50_50'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN standard_line REAL"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore

            # Preserve true Goblin / Demon bet types. Earlier builds rewrote every
            # demon row to 50_50, which also erased legitimate Smart Money demon
            # picks on subsequent app starts. Only do best-effort restoration when
            # notes clearly identify the intended classification.
            try:
                cursor.execute(
                    "UPDATE bets SET bet_type = 'demon' "
                    "WHERE lower(COALESCE(notes, '')) LIKE '%smart money demon%' "
                    "AND COALESCE(lower(bet_type), '') <> 'demon'"
                )
                cursor.execute(
                    "UPDATE bets SET bet_type = 'goblin' "
                    "WHERE lower(COALESCE(notes, '')) LIKE '%smart money goblin%' "
                    "AND COALESCE(lower(bet_type), '') <> 'goblin'"
                )
            except sqlite3.OperationalError:
                pass

            # â”€â”€ entry_id column migration (link bets to parlay entries) â”€â”€
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN entry_id INTEGER"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists â€” safe to ignore


            # ── source column migration (track bet origin) ──
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN source TEXT DEFAULT 'manual'"
                )
                # Backfill: auto-logged bets get 'qeg_auto', manual bets keep 'manual'
                cursor.execute(
                    "UPDATE bets SET source = 'qeg_auto' WHERE auto_logged = 1 AND source = 'manual'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists
            # â”€â”€ Rename retrieved_at column in player_game_logs â”€â”€
            # Older databases have the column named with old terminology; new schema
            # uses retrieved_at.  SQLite â‰¥ 3.25 supports ALTER TABLE RENAME
            # COLUMN, but we guard with try/except for older builds.
            try:
                cursor.execute(
                    "ALTER TABLE player_game_logs RENAME COLUMN fetched_at TO retrieved_at"
                )
            except sqlite3.OperationalError:
                pass  # Column already renamed or doesn't exist

            # â”€â”€ Unique index on all_analysis_picks to prevent duplicate rows â”€â”€
            # v2 key includes platform so distinct platform props do not collapse
            # into one row when player/stat/line/direction match.
            try:
                cursor.execute("DROP INDEX IF EXISTS idx_aap_unique_pick")
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_aap_unique_pick_v2 "
                    "ON all_analysis_picks "
                    "(pick_date, lower(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))"
                )
            except sqlite3.OperationalError:
                # May fail if existing data already has duplicates on the v2 key.
                # Clean up duplicates first, then retry.
                try:
                    cursor.execute(
                        """
                        DELETE FROM all_analysis_picks
                        WHERE pick_id NOT IN (
                            SELECT MIN(pick_id)
                            FROM all_analysis_picks
                            GROUP BY pick_date, lower(player_name), stat_type, prop_line, direction, COALESCE(platform, '')
                        )
                        """
                    )
                    cursor.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_aap_unique_pick_v2 "
                        "ON all_analysis_picks "
                        "(pick_date, lower(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))"
                    )
                except sqlite3.OperationalError:
                    pass  # Best-effort â€” app-level dedup still protects

            # ── Password reset token columns on users table ──
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN reset_token TEXT"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN reset_token_expires TEXT"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # ── Login attempt rate-limiting columns on users table ──
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN failed_login_count INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN lockout_until TEXT"
                )
            except sqlite3.OperationalError:
                pass

            # ── Admin role column on users table ──
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # ── Subscription tier column on users table ──
            try:
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN plan_tier TEXT DEFAULT 'free'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # ── Analytics events table ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    user_email TEXT,
                    event_name TEXT NOT NULL,
                    page TEXT,
                    event_data TEXT,
                    ip_hash TEXT,
                    user_agent TEXT
                )
            """)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ae_timestamp ON analytics_events (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ae_event_name ON analytics_events (event_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ae_user ON analytics_events (user_email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ae_page ON analytics_events (page)")
            except sqlite3.OperationalError:
                pass

            # Save the changes
            connection.commit()

        _DB_INITIALIZED = True
        try:
            maybe_create_automatic_backup()
        except Exception as backup_err:
            _logger.debug("auto backup after init skipped: %s", backup_err)
        return True

    except sqlite3.Error as database_error:
        _logger.error(f"Database initialization error: {database_error}")
        return False


def get_database_connection():
    """
    Get a connection to the SQLite database.

    Returns:
        sqlite3.Connection: Active database connection
        Call .close() when done, or use 'with' statement.
    """
    # Ensure database exists before connecting
    initialize_database()

    # Connect with row_factory so results come back as dictionaries
    # BEGINNER NOTE: row_factory makes results easier to work with â€”
    # instead of tuples (24, 'LeBron') you get {'points': 24, 'name': 'LeBron'}
    # check_same_thread=False: required for Streamlit Server multi-session access
    connection = sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30)
    # Enable WAL mode for safe concurrent read access
    connection.execute("PRAGMA journal_mode=WAL")
    connection.row_factory = sqlite3.Row  # Rows behave like dicts

    return connection


def create_database_backup(*, reason="scheduled"):
    """Create a timestamped SQLite backup and prune older backups.

    Returns:
        tuple[bool, str]: (success, file path or error message)
    """
    try:
        initialize_database()
        if not DB_FILE_PATH.exists():
            return False, "database file not found"

        BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIRECTORY / f"smartai_nba_{timestamp}.db"

        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30) as source_conn:
            source_conn.execute("PRAGMA journal_mode=WAL")
            with sqlite3.connect(str(backup_path), check_same_thread=False, timeout=30) as backup_conn:
                source_conn.backup(backup_conn)

        backups = sorted(BACKUP_DIRECTORY.glob("smartai_nba_*.db"), reverse=True)
        for old_backup in backups[_AUTO_BACKUP_RETENTION:]:
            try:
                old_backup.unlink(missing_ok=True)
            except Exception as prune_err:
                _logger.debug("Could not prune backup %s: %s", old_backup, prune_err)

        _logger.info("Database backup created (%s): %s", reason, backup_path)
        return True, str(backup_path)
    except Exception as backup_err:
        _logger.warning("create_database_backup failed: %s", backup_err)
        return False, str(backup_err)


def maybe_create_automatic_backup():
    """Create a periodic backup if enough time has elapsed."""
    try:
        BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
        now_ts = time.time()
        last_ts = 0.0
        if _AUTO_BACKUP_SENTINEL.exists():
            try:
                last_ts = float(_AUTO_BACKUP_SENTINEL.read_text(encoding="utf-8").strip() or "0")
            except Exception:
                last_ts = 0.0

        if now_ts - last_ts < _AUTO_BACKUP_INTERVAL_SECONDS:
            return False

        ok, _ = create_database_backup(reason="auto")
        if ok:
            _AUTO_BACKUP_SENTINEL.write_text(str(now_ts), encoding="utf-8")
            return True
        return False
    except Exception as auto_backup_err:
        _logger.debug("maybe_create_automatic_backup skipped: %s", auto_backup_err)
        return False

# ============================================================
# END SECTION: Database Initialization
# ============================================================


# ============================================================
# SECTION: Database CRUD Operations
# CRUD = Create, Read, Update, Delete
# ============================================================

def insert_bet(bet_data):
    """
    Save a new bet to the database.

    Args:
        bet_data (dict): Bet information with keys:
            bet_date, player_name, team, stat_type, prop_line,
            direction, platform, confidence_score, probability_over,
            edge_percentage, tier, entry_type, entry_fee, notes,
            auto_logged (optional, default 0)

    Returns:
        int or None: The new bet's ID, or None if error
    """
    # SQL INSERT statement â€” ? placeholders for safety
    # BEGINNER NOTE: Never put values directly in SQL strings!
    # Use ? placeholders to prevent "SQL injection" attacks
    insert_sql = """
    INSERT INTO bets (
        bet_date, player_name, team, stat_type, prop_line,
        direction, platform, confidence_score, probability_over,
        edge_percentage, tier, entry_type, entry_fee, notes, auto_logged,
        bet_type, std_devs_from_line, source
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    values = (
        bet_data.get("bet_date", ""),
        bet_data.get("player_name", ""),
        bet_data.get("team", ""),
        bet_data.get("stat_type", ""),
        bet_data.get("prop_line", 0.0),
        bet_data.get("direction", "OVER"),
        bet_data.get("platform", ""),
        bet_data.get("confidence_score", 0.0),
        bet_data.get("probability_over", 0.5),
        bet_data.get("edge_percentage", 0.0),
        bet_data.get("tier", "Bronze"),
        bet_data.get("entry_type", ""),
        bet_data.get("entry_fee", 0.0),
        bet_data.get("notes", ""),
        int(bet_data.get("auto_logged", 0)),
        bet_data.get("bet_type", "normal"),
        float(bet_data.get("std_devs_from_line", 0.0)),
        bet_data.get("source", "manual"),
    )

    if _DATABASE_URL:
        pg_sql = _to_pg_sql(insert_sql) + " RETURNING bet_id"
        conn = None
        try:
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(pg_sql, values)
            row = cur.fetchone()
            conn.commit()
            conn.close()
            return row[0] if row else None
        except Exception as _pg_err:
            _logger.error(f"insert_bet PG error: {_pg_err}")
            try:
                if conn:
                    conn.rollback()
                    conn.close()
            except Exception:
                pass
            return None

    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                cursor = connection.cursor()
                cursor.execute(insert_sql, values)
                connection.commit()
                return cursor.lastrowid  # Return the new row's ID

        except sqlite3.OperationalError as op_err:
            if "locked" in str(op_err).lower() and _attempt < _WRITE_RETRY_ATTEMPTS - 1:
                _logger.warning(f"insert_bet: database locked, retry {_attempt + 1}/{_WRITE_RETRY_ATTEMPTS}")
                time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
                continue
            _logger.error(f"Error inserting bet: {op_err}")
            return None
        except sqlite3.Error as database_error:
            _logger.error(f"Error inserting bet: {database_error}")
            return None
    return None


def update_bet_result(bet_id, result, actual_value):
    """
    Update a bet with its result after the game.

    Args:
        bet_id (int): The bet's database ID
        result (str): 'WIN', 'LOSS', or 'EVEN'
        actual_value (float): What the player actually scored

    Returns:
        bool: True if updated successfully
    """
    update_sql = """
    UPDATE bets
    SET result = ?, actual_value = ?
    WHERE bet_id = ?
    """

    if _DATABASE_URL:
        cur = _pg_execute_write(
            "UPDATE bets SET result = %s, actual_value = %s WHERE bet_id = %s",
            (result, actual_value, bet_id),
            caller="update_bet_result",
        )
        return cur is not None and cur.rowcount > 0

    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                cursor = connection.cursor()
                cursor.execute(update_sql, (result, actual_value, bet_id))
                connection.commit()
                return cursor.rowcount > 0  # True if a row was updated

        except sqlite3.OperationalError as op_err:
            if "locked" in str(op_err).lower() and _attempt < _WRITE_RETRY_ATTEMPTS - 1:
                _logger.warning(f"update_bet_result: database locked, retry {_attempt + 1}/{_WRITE_RETRY_ATTEMPTS}")
                time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
                continue
            _logger.error(f"Error updating bet result: {op_err}")
            return False
        except sqlite3.Error as database_error:
            _logger.error(f"Error updating bet result: {database_error}")
            return False
    return False


def delete_bet(bet_id):
    """
    Delete a bet from the database and log the deletion in the audit table.

    Args:
        bet_id (int): The bet's database ID.

    Returns:
        tuple[bool, str]: (success, message)
    """
    # First, fetch the bet for audit purposes
    _lookup_rows = _execute_read("SELECT * FROM bets WHERE bet_id = ?", (bet_id,))
    if not _lookup_rows:
        return False, f"Bet #{bet_id} not found."
    bet_snapshot = _lookup_rows[0]

    # Delete the bet
    cursor = _execute_write(
        "DELETE FROM bets WHERE bet_id = ?", (bet_id,), caller="delete_bet"
    )
    if cursor is None or cursor.rowcount == 0:
        return False, f"Failed to delete bet #{bet_id}."

    # Log audit record
    _execute_write(
        """INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at)
           VALUES (?, 'DELETE', ?, NULL, datetime('now'))""",
        (bet_id, json.dumps(bet_snapshot, default=str)),
        caller="delete_bet_audit",
    )
    return True, f"Bet #{bet_id} deleted successfully."


def update_bet_fields(bet_id, updates):
    """
    Update editable fields of a bet (line, direction, platform, notes, tier).

    Args:
        bet_id (int): The bet's database ID.
        updates (dict): Key-value pairs to update. Only whitelisted fields are
            accepted: prop_line, direction, platform, notes, tier, stat_type.

    Returns:
        tuple[bool, str]: (success, message)
    """
    ALLOWED_FIELDS = {"prop_line", "direction", "platform", "notes", "tier", "stat_type"}
    filtered = {k: v for k, v in updates.items() if k in ALLOWED_FIELDS}
    if not filtered:
        return False, "No valid fields to update."

    # Fetch old values for audit
    _lookup_rows = _execute_read("SELECT * FROM bets WHERE bet_id = ?", (bet_id,))
    if not _lookup_rows:
        return False, f"Bet #{bet_id} not found."
    old_values = {k: _lookup_rows[0].get(k) for k in filtered}

    # Build SET clause
    set_parts = [f"{k} = ?" for k in filtered]
    values = list(filtered.values()) + [bet_id]
    sql = f"UPDATE bets SET {', '.join(set_parts)} WHERE bet_id = ?"

    cursor = _execute_write(sql, tuple(values), caller="update_bet_fields")
    if cursor is None or cursor.rowcount == 0:
        return False, f"Failed to update bet #{bet_id}."

    # Log audit record
    _execute_write(
        """INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at)
           VALUES (?, 'EDIT', ?, ?, datetime('now'))""",
        (bet_id, json.dumps(old_values, default=str), json.dumps(filtered, default=str)),
        caller="update_bet_fields_audit",
    )
    return True, f"Bet #{bet_id} updated: {', '.join(filtered.keys())}."


def apply_bet_edits_atomic(edits: list, deletes: list) -> tuple:
    """Apply a batch of field edits and row deletions in one atomic transaction.

    All-or-nothing: if any statement fails the entire batch is rolled back and
    the DB is left unchanged. The caller receives a (False, reason) tuple so it
    can surface an st.error without showing a false success.

    Args:
        edits:   list of {"bet_id": int, "updates": dict[str, Any]}
        deletes: list of int bet_ids to hard-delete

    Returns:
        tuple[bool, str]: (success, human-readable message)
    """
    ALLOWED = {"prop_line", "direction", "platform", "notes", "tier", "stat_type"}

    if not edits and not deletes:
        return False, "Nothing to apply."

    # Compile and validate all edits before opening a DB connection
    compiled_edits = []
    for item in edits:
        bid = item.get("bet_id")
        safe = {k: v for k, v in (item.get("updates") or {}).items() if k in ALLOWED}
        if not bid or not safe:
            continue
        set_clause = ", ".join(f"{k} = ?" for k in safe)
        params = tuple(safe.values()) + (int(bid),)
        compiled_edits.append((int(bid), f"UPDATE bets SET {set_clause} WHERE bet_id = ?", params, safe))

    compiled_deletes = [int(d) for d in deletes if d]

    if not compiled_edits and not compiled_deletes:
        return False, "No valid changes after field validation."

    n_edits, n_dels = len(compiled_edits), len(compiled_deletes)
    _now_sql = "NOW()" if _DATABASE_URL else "datetime('now')"

    # ── PostgreSQL — single connection, explicit transaction ──────────────
    if _DATABASE_URL:
        import psycopg2
        conn = None
        try:
            conn = _pg_conn()
            cur = conn.cursor()
            for bid, sql, params, safe in compiled_edits:
                cur.execute(_to_pg_sql(sql), params)
                cur.execute(
                    _to_pg_sql(
                        "INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at) "
                        "VALUES (?, 'EDIT', NULL, ?, " + _now_sql + ")"
                    ),
                    (bid, json.dumps(safe, default=str)),
                )
            for did in compiled_deletes:
                cur.execute(_to_pg_sql("DELETE FROM bets WHERE bet_id = ?"), (did,))
                cur.execute(
                    _to_pg_sql(
                        "INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at) "
                        "VALUES (?, 'DELETE', NULL, NULL, " + _now_sql + ")"
                    ),
                    (did,),
                )
            conn.commit()
            return True, f"Applied {n_edits} edit(s) and {n_dels} deletion(s)."
        except psycopg2.Error as _pg_err:
            _logger.error("apply_bet_edits_atomic PG error: %s", _pg_err)
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
            return False, f"Transaction rolled back: {_pg_err}"
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    # ── SQLite — context manager auto-commits on clean exit, rolls back on exception
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            for bid, sql, params, safe in compiled_edits:
                conn.execute(sql, params)
                conn.execute(
                    "INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at) "
                    "VALUES (?, 'EDIT', NULL, ?, datetime('now'))",
                    (bid, json.dumps(safe, default=str)),
                )
            for did in compiled_deletes:
                conn.execute("DELETE FROM bets WHERE bet_id = ?", (did,))
                conn.execute(
                    "INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at) "
                    "VALUES (?, 'DELETE', NULL, NULL, datetime('now'))",
                    (did,),
                )
        return True, f"Applied {n_edits} edit(s) and {n_dels} deletion(s)."
    except sqlite3.Error as _sq_err:
        _logger.error("apply_bet_edits_atomic SQLite error: %s", _sq_err)
        return False, f"Transaction rolled back: {_sq_err}"


def search_bets_by_player(query, limit=200):
    """
    Search bets by player name substring (case-insensitive).

    Args:
        query (str): Player name search string.
        limit (int): Maximum results.

    Returns:
        list[dict]: Matching bet records.
    """
    if not query or not query.strip():
        return []
    sql = """
    SELECT * FROM bets
    WHERE LOWER(player_name) LIKE ?
      AND entry_id IS NULL
    ORDER BY created_at DESC
    LIMIT ?
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (f"%{query.strip().lower()}%", limit)).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as err:
        _logger.error(f"search_bets_by_player error: {err}")
        return []


def load_bets_by_date_range(start_date, end_date, limit=10000):
    """
    Load bets within a date range (inclusive).

    Args:
        start_date (str): Start date in ISO format (YYYY-MM-DD).
        end_date (str): End date in ISO format (YYYY-MM-DD).
        limit (int): Maximum results.

    Returns:
        list[dict]: Matching bet records.
    """
    sql = """
    SELECT * FROM bets
    WHERE bet_date >= ? AND bet_date <= ?
      AND entry_id IS NULL
    ORDER BY created_at DESC
    LIMIT ?
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, (start_date, end_date, limit)).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as err:
        _logger.error(f"load_bets_by_date_range error: {err}")
        return []


def export_bets_csv(bets):
    """
    Convert a list of bet dicts to CSV string.

    Args:
        bets (list[dict]): Bet records.

    Returns:
        str: CSV-formatted string.
    """
    if not bets:
        return ""

    columns = [
        "bet_id", "bet_date", "player_name", "team", "stat_type",
        "prop_line", "direction", "platform", "confidence_score",
        "tier", "result", "actual_value", "edge_percentage", "notes",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for bet in bets:
        writer.writerow(bet)
    return buffer.getvalue()


# ============================================================
# SECTION: Parlay / Entry CRUD
# ============================================================

def insert_entry(entry_data):
    """
    Save a new parlay/entry to the database.

    Args:
        entry_data (dict): Entry information with keys:
            entry_date, platform, entry_type, entry_fee,
            expected_value, pick_count, notes

    Returns:
        int or None: The new entry's ID, or None if error
    """
    insert_sql = """
    INSERT INTO entries (
        entry_date, platform, entry_type, entry_fee,
        expected_value, pick_count, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        entry_data.get("entry_date", ""),
        entry_data.get("platform", ""),
        entry_data.get("entry_type", "parlay"),
        entry_data.get("entry_fee", 0.0),
        entry_data.get("expected_value", 0.0),
        entry_data.get("pick_count", 0),
        entry_data.get("notes", ""),
    )
    cursor = _execute_write(insert_sql, values, caller="insert_entry")
    if cursor is not None:
        return cursor.lastrowid
    return None


def load_all_entries(limit=500):
    """
    Load recent parlay entries from the database.

    Returns:
        list of dict: Entry rows as dictionaries
    """
    select_sql = """
    SELECT * FROM entries
    ORDER BY created_at DESC
    LIMIT ?
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(select_sql, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as database_error:
        _logger.error(f"Error loading entries: {database_error}")
        return []


def update_entry_result(entry_id, result, payout=None):
    """
    Update a parlay entry with its result.

    Args:
        entry_id (int): The entry's database ID
        result (str): 'WIN', 'LOSS', or 'EVEN'
        payout (float, optional): Actual payout amount

    Returns:
        bool: True if updated successfully
    """
    update_sql = """
    UPDATE entries
    SET result = ?, payout = ?
    WHERE entry_id = ?
    """
    cursor = _execute_write(
        update_sql, (result, payout, entry_id), caller="update_entry_result"
    )
    return cursor is not None and cursor.rowcount > 0


def link_bets_to_entry(bet_ids, entry_id):
    """
    Link a list of bet IDs to a parlay entry.

    Args:
        bet_ids (list[int]): Bet IDs to link
        entry_id (int): Entry ID to link to

    Returns:
        int: Number of bets linked
    """
    linked = 0
    for bet_id in bet_ids:
        cursor = _execute_write(
            "UPDATE bets SET entry_id = ? WHERE bet_id = ?",
            (entry_id, bet_id),
            caller="link_bets_to_entry",
        )
        if cursor is not None and cursor.rowcount > 0:
            linked += 1
    return linked


def get_entry_legs(entry_id):
    """
    Get all bets (legs) linked to a parlay entry.

    Args:
        entry_id (int): The entry ID

    Returns:
        list of dict: Bet rows linked to this entry
    """
    select_sql = """
    SELECT * FROM bets
    WHERE entry_id = ?
    ORDER BY created_at ASC
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(select_sql, (entry_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as database_error:
        _logger.error(f"Error loading entry legs: {database_error}")
        return []


def resolve_entry_from_legs(entry_id):
    """
    Compute and update an entry's result from its linked legs.
    All legs must be WIN for the entry to be WIN.
    If any leg is LOSS, entry is LOSS.
    If all legs resolved and none lost, it's WIN.

    Returns:
        str or None: The computed result, or None if still pending
    """
    legs = get_entry_legs(entry_id)
    if not legs:
        return None

    results = [leg.get("result") for leg in legs]

    # If any leg is LOSS, the whole entry is LOSS
    if "LOSS" in results:
        update_entry_result(entry_id, "LOSS", payout=0.0)
        return "LOSS"

    # If all legs have results and none are LOSS
    if all(r in ("WIN", "EVEN") for r in results):
        if all(r == "WIN" for r in results):
            # All legs won â€” entry is a WIN
            update_entry_result(entry_id, "WIN")
            return "WIN"
        if all(r == "EVEN" for r in results):
            # All legs even â€” entry is a full EVEN (fee returned)
            update_entry_result(entry_id, "EVEN", payout=0.0)
            return "EVEN"
        # Mix of WIN and EVEN â€” standard rule: even legs are removed,
        # payout adjusts to lower leg count. Mark as EVEN for manual review.
        update_entry_result(entry_id, "EVEN", payout=0.0)
        return "EVEN"

    # Some legs still pending
    return None


def delete_entry(entry_id):
    """
    Delete a parlay entry and unlink its legs.

    Returns:
        tuple[bool, str]: (success, message)
    """
    # Unlink legs first
    _execute_write(
        "UPDATE bets SET entry_id = NULL WHERE entry_id = ?",
        (entry_id,),
        caller="delete_entry_unlink",
    )
    cursor = _execute_write(
        "DELETE FROM entries WHERE entry_id = ?",
        (entry_id,),
        caller="delete_entry",
    )
    if cursor is not None and cursor.rowcount > 0:
        return True, f"Entry #{entry_id} deleted."
    return False, f"Entry #{entry_id} not found."


def _build_bets_filter_clause(
    *,
    exclude_linked=True,
    player_search=None,
    start_date=None,
    end_date=None,
    direction=None,
    platform_terms=None,
    result_filter=None,
    tier_filter=None,
    bet_types=None,
):
    """Build SQL WHERE clause + params for reusable bet filters."""
    where_parts = []
    params = []

    if exclude_linked:
        where_parts.append("entry_id IS NULL")

    if player_search:
        where_parts.append("LOWER(COALESCE(player_name, '')) LIKE ?")
        params.append(f"%{str(player_search).strip().lower()}%")

    if start_date:
        where_parts.append("COALESCE(bet_date, '') >= ?")
        params.append(str(start_date))

    if end_date:
        where_parts.append("COALESCE(bet_date, '') <= ?")
        params.append(str(end_date))

    if direction and str(direction).upper() in {"OVER", "UNDER"}:
        where_parts.append("UPPER(COALESCE(direction, '')) = ?")
        params.append(str(direction).upper())

    if platform_terms:
        normalized_terms = [str(term).strip().lower() for term in platform_terms if str(term).strip()]
        if normalized_terms:
            term_clauses = []
            for term in normalized_terms:
                term_clauses.append("LOWER(COALESCE(platform, '')) LIKE ?")
                params.append(f"%{term}%")
            where_parts.append("(" + " OR ".join(term_clauses) + ")")

    if result_filter == "PENDING":
        where_parts.append("(result IS NULL OR result = '')")
    elif result_filter in {"WIN", "LOSS", "EVEN", "VOID"}:
        where_parts.append("result = ?")
        params.append(result_filter)

    if tier_filter and tier_filter in {"Platinum", "Gold", "Silver", "Bronze"}:
        where_parts.append("tier = ?")
        params.append(tier_filter)

    if bet_types:
        normalized_types = [str(bt).strip().lower() for bt in bet_types if str(bt).strip()]
        if normalized_types:
            placeholders = ",".join(["?"] * len(normalized_types))
            where_parts.append(f"LOWER(COALESCE(bet_type, 'standard')) IN ({placeholders})")
            params.extend(normalized_types)

    if where_parts:
        return "WHERE " + " AND ".join(where_parts), params
    return "", params


def load_bets_page(
    *,
    limit=50,
    offset=0,
    exclude_linked=True,
    player_search=None,
    start_date=None,
    end_date=None,
    direction=None,
    platform_terms=None,
    result_filter=None,
    tier_filter=None,
    bet_types=None,
):
    """Load a page of bets using DB-side filters and pagination."""
    where_sql, params = _build_bets_filter_clause(
        exclude_linked=exclude_linked,
        player_search=player_search,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        platform_terms=platform_terms,
        result_filter=result_filter,
        tier_filter=tier_filter,
        bet_types=bet_types,
    )

    query_sql = f"""
        SELECT *
        FROM bets
        {where_sql}
        ORDER BY DATE(COALESCE(bet_date, '1900-01-01')) DESC, created_at DESC NULLS LAST
        LIMIT ? OFFSET ?
    """

    try:
        return _execute_read(query_sql, tuple(params + [int(limit), int(offset)]))
    except Exception as database_error:
        _logger.error(f"Error loading paged bets: {database_error}")
        return []


def count_bets(
    *,
    exclude_linked=True,
    player_search=None,
    start_date=None,
    end_date=None,
    direction=None,
    platform_terms=None,
    result_filter=None,
    tier_filter=None,
    bet_types=None,
):
    """Count total bets for the provided filters."""
    where_sql, params = _build_bets_filter_clause(
        exclude_linked=exclude_linked,
        player_search=player_search,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        platform_terms=platform_terms,
        result_filter=result_filter,
        tier_filter=tier_filter,
        bet_types=bet_types,
    )

    query_sql = f"SELECT COUNT(*) AS total_count FROM bets {where_sql}"
    try:
        rows = _execute_read(query_sql, tuple(params))
        return int((rows[0].get("total_count") or 0) if rows else 0)
    except Exception as database_error:
        _logger.error(f"Error counting bets: {database_error}")
        return 0


def get_bets_summary(
    *,
    exclude_linked=True,
    player_search=None,
    start_date=None,
    end_date=None,
    direction=None,
    platform_terms=None,
    result_filter=None,
    tier_filter=None,
    bet_types=None,
):
    """Return summary counts for a filtered bet set."""
    where_sql, params = _build_bets_filter_clause(
        exclude_linked=exclude_linked,
        player_search=player_search,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        platform_terms=platform_terms,
        result_filter=result_filter,
        tier_filter=tier_filter,
        bet_types=bet_types,
    )

    query_sql = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN result = 'EVEN' THEN 1 ELSE 0 END) AS evens,
            SUM(CASE WHEN result IS NULL OR result = '' THEN 1 ELSE 0 END) AS pending
        FROM bets
        {where_sql}
    """

    try:
        rows = _execute_read(query_sql, tuple(params))
        row = rows[0] if rows else {}
        return {
            "total":   int(row.get("total")   or 0),
            "wins":    int(row.get("wins")    or 0),
            "losses":  int(row.get("losses")  or 0),
            "evens":   int(row.get("evens")   or 0),
            "pending": int(row.get("pending") or 0),
        }
    except Exception as database_error:
        _logger.error(f"Error summarizing bets: {database_error}")
        return {"total": 0, "wins": 0, "losses": 0, "evens": 0, "pending": 0}


def load_all_bets(limit=10000, exclude_linked=True):
    """Backward-compatible wrapper around paged bet loading."""
    return load_bets_page(limit=limit, offset=0, exclude_linked=exclude_linked)


def get_performance_summary():
    """
    Get win/loss statistics from the database.

    Returns:
        dict: Performance stats including:
            'total_bets', 'wins', 'losses', 'pushes',
            'win_rate', 'roi'
    """
    # SQL aggregation query to count outcomes (exclude parlay legs)
    summary_sql = """
    SELECT
        COUNT(*) as total_bets,
        SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN result = 'EVEN' THEN 1 ELSE 0 END) as pushes,
        CASE WHEN SUM(CASE WHEN result IN ('WIN','LOSS') THEN 1 ELSE 0 END) > 0
            THEN CAST(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS REAL)
                 / SUM(CASE WHEN result IN ('WIN','LOSS') THEN 1 ELSE 0 END)
            ELSE 0.0
        END as win_rate
    FROM bets
    WHERE result IS NOT NULL AND result != ''
      AND entry_id IS NULL
      AND (LOWER(COALESCE(bet_type, '')) != 'risky')
    """

    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(summary_sql)
            row = cursor.fetchone()

            if row:
                total = row["total_bets"] or 0
                wins = row["wins"] or 0
                losses = row["losses"] or 0
                pushes = row["pushes"] or 0
                win_rate = row["win_rate"] or 0.0

                return {
                    "total_bets": total,
                    "wins": wins,
                    "losses": losses,
                    "pushes": pushes,
                    "win_rate": round(win_rate * 100, 1),
                }

    except sqlite3.Error as database_error:
        _logger.error(f"Error getting performance summary: {database_error}")

    return {
        "total_bets": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "win_rate": 0.0,
    }


# ============================================================
# SECTION: Prediction History & Calibration (W7)
# Store prediction outcomes and compute calibration adjustments
# so the model can self-correct systematic over/underconfidence.
# ============================================================

def insert_prediction(prediction_data):
    """
    Save a model prediction to the history table. (W7)

    Call this when a bet is placed. Later, update with
    `update_prediction_outcome()` when the result is known.

    Args:
        prediction_data (dict): Prediction data with keys:
            prediction_date (str), player_name (str), stat_type (str),
            prop_line (float), direction (str), confidence_score (float),
            probability_predicted (float), notes (str, optional)

    Returns:
        int or None: The new prediction's ID, or None if error
    """
    initialize_database()  # Ensure prediction_history table exists
    insert_sql = """
    INSERT INTO prediction_history (
        prediction_date, player_name, stat_type, prop_line,
        direction, confidence_score, probability_predicted, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        prediction_data.get("prediction_date", ""),
        prediction_data.get("player_name", ""),
        prediction_data.get("stat_type", ""),
        prediction_data.get("prop_line", 0.0),
        prediction_data.get("direction", "OVER"),
        prediction_data.get("confidence_score", 0.0),
        prediction_data.get("probability_predicted", 0.5),
        prediction_data.get("notes", ""),
    )
    cursor = _execute_write(insert_sql, values, caller="insert_prediction")
    return cursor.lastrowid if cursor else None


def load_recent_predictions(days=90):
    """
    Load recent prediction records from the prediction_history table.

    Used by the calibration engine to build calibration curves and
    compute self-correction adjustments.

    Args:
        days (int): Number of past days to include. Default 90.

    Returns:
        list of dict: Prediction records with keys including
            ``probability_over`` (aliased from probability_predicted),
            ``result`` (aliased from was_correct), ``stat_type``,
            ``date`` (aliased from prediction_date), and ``created_at``.
        Empty list on cold start or database errors.
    """
    initialize_database()
    cutoff = (
        datetime.datetime.now() - datetime.timedelta(days=days)
    ).strftime("%Y-%m-%d")
    query_sql = """
    SELECT
        prediction_id,
        prediction_date  AS date,
        player_name,
        stat_type,
        prop_line,
        direction,
        confidence_score,
        probability_predicted AS probability_over,
        was_correct           AS result,
        actual_value,
        notes,
        created_at
    FROM prediction_history
    WHERE prediction_date >= ?
    ORDER BY prediction_date DESC
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query_sql, (cutoff,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        _logger.error("[database] load_recent_predictions error: %s", exc)
        return []


def update_prediction_outcome(prediction_id, was_correct, actual_value):
    """
    Record the actual outcome for a prediction. (W7)

    Args:
        prediction_id (int): The prediction's database ID
        was_correct (bool): True if the prediction was correct
        actual_value (float): The actual stat value achieved

    Returns:
        bool: True if updated successfully
    """
    update_sql = """
    UPDATE prediction_history
    SET was_correct = ?, actual_value = ?
    WHERE prediction_id = ?
    """
    cursor = _execute_write(
        update_sql,
        (1 if was_correct else 0, actual_value, prediction_id),
        caller="update_prediction_outcome",
    )
    return cursor is not None


def get_calibration_adjustment(stat_type=None, min_samples=20):
    """
    Compute a calibration adjustment for the confidence model. (W7)

    Compares the model's predicted probability to the actual
    hit rate. If the model says 62% but only 58% of picks hit,
    the calibration adjustment is +4 (subtract 4 from displayed score).

    Args:
        stat_type (str or None): Compute calibration for a specific
            stat type, or overall if None.
        min_samples (int): Minimum number of graded predictions needed
            before returning a non-zero adjustment (default: 20).
            With fewer samples, the adjustment is unreliable.

    Returns:
        float: Calibration adjustment in confidence points.
            Positive = model overestimates (subtract from score).
            Negative = model underestimates (add to score).
            Returns 0.0 if insufficient data.

    Example:
        Model predicts avg 62% probability, actual hit rate is 57%
        â†’ calibration_adjustment = +5.0 points (reduce all scores by 5)
    """
    initialize_database()  # Ensure prediction_history table exists
    if stat_type:
        query_sql = """
        SELECT
            AVG(probability_predicted) as avg_predicted_prob,
            AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
            COUNT(*) as sample_count
        FROM prediction_history
        WHERE was_correct IS NOT NULL AND stat_type = ?
        """
        params = (stat_type,)
    else:
        query_sql = """
        SELECT
            AVG(probability_predicted) as avg_predicted_prob,
            AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
            COUNT(*) as sample_count
        FROM prediction_history
        WHERE was_correct IS NOT NULL
        """
        params = ()

    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(query_sql, params)
            row = cursor.fetchone()

            if row and row["sample_count"] >= min_samples:
                avg_predicted = row["avg_predicted_prob"] or 0.5
                actual_rate = row["actual_hit_rate"] or 0.5
                # Overconfidence = model probability higher than actual hit rate
                # Convert probability gap to confidence score adjustment
                # (1% probability gap â‰ˆ 2 confidence score points)
                prob_gap_pct = (avg_predicted - actual_rate) * 100.0
                adjustment = prob_gap_pct * 2.0  # Scale to confidence score points
                # Cap adjustment to Â±15 points to avoid extreme corrections
                return round(max(-15.0, min(15.0, adjustment)), 1)

    except sqlite3.Error as database_error:
        _logger.error(f"Error computing calibration: {database_error}")

    return 0.0  # No adjustment if insufficient data


def get_calibration_report():
    """
    Build a human-readable calibration report for the Model Health page. (W7)

    Returns:
        dict: {
            'overall': dict with avg_predicted, actual_hit_rate, sample_count, adjustment
            'by_stat': dict {stat_type: same dict}
            'summary_text': str (human-readable summary)
        }
    """
    initialize_database()  # Ensure prediction_history table exists
    report = {"overall": {}, "by_stat": {}, "summary_text": ""}

    query_overall = """
    SELECT
        stat_type,
        AVG(probability_predicted) as avg_predicted_prob,
        AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
        COUNT(*) as sample_count
    FROM prediction_history
    WHERE was_correct IS NOT NULL
    GROUP BY stat_type
    ORDER BY sample_count DESC
    """

    query_all = """
    SELECT
        AVG(probability_predicted) as avg_predicted_prob,
        AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
        COUNT(*) as sample_count
    FROM prediction_history
    WHERE was_correct IS NOT NULL
    """

    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()

            # Overall calibration
            cursor.execute(query_all)
            row = cursor.fetchone()
            if row and row["sample_count"]:
                avg_p = row["avg_predicted_prob"] or 0.5
                actual = row["actual_hit_rate"] or 0.5
                report["overall"] = {
                    "avg_predicted_prob": round(avg_p * 100, 1),
                    "actual_hit_rate": round(actual * 100, 1),
                    "sample_count": row["sample_count"],
                    "calibration_adjustment": round((avg_p - actual) * 100 * 2, 1),
                }
                cal_dir = "overconfident" if avg_p > actual else "underconfident"
                report["summary_text"] = (
                    f"Model is {cal_dir}: predicts {avg_p*100:.1f}% avg but "
                    f"hits {actual*100:.1f}% ({row['sample_count']} graded predictions)"
                )

            # By stat type
            cursor.execute(query_overall)
            rows = cursor.fetchall()
            for r in rows:
                if r["sample_count"] and r["sample_count"] >= 5:
                    avg_p = r["avg_predicted_prob"] or 0.5
                    actual = r["actual_hit_rate"] or 0.5
                    report["by_stat"][r["stat_type"]] = {
                        "avg_predicted_prob": round(avg_p * 100, 1),
                        "actual_hit_rate": round(actual * 100, 1),
                        "sample_count": r["sample_count"],
                        "calibration_adjustment": round((avg_p - actual) * 100 * 2, 1),
                    }

    except sqlite3.Error as database_error:
        _logger.error(f"Error building calibration report: {database_error}")

    return report

# ============================================================
# END SECTION: Prediction History & Calibration
# ============================================================

# ============================================================
# SECTION: Daily Snapshots
# ============================================================

def save_daily_snapshot(date_str=None):
    """
    Aggregate all bets for *date_str* and write/update the daily_snapshots row.

    Args:
        date_str (str | None): ISO date string (YYYY-MM-DD). Defaults to today.

    Returns:
        bool: True on success, False on error.
    """
    import json
    import datetime as _dt

    if date_str is None:
        date_str = _dt.date.today().isoformat()

    conn = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()

        # ── DB-side aggregation (replaces full SELECT * + Python loops) ───────
        # Previous approach: load every bet row into Python memory, then run
        # four separate for-loops to build wins/losses, platform, tier, and
        # stat-type breakdowns.  On a heavy session (1000+ bets) this allocated
        # ~1000 dicts and ran O(4n) Python iterations.
        #
        # New approach: a single GROUP BY query returns only summary counts
        # (< 100 rows for any realistic slate).  All aggregation happens inside
        # SQLite's C layer — O(n) with zero Python object allocation per bet.
        cursor.execute(
            """
            SELECT
                COALESCE(result, '')         AS result,
                COALESCE(platform, 'Unknown') AS platform,
                COALESCE(tier,     'Unknown') AS tier,
                COALESCE(stat_type,'Unknown') AS stat_type,
                COUNT(*)                      AS cnt
            FROM bets
            WHERE bet_date = ? AND entry_id IS NULL
            GROUP BY
                COALESCE(result,''),
                COALESCE(platform,'Unknown'),
                COALESCE(tier,'Unknown'),
                COALESCE(stat_type,'Unknown')
            """,
            (date_str,),
        )
        summary_rows = [dict(zip([d[0] for d in cursor.description], row))
                        for row in cursor.fetchall()]

        # For best/worst pick we need two lightweight ORDER BY queries —
        # still O(1) I/O vs loading the full table into Python.
        cursor.execute(
            """
            SELECT player_name, stat_type, edge_percentage, result
            FROM bets
            WHERE bet_date = ? AND entry_id IS NULL
              AND result IN ('WIN', 'LOSS')
            ORDER BY COALESCE(edge_percentage, 0) DESC
            LIMIT 1
            """,
            (date_str,),
        )
        _best_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT player_name, stat_type, edge_percentage, result
            FROM bets
            WHERE bet_date = ? AND entry_id IS NULL
              AND result IN ('WIN', 'LOSS')
            ORDER BY COALESCE(edge_percentage, 0) ASC
            LIMIT 1
            """,
            (date_str,),
        )
        _worst_row = cursor.fetchone()
    except Exception as exc:
        _logger.error(f"[database] save_daily_snapshot read error: {exc}")
        return False
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    try:
        # ── Collapse GROUP BY rows into breakdown dicts — O(rows) not O(bets) ─
        total = wins = losses = pushes = pending = 0
        platform_breakdown: dict = {}
        tier_breakdown: dict = {}
        stat_type_breakdown: dict = {}

        for r in summary_rows:
            res   = r["result"]
            plat  = r["platform"]
            tier_ = r["tier"]
            stype = r["stat_type"]
            cnt   = int(r["cnt"])

            total += cnt
            if   res == "WIN":  wins    += cnt
            elif res == "LOSS": losses  += cnt
            elif res == "EVEN": pushes  += cnt
            else:               pending += cnt

            # Platform breakdown
            if plat not in platform_breakdown:
                platform_breakdown[plat] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            if   res == "WIN":  platform_breakdown[plat]["wins"]    += cnt
            elif res == "LOSS": platform_breakdown[plat]["losses"]  += cnt
            elif res == "EVEN": platform_breakdown[plat]["pushes"]  += cnt
            else:               platform_breakdown[plat]["pending"] += cnt

            # Tier breakdown
            if tier_ not in tier_breakdown:
                tier_breakdown[tier_] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            if   res == "WIN":  tier_breakdown[tier_]["wins"]    += cnt
            elif res == "LOSS": tier_breakdown[tier_]["losses"]  += cnt
            elif res == "EVEN": tier_breakdown[tier_]["pushes"]  += cnt
            else:               tier_breakdown[tier_]["pending"] += cnt

            # Stat-type breakdown
            if stype not in stat_type_breakdown:
                stat_type_breakdown[stype] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            if   res == "WIN":  stat_type_breakdown[stype]["wins"]    += cnt
            elif res == "LOSS": stat_type_breakdown[stype]["losses"]  += cnt
            elif res == "EVEN": stat_type_breakdown[stype]["pushes"]  += cnt
            else:               stat_type_breakdown[stype]["pending"] += cnt

        win_rate = round(wins / (wins + losses) * 100, 2) if (wins + losses) > 0 else 0.0

        # ── Best / worst pick from targeted ORDER BY queries ──────────────────
        best_pick = worst_pick = ""
        if _best_row:
            best_pick = json.dumps({
                "player": _best_row[0], "stat": _best_row[1],
                "edge": _best_row[2],   "result": _best_row[3],
            })
        if _worst_row:
            worst_pick = json.dumps({
                "player": _worst_row[0], "stat": _worst_row[1],
                "edge": _worst_row[2],   "result": _worst_row[3],
            })

        _upsert_sql = """
            INSERT INTO daily_snapshots
                (snapshot_date, total_picks, wins, losses, pushes, pending,
                 win_rate, platform_breakdown, tier_breakdown, stat_type_breakdown,
                 best_pick, worst_pick)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date) DO UPDATE SET
                total_picks        = excluded.total_picks,
                wins               = excluded.wins,
                losses             = excluded.losses,
                pushes             = excluded.pushes,
                pending            = excluded.pending,
                win_rate           = excluded.win_rate,
                platform_breakdown = excluded.platform_breakdown,
                tier_breakdown     = excluded.tier_breakdown,
                stat_type_breakdown = excluded.stat_type_breakdown,
                best_pick          = excluded.best_pick,
                worst_pick         = excluded.worst_pick
            """
        _upsert_params = (
            date_str, total, wins, losses, pushes, pending, win_rate,
            json.dumps(platform_breakdown), json.dumps(tier_breakdown),
            json.dumps(stat_type_breakdown), best_pick, worst_pick,
        )
        result = _execute_write(_upsert_sql, _upsert_params, caller="save_daily_snapshot")
        return result is not None
    except Exception as exc:
        _logger.error(f"[database] save_daily_snapshot error: {exc}")
        return False


def load_daily_snapshots(days=14):
    """Return the last *days* rows from daily_snapshots, newest first.

    Returns:
        list[dict]
    """
    import json

    conn = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM daily_snapshots
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (days,),
        )
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        conn.close()
        conn = None
        snapshots = []
        for row in rows:
            s = dict(zip(cols, row))
            for field in ("platform_breakdown", "tier_breakdown", "stat_type_breakdown"):
                try:
                    s[field] = json.loads(s.get(field) or "{}")
                except Exception:
                    s[field] = {}
            for field in ("best_pick", "worst_pick"):
                try:
                    s[field] = json.loads(s.get(field) or "{}")
                except Exception:
                    s[field] = {}
            snapshots.append(s)
        return snapshots
    except Exception as exc:
        _logger.error(f"[database] load_daily_snapshots error: {exc}")
        return []
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def purge_old_snapshots(days=30):
    """Delete snapshots older than *days* days.

    Returns:
        int: Number of rows deleted.
    """
    import datetime as _dt

    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    conn = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM daily_snapshots WHERE snapshot_date < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    except Exception as exc:
        _logger.error(f"[database] purge_old_snapshots error: {exc}")
        return 0
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def purge_stale_game_logs(days=30):
    """Delete cached player game logs older than *days* days.

    The ``player_game_logs`` table is a local cache that accumulates
    indefinitely.  Pruning entries whose ``retrieved_at`` timestamp is older
    than the cutoff keeps the database lean without losing analytical value
    (the ETL ``Player_Game_Logs`` table retains the canonical history).

    Returns:
        int: Number of rows deleted.
    """
    import datetime as _dt

    cutoff = (_dt.datetime.now() - _dt.timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM player_game_logs WHERE retrieved_at < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount
        conn.commit()
        _logger.info("[database] purge_stale_game_logs: removed %d rows", deleted)
        return deleted
    except Exception as exc:
        _logger.error("[database] purge_stale_game_logs error: %s", exc)
        return 0
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def purge_old_sessions(days=90):
    """Delete analysis sessions older than *days* days.

    The ``analysis_sessions`` table stores full JSON blobs per run and
    grows without bound.  Archiving old sessions recovers disk space.

    Returns:
        int: Number of rows deleted.
    """
    import datetime as _dt

    cutoff = (_dt.datetime.now() - _dt.timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM analysis_sessions WHERE created_at < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount
        conn.commit()
        _logger.info("[database] purge_old_sessions: removed %d rows", deleted)
        return deleted
    except Exception as exc:
        _logger.error("[database] purge_old_sessions error: %s", exc)
        return 0
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def purge_old_backtest_results(keep=50):
    """Keep only the most recent *keep* backtest result rows.

    Returns:
        int: Number of rows deleted.
    """
    conn = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM backtest_results WHERE backtest_id NOT IN "
            "(SELECT backtest_id FROM backtest_results "
            "ORDER BY created_at DESC LIMIT ?)",
            (keep,),
        )
        deleted = cursor.rowcount
        conn.commit()
        _logger.info("[database] purge_old_backtest_results: removed %d rows", deleted)
        return deleted
    except Exception as exc:
        _logger.error("[database] purge_old_backtest_results error: %s", exc)
        return 0
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# â”€â”€ Maintenance defaults â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_MAINTENANCE_SNAPSHOT_DAYS = 30
_MAINTENANCE_GAME_LOG_DAYS = 30
_MAINTENANCE_SESSION_DAYS = 90
_MAINTENANCE_BACKTEST_KEEP = 50


def run_maintenance(
    *,
    snapshot_days=_MAINTENANCE_SNAPSHOT_DAYS,
    game_log_days=_MAINTENANCE_GAME_LOG_DAYS,
    session_days=_MAINTENANCE_SESSION_DAYS,
    backtest_keep=_MAINTENANCE_BACKTEST_KEEP,
):
    """Run all database cleanup routines and VACUUM.

    Combines snapshot, game-log, session, and backtest pruning into a
    single convenience call, then runs VACUUM to reclaim disk space.

    Args:
        snapshot_days: Delete snapshots older than this many days.
        game_log_days: Delete cached game logs older than this many days.
        session_days: Delete analysis sessions older than this many days.
        backtest_keep: Number of most-recent backtest runs to retain.

    Returns:
        dict: Summary with keys ``snapshots``, ``game_logs``, ``sessions``,
              ``backtests`` (each the number of rows deleted) and
              ``vacuumed`` (bool).
    """
    result = {
        "snapshots": purge_old_snapshots(days=snapshot_days),
        "game_logs": purge_stale_game_logs(days=game_log_days),
        "sessions": purge_old_sessions(days=session_days),
        "backtests": purge_old_backtest_results(keep=backtest_keep),
        "vacuumed": False,
    }
    conn = None
    try:
        conn = get_database_connection()
        conn.execute("VACUUM")
        result["vacuumed"] = True
        _logger.info("[database] run_maintenance: VACUUM completed")
    except Exception as exc:
        _logger.error("[database] run_maintenance VACUUM error: %s", exc)
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
    _logger.info("[database] run_maintenance complete: %s", result)
    return result


def get_rolling_stats(days=14):
    """Compute rolling win rate, current streak, best/worst day from snapshots.

    Returns:
        dict with keys: total_bets, total_wins, total_losses, total_pushes,
                        win_rate, streak (int, positive=win streak, negative=loss streak),
                        best_day (dict), worst_day (dict), snapshots (list)
    """
    snapshots = load_daily_snapshots(days)
    if not snapshots:
        return {
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "total_pushes": 0,
            "win_rate": 0.0,
            "streak": 0,
            "best_day": {},
            "worst_day": {},
            "snapshots": [],
        }

    total_bets = sum(s.get("total_picks", 0) for s in snapshots)
    total_wins = sum(s.get("wins", 0) for s in snapshots)
    total_losses = sum(s.get("losses", 0) for s in snapshots)
    total_pushes = sum(s.get("pushes", 0) for s in snapshots)
    win_rate = round(total_wins / max(total_wins + total_losses, 1) * 100, 1)

    # Current streak: walk individual resolved bets newest→oldest.
    # This matches the individual-bet streak displayed in Health tab summary cards.
    try:
        _recent_bets = load_all_bets(limit=500)
        _cutoff = (
            __import__("datetime").date.today()
            - __import__("datetime").timedelta(days=days)
        ).isoformat()
        _resolved_bets = sorted(
            [
                b for b in _recent_bets
                if b.get("result") in ("WIN", "LOSS")
                and str(b.get("bet_date", ""))[:10] >= _cutoff
            ],
            key=lambda b: (b.get("bet_date", ""), b.get("id", 0)),
            reverse=True,  # newest first
        )
        streak = 0
        if _resolved_bets:
            _first = _resolved_bets[0].get("result")
            streak = 1 if _first == "WIN" else -1
            for _b in _resolved_bets[1:]:
                _r = _b.get("result")
                if streak > 0 and _r == "WIN":
                    streak += 1
                elif streak < 0 and _r == "LOSS":
                    streak -= 1
                else:
                    break
    except Exception:
        # Fall back to day-level streak if bets can't be loaded
        streak = 0
        for snap in snapshots:
            w = snap.get("wins", 0)
            l = snap.get("losses", 0)
            if w + l == 0:
                continue
            day_wr = w / (w + l)
            if streak == 0:
                streak = 1 if day_wr >= 0.5 else -1
            elif streak > 0 and day_wr >= 0.5:
                streak += 1
            elif streak < 0 and day_wr < 0.5:
                streak -= 1
            else:
                break

    resolved = [s for s in snapshots if (s.get("wins", 0) + s.get("losses", 0)) > 0]
    best_day = max(resolved, key=lambda s: s.get("win_rate", 0)) if resolved else {}
    worst_day = min(resolved, key=lambda s: s.get("win_rate", 0)) if resolved else {}

    return {
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_pushes": total_pushes,
        "win_rate": win_rate,
        "streak": streak,
        "best_day": best_day,
        "worst_day": worst_day,
        "snapshots": snapshots,
    }

# ============================================================
# END SECTION: Daily Snapshots
# ============================================================

# ============================================================
# SECTION: All Analysis Picks â€” Store and Load
# ============================================================

def insert_analysis_picks(analysis_results):
    """
    Persist all Neural Analysis output picks to the all_analysis_picks table.

    Deduplicates by (pick_date, player_name, stat_type, prop_line, direction,
    platform) so re-runs do not duplicate the same pick while still preserving
    distinct platform variants.

    Args:
        analysis_results (list[dict]): Full list of analysis result dicts from
            Neural Analysis (as stored in st.session_state["analysis_results"]).

    Returns:
        int: Number of new rows inserted.
    """
    if not analysis_results:
        return 0

    today_str = _nba_today_iso()
    inserted = 0

    if _DATABASE_URL:
        inserted = _pg_insert_analysis_picks(analysis_results, today_str)
        if inserted > 0:
            _write_latest_picks_cache(today_str)
        return inserted

    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                # Dedup key includes line + platform to preserve distinct props.
                existing = {}  # key → pick_id for update
                for row in conn.execute(
                    "SELECT pick_id, lower(player_name), stat_type, prop_line, direction, COALESCE(platform, '') "
                    "FROM all_analysis_picks WHERE pick_date = ?",
                    (today_str,),
                ).fetchall():
                    _k = (
                        row[1],
                        row[2],
                        round(float(row[3] or 0), 2),
                        str(row[4] or "OVER").upper(),
                        str(row[5] or "").strip().lower(),
                    )
                    existing[_k] = row[0]

                for r in analysis_results:
                    _line = round(float(r.get("line", 0) or 0), 2)
                    _platform = str(r.get("platform", "") or "").strip().lower()
                    key = (
                        r.get("player_name", "").lower(),
                        r.get("stat_type", ""),
                        _line,
                        str(r.get("direction", "OVER") or "OVER").upper(),
                        _platform,
                    )
                    if key in existing:
                        # Refresh the existing identical pick row.
                        conn.execute(
                            """UPDATE all_analysis_picks
                               SET prop_line = ?, confidence_score = ?,
                                   probability_over = ?, edge_percentage = ?,
                                   tier = ?, notes = ?, bet_type = ?, platform = ?,
                                   std_devs_from_line = ?, is_risky = ?
                               WHERE pick_id = ?""",
                            (
                                _line,
                                float(r.get("confidence_score", 0) or 0),
                                float(r.get("probability_over", 0.5) or 0.5),
                                float(r.get("edge_percentage", 0) or 0),
                                r.get("tier", "Bronze"),
                                f"Auto-stored by Smart Pick Pro. SAFE Score: {r.get('confidence_score', 0):.0f}",
                                r.get("bet_type", "normal"),
                                r.get("platform", ""),
                                float(r.get("std_devs_from_line", 0.0)),
                                1 if r.get("should_avoid", False) else 0,
                                existing[key],
                            ),
                        )
                        continue
                    _cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO all_analysis_picks
                            (pick_date, player_name, team, stat_type, prop_line,
                             direction, platform, confidence_score, probability_over,
                             edge_percentage, tier, result, actual_value, notes,
                             bet_type, std_devs_from_line, is_risky)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
                        """,
                        (
                            today_str,
                            r.get("player_name", ""),
                            r.get("player_team", r.get("team", "")),
                            r.get("stat_type", ""),
                            _line,
                            r.get("direction", "OVER"),
                            r.get("platform", ""),
                            float(r.get("confidence_score", 0) or 0),
                            float(r.get("probability_over", 0.5) or 0.5),
                            float(r.get("edge_percentage", 0) or 0),
                            r.get("tier", "Bronze"),
                            f"Auto-stored by Smart Pick Pro. SAFE Score: {r.get('confidence_score', 0):.0f}",
                            r.get("bet_type", "normal"),
                            float(r.get("std_devs_from_line", 0.0)),
                            1 if r.get("should_avoid", False) else 0,
                        ),
                    )
                    if _cursor.rowcount > 0:
                        existing[key] = _cursor.lastrowid
                        inserted += 1
                conn.commit()
            break  # success â€” exit retry loop
        except sqlite3.OperationalError as op_err:
            if "locked" in str(op_err).lower() and _attempt < _WRITE_RETRY_ATTEMPTS - 1:
                _logger.warning(
                    f"insert_analysis_picks: database locked, retry "
                    f"{_attempt + 1}/{_WRITE_RETRY_ATTEMPTS}"
                )
                time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
                # Reset: the fresh retry re-reads existing keys so
                # deduplication is re-applied and no duplicates arise.
                inserted = 0
                continue
            _logger.warning(f"insert_analysis_picks error (non-fatal): {op_err}")
        except Exception as err:
            _logger.warning(f"insert_analysis_picks error (non-fatal): {err}")
            break  # non-retryable error

    # Write a JSON cache of today's top picks for the landing page preview.
    # This ensures the auth-gate landing page shows real picks even when
    # the DB is empty (e.g. fresh Railway deploy before analysis runs).
    if inserted > 0:
        _write_latest_picks_cache(today_str)

    return inserted


def _write_latest_picks_cache(date_str: str, limit: int = 5) -> None:
    """Persist today's top analysis picks to ``cache/latest_picks.json``.

    Called automatically after ``insert_analysis_picks`` succeeds.
    Supports both PostgreSQL (Railway) and SQLite (local dev).

    Also bumps the DB-backed data_version so *any* running Streamlit
    container (not just the one that wrote picks) detects fresh data.
    """
    import json as _json
    try:
        if _DATABASE_URL:
            # ── PostgreSQL path ──────────────────────────────────────────
            rows_data: list[dict] = []
            try:
                conn = _pg_conn()
                cur = conn.cursor()
                cur.execute(
                    """SELECT player_name, team, stat_type, prop_line, direction,
                              platform, confidence_score, probability_over,
                              edge_percentage, tier
                       FROM all_analysis_picks
                       WHERE pick_date = %s
                       ORDER BY confidence_score DESC
                       LIMIT %s""",
                    (date_str, limit),
                )
                cols = [d[0] for d in cur.description]
                rows_data = [dict(zip(cols, row)) for row in cur.fetchall()]
                conn.close()
            except Exception as pg_err:
                _logger.debug("_write_latest_picks_cache PG query: %s", pg_err)
            if not rows_data:
                return
            cache_data = {"date": date_str, "picks": rows_data}
        else:
            # ── SQLite path ──────────────────────────────────────────────
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT player_name, team, stat_type, prop_line, direction,
                              platform, confidence_score, probability_over,
                              edge_percentage, tier
                       FROM all_analysis_picks
                       WHERE pick_date = ?
                       ORDER BY confidence_score DESC
                       LIMIT ?""",
                    (date_str, limit),
                ).fetchall()
                if not rows:
                    return
                cache_data = {"date": date_str, "picks": [dict(r) for r in rows]}

        cache_path = Path(__file__).parent.parent / "cache" / "latest_picks.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(_json.dumps(cache_data, indent=2), encoding="utf-8")
        _logger.debug("Wrote %d picks to %s", len(cache_data["picks"]), cache_path)
        # Bump the shared data-version stamp so running Streamlit sessions
        # detect the new picks and re-seed session state from the DB.
        _bump_data_version(date_str)
        # Auto-commit the cache file to git so Railway deploys carry today's picks.
        _git_commit_cache(cache_path, date_str)
    except Exception as exc:
        _logger.debug("_write_latest_picks_cache: %s", exc)


def _bump_data_version(date_str: str) -> None:
    """Write a data-version stamp that any Streamlit container can detect.

    Two mechanisms:
    1. ``cache/data_version.json`` — file-based; works in-process.
    2. DB row in ``app_state`` table — survives container restarts and is
       readable by any container connected to the same PostgreSQL database,
       so GitHub Actions CI runs can signal the running app to refresh.
    """
    import json as _json, time as _time
    _ver = _time.time()
    # ── File stamp (in-process / single-container awareness) ─────────────
    try:
        version_path = Path(__file__).parent.parent / "cache" / "data_version.json"
        version_path.parent.mkdir(parents=True, exist_ok=True)
        version_path.write_text(
            _json.dumps({"version": _ver, "date": date_str}),
            encoding="utf-8",
        )
    except Exception as exc:
        _logger.debug("_bump_data_version (file): %s", exc)
    # ── DB stamp (cross-container / cross-deploy awareness) ───────────────
    # Store version as a row in app_state(key TEXT PRIMARY KEY, value TEXT).
    # The home page reads this via get_data_version() so any container
    # (including GitHub Actions CI) can signal a Streamlit session to refresh.
    try:
        if _DATABASE_URL:
            conn = _pg_conn()
            cur = conn.cursor()
            # Create table if missing (idempotent)
            cur.execute(
                "CREATE TABLE IF NOT EXISTS app_state "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMPTZ DEFAULT NOW())"
            )
            cur.execute(
                "INSERT INTO app_state (key, value, updated_at) VALUES ('data_version', %s, NOW()) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
                (str(_ver),),
            )
            conn.commit()
            conn.close()
        else:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS app_state "
                    "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)"
                )
                conn.execute(
                    "INSERT OR REPLACE INTO app_state (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                    ("data_version", str(_ver)),
                )
    except Exception as exc:
        _logger.debug("_bump_data_version (db): %s", exc)


def get_data_version() -> float:
    """Read the current data version from the DB (cross-container safe).

    Returns the version as a float timestamp (seconds since epoch).
    Falls back to reading ``cache/data_version.json`` if DB is unavailable.
    Returns 0.0 if both sources are unavailable.
    """
    import json as _json
    # ── Primary: DB (works across container restarts and CI writes) ───────
    try:
        if _DATABASE_URL:
            rows = _pg_execute_read(
                "SELECT value FROM app_state WHERE key = 'data_version'"
            )
            if rows:
                return float(rows[0]["value"])
        else:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                row = conn.execute(
                    "SELECT value FROM app_state WHERE key = 'data_version'"
                ).fetchone()
                if row:
                    return float(row[0])
    except Exception:
        pass
    # ── Fallback: file stamp ──────────────────────────────────────────────
    try:
        import json as _j
        vp = Path(__file__).parent.parent / "cache" / "data_version.json"
        if vp.exists():
            return float(_j.loads(vp.read_text(encoding="utf-8")).get("version", 0))
    except Exception:
        pass
    return 0.0


def _git_commit_cache(cache_path: Path, date_str: str) -> None:
    """Stage and commit cache/latest_picks.json to git (best-effort, non-blocking).

    This ensures that when Railway redeploys from git the landing page always
    shows the most recent real picks rather than the previous deploy's snapshot.
    Silently skips if git is not available or the repo has no remote configured.
    """
    import subprocess as _sp
    try:
        repo_root = cache_path.parent.parent
        _sp.run(
            ["git", "add", str(cache_path.relative_to(repo_root))],
            cwd=str(repo_root), capture_output=True, timeout=10, check=False,
        )
        result = _sp.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(repo_root), capture_output=True, timeout=5,
        )
        if result.returncode != 0:  # there are staged changes
            _sp.run(
                ["git", "commit", "-m", f"chore: update picks cache {date_str} [skip ci]"],
                cwd=str(repo_root), capture_output=True, timeout=15, check=False,
            )
            _sp.run(
                ["git", "push", "origin", "HEAD"],
                cwd=str(repo_root), capture_output=True, timeout=30, check=False,
            )
            _logger.debug("_git_commit_cache: committed and pushed picks for %s", date_str)
    except Exception as exc:
        _logger.debug("_git_commit_cache (non-fatal): %s", exc)


def load_all_analysis_picks(days=30):
    """
    Load all Neural Analysis output picks from the database.

    Args:
        days (int): Number of days of history to load. Defaults to 30.

    Returns:
        list[dict]: List of pick dicts with columns as keys.
    """
    import datetime as _dt
    cutoff = (
        datetime.date.fromisoformat(_nba_today_iso()) - _dt.timedelta(days=days)
    ).isoformat()
    try:
        return _execute_read(
            "SELECT * FROM all_analysis_picks WHERE pick_date >= ? ORDER BY pick_date DESC, confidence_score DESC",
            (cutoff,),
        )
    except Exception as err:
        _logger.warning(f"load_all_analysis_picks error (non-fatal): {err}")
        return []

def update_analysis_pick_result(pick_id, result, actual_value):
    """
    Write a WIN / LOSS / EVEN result back to a row in all_analysis_picks.

    Args:
        pick_id (int): Primary key of the row in all_analysis_picks.
        result (str): 'WIN', 'LOSS', or 'EVEN'.
        actual_value (float): The player's actual stat value.

    Returns:
        bool: True if a row was updated, False otherwise.
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.execute(
                "UPDATE all_analysis_picks SET result = ?, actual_value = ? WHERE pick_id = ?",
                (result, float(actual_value), int(pick_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as err:
        _logger.warning(f"update_analysis_pick_result error (non-fatal): {err}")
        return False


def load_pending_analysis_picks(limit=2000):
    """
    Load all rows from all_analysis_picks that have not yet been resolved
    (result IS NULL or result = '').

    Args:
        limit (int): Maximum rows to return.

    Returns:
        list[dict]: Pending pick rows as dicts.
    """
    try:
        return _execute_read(
            """SELECT * FROM all_analysis_picks
               WHERE (result IS NULL OR result = '')
               ORDER BY pick_date ASC
               LIMIT ?""",
            (limit,),
        )
    except Exception as err:
        _logger.warning(f"load_pending_analysis_picks error (non-fatal): {err}")
        return []


def load_analysis_picks_for_date(date_str):
    """
    Load ALL picks (resolved and pending) from all_analysis_picks for a
    specific date so users can review and re-resolve a past night's picks.

    Args:
        date_str (str): ISO date string "YYYY-MM-DD".

    Returns:
        list[dict]: Pick rows for that date ordered by confidence_score DESC.
    """
    try:
        return _execute_read(
            "SELECT * FROM all_analysis_picks WHERE pick_date = ? ORDER BY confidence_score DESC",
            (date_str,),
        )
    except Exception as err:
        _logger.warning(f"load_analysis_picks_for_date error (non-fatal): {err}")
        return []


def get_analysis_pick_dates(days=30):
    """
    Return a sorted list (newest first) of distinct pick_date values from BOTH
    the all_analysis_picks table AND the bets table within the last *days* days.

    This ensures dates that only exist in the bets table (e.g. manually-added or
    SQL-inserted bets) still appear in the date dropdowns on the All Picks and
    Resolve tabs.

    Args:
        days (int): How many days of history to scan. Defaults to 30.

    Returns:
        list[str]: ISO date strings, e.g. ["2026-04-21", "2026-04-20", ...].
    """
    import datetime as _dt
    cutoff = (
        datetime.date.fromisoformat(_nba_today_iso()) - _dt.timedelta(days=days)
    ).isoformat()
    dates_set = set()

    # ── Source 1: all_analysis_picks (SQLite local) ──────────────────────────
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            rows = conn.execute(
                "SELECT DISTINCT pick_date FROM all_analysis_picks WHERE pick_date >= ? ORDER BY pick_date DESC",
                (cutoff,),
            ).fetchall()
            for r in rows:
                if r[0]:
                    dates_set.add(r[0])
    except Exception as err:
        _logger.warning(f"get_analysis_pick_dates (SQLite) error: {err}")

    # ── Source 2: bets table (PostgreSQL when available, else SQLite) ─────────
    try:
        bets_date_rows = _execute_read(
            "SELECT DISTINCT bet_date FROM bets WHERE bet_date >= ? AND bet_date IS NOT NULL AND bet_date != ''",
            (cutoff,),
        )
        for r in bets_date_rows:
            d = r.get("bet_date") or r.get("DISTINCT bet_date", "")
            if d:
                dates_set.add(str(d)[:10])  # trim to YYYY-MM-DD if timestamp
    except Exception as err:
        _logger.warning(f"get_analysis_pick_dates (bets table) error: {err}")

    return sorted(dates_set, reverse=True)

# ============================================================
# END SECTION: All Analysis Picks
# ============================================================

# ============================================================
# SECTION: Analysis Session Persistence
# Saves and restores full Neural Analysis results to SQLite so
# users never lose their analysis after page refresh or inactivity.
# ============================================================

def save_analysis_session(analysis_results, todays_games=None, selected_picks=None):
    """
    Persist a full Neural Analysis session to SQLite.

    Args:
        analysis_results (list[dict]): Full analysis results list from Neural Analysis.
        todays_games (list[dict]|None): Tonight's games list.
        selected_picks (list[dict]|None): Currently selected picks.

    Returns:
        int: The new session_id, or -1 on error.
    """
    try:
        initialize_database()
        _ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        _results_json = json.dumps(analysis_results, default=str)
        _games_json = json.dumps(todays_games or [], default=str)
        _picks_json = json.dumps(selected_picks or [], default=str)
        _prop_count = len(analysis_results)
        cursor = _execute_write(
            """INSERT INTO analysis_sessions
               (analysis_timestamp, analysis_results_json, todays_games_json,
                selected_picks_json, prop_count)
               VALUES (?, ?, ?, ?, ?)""",
            (_ts, _results_json, _games_json, _picks_json, _prop_count),
            caller="save_analysis_session",
        )
        return cursor.lastrowid if cursor else -1
    except Exception as _err:
        _logger.warning(f"save_analysis_session error (non-fatal): {_err}")
        return -1


def load_latest_analysis_session():
    """
    Load the most recently saved Neural Analysis session from SQLite.

    Returns:
        dict|None: Session dict with keys:
            'analysis_timestamp', 'analysis_results', 'todays_games', 'selected_picks',
            'prop_count', 'created_at'
        Returns None if no session found or on error.
    """
    try:
        import zoneinfo as _zi
        _today_et = datetime.datetime.now(_zi.ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        _today_et = datetime.date.today().isoformat()
    try:
        rows = _execute_read(
            """SELECT * FROM analysis_sessions
               WHERE substr(analysis_timestamp, 1, 10) = ?
               ORDER BY session_id DESC LIMIT 1""",
            (_today_et,),
        )
        if not rows:
            return None
        row_dict = dict(rows[0])
        try:
            row_dict["analysis_results"] = json.loads(row_dict.get("analysis_results_json") or "[]")
        except Exception:
            row_dict["analysis_results"] = []
        try:
            row_dict["todays_games"] = json.loads(row_dict.get("todays_games_json") or "[]")
        except Exception:
            row_dict["todays_games"] = []
        try:
            row_dict["selected_picks"] = json.loads(row_dict.get("selected_picks_json") or "[]")
        except Exception:
            row_dict["selected_picks"] = []
        return row_dict
    except Exception as _err:
        _logger.warning(f"load_latest_analysis_session error (non-fatal): {_err}")
        return None

# ============================================================
# END SECTION: Analysis Session Persistence
# ============================================================

# ============================================================
# SECTION: Backtest Results Persistence
# Saves and retrieves historical backtesting runs so results
# survive page reloads and can be compared across time.
# ============================================================

def save_backtest_result(backtest_result):
    """
    Persist a backtest run to the database.

    Args:
        backtest_result (dict): The dict returned by engine/backtester.run_backtest().

    Returns:
        int or None: The new backtest_id on success, None on error.

    Example:
        result = run_backtest(season="2024-25", stat_types=["points"])
        save_backtest_result(result)
    """
    if not backtest_result or backtest_result.get("status") != "ok":
        return None
    try:
        run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        stat_types_json = json.dumps(backtest_result.get("stat_types", []))
        tier_win_rates_json = json.dumps(backtest_result.get("tier_win_rates", {}))
        stat_win_rates_json = json.dumps(backtest_result.get("stat_win_rates", {}))
        edge_win_rates_json = json.dumps(backtest_result.get("edge_win_rates", {}))
        pick_log_json = json.dumps(backtest_result.get("pick_log", []))

        cursor = _execute_write(
            """
            INSERT INTO backtest_results (
                run_timestamp, season, stat_types_json, min_edge, tier_filter,
                total_picks, wins, losses, win_rate, roi, total_pnl,
                tier_win_rates_json, stat_win_rates_json, edge_win_rates_json,
                pick_log_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_ts,
                backtest_result.get("season", ""),
                stat_types_json,
                backtest_result.get("min_edge", 0.05),
                backtest_result.get("tier_filter"),
                backtest_result.get("total_picks", 0),
                backtest_result.get("wins", 0),
                backtest_result.get("losses", 0),
                backtest_result.get("win_rate", 0.0),
                backtest_result.get("roi", 0.0),
                backtest_result.get("total_pnl", 0.0),
                tier_win_rates_json,
                stat_win_rates_json,
                edge_win_rates_json,
                pick_log_json,
            ),
            caller="save_backtest_result",
        )
        return cursor.lastrowid if cursor else None
    except Exception as _err:
        _logger.error(f"save_backtest_result error: {_err}")
        return None


def load_backtest_results(limit=20):
    """
    Load the most recent backtest runs from the database.

    Args:
        limit (int): Maximum number of runs to return (default 20).

    Returns:
        list of dict: Recent backtest result rows, newest first.

    Example:
        results = load_backtest_results(limit=5)
        for r in results:
            print(r["season"], r["win_rate"])
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM backtest_results
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                row_dict = dict(row)
                # Deserialize JSON fields â€” handle None, empty string, and invalid JSON
                for json_field in ("stat_types_json", "tier_win_rates_json",
                                   "stat_win_rates_json", "edge_win_rates_json",
                                   "pick_log_json"):
                    raw_value = row_dict.get(json_field)
                    if raw_value:
                        try:
                            row_dict[json_field] = json.loads(raw_value)
                        except (json.JSONDecodeError, TypeError):
                            row_dict[json_field] = None
                    else:
                        row_dict[json_field] = None
                results.append(row_dict)
            return results
    except Exception as _err:
        _logger.warning(f"load_backtest_results error (non-fatal): {_err}")
        return []

# ============================================================
# END SECTION: Backtest Results Persistence
# ============================================================


# ============================================================
# SECTION: Player Game Logs Persistence (Feature 12)
# Store and retrieve player game logs from SQLite so the KDE
# simulation engine has reliable data across browser refreshes.
# ============================================================

def save_player_game_logs_to_db(player_id, player_name, game_logs):
    """
    Persist a list of player game log rows to the player_game_logs table.

    Uses INSERT OR REPLACE so re-running the retrieval doesn't create
    duplicate rows (the UNIQUE constraint on player_id + game_date
    handles deduplication).

    Args:
        player_id (str): NBA API player ID
        player_name (str): Player display name
        game_logs (list[dict]): List of game log dicts with keys:
            game_date, opponent, minutes, points, rebounds, assists,
            threes, steals, blocks, turnovers, fg_pct, ft_pct, plus_minus

    Returns:
        int: Number of rows inserted/replaced.
    """
    if not game_logs:
        return 0

    import datetime as _dt
    retrieved_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    inserted = 0

    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                for g in game_logs:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO player_game_logs
                            (player_id, player_name, game_date, opponent,
                             minutes, points, rebounds, assists, threes,
                             steals, blocks, turnovers, fg_pct, ft_pct,
                             plus_minus, retrieved_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(player_id),
                            str(player_name),
                            str(g.get("game_date", g.get("GAME_DATE", ""))),
                            str(g.get("opponent", g.get("MATCHUP", ""))),
                            _safe_float(g.get("minutes", g.get("MIN", g.get("min")))),
                            _safe_int(g.get("points",    g.get("PTS", g.get("pts")))),
                            _safe_int(g.get("rebounds",  g.get("REB", g.get("reb")))),
                            _safe_int(g.get("assists",   g.get("AST", g.get("ast")))),
                            _safe_int(g.get("threes",    g.get("FG3M", g.get("fg3m")))),
                            _safe_int(g.get("steals",    g.get("STL", g.get("stl")))),
                            _safe_int(g.get("blocks",    g.get("BLK", g.get("blk")))),
                            _safe_int(g.get("turnovers", g.get("TOV", g.get("tov")))),
                            _safe_float(g.get("fg_pct",  g.get("FG_PCT", g.get("fg_pct")))),
                            _safe_float(g.get("ft_pct",  g.get("FT_PCT", g.get("ft_pct")))),
                            _safe_int(g.get("plus_minus", g.get("PLUS_MINUS", g.get("plus_minus")))),
                            retrieved_at,
                        ),
                    )
                    inserted += 1
                conn.commit()
            break  # success â€” exit retry loop
        except sqlite3.OperationalError as op_err:
            if "locked" in str(op_err).lower() and _attempt < _WRITE_RETRY_ATTEMPTS - 1:
                _logger.warning(
                    f"save_player_game_logs_to_db: database locked, retry "
                    f"{_attempt + 1}/{_WRITE_RETRY_ATTEMPTS}"
                )
                time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
                # Reset: INSERT OR REPLACE handles deduplication, so
                # re-inserting the same rows is idempotent.
                inserted = 0
                continue
            _logger.warning(f"save_player_game_logs_to_db error (non-fatal): {op_err}")
        except Exception as err:
            _logger.warning(f"save_player_game_logs_to_db error (non-fatal): {err}")
            break  # non-retryable error

    return inserted


def _safe_float(value, default=None):
    """Safely convert a value to float, returning default on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=None):
    """Safely convert a value to int, returning default on failure."""
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_player_game_logs_from_db(player_id, days=60):
    """
    Load cached game logs for a player from SQLite.

    Args:
        player_id (str): NBA API player ID.
        days (int): How many days of history to return. Defaults to 60.

    Returns:
        list[dict]: Game log rows ordered most-recent-first.
            Returns empty list if no data or on error.
    """
    import datetime as _dt
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    rows = []
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM player_game_logs
                WHERE player_id = ? AND game_date >= ?
                ORDER BY game_date DESC
                """,
                (str(player_id), cutoff),
            )
            rows = [dict(row) for row in cursor.fetchall()]
    except Exception as err:
        _logger.warning(f"load_player_game_logs_from_db error (non-fatal): {err}")
    return rows


def is_game_log_cache_stale(player_id, max_age_hours=24):
    """
    Check whether the cached game logs for a player are stale.

    Args:
        player_id (str): NBA API player ID.
        max_age_hours (int): Age threshold in hours. Defaults to 24.

    Returns:
        bool: True if cache is missing or older than max_age_hours.
    """
    import datetime as _dt
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute(
                "SELECT MAX(retrieved_at) FROM player_game_logs WHERE player_id = ?",
                (str(player_id),),
            ).fetchone()
            if not row or not row[0]:
                return True
            latest_ts = _dt.datetime.fromisoformat(str(row[0]))
            # Ensure both sides are tz-aware (UTC) to avoid
            # "can't subtract offset-naive and offset-aware datetimes"
            now_utc = _dt.datetime.now(_dt.timezone.utc)
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=_dt.timezone.utc)
            age_hours = (now_utc - latest_ts).total_seconds() / 3600.0
            return age_hours > max_age_hours
    except Exception:
        return True  # If we can't check, assume stale and re-retrieve


# ============================================================
# END SECTION: Player Game Logs Persistence
# ============================================================

# ============================================================
# SECTION: User Settings Persistence
# ============================================================
# Saves and restores user-configurable settings (simulation depth,
# edge threshold, platforms, tuning sliders, etc.) so a browser
# reload restores the user's previous configuration.
# ============================================================

# Settings keys that should be persisted across browser reloads.
_PERSISTED_SETTINGS_KEYS = (
    "simulation_depth",
    "minimum_edge_threshold",
    "entry_fee",
    "total_bankroll",
    "kelly_multiplier",
    "selected_platforms",
    "home_court_boost",
    "blowout_sensitivity",
    "fatigue_sensitivity",
    "pace_sensitivity",
)


def save_user_settings(settings_dict):
    """Persist user settings to SQLite.

    Only the keys listed in ``_PERSISTED_SETTINGS_KEYS`` are stored.
    Uses INSERT OR REPLACE on a single-row table (settings_id=1).

    Args:
        settings_dict (dict): Mapping of setting names to values.
            Typically ``st.session_state`` or a subset of it.

    Returns:
        bool: True on success, False on error.
    """
    try:
        initialize_database()
        # Filter to only the keys we want to persist
        filtered = {
            k: v for k, v in settings_dict.items()
            if k in _PERSISTED_SETTINGS_KEYS
        }
        if not filtered:
            return True  # Nothing to save
        _settings_json = json.dumps(filtered, default=str)
        _execute_write(
            """INSERT OR REPLACE INTO user_settings (settings_id, settings_json, updated_at)
               VALUES (1, ?, datetime('now'))""",
            (_settings_json,),
            caller="save_user_settings",
        )
        return True
    except Exception as _err:
        _logger.warning("save_user_settings error (non-fatal): %s", _err)
        return False


def load_user_settings():
    """Load the most recently saved user settings from SQLite.

    Returns:
        dict: Mapping of setting names to values (only keys in
            ``_PERSISTED_SETTINGS_KEYS``).  Returns an empty dict
            if no settings have been saved or on error.
    """
    try:
        initialize_database()
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute(
                "SELECT settings_json FROM user_settings WHERE settings_id = 1"
            ).fetchone()
            if not row or not row[0]:
                return {}
            raw = json.loads(row[0])
            # Only return recognised keys to avoid injecting stale/unknown state
            return {
                k: v for k, v in raw.items()
                if k in _PERSISTED_SETTINGS_KEYS
            }
    except Exception as _err:
        _logger.warning("load_user_settings error (non-fatal): %s", _err)
        return {}


# ============================================================
# END SECTION: User Settings Persistence
# ============================================================

# ============================================================
# SECTION: Page State Persistence
# ============================================================
# Saves and restores critical page data (analysis results, selected
# picks, today's games, props, injury map, etc.) so a session reset
# caused by an idle WebSocket timeout doesn't wipe the user's work.
# ============================================================

# Page state keys that should be persisted across session resets.
_PERSISTED_PAGE_STATE_KEYS = (
    "analysis_results",
    "selected_picks",
    "todays_games",
    "current_props",
    "session_props",
    "loaded_live_picks",
    "injury_status_map",
    "league_standings",
    "analysis_timestamp",
    "line_snapshots",
)


def save_page_state(session_dict):
    """Persist critical page state to SQLite.

    Only the keys listed in ``_PERSISTED_PAGE_STATE_KEYS`` are stored.
    Uses INSERT OR REPLACE on a single-row table (state_id=1).

    This is designed to be called frequently (every page render) so
    that the latest data is always available for restoration.  Empty
    containers are skipped during save so that a page that hasn't
    populated a key yet doesn't wipe previously saved data for that
    key.  The function merges new non-empty values into any existing
    saved state before writing.

    Args:
        session_dict (dict): Mapping of state names to values.
            Typically ``st.session_state`` or a subset of it.

    Returns:
        bool: True on success, False on error.
    """
    try:
        initialize_database()
        # Filter to only the keys we want to persist and that have content
        filtered = {}
        for k, v in session_dict.items():
            if k not in _PERSISTED_PAGE_STATE_KEYS:
                continue
            # Skip empty containers so we don't overwrite previously
            # saved non-empty values for keys that haven't been populated
            # in the current page context.
            if isinstance(v, (list, dict)) and not v:
                continue
            filtered[k] = v
        if not filtered:
            return True  # Nothing to save
        # Merge with existing saved state so keys from other pages
        # that aren't present in this render are preserved.
        existing = load_page_state()
        merged = {**existing, **filtered}
        # Stamp the saved payload so stale daily state can be dropped next day.
        merged["__saved_for_date"] = _nba_today_iso()
        _state_json = json.dumps(merged, default=str)
        _execute_write(
            """INSERT OR REPLACE INTO page_state (state_id, state_json, updated_at)
               VALUES (1, ?, datetime('now'))""",
            (_state_json,),
            caller="save_page_state",
        )
        return True
    except Exception as _err:
        _logger.warning("save_page_state error (non-fatal): %s", _err)
        return False


def load_page_state():
    """Load the most recently saved page state from SQLite.

    Returns:
        dict: Mapping of state names to values (only keys in
            ``_PERSISTED_PAGE_STATE_KEYS``).  Returns an empty dict
            if no state has been saved or on error.
    """
    try:
        initialize_database()
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute(
                "SELECT state_json FROM page_state WHERE state_id = 1"
            ).fetchone()
            if not row or not row[0]:
                return {}
            raw = json.loads(row[0])

            # Drop day-scoped state when crossing into a new NBA day.
            _saved_for = _extract_iso_date(raw.get("__saved_for_date"))
            _analysis_day = _extract_iso_date(raw.get("analysis_timestamp"))
            if not _saved_for:
                _saved_for = _analysis_day
            _today = _nba_today_iso()
            _is_stale_day = (_saved_for and _saved_for != _today) or (
                _analysis_day and _analysis_day != _today
            )
            if _is_stale_day:
                for _k in (
                    "analysis_results",
                    "selected_picks",
                    "todays_games",
                    "current_props",
                    "session_props",
                    "loaded_live_picks",
                    "analysis_timestamp",
                    "line_snapshots",
                ):
                    raw.pop(_k, None)

            # Only return recognised keys to avoid injecting stale/unknown state
            return {
                k: v for k, v in raw.items()
                if k in _PERSISTED_PAGE_STATE_KEYS
            }
    except Exception as _err:
        _logger.warning("load_page_state error (non-fatal): %s", _err)
        return {}


# ============================================================
# END SECTION: Page State Persistence
# ============================================================


# ============================================================
# SECTION: User Profile Persistence (Premium Onboarding)
# ============================================================

def save_user_profile(email: str, profile_data: dict) -> bool:
    """Save or update a premium subscriber's profile.

    Args:
        email: Subscriber email (case-insensitive key).
        profile_data: Dict with keys matching user_profiles columns.

    Returns:
        True on success, False on error.
    """
    if not email:
        return False
    try:
        initialize_database()
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                INSERT INTO user_profiles
                    (email, display_name, favorite_team, preferred_platforms,
                     experience_level, betting_style, daily_budget, profile_complete)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(email) DO UPDATE SET
                    display_name        = excluded.display_name,
                    favorite_team       = excluded.favorite_team,
                    preferred_platforms  = excluded.preferred_platforms,
                    experience_level    = excluded.experience_level,
                    betting_style       = excluded.betting_style,
                    daily_budget        = excluded.daily_budget,
                    profile_complete    = 1,
                    updated_at          = datetime('now')
                """,
                (
                    email.strip().lower(),
                    profile_data.get("display_name", ""),
                    profile_data.get("favorite_team", ""),
                    profile_data.get("preferred_platforms", ""),
                    profile_data.get("experience_level", ""),
                    profile_data.get("betting_style", ""),
                    profile_data.get("daily_budget", ""),
                ),
            )
            conn.commit()
        return True
    except Exception as _err:
        _logger.warning("save_user_profile error: %s", _err)
        return False


def load_user_profile(email: str) -> dict | None:
    """Load a subscriber's profile from the database.

    Returns:
        Profile dict if found, None otherwise.
    """
    if not email:
        return None
    try:
        initialize_database()
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute(
                "SELECT * FROM user_profiles WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
            return dict(row) if row else None
    except Exception as _err:
        _logger.warning("load_user_profile error: %s", _err)
        return None


def is_profile_complete(email: str) -> bool:
    """Check if a subscriber has completed their profile setup."""
    profile = load_user_profile(email)
    return bool(profile and profile.get("profile_complete"))


# ============================================================
# END SECTION: User Profile Persistence
# ============================================================


# ============================================================
# SECTION: Slate Worker Integration
# Helpers used by slate_worker.py (background job) and the
# Streamlit UI to record/read pre-computed slate results.
# ============================================================

def record_slate_run(
    *,
    for_date: str,
    pick_count: int,
    props_fetched: int,
    games_count: int,
    status: str = "ok",
    error_message: str | None = None,
    duration_seconds: float | None = None,
) -> bool:
    """Insert a slate_worker run record into slate_cache.

    Called exclusively by slate_worker.py after each pipeline execution.
    Only keeps the last 30 rows per date to prevent unbounded table growth.

    Returns:
        True on success, False on error.
    """
    run_at = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sql = (
        "INSERT INTO slate_cache "
        "(for_date, run_at, pick_count, props_fetched, games_count, status, error_message, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    params = (
        for_date, run_at, pick_count, props_fetched, games_count,
        status, error_message, duration_seconds,
    )
    try:
        _execute_write(sql, params, caller="record_slate_run")
        # Prune old rows (keep last 30)
        _execute_write(
            "DELETE FROM slate_cache WHERE id NOT IN "
            "(SELECT id FROM slate_cache ORDER BY id DESC LIMIT 30)",
            caller="record_slate_run_prune",
        )
        return True
    except Exception as exc:
        _logger.error("record_slate_run failed: %s", exc)
        return False


def get_slate_status() -> dict:
    """Return metadata about the most recent slate_worker run.

    Used by Admin Metrics to show worker health and data freshness.

    Returns:
        dict with keys: for_date, run_at, pick_count, props_fetched,
        games_count, status, error_message, duration_seconds.
        Empty dict if no record exists.
    """
    try:
        if _DATABASE_URL:
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT for_date, run_at, pick_count, props_fetched, games_count, "
                "status, error_message, duration_seconds "
                "FROM slate_cache ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            conn.close()
            if row:
                keys = ["for_date", "run_at", "pick_count", "props_fetched",
                        "games_count", "status", "error_message", "duration_seconds"]
                return dict(zip(keys, row))
            return {}
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT for_date, run_at, pick_count, props_fetched, games_count, "
                "status, error_message, duration_seconds "
                "FROM slate_cache ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}
    except Exception as exc:
        _logger.debug("get_slate_status failed: %s", exc)
        return {}


def get_slate_picks_for_today() -> list[dict]:
    """Return today's pre-computed picks from all_analysis_picks.

    Designed to be wrapped in ``@st.cache_data(ttl=300)`` so concurrent
    Streamlit sessions share one DB round-trip per 5-minute window.

    Uses the NBA ET-anchored date so Railway (UTC server) doesn't query
    the wrong day after midnight UTC.

    Returns:
        List of pick dicts sorted by confidence_score DESC.
        Empty list if no picks exist for today.
    """
    today_str = _nba_today_iso()
    try:
        if _DATABASE_URL:
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT pick_id, pick_date, player_name, team, stat_type, prop_line, "
                "direction, platform, confidence_score, probability_over, edge_percentage, "
                "tier, result, actual_value, notes, bet_type, std_devs_from_line, is_risky "
                "FROM all_analysis_picks "
                "WHERE pick_date = %s "
                "ORDER BY confidence_score DESC",
                (today_str,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()
            return rows
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM all_analysis_picks "
                "WHERE pick_date = ? "
                "ORDER BY confidence_score DESC",
                (today_str,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        _logger.debug("get_slate_picks_for_today failed: %s", exc)
        return []

# ============================================================
# END SECTION: Slate Worker Integration
# ============================================================

# ============================================================
# END SECTION: Database CRUD Operations
# ============================================================
