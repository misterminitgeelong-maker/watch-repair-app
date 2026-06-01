# Customer Repair-Tracking Portal — Overhaul Plan

Scope: the **repair-tracking portal** (`/customer-portal`), not the mobile-key
booking portal (`/portal/:slug`).

## Current implementation

The flow is three thin pieces:

- **Entry** — `frontend/src/pages/CustomerPortalPage.tsx` (`/customer-portal`):
  type an email → `POST /v1/public/customer-lookup` returns active jobs; in the
  background `POST /v1/public/portal/create-session` mints a 30-day bookmark token.
- **Bookmark** — `/customer-portal/s/:token`: `GET /v1/public/portal/session/{token}`
  re-runs the same lookup.
- **Detail** — each row links *out* to a standalone page: `/status/:token` (watch)
  or `/shoe-status/:token` (shoe).

Backend lives in `backend/app/routes/public_jobs.py`. The watch+shoe aggregation
is duplicated between `customer_lookup` (~line 724) and `get_portal_session_jobs`
(~line 828).

## Problems to fix (priority order)

1. **Cross-tenant leak.** `customer_lookup` matches `Customer` by email across all
   tenants and returns one flat merged list, with no indication which shop each job
   belongs to.
2. **Mobile-key jobs missing.** Aggregation returns only `RepairJob` (watch) and
   `ShoeRepairJob` (shoe); `AutoKeyJob` is never included.
3. **No branding.** Generic `--ms-*` tokens, no shop name/logo, despite tenant
   branding existing in the data model.
4. **Read-only / dead-ends.** Pending quotes, unpaid invoices, and booking
   confirmations are not actionable inline even though endpoints exist
   (`auto-key-quote/{token}/decision`, `shoe-quotes/{token}/decision`,
   `auto-key-invoice/{token}/checkout`, `auto-key-booking/{token}/confirm`).
5. **No history/receipts.** Lookup filters out collected/cancelled jobs.
6. **Fragile bookmark + raw status.** Link is only shown on-screen, never emailed;
   status is raw `snake_case` via regex with no progress/stage indicator.
7. **(Deferred) No identity verification.** Email is trusted. OTP is out of scope
   for now, but the entry flow should be designed so it can drop in later.

## Decisions

- **Cross-tenant rule: group by shop.** Return all the customer's jobs, grouped
  into a section per shop, each with its own branding. Do not merge into one flat
  list, and do not scope to a single shop.
- **Execution: Cursor**, phased, committing after each phase.

## Phases

### Phase 0 — Backend correctness + single source of truth
- Extract `_collect_customer_jobs(session, email, include_history=False)` used by
  both `customer_lookup` and `get_portal_session_jobs`.
- Include `AutoKeyJob` alongside watch and shoe jobs.
- Group results by shop:
  `{ shops: [{ tenant_id, shop_name, logo_url, brand_color, jobs: [...] }] }`.
- Add `include_history` flag returning collected/cancelled jobs when true.

### Phase 1 — Branded, unified portal shell
- Rebuild `CustomerPortalPage.tsx` around the grouped payload, one section per shop.
- Shared status → { friendly label, stage } map + progress tracker
  (Received → In progress → Ready → Collected). Replace `readableStatus`.
- Active / History toggle.
- Email the bookmark link on lookup (`backend/app/email_client.py`), keep banner.

### Phase 2 — Make it actionable
- Inline actions on job cards wired to existing endpoints (approve/decline quote,
  pay invoice, confirm booking) — no new business logic.
- Bring job detail inline (timeline from `*StatusHistory`, items, attachments) or
  embed the standalone status pages as portal routes for consistent branding.
- Empty state becomes an action (book a drop-off / contact the shop).

### Phase 3 — Engagement
- Opt-in status-change notifications (email + `app/sms.py`).
- Request-a-callback / message-to-shop writing a `TenantEventLog` event.
- Downloadable receipts/invoice archive in History.

## Constraints
- Match existing style and `--ms-*` design tokens.
- Keep all existing routes/endpoints working.
- Extend `backend/tests/test_customer_portal_public.py`.
- Run backend tests + frontend typecheck/build before declaring a phase done.
