/**
 * The one definition of an "active" job, per service line.
 *
 * The dashboard and the job directories used to count differently (the
 * dashboard dropped completed / awaiting-collection jobs, the Watch directory
 * kept them), so "Watch: 7 active" sat next to "Active (11)". Every count of
 * active jobs goes through these helpers so the numbers always agree.
 *
 * Watch: active until the watch is collected. Completed and awaiting-collection
 * watches are still in the shop, and a No Go still needs the customer contacted.
 */
import { CLOSED_DIRECTORY_STATUSES } from '@/lib/utils'
import { MOBILE_ACTIVE_STATUSES, MOBILE_CLOSED_STATUSES } from '@/lib/mobileStatus'

export const WATCH_CLOSED_STATUSES: readonly string[] = CLOSED_DIRECTORY_STATUSES

export const SHOE_ACTIVE_STATUSES: readonly string[] = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'working_on']
export const SHOE_CLOSED_STATUSES: readonly string[] = ['completed', 'awaiting_collection', 'collected', 'no_go']

export { MOBILE_ACTIVE_STATUSES, MOBILE_CLOSED_STATUSES }

export function isActiveWatchStatus(status: string): boolean {
  return !WATCH_CLOSED_STATUSES.includes(status)
}

export function isActiveShoeStatus(status: string): boolean {
  return SHOE_ACTIVE_STATUSES.includes(status)
}

export function isActiveMobileStatus(status: string): boolean {
  return !(MOBILE_CLOSED_STATUSES as readonly string[]).includes(status)
}

/** Active watch jobs from a `{status: count}` summary (reports `jobs_by_status`). */
export function countActiveWatchJobs(jobsByStatus: Record<string, number> | undefined | null): number {
  if (!jobsByStatus) return 0
  return Object.entries(jobsByStatus).reduce((sum, [status, n]) => (isActiveWatchStatus(status) ? sum + n : sum), 0)
}
