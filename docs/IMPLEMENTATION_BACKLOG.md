# Watch Repair SaaS MVP - Prioritized Backlog (Solo Builder)

Use this list as your execution queue. Each item includes a copy/paste AI prompt.

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
