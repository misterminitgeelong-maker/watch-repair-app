import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CalendarClock,
  ChevronRight,
  CircleDollarSign,
  MapPinned,
  Radio,
  Route,
  UsersRound,
} from 'lucide-react'
import { Card, EmptyState } from '@/components/ui'
import {
  listInboundLeads,
  listJobPool,
  type AutoKeyJob,
  type TenantUser,
} from '@/lib/api'
import { mobileStatusLabel } from '@/lib/mobileStatus'
import { AUTO_KEY_CLOSED_STATUSES, canonicalAutoKeyStatus, computeSlaChip, formatCents, ymdLocal } from './dispatchHelpers'

const CLOSED = new Set<string>(AUTO_KEY_CLOSED_STATUSES)
const PRIORITY_WEIGHT: Record<string, number> = { urgent: 4, high: 3, normal: 2, low: 1 }
const createdAtMs = (value: string | null | undefined) => value ? new Date(value).getTime() : Number.MAX_SAFE_INTEGER

function Metric({ label, value, hint, tone = 'neutral' }: { label: string; value: string | number; hint: string; tone?: 'neutral' | 'warn' | 'good' }) {
  const color = tone === 'warn' ? 'var(--ms-error)' : tone === 'good' ? '#4F7A4A' : 'var(--ms-text)'
  return (
    <Card className="p-4 min-w-0">
      <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
      <p className="mt-1 text-2xl font-extrabold tabular-nums" style={{ color }}>{value}</p>
      <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>{hint}</p>
    </Card>
  )
}

