import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import { Capacitor } from '@capacitor/core'
import './index.css'
import App from './App.tsx'
import { hydrateNativeAuthFromPreferences } from '@/lib/api'
import { applyTheme, readStoredTheme } from '@/context/ThemeContext'

applyTheme(readStoredTheme())

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

const sentryDsn = import.meta.env.VITE_SENTRY_DSN
if (typeof sentryDsn === 'string' && sentryDsn.trim()) {
  Sentry.init({
    dsn: sentryDsn.trim(),
    tracesSampleRate: 0.1,
    environment: import.meta.env.MODE,
  })
}

async function initNativeShell(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  await hydrateNativeAuthFromPreferences()
  const [{ StatusBar, Style }, { SplashScreen }] = await Promise.all([
    import('@capacitor/status-bar'),
    import('@capacitor/splash-screen'),
  ])
  try {
    await StatusBar.setStyle({ style: Style.Dark })
  } catch {
    /* iOS / WebView variance */
  }
  try {
    await StatusBar.setBackgroundColor({ color: '#2D231C' })
  } catch {
    /* not supported on all platforms */
  }
  try {
    await SplashScreen.hide()
  } catch {
    /* already hidden */
  }
}

async function bootstrap(): Promise<void> {
  await initNativeShell()
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void bootstrap()
