# Native Android vs Web/Capacitor parity audit: watch core

Scope: Dashboard, Customers, Customer detail, Jobs, Job detail, Catalogue, Quotes, Invoices + detail, Inbox, Reports, Database, Accounts, Customer Orders, Customer Accounts, global search, intake printing, watch intake wizard, app shell / More / settings.
Web root: /home/user/watch-repair-app/frontend/src. Native root: /tmp/native-wt/apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp (PR #48 branch).
Read-only audit. Line numbers are approximate (+/- a few lines). Status: MATCH / PARTIAL / MISSING / NATIVE-ONLY.

## Top gaps (ranked by shop visibility)

| # | Gap | Status | Web | Native |
|---|-----|--------|-----|--------|
| 1 | Quotes list has no "New Quote"; list capped at 100, no load more | MISSING | pages/QuotesPage.tsx:109-240 (CreateQuoteModal), :345 | MainspringAppShell.kt "quotes" route does not pass onNewQuote; QuotesScreen.kt, QuotesViewModel.kt (quotes can only be created from a job via JobQuotesScreen/QuoteComposer) |
| 2 | Jobs: no cost-outlier or past-collection filters; fewer sort options | MISSING/PARTIAL | pages/JobsPage.tsx:50-56, 436-441 | JobsViewModel.kt, ui/screens/JobsScreen.kt |
| 3 | Dashboard: no follow-up sweep, filtered action-needed links, Commercial Pulse / Operational Pressure / Financial Data Health cards | MISSING | pages/DashboardPage.tsx:~610, 619-640, 700-807 | ui/screens/TodayHubScreen.kt, DashboardViewModel.kt |
| 4 | Intake: no print-after-create prompt, no per-watch physical ticket # for multi-watch jobs, no brand autocomplete | MISSING | components/NewJobModal.tsx:523, 596-620, 743 | WatchIntakeScreen.kt, IntakeTickets.kt |
| 5 | Job detail: no copy status link; no set-quote-from-movement; workflow rail not tappable / no step note; attachments image-only | MISSING/PARTIAL | pages/JobDetailPage.tsx:776, 817 (copy link); 1008-1013, 611-624 (movement quote); 573-600 (rail); 1256 (any-file upload) | JobDetailScreen.kt (~100-130 menu); JobPhotosScreen.kt:71 (image MIME only) |
| 6 | Reports: no Job / Quote / Shoe status panels | MISSING | pages/ReportsPage.tsx:~700-790 | PeriodReportsScreen.kt, ReportExtrasScreen.kt, ReportBreakdownPanels.kt |
| 7 | Invoice list: no inline pay / print; invoice print is plain, no QR | PARTIAL | pages/InvoicesPage.tsx:265, 279; pages/PrintInvoicePage.tsx | InvoicesScreen.kt, InvoiceSummaryPrint.kt |
| 8 | Smaller: Stripe payouts setup and Xero connect; What's new; recent searches; Database "replace existing"; network link requests banner; API keys / webhooks; checklist reset | MISSING | pages/AccountsPage.tsx:931-1160; components/NetworkLinkRequestsBanner.tsx; lib/recentSearch.ts; TenantQolSettings.tsx | AccountsScreen.kt, SearchScreen.kt, DatabaseScreen.kt, MoreScreen.kt |

## Per-page detail

### Dashboard (DashboardPage.tsx vs TodayHubScreen.kt)
| Item | Status | Notes |
|------|--------|-------|
| Stat cards (open, ready, overdue etc.) | MATCH | |
| Action-needed list | PARTIAL | Native lists but does not deep-link to filtered job lists (web 619-640) |
| Follow-up sweep | MISSING | web ~610 |
| Commercial Pulse, Operational Pressure, Financial Data Health | MISSING | web 700-807 |

### Customers / Customer detail
| Item | Status | Notes |
|------|--------|-------|
| List, search, open | MATCH | CustomersScreen.kt |
| Detail, loyalty, add watch, new job | MATCH | CustomerDetailScreen.kt, CustomerLoyaltyMergeSection.kt |
| Merge customers | PARTIAL | UX differs |
| Edit customer / edit watch | NATIVE-ONLY | CustomerEditorScreen.kt, WatchEditorScreen.kt |

### Jobs
| Item | Status | Notes |
|------|--------|-------|
| Board and list views, status filter, search | MATCH | |
| Sort | PARTIAL | fewer options |
| Cost-outlier / past-collection filters | MISSING | web 54-56 |
| Active vs Completed split | PARTIAL | web keeps no_go and completed in Active (lib/utils.ts ~54-64); native puts no_go in Completed |
| CSV export | PARTIAL | web ~303 server-side; native JobsScreen.kt:48 builds from loaded rows only |
| Delete | MATCH | |
| Saved views | NATIVE-ONLY | |

### Job detail
| Item | Status | Notes |
|------|--------|-------|
| Status change, details edit, messages, resend | MATCH | |
| Quotes, checklist, photos | MATCH | |
| Copy status link | MISSING | web 776, 817 |
| Set quote from movement | MISSING | web 1008-1013, 611-624 |
| Workflow rail tap + step note | PARTIAL | web 573-600 |
| Attachments | PARTIAL | web 1256 any file; native JobPhotosScreen.kt:71 images only; no size sort |
| Checklist reset | MISSING | |

### Catalogue, Inbox, Customer Orders, Customer Accounts, Invoice detail: MATCH
(CatalogueScreen.kt, InboxViewModel.kt, CustomerOrdersScreen.kt + OrderImportDialog.kt, BusinessAccountsScreen.kt, InvoiceDetailScreen.kt). Business account edit is NATIVE-ONLY.

### Quotes
| Item | Status | Notes |
|------|--------|-------|
| List, open, detail | MATCH | |
| New Quote | MISSING | see top gap 1 |
| Sort / pagination | PARTIAL | |
| Inline actions | PARTIAL | |

### Invoices
| Item | Status | Notes |
|------|--------|-------|
| List, detail, payments | MATCH | |
| Inline pay / print from list | PARTIAL | web 265, 279 |
| Print layout | PARTIAL | no QR |

### Reports
| Item | Status | Notes |
|------|--------|-------|
| Sales, period reports, exports | PARTIAL | sales range and trend months differ |
| Job / Quote / Shoe status panels | MISSING | web ~700-790 |
| Regional Report | UNSURE | applicability not confirmed |

### Database
Import MATCH. "Replace existing" MISSING (likely deliberate). Exports NATIVE-ONLY.

### Accounts / settings
| Item | Status | Notes |
|------|--------|-------|
| Shop identity fields | PARTIAL | |
| Stripe payouts, Xero connect | MISSING | web 931-1160 |
| API keys / webhooks | MISSING | TenantQolSettings |
| Plan checkout | N/A | hidden in native builds |
| Dispatch / route / toolkit, push, app lock, offline queue | NATIVE-ONLY | |

### Global search
Core MATCH. Recent searches MISSING (lib/recentSearch.ts).

### Intake and printing
Core wizard MATCH. QR targets PARTIAL. Print-after-create prompt, per-watch ticket #, brand autocomplete MISSING. Niimbot BLE label printing NATIVE-ONLY.

### App shell / More
What's new MISSING; network link banner MISSING; stocktake intentionally ignored.

## Caveats
Regional Report applicability unknown; Database replace-existing probably deliberately omitted; line numbers approximate; this file is a condensed rendering of the audit findings.
