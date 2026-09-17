import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CalendarClock,
  ChevronRight,
  CircleDollarSign,
  Info,
  MapPinned,
  Radio,
  RefreshCw,
  Route,
  Target,
  UsersRound,
} from 'lucide-react'
import { Button, Card, EmptyState, Spinner } from '@/components/ui'
import {
  getApiErrorMessage,
  getAutoKeyCockpit,
  listJobPool,
  setAutoKeyWeeklyTarget,
  type MobileCockpit,
  type MobileCockpitFocusKey,
  type MobileCockpitJobSummary,
  type MobileCockpitMetric,
  type MobileCockpitQueue,
  type MobileCockpitTone,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import {
  TONE_BACKGROUNDS,
  TONE_COLORS,
  comparisonLabel,
  formatDelta,
  formatMetricValue,
  formatMinutes,
  formatShopDay,
} from '@/lib/cockpitFormat'
import { COCKPIT_QUERY_KEY, focusHref } from '@/lib/cockpitFocus'
import { mobileStatusLabel } from '@/lib/mobileStatus'
import { formatCents } from '@/lib/money'
import { dollarsToCents } from '@/lib/money'

function toneStyle(tone: MobileCockpitTone) {
  return { color: TONE_COLORS[tone], backgroundColor: TONE_BACKGROUNDS[tone] }
}

function SectionTitle({ icon, title, hint }: { icon: React.ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mb-3 min-w-0">
      <span style={{ color: 'var(--ms-accent)' }}>{icon}</span>
      <h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>{title}</h3>
      {hint && <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{hint}</span>}
    </div>
  )
}

function AttentionTile({ queue }: { queue: MobileCockpitQueue }) {
  const tone: MobileCockpitTone = queue.count === 0 ? 'neutral' : queue.tone
  return (
    <Link
      to={focusHref(queue.key)}
      className="block rounded-lg p-3 min-w-0 transition-colors hover:bg-[var(--ms-hover)]"
      style={{ border: `1px solid ${queue.count > 0 && tone !== 'neutral' ? TONE_COLORS[tone] : 'var(--ms-border)'}`, backgroundColor: 'var(--ms-surface)' }}
      title={queue.description}
      aria-label={`${queue.label}: ${queue.count}. Open the filtered list`}
    >
      <p className="text-[11px] font-bold uppercase tracking-wider truncate" style={{ color: 'var(--ms-text-muted)' }}>{queue.label}</p>
      <p className="mt-1 text-2xl font-extrabold tabular-nums" style={{ color: queue.count > 0 && tone !== 'neutral' ? TONE_COLORS[tone] : 'var(--ms-text)' }}>{queue.count}</p>
      <p className="mt-0.5 text-[11px] leading-snug line-clamp-2" style={{ color: 'var(--ms-text-muted)' }}>{queue.description}</p>
    </Link>
  )
}

function JobRow({ job, timeZone, todayYmd, reason, trailing }: { job: MobileCockpitJobSummary; timeZone: string; todayYmd: string; reason?: string; trailing?: React.ReactNode }) {
  return (
    <Link
      to={`/auto-key/${job.id}`}
      className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-[var(--ms-hover)]"
      style={{ borderBottom: '1px solid var(--ms-border)' }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-bold shrink-0" style={{ color: 'var(--ms-accent)' }}>#{job.job_number}</span>
          <span className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{job.customer_name ?? job.title}</span>
        </div>
        <p className="mt-0.5 text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>
          {[reason, formatShopDay(job.scheduled_at, timeZone, todayYmd), job.assigned_name ?? 'Unassigned', mobileStatusLabel(job.status)].filter(Boolean).join(' · ')}
        </p>
      </div>
      {trailing}
      <ChevronRight size={16} className="shrink-0" style={{ color: 'var(--ms-text-muted)' }} />
    </Link>
  )
}

function QueueCard({ queue, timeZone, todayYmd, subtitle, empty }: { queue: MobileCockpitQueue; timeZone: string; todayYmd: string; subtitle?: string; empty: string }) {
  return (
    <Card className="overflow-hidden flex flex-col">
      <div className="flex items-center justify-between gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
        <div className="min-w-0">
          <h4 className="text-sm font-bold truncate" style={{ color: 'var(--ms-text)' }}>{queue.label}</h4>
          {subtitle && <p className="text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>{subtitle}</p>}
        </div>
        <Link to={focusHref(queue.key)} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold shrink-0" style={toneStyle(queue.count ? queue.tone : 'neutral')}>
          {queue.count} <ChevronRight size={12} />
        </Link>
      </div>
      {queue.items.length === 0 ? (
        <p className="px-4 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>{empty}</p>
      ) : (
        <div>
          {queue.items.map(job => <JobRow key={job.id} job={job} timeZone={timeZone} todayYmd={todayYmd} />)}
          {queue.count > queue.items.length && (
            <Link to={focusHref(queue.key)} className="block px-4 py-2 text-xs font-semibold" style={{ color: 'var(--ms-accent)' }}>
              View all {queue.count}
            </Link>
          )}
        </div>
      )}
    </Card>
  )
}

const METRIC_DRILL: Record<MobileCockpitMetric['key'], MobileCockpitFocusKey | null> = {
  booked: 'this_week',
  completed: 'completed_this_week',
  invoiced: 'invoiced_this_week',
  collected: 'collected_this_week',
  jobs_created: null,
  jobs_completed: 'completed_this_week',
}

function DeltaLine({ label, delta, tone, unit }: { label: string; delta: MobileCockpitMetric['vs_previous']; tone: MobileCockpitTone; unit: 'cents' | 'count' }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs">
      <span className="truncate" style={{ color: 'var(--ms-text-muted)' }}>{label}</span>
      <span className="font-semibold tabular-nums shrink-0" style={{ color: TONE_COLORS[tone] }}>{formatDelta(delta, unit)}</span>
    </div>
  )
}

function MetricCard({ metric }: { metric: MobileCockpitMetric }) {
  const drill = METRIC_DRILL[metric.key]
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--ms-text-muted)' }}>{metric.label}</p>
        <span title={metric.definition} aria-label={metric.definition}><Info size={13} style={{ color: 'var(--ms-text-muted)' }} /></span>
      </div>
      <p className="mt-1 text-2xl font-extrabold tabular-nums" style={{ color: 'var(--ms-text)' }}>{formatMetricValue(metric.current, metric.unit)}</p>
      <p className="text-[11px] mb-2" style={{ color: 'var(--ms-text-muted)' }}>
        {metric.partial ? `${metric.days_elapsed} of 7 days` : 'full week'} · last wk {formatMetricValue(metric.previous, metric.unit)}
      </p>
      <div className="space-y-1">
        <DeltaLine label={comparisonLabel(metric, 'previous')} delta={metric.vs_previous} tone={metric.vs_previous_tone} unit={metric.unit} />
        <DeltaLine label={comparisonLabel(metric, 'four_week')} delta={metric.vs_four_week} tone={metric.vs_four_week_tone} unit={metric.unit} />
        {metric.target != null && (
          <DeltaLine label={comparisonLabel(metric, 'target')} delta={metric.vs_target} tone={metric.vs_target_tone} unit={metric.unit} />
        )}
      </div>
    </>
  )
  if (!drill) return <Card className="p-4 min-w-0">{body}</Card>
  return (
    <Link to={focusHref(drill)} className="block min-w-0" aria-label={`${metric.label}: open the jobs behind this figure`}>
      <Card className="p-4 min-w-0 h-full ms-card-hoverable" hoverable>{body}</Card>
    </Link>
  )
}

