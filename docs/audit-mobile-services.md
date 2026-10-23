# Audit: Mobile Services (auto-key) - Web vs Native Android

Scope: web `frontend/src/pages` (AutoKeyJobsPage, AutoKeyJobDetailPage, JobPoolPage, RevenueControlPage, MobileServicesTeamPage, ProspectsPage, ProspectBoardPage, LeadInboxPage, ToolkitPage, ShopMobileBookingsPage, public Mobile* pages, KeyEnquiryPage, `pages/autoKey/*`, `components/ShopBookingInbox`, `MobileServicesMap`, `mobile/*`) vs native `apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp` (`ui/screens`, `*ViewModel.kt`, `api/MainspringApi.kt`, `api/RevenueApi.kt`).

Legend: HAS = parity for the field workflow; PARTIAL = exists but reduced; MISSING = no native UI (an API method may exist). Effort S/M/L. Priority is for a solo or small-team mobile locksmith owner.
Native paths are relative to `apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp/`. Web paths are relative to `frontend/src/`.

## 1. Job board and dispatch (AutoKeyJobsPage + autoKey/*)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Job list with search | pages/AutoKeyJobsPage.tsx (list layout) | HAS | ui/screens/AutoKeyJobsScreen.kt, AutoKeyJobsViewModel.kt (`/auto-key-jobs/page`, debounced search, load more) | - | high |
| Active / Completed / All directory | AutoKeyJobsPage `jobDirectoryView` | HAS | AutoKeyJobsScreen.kt FilterRow | - | high |
| Focus filters (today, unscheduled, unassigned, needs quote, completed-unpaid) | AutoKeyJobsPage `focusFilter`, MobileOperationsCockpit queues | HAS | AutoKeyJobsScreen.kt (5 chips) | - | high |
| Filter by status / status category / technician / older-than-days / date drill | AutoKeyJobsPage `statusFilter`, `categoryFilter`, `techFilter`, `olderThanDays`, `dateDrill` | MISSING | List only has directory + focus + day. No tech, status or category filter | S | med |
| Schedule-by-day (date picker, prev/next day) | AutoKeyJobsPage dispatch date | HAS | AutoKeyJobsScreen.kt (`day`, `shiftDay`, DatePickerDialog) | - | high |
| Kanban board | AutoKeyJobsPage board, `AUTO_KEY_KANBAN_COLUMNS` | PARTIAL | ui/screens/MobileWorkBoardScreen.kt `MobileKanbanScreen`: 7 coarse columns, read-only. No per-status columns, no tech filter | M | med |
| Kanban drag to change status | AutoKeyJobsPage KanbanBoard `onStatusChange` | MISSING | Open job then change status (acceptable on phone) | M | low |
| Bulk select + bulk status change | AutoKeyJobsPage `bulkAutoKeyJobStatus` | MISSING | No API method or UI | M | low |
| Today cockpit (late / today / unscheduled queues, week money, capacity, follow-ups, week-at-a-glance, weekly target) | pages/autoKey/MobileOperationsCockpit.tsx, MobileTodayWorkspace.tsx; `getAutoKeyCockpit`, `setAutoKeyWeeklyTarget` | PARTIAL | ui/screens/TodayScreen.kt + TodayViewModel.kt (tabs active/quote/booked/completed; today + unscheduled via `/page` focus). No late-run detection, money, capacity, targets, follow-up tiles | M | high |
| Run sheet "Next on the road" | MobileTodayWorkspace run sheet | HAS | ui/screens/DispatchScreen.kt (TodayViewModel, nextFieldJob) | - | high |
| Complete job from run-sheet card | MobileTodayWorkspace confirm complete | PARTIAL | Via job detail next-action button only | S | low |
| Dispatch view (day resource lanes by tech, tech filter, sort by time/risk, unscheduled column) | AutoKeyJobsPage `view==='dispatch'`/planner, dispatchHelpers.ts | MISSING | DispatchScreen is a today list: no technician lanes, no reassign, no risk sort | L | med (high if multi-tech) |
| SLA chips (late / at risk) | pages/autoKey/SlaChipBadge.tsx, dispatchHelpers `computeSlaChip` | MISSING | Not computed anywhere | S | med |
| Week planner / calendar | AutoKeyJobsPage `view==='week'`, WeekGridCells.tsx | PARTIAL | MobileWorkBoardScreen.kt `WeekPlannerScreen`: 7-day grid, tech filter, unscheduled strip, move via slot-tap or typed time, uncertain-write recovery. No drag, no assign-on-drop | M | high |
| Reschedule job | Detail page `scheduleMut`; planner drag | HAS | WeekPlannerScreen `Move` + WeekPlannerViewModel.move; MobileEditorScreen booking field | - | high |
| Map view (pins for day / week / month, tech filter) | AutoKeyJobsPage `view==='map'`, components/MobileServicesMap.tsx | PARTIAL | ui/screens/RouteScreen.kt: today only, device geocoding, Google MapView if `MAPS_CONFIGURED`, Navigate per stop. No range, no tech filter | M | med |
| Optimise driving route + persist visit_order | MobileServicesMap `optimizeDrivingRoute`, AutoKeyJobsPage visit_order | PARTIAL | RouteScreen honours saved `visit_order` but cannot optimise, set or clear it | M | high |
| Navigate to address | Detail "Get Directions"/"Nav" | HAS | AutoKeyJobDetailScreen.kt (geo: intent), RouteScreen.kt (Google Maps directions) | - | high |
| POS / quick sale (cart, quick items, OEM pricing picker, per-item discounts, B2B link, link to job, quote-only mode) | pages/autoKey/POSView.tsx, posQuickItems.ts, posDiscount.ts | PARTIAL | ui/screens/CounterSaleScreen.kt + CounterSaleViewModel.kt, QuoteComposer.kt (quick items, discounts, GST), PricingPicker.kt. No "link to existing job" or quote-only checkout mode | M | med |
| Finance report (money, after-commission, conversion, ageing, trend, tech performance, CSV export) | pages/autoKey/MobileFinanceReport.tsx, `getAutoKeyFinance`, `downloadAutoKeyFinanceExport` | MISSING | PeriodReportsScreen.kt is a shop-wide period summary, not mobile-specific. `mobileCommission` only used in Team | L | med |
| Auto-key reports tab (KPIs, jobs by type/tech, week-on-week) | AutoKeyJobsPage reports view, `getAutoKeyReports` | MISSING | No call | M | low |
| New job (full create form) | pages/autoKey/NewAutoKeyJobModal.tsx | PARTIAL | ui/screens/MobileIntakeScreen.kt (job type, customer existing/new, billing account, vehicle, address, booking, tech, priority, deposit, initial status, booking SMS, draft + uncertain-write recovery). Missing: vehicle-DB autofill, address autocomplete, auto quote suggestion, "use last job vehicle", additional services | M | high |
| Send booking request SMS (customer self-fills vehicle/date via link) | pages/autoKey/SendBookingRequestModal.tsx, `createAutoKeyQuickIntake` | MISSING | `postAutoKeyQuickIntake` is declared in MainspringApi.kt but no screen uses it | S | high |
| Day-before reminders to tomorrow's customers | AutoKeyJobsPage + hooks/useAutoKeyDayBeforeReminders | MISSING | No API method | S | med |
| Job card quick actions in list (status, assign tech, send quote, invoice, delete) | pages/autoKey/AutoKeyJobCard.tsx | PARTIAL | List card opens detail only; actions live in detail | S | low |
| Delete job | AutoKeyJobDetailPage `deleteMut`, JobCard | MISSING | No delete API method | S | low |
| Offline snapshot of job / list | n/a on web | HAS (native-only) | AutoKeyJobDetailViewModel offlineSnapshot, FieldSnapshots.kt | - | - |

