import type { QueryClient } from '@tanstack/react-query'
import {
  getReportsSummary,
  getReportsTechBreakdown,
  listAutoKeyJobs,
  listCustomers,
  listJobs,
} from '@/lib/api'
import { autoKeyJobsListKey } from '@/lib/autoKeyJobQueries'
import { WATCH_JOBS_BOARD_QUERY } from '@/lib/queryKeys'

/** Long enough that the warm-up itself is not immediately re-fetched by the
 * page that lands on it, short enough that a screen opened much later still
 * refreshes. Pages keep their own staleTime, so they still revalidate on
 * mount — the cache is what makes them paint instantly, not what they trust. */
const WARM_STALE_MS = 60_000

/** Which screens this login actually has. Warming a shop's job list for an HQ
 * login would just burn a request on a 403. */
export interface WarmScope {
  watch: boolean
  autoKey: boolean
  reports: boolean
}

/** Pull the data behind the screens people live in — watch repairs, mobile
 * services and reporting — into cache in the background, so opening them
 * paints from cache instead of waiting on a request.
 *
 * Every fetch is allowed to fail: this is an optimisation, and the page's own
 * query is still the thing that reports errors to the user. */
export async function prefetchKeyScreenData(qc: QueryClient, scope: WarmScope): Promise<void> {
  const warm = (queryKey: readonly unknown[], queryFn: () => Promise<unknown>) =>
    qc.prefetchQuery({ queryKey, queryFn, staleTime: WARM_STALE_MS }).catch(() => undefined)

  const jobs: Array<Promise<void>> = []

  if (scope.watch) {
    // The exact key JobsPage opens on, so its first render is a cache hit.
    jobs.push(warm(WATCH_JOBS_BOARD_QUERY.key, () => listJobs(WATCH_JOBS_BOARD_QUERY.params).then(r => r.data)))
  }

  if (scope.autoKey) {
    jobs.push(warm(autoKeyJobsListKey, () => listAutoKeyJobs().then(r => r.data)))
    jobs.push(warm(['customers'], () => listCustomers().then(r => r.data)))
  }

  if (scope.reports) {
    // Only the period-independent panels — the trend charts key off a date
    // range the user picks, so warming one guesses wrong as often as right.
    jobs.push(warm(['reports-summary'], () => getReportsSummary().then(r => r.data)))
    jobs.push(warm(['reports-tech-breakdown'], () => getReportsTechBreakdown().then(r => r.data)))
  }

  await Promise.all(jobs)
}
