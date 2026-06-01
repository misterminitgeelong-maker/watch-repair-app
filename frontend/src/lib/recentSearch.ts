const RECENT_KEY = 'ms-recent-search'
const MAX = 8

export type RecentHit = {
  kind: string
  id: string
  title: string
  href: string
}

export function loadRecentHits(): RecentHit[] {
  try {
    const raw = sessionStorage.getItem(RECENT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as RecentHit[]
    return Array.isArray(parsed) ? parsed.slice(0, MAX) : []
  } catch {
    return []
  }
}

export function pushRecentHit(hit: RecentHit) {
  const prev = loadRecentHits().filter(h => !(h.kind === hit.kind && h.id === hit.id))
  sessionStorage.setItem(RECENT_KEY, JSON.stringify([hit, ...prev].slice(0, MAX)))
}
