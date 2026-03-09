import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { listJobs, type JobStatus, type RepairJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const JOB_STATUSES: JobStatus[] = ['awaiting_go_ahead', 'go_ahead', 'no_go', 'working_on', 'awaiting_parts', 'parts_to_order', 'sent_to_labanda', 'service', 'completed', 'awaiting_collection', 'collected']
const COMPLETED_DIRECTORY_STATUSES: JobStatus[] = ['completed', 'awaiting_collection', 'collected']
const NON_ACTIVE_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]
const ACTIVE_DIRECTORY_STATUSES: JobStatus[] = JOB_STATUSES.filter(s => !NON_ACTIVE_STATUSES.includes(s))
const CLOSED_DIRECTORY_STATUSES: JobStatus[] = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]

export default function JobsPage() {
  const [showAdd, setShowAdd] = useState(false)
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
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            className="pl-9 pr-4 py-2 rounded-lg text-sm outline-none transition"
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
          className="rounded-lg px-3 py-2 text-sm outline-none transition"
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
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  {['Job #', 'Title', 'Status', 'Priority', 'Created'].map(h => (
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
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(j.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
