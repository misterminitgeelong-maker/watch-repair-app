/** Bound, durable cache of successful geocodes (never stores hashed fallbacks). */

export const GEOCODE_CACHE_KEY = 'geocode_cache'
export const GEOCODE_CACHE_MAX_ENTRIES = 500
export const GEOCODE_CACHE_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000

export type GeocodeCacheEntry = { lat: number; lng: number; cachedAt: number }

function storageGet(): string | null {
  try {
    return localStorage.getItem(GEOCODE_CACHE_KEY) ?? sessionStorage.getItem(GEOCODE_CACHE_KEY)
  } catch {
    return null
  }
}

function storageSet(raw: string): void {
  try {
    localStorage.setItem(GEOCODE_CACHE_KEY, raw)
    sessionStorage.removeItem(GEOCODE_CACHE_KEY)
  } catch {
    try {
      sessionStorage.setItem(GEOCODE_CACHE_KEY, raw)
    } catch {
      // ignore quota / private-mode failures
    }
  }
}

export function pruneGeocodeCache(map: Map<string, GeocodeCacheEntry>, now = Date.now()): Map<string, GeocodeCacheEntry> {
  const cutoff = now - GEOCODE_CACHE_MAX_AGE_MS
  for (const [key, entry] of map) {
    if (!entry || typeof entry.lat !== 'number' || typeof entry.lng !== 'number') {
      map.delete(key)
      continue
    }
    if ((entry.cachedAt ?? 0) < cutoff) map.delete(key)
  }
  if (map.size <= GEOCODE_CACHE_MAX_ENTRIES) return map
  const ranked = [...map.entries()].sort((a, b) => (a[1].cachedAt ?? 0) - (b[1].cachedAt ?? 0))
  const drop = ranked.length - GEOCODE_CACHE_MAX_ENTRIES
  for (let i = 0; i < drop; i += 1) {
    map.delete(ranked[i][0])
  }
  return map
}

export function loadGeocodeCache(): Map<string, GeocodeCacheEntry> {
  const map = new Map<string, GeocodeCacheEntry>()
  try {
    const raw = storageGet()
    if (!raw) return map
    const parsed = JSON.parse(raw) as { key: string; lat: number; lng: number; cachedAt?: number }[]
    if (!Array.isArray(parsed)) return map
    const now = Date.now()
    for (const row of parsed) {
      if (typeof row?.key !== 'string' || typeof row.lat !== 'number' || typeof row.lng !== 'number') continue
      map.set(row.key, { lat: row.lat, lng: row.lng, cachedAt: typeof row.cachedAt === 'number' ? row.cachedAt : now })
    }
  } catch {
    return new Map()
  }
  return pruneGeocodeCache(map)
}

export function saveGeocodeCache(map: Map<string, GeocodeCacheEntry>): void {
  pruneGeocodeCache(map)
  const entries = Array.from(map.entries(), ([key, coords]) => ({
    key,
    lat: coords.lat,
    lng: coords.lng,
    cachedAt: coords.cachedAt,
  }))
  try {
    storageSet(JSON.stringify(entries))
  } catch {
    // ignore
  }
}

export function cacheGeocode(map: Map<string, GeocodeCacheEntry>, key: string, lat: number, lng: number, now = Date.now()): void {
  map.set(key, { lat, lng, cachedAt: now })
  pruneGeocodeCache(map, now)
}

/** Deterministic scatter around Melbourne CBD — never treat as a real geocode. */
export function approximateMelbourneCoords(address: string): { lat: number; lng: number } {
  let h = 2166136261
  for (let i = 0; i < address.length; i++) h = Math.imul(h ^ address.charCodeAt(i), 16777619)
  const u = (h >>> 0) / 0xffffffff
  const v = ((h >>> 16) >>> 0) / 0xffff
  return { lat: -37.8136 + (u - 0.5) * 0.14, lng: 144.9631 + (v - 0.5) * 0.2 }
}

export type MapPinCoords = { lat: number; lng: number; approximated: boolean }

export function realMapCoords(pin: MapPinCoords | undefined | null): { lat: number; lng: number } | null {
  if (!pin || pin.approximated) return null
  return { lat: pin.lat, lng: pin.lng }
}

export function countApproximatedPins(pins: Iterable<MapPinCoords>): number {
  let n = 0
  for (const pin of pins) {
    if (pin.approximated) n += 1
  }
  return n
}
