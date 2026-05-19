import { describe, expect, it } from 'vitest'
import {
  effectiveMinitPlanCode,
  isMinitHqUi,
  resolveMinitHqUi,
} from '@/lib/minitProduct'

describe('resolveMinitHqUi', () => {
  it('detects mmsupport slug regardless of plan', () => {
    expect(resolveMinitHqUi({ tenantSlug: 'mmsupport', planCode: 'pro', product: 'mainspring' })).toBe(true)
    expect(resolveMinitHqUi({ tenantSlug: 'MMSupport', planCode: 'pro', product: 'mainspring' })).toBe(true)
  })

  it('detects minit_hq plan regardless of slug', () => {
    expect(resolveMinitHqUi({ tenantSlug: 'other', planCode: 'minit_hq', product: 'minit' })).toBe(true)
  })

  it('detects minit product with minit_hq plan', () => {
    expect(resolveMinitHqUi({ tenantSlug: null, planCode: 'minit_hq', product: 'minit' })).toBe(true)
  })

  it('uses last login slug before session loads', () => {
    expect(
      resolveMinitHqUi({
        tenantSlug: null,
        planCode: 'pro',
        product: 'mainspring',
        lastLoginSlug: 'mmsupport',
      }),
    ).toBe(true)
  })

  it('does not treat retail minit- shops as HQ', () => {
    expect(resolveMinitHqUi({ tenantSlug: 'minit-3269', planCode: 'booking_only', product: 'minit' })).toBe(false)
    expect(resolveMinitHqUi({ tenantSlug: 'minit-3269', planCode: 'pro', product: 'minit' })).toBe(false)
  })

  it('honours debug force flag', () => {
    expect(resolveMinitHqUi({ tenantSlug: 'myshop', planCode: 'pro', debugForce: true })).toBe(true)
  })
})

describe('isMinitHqUi', () => {
  it('delegates to resolveMinitHqUi', () => {
    expect(isMinitHqUi('minit', 'minit_hq', 'mmsupport')).toBe(true)
    expect(isMinitHqUi('mainspring', 'pro', 'myshop')).toBe(false)
  })
})

describe('effectiveMinitPlanCode', () => {
  it('maps mmsupport to minit_hq', () => {
    expect(effectiveMinitPlanCode('pro', 'mmsupport')).toBe('minit_hq')
    expect(effectiveMinitPlanCode(null, 'mmsupport')).toBe('minit_hq')
  })
})
