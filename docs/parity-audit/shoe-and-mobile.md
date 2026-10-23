# Parity audit: shoe repairs and mobile services (web/Capacitor vs native Android, PR #48)

Read-only audit. Web root: frontend/src (W). Native root: apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp (N).
Line numbers marked "~" are approximate. Statuses: MATCH / PARTIAL / MISSING / NATIVE-ONLY.

## Known gaps checked
| Claim | Verdict | Evidence |
|---|---|---|
| "+ New Quote" is a message only | CONFIRMED | N/ui/screens/QuotesScreen.kt:45,64 (onNewQuote nullable, falls back to info dialog); shell does not pass it. Web W/pages/QuotesPage.tsx ~345 opens CreateQuoteModal (~109). |
| No Xero retry for mobile invoices | CONFIRMED | Web W/pages/AutoKeyJobDetailPage.tsx:27,350-355,1296-1309,1358 (status line + retry). Native: no "xero" anywhere in MobileFinanceViewModel / MobileFinanceScreen / api/MobileFinanceApi. |
| No mobile saved views | CONFIRMED | Web W/pages/AutoKeyJobsPage.tsx:56,127,236,243 (AUTO_KEY_VIEWS_KEY, auto-persisted filters). Native: nothing. |
| Shoe saved views removed | CONFIRMED | Web W/pages/ShoeRepairsPage.tsx:20,492,498. Native N/ShoeJobsViewModel.kt:25,57,67 has plumbing (appSavedViews) but no UI. |
| No shoe bulk actions | REFUTED as a gap | Web ShoeRepairsPage has no bulk actions either. (Mobile auto-key list DOES have bulk, see below, and native lacks it.) |
| No Log work on boards | CONFIRMED for the repair queue / shoe lane | Web W/components/RepairQueueModal.tsx has notes, log work, claim, SMS reminder; native N/ui/screens/RepairQueueScreen.kt + ShoeRepairQueueViewModel.kt do not. |
| (my earlier suspicion) header Add technician / Commission rules missing | REFUTED | Native TeamScreen editor has create, retainer, shop/tech/minit % (N/ui/screens/TeamScreen.kt:85-107). |

## Shoe repairs
| Function | Status | Notes |
|---|---|---|
| Job list, status chips, search, sort | MATCH | ShoeRepairsPage vs ShoeJobsScreen/ShoeJobsViewModel. |
| Saved views | PARTIAL/MISSING | See above (no UI). |
| Inline status change on card | MISSING | Web card has status select; native card is open-only. |
| Delete job from list | MISSING | |
| Photo upload from card | MISSING | Native has photos only in detail. |
| New shoe job (intake) | PARTIAL | NewShoeJobModal vs ShoeIntakeScreen/ViewModel/Workflow. Missing: post-create print prompt. |
| Job detail: status, notes, payments, photos, pickup, SMS | MATCH | ShoeJobDetailPage vs ShoeJobDetailScreen/ShoeJobSections/CounterEditorViewModel. |
| Add pair from existing shoe | MISSING | |
| Per-pair services | MISSING | |
| Edit shoe fields after create | MISSING | |
| Services catalogue (ShoeServicesPage) | MATCH | ShoeServicesScreen/ViewModel. |
| Print intake tickets | PARTIAL | Web PrintShoeIntakeTicketsPage prints customer copy + deposit/balance; native N/ui/IntakeTicketPrinter.kt + niimbot/NiimbotLabel.kt prints a single label, no customer copy, no deposit/balance. |
| Repair queue (shoe lane) | PARTIAL | RepairQueueModal vs RepairQueueScreen: missing notes, log work, claim, SMS reminder, filters, "no update", "checked in". |
| Bulk actions | N/A | Neither side has them. |

