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
- **Tokens on device:** `@capacitor/preferences` — access/refresh tokens and “remember device” sync to native storage (in-memory cache for axios). This is **not** hardware-backed encryption; upgrade later if you need stricter guarantees.

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
