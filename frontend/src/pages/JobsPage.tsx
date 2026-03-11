import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { listJobs, listQuotes, submitJobIntake, updateJobStatus, type JobStatus, type RepairJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge, Input, Textarea, Modal } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const JOB_STATUSES: JobStatus[] = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'parts_to_order', 'sent_to_labanda', 'quoted_by_labanda', 'awaiting_parts', 'working_on', 'completed', 'awaiting_collection']
const COMPLETED_DIRECTORY_STATUSES: JobStatus[] = ['completed', 'awaiting_collection', 'collected']
const NON_ACTIVE_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]
const ACTIVE_DIRECTORY_STATUSES: JobStatus[] = JOB_STATUSES.filter(s => !NON_ACTIVE_STATUSES.includes(s))
const CLOSED_DIRECTORY_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]
const ALL_STATUS_OPTIONS: JobStatus[] = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'service',
  'completed',
  'awaiting_collection',
  'collected',
  'no_go',
]

const STATUS_OPTION_LABELS: Record<JobStatus, string> = {
  awaiting_quote: 'Awaiting Quote',
  awaiting_go_ahead: 'Awaiting Go Ahead',
  go_ahead: 'Go Ahead Given',
  no_go: 'No Go',
  working_on: 'Started Work',
  awaiting_parts: 'Awaiting Parts',
  parts_to_order: 'Parts Ordered',
  sent_to_labanda: 'Sent to Labanda',
  quoted_by_labanda: 'Quoted by Labanda',
  service: 'Service',
  completed: 'Work Completed',
  awaiting_collection: 'Ready for Collection',
  collected: 'Collected',
}

function TicketInModal({ job, onClose }: { job: RepairJob; onClose: () => void }) {
  const qc = useQueryClient()
  const [preQuote, setPreQuote] = useState(job.pre_quote_cents > 0 ? (job.pre_quote_cents / 100).toFixed(2) : '')
  const [intakeNotes, setIntakeNotes] = useState('')
  const [hasScratches, setHasScratches] = useState(false)
  const [hasDents, setHasDents] = useState(false)
  const [hasCrackedCrystal, setHasCrackedCrystal] = useState(false)
  const [crownMissing, setCrownMissing] = useState(false)
  const [strapDamage, setStrapDamage] = useState(false)

  const mut = useMutation({
    mutationFn: () =>
      submitJobIntake(job.id, {
        intake_notes: intakeNotes || undefined,
        pre_quote_cents: preQuote ? Math.round(parseFloat(preQuote) * 100) : 0,
        has_scratches: hasScratches,
        has_dents: hasDents,
        has_cracked_crystal: hasCrackedCrystal,
        crown_missing: crownMissing,
        strap_damage: strapDamage,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['job', job.id] })
      onClose()
    },
  })

  return (
    <Modal title={`Ticket In · #${job.job_number}`} onClose={onClose}>
      <div className="space-y-4">
        <Input
          label="Pre-Quote ($)"
          type="number"
          min="0"
          step="0.01"
          value={preQuote}
          onChange={(e) => setPreQuote(e.target.value)}
          placeholder="0.00"
        />

        <div>
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Condition checklist</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
            <label className="flex items-center gap-2"><input type="checkbox" checked={hasScratches} onChange={(e) => setHasScratches(e.target.checked)} /> Scratches</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={hasDents} onChange={(e) => setHasDents(e.target.checked)} /> Dents</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={hasCrackedCrystal} onChange={(e) => setHasCrackedCrystal(e.target.checked)} /> Cracked crystal</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={crownMissing} onChange={(e) => setCrownMissing(e.target.checked)} /> Crown missing</label>
            <label className="flex items-center gap-2 sm:col-span-2"><input type="checkbox" checked={strapDamage} onChange={(e) => setStrapDamage(e.target.checked)} /> Strap damage</label>
          </div>
        </div>

        <Textarea
          label="Intake notes"
          rows={3}
          value={intakeNotes}
          onChange={(e) => setIntakeNotes(e.target.value)}
          placeholder="Anything the team should know before quoting/repairing."
        />

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>{mut.isPending ? 'Saving…' : 'Save ticket in'}</Button>
        </div>
      </div>
    </Modal>
  )
}

