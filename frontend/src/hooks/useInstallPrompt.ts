import { useCallback, useEffect, useRef, useState } from 'react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

/** Remembers a dismissal so the install affordance does not nag. */
const DISMISSED_KEY = 'mainspring.install-prompt-dismissed-at'
const DISMISS_QUIET_MS = 30 * 24 * 60 * 60 * 1000

export function isStandaloneDisplay(): boolean {
  if (typeof window === 'undefined') return false
  const standaloneNavigator = (navigator as Navigator & { standalone?: boolean }).standalone === true
  const matches = typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches
  return standaloneNavigator || matches
}

/** iOS Safari never fires beforeinstallprompt, so it needs written guidance instead. */
export function isIosSafari(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  const iosDevice = /iphone|ipad|ipod/i.test(ua)
  // iPadOS 13+ reports as a Mac; a touch-capable "Mac" is an iPad.
  const iPadOsDesktopMode = /macintosh/i.test(ua) && typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 1
  if (!iosDevice && !iPadOsDesktopMode) return false
  return !(window as Window & { MSStream?: unknown }).MSStream
}

export function readInstallDismissedAt(now = Date.now()): boolean {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY)
    if (!raw) return false
    const at = Number(raw)
    if (!Number.isFinite(at)) return false
    return now - at < DISMISS_QUIET_MS
  } catch {
    return false
  }
}

export function useInstallPrompt() {
  const deferredPrompt = useRef<BeforeInstallPromptEvent | null>(null)
  const [canInstall, setCanInstall] = useState(false)
  const [installed, setInstalled] = useState(false)
  const [dismissed, setDismissed] = useState(() => readInstallDismissedAt())

  // Standalone can change within a session (the user installs and reopens), so
  // track it rather than reading it once during render.
  const [standalone, setStandalone] = useState(isStandaloneDisplay)
  const isIos = isIosSafari()

  useEffect(() => {
    const onBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      deferredPrompt.current = e as BeforeInstallPromptEvent
      setCanInstall(true)
    }
    const onAppInstalled = () => {
      deferredPrompt.current = null
      setCanInstall(false)
      setInstalled(true)
      setStandalone(true)
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    window.addEventListener('appinstalled', onAppInstalled)

    const media = typeof window.matchMedia === 'function' ? window.matchMedia('(display-mode: standalone)') : null
    const onDisplayModeChange = (e: MediaQueryListEvent) => setStandalone(e.matches)
    media?.addEventListener?.('change', onDisplayModeChange)

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
      window.removeEventListener('appinstalled', onAppInstalled)
      media?.removeEventListener?.('change', onDisplayModeChange)
    }
  }, [])

  /** Remember a "not now" so the affordance stays quiet for a month. */
  const dismissInstallPrompt = useCallback(() => {
    try {
      localStorage.setItem(DISMISSED_KEY, String(Date.now()))
    } catch {
      /* ignore */
    }
    setDismissed(true)
  }, [])

  const promptInstall = useCallback(async (): Promise<boolean> => {
    if (!deferredPrompt.current) return false
    await deferredPrompt.current.prompt()
    const { outcome } = await deferredPrompt.current.userChoice
    deferredPrompt.current = null
    setCanInstall(false)
    // Declining the browser's own dialog counts as "not now".
    if (outcome === 'dismissed') dismissInstallPrompt()
    return outcome === 'accepted'
  }, [dismissInstallPrompt])

  /** True only where the platform can actually install, and the user has not said no. */
  const showInstallAffordance = !standalone && !installed && !dismissed && (canInstall || isIos)

  return {
    canInstall,
    isIos,
    isStandalone: standalone,
    installed,
    dismissed,
    showInstallAffordance,
    promptInstall,
    dismissInstallPrompt,
  }
}
