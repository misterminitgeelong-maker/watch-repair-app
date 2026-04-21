/**
 * Pure helpers extracted from MobileServicesMap.tsx.
 *
 * The map component used to inline ~100 lines of geocode-cache + job-shape
 * logic plus several small utility functions. Moving them to a sibling
 * module means:
 *   - The helpers are unit-testable without spinning up a Google Maps stub.
 *   - Future splits (GoogleMapView / LeafletMapView) share them.
 *
 * If you change a helper here, run the existing map-oriented tests
 * (mobileRouteUtils.test.ts) and check-in a new case if behaviour
 * changed.
 */

export const MELBOURNE_CENTRE = { lat: -37.8136, lng: 144.9631 }
export const GEOCODE_CACHE_KEY = 'geocode_cache'

export interface MapCustomer {
  id: string
  full_name: string
  address?: string
}

export interface MapJob {
  id: string
  job_number: string
  title: string
  job_address?: string
  job_type?: string
  scheduled_at?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  status: string
  customer_id: string
}

export type MapJobWithAddr = MapJob & { _addressForMap: string }

/** Deterministic spread around Melbourne when real geocoding is unavailable. */
export function approximateMelbourneCoords(address: string): { lat: number; lng: number } {
  let h = 2166136261
  for (let i = 0; i < address.length; i++) h = Math.imul(h ^ address.charCodeAt(i), 16777619)
  const u = (h >>> 0) / 0xffffffff
  const v = ((h >>> 16) >>> 0) / 0xffff
  return {
    lat: MELBOURNE_CENTRE.lat + (u - 0.5) * 0.14,
    lng: MELBOURNE_CENTRE.lng + (v - 0.5) * 0.2,
  }
}

export function loadGeocodeCache(): Map<string, { lat: number; lng: number }> {
  try {
    const raw = sessionStorage.getItem(GEOCODE_CACHE_KEY)
    if (!raw) return new Map()
    const parsed = JSON.parse(raw) as { key: string; lat: number; lng: number }[]
    if (!Array.isArray(parsed)) return new Map()
    const map = new Map<string, { lat: number; lng: number }>()
    for (const { key, lat, lng } of parsed) {
      if (typeof key === 'string' && typeof lat === 'number' && typeof lng === 'number') {
        map.set(key, { lat, lng })
      }
    }
    return map
  } catch {
    return new Map()
  }
}

export function saveGeocodeCache(map: Map<string, { lat: number; lng: number }>): void {
  try {
    const entries = Array.from(map.entries(), ([key, coords]) => ({ key, ...coords }))
    sessionStorage.setItem(GEOCODE_CACHE_KEY, JSON.stringify(entries))
  } catch {
    // best-effort; session storage may be blocked in private browsing
  }
}

export function customerName(customers: MapCustomer[], customerId: string): string {
  const c = customers.find((x) => x.id === customerId)
  return c?.full_name ?? '—'
}

export function vehicleLabel(job: MapJob): string {
  const parts = [
    job.vehicle_make || 'Vehicle',
    job.vehicle_model,
    job.vehicle_year?.toString(),
    job.registration_plate,
  ].filter(Boolean)
  return parts.join(' · ') || '—'
}

export function isMobileVisitJob(j: MapJob, mobileJobTypes: ReadonlySet<string>): boolean {
  const t = j.job_type?.trim()
  if (!t) return !!j.job_address?.trim()
  return mobileJobTypes.has(t)
}

export function attachAddress(j: MapJob, customers: MapCustomer[]): MapJobWithAddr | null {
  const address =
    j.job_address?.trim() ||
    customers.find((c) => c.id === j.customer_id)?.address?.trim()
  if (!address) return null
  return { ...j, _addressForMap: address }
}

export function sortJobsBySchedule<T extends { scheduled_at?: string; job_number: string }>(jobs: T[]): T[] {
  return [...jobs].sort((a, b) => {
    const ta = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0
    const tb = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0
    if (ta !== tb) return ta - tb
    return a.job_number.localeCompare(b.job_number, undefined, { numeric: true })
  })
}

export function buildGoogleMapsDirUrl(addresses: string[]): string {
  if (addresses.length === 0) return 'https://www.google.com/maps'
  const path = addresses.map((a) => encodeURIComponent(a)).join('/')
  return `https://www.google.com/maps/dir/${path}`
}

export function isValidPermutation(order: number[], n: number): boolean {
  if (order.length !== n) return false
  if (new Set(order).size !== n) return false
  return order.every((i) => i >= 0 && i < n)
}
