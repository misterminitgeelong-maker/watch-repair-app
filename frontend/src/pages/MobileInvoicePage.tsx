import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Clock, FileText } from 'lucide-react'
import { getApiErrorMessage, getPublicAutoKeyInvoice, type PublicAutoKeyInvoice } from '@/lib/api'
import { Card } from '@/components/ui'

function formatMoney(cents: number, currency: string) {
  const code = (currency || 'AUD').toUpperCase().slice(0, 3)
  return (cents / 100).toLocaleString('en-AU', { style: 'currency', currency: code })
}

export default function MobileInvoicePage() {
  const { token } = useParams<{ token: string }>()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['public-auto-key-invoice', token],
    queryFn: () => getPublicAutoKeyInvoice(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="text-center" style={{ color: 'var(--cafe-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading invoice…</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    const msg =
      axios.isAxiosError(error) && error.response?.status === 404
        ? 'This invoice link is not valid. Contact the shop if you need a copy.'
        : getApiErrorMessage(error, 'Could not load invoice.')
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Invoice unavailable
          </h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>{msg}</p>
        </div>
      </div>
    )
  }

  const inv = data as PublicAutoKeyInvoice

  return (
    <div className="min-h-screen py-6 px-4 sm:py-10 sm:px-5" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <div className="max-w-lg mx-auto space-y-4 sm:space-y-5">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <FileText size={22} style={{ color: 'var(--cafe-gold-dark)' }} />
          </div>
          <h1 className="text-xl sm:text-2xl font-bold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Invoice
          </h1>
          {inv.shop_name && (
            <p className="text-sm mt-1 font-medium" style={{ color: 'var(--cafe-text)' }}>{inv.shop_name}</p>
          )}
          <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
            {inv.invoice_number} · Job #{inv.job_number}
          </p>
        </div>

        <Card className="p-4 sm:p-5 space-y-3">
          <p className="text-sm" style={{ color: 'var(--cafe-text)' }}>{inv.job_title}</p>
          <p className="text-xs uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Status</p>
          <p className="text-sm capitalize" style={{ color: 'var(--cafe-text)' }}>{inv.status.replace(/_/g, ' ')}</p>

          <div className="pt-2" style={{ borderTop: '1px solid var(--cafe-border)' }}>
            <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Line items</p>
            <ul className="text-sm space-y-2" style={{ color: 'var(--cafe-text)' }}>
              {inv.line_items.map((li, i) => (
                <li key={i} className="flex justify-between gap-3">
                  <span>
                    {li.quantity}× {li.description}
                  </span>
                  <span className="tabular-nums shrink-0">{formatMoney(li.total_price_cents, inv.currency)}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 space-y-1 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span className="tabular-nums">{formatMoney(inv.subtotal_cents, inv.currency)}</span>
              </div>
              <div className="flex justify-between">
                <span>Tax</span>
                <span className="tabular-nums">{formatMoney(inv.tax_cents, inv.currency)}</span>
              </div>
              <div className="flex justify-between font-semibold pt-1" style={{ color: 'var(--cafe-text)' }}>
                <span>Total</span>
                <span className="tabular-nums">{formatMoney(inv.total_cents, inv.currency)}</span>
              </div>
            </div>
          </div>
        </Card>

        <p className="text-xs text-center" style={{ color: 'var(--cafe-text-muted)' }}>
          Questions? Reply to the shop or call them with your job number.
        </p>
      </div>
    </div>
  )
}
