# Mainspring — remaining work

Standalone execution plan. Everything here is verified against the repo at
`main` = `4a7aa52`. Line numbers and counts were measured, not estimated.

**Read this first:** both remaining items were deliberately *not* done, for the
same reason — the code they touch has no test coverage, and refactoring
uncovered code is how you turn a tidy-up into an outage. Each phase below
therefore writes the safety net **before** the refactor. The tests are worth
having even if the refactor never happens.

Do the phases in order. Each is independently shippable; do not batch them into
one pull request.

---

## Context you need

**Stack.** FastAPI + SQLModel + Alembic + Postgres (psycopg 3) backend;
React 19 + Vite 7 + Tailwind v4 + TanStack Query frontend. Single container on
Railway, deploys on merge to `main`.

**Run the backend tests against Postgres, not SQLite.** This matters more than
it sounds. Three bugs have already reached `main` in this project because
SQLite could not express the behaviour under test — foreign keys are not
enforced by default, there are no advisory locks, and UUID coercion differs.
The `backend-sqlite` CI job is the convenience path; `backend` is the real one.

```bash
# from backend/
export DATABASE_URL="postgresql://USER:PASS@localhost:5432/mainspring_test"
export JWT_SECRET=ci-secret-not-for-production APP_ENV=test TEST_SCHEMA_BOOTSTRAP=alembic
python -m pytest tests/ -q
```

Current baseline: **510 passed, 1 skipped** on Postgres.

**Tenant isolation is now structural.** `app/tenant_scope.py` restricts every
ORM statement on an authenticated session to the caller's tenant — including
`session.get()`. If a query that should see other tenants starts returning
nothing, that is why. Read `docs/TENANT_ISOLATION.md` before working around it,
and use `without_scope(session)` rather than opening a second session.

**Prove every regression test fails without its fix.** Sabotage the fix, run
the test, confirm red, restore. A test that passes against the broken code is
worse than no test, because it stops people looking. This caught a bad test
twice in the work leading up to this plan.

---

## Phase 1 — Characterisation tests for the shoe and mobile CSV import paths

**Backend. No production code changes. Ship on its own.**

### Why

`_import_csv_sync` in `backend/app/routes/csv_import.py:660` is **581 lines**
handling three import targets:

| target | lines | covered by tests |
|---|---|---|
| `watch` | 139 (741–879) | yes — 7 tests |
| `shoe` | 147 (882–1028) | **none** |
| `mobile` | 162 (1031–1192) | **none** |

`tests/test_csv_import_safety.py` has seven tests and **not one passes
`import_target`**, so all seven exercise the default `watch` branch only. 309
lines that parse spreadsheets uploaded by franchisees have no test at all.

### The work

Add `backend/tests/test_csv_import_targets.py` covering the shoe and mobile
paths at the same level the watch path already enjoys.

The endpoint is `POST /v1/import/csv` with `import_target` as a **query
parameter** (`backend/app/routes/csv_import.py:631`, pattern
`^(watch|shoe|mobile)$`). Model the new tests on the existing file's
`_csv_file()` helper and auth bootstrap.

**Plan gating.** `_auth_has_import_target` (line 538) maps targets to plan
features: `shoe` needs the `shoe` feature, `mobile` needs `auto_key`. Make sure
the test tenant's `plan_code` grants them, or the request 403s before reaching
the code under test. Features are listed in `app/dependencies.py:144`.

**Column names.** Both branches resolve columns through `_get_first(row, [...])`
with generous alias lists, so canonical names work:

- shoe (from line 888): `customer_name`, `phone`, `date_in`, `shoe_brand`,
  `ticket_number`, plus the quote/cost columns
- mobile (from line 1037): `customer_name`, `phone`, `quote`, `cost`,
  `date_in`, `ticket_number`

Read the actual alias lists rather than trusting this summary.

**Cover, per target:**

