# Code Review Recommendations — Mainspring Watch Repair SaaS

This document summarizes recommendations to improve the app’s maintainability, security, reliability, and developer experience. Items are grouped by area and ordered by impact.

**Implementation status (2026-03):** The following have been implemented: Alembic migration for legacy columns and removal of runtime patch; tenant-scoped get helpers; JWT refresh tokens and frontend 401 retry + proactive refresh; single source of truth for job status labels; production config hardening (JWT secret, bootstrap warning); rate limiting on public/signup; React Error Boundary; CI (GitHub Actions); broader tenant-isolation tests (quotes, invoices); ENV_VARS.md, /v1/ready, request logging; AuthContext comment and frontend unit tests (getApiErrorMessage). The “split models.py” item was skipped to avoid a large refactor.

---

## 1. Backend — Database & Schema

### 1.1 Replace runtime column patching with migrations (High)

**Current:** `database.py` uses `_ensure_runtime_columns()` to ALTER tables at startup when columns are missing (e.g. `repairjob.assigned_user_id`, `customer.address`).

**Issue:** Mixing migration history with runtime schema patching makes deployments and rollbacks unclear and can hide missing migrations.

**Recommendation:**

- Add an Alembic migration that adds any columns still managed by `_ensure_runtime_columns()` (and backfill/defaults if needed).
- Remove `_ensure_runtime_columns()` and its call from `create_db_and_tables()`.
- Use Alembic for all future schema changes so there is a single source of truth.

### 1.2 Consider splitting `models.py` (Medium)

**Current:** `models.py` is very large (1,400+ lines) with table models, Pydantic request/response schemas, and shared types.

**Recommendation:**

- Split into modules, e.g.:
  - `models/base.py` or `models/__init__.py` — shared types (`JobStatus`, `PlanCode`, etc.)
  - `models/tables.py` — SQLModel table definitions
  - `models/schemas.py` or per-domain files — request/response Pydantic models
- Re-export from `models/__init__.py` so existing `from ..models import X` imports keep working.
- Improves navigation and keeps table vs schema changes easier to reason about.

---

## 2. Backend — Security & Auth

### 2.1 Add JWT refresh tokens (High)

**Current:** Only access tokens are issued (8-hour expiry). The frontend calls `/auth/session` to refresh user/plan state but does not renew the JWT. When the token expires, the user is logged out.

**Recommendation:**

- Introduce refresh tokens (e.g. stored in DB or signed/rotating) with longer expiry (e.g. 7 days).
- Add an endpoint such as `POST /v1/auth/refresh` that accepts a valid refresh token and returns a new access token (and optionally refresh token).
- Frontend: before access token expiry (or on 401), call refresh; on success retry the request; on failure redirect to login.
- Optionally use `expires_in_seconds` from the login response to schedule a proactive refresh (e.g. refresh 5 minutes before expiry).

### 2.2 Harden default config for production (Medium)

**Current:** `config.py` uses defaults like `jwt_secret="change-me-in-production"` and `allow_public_bootstrap: bool = True`.

**Recommendation:**

- In production (`app_env=production`), require `JWT_SECRET` to be set and different from the default (fail startup or refuse auth if not).
- Consider defaulting `allow_public_bootstrap` to `False` when `app_env=production`, or document that it must be explicitly disabled after initial setup.
- Ensures production is not accidentally run with dev defaults.

### 2.3 Rate limiting beyond auth (Low)

**Current:** Rate limiting is applied to `/auth/login` and `/auth/multi-site-login` (20/minute). Other sensitive endpoints (e.g. public approval, signup, password reset if added) are not limited.

**Recommendation:**

- Apply rate limits to:
  - Public approval endpoint (e.g. `/approve/:token`)
  - Signup / checkout endpoints
- Use the existing `slowapi` limiter and same pattern as auth routes.

---

## 3. Backend — Consistency & Quality

### 3.1 Centralize tenant-scoped lookups (Medium)

