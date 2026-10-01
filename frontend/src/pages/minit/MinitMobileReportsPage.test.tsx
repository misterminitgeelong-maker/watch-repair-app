import { beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { renderAtRoute } from '@/test/renderPage'
import MinitMobileReportsPage from './MinitMobileReportsPage'
import { getParentMobileKpiPeriod, getParentMobileJobsReport } from '@/lib/api'

vi.mock('@/hooks/useParentAccount', () => ({ useParentAccount: () => ({ data: { my_role: 'hq_viewer' } }) }))
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  getParentMobileKpisLive: vi.fn().mockResolvedValue({ data: {} }),
  getParentMobileKpiDays: vi.fn().mockResolvedValue({ data: { days: [] } }),
  getParentMobileKpiPeriod: vi.fn(),
  getParentMobileJobsReport: vi.fn().mockResolvedValue({ data: { jobs: [], total_count: 0, active_count: 0 } }),
  getParentEmailLeadsByShopReport: vi.fn().mockResolvedValue({ data: { shops: [] } }),
}))

const row = {
  operator_tenant_id: 'retail-3269', operator_name: 'Mister Minit Chadstone', operator_shop_number: '3269',
  sales_cents: 12300, jobs_created: 1, jobs_completed: 1, customers_count: 1,
  active_jobs: 5, outstanding_cents: 999900, enquiries_not_actioned: 0,
}
const period = {
  start: '2025-03-31T13:00:00Z', end: '2025-04-30T13:59:59.999999Z',
  start_ymd: '2025-04-01', end_ymd: '2025-04-30', timezone: 'Australia/Sydney',
  generated_at: '2026-10-01T04:00:00Z', network: row, operators: [row],
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getParentMobileKpiPeriod).mockResolvedValue({ data: period } as unknown as Awaited<ReturnType<typeof getParentMobileKpiPeriod>>)
})

it('uses the Minit year for all four periods and drills using exact Sydney boundaries', async () => {
  renderAtRoute(<MinitMobileReportsPage />, { path: '/minit/mobile-reports', route: '/minit/mobile-reports' })
  fireEvent.click(screen.getByRole('button', { name: 'Monthly / yearly' }))
  await screen.findByText(/Minit year: 1 April/)
  fireEvent.change(screen.getByLabelText('Month within reporting period'), { target: { value: '2025-04' } })
  await waitFor(() => expect(getParentMobileKpiPeriod).toHaveBeenLastCalledWith({ period: 'month', anchor: '2025-04-01', year_start_month: 4 }))
  for (const [label, key] of [['Quarterly', 'quarter'], ['6 months', 'half_year'], ['Yearly', 'year']]) {
    fireEvent.click(screen.getByRole('button', { name: label }))
    await waitFor(() => expect(getParentMobileKpiPeriod).toHaveBeenLastCalledWith({ period: key, anchor: '2025-04-01', year_start_month: 4 }))
  }
  const drill = await screen.findByRole('button', { name: /Mister Minit Chadstone/ })
  expect(screen.queryByText(/5 active/)).not.toBeInTheDocument()
  fireEvent.click(drill)
  await waitFor(() => expect(getParentMobileJobsReport).toHaveBeenCalledWith(expect.objectContaining({
    operator_tenant_id: 'retail-3269', from_date: period.start, to_date: period.end,
  })))
})
