import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listParentAccountActivity } from '@/lib/api'
import WebsiteLeadRoutingPanel from '@/components/minit/WebsiteLeadRoutingPanel'
import { Card, EmptyState, PageHeader } from '@/components/ui'

export default function MinitLeadRoutingPage() {
  const [error, setError] = useState('')

  const { data: activity = [] } = useQuery({
    queryKey: ['parent-account-activity'],
    queryFn: () => listParentAccountActivity(20).then(r => r.data),
  })

  return (
    <div>
      <PageHeader title="Lead routing" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Website ingest, operator dispatch, and territory mapping for minit.com.au mobile key leads.
      </p>

      {error && (
        <div
          className="mb-4 text-sm rounded-lg px-4 py-3"
          style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}
        >
          {error}
        </div>
      )}

      <WebsiteLeadRoutingPanel hqMode onError={setError} />

      <Card className="mt-6">
        <div className="px-5 py-3.5" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>Recent routing activity</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
            Ingest setup, territory imports, and dispatch changes.
          </p>
        </div>
        {activity.length === 0 ? (
          <EmptyState message="No activity recorded yet." />
        ) : (
          <div>
            {activity.map(event => (
              <div
                key={event.id}
                className="px-5 py-3 text-sm flex items-start justify-between gap-3"
                style={{ borderBottom: '1px solid var(--ms-border)' }}
              >
                <div>
                  <p className="font-semibold" style={{ color: 'var(--ms-text)' }}>{event.event_summary}</p>
                  <p className="text-xs capitalize" style={{ color: 'var(--ms-text-muted)' }}>
                    {event.event_type.replace(/_/g, ' ')}{event.actor_email ? ` · ${event.actor_email}` : ''}
                  </p>
                </div>
                <p className="text-xs whitespace-nowrap" style={{ color: 'var(--ms-text-muted)' }}>
                  {new Date(event.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
