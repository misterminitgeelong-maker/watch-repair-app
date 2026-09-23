import { useEffect, useMemo, useState } from 'react'
import { computeGstAmounts } from '@/lib/money'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, Trash2, MessageSquare, Copy, CheckCheck, FileText } from 'lucide-react'
import {
  DEFAULT_PAGE_SIZE,
  listQuotes,
  createQuote,
  sendQuote,
  resendQuote,
  createInvoiceFromQuote,
  listJobs,
  getApiErrorMessage,
  type QuoteLineItemInput,
  type SortDir,
} from '@/lib/api'
import { Card, PageHeader, Button, Modal, Spinner, EmptyState, Badge, Select, MobileActionMenu } from '@/components/ui'
import MobileFilterBar, { type ActiveFilter } from '@/components/mobile/MobileFilterBar'
import { ModalStickyFooter } from '@/components/mobile/MobileStickyBar'
import { formatCents, formatDate } from '@/lib/utils'
import { flattenInfinitePages, useOffsetPaginatedQuery } from '@/hooks/useOffsetPaginatedQuery'

const inputStyle = { border: '1px solid var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }
const labelStyle = { color: 'var(--ms-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' as const }

function AddLineItemRow({ item, index, onChange, onRemove }: {
  item: QuoteLineItemInput; index: number
  onChange: (i: number, key: keyof QuoteLineItemInput, value: string | number) => void
  onRemove: (i: number) => void
}) {
  const typeSelect = (
    <select className="h-11 w-full rounded px-2 text-base sm:h-8 sm:text-sm" style={inputStyle} value={item.item_type} onChange={e => onChange(index, 'item_type', e.target.value)} aria-label="Line item type">
      <option value="labor">Labor</option>
      <option value="part">Part</option>
      <option value="fee">Fee</option>
      <option value="discount">Discount</option>
    </select>
  )
  const descInput = (
    <input className="h-11 w-full rounded px-2 text-base sm:h-8 sm:text-sm" style={inputStyle} value={item.description} onChange={e => onChange(index, 'description', e.target.value)} placeholder="Movement service…" aria-label="Line item description" />
  )
  const qtyInput = (
    <input type="number" min="0.01" step="0.01" inputMode="decimal" aria-label="Quantity" className="h-11 w-full rounded px-2 text-base sm:h-8 sm:text-sm" style={inputStyle} value={item.quantity} onChange={e => { const n = Number.parseFloat(e.target.value); onChange(index, 'quantity', Number.isFinite(n) ? n : 0) }} />
  )
  const priceInput = (
    <input type="number" min="0" step="1" inputMode="numeric" aria-label="Unit price in cents" className="h-11 w-full rounded px-2 text-base sm:h-8 sm:text-sm" style={inputStyle} value={item.unit_price_cents} placeholder="5000" onChange={e => { const n = Number.parseInt(e.target.value, 10); onChange(index, 'unit_price_cents', Number.isFinite(n) ? n : 0) }} />
  )
  const deleteBtn = (
    <button onClick={() => onRemove(index)} aria-label="Remove line item" className="flex h-11 w-11 items-center justify-center transition-colors sm:h-8 sm:w-8" style={{ color: 'var(--ms-error)' }} onMouseEnter={e => (e.currentTarget.style.color = '#9B3D2A')} onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-error)')}>
      <Trash2 size={14} />
    </button>
  )

  return (
    <>
      {/* Mobile stacked layout */}
      <div className="sm:hidden space-y-2 pb-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs font-medium block mb-1" style={labelStyle}>Type</label>
            {typeSelect}
          </div>
          <div>
            <label className="text-xs font-medium block mb-1" style={labelStyle}>Qty</label>
            {qtyInput}
          </div>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1" style={labelStyle}>Description</label>
          {descInput}
        </div>
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label className="text-xs font-medium block mb-1" style={labelStyle}>Unit Price (cents)</label>
            {priceInput}
          </div>
          <div className="pb-0.5">{deleteBtn}</div>
        </div>
      </div>

      {/* Desktop 12-col layout */}
      <div className="hidden sm:grid grid-cols-12 gap-2 items-end">
        <div className="col-span-3">
          {index === 0 && <label className="text-xs font-medium block mb-1" style={labelStyle}>Type</label>}
          {typeSelect}
        </div>
        <div className="col-span-4">
          {index === 0 && <label className="text-xs font-medium block mb-1" style={labelStyle}>Description</label>}
          {descInput}
        </div>
        <div className="col-span-2">
          {index === 0 && <label className="text-xs font-medium block mb-1" style={labelStyle}>Qty</label>}
          {qtyInput}
        </div>
        <div className="col-span-2">
          {index === 0 && <label className="text-xs font-medium block mb-1" style={labelStyle}>Unit Price</label>}
          {priceInput}
        </div>
        <div className="col-span-1 flex justify-end">
          {index === 0 && <div className="mb-1 h-4" />}
          {deleteBtn}
        </div>
      </div>
    </>
  )
}

function CreateQuoteModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const jobsQuery = useOffsetPaginatedQuery({
    queryKey: ['jobs', 'paged', 'quote-modal', 'created_at', 'desc'],
    queryFn: (offset) =>
      listJobs({
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: 'created_at',
        sort_dir: 'desc',
      }).then((r) => r.data),
  })
  const jobs = useMemo(() => flattenInfinitePages(jobsQuery.data), [jobsQuery.data])
  const [jobId, setJobId] = useState('')
  const [gstEnabled, setGstEnabled] = useState(true)
  const [gstInclusive, setGstInclusive] = useState(true)
  const [items, setItems] = useState<QuoteLineItemInput[]>([
    { item_type: 'labor', description: '', quantity: 1, unit_price_cents: 0 },
    { item_type: 'part', description: '', quantity: 1, unit_price_cents: 0 },
    { item_type: 'part', description: '', quantity: 1, unit_price_cents: 0 },
    { item_type: 'fee', description: '', quantity: 1, unit_price_cents: 0 },
  ])
  const [error, setError] = useState('')

  const updateItem = (i: number, key: keyof QuoteLineItemInput, value: string | number) =>
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, [key]: value } : it))
  const removeItem = (i: number) => setItems(prev => prev.filter((_, idx) => idx !== i))
  const addItem = () => setItems(prev => [...prev, { item_type: 'labor', description: '', quantity: 1, unit_price_cents: 0 }])

  const activeJobs = jobs.filter(j => !['collected', 'no_go'].includes(j.status))
  const selectedJob = activeJobs.find(j => j.id === jobId)

  // Default the GST mode from whether this job belongs to a business account —
  // businesses get GST added on top, individual customers get it included in the total.
  useEffect(() => {
    setGstInclusive(!selectedJob?.customer_account_id)
  }, [selectedJob?.customer_account_id])

  // Discount lines are entered as a positive amount and subtracted (the server
  // stores them with a negative unit price).
  const enteredCents = items.reduce(
    (s, it) => s + Math.round(it.quantity * it.unit_price_cents) * (it.item_type === 'discount' ? -1 : 1),
    0,
  )
  const { subtotalCents, taxCents, totalCents: total } = computeGstAmounts(enteredCents, gstEnabled, gstInclusive)

  const mut = useMutation({
    mutationFn: () => createQuote({ repair_job_id: jobId, gst_enabled: gstEnabled, gst_inclusive: gstInclusive, line_items: items }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['quotes'] }); onClose() },
    onError: (err) => setError(getApiErrorMessage(err, 'Failed to create quote.')),
  })

  return (
    <Modal title="Create Quote" onClose={onClose}>
      <div className="space-y-4">
        <Select label="Repair Job *" value={jobId} onChange={e => setJobId(e.target.value)}>
          <option value="">Select a job…</option>
          {activeJobs.map(j => <option key={j.id} value={j.id}>#{j.job_number} — {j.title}</option>)}
        </Select>
        {jobsQuery.hasNextPage && (
          <Button
            type="button"
            variant="secondary"
            className="text-xs"
            onClick={() => void jobsQuery.fetchNextPage()}
            disabled={jobsQuery.isFetchingNextPage}
          >
            {jobsQuery.isFetchingNextPage ? 'Loading jobs…' : 'Load more jobs in list'}
          </Button>
        )}

        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Line Items</label>
          {items.map((item, i) => (
            <AddLineItemRow key={i} item={item} index={i} onChange={updateItem} onRemove={removeItem} />
          ))}
          <button onClick={addItem} className="text-sm flex items-center gap-1 font-medium transition-colors" style={{ color: 'var(--ms-accent)' }} onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent-hover)')} onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-accent)')}><Plus size={14} />Add line</button>
        </div>

        <div className="space-y-2">
          <label className="flex min-h-11 items-center gap-2 text-sm sm:min-h-0" style={{ color: 'var(--ms-text)' }}>
            <input type="checkbox" className="h-5 w-5 sm:h-4 sm:w-4" checked={gstEnabled} onChange={e => setGstEnabled(e.target.checked)} />
            Apply GST (10%)
          </label>
          {gstEnabled && (
            <div className="flex flex-col pl-6 text-sm sm:flex-row sm:gap-4" style={{ color: 'var(--ms-text-mid)' }}>
              <label className="flex min-h-11 items-center gap-2 sm:min-h-0 sm:gap-1.5">
                <input type="radio" className="h-5 w-5 sm:h-4 sm:w-4" name="gst-mode" checked={gstInclusive} onChange={() => setGstInclusive(true)} />
                Include in total (non-business)
              </label>
              <label className="flex min-h-11 items-center gap-2 sm:min-h-0 sm:gap-1.5">
                <input type="radio" className="h-5 w-5 sm:h-4 sm:w-4" name="gst-mode" checked={!gstInclusive} onChange={() => setGstInclusive(false)} />
                Add on top (business)
              </label>
            </div>
          )}
        </div>

        {error && <p role="alert" className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}

        {/* Totals and the submit action stay on screen while a long line-item
            list is scrolled on a phone. */}
        <ModalStickyFooter>
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            {([
              ['Subtotal', formatCents(subtotalCents), false],
              ['GST', formatCents(taxCents), false],
              ['Total', formatCents(total), true],
            ] as const).map(([label, value, strong]) => (
              <div key={label} className="flex flex-col gap-1">
                <span className="text-[10px] font-medium uppercase tracking-widest sm:text-xs" style={{ color: 'var(--ms-text-muted)' }}>{label}</span>
                <span
                  className={`rounded-lg px-2 py-2 text-sm tabular-nums sm:px-3 ${strong ? 'font-semibold' : ''}`}
                  style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
                >
                  {value}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="secondary" className="sm:w-auto" onClick={onClose}>Cancel</Button>
            <Button
              className="sm:w-auto"
              onClick={() => mut.mutate()}
              disabled={!jobId || items.some(i => !i.description) || mut.isPending}
            >
              {mut.isPending ? 'Creating…' : 'Create Quote'}
            </Button>
          </div>
        </ModalStickyFooter>
      </div>
    </Modal>
  )
}

const QUOTE_STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'sent', label: 'Sent' },
  { value: 'approved', label: 'Approved' },
  { value: 'declined', label: 'Declined' },
  { value: 'expired', label: 'Expired' },
]

