import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import BottomTabBar from './BottomTabBar'

const state = vi.hoisted(() => ({ demo: false }))
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    hasFeature: (feature: string) => feature === 'watch',
    logout: vi.fn(), availableSites: [], activeSiteTenantId: 'shop', switchSite: vi.fn(),
  }),
}))
vi.mock('@/lib/onboarding', () => ({ isDemoModeEnabled: () => state.demo }))
vi.mock('@/hooks/useInboxCount', () => ({ useInboxCount: () => 0 }))
vi.mock('./ChangelogModal', () => ({ default: () => null }))

function Location() {
  const location = useLocation()
  return <output aria-label="Current page">{location.pathname}</output>
}
function show(bookingOnly = false) {
  return render(<MemoryRouter initialEntries={['/accounts']}><BottomTabBar bookingOnly={bookingOnly} /><Location /></MemoryRouter>)
}
beforeEach(() => { state.demo = false })

describe('phone messaging navigation', () => {
  it('gives booking-only Minit shops a direct Messages tab', () => {
    show(true)
    expect(screen.getByRole('link', { name: 'Messages' })).toHaveAttribute('href', '/messages')
    expect(screen.getByRole('link', { name: 'Book mobile' })).toHaveAttribute('href', '/shop-mobile-bookings')
    expect(screen.getByRole('link', { name: 'Inbox' })).toHaveAttribute('href', '/inbox')
    expect(screen.queryByRole('link', { name: 'Home' })).not.toBeInTheDocument()
  })

  it('keeps booking-only More options within the supported shop pages', async () => {
    show(true)
    await userEvent.click(screen.getByRole('button', { name: 'More navigation options' }))
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Customers' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Database' })).not.toBeInTheDocument()
  })

  it('lets standard shop users open Messages from More on a phone', async () => {
    show()
    await userEvent.click(screen.getByRole('button', { name: 'More navigation options' }))
    await userEvent.click(screen.getByRole('button', { name: 'Messages' }))
    expect(screen.getByLabelText('Current page')).toHaveTextContent('/messages')
    expect(screen.queryByRole('button', { name: 'Settings' })).not.toBeInTheDocument()
  })

  it('keeps live network messaging out of the demo menu', async () => {
    state.demo = true
    show()
    await userEvent.click(screen.getByRole('button', { name: 'More navigation options' }))
    expect(screen.queryByRole('button', { name: 'Messages' })).not.toBeInTheDocument()
  })
})
