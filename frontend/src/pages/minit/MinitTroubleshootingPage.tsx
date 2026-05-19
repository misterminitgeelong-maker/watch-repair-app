import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getParentTroubleshooting } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, PageHeader, Spinner } from '@/components/ui'

function severityColor(severity: string) {
  if (severity === 'warning') return '#C96A5A'
  return 'var(--ms-text-muted)'
}

export default function MinitTroubleshootingPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['minit-troubleshooting'],
    queryFn: () => getParentTroubleshooting(80).then(r => r.data),
  })

  if (isLoading) return <Spinner />

  const items = data?.items ?? []

  return (
    <div>
      <PageHeader title="Troubleshooting" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Actionable issues: failed bookings, stale pending requests, missing operator SMS numbers, and quiet shops.
      </p>

      {items.length === 0 ? (
        <Card className="p-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          No issues detected right now.
        </Card>
      ) : (
        <Card className="overflow-hidden">
          {items.map((item, i) => (
            <div
              key={`${item.kind}-${item.related_id ?? item.tenant_id ?? i}`}
              className="px-5 py-4"
              style={{ borderBottom: '1px solid var(--ms-border)' }}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-sm" style={{ color: severityColor(item.severity) }}>
                    {item.title}
                  </p>
                  <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                    {item.detail}
                  </p>
                  {item.created_at && (
                    <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                      {formatDate(item.created_at)}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 text-xs">
                  {item.tenant_slug && (
                    <Link
                      to="/minit/shops"
                      className="font-medium underline"
                      style={{ color: 'var(--ms-accent)' }}
                    >
                      Shops
                    </Link>
                  )}
                  {item.kind.startsWith('booking_') && (
                    <Link
                      to="/minit/reports/shops"
                      className="font-medium underline"
                      style={{ color: 'var(--ms-accent)' }}
                    >
                      Bookings
                    </Link>
                  )}
                  {item.kind.startsWith('job_') && (
                    <Link
                      to="/minit/reports/mobile"
                      className="font-medium underline"
                      style={{ color: 'var(--ms-accent)' }}
                    >
                      Mobile jobs
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