**Current:** Routes repeatedly do “get by ID then check `resource.tenant_id == auth.tenant_id`” and raise 404 if missing or wrong tenant.

**Recommendation:**

- Add small helpers, e.g. `get_tenant_repair_job(session, job_id, tenant_id) -> RepairJob | None`, used by repair_jobs, work_logs, quotes, etc.
- Reduces duplication and ensures consistent 404 behavior and tenant isolation in one place.
- Apply the same pattern for other key entities (Customer, Watch, Invoice, etc.) where multiple routes need the same check.

### 3.2 Validate UUID path params in one place (Low)

**Current:** Route handlers take `job_id: UUID` etc.; FastAPI already validates UUIDs. No change required for correctness.

**Recommendation:** Optional: add a small dependency or shared doc that “all tenant-scoped resource IDs are UUID path params validated by FastAPI,” so new routes stay consistent.

### 3.3 Add structured request logging (Low)

**Current:** No request/response or error logging visible in the reviewed code.

**Recommendation:**

- Add middleware or a logging dependency that logs method, path, status, tenant_id (if authenticated), and duration. Omit sensitive headers/body.
- Eases debugging and supports audit requirements (e.g. from your security checklist).
- In production, consider also sending errors to Sentry (already in your backlog).

---

## 4. Frontend — Architecture & DX

### 4.1 Single source of truth for job status labels (High)

**Current:** Job status labels (and sometimes colors) are duplicated in:

- `frontend/src/lib/utils.ts` — `STATUS_LABELS`, `STATUS_COLORS`
- `JobsPage.tsx` — `STATUS_OPTION_LABELS`, `JOB_STATUSES`, etc.
- `JobDetailPage.tsx`, `ShoeRepairsPage.tsx`, `ShoeJobDetailPage.tsx`, `NewJobModal.tsx`, `NewShoeJobModal.tsx`, `AutoKeyJobsPage.tsx` — local status arrays/labels

**Recommendation:**

- Use the existing `STATUS_LABELS` and `STATUS_COLORS` from `utils.ts` everywhere.
- Export a single ordered list of job statuses (e.g. `JOB_STATUS_ORDER` or per-type if watch/shoe/auto-key differ) and status options from `utils.ts` or a small `constants/status.ts` module.
- Remove duplicate definitions from page/components and import from the shared module. This avoids drift when you add or rename statuses.

### 4.2 Add a React Error Boundary (Medium)

**Current:** No `ErrorBoundary` or `componentDidCatch` usage was found. Uncaught render errors can blank the whole app.

**Recommendation:**

- Add an error boundary component that catches render errors, shows a friendly message and a “Reload” or “Go to dashboard” action, and optionally reports to Sentry.
- Wrap the main app or the `AppShell` outlet so that most of the app is protected. Optionally add boundaries around heavy sections (e.g. reports, stocktakes).

### 4.3 Proactive token refresh (Medium)

**Current:** The frontend stores the JWT and calls `getAuthSession()` on load and after login/site switch. It does not refresh the token before it expires; users hit 401 when the 8-hour window ends.

**Recommendation:**

- When you add refresh tokens (see 2.1), implement proactive refresh:
  - After login/session fetch, schedule a refresh (e.g. `setTimeout` or `setInterval`) based on `expires_in_seconds` (e.g. refresh at 90% of that).
  - Alternatively, use an axios response interceptor: on 401, try refresh once, then retry the request; if refresh fails, clear token and redirect to login.
- Improves UX and aligns with the “refresh token” recommendation.

### 4.4 AuthContext: avoid parsing JWT in the client (Low)

**Current:** `parseRoleFromToken` in `AuthContext.tsx` decodes the JWT payload client-side to read role from the `sub` claim.

**Issue:** JWTs are not encrypted; parsing is fine for UX (e.g. showing role before `/auth/session` returns), but the role is already returned by `/auth/session`. Relying on client-parsed role for anything security-sensitive would be wrong (and you correctly enforce roles on the backend).

**Recommendation:**

