import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Plus, ChevronLeft, Wrench } from 'lucide-react'
import { getCustomer, listWatches, createWatch, listJobs, listShoeRepairJobs, listAutoKeyJobs, type Watch, type ShoeRepairJob, type AutoKeyJob } from '@/lib/api'
import { Card, PageHeader, Button, Input, Modal, Spinner, Badge, Select, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const COMPLETED_DIRECTORY_STATUSES = ['completed', 'awaiting_collection', 'collected']
const NON_ACTIVE_STATUSES = ['no_go', ...COMPLETED_DIRECTORY_STATUSES]

function AddWatchModal({ customerId, onClose }: { customerId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({ customer_id: customerId, brand: '', model: '', serial_number: '', movement_type: '', condition_notes: '' })
  const [error, setError] = useState('')
  const mut = useMutation({
    mutationFn: () => createWatch(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['watches', customerId] }); onClose() },
    onError: () => setError('Failed to add watch.'),
  })
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <Modal title="Add Watch" onClose={onClose}>
      <div className="space-y-3">
        <Input label="Brand" value={form.brand} onChange={set('brand')} placeholder="Rolex, Omega…" />
        <Input label="Model" value={form.model} onChange={set('model')} placeholder="Submariner, Speedmaster…" />
        <Input label="Serial Number" value={form.serial_number} onChange={set('serial_number')} />
        <Select label="Movement Type" value={form.movement_type} onChange={set('movement_type')}>
          <option value="">Select…</option>
          <option value="mechanical">Mechanical</option>
          <option value="automatic">Automatic</option>
          <option value="quartz">Quartz</option>
          <option value="solar">Solar</option>
          <option value="kinetic">Kinetic</option>
        </Select>
        <Textarea label="Condition Notes" value={form.condition_notes} onChange={set('condition_notes')} rows={2} />
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>{mut.isPending ? 'Saving…' : 'Add Watch'}</Button>
        </div>
      </div>
    </Modal>
  )
}

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [showAddWatch, setShowAddWatch] = useState(false)
  const [showNewJob, setShowNewJob] = useState(false)
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>('active')
  const { data: customer, isLoading } = useQuery({ queryKey: ['customer', id], queryFn: () => getCustomer(id!).then(r => r.data) })
  const { data: watches } = useQuery({ queryKey: ['watches', id], queryFn: () => listWatches(id).then(r => r.data) })
  const { data: jobs } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })
  const { data: shoeJobs = [] } = useQuery({
    queryKey: ['shoe-repair-jobs', 'customer', id],
    queryFn: () => listShoeRepairJobs({ customer_id: id }).then(r => r.data),
    enabled: !!id,
  })
  const { data: autoKeyJobs = [] } = useQuery({
    queryKey: ['auto-key-jobs', 'customer', id],
    queryFn: () => listAutoKeyJobs({ customer_id: id }).then(r => r.data),
    enabled: !!id,
  })

  const customerWatchIds = new Set((watches ?? []).map(w => w.id))
  const customerJobs = (jobs ?? []).filter(j => customerWatchIds.has(j.watch_id))
  const activeJobs = customerJobs.filter(j => !NON_ACTIVE_STATUSES.includes(j.status))
  const completedDirectoryJobs = customerJobs.filter(j => COMPLETED_DIRECTORY_STATUSES.includes(j.status))
  const noGoJobs = customerJobs.filter(j => j.status === 'no_go')
  const closedJobsCount = completedDirectoryJobs.length + noGoJobs.length

  if (isLoading) return <Spinner />
  if (!customer) return <p style={{ color: 'var(--cafe-text-muted)' }}>Customer not found.</p>

  return (
    <div>
      <div className="mb-5">
        <Link
          to="/customers"
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--cafe-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
        >
          <ChevronLeft size={14} /> Back to Customers
        </Link>
      </div>
      <PageHeader
        title={customer.full_name}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowAddWatch(true)}><Plus size={16} />Add Watch</Button>
            <Button onClick={() => setShowNewJob(true)}><Wrench size={16} />New Job Ticket</Button>
          </div>
        }
      />
      {showAddWatch && <AddWatchModal customerId={customer.id} onClose={() => setShowAddWatch(false)} />}
      {showNewJob && (
        <NewJobModal
          preselectedCustomer={{ id: customer.id, full_name: customer.full_name }}
          onClose={() => setShowNewJob(false)}
          onSuccess={jobId => { setShowNewJob(false); navigate(`/jobs/${jobId}`) }}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6 text-sm">
        {customer.phone && <div style={{ color: 'var(--cafe-text-mid)' }}><span className="font-medium" style={{ color: 'var(--cafe-text)' }}>Phone: </span>{customer.phone}</div>}
        {customer.email && <div style={{ color: 'var(--cafe-text-mid)' }}><span className="font-medium" style={{ color: 'var(--cafe-text)' }}>Email: </span>{customer.email}</div>}
        {customer.address && <div style={{ color: 'var(--cafe-text-mid)' }}><span className="font-medium" style={{ color: 'var(--cafe-text)' }}>Address: </span>{customer.address}</div>}
        {customer.notes && <div className="lg:col-span-3" style={{ color: 'var(--cafe-text-mid)' }}><span className="font-medium" style={{ color: 'var(--cafe-text)' }}>Notes: </span>{customer.notes}</div>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--cafe-border)', fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
          >
            Watches ({watches?.length ?? 0})
          </div>
          <div>
            {(watches ?? []).map((w: Watch, i) => (
              <div
                key={w.id}
                className="px-5 py-3.5"
                style={{ borderBottom: i < (watches ?? []).length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
              >
                <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>{[w.brand, w.model].filter(Boolean).join(' ') || 'Unknown watch'}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>{w.serial_number ? `S/N: ${w.serial_number}` : ''} {w.movement_type ?? ''}</p>
              </div>
            ))}
            {(watches ?? []).length === 0 && (
              <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>No watches yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--cafe-border)', fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
          >
            Repair Jobs ({customerJobs.length})
          </div>
          <div>
            <div className="px-5 pt-4 pb-3" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
                <button
                  type="button"
                  className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                  style={{
                    backgroundColor: jobDirectoryView === 'active' ? 'var(--cafe-paper)' : 'transparent',
                    color: jobDirectoryView === 'active' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
                  }}
                  onClick={() => setJobDirectoryView('active')}
                >
                  Active ({activeJobs.length})
                </button>
                <button
                  type="button"
                  className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                  style={{
                    backgroundColor: jobDirectoryView === 'completed' ? 'var(--cafe-paper)' : 'transparent',
                    color: jobDirectoryView === 'completed' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
                  }}
                  onClick={() => setJobDirectoryView('completed')}
                >
                  Completed ({closedJobsCount})
                </button>
              </div>
            </div>

            {jobDirectoryView === 'active' && (
              <>
                {activeJobs.map((job, i) => (
                  <Link
                    key={job.id}
                    to={`/jobs/${job.id}`}
                    className="flex items-center justify-between px-5 py-3.5 transition-colors"
                    style={{ borderBottom: i < activeJobs.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{job.title}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                    </div>
                    <Badge status={job.status} />
                  </Link>
                ))}
                {activeJobs.length === 0 && (
                  <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>No active jobs.</p>
                )}
              </>
            )}

            {jobDirectoryView === 'completed' && (
              <>
                {completedDirectoryJobs.length > 0 && (
                  <div className="px-5 pt-4 pb-2 text-[11px] font-semibold tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                    Completed Directory ({completedDirectoryJobs.length})
                  </div>
                )}
                {completedDirectoryJobs.map((job, i) => (
                  <Link
                    key={job.id}
                    to={`/jobs/${job.id}`}
                    className="flex items-center justify-between px-5 py-3.5 transition-colors"
                    style={{ borderBottom: i < completedDirectoryJobs.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{job.title}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                    </div>
                    <Badge status={job.status} />
                  </Link>
                ))}

                {noGoJobs.length > 0 && (
                  <>
                    <div className="px-5 pt-4 pb-2 text-[11px] font-semibold tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)', borderTop: completedDirectoryJobs.length > 0 ? '1px solid var(--cafe-border)' : 'none' }}>
                      Closed - No Go ({noGoJobs.length})
                    </div>
                    {noGoJobs.map((job, i) => (
                      <Link
                        key={job.id}
                        to={`/jobs/${job.id}`}
                        className="flex items-center justify-between px-5 py-3.5 transition-colors"
                        style={{ borderBottom: i < noGoJobs.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                        onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                        onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{job.title}</p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                        </div>
                        <Badge status={job.status} />
                      </Link>
                    ))}
                  </>
                )}

                {closedJobsCount === 0 && (
                  <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>No completed jobs.</p>
                )}
              </>
            )}
            {customerJobs.length === 0 && (
              <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>No jobs yet.</p>
            )}
          </div>
        </Card>
      </div>

      {/* ── Shoe Repair Jobs ─────────────────────────────────────────── */}
      {shoeJobs.length > 0 && (
        <Card className="mt-6">
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--cafe-border)', fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
          >
            Shoe Repairs ({shoeJobs.length})
          </div>
          <div>
            {(shoeJobs as ShoeRepairJob[]).map((job, i) => (
              <Link
                key={job.id}
                to={`/shoe-repairs/${job.id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors"
                style={{ borderBottom: i < shoeJobs.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{job.title}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                    #{job.job_number}
                    {job.shoe?.brand ? ` · ${job.shoe.brand}` : ''}
                    {` · ${formatDate(job.created_at)}`}
                  </p>
                </div>
                <Badge status={job.status} />
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* ── Auto / Mobile Key Jobs ────────────────────────────────────── */}
      {autoKeyJobs.length > 0 && (
        <Card className="mt-4">
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--cafe-border)', fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
          >
            Mobile Key Jobs ({autoKeyJobs.length})
          </div>
          <div>
            {(autoKeyJobs as AutoKeyJob[]).map((job, i) => (
              <Link
                key={job.id}
                to={`/auto-key/${job.id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors"
                style={{ borderBottom: i < autoKeyJobs.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{job.title}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                    #{job.job_number}
                    {job.vehicle_make ? ` · ${job.vehicle_make}${job.vehicle_model ? ` ${job.vehicle_model}` : ''}` : ''}
                    {` · ${formatDate(job.created_at)}`}
                  </p>
                </div>
                <Badge status={job.status} />
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

