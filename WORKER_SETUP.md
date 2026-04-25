# Worker Service Setup (Railway)

The pipeline overhaul (Phase 5) splits Smart Pick Pro into two Railway
services that share the same Postgres database:

| Service        | Process                                | Purpose                                               |
| -------------- | -------------------------------------- | ----------------------------------------------------- |
| `web`          | `python start.py`                      | Streamlit UI + FastAPI                                |
| `worker`       | `python slate_worker.py --daemon`      | Multi-job scheduler (props/ETL/bet-logging/resolve)   |

## Why a separate worker?

The Streamlit app no longer auto-logs bets on page load.  All
auto-logging, auto-resolution, postponement detection, and slate cache
warming happen in the worker so the UI is read-only against the `bets`
table.  This keeps page loads fast and prevents two users hitting the
DB at the same time from racing on writes.

## Railway setup steps

The repo has a `Procfile` declaring both processes, **but Railway does
not auto-create a worker service from a Procfile when the build is
Docker-based.**  You add the worker service manually:

1. Open the Railway project dashboard for `smart-pick-pro-pd`.
2. Click **+ New** → **Empty Service**.  Name it `worker`.
3. In the new service's **Settings**:
   - **Source**: connect to the same GitHub repo (`bucks551010/smart-pick-pro-pd`), branch `master`.
   - **Build**: select **Dockerfile** (re-uses the same image as `web`).
   - **Custom Start Command**: `python slate_worker.py --daemon`
   - **Healthcheck Path**: leave blank (worker is not an HTTP service).
   - **Restart Policy**: `On Failure`, max retries `5`.
4. **Variables** tab: click **Reference Variables** → select the `web`
   service, copy all variables (or at minimum `DATABASE_URL`,
   `ODDS_API_KEY`, `BET_PENDING_RETRY_DAYS`, `QAM_SIM_DEPTH`,
   `SLATE_WORKER_LOG`).
5. Click **Deploy**.  The first deploy will catch up on every job
   (props refresh, ETL refresh, nightly sweep) before settling into
   the schedule.

## Environment variables

| Variable                   | Default | Purpose                                                              |
| -------------------------- | ------- | -------------------------------------------------------------------- |
| `BET_PENDING_RETRY_DAYS`   | `3`     | Days to keep retrying unresolved bets before deletion                |
| `QAM_SIM_DEPTH`            | `1000`  | Quantum simulation depth (lower = faster worker, less precise)       |
| `SLATE_WORKER_LOG`         | `INFO`  | Worker log verbosity (`DEBUG` for development, `WARNING` for prod)   |
| `SLATE_WORKER_INTERVAL_MIN`| `30`    | Scheduler tick interval (jobs have their own per-job schedules)      |

## Schedule (ET-anchored)

| Job              | Frequency                       | Action                                                        |
| ---------------- | ------------------------------- | ------------------------------------------------------------- |
| `props_refresh`  | every 30 min                    | fetch props → analysis → `all_analysis_picks`                 |
| `etl_refresh`    | daily at 06:00 ET               | advanced metrics + defensive ratings                          |
| `bet_logging`    | 2 hours before first tip-off    | log smart_money + qeg + platform_ai + quantum bets            |
| `auto_resolve`   | every 30 min                    | resolve completed games with full CLV/distance tracking       |
| `nightly_sweep`  | daily at 02:30 ET               | postponements + 3-day retry cleanup + props_cache cleanup + daily snapshot |

## Catch-up behaviour

On every restart the worker reads the `worker_state` table and runs any
job whose last successful run is older than its schedule.  This means a
deploy or crash never causes a missed slate — the worker resumes
immediately on boot.

## Monitoring

Tail the worker logs in the Railway dashboard, or query the DB:

```sql
SELECT job_name, last_run_at, last_status, last_error, run_count
  FROM worker_state
 ORDER BY last_run_at DESC;
```

Per-source betting performance:

```python
from tracking.bet_tracker import get_pipeline_performance_stats
get_pipeline_performance_stats()
# → {'qeg': {'wins': 37, 'losses': 16, 'win_rate': 0.698, ...}, ...}
```