1. dry run writes nothing
2. a normal run creates the expected rows (`ShoeRepairJob` / `AutoKeyJob`)
3. invalid rows are reported in `skipped_reasons` rather than aborting the import
4. duplicate ticket numbers get unique job numbers
5. a ticket number already in the database does not collide
6. `replace_existing` clears only the target's own tab
7. the response `ImportSummaryResponse` counts match what landed

Assert on **database state and the response summary**, not on internal
structure — these tests have to survive Phase 2 rewriting the code underneath
them.

### Done when

Shoe and mobile have parity with the watch coverage, and the full Postgres
suite is green.

---

## Phase 2 — Split `_import_csv_sync` into per-target strategies

**Backend. Do not start until Phase 1 is merged.**

### The shape

The function is: preamble (validation, `_load_rows`, tenant lookup,
`replace_existing` clearing, import-log setup) → a single **490-line `try`
block** → return. Inside the `try` is one `if import_target == …` chain with the
three branches above, then import-log finalisation.

The branches share mutable state: `imported`, `skipped`, `skipped_reasons`,
`customer_cache`, `job_seq`, `job_number_usage`,
`duplicate_customer_rows_in_file`, and the `log_skip` closure.

### The work

Extract `_import_watch_rows`, `_import_shoe_rows`, `_import_mobile_rows`.

Bundle the shared counters into one small mutable dataclass — call it
`ImportRunState` — rather than threading eight parameters through each
function. Give it the `log_skip` behaviour as a method. The preamble and the
import-log finalisation stay in `_import_csv_sync`.

Dispatch through a dict keyed by target, the same pattern
`_WEBHOOK_HANDLERS` uses in `app/routes/billing.py` (see PR #36 for a worked
example of exactly this refactor).

**Do not change behaviour.** Not the skip reasons, not the job-number
allocation, not the counts. Phase 1's tests are the contract.

### Done when

Each strategy is under ~160 lines, `_import_csv_sync` is under ~80, the full
Postgres suite is green, and the diff contains no behaviour change you cannot
point at a test for.

---

## Phase 3 — Characterisation tests for the three job-detail pages

**Frontend. Ship on its own. This is the prerequisite for Phase 4.**

### Why

| page | lines | tests |
|---|---|---|
| `frontend/src/pages/JobDetailPage.tsx` | 1,319 | **none** |
| `frontend/src/pages/ShoeJobDetailPage.tsx` | 1,114 | **none** |
| `frontend/src/pages/AutoKeyJobDetailPage.tsx` | 1,631 | **none** |

**4,064 lines with zero coverage**, and these are the screens shop staff use all
day. Phase 4 rewrites them. Without this phase, Phase 4 is a blind rewrite of
the application's core surface, verified by nothing stronger than "it compiles".

### The infrastructure already exists

`msw` 2.13, `@testing-library/react` 16.3 and `@testing-library/user-event` are
installed, with a shared server at `src/test/msw/server.ts` and handlers at
`src/test/msw/handlers.ts`. `src/lib/listAutoKeyJobs.msw.test.ts` is a working
example — note it sets `api.defaults.baseURL` to an absolute origin, because
Node's axios cannot resolve a relative `/v1` for MSW to intercept.

Routes are in `src/App.tsx` (`jobs/:id` at line 175 and the shoe/auto-key
equivalents nearby). Pages are lazy-loaded, so tests need `Suspense`.

### The work

For **each** of the three pages, render with MSW-mocked API responses and assert
the things a user would notice:

1. the header renders job number, title, customer and current status
2. the status rail shows the right stage and the right available transitions
3. line items render with correctly formatted money (`en-AU`, and check a
   negative)
4. the attachments section lists attachments and shows its empty state
5. the message thread renders inbound, outbound and system messages distinctly
6. quote and invoice actions appear only in the statuses that allow them
7. a failed fetch renders an error state rather than a blank page
8. the loading state renders before data arrives

Add the per-vertical differences too — that is the point of having three:
watch has no line-item table the way shoe does; auto-key has vehicle fields and
dispatch actions the others lack.

**Prefer `getByRole` and visible text over test ids**, so the assertions survive
markup changes in Phase 4. If you find yourself adding `data-testid` to make an
assertion work, that assertion is probably too tightly coupled to the current
DOM.

