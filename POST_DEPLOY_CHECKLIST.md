# Post-Deploy Checklist

## 0) One-command guardrails (recommended)

- `cd backend`
- `python scripts/run_deploy_guardrails.py`
- If a step fails, resolve it and then continue with the detailed checklist below.

## 1) Run migrations

- `cd backend`
- `python -m alembic upgrade head`

## 2) Run auto-key duplicate audit

- Dry run:
  - `cd backend`
  - `python scripts/audit_autokey_numbers.py`
- If duplicates are reported, repair and re-check:
  - `python scripts/audit_autokey_numbers.py --fix`
  - `python scripts/audit_autokey_numbers.py`

## 3) Smoke checks

- `cd backend`
- `python scripts/run_smoke_checks.py`
- `cd ../frontend`
- `npm run build`

## 4) First 24h monitoring

- Watch API error rates for:
  - `POST /v1/auto-key-jobs/{id}/arrival-sms`
  - `POST /v1/auto-key-jobs/day-before-reminders`
  - `PATCH /v1/auto-key-jobs/invoices/{invoice_id}`
  - `POST /v1/auto-key-jobs/quick-intake`
- Watch logs for:
  - `auto_key_job.quick_intake_sms_failed`
  - `auto_key_invoice.auto_create_from_cost`
  - `auto_key_invoice.auto_create_from_quote`
- Verify public routes are live:
  - `/v1/public/auto-key-booking/{token}`
  - `/v1/public/auto-key-booking/{token}/confirm`
  - `/v1/public/auto-key-invoice/{token}`
- Verify Sentry alerts for critical workflow failures are arriving with `CRITICAL_WORKFLOW_FAILURE` in the message.

## 5) Manual flow checks

- Quick intake creates customer + auto-key job and sends intake SMS.
- Completing a job with no quote creates fallback invoice.
- Marking invoice as paid via job detail updates status/method.
- Platform Admin:
  - can enter a shop,
  - can return to admin,
  - activity tab shows recent cross-shop actions.
