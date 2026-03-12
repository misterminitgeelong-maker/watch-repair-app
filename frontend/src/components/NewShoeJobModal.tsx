import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import {
  listCustomers, createCustomer, createShoe, createShoeRepairJob,
  addShoeToJob, appendShoeRepairJobItems,
  listCustomerAccounts,
  getApiErrorMessage,
  type Customer,
  type CustomerAccount,
} from '@/lib/api'
import ShoeServicePicker, { buildShoeRepairJobItemsPayload, type SelectedShoeService } from '@/components/ShoeServicePicker'
import { Modal, Button, Input, Select, Textarea } from '@/components/ui'

type IntakeShoe = {
  shoe_type: string
  brand: string
  color: string
  description_notes: string
  services: SelectedShoeService[]
}

function newIntakeShoe(): IntakeShoe {
  return { shoe_type: '', brand: '', color: '', description_notes: '', services: [] }
}

function toItemPayload(services: SelectedShoeService[], pairIndex: number, pairCount: number) {
  const withPrefix = pairCount > 1
  return buildShoeRepairJobItemsPayload(services).map(item => ({
    ...item,
    notes: withPrefix
      ? `Pair ${pairIndex + 1}${item.notes ? ` - ${item.notes}` : ''}`
      : item.notes,
  }))
}

function buildShoeContextLabel(shoe: IntakeShoe, idx: number) {
  const bits = [shoe.shoe_type, shoe.brand, shoe.color].map(v => v.trim()).filter(Boolean)
  return bits.length > 0 ? bits.join(' - ') : `Pair ${idx + 1}`
}

