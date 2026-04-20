import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { Camera, CheckCircle, ChevronLeft, MapPin, MessageSquare, Phone, Mail, Plus, Send } from 'lucide-react'
import {
  getAutoKeyJob,
  getApiErrorMessage,
  getUploadErrorMessage,
  getCustomer,
  getVehicleJobContext,
  listAutoKeyAttachments,
  listAutoKeyInvoices,
  listAutoKeyQuotes,
  listCustomerAccounts,
  listUsers,
  createAutoKeyQuote,
  sendAutoKeyQuote,
  createAutoKeyInvoiceFromQuote,
  sendAutoKeyInvoice,
  searchVehicleKeySpecs,
  sendAutoKeyArrivalSms,
  updateAutoKeyInvoice,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  uploadAutoKeyAttachment,
  MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS,
  type AutoKeyJobUpdatePayload,
  type CuttingProfile,
  type CustomerAccount,
  type JobStatus,
  type KnownIssue,
  type ToolRecommendation,
  type VehicleKeySpecMatch,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { AUTO_KEY_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'
import { AklComplexityPill } from '@/components/auto-key/AklComplexityPill'
import { SecureAttachmentImage, SecureAttachmentLink } from '@/components/SecureAttachment'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'
import { formatDate, STATUS_LABELS } from '@/lib/utils'

function CreateQuoteInlineForm({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [err, setErr] = useState('')
  const [description, setDescription] = useState('Mobile service')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('120.00')
  const [tax, setTax] = useState('0.00')

  const mut = useMutation({
    mutationFn: () =>
      createAutoKeyQuote(jobId, {
        line_items: [{ description: description.trim() || 'Mobile service', quantity: Math.max(1, Number(quantity || '1')), unit_price_cents: Math.max(0, Math.round(parseFloat(unitPrice || '0') * 100)) }],
        tax_cents: Math.max(0, Math.round(parseFloat(tax || '0') * 100)),
      }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['auto-key-quotes', jobId] }); onClose() },
    onError: (e) => setErr(getApiErrorMessage(e, 'Failed to create quote.')),
  })

  const total = (parseFloat(unitPrice || '0') * parseFloat(quantity || '1') + parseFloat(tax || '0')).toFixed(2)

  return (
    <div className="space-y-3">
      <Input label="Description" value={description} onChange={e => setDescription(e.target.value)} />
      <div className="grid grid-cols-3 gap-3">
        <Input label="Qty" type="number" min="1" value={quantity} onChange={e => setQuantity(e.target.value)} />
        <Input label="Unit price ($)" type="number" step="0.01" min="0" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} />
        <Input label="GST ($)" type="number" step="0.01" min="0" value={tax} onChange={e => setTax(e.target.value)} />
      </div>
      <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>Total: ${total}</p>
      {err && <p className="text-sm" style={{ color: '#C96A5A' }}>{err}</p>}
      <div className="flex gap-2 pt-1">
        <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
        <Button className="flex-1 flex items-center justify-center gap-1" onClick={() => mut.mutate()} disabled={mut.isPending}>
          {mut.isPending ? 'Creating…' : 'Save Quote'}
        </Button>
      </div>
    </div>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const s = severity.toLowerCase()
  let bg = 'rgba(201,162,72,0.12)', color = '#9A7220'
  if (s.includes('very high') || s.includes('critical')) { bg = 'rgba(201,106,90,0.15)'; color = '#C96A5A' }
  else if (s.includes('high'))  { bg = 'rgba(201,106,90,0.10)'; color = '#B85A4A' }
  else if (s.includes('low'))   { bg = 'rgba(120,180,120,0.15)'; color = '#4A8A4A' }
  return (
    <span className='inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap shrink-0'
      style={{ backgroundColor: bg, color }}>
      {severity}
    </span>
  )
}

const STATUSES: JobStatus[] = [
  'awaiting_quote',
  'quote_sent',
  'awaiting_booking_confirmation',
  'booking_confirmed',
  'job_delayed',
  'en_route',
  'on_site',
  'work_completed',
  'invoice_paid',
  'failed_job',
]

function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

export default function AutoKeyJobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const { hasFeature } = useAuth()
  const [error, setError] = useState('')
  const [vLookupMake, setVLookupMake] = useState('')
  const [vLookupModel, setVLookupModel] = useState('')
  const [vLookupYear, setVLookupYear] = useState('')
  const [addressEdit, setAddressEdit] = useState<string | null>(null)
  const [keyTypeEdit, setKeyTypeEdit] = useState<string | null>(null)
  const [bladeCodeEdit, setBladeCodeEdit] = useState<string | null>(null)
  const [chipTypeEdit, setChipTypeEdit] = useState<string | null>(null)
  const [techNotesEdit, setTechNotesEdit] = useState<string | null>(null)
  const [showArrivalSms, setShowArrivalSms] = useState(false)
  const [arrivalWindow, setArrivalWindow] = useState('9–11am')
  const [invoiceToPay, setInvoiceToPay] = useState<{ id: string; invoice_number: string; total_cents: number } | null>(null)
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'eftpos' | 'bank'>('eftpos')
  const [statusFeedback, setStatusFeedback] = useState('')
  const [detailTab, setDetailTab] = useState<'info' | 'vehicle' | 'financial' | 'photos'>('info')
  const [showQuoteModal, setShowQuoteModal] = useState(false)
  const [sendInvoiceFeedback, setSendInvoiceFeedback] = useState('')

  const { data: job, isLoading } = useQuery({
    queryKey: ['auto-key-job', id],
    queryFn: () => getAutoKeyJob(id!).then(r => r.data),
    enabled: !!id,
  })

  useEffect(() => {
    if (!job) return
    setVLookupMake(job.vehicle_make ?? '')
    setVLookupModel(job.vehicle_model ?? '')
    setVLookupYear(job.vehicle_year != null ? String(job.vehicle_year) : '')
  }, [job?.id, job?.vehicle_make, job?.vehicle_model, job?.vehicle_year])

  const parsedLookupYear = vLookupYear.trim() ? Number.parseInt(vLookupYear, 10) : NaN
  const lookupYearParam = Number.isFinite(parsedLookupYear) ? parsedLookupYear : undefined
  const { data: vehicleSpecSearch } = useQuery({
    queryKey: ['vehicle-key-specs', 'job-detail', job?.id, vLookupMake, vLookupModel, vLookupYear],
    queryFn: () =>
      searchVehicleKeySpecs({
        make: vLookupMake,
        model: vLookupModel,
        year: lookupYearParam,
      }).then(r => r.data),
    enabled:
      !!job &&
      hasFeature('auto_key') &&
      (vLookupMake.trim().length >= 2 || vLookupModel.trim().length >= 2),
    staleTime: 60_000,
  })

  // ── Job context: complexity, known issues, tool recs, cutting profiles ─────
  const { data: jobContext } = useQuery({
    queryKey: ['vehicle-job-context', job?.vehicle_make, job?.vehicle_model, job?.vehicle_year, job?.job_type, job?.blade_code],
    queryFn: () =>
      getVehicleJobContext({
        make: job!.vehicle_make ?? '',
        model: job!.vehicle_model ?? '',
        year: job!.vehicle_year ?? undefined,
        job_type: job!.job_type ?? undefined,
        blade_code: job!.blade_code ?? undefined,
      }).then(r => r.data),
    enabled: !!job && !!(job.vehicle_make || job.vehicle_model),
    staleTime: 120_000,
  })

  const applyVehicleDbMut = useMutation({
    mutationFn: (m: VehicleKeySpecMatch) => {
      const yParsed = vLookupYear.trim() ? Number.parseInt(vLookupYear, 10) : NaN
      const yearToSet = Number.isFinite(yParsed) ? yParsed : (m.year_from ?? undefined)
      const patch: AutoKeyJobUpdatePayload = {
        vehicle_make: m.vehicle_make,
        vehicle_model: m.vehicle_model,
      }
      if (yearToSet !== undefined) patch.vehicle_year = yearToSet
      if (m.key_type) patch.key_type = m.key_type
      if (m.chip_type) patch.chip_type = m.chip_type
      if (m.tech_notes) patch.tech_notes = m.tech_notes
      if (m.suggested_blade_code) patch.blade_code = m.suggested_blade_code
      return updateAutoKeyJob(id!, patch)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setKeyTypeEdit(null)
      setBladeCodeEdit(null)
      setChipTypeEdit(null)
      setTechNotesEdit(null)
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not apply vehicle database row.')),
  })

  const { data: customer } = useQuery({
    queryKey: ['customer', job?.customer_id],
    queryFn: () => getCustomer(job!.customer_id).then(r => r.data),
    enabled: !!job?.customer_id,
  })

  const { data: attachments = [], refetch: refetchAttachments } = useQuery({
    queryKey: ['auto-key-attachments', id],
    queryFn: () => listAutoKeyAttachments(id!).then(r => r.data),
    enabled: !!id,
  })
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })
  const isSolo = users.length <= 1

  const { data: quotes = [] } = useQuery({
    queryKey: ['auto-key-quotes', id],
    queryFn: () => listAutoKeyQuotes(id!).then(r => r.data),
    enabled: !!id,
  })

  const { data: invoices = [] } = useQuery({
    queryKey: ['auto-key-invoices', id],
    queryFn: () => listAutoKeyInvoices(id!).then(r => r.data),
    enabled: !!id,
  })

  const statusMut = useMutation({
    mutationFn: (status: JobStatus) => updateAutoKeyJobStatus(id!, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update status.')),
  })

  const handleStatusChange = async (status: JobStatus) => {
    setStatusFeedback('')
    const invoicesBefore = invoices.length
    await statusMut.mutateAsync(status)
    if (status !== 'work_completed') return

    const [{ data: latestQuotes }, { data: latestInvoices }] = await Promise.all([
      listAutoKeyQuotes(id!),
      listAutoKeyInvoices(id!),
    ])
    const newestQuote = latestQuotes[0]
    if (latestInvoices.length > invoicesBefore) {
      setStatusFeedback('Work completed — invoice created and payment link sent to customer.')
      return
    }
    if (!newestQuote) {
      setStatusFeedback('Work completed. No invoice auto-created because no quote exists yet.')
      return
    }
    if (newestQuote.status === 'declined') {
      setStatusFeedback('Work completed. No invoice auto-created because the latest quote is declined.')
      return
    }
    setStatusFeedback('Work completed. No new invoice was created (an invoice may already exist).')
  }

  const sendQuoteMut = useMutation({
    mutationFn: (quoteId: string) => sendAutoKeyQuote(quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-quotes', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to send quote.')),
  })

  const createInvoiceMut = useMutation({
    mutationFn: (quoteId: string) => createAutoKeyInvoiceFromQuote(id!, quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-invoices', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to create invoice.')),
  })

  const sendInvoiceMut = useMutation({
    mutationFn: (invoiceId: string) => sendAutoKeyInvoice(invoiceId),
    onSuccess: () => setSendInvoiceFeedback('Payment link sent to customer via SMS.'),
    onError: err => setSendInvoiceFeedback(getApiErrorMessage(err, 'Failed to send invoice.')),
  })

  const assignTechMut = useMutation({
    mutationFn: (assigned_user_id: string | null) => updateAutoKeyJob(id!, { assigned_user_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to assign tech.')),
  })

  const leadSourceMut = useMutation({
    mutationFn: (commission_lead_source: string) => updateAutoKeyJob(id!, { commission_lead_source }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update commission source.')),
  })

  const recordPaymentMut = useMutation({
    mutationFn: ({ invId, method }: { invId: string; method: 'cash' | 'eftpos' | 'bank' }) =>
      updateAutoKeyInvoice(id!, invId, { status: 'paid', payment_method: method }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-invoices', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setInvoiceToPay(null)
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to record payment.')),
  })

  const accountMut = useMutation({
    mutationFn: (customer_account_id: string | null) => updateAutoKeyJob(id!, { customer_account_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update customer account.')),
  })

  const scheduleMut = useMutation({
    mutationFn: (data: { scheduled_at?: string | null; job_address?: string | null; job_type?: string | null }) =>
      updateAutoKeyJob(id!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update schedule.')),
  })

  const keyDetailsMut = useMutation({
    mutationFn: (data: { key_type?: string | null; blade_code?: string | null; chip_type?: string | null; tech_notes?: string | null }) =>
      updateAutoKeyJob(id!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update key details.')),
  })

  const uploadAttachmentMut = useMutation({
    mutationFn: (file: File) => uploadAutoKeyAttachment(file, id!),
    onSuccess: () => {
      refetchAttachments()
      qc.invalidateQueries({ queryKey: ['auto-key-attachments', id] })
      setError('')
    },
    onError: err => setError(getUploadErrorMessage(err, getApiErrorMessage(err, 'Failed to upload photo.'))),
  })

  const arrivalSmsMut = useMutation({
    mutationFn: (time_window: string) => sendAutoKeyArrivalSms(id!, time_window),
    onSuccess: () => {
      setShowArrivalSms(false)
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to send arrival SMS.')),
  })

  const toDatetimeLocal = (s?: string | null) => {
    if (!s) return ''
    const d = new Date(s)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  const handleScheduleChange = (field: 'scheduled_at' | 'job_address' | 'job_type', value: string | null) => {
    const payload: Parameters<typeof scheduleMut.mutate>[0] = {}
    if (field === 'scheduled_at') payload.scheduled_at = value ? new Date(value).toISOString() : null
    if (field === 'job_address') payload.job_address = value || null
    if (field === 'job_type') payload.job_type = value || null
    scheduleMut.mutate(payload)
  }

  const handleKeyDetailBlur = (field: 'key_type' | 'blade_code' | 'chip_type' | 'tech_notes', value: string) => {
    const trimmed = value.trim() || null
    keyDetailsMut.mutate({ [field]: trimmed })
    if (field === 'key_type') setKeyTypeEdit(null)
    if (field === 'blade_code') setBladeCodeEdit(null)
    if (field === 'chip_type') setChipTypeEdit(null)
    if (field === 'tech_notes') setTechNotesEdit(null)
  }

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || attachments.length >= 5) return
    setUploading(true)
    try {
      await uploadAttachmentMut.mutateAsync(file)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleCameraCapture(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || attachments.length >= 5) return
    setUploading(true)
    try {
      await uploadAttachmentMut.mutateAsync(file)
    } finally {
      setUploading(false)
      if (cameraInputRef.current) cameraInputRef.current.value = ''
    }
  }

  if (isLoading) return <Spinner />
  if (!job) return <EmptyState message='Mobile Services job not found.' />

  const matchingAccounts = customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(job.customer_id))

  return (
    <div className='max-w-7xl mx-auto w-full'>
      <div className='mb-5'>
        <Link
          to='/auto-key'
          className='inline-flex items-center gap-1 text-sm font-medium transition-colors'
          style={{ color: 'var(--cafe-text-muted)' }}
        >
          <ChevronLeft size={14} /> Back to Mobile Services
        </Link>
        <MobileServicesSubNav className='mt-4' />
      </div>

      <PageHeader title={`#${job.job_number} · ${job.title}`} />

      {/* Mobile quick-action strip */}
      <div className="lg:hidden mb-3 flex items-center gap-2 flex-wrap">
        <Badge status={job.status} />
        <select
          className="flex-1 min-w-0 h-9 rounded-lg border px-2 text-sm"
          style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
          value={job.status}
          disabled={statusMut.isPending}
          onChange={e => { void handleStatusChange(e.target.value as JobStatus) }}
        >
          {STATUSES.map(s => (
            <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        {job.job_address && (
          <a
            href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-sm font-medium touch-manipulation shrink-0"
            style={{ backgroundColor: 'rgba(201,162,72,0.12)', color: 'var(--cafe-amber)', border: '1px solid rgba(201,162,72,0.3)' }}
          >
            <MapPin size={14} /> Nav
          </a>
        )}
      </div>
      {statusFeedback && (
        <p className='lg:hidden text-xs rounded-md px-2 py-1.5 mb-2' style={{ backgroundColor: '#F8EBDD', color: '#6A3D21' }}>
          {statusFeedback}
        </p>
      )}

      {/* Mobile tab bar */}
      <div className="lg:hidden mb-4 -mx-4 px-4 overflow-x-auto">
        <div className="flex gap-2 flex-nowrap pb-1">
          {([
            { key: 'info', label: 'Info' },
            { key: 'vehicle', label: 'Vehicle & Key' },
            { key: 'financial', label: 'Financial' },
            { key: 'photos', label: 'Photos' },
          ] as const).map(tab => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setDetailTab(tab.key)}
              className="px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap touch-manipulation"
              style={{
                backgroundColor: detailTab === tab.key ? 'var(--cafe-amber)' : 'var(--cafe-surface)',
                color: detailTab === tab.key ? '#2C1810' : 'var(--cafe-text-muted)',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className='grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-12 gap-5 lg:gap-6'>
        <Card className='p-5 space-y-4 xl:col-span-4'>
          {/* Info tab: customer, job info, status, assign, schedule */}
          <div className={detailTab !== 'info' ? 'hidden lg:contents' : ''}>
          {/* Customer section */}
          {customer && (
            <div className='pb-3' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold text-xs uppercase tracking-widest mb-2' style={{ color: 'var(--cafe-text-muted)' }}>Customer</h2>
              <div className='space-y-1.5 text-sm'>
                <div>
                  <Link to={`/customers/${customer.id}`} className='font-medium' style={{ color: 'var(--cafe-amber)' }}>
                    {customer.full_name || 'Unknown'}
                  </Link>
                </div>
                {customer.phone && (
                  <a href={`tel:${customer.phone.replace(/\s/g, '')}`} className='flex items-center gap-1.5 touch-manipulation' style={{ color: 'var(--cafe-text)' }}>
                    <Phone size={14} /> {customer.phone}
                  </a>
                )}
                {customer.email && (
                  <a href={`mailto:${customer.email}`} className='flex items-center gap-1.5' style={{ color: 'var(--cafe-text)' }}>
                    <Mail size={14} /> {customer.email}
                  </a>
                )}
              </div>
            </div>
          )}

          <h2 className='font-semibold text-xs uppercase tracking-widest' style={{ color: 'var(--cafe-text-muted)' }}>Job Info</h2>
          <div className='space-y-2 text-sm'>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Status</span><Badge status={job.status} /></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Priority</span><span className='capitalize'>{job.priority}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Created</span><span>{formatDate(job.created_at)}</span></div>
            {(job.vehicle_make || job.vehicle_model) && (
              <div className='flex justify-between items-center gap-2'>
                <span style={{ color: 'var(--cafe-text-muted)' }}>Vehicle</span>
                <div className='flex items-center gap-1.5'>
                  <span>{[job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}</span>
                  {jobContext?.complexity && <AklComplexityPill complexity={jobContext.complexity} className='px-2 text-xs' />}
                </div>
              </div>
            )}
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Qty</span><span>{job.key_quantity}</span></div>
            {job.job_type && <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Type</span><span>{job.job_type}</span></div>}
            {job.additional_services_json && (() => {
              try {
                const arr = JSON.parse(job.additional_services_json) as { preset?: string | null; custom?: string | null }[]
                if (!Array.isArray(arr) || arr.length === 0) return null
                const lines = arr.map(x => x.custom || x.preset).filter(Boolean)
                if (!lines.length) return null
                return (
                  <div className='pt-1'>
                    <div className='text-xs uppercase tracking-widest mb-1' style={{ color: 'var(--cafe-text-muted)' }}>Additional services</div>
                    <ul className='text-sm list-disc pl-5 space-y-0.5' style={{ color: 'var(--cafe-text)' }}>
                      {lines.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                )
              } catch {
                return null
              }
            })()}
            {job.scheduled_at && <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Scheduled</span><span style={{ color: 'var(--cafe-amber)' }}>{formatDate(job.scheduled_at)}</span></div>}
            {job.job_address && (
              <div>
                <div className='flex justify-between items-start gap-2'><span style={{ color: 'var(--cafe-text-muted)' }}>Address</span><span className='text-right'>{job.job_address}</span></div>
                <a
                  href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 min-h-9 px-3 py-1.5 rounded-lg text-sm font-medium mt-2 touch-manipulation"
                  style={{ color: 'var(--cafe-text)', backgroundColor: 'rgba(201, 162, 72, 0.15)', border: '1px solid var(--cafe-amber)' }}
                >
                  <MapPin size={14} /> Get Directions
                </a>
              </div>
            )}
            {job.job_address && (
              <button
                type="button"
                onClick={() => setShowArrivalSms(true)}
                className="inline-flex items-center gap-2 min-h-11 px-3 py-2 rounded-lg text-sm font-medium touch-manipulation"
                style={{ color: 'var(--cafe-amber)', backgroundColor: 'rgba(201, 162, 72, 0.12)' }}
              >
                <MessageSquare size={16} /> Send arrival SMS to customer
              </button>
            )}
          </div>

          </div>{/* end info tab group */}

          {/* Vehicle & Key tab: vehicle DB, key details, tech notes */}
          <div className={detailTab !== 'vehicle' ? 'hidden lg:contents' : ''}>
          {hasFeature('auto_key') && (
            <>
              <h3 className='font-semibold text-xs uppercase tracking-widest pt-2' style={{ color: 'var(--cafe-text-muted)' }}>
                Vehicle database
              </h3>
              <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>
                Refine make, model, and year, then tap a match to fill vehicle, key type, chip, blade code, and tech notes.
              </p>
              <div className='space-y-2'>
                <Input
                  label='Search make'
                  value={vLookupMake}
                  onChange={e => setVLookupMake(e.target.value)}
                  placeholder='e.g. Toyota'
                />
                <Input
                  label='Search model'
                  value={vLookupModel}
                  onChange={e => setVLookupModel(e.target.value)}
                  placeholder='e.g. Hilux'
                />
                <Input
                  label='Year (optional)'
                  type='number'
                  value={vLookupYear}
                  onChange={e => setVLookupYear(e.target.value)}
                  placeholder='Narrows generation'
                />
              </div>
              {vehicleSpecSearch && vehicleSpecSearch.matches.length > 0 && (
                <ul className='max-h-44 overflow-y-auto space-y-1 rounded-lg border p-1.5' style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-paper)' }}>
                  {vehicleSpecSearch.matches.map((m, i) => (
                    <li key={`${m.label}-${i}`}>
                      <button
                        type='button'
                        disabled={applyVehicleDbMut.isPending}
                        className='w-full text-left px-2 py-1.5 rounded text-sm transition disabled:opacity-50'
                        style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)' }}
                        onClick={() => applyVehicleDbMut.mutate(m)}
                      >
                        <span className='block'>{m.label}</span>
                        {(m.suggested_blade_code || (m.key_blanks && m.key_blanks.length > 0)) && (
                          <span className='block text-xs mt-0.5' style={{ color: 'var(--cafe-text-muted)' }}>
                            Blanks: {(m.key_blanks ?? []).slice(0, 4).map(b => b.primary_code || b.blank_reference).filter(Boolean).join(', ') || m.suggested_blade_code}
                          </span>
                        )}
                        <div className='flex flex-wrap gap-1 mt-1'>
                          {m.akl_complexity && <AklComplexityPill complexity={m.akl_complexity} className='px-2 text-xs' />}
                          {m.bsu_required && <span className='rounded-full px-1.5 py-0.5 text-[10px] font-semibold' style={{ backgroundColor: 'rgba(201,162,72,0.15)', color: '#9A7220' }}>BSU required</span>}
                          {m.pin_required && <span className='rounded-full px-1.5 py-0.5 text-[10px] font-semibold' style={{ backgroundColor: 'rgba(201,106,90,0.12)', color: '#C96A5A' }}>PIN required</span>}
                          {m.dealer_required && <span className='rounded-full px-1.5 py-0.5 text-[10px] font-semibold' style={{ backgroundColor: 'rgba(201,106,90,0.2)', color: '#C96A5A' }}>Dealer only</span>}
                          {m.eeprom_required && !m.obd_programmable && <span className='rounded-full px-1.5 py-0.5 text-[10px] font-semibold' style={{ backgroundColor: 'rgba(120,100,180,0.15)', color: '#7060B0' }}>EEPROM</span>}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          <h3 className='font-semibold text-xs uppercase tracking-widest pt-2' style={{ color: 'var(--cafe-text-muted)' }}>Key Details</h3>
          <Input
            label='Key Type'
            value={keyTypeEdit !== null ? keyTypeEdit : (job.key_type ?? '')}
            onChange={e => setKeyTypeEdit(e.target.value)}
            onBlur={e => { handleKeyDetailBlur('key_type', e.target.value) }}
            disabled={keyDetailsMut.isPending}
            placeholder='From intake'
          />
          <Input
            label='Blade Code'
            value={bladeCodeEdit !== null ? bladeCodeEdit : (job.blade_code ?? '')}
            onChange={e => setBladeCodeEdit(e.target.value)}
            onBlur={e => { handleKeyDetailBlur('blade_code', e.target.value) }}
            disabled={keyDetailsMut.isPending}
            placeholder='Blade code'
          />
          <Input
            label='Transponder Chip Type'
            value={chipTypeEdit !== null ? chipTypeEdit : (job.chip_type ?? '')}
            onChange={e => setChipTypeEdit(e.target.value)}
            onBlur={e => { handleKeyDetailBlur('chip_type', e.target.value) }}
            disabled={keyDetailsMut.isPending}
            placeholder='Chip type'
          />

          <h3 className='font-semibold text-xs uppercase tracking-widest pt-2' style={{ color: 'var(--cafe-text-muted)' }}>Tech Notes</h3>
          <textarea
            value={techNotesEdit !== null ? techNotesEdit : (job.tech_notes ?? '')}
            onChange={e => setTechNotesEdit(e.target.value)}
            onBlur={e => { handleKeyDetailBlur('tech_notes', e.target.value) }}
            disabled={keyDetailsMut.isPending}
            placeholder='Notes for the technician'
            className='w-full min-h-20 px-3 py-2 rounded-lg text-sm resize-y'
            style={{ backgroundColor: 'var(--cafe-bg)', border: '1px solid var(--cafe-border)', color: 'var(--cafe-text)' }}
          />

          {/* Known Issues warning */}
          {jobContext?.known_issues && jobContext.known_issues.length > 0 && (
            <div className='space-y-2 pt-2'>
              <h3 className='font-semibold text-xs uppercase tracking-widest' style={{ color: '#C96A5A' }}>⚠ Known Issues</h3>
              {jobContext.known_issues.map((issue: KnownIssue, i: number) => (
                <div key={i} className='rounded-lg border p-3 space-y-1 text-sm'
                  style={{ borderColor: '#C96A5A', backgroundColor: 'rgba(201,106,90,0.07)' }}>
                  <div className='flex items-start justify-between gap-2'>
                    <span className='font-medium' style={{ color: 'var(--cafe-text)' }}>{issue.issue}</span>
                    {issue.severity && <SeverityBadge severity={issue.severity} />}
                  </div>
                  {issue.notes && <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>{issue.notes}</p>}
                  {issue.resolution && (
                    <p className='text-xs font-medium' style={{ color: 'var(--cafe-text)' }}>
                      Fix: {issue.resolution}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Tool Recommendations */}
          {jobContext?.tool_recommendations && jobContext.tool_recommendations.length > 0 && (
            <div className='space-y-2 pt-2'>
              <h3 className='font-semibold text-xs uppercase tracking-widest' style={{ color: 'var(--cafe-text-muted)' }}>Recommended Tools</h3>
              {jobContext.tool_recommendations.map((rec: ToolRecommendation, i: number) => (
                <div key={i} className='rounded-lg border p-3 text-sm space-y-1'
                  style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-paper)' }}>
                  <div className='flex items-center justify-between gap-2'>
                    {rec.job_type && <span className='text-xs font-medium uppercase tracking-wide' style={{ color: 'var(--cafe-text-muted)' }}>{rec.job_type}</span>}
                    {rec.risk_level && <SeverityBadge severity={rec.risk_level} />}
                  </div>
                  <div className='flex items-center gap-1.5'>
                    <span className='font-semibold' style={{ color: 'var(--cafe-amber)' }}>Primary:</span>
                    <span>{rec.primary_tool}</span>
                  </div>
                  {rec.backup_tool && (
                    <div className='flex items-center gap-1.5'>
                      <span style={{ color: 'var(--cafe-text-muted)' }}>Backup:</span>
                      <span>{rec.backup_tool}</span>
                    </div>
                  )}
                  {rec.escalation_tool && (
                    <div className='flex items-center gap-1.5'>
                      <span style={{ color: 'var(--cafe-text-muted)' }}>Escalate to:</span>
                      <span>{rec.escalation_tool}</span>
                    </div>
                  )}
                  {rec.notes && <p className='text-xs pt-0.5' style={{ color: 'var(--cafe-text-muted)' }}>{rec.notes}</p>}
                </div>
              ))}
            </div>
          )}

          {/* Cutting Machine Profiles */}
          {jobContext?.cutting_profiles && jobContext.cutting_profiles.length > 0 && (
            <div className='space-y-2 pt-2'>
              <h3 className='font-semibold text-xs uppercase tracking-widest' style={{ color: 'var(--cafe-text-muted)' }}>Cutting Machine Profiles</h3>
              {jobContext.cutting_profiles.map((cp: CuttingProfile, i: number) => (
                <div key={i} className='rounded-lg border p-3 text-sm space-y-2'
                  style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-paper)' }}>
                  <div className='font-medium' style={{ color: 'var(--cafe-text)' }}>
                    {cp.blank_reference}
                    {cp.description ? ` — ${cp.description}` : ''}
                  </div>
                  <div className='grid grid-cols-1 gap-1 text-xs'>
                    {cp.dolphin_xp005l && (
                      <div className='flex justify-between'>
                        <span style={{ color: 'var(--cafe-text-muted)' }}>Dolphin XP-005L</span>
                        <span className='font-mono font-medium'>{cp.dolphin_xp005l}</span>
                      </div>
                    )}
                    {cp.condor_xc_mini_plus_ii && (
                      <div className='flex justify-between'>
                        <span style={{ color: 'var(--cafe-text-muted)' }}>Condor XC-Mini Plus II</span>
                        <span className='font-mono font-medium'>{cp.condor_xc_mini_plus_ii}</span>
                      </div>
                    )}
                    {cp.silca_alpha_pro && (
                      <div className='flex justify-between'>
                        <span style={{ color: 'var(--cafe-text-muted)' }}>Silca Alpha Pro</span>
                        <span className='font-mono font-medium'>{cp.silca_alpha_pro}</span>
                      </div>
                    )}
                    {cp.silca_futura_pro && (
                      <div className='flex justify-between'>
                        <span style={{ color: 'var(--cafe-text-muted)' }}>Silca Futura Pro</span>
                        <span className='font-mono font-medium'>{cp.silca_futura_pro}</span>
                      </div>
                    )}
                  </div>
                  {cp.notes && <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>{cp.notes}</p>}
                </div>
              ))}
            </div>
          )}

          </div>{/* end vehicle tab group */}

          {/* Photos tab */}
          <div className={detailTab !== 'photos' ? 'hidden lg:contents' : ''}>
          <h3 className='font-semibold text-xs uppercase tracking-widest pt-2' style={{ color: 'var(--cafe-text-muted)' }}>Photo Attachments</h3>
          <div className='space-y-2'>
            {attachments.length > 0 && (
              <div className='flex flex-wrap gap-2'>
                {attachments.map((a: { id: string; storage_key: string }) => (
                  <SecureAttachmentLink
                    key={a.id}
                    storageKey={a.storage_key}
                    target='_blank'
                    rel='noopener noreferrer'
                    className='block w-16 h-16 rounded-lg overflow-hidden shrink-0'
                    style={{ border: '1px solid var(--cafe-border)' }}
                  >
                    <SecureAttachmentImage
                      storageKey={a.storage_key}
                      alt=''
                      className='w-full h-full object-cover'
                    />
                  </SecureAttachmentLink>
                ))}
              </div>
            )}
            {attachments.length < 5 && (
              <div className='flex gap-2'>
                <input
                  ref={fileInputRef}
                  type='file'
                  accept='image/*'
                  onChange={handlePhotoUpload}
                  className='hidden'
                />
                <input
                  ref={cameraInputRef}
                  type='file'
                  accept='image/*'
                  capture='environment'
                  onChange={handleCameraCapture}
                  className='hidden'
                />
                <Button
                  variant='secondary'
                  className='text-sm py-2 px-3'
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading || attachments.length >= 5}
                >
                  {uploading ? 'Uploading…' : 'Choose photo'}
                </Button>
                <Button
                  variant='secondary'
                  className='text-sm py-2 px-3'
                  onClick={() => cameraInputRef.current?.click()}
                  disabled={uploading || attachments.length >= 5}
                >
                  <Camera size={14} /> Camera
                </Button>
              </div>
            )}
            <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>{attachments.length}/5 photos</p>
          </div>

          </div>{/* end photos tab group */}

          {/* Info tab continued: status, assign, lead source, account, schedule */}
          <div className={detailTab !== 'info' ? 'hidden lg:contents' : ''}>
          <Select
            label='Status'
            value={job.status}
            onChange={e => { void handleStatusChange(e.target.value as JobStatus) }}
            disabled={statusMut.isPending}
          >
            {STATUSES.map(s => (
              <option key={s} value={s}>{STATUS_LABELS[s] ?? s.replace(/_/g, ' ')}</option>
            ))}
          </Select>
          {statusFeedback && (
            <p className='hidden lg:block text-xs rounded-md px-2 py-1.5' style={{ backgroundColor: '#F8EBDD', color: '#6A3D21' }}>
              {statusFeedback}
            </p>
          )}

          {!isSolo && (
          <Select
            label='Assign tech'
            value={job.assigned_user_id ?? ''}
            onChange={e => assignTechMut.mutate(e.target.value || null)}
            disabled={assignTechMut.isPending}
          >
            <option value=''>Unassigned</option>
            {users.map((u: { id: string; full_name: string }) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </Select>
          )}

          <Select
            label='Job source (commission tier)'
            value={(job as { commission_lead_source?: string }).commission_lead_source ?? 'shop_referred'}
            onChange={e => leadSourceMut.mutate(e.target.value)}
            disabled={leadSourceMut.isPending}
          >
            {MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>

          <Select
            label='Customer Account'
            value={job.customer_account_id ?? ''}
            onChange={e => accountMut.mutate(e.target.value || null)}
            disabled={accountMut.isPending}
          >
            <option value=''>No B2B account</option>
            {matchingAccounts.map((account: CustomerAccount) => (
              <option key={account.id} value={account.id}>{account.name}{account.account_code ? ` (${account.account_code})` : ''}</option>
            ))}
          </Select>

          <h3 className='font-semibold text-xs uppercase tracking-widest pt-2' style={{ color: 'var(--cafe-text-muted)' }}>Schedule</h3>
          <Select
            label='Job type'
            value={job.job_type ?? ''}
            onChange={e => handleScheduleChange('job_type', e.target.value || null)}
            disabled={scheduleMut.isPending}
          >
            <option value=''>Not set</option>
            {AUTO_KEY_JOB_TYPES.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </Select>
          <Input
            label='Scheduled date & time'
            type='datetime-local'
            value={toDatetimeLocal(job.scheduled_at) ?? ''}
            onChange={e => handleScheduleChange('scheduled_at', e.target.value || null)}
            disabled={scheduleMut.isPending}
          />
          <Input
            label='Job address (mobile)'
            value={addressEdit !== null ? addressEdit : (job.job_address ?? '')}
            onChange={e => setAddressEdit(e.target.value)}
            onBlur={() => {
              const v = addressEdit !== null ? addressEdit : (job.job_address ?? '')
              handleScheduleChange('job_address', v.trim() || null)
              setAddressEdit(null)
            }}
            disabled={scheduleMut.isPending}
            placeholder='Address for mobile visits'
          />

          {error && <p className='text-sm' style={{ color: '#C96A5A' }}>{error}</p>}
          </div>{/* end info tab group (status/assign/schedule) */}
        </Card>

        {showArrivalSms && (
          <Modal title="Send arrival SMS" onClose={() => setShowArrivalSms(false)}>
            <p className="text-sm mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
              Customer will receive: &quot;Your technician is on the way and will arrive between [time window].&quot;
            </p>
            <Input
              label="Time window"
              value={arrivalWindow}
              onChange={e => setArrivalWindow(e.target.value)}
              placeholder="e.g. 9–11am, 2–4pm"
            />
            <div className="flex gap-2 mt-4">
              <Button variant="secondary" onClick={() => setShowArrivalSms(false)}>Cancel</Button>
              <Button onClick={() => arrivalSmsMut.mutate(arrivalWindow)} disabled={arrivalSmsMut.isPending || !arrivalWindow.trim()}>
                {arrivalSmsMut.isPending ? 'Sending…' : 'Send SMS'}
              </Button>
            </div>
          </Modal>
        )}

        <div className={`lg:col-span-2 xl:col-span-8 space-y-5${detailTab !== 'financial' ? ' hidden lg:block' : ''}`}>
          {showQuoteModal && (
            <Modal title="Create Quote" onClose={() => setShowQuoteModal(false)}>
              <CreateQuoteInlineForm jobId={id!} onClose={() => setShowQuoteModal(false)} />
            </Modal>
          )}

          <Card>
            <div className='px-5 py-3.5 flex items-center justify-between' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Quotes</h2>
              <Button variant="secondary" className="text-xs py-1 px-2 flex items-center gap-1" onClick={() => setShowQuoteModal(true)}>
                <Plus size={13} /> New Quote
              </Button>
            </div>
            {(quotes ?? []).length === 0 ? (
              <p className='px-5 py-4 text-sm' style={{ color: 'var(--cafe-text-muted)' }}>No quotes yet.</p>
            ) : (
              quotes.map(q => (
                <div key={q.id} className='px-5 py-3 text-sm space-y-2' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <div className='flex items-center justify-between'>
                    <div>
                      <p style={{ color: 'var(--cafe-text)' }}>{formatDate(q.created_at)}</p>
                      <p className='text-xs capitalize' style={{ color: q.status === 'sent' ? '#4A8A4A' : q.status === 'declined' ? '#C96A5A' : 'var(--cafe-text-muted)' }}>
                        {q.status}{q.sent_at ? ` · sent ${formatDate(q.sent_at)}` : ''}
                      </p>
                    </div>
                    <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{formatCents(q.total_cents)}</p>
                  </div>
                  {(q.line_items ?? []).map((li, i) => (
                    <p key={i} className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>
                      {li.quantity} × {li.description} — {formatCents(li.unit_price_cents)} ea
                    </p>
                  ))}
                  {q.status === 'draft' && (
                    <Button
                      className="text-xs py-1 px-3 flex items-center gap-1"
                      onClick={() => sendQuoteMut.mutate(q.id)}
                      disabled={sendQuoteMut.isPending}
                    >
                      <Send size={12} /> {sendQuoteMut.isPending ? 'Sending…' : 'Send Quote to Customer'}
                    </Button>
                  )}
                </div>
              ))
            )}
          </Card>

          <Card>
            <div className='px-5 py-3.5 flex items-center justify-between' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Invoices</h2>
              {quotes.length > 0 && invoices.length === 0 && (
                <Button
                  variant="secondary"
                  className="text-xs py-1 px-2 flex items-center gap-1"
                  onClick={() => createInvoiceMut.mutate(quotes[0].id)}
                  disabled={createInvoiceMut.isPending}
                >
                  <Plus size={13} /> {createInvoiceMut.isPending ? 'Creating…' : 'Create Invoice'}
                </Button>
              )}
            </div>
            {(invoices ?? []).length === 0 ? (
              <p className='px-5 py-4 text-sm' style={{ color: 'var(--cafe-text-muted)' }}>
                {quotes.length === 0 ? 'Create a quote first, then generate an invoice.' : 'No invoice yet — click Create Invoice above.'}
              </p>
            ) : (
              invoices.map(inv => (
                <div key={inv.id} className='px-5 py-3 text-sm space-y-2' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <div className='flex items-center justify-between flex-wrap gap-2'>
                    <div>
                      <p style={{ color: 'var(--cafe-text)', fontWeight: 600 }}>{inv.invoice_number}</p>
                      <p className='text-xs' style={{ color: inv.status === 'paid' ? '#4A8A4A' : inv.status === 'void' ? '#999' : '#C9A248' }}>
                        {inv.status === 'paid' ? '✓ Paid' : inv.status === 'void' ? 'Void' : 'Unpaid'}
                        {inv.payment_method && inv.status === 'paid' ? ` · ${inv.payment_method}` : ''}
                        {' · '}{formatDate(inv.created_at)}
                      </p>
                    </div>
                    <p className='font-semibold' style={{ color: inv.status === 'paid' ? '#4A8A4A' : 'var(--cafe-text)' }}>{formatCents(inv.total_cents)}</p>
                  </div>
                  <div className='flex gap-2 flex-wrap'>
                    {inv.status === 'unpaid' && (
                      <>
                        <Button
                          variant="secondary"
                          className="text-xs py-1 px-2 flex items-center gap-1"
                          onClick={() => { setSendInvoiceFeedback(''); sendInvoiceMut.mutate(inv.id) }}
                          disabled={sendInvoiceMut.isPending}
                        >
                          <Send size={12} /> {sendInvoiceMut.isPending ? 'Sending…' : 'Send to Customer'}
                        </Button>
                        <Button
                          variant="secondary"
                          className="text-xs py-1 px-2 flex items-center gap-1"
                          onClick={() => setInvoiceToPay({ id: inv.id, invoice_number: inv.invoice_number, total_cents: inv.total_cents })}
                        >
                          <CheckCircle size={12} /> Record Payment
                        </Button>
                      </>
                    )}
                  </div>
                  {sendInvoiceFeedback && inv.id && (
                    <p className='text-xs rounded px-2 py-1' style={{ backgroundColor: '#F0FAF0', color: '#2A6A2A' }}>{sendInvoiceFeedback}</p>
                  )}
                </div>
              ))
            )}
          </Card>
        </div>
      </div>
      {invoiceToPay && (
        <Modal title="Record payment" onClose={() => setInvoiceToPay(null)}>
          <div className="space-y-4">
            <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'var(--cafe-bg)', border: '1px solid var(--cafe-border)' }}>
              <p><span style={{ color: 'var(--cafe-text-muted)' }}>Invoice</span> #{invoiceToPay.invoice_number}</p>
              <p><span style={{ color: 'var(--cafe-text-muted)' }}>Total</span> {formatCents(invoiceToPay.total_cents)}</p>
            </div>
            <Select
              label="Payment method"
              value={paymentMethod}
              onChange={e => setPaymentMethod(e.target.value as 'cash' | 'eftpos' | 'bank')}
            >
              <option value="cash">Cash</option>
              <option value="eftpos">EFTPOS</option>
              <option value="bank">Bank transfer</option>
            </Select>
            {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
            <div className="flex gap-2 pt-2">
              <Button variant="secondary" className="flex-1" onClick={() => setInvoiceToPay(null)}>Cancel</Button>
              <Button
                className="flex-1"
                onClick={() => recordPaymentMut.mutate({ invId: invoiceToPay.id, method: paymentMethod })}
                disabled={recordPaymentMut.isPending}
              >
                <CheckCircle size={14} />
                {recordPaymentMut.isPending ? 'Recording…' : 'Mark paid'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
