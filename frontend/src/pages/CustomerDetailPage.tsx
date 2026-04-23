import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Plus, ChevronLeft, Wrench, Star } from 'lucide-react'
import { getCustomer, listWatches, createWatch, listJobs, listShoeRepairJobs, listAutoKeyJobs, getLoyaltyProfile, adjustLoyaltyPoints, type Watch, type ShoeRepairJob, type AutoKeyJob, type LoyaltyProfileResponse } from '@/lib/api'
import { Card, PageHeader, Button, Input, Modal, Spinner, Badge, Select, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewJobModal from '@/components/NewJobModal'

const TIER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Bronze:   { bg: '#F5EDE0', text: '#7C4A1E', border: '#D4956A' },
  Silver:   { bg: '#F0F0F0', text: '#4A4A4A', border: '#A0A0A0' },
  Gold:     { bg: '#FFF8E1', text: '#7A5E00', border: '#D4AF37' },
  Platinum: { bg: '#EDF4FF', text: '#1A3A6B', border: '#6A9FD4' },
}

function AdjustPointsModal({ customerId, onClose }: { customerId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [delta, setDelta] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const mut = useMutation({
    mutationFn: () => adjustLoyaltyPoints(customerId, parseInt(delta, 10), note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['loyalty', customerId] })
      onClose()
    },
    onError: (e: any) => setError(e?.response?.data?.detail ?? 'Failed to adjust points.'),
  })
  const deltaNum = parseInt(delta, 10)
  const valid = !isNaN(deltaNum) && deltaNum !== 0 && note.trim().length > 0

  return (
    <Modal title="Adjust Points" onClose={onClose}>
      <div className="space-y-3">
        <Input
          label="Points (positive to add, negative to deduct)"
          value={delta}
          onChange={e => setDelta(e.target.value)}
          placeholder="e.g. 100 or -50"
          type="number"
        />
        <Input
          label="Reason"
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="e.g. Goodwill adjustment"
        />
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !valid}>
            {mut.isPending ? 'Saving…' : 'Apply'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function LoyaltyPanel({ customerId }: { customerId: string }) {
  const [showAdjust, setShowAdjust] = useState(false)
  const { data, isLoading, isError } = useQuery<LoyaltyProfileResponse>({
    queryKey: ['loyalty', customerId],
    queryFn: () => getLoyaltyProfile(customerId).then(r => r.data),
  })

  if (isLoading) return (
    <Card className="mt-6">
      <div className="px-5 py-8 flex justify-center"><Spinner /></div>
    </Card>
  )
  if (isError || !data) return null

  const { loyalty, recent_ledger } = data
  const colors = TIER_COLORS[loyalty.tier_name] ?? TIER_COLORS.Bronze
  const ENTRY_LABELS: Record<string, string> = {
    earn: 'Earned',
    adjust: 'Adjusted',
    signup_bonus: 'Welcome bonus',
  }

  return (
    <>
      {showAdjust && <AdjustPointsModal customerId={customerId} onClose={() => setShowAdjust(false)} />}
      <Card className="mt-6">
        <div
          className="px-5 py-4 flex items-center justify-between"
          style={{ borderBottom: '1px solid var(--ms-border)' }}
        >
          <div className="flex items-center gap-2 font-semibold" style={{ color: 'var(--ms-text)' }}>
            <Star size={16} />
            Loyalty
          </div>
          <Button variant="secondary" onClick={() => setShowAdjust(true)} style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
            Adjust points
          </Button>
        </div>

        {/* Tier + balance summary */}
        <div className="px-5 py-4 flex items-center gap-4" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <div
            className="px-3 py-1 rounded-full text-xs font-bold tracking-wide"
            style={{ backgroundColor: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
          >
            {loyalty.tier_name} · {loyalty.tier_label}
          </div>
          <div>
            <span className="text-2xl font-bold" style={{ color: 'var(--ms-text)' }}>
              {loyalty.points_balance.toLocaleString()}
            </span>
            <span className="ml-1 text-sm" style={{ color: 'var(--ms-text-muted)' }}>pts</span>
            <span className="ml-2 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              (≈ ${loyalty.points_dollar_value.toFixed(2)})
            </span>
          </div>
        </div>

        {/* Rolling spend */}
        <div className="px-5 py-3 text-xs" style={{ color: 'var(--ms-text-muted)', borderBottom: '1px solid var(--ms-border)' }}>
          12-month spend: <span className="font-medium" style={{ color: 'var(--ms-text-mid)' }}>
            ${(loyalty.rolling_12m_spend_cents / 100).toFixed(2)}
          </span>
          {' · '}Member since {formatDate(loyalty.joined_at)}
        </div>

        {/* Ledger */}
        <div>
          {recent_ledger.length === 0 && (
            <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No activity yet.</p>
          )}
          {recent_ledger.map((row, i) => (
            <div
              key={row.id}
              className="flex items-center justify-between px-5 py-3"
              style={{ borderBottom: i < recent_ledger.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
            >
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                  {ENTRY_LABELS[row.entry_type] ?? row.entry_type}
                  {row.note ? ` — ${row.note}` : ''}
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(row.occurred_at)}</p>
              </div>
              <span
                className="text-sm font-semibold"
                style={{ color: row.points_delta >= 0 ? '#3A7D44' : '#C96A5A' }}
              >
                {row.points_delta >= 0 ? '+' : ''}{row.points_delta}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </>
  )
}

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
  if (!customer) return <p style={{ color: 'var(--ms-text-muted)' }}>Customer not found.</p>

  return (
    <div>
      <div className="mb-5">
        <Link
          to="/customers"
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--ms-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-text-muted)')}
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
        {customer.phone && <div style={{ color: 'var(--ms-text-mid)' }}><span className="font-medium" style={{ color: 'var(--ms-text)' }}>Phone: </span>{customer.phone}</div>}
        {customer.email && <div style={{ color: 'var(--ms-text-mid)' }}><span className="font-medium" style={{ color: 'var(--ms-text)' }}>Email: </span>{customer.email}</div>}
        {customer.address && <div style={{ color: 'var(--ms-text-mid)' }}><span className="font-medium" style={{ color: 'var(--ms-text)' }}>Address: </span>{customer.address}</div>}
        {customer.notes && <div className="lg:col-span-3" style={{ color: 'var(--ms-text-mid)' }}><span className="font-medium" style={{ color: 'var(--ms-text)' }}>Notes: </span>{customer.notes}</div>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            Watches ({watches?.length ?? 0})
          </div>
          <div>
            {(watches ?? []).map((w: Watch, i) => (
              <div
                key={w.id}
                className="px-5 py-3.5"
                style={{ borderBottom: i < (watches ?? []).length - 1 ? '1px solid var(--ms-border)' : 'none' }}
              >
                <p className="font-medium" style={{ color: 'var(--ms-text)' }}>{[w.brand, w.model].filter(Boolean).join(' ') || 'Unknown watch'}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{w.serial_number ? `S/N: ${w.serial_number}` : ''} {w.movement_type ?? ''}</p>
              </div>
            ))}
            {(watches ?? []).length === 0 && (
              <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No watches yet.</p>
            )}
          </div>
        </Card>

        <Card>
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            Repair Jobs ({customerJobs.length})
          </div>
          <div>
            <div className="px-5 pt-4 pb-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
              <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
                <button
                  type="button"
                  className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                  style={{
                    backgroundColor: jobDirectoryView === 'active' ? 'var(--ms-surface)' : 'transparent',
                    color: jobDirectoryView === 'active' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
                  }}
                  onClick={() => setJobDirectoryView('active')}
                >
                  Active ({activeJobs.length})
                </button>
                <button
                  type="button"
                  className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                  style={{
                    backgroundColor: jobDirectoryView === 'completed' ? 'var(--ms-surface)' : 'transparent',
                    color: jobDirectoryView === 'completed' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
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
                    style={{ borderBottom: i < activeJobs.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                    </div>
                    <Badge status={job.status} />
                  </Link>
                ))}
                {activeJobs.length === 0 && (
                  <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No active jobs.</p>
                )}
              </>
            )}

            {jobDirectoryView === 'completed' && (
              <>
                {completedDirectoryJobs.length > 0 && (
                  <div className="px-5 pt-4 pb-2 text-[11px] font-semibold tracking-widest uppercase" style={{ color: 'var(--ms-text-muted)' }}>
                    Completed Directory ({completedDirectoryJobs.length})
                  </div>
                )}
                {completedDirectoryJobs.map((job, i) => (
                  <Link
                    key={job.id}
                    to={`/jobs/${job.id}`}
                    className="flex items-center justify-between px-5 py-3.5 transition-colors"
                    style={{ borderBottom: i < completedDirectoryJobs.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                    </div>
                    <Badge status={job.status} />
                  </Link>
                ))}

                {noGoJobs.length > 0 && (
                  <>
                    <div className="px-5 pt-4 pb-2 text-[11px] font-semibold tracking-widest uppercase" style={{ color: 'var(--ms-text-muted)', borderTop: completedDirectoryJobs.length > 0 ? '1px solid var(--ms-border)' : 'none' }}>
                      Closed - No Go ({noGoJobs.length})
                    </div>
                    {noGoJobs.map((job, i) => (
                      <Link
                        key={job.id}
                        to={`/jobs/${job.id}`}
                        className="flex items-center justify-between px-5 py-3.5 transition-colors"
                        style={{ borderBottom: i < noGoJobs.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                        onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                        onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                        </div>
                        <Badge status={job.status} />
                      </Link>
                    ))}
                  </>
                )}

                {closedJobsCount === 0 && (
                  <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No completed jobs.</p>
                )}
              </>
            )}
            {customerJobs.length === 0 && (
              <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No jobs yet.</p>
            )}
          </div>
        </Card>
      </div>

      {/* ── Shoe Repair Jobs ─────────────────────────────────────────── */}
      {shoeJobs.length > 0 && (
        <Card className="mt-6">
          <div
            className="px-5 py-4 font-semibold"
            style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            Shoe Repairs ({shoeJobs.length})
          </div>
          <div>
            {(shoeJobs as ShoeRepairJob[]).map((job, i) => (
              <Link
                key={job.id}
                to={`/shoe-repairs/${job.id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors"
                style={{ borderBottom: i < shoeJobs.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
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
            style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            Mobile Key Jobs ({autoKeyJobs.length})
          </div>
          <div>
            {(autoKeyJobs as AutoKeyJob[]).map((job, i) => (
              <Link
                key={job.id}
                to={`/auto-key/${job.id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors"
                style={{ borderBottom: i < autoKeyJobs.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
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

      <LoyaltyPanel customerId={customer.id} />
    </div>
  )
}

