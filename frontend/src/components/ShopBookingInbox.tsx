import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  acceptShopMobileBooking,
  declineShopMobileBooking,
  getApiErrorMessage,
  listShopMobileBookings,
  type ShopMobileBooking,
} from '@/lib/api'
import { Badge, Button, Card, Modal, Textarea } from '@/components/ui'
import { formatDate } from '@/lib/utils'

export default function ShopBookingInbox() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [declineTarget, setDeclineTarget] = useState<ShopMobileBooking | null>(null)
  const [declineReason, setDeclineReason] = useState('')

  const { data: pending = [], isLoading } = useQuery({
    queryKey: ['shop-mobile-bookings', 'pending'],
    queryFn: () => listShopMobileBookings('pending').then(r => r.data),
  })

  const acceptMut = useMutation({
    mutationFn: (id: string) => acceptShopMobileBooking(id).then(r => r.data),
    onSuccess: (row) => {
      setError('')
      if (row.schedule_conflict_warning) {
        setError(row.schedule_conflict_warning)
      }
      qc.invalidateQueries({ queryKey: ['shop-mobile-bookings'] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      if (row.resulting_auto_key_job_id) {
        navigate(`/auto-key/${row.resulting_auto_key_job_id}`)
      }
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not accept booking.')),
  })

  const declineMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      declineShopMobileBooking(id, reason).then(r => r.data),
    onSuccess: () => {
      setError('')
      setDeclineTarget(null)
      setDeclineReason('')
      qc.invalidateQueries({ queryKey: ['shop-mobile-bookings'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not decline booking.')),
  })

  if (isLoading) return null
  if (pending.length === 0) return null

  return (
    <Card className="mb-6 p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>
          Shop booking requests
          <Badge variant="warning" className="ml-2">{pending.length}</Badge>
        </h2>
        <Link to="/auto-key" className="text-xs font-medium" style={{ color: 'var(--ms-accent)' }}>
          View all jobs
        </Link>
      </div>
      {error && (
        <p className="text-sm mb-3" style={{ color: '#C96A5A' }}>{error}</p>
      )}
      <div className="space-y-3">
        {pending.map(b => (
          <div
            key={b.id}
            className="rounded-lg p-4"
            style={{ border: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-surface)' }}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                  {b.customer_name}
                  <span className="font-normal" style={{ color: 'var(--ms-text-muted)' }}> · from {b.requesting_shop_name}</span>
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                  {b.job_address} · {formatDate(b.created_at)}
                </p>
                {b.notes && (
                  <p className="text-xs mt-2" style={{ color: 'var(--ms-text-mid)' }}>{b.notes}</p>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <Button
                  className="text-xs"
                  onClick={() => acceptMut.mutate(b.id)}
                  disabled={acceptMut.isPending || declineMut.isPending}
                >
                  {acceptMut.isPending ? 'Accepting…' : 'Accept'}
                </Button>
                <Button
                  variant="secondary"
                  className="text-xs"
                  onClick={() => { setDeclineTarget(b); setDeclineReason('') }}
                  disabled={acceptMut.isPending || declineMut.isPending}
                >
                  Decline
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {declineTarget && (
        <Modal title="Decline booking" onClose={() => setDeclineTarget(null)}>
          <p className="text-sm mb-3" style={{ color: 'var(--ms-text-mid)' }}>
            Decline request from {declineTarget.requesting_shop_name} for {declineTarget.customer_name}?
          </p>
          <Textarea label="Reason (optional)" value={declineReason} onChange={e => setDeclineReason(e.target.value)} rows={3} />
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="secondary" onClick={() => setDeclineTarget(null)}>Cancel</Button>
            <Button
              onClick={() => declineMut.mutate({ id: declineTarget.id, reason: declineReason.trim() || undefined })}
              disabled={declineMut.isPending}
            >
              {declineMut.isPending ? 'Declining…' : 'Decline request'}
            </Button>
          </div>
        </Modal>
      )}
    </Card>
  )
}
