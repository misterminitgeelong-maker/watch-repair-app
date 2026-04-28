import { useState, useRef, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ChevronLeft, ArrowRight, Clock, Paperclip, History, FileText, Plus, Download, Upload, Camera, Pencil, Printer, MessageSquare } from 'lucide-react'
import {
  DEFAULT_PAGE_SIZE,
  getJob, quickStatusAction, updateJobStatus, updateJob, listQuotes,
  listWorkLogs,
  listAttachments, uploadAttachment,
  getStatusHistory, getSmsLog,
  resendJobNotification,
  listCustomerAccounts, getWatch, getCustomer,
  getWatchMovementQuote,
  getApiErrorMessage,
  getUploadErrorMessage,
  listUsers,
  createQuote, sendQuote,
  type JobStatus, type RepairJob, type CustomerAccount, type TenantUser,
} from '@/lib/api'
import { Card, PageHeader, Badge, Button, Modal, Select, Spinner, EmptyState, Input, Textarea } from '@/components/ui'
import { flattenInfinitePages, useOffsetPaginatedQuery } from '@/hooks/useOffsetPaginatedQuery'
import { SecureAttachmentImage, SecureAttachmentLink } from '@/components/SecureAttachment'
import MovementAutocomplete from '@/components/MovementAutocomplete'
import { formatDate, STATUS_LABELS, JOB_STATUS_ORDER } from '@/lib/utils'
import { WorkflowRail, WATCH_WORKFLOW_STEPS } from '@/components/WorkflowRail'
import LogWorkModal from '@/components/LogWorkModal'

const STATUS_FLOW: Record<JobStatus, JobStatus | null> = {
  awaiting_quote:      'awaiting_go_ahead',
  awaiting_go_ahead:   'go_ahead',
  go_ahead:            'working_on',
  no_go:               null,
  working_on:          'completed',
  awaiting_parts:      'working_on',
  parts_to_order:      'sent_to_labanda',
  sent_to_labanda:     'quoted_by_labanda',
  quoted_by_labanda:   'awaiting_parts',
  service:             'completed',
  completed:           'awaiting_collection',
  awaiting_collection: 'collected',
  collected:           null,
  en_route:            'on_site',
  on_site:             'completed',
  pending_booking:     null,
  booked:              null,
  awaiting_customer_details: null,
  quote_sent:                    null,
  awaiting_booking_confirmation: null,
  booking_confirmed:             null,
  booking_on_hold:               null,
  booking_completed:             null,
  job_delayed:                   null,
  work_completed:                null,
  invoice_paid:                  null,
  failed_job:                    null,
}

// ── Image compression helper ──────────────────────────────────────────────────
function compressImage(file: File, maxDim = 1500, quality = 0.8): Promise<File> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width > maxDim || height > maxDim) {
        if (width >= height) { height = Math.round((height / width) * maxDim); width = maxDim }
        else { width = Math.round((width / height) * maxDim); height = maxDim }
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      canvas.getContext('2d')!.drawImage(img, 0, 0, width, height)
      canvas.toBlob(
        (blob) => resolve(blob ? new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }) : file),
        'image/jpeg',
        quality,
      )
    }
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file) }
    img.src = url
  })
}

// ── Step note suggestions per destination status ──────────────────────────────
const STATUS_STEP_NOTES: Partial<Record<JobStatus, string[]>> = {
  go_ahead: [
    'Customer approved the quote — proceeding with repair.',
    'Go ahead confirmed by customer.',
    'Customer called to confirm approval.',
  ],
  working_on: [
    'Movement disassembled for inspection.',
    'Ultrasonic cleaning started.',
    'Reassembly in progress.',
    'Movement lubricated and timing underway.',
    'Waiting on bench time — repair to start shortly.',
  ],
  awaiting_parts: [
    'Awaiting mainspring from supplier.',
    'Awaiting crown / stem.',
    'Awaiting crystal replacement.',
    'Service kit ordered — ETA to be confirmed.',
    'Parts on backorder.',
  ],
  parts_to_order: [
    'Parts identified and being ordered.',
    'Sent parts list to supplier.',
    'Awaiting supplier confirmation.',
  ],
  sent_to_labanda: [
    'Movement sent to Labanda for specialist service.',
    'Forwarded to Labanda — mainspring replacement required.',
    'Sent to Labanda for full movement overhaul.',
  ],
  quoted_by_labanda: [
    'Quote received from Labanda — awaiting customer approval.',
    'Labanda quote in — will contact customer.',
  ],
  service: [
    'Service started.',
    'Routine service in progress.',
  ],
  completed: [
    'Full service complete — movement cleaned, lubricated, and timed.',
    'Crystal replacement complete — tested.',
    'Crown / stem replacement complete.',
    'Repair complete — movement running to specification.',
    'Service complete — regulated to within +/- 10 sec/day.',
  ],
  awaiting_collection: [
    'Job complete — customer notified for collection.',
    'Ready for pickup.',
    'SMS sent to customer.',
  ],
  collected: [
    'Collected by customer — payment received.',
    'Watch collected.',
  ],
}

