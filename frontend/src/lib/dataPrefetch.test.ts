import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { prefetchKeyScreenData } from './dataPrefetch'
import { WATCH_JOBS_BOARD_QUERY } from './queryKeys'
import { autoKeyJobsListKey } from './autoKeyJobQueries'

vi.mock('@/lib/api', () => ({
  // queryKeys.ts imports this from the same module, so the mock has to carry it.
  WATCH_JOBS_LIST_MAX: 200,
  listJobs: vi.fn(async () => ({ data: [{ id: 'watch-1' }] })),
  listAutoKeyJobs: vi.fn(async () => ({ data: [{ id: 'mobile-1' }] })),
  listCustomers: vi.fn(async () => ({ data: [] })),
  getReportsSummary: vi.fn(async () => ({ data: { total: 1 } })),
  getReportsTechBreakdown: vi.fn(async () => ({ data: [] })),
}))

const api = await import('@/lib/api')

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

describe('prefetchKeyScreenData', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fills the cache under the exact keys those pages read', async () => {
    const qc = client()
    await prefetchKeyScreenData(qc, { watch: true, autoKey: true, reports: true })

    // If a key drifts from the page's own, the warm-up silently stops working.
    expect(qc.getQueryData(WATCH_JOBS_BOARD_QUERY.key)).toEqual([{ id: 'watch-1' }])
    expect(qc.getQueryData(autoKeyJobsListKey)).toEqual([{ id: 'mobile-1' }])
    expect(qc.getQueryData(['reports-summary'])).toEqual({ total: 1 })
  })

  it('only warms what the login actually has', async () => {
    const qc = client()
    await prefetchKeyScreenData(qc, { watch: false, autoKey: true, reports: false })

    expect(api.listJobs).not.toHaveBeenCalled()
    expect(api.getReportsSummary).not.toHaveBeenCalled()
    expect(api.listAutoKeyJobs).toHaveBeenCalledTimes(1)
  })

  it('never rejects when an endpoint fails', async () => {
    vi.mocked(api.listJobs).mockRejectedValueOnce(new Error('503'))
    const qc = client()

    // A warm-up is an optimisation — a failure here must not surface as an
    // unhandled rejection or stop the other screens warming.
    await expect(
      prefetchKeyScreenData(qc, { watch: true, autoKey: false, reports: true }),
    ).resolves.toBeUndefined()
    expect(qc.getQueryData(['reports-summary'])).toEqual({ total: 1 })
  })
})
