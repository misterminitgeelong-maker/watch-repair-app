# Native Android: release readiness

Scope: `apps/mainspring-native-android`, UI layer (`ui/`). Written alongside the accessibility, contrast, dark mode and font-scale pass.

## 1. TalkBack / semantics

Changes made:

- Screen titles and section labels expose `heading()`: `LargeHeader` title, `AtelierTopAppBar` title, `SectionLabel` (Calibre mono and plain), `EmptyState` title, login title.
- Every clickable row/column/box that had no role now uses `Role.Button` (Today rows, Jobs rows, More rows, Search hits, Inbox cards, board cards, lead rows, toolkit rows, sync chips). Tabs/pills already use `Role.Tab` plus `selected`.
- `RoundPlusButton` exposes `Role.Button` with its label ("New intake", "New", ...).
- Checkbox rows ("Remember shop ID", "I contacted the customer") are now `toggleable(role = Checkbox)` so the whole 48dp row is one control, instead of a clickable row wrapped around a second clickable checkbox.
- The Today search field overlay (an invisible clickable over a read-only field) now has a content description.
- Login logo is decorative (`contentDescription = null`); it sits next to the "Mainspring" heading. The sign-in spinner is announced as "Signing in".
- Live regions: `ErrorBanner` (assertive), offline/online banner and the sync chip row (polite), subscription banner (polite). The "Saved offline, will sync" message is shown through these banners / ErrorBanner paths.
- Inbox tab badge reads "N unread"; the Calibre wizard step caption reads "Step N of M, title"; the Calibre job stage strip reads "Progress: <stage>, step N of 4".
- Touch targets: `PillChip`, `AtelierChip`, `TabChip` minimum raised from 44dp to 48dp; sync chips use `minimumInteractiveComponentSize()`.

Known gaps / manual TalkBack checks still needed:

- Canvas icons (`FieldIcon`, `AtelierIcon`, `WatchArt`) are decorative by design; their parent control carries the label. Verify on a device that each tab announces "<label>, selected, tab".
- The Material `Switch` for "Use field navigation" is labelled by a content description rather than a merged row; consider converting to a `toggleable` row.
- Screens not individually walked through with TalkBack (only audited by code search): quote composer, intake wizards, dispatch map art, QR/print screens.

## 2. Contrast (WCAG 2.1 AA)

Ratios computed with the WCAG relative-luminance formula (text needs 4.5:1, large text and UI components 3:1).

### Calibre light

| Pair | Ratio | Result |
|---|---|---|
| Forest `#294D3C` on white | 9.45 | pass |
| Forest on ForestMint `#E6EFE9` | 8.05 | pass |
| Forest on Grey `#F3F3F3` | 8.52 | pass |
| Forest on `#EDEDED` | 8.08 | pass |
| White on Forest (buttons, banner) | 9.45 | pass |
| Ink `#1B1B1B` on white | 17.22 | pass |
| White on Ink (offline banner) | 17.22 | pass |
| Muted `#6A6A6A` on white | 5.41 | pass |
| Muted `#6A6A6A` on Grey `#F3F3F3` | 4.87 | pass |
| Muted `#6A6A6A` on `#EDEDED` | 4.62 | pass |
| Muted `#6A6A6A` on `#E6E6E6` (surfaceContainerHighest) | 4.33 | FAIL |
| Error `#B3261E` on white | 6.54 | pass |
| Outline `#8A8A8A` on white | 3.45 | pass (UI component, 3:1) |
| Hairline `#DADADA` on white | 1.40 | decorative divider only; not used as the sole boundary of an input |

Fix: `Calibre.Muted` changed to `#5F5F5F` (6.39 on white, 5.75 on Grey, 5.12 on `#E6E6E6`). All Calibre light text pairs now pass.

Open design question: unfocused Calibre text fields have no border (Grey fill on white is about 1.1:1). The label/placeholder identifies the field, but WCAG 1.4.11 would want a 3:1 boundary. Switching `unfocusedBorderColor` to `outline` (3.45) fixes it at the cost of the flat look. Not changed.

### Calibre dark (new)

Previously Calibre ignored system dark mode, and the only dark option was the separate Night (blue) appearance. Hard-coded `Calibre.Forest` (`#294D3C`) on a dark surface is 1.97:1, which fails. Now, when the appearance is Calibre and the system is in dark mode, `MainspringTheme` builds a Calibre dark scheme (flat Calibre layout, green accent) using new tokens:

| Pair | Ratio |
|---|---|
| ForestDark `#8FC4A3` on background `#111512` | 9.29 |
| ForestDark on surface-high `#252C27` | 7.21 |
| OnForestDark `#0B1A12` on ForestDark (primary buttons) | 9.05 |
| DarkMuted `#A9B1AB` on `#111512` | 8.39 |
| DarkMuted on `#252C27` | 6.51 |
| DarkInk `#EEF2EE` on `#111512` | 16.29 |
| Outline `#7C857E` on `#111512` | 4.84 |
| Error `#FFB4AB` on `#111512` | 10.85 |
| DarkHairline `#2E352F` on `#111512` | 1.46 (decorative) |