## 2. Job detail (AutoKeyJobDetailPage)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Header: job number/title, customer, vehicle, status pill, journey progress | AutoKeyJobDetailPage header | HAS | ui/screens/AutoKeyJobDetailScreen.kt (`JourneyProgress`, FieldJourney.kt) | - | high |
| Call customer | detail customer card | HAS | AutoKeyJobDetailScreen.kt (ACTION_DIAL) | - | high |
| En Route one-tap with confirm | status select | HAS | AutoKeyJobDetailScreen.kt `pendingStep`/`confirmEnRoute`, `initialStatus=en_route` deep link | - | high |
| On Site one-tap | status select | HAS | same, `pendingStep="on_site"` | - | high |
| Finish work (completion note; may auto-create invoice and notify) | `handleStatusChange` (work_completed feedback) | HAS | same, `finishing` then jumps to Financial tab. Does not surface the `invoice_created` / skip-reason message | S | high |
| Full status picker with note | Status Select | PARTIAL | statusPicker dialog uses `AUTO_KEY_JOB_STATUS_OPTIONS` (WatchJobStatuses.kt). Raw status keys shown; lacks `booking_on_hold`, `booking_completed` vs web `MOBILE_STATUS_OPTIONS` | S | med |
| Stale-write protection on status (X-Expected-Updated-At) | n/a | HAS (native-only) | AutoKeyJobDetailViewModel.setStatus | - | - |
| Tabs: Info / Vehicle & Key / Financial / Photos / Messages | detailTab | HAS | AutoKeyJobDetailScreen.kt PillChip tabs | - | high |
| Activity tab (event log) | `listAutoKeyJobActivity` | MISSING | No API method | S | med |
| Customer/job info panels, requested work, schedule, address | Info tab | HAS | MobileInfoPanels | - | high |
| Edit job details (title, address, schedule, vehicle, key, notes) | Info/Vehicle inline edits | HAS | ui/screens/MobileEditorScreen.kt (MobileEditorViewModel, versioned PATCH, local draft) | - | high |
| Edit job type, priority, deposit, additional services | Info tab / new-job modal | MISSING | Editor lacks `job_type`, `priority`, `deposit_cents`, `additional_services_json` | S | med |
| Assign / change technician | Assign tech select | HAS | MobileEditorScreen technician dialog | - | high |
| Change B2B billing account | Customer Account select | HAS | MobileEditorScreen account dialog | - | med |
| Job source (commission lead-source tier) | `leadSourceMut` | MISSING | `commission_lead_source` is modelled but not editable | S | med (high if paying commission) |
| Custom fields | components/JobCustomFields.tsx | MISSING | No support | M | low |
| Duplicate job | `cloneAutoKeyJob` | MISSING | No API method | S | med |
| Vehicle and key details view | Vehicle & Key tab | HAS | AutoKeyJobDetailScreen.kt vehicle tab | - | high |
| Vehicle knowledge: AKL complexity, known issues, recommended tools, cutting profiles | `getVehicleJobContext`, VehicleAlertBanner, AklComplexityPill | HAS | AutoKeyJobDetailViewModel `vehicleJobContext` + vehicle tab + PreparationPanel. AKL shown as text; no BSU/PIN/dealer badges or alert banner | S | high |
| Vehicle key-database search + apply match to job (key type, chip, blade, notes) | `searchVehicleKeySpecs`, `applyVehicleDbMut`, `/vehicle-key-specs/search` | MISSING | Only `/job-context` is called; no search or autofill | M | high |
| Tech notes | Tech Notes field | HAS | MobileInfoPanels + MobileEditorScreen | - | high |
| Photos: camera + gallery, labels, list, view | Photo Attachments (max 5) | HAS | ui/screens/JobPhotosScreen.kt, JobPhotosViewModel.kt (owned-file upload, uncertain-write recovery) | - | high |
| Messages thread with customer | JobMessageThread, `getAutoKeyMessages` | HAS | ui/screens/MessageThreadScreen.kt (`auto-key-jobs`) | - | high |
| Arrival SMS (time window) | Send arrival SMS modal | HAS | ui/screens/ArrivalMessageScreen.kt, ArrivalMessageViewModel.kt | - | high |
| Work logs (time spent) | none on the mobile-services detail page | N/A | WorkLogsScreen is wired to watch jobs only; web auto-key detail has no work log either | - | - |
| Quotes list and create (line items, GST inclusive/exclusive, catalogue bundles) | Quotes card, POS / CreateQuoteModal | HAS | ui/screens/MobileFinanceScreen.kt + QuoteComposer.kt (`/auto-key-jobs/{id}/quotes`) | - | high |
| Send quote (SMS/email) | `sendQuoteMut` | HAS | MobileFinanceScreen `sendQuote` (no per-channel result text) | - | high |
| View customer's signature on approved quote | QuoteSignatureImage | HAS | ui/screens/QuoteSignatureScreen.kt | - | med |
| Capture signature in person on the phone | none on staff pages (customer signs on public MobileQuotePage / MobileBookingPage) | MISSING (also missing on web staff UI) | No signature pad in native | M | med |
| Quote suggestions by job type/qty/tier | `getAutoKeyQuoteSuggestions` | MISSING | Not called | S | low |
| Create invoice from approved quote | `createInvoiceMut` | HAS | MobileFinanceScreen `createInvoice` | - | high |
| Send invoice, choose channel (text / email / both) | `sendInvoiceMut` channel select | PARTIAL | MobileFinanceScreen `sendInvoice` single call; no channel choice or per-channel feedback | S | med |
| Record payment (cash / card / bank) | Record payment modal (cash/eftpos/bank) | HAS | MobileFinanceScreen payment sheet, `updateMobileInvoice(paid, method)` with uncertain-write recovery | - | high |
| Take card payment / share payment link (customer pays via Stripe checkout on public invoice) | MobileInvoicePage `createPublicAutoKeyInvoiceCheckout`; link sent on completion | PARTIAL | Link goes out server-side via "send invoice"; no copy/share link or QR for pay-on-the-spot | S | high |
| Edit invoice amounts | `editInvoiceMut` | MISSING | `updateMobileInvoice` exists but only used for paid | S | low |
| Xero retry on failed sync | `retryAutoKeyInvoiceXeroSync` | MISSING | No call | S | low |
| Print/save invoice summary | n/a | HAS (native-only) | InvoiceSummaryPrint.kt | - | - |
| Global invoices list / detail | `/invoices` | HAS | ui/screens/InvoicesScreen.kt, InvoiceDetailScreen.kt | - | med |

