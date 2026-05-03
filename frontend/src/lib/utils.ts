import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCents(cents: number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100)
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/** Format estimated turnaround for shoe repairs: "3–5 days" or "~3 days" */
export function formatEstimatedTurnaround(min: number, max: number): string {
  if (min === max) return `~${min} day${min === 1 ? '' : 's'}`
  return `${min}–${max} days`
}

export const COMPLEXITY_LABELS: Record<string, string> = {
  simple: 'Simple',
  standard: 'Standard',
  complex: 'Complex',
}

// Single source of truth for job status order (watch repair directory views)
export const JOB_STATUS_ORDER = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'no_go',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'service',
  'completed',
  'awaiting_collection',
  'collected',
] as const

export const ACTIVE_DIRECTORY_STATUSES = [
  'awaiting_quote', 'awaiting_customer_details', 'awaiting_go_ahead', 'quote_sent',
  'go_ahead', 'parts_to_order', 'sent_to_labanda', 'quoted_by_labanda', 'awaiting_parts',
  'working_on', 'service', 'completed', 'awaiting_collection',
] as const

export const CLOSED_DIRECTORY_STATUSES = ['no_go', 'collected'] as const

/** Same order as backend `_WATCH_QUEUE_SEQUENCE` — watch Tinder queue only. */
export const WATCH_QUEUE_SWIPE_SEQUENCE = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'service',
  'completed',
  'awaiting_collection',
  'collected',
] as const

export type WatchQueueSwipeStatus = (typeof WATCH_QUEUE_SWIPE_SEQUENCE)[number]

/** Next status after a queue swipe, or null if swipe is invalid for this status/direction. */
export function previewWatchQueueSwipe(
  current: string,
  direction: 'left' | 'right',
): WatchQueueSwipeStatus | null {
  const idx = WATCH_QUEUE_SWIPE_SEQUENCE.indexOf(current as WatchQueueSwipeStatus)
  if (idx < 0) return null
  if (direction === 'right') {
    if (idx >= WATCH_QUEUE_SWIPE_SEQUENCE.length - 1) return null
    return WATCH_QUEUE_SWIPE_SEQUENCE[idx + 1]
  }
  if (idx <= 0) return null
  return WATCH_QUEUE_SWIPE_SEQUENCE[idx - 1]
}

export const STATUS_LABELS: Record<string, string> = {
  awaiting_quote:      'Awaiting Quote',
  awaiting_customer_details: 'Awaiting customer details',
  awaiting_go_ahead:   'Awaiting Go Ahead',
  go_ahead:            'Go Ahead Given',
  no_go:               'No Go',
  working_on:          'Started Work',
  awaiting_parts:      'Awaiting Parts',
  parts_to_order:      'Parts Ordered',
  sent_to_labanda:     'Sent to Labanda',
  quoted_by_labanda:   'Quoted by Labanda',
  service:             'Service',
  completed:           'Work Completed',
  awaiting_collection: 'Ready for Collection',
  collected:           'Collected',
  en_route:            'En Route',
  on_site:             'On Site',
  pending_booking:     'Awaiting booking confirm',
  booked:              'Confirmed booking',
  quote_sent:                    'Quote Sent',
  awaiting_booking_confirmation: 'Awaiting Booking Confirmation',
  booking_confirmed:             'Booking Confirmed',
  booking_on_hold:               'Booking on Hold',
  booking_completed:             'Booking Completed',
  job_delayed:                   'Job Delayed',
  work_completed:                'Work Completed',
  invoice_paid:                  'Invoice Paid',
  failed_job:                    'Failed Job',
  draft:               'Draft',
  sent:                'Sent',
  approved:            'Approved',
  declined:            'Declined',
  expired:             'Expired',
  unpaid:              'Unpaid',
  paid:                'Paid',
  void:                'Void',
}

export const STATUS_COLORS: Record<string, string> = {
  // Watch repair statuses — all use CSS variables so they adapt to every theme
  awaiting_quote:      'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  awaiting_customer_details: 'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  awaiting_go_ahead:   'bg-[var(--ms-badge-wait-bg)] text-[var(--ms-badge-wait-text)]',
  go_ahead:            'bg-[var(--ms-badge-blue-bg)] text-[var(--ms-badge-blue-text)]',
  no_go:               'bg-[var(--ms-badge-alert-bg)] text-[var(--ms-badge-alert-text)]',
  working_on:          'bg-[var(--ms-badge-orange-bg)] text-[var(--ms-badge-orange-text)]',
  awaiting_parts:      'bg-[var(--ms-badge-alert-bg)] text-[var(--ms-badge-alert-text)]',
  parts_to_order:      'bg-[var(--ms-badge-orange-bg)] text-[var(--ms-badge-orange-text)]',
  sent_to_labanda:     'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  quoted_by_labanda:   'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  service:             'bg-[var(--ms-badge-teal-bg)] text-[var(--ms-badge-teal-text)]',
  completed:           'bg-[var(--ms-badge-done-bg)] text-[var(--ms-badge-done-text)]',
  awaiting_collection: 'bg-[var(--ms-badge-wait-bg)] text-[var(--ms-badge-wait-text)]',
  collected:           'bg-[var(--ms-badge-teal-bg)] text-[var(--ms-badge-teal-text)]',
  // Mobile Services dispatch statuses
  en_route:            'bg-[#EDE5F5] text-[#5D4A9B]',  // purple — intentional, no theme var
  on_site:             'bg-[var(--ms-badge-green-bg)] text-[var(--ms-badge-green-text)]',
  pending_booking:     'bg-[var(--ms-badge-orange-bg)] text-[var(--ms-badge-orange-text)]',
  booked:              'bg-[var(--ms-badge-blue-bg)] text-[var(--ms-badge-blue-text)]',
  quote_sent:                    'bg-[var(--ms-badge-blue-bg)] text-[var(--ms-badge-blue-text)]',
  awaiting_booking_confirmation: 'bg-[var(--ms-badge-wait-bg)] text-[var(--ms-badge-wait-text)]',
  booking_confirmed:             'bg-[var(--ms-badge-blue-bg)] text-[var(--ms-badge-blue-text)]',
  booking_on_hold:               'bg-[var(--ms-badge-orange-bg)] text-[var(--ms-badge-orange-text)]',
  booking_completed:             'bg-[var(--ms-badge-done-bg)] text-[var(--ms-badge-done-text)]',
  job_delayed:                   'bg-[var(--ms-badge-orange-bg)] text-[var(--ms-badge-orange-text)]',
  work_completed:                'bg-[var(--ms-badge-done-bg)] text-[var(--ms-badge-done-text)]',
  invoice_paid:                  'bg-[var(--ms-badge-teal-bg)] text-[var(--ms-badge-teal-text)]',
  failed_job:                    'bg-[var(--ms-badge-alert-bg)] text-[var(--ms-badge-alert-text)]',
  // Quote / Invoice statuses
  draft:               'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  sent:                'bg-[var(--ms-badge-blue-bg)] text-[var(--ms-badge-blue-text)]',
  approved:            'bg-[var(--ms-badge-done-bg)] text-[var(--ms-badge-done-text)]',
  declined:            'bg-[var(--ms-badge-alert-bg)] text-[var(--ms-badge-alert-text)]',
  expired:             'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  unpaid:              'bg-[var(--ms-badge-wait-bg)] text-[var(--ms-badge-wait-text)]',
  paid:                'bg-[var(--ms-badge-done-bg)] text-[var(--ms-badge-done-text)]',
  void:                'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
}
