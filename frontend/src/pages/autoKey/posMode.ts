export type PosCheckoutMode = 'quote' | 'sale'

/** Jobs still being priced — POS should save a quote, not take payment. */
export const POS_QUOTE_DEFAULT_STATUSES = [
  'awaiting_quote',
  'quote_sent',
  'awaiting_customer_details',
  'pending_booking',
] as const

/** Jobs that are collecting payment or already sold. */
export const POS_SALE_DEFAULT_STATUSES = [
  'on_site',
  'work_completed',
  'booking_completed',
  'invoice_paid',
] as const

export interface PosModeJobHint {
  status?: string | null
  shop_mobile_booking_request_id?: string | null
}

export function parsePosModeParam(value: string | null | undefined): PosCheckoutMode | null {
  if (value === 'quote' || value === 'sale') return value
  return null
}

/**
 * Quote mode when the operator asked for a quote, or the job is still quoting
 * (awaiting quote / booking request). Sale mode for on-site collect / invoiced
 * jobs, and for a walk-in till with no job.
 */
export function isPosQuoteMode(opts: {
  explicitMode?: PosCheckoutMode | null
  job?: PosModeJobHint | null
}): boolean {
  if (opts.explicitMode === 'quote') return true
  if (opts.explicitMode === 'sale') return false
  const job = opts.job
  if (!job) return false
  const status = job.status ?? ''
  if ((POS_SALE_DEFAULT_STATUSES as readonly string[]).includes(status)) return false
  if ((POS_QUOTE_DEFAULT_STATUSES as readonly string[]).includes(status)) return true
  return Boolean(job.shop_mobile_booking_request_id)
}

export function autoKeyPosHref(jobId: string, mode?: PosCheckoutMode | null): string {
  const params = new URLSearchParams({ view: 'pos', job_id: jobId })
  if (mode) params.set('mode', mode)
  return `/auto-key?${params.toString()}`
}
