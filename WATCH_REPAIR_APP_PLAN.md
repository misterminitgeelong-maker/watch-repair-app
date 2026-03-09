# Watch Repair SaaS Platform Plan (Solo + AI Builder Edition)

This plan is optimized for **one founder** building with AI copilots.

## 1) Goal
Build one product with:
- **Android app** for intake + bench technicians.
- **Web app** for shop operations and management.
- **SaaS backend** so many shops can subscribe.

## 2) Solo-Builder Principles
- Keep the stack minimal and boring.
- Ship one thin vertical slice at a time.
- Use AI for scaffolding/tests/docs, then verify manually.
- Avoid custom infra until revenue demands it.

## 3) Opinionated Stack (Recommended for Solo)

### Frontend
- **Flutter** for Android app.
- **Next.js (React + TypeScript)** for web dashboard.

### Backend
- **FastAPI (Python)** for API + business rules.
- **PostgreSQL** for data.
- **S3-compatible storage** for photos/files.
- **Redis** (optional later) for queues/caching.

### SaaS & Auth
- JWT auth with refresh tokens.
- Multi-tenant schema with `tenant_id` on all tenant-bound tables.
- Stripe Billing for subscriptions.

### Hosting (simple default)
- API: Railway/Render/Fly.io.
- DB: managed Postgres (Neon/Supabase/RDS).
- Web: Vercel.
- Object storage: Cloudflare R2 or S3.

## 4) MVP Scope (Do Only This First)

### A. Intake + Job Tracking
- ✅ Create customer + watch + repair job.
- Upload intake photos.
- Status flow:
  `Intake -> Diagnosis -> Awaiting Approval -> In Repair -> QC -> Ready -> Delivered`

### B. Quote + Approval
- ✅ Add estimate line items (labor + parts).
- ✅ Send approval link (email first; SMS later).
- ✅ Store approval audit (approved/declined, timestamp, IP).

### C. Work Logging
- ✅ Technician notes.
- ✅ Labor time entries.
- Parts used.

### D. Billing Lite
- ✅ Generate invoice from approved quote.
- ✅ Mark payment state: unpaid/paid/refunded (manual payment capture).

### E. SaaS Basics
- Tenant signup.
- Admin invites staff.
- Role permissions: owner, manager, tech, intake.

## 5) Data Model (MVP)
- `tenants`
- `users`
- `customers`
- `watches`
- `repair_jobs`
- `job_status_history`
- `quotes`
- `quote_line_items`
- `approvals`
- `work_logs`
- `parts`
- `invoices`
- `payments`
- `attachments`

Rule: every tenant-owned row must include `tenant_id` and tenant-filtered queries.


## Progress Tracker
- ✅ Auth + tenant bootstrap
- ✅ Customers + watches CRUD
- ✅ Repair jobs + status history
- ✅ Quote creation + public approval flow
- ✅ Invoice generation + manual payment capture
- ✅ Work logs + technician notes
- ✅ Attachments upload (signed URLs)
- ⬜ Stripe subscriptions + plan limits

## 6) 12-Week Solo Build Roadmap

### Weeks 1-2: Foundation
- Repo setup (monorepo optional).
- Auth + tenant model.
- Local/dev/prod environment templates.
- CI pipeline for lint + tests.

### Weeks 3-4: Core CRUD
- Customers, watches, repair jobs.
- Status history tracking.
- Basic web dashboard list/detail views.

### Weeks 5-6: Quote/Approval
- Quote line items.
- Public approval page (tokenized URL).
- Approval audit log.

### Weeks 7-8: Technician Workflow
- Notes, work logs, parts usage.
- Android job detail + status update UI.

### Weeks 9-10: Billing + Subscriptions
- Invoice generation + payment status.
- Stripe subscription plans/trials.
- Tenant plan enforcement (limits by tier).

### Weeks 11-12: Hardening + Pilot
- Permission checks, audit logs, backups.
- Bug bash + UX polish.
- Pilot with your own shop and one external shop.

## 7) “Build It with AI” Workflow

For each feature, run this loop:
1. Write a short feature spec (inputs, outputs, edge cases).
2. Ask AI to generate:
   - DB migration
   - API endpoint
   - frontend form/list
   - tests
3. Manually review for security and tenant isolation.
4. Run tests locally.
5. Deploy to staging.
6. Validate with real job scenarios.

## 8) Prompt Templates You Can Reuse

### A. Backend Prompt
"Implement FastAPI endpoint `<name>` with Pydantic schemas, SQLAlchemy models, tenant isolation by `tenant_id`, validation, and pytest tests. Return patch + migration + test data."

### B. Frontend Prompt
"Create Next.js page for `<feature>` with loading/error states, optimistic updates where safe, Zod validation, and unit tests. Use existing API client."

### C. QA Prompt
"Given this feature spec and code diff, produce a test checklist with critical paths, edge cases, and tenant-boundary abuse tests."

## 9) Security Checklist (Must-Have)
- Tenant isolation tests for every read/write endpoint.
- Server-side role checks (never UI-only).
- Signed URLs for attachments.
- Rate limiting on auth and approval endpoints.
- Audit log for quote approvals, status changes, invoice/payment edits.
- Encrypted secrets + routine key rotation.

## 10) Solo Operations Checklist
- Error tracking: Sentry.
- Uptime monitoring: Better Stack/UptimeRobot.
- Nightly DB backups + monthly restore drill.
- Feature flags for risky changes.
- Changelog + in-app release notes.

## 11) Monetization Plan (Start Simple)

### Plans
- **Starter**: small shop, user cap, core workflow.
- **Growth**: more users + reporting.
- **Pro**: multi-location + priority support.

### Pricing strategy
- Monthly + annual discount.
- 14-day trial.
- Optional SMS usage add-on.

### KPIs
- MRR
- Trial-to-paid conversion
- Churn
- Average jobs/shop/month
- Quote approval rate
- Avg turnaround time

## 12) What Not To Build Yet
- Native iOS app.
- Deep accounting integrations.
- Complex inventory forecasting.
- AI diagnostics suggestions.

Ship the MVP first; expand only after real usage proves demand.

---

If you want next, I can generate:
1. exact Postgres schema SQL,
2. OpenAPI spec for MVP endpoints,
3. first 20 GitHub issues in priority order,
4. copy-paste AI prompts for each issue.
