import { describe, it, expect } from 'vitest'
import type { AxiosError } from 'axios'
import { getApiErrorMessage } from './api'

describe('getApiErrorMessage', () => {
  it('returns detail string when response has detail string', () => {
    const err = Object.assign(new Error('Request failed'), {
      response: { status: 400, data: { detail: 'Tenant slug already exists' } },
    }) as unknown as AxiosError
    expect(getApiErrorMessage(err)).toBe('Tenant slug already exists')
  })

  it('returns first validation message when detail is array', () => {
    const err = Object.assign(new Error('Request failed'), {
      response: {
        status: 422,
        data: {
          detail: [
            { msg: 'Field required', type: 'value_error' },
            { msg: 'Invalid email' },
          ],
        },
      },
    }) as unknown as AxiosError
    expect(getApiErrorMessage(err)).toBe('Field required')
  })

  it('returns session expired message for 401', () => {
    const err = Object.assign(new Error('Request failed'), {
      response: { status: 401, data: {} },
    }) as unknown as AxiosError
    expect(getApiErrorMessage(err)).toBe('Session expired. Please sign in again.')
  })

  it('returns fallback for non-axios error', () => {
    expect(getApiErrorMessage(new Error('oops'), 'Custom fallback')).toBe('Custom fallback')
  })

  it('returns default fallback when no detail', () => {
    const err = Object.assign(new Error('Request failed'), {
      response: { status: 500, data: {} },
    }) as unknown as AxiosError
    expect(getApiErrorMessage(err)).toBe('Request failed.')
  })
})