export default function JobsPage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [ticketInJob, setTicketInJob] = useState<RepairJob | null>(null)
  const [updatingJobId, setUpdatingJobId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>('active')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const { data: jobs, isLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })
  const { data: quotes } = useQuery({ queryKey: ['quotes'], queryFn: () => listQuotes().then(r => r.data) })

  const latestQuoteByJob = new Map<string, number>()
  for (const q of quotes ?? []) {
    const existing = latestQuoteByJob.get(q.repair_job_id)
    if (existing === undefined || q.total_cents > existing) {
      latestQuoteByJob.set(q.repair_job_id, q.total_cents)
    }
  }

  const displayQuoteCents = (job: RepairJob) => {
    if (job.cost_cents > 0) return job.cost_cents
    if (job.pre_quote_cents > 0) return job.pre_quote_cents
    return latestQuoteByJob.get(job.id) ?? 0
  }

  const activeCount = (jobs ?? []).filter(j => !CLOSED_DIRECTORY_STATUSES.includes(j.status)).length
  const completedCount = (jobs ?? []).filter(j => CLOSED_DIRECTORY_STATUSES.includes(j.status)).length
  const statusOptions = jobDirectoryView === 'active' ? ACTIVE_DIRECTORY_STATUSES : CLOSED_DIRECTORY_STATUSES

  const statusMut = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: JobStatus }) => updateJobStatus(jobId, status),
    onMutate: ({ jobId }) => setUpdatingJobId(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onSettled: () => setUpdatingJobId(null),
  })

  const filtered = (jobs ?? []).filter(j => {
    const matchSearch = j.title.toLowerCase().includes(search.toLowerCase()) || j.job_number.includes(search)
    const inDirectory = jobDirectoryView === 'active'
      ? !CLOSED_DIRECTORY_STATUSES.includes(j.status)
      : CLOSED_DIRECTORY_STATUSES.includes(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    return matchSearch && inDirectory && matchStatus
  })

  return (
    <div>
      <PageHeader title="Repair Jobs" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} />New Job Ticket</Button>} />
      {showAdd && <NewJobModal onClose={() => setShowAdd(false)} />}
      {ticketInJob && <TicketInModal job={ticketInJob} onClose={() => setTicketInJob(null)} />}

      <div className="mb-5 flex items-center justify-between gap-3 flex-wrap">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <button
            type="button"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{
              backgroundColor: jobDirectoryView === 'active' ? 'var(--cafe-paper)' : 'transparent',
              color: jobDirectoryView === 'active' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
            onClick={() => {
              setJobDirectoryView('active')
              setStatusFilter('all')
            }}
          >
            Active ({activeCount})
          </button>
          <button
            type="button"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{
              backgroundColor: jobDirectoryView === 'completed' ? 'var(--cafe-paper)' : 'transparent',
              color: jobDirectoryView === 'completed' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
            onClick={() => {
              setJobDirectoryView('completed')
              setStatusFilter('all')
            }}
          >
            Completed ({completedCount})
          </button>
        </div>
      </div>

      <div className="flex gap-3 mb-5 flex-wrap">
        <div className="relative w-full sm:w-auto">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            className="w-full sm:w-auto pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              border: '1px solid var(--cafe-border-2)',
              color: 'var(--cafe-text)',
            }}
            placeholder="Search jobs…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1px solid var(--cafe-border-2)',
            color: 'var(--cafe-text)',
          }}
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
        >
          <option value="all">All in {jobDirectoryView === 'active' ? 'active' : 'completed'}</option>
          {statusOptions.map(s => <option key={s} value={s}>{STATUS_OPTION_LABELS[s]}</option>)}
        </select>
      </div>

      {isLoading ? <Spinner /> : (
        filtered.length === 0 ? (
          <Card>
            <EmptyState message="No jobs found." />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {statusOptions
              .filter(s => statusFilter === 'all' || s === statusFilter)
              .map((status) => {
                const jobsInStatus = filtered.filter(j => j.status === status)
                return (
                  <Card key={status} className="overflow-hidden">
                    <div
                      className="px-4 py-3.5 flex items-center justify-between"
                      style={{ borderBottom: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
                    >
                      <p className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {STATUS_OPTION_LABELS[status]}
                      </p>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ backgroundColor: '#EEE6DA', color: 'var(--cafe-text-mid)' }}>
                        {jobsInStatus.length}
                      </span>
                    </div>

                    <div>
                      {jobsInStatus.length === 0 ? (
                        <p className="px-4 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                          No jobs in this stage.
                        </p>
                      ) : (
                        jobsInStatus.map((j, i) => (
                          <div
                            key={j.id}
                            className="px-4 py-3"
                            style={{ borderBottom: i < jobsInStatus.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <Link to={`/jobs/${j.id}`} className="text-sm font-medium hover:underline" style={{ color: 'var(--cafe-amber)' }}>
                                  {j.title}
                                </Link>
                                <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
                                  #{j.job_number} · {formatDate(j.created_at)}
                                </p>
                              </div>
                              <Badge status={j.status} />
                            </div>

                            <div className="mt-2 flex items-center justify-between text-xs" style={{ color: 'var(--cafe-text-mid)' }}>
                              <span className="capitalize">Priority: {j.priority}</span>
                              <span>Quote: ${(displayQuoteCents(j) / 100).toFixed(2)}</span>
                            </div>

                            <div className="mt-2">
                              <select
                                className="w-full rounded-md px-2.5 py-2 text-xs outline-none transition"
                                style={{
                                  backgroundColor: 'var(--cafe-surface)',
                                  border: '1px solid var(--cafe-border-2)',
                                  color: 'var(--cafe-text-mid)',
                                }}
                                value={j.status}
                                onChange={(e) => statusMut.mutate({ jobId: j.id, status: e.target.value as JobStatus })}
                                disabled={updatingJobId === j.id}
                              >
                                {ALL_STATUS_OPTIONS.map(s => (
                                  <option key={s} value={s}>{STATUS_OPTION_LABELS[s]}</option>
                                ))}
                              </select>
                            </div>

                            {!CLOSED_DIRECTORY_STATUSES.includes(j.status) && (
                              <div className="mt-2">
                                <Button className="w-full justify-center" variant="secondary" onClick={() => setTicketInJob(j)}>
                                  Ticket In
                                </Button>
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </Card>
                )
              })}
          </div>
        )
      )}
    </div>
  )
}
