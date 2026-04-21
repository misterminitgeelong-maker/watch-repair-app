import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Calendar, CheckCircle, Clock, MapPin, Wrench } from 'lucide-react'
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

export default function MobileBookingPage() {
  const { token } = useParams<{ token: string }>()
  const qc = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['public-auto-key-booking', token],
    queryFn: () => getPublicAutoKeyBooking(token!).then(r => r.data),
    enabled: !!token,
    retry: false,
  })

  const confirmMut = useMutation({
    mutationFn: () => confirmPublicAutoKeyBooking(token!).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['public-auto-key-booking', token] })
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
                Thank you. Your booking is confirmed; the shop will complete the service at the scheduled time (the job stays open for them until then).
              </p>
            </div>
          </div>
        ) : canConfirm ? (
          <div className="space-y-3">
            <p className="text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
              Tap confirm to accept this time and the quoted price. This only confirms your booking — the job is not marked as finished until the work is done.
            </p>
            <Button
              type="button"
              className="w-full min-h-12"
              disabled={confirmMut.isPending}
              onClick={() => confirmMut.mutate()}
            >
              {confirmMut.isPending ? 'Confirming…' : 'Confirm booking'}
            </Button>
            {confirmMut.isError && (
              <p className="text-sm text-center" style={{ color: '#C96A5A' }}>
                {getApiErrorMessage(confirmMut.error, 'Could not confirm. Try again or call the shop.')}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
            This job is not awaiting confirmation. Contact the shop if you need help.
          </p>
        )}
      </div>
    </div>
  )
}
