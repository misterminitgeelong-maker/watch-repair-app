# Native Android vs Web: business-wide and shell audit

Scope: Dashboard, Customers (list, detail, orders, accounts), Quotes, Invoices (detail, print, payments), Inbox, Reports, Database import/export, Accounts, auth/session/multi-site, notifications, subscription gating, changelog, settings/appearance, offline, search, shortcuts, role visibility. Out of scope: Minit HQ, stocktake, platform admin.

Method: read-only comparison of `frontend/src` (pages, AppShell, Sidebar, BottomTabBar, GlobalSearch, banners, `lib/api/index.ts`, `lib/pushNotifications.ts`, `lib/offlineQueue.ts`) and `backend/app/routes` against `apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp` (written as `N/` below). Nothing was run; statuses come from reading code.

Legend. Status: HAS = equivalent behaviour exists, PARTIAL = exists with material gaps, MISSING = not present. Effort (native side, assuming the backend route already exists): S under 1 day, M 1 to 3 days, L over 3 days. Priority is for a shop owner running the business day to day.

Note: the Capacitor build of the web app deliberately hides signup, plan change, "Add card" and "Manage billing" (`isNativeApp` checks in `App.tsx`, `AppShell.tsx`, `AccountsPage.tsx`, `LoginPage.tsx`). Those rows say "Intentional" where native should probably keep omitting them for store-policy reasons.

## Biggest gaps (summary)

1. No push notifications. Backend already sends FCM on inbox events (`backend/app/push.py`, `POST /v1/me/devices`) and the Capacitor build registers tokens (`lib/pushNotifications.ts`); native has no Firebase, no token registration, no `POST_NOTIFICATIONS` permission, no deep-link intent filter.
2. No offline behaviour: no read cache, no mutation queue (web auto-queues every offline POST/PATCH/PUT/DELETE with idempotency keys plus a dead-letter UI), no connectivity banner. Native only keeps drafts and "was it saved?" checkpoints.
3. Inbox is a read-only list: no tap-through to the job/invoice, no delete, no unread badge (`/v1/inbox/count` never called), and no card-payment-needs-attention actions (refund / apply / dismiss), which is money handling.
4. Dashboard shows far less than web: no revenue, gross profit, approval rate, avg/job, billed/outstanding, open-invoice value, overdue-jobs and past-collection alerts, launch checklist, inbox alert card. The data is fetched (`DashboardViewModel` loads `reports/summary` and `reports/widgets`) but only two widget counts are rendered, and only for watch shops.
5. Global search is a local filter of already-loaded jobs. `GET /v1/search` (jobs, customers, invoices) is not used.
6. Session/subscription shell gaps: no trial-days or past-due banner, no `signup_payment_pending` gate, no server-side logout or device-token removal, "Remember shop ID" not persisted, no in-app account-deletion path (web has `/delete-account`; Google Play requires one). Forgot-password does not exist on web either.
7. Owner admin tools missing: shop identity editing, notification preferences, API keys/webhooks, integration health, data exports (jobs/customers/invoices/sales CSV, my-data JSON), GST summary, sales by category, CSV/Excel Database import.
8. Team management is reachable only inside the "Mobile services" group of More (needs `auto_key`), so watch-only or shoe-only owners cannot add or edit staff natively. Team accounts cannot be deleted.
9. Customer records: no merge duplicates, no loyalty panel/points adjust, the "Orders" tab on customer detail is a hard-coded empty state (never loads orders), no sort control, no active/completed job split.
10. Invoices list is watch-only (web merges watch and mobile invoices with type filter and number search); no Xero status/retry or "Pay online"; print is a plain text summary, not the branded invoice with QR. Quotes list lacks sort, age filter (used by dashboard follow-up links) and Resend SMS.

---

