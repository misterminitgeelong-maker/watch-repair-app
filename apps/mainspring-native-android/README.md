# Mainspring Native Android

Kotlin/Jetpack Compose implementation of the existing Mainspring shop and mobile workflows. This is the native replacement release candidate for the existing Play app. See [the 11 November parity and release record](../../docs/NATIVE_ANDROID_PARITY_RELEASE_2026-11-11.md) for validation and submission status.

## Implementation

- Compose/Material 3, Navigation Compose, ViewModels/StateFlow and coroutines.
- Retrofit/OkHttp with fixed-origin, sign-in-bound API services and guarded token refresh.
- Encrypted preferences for tokens and server/tenant/user-scoped drafts and creation checkpoints.
- Native watch/shoe/mobile intake, camera/document photos, job/customer editing and conversations.
- Quotes/GST/discounts, catalogue lookup, counter sale, invoices/payments and work logs.
- Mobile prospects, shared toolkit, booking requests, dispatch pool and business-account billing/membership.
- Verified shop switching, day scheduling, guarded mobile status changes and invoice summary printing/PDF.
- Period reports/comparisons, inventory search/paging and checkpointed stocktake workflows.

The [implementation record](../../docs/NATIVE_ANDROID_WORKFLOW.md) lists tested behavior and limits. The [parity worklist](../../docs/NATIVE_ANDROID_PARITY_PLAN.md) records remaining work; full web-app parity is not claimed.

## Build and run

Open this directory as an Android Studio project. The build uses Java 17 language compatibility, Android SDK 36 and min SDK 24 (with core library desugaring). The project has been built with Android Studio's bundled JBR and the supplied Gradle wrapper.

Set `ANDROID_HOME` to your SDK and `JAVA_HOME` to the compatible JDK, then run:

```powershell
./gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
# With an emulator or device connected:
./gradlew.bat :app:connectedDebugAndroidTest
```

The default server is `https://mainspring.au/`. Optional `local.properties` settings:

```properties
sdk.dir=C:/Users/your-user/AppData/Local/Android/Sdk
api.base.url=http://10.0.2.2:8000/
```

Debug builds allow local HTTP for emulator development; release builds require HTTPS. Login also exposes validated server settings. Do not put credentials in source or local configuration.

Debug package: `au.mainspring.nativeapp.debug`. Play release package: `au.mainspring.app`. APK: `app/build/outputs/apk/debug/app-debug.apk`. Debug remains separate; the signed release updates the existing Play listing using its upload key.

Instrumentation checks use MockWebServer and the debug package, clear its test token/draft state, and must run in an isolated emulator/device profile. They create no production customers, invoices or messages. Reports are under `app/build/reports/`.

Before a production replacement: complete parity/staging/physical-device checks, currency handling, accessibility, production package/signing and migration, and current Android/Google Play requirement verification.

## Local backend integration check

The opt-in `LocalBackendSmokeTest` exercises native Retrofit models and requests against the current FastAPI routes, real auth and a disposable SQLite shop. It skips during ordinary emulator suites unless local arguments are supplied. Production startup/migrations, provider delivery and deployed infrastructure are outside this check.

From the repository root, run `qa/local_backend.py` using this project's Python environment:

```powershell
.venv/Scripts/python.exe apps/mainspring-native-android/qa/local_backend.py
```

The script writes synthetic connection metadata under `artifacts/native-local-backend/`, binds only `127.0.0.1:8716`, disables delivery providers and creates a fresh test database. In another terminal, from this Android project directory:

```powershell
adb -s emulator-5554 reverse tcp:8716 tcp:8716
$qa = Get-Content ../../artifacts/native-local-backend/connection.json | ConvertFrom-Json
./gradlew.bat :app:connectedDebugAndroidTest `
  '-Pandroid.testInstrumentationRunnerArguments.class=au.mainspring.nativeapp.LocalBackendSmokeTest' `
  '-Pandroid.testInstrumentationRunnerArguments.localApiBaseUrl=http://127.0.0.1:8716/' `
  "-Pandroid.testInstrumentationRunnerArguments.localTenantSlug=$($qa.slug)" `
  "-Pandroid.testInstrumentationRunnerArguments.localOwnerEmail=$($qa.email)"
```

