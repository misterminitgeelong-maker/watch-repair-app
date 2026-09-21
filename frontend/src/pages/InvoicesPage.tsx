import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronLeft, CheckCircle, Printer, Send, ExternalLink } from 'lucide-react'
import { listInvoices, listAllAutoKeyInvoices, getInvoice, getInvoiceLineItems, recordPayment, sendWatchInvoice, retryInvoiceXeroSync, getXeroConnectionStatus, getApiErrorMessage, type Invoice, type AutoKeyInvoice } from '@/lib/api'
import { Card, PageHeader, Badge, Button, Modal, Input, Spinner, EmptyState, MobileActionMenu } from '@/components/ui'
import MobileFilterBar, { type ActiveFilter } from '@/components/mobile/MobileFilterBar'
import { formatCents, formatDate } from '@/lib/utils'
import { dollarsToCents } from '@/lib/money'
import { isDemoModeEnabled } from '@/lib/onboarding'
import { useAuth } from '@/context/AuthContext'

type InvoiceSource = 'watch' | 'auto_key'

type ListedInvoice = {
  id: string
  invoice_number: string
  status: string
  subtotal_cents: number
  tax_cents: number
  total_cents: number
  created_at: string
  customer_name?: string | null
  source: InvoiceSource
  jobHref: string
  detailHref: string
  watchInvoice?: Invoice
}

function toWatchListedInvoice(inv: Invoice): ListedInvoice {
  return {
    id: inv.id,
    invoice_number: inv.invoice_number,
    status: inv.status,
    subtotal_cents: inv.subtotal_cents,
    tax_cents: inv.tax_cents,
    total_cents: inv.total_cents,
    created_at: inv.created_at,
    customer_name: inv.customer_name,
    source: 'watch',
    jobHref: `/jobs/${inv.repair_job_id}`,
    detailHref: `/invoices/${inv.id}`,
    watchInvoice: inv,
  }
}

function toAutoKeyListedInvoice(inv: AutoKeyInvoice): ListedInvoice {
  return {
    id: inv.id,
    invoice_number: inv.invoice_number,
    status: inv.status,
    subtotal_cents: inv.subtotal_cents,
    tax_cents: inv.tax_cents,
    total_cents: inv.total_cents,
    created_at: inv.created_at,
    customer_name: inv.customer_name,
    source: 'auto_key',
    jobHref: `/auto-key/${inv.auto_key_job_id}?tab=financial`,
    detailHref: `/auto-key/${inv.auto_key_job_id}?tab=financial`,
  }
}

