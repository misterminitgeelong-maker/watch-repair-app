/**
 * Pure helpers for RepairQueueModal's queueOrder state.
 *
 * F-H3 regression: the modal previously keyed its queue-seeding effect only
 * on `filteredJobs.length`, so when a filter change produced the same count
 * but a different set of jobs (e.g. 5 "due today" -> 5 "in progress"),
 * queueOrder stayed stale and the UI surfaced the wrong jobs. These helpers
 * are the pure core of the fix: the effect now keys on a stable id-set key
 * and uses `mergeQueueOrder` to preserve manual order for ids still present
 * while appending any newly-present ids in their default sort position.
 */

/** Stable key for a set of ids, order-insensitive. */
export function filteredJobsIdKey(ids: readonly string[]): string {
  return ids.slice().sort().join('|')
}

/**
 * Rebuild queueOrder after a membership change.
 *
 * - Preserves the relative order of ids that are still in `sortedIds`
 *   (so a user's manual drag-reorder stays sticky).
 * - Appends any ids in `sortedIds` that weren't in `previous` in their
 *   sortedIds position, so new rows do appear.
 * - When `previous` is null (first seed), returns sortedIds directly.
 */
export function mergeQueueOrder(
  previous: readonly string[] | null,
  sortedIds: readonly string[],
): string[] {
  if (previous === null) return sortedIds.slice()
  const filteredSet = new Set(sortedIds)
  const kept = previous.filter((id) => filteredSet.has(id))
  const keptSet = new Set(kept)
  const appended = sortedIds.filter((id) => !keptSet.has(id))
  return [...kept, ...appended]
}
