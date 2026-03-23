import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { Camera, CheckCircle, ChevronLeft, MapPin, MessageSquare, Phone, Mail } from 'lucide-react'
import {
  getAutoKeyJob,
  getApiErrorMessage,
  getCustomer,
  getAttachmentDownloadUrl,
  listAutoKeyAttachments,
  listAutoKeyInvoices,
  listAutoKeyQuotes,
  listCustomerAccounts,
  listUsers,
  sendAutoKeyArrivalSms,
  updateAutoKeyInvoice,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  uploadAutoKeyAttachment,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { AUTO_KEY_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import { Badge, Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'
import { formatDate } from '@/lib/utils'

const STATUSES: JobStatus[] = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'working_on',
  'en_route',
  'on_site',
  'awaiting_parts',
  'completed',
  'awaiting_collection',
  'collected',
  'no_go',
]

function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

export default function AutoKeyJobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [addressEdit, setAddressEdit] = useState<string | null>(null)
  const [keyTypeEdit, setKeyTypeEdit] = useState<string | null>(null)
  const [bladeCodeEdit, setBladeCodeEdit] = useState<string | null>(null)
  const [chipTypeEdit, setChipTypeEdit] = useState<string | null>(null)
  const [techNotesEdit, setTechNotesEdit] = useState<string | null>(null)
  const [showArrivalSms, setShowArrivalSms] = useState(false)
  const [arrivalWindow, setArrivalWindow] = useState('9–11am')
  const [invoiceToPay, setInvoiceToPay] = useState<{ id: string; invoice_number: string; total_cents: number } | null>(null)
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'eftpos' | 'bank'>('eftpos')

  const { data: job, isLoading } = useQuery({
    queryKey: ['auto-key-job', id],
    queryFn: () => getAutoKeyJob(id!).then(r => r.data),
    enabled: !!id,
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

  const assignTechMut = useMutation({
    mutationFn: (assigned_user_id: string | null) => updateAutoKeyJob(id!, { assigned_user_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to assign tech.')),
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
    onError: err => setError(getApiErrorMessage(err, 'Failed to upload photo.')),
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
    <div>
      <div className='mb-5'>
        <Link
          to='/auto-key'
          className='inline-flex items-center gap-1 text-sm font-medium transition-colors'
          style={{ color: 'var(--cafe-text-muted)' }}
        >
          <ChevronLeft size={14} /> Back to Mobile Services
        </Link>
      </div>

      <PageHeader title={`#${job.job_number} · ${job.title}`} />

      <div className='grid grid-cols-1 lg:grid-cols-3 gap-5'>
        <Card className='p-5 space-y-4'>
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
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Vehicle</span><span>{job.vehicle_make || 'Unknown'} {job.vehicle_model || ''}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Programming</span><span>{job.programming_status.replace(/_/g, ' ')}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Qty</span><span>{job.key_quantity}</span></div>
            {job.job_type && <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Type</span><span>{job.job_type}</span></div>}
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

          <h3 className='font-semibold text-xs uppercase tracking-widest pt-2' style={{ color: 'var(--cafe-text-muted)' }}>Photo Attachments</h3>
          <div className='space-y-2'>
            {attachments.length > 0 && (
              <div className='flex flex-wrap gap-2'>
                {attachments.map((a: { id: string; storage_key: string }) => (
                  <a
                    key={a.id}
                    href={getAttachmentDownloadUrl(a.storage_key)}
                    target='_blank'
                    rel='noopener noreferrer'
                    className='block w-16 h-16 rounded-lg overflow-hidden shrink-0'
                    style={{ border: '1px solid var(--cafe-border)' }}
                  >
                    <img
                      src={getAttachmentDownloadUrl(a.storage_key)}
                      alt=''
                      className='w-full h-full object-cover'
                    />
                  </a>
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

          <Select
            label='Status'
            value={job.status}
            onChange={e => statusMut.mutate(e.target.value as JobStatus)}
            disabled={statusMut.isPending}
          >
            {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </Select>

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

        <div className='lg:col-span-2 space-y-5'>
          <Card>
            <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Quotes</h2>
            </div>
            {(quotes ?? []).length === 0 ? (
              <p className='px-5 py-4 text-sm' style={{ color: 'var(--cafe-text-muted)' }}>No quotes yet.</p>
            ) : (
              quotes.map(q => (
                <div key={q.id} className='px-5 py-3 text-sm flex items-center justify-between' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <div>
                    <p style={{ color: 'var(--cafe-text)' }}>{formatDate(q.created_at)}</p>
                    <p className='text-xs capitalize' style={{ color: 'var(--cafe-text-muted)' }}>{q.status}</p>
                  </div>
                  <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{formatCents(q.total_cents)}</p>
                </div>
              ))
            )}
          </Card>

          <Card>
            <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Invoices</h2>
            </div>
            {(invoices ?? []).length === 0 ? (
              <p className='px-5 py-4 text-sm' style={{ color: 'var(--cafe-text-muted)' }}>No invoices yet.</p>
            ) : (
              invoices.map(inv => (
                <div key={inv.id} className='px-5 py-3 text-sm flex items-center justify-between flex-wrap gap-2' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <div>
                    <p style={{ color: 'var(--cafe-text)' }}>{inv.invoice_number}</p>
                    <p className='text-xs capitalize' style={{ color: 'var(--cafe-text-muted)' }}>
                      {inv.status}
                      {inv.payment_method && <span> · {inv.payment_method}</span>}
                      {' · '}{formatDate(inv.created_at)}
                    </p>
                  </div>
                  <div className='flex items-center gap-2'>
                    <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{formatCents(inv.total_cents)}</p>
                    {inv.status === 'unpaid' && (
                      <Button
                        variant="secondary"
                        className="text-xs py-1 px-2"
                        onClick={() => setInvoiceToPay({ id: inv.id, invoice_number: inv.invoice_number, total_cents: inv.total_cents })}
                      >
                        <CheckCircle size={12} /> Record payment
                      </Button>
                    )}
                  </div>
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
