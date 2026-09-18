import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isIosSafari, isStandaloneDisplay, readInstallDismissedAt, useInstallPrompt } from './useInstallPrompt'

const ORIGINAL_UA = navigator.userAgent

function setUserAgent(ua: string, maxTouchPoints = 0) {
  Object.defineProperty(navigator, 'userAgent', { value: ua, configurable: true })
  Object.defineProperty(navigator, 'maxTouchPoints', { value: maxTouchPoints, configurable: true })
}

function mockMatchMedia(standalone: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: standalone && query.includes('standalone'),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

/** A stand-in for the browser's beforeinstallprompt event. */
function fireBeforeInstallPrompt(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt') as Event & {
    prompt: () => Promise<void>
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
  }
  event.prompt = vi.fn().mockResolvedValue(undefined)
  event.userChoice = Promise.resolve({ outcome })
  act(() => {
    window.dispatchEvent(event)
  })
  return event
}

describe('useInstallPrompt', () => {
  beforeEach(() => {
    localStorage.clear()
    setUserAgent('Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile')
    mockMatchMedia(false)
  })

  afterEach(() => {
    setUserAgent(ORIGINAL_UA)
  })

  it('offers no install affordance until the platform says it can install', () => {
    const { result } = renderHook(() => useInstallPrompt())
    expect(result.current.canInstall).toBe(false)
    expect(result.current.showInstallAffordance).toBe(false)
  })

  it('shows the affordance once beforeinstallprompt fires', () => {
    const { result } = renderHook(() => useInstallPrompt())
    fireBeforeInstallPrompt()
    expect(result.current.canInstall).toBe(true)
    expect(result.current.showInstallAffordance).toBe(true)
  })

  it('prompts and reports acceptance', async () => {
    const { result } = renderHook(() => useInstallPrompt())
    const event = fireBeforeInstallPrompt('accepted')

    let accepted: boolean | undefined
    await act(async () => {
      accepted = await result.current.promptInstall()
    })
    expect(event.prompt).toHaveBeenCalled()
    expect(accepted).toBe(true)
    expect(result.current.canInstall).toBe(false)
  })

  it('stops offering after the user declines the browser dialog', async () => {
    const { result } = renderHook(() => useInstallPrompt())
    fireBeforeInstallPrompt('dismissed')
    await act(async () => {
      await result.current.promptInstall()
    })
    expect(result.current.dismissed).toBe(true)
    expect(result.current.showInstallAffordance).toBe(false)
    expect(readInstallDismissedAt()).toBe(true)
  })

  it('remembers an explicit dismissal across mounts, so it does not nag', () => {
    const first = renderHook(() => useInstallPrompt())
    act(() => first.result.current.dismissInstallPrompt())
    first.unmount()

    const second = renderHook(() => useInstallPrompt())
    fireBeforeInstallPrompt()
    expect(second.result.current.canInstall).toBe(true)
    expect(second.result.current.showInstallAffordance).toBe(false)
  })

  it('hides the affordance once the app reports itself installed', () => {
    const { result } = renderHook(() => useInstallPrompt())
    fireBeforeInstallPrompt()
    act(() => {
      window.dispatchEvent(new Event('appinstalled'))
    })
    expect(result.current.installed).toBe(true)
    expect(result.current.isStandalone).toBe(true)
    expect(result.current.showInstallAffordance).toBe(false)
  })

  it('offers iOS guidance where beforeinstallprompt never fires', () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari')
    const { result } = renderHook(() => useInstallPrompt())
    expect(result.current.isIos).toBe(true)
    expect(result.current.canInstall).toBe(false)
    expect(result.current.showInstallAffordance).toBe(true)
  })

  it('offers nothing when already running standalone', () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari')
    mockMatchMedia(true)
    const { result } = renderHook(() => useInstallPrompt())
    expect(result.current.isStandalone).toBe(true)
    expect(result.current.showInstallAffordance).toBe(false)
  })
})

describe('platform detection', () => {
  afterEach(() => setUserAgent(ORIGINAL_UA))

  it('treats an iPad in desktop mode as iOS', () => {
    setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari', 5)
    expect(isIosSafari()).toBe(true)
  })

  it('does not treat a real Mac as iOS', () => {
    setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari', 0)
    expect(isIosSafari()).toBe(false)
  })

  it('detects standalone display mode', () => {
    mockMatchMedia(true)
    expect(isStandaloneDisplay()).toBe(true)
    mockMatchMedia(false)
    expect(isStandaloneDisplay()).toBe(false)
  })
})
