import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelShopMobileBooking,
  createShopMobileBooking,
  formatTenantLabel,
  getApiErrorMessage,
  listShopMobileBookings,
  suggestShopMobileOperator,
  type ShopMobileBooking,
  type ShopMobileOperatorOption,
  type ShopMobileVisitLocationType,
} from '@/lib/api'
import { AddressAutocompleteInput } from '@/components/AddressAutocompleteInput'
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import { formatDate } from '@/lib/utils'

const AU_STATES = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'] as const

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  accepted: 'Accepted',
  declined: 'Declined',
  cancelled: 'Cancelled',
  expired: 'Expired',
}

const ROUTING_LABEL: Record<string, string> = {
  suburb_route: 'Mapped suburb',
  fallback_operator: 'Fallback operator',
  manual_override: 'Manual override',
}

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'danger' {
  if (status === 'accepted') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'declined' || status === 'cancelled' || status === 'expired') return 'danger'
  return 'default'
}

export default function ShopMobileBookingsPage() {
  const qc = useQueryClient()
  const { tenantBusinessAddress } = useAuth()
  const [error, setError] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [vehicleMake, setVehicleMake] = useState('')
  const [vehicleModel, setVehicleModel] = useState('')
  const [registrationPlate, setRegistrationPlate] = useState('')
  const [visitType, setVisitType] = useState<ShopMobileVisitLocationType>('customer_site')
  const [jobAddress, setJobAddress] = useState('')
  const [preferredAt, setPreferredAt] = useState('')
  const [jobType, setJobType] = useState('')
  const [notes, setNotes] = useState('')
  const [routeSuburb, setRouteSuburb] = useState('')
  const [routeState, setRouteState] = useState<string>('VIC')
  const [routedOperator, setRoutedOperator] = useState<ShopMobileOperatorOption | null>(null)
  const [routingLookupError, setRoutingLookupError] = useState('')

  const { data: bookings = [], isLoading: listLoading } = useQuery({
    queryKey: ['shop-mobile-bookings'],
    queryFn: () => listShopMobileBookings().then(r => r.data),
  })

  useEffect(() => {
    if (visitType === 'at_shop' && tenantBusinessAddress?.trim()) {
      setJobAddress(tenantBusinessAddress.trim())
    }
  }, [visitType, tenantBusinessAddress])

  useEffect(() => {
    const suburb = routeSuburb.trim()
    if (!suburb) {
      setRoutedOperator(null)
      setRoutingLookupError('')
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      void (async () => {
        setRoutingLookupError('')
        try {
          const res = await suggestShopMobileOperator(suburb, routeState)
          if (cancelled) return
          setRoutedOperator(res.data)
          if (!res.data) {
            setRoutingLookupError('No operator configured for this suburb. Contact support.')
          }
        } catch (err) {
          if (!cancelled) {
            setRoutedOperator(null)
            setRoutingLookupError(getApiErrorMessage(err, 'Could not look up operator for this suburb.'))
          }
        }
      })()
    }, 400)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [routeSuburb, routeState])

  const createMut = useMutation({
    mutationFn: () =>
      createShopMobileBooking({
        suburb: routeSuburb.trim(),
        state_code: routeState,
        customer_name: customerName.trim(),
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        vehicle_make: vehicleMake.trim() || undefined,
        vehicle_model: vehicleModel.trim() || undefined,
        registration_plate: registrationPlate.trim() || undefined,
        visit_location_type: visitType,
        job_address: jobAddress.trim(),
        preferred_scheduled_at: preferredAt ? new Date(preferredAt).toISOString() : undefined,
        job_type: jobType.trim() || undefined,
        notes: notes.trim() || undefined,
      }).then(r => r.data),
    onSuccess: () => {
      setError('')
      setCustomerName('')
      setPhone('')
      setEmail('')
      setVehicleMake('')
      setVehicleModel('')
      setRegistrationPlate('')
      setJobAddress('')
      setPreferredAt('')
      setJobType('')
      setNotes('')
      qc.invalidateQueries({ queryKey: ['shop-mobile-bookings'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not submit booking request.')),
  })

  const cancelMut = useMutation({
    mutationFn: (id: string) => cancelShopMobileBooking(id).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shop-mobile-bookings'] }),
    onError: err => setError(getApiErrorMessage(err, 'Could not cancel request.')),
  })

  const canSubmit =
    Boolean(routeSuburb.trim()) &&
    Boolean(customerName.trim()) &&
    Boolean(jobAddress.trim()) &&
    Boolean(routedOperator) &&
    !routingLookupError

  return (
    <div>
      <PageHeader title="Book mobile locksmith" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Submit a booking request — we route it to your network mobile operator automatically.
      </p>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

      <Card className="mb-6 p-5">
        <h2 className="font-semibold mb-4" style={{ color: 'var(--ms-text)' }}>New booking request</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>
              Job location (for routing)
            </p>
            <div className="flex flex-wrap gap-2 items-end">
              <Input
                label="Suburb"
                value={routeSuburb}
                onChange={e => setRouteSuburb(e.target.value)}
                placeholder="Chadstone"
                className="min-w-[140px] flex-1"
                required
              />
              <Select label="State" value={routeState} onChange={e => setRouteState(e.target.value)} className="w-28">
                {AU_STATES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </Select>
            </div>
            {routedOperator && (
              <p className="text-xs mt-2" style={{ color: 'var(--ms-text-mid)' }}>
                Routed to{' '}
                <span className="font-medium">
                  {formatTenantLabel(routedOperator.tenant_name, routedOperator.shop_number)}
                </span>
                {routedOperator.routing_rule && (
                  <span style={{ color: 'var(--ms-text-muted)' }}>
                    {' '}
                    · {ROUTING_LABEL[routedOperator.routing_rule] ?? routedOperator.routing_rule}
                  </span>
                )}
              </p>
            )}
            {routingLookupError && (
              <p className="text-xs mt-2" style={{ color: '#C96A5A' }}>{routingLookupError}</p>
            )}
          </div>
          <Input label="Customer name" value={customerName} onChange={e => setCustomerName(e.target.value)} required />
          <Input label="Phone" value={phone} onChange={e => setPhone(e.target.value)} />
          <Input label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} />
          <Input label="Vehicle make" value={vehicleMake} onChange={e => setVehicleMake(e.target.value)} />
          <Input label="Vehicle model" value={vehicleModel} onChange={e => setVehicleModel(e.target.value)} />
          <Input label="Registration" value={registrationPlate} onChange={e => setRegistrationPlate(e.target.value)} />
          <Select label="Visit location" value={visitType} onChange={e => setVisitType(e.target.value as ShopMobileVisitLocationType)}>
            <option value="customer_site">Customer site (mobile)</option>
            <option value="at_shop">At our shop</option>
          </Select>
          <Input label="Job type" value={jobType} onChange={e => setJobType(e.target.value)} placeholder="Lockout – Car" />
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--ms-text)' }}>Address</label>
            <AddressAutocompleteInput value={jobAddress} onChange={setJobAddress} placeholder={visitType === 'at_shop' ? 'Shop address' : 'Customer address'} />
          </div>
          <Input label="Preferred date & time" type="datetime-local" value={preferredAt} onChange={e => setPreferredAt(e.target.value)} />
          <div className="md:col-span-2">
            <Textarea label="Notes for operator" value={notes} onChange={e => setNotes(e.target.value)} rows={3} />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            onClick={() => createMut.mutate()}
            disabled={createMut.isPending || !canSubmit}
          >
            {createMut.isPending ? 'Sending…' : 'Send booking request'}
          </Button>
        </div>
      </Card>

      <Card>
        <div className="px-5 py-3.5" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>My booking requests</h2>
        </div>
        {listLoading ? (
          <Spinner />
        ) : bookings.length === 0 ? (
          <EmptyState message="No booking requests yet." />
        ) : (
          <div className="divide-y" style={{ borderColor: 'var(--ms-border)' }}>
            {bookings.map((b: ShopMobileBooking) => (
              <div key={b.id} className="px-5 py-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>{b.customer_name}</p>
                    <Badge variant={statusVariant(b.status)}>{STATUS_LABEL[b.status] ?? b.status}</Badge>
                  </div>
                  <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                    Operator: {formatTenantLabel(b.target_operator_name, b.target_operator_shop_number)} · {formatDate(b.created_at)}
                  </p>
                  {b.job_suburb && b.job_state_code && (
                    <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                      Routed from {b.job_suburb}, {b.job_state_code}
                      {b.operator_routing_rule
                        ? ` · ${ROUTING_LABEL[b.operator_routing_rule] ?? b.operator_routing_rule}`
                        : ''}
                    </p>
                  )}
                  {b.status === 'accepted' && b.resulting_job_number && (
                    <p className="text-xs mt-1" style={{ color: 'var(--ms-text-mid)' }}>
                      Job {b.resulting_job_number}
                      {b.job_status ? ` · ${b.job_status.replace(/_/g, ' ')}` : ''}
                    </p>
                  )}
                  {b.status === 'declined' && b.decline_reason && (
                    <p className="text-xs mt-1" style={{ color: '#C96A5A' }}>{b.decline_reason}</p>
                  )}
                </div>
                {b.status === 'pending' && (
                  <Button variant="secondary" className="text-xs" onClick={() => cancelMut.mutate(b.id)} disabled={cancelMut.isPending}>
                    Cancel
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