function OutstandingCard({ outstanding }: { outstanding: MobileCockpit['outstanding'] }) {
  const overdueTone: MobileCockpitTone = outstanding.overdue_cents > 0 ? 'bad' : 'neutral'
  const buckets: Array<[label: string, cents: number, count: number, tone: MobileCockpitTone]> = [
    ['0–7 days', outstanding.aging_cents.current, outstanding.aging_counts.current, 'neutral'],
    ['8–30 days', outstanding.aging_cents.d8_30, outstanding.aging_counts.d8_30, 'warn'],
    ['31+ days', outstanding.aging_cents.d31_plus, outstanding.aging_counts.d31_plus, 'bad'],
  ]
  return (
    <Link to={focusHref('unpaid_invoices')} className="block min-w-0" aria-label="Outstanding: open unpaid invoices">
      <Card className="p-4 min-w-0 h-full" hoverable>
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--ms-text-muted)' }}>{outstanding.label}</p>
          <span title={outstanding.definition}><Info size={13} style={{ color: 'var(--ms-text-muted)' }} /></span>
        </div>
        <p className="mt-1 text-2xl font-extrabold tabular-nums" style={{ color: overdueTone === 'bad' ? TONE_COLORS.bad : 'var(--ms-text)' }}>{formatCents(outstanding.current)}</p>
        <p className="text-[11px] mb-2" style={{ color: 'var(--ms-text-muted)' }}>{outstanding.count} unpaid invoice{outstanding.count === 1 ? '' : 's'} · {formatCents(outstanding.overdue_cents)} overdue</p>
        <div className="space-y-1">
          {buckets.map(([label, cents, count, tone]) => (
            <div key={label} className="flex items-baseline justify-between gap-2 text-xs">
              <span style={{ color: 'var(--ms-text-muted)' }}>{label}</span>
              <span className="font-semibold tabular-nums" style={{ color: cents > 0 ? TONE_COLORS[tone] : 'var(--ms-text-muted)' }}>{formatCents(cents)}{count > 0 ? ` · ${count}` : ''}</span>
            </div>
          ))}
        </div>
      </Card>
    </Link>
  )
}

