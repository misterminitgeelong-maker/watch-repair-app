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
    navigator.serviceWorker.register('/sw.js').catch(() => {})
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