- Treat client-parsed role as optional/optimistic only. After `getAuthSession()` succeeds, always use `data.user.role` (and plan/features) as the source of truth.
- Optionally remove `parseRoleFromToken` and rely solely on session data once loaded, to avoid maintaining two sources of “current role.”

---

## 5. Testing & CI

### 5.1 Add CI pipeline (High)

**Current:** No `.github/workflows` (or other CI) was found. Tests and lint are run manually.

**Recommendation:**

- Add a GitHub Actions workflow (or equivalent) that:
  - On push/PR: install backend deps, run pytest; install frontend deps, run `npm run build` and `npm run lint`.
  - Optionally run tests with a real Postgres service or use SQLite for speed (matching your current test DB).
- Ensures every PR is validated and prevents regressions from merging.

### 5.2 Broaden tenant-isolation tests (Medium)

**Current:** `test_auth.py` and `test_customer_accounts.py` include tenant isolation tests (e.g. cross-tenant access denied). Other domains (repair jobs, quotes, invoices, work logs, attachments, stocktakes, etc.) may have fewer or no dedicated isolation tests.

**Recommendation:**

- For each tenant-scoped resource (repair jobs, quotes, invoices, customers, watches, work logs, attachments, stocktakes), add at least one test: create resource as tenant A, request as tenant B (different token), expect 404 or 403.
- Reuse your existing bootstrap + login helpers and keep tests in the same style as `test_customer_accounts.py` and `test_auth.py`.

### 5.3 Frontend tests (Low)

**Current:** Frontend has ESLint and TypeScript build; no unit/integration tests were seen.

**Recommendation:**

- Add a small set of tests for critical paths, e.g.:
  - AuthContext: login stores token, logout clears it, session fetch updates role/plan.
  - API helpers: `getApiErrorMessage` for 401, 4xx with detail string, validation array.
- Use Vitest (fits Vite) or React Testing Library for components. Start with a few high-value tests and grow over time.

---

## 6. Operations & Docs

### 6.1 Environment template (Medium)

**Current:** `.env.example` exists at repo and backend level. `DEPLOY.md` lists env vars for Railway.

**Recommendation:**

- Ensure a single, commented `.env.example` (or `docs/ENV_VARS.md`) lists every variable used by the app (backend + any frontend build-time vars), with safe defaults and “required in production” notes.
- Refer to it from `README.md` and `DEPLOY.md` so new contributors and deployments have a clear checklist.

### 6.2 Health check and readiness (Low)

**Current:** `GET /v1/health` returns status and seed status. No explicit DB connectivity check.

**Recommendation:**

- Optionally extend the health endpoint to run a trivial DB query (e.g. `SELECT 1`) and return 503 if it fails. This helps orchestrators (e.g. Railway, Docker) restart unhealthy instances.
- Keep the response small and avoid exposing internal details.

---

## 7. Summary Priority Matrix

| Priority | Item |
|----------|------|
| **High** | Replace runtime column patching with Alembic migrations |
| **High** | Add JWT refresh tokens and proactive refresh on frontend |
| **High** | Single source of truth for job status labels (and remove duplicates) |
| **High** | Add CI (pytest + frontend build/lint) |
| **Medium** | Split `models.py` into tables/schemas/base |
| **Medium** | Harden production config (JWT secret, bootstrap) |
| **Medium** | Centralize tenant-scoped get helpers in backend |
| **Medium** | React Error Boundary |
| **Medium** | Broaden tenant-isolation test coverage |
| **Medium** | Document env vars in one place |
| **Low** | Rate limit public/signup endpoints |
| **Low** | Proactive token refresh (tied to refresh tokens) |
| **Low** | AuthContext: treat session as source of truth for role |
| **Low** | Structured request logging; health/readiness |
| **Low** | Frontend unit tests for auth and API error handling |

Implementing the high-priority items first will improve security (refresh tokens), reliability (migrations, CI), and maintainability (status constants, CI). The rest can be scheduled in follow-up sprints.
