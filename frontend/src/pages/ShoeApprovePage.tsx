import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { CheckCircle, XCircle, Clock, Footprints } from 'lucide-react'
import { getPublicShoeQuote, decideShoeQuote, getApiErrorMessage } from '@/lib/api'

function formatCents(c: number) {
  return (c / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function loadErrorCopy(error: unknown): { title: string; body: string } {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    if (status === 404) return { title: 'Invalid link', body: 'This quote link is not valid. Check the URL or contact the shop.' }
    if (status === 410) return { title: 'This quote link has expired', body: 'Please contact the shop for an updated quote or approval link.' }
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return { title: 'Unable to load quote', body: detail }
  }
  return { title: 'Unable to load quote', body: 'Something went wrong. Please try again or contact the shop.' }
}

export default function ShoeApprovePage() {
  const { token } = useParams<{ token: string }>()
  const [decision, setDecision] = useState<'approved' | 'declined' | null>(null)
  const [done, setDone] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const { data, isLoading, isError, error: loadError } = useQuery({
    queryKey: ['public-shoe-quote', token],
    queryFn: () => getPublicShoeQuote(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  const mut = useMutation({
    mutationFn: (d: 'approved' | 'declined') => decideShoeQuote(token!, d),
    onSuccess: (_, d) => { setDecision(d); setDone(true) },
    onError: (err: unknown) => {
      if (axios.isAxiosError(err)) {
        const s = err.response?.status
        if (s === 409) { setSubmitError('A decision has already been submitted for this quote.'); return }
        if (s === 410) { setSubmitError('This quote link has expired.'); return }
        if (s === 404) { setSubmitError('This quote link is no longer valid.'); return }
      }
      setSubmitError(getApiErrorMessage(err, 'Something went wrong. Please try again or contact the shop.'))
    },
  })

  const bg = { backgroundColor: 'var(--cafe-bg)' }
  const surface = { backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={bg}>
        <div className="text-center" style={{ color: 'var(--cafe-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading your quote…</p>
        </div>
      </div>
    )
  }

  if (isError && loadError) {
    const { title, body } = loadErrorCopy(loadError)
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={bg}>
        <div className="max-w-md text-center">
          <XCircle className="mx-auto mb-4" size={40} style={{ color: '#C96A5A' }} />
          <h1 className="text-xl font-semibold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>{title}</h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>{body}</p>
        </div>
      </div>
    )
  }

  if (!data) return null

  const q = data

  if (q.quote_status === 'approved' || q.quote_status === 'declined') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={bg}>
        <div className="max-w-md text-center">
          {q.quote_status === 'approved'
            ? <CheckCircle className="mx-auto mb-4" size={48} style={{ color: '#1F6D4C' }} />
            : <XCircle className="mx-auto mb-4" size={48} style={{ color: 'var(--cafe-text-muted)' }} />}
          <h1 className="text-xl font-semibold mb-2 capitalize" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Quote already {q.quote_status}
          </h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>This quote has already been responded to. Contact the shop if you have questions.</p>
        </div>
      </div>
    )
  }

  if (done && decision) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={bg}>
        <div className="max-w-md text-center">
          {decision === 'approved' ? (
            <>
              <CheckCircle className="mx-auto mb-4" size={48} style={{ color: '#1F6D4C' }} />
              <h1 className="text-2xl font-bold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Quote Approved!</h1>
              <p style={{ color: 'var(--cafe-text-muted)' }}>Thank you — we've received your approval and will get started on your shoes shortly.</p>
            </>
          ) : (
            <>
              <XCircle className="mx-auto mb-4" size={48} style={{ color: 'var(--cafe-text-muted)' }} />
              <h1 className="text-2xl font-bold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Quote Declined</h1>
              <p style={{ color: 'var(--cafe-text-muted)' }}>We've noted your decision. Please contact us if you'd like to discuss alternatives.</p>
            </>
          )}
        </div>
      </div>
    )
  }

  const shoeDesc = [q.shoe.brand, q.shoe.shoe_type, q.shoe.color].filter(Boolean).join(' · ') || 'Shoe repair'

  return (
    <div className="min-h-screen py-10 px-4" style={bg}>
      <div className="max-w-xl mx-auto space-y-5">
        <div className="text-center mb-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <Footprints size={22} style={{ color: 'var(--cafe-gold-dark)' }} />
          </div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
            Your Shoe Repair Quote
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
            {q.shop_name} · Job #{q.job_number} · {shoeDesc}
          </p>
        </div>

        {/* Line items */}
        <div className="rounded-xl p-5 space-y-3" style={surface}>
          <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Services</h2>
          {q.items.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>Quote details are being finalised.</p>
          ) : (
            q.items.map((item, idx) => (
              <div key={`${item.item_name}-${idx}`} className="flex justify-between items-start text-sm gap-4">
                <div>
                  <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>{item.item_name}</p>
                  {item.notes && <p style={{ color: 'var(--cafe-text-muted)' }}>{item.notes}</p>}
                </div>
                <span className="whitespace-nowrap" style={{ color: 'var(--cafe-text-muted)' }}>
                  {item.unit_price_cents == null ? 'TBC' : formatCents(item.unit_price_cents * item.quantity)}
                </span>
              </div>
            ))
          )}
          <div className="pt-3 border-t flex justify-between text-sm font-semibold" style={{ borderColor: 'var(--cafe-border)' }}>
            <span style={{ color: 'var(--cafe-text)' }}>Total (est.)</span>
            <span style={{ color: 'var(--cafe-amber)' }}>{formatCents(q.subtotal_cents)}</span>
          </div>
        </div>

        {q.description && (
          <div className="rounded-xl p-5" style={surface}>
            <h2 className="text-sm font-semibold uppercase tracking-widest mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Notes</h2>
            <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>{q.description}</p>
          </div>
        )}

        {/* Decision buttons */}
        {submitError && (
          <p className="text-sm text-center" style={{ color: '#C96A5A' }}>{submitError}</p>
        )}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            type="button"
            onClick={() => mut.mutate('declined')}
            disabled={mut.isPending}
            className="py-3 rounded-xl text-sm font-semibold transition-opacity"
            style={{ border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text-muted)', backgroundColor: 'var(--cafe-surface)', opacity: mut.isPending ? 0.6 : 1 }}
          >
            Decline
          </button>
          <button
            type="button"
            onClick={() => mut.mutate('approved')}
            disabled={mut.isPending}
            className="py-3 rounded-xl text-sm font-semibold transition-opacity"
            style={{ backgroundColor: 'var(--cafe-amber)', color: '#fff', opacity: mut.isPending ? 0.6 : 1 }}
          >
            {mut.isPending ? 'Submitting…' : 'Approve Quote'}
          </button>
        </div>
      </div>
    </div>
  )
}