## 3. Pool, bookings, leads, revenue, team, toolkit

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Dispatch pool list sorted by ring | pages/JobPoolPage.tsx (`GET /pool`) | HAS | ui/screens/DispatchPoolScreen.kt, DispatchPoolViewModel.kt (ring shown per card, no ring group headings) | - | high |
| Claim pool job with confirm; open claimed job | `claimPoolJob` | HAS | DispatchPoolScreen (uncertain-claim recovery) | - | high |
| Pool auto-refresh every 30 s / push for new pool job | `refetchInterval: 30000` | PARTIAL | RefreshOnResume only; no polling or push | M | high |
| Service area / base location setting | JobPoolPage -> /accounts; `POST /settings/dispatch-base-location` | MISSING | No base-location UI | M | med |
| Incoming booking requests from shops: accept / decline with reason | components/ShopBookingInbox.tsx | HAS | ui/screens/BookingRequestsScreen.kt (accept creates job, decline reason, open resulting job) | - | high |
| Accept from SMS/email deep link (`?accept_booking=`) | ShopBookingInbox `accept_booking` param | MISSING | No deep-link handling | S | med |
| Pending-booking banner/badge on the job board | `<ShopBookingInbox />` atop AutoKeyJobsPage | MISSING | Requests reachable via More / Lead hub only; no badge | S | high |
| Shop creates booking request for an operator | pages/ShopMobileBookingsPage.tsx | PARTIAL | BookingRequestsScreen "New request" (draft saved, operator routing option, state chips). No address autocomplete, no `suggest-operator` preview, no job-type select, free-text dates | M | low |
| Cancel own request | `cancelShopMobileBooking` | HAS | BookingRequestsScreen | - | low |
| Revenue control queues (due / scheduled / all) and category chips | pages/RevenueControlPage.tsx | HAS | ui/screens/RevenueControlScreen.kt (+ api/RevenueApi.kt, RevenueControlViewModel) | - | high |
| Revenue control follow-up (owner, snooze, note, mark contacted) | FollowUpModal, `PUT /revenue-control/{key}/follow-up` | MISSING | Rows are read-only; no follow-up API method | M | high |
| Revenue control owner filter + search | `owner`, `search` params | MISSING | API accepts them (RevenueApi.kt) but no UI | S | med |
| Revenue row opens the job | `item.job_id` links | MISSING | `RevenueRow` is not clickable | S | high |
| Team list with role, active state, commission summary | pages/MobileServicesTeamPage.tsx, `/users` | HAS | ui/screens/TeamScreen.kt (+ commission report by period) | - | med |
| Add technician / account | Add technician modal | HAS | TeamScreen TeamEditor (owner/manager gated) | - | med |
| Commission rules edit | "Commission rules" modal | HAS | TeamEditor (retainer, shop/tech/minit rates) | - | med |
| Commission report per tech | `getAutoKeyCommissionReport` | HAS | TeamViewModel / `mobileCommission` | - | med |
| Prospect search (category, state, suburbs, live Google refresh, result filter) | pages/ProspectsPage.tsx | PARTIAL | ui/screens/ProspectsScreen.kt "Find businesses": category, state, free-text suburbs, live flag. No region/suburb picker, no result filter, no remembered filters, no collector-status | M | low |
| Prospect tap-to-call, website, Maps link, "Find contact details" | ProspectResult, `getProspectContactDetails` | MISSING | Phone/website shown as plain text; no actions or contact lookup | S | med |
| Save prospect to board | `saveProspectLead` | HAS | ProspectsScreen -> `saveProspect` | - | med |
| Prospect board stages (new, contacted, visited, onboarded, quote_needed, follow_up_due, won, archived) | pages/ProspectBoardPage.tsx | PARTIAL | Stage chips + advance for 5 statuses; no won/archived handling. List only, no kanban (fine on phone) | S | med |
| Prospect edit (contact, email, notes, visit date) + advance (creates business account at onboarded) | LeadModal `advanceProspectLead` | HAS | ProspectsScreen ProspectEditor (local draft, uncertain-stage recovery) | - | med |
| Visits view (upcoming scheduled visits) | ProspectBoardPage 'visits' | PARTIAL | "Follow-ups today" metric only; no visits list | S | low |
| Remove prospect | `deleteProspectLead` | MISSING | No delete | S | low |
| Lead inbox (inbound/website leads: New, Quote needed, Contacted, Follow-up due) | pages/LeadInboxPage.tsx, `/prospects/leads` | MISSING | Lead hub "Lead inbox" tab is `InboxScreen` (generic `/inbox` activity events), not leads | M | high |
| Create inbound lead manually | AddLeadForm | MISSING | | S | med |
| Lead status change, schedule follow-up, overdue highlighting | LeadCard `update` | MISSING | | S | med |
| Convert lead to business account | `convertInboundLeadToAccount` | MISSING | | S | med |
| Lead routing (website enquiry -> shop/operator) | backend mobile_lead_ingest.py, `inbound_lead` | MISSING | Native has no inbound-lead concept and no push for new leads | M | high |
| Toolkit selection (groups, search, save, discard draft) | pages/ToolkitPage.tsx | HAS | ui/screens/ToolkitScreen.kt, ToolkitViewModel.kt | - | med |
| Toolkit scenario readiness check (missing / optional tools) | `toolkitRecommend` | HAS | ToolkitScreen scenario buttons | - | med |
| Toolkit: customer SMS toggle + dispatch phone | `/toolkit/mobile-notifications` | MISSING | No API method. Controls whether customers get en route / arrival SMS | S | high |
| Toolkit: POS catalogue categories the shop sells | `/toolkit/mobile-catalogue` | MISSING | QuoteComposer reads `pricingMeta` categories but cannot edit enabled categories | S | med |

