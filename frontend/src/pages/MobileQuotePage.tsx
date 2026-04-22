import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { CheckCircle, XCircle, FileText, MapPin, Car } from 'lucide-react'
import {
  decidePublicAutoKeyQuote,
  getApiErrorMessage,
  getPublicAutoKeyQuote,
  type PublicAutoKeyQuote,
} from '@/lib/api'
import { Button, Card } from '@/components/ui'
import { useState } from 'react'

function formatMoney(cents: number, currency: string) {
  const code = (currency || 'AUD').toUpperCase().slice(0, 3)
  return (cents / 100).toLocaleString('en-AU', { style: 'currency', currency: code })
}

export default function MobileQuotePage() {
  const { token } = useParams<{ token: string }>()
  const qc = useQueryClient()
  const [declineConfirm, setDeclineConfirm] = useState(false)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['public-auto-key-quote', token],
    queryFn: () => getPublicAutoKeyQuote(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  const decideMut = useMutation({
    mutationFn: (decision: 'approved' | 'declined') =>
      decidePublicAutoKeyQuote(token!, decision).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['public-auto-key-quote', token] })
      setDeclineConfirm(false)
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <p style={{ color: 'var(--ms-text-muted)' }}>Loading quote…</p>
      </div>
    )
  }

  if (isError || !data) {
    const msg =
      axios.isAxiosError(error) && error.response?.status === 404
        ? 'This quote link is not valid or has expired. Contact the shop if you need a new link.'
        : getApiErrorMessage(error, 'Could not load quote.')
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>Quote unavailable</h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>{msg}</p>
        </div>
      </div>
    )
  }

  const quote = data as PublicAutoKeyQuote
  const isApproved = quote.status === 'approved'
  const isDeclined = quote.status === 'declined'
  const isSettled = isApproved || isDeclined
  const vehicle = [quote.vehicle_make, quote.vehicle_model, quote.vehicle_year].filter(Boolean).join(' ')

  return (
    <div className="min-h-screen py-6 px-4 sm:py-10 sm:px-5" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-4 sm:space-y-5">

        {/* Header */}
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <FileText size={22} style={{ color: 'var(--ms-accent)' }} />
          </div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--ms-text)' }}>{quote.shop_name}</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            Quote for job #{quote.job_number}
            {quote.customer_name ? ` — ${quote.customer_name}` : ''}
          </p>
        </div>

        {/* Status banner */}
        {isApproved && (
          <div className="flex items-center gap-3 rounded-xl px-4 py-3" style={{ backgroundColor: 'rgba(80,180,100,0.12)', border: '1px solid rgba(80,180,100,0.3)' }}>
            <CheckCircle size={20} style={{ color: '#3A9A50', flexShrink: 0 }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: '#2A7A40' }}>Quote accepted</p>
              <p className="text-xs" style={{ color: '#2A7A40' }}>We'll be in touch to confirm your appointment.</p>
            </div>
          </div>
        )}
        {isDeclined && (
          <div className="flex items-center gap-3 rounded-xl px-4 py-3" style={{ backgroundColor: 'rgba(201,106,90,0.1)', border: '1px solid rgba(201,106,90,0.3)' }}>
            <XCircle size={20} style={{ color: '#C96A5A', flexShrink: 0 }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: '#C96A5A' }}>Quote declined</p>
              <p className="text-xs" style={{ color: '#C96A5A' }}>Contact us if you change your mind.</p>
            </div>
          </div>
        )}

        {/* Job details */}
        <Card className="p-4 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Job details</h2>
          <p className="font-semibold" style={{ color: 'var(--ms-text)' }}>{quote.title}</p>
          {vehicle && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>
              <Car size={14} />
              <span>{vehicle}</span>
            </div>
          )}
          {quote.job_address && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>
              <MapPin size={14} />
              <span>{quote.job_address}</span>
            </div>
          )}
        </Card>

        {/* Quote line items */}
        <Card className="p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>Quote breakdown</h2>
          <div className="space-y-2">
            {quote.line_items.map((item, i) => (
              <div key={i} className="flex items-start justify-between gap-4 text-sm">
                <span style={{ color: 'var(--ms-text)' }}>
                  {item.description}
                  {item.quantity !== 1 && (
                    <span className="ml-1" style={{ color: 'var(--ms-text-muted)' }}>× {item.quantity}</span>
                  )}
                </span>
                <span className="font-medium whitespace-nowrap" style={{ color: 'var(--ms-text)' }}>
                  {formatMoney(item.total_price_cents, quote.currency)}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 space-y-1" style={{ borderTop: '1px solid var(--ms-border)' }}>
            {quote.tax_cents > 0 && (
              <>
                <div className="flex justify-between text-sm" style={{ color: 'var(--ms-text-mid)' }}>
                  <span>Subtotal</span>
                  <span>{formatMoney(quote.subtotal_cents, quote.currency)}</span>
                </div>
                <div className="flex justify-between text-sm" style={{ color: 'var(--ms-text-mid)' }}>
                  <span>GST</span>
                  <span>{formatMoney(quote.tax_cents, quote.currency)}</span>
                </div>
              </>
            )}
            <div className="flex justify-between font-bold text-base pt-1" style={{ color: 'var(--ms-text)' }}>
              <span>Total</span>
              <span>{formatMoney(quote.total_cents, quote.currency)}</span>
            </div>
          </div>
        </Card>

        {/* Actions */}
        {!isSettled && (
          <div className="space-y-3">
            {decideMut.isError && (
              <p className="text-sm text-center" style={{ color: '#C96A5A' }}>
                {getApiErrorMessage(decideMut.error, 'Something went wrong. Please try again.')}
              </p>
            )}

            {declineConfirm ? (
              <Card className="p-4 space-y-3">
                <p className="text-sm font-medium text-center" style={{ color: 'var(--ms-text)' }}>
                  Are you sure you want to decline this quote?
                </p>
                <div className="flex gap-3">
                  <Button variant="secondary" className="flex-1" onClick={() => setDeclineConfirm(false)}>
                    Go back
                  </Button>
                  <Button
                    className="flex-1"
                    style={{ backgroundColor: '#C96A5A', color: '#fff' }}
                    onClick={() => decideMut.mutate('declined')}
                    disabled={decideMut.isPending}
                  >
                    {decideMut.isPending ? 'Declining…' : 'Yes, decline'}
                  </Button>
                </div>
              </Card>
            ) : (
              <>
                <Button
                  className="w-full py-3 text-base font-semibold"
                  onClick={() => decideMut.mutate('approved')}
                  disabled={decideMut.isPending}
                >
                  {decideMut.isPending ? 'Accepting…' : 'Accept quote'}
                </Button>
                <button
                  type="button"
                  className="w-full text-sm py-2"
                  style={{ color: 'var(--ms-text-muted)' }}
                  onClick={() => setDeclineConfirm(true)}
                  disabled={decideMut.isPending}
                >
                  Decline quote
                </button>
              </>
            )}
          </div>
        )}

        {/* Contact */}
        {quote.shop_phone && (
          <p className="text-xs text-center" style={{ color: 'var(--ms-text-muted)' }}>
            Questions? Call{' '}
            <a href={`tel:${quote.shop_phone}`} style={{ color: 'var(--ms-accent)' }}>
              {quote.shop_phone}
            </a>
          </p>
        )}
      </div>
    </div>
  )
}
