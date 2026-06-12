import { describe, it, expect } from 'vitest'
import { safeNextPath } from './safeNext'

describe('safeNextPath', () => {
  it('allows same-origin absolute paths', () => {
    expect(safeNextPath('/jobs/123')).toBe('/jobs/123')
    expect(safeNextPath('/shoe-repairs/abc?tab=details')).toBe('/shoe-repairs/abc?tab=details')
    expect(safeNextPath('/')).toBe('/')
  })

  it('rejects empty / missing values', () => {
    expect(safeNextPath(null)).toBeNull()
    expect(safeNextPath(undefined)).toBeNull()
    expect(safeNextPath('')).toBeNull()
  })

  it('rejects off-site and relative targets', () => {
    expect(safeNextPath('https://evil.com')).toBeNull()
    expect(safeNextPath('jobs/123')).toBeNull()
    expect(safeNextPath('mailto:a@b.com')).toBeNull()
  })

  it('rejects protocol-relative and backslash open-redirect tricks', () => {
    expect(safeNextPath('//evil.com')).toBeNull()
    expect(safeNextPath('/\\evil.com')).toBeNull()
  })
})
