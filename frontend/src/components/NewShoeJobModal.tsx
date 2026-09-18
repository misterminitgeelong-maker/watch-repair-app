import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import {
  listCustomers, createCustomer, createShoe, createShoeRepairJob,
  addShoeToJob, appendShoeRepairJobItems,
  listCustomerAccounts,
  uploadShoeAttachment,
  getApiErrorMessage,
  trackingSmsWarning,
  type CustomerAccount,
} from '@/lib/api'
import ShoeServicePicker, { buildShoeRepairJobItemsPayload, type SelectedShoeService, SHOE_TYPE_GROUPS } from '@/components/ShoeServicePicker'
import { Modal, Button, Input, Select, Textarea } from '@/components/ui'
import { CustomerSearchSelect } from '@/components/CustomerSearchSelect'
import { STATUS_LABELS } from '@/lib/utils'
import {
  preparePhotoFile,
  getPhotoPrepareErrorMessage,
  uploadBatchWithRetry,
  describeUploadFailures,
  initialUploadProgress,
  isOffline,
  OFFLINE_UPLOAD_MESSAGE,
  type UploadProgress,
} from '@/lib/photoUpload'
import { IntakeWarningBanner } from '@/lib/intakeWarnings'
import { useAuth } from '@/context/AuthContext'
import { useIntakeDraft } from '@/hooks/useIntakeDraft'
import { draftScope, photoMetaFromFile, type DraftPhotoMeta } from '@/lib/draftStorage'
import DraftRestoredNotice from '@/components/DraftRestoredNotice'
import IntakeSubmitStatus from '@/components/IntakeSubmitStatus'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'

