import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search, X } from 'lucide-react'
import { deleteJob, getApiErrorMessage, listJobs, listQuotes, updateJobStatus, type JobStatus, type RepairJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge, Modal } from '@/components/ui'
import { formatDate, STATUS_LABELS, ACTIVE_DIRECTORY_STATUSES, CLOSED_DIRECTORY_STATUSES, JOB_STATUS_ORDER } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const ALL_STATUS_OPTIONS: JobStatus[] = [...JOB_STATUS_ORDER]

export default function JobsPage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [jobToDelete, setJobToDelete] = useState<RepairJob | null>(null)
  const [deleteError, setDeleteError] = useState('')
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

  const activeCount = (jobs ?? []).filter(j => !(CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)).length
  const completedCount = (jobs ?? []).filter(j => (CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)).length
  const statusOptions = jobDirectoryView === 'active' ? [...ACTIVE_DIRECTORY_STATUSES] : [...CLOSED_DIRECTORY_STATUSES]

  const statusMut = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: JobStatus }) => updateJobStatus(jobId, status),
    onMutate: ({ jobId }) => setUpdatingJobId(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onSettled: () => setUpdatingJobId(null),
  })

  const deleteMut = useMutation({
    mutationFn: (jobId: string) => deleteJob(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['quotes'] })
      setJobToDelete(null)
      setDeleteError('')
    },
    onError: (err) => {
      setDeleteError(getApiErrorMessage(err, 'Failed to delete job.'))
    },
  })

  const filtered = (jobs ?? []).filter(j => {
    const matchSearch = j.title.toLowerCase().includes(search.toLowerCase()) || j.job_number.includes(search)
    const inDirectory = jobDirectoryView === 'active'
      ? !(CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)
      : (CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    return matchSearch && inDirectory && matchStatus
  })

  return (
    <div>
      <PageHeader
        title="Repair Jobs"
        action={
          <div className="flex flex-col items-end gap-1">
            <Button onClick={() => setShowAdd(true)}><Plus size={16} />New Job Ticket</Button>
            <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              After create, you can print tickets from the desktop flow.
            </span>
          </div>
        }
      />
      {showAdd && <NewJobModal onClose={() => setShowAdd(false)} />}

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
          {statusOptions.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
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
                        {STATUS_LABELS[status]}
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
                                {j.customer_account_id && (
                                  <p className="text-[11px] mt-1 inline-flex items-center rounded-full px-2 py-0.5 font-semibold" style={{ backgroundColor: '#EAF4EA', color: '#2F6A3D' }}>
                                    B2B
                                  </p>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge status={j.status} />
                                <button
                                  type="button"
                                  aria-label={`Delete job ${j.job_number}`}
                                  onClick={() => {
                                    setDeleteError('')
                                    setJobToDelete(j)
                                  }}
                                  className="h-7 w-7 rounded-full flex items-center justify-center transition-colors"
                                  style={{ color: '#A4664A', border: '1px solid #E7C6B7', backgroundColor: '#FFF7F3' }}
                                >
                                  <X size={14} />
                                </button>
                              </div>
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
                                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                                ))}
                              </select>
                            </div>
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

      {jobToDelete && (
        <Modal
          title="Delete Job"
          onClose={() => {
            if (!deleteMut.isPending) {
              setJobToDelete(null)
              setDeleteError('')
            }
          }}
        >
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--cafe-text)' }}>
              Are you sure you want to delete this job?
            </p>
            <div className="rounded-lg px-3 py-2" style={{ border: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
              <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                #{jobToDelete.job_number} · {jobToDelete.title}
              </p>
            </div>
            <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              This action cannot be undone.
            </p>
            {deleteError && <p className="text-sm" style={{ color: '#C96A5A' }}>{deleteError}</p>}
            <div className="flex gap-2 pt-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setJobToDelete(null)
                  setDeleteError('')
                }}
                className="flex-1"
                disabled={deleteMut.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => deleteMut.mutate(jobToDelete.id)}
                className="flex-1"
                disabled={deleteMut.isPending}
              >
                {deleteMut.isPending ? 'Deleting…' : 'Delete Job'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
