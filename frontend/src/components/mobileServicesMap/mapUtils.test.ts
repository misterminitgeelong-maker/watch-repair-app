import { describe, expect, it, beforeEach } from 'vitest'

import {
  approximateMelbourneCoords,
  attachAddress,
  buildGoogleMapsDirUrl,
  customerName,
  isMobileVisitJob,
  isValidPermutation,
  loadGeocodeCache,
  MELBOURNE_CENTRE,
  saveGeocodeCache,
  sortJobsBySchedule,
  vehicleLabel,
  type MapCustomer,
  type MapJob,
} from './mapUtils'

beforeEach(() => {
  try {
    sessionStorage.clear()
  } catch {
    // ignore
  }
})

describe('approximateMelbourneCoords', () => {
  it('returns coords within ~10km of Melbourne centre', () => {
    const r = approximateMelbourneCoords('123 Collins St, Melbourne VIC')
    expect(r.lat).toBeCloseTo(MELBOURNE_CENTRE.lat, 0)
    expect(r.lng).toBeCloseTo(MELBOURNE_CENTRE.lng, 0)
    expect(Math.abs(r.lat - MELBOURNE_CENTRE.lat)).toBeLessThan(0.15)
    expect(Math.abs(r.lng - MELBOURNE_CENTRE.lng)).toBeLessThan(0.2)
  })

  it('is deterministic for the same input', () => {
    const a = approximateMelbourneCoords('45 Flinders St')
    const b = approximateMelbourneCoords('45 Flinders St')
    expect(a).toEqual(b)
  })

  it('differs for different inputs', () => {
    const a = approximateMelbourneCoords('1 Bourke St')
    const b = approximateMelbourneCoords('2 Bourke St')
    expect(a).not.toEqual(b)
  })
})

describe('geocode cache', () => {
  it('round-trips through sessionStorage', () => {
    const m = new Map<string, { lat: number; lng: number }>()
    m.set('10 Lonsdale St', { lat: -37.81, lng: 144.96 })
    saveGeocodeCache(m)
    const loaded = loadGeocodeCache()
    expect(loaded.get('10 Lonsdale St')).toEqual({ lat: -37.81, lng: 144.96 })
  })

  it('returns an empty map when storage is empty', () => {
    const loaded = loadGeocodeCache()
    expect(loaded.size).toBe(0)
  })
})

describe('customerName', () => {
  const customers: MapCustomer[] = [
    { id: 'c1', full_name: 'Pat Smith' },
    { id: 'c2', full_name: 'Jo Brown' },
  ]

  it('returns the matching name', () => {
    expect(customerName(customers, 'c2')).toBe('Jo Brown')
  })

  it('falls back to em-dash when unknown', () => {
    expect(customerName(customers, 'missing')).toBe('—')
  })
})

describe('vehicleLabel', () => {
  const baseJob: MapJob = {
    id: 'j1',
    job_number: 'AK-001',
    title: 'Lockout',
    status: 'booked',
    customer_id: 'c1',
  }

  it('joins populated fields with middots', () => {
    const j = { ...baseJob, vehicle_make: 'Toyota', vehicle_model: 'Camry', vehicle_year: 2020, registration_plate: 'ABC123' }
    expect(vehicleLabel(j)).toBe('Toyota · Camry · 2020 · ABC123')
  })

  it('defaults make to "Vehicle" when missing', () => {
    expect(vehicleLabel(baseJob)).toBe('Vehicle')
  })
})

describe('isMobileVisitJob', () => {
  const mobileTypes = new Set(['Lockout – Car', 'All Keys Lost'])

  it('true when job_type is in the set', () => {
    expect(isMobileVisitJob({ id: 'j', job_number: '', title: '', status: '', customer_id: '', job_type: 'Lockout – Car' }, mobileTypes)).toBe(true)
  })

  it('false when job_type is out of the set', () => {
    expect(isMobileVisitJob({ id: 'j', job_number: '', title: '', status: '', customer_id: '', job_type: 'Watch Service' }, mobileTypes)).toBe(false)
  })

  it('falls back to job_address when job_type is missing', () => {
    expect(isMobileVisitJob({ id: 'j', job_number: '', title: '', status: '', customer_id: '', job_address: '1 Lygon St' }, mobileTypes)).toBe(true)
    expect(isMobileVisitJob({ id: 'j', job_number: '', title: '', status: '', customer_id: '' }, mobileTypes)).toBe(false)
  })
})

describe('attachAddress', () => {
  const customers: MapCustomer[] = [{ id: 'c1', full_name: 'Pat', address: '1 Swanston St' }]

  it('uses job_address when present', () => {
    const r = attachAddress({ id: 'j', job_number: '', title: '', status: '', customer_id: 'c1', job_address: '2 Collins St' }, customers)
    expect(r?._addressForMap).toBe('2 Collins St')
  })

  it('falls back to customer address', () => {
    const r = attachAddress({ id: 'j', job_number: '', title: '', status: '', customer_id: 'c1' }, customers)
    expect(r?._addressForMap).toBe('1 Swanston St')
  })

  it('returns null when no address anywhere', () => {
    const r = attachAddress({ id: 'j', job_number: '', title: '', status: '', customer_id: 'missing' }, customers)
    expect(r).toBeNull()
  })
})

describe('sortJobsBySchedule', () => {
  it('sorts by scheduled_at, then job_number numerically', () => {
    const rows = [
      { scheduled_at: '2026-04-21T10:00:00Z', job_number: 'AK-3' },
      { scheduled_at: '2026-04-21T09:00:00Z', job_number: 'AK-10' },
      { scheduled_at: '2026-04-21T09:00:00Z', job_number: 'AK-2' },
    ]
    const sorted = sortJobsBySchedule(rows)
    expect(sorted.map((r) => r.job_number)).toEqual(['AK-2', 'AK-10', 'AK-3'])
  })

  it('treats missing scheduled_at as 0 (sorts first)', () => {
    const rows = [
      { scheduled_at: '2026-04-21T09:00:00Z', job_number: 'AK-2' },
      { job_number: 'AK-1' },
    ]
    expect(sortJobsBySchedule(rows).map((r) => r.job_number)).toEqual(['AK-1', 'AK-2'])
  })
})

describe('buildGoogleMapsDirUrl', () => {
  it('produces a slash-separated path for multi-stop routes', () => {
    const url = buildGoogleMapsDirUrl(['1 Collins St', '2 Bourke St'])
    expect(url).toBe('https://www.google.com/maps/dir/1%20Collins%20St/2%20Bourke%20St')
  })

  it('returns the Google Maps home for empty input', () => {
    expect(buildGoogleMapsDirUrl([])).toBe('https://www.google.com/maps')
  })
})

describe('isValidPermutation', () => {
  it('true for a valid 0..n-1 permutation', () => {
    expect(isValidPermutation([2, 0, 1], 3)).toBe(true)
  })

  it('false when length differs', () => {
    expect(isValidPermutation([0, 1], 3)).toBe(false)
  })

  it('false when duplicates exist', () => {
    expect(isValidPermutation([0, 0, 1], 3)).toBe(false)
  })

  it('false when an index is out of range', () => {
    expect(isValidPermutation([0, 1, 3], 3)).toBe(false)
    expect(isValidPermutation([-1, 0, 1], 3)).toBe(false)
  })
})
