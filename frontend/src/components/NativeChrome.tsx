import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Capacitor } from '@capacitor/core'
import { App } from '@capacitor/app'
import { refreshSessionOnNativeResume } from '@/lib/api'
import { inAppPathFromUniversalUrl } from '@/lib/nativeDeepLinks'

/**
 * Android hardware back → in-app history when possible (Capacitor WebView only).
 * App resume → proactive JWT refresh (Step 5).
 * Universal Links / App Links → React Router path (Step 7).
 */
export default function NativeChrome() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return

    let backHandle: { remove: () => void } | undefined
    let resumeHandle: { remove: () => void } | undefined
    let urlOpenHandle: { remove: () => void } | undefined
    let canceled = false

    function applyOpenedUrl(url: string) {
      const path = inAppPathFromUniversalUrl(url)
      if (path) navigate(path, { replace: true })
    }

    void App.getLaunchUrl().then((launch) => {
      if (!canceled && launch?.url) applyOpenedUrl(launch.url)
    })

    void App.addListener('appUrlOpen', (event) => {
      applyOpenedUrl(event.url)
    }).then((h) => {
      if (!canceled) urlOpenHandle = h
    })

    void App.addListener('backButton', () => {
      if (window.history.length > 1) navigate(-1)
    }).then((h) => {
      if (!canceled) backHandle = h
    })

    void App.addListener('resume', () => {
      void refreshSessionOnNativeResume()
    }).then((h) => {
      if (!canceled) resumeHandle = h
    })

    return () => {
      canceled = true
      backHandle?.remove()
      resumeHandle?.remove()
      urlOpenHandle?.remove()
    }
  }, [navigate])

  return null
}
