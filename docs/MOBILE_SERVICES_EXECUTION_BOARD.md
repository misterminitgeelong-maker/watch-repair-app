# Mobile Services Execution Board (Beat ServiceM8)

This board is optimized for the next 8 weeks, with a hard field-test focus in week 1.

## Objective

Ship a Mobile Services experience that is faster and more locksmith-specific than ServiceM8 for solo/small teams.

## Success Metrics (track weekly)

- Lead to first quote sent: under 5 minutes (median)
- Job complete to invoice sent: under 3 minutes (median)
- Same-day invoice rate for completed jobs: above 90%
- Schedule adherence (within promised window): above 85%
- Critical field-test blockers: 0 open

---

## P0 - Field-Test Week (Ship in 7 days)

### P0.1 Dispatch and planner reliability
- **Why**: Field teams need predictable schedule behavior under pressure.
- **Scope**
  - Stabilize day/week/planner drag and reschedule flows
  - Ensure unscheduled queue always visible and recoverable
  - Ensure schedule saves survive refresh
- **Acceptance criteria**
  - Reschedule from all planner entry points updates job consistently
  - No duplicate/vanishing jobs after drag + refresh
  - Unscheduled queue count matches backend query after refresh
- **Evidence**
  - 20 manual reschedule actions across day/week/planner without mismatch

### P0.2 Mobile map resiliency and fallback UX
- **Why**: Map failures in the field must degrade gracefully.
- **Scope**
  - Handle missing maps key, empty addresses, and geocode misses cleanly
  - Always provide "open in Google Maps" fallback from job cards/details
  - Prevent stale marker display after filters/date changes
- **Acceptance criteria**
  - No map hard-fail states; user sees clear next action
  - Marker list and visible jobs stay in sync across date/tech filters
- **Evidence**
  - Test matrix pass for: key missing, no address, partial geocode failure

### P0.3 Job execution quick actions
- **Why**: Service speed is the key competitive win.
- **Scope**
  - One-tap transitions for `scheduled -> en_route -> on_site -> completed`
  - Keep arrival SMS action visible on job detail
  - Guard against invalid transitions with clear message
- **Acceptance criteria**
  - Core status transitions complete in <= 2 taps from active job view
  - Arrival SMS can be sent from active job without navigation detour
- **Evidence**
  - 10 end-to-end field simulations pass (status + SMS + notes)

### P0.4 Quote/invoice reliability on completion
- **Why**: Cashflow breaks are release blockers.
- **Scope**
  - Preserve single-invoice guarantees for completion flow
  - Ensure invoice generation behavior matches quote state rules
  - Show user-facing reason when auto-invoice does not occur
- **Acceptance criteria**
  - No duplicate invoice creation under repeat complete actions
  - Completion billing behavior passes backend tests + manual checks
- **Evidence**
  - Automated tests green + 10 manual completion cycles

### P0.5 Field-safe error handling
- **Why**: Ambiguous errors cause operator churn.
- **Scope**
  - Standardize actionable error messages in Mobile Services paths
  - Avoid silent failures on create/update/dispatch/quote actions
- **Acceptance criteria**
  - Every failed primary action shows clear message + next step
  - No unhandled promise errors in critical path
- **Evidence**
  - Error-injection smoke pass with expected user messages

---

## P1 - Competitive Edge Sprint (Weeks 2-4)

### P1.1 Locksmith quick quote presets — ✅ SHIPPED (telemetry deferred)
- **Why**: Beat ServiceM8 on locksmith-specific speed.
- **Status**: One-tap single-service presets + multi-line bundles in both
  auto-key quote builders (`QUOTE_PRESETS` / `QUOTE_BUNDLES`); editable qty + GST.
  Quote-from-preset in ≤30s met. **Deferred**: preset adoption telemetry (low
  value for a solo operator; revisit with staff/rollout).

### P1.2 Rego lookup UX hardening — REMOVED (off-roadmap)
- Vehicle plate (rego) lookup is **not** being built — the third-party API is
  too expensive to justify. Vehicle details are entered manually. This ticket is
  retained only as a record of the decision; do not implement.

### P1.3 Fleet/B2B mobile workflow polish — ✅ SHIPPED
- **Why**: Strong differentiator for dealership/fleet work.
- **Status**: `NewAutoKeyJobModal` links a customer account inline (auto-applies
  B2B pricing tier); `CustomerAccountsPage` has the statement → month-end invoice
  flow. Account-linked jobs create without cross-page detours.

### P1.4 Dispatch SLA indicators — ✅ SHIPPED
- **Why**: Operational clarity beats generic feature volume.
- **Status**: `computeSlaChip` renders late/at-risk/aging chips on dispatch
  cards via `SlaChipBadge`; dispatch list has a time/risk sort toggle
  (`slaRiskWeight`). At-risk jobs visible at a glance; risk queue clearable from
  one screen.

---

## P2 - Moat Features (Weeks 4-8)

### P2.1 Route order assistant
- **Why**: Improve productivity without building full routing engine.
- **Scope**
  - Suggest visit order based on area/time windows
  - Keep manual override simple
- **Acceptance criteria**
  - Suggested order available for day schedule
  - Manual route edits remain one interaction

### P2.2 Mobile service KPI cockpit — ✅ SHIPPED
- **Why**: Prove value and identify process drag.
- **Status**: `/reports/auto-key` computes mobile-vs-shop revenue split, jobs per
  tech, lead→quote conversion, avg cycle time, same-day invoice rate, and
  schedule adherence; rendered in the AutoKeyJobsPage Reports view with good/bad
  thresholds. CSV exports exist for jobs/customers/invoices/period summary.

### P2.3 Lead-to-dispatch conversion board
- **Why**: Convert inbound leads faster than competitors.
- **Scope**
  - Website lead ingest queue with SLA and routing confidence
  - "Quote needed" and "follow-up due" surfacing
- **Acceptance criteria**
  - No orphaned leads in production workflow
  - Lead-to-job conversion tracking visible by day/week

---

## Work Cadence and Ownership

- **Daily**: 15-minute triage of field feedback and blockers
- **Twice weekly**: release windows for Mobile Services fixes
- **Weekly**: compare benchmark timings against baseline

Suggested ownership (single founder + AI):
- **Owner**: prioritize and sign off P0 scope daily
- **Build**: implement tickets in small vertical slices
- **QA**: run fixed smoke script after every push

---

## Weekly Benchmark Script (ServiceM8 comparison)

> Run sheet: [MOBILE_SERVICES_FIELD_RUN.md](MOBILE_SERVICES_FIELD_RUN.md) — a
> printable one-pager with timing slots, resiliency spot-checks, and a
> punch-list that feeds blockers back into the P0 queue.

Run this sequence and record time/errors:
1. Create job from inbound lead
2. Schedule and assign
3. Move to en-route and on-site
4. Send quote
5. Mark completed
6. Generate/send invoice
7. Record payment

Track:
- completion time per step
- number of clicks
- user confusion points
- recoverability from errors

If faster and clearer on locksmith workflows, we are winning.

---

## Release Gates

Before broad rollout:
- P0 tickets complete
- Backend tests green
- Mobile Services smoke checklist pass
- No critical open bugs in dispatch, status, quote, or invoice flows

Before "better than ServiceM8" claim in sales/demo:
- 2 consecutive weeks meeting success metrics
- At least 20 real field jobs logged with no critical blockers
