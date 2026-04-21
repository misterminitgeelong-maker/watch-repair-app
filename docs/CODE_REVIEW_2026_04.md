# Code Review — Mainspring / Watch Repair App

**Scope:** All code under `/workspace`: FastAPI + SQLModel backend (`backend/`), React + Vite + Capacitor frontend (`frontend/`), native Kotlin/Compose Android app (`apps/mainspring-native-android/`), auxiliary scrapers, and infra/docs at the repo root.

**Method:** Static read-through + targeted verification of highest-impact findings (no runtime exec). Where I call out a line, I re-read the file in this session to confirm the claim.

**TL;DR — the top 5 things worth fixing first**

1. **Customer portal watch-jobs query is broken.** `routes/public_jobs.py` filters `RepairJob.customer_id == customer.id`, but `RepairJob` has **no `customer_id` column**. This 500s at runtime. (Verified against `models.py` lines 251–274 and grep.)
2. **Public customer-lookup / portal endpoints have no rate limits, no proof-of-email-control, and mint 30-day bookmarkable tokens from just an email.** Enumeration + long-lived session footgun.
3. **`Dockerfile` bakes `JWT_SECRET="change-me-in-production"` into the image.** Prod startup validator catches it, but the default should not be in the image at all.
4. **Unauth'd `/v1/debug/demo-status` leaks tenant id + plan + B2B count.** It's also embedded inside the `/v1/health` response.
5. **Several large modules mix too many responsibilities**: `models.py` (1899), `routes/auth.py` (1234), `routes/csv_import.py` (1201), `components/RepairQueueModal.tsx` (1012), `components/MobileServicesMap.tsx` (907), `components/AppShell.tsx`. Not bugs — but the main reason the review found the bugs it did.

Below, **High** = correctness/security/data integrity, **Medium** = performance/maintainability, **Low** = style/nits.

---

## 1. Backend (`backend/`)

### Strengths

- **Layered auth**: `dependencies.py` loads user + tenant, checks suspension, verifies `iat` against `auth_revoked_at`, enforces plan limits, and caches with a short TTL. Refresh and access tokens are typed separately (`security.py`).
- **Per-tenant counters are concurrency-safe**: `repair_jobs.py` and `invoices.py` use a compare-and-swap retry loop backed by a uniqueness constraint on `(tenant_id, job_number)` / `(tenant_id, invoice_number)`. Tests exist.
- **Production config guardrails**: `config.validate_runtime_config()` fails fast on default JWT secret, wildcard CORS, localhost public URL, unintended SQLite.
- **Attachment safety**: MIME allowlist, size cap, image re-encode, `_resolve_safe_path` blocks `..` / symlink escape (`services/attachment_storage.py` 39–50), signed download URLs expire in 5 minutes.
- **List endpoint batching done right**: `list_repair_jobs` batch-loads watches, customers, and `claimed_by` users rather than N+1 per row (`routes/repair_jobs.py` ~266–294).
- **Test coverage** for auth, repair jobs, invoices, CSV import safety, attachments, rate limiting, and auto-key flows is solid.

### High priority

