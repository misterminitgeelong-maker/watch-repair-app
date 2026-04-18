import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Capacitor } from '@capacitor/core'
import { App } from '@capacitor/app'

/**
 * Android hardware back → in-app history when possible (Capacitor WebView only).
 */
export default function NativeChrome() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return

    let handle: { remove: () => void } | undefined
    let canceled = false

    void App.addListener('backButton', () => {
      if (window.history.length > 1) navigate(-1)
    }).then((h) => {
      if (!canceled) handle = h
    })

    return () => {
      canceled = true
      handle?.remove()
    }
  }, [navigate])

  return null
}
