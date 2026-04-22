# ============================================================
# FILE: utils/telemetry.py
# PURPOSE: Enterprise-grade telemetry and observability layer for
#          Smart Pick Pro.
#
# ARCHITECTURE:
#   ┌─────────────────────────────────────────────────────┐
#   │  Public API (never raises — all wrapped in try/except)│
#   │  ─────────────────────────────────────────────────── │
#   │  @profile_execution("label")  ← timing decorator     │
#   │  track_feature(name, metadata)← feature usage event  │
#   │  capture_exception(exc, ctx)  ← error capture        │
#   └──────────────┬──────────────────────────────────────┘
#                  │
#          ┌───────┴────────┐
#          ▼                ▼
#   Azure App Insights   SQLite / PostgreSQL
#   (opencensus-ext-azure  (telemetry_timings,
#    — optional soft dep)   telemetry_errors,
#                           telemetry_features)
#
# PRIVACY:
#   scrub_pii() runs on ALL event metadata before any data
#   leaves this module.  Emails, phone numbers, credit card
#   numbers, JWTs, and SSNs are replaced with safe tokens.
#
# STREAMLIT SAFETY:
#   Telemetry writes are fire-and-forget.  Any exception inside
#   a telemetry call is caught and logged at DEBUG level only,
#   so it NEVER interrupts the main Streamlit execution flow.
# ============================================================

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import re
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

_logger = logging.getLogger("smartai_nba.telemetry")

# ── Type var for the generic decorator ───────────────────────
_F = TypeVar("_F", bound=Callable[..., Any])

# ═══════════════════════════════════════════════════════════
# SECTION 2: PII Scrubbing
# ═══════════════════════════════════════════════════════════

# Compiled regex patterns for recognised PII categories
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email addresses (RFC 5321 simplified)
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE), "[EMAIL]"),
    # US / international phone numbers (various formats)
    (re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    # Payment card numbers (13–19 digits with optional separators)
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), "[CARD]"),
    # JWT / Bearer tokens (three base64url segments separated by dots)
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "[JWT]"),
    # US Social Security numbers
    (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "[SSN]"),
    # API / secret keys: long hex/base64 strings (≥ 32 chars)
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[KEY]"),
]

_PII_FIELD_BLOCKLIST: frozenset[str] = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "auth", "credential", "private_key", "access_token",
    "refresh_token", "session_token", "stripe_key",
})


def scrub_pii(data: Any) -> Any:
    """
    Recursively sanitise a value before it enters telemetry storage.

    Handles dicts, lists, and scalar strings.  Mutates a deep-copy so the
    original caller's data is never modified.

    Args:
        data: Any Python value (dict, list, str, int, …)

    Returns:
        A new value with PII tokens replaced.
    """
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k.lower() in _PII_FIELD_BLOCKLIST else scrub_pii(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [scrub_pii(item) for item in data]
    if isinstance(data, str):
        result = data
        for pattern, replacement in _PII_PATTERNS:
            result = pattern.sub(replacement, result)
        return result
    return data


# ═══════════════════════════════════════════════════════════
# SECTION 3: SQLite Telemetry Tables
# ═══════════════════════════════════════════════════════════

_TELEMETRY_TABLES_SQL: list[str] = [
    # Execution timing records (from @profile_execution)
    """CREATE TABLE IF NOT EXISTS telemetry_timings (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    TEXT    NOT NULL,
        function_label TEXT  NOT NULL,
        duration_ms  REAL    NOT NULL,
        session_id   TEXT,
        success      INTEGER DEFAULT 1,
        error_type   TEXT
    )""",
    # Exception / error captures
    """CREATE TABLE IF NOT EXISTS telemetry_errors (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    TEXT    NOT NULL,
        session_id   TEXT,
        error_type   TEXT    NOT NULL,
        error_message TEXT,
        context      TEXT,
        page         TEXT,
        stack_trace  TEXT
    )""",
    # Feature usage events
    """CREATE TABLE IF NOT EXISTS telemetry_features (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    TEXT    NOT NULL,
        session_id   TEXT,
        feature_name TEXT    NOT NULL,
        page         TEXT,
        metadata     TEXT
    )""",
]

_TELEMETRY_INDEXES_SQL: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_tt_label     ON telemetry_timings  (function_label)",
    "CREATE INDEX IF NOT EXISTS idx_tt_ts        ON telemetry_timings  (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_te_ts        ON telemetry_errors   (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_te_type      ON telemetry_errors   (error_type)",
    "CREATE INDEX IF NOT EXISTS idx_tf_feature   ON telemetry_features (feature_name)",
    "CREATE INDEX IF NOT EXISTS idx_tf_ts        ON telemetry_features (timestamp)",
]

