import { persistTheme } from '@/context/ThemeContext'
import type { PlanCode } from '@/lib/api'

/** True for Mister Minit corporate and seeded network tenants (mmsupport, minit-3269, …). */
export function isMinitTenantSlug(slug: string | null | undefined): boolean {
  if (!slug) return false
  const s = slug.trim().toLowerCase()
  return s === 'mmsupport' || s.startsWith('minit-')
}

export function shouldUseMinitBranding(slug: string | null | undefined): boolean {
  return isMinitTenantSlug(slug)
}

export function applyMinitBrandingIfNeeded(slug: string | null | undefined, _planCode?: PlanCode): void {
  if (shouldUseMinitBranding(slug)) persistTheme('minit')
}
