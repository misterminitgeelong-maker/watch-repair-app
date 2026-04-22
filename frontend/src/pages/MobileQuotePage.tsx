import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { CheckCircle, XCircle, MapPin, Car, PenLine } from 'lucide-react'
import {
  decidePublicAutoKeyQuote,
  getApiErrorMessage,
  getPublicAutoKeyQuote,
  type PublicAutoKeyQuote,
} from '@/lib/api'
import { Button, Card } from '@/components/ui'
import { useEffect, useRef, useState, useCallback } from 'react'

function formatMoney(cents: number, currency: string) {
  const code = (currency || 'AUD').toUpperCase().slice(0, 3)
  return (cents / 100).toLocaleString('en-AU', { style: 'currency', currency: code })
}

// ── Signature pad ────────────────────────────────────────────────────────────

function SignaturePad({
  onSave,
  onCancel,
  isPending,
}: {
  onSave: (dataUrl: string) => void
  onCancel: () => void
  isPending: boolean
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const [hasStrokes, setHasStrokes] = useState(false)

  const getPos = (e: MouseEvent | Touch, canvas: HTMLCanvasElement) => {
    const rect = canvas.getBoundingClientRect()
    return {
      x: (e.clientX - rect.left) * (canvas.width / rect.width),
      y: (e.clientY - rect.top) * (canvas.height / rect.height),
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.strokeStyle = '#1a1a1a'
    ctx.lineWidth = 2.5
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    const start = (e: MouseEvent | TouchEvent) => {
      e.preventDefault()
      drawing.current = true
      const pos = getPos('touches' in e ? e.touches[0] : e, canvas)
      ctx.beginPath()
      ctx.moveTo(pos.x, pos.y)
    }

    const move = (e: MouseEvent | TouchEvent) => {
      e.preventDefault()
      if (!drawing.current) return
      const pos = getPos('touches' in e ? e.touches[0] : e, canvas)
      ctx.lineTo(pos.x, pos.y)
      ctx.stroke()
      setHasStrokes(true)
    }

    const end = () => { drawing.current = false }

    canvas.addEventListener('mousedown', start)
    canvas.addEventListener('mousemove', move)
    canvas.addEventListener('mouseup', end)
    canvas.addEventListener('touchstart', start, { passive: false })
    canvas.addEventListener('touchmove', move, { passive: false })
    canvas.addEventListener('touchend', end)

    return () => {
      canvas.removeEventListener('mousedown', start)
      canvas.removeEventListener('mousemove', move)
      canvas.removeEventListener('mouseup', end)
      canvas.removeEventListener('touchstart', start)
      canvas.removeEventListener('touchmove', move)
      canvas.removeEventListener('touchend', end)
    }
  }, [])

  const clear = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    setHasStrokes(false)
  }, [])

  const save = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    // Strip the data: prefix — backend expects raw base64
    const dataUrl = canvas.toDataURL('image/png')
    const base64 = dataUrl.split(',')[1]
    onSave(base64)
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
          Sign to accept
        </p>
        <button
          type="button"
          onClick={clear}
          className="text-xs px-2 py-0.5 rounded"
          style={{ color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border)' }}
        >
          Clear
        </button>
      </div>

      <div
        className="rounded-lg overflow-hidden"
        style={{ border: '1.5px solid var(--ms-border)', backgroundColor: '#fff', touchAction: 'none' }}
      >
        <canvas
          ref={canvasRef}
          width={600}
          height={180}
          style={{ width: '100%', height: 180, display: 'block', cursor: 'crosshair' }}
        />
      </div>
      <p className="text-xs text-center" style={{ color: 'var(--ms-text-muted)' }}>
        Draw your signature above
      </p>

      <div className="flex gap-3">
        <Button variant="secondary" className="flex-1" onClick={onCancel} disabled={isPending}>
          Back
        </Button>
        <Button
          className="flex-1"
          onClick={save}
          disabled={!hasStrokes || isPending}
        >
          {isPending ? 'Submitting…' : 'Sign & accept'}
        </Button>
      </div>
    </Card>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function MobileQuotePage() {
  const { token } = useParams<{ token: string }>()
  const qc = useQueryClient()
  const [step, setStep] = useState<'view' | 'sign' | 'decline-confirm'>('view')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['public-auto-key-quote', token],
    queryFn: () => getPublicAutoKeyQuote(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  const decideMut = useMutation({
    mutationFn: ({ decision, signatureData }: { decision: 'approved' | 'declined'; signatureData?: string }) =>
      decidePublicAutoKeyQuote(token!, decision, { signatureData }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['public-auto-key-quote', token] })
      setStep('view')
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
            <img src="/mainspring-icon.svg" alt="Mainspring" style={{ width: 30, height: 30 }} />
          </div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--ms-text)' }}>{quote.shop_name}</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            Quote for job #{quote.job_number}
            {quote.customer_name ? ` — ${quote.customer_name}` : ''}
          </p>
        </div>

        {/* Status banner */}
        {isApproved && (
          <div className="rounded-xl px-4 py-3" style={{ backgroundColor: 'rgba(80,180,100,0.12)', border: '1px solid rgba(80,180,100,0.3)' }}>
            <div className="flex items-center gap-3 mb-1">
              <CheckCircle size={20} style={{ color: '#3A9A50', flexShrink: 0 }} />
              <p className="text-sm font-semibold" style={{ color: '#2A7A40' }}>Quote accepted</p>
            </div>
            {quote.signed_at && (
              <p className="text-xs ml-8" style={{ color: '#2A7A40' }}>
                Signed {new Date(quote.signed_at).toLocaleString('en-AU', { dateStyle: 'medium', timeStyle: 'short' })}
                {quote.signer_name ? ` by ${quote.signer_name}` : ''}
              </p>
            )}
            <p className="text-xs ml-8 mt-0.5" style={{ color: '#2A7A40' }}>We'll be in touch to confirm your appointment.</p>
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
        <Card className="p-4 space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Job details</h2>
          <p className="font-semibold" style={{ color: 'var(--ms-text)' }}>{quote.title}</p>
          {vehicle && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>
              <Car size={14} /><span>{vehicle}</span>
            </div>
          )}
          {quote.job_address && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>
              <MapPin size={14} /><span>{quote.job_address}</span>
            </div>
          )}
        </Card>

        {/* Quote breakdown */}
        <Card className="p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--ms-text-muted)' }}>Quote breakdown</h2>
          <div className="space-y-2">
            {quote.line_items.map((item, i) => (
              <div key={i} className="flex items-start justify-between gap-4 text-sm">
                <span style={{ color: 'var(--ms-text)' }}>
                  {item.description}
                  {item.quantity !== 1 && <span className="ml-1" style={{ color: 'var(--ms-text-muted)' }}>× {item.quantity}</span>}
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
                  <span>Subtotal</span><span>{formatMoney(quote.subtotal_cents, quote.currency)}</span>
                </div>
                <div className="flex justify-between text-sm" style={{ color: 'var(--ms-text-mid)' }}>
                  <span>GST</span><span>{formatMoney(quote.tax_cents, quote.currency)}</span>
                </div>
              </>
            )}
            <div className="flex justify-between font-bold text-base pt-1" style={{ color: 'var(--ms-text)' }}>
              <span>Total</span><span>{formatMoney(quote.total_cents, quote.currency)}</span>
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

            {step === 'sign' && (
              <SignaturePad
                isPending={decideMut.isPending}
                onCancel={() => setStep('view')}
                onSave={signatureData => decideMut.mutate({ decision: 'approved', signatureData })}
              />
            )}

            {step === 'decline-confirm' && (
              <Card className="p-4 space-y-3">
                <p className="text-sm font-medium text-center" style={{ color: 'var(--ms-text)' }}>
                  Are you sure you want to decline this quote?
                </p>
                <div className="flex gap-3">
                  <Button variant="secondary" className="flex-1" onClick={() => setStep('view')}>Go back</Button>
                  <Button
                    className="flex-1"
                    style={{ backgroundColor: '#C96A5A', color: '#fff' }}
                    onClick={() => decideMut.mutate({ decision: 'declined' })}
                    disabled={decideMut.isPending}
                  >
                    {decideMut.isPending ? 'Declining…' : 'Yes, decline'}
                  </Button>
                </div>
              </Card>
            )}

            {step === 'view' && (
              <>
                <Button
                  className="w-full py-3 text-base font-semibold flex items-center justify-center gap-2"
                  onClick={() => setStep('sign')}
                >
                  <PenLine size={18} />
                  Review & sign quote
                </Button>
                <button
                  type="button"
                  className="w-full text-sm py-2"
                  style={{ color: 'var(--ms-text-muted)' }}
                  onClick={() => setStep('decline-confirm')}
                >
                  Decline quote
                </button>
              </>
            )}
          </div>
        )}

        {quote.shop_phone && (
          <p className="text-xs text-center" style={{ color: 'var(--ms-text-muted)' }}>
            Questions? Call{' '}
            <a href={`tel:${quote.shop_phone}`} style={{ color: 'var(--ms-accent)' }}>{quote.shop_phone}</a>
          </p>
        )}
      </div>
    </div>
  )
}
