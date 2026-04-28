import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Camera, X } from 'lucide-react'
import {
  listCustomers, createCustomer, listWatches, createWatch, createJob,
  listCustomerAccounts,
  uploadAttachment,
  getApiErrorMessage,
  getUploadErrorMessage,
  getWatchRepairsConfig,
  type JobStatus, type Customer, type Watch, type CustomerAccount,
  type WatchCatalogueItem,
} from '@/lib/api'
import { Modal, Button, Input, Select, Textarea } from '@/components/ui'
import BrandAutocomplete from '@/components/BrandAutocomplete'
import WatchServicePicker, { type SelectedWatchService } from '@/components/WatchServicePicker'
import { STATUS_LABELS } from '@/lib/utils'

const INITIAL_STATUS_OPTIONS = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'service'] as const
const MAX_WATCHES = 5

function calculateRepairsTotal(
  items: { item: WatchCatalogueItem }[],
  combos: Array<{ keys?: string[]; total_cents?: number; battery_key?: string; band_keys?: string[]; band_discount_percent?: number }> = []
): number {
  if (items.length === 0) return 0
  const keys = new Set(items.map(i => i.item.key))
  let total = 0
  const appliedKeys = new Set<string>()

  for (const combo of combos) {
    if (combo.keys && combo.total_cents != null) {
      const match = combo.keys.every(k => keys.has(k))
      if (match) {
        total += combo.total_cents
        combo.keys.forEach(k => appliedKeys.add(k))
        break
      }
    }
  }

  const batteryCombo = combos.find(c => c.battery_key && c.band_keys)
  const hasBattery = batteryCombo && keys.has(batteryCombo.battery_key!)
  const bandSet = batteryCombo ? new Set(batteryCombo.band_keys ?? []) : new Set<string>()
  const bandDiscount = (batteryCombo?.band_discount_percent ?? 0) / 100

  for (const { item } of items) {
    if (appliedKeys.has(item.key)) continue
    let cents = item.price_cents ?? 0
    if (hasBattery && bandSet.has(item.key) && bandDiscount > 0) {
      cents = Math.round(cents * (1 - bandDiscount))
    }
    total += cents
  }
  return total
}

