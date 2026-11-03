# Watch Repair and Shoe Repair: Web vs Native Android feature audit

Scope: watch and shoe repair areas only (JobsPage, JobDetailPage, CataloguePage, PrintWatchIntakeTicketsPage, ShoeRepairsPage, ShoeJobDetailPage, ShoeServicesPage, PrintShoeIntakeTicketsPage, StatusPage / ShoeStatusPage, ApprovePage / ShoeApprovePage, CustomerDetailPage, NewJobModal / NewShoeJobModal, RepairQueueModal). Read-only source comparison; nothing was run.

Path shorthand: `W/` = `frontend/src/`; `N/` = `apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp/`; `B/` = `backend/app/routes/`.
Native status: HAS, PARTIAL, MISSING, N/A (not applicable to a native staff app, or web lacks it too). Effort: S about a day or less, M 2-4 days, L a week or more.

## Cross-cutting findings

1. **Native data models are thin.** `RepairJobRead` (N/api/ApiModels.kt) omits fields the backend already returns: `assigned_user_id`, `status_token`, customer phone/email, `customer_note`, `status_changed_at`, watch brand/model, `quote_status`, custom fields. `ShoeRepairJobRead.shoe` / `extra_shoes` are raw `JsonElement` and never rendered. Many MISSING rows are therefore S-sized.
2. **Watch status list is out of date.** `WATCH_JOB_STATUS_OPTIONS` (N/WatchJobStatuses.kt) lacks `at_third_party_for_quoting`, `third_party_quote_approved`, `at_third_party_repairer` and still offers legacy `sent_to_labanda`, `quoted_by_labanda`, `parts_to_order`, `service`.
3. **Assignment mismatch.** Web assigns via `assigned_user_id`; native claim/release writes `claimed_by_user_id` and "Mine" (JobsHubViewModel) checks the claim field. A job assigned on web is not "Mine" on the phone.
4. **No push notifications, no inbox badge.** Manifest declares only INTERNET; `v1/inbox/count` and inbox dismiss unused.
5. **No printing or labels.** Web intake tickets (A4 workshop + customer copy with QR, Niimbot 50x70 BLE labels) have no native counterpart.
6. **Native extras (not on web):** stale-status guard and unknown-result checkpoints on writes, persistent intake drafts, claim/release on shoe jobs, two-way SMS on both trades, tap-to-call/email on customer page, shoe/mobile "new job" from a customer, Edit watch from customer, Today hub with Mine/Ready.
7. **Warranty:** no warranty feature on web for watch/shoe (only shoe guarantee text). Nothing to port.
8. **Bulk actions:** none on web for watch/shoe (bulk status exists only for mobile auto-key). N/A.
9. **Shoe invoices/payments:** web has none either. N/A.

