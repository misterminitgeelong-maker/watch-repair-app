import { describe, it, expect } from 'vitest'
import { dollarsToCents, lineItemsSubtotalCents, totalWithTaxCents } from './money'

describe('dollarsToCents', () => {
  it('converts whole and decimal dollars to cents', () => {
    expect(dollarsToCents('5')).toBe(500)
    expect(dollarsToCents('5.00')).toBe(500)
    expect(dollarsToCents('12.34')).toBe(1234)
    expect(dollarsToCents(19.99)).toBe(1999)
    expect(dollarsToCents('0')).toBe(0)
  })

  it('rounds floating-point representation cleanly (no off-by-one)', () => {
    // 0.29 * 100 === 28.999999999999996 in IEEE float
    expect(dollarsToCents('0.29')).toBe(29)
    expect(dollarsToCents('19.99')).toBe(1999)
    expect(dollarsToCents('1.1')).toBe(110)
    expect(dollarsToCents(0.1 + 0.2)).toBe(30)
  })

  it('returns 0 for blank, whitespace, or garbage instead of NaN', () => {
    // The bug this guards: NaN -> JSON null -> corrupted charge.
    expect(dollarsToCents('')).toBe(0)
    expect(dollarsToCents('   ')).toBe(0)
    expect(dollarsToCents('abc')).toBe(0)
    expect(dollarsToCents(null)).toBe(0)
    expect(dollarsToCents(undefined)).toBe(0)
    expect(dollarsToCents(NaN)).toBe(0)
    expect(dollarsToCents(Infinity)).toBe(0)
    expect(Number.isNaN(dollarsToCents('not a number'))).toBe(false)
  })

  it('clamps negative amounts to 0 (money inputs are never negative)', () => {
    expect(dollarsToCents('-5')).toBe(0)
    expect(dollarsToCents(-0.01)).toBe(0)
  })

  it('tolerates leading/trailing whitespace', () => {
    expect(dollarsToCents('  12.50  ')).toBe(1250)
  })
})

describe('lineItemsSubtotalCents', () => {
  it('sums quantity × unit price across lines', () => {
    expect(
      lineItemsSubtotalCents([
        { quantity: 1, unit_price_cents: 5000 },
        { quantity: 2, unit_price_cents: 2500 },
      ]),
    ).toBe(10000)
  })

  it('handles fractional quantities by rounding each line', () => {
    // 1.5h × $40.00/h = $60.00
    expect(lineItemsSubtotalCents([{ quantity: 1.5, unit_price_cents: 4000 }])).toBe(6000)
    // 0.333 × 999c = 332.667 -> 333 per line
    expect(lineItemsSubtotalCents([{ quantity: 0.333, unit_price_cents: 999 }])).toBe(333)
  })

  it('is 0 for an empty list', () => {
    expect(lineItemsSubtotalCents([])).toBe(0)
  })
})

describe('totalWithTaxCents', () => {
  it('adds a non-negative tax to the subtotal', () => {
    expect(totalWithTaxCents(10000, 1000)).toBe(11000)
    expect(totalWithTaxCents(10000, 0)).toBe(10000)
  })

  it('treats negative tax as 0', () => {
    expect(totalWithTaxCents(10000, -500)).toBe(10000)
  })
})
