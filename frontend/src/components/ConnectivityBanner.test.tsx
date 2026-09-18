import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ConnectivityBanner from './ConnectivityBanner'
import { BACK_ONLINE_MS } from '@/hooks/useOnlineStatus'

function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true, writable: true })
}

function fireConnectivity(event: 'online' | 'offline') {
  act(() => {
    setOnline(event === 'online')
    window.dispatchEvent(new Event(event))
  })
}

describe('ConnectivityBanner', () => {
  beforeEach(() => {
    setOnline(true)
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    setOnline(true)
  })

  it('stays out of the way while online', () => {
    render(<ConnectivityBanner />)
    expect(screen.queryByTestId('connectivity-banner')).not.toBeInTheDocument()
  })

  it('announces an actionable message when the connection drops', () => {
    render(<ConnectivityBanner />)
    fireConnectivity('offline')

    const banner = screen.getByTestId('connectivity-banner')
    expect(banner).toHaveAttribute('role', 'status')
    expect(banner).toHaveAttribute('aria-live', 'polite')
    expect(banner).toHaveTextContent(/no internet connection/i)
    // Cached screens underneath must stay usable.
    expect(banner).toHaveStyle({ pointerEvents: 'none' })
  })

  it('shows a brief "Back online" state and then clears it', () => {
    render(<ConnectivityBanner />)
    fireConnectivity('offline')
    fireConnectivity('online')

    expect(screen.getByTestId('connectivity-banner')).toHaveTextContent(/back online/i)

    act(() => {
      vi.advanceTimersByTime(BACK_ONLINE_MS + 10)
    })
    expect(screen.queryByTestId('connectivity-banner')).not.toBeInTheDocument()
  })

  it('does not show "Back online" for a duplicate online event', () => {
    render(<ConnectivityBanner />)
    fireConnectivity('online')
    expect(screen.queryByTestId('connectivity-banner')).not.toBeInTheDocument()
  })

  it('returns to the offline message if the connection drops again', () => {
    render(<ConnectivityBanner />)
    fireConnectivity('offline')
    fireConnectivity('online')
    fireConnectivity('offline')
    expect(screen.getByTestId('connectivity-banner')).toHaveTextContent(/no internet connection/i)
  })

  it('renders offline immediately when the app starts with no connection', () => {
    setOnline(false)
    render(<ConnectivityBanner />)
    expect(screen.getByTestId('connectivity-banner')).toHaveTextContent(/no internet connection/i)
  })
})
