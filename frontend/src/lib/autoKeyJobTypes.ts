/** Auto Key / Mobile Services job type options for dropdowns and reports */
export const AUTO_KEY_JOB_TYPES = [
  'Key Cutting (in-store)',
  'Transponder Programming',
  'Lockout – Car',
  'Lockout – Boot/Trunk',
  'Lockout – Roadside',
  'All Keys Lost',
  'Remote / Fob Sync',
  'Ignition Repair',
  'Ignition Replace',
  'Duplicate Key',
  'Broken Key Extraction',
  'Door Lock Change',
  'Diagnostic',
] as const

/** Job types that require a job address (mobile/on-site visits) */
export const MOBILE_JOB_TYPES: ReadonlySet<string> = new Set([
  'Lockout – Car',
  'Lockout – Boot/Trunk',
  'Lockout – Roadside',
  'All Keys Lost',
  'Remote / Fob Sync',
  'Ignition Repair',
  'Ignition Replace',
  'Broken Key Extraction',
  'Door Lock Change',
  'Diagnostic',
])

export type AutoKeyJobType = (typeof AUTO_KEY_JOB_TYPES)[number] | ''

/**
 * One-tap quote preset bundles. Prices (whole AUD dollars) mirror the retail
 * baseline in backend `auto_key_quote_suggestions._JOB_TYPE_DEFAULT_CENTS`,
 * so they stay consistent with server-side quote suggestions.
 */
export const QUOTE_PRESETS: { label: string; description: string; price: number }[] = [
  { label: 'Duplicate Key', description: 'Duplicate key — cut & program', price: 89 },
  { label: 'All Keys Lost', description: 'All keys lost — supply & program', price: 449 },
  { label: 'Transponder Programming', description: 'Transponder programming', price: 120 },
  { label: 'Lockout – Car', description: 'Vehicle lockout service', price: 189 },
  { label: 'Key Cutting', description: 'Key cutting (in-store)', price: 35 },
  { label: 'Lockout – Boot/Trunk', description: 'Boot/trunk lockout', price: 189 },
  { label: 'Lockout – Roadside', description: 'Roadside lockout', price: 220 },
  { label: 'Remote / Fob Sync', description: 'Remote / fob programming', price: 99 },
  { label: 'Ignition Repair', description: 'Ignition repair', price: 159 },
  { label: 'Ignition Replace', description: 'Ignition replacement', price: 349 },
  { label: 'Broken Key Extraction', description: 'Broken key extraction', price: 129 },
  { label: 'Door Lock Change', description: 'Door lock service', price: 199 },
  { label: 'Diagnostic', description: 'Automotive key / immobiliser diagnostic', price: 159 },
]

export interface QuoteBundleItem { description: string; quantity: number; price: number }
export interface QuoteBundle { label: string; note: string; items: QuoteBundleItem[] }

/**
 * Multi-line bundles: one tap drops a full common job (several line items) into
 * the quote. Line descriptions/prices mirror QUOTE_PRESETS so totals stay
 * consistent with single presets and server-side suggestions.
 */
export const QUOTE_BUNDLES: QuoteBundle[] = [
  {
    label: 'All Keys Lost (full)',
    note: 'Supply & program + diagnostic',
    items: [
      { description: 'All keys lost — supply & program', quantity: 1, price: 449 },
      { description: 'Automotive key / immobiliser diagnostic', quantity: 1, price: 159 },
    ],
  },
  {
    label: 'Lockout + new key',
    note: 'Vehicle lockout + duplicate key',
    items: [
      { description: 'Vehicle lockout service', quantity: 1, price: 189 },
      { description: 'Duplicate key — cut & program', quantity: 1, price: 89 },
    ],
  },
  {
    label: 'Ignition replace (full)',
    note: 'Ignition + programming + diagnostic',
    items: [
      { description: 'Ignition replacement', quantity: 1, price: 349 },
      { description: 'Transponder programming', quantity: 1, price: 120 },
      { description: 'Automotive key / immobiliser diagnostic', quantity: 1, price: 159 },
    ],
  },
  {
    label: 'Broken key recovery',
    note: 'Extraction + duplicate key',
    items: [
      { description: 'Broken key extraction', quantity: 1, price: 129 },
      { description: 'Duplicate key — cut & program', quantity: 1, price: 89 },
    ],
  },
]

/** Sum of a bundle's line prices (whole AUD dollars), for button labels. */
export function quoteBundleTotal(bundle: QuoteBundle): number {
  return bundle.items.reduce((sum, it) => sum + it.price * it.quantity, 0)
}

/** Expand a bundle into editable quote line-item drafts (string fields). */
export function bundleToDraftItems(bundle: QuoteBundle): { description: string; quantity: string; unitPrice: string }[] {
  return bundle.items.map(it => ({ description: it.description, quantity: String(it.quantity), unitPrice: String(it.price) }))
}
