import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Spinner } from '@/components/ui'
import type { FeatureKey } from '@/lib/api'
import { defaultHomePathForMinit, isMinitRestrictedUi } from '@/lib/minitProduct'

export function RouteFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner />
    </div>
  )
}

export function FeatureGate({ feature, children }: { feature: FeatureKey; children: React.ReactNode }) {
  const { hasFeature, role, product, planCode, tenantSlug, authStatus } = useAuth()
  const { pathname } = useLocation()
  if (role === 'platform_admin' || hasFeature(feature)) return <>{children}</>
  // Features come from the session payload — don't bounce deep links (e.g.
  // scanned ticket QRs straight after login) to the dashboard before it loads.
  if (authStatus === 'authenticating') return <RouteFallback />
  const fallback = isMinitRestrictedUi(product, planCode, tenantSlug)
    ? defaultHomePathForMinit(planCode, tenantSlug)
    : '/dashboard'
  if (pathname === fallback || pathname.startsWith(`${fallback}/`)) {
    return (
      <div className="p-6 text-sm" style={{ color: '#C96A5A' }}>
        This page is not available on your plan. Open Account or sign in again if the problem persists.
      </div>
    )
  }
  return <Navigate to={fallback} replace />
}
