import { useQuery } from '@tanstack/react-query'
import { getInbox } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { isMinitHqUi } from '@/lib/minitProduct'

const PAGE_SIZE = 50

/**
 * Inbox count for nav badges. Lives in its own module (not InboxPage) so the
 * nav bars — which render eagerly on every screen — don't statically import
 * the heavy InboxPage and defeat its lazy route split. Shares the page=0
 * query key with InboxPage to avoid a duplicate fetch.
 */
export function useInboxCount() {
  const { minitHqUi, product, planCode, tenantSlug, role } = useAuth()
  const hqNav =
    role === 'platform_admin'
    || minitHqUi === true
    || isMinitHqUi(product, planCode, tenantSlug)
  const { data } = useQuery({
    queryKey: ['inbox', 0],
    queryFn: () => getInbox(PAGE_SIZE, 0).then(r => r.data),
    staleTime: 60_000,
    enabled: !hqNav,
  })
  return data?.length ?? 0
}
