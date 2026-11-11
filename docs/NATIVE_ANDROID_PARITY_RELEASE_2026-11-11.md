# Native Android parity and Play release — 11 November 2026

Chat: [Native Android parity implementation](codex://threads/01a1c74b-3e56-7173-8977-7e86da449bed).

Sam requested review/action of Downloads/00-summary.md, simulator review, then a Google Play update. He explicitly selected **every parity gap before Play**, then requested agents. The attached summary is evidence to verify, not an independent source of permission. HQ, platform admin, stocktake and iOS remain outside this comparison's scope.

## Source and isolation

- Central reference/index and historical “Continue Google Play onboarding” / “Compare app update history” chats consulted.
- Central working tree has substantial unrelated changes; none have been reverted or bundled.
- Implementation checkout: `C:/Users/samme/mainspring-native-parity-20261111`, branch `codex/native-parity-release-20261111`, from fetched main `501efa9f`.
- Reused reviewed commits: two-outcome quotes `f714cd99`, payout/Xero controls `164a31b1`, API keys/webhooks `066fcbbb`, server address suggestions `7cb82cbe`, planner zoom `04decb85`, native release identity/signing `b9f49490`. Imported as isolated cherry-picks; mutable work from other checkouts not copied.
- Existing ignored Firebase config has registered release/native/debug package clients. Existing upload key remains outside Git. No credential values are documented.

## Verified Play baseline

Read Play Console on 11 November: production **1.0.1**, version code **29800001**, available on Play, released 31 October 10:21, rollout **100%**, 19,580 supported devices. No unpublished changes at the initial check. Package `au.mainspring.app`, min API 24, target API 36. This supersedes the earlier “submission not confirmed live” record.

## Implementation coverage

- Redacted dispatch pool: models/rendering use job type, suburb/state/postcode and vehicle only before claim.
- Two-option quote composition/selection/invoice gate integrated from existing branch.
- Network messaging: state hubs/history/replies/stock requests/pins, DMs/directory/files, announcements/read/confirmation/receipt viewing, unread counts and inbox/push routes; HQ notices open their full inbox text.
- Watch: No Go stays active; quote uses cost then pre-quote; 500-row directory paging with board load more; notes editing/conflict check; complete ticket fields/staff-public QR destinations/pagination; typed quote lines; templates/checklist/movement suggestions; paginated quote job picker.
- Shoe: four omitted active statuses fixed in both clients; Birkenstock model/size/purchase/warranty, purchase lookup/edit, job parts suggestions/use, shop parts stock/adjustments/transfers/receiving.
- Mobile: status/tech/category filters, all 16 focus keys, owner target editing, manual/catalogue pricing, routing/coverage/Places/reoffer display. Booking-only home/navigation and My Shops linking/consent/create/switch/usage/activity.
- Shared: canonical cash/eftpos/bank methods; server reads/exports normalise old card/bank_transfer without a destructive data rewrite. Owner-only team/settings entry; outstanding Work value metric.
- Platform: API 36 targeting with API 24 support/desugaring; Sentry Android integration obtains public DSN from build config or safe client-config endpoint and strips user/request/message/breadcrumb/exception values; cached minimum-version policy plus Play in-app update flows. Production API origin pinned.

## Stale findings corrected during review

- Front/back watch intake photos already existed (separate labels, camera/picker, native upload); regression coverage added.
- Custom fields already existed.
- Native 90-day sliding refresh sessions (365-day cap) and backend tests already exist on current main; no duplicate branch merge.
- Watch closed-directory status on current web is collected only; native aligned to that current rule.
- Invoice manager gating on native matches the current backend; permissive web controls cannot override server authorisation.

## Checks recorded so far

- Combined original native unit suite compiled/passed after branch integration.
- New watch/parts/mobile unit contract tests pass; new instrumentation sources compile.
- Backend: 90 passed, 1 skipped across client config, payment aliases, refresh sessions, mobile invoices/finance and reports; booking suite 22 passed. Tests use a disposable SQLite database.
- Full combined native unit/lint/build and emulator workflows are in progress. A fresh emulator at port 5560 uses an isolated data directory; it does not reuse Sam's saved app session.

## Release gate

Do not describe this as fully validated, shipped or live until combined tests, simulator workflow review, signed bundle checks, backend deployment where needed, and actual Google Play submission are recorded below. Additive backend changes (booking offer count and public native config) must be deployed for full behavior. Real SMS/email/push delivery, physical BLE printing and field behavior require their appropriate environment; synthetic checks do not prove delivery.

## Validation updates

- Native combined build/lint passed (0 lint errors, existing warnings remain); 296 unit tests passed before the final recovery/outcome additions.
- New parts/community/engraving emulator group: 11 passed, plus 3 representative screenshot cases passed. Images in `artifacts/parity-20261111/` in the implementation checkout.
- Broader initial emulator run: 100 passed before a stale mock assertion crashed the test process. Corrected the expectation from card to eftpos; fixed a genuine cached-session publication race, and resumed the remaining suite.
- Actual localhost API exposed offset-datetime persistence loss under SQLite. Create/PATCH now normalise aware scheduled times to UTC before persistence; 36 scheduling/booking/cockpit backend tests pass including +11/+10, naive UTC, explicit null and calendar-day membership.
- Both invoice controls and the native VM now require a selected two-outcome option before invoicing; added blocking/selection regressions.
- Native replacement upgrade now preserves previous Capacitor drafts and IndexedDB in an encrypted, read-only recovery archive. Exact account-scoped drafts can be inspected/exported; queued existing-job data is only shown after a live tenant check. No legacy writes are replayed because their original result and stale-write semantics cannot be proven. Original local storage is never deleted.
- Weekly release workflow switched to the native module, plus native unit/lint/test-compilation CI. Release signing and Firebase package are checked before a Play build. GitHub CLI has no authenticated session here; existing signing/Firebase/Play secrets were not modified.
- Actual typed API round trips pass for auth, customer/watch/mobile jobs, scheduling offsets, quotes/invoices, reports/CSV, stock, state hubs/DMs/receipts, My Shops, Birkenstock parts, engraving queue/export and API-key create/revoke. These use only the loopback disposable QA database with delivery providers disabled.
- Session API now returns authenticated shop currency, name, ABN and phone: native already expected these fields, but the real API did not supply them. Cross-shop regression plus all 24 auth tests pass.
- Shop stock "Set count to" now has explicit absolute-count semantics (`set_count`); existing HQ signed-delta adjustments remain compatible. Stock/shoe backend tests: 10 passed; relevant frontend tests: 12 passed. Frontend typecheck and production build pass; generated OpenAPI refreshed.
- Route map now has a bundled Leaflet/OpenStreetMap fallback without an Android Maps key, displaying real geocodes and explicit unlocated counts. Renderer uses local scripts, escaped text and restricted tile networking. Booking/intake default address suggestions now use available device geocoding, rather than nonexistent server Places routes.
- Final native unit suite: 306 passed; lint has 0 errors. Broader emulator outcome aggregation before final map additions: 378 unique passed, 2 skipped, no unresolved failures. Map/booking/reorder group: 22 passed; two map assertions corrected to use substring matching and rerun separately.
- Simulator walkthrough verified sample network hubs, pinned stock requests and replies against the actual QA backend. Screenshot: `artifacts/parity-20261111/simulator-network-hub.png` in isolated checkout.
- Play app-content review has no outstanding declarations. Existing exported Data safety answers already include crash logs, diagnostics, device identifiers, messaging, photos and user-generated content. No declaration has been changed.
- Final candidate: **1.1.0 (29905800)**, package `au.mainspring.app`, min24/target36, production origin pinned. AAB SHA256 `58142642A524D56C8FD167BDB6CC2E859B5E2853319B01BF7057F9816B549901`. Upload certificate matches the previous Capacitor release; 64-bit native libraries have 16KB load-segment alignment. Signed bundle and release APK build passed.

## Deployment and submission

Pending: CI, backend deployment, production health/config verification and Google Play submission. Deploy all additive backend contracts before rollout, including `set_count`, session identity, booking offer count and public client config. Do not infer store approval from an upload or submission.

## Screenshot review hold

Sam requested screenshots of each screen before any Google Play update, then instructed work to continue. **Publication is held until he reviews the screenshots.**

- Prepared 195 labelled phone-simulator screenshots across 10 sections, including main screens, major tabs, dialogs/forms and selected lower sections of long pages. Actual native composables use a disposable localhost shop with synthetic records. No production messages, payments or destructive changes were submitted.
- Central gallery: [screen review](native-screen-review-2026-11-11/index.html), with individual full-resolution PNGs, an image manifest and a 195-page bookmarked PDF in the same folder. A ZIP sits beside the folder.
- The default Mainspring appearance is shown. The login screenshot notes its developer-only Connection settings row; the Play build hides that row. Demo signature artwork and map coordinates are explicitly labelled samples.
- Visual QA caught a real WebView map-height bug: native viewport 1080x683px, but HTML/body/map computed height was zero despite loaded tiles/markers. The bundled renderer now sizes to actual CSS-pixel viewport height before initialisation/rendering and on resize. Both native map regressions pass, including positive container height and a marker within its bounds. The replacement map screenshot visibly shows OSM tiles, all four stops and controls; no image compositing was used.
- Rebuilt signed AAB and release APK after the map fix. Current AAB SHA256 is `10FEF8D8F0C15F1A0AAED7F1FEA0B21BDB6780EB79F3D7DFD3202E2B1C4F857E`; the earlier `58142642...` artifact is superseded. Version remains **1.1.0 (29905800)**, package `au.mainspring.app`. JarFile verification and unchanged upload-certificate fingerprint confirmed.
- CI native/frontend checks pass. Full Postgres/SQLite suites exposed the same missing public-read rate limit on client config; its minimal fix and actual HTTP429 tests pass (29 passed, 2 skipped), but that fix still needs committing and CI rerun before deployment.
- No Play release was uploaded, submitted or published. Resume release work only after visual feedback/approval, then complete CI, backend deployment and production verification before submission.
