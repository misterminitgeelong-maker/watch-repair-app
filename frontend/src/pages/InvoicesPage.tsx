import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronLeft, CheckCircle, Printer } from 'lucide-react'
import { listInvoices, getInvoice, getInvoiceLineItems, recordPayment, type Invoice } from '@/lib/api'
import { Card, PageHeader, Badge, Button, Modal, Input, Spinner, EmptyState } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'

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
          onChange={e => setAmount(Math.round(parseFloat(e.target.value || '0') * 100))}
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
  const [payInvoice, setPayInvoice] = useState<Invoice | null>(null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialStatusFilter = searchParams.get('status') ?? ''
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter)
  const { data: invoices, isLoading } = useQuery({ queryKey: ['invoices'], queryFn: () => listInvoices({ limit: 500 }).then(r => r.data) })
  const filteredInvoices = useMemo(
    () => (invoices ?? []).filter((inv) => (statusFilter ? inv.status === statusFilter : true)),
    [invoices, statusFilter],
  )

  useEffect(() => {
    const next = new URLSearchParams()
    if (statusFilter) next.set('status', statusFilter)
    setSearchParams(next, { replace: true })
  }, [setSearchParams, statusFilter])

  return (
    <div>
      <PageHeader title="Invoices" />
      {payInvoice && <PaymentModal invoice={payInvoice} onClose={() => setPayInvoice(null)} />}

      {isLoading ? <Spinner /> : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setStatusFilter('')}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold"
              style={{
                backgroundColor: statusFilter === '' ? '#F3EADF' : 'var(--ms-surface)',
                color: 'var(--ms-text)',
                border: '1px solid var(--ms-border)',
              }}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('unpaid')}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold"
              style={{
                backgroundColor: statusFilter === 'unpaid' ? '#F3EADF' : 'var(--ms-surface)',
                color: 'var(--ms-text)',
                border: '1px solid var(--ms-border)',
              }}
            >
              Unpaid
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter('paid')}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold"
              style={{
                backgroundColor: statusFilter === 'paid' ? '#F3EADF' : 'var(--ms-surface)',
                color: 'var(--ms-text)',
                border: '1px solid var(--ms-border)',
              }}
            >
              Paid
            </button>
          </div>
          {filteredInvoices.length === 0 ? (
            <Card><EmptyState message="No invoices yet. They are created automatically when a quote is approved." /></Card>
          ) : (
            <>
              {/* Mobile card list */}
              <div className="md:hidden space-y-3">
                {filteredInvoices.map((inv: Invoice) => (
                  <Card key={inv.id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Link to={`/invoices/${inv.id}`} className="font-mono font-semibold text-base" style={{ color: 'var(--ms-accent)' }}>
                            #{inv.invoice_number}
                          </Link>
                          <Badge status={inv.status} />
                        </div>
                        <div className="mt-1 flex items-center gap-3 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
                          <span>{formatDate(inv.created_at)}</span>
                          <Link to={`/jobs/${inv.repair_job_id}`} className="font-mono text-xs underline" style={{ color: 'var(--ms-accent)' }}>View Job</Link>
                        </div>
                        <div className="mt-2 text-xs space-y-0.5" style={{ color: 'var(--ms-text-mid)' }}>
                          <div className="flex gap-4">
                            <span>Subtotal: {formatCents(inv.subtotal_cents)}</span>
                            <span>Tax: {formatCents(inv.tax_cents)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-lg font-semibold" style={{ color: 'var(--ms-text)' }}>
                          {formatCents(inv.total_cents)}
                        </p>
                        {inv.status === 'unpaid' && (
                          <button
                            className="mt-2 text-xs font-semibold rounded-lg px-3 py-1.5"
                            style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
                            onClick={() => setPayInvoice(inv)}
                          >
                            Record Payment
                          </button>
                        )}
                      </div>
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
                    {filteredInvoices.map((inv: Invoice) => (
                      <tr key={inv.id} style={{ borderBottom: '1px solid var(--ms-border)' }} onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')} onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}>
                        <td className="px-5 py-3">
                          <span className="text-xs font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: '#E8E6F0', color: '#4A4566' }}>Watch</span>
                        </td>
                        <td
                          className="px-5 py-3 cursor-pointer"
                          onClick={() => navigate(`/invoices/${inv.id}`)}
                        >
                          <Link
                            to={`/invoices/${inv.id}`}
                            className="inline-block font-mono transition-colors"
                            style={{ color: 'var(--ms-accent)' }}
                            onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent-hover)')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
                          >
                            #{inv.invoice_number}
                          </Link>
                        </td>
                        <td
                          className="px-5 py-3 cursor-pointer"
                          onClick={() => navigate(`/jobs/${inv.repair_job_id}`)}
                        >
                          <Link
                            to={`/jobs/${inv.repair_job_id}`}
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
                          {inv.status === 'unpaid' && (
                            <Button variant="secondary" className="text-xs py-1 px-2" onClick={() => setPayInvoice(inv)}>
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
  const { data: invoice, isLoading } = useQuery({ queryKey: ['invoice', id], queryFn: () => getInvoice(id!).then(r => r.data?.invoice ?? r.data) })
  const { data: lineItems } = useQuery({
    queryKey: ['invoice-line-items', id],
    queryFn: () => getInvoiceLineItems(id!).then(r => r.data),
    enabled: !!id,
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
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => navigate(`/invoices/${id}/print`)}><Printer size={15} />Print / PDF</Button>
            {invoice.status === 'unpaid' && <Button onClick={() => setShowPay(true)}><CheckCircle size={15} />Record Payment</Button>}
          </div>
        }
      />
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
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Date</span>
              <span style={{ color: 'var(--ms-text)' }}>{formatDate(invoice.created_at)}</span>
            </div>
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
