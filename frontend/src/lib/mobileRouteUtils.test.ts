import { describe, expect, it } from 'vitest'
import { haversineKm, nearestNeighborOrder } from './mobileRouteUtils'

describe('haversineKm', () => {
  it('is ~0 for identical points', () => {
    const p = { lat: -37.8, lng: 144.9 }
    expect(haversineKm(p, p)).toBe(0)
  })

  it('Melbourne to Sydney is hundreds of km', () => {
    const mel = { lat: -37.8136, lng: 144.9631 }
    const syd = { lat: -33.8688, lng: 151.2093 }
    const d = haversineKm(mel, syd)
    expect(d).toBeGreaterThan(650)
    expect(d).toBeLessThan(750)
  })
})

describe('nearestNeighborOrder', () => {
  const pts = [
    { id: 'a', c: { lat: -37.8, lng: 144.9 } },
    { id: 'b', c: { lat: -37.81, lng: 144.91 } },
    { id: 'c', c: { lat: -37.85, lng: 144.95 } },
  ]

  it('starts at startIndex and visits all with coords', () => {
    const order = nearestNeighborOrder(pts, (p) => p.c, 0)
    expect(order).toHaveLength(3)
    expect(new Set(order)).toEqual(new Set([0, 1, 2]))
    expect(order[0]).toBe(0)
  })
})
