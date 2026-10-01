export type PosDiscountType = 'none' | 'percent' | 'amount'
export interface PosDiscount { type: PosDiscountType; value: string }
export const NO_POS_DISCOUNT: PosDiscount = { type: 'none', value: '' }

/** Discounts apply to each unit before the existing GST calculation. */
export function priceWithDiscount(unitPriceCents: number, discount: PosDiscount) {
  const raw = discount.value.trim()
  const invalid = (error: string) => ({ unitPriceCents, discountCents: 0, label: '', error })
  if (discount.type === 'none' || raw === '') return { unitPriceCents, discountCents: 0, label: '', error: '' }
  if (!/^(?:\d+(?:\.\d{0,2})?|\.\d{1,2})$/.test(raw)) return invalid('Enter a non-negative discount with up to two decimal places.')
  const value = Number(raw)
  if (!Number.isFinite(value)) return invalid('Enter a valid discount.')
  if (discount.type === 'percent' && value > 100) return invalid('Percentage discount cannot exceed 100%.')
  const [whole, fraction = ''] = raw.split('.')
  const hundredths = Number(whole || '0') * 100 + Number(fraction.padEnd(2, '0'))
  const discountCents = discount.type === 'amount' ? hundredths : Math.round(unitPriceCents * hundredths / 10_000)
  if (discountCents > unitPriceCents) return invalid('Dollar discount cannot exceed the item price.')
  return { unitPriceCents: unitPriceCents - discountCents, discountCents,
    label: discountCents > 0 ? (discount.type === 'percent' ? `${value}% discount` : `$${(discountCents / 100).toFixed(2)} discount per item`) : '', error: '' }
}

export function discountedQuoteLine(line: { description: string; quantity: number; unit_price_cents: number; discount: PosDiscount }) {
  const price = priceWithDiscount(line.unit_price_cents, line.discount)
  if (price.error) throw new Error(price.error)
  return { description: price.label ? `${line.description} (${price.label}; was $${(line.unit_price_cents / 100).toFixed(2)} each)` : line.description,
    quantity: line.quantity, unit_price_cents: price.unitPriceCents }
}
