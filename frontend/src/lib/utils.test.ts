import { describe, expect, it } from 'vitest'
import { formatDate } from './utils'

describe('Australian date display', () => {
  it('uses zero-padded day/month/year for calendar dates', () => {
    expect(formatDate('2026-10-01')).toBe('01/10/2026')
    expect(formatDate('2026-01-12')).toBe('12/01/2026')
  })

  it('formats timestamps with the Australian locale', () => {
    expect(formatDate('2026-10-01T12:00:00')).toBe('01/10/2026')
  })

  it('handles missing and invalid dates', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate(undefined)).toBe('—')
    expect(formatDate('')).toBe('—')
    expect(formatDate('invalid')).toBe('—')
  })
})