## 1. Dashboard

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Landing screen | `DashboardPage.tsx` ("Operations Dashboard") | PARTIAL | `N/ui/screens/TodayHubScreen.kt` ("Today"); job-centric rather than business-centric | M | high |
| Revenue KPI | Hero grid, `reports/summary` | MISSING | Summary fetched in `DashboardViewModel.kt` but never rendered; revenue only in `PeriodReportsScreen.kt` | S | high |
| Gross profit KPI (+ cost-outlier warning) | Hero grid | MISSING | Only in period report | S | med |
| Approval rate KPI | Hero grid | MISSING | Only in `PeriodReportsScreen.kt` funnel | S | low |
| Avg revenue per job KPI | Hero grid | MISSING | Only in `PeriodReportsScreen.kt` | S | low |
| Active jobs total across service lines | Stat card "All Active Jobs" | PARTIAL | "On the bench" / "Mine" / "Ready to collect" strip (`JobsHubViewModel`); no per-service breakdown | S | med |
| Customers count + business account groups | Stat card | MISSING | none | S | low |
| Quotes awaiting action + approval rate | Stat card | PARTIAL | Attention card counts only quotes sent 7+ days (widgets), watch shops only; no draft+sent total | S | med |
| Open invoices count and value | Stat card | PARTIAL | Attention card shows `overdue_invoices_count` only, no value | S | high |
| Outstanding work value | Stat card | MISSING | `financials.outstanding_cents` not displayed | S | med |
| Team and sites / plan chip | Stat card + hero chips | MISSING | Plan/modules only in More and Accounts | S | low |
| Action needed: jobs awaiting go-ahead 14+ days | "Action needed" panel | MISSING | `overdueJobsCount` parsed in `DashboardWidgetsResponse` but unused | S | high |
| Action needed: quotes sent 7+ days | "Action needed" | HAS | `AttentionCard` in `TodayHubScreen.kt`; opens unfiltered Quotes (web deep-links `status=sent&older_than_days=7`) | S | med |
| Action needed: unpaid invoices | "Action needed" | HAS | `AttentionCard`; opens unfiltered Invoices | S | med |
| Action needed: jobs past collection date | "Action needed" | MISSING | `overdueCollectionCount` parsed but unused | S | high |
| "Start follow-up sweep" one-tap route | Dashboard button | MISSING | Needs filter deep-links on Jobs/Quotes/Invoices | M | med |
| Inbox alert summary card | Dashboard card linking to Inbox | MISSING | Dashboard does not call inbox | S | high |
| Commercial Pulse (billed, received, outstanding, margin) | Right column | MISSING | none | S | med |
| Operational Pressure (watch OK-wait, quotes pending, urgent, open invoices) | Right column | MISSING | none | S | low |
| Financial Data Health (cost outliers + review links) | Right column | MISSING | none | S | low |
| Live service queue (recent jobs across services) | "Live Service Queue" | PARTIAL | "Needs your attention" (4 jobs) + Recent (3) in `TodayHubScreen.kt` | S | med |
| Launch checklist (dismissable per tenant) | Dashboard | MISSING | none | S | low |
| "Refresh now" and last-refreshed time | Dashboard | PARTIAL | `RefreshOnResume`; no pull-to-refresh or timestamp | S | low |
| Auto-refresh every 30s | Queries `refetchInterval` | MISSING | Resume only | S | low |
| Money widgets for non-watch shops | Dashboard | MISSING | Widgets gated `"watch" in features`; shoe-only/mobile-only shops get no money alerts | S | med |
| Quick actions (new intake, customer, counter sale, quotes, invoices) | Not on web dashboard | HAS (native extra) | `TodayHubScreen.kt` chips | n/a | n/a |
| Role-aware content | Owner sees team metrics | PARTIAL | New intake hidden when `!canWorkJobs()`; no owner-only tiles | S | low |

