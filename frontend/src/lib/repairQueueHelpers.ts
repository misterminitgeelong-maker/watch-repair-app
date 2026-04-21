/**
 * Pure helpers for RepairQueueModal extracted so they can be unit-tested
 * without rendering the 1000-line modal. `queueOrder.ts` already extracted
 * the merge logic; this file adds the day-queue localStorage + sort / urgency
 * helpers.
 */

export interface QueueJobForSort {
  id: string
  priority: string
  status: string
  created_at: string
  collection_date?: string
}

export interface SessionStats {
  advanced: number
  checkedIn: number
  skipped: number
}

const PRIORITY_ORDER: Record<string, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
}

/** Collection urgency buckets: 0 = overdue, 1 = today, 2 = tomorrow, 3 = later / unset. */
export function getCollectionUrgency(collectionDate?: string): number {
  if (!collectionDate) return 3
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const d = new Date(collectionDate)
  if (d < today) return 0
  if (d <= today) return 1
  if (d <= tomorrow) return 2
  return 3
}

/** Sort the queue: most urgent collection first, then priority, then oldest intake. */
export function sortQueue<T extends QueueJobForSort>(jobs: T[]): T[] {
  return [...jobs].sort((a, b) => {
    const cu = getCollectionUrgency(a.collection_date) - getCollectionUrgency(b.collection_date)
    if (cu !== 0) return cu
    const pu = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99)
    if (pu !== 0) return pu
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })
}

export function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

/** Local calendar date key for offline cache only (browser). Server uses tenant tz. */
export function getLocalDateKey(now: Date = new Date()): string {
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function dayQueueStorageKey(mode: 'watch' | 'shoe'): string {
  return `repairQueueDay:v1:${mode}:${getLocalDateKey()}`
}

export function readDayQueueState(mode: 'watch' | 'shoe'): {
  done: Set<string>
  stats: SessionStats
} {
  const emptyStats: SessionStats = { advanced: 0, checkedIn: 0, skipped: 0 }
  try {
    const raw = localStorage.getItem(dayQueueStorageKey(mode))
    if (!raw) return { done: new Set(), stats: emptyStats }
    const o = JSON.parse(raw) as { doneIds?: string[]; stats?: Partial<SessionStats> }
    const stats: SessionStats = {
      advanced: typeof o.stats?.advanced === 'number' ? o.stats.advanced : 0,
      checkedIn: typeof o.stats?.checkedIn === 'number' ? o.stats.checkedIn : 0,
      skipped: typeof o.stats?.skipped === 'number' ? o.stats.skipped : 0,
    }
    return { done: new Set(Array.isArray(o.doneIds) ? o.doneIds : []), stats }
  } catch {
    return { done: new Set(), stats: emptyStats }
  }
}

export function writeDayQueueState(
  mode: 'watch' | 'shoe',
  done: Set<string>,
  stats: SessionStats,
): void {
  try {
    localStorage.setItem(
      dayQueueStorageKey(mode),
      JSON.stringify({ doneIds: [...done], stats }),
    )
  } catch {
    // ignore quota / private browsing
  }
}
