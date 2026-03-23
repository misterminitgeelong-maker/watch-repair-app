import { Fragment, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, BarChart3, Calendar, CalendarDays, ChevronLeft, ChevronRight, List, Map as MapIcon, MapPin, Search, X } from 'lucide-react'
import {
  createAutoKeyInvoiceFromQuote,
  createAutoKeyJob,
  createAutoKeyQuote,
  createCustomer,
  deleteAutoKeyJob,
  getApiErrorMessage,
  listCustomerAccounts,
  listAutoKeyInvoices,
  listAutoKeyJobs,
  listAutoKeyQuotes,
  listCustomers,
  listUsers,
  sendAutoKeyQuote,
  sendAutoKeyDayBeforeReminders,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  getAutoKeySummary,
  vehicleLookup,
  type AutoKeyProgrammingStatus,
  type Customer,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import MobileServicesMap from '@/components/MobileServicesMap'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { formatDate, STATUS_LABELS, JOB_STATUS_ORDER } from '@/lib/utils'

const STATUSES: JobStatus[] = [...JOB_STATUS_ORDER]

const AUTO_KEY_CLOSED_STATUSES = ['no_go', 'completed', 'awaiting_collection', 'collected'] as const
const AUTO_KEY_ACTIVE_STATUSES = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'working_on', 'en_route', 'on_site', 'awaiting_parts'] as const

const PROGRAMMING_STATUSES: AutoKeyProgrammingStatus[] = ['pending', 'in_progress', 'programmed', 'failed', 'not_required']

const AU_STATES = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'] as const

function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

