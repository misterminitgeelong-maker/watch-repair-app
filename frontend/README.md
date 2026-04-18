# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

## Capacitor (iOS / Android store apps)

This repo includes **Capacitor** (`capacitor.config.ts`, `android/`, `ios/`). The web UI is built to `dist/`, then copied into the native projects.

1. Set **`VITE_API_BASE_URL`** in `.env.local` to your public API origin (e.g. `https://mainspring.au`) so the app calls the real server from the WebView. Production **CORS** must allow Capacitor origins (see root `.env.example`).
2. Build and sync: **`npm run build && npm run cap:sync`** (or **`npm run cap:bundle`**). If TypeScript project refs fail locally, use **`npm run cap:bundle:vite`** for a Vite-only bundle for native QA.
3. Open a native IDE: **`npm run cap:open:android`** or **`npm run cap:open:ios`** (iOS needs macOS with Xcode; first time run **`pod install`** in `ios/App` if CocoaPods is installed).

Synced web assets under `android/…/public` and `ios/…/public` are gitignored; always run **`cap:sync`** after a web build before shipping a native binary.

### Native shell (Step 3)

- **Safe area:** `viewport-fit=cover` in `index.html`; mobile app header uses `env(safe-area-inset-top)` (see `AppShell.tsx`). Bottom tabs already used `safe-area-inset-bottom`.
- **Status bar & splash:** `@capacitor/status-bar` + `@capacitor/splash-screen` — tuned in `main.tsx` after auth hydration; defaults also in `capacitor.config.ts`.
- **Android back:** `@capacitor/app` — `NativeChrome.tsx` maps hardware back to in-app `navigate(-1)` when history allows.
- **Tokens on device:** access/refresh JWTs use **Keychain / Android Keystore** via `@aparajita/capacitor-secure-storage` (Step 5); “remember device” stays in `@capacitor/preferences`. In-memory cache still feeds axios synchronously.

### Permissions & APIs (Step 4)

**Declared in native projects**

- **Camera & photo library** — watch/shoe/auto-key intake uses `<input type="file" capture>` and gallery picks. Android: `CAMERA` + optional camera hardware features. iOS: `NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`.
- **Bluetooth (Web Bluetooth / Niimbot)** — Android 12+: `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` (`neverForLocation`); older API levels use legacy Bluetooth permissions. iOS: `NSBluetoothAlwaysUsageDescription`. Behaviour still depends on Chrome/WebView support; test on a real device.

**Google Maps (`VITE_GOOGLE_MAPS_API_KEY`)**

The map uses the **Maps JavaScript API** inside the WebView. In [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your browser key → **Application restrictions**:

- Under **HTTP referrers**, add (at minimum) the WebView origins used by Capacitor builds, for example:
  - `https://localhost/*`
  - `capacitor://localhost/*` (if your tooling reports this origin on iOS)
- Keep your existing production website referrers (e.g. `https://mainspring.au/*`) for the deployed web app.

If the key is restricted to production domain only, **maps will fail inside the store app** until those referrers exist.

**Quick native QA checklist**

1. Login + session survives app restart (remember device on/off).
2. Take photo + upload on a watch job, shoe job, and mobile-services job.
3. Open Mobile Services **Map** view with a valid Maps key (pins or fallback).
4. Optional: **Print to M2** from intake print page on Android Chrome vs Capacitor WebView.

### Auth & session hardening (Step 5)

- **Secure token storage (native):** `@aparajita/capacitor-secure-storage` stores access + refresh tokens. Existing installs **migrate once** from legacy `@capacitor/preferences` token keys on next cold start.
- **Resume refresh:** `@capacitor/app` `resume` (see `NativeChrome.tsx`) calls a **proactive** `/auth/refresh` (cooldown 5s) so long background periods are less likely to hit expired access JWTs on the first tap.
- **React state sync:** after any silent refresh (401 interceptor or resume), `AuthContext` listens for `auth:access-token-updated` and reschedules the proactive refresh timer from `expires_in_seconds` or the JWT `exp` claim.
- **Web / dev:** unchanged — still `localStorage` / `sessionStorage` per remember-me.

### Device APIs & external flows (Step 6)

**Feature audit (same React build; native is WebView + permissions)**

| Area | In-app usage | Native notes |
|------|----------------|--------------|
| **Camera / gallery** | `<input type="file" accept="image/*">` with optional `capture="environment"` on watch/shoe/auto-key/new job flows | iOS/Android permission strings: Step 4. |
| **Spreadsheet import** | CSV/XLSX `input type="file"` on Database / Stocktakes | Uses system document picker; no extra Android storage permission for typical WebView flows. |
| **Downloads / blobs** | CSV exports, stocktake export, attachment download (`<a download>` / blob URLs) | Behaviour depends on WebView; if a device saves to “Downloads” oddly, treat as QA edge case. |
| **Google Maps** | `VITE_GOOGLE_MAPS_API_KEY` + `@vis.gl/react-google-maps` (**Maps JavaScript API**) | Restrict keys by **HTTP referrer** (Step 4), not by Android package / iOS bundle id — that applies to the **native Maps SDK**, which this app does not use. Server route `/maps/optimize-driving-route` needs **`GOOGLE_MAPS_WEB_SERVICES_KEY`** separately. |
| **Web Bluetooth (Niimbot)** | `PrintWatchIntakeTicketsPage` / `PrintShoeIntakeTicketsPage` via `navigator.bluetooth` | Permissions: Step 4. Chrome vs in-app WebView support varies — QA on real hardware. |
| **Stripe / billing** | `window.location.assign` / `window.open` to `checkout.stripe.com`, Connect onboarding, billing portal | **`server.allowNavigation`** in `capacitor.config.ts` lists **hostname masks** (`*.stripe.com`, etc.) so those navigations stay in the WebView. Extend the list if your Stripe return URLs use another domain. Android **`queries`** for `https` VIEW intents helps resolve external handlers (manifest). |
| **Clipboard** | `navigator.clipboard.writeText` (quotes, portal, parent ingest, etc.) | Requires **secure context** (HTTPS / Capacitor localhost); no extra plist keys for basic copy. |

**Store checklist**

1. Stripe Checkout, Connect, and return to your **production web hostname** (add to `allowNavigation` if not `mainspring.au`).
2. Maps + geocode with referrers from Step 4; Directions API for route optimisation on the server key.
3. Photo intake on one watch job, one shoe job, one auto-key job on **physical** devices.
4. Optional: pay a **test invoice** through Stripe in an internal build.
