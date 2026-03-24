import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { APIProvider, Map as GoogleMap, Marker, InfoWindow, useMarkerRef, useMap } from '@vis.gl/react-google-maps'
import { STATUS_LABELS } from '@/lib/utils'

const MELBOURNE_CENTRE = { lat: -37.8136, lng: 144.9631 }

interface Customer {
  id: string
  full_name: string
  address?: string
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
  /** Shown above the map (e.g. selected date range) */
  rangeLabel?: string
}

const GEOCODE_CACHE_KEY = 'geocode_cache'

function loadGeocodeCache(): Map<string, { lat: number; lng: number }> {
  try {
    const raw = sessionStorage.getItem(GEOCODE_CACHE_KEY)
    if (!raw) return new Map()
    const parsed = JSON.parse(raw) as { key: string; lat: number; lng: number }[]
    if (!Array.isArray(parsed)) return new Map()
    const map = new Map<string, { lat: number; lng: number }>()
    for (const { key, lat, lng } of parsed) {
      if (typeof key === 'string' && typeof lat === 'number' && typeof lng === 'number') {
        map.set(key, { lat, lng })
      }
    }
    return map
  } catch {
    return new Map()
  }
}

function saveGeocodeCache(map: Map<string, { lat: number; lng: number }>) {
  try {
    const entries = Array.from(map.entries(), ([key, coords]) => ({ key, ...coords }))
    sessionStorage.setItem(GEOCODE_CACHE_KEY, JSON.stringify(entries))
  } catch {
    // ignore
  }
}

const geocodeCache = loadGeocodeCache()

async function geocodeWithGoogle(address: string, apiKey: string): Promise<{ lat: number; lng: number } | null> {
  const cacheKey = address.trim().toLowerCase()
  const cached = geocodeCache.get(cacheKey)
  if (cached) return cached
  try {
    const res = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(address)}&region=au&key=${apiKey}`
    )
    const data = await res.json()
    if (data?.status === 'OK' && data?.results?.[0]?.geometry?.location) {
      const loc = data.results[0].geometry.location
      const coords = { lat: loc.lat, lng: loc.lng }
      geocodeCache.set(cacheKey, coords)
      saveGeocodeCache(geocodeCache)
      return coords
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
  displayAddress,
}: {
  job: Job
  position: { lat: number; lng: number }
  customers: Customer[]
  displayAddress: string
}) {
  const [markerRef, marker] = useMarkerRef()
  const [infoWindowShown, setInfoWindowShown] = useState(false)
  const handleMarkerClick = useCallback(() => setInfoWindowShown((s) => !s), [])
  const handleClose = useCallback(() => setInfoWindowShown(false), [])

  const labelText = job.job_number || job.title || '?'
  return (
    <>
      <Marker
        ref={markerRef}
        position={position}
        label={{
          text: labelText,
          color: '#2C1810',
          fontSize: '14px',
          fontWeight: 'bold',
        }}
        onClick={handleMarkerClick}
      />
      {infoWindowShown && marker && (
        <InfoWindow anchor={marker} onClose={handleClose} disableAutoPan shouldFocus={false}>
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
              {displayAddress}
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
        const coords = geocoded.get(job.id)
        const displayAddress = (job as { _addressForMap?: string })._addressForMap ?? job.job_address ?? ''
        if (!coords) return null
        return (
          <MarkerWithInfoWindow key={job.id} job={job} position={coords} customers={customers} displayAddress={displayAddress} />
        )
      })}
    </>
  )
}

function MobileServicesMapInner({ jobs, date, customers = [], rangeLabel }: Props) {
  const [geocoded, setGeocoded] = useState<Map<string, { lat: number; lng: number }>>(new Map())
  const [loading, setLoading] = useState(true)
  const abortedRef = useRef(false)

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined
  const mobileJobs = useMemo(() => {
    return jobs
      .map((j) => {
        const address = j.job_address?.trim() || (customers.find((c) => c.id === j.customer_id)?.address?.trim())
        return address ? { ...j, _addressForMap: address } : null
      })
      .filter((j): j is NonNullable<typeof j> => !!j)
  }, [jobs, customers])
  const jobsKey = useMemo(
    () => mobileJobs.map((j) => `${j.id}:${j._addressForMap}`).sort().join('|'),
    [mobileJobs]
  )

  const lastJobsKeyRef = useRef<string | null>(null)

  useEffect(() => {
    abortedRef.current = false
    if (!apiKey || mobileJobs.length === 0) {
      setLoading(false)
      return
    }
    // Skip if we already completed for this exact jobsKey (prevents duplicate runs from parent re-renders)
    if (lastJobsKeyRef.current === jobsKey) {
      setLoading(false)
      return
    }
    const run = async () => {
      const results = new Map<string, { lat: number; lng: number }>()
      // Fast path: if all addresses are cached, resolve synchronously (0 API calls)
      const cacheKeys = mobileJobs.map((j) => j._addressForMap.trim().toLowerCase())
      const allCached = cacheKeys.every((ck) => geocodeCache.has(ck))
      if (allCached) {
        for (const j of mobileJobs) {
          const ck = j._addressForMap.trim().toLowerCase()
          const c = geocodeCache.get(ck)
          if (c) results.set(j.id, c)
        }
        lastJobsKeyRef.current = jobsKey
        setGeocoded(results)
        setLoading(false)
        return
      }
      for (let i = 0; i < mobileJobs.length; i++) {
        if (abortedRef.current) return
        const j = mobileJobs[i]
        const coords = await geocodeWithGoogle(j._addressForMap, apiKey)
        if (abortedRef.current) return
        if (coords) results.set(j.id, coords)
        if (i < mobileJobs.length - 1) await new Promise((r) => setTimeout(r, 200))
      }
      if (!abortedRef.current) {
        lastJobsKeyRef.current = jobsKey
        setGeocoded(results)
        setLoading(false)
      }
    }
    setLoading(true)
    run()
    return () => { abortedRef.current = true }
  }, [apiKey, date, jobsKey])

  if (mobileJobs.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
        <p style={{ color: 'var(--cafe-text-muted)' }}>No jobs with addresses for this date.</p>
        <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Add job addresses (or customer addresses) to see them on the map.
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
      {rangeLabel && (
        <p className="text-sm font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
          {rangeLabel}
        </p>
      )}
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