export default function QuotesPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialStatus = searchParams.get('status') ?? ''
  const initialOlderThanDays = Number.parseInt(searchParams.get('older_than_days') ?? '', 10)
  const [showCreate, setShowCreate] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState(initialStatus)
  const [olderThanDays, setOlderThanDays] = useState<number>(Number.isFinite(initialOlderThanDays) ? initialOlderThanDays : 0)
  const [invoiceCreated, setInvoiceCreated] = useState<string | null>(null)
  const [invoiceError, setInvoiceError] = useState('')
  const [sortBy, setSortBy] = useState<'created_at' | 'sent_at' | 'status' | 'total_cents'>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  useEffect(() => {
    const next = new URLSearchParams()
    if (statusFilter) next.set('status', statusFilter)
    if (olderThanDays > 0) next.set('older_than_days', String(olderThanDays))
    setSearchParams(next, { replace: true })
  }, [olderThanDays, setSearchParams, statusFilter])

  const quotesQuery = useOffsetPaginatedQuery({
    queryKey: ['quotes', 'paged', 'page', statusFilter || null, sortBy, sortDir],
    queryFn: (offset) =>
      listQuotes(undefined, {
        limit: DEFAULT_PAGE_SIZE,
        offset,
        sort_by: sortBy,
        sort_dir: sortDir,
        ...(statusFilter ? { status: statusFilter } : {}),
      }).then((r) => r.data),
  })
  const quotes = useMemo(() => flattenInfinitePages(quotesQuery.data), [quotesQuery.data])
  const filteredQuotes = useMemo(() => {
    if (olderThanDays <= 0) return quotes
    const cutoff = Date.now() - olderThanDays * 86_400_000
    return quotes.filter((q) => {
      if (!q.sent_at) return false
      return new Date(q.sent_at).getTime() <= cutoff
    })
  }, [olderThanDays, quotes])
  const isLoading = quotesQuery.isLoading

  const SORT_LABELS: Record<typeof sortBy, string> = {
    created_at: 'Created',
    sent_at: 'Sent',
    status: 'Status',
    total_cents: 'Total',
  }
  const statusLabel = QUOTE_STATUS_FILTERS.find(o => o.value === statusFilter)?.label ?? statusFilter
  const activeFilters: ActiveFilter[] = [
    ...(statusFilter ? [{ key: 'status', label: `Status: ${statusLabel}`, onClear: () => setStatusFilter('') }] : []),
    ...(olderThanDays > 0
      ? [{ key: 'age', label: `Sent ${olderThanDays}+ days ago`, onClear: () => setOlderThanDays(0) }]
      : []),
    ...(sortBy !== 'created_at' || sortDir !== 'desc'
      ? [{
          key: 'sort',
          label: `Sort: ${SORT_LABELS[sortBy]} ${sortDir === 'desc' ? '↓' : '↑'}`,
          onClear: () => { setSortBy('created_at'); setSortDir('desc') },
        }]
      : []),
  ]

  const sendMut = useMutation({
    mutationFn: (id: string) => sendQuote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes'] }),
  })

  const resendMut = useMutation({
    mutationFn: (id: string) => resendQuote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes'] }),
  })

  const invoiceMut = useMutation({
    mutationFn: (quoteId: string) => createInvoiceFromQuote(quoteId).then(r => r.data),
    onSuccess: (data) => {
      setInvoiceCreated(data.invoice.invoice_number)
    },
    onError: (err) => setInvoiceError(getApiErrorMessage(err, 'Could not create invoice.')),
  })

  function copyApprovalLink(token: string, id: string) {
    const url = `${window.location.origin}/approve/${token}`
    navigator.clipboard.writeText(url)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div>
      <PageHeader title="Quotes" action={<Button onClick={() => setShowCreate(true)}><Plus size={16} />New Quote</Button>} />
      {showCreate && <CreateQuoteModal onClose={() => setShowCreate(false)} />}

      <MobileFilterBar
        primary={
          <select
            className="h-11 w-full rounded-lg border px-3 text-base outline-none transition sm:h-9 sm:w-auto sm:text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by quote status"
          >
            {QUOTE_STATUS_FILTERS.map((o) => (
              <option key={o.value || 'all'} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        }
        secondary={
          <>
            <select
              className="h-11 w-full rounded-lg border px-3 text-base outline-none transition sm:h-9 sm:w-auto sm:text-sm"
              style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              aria-label="Sort quotes"
            >
              <option value="created_at">Sort: Created</option>
              <option value="sent_at">Sort: Sent</option>
              <option value="status">Sort: Status</option>
              <option value="total_cents">Sort: Total</option>
            </select>
            <select
              className="h-11 w-full rounded-lg border px-3 text-base outline-none transition sm:h-9 sm:w-auto sm:text-sm"
              style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value as SortDir)}
              aria-label="Sort direction"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
            <select
              className="h-11 w-full rounded-lg border px-3 text-base outline-none transition sm:h-9 sm:w-auto sm:text-sm"
              style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
              value={String(olderThanDays)}
              onChange={(e) => setOlderThanDays(Number.parseInt(e.target.value, 10) || 0)}
              aria-label="Filter by quote age"
            >
              <option value="0">Any sent age</option>
              <option value="7">Sent 7+ days ago</option>
              <option value="14">Sent 14+ days ago</option>
              <option value="21">Sent 21+ days ago</option>
            </select>
          </>
        }
        activeFilters={activeFilters}
        onClearAll={
          activeFilters.length > 0
            ? () => { setStatusFilter(''); setOlderThanDays(0); setSortBy('created_at'); setSortDir('desc') }
            : undefined
        }
        resultSummary={
          olderThanDays > 0 ? `${filteredQuotes.length} of ${quotes.length} loaded quotes` : undefined
        }
      />

      {quotesQuery.error && (
        <p className="text-sm mb-3" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(quotesQuery.error)}</p>
      )}
      {quotesQuery.hasNextPage && (
        <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
          More quotes exist — use Load more to fetch the next batch.
        </p>
      )}

      {invoiceCreated && (
        <div className="mb-3 rounded-lg px-4 py-3 text-sm flex items-center justify-between" style={{ backgroundColor: '#E8F6EE', color: '#1F6D4C', border: '1px solid #B8DEC8' }}>
          <span>Invoice <strong>{invoiceCreated}</strong> created successfully.</span>
          <button onClick={() => setInvoiceCreated(null)} style={{ color: '#1F6D4C' }}>✕</button>
        </div>
      )}
      {invoiceError && (
        <div className="mb-3 rounded-lg px-4 py-3 text-sm flex items-center justify-between" style={{ backgroundColor: '#FDF0EE', color: 'var(--ms-error)', border: '1px solid #E8B4AA' }}>
          <span>{invoiceError}</span>
          <button onClick={() => setInvoiceError('')} style={{ color: 'var(--ms-error)' }}>✕</button>
        </div>
      )}

      {isLoading ? <Spinner /> : (
        <>
          {filteredQuotes.length === 0 ? (
            <Card><EmptyState message="No quotes yet." /></Card>
          ) : (
            <>
              {/* Mobile card list */}
              <div className="md:hidden space-y-3">
                {filteredQuotes.map(q => (
                  <Card key={q.id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge status={q.status} />
                          {q.sent_at && (
                            <span className="flex items-center gap-1 text-xs" style={{ color: '#1F6D4C' }}>
                              <MessageSquare size={11} aria-hidden="true" /> Sent {formatDate(q.sent_at)}
                            </span>
                          )}
                        </div>
                        <p className="mt-1.5 text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                          {q.customer_name || (q.job_number ? `Job #${q.job_number}` : 'Watch quote')}
                        </p>
                        <p className="mt-0.5 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                          {q.job_number ? `#${q.job_number} · ` : ''}Created {formatDate(q.created_at)}
                          {q.status === 'sent' ? ' · awaiting response' : ''}
                        </p>
                      </div>
                      <p className="shrink-0 text-lg font-semibold tabular-nums" style={{ color: 'var(--ms-text)' }}>
                        {formatCents(q.total_cents)}
                      </p>
                    </div>
                    {/* The status-appropriate next step gets the full-width
                        row; everything else goes in the overflow menu. */}
                    <div className="mt-3 flex items-center gap-2">
                      {q.status === 'draft' && (
                        <Button className="flex-1" onClick={() => sendMut.mutate(q.id)} disabled={sendMut.isPending}>
                          <MessageSquare size={14} />{sendMut.isPending ? 'Sending…' : 'Send SMS'}
                        </Button>
                      )}
                      {q.status === 'sent' && (
                        <Button variant="secondary" className="flex-1" onClick={() => resendMut.mutate(q.id)} disabled={resendMut.isPending}>
                          <MessageSquare size={14} />{resendMut.isPending ? 'Resending…' : 'Resend SMS'}
                        </Button>
                      )}
                      {q.status === 'approved' && (
                        <Button className="flex-1" onClick={() => invoiceMut.mutate(q.id)} disabled={invoiceMut.isPending}>
                          <FileText size={14} />{invoiceMut.isPending ? 'Creating…' : 'Create invoice'}
                        </Button>
                      )}
                      {!['draft', 'sent', 'approved'].includes(q.status) && (
                        <Button variant="secondary" className="flex-1" onClick={() => navigate(`/jobs/${q.repair_job_id}`)}>
                          View job
                        </Button>
                      )}
                      <MobileActionMenu
                        hiddenFrom="md"
                        label={`More actions for this quote`}
                        actions={[
                          { label: 'View quote / job', onClick: () => navigate(`/jobs/${q.repair_job_id}`) },
                          ...(q.status === 'sent' || q.status === 'draft'
                            ? [{
                                label: copiedId === q.id ? 'Approval link copied' : 'Copy approval link',
                                icon: copiedId === q.id ? <CheckCheck size={15} /> : <Copy size={15} />,
                                onClick: () => copyApprovalLink(q.approval_token, q.id),
                              }]
                            : []),
                        ]}
                      />
                    </div>
                  </Card>
                ))}
              </div>

              {/* Desktop table */}
              <Card className="hidden md:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-widest" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium">Total</th>
                      <th className="px-5 py-3 font-medium">Sent</th>
                      <th className="px-5 py-3 font-medium">Created</th>
                      <th className="px-5 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredQuotes.map(q => (
                      <tr key={q.id} style={{ borderBottom: '1px solid var(--ms-border)', cursor: 'pointer' }} onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--ms-hover)')} onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}>
                        <td className="px-5 py-3"><Badge status={q.status} /></td>
                        <td className="px-5 py-3 font-semibold">{formatCents(q.total_cents)}</td>
                        <td className="px-5 py-3">
                          {q.sent_at ? (
                            <span className="flex items-center gap-1 text-xs text-green-600">
                              <MessageSquare size={12} /> {formatDate(q.sent_at)}
                            </span>
                          ) : (
                            <span className="text-xs" style={{ color: 'var(--ms-border-strong)' }}>—</span>
                          )}
                        </td>
                        <td className="px-5 py-3" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(q.created_at)}</td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-2">
                            <Link to={`/jobs/${q.repair_job_id}`} className="text-xs font-mono transition-colors" style={{ color: 'var(--ms-accent)' }} onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent-hover)')} onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-accent)')}>View Job</Link>
                            {q.status === 'draft' && (
                              <Button variant="secondary" onClick={() => sendMut.mutate(q.id)} disabled={sendMut.isPending} className="text-xs py-1 px-2">
                                <MessageSquare size={12} /> Send SMS
                              </Button>
                            )}
                            {q.status === 'sent' && (
                              <>
                                <span className="text-xs italic" style={{ color: 'var(--ms-text-muted)' }}>Awaiting response</span>
                                <Button variant="secondary" className="text-xs py-1 px-2" onClick={() => resendMut.mutate(q.id)} disabled={resendMut.isPending}>
                                  <MessageSquare size={12} /> Resend
                                </Button>
                              </>
                            )}
                            {q.status === 'approved' && (
                              <Button
                                variant="secondary"
                                className="text-xs py-1 px-2"
                                style={{ backgroundColor: '#E8F6EE', borderColor: '#B8DEC8', color: '#1F6D4C' }}
                                onClick={() => invoiceMut.mutate(q.id)}
                                disabled={invoiceMut.isPending}
                              >
                                <FileText size={12} /> {invoiceMut.isPending ? 'Creating…' : 'Create Invoice'}
                              </Button>
                            )}
                            {(q.status === 'sent' || q.status === 'draft') && (
                              <button
                                title="Copy approval link"
                                onClick={() => copyApprovalLink(q.approval_token, q.id)}
                                className="p-1 transition-colors"
                                style={{ color: 'var(--ms-text-muted)' }}
                                onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
                                onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-text-muted)')}
                              >
                                {copiedId === q.id ? <CheckCheck size={14} className="text-green-500" /> : <Copy size={14} />}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </>
          )}
        </>
      )}

      {quotesQuery.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            onClick={() => void quotesQuery.fetchNextPage()}
            disabled={quotesQuery.isFetchingNextPage}
          >
            {quotesQuery.isFetchingNextPage ? 'Loading…' : 'Load more quotes'}
          </Button>
        </div>
      )}
    </div>
  )
}
