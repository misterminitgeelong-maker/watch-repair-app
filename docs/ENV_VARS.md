# Environment Variables

Backend (FastAPI) reads from `.env` in the backend directory or from the process environment. Required in **production** are marked.

## Backend

| Variable | Default | Required (prod) | Description |
|----------|---------|------------------|-------------|
| `DATABASE_URL` | `sqlite:///./watch_repair.db` | Yes | PostgreSQL or SQLite URL. Use `postgresql+psycopg://...` for Postgres. |
| `JWT_SECRET` | `change-me-in-production` | **Yes** | Secret for signing JWTs. Must not be default in production. Generate with: `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | No | JWT algorithm. |
| `JWT_EXPIRE_MINUTES` | `480` | No | Access token lifetime (minutes). |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | No | Refresh token lifetime (days). |
| `APP_ENV` | `production` | No | Set to `test` for tests; `production` enables JWT secret check. |
| `ALLOW_PUBLIC_BOOTSTRAP` | `True` | No | If `True`, anyone can create a tenant via `/v1/auth/bootstrap`. Set to `false` after creating your first tenant. |
| `ALLOW_DEV_AUTO_LOGIN` | `False` | No | Enables `/v1/auth/dev-auto-login` when not in production. |
| `CORS_ORIGINS` | `https://mainspring.au,...` | Yes (if SPA on different origin) | Comma-separated allowed origins. |
| `PUBLIC_BASE_URL` | `https://mainspring.au` | No | Base URL for approval/status links in SMS. |
| `STATIC_DIR` | (empty) | For single-server deploy | Path to built frontend (e.g. `/app/static`). |
| `TWILIO_ACCOUNT_SID` | (empty) | No | Twilio SID for SMS. Leave blank for dry-run. |
| `TWILIO_AUTH_TOKEN` | (empty) | No | Twilio auth token. |
| `TWILIO_FROM_NUMBER` | (empty) | No | E.164 number for sending SMS. |
| `STRIPE_SECRET_KEY` | (empty) | No | Stripe API key for billing. |
| `STRIPE_WEBHOOK_SECRET` | (empty) | No | Stripe webhook signing secret. |
| `STRIPE_PRICE_*` | (empty) | No | Various Stripe price IDs for plans. |
| `PLATFORM_ADMIN_*` | (empty) | No | Optional platform admin account (email, password, etc.). |
| `TESTING_TENANT_SLUG` / `TESTING_OWNER_EMAIL` / `TESTING_OWNER_PASSWORD` | (empty) | No | Optional testing tenant for QA. When set, creates a separate tenant at startup; testing login has no demo prompts. |
| `STARTUP_SEED_*` | (varies) | No | One-time CSV seed and demo tenant settings. |
| `SENTRY_DSN` | (empty) | No | Sentry DSN for backend error reporting. Leave blank to disable. |
| `SENDGRID_API_KEY` / `POSTMARK_API_KEY` | (empty) | No | Optional email provider API key when `enable_email_notifications` is true. |
| `GOOGLE_PLACES_API_KEY` | (empty) | No | Google Places API key for Prospects search (/prospects). Leave blank to disable; endpoints return 500 if key is missing. |

## Health and readiness

- **GET /v1/health** — Returns `{"status": "ok", "startup_seed": ...}`. Use for liveness.
- **GET /v1/ready** — Runs a simple DB check. Returns 200 with `{"status": "healthy"}` or 503 if the database is unreachable. Use for readiness (e.g. Kubernetes).

## Frontend (build-time)

| Variable | Description |
|----------|-------------|
| `VITE_ENABLE_DEV_AUTO_LOGIN` | Set to `true` in dev to use dev-auto-login. |
| `VITE_DEMO_TENANT_SLUG` / `VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD` | Demo login button prefills (optional). |
| `VITE_SENTRY_DSN` | Sentry DSN for frontend error reporting (optional). Leave unset to disable. |
