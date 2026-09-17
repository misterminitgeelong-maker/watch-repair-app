# Mobile Services — status vocabulary, catalogue categories, operations cockpit, finance report

## 1. Status vocabulary (one label, one category, everywhere)

`backend/app/auto_key_status.py` is the single definition of the Mobile Services job
lifecycle. `frontend/src/lib/mobileStatus.ts` mirrors it for presentation and both are
pinned to the same contract by `backend/tests/test_mobile_status_vocabulary.py` and
`frontend/src/lib/mobileStatus.test.ts` — change them together.

| Canonical stored value | Label | Reporting category | Presents the same for (aliases) |
|---|---|---|---|
| `awaiting_quote` | Awaiting Quote | pipeline | — |
| `awaiting_customer_details` | Awaiting Customer Details | pipeline | — |
| `quote_sent` | Quote Sent | pipeline | `awaiting_go_ahead` |
| `awaiting_booking_confirmation` | Awaiting Booking Confirmation | booking | `pending_booking`, `go_ahead` |
| `booking_confirmed` | Booking Confirmed | booking | `booked` |
| `booking_on_hold` | Booking on Hold | booking | `job_delayed`, `awaiting_parts`, `parts_to_order`, `sent_to_labanda`, `quoted_by_labanda`, `at_third_party_for_quoting`, `third_party_quote_approved`, `at_third_party_repairer` |
| `en_route` | En Route | field | — |
| `on_site` | On Site | field | `working_on`, `service` |
| `work_completed` | Work Completed | completed | `booking_completed`, `completed`, `awaiting_collection` |
| `invoice_paid` | Invoice Paid | paid | `collected` |
| `failed_job` | Failed Job | lost | — |
| `no_go` | No Go | lost | — |

*Closed* = completed + paid + lost (the physical work is over; money may still be open).
The "Active" directory excludes closed statuses, so **Completed, not paid** is a
follow-up queue rather than active work.

Where it is used: Today (cockpit), List chips and status picker, Kanban columns,
job detail and job card pickers, new-job modal, dispatch/week grids, the map,
`/v1/reports/auto-key` (`jobs_by_status` now carries `label` and `category`) and
CSV import (`_infer_auto_key_status`).

### The mismatch that prompted this

The Kanban folded `awaiting_booking_confirmation` into the **Quote Sent** column and
`pending_booking` into **Booking Confirmed**, while every other surface labelled them
"Awaiting Booking Confirmation". The board now has one column per stage; closed
stages (Invoice Paid, Failed / No Go) appear only when the directory shows completed
or all jobs.

### Migration / compatibility note

* Two flows had grown parallel stored values for the same stage: the booking-SMS flow
  wrote `pending_booking` → `booked`, quote approval wrote
  `awaiting_booking_confirmation` → `booking_confirmed`. New transitions now write
  the canonical value; the public confirm endpoint accepts either spelling.
* Migration `20260918a_mobile_ops_cockpit` rewrites the four duplicate values
  (`pending_booking`, `booked`, `job_delayed`, `booking_completed`) to their canonical
  twins on `autokeyjob`, following `20260917b_mobile_statuses`. It is a tidy-up, not a
  prerequisite: an un-migrated deployment still labels, groups and reports every
  alias correctly. Downgrade keeps the data (the canonical values are valid).
* `JobStatus` (API literal) is unchanged; no enum values were removed, so older
  clients keep working. The public booking payload gains `awaiting_confirmation`
  and reports `booking_confirmed` (previously `booked`) after a confirm.
* Customer-portal mapping (`portalStatus.ts`) and SMS/webhook terminal sets still
  list the aliases, so nothing changes for customers.

## 2. POS catalogue categories

Garage-door lines appeared in the mobile-key POS because the hardcoded quick-item
list had no category, not because of seed data: `service_pricing` contains no
garage rows and `garage_servicing_pricing` is a separate table. Nothing was deleted.

* Categories: `vehicle_key`, `general_service`, `garage_door`
  (`backend/app/mobile_catalogue.py`).
* Per-shop selection lives in `tenant.mobile_catalogue_categories_json`
  (NULL = default: vehicle keys + general services). Owner-only
  `PATCH /v1/toolkit/mobile-catalogue`; everyone can `GET` it, and
  `/v1/mobile-services-pricing/meta` returns `enabled_categories` for the POS.
* The POS quick items and the "Price by manufacturer" tabs show only enabled
  categories. The read endpoints for each catalogue stay open — visibility is a
  presentation choice, and historical quotes/invoices are untouched.
* UI: Mobile Services → Toolkit → **POS catalogue** (owner).

## 3. Operations cockpit (`GET /v1/reports/auto-key/cockpit`)

Computed server-side in the shop's timezone (`tenant.timezone`, falling back to
`SCHEDULE_CALENDAR_TIMEZONE`). Optional `as_of=YYYY-MM-DD` evaluates a past day.

### Focuses — every tile drills into the rows it counted

`backend/app/mobile_cockpit.FOCUS_DEFINITIONS` defines each headline number as a SQL
filter over `autokeyjob`. `GET /v1/auto-key-jobs/page?focus=<key>` applies the same
filter, so the list a user lands on has exactly the count they clicked
(`test_cockpit_counts_match_the_list_drill_down_for_every_focus`).

