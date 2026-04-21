# ── Stage 1: Build the React frontend ──────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
# Vite env vars must be passed as build args (Railway injects service vars)
ARG VITE_GOOGLE_MAPS_API_KEY
ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY
# Optional: set for Capacitor / native builds (e.g. https://mainspring.au). Omit for same-origin web bundle in Docker.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + built frontend ──────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./

# Copy the built frontend into /app/static
COPY --from=frontend-build /app/frontend/dist /app/static

# Persistent volume mount points
RUN mkdir -p /app/uploads /app/data

# Environment defaults (override at deploy time)
#
# IMPORTANT: JWT_SECRET is intentionally NOT set here. Baking a default
# secret into the image (even a placeholder) is a footgun — any non-production
# environment that skips the runtime validator would silently run on it.
# Deploys MUST inject JWT_SECRET via the platform's secret manager
# (Railway service variables, GitHub Actions secrets, etc.). The runtime
# validator in app/config.py fails fast in production if JWT_SECRET is
# unset or still the placeholder.
ENV DATABASE_URL="sqlite:////app/data/watch_repair.db" \
    STATIC_DIR="/app/static" \
    APP_ENV="production" \
    ALLOW_DEV_AUTO_LOGIN="false" \
    CORS_ORIGINS="https://mainspring.au,https://www.mainspring.au" \
    PUBLIC_BASE_URL="https://mainspring.au"

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
