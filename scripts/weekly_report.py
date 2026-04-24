#!/usr/bin/env python3
# ============================================================
# FILE: scripts/weekly_report.py
# PURPOSE: Aggregate raw telemetry data into an executive-grade
#          weekly performance summary.
#
# USAGE:
#   # Run directly from the project root:
#   python scripts/weekly_report.py
#
#   # Or import and call programmatically:
#   from scripts.weekly_report import generate_weekly_report
#   summary = generate_weekly_report()
#
#   # Schedule via cron (every Monday at 07:00):
#   0 7 * * 1  cd /app && python scripts/weekly_report.py
#
#   # Or Railway CRON job (railway.toml):
#   [crons.weekly_report]
#   schedule = "0 7 * * 1"
#   command  = "python scripts/weekly_report.py"
#
# OUTPUT:
#   logs/weekly_report_YYYY-MM-DD.json  — machine-readable summary
#   logs/weekly_report_YYYY-MM-DD.txt   — human-readable executive digest
#   Optional email delivery when SMTP_HOST + REPORT_RECIPIENTS are set.
#
# PRIVACY:
#   All user identifiers in the output are SHA-256 hashed.
#   Raw email addresses never appear in report files or email payloads.
# ============================================================

from __future__ import annotations

import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

# ── Bootstrap path so the script can find the project modules ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env if present (Railway / local dev)
try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
_logger = logging.getLogger("smartai.weekly_report")

_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════
# SECTION 1: Data Aggregation
# ═══════════════════════════════════════════════════════════

