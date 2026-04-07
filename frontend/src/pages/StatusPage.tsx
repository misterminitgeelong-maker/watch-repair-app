import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Clock, RefreshCw, Wrench } from 'lucide-react'
import { getPublicJobStatus, type PublicJobStatus } from '@/lib/api'
import { STATUS_LABELS, formatDate } from '@/lib/utils'

function readableStatus(status: string) {
  const known = STATUS_LABELS as Record<string, string>
  return known[status] ?? status.replace(/_/g, ' ')
}

function formatCents(value: number) {
  return (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export default function StatusPage() {
  const { token } = useParams<{ token: string }>()

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['public-job-status', token],
    queryFn: () => getPublicJobStatus(token!).then((r) => r.data),
    enabled: !!token,
    retry: false,
    refetchInterval: 15000,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="text-center" style={{ color: 'var(--cafe-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading repair status…</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Status link not found
          </h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>
            This status link may have expired. Please contact the shop for an updated link.
          </p>
        </div>
      </div>
    )
  }

  const job = data as PublicJobStatus
  const watchTitle = [job.watch?.brand, job.watch?.model].filter(Boolean).join(' ') || 'Watch repair'

  return (
    <div className="min-h-screen py-8 px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="text-center mb-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <Wrench size={22} style={{ color: 'var(--cafe-gold-dark)' }} />
          </div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Live Repair Status
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
            Job #{job.job_number} • {watchTitle}
          </p>
        </div>

        <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Current stage</p>
              <p className="text-lg font-semibold capitalize" style={{ color: 'var(--cafe-text)' }}>{readableStatus(job.status)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Pre-quote</p>
              <p className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{formatCents(job.pre_quote_cents || 0)}</p>
            </div>
          </div>
          {job.description && (
            <p className="text-sm mt-3" style={{ color: 'var(--cafe-text-mid)' }}>{job.description}</p>
          )}
          {job.collection_date && (
            <div className="flex items-center gap-2 text-sm mt-3 pt-3" style={{ borderTop: '1px solid var(--cafe-border)', color: 'var(--cafe-text-mid)' }}>
              <span style={{ color: 'var(--cafe-text-muted)' }}>Expected ready:</span>
              <span className="font-medium" style={{ color: 'var(--cafe-text)' }}>{job.collection_date}</span>
            </div>
          )}
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs font-medium"
              style={{ color: 'var(--cafe-amber)' }}
              onClick={() => refetch()}
            >
              <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} />
              Refresh now
            </button>
          </div>
        </div>

        <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
          <h2 className="text-sm font-semibold uppercase tracking-widest mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
            Timeline
          </h2>
          <div className="space-y-3">
            {job.history.map((entry, idx) => (
              <div key={`${entry.created_at}-${idx}`} className="flex items-start justify-between gap-4 text-sm">
                <div>
                  <p className="font-medium capitalize" style={{ color: 'var(--cafe-text)' }}>{readableStatus(entry.new_status)}</p>
                  {entry.change_note && <p style={{ color: 'var(--cafe-text-mid)' }}>{entry.change_note}</p>}
                </div>
                <span className="text-xs whitespace-nowrap" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(entry.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