Stop the QA server and remove the ADB reverse mapping afterward. The test rejects non-loopback targets and non-QA account names.


### Android design reference build

See `../../docs/NATIVE_ANDROID_DESIGN_REFERENCE.md` for the implemented screen map, tested adaptations and remaining API/device limits. The default Refined Warmth theme follows the user's 21-page Android reference; More contains the other themes and field-navigation preference.

The route screen works without a Maps key: bundled Leaflet renders interactive OpenStreetMap tiles with real device-geocoded stops, numbered markers, fit-to-stops, stop-order lines, job popups and explicit navigation. Unlocated addresses are reported honestly and remain in the stop list; no fabricated coordinates are shown. Customer text stays in the local renderer, which allows remote raster tiles only. Leaflet’s BSD licence is included in `app/src/main/assets/route-map/LEAFLET-LICENSE.txt`; OpenStreetMap attribution remains visible on the map.

Google Maps is optional. Put `maps.api.key=<Android-restricted key>` in ignored `local.properties`, enable Maps SDK for Android on the existing Maps project, and restrict the key to the package and signing certificate. Debug uses `au.mainspring.nativeapp.debug` and its debug certificate. The published replacement uses `au.mainspring.app` and the **Play app-signing certificate** shown in Play Console for installed Play builds; the upload certificate is different. Keep the web key’s restrictions separate. Setup: [Maps SDK for Android](https://developers.google.com/maps/documentation/android-sdk/start).

Address autocomplete uses Android’s available device geocoder, including suburb/state/postcode on booking requests. It does not call an unimplemented `/v1/places` proxy. Typed addresses and coverage lookup remain available when the device geocoder cannot supply suggestions.

The companion session API source update exposes verified shop currency/details and fixes its calendar zone to match per-shop mobile scheduling. Deployment, production package/version/signing migration and physical-device QA remain release tasks. Play builds require the existing signing configuration outside Git and the Firebase config for `au.mainspring.app` (`-PplayRelease=true`).


## Field experience redesign

The 9 October pass focuses on Today and the complete mobile job journey: preparation, confirmed departure/arrival, quote review, completion and full-payment recording. Read-only encrypted snapshots support viewing today’s schedule and the last 50 opened jobs during connection outages. Updates remain blocked until a successful refresh. Unconfirmed payments require invoice review before retrying. See [the shared field experience document](../../docs/NATIVE_FIELD_EXPERIENCE.md) for scope and release limitations.


## Native replacement release

The release API origin is pinned to `https://mainspring.au/`. Firebase JSON and upload signing credentials stay outside Git. `-PplayRelease=true` fails if signing or the published Firebase package is missing. The weekly release workflow now builds this native module, so it cannot replace the new native client with a later Capacitor internal build.

The app checks the public `/v1/client-config/android` policy and Google Play for updates. Server settings `ANDROID_MINIMUM_VERSION_CODE` (default 0) and `ANDROID_UPDATE_MESSAGE` control the minimum supported client. Crash diagnostics use an optional build `NATIVE_SENTRY_DSN`/local `sentry.dsn`, or the public, secret-free DSN from the existing backend Sentry configuration; no authentication data or customer text is attached.

Previous Capacitor drafts and queued writes are read from their original local WebView origin, preserved in a separate encrypted archive, and available through **Previous app work**. Nothing is automatically replayed or deleted. Queued changes matched by signed-in user and a live tenant-scoped read can be inspected/exported and finished manually in the current job. Recovery never replays an earlier write; original outcomes may be uncertain.
