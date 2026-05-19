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

## Mainspring web app

This frontend is **web-only**: run in the browser or install as a PWA (`manifest.json` + service worker in production).

### Local development

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/v1` to the backend. Copy `.env.example` to `.env.local` for optional overrides.

### Production build

```bash
npm run build    # output in dist/
npm run preview  # smoke-test the bundle
```

Docker and Railway builds use the root `Dockerfile`, which runs `npm run build` and serves `dist/` from FastAPI.

### Environment variables

| Variable | Purpose |
|----------|---------|
| `VITE_GOOGLE_MAPS_API_KEY` | Browser key for Maps JavaScript API (restrict by HTTP referrer for your domain). |
| `VITE_API_BASE_URL` | Optional API origin when UI and API are on different hosts (e.g. `https://mainspring.au`). Omit for same-origin deploys. |
| `VITE_SENTRY_DSN` | Optional error reporting. |

### Auth

JWT access and refresh tokens use **`localStorage`** or **`sessionStorage`** depending on “remember this device” on the login page. Silent refresh runs via the axios 401 interceptor and `AuthContext` proactive timer.

### Mobile browsers

The layout uses safe-area insets (`viewport-fit=cover`, `AppShell.tsx`). Camera intake uses standard `<input type="file" capture>`. **Web Bluetooth** (Niimbot labels) works in supported desktop/Android Chrome builds, not in all mobile browsers.
