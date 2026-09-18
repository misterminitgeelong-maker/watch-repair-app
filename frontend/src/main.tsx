import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.tsx'
import { applyTheme, readStoredTheme } from '@/context/ThemeContext'
import { stampBuildMetaTag } from '@/lib/buildInfo'

applyTheme(readStoredTheme())
stampBuildMetaTag()

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then(registration => {
        // A phone can stay on one tab for days. Re-check for a new worker when
        // the app is brought back to the foreground so techs are not stuck on a
        // stale bundle; the worker still decides when to take over.
        const checkForUpdate = () => {
          if (document.visibilityState === 'visible') registration.update().catch(() => {})
        }
        document.addEventListener('visibilitychange', checkForUpdate)
      })
      .catch(() => {})
  })
}

const sentryDsn = import.meta.env.VITE_SENTRY_DSN
if (typeof sentryDsn === 'string' && sentryDsn.trim()) {
  const dsn = sentryDsn.trim()
  try {
    const parsed = new URL(dsn)
    const looksValid =
      (parsed.protocol === 'https:' || parsed.protocol === 'http:') &&
      parsed.username.length > 0 &&
      parsed.hostname.length > 0 &&
      parsed.pathname.replace(/\/+$/, '').length > 1
    if (!looksValid) {
      console.warn('Ignoring malformed VITE_SENTRY_DSN; continuing without Sentry')
    } else {
      Sentry.init({
        dsn,
        tracesSampleRate: 0.1,
        environment: import.meta.env.MODE,
      })
    }
  } catch (err) {
    console.warn('Sentry.init failed; continuing without Sentry', err)
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
