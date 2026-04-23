import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Calendar, CheckCircle, Clock, MapPin, PenLine, Wrench } from 'lucide-react'
import {
  confirmPublicAutoKeyBooking,
  getApiErrorMessage,
  getPublicAutoKeyBooking,
  type PublicAutoKeyBooking,
} from '@/lib/api'
import { Button, Card } from '@/components/ui'

function formatMoney(cents: number, currency: string) {
  const code = (currency || 'AUD').toUpperCase().slice(0, 3)
  return (cents / 100).toLocaleString('en-AU', { style: 'currency', currency: code })
}

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
    const dataUrl = canvas.toDataURL('image/png')
    const base64 = dataUrl.split(',')[1]
    onSave(base64)
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
          Sign to confirm booking
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
          {isPending ? 'Confirming…' : 'Sign & confirm'}
        </Button>
      </div>
    </Card>
  )
}

export default function MobileBookingPage() {
  const { token } = useParams<{ token: string }>()
  const qc = useQueryClient()
  const [step, setStep] = useState<'view' | 'sign'>('view')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['public-auto-key-booking', token],
    queryFn: () => getPublicAutoKeyBooking(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  const confirmMut = useMutation({
    mutationFn: (signatureData: string) =>
      confirmPublicAutoKeyBooking(token!, { signatureData }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['public-auto-key-booking', token] })
      setStep('view')
    },
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="text-center" style={{ color: 'var(--ms-text-muted)' }}>
          <Clock className="mx-auto mb-3 animate-spin" size={28} />
          <p>Loading booking…</p>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    const msg =
      axios.isAxiosError(error) && error.response?.status === 404
        ? 'This booking link is not valid or has expired. Contact the shop if you need a new link.'
        : getApiErrorMessage(error, 'Could not load booking.')
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>
            Booking link unavailable
          </h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>{msg}</p>
        </div>
      </div>
    )
  }

  const job = data as PublicAutoKeyBooking
  const confirmed = job.already_confirmed || job.status === 'booked'
  const canConfirm = job.status === 'pending_booking' && !confirmed

  const scheduled =
    job.scheduled_at != null && job.scheduled_at !== ''
      ? new Date(job.scheduled_at).toLocaleString('en-AU', {
          dateStyle: 'medium',
          timeStyle: 'short',
        })
      : null

  return (
    <div className="min-h-screen py-6 px-4 sm:py-10 sm:px-5" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-4 sm:space-y-5">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3" style={{ backgroundColor: '#EEE6DA' }}>
            <Wrench size={22} style={{ color: 'var(--ms-accent-hover)' }} />
          </div>
          <h1 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--ms-text)' }}>
            Mobile service booking
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            Job #{job.job_number} · {job.title}
          </p>
        </div>

        <Card className="p-4 sm:p-5 space-y-3">
          {job.vehicle_make || job.vehicle_model ? (
            <p className="text-sm" style={{ color: 'var(--ms-text)' }}>
              <span className="font-medium">Vehicle: </span>
              {[job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}
            </p>
          ) : null}
          {scheduled && (
            <div className="flex gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
              <Calendar size={18} className="shrink-0 mt-0.5" style={{ color: 'var(--ms-accent)' }} />
              <span><span className="font-medium">Scheduled: </span>{scheduled}</span>
            </div>
          )}
          {job.job_address && (
            <div className="flex gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
              <MapPin size={18} className="shrink-0 mt-0.5" style={{ color: 'var(--ms-accent)' }} />
              <span>{job.job_address}</span>
            </div>
          )}

          <div className="pt-2" style={{ borderTop: '1px solid var(--ms-border)' }}>
            <p className="text-xs uppercase tracking-widest mb-2" style={{ color: 'var(--ms-text-muted)' }}>Quote</p>
            {job.line_items.length > 0 ? (
              <ul className="text-sm space-y-1 mb-2" style={{ color: 'var(--ms-text-muted)' }}>
                {job.line_items.map((li, i) => (
                  <li key={i}>
                    {li.quantity}× {li.description} — {formatMoney(li.total_price_cents, job.currency)}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="flex justify-between text-sm">
              <span style={{ color: 'var(--ms-text-muted)' }}>Total (incl. GST)</span>
              <span className="font-semibold tabular-nums" style={{ color: 'var(--ms-text)' }}>
                {formatMoney(job.quote_total_cents, job.currency)}
              </span>
            </div>
          </div>
        </Card>

        {confirmed ? (
          <div
            className="rounded-xl p-4 flex items-start gap-3"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
          >
            <CheckCircle className="shrink-0 text-green-700" size={22} />
            <div>
              <p className="font-semibold" style={{ color: 'var(--ms-text)' }}>Booking confirmed</p>
              <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                Thank you. Your booking is confirmed; the shop will complete the service at the scheduled time.
              </p>
            </div>
          </div>
        ) : canConfirm ? (
          step === 'sign' ? (
            <>
              <p className="text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
                By signing you accept the quoted price and confirm your booking.
              </p>
              <SignaturePad
                isPending={confirmMut.isPending}
                onCancel={() => setStep('view')}
                onSave={sig => confirmMut.mutate(sig)}
              />
              {confirmMut.isError && (
                <p className="text-sm text-center" style={{ color: '#C96A5A' }}>
                  {getApiErrorMessage(confirmMut.error, 'Could not confirm. Try again or call the shop.')}
                </p>
              )}
            </>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
                Review the details above, then sign to accept the quoted price and confirm your booking.
              </p>
              <Button
                type="button"
                className="w-full min-h-12 flex items-center justify-center gap-2"
                onClick={() => setStep('sign')}
              >
                <PenLine size={18} />
                Review &amp; sign to confirm
              </Button>
            </div>
          )
        ) : (
          <p className="text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
            This job is not awaiting confirmation. Contact the shop if you need help.
          </p>
        )}
      </div>
    </div>
  )
}