function TechnicianRow({ tech, timeZone, todayYmd }: { tech: MobileCockpit['technicians'][number]; timeZone: string; todayYmd: string }) {
  const pct = Math.min(100, tech.utilisation_pct)
  const barColor = pct >= 100 ? TONE_COLORS.bad : pct >= 75 ? TONE_COLORS.warn : TONE_COLORS.good
  return (
    <div className="rounded-lg px-3 py-2.5 min-w-0" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}>
      <div className="flex items-center justify-between gap-2 min-w-0">
        <Link to={`/auto-key?view=planner&dispatch_tech=${tech.user_id}`} className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{tech.name}</Link>
        <span className="text-xs font-bold shrink-0 tabular-nums" style={{ color: tech.available_minutes === 0 ? TONE_COLORS.bad : 'var(--ms-accent)' }}>
          {formatMinutes(tech.available_minutes)} free
        </span>
      </div>
      <div className="mt-1.5 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--ms-border)' }} aria-hidden>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: barColor }} />
      </div>
      <p className="mt-1.5 text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>
        <Link to={`/auto-key?view=jobs&jobs_layout=list&tech=${tech.user_id}&focus=today`} style={{ color: 'var(--ms-text-mid)' }}>{tech.scheduled_today} today</Link>
        {' · '}{formatMinutes(tech.booked_minutes_today)} booked · {tech.active_jobs} active
        {tech.in_field_now && <span className="ml-1 font-semibold" style={{ color: TONE_COLORS.good }}>· in field{tech.current_job_number ? ` #${tech.current_job_number}` : ''}</span>}
      </p>
      {tech.next_job && (
        <p className="text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>
          Next: <Link to={`/auto-key/${tech.next_job.id}`} style={{ color: 'var(--ms-accent)' }}>#{tech.next_job.job_number}</Link> {formatShopDay(tech.next_job.scheduled_at, timeZone, todayYmd)}{tech.next_job.job_address ? ` · ${tech.next_job.job_address}` : ''}
        </p>
      )}
      {(tech.late_today > 0 || tech.conflicts.length > 0) && (
        <p className="mt-1 text-xs font-semibold" style={{ color: TONE_COLORS.bad }}>
          {tech.late_today > 0 && `${tech.late_today} late today`}
          {tech.late_today > 0 && tech.conflicts.length > 0 && ' · '}
          {tech.conflicts.map(c => `#${c.job_number} → #${c.next_job_number} only ${c.gap_minutes} min apart`).join(' · ')}
        </p>
      )}
      <p className="mt-1 text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
        This week: {tech.completed_week} completed · {formatCents(tech.collected_week_cents)} collected
      </p>
    </div>
  )
}