## A. Watch jobs list (JobsPage)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Search jobs | W/pages/JobsPage.tsx search (title, job #, customer) | PARTIAL | N/ui/screens/AtelierJobsScreen.kt client-side over first 200; JobsScreen.kt sends `q`, backend matches title/job # only, not customer | S | high |
| Active / Completed directory with counts | JobsPage toggle | PARTIAL | Hub segments Active/Mine/Ready; no Collected browsing in hub (JobsScreen has a Collected chip) | S | med |
| Status filter | JobsPage select | PARTIAL | JobsScreen 5 chips only; no go-ahead, no-go, awaiting parts, third-party | S | med |
| Board (kanban) view | JobsPage + W/components/kanban/* | MISSING | List only | M | med |
| List view | JobsPage ListView | HAS | JobsScreen, AtelierJobsScreen | n/a | n/a |
| Drag card / per-card status dropdown | KanbanBoard, JobCard | MISSING | Must open job; add long-press "Move to..." | S | med |
| Sort (date, job #, status, priority; asc/desc) | JobsPage selects | MISSING | API supports `sort_by`; VM never sets it | S | low |
| Filter by technician | JobsPage assignee select | MISSING | Only "Mine" (see finding 3) | S | med |
| Cost outliers only | JobsPage checkbox | MISSING | Param not exposed | S | low |
| N+ days in shop filter (7/14/21) | JobsPage select | MISSING | `createdAt` already in model | S | med |
| Past collection date only | JobsPage checkbox | PARTIAL | Hub "DUE TODAY" group includes overdue; status line says "Overdue" | S | med |
| Days in shop / days in status badges | JobCard, ListView | MISSING | Needs `status_changed_at` | S | med |
| Rich card (brand/model, phone, quote $, tech, priority, B2B) | JobCard | PARTIAL | Title, number, customer, status, urgent, due only | S | med |
| Active-filter banner, clear, saved view | JobsPage + W/lib/savedViews | MISSING | State resets | S | low |
| Paging past first page | JobsPage cap notice | PARTIAL | JobsScreen has Load more; hub (JobsHubViewModel) loads 200 per trade with no paging | S | med |
| Export repair jobs CSV | JobsPage (`/repair-jobs/export.csv`) | MISSING | Native only exports period report (PeriodReportsScreen) | M | low |
| Repair Queue (swipe triage, filters, claim, note, log work, resend) | W/components/RepairQueueModal.tsx | MISSING | Closest: Today hub attention list | L | med |
| Log work from list card | JobCard | PARTIAL | Only inside job (WorkLogsScreen) | S | low |
| Delete job | JobsPage ListView | MISSING | None | S | low |
| Jobs/Catalogue sub-tabs | JobsPage header | HAS | More menu (MoreScreen.kt) | n/a | n/a |
| Prev/Next job | JobDetailPage nav neighbours | MISSING | None | S | low |
| New job button | JobsPage | HAS | "+" opens WatchIntakeScreen | n/a | n/a |

## B. Watch job detail (JobDetailPage)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Change status with staff note | StatusModal | HAS | N/ui/screens/JobDetailScreen.kt, JobDetailViewModel.setStatus | n/a | n/a |
| Third-party repairer statuses | JOB_STATUS_ORDER (W/lib/utils.ts) | MISSING | Not in WATCH_JOB_STATUS_OPTIONS | S | high |
| Customer-visible note on status change | StatusModal "Note for customer" | MISSING | `RepairJobStatusUpdate` has status + note only | S | high |
| One-tap next status / workflow rail | STATUS_FLOW, WorkflowRail | PARTIAL | Read-only JobStageStrip (Calibre theme); picker for changes | S | med |
| Suggested quick notes per status | STATUS_STEP_NOTES | MISSING | Static table | S | low |
| Create and send quote in one step | CreateSendQuoteModal | PARTIAL | JobQuotesScreen makes a draft; then open quote and Send | S | high |
| Job quotes list | Quotes card | HAS | JobQuotesScreen | n/a | n/a |
| Quote detail / send | QuotesPage | HAS | QuoteDetailScreen (draft only) | n/a | n/a |
| Resend quote / copy approval link | QuotesPage `/quotes/{id}/resend` | MISSING | No resend call; token not surfaced | S | high |
| Invoice from approved quote | QuotesPage | HAS | QuoteDetailScreen (owner role) | n/a | n/a |
| View/email/print invoice | InvoicesPage, PrintInvoicePage | PARTIAL | InvoiceDetailScreen: email + system print of text summary | M | med |
| Record payment | InvoicesPage Pay modal | HAS | InvoiceDetailScreen | n/a | n/a |
| Deposit / balance outstanding | Details card | HAS | JobDetailScreen footnote, banner, collection checklist | n/a | n/a |
| Edit quote amount | Details pencil | PARTIAL | Via CounterEditorScreen | S | low |
| Set quote from movement DB | MovementAutocomplete | PARTIAL | CatalogueScreen shows RRP read-only; cannot apply to job | M | med |
| Edit ticket (job #, title, notes, priority, collection, deposit, estimate) | EditTicketModal | HAS | N/ui/screens/CounterEditorScreen.kt (+ salesperson, pre-quote, internal notes, parts ETA) | n/a | n/a |
| Edit watch from the job | EditTicketModal | PARTIAL | Only via Customer > Edit watch | S | med |
| Edit customer from the job | EditTicketModal | PARTIAL | Only via Customers > Edit | S | med |
| Watch details on the job (brand, model, serial, movement, condition) | Summary / Edit | MISSING | `getWatch` exists but JobDetailViewModel never loads it | S | high |
| Customer contact on job (call/email) | Details card | MISSING | "Customer & contact" card not tappable; model lacks phone/email | S | high |
| Internal notes edit | InternalNotesCard | PARTIAL | Displayed; edited in long CounterEditor form | S | low |
| Parts ETA | PartsEtaCard | PARTIAL | CounterEditor field; not contextual; no notify | S | med |
| Assign any technician | Details select (`assigned_user_id`) | MISSING | Claim/release for self only | S | med |
| Assign B2B account after intake | Details select | MISSING | Intake only | S | med |
| Intake photos / photo grid | Details, Attachments tab | PARTIAL | JobPhotosScreen: file rows, "Open file", no thumbnails | M | med |
| Upload photo/file with label | Attachments tab | HAS | JobPhotosScreen, one at a time | n/a | n/a |
| Attachment sort | Attachments tab | MISSING | Newest first only | S | low |
| Work logs | Work Logs tab, LogWorkModal | HAS | WorkLogsScreen | n/a | n/a |
| Status history | History tab | HAS | Activity tab | n/a | n/a |
| Standalone shop note | (web: via status note) | HAS | Menu "Add shop note" | n/a | n/a |
| Two-way SMS thread | Messages tab | HAS | MessageThreadScreen (15 s refresh) | n/a | n/a |
| Resend job live / ready / quote SMS, SMS log | Messages tab | HAS | "Notify customer" + Activity | n/a | n/a |
| Copy status link | Header | MISSING | `status_token` not in model; add copy + share sheet | S | med |
| Print intake tickets / Niimbot labels | W/pages/PrintWatchIntakeTicketsPage.tsx | MISSING | A4 via PrintManager is M; BLE labels are the L part | L | high |
| Duplicate job | Header (`/repair-jobs/{id}/clone`) | MISSING | No clone call | S | med |
| Custom fields | JobCustomFields | MISSING | Not modelled | M | low |
| Summary strip: created, days in shop | Header | PARTIAL | Banner shows status/urgent/balance | S | low |
| Claim / release | (web queue) | HAS | JobDetailScreen | n/a | n/a |

## C. Watch catalogue

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Repair services search + category | W/components/WatchCatalogueTab.tsx | HAS | N/ui/screens/CatalogueScreen.kt | n/a | n/a |
| Movement DB search | WatchCatalogueTab | HAS | Movements tab (cap 500) | n/a | n/a |
| Movement purchase cost beside RRP | WatchCatalogueTab | PARTIAL | RRP only; confirm intentional | S | low |

## D. Watch intake wizard (NewJobModal)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| 4-step flow | W/components/NewJobModal.tsx | HAS | N/ui/screens/WatchIntakeScreen.kt, WatchIntakeViewModel.kt | n/a | n/a |
| Existing/new customer | Step 1 | HAS | Same | n/a | n/a |
| Phone-match duplicate warning | Step 1 `phoneMatch` | MISSING | Duplicate customers possible | S | med |
| 1-5 watches, existing or new | Step 2 | HAS | Same | n/a | n/a |
| Brand autocomplete, movement dropdown | Step 2 | PARTIAL | Free text | S | low |
| Per-watch ticket number | Step 2 | PARTIAL | Override only when 1 watch | S | low |
| Catalogue picker with combo pricing | Step 3 | HAS | Flat list (first 30); N/IntakePricing.kt mirrors combos | S | low |
| Priority, status, salesperson, collection, deposit, pre-quote, B2B, override | Step 3 | HAS | Same | n/a | n/a |
| Front/back photos; quick job | Step 4 | HAS | Same | n/a | n/a |
| Tracking SMS skipped warning | Post-create | HAS | N/TrackingWarning.kt | n/a | n/a |
| Draft persistence / offline guard | useIntakeDraft | HAS | Stronger on native | n/a | n/a |
| Print tickets prompt | finishCreate | MISSING | Print gap | L | high |
| Start from customer | CustomerDetailPage | HAS | `watch_intake?customerId=` | n/a | n/a |

## E. Shoe jobs list (ShoeRepairsPage)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Search (job #, title, description, service) | W/pages/ShoeRepairsPage.tsx | MISSING | N/ui/screens/ShoeJobsScreen.kt has no search; hub shows no customer for shoe jobs | S | high |
| Active / Completed with counts | ShoeRepairsPage | MISSING | Flat list; hub has Active/Ready | S | med |
| Status filter | ShoeRepairsPage | MISSING | None | S | med |
| Cost outliers; N+ days in shop | ShoeRepairsPage | MISSING | Not exposed | S | low |
| Board vs Cards view | ViewToggle, SHOE_KANBAN_COLUMNS | MISSING | List only | M | med |
| Rich card (ready-by, complexity, turnaround, pairs, total, deposit, collect, B2B, urgent) | DetailedJobCard / KanbanJobCard | MISSING | Rows show title, number, status; model already has complexity/ready-by | S | med |
| Inline status change on card / drag | DetailedJobCard, KanbanBoard | MISSING | Open job first | S | med |
| Expand services/photos, upload from card | DetailedJobCard | MISSING | Inside job only | S | low |
| Delete job | DetailedJobCard | MISSING | None | S | low |
| Combos and guarantee banner | ComboBanner | PARTIAL | On Shoe services screen, not list | S | low |
| Repair Queue (shoe) | RepairQueueModal | MISSING | None | L | med |
| Paging | (web 500) | HAS | ShoeJobsViewModel pages 200 | n/a | n/a |
| New job button | ShoeRepairsPage | HAS | "+" opens ShoeIntakeScreen | n/a | n/a |
| Services sub-tab | tabs | HAS | More > Shoe services | n/a | n/a |

## F. Shoe job detail (ShoeJobDetailPage)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Change status with staff note | StatusModal | HAS | N/ui/screens/ShoeJobDetailScreen.kt, ShoeJobDetailViewModel | n/a | n/a |
| Customer-visible note on status | StatusModal | MISSING | Same payload gap as watch | S | high |
| Workflow rail one-tap | WorkflowRail SHOE_WORKFLOW_STEPS | MISSING | Picker only | S | med |
| Send/resend quote SMS; quote status | Header | PARTIAL | Menu "Send quote" (hidden once approved); no "Resend" wording or link | S | med |
| Shoe details per pair (type, brand, colour, notes) | ShoeTab | MISSING | `shoe` parsed as raw JSON, never shown | S | high |
| Pair tabs; add/remove pair | Shoes card, AddPairModal | MISSING | `linkShoe`/`createShoe` used only at intake | M | med |
| Services with prices; add/remove services | ServicesCard, AddServicesModal | MISSING | Read-only names; `appendShoeItems` only used at intake | M | high |
| Estimated total, complexity, ready-by, turnaround | Summary | MISSING | Fields in model, not shown | S | med |
| Edit ticket (title, notes, priority, collection, deposit, cost) | EditTicketModal | HAS | CounterEditorScreen (shoe-repair-jobs) | n/a | n/a |
| Edit shoe fields / customer contact | EditTicketModal | MISSING | None | S | med |
| Assign B2B account | Job Info select | MISSING | Intake only | S | med |
| Photos grid, camera, multi gallery upload | Photos card | PARTIAL | JobPhotosScreen, one at a time, no thumbnails | M | med |
| Resend SMS (job live, current status) and SMS log | MessagesCard | MISSING | No shoe sms-log/resend calls (backend has them) | S | med |
| Two-way SMS thread | JobMessageThread | HAS | Messages tab | n/a | n/a |
| History incl. notes | HistoryCard | HAS | History tab | n/a | n/a |
| Add a note | (web: via status) | HAS | Menu "Add note" | n/a | n/a |
| Print intake tickets | PrintShoeIntakeTicketsPage | MISSING | Print gap | L | high |
| Duplicate job | DuplicateShoeJobButton | MISSING | No clone call | S | med |
| Custom fields | JobCustomFields | MISSING | Not modelled | M | low |
| Claim / release | (web kanban shows tech) | HAS | ShoeJobDetailScreen | n/a | n/a |
| Invoice / payment | n/a | N/A | Web has none; native "Quote and invoice" card is informational | n/a | n/a |

## G. Shoe services reference and shoe intake wizard

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Service reference (search, group, price formats, notes) | W/pages/ShoeServicesPage.tsx | HAS | N/ui/screens/ShoeServicesScreen.kt | n/a | n/a |
| Combos and guarantee | ShoeServicesPage | HAS | Same | n/a | n/a |
| Intake flow (customer, pairs/services, details, photos) | W/components/NewShoeJobModal.tsx | HAS | ShoeIntakeScreen.kt, ShoeIntakeViewModel.kt (up to 15 pairs) | n/a | n/a |
| Shoe type dropdown, brand, colour, condition | Step 2 | PARTIAL | Free-text type | S | low |
| Picker filtered by shoe type; complexity/turnaround at pick | ShoeServicePicker | PARTIAL | Flat list, price only | S | med |
| Per-service quantity, agreed price, notes | ShoeServicePicker | HAS | Native fields | n/a | n/a |
| Combo discount / estimated total preview | ShoeServicePicker | MISSING | No total at intake | S | med |
| Multiple photos per pair | Step 2 | PARTIAL | One per pair | S | low |
| Title, priority, status, salesperson, collection, deposit, B2B | Step 3 | HAS | Same | n/a | n/a |
| Print prompt after create | finishCreate | MISSING | Print gap | L | high |
| Tracking SMS warning | Post-create | HAS | shown | n/a | n/a |

## H. Customer detail (CustomerDetailPage)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Contact info | W/pages/CustomerDetailPage.tsx | HAS | N/ui/screens/CustomerDetailScreen.kt (adds call/email) | n/a | n/a |
| Watches list, add watch | AddWatchModal | HAS | Add and Edit (WatchEditorScreen) | n/a | n/a |
| Watch jobs split Active/Completed/No go | Repair Jobs card | PARTIAL | Flat list with status pills, load older | S | low |
| Shoe jobs list | Shoe Repairs card | HAS | historySection | n/a | n/a |
| New watch job for customer | Header | HAS | `watch_intake?customerId=` (+ shoe, mobile) | n/a | n/a |
| Loyalty panel (tier, points, ledger, adjust) | LoyaltyPanel | MISSING | No loyalty API/UI | M | low |

## I. Public and print pages

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Public watch status page | W/pages/StatusPage.tsx | N/A | Customer-facing; staff need "Copy status link" (MISSING above) | n/a | n/a |
| Public shoe status page | W/pages/ShoeStatusPage.tsx | N/A | `statusToken` in shoe model but no UI uses it | S | med |
| Public quote approve/decline (watch with signature; shoe) | ApprovePage.tsx, ShoeApprovePage.tsx | N/A | Native has in-person signature for mobile jobs only; no counter-signing for watch/shoe | M | low |
| Watch ticket print + Niimbot labels | PrintWatchIntakeTicketsPage.tsx | MISSING | See B | L | high |
| Shoe ticket print | PrintShoeIntakeTicketsPage.tsx | MISSING | See F | L | high |
| Invoice print | PrintInvoicePage.tsx | PARTIAL | N/InvoiceSummaryPrint.kt plain summary | M | med |

## J. Search, notifications, cross-cutting

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Global search (customers + jobs) | W/components/GlobalSearch.tsx | PARTIAL | Today search filters loaded jobs; `/search` not wired | M | med |
| Inbox of events | W/pages/InboxPage.tsx | PARTIAL | InboxScreen lists; no unread badge, no dismiss | S | med |
| Push notifications | n/a (web polls) | MISSING | Needs FCM + device token route (B/devices.py exists) | L | high |
| Bulk status | n/a | N/A | Not on web for watch/shoe | n/a | n/a |
| Warranty | n/a | N/A | Not on web | n/a | n/a |
| Role gating | AuthContext | HAS | TokenStore.canWorkJobs(), canManageInvoices() | n/a | n/a |

## Top gaps, in order

1. Add the three third-party statuses (drop legacy) to WATCH_JOB_STATUS_OPTIONS (S).
2. Customer-visible note on status change, watch and shoe (S).
3. Show watch details + customer call/email on watch job; shoe details on shoe job (S).
4. Shoe jobs list: search, status filter, active/completed, richer cards (S).
5. Shoe job: add/remove services and pairs after intake (M).
6. One-step create-and-send quote, resend quote, copy approval link (S).
7. Print intake tickets / labels (L).
8. Push notifications and inbox badge (L).
9. Technician assignment/filter using `assigned_user_id`; fix "Mine" (S-M).
10. Shoe SMS log + resend, copy status link, duplicate job (S each).
