import { useEffect, useRef, useState } from 'react'

/** How long the "Back online" confirmation stays up after recovery. */
export const BACK_ONLINE_MS = 4000

export type OnlineStatus = {
  online: boolean
  /** True for a few seconds after the connection comes back. */
  justReconnected: boolean
}

export function readOnline(): boolean {
  if (typeof navigator === 'undefined') return true
  // Some environments leave onLine undefined; assume online rather than
  // blocking the UI on a value we cannot trust.
  return navigator.onLine !== false
}

/**
 * Track browser connectivity.
 *
 * `navigator.onLine` only proves the radio is up, so this is used for
 * messaging and for skipping doomed requests — never to block cached,
 * read-only screens.
 */
export function useOnlineStatus(backOnlineMs = BACK_ONLINE_MS): OnlineStatus {
  const [online, setOnline] = useState(readOnline)
  const [justReconnected, setJustReconnected] = useState(false)
  const timerRef = useRef<number | null>(null)
  const onlineRef = useRef(online)
  onlineRef.current = online

  useEffect(() => {
    const clearTimer = () => {
      if (timerRef.current != null) {
        window.clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }

    const handleOnline = () => {
      // Only announce a real transition, not a duplicate event.
      const wasOffline = !onlineRef.current
      onlineRef.current = true
      setOnline(true)
      if (!wasOffline) return
      setJustReconnected(true)
      clearTimer()
      timerRef.current = window.setTimeout(() => setJustReconnected(false), backOnlineMs)
    }

    const handleOffline = () => {
      clearTimer()
      onlineRef.current = false
      setJustReconnected(false)
      setOnline(false)
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      clearTimer()
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [backOnlineMs])

  return { online, justReconnected }
}
