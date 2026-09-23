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

/** Australian GST rate. Mirrors backend/app/routes/quotes.py GST_RATE. */
export const GST_RATE = 0.10

export interface GstAmounts {
  subtotalCents: number
  taxCents: number
  totalCents: number
}

/**
 * Given the sum of the entered line-item prices, split it into
 * (subtotal, GST, total) for preview purposes. Mirrors the backend's
 * compute_gst_amounts so the modal preview matches what the server returns.
 *
 * subtotalCents is always GST-exclusive and totalCents is always what the
 * customer pays, so totalCents === subtotalCents + taxCents in every case.
 */
/** Integer division rounding half away from zero — mirrors backend `app/gst.py`. */
function divHalfUp(numerator: number, denominator: number): number {
  if (numerator < 0) return -divHalfUp(-numerator, denominator)
  return Math.floor((2 * numerator + denominator) / (2 * denominator))
}

/**
 * Whole-cent GST, half-up (what Xero does). Mirrors backend `compute_gst_amounts`:
 * Australian GST only applies to AUD amounts.
 */
export function computeGstAmounts(
  enteredCents: number,
  gstEnabled: boolean,
  gstInclusive: boolean,
  currency: string = 'AUD',
): GstAmounts {
  const entered = Math.round(enteredCents)
  const isAud = (currency || 'AUD').trim().toUpperCase() === 'AUD'
  if (!gstEnabled || !isAud) return { subtotalCents: entered, taxCents: 0, totalCents: entered }
  if (gstInclusive) {
    const subtotalCents = divHalfUp(entered * 10, 11)
    return { subtotalCents, taxCents: entered - subtotalCents, totalCents: entered }
  }
  const taxCents = divHalfUp(entered, 10)
  return { subtotalCents: entered, taxCents, totalCents: entered + taxCents }
}

/** Display a cent amount as currency. Defaults to AUD / en-AU for this product. */
export function formatMoney(cents: number, currency = 'AUD'): string {
  const code = (currency || 'AUD').toUpperCase().slice(0, 3) || 'AUD'
  try {
    return new Intl.NumberFormat('en-AU', { style: 'currency', currency: code }).format(cents / 100)
  } catch {
    return new Intl.NumberFormat('en-AU', { style: 'currency', currency: 'AUD' }).format(cents / 100)
  }
}

/** Alias used across shop screens; same rendering as formatMoney. */
export function formatCents(cents: number, currency = 'AUD'): string {
  return formatMoney(cents, currency)
}
