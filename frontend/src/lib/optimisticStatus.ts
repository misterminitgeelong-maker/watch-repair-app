import type { QueryClient, QueryKey } from '@tanstack/react-query'

/** What was in the cache before an optimistic move, so a failed request can put it back. */
export type StatusSnapshot = Array<[QueryKey, unknown]>

interface JobLike {
  id: string
  status: string
}

function isJobArray(value: unknown): value is JobLike[] {
  return Array.isArray(value) && value.every(item => typeof item === 'object' && item !== null && 'id' in item)
}

/** Rewrite one job's status wherever it appears in a cached payload, leaving
 * anything we do not recognise untouched. Handles both a plain list and the
 * paged `{ items, total, ... }` shape. */
function withStatus(data: unknown, jobId: string, status: string): unknown {
  if (isJobArray(data)) {
    let changed = false
    const next = data.map(job => {
      if (job.id !== jobId || job.status === status) return job
      changed = true
      return { ...job, status }
    })
    return changed ? next : data
  }
  if (data && typeof data === 'object' && 'items' in data) {
    const page = data as { items: unknown }
    const items = withStatus(page.items, jobId, status)
    return items === page.items ? data : { ...data, items }
  }
  return data
}

/** Move a job to its new status in every cached list under `rootKey`, so the
 * board redraws on drop instead of after the round-trip. Returns a snapshot to
 * hand back to `rollbackStatus` if the request fails.
 *
 * In-flight fetches are cancelled first: one that resolves after this would
 * overwrite the optimistic move with the pre-move server state, and the card
 * would visibly jump back. */
export async function applyOptimisticStatus(
  qc: QueryClient,
  rootKey: QueryKey,
  jobId: string,
  status: string,
): Promise<StatusSnapshot> {
  await qc.cancelQueries({ queryKey: rootKey })
  const snapshot: StatusSnapshot = []
  for (const [key, data] of qc.getQueriesData({ queryKey: rootKey })) {
    const next = withStatus(data, jobId, status)
    if (next === data) continue
    snapshot.push([key, data])
    qc.setQueryData(key, next)
  }
  return snapshot
}

export function rollbackStatus(qc: QueryClient, snapshot: StatusSnapshot | undefined): void {
  if (!snapshot) return
  for (const [key, data] of snapshot) qc.setQueryData(key, data)
}
