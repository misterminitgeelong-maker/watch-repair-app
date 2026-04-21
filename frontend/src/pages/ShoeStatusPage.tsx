import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Clock, RefreshCw, Footprints } from 'lucide-react'
import { getPublicShoeJobStatus, type PublicShoeJobStatus } from '@/lib/api'
import { formatDate } from '@/lib/utils'

function readableStatus(status: string) {
  return status.replace(/_/g, ' ')
}

function formatCents(value: number) {
  return (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export default function ShoeStatusPage() {
  const { token } = useParams<{ token: string }>()

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['public-shoe-job-status', token],
    queryFn: () => getPublicShoeJobStatus(token!).then((r) => r.data),
    enabled: !!token,
    retry: false,
    refetchInterval: 15000,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="text-center" style={{ color: 'var(--ms-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading repair status…</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>
            Status link not found
          </h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>
            This status link may have expired. Please contact the shop for an updated link.
          </p>
        </div>
      </div>
    )
  }

  const job = data as PublicShoeJobStatus
  const shoeTitle = [job.shoe?.brand, job.shoe?.shoe_type, job.shoe?.color].filter(Boolean).join(' · ') || 'Shoe repair'
  const balance = Math.max(job.estimated_total_cents - job.deposit_cents, 0)

  return (
    <div className="min-h-screen py-8 px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="text-center mb-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <Footprints size={22} style={{ color: 'var(--ms-accent-hover)' }} />
          </div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--ms-text)' }}>
            Live Repair Status
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            Job #{job.job_number} • {shoeTitle}
          </p>
        </div>

        <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Current stage</p>
              <p className="text-lg font-semibold capitalize" style={{ color: 'var(--ms-text)' }}>{readableStatus(job.status)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Estimated balance</p>
              <p className="font-semibold" style={{ color: 'var(--ms-text)' }}>{formatCents(balance)}</p>
            </div>
          </div>
          {job.description && (
            <p className="text-sm mt-3" style={{ color: 'var(--ms-text-mid)' }}>{job.description}</p>
          )}
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs font-medium"
              style={{ color: 'var(--ms-accent)' }}
              onClick={() => refetch()}
            >
              <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} />
              Refresh now
            </button>
          </div>
        </div>

        <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
          <h2 className="text-sm font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--ms-text-muted)' }}>
            Services
          </h2>
          {job.items.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>No services listed yet.</p>
          ) : (
            <div className="space-y-2">
              {job.items.map((item, idx) => (
                <div key={`${item.item_name}-${idx}`} className="flex items-start justify-between gap-3 text-sm">
                  <div>
                    <p className="font-medium" style={{ color: 'var(--ms-text)' }}>{item.item_name}</p>
                    {item.notes && <p style={{ color: 'var(--ms-text-mid)' }}>{item.notes}</p>}
                  </div>
                  <span style={{ color: 'var(--ms-text-muted)' }}>
                    {item.unit_price_cents == null ? 'Quoted' : formatCents(item.unit_price_cents * item.quantity)}
                  </span>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs mt-3" style={{ color: 'var(--ms-text-muted)' }}>
            Last updated {formatDate(job.created_at)}
          </p>
        </div>

        {job.history && job.history.length > 0 && (
          <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            <h2 className="text-sm font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--ms-text-muted)' }}>
              Timeline
            </h2>
            <div className="space-y-3">
              {job.history.map((entry, idx) => (
                <div key={`${entry.created_at}-${idx}`} className="flex items-start justify-between gap-4 text-sm">
                  <div>
                    <p className="font-medium capitalize" style={{ color: 'var(--ms-text)' }}>{readableStatus(entry.new_status)}</p>
                    {entry.change_note && <p style={{ color: 'var(--ms-text-mid)' }}>{entry.change_note}</p>}
                  </div>
                  <span className="text-xs whitespace-nowrap" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(entry.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
