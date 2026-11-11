import { describe, expect, it } from 'vitest'
import { ACTIVE_DIRECTORY_STATUSES, CLOSED_DIRECTORY_STATUSES } from '@/lib/utils'
import { countActiveWatchJobs, isActiveShoeStatus, isActiveWatchStatus } from './activeJobs'

describe('active job definition', () => {
  it('matches the Watch directory tabs exactly', () => {
    for (const s of ACTIVE_DIRECTORY_STATUSES) expect(isActiveWatchStatus(s)).toBe(true)
    for (const s of CLOSED_DIRECTORY_STATUSES) expect(isActiveWatchStatus(s)).toBe(false)
  })

  it('counts completed and awaiting-collection watches as active, like the Jobs page', () => {
    // The L16 report: dashboard said 7 while the Jobs page said 11.
    const summary = { awaiting_quote: 3, working_on: 4, completed: 2, awaiting_collection: 2, collected: 9 }
    expect(countActiveWatchJobs(summary)).toBe(11)
  })

  it('treats shoe no-go and finished work as closed', () => {
    expect(isActiveShoeStatus('working_on')).toBe(true)
    expect(isActiveShoeStatus('no_go')).toBe(false)
    expect(isActiveShoeStatus('awaiting_collection')).toBe(false)
  })

  it('keeps waiting-for-parts, quote and customer-detail shoe jobs visible as active', () => {
    const rows = ['awaiting_parts', 'quote_sent', 'awaiting_customer_details', 'parts_to_order', 'collected']
    expect(rows.filter(isActiveShoeStatus)).toEqual(rows.slice(0, 4))
  })
})
