import { describe, expect, it } from 'vitest'
import {
  defaultHomePathForMinit,
  effectiveMinitPlanCode,
  isMinitRestrictedUi,
  isMinitHqUi,
  resolveMinitHqUi,
} from '@/lib/minitProduct'

describe('resolveMinitHqUi', () => {
  it('prefers server is_minit_hq_ui when provided', () => {
    expect(
      resolveMinitHqUi({
        tenantSlug: 'other',
        planCode: 'pro',
        product: 'mainspring',
        serverMinitHqUi: true,
      }),
    ).toBe(true)
    expect(
      resolveMinitHqUi({
        tenantSlug: 'mmsupport',
        planCode: 'minit_hq',
        product: 'minit',
        serverMinitHqUi: false,
      }),
    ).toBe(false)
  })

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

  it('does not use last login slug when session is a retail shop', () => {
    expect(
      resolveMinitHqUi({
        tenantSlug: 'minit-3269',
        planCode: 'booking_only',
        product: 'minit',
        lastLoginSlug: 'mmsupport',
      }),
    ).toBe(false)
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

describe('isMinitRestrictedUi', () => {
  it('keeps HQ and retail shopfronts in the Minit UI', () => {
    expect(isMinitRestrictedUi('minit', 'minit_hq', 'mmsupport')).toBe(true)
    expect(isMinitRestrictedUi('minit', 'booking_only', 'minit-3269')).toBe(true)
    // A shopfront still stored on a Mainspring plan is treated as booking_only.
    expect(isMinitRestrictedUi('minit', 'pro', 'minit-3269')).toBe(true)
  })

  it('gives a Minit mobile van on Auto Key Basic the normal app', () => {
    expect(isMinitRestrictedUi('minit', 'basic_auto_key', 'minit-mobile-3904')).toBe(false)
  })

  it('never sends a van to the Parent Account page it cannot open', () => {
    // FeatureGate only uses the Minit home when the restricted UI applies; the
    // van falls back to /dashboard like any Auto Key shop.
    const restricted = isMinitRestrictedUi('minit', 'basic_auto_key', 'minit-mobile-3904')
    const home = restricted ? defaultHomePathForMinit('basic_auto_key', 'minit-mobile-3904') : '/dashboard'
    expect(home).toBe('/dashboard')
  })
})