function AttentionRow({ job, reason }: { job: AutoKeyJob; reason: string }) {
  return (
    <Link
      to={`/auto-key/${job.id}`}
      className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-[var(--ms-hover)]"
      style={{ borderBottom: '1px solid var(--ms-border)' }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-bold shrink-0" style={{ color: 'var(--ms-accent)' }}>#{job.job_number}</span>
          <span className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{job.customer_name ?? job.title}</span>
        </div>
        <p className="mt-0.5 text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>
          {reason} · {mobileStatusLabel(job.status)}
        </p>
      </div>
      <ChevronRight size={16} className="shrink-0" style={{ color: 'var(--ms-text-muted)' }} />
    </Link>
  )
}

export default function MobileOperationsToday({
  jobs,
  users,
}: {
  jobs: AutoKeyJob[]
  users: TenantUser[]
}) {
  const today = ymdLocal(new Date())
  const { data: inboundLeads = [] } = useQuery({
    queryKey: ['prospect-leads', 'operations-today'],
    queryFn: () => listInboundLeads().then(r => r.data),
    staleTime: 60_000,
  })
  const { data: poolJobs = [] } = useQuery({
    queryKey: ['job-pool'],
    queryFn: () => listJobPool().then(r => r.data),
    staleTime: 30_000,
  })

  const operational = useMemo(() => {
    const active = jobs.filter(j => !CLOSED.has(j.status))
    const todayJobs = active
      .filter(j => j.scheduled_at && ymdLocal(new Date(j.scheduled_at)) === today)
      .sort((a, b) => new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime())
    const unassigned = active.filter(j => !j.assigned_user_id)
    const unscheduled = active.filter(j => !j.scheduled_at)
    const quoteBacklog = active.filter(j => ['awaiting_quote', 'quote_sent'].includes(j.status))
    const fieldNow = active.filter(j => ['en_route', 'on_site'].includes(j.status))
    const awaitingMoney = jobs.filter(j => ['booking_completed', 'work_completed'].includes(canonicalAutoKeyStatus(j.status)))
    const urgent = active.filter(j => j.priority === 'urgent' || computeSlaChip(j)?.kind === 'late')

    const attention = active
      .map(job => {
        const sla = computeSlaChip(job)
        let reason = ''
        if (sla?.kind === 'late') reason = sla.label
        else if (job.priority === 'urgent') reason = 'Urgent priority'
        else if (!job.assigned_user_id) reason = 'No technician assigned'
        else if (!job.scheduled_at) reason = 'Needs a booking time'
        else if (job.status === 'awaiting_quote') reason = 'Quote required'
        return { job, reason, weight: (sla?.kind === 'late' ? 10 : 0) + (PRIORITY_WEIGHT[job.priority] ?? 0) }
      })
      .filter(row => row.reason)
      .sort((a, b) => b.weight - a.weight || createdAtMs(a.job.created_at) - createdAtMs(b.job.created_at))
      .slice(0, 8)

    return { active, todayJobs, unassigned, unscheduled, quoteBacklog, fieldNow, awaitingMoney, urgent, attention }
  }, [jobs, today])

  const techRows = useMemo(() => {
    const techs = users.filter(u => u.role === 'tech' && u.is_active)
    return techs.map(tech => {
      const assigned = operational.active.filter(j => j.assigned_user_id === tech.id)
      const scheduledToday = operational.todayJobs.filter(j => j.assigned_user_id === tech.id)
      return { tech, assigned: assigned.length, scheduledToday: scheduledToday.length }
    }).sort((a, b) => b.scheduledToday - a.scheduledToday || a.tech.full_name.localeCompare(b.tech.full_name))
  }, [operational.active, operational.todayJobs, users])

  const openLeads = inboundLeads.filter(l => !['won', 'lost'].includes(l.status))
  const dueFollowUps = openLeads.filter(l => l.next_follow_up_on && l.next_follow_up_on <= today)
  const bookedValue = operational.todayJobs.reduce((sum, job) => sum + Math.max(0, job.cost_cents || 0), 0)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--ms-accent)' }}>Operations command centre</p>
          <h2 className="text-xl font-extrabold mt-1" style={{ color: 'var(--ms-text)' }}>Today’s mobile operation</h2>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>Work needing action, technician load and commercial follow-through in one view.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <Link to="/auto-key/pool" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border)' }}>
            <Radio size={14} /> Dispatch pool {poolJobs.length > 0 && `(${poolJobs.length})`}
          </Link>
          <Link to="/auto-key/prospects/inbox" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border)' }}>
            <UsersRound size={14} /> Lead inbox ({openLeads.length})
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-6">
        <Metric label="Today" value={operational.todayJobs.length} hint={`${operational.fieldNow.length} currently in field`} />
        <Metric label="Booked value" value={formatCents(bookedValue)} hint="Today’s scheduled sell value" tone="good" />
        <Metric label="Urgent / late" value={operational.urgent.length} hint="Needs dispatch attention" tone={operational.urgent.length ? 'warn' : 'good'} />
        <Metric label="Unassigned" value={operational.unassigned.length} hint="No technician owner" tone={operational.unassigned.length ? 'warn' : 'neutral'} />
        <Metric label="Unscheduled" value={operational.unscheduled.length} hint="Active jobs without a slot" tone={operational.unscheduled.length ? 'warn' : 'neutral'} />
        <Metric label="Follow-up due" value={dueFollowUps.length} hint={`${openLeads.length} open leads`} tone={dueFollowUps.length ? 'warn' : 'neutral'} />
      </div>

      <div className="grid gap-5 xl:grid-cols-12">
        <Card className="overflow-hidden xl:col-span-7">
          <div className="flex items-center justify-between gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} style={{ color: operational.attention.length ? 'var(--ms-error)' : '#4F7A4A' }} />
              <h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Attention queue</h3>
            </div>
            <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{operational.attention.length} highest priority</span>
          </div>
          {operational.attention.length === 0
            ? <EmptyState message="Nothing needs immediate attention." />
            : operational.attention.map(row => <AttentionRow key={row.job.id} job={row.job} reason={row.reason} />)}
        </Card>

        <Card className="overflow-hidden xl:col-span-5">
          <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
            <CalendarClock size={16} style={{ color: 'var(--ms-accent)' }} />
            <h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Today’s run sheet</h3>
          </div>
          {operational.todayJobs.length === 0 ? (
            <EmptyState message="No jobs scheduled today." />
          ) : (
            <div>
              {operational.todayJobs.slice(0, 8).map(job => {
                const tech = users.find(u => u.id === job.assigned_user_id)
                return (
                  <Link key={job.id} to={`/auto-key/${job.id}`} className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--ms-hover)]" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                    <span className="text-xs font-extrabold tabular-nums w-14 shrink-0" style={{ color: 'var(--ms-accent)' }}>
                      {new Date(job.scheduled_at!).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{job.customer_name ?? job.title}</p>
                      <p className="text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>{tech?.full_name ?? 'Unassigned'}{job.job_address ? ` · ${job.job_address}` : ''}</p>
                    </div>
                  </Link>
                )
              })}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <div className="flex items-center gap-2 mb-3"><Route size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Technician capacity</h3></div>
          {techRows.length === 0 ? <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No active technicians configured.</p> : (
            <div className="grid gap-2 sm:grid-cols-2">
              {techRows.map(({ tech, assigned, scheduledToday }) => (
                <div key={tech.id} className="rounded-lg px-3 py-2.5" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{tech.full_name}</span>
                    <span className="text-xs font-bold" style={{ color: scheduledToday >= 6 ? 'var(--ms-error)' : 'var(--ms-accent)' }}>{scheduledToday} today</span>
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>{assigned} total active jobs</p>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3"><CircleDollarSign size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Commercial follow-through</h3></div>
          <div className="space-y-3 text-sm">
            <Link to="/auto-key?view=jobs&jobs_layout=list&status=awaiting_quote" className="flex items-center justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Quotes required</span><strong style={{ color: 'var(--ms-text)' }}>{operational.quoteBacklog.length}</strong></Link>
            <Link to="/auto-key?view=jobs&jobs_layout=list&status=work_completed" className="flex items-center justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Completed, not paid</span><strong style={{ color: 'var(--ms-text)' }}>{operational.awaitingMoney.length}</strong></Link>
            <Link to="/auto-key?view=map" className="flex items-center gap-2 pt-2 font-semibold" style={{ color: 'var(--ms-accent)', borderTop: '1px solid var(--ms-border)' }}><MapPinned size={14} /> Open dispatch map <ChevronRight size={14} className="ml-auto" /></Link>
          </div>
        </Card>
      </div>
    </div>
  )
}
