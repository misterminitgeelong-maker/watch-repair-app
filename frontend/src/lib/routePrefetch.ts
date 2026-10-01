import { lazy, type ComponentType } from 'react'

/** Every route chunk's import thunk, in the order App.tsx declares them — which
 * is roughly how often they get used, so the warm-up front-loads the screens
 * people actually open. */
const factories: Array<() => Promise<unknown>> = []

let started = false

/** Reload after dropping the service worker and its caches. */
export function hardReload(): void {
  const cleanup = async () => {
    try {
      if ('serviceWorker' in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations()
        await Promise.all(regs.map(r => r.unregister()))
      }
      if ('caches' in window) {
        const keys = await caches.keys()
        await Promise.all(keys.filter(k => k.startsWith('mainspring-')).map(k => caches.delete(k)))
      }
    } catch {
      /* best effort — still reload */
    }
  }
  let reloaded = false
  const reload = () => {
    if (reloaded) return
    reloaded = true
    window.location.reload()
  }
  const deadline = window.setTimeout(reload, 1500)
  void cleanup().finally(() => { window.clearTimeout(deadline); reload() })
}

/** A rejected import must settle; Suspense must never wait indefinitely. */
async function loadChunk<T>(factory: () => Promise<T>): Promise<T> {
  return factory()
}

/** Drop-in for React.lazy that also registers the chunk for post-login warm-up.
 * Calling the factory a second time does not re-download: the browser's module
 * cache (and React.lazy's own) both dedupe it. */
// Mirrors React.lazy's own generic, so every page type flows through unchanged.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lazyPage<T extends ComponentType<any>>(
  factory: () => Promise<{ default: T }>,
) {
  // The bare factory is what the warm-up uses: it must never trigger a reload,
  // since it runs in the background against pages nobody asked for.
  factories.push(factory)
  return lazy(() => loadChunk(factory))
}

/** Resolves the next time the browser has nothing better to do. */
function nextIdle(): Promise<void> {
  return new Promise(resolve => {
    const ric = (window as typeof window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number
    }).requestIdleCallback
    if (typeof ric === 'function') ric(() => resolve(), { timeout: 1000 })
    else window.setTimeout(resolve, 0)
  })
}

/** Pull every route chunk into cache in the background. Safe to call more than
 * once — only the first call does the work.
 *
 * One at a time, each waiting for an idle moment first. A dynamic import does
 * not merely download a chunk, it evaluates it, so running these back to back
 * put a long stretch of main-thread work right where someone has just started
 * using the app — enough to make scrolling stutter. Idle-gating means the warm
 * up takes longer overall and never competes with what the user is doing,
 * which is the right trade for something they should never notice.
 *
 * Deliberately not tied to the post-login gate's own completion check: that
 * waits on React Query, and these are module imports, so warming chunks can
 * never hold the gate open or push it into its 8s ceiling. */
export async function prefetchAllPages(): Promise<void> {
  if (started) return
  started = true
  for (const factory of factories) {
    await nextIdle()
    try {
      // A chunk that 404s (a stale tab after a deploy renames every file) must
      // not stop the rest — the real navigation surfaces it through the router.
      await factory()
    } catch {
      // ignored on purpose
    }
  }
}

/** Run `fn` when the browser is next idle, falling back to a timer on Safari
 * versions without requestIdleCallback. Returns a cancel function. */
export function whenIdle(fn: () => void, timeoutMs = 2000): () => void {
  const ric = (window as typeof window & {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number
    cancelIdleCallback?: (handle: number) => void
  })
  if (typeof ric.requestIdleCallback === 'function') {
    const handle = ric.requestIdleCallback(fn, { timeout: timeoutMs })
    return () => ric.cancelIdleCallback?.(handle)
  }
  const handle = window.setTimeout(fn, 200)
  return () => window.clearTimeout(handle)
}

/** How many chunks are registered — lets a test prove App.tsx's routes all
 * arrived here, rather than trusting that every lazy() got converted. */
export function __registeredPageCount(): number {
  return factories.length
}

/** Test seam — the registry is module-level and would otherwise leak between tests. */
export function __resetPrefetchForTests(): void {
  factories.length = 0
  started = false
}