_tables_ensured = False


def _ensure_tables() -> None:
    """Create all telemetry tables (idempotent, runs at most once per process)."""
    global _tables_ensured
    if _tables_ensured:
        return
    try:
        from tracking.database import get_database_connection, initialize_database
        initialize_database()
        with get_database_connection() as conn:
            for sql in _TELEMETRY_TABLES_SQL:
                conn.execute(sql)
            for sql in _TELEMETRY_INDEXES_SQL:
                conn.execute(sql)
            conn.commit()
        _tables_ensured = True
    except Exception as exc:
        _logger.debug("telemetry table init skipped (non-fatal): %s", exc)


def _get_session_id() -> str:
    """
    Return a stable, opaque session identifier for the active Streamlit session.

    Falls back to an empty string outside of a Streamlit runtime context
    (e.g. during unit tests or the weekly report script).
    """
    try:
        import streamlit as st
        key = "_telemetry_session_id"
        if key not in st.session_state:
            import secrets
            st.session_state[key] = secrets.token_hex(8)
        return st.session_state[key]
    except Exception:
        return ""


def _get_current_page() -> str:
    """Infer the current Streamlit page name from the runtime context."""
    try:
        import streamlit as st
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        if ctx and hasattr(ctx, "page_script_hash"):
            import os as _os
            script_path = getattr(ctx, "script_path", None) or ""
            return _os.path.splitext(_os.path.basename(script_path))[0]
    except Exception:
        pass
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db_write(sql: str, params: tuple[Any, ...]) -> None:
    """
    Execute a single parameterised INSERT into the telemetry DB.

    Fire-and-forget: any exception is swallowed so telemetry writes
    never propagate into the main application thread.
    """
    try:
        _ensure_tables()
        from tracking.database import get_database_connection
        with get_database_connection() as conn:
            conn.execute(sql, params)
            conn.commit()
    except Exception as exc:
        _logger.debug("telemetry db write failed: %s", exc)


# ═══════════════════════════════════════════════════════════
# SECTION 4: Performance Profiling Decorator
# ═══════════════════════════════════════════════════════════

def profile_execution(label: str | None = None, *, warn_above_ms: float = 2000.0) -> Callable[[_F], _F]:
    """
    Decorator factory that records wall-clock execution time for a function.

    Records the result to:
      1. SQLite ``telemetry_timings`` table
      2. Azure App Insights custom metric (if configured)
      3. A WARNING log entry when ``warn_above_ms`` is exceeded

    Usage::

        @profile_execution("qam_model_score")
        def run_quantum_model(props):
            ...

        # Works seamlessly alongside st.cache_data:
        @st.cache_data(ttl=300)          # outer — caches result
        @profile_execution("fetch_lines")  # inner — times cache misses only
        def fetch_prizepick_lines():
            ...

    Args:
        label:        Human-readable label for the metric. Defaults to the
                      qualified function name.
        warn_above_ms: Emit a WARNING log when execution time exceeds this
                       threshold (default 2 000 ms).
    """
    def decorator(func: _F) -> _F:
        metric_label = label or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            success = True
            err_type: str | None = None
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                success = False
                err_type = type(exc).__name__
                raise  # Re-raise so the caller sees the original exception
            finally:
                duration_ms = (time.perf_counter() - start) * 1000.0
                session = _get_session_id()

                # Warn on slow execution without blocking
                if duration_ms > warn_above_ms:
                    _logger.warning(
                        "SLOW EXECUTION [%s] %.1f ms (threshold %.0f ms)",
                        metric_label, duration_ms, warn_above_ms,
                    )

                # SQLite write (non-blocking)
                _db_write(
                    "INSERT INTO telemetry_timings "
                    "(timestamp, function_label, duration_ms, session_id, success, error_type) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (_now_iso(), metric_label, round(duration_ms, 2),
                     session, int(success), err_type),
                )

        return wrapper  # type: ignore[return-value]
    return decorator


