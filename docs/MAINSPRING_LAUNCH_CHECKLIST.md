# Mainspring.au Launch Checklist

This is the go-live runbook for deploying Mainspring to Railway on mainspring.au.

## Pre-Flight

- Confirm these features are merged:
  - Public signup endpoint at /v1/auth/signup.
  - Import supports CSV, XLSX, and XLS.
  - Ticket-in workflow and mobile job cards are available.
  - Public status page at /status/{token}.
  - QR endpoint at /v1/public/jobs/{status_token}/qr.
- Confirm these migrations exist in backend/alembic/versions:
  - b7b5e6f3a9f2_add_import_log_tables.py
  - c31dd0be9d6f_add_pre_quote_to_repairjob.py
  - de9f6ccfac01_add_status_token_to_repairjob.py

## Railway Setup

- Use [docs/RAILWAY_VARIABLES_MAINSPRING.md](docs/RAILWAY_VARIABLES_MAINSPRING.md) as the source of truth when filling Railway Variables.

- Create a Railway project from the GitHub repo.
- Add PostgreSQL plugin.
- Set service variables:

```env
APP_ENV=production
ALLOW_DEV_AUTO_LOGIN=false
ALLOW_PUBLIC_BOOTSTRAP=true
JWT_SECRET=<generate-long-random-secret>
JWT_EXPIRE_MINUTES=480
CORS_ORIGINS=https://mainspring.au,https://www.mainspring.au
PUBLIC_BASE_URL=https://mainspring.au
STATIC_DIR=/app/static
STARTUP_SEED_ENABLED=false
TWILIO_ACCOUNT_SID=<twilio-sid>
TWILIO_AUTH_TOKEN=<twilio-token>
TWILIO_FROM_NUMBER=<twilio-number>
PLATFORM_ADMIN_ENABLED=true
PLATFORM_ADMIN_EMAIL=<sammeyerphotogaphy@gmail.com
PLATFORM_ADMIN_PASSWORD=<MisterMinitAdmin
PLATFORM_ADMIN_FULL_NAME=Platform Admin
PLATFORM_ADMIN_TENANT_SLUG=platform
PLATFORM_ADMIN_TENANT_NAME=Platform
```

- Ensure DATABASE_URL is present from the Railway PostgreSQL plugin.
- Deploy and verify the service starts cleanly.

## Domain and DNS

- Add custom domains in Railway:
  - mainspring.au
  - `www.mainspring.au` (optional)
- In your DNS provider, add records exactly as shown by Railway for domain verification.
- Wait for TLS to become active in Railway.

## First Production Boot

- Check health endpoint:
  - <https://mainspring.au/v1/health>
- Bootstrap owner if needed:

```bash
curl -X POST https://mainspring.au/v1/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Mainspring",
    "tenant_slug": "mainspring",
    "owner_email": "you@mainspring.au",
    "owner_full_name": "Owner",
    "owner_password": "change-this-password"
  }'
```

- After owner is created, set ALLOW_PUBLIC_BOOTSTRAP=false.
- Redeploy to lock bootstrap.
- Verify platform admin account can log in with tenant slug `platform`.

## Production Smoke Tests

- One-command option (PowerShell):

```powershell
./scripts/smoke-test-mainspring.ps1 -BaseUrl https://mainspring.au
```

- Full option including public status and QR checks:

```powershell
./scripts/smoke-test-mainspring.ps1 -BaseUrl https://mainspring.au -StatusToken <status_token>
```

- Health and app shell:

```bash
curl https://mainspring.au/v1/health
curl -I https://mainspring.au/
```

- Signup endpoint:

```bash
curl -X POST https://mainspring.au/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Pilot Shop",
    "tenant_slug": "pilotshop",
    "email": "owner@pilotshop.au",
    "full_name": "Pilot Owner",
    "password": "pilotpass123"
  }'
```

- Login endpoint:

```bash
curl -X POST https://mainspring.au/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "pilotshop",
    "email": "owner@pilotshop.au",
    "password": "pilotpass123"
  }'
```

- Platform admin global users endpoint:

```bash
curl -X GET https://mainspring.au/v1/platform-admin/users \
  -H "Authorization: Bearer <platform_admin_token>"
```

- Public status page with real token:
  - <https://mainspring.au/status/{status_token}>
- QR endpoint with real token:
  - <https://mainspring.au/v1/public/jobs/{status_token}/qr>
- Import verification from UI:
  - Upload one CSV.
  - Upload one XLSX.
  - Confirm import_id and counts are shown.

## Twilio Validation

- Create a test job with a real customer phone.
- Trigger quote send and status updates.
- Verify SMS includes:
  - Quote link (/approve/{token}) when applicable.
  - Live status link (/status/{status_token}).
- Confirm records are stored in smslog table.

## Security and Operations

- Keep these production values:
  - APP_ENV=production
  - ALLOW_DEV_AUTO_LOGIN=false
  - ALLOW_PUBLIC_BOOTSTRAP=false after first tenant
  - PLATFORM_ADMIN_ENABLED=true only when admin email/password are set
- Enable Railway PostgreSQL backups/snapshots.
- Monitor:
  - GET /v1/health
  - 5xx rate and latency

## Rollback Plan

- If deploy fails, roll back to previous Railway deployment.
- If migration fails, restore latest DB snapshot and redeploy previous image.
- If DNS or TLS fails, use the Railway default domain temporarily.

## First-Week Daily Checks

- Verify signup and login success rate.
- Verify imports persist correctly.
- Verify team is using ticket-in workflow.
- Verify status links and QR scans work on mobile.
- Verify quote and status SMS delivery health.
