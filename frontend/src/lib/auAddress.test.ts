import { describe, expect, it } from 'vitest'
import {
  normalizeAuStateCode,
  parseAuAddressFromComponents,
  parseAuAddressFromFormatted,
} from './auAddress'

describe('normalizeAuStateCode', () => {
  it('accepts short and long state names', () => {
    expect(normalizeAuStateCode('VIC')).toBe('VIC')
    expect(normalizeAuStateCode('Victoria')).toBe('VIC')
    expect(normalizeAuStateCode('nsw')).toBe('NSW')
  })
})

describe('parseAuAddressFromComponents', () => {
  it('reads suburb and state from Google components', () => {
    const parsed = parseAuAddressFromComponents([
      { long_name: 'Chadstone', short_name: 'Chadstone', types: ['locality', 'political'] },
      { long_name: 'Victoria', short_name: 'VIC', types: ['administrative_area_level_1', 'political'] },
      { long_name: 'Australia', short_name: 'AU', types: ['country', 'political'] },
    ])
    expect(parsed.suburb).toBe('Chadstone')
    expect(parsed.stateCode).toBe('VIC')
  })

  it('falls back to postal_town when locality missing', () => {
    const parsed = parseAuAddressFromComponents([
      { long_name: 'Sydney', short_name: 'Sydney', types: ['postal_town', 'political'] },
      { long_name: 'New South Wales', short_name: 'NSW', types: ['administrative_area_level_1', 'political'] },
    ])
    expect(parsed.suburb).toBe('Sydney')
    expect(parsed.stateCode).toBe('NSW')
  })
})

describe('parseAuAddressFromFormatted', () => {
  it('parses suburb and state before postcode', () => {
    expect(parseAuAddressFromFormatted('10 George St, Sydney NSW 2000, Australia')).toEqual({
      suburb: 'Sydney',
      stateCode: 'NSW',
    })
  })

  it('parses Chadstone-style addresses', () => {
    expect(parseAuAddressFromFormatted('100 Retail Parade, Chadstone VIC 3148')).toEqual({
      suburb: 'Chadstone',
      stateCode: 'VIC',
    })
  })
})
