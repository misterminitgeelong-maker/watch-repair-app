import { describe, expect, it } from 'vitest'
import { autoKeyPosHref, isPosQuoteMode, parsePosModeParam } from './posMode'

describe('parsePosModeParam', () => {
  it('accepts quote and sale', () => {
    expect(parsePosModeParam('quote')).toBe('quote')
    expect(parsePosModeParam('sale')).toBe('sale')
  })

  it('ignores anything else', () => {
    expect(parsePosModeParam(null)).toBeNull()
    expect(parsePosModeParam('')).toBeNull()
    expect(parsePosModeParam('checkout')).toBeNull()
  })
})

describe('isPosQuoteMode', () => {
  it('honours an explicit New Quote / Complete sale choice', () => {
    expect(isPosQuoteMode({ explicitMode: 'quote', job: { status: 'on_site' } })).toBe(true)
    expect(isPosQuoteMode({ explicitMode: 'sale', job: { status: 'awaiting_quote' } })).toBe(false)
  })

  it('defaults quoting and booking-request jobs to quote mode', () => {
    expect(isPosQuoteMode({ job: { status: 'awaiting_quote' } })).toBe(true)
    expect(isPosQuoteMode({ job: { status: 'quote_sent' } })).toBe(true)
    expect(isPosQuoteMode({ job: { status: 'awaiting_customer_details' } })).toBe(true)
    expect(isPosQuoteMode({ job: { status: 'pending_booking' } })).toBe(true)
    expect(isPosQuoteMode({ job: { status: 'booking_confirmed', shop_mobile_booking_request_id: 'req-1' } })).toBe(true)
  })

  it('keeps the till in sale mode for on-site collect and invoiced jobs', () => {
    expect(isPosQuoteMode({ job: { status: 'on_site' } })).toBe(false)
    expect(isPosQuoteMode({ job: { status: 'work_completed' } })).toBe(false)
    expect(isPosQuoteMode({ job: { status: 'invoice_paid' } })).toBe(false)
    expect(isPosQuoteMode({ job: { status: 'on_site', shop_mobile_booking_request_id: 'req-1' } })).toBe(false)
  })

  it('is a sale (walk-in till) when no job is linked', () => {
    expect(isPosQuoteMode({})).toBe(false)
    expect(isPosQuoteMode({ job: null })).toBe(false)
  })
})

describe('autoKeyPosHref', () => {
  it('opens POS on the job, with optional quote mode', () => {
    expect(autoKeyPosHref('job-1')).toBe('/auto-key?view=pos&job_id=job-1')
    expect(autoKeyPosHref('job-1', 'quote')).toBe('/auto-key?view=pos&job_id=job-1&mode=quote')
  })
})
