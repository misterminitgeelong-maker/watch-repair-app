import { describe, it, expect } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import {
  autoKeyJobsDashboardKey,
  autoKeyJobsDispatchPrefix,
  autoKeyJobsListKey,
  invalidateAutoKeyDispatchBoard,
  invalidateAutoKeyJobCollections,
  invalidateAutoKeyScheduleViews,
} from './autoKeyJobQueries'

function seed(qc: QueryClient) {
  qc.setQueryData([...autoKeyJobsListKey], [])
  qc.setQueryData([...autoKeyJobsDispatchPrefix, '2026-01-01', '', 'single-day'], [])
  qc.setQueryData([...autoKeyJobsDashboardKey], [])
  qc.setQueryData(['auto-key-jobs', 'week', '2026-01-05', '2026-01-11'], [])
  qc.setQueryData(['auto-key-jobs', 'customer', 'cust-1'], [])
}

describe('auto-key job query invalidation', () => {
  it('does not treat the jobs list as the collection prefix', () => {
    expect(autoKeyJobsListKey).toEqual(['auto-key-jobs', 'list'])
  })

  it('visit-order invalidation leaves list, week, and dashboard fresh', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    seed(qc)
    invalidateAutoKeyDispatchBoard(qc)
    expect(qc.getQueryState(autoKeyJobsListKey)?.isInvalidated).toBe(false)
    expect(qc.getQueryState(autoKeyJobsDashboardKey)?.isInvalidated).toBe(false)
    expect(qc.getQueryState(['auto-key-jobs', 'week', '2026-01-05', '2026-01-11'])?.isInvalidated).toBe(false)
    expect(qc.getQueryState([...autoKeyJobsDispatchPrefix, '2026-01-01', '', 'single-day'])?.isInvalidated).toBe(true)
  })

  it('week reschedule does not refetch the jobs list', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    seed(qc)
    invalidateAutoKeyScheduleViews(qc)
    expect(qc.getQueryState(autoKeyJobsListKey)?.isInvalidated).toBe(false)
    expect(qc.getQueryState(['auto-key-jobs', 'week', '2026-01-05', '2026-01-11'])?.isInvalidated).toBe(true)
    expect(qc.getQueryState(autoKeyJobsDashboardKey)?.isInvalidated).toBe(true)
  })

  it('collection invalidation hits list and dispatch without using the bare prefix', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    seed(qc)
    invalidateAutoKeyJobCollections(qc)
    expect(qc.getQueryState(autoKeyJobsListKey)?.isInvalidated).toBe(true)
    expect(qc.getQueryState([...autoKeyJobsDispatchPrefix, '2026-01-01', '', 'single-day'])?.isInvalidated).toBe(true)
    expect(qc.getQueryState(['auto-key-jobs', 'customer', 'cust-1'])?.isInvalidated).toBe(true)
  })
})
