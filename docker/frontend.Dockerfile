# ─────────────────────────────────────────────────────────────────────────────
# ChainWatch — Frontend Dockerfile
#
# Stage 1 (builder): installs npm deps and runs `vite build`
#   VITE_API_BASE is injected as a build arg so the compiled JS bundle
#   calls /api/v1 (same-origin through Nginx) rather than localhost:8000.
#
# Stage 2 (runtime): copies dist/ into nginx:alpine
#   Nginx configuration is provided separately via docker-compose volume mount.
#   This image is stateless — no runtime env needed.
#
# Works on: linux/amd64, linux/arm64
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: build ───────────────────────────────────────────────────────────
# Vite 8 requires Node >=22.12.0 or ^20.19.0.  Using node:22-alpine to satisfy
# the engine requirement without pinning a patch version of Node 20.
FROM node:22-alpine AS builder

WORKDIR /build

# Install dependencies first (cacheable layer)
COPY chainwatch_frontend/package.json chainwatch_frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --legacy-peer-deps

# Copy source
COPY chainwatch_frontend/ .

# VITE_API_BASE controls where the browser sends API calls.
# Default is /api/v1 (same-origin, proxied by Nginx).
# Override at build time with: --build-arg VITE_API_BASE=https://your-host/api/v1
ARG VITE_API_BASE=/api/v1
ARG VITE_API_KEY=chainwatch-local
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_API_KEY=${VITE_API_KEY}

RUN npm run build

# ── Stage 2: nginx runtime — serves static files AND acts as the reverse proxy ─
# The frontend image IS the nginx service.  It bundles both the SPA static files
# and the nginx.conf (reverse proxy config).  This removes the need for a
# separate nginx service or a shared volume to transfer dist/ files.
FROM nginx:1.27-alpine AS runtime

# curl for the HEALTHCHECK
RUN apk add --no-cache curl

# Remove the default server block
RUN rm /etc/nginx/conf.d/default.conf

# Copy built static assets into nginx's web root
COPY --from=builder /build/dist /usr/share/nginx/html

# Copy the reverse-proxy nginx config
# This config routes /api/* → backend:8000 and / → static files
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1
