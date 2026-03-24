# Production Readiness Checklist

Practical pre-release checklist for this repository's current backend implementation.

Use this in two passes:

- **Pass 1:** Must-have before pilot rollout.
- **Pass 2:** Should-have before broader production scale.

---

## Must-Have Before Pilot

### Database and Migrations

- [ ] `alembic upgrade head` runs cleanly in target environment.
- [ ] No runtime schema bootstrap is enabled in production (`AUTO_CREATE_SCHEMA_ON_STARTUP=false`).
- [ ] Startup succeeds against migrated schema without manual table creation.
- [ ] Legacy DB handling plan is chosen (wipe/rebuild vs stamp) before go-live.
- [ ] Verify uniqueness constraints critical to operations are active:
  - [ ] `(tenant_id, job_number)` on repair jobs
  - [ ] `(tenant_id, invoice_number)` on invoices
  - [ ] `(tenant_id, email)` on users

### Config and Environment Validation

- [ ] `APP_ENV=production` is set for production deployments.
- [ ] `JWT_SECRET` is strong and not default.
- [ ] `CORS_ORIGINS` contains explicit origins (no `*`).
- [ ] `PUBLIC_BASE_URL` is real public URL (not localhost).
- [ ] Production DB uses server database (or `ALLOW_SQLITE_IN_PRODUCTION=true` is intentionally approved).
- [ ] `ALLOW_PUBLIC_BOOTSTRAP` is disabled after first tenant bootstrap.

### Auth and Security

- [ ] Access/refresh token flow works with explicit JWT claims (`tenant_id`, `user_id`, `role`).
- [ ] Cross-tenant access attempts are rejected in core endpoints.
- [ ] Role-protected actions (e.g. job status updates) behave as expected.

### Rate Limiting

- [ ] Confirm rate limits are configured for:
  - [ ] `POST /v1/auth/login`
  - [ ] `GET /v1/public/quotes/{token}`
  - [ ] `POST /v1/public/quotes/{token}/decision`
  - [ ] `POST /v1/import/csv`
- [ ] Validate `429` behavior with simple load test/script in staging.
- [ ] Confirm test env override values do not leak into production env vars.

### Tenant Isolation Checks

- [ ] Verify tenant isolation on list/read endpoints:
  - [ ] `/v1/repair-jobs`
  - [ ] `/v1/quotes`
  - [ ] `/v1/customers`
  - [ ] `/v1/watches`
  - [ ] `/v1/attachments`
- [ ] Verify tenant isolation on attachment download and signed-link access.

### Quote Approval Token Lifecycle

- [ ] `send quote` sets token expiry (`approval_token_expires_at`).
- [ ] Invalid token returns expected error.
- [ ] Expired token returns expected error and cannot be decided.
- [ ] Already-decided quote cannot be re-decided.

### Attachment Storage Safety

- [ ] Attachment MIME allowlist is configured for expected file types.
- [ ] `ATTACHMENT_MAX_UPLOAD_BYTES` is set to approved size limit.
- [ ] Upload path root (`ATTACHMENT_LOCAL_UPLOAD_DIR`) is set to durable storage location.
- [ ] Upload/download flows work for same-tenant user.
- [ ] Cross-tenant download attempt fails.

### CSV Import Safety

- [ ] Dry-run path is exercised (`dry_run=true`) and confirms no writes.
- [ ] Normal import path is exercised and writes expected rows.
- [ ] Import summary is reviewed for:
  - [ ] skipped row reasons
  - [ ] duplicate-like customer row count in file
- [ ] Pilot operators are trained to run dry-run before first large import.

### SMS / Twilio Behavior

- [ ] Twilio credentials configured correctly (or intentionally blank for dry-run/log-only behavior).
- [ ] Quote/status SMS flows validated with real test numbers.
- [ ] `smslog` entries show expected success/failure state.
- [ ] Fallback behavior is understood if Twilio is unavailable.

### Backups and Restore Testing

- [ ] Automated DB backup schedule is enabled in host platform.
- [ ] At least one restore test has been performed to non-production environment.
- [ ] Restore runbook exists with owner and expected RTO/RPO.

### Logging and Monitoring

- [ ] Health endpoint (`/v1/health`) is monitored.
- [ ] Error rate and latency monitoring are configured.
- [ ] Request logs include enough context for incident triage (tenant/request correlation where available).

### Deployment Validation

- [ ] Deployment uses correct env vars for target environment.
- [ ] Post-deploy smoke checks pass:
  - [ ] auth login
  - [ ] create/list customers and watches
  - [ ] create/send quote + public fetch/decision
  - [ ] create invoice + payment
  - [ ] attachment upload/download
  - [ ] CSV dry-run and normal import

### Testing and Regression

- [ ] Backend test suite passes in CI for release candidate.
- [ ] Recent hardening tests pass (quote token lifecycle, attachment hardening, CSV safety, rate limiting, list endpoint pagination/filter/sort).

---

## Should-Have Before Broader Production Scale

### Rate Limiter and Multi-Instance Behavior

- [ ] Move from in-memory limiter storage to shared backend (e.g. Redis) before horizontal scaling.
- [ ] Revalidate limit behavior under multi-instance load.

### Attachment Storage Evolution

- [ ] Plan migration from local filesystem storage to object storage implementation using existing storage abstraction contract.
- [ ] Define retention and cleanup policy for orphaned attachment files.

### Operational Maturity

- [ ] Alerting thresholds are tuned from pilot traffic patterns.
- [ ] Incident response runbook is documented (auth outage, DB issues, Twilio outage, import failures).
- [ ] Disaster recovery drill repeated after major schema changes.

### Data Operations

- [ ] Formal import SOP established (dry-run first, then production import).
- [ ] Duplicate-resolution process documented for importer edge cases.
- [ ] Large import performance expectations documented (row volume, expected runtime).

### Security Hardening Follow-Through

- [ ] Secret rotation cadence documented (`JWT_SECRET`, provider credentials).
- [ ] Access policy review completed for operator/admin accounts.
- [ ] Production readiness review repeated on each major release.

---

## Current Known Caveats

- Rate limiter storage is currently process-local by default; this is acceptable for single-instance/pilot but not sufficient for scaled multi-instance deployments.
- Attachment storage currently uses local filesystem implementation; design is ready for object storage, but migration/ops runbook must be completed before larger scale.
- CSV import is synchronous; very large files may require operator controls and off-peak execution until a background processing model is introduced.
