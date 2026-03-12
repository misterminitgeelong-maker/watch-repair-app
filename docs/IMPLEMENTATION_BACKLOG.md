# Watch Repair SaaS MVP - Prioritized Backlog (Solo Builder)

Use this list as your execution queue. Each item includes a copy/paste AI prompt.

## Active Worthwhile Jobs Queue (Current Sprint)

- [x] Auto Key deep-link detail route (`/auto-key/:id`) and invoice-line navigation to exact job.
- [x] B2B statements include only completed/collection-ready jobs.
- [x] B2B statements exclude already invoiced job lines (`uninvoiced` behavior).
- [x] Add CSV export for Customer Account monthly statements/invoices.
- [x] Add Parent Account + multi-site login foundations (schema + auth context + site switcher).
- [x] Add guided onboarding v2 checklist (first job, first quote, first invoice).
- [x] Add frontend active-site switcher UI for multi-site users.
- [x] Add multi-site login entrypoint on login page (email/password path).
- [x] Add Parent Account admin API + UI to list linked sites and link existing tenants.
- [x] Add Parent Account UI action to switch directly into a linked site context.
- [x] Add Parent Account unlink/remove site action with safety checks.
- [x] Add Parent Account create-new-site flow (create tenant + auto-link + UI form).
- [x] Add Parent Account event-log table and write activity on link/unlink/create-site/switch-site.
- [x] Add Parent Account activity API endpoint (`/v1/parent-accounts/me/activity`).
- [x] Add Parent Account UI activity feed panel.
- [x] Add Parent Account UI activity feed panel.
- [x] Plan limit enforcement per plan code (watch/shoe/auto_key: 2000 jobs, 5 users; enterprise: unlimited). Returns HTTP 402 on breach.
- [x] Simple analytics panel — monthly trends (6-month job opens + revenue bars) and Audit Log feed in ReportsPage.
- [x] Tenant audit log (TenantEventLog table) — records login, user_created, invoice_created, plan_changed events.
- [x] Rate limiting — slowapi middleware on /auth/login and /auth/multi-site-login (20/minute per IP).
- [x] Stripe billing integration — /v1/billing/limits, /v1/billing/checkout, /v1/billing/portal-url, /v1/billing/webhook; BillingCard usage meters in AccountsPage.

## P0 (Build these first)

1. **Auth + tenant bootstrap**
   - Output: login, refresh, tenant creation, owner user creation.
   - Prompt: "Implement FastAPI auth with JWT access+refresh tokens and tenant bootstrap endpoint. Include SQLAlchemy models, alembic migration, and pytest coverage for login failures and token refresh."

2. **Customers + watches CRUD**
   - Output: create/list/update endpoints with tenant isolation.
   - Prompt: "Add FastAPI CRUD for customers and watches with strict tenant_id filtering in every query and test cross-tenant denial."

3. **Repair jobs CRUD + status history**
   - Output: job creation, assignment, status transitions, timeline.
   - Prompt: "Implement repair job endpoints and append-only job_status_history entries for every status change, with role checks and tests."

4. **Web dashboard list/detail pages**
   - Output: Next.js pages for jobs, filters, and detail timeline.
   - Prompt: "Build Next.js TypeScript pages for repair job list and detail with loading/error states, status badge UI, and API integration tests."

5. **Quote builder + totals**
   - Output: quote line item editor and server-side totals.
   - Prompt: "Add quote creation endpoint with line items and server-side subtotal/tax/total calculations; include tests for rounding and invalid inputs."

6. **Public approval flow**
   - Output: tokenized approve/decline endpoint + audit metadata.
   - Prompt: "Create public quote decision endpoint using secure token, storing decision, decided_at, IP, and user-agent; include replay/expired token tests."

## P1 (Immediately after P0)

7. **Work logs + technician notes**
8. **Attachment upload with signed URLs**
9. **Invoice generation from approved quote**
10. **Manual payment capture + status updates**
11. **Stripe subscription plans + webhook handling**
12. **Plan limit enforcement (users/jobs per plan)**

## P2 (Pilot hardening)

13. **Audit log viewer (owner/manager only)**
14. **Sentry error tracking integration**
15. **Nightly backup verification script**
16. **Rate limiting on auth/public endpoints**
17. **Simple analytics panel (jobs opened/closed, approval rate)**
18. **In-app changelog + feedback capture**

## Definition of Done (per backlog item)
- Endpoint/UI implemented.
- Unit/integration tests added.
- Tenant-boundary tests pass.
- Feature documented in CHANGELOG.
- Deployed to staging and manually validated with a sample repair flow.

## 2026-03 Expansion Requests (Bundling + New Verticals)

1. Product bundles and feature gating
- Add `plan_code` to tenant billing profile with: `shoe`, `watch`, `auto_key`, `enterprise`.
- Add backend authorization helper `require_feature(feature_key)` and gate APIs by feature.
- Gate sidebar navigation by enabled modules.
- Add plan matrix UI in Accounts/Billing page.

2. Auto key workflow
- Create `auto_key_jobs` module mirroring repair job lifecycle.
- Required fields: vehicle details, key type, programming status, completion status.
- Add quote/invoice pipeline with optional automatic invoice creation on status `completed`.
- Add new `Auto Key` tab and detail page.

3. B2B customer account tab
- Add `customer_accounts` and `customer_account_members` for business clients.
- Link jobs to account-level billing entity.
- Monthly statement endpoint: aggregates uninvoiced completed jobs by account and period.
- Add "Generate month-end invoice" action per business account.

4. Parent account with multi-site login
- Add `parent_accounts` table and link multiple tenants/sites to one parent entity.
- Permit one email/password identity with scoped site membership.
- Add site switcher after login for users attached to multiple sites.
- Enforce tenant isolation using active site context in token/session.

5. Demo account and onboarding
- Keep public demo entry (`/login?demo=1`) with seeded tenant defaults.
- Maintain one-time tutorial modal and extend to guided, step-by-step tours per page.

## Execution Plan (Ship One-by-One)

### Phase 0 - Already shipped
- Shoe quote context carry-over (type, brand, colour shown in service picker).
- Shoe intake pair limit increased to 15.
- Demo login links and login-page demo autofill.
- First-run quick tour modal.
- Auto Key + Customer Accounts tabs scaffolded.

### Phase 1 - Foundation (do first)
1. Add plan codes and feature gating at backend level (`shoe`, `watch`, `auto_key`, `enterprise`).
2. Hide/show frontend nav modules based on enabled features.
3. Add billing/settings UI to assign and display active plan.

### Phase 2 - Auto Key vertical
1. Create `auto_key_jobs` schema + migration.
2. Build API routes for create/list/update/status workflow.
3. Add quote and invoice integration.
4. Add optional auto-invoice on completion.

### Phase 3 - B2B Customer Accounts
1. Create `customer_accounts` and account membership schema.
2. Link repair jobs to account billing entity.
3. Build month-end statement aggregation endpoint.
4. Add "Generate monthly invoice" action and print/export view.

### Phase 4 - Parent accounts / multi-site login
1. Add `parent_accounts` and site membership schema.
2. Support one email/password mapped to multiple shop/site IDs.
3. Add post-login site picker and active-site switcher.
4. Enforce active site tenant context across all APIs.

### Phase 5 - Guided onboarding v2
1. Upgrade quick tour into step-by-step walkthrough per page.
2. Add checklist progress (complete first job, first quote, first invoice).
3. Add dismiss/reset controls in account settings.

## Delivery Rule (for each phase)
- Design + migration first.
- API endpoints second.
- Frontend screens third.
- Tests and smoke run before merging.
- Release notes + docs update.
