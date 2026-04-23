# SmartPickPro — Social Engine

Autonomous social-media asset generator and distribution engine for the
SmartPickPro NBA quantitative analytics platform.

> **One repo, two services.** Streamlit UI for manual campaigns +
> FastAPI worker (with APScheduler) for autonomous posting.

## What it does

| Pillar | Component | Files |
|---|---|---|
| **Factory** | Jinja2 HTML/CSS templates → Playwright headless PNG (1080×1080, 1200×675, 1080×1920) | `templates/`, `render/` |
| **Shield** | QR + UTM tracking, low-opacity watermark, compliance footer | `core/qr.py`, `templates/_base.css` |
| **Megaphone** | Gemini copy gen (3 tones) → Tweepy / Meta Graph / TikTok auto-posters | `core/llm_copy.py`, `distribute/` |
| **Autopilot** | APScheduler (morning recap, T-2h pre-game, branding cron) + FastAPI webhook | `webhook/api.py`, `scheduler/jobs.py` |

## Architecture

```
                                ┌──────────────────────┐
                                │  Main Smart Pick Pro │
                                │   Postgres / SQLite  │
                                └──────────┬───────────┘
                                           │ shared DATABASE_URL
                       ┌───────────────────┴───────────────────┐
                       │                                       │
              ┌────────▼─────────┐                  ┌──────────▼──────────┐
              │  Streamlit UI    │                  │  FastAPI Worker     │
              │  (manual posts)  │                  │  + APScheduler      │
              │  port 8501       │                  │  port 8000          │
              └────────┬─────────┘                  └──────────┬──────────┘
                       │                                       │
                       └───────────────┬───────────────────────┘
                                       │
                  ┌────────┬───────────┼───────────┬─────────┐
                  ▼        ▼           ▼           ▼         ▼
                Twitter  Facebook  Instagram   Threads   TikTok
```

## Quick start (local)

```bash
cd social_engine
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
playwright install --with-deps chromium

cp .env.example .env
# fill in DATABASE_URL + (optional) GEMINI_API_KEY first

# UI:
streamlit run app.py

# Worker (in a second terminal):
uvicorn webhook.api:app --reload --port 8000
```

## Railway deploy (2 services from this repo)

Create **two** services in your Railway project, both rooted at `/social_engine`:

| Service | Start command | Port |
|---|---|---|
| `social-ui` | `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` | 8501 |
| `social-worker` | `uvicorn webhook.api:app --host 0.0.0.0 --port $PORT` | 8000 |

Both services share the same env vars (see `.env.example`). The `Dockerfile`
already supports both modes via `START_MODE=ui` (default) or `START_MODE=worker`.

## Scheduler cadence

| Job | Trigger | Default |
|---|---|---|
| Morning recap | Cron daily | `09:00 America/New_York` |
| Pre-game scanner | Every 15 min | Posts when any game tips in `T+2h` to `T+3h` window |
| Branding / CTA | Cron weekly | `0 14 * * 2,5` (Tue & Fri 2pm) |

All adjustable via env vars: `RECAP_HOUR_LOCAL`, `PREGAME_LEAD_HOURS`, `BRANDING_CRON`.

## Webhook endpoints (worker only)

All POST endpoints require header `X-Webhook-Secret: <WEBHOOK_SHARED_SECRET>`.

```bash
# Force a morning recap right now
curl -X POST https://your-worker.railway.app/trigger/morning-recap \
     -H "X-Webhook-Secret: $SECRET"

# Force a pre-game slate post
curl -X POST "https://your-worker.railway.app/trigger/pregame?pick_filter=top3" \
     -H "X-Webhook-Secret: $SECRET"

# Branding push
curl -X POST https://your-worker.railway.app/trigger/branding \
     -H "X-Webhook-Secret: $SECRET"

# Main app calls this when a notable W/L milestone hits
curl -X POST https://your-worker.railway.app/trigger/success \
     -H "X-Webhook-Secret: $SECRET"
```

## Credentials

See [`CREDENTIALS.md`](./CREDENTIALS.md) — step-by-step for every API key.
The engine works in **demo mode** (deterministic copy fallback, channels report
"not configured") with zero credentials, so you can preview templates immediately.

## Compliance

Every generated graphic includes:
- Anti-theft watermark (~4% opacity, repeating brand text, rotated)
- Compliance footer: `21+ • Play Responsibly • Not gambling advice • For entertainment only • Problem? Call 1-800-GAMBLER`
- QR code with embedded UTM params (`utm_source`, `utm_medium`, `utm_campaign`)

The LLM copy prompt explicitly forbids guarantees, "lock", "#1" claims.