## 2. Customers

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| List with server search (name/email/phone) | `CustomersPage.tsx` | HAS | `N/ui/screens/CustomersScreen.kt`, `CustomersViewModel.kt` (debounced `q`, paging 100) | n/a | high |
| Sort (newest/oldest/name A-Z/Z-A) | Select | MISSING | Fixed `full_name asc` | S | low |
| Email/phone/"Added" columns | Table | PARTIAL | Phone and email line; no added date | S | low |
| Add customer | `AddCustomerModal` | HAS | `CustomerEditorScreen.kt` (plus address, duplicate check, checkpoints; better than web) | n/a | high |
| Merge duplicate customers | `MergeCustomersModal`, `POST /customers/merge` | MISSING | No API method or UI | M | med |
| Detail: contact info | `CustomerDetailPage.tsx` | HAS | `CustomerDetailScreen.kt` (plus Call / Email intents) | n/a | high |
| Edit customer | Web only via job detail (`updateCustomer`) | HAS (native extra) | `CustomerEditorScreen.kt` | n/a | n/a |
| Watches list, add, edit | Add only | HAS | `CustomerDetailScreen.kt` + `WatchEditorScreen.kt` | n/a | med |
| Watch job history | Active / Completed / No-go split | PARTIAL | Single paged section, no split | S | med |
| Shoe and mobile job history | `CustomerDetailPage.tsx` | HAS | `historySection` | n/a | med |
| Start new job (watch/shoe/mobile) | "New Job Ticket" | HAS | Buttons with `customerId` preselect | n/a | high |
| Loyalty tier, points, ledger | `LoyaltyPanel` (`GET /loyalty/customers/{id}`) | MISSING | none | M | low |
| Adjust loyalty points (manager+) | `AdjustPointsModal` | MISSING | none | S | low |
| "Orders" tab | Not on web customer page | PARTIAL | Hard-coded empty state "No orders yet" in `CustomerDetailScreen.kt`; never calls `customer-orders`. Misleading: wire to real orders or remove | S | med |
| "Account" tab | n/a | PARTIAL | Repeats contact rows; does not show linked business account | S | low |

## 3. Customer Orders (items ordered in for customers)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Orders by status (to order, ordered, arrived, notified, collected) | `CustomerOrdersPage.tsx` kanban | PARTIAL | `N/ui/screens/CustomerOrdersScreen.kt` status filter chips + list, no board | S | med |
| Change status | Drag between columns | PARTIAL | Tap card, pick status (`setStatus`) | n/a | med |
| Create order (item, customer, supplier, cost, priority, notes) | `OrderModal` | HAS | `NewCustomerOrderDialog` with customer search | n/a | med |
| Edit order fields | `OrderModal` edit | MISSING | Only status changes; `CustomerOrderUpdate` exists in API models | S | med |
| Delete order | `DELETE /customer-orders/{id}` | MISSING | No API method | S | low |
| Priority pill (urgent/high) on cards | `PriorityPill` | MISSING | Saved but not displayed | S | low |
| Import orders from CSV/Excel (dry run, sheet pick) | `ImportModal` | MISSING | none | M | low |

## 4. Customer Accounts (business / B2B)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Account list + search | `CustomerAccountsPage.tsx` | HAS | `N/ui/screens/BusinessAccountsScreen.kt` (feature `customer_accounts`) | n/a | med |
| Summary KPIs (active accounts, credit limit total, billing-cycle mix) | Header cards | MISSING | none | S | low |
| Create account (all fields) | `CreateCustomerAccountModal` | HAS | `BusinessAccountEditorScreen.kt` | n/a | med |
| Edit account | Not evident on web list | HAS (native extra) | `editBusinessAccount/{id}` | n/a | n/a |
| Link / unlink customers | Select + Add, Remove | HAS | `BusinessAccountScreen` search + confirm dialogs | n/a | med |
| Monthly statement preview | "Preview statement" | HAS | `vm.preview()` | n/a | med |
| Generate monthly invoice with GST | Button | HAS | `vm.generate()` with unknown-result guard | n/a | med |
| Account invoice history with lines | Recent invoices | HAS | Account invoices list | n/a | med |
| Download account invoices CSV | `downloadInvoiceCsv` | MISSING | Print summary only | S | low |
| Print account invoice | Not on web page | HAS (native extra) | `printInvoiceSummary` | n/a | n/a |
| Role gating | Server manager+ | HAS | `canManageInvoices()` | n/a | n/a |

