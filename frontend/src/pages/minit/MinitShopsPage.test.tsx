import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderAtRoute } from '@/test/renderPage'
import MinitShopsPage from './MinitShopsPage'
import { getMyParentAccount, listParentAccountSites, listRegions } from '@/lib/api'

vi.mock('@/components/MinitShopImport', () => ({ MinitShopImport: () => null }))
vi.mock('@/components/MinitDirectoryImport', () => ({ MinitDirectoryImport: () => null }))
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  getMyParentAccount: vi.fn(),
  listParentAccountSites: vi.fn(),
  listRegions: vi.fn(),
}))

type SitesResponse = Awaited<ReturnType<typeof listParentAccountSites>>
const renderPage = () => renderAtRoute(<MinitShopsPage />, { path: '/minit/shops', route: '/minit/shops' })

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getMyParentAccount).mockResolvedValue({ data: { site_count: 120 } } as Awaited<ReturnType<typeof getMyParentAccount>>)
  vi.mocked(listRegions).mockResolvedValue({ data: [] } as unknown as Awaited<ReturnType<typeof listRegions>>)
})

describe('Minit HQ shops', () => {
  it('says the shop list failed to load instead of showing no shops', async () => {
    vi.mocked(listParentAccountSites).mockRejectedValue(new Error('Offline'))
    renderPage()
    const alerts = await screen.findAllByRole('alert')
    expect(alerts.map(a => a.textContent).join(' ')).toMatch(/Could not load shops/)
    expect(screen.queryByText(/No shops match your filters/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Try again' }).length).toBeGreaterThan(0)
  })

  it('asks for every mobile van, not just the first 50', async () => {
    vi.mocked(listParentAccountSites).mockResolvedValue({ data: { sites: [], total: 0 } } as unknown as SitesResponse)
    renderPage()
    await screen.findByText(/No retail shops linked yet/)
    const operatorCall = vi.mocked(listParentAccountSites).mock.calls.find(([p]) => p?.plan_kind === 'operator')
    expect(operatorCall?.[0]?.limit).toBe(500)
  })
})
