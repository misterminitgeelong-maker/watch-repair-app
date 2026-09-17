import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  Clock3,
  MapPinned,
  Navigation,
  Phone,
  Radio,
  Route,
  UserRoundX,
} from 'lucide-react'
import { Button, Card, Modal } from '@/components/ui'
import {
  getApiErrorMessage,
  updateAutoKeyJobStatus,
  type JobStatus,
  type MobileCockpit,
  type MobileCockpitFocusKey,
  type MobileCockpitJobSummary,
  type MobileCockpitQueue,
  type MobileCockpitTone,
} from '@/lib/api'
import { invalidateAutoKeyJobCollections } from '@/lib/autoKeyJobQueries'
import { TONE_BACKGROUNDS, TONE_COLORS, formatShopDay } from '@/lib/cockpitFormat'
import { focusHref } from '@/lib/cockpitFocus'
import { formatCents } from '@/lib/money'
import { mobileStatusLabel } from '@/lib/mobileStatus'
import { nextMobileStatus } from './dispatchHelpers'

function queueFor(data: MobileCockpit, key: MobileCockpitFocusKey): MobileCockpitQueue | undefined {
  return data.attention.find(queue => queue.key === key)
}

function uniqueJobs(queues: Array<MobileCockpitQueue | undefined>): MobileCockpitJobSummary[] {
  const jobs = new Map<string, MobileCockpitJobSummary>()
  queues.forEach(queue => queue?.items.forEach(job => jobs.set(job.id, job)))
  return [...jobs.values()]
}

function jobSort(a: MobileCockpitJobSummary, b: MobileCockpitJobSummary) {
  const field = new Set(['en_route', 'on_site', 'working_on', 'service'])
  const fieldDifference = Number(field.has(b.status)) - Number(field.has(a.status))
  if (fieldDifference) return fieldDifference
  if (!a.scheduled_at) return 1
  if (!b.scheduled_at) return -1
  return new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime()
}

function quickStatusCopy(status: JobStatus) {
  if (status === 'en_route') return 'Start trip'
  if (status === 'on_site') return 'I’ve arrived'
  if (status === 'work_completed') return 'Complete job'
  return `Mark ${mobileStatusLabel(status)}`
}

function MobileJobCard({ job, data, lateIds }: { job: MobileCockpitJobSummary; data: MobileCockpit; lateIds: Set<string> }) {
  const qc = useQueryClient()
  const [confirmComplete, setConfirmComplete] = useState(false)
  const [error, setError] = useState('')
  const nextStatus = nextMobileStatus(job.canonical_status)
  const isLate = lateIds.has(job.id)
  const directionsHref = job.job_address
    ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`
    : null
  const mutation = useMutation({
    mutationFn: (status: JobStatus) => updateAutoKeyJobStatus(job.id, status),
    onSuccess: () => {
      setConfirmComplete(false)
      setError('')
      invalidateAutoKeyJobCollections(qc)
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not update the job. Please try again.')),
  })

  const advance = () => {
    if (!nextStatus) return
    if (nextStatus === 'work_completed') {
      setConfirmComplete(true)
      return
    }
    mutation.mutate(nextStatus)
  }

  return (
    <>
      <Card className="overflow-hidden">
        <Link to={`/auto-key/${job.id}`} className="block min-h-11 px-4 pt-3 pb-2 active:bg-[var(--ms-hover)]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-bold" style={{ color: 'var(--ms-accent)' }}>#{job.job_number}</span>
                {isLate && <span className="rounded-full px-2 py-0.5 text-[11px] font-bold" style={{ color: TONE_COLORS.bad, backgroundColor: TONE_BACKGROUNDS.bad }}>Late</span>}
                {(job.priority === 'urgent' || job.priority === 'high') && (
                  <span className="rounded-full px-2 py-0.5 text-[11px] font-bold uppercase" style={{ color: job.priority === 'urgent' ? TONE_COLORS.bad : TONE_COLORS.warn, backgroundColor: job.priority === 'urgent' ? TONE_BACKGROUNDS.bad : TONE_BACKGROUNDS.warn }}>
                    {job.priority}
                  </span>
                )}
              </div>
              <p className="mt-1 truncate text-base font-bold" style={{ color: 'var(--ms-text)' }}>{job.customer_name ?? job.title}</p>
              {job.customer_name && <p className="truncate text-sm" style={{ color: 'var(--ms-text-mid)' }}>{job.title}</p>}
            </div>
            <ChevronRight size={18} className="mt-1 shrink-0" style={{ color: 'var(--ms-text-muted)' }} />
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            <span className="inline-flex items-center gap-1"><Clock3 size={13} />{formatShopDay(job.scheduled_at, data.timezone, data.as_of)}</span>
            <span>{job.assigned_name ?? 'Unassigned'}</span>
            <span>{mobileStatusLabel(job.status)}</span>
          </div>
          {job.job_address && <p className="mt-1.5 line-clamp-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>{job.job_address}</p>}
        </Link>

        <div className="grid grid-cols-3 gap-2 px-3 pb-3 pt-1">
          {job.customer_phone ? (
            <a href={`tel:${job.customer_phone.replace(/\s/g, '')}`} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-2 text-sm font-semibold" style={{ color: 'var(--ms-text)', border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
              <Phone size={16} /> Call
            </a>
          ) : (
            <span className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-2 text-sm" style={{ color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
              <Phone size={16} /> No phone
            </span>
          )}
          {directionsHref ? (
            <a href={directionsHref} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-2 text-sm font-semibold" style={{ color: 'var(--ms-text)', border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
              <Navigation size={16} /> Route
            </a>
          ) : (
            <span className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-2 text-sm" style={{ color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
              <Navigation size={16} /> No address
            </span>
          )}
          {nextStatus ? (
            <button type="button" onClick={advance} disabled={mutation.isPending} className="inline-flex min-h-11 items-center justify-center gap-1 rounded-lg px-2 text-sm font-bold disabled:opacity-50" style={{ color: 'var(--ms-on-accent)', backgroundColor: 'var(--ms-accent)' }}>
              {mutation.isPending ? 'Saving…' : quickStatusCopy(nextStatus)}
            </button>
          ) : (
            <Link to={`/auto-key/${job.id}`} className="inline-flex min-h-11 items-center justify-center gap-1 rounded-lg px-2 text-sm font-bold" style={{ color: 'var(--ms-on-accent)', backgroundColor: 'var(--ms-accent)' }}>
              Open <ArrowRight size={14} />
            </Link>
          )}
        </div>
        {error && <p role="alert" className="mx-3 mb-3 rounded-lg px-3 py-2 text-xs" style={{ color: TONE_COLORS.bad, backgroundColor: TONE_BACKGROUNDS.bad }}>{error}</p>}
      </Card>

      {confirmComplete && (
        <Modal title={`Complete job #${job.job_number}?`} onClose={() => !mutation.isPending && setConfirmComplete(false)}>
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            This marks the work complete. If the job has an approved quote, Mainspring may create the invoice and send its payment link.
          </p>
          <div className="mt-4 flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={() => setConfirmComplete(false)} disabled={mutation.isPending}>Cancel</Button>
            <Button className="flex-1" onClick={() => mutation.mutate('work_completed')} disabled={mutation.isPending}>{mutation.isPending ? 'Completing…' : 'Complete job'}</Button>
          </div>
          {error && <p role="alert" className="mt-3 text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}
        </Modal>
      )}
    </>
  )
}

