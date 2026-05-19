import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { KeyRound, MessageSquare } from 'lucide-react'
import { API_ORIGIN, getInbox, getMyParentAccount } from '@/lib/api'
import { Card, EmptyState, PageHeader, Spinner } from '@/components/ui'

function formatDate(s: string) {
  const d = new Date(s)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  return d.toLocaleDateString()
}

export default function MinitInboxPage() {
  const { data: alerts, isLoading: inboxLoading } = useQuery({
    queryKey: ['inbox', 0],
    queryFn: () => getInbox(50, 0).then(r => r.data),
  })

  const { data: parent, isLoading: parentLoading } = useQuery({
    queryKey: ['parent-account-me'],
    queryFn: () => getMyParentAccount().then(r => r.data),
  })

  if (inboxLoading || parentLoading) return <Spinner />

  const items = alerts ?? []
  const ingestPublicId = parent?.mobile_lead_ingest_public_id ?? null
  const ingestUrl = ingestPublicId
    ? `${API_ORIGIN || window.location.origin}/v1/public/mobile-key-leads/${ingestPublicId}`
    : null
  const ingestReady = Boolean(ingestPublicId && parent?.mobile_lead_webhook_secret_configured)

  return (
    <div>
      <PageHeader title="Inbox" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Customer enquiries from the Mister Minit website and network alerts.
      </p>

      {!ingestReady && (
        <Card className="mb-6 p-5">
          <div className="flex items-start gap-3">
            <MessageSquare size={20} style={{ color: 'var(--ms-accent)', flexShrink: 0, marginTop: 2 }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
                Website lead ingest {ingestPublicId ? 'needs webhook secret' : 'not enabled yet'}
              </p>
              <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                When configured, customer job requests from minit.com.au are routed to the right shop or mobile
                operator. Enquiries appear in the routed site&apos;s inbox; network-level activity will show here
                as HQ inbox grows.
              </p>
              {ingestUrl && (
                <p className="text-xs mt-2 font-mono break-all" style={{ color: 'var(--ms-text-muted)' }}>
                  {ingestUrl}
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      {items.length === 0 ? (
        <EmptyState message="No enquiries yet. Website mobile key leads, quote activity, and customer replies will appear here once lead ingest is active and customers submit requests." />
      ) : (
        <div className="space-y-3">
          {items.map(ev => (
            <Card key={ev.id} className="p-4">
              <div className="flex items-start gap-4">
                <div
                  className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: 'rgba(180,120,40,0.15)', color: '#B47828' }}
                >
                  <KeyRound size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                    {ev.event_summary}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                    {formatDate(ev.created_at)}
                  </p>
                </div>
                {ev.entity_type === 'auto_key_job' && ev.entity_id && (
                  <Link
                    to={`/minit/mobile-services`}
                    className="text-sm font-medium shrink-0"
                    style={{ color: 'var(--ms-accent)' }}
                  >
                    View network
                  </Link>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
