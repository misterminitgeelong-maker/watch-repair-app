import { describe, expect, it } from 'vitest'
import { computeGstAmounts } from '@/lib/money'
import { discountedQuoteLine, priceWithDiscount } from './posDiscount'

describe('POS item discounts', () => {
  it('applies percentage and dollar discounts in cents before GST', () => {
    const percentage = priceWithDiscount(10_000, { type: 'percent', value: '10' })
    expect(percentage.unitPriceCents).toBe(9000)
    expect(computeGstAmounts(percentage.unitPriceCents * 2, true, true)).toEqual({ subtotalCents: 16364, taxCents: 1636, totalCents: 18000 })
    expect(computeGstAmounts(percentage.unitPriceCents * 2, true, false)).toEqual({ subtotalCents: 18000, taxCents: 1800, totalCents: 19800 })
    expect(priceWithDiscount(10_000, { type: 'amount', value: '12.34' }).unitPriceCents).toBe(8766)
    expect(priceWithDiscount(999, { type: 'percent', value: '12.5' }).unitPriceCents).toBe(874)
  })
  it.each(['-1', 'abc', 'NaN', 'Infinity', '10.001', '1e2'])('rejects invalid discount %s', value => {
    expect(priceWithDiscount(10_000, { type: 'amount', value }).error).toBeTruthy()
  })
  it('prevents discounts above the price and permits free items', () => {
    expect(priceWithDiscount(10_000, { type: 'percent', value: '100.01' }).error).toBeTruthy()
    expect(priceWithDiscount(10_000, { type: 'amount', value: '100.01' }).error).toBeTruthy()
    expect(priceWithDiscount(10_000, { type: 'percent', value: '100' }).unitPriceCents).toBe(0)
    expect(priceWithDiscount(10_000, { type: 'amount', value: '100' }).unitPriceCents).toBe(0)
    expect(priceWithDiscount(10_000, { type: 'none', value: '100' }).unitPriceCents).toBe(10_000)
  })
  it('preserves the original price and discount in the persisted quote description', () => {
    expect(discountedQuoteLine({ description: 'Gain entry', quantity: 2, unit_price_cents: 10_000, discount: { type: 'amount', value: '10' } })).toEqual({ description: 'Gain entry ($10.00 discount per item; was $100.00 each)', quantity: 2, unit_price_cents: 9000 })
  })
})
