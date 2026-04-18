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
