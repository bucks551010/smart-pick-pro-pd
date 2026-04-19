FROM python:3.12-slim
WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Install system dependencies required by curl_cffi, lxml, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    libcurl4-openssl-dev libssl-dev \
    libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the app user owns writable directories
RUN mkdir -p /app/db /app/logs /app/cache \
    && chown -R appuser:appuser /app/db /app/logs /app/cache

EXPOSE 8501 8000

# Health check: Streamlit exposes /_stcore/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"]

USER appuser
CMD ["python", "start.py"]
