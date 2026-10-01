# Mainspring Native Android App

Native Android application built with Kotlin, Jetpack Compose, Material 3, and Retrofit.

## Architecture

- **UI Layer**: Jetpack Compose with Material 3 UI components, edge-to-edge layout support, and reactive state collection with `StateFlow`.
- **ViewModel & State Management**: AndroidX ViewModels managing UI state with Kotlin Coroutines.
- **Network Layer**: Retrofit 2 + OkHttp 4 with OkHttp logging interceptor, token refresh authenticator (`TokenAuthenticator`), and authentication interceptor (`AuthInterceptor`).
- **Secure Storage**: `EncryptedSharedPreferences` via AndroidX Security for storing JWT access and refresh tokens.
- **Navigation**: Jetpack Navigation Compose (`NavHost`).

## Features Covered

- **Authentication**: Tenant slug, email, and password login; JWT session management with refresh token support.
- **Dashboard**: High-level KPIs, job counts, revenue metrics, and activity summary.
- **Watch Repair Jobs**: Full list with status filtering, search, detailed view, status transitions (e.g. Intake -> Diagnosis -> Ready -> Delivered), technician notes, claim/release job actions, and attachments.
- **Shoe Repair Jobs**: List, detail, status updates, technician notes, claim/release.
- **Auto Key Jobs**: Mobile locksmith quick intake, job management, status updates.
- **Customers**: Customer listing, search, customer profile, and associated repair job history.
- **Quotes**: Quote overview, status filtering, quote line items, and sending approval links.
- **Invoices**: Invoice listing, payment recording, and detailed payment history.
- **Inbox**: Event logs and system notification inbox.

## Getting Started

### Prerequisites
- Android Studio Ladybug (2024.2.1) or newer
- JDK 17
- Android SDK 35 (min SDK 26)

### Configuration
1. Create a `local.properties` file in `apps/mainspring-native-android/` (or copy `local.properties.example`):
   ```properties
   sdk.dir=C\:\\Users\\<your-user>\\AppData\\Local\\Android\\Sdk
   api.base.url=http://10.0.2.2:8000/
   ```
   *Note: `10.0.2.2` connects to `localhost` on your host computer when running in the Android Emulator.*

2. Open the `apps/mainspring-native-android` project in Android Studio.
3. Sync Gradle and run the `:app` configuration on an Android Emulator or connected physical device.
