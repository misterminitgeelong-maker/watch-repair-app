import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, Printer } from 'lucide-react'
import { getInvoice } from '@/lib/api'
import { Spinner } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'

export default function PrintInvoicePage() {
  const { id } = useParams<{ id: string }>()
  const { data: invoice, isLoading } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => getInvoice(id!).then(r => r.data),
    enabled: !!id,
  })

  if (isLoading) return (
    <div className="flex items-center justify-center min-h-screen">
      <Spinner />
    </div>
  )
  if (!invoice) return <p className="p-8" style={{ color: 'var(--cafe-text-muted)' }}>Invoice not found.</p>

  return (
    <>
      {/* Screen controls — hidden when printing */}
      <div className="print:hidden fixed top-0 left-0 right-0 px-6 py-3 flex items-center justify-between z-10 shadow-sm" style={{ backgroundColor: 'var(--cafe-surface)', borderBottom: '1px solid var(--cafe-border)' }}>
        <Link
          to={`/invoices/${id}`}
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--cafe-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
        >
          <ChevronLeft size={15} /> Back
        </Link>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{ backgroundColor: 'var(--cafe-amber)', color: '#FEFCF8' }}
          onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--cafe-gold-dark)')}
          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'var(--cafe-amber)')}
        >
          <Printer size={15} /> Print / Save PDF
        </button>
      </div>

      {/* Printable invoice */}
      <div className="print:pt-0 pt-16 min-h-screen bg-[#F8F4EE] print:bg-white">
        <div
          id="invoice-print"
          className="max-w-2xl mx-auto bg-white print:shadow-none shadow-lg my-8 print:my-0 rounded-xl print:rounded-none p-10"
        >
          {/* Shop header */}
          <div className="flex items-start justify-between mb-10">
            <div>
              <h1 className="text-2xl font-bold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>WatchRepair Atelier</h1>
              <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-muted)' }}>Professional Watch Services</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-extrabold" style={{ color: 'var(--cafe-gold-dark)' }}>INVOICE</p>
              <p className="font-mono text-sm mt-1" style={{ color: 'var(--cafe-text-mid)' }}>#{invoice.invoice_number}</p>
            </div>
          </div>

          {/* Invoice meta */}
          <div className="grid grid-cols-2 gap-8 mb-10 pb-8" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--cafe-text-muted)' }}>Bill To</p>
              <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>Customer</p>
            </div>
            <div className="text-right">
              <div className="space-y-1 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                <div><span style={{ color: 'var(--cafe-text-muted)' }}>Date: </span>{formatDate(invoice.created_at)}</div>
                <div>
                  <span style={{ color: 'var(--cafe-text-muted)' }}>Status: </span>
                  <span className={`font-medium capitalize ${invoice.status === 'paid' ? 'text-green-600' : invoice.status === 'voided' ? 'text-red-500' : 'text-orange-600'}`}>
                    {invoice.status}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Line items table */}
          <table className="w-full text-sm mb-8">
            <thead>
              <tr style={{ borderBottom: '2px solid var(--cafe-espresso)' }}>
                <th className="text-left pb-2 font-semibold" style={{ color: 'var(--cafe-text)' }}>Description</th>
                <th className="text-right pb-2 font-semibold w-20" style={{ color: 'var(--cafe-text)' }}>Qty</th>
                <th className="text-right pb-2 font-semibold w-24" style={{ color: 'var(--cafe-text)' }}>Unit Price</th>
                <th className="text-right pb-2 font-semibold w-24" style={{ color: 'var(--cafe-text)' }}>Amount</th>
              </tr>
            </thead>
            <tbody>
              {/* Placeholder row — backend invoices don't expose line items directly yet */}
              <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                <td className="py-3" style={{ color: 'var(--cafe-text-mid)' }}>Watch Repair Services</td>
                <td className="py-3 text-right" style={{ color: 'var(--cafe-text-muted)' }}>1</td>
                <td className="py-3 text-right" style={{ color: 'var(--cafe-text-muted)' }}>{formatCents(invoice.subtotal_cents)}</td>
                <td className="py-3 text-right font-medium" style={{ color: 'var(--cafe-text)' }}>{formatCents(invoice.subtotal_cents)}</td>
              </tr>
            </tbody>
          </table>

          {/* Totals */}
          <div className="flex justify-end mb-10">
            <div className="w-56 space-y-2 text-sm">
              <div className="flex justify-between text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                <span>Subtotal</span><span>{formatCents(invoice.subtotal_cents)}</span>
              </div>
              <div className="flex justify-between text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                <span>Tax</span><span>{formatCents(invoice.tax_cents)}</span>
              </div>
              <div className="flex justify-between font-bold text-base pt-2 mt-1" style={{ borderTop: '2px solid var(--cafe-espresso)', color: 'var(--cafe-text)' }}>
                <span>Total Due</span><span>{formatCents(invoice.total_cents)}</span>
              </div>
              {invoice.status === 'paid' && (
                <div className="text-center font-bold text-green-600 text-lg pt-2 mt-2" style={{ borderTop: '1px solid var(--cafe-border)' }}>
                  ✓ PAID
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="pt-6 text-center text-xs" style={{ borderTop: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}>
            <p>Thank you for choosing our watch repair service.</p>
            <p className="mt-1">Please retain this invoice for your records.</p>
          </div>
        </div>
      </div>

      {/* Print styles */}
      <style>{`
        @media print {
          @page { margin: 0.5in; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>
    </>
  )
}
