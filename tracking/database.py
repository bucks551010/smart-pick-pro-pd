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
import functools  # For lru_cache on the PostgreSQL connection pool
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
# Use DB_DIR env var (set on Railway to the persistent volume) or default to local db/
DB_DIRECTORY = Path(os.environ.get("DB_DIR", str(Path(__file__).parent.parent / "db")))
DB_FILE_PATH = DB_DIRECTORY / "smartai_nba.db"

# PostgreSQL â€” routes all DB operations to PostgreSQL when DATABASE_URL is set
# (e.g. on Railway), falling back to SQLite for local dev.
_DATABASE_URL: str = os.environ.get("DATABASE_URL", "")


def _normalize_pg_url(url: str) -> str:
    """Convert postgres:// -> postgresql:// for psycopg2."""
    return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url


@functools.lru_cache(maxsize=1)
def _pg_pool():
    """Module-level PostgreSQL ThreadedConnectionPool (lazy, cached per process).

    Reusing a pool across Streamlit reruns prevents the "new connection per
    rerun" overhead that exhausts PostgreSQL connection limits and causes the
    WebSocket to drop with a white screen.  The pool is created once and
    shared for the lifetime of the Streamlit worker process.
    """
    import psycopg2.pool
    return psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=_normalize_pg_url(_DATABASE_URL),
        connect_timeout=10,
    )


def _pg_conn():
    """Return a connection from the module-level pool (falls back to fresh connect)."""
    try:
        return _pg_pool().getconn()
    except Exception:
        import psycopg2
        return psycopg2.connect(_normalize_pg_url(_DATABASE_URL), connect_timeout=10)


def _pg_putconn(conn):
    """Return a connection to the pool (or close it if the pool is unavailable)."""
    try:
        _pg_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


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
            return cur
        except psycopg2.Error as err:
            _logger.error(f"{caller} PG write error (attempt {_attempt + 1}): {err}")
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
            if _attempt >= _WRITE_RETRY_ATTEMPTS - 1:
                return None
            time.sleep(_WRITE_RETRY_DELAY * (2 ** _attempt))
        finally:
            if conn is not None:
                _pg_putconn(conn)
                conn = None
    return None


def _pg_execute_read(sql: str, params=()) -> list:
    """Run a SELECT on PostgreSQL and return a list of dicts."""
    import psycopg2
    import psycopg2.extras
    pg_sql = _to_pg_sql(sql)
    conn = None
    try:
        conn = _pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(pg_sql, params if params else ())
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    except Exception as err:
        _logger.warning(f"PG read error: {err}")
        return []
    finally:
        if conn is not None:
            _pg_putconn(conn)


def _get_eastern_tz():
    """Return America/New_York timezone, with UTC-4 fallback."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except ImportError:
        return datetime.timezone(datetime.timedelta(hours=-4))


def _nba_today_iso() -> str:
    """Return the current NBA 'sports day' anchored to Eastern Time.

    The sports day boundary is 4:00 AM ET (not midnight).  Between
    12:00 AM and 3:59 AM ET the running slate is still attributed to
    the *previous* calendar day, matching how sportsbooks treat West-
    Coast games that finish at 1â€“2 AM ET.
    """
    now_et = datetime.datetime.now(_get_eastern_tz())
    # Before 4 AM ET â†’ still the previous sports day
    if now_et.hour < 4:
        now_et = now_et - datetime.timedelta(days=1)
    return now_et.date().isoformat()

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
    odds_type TEXT DEFAULT 'standard',
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

# ============================================================
# END SECTION: Database Configuration
# ============================================================


# ============================================================
# SECTION: Unified DB Helpers (PostgreSQL / SQLite routing)
# All write/read operations should use _db_write / _db_read so
# they automatically route to the correct backend.
# ============================================================

def _db_write(sql: str, params=(), *, caller: str = "write"):
    """Route a write to PostgreSQL (Railway) or SQLite (local dev)."""
    if _DATABASE_URL:
        return _pg_execute_write(sql, params, caller=caller)
    return _execute_write(sql, params, caller=caller)


def _db_read(sql: str, params=()) -> list:
    """Route a SELECT to PostgreSQL (Railway) or SQLite (local dev).

    Always returns a list of plain dicts.
    """
    if _DATABASE_URL:
        return _pg_execute_read(sql, params)
    try:
        with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params if params else ()).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as err:
        _logger.warning("_db_read error: %s", err)
        return []


def _pg_initialize_database() -> bool:
    """Create all required tables and indexes on PostgreSQL (idempotent).

    Called from initialize_database() when DATABASE_URL is set.
    Uses PostgreSQL-compatible DDL (SERIAL primary keys, NOW() defaults).
    """
    _PG_STMTS = [
        # â”€â”€ Core tables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            closing_line REAL,
            clv_value REAL,
            distance_from_line REAL,
            void_reason TEXT,
            resolve_attempts INTEGER DEFAULT 0,
            last_resolve_attempt TEXT,
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
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
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
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
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
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
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
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
            odds_type TEXT DEFAULT 'standard',
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
        )""",
        """CREATE TABLE IF NOT EXISTS subscriptions (
            subscription_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            customer_email TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            plan_name TEXT DEFAULT 'Premium',
            current_period_start TEXT,
            current_period_end TEXT,
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
            updated_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
        )""",
        """CREATE TABLE IF NOT EXISTS analysis_sessions (
            session_id SERIAL PRIMARY KEY,
            analysis_timestamp TEXT NOT NULL,
            analysis_results_json TEXT NOT NULL,
            todays_games_json TEXT,
            selected_picks_json TEXT,
            prop_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
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
            created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
        )""",
        """CREATE TABLE IF NOT EXISTS player_game_logs (
            log_id SERIAL PRIMARY KEY,
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
            retrieved_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
            UNIQUE(player_id, game_date)
        )""",
        """CREATE TABLE IF NOT EXISTS bet_audit_log (
            audit_id SERIAL PRIMARY KEY,
            bet_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            changed_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
        )""",
        """CREATE TABLE IF NOT EXISTS user_settings (
            settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
            settings_json TEXT NOT NULL,
            updated_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
        )""",
        """CREATE TABLE IF NOT EXISTS page_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            state_json TEXT NOT NULL,
            updated_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS')
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
        """CREATE TABLE IF NOT EXISTS props_cache (
            id SERIAL PRIMARY KEY,
            for_date TEXT NOT NULL,
            platform TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            props_json TEXT NOT NULL,
            prop_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(for_date, platform)
        )""",
        """CREATE TABLE IF NOT EXISTS worker_state (
            job_name TEXT PRIMARY KEY,
            last_run_at TEXT NOT NULL,
            last_status TEXT,
            last_error TEXT,
            run_count INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT
        )""",
        # â”€â”€ Joseph M. Smith tables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        """CREATE TABLE IF NOT EXISTS joseph_diary (
            diary_id SERIAL PRIMARY KEY,
            diary_date TEXT UNIQUE NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            mood TEXT,
            narrative TEXT,
            picks_json TEXT,
            week_summary_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS joseph_player_history (
            history_id SERIAL PRIMARY KEY,
            player_name TEXT NOT NULL,
            stat_type TEXT NOT NULL,
            total_picks INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            last_verdict TEXT,
            last_pick_date TEXT,
            notes TEXT,
            created_at TEXT,
            UNIQUE(player_name, stat_type)
        )""",
        # â”€â”€ Per-user live entry bucket (picks staged from QAM â†’ Entry Builder) â”€â”€
        """CREATE TABLE IF NOT EXISTS live_entry_bucket (
            bucket_id SERIAL PRIMARY KEY,
            user_email TEXT NOT NULL,
            pick_key TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT,
            stat_type TEXT NOT NULL,
            prop_line REAL NOT NULL,
            direction TEXT NOT NULL,
            platform TEXT,
            tier TEXT,
            tier_emoji TEXT,
            confidence_score REAL,
            probability_over REAL,
            edge_percentage REAL,
            bet_type TEXT DEFAULT 'normal',
            odds_type TEXT DEFAULT 'standard',
            added_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
            UNIQUE(user_email, pick_key)
        )""",
        # â”€â”€ Analytics / notifications / drip emails â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        """CREATE TABLE IF NOT EXISTS drip_emails (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            plan_name TEXT NOT NULL DEFAULT '',
            sequence_step INTEGER NOT NULL,
            send_after TEXT NOT NULL,
            sent_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
        )""",
        # ── Telemetry tables ────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS telemetry_timings (
            id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            function_label TEXT NOT NULL,
            duration_ms REAL NOT NULL,
            session_id TEXT,
            success INTEGER DEFAULT 1,
            error_type TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS telemetry_errors (
            id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            error_type TEXT NOT NULL,
            error_message TEXT,
            context TEXT,
            page TEXT,
            stack_trace TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS telemetry_features (
            id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            feature_name TEXT NOT NULL,
            page TEXT,
            metadata TEXT
        )""",
        # â”€â”€ Indexes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "CREATE INDEX IF NOT EXISTS idx_ae_timestamp ON analytics_events (timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_ae_event_name ON analytics_events (event_name)",
        "CREATE INDEX IF NOT EXISTS idx_ae_user ON analytics_events (user_email)",
        "CREATE INDEX IF NOT EXISTS idx_drip_pending ON drip_emails (status, send_after)",
        "CREATE INDEX IF NOT EXISTS idx_bets_player ON bets (player_name)",
        "CREATE INDEX IF NOT EXISTS idx_bets_date ON bets (bet_date)",
        "CREATE INDEX IF NOT EXISTS idx_bets_created ON bets (created_at)",
        "CREATE INDEX IF NOT EXISTS idx_bets_stat_type ON bets (stat_type)",
        "CREATE INDEX IF NOT EXISTS idx_bets_platform ON bets (platform)",
        "CREATE INDEX IF NOT EXISTS idx_bets_date_result ON bets (bet_date, result)",
        "CREATE INDEX IF NOT EXISTS idx_aap_date ON all_analysis_picks (pick_date)",
        "CREATE INDEX IF NOT EXISTS idx_aap_player ON all_analysis_picks (player_name)",
        "CREATE INDEX IF NOT EXISTS idx_aap_stat_type ON all_analysis_picks (stat_type)",
        "CREATE INDEX IF NOT EXISTS idx_aap_date_result ON all_analysis_picks (pick_date, result)",
        "CREATE INDEX IF NOT EXISTS idx_pgl_player_id ON player_game_logs (player_id)",
        "CREATE INDEX IF NOT EXISTS idx_pgl_game_date ON player_game_logs (game_date)",
        "CREATE INDEX IF NOT EXISTS idx_pgl_player_date ON player_game_logs (player_id, game_date)",
        "CREATE INDEX IF NOT EXISTS idx_ph_date ON prediction_history (prediction_date)",
        "CREATE INDEX IF NOT EXISTS idx_ph_stat ON prediction_history (stat_type)",
        # idx_bets_auto_dedup is created separately below (after dup cleanup)
    ]
    # The unique index on all_analysis_picks must match the ON CONFLICT clause
    # in _pg_insert_analysis_picks exactly (including LOWER/COALESCE expressions).
    # Mismatch causes PostgreSQL to raise a constraint error on every insert.
    _UNIQUE_IDX = (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_aap_unique_pick "
        "ON all_analysis_picks (pick_date, LOWER(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))"
    )
    conn = None
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        for stmt in _PG_STMTS:
            cur.execute(stmt)

        # â”€â”€ CRITICAL: commit all CREATE TABLE / CREATE INDEX statements NOW â”€â”€
        # The ALTER TABLE loop below calls conn.rollback() when a statement
        # fails (e.g. ALTER TABLE entries when the entries table doesn't exist).
        # Without this commit, that rollback wipes ALL the tables and indexes
        # created above, leaving the DB empty and silently breaking every
        # subsequent insert.  Committing here means each ALTER failure only
        # rolls back that single statement, never the schema itself.
        conn.commit()

        # â”€â”€ Pipeline-overhaul ALTER TABLE migrations for existing PG DBs â”€â”€
        # Each ALTER runs in its own transaction so a failure never rolls back
        # the previously committed schema.
        _PG_ALTERS = [
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS closing_line REAL",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS clv_value REAL",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS distance_from_line REAL",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS void_reason TEXT",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS resolve_attempts INTEGER DEFAULT 0",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS last_resolve_attempt TEXT",
            # odds_type â€” critical for QEG filtering; without it DB-loaded picks
            # all default to 'standard' and goblin/demon lines bypass the filter.
            "ALTER TABLE all_analysis_picks ADD COLUMN IF NOT EXISTS odds_type TEXT DEFAULT 'standard'",
            # Joseph diary and player history were added after initial deploy;
            # existing PG DBs need these columns if table already exists.
            "ALTER TABLE joseph_diary ADD COLUMN IF NOT EXISTS week_summary_json TEXT",
            "ALTER TABLE joseph_player_history ADD COLUMN IF NOT EXISTS notes TEXT",
            # Per-user bet tracking (Live Entry Bucket â†’ Entry Builder lock)
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS user_email TEXT",
            "ALTER TABLE entries ADD COLUMN IF NOT EXISTS user_email TEXT",
            "CREATE INDEX IF NOT EXISTS idx_bets_user_email ON bets (user_email)",
            "CREATE INDEX IF NOT EXISTS idx_entries_user_email ON entries (user_email)",
            "CREATE INDEX IF NOT EXISTS idx_leb_user ON live_entry_bucket (user_email)",
        ]
        for _alter in _PG_ALTERS:
            try:
                cur.execute(_alter)
                conn.commit()   # commit each ALTER individually
            except Exception as _alter_exc:
                _logger.debug("PG ALTER skipped: %s â€” %s", _alter, _alter_exc)
                conn.rollback()  # only rolls back this one ALTER

        # Unique index: delete dups first if needed
        try:
            cur.execute(_UNIQUE_IDX)
            conn.commit()
        except Exception:
            conn.rollback()
            try:
                cur.execute(
                    """DELETE FROM all_analysis_picks
                       WHERE pick_id NOT IN (
                           SELECT MIN(pick_id)
                           FROM all_analysis_picks
                           GROUP BY pick_date, LOWER(player_name), stat_type,
                                    prop_line, direction, COALESCE(platform, '')
                       )"""
                )
                cur.execute(_UNIQUE_IDX)
                conn.commit()
            except Exception:
                conn.rollback()  # Best-effort â€” index may already exist

        # Unique index on auto-logged bets: dedup first so index never fails silently
        _BETS_DEDUP_IDX = (
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_bets_auto_dedup "
            "ON bets (bet_date, LOWER(player_name), stat_type, direction, platform) WHERE auto_logged = 1"
        )
        try:
            cur.execute(_BETS_DEDUP_IDX)
            conn.commit()
        except Exception:
            conn.rollback()
            try:
                cur.execute(
                    """DELETE FROM bets WHERE auto_logged = 1 AND bet_id NOT IN (
                        SELECT MAX(bet_id) FROM bets WHERE auto_logged = 1
                        GROUP BY bet_date, LOWER(player_name), stat_type, direction, platform
                    )"""
                )
                cur.execute(_BETS_DEDUP_IDX)
                conn.commit()
            except Exception:
                conn.rollback()  # Best-effort
        _logger.info("PostgreSQL schema initialized successfully")
        return True
    except Exception as exc:
        _logger.error("_pg_initialize_database failed: %s", exc)
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if conn:
            _pg_putconn(conn)


