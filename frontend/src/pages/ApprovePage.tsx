import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { CheckCircle, XCircle, Clock, WrenchIcon } from 'lucide-react'
import { getPublicQuote, submitQuoteDecision } from '@/lib/api'
import SignaturePad from '@/components/SignaturePad'

function formatCents(c: number) {
  return (c / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export default function ApprovePage() {
  const { token } = useParams<{ token: string }>()
  const [decision, setDecision] = useState<'approved' | 'declined' | null>(null)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [signature, setSignature] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-quote', token],
    queryFn: () => getPublicQuote(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  const mut = useMutation({
    mutationFn: (d: 'approved' | 'declined') => submitQuoteDecision(token!, d, signature),
    onSuccess: (_, d) => { setDecision(d); setDone(true) },
    onError: () => setError('Something went wrong. Please try again or contact the shop.'),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="text-center" style={{ color: 'var(--cafe-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading your quote…</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="max-w-md text-center">
          <XCircle className="mx-auto mb-4" size={40} style={{ color: '#C96A5A' }} />
          <h1 className="text-xl font-semibold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Quote not found</h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>This quote link may have expired or is invalid. Please contact the shop.</p>
        </div>
      </div>
    )
  }

  const q = data

  if (done && decision) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="max-w-md text-center">
          {decision === 'approved' ? (
            <>
              <CheckCircle className="mx-auto mb-4 text-green-500" size={48} />
              <h1 className="text-2xl font-bold mb-2" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Quote Approved!</h1>
              <p style={{ color: 'var(--cafe-text-muted)' }}>Thank you! We've received your approval and will be in touch shortly to confirm next steps.</p>
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

  // Already decided
  if (q.status === 'approved' || q.status === 'declined') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <div className="max-w-md text-center">
          {q.status === 'approved'
            ? <CheckCircle className="mx-auto mb-4 text-green-500" size={48} />
            : <XCircle className="mx-auto mb-4" size={48} style={{ color: 'var(--cafe-text-muted)' }} />}
          <h1 className="text-xl font-semibold mb-2 capitalize" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Quote already {q.status}</h1>
          <p style={{ color: 'var(--cafe-text-muted)' }}>This quote has already been responded to. Please contact the shop if you have questions.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-10 px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <div className="max-w-xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-4" style={{ backgroundColor: '#EEE6DA' }}>
            <WrenchIcon size={22} style={{ color: 'var(--cafe-gold-dark)' }} />
          </div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Your Repair Quote</h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>Review the quote below and let us know your decision.</p>
        </div>

        {/* Quote card */}
        <div className="rounded-2xl shadow-sm overflow-hidden mb-5" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
          {/* Line items */}
          <table className="w-full text-sm">
            <thead>
              <tr style={{ backgroundColor: 'var(--cafe-bg)', borderBottom: '1px solid var(--cafe-border)' }}>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Item</th>
                <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Qty</th>
                <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Unit</th>
                <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {q.line_items.map((li, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <td className="px-5 py-3">
                    <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>{li.description}</p>
                    <p className="text-xs capitalize" style={{ color: 'var(--cafe-text-muted)' }}>{li.item_type}</p>
                  </td>
                  <td className="px-5 py-3 text-right" style={{ color: 'var(--cafe-text-mid)' }}>{li.quantity}</td>
                  <td className="px-5 py-3 text-right" style={{ color: 'var(--cafe-text-mid)' }}>{formatCents(li.unit_price_cents)}</td>
                  <td className="px-5 py-3 text-right font-medium" style={{ color: 'var(--cafe-text)' }}>{formatCents(li.total_price_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Totals */}
          <div className="px-5 py-4 space-y-1.5" style={{ borderTop: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
            <div className="flex justify-between text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              <span>Subtotal</span><span>{formatCents(q.subtotal_cents)}</span>
            </div>
            <div className="flex justify-between text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              <span>Tax</span><span>{formatCents(q.tax_cents)}</span>
            </div>
            <div className="flex justify-between font-bold text-base pt-1" style={{ borderTop: '1px solid var(--cafe-border)', color: 'var(--cafe-text)' }}>
              <span>Total</span><span>{formatCents(q.total_cents)}</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>{error}</div>
        )}

        {/* Optional signature */}
        <div className="mb-5">
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--cafe-text-muted)' }}>Sign to approve (optional)</p>
          <SignaturePad onSignatureChange={setSignature} width={280} height={100} />
        </div>

        {/* Decision buttons */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => mut.mutate('declined')}
            disabled={mut.isPending}
            className="flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-medium transition-colors disabled:opacity-50"
            style={{ border: '2px solid var(--cafe-border-2)', color: 'var(--cafe-text-mid)' }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'var(--cafe-bg)'; e.currentTarget.style.borderColor = 'var(--cafe-amber)' }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.borderColor = 'var(--cafe-border-2)' }}
          >
            <XCircle size={18} />Decline
          </button>
          <button
            onClick={() => mut.mutate('approved')}
            disabled={mut.isPending}
            className="flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold transition-colors shadow-sm disabled:opacity-50"
            style={{ backgroundColor: 'var(--cafe-amber)', color: '#FEFCF8' }}
            onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--cafe-gold-dark)')}
            onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'var(--cafe-amber)')}
          >
            <CheckCircle size={18} />{mut.isPending ? 'Submitting…' : 'Approve'}
          </button>
        </div>

        <p className="text-center text-xs mt-5" style={{ color: 'var(--cafe-text-muted)' }}>
          Questions? Contact your watch repair shop directly.
        </p>
      </div>
    </div>
  )
}