## 5. Quotes

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Quote list | `QuotesPage.tsx` | HAS | `N/ui/screens/QuotesScreen.kt` (via More or dashboard chip) | n/a | high |
| Status filter (draft/sent/approved/declined) | Select | HAS | `FilterRow` | n/a | high |
| Sort (created/sent/status/total) and direction | Selects | MISSING | none | S | low |
| Age filter ("older than N days") + URL deep-link from dashboard | `older_than_days` param | MISSING | Needed for the follow-up sweep | S | med |
| Active filter chips + clear all | `MobileFilterBar` | MISSING | none | S | low |
| Create quote (pick job, line items, GST on/inclusive) | `CreateQuoteModal` | PARTIAL | Created from a job via `JobQuotesScreen.kt` + `QuoteComposer.kt` (with drafts); no standalone "New quote" on the Quotes list | M | med |
| Quote detail: totals, line items | Row on list | HAS | `QuoteDetailScreen.kt` | n/a | med |
| Send quote to customer (SMS/email approval link) | Send button | HAS | `QuoteDetailScreen.kt` confirm + `postQuoteSend` | n/a | high |
| Resend quote SMS | `resendQuote` (`POST /quotes/{id}/resend`) | MISSING | No API method | S | high |
| Bulk quote reminders | `POST /quotes/send-reminders` (not in web UI either) | MISSING | n/a | S | low |
| Create invoice from approved quote | "Create invoice" | HAS | `QuoteDetailScreen.kt` (manager+ only) | n/a | high |
| Shoe and mobile quotes | Separate flows | HAS | `MobileFinanceScreen.kt`, shoe `sendShoeQuote` | n/a | n/a |
| Customer signature on quote | Not on web quotes page | HAS (native extra) | `QuoteSignatureScreen.kt` (mobile jobs) | n/a | n/a |

## 6. Invoices, print and payments

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Invoice list (paged) | `InvoicesPage.tsx` | PARTIAL | `N/ui/screens/InvoicesScreen.kt`; watch invoices only (`GET /v1/invoices`); mobile-service invoices only reachable from the mobile job finance screen | M | high |
| Status filter | Chips | PARTIAL | All / Unpaid / Paid | n/a | med |
| Type filter (watch vs mobile) | Chips | MISSING | n/a until mobile invoices are listed | M | med |
| Search by invoice number | MobileFilterBar search | MISSING | none | S | med |
| Customer name on row | Joined from jobs | PARTIAL | Jobs joined from `listRepairJobs(limit=200)`; older invoices show no customer | S | low |
| Invoice detail: totals, line items, payments | `InvoiceDetailPage` | HAS | `N/ui/screens/InvoiceDetailScreen.kt` | n/a | high |
| Record payment (amount) | `PaymentModal` | HAS | Dialog with amount + reference, over-payment blocked, unknown-result guard (`paymentUnknown`) | n/a | high |
| Email invoice to customer | "Email Customer" | HAS | `sendInvoice`, manager+ only | n/a | high |
| Print / PDF | `PrintInvoicePage.tsx` (branded, logo, ABN, status QR) | PARTIAL | `InvoiceSummaryPrint.kt` plain summary via Android print; no logo, ABN header or QR | M | med |
| Xero sync status + retry | `InvoiceDetailPage` (`POST /invoices/{id}/xero/retry`) | MISSING | `SessionResponse` lacks Xero; no API | S | low |
| "Pay online (Xero)" link | `xero_online_invoice_url` | MISSING | field not modelled | S | low |
| Role gating of payments | Server manager+ | HAS | `canManageInvoices()` | n/a | n/a |