| # | File / Line | Finding | Recommended fix |
|---|---|---|---|
| B-H1 | `routes/public_jobs.py:689, 796` | Filters `RepairJob.customer_id == customer.id`, but `RepairJob` (models.py 251–274) has no `customer_id` field. Only `watch_id`, `tenant_id`, `customer_account_id`, and `assigned_user_id`. Either this endpoint has never been exercised or it 500s. Confirmed via `grep "customer_id" models.py` (column exists on `Watch`, `Shoe`, `AutoKeyJob`, but **not** `RepairJob`). | Join through `Watch`: `select(RepairJob).join(Watch, Watch.id == RepairJob.watch_id).where(Watch.customer_id == customer.id)`. Add a test that creates a customer → watch → repair job and calls `POST /v1/public/customer-lookup`. |
| B-H2 | `routes/public_jobs.py` (entire module) | **Zero** `@limiter.limit` decorators in this file (verified — `rg -c` returned 0). `/v1/public/customer-lookup`, `/v1/public/portal/create-session`, `/v1/public/portal/session/{token}` are all unauth'd and can be hit at IP rate. `create_portal_session` mints a 30-day bookmarkable token knowing only an email. | Add per-IP limits (`slowapi`). For portal session issuance, require proof of email control: send a one-time magic link or code, don't mint a 30-day session straight from an email POST. |
| B-H3 | `main.py:217–239, 259–263` | `/v1/debug/demo-status` is unauth'd and returns tenant `id`, `slug`, `plan_code`, and CustomerAccount count. `/v1/health` calls it inline and includes the same payload. | Gate behind `settings.app_env != "production"`, or strip identifiers (boolean “demo tenant exists” only). |
| B-H4 | `routes/csv_import.py:1178–1188` | On unexpected errors returns `HTTPException(400, detail=f"Import failed: {exc}")`. This can echo driver-level errors (IntegrityError details, file paths) back to the client. | Log `exc` via `logger.exception`, return a generic `"Import failed, please try again."`. |
| B-H5 | `routes/attachments.py:48–56` | Signed download URLs are JWTs signed with the same `settings.jwt_secret` used for session tokens. If ever a download URL leaks into logs/analytics, the signing key is the same key that signs auth. | Use a distinct HMAC secret (`ATTACHMENT_SIGNING_SECRET`), or at minimum add a required `purpose: "download"` claim and reject it on auth paths. |
| B-H6 | `Dockerfile:41` | `ENV … JWT_SECRET="change-me-in-production"` is baked into the image. The runtime validator catches it for prod, but shipping this default in the image is fragile (e.g., someone sets `APP_ENV=staging`, the validator skips, and the placeholder persists). | Remove the `JWT_SECRET` line; require it to be injected at deploy time. |
| B-H7 | `main.py:242–271` / overall | `/v1/health` runs 2–3 queries per call (tenant lookup + demo status). Load balancers hit this often. Not a bug, but under load it is a small amplification on every healthcheck. | Split into `/v1/health` (no DB) and `/v1/health/deep` (DB + demo). |

### Medium priority

| # | File / Line | Finding | Recommended fix |
|---|---|---|---|
| B-M1 | `routes/repair_jobs.py:82–91, 297–306` | `_repair_job_to_read` does two `session.get` per call (watch, then customer). `GET /v1/repair-jobs/{id}` skips this helper entirely and returns `RepairJobRead(**job.model_dump())` without `customer_name` / `claimed_by_name`, so the single-GET and list responses have different shapes for the same `RepairJobRead` type. | Unify: one `_assemble(job)` helper used by both handlers; fetch watch/customer in a single query. |
| B-M2 | `routes/csv_import.py:794–798, 946–950` | Per row: `session.exec(select(func.count()).…)` to enforce plan limits. O(rows) count queries. | Count once before the loop; decrement/increment locally during the batch. |
| B-M3 | `routes/platform_admin.py:63–68` | Per-tenant count query in a loop (classic N+1). | One `GROUP BY tenant_id` query. |
| B-M4 | `routes/public_jobs.py:685–728` (after fixing B-H1) | After join fix, still a `session.get(Watch)` / `session.get(Shoe)` per row. | Batch-fetch watches and shoes by the set of ids returned. |
| B-M5 | `app/services/` | Only `attachment_storage.py` lives here. Everything else — billing, numbering, import pipelines, auto-key job orchestration — is inside route handlers. Unit-testing that logic requires an HTTP client. | Extract `services/billing.py`, `services/numbering.py`, `services/csv_import/…` (parse → normalize → persist). Route stays thin. |
| B-M6 | `routes/auth.py` (1234 lines) | Mixes bootstrap, signup, login, refresh, dev-auto-login, multi-site switching, Stripe signup-pending gates, and demo seeding. | Split by concern (`auth_login.py`, `auth_signup.py`, `auth_refresh.py`, `auth_bootstrap.py`). |
| B-M7 | `routes/csv_import.py` (1201 lines) | One module for watch, shoe, mobile-lead import pipelines and all file parsing. | Split parse / normalize / pipeline-per-domain. |
| B-M8 | `models.py` (1899 lines) | Mixes DB tables, enums, API read/write DTOs. | `models/tables/*.py` (tables only) + `schemas/*.py` (DTOs). Alembic still picks up tables via a package `__init__`. |
| B-M9 | `limiter.py` / `main.py` | `slowapi` uses `get_remote_address` with in-memory storage. Multi-worker (uvicorn `--workers > 1`) or horizontally scaled deploys will desynchronize limits. The Dockerfile pins `--workers 1`, which keeps you correct today but is a latent bug when scaling. | Switch to Redis-backed storage before bumping worker count. README already calls this out — make it louder in `DEPLOY.md`. |
| B-M10 | `tenant_helpers.py` | Pattern is “`session.get` then compare `tenant_id`”. Correct, but anyone writing a raw `select()` elsewhere can forget to add `where(Model.tenant_id == auth.tenant_id)`. | Prefer a single pattern: always `select(Model).where(Model.id == id, Model.tenant_id == tenant_id)`; consider a helper `tenant_scoped(session, Model, tenant_id)` that returns a pre-filtered selectable. |

