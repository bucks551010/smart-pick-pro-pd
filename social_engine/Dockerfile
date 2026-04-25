# ── Social Engine worker — FastAPI + APScheduler + Playwright ──
# Cache-bust: 2026-04-24b
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install pip packages first (cached layer)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# playwright install --with-deps handles ALL system deps for Chromium
# (avoids manual apt package names that differ across Debian versions)
RUN playwright install --with-deps chromium

COPY . .
# Pre-create _out so it exists with correct ownership regardless of run user
RUN mkdir -p /app/_out

EXPOSE 8000

# start.py reads $PORT (Railway injects it) and starts uvicorn
CMD ["python", "start.py"]