## 7. Inbox and in-app notifications

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Inbox event list (quote approved/declined, invoice paid, SMS reply, leads, bookings) | `InboxPage.tsx` | PARTIAL | `N/ui/screens/InboxScreen.kt` shows type, date, summary; first 80 events only, no paging | S | high |
| Tap an alert to open the job / invoice / reply thread | Link with `?tab=messages` | MISSING | Rows not clickable; events carry `entityType/entityId` | S | high |
| Delete (dismiss) an alert | Trash icon, `DELETE /inbox/{id}` | MISSING | none | S | med |
| Alert count badge on nav | `useInboxCount` -> `GET /inbox/count` | MISSING | No badge on Inbox tab in `FloatingTabBar` | S | high |
| Card payment needs attention: refund / apply / dismiss | `CardPaymentActions` | MISSING | none; money handling, owner must use web | M | high |
| Pagination (Older / Newer) | `InboxPage.tsx` | MISSING | none | S | low |
| Customer SMS reply threads | Job messages tab | HAS | `MessageThreadScreen.kt` per job | n/a | high |
| Mobile lead inbox | `LeadInboxPage` | HAS | `LeadHubScreen.kt` | n/a | n/a |

## 8. Push notifications

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Register device for FCM and sync token | `lib/pushNotifications.ts` -> `POST /me/devices`; server `push.py` | MISSING | No Firebase, no `google-services`, no messaging service, no permission in `AndroidManifest.xml` | L | high |
| Runtime notification permission (Android 13+) | Capacitor `requestPermissions` | MISSING | none | S | high |
| Tap notification deep-links to `data.path` | `pushNotificationActionPerformed` | MISSING | No intent filters in manifest; needs path-to-route mapping | M | high |
| Unregister device on sign-out | `DELETE /me/devices` | MISSING | `logout()` only clears local tokens | S | high |
| Per-user email alert preferences | `TenantQolSettings` (`/me/notification-preferences`) | MISSING | none | S | med |
| Notification channels (messages vs money) | n/a | MISSING | would be new | S | low |

## 9. Reports

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Period report (day/week/month/quarter) with previous-period compare | `ReportsPage.tsx` | HAS | `N/ui/screens/PeriodReportsScreen.kt` (`reports/period-summary`), date picker | n/a | high |
| Period CSV export | "Download period CSV" | HAS | SAF save in `PeriodReportsScreen.kt` | n/a | med |
| KPI cards: revenue, cost, gross profit, outstanding | Overview | PARTIAL | Revenue/billed/cost/profit/margin shown; outstanding not shown | S | med |
| Monthly trend charts (jobs opened, revenue; 3/6/12 months) | `getReportsTrends` | MISSING | Only a two-bar current-vs-previous chart | M | med |
| Job status, quote status, shoe status breakdowns | Overview | MISSING | none | S | low |
| Sales funnel | Overview | HAS | "Sales funnel" group | n/a | med |
| Operations: avg turnaround, quote response time | Overview | PARTIAL | Work minutes and avg revenue only | S | low |
| Sales by category with date range and per-category export | `getCategorySummary`, `getExportSalesCsv` | MISSING | none | M | med |
| GST collected summary | `getGstSummary` | MISSING | none (account statement GST only) | S | high |
| Technician leaderboard | `getReportsTechBreakdown` | PARTIAL | Mobile commission per tech in `TeamScreen.kt`; no cross-service leaderboard | M | low |
| Audit log (tenant activity) | `getTenantActivity` | MISSING | none | S | low |
| Exports: jobs, customers, invoices CSV | Export menu | MISSING | none | M | med |
| Export my data (JSON) | `getExportMyData` | MISSING | none | S | low |
| Regional (VSWT) tab | `VswtRegionalReportSection` | MISSING | HQ network feature | n/a | n/a |
| Role gating | Server manager+ | HAS | Native blocks with "Reports require an owner or manager account" and hides the More entry for others | n/a | n/a |

## 10. Database (import / export / catalogue)

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Import watch / shoe / mobile history from CSV or Excel | `DatabasePage.tsx` (`POST /import/csv`) | MISSING | No file picker or API method | L | low (desktop task) |
| Dry-run preview, result summary, error rows | `DatabasePage.tsx` | MISSING | none | M | low |
| Replace existing module data (owner) | `canReplace` | MISSING | none, and risky on a phone | n/a | low |
| Excel sheet-name selection | Input | MISSING | none | S | low |
| Catalogue tab (watch services and prices) | `DatabasePage` tab, `CataloguePage` | HAS | `CatalogueScreen.kt` (read), `ShoeServicesScreen.kt` | n/a | med |
| Data export links | In Reports | MISSING | see Reports | M | med |

