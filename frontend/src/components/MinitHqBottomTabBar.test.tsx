import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import MinitHqBottomTabBar from './MinitHqBottomTabBar'

const auth = vi.hoisted(() => ({ logout: vi.fn(), sessionReady: false, initializing: true, hasFeature: () => false }))
vi.mock('@/context/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('@/hooks/useInboxCount', () => ({ useInboxCount: () => 0 }))
// Settings not loaded yet: the menu falls back to the full Minit set.
vi.mock('@/hooks/useHqConfig', async original => ({ ...await original<typeof import('@/hooks/useHqConfig')>(), useHqConfig: () => ({ data: undefined }) }))

beforeEach(() => { auth.logout.mockClear() })

describe('HQ mobile session recovery', () => {
  it.each([false, true])('keeps sign out accessible with sessionReady=%s', async sessionReady => {
    auth.sessionReady = sessionReady
    auth.initializing = !sessionReady
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/minit/dashboard']}><MinitHqBottomTabBar /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'More Minit Support Office pages' }))
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(auth.logout).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
  })
})
