import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Search, X, ListOrdered } from 'lucide-react'
import {
  deleteJob,
  getApiErrorMessage,
  listJobs,
  listQuotes,
  listUsers,
  updateJobStatus,
  WATCH_JOBS_LIST_MAX,
  type JobStatus,
  type RepairJob,
  type SortDir,
} from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge, Modal, ViewToggle } from '@/components/ui'
import { formatDate, STATUS_LABELS, ACTIVE_DIRECTORY_STATUSES, CLOSED_DIRECTORY_STATUSES } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'
import RepairQueueModal from '@/components/RepairQueueModal'
import LogWorkModal from '@/components/LogWorkModal'
import { KanbanBoard, JobCard, WATCH_KANBAN_COLUMNS } from '@/components/kanban'

function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

function daysInCurrentStatus(job: { status: string; status_changed_at?: string | null; created_at: string }): number {
  const TERMINAL = new Set(['collected', 'no_go', 'awaiting_collection'])
  if (TERMINAL.has(job.status)) return 0
  const from = job.status_changed_at ?? job.created_at
  return Math.floor((Date.now() - new Date(from).getTime()) / 86_400_000)
}

const JOB_SORT_FIELDS = ['created_at', 'job_number', 'status', 'priority'] as const
type JobSortField = (typeof JOB_SORT_FIELDS)[number]
type BoardView = 'board' | 'list'