# ============================================================
# END SECTION: Unified DB Helpers
# ============================================================


# ============================================================
# SECTION: Database Initialization
# ============================================================

_DB_INITIALIZED = False


def initialize_database():
    """
    Create the database and tables if they don't exist.

    Call this once when the app starts. It's safe to call
    multiple times Ã¢â‚¬â€ CREATE TABLE IF NOT EXISTS won't
    overwrite existing tables.  After the first successful
    initialization the heavy work (PRAGMA integrity_check,
    CREATE TABLE, ALTER TABLE migrations) is skipped.

    Returns:
        bool: True if successful, False if error occurred
    """
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return True

    # â”€â”€ PostgreSQL path (Railway / production) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # When DATABASE_URL is set, create all tables on PostgreSQL and skip
    # the SQLite path entirely.  No local file is needed on Railway.
    if _DATABASE_URL:
        ok = _pg_initialize_database()
        if ok:
            _DB_INITIALIZED = True
            # â”€â”€ Stale data cleanup for PostgreSQL (mirrors SQLite init) â”€â”€
            # player_game_logs: keep only the last 3 days of cache rows.
            _cutoff_3d = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
            _db_write(
                "DELETE FROM player_game_logs WHERE retrieved_at < ?",
                (_cutoff_3d,),
                caller="pg_stale_cleanup",
            )
            # analysis_sessions: keep only today's sessions.
            _db_write(
                "DELETE FROM analysis_sessions WHERE analysis_timestamp < ?",
                (_nba_today_iso(),),
                caller="pg_stale_cleanup",
            )
            # all_analysis_picks: keep only the last 60 days.
            _cutoff_60d = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
            _db_write(
                "DELETE FROM all_analysis_picks WHERE pick_date < ?",
                (_cutoff_60d,),
                caller="pg_stale_cleanup",
            )
            # prediction_history: keep only the last 90 days.
            _cutoff_90d = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
            _db_write(
                "DELETE FROM prediction_history WHERE prediction_date < ?",
                (_cutoff_90d,),
                caller="pg_stale_cleanup",
            )
            # daily_snapshots: keep only the last 90 days.
            _db_write(
                "DELETE FROM daily_snapshots WHERE snapshot_date < ?",
                (_cutoff_90d,),
                caller="pg_stale_cleanup",
            )
            # backtest_results: keep only the most recent 50 runs.
            _db_write(
                "DELETE FROM backtest_results WHERE backtest_id NOT IN "
                "(SELECT backtest_id FROM backtest_results ORDER BY created_at DESC LIMIT 50)",
                (),
                caller="pg_stale_cleanup",
            )
            # slate_cache: keep only the last 30 days.
            _cutoff_30d = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
            _db_write(
                "DELETE FROM slate_cache WHERE for_date < ?",
                (_cutoff_30d,),
                caller="pg_stale_cleanup",
            )
            # analytics_events: keep only the last 90 days.
            _db_write(
                "DELETE FROM analytics_events WHERE timestamp < ?",
                (_cutoff_90d + "T00:00:00",),
                caller="pg_stale_cleanup",
            )
            # drip_emails: purge sent/failed records older than 30 days.
            _db_write(
                "DELETE FROM drip_emails WHERE status != 'pending' AND send_after < ?",
                (_cutoff_30d,),
                caller="pg_stale_cleanup",
            )
            # props_cache: keep only the last 7 days.
            _cutoff_7d = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            _db_write(
                "DELETE FROM props_cache WHERE for_date < ?",
                (_cutoff_7d,),
                caller="pg_stale_cleanup",
            )
            # login_sessions: prune expired tokens (keeps the table small).
            _now_iso = datetime.datetime.utcnow().isoformat()
            _db_write(
                "DELETE FROM login_sessions WHERE expires_at < ?",
                (_now_iso,),
                caller="pg_stale_cleanup",
            )
        return ok

    # â”€â”€ SQLite path (local development) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            cursor.execute(CREATE_ANALYSIS_SESSIONS_TABLE_SQL)    # analysis session persistence
            cursor.execute(CREATE_BACKTEST_RESULTS_TABLE_SQL)     # historical backtesting results
            cursor.execute(CREATE_PLAYER_GAME_LOGS_TABLE_SQL)     # Feature 12: game log persistence
            cursor.execute(CREATE_BET_AUDIT_LOG_TABLE_SQL)         # Bet edit/delete audit log
            cursor.execute(CREATE_USER_SETTINGS_TABLE_SQL)        # User settings persistence
            cursor.execute(CREATE_PAGE_STATE_TABLE_SQL)             # Page state persistence
            # Slate worker + cross-container data-version signaling
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS slate_cache "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, for_date TEXT NOT NULL, "
                "run_at TEXT NOT NULL, pick_count INTEGER NOT NULL DEFAULT 0, "
                "props_fetched INTEGER NOT NULL DEFAULT 0, games_count INTEGER NOT NULL DEFAULT 0, "
                "status TEXT NOT NULL DEFAULT 'ok', error_message TEXT, duration_seconds REAL)"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS app_state "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)"
            )

            # â”€â”€ Joseph M. Smith tables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS joseph_diary "
                "(diary_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "diary_date TEXT UNIQUE NOT NULL, "
                "wins INTEGER NOT NULL DEFAULT 0, "
                "losses INTEGER NOT NULL DEFAULT 0, "
                "mood TEXT, narrative TEXT, picks_json TEXT, "
                "week_summary_json TEXT, created_at TEXT, updated_at TEXT)"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS joseph_player_history "
                "(history_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "player_name TEXT NOT NULL, stat_type TEXT NOT NULL, "
                "total_picks INTEGER NOT NULL DEFAULT 0, "
                "wins INTEGER NOT NULL DEFAULT 0, "
                "losses INTEGER NOT NULL DEFAULT 0, "
                "last_verdict TEXT, last_pick_date TEXT, notes TEXT, created_at TEXT, "
                "UNIQUE(player_name, stat_type))"
            )

            # Ã¢â€â‚¬Ã¢â€â‚¬ Indexes for performance Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
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

            # Ã¢â€â‚¬Ã¢â€â‚¬ Schema migrations for existing databases Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # Add auto_logged column if it doesn't exist yet
            # (ALTER TABLE is idempotent-safe via the try/except)
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN auto_logged INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            # Ensure actual_value column exists (older schema may not have it)
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN actual_value REAL"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            # Ã¢â€â‚¬Ã¢â€â‚¬ Subscriptions table migration Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # If the subscriptions table was created without updated_at
            # (e.g., from an older version of the schema), add it now.
            try:
                cursor.execute(
                    "ALTER TABLE subscriptions ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            # Ã¢â€â‚¬Ã¢â€â‚¬ Goblin/Demon bet_type column migrations Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # Add bet_type and std_devs_from_line to bets table
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN bet_type TEXT DEFAULT 'normal'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN std_devs_from_line REAL DEFAULT 0.0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            # Add bet_type to all_analysis_picks table
            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN bet_type TEXT DEFAULT 'normal'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN std_devs_from_line REAL DEFAULT 0.0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            # Add is_risky flag to all_analysis_picks (1 = avoid/risky pick)
            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN is_risky INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add odds_type to all_analysis_picks (standard / goblin / demon)
            # Critical for QEG filtering â€” without this, DB-loaded picks lack
            # the field and all default to "standard", letting goblin/demon
            # alternate-line picks slip into QEG incorrectly.
            try:
                cursor.execute(
                    "ALTER TABLE all_analysis_picks ADD COLUMN odds_type TEXT DEFAULT 'standard'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists
            # Ã¢â€â‚¬Ã¢â€â‚¬ Line category column migration Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
            # Add line_category and standard_line columns for the three-tier
            # Goblin / 50_50 / Demon classification system.
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN line_category TEXT DEFAULT '50_50'"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN standard_line REAL"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists Ã¢â‚¬â€ safe to ignore

            # Remap old "demon" bet_type records (conflicting-forces picks under
            # the old system) to "50_50" Ã¢â‚¬â€ they were standard-line uncertain picks,
            # not true Demon bets (line above standard O/U).
            try:
                cursor.execute(
                    "UPDATE bets SET bet_type = '50_50' WHERE bet_type = 'demon'"
                )
            except sqlite3.OperationalError:
                pass

            # -- entry_id column migration (link bets to parlay entries) --
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN entry_id INTEGER"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists -- safe to ignore

            # -- auto-logged bet dedup index --
            # Prevents duplicate auto-logged bets at the DB level.  Purge any
            # existing duplicates first (keep the latest bet_id per group) so
            # the UNIQUE index creation never silently fails.
            try:
                cursor.execute(
                    """DELETE FROM bets WHERE auto_logged = 1 AND bet_id NOT IN (
                        SELECT MAX(bet_id) FROM bets WHERE auto_logged = 1
                        GROUP BY bet_date, LOWER(player_name), stat_type, direction, platform
                    )"""
                )
            except sqlite3.OperationalError:
                pass  # Safe to skip â€” index creation handles remaining cases
            try:
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_bets_auto_dedup "
                    "ON bets (bet_date, player_name, stat_type, direction, platform) "
                    "WHERE auto_logged = 1"
                )
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
                pass  # Best-effort â€” app-level dedup still runs first

            # -- source column migration (track bet origin) --
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

            # â”€â”€ Pipeline-overhaul resolution columns (closing_line, CLV, etc.) â”€â”€
            for _col_sql in (
                "ALTER TABLE bets ADD COLUMN closing_line REAL",
                "ALTER TABLE bets ADD COLUMN clv_value REAL",
                "ALTER TABLE bets ADD COLUMN distance_from_line REAL",
                "ALTER TABLE bets ADD COLUMN void_reason TEXT",
                "ALTER TABLE bets ADD COLUMN resolve_attempts INTEGER DEFAULT 0",
                "ALTER TABLE bets ADD COLUMN last_resolve_attempt TEXT",
            ):
                try:
                    cursor.execute(_col_sql)
                except sqlite3.OperationalError:
                    pass

            # â”€â”€ Props cache table (prop JSON storage by date+platform) â”€â”€
            try:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS props_cache ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "for_date TEXT NOT NULL, "
                    "platform TEXT NOT NULL, "
                    "fetched_at TEXT NOT NULL, "
                    "props_json TEXT NOT NULL, "
                    "prop_count INTEGER NOT NULL DEFAULT 0, "
                    "UNIQUE(for_date, platform))"
                )
            except sqlite3.OperationalError:
                pass

            # â”€â”€ Worker state (job name â†’ last run / status) â”€â”€
            try:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS worker_state ("
                    "job_name TEXT PRIMARY KEY, "
                    "last_run_at TEXT NOT NULL, "
                    "last_status TEXT, "
                    "last_error TEXT, "
                    "run_count INTEGER DEFAULT 0)"
                )
            except sqlite3.OperationalError:
                pass

            # â”€â”€ Per-user live entry bucket (picks staged from QAM â†’ Entry Builder) â”€â”€
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS live_entry_bucket ("
                "bucket_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_email TEXT NOT NULL, "
                "pick_key TEXT NOT NULL, "
                "player_name TEXT NOT NULL, "
                "team TEXT, "
                "stat_type TEXT NOT NULL, "
                "prop_line REAL NOT NULL, "
                "direction TEXT NOT NULL, "
                "platform TEXT, "
                "tier TEXT, "
                "tier_emoji TEXT, "
                "confidence_score REAL, "
                "probability_over REAL, "
                "edge_percentage REAL, "
                "bet_type TEXT DEFAULT 'normal', "
                "odds_type TEXT DEFAULT 'standard', "
                "added_at TEXT DEFAULT (datetime('now')), "
                "UNIQUE(user_email, pick_key))"
            )

            # â”€â”€ user_email columns on bets + entries (per-user bet tracking) â”€â”€
            for _ue_alter in (
                "ALTER TABLE bets ADD COLUMN user_email TEXT",
                "ALTER TABLE entries ADD COLUMN user_email TEXT",
            ):
                try:
                    cursor.execute(_ue_alter)
                except sqlite3.OperationalError:
                    pass  # column already exists

            # Indexes for fast per-user filtering
            for _idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_bets_user_email ON bets (user_email)",
                "CREATE INDEX IF NOT EXISTS idx_entries_user_email ON entries (user_email)",
                "CREATE INDEX IF NOT EXISTS idx_leb_user ON live_entry_bucket (user_email)",
            ):
                try:
                    cursor.execute(_idx_sql)
                except sqlite3.OperationalError:
                    pass

            # â”€â”€ Rename retrieved_at column in player_game_logs â”€â”€
            # Older databases have the column named with old terminology; new schema
            # uses retrieved_at.  SQLite Ã¢â€°Â¥ 3.25 supports ALTER TABLE RENAME
            # COLUMN, but we guard with try/except for older builds.
            try:
                cursor.execute(
                    "ALTER TABLE player_game_logs RENAME COLUMN fetched_at TO retrieved_at"
                )
            except sqlite3.OperationalError:
                pass  # Column already renamed or doesn't exist

            # Ã¢â€â‚¬Ã¢â€â‚¬ Unique index on all_analysis_picks to prevent duplicate rows Ã¢â€â‚¬Ã¢â€â‚¬
            # Covers the natural key (pick_date, player_name, stat_type,
            # prop_line, direction) that insert_analysis_picks already
            # deduplicates in application code.  The index makes the DB
            # enforce uniqueness even if the app-level check is bypassed.
            try:
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_aap_unique_pick "
                    "ON all_analysis_picks "
                    "(pick_date, player_name, stat_type, prop_line, direction)"
                )
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
                # May fail if existing data already has duplicates.
                # Clean up duplicates first, then retry.
                try:
                    cursor.execute(
                        """
                        DELETE FROM all_analysis_picks
                        WHERE pick_id NOT IN (
                            SELECT MIN(pick_id)
                            FROM all_analysis_picks
                            GROUP BY pick_date, LOWER(player_name), stat_type,
                                     prop_line, direction, COALESCE(platform, '')
                        )
                        """
                    )
                    cursor.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_aap_unique_pick "
                        "ON all_analysis_picks "
                        "(pick_date, LOWER(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))"
                    )
                except (sqlite3.OperationalError, sqlite3.IntegrityError):
                    pass  # Best-effort -- app-level dedup still protects

            # â”€â”€ Stale data cleanup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # player_game_logs: keep only the last 3 days of cache rows.
            # Older entries are regenerated on demand and just waste space.
            try:
                cursor.execute(
                    "DELETE FROM player_game_logs "
                    "WHERE retrieved_at < date('now', '-3 days')"
                )
            except sqlite3.OperationalError:
                pass

            # analysis_sessions: keep only sessions from today (ET-anchored).
            # Prior-day sessions are discarded on read anyway (load_latest_analysis_session),
            # so we prune them at startup to keep the table lean.
            try:
                _today_str = _nba_today_iso()
                cursor.execute(
                    "DELETE FROM analysis_sessions "
                    "WHERE analysis_timestamp < ?",
                    (_today_str,),
                )
            except sqlite3.OperationalError:
                pass

            # analytics_events: keep only the last 90 days.
            try:
                _ae_cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
                cursor.execute(
                    "DELETE FROM analytics_events WHERE timestamp < ?",
                    (_ae_cutoff + "T00:00:00",),
                )
            except sqlite3.OperationalError:
                pass

            # props_cache: keep only the last 7 days (stale props are useless).
            try:
                _pc_cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
                cursor.execute(
                    "DELETE FROM props_cache WHERE for_date < ?",
                    (_pc_cutoff,),
                )
            except sqlite3.OperationalError:
                pass

            # drip_emails: purge sent/failed records older than 30 days.
            try:
                _de_cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
                cursor.execute(
                    "DELETE FROM drip_emails WHERE status != 'pending' AND send_after < ?",
                    (_de_cutoff,),
                )
            except sqlite3.OperationalError:
                pass

            # login_sessions: prune expired tokens.
            try:
                import datetime as _dt
                _ls_now = _dt.datetime.utcnow().isoformat()
                cursor.execute(
                    "DELETE FROM login_sessions WHERE expires_at < ?",
                    (_ls_now,),
                )
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
    Get a database connection routed to PostgreSQL (Railway) or SQLite (local dev).

    On Railway (``DATABASE_URL`` is set) returns a ``_PGCompatConn`` wrapper that
    exposes the same ``execute`` / ``fetchall`` / ``fetchone`` / ``commit`` API as
    a SQLite connection, so all existing callers work without modification.

    Returns:
        _PGCompatConn | sqlite3.Connection: Use as a context manager.
    """
    if _DATABASE_URL:
        initialize_database()
        return _PGCompatConn()

    # â”€â”€ Local SQLite path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not _DB_INITIALIZED:
        initialize_database()

    connection = sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30)
    # Enable WAL mode for safe concurrent read access
    connection.execute("PRAGMA journal_mode=WAL")
    connection.row_factory = sqlite3.Row  # Rows behave like dicts

    return connection


# â”€â”€ PostgreSQL-compatible connection wrapper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class _PGCompatConn:
    """Context manager that wraps psycopg2 and mimics the SQLite connection API.

    Allows code written against SQLite (``?`` placeholders, ``conn.execute()``,
    dict-like row access) to work transparently with PostgreSQL on Railway.
    SQL dialect translation is handled by ``_to_pg_sql()``.
    """

    def __init__(self):
        import psycopg2
        import psycopg2.extras
        self._conn = psycopg2.connect(
            _DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
            connect_timeout=10,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()

    # row_factory attribute accepted but ignored â€” PG always returns dicts
    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, value):
        pass

    class _Cursor:
        """Psycopg2 cursor with SQLite-compatible fetchone/fetchall."""

        def __init__(self, cur):
            self._cur = cur

        def fetchall(self):
            return [dict(r) for r in self._cur.fetchall()]

        def fetchone(self):
            row = self._cur.fetchone()
            return dict(row) if row is not None else None

        def __iter__(self):
            return iter(self.fetchall())

        @property
        def rowcount(self):
            return self._cur.rowcount

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor()
        cur.execute(_to_pg_sql(sql), params if params else ())
        return self._Cursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


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
    # SQL INSERT statement Ã¢â‚¬â€ ? placeholders for safety
    # BEGINNER NOTE: Never put values directly in SQL strings!
    # Use ? placeholders to prevent "SQL injection" attacks
    insert_sql = """
    INSERT INTO bets (
        bet_date, player_name, team, stat_type, prop_line,
        direction, platform, confidence_score, probability_over,
        edge_percentage, tier, entry_type, entry_fee, notes, auto_logged,
        bet_type, std_devs_from_line, source, user_email
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        bet_data.get("user_email", "") or None,
    )

    # â”€â”€ PostgreSQL path (Railway) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if _DATABASE_URL:
        pg_insert_sql = insert_sql.replace(
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING bet_id",
        )
        conn = None
        try:
            import psycopg2
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(pg_insert_sql, values)
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
        except Exception as _pg_err:
            _logger.error("insert_bet PG error: %s", _pg_err)
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
            return None
        finally:
            if conn:
                _pg_putconn(conn)

    # â”€â”€ SQLite path (local dev) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ PostgreSQL path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if _DATABASE_URL:
        cur = _pg_execute_write(update_sql, (result, actual_value, bet_id), caller="update_bet_result")
        return cur is not None and cur.rowcount > 0

    # â”€â”€ SQLite path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    rows = _db_read("SELECT * FROM bets WHERE bet_id = ?", (bet_id,))
    if not rows:
        return False, f"Bet #{bet_id} not found."
    bet_snapshot = rows[0]

    # Delete the bet
    cursor = _db_write(
        "DELETE FROM bets WHERE bet_id = ?", (bet_id,), caller="delete_bet"
    )
    if cursor is None or cursor.rowcount == 0:
        return False, f"Failed to delete bet #{bet_id}."

    # Log audit record
    _db_write(
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
    rows = _db_read("SELECT * FROM bets WHERE bet_id = ?", (bet_id,))
    if not rows:
        return False, f"Bet #{bet_id} not found."
    old_values = {k: rows[0].get(k) for k in filtered}

    # Build SET clause
    set_parts = [f"{k} = ?" for k in filtered]
    values = list(filtered.values()) + [bet_id]
    sql = f"UPDATE bets SET {', '.join(set_parts)} WHERE bet_id = ?"

    cursor = _db_write(sql, tuple(values), caller="update_bet_fields")
    if cursor is None or cursor.rowcount == 0:
        return False, f"Failed to update bet #{bet_id}."

    # Log audit record
    _db_write(
        """INSERT INTO bet_audit_log (bet_id, action, old_values, new_values, changed_at)
           VALUES (?, 'EDIT', ?, ?, datetime('now'))""",
        (bet_id, json.dumps(old_values, default=str), json.dumps(filtered, default=str)),
        caller="update_bet_fields_audit",
    )
    return True, f"Bet #{bet_id} updated: {', '.join(filtered.keys())}."


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
    return _db_read(sql, (f"%{query.strip().lower()}%", limit))


def load_all_bets(*, limit=10000, exclude_linked=True, user_email=None):
    """
    Load all bets, optionally excluding those linked to a parlay entry.

    Args:
        limit (int): Maximum number of rows to return.
        exclude_linked (bool): If True, exclude bets with an entry_id set.
        user_email (str|None): If set, restrict to that user's bets only.

    Returns:
        list[dict]: Bet rows.
    """
    where_parts = []
    params = []
    if exclude_linked:
        where_parts.append("entry_id IS NULL")
    if user_email:
        where_parts.append(
            "(user_email IS NULL OR user_email = '' "
            "OR LOWER(user_email) = ?)"
        )
        params.append(str(user_email).strip().lower())
    where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    sql = f"SELECT * FROM bets{where_sql} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return _db_read(sql, tuple(params))


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
    return _db_read(sql, (start_date, end_date, limit))


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
        expected_value, pick_count, notes, user_email
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        entry_data.get("entry_date", ""),
        entry_data.get("platform", ""),
        entry_data.get("entry_type", "parlay"),
        entry_data.get("entry_fee", 0.0),
        entry_data.get("expected_value", 0.0),
        entry_data.get("pick_count", 0),
        entry_data.get("notes", ""),
        entry_data.get("user_email", "") or None,
    )
    cursor = _db_write(insert_sql, values, caller="insert_entry")
    if cursor is not None:
        return cursor.lastrowid
    return None


