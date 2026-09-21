import { describe, it, expect, vi, beforeEach } from 'vitest'
import { lazyPage, prefetchAllPages, whenIdle, __resetPrefetchForTests } from './routePrefetch'

describe('routePrefetch', () => {
  beforeEach(() => {
    __resetPrefetchForTests()
  })

  it('warms every registered chunk exactly once', async () => {
    const first = vi.fn(async () => ({ default: () => null }))
    const second = vi.fn(async () => ({ default: () => null }))
    lazyPage(first)
    lazyPage(second)

    await prefetchAllPages()
    expect(first).toHaveBeenCalledTimes(1)
    expect(second).toHaveBeenCalledTimes(1)

    // A second trigger (remount, another idle callback) must not re-download.
    await prefetchAllPages()
    expect(first).toHaveBeenCalledTimes(1)
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('keeps going when a chunk fails to load', async () => {
    // A stale tab after a deploy: the old hashed filename is gone.
    const missing = vi.fn(async () => { throw new Error('404 loading chunk') })
    const healthy = vi.fn(async () => ({ default: () => null }))
    lazyPage(missing as never)
    lazyPage(healthy)

    await expect(prefetchAllPages()).resolves.toBeUndefined()
    expect(healthy).toHaveBeenCalledTimes(1)
  })

  it('falls back to a timer when requestIdleCallback is missing', () => {
    vi.useFakeTimers()
    const original = window.requestIdleCallback
    // @ts-expect-error — simulating an older Safari
    delete window.requestIdleCallback
    try {
      const fn = vi.fn()
      whenIdle(fn)
      expect(fn).not.toHaveBeenCalled()
      vi.advanceTimersByTime(250)
      expect(fn).toHaveBeenCalledTimes(1)
    } finally {
      window.requestIdleCallback = original
      vi.useRealTimers()
    }
  })

  it('cancels a pending warm-up when the shell unmounts first', () => {
    vi.useFakeTimers()
    const original = window.requestIdleCallback
    // @ts-expect-error — simulating an older Safari
    delete window.requestIdleCallback
    try {
      const fn = vi.fn()
      whenIdle(fn)()
      vi.advanceTimersByTime(250)
      expect(fn).not.toHaveBeenCalled()
    } finally {
      window.requestIdleCallback = original
      vi.useRealTimers()
    }
  })
})

describe('App route registration', () => {
  it('registers every lazily-loaded page for warm-up', async () => {
    // Importing App evaluates its lazyPage() calls as a side effect. If someone
    // adds a route with a bare React.lazy, it silently misses the warm-up and
    // that screen goes back to loading its chunk on first navigation.
    __resetPrefetchForTests()
    await import('@/App')
    const { __registeredPageCount } = await import('./routePrefetch')
    expect(__registeredPageCount()).toBeGreaterThanOrEqual(60)
  })
})


describe('recovering from a deploy that renamed the chunks', () => {
  const chunkError = () =>
    new TypeError('Failed to fetch dynamically imported module: https://x/assets/Page-abc.js')

  let reload: ReturnType<typeof vi.fn>

  beforeEach(() => {
    __resetPrefetchForTests()
    sessionStorage.clear()
    reload = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...window.location, reload },
    })
  })

  /** lazyPage returns a React.lazy component; reach its loader without React. */
  function loaderOf(component: unknown): () => Promise<unknown> {
    return (component as { _payload: { _result: () => Promise<unknown> } })._payload._result
  }

  it('reloads once so the tab picks up the current chunk names', async () => {
    const factory = vi.fn(async () => {
      throw chunkError()
    })
    const load = loaderOf(lazyPage(factory as never))

    // Never settles: the reload is what resolves this for the user.
    let settled = false
    void load().then(
      () => { settled = true },
      () => { settled = true },
    )
    await Promise.resolve()
    await Promise.resolve()

    expect(reload).toHaveBeenCalledTimes(1)
    expect(settled).toBe(false)
  })

  it('gives up after one reload instead of boot-looping', async () => {
    sessionStorage.setItem('ms.chunkReload.v1', '1')
    const factory = vi.fn(async () => {
      throw chunkError()
    })
    const load = loaderOf(lazyPage(factory as never))

    await expect(load()).rejects.toThrow(/dynamically imported module/)
    expect(reload).not.toHaveBeenCalled()
  })

  it('leaves a genuine error from the module alone', async () => {
    const factory = vi.fn(async () => {
      throw new Error('boom in module top-level code')
    })
    const load = loaderOf(lazyPage(factory as never))

    await expect(load()).rejects.toThrow('boom in module top-level code')
    expect(reload).not.toHaveBeenCalled()
  })

  it('clears the flag on a good load, so a later deploy can recover too', async () => {
    sessionStorage.setItem('ms.chunkReload.v1', '1')
    const load = loaderOf(lazyPage(async () => ({ default: () => null })))

    await load()
    expect(sessionStorage.getItem('ms.chunkReload.v1')).toBeNull()
  })
})
