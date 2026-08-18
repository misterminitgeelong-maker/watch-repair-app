/** Persist list/board filter preferences per module in localStorage. */

export function loadSavedView<T extends object>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return { ...fallback, ...JSON.parse(raw) as T }
  } catch {
    return fallback
  }
}

export function saveSavedView<T extends object>(key: string, value: T) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore quota */
  }
}

export const AUTO_KEY_VIEWS_KEY = 'ms-saved-view-auto-key'
export const WATCH_JOBS_VIEWS_KEY = 'ms-saved-view-watch-jobs'
export const SHOE_JOBS_VIEWS_KEY = 'ms-saved-view-shoe-jobs'

export type AutoKeySavedView = {
  view?: string
  jobDirectoryView?: string
  statusFilter?: string
  jobsLayout?: string
  mapRangeMode?: string
}

export type WatchJobsSavedView = {
  jobDirectoryView?: 'active' | 'completed'
  statusFilter?: string
  view?: 'board' | 'list'
  assignedUserId?: string
  costOutlierOnly?: boolean
  olderThanDays?: number
  pastCollectionOnly?: boolean
}

export type ShoeJobsSavedView = {
  jobDirectoryView?: 'active' | 'completed'
  statusFilter?: string
  viewMode?: 'kanban' | 'cards'
  costOutlierOnly?: boolean
  olderThanDays?: number
}
