import { Fragment, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, BarChart3, Calendar, CalendarDays, ChevronLeft, ChevronRight, CreditCard, LayoutGrid, List, Map as MapIcon, MapPin, Minus, Search, ShoppingCart, X } from 'lucide-react'
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
  getAutoKeyReports,
  vehicleLookup,
  type AutoKeyProgrammingStatus,
  type Customer,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import MobileServicesMap from '@/components/MobileServicesMap'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { AUTO_KEY_JOB_TYPES, MOBILE_JOB_TYPES } from '@/lib/autoKeyJobTypes'
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
    job_type: '' as string,
    job_address: '',
    scheduled_at: '',  // date only for display
    scheduled_datetime: '',  // full datetime for booking
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
      if (MOBILE_JOB_TYPES.has(form.job_type) && !form.job_address.trim()) {
        throw new Error('Address required for mobile jobs')
      }
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
        scheduled_at: form.scheduled_datetime ? new Date(form.scheduled_datetime).toISOString() : (form.scheduled_at ? form.scheduled_at + 'T09:00:00Z' : undefined),
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
        <Select label="Job type" value={form.job_type} onChange={e => setForm(f => ({ ...f, job_type: e.target.value }))}>
          <option value="">Not set</option>
          {AUTO_KEY_JOB_TYPES.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </Select>
        <Input label="Schedule date" type="date" value={form.scheduled_at} onChange={e => setForm(f => ({ ...f, scheduled_at: e.target.value }))} />
        <Input label="Book date & time (optional)" type="datetime-local" value={form.scheduled_datetime} onChange={e => setForm(f => ({ ...f, scheduled_datetime: e.target.value, scheduled_at: e.target.value ? e.target.value.slice(0, 10) : f.scheduled_at }))} />
        <Input
          label={MOBILE_JOB_TYPES.has(form.job_type) ? 'Job address *' : 'Job address'}
          value={form.job_address}
          onChange={e => setForm(f => ({ ...f, job_address: e.target.value }))}
          placeholder={MOBILE_JOB_TYPES.has(form.job_type) ? 'Where to meet customer (required for mobile jobs)' : 'Where to meet customer (optional)'}
        />
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

const POS_QUICK_ITEMS = [
  // Key cutting & blanks
  { label: 'Key cut – basic', desc: 'Basic key cutting', price: 3500 },
  { label: 'Key cut – laser', desc: 'Laser-cut key', price: 12000 },
  { label: 'Key cut – Tibbe', desc: 'Tibbe key cutting', price: 15000 },
  { label: 'Blank – transponder', desc: 'Transponder blank', price: 4500 },
  { label: 'Blank – flip key', desc: 'Flip/smart key blank', price: 8500 },
  { label: 'Blank – proximity', desc: 'Proximity key blank', price: 12000 },
  // Programming
  { label: 'Program – transponder', desc: 'Transponder key programming', price: 9500 },
  { label: 'Program – proximity', desc: 'Proximity key programming', price: 15000 },
  { label: 'Program – all keys lost', desc: 'All keys lost – full programming', price: 25000 },
  { label: 'Program – add key', desc: 'Add key to existing', price: 7500 },
  { label: 'Sync remote', desc: 'Remote/fob sync', price: 5500 },
  // Duplication & replacement
  { label: 'Duplicate – transponder', desc: 'Duplicate transponder key', price: 12000 },
  { label: 'Duplicate – flip key', desc: 'Duplicate flip key', price: 18000 },
  { label: 'Replace – lost key', desc: 'Replace lost key (cut + program)', price: 15000 },
  { label: 'Replace – all keys lost', desc: 'Replace all lost keys', price: 35000 },
  // Lockout & entry
  { label: 'Lockout – car', desc: 'Car lockout / emergency entry', price: 12000 },
  { label: 'Lockout – boot/trunk', desc: 'Boot/trunk lockout', price: 8500 },
  { label: 'Lockout – roadside', desc: 'Roadside lockout callout', price: 18000 },
  // Ignition & lock work
  { label: 'Ignition repair', desc: 'Ignition barrel repair', price: 15000 },
  { label: 'Ignition replace', desc: 'Ignition barrel replacement', price: 25000 },
  { label: 'Broken key extraction', desc: 'Extract broken key from lock', price: 8500 },
  { label: 'Door lock change', desc: 'Door lock cylinder change', price: 12000 },
  { label: 'Boot lock change', desc: 'Boot/trunk lock change', price: 9500 },
  // Service & misc
  { label: 'Service call', desc: 'Service call / travel fee', price: 5500 },
  { label: 'After hours', desc: 'After-hours surcharge', price: 3500 },
  { label: 'Diagnostic', desc: 'Key/ECU diagnostic', price: 6500 },
] as const

interface CartLine {
  id: string
  description: string
  quantity: number
  unit_price_cents: number
}

function POSView({ customers, customerAccounts, onComplete }: { customers: Customer[]; customerAccounts: CustomerAccount[]; onComplete: () => void }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [customerId, setCustomerId] = useState('')
  const [customerAccountId, setCustomerAccountId] = useState('')
  const [linkToJobId, setLinkToJobId] = useState('')
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '' })
  const [cart, setCart] = useState<CartLine[]>([])

  const { data: activeJobsForCustomer = [] } = useQuery({
    queryKey: ['auto-key-jobs', 'active', customerId],
    queryFn: () => listAutoKeyJobs({ customer_id: customerId, active_only: true }).then(r => r.data),
    enabled: !!customerId && customerMode === 'existing',
  })
  const [customDesc, setCustomDesc] = useState('')
  const [customPrice, setCustomPrice] = useState('')
  const [error, setError] = useState('')
  const [successJobId, setSuccessJobId] = useState<string | null>(null)

  const subtotal = cart.reduce((s, l) => s + l.quantity * l.unit_price_cents, 0)
  const tax = 0
  const total = subtotal + tax

  const addToCart = (description: string, unit_price_cents: number, quantity = 1) => {
    const existing = cart.find(l => l.description === description && l.unit_price_cents === unit_price_cents)
    if (existing) {
      setCart(cart.map(l => l.id === existing.id ? { ...l, quantity: l.quantity + quantity } : l))
    } else {
      setCart([...cart, { id: crypto.randomUUID(), description, quantity, unit_price_cents }])
    }
  }

  const removeFromCart = (id: string) => setCart(cart.filter(l => l.id !== id))
  const updateQty = (id: string, qty: number) => {
    if (qty < 1) removeFromCart(id)
    else setCart(cart.map(l => l.id === id ? { ...l, quantity: qty } : l))
  }

  const completeMut = useMutation({
    mutationFn: async () => {
      setError('')
      let cid = customerId
      if (customerMode === 'new') {
        if (!newCustomer.full_name.trim()) throw new Error('Customer name is required.')
        const { data } = await createCustomer(newCustomer)
        cid = data.id
        qc.invalidateQueries({ queryKey: ['customers'] })
      } else if (!cid) throw new Error('Select a customer.')

      if (cart.length === 0) throw new Error('Add at least one item.')

      const accountId = customerAccountId && customerAccounts.some((a: CustomerAccount) => a.id === customerAccountId && a.customer_ids.includes(cid))
        ? customerAccountId
        : undefined

      let job: { id: string }
      if (linkToJobId) {
        job = { id: linkToJobId }
        const quote = await createAutoKeyQuote(linkToJobId, {
          line_items: cart.map(l => ({ description: l.description, quantity: l.quantity, unit_price_cents: l.unit_price_cents })),
          tax_cents: tax,
        }).then(r => r.data)
        await createAutoKeyInvoiceFromQuote(linkToJobId, quote.id)
        await updateAutoKeyJobStatus(linkToJobId, 'completed')
      } else {
        job = await createAutoKeyJob({
          customer_id: cid,
          customer_account_id: accountId || undefined,
          title: `POS sale ${new Date().toLocaleDateString()}`,
          key_quantity: 1,
          programming_status: 'not_required',
          priority: 'normal',
          status: 'awaiting_quote',
          deposit_cents: 0,
          cost_cents: total,
        }).then(r => r.data)
        const quote = await createAutoKeyQuote(job.id, {
          line_items: cart.map(l => ({ description: l.description, quantity: l.quantity, unit_price_cents: l.unit_price_cents })),
          tax_cents: tax,
        }).then(r => r.data)
        await createAutoKeyInvoiceFromQuote(job.id, quote.id)
        await updateAutoKeyJobStatus(job.id, 'collected')
      }

      return { job }
    },
    onSuccess: ({ job }) => {
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      qc.invalidateQueries({ queryKey: ['auto-key-job', job.id] })
      setCart([])
      setCustomerId('')
      setCustomerAccountId('')
      setLinkToJobId('')
      setNewCustomer({ full_name: '', email: '', phone: '' })
      setSuccessJobId(job.id)
      onComplete()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Sale failed.')),
  })

  if (successJobId) {
    return (
      <Card className="p-8 text-center">
        <p className="text-lg font-semibold mb-2" style={{ color: 'var(--cafe-text)' }}>Sale complete</p>
        <p className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
          Invoice created (unpaid). Send to customer via email or SMS, or record payment on the job.
        </p>
        <div className="flex gap-2 justify-center flex-wrap">
          <Button variant="secondary" onClick={() => setSuccessJobId(null)}>New sale</Button>
          <Button onClick={() => { setSuccessJobId(null); navigate(`/auto-key/${successJobId}`) }}>View job & record payment</Button>
        </div>
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>Customer</h3>
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setCustomerMode('existing')}
              className={`flex-1 py-2 rounded text-sm font-medium border ${customerMode === 'existing' ? 'bg-amber-100 border-amber-400' : 'border-gray-300'}`}
              style={customerMode === 'existing' ? { backgroundColor: 'rgba(245,158,11,0.2)', borderColor: 'var(--cafe-amber)' } : {}}
            >Existing</button>
            <button
              onClick={() => setCustomerMode('new')}
              className={`flex-1 py-2 rounded text-sm font-medium border ${customerMode === 'new' ? 'bg-amber-100 border-amber-400' : 'border-gray-300'}`}
              style={customerMode === 'new' ? { backgroundColor: 'rgba(245,158,11,0.2)', borderColor: 'var(--cafe-amber)' } : {}}
            >Walk-in</button>
          </div>
          {customerMode === 'existing' ? (
            <>
              <CustomerSearchSelect customers={customers} value={customerId} onChange={id => { setCustomerId(id); setCustomerAccountId(''); setLinkToJobId('') }} />
              {customerId && (
                <>
                  <Select
                    label="B2B Account (optional)"
                    value={customerAccountId}
                    onChange={e => setCustomerAccountId(e.target.value)}
                  >
                    <option value="">Personal / no B2B</option>
                    {customerAccounts
                      .filter((a: CustomerAccount) => a.customer_ids.includes(customerId))
                      .map((a: CustomerAccount) => (
                        <option key={a.id} value={a.id}>
                          {a.name}{a.account_code ? ` (${a.account_code})` : ''}
                        </option>
                      ))}
                  </Select>
                  <Select
                    label="Link to Job (optional)"
                    value={linkToJobId}
                    onChange={e => setLinkToJobId(e.target.value)}
                  >
                    <option value="">Create new job</option>
                    {(activeJobsForCustomer ?? []).map((j: { id: string; job_number: string; vehicle_make?: string; vehicle_model?: string }) => (
                      <option key={j.id} value={j.id}>
                        {j.job_number} · {[j.vehicle_make, j.vehicle_model].filter(Boolean).join(' ') || 'No vehicle'}
                      </option>
                    ))}
                  </Select>
                </>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <Input label="Name *" value={newCustomer.full_name} onChange={e => setNewCustomer(f => ({ ...f, full_name: e.target.value }))} placeholder="Customer name" />
              <div className="grid grid-cols-2 gap-2">
                <Input label="Phone" value={newCustomer.phone} onChange={e => setNewCustomer(f => ({ ...f, phone: e.target.value }))} placeholder="0412 345 678" />
                <Input label="Email" value={newCustomer.email} onChange={e => setNewCustomer(f => ({ ...f, email: e.target.value }))} placeholder="email@example.com" />
              </div>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>Add items</h3>
          <div className="flex flex-wrap gap-2 mb-4">
            {POS_QUICK_ITEMS.map(({ label, desc, price }) => (
              <button
                key={label}
                type="button"
                onClick={() => addToCart(desc, price)}
                className="px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors"
                style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
              >
                {label} — ${(price / 100).toFixed(2)}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              className="flex-1"
              placeholder="Description"
              value={customDesc}
              onChange={e => setCustomDesc(e.target.value)}
            />
            <Input
              type="number"
              step="0.01"
              min="0"
              placeholder="Price"
              className="w-24"
              value={customPrice}
              onChange={e => setCustomPrice(e.target.value)}
            />
            <Button
              variant="secondary"
              onClick={() => {
                const cents = Math.round(parseFloat(customPrice || '0') * 100)
                if (customDesc.trim() && cents > 0) {
                  addToCart(customDesc.trim(), cents)
                  setCustomDesc('')
                  setCustomPrice('')
                }
              }}
            >
              Add
            </Button>
          </div>
        </Card>
      </div>

      <Card className="p-5 h-fit">
        <h3 className="text-sm font-semibold uppercase tracking-wide mb-4 flex items-center gap-2" style={{ color: 'var(--cafe-text-muted)' }}>
          <ShoppingCart size={16} /> Cart
        </h3>
        {cart.length === 0 ? (
          <p className="text-sm py-6 text-center" style={{ color: 'var(--cafe-text-muted)' }}>Cart empty. Add items above.</p>
        ) : (
          <div className="space-y-3 mb-4">
            {cart.map(line => (
              <div key={line.id} className="flex items-center justify-between gap-2 py-2 border-b" style={{ borderColor: 'var(--cafe-border)' }}>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--cafe-text)' }}>{line.description}</p>
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>${(line.unit_price_cents / 100).toFixed(2)} × {line.quantity}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button type="button" onClick={() => updateQty(line.id, line.quantity - 1)} className="w-7 h-7 rounded flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)' }}><Minus size={14} /></button>
                  <span className="text-sm w-6 text-center" style={{ color: 'var(--cafe-text)' }}>{line.quantity}</span>
                  <button type="button" onClick={() => updateQty(line.id, line.quantity + 1)} className="w-7 h-7 rounded flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)' }}>+</button>
                  <button type="button" onClick={() => removeFromCart(line.id)} className="w-7 h-7 rounded flex items-center justify-center" style={{ color: '#C96A5A' }}><X size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="border-t pt-4" style={{ borderColor: 'var(--cafe-border)' }}>
          <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--cafe-text-muted)' }}>Subtotal</span><span style={{ color: 'var(--cafe-text)' }}>${(subtotal / 100).toFixed(2)}</span></div>
          {tax > 0 && <div className="flex justify-between text-sm mb-1"><span style={{ color: 'var(--cafe-text-muted)' }}>Tax</span><span style={{ color: 'var(--cafe-text)' }}>${(tax / 100).toFixed(2)}</span></div>}
          <div className="flex justify-between text-lg font-bold mt-2" style={{ color: 'var(--cafe-amber)' }}><span>Total</span><span>${(total / 100).toFixed(2)}</span></div>
        </div>
        {error && <p className="text-sm mt-3" style={{ color: '#C96A5A' }}>{error}</p>}
        <Button
          className="w-full mt-4"
          onClick={() => completeMut.mutate()}
          disabled={completeMut.isPending || cart.length === 0}
        >
          <CreditCard size={16} />
          {completeMut.isPending ? 'Processing…' : 'Complete sale'}
        </Button>
      </Card>
    </div>
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
            {!isSolo && (
              <span className="text-[11px] font-medium rounded-full px-2 py-0.5" style={{ backgroundColor: job.assigned_user_id ? 'rgba(93,74,155,0.2)' : 'rgba(138,117,99,0.25)', color: job.assigned_user_id ? '#5D4A9B' : 'var(--cafe-text-muted)' }}>
                {job.assigned_user_id ? (users.find(u => u.id === job.assigned_user_id)?.full_name ?? 'Assigned') : 'Unassigned'}
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
          <p className="text-xs mt-0.5" style={{ color: job.job_address ? 'var(--cafe-text-mid)' : 'var(--cafe-text-muted)' }}>
            {job.job_address || 'No address set'}
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
              {job.job_type}
            </p>
          )}
          {job.job_address && (
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
  const [view, setView] = useState<'dashboard' | 'jobs' | 'pos' | 'dispatch' | 'week' | 'map' | 'planner' | 'reports'>('dashboard')
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
  const [reportDateFrom, setReportDateFrom] = useState('')
  const [reportDateTo, setReportDateTo] = useState('')
  const [reportPreset, setReportPreset] = useState<'today' | 'week' | 'month' | 'last_month' | 'all' | 'custom'>('month')

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['auto-key-jobs'],
    queryFn: () => listAutoKeyJobs().then(r => r.data),
  })
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
    enabled: view === 'pos' || view === 'map' || view === 'planner',
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
    enabled: view === 'pos',
  })
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })

  const dispatchParams = view === 'dispatch' || view === 'map' || view === 'planner' ? { date_from: dispatchDate, date_to: dispatchDate, ...(dispatchTechFilter ? { assigned_user_id: dispatchTechFilter } : {}) } : undefined
  const { data: dispatchJobs = [], isLoading: dispatchLoading } = useQuery({
    queryKey: ['auto-key-jobs', 'dispatch', dispatchDate, dispatchTechFilter],
    queryFn: () => listAutoKeyJobs(dispatchParams!).then(r => r.data),
    enabled: (view === 'dispatch' || view === 'map' || view === 'planner') && !!dispatchParams,
  })

  const weekEnd = (() => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + 6)
    return d.toISOString().slice(0, 10)
  })()
  const weekParams = view === 'week' ? { date_from: weekStart, date_to: weekEnd, include_unscheduled: true } : undefined

  const reportDateParams = (() => {
    if (view !== 'reports') return undefined
    if (reportPreset === 'custom' && reportDateFrom && reportDateTo) {
      return { date_from: reportDateFrom, date_to: reportDateTo }
    }
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    if (reportPreset === 'today') {
      const today = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
      return { date_from: today, date_to: today }
    }
    if (reportPreset === 'week') {
      const day = d.getDay()
      const diff = d.getDate() - day + (day === 0 ? -6 : 1)
      const mon = new Date(d)
      mon.setDate(diff)
      const sun = new Date(mon)
      sun.setDate(mon.getDate() + 6)
      return {
        date_from: mon.toISOString().slice(0, 10),
        date_to: sun.toISOString().slice(0, 10),
      }
    }
    if (reportPreset === 'month') {
      const start = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-01`
      const end = new Date(d.getFullYear(), d.getMonth() + 1, 0)
      return { date_from: start, date_to: end.toISOString().slice(0, 10) }
    }
    if (reportPreset === 'last_month') {
      const prev = new Date(d.getFullYear(), d.getMonth() - 1)
      const start = `${prev.getFullYear()}-${pad(prev.getMonth() + 1)}-01`
      const end = new Date(prev.getFullYear(), prev.getMonth() + 1, 0)
      return { date_from: start, date_to: end.toISOString().slice(0, 10) }
    }
    if (reportPreset === 'all') {
      return { date_from: '2000-01-01', date_to: '2099-12-31' }
    }
    return undefined
  })()

  const { data: autoKeyReports, isLoading: reportsLoading } = useQuery({
    queryKey: ['auto-key-reports', reportDateParams?.date_from, reportDateParams?.date_to],
    queryFn: () => getAutoKeyReports(reportDateParams!).then(r => r.data),
    enabled: view === 'reports' && !!reportDateParams,
  })
  const sendRemindersMut = useMutation({
    mutationFn: () => sendAutoKeyDayBeforeReminders().then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-reports'] }),
  })

  const statusMut = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: JobStatus }) => updateAutoKeyJobStatus(jobId, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
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
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setView('dashboard')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'dashboard' ? 'bg-opacity-20' : ''}`}
            style={view === 'dashboard' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <LayoutGrid size={16} /> Dashboard
          </button>
          <button
            onClick={() => setView('jobs')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'jobs' ? 'bg-opacity-20' : ''}`}
            style={view === 'jobs' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <List size={16} /> Jobs
          </button>
          <button
            onClick={() => setView('pos')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'pos' ? 'bg-opacity-20' : ''}`}
            style={view === 'pos' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <CreditCard size={16} /> POS
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
            onClick={() => setView('planner')}
            className={`flex items-center gap-2 px-4 py-3 min-h-11 rounded-lg text-sm font-medium transition-colors touch-manipulation ${view === 'planner' ? 'bg-opacity-20' : ''}`}
            style={view === 'planner' ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
          >
            <CalendarDays size={16} /> Day Planner
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

      {view === 'dashboard' && (
        <>
          <div className="mb-5 flex items-center justify-between gap-3 flex-wrap">
            <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
              <button
                type="button"
                onClick={() => { setJobDirectoryView('active'); setStatusFilter('all') }}
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
                onClick={() => { setJobDirectoryView('completed'); setStatusFilter('all') }}
                className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
                style={{
                  backgroundColor: jobDirectoryView === 'completed' ? 'var(--cafe-paper)' : 'transparent',
                  color: jobDirectoryView === 'completed' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
                }}
              >
                Completed ({completedCount})
              </button>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative flex-1 max-w-xs">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4" style={{ color: 'var(--cafe-text-muted)' }} />
                <input
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search…"
                  className="w-full pl-9 pr-3 py-2 rounded-lg border text-sm"
                  style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
                />
              </div>
              <Select
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}
                className="min-w-[140px]"
                style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
              >
                <option value="all">All stages</option>
                {statusOptions.map(s => (
                  <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>
                ))}
              </Select>
            </div>
          </div>
          {isLoading ? <Spinner /> : filteredJobs.length === 0 ? (
            <EmptyState message={jobs?.length === 0 ? 'No Mobile Services jobs yet.' : 'No jobs match your filters.'} />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 overflow-x-auto">
              {(statusFilter === 'all' ? statusOptions : statusOptions.filter(s => s === statusFilter)).map((status) => {
                const jobsInStatus = filteredJobs.filter((j: { status: JobStatus }) => j.status === status)
                return (
                  <Card key={status} className="overflow-hidden min-w-[240px]">
                    <div
                      className="px-4 py-3.5 flex items-center justify-between"
                      style={{ borderBottom: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
                    >
                      <p className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {STATUS_LABELS[status] ?? status.replace(/_/g, ' ')}
                      </p>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ backgroundColor: '#EEE6DA', color: 'var(--cafe-text-mid)' }}>
                        {jobsInStatus.length}
                      </span>
                    </div>
                    <div>
                      {jobsInStatus.length === 0 ? (
                        <p className="px-4 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No jobs in this stage.</p>
                      ) : (
                        jobsInStatus.map((j: object, i: number) => {
                          const job = j as { id: string; job_number: string; title: string; status: JobStatus; vehicle_make?: string; vehicle_model?: string; registration_plate?: string; created_at: string; job_type?: string }
                          return (
                            <div
                              key={job.id}
                              className="px-4 py-3"
                              style={{ borderBottom: i < jobsInStatus.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <Link to={`/auto-key/${job.id}`} className="text-sm font-medium hover:underline" style={{ color: 'var(--cafe-amber)' }}>
                                    {job.title}
                                  </Link>
                                  <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                                    #{job.job_number} · {formatDate(job.created_at)}
                                  </p>
                                </div>
                                <Badge status={job.status} />
                              </div>
                              {(job.vehicle_make || job.vehicle_model || job.registration_plate) && (
                                <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-mid)' }}>
                                  {job.vehicle_make || ''} {job.vehicle_model || ''}{job.registration_plate ? ` · ${job.registration_plate}` : ''}
                                </p>
                              )}
                              {job.job_type && (
                                <p className="text-[11px] mt-1" style={{ color: 'var(--cafe-text-muted)' }}>{job.job_type}</p>
                              )}
                              <select
                                value={job.status}
                                className="w-full mt-2 rounded-md px-2 py-1.5 text-xs outline-none"
                                style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
                                onChange={e => statusMut.mutate({ jobId: job.id, status: e.target.value as JobStatus })}
                                disabled={statusMut.isPending}
                              >
                                {statusOptions.map(s => (
                                  <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>
                                ))}
                              </select>
                            </div>
                          )
                        })
                      )}
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </>
      )}

      {view === 'pos' && (
        <POSView
          customers={customers}
          customerAccounts={customerAccounts}
          onComplete={() => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })}
        />
      )}

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
            {users.length > 1 && (
              <>
                <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Tech</label>
                <Select
                  value={dispatchTechFilter}
                  onChange={e => setDispatchTechFilter(e.target.value)}
                  className="min-w-[160px]"
                  style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
                >
                  <option value="">All techs</option>
                  {users.map((u: { id: string; full_name: string }) => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
                </Select>
              </>
            )}
          </div>
          {dispatchLoading ? <Spinner /> : <MobileServicesMap jobs={dispatchJobs} date={dispatchDate} customers={customers} />}
        </div>
      )}

      {view === 'planner' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-4">
            <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Date</label>
            <input
              type="date"
              value={dispatchDate}
              onChange={e => setDispatchDate(e.target.value)}
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            />
            {users.length > 1 && (
              <>
                <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Tech</label>
                <Select
                  value={dispatchTechFilter}
                  onChange={e => setDispatchTechFilter(e.target.value)}
                  className="min-w-[160px]"
                  style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
                >
                  <option value="">All techs</option>
                  {users.map((u: { id: string; full_name: string }) => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
                </Select>
              </>
            )}
          </div>
          {dispatchLoading ? (
            <Spinner />
          ) : (
            <>
              <Card className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
                  {formatDate(dispatchDate)} — {dispatchJobs.length} job{dispatchJobs.length !== 1 ? 's' : ''}
                </h3>
                {dispatchJobs.length === 0 ? (
                  <p className="text-sm py-4" style={{ color: 'var(--cafe-text-muted)' }}>No jobs scheduled for this date.</p>
                ) : (
                  <div className="space-y-3">
                    {[...dispatchJobs]
                      .sort((a: { scheduled_at?: string }, b: { scheduled_at?: string }) => {
                        const ta = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0
                        const tb = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0
                        return ta - tb
                      })
                      .map((job: { id: string; job_number: string; title: string; customer_id: string; scheduled_at?: string; job_address?: string; vehicle_make?: string; vehicle_model?: string }) => {
                        const customer = customers.find((c: { id: string }) => c.id === job.customer_id)
                        const timeStr = job.scheduled_at ? new Date(job.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'
                        return (
                          <div
                            key={job.id}
                            className="flex items-start gap-4 py-3 border-b last:border-b-0"
                            style={{ borderColor: 'var(--cafe-border)' }}
                          >
                            <span className="shrink-0 w-12 text-sm font-semibold" style={{ color: 'var(--cafe-amber)' }}>{timeStr}</span>
                            <div className="flex-1 min-w-0">
                              <Link to={`/auto-key/${job.id}`} className="font-medium hover:underline" style={{ color: 'var(--cafe-text)' }}>
                                #{job.job_number} · {job.title}
                              </Link>
                              <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                                {customer?.full_name ?? '—'}
                                {job.vehicle_make || job.vehicle_model ? ` · ${[job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}` : ''}
                              </p>
                              {job.job_address && (
                                <p className="text-xs mt-0.5 flex items-center gap-1" style={{ color: 'var(--cafe-text-mid)' }}>
                                  <MapPin size={12} /> {job.job_address}
                                </p>
                              )}
                            </div>
                            <Link
                              to={`/auto-key/${job.id}`}
                              className="shrink-0 px-3 py-1.5 rounded text-xs font-medium"
                              style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }}
                            >
                              View
                            </Link>
                          </div>
                        )
                      })}
                  </div>
                )}
              </Card>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>Map — where to go</h3>
                <MobileServicesMap jobs={dispatchJobs} date={dispatchDate} customers={customers} />
              </div>
            </>
          )}
        </div>
      )}

      {view === 'reports' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium" style={{ color: 'var(--cafe-text-muted)' }}>Date range:</span>
              {(['today', 'week', 'month', 'last_month', 'all'] as const).map(preset => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setReportPreset(preset)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${reportPreset === preset ? '' : ''}`}
                  style={reportPreset === preset ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' } : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}
                >
                  {preset === 'today' ? 'Today' : preset === 'week' ? 'This Week' : preset === 'month' ? 'This Month' : preset === 'last_month' ? 'Last Month' : 'All Time'}
                </button>
              ))}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={reportPreset === 'custom'}
                  onChange={e => setReportPreset(e.target.checked ? 'custom' : 'month')}
                />
                <span style={{ color: 'var(--cafe-text-muted)' }}>Custom</span>
              </label>
              {reportPreset === 'custom' && (
                <div className="flex items-center gap-2">
                  <Input
                    type="date"
                    value={reportDateFrom}
                    onChange={e => setReportDateFrom(e.target.value)}
                    className="w-36"
                  />
                  <span style={{ color: 'var(--cafe-text-muted)' }}>to</span>
                  <Input
                    type="date"
                    value={reportDateTo}
                    onChange={e => setReportDateTo(e.target.value)}
                    className="w-36"
                  />
                </div>
              )}
            </div>
            <Button variant="secondary" onClick={() => sendRemindersMut.mutate()} disabled={sendRemindersMut.isPending}>
              {sendRemindersMut.isPending ? 'Sending…' : 'Send day-before reminders now'}
            </Button>
          </div>

          {reportsLoading ? <Spinner /> : autoKeyReports ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card className="p-5" style={{ borderLeft: '4px solid var(--cafe-amber)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Total Jobs</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>{autoKeyReports.summary.total_jobs}</p>
                </Card>
                <Card className="p-5" style={{ borderLeft: '4px solid var(--cafe-amber)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Total Revenue</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>{formatCents(autoKeyReports.summary.total_revenue_cents)}</p>
                </Card>
                <Card className="p-5" style={{ borderLeft: '4px solid var(--cafe-amber)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Avg Job Value</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--cafe-text)' }}>{formatCents(autoKeyReports.summary.avg_job_value_cents)}</p>
                </Card>
                <Card className="p-5" style={{ borderLeft: '4px solid var(--cafe-amber)' }}>
                  <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Mobile vs Shop</p>
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                    Mobile: {autoKeyReports.summary.mobile_count} ({autoKeyReports.summary.mobile_pct}%) · Shop: {autoKeyReports.summary.shop_count} ({autoKeyReports.summary.shop_pct}%)
                  </p>
                </Card>
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card className="p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Jobs by Type</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left border-b" style={{ borderColor: 'var(--cafe-border)' }}>
                          <th className="py-2 pr-4 font-medium" style={{ color: 'var(--cafe-text-muted)' }}>Job Type</th>
                          <th className="py-2 pr-4 font-medium text-right" style={{ color: 'var(--cafe-text-muted)' }}>Jobs</th>
                          <th className="py-2 pr-4 font-medium text-right" style={{ color: 'var(--cafe-text-muted)' }}>Revenue</th>
                          <th className="py-2 font-medium text-right" style={{ color: 'var(--cafe-text-muted)' }}>Avg Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {autoKeyReports.jobs_by_type.map(row => (
                          <tr key={row.job_type} className="border-b last:border-0" style={{ borderColor: 'var(--cafe-border)' }}>
                            <td className="py-2 pr-4" style={{ color: 'var(--cafe-text)' }}>{row.job_type}</td>
                            <td className="py-2 pr-4 text-right" style={{ color: 'var(--cafe-text)' }}>{row.jobs}</td>
                            <td className="py-2 pr-4 text-right" style={{ color: 'var(--cafe-text)' }}>{formatCents(row.revenue_cents)}</td>
                            <td className="py-2 text-right" style={{ color: 'var(--cafe-text)' }}>{formatCents(row.avg_value_cents)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
                <Card className="p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Jobs by Tech</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left border-b" style={{ borderColor: 'var(--cafe-border)' }}>
                          <th className="py-2 pr-4 font-medium" style={{ color: 'var(--cafe-text-muted)' }}>Tech</th>
                          <th className="py-2 pr-4 font-medium text-right" style={{ color: 'var(--cafe-text-muted)' }}>Jobs</th>
                          <th className="py-2 font-medium text-right" style={{ color: 'var(--cafe-text-muted)' }}>Revenue</th>
                        </tr>
                      </thead>
                      <tbody>
                        {autoKeyReports.jobs_by_tech.length === 0 ? (
                          <tr><td colSpan={3} className="py-4 text-center text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No data</td></tr>
                        ) : (
                          autoKeyReports.jobs_by_tech.map(t => (
                            <tr key={t.tech_id} className="border-b last:border-0" style={{ borderColor: 'var(--cafe-border)' }}>
                              <td className="py-2 pr-4" style={{ color: 'var(--cafe-text)' }}>{t.tech_name}</td>
                              <td className="py-2 pr-4 text-right" style={{ color: 'var(--cafe-text)' }}>{t.job_count}</td>
                              <td className="py-2 text-right" style={{ color: 'var(--cafe-text)' }}>{formatCents(t.revenue_cents)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card className="p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Jobs by Status (Live Pipeline)</h3>
                  <div className="flex flex-wrap gap-2">
                    {autoKeyReports.jobs_by_status.map(s => (
                      <div
                        key={s.status}
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg"
                        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
                      >
                        <span className="text-sm" style={{ color: 'var(--cafe-text)' }}>{s.label}</span>
                        <span className="text-sm font-semibold" style={{ color: 'var(--cafe-amber)' }}>{s.count}</span>
                      </div>
                    ))}
                  </div>
                </Card>
                <Card className="p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Week on Week (Last 8 Weeks)</h3>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {autoKeyReports.week_on_week.map((w, i) => (
                      <div key={i} className="flex items-center justify-between py-1.5 border-b last:border-0 text-sm" style={{ borderColor: 'var(--cafe-border)' }}>
                        <span style={{ color: 'var(--cafe-text-muted)' }}>{w.week_label}</span>
                        <span style={{ color: 'var(--cafe-text)' }}>
                          {w.jobs} jobs · {formatCents(w.revenue_cents)}
                        </span>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </>
          ) : (
            <EmptyState message="No report data. Select a date range." />
          )}
        </div>
      )}
    </div>
  )
}
