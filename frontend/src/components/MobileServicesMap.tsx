import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { APIProvider, Map as GoogleMap, Marker, InfoWindow, useMarkerRef, useMap as useGoogleMap } from '@vis.gl/react-google-maps'
import L from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap as useLeafletMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { MOBILE_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import { getApiErrorMessage, optimizeDrivingRoute } from '@/lib/api'
import { nearestNeighborOrder } from '@/lib/mobileRouteUtils'
import { STATUS_LABELS } from '@/lib/utils'

const MELBOURNE_CENTRE = { lat: -37.8136, lng: 144.9631 }

/** Deterministic spread around Melbourne when Google geocoding is unavailable (no API key or API failure). */
function approximateMelbourneCoords(address: string): { lat: number; lng: number } {
  let h = 2166136261
  for (let i = 0; i < address.length; i++) h = Math.imul(h ^ address.charCodeAt(i), 16777619)
  const u = (h >>> 0) / 0xffffffff
  const v = ((h >>> 16) >>> 0) / 0xffff
  return { lat: -37.8136 + (u - 0.5) * 0.14, lng: 144.9631 + (v - 0.5) * 0.2 }
}

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

type JobWithAddr = Job & { _addressForMap: string }

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

function isMobileVisitJob(j: Job): boolean {
  const t = j.job_type?.trim()
  if (!t) return !!j.job_address?.trim()
  return MOBILE_JOB_TYPES.has(t)
}

function attachAddress(j: Job, customers: Customer[]): JobWithAddr | null {
  const address = j.job_address?.trim() || customers.find((c) => c.id === j.customer_id)?.address?.trim()
  if (!address) return null
  return { ...j, _addressForMap: address }
}

function sortJobsBySchedule(jobs: JobWithAddr[]): JobWithAddr[] {
  return [...jobs].sort((a, b) => {
    const ta = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0
    const tb = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0
    if (ta !== tb) return ta - tb
    return a.job_number.localeCompare(b.job_number, undefined, { numeric: true })
  })
}

function buildGoogleMapsDirUrl(addresses: string[]): string {
  if (addresses.length === 0) return 'https://www.google.com/maps'
  const path = addresses.map((a) => encodeURIComponent(a)).join('/')
  return `https://www.google.com/maps/dir/${path}`
}

function isValidPermutation(order: number[], n: number): boolean {
  if (order.length !== n) return false
  if (new Set(order).size !== n) return false
  return order.every((i) => i >= 0 && i < n)
}

function RoutePolyline({ path }: { path: google.maps.LatLngLiteral[] }) {
  const map = useGoogleMap()
  useEffect(() => {
    if (!map || path.length < 2) return
    const poly = new google.maps.Polyline({
      path,
      strokeColor: '#C9772A',
      strokeOpacity: 0.88,
      strokeWeight: 3,
      geodesic: true,
      map,
    })
    return () => poly.setMap(null)
  }, [map, path])
  return null
}

function MarkerWithInfoWindow({
  job,
  position,
  customers,
  displayAddress,
  stopNumber,
}: {
  job: Job
  position: { lat: number; lng: number }
  customers: Customer[]
  displayAddress: string
  stopNumber: number
}) {
  const [markerRef, marker] = useMarkerRef()
  const [infoWindowShown, setInfoWindowShown] = useState(false)
  const handleMarkerClick = useCallback(() => setInfoWindowShown((s) => !s), [])
  const handleClose = useCallback(() => setInfoWindowShown(false), [])

  const labelText = `${stopNumber}. ${job.job_number || job.title || '?'}`
  return (
    <>
      <Marker
        ref={markerRef}
        position={position}
        label={{
          text: labelText,
          color: '#2C1810',
          fontSize: '13px',
          fontWeight: 'bold',
        }}
        onClick={handleMarkerClick}
      />
      {infoWindowShown && marker && (
        <InfoWindow anchor={marker} onClose={handleClose} disableAutoPan shouldFocus={false}>
          <div className="min-w-[200px] text-sm" style={{ color: 'var(--cafe-text)' }}>
            <p className="font-semibold" style={{ color: 'var(--cafe-amber)' }}>
              Stop {stopNumber} · #{job.job_number}
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
  orderedJobs,
  customers,
  geocoded,
  routePath,
}: {
  orderedJobs: JobWithAddr[]
  customers: Customer[]
  geocoded: Map<string, { lat: number; lng: number }>
  routePath: google.maps.LatLngLiteral[]
}) {
  const map = useGoogleMap()

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
      {routePath.length >= 2 && <RoutePolyline path={routePath} />}
      {orderedJobs.map((job, idx) => {
        const coords = geocoded.get(job.id)
        const displayAddress = job._addressForMap ?? job.job_address ?? ''
        if (!coords) return null
        return (
          <MarkerWithInfoWindow
            key={job.id}
            job={job}
            position={coords}
            customers={customers}
            displayAddress={displayAddress}
            stopNumber={idx + 1}
          />
        )
      })}
    </>
  )
}

function LeafletFitBounds({ positions }: { positions: [number, number][] }) {
  const map = useLeafletMap()
  useEffect(() => {
    if (!map || positions.length === 0) return
    if (positions.length === 1) {
      map.setView(positions[0], 13)
    } else {
      map.fitBounds(L.latLngBounds(positions) as L.LatLngBoundsExpression, { padding: [40, 40] })
    }
  }, [map, positions])
  return null
}

function LeafletDispatchMap({
  orderedJobs,
  customers,
  geocoded,
  routePath,
}: {
  orderedJobs: JobWithAddr[]
  customers: Customer[]
  geocoded: Map<string, { lat: number; lng: number }>
  routePath: google.maps.LatLngLiteral[]
}) {
  const positions = useMemo(
    () => routePath.map((p) => [p.lat, p.lng] as [number, number]),
    [routePath],
  )
  return (
    <MapContainer
      center={[MELBOURNE_CENTRE.lat, MELBOURNE_CENTRE.lng]}
      zoom={11}
      style={{ width: '100%', height: '100%' }}
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <LeafletFitBounds positions={positions.length > 0 ? positions : [[MELBOURNE_CENTRE.lat, MELBOURNE_CENTRE.lng]]} />
      {routePath.length >= 2 && (
        <Polyline positions={positions} pathOptions={{ color: '#C9772A', weight: 3, opacity: 0.88 }} />
      )}
      {orderedJobs.map((job, idx) => {
        const coords = geocoded.get(job.id)
        if (!coords) return null
        const displayAddress = job._addressForMap ?? job.job_address ?? ''
        return (
          <CircleMarker
            key={job.id}
            center={[coords.lat, coords.lng]}
            radius={10}
            pathOptions={{ color: '#8D6725', fillColor: '#FFF7EA', fillOpacity: 0.95, weight: 2 }}
          >
            <Popup>
              <div className="min-w-[200px] text-sm" style={{ color: '#2C1810' }}>
                <p className="font-semibold" style={{ color: '#B8860B' }}>
                  Stop {idx + 1} · #{job.job_number}
                </p>
                <p className="mt-1 font-medium">{vehicleLabel(job)}</p>
                <p className="mt-0.5 text-xs" style={{ color: '#5c4a3a' }}>
                  {customerName(customers, job.customer_id)}
                </p>
                <p className="mt-0.5">
                  <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: '#EEE8E3', color: '#4a3d32' }}>
                    {STATUS_LABELS[job.status] ?? job.status.replace(/_/g, ' ')}
                  </span>
                </p>
                <p className="mt-1 text-xs" style={{ color: '#6b5b4a' }}>
                  {displayAddress}
                </p>
                <a href={`/auto-key/${job.id}`} className="mt-2 inline-block text-xs font-semibold" style={{ color: '#B8860B' }}>
                  View job →
                </a>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}

function MobileServicesMapInner({ jobs, date, customers = [], rangeLabel }: Props) {
  const [geocoded, setGeocoded] = useState<Map<string, { lat: number; lng: number }>>(new Map())
  const [loading, setLoading] = useState(true)
  const [mapFilter, setMapFilter] = useState<'mobile_visits' | 'all_addresses'>('mobile_visits')
  const [routeOrder, setRouteOrder] = useState<'scheduled' | 'optimized' | 'driving'>('scheduled')
  const [drivingVisitOrder, setDrivingVisitOrder] = useState<number[] | null>(null)
  const [drivingErr, setDrivingErr] = useState('')
  const [drivingLoading, setDrivingLoading] = useState(false)
  const lastDrivingFetchKey = useRef<string | null>(null)
  /** Bumps on geocode effect cleanup + each run so in-flight async cannot apply stale results. */
  const geocodeGenerationRef = useRef(0)

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined

  const jobsWithAddresses = useMemo(() => {
    return jobs
      .map((j) => attachAddress(j, customers))
      .filter((j): j is JobWithAddr => !!j)
  }, [jobs, customers])

  const filteredJobs = useMemo(() => {
    if (mapFilter === 'all_addresses') return jobsWithAddresses
    return jobsWithAddresses.filter(isMobileVisitJob)
  }, [jobsWithAddresses, mapFilter])

  const jobsKey = useMemo(
    () => filteredJobs.map((j) => `${j.id}:${j._addressForMap}`).sort().join('|'),
    [filteredJobs]
  )

  const sortedBySchedule = useMemo(() => sortJobsBySchedule(filteredJobs), [filteredJobs])

  const optimizedIndices = useMemo(() => {
    if (sortedBySchedule.length === 0) return []
    return nearestNeighborOrder(
      sortedBySchedule,
      (j) => geocoded.get(j.id) ?? null,
      0,
    )
  }, [sortedBySchedule, geocoded])

  const orderedJobs: JobWithAddr[] = useMemo(() => {
    if (sortedBySchedule.length === 0) return []
    if (routeOrder === 'scheduled') return sortedBySchedule
    if (routeOrder === 'optimized') {
      return optimizedIndices.map((i) => sortedBySchedule[i])
    }
    if (
      drivingVisitOrder &&
      isValidPermutation(drivingVisitOrder, sortedBySchedule.length)
    ) {
      return drivingVisitOrder.map((i) => sortedBySchedule[i])
    }
    return sortedBySchedule
  }, [sortedBySchedule, routeOrder, optimizedIndices, drivingVisitOrder])

  const routePath = useMemo(() => {
    const pts: google.maps.LatLngLiteral[] = []
    for (const j of orderedJobs) {
      const c = geocoded.get(j.id)
      if (c) pts.push(c)
    }
    return pts
  }, [orderedJobs, geocoded])

  const mapsDirUrl = useMemo(
    () => buildGoogleMapsDirUrl(orderedJobs.map((j) => j._addressForMap).filter(Boolean)),
    [orderedJobs],
  )

  const ungeocodedJobs = useMemo(
    () => filteredJobs.filter((j) => !geocoded.has(j.id)),
    [filteredJobs, geocoded],
  )

  /** Geocode effect keys off `jobsKey` only; `filteredJobs` gets new array refs without content changes (e.g. customers query). */
  const filteredJobsRef = useRef(filteredJobs)
  filteredJobsRef.current = filteredJobs

  useEffect(() => {
    setRouteOrder('scheduled')
    setDrivingVisitOrder(null)
    setDrivingErr('')
    lastDrivingFetchKey.current = null
  }, [jobsKey])

  useEffect(() => {
    if (routeOrder !== 'driving') {
      lastDrivingFetchKey.current = null
      setDrivingLoading(false)
      return
    }
    if (sortedBySchedule.length === 0) return
    if (!sortedBySchedule.every((j) => geocoded.has(j.id))) return

    const stops = sortedBySchedule.map((j) => geocoded.get(j.id)!)
    const fp = `${jobsKey}|${stops.map((c) => `${c.lat.toFixed(5)},${c.lng.toFixed(5)}`).join(';')}`
    if (lastDrivingFetchKey.current === fp) return
    lastDrivingFetchKey.current = fp

    if (stops.length <= 2) {
      setDrivingVisitOrder(stops.map((_, i) => i))
      setDrivingErr('')
      setDrivingLoading(false)
      return
    }

    let cancelled = false
    setDrivingLoading(true)
    setDrivingErr('')
    optimizeDrivingRoute(stops)
      .then((res) => {
        if (cancelled) return
        const vo = res.data.visit_order
        if (!isValidPermutation(vo, sortedBySchedule.length)) {
          setDrivingErr('Unexpected route response from server.')
          setDrivingVisitOrder(null)
          lastDrivingFetchKey.current = null
        } else {
          setDrivingVisitOrder(vo)
        }
        setDrivingLoading(false)
      })
      .catch((e) => {
        if (cancelled) return
        lastDrivingFetchKey.current = null
        setDrivingErr(getApiErrorMessage(e, 'Could not compute driving route.'))
        setDrivingVisitOrder(null)
        setDrivingLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [routeOrder, jobsKey, sortedBySchedule, geocoded])

  useEffect(() => {
    const gen = ++geocodeGenerationRef.current
    const isStale = () => gen !== geocodeGenerationRef.current
    const filteredJobsSnapshot = filteredJobsRef.current

    const run = async () => {
      if (filteredJobsSnapshot.length === 0) {
        if (!isStale()) {
          setGeocoded(new Map())
          setLoading(false)
        }
        return
      }

      setLoading(true)

      if (isStale()) {
        setLoading(false)
        return
      }

      const results = new Map<string, { lat: number; lng: number }>()
      const useGoogle = Boolean(apiKey?.trim())
      const fallbackFor = (addr: string) => approximateMelbourneCoords(addr)

      if (!useGoogle) {
        for (const j of filteredJobsSnapshot) {
          results.set(j.id, fallbackFor(j._addressForMap))
        }
        if (isStale()) {
          setLoading(false)
          return
        }
        setGeocoded(results)
        setLoading(false)
        return
      }

      const cacheKeys = filteredJobsSnapshot.map((j) => j._addressForMap.trim().toLowerCase())
      const allCached = cacheKeys.every((ck) => geocodeCache.has(ck))
      if (allCached) {
        for (const j of filteredJobsSnapshot) {
          const ck = j._addressForMap.trim().toLowerCase()
          const c = geocodeCache.get(ck)
          results.set(j.id, c ?? fallbackFor(j._addressForMap))
        }
        if (isStale()) {
          setLoading(false)
          return
        }
        setGeocoded(results)
        setLoading(false)
        return
      }
      for (let i = 0; i < filteredJobsSnapshot.length; i++) {
        if (isStale()) {
          setLoading(false)
          return
        }
        const j = filteredJobsSnapshot[i]
        const coords = await geocodeWithGoogle(j._addressForMap, apiKey!)
        if (isStale()) {
          setLoading(false)
          return
        }
        results.set(j.id, coords ?? fallbackFor(j._addressForMap))
        if (i < filteredJobsSnapshot.length - 1) await new Promise((r) => setTimeout(r, 200))
      }
      if (!isStale()) {
        setGeocoded(results)
        setLoading(false)
      } else {
        setLoading(false)
      }
    }
    void run()
    return () => {
      geocodeGenerationRef.current += 1
    }
  }, [apiKey, jobsKey])

  if (jobsWithAddresses.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
        <p style={{ color: 'var(--cafe-text-muted)' }}>No jobs with addresses in this range.</p>
        <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Add job or customer addresses to see them on the map.
        </p>
      </div>
    )
  }

  if (mapFilter === 'mobile_visits' && filteredJobs.length === 0) {
    return (
      <div className="space-y-4">
        {rangeLabel && (
          <p className="text-sm font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
            {rangeLabel}
          </p>
        )}
        <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
          <p style={{ color: 'var(--cafe-text-muted)' }}>No on-site / mobile visits with addresses for this range.</p>
          <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
            Mobile visit job types include lockouts, roadside, all keys lost, ignition work, and similar. In-shop jobs are hidden unless you widen the filter.
          </p>
          <button
            type="button"
            className="mt-4 px-4 py-2 rounded-lg text-sm font-medium touch-manipulation"
            style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }}
            onClick={() => setMapFilter('all_addresses')}
          >
            Show all jobs with addresses
          </button>
        </div>
      </div>
    )
  }

  const allStopsGeocoded =
    sortedBySchedule.length > 0 && sortedBySchedule.every((j) => geocoded.has(j.id))
  const canOptimize = sortedBySchedule.length >= 2 && allStopsGeocoded

  const routeStopsLegend =
    routeOrder === 'scheduled'
      ? 'by appointment time'
      : routeOrder === 'optimized'
        ? 'optimized (straight-line)'
        : drivingLoading
          ? 'driving (loading…)'
          : drivingErr
            ? 'by time (driving unavailable)'
            : 'driving (Google Directions)'

  const useGoogleTiles = Boolean(apiKey?.trim())

  return (
    <div className="space-y-3">
      {rangeLabel && (
        <p className="text-sm font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
          {rangeLabel}
        </p>
      )}
      {!useGoogleTiles && (
        <p className="text-xs rounded-lg border px-3 py-2" style={{ backgroundColor: '#F7F0E6', borderColor: 'var(--cafe-border)', color: 'var(--cafe-text-mid)' }}>
          OpenStreetMap with approximate pin positions (works without a browser key). Set{' '}
          <span className="font-mono text-[11px]">VITE_GOOGLE_MAPS_API_KEY</span> for Google Maps and accurate geocoding.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Show</span>
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <button
            type="button"
            onClick={() => setMapFilter('mobile_visits')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
            style={{
              backgroundColor: mapFilter === 'mobile_visits' ? 'var(--cafe-paper)' : 'transparent',
              color: mapFilter === 'mobile_visits' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
          >
            Mobile visits
          </button>
          <button
            type="button"
            onClick={() => setMapFilter('all_addresses')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
            style={{
              backgroundColor: mapFilter === 'all_addresses' ? 'var(--cafe-paper)' : 'transparent',
              color: mapFilter === 'all_addresses' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
          >
            All with address
          </button>
        </div>
        <span className="text-xs font-semibold uppercase tracking-wide ml-1" style={{ color: 'var(--cafe-text-muted)' }}>Route</span>
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <button
            type="button"
            onClick={() => setRouteOrder('scheduled')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
            style={{
              backgroundColor: routeOrder === 'scheduled' ? 'var(--cafe-paper)' : 'transparent',
              color: routeOrder === 'scheduled' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
          >
            By time
          </button>
          <button
            type="button"
            disabled={!canOptimize || loading}
            onClick={() => setRouteOrder('optimized')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation disabled:opacity-45"
            style={{
              backgroundColor: routeOrder === 'optimized' ? 'var(--cafe-paper)' : 'transparent',
              color: routeOrder === 'optimized' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
            title={!canOptimize ? 'Geocode all stops first (wait for loading to finish).' : 'Reorder by nearest-neighbor from the first scheduled stop'}
          >
            Optimized
          </button>
          <button
            type="button"
            disabled={!allStopsGeocoded || loading}
            onClick={() => setRouteOrder('driving')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation disabled:opacity-45"
            style={{
              backgroundColor: routeOrder === 'driving' ? 'var(--cafe-paper)' : 'transparent',
              color: routeOrder === 'driving' ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
            }}
            title={
              !allStopsGeocoded
                ? 'Geocode every stop first.'
                : 'Shortest driving order via Google (first & last appointment fixed). Requires server GOOGLE_MAPS_WEB_SERVICES_KEY.'
            }
          >
            Driving
          </button>
        </div>
        {orderedJobs.length >= 2 && (
          <a
            href={mapsDirUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold hover:underline touch-manipulation"
            style={{ color: 'var(--cafe-amber)' }}
          >
            Open in Google Maps →
          </a>
        )}
      </div>
      {routeOrder === 'optimized' && canOptimize && (
        <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          Line shows a straight path between stops (not driving directions). Use Open in Google Maps for turn-by-turn.
        </p>
      )}
      {routeOrder === 'driving' && allStopsGeocoded && sortedBySchedule.length >= 3 && (
        <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          First and last stops stay in appointment order; Google reorders the middle for driving distance. Map line is still straight between stops; use Open in Google Maps for roads.
        </p>
      )}
      {routeOrder === 'driving' && drivingLoading && (
        <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Computing driving order…
        </p>
      )}
      {routeOrder === 'driving' && drivingErr && (
        <p className="text-sm" style={{ color: '#C96A5A' }}>
          {drivingErr}
        </p>
      )}
      {loading && (
        <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
          Geocoding addresses…
        </p>
      )}
      {!loading && ungeocodedJobs.length > 0 && (
        <div className="rounded-lg border p-3 text-sm" style={{ borderColor: '#E7C6B7', backgroundColor: '#FFF7F3', color: 'var(--cafe-text-mid)' }}>
          <p className="font-medium">
            Could not place {ungeocodedJobs.length} job{ungeocodedJobs.length === 1 ? '' : 's'} on the map.
          </p>
          <p className="mt-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
            You can still open directions from these jobs:
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {ungeocodedJobs.slice(0, 8).map((j) => (
              <a
                key={j.id}
                href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(j._addressForMap)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-2 py-1 rounded text-xs font-medium"
                style={{ backgroundColor: '#F8EBDD', color: '#6A3D21' }}
              >
                #{j.job_number}
              </a>
            ))}
          </div>
        </div>
      )}
      <div className="h-[min(520px,70vh)] min-h-[320px] rounded-lg border overflow-hidden" style={{ borderColor: 'var(--cafe-border)' }}>
        {useGoogleTiles ? (
          <APIProvider apiKey={apiKey!}>
            <GoogleMap
              defaultCenter={MELBOURNE_CENTRE}
              defaultZoom={11}
              gestureHandling="greedy"
              style={{ width: '100%', height: '100%' }}
            >
              <MapContent orderedJobs={orderedJobs} customers={customers} geocoded={geocoded} routePath={routePath} />
            </GoogleMap>
          </APIProvider>
        ) : (
          <LeafletDispatchMap orderedJobs={orderedJobs} customers={customers} geocoded={geocoded} routePath={routePath} />
        )}
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
          Stops ({routeStopsLegend}):
        </span>
        {orderedJobs.map((j, i) => (
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
