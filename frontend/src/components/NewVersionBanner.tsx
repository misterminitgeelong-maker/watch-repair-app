import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { APP_BUILD_ID } from '@/lib/buildInfo'
import { hardReload } from '@/lib/routePrefetch'

const CHECK_INTERVAL_MS = 5 * 60 * 1000

async function fetchDeployedBuildId(): Promise<string | null> {
  try {
    const res = await fetch('/index.html', { cache: 'no-store' })
    if (!res.ok) return null
    const html = await res.text()
    const m = html.match(/<meta\s+name="app-build"\s+content="([^"]*)"/i)
    return m ? m[1] : null
  } catch {
    return null
  }
}

/**
 * The SPA keeps running the JS it loaded until the page reloads, so a deploy
 * never reaches an open tab. Poll the (no-cache) index.html for the build id,
 * show a reload banner when it differs, and reload on the next navigation so
 * nobody loses a half-filled form mid-screen.
 */
export default function NewVersionBanner() {
  const [stale, setStale] = useState(false)
  const location = useLocation()
  const firstPath = useRef(location.pathname + location.search)

  const check = useCallback(async () => {
    if (APP_BUILD_ID === 'dev') return
    const deployed = await fetchDeployedBuildId()
    if (deployed && deployed !== 'dev' && deployed !== APP_BUILD_ID) setStale(true)
  }, [])

  useEffect(() => {
    void check()
    const timer = window.setInterval(() => void check(), CHECK_INTERVAL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [check])

  // Navigating is a safe moment to swap in the new build.
  useEffect(() => {
    const here = location.pathname + location.search
    if (stale && here !== firstPath.current) hardReload()
  }, [stale, location.pathname, location.search])

  if (!stale) return null
  return (
    <div
      role="status"
      className="fixed bottom-4 left-1/2 z-[100] flex -translate-x-1/2 items-center gap-3 rounded-lg bg-stone-900 px-4 py-2 text-sm text-white shadow-lg"
    >
      <span>A new version of Mainspring is available.</span>
      <button
        type="button"
        className="rounded bg-white px-2 py-1 font-medium text-stone-900"
        onClick={() => hardReload()}
      >
        Reload
      </button>
    </div>
  )
}
