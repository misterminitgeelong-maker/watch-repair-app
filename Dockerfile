# ── Stage 1: Build the React frontend ──────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
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
ENV DATABASE_URL="sqlite:////app/data/watch_repair.db" \
    STATIC_DIR="/app/static" \
    APP_ENV="production" \
    JWT_SECRET="change-me-in-production" \
    ALLOW_DEV_AUTO_LOGIN="false" \
    CORS_ORIGINS="https://mainspring.au,https://www.mainspring.au" \
    PUBLIC_BASE_URL="https://mainspring.au"

EXPOSE 8000

CMD ["bash", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