function TargetEditor({ current, canEdit }: { current: number | null; canEdit: boolean }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(current != null ? (current / 100).toFixed(0) : '')
  const mutation = useMutation({
    mutationFn: (cents: number | null) => setAutoKeyWeeklyTarget(cents),
    onSuccess: () => {
      setEditing(false)
      void qc.invalidateQueries({ queryKey: COCKPIT_QUERY_KEY })
    },
  })
  if (!canEdit) {
    return <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{current != null ? `Weekly cash target ${formatCents(current)}` : 'No weekly cash target set (owner can set one)'}</span>
  }
  if (!editing) {
    return (
      <button type="button" onClick={() => setEditing(true)} className="inline-flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--ms-accent)' }}>
        <Target size={13} /> {current != null ? `Weekly cash target ${formatCents(current)}` : 'Set a weekly cash target'}
      </button>
    )
  }
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={e => {
        e.preventDefault()
        const trimmed = value.trim()
        mutation.mutate(trimmed ? dollarsToCents(trimmed) : null)
      }}
    >
      <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }} htmlFor="cockpit-target">Weekly cash target $</label>
      <input
        id="cockpit-target"
        type="number"
        min={0}
        step={100}
        value={value}
        onChange={e => setValue(e.target.value)}
        className="w-28 rounded-md px-2 py-1 text-sm"
        style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
      />
      <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save'}</Button>
      <button type="button" className="text-xs" style={{ color: 'var(--ms-text-muted)' }} onClick={() => setEditing(false)}>Cancel</button>
      {mutation.isError && <span className="text-xs" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(mutation.error, 'Could not save')}</span>}
    </form>
  )
}