## 4. Public / customer-facing pages (no native UI expected)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Customer intake form from SMS link (vehicle, date, photos) | pages/MobileJobIntakePage.tsx | N/A (web link) | Owner trigger is the missing "Send booking request" row above | - | - |
| Customer booking confirm + signature | pages/MobileBookingPage.tsx | N/A (web link) | Staff only changes status | - | - |
| Customer quote approve/decline with signature | pages/MobileQuotePage.tsx | N/A (web link); staff view of signature HAS | QuoteSignatureScreen.kt | - | - |
| Customer pays invoice (Stripe checkout) | pages/MobileInvoicePage.tsx | N/A (web link) | See "share payment link" row | - | - |
| Car key enquiry form (public lead capture) | pages/KeyEnquiryPage.tsx -> `mobile_lead_ingest` | N/A (public); owner needs a share link/QR | No "share my enquiry link" in native | S | med |
| Public job status tracking page | `getPublicAutoKeyJobStatus` | N/A | `status_token` is in the model but never shared from the UI | S | low |

## Biggest gaps (ranked)

1. Lead inbox / inbound lead pipeline absent; the Lead hub tab is a different feature (generic activity inbox).
2. Revenue control is read-only: no follow-up, owner, snooze or search, and rows do not open the job.
3. Toolkit notification settings (customer SMS on/off, dispatch phone) and POS catalogue categories are not editable.
4. Vehicle key-database search and autofill (key type, chip, blade, notes) missing; only passive job-context is shown.
5. "Send booking request" quick-intake SMS (API stub unused), day-before reminders, and a pending-booking badge on the job board.
6. Dispatch is a today list: no per-technician lanes, SLA/late flags, route optimisation or visit_order editing; map is today-only.
7. Operations cockpit and mobile finance report (money, capacity, ageing, conversion, CSV) absent.
8. Job admin gaps: activity log, duplicate, delete, job type/priority/deposit edit, commission lead-source, custom fields, invoice channel choice, invoice amount edit, Xero retry.
9. Pool and bookings are refresh-on-resume only (web polls every 30 s); no push for new pool jobs or booking requests; no base-location setting.
10. Prospecting is serviceable but lacks a region picker, tap-to-call/website/Maps actions, contact lookup, delete and won/archive stages.
