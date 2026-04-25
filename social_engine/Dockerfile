# Social Engine worker - FastAPI + APScheduler + Playwright
# Cache-bust: 2026-04-24c
# Uses official Playwright image - Chromium + all system deps pre-installed,
# avoiding apt package name differences across Debian/Ubuntu versions.
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Pre-create output dir so non-root users can write rendered images
RUN mkdir -p /app/_out

EXPOSE 8000

# start.py reads $PORT (Railway injects it) and starts uvicorn
CMD ["python", "start.py"]