function AttentionLink({ queue, icon }: { queue: MobileCockpitQueue; icon: React.ReactNode }) {
  const tone: MobileCockpitTone = queue.count ? queue.tone : 'neutral'
  return (
    <Link to={focusHref(queue.key)} className="flex min-h-11 items-center gap-2 rounded-xl px-3 py-2" style={{ color: TONE_COLORS[tone], backgroundColor: TONE_BACKGROUNDS[tone], border: `1px solid ${queue.count ? TONE_COLORS[tone] : 'var(--ms-border)'}` }}>
      {icon}
      <span className="min-w-0 flex-1 truncate text-sm font-semibold">{queue.label}</span>
      <strong className="text-base tabular-nums">{queue.count}</strong>
    </Link>
  )
}

export function MobileTodayWorkspace({ data, poolCount, isFetching }: { data: MobileCockpit; poolCount: number; isFetching: boolean }) {
  const late = queueFor(data, 'late')
  const today = queueFor(data, 'today')
  const inField = queueFor(data, 'in_field')
  const unassigned = queueFor(data, 'unassigned')
  const unscheduled = queueFor(data, 'unscheduled')
  const onHold = queueFor(data, 'on_hold')
  const lateIds = new Set(late?.items.map(job => job.id) ?? [])
  const runSheet = uniqueJobs([late, inField, today]).sort(jobSort)
  const attentionQueues = [late, unassigned, unscheduled, onHold].filter((queue): queue is MobileCockpitQueue => Boolean(queue))
  const attentionCount = attentionQueues.reduce((sum, queue) => sum + queue.count, 0)
  const collected = data.metrics.find(metric => metric.key === 'collected')?.current ?? 0
  const completed = data.metrics.find(metric => metric.key === 'jobs_completed')?.current ?? 0

  return (
    <div className="space-y-4 md:hidden">
      <header>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--ms-accent)' }}>Today</p>
            <h2 className="mt-1 text-2xl font-extrabold" style={{ color: 'var(--ms-text)' }}>
              {new Date(`${data.as_of}T00:00:00`).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'short' })}
            </h2>
          </div>
          <span className="mt-1 text-xs" aria-live="polite" style={{ color: 'var(--ms-text-muted)' }}>{isFetching ? 'Refreshing…' : 'Live'}</span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <div className="rounded-xl px-3 py-2" style={{ backgroundColor: attentionCount ? TONE_BACKGROUNDS.warn : 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            <p className="text-xl font-extrabold tabular-nums" style={{ color: attentionCount ? TONE_COLORS.warn : 'var(--ms-text)' }}>{attentionCount}</p>
            <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>action flags</p>
          </div>
          <div className="rounded-xl px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            <p className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--ms-text)' }}>{today?.count ?? 0}</p>
            <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>booked today</p>
          </div>
          <div className="rounded-xl px-3 py-2" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            <p className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--ms-text)' }}>{inField?.count ?? 0}</p>
            <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>in the field</p>
          </div>
        </div>
      </header>

      <nav aria-label="Today shortcuts" className="grid grid-cols-3 gap-2">
        <Link to="/auto-key?view=dispatch" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl text-sm font-semibold" style={{ color: 'var(--ms-text)', backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}><Route size={16} /> Planner</Link>
        <Link to="/auto-key?view=map" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl text-sm font-semibold" style={{ color: 'var(--ms-text)', backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}><MapPinned size={16} /> Map</Link>
        <Link to="/auto-key/pool" className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl text-sm font-semibold" style={{ color: 'var(--ms-text)', backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}><Radio size={16} /> Pool{poolCount ? ` ${poolCount}` : ''}</Link>
      </nav>

      <section aria-labelledby="mobile-attention-heading">
        <div className="mb-2 flex items-center gap-2">
          <AlertTriangle size={17} style={{ color: attentionCount ? TONE_COLORS.warn : TONE_COLORS.good }} />
          <h3 id="mobile-attention-heading" className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Needs action</h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {late && <AttentionLink queue={late} icon={<Clock3 size={16} />} />}
          {unassigned && <AttentionLink queue={unassigned} icon={<UserRoundX size={16} />} />}
          {unscheduled && <AttentionLink queue={unscheduled} icon={<BriefcaseBusiness size={16} />} />}
          {onHold && <AttentionLink queue={onHold} icon={<AlertTriangle size={16} />} />}
        </div>
      </section>

      <section aria-labelledby="mobile-run-sheet-heading">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Route size={17} style={{ color: 'var(--ms-accent)' }} />
            <h3 id="mobile-run-sheet-heading" className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Run sheet</h3>
          </div>
          <Link to={focusHref('today')} className="text-sm font-semibold" style={{ color: 'var(--ms-accent)' }}>View list</Link>
        </div>
        {runSheet.length ? (
          <div className="space-y-3">
            {runSheet.map(job => <MobileJobCard key={job.id} job={job} data={data} lateIds={lateIds} />)}
          </div>
        ) : (
          <Card className="p-5 text-center">
            <CheckCircle2 size={26} className="mx-auto" style={{ color: TONE_COLORS.good }} />
            <p className="mt-2 font-semibold" style={{ color: 'var(--ms-text)' }}>No field jobs waiting</p>
            <p className="mt-1 text-sm" style={{ color: 'var(--ms-text-muted)' }}>Today’s scheduled and active jobs will appear here.</p>
          </Card>
        )}
      </section>

      {unassigned && unassigned.items.length > 0 && (
        <section aria-labelledby="mobile-dispatch-heading">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 id="mobile-dispatch-heading" className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Needs dispatch</h3>
            <Link to={focusHref('unassigned')} className="text-sm font-semibold" style={{ color: 'var(--ms-accent)' }}>All {unassigned.count}</Link>
          </div>
          <Card className="overflow-hidden">
            {unassigned.items.slice(0, 4).map(job => (
              <Link key={job.id} to={`/auto-key/${job.id}`} className="flex min-h-14 items-center gap-3 px-4 py-3 active:bg-[var(--ms-hover)]" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>#{job.job_number} · {job.customer_name ?? job.title}</p>
                  <p className="truncate text-xs" style={{ color: 'var(--ms-text-muted)' }}>{formatShopDay(job.scheduled_at, data.timezone, data.as_of)} · {mobileStatusLabel(job.status)}</p>
                </div>
                <ChevronRight size={16} style={{ color: 'var(--ms-text-muted)' }} />
              </Link>
            ))}
          </Card>
        </section>
      )}

      <section aria-labelledby="mobile-pulse-heading">
        <div className="mb-2 flex items-center gap-2">
          <BriefcaseBusiness size={17} style={{ color: 'var(--ms-accent)' }} />
          <h3 id="mobile-pulse-heading" className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Week at a glance</h3>
        </div>
        <Link to="/auto-key?view=reports" className="grid grid-cols-3 gap-2 rounded-xl p-3" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
          <div><p className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>{formatCents(collected)}</p><p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>collected</p></div>
          <div><p className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>{completed}</p><p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>completed</p></div>
          <div className="flex items-start justify-between gap-1"><div><p className="text-base font-bold" style={{ color: data.outstanding.current ? TONE_COLORS.warn : 'var(--ms-text)' }}>{formatCents(data.outstanding.current)}</p><p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>outstanding</p></div><ChevronRight size={15} style={{ color: 'var(--ms-text-muted)' }} /></div>
        </Link>
      </section>
    </div>
  )
}
