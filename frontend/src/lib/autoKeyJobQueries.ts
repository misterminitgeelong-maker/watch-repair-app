import type { QueryClient } from '@tanstack/react-query'

/**
 * TanStack Query keys for Mobile Services job collections.
 *
 * The list used to live at the prefix `['auto-key-jobs']`. Invalidating that
 * prefix also refetched dispatch, week, dashboard, and every other child —
 * dragging five jobs on the dispatch board became 20+ refetches.
 */
export const autoKeyJobsListKey = ['auto-key-jobs', 'list'] as const
export const autoKeyJobsDispatchPrefix = ['auto-key-jobs', 'dispatch'] as const
export const autoKeyJobsWeekPrefix = ['auto-key-jobs', 'week'] as const
export const autoKeyJobsDashboardKey = ['auto-key-jobs', 'dashboard'] as const

function invalidate(qc: QueryClient, queryKey: readonly unknown[]) {
  void qc.invalidateQueries({ queryKey })
}

/** Job rows changed in a way every collection should notice (create / delete / status). */
export function invalidateAutoKeyJobCollections(qc: QueryClient) {
  invalidate(qc, autoKeyJobsListKey)
  invalidate(qc, autoKeyJobsDispatchPrefix)
  invalidate(qc, autoKeyJobsWeekPrefix)
  invalidate(qc, autoKeyJobsDashboardKey)
  invalidate(qc, ['auto-key-jobs', 'customer'])
  invalidate(qc, ['auto-key-jobs', 'active'])
  invalidate(qc, ['auto-key-jobs', 'tomorrow-count'])
  invalidate(qc, ['auto-key-jobs', 'page'])
  invalidate(qc, ['auto-key-cockpit'])
  void qc.invalidateQueries({
    predicate: (q) => q.queryKey[0] === 'auto-key-jobs' && q.queryKey[2] === 'planner-detail',
  })
}

/** Visit-order / route edits only live on the dispatch board. */
export function invalidateAutoKeyDispatchBoard(qc: QueryClient) {
  invalidate(qc, autoKeyJobsDispatchPrefix)
}

/** Reschedule on the week grid: week + dispatch + dashboard, not the jobs list. */
export function invalidateAutoKeyScheduleViews(qc: QueryClient) {
  invalidate(qc, autoKeyJobsWeekPrefix)
  invalidate(qc, autoKeyJobsDispatchPrefix)
  invalidate(qc, autoKeyJobsDashboardKey)
}
