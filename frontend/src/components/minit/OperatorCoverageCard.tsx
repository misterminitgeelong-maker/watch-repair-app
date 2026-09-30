import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MapContainer, TileLayer, Circle, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { getApiErrorMessage, setSiteBaseLocation, type ParentAccountSite } from '@/lib/api'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Input } from '@/components/ui'

const AU_CENTRE: [number, number] = [-28.5, 134]

/** HQ view of operator coverage: a circle per operator, plus where each one's rings start. */
export default function OperatorCoverageCard({ sites }: { sites: ParentAccountSite[] }) {
  const placed = sites.filter(s => s.base_lat != null && s.base_lng != null)
  return (
    <div className="ml-8 mb-5">
      <p className="text-sm font-medium mb-1" style={{ color: 'var(--ms-text)' }}>
        Operator coverage ({placed.length} of {sites.length} operators placed)
      </p>
      <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>
        HQ sets each operator&apos;s starting point and ring size. Operators can&apos;t change them.
        Circles show Ring 1 for each operator.
      </p>
      <div className="rounded-lg overflow-hidden border mb-3" style={{ borderColor: 'var(--ms-border)', height: 320 }}>
        <MapContainer center={AU_CENTRE} zoom={4} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {placed.map(s => (
            <Circle
              key={s.tenant_id}
              center={[s.base_lat as number, s.base_lng as number]}
              radius={(s.ring_radius_km ?? 10) * 1000}
              pathOptions={{ color: '#D2361B', weight: 2, fillOpacity: 0.12 }}
            >
              <Tooltip>{s.tenant_name} · {s.ring_radius_km ?? 10}km</Tooltip>
            </Circle>
          ))}
        </MapContainer>
      </div>
      <div className="space-y-2">
        {sites.map(s => <OperatorBaseRow key={s.tenant_id} site={s} />)}
      </div>
    </div>
  )
}

function OperatorBaseRow({ site }: { site: ParentAccountSite }) {
  const qc = useQueryClient()
  const [where, setWhere] = useState('')
  const [ringKm, setRingKm] = useState(site.ring_radius_km ?? 10)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const mut = useMutation({
    mutationFn: () => {
      const v = where.trim()
      const payload = /^\d{4}$/.test(v) ? { postcode: v } : { address: v }
      return setSiteBaseLocation(site.tenant_id, { ...payload, ring_radius_km: ringKm }).then(r => r.data)
    },
    onSuccess: () => {
      setSaved(true)
      setError('')
      setWhere('')
      void qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
    },
    onError: err => setError(getApiErrorMessage(err) || 'Could not save base location.'),
  })

  return (
    <div className="flex flex-col sm:flex-row sm:items-end gap-2">
      <div className="sm:w-56 text-sm" style={{ color: 'var(--ms-text)' }}>
        <p className="font-medium">{site.tenant_name}</p>
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          {site.base_lat != null
            ? `Base set · ${site.ring_radius_km ?? 10}km rings`
            : 'No base set — no ring yet'}
        </p>
      </div>
      <div className="flex-1 min-w-0">
        <Input
          label="Postcode or base address"
          value={where}
          onChange={e => { setWhere(e.target.value); setSaved(false) }}
          placeholder="e.g. 3000 or 123 Depot St, Melbourne VIC"
        />
      </div>
      <input
        type="number"
        aria-label="Ring size in km"
        min={1}
        max={200}
        value={ringKm}
        onChange={e => { setRingKm(Number(e.target.value)); setSaved(false) }}
        className="w-24 px-3 py-2 rounded-lg text-sm outline-none"
        style={{ border: '1px solid var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
      />
      <Button onClick={() => mut.mutate()} disabled={!where.trim() || mut.isPending}>
        {mut.isPending ? 'Saving…' : 'Set'}
      </Button>
      {error && <p className="text-xs" style={{ color: 'var(--ms-error)' }}>{error}</p>}
      {saved && <p className="text-xs" style={{ color: 'var(--ms-badge-done-text)' }}>Saved.</p>}
    </div>
  )
}