const SHOE_INITIAL_STATUS_OPTIONS = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'working_on'] as const

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
    <div className="mb-5 flex items-center gap-1" aria-label={`Step ${current} of ${steps.length}: ${steps[current - 1]}`}>
      {steps.map((s, i) => (
        <div key={s} className="flex shrink-0 items-center gap-1">
          <div className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${
            i + 1 === current ? 'bg-[#A07028] text-white' :
            i + 1 < current ? 'bg-green-100 text-green-700' :
            'bg-[#F0EBE0] text-[#9B7860]'
          }`}>
            <span className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold border border-current">
              {i + 1 < current ? '✓' : i + 1}
            </span>
            <span className={i + 1 === current ? 'inline' : 'hidden sm:inline'}>{s}</span>
          </div>
          {i < steps.length - 1 && <ChevronRight size={12} className="hidden text-[#D5C4A8] sm:block" />}
        </div>
      ))}
    </div>
  )
}

// ── Draft ─────────────────────────────────────────────────────────────────────
const DRAFT_KIND = 'shoe-intake'

type ShoeIntakeDraft = {
  step: number
  customerMode: 'existing' | 'new'
  selectedCustomerId: string
  newCustomer: { full_name: string; email: string; phone: string; address: string; notes: string }
  shoeCount: number
  shoes: IntakeShoe[]
  job: {
    title: string
    description: string
    priority: string
    status: string
    salesperson: string
    deposit_cents: string
    collection_date: string
  }
  selectedCustomerAccountId: string
  /** Photo names/sizes only — Files cannot be stored, so they are reselected. */
  photoMeta: DraftPhotoMeta[]
}

function draftHasContent(d: ShoeIntakeDraft): boolean {
  if (d.job.title.trim() || d.job.description.trim()) return true
  if (d.customerMode === 'new' && d.newCustomer.full_name.trim()) return true
  if (d.selectedCustomerId) return true
  return d.shoes.some(s => s.shoe_type || s.brand.trim() || s.color.trim() || s.description_notes.trim() || s.services.length > 0)
}

// ── Main Modal ────────────────────────────────────────────────────────────────
interface Props {
  onClose: () => void
  preselectedCustomer?: { id: string; full_name: string }
  onSuccess?: (jobId: string) => void
}

export default function NewShoeJobModal({ onClose, preselectedCustomer, onSuccess }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { tenantId, activeSiteTenantId, sessionUserId } = useAuth()
  const { online } = useOnlineStatus()
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
  const [job, setJob] = useState({ title: '', description: '', priority: 'normal', status: 'awaiting_go_ahead', salesperson: '', deposit_cents: '', collection_date: '' })
  const [selectedCustomerAccountId, setSelectedCustomerAccountId] = useState('')

  const [intakePhotos, setIntakePhotos] = useState<Array<{ file: File; preview: string }>>([])
  const [photoLoading, setPhotoLoading] = useState(false)
  const photoInputRef = useRef<HTMLInputElement>(null)

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [createdJobId, setCreatedJobId] = useState<string | null>(null)
  const [intakeWarnings, setIntakeWarnings] = useState<string[]>([])
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null)
  const [submitStage, setSubmitStage] = useState<string | null>(null)
  const [draftPhotoCount, setDraftPhotoCount] = useState(0)

  // Records created by an earlier, partly-failed submit. Reused on retry so a
  // second attempt never creates duplicate shoes or a duplicate job.
  const createdShoeIdsRef = useRef<string[]>([])
  const createdJobIdRef = useRef<string | null>(null)
  const submittingRef = useRef(false)

  const busy = loading || photoLoading

  const requestClose = useCallback(() => {
    if (busy) return
    if (step > 1 && !createdJobId) {
      if (!window.confirm('Close this intake? Your typed details are kept as a draft, but photos must be reselected.')) return
    }
    onClose()
  }, [busy, step, createdJobId, onClose])

  useEffect(() => () => {
    intakePhotos.forEach(p => URL.revokeObjectURL(p.preview))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- revoke on unmount only

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
    ? customerAccounts.filter((a: CustomerAccount) => (a.customer_ids ?? []).includes(activeCustomerId))
    : customerAccounts

  // ── Draft preservation ──────────────────────────────────────────────────────
  const scope = draftScope(activeSiteTenantId || tenantId, sessionUserId)
  const photoMeta = useMemo(() => intakePhotos.map(p => photoMetaFromFile(p.file)), [intakePhotos])
  const draftValue = useMemo<ShoeIntakeDraft>(
    () => ({
      step,
      customerMode,
      selectedCustomerId,
      newCustomer,
      shoeCount,
      shoes,
      job,
      selectedCustomerAccountId,
      photoMeta,
    }),
    [step, customerMode, selectedCustomerId, newCustomer, shoeCount, shoes, job, selectedCustomerAccountId, photoMeta],
  )

  const restoreDraft = useCallback((d: ShoeIntakeDraft) => {
    if (!preselectedCustomer) {
      setCustomerMode(d.customerMode)
      setSelectedCustomerId(d.selectedCustomerId)
      setNewCustomer(d.newCustomer)
    }
    const count = Math.max(1, Math.min(d.shoeCount || 1, 15))
    setShoeCount(count)
    setShoes(Array.from({ length: count }, (_, i) => ({ ...newIntakeShoe(), ...(d.shoes?.[i] ?? {}) })))
    setJob(prev => ({ ...prev, ...d.job }))
    setSelectedCustomerAccountId(d.selectedCustomerAccountId ?? '')
    setDraftPhotoCount((d.photoMeta ?? []).length)
    setStep(Math.min(Math.max(1, d.step || 1), 3))
  }, [preselectedCustomer])

  const draft = useIntakeDraft<ShoeIntakeDraft>({
    kind: DRAFT_KIND,
    scope,
    value: draftValue,
    enabled: !createdJobId && !loading,
    hasContent: draftHasContent,
    onRestore: restoreDraft,
  })

  function handleDiscardDraft() {
    draft.discardDraft()
    setDraftPhotoCount(0)
    setIntakePhotos(prev => {
      for (const p of prev) URL.revokeObjectURL(p.preview)
      return []
    })
    setShoeCount(1)
    setShoes([newIntakeShoe()])
    setJob({ title: '', description: '', priority: 'normal', status: 'awaiting_go_ahead', salesperson: '', deposit_cents: '', collection_date: '' })
    setSelectedCustomerAccountId('')
    if (!preselectedCustomer) {
      setCustomerMode('existing')
      setSelectedCustomerId('')
      setNewCustomer({ full_name: '', email: '', phone: '', address: '', notes: '' })
    }
    setError('')
    setStep(preselectedCustomer ? 2 : 1)
  }

  const setC = (k: keyof typeof newCustomer) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setNewCustomer(f => ({ ...f, [k]: e.target.value }))
  const setJ = (k: keyof typeof job) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setJob(f => ({ ...f, [k]: e.target.value }))


  function updateShoe(idx: number, patch: Partial<IntakeShoe>) {
    setShoes(prev => prev.map((row, i) => {
      if (i !== idx) return row
      // If shoe_type is being changed, filter out invalid services
      if (patch.shoe_type !== undefined && patch.shoe_type !== row.shoe_type) {
        const newType = patch.shoe_type
        let filteredServices = row.services
        if (newType) {
          filteredServices = row.services.filter(svc => {
            const types = svc.item.applicable_shoe_types
            if (Array.isArray(types)) {
              return types.includes(newType)
            }
            // fallback to group filter for legacy items
            return SHOE_TYPE_GROUPS[newType]?.includes(svc.item.group_id)
          })
        }
        return { ...row, ...patch, services: filteredServices }
      }
      return { ...row, ...patch }
    }))
  }

  function changeShoeCount(nextCount: number) {
    setShoeCount(nextCount)
    setShoes(prev => {
      if (nextCount <= prev.length) return prev.slice(0, nextCount)
      const added = Array.from({ length: nextCount - prev.length }, () => newIntakeShoe())
      return [...prev, ...added]
    })
  }

  function nextStep1() {
    setError('')
    if (customerMode === 'new') {
      if (!newCustomer.full_name) { setError('Customer name is required.'); return }
    } else if (!selectedCustomerId) {
      setError('Please select a customer.')
      return
    }
    setStep(2)
  }

  async function handleIntakePhotos(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    e.target.value = ''
    if (!files.length) return
    setPhotoLoading(true)
    setError('')
    try {
      const prepared: Array<{ file: File; preview: string }> = []
      for (const file of files) {
        const compressed = await preparePhotoFile(file)
        prepared.push({ file: compressed, preview: URL.createObjectURL(compressed) })
      }
      setIntakePhotos(prev => {
        for (const p of prev) URL.revokeObjectURL(p.preview)
        return prepared
      })
    } catch (err: unknown) {
      setError(getPhotoPrepareErrorMessage(err, 'Could not process photos.'))
    } finally {
      setPhotoLoading(false)
    }
  }

  function removeIntakePhoto(index: number) {
    setIntakePhotos(prev => {
      const next = [...prev]
      const removed = next.splice(index, 1)[0]
      if (removed) URL.revokeObjectURL(removed.preview)
      return next
    })
  }

  async function submit() {
    // Re-entrancy guard: a double tap on a slow phone must not create two jobs.
    if (submittingRef.current) return
    setError('')
    const anyServices = shoes.some(s => s.services.length > 0)
    if (!job.title && !anyServices) {
      setError('Please add a job title or select at least one service for a pair.')
      return
    }
    if (isOffline()) {
      setError('You are offline. Reconnect before creating the job — your details are saved as a draft.')
      return
    }
    submittingRef.current = true
    setLoading(true)
    setUploadProgress(null)
    setSubmitStage('Creating job…')
    const warnings: string[] = []
    try {
      let customerId = createdCustomerId || selectedCustomerId
      if (customerMode === 'new' && !customerId) {
        const { data } = await createCustomer(newCustomer)
        customerId = data.id
        setCreatedCustomerId(data.id)
        qc.invalidateQueries({ queryKey: ['customers'] })
      }

      // Resume from whatever a previous failed attempt already created.
      const createdShoeIds = createdShoeIdsRef.current
      for (let i = createdShoeIds.length; i < shoes.length; i += 1) {
        const intakeShoe = shoes[i]
        const { data } = await createShoe({
          customer_id: customerId,
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

      let jobId = createdJobIdRef.current
      if (!jobId) {
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
          collection_date: job.collection_date || undefined,
          items: firstItems,
        })
        jobId = jobData.id
        createdJobIdRef.current = jobId
        const smsMsg = trackingSmsWarning(jobData.tracking_sms_skipped_reason)
        if (smsMsg) warnings.push(smsMsg)
      }

      for (let i = 1; i < createdShoeIds.length; i += 1) {
        await addShoeToJob(jobId, createdShoeIds[i])
        const itemsForPair = toItemPayload(shoes[i].services, i, shoes.length)
        if (itemsForPair.length > 0) {
          await appendShoeRepairJobItems(jobId, itemsForPair)
        }
      }

      // The job exists from here on; photo problems are reported, not fatal.
      if (intakePhotos.length > 0) {
        setSubmitStage(null)
        setUploadProgress({ ...initialUploadProgress(intakePhotos.length), phase: 'preparing', message: `Preparing ${intakePhotos.length} photo${intakePhotos.length === 1 ? '' : 's'}…` })
        const result = await uploadBatchWithRetry(
          intakePhotos.map((p, i) => ({ file: p.file, label: `Photo ${i + 1}` })),
          (f: File) => uploadShoeAttachment(f, jobId, 'intake'),
          { onProgress: setUploadProgress },
        )
        const failureMsg = describeUploadFailures(result.failures)
        if (failureMsg) warnings.push(failureMsg)
      }

      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      setIntakeWarnings(warnings)
      draft.clearSavedDraft()
      setCreatedJobId(jobId)
    } catch (err) {
      if (createdJobIdRef.current) {
        // The ticket exists — surface it instead of inviting a resubmit that
        // would duplicate it.
        setIntakeWarnings([
          ...warnings,
          `The job was created, but finishing it failed: ${getApiErrorMessage(err, 'please check the job page.')} Add any missing pairs, services or photos from the job page.`,
        ])
        draft.clearSavedDraft()
        setCreatedJobId(createdJobIdRef.current)
      } else {
        setError(getApiErrorMessage(err, 'Failed to create job. Please try again.'))
      }
    }
    submittingRef.current = false
    setSubmitStage(null)
    setLoading(false)
  }

  function finishCreate(jobId: string, shouldPrint: boolean) {
    if (shouldPrint) {
      navigate(`/shoe-repairs/${jobId}/intake-print?autoprint=1`)
    }
    onSuccess?.(jobId)
    onClose()
  }

  if (createdJobId) {
    return (
      <Modal title="Print Tickets" onClose={() => finishCreate(createdJobId, false)}>
        <div className="space-y-4">
          <IntakeWarningBanner messages={intakeWarnings} />
          <p className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>
            Print job tickets now?
          </p>
          <div className="rounded-lg px-3 py-3" style={{ backgroundColor: '#FEF0DC', border: '1px solid #E8D4A0' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
              Recommended at intake
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--ms-text-mid)' }}>
              Print both copies now: one for workshop, one for customer.
            </p>
          </div>
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
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
    <Modal title="New Shoe Repair Job" onClose={requestClose} closeDisabled={busy} mobileFullScreen>
      <DraftRestoredNotice
        savedAt={draft.restoredAt}
        onDiscard={handleDiscardDraft}
        photosNeedReselect={draftPhotoCount > 0}
        photoCount={draftPhotoCount}
      />
      <Steps current={step} />

      {error && (
        <p className="mb-4 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--ms-error) 10%, transparent)', color: 'var(--ms-error)' }}>
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
                className="min-h-11 flex-1 rounded-lg border py-2 text-sm font-medium transition-colors"
                style={{
                  backgroundColor: customerMode === mode ? 'var(--ms-accent)' : 'var(--ms-surface)',
                  color: customerMode === mode ? '#fff' : 'var(--ms-text-mid)',
                  borderColor: customerMode === mode ? 'var(--ms-accent)' : 'var(--ms-border-strong)',
                }}
              >
                {mode === 'existing' ? 'Existing Customer' : 'New Customer'}
              </button>
            ))}
          </div>
          {customerMode === 'existing' ? (
            <CustomerSearchSelect customers={customers ?? []} value={selectedCustomerId} onChange={setSelectedCustomerId} />
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
              style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)' }}
            >
              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
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

          {/* Photo upload widget */}
          <div className="rounded-xl border p-3 space-y-3" style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)' }}>
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
              Intake Photos (optional)
            </p>
            <input
              ref={photoInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              className="hidden"
              onChange={handleIntakePhotos}
            />
            <Button type="button" variant="secondary" disabled={photoLoading} onClick={() => photoInputRef.current?.click()}>
              {photoLoading ? 'Processing…' : intakePhotos.length ? 'Replace photos' : 'Add photos'}
            </Button>
            {intakePhotos.length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {intakePhotos.map((p, i) => (
                  <div key={i} className="relative">
                    <img src={p.preview} alt="" className="w-full aspect-square object-cover rounded-lg" style={{ border: '1px solid var(--ms-border)' }} />
                    <button type="button" onClick={() => removeIntakePhoto(i)} className="absolute top-1 right-1 bg-red-500 text-white rounded-full px-1.5 text-xs">×</button>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              Photos attach to the job when you submit on the next step.
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)} className="flex-1" disabled={busy}>Back</Button>
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
              style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)' }}
            >
              <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>
                Services for Pair {idx + 1}
              </p>
              <ShoeServicePicker
                selected={shoe.services}
                onChange={services => updateShoe(idx, { services })}
                contextLabel={buildShoeContextLabel(shoe, idx)}
                shoeType={shoe.shoe_type}
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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select label="Priority" value={job.priority} onChange={setJ('priority')}>
              <option value="normal">Normal</option>
              <option value="urgent">Urgent</option>
              <option value="low">Low</option>
            </Select>
            <Select label="Status" value={job.status} onChange={setJ('status')}>
              {SHOE_INITIAL_STATUS_OPTIONS.map(s => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input label="Salesperson" value={job.salesperson} onChange={setJ('salesperson')} placeholder="Name" />
            <Input label="Collection Date" type="date" value={job.collection_date} onChange={setJ('collection_date')} />
          </div>
          <Input label="Deposit ($)" type="number" step="0.01" value={job.deposit_cents} onChange={setJ('deposit_cents')} placeholder="0.00" />
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

          {!online && !loading && (
            <p className="text-sm" style={{ color: '#6A4A10' }}>
              {OFFLINE_UPLOAD_MESSAGE} Your typed details stay saved as a draft.
            </p>
          )}
          <IntakeSubmitStatus progress={uploadProgress} stageMessage={submitStage} offline={!online} />

          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(2)} className="flex-1" disabled={busy}>Back</Button>
            <Button onClick={submit} disabled={busy || !online} className="flex-1">
              {loading ? 'Creating…' : 'Create Job'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
