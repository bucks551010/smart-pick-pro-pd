"""FastAPI webhook + APScheduler — runs as the `worker` service.

Endpoints:
  GET  /healthz                        — liveness probe
  POST /trigger/morning-recap          — fire the morning recap immediately
  POST /trigger/pregame                — fire pre-game slate (?filter=top3|qeg|platform:X)
  POST /trigger/branding               — fire branding/CTA push
  POST /trigger/success                — autonomous post triggered by main app

All POST endpoints require header `X-Webhook-Secret: <WEBHOOK_SHARED_SECRET>`.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Header, HTTPException, Query

from config import SETTINGS
from core import data_source as ds
from scheduler.jobs import (
    build_and_post_branding,
    build_and_post_morning_recap,
    build_and_post_pregame_slate,
    build_and_post_weekly_scorecard,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
_log = logging.getLogger("webhook")

_scheduler: Optional[BackgroundScheduler] = None


# ── Pre-game scanner ─────────────────────────────────────────
def _pregame_scan():
    """Runs every 15min. Posts T-2h before any tipoff."""
    games = ds.get_games_starting_in((SETTINGS.pregame_lead_hours, SETTINGS.pregame_lead_hours + 1))
    if not games:
        return
    _log.info("Pre-game scan: %d games tipping in window — posting top-3 slate", len(games))
    build_and_post_pregame_slate(pick_filter="top3")


def _start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone=SETTINGS.timezone)

    # 1. Morning recap — daily at RECAP_HOUR_LOCAL
    sched.add_job(
        build_and_post_morning_recap,
        CronTrigger(hour=SETTINGS.recap_hour, minute=0, timezone=SETTINGS.timezone),
        id="morning_recap", replace_existing=True,
    )
    # 2. Pre-game scanner — every 15 minutes
    sched.add_job(
        _pregame_scan,
        IntervalTrigger(minutes=15),
        id="pregame_scan", replace_existing=True,
    )
    # 3. Weekly scorecard — every Sunday at 10am local
    sched.add_job(
        build_and_post_weekly_scorecard,
        CronTrigger(hour=10, minute=0, day_of_week="sun", timezone=SETTINGS.timezone),
        id="weekly_scorecard", replace_existing=True,
    )
    # 4. Branding cadence — cron expression
    parts = SETTINGS.branding_cron.split()
    if len(parts) == 5:
        m, h, dom, mon, dow = parts
        sched.add_job(
            build_and_post_branding,
            CronTrigger(minute=m, hour=h, day=dom, month=mon, day_of_week=dow,
                        timezone=SETTINGS.timezone),
            id="branding", replace_existing=True,
        )
    sched.start()
    _log.info("APScheduler started — recap=%02d:00 %s | pregame=every 15min | branding=%s | weekly=Sun 10:00",
              SETTINGS.recap_hour, SETTINGS.timezone, SETTINGS.branding_cron)
    return sched


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    if SETTINGS.scheduler_enabled:
        _scheduler = _start_scheduler()
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="SmartPickPro Social Engine", lifespan=lifespan)


def _auth(secret: str | None) -> None:
    if not SETTINGS.webhook_secret:
        raise HTTPException(503, "WEBHOOK_SHARED_SECRET not configured")
    if secret != SETTINGS.webhook_secret:
        raise HTTPException(401, "invalid webhook secret")


# ── Endpoints ────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"ok": True, "scheduler": _scheduler is not None}


@app.post("/trigger/morning-recap")
def trigger_recap(x_webhook_secret: str | None = Header(default=None)):
    _auth(x_webhook_secret)
    results = build_and_post_morning_recap()
    return {"results": [r.__dict__ for r in results]}


@app.post("/trigger/pregame")
def trigger_pregame(
    pick_filter: str = Query("top3"),
    x_webhook_secret: str | None = Header(default=None),
):
    _auth(x_webhook_secret)
    results = build_and_post_pregame_slate(pick_filter=pick_filter)
    return {"results": [r.__dict__ for r in results]}


@app.post("/trigger/branding")
def trigger_branding(x_webhook_secret: str | None = Header(default=None)):
    _auth(x_webhook_secret)
    results = build_and_post_branding()
    return {"results": [r.__dict__ for r in results]}


@app.post("/trigger/success")
def trigger_success(x_webhook_secret: str | None = Header(default=None)):
    """Called by main app when a notable W/L milestone hits.

    The main app should evaluate the trigger condition (e.g. perfect sweep,
    ROI > X%) and POST here. We just fire the recap graphic immediately.
    """
    _auth(x_webhook_secret)
    results = build_and_post_morning_recap()
    return {"results": [r.__dict__ for r in results]}