def _query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Execute a read-only query against the telemetry database."""
    try:
        from tracking.database import get_database_connection, initialize_database
        initialize_database()
        import sqlite3
        with get_database_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        _logger.warning("DB query failed: %s", exc)
        return []


def _aggregate_feature_usage(since: str) -> list[dict[str, Any]]:
    """Top features by activation count for the report period."""
    return _query(
        """
        SELECT
            feature_name,
            COUNT(*)                        AS total_activations,
            COUNT(DISTINCT session_id)      AS unique_sessions,
            page
        FROM   telemetry_features
        WHERE  timestamp >= ?
        GROUP  BY feature_name
        ORDER  BY total_activations DESC
        LIMIT  20
        """,
        (since,),
    )


def _aggregate_performance(since: str) -> list[dict[str, Any]]:
    """Per-function latency statistics for the report period."""
    return _query(
        """
        SELECT
            function_label,
            COUNT(*)                                AS calls,
            ROUND(AVG(duration_ms), 1)              AS avg_ms,
            ROUND(MIN(duration_ms), 1)              AS min_ms,
            ROUND(MAX(duration_ms), 1)              AS max_ms,
            SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS error_calls
        FROM   telemetry_timings
        WHERE  timestamp >= ?
        GROUP  BY function_label
        ORDER  BY avg_ms DESC
        LIMIT  30
        """,
        (since,),
    )


def _aggregate_errors(since: str) -> list[dict[str, Any]]:
    """Error count by type for the report period."""
    return _query(
        """
        SELECT
            error_type,
            COUNT(*)           AS occurrences,
            COUNT(DISTINCT page) AS affected_pages,
            MAX(timestamp)     AS last_seen
        FROM   telemetry_errors
        WHERE  timestamp >= ?
        GROUP  BY error_type
        ORDER  BY occurrences DESC
        """,
        (since,),
    )


def _aggregate_daily_activity(since: str) -> list[dict[str, Any]]:
    """Daily event totals broken down by day for trend analysis."""
    return _query(
        """
        SELECT
            SUBSTR(timestamp, 1, 10)    AS day,
            COUNT(*)                    AS total_events,
            COUNT(DISTINCT session_id)  AS unique_sessions
        FROM   telemetry_features
        WHERE  timestamp >= ?
        GROUP  BY day
        ORDER  BY day
        """,
        (since,),
    )


def _aggregate_top_pages(since: str) -> list[dict[str, Any]]:
    """Most-visited pages by unique session count."""
    return _query(
        """
        SELECT
            page,
            COUNT(DISTINCT session_id)  AS unique_sessions,
            COUNT(*)                    AS page_events
        FROM   telemetry_features
        WHERE  timestamp >= ? AND page != ''
        GROUP  BY page
        ORDER  BY unique_sessions DESC
        LIMIT  15
        """,
        (since,),
    )


def _aggregate_ga4_events(since: str) -> list[dict[str, Any]]:
    """Top analytics events from the server-side event log."""
    return _query(
        """
        SELECT
            event_name,
            COUNT(*)                    AS occurrences,
            COUNT(DISTINCT session_id)  AS unique_sessions
        FROM   analytics_events
        WHERE  timestamp >= ?
        GROUP  BY event_name
        ORDER  BY occurrences DESC
        LIMIT  20
        """,
        (since,),
    )


# ═══════════════════════════════════════════════════════════
# SECTION 2: Report Generation
# ═══════════════════════════════════════════════════════════

def generate_weekly_report(
    days: int = 7,
    *,
    save_files: bool = True,
    send_email: bool = True,
) -> dict[str, Any]:
    """
    Aggregate the past ``days`` of telemetry into an executive summary dict.

    Args:
        days:        Number of days to look back (default 7).
        save_files:  Write JSON + TXT report files to ``logs/``.
        send_email:  Attempt email delivery if SMTP env vars are set.

    Returns:
        dict with keys: period, feature_usage, performance, errors,
        daily_activity, top_pages, ga4_events, kpis.
    """
    now_utc = datetime.now(timezone.utc)
    since   = (now_utc - timedelta(days=days)).isoformat(timespec="seconds")
    period  = {
        "from":         since,
        "to":           now_utc.isoformat(timespec="seconds"),
        "days":         days,
        "generated_at": now_utc.isoformat(timespec="seconds"),
    }

    _logger.info("Generating %d-day telemetry report (since %s)", days, since)

    feature_usage   = _aggregate_feature_usage(since)
    performance     = _aggregate_performance(since)
    errors          = _aggregate_errors(since)
    daily_activity  = _aggregate_daily_activity(since)
    top_pages       = _aggregate_top_pages(since)
    ga4_events      = _aggregate_ga4_events(since)

    # ── Derived KPIs for the executive summary ──────────────
    total_events = sum(d.get("total_events", 0) for d in daily_activity)
    total_sessions = len({
        row.get("unique_sessions") for row in daily_activity
    })
    peak_day = max(daily_activity, key=lambda d: d.get("total_events", 0), default={})
    total_errors = sum(e.get("occurrences", 0) for e in errors)
    error_rate_pct = (
        round(total_errors / total_events * 100, 2) if total_events > 0 else 0.0
    )
    slowest_fn = performance[0] if performance else {}

    # p95 approximation from the DB
    p95_rows = _query(
        """
        SELECT function_label, duration_ms
        FROM   telemetry_timings
        WHERE  timestamp >= ?
        ORDER  BY function_label, duration_ms
        """,
        (since,),
    )
    p95_by_fn: dict[str, float] = {}
    if p95_rows:
        from itertools import groupby
        for fn_label, grp in groupby(p95_rows, key=lambda r: r["function_label"]):
            durations = [r["duration_ms"] for r in grp]
            idx = max(0, int(len(durations) * 0.95) - 1)
            p95_by_fn[fn_label] = round(sorted(durations)[idx], 1)

    kpis = {
        "total_feature_events":      total_events,
        "top_feature":               feature_usage[0]["feature_name"] if feature_usage else "—",
        "top_feature_activations":   feature_usage[0]["total_activations"] if feature_usage else 0,
        "total_errors_in_period":    total_errors,
        "error_rate_percent":        error_rate_pct,
        "peak_activity_day":         peak_day.get("day", "—"),
        "peak_day_events":           peak_day.get("total_events", 0),
        "slowest_function":          slowest_fn.get("function_label", "—"),
        "slowest_function_avg_ms":   slowest_fn.get("avg_ms", 0),
        "top_page":                  top_pages[0]["page"] if top_pages else "—",
        "p95_latency_by_function":   p95_by_fn,
    }

    report: dict[str, Any] = {
        "period":         period,
        "kpis":           kpis,
        "feature_usage":  feature_usage,
        "performance":    performance,
        "errors":         errors,
        "daily_activity": daily_activity,
        "top_pages":      top_pages,
        "ga4_events":     ga4_events,
    }

    if save_files:
        _save_report_files(report, now_utc)

    if send_email:
        _maybe_send_email(report, now_utc)

    _logger.info("Weekly report complete.  KPIs: %s", kpis)
    return report


# ═══════════════════════════════════════════════════════════
# SECTION 3: File Output
# ═══════════════════════════════════════════════════════════

def _save_report_files(report: dict[str, Any], now: datetime) -> None:
    """Write machine-readable JSON and human-readable TXT digest."""
    date_str = now.strftime("%Y-%m-%d")

    # ── JSON (machine-readable) ──────────────────────────────
    json_path = _LOG_DIR / f"weekly_report_{date_str}.json"
    try:
        json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        _logger.info("JSON report saved: %s", json_path)
    except OSError as exc:
        _logger.warning("Could not write JSON report: %s", exc)

    # ── TXT (executive digest) ───────────────────────────────
    txt_path = _LOG_DIR / f"weekly_report_{date_str}.txt"
    try:
        txt_path.write_text(_render_executive_digest(report), encoding="utf-8")
        _logger.info("TXT digest saved: %s", txt_path)
    except OSError as exc:
        _logger.warning("Could not write TXT digest: %s", exc)


def _render_executive_digest(report: dict[str, Any]) -> str:
    """Render a plain-text executive summary suitable for email body."""
    p     = report["period"]
    kpis  = report["kpis"]
    feats = report["feature_usage"][:5]
    errs  = report["errors"][:5]
    perf  = report["performance"][:5]
    pages = report["top_pages"][:5]

    lines: list[str] = [
        "=" * 62,
        " SMART PICK PRO — WEEKLY PERFORMANCE SUMMARY",
        f" Period : {p['from']}  →  {p['to']}",
        f" Generated : {p['generated_at']}",
        "=" * 62,
        "",
        "── EXECUTIVE KPIs ──────────────────────────────────────",
        f"  Total Feature Events  : {kpis['total_feature_events']:,}",
        f"  Top Feature           : {kpis['top_feature']}  ({kpis['top_feature_activations']:,} activations)",
        f"  Peak Activity Day     : {kpis['peak_activity_day']}  ({kpis['peak_day_events']:,} events)",
        f"  Total Errors (period) : {kpis['total_errors_in_period']:,}  ({kpis['error_rate_percent']}% of events)",
        f"  Slowest Function      : {kpis['slowest_function']}  (avg {kpis['slowest_function_avg_ms']} ms)",
        f"  Top Page              : {kpis['top_page']}",
        "",
        "── TOP 5 FEATURES ──────────────────────────────────────",
    ]
    for i, f in enumerate(feats, 1):
        lines.append(
            f"  {i}. {f['feature_name']:<40} {f['total_activations']:>6} activations"
        )

    lines += ["", "── TOP 5 PAGES ─────────────────────────────────────────"]
    for i, pg in enumerate(pages, 1):
        lines.append(
            f"  {i}. {pg['page']:<40} {pg['unique_sessions']:>4} sessions"
        )

    lines += ["", "── PERFORMANCE (avg latency) ────────────────────────────"]
    for fn in perf:
        lines.append(
            f"  {fn['function_label']:<44} avg {fn['avg_ms']:>7} ms  "
            f"({fn['calls']} calls, {fn['error_calls']} errors)"
        )

    lines += ["", "── ERRORS ──────────────────────────────────────────────"]
    if errs:
        for e in errs:
            lines.append(
                f"  {e['error_type']:<35} {e['occurrences']:>4}×  last: {e['last_seen']}"
            )
    else:
        lines.append("  ✅ No errors recorded this period.")

    lines += ["", "=" * 62, ""]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# SECTION 4: Optional Email Delivery
# ═══════════════════════════════════════════════════════════

def _maybe_send_email(report: dict[str, Any], now: datetime) -> None:
    """
    Send the executive digest via SMTP if configured.

    Required env vars:
        SMTP_HOST          — SMTP server hostname (e.g. smtp.sendgrid.net)
        SMTP_PORT          — Port (default 587)
        SMTP_USER          — SMTP login username
        SMTP_PASSWORD      — SMTP login password
        REPORT_RECIPIENTS  — Comma-separated list of recipient emails
        REPORT_FROM        — Sender address (default noreply@smartpickpro.ai)
    """
    smtp_host   = os.environ.get("SMTP_HOST", "")
    smtp_user   = os.environ.get("SMTP_USER", "")
    smtp_pass   = os.environ.get("SMTP_PASSWORD", "")
    recipients  = [r.strip() for r in os.environ.get("REPORT_RECIPIENTS", "").split(",") if r.strip()]

    if not all([smtp_host, smtp_user, smtp_pass, recipients]):
        _logger.debug("Email delivery skipped — SMTP env vars not fully configured.")
        return

    smtp_port   = int(os.environ.get("SMTP_PORT", "587"))
    sender      = os.environ.get("REPORT_FROM", "noreply@smartpickpro.ai")
    subject     = f"Smart Pick Pro — Weekly Report ({now.strftime('%Y-%m-%d')})"
    body_text   = _render_executive_digest(report)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, recipients, msg.as_string())
        _logger.info("Weekly report emailed to: %s", recipients)
    except Exception as exc:
        _logger.warning("Email delivery failed (non-fatal): %s", exc)


# ═══════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Smart Pick Pro weekly performance report")
    parser.add_argument("--days",    type=int,  default=7,    help="Lookback window in days (default: 7)")
    parser.add_argument("--no-save", action="store_true",     help="Skip writing report files to disk")
    parser.add_argument("--no-email",action="store_true",     help="Skip email delivery even if SMTP is configured")
    args = parser.parse_args()

    summary = generate_weekly_report(
        days=args.days,
        save_files=not args.no_save,
        send_email=not args.no_email,
    )

    print(_render_executive_digest(summary))
