# Mobile Services Field Run — Benchmark Checklist

A one-page, do-it-on-a-real-phone run sheet. The goal is **evidence, not vibes**:
walk one real job end to end, time each step, and leave with a concrete
punch-list instead of an impression. This is the run that decides whether we can
honestly claim "faster and more locksmith-specific than ServiceM8."

Run it on a real phone, on cellular (not office Wi-Fi), ideally with a real
customer/job. Repeat weekly. Compare against [the execution board's success
metrics](MOBILE_SERVICES_EXECUTION_BOARD.md#success-metrics-track-weekly).

---

## How to use this sheet

1. Print it or copy the table into a note on the phone you'll run the job on.
2. Start a stopwatch at the top of each step; write the **elapsed seconds** and
   **tap count** when the step's "done" condition is met.
3. In **Where it hurt**, write one line the moment something is slow, confusing,
   or recoverable-but-ugly. Don't fix anything mid-run — capture and move on.
4. After the run, every "Where it hurt" line becomes a punch-list item below.

**Run header**

| Field | Value |
|-------|-------|
| Date | |
| Device / OS | |
| Network (cellular/Wi-Fi) | |
| Tester | |
| Job # used | |
| Real or seeded job? | |

---

## The benchmark sequence

Targets come straight from the board. "Tier" is the P0 ticket each step
pressure-tests, so a failure maps directly back to scope.

| # | Step | Done when… | Target | Elapsed (s) | Taps | Where it hurt |
|---|------|------------|--------|-------------|------|---------------|
| 1 | **Create job from inbound lead** | Job exists with customer + address | part of <5 min to quote (P2.3 / intake) | | | |
| 2 | **Schedule & assign** | Job on the planner, assigned to a tech, survives a refresh | no vanish/dupe after refresh (P0.1) | | | |
| 3 | **Rego lookup autofill** | Vehicle fields populated from plate, or manual fallback used | autofill ≥70%; manual recovery ≤15 s (P1.2) | | | |
| 4 | **Move to en-route** | Status `en_route`; arrival SMS offered/sent | ≤2 taps from active job (P0.3) | | | |
| 5 | **Move to on-site** | Status `on_site` | ≤2 taps (P0.3) | | | |
| 6 | **Send quote** | Customer receives quote link (SMS/email) | part of <5 min lead→quote (P1.1) | | | |
| 7 | **Mark completed** | Status `work_completed`; invoice auto-created with correct total | single invoice, no dupe (P0.4) | | | |
| 8 | **Invoice sent** | Customer has the invoice + payment link | <3 min complete→invoice (metric) | | | |
| 9 | **Record payment** | Invoice marked paid | same-day invoice rate ≥90% (metric) | | | |

**Totals**

| Metric | This run | Target | Pass? |
|--------|----------|--------|-------|
| Lead → quote sent (steps 1–6) | | < 5 min | |
| Complete → invoice sent (steps 7–8) | | < 3 min | |
| Total taps, lead → payment | | (track trend) | |
| Critical blockers hit | | 0 | |

---

## Resiliency spot-checks (do at least one per run)

These are the manual matrices the board calls for under P0.2 / P0.5 — quick to
trigger in the field, impossible to prove from a desk.

- [ ] **Map, no/!bad address** — open a job with a missing or junk address. Expect
      a clear "couldn't place on map" state **with an Open-in-Google-Maps
      fallback**, never a blank/hard-fail map. (P0.2)
- [ ] **Map, geocode miss** — a real address that doesn't resolve. Expect the
      ungeocoded-jobs panel with a working directions link. (P0.2)
- [ ] **Reschedule consistency** — drag the same job across day/week/planner a few
      times, refresh between. Unscheduled-queue count and the board must agree
      after every refresh. (P0.1)
- [ ] **Error injection** — kill cellular mid-action on a create/dispatch/quote.
      Expect an actionable message + a next step, not a silent failure or a
      spinner that never resolves. (P0.5)

---

## Punch-list (fill in after the run)

Each row is a real defect found this run. Sev: **blocker** (stops a field job) /
**friction** (slows it) / **polish**.

| # | Step/check | What happened | Sev | Fix idea | Owner |
|---|-----------|---------------|-----|----------|-------|
| | | | | | |
| | | | | | |
| | | | | | |

**Release gate:** broad rollout only when a run has **0 blockers** and the two
median timing targets are met two weeks running (per the board's release gate).

---

## After the run

- Promote every **blocker** row into the real P0 queue — these replace the
  speculative ones.
- Log the run header + totals so the weekly trend is visible.
- If a step beat ServiceM8 on clicks/time, note it — that's sales/demo ammo.
