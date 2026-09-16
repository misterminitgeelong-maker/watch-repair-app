import { describe, expect, it } from 'vitest'

import { fmtVswtDelta } from './format'

describe('fmtVswtDelta', () => {
  it('shows rate movements as percentage points', () => {
    expect(fmtVswtDelta(0.151, 0.735, 'percent')).toBe('+15.1 pp')
    expect(fmtVswtDelta(-0.025, -0.2, 'percent')).toBe('-2.5 pp')
  })

  it('shows absolute and relative movement for financial values', () => {
    expect(fmtVswtDelta(1947, 0.141, 'currency')).toBe('+$1,947 (+14.1%)')
    expect(fmtVswtDelta(-4069, -0.127, 'currency')).toBe('-$4,069 (-12.7%)')
  })
})
