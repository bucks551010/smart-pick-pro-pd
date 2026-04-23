# ── Multi-stage Dockerfile: Streamlit UI + Headless Chromium ──
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# System deps required by headless Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxrandr2 libxshmfence1 libxss1 \
    libxtst6 xdg-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8501 8000

# START_MODE selects which process this container runs.
#   ui     → Streamlit control room (default)
#   worker → FastAPI webhook + APScheduler jobs
ENV START_MODE=ui
CMD ["sh", "-c", "if [ \"$START_MODE\" = \"worker\" ]; then \
        uvicorn webhook.api:app --host 0.0.0.0 --port 8000; \
     else \
        streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true; \
     fi"]