## 11. Accounts and settings

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| My name, email, role | `AccountsPage.tsx` | HAS | `N/ui/screens/AccountsScreen.kt` | n/a | med |
| Shop identity view (name, ABN, phone, address, currency, timezone) | `ShopIdentityCard` | HAS (read-only) | `AccountsScreen.kt` and More | n/a | med |
| Edit shop identity (ABN/GST, phone, email, logo URL, brand colour; manager+) | `ShopIdentityCard` (`PATCH /shop-settings`) | MISSING | none | M | med |
| Dispatch base location (mobile) | `DispatchBaseLocationCard` | MISSING | Base address shown read-only | S | low |
| Team list: add account, change role/active | Team table, `AddUserModal` | PARTIAL | `TeamScreen.kt` add/edit/commission, but entry only in "Mobile services" group (needs `auto_key`), owner-only | S | high |
| Delete team account | `deleteUser` | MISSING | none (deactivate only) | S | low |
| Plan usage vs limits | `BillingCard` | HAS | `AccountsScreen.kt` (manager+) | n/a | med |
| Change plan / Stripe checkout / billing portal | `AccountsPage.tsx` | MISSING | Intentional: text says "Change plans and billing from the web app" | n/a | low |
| Stripe Connect payouts (set up / status) | `StripeConnectCard` | MISSING | Owner must use web before card payments settle | M | med |
| Xero connect / disconnect | `XeroConnectCard` | MISSING | Status only (`xeroConnected`) | S | low |
| Notification preferences, scheduled sales reports | `TenantQolSettings` | MISSING | none | S | med |
| API keys, outbound webhooks | `TenantQolSettings` | MISSING | none, desktop task | n/a | low |
| Integration health (Twilio, Stripe, SendGrid, attachments) | `TenantQolSettings` | MISSING | none | S | low |
| Sign out | Sidebar / More | HAS | `MoreScreen.kt`, `AccountsScreen.kt`; local clear only, no `POST /auth/logout`, no device-token delete | S | high |
| Active sessions list / revoke others | `GET /auth/sessions`, `revoke-others` | MISSING | Backend only, not in web UI either | M | low |
| Delete my account / shop (store policy) | `/delete-account` page | MISSING | No in-app path; Google Play requires one | S | high |
| Privacy policy / legal pages | `/privacy`, `LegalPages` | MISSING | No link in app | S | med |

## 12. Login, signup, session, multi-site

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Shop ID + email + password login | `LoginPage.tsx` | HAS | `N/ui/screens/LoginScreen.kt`, `AuthViewModel.login` | n/a | high |
| Email-only multi-shop login (blank Shop ID) | `multiSiteLogin` | HAS | blank slug calls `multiSiteLogin` | n/a | high |
| Show/hide password | Web input | HAS | Toggle in `LoginScreen.kt` | n/a | low |
| Remember Shop ID across launches | `lib/rememberedShopId.ts`, Remember-me checkbox | MISSING | Slug is `rememberSaveable` only (lost on relaunch) | S | med |
| Persistent session | `getRememberMe` | HAS | Tokens persisted in `TokenStore` (encrypted prefs) | n/a | n/a |
| Server URL override | Not on web | HAS (native extra) | "Connection settings" (HTTPS enforced; debug allows localhost) | n/a | n/a |
| Forgot password / reset | Absent on web too | MISSING | Gap in both apps (platform admin resets today) | M (needs backend) | med |
| Signup (create shop) | `SignupPage.tsx` | MISSING | Intentional; Capacitor build redirects to login | n/a | low |
| Signup checkout / trial card | `SignupCheckoutPage.tsx` | MISSING | Intentional | n/a | low |
| Session refresh on 401 | `lib/api/client.ts` | HAS | `TokenAuthenticator.kt` (more careful than web) | n/a | high |
| Session-expired UX, drafts retained | Redirect to login with `next` | HAS | `AuthViewModel` "Your session expired. Sign in again; your drafts are retained." | n/a | high |
| Return to original destination after login | `?next=` | MISSING | No deep links | M | med |
| Reconnecting screen when offline at launch | `AppShell` "Reconnecting to your workspace" + Retry | PARTIAL | Error text and retained tokens; returns to login screen, no Retry button | S | med |
| Post-login loading screen | `PostLoginLoadingScreen` | PARTIAL | `state.loading` only | S | low |
| Switch shop (multi-site) | Header select, bottom bar sheet | HAS | `MainspringAppShell.kt` dialog + `AuthViewModel.switchSite` (`PATCH auth/session/site`) | n/a | high |
| Active shop name shown | Header select | HAS | Wordmark and More | n/a | med |
| Demo mode / guided tour | `LoginPage`, `AppShell` tour | MISSING | Not needed for staff app | n/a | low |
| HQ / platform console landing | n/a | HAS | `ConsoleLandingScreen.kt` (opens web) | n/a | n/a |
| Biometric / app lock | Not on web | MISSING | Tokens in encrypted prefs only | M | med |
| Impersonation return banners | `AdminReturnBanner`, `HqReturnBanner` | MISSING | Out of scope | n/a | n/a |

