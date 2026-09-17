import { describe, expect, it } from 'vitest'
import { COCKPIT_FOCUS_KEYS, FINANCE_DATE_FIELDS, FINANCE_PRESETS, drillHref, focusHref } from './cockpitFocus'

describe('cockpit and finance drill-down links', () => {
  it('links a focus tile to the list with the same server filter', () => {
    expect(focusHref('late')).toBe('/auto-key?view=jobs&jobs_layout=list&focus=late')
    expect(COCKPIT_FOCUS_KEYS).toContain('unpaid_invoices')
  })

  it('links a finance figure to the list by date field, or to a focus', () => {
    expect(drillHref({ date_field: 'paid', date_from: '2026-09-01', date_to: '2026-09-30', directory: 'all' })).toBe(
      '/auto-key?view=jobs&jobs_layout=list&date_field=paid&date_from=2026-09-01&date_to=2026-09-30',
    )
    expect(drillHref({ focus: 'unpaid_invoices' })).toBe('/auto-key?view=jobs&jobs_layout=list&focus=unpaid_invoices')
    expect(drillHref({ date_field: 'paid' })).toBeNull()
    expect(drillHref(null)).toBeNull()
  })

  it('keeps the date fields and presets in step with the API', () => {
    expect(FINANCE_DATE_FIELDS).toEqual(['created', 'scheduled', 'completed', 'invoiced', 'paid'])
    expect(FINANCE_PRESETS.map(p => p.key)).toEqual(['week', 'last_week', 'month', 'last_month', 'quarter', 'last_4_weeks', 'last_13_weeks', 'custom'])
  })
})
