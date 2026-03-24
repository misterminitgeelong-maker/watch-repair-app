import { describe, it, expect } from 'vitest'
import type { AxiosError } from 'axios'
import { buildImportCsvQueryString, compactListParams, getApiErrorMessage } from './api'

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

  it('returns Error message for plain Error before fallback', () => {
    expect(getApiErrorMessage(new Error('oops'), 'Custom fallback')).toBe('oops')
  })

  it('returns default fallback for axios 500 without detail when not an Error instance', () => {
    const err = axiosLikeError({
      response: { status: 500, data: {} },
    })
    expect(getApiErrorMessage(err)).toBe('Request failed.')
  })
})

describe('compactListParams', () => {
  it('passes limit, offset, sort_by, sort_dir', () => {
    expect(
      compactListParams({
        limit: 50,
        offset: 100,
        sort_by: 'created_at',
        sort_dir: 'desc',
      }),
    ).toEqual({ limit: 50, offset: 100, sort_by: 'created_at', sort_dir: 'desc' })
  })

  it('omits empty string and undefined', () => {
    expect(
      compactListParams({
        limit: 50,
        offset: 0,
        status: '',
        assigned_user_id: undefined,
      }),
    ).toEqual({ limit: 50, offset: 0 })
  })
})

describe('buildImportCsvQueryString', () => {
  it('adds dry_run=true when dryRun is set', () => {
    expect(buildImportCsvQueryString({ dryRun: true })).toBe('?dry_run=true')
  })

  it('combines dry run with replace_existing', () => {
    const q = buildImportCsvQueryString({ dryRun: true, replaceExisting: true })
    expect(q).toContain('dry_run=true')
    expect(q).toContain('replace_existing=true')
  })
})