## Mobile services / auto-key
| Function | Status | Notes |
|---|---|---|
| Jobs list with search + pager | PARTIAL | AutoKeyJobsPage vs AutoKeyJobsScreen/ViewModel. Web has 16 focus keys, status chips, tech/category/date drill-downs; native has 5 focus keys. |
| Bulk select + set status | MISSING | W AutoKeyJobsPage.tsx:23,204. |
| Saved views | MISSING | See above. |
| Kanban board | MATCH | MobileWorkBoardScreen. |
| Log work on boards | MISSING | |
| Job detail (status flow, notes, photos, call, route) | MATCH | AutoKeyJobDetailPage vs AutoKeyJobDetailScreen/ViewModel. |
| Invoice edit amounts | MISSING | Native cannot edit invoice line amounts after create. |
| Invoice send channel (Text+Email / Text / Email) | MISSING | Native sends with default. |
| Xero status + retry | MISSING | See above. |
| New job (NewAutoKeyJobModal) | PARTIAL | MobileIntakeScreen/ViewModel. Closed on native: server suggested quote (with offline estimate), device-geocoder address suggestions (no Places widget), last-vehicle banner, key spec DB matches, extra services, blade and chip, commission source, salesperson. Still missing: PricingSelector catalogue pick (pricing_ref_id), manual cost field. |
| Create quote | PARTIAL | QuoteComposer exists; the "+ New Quote" entry on Quotes list is a dead-end message. (autoKey/CreateQuoteModal.tsx is unused on web.) |
| Mobile Today run sheet (MobileTodayWorkspace) | PARTIAL/MISSING | Web: per-row Call, Route, Start trip, Arrived, Complete, needs-action queues (MobileTodayWorkspace.tsx:56-58,120,150). Native renders TodayHubScreen; TodayScreen.kt:30 is never called (dead). |
| Dispatch / day planner | PARTIAL | DispatchScreen: no date picker, no Unscheduled list, no inline card actions. |
| Week planner / technician load / conflicts | PARTIAL | Native has Planner select; no technician load or conflict view. |
| Route view | MATCH | RouteScreen/RouteOrderViewModel/RouteFilters. |
| Map | PARTIAL | No week/month range, no multi-stop maps link. |
| POS / counter sale | PARTIAL | CounterSaleScreen: Link-to-Job missing. Payment-method mapping (eftpos vs card) not verified. |
| Finance (MobileFinance) | PARTIAL | See invoice gaps. |
| Finance report | PARTIAL | MobileFinanceReportScreen: no custom range, 13-week trend, commission section, drill-downs. |
| Weekly cash target editor | MISSING | Display only (W MobileOperationsCockpit.tsx:258,271,384). Check: full cockpit is desktop-only on web, so phone impact is low. |
| Revenue control | MATCH | RevenueControlPage vs RevenueControlScreen/ViewModel (queues, owner, search, follow-up, show more all present). |
| Job pool + claim | MATCH | JobPoolPage vs DispatchPoolScreen (refresh, ring grouping, confirm claim). Native adds base-location editor and unresolved-claim recovery (NATIVE-ONLY). |
| Team + commission | MATCH | MobileServicesTeamPage vs TeamScreen; native adds delete and commission report (NATIVE-ONLY extras). |
| Toolkit (tools, scenario check, SMS toggle, dispatch phone, catalogue) | MATCH | ToolkitPage vs ToolkitScreen. |
| Lead inbox (tabs, new lead, status, follow-up, convert, call) | MATCH | LeadInboxPage vs LeadInboxScreen/LeadsViewModel. Native follow-up days parameterised. |
| Prospect search (Find businesses) | PARTIAL | ProspectsPage vs ProspectsScreen: free-text suburbs vs web suburb picker; missing "Get contact details" lookup (web ProspectsPage.tsx:35), Call link, Website link, Google Maps link (:28,29,36), result filter (:112). |
| Prospect board | PARTIAL | ProspectBoardPage vs ProspectsScreen/ProspectBoard.kt: board/list present; missing Visits view (web ProspectBoardPage.tsx ~354), Remove prospect (:251), tap-to-call (:116), maps (:130), website (:144), rating line, View Customer Account button (:244). |
| Shop mobile bookings (create/cancel/accept/decline) | MATCH | ShopMobileBookingsPage vs BookingRequestsScreen/AcceptBookingScreen/SendBookingRequestScreen. Gaps: job type is free text (web picker), no routed-operator preview (native lets you choose operator). |
| Public customer booking/quote/invoice token pages | out of scope | |

## Counts (rows above, excluding N/A and out of scope)
MATCH 11, PARTIAL 16, MISSING 12 (incl. 5 shoe-card/detail items), NATIVE-ONLY extras 2.

## Top gaps by shop impact
1. No Xero status/retry on mobile invoices: W AutoKeyJobDetailPage.tsx:350-355,1358; native MobileFinance* has none.
2. "+ New Quote" is a dead-end: N QuotesScreen.kt:45,64.
3. Today run sheet (Call/Route/Start trip/Arrived/Complete + needs-action) missing; TodayScreen.kt:30 dead: W MobileTodayWorkspace.tsx:56-150.
4. Mobile intake missing key spec DB, extra services, blade/chip, commission source, suggested quote, salesperson, address autocomplete: W NewAutoKeyJobModal.tsx vs N MobileIntakeScreen.kt.
5. Invoice edit amounts and send-channel selector missing.
6. Repair queue lacks log work, notes, claim, SMS reminder, filters: W RepairQueueModal.tsx vs N RepairQueueScreen.kt.
7. Auto-key list: bulk status (W AutoKeyJobsPage.tsx:204), saved views (:127,243), 16 vs 5 focus keys.
8. Shoe: label has no customer copy/deposit/balance; no post-intake print prompt; no add pair/per-pair services/edit fields; no inline status/delete/photo on cards; saved views no UI (N ShoeJobsViewModel.kt:57,67).
9. Prospects: no tap-to-call, maps, website, remove, Visits view, contact-details lookup.
10. Dispatch: no date picker/Unscheduled/inline actions; Map no week/month; no technician load view; POS no Link-to-Job; finance report no custom range/13-week/commission.
