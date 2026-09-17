import type { JobStatus } from '@/lib/api'

/**
 * Mobile Services status vocabulary — the presentation mirror of
 * `backend/app/auto_key_status.py`. One canonical stage per stored value, one
 * label, one reporting category. Every Mobile Services surface (Today, List,
 * Kanban, job detail, filters, reports, imports) reads from here so a job is
 * called the same thing everywhere.
 *
 * `mobileStatus.test.ts` pins this table to the backend contract; change both
 * sides together.
 */

export type MobileStatusCategory = 'pipeline' | 'booking' | 'field' | 'completed' | 'paid' | 'lost'

export interface MobileStatusDefinition {
  key: JobStatus
  label: string
  category: MobileStatusCategory
  /** Older stored values that present as this stage (never written by new code). */
  aliases: readonly JobStatus[]
}

const CLOSED_CATEGORIES: ReadonlySet<MobileStatusCategory> = new Set(['completed', 'paid', 'lost'])

// Lifecycle order. Each stored status appears exactly once, as a key or an alias.
export const MOBILE_STATUS_DEFINITIONS: readonly MobileStatusDefinition[] = [
  { key: 'awaiting_quote', label: 'Awaiting Quote', category: 'pipeline', aliases: [] },
  { key: 'awaiting_customer_details', label: 'Awaiting Customer Details', category: 'pipeline', aliases: [] },
  { key: 'quote_sent', label: 'Quote Sent', category: 'pipeline', aliases: ['awaiting_go_ahead'] },
  { key: 'awaiting_booking_confirmation', label: 'Awaiting Booking Confirmation', category: 'booking', aliases: ['pending_booking', 'go_ahead'] },
  { key: 'booking_confirmed', label: 'Booking Confirmed', category: 'booking', aliases: ['booked'] },
  {
    key: 'booking_on_hold',
    label: 'Booking on Hold',
    category: 'booking',
    aliases: [
      'job_delayed',
      'awaiting_parts',
      'parts_to_order',
      'sent_to_labanda',
      'quoted_by_labanda',
      'at_third_party_for_quoting',
      'third_party_quote_approved',
      'at_third_party_repairer',
    ],
  },
  { key: 'en_route', label: 'En Route', category: 'field', aliases: [] },
  { key: 'on_site', label: 'On Site', category: 'field', aliases: ['working_on', 'service'] },
  { key: 'work_completed', label: 'Work Completed', category: 'completed', aliases: ['booking_completed', 'completed', 'awaiting_collection'] },
  { key: 'invoice_paid', label: 'Invoice Paid', category: 'paid', aliases: ['collected'] },
  { key: 'failed_job', label: 'Failed Job', category: 'lost', aliases: [] },
  { key: 'no_go', label: 'No Go', category: 'lost', aliases: [] },
]

export const MOBILE_STATUS_CATEGORY_LABELS: Record<MobileStatusCategory, string> = {
  pipeline: 'Quoting',
  booking: 'Booking',
  field: 'In the field',
  completed: 'Work completed',
  paid: 'Paid',
  lost: 'Lost',
}

const DEFINITION_BY_KEY = new Map<string, MobileStatusDefinition>(MOBILE_STATUS_DEFINITIONS.map(d => [d.key, d]))

/** Stored alias → canonical key. */
export const MOBILE_STATUS_ALIASES: Readonly<Record<string, JobStatus>> = Object.fromEntries(
  MOBILE_STATUS_DEFINITIONS.flatMap(d => d.aliases.map(alias => [alias, d.key])),
)

/** Canonical keys in lifecycle order — the option list for every status picker. */
export const MOBILE_STATUS_OPTIONS: readonly JobStatus[] = MOBILE_STATUS_DEFINITIONS.map(d => d.key)

/** Any stored value (canonical or alias) → label. */
export const MOBILE_STATUS_LABELS: Readonly<Record<string, string>> = Object.fromEntries(
  MOBILE_STATUS_DEFINITIONS.flatMap(d => [[d.key, d.label], ...d.aliases.map(alias => [alias, d.label])]),
)

export const MOBILE_CLOSED_STATUSES: readonly string[] = MOBILE_STATUS_DEFINITIONS
  .filter(d => CLOSED_CATEGORIES.has(d.category))
  .flatMap(d => [d.key, ...d.aliases])
export const MOBILE_ACTIVE_STATUSES: readonly string[] = MOBILE_STATUS_DEFINITIONS
  .filter(d => !CLOSED_CATEGORIES.has(d.category))
  .flatMap(d => [d.key, ...d.aliases])

export function canonicalMobileStatus(status: string): string {
  return MOBILE_STATUS_ALIASES[status] ?? status
}

export function mobileStatusDefinition(status: string): MobileStatusDefinition | undefined {
  return DEFINITION_BY_KEY.get(canonicalMobileStatus(status))
}

export function mobileStatusLabel(status: string): string {
  return MOBILE_STATUS_LABELS[status] ?? status.replace(/_/g, ' ')
}

export function mobileStatusCategory(status: string): MobileStatusCategory | null {
  return mobileStatusDefinition(status)?.category ?? null
}

export function isMobileStatusClosed(status: string): boolean {
  const category = mobileStatusCategory(status)
  return category != null && CLOSED_CATEGORIES.has(category)
}

/** Every stored value that reports under `category`. */
export function mobileStatusesInCategory(category: MobileStatusCategory): readonly string[] {
  return MOBILE_STATUS_DEFINITIONS.filter(d => d.category === category).flatMap(d => [d.key, ...d.aliases])
}
