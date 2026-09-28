import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import PlatformAdminPage from './PlatformAdminUsersPage'
import { listPlatformTenants, listPlatformUsers, getPlatformReports, setPlatformTenantStatus, forcePlatformTenantLogout } from '@/lib/api'

vi.mock('@/lib/adminImpersonation', () => ({ useAdminEnterShop: () => ({ enterShop: vi.fn(), entering: '', error: '' }) }))
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  listPlatformTenants: vi.fn(), listPlatformUsers: vi.fn(), getPlatformReports: vi.fn(),
  setPlatformTenantStatus: vi.fn(), forcePlatformTenantLogout: vi.fn(),
}))

const tenants = Array.from({ length: 30 }, (_, i) => ({
  id: `shop-${i}`, slug: `shop-${i}`, name: `Shop ${String(i).padStart(2, '0')}`,
  plan_code: i === 29 ? 'basic_watch' : 'pro', is_active: i !== 29,
  signup_payment_pending: i === 0, billing_exempt: false,
  user_count: 2, created_at: '2026-09-01T00:00:00Z',
}))
const renderPage = (route: string) => renderAtRoute(<PlatformAdminPage />, { path: '/platform-admin/:tab', route })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listPlatformTenants).mockResolvedValue({ data: tenants } as Awaited<ReturnType<typeof listPlatformTenants>>)
  vi.mocked(getPlatformReports).mockRejectedValue(new Error('Offline'))
})

describe('platform console', () => {
  it('shows the overview and links billing follow-ups to the matching shop', async () => {
    renderPage('/platform-admin/overview')
    expect(await screen.findByText('Shops connected')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Review billing/ })).toHaveAttribute('href', '/platform-admin/billing')
    expect(screen.getByRole('link', { name: 'Review' })).toHaveAttribute('href', '/platform-admin/shops?q=shop-0')
    expect(await screen.findByRole('alert')).toHaveTextContent('Activity is unavailable')
  })

  it('paginates shops and resets pagination when filtering', async () => {
    const user = userEvent.setup()
    renderPage('/platform-admin/shops')
    expect(await screen.findByText('1–25 of 30')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByText('26–30 of 30')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Filter shop status'), 'suspended')
    expect(screen.getByText('1–1 of 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Manage Shop 29' })).toBeInTheDocument()
  })

  it('honours a linked shop search and provides the full management controls', async () => {
    const user = userEvent.setup()
    renderPage('/platform-admin/shops?q=shop-0')
    await user.click(await screen.findByRole('button', { name: 'Manage Shop 00' }))
    const dialog = screen.getByRole('dialog')
    for (const name of ['Change Plan', 'Mark Paid', 'Edit', 'Delete Account']) expect(within(dialog).getByRole('button', { name })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it.each(['Suspend', 'Force Logout'])('does not execute %s when the reason prompt is cancelled', async action => {
    const user = userEvent.setup()
    const prompt = vi.spyOn(window, 'prompt').mockReturnValueOnce('shop-0').mockReturnValueOnce(null)
    renderPage('/platform-admin/shops?q=shop-0')
    await user.click(await screen.findByRole('button', { name: 'Manage Shop 00' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: action }))
    expect(setPlatformTenantStatus).not.toHaveBeenCalled()
    expect(forcePlatformTenantLogout).not.toHaveBeenCalled()
    prompt.mockRestore()
  })

  it('shows a failed users request as an error rather than an empty directory', async () => {
    vi.mocked(listPlatformUsers).mockRejectedValue(new Error('Offline'))
    renderPage('/platform-admin/users')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load users')
    expect(screen.queryByText('No users found.')).not.toBeInTheDocument()
  })
})
