import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle, XCircle, ArrowRight } from 'lucide-react'
import { getInbox } from '@/lib/api'
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
  const { data: alerts, isLoading } = useQuery({
    queryKey: ['inbox'],
    queryFn: () => getInbox(50).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!alerts) return null

  return (
    <div>
      <PageHeader title="Inbox" />
      {alerts.length === 0 ? (
        <EmptyState message="No alerts yet. When customers approve or decline quotes, they'll show up here." />
      ) : (
        <div className="space-y-3">
          {alerts.map(ev => {
            const isApproved = ev.event_type === 'quote_approved'
            const jobLink = ev.entity_type === 'repair_job' && ev.entity_id
              ? `/jobs/${ev.entity_id}`
              : null
            return (
              <Card key={ev.id} className="p-4">
                <div className="flex items-start gap-4">
                  <div
                    className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                    style={{
                      backgroundColor: isApproved ? 'rgba(31,109,76,0.12)' : 'rgba(139,58,58,0.12)',
                      color: isApproved ? '#1F6D4C' : '#8B3A3A',
                    }}
                  >
                    {isApproved ? <CheckCircle size={20} /> : <XCircle size={20} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                      {ev.event_summary}
                    </p>
                    <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
                      {formatDate(ev.created_at)}
                    </p>
                  </div>
                  {jobLink && (
                    <Link
                      to={jobLink}
                      className="shrink-0 flex items-center gap-1 text-sm font-medium transition-colors"
                      style={{ color: 'var(--cafe-amber)' }}
                    >
                      View job <ArrowRight size={14} />
                    </Link>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
