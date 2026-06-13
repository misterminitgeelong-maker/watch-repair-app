import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Phone, Clock, MapPin, X } from 'lucide-react'
import {
  createAutoKeyInvoiceFromQuote,
  deleteAutoKeyJob,
  getApiErrorMessage,
  listAutoKeyInvoices,
  listAutoKeyQuotes,
  listCustomerAccounts,
  sendAutoKeyQuote,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { AklComplexityPill, parseAklComplexity } from '@/components/auto-key/AklComplexityPill'
import { Badge, Button, Card, Modal, Select } from '@/components/ui'
import { formatDate, STATUS_LABELS } from '@/lib/utils'
import { STATUSES, computeSlaChip, formatCents, nextMobileStatus } from './dispatchHelpers'
import { SlaChipBadge } from './SlaChipBadge'
import { CreateQuoteModal } from './CreateQuoteModal'

export function AutoKeyJobCard({
  job,
  users,
  isSolo,
  /** When true, skip per-job quotes/invoices/account queries so long lists do not fan out dozens of parallel API calls (can freeze the UI). */
  listMode = false,
}: {
  job: { id: string; job_number: string; title: string; customer_id: string; customer_name?: string | null; customer_phone?: string | null; customer_account_id?: string; assigned_user_id?: string; vehicle_make?: string; vehicle_model?: string; vehicle_year?: number; registration_plate?: string; key_type?: string; key_quantity: number; programming_status: string; status: JobStatus; priority?: string; created_at: string; salesperson?: string; scheduled_at?: string; job_address?: string; job_type?: string; tech_notes?: string }
  users: { id: string; full_name: string }[]
  isSolo?: boolean
  listMode?: boolean
}) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showQuoteModal, setShowQuoteModal] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [statusFeedback, setStatusFeedback] = useState('')
  const [actionError, setActionError] = useState('')
  const [confirmStatus, setConfirmStatus] = useState<JobStatus | null>(null)

  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
    enabled: !listMode,
  })
  const matchingAccounts = listMode ? [] : customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(job.customer_id))

  const { data: quotes = [] } = useQuery({
    queryKey: ['auto-key-quotes', job.id],
    queryFn: () => listAutoKeyQuotes(job.id).then(r => r.data),
    enabled: !listMode,
  })
  const { data: invoices = [] } = useQuery({
    queryKey: ['auto-key-invoices', job.id],
    queryFn: () => listAutoKeyInvoices(job.id).then(r => r.data),
    enabled: !listMode,
  })

  const latestQuote = quotes[0]
  const latestInvoice = invoices[0]
  const nextStatus = nextMobileStatus(job.status)
  const quickStatusLabel = nextStatus ? `Mark ${STATUS_LABELS[nextStatus] ?? nextStatus.replace(/_/g, ' ')}` : null

  const statusMut = useMutation({
    mutationFn: (status: JobStatus) => updateAutoKeyJobStatus(job.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
    onError: (err) => setActionError(getApiErrorMessage(err, 'Could not update job status. Please try again.')),
  })

  const updateAccountMut = useMutation({
    mutationFn: (customer_account_id: string | null) => updateAutoKeyJob(job.id, { customer_account_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
    onError: (err) => setActionError(getApiErrorMessage(err, 'Could not update the linked account.')),
  })

  const assignTechMut = useMutation({
    mutationFn: (assigned_user_id: string | null) => updateAutoKeyJob(job.id, { assigned_user_id }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-jobs'] }),
    onError: (err) => setActionError(getApiErrorMessage(err, 'Could not assign the technician.')),
  })

  const sendQuoteMut = useMutation({
    mutationFn: (quoteId: string) => sendAutoKeyQuote(quoteId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-quotes', job.id] }),
    onError: (err) => setActionError(getApiErrorMessage(err, 'Could not send the quote. Check the customer contact details and try again.')),
  })

  const invoiceMut = useMutation({
    mutationFn: (quoteId: string) => createAutoKeyInvoiceFromQuote(job.id, quoteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-invoices', job.id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
    },
    onError: (err) => setActionError(getApiErrorMessage(err, 'Could not create the invoice from this quote.')),
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

  const handleStatusChange = async (status: JobStatus) => {
    if (['work_completed', 'failed_job'].includes(status)) {
      setConfirmStatus(status)
      return
    }
    setStatusFeedback('')
    setActionError('')
    const invoicesBefore = invoices.length
    try {
      await statusMut.mutateAsync(status)
    } catch {
      // onError surfaces the message; stop here so we don't show a misleading completion note.
      return
    }
    if (status !== 'work_completed') return

    const [{ data: latestQuotes }, { data: latestInvoices }] = await Promise.all([
      listAutoKeyQuotes(job.id),
      listAutoKeyInvoices(job.id),
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
            <p className="text-xs font-mono font-semibold" style={{ color: 'var(--ms-accent)' }}>#{job.job_number}</p>
            {!isSolo && (
              <span className="text-[11px] font-medium rounded-full px-2 py-0.5" style={{ backgroundColor: job.assigned_user_id ? 'rgba(93,74,155,0.2)' : 'rgba(138,117,99,0.25)', color: job.assigned_user_id ? '#5D4A9B' : 'var(--ms-text-muted)' }}>
                {job.assigned_user_id ? (users.find(u => u.id === job.assigned_user_id)?.full_name ?? 'Assigned') : 'Unassigned'}
              </span>
            )}
            {job.priority === 'urgent' && (
              <span className="text-[11px] font-bold uppercase rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(201,100,90,0.15)', color: '#C96A5A' }}>
                Urgent
              </span>
            )}
            {job.priority === 'high' && (
              <span className="text-[11px] font-bold uppercase rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(200,130,50,0.15)', color: '#B87030' }}>
                High
              </span>
            )}
            {(() => {
              const chip = computeSlaChip(job)
              return chip ? <SlaChipBadge chip={chip} /> : null
            })()}
            {job.customer_account_id && (
              <span className="text-[11px] font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: '#EAF4EA', color: '#2F6A3D' }}>
                B2B
              </span>
            )}
          </div>
          <span className="text-sm font-semibold hover:underline block" style={{ color: 'var(--ms-text)' }}>
            {job.title}
          </span>
          {job.customer_name && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{job.customer_name}</p>
          )}
          {job.customer_phone && (
            <a
              href={`tel:${job.customer_phone.replace(/\s/g, '')}`}
              className="inline-flex items-center gap-1 text-xs font-medium mt-0.5 touch-manipulation"
              style={{ color: 'var(--ms-accent)' }}
              onClick={e => e.stopPropagation()}
            >
              <Phone size={11} /> {job.customer_phone}
            </a>
          )}
          {(() => {
            const scheduledLabel = job.scheduled_at
              ? new Date(job.scheduled_at).toLocaleString('en-AU', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
              : null
            return scheduledLabel ? (
              <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-xs font-medium" style={{ backgroundColor: 'rgba(245,158,11,0.12)', color: 'var(--ms-accent)' }}>
                <Clock size={11} />
                {scheduledLabel}
              </span>
            ) : null
          })()}
          {(job.vehicle_make || job.vehicle_model || job.registration_plate) && (
            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
              <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                {[job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}
                {job.vehicle_year ? ` · ${job.vehicle_year}` : ''}
                {job.registration_plate ? ` · ${job.registration_plate}` : ''}
              </p>
              {(() => {
                const complexity = parseAklComplexity(job.tech_notes)
                return complexity ? <AklComplexityPill complexity={complexity} /> : null
              })()}
            </div>
          )}
          {job.job_address && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>
              {job.job_address}
            </p>
          )}
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            Key: {job.key_type || 'Unspecified'} · Qty {job.key_quantity}
          </p>
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            {formatDate(job.created_at)}{job.salesperson ? ` · ${job.salesperson}` : ''}
          </p>
          {job.job_type && (
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{job.job_type}</p>
          )}
          {job.job_address && (
            <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(job.job_address)}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="inline-flex items-center gap-1 text-xs font-medium mt-1 hover:underline" style={{ color: 'var(--ms-accent)' }}>
              <MapPin size={12} /> Get directions
            </a>
          )}

          {latestQuote && (
            <p className="text-xs mt-2" style={{ color: 'var(--ms-text-mid)' }}>
              Latest quote: {formatCents(latestQuote.total_cents)} ({latestQuote.status})
            </p>
          )}
          {latestInvoice && (
            <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
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
            onChange={e => { void handleStatusChange(e.target.value as JobStatus) }}
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
          {(matchingAccounts.length > 0 || job.customer_account_id) && (
            <div className="mt-2">
              <Select
                value={job.customer_account_id ?? ''}
                onChange={e => updateAccountMut.mutate(e.target.value || null)}
                disabled={updateAccountMut.isPending}
              >
                <option value="">No account</option>
                {matchingAccounts.map((account: CustomerAccount) => (
                  <option key={account.id} value={account.id}>
                    {account.name}{account.account_code ? ` (${account.account_code})` : ''}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="mt-2 space-y-2">
            {nextStatus && (
              <button
                type="button"
                className="w-full inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none md:min-h-10 md:py-2"
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', boxShadow: '0 2px 6px rgba(245,158,11,0.35)' }}
                onClick={() => { void handleStatusChange(nextStatus) }}
                disabled={statusMut.isPending}
              >
                {statusMut.isPending ? 'Updating…' : quickStatusLabel}
              </button>
            )}
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
            {statusFeedback && (
              <p className="text-xs rounded-md px-2 py-1.5" style={{ backgroundColor: '#F8EBDD', color: '#6A3D21' }}>
                {statusFeedback}
              </p>
            )}
            {actionError && (
              <p role="alert" className="text-xs rounded-md px-2 py-1.5 flex items-start justify-between gap-2" style={{ backgroundColor: '#FFF1ED', color: '#A4392B', border: '1px solid #E7C6B7' }}>
                <span>{actionError}</span>
                <button type="button" aria-label="Dismiss error" onClick={() => setActionError('')} className="shrink-0 font-semibold">
                  <X size={12} />
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </Card>
      {confirmStatus && (
        <Modal
          title={`Mark as ${STATUS_LABELS[confirmStatus] ?? confirmStatus.replace(/_/g, ' ')}?`}
          onClose={() => setConfirmStatus(null)}
        >
          <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
            {confirmStatus === 'failed_job'
              ? 'This will mark the job as failed. No invoice will be auto-created.'
              : 'This will mark the job as work completed. An invoice will be auto-created and payment link sent to the customer.'}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={() => setConfirmStatus(null)}>Cancel</Button>
            <Button
              className="flex-1"
              onClick={async () => {
                const s = confirmStatus
                setConfirmStatus(null)
                setStatusFeedback('')
                setActionError('')
                const invoicesBefore = invoices.length
                try {
                  await statusMut.mutateAsync(s)
                } catch {
                  return
                }
                if (s !== 'work_completed') return
                const [{ data: latestQuotes }, { data: latestInvoices }] = await Promise.all([
                  listAutoKeyQuotes(job.id),
                  listAutoKeyInvoices(job.id),
                ])
                const newestQuote = latestQuotes[0]
                if (latestInvoices.length > invoicesBefore) { setStatusFeedback('Work completed — invoice created and payment link sent to customer.'); return }
                if (!newestQuote) { setStatusFeedback('Work completed. No invoice auto-created because no quote exists yet.'); return }
                if (newestQuote.status === 'declined') { setStatusFeedback('Work completed. No invoice auto-created because the latest quote is declined.'); return }
                setStatusFeedback('Work completed. No new invoice was created (an invoice may already exist).')
              }}
              disabled={statusMut.isPending}
            >
              {statusMut.isPending ? 'Updating…' : 'Confirm'}
            </Button>
          </div>
        </Modal>
      )}
    {showDeleteConfirm && (
      <Modal
        title="Delete Mobile Services Job"
        onClose={() => { if (!deleteMut.isPending) { setShowDeleteConfirm(false); setDeleteError('') } }}
      >
        <div className="space-y-4">
          <p className="text-sm" style={{ color: 'var(--ms-text)' }}>Are you sure you want to delete this job?</p>
          <div className="rounded-lg px-3 py-2" style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>#{job.job_number} · {job.title}</p>
          </div>
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>This action cannot be undone.</p>
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
