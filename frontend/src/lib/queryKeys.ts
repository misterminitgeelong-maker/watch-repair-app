import { WATCH_JOBS_LIST_MAX, type SortDir } from '@/lib/api'

/** Default watch jobs board fetch — shared by JobsPage and RepairQueueModal so cache is reused. */
export const WATCH_JOBS_BOARD_QUERY = {
  key: ['jobs', 'all', undefined, null, 'created_at', 'desc', false] as const,
  params: {
    limit: WATCH_JOBS_LIST_MAX,
    offset: 0,
    sort_by: 'created_at' as const,
    sort_dir: 'desc' as SortDir,
  },
}

export function watchJobsListQueryKey(opts?: {
  status?: string
  assignedUserId?: string | null
  sortBy?: string
  sortDir?: SortDir
  costOutlierOnly?: boolean
}) {
  return [
    'jobs',
    'all',
    opts?.status,
    opts?.assignedUserId ?? null,
    opts?.sortBy ?? 'created_at',
    opts?.sortDir ?? 'desc',
    opts?.costOutlierOnly ?? false,
  ] as const
}
