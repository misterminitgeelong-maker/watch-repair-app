import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CalendarClock, Mail, MapPin, MessageSquareQuote, Phone } from 'lucide-react'
import {
  getPublicAutoKeyJobStatus,
  getPublicJobStatus,
  getPublicShoeJobStatus,
} from '@/lib/api'
import { CustomerPortalJobCard, StatusPill } from '@/components/CustomerPortalJobCard'
import {
  PortalBody,
  PortalHero,
  PortalLoading,
  PortalPage,
  StageRing,
  StageStepper,
} from '@/components/portal/PortalChrome'
import { jobIcon, jobTypeLabel, STAGE_COPY } from '@/components/portal/portalUtils'
import { portalJobStage, portalJobStatusLabel } from '@/lib/portalStatus'
import { formatDate } from '@/lib/utils'
import { clsx } from 'clsx'

type JobType = 'watch' | 'shoe' | 'auto_key'

function BackLink({ to }: { to: string }) {
  return (
    <Link to={to} className="pt-link pt-link--on-ink">
      <ArrowLeft size={14} /> My repairs
    </Link>
  )
}

function DetailShell({
  eyebrow,
  title,
  subtitle,
  backTo,
  shopName,
  children,
}: {
  eyebrow?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  backTo: string
  shopName?: string | null
  children?: ReactNode
}) {
  return (
    <PortalPage>
      <PortalHero
        brand={{ name: shopName }}
        barRight={<BackLink to={backTo} />}
        eyebrow={eyebrow}
        title={title}
        lede={subtitle}
        showDial={false}
      />
      <PortalBody>{children}</PortalBody>
    </PortalPage>
  )
}

/** The big status card at the top of a job's page: ring, pill, stepper. */
function StatusHero({ type, status }: { type: JobType; status: string }) {
  const stage = portalJobStage(type, status)
  const Icon = jobIcon(type)
  return (
    <section className="pt-card pt-rise" style={{ overflow: 'hidden' }}>
      <div className="pt-card-pad" style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <StageRing stage={stage} size={92}>
          <Icon size={28} strokeWidth={1.5} />
        </StageRing>
        <div style={{ minWidth: 0 }}>
          <p className="pt-label" style={{ margin: 0 }}>Where it’s at</p>
          <p className="pt-serif" style={{ fontSize: 30, lineHeight: 1.05, margin: '6px 0 8px' }}>{STAGE_COPY[stage]}</p>
          <StatusPill stage={stage} label={portalJobStatusLabel(type, status)} />
        </div>
      </div>
      <div style={{ padding: '4px 20px 20px' }}>
        <StageStepper stage={stage} />
      </div>
    </section>
  )
}

function ShopNote({ note, at }: { note?: string | null; at?: string | null }) {
  if (!note?.trim()) return null
  return (
    <div className="pt-callout pt-callout--note pt-rise" style={{ animationDelay: '0.08s', padding: 18 }}>
      <MessageSquareQuote size={18} className="pt-callout-icon" />
      <div>
        <p className="pt-label" style={{ margin: 0 }}>A note from the shop{at ? ` · ${formatDate(at)}` : ''}</p>
        <p className="pt-quote">“{note.trim()}”</p>
      </div>
    </div>
  )
}

function FactRow({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '12px 0' }}>
      <span style={{ color: 'var(--pt-brass)', marginTop: 2, flexShrink: 0 }}>{icon}</span>
      <div style={{ minWidth: 0 }}>
        <p className="pt-label" style={{ margin: 0 }}>{label}</p>
        <div style={{ fontSize: 14.5, marginTop: 3, color: 'var(--pt-text)' }}>{children}</div>
      </div>
    </div>
  )
}

