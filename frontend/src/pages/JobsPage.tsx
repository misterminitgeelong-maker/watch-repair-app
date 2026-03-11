import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { listJobs, submitJobIntake, type JobStatus, type RepairJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge, Input, Textarea, Modal } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const JOB_STATUSES: JobStatus[] = ['awaiting_go_ahead', 'go_ahead', 'no_go', 'working_on', 'awaiting_parts', 'parts_to_order', 'sent_to_labanda', 'service', 'completed', 'awaiting_collection', 'collected']
const COMPLETED_DIRECTORY_STATUSES: JobStatus[] = ['completed', 'awaiting_collection', 'collected']
const NON_ACTIVE_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]
const ACTIVE_DIRECTORY_STATUSES: JobStatus[] = JOB_STATUSES.filter(s => !NON_ACTIVE_STATUSES.includes(s))
const CLOSED_DIRECTORY_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]

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
  const [showAdd, setShowAdd] = useState(false)
  const [ticketInJob, setTicketInJob] = useState<RepairJob | null>(null)
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>('active')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const { data: jobs, isLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })

  const activeCount = (jobs ?? []).filter(j => !CLOSED_DIRECTORY_STATUSES.includes(j.status)).length
  const completedCount = (jobs ?? []).filter(j => CLOSED_DIRECTORY_STATUSES.includes(j.status)).length
  const statusOptions = jobDirectoryView === 'active' ? ACTIVE_DIRECTORY_STATUSES : CLOSED_DIRECTORY_STATUSES

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
          {statusOptions.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
        </select>
      </div>

      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No jobs found." /> : (
            <>
            <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
              {filtered.map((j) => (
                <div key={j.id} className="p-4 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/jobs/${j.id}`} className="font-medium" style={{ color: 'var(--cafe-amber)' }}>{j.title}</Link>
                    <Badge status={j.status} />
                  </div>
                  <div className="flex items-center justify-between text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                    <span>#{j.job_number}</span>
                    <span>{formatDate(j.created_at)}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs" style={{ color: 'var(--cafe-text-mid)' }}>
                    <span className="capitalize">Priority: {j.priority}</span>
                    <span>Pre-quote: ${(j.pre_quote_cents / 100).toFixed(2)}</span>
                  </div>
                  {!CLOSED_DIRECTORY_STATUSES.includes(j.status) && (
                    <div className="pt-1">
                      <Button className="w-full justify-center" variant="secondary" onClick={() => setTicketInJob(j)}>Ticket In</Button>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <table className="w-full text-sm hidden md:table">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  {['Job #', 'Title', 'Status', 'Priority', 'Pre-Quote', 'Created', 'Actions'].map(h => (
                    <th
                      key={h}
                      className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase"
                      style={{ color: 'var(--cafe-text-muted)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((j: RepairJob, i) => (
                  <tr
                    key={j.id}
                    style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td className="px-5 py-3.5 font-mono text-xs" style={{ color: 'var(--cafe-text-muted)' }}>#{j.job_number}</td>
                    <td className="px-5 py-3.5">
                      <Link
                        to={`/jobs/${j.id}`}
                        className="font-medium hover:underline"
                        style={{ color: 'var(--cafe-amber)' }}
                      >
                        {j.title}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5"><Badge status={j.status} /></td>
                    <td className="px-5 py-3.5">
                      <span
                        className="text-xs font-medium capitalize"
                        style={{
                          color: j.priority === 'urgent' ? '#8B3A3A'
                               : j.priority === 'high'   ? '#9B4E0F'
                               : 'var(--cafe-text-mid)',
                        }}
                      >
                        {j.priority}
                      </span>
                    </td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>${(j.pre_quote_cents / 100).toFixed(2)}</td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(j.created_at)}</td>
                    <td className="px-5 py-3.5">
                      {!CLOSED_DIRECTORY_STATUSES.includes(j.status) && (
                        <Button variant="secondary" onClick={() => setTicketInJob(j)}>Ticket In</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </>
          )}
        </Card>
      )}
    </div>
  )
}