| Focus | Definition |
|---|---|
| `late` | Active, scheduled time has passed, not en route / on site / on hold |
| `today` | Active, scheduled today (shop day) |
| `in_field` | `en_route` or `on_site` |
| `unscheduled` | Active, no `scheduled_at` |
| `unassigned` | Active, no technician |
| `on_hold` | Booking on hold (and its aliases) |
| `needs_quote` | Awaiting quote / customer details |
| `quote_follow_up` | Quote sent, no change for 2+ days |
| `confirmation_follow_up` | Awaiting booking confirmation for 24+ hours |
| `completed_unpaid` | Work completed, invoice not paid |
| `overdue_invoices` | Unpaid invoice older than 7 days |
| `unpaid_invoices` | Any unpaid invoice (excl. void/refunded) |
| `this_week` | Scheduled in the current shop week (failed / no-go excluded) |
| `completed_this_week` | `work_completed_at` in the current week |
| `invoiced_this_week` | Invoice raised in the current week |
| `collected_this_week` | Invoice paid in the current week |

`?category=pipeline|booking|field|completed|paid|lost` filters the list by reporting
category; `?tech=<user_id>` narrows to a technician (URL params on the List view).

### Money ladder — definitions

| Metric | Definition | Direction |
|---|---|---|
| Booked | Sell value (`cost_cents`) of jobs scheduled in the period, whatever stage they reached; failed / no-go excluded | higher is better |
| Completed | Value of jobs whose `work_completed_at` is in the period (invoice total, else job price) | higher is better |
| Invoiced | Invoices created in the period, excluding void/refunded | higher is better |
| Cash collected | Invoices with `paid_at` in the period | higher is better |
| Outstanding | Unpaid invoices as of now (not period based), with 0–7 / 8–30 / 31+ day ageing | lower is better |
| Jobs created / completed | Counts by `created_at` / `work_completed_at` | neutral / higher is better |

Comparisons: **this week** (Mon–Sun, shop time) vs **last week**, the **four-week
average** of the four full weeks before this one, and the owner's **weekly cash
target** (`tenant.mobile_weekly_target_cents`, `PATCH /v1/reports/auto-key/cockpit/target`).
While the week is incomplete the primary comparison is like-for-like: the same
number of elapsed days of each prior period and a pro-rated target (`partial: true`,
`days_elapsed`). Percentages are `null` when the baseline is zero; the UI shows
"no prior" rather than dividing by zero. Tones (`good`/`bad`/`neutral`) honour the
metric's direction — a rise in Outstanding is bad.

### Technicians

Per active technician (plus any owner/manager holding active jobs): bookings today,
booked vs available minutes, utilisation, in-field now, next job, late count,
schedule conflicts (two bookings closer than 60 minutes), and this week's completed
jobs and collected cash. **Assumptions are surfaced in the payload and the UI**:
60 minutes per booking and an 8-hour day, because no estimated duration is
recorded; no travel time or clustering, because job locations are not geocoded.

### Data quality flags

`data_quality[]` lists what would make the numbers more trustworthy: assumed
durations, jobs booked today with no address, scheduled jobs with no price (Booked
understated), no target set, no technicians, no geocoding.

## 4. Finance report (`GET /v1/reports/auto-key/finance`)

Reports tab. One period drives everything: `period=week|last_week|month|last_month|quarter|last_4_weeks|last_13_weeks|custom` (+ `date_from`/`date_to`), resolved to shop-local civil dates; the comparison is the same number of days immediately before. `backend/app/mobile_finance.py` holds the arithmetic (pure, unit-tested); the route only fetches rows.

| Section | What it is |
|---|---|
| Money | Booked, Completed, Invoiced, Cash collected (period based) and Outstanding at period end (raised by then, unpaid by then). Each tile drills into the list via `?date_field=scheduled|completed|invoiced|paid&date_from&date_to` — the list applies the same filter (`mobile_finance.list_date_filter`). |
| Target | Weekly cash target pro-rated to the elapsed days of the period; attainment and variance. |
| After commission | Technician commission on cash collected (each technician's rules) and cash minus commission. **This is not a gross margin** — no parts / cost of goods are recorded on mobile jobs, so margin is deliberately not shown. Hidden when no technician has commission rules. |
| Conversion | Quote → approved (quotes sent in the period), Lead → booking (jobs created in the period that reached a confirmed booking or later), Booking → completed (jobs scheduled in the period that are done). |
| Activity | Jobs created / completed, jobs per working day (Mon–Sat, to date), quotes sent. |
| Receivables | Ageing 0–7 / 8–30 / 31–60 / 61+ days as of now, oldest open invoices. |
| Trend | 13 Monday-weeks ending in the period for booked/completed/invoiced/collected/jobs, with 4- and 13-week averages. |
| Technicians | Per technician for the period: booked, completed, invoiced, collected, per-job, commission, utilisation (60 min per booking against 8h × working days), average on-site minutes with sample size. |
| Durations | Estimated = an assumed 60 min (no per-job estimate exists yet). Actual on-site = On Site → Work Completed and travel = En Route → On Site, both read from `auto_key_status_changed` event-log rows, reported with `count` / median / p90 and by job type. Transitions longer than 12h (on site) or 4h (travel) are treated as forgotten statuses and skipped. |
| CSV | `/finance/export?kind=summary` (the metrics, conversion, ageing, trend and technician tables as shown) and `?kind=invoices` (invoices raised or paid in the period). Owner/manager only; same period parameters as the screen. |

`data_quality[]` names what limits the numbers: no cost data, no commission rules, unpriced bookings, paid invoices without a paid date, duration sample size, no target, no geocoding.

### Not in this phase

Per-job estimated durations (a field on the job), route/cluster estimates (needs
geocoded job locations), and cost-of-goods capture for a real gross margin.