### Low priority / nits

- `datetime_utils.local_calendar_day_bounds_utc` relies on naive-UTC-in-DB invariant; add a one-line docstring to prevent drift.
- Plan/feature constants are referenced in `dependencies.py` and `csv_import.py` independently. Centralize in `app/plans.py`.
- `config.rego_lookup_base_url` is operator-configurable; low SSRF risk but worth an allowlist in production.

---

## 2. Frontend (`frontend/`)

### Strengths

- **Single Axios client** in `src/lib/api.ts` with a **de-duplicated refresh** (`refreshPromise`) and single-retry on 401. This is the correct pattern and avoids the most common auth-refresh bugs.
- **React Query** used throughout with sensible defaults (`staleTime: 30s`, `retry: 1`).
- **Strict TypeScript** (`tsconfig.app.json` with `strict`, `noUnusedLocals`, `noUnusedParameters`). Grep did not find any widespread `any` usage in `src/`.
- **OpenAPI-driven types** via `src/lib/generated/openapi.d.ts` + `api-types.ts`, with scripts `generate:openapi-json` and `generate:api-types`.
- **Lazy routes + `Suspense` + route-scoped `ErrorBoundary`** in `App.tsx` (good blast-radius control).
- **Capacitor integration** with secure storage and native hydration on startup (`main.tsx`, `api.ts`).
- **MSW tests** with `onUnhandledRequest: 'error'` — strict and prevents silent passes.

### High priority

| # | File / Line | Finding | Recommended fix |
|---|---|---|---|
| F-H1 | `capacitor.config.ts:19–31` | `allowNavigation` includes broad wildcard patterns like `*.amazonaws.com` and `*.*.*.amazonaws.com`. Any bucket on AWS stays inside the WebView. | Narrow to specific hostnames actually used; document each entry. |
| F-H2 | `src/context/AuthContext.tsx:316–324` | Dev-only `dev-auto-login` flow calls `/v1/auth/dev-auto-login`. The backend defaults `allow_dev_auto_login: False`, so the server gate works — but keep the client gate too. | Gate on `import.meta.env.DEV` in the fetch path; ensure the call is tree-shaken from prod bundles. |
| F-H3 | `src/components/RepairQueueModal.tsx:318–323` | `useEffect` seeding `queueOrder` depends only on `filteredJobs.length` (with `eslint-disable`). If job *identity* changes but count stays equal (filter swap at same size), order stays stale — shows wrong jobs. | Depend on a stable key (e.g., `filteredJobs.map(j => j.id).join('|')`) or `useMemo` the filtered ids and depend on that. |

### Medium priority

