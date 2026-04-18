import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Capacitor } from '@capacitor/core'
import { App } from '@capacitor/app'
import { refreshSessionOnNativeResume } from '@/lib/api'

/**
 * Android hardware back → in-app history when possible (Capacitor WebView only).
 * App resume → proactive JWT refresh so sessions survive long background (Step 5).
 */
export default function NativeChrome() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return

    let backHandle: { remove: () => void } | undefined
    let resumeHandle: { remove: () => void } | undefined
    let canceled = false

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
    }
  }, [navigate])

  return null
}
