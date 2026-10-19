# Cross-cutting parity audit: web/Capacitor (phone) vs native Android

Scope: backend coverage, settings/owner functions, offline, auth/session, platform features, role and plan gating.
Read-only audit. Web = `/home/user/watch-repair-app/frontend/src` (WEB). Native = PR #48 worktree `/tmp/native-wt/apps/mainspring-native-android/app/src/main/java/au/mainspring/nativeapp` (NAT).
Status: MATCH, PARTIAL, MISSING, NATIVE-ONLY. "(unsure)" marks things I could not fully confirm.

Method note: web endpoints were extracted by regex from every `api.get/post/put/patch/delete(...)` call under `frontend/src`; native endpoints from every Retrofit annotation (including multi-line ones and the `{resource}/{id}/messages` and `shop-mobile-bookings/{id}/{action}` generic paths). The diff was then hand-checked, so false positives from path templating were removed. Stocktake, minit/HQ, platform-admin, parent-account, signup/checkout and marketing were skipped as asked.

Context that explains several rows: the Capacitor build hides billing UI by design (`AccountsPage.tsx:364` plan switcher and `:1221` billing portal are `!isNativeApp`; `AppShell.tsx:82,105` hide "Add card"/"Fix billing"), disables the service worker (`main.tsx:24`), and has no Android App Links. The web service worker never caches JSON API responses (`public/sw.js:73-74`), so the Capacitor build has no offline reads either.

## A. Backend route coverage (phone-relevant web calls that native never makes)