| # | File / Line | Finding | Recommended fix |
|---|---|---|---|
| F-M1 | `src/context/AuthContext.tsx:395–422` | Provider `value` is a new object each render; `login`/`logout`/`refreshSession`/`switchSite`/`hasFeature` are not `useCallback`ed → every `useAuth()` consumer re-renders on every auth change. | Split into `AuthStateContext` + `AuthActionsContext`, or `useMemo` the value with `useCallback` actions. |
| F-M2 | `src/components/AppShell.tsx:159–716` | Huge “god shell”: subscription UI + Stripe nudge + guided-tour content + site switcher + layout + modals. | Move tutorial content to `src/lib/onboardingTour.ts`; extract `GuidedTourOverlay`, `SubscriptionBanner`. |
| F-M3 | `src/components/Sidebar.tsx:1–2`, `src/components/AppShell.tsx:29` | Components import hooks/components from **pages** (`@/pages/InboxPage`, `@/pages/PlatformAdminUsersPage`). Pages should sit above components in the dependency graph. | Move `useInboxCount` to `src/hooks/useInboxCount.ts`; move `AdminReturnBanner` to `components/`. |
| F-M4 | `src/components/RepairQueueModal.tsx:284–305` | Loads up to 200 watch jobs or **all** shoe jobs client-side to build the queue. Mobile-hostile for busy tenants. | Server-side queue endpoint that returns just what the queue needs; paginate / “load more”. |
| F-M5 | `src/components/MobileServicesMap.tsx` (907 lines) | One module combines Google Maps + Leaflet + geocoding + caching + route optimization. | Split `GoogleMapView.tsx` / `LeafletMapView.tsx`, extract `useGeocode`, `optimizeRoute`. |
| F-M6 | `src/components/NewJobModal.tsx` / `NewShoeJobModal.tsx` | Two large multi-step wizards with duplicated customer step. | Extract shared `CustomerStep`, `useCustomerAccounts`. |
| F-M7 | `src/lib/api.ts:214–215` | Mutates `config._retried` on an Axios request config without a type augmentation. | Add `declare module 'axios' { interface InternalAxiosRequestConfig { _retried?: boolean } }`. |
| F-M8 | `src/components/GlobalSearch.tsx:37–60` | Debounced search has no `AbortController`; rapid typing can resolve out of order and display a stale result. | Use `AbortController` per request and pass `signal` to axios. |
| F-M9 | `src/components/ShoeServicePicker.tsx:107–115` | Casts custom services to `ShoeCatalogueItem[]` with synthetic fields; hides shape mismatches. | Introduce a `SelectableItem` union (`'catalogue' \| 'custom'`) with a discriminator, or a mapper with explicit fields. |
| F-M10 | No list virtualization in the tree | Dense lists (auto-key board, jobs, customers) render all rows as DOM. | Adopt `@tanstack/react-virtual` for lists > ~100 rows. |

### Low priority / nits

- `src/components/ui.tsx:175–212` — the `Modal` is a `div`, not `role="dialog"`, no `aria-modal`, no focus trap, backdrop doesn't close, close button has no `aria-label`. Apply the WAI-ARIA dialog pattern.
- `GlobalSearch` overlay lacks `role="dialog"` too.
- Component tests are thin. The big modals and `AppShell` tour are where regressions will bite. Consider adding a few Playwright / RTL smoke tests for `NewJobModal`, `RepairQueueModal`, and sign-in flow.

---

## 3. Native Android (`apps/mainspring-native-android/`)

### Strengths

- Clean layering: Retrofit surface (`MainspringApi.kt`), shared `ApiClient`, encrypted token storage (`TokenStore.kt` via `EncryptedSharedPreferences` + `MasterKey`).
- 401 refresh flow is correct: OkHttp `Authenticator` + `X-Auth-Retry` header prevents loops, skips auth endpoints, clears tokens on refresh failure (`TokenAuthenticator.kt`).
- Emulator-friendly default API URL via `local.properties` / `BuildConfig`.

### High priority

| # | File / Line | Finding | Recommended fix |
|---|---|---|---|
| A-H1 | `api/ApiClient.kt:16–46` | `HttpLoggingInterceptor(BASIC)` is attached to **both** `plainClient` and the authenticated `mainClient`, in **all** build types. BASIC logs request/response status lines; higher levels would log `Authorization`. Release has `minifyEnabled false`, so it's not stripped. Either way, production HTTP activity is being logged. | Guard on `BuildConfig.DEBUG`; in release use `Level.NONE` or remove the interceptor. If you need any prod logging, wrap in a redacting interceptor. |
| A-H2 | `AndroidManifest.xml:6–14` | `android:usesCleartextTraffic="true"` is set globally. OK for emulator dev (`http://10.0.2.2:8000`), but a misconfigured release pointing at `http://` still works silently. | Constrain via `network_security_config.xml` to known dev hostnames; in release, disable cleartext entirely. |

