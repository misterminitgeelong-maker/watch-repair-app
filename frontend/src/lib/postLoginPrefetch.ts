import type { QueryClient } from '@tanstack/react-query'
import {
  getGstSummary,
  getReportsSummary,
  getReportsTechBreakdown,
  getReportsTrends,
  getTenantActivity,
  listAutoKeyJobs,
  listJobs,
  type FeatureKey,
} from '@/lib/api'
import { WATCH_JOBS_BOARD_QUERY } from '@/lib/queryKeys'

/** Mirrors ReportsPage's own (unexported) todayYmd() — the gst-summary query key includes
 * today's date, so this has to format it identically or the prefetch lands under a different
 * key and ReportsPage just refetches anyway. */
function todayYmd(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Fired once, right as the post-login loading screen mounts (see AppShell) — warms the
 * board-level queries for the sections a shop jumps into most from the dashboard: Watch
 * Repairs, Mobile Services, and Reports. Each call uses the exact same queryKey/queryFn (and,
 * for Reports, the same default filter state — period '6m', sales range 'all') that the
 * destination page itself uses on mount, so when that page actually mounts it finds the data
 * already in cache instead of firing its own fetch.
 *
 * No separate "is this ready" bookkeeping needed here — PostLoginLoadingScreen's global
 * useIsFetching() already counts whatever prefetchQuery kicks off, so the bar simply holds a
 * little longer while these are in flight and hands off once they (and the landing page's own
 * queries) are done.
 *
 * Gated behind hasFeature so a shop without Mobile Services (or without Watch Repairs) doesn't
 * pay for a fetch it has no route to render.
 */
export function prefetchPostLoginRoutes(
  qc: QueryClient,
  hasFeature: (feature: FeatureKey) => boolean,
): void {
  if (hasFeature('watch')) {
    qc.prefetchQuery({
      queryKey: WATCH_JOBS_BOARD_QUERY.key,
      queryFn: () => listJobs(WATCH_JOBS_BOARD_QUERY.params).then((r) => r.data),
    })
  }

  if (hasFeature('auto_key')) {
    qc.prefetchQuery({
      queryKey: ['auto-key-jobs'],
      queryFn: () => listAutoKeyJobs().then((r) => r.data),
    })
  }

  // Reports has no feature gate — every plan can see it — and always mounts at period '6m',
  // sales range 'all'. Match exactly what ReportsPage fetches for that default state.
  const today = todayYmd()
  qc.prefetchQuery({ queryKey: ['reports-summary'], queryFn: () => getReportsSummary().then((r) => r.data) })
  qc.prefetchQuery({ queryKey: ['reports-trends', 6], queryFn: () => getReportsTrends(6).then((r) => r.data) })
  qc.prefetchQuery({ queryKey: ['reports-tech-breakdown'], queryFn: () => getReportsTechBreakdown().then((r) => r.data) })
  qc.prefetchQuery({ queryKey: ['reports-activity'], queryFn: () => getTenantActivity(50).then((r) => r.data) })
  qc.prefetchQuery({
    queryKey: ['reports-gst-summary', 'all', today, today, today],
    queryFn: () => getGstSummary(undefined).then((r) => r.data),
  })
}
