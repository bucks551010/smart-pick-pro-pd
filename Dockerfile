# ================================================================
# Smart Pick Pro — Production Dockerfile (multi-stage)
#
# Stage 1 (builder): compiles native extensions (lxml, curl_cffi,
#   catboost, psycopg2-binary) and installs all Python wheels into
#   a separate prefix so the final image stays slim.
# Stage 2 (runtime): Python slim + runtime .so libs only; no
#   compilers, no header files, no build cache in the final layer.
#
# Build:
#   docker build --target runtime -t smart-pick-pro:latest .
# ================================================================

# ── Stage 1: dependency builder ──────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time system libraries (compilers + dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ make \
        libcurl4-openssl-dev libssl-dev \
        libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install wheels into /install prefix so they can
# be copied cleanly into the runtime stage.
COPY requirements.txt .
RUN pip install --upgrade pip==24.3.1 \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only shared libraries (no compilers or -dev packages)
# libgomp1    — required by catboost / xgboost
# libcurl4    — required by curl_cffi
# libxml2 / libxslt1.1 — required by lxml at import time
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libcurl4 \
        libxml2 libxslt1.1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages from the builder stage
COPY --from=builder /install /usr/local

# Non-root user (UID/GID 1000 — aligns with Azure Container Apps defaults)
RUN groupadd --gid 1000 appuser \
 && useradd  --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy application source; exclude heavy local artifacts
COPY --chown=appuser:appuser . .

# Writable runtime directories — mounted as Azure volumes in production
RUN mkdir -p /app/db /app/logs /app/cache /data /app/_out \
 && chown -R appuser:appuser /app/db /app/logs /app/cache /data /app/_out

# ── Build metadata (available at runtime via os.environ) ─────
ARG BUILD_DATE="unknown"
ARG GIT_SHA="unknown"
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.title="smart-pick-pro"

# ── Runtime environment ───────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DB_DIR=/data \
    PORT=8501

EXPOSE 8501 8000

# Streamlit's built-in liveness probe is /_stcore/health.
# The FastAPI side exposes /healthz (lightweight, no DB I/O).
# Both are checked here so a container with a broken API is
# also replaced by the load balancer.
HEALTHCHECK --interval=30s --timeout=8s --start-period=45s --retries=3 \
    CMD curl -sf http://localhost:8501/_stcore/health \
     && curl -sf http://localhost:8000/healthz \
     || exit 1

USER appuser
CMD ["python", "start.py"]
