import { Fragment, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Calendar, CalendarDays, ChevronLeft, ChevronRight, List, MapPin } from 'lucide-react'
import {
  createAutoKeyInvoiceFromQuote,
  createAutoKeyJob,
  createAutoKeyQuote,
  getApiErrorMessage,
  listCustomerAccounts,
  listAutoKeyInvoices,
  listAutoKeyJobs,
  listAutoKeyQuotes,
  listCustomers,
  listUsers,
  sendAutoKeyQuote,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  vehicleLookup,
  type AutoKeyProgrammingStatus,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { formatDate, STATUS_LABELS, JOB_STATUS_ORDER } from '@/lib/utils'

const STATUSES: JobStatus[] = [...JOB_STATUS_ORDER]

const PROGRAMMING_STATUSES: AutoKeyProgrammingStatus[] = ['pending', 'in_progress', 'programmed', 'failed', 'not_required']

function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

function NewAutoKeyJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    customer_id: '',
    customer_account_id: '',
    assigned_user_id: '',
    title: '',
    description: '',
    job_type: '' as '' | 'mobile' | 'shop',
    job_address: '',
    scheduled_at: '',
    vehicle_make: '',
    vehicle_model: '',
    vehicle_year: '',
    registration_plate: '',
    rego_state: 'VIC',
    vin: '',
    key_type: '',
    key_quantity: '1',
    programming_status: 'pending' as AutoKeyProgrammingStatus,
    priority: 'normal' as 'low' | 'normal' | 'high' | 'urgent',
    status: 'awaiting_quote' as JobStatus,
    salesperson: '',
    collection_date: '',
    deposit: '',
    cost: '',
  })

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })

  const matchingAccounts = form.customer_id
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(form.customer_id))
    : customerAccounts

  const lookupMut = useMutation({
    mutationFn: () => vehicleLookup(form.registration_plate.trim(), form.rego_state).then(r => r.data),
    onSuccess: data => {
      if (data.found) {
        setForm(f => ({
          ...f,
          vehicle_make: data.make ?? f.vehicle_make,
          vehicle_model: data.model ?? f.vehicle_model,
          vehicle_year: data.year ? String(data.year) : f.vehicle_year,
          vin: data.vin ?? f.vin,
          registration_plate: data.registration_plate ?? f.registration_plate,
        }))
      }
    },
    onError: err => setError(getApiErrorMessage(err, 'Lookup failed. Check plate, state, or API config.')),
  })

  const createMut = useMutation({
    mutationFn: async () => {
      if (!form.customer_id || !form.title.trim()) {
        throw new Error('Customer and job title are required.')
      }
      return createAutoKeyJob({
        customer_id: form.customer_id,
        customer_account_id: form.customer_account_id || undefined,
        assigned_user_id: form.assigned_user_id || undefined,
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        job_type: form.job_type || undefined,
        job_address: form.job_address.trim() || undefined,
        scheduled_at: form.scheduled_at ? form.scheduled_at + 'T09:00:00Z' : undefined,
        vehicle_make: form.vehicle_make.trim() || undefined,
        vehicle_model: form.vehicle_model.trim() || undefined,
        vehicle_year: form.vehicle_year ? Number(form.vehicle_year) : undefined,
        registration_plate: form.registration_plate.trim() || undefined,
        vin: form.vin.trim() || undefined,
        key_type: form.key_type.trim() || undefined,
        key_quantity: Math.max(1, Number(form.key_quantity || '1')),
        programming_status: form.programming_status,
        priority: form.priority,
        status: form.status,
        salesperson: form.salesperson.trim() || undefined,
        collection_date: form.collection_date.trim() || undefined,
        deposit_cents: form.deposit ? Math.round(parseFloat(form.deposit) * 100) : 0,
        cost_cents: form.cost ? Math.round(parseFloat(form.cost) * 100) : 0,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create auto key job.')),
  })

  return (
    <Modal title="New Auto Key Job" onClose={onClose}>
      <div className="space-y-3">
        <Select label="Customer *" value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}>
          <option value="">Select customer</option>
          {customers.map(c => (
            <option key={c.id} value={c.id}>{c.full_name}{c.phone ? ` · ${c.phone}` : ''}</option>
          ))}
        </Select>
        <Select label="Customer Account (optional)" value={form.customer_account_id} onChange={e => setForm(f => ({ ...f, customer_account_id: e.target.value }))}>
          <option value="">No B2B account</option>
          {matchingAccounts.map((account: CustomerAccount) => (
            <option key={account.id} value={account.id}>
              {account.name}{account.account_code ? ` (${account.account_code})` : ''}
            </option>
          ))}
        </Select>
        <Select label="Assign tech" value={form.assigned_user_id} onChange={e => setForm(f => ({ ...f, assigned_user_id: e.target.value }))}>
          <option value="">Unassigned</option>
          {users.map((u: { id: string; full_name: string }) => (
            <option key={u.id} value={u.id}>{u.full_name}</option>
          ))}
        </Select>
        <Input label="Job title *" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="e.g. Duplicate transponder key" />
        <Textarea label="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} />
        <Select label="Job type" value={form.job_type} onChange={e => setForm(f => ({ ...f, job_type: e.target.value as '' | 'mobile' | 'shop' }))}>
          <option value="">Not set</option>
          <option value="shop">Shop (in-store)</option>
          <option value="mobile">Mobile (on-site visit)</option>
        </Select>
        {form.job_type === 'mobile' && (
          <Input label="Job address" value={form.job_address} onChange={e => setForm(f => ({ ...f, job_address: e.target.value }))} placeholder="Where to meet customer" />
        )}
        <Input label="Schedule date" type="date" value={form.scheduled_at} onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))} />
        <div className="flex flex-wrap items-end gap-2">
          <Input label="Registration" value={form.registration_plate} onChange={e => setForm(f => ({ ...f, registration_plate: e.target.value }))} placeholder="ABC123" className="flex-1 min-w-[120px]" />
          <Select label="State" value={form.rego_state} onChange={e => setForm(f => ({ ...f, rego_state: e.target.value }))} className="w-24">
            {['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
          <Button type="button" variant="secondary" onClick={() => lookupMut.mutate()} disabled={lookupMut.isPending || !form.registration_plate.trim()}>
            {lookupMut.isPending ? 'Looking up…' : 'Look up'}
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Vehicle make" value={form.vehicle_make} onChange={e => setForm(f => ({ ...f, vehicle_make: e.target.value }))} />
          <Input label="Vehicle model" value={form.vehicle_model} onChange={e => setForm(f => ({ ...f, vehicle_model: e.target.value }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Vehicle year" type="number" value={form.vehicle_year} onChange={e => setForm(f => ({ ...f, vehicle_year: e.target.value }))} />
          <Input label="VIN" value={form.vin} onChange={e => setForm(f => ({ ...f, vin: e.target.value }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Key type" value={form.key_type} onChange={e => setForm(f => ({ ...f, key_type: e.target.value }))} />
          <Input label="Qty" type="number" min="1" value={form.key_quantity} onChange={e => setForm(f => ({ ...f, key_quantity: e.target.value }))} />
          <Select label="Programming" value={form.programming_status} onChange={e => setForm(f => ({ ...f, programming_status: e.target.value as AutoKeyProgrammingStatus }))}>
            {PROGRAMMING_STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Select label="Priority" value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value as 'low' | 'normal' | 'high' | 'urgent' }))}>
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </Select>
          <Select label="Status" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value as JobStatus }))}>
            {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>)}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Deposit ($)" type="number" step="0.01" value={form.deposit} onChange={e => setForm(f => ({ ...f, deposit: e.target.value }))} />
          <Input label="Cost ($)" type="number" step="0.01" value={form.cost} onChange={e => setForm(f => ({ ...f, cost: e.target.value }))} />
        </div>
        <Input label="Collection Date" type="date" value={form.collection_date} onChange={e => setForm(f => ({ ...f, collection_date: e.target.value }))} />
        <Input label="Salesperson" value={form.salesperson} onChange={e => setForm(f => ({ ...f, salesperson: e.target.value }))} />

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

        <div className="flex gap-2 pt-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button className="flex-1" onClick={() => createMut.mutate()} disabled={createMut.isPending}>
            {createMut.isPending ? 'Creating…' : 'Create Job'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function CreateQuoteModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [description, setDescription] = useState('Auto key service')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('120.00')
  const [tax, setTax] = useState('0.00')

  const quoteMut = useMutation({
    mutationFn: () =>
      createAutoKeyQuote(jobId, {
        line_items: [
          {
            description: description.trim() || 'Auto key service',
            quantity: Math.max(1, Number(quantity || '1')),
            unit_price_cents: Math.max(0, Math.round(parseFloat(unitPrice || '0') * 100)),
          },
        ],
        tax_cents: Math.max(0, Math.round(parseFloat(tax || '0') * 100)),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-quotes', jobId] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create quote.')),
  })

  return (
    <Modal title="Create Auto Key Quote" onClose={onClose}>
      <div className="space-y-3">
        <Input label="Line item" value={description} onChange={e => setDescription(e.target.value)} />
        <div className="grid grid-cols-3 gap-3">
          <Input label="Qty" type="number" min="1" value={quantity} onChange={e => setQuantity(e.target.value)} />
          <Input label="Unit ($)" type="number" step="0.01" min="0" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} />
          <Input label="Tax ($)" type="number" step="0.01" min="0" value={tax} onChange={e => setTax(e.target.value)} />
        </div>
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex gap-2 pt-2">
          <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button className="flex-1" onClick={() => quoteMut.mutate()} disabled={quoteMut.isPending}>
            {quoteMut.isPending ? 'Creating…' : 'Create Quote'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function AutoKeyJobCard({ job, users }: { job: { id: string; job_number: string; title: string; customer_id: string; customer_account_id?: string; assigned_user_id?: string; vehicle_make?: string; vehicle_model?: string; vehicle_year?: number; registration_plate?: string; key_type?: string; key_quantity: number; programming_status: string; status: JobStatus; created_at: string; salesperson?: string; scheduled_at?: string; job_address?: string; job_type?: string }; users: { id: string; full_name: string }[] }) {
  const qc = useQueryClient()
  const [showQuoteModal, setShowQuoteModal] = useState(false)

  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const matchingAccounts = customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(job.customer_id))

  const { data: quotes = [] } = useQuery({
    queryKey: ['auto-key-quotes', job.id],
    queryFn: () => listAutoKeyQuotes(job.id).then(r => r.data),
  })
  const { data: invoices = [] } = useQuery({
    queryKey: ['auto-key-invoices', job.id],
    queryFn: () => listAutoKeyInvoices(job.id).then(r => r.data),
  })

  const latestQuote = quotes[0]
  const latestInvoice = invoices[0]

  const statusMut = useMutation({
    mutationFn: (status: JobStatus) => updateAutoKeyJobStatus(job.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const updateAccountMut = useMutation({
    mutationFn: (customer_account_id: string | null) => updateAutoKeyJob(job.id, { customer_account_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const assignTechMut = useMutation({
    mutationFn: (assigned_user_id: string | null) => updateAutoKeyJob(job.id, { assigned_user_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
  })

  const sendQuoteMut = useMutation({
    mutationFn: (quoteId: string) => sendAutoKeyQuote(quoteId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-quotes', job.id] }),
  })

  const invoiceMut = useMutation({
    mutationFn: (quoteId: string) => createAutoKeyInvoiceFromQuote(job.id, quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-invoices', job.id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
    },
  })

  return (
    <Card className="p-4">
      {showQuoteModal && <CreateQuoteModal jobId={job.id} onClose={() => setShowQuoteModal(false)} />}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-mono font-semibold" style={{ color: 'var(--cafe-amber)' }}>#{job.job_number}</p>
            {job.assigned_user_id && (
              <span className="text-[11px] font-medium rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(93,74,155,0.2)', color: '#5D4A9B' }}>
                {users.find(u => u.id === job.assigned_user_id)?.full_name ?? 'Assigned'}
              </span>
            )}
            {job.customer_account_id && (
              <span className="text-[11px] font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: '#EAF4EA', color: '#2F6A3D' }}>
                B2B
              </span>
            )}
          </div>
          <Link to={`/auto-key/${job.id}`} className="text-sm font-semibold hover:underline" style={{ color: 'var(--cafe-text)' }}>
            {job.title}
          </Link>
          <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
            {job.vehicle_make || 'Unknown make'} {job.vehicle_model || ''}
            {job.vehicle_year ? ` · ${job.vehicle_year}` : ''}
            {job.registration_plate ? ` · ${job.registration_plate}` : ''}
          </p>
          <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
            Key: {job.key_type || 'Unspecified'} · Qty {job.key_quantity} · Programming {job.programming_status.replace(/_/g, ' ')}
          </p>
          <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
            {formatDate(job.created_at)}{job.salesperson ? ` · ${job.salesperson}` : ''}
          </p>
          {(job.scheduled_at || job.job_type) && (
            <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              {job.scheduled_at && <span className="font-medium" style={{ color: 'var(--cafe-amber)' }}>{formatDate(job.scheduled_at)}</span>}
              {job.scheduled_at && job.job_type && ' · '}
              {job.job_type === 'mobile' && <>Mobile{job.job_address ? ` · ${job.job_address}` : ''}</>}
              {job.job_type === 'shop' && 'Shop'}
            </p>
          )}
          {job.job_type === 'mobile' && job.job_address && (
            <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-medium mt-1 hover:underline" style={{ color: 'var(--cafe-amber)' }}>
              <MapPin size={12} /> Get directions
            </a>
          )}

          {latestQuote && (
            <p className="text-xs mt-2" style={{ color: 'var(--cafe-text-mid)' }}>
              Latest quote: {formatCents(latestQuote.total_cents)} ({latestQuote.status})
            </p>
          )}
          {latestInvoice && (
            <p className="text-xs" style={{ color: 'var(--cafe-text-mid)' }}>
              Latest invoice: {latestInvoice.invoice_number} · {formatCents(latestInvoice.total_cents)} ({latestInvoice.status})
            </p>
          )}
        </div>

        <div className="w-56">
          <div className="mb-2"><Badge status={job.status} /></div>
          <Select
            value={job.status}
            onChange={e => statusMut.mutate(e.target.value as JobStatus)}
            disabled={statusMut.isPending}
          >
            {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>)}
          </Select>
          <div className="mt-2">
            <Select
              label="Assign tech"
              value={job.assigned_user_id ?? ''}
              onChange={e => assignTechMut.mutate(e.target.value || null)}
              disabled={assignTechMut.isPending}
            >
              <option value="">Unassigned</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.full_name}</option>
              ))}
            </Select>
          </div>
          <div className="mt-2">
            <Select
              value={job.customer_account_id ?? ''}
              onChange={e => updateAccountMut.mutate(e.target.value || null)}
              disabled={updateAccountMut.isPending}
            >
              <option value="">No B2B account</option>
              {matchingAccounts.map((account: CustomerAccount) => (
                <option key={account.id} value={account.id}>
                  {account.name}{account.account_code ? ` (${account.account_code})` : ''}
                </option>
              ))}
            </Select>
          </div>
          <div className="mt-2 space-y-2">
            <Button variant="secondary" className="w-full" onClick={() => setShowQuoteModal(true)}>
              New Quote
            </Button>
            {latestQuote && latestQuote.status === 'draft' && (
              <Button className="w-full" onClick={() => sendQuoteMut.mutate(latestQuote.id)} disabled={sendQuoteMut.isPending}>
                {sendQuoteMut.isPending ? 'Sending…' : 'Mark Quote Sent'}
              </Button>
            )}
            {latestQuote && !latestInvoice && (
              <Button className="w-full" onClick={() => invoiceMut.mutate(latestQuote.id)} disabled={invoiceMut.isPending}>
                {invoiceMut.isPending ? 'Creating…' : 'Create Invoice from Quote'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}

export default function AutoKeyJobsPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [view, setView] = useState<'jobs' | 'dispatch' | 'week'>('jobs')
  const [dispatchDate, setDispatchDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [dispatchTechFilter, setDispatchTechFilter] = useState<string>('')
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date()
    const day = d.getDay()
    const diff = d.getDate() - day + (day === 0 ? -6 : 1) // Monday
    const mon = new Date(d)
    mon.setDate(diff)
    return mon.toISOString().slice(0, 10)
  })

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['auto-key-jobs'],
    queryFn: () => listAutoKeyJobs().then(r => r.data),
  })
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })

  const dispatchParams = view === 'dispatch' ? { date_from: dispatchDate, date_to: dispatchDate, ...(dispatchTechFilter ? { assigned_user_id: dispatchTechFilter } : {}) } : undefined
  const { data: dispatchJobs = [], isLoading: dispatchLoading } = useQuery({
    queryKey: ['auto-key-jobs', 'dispatch', dispatchDate, dispatchTechFilter],
    queryFn: () => listAutoKeyJobs(dispatchParams!).then(r => r.data),
    enabled: view === 'dispatch' && !!dispatchParams,
  })

  const weekEnd = (() => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + 6)
    return d.toISOString().slice(0, 10)
  })()
  const weekParams = view === 'week' ? { date_from: weekStart, date_to: weekEnd } : undefined
  const { data: weekJobs = [], isLoading: weekLoading } = useQuery({
    queryKey: ['auto-key-jobs', 'week', weekStart, weekEnd],
    queryFn: () => listAutoKeyJobs(weekParams!).then(r => r.data),
    enabled: view === 'week' && !!weekParams,
  })

  const unscheduledJobs = view === 'dispatch' ? jobs.filter((j: { scheduled_at?: string }) => !j.scheduled_at) : []

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <PageHeader
          title="Auto Key"
          action={<Button onClick={() => setShowCreate(true)}><Plus size={16} />New Job</Button>}
        />
        <div className="flex items-center gap-2">
          <button
            onClick={() => setView('jobs')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'jobs' ? 'bg-opacity-20' : ''}`}
            style={view === 'jobs' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <List size={16} /> Jobs
          </button>
          <button
            onClick={() => setView('dispatch')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'dispatch' ? 'bg-opacity-20' : ''}`}
            style={view === 'dispatch' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <Calendar size={16} /> Dispatch
          </button>
          <button
            onClick={() => setView('week')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'week' ? 'bg-opacity-20' : ''}`}
            style={view === 'week' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <CalendarDays size={16} /> Week
          </button>
        </div>
      </div>

      {showCreate && <NewAutoKeyJobModal onClose={() => setShowCreate(false)} />}

      {view === 'jobs' && (
        isLoading ? <Spinner /> : (
          <div className="space-y-3">
            {jobs.length === 0 ? <EmptyState message="No auto key jobs yet." /> : jobs.map((job: object) => <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} />)}
          </div>
        )
      )}

      {view === 'dispatch' && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Date</label>
              <input
                type="date"
                value={dispatchDate}
                onChange={e => setDispatchDate(e.target.value)}
                className="rounded-lg border px-3 py-2 text-sm"
                style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Tech</label>
              <Select
                value={dispatchTechFilter}
                onChange={e => setDispatchTechFilter(e.target.value)}
                className="min-w-[160px]"
                style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
              >
                <option value="">All technicians</option>
                {users.map((u: { id: string; full_name: string }) => (
                  <option key={u.id} value={u.id}>{u.full_name}</option>
                ))}
              </Select>
            </div>
          </div>

          {dispatchLoading ? <Spinner /> : (
            <>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
                  Scheduled for {formatDate(dispatchDate)}
                </h3>
                {dispatchJobs.length === 0 ? (
                  <p className="text-sm py-4" style={{ color: 'var(--cafe-text-muted)' }}>No jobs scheduled for this date.</p>
                ) : dispatchTechFilter ? (
                  <div className="space-y-2">
                    {dispatchJobs.map((job: object) => (
                      <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} />
                    ))}
                  </div>
                ) : (
                  (() => {
                    const byTech = new Map<string | null, typeof dispatchJobs>()
                    for (const j of dispatchJobs) {
                      const uid = (j as { assigned_user_id?: string }).assigned_user_id ?? null
                      const key = uid ?? '__unassigned__'
                      if (!byTech.has(key)) byTech.set(key, [])
                      byTech.get(key)!.push(j)
                    }
                    const unassigned = byTech.get('__unassigned__') ?? []
                    const assigned = [...byTech.entries()].filter(([k]) => k !== '__unassigned__').sort((a, b) => {
                      const na = users.find((u: { id: string }) => u.id === a[0])?.full_name ?? ''
                      const nb = users.find((u: { id: string }) => u.id === b[0])?.full_name ?? ''
                      return na.localeCompare(nb)
                    })
                    return (
                      <div className="space-y-4">
                        {assigned.map(([uid, jobs]) => (
                          <div key={uid}>
                            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-amber)' }}>
                              {users.find((u: { id: string }) => u.id === uid)?.full_name ?? 'Tech'}
                            </p>
                            <div className="space-y-2">
                              {jobs.map((job: object) => (
                                <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} />
                              ))}
                            </div>
                          </div>
                        ))}
                        {unassigned.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Unassigned</p>
                            <div className="space-y-2">
                              {unassigned.map((job: object) => (
                                <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })()
                )}
              </div>

              {unscheduledJobs.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
                    Unscheduled ({unscheduledJobs.length})
                  </h3>
                  <div className="space-y-2">
                    {unscheduledJobs.map((job: object) => (
                      <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {view === 'week' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={() => {
                const d = new Date(weekStart)
                d.setDate(d.getDate() - 7)
                setWeekStart(d.toISOString().slice(0, 10))
              }}><ChevronLeft size={16} /></Button>
              <span className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                {formatDate(weekStart)} – {formatDate(weekEnd)}
              </span>
              <Button variant="secondary" onClick={() => {
                const d = new Date(weekStart)
                d.setDate(d.getDate() + 7)
                setWeekStart(d.toISOString().slice(0, 10))
              }}><ChevronRight size={16} /></Button>
            </div>
          </div>
          {weekLoading ? <Spinner /> : (
            <div className="overflow-x-auto">
              <div className="grid gap-2" style={{ gridTemplateColumns: '80px repeat(7, minmax(120px, 1fr))' }}>
                <div />
                {[...Array(7)].map((_, i) => {
                  const d = new Date(weekStart)
                  d.setDate(d.getDate() + i)
                  const dayStr = d.toISOString().slice(0, 10)
                  const dayName = d.toLocaleDateString('en-AU', { weekday: 'short' })
                  const dayNum = d.getDate()
                  const isToday = dayStr === new Date().toISOString().slice(0, 10)
                  return (
                    <div key={dayStr} className="text-center py-2 rounded-lg" style={{ backgroundColor: isToday ? 'rgba(245, 158, 11, 0.15)' : 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
                      <p className="text-xs font-semibold" style={{ color: 'var(--cafe-text-muted)' }}>{dayName}</p>
                      <p className="text-sm font-bold" style={{ color: 'var(--cafe-text)' }}>{dayNum}</p>
                    </div>
                  )
                })}
                {[8, 9, 10, 11, 12, 13, 14, 15, 16, 17].map(hour => (
                  <Fragment key={hour}>
                    <div className="py-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {String(hour).padStart(2, '0')}:00
                    </div>
                    {[...Array(7)].map((_, i) => {
                      const d = new Date(weekStart)
                      d.setDate(d.getDate() + i)
                      const dayStr = d.toISOString().slice(0, 10)
                      const slotStart = new Date(`${dayStr}T${String(hour).padStart(2, '0')}:00:00Z`)
                      const slotEnd = new Date(`${dayStr}T${String(hour + 1).padStart(2, '0')}:00:00Z`)
                      const inSlot = weekJobs.filter((j: { scheduled_at?: string }) => {
                        if (!j.scheduled_at) return false
                        const t = new Date(j.scheduled_at).getTime()
                        return t >= slotStart.getTime() && t < slotEnd.getTime()
                      })
                      return (
                        <div key={`${dayStr}-${hour}`} className="min-h-[44px] p-1 rounded border" style={{ backgroundColor: 'var(--cafe-bg)', borderColor: 'var(--cafe-border)' }}>
                          {inSlot.map((job: object) => (
                            <Link key={(job as { id: string }).id} to={`/auto-key/${(job as { id: string }).id}`} className="block text-xs p-1.5 rounded mb-1 hover:opacity-90" style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }}>
                              #{(job as { job_number: string }).job_number} · {(job as { title: string }).title}
                            </Link>
                          ))}
                        </div>
                      )
                    })}
                  </Fragment>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
