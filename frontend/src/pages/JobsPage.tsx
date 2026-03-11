import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { listJobs, type JobStatus, type RepairJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge } from '@/components/ui'
import { formatDate, STATUS_LABELS } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const JOB_STATUSES: JobStatus[] = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'no_go', 'working_on', 'awaiting_parts', 'parts_to_order', 'sent_to_labanda', 'service', 'completed', 'awaiting_collection', 'collected']
const COMPLETED_DIRECTORY_STATUSES: JobStatus[] = ['completed', 'awaiting_collection', 'collected']
const NON_ACTIVE_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]
const ACTIVE_DIRECTORY_STATUSES: JobStatus[] = JOB_STATUSES.filter(s => !NON_ACTIVE_STATUSES.includes(s))
const CLOSED_DIRECTORY_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]

type SortKey = 'job_number' | 'status' | 'priority' | 'pre_quote_cents' | 'created_at'
type SortDir = 'asc' | 'desc'

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 }

function SortIcon({ col, sortBy, sortDir }: { col: SortKey; sortBy: SortKey; sortDir: SortDir }) {
  if (sortBy !== col) return <ChevronsUpDown size={12} className="inline ml-1 opacity-40" />
  return sortDir === 'asc' ? <ChevronUp size={12} className="inline ml-1" /> : <ChevronDown size={12} className="inline ml-1" />
}

export default function JobsPage() {
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>('active')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<SortKey>('job_number')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const { data: jobs, isLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })

  const activeCount = (jobs ?? []).filter(j => !CLOSED_DIRECTORY_STATUSES.includes(j.status)).length
  const completedCount = (jobs ?? []).filter(j => CLOSED_DIRECTORY_STATUSES.includes(j.status)).length
  const statusOptions = jobDirectoryView === 'active' ? ACTIVE_DIRECTORY_STATUSES : CLOSED_DIRECTORY_STATUSES

  function handleSort(col: SortKey) {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortBy(col); setSortDir('asc') }
  }

  const filtered = (jobs ?? []).filter(j => {
    const matchSearch = j.title.toLowerCase().includes(search.toLowerCase()) || j.job_number.includes(search)
    const inDirectory = jobDirectoryView === 'active'
      ? !CLOSED_DIRECTORY_STATUSES.includes(j.status)
      : CLOSED_DIRECTORY_STATUSES.includes(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    return matchSearch && inDirectory && matchStatus
  }).sort((a, b) => {
    let cmp = 0
    if (sortBy === 'job_number') cmp = a.job_number.localeCompare(b.job_number, undefined, { numeric: true })
    else if (sortBy === 'status') cmp = a.status.localeCompare(b.status)
    else if (sortBy === 'priority') cmp = (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9)
    else if (sortBy === 'pre_quote_cents') cmp = a.pre_quote_cents - b.pre_quote_cents
    else if (sortBy === 'created_at') cmp = a.created_at.localeCompare(b.created_at)
    return sortDir === 'asc' ? cmp : -cmp
  })

  return (
    <div>
      <PageHeader title="Repair Jobs" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} />New Job Ticket</Button>} />
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
          {statusOptions.map(s => <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>)}
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
                    <Link to={`/jobs/${j.id}`} className="font-medium font-mono text-xs" style={{ color: 'var(--cafe-amber)' }}>#{j.job_number}</Link>
                    <Badge status={j.status} />
                  </div>
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{j.title}</p>
                  <div className="flex items-center justify-between text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                    <span>{formatDate(j.created_at)}</span>
                    <span>Quote: ${(j.pre_quote_cents / 100).toFixed(2)}</span>
                  </div>
                  <div className="flex items-center text-xs" style={{ color: 'var(--cafe-text-mid)' }}>
                    <span className="capitalize">Priority: {j.priority}</span>
                  </div>
                </div>
              ))}
            </div>

            <table className="w-full text-sm hidden md:table">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  {([
                    { key: 'job_number' as SortKey, label: 'Job #' },
                    { key: null, label: 'Watch / Title' },
                    { key: 'status' as SortKey, label: 'Status' },
                    { key: 'priority' as SortKey, label: 'Priority' },
                    { key: 'pre_quote_cents' as SortKey, label: 'Quote' },
                    { key: 'created_at' as SortKey, label: 'Created' },
                  ] as { key: SortKey | null; label: string }[]).map(({ key, label }) => (
                    <th
                      key={label}
                      className={`px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase select-none${key ? ' cursor-pointer' : ''}`}
                      style={{ color: key ? 'var(--cafe-amber)' : 'var(--cafe-text-muted)' }}
                      onClick={() => key && handleSort(key)}
                    >
                      {label}{key && <SortIcon col={key} sortBy={sortBy} sortDir={sortDir} />}
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
                    <td className="px-5 py-3.5 font-mono text-xs">
                      <Link to={`/jobs/${j.id}`} className="font-medium hover:underline" style={{ color: 'var(--cafe-amber)' }}>#{j.job_number}</Link>
                    </td>
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text)' }}>{j.title}</td>
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
