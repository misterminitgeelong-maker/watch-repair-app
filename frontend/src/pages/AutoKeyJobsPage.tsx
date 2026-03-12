import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
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
  sendAutoKeyQuote,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  type AutoKeyProgrammingStatus,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'

const STATUSES: JobStatus[] = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'working_on',
  'awaiting_parts',
  'completed',
  'awaiting_collection',
  'collected',
  'no_go',
]

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
    title: '',
    description: '',
    vehicle_make: '',
    vehicle_model: '',
    vehicle_year: '',
    registration_plate: '',
    vin: '',
    key_type: '',
    key_quantity: '1',
    programming_status: 'pending' as AutoKeyProgrammingStatus,
    priority: 'normal' as 'low' | 'normal' | 'high' | 'urgent',
    status: 'awaiting_quote' as JobStatus,
    salesperson: '',
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

  const matchingAccounts = form.customer_id
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(form.customer_id))
    : customerAccounts

  const createMut = useMutation({
    mutationFn: async () => {
      if (!form.customer_id || !form.title.trim()) {
        throw new Error('Customer and job title are required.')
      }
      return createAutoKeyJob({
        customer_id: form.customer_id,
        customer_account_id: form.customer_account_id || undefined,
        title: form.title.trim(),
        description: form.description.trim() || undefined,
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
        <Input label="Job title *" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="e.g. Duplicate transponder key" />
        <Textarea label="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Vehicle make" value={form.vehicle_make} onChange={e => setForm(f => ({ ...f, vehicle_make: e.target.value }))} />
          <Input label="Vehicle model" value={form.vehicle_model} onChange={e => setForm(f => ({ ...f, vehicle_model: e.target.value }))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Vehicle year" type="number" value={form.vehicle_year} onChange={e => setForm(f => ({ ...f, vehicle_year: e.target.value }))} />
          <Input label="Registration" value={form.registration_plate} onChange={e => setForm(f => ({ ...f, registration_plate: e.target.value }))} />
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
            {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Deposit ($)" type="number" step="0.01" value={form.deposit} onChange={e => setForm(f => ({ ...f, deposit: e.target.value }))} />
          <Input label="Cost ($)" type="number" step="0.01" value={form.cost} onChange={e => setForm(f => ({ ...f, cost: e.target.value }))} />
        </div>
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

function AutoKeyJobCard({ job }: { job: { id: string; job_number: string; title: string; customer_id: string; customer_account_id?: string; vehicle_make?: string; vehicle_model?: string; vehicle_year?: number; registration_plate?: string; key_type?: string; key_quantity: number; programming_status: string; status: JobStatus; created_at: string; salesperson?: string } }) {
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
          <div className="flex items-center gap-2">
            <p className="text-xs font-mono font-semibold" style={{ color: 'var(--cafe-amber)' }}>#{job.job_number}</p>
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
            {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </Select>
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

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['auto-key-jobs'],
    queryFn: () => listAutoKeyJobs().then(r => r.data),
  })

  return (
    <div>
      <PageHeader
        title="Auto Key Jobs"
        action={<Button onClick={() => setShowCreate(true)}><Plus size={16} />New Auto Key Job</Button>}
      />

      {showCreate && <NewAutoKeyJobModal onClose={() => setShowCreate(false)} />}

      {isLoading ? <Spinner /> : (
        <div className="space-y-3">
          {jobs.length === 0 ? <EmptyState message="No auto key jobs yet." /> : jobs.map(job => <AutoKeyJobCard key={job.id} job={job} />)}
        </div>
      )}
    </div>
  )
}
