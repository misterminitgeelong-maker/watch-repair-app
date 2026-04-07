import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search, X } from 'lucide-react'
import {
  DEFAULT_PAGE_SIZE,
  deleteJob,
  getApiErrorMessage,
  listJobs,
  listQuotes,
  listUsers,
  updateJobStatus,
  type JobStatus,
  type RepairJob,
  type SortDir,
} from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge, Modal } from '@/components/ui'
import { formatDate, STATUS_LABELS, ACTIVE_DIRECTORY_STATUSES, CLOSED_DIRECTORY_STATUSES, JOB_STATUS_ORDER } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'
import { flattenInfinitePages, useOffsetPaginatedQuery } from '@/hooks/useOffsetPaginatedQuery'

function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

const ALL_STATUS_OPTIONS: JobStatus[] = [...JOB_STATUS_ORDER]

const JOB_SORT_FIELDS = ['created_at', 'job_number', 'status', 'priority'] as const
type JobSortField = (typeof JOB_SORT_FIELDS)[number]

export default function JobsPage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [jobToDelete, setJobToDelete] = useState<RepairJob | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [updatingJobId, setUpdatingJobId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>('active')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<JobSortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [assignedUserId, setAssignedUserId] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)

  const apiStatus = statusFilter === 'all' ? undefined : statusFilter

  const jobsQuery = useOffsetPaginatedQuery({
    queryKey: ['jobs', 'paged', apiStatus, assignedUserId || null, sortBy, sortDir],
    queryFn: (offset) =>
      listJobs({
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: sortBy,
        sort_dir: sortDir,
        ...(apiStatus ? { status: apiStatus } : {}),
        ...(assignedUserId ? { assigned_user_id: assignedUserId } : {}),
      }).then((r) => r.data),
  })

  const quotesQuery = useOffsetPaginatedQuery({
    queryKey: ['quotes', 'paged', 'jobs-page'],
    queryFn: (offset) =>
      listQuotes(undefined, {
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: 'created_at',
        sort_dir: 'desc',
      }).then((r) => r.data),
  })

  const { data: usersForAssignee } = useQuery({
    queryKey: ['users', 'jobs-filter'],
    queryFn: () => listUsers().then((r) => r.data),
  })

  const jobs = useMemo(() => flattenInfinitePages(jobsQuery.data), [jobsQuery.data])
  const quotes = useMemo(() => flattenInfinitePages(quotesQuery.data), [quotesQuery.data])

  const isLoading = jobsQuery.isLoading
  const listError = jobsQuery.error ?? quotesQuery.error

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

  const filtered = jobs.filter(j => {
    const q = search.toLowerCase()
    const matchSearch = !q || j.title.toLowerCase().includes(q) || j.job_number.includes(q) || (j.customer_name ?? '').toLowerCase().includes(q)
    const inDirectory = jobDirectoryView === 'active'
      ? !(CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)
      : (CLOSED_DIRECTORY_STATUSES as readonly JobStatus[]).includes(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    return matchSearch && inDirectory && matchStatus
  })

  async function handleLoadMore() {
    const tasks: Promise<unknown>[] = []
    if (jobsQuery.hasNextPage) tasks.push(jobsQuery.fetchNextPage())
    if (quotesQuery.hasNextPage) tasks.push(quotesQuery.fetchNextPage())
    await Promise.all(tasks)
  }

  const showLoadMore = jobsQuery.hasNextPage ?? false
  const loadMoreBusy = jobsQuery.isFetchingNextPage || quotesQuery.isFetchingNextPage

  const showSwitchToCompletedHint =
    !isLoading &&
    jobDirectoryView === 'active' &&
    statusFilter === 'all' &&
    !search.trim() &&
    filtered.length === 0 &&
    completedCount > 0

  return (
    <div>
      <PageHeader
        title="Watch Repairs"
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

      <p className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
        Movement services, batteries, pressure testing, and full servicing.
      </p>

      <div className="mb-5 flex items-center gap-2">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <span
            className="px-3 py-1.5 text-xs font-semibold rounded-md"
            style={{ backgroundColor: 'var(--cafe-paper)', color: 'var(--cafe-text)' }}
          >
            Jobs
          </span>
          <Link
            to="/catalogue"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{
              backgroundColor: 'transparent',
              color: 'var(--cafe-text-muted)',
              textDecoration: 'none',
            }}
          >
            Catalogue
          </Link>
        </div>
      </div>

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

      <div className="mb-5">
        {/* Search + filter toggle row */}
        <div className="flex gap-2 mb-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
            <input
              className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
              style={{
                backgroundColor: 'var(--cafe-surface)',
                border: '1px solid var(--cafe-border-2)',
                color: 'var(--cafe-text)',
              }}
              placeholder="Search by title, job #, or customer…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          {/* Filters toggle — mobile only */}
          <button
            type="button"
            onClick={() => setShowFilters(f => !f)}
            className="sm:hidden flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-sm font-medium transition"
            style={{
              backgroundColor: showFilters ? 'var(--cafe-amber)' : 'var(--cafe-surface)',
              border: '1px solid var(--cafe-border-2)',
              color: showFilters ? '#2C1810' : 'var(--cafe-text-muted)',
              whiteSpace: 'nowrap',
            }}
            aria-expanded={showFilters}
          >
            Filters{(statusFilter !== 'all' || sortBy !== 'created_at' || sortDir !== 'desc' || assignedUserId) ? ' ·' : ''}
          </button>
        </div>

        {/* Secondary filters — always visible on sm+, toggle on mobile */}
        <div className={`flex gap-3 flex-wrap ${showFilters ? 'flex' : 'hidden'} sm:flex`}>
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
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              border: '1px solid var(--cafe-border-2)',
              color: 'var(--cafe-text)',
            }}
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
            style={{
              backgroundColor: 'var(--cafe-surface)',
              border: '1px solid var(--cafe-border-2)',
              color: 'var(--cafe-text)',
            }}
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value as SortDir)}
            aria-label="Sort direction"
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
          <select
            className="w-full sm:w-auto rounded-lg px-3 py-2.5 text-base sm:text-sm outline-none transition"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              border: '1px solid var(--cafe-border-2)',
              color: 'var(--cafe-text)',
            }}
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
        </div>
      </div>

      {(showLoadMore || jobs.length > 0) && (
        <p className="text-xs mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
          {showLoadMore
            ? 'More jobs exist on the server — use Load more to fetch the next batch. Totals above reflect loaded rows only until you load everything.'
            : 'All matching jobs loaded for this filter.'}
        </p>
      )}

      {listError && (
        <p className="text-sm mb-3" style={{ color: '#C96A5A' }}>
          {getApiErrorMessage(listError, 'Could not load jobs or quotes.')}
        </p>
      )}

      {isLoading ? <Spinner /> : (
        filtered.length === 0 ? (
          <Card>
            {showSwitchToCompletedHint ? (
              <div className="py-10 px-4 text-center space-y-4 max-w-lg mx-auto">
                <p className="text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                  No jobs in the Active board.
                </p>
                <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
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
                                {j.customer_name && (
                                  <p className="text-xs mt-0.5 font-medium" style={{ color: 'var(--cafe-text-mid)' }}>{j.customer_name}</p>
                                )}
                                <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
                                  #{j.job_number} · {formatDate(j.created_at)}
                                </p>
                                {(() => {
                                  const days = daysInShop(j.created_at)
                                  const color = days >= 14 ? '#8B3A3A' : days >= 7 ? '#9B4E0F' : 'var(--cafe-text-muted)'
                                  const bg = days >= 14 ? '#FCE8E8' : days >= 7 ? '#FDE8D4' : 'var(--cafe-bg)'
                                  return (
                                    <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: bg, color }}>
                                      {days}d in shop
                                    </span>
                                  )
                                })()}
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
                              {j.collection_date && (
                                <span style={{ color: new Date(j.collection_date) < new Date() ? '#8B3A3A' : 'var(--cafe-text-mid)' }}>
                                  Due: {j.collection_date}
                                </span>
                              )}
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

      {showLoadMore && (
        <div className="mt-6 flex justify-center">
          <Button variant="secondary" onClick={() => void handleLoadMore()} disabled={loadMoreBusy}>
            {loadMoreBusy ? 'Loading…' : 'Load more jobs'}
          </Button>
        </div>
      )}

      {/* Mobile FAB */}
      <button
        type="button"
        onClick={() => setShowAdd(true)}
        className="sm:hidden fixed bottom-20 right-5 z-30 flex items-center gap-2 rounded-full px-5 py-3.5 text-sm font-semibold shadow-lg"
        style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810', boxShadow: '0 4px 16px rgba(140,95,15,0.35)' }}
        aria-label="New job ticket"
      >
        <Plus size={18} />New Job
      </button>

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
