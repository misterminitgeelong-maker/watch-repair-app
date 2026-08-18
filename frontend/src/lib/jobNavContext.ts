const WATCH_JOBS_NAV_KEY = 'watchJobsNavContext:v1'

/** Remember board/list order so job detail can offer prev/next. */
export function saveWatchJobsNavContext(jobIds: string[]) {
  if (jobIds.length === 0) return
  try {
    sessionStorage.setItem(WATCH_JOBS_NAV_KEY, JSON.stringify(jobIds))
  } catch {
    /* private mode */
  }
}

export function getWatchJobsNavNeighbors(currentId: string): { prevId: string | null; nextId: string | null } {
  try {
    const raw = sessionStorage.getItem(WATCH_JOBS_NAV_KEY)
    if (!raw) return { prevId: null, nextId: null }
    const jobIds = JSON.parse(raw) as string[]
    if (!Array.isArray(jobIds)) return { prevId: null, nextId: null }
    const idx = jobIds.indexOf(currentId)
    if (idx < 0) return { prevId: null, nextId: null }
    return {
      prevId: idx > 0 ? jobIds[idx - 1]! : null,
      nextId: idx < jobIds.length - 1 ? jobIds[idx + 1]! : null,
    }
  } catch {
    return { prevId: null, nextId: null }
  }
}