function ShopContact({
  name,
  phone,
  email,
}: {
  name?: string | null
  phone?: string | null
  email?: string | null
}) {
  const p = phone?.trim()
  const e = email?.trim()
  if (!p && !e) return null
  return (
    <div className="pt-card pt-card-pad pt-rise" style={{ animationDelay: '0.2s' }}>
      <p className="pt-label" style={{ margin: 0 }}>Questions?</p>
      <p className="pt-serif" style={{ fontSize: 22, margin: '4px 0 14px' }}>
        {name ? <>Talk to {name}</> : 'Talk to the shop'}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {p && <a href={`tel:${p}`} className="pt-btn pt-btn--sm"><Phone size={13} /> {p}</a>}
        {e && <a href={`mailto:${e}`} className="pt-btn-ghost"><Mail size={13} /> Email</a>}
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
  // Newest first: the top of the list is where the job is now.
  const entries = [...history].sort((a, b) => b.created_at.localeCompare(a.created_at))
  return (
    <section className="pt-card pt-card-pad pt-rise" style={{ animationDelay: '0.12s' }}>
      <p className="pt-label" style={{ margin: '0 0 16px' }}>The journey so far</p>
      <ol className="pt-timeline">
        {entries.map((entry, idx) => (
          <li
            key={`${entry.created_at}-${idx}`}
            className={clsx('pt-tl-item', idx === 0 && 'pt-tl-item--latest')}
            style={{ animationDelay: `${0.15 + Math.min(idx, 8) * 0.05}s` }}
          >
            <span className="pt-tl-dot" />
            <div style={{ minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: 14.5, fontWeight: idx === 0 ? 700 : 500, color: idx === 0 ? 'var(--pt-text)' : 'var(--pt-text-mid)' }}>
                {portalJobStatusLabel(jobType, entry.new_status)}
              </p>
              <p className="pt-muted" style={{ margin: '2px 0 0', fontSize: 12 }}>{formatDate(entry.created_at)}</p>
              {entry.change_note && (
                <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--pt-text-mid)' }}>{entry.change_note}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function NotFound({ backTo }: { backTo: string }) {
  return (
    <DetailShell
      eyebrow="Job not found"
      title={<>We couldn’t find <em>that repair.</em></>}
      subtitle="This link may have expired. Head back to your repairs, or contact the shop for a fresh link."
      backTo={backTo}
    />
  )
}

function WatchJobDetail({ token, backTo }: { token: string; backTo: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portal-watch-detail', token],
    queryFn: () => getPublicJobStatus(token).then((r) => r.data),
  })

  if (isLoading) return <PortalLoading label="Opening the case back…" />
  if (isError || !data) return <NotFound backTo={backTo} />

  const watchTitle = [data.watch?.brand, data.watch?.model].filter(Boolean).join(' ') || 'Watch repair'
  return (
    <DetailShell
      eyebrow={<>{jobTypeLabel('watch')} · #{data.job_number}</>}
      title={data.title}
      subtitle={watchTitle}
      backTo={backTo}
      shopName={data.shop?.name}
    >
      <StatusHero type="watch" status={data.status} />
      <ShopNote note={data.customer_note} at={data.customer_note_at} />
      {data.collection_date && (
        <div className="pt-card pt-card-pad pt-rise" style={{ paddingTop: 8, paddingBottom: 8 }}>
          <FactRow icon={<CalendarClock size={17} />} label="Expected ready">
            {data.collection_date}
          </FactRow>
        </div>
      )}
      <HistoryTimeline jobType="watch" history={data.history} />
      <ShopContact name={data.shop?.name} phone={data.shop?.phone} email={data.shop?.email} />
    </DetailShell>
  )
}

function ShoeJobDetail({ token, backTo }: { token: string; backTo: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portal-shoe-detail', token],
    queryFn: () => getPublicShoeJobStatus(token).then((r) => r.data),
  })

  if (isLoading) return <PortalLoading label="Checking the workbench…" />
  if (isError || !data) return <NotFound backTo={backTo} />

  const shoeTitle = [data.shoe?.brand, data.shoe?.shoe_type].filter(Boolean).join(' · ') || 'Shoe repair'
  return (
    <DetailShell
      eyebrow={<>{jobTypeLabel('shoe')} · #{data.job_number}</>}
      title={data.title}
      subtitle={shoeTitle}
      backTo={backTo}
    >
      <StatusHero type="shoe" status={data.status} />
      <ShopNote note={data.customer_note} at={data.customer_note_at} />
      {data.items?.length > 0 && (
        <section className="pt-card pt-card-pad pt-rise" style={{ animationDelay: '0.1s' }}>
          <p className="pt-label" style={{ margin: '0 0 8px' }}>The work</p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {data.items.map((item, idx) => (
              <li
                key={idx}
                style={{
                  display: 'flex', justifyContent: 'space-between', gap: 12, padding: '10px 0', fontSize: 14.5,
                  borderTop: idx ? '1px solid var(--pt-line)' : undefined,
                }}
              >
                <span>{item.item_name}</span>
                <span className="pt-muted" style={{ fontVariantNumeric: 'tabular-nums' }}>× {item.quantity}</span>
              </li>
            ))}
          </ul>
        </section>
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

  if (isLoading) return <PortalLoading label="Finding your booking…" />
  if (isError || !data) return <NotFound backTo={backTo} />

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
    id: data.job_id ?? '',
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

  const hasFacts = !!(data.job_address || data.scheduled_at || data.description)

  return (
    <DetailShell
      eyebrow={<>{jobTypeLabel('auto_key')} · #{data.job_number}</>}
      title={data.title}
      subtitle={vehicle || undefined}
      backTo={backTo}
      shopName={data.shop_name}
    >
      <CustomerPortalJobCard job={jobCard} shop={shopStub} linkToDetail={false} />
      {hasFacts && (
        <section className="pt-card pt-card-pad pt-rise" style={{ paddingTop: 8, paddingBottom: 8, animationDelay: '0.1s' }}>
          {data.scheduled_at && (
            <FactRow icon={<CalendarClock size={17} />} label="Booked for">{formatDate(data.scheduled_at)}</FactRow>
          )}
          {data.job_address && (
            <FactRow icon={<MapPin size={17} />} label="Location">{data.job_address}</FactRow>
          )}
          {data.description && (
            <FactRow icon={<MessageSquareQuote size={17} />} label="The job">{data.description}</FactRow>
          )}
        </section>
      )}
      <ShopContact name={data.shop_name} phone={data.shop_phone} email={data.shop_email} />
    </DetailShell>
  )
}

export default function CustomerPortalJobDetailPage() {
  const { jobType, statusToken } = useParams<{ jobType: string; statusToken: string }>()
  const backTo = '/customer-portal'

  if (!statusToken || !jobType) {
    return (
      <DetailShell eyebrow="Invalid link" title={<>That link is <em>missing a piece.</em></>} subtitle="Missing job reference." backTo={backTo} />
    )
  }

  if (jobType === 'watch') return <WatchJobDetail token={statusToken} backTo={backTo} />
  if (jobType === 'shoe') return <ShoeJobDetail token={statusToken} backTo={backTo} />
  if (jobType === 'auto_key') return <AutoKeyJobDetail token={statusToken} backTo={backTo} />

  return (
    <DetailShell eyebrow="Unknown job type" title="We can’t show this one." subtitle="This job type is not supported." backTo={backTo} />
  )
}
