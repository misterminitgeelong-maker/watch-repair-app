import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import HqShoeRepairsPage from './HqShoeRepairsPage'
import { getHqShoeSummary, searchHqShoeJobs } from '@/lib/api'

vi.mock('@/lib/api', async original => ({ ...await original<typeof import('@/lib/api')>(), getHqShoeSummary: vi.fn(), searchHqShoeJobs: vi.fn() }))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getHqShoeSummary).mockResolvedValue({ data: {
    from_date: null, to_date: null, status_counts: {},
    totals: { shops: 2, opened: 5, active: 3, ready_to_collect: 1, collected: 2, billed_cents: 21000, avg_turnaround_days: 4 },
    by_shop: [
      { tenant_id: 'a', tenant_name: 'Chadstone', tenant_slug: 'a', region: 'VIC', opened: 3, active: 2, ready_to_collect: 1, collected: 1, billed_cents: 17000, avg_turnaround_days: 4, oldest_active_days: 10 },
      { tenant_id: 'b', tenant_name: 'Bondi', tenant_slug: 'b', region: null, opened: 2, active: 1, ready_to_collect: 0, collected: 1, billed_cents: 4000, avg_turnaround_days: null, oldest_active_days: null },
    ],
  } } as unknown as Awaited<ReturnType<typeof getHqShoeSummary>>)
  vi.mocked(searchHqShoeJobs).mockResolvedValue({ data: { has_more: false, jobs: [
    { id: 'j1', job_number: 'SHO-00001', status: 'working_on', title: 'Resole', tenant_id: 'a', tenant_name: 'Chadstone', region: 'VIC', customer_name: 'Anna Walker', shoe: 'Birkenstock sandals', created_at: '2026-10-01T00:00:00Z', age_days: 8 },
  ] } } as unknown as Awaited<ReturnType<typeof searchHqShoeJobs>>)
})

describe('HQ shoe repairs', () => {
  it('shows network totals and a row per shop', async () => {
    renderAtRoute(<HqShoeRepairsPage />, { path: '/minit/shoe-repairs', route: '/minit/shoe-repairs' })
    const shops = await screen.findAllByText('Chadstone', { selector: 'td' })
    expect(shops.length).toBeGreaterThan(0)
    expect(screen.getByText('Bondi', { selector: 'td' })).toBeInTheDocument()
    expect(screen.getByText('$210.00')).toBeInTheDocument()
  })

  it('searches the whole network by what the user types', async () => {
    const user = userEvent.setup()
    renderAtRoute(<HqShoeRepairsPage />, { path: '/minit/shoe-repairs', route: '/minit/shoe-repairs' })
    await user.type(await screen.findByLabelText('Ticket number, customer name or phone'), 'walker')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(searchHqShoeJobs).toHaveBeenLastCalledWith({ q: 'walker', limit: 50 }))
    expect(await screen.findByText('Anna Walker')).toBeInTheDocument()
  })
})
