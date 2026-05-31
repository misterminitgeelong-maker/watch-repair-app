import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Clock } from 'lucide-react'
import {
  getPublicAutoKeyJobStatus,
  getPublicJobStatus,
  getPublicShoeJobStatus,
} from '@/lib/api'
import { CustomerPortalJobCard } from '@/components/CustomerPortalJobCard'
import { portalJobStatusLabel } from '@/lib/portalStatus'
import { formatDate } from '@/lib/utils'

function DetailShell({
  title,
  subtitle,
  backTo,
  children,
}: {
  title: string
  subtitle?: string
  backTo: string
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen py-8 px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-4">
        <Link
          to={backTo}
          className="inline-flex items-center gap-1.5 text-sm font-medium"
          style={{ color: 'var(--ms-accent)', textDecoration: 'none' }}
        >
          <ArrowLeft size={14} /> Back to my repairs
        </Link>
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--ms-text)' }}>{title}</h1>
          {subtitle && <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>{subtitle}</p>}
        </div>
        {children}
      </div>
    </div>
  )
}

function HistoryTimeline({
  history,
  jobType,
}: {
  jobType: 'watch' | 'shoe'
  history: Array<{ old_status?: string | null; new_status: string; change_note?: string | null; created_at: string }>
}) {
  if (!history.length) return null
  return (
    <div className="rounded-xl p-4 space-y-3" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
      <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Timeline</p>
      {history.map((entry, idx) => (
        <div key={idx} className="flex gap-3 text-sm">
          <span className="shrink-0 text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)', minWidth: 72 }}>
            {formatDate(entry.created_at)}
          </span>
          <div>
            <p style={{ color: 'var(--ms-text)' }}>{portalJobStatusLabel(jobType, entry.new_status)}</p>
            {entry.change_note && (
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{entry.change_note}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function WatchJobDetail({ token, backTo }: { token: string; backTo: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portal-watch-detail', token],
    queryFn: () => getPublicJobStatus(token).then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <Clock className="animate-spin" style={{ color: 'var(--ms-text-muted)' }} />
      </div>
    )
  }
  if (isError || !data) {
    return (
      <DetailShell title="Job not found" backTo={backTo}>
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>This link may have expired.</p>
      </DetailShell>
    )
  }

  const watchTitle = [data.watch?.brand, data.watch?.model].filter(Boolean).join(' ') || 'Watch repair'
  return (
    <DetailShell title={data.title} subtitle={`#${data.job_number} · ${watchTitle}`} backTo={backTo}>
      <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
        <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Status</p>
        <p className="text-lg font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>
          {portalJobStatusLabel('watch', data.status)}
        </p>
        {data.description && <p className="text-sm mt-3" style={{ color: 'var(--ms-text-mid)' }}>{data.description}</p>}
      </div>
      <HistoryTimeline jobType="watch" history={data.history} />
    </DetailShell>
  )
}

function ShoeJobDetail({ token, backTo }: { token: string; backTo: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portal-shoe-detail', token],
    queryFn: () => getPublicShoeJobStatus(token).then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <Clock className="animate-spin" style={{ color: 'var(--ms-text-muted)' }} />
      </div>
    )
  }
  if (isError || !data) {
    return (
      <DetailShell title="Job not found" backTo={backTo}>
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>This link may have expired.</p>
      </DetailShell>
    )
  }

  const shoeTitle = [data.shoe?.brand, data.shoe?.shoe_type].filter(Boolean).join(' · ') || 'Shoe repair'
  return (
    <DetailShell title={data.title} subtitle={`#${data.job_number} · ${shoeTitle}`} backTo={backTo}>
      <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
        <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Status</p>
        <p className="text-lg font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>
          {portalJobStatusLabel('shoe', data.status)}
        </p>
        {data.description && <p className="text-sm mt-3" style={{ color: 'var(--ms-text-mid)' }}>{data.description}</p>}
      </div>
      {data.items?.length > 0 && (
        <div className="rounded-xl p-4 space-y-2" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Work items</p>
          {data.items.map((item, idx) => (
            <p key={idx} className="text-sm" style={{ color: 'var(--ms-text)' }}>
              {item.item_name} × {item.quantity}
            </p>
          ))}
        </div>
      )}
      <HistoryTimeline jobType="shoe" history={data.history} />
    </DetailShell>
  )
}

function AutoKeyJobDetail({ token, backTo }: { token: string; backTo: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portal-auto-key-detail', token],
    queryFn: () => getPublicAutoKeyJobStatus(token).then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <Clock className="animate-spin" style={{ color: 'var(--ms-text-muted)' }} />
      </div>
    )
  }
  if (isError || !data) {
    return (
      <DetailShell title="Job not found" backTo={backTo}>
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>This link may have expired.</p>
      </DetailShell>
    )
  }

  const vehicle = [data.vehicle_make, data.vehicle_year, data.vehicle_model].filter(Boolean).join(' ')
  const shopStub = {
    tenant_id: '',
    shop_name: data.shop_name,
    logo_url: null,
    brand_color: null,
    shop_phone: data.shop_phone ?? null,
    shop_email: data.shop_email ?? null,
    jobs: [],
  }
  const jobCard = {
    type: 'auto_key' as const,
    job_number: data.job_number,
    title: data.title,
    status: data.status,
    created_at: data.created_at,
    status_token: token,
    status_url: `/customer-portal/job/auto_key/${token}`,
    detail: vehicle || null,
    pending_actions: data.pending_actions,
  }

  return (
    <DetailShell title={data.title} subtitle={`#${data.job_number} · ${data.shop_name}`} backTo={backTo}>
      <CustomerPortalJobCard job={jobCard} shop={shopStub} />
      <div className="rounded-xl p-4 space-y-2" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
        <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Status</p>
        <p className="text-lg font-semibold" style={{ color: 'var(--ms-text)' }}>
          {portalJobStatusLabel('auto_key', data.status)}
        </p>
        {data.job_address && (
          <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>Location: {data.job_address}</p>
        )}
        {data.description && (
          <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>{data.description}</p>
        )}
      </div>
    </DetailShell>
  )
}

export default function CustomerPortalJobDetailPage() {
  const { jobType, statusToken } = useParams<{ jobType: string; statusToken: string }>()
  const backTo = '/customer-portal'

  if (!statusToken || !jobType) {
    return (
      <DetailShell title="Invalid link" backTo={backTo}>
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Missing job reference.</p>
      </DetailShell>
    )
  }

  if (jobType === 'watch') return <WatchJobDetail token={statusToken} backTo={backTo} />
  if (jobType === 'shoe') return <ShoeJobDetail token={statusToken} backTo={backTo} />
  if (jobType === 'auto_key') return <AutoKeyJobDetail token={statusToken} backTo={backTo} />

  return (
    <DetailShell title="Unknown job type" backTo={backTo}>
      <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>This job type is not supported.</p>
    </DetailShell>
  )
}
