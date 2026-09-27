# ─────────────────────────────────────────────────────────────────────────────
# ChainWatch — Backend Dockerfile
#
# Image: python:3.12-slim (Debian Bookworm base)
# Extras: weasyprint system dependencies (Pango, Cairo, GLib, fontconfig)
#         maxminddb, scikit-learn, shap, networkx — all from requirements.txt
#
# Multi-stage: build (installs deps) → runtime (lean final image)
# Works on: linux/amd64, linux/arm64 (Apple Silicon, AWS Graviton)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependency install ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

# System packages needed at build time:
#   build-essential  — compiles any C extensions (e.g. numpy, shap)
#   libpango-1.0-0 + friends — required by weasyprint at import time
#   libcairo2        — weasyprint PDF rendering
#   libgdk-pixbuf-2.0-0 — weasyprint image support
#   libffi-dev       — cffi (weasyprint dep)
#   curl             — healthcheck in the runtime stage
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        fonts-liberation \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first — lets Docker cache this layer when code changes
COPY chainwatch_backend/requirements.txt .

RUN pip install --upgrade pip --no-cache-dir \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime-only system libs (no build tools — keeps image lean)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        libxml2 \
        fonts-liberation \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# Copy application source
COPY chainwatch_backend/ .

# GeoIP databases are NOT baked in — they are mounted at runtime via volumes.
# The backend falls back to CSV-based IP lookup if MMDB files are absent.
# To enable MaxMind MMDB: place files in ./database/ and they will be found
# via ALT_CITY_DB_PATH = /app/database/GeoIP-City.mmdb
#                        /app/database/GeoIP-ASN.mmdb

# Create the database directory so the mount point always exists
RUN mkdir -p /app/database

# Non-root user for security
RUN useradd -r -u 1001 -m chainwatch \
 && chown -R chainwatch:chainwatch /app
USER chainwatch

EXPOSE 8000

# Healthcheck via the /api/v1/health/ready endpoint
# Allows 60s for Neo4j to come up before the container is marked unhealthy
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/api/v1/health/ready || exit 1

# Production startup — no --reload, binds to all interfaces inside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