function PaymentModal({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  const qc = useQueryClient()
  const [amount, setAmount] = useState(invoice.total_cents)
  const mut = useMutation({
    mutationFn: () => recordPayment(invoice.id, amount),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['invoices'] }); qc.invalidateQueries({ queryKey: ['invoice', invoice.id] }); onClose() },
  })

  return (
    <Modal title="Record Payment" onClose={onClose}>
      <div className="space-y-4">
        <div className="rounded-lg p-4 text-sm space-y-1" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}>
          <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Invoice</span><span className="font-mono">#{invoice.invoice_number}</span></div>
          <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Total Due</span><span className="font-semibold">{formatCents(invoice.total_cents)}</span></div>
        </div>
        <Input
          label="Amount ($)"
          type="number"
          min="0.01"
          step="0.01"
          value={(amount / 100).toFixed(2)}
          onChange={e => setAmount(dollarsToCents(e.target.value))}
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>
            <CheckCircle size={15} />{mut.isPending ? 'Saving…' : 'Record Payment'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export function InvoicesPage() {
  const { hasFeature } = useAuth()
  const [payInvoice, setPayInvoice] = useState<Invoice | null>(null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialStatusFilter = searchParams.get('status') ?? ''
  const initialTypeFilter = (searchParams.get('type') === 'watch' || searchParams.get('type') === 'auto_key')
    ? searchParams.get('type') as InvoiceSource
    : ''
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter)
  const [typeFilter, setTypeFilter] = useState<InvoiceSource | ''>(initialTypeFilter)
  const [searchTerm, setSearchTerm] = useState(searchParams.get('q') ?? '')
  const watchInvoicesQ = useQuery({
    queryKey: ['invoices'],
    queryFn: () => listInvoices({ limit: 500 }).then(r => r.data.items),
  })
  const autoKeyInvoicesQ = useQuery({
    queryKey: ['auto-key-invoices', 'all'],
    queryFn: () => listAllAutoKeyInvoices({ limit: 500 }).then(r => r.data),
    enabled: hasFeature('auto_key'),
  })
  const isLoading = watchInvoicesQ.isLoading || autoKeyInvoicesQ.isLoading
  const invoices = useMemo<ListedInvoice[]>(() => {
    const watch = (watchInvoicesQ.data ?? []).map(toWatchListedInvoice)
    const autoKey = (autoKeyInvoicesQ.data ?? []).map(toAutoKeyListedInvoice)
    return [...watch, ...autoKey].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
  }, [autoKeyInvoicesQ.data, watchInvoicesQ.data])
  const filteredInvoices = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    return invoices.filter((inv) => {
      if (statusFilter && inv.status !== statusFilter) return false
      if (typeFilter && inv.source !== typeFilter) return false
      if (!term) return true
      return inv.invoice_number.toLowerCase().includes(term) || (inv.customer_name ?? '').toLowerCase().includes(term)
    })
  }, [invoices, statusFilter, typeFilter, searchTerm])

  const activeFilters: ActiveFilter[] = [
    ...(statusFilter ? [{ key: 'status', label: `Status: ${statusFilter}`, onClear: () => setStatusFilter('') }] : []),
    ...(typeFilter ? [{ key: 'type', label: typeFilter === 'auto_key' ? 'Type: Mobile' : 'Type: Watch', onClear: () => setTypeFilter('') }] : []),
    ...(searchTerm.trim() ? [{ key: 'q', label: `Search: ${searchTerm.trim()}`, onClear: () => setSearchTerm('') }] : []),
  ]

  useEffect(() => {
    const next = new URLSearchParams()
    if (statusFilter) next.set('status', statusFilter)
    if (typeFilter) next.set('type', typeFilter)
    if (searchTerm.trim()) next.set('q', searchTerm.trim())
    setSearchParams(next, { replace: true })
  }, [setSearchParams, statusFilter, typeFilter, searchTerm])

  return (
    <div>
      <PageHeader title="Invoices" />
      {payInvoice && <PaymentModal invoice={payInvoice} onClose={() => setPayInvoice(null)} />}

      {isLoading ? <Spinner /> : (
        <>
          <MobileFilterBar
            search={{
              value: searchTerm,
              onChange: setSearchTerm,
              label: 'Search invoices by number',
              placeholder: 'Search invoice number…',
            }}
            primary={
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
                  {([
                    { key: '', label: 'All' },
                    { key: 'unpaid', label: 'Unpaid' },
                    { key: 'paid', label: 'Paid' },
                  ] as const).map(option => (
                    <button
                      key={option.key || 'all'}
                      type="button"
                      aria-pressed={statusFilter === option.key}
                      onClick={() => setStatusFilter(option.key)}
                      className="min-h-11 flex-1 rounded-lg px-3 text-sm font-semibold sm:min-h-9 sm:flex-none sm:text-xs"
                      style={{
                        backgroundColor: statusFilter === option.key ? '#F3EADF' : 'var(--ms-surface)',
                        color: 'var(--ms-text)',
                        border: '1px solid var(--ms-border)',
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                {hasFeature('auto_key') && (
                  <div role="group" aria-label="Filter by type" className="flex flex-wrap gap-2">
                    {([
                      { key: '', label: 'All types' },
                      { key: 'watch', label: 'Watch' },
                      { key: 'auto_key', label: 'Mobile' },
                    ] as const).map(option => (
                      <button
                        key={option.key || 'all-types'}
                        type="button"
                        aria-pressed={typeFilter === option.key}
                        onClick={() => setTypeFilter(option.key)}
                        className="min-h-11 flex-1 rounded-lg px-3 text-sm font-semibold sm:min-h-9 sm:flex-none sm:text-xs"
                        style={{
                          backgroundColor: typeFilter === option.key ? '#F3EADF' : 'var(--ms-surface)',
                          color: 'var(--ms-text)',
                          border: '1px solid var(--ms-border)',
                        }}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            }
            activeFilters={activeFilters}
            onClearAll={activeFilters.length > 0 ? () => { setStatusFilter(''); setTypeFilter(''); setSearchTerm('') } : undefined}
            resultSummary={
              invoices && activeFilters.length > 0
                ? `${filteredInvoices.length} of ${invoices.length} invoices`
                : undefined
            }
          />
          {filteredInvoices.length === 0 ? (
            <Card>
              <EmptyState
                message={
                  activeFilters.length > 0
                    ? 'No invoices match these filters. Clear them to see all invoices.'
                    : 'No invoices yet. They are created automatically when a quote is approved.'
                }
              />
            </Card>
          ) : (
            <>
              {/* Mobile card list */}
              <div className="md:hidden space-y-3">
                {filteredInvoices.map((inv) => (
                  <Card key={`${inv.source}-${inv.id}`} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to={inv.detailHref}
                            className="inline-flex min-h-11 items-center font-mono text-base font-semibold sm:min-h-0"
                            style={{ color: 'var(--ms-accent)' }}
                          >
                            #{inv.invoice_number}
                          </Link>
                          <Badge status={inv.status} />
                          <span className="text-[10px] font-semibold uppercase tracking-wide rounded-full px-2 py-0.5" style={{ backgroundColor: inv.source === 'auto_key' ? '#E7F0E4' : '#E8E6F0', color: inv.source === 'auto_key' ? '#2F6A3D' : '#4A4566' }}>
                            {inv.source === 'auto_key' ? 'Mobile' : 'Watch'}
                          </span>
                        </div>
                        <p className="mt-1 text-sm" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(inv.created_at)}</p>
                        {inv.customer_name && (
                          <p className="mt-1 text-sm" style={{ color: 'var(--ms-text)' }}>{inv.customer_name}</p>
                        )}
                        <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                          Subtotal {formatCents(inv.subtotal_cents)} · Tax {formatCents(inv.tax_cents)}
                        </p>
                      </div>
                      <p className="shrink-0 text-right text-lg font-semibold tabular-nums" style={{ color: 'var(--ms-text)' }}>
                        {formatCents(inv.total_cents)}
                      </p>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      {inv.status === 'unpaid' && inv.watchInvoice ? (
                        <Button className="flex-1" onClick={() => setPayInvoice(inv.watchInvoice!)}>
                          <CheckCircle size={15} />Record payment
                        </Button>
                      ) : (
                        <Button variant="secondary" className="flex-1" onClick={() => navigate(inv.detailHref)}>
                          {inv.source === 'auto_key' ? 'Open job invoice' : 'View invoice'}
                        </Button>
                      )}
                      <MobileActionMenu
                        hiddenFrom="md"
                        label={`More actions for invoice ${inv.invoice_number}`}
                        actions={[
                          { label: inv.source === 'auto_key' ? 'Open job invoice' : 'Open invoice', onClick: () => navigate(inv.detailHref) },
                          { label: 'Open job', onClick: () => navigate(inv.jobHref) },
                          ...(inv.source === 'watch' ? [{ label: 'Print / PDF', onClick: () => navigate(`/invoices/${inv.id}/print`) }] : []),
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
                      <th className="px-5 py-3 font-medium">Source</th>
                      <th className="px-5 py-3 font-medium">Invoice #</th>
                      <th className="px-5 py-3 font-medium">Customer</th>
                      <th className="px-5 py-3 font-medium">Job</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium">Subtotal</th>
                      <th className="px-5 py-3 font-medium">Tax</th>
                      <th className="px-5 py-3 font-medium">Total</th>
                      <th className="px-5 py-3 font-medium">Date</th>
                      <th className="px-5 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredInvoices.map((inv) => (
                      <tr key={`${inv.source}-${inv.id}`} style={{ borderBottom: '1px solid var(--ms-border)', cursor: 'pointer' }} onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--ms-hover)')} onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}>
                        <td className="px-5 py-3">
                          <span className="text-xs font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: inv.source === 'auto_key' ? '#E7F0E4' : '#E8E6F0', color: inv.source === 'auto_key' ? '#2F6A3D' : '#4A4566' }}>
                            {inv.source === 'auto_key' ? 'Mobile' : 'Watch'}
                          </span>
                        </td>
                        <td
                          className="px-5 py-3 cursor-pointer"
                          onClick={() => navigate(inv.detailHref)}
                        >
                          <Link
                            to={inv.detailHref}
                            className="inline-block font-mono transition-colors"
                            style={{ color: 'var(--ms-accent)' }}
                            onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent-hover)')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
                          >
                            #{inv.invoice_number}
                          </Link>
                        </td>
                        <td className="px-5 py-3" style={{ color: 'var(--ms-text-mid)' }}>{inv.customer_name ?? '—'}</td>
                        <td
                          className="px-5 py-3 cursor-pointer"
                          onClick={() => navigate(inv.jobHref)}
                        >
                          <Link
                            to={inv.jobHref}
                            className="inline-block text-xs font-mono transition-colors"
                            style={{ color: 'var(--ms-accent)' }}
                            onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent-hover)')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
                          >
                            View Job
                          </Link>
                        </td>
                        <td className="px-5 py-3"><Badge status={inv.status} /></td>
                        <td className="px-5 py-3">{formatCents(inv.subtotal_cents)}</td>
                        <td className="px-5 py-3">{formatCents(inv.tax_cents)}</td>
                        <td className="px-5 py-3 font-semibold">{formatCents(inv.total_cents)}</td>
                        <td className="px-5 py-3" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(inv.created_at)}</td>
                        <td className="px-5 py-3">
                          {inv.status === 'unpaid' && inv.watchInvoice && (
                            <Button variant="secondary" className="text-xs py-1 px-2" onClick={() => setPayInvoice(inv.watchInvoice!)}>
                              Record Payment
                            </Button>
                          )}
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
    </div>
  )
}

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [showPay, setShowPay] = useState(false)
  const [sendFeedback, setSendFeedback] = useState('')
  const { data: invoice, isLoading } = useQuery({ queryKey: ['invoice', id], queryFn: () => getInvoice(id!).then(r => r.data?.invoice ?? r.data) })
  const sendMut = useMutation({
    mutationFn: () => sendWatchInvoice(id!),
    onSuccess: (res) => {
      const data = res.data
      if (data?.email_sent) {
        setSendFeedback('Invoice emailed to customer.')
      } else if (data?.email_skipped_reason === 'email_disabled') {
        setSendFeedback('Email is disabled. Set ENABLE_EMAIL_NOTIFICATIONS=true in production.')
      } else if (data?.email_skipped_reason === 'sendgrid_not_configured') {
        setSendFeedback('Add SENDGRID_API_KEY from Twilio Console → Email.')
      } else {
        setSendFeedback('Email could not be sent. Check SendGrid domain verification.')
      }
    },
    onError: (err) => setSendFeedback(getApiErrorMessage(err, 'Failed to send invoice.')),
  })
  const { data: lineItems } = useQuery({
    queryKey: ['invoice-line-items', id],
    queryFn: () => getInvoiceLineItems(id!).then(r => r.data),
    enabled: !!id,
  })
  const qc = useQueryClient()
  const { data: xero } = useQuery({
    queryKey: ['xero-status'],
    queryFn: () => getXeroConnectionStatus().then(r => r.data),
  })
  const retryXeroMut = useMutation({
    mutationFn: () => retryInvoiceXeroSync(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invoice', id] }),
    onError: (err) => setSendFeedback(getApiErrorMessage(err, 'Xero sync retry failed.')),
  })

  if (isLoading) return <Spinner />
  if (!invoice) return <p style={{ color: 'var(--ms-text-muted)' }}>Invoice not found.</p>

  return (
    <div>
      <div className="mb-4">
        <Link
          to="/invoices"
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--ms-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-text-muted)')}
        >
          <ChevronLeft size={14} /> Back to Invoices
        </Link>
      </div>
      <PageHeader
        title={`Invoice #${invoice.invoice_number}`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => { setSendFeedback(''); sendMut.mutate() }}
              disabled={sendMut.isPending}
            >
              <Send size={15} />{sendMut.isPending ? 'Sending…' : 'Email Customer'}
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/invoices/${id}/print`)}><Printer size={15} />Print / PDF</Button>
            {invoice.xero_online_invoice_url && !isDemoModeEnabled() && (
              <Button variant="secondary" onClick={() => window.open(invoice.xero_online_invoice_url!, '_blank', 'noopener')}>
                <ExternalLink size={15} />Pay online (Xero)
              </Button>
            )}
            {invoice.status === 'unpaid' && <Button onClick={() => setShowPay(true)}><CheckCircle size={15} />Record Payment</Button>}
          </div>
        }
      />
      {sendFeedback && (
        <p className="mb-4 text-sm rounded-lg px-3 py-2" style={{ backgroundColor: '#F0FAF0', color: '#2A6A2A' }}>{sendFeedback}</p>
      )}
      {showPay && <PaymentModal invoice={invoice} onClose={() => setShowPay(false)} />}

      {lineItems && lineItems.length > 0 && (
        <Card className="p-5 mb-4">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Line Items</h2>
          <div className="space-y-2">
            {lineItems.map((item, i) => (
              <div key={i} className="flex items-start justify-between gap-4 text-sm py-2" style={{ borderBottom: i < lineItems.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                <div className="min-w-0">
                  <p className="font-medium" style={{ color: 'var(--ms-text)' }}>{item.description}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                    {item.item_type} · qty {item.quantity} × ${(item.unit_price_cents / 100).toFixed(2)}
                  </p>
                </div>
                <span className="font-semibold shrink-0" style={{ color: 'var(--ms-text)' }}>
                  ${(item.total_price_cents / 100).toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
      <Card className="max-w-2xl p-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span style={{ color: 'var(--ms-text-muted)' }}>Status</span>
              <Badge status={invoice.status} />
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Invoice #</span>
              <span className="font-mono" style={{ color: 'var(--ms-text)' }}>{invoice.invoice_number}</span>
            </div>
            {invoice.customer_name && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Customer</span>
                <span style={{ color: 'var(--ms-text)' }}>{invoice.customer_name}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Date</span>
              <span style={{ color: 'var(--ms-text)' }}>{formatDate(invoice.created_at)}</span>
            </div>
            {xero?.configured && !isDemoModeEnabled() && (
              <div className="flex justify-between items-center gap-2">
                <span style={{ color: 'var(--ms-text-muted)' }}>Xero</span>
                <span className="flex items-center gap-2 text-right" style={{ color: 'var(--ms-text)' }}>
                  <span>
                    {invoice.xero_sync_status === 'synced'
                      ? '✓ Synced'
                      : invoice.xero_sync_status === 'failed'
                        ? 'Failed'
                        : invoice.xero_sync_status === 'pending'
                          ? 'Not connected'
                          : invoice.xero_sync_status === 'skipped'
                            ? 'Not configured'
                            : '—'}
                  </span>
                  {invoice.xero_sync_status !== 'synced' && (
                    <Button
                      variant="secondary"
                      className="text-xs py-0.5 px-2"
                      onClick={() => { setSendFeedback(''); retryXeroMut.mutate() }}
                      disabled={retryXeroMut.isPending}
                    >
                      {retryXeroMut.isPending ? 'Syncing…' : 'Retry'}
                    </Button>
                  )}
                </span>
              </div>
            )}
            {xero?.configured && !isDemoModeEnabled() && invoice.xero_sync_status === 'failed' && invoice.xero_sync_error && (
              <p className="text-xs" style={{ color: '#C9772A' }}>{invoice.xero_sync_error.slice(0, 120)}</p>
            )}
          </div>
          <div className="space-y-2 text-sm border-t pt-4 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-6" style={{ borderColor: 'var(--ms-border)' }}>
            <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Subtotal</span><span style={{ color: 'var(--ms-text)' }}>{formatCents(invoice.subtotal_cents)}</span></div>
            <div className="flex justify-between"><span style={{ color: 'var(--ms-text-muted)' }}>Tax</span><span style={{ color: 'var(--ms-text)' }}>{formatCents(invoice.tax_cents)}</span></div>
            <div className="flex justify-between font-bold text-base pt-2 mt-2" style={{ borderTop: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
              <span>Total</span><span>{formatCents(invoice.total_cents)}</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
