# Mainspring Native Android

Kotlin/Jetpack Compose implementation of the existing Mainspring shop and mobile workflows. This remains a separate development app; it has not replaced the live Capacitor release.

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

Open this directory as an Android Studio project. The build uses Java 17 language compatibility, Android SDK 35 and min SDK 26. The project has been built with Android Studio's bundled JBR and the supplied Gradle wrapper.

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

Debug package: `au.mainspring.nativeapp.debug`. Prototype release package: `au.mainspring.nativeapp`. APK: `app/build/outputs/apk/debug/app-debug.apk`. Both remain separate from the live `au.mainspring.app` package.

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

For the native map, put `maps.api.key=<Android-restricted key>` in ignored `local.properties`. Enable Maps SDK for Android on the existing Maps project and restrict the key to the package and signing certificate for this build. Debug uses `au.mainspring.nativeapp.debug`; the prototype release bundle uses `au.mainspring.nativeapp`. Do not reuse the web key without checking its API/application restrictions. Instructions: https://developers.google.com/maps/documentation/android-sdk/start . Without a configured key the app provides the real stop list and external navigation, with an explicit map-unavailable state.

The companion session API source update exposes verified shop currency/details and fixes its calendar zone to match per-shop mobile scheduling. Deployment, production package/version/signing migration and physical-device QA remain release tasks. The generated prototype AAB is unsigned.


## Field experience redesign

The 9 October pass focuses on Today and the complete mobile job journey: preparation, confirmed departure/arrival, quote review, completion and full-payment recording. Read-only encrypted snapshots support viewing today’s schedule and the last 50 opened jobs during connection outages. Updates remain blocked until a successful refresh. Unconfirmed payments require invoice review before retrying. See [the shared field experience document](../../docs/NATIVE_FIELD_EXPERIENCE.md) for scope and release limitations.
