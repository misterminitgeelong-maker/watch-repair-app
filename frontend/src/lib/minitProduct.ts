import type { FeatureKey, PlanCode } from '@/lib/api'
import { isMinitTenantSlug } from '@/lib/minitBranding'

export type TenantProduct = 'minit' | 'mainspring'

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

export function isMinitBookingOnlyPlan(planCode: PlanCode | null | undefined): boolean {
  return planCode === 'booking_only'
}

/** True when the tenant should see the Minit mobile-network UI (not Mainspring repair POS). */
export function isMinitRestrictedUi(
  product: TenantProduct | null | undefined,
  planCode: PlanCode | null | undefined,
  tenantSlug?: string | null,
): boolean {
  if (product === 'minit') return true
  if (isMinitHqPlan(planCode) || isMinitBookingOnlyPlan(planCode)) return true
  return isMinitTenantSlug(tenantSlug)
}

export function minitHqAllowedPath(pathname: string): boolean {
  return /^\/(parent-account|shop-mobile-bookings|accounts|subscription-required)(\/|$)/.test(pathname)
}

export function minitBookingOnlyAllowedPath(pathname: string): boolean {
  return /^\/(shop-mobile-bookings|accounts|subscription-required)(\/|$)/.test(pathname)
}

export function defaultHomePathForMinit(planCode: PlanCode | null | undefined): string {
  if (isMinitHqPlan(planCode)) return '/parent-account'
  if (isMinitBookingOnlyPlan(planCode)) return '/shop-mobile-bookings'
  return '/parent-account'
}

export function readSessionSnapshot(): SessionSnapshot | null {
  try {
    const raw = sessionStorage.getItem(SESSION_SNAPSHOT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as SessionSnapshot
    if (!parsed?.tenantSlug || !parsed?.planCode || !Array.isArray(parsed.enabledFeatures)) return null
    return parsed
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