export default function JobsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialStatus = searchParams.get('status')
  const statusIsClosed = initialStatus != null && (CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(initialStatus as JobStatus)
  const initialCostOutlier = searchParams.get('cost_outlier') === '1' || searchParams.get('cost_outlier') === 'true'
  const initialOlderThanDays = Number.parseInt(searchParams.get('older_than_days') ?? '', 10)
  const initialPastCollectionOnly = searchParams.get('past_collection') === '1' || searchParams.get('past_collection') === 'true'
  const initialView: BoardView = searchParams.get('view') === 'list' ? 'list' : 'board'
  const [showAdd, setShowAdd] = useState(false)
  const [showQueue, setShowQueue] = useState(false)
  const [logWorkJobId, setLogWorkJobId] = useState<string | null>(null)
  const [jobToDelete, setJobToDelete] = useState<RepairJob | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [updatingJobId, setUpdatingJobId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>(statusIsClosed ? 'completed' : 'active')
  const [statusFilter, setStatusFilter] = useState<string>(initialStatus ?? 'all')
  const [sortBy, setSortBy] = useState<JobSortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [assignedUserId, setAssignedUserId] = useState<string>('')
  const [costOutlierOnly, setCostOutlierOnly] = useState(initialCostOutlier)
  const [olderThanDays, setOlderThanDays] = useState<number>(Number.isFinite(initialOlderThanDays) ? initialOlderThanDays : 0)
  const [pastCollectionOnly, setPastCollectionOnly] = useState(initialPastCollectionOnly)
  const [showFilters, setShowFilters] = useState(false)
  const [view, setView] = useState<BoardView>(initialView)

  const apiStatus = statusFilter === 'all' ? undefined : statusFilter

  const jobsQuery = useQuery({
    queryKey: ['jobs', 'all', apiStatus, assignedUserId || null, sortBy, sortDir, costOutlierOnly],
    queryFn: () =>
      listJobs({
        limit: WATCH_JOBS_LIST_MAX,
        offset: 0,
        sort_by: sortBy,
        sort_dir: sortDir,
        ...(apiStatus ? { status: apiStatus } : {}),
        ...(assignedUserId ? { assigned_user_id: assignedUserId } : {}),
        ...(costOutlierOnly ? { cost_outlier: true } : {}),
      }).then((r) => r.data),
  })

  const quotesQuery = useQuery({
    queryKey: ['quotes', 'all', 'jobs-page'],
    queryFn: () =>
      listQuotes(undefined, {
        limit: WATCH_JOBS_LIST_MAX,
        offset: 0,
        sort_by: 'created_at',
        sort_dir: 'desc',
      }).then((r) => r.data),
  })

  const { data: usersForAssignee } = useQuery({
    queryKey: ['users', 'jobs-filter'],
    queryFn: () => listUsers().then((r) => r.data),
  })

  const jobs = jobsQuery.data ?? []
  const quotes = quotesQuery.data ?? []

  const isLoading = jobsQuery.isLoading
  const listError = jobsQuery.error ?? quotesQuery.error

  const latestQuoteByJob = useMemo(() => {
    const map = new Map<string, number>()
    for (const q of quotes ?? []) {
      const existing = map.get(q.repair_job_id)
      if (existing === undefined || q.total_cents > existing) {
        map.set(q.repair_job_id, q.total_cents)
      }
    }
    return map
  }, [quotes])

  const displayQuoteCents = (job: RepairJob) => {
    if (job.cost_cents > 0) return job.cost_cents
    if (job.pre_quote_cents > 0) return job.pre_quote_cents
    return latestQuoteByJob.get(job.id) ?? 0
  }

  const assigneeName = useMemo(() => {
    const m = new Map<string, string>()
    for (const u of usersForAssignee ?? []) m.set(u.id, u.full_name)
    return m
  }, [usersForAssignee])

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

  const filtered = jobs.filter(j => {
    const q = search.toLowerCase()
    const matchSearch = !q || j.title.toLowerCase().includes(q) || j.job_number.includes(q) || (j.customer_name ?? '').toLowerCase().includes(q)
    const inDirectory = jobDirectoryView === 'active'
      ? !(CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)
      : (CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    const ageDays = daysInShop(j.created_at)
    const matchAge = olderThanDays > 0 ? ageDays >= olderThanDays : true
    const todayYmd = new Date().toISOString().slice(0, 10)
    const matchPastCollection = pastCollectionOnly ? !!j.collection_date && j.collection_date < todayYmd : true
    return matchSearch && inDirectory && matchStatus && matchAge && matchPastCollection
  })

  const showSwitchToCompletedHint =
    !isLoading &&
    jobDirectoryView === 'active' &&
    statusFilter === 'all' &&
    !search.trim() &&
    filtered.length === 0 &&
    completedCount > 0

  useEffect(() => {
    const next = new URLSearchParams()
    if (statusFilter !== 'all') next.set('status', statusFilter)
    if (costOutlierOnly) next.set('cost_outlier', '1')
    if (olderThanDays > 0) next.set('older_than_days', String(olderThanDays))
    if (pastCollectionOnly) next.set('past_collection', '1')
    if (view === 'list') next.set('view', 'list')
    setSearchParams(next, { replace: true })
  }, [costOutlierOnly, olderThanDays, pastCollectionOnly, setSearchParams, statusFilter, view])

  return (
    <div>
      <PageHeader
        title="Watch Repairs"
        action={
          <div className="flex items-center gap-2">
            {jobDirectoryView === 'active' && (
              <ViewToggle<BoardView>
                value={view}
                onChange={setView}
                options={[
                  { value: 'board', label: 'Board' },
                  { value: 'list', label: 'List' },
                ]}
              />
            )}
            <Button variant="secondary" onClick={() => setShowQueue(true)}><ListOrdered size={16} />Queue</Button>
            <Button onClick={() => setShowAdd(true)}><Plus size={16} />New Job Ticket</Button>
          </div>
        }
      />
      {showAdd && <NewJobModal onClose={() => setShowAdd(false)} />}
      {showQueue && <RepairQueueModal mode="watch" onClose={() => setShowQueue(false)} />}

      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
        Movement services, batteries, pressure testing, and full servicing.
      </p>

      <div className="mb-5 flex items-center gap-2">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: 'var(--ms-bg)' }}>
          <span
            className="px-3 py-1.5 text-xs font-semibold rounded-md"
            style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
          >
            Jobs
          </span>
          <Link
            to="/catalogue"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{ backgroundColor: 'transparent', color: 'var(--ms-text-muted)', textDecoration: 'none' }}
          >
            Catalogue
          </Link>
        </div>
      </div>

      <div className="mb-5 flex items-center justify-between gap-3 flex-wrap">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: 'var(--ms-bg)' }}>
          <button
            type="button"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{
              backgroundColor: jobDirectoryView === 'active' ? 'var(--ms-surface)' : 'transparent',
              color: jobDirectoryView === 'active' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
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
              backgroundColor: jobDirectoryView === 'completed' ? 'var(--ms-surface)' : 'transparent',
              color: jobDirectoryView === 'completed' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
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

      <div className="mb-5">
        <div className="flex gap-2 mb-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
            <input
              className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
              style={{
                backgroundColor: 'var(--ms-surface)',
                border: '1px solid var(--ms-border)',
                color: 'var(--ms-text)',
              }}
              placeholder="Search by title, job #, or customer…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <button
            type="button"
            onClick={() => setShowFilters(f => !f)}
            className="sm:hidden flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-sm font-medium transition"
            style={{
              backgroundColor: showFilters ? 'var(--ms-accent-light)' : 'var(--ms-surface)',
              border: '1px solid var(--ms-border)',
              color: showFilters ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
              whiteSpace: 'nowrap',
            }}
            aria-expanded={showFilters}
          >
            Filters{(statusFilter !== 'all' || sortBy !== 'created_at' || sortDir !== 'desc' || assignedUserId) ? ' ·' : ''}
          </button>
        </div>

        <div className={`flex gap-3 flex-wrap ${showFilters ? 'flex' : 'hidden'} sm:flex`}>
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="all">All in {jobDirectoryView === 'active' ? 'active' : 'completed'}</option>
            {statusOptions.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
          </select>
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as JobSortField)}
            aria-label="Sort jobs by"
          >
            <option value="created_at">Sort: Date in</option>
            <option value="job_number">Sort: Job #</option>
            <option value="status">Sort: Status</option>
            <option value="priority">Sort: Priority</option>
          </select>
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value as SortDir)}
            aria-label="Sort direction"
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            value={assignedUserId}
            onChange={(e) => setAssignedUserId(e.target.value)}
            aria-label="Filter by assignee"
          >
            <option value="">All assignees</option>
            {(usersForAssignee ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </select>
          <label
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition inline-flex items-center gap-2"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            <input type="checkbox" checked={costOutlierOnly} onChange={(e) => setCostOutlierOnly(e.target.checked)} />
            Cost outliers only
          </label>
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            value={String(olderThanDays)}
            onChange={(e) => setOlderThanDays(Number.parseInt(e.target.value, 10) || 0)}
            aria-label="Filter by minimum days in shop"
          >
            <option value="0">Any age</option>
            <option value="7">7+ days in shop</option>
            <option value="14">14+ days in shop</option>
            <option value="21">21+ days in shop</option>
          </select>
          <label
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition inline-flex items-center gap-2"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            <input type="checkbox" checked={pastCollectionOnly} onChange={(e) => setPastCollectionOnly(e.target.checked)} />
            Past collection date only
          </label>
        </div>
      </div>

      {jobs.length > 0 && !isLoading && (
        <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
          All matching jobs are loaded for this filter (up to {WATCH_JOBS_LIST_MAX.toLocaleString()} rows).
        </p>
      )}

      {listError && (
        <p className="text-sm mb-3" style={{ color: 'var(--ms-error)' }}>
          {getApiErrorMessage(listError, 'Could not load jobs or quotes.')}
        </p>
      )}

      {isLoading ? <Spinner /> : (
        filtered.length === 0 ? (
          <Card>
            {showSwitchToCompletedHint ? (
              <div className="py-10 px-4 text-center space-y-4 max-w-lg mx-auto">
                <p className="text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>
                  No jobs in the Active board.
                </p>
                <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
                  Rows with status <strong className="font-medium">Ready for collection</strong>,{' '}
                  <strong className="font-medium">Completed</strong>, or <strong className="font-medium">Collected</strong>{' '}
                  (common in imports and old exports) are grouped under <strong className="font-medium">Completed</strong>.
                </p>
                <Button
                  variant="secondary"
                  type="button"
                  onClick={() => {
                    setJobDirectoryView('completed')
                    setStatusFilter('all')
                  }}
                >
                  Open Completed ({completedCount})
                </Button>
              </div>
            ) : (
              <EmptyState message="No jobs found." />
            )}
          </Card>
        ) : (jobDirectoryView === 'completed' ? 'list' : view) === 'board' ? (
          <KanbanBoard
            jobs={filtered}
            columns={WATCH_KANBAN_COLUMNS}
            onStatusChange={(jobId, nextStatus) =>
              statusMut.mutate({ jobId, status: nextStatus as JobStatus })
            }
            renderCard={(job, column) => (
              <JobCard
                jobNumber={job.job_number}
                title={job.title}
                description={job.description ?? undefined}
                customerName={job.customer_name ?? undefined}
                customerPhone={job.customer_phone ?? undefined}
                priority={job.priority}
                daysInShop={daysInShop(job.created_at)}
                daysInCurrentStatus={daysInCurrentStatus(job)}
                quoteCents={displayQuoteCents(job)}
                techName={assigneeName.get(job.assigned_user_id ?? '') ?? null}
                techKey={job.assigned_user_id ?? null}
                accentColor={column.color}
                href={`/jobs/${job.id}`}
                draggable={!updatingJobId}
                onLogWork={() => setLogWorkJobId(job.id)}
                onDragStart={e => {
                  e.dataTransfer.setData('text/job-id', job.id)
                  e.dataTransfer.effectAllowed = 'move'
                }}
                extras={job.customer_account_id ? (
                  <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{ backgroundColor: '#EAF4EA', color: '#2F6A3D' }}>
                    B2B
                  </span>
                ) : null}
              />
            )}
          />
        ) : (
          <ListView
            jobs={filtered}
            displayQuoteCents={displayQuoteCents}
            assigneeName={assigneeName}
            onDelete={(job) => {
              setDeleteError('')
              setJobToDelete(job)
            }}
          />
        )
      )}

      <button
        type="button"
        onClick={() => setShowAdd(true)}
        className="sm:hidden fixed bottom-20 right-5 z-30 flex items-center gap-2 rounded-full px-5 py-3.5 text-sm font-semibold shadow-lg"
        style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', boxShadow: '0 4px 16px rgba(60,30,10,0.35)' }}
        aria-label="New job ticket"
      >
        <Plus size={18} />New Job
      </button>

      {logWorkJobId && (
        <LogWorkModal jobId={logWorkJobId} onClose={() => setLogWorkJobId(null)} />
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
            <p className="text-sm" style={{ color: 'var(--ms-text)' }}>
              Are you sure you want to delete this job?
            </p>
            <div className="rounded-lg px-3 py-2" style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
              <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                #{jobToDelete.job_number} · {jobToDelete.title}
              </p>
            </div>
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              This action cannot be undone.
            </p>
            {deleteError && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{deleteError}</p>}
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

function ListView({
  jobs,
  displayQuoteCents,
  assigneeName,
  onDelete,
}: {
  jobs: RepairJob[]
  displayQuoteCents: (j: RepairJob) => number
  assigneeName: Map<string, string>
  onDelete: (job: RepairJob) => void
}) {
  const today = new Date().toISOString().slice(0, 10)
  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--ms-surface-alt)', borderBottom: '1px solid var(--ms-border)' }}>
              <Th>#</Th>
              <Th>Watch &amp; Description</Th>
              <Th>Customer</Th>
              <Th>Status</Th>
              <Th>Priority</Th>
              <Th>Days</Th>
              <Th>Quote</Th>
              <Th>Collection</Th>
              <Th>Tech</Th>
              <Th>{''}</Th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j, idx) => {
              const days = daysInShop(j.created_at)
              const daysColor = days >= 14 ? 'var(--ms-error)' : days >= 7 ? '#9A5010' : 'var(--ms-text-mid)'
              const pastCollection = j.collection_date && j.collection_date < today
              const tech = assigneeName.get(j.assigned_user_id ?? '') ?? null
              return (
                <tr
                  key={j.id}
                  style={{
                    borderBottom: idx === jobs.length - 1 ? 'none' : '1px solid var(--ms-border)',
                    backgroundColor: 'var(--ms-surface)',
                  }}
                >
                  <Td>
                    <Link to={`/jobs/${j.id}`} style={{ color: 'var(--ms-accent)', fontWeight: 600, textDecoration: 'none' }}>
                      #{j.job_number}
                    </Link>
                  </Td>
                  <Td>
                    <div style={{ fontWeight: 600, color: 'var(--ms-text)' }}>{j.title}</div>
                    {j.description && (
                      <div style={{ fontSize: 11, color: 'var(--ms-text-muted)', marginTop: 2, maxWidth: 320 }}>
                        {j.description}
                      </div>
                    )}
                  </Td>
                  <Td style={{ color: 'var(--ms-text-mid)' }}>{j.customer_name ?? '—'}</Td>
                  <Td><Badge status={j.status} /></Td>
                  <Td style={{ textTransform: 'capitalize', color: 'var(--ms-text-mid)' }}>{j.priority}</Td>
                  <Td style={{ color: daysColor, fontWeight: 600 }}>{days}d</Td>
                  <Td style={{ color: 'var(--ms-text)', fontWeight: 600 }}>
                    ${(displayQuoteCents(j) / 100).toFixed(2)}
                  </Td>
                  <Td style={{ color: pastCollection ? 'var(--ms-error)' : 'var(--ms-text-mid)' }}>
                    {j.collection_date ? formatDate(j.collection_date) : '—'}
                  </Td>
                  <Td style={{ color: 'var(--ms-text-mid)' }}>{tech ?? '—'}</Td>
                  <Td>
                    <button
                      type="button"
                      aria-label={`Delete job ${j.job_number}`}
                      onClick={() => onDelete(j)}
                      className="h-7 w-7 rounded-full flex items-center justify-center"
                      style={{ color: 'var(--ms-error)', border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-surface)' }}
                    >
                      <X size={14} />
                    </button>
                  </Td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th
      style={{
        textAlign: 'left',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.10em',
        textTransform: 'uppercase',
        color: 'var(--ms-text-muted)',
        padding: '10px 14px',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </th>
  )
}

function Td({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <td style={{ padding: '12px 14px', verticalAlign: 'top', fontSize: 13, ...style }}>
      {children}
    </td>
  )
}