### Done when

Each page has meaningful coverage of the eight areas above, `npm test` and
`npm run typecheck` are green, and you can describe what each test would catch.

---

## Phase 4 — Collapse the three job-detail pages

**Frontend. Do not start until Phase 3 is merged. The largest item here.**

### Why

Three structurally identical screens, instantiated once per vertical: header,
status rail, line items, attachments, message thread, quote and invoice
actions. They differ in statuses, line-item shape and available actions.

Every cross-cutting change is a three-file change with three chances to miss
one. Expect roughly 4,067 lines to become ~1,400.

They already share their building blocks — `@/components/WorkflowRail`,
`JobMessageThread`, `JobCustomFields`, `SecureAttachment`, `@/components/ui` —
so the duplication is in the orchestration, not the widgets.

### The work

Extract a `JobDetailShell` taking a per-vertical config: statuses and
transitions, line-item shape, available actions, and the API functions to call.

**Go one vertical at a time**, with the other two untouched and working. Watch,
then shoe, then auto-key — auto-key is the largest (1,631 lines) and most
divergent, so it benefits from the shell being proven on the other two first.

One vertical per pull request. A single PR rewriting all three is not reviewable
and not safely revertible.

### Verification — this one cannot be done by tests alone

Phase 3's tests catch regressions in rendering and state. They will not catch a
broken end-to-end workflow. **Click through all three verticals** before and
after each vertical's PR:

- intake → quote → send quote → approve → invoice → pay → collect
- print an intake ticket and an invoice
- upload a photo, add a note, send an SMS from the thread
- the offline queue: go offline mid-edit, come back, confirm the replay

If you cannot do this manually, do not merge it. This is user-facing surface on
a system real shops run their day on.

---

## Lower priority, recorded so it is not lost

**From the batch 3 review** — none urgent, all real:

- **B3-03** — `reject_stale_write` is wired to 2 endpoints while the offline
  queue replays every mutation. Needs a scope decision, not a patch.
- **B3-04** — `X-Queued-At` trusts the client's wall clock; a skewed tablet
  either bypasses the check or gets spurious 409s.
- **B3-05** — silent truncation at 20,000 rows; `X-Total-Count` is fetched but
  never surfaced in the UI.
- **B3-08** — every list request runs a second `COUNT(*)`. **Measured**: at
  200k jobs it costs 15–20 ms against a 0.35 ms page query; at a realistic 20k
  it is 3–4 ms. Not worth fixing until a single tenant passes ~50k jobs.
- **B3-09** — notification logging opens a connection per message.

**Backend schema under-specification**, both surfaced by the API type
conformance work:

- `CustomerPortalLookupResponse.pending_actions` is declared as a bare
  `{additionalProperties: true}` object, so the generated TypeScript carries no
  field information. Give it a real response model; then it can be added to
  `frontend/src/lib/api/conformance.test-d.ts`.
- `InboundEmail.status` and `JobMessage.direction` are typed `str` in their
  response models although the application only ever writes three values each.
  Narrowing them to `Literal` would let the frontend stop using an open-enum
  workaround. **This needs a data audit first** — the columns have no check
  constraint, and narrowing a *response* model means an unexpected legacy row
  500s the endpoint. Audit the distinct values in production, add a check
  constraint, then narrow.

**Type alignment.** 39 of 197 hand-written API interfaces are asserted against
the backend in `conformance.test-d.ts`; another 38 became pairable via the
backend's `*Read` suffix. The rest are named differently. Every interface
renamed to match its backend schema can be added to the assertion list.

---

## Ground rules

1. **One phase per pull request.** Phases 1–3 are each one PR; Phase 4 is three.
2. **Tests before refactors**, always, where coverage is missing.
3. **Prove regression tests fail without their fix.** Sabotage, run, restore.
4. **Verify on Postgres**, not only SQLite.
5. **Do not widen scope mid-phase.** Note what you find and move on.
6. **Say what you did not do.** A phase that ships 80% with the rest named
   honestly is worth more than one that claims 100%.