export default function MobileOperationsCockpit() {
  const { role } = useAuth()
  const canEditTarget = role === 'owner' || role === 'platform_admin'
  const cockpitQuery = useQuery({
    queryKey: COCKPIT_QUERY_KEY,
    queryFn: () => getAutoKeyCockpit().then(r => r.data),
    staleTime: 30_000,
    refetchInterval: 120_000,
  })
  const { data: poolJobs = [] } = useQuery({
    queryKey: ['job-pool'],
    queryFn: () => listJobPool().then(r => r.data),
    staleTime: 30_000,
  })

  if (cockpitQuery.isLoading) return <Spinner />
  if (cockpitQuery.isError || !cockpitQuery.data) {
    return (
      <Card className="p-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(cockpitQuery.error, 'Could not load the operations cockpit.')}</p>
        <Button type="button" variant="secondary" onClick={() => void cockpitQuery.refetch()}><RefreshCw size={14} /> Retry</Button>
      </Card>
    )
  }

  const data = cockpitQuery.data
  const timeZone = data.timezone
  const todayYmd = data.as_of
  const attentionCount = data.attention.filter(q => q.key !== 'today' && q.key !== 'in_field').reduce((sum, q) => sum + q.count, 0)
  const totalActive = data.active_by_category.reduce((sum, c) => sum + c.count, 0)
  const nothingYet = totalActive === 0 && data.metrics.every(m => m.current === 0 && m.previous === 0) && data.outstanding.count === 0
  const followUps = data.follow_ups
  const ladder = data.metrics.filter(m => m.unit === 'cents')
  const counts = data.metrics.filter(m => m.unit === 'count')
  const weekLabel = `${new Date(`${data.week.start}T00:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })} – ${new Date(`${data.week.end}T00:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}`

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--ms-accent)' }}>Operations cockpit</p>
          <h2 className="text-xl font-extrabold mt-1" style={{ color: 'var(--ms-text)' }}>Mobile operation today</h2>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            {new Date(`${data.as_of}T00:00:00`).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })} · week {weekLabel}, day {data.week.days_elapsed} of 7 · shop time {timeZone}
            {cockpitQuery.isFetching && ' · refreshing…'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <Link to="/auto-key/pool" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border)' }}>
            <Radio size={14} /> Dispatch pool {poolJobs.length > 0 && `(${poolJobs.length})`}
          </Link>
          <Link to="/auto-key/prospects/inbox" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border)' }}>
            <UsersRound size={14} /> Lead inbox
          </Link>
          <Link to="/auto-key?view=map" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border)' }}>
            <MapPinned size={14} /> Map
          </Link>
        </div>
      </div>

      {nothingYet && (
        <Card className="p-5">
          <EmptyState message="No Mobile Services jobs yet. Once jobs are booked, this cockpit shows what needs attention, technician capacity and how the week is tracking." />
        </Card>
      )}

      {/* ── What needs attention now ── */}
      <section aria-labelledby="cockpit-attention">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle size={16} style={{ color: attentionCount ? TONE_COLORS.bad : TONE_COLORS.good }} />
          <h3 id="cockpit-attention" className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>What needs attention now</h3>
          <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{attentionCount === 0 ? 'nothing blocked' : `${attentionCount} job${attentionCount === 1 ? '' : 's'} need action`} · tap a tile to open the list</span>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
          {data.attention.map(queue => <AttentionTile key={queue.key} queue={queue} />)}
        </div>
      </section>

      {/* ── Late / unscheduled / unassigned lists ── */}
      <div className="grid gap-4 lg:grid-cols-3">
        <QueueCard queue={data.attention.find(q => q.key === 'late')!} timeZone={timeZone} todayYmd={todayYmd} subtitle="Booked time passed, not en route" empty="Nobody is running late." />
        <QueueCard queue={data.attention.find(q => q.key === 'today')!} timeZone={timeZone} todayYmd={todayYmd} subtitle="Run sheet, in shop time" empty="No jobs booked today." />
        <QueueCard queue={data.attention.find(q => q.key === 'unscheduled')!} timeZone={timeZone} todayYmd={todayYmd} subtitle="Need a booking time" empty="Every active job has a time." />
      </div>

      {/* ── Money ladder ── */}
      <section aria-labelledby="cockpit-money">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <CircleDollarSign size={16} style={{ color: 'var(--ms-accent)' }} />
            <h3 id="cockpit-money" className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>This week’s money</h3>
            <span className="text-xs hidden sm:inline" style={{ color: 'var(--ms-text-muted)' }}>booked → completed → invoiced → collected → outstanding · jobs, quotes, invoices and cash are counted separately</span>
          </div>
          <TargetEditor current={data.weekly_target_cents} canEdit={canEditTarget} />
        </div>
        {data.week.days_elapsed < 7 && (
          <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>
            Week in progress: comparisons are against the same {data.week.days_elapsed} day{data.week.days_elapsed === 1 ? '' : 's'} of last week, the four-week average and the pro-rated target.
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {ladder.map(metric => <MetricCard key={metric.key} metric={metric} />)}
          <OutstandingCard outstanding={data.outstanding} />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:max-w-md">
          {counts.map(metric => <MetricCard key={metric.key} metric={metric} />)}
        </div>
      </section>

      {/* ── Technicians ── */}
      <section aria-labelledby="cockpit-techs">
        <Card className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <SectionTitle icon={<Route size={16} />} title="Technician capacity today" hint={`${formatMinutes(data.capacity.available_minutes)} free of ${formatMinutes(data.capacity.capacity_minutes)} across ${data.capacity.technicians} tech${data.capacity.technicians === 1 ? '' : 's'}`} />
            <div className="flex flex-wrap gap-2 text-xs font-semibold">
              {data.capacity.unassigned_today > 0 && (
                <Link to={focusHref('unassigned')} className="rounded-full px-2.5 py-1" style={toneStyle('warn')}>{data.capacity.unassigned_today} booked today with no tech</Link>
              )}
              {data.capacity.conflicts > 0 && (
                <span className="rounded-full px-2.5 py-1" style={toneStyle('bad')}>{data.capacity.conflicts} schedule conflict{data.capacity.conflicts === 1 ? '' : 's'}</span>
              )}
            </div>
          </div>
          {data.technicians.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No active technicians configured. Add technicians under Team to see capacity.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {data.technicians.map(tech => <TechnicianRow key={tech.user_id} tech={tech} timeZone={timeZone} todayYmd={todayYmd} />)}
            </div>
          )}
          <p className="mt-3 text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
            Capacity assumes {data.assumptions.assumed_job_minutes} min per booking in a {Math.round(data.assumptions.tech_day_minutes / 60)}-hour day; no travel time is estimated because job locations are not geocoded.
          </p>
        </Card>
      </section>

      {/* ── Follow-ups ── */}
      <section aria-labelledby="cockpit-followups">
        <div className="flex items-center gap-2 mb-3">
          <CalendarClock size={16} style={{ color: 'var(--ms-accent)' }} />
          <h3 id="cockpit-followups" className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Follow-ups</h3>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <QueueCard
            queue={followUps.quotes}
            timeZone={timeZone}
            todayYmd={todayYmd}
            subtitle={`${followUps.quotes.open_count} quote${followUps.quotes.open_count === 1 ? '' : 's'} out · ${formatCents(followUps.quotes.value_cents)} quoted`}
            empty="No quotes waiting past the follow-up window."
          />
          <QueueCard
            queue={followUps.confirmations}
            timeZone={timeZone}
            todayYmd={todayYmd}
            subtitle={`${followUps.confirmations.open_count} booking${followUps.confirmations.open_count === 1 ? '' : 's'} awaiting a customer`}
            empty="Every booking request has been answered."
          />
          <QueueCard
            queue={followUps.completed_unpaid}
            timeZone={timeZone}
            todayYmd={todayYmd}
            subtitle={`${formatCents(followUps.completed_unpaid.value_cents)} of finished work not yet paid`}
            empty="All completed work is paid."
          />
          <Card className="overflow-hidden flex flex-col">
            <div className="flex items-center justify-between gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
              <div className="min-w-0">
                <h4 className="text-sm font-bold truncate" style={{ color: 'var(--ms-text)' }}>{followUps.overdue_invoices.label}</h4>
                <p className="text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>{formatCents(followUps.overdue_invoices.value_cents)} older than {data.assumptions.invoice_overdue_days} days</p>
              </div>
              <Link to={focusHref('overdue_invoices')} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold shrink-0" style={toneStyle(followUps.overdue_invoices.count ? 'bad' : 'neutral')}>
                {followUps.overdue_invoices.count} <ChevronRight size={12} />
              </Link>
            </div>
            {followUps.overdue_invoices.items.length === 0 ? (
              <p className="px-4 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No overdue invoices.</p>
            ) : (
              followUps.overdue_invoices.items.map(item => (
                <JobRow
                  key={item.invoice_id}
                  job={item}
                  timeZone={timeZone}
                  todayYmd={todayYmd}
                  reason={`Inv ${item.invoice_number} · ${item.invoice_age_days}d`}
                  trailing={<span className="text-xs font-bold tabular-nums shrink-0" style={{ color: TONE_COLORS.bad }}>{formatCents(item.invoice_total_cents)}</span>}
                />
              ))
            )}
          </Card>
        </div>
      </section>

      {/* ── Where the work sits + data quality ── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <SectionTitle icon={<Route size={16} />} title="Where the active work sits" hint={`${totalActive} active`} />
          <div className="grid grid-cols-3 gap-2">
            {data.active_by_category.map(row => (
              <Link key={row.category} to={`/auto-key?view=jobs&jobs_layout=list&category=${row.category}`} className="rounded-lg px-3 py-2 min-w-0" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}>
                <p className="text-[11px] font-bold uppercase tracking-wider truncate" style={{ color: 'var(--ms-text-muted)' }}>{row.label}</p>
                <p className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--ms-text)' }}>{row.count}</p>
              </Link>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <SectionTitle icon={<Info size={16} />} title="Definitions and data quality" />
          <ul className="space-y-1.5 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
            {data.data_quality.map(item => (
              <li key={item.code} className="flex gap-2">
                <span className="shrink-0" style={{ color: item.count ? TONE_COLORS.warn : 'var(--ms-text-muted)' }}>•</span>
                <span>{item.count != null ? <strong style={{ color: 'var(--ms-text)' }}>{item.count} </strong> : null}{item.message}</span>
              </li>
            ))}
            <li className="flex gap-2"><span className="shrink-0" style={{ color: 'var(--ms-text-muted)' }}>•</span><span>Quote follow-up after {data.assumptions.quote_follow_up_days} days; booking confirmation follow-up after {data.assumptions.confirmation_follow_up_hours} hours; invoices overdue after {data.assumptions.invoice_overdue_days} days.</span></li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