### Medium priority

- `app/build.gradle` — release is `minifyEnabled false`. Enable R8 + ProGuard rules for a token-handling app before shipping to production beta.
- `TokenAuthenticator` uses `synchronized(this)` and blocking `refreshApi.refresh(...).execute()` on the OkHttp worker thread. Fine today (one client instance), but multiple simultaneous 401s all stall on one thread. Document or move refresh onto a dedicated short-lived client.
- Gson `setLenient()` hides API contract drift.
- **Native Kotlin app is not built in CI** — `.github/workflows/ci.yml` builds the Capacitor Android wrapper (`frontend/android/assembleDebug`) but never touches `apps/mainspring-native-android`. Add a second `android_native` job that runs `./gradlew assembleDebug` in `apps/mainspring-native-android/`.

### Low priority

- `AuthViewModel.session()` maps any `Exception` to a generic "Session expired or API unreachable" message. Acceptable UX tradeoff.
- Debug application id suffix `.debug` is good (side-by-side installs).

---

## 4. Scrapers

- **AliExpress** (`aliexpress_watch_movements_scraper/scraper.py:38–42`): `@retry(..., retry_if_exception_type((PlaywrightTimeout, ConnectionError, Exception)))` catches `Exception` — too broad; programming bugs get retried. Narrow to network/Playwright types.
- **Labanda**: Heavy coupling to Drupal `views-table` selectors; saves raw HTML which is a good mitigation for breakage.
- **Automotive prospects**: No retries (ABR streaming, offline CSV) — appropriate.
- All three pipelines overwrite `data/` exports. Document single-writer expectation; concurrent runs will race.

---

## 5. Infra / Docs

### High priority

| # | File | Finding | Recommended fix |
|---|---|---|---|
| I-H1 | `Dockerfile:41` | `JWT_SECRET="change-me-in-production"` baked in image (see B-H6). | Remove default. |
| I-H2 | `WHY_DEMO_MIGHT_FAIL.md:43` | Recommends `python -m uvicorn backend.app.main:app`. The correct command is `uvicorn app.main:app` run from `backend/` (matches README). | Fix the command. |
| I-H3 | `DEPLOY.md` "Environment Variables Reference" | Claims `ALLOW_DEV_AUTO_LOGIN` defaults to `true` and `CORS_ORIGINS` defaults to `*`. Actual defaults in `config.py` are `allow_dev_auto_login: False` (line 25) and `cors_origins` set to a specific allowlist (lines 67–71). | Regenerate from `Settings` + `.env.example`. |

### Medium priority

- `docker-compose.yml` — Postgres password default `changeme`; fine for dev, keep documented.
- CI (`.github/workflows/ci.yml`) runs backend pytest + frontend lint/test/build + Capacitor Android `assembleDebug`. Missing: native Kotlin app build, and a quick `tsc --noEmit` is folded into `build` which is slower feedback than a dedicated step.
- `POST_DEPLOY_CHECKLIST.md` references scripts in `backend/scripts/`; verify paths still exist whenever scripts are moved.

---

## Recommended work order

If you want me to start fixing, the order with highest value-per-edit is:

1. **B-H1** (broken portal query) — small fix, prevents 500s on a customer-facing endpoint.
2. **B-H2** (rate-limit public endpoints) — add `@limiter.limit` to each route in `public_jobs.py`; gate portal session issuance behind a magic link.
3. **I-H1 / B-H6** (remove `JWT_SECRET` from `Dockerfile`).
4. **B-H3** (gate `/v1/debug/demo-status` or remove from `/v1/health`).
5. **B-H4** (CSV import error leakage).
6. **F-H3** (RepairQueueModal stale-order effect).
7. **A-H1** (Android logging in release).
8. **I-H2 / I-H3** (doc fixes).
9. Then the medium-priority refactors: split `routes/auth.py`, `routes/csv_import.py`, `models.py`; extract `AppShell` tour; unify repair-job read shape (B-M1).

If you'd like, reply with "fix the highs" (or a subset) and I'll work through them on this branch with one commit per fix and update the PR as I go.
