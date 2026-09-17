import { describe, expect, it } from 'vitest'
import { AUTO_KEY_KANBAN_ALL_COLUMNS, findColumnForStatus } from '@/components/kanban'
import type { JobStatus } from '@/lib/api'
import { STATUS_LABELS } from '@/lib/utils'
import {
  MOBILE_ACTIVE_STATUSES,
  MOBILE_CLOSED_STATUSES,
  MOBILE_STATUS_ALIASES,
  MOBILE_STATUS_DEFINITIONS,
  MOBILE_STATUS_OPTIONS,
  canonicalMobileStatus,
  mobileStatusCategory,
  mobileStatusLabel,
} from './mobileStatus'

/**
 * Contract shared with backend/tests/test_mobile_status_vocabulary.py. Change
 * both together.
 */
const EXPECTED: Record<string, [label: string, category: string]> = {
  awaiting_quote: ['Awaiting Quote', 'pipeline'],
  awaiting_customer_details: ['Awaiting Customer Details', 'pipeline'],
  quote_sent: ['Quote Sent', 'pipeline'],
  awaiting_booking_confirmation: ['Awaiting Booking Confirmation', 'booking'],
  booking_confirmed: ['Booking Confirmed', 'booking'],
  booking_on_hold: ['Booking on Hold', 'booking'],
  en_route: ['En Route', 'field'],
  on_site: ['On Site', 'field'],
  work_completed: ['Work Completed', 'completed'],
  invoice_paid: ['Invoice Paid', 'paid'],
  failed_job: ['Failed Job', 'lost'],
  no_go: ['No Go', 'lost'],
}

const EXPECTED_ALIASES: Record<string, string> = {
  pending_booking: 'awaiting_booking_confirmation',
  booked: 'booking_confirmed',
  job_delayed: 'booking_on_hold',
  booking_completed: 'work_completed',
  awaiting_go_ahead: 'quote_sent',
  go_ahead: 'awaiting_booking_confirmation',
  working_on: 'on_site',
  service: 'on_site',
  awaiting_parts: 'booking_on_hold',
  parts_to_order: 'booking_on_hold',
  sent_to_labanda: 'booking_on_hold',
  quoted_by_labanda: 'booking_on_hold',
  at_third_party_for_quoting: 'booking_on_hold',
  third_party_quote_approved: 'booking_on_hold',
  at_third_party_repairer: 'booking_on_hold',
  completed: 'work_completed',
  awaiting_collection: 'work_completed',
  collected: 'invoice_paid',
}

// Every JobStatus literal the API can return (kept in step with backend JobStatus).
const EVERY_JOB_STATUS: JobStatus[] = [
  'awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'no_go', 'working_on', 'awaiting_parts', 'parts_to_order',
  'sent_to_labanda', 'quoted_by_labanda', 'at_third_party_for_quoting', 'third_party_quote_approved',
  'at_third_party_repairer', 'service', 'completed', 'awaiting_collection', 'collected', 'awaiting_customer_details',
  'en_route', 'on_site', 'booked', 'pending_booking', 'quote_sent', 'awaiting_booking_confirmation',
  'booking_confirmed', 'booking_on_hold', 'booking_completed', 'job_delayed', 'work_completed', 'invoice_paid', 'failed_job',
]

describe('Mobile Services status vocabulary', () => {
  it('matches the backend contract, in lifecycle order', () => {
    expect(Object.fromEntries(MOBILE_STATUS_DEFINITIONS.map(d => [d.key, [d.label, d.category]]))).toEqual(EXPECTED)
    expect(MOBILE_STATUS_OPTIONS).toEqual(Object.keys(EXPECTED))
    expect(MOBILE_STATUS_ALIASES).toEqual(EXPECTED_ALIASES)
  })

  it('gives every stored status exactly one stage, label and category', () => {
    const seen = new Map<string, string>()
    for (const definition of MOBILE_STATUS_DEFINITIONS) {
      for (const value of [definition.key, ...definition.aliases]) {
        expect(seen.has(value), `${value} is defined twice`).toBe(false)
        seen.set(value, definition.key)
      }
    }
    for (const status of EVERY_JOB_STATUS) {
      expect(seen.has(status), `${status} has no Mobile Services stage`).toBe(true)
      const canonical = canonicalMobileStatus(status)
      expect(mobileStatusLabel(status)).toBe(EXPECTED[canonical][0])
      expect(mobileStatusCategory(status)).toBe(EXPECTED[canonical][1])
    }
  })

  it('partitions every status into active or closed', () => {
    const all = new Set([...MOBILE_ACTIVE_STATUSES, ...MOBILE_CLOSED_STATUSES])
    expect(all.size).toBe(MOBILE_ACTIVE_STATUSES.length + MOBILE_CLOSED_STATUSES.length)
    expect([...all].sort()).toEqual([...EVERY_JOB_STATUS].sort())
    expect(MOBILE_CLOSED_STATUSES).toContain('work_completed')
    expect(MOBILE_ACTIVE_STATUSES).toContain('booking_on_hold')
  })

  it('places every status in exactly one Kanban column, grouped with its own stage', () => {
    for (const status of EVERY_JOB_STATUS) {
      const columns = AUTO_KEY_KANBAN_ALL_COLUMNS.filter(c => c.statuses.includes(status))
      expect(columns, `${status} column count`).toHaveLength(1)
      expect(columns[0].statuses.map(canonicalMobileStatus)).toContain(canonicalMobileStatus(status))
    }
    // The mismatch this vocabulary fixed: awaiting-confirmation jobs sat under "Quote Sent"
    // on the board while every other surface called them "Awaiting Booking Confirmation".
    expect(findColumnForStatus(AUTO_KEY_KANBAN_ALL_COLUMNS, 'awaiting_booking_confirmation')?.label).toBe(
      mobileStatusLabel('awaiting_booking_confirmation'),
    )
    expect(findColumnForStatus(AUTO_KEY_KANBAN_ALL_COLUMNS, 'pending_booking')?.key).toBe('awaiting_booking_confirmation')
  })

  it('feeds the shared STATUS_LABELS map for mobile-only statuses', () => {
    for (const key of ['quote_sent', 'awaiting_booking_confirmation', 'booking_confirmed', 'booking_on_hold', 'en_route', 'on_site', 'work_completed', 'invoice_paid', 'failed_job']) {
      expect(STATUS_LABELS[key]).toBe(mobileStatusLabel(key))
    }
    expect(STATUS_LABELS.pending_booking).toBe('Awaiting Booking Confirmation')
    expect(STATUS_LABELS.booked).toBe('Booking Confirmed')
    // Watch-repair keys keep their own wording in the shared map.
    expect(STATUS_LABELS.collected).toBe('Collected')
  })
})
