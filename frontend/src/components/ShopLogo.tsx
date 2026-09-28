import type { ReactNode } from 'react'
import { MINIT_LOGO_SRC } from '@/components/portal/portalUtils'

/**
 * The logo at the top of a customer-facing page: Mister Minit's for a Minit
 * shop, the shop's own if it has one, otherwise `fallback` (the page's icon).
 */
export function ShopLogo({
  minit,
  logoUrl,
  name,
  fallback,
  className = 'mb-4',
}: {
  minit?: boolean | null
  logoUrl?: string | null
  name?: string | null
  fallback: ReactNode
  className?: string
}) {
  if (minit) {
    return (
      <img
        src={MINIT_LOGO_SRC}
        alt="Mister Minit"
        className={`h-14 w-auto mx-auto object-contain rounded-lg ${className}`}
      />
    )
  }
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={name ?? ''}
        className={`h-12 w-auto max-w-[200px] mx-auto object-contain ${className}`}
      />
    )
  }
  return <>{fallback}</>
}