// ── Step indicator ────────────────────────────────────────────────────────────
function Steps({ current }: { current: number }) {
  const steps = ['Customer', 'Shoe', 'Job & Services']
  return (
    <div className="flex items-center gap-1 mb-5">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full ${
            i + 1 === current ? 'bg-[#A07028] text-white' :
            i + 1 < current ? 'bg-green-100 text-green-700' :
            'bg-[#F0EBE0] text-[#9B7860]'
          }`}>
            <span className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold border border-current">
              {i + 1 < current ? '✓' : i + 1}
            </span>
            {s}
          </div>
          {i < steps.length - 1 && <ChevronRight size={12} className="text-[#D5C4A8]" />}
        </div>
      ))}
    </div>
  )
}

// ── Main Modal ────────────────────────────────────────────────────────────────
interface Props {
  onClose: () => void
  preselectedCustomer?: { id: string; full_name: string }
  onSuccess?: (jobId: string) => void
}

export default function NewShoeJobModal({ onClose, preselectedCustomer, onSuccess }: Props) {
  const qc = useQueryClient()
  const [step, setStep] = useState(preselectedCustomer ? 2 : 1)

  // Step 1 – Customer
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [selectedCustomerId, setSelectedCustomerId] = useState(preselectedCustomer?.id ?? '')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '', address: '', notes: '' })
  const [createdCustomerId, setCreatedCustomerId] = useState('')

  // Step 2 / 3 – Shoes + services
  const [shoeCount, setShoeCount] = useState(1)
  const [shoes, setShoes] = useState<IntakeShoe[]>([newIntakeShoe()])

  // Step 3 – Job fields
  const [job, setJob] = useState({ title: '', description: '', priority: 'normal', status: 'awaiting_go_ahead', salesperson: '', deposit_cents: '' })
  const [selectedCustomerAccountId, setSelectedCustomerAccountId] = useState('')

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [createdJobId, setCreatedJobId] = useState<string | null>(null)

  const { data: customers } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
    enabled: !preselectedCustomer,
  })

  const activeCustomerId = createdCustomerId || selectedCustomerId
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const matchingAccounts = activeCustomerId
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(activeCustomerId))
    : customerAccounts

  const setC = (k: keyof typeof newCustomer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setNewCustomer(f => ({ ...f, [k]: e.target.value }))
  const setJ = (k: keyof typeof job) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setJob(f => ({ ...f, [k]: e.target.value }))

  function updateShoe(idx: number, patch: Partial<IntakeShoe>) {
    setShoes(prev => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }

  function changeShoeCount(nextCount: number) {
    setShoeCount(nextCount)
    setShoes(prev => {
      if (nextCount <= prev.length) return prev.slice(0, nextCount)
      const added = Array.from({ length: nextCount - prev.length }, () => newIntakeShoe())
      return [...prev, ...added]
    })
  }

  async function nextStep1() {
    setError('')
    if (customerMode === 'new') {
      if (!newCustomer.full_name) { setError('Customer name is required.'); return }
      setLoading(true)
      try {
        const { data } = await createCustomer(newCustomer)
        setCreatedCustomerId(data.id)
        qc.invalidateQueries({ queryKey: ['customers'] })
      } catch (err) { setError(getApiErrorMessage(err, 'Failed to create customer.')); setLoading(false); return }
      setLoading(false)
    } else {
      if (!selectedCustomerId) { setError('Please select a customer.'); return }
    }
    setStep(2)
  }

  async function submit() {
    setError('')
    const anyServices = shoes.some(s => s.services.length > 0)
    if (!job.title && !anyServices) {
      setError('Please add a job title or select at least one service for a pair.')
      return
    }
    const custId = createdCustomerId || selectedCustomerId
    setLoading(true)
    try {
      const createdShoeIds: string[] = []
      for (const intakeShoe of shoes) {
        const { data } = await createShoe({
          customer_id: custId,
          shoe_type: intakeShoe.shoe_type || undefined,
          brand: intakeShoe.brand || undefined,
          color: intakeShoe.color || undefined,
          description_notes: intakeShoe.description_notes || undefined,
        })
        createdShoeIds.push(data.id)
      }

      const autoTitle =
        job.title ||
        (() => {
          const names = Array.from(new Set(shoes.flatMap(s => s.services.map(it => it.item.name))))
          return names.length ? names.join(', ') : `Shoe repair (${shoes.length} pair${shoes.length === 1 ? '' : 's'})`
        })()

      const firstItems = toItemPayload(shoes[0].services, 0, shoes.length)
      const { data: jobData } = await createShoeRepairJob({
        shoe_id: createdShoeIds[0],
        customer_account_id: selectedCustomerAccountId || undefined,
        title: autoTitle,
        description: job.description || undefined,
        priority: job.priority,
        status: job.status,
        salesperson: job.salesperson || undefined,
        deposit_cents: job.deposit_cents ? Math.round(parseFloat(job.deposit_cents) * 100) : 0,
        items: firstItems,
      })

      for (let i = 1; i < createdShoeIds.length; i += 1) {
        await addShoeToJob(jobData.id, createdShoeIds[i])
        const itemsForPair = toItemPayload(shoes[i].services, i, shoes.length)
        if (itemsForPair.length > 0) {
          await appendShoeRepairJobItems(jobData.id, itemsForPair)
        }
      }

      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      setCreatedJobId(jobData.id)
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to create job. Please try again.'))
    }
    setLoading(false)
  }

  function finishCreate(jobId: string, shouldPrint: boolean) {
    if (shouldPrint) {
      window.open(`/shoe-repairs/${jobId}/intake-print?autoprint=1`, '_blank', 'noopener,noreferrer')
    }
    onSuccess?.(jobId)
    onClose()
  }

  if (createdJobId) {
    return (
      <Modal title="Print Tickets" onClose={() => finishCreate(createdJobId, false)}>
        <div className="space-y-4">
          <p className="text-base font-semibold" style={{ color: 'var(--cafe-text)' }}>
            Print job tickets now?
          </p>
          <div className="rounded-lg px-3 py-3" style={{ backgroundColor: '#FEF0DC', border: '1px solid #E8D4A0' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
              Recommended at intake
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-mid)' }}>
              Print both copies now: one for workshop, one for customer.
            </p>
          </div>
          <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
            This will open the browser print flow. You can also print later from the desktop job details page.
          </p>
          <div className="flex gap-2 pt-2">
            <Button variant="secondary" onClick={() => finishCreate(createdJobId, false)} className="flex-1">
              Skip Printing
            </Button>
            <Button onClick={() => finishCreate(createdJobId, true)} className="flex-1 font-semibold">
              Print Tickets Now
            </Button>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="New Shoe Repair Job" onClose={onClose}>
      <Steps current={step} />

      {error && (
        <p className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: 'rgba(201,106,90,0.1)', color: '#C96A5A' }}>
          {error}
        </p>
      )}

      {/* ── Step 1: Customer ── */}
      {step === 1 && (
        <div className="space-y-4">
          <div className="flex gap-2">
            {(['existing', 'new'] as const).map(mode => (
              <button
                key={mode}
                type="button"
                onClick={() => setCustomerMode(mode)}
                className="flex-1 rounded-lg py-2 text-sm font-medium transition-colors border"
                style={{
                  backgroundColor: customerMode === mode ? 'var(--cafe-amber)' : 'var(--cafe-surface)',
                  color: customerMode === mode ? '#fff' : 'var(--cafe-text-mid)',
                  borderColor: customerMode === mode ? 'var(--cafe-amber)' : 'var(--cafe-border-2)',
                }}
              >
                {mode === 'existing' ? 'Existing Customer' : 'New Customer'}
              </button>
            ))}
          </div>
          {customerMode === 'existing' ? (
            <Select
              label="Select Customer"
              value={selectedCustomerId}
              onChange={e => setSelectedCustomerId(e.target.value)}
            >
              <option value="">Choose…</option>
              {(customers ?? []).map((c: Customer) => (
                <option key={c.id} value={c.id}>{c.full_name}{c.phone ? ` · ${c.phone}` : ''}</option>
              ))}
            </Select>
          ) : (
            <>
              <Input label="Full Name *" value={newCustomer.full_name} onChange={setC('full_name')} placeholder="Jane Smith" />
              <Input label="Phone" value={newCustomer.phone ?? ''} onChange={setC('phone')} placeholder="+61 4xx xxx xxx" />
              <Input label="Email" value={newCustomer.email ?? ''} onChange={setC('email')} placeholder="jane@example.com" />
            </>
          )}
          <Button onClick={nextStep1} disabled={loading} className="w-full">
            {loading ? 'Saving…' : 'Continue'}
          </Button>
        </div>
      )}

      {/* ── Step 2: Shoe Details ── */}
      {step === 2 && (
        <div className="space-y-4">
          <Select
            label="How many pairs are being booked in?"
            value={String(shoeCount)}
            onChange={e => changeShoeCount(Number(e.target.value))}
          >
            {Array.from({ length: 15 }, (_, i) => i + 1).map(n => (
              <option key={n} value={n}>{n} pair{n === 1 ? '' : 's'}</option>
            ))}
          </Select>

          {shoes.map((shoe, idx) => (
            <div
              key={idx}
              className="rounded-xl border p-3 space-y-3"
              style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-bg)' }}
            >
              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                Pair {idx + 1}
              </p>
              <Select
                label="Shoe Type"
                value={shoe.shoe_type}
                onChange={e => updateShoe(idx, { shoe_type: e.target.value })}
              >
                <option value="">Select type (optional)</option>
                <option>Dress shoes</option>
                <option>Boots</option>
                <option>Sneakers</option>
                <option>Sandals / Thongs</option>
                <option>Heels / Stilettos</option>
                <option>Work boots</option>
                <option>Birkenstocks</option>
                <option>Other</option>
              </Select>
              <Input
                label="Brand"
                value={shoe.brand}
                onChange={e => updateShoe(idx, { brand: e.target.value })}
                placeholder="e.g. RM Williams"
              />
              <Input
                label="Colour"
                value={shoe.color}
                onChange={e => updateShoe(idx, { color: e.target.value })}
                placeholder="e.g. Tan"
              />
              <Textarea
                label="Description / Condition Notes"
                value={shoe.description_notes}
                onChange={e => updateShoe(idx, { description_notes: e.target.value })}
                placeholder="Describe the shoes and any damage…"
                rows={3}
              />
            </div>
          ))}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)} className="flex-1">Back</Button>
            <Button onClick={() => setStep(3)} className="flex-1">Continue</Button>
          </div>
        </div>
      )}

      {/* ── Step 3: Job details + catalogue ── */}
      {step === 3 && (
        <div className="space-y-4">
          <Input
            label="Job Title (optional — auto-filled from services)"
            value={job.title}
            onChange={setJ('title')}
            placeholder="e.g. Heel & sole replacement"
          />

          {shoes.map((shoe, idx) => (
            <div
              key={idx}
              className="rounded-xl border p-3"
              style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-bg)' }}
            >
              <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>
                Services for Pair {idx + 1}
              </p>
              <ShoeServicePicker
                selected={shoe.services}
                onChange={services => updateShoe(idx, { services })}
                contextLabel={buildShoeContextLabel(shoe, idx)}
              />
            </div>
          ))}

          <Textarea
            label="Additional Notes"
            value={job.description}
            onChange={setJ('description')}
            placeholder="Any extra instructions or customer requests…"
            rows={2}
          />
          <div className="grid grid-cols-2 gap-3">
            <Select label="Priority" value={job.priority} onChange={setJ('priority')}>
              <option value="normal">Normal</option>
              <option value="urgent">Urgent</option>
              <option value="low">Low</option>
            </Select>
            <Select label="Status" value={job.status} onChange={setJ('status')}>
              <option value="awaiting_quote">Awaiting Quote</option>
              <option value="awaiting_go_ahead">Awaiting Go Ahead</option>
              <option value="go_ahead">Go Ahead Given</option>
              <option value="working_on">Working On</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Salesperson" value={job.salesperson} onChange={setJ('salesperson')} placeholder="Name" />
            <Input label="Deposit ($)" type="number" step="0.01" value={job.deposit_cents} onChange={setJ('deposit_cents')} placeholder="0.00" />
          </div>
          <Select
            label="Customer Account (optional)"
            value={selectedCustomerAccountId}
            onChange={e => setSelectedCustomerAccountId(e.target.value)}
          >
            <option value="">No B2B account</option>
            {matchingAccounts.map((account: CustomerAccount) => (
              <option key={account.id} value={account.id}>
                {account.name}{account.account_code ? ` (${account.account_code})` : ''}
              </option>
            ))}
          </Select>

          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(2)} className="flex-1">Back</Button>
            <Button onClick={submit} disabled={loading} className="flex-1">
              {loading ? 'Creating…' : 'Create Job'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
