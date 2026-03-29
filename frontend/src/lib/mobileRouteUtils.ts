/** Haversine distance in km (great-circle), sufficient for stop-order heuristics */

export function haversineKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const s1 = Math.sin(dLat / 2)
  const s2 = Math.sin(dLng / 2)
  const h = s1 * s1 + Math.cos(lat1) * Math.cos(lat2) * s2 * s2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)))
}

/**
 * Nearest-neighbor ordering: start at `startIndex`, then repeatedly visit the closest unvisited stop.
 * Returns indices into the input array (permutation).
 */
export function nearestNeighborOrder<T>(
  items: T[],
  coords: (item: T) => { lat: number; lng: number } | null | undefined,
  startIndex: number,
): number[] {
  const n = items.length
  if (n === 0) return []
  const si = Math.max(0, Math.min(n - 1, Math.floor(startIndex)))
  const order: number[] = []
  const used = new Set<number>()
  let current = si
  const firstCoord = coords(items[current])
  if (!firstCoord) {
    return items.map((_, i) => i)
  }
  order.push(current)
  used.add(current)
  while (order.length < n) {
    let bestJ = -1
    let bestD = Infinity
    const curPt = coords(items[current]) ?? firstCoord
    for (let j = 0; j < n; j++) {
      if (used.has(j)) continue
      const c = coords(items[j])
      if (!c) continue
      const d = haversineKm(curPt, c)
      if (d < bestD) {
        bestD = d
        bestJ = j
      }
    }
    if (bestJ < 0) break
    order.push(bestJ)
    used.add(bestJ)
    current = bestJ
  }
  for (let j = 0; j < n; j++) {
    if (!used.has(j)) order.push(j)
  }
  return order
}