function CustomerSearchSelect({ customers, value, onChange }: { customers: Customer[]; value: string; onChange: (id: string) => void }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const q = search.trim().toLowerCase()
  const filtered = q
    ? customers.filter(c =>
        c.full_name.toLowerCase().includes(q) ||
        (c.phone && c.phone.replace(/\D/g, '').includes(q.replace(/\D/g, ''))) ||
        (c.email && c.email.toLowerCase().includes(q))
      )
    : customers
  const selected = customers.find(c => c.id === value)
  const display = selected ? `${selected.full_name}${selected.phone ? ` · ${selected.phone}` : ''}` : search
  useEffect(() => { setHighlight(0) }, [search, filtered.length])
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const h = (e: MouseEvent) => { if (!el.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={containerRef} className="relative">
      <Input
        label="Search customer"
        value={open ? search : display}
        onChange={e => { setSearch(e.target.value); setOpen(true); setHighlight(0) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={e => {
          if (!open || filtered.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(i => (i + 1) % filtered.length) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(i => (i - 1 + filtered.length) % filtered.length) }
          else if (e.key === 'Enter') { e.preventDefault(); onChange(filtered[highlight].id); setOpen(false); setSearch('') }
          else if (e.key === 'Escape') setOpen(false)
        }}
        placeholder="Type name, phone or email…"
      />
      {open && (
        <ul className="absolute z-50 w-full mt-1 py-1 rounded-lg border shadow-lg overflow-y-auto max-h-48" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)' }}>
          {filtered.slice(0, 30).map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                className="w-full text-left px-3 py-2 text-sm truncate"
                style={{ color: 'var(--cafe-text)', backgroundColor: i === highlight ? '#F5EDE0' : 'transparent' }}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={e => { e.preventDefault(); onChange(c.id); setOpen(false); setSearch('') }}
              >
                {c.full_name}{c.phone ? ` · ${c.phone}` : ''}{c.email ? ` · ${c.email}` : ''}
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="px-3 py-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No customers match</li>}
        </ul>
      )}
    </div>
  )
}

function NewAutoKeyJobModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { hasFeature } = useAuth()
  const canLookupRego = hasFeature('rego_lookup')
  const [error, setError] = useState('')
  const [regoLookupError, setRegoLookupError] = useState('')
  const [regoLookupLoading, setRegoLookupLoading] = useState(false)
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '', address: '', notes: '' })
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
    rego_state: 'NSW' as string,
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

  const createMut = useMutation({
    mutationFn: async () => {
      if (!form.title.trim()) throw new Error('Job title is required.')
      let customerId = form.customer_id
      if (customerMode === 'new') {
        if (!newCustomer.full_name.trim()) throw new Error('Customer name is required.')
        const { data } = await createCustomer(newCustomer)
        customerId = data.id
        qc.invalidateQueries({ queryKey: ['customers'] })
      } else if (!customerId) {
        throw new Error('Please select a customer.')
      }
      return createAutoKeyJob({
        customer_id: customerId,
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
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create Mobile Services job.')),
  })

  return (
    <Modal title="New Mobile Services Job" onClose={onClose}>
      <div className="space-y-3">
        <div className="flex gap-2 mb-1">
          <button
            onClick={() => setCustomerMode('existing')}
            className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
            style={customerMode === 'existing' ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' } : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }}
          >Existing Customer</button>
          <button
            onClick={() => setCustomerMode('new')}
            className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
            style={customerMode === 'new' ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' } : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }}
          >New Customer</button>
        </div>
        {customerMode === 'existing' ? (
          <CustomerSearchSelect customers={customers} value={form.customer_id} onChange={id => setForm(f => ({ ...f, customer_id: id }))} />
        ) : (
          <>
            <Input label="Full Name *" value={newCustomer.full_name} onChange={e => setNewCustomer(f => ({ ...f, full_name: e.target.value }))} placeholder="Jane Smith" />
            <div className="grid grid-cols-2 gap-2">
              <Input label="Phone" value={newCustomer.phone} onChange={e => setNewCustomer(f => ({ ...f, phone: e.target.value }))} placeholder="0412 345 678" />
              <Input label="Email" type="email" value={newCustomer.email} onChange={e => setNewCustomer(f => ({ ...f, email: e.target.value }))} placeholder="jane@example.com" />
            </div>
            <Input label="Address" value={newCustomer.address} onChange={e => setNewCustomer(f => ({ ...f, address: e.target.value }))} placeholder="Optional" />
            <Textarea label="Notes" value={newCustomer.notes} onChange={e => setNewCustomer(f => ({ ...f, notes: e.target.value }))} rows={1} placeholder="Optional" />
          </>
        )}
        {customerMode === 'existing' && form.customer_id && (
          <Select label="Customer Account (optional)" value={form.customer_account_id} onChange={e => setForm(f => ({ ...f, customer_account_id: e.target.value }))}>
            <option value="">No B2B account</option>
            {matchingAccounts.map((account: CustomerAccount) => (
              <option key={account.id} value={account.id}>
                {account.name}{account.account_code ? ` (${account.account_code})` : ''}
              </option>
            ))}
          </Select>
        )}
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
        <div className="grid grid-cols-2 gap-3">
          <Input label="Vehicle make" value={form.vehicle_make} onChange={e => setForm(f => ({ ...f, vehicle_make: e.target.value }))} />
          <Input label="Vehicle model" value={form.vehicle_model} onChange={e => setForm(f => ({ ...f, vehicle_model: e.target.value }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Vehicle year" type="number" value={form.vehicle_year} onChange={e => setForm(f => ({ ...f, vehicle_year: e.target.value }))} />
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--cafe-text)' }}>Registration</label>
            <div className="flex gap-2">
              <Input
                value={form.registration_plate}
                onChange={e => { setForm(f => ({ ...f, registration_plate: e.target.value })); setRegoLookupError('') }}
                placeholder="ABC123"
                className="flex-1"
              />
              {canLookupRego ? (
                <>
                  <Select
                    value={form.rego_state}
                    onChange={e => setForm(f => ({ ...f, rego_state: e.target.value }))}
                    className="w-20 shrink-0"
                  >
                    {AU_STATES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </Select>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!form.registration_plate.trim() || regoLookupLoading}
                    onClick={async () => {
                      setRegoLookupError('')
                      setRegoLookupLoading(true)
                      try {
                        const { data } = await vehicleLookup(form.registration_plate.trim(), form.rego_state)
                        if (data.found) {
                          setForm(f => ({
                            ...f,
                            vehicle_make: data.make ?? f.vehicle_make,
                            vehicle_model: data.model ?? f.vehicle_model,
                            vehicle_year: data.year ? String(data.year) : f.vehicle_year,
                            vin: data.vin ?? f.vin,
                          }))
                        } else {
                          setRegoLookupError('Registration not found')
                        }
                      } catch (err) {
                        const status = (err as { response?: { status?: number } })?.response?.status
                        if (status === 403) {
                          setRegoLookupError('Upgrade to Pro for rego lookup')
                        } else {
                          setRegoLookupError(getApiErrorMessage(err, 'Lookup failed'))
                        }
                      } finally {
                        setRegoLookupLoading(false)
                      }
                    }}
                  >
                    {regoLookupLoading ? 'Loading…' : 'Look up'}
                  </Button>
                </>
              ) : (
                <span className="flex items-center text-xs" style={{ color: 'var(--cafe-text-muted)' }}>Upgrade for rego lookup</span>
              )}
            </div>
            {regoLookupError && <p className="text-sm mt-1" style={{ color: '#C96A5A' }}>{regoLookupError}</p>}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="VIN" value={form.vin} onChange={e => setForm(f => ({ ...f, vin: e.target.value }))} />
          <Input label="Key type" value={form.key_type} onChange={e => setForm(f => ({ ...f, key_type: e.target.value }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
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
  const [description, setDescription] = useState('Mobile service')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('120.00')
  const [tax, setTax] = useState('0.00')

  const quoteMut = useMutation({
    mutationFn: () =>
      createAutoKeyQuote(jobId, {
        line_items: [
          {
            description: description.trim() || 'Mobile service',
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
    <Modal title="Create Mobile Services Quote" onClose={onClose}>
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

function AutoKeyJobCard({ job, users, isSolo }: { job: { id: string; job_number: string; title: string; customer_id: string; customer_account_id?: string; assigned_user_id?: string; vehicle_make?: string; vehicle_model?: string; vehicle_year?: number; registration_plate?: string; key_type?: string; key_quantity: number; programming_status: string; status: JobStatus; created_at: string; salesperson?: string; scheduled_at?: string; job_address?: string; job_type?: string }; users: { id: string; full_name: string }[]; isSolo?: boolean }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showQuoteModal, setShowQuoteModal] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState('')

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

  const deleteMut = useMutation({
    mutationFn: () => deleteAutoKeyJob(job.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setShowDeleteConfirm(false)
      setDeleteError('')
    },
    onError: (err) => setDeleteError(getApiErrorMessage(err, 'Failed to delete job.')),
  })

  return (
    <>
    <Card className="p-4">
      {showQuoteModal && <CreateQuoteModal jobId={job.id} onClose={() => setShowQuoteModal(false)} />}
      <div className="flex items-start justify-between gap-3">
        <div
          className="min-w-0 flex-1 cursor-pointer"
          onClick={() => navigate(`/auto-key/${job.id}`)}
          onKeyDown={e => e.key === 'Enter' && navigate(`/auto-key/${job.id}`)}
          role="button"
          tabIndex={0}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-mono font-semibold" style={{ color: 'var(--cafe-amber)' }}>#{job.job_number}</p>
            {!isSolo && job.assigned_user_id && (
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
          <span className="text-sm font-semibold hover:underline block" style={{ color: 'var(--cafe-text)' }}>
            {job.title}
          </span>
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
            <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="inline-flex items-center gap-1 text-xs font-medium mt-1 hover:underline" style={{ color: 'var(--cafe-amber)' }}>
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

        <div className="w-56 shrink-0" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between gap-2 mb-2">
            <Badge status={job.status} />
            <button
              type="button"
              aria-label={`Delete job ${job.job_number}`}
              onClick={() => { setDeleteError(''); setShowDeleteConfirm(true) }}
              className="h-7 w-7 rounded-full flex items-center justify-center transition-colors shrink-0"
              style={{ color: '#A4664A', border: '1px solid #E7C6B7', backgroundColor: '#FFF7F3' }}
            >
              <X size={14} />
            </button>
          </div>
          <Select
            value={job.status}
            onChange={e => statusMut.mutate(e.target.value as JobStatus)}
            disabled={statusMut.isPending}
          >
            {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>)}
          </Select>
          {!isSolo && (
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
          )}
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
    {showDeleteConfirm && (
      <Modal
        title="Delete Mobile Services Job"
        onClose={() => { if (!deleteMut.isPending) { setShowDeleteConfirm(false); setDeleteError('') } }}
      >
        <div className="space-y-4">
          <p className="text-sm" style={{ color: 'var(--cafe-text)' }}>Are you sure you want to delete this job?</p>
          <div className="rounded-lg px-3 py-2" style={{ border: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>#{job.job_number} · {job.title}</p>
          </div>
          <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>This action cannot be undone.</p>
          {deleteError && <p className="text-sm" style={{ color: '#C96A5A' }}>{deleteError}</p>}
          <div className="flex gap-2 pt-2">
            <Button variant="secondary" className="flex-1" onClick={() => { if (!deleteMut.isPending) { setShowDeleteConfirm(false); setDeleteError('') } }}>Cancel</Button>
            <Button variant="danger" className="flex-1" onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}>
              {deleteMut.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    )}
    </>
  )
}

export default function AutoKeyJobsPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [view, setView] = useState<'jobs' | 'dispatch' | 'week' | 'map' | 'reports'>('dispatch')
  const [search, setSearch] = useState('')
  const [jobDirectoryView, setJobDirectoryView] = useState<'active' | 'completed'>('active')
  const [statusFilter, setStatusFilter] = useState<string>('all')
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

  const dispatchParams = view === 'dispatch' || view === 'map' ? { date_from: dispatchDate, date_to: dispatchDate, ...(dispatchTechFilter ? { assigned_user_id: dispatchTechFilter } : {}) } : undefined
  const { data: dispatchJobs = [], isLoading: dispatchLoading } = useQuery({
    queryKey: ['auto-key-jobs', 'dispatch', dispatchDate, dispatchTechFilter],
    queryFn: () => listAutoKeyJobs(dispatchParams!).then(r => r.data),
    enabled: (view === 'dispatch' || view === 'map') && !!dispatchParams,
  })

  const weekEnd = (() => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + 6)
    return d.toISOString().slice(0, 10)
  })()
  const weekParams = view === 'week' ? { date_from: weekStart, date_to: weekEnd, include_unscheduled: true } : undefined
  const { data: autoKeySummary, isLoading: summaryLoading } = useQuery({
    queryKey: ['auto-key-summary'],
    queryFn: () => getAutoKeySummary().then(r => r.data),
    enabled: view === 'reports',
  })
  const sendRemindersMut = useMutation({
    mutationFn: () => sendAutoKeyDayBeforeReminders().then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-summary'] }),
  })

  const rescheduleMut = useMutation({
    mutationFn: ({ jobId, scheduled_at }: { jobId: string; scheduled_at: string | null }) =>
      updateAutoKeyJob(jobId, scheduled_at ? { scheduled_at } : { scheduled_at: null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
    },
  })
  const { data: weekJobs = [], isLoading: weekLoading } = useQuery({
    queryKey: ['auto-key-jobs', 'week', weekStart, weekEnd],
    queryFn: () => listAutoKeyJobs(weekParams!).then(r => r.data),
    enabled: view === 'week' && !!weekParams,
  })

  const unscheduledJobs = view === 'dispatch' ? jobs.filter((j: { scheduled_at?: string }) => !j.scheduled_at) : []
  const isSolo = users.length <= 1

  const autoKeyClosedStatuses = new Set(AUTO_KEY_CLOSED_STATUSES)
  const isClosed = (status: JobStatus) => autoKeyClosedStatuses.has(status as typeof AUTO_KEY_CLOSED_STATUSES[number])
  const filteredJobs = (jobs ?? []).filter((j: { id: string; job_number: string; title: string; status: JobStatus; vehicle_make?: string; vehicle_model?: string; registration_plate?: string }) => {
    const q = search.trim().toLowerCase()
    const matchSearch = !q || j.job_number.toLowerCase().includes(q) || j.title.toLowerCase().includes(q) ||
      (j.vehicle_make && j.vehicle_make.toLowerCase().includes(q)) ||
      (j.vehicle_model && j.vehicle_model.toLowerCase().includes(q)) ||
      (j.registration_plate && j.registration_plate.toLowerCase().includes(q))
    const inDirectory = jobDirectoryView === 'active' ? !isClosed(j.status) : isClosed(j.status)
    const matchStatus = statusFilter === 'all' ? true : j.status === statusFilter
    return matchSearch && inDirectory && matchStatus
  })
  const statusOptions = jobDirectoryView === 'active' ? [...AUTO_KEY_ACTIVE_STATUSES] : [...AUTO_KEY_CLOSED_STATUSES]
  const activeCount = (jobs ?? []).filter((j: { status: JobStatus }) => !isClosed(j.status)).length
  const completedCount = (jobs ?? []).filter((j: { status: JobStatus }) => isClosed(j.status)).length

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <PageHeader
          title="Mobile Services"
          action={<Button onClick={() => setShowCreate(true)}><Plus size={16} />New Job</Button>}
        />
      </div>
      <p className="text-sm mb-5" style={{ color: 'var(--cafe-text-muted)' }}>
        Mobile and in-shop key cutting, programming, and replacement. Plan your day, track mobile vs shop work.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setView('jobs')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'jobs' ? 'bg-opacity-20' : ''}`}
            style={view === 'jobs' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <List size={16} /> Jobs
          </button>
          <button
            onClick={() => setView('dispatch')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'dispatch' ? 'bg-opacity-20' : ''}`}
            style={view === 'dispatch' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <Calendar size={16} /> Dispatch
          </button>
          <button
            onClick={() => setView('week')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'week' ? 'bg-opacity-20' : ''}`}
            style={view === 'week' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <CalendarDays size={16} /> Week
          </button>
          <button
            onClick={() => setView('map')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'map' ? 'bg-opacity-20' : ''}`}
            style={view === 'map' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <MapIcon size={16} /> Map
          </button>
          <button
            onClick={() => setView('reports')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'reports' ? 'bg-opacity-20' : ''}`}
            style={view === 'reports' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <BarChart3 size={16} /> Reports
          </button>
        </div>
      </div>

      {showCreate && <NewAutoKeyJobModal onClose={() => setShowCreate(false)} />}

      {view === 'jobs' && (
        <>
          <div className="mb-5 flex items-center gap-2">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4" style={{ color: 'var(--cafe-text-muted)' }} />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search jobs, vehicle, rego…"
                className="w-full pl-9 pr-3 py-2 rounded-lg border text-sm"
                style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
              />
            </div>
            <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
              <button
                type="button"
                onClick={() => setJobDirectoryView('active')}
                className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                style={{
                  backgroundColor: jobDirectoryView === 'active' ? 'var(--cafe-paper)' : 'transparent',
                  color: jobDirectoryView === 'active' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
                }}
              >
                Active ({activeCount})
              </button>
              <button
                type="button"
                onClick={() => setJobDirectoryView('completed')}
                className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                style={{
                  backgroundColor: jobDirectoryView === 'completed' ? 'var(--cafe-paper)' : 'transparent',
                  color: jobDirectoryView === 'completed' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
                }}
              >
                Completed ({completedCount})
              </button>
            </div>
            <Select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="min-w-[160px]"
              style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            >
              <option value="all">All statuses</option>
              {statusOptions.map(s => (
                <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>
              ))}
            </Select>
          </div>
          {isLoading ? <Spinner /> : (
            <div className="space-y-3">
              {filteredJobs.length === 0 ? (
                <EmptyState message={jobs?.length === 0 ? 'No Mobile Services jobs yet.' : 'No jobs match your filters.'} />
              ) : (
                filteredJobs.map((job: object) => <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} />)
              )}
            </div>
          )}
        </>
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
            {!isSolo && (
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
            )}
          </div>

          {dispatchLoading ? <Spinner /> : (
            <>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
                  {isSolo ? "Today's schedule" : 'Scheduled for'} {formatDate(dispatchDate)}
                </h3>
                {dispatchJobs.length === 0 ? (
                  <p className="text-sm py-4" style={{ color: 'var(--cafe-text-muted)' }}>No jobs scheduled for this date.</p>
                ) : isSolo || dispatchTechFilter ? (
                  <div className="space-y-2">
                    {dispatchJobs.map((job: object) => (
                      <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} />
                    ))}
                  </div>
                ) : (
                  (() => {
                    const byTech = new Map<string, object[]>()
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
                        {assigned.map(([uid, techJobs]) => (
                          <div key={uid}>
                            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-amber)' }}>
                              {users.find((u: { id: string }) => u.id === uid)?.full_name ?? 'Tech'}
                            </p>
                            <div className="space-y-2">
                              {techJobs.map((job: object) => (
                                <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} />
                              ))}
                            </div>
                          </div>
                        ))}
                        {unassigned.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Unassigned</p>
                            <div className="space-y-2">
                              {unassigned.map((job: object) => (
                                <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} />
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
                    <AutoKeyJobCard key={(job as { id: string }).id} job={job as Parameters<typeof AutoKeyJobCard>[0]['job']} users={users} isSolo={isSolo} />
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
            <div className="space-y-4">
              {(() => {
                const unscheduled = weekJobs.filter((j: { scheduled_at?: string }) => !j.scheduled_at)
                return (
                  <>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>
                  Unscheduled — {unscheduled.length > 0 ? 'drag onto a slot to schedule, or drop here to unschedule' : 'drop jobs here to unschedule'}
                </h3>
                <div
                    className="min-h-[52px] p-2 rounded border flex flex-wrap gap-2 content-start transition-colors"
                    style={{ backgroundColor: 'var(--cafe-bg)', borderColor: 'var(--cafe-border)', borderStyle: 'dashed' }}
                    onDragOver={e => { e.preventDefault(); (e.currentTarget as HTMLDivElement).style.backgroundColor = '#F5EDE0' }}
                    onDragLeave={e => { (e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--cafe-bg)' }}
                    onDrop={e => {
                      e.preventDefault()
                      ;(e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--cafe-bg)'
                      const jobId = e.dataTransfer.getData('application/x-autokey-job-id')
                      if (jobId) rescheduleMut.mutate({ jobId, scheduled_at: null })
                    }}
                  >
                    {unscheduled.map((job: object) => (
                      <div
                        key={(job as { id: string }).id}
                        draggable
                        onDragStart={e => {
                          e.dataTransfer.setData('application/x-autokey-job-id', (job as { id: string }).id)
                          e.dataTransfer.effectAllowed = 'move'
                        }}
                        className="cursor-grab active:cursor-grabbing shrink-0"
                      >
                        <Link to={`/auto-key/${(job as { id: string }).id}`} className="block text-xs p-1.5 rounded hover:opacity-90" style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)' }} onClick={e => e.stopPropagation()}>
                          #{(job as { job_number: string }).job_number} · {(job as { title: string }).title}
                        </Link>
                      </div>
                    ))}
                  </div>
                </div>
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
                      const newScheduledAt = slotStart.toISOString()
                      return (
                        <div
                          key={`${dayStr}-${hour}`}
                          className="min-h-[44px] p-1 rounded border transition-colors"
                          style={{ backgroundColor: 'var(--cafe-bg)', borderColor: 'var(--cafe-border)' }}
                          onDragOver={e => { e.preventDefault(); (e.currentTarget as HTMLDivElement).style.backgroundColor = '#F5EDE0' }}
                          onDragLeave={e => { (e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--cafe-bg)' }}
                          onDrop={e => {
                            e.preventDefault()
                            ;(e.currentTarget as HTMLDivElement).style.backgroundColor = 'var(--cafe-bg)'
                            const jobId = e.dataTransfer.getData('application/x-autokey-job-id')
                            if (jobId) rescheduleMut.mutate({ jobId, scheduled_at: newScheduledAt })
                          }}
                        >
                          {inSlot.map((job: object) => (
                            <div
                              key={(job as { id: string }).id}
                              draggable
                              onDragStart={e => {
                                e.dataTransfer.setData('application/x-autokey-job-id', (job as { id: string }).id)
                                e.dataTransfer.effectAllowed = 'move'
                              }}
                              className="cursor-grab active:cursor-grabbing"
                            >
                              <Link to={`/auto-key/${(job as { id: string }).id}`} className="block text-xs p-1.5 rounded mb-1 hover:opacity-90" style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }} onClick={e => e.stopPropagation()}>
                                #{(job as { job_number: string }).job_number} · {(job as { title: string }).title}
                              </Link>
                            </div>
                          ))}
                        </div>
                      )
                    })}
                  </Fragment>
                ))}
              </div>
            </div>
                  </>
                )
              })()}
          </div>
          )}
        </div>
      )}

      {view === 'map' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Date</label>
            <input
              type="date"
              value={dispatchDate}
              onChange={e => setDispatchDate(e.target.value)}
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            />
          </div>
          {dispatchLoading ? <Spinner /> : <MobileServicesMap jobs={dispatchJobs} date={dispatchDate} />}
        </div>
      )}

      {view === 'reports' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold" style={{ color: 'var(--cafe-text)' }}>Mobile Services Summary</h2>
            <Button variant="secondary" onClick={() => sendRemindersMut.mutate()} disabled={sendRemindersMut.isPending}>
              {sendRemindersMut.isPending ? 'Sending…' : 'Send day-before reminders now'}
            </Button>
          </div>
          {summaryLoading ? <Spinner /> : autoKeySummary ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Total jobs</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>{autoKeySummary.total_jobs}</p>
              </Card>
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Total revenue</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>{formatCents(autoKeySummary.total_revenue_cents)}</p>
              </Card>
              <Card className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Mobile vs shop</p>
                <p className="text-sm" style={{ color: 'var(--cafe-text)' }}>
                  Mobile: {autoKeySummary.mobile_vs_shop.mobile} · Shop: {autoKeySummary.mobile_vs_shop.shop}
                  {autoKeySummary.mobile_vs_shop.other > 0 ? ` · Other: ${autoKeySummary.mobile_vs_shop.other}` : ''}
                </p>
              </Card>
            </div>
          ) : null}
          {!isSolo && autoKeySummary && autoKeySummary.jobs_by_tech.length > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Jobs & revenue by tech</h3>
              <div className="space-y-2">
                {autoKeySummary.jobs_by_tech.map(t => (
                  <div key={t.tech_id} className="flex items-center justify-between py-2 border-b last:border-0" style={{ borderColor: 'var(--cafe-border)' }}>
                    <span style={{ color: 'var(--cafe-text)' }}>{t.tech_name}</span>
                    <span className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                      {t.job_count} job{t.job_count !== 1 ? 's' : ''} · {formatCents(t.revenue_cents)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {autoKeySummary && autoKeySummary.total_jobs === 0 && (
            <EmptyState message="No Mobile Services jobs yet. Create one to see reports." />
          )}
        </div>
      )}
    </div>
  )
}
