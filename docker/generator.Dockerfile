# ─────────────────────────────────────────────────────────────────────────────
# ChainWatch — Streamlit Generator Dockerfile  (optional, profile: tools)
#
# Runs the synthetic dataset generator on port 8501.
# Activated with: docker compose --profile tools up -d
#
# Shares the same Python base and system libs as the backend image.
# Works on: linux/amd64, linux/arm64
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        libxml2-dev \
        fonts-liberation \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY chainwatch_backend/requirements.txt .
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir streamlit==1.40.2

COPY chainwatch_backend/ .

# Generated CSVs are written to /app/exports/ which is mounted as a volume
# so the host can pick them up for upload to the ingest endpoint.
RUN mkdir -p /app/exports

# Non-root user
RUN useradd -r -u 1001 -m chainwatch \
 && chown -R chainwatch:chainwatch /app
USER chainwatch

EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# headless=true disables browser auto-open; address=0.0.0.0 binds for Docker
CMD ["streamlit", "run", "generator_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
