import { describe, expect, it } from 'vitest'
import { AUTO_KEY_KANBAN_COLUMNS, findColumnForStatus } from '@/components/kanban'
import {
  AUTO_KEY_CLOSED_STATUSES,
  canonicalAutoKeyStatus,
  computeSlaChip,
} from './dispatchHelpers'

describe('Mobile Services legacy status compatibility', () => {
  it.each([
    ['awaiting_go_ahead', 'quote_sent'],
    ['go_ahead', 'awaiting_booking_confirmation'],
    ['working_on', 'on_site'],
    ['completed', 'work_completed'],
    ['awaiting_collection', 'work_completed'],
    ['collected', 'invoice_paid'],
  ])('canonicalises %s to %s', (legacy, canonical) => {
    expect(canonicalAutoKeyStatus(legacy)).toBe(canonical)
  })

  it('treats imported completed states as operationally closed', () => {
    expect(AUTO_KEY_CLOSED_STATUSES).toEqual(expect.arrayContaining(['completed', 'awaiting_collection', 'collected']))
    expect(computeSlaChip({ status: 'completed', scheduled_at: '2020-01-01T00:00:00Z', created_at: '2020-01-01T00:00:00Z' })).toBeNull()
  })

  it.each([
    ['awaiting_go_ahead', 'quote_sent'],
    ['go_ahead', 'quote_sent'],
    ['working_on', 'en_route'],
    ['awaiting_parts', 'booking_on_hold'],
    ['completed', 'booking_completed'],
    ['collected', 'booking_completed'],
  ])('keeps %s visible in the %s Kanban column', (status, columnKey) => {
    expect(findColumnForStatus(AUTO_KEY_KANBAN_COLUMNS, status)?.key).toBe(columnKey)
  })
})
