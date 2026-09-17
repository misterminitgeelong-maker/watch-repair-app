import type { MobileCockpitFocusKey, MobileStatusCategoryKey } from '@/lib/api'

/**
 * Cockpit focus keys the list view accepts from the URL. The filter itself is
 * applied server-side (see backend `mobile_cockpit.FOCUS_DEFINITIONS`); the
 * labels here only name the drill-down banner.
 */
export const COCKPIT_FOCUS_LABELS: Record<MobileCockpitFocusKey, string> = {
  late: 'Late — booked time passed, not en route',
  today: 'Booked today',
  in_field: 'In the field now',
  unscheduled: 'Unscheduled active jobs',
  unassigned: 'Unassigned active jobs',
  on_hold: 'Bookings on hold',
  needs_quote: 'Needs a quote',
  quote_follow_up: 'Quote sent, no answer — follow up',
  confirmation_follow_up: 'Booking unconfirmed — follow up',
  completed_unpaid: 'Completed, not paid',
  overdue_invoices: 'Overdue invoices',
  unpaid_invoices: 'Unpaid invoices',
  this_week: 'Booked this week',
  completed_this_week: 'Completed this week',
  invoiced_this_week: 'Invoiced this week',
  collected_this_week: 'Paid this week',
}

export const COCKPIT_FOCUS_KEYS = Object.keys(COCKPIT_FOCUS_LABELS) as MobileCockpitFocusKey[]
export const MOBILE_CATEGORY_KEYS: MobileStatusCategoryKey[] = ['pipeline', 'booking', 'field', 'completed', 'paid', 'lost']

export const COCKPIT_QUERY_KEY = ['auto-key-cockpit'] as const

/** Deep link into the list view with the exact server-side filter a tile counted. */
export function focusHref(focus: MobileCockpitFocusKey): string {
  return `/auto-key?view=jobs&jobs_layout=list&focus=${focus}`
}
