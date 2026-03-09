import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { listJobs, type JobStatus, type RepairJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const JOB_STATUSES: JobStatus[] = ['intake', 'diagnosis', 'awaiting_approval', 'in_repair', 'qc', 'ready', 'delivered', 'cancelled']

export default function JobsPage() {
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('active')
  const { data: jobs, isLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })

  const filtered = (jobs ?? []).filter(j => {
    const matchSearch = j.title.toLowerCase().includes(search.toLowerCase()) || j.job_number.includes(search)
    const matchStatus = statusFilter === 'all' ? true :
      statusFilter === 'active' ? !['delivered', 'cancelled'].includes(j.status) :
      j.status === statusFilter
    return matchSearch && matchStatus
  })

  return (
    <div>
      <PageHeader title="Repair Jobs" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} />New Job Ticket</Button>} />
      {showAdd && <NewJobModal onClose={() => setShowAdd(false)} />}

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
          <option value="active">Active jobs</option>
          <option value="all">All statuses</option>
          {JOB_STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
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
