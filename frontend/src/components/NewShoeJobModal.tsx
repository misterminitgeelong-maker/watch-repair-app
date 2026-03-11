import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, X, ChevronRight, Tag } from 'lucide-react'
import {
  listCustomers, createCustomer, createShoe, createShoeRepairJob,
  listShoeCatalogueGroups, searchShoeCatalogueItems, formatShoePricingType,
  type Customer, type ShoeCatalogueItem, type ShoePricingType,
} from '@/lib/api'
import { Modal, Button, Input, Select, Textarea } from '@/components/ui'

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

// ── Catalogue picker ──────────────────────────────────────────────────────────
const FROM_PRICING_TYPES: ShoePricingType[] = [
  'from', 'pair_from', 'each_from', 'from_per_boot', 'from_per_strap', 'quoted_upon_inspection',
]

function isPriceAdjustable(t: ShoePricingType) {
  return FROM_PRICING_TYPES.includes(t)
}

interface SelectedItem {
  item: ShoeCatalogueItem
  quantity: number
  notes: string
  /** Only set for 'from' / quoted_upon_inspection types — the agreed price in dollars as a string */
  agreedPrice: string
}

function CataloguePicker({
  selected,
  onChange,
}: {
  selected: SelectedItem[]
  onChange: (items: SelectedItem[]) => void
}) {
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')

  const { data: groups = [] } = useQuery({
    queryKey: ['shoe-catalogue-groups'],
    queryFn: () => listShoeCatalogueGroups().then(r => r.data),
    staleTime: Infinity,
  })

  const { data: items = [] } = useQuery({
    queryKey: ['shoe-catalogue-items', search, groupFilter],
    queryFn: () => searchShoeCatalogueItems({ q: search || undefined, group: groupFilter || undefined }).then(r => r.data),
    staleTime: 30_000,
  })

  const selectedKeys = new Set(selected.map(s => s.item.key))

  function addItem(item: ShoeCatalogueItem) {
    if (selectedKeys.has(item.key)) return
    onChange([...selected, { item, quantity: 1, notes: item.notes ?? '', agreedPrice: '' }])
  }

  function removeItem(key: string) {
    onChange(selected.filter(s => s.item.key !== key))
  }

  return (
    <div>
      {/* Search + group filter */}
      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search services…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              borderColor: 'var(--cafe-border-2)',
              color: 'var(--cafe-text)',
            }}
          />
        </div>
        <select
          value={groupFilter}
          onChange={e => setGroupFilter(e.target.value)}
          className="h-9 rounded-lg border px-2 text-sm outline-none focus:ring-2"
          style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
        >
          <option value="">All categories</option>
          {groups.map(g => (
            <option key={g.id} value={g.id}>{g.label}</option>
          ))}
        </select>
      </div>

      {/* Results list */}
      <div
        className="rounded-xl border overflow-y-auto mb-4"
        style={{ maxHeight: '220px', borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
      >
        {items.length === 0 ? (
          <p className="text-center py-6 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No services found</p>
        ) : (
          items.map(item => {
            const alreadyAdded = selectedKeys.has(item.key)
            const priceLabel = formatShoePricingType(item.pricing_type as ShoePricingType, item.price_cents)
            return (
              <button
                key={item.key}
                type="button"
                disabled={alreadyAdded}
                onClick={() => addItem(item)}
                className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left text-sm border-b last:border-b-0 transition-colors"
                style={{
                  borderColor: 'var(--cafe-border)',
                  backgroundColor: alreadyAdded ? 'var(--cafe-border)' : 'transparent',
                  opacity: alreadyAdded ? 0.5 : 1,
                  cursor: alreadyAdded ? 'default' : 'pointer',
                }}
                onMouseEnter={e => { if (!alreadyAdded) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--cafe-surface)' }}
                onMouseLeave={e => { if (!alreadyAdded) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate" style={{ color: 'var(--cafe-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{item.group_label}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-semibold" style={{ color: 'var(--cafe-amber)' }}>{priceLabel}</p>
                  {alreadyAdded && (
                    <span className="text-[10px] text-green-600 font-medium">Added</span>
                  )}
                </div>
              </button>
            )
          })
        )}
      </div>

      {/* Selected items */}
      {selected.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>
            Selected services ({selected.length})
          </p>
          <div className="space-y-2">
            {selected.map(({ item, notes, agreedPrice }, idx) => (
              <div
                key={item.key}
                className="flex items-start gap-2 rounded-lg px-3 py-2"
                style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}
              >
                <Tag size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--cafe-amber)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                    {item.group_label}
                    {isPriceAdjustable(item.pricing_type as ShoePricingType)
                      ? <>
                          {' · '}
                          <span style={{ color: 'var(--cafe-amber)' }}>
                            {formatShoePricingType(item.pricing_type as ShoePricingType, item.price_cents)}
                          </span>
                        </>
                      : <> · {formatShoePricingType(item.pricing_type as ShoePricingType, item.price_cents)}</>}
                  </p>
                  {item.includes && item.includes.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {item.includes.map(inc => (
                        <li key={inc} className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>• {inc}</li>
                      ))}
                    </ul>
                  )}
                  {/* Adjustable price field for 'from' and quoted_upon_inspection types */}
                  {isPriceAdjustable(item.pricing_type as ShoePricingType) && (
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="text-xs font-semibold" style={{ color: 'var(--cafe-text-muted)' }}>Agreed $</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder={item.pricing_type === 'quoted_upon_inspection' ? '0.00' : ((item.price_cents ?? 0) / 100).toFixed(2)}
                        value={agreedPrice}
                        onChange={e => {
                          const updated = [...selected]
                          updated[idx] = { ...updated[idx], agreedPrice: e.target.value }
                          onChange(updated)
                        }}
                        className="w-24 h-7 rounded border px-2 text-xs outline-none focus:ring-1"
                        style={{
                          backgroundColor: 'var(--cafe-bg)',
                          borderColor: agreedPrice ? 'var(--cafe-amber)' : 'var(--cafe-border-2)',
                          color: 'var(--cafe-text)',
                        }}
                      />
                      {agreedPrice && (
                        <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                          = ${parseFloat(agreedPrice || '0').toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}
                  <input
                    type="text"
                    placeholder="Notes (optional)"
                    value={notes}
                    onChange={e => {
                      const updated = [...selected]
                      updated[idx] = { ...updated[idx], notes: e.target.value }
                      onChange(updated)
                    }}
                    className="mt-1.5 w-full h-7 rounded border px-2 text-xs outline-none focus:ring-1"
                    style={{
                      backgroundColor: 'var(--cafe-bg)',
                      borderColor: 'var(--cafe-border-2)',
                      color: 'var(--cafe-text)',
                    }}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removeItem(item.key)}
                  className="p-0.5 rounded hover:bg-[#F5EDE0] transition-colors"
                  style={{ color: 'var(--cafe-text-muted)' }}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
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

  // Step 2 – Shoe details
  const [shoe, setShoe] = useState({ shoe_type: '', brand: '', color: '', description_notes: '' })

  // Step 3 – Job + catalogue items
  const [job, setJob] = useState({ title: '', description: '', priority: 'normal', status: 'awaiting_go_ahead', salesperson: '', deposit_cents: '' })
  const [selectedItems, setSelectedItems] = useState<SelectedItem[]>([])

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { data: customers } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
    enabled: !preselectedCustomer,
  })

  const setC = (k: keyof typeof newCustomer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setNewCustomer(f => ({ ...f, [k]: e.target.value }))
  const setS = (k: keyof typeof shoe) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setShoe(f => ({ ...f, [k]: e.target.value }))
  const setJ = (k: keyof typeof job) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setJob(f => ({ ...f, [k]: e.target.value }))

  async function nextStep1() {
    setError('')
    if (customerMode === 'new') {
      if (!newCustomer.full_name) { setError('Customer name is required.'); return }
      setLoading(true)
      try {
        const { data } = await createCustomer(newCustomer)
        setCreatedCustomerId(data.id)
        qc.invalidateQueries({ queryKey: ['customers'] })
      } catch { setError('Failed to create customer.'); setLoading(false); return }
      setLoading(false)
    } else {
      if (!selectedCustomerId) { setError('Please select a customer.'); return }
    }
    setStep(2)
  }

  async function submit() {
    setError('')
    if (!job.title && selectedItems.length === 0) {
      setError('Please add a job title or select at least one service.')
      return
    }
    const custId = createdCustomerId || selectedCustomerId
    setLoading(true)
    try {
      const { data: shoeData } = await createShoe({ customer_id: custId, ...shoe })
      const autoTitle = job.title || selectedItems.map(s => s.item.name).join(', ')
      const { data: jobData } = await createShoeRepairJob({
        shoe_id: shoeData.id,
        title: autoTitle,
        description: job.description || undefined,
        priority: job.priority,
        status: job.status,
        salesperson: job.salesperson || undefined,
        deposit_cents: job.deposit_cents ? Math.round(parseFloat(job.deposit_cents) * 100) : 0,
        items: selectedItems.map(s => {
          // For 'from' types, use the agreed price if entered; otherwise fall back to the catalogue minimum
          const agreedCents = s.agreedPrice
            ? Math.round(parseFloat(s.agreedPrice) * 100)
            : s.item.price_cents
          return {
            catalogue_key: s.item.key,
            catalogue_group: s.item.group_id,
            item_name: s.item.name,
            pricing_type: s.item.pricing_type,
            unit_price_cents: agreedCents,
            quantity: s.quantity,
            notes: s.notes || undefined,
          }
        }),
      })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      onSuccess?.(jobData.id)
      onClose()
    } catch {
      setError('Failed to create job. Please try again.')
    }
    setLoading(false)
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
          <Select label="Shoe Type" value={shoe.shoe_type} onChange={setS('shoe_type')}>
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
          <Input label="Brand" value={shoe.brand} onChange={setS('brand')} placeholder="e.g. RM Williams" />
          <Input label="Colour" value={shoe.color} onChange={setS('color')} placeholder="e.g. Tan" />
          <Textarea
            label="Description / Condition Notes"
            value={shoe.description_notes}
            onChange={setS('description_notes')}
            placeholder="Describe the shoes and any damage…"
            rows={3}
          />
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

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>
              Services
            </p>
            <CataloguePicker selected={selectedItems} onChange={setSelectedItems} />
          </div>

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