## 13. Subscription gating and banners

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Subscription-required gate (`signup_payment_pending`) | `SubscriptionRequiredPage.tsx`, `AppShell` redirect | MISSING | `SessionResponse` lacks `signup_payment_pending`; a blocked shop gets raw API errors. Needs a screen "finish setup on the web" plus sign out | S | high |
| Trial days-left banner | `SubscriptionBanner` | MISSING | `subscription_status`, `trial_end` not parsed | S | med |
| Past-due payment banner | `SubscriptionBanner` | MISSING | same | S | high |
| Plan-limit (HTTP 402) message | `getApiErrorMessage` | PARTIAL | Server detail passed through by `userMessage()`; no pointer to upgrade | S | low |
| Feature gating by plan modules | `FeatureGate`, nav filtering | HAS | `features` set drives tabs, More, quick actions | n/a | high |
| Payout (Stripe Connect) nudge | `StripeConnectNudge` | MISSING | none | S | low |
| New-version-available banner | `NewVersionBanner` | MISSING | Needs Play in-app update API | M | low |

## 14. Changelog / what's new

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| "What's new" list (versioned) | Sidebar/bottom bar -> `ChangelogModal` (`data/changelog.json`) | MISSING | No screen; app version not displayed either | S | low |
| App version / build info | `lib/buildInfo.ts` | MISSING | none in More | S | low |
| Install / add-to-home prompt | `useInstallPrompt` | n/a | Not applicable to a native app | n/a | n/a |

## 15. Appearance and settings

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Theme choice | `AppearanceCard`, `ThemeContext` (warm, ink, neutral, dark, minit) | HAS | `ui/DesignPreferences.kt`; More: Calibre, Atelier, Night Workshop, Steel & Amber, Mister Minit | n/a | low |
| Follow system dark mode | Web: manual only | MISSING | No "System" option | S | low |
| Field navigation toggle | n/a | HAS (native extra) | `MoreScreen.kt` | n/a | n/a |
| Brand colour / logo applied in UI | `ShopIdentityCard` accent | MISSING | Not applied | M | low |

## 16. Offline behaviour

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Connectivity banner (offline / back online) | `ConnectivityBanner.tsx` | MISSING | No `ConnectivityManager` use; failures surface as per-screen errors | S | high |
| Offline mutation queue with idempotency keys, replay on reconnect | `lib/offlineQueue.ts`, `OfflineQueueBanner.tsx`, `api/client.ts` | MISSING | none; native relies on checkpoints (`setPendingOperation`) and manual re-check | L | high |
| Dead-letter list / conflict (409) handling | `OfflineQueueBanner` | MISSING | `stale_write` handled for mobile jobs and customer-edit conflicts only | M | med |
| Cached read-only screens / service worker | `main.tsx` service worker, route prefetch | MISSING | No disk cache; lists are blank offline | L | high |
| Draft preservation of in-progress forms | `useIntakeDraft`, `DraftRestoredNotice` | HAS | Encrypted, tenant+user scoped drafts (`TokenStore.bindDrafts`) for intake, quotes, customers, accounts | n/a | high |
| Photo upload retry | `photoUpload.ts` | PARTIAL | `OwnedPhotoFiles`, `JobPhotosViewModel`; manual retry | n/a | med |

