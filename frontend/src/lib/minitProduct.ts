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
const LAST_LOGIN_TENANT_SLUG_KEY = 'mainspring.lastLoginTenantSlug.v1'

let minitHqNavMismatchWarned = false

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

export type MinitHqUiContext = {
  product?: TenantProduct | null
  planCode?: PlanCode | null
  tenantSlug?: string | null
  /** Persisted from login form — used before /auth/session returns. */
  lastLoginSlug?: string | null
  /** From GET /auth/session — overrides client heuristics when present. */
  serverMinitHqUi?: boolean | null
  /** Dev/diagnostic: ?minit_hq=1 forces HQ nav. */
  debugForce?: boolean
}

/** True when `?minit_hq=1` is in the URL (diagnostic override). */
export function isMinitHqDebugForced(): boolean {
  try {
    return new URLSearchParams(window.location.search).get('minit_hq') === '1'
  } catch {
    return false
  }
}

/**
 * Single gate for Minit HQ UI — any matching signal renders the six-item sidebar only.
 * Retail `minit-*` shops (booking_only) are explicitly excluded unless plan is minit_hq.
 */
export function resolveMinitHqUi(ctx: MinitHqUiContext): boolean {
  if (ctx.debugForce || isMinitHqDebugForced()) return true
  if (ctx.serverMinitHqUi === true) return true
  if (ctx.serverMinitHqUi === false) return false

  const sessionSlug = (ctx.tenantSlug || '').trim().toLowerCase()
  const loginSlug = (ctx.lastLoginSlug || readLastLoginTenantSlug() || '').trim().toLowerCase()
  const slug = sessionSlug || loginSlug

  if (isMinitHqTenantSlug(sessionSlug)) return true
  if (isMinitHqTenantSlug(loginSlug)) return true
  if (isMinitHqPlan(ctx.planCode)) return true
  if (ctx.product === 'minit' && isMinitHqPlan(ctx.planCode)) return true

  const effective = effectiveMinitPlanCode(ctx.planCode, slug || ctx.tenantSlug)
  if (isMinitHqPlan(effective)) return true

  return false
}

/** True when the signed-in tenant should see the six-item Minit HQ sidebar. */
export function isMinitHqUi(
  product: TenantProduct | null | undefined,
  planCode: PlanCode | null | undefined,
  tenantSlug: string | null | undefined,
): boolean {
  return resolveMinitHqUi({ product, planCode, tenantSlug })
}

/** Warn once when HQ tenant would get non-HQ nav (stale bundle / session). */
export function warnIfMinitHqNavMismatch(showingHqNav: boolean, ctx: MinitHqUiContext): void {
  if (showingHqNav || minitHqNavMismatchWarned) return
  const slug =
    (ctx.tenantSlug || ctx.lastLoginSlug || readLastLoginTenantSlug() || '').trim().toLowerCase()
  if (!isMinitHqTenantSlug(slug) && !isMinitHqPlan(ctx.planCode)) return
  minitHqNavMismatchWarned = true
  console.warn(
    '[Minit HQ] Expected six-item HQ sidebar but rendered standard nav. Hard refresh (Ctrl+Shift+R) or clear site data.',
    { tenantSlug: ctx.tenantSlug, planCode: ctx.planCode, product: ctx.product, slugHint: slug },
  )
}

export function readLastLoginTenantSlug(): string | null {
  try {
    const raw = localStorage.getItem(LAST_LOGIN_TENANT_SLUG_KEY)
    return raw?.trim() || null
  } catch {
    return null
  }
}

export function writeLastLoginTenantSlug(slug: string): void {
  try {
    localStorage.setItem(LAST_LOGIN_TENANT_SLUG_KEY, slug.trim().toLowerCase())
  } catch {
    /* ignore */
  }
}

export function clearLastLoginTenantSlug(): void {
  try {
    localStorage.removeItem(LAST_LOGIN_TENANT_SLUG_KEY)
  } catch {
    /* ignore */
  }
}

/** Called immediately after login so HQ nav is correct before /auth/session. */
export function seedLoginTenantHint(tenantSlug: string): void {
  const slug = tenantSlug.trim().toLowerCase()
  if (!slug) return
  writeLastLoginTenantSlug(slug)
  if (!isMinitHqTenantSlug(slug)) return
  const planCode: PlanCode = 'minit_hq'
  writeSessionSnapshot({
    product: 'minit',
    planCode,
    tenantSlug: slug,
    enabledFeatures: mergeEnabledFeatures(planCode, []),
  })
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

export function clearMinitSessionHints(): void {
  clearSessionSnapshot()
  clearLastLoginTenantSlug()
}