| # | Web call | Web use | Native | Status |
|---|---|---|---|---|
| A1 | `GET/PUT/DELETE /me/repair-queue-day` | `lib/api/index.ts:1340-1352`, `components/RepairQueueModal.tsx:254,319` (per-user "done today" ids, queue order and stats saved per shop day) | No call. `RepairQueueViewModel.kt:1-60` keeps progress in memory only (`advanced`, `skipped`, undo stack), so reopening the queue loses it and it does not sync to the web | MISSING |
| A2 | `POST /auto-key-jobs/bulk-status` | `pages/AutoKeyJobsPage.tsx:199-206` (multi-select, set status for many mobile jobs) | No bulk selection; status is per job (`AutoKeyJobsViewModel.kt:38`) | MISSING |
| A3 | `POST /auto-key-jobs/invoices/{id}/xero/retry` | `pages/AutoKeyJobDetailPage.tsx:350-355` | Watch-invoice retry exists (`api/InvoiceExtrasApi.kt:43`, `ui/screens/InvoiceDetailScreen.kt:111-120`); no retry for mobile-service invoices (`MobileFinance*` has no Xero code) | MISSING |
| A4 | `GET /auto-key-jobs/quote-suggestions` | `lib/api/index.ts:3632-3635`, `pages/autoKey/NewAutoKeyJobModal.tsx:201` (server price suggestions by job type, key quantity and pricing tier) | Not called. Native uses a hard-coded list `MOBILE_QUICK_ITEMS` and `QuoteBundle` presets (`MobilePresets.kt:5-37`), so shop-specific pricing tier is ignored. Hard-coded 'mirrors web quick-item catalogue' comment | PARTIAL |
| A5 | `GET /prospects/contact-details`, `GET /prospects/collector-status` | `lib/api/index.ts:3750-3752`, `pages/ProspectsPage.tsx` (fetch phone/website for a found business, show lookup quota) | Native has `prospects/search`, `categories`, `leads` (`api/LeadsApi.kt`) but no contact-details or quota call | MISSING |
| A6 | `DELETE /prospect-leads/{id}` | `pages/ProspectBoardPage.tsx:75-77` | No delete in `MainspringApi.kt:51-54` (list/create/update/advance only) | MISSING |
| A7 | `GET /shoe-repair-jobs/shoes`, `PATCH /shoe-repair-jobs/shoes/{id}` | `pages/ShoeJobDetailPage.tsx:170,264` (list a customer's shoes, edit a shoe) | Only `POST shoes` and link/append/remove (`MainspringApi.kt:80-85`). I did not find a list or edit of an existing shoe record (unsure whether the shoe list comes from another endpoint) | PARTIAL |
| A8 | `POST /custom-services` | `components/WatchServicePicker.tsx:45-53`, `components/ShoeServicePicker.tsx:91-99`, `lib/api/index.ts:2921` (add a custom service inline at intake) | Read only (`MainspringApi.kt:107-108`) | MISSING |
| A9 | `GET /watch-catalogue/movements/{key}/quote` | `pages/JobDetailPage.tsx:611-615` (apply a movement's service quote to a job) | Not called; `CatalogueScreen.kt` browses movements but cannot apply the quote | MISSING |
| A10 | `GET /repair-jobs/export.csv` | `pages/JobsPage.tsx`, `lib/api/index.ts:3084` | Not called (native has sales exports via `reports/export/*` and `DatabaseApi`, not the job CSV) | MISSING (low) |
| A11 | `GET /network-link-requests`, `POST .../accept`, `.../decline` | `components/NetworkLinkRequestsBanner.tsx:22-45` (owner banner mounted in `AppShell.tsx`) | Not called | MISSING (owner only) |
| A12 | `GET/POST/DELETE /tenant/api-keys`, `/tenant/webhooks` | `components/TenantQolSettings.tsx:126-160`, mounted at `pages/AccountsPage.tsx:578` | Not called | MISSING (low on a phone) |
| A13 | `GET /billing/xero/status`, `GET /billing/xero/connect`, `POST /billing/xero/disconnect` | `pages/AccountsPage.tsx:1046-1160` | `xero_connected` shown read-only (`AccountsScreen.kt:57`) from `billing/limits`; no connect or disconnect | MISSING |
| A14 | `POST /billing/connect/account-link`, `POST /billing/connect/refresh` (Stripe payouts) | `pages/AccountsPage.tsx:931-1040`, plus the owner nudge `AppShell.tsx:121-175` | `OwnerSettingsScreen.kt:~44` shows "Finish setup on the web"; no link or refresh | MISSING |
| A15 | `GET /billing/portal-url`, `PATCH /auth/session/plan`, billing checkout | `AccountsPage.tsx:251-266,364,1221` | Not called, and the web hides them in the Capacitor build | MATCH (by design) |
| A16 | `PATCH /reports/auto-key/cockpit/target` | `lib/api/index.ts:3622`, `pages/autoKey/MobileOperationsCockpit.tsx:291` (owner edits weekly target) | Target is shown read-only (`MobileFinanceReportScreen.kt:102`) | MISSING (low) |
| A17 | `GET /shop-mobile-bookings/suggest-operator`, `GET /shop-mobile-bookings/{id}` | `lib/api/index.ts:1153,1163` | Native lists operators (`MainspringApi.kt:48`) and does accept/decline/cancel through the generic action path (`MainspringApi.kt:50`, `BookingViewModel.kt:47`); no operator suggestion | PARTIAL (low) |
| A18 | Messages threads (`{resource}/{id}/messages`), attachments upload/list/download-link, bookings create/accept/decline/cancel, customers merge, loyalty, card-payment-issues, quotes, invoices, dispatch/route, toolkit, customer-orders import, CSV import, export-my-data, notification prefs, shop identity, users CRUD, device register | web `lib/api/index.ts` | Present in `api/*.kt` (e.g. `MainspringApi.kt:22,87,124,211,220`, `OwnerAdminApi.kt`, `TeamViewModel.kt`) | MATCH |
| A19 | Web api-layer functions with no page caller: `job-templates`, `repair-jobs/{id}/intake`, `stock/items/{id}`, `auth/bootstrap` | `lib/api/index.ts:3087,1365` | Not called | Not a gap (dead on web, unsure on `stock/items/{id}`) |

## B. Settings and owner functions

| # | Function | Web | Native | Status |
|---|---|---|---|---|
| B1 | Shop details (ABN, phone, email, payment instructions, logo link, brand colour) | `AccountsPage.tsx:614-700` `ShopIdentityCard` | `OwnerSettingsScreen.kt:30-78`, `OwnerSettingsViewModel.kt:55-72` (manager+, same `/settings/shop-identity`) | MATCH |
| B1b | Region AU/NZ and Minit shop number in the same card | `AccountsPage.tsx:~620-700` | Fields not exposed (`ShopIdentityUpdate` in `OwnerAdminApi.kt:46-53`). The screen footnote says name, address, currency and timezone are "changed from the web app"; I did not find those fields on the web card either (unsure), so the note may be misleading | PARTIAL (low) |
| B2 | Dispatch base location and ring radius | `AccountsPage.tsx:806-858` | `DispatchPoolScreen.kt:36` (`baseOpen`, manager+) | MATCH |
| B3 | Team users: add, change role, active/inactive, delete | `AccountsPage.tsx:83-260,476-580` (owner/platform_admin) | `TeamScreen.kt:33-72`, `TeamViewModel.kt:36-82` (owner only via `canManageTeam`, `TokenStore.kt:124`); also adds commission rules (web has this on `MobileServicesTeamPage`) | MATCH |
| B4 | Services and pricing (watch catalogue, shoe services) | `CataloguePage`, `ShoeServicesPage` | `CatalogueScreen.kt`, `ShoeServicesScreen.kt` (other audit areas); custom-service creation missing (A8) | PARTIAL |
| B5 | Custom fields | Per-job values only (`lib/api/index.ts:3094-3099`, `components/JobCustomFields.tsx`); I found no definition editor on web | `ui/CustomFieldsCard.kt`, `api/CustomFieldsApi.kt:22-24` | MATCH |
| B6 | SMS and email templates | No template editor on web and no template routes in `backend/app/routes` | None | MATCH (nothing to match) |
| B7 | Xero connect | `AccountsPage.tsx:1046-1160` | read-only flag only | MISSING (see A13) |
| B8 | Stripe Connect payouts + owner payout nudge | `AccountsPage.tsx:931-1040`, `AppShell.tsx:121-175` | read-only health row `OwnerSettingsScreen.kt:~44`; no nudge | MISSING (see A14) |
| B9 | Subscription: trial and past-due banner, signup-payment-pending screen | `AppShell.tsx:55-110`, `pages/SubscriptionRequiredPage.tsx` | `ui/SubscriptionBanner.kt:20-60` (copies the same rules), `SubscriptionRequiredScreen.kt`, `MainActivity.kt:~58` | MATCH |
| B10 | Plan and usage display | `AccountsPage.tsx:365-475` | `AccountsScreen.kt:48-66` (plan, modules, usage vs limits, manager only) | MATCH |
| B11 | Email alert preferences (quote approved, invoice paid, SMS reply, digest, weekly and monthly sales) | `TenantQolSettings.tsx:83-119` | `OwnerSettingsScreen.kt:34-50` | MATCH |
| B12 | Integration health | `TenantQolSettings.tsx:170-190` | `OwnerSettingsScreen.kt:55-70` | MATCH |
| B13 | API keys and webhooks | `TenantQolSettings.tsx:126-165` | none | MISSING (A12) |
| B14 | Appearance and theme | `AccountsPage.tsx:860-930` | `MoreScreen.kt` settings dialog (appearance cards) | MATCH |
| B15 | Data export (my data JSON) | `pages/ReportsPage.tsx:257` | `DatabaseViewModel.kt:105`, `api/DatabaseApi.kt:45` | MATCH |
| B16 | Account deletion | public `/delete-account` page, an email-to-support flow (`LegalPages.tsx:118-139`) | `AccountDeletionDialog.kt` builds the same email request, owner only (`AccountsScreen.kt:78`) | MATCH |
| B17 | Mobile toolkit notifications and catalogue | `ToolkitPage.tsx:24,47` | `ToolkitViewModel.kt:25`, `api/ToolkitSettingsApi.kt` | MATCH |

## C. Offline

Native queues (`offline/OfflineWriteQueue.kt:70-75`, `OfflineKinds.ALLOWED`): watch status, shoe status, mobile-job status, watch note, shoe note. Queued only on `IOException` (`OfflineSync.kt:66-95`). Callers: `JobDetailViewModel.kt:145,176`, `JobsViewModel.kt:160`, `ShoeJobsViewModel.kt:88`, `AutoKeyJobsViewModel.kt:38`, `AutoKeyJobDetailViewModel.kt:76`, `ShoeJobDetailViewModel.kt:123,150`. It replays in order with idempotency keys, a stale-write check (`X-Expected-Updated-At` for mobile jobs, base-status compare for watch/shoe), a needs-attention list, "Apply anyway" and a queue screen (`QueuedChangesScreen.kt`), and a per-scope purge on sign-out.

Web queues any POST/PATCH/PUT/DELETE that fails while `navigator.onLine` is false (`lib/api/client.ts:179-193`), into IndexedDB with dead letters and a banner (`lib/offlineQueue.ts`, `components/OfflineQueueBanner.tsx`).

| # | Item | Web | Native | Status |
|---|---|---|---|---|
| C1 | Offline status change (watch, shoe, mobile) and job notes (watch, shoe) | queued | queued, with stale checks | MATCH |
| C2 | Offline mobile-job note | queued (generic) | not queued (`OfflineKinds` has no mobile note; `queueNote` is only called for watch/shoe) | PARTIAL |
| C3 | Offline edits to customers, jobs, quotes, payments, invoices, creates, deletes, photo uploads | Generic queue would replay them (photo multipart would not serialise sensibly; unsure) | Not queued by design (`OfflineWriteQueue.kt:11` "Never payments, invoices, deletes or creates"); the screen shows an error, drafts are kept (`TokenStore.bindDrafts`) | PARTIAL (native is deliberately narrower and safer) |
| C4 | Reads while offline | None. The service worker never caches `/v1/` (`public/sw.js:73-74`) and is off in Capacitor (`main.tsx:24`); only in-memory React Query data | Snapshots only for the mobile Today tabs and mobile job detail (`FieldSnapshots.kt:8-32`, used by `TodayViewModel`, `AutoKeyJobDetailViewModel`). Everything else (watch and shoe lists and detail, customers, quotes, invoices, inbox, search, reports, catalogue, stock) fails with "Cannot reach your shop" | NATIVE-ONLY (better than web for mobile service jobs) |
| C5 | Cold start with no network and a saved login | Keeps the token, boots the shell from the cached session snapshot, retries on `online`/`focus` (`AuthContext.tsx:380-431`) | `AuthViewModel.kt:111-120` sets `loggedIn=false` with "Cannot reach your shop..." so the sign-in screen appears; there is no auto retry on connectivity and no way into the app or the Today snapshot until the network returns (unsure how it behaves if the OS already has the access token cached; code reads as above) | MISSING |
| C6 | Queue indicator and sync-on-reconnect | `OfflineQueueBanner` | `ConnectivityBanner.kt`, `OfflineSync.kt:42-46` (replay on reconnect) | MATCH |
| C7 | Repair queue offline | n/a | `RepairQueueViewModel.kt:51` has an `isOnline` guard (swipes need network) | MATCH |

## D. Auth and session

| # | Flow | Web | Native | Status |
|---|---|---|---|---|
| D1 | Sign in with shop ID, email, password | `LoginPage.tsx:60-95` | `AuthViewModel.kt:64-95`, `LoginScreen.kt` | MATCH |
| D2 | Blank shop ID = multi-site login by email | `LoginPage.tsx:68-72` | `AuthViewModel.kt:76` | MATCH |
| D3 | Remember shop ID | `rememberedShopId.ts`, `LoginPage.tsx:73-76` | `LoginScreen.kt` "Remember shop ID" checkbox | MATCH |
| D4 | Forgot password, reset password, change own password | None on web, and no such route in `backend/app/routes` (only `users.py:192/263` owner create/patch) | None | MATCH (both absent; a gap for the product, not for parity) |
| D5 | Invite acceptance (`/shop-invite/:token`, `/hq-invite/:token`) | `App.tsx:223-224`, `pages/ShopOwnerInvitePage.tsx`; the Capacitor build has no deep links so it opens in a browser | No handler; manifest filters only claim `/auto-key` and `mainspring://booking` (`AndroidManifest.xml:47-60`) | MISSING (low: one-off onboarding, works in a browser) |
| D6 | Multi-shop switching | `BottomTabBar.tsx:59` `switchSite`, `PATCH /auth/session/site` | `AuthViewModel.kt:150-170`, `MoreScreen.kt` "Switch shop", `MainspringAppShell.kt:~234` | MATCH |
| D7 | Token refresh and sign-out revoke | `client.ts:139-175` | `TokenAuthenticator.kt`, `SignOutClient` (`AccountsApi.kt:55-90`, also unregisters push device) | MATCH |
| D8 | Session ended screen ("Welcome back", shop ID prefilled) | none | `AuthViewModel.kt:43-46`, `LoginScreen.kt:100` | NATIVE-ONLY |
| D9 | Biometric/PIN app lock | none (`grep -i biometric` finds nothing in `frontend/src`) | `AppLock.kt`, `MoreScreen.kt` `AppLockSetting`, `MainActivity.kt:53-56` | NATIVE-ONLY |
| D10 | HQ/platform console accounts | full web UI | `ConsoleLandingScreen` sends them to the browser (`MainActivity.kt:55-60`) | PARTIAL (by design) |
| D11 | Password strength | server rules via `users.py:77-86` | native checks only length >= 8 (`TeamViewModel.kt:42`); server will still reject others | MATCH (server enforced) |

## E. Platform features

| # | Feature | Web | Native | Status |
|---|---|---|---|---|
| E1 | Push registration (`POST /me/devices`, token re-sync per sign-in) | `lib/pushNotifications.ts:11-51`, behind `VITE_ENABLE_PUSH` | `PushRegistration.kt`, `DeviceRegistrar.kt`, `PushService.kt`, `PushSetup.kt` (permission prompt, settings row) | MATCH |
| E2 | Push tap routing | opens any path starting with `/` (`pushNotifications.ts:36-42`), including `?tab=messages` for SMS replies (`backend/app/push.py:46-55`) | `PushRoutes.kt:15-29` maps `jobs/`, `shoe-repairs/`, `auto-key/`, `inbox`, `invoices` but strips the query (`substringBefore('?')`), so a customer-SMS-reply push opens the job, not its Messages tab | PARTIAL |
| E3 | Camera and photo upload | `lib/nativeCamera.ts`, `lib/photoUpload.ts` (1600px, intake photos in `NewJobModal`) | `JobPhotosScreen.kt`, `JobPhotosViewModel.kt:86-99`, `PreparedPhoto.kt`; watch and shoe intake photos in `WatchIntakeViewModel.kt`, `ShoeIntakeViewModel.kt`. No photo capture in new mobile-job intake (`MobileIntakeViewModel.kt` has none; photos are added from job detail) | MATCH (mobile intake photo PARTIAL, unsure whether web mobile intake has it) |
| E4 | Niimbot label printing | `lib/niimbot.ts`, `hooks/useNiimbotPrinter.ts`, `PrintWatchIntakeTicketsPage.tsx:15-190`: two labels in one job (WORKSHOP COPY with Dep/Bal line, CUSTOMER COPY), label size auto-detected from RFID, auto-connect to the last printer, offered automatically after intake (`NewJobModal.tsx:585`, `NewShoeJobModal.tsx:453`) | `niimbot/*`: BLE connect, RFID label-size handshake, one single page (`NiimbotPrintDialog.kt:112-113` `session.print(listOf(page))`); no customer copy, no deposit/balance line (`NiimbotLabelData`, `NiimbotLabel.kt:11-21`), only reachable from job detail (`JobDetailScreen.kt:71,135`, `ShoeJobDetailScreen.kt:54,134`), not offered right after intake | PARTIAL |
| E5 | Print intake ticket / invoice | `PrintInvoicePage.tsx`, `Print*IntakeTicketsPage.tsx` (browser print) | `InvoiceSummaryPrint.kt:96` and `IntakeTicketPrinter.kt` via Android PrintManager | MATCH |
| E6 | Deep link: live-booking SMS/email "Accept & quote" | `?accept_booking=` handled in-page (`ShopBookingInbox.tsx:57-67`); no App Links in Capacitor | `BookingDeepLink.kt`, `AndroidManifest.xml:47-60`, `AcceptBookingScreen.kt` | NATIVE-ONLY |
| E7 | Role gating | UI mostly shows everything and relies on the server (`require_roles`, `backend/app/dependencies.py:376-378`); web checks only in a few places (`DatabasePage.tsx:13`, `ToolkitPage.tsx:24,47`, `RevenueControlPage.tsx:71`, `DashboardPage.tsx:218`, `MobileServicesTeamPage.tsx:51`) | `TokenStore.kt:122-126` (`canManageTeam`=owner, `canManageInvoices`=owner/manager, `canWorkJobs`=owner/manager/tech) mirrors the server tiers. Native hides Reports, Database, Finance report, Team, Shop settings, Sales and activity for tech and clerk; blocks writes for clerk (`intake`) the same way the server does (`require_tech_or_above`) | MATCH (native hides more than web, consistent with server) |
| E8 | Feature gating by service line and plan | `App.tsx:238-300` `FeatureGate` for `watch`, `shoe`, `auto_key`, `customer_accounts`, `shop_mobile_booking`; `BottomTabBar.tsx:67-82` | `MoreScreen.kt:34-57` and `serviceTabKeys`/`navTabs` hide tiles by `features`; field-mode nav when `auto_key` and not manager (`MainspringAppShell.kt:116`). No route-level guard in the NavHost (`MainspringAppShell.kt:216-447`), so a stale push or deep link to a gated route would still open it; low risk (unsure) | MATCH (tile-level only) |
| E9 | Search | `GlobalSearch.tsx` | `SearchScreen.kt`, `api/SearchApi.kt` | MATCH |
| E10 | Inbox count badge | `hooks/useInboxCount.ts` | `InboxCountStore.kt` | MATCH |

## Status counts (rows above, A19 excluded)

Total rows 64: MATCH 32, PARTIAL 10, MISSING 18, NATIVE-ONLY 4

## Top gaps a shop would notice (most to least)

1. Cold start without signal bounces to the sign-in screen (C5): `AuthViewModel.kt:111-120`, vs web `AuthContext.tsx:380-431`. A tech opening the app in a cellar or basement cannot reach the cached mobile Today or job snapshots at all.
2. Niimbot prints one label only, with no workshop/customer pair or deposit and balance, and no print prompt after intake (E4): `NiimbotPrintDialog.kt:112-113`, `NiimbotLabel.kt:11-21`, vs `PrintWatchIntakeTicketsPage.tsx`, `NewJobModal.tsx:585`.
3. Repair queue "done today" progress does not persist or sync with the web (A1): `RepairQueueViewModel.kt`, vs `RepairQueueModal.tsx:254,319`.
4. Mobile job pricing uses fixed built-in prices instead of the server's tiered suggestions (A4): `MobilePresets.kt:5-37`, vs `NewAutoKeyJobModal.tsx:201`.
5. No inline "add custom service" and no movement quote apply (A8, A9): `MainspringApi.kt:107-108`, vs `WatchServicePicker.tsx:45`, `JobDetailPage.tsx:611`.
6. No bulk status change for mobile jobs (A2): `AutoKeyJobsPage.tsx:199`.
7. Xero connect/disconnect, Stripe payout setup and its owner nudge, and mobile-invoice Xero retry are web-only (A3, A13, A14): `AccountsPage.tsx:931-1160`, `AutoKeyJobDetailPage.tsx:350`.
8. Push for a customer SMS reply opens the job but not its Messages tab (E2): `PushRoutes.kt:19`, vs `backend/app/push.py:46`.
9. Offline mobile-job notes are not queued although status changes are (C2).
10. Prospect contact lookup and delete, owner network link requests, API keys and webhooks, job CSV export, weekly target edit, invite acceptance (A5, A6, A10, A11, A10/A16, D5): all low volume on a phone.

Native advantages worth keeping in mind: biometric app lock (D9), App Links for booking accept (E6), offline snapshots for mobile service jobs (C4), stale-write protection on queued changes (C1), and a Welcome back screen (D8).
