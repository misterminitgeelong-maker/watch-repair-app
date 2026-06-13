/**
 * Money parsing for forms that charge real customers.
 *
 * The pattern `Math.round(parseFloat(x) * 100)` was reimplemented across the
 * job / quote / invoice / POS forms with inconsistent handling of blanks,
 * garbage, and negatives — some emitted `NaN` (which serialises to `null` and
 * corrupts the charge), some allowed negative cents. This centralises the
 * conversion with one safe, tested definition.
 */

/**
 * Parse a user-entered dollar amount into a finite, non-negative integer of
 * cents. Blank/whitespace/garbage → 0; negatives clamp to 0; rounded to the
 * nearest cent.
 *
 * Note: uses standard IEEE rounding via Math.round, matching the prior inline
 * code — e.g. `1.005` → `100` (not 101) because 1.005*100 is 100.4999…. Callers
 * needing banker's rounding must handle it explicitly; this preserves existing
 * behaviour while removing the NaN/negative hazards.
 */
export function dollarsToCents(value: string | number | null | undefined): number {
  const n = typeof value === 'number' ? value : parseFloat(String(value ?? '').trim())
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.round(n * 100))
}

export interface MoneyLineItem {
  quantity: number
  unit_price_cents: number
}

/**
 * Subtotal (in cents) of quote/invoice line items. Each line is rounded
 * before summing so the total matches the sum of per-line charges the
 * customer sees, and fractional quantities (e.g. 1.5h labour) stay exact.
 */
export function lineItemsSubtotalCents(items: MoneyLineItem[]): number {
  return items.reduce((sum, li) => sum + Math.round(li.quantity * li.unit_price_cents), 0)
}

/** Quote/invoice grand total: subtotal plus a non-negative tax amount. */
export function totalWithTaxCents(subtotalCents: number, taxCents: number): number {
  return subtotalCents + Math.max(0, Math.round(taxCents))
}