The explicit Night appearance (blue) is unchanged: primary 6.58, onSurfaceVariant 7.74, outline 3.83, error 9.56 on its surface `#18212D`, all pass. Atelier light: primary `#2453D4` on white 6.44, onSurfaceVariant on background 5.45, outline 3.11.

Hard-coded `Calibre.*` colours in screens were replaced with theme roles (`primary`, `onSurfaceVariant`, `surfaceVariant`, `outlineVariant`, `onSurface`) so they follow whichever scheme is active (job detail notes, activity cards, check rows, stage strip, wordmark, invoice notice/link, route screen, subscription banner, search divider, wizard progress, Dispatch route art). Values in Calibre light are identical to before. The only remaining direct uses are the connectivity banner background (Ink or Forest with white text, correct in both modes) and non-Calibre fixed illustration colours.

Note: `MainspringTheme(darkTheme = true)` (used by an existing test) still forces the Night scheme; the Calibre dark scheme applies only when the theme follows the system.

## 3. Large font scale (200%)

- Login: sign-in button `height(52)` became `heightIn(min = 52)`; checkbox row is 48dp minimum.
- Route screen placeholder card and Period Reports revenue chart: fixed heights became minimums.
- `LargeHeader` titles may now wrap to two lines (was `maxLines = 1`, which clipped "Today, at the bench." style titles).
- Already scale-safe on inspection: Today (time column widens above 1.3x), More rows (`heightIn(min = 56)`), Jobs list/search (chips scroll horizontally, rows wrap), segmented pills fall back to horizontal scroll above 1.2x/1.25x.
- Remaining fixed heights are decorative (3dp/2dp rules, 210dp route art with no text, spacers).
- Manual check still required on a device at Settings > Display > Font size largest plus Display size largest: Today, Jobs list, job detail (watch/shoe/auto key), More, login, intake wizards.

## 4. Play release checklist (manual steps)

Current state (`app/build.gradle`): `applicationId au.mainspring.nativeapp`, `versionCode 1`, `versionName 0.3.0-native`, `minSdk 26`, `targetSdk 35`, release `minifyEnabled false`, no `signingConfigs` block in the repo (the upload key lives outside the repo).

- [ ] Signing: add a release `signingConfig` that reads keystore path/alias/passwords from `~/.gradle/gradle.properties` or CI secrets (never committed); confirm Play App Signing is enrolled and the upload key matches.
- [ ] Version: bump `versionCode` (monotonic integer, Play rejects reuse) and set a release `versionName`; drop the `-native` suffix if not wanted publicly.
- [ ] Build an Android App Bundle: `./gradlew.bat :app:bundleRelease`; install the signed build on a real device and smoke test login, Today, a job, offline queue.
- [ ] R8/ProGuard: `minifyEnabled` is false. Enabling it shrinks the app but needs a full regression pass; if enabled, add keep rules for Gson/Retrofit/Moshi models (whatever `ApiClient` uses), the FileProvider, and `R.font` resources, and keep the mapping file for Play Console crash de-obfuscation. Decide explicitly rather than shipping by default.
- [ ] Permissions (manifest): `INTERNET`, `ACCESS_NETWORK_STATE` only. No location, camera, contacts or storage permissions are declared. Photo/intake files go through the `FileProvider` (not exported, `grantUriPermissions`). `allowBackup=false`, `usesCleartextTraffic=false`, with a network security config. Re-check the merged manifest (`app/build/intermediates/merged_manifests`) for library-added permissions before upload.
- [ ] Maps: `MAPS_API_KEY` must be set for the release build (otherwise `BuildConfig.MAPS_CONFIGURED` is false and a placeholder is shown). Restrict the key in Google Cloud to the package name plus the Play App Signing SHA-1.
- [ ] API base URL: confirm the release `API_BASE_URL` points at the production host over HTTPS.
- [ ] Data safety form (draft notes, verify against actual behaviour before submitting):
  - Data collected: name, email, phone, address (customer and staff records), financial info in the sense of invoices and payment status (card payments are taken through Stripe, no card numbers handled in-app), photos the user attaches to jobs, app activity and diagnostics if Sentry or similar is enabled.
  - Purpose: app functionality; account management. No advertising, no analytics SDK for ads, no data sold.
  - Shared with: the Mainspring backend and its processors (Stripe for payments, email/SMS providers) as service providers; declare accordingly.
  - Encrypted in transit: yes (HTTPS only). Deletion: users can request account and shop data deletion; provide the URL in the Play Console.
- [ ] Privacy policy URL and in-app account deletion path (Play requires both for apps with account creation; here accounts are provisioned by the shop, so state this in the form).
- [ ] Store listing: icon (the current launcher is a vector only; add adaptive/monochrome icon and a 512px store icon), feature graphic, at least two phone screenshots (plus tablet screenshots, since the shell has a wide layout), short and full description, content rating questionnaire, target audience (18+ business app), contact email.
- [ ] Testing track: internal testing first, then closed testing (new personal developer accounts must run a closed test with testers for the required period before production access).
- [ ] Pre-launch report / Play Console: review accessibility and stability warnings from the automatic pre-launch device run.
- [ ] Run the connected test suite on an emulator and a physical device (not run in this pass), including at 200% font scale and in system dark mode with Calibre selected.
- [ ] Crash reporting and release notes: confirm the crash reporting DSN is the production one; prepare "What's new" text.