## 17. Search

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Global search across jobs, customers, invoices | `GlobalSearch.tsx` (`GET /v1/search`), header icon / Cmd+K | MISSING | Dashboard box filters only already-loaded jobs, plus a link to Customers; no API call, no invoices | M | high |
| Recent searches / recent items | `lib/recentSearch.ts` | PARTIAL | "Recent" opened jobs (3) on dashboard via `RecentItems.kt`; no customer/invoice recents | S | low |
| Search reachable from every screen | AppShell mobile header icon | MISSING | Only on the Today tab | S | high |
| Customer search | Customers page | HAS | server `q` | n/a | high |
| Find-a-tool filter | n/a | HAS (native extra) | `MoreScreen.kt` | n/a | n/a |

## 18. Keyboard and shortcuts

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Cmd/Ctrl+K opens search | `AppShell.tsx` keydown | MISSING | No hardware-keyboard handling (tablet/ChromeOS) | S | low |
| Esc closes search/modals | `GlobalSearch` | HAS | Back gesture / dialog dismiss | n/a | n/a |
| Enter to submit | Forms | PARTIAL | IME actions on login and customer search only | S | low |
| Launcher shortcuts / widgets / share targets | n/a | MISSING | No "New intake" shortcut | S | low |

## 19. Role-based visibility (owner / manager / tech / intake)

Server rules: `require_owner` (billing, users), `require_manager_or_above` (reports, invoice writes, import, shop settings, customer accounts write, loyalty adjust), `require_tech_or_above` (inbox delete, customer-order writes, job operations, QoL settings). Web hides almost nothing by role in navigation and relies on 403s; native hides more proactively.

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Owner: manage team, billing | Accounts page | PARTIAL | `TokenStore.canManageTeam()`; Team hidden for non-mobile shops (see section 11) | S | high |
| Manager: reports, invoices, payments | server only | HAS | `canManageInvoices()` gates Reports, payments, email invoice, create invoice, account invoicing | n/a | high |
| Tech: work jobs | server only | HAS | `canWorkJobs()` | n/a | high |
| Intake role | `intake` is offered in Add Team Account | PARTIAL | `canWorkJobs()` excludes `intake`, so Today "New intake" and the quick action are hidden for intake clerks, and the server's `require_tech_or_above` also blocks job creation. Decide whether intake is meant to create tickets and align web, native and backend | S | med |
| Role refreshed per session | `AuthContext` | HAS | `TokenStore.setSessionRole` on each `session()` load | n/a | n/a |
| Nav items filtered by role | Web: none | HAS | Reports and Team hidden in More | n/a | n/a |

## 20. Other shell items

| Feature | Web location | Native status | Native file or note | Effort | Priority |
|---|---|---|---|---|---|
| Primary navigation | `Sidebar.tsx`, `BottomTabBar.tsx` | HAS | `MainspringAppShell.kt` `FloatingTabBar`; top pill nav at 840dp and wider | n/a | high |
| Invoices / Quotes / Reports reachable from nav | Sidebar | PARTIAL | Only via More or dashboard chips (2 taps) | n/a | med |
| Error boundary per route | `ErrorBoundary` | MISSING | No Compose error fallback | S | med |
| Parent account page (multi-site HQ) | `ParentAccountPage` | MISSING | `multi_site` feature unused; only the site switcher | L | low |
| Network link requests banner | `NetworkLinkRequestsBanner` | MISSING | HQ network feature | n/a | low |
| Deep links (job, quote, invoice) from SMS/email/push | web URLs | MISSING | Manifest has launcher intent only | M | med |
| Crash / error telemetry | Web Sentry | MISSING | No Sentry/Crashlytics found | S | med |
