import type { MobileCockpitFocusKey, MobileFinanceDateField, MobileFinanceDrill, MobileFinancePreset, MobileStatusCategoryKey } from '@/lib/api'

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

/** Finance drill-downs: which job/invoice date the list is filtered on. */
export const FINANCE_DATE_FIELD_LABELS: Record<MobileFinanceDateField, string> = {
  created: 'Jobs created',
  scheduled: 'Jobs booked',
  completed: 'Jobs completed',
  invoiced: 'Jobs invoiced',
  paid: 'Jobs paid',
}
export const FINANCE_DATE_FIELDS = Object.keys(FINANCE_DATE_FIELD_LABELS) as MobileFinanceDateField[]

export const FINANCE_PRESETS: Array<{ key: MobileFinancePreset; label: string }> = [
  { key: 'week', label: 'This week' },
  { key: 'last_week', label: 'Last week' },
  { key: 'month', label: 'This month' },
  { key: 'last_month', label: 'Last month' },
  { key: 'quarter', label: 'This quarter' },
  { key: 'last_4_weeks', label: 'Last 4 weeks' },
  { key: 'last_13_weeks', label: 'Last 13 weeks' },
  { key: 'custom', label: 'Custom' },
]

/** Deep link into the list with the exact server filter behind a finance figure. */
export function drillHref(drill: MobileFinanceDrill | null): string | null {
  if (!drill) return null
  if (drill.focus) return focusHref(drill.focus)
  if (!drill.date_field || !drill.date_from || !drill.date_to) return null
  const params = new URLSearchParams({ view: 'jobs', jobs_layout: 'list', date_field: drill.date_field, date_from: drill.date_from, date_to: drill.date_to })
  return `/auto-key?${params.toString()}`
}