def load_all_entries(limit=500, user_email=None):
    """
    Load recent parlay entries from the database.

    When *user_email* is supplied, restricts to that user's entries plus
    legacy rows without a user_email (historical visibility during rollout).

    Returns:
        list of dict: Entry rows as dictionaries
    """
    if user_email:
        select_sql = """
        SELECT * FROM entries
        WHERE (user_email IS NULL OR user_email = ''
               OR LOWER(user_email) = ?)
        ORDER BY created_at DESC
        LIMIT ?
        """
        return _db_read(select_sql, (str(user_email).strip().lower(), int(limit)))
    select_sql = """
    SELECT * FROM entries
    ORDER BY created_at DESC
    LIMIT ?
    """
    return _db_read(select_sql, (limit,))


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
    cursor = _db_write(
        update_sql, (result, payout, entry_id), caller="update_entry_result"
    )
    return cursor is not None


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
        cursor = _db_write(
            "UPDATE bets SET entry_id = ? WHERE bet_id = ?",
            (entry_id, bet_id),
            caller="link_bets_to_entry",
        )
        if cursor is not None:
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
    return _db_read(select_sql, (entry_id,))


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
            # All legs won Ã¢â‚¬â€ entry is a WIN
            update_entry_result(entry_id, "WIN")
            return "WIN"
        if all(r == "EVEN" for r in results):
            # All legs even Ã¢â‚¬â€ entry is a full EVEN (fee returned)
            update_entry_result(entry_id, "EVEN", payout=0.0)
            return "EVEN"
        # Mix of WIN and EVEN Ã¢â‚¬â€ standard rule: even legs are removed,
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
    _db_write(
        "UPDATE bets SET entry_id = NULL WHERE entry_id = ?",
        (entry_id,),
        caller="delete_entry_unlink",
    )
    cursor = _db_write(
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
    user_email=None,
):
    """Build SQL WHERE clause + params for reusable bet filters."""
    where_parts = []
    params = []

    if exclude_linked:
        where_parts.append("entry_id IS NULL")

    if user_email:
        # Match this user's bets PLUS legacy (NULL/empty) rows so
        # historical bets from before per-user tagging remain visible
        # in everyone's tracker until they're explicitly cleaned up.
        where_parts.append(
            "(user_email IS NULL OR user_email = '' "
            "OR LOWER(user_email) = ?)"
        )
        params.append(str(user_email).strip().lower())

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
        where_parts.append("(result IS NULL OR result = '' OR result = 'VOID')")
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
    user_email=None,
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
        user_email=user_email,
    )

    query_sql = f"""
        SELECT *
        FROM bets
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    return _db_read(query_sql, tuple(params + [int(limit), int(offset)]))


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
    user_email=None,
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
        user_email=user_email,
    )

    query_sql = f"SELECT COUNT(*) AS total_count FROM bets {where_sql}"
    rows = _db_read(query_sql, tuple(params))
    if rows:
        val = rows[0].get("total_count") or rows[0].get("count") or list(rows[0].values())[0]
        return int(val or 0)
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
    user_email=None,
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
        user_email=user_email,
    )

    query_sql = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN result = 'EVEN' THEN 1 ELSE 0 END) AS evens,
            SUM(CASE WHEN (result IS NULL OR result = '' OR result = 'VOID')
                THEN 1 ELSE 0 END) AS pending
        FROM bets
        {where_sql}
    """

    try:
        rows = _db_read(query_sql, tuple(params))
        if not rows:
            return {"total": 0, "wins": 0, "losses": 0, "evens": 0, "pending": 0}
        row = rows[0]
        return {
            "total": int(row.get("total") or 0),
            "wins": int(row.get("wins") or 0),
            "losses": int(row.get("losses") or 0),
            "evens": int(row.get("evens") or 0),
            "pending": int(row.get("pending") or 0),
        }
    except Exception as database_error:
        _logger.error(f"Error summarizing bets: {database_error}")
        return {"total": 0, "wins": 0, "losses": 0, "evens": 0, "pending": 0}


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
    """

    rows = _db_read(summary_sql)
    try:
        row = rows[0] if rows else {}
        total    = int(row.get("total_bets") or 0)
        wins     = int(row.get("wins") or 0)
        losses   = int(row.get("losses") or 0)
        pushes   = int(row.get("pushes") or 0)
        win_rate = float(row.get("win_rate") or 0.0)
        return {
            "total_bets": total,
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": round(win_rate * 100, 1),
        }
    except Exception as database_error:
        _logger.error(f"Error summarizing bets: {database_error}")
        return {"total": 0, "wins": 0, "losses": 0, "evens": 0, "pending": 0}
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
    cursor = _db_write(insert_sql, values, caller="insert_prediction")
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
    return _db_read(query_sql, (cutoff,))


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
    cursor = _db_write(
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
        Ã¢â€ â€™ calibration_adjustment = +5.0 points (reduce all scores by 5)
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
        rows = _db_read(query_sql, params)
        if rows:
            row = rows[0]
            if (row.get("sample_count") or 0) >= min_samples:
                avg_predicted = row.get("avg_predicted_prob") or 0.5
                actual_rate = row.get("actual_hit_rate") or 0.5
                # Overconfidence = model probability higher than actual hit rate
                # Convert probability gap to confidence score adjustment
                # (1% probability gap Ã¢â€°Ë† 2 confidence score points)
                prob_gap_pct = (avg_predicted - actual_rate) * 100.0
                adjustment = prob_gap_pct * 2.0  # Scale to confidence score points
                # Cap adjustment to Ã‚Â±15 points to avoid extreme corrections
                return round(max(-15.0, min(15.0, adjustment)), 1)

    except Exception as database_error:
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
        # Overall calibration
        all_rows = _db_read(query_all)
        if all_rows:
            row = all_rows[0]
            if row.get("sample_count"):
                avg_p = row.get("avg_predicted_prob") or 0.5
                actual = row.get("actual_hit_rate") or 0.5
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
        stat_rows = _db_read(query_overall)
        for r in stat_rows:
            if r.get("sample_count") and r["sample_count"] >= 5:
                avg_p = r.get("avg_predicted_prob") or 0.5
                actual = r.get("actual_hit_rate") or 0.5
                report["by_stat"][r["stat_type"]] = {
                    "avg_predicted_prob": round(avg_p * 100, 1),
                    "actual_hit_rate": round(actual * 100, 1),
                    "sample_count": r["sample_count"],
                    "calibration_adjustment": round((avg_p - actual) * 100 * 2, 1),
                }

    except Exception as database_error:
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

    try:
        bets = _db_read(
            "SELECT * FROM bets WHERE bet_date = ? AND (entry_id IS NULL)",
            (date_str,),
        )
    except Exception as exc:
        _logger.error(f"[database] save_daily_snapshot read error: {exc}")
        return False

    try:
        total = len(bets)
        wins = sum(1 for b in bets if b.get("result") == "WIN")
        losses = sum(1 for b in bets if b.get("result") == "LOSS")
        pushes = sum(1 for b in bets if b.get("result") == "EVEN")
        pending = sum(1 for b in bets if not b.get("result"))
        # win_rate is 0.0 when there are no resolved bets (wins + losses == 0)
        win_rate = round(wins / (wins + losses) * 100, 2) if (wins + losses) > 0 else 0.0

        # Platform breakdown
        platform_breakdown: dict = {}
        for b in bets:
            p = b.get("platform") or "Unknown"
            if p not in platform_breakdown:
                platform_breakdown[p] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            res = b.get("result")
            if res == "WIN":
                platform_breakdown[p]["wins"] += 1
            elif res == "LOSS":
                platform_breakdown[p]["losses"] += 1
            elif res == "EVEN":
                platform_breakdown[p]["pushes"] += 1
            else:
                platform_breakdown[p]["pending"] += 1

        # Tier breakdown
        tier_breakdown: dict = {}
        for b in bets:
            t = b.get("tier") or "Unknown"
            if t not in tier_breakdown:
                tier_breakdown[t] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            res = b.get("result")
            if res == "WIN":
                tier_breakdown[t]["wins"] += 1
            elif res == "LOSS":
                tier_breakdown[t]["losses"] += 1
            elif res == "EVEN":
                tier_breakdown[t]["pushes"] += 1
            else:
                tier_breakdown[t]["pending"] += 1

        # Stat-type breakdown
        stat_type_breakdown: dict = {}
        for b in bets:
            s = b.get("stat_type") or "Unknown"
            if s not in stat_type_breakdown:
                stat_type_breakdown[s] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            res = b.get("result")
            if res == "WIN":
                stat_type_breakdown[s]["wins"] += 1
            elif res == "LOSS":
                stat_type_breakdown[s]["losses"] += 1
            elif res == "EVEN":
                stat_type_breakdown[s]["pushes"] += 1
            else:
                stat_type_breakdown[s]["pending"] += 1

        # Best / worst pick (by edge_percentage, resolved only)
        resolved = [b for b in bets if b.get("result") in ("WIN", "LOSS")]
        best_pick = ""
        worst_pick = ""
        if resolved:
            best = max(resolved, key=lambda b: float(b.get("edge_percentage") or 0))
            worst = min(resolved, key=lambda b: float(b.get("edge_percentage") or 0))
            best_pick = json.dumps({
                "player": best.get("player_name", ""),
                "stat": best.get("stat_type", ""),
                "edge": best.get("edge_percentage", 0),
                "result": best.get("result", ""),
            })
            worst_pick = json.dumps({
                "player": worst.get("player_name", ""),
                "stat": worst.get("stat_type", ""),
                "edge": worst.get("edge_percentage", 0),
                "result": worst.get("result", ""),
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
            date_str,
            total,
            wins,
            losses,
            pushes,
            pending,
            win_rate,
            json.dumps(platform_breakdown),
            json.dumps(tier_breakdown),
            json.dumps(stat_type_breakdown),
            best_pick,
            worst_pick,
        )
        result = _db_write(_upsert_sql, _upsert_params, caller="save_daily_snapshot")
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

    try:
        rows = _db_read(
            "SELECT * FROM daily_snapshots ORDER BY snapshot_date DESC LIMIT ?",
            (days,),
        )
        snapshots = []
        for s in rows:
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


def purge_old_snapshots(days=30):
    """Delete snapshots older than *days* days.

    Returns:
        int: Number of rows deleted.
    """
    import datetime as _dt

    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    try:
        cur = _db_write(
            "DELETE FROM daily_snapshots WHERE snapshot_date < ?",
            (cutoff,),
            caller="purge_old_snapshots",
        )
        deleted = cur.rowcount if cur is not None else 0
        return deleted
    except Exception as exc:
        _logger.error(f"[database] purge_old_snapshots error: {exc}")
        return 0


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
    try:
        cur = _db_write(
            "DELETE FROM player_game_logs WHERE retrieved_at < ?",
            (cutoff,),
            caller="purge_stale_game_logs",
        )
        deleted = cur.rowcount if cur is not None else 0
        _logger.info("[database] purge_stale_game_logs: removed %d rows", deleted)
        return deleted
    except Exception as exc:
        _logger.error("[database] purge_stale_game_logs error: %s", exc)
        return 0


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
    try:
        cur = _db_write(
            "DELETE FROM analysis_sessions WHERE created_at < ?",
            (cutoff,),
            caller="purge_old_sessions",
        )
        deleted = cur.rowcount if cur is not None else 0
        _logger.info("[database] purge_old_sessions: removed %d rows", deleted)
        return deleted
    except Exception as exc:
        _logger.error("[database] purge_old_sessions error: %s", exc)
        return 0


def purge_old_backtest_results(keep=50):
    """Keep only the most recent *keep* backtest result rows.

    Returns:
        int: Number of rows deleted.
    """
    try:
        cur = _db_write(
            "DELETE FROM backtest_results WHERE backtest_id NOT IN "
            "(SELECT backtest_id FROM backtest_results "
            "ORDER BY created_at DESC LIMIT ?)",
            (keep,),
            caller="purge_old_backtest_results",
        )
        deleted = cur.rowcount if cur is not None else 0
        _logger.info("[database] purge_old_backtest_results: removed %d rows", deleted)
        return deleted
    except Exception as exc:
        _logger.error("[database] purge_old_backtest_results error: %s", exc)
        return 0


# Ã¢â€â‚¬Ã¢â€â‚¬ Maintenance defaults Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
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
    # VACUUM is SQLite-only (reclaims freed pages). Skip on PostgreSQL â€”
    # Postgres auto-vacuums, and running VACUUM inside a transaction is not supported.
    if not _DATABASE_URL:
        conn = None
        try:
            conn = sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=30)
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
    else:
        result["vacuumed"] = True  # PG auto-vacuums
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

    # Current streak: walk from most recent snapshot backward
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
# SECTION: All Analysis Picks Ã¢â‚¬â€ Store and Load
# ============================================================

def insert_analysis_picks(analysis_results):
    """
    Persist all Neural Analysis output picks to the all_analysis_picks table.

    Deduplicates by (pick_date, player_name, stat_type, direction) â€” prop_line
    is excluded so that line movements UPDATE the existing row instead of
    creating phantom duplicates.

    Routes to PostgreSQL when DATABASE_URL is set (Railway production).

    Args:
        analysis_results (list[dict]): Full list of analysis result dicts from
            Neural Analysis (as stored in st.session_state["analysis_results"]).

    Returns:
        int: Number of new rows inserted.
    """
    if not analysis_results:
        return 0

    today_str = _nba_today_iso()  # ET-anchored â€” correct for NBA game dates
    inserted = 0

    # â”€â”€ PostgreSQL path (Railway production) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if _DATABASE_URL:
        inserted = _pg_insert_analysis_picks(analysis_results, today_str)
        if inserted > 0:
            _write_latest_picks_cache(today_str)
        return inserted

    for _attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                # Dedup key excludes prop_line so line movements update rather than duplicate
                existing = {}  # key â†’ pick_id for update
                for row in conn.execute(
                    "SELECT pick_id, lower(player_name), stat_type, direction "
                    "FROM all_analysis_picks WHERE pick_date = ?",
                    (today_str,),
                ).fetchall():
                    existing[(row[1], row[2], row[3])] = row[0]

                for r in analysis_results:
                    key = (
                        r.get("player_name", "").lower(),
                        r.get("stat_type", ""),
                        r.get("direction", "OVER"),
                    )
                    if key in existing:
                        # Line may have moved â€” update the existing row
                        conn.execute(
                            """UPDATE all_analysis_picks
                               SET prop_line = ?, confidence_score = ?,
                                   probability_over = ?, edge_percentage = ?,
                                   tier = ?, notes = ?, bet_type = ?,
                                   std_devs_from_line = ?, odds_type = ?
                               WHERE pick_id = ?""",
                            (
                                float(r.get("line", 0) or 0),
                                float(r.get("confidence_score", 0) or 0),
                                float(r.get("probability_over", 0.5) or 0.5),
                                float(r.get("edge_percentage", 0) or 0),
                                r.get("tier", "Bronze"),
                                f"Auto-stored by Smart Pick Pro. SAFE Score: {r.get('confidence_score', 0):.0f}",
                                r.get("bet_type", "normal"),
                                float(r.get("std_devs_from_line", 0.0)),
                                str(r.get("odds_type", "standard") or "standard").strip().lower(),
                                existing[key],
                            ),
                        )
                        continue
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO all_analysis_picks
                            (pick_date, player_name, team, stat_type, prop_line,
                             direction, platform, confidence_score, probability_over,
                             edge_percentage, tier, result, actual_value, notes,
                             bet_type, std_devs_from_line, is_risky, odds_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
                        """,
                        (
                            today_str,
                            r.get("player_name", ""),
                            r.get("player_team", r.get("team", "")),
                            r.get("stat_type", ""),
                            float(r.get("line", 0) or 0),
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
                            str(r.get("odds_type", "standard") or "standard").strip().lower(),
                        ),
                    )
                    existing[key] = -1  # mark as inserted so dedup skips on retry
                    inserted += 1
                conn.commit()
            break  # success Ã¢â‚¬â€ exit retry loop
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

    return inserted