// ── Step-note modal ────────────────────────────────────────────────────────────
function StepNoteModal({
  targetStatus,
  onConfirm,
  onClose,
  isPending,
}: {
  targetStatus: JobStatus
  onConfirm: (note: string) => void
  onClose: () => void
  isPending: boolean
}) {
  const suggestions = STATUS_STEP_NOTES[targetStatus] ?? []
  const [note, setNote] = useState(suggestions[0] ?? '')
  return (
    <Modal title={`Move to: ${STATUS_LABELS[targetStatus]}`} onClose={onClose}>
      <div className="space-y-3">
        {suggestions.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>Quick notes</p>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => setNote(s)}
                  className="rounded-full px-3 py-1 text-xs transition-colors"
                  style={{
                    backgroundColor: note === s ? 'var(--ms-accent)' : 'var(--ms-surface)',
                    color: note === s ? 'var(--ms-sidebar-act-text)' : 'var(--ms-text-mid)',
                    border: `1px solid ${note === s ? 'var(--ms-accent)' : 'var(--ms-border-strong)'}`,
                    fontWeight: note === s ? 600 : 400,
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <Textarea
          label="Note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Add a note about this step…"
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onConfirm(note)} disabled={isPending}>
            {isPending ? 'Updating…' : 'Confirm'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Create-and-send quote modal (awaiting_quote fast flow) ────────────────────
function CreateSendQuoteModal({ jobId, onClose, onSent }: { jobId: string; onClose: () => void; onSent: () => void }) {
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [taxPct, setTaxPct] = useState('0')
  const [step, setStep] = useState<'form' | 'sending' | 'done'>('form')
  const [error, setError] = useState('')
  const [approvalToken, setApprovalToken] = useState('')

  async function handleSubmit() {
    const amountCents = Math.round(parseFloat(amount) * 100)
    if (!description.trim() || !amountCents) { setError('Enter a description and amount.'); return }
    setStep('sending')
    setError('')
    try {
      const taxCents = Math.round(amountCents * (parseFloat(taxPct || '0') / 100))
      const quote = await createQuote({
        repair_job_id: jobId,
        tax_cents: taxCents,
        line_items: [{ item_type: 'labor', description: description.trim(), quantity: 1, unit_price_cents: amountCents }],
      })
      const sent = await sendQuote(quote.data.id)
      setApprovalToken(sent.data.approval_token)
      setStep('done')
      onSent()
    } catch {
      setError('Failed to create or send the quote. Please try again.')
      setStep('form')
    }
  }

  if (step === 'done') {
    const approvalUrl = `${window.location.origin}/approve/${approvalToken}`
    return (
      <Modal title="Quote Sent" onClose={onClose}>
        <div className="space-y-4 text-sm">
          <p style={{ color: 'var(--ms-text)' }}>Quote created and sent to the customer for approval.</p>
          <div className="rounded-xl p-3 space-y-1" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}>
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Approval link</p>
            <p className="break-all text-xs font-mono" style={{ color: 'var(--ms-text-mid)' }}>{approvalUrl}</p>
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => void navigator.clipboard.writeText(approvalUrl)}
            >
              Copy link
            </Button>
            <Button className="flex-1" onClick={onClose}>Done</Button>
          </div>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="Create & Send Quote" onClose={onClose}>
      <div className="space-y-3">
        <Textarea
          label="What's being repaired / serviced *"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="Full service — movement clean, lubricate, and regulate…"
          autoFocus
        />
        <div className="flex gap-3">
          <div className="flex-1">
            <Input
              label="Amount ($) *"
              type="number"
              min="0"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="195.00"
            />
          </div>
          <div style={{ width: 90 }}>
            <Input
              label="Tax (%)"
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={taxPct}
              onChange={(e) => setTaxPct(e.target.value)}
              placeholder="10"
            />
          </div>
        </div>
        {amount && !isNaN(parseFloat(amount)) && (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            Total: ${(parseFloat(amount) * (1 + parseFloat(taxPct || '0') / 100)).toFixed(2)}
          </p>
        )}
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => void handleSubmit()} disabled={step === 'sending'}>
            {step === 'sending' ? 'Sending…' : 'Create & Send Quote'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Status update modal ───────────────────────────────────────────────────────
function StatusModal({ job, onClose }: { job: RepairJob; onClose: () => void }) {
  const qc = useQueryClient()
  const [status, setStatus] = useState<JobStatus>(job.status)
  const [note, setNote] = useState('')
  const mut = useMutation({
    mutationFn: () => updateJobStatus(job.id, status, note || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', job.id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['history', job.id] })
      onClose()
    },
  })
  const statuses: JobStatus[] = [...JOB_STATUS_ORDER]

  return (
    <Modal title="Update Status" onClose={onClose}>
      <div className="space-y-3">
        <Select label="New Status" value={status} onChange={e => setStatus(e.target.value as JobStatus)}>
          {statuses.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </Select>
        <Input label="Note (optional)" value={note} onChange={e => setNote(e.target.value)} placeholder="Parts arrived, awaiting…" />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>{mut.isPending ? 'Updating…' : 'Update'}</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Work log modal ────────────────────────────────────────────────────────────
// ── Tab types ─────────────────────────────────────────────────────────────────
type Tab = 'details' | 'worklogs' | 'attachments' | 'history' | 'messages'

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('details')
  const [showStatus, setShowStatus] = useState(false)
  const [showLogWork, setShowLogWork] = useState(false)
  const [showCreateQuote, setShowCreateQuote] = useState(false)
  const [pendingStepStatus, setPendingStepStatus] = useState<JobStatus | null>(null)
  const [editingQuote, setEditingQuote] = useState(false)
  const [quoteInput, setQuoteInput] = useState('')
  const [movementApplying, setMovementApplying] = useState(false)
  const updateJobMutation = useMutation({
      mutationFn: (cost_cents: number) => updateJob(id!, { cost_cents }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['job', id] })
        qc.invalidateQueries({ queryKey: ['jobs'] })
        setEditingQuote(false)
      },
    })
  const quickStatusMutation = useMutation({
    mutationFn: ({ status, note }: { status: JobStatus; note?: string }) => quickStatusAction(id!, status, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['history', id] })
    },
  })
  const fileRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [attachmentSortBy, setAttachmentSortBy] = useState<'created_at' | 'file_name' | 'file_size_bytes'>('created_at')
  const [attachmentSortDir, setAttachmentSortDir] = useState<'asc' | 'desc'>('desc')
  const parseDollarsToCents = (value: string) => {
    const parsed = Number.parseFloat(value)
    return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0
  }

  const { data: job, isLoading } = useQuery({ queryKey: ['job', id], queryFn: () => getJob(id!).then(r => r.data) })
  const { data: watch } = useQuery({
    queryKey: ['watch', job?.watch_id],
    queryFn: () => getWatch(job!.watch_id).then(r => r.data),
    enabled: !!job?.watch_id,
  })
  const { data: customer } = useQuery({
    queryKey: ['customer', watch?.customer_id],
    queryFn: () => getCustomer(watch!.customer_id).then(r => r.data),
    enabled: !!watch?.customer_id,
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const matchingAccounts = watch?.customer_id
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(watch.customer_id))
    : customerAccounts

  async function applyMovementQuote(movementKey: string) {
    if (!id || !movementKey) return
    setMovementApplying(true)
    try {
      const { data } = await getWatchMovementQuote(movementKey)
      await updateJob(id, { cost_cents: data.quote_cents, pre_quote_cents: data.quote_cents })
      qc.invalidateQueries({ queryKey: ['job', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      setQuoteInput((data.quote_cents / 100).toFixed(2))
      setEditingQuote(false)
    } finally {
      setMovementApplying(false)
    }
  }
  const updateAccountMutation = useMutation({
    mutationFn: (customer_account_id: string | null) => updateJob(id!, { customer_account_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => listUsers().then(r => r.data) })

  const assignMutation = useMutation({
    mutationFn: (userId: string | null) =>
      userId
        ? updateJob(id!, { assigned_user_id: userId })
        : updateJob(id!, { clear_assigned_user: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })

  const resendMut = useMutation({
    mutationFn: (eventType: 'job_live' | 'job_ready' | 'quote_sent') =>
      resendJobNotification(id!, eventType).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sms-log', id] }),
  })

  const quotesQuery = useOffsetPaginatedQuery({
    queryKey: ['quotes', id, 'paged', 'created_at', 'desc'],
    queryFn: (offset) =>
      listQuotes(id!, {
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: 'created_at',
        sort_dir: 'desc',
      }).then((r) => r.data),
    enabled: !!id,
  })
  const quotes = useMemo(() => flattenInfinitePages(quotesQuery.data), [quotesQuery.data])

  const { data: workLogs } = useQuery({ queryKey: ['worklogs', id], queryFn: () => listWorkLogs(id!).then(r => r.data), enabled: !!id })

  const attachmentsQuery = useOffsetPaginatedQuery({
    queryKey: ['attachments', id, 'paged', attachmentSortBy, attachmentSortDir],
    queryFn: (offset) =>
      listAttachments(id!, {
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: attachmentSortBy,
        sort_dir: attachmentSortDir,
      }).then((r) => r.data),
    enabled: !!id,
  })
  const attachments = useMemo(() => flattenInfinitePages(attachmentsQuery.data), [attachmentsQuery.data])
  const { data: history } = useQuery({ queryKey: ['history', id], queryFn: () => getStatusHistory(id!).then(r => r.data), enabled: tab === 'history' })
  const { data: smsLog } = useQuery({ queryKey: ['sms-log', id], queryFn: () => getSmsLog(id!).then(r => r.data), enabled: tab === 'messages' })

  const nextStatus = job ? STATUS_FLOW[job.status] : null

  async function uploadFile(file: File, label?: string) {
    if (!file || !id) return
    setUploading(true)
    setUploadError('')
    try {
      const toUpload = file.type.startsWith('image/') ? await compressImage(file) : file
      await uploadAttachment(toUpload, id, label)
      qc.invalidateQueries({ queryKey: ['attachments', id] })
    } catch (err: unknown) {
      setUploadError(getUploadErrorMessage(err, 'Upload failed.'))
    } finally {
      setUploading(false)
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadFile(file)
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleCameraCapture(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadFile(file, 'extra_photo')
    } finally {
      if (cameraRef.current) cameraRef.current.value = ''
    }
  }

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'details', label: 'Details', icon: <FileText size={14} /> },
    { key: 'worklogs', label: 'Work Logs', icon: <Clock size={14} /> },
    { key: 'attachments', label: 'Attachments', icon: <Paperclip size={14} /> },
    { key: 'history', label: 'History', icon: <History size={14} /> },
    { key: 'messages', label: 'Messages', icon: <MessageSquare size={14} /> },
  ]

  if (isLoading) return <Spinner />
  if (!job) return <p style={{ color: 'var(--ms-text-muted)' }}>Job not found.</p>

  return (
    <div>
      <div className="mb-5">
        <Link
          to="/jobs"
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--ms-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-text-muted)')}
        >
          <ChevronLeft size={14} /> Back to Jobs
        </Link>
      </div>
      <PageHeader
        title={`#${job.job_number} · ${job.title}`}
        action={
          <div className="flex gap-2">
            {/* Desktop: all buttons */}
            <Button
              variant="ghost"
              className="hidden sm:inline-flex text-sm"
              onClick={() => {
                const url = `${window.location.origin}/status/${job.status_token}`
                void navigator.clipboard.writeText(url).then(() => { /* optional toast */ })
              }}
            >
              Copy status link
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/jobs/${job.id}/intake-print?autoprint=1`)}>
              <Printer size={15} /><span className="hidden sm:inline">Print Intake Tickets</span>
            </Button>
            {nextStatus && (
              <Button variant="secondary" onClick={() => setShowStatus(true)}>
                <ArrowRight size={15} /><span className="hidden sm:inline">Move to {STATUS_LABELS[nextStatus]}</span><span className="sm:hidden">{STATUS_LABELS[nextStatus]}</span>
              </Button>
            )}
            <Button variant="ghost" onClick={() => setShowStatus(true)}>Status</Button>
          </div>
        }
      />
      {showStatus && <StatusModal job={job} onClose={() => setShowStatus(false)} />}
      {showLogWork && <LogWorkModal jobId={id!} onClose={() => setShowLogWork(false)} />}
      {showCreateQuote && (
        <CreateSendQuoteModal
          jobId={id!}
          onClose={() => setShowCreateQuote(false)}
          onSent={() => {
            qc.invalidateQueries({ queryKey: ['job', id] })
            qc.invalidateQueries({ queryKey: ['jobs'] })
            qc.invalidateQueries({ queryKey: ['quotes', id] })
            qc.invalidateQueries({ queryKey: ['history', id] })
          }}
        />
      )}
      {pendingStepStatus && (
        <StepNoteModal
          targetStatus={pendingStepStatus}
          isPending={quickStatusMutation.isPending}
          onClose={() => setPendingStepStatus(null)}
          onConfirm={(note) => {
            quickStatusMutation.mutate(
              { status: pendingStepStatus, note: note || undefined },
              { onSuccess: () => setPendingStepStatus(null) },
            )
          }}
        />
      )}

      {/* Summary strip */}
      <div className="flex flex-wrap gap-4 mb-6 text-sm">
        <span style={{ color: 'var(--ms-text-muted)' }}>Status: <Badge status={job.status} /></span>
        <span style={{ color: 'var(--ms-text-muted)' }}>Priority: <span className="font-medium capitalize" style={{ color: job.priority === 'urgent' ? '#8B3A3A' : job.priority === 'high' ? '#9B4E0F' : 'var(--ms-text)' }}>{job.priority}</span></span>
        <span style={{ color: 'var(--ms-text-muted)' }}>Quote: <span className="font-medium" style={{ color: 'var(--ms-text)' }}>${((job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents) / 100).toFixed(2)}</span></span>
        <span style={{ color: 'var(--ms-text-muted)' }}>Created: <span style={{ color: 'var(--ms-text)' }}>{formatDate(job.created_at)}</span></span>
        {(() => {
          const days = Math.floor((Date.now() - new Date(job.created_at).getTime()) / 86_400_000)
          const color = days >= 14 ? '#8B3A3A' : days >= 7 ? '#9B4E0F' : 'var(--ms-text-muted)'
          return <span style={{ color: 'var(--ms-text-muted)' }}>In shop: <span className="font-medium" style={{ color }}>{days} day{days !== 1 ? 's' : ''}</span></span>
        })()}
      </div>

      <Card className="mb-5" style={{ padding: 0, overflow: 'hidden' }}>
        <WorkflowRail
          steps={WATCH_WORKFLOW_STEPS}
          currentStatus={job.status}
          disabled={quickStatusMutation.isPending}
          onStepClick={(status) => setPendingStepStatus(status as JobStatus)}
        />
        {job.status === 'awaiting_quote' && (
          <div
            className="flex flex-col sm:flex-row sm:items-center gap-4"
            style={{ padding: '14px 24px', backgroundColor: 'var(--ms-accent-light)' }}
          >
            <div className="flex-1">
              <p className="font-semibold" style={{ color: 'var(--ms-text)' }}>Ready to quote this job?</p>
              <p className="text-sm mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                Enter the repair description and price — the quote will be created and sent to the customer in one step.
              </p>
            </div>
            <Button onClick={() => setShowCreateQuote(true)} className="flex-shrink-0">
              Create &amp; Send Quote
            </Button>
          </div>
        )}
      </Card>

      {/* Tabs */}
      <div className="-mx-4 px-4 sm:mx-0 sm:px-0 overflow-x-auto mb-6" style={{ borderBottom: '1px solid var(--ms-border)' }}>
        <div className="flex gap-0.5 min-w-max">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all duration-150"
              style={{
                borderBottom: tab === t.key ? '2px solid var(--ms-accent)' : '2px solid transparent',
                color: tab === t.key ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
                fontWeight: tab === t.key ? 700 : 500,
              }}
              onMouseEnter={e => { if (tab !== t.key) e.currentTarget.style.color = 'var(--ms-text-mid)' }}
              onMouseLeave={e => { if (tab !== t.key) e.currentTarget.style.color = 'var(--ms-text-muted)' }}
            >
              {t.icon}{t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab: Details ─────────────────────────────────────────── */}
      {tab === 'details' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Card style={{ padding: 0, overflow: 'hidden' }}>
            <div
              style={{
                background: 'var(--ms-sidebar)',
                color: '#fff',
                padding: '18px 20px 16px',
                position: 'relative',
              }}
            >
              <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ms-sidebar-text)' }}>
                Job Ticket
              </p>
              <p style={{ fontSize: 32, fontWeight: 800, color: '#fff', lineHeight: 1.05, marginTop: 4, letterSpacing: '-0.02em' }}>
                #{job.job_number}
              </p>
              <p style={{ fontSize: 12, marginTop: 4, color: 'var(--ms-sidebar-text)' }}>{formatDate(job.created_at)}</p>
              {(customer?.full_name || customer?.phone) && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.15)' }}>
                  {customer.full_name && (
                    <p style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{customer.full_name}</p>
                  )}
                  {customer.phone && (
                    <a
                      href={`tel:${customer.phone}`}
                      style={{ fontSize: 12, color: 'var(--ms-sidebar-text)', textDecoration: 'none' }}
                    >
                      {customer.phone}
                    </a>
                  )}
                </div>
              )}
            </div>
            <div style={{ borderTop: '1px dashed var(--ms-border-strong)', margin: '0 12px' }} />
            <div className="space-y-2.5 text-sm" style={{ padding: '16px 20px' }}>
              <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Job #</span><span className="font-mono" style={{ color: 'var(--ms-text)' }}>#{job.job_number}</span></div>
              <div className="flex justify-between items-center"><span style={{ color: 'var(--ms-text-muted)' }}>Status</span><Badge status={job.status} /></div>
              <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Priority</span><span className="capitalize font-medium" style={{ color: 'var(--ms-text)' }}>{job.priority}</span></div>
              <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Date In</span><span style={{ color: 'var(--ms-text)' }}>{formatDate(job.created_at)}</span></div>
              {job.collection_date && <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Collection</span><span style={{ color: 'var(--ms-text)' }}>{job.collection_date}</span></div>}
              {job.salesperson && <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Salesperson</span><span style={{ color: 'var(--ms-text)' }}>{job.salesperson}</span></div>}
              {job.customer_name && <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Customer</span><span className="font-medium" style={{ color: 'var(--ms-text)' }}>{job.customer_name}</span></div>}
              {job.customer_phone && <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Phone</span><a href={`tel:${job.customer_phone}`} className="font-medium" style={{ color: 'var(--ms-primary)' }}>{job.customer_phone}</a></div>}
              {job.customer_email && <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Email</span><a href={`mailto:${job.customer_email}`} className="font-medium" style={{ color: 'var(--ms-primary)', wordBreak: 'break-all' }}>{job.customer_email}</a></div>}
              {job.deposit_cents > 0 && <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Deposit</span><span className="font-medium" style={{ color: '#3B6B42' }}>${(job.deposit_cents / 100).toFixed(2)}</span></div>}
              <div className="space-y-1">
                <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Assigned Technician</span>
                <Select
                  value={job.assigned_user_id ?? ''}
                  onChange={e => {
                    const val = e.target.value
                    assignMutation.mutate(val || null)
                  }}
                  disabled={assignMutation.isPending}
                >
                  <option value="">Unassigned</option>
                  {(users ?? []).map((u: TenantUser) => (
                    <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Customer Account</span>
                <Select
                  value={job.customer_account_id ?? ''}
                  onChange={e => updateAccountMutation.mutate(e.target.value || null)}
                  disabled={updateAccountMutation.isPending}
                >
                  <option value="">No B2B account</option>
                  {matchingAccounts.map((account: CustomerAccount) => (
                    <option key={account.id} value={account.id}>
                      {account.name}{account.account_code ? ` (${account.account_code})` : ''}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1 mb-2">
                <MovementAutocomplete
                  label="Set quote from movement"
                  placeholder="Search ETA, Miyota, Ronda…"
                  onSelect={key => applyMovementQuote(key)}
                  disabled={movementApplying}
                />
              </div>
              <div className="flex justify-between items-center">
                <span style={{ color: 'var(--ms-text-muted)' }}>Quote{job.cost_cents === 0 && job.pre_quote_cents > 0 ? ' (est.)' : ''}</span>
                {editingQuote ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>$</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={quoteInput}
                      onChange={e => setQuoteInput(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') updateJobMutation.mutate(parseDollarsToCents(quoteInput))
                        if (e.key === 'Escape') setEditingQuote(false)
                      }}
                      autoFocus
                      className="w-24 text-right text-sm rounded px-1.5 py-0.5"
                      style={{ border: '1px solid var(--ms-border)', background: 'var(--ms-bg)', color: 'var(--ms-text)' }}
                    />
                    <button
                      onClick={() => updateJobMutation.mutate(parseDollarsToCents(quoteInput))}
                      disabled={updateJobMutation.isPending}
                      className="text-xs px-2 py-0.5 rounded font-medium"
                      style={{ backgroundColor: '#EEE6DA', color: 'var(--ms-text)' }}
                    >
                      Save
                    </button>
                    <button onClick={() => setEditingQuote(false)} className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>✕</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="font-medium" style={{ color: 'var(--ms-text-mid)' }}>
                      ${((job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents) / 100).toFixed(2)}
                    </span>
                    <button
                      onClick={() => {
                        setQuoteInput(((job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents) / 100).toFixed(2))
                        setEditingQuote(true)
                      }}
                      className="opacity-50 hover:opacity-100 transition-opacity"
                      title="Edit quote"
                    >
                      <Pencil size={12} style={{ color: 'var(--ms-text-muted)' }} />
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Intake Photos */}
            {(() => {
              const frontPhoto = attachments.find(a => a.label === 'watch_front')
              const backPhoto = attachments.find(a => a.label === 'watch_back')
              if (!frontPhoto && !backPhoto) return null
              return (
                <div style={{ borderTop: '1px solid var(--ms-border)', padding: '14px 20px 18px' }}>
                  <h2 className="font-semibold text-xs uppercase tracking-widest mb-2 flex items-center gap-1.5" style={{ color: 'var(--ms-text-muted)' }}><Camera size={13} />Intake Photos</h2>
                  <div className="grid grid-cols-2 gap-2">
                    {frontPhoto && (
                      <SecureAttachmentLink storageKey={frontPhoto.storage_key} target="_blank" rel="noopener noreferrer" className="group">
                        <SecureAttachmentImage storageKey={frontPhoto.storage_key} alt="Watch front" className="w-full aspect-square object-cover rounded-lg transition-shadow" style={{ border: '1px solid var(--ms-border)' }} />
                        <p className="text-[10px] text-center mt-1" style={{ color: 'var(--ms-text-muted)' }}>Front</p>
                      </SecureAttachmentLink>
                    )}
                    {backPhoto && (
                      <SecureAttachmentLink storageKey={backPhoto.storage_key} target="_blank" rel="noopener noreferrer" className="group">
                        <SecureAttachmentImage storageKey={backPhoto.storage_key} alt="Watch back" className="w-full aspect-square object-cover rounded-lg transition-shadow" style={{ border: '1px solid var(--ms-border)' }} />
                        <p className="text-[10px] text-center mt-1" style={{ color: 'var(--ms-text-muted)' }}>Back</p>
                      </SecureAttachmentLink>
                    )}
                  </div>
                </div>
              )
            })()}
          </Card>

          <div className="lg:col-span-2 flex flex-col gap-5">
            {job.description && (
              <Card className="p-5">
                <h2 className="font-semibold text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--ms-text-muted)' }}>Description / Fault Report</h2>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--ms-text-mid)' }}>{job.description}</p>
              </Card>
            )}

            <Card>
              <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>Quotes</h2>
                <Link to="/quotes" className="text-xs font-medium tracking-wide uppercase transition-colors" style={{ color: 'var(--ms-accent)' }}>Manage quotes →</Link>
              </div>
              <div>
                {quotesQuery.error && (
                  <p className="px-5 py-2 text-sm" style={{ color: '#C96A5A' }}>{getApiErrorMessage(quotesQuery.error, 'Could not load quotes.')}</p>
                )}
                {quotesQuery.isLoading && quotes.length === 0 ? (
                  <div className="px-5 py-5"><Spinner /></div>
                ) : (
                  <>
                    {quotes.map((q, i) => (
                      <div key={q.id} className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: i < quotes.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>Quote</p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(q.created_at)}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>${((q.total_cents ?? 0) / 100).toFixed(2)}</span>
                          <Badge status={q.status} />
                        </div>
                      </div>
                    ))}
                    {quotes.length === 0 && !quotesQuery.isLoading && (
                      <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No quotes yet.</p>
                    )}
                    {quotesQuery.hasNextPage && (
                      <div className="px-5 py-3 flex justify-center" style={{ borderTop: '1px solid var(--ms-border)' }}>
                        <Button
                          variant="secondary"
                          className="text-xs"
                          onClick={() => void quotesQuery.fetchNextPage()}
                          disabled={quotesQuery.isFetchingNextPage}
                        >
                          {quotesQuery.isFetchingNextPage ? 'Loading…' : 'Load more quotes'}
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </Card>

            {/* Work Logs inline on Details tab */}
            <Card>
              <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                <h2 className="font-semibold flex items-center gap-1.5" style={{ color: 'var(--ms-text)' }}><Clock size={14} />Work Logs</h2>
                <Button onClick={() => setShowLogWork(true)}><Plus size={14} />Log Work</Button>
              </div>
              {!workLogs ? (
                <div className="px-5 py-5"><Spinner /></div>
              ) : workLogs.length === 0 ? (
                <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No work logged yet.</p>
              ) : (
                <div className="divide-y" style={{ borderColor: 'var(--ms-border)' }}>
                  {workLogs.map(log => (
                    <div key={log.id} className="flex items-start justify-between gap-4 px-5 py-3.5">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap flex-1" style={{ color: 'var(--ms-text-mid)' }}>{log.note}</p>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {log.minutes_spent && (
                          <span className="text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap" style={{ backgroundColor: '#EEE6DA', color: 'var(--ms-text-mid)' }}>
                            <Clock size={11} className="inline mr-0.5" />{log.minutes_spent} min
                          </span>
                        )}
                        <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(log.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* ── Tab: Work Logs ──────────────────────────────────────── */}
      {tab === 'worklogs' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>{(workLogs ?? []).length} log{(workLogs ?? []).length !== 1 ? 's' : ''}</p>
            <Button onClick={() => setShowLogWork(true)}><Plus size={15} />Log Work</Button>
          </div>
          <div className="space-y-3">
            {job.description && (
              <Card className="p-4" style={{ borderLeft: '3px solid var(--ms-border)' }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Initial Notes</span>
                </div>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--ms-text-mid)' }}>{job.description}</p>
                <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(job.created_at)}</p>
              </Card>
            )}
            {!workLogs ? <Spinner /> : workLogs.length === 0 && !job.description ? (
              <EmptyState message="No work logged yet. Tap 'Log Work' to record what was done." />
            ) : (
              workLogs.map(log => (
                <Card key={log.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap flex-1" style={{ color: 'var(--ms-text-mid)' }}>{log.note}</p>
                    {log.minutes_spent && (
                      <span className="text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap" style={{ backgroundColor: '#EEE6DA', color: 'var(--ms-text-mid)' }}>
                        <Clock size={11} className="inline mr-0.5" />{log.minutes_spent} min
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(log.created_at)}</p>
                </Card>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Attachments ──────────────────────────────────── */}
      {tab === 'attachments' && (
        <div>
          <div className="flex flex-wrap justify-between items-center gap-3 mb-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              {attachments.length} file{attachments.length !== 1 ? 's' : ''} loaded
              {attachmentsQuery.hasNextPage ? ' — more available' : ''}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded-lg px-2 py-1.5 text-xs outline-none"
                style={{ border: '1px solid var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
                value={attachmentSortBy}
                onChange={(e) => setAttachmentSortBy(e.target.value as typeof attachmentSortBy)}
                aria-label="Sort attachments by"
              >
                <option value="created_at">Sort: Date</option>
                <option value="file_name">Sort: Name</option>
                <option value="file_size_bytes">Sort: Size</option>
              </select>
              <select
                className="rounded-lg px-2 py-1.5 text-xs outline-none"
                style={{ border: '1px solid var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
                value={attachmentSortDir}
                onChange={(e) => setAttachmentSortDir(e.target.value as 'asc' | 'desc')}
                aria-label="Attachment sort direction"
              >
                <option value="desc">Newest / Z–A</option>
                <option value="asc">Oldest / A–Z</option>
              </select>
              <input ref={fileRef} type="file" className="hidden" onChange={handleFileUpload} />
              <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleCameraCapture} />
              <Button variant="secondary" onClick={() => cameraRef.current?.click()} disabled={uploading}>
                <Camera size={15} />{uploading ? 'Uploading…' : 'Take Extra Photo'}
              </Button>
              <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
                <Upload size={15} />{uploading ? 'Uploading…' : 'Upload File'}
              </Button>
            </div>
          </div>
          {uploadError && (
            <p className="text-sm mb-3" style={{ color: '#C96A5A' }}>{uploadError}</p>
          )}
          {attachmentsQuery.error && (
            <p className="text-sm mb-3" style={{ color: '#C96A5A' }}>{getApiErrorMessage(attachmentsQuery.error, 'Could not load attachments.')}</p>
          )}
          {attachmentsQuery.isLoading && attachments.length === 0 ? (
            <Spinner />
          ) : attachments.length === 0 ? (
            <EmptyState message="No attachments yet. Upload photos or documents." />
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {attachments.map(att => (
                  <Card key={att.id} className="p-4 flex items-start gap-3">
                    <Paperclip size={17} className="mt-0.5 shrink-0" style={{ color: 'var(--ms-text-muted)' }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: 'var(--ms-text)' }}>{att.file_name}</p>
                      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{att.content_type} · {att.file_size_bytes ? `${(att.file_size_bytes / 1024).toFixed(1)} KB` : ''}</p>
                    </div>
                    <SecureAttachmentLink
                      storageKey={att.storage_key}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 transition-colors"
                      style={{ color: 'var(--ms-accent)' }}
                      title="Download"
                    >
                      <Download size={15} />
                    </SecureAttachmentLink>
                  </Card>
                ))}
              </div>
              {attachmentsQuery.hasNextPage && (
                <div className="mt-6 flex justify-center">
                  <Button
                    variant="secondary"
                    onClick={() => void attachmentsQuery.fetchNextPage()}
                    disabled={attachmentsQuery.isFetchingNextPage}
                  >
                    {attachmentsQuery.isFetchingNextPage ? 'Loading…' : 'Load more attachments'}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Tab: Messages (SMS log) ───────────────────────────────────────────── */}
      {tab === 'messages' && (
        <div>
          <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>Texts sent to the customer for this job.</p>
          <div className="mb-4 flex flex-wrap gap-2">
            {(['job_live', 'job_ready', 'quote_sent'] as const).map(evt => (
              <Button
                key={evt}
                variant="secondary"
                onClick={() => resendMut.mutate(evt)}
                disabled={resendMut.isPending}
              >
                {evt === 'job_live' ? 'Resend: Job live SMS' : evt === 'job_ready' ? 'Resend: Job ready' : 'Resend: Quote'}
              </Button>
            ))}
            {resendMut.isSuccess && resendMut.data && (
              <p className="text-xs self-center" style={{ color: '#1F6D4C' }}>
                Sent — SMS: {resendMut.data.sent.sms ? '✓' : '—'} · Email: {resendMut.data.sent.email ? '✓' : '—'}
              </p>
            )}
            {resendMut.isError && (
              <p className="text-xs self-center" style={{ color: '#C96A5A' }}>Failed to send</p>
            )}
          </div>
          {!smsLog ? <Spinner /> : smsLog.length === 0 ? <EmptyState message="No messages sent yet. The customer will receive a text when the job goes live and when a quote is sent." /> : (
            <div className="space-y-3">
              {smsLog.map(log => (
                <Card key={log.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--ms-text-mid)' }}>{log.body}</p>
                      <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>
                        To: {log.to_phone} · {log.event.replace(/_/g, ' ')}
                        {log.status === 'dry_run' && ' (dry run)'}
                      </p>
                    </div>
                    <span className="text-xs whitespace-nowrap" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(log.created_at)}</span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: History ───────────────────────────────────────── */}
      {tab === 'history' && (
        <div>
          {!history ? <Spinner /> : history.length === 0 ? <EmptyState message="No status history yet." /> : (
            <div className="relative pl-6 space-y-4">
              <div className="absolute left-2 top-0 bottom-0 w-0.5" style={{ backgroundColor: 'var(--ms-border-strong)' }} />
              {history.map((h, i) => (
                <div key={h.id} className="relative">
                  <div
                    className="absolute -left-4 top-1 w-3 h-3 rounded-full border-2"
                    style={{
                      borderColor: 'var(--ms-surface)',
                      backgroundColor: i === 0 ? 'var(--ms-accent)' : 'var(--ms-border-strong)',
                    }}
                  />
                  <Card className="p-4">
                    <div className="flex items-center justify-between">
                      <Badge status={h.new_status} />
                      <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(h.created_at)}</span>
                    </div>
                    {h.old_status && <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>from: {h.old_status.replace(/_/g, ' ')}</p>}
                    {h.change_note && <p className="text-sm mt-1.5" style={{ color: 'var(--ms-text-mid)' }}>{h.change_note}</p>}
                  </Card>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
