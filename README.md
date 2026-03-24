# Watch Repair App

Multi-tenant FastAPI + SQLModel backend for running watch repair operations, including customers, watches, repair jobs, quotes, invoicing, attachments, and data import.

## Current Backend Capabilities

- Tenant bootstrap and tenant-scoped authentication (JWT access + refresh).
- Tenant-isolated CRUD flows for customers, watches, repair jobs, quotes, invoices, payments, and attachments.
- Concurrency-safe per-tenant numbering for repair jobs (`JOB-xxxxx`) and invoices (`INV-xxxxx`) with DB uniqueness constraints.
- Public quote approval flow with token lifecycle controls (expiry handling, invalid/expired protection, already-decided protection).
- Attachment uploads to local storage with validation (MIME allowlist + max size), signed download links, and tenant-safe access checks.
- CSV/XLS/XLSX import endpoint with dry-run mode, skipped-row reasons, and duplicate-like customer row visibility.
- Pagination/filter/sort support on core list endpoints:
  - `/v1/repair-jobs`
  - `/v1/quotes`
  - `/v1/customers`
  - `/v1/watches`
  - `/v1/attachments`
- Rate limiting for high-risk endpoints (`/v1/auth/login`, public quote endpoints, `/v1/import/csv`).

## Local Setup

### Prerequisites

- Python 3.11+ (3.12 recommended)
- `pip`

### Start local backend

```bash
cd backend
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Open API docs at `http://127.0.0.1:8000/docs`.

## Database Migrations

Alembic is the schema source of truth. Runtime schema creation is not the normal path.

### Apply latest migrations

```bash
cd backend
alembic upgrade head
```

### Create a migration

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Legacy local DB created outside Alembic

If your local SQLite DB was created historically via `create_all()`, choose one:

- **Wipe and recreate (recommended)** when local data can be dropped:

```bash
cd backend
# Windows (PowerShell)
Remove-Item .\watch_repair.db -ErrorAction SilentlyContinue
# macOS/Linux
# rm -f watch_repair.db
alembic upgrade head
```

- **Stamp then upgrade** only if schema already matches:

```bash
cd backend
alembic stamp head
alembic upgrade head
```

### Dev-only bootstrap helper

For local experimentation only:

```env
AUTO_CREATE_SCHEMA_ON_STARTUP=true
```

Do not use this in production/shared environments.

## Environment and Config Basics

Primary settings live in `backend/app/config.py`, loaded from `.env` and `backend/.env`.

Important examples:

```env
# Environment mode
APP_ENV=development

# Database and auth
DATABASE_URL=sqlite:///./watch_repair.db
JWT_SECRET=change-me-in-production

# Public URL + CORS
PUBLIC_BASE_URL=https://mainspring.au
CORS_ORIGINS=https://mainspring.au,https://www.mainspring.au

# Quote approval token lifecycle
QUOTE_APPROVAL_TOKEN_TTL_HOURS=168

# Attachment safety
ATTACHMENT_ALLOWED_CONTENT_TYPES=image/jpeg,image/png,image/webp,application/pdf,text/plain
ATTACHMENT_MAX_UPLOAD_BYTES=10485760
ATTACHMENT_LOCAL_UPLOAD_DIR=uploads

# Sensitive endpoint rate limits
RATE_LIMIT_AUTH_LOGIN=20/minute
RATE_LIMIT_PUBLIC_QUOTE_GET=30/minute
RATE_LIMIT_PUBLIC_QUOTE_DECISION=20/minute
RATE_LIMIT_IMPORT_CSV=5/minute
```

## Running Tests

```bash
cd backend
python -m pytest
```

Run a focused file:

```bash
cd backend
python -m pytest tests/test_quote_token_lifecycle.py
```

## Operational Notes

- **Production config safety checks:** startup fails in production if unsafe values are detected (default JWT secret, wildcard CORS, localhost public URL, unintended SQLite usage).
- **Tenant isolation:** all core routes scope reads/writes by tenant context.
- **Limiter storage:** current `slowapi` store is in-process; use Redis-backed storage when running multiple API instances.
- **Attachment storage today:** local filesystem abstraction; service contract is ready for future S3/R2 implementation.
