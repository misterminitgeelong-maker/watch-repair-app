# Native Android: where things live (web menu vs app)

Taps are counted from any screen with the bottom bar visible. "Before" is the Atelier build; "After" is this branch.

| Web menu / page | Before (native) | After (native) |
|---|---|---|
| Dashboard | Today tab, 1 | Dashboard tab, 1 (renamed; the headline still reads "Today, at the bench.") |
| Book mobile services | More > group > item, 3 | More > Book mobile services, 2; Today quick action, 1 |
| Inbox | Inbox tab, 1 | Inbox tab, 1 |
| Customers | People tab, 1 | Customers tab, 1 (renamed to the web name) |
| Watch Repairs | Jobs > Watch, 2 | Today tile 1; More > Watch Repairs 2; Jobs > Watch 2 |
| Shoe Repairs | Jobs > Shoe, 2 | Today tile 1; More > Shoe Repairs 2; Jobs > Shoe 2 |
| Customer Orders | missing | More > Customer Orders, 2 (new screen, with customer picker and priority) |
| Catalogue (watch price list and movements) | missing | More > Catalogue, 2 (new, read-only) |
| Shoe services price list | missing (only inside intake) | More > Shoe services, 2 (new, read-only) |
| Mobile services: Revenue control | missing | More > Revenue control, 2 (new, read-only; no follow-up editing) |
| Accounts | missing | More > Accounts, 2 (new, read-only: user, shop, plan; billing for owners and managers; sign out) |
| Recent jobs | none | Today > Recent (last 3 opened jobs) |
| Mobile services: Jobs & dispatch | More > group > item, 3 | Today tile 1; More > Jobs & dispatch 2 |
| Mobile services: Job pool | More > group > item, 3 | More > Dispatch pool, 2 |
| Mobile services: Lead inbox | More > "Lead inbox & prospects", 3 | More > Lead inbox, 2 |
| Mobile services: Prospects / Board | 3 / 4 | More > Prospects, 2; Board is a tab in Lead inbox, 3 |
| Mobile services: Team | More > group > "Team & commission", 3 | More > Team, 2 |
| Mobile services: Toolkit | More > group > item, 3 | More > Mobile toolkit, 2 |
| Customer Accounts | More > group > "Business accounts", 3 | More > Customer Accounts, 2 (renamed) |
| Quotes (web: /quotes) | More > group > item, 3 | More > Quotes, 2; Today quick action, 1 |
| Invoices | More > group > item, 3 | More > Invoices, 2; Today quick action, 1 |
| Reports | More > group > item, 3 | More > Reports, 2 |
| Inventory (web: Database / Stocktake) | More > group > item, 3 | More > Inventory, 2 |
| New intake | Today +, 2 | Today +, 2; Today quick action, 1 |
| New customer | Customers +, 2 | Today quick action, 1 |
| Point of sale / counter sale | More > group > item, 3 | More > POS / quick sale, 2; Today quick action, 1 |
| Global search | none | Today search box opens Search (jobs, customers, invoices via the search API) |
| Send booking request | none | Today quick action, More > Send booking request |
| Finance report (mobile) | none | More > Finance report (owner) |
| Database (GST, CSV export/import) | none | More > Database (owner) |

Not in the native app yet: Parent Account, Accounts management (team users, plan changes, Stripe/Xero setup, which stay on the web), Stocktake (dropped on purpose).

## Phase 1, batch 1 (parity with the web, from the audits in docs/audit-*.md)

| Item | Where in the app | Status |
|---|---|---|
| Revenue KPIs, "Action needed", inbox alert card | Dashboard tab | done |
| Inbox: tap through to the job/invoice/thread, delete, paging, alert badge on the Inbox tab, card-payment actions | Inbox tab | done (badge counts alerts; the web has no read state) |
| Watch jobs: third-party statuses, customer-visible status note, watch details and tappable contact, assign technician, resend quote, copy approval link, sort and filters | Jobs > Watch Repairs and job detail | done |
| Shoe jobs: details per pair, priced services, add/remove services and pairs, customer-visible note, list search and filters | Jobs > Shoe Repairs and job detail | done (ready-by date edit is not possible on the backend) |
| Invoices: watch and mobile together, type filter, search; quotes sort, search and age filter | More > Invoices, Quotes | done |
| Push notifications | n/a | blocked: no google-services.json in the repo |

## Phase 1, batches 2 and 3

| Item | Where in the app | Status |
|---|---|---|
| Global search | Today search box | done |
| Send booking request | Today quick action, More | done |
| Lead inbox board | More > Lead inbox | done |
| Mobile Finance report and Operations cockpit | More > Finance report (owner) | done |
| Database: GST, CSV export, import | More > Database (owner) | done |
| Toolkit settings, Revenue control follow-up | More > Mobile toolkit, Revenue control | done |
| Customer parity: loyalty, merge, order edit/delete | Customers | done |
| Account safety: remember shop ID, sign-out, delete request, subscription banner and blocking screen | Login, shell | done |
| Intake ticket printing with QR | Job detail menu | done |
| Watch/shoe admin: delete, duplicate, edit customer/watch, create-and-send quote | Job detail | done |
| Mobile job admin: 12 statuses, editor fields, duplicate/delete, Activity, key lookup | Mobile job detail | done |
| Connectivity banner | Top of the app | done (offline write queue not built yet) |
| Offline write queue | n/a | not started |
| Push notifications | n/a | blocked: no google-services.json |

## Phase 2 (watch and shoe)

| Item | Where in the app | Status |
|---|---|---|
| Board (kanban) view with "Move to" status change | Watch Repairs and Shoe Repairs lists, List/Board chips | done |
| Shoe SMS log and resend (job live, current status) | Shoe job detail > Notify customer, History | done |
| Repair jobs CSV export | More > Database (already exports jobs) | already done |
| Prev/next job, saved views, repair queue swipe triage, Niimbot labels, push | n/a | not built |
## Phase 2 (business shell)

| Item | Where in the app | Status |
|---|---|---|
| Shop details edit, email alert preferences, integration health | `OwnerSettingsScreen` | built; needs shell wiring (More > Shop settings) |
| Sales by category, sales CSV, shop activity log | `ReportExtrasScreen` | built; needs shell wiring (More > Sales & activity) |
| Customer Orders import (CSV/Excel, sheet pick, dry run) | Customer orders > Import | done |
| Delete team account (owner) | Team > Delete account | done |
| Team entry for watch/shoe-only shops | More | needs shell wiring |
## Phase 2: mobile services dispatch

| Item | Where in the app | Status |
|---|---|---|
| SLA chips (Late / At risk / Unscheduled aging) | Dispatch list, Jobs list cards | done |
| Technician lanes and risk-first sort | Dispatch (lane chips from the team list; Unassigned lane) | done |
| Day-before reminders to tomorrow's customers | Dispatch > Send tomorrow's reminders | done |
| Pool auto-refresh every 30 s, ring headings | Dispatch pool | done |
| Service area (base address and ring radius) | Dispatch pool > Service area (owner/manager) | done |
| Optimise driving order, save or clear visit_order | Today's route | done |
| Pending booking request banner | Jobs board, Dispatch (Dispatch needs shell wiring) | done |
| Push for new pool jobs or requests | n/a | blocked: no google-services.json |
