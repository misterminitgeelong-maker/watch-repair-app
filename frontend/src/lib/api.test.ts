import { describe, it, expect } from 'vitest'
import type { AxiosError } from 'axios'
import { API_ROUTES, getApiErrorMessage } from './api'

function axiosLikeError(partial: Partial<AxiosError> & { response: AxiosError['response'] }): AxiosError {
  return { isAxiosError: true, name: 'AxiosError', message: 'Request failed', ...partial } as AxiosError
}

describe('getApiErrorMessage', () => {
  it('returns detail string when response has detail string', () => {
    const err = axiosLikeError({
      response: { status: 400, data: { detail: 'Tenant slug already exists' } },
    })
    expect(getApiErrorMessage(err)).toBe('Tenant slug already exists')
  })

  it('returns first validation message when detail is array', () => {
    const err = axiosLikeError({
      response: {
        status: 422,
        data: {
          detail: [
            { msg: 'Field required', type: 'value_error' },
            { msg: 'Invalid email' },
          ],
        },
      },
    })
    expect(getApiErrorMessage(err)).toBe('Field required')
  })

  it('returns session expired message for 401', () => {
    const err = axiosLikeError({
      response: { status: 401, data: {} },
    })
    expect(getApiErrorMessage(err)).toBe('Session expired. Please sign in again.')
  })

  it('returns fallback for plain Error values', () => {
    expect(getApiErrorMessage(new Error('oops'), 'Custom fallback')).toBe('Custom fallback')
  })

  it('returns default fallback for axios 500 without detail when not an Error instance', () => {
    const err = axiosLikeError({
      response: { status: 500, data: {} },
    })
    expect(getApiErrorMessage(err)).toBe('Request failed.')
  })
})

describe('API route contracts', () => {
  it('keeps public auto-key invoice/booking routes singular', () => {
    expect(API_ROUTES.publicAutoKeyInvoice('abc123')).toBe('/v1/public/auto-key-invoice/abc123')
    expect(API_ROUTES.publicAutoKeyInvoiceCheckout('abc123')).toBe('/v1/public/auto-key-invoice/abc123/checkout')
    expect(API_ROUTES.publicAutoKeyBooking('abc123')).toBe('/v1/public/auto-key-booking/abc123')
    expect(API_ROUTES.publicAutoKeyBookingConfirm('abc123')).toBe('/v1/public/auto-key-booking/abc123/confirm')
  })

  it('uses token-free attachment helper routes', () => {
    expect(API_ROUTES.attachmentDownload('folder/file.png')).toBe('/v1/attachments/download/folder%2Ffile.png')
    expect(API_ROUTES.attachmentDownloadLink('folder/file.png')).toBe('/attachments/download-link/folder%2Ffile.png')
  })
})
