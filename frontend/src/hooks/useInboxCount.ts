import { useQuery } from '@tanstack/react-query'
import { getInbox, listInboundEmails } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { isMinitHqUi } from '@/lib/minitProduct'

const PAGE_SIZE = 50

/**
 * Inbox count for nav badges. Lives in its own module (not InboxPage) so the
 * nav bars — which render eagerly on every screen — don't statically import
 * the heavy InboxPage and defeat its lazy route split.
 */
export function useInboxCount() {
  const { minitHqUi, product, planCode, tenantSlug, role } = useAuth()
  const hqNav =
    role === 'platform_admin'
    || minitHqUi === true
    || isMinitHqUi(product, planCode, tenantSlug)

  const { data: inboxItems } = useQuery({
    queryKey: ['inbox', 0],
    queryFn: () => getInbox(PAGE_SIZE, 0).then(r => r.data),
    staleTime: 60_000,
  })

  const { data: emailLeads } = useQuery({
    queryKey: ['inbound-emails'],
    queryFn: () => listInboundEmails().then(r => r.data),
    staleTime: 60_000,
    enabled: hqNav,
  })

  if (!hqNav) {
    return inboxItems?.length ?? 0
  }

  const newEmails = (emailLeads ?? []).filter(e => e.status === 'new').length
  const alerts = (inboxItems ?? []).filter(ev => ev.event_type !== 'inbound_email_received').length
  return newEmails + alerts
}
