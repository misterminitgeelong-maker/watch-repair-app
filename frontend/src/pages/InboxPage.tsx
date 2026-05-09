import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle, XCircle, ArrowRight, Trash2, KeyRound, DollarSign, MessageSquare } from 'lucide-react'
import { getInbox, deleteInboxEvent } from '@/lib/api'
import { Card, PageHeader, Spinner, EmptyState } from '@/components/ui'

const PAGE_SIZE = 50

function formatDate(s: string) {
  const d = new Date(s)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  return d.toLocaleDateString()
}

function eventStyle(eventType: string): { iconBg: string; iconColor: string } {
  switch (eventType) {
    case 'quote_approved': return { iconBg: 'rgba(31,109,76,0.12)', iconColor: '#1F6D4C' }
    case 'quote_declined': return { iconBg: 'rgba(139,58,58,0.12)', iconColor: '#8B3A3A' }
    case 'invoice_paid': return { iconBg: 'rgba(31,76,109,0.12)', iconColor: '#1F4C6D' }
    case 'customer_sms_reply': return { iconBg: 'rgba(79,130,201,0.12)', iconColor: '#4F82C9' }
    default: return { iconBg: 'rgba(180,120,40,0.15)', iconColor: '#B47828' }
  }
}

function EventIcon({ eventType }: { eventType: string }) {
  if (eventType === 'quote_approved') return <CheckCircle size={20} />
  if (eventType === 'quote_declined') return <XCircle size={20} />
  if (eventType === 'invoice_paid') return <DollarSign size={20} />
  if (eventType === 'customer_sms_reply') return <MessageSquare size={20} />
  return <KeyRound size={20} />
}

/** Hook to get inbox count for nav badges — shares key with InboxPage page=0 to avoid duplicate fetch */
export function useInboxCount() {
  const { data } = useQuery({
    queryKey: ['inbox', 0],
    queryFn: () => getInbox(PAGE_SIZE, 0).then(r => r.data),
    staleTime: 60_000,
  })
  return data?.length ?? 0
}

export default function InboxPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const { data: alerts, isLoading } = useQuery({
    queryKey: ['inbox', page],
    queryFn: () => getInbox(PAGE_SIZE, page * PAGE_SIZE).then(r => r.data),
  })
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteInboxEvent(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['inbox'] })
    },
  })

  if (isLoading) return <Spinner />
  if (!alerts) return null

  return (
    <div>
      <PageHeader title="Inbox" />
      {alerts.length === 0 && page === 0 ? (
        <EmptyState message="No alerts yet. Quote approvals, declines, invoice payments, new website mobile key leads, and customer SMS replies will show up here." />
      ) : (
        <div className="space-y-3">
          {alerts.map(ev => {
            const { iconBg, iconColor } = eventStyle(ev.event_type)
            const jobLink =
              ev.entity_type === 'repair_job' && ev.entity_id
                ? `/jobs/${ev.entity_id}`
                : ev.entity_type === 'auto_key_job' && ev.entity_id
                  ? `/auto-key/${ev.entity_id}`
                  : ev.entity_type === 'invoice' && ev.event_type === 'invoice_paid'
                    ? '/invoices'
                    : null
            const linkLabel = ev.event_type === 'invoice_paid' ? 'View invoices' : 'View job'
            return (
              <Card key={ev.id} className="p-4">
                <div className="flex items-start gap-4">
                  <div
                    className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: iconBg, color: iconColor }}
                  >
                    <EventIcon eventType={ev.event_type} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                      {ev.event_summary}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                      {formatDate(ev.created_at)}
                    </p>
                  </div>
                  <div className="shrink-0 flex items-center gap-2">
                    {jobLink && (
                      <Link
                        to={jobLink}
                        className="flex items-center gap-1 text-sm font-medium transition-colors"
                        style={{ color: 'var(--ms-accent)' }}
                      >
                        {linkLabel} <ArrowRight size={14} />
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => deleteMut.mutate(ev.id)}
                      disabled={deleteMut.isPending}
                      className="p-1.5 rounded transition-colors hover:bg-black/10"
                      style={{ color: 'var(--ms-text-muted)' }}
                      title="Delete"
                      aria-label="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </Card>
            )
          })}

          {/* Pagination */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="text-sm px-4 py-2 rounded-lg"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: page === 0 ? 'var(--ms-text-muted)' : 'var(--ms-text)', opacity: page === 0 ? 0.4 : 1 }}
            >
              ← Newer
            </button>
            <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Page {page + 1}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={alerts.length < PAGE_SIZE}
              className="text-sm px-4 py-2 rounded-lg"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: alerts.length < PAGE_SIZE ? 'var(--ms-text-muted)' : 'var(--ms-text)', opacity: alerts.length < PAGE_SIZE ? 0.4 : 1 }}
            >
              Older →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
