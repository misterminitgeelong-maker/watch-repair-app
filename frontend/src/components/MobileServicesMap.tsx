import { useCallback, useEffect, useState } from 'react'
import { APIProvider, Map as GoogleMap, Marker, InfoWindow, useMarkerRef, useMap } from '@vis.gl/react-google-maps'
import { STATUS_LABELS } from '@/lib/utils'

const MELBOURNE_CENTRE = { lat: -37.8136, lng: 144.9631 }

interface Customer {
  id: string
  full_name: string
}

interface Job {
  id: string
  job_number: string
  title: string
  job_address?: string
  job_type?: string
  scheduled_at?: string
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  status: string
  customer_id: string
}

interface Props {
  jobs: Job[]
  date: string
  customers?: Customer[]
}

async function geocodeWithGoogle(address: string, apiKey: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const res = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(address)}&region=au&key=${apiKey}`
    )
    const data = await res.json()
    if (data?.status === 'OK' && data?.results?.[0]?.geometry?.location) {
      const loc = data.results[0].geometry.location
      return { lat: loc.lat, lng: loc.lng }
    }
  } catch {
    // ignore
  }
  return null
}

function customerName(customers: Customer[], customerId: string): string {
  const c = customers.find((x) => x.id === customerId)
  return c?.full_name ?? '—'
}

function vehicleLabel(job: Job): string {
  const parts = [job.vehicle_make || 'Vehicle', job.vehicle_model, job.vehicle_year?.toString(), job.registration_plate].filter(Boolean)
  return parts.join(' · ') || '—'
}

function MarkerWithInfoWindow({
  job,
  position,
  customers,
}: {
  job: Job
  position: { lat: number; lng: number }
  customers: Customer[]
}) {
  const [markerRef, marker] = useMarkerRef()
  const [infoWindowShown, setInfoWindowShown] = useState(false)
  const handleMarkerClick = useCallback(() => setInfoWindowShown((s) => !s), [])
  const handleClose = useCallback(() => setInfoWindowShown(false), [])

  return (
    <>
      <Marker ref={markerRef} position={position} onClick={handleMarkerClick} />
      {infoWindowShown && marker && (
        <InfoWindow anchor={marker} onClose={handleClose}>
          <div className="min-w-[200px] text-sm" style={{ color: 'var(--cafe-text)' }}>
            <p className="font-semibold" style={{ color: 'var(--cafe-amber)' }}>
              #{job.job_number}
            </p>
            <p className="mt-1 font-medium">{vehicleLabel(job)}</p>
            <p className="mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
              {customerName(customers, job.customer_id)}
            </p>
            <p className="mt-0.5">
              <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: '#EEE8E3', color: 'var(--cafe-text-mid)' }}>
                {STATUS_LABELS[job.status] ?? job.status.replace(/_/g, ' ')}
              </span>
            </p>
            <p className="mt-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              {job.job_address}
            </p>
            <a
              href={`/auto-key/${job.id}`}
              className="mt-2 inline-block text-xs font-semibold hover:underline"
              style={{ color: 'var(--cafe-amber)' }}
              onClick={(e) => e.stopPropagation()}
            >
              View job →
            </a>
          </div>
        </InfoWindow>
      )}
    </>
  )
}

function MapContent({
  jobs,
  customers,
  geocoded,
}: {
  jobs: Job[]
  customers: Customer[]
  geocoded: Map<string, { lat: number; lng: number }>
}) {
  const map = useMap()

  useEffect(() => {
    if (!map || geocoded.size === 0) return
    const coords = Array.from(geocoded.values())
    if (coords.length === 1) {
      map.setCenter(coords[0])
      map.setZoom(14)
    } else if (coords.length > 1) {
      const lats = coords.map((c) => c.lat)
      const lngs = coords.map((c) => c.lng)
      const bounds = {
        south: Math.min(...lats),
        north: Math.max(...lats),
        west: Math.min(...lngs),
        east: Math.max(...lngs),
      }
      map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 })
    }
  }, [map, geocoded])

  return (
    <>
      {jobs.map((job) => {
        const coords = job.job_address ? geocoded.get(job.id) : null
        if (!coords) return null
        return (
          <MarkerWithInfoWindow key={job.id} job={job} position={coords} customers={customers} />
        )
      })}
    </>
  )
}

function MobileServicesMapInner({ jobs, date, customers = [] }: Props) {
  const [geocoded, setGeocoded] = useState<Map<string, { lat: number; lng: number }>>(new Map())
  const [loading, setLoading] = useState(true)

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined
  const mobileJobs = jobs.filter((j) => j.job_address)

  const geocodeAll = useCallback(async () => {
    if (!apiKey || mobileJobs.length === 0) {
      setLoading(false)
      return
    }
    const results = new Map<string, { lat: number; lng: number }>()
    for (let i = 0; i < mobileJobs.length; i++) {
      const j = mobileJobs[i]
      const coords = await geocodeWithGoogle(j.job_address!, apiKey)
      if (coords) results.set(j.id, coords)
      if (i < mobileJobs.length - 1) await new Promise((r) => setTimeout(r, 200))
    }
    setGeocoded(results)
    setLoading(false)
  }, [apiKey, mobileJobs])

  useEffect(() => {
    geocodeAll()
  }, [date, mobileJobs.map((j) => `${j.id}:${j.job_address}`).join('|'), geocodeAll])

  if (mobileJobs.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
        <p style={{ color: 'var(--cafe-text-muted)' }}>No mobile jobs with addresses for this date.</p>
        <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Add job addresses to see them on the map.
        </p>
      </div>
    )
  }

  if (!apiKey) {
    return (
      <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
        <p style={{ color: 'var(--cafe-text-muted)' }}>Google Maps API key not configured.</p>
        <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Set VITE_GOOGLE_MAPS_API_KEY in your environment to display the map.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {loading && (
        <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Geocoding addresses…
        </p>
      )}
      <div className="h-[400px] rounded-lg border overflow-hidden" style={{ borderColor: 'var(--cafe-border)' }}>
        <APIProvider apiKey={apiKey}>
          <GoogleMap
            defaultCenter={MELBOURNE_CENTRE}
            defaultZoom={11}
            gestureHandling="greedy"
            style={{ width: '100%', height: '100%' }}
          >
            <MapContent jobs={mobileJobs} customers={customers} geocoded={geocoded} />
          </GoogleMap>
        </APIProvider>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
          Jobs on map:
        </span>
        {mobileJobs.map((j, i) => (
          <span key={j.id} className="text-sm">
            <a
              href={`/auto-key/${j.id}`}
              className="px-3 py-1.5 rounded inline-block"
              style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }}
            >
              {i + 1}. #{j.job_number} · {j.title}
            </a>
          </span>
        ))}
      </div>
    </div>
  )
}

export default function MobileServicesMap(props: Props) {
  return <MobileServicesMapInner {...props} />
}