// ── Step indicator ────────────────────────────────────────────────────────────
function Steps({ current }: { current: number }) {
  const steps = ['Customer', 'Watches', 'Job Details', 'Photos']
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

// ── Watch form type ───────────────────────────────────────────────────────────
interface WatchForm {
  mode: 'existing' | 'new'
  selectedWatchId: string
  brand: string
  model: string
  serial_number: string
  movement_type: string
  condition_notes: string
}

function emptyWatchForm(): WatchForm {
  return { mode: 'new', selectedWatchId: '', brand: '', model: '', serial_number: '', movement_type: '', condition_notes: '' }
}

// ── NewJobModal ───────────────────────────────────────────────────────────────
interface Props {
  onClose: () => void
  preselectedCustomer?: { id: string; full_name: string }
  onSuccess?: (jobId: string) => void
}

export default function NewJobModal({ onClose, preselectedCustomer, onSuccess }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [step, setStep] = useState(preselectedCustomer ? 2 : 1)

  // Step 1 – Customer
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [selectedCustomerId, setSelectedCustomerId] = useState(preselectedCustomer?.id ?? '')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '', address: '', notes: '' })
  const [createdCustomerId, setCreatedCustomerId] = useState('')
  const [phoneMatch, setPhoneMatch] = useState<Customer | null>(null)

  // Step 2 – Watches (multi)
  const [watchCount, setWatchCount] = useState(1)
  const [watchForms, setWatchForms] = useState<WatchForm[]>([emptyWatchForm()])
  const [createdWatchIds, setCreatedWatchIds] = useState<string[]>([])
  const [activeWatchTab, setActiveWatchTab] = useState(0)

  // Step 3 – Job
  const [job, setJob] = useState({ title: '', description: '', priority: 'normal', status: 'awaiting_quote' as JobStatus, salesperson: '', collection_date: '', deposit_cents: '', pre_quote_cents: '', job_number_override: '' })
  const [selectedRepairs, setSelectedRepairs] = useState<SelectedWatchService[]>([])
  const [selectedCustomerAccountId, setSelectedCustomerAccountId] = useState('')

  // Step 4 – Photos (per watch, optional for multi)
  const [photos, setPhotos] = useState<Array<{ front: File | null; back: File | null; frontPreview: string | null; backPreview: string | null }>>(
    [{ front: null, back: null, frontPreview: null, backPreview: null }]
  )
  const frontRefs = useRef<Array<HTMLInputElement | null>>([])
  const backRefs = useRef<Array<HTMLInputElement | null>>([])

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [createdJobId, setCreatedJobId] = useState<string | null>(null)

  const { data: customers } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
    enabled: !preselectedCustomer,
  })

  const { data: repairsConfig } = useQuery({
    queryKey: ['watch-repairs-config'],
    queryFn: () => getWatchRepairsConfig().then(r => r.data),
  })

  const activeCustomerId = createdCustomerId || selectedCustomerId
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })

  const matchingAccounts = activeCustomerId
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(activeCustomerId))
    : customerAccounts

  const { data: watches } = useQuery({
    queryKey: ['watches', activeCustomerId],
    queryFn: () => listWatches(activeCustomerId).then(r => r.data),
    enabled: !!activeCustomerId,
  })

  function handleCountChange(count: number) {
    setWatchCount(count)
    setWatchForms(prev => {
      const next = [...prev]
      while (next.length < count) next.push(emptyWatchForm())
      return next.slice(0, count)
    })
    setPhotos(prev => {
      const next = [...prev]
      while (next.length < count) next.push({ front: null, back: null, frontPreview: null, backPreview: null })
      return next.slice(0, count)
    })
    if (activeWatchTab >= count) setActiveWatchTab(count - 1)
  }

  function updateWatchForm(idx: number, patch: Partial<WatchForm>) {
    setWatchForms(prev => prev.map((f, i) => i === idx ? { ...f, ...patch } : f))
  }

  const setC = (k: keyof typeof newCustomer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.value
    setNewCustomer(f => ({ ...f, [k]: value }))
    if (k === 'phone' && customers) {
      const match = customers.find((c: Customer) => c.phone && value && c.phone.replace(/\D/g, '') === value.replace(/\D/g, ''))
      setPhoneMatch(match || null)
    }
    if (k === 'phone' && !value) setPhoneMatch(null)
  }

  const setJ = (k: keyof typeof job) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setJob(f => ({ ...f, [k]: e.target.value as JobStatus }))

  function handlePhoto(watchIdx: number, side: 'front' | 'back', e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const url = URL.createObjectURL(file)
    setPhotos(prev => prev.map((p, i) => i === watchIdx
      ? { ...p, [side]: file, [`${side}Preview`]: url }
      : p
    ))
  }

  function removePhoto(watchIdx: number, side: 'front' | 'back') {
    setPhotos(prev => prev.map((p, i) => i === watchIdx
      ? { ...p, [side]: null, [`${side}Preview`]: null }
      : p
    ))
    const ref = side === 'front' ? frontRefs.current[watchIdx] : backRefs.current[watchIdx]
    if (ref) ref.value = ''
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

  async function nextStep2() {
    setError('')
    const custId = createdCustomerId || selectedCustomerId
    setLoading(true)
    const ids: string[] = []
    try {
      for (let i = 0; i < watchCount; i++) {
        const form = watchForms[i]
        if (form.mode === 'new') {
          const { data } = await createWatch({
            customer_id: custId,
            brand: form.brand,
            model: form.model,
            serial_number: form.serial_number,
            movement_type: form.movement_type,
            condition_notes: form.condition_notes,
          })
          ids.push(data.id)
          qc.invalidateQueries({ queryKey: ['watches', custId] })
        } else {
          if (!form.selectedWatchId) { setError(`Please select a watch for Watch ${i + 1}.`); setLoading(false); return }
          ids.push(form.selectedWatchId)
        }
      }
    } catch (err) { setError(getApiErrorMessage(err, 'Failed to add watch.')); setLoading(false); return }
    setCreatedWatchIds(ids)
    setLoading(false)
    setStep(3)
  }

  async function submit() {
    setError('')
    if (!job.title) { setError('Job title is required.'); return }
    // Require photos only for single-watch intake
    if (watchCount === 1 && (!photos[0].front || !photos[0].back)) {
      setError('Both front and back photos are required.')
      return
    }
    setLoading(true)
    let firstJobId: string | null = null
    try {
      for (let i = 0; i < watchCount; i++) {
        const watchId = createdWatchIds[i]
        const jobTitle = watchCount > 1 ? `${job.title} (Watch ${i + 1} of ${watchCount})` : job.title
        const { data } = await createJob({
          watch_id: watchId,
          customer_account_id: selectedCustomerAccountId || undefined,
          title: jobTitle,
          description: job.description,
          priority: job.priority,
          status: job.status,
          salesperson: job.salesperson || undefined,
          collection_date: job.collection_date || undefined,
          deposit_cents: job.deposit_cents ? Math.round(parseFloat(job.deposit_cents) * 100) : 0,
          pre_quote_cents: job.pre_quote_cents ? Math.round(parseFloat(job.pre_quote_cents) * 100) : 0,
          cost_cents: 0,
          job_number_override: (watchCount === 1 && job.job_number_override.trim()) ? job.job_number_override.trim() : undefined,
        })
        if (!firstJobId) firstJobId = data.id
        const p = photos[i]
        const uploads: Promise<unknown>[] = []
        if (p.front) uploads.push(uploadAttachment(p.front, data.id, 'watch_front'))
        if (p.back) uploads.push(uploadAttachment(p.back, data.id, 'watch_back'))
        await Promise.all(uploads)
      }
      qc.invalidateQueries({ queryKey: ['jobs'] })
      setCreatedJobId(firstJobId)
    } catch (err: unknown) {
      setError(getUploadErrorMessage(err, getApiErrorMessage(err, 'Failed to create job.')))
    }
    setLoading(false)
  }

  function finishCreate(jobId: string, shouldPrint: boolean) {
    if (shouldPrint) navigate(`/jobs/${jobId}/intake-print?autoprint=1`)
    onSuccess?.(jobId)
    onClose()
  }

  if (createdJobId) {
    return (
      <Modal title="Print Tickets" onClose={() => finishCreate(createdJobId, false)}>
        <div className="space-y-4">
          <p className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>
            {watchCount > 1 ? `${watchCount} job tickets created!` : 'Print job ticket now?'}
          </p>
          {watchCount > 1 && (
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              {watchCount} separate tickets have been created. You can print from each job's detail page.
            </p>
          )}
          <div className="rounded-lg px-3 py-3" style={{ backgroundColor: '#FEF0DC', border: '1px solid #E8D4A0' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Recommended at intake</p>
            <p className="text-sm mt-1" style={{ color: 'var(--ms-text-mid)' }}>
              Print both copies: one for workshop, one for customer.
            </p>
          </div>
          <div className="flex gap-2 pt-2">
            <Button variant="secondary" onClick={() => finishCreate(createdJobId, false)} className="flex-1">
              {watchCount > 1 ? 'Done' : 'Skip Printing'}
            </Button>
            <Button onClick={() => finishCreate(createdJobId, true)} className="flex-1 font-semibold">
              Print {watchCount > 1 ? 'First Ticket' : 'Tickets Now'}
            </Button>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="New Job Ticket" onClose={onClose}>
      <Steps current={step} />

      {preselectedCustomer && (
        <div className="mb-4 flex items-center gap-2 text-sm rounded-lg px-3 py-2" style={{ backgroundColor: '#FEF0DC', border: '1px solid #E8D4A0' }}>
          <span style={{ color: 'var(--ms-text-muted)' }}>Customer:</span>
          <span className="font-semibold" style={{ color: 'var(--ms-text)' }}>{preselectedCustomer.full_name}</span>
        </div>
      )}

      {/* ── Step 1: Customer ── */}
      {step === 1 && (
        <div className="space-y-3">
          <div className="flex gap-2 mb-1">
            <button onClick={() => setCustomerMode('existing')} className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
              style={customerMode === 'existing' ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' } : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }}>
              Existing Customer
            </button>
            <button onClick={() => setCustomerMode('new')} className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
              style={customerMode === 'new' ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' } : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }}>
              New Customer
            </button>
          </div>
          {customerMode === 'existing' ? (
            <Select label="Select Customer" value={selectedCustomerId} onChange={e => setSelectedCustomerId(e.target.value)}>
              <option value="">Choose…</option>
              {(customers ?? []).map((c: Customer) => <option key={c.id} value={c.id}>{c.full_name}{c.phone ? ` · ${c.phone}` : ''}</option>)}
            </Select>
          ) : (
            <>
              <Input label="Full Name *" value={newCustomer.full_name} onChange={setC('full_name')} placeholder="Jane Smith" autoFocus />
              <div className="grid grid-cols-2 gap-2">
                <Input label="Phone" value={newCustomer.phone} onChange={setC('phone')} placeholder="0412 345 678" />
                <Input label="Email" type="email" value={newCustomer.email} onChange={setC('email')} placeholder="jane@example.com" />
              </div>
              {phoneMatch && (
                <div className="rounded bg-yellow-100 border border-yellow-300 px-3 py-2 text-sm mt-2 flex items-center gap-2">
                  <span>Existing customer found:</span>
                  <span className="font-semibold">{phoneMatch.full_name}</span>
                  <Button variant="secondary" onClick={() => { setCustomerMode('existing'); setSelectedCustomerId(phoneMatch.id); setPhoneMatch(null) }}>Use</Button>
                </div>
              )}
              <Input label="Address" value={newCustomer.address} onChange={setC('address')} placeholder="Unit 5/36 Grange Rd, Toorak 3142" />
              <Textarea label="Notes" value={newCustomer.notes} onChange={setC('notes')} rows={2} placeholder="VIP, allergic to…" />
            </>
          )}
          {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button onClick={nextStep1} disabled={loading}>{loading ? 'Saving…' : 'Next →'}</Button>
          </div>
        </div>
      )}

      {/* ── Step 2: Watches ── */}
      {step === 2 && (
        <div className="space-y-4">
          {/* Watch count picker */}
          <div>
            <label className="block text-xs font-medium mb-2" style={{ color: 'var(--ms-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              How many watches?
            </label>
            <div className="flex gap-2">
              {Array.from({ length: MAX_WATCHES }, (_, i) => i + 1).map(n => (
                <button
                  key={n}
                  onClick={() => handleCountChange(n)}
                  className="w-10 h-10 rounded-lg text-sm font-bold border transition-colors"
                  style={watchCount === n
                    ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' }
                    : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }
                  }
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* Tabs when multiple watches */}
          {watchCount > 1 && (
            <div className="flex gap-1 border-b" style={{ borderColor: 'var(--ms-border)' }}>
              {Array.from({ length: watchCount }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveWatchTab(i)}
                  className="px-3 py-1.5 text-xs font-medium transition-colors"
                  style={{
                    borderBottom: activeWatchTab === i ? '2px solid var(--ms-accent)' : '2px solid transparent',
                    color: activeWatchTab === i ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
                    marginBottom: -1,
                  }}
                >
                  Watch {i + 1}
                </button>
              ))}
            </div>
          )}

          {/* Watch form for active tab */}
          {Array.from({ length: watchCount }, (_, i) => i).map(idx => (
            <div key={idx} className={idx === activeWatchTab ? 'space-y-3' : 'hidden'}>
              <div className="flex gap-2 mb-1">
                <button onClick={() => updateWatchForm(idx, { mode: 'existing' })} className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
                  style={watchForms[idx].mode === 'existing' ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' } : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }}>
                  Existing Watch
                </button>
                <button onClick={() => updateWatchForm(idx, { mode: 'new' })} className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
                  style={watchForms[idx].mode === 'new' ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderColor: 'var(--ms-accent)' } : { borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-mid)', backgroundColor: 'transparent' }}>
                  Add New Watch
                </button>
              </div>
              {watchForms[idx].mode === 'existing' ? (
                <Select label="Select Watch" value={watchForms[idx].selectedWatchId} onChange={e => updateWatchForm(idx, { selectedWatchId: e.target.value })}>
                  <option value="">Choose…</option>
                  {(watches ?? []).map((w: Watch) => (
                    <option key={w.id} value={w.id}>{[w.brand, w.model].filter(Boolean).join(' ') || 'Unknown watch'}{w.serial_number ? ` (S/N ${w.serial_number})` : ''}</option>
                  ))}
                </Select>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <BrandAutocomplete label="Brand" value={watchForms[idx].brand} onChange={v => updateWatchForm(idx, { brand: v })} placeholder="Rolex" autoFocus={idx === 0} />
                    <Input label="Model" value={watchForms[idx].model} onChange={e => updateWatchForm(idx, { model: e.target.value })} placeholder="Submariner" />
                  </div>
                  <Input label="Serial Number" value={watchForms[idx].serial_number} onChange={e => updateWatchForm(idx, { serial_number: e.target.value })} />
                  <Select label="Movement" value={watchForms[idx].movement_type} onChange={e => updateWatchForm(idx, { movement_type: e.target.value })}>
                    <option value="">Select…</option>
                    <option value="mechanical">Mechanical</option>
                    <option value="automatic">Automatic</option>
                    <option value="quartz">Quartz</option>
                    <option value="solar">Solar</option>
                    <option value="kinetic">Kinetic</option>
                  </Select>
                  <Textarea label="Condition on Intake" value={watchForms[idx].condition_notes} onChange={e => updateWatchForm(idx, { condition_notes: e.target.value })} rows={2} placeholder="Scratches on crystal, crown missing…" />
                </>
              )}
            </div>
          ))}

          {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
          <div className="flex justify-between pt-2">
            {preselectedCustomer
              ? <Button variant="ghost" onClick={onClose}>Cancel</Button>
              : <Button variant="ghost" onClick={() => setStep(1)}>← Back</Button>
            }
            <Button onClick={nextStep2} disabled={loading}>{loading ? 'Saving…' : 'Next →'}</Button>
          </div>
        </div>
      )}

      {/* ── Step 3: Job Details ── */}
      {step === 3 && (
        <div className="space-y-3">
          {watchCount > 1 && (
            <p className="text-xs rounded-lg px-3 py-2" style={{ backgroundColor: '#FEF0DC', color: 'var(--ms-text-mid)', border: '1px solid #E8D4A0' }}>
              These details apply to all {watchCount} watches. Each will get its own ticket numbered Watch 1–{watchCount}.
            </p>
          )}
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--ms-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Select repairs (optional)</label>
            <WatchServicePicker
              selected={selectedRepairs}
              onChange={items => {
                setSelectedRepairs(items)
                const names = items.map(i => i.item.name)
                const sumCents = calculateRepairsTotal(items, repairsConfig?.combos ?? [])
                const hasQuotedService = items.some(i => i.item.pricing_type === 'quote')
                setJob(prev => ({
                  ...prev,
                  title: names.length ? names.join(', ') : prev.title,
                  pre_quote_cents: names.length ? (sumCents / 100).toFixed(2) : prev.pre_quote_cents,
                  status: hasQuotedService ? 'awaiting_quote' : prev.status,
                }))
              }}
            />
          </div>
          <Input label="Job Title *" value={job.title} onChange={setJ('title')} placeholder="e.g. Battery replacement, Band (Orange) — or type custom" autoFocus />
          <Textarea label="Instructions / Fault Description" value={job.description} onChange={setJ('description')} rows={3} placeholder="Quick service / overhaul. Watch losing 5 min per day, crown feels loose…" />
          <div className="grid grid-cols-2 gap-3">
            <Select label="Priority" value={job.priority} onChange={setJ('priority')}>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">🔴 Urgent</option>
            </Select>
            <Select label="Initial Status" value={job.status} onChange={setJ('status')} disabled={selectedRepairs.some(i => i.item.pricing_type === 'quote')}>
              {INITIAL_STATUS_OPTIONS.map(s => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </Select>
          </div>
          {selectedRepairs.some(i => i.item.pricing_type === 'quote') && (
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              Quoted service selected → job will go to Awaiting quote for workshop review
            </p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Input label="Salesperson" value={job.salesperson} onChange={setJ('salesperson')} placeholder="Your initials or name" />
            <Input label="Collection Date" type="date" value={job.collection_date} onChange={setJ('collection_date')} />
          </div>
          {watchCount === 1 && (
            <Input label="Physical Ticket # (optional)" value={job.job_number_override} onChange={setJ('job_number_override')} placeholder="e.g. 1234 — leave blank to auto-assign" />
          )}
          <Select label="Customer Account (optional)" value={selectedCustomerAccountId} onChange={e => setSelectedCustomerAccountId(e.target.value)}>
            <option value="">No B2B account</option>
            {matchingAccounts.map((account: CustomerAccount) => (
              <option key={account.id} value={account.id}>{account.name}{account.account_code ? ` (${account.account_code})` : ''}</option>
            ))}
          </Select>
          <Input label="Deposit ($)" type="number" min="0" step="0.01" value={job.deposit_cents} onChange={setJ('deposit_cents')} placeholder="0.00" />
          <Input label="Pre-Quote ($)" type="number" min="0" step="0.01" value={job.pre_quote_cents} onChange={setJ('pre_quote_cents')} placeholder="0.00" />
          {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
          <div className="flex justify-between pt-2">
            <Button variant="ghost" onClick={() => setStep(2)}>← Back</Button>
            <Button onClick={() => { if (!job.title) { setError('Job title is required.'); return }; setError(''); setStep(4) }} disabled={!job.title}>Next →</Button>
          </div>
        </div>
      )}

      {/* ── Step 4: Watch Photos ── */}
      {step === 4 && (
        <div className="space-y-4">
          {watchCount === 1 ? (
            <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
              Take or upload two photos of the watch — one of the <strong>front</strong> (dial) and one of the <strong>back</strong> (caseback).
            </p>
          ) : (
            <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
              Photos are optional for batch intake — you can add them from each job's detail page. Front and back shown per watch below.
            </p>
          )}

          {/* Tabs for multi-watch photos */}
          {watchCount > 1 && (
            <div className="flex gap-1 border-b" style={{ borderColor: 'var(--ms-border)' }}>
              {Array.from({ length: watchCount }, (_, i) => (
                <button key={i} onClick={() => setActiveWatchTab(i)}
                  className="px-3 py-1.5 text-xs font-medium transition-colors"
                  style={{ borderBottom: activeWatchTab === i ? '2px solid var(--ms-accent)' : '2px solid transparent', color: activeWatchTab === i ? 'var(--ms-accent)' : 'var(--ms-text-muted)', marginBottom: -1 }}>
                  Watch {i + 1}
                  {(photos[i]?.front || photos[i]?.back) && <span className="ml-1 text-green-600">✓</span>}
                </button>
              ))}
            </div>
          )}

          {Array.from({ length: watchCount }, (_, idx) => idx).map(idx => (
            <div key={idx} className={idx === activeWatchTab ? 'grid grid-cols-2 gap-4' : 'hidden'}>
              {/* Front photo */}
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--ms-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  Front (Dial){watchCount === 1 ? ' *' : ''}
                </label>
                <input
                  ref={el => { frontRefs.current[idx] = el }}
                  type="file" accept="image/*" capture="environment" className="hidden"
                  onChange={e => handlePhoto(idx, 'front', e)}
                />
                {photos[idx]?.frontPreview ? (
                  <div className="relative group">
                    <img src={photos[idx].frontPreview!} alt="Watch front" className="w-full aspect-square object-cover rounded-lg" style={{ border: '1px solid var(--ms-border)' }} />
                    <button onClick={() => removePhoto(idx, 'front')} className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"><X size={14} /></button>
                  </div>
                ) : (
                  <button onClick={() => frontRefs.current[idx]?.click()} className="w-full aspect-square rounded-lg border-2 border-dashed transition-colors flex flex-col items-center justify-center gap-2"
                    style={{ borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ms-accent)'; e.currentTarget.style.backgroundColor = '#FEF0DC'; e.currentTarget.style.color = 'var(--ms-accent)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ms-border-strong)'; e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--ms-text-muted)' }}>
                    <Camera size={28} />
                    <span className="text-xs font-medium">Tap to capture</span>
                  </button>
                )}
              </div>

              {/* Back photo */}
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--ms-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  Back (Caseback){watchCount === 1 ? ' *' : ''}
                </label>
                <input
                  ref={el => { backRefs.current[idx] = el }}
                  type="file" accept="image/*" capture="environment" className="hidden"
                  onChange={e => handlePhoto(idx, 'back', e)}
                />
                {photos[idx]?.backPreview ? (
                  <div className="relative group">
                    <img src={photos[idx].backPreview!} alt="Watch back" className="w-full aspect-square object-cover rounded-lg" style={{ border: '1px solid var(--ms-border)' }} />
                    <button onClick={() => removePhoto(idx, 'back')} className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"><X size={14} /></button>
                  </div>
                ) : (
                  <button onClick={() => backRefs.current[idx]?.click()} className="w-full aspect-square rounded-lg border-2 border-dashed transition-colors flex flex-col items-center justify-center gap-2"
                    style={{ borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ms-accent)'; e.currentTarget.style.backgroundColor = '#FEF0DC'; e.currentTarget.style.color = 'var(--ms-accent)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ms-border-strong)'; e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--ms-text-muted)' }}>
                    <Camera size={28} />
                    <span className="text-xs font-medium">Tap to capture</span>
                  </button>
                )}
              </div>
            </div>
          ))}

          {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
          <div className="flex justify-between pt-2">
            <Button variant="ghost" onClick={() => setStep(3)}>← Back</Button>
            <Button onClick={submit} disabled={loading || (watchCount === 1 && (!photos[0]?.front || !photos[0]?.back))}>
              {loading ? 'Creating…' : watchCount > 1 ? `Create ${watchCount} Tickets` : 'Create Job Ticket'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
