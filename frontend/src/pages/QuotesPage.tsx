import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Trash2, MessageSquare, Copy, CheckCheck, FileText } from 'lucide-react'
import {
  DEFAULT_PAGE_SIZE,
  listQuotes,
  createQuote,
  sendQuote,
  createInvoiceFromQuote,
  listJobs,
  getApiErrorMessage,
  type QuoteLineItemInput,
  type SortDir,
} from '@/lib/api'
import { Card, PageHeader, Button, Input, Modal, Spinner, EmptyState, Badge, Select } from '@/components/ui'
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
    <select className="w-full rounded px-2 py-1.5 text-sm" style={inputStyle} value={item.item_type} onChange={e => onChange(index, 'item_type', e.target.value)}>
      <option value="labor">Labor</option>
      <option value="part">Part</option>
      <option value="fee">Fee</option>
    </select>
  )
  const descInput = (
    <input className="w-full rounded px-2 py-1.5 text-sm" style={inputStyle} value={item.description} onChange={e => onChange(index, 'description', e.target.value)} placeholder="Movement service…" />
  )
  const qtyInput = (
    <input type="number" min="0.01" step="0.01" className="w-full rounded px-2 py-1.5 text-sm" style={inputStyle} value={item.quantity} onChange={e => { const n = Number.parseFloat(e.target.value); onChange(index, 'quantity', Number.isFinite(n) ? n : 0) }} />
  )
  const priceInput = (
    <input type="number" min="0" step="1" className="w-full rounded px-2 py-1.5 text-sm" style={inputStyle} value={item.unit_price_cents} placeholder="5000" onChange={e => { const n = Number.parseInt(e.target.value, 10); onChange(index, 'unit_price_cents', Number.isFinite(n) ? n : 0) }} />
  )
  const deleteBtn = (
    <button onClick={() => onRemove(index)} className="p-1.5 transition-colors" style={{ color: '#C96A5A' }} onMouseEnter={e => (e.currentTarget.style.color = '#9B3D2A')} onMouseLeave={e => (e.currentTarget.style.color = '#C96A5A')}>
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
  const [taxCents, setTaxCents] = useState(0)
  const [items, setItems] = useState<QuoteLineItemInput[]>([{ item_type: 'labor', description: '', quantity: 1, unit_price_cents: 0 }])
  const [error, setError] = useState('')

  const updateItem = (i: number, key: keyof QuoteLineItemInput, value: string | number) =>
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, [key]: value } : it))
  const removeItem = (i: number) => setItems(prev => prev.filter((_, idx) => idx !== i))
  const addItem = () => setItems(prev => [...prev, { item_type: 'labor', description: '', quantity: 1, unit_price_cents: 0 }])

  const subtotal = items.reduce((s, it) => s + it.quantity * it.unit_price_cents, 0)
  const total = subtotal + taxCents

  const mut = useMutation({
    mutationFn: () => createQuote({ repair_job_id: jobId, tax_cents: taxCents, line_items: items }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['quotes'] }); onClose() },
    onError: () => setError('Failed to create quote.'),
  })

  const activeJobs = jobs.filter(j => !['collected', 'no_go'].includes(j.status))

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

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Tax (cents)"
            type="number"
            min="0"
            value={taxCents}
            onChange={e => {
              const next = Number.parseInt(e.target.value, 10)
              setTaxCents(Number.isFinite(next) ? next : 0)
            }}
          />
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>Total</label>
            <div className="rounded-lg px-3 py-2 text-sm font-semibold" style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}>{formatCents(total)}</div>
          </div>
        </div>

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!jobId || items.some(i => !i.description) || mut.isPending}>
            {mut.isPending ? 'Creating…' : 'Create Quote'}
          </Button>
        </div>
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

  const sendMut = useMutation({
    mutationFn: (id: string) => sendQuote(id),
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

      <div className="mb-4 flex flex-wrap gap-3 items-center">
        <select
          className="rounded-lg px-3 py-2 text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            color: 'var(--ms-text)',
          }}
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
        <select
          className="rounded-lg px-3 py-2 text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            color: 'var(--ms-text)',
          }}
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
          className="rounded-lg px-3 py-2 text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            color: 'var(--ms-text)',
          }}
          value={sortDir}
          onChange={(e) => setSortDir(e.target.value as SortDir)}
          aria-label="Sort direction"
        >
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
        <select
          className="rounded-lg px-3 py-2 text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            color: 'var(--ms-text)',
          }}
          value={String(olderThanDays)}
          onChange={(e) => setOlderThanDays(Number.parseInt(e.target.value, 10) || 0)}
          aria-label="Filter by quote age"
        >
          <option value="0">Any sent age</option>
          <option value="7">Sent 7+ days ago</option>
          <option value="14">Sent 14+ days ago</option>
          <option value="21">Sent 21+ days ago</option>
        </select>
      </div>

      {quotesQuery.error && (
        <p className="text-sm mb-3" style={{ color: '#C96A5A' }}>{getApiErrorMessage(quotesQuery.error)}</p>
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
        <div className="mb-3 rounded-lg px-4 py-3 text-sm flex items-center justify-between" style={{ backgroundColor: '#FDF0EE', color: '#C96A5A', border: '1px solid #E8B4AA' }}>
          <span>{invoiceError}</span>
          <button onClick={() => setInvoiceError('')} style={{ color: '#C96A5A' }}>✕</button>
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
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge status={q.status} />
                          {q.sent_at && (
                            <span className="flex items-center gap-1 text-xs text-green-600">
                              <MessageSquare size={11} /> Sent {formatDate(q.sent_at)}
                            </span>
                          )}
                        </div>
                        <p className="mt-1.5 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                          Created {formatDate(q.created_at)}
                        </p>
                        <div className="mt-2 flex items-center gap-3 flex-wrap">
                          <Link to={`/jobs/${q.repair_job_id}`} className="text-xs font-mono underline" style={{ color: 'var(--ms-accent)' }}>View Job</Link>
                          {q.status === 'draft' && (
                            <button
                              className="text-xs font-semibold flex items-center gap-1 rounded-lg px-2.5 py-1"
                              style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
                              onClick={() => sendMut.mutate(q.id)}
                              disabled={sendMut.isPending}
                            >
                              <MessageSquare size={11} /> Send SMS
                            </button>
                          )}
                          {q.status === 'sent' && (
                            <span className="text-xs italic" style={{ color: 'var(--ms-text-muted)' }}>Awaiting response</span>
                          )}
                          {q.status === 'approved' && (
                            <button
                              className="text-xs font-semibold flex items-center gap-1 rounded-lg px-2.5 py-1"
                              style={{ backgroundColor: '#E8F6EE', border: '1px solid #B8DEC8', color: '#1F6D4C' }}
                              onClick={() => invoiceMut.mutate(q.id)}
                              disabled={invoiceMut.isPending}
                            >
                              <FileText size={11} /> {invoiceMut.isPending ? 'Creating…' : 'Create Invoice'}
                            </button>
                          )}
                          {(q.status === 'sent' || q.status === 'draft') && (
                            <button
                              title="Copy approval link"
                              onClick={() => copyApprovalLink(q.approval_token, q.id)}
                              className="p-1 transition-colors"
                              style={{ color: 'var(--ms-text-muted)' }}
                            >
                              {copiedId === q.id ? <CheckCheck size={14} className="text-green-500" /> : <Copy size={14} />}
                            </button>
                          )}
                        </div>
                      </div>
                      <p className="text-lg font-semibold shrink-0" style={{ color: 'var(--ms-text)' }}>
                        {formatCents(q.total_cents)}
                      </p>
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
                      <tr key={q.id} style={{ borderBottom: '1px solid var(--ms-border)' }} onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')} onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}>
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
                              <span className="text-xs italic" style={{ color: 'var(--ms-text-muted)' }}>Awaiting response</span>
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
