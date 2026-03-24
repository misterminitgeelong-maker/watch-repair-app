import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle, XCircle, ArrowRight, Trash2, KeyRound } from 'lucide-react'
import { getInbox, deleteInboxEvent } from '@/lib/api'
import { Card, PageHeader, Spinner, EmptyState } from '@/components/ui'

function formatDate(s: string) {
  const d = new Date(s)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  return d.toLocaleDateString()
}

export default function InboxPage() {
  const qc = useQueryClient()
  const { data: alerts, isLoading } = useQuery({
    queryKey: ['inbox'],
    queryFn: () => getInbox(50).then(r => r.data),
  })
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteInboxEvent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inbox'] }),
  })

  if (isLoading) return <Spinner />
  if (!alerts) return null

  return (
    <div>
      <PageHeader title="Inbox" />
      {alerts.length === 0 ? (
        <EmptyState message="No alerts yet. Quote approvals and declines, and new website mobile key leads, will show up here." />
      ) : (
        <div className="space-y-3">
          {alerts.map(ev => {
            const isWebsiteLead = ev.event_type === 'mobile_lead_quote_needed'
            const isApproved = ev.event_type === 'quote_approved'
            const jobLink =
              ev.entity_type === 'repair_job' && ev.entity_id
                ? `/jobs/${ev.entity_id}`
                : ev.entity_type === 'auto_key_job' && ev.entity_id
                  ? `/auto-key/${ev.entity_id}`
                  : null
            const iconBg = isWebsiteLead
              ? 'rgba(180,120,40,0.15)'
              : isApproved
                ? 'rgba(31,109,76,0.12)'
                : 'rgba(139,58,58,0.12)'
            const iconColor = isWebsiteLead ? '#B47828' : isApproved ? '#1F6D4C' : '#8B3A3A'
            return (
              <Card key={ev.id} className="p-4">
                <div className="flex items-start gap-4">
                  <div
                    className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                    style={{
                      backgroundColor: iconBg,
                      color: iconColor,
                    }}
                  >
                    {isWebsiteLead ? <KeyRound size={20} /> : isApproved ? <CheckCircle size={20} /> : <XCircle size={20} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                      {ev.event_summary}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
                      {formatDate(ev.created_at)}
                    </p>
                  </div>
                  <div className="shrink-0 flex items-center gap-2">
                    {jobLink && (
                      <Link
                        to={jobLink}
                        className="flex items-center gap-1 text-sm font-medium transition-colors"
                        style={{ color: 'var(--cafe-amber)' }}
                      >
                        View job <ArrowRight size={14} />
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => deleteMut.mutate(ev.id)}
                      disabled={deleteMut.isPending}
                      className="p-1.5 rounded transition-colors hover:bg-black/10"
                      style={{ color: 'var(--cafe-text-muted)' }}
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
        </div>
      )}
    </div>
  )
}
