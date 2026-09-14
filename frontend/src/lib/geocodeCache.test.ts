import { beforeEach, describe, expect, it } from 'vitest'
import { asyncPool } from './asyncPool'
import {
  GEOCODE_CACHE_KEY,
  GEOCODE_CACHE_MAX_ENTRIES,
  approximateMelbourneCoords,
  cacheGeocode,
  countApproximatedPins,
  loadGeocodeCache,
  pruneGeocodeCache,
  realMapCoords,
  saveGeocodeCache,
  type GeocodeCacheEntry,
} from './geocodeCache'
import { nearestNeighborOrder } from './mobileRouteUtils'

describe('geocodeCache', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('persists to localStorage rather than sessionStorage', () => {
    const map = new Map<string, GeocodeCacheEntry>()
    cacheGeocode(map, '1 collins st', -37.81, 144.96)
    saveGeocodeCache(map)
    expect(localStorage.getItem(GEOCODE_CACHE_KEY)).toBeTruthy()
    expect(sessionStorage.getItem(GEOCODE_CACHE_KEY)).toBeNull()
    const reloaded = loadGeocodeCache()
    expect(reloaded.get('1 collins st')).toMatchObject({ lat: -37.81, lng: 144.96 })
  })

  it('evicts the oldest entries once the size bound is exceeded', () => {
    const map = new Map<string, GeocodeCacheEntry>()
    for (let i = 0; i < GEOCODE_CACHE_MAX_ENTRIES + 3; i += 1) {
      cacheGeocode(map, `addr-${i}`, -37.8, 144.9, i + 1)
    }
    pruneGeocodeCache(map, GEOCODE_CACHE_MAX_ENTRIES + 10)
    expect(map.size).toBe(GEOCODE_CACHE_MAX_ENTRIES)
    expect(map.has('addr-0')).toBe(false)
    expect(map.has('addr-1')).toBe(false)
    expect(map.has('addr-2')).toBe(false)
    expect(map.has(`addr-${GEOCODE_CACHE_MAX_ENTRIES + 2}`)).toBe(true)
  })
})

describe('approximate pins', () => {
  it('are not treated as real coordinates for routing', () => {
    const approx = { ...approximateMelbourneCoords('12 nowhere rd'), approximated: true as const }
    const real = { lat: -37.81, lng: 144.96, approximated: false as const }
    expect(realMapCoords(approx)).toBeNull()
    expect(realMapCoords(real)).toEqual({ lat: -37.81, lng: 144.96 })
    expect(countApproximatedPins([approx, real])).toBe(1)
  })

  it('are excluded from nearest-neighbor order', () => {
    const jobs = [
      { id: 'real-a', c: { lat: -37.8, lng: 144.9, approximated: false } },
      { id: 'fake', c: { lat: -37.81, lng: 144.91, approximated: true } },
      { id: 'real-b', c: { lat: -37.85, lng: 144.95, approximated: false } },
    ]
    const order = nearestNeighborOrder(jobs, (j) => realMapCoords(j.c), 0)
    expect(order[0]).toBe(0)
    expect(order.slice(0, 2).sort()).toEqual([0, 2])
    expect(order[2]).toBe(1)
  })
})

describe('asyncPool', () => {
  it('never runs more than the concurrency limit at once', async () => {
    let inflight = 0
    let peak = 0
    await asyncPool([1, 2, 3, 4, 5, 6], 2, async (n) => {
      inflight += 1
      peak = Math.max(peak, inflight)
      await new Promise((r) => setTimeout(r, 15))
      inflight -= 1
      return n
    })
    expect(peak).toBeLessThanOrEqual(2)
  })
})
