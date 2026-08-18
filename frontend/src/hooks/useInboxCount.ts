import { useQuery } from '@tanstack/react-query'
import { getInboxCount, listInboundEmails } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { isMinitHqUi } from '@/lib/minitProduct'

/**
 * Inbox count for nav badges. Lives in its own module (not InboxPage) so the
 * nav bars — which render eagerly on every screen — don't statically import
 * the heavy InboxPage and defeat its lazy route split.
 *
 * Uses GET /inbox/count (DB COUNT) instead of fetching 50 inbox rows.
 */
export function useInboxCount() {
  const { minitHqUi, product, planCode, tenantSlug } = useAuth()
  const hqNav = minitHqUi === true || isMinitHqUi(product, planCode, tenantSlug)

  const { data: inboxCount = 0 } = useQuery({
    queryKey: ['inbox-count', hqNav ? 'hq' : 'shop'],
    queryFn: () =>
      getInboxCount(hqNav ? ['inbound_email_received'] : undefined).then(r => r.data.count),
    staleTime: 60_000,
  })

  const { data: emailLeads } = useQuery({
    queryKey: ['inbound-emails'],
    queryFn: () => listInboundEmails().then(r => r.data),
    staleTime: 60_000,
    enabled: hqNav,
  })

  if (!hqNav) {
    return inboxCount
  }

  const newEmails = (emailLeads ?? []).filter(e => e.status === 'new').length
  return newEmails + inboxCount
}