def load_all_analysis_picks(days=30):
    """
    Load all Neural Analysis output picks from the database.

    Args:
        days (int): Number of days of history to load. Defaults to 30.

    Returns:
        list[dict]: List of pick dicts with columns as keys.
    """
    import datetime as _dt
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    try:
        return _db_read(
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
        cur = _db_write(
            "UPDATE all_analysis_picks SET result = ?, actual_value = ? WHERE pick_id = ?",
            (result, float(actual_value), int(pick_id)),
            caller="update_analysis_pick_result",
        )
        return cur is not None
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
        return _db_read(
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
        return _db_read(
            "SELECT * FROM all_analysis_picks WHERE pick_date = ? ORDER BY confidence_score DESC",
            (date_str,),
        )
    except Exception as err:
        _logger.warning(f"load_analysis_picks_for_date error (non-fatal): {err}")
        return []


def get_analysis_pick_dates(days=30):
    """
    Return a sorted list (newest first) of distinct pick_date values in the
    all_analysis_picks table within the last *days* days.

    Args:
        days (int): How many days of history to scan. Defaults to 30.

    Returns:
        list[str]: ISO date strings, e.g. ["2026-03-13", "2026-03-12", ...].
    """
    import datetime as _dt
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    try:
        rows = _db_read(
            "SELECT DISTINCT pick_date FROM all_analysis_picks WHERE pick_date >= ? ORDER BY pick_date DESC",
            (cutoff,),
        )
        return [r["pick_date"] for r in rows]
    except Exception as err:
        _logger.warning(f"get_analysis_pick_dates error (non-fatal): {err}")
        return []


def sync_picks_with_bet_result(bet_date, player_name, stat_type, prop_line, direction, result, actual_value):
    """Sync a resolved bet result to any matching all_analysis_picks row.

    When a bet is resolved (WIN/LOSS/EVEN/VOID), find the matching pick in
    all_analysis_picks and update its result so both tables stay in sync.
    Uses a fuzzy prop_line match (Â±0.15) to tolerate minor line movements.

    Args:
        bet_date (str): ISO date string "YYYY-MM-DD".
        player_name (str): Player name.
        stat_type (str): Stat type (e.g. 'points').
        prop_line (float): The prop line value.
        direction (str): 'OVER' or 'UNDER'.
        result (str): 'WIN', 'LOSS', 'EVEN', or 'VOID'.
        actual_value (float): The player's actual stat value.

    Returns:
        int: Number of pick rows updated.
    """
    try:
        pick_result = result.upper()
        prop_line_f = float(prop_line or 0)
        rows = _db_read(
            """SELECT pick_id FROM all_analysis_picks
               WHERE pick_date = ?
                 AND LOWER(player_name) = LOWER(?)
                 AND stat_type = ?
                 AND direction = ?
                 AND ABS(prop_line - ?) < 0.15
                 AND (result IS NULL OR result = '')""",
            (bet_date, str(player_name), str(stat_type), str(direction).upper(), prop_line_f),
        )
        updated = 0
        for row in rows:
            cur = _db_write(
                "UPDATE all_analysis_picks SET result = ?, actual_value = ? WHERE pick_id = ?",
                (pick_result, float(actual_value or 0), row["pick_id"]),
                caller="sync_picks_with_bet_result",
            )
            if cur is not None:
                updated += 1
        return updated
    except Exception as exc:
        _logger.debug("sync_picks_with_bet_result error (non-fatal): %s", exc)
        return 0


def sync_player_game_logs_from_etl(player_ids=None, limit_per_player=20):
    """Populate tracking DB player_game_logs cache from the ETL database.

    Reads Player_Game_Logs from smartpicks.db (ETL / NBA-data database)
    and writes them into the tracking database's player_game_logs table.
    This keeps both databases in sync so bet resolution and display have
    up-to-date box-score data even if the per-player API fetcher has not run.

    Args:
        player_ids (list[int] | None): Specific player IDs to sync.
            None syncs all players present in the ETL DB.
        limit_per_player (int): Max recent games per player. Defaults to 20.

    Returns:
        int: Total rows written (inserted or updated).
    """
    import os as _os
    import pathlib as _pathlib

    db_dir = _os.environ.get("DB_DIR", "")
    etl_db = _pathlib.Path(db_dir) / "smartpicks.db" if db_dir else None
    if not etl_db or not etl_db.exists():
        _logger.debug("sync_player_game_logs_from_etl: ETL DB not found at %s", etl_db)
        return 0

    import datetime as _dt
    retrieved_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    total_written = 0

    if _DATABASE_URL:
        upsert_sql = (
            "INSERT INTO player_game_logs "
            "    (player_id, player_name, game_date, opponent, minutes, points, rebounds, "
            "     assists, threes, steals, blocks, turnovers, fg_pct, ft_pct, plus_minus, retrieved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (player_id, game_date) DO UPDATE SET "
            "    player_name=EXCLUDED.player_name, minutes=EXCLUDED.minutes, "
            "    points=EXCLUDED.points, rebounds=EXCLUDED.rebounds, assists=EXCLUDED.assists, "
            "    threes=EXCLUDED.threes, steals=EXCLUDED.steals, blocks=EXCLUDED.blocks, "
            "    turnovers=EXCLUDED.turnovers, fg_pct=EXCLUDED.fg_pct, ft_pct=EXCLUDED.ft_pct, "
            "    plus_minus=EXCLUDED.plus_minus, retrieved_at=EXCLUDED.retrieved_at"
        )
    else:
        upsert_sql = (
            "INSERT OR REPLACE INTO player_game_logs "
            "    (player_id, player_name, game_date, opponent, minutes, points, rebounds, "
            "     assists, threes, steals, blocks, turnovers, fg_pct, ft_pct, plus_minus, retrieved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

    try:
        import sqlite3 as _sqlite3
        etl_conn = _sqlite3.connect(str(etl_db), check_same_thread=False, timeout=10)
        etl_conn.row_factory = _sqlite3.Row

        if player_ids:
            _ph = ",".join(["?" for _ in player_ids])
            sql = (
                f"SELECT p.player_id, p.first_name, p.last_name, g.game_date, "
                f"       l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.fg3m, "
                f"       l.fg_pct, l.ft_pct, l.plus_minus, l.min "
                f"FROM Player_Game_Logs l "
                f"JOIN Games g ON l.game_id = g.game_id "
                f"JOIN Players p ON l.player_id = p.player_id "
                f"WHERE l.player_id IN ({_ph}) "
                f"ORDER BY l.player_id, g.game_date DESC"
            )
            etl_rows = etl_conn.execute(sql, list(player_ids)).fetchall()
        else:
            etl_rows = etl_conn.execute(
                "SELECT p.player_id, p.first_name, p.last_name, g.game_date, "
                "       l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.fg3m, "
                "       l.fg_pct, l.ft_pct, l.plus_minus, l.min "
                "FROM Player_Game_Logs l "
                "JOIN Games g ON l.game_id = g.game_id "
                "JOIN Players p ON l.player_id = p.player_id "
                "ORDER BY l.player_id, g.game_date DESC"
            ).fetchall()

        _seen: dict = {}
        for r in etl_rows:
            pid = str(r["player_id"])
            _seen[pid] = _seen.get(pid, 0) + 1
            if _seen[pid] > limit_per_player:
                continue

            def _n(v, as_int=False):
                try:
                    f = float(v or 0)
                    return int(f) if as_int else f
                except (TypeError, ValueError):
                    return 0 if as_int else 0.0

            min_raw = str(r["min"] or "0")
            try:
                minutes_f = float(min_raw.split(":")[0]) if ":" in min_raw else float(min_raw)
            except (ValueError, TypeError):
                minutes_f = 0.0

            pname = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
            cur = _db_write(upsert_sql, (
                pid, pname, str(r["game_date"] or ""), "",
                minutes_f, _n(r["pts"], True), _n(r["reb"], True), _n(r["ast"], True),
                _n(r["fg3m"], True), _n(r["stl"], True), _n(r["blk"], True), _n(r["tov"], True),
                _n(r["fg_pct"]), _n(r["ft_pct"]), _n(r["plus_minus"], True),
                retrieved_at,
            ), caller="sync_player_game_logs_from_etl")
            if cur is not None:
                total_written += 1

        etl_conn.close()
    except Exception as exc:
        _logger.warning("sync_player_game_logs_from_etl error: %s", exc)

    if total_written:
        _logger.info("sync_player_game_logs_from_etl: wrote %d rows to tracking DB", total_written)
    return total_written


# ============================================================
# END SECTION: All Analysis Picks
# ============================================================

# ============================================================
# SECTION: Slate Worker Integration
# Helpers used by slate_worker.py and the Streamlit UI to
# record/read pre-computed slate results and signal running
# sessions that fresh data is available.
# ============================================================

def _pg_insert_analysis_picks(analysis_results: list, today_str: str) -> int:
    """PostgreSQL UPSERT for all_analysis_picks.

    Primary path uses ON CONFLICT (requires idx_aap_unique_pick).
    Falls back to per-row INSERT with duplicate-skip on UniqueViolation when
    the unique index is missing (e.g. first deploy or failed index creation).

    Enforces the same 5-props-per-player cap as analysis_orchestrator.py so
    that even if the caller passes un-capped results no player leaks >5 rows.
    """
    if not analysis_results:
        return 0

    # Apply per-player cap before hitting the DB (results already sorted by
    # quality from the orchestrator, so first 5 per player are best ones).
    _MAX_PICKS_PER_PLAYER = 5
    _pcounts: dict = {}
    capped_results = []
    for r in analysis_results:
        pname = str(r.get("player_name", "")).lower()
        _pcounts[pname] = _pcounts.get(pname, 0) + 1
        if _pcounts[pname] <= _MAX_PICKS_PER_PLAYER:
            capped_results.append(r)

    def _build_params(r):
        _line = round(float(r.get("line", 0) or 0), 2)
        _platform = str(r.get("platform", "") or "").strip()
        return (
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
            str(r.get("odds_type", "standard") or "standard").strip().lower(),
        )

    _UPSERT_SQL = """
        INSERT INTO all_analysis_picks
            (pick_date, player_name, team, stat_type, prop_line, direction,
             platform, confidence_score, probability_over, edge_percentage,
             tier, notes, bet_type, std_devs_from_line, is_risky, odds_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (pick_date, LOWER(player_name), stat_type, prop_line, direction, COALESCE(platform, ''))
        DO UPDATE SET
            confidence_score   = EXCLUDED.confidence_score,
            probability_over   = EXCLUDED.probability_over,
            edge_percentage    = EXCLUDED.edge_percentage,
            tier               = EXCLUDED.tier,
            notes              = EXCLUDED.notes,
            bet_type           = EXCLUDED.bet_type,
            std_devs_from_line = EXCLUDED.std_devs_from_line,
            is_risky           = EXCLUDED.is_risky,
            odds_type          = EXCLUDED.odds_type
    """

    _INSERT_SQL = """
        INSERT INTO all_analysis_picks
            (pick_date, player_name, team, stat_type, prop_line, direction,
             platform, confidence_score, probability_over, edge_percentage,
             tier, notes, bet_type, std_devs_from_line, is_risky, odds_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    inserted = 0
    conn = None
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        # ── Primary path: batch upsert with ON CONFLICT ──────────────────
        try:
            for r in capped_results:
                cur.execute(_UPSERT_SQL, _build_params(r))
                inserted += 1
            conn.commit()
            conn.close()
            return inserted
        except Exception as upsert_err:
            # ON CONFLICT clause requires idx_aap_unique_pick.
            # If the index is missing, fall back to per-row inserts with
            # individual duplicate-key suppression.
            _logger.warning(
                "_pg_insert_analysis_picks: ON CONFLICT path failed (%s) — "
                "falling back to row-by-row INSERT with duplicate suppression.",
                upsert_err,
            )
            try:
                conn.rollback()
            except Exception:
                pass
        # ── Fallback: row-by-row INSERT, skip on duplicate ───────────────
        import psycopg2
        inserted = 0
        cur = conn.cursor()  # fresh cursor after rollback
        for r in capped_results:
            try:
                cur.execute(_INSERT_SQL, _build_params(r))
                conn.commit()
                inserted += 1
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                cur = conn.cursor()  # recreate cursor after rollback
            except Exception as row_err:
                _logger.debug("_pg_insert_analysis_picks row error: %s", row_err)
                conn.rollback()
                cur = conn.cursor()
        conn.close()
        return inserted
    except Exception as err:
        _logger.warning(f"_pg_insert_analysis_picks error: {err}")
        try:
            if conn:
                conn.rollback()
                conn.close()
        except Exception:
            pass
    return inserted


def _write_latest_picks_cache(date_str: str, limit: int = 5) -> None:
    """Persist today's top picks to cache/latest_picks.json.

    Supports both PostgreSQL (Railway) and SQLite (local dev).
    Also bumps the DB-backed data_version so any running Streamlit
    container detects fresh picks without a manual reload.
    """
    import json as _json
    try:
        if _DATABASE_URL:
            rows_data: list = []
            conn = None
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
            except Exception as pg_err:
                _logger.debug("_write_latest_picks_cache PG query: %s", pg_err)
            finally:
                if conn is not None:
                    _pg_putconn(conn)
            if not rows_data:
                return
            cache_data = {"date": date_str, "picks": rows_data}
        else:
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
        _bump_data_version(date_str)
    except Exception as exc:
        _logger.debug("_write_latest_picks_cache: %s", exc)


def _bump_data_version(date_str: str) -> None:
    """Write a data-version stamp visible to all containers.

    Two mechanisms:
    1. cache/data_version.json â€” file-based, in-process.
    2. app_state DB row â€” cross-container; GitHub Actions CI writes here
       after inserting picks so running Streamlit containers detect updates.
    """
    import json as _json, time as _time
    _ver = _time.time()
    try:
        version_path = Path(__file__).parent.parent / "cache" / "data_version.json"
        version_path.parent.mkdir(parents=True, exist_ok=True)
        version_path.write_text(
            _json.dumps({"version": _ver, "date": date_str}), encoding="utf-8"
        )
    except Exception as exc:
        _logger.debug("_bump_data_version (file): %s", exc)
    try:
        if _DATABASE_URL:
            conn = _pg_conn()
            cur = conn.cursor()
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
    """Read the current data version from DB (cross-container safe).

    Returns version as a float timestamp. Falls back to file, then 0.0.
    """
    import json as _json
    try:
        if _DATABASE_URL:
            rows = _pg_execute_read("SELECT value FROM app_state WHERE key = 'data_version'")
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
    try:
        vp = Path(__file__).parent.parent / "cache" / "data_version.json"
        if vp.exists():
            return float(_json.loads(vp.read_text(encoding="utf-8")).get("version", 0))
    except Exception:
        pass
    return 0.0


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

    Returns True on success, False on error.
    """
    run_at = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sql = (
        "INSERT INTO slate_cache "
        "(for_date, run_at, pick_count, props_fetched, games_count, status, error_message, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    params = (for_date, run_at, pick_count, props_fetched, games_count, status, error_message, duration_seconds)
    try:
        if _DATABASE_URL:
            _pg_execute_write(_to_pg_sql(sql), params, caller="record_slate_run")
        else:
            _execute_write(sql, params, caller="record_slate_run")
        # Prune old rows (keep last 30)
        prune_sql = "DELETE FROM slate_cache WHERE id NOT IN (SELECT id FROM slate_cache ORDER BY id DESC LIMIT 30)"
        if _DATABASE_URL:
            _pg_execute_write(prune_sql, caller="record_slate_run_prune")
        else:
            _execute_write(prune_sql, caller="record_slate_run_prune")
        return True
    except Exception as exc:
        _logger.error("record_slate_run failed: %s", exc)
        return False


def get_slate_picks_for_today() -> list:
    """Return today's pre-computed picks from all_analysis_picks.

    Uses the NBA ET-anchored date so Railway (UTC server) queries the right day.
    Designed to be wrapped in @st.cache_data(ttl=60).

    Enforces a 5-props-per-player cap (matching analysis_orchestrator.py) on
    the read path so that multiple worker runs or multi-platform rows in the DB
    never leak more than 5 picks per player to the UI.
    """
    _MAX_PICKS_PER_PLAYER = 5
    today_str = _nba_today_iso()
    try:
        if _DATABASE_URL:
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT pick_id, pick_date, player_name, team, stat_type, prop_line, "
                "direction, platform, confidence_score, probability_over, edge_percentage, "
                "tier, result, actual_value, notes, bet_type, std_devs_from_line, is_risky, odds_type "
                "FROM all_analysis_picks "
                "WHERE pick_date = %s "
                "ORDER BY confidence_score DESC",
                (today_str,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()
        else:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM all_analysis_picks "
                    "WHERE pick_date = ? "
                    "ORDER BY confidence_score DESC",
                    (today_str,),
                ).fetchall()]

        # Enforce per-player cap: results are already sorted by confidence_score DESC
        # so we keep the best picks for each player.
        _player_counts: dict = {}
        capped: list = []
        for r in rows:
            pname = str(r.get("player_name", "")).lower()
            _player_counts[pname] = _player_counts.get(pname, 0) + 1
            if _player_counts[pname] <= _MAX_PICKS_PER_PLAYER:
                capped.append(r)
        return capped
    except Exception as exc:
        _logger.debug("get_slate_picks_for_today failed: %s", exc)
        return []

# ============================================================
# END SECTION: Slate Worker Integration
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
        if _DATABASE_URL:
            # PG path: use RETURNING to get the new session_id
            conn = None
            try:
                conn = _pg_conn()
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO analysis_sessions
                       (analysis_timestamp, analysis_results_json, todays_games_json,
                        selected_picks_json, prop_count)
                       VALUES (%s, %s, %s, %s, %s)
                       RETURNING session_id""",
                    (_ts, _results_json, _games_json, _picks_json, _prop_count),
                )
                row = cur.fetchone()
                conn.commit()
                conn.close()
                if row:
                    return int(row["session_id"] if isinstance(row, dict) else row[0])
                return -1
            except Exception as _pg_err:
                _logger.warning("save_analysis_session PG error: %s", _pg_err)
                try:
                    if conn:
                        conn.rollback()
                        conn.close()
                except Exception:
                    pass
                return -1
        cursor = _db_write(
            """INSERT INTO analysis_sessions
               (analysis_timestamp, analysis_results_json, todays_games_json,
                selected_picks_json, prop_count)
               VALUES (?, ?, ?, ?, ?)""",
            (_ts, _results_json, _games_json, _picks_json, _prop_count),
            caller="save_analysis_session",
        )
        if cursor is None:
            return -1
        try:
            return cursor.lastrowid if cursor.lastrowid else -1
        except Exception:
            return -1
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
        rows = _db_read(
            "SELECT * FROM analysis_sessions ORDER BY session_id DESC LIMIT 1"
        )
        if not rows:
            return None
        row_dict = rows[0]
        # Date guard: if the session is from a prior sports day, return None.
        # The QAM page falls back to get_slate_picks_for_today() when this
        # returns None, which has a hard pick_date = today filter.
        _session_ts = row_dict.get("analysis_timestamp", "")
        if _session_ts:
            try:
                _session_date = _session_ts[:10]  # "YYYY-MM-DD"
                if _session_date < _nba_today_iso():
                    _logger.debug(
                        "load_latest_analysis_session: session %s is prior-day (%s < %s) â€” skipping",
                        row_dict.get("session_id"),
                        _session_date,
                        _nba_today_iso(),
                    )
                    return None
            except Exception:
                pass  # If date parse fails, still return the session
        # Deserialize JSON blobs
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


def load_analysis_session_by_id(session_id: int):
    """Load a specific Neural Analysis session from the DB by its primary key.

    Used by the QAM Session Bridge: after a run is saved the session_id is
    written to ``st.query_params["sid"]`` so that a page refresh or tab-switch
    recovers the EXACT run the user was viewing rather than whatever the most
    recent DB row happens to be.

    Args:
        session_id: The ``session_id`` primary key returned by
            ``save_analysis_session``.

    Returns:
        dict|None: Session dict with deserialized ``analysis_results``,
            ``todays_games``, ``selected_picks`` fields, or None if not found.
    """
    if not session_id:
        return None
    try:
        row_dict: dict | None = None
        if _DATABASE_URL:
            rows = _pg_execute_read(
                "SELECT * FROM analysis_sessions WHERE session_id = ?",
                (int(session_id),),
            )
            row_dict = dict(rows[0]) if rows else None
        else:
            with sqlite3.connect(str(DB_FILE_PATH), check_same_thread=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM analysis_sessions WHERE session_id = ?",
                    (int(session_id),),
                )
                row = cursor.fetchone()
                row_dict = dict(row) if row else None
        if not row_dict:
            return None
        # Note: sessions are kept across midnight â€” same policy as load_latest_analysis_session.
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
        _logger.warning(f"load_analysis_session_by_id({session_id}) error (non-fatal): {_err}")
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

        cursor = _db_write(
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
        rows = _db_read(
            "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        results = []
        for row_dict in rows:
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

    # Choose INSERT syntax based on backend (ON CONFLICT for PG, INSERT OR REPLACE for SQLite)
    if _DATABASE_URL:
        upsert_sql = (
            "INSERT INTO player_game_logs "
            "    (player_id, player_name, game_date, opponent, minutes, points, rebounds, "
            "     assists, threes, steals, blocks, turnovers, fg_pct, ft_pct, plus_minus, retrieved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (player_id, game_date) DO UPDATE SET "
            "    player_name=EXCLUDED.player_name, minutes=EXCLUDED.minutes, "
            "    points=EXCLUDED.points, rebounds=EXCLUDED.rebounds, assists=EXCLUDED.assists, "
            "    threes=EXCLUDED.threes, steals=EXCLUDED.steals, blocks=EXCLUDED.blocks, "
            "    turnovers=EXCLUDED.turnovers, fg_pct=EXCLUDED.fg_pct, ft_pct=EXCLUDED.ft_pct, "
            "    plus_minus=EXCLUDED.plus_minus, retrieved_at=EXCLUDED.retrieved_at"
        )
    else:
        upsert_sql = (
            "INSERT OR REPLACE INTO player_game_logs "
            "    (player_id, player_name, game_date, opponent, minutes, points, rebounds, "
            "     assists, threes, steals, blocks, turnovers, fg_pct, ft_pct, plus_minus, retrieved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

    inserted = 0
    for g in game_logs:
        cur = _db_write(upsert_sql, (
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
        ), caller="save_player_game_logs_to_db")
        if cur is not None:
            inserted += 1

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
    try:
        return _db_read(
            "SELECT * FROM player_game_logs WHERE player_id = ? AND game_date >= ? ORDER BY game_date DESC",
            (str(player_id), cutoff),
        )
    except Exception as err:
        _logger.warning(f"load_player_game_logs_from_db error (non-fatal): {err}")
        return []


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
        rows = _db_read(
            "SELECT MAX(retrieved_at) AS latest_ts FROM player_game_logs WHERE player_id = ?",
            (str(player_id),),
        )
        if not rows or not rows[0].get("latest_ts"):
            return True
        latest_ts = _dt.datetime.fromisoformat(str(rows[0]["latest_ts"]))
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
        if _DATABASE_URL:
            _db_write(
                "INSERT INTO user_settings (settings_id, settings_json, updated_at) "
                "VALUES (1, ?, to_char(now(), 'YYYY-MM-DD HH24:MI:SS')) "
                "ON CONFLICT (settings_id) DO UPDATE SET "
                "    settings_json=EXCLUDED.settings_json, updated_at=EXCLUDED.updated_at",
                (_settings_json,),
                caller="save_user_settings",
            )
        else:
            _db_write(
                "INSERT OR REPLACE INTO user_settings (settings_id, settings_json, updated_at) "
                "VALUES (1, ?, datetime('now'))",
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
        rows = _db_read("SELECT settings_json FROM user_settings WHERE settings_id = 1")
        if not rows or not rows[0].get("settings_json"):
            return {}
        raw = json.loads(rows[0]["settings_json"])
        return {k: v for k, v in raw.items() if k in _PERSISTED_SETTINGS_KEYS}
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
        # Stamp the date so load_page_state() can discard next-day stale state.
        merged["_page_state_date"] = _nba_today_iso()
        _state_json = json.dumps(merged, default=str)
        if _DATABASE_URL:
            _db_write(
                "INSERT INTO page_state (state_id, state_json, updated_at) "
                "VALUES (1, ?, to_char(now(), 'YYYY-MM-DD HH24:MI:SS')) "
                "ON CONFLICT (state_id) DO UPDATE SET "
                "    state_json=EXCLUDED.state_json, updated_at=EXCLUDED.updated_at",
                (_state_json,),
                caller="save_page_state",
            )
        else:
            _db_write(
                "INSERT OR REPLACE INTO page_state (state_id, state_json, updated_at) "
                "VALUES (1, ?, datetime('now'))",
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
        rows = _db_read("SELECT state_json FROM page_state WHERE state_id = 1")
        if not rows or not rows[0].get("state_json"):
            return {}
        raw = json.loads(rows[0]["state_json"])
        # Discard state saved on a prior NBA day â€” prevents yesterday's players
        # from appearing after the Eastern Time day boundary rolls over.
        saved_date = raw.get("_page_state_date", "")
        if saved_date != _nba_today_iso():
            _logger.info(
                "load_page_state: discarding stale state from '%s' (today=%s)",
                saved_date,
                _nba_today_iso(),
            )
            return {}
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
# END SECTION: Database CRUD Operations
# ============================================================


# ============================================================
# SECTION: Pipeline Overhaul Helpers
# (props_cache, worker_state, full bet resolution, retry/cleanup)
# ============================================================

def save_props_to_cache(for_date: str, platform: str, props: list) -> bool:
    """Persist a list of props for a given date+platform.

    Used by the worker to save fresh PrizePicks/Underdog/DK props into
    the DB so the Streamlit app reads them without hitting the upstream
    API on every page load. Replaces any existing row for the same
    (for_date, platform) pair.

    Args:
        for_date: ISO date the props are valid for (NBA day, ET).
        platform: Platform name ("PrizePicks", "Underdog Fantasy", ...).
        props: List of prop dicts to JSON-encode and store.

    Returns:
        True on success, False on error.
    """
    try:
        payload = json.dumps(props, default=str)
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        if _DATABASE_URL:
            sql = (
                "INSERT INTO props_cache (for_date, platform, fetched_at, props_json, prop_count) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (for_date, platform) DO UPDATE "
                "SET fetched_at = EXCLUDED.fetched_at, "
                "    props_json = EXCLUDED.props_json, "
                "    prop_count = EXCLUDED.prop_count"
            )
        else:
            sql = (
                "INSERT INTO props_cache (for_date, platform, fetched_at, props_json, prop_count) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(for_date, platform) DO UPDATE SET "
                "    fetched_at = excluded.fetched_at, "
                "    props_json = excluded.props_json, "
                "    prop_count = excluded.prop_count"
            )
        cur = _db_write(
            sql,
            (for_date, platform, now_iso, payload, len(props)),
            caller="save_props_to_cache",
        )
        return cur is not None
    except Exception as exc:
        _logger.error("save_props_to_cache failed (%s/%s): %s", for_date, platform, exc)
        return False


def load_props_from_cache(
    for_date: str,
    platform: str | None = None,
    *,
    max_age_minutes: int = 30,
) -> list:
    """Return cached props for date (and optional platform) if fresh.

    Args:
        for_date: NBA day in ET ('YYYY-MM-DD').
        platform: Single platform to filter on (None = all platforms).
        max_age_minutes: Age cutoff. Older rows are ignored (stale).

    Returns:
        Flat list of prop dicts (merged across platforms if platform is None).
        Empty list if nothing fresh is cached.
    """
    try:
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(minutes=max_age_minutes)
        ).isoformat() + "Z"
        if platform:
            rows = _db_read(
                "SELECT props_json, fetched_at FROM props_cache "
                "WHERE for_date = ? AND platform = ? AND fetched_at >= ?",
                (for_date, platform, cutoff),
            )
        else:
            rows = _db_read(
                "SELECT props_json, fetched_at FROM props_cache "
                "WHERE for_date = ? AND fetched_at >= ?",
                (for_date, cutoff),
            )
        merged: list = []
        for r in rows or []:
            try:
                merged.extend(json.loads(r["props_json"]))
            except Exception:
                continue
        return merged
    except Exception as exc:
        _logger.debug("load_props_from_cache failed (%s/%s): %s", for_date, platform, exc)
        return []


def update_worker_state(
    job_name: str,
    *,
    status: str = "ok",
    error: str | None = None,
) -> None:
    """Stamp a job run in the worker_state table.

    Used by the slate worker so it can see which jobs need to catch up
    after a restart and so the operator can audit the schedule.
    """
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    if _DATABASE_URL:
        sql = (
            "INSERT INTO worker_state (job_name, last_run_at, last_status, last_error, run_count) "
            "VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT (job_name) DO UPDATE "
            "SET last_run_at = EXCLUDED.last_run_at, "
            "    last_status = EXCLUDED.last_status, "
            "    last_error = EXCLUDED.last_error, "
            "    run_count = worker_state.run_count + 1"
        )
    else:
        sql = (
            "INSERT INTO worker_state (job_name, last_run_at, last_status, last_error, run_count) "
            "VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT(job_name) DO UPDATE SET "
            "    last_run_at = excluded.last_run_at, "
            "    last_status = excluded.last_status, "
            "    last_error = excluded.last_error, "
            "    run_count = worker_state.run_count + 1"
        )
    _db_write(sql, (job_name, now_iso, status, error), caller="update_worker_state")


def get_worker_state(job_name: str | None = None) -> list[dict]:
    """Read worker_state. If job_name is given, returns just that one row."""
    if job_name:
        rows = _db_read(
            "SELECT job_name, last_run_at, last_status, last_error, run_count "
            "FROM worker_state WHERE job_name = ?",
            (job_name,),
        )
    else:
        rows = _db_read(
            "SELECT job_name, last_run_at, last_status, last_error, run_count FROM worker_state",
            (),
        )
    return [dict(r) for r in (rows or [])]


def update_bet_resolution_full(
    bet_id: int,
    result: str,
    actual_value: float,
    *,
    closing_line: float | None = None,
    void_reason: str | None = None,
) -> tuple[bool, str]:
    """Record a full resolution (WIN/LOSS/EVEN/VOID) with derived metrics.

    Computes:
        distance_from_line = actual_value - prop_line  (signed)
        clv_value          = (closing_line - prop_line) * (+1 OVER, -1 UNDER)
                             â€” positive CLV = line moved toward your bet.

    Increments resolve_attempts and stamps last_resolve_attempt regardless
    of the outcome so the worker's retry policy can see the history.
    """
    try:
        # Pull the bet so we know prop_line / direction for derived metrics.
        rows = _db_read(
            "SELECT prop_line, direction FROM bets WHERE bet_id = ?", (bet_id,)
        )
        if not rows:
            return False, f"bet_id {bet_id} not found"
        prop_line = float(rows[0]["prop_line"] or 0)
        direction = (rows[0]["direction"] or "OVER").upper()

        distance = float(actual_value) - prop_line
        clv = None
        if closing_line is not None:
            sign = 1.0 if direction == "OVER" else -1.0
            clv = (float(closing_line) - prop_line) * sign

        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        cur = _db_write(
            "UPDATE bets SET "
            "  result = ?, actual_value = ?, distance_from_line = ?, "
            "  closing_line = COALESCE(?, closing_line), "
            "  clv_value = COALESCE(?, clv_value), "
            "  void_reason = COALESCE(?, void_reason), "
            "  resolve_attempts = COALESCE(resolve_attempts, 0) + 1, "
            "  last_resolve_attempt = ? "
            "WHERE bet_id = ?",
            (result, float(actual_value), distance, closing_line, clv, void_reason, now_iso, bet_id),
            caller="update_bet_resolution_full",
        )
        return (cur is not None), "ok" if cur is not None else "db error"
    except Exception as exc:
        _logger.error("update_bet_resolution_full failed (#%s): %s", bet_id, exc)
        return False, str(exc)


def stamp_resolve_attempt(bet_id: int, error: str | None = None) -> None:
    """Increment resolve_attempts/last_resolve_attempt without resolving.

    Called when an attempt fails (no game log, API down, etc.) so the
    retry-window cleanup can decide when to give up.
    """
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    _db_write(
        "UPDATE bets SET "
        "  resolve_attempts = COALESCE(resolve_attempts, 0) + 1, "
        "  last_resolve_attempt = ? "
        "WHERE bet_id = ?",
        (now_iso, bet_id),
        caller="stamp_resolve_attempt",
    )


def delete_unresolved_bets_older_than(days: int = 3) -> int:
    """Delete pending bets whose bet_date is older than ``days`` ago.

    Implements the "if we couldn't resolve it, it never happened" rule.
    Only removes bets that still have NULL/empty result. Returns the
    deleted row count (best-effort â€” SQLite/PG cursor.rowcount).
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    cur = _db_write(
        "DELETE FROM bets WHERE bet_date < ? AND (result IS NULL OR result = '')",
        (cutoff,),
        caller="delete_unresolved_bets_older_than",
    )
    try:
        return int(cur.rowcount or 0) if cur is not None else 0
    except Exception:
        return 0


def void_team_bets(date_str: str, teams: list[str], reason: str) -> int:
    """VOID all pending bets on ``date_str`` for any of the given teams.

    Used by the postponement handler: ESPN reports a game never reached
    Final, so neither team's bets can be resolved. Marks them VOID with
    the supplied reason. Returns the number of rows updated.
    """
    if not teams:
        return 0
    try:
        # Build placeholder list for the IN clause.
        placeholders = ",".join(["?"] * len(teams))
        sql = (
            f"UPDATE bets SET result = 'VOID', void_reason = ?, "
            f"  last_resolve_attempt = ? "
            f"WHERE bet_date = ? AND (result IS NULL OR result = '') "
            f"  AND team IN ({placeholders})"
        )
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        params = (reason, now_iso, date_str, *teams)
        cur = _db_write(sql, params, caller="void_team_bets")
        try:
            return int(cur.rowcount or 0) if cur is not None else 0
        except Exception:
            return 0
    except Exception as exc:
        _logger.error("void_team_bets failed (%s, teams=%s): %s", date_str, teams, exc)
        return 0


def cleanup_props_cache(days: int = 30) -> None:
    """Trim the props_cache table to the last ``days`` days."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    _db_write(
        "DELETE FROM props_cache WHERE for_date < ?",
        (cutoff,),
        caller="cleanup_props_cache",
    )


# â”€â”€ Joseph M. Smith DB helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def save_joseph_diary_entry(date_str: str, entry: dict) -> bool:
    """Upsert a Joseph diary entry for *date_str* (YYYY-MM-DD)."""
    import json as _json
    try:
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        _db_write(
            "INSERT INTO joseph_diary "
            "(diary_date, wins, losses, mood, narrative, picks_json, week_summary_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(diary_date) DO UPDATE SET "
            "wins=excluded.wins, losses=excluded.losses, mood=excluded.mood, "
            "narrative=excluded.narrative, picks_json=excluded.picks_json, "
            "week_summary_json=excluded.week_summary_json, updated_at=excluded.updated_at",
            (
                date_str,
                entry.get("wins", 0),
                entry.get("losses", 0),
                entry.get("mood", "neutral"),
                entry.get("narrative", ""),
                _json.dumps(entry.get("picks", [])),
                _json.dumps(entry.get("week_summary", {})),
                now_iso,
                now_iso,
            ),
            caller="save_joseph_diary",
        )
        return True
    except Exception as exc:
        _logger.debug("save_joseph_diary_entry failed: %s", exc)
        return False


def load_joseph_diary_entry(date_str: str) -> dict | None:
    """Load a Joseph diary entry for *date_str*. Returns None if not found."""
    import json as _json
    try:
        rows = _db_read(
            "SELECT wins, losses, mood, narrative, picks_json, week_summary_json "
            "FROM joseph_diary WHERE diary_date = ?",
            (date_str,),
        )
        if not rows:
            return None
        row = rows[0]
        entry: dict = {
            "wins": row["wins"] or 0,
            "losses": row["losses"] or 0,
            "mood": row["mood"] or "neutral",
            "narrative": row["narrative"] or "",
        }
        try:
            entry["picks"] = _json.loads(row["picks_json"] or "[]")
        except Exception:
            entry["picks"] = []
        try:
            entry["week_summary"] = _json.loads(row["week_summary_json"] or "{}")
        except Exception:
            entry["week_summary"] = {}
        return entry
    except Exception as exc:
        _logger.debug("load_joseph_diary_entry failed: %s", exc)
        return None


def load_joseph_full_diary() -> dict:
    """Load all Joseph diary entries as a {date_str: entry} dict."""
    import json as _json
    try:
        rows = _db_read(
            "SELECT diary_date, wins, losses, mood, narrative, picks_json, week_summary_json "
            "FROM joseph_diary ORDER BY diary_date",
            (),
        )
        result: dict = {}
        for row in rows:
            entry: dict = {
                "wins": row["wins"] or 0,
                "losses": row["losses"] or 0,
                "mood": row["mood"] or "neutral",
                "narrative": row["narrative"] or "",
            }
            try:
                entry["picks"] = _json.loads(row["picks_json"] or "[]")
            except Exception:
                entry["picks"] = []
            try:
                entry["week_summary"] = _json.loads(row["week_summary_json"] or "{}")
            except Exception:
                entry["week_summary"] = {}
            result[row["diary_date"]] = entry
        return result
    except Exception as exc:
        _logger.debug("load_joseph_full_diary failed: %s", exc)
        return {}


def get_joseph_player_history(player_name: str, stat_type: str) -> dict | None:
    """Return Joseph's tracked accuracy record for *player_name* / *stat_type*."""
    try:
        rows = _db_read(
            "SELECT total_picks, wins, losses, last_verdict, last_pick_date, notes "
            "FROM joseph_player_history WHERE player_name = ? AND stat_type = ?",
            (player_name, stat_type),
        )
        if not rows:
            return None
        row = rows[0]
        total = row["total_picks"] or 0
        wins = row["wins"] or 0
        return {
            "total_picks": total,
            "wins": wins,
            "losses": row["losses"] or 0,
            "win_rate": round(wins / total, 3) if total > 0 else 0.0,
            "last_verdict": row["last_verdict"],
            "last_pick_date": row["last_pick_date"],
            "notes": row["notes"] or "",
        }
    except Exception as exc:
        _logger.debug("get_joseph_player_history failed: %s", exc)
        return None


def update_joseph_player_history(
    player_name: str,
    stat_type: str,
    verdict: str,
    was_correct: bool | None,
) -> bool:
    """Increment Joseph's per-player accuracy stats after a result resolves."""
    try:
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        today = datetime.date.today().isoformat()
        win_inc = 1 if was_correct else 0
        loss_inc = 1 if was_correct is False else 0
        _db_write(
            "INSERT INTO joseph_player_history "
            "(player_name, stat_type, total_picks, wins, losses, last_verdict, last_pick_date, created_at) "
            "VALUES (?, ?, 1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(player_name, stat_type) DO UPDATE SET "
            "total_picks = total_picks + 1, "
            "wins = wins + ?, "
            "losses = losses + ?, "
            "last_verdict = excluded.last_verdict, "
            "last_pick_date = excluded.last_pick_date",
            (
                player_name, stat_type, win_inc, loss_inc, verdict, today, now_iso,
                win_inc, loss_inc,
            ),
            caller="update_joseph_player_history",
        )
        return True
    except Exception as exc:
        _logger.debug("update_joseph_player_history failed: %s", exc)
        return False


def get_pending_bets_for_date(date_str: str) -> list[dict]:
    """Return all pending bets (no result yet) for the given NBA day."""
    rows = _db_read(
        "SELECT * FROM bets WHERE bet_date = ? AND (result IS NULL OR result = '')",
        (date_str,),
    )
    return [dict(r) for r in (rows or [])]


# ============================================================
# END SECTION: Pipeline Overhaul Helpers
# ============================================================