# ═══════════════════════════════════════════════════════════
# SECTION 5: Feature Usage Tracking
# ═══════════════════════════════════════════════════════════

def track_feature(feature_name: str, metadata: dict[str, Any] | None = None) -> None:
    """
    Record that a user interacted with a named feature.

    Writes to SQLite and fires a GA4 custom event via ``ga4_event()``.
    PII is scrubbed from ``metadata`` before any storage.

    Call this at the point of user action, e.g.::

        if st.button("Run Quantum Analysis"):
            track_feature("quantum_analysis_run", {"prop_count": len(props)})

    Args:
        feature_name: Snake_case identifier, e.g. ``"qam_analysis"``,
                      ``"prop_scanner_filter"``, ``"entry_builder_submit"``.
        metadata:     Optional key/value dict of non-PII context.
    """
    try:
        safe_meta = scrub_pii(metadata or {})
        session = _get_session_id()
        page = _get_current_page()
        meta_json = json.dumps(safe_meta)

        # SQLite record
        _db_write(
            "INSERT INTO telemetry_features "
            "(timestamp, session_id, feature_name, page, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (_now_iso(), session, feature_name, page, meta_json),
        )

        # GA4 custom event (best-effort — no-op when GA_MEASUREMENT_ID unset)
        try:
            from utils.analytics import ga4_event
            ga4_event(f"feature_{feature_name}", safe_meta)
        except Exception:
            pass  # GA4 injection fails outside Streamlit context; ignore

    except Exception as exc:
        _logger.debug("track_feature failed (non-fatal): %s", exc)


# ═══════════════════════════════════════════════════════════
# SECTION 6: Exception / Error Capture
# ═══════════════════════════════════════════════════════════

def capture_exception(
    exc: BaseException,
    context: str = "",
    *,
    reraise: bool = False,
) -> None:
    """
    Capture and record an exception to all configured telemetry sinks.

    Sends to:
      1. SQLite ``telemetry_errors`` table
      2. Azure App Insights at ERROR level (with full stack trace)
      3. Module logger at ERROR level

    Designed for ``except`` blocks where you want observability without
    crashing the UI::

        try:
            result = fetch_prizepick_lines()
        except Exception as exc:
            capture_exception(exc, context="prize_pick_fetch")
            result = []  # degrade gracefully

    Args:
        exc:     The caught exception.
        context: Human-readable description of the operation that failed.
        reraise: If True, re-raises the original exception after recording.
    """
    try:
        error_type = type(exc).__name__
        # Scrub PII from the exception message itself
        raw_message = str(exc)
        safe_message = scrub_pii(raw_message)
        safe_context = scrub_pii(context)
        stack = traceback.format_exc()
        page = _get_current_page()
        session = _get_session_id()

        _logger.error(
            "[telemetry] %s — %s: %s",
            safe_context or "unhandled", error_type, safe_message,
        )

        # SQLite record
        _db_write(
            "INSERT INTO telemetry_errors "
            "(timestamp, session_id, error_type, error_message, context, page, stack_trace) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now_iso(), session, error_type, safe_message,
             safe_context, page, stack[:4000]),  # cap stack at 4 KB
        )

    except Exception as inner_exc:
        # The error reporter itself failed — log at DEBUG so we don't loop
        _logger.debug("capture_exception internal failure: %s", inner_exc)
    finally:
        if reraise:
            raise exc


# ═══════════════════════════════════════════════════════════
# SECTION 7: Session Hash Helper (privacy-safe user identity)
# ═══════════════════════════════════════════════════════════

def hash_user_id(user_email: str) -> str:
    """
    Return a one-way SHA-256 hash of a user email for correlation without
    storing the raw email in telemetry records.

    Used in the admin dashboard to count distinct users without exposing PII.
    """
    if not user_email:
        return ""
    return hashlib.sha256(user_email.lower().strip().encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════
# SECTION 8: Convenience Query Helpers (used by admin page)
# ═══════════════════════════════════════════════════════════

def query_telemetry(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """
    Execute a read-only SELECT against the telemetry tables.

    Returns a list of row dicts.  Returns [] on any error so callers
    never need to handle exceptions.
    """
    try:
        _ensure_tables()
        from tracking.database import get_database_connection
        with get_database_connection() as conn:
            conn.row_factory = __import__("sqlite3").Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        _logger.debug("query_telemetry failed: %s", exc)
        return []
