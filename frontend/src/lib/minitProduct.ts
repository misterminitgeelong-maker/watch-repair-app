import type { FeatureKey, PlanCode } from '@/lib/api'
import { isMinitTenantSlug, MINIT_HQ_SLUG } from '@/lib/minitBranding'

export type TenantProduct = 'minit' | 'mainspring'

/** Mainspring repair/POS plans that Minit tenants must never keep in the UI. */
const MINIT_DISALLOWED_PLANS = new Set([
  'pro',
  'enterprise',
  'basic_watch',
  'basic_shoe',
  'basic_watch_shoe',
  'basic_watch_auto_key',
  'basic_shoe_auto_key',
  'basic_all_tabs',
])

const SESSION_SNAPSHOT_KEY = 'mainspring.sessionSnapshot.v1'

export type SessionSnapshot = {
  product: TenantProduct
  planCode: PlanCode
  tenantSlug: string
  enabledFeatures: FeatureKey[]
}

export function tenantProductFromSlug(slug: string | null | undefined): TenantProduct {
  return isMinitTenantSlug(slug) ? 'minit' : 'mainspring'
}

export function isMinitProduct(product: TenantProduct | null | undefined): boolean {
  return product === 'minit'
}

export function isMinitHqPlan(planCode: PlanCode | null | undefined): boolean {
  return planCode === 'minit_hq'
}

export function isMinitHqTenantSlug(tenantSlug: string | null | undefined): boolean {
  return (tenantSlug || '').trim().toLowerCase() === MINIT_HQ_SLUG
}

/** True when the signed-in tenant should see the six-item Minit HQ sidebar. */
export function isMinitHqUi(
  _product: TenantProduct | null | undefined,
  planCode: PlanCode | null | undefined,
  tenantSlug: string | null | undefined,
): boolean {
  if (isMinitHqPlan(planCode)) return true
  return isMinitHqTenantSlug(tenantSlug)
}

export function isMinitBookingOnlyPlan(planCode: PlanCode | null | undefined): boolean {
  return planCode === 'booking_only'
}

/** Mirrors backend `effective_plan_code` for session snapshot and first paint. */
export function effectiveMinitPlanCode(
  planCode: PlanCode | null | undefined,
  tenantSlug: string | null | undefined,
): PlanCode {
  const slug = (tenantSlug || '').trim().toLowerCase()
  if (slug === MINIT_HQ_SLUG) {
    return 'minit_hq'
  }
  if (slug.startsWith('minit-')) {
    if (isMinitHqPlan(planCode) || isMinitBookingOnlyPlan(planCode)) return planCode!
    if (planCode && MINIT_DISALLOWED_PLANS.has(String(planCode))) return 'booking_only'
  }
  return planCode ?? 'pro'
}

/** Plan defaults mirrored from backend `PLAN_FEATURES` (subset used by Minit UI). */
const PLAN_FEATURE_DEFAULTS: Partial<Record<PlanCode, FeatureKey[]>> = {
  booking_only: ['shop_mobile_booking'],
  minit_hq: ['shop_mobile_booking', 'multi_site'],
}

export function featuresForPlan(planCode: PlanCode | null | undefined): FeatureKey[] {
  if (!planCode) return []
  return PLAN_FEATURE_DEFAULTS[planCode] ?? []
}

export function mergeEnabledFeatures(planCode: PlanCode, enabled: FeatureKey[]): FeatureKey[] {
  const fromPlan = featuresForPlan(planCode)
  if (!fromPlan.length && enabled.length) return enabled
  return [...new Set([...enabled, ...fromPlan])]
}

/** True when the tenant should see the Minit mobile-network UI (not Mainspring repair POS). */
export function isMinitRestrictedUi(
  product: TenantProduct | null | undefined,
  planCode: PlanCode | null | undefined,
  tenantSlug?: string | null,
): boolean {
  if (product === 'minit') return true
  const effective = effectiveMinitPlanCode(planCode, tenantSlug)
  if (isMinitHqPlan(effective) || isMinitBookingOnlyPlan(effective)) return true
  return isMinitTenantSlug(tenantSlug)
}

export function minitHqAllowedPath(pathname: string): boolean {
  return /^\/minit(\/|$)/.test(pathname) || pathname === '/subscription-required'
}

export function minitBookingOnlyAllowedPath(pathname: string): boolean {
  return /^\/(shop-mobile-bookings|accounts|subscription-required)(\/|$)/.test(pathname)
}

export function defaultHomePathForMinit(
  planCode: PlanCode | null | undefined,
  tenantSlug?: string | null,
): string {
  const effective = effectiveMinitPlanCode(planCode, tenantSlug)
  if (isMinitHqPlan(effective) || isMinitHqTenantSlug(tenantSlug)) return '/minit/dashboard'
  if (isMinitBookingOnlyPlan(effective)) return '/shop-mobile-bookings'
  return '/parent-account'
}

export function normalizeSessionSnapshot(snapshot: SessionSnapshot): SessionSnapshot {
  const product =
    snapshot.product === 'minit' || snapshot.product === 'mainspring'
      ? snapshot.product
      : tenantProductFromSlug(snapshot.tenantSlug)
  const planCode = effectiveMinitPlanCode(snapshot.planCode, snapshot.tenantSlug)
  return {
    ...snapshot,
    product,
    planCode,
    enabledFeatures: mergeEnabledFeatures(planCode, snapshot.enabledFeatures),
  }
}

export function readSessionSnapshot(): SessionSnapshot | null {
  try {
    const raw = sessionStorage.getItem(SESSION_SNAPSHOT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SessionSnapshot
    if (!parsed?.tenantSlug || !parsed?.planCode || !Array.isArray(parsed.enabledFeatures)) return null
    return normalizeSessionSnapshot({
      product:
        parsed.product === 'minit' || parsed.product === 'mainspring'
          ? parsed.product
          : tenantProductFromSlug(parsed.tenantSlug),
      planCode: parsed.planCode,
      tenantSlug: parsed.tenantSlug,
      enabledFeatures: parsed.enabledFeatures,
    })
  } catch {
    return null
  }
}

export function writeSessionSnapshot(snapshot: SessionSnapshot): void {
  try {
    sessionStorage.setItem(SESSION_SNAPSHOT_KEY, JSON.stringify(snapshot))
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearSessionSnapshot(): void {
  try {
    sessionStorage.removeItem(SESSION_SNAPSHOT_KEY)
  } catch {
    /* ignore */
  }
}
