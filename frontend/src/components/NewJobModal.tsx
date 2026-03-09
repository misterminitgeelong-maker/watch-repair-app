import { useState, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Camera, X } from 'lucide-react'
import {
  listCustomers, createCustomer, listWatches, createWatch, createJob,
  uploadAttachment,
  type JobStatus, type Customer, type Watch,
} from '@/lib/api'
import { Modal, Button, Input, Select, Textarea } from '@/components/ui'

// ── Step indicator ────────────────────────────────────────────────────────────
function Steps({ current }: { current: number }) {
  const steps = ['Customer', 'Watch', 'Job Details', 'Photos']
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

// ── NewJobModal ───────────────────────────────────────────────────────────────
interface Props {
  onClose: () => void
  /** When provided the Customer step is skipped and the watch step loads immediately */
  preselectedCustomer?: { id: string; full_name: string }
  /** Called with the new job's id after creation so callers can navigate */
  onSuccess?: (jobId: string) => void
}

export default function NewJobModal({ onClose, preselectedCustomer, onSuccess }: Props) {
  const qc = useQueryClient()

  // Start at step 2 if customer is already known
  const [step, setStep] = useState(preselectedCustomer ? 2 : 1)

  // Step 1 – Customer
  const [customerMode, setCustomerMode] = useState<'existing' | 'new'>('existing')
  const [selectedCustomerId, setSelectedCustomerId] = useState(preselectedCustomer?.id ?? '')
  const [newCustomer, setNewCustomer] = useState({ full_name: '', email: '', phone: '', address: '', notes: '' })
  const [createdCustomerId, setCreatedCustomerId] = useState('')

  // Step 2 – Watch
  const [watchMode, setWatchMode] = useState<'existing' | 'new'>('existing')
  const [selectedWatchId, setSelectedWatchId] = useState('')
  const [newWatch, setNewWatch] = useState({ brand: '', model: '', serial_number: '', movement_type: '', condition_notes: '' })
  const [createdWatchId, setCreatedWatchId] = useState('')

  // Step 3 – Job
  const [job, setJob] = useState({ title: '', description: '', priority: 'normal', status: 'awaiting_go_ahead' as JobStatus, salesperson: '', collection_date: '', deposit_cents: '' })

  // Step 4 – Watch Photos
  const [frontPhoto, setFrontPhoto] = useState<File | null>(null)
  const [backPhoto, setBackPhoto] = useState<File | null>(null)
  const [frontPreview, setFrontPreview] = useState<string | null>(null)
  const [backPreview, setBackPreview] = useState<string | null>(null)
  const frontRef = useRef<HTMLInputElement>(null)
  const backRef = useRef<HTMLInputElement>(null)

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { data: customers } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers().then(r => r.data),
    enabled: !preselectedCustomer,
  })

  const activeCustomerId = createdCustomerId || selectedCustomerId
  const { data: watches } = useQuery({
    queryKey: ['watches', activeCustomerId],
    queryFn: () => listWatches(activeCustomerId).then(r => r.data),
    enabled: !!activeCustomerId,
  })

  const setC = (k: keyof typeof newCustomer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setNewCustomer(f => ({ ...f, [k]: e.target.value }))
  const setW = (k: keyof typeof newWatch) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setNewWatch(f => ({ ...f, [k]: e.target.value }))
  const setJ = (k: keyof typeof job) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setJob(f => ({ ...f, [k]: e.target.value as JobStatus }))

  function handlePhoto(side: 'front' | 'back', e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const url = URL.createObjectURL(file)
    if (side === 'front') { setFrontPhoto(file); setFrontPreview(url) }
    else { setBackPhoto(file); setBackPreview(url) }
  }

  function removePhoto(side: 'front' | 'back') {
    if (side === 'front') { setFrontPhoto(null); setFrontPreview(null); if (frontRef.current) frontRef.current.value = '' }
    else { setBackPhoto(null); setBackPreview(null); if (backRef.current) backRef.current.value = '' }
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
      } catch { setError('Failed to create customer.'); setLoading(false); return }
      setLoading(false)
    } else {
      if (!selectedCustomerId) { setError('Please select a customer.'); return }
    }
    setStep(2)
  }

  async function nextStep2() {
    setError('')
    const custId = createdCustomerId || selectedCustomerId
    if (watchMode === 'new') {
      setLoading(true)
      try {
        const { data } = await createWatch({ customer_id: custId, ...newWatch })
        setCreatedWatchId(data.id)
        qc.invalidateQueries({ queryKey: ['watches', custId] })
      } catch { setError('Failed to add watch.'); setLoading(false); return }
      setLoading(false)
    } else {
      if (!selectedWatchId) { setError('Please select a watch.'); return }
    }
    setStep(3)
  }

  async function submit() {
    setError('')
    if (!frontPhoto || !backPhoto) { setError('Both front and back photos are required.'); return }
    if (!job.title) { setError('Job title is required.'); return }
    const watchId = createdWatchId || selectedWatchId
    setLoading(true)
    try {
      const { data } = await createJob({
        watch_id: watchId,
        title: job.title,
        description: job.description,
        priority: job.priority,
        status: job.status,
        salesperson: job.salesperson || undefined,
        collection_date: job.collection_date || undefined,
        deposit_cents: job.deposit_cents ? Math.round(parseFloat(job.deposit_cents) * 100) : 0,
      })
      // Upload the two watch photos
      await Promise.all([
        uploadAttachment(frontPhoto, data.id, 'watch_front'),
        uploadAttachment(backPhoto, data.id, 'watch_back'),
      ])
      qc.invalidateQueries({ queryKey: ['jobs'] })
      onSuccess?.(data.id)
      onClose()
    } catch { setError('Failed to create job.') }
    setLoading(false)
  }

  return (
    <Modal title="New Job Ticket" onClose={onClose}>
      <Steps current={step} />

      {/* Customer banner when pre-selected */}
      {preselectedCustomer && (
        <div className="mb-4 flex items-center gap-2 text-sm rounded-lg px-3 py-2" style={{ backgroundColor: '#FEF0DC', border: '1px solid #E8D4A0' }}>
          <span style={{ color: 'var(--cafe-text-muted)' }}>Customer:</span>
          <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{preselectedCustomer.full_name}</span>
        </div>
      )}

      {/* ── Step 1: Customer ── */}
      {step === 1 && (
        <div className="space-y-3">
          <div className="flex gap-2 mb-1">
            <button
              onClick={() => setCustomerMode('existing')}
              className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
              style={customerMode === 'existing'
                ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' }
                : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }
              }
            >Existing Customer</button>
            <button
              onClick={() => setCustomerMode('new')}
              className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
              style={customerMode === 'new'
                ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' }
                : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }
              }
            >New Customer</button>
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

      {/* ── Step 2: Watch ── */}
      {step === 2 && (
        <div className="space-y-3">
          <div className="flex gap-2 mb-1">
            <button
              onClick={() => setWatchMode('existing')}
              className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
              style={watchMode === 'existing'
                ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' }
                : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }
              }
            >Existing Watch</button>
            <button
              onClick={() => setWatchMode('new')}
              className="flex-1 py-1.5 rounded text-sm font-medium border transition-colors"
              style={watchMode === 'new'
                ? { backgroundColor: 'var(--cafe-amber)', color: '#fff', borderColor: 'var(--cafe-amber)' }
                : { borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-mid)', backgroundColor: 'transparent' }
              }
            >Add New Watch</button>
          </div>
          {watchMode === 'existing' ? (
            <Select label="Select Watch" value={selectedWatchId} onChange={e => setSelectedWatchId(e.target.value)}>
              <option value="">Choose…</option>
              {(watches ?? []).map((w: Watch) => (
                <option key={w.id} value={w.id}>{[w.brand, w.model].filter(Boolean).join(' ') || 'Unknown watch'}{w.serial_number ? ` (S/N ${w.serial_number})` : ''}</option>
              ))}
            </Select>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <Input label="Brand" value={newWatch.brand} onChange={setW('brand')} placeholder="Rolex" autoFocus />
                <Input label="Model" value={newWatch.model} onChange={setW('model')} placeholder="Submariner" />
              </div>
              <Input label="Serial Number" value={newWatch.serial_number} onChange={setW('serial_number')} />
              <Select label="Movement" value={newWatch.movement_type} onChange={setW('movement_type')}>
                <option value="">Select…</option>
                <option value="mechanical">Mechanical</option>
                <option value="automatic">Automatic</option>
                <option value="quartz">Quartz</option>
                <option value="solar">Solar</option>
                <option value="kinetic">Kinetic</option>
              </Select>
              <Textarea label="Condition on Intake" value={newWatch.condition_notes} onChange={setW('condition_notes')} rows={2} placeholder="Scratches on crystal, crown missing…" />
            </>
          )}
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
          <Input label="Job Title *" value={job.title} onChange={setJ('title')} placeholder="Full movement service & overhaul" autoFocus />
          <Textarea label="Instructions / Fault Description" value={job.description} onChange={setJ('description')} rows={3} placeholder="Quick service / overhaul. Watch losing 5 min per day, crown feels loose…" />
          <div className="grid grid-cols-2 gap-3">
            <Select label="Priority" value={job.priority} onChange={setJ('priority')}>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">🔴 Urgent</option>
            </Select>
            <Select label="Initial Status" value={job.status} onChange={setJ('status')}>
              <option value="awaiting_go_ahead">Awaiting Go Ahead</option>
              <option value="go_ahead">Go Ahead</option>
              <option value="service">Service</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Salesperson" value={job.salesperson} onChange={setJ('salesperson')} placeholder="Your initials or name" />
            <Input label="Collection Date" type="date" value={job.collection_date} onChange={setJ('collection_date')} />
          </div>
          <Input
            label="Deposit ($)"
            type="number"
            min="0"
            step="0.01"
            value={job.deposit_cents}
            onChange={setJ('deposit_cents')}
            placeholder="0.00"
          />
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
          <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>Take or upload two photos of the watch — one of the <strong>front</strong> (dial) and one of the <strong>back</strong> (caseback).</p>

          <div className="grid grid-cols-2 gap-4">
            {/* Front photo */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--cafe-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Front (Dial) *</label>
              <input ref={frontRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={e => handlePhoto('front', e)} />
              {frontPreview ? (
                <div className="relative group">
                  <img src={frontPreview} alt="Watch front" className="w-full aspect-square object-cover rounded-lg" style={{ border: '1px solid var(--cafe-border)' }} />
                  <button onClick={() => removePhoto('front')} className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity" title="Remove"><X size={14} /></button>
                </div>
              ) : (
                <button onClick={() => frontRef.current?.click()} className="w-full aspect-square rounded-lg border-2 border-dashed transition-colors flex flex-col items-center justify-center gap-2" style={{ borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-muted)' }} onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--cafe-amber)'; e.currentTarget.style.backgroundColor = '#FEF0DC'; e.currentTarget.style.color = 'var(--cafe-amber)' }} onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--cafe-border-2)'; e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--cafe-text-muted)' }}>
                  <Camera size={28} />
                  <span className="text-xs font-medium">Tap to capture</span>
                </button>
              )}
            </div>

            {/* Back photo */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--cafe-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Back (Caseback) *</label>
              <input ref={backRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={e => handlePhoto('back', e)} />
              {backPreview ? (
                <div className="relative group">
                  <img src={backPreview} alt="Watch back" className="w-full aspect-square object-cover rounded-lg" style={{ border: '1px solid var(--cafe-border)' }} />
                  <button onClick={() => removePhoto('back')} className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity" title="Remove"><X size={14} /></button>
                </div>
              ) : (
                <button onClick={() => backRef.current?.click()} className="w-full aspect-square rounded-lg border-2 border-dashed transition-colors flex flex-col items-center justify-center gap-2" style={{ borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-muted)' }} onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--cafe-amber)'; e.currentTarget.style.backgroundColor = '#FEF0DC'; e.currentTarget.style.color = 'var(--cafe-amber)' }} onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--cafe-border-2)'; e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--cafe-text-muted)' }}>
                  <Camera size={28} />
                  <span className="text-xs font-medium">Tap to capture</span>
                </button>
              )}
            </div>
          </div>

          {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
          <div className="flex justify-between pt-2">
            <Button variant="ghost" onClick={() => setStep(3)}>← Back</Button>
            <Button onClick={submit} disabled={!frontPhoto || !backPhoto || loading}>{loading ? 'Creating…' : 'Create Job Ticket'}</Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
