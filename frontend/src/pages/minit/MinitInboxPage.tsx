import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { KeyRound, Mail, MessageSquare } from 'lucide-react'
import {
  API_ORIGIN,
  getInbox,
  getInboundEmail,
  listInboundEmails,
  updateInboundEmailStatus,
} from '@/lib/api'
import { useParentLeadIngest } from '@/hooks/useParentLeadIngest'
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

const STATUS_COLORS: Record<string, string> = {
  new: '#B47828',
  processed: '#2F855A',
  dismissed: '#718096',
}

function InboundEmailCard({ id, subject, fromEmail, status, createdAt }: {
  id: string
  subject?: string | null
  fromEmail?: string | null
  status: 'new' | 'processed' | 'dismissed'
  createdAt: string
}) {
  const [expanded, setExpanded] = useState(false)
  const queryClient = useQueryClient()

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['inbound-email', id],
    queryFn: () => getInboundEmail(id).then(r => r.data),
    enabled: expanded,
  })

  const statusMutation = useMutation({
    mutationFn: (next: 'processed' | 'dismissed') => updateInboundEmailStatus(id, next),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbound-emails'] })
      queryClient.invalidateQueries({ queryKey: ['inbound-email', id] })
    },
  })

  return (
    <Card className="p-4">
      <div className="flex items-start gap-4">
        <div
          className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: 'rgba(180,120,40,0.15)', color: '#B47828' }}
        >
          <Mail size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <button
            type="button"
            className="text-left w-full"
            onClick={() => setExpanded(v => !v)}
          >
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
              {subject?.trim() || '(no subject)'}
            </p>
            <p className="text-xs mt-1 truncate" style={{ color: 'var(--ms-text-muted)' }}>
              {fromEmail || 'Unknown sender'} · {formatDate(createdAt)}
            </p>
          </button>
          {expanded && (
            <div className="mt-3">
              {detailLoading ? (
                <Spinner />
              ) : detail?.text_body ? (
                <pre
                  className="text-xs whitespace-pre-wrap rounded p-3 max-h-80 overflow-y-auto"
                  style={{ backgroundColor: 'var(--ms-bg, rgba(0,0,0,0.04))', color: 'var(--ms-text)' }}
                >
                  {detail.text_body}
                </pre>
              ) : (
                <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                  No plain-text body captured{detail?.html_body ? ' (HTML only — open the job email in your mail client if needed)' : ''}.
                </p>
              )}
              {status === 'new' && (
                <div className="flex gap-3 mt-3">
                  <button
                    type="button"
                    className="text-sm font-medium"
                    style={{ color: 'var(--ms-accent)' }}
                    disabled={statusMutation.isPending}
                    onClick={() => statusMutation.mutate('processed')}
                  >
                    Mark processed
                  </button>
                  <button
                    type="button"
                    className="text-sm font-medium"
                    style={{ color: 'var(--ms-text-muted)' }}
                    disabled={statusMutation.isPending}
                    onClick={() => statusMutation.mutate('dismissed')}
                  >
                    Dismiss
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        <span
          className="text-xs font-medium shrink-0 capitalize"
          style={{ color: STATUS_COLORS[status] ?? 'var(--ms-text-muted)' }}
        >
          {status}
        </span>
      </div>
    </Card>
  )
}

export default function MinitInboxPage() {
  const { data: alerts, isLoading: inboxLoading } = useQuery({
    queryKey: ['inbox', 0],
    queryFn: () => getInbox(50, 0).then(r => r.data),
  })

  const { data: emailLeads, isLoading: emailsLoading } = useQuery({
    queryKey: ['inbound-emails'],
    queryFn: () => listInboundEmails().then(r => r.data),
  })

  const { data: leadIngest, isLoading: ingestLoading } = useParentLeadIngest()

  if (inboxLoading || emailsLoading) return <Spinner />

  // Email leads get their own triage cards; hide their duplicate generic alerts.
  const items = (alerts ?? []).filter(ev => ev.event_type !== 'inbound_email_received')
  const emails = emailLeads ?? []
  const ingestPublicId = leadIngest?.mobile_lead_ingest_public_id ?? null
  const ingestUrl = ingestPublicId
    ? `${API_ORIGIN || window.location.origin}/v1/public/mobile-key-leads/${ingestPublicId}`
    : null
  const emailParseUrl = ingestPublicId
    ? `${API_ORIGIN || window.location.origin}/v1/public/inbound-email/${ingestPublicId}?key=<webhook secret>`
    : null
  const ingestReady = Boolean(ingestPublicId && leadIngest?.mobile_lead_webhook_secret_configured)

  return (
    <div>
      <PageHeader title="Inbox" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Customer enquiries from the Mister Minit website and network alerts.
      </p>

      {!ingestReady && !ingestLoading && (
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
              <Link
                to="/parent-account"
                className="text-sm font-medium inline-block mt-2"
                style={{ color: 'var(--ms-accent)' }}
              >
                Set up website lead feed →
              </Link>
            </div>
          </div>
        </Card>
      )}

      {(emails.length > 0 || ingestReady) && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>
            Email leads
          </h2>
          {emails.length === 0 ? (
            <Card className="p-4">
              <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
                No emails captured yet. BCC&apos;d enquiry-form emails will appear here once the inbound
                address is live.
              </p>
              {emailParseUrl && (
                <p className="text-xs mt-2 font-mono break-all" style={{ color: 'var(--ms-text-muted)' }}>
                  Inbound Parse webhook: {emailParseUrl}
                </p>
              )}
              <Link
                to="/parent-account"
                className="text-sm font-medium inline-block mt-2"
                style={{ color: 'var(--ms-accent)' }}
              >
                Website lead feed settings →
              </Link>
            </Card>
          ) : (
            <div className="space-y-3">
              {emails.map(em => (
                <InboundEmailCard
                  key={em.id}
                  id={em.id}
                  subject={em.subject}
                  fromEmail={em.from_email}
                  status={em.status}
                  createdAt={em.created_at}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {items.length === 0 && emails.length === 0 ? (
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
