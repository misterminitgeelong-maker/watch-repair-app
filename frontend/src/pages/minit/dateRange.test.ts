import { describe, expect, it } from 'vitest'
import { toIsoEnd, toIsoStart } from './dateRange'

describe('Minit report date range (Melbourne time)', () => {
  it('starts the day at Melbourne midnight (AEDT, UTC+11)', () => {
    expect(toIsoStart('2026-10-28')).toBe('2026-10-27T13:00:00.000Z')
    expect(toIsoEnd('2026-10-28')).toBe('2026-10-28T12:59:59.999Z')
  })

  it('uses AEST (UTC+10) outside daylight saving', () => {
    expect(toIsoStart('2026-07-01')).toBe('2026-06-30T14:00:00.000Z')
  })
})
