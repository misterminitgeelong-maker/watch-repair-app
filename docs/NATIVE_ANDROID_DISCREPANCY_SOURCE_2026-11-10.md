# Native Android vs web: discrepancy summary (reviewed 10 Nov 2026)

Scope: native Android (Kotlin) on main vs the web app. Static code review only, nothing was run on a device. Sam's SwiftUI iOS app is not in the repo and is NOT covered. HQ, platform admin and stocktake were excluded by decision. Native on main has not changed since the 23 Oct merge (#48); 62 web/backend commits since then have no native counterpart.

Detail files in this folder: 01-watch-repairs, 02-shoe-and-stock, 03-mobile-services, 04-shared-business, 05-engraving-auth-platform, 06-api-and-changelog. The old 14-23 Oct audits are stale: several "missing" items (Xero retry, saved views, run sheet) are now present.

## Fix first (likely broken or misleading today)
1. Dispatch pool screen: backend /v1/pool now redacts customer name, address, plate and description; native model expects them, so blanks or a crash. Web handles it.
2. Two-option (CAS3 vs CAS3++) quotes made on web cannot be resolved or invoiced in native (invoice returns 409). Fix exists only on branch native-two-option-quotes.
3. Inbox shows hq_message / network_message / network_announcement as dead rows; badge counts them but they can't be opened. Push taps for /messages routes open nothing.
4. Watch jobs: native treats no_go as Completed (web keeps Active); price shown on cards/header differs from web (ignores cost); native loads 100 jobs vs web 500, board has no load-more.
5. Shoe jobs in awaiting_parts / quote_sent / awaiting_customer_details / parts_to_order vanish from lists on BOTH web and native (shared defect).
6. Payment methods differ (native card/cash/bank_transfer, web cash/eftpos/bank), so reports mix values.

## Missing entirely on main (and on every branch unless noted)
- Network messaging (Messages page, state hubs, DMs, announcements with receipts, unread badge). Blocker for Minit shops.
- Medal engraving events module (about 5-7 days for full port; 2-3 days for a stall-companion slice).
- Birkenstock shoe fields (model, size, purchase, warranty), purchase lookup, parts card on shoe job, shop parts stock page.
- Parent account page (My Shops, link shop) and booking-only Minit mode.
- Booking requests: routing preview/coverage message, address autocomplete, re-offer state, moved_to_pool status shown raw.
- Mobile services: job list filters (status/tech/category), 11 of 16 cockpit focus keys, editable targets in reports, manual price and catalogue reference on intake.
- Watch: printed tickets lack many fields and use a different QR link; internal notes append-only; front/back intake photos; quote lines all typed "labor"; job templates and condition checklist.
- Platform: no crash reporting (Sentry), no version check/force update.

## Only on unmerged branches
Two-option quotes, Xero disconnect + Stripe payout refresh (native-xero-stripe), API keys + webhooks, address suggestions (intake only), planner zoom, sliding sessions (native-long-session), Play release build (native-play-release / -v2). Note: the Play branches change applicationId to au.mainspring.app, replacing the Capacitor listing; main is still au.mainspring.nativeapp, unsigned, versionCode 1, so it is not Play-ready.

## Other differences
- Role gating: More shows Team/Shop settings to managers but Team actions need owner; several invoice actions are manager-only in native but open to all on web.
- Dashboard tiles use different metrics ("Work value" shows revenue vs outstanding on web). Reports are split over three screens.
- Staff login is email+password with optional Shop ID on both; texted-code login is customer portal only.

## Native is ahead of web
Biometric app lock, BLE Niimbot + PrintManager printing, offline write queue with undo, signature capture, saved views, job delete/claim, route reorder, conflict-detecting editors.

## Unverified
Custom fields, message polling, MovementAutocomplete, status-label mapping, quote job picker, whether booking_only plans reach Inbox, push needing google-services.json at build.
