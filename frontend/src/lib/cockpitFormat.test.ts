import { describe, expect, it } from 'vitest'
import { ageDays, comparisonLabel, formatDelta, formatMetricValue, formatMinutes, formatShopDay, formatShopTime } from './cockpitFormat'

describe('cockpit formatting', () => {
  it('formats money and counts', () => {
    expect(formatMetricValue(123456, 'cents')).toBe('$1,234.56')
    expect(formatMetricValue(4, 'count')).toBe('4')
    expect(formatMetricValue(2.5, 'count')).toBe('2.5')
  })

  it('formats deltas with sign, and never invents a percentage for a zero baseline', () => {
    expect(formatDelta({ abs: 120000, pct: 20 }, 'cents')).toBe('+$1,200.00 (+20%)')
    expect(formatDelta({ abs: -3, pct: -50 }, 'count')).toBe('−3 (−50%)')
    expect(formatDelta({ abs: 2, pct: null }, 'count')).toBe('+2 (no prior)')
    expect(formatDelta({ abs: 0, pct: null }, 'count')).toBe('no change')
    expect(formatDelta({ abs: 0, pct: 0 }, 'cents')).toBe('$0.00 (0%)')
    expect(formatDelta(null, 'cents')).toBe('—')
  })

  it('explains partial-week comparisons', () => {
    expect(comparisonLabel({ partial: false, days_elapsed: 7 }, 'previous')).toBe('vs last wk')
    expect(comparisonLabel({ partial: true, days_elapsed: 3 }, 'previous')).toBe('vs last wk (3d)')
    expect(comparisonLabel({ partial: true, days_elapsed: 1 }, 'four_week')).toBe('vs 4-wk avg (1d)')
    expect(comparisonLabel({ partial: true, days_elapsed: 5 }, 'target')).toBe('vs target (5d)')
  })

  it('formats minutes as hours', () => {
    expect(formatMinutes(0)).toBe('0h')
    expect(formatMinutes(45)).toBe('45m')
    expect(formatMinutes(120)).toBe('2h')
    expect(formatMinutes(150)).toBe('2h 30m')
    expect(formatMinutes(-10)).toBe('0h')
  })

  it('renders times in the shop timezone, not the browser zone', () => {
    // 23:30 UTC on the 17th is 09:30 on the 18th in Melbourne (AEST, +10).
    expect(formatShopTime('2026-09-17T23:30:00Z', 'Australia/Melbourne')).toBe('09:30 am')
    expect(formatShopDay('2026-09-17T23:30:00Z', 'Australia/Melbourne', '2026-09-18')).toBe('Today 09:30 am')
    expect(formatShopDay('2026-09-17T23:30:00Z', 'Australia/Melbourne', '2026-09-17')).toBe('Fri, 18 Sept 09:30 am')
    expect(formatShopDay(null, 'Australia/Melbourne', '2026-09-18')).toBe('Unscheduled')
    expect(formatShopTime('garbage', 'Australia/Melbourne')).toBe('—')
  })

  it('ages timestamps in whole days', () => {
    const now = Date.parse('2026-09-18T00:00:00Z')
    expect(ageDays('2026-09-08T00:00:00Z', now)).toBe(10)
    expect(ageDays('2026-09-17T12:00:00Z', now)).toBe(0)
    expect(ageDays(null, now)).toBe(0)
    expect(ageDays('2099-01-01T00:00:00Z', now)).toBe(0)
  })
})
