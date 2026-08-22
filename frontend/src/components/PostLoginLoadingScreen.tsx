import { useEffect, useRef, useState } from 'react'
import { useIsFetching } from '@tanstack/react-query'
import { useTheme } from '@/context/ThemeContext'

const MIN_VISIBLE_MS = 700 // never flash — feels intentional even when data is already warm
const IDLE_GRACE_MS = 400 // how long "nothing is fetching" must hold before we trust it
const MAX_WAIT_MS = 8000 // hard ceiling — a hung request must never trap the user here

/** Shown once, right after a successful login, over the real destination page — which mounts
 * and fires its normal data queries underneath this overlay. The bar animates toward ~92% on
 * its own (there's no single "total bytes" to measure against), then only jumps to 100% and
 * hands off once React Query genuinely has nothing left in flight, so "100%" always corresponds
 * to the dashboard actually being ready to show. */
export function PostLoginLoadingScreen({ onDone }: { onDone: () => void }) {
  const { theme } = useTheme()
  const isFetching = useIsFetching()
  const [progress, setProgress] = useState(4)
  const startedAt = useRef(Date.now())
  const sawFetchingRef = useRef(false)
  const idleSinceRef = useRef<number | null>(isFetching === 0 ? Date.now() : null)

  useEffect(() => {
    if (isFetching > 0) {
      sawFetchingRef.current = true
      idleSinceRef.current = null
    } else if (idleSinceRef.current === null) {
      idleSinceRef.current = Date.now()
    }
  }, [isFetching])

  // Ease toward 92% and hold — the last stretch to 100% only happens once we know we're done.
  useEffect(() => {
    let raf: number
    const tick = () => {
      setProgress(p => (p < 92 ? p + (92 - p) * 0.06 + 0.15 : p))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  useEffect(() => {
    const check = setInterval(() => {
      const elapsed = Date.now() - startedAt.current
      const idleFor = idleSinceRef.current != null ? Date.now() - idleSinceRef.current : 0
      const settled = sawFetchingRef.current ? isFetching === 0 : idleFor >= IDLE_GRACE_MS
      const forced = elapsed >= MAX_WAIT_MS
      if (forced || (settled && elapsed >= MIN_VISIBLE_MS)) {
        clearInterval(check)
        setProgress(100)
        setTimeout(onDone, 220) // let the bar visibly land on 100% before revealing the page
      }
    }, 100)
    return () => clearInterval(check)
  }, [isFetching, onDone])

  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-5 px-6"
      style={{ backgroundColor: 'var(--ms-bg)' }}
    >
      <img
        src={theme === 'minit' ? '/minit-logo-dark.svg' : '/mainspring-logo.svg'}
        alt=""
        style={{ width: 'clamp(120px, 30vw, 160px)', height: 'auto', objectFit: 'contain' }}
      />
      <div style={{ width: 'min(260px, 70vw)', height: 4, borderRadius: 2, backgroundColor: 'var(--ms-border)', overflow: 'hidden' }}>
        <div
          style={{
            width: `${progress}%`, height: '100%', borderRadius: 2,
            backgroundColor: 'var(--ms-accent)', transition: 'width 150ms linear',
          }}
        />
      </div>
      <p className="text-xs font-medium" style={{ color: 'var(--ms-text-muted)' }}>
        Loading your workspace… {Math.round(progress)}%
      </p>
    </div>
  )
}
