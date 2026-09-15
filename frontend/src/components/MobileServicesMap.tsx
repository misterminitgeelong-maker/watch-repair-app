import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import {
  APIProvider,
  APILoadingStatus,
  Map as GoogleMap,
  Marker,
  InfoWindow,
  useApiLoadingStatus,
  useMap as useGoogleMap,
  useMapsLibrary,
  useMarkerRef,
} from '@vis.gl/react-google-maps'
import L from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Marker as LeafletMarker, Popup, Polyline, useMap as useLeafletMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { MOBILE_JOB_TYPES } from '@/lib/autoKeyJobTypes'
import { getApiErrorMessage, optimizeDrivingRoute } from '@/lib/api'
import { asyncPool } from '@/lib/asyncPool'
import {
  approximateMelbourneCoords,
  cacheGeocode,
  countApproximatedPins,
  loadGeocodeCache,
  realMapCoords,
  saveGeocodeCache,
  type MapPinCoords,
} from '@/lib/geocodeCache'
import { nearestNeighborOrder } from '@/lib/mobileRouteUtils'
import { STATUS_LABELS } from '@/lib/utils'

const MELBOURNE_CENTRE = { lat: -37.8136, lng: 144.9631 }
const GEOCODE_CONCURRENCY = 5

const APPROX_PIN_ICON =
  'data:image/svg+xml;charset=UTF-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><circle cx="16" cy="16" r="12" fill="#F4E6C3" stroke="#6A4A10" stroke-width="2" stroke-dasharray="3 2"/><text x="16" y="21" text-anchor="middle" font-size="16" font-family="sans-serif" fill="#6A4A10">?</text></svg>',
  )

function approxLeafletIcon(): L.DivIcon {
  return L.divIcon({
    className: 'ms-approx-pin',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: '<div style="width:28px;height:28px;border-radius:50%;border:2px dashed #6A4A10;background:#F4E6C3;color:#6A4A10;font:700 14px/28px sans-serif;text-align:center">?</div>',
  })
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
  job_address?: string | null
  job_type?: string | null
  scheduled_at?: string | null
  vehicle_make?: string | null
  vehicle_model?: string | null
  vehicle_year?: number | null
  registration_plate?: string | null
  status: string
  customer_id: string
}

interface Props {
  jobs: Job[]
  date: string
  customers?: Customer[]
  /** Shown above the map (e.g. selected date range) */
  rangeLabel?: string
  /**
   * When provided, an "Apply to schedule" action appears whenever the current
   * route is a suggested order (optimized/driving). Receives the job ids in the
   * proposed visit order so the caller can persist `visit_order`.
   */
  onApplyVisitOrder?: (orderedJobIds: string[]) => void
  applyVisitOrderPending?: boolean
}

type JobWithAddr = Job & { _addressForMap: string }

const geocodeCache = loadGeocodeCache()

/** Geocode with Maps JavaScript API (same key/referrer rules as the map; avoids REST Geocoding restrictions). */
function geocodeAddressWithJsApi(
  geocoder: google.maps.Geocoder,
  address: string,
): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    geocoder.geocode({ address, region: 'au' }, (results, status) => {
      if (status === google.maps.GeocoderStatus.OK && results?.[0]?.geometry?.location) {
        const l = results[0].geometry.location
        resolve({ lat: l.lat(), lng: l.lng() })
        return
      }
      resolve(null)
    })
  })
}

/**
 * Runs inside APIProvider — uses JS Geocoder + session cache. On API auth failure or load error, falls back to approximate coords.
 */
function GoogleMapsJsGeocodeEffect({
  jobsKey,
  filteredJobsRef,
  setGeocoded,
  setLoading,
}: {
  jobsKey: string
  filteredJobsRef: MutableRefObject<JobWithAddr[]>
  setGeocoded: Dispatch<SetStateAction<Map<string, MapPinCoords>>>
  setLoading: Dispatch<SetStateAction<boolean>>
}) {
  const apiStatus = useApiLoadingStatus()
  const geocodeGenRef = useRef(0)
  const geocodingLib = useMapsLibrary('geocoding')
  const geocoder = useMemo(() => (geocodingLib ? new geocodingLib.Geocoder() : null), [geocodingLib])

  useEffect(() => {
    const gen = ++geocodeGenRef.current
    const isStale = () => gen !== geocodeGenRef.current

    const setApproxForSnapshot = (snapshot: JobWithAddr[]) => {
      if (snapshot.length === 0) {
        if (!isStale()) {
          setGeocoded(new Map())
          setLoading(false)
        }
        return
      }
      const results = new Map<string, MapPinCoords>()
      for (const j of snapshot) {
        const approx = approximateMelbourneCoords(j._addressForMap)
        results.set(j.id, { ...approx, approximated: true })
      }
      if (!isStale()) {
        setGeocoded(results)
        setLoading(false)
      }
    }

    const snapshot = filteredJobsRef.current

    if (apiStatus === APILoadingStatus.FAILED || apiStatus === APILoadingStatus.AUTH_FAILURE) {
      setApproxForSnapshot(snapshot)
      return () => {
        geocodeGenRef.current += 1
      }
    }

    if (apiStatus !== APILoadingStatus.LOADED || !geocoder) {
      return () => {
        geocodeGenRef.current += 1
      }
    }

    const run = async () => {
      if (snapshot.length === 0) {
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

      const results = new Map<string, MapPinCoords>()
      await asyncPool(snapshot, GEOCODE_CONCURRENCY, async (j) => {
        if (isStale()) return
        const ck = j._addressForMap.trim().toLowerCase()
        const cached = geocodeCache.get(ck)
        let coords = cached ? { lat: cached.lat, lng: cached.lng } : null
        if (!coords) {
          coords = await geocodeAddressWithJsApi(geocoder, j._addressForMap)
          if (coords) cacheGeocode(geocodeCache, ck, coords.lat, coords.lng)
        }
        if (isStale()) return
        if (coords) {
          results.set(j.id, { ...coords, approximated: false })
        } else {
          results.set(j.id, { ...approximateMelbourneCoords(j._addressForMap), approximated: true })
        }
      })
      saveGeocodeCache(geocodeCache)
      if (!isStale()) {
        setGeocoded(results)
        setLoading(false)
      } else {
        setLoading(false)
      }
    }

    void run()
    return () => {
      geocodeGenRef.current += 1
    }
  }, [apiStatus, geocoder, jobsKey, setGeocoded, setLoading])

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
  approximated,
}: {
  job: Job
  position: { lat: number; lng: number }
  customers: Customer[]
  displayAddress: string
  stopNumber: number
  approximated: boolean
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
        icon={approximated ? APPROX_PIN_ICON : undefined}
        label={
          approximated
            ? undefined
            : {
                text: labelText,
                color: '#2C1810',
                fontSize: '13px',
                fontWeight: 'bold',
              }
        }
        title={approximated ? `Approximate position · #${job.job_number}` : labelText}
        onClick={handleMarkerClick}
      />
      {infoWindowShown && marker && (
        <InfoWindow anchor={marker} onClose={handleClose} disableAutoPan shouldFocus={false}>
          <div className="min-w-[200px] text-sm" style={{ color: 'var(--ms-text)' }}>
            <p className="font-semibold" style={{ color: 'var(--ms-accent)' }}>
              Stop {stopNumber} · #{job.job_number}
            </p>
            <p className="mt-1 font-medium">{vehicleLabel(job)}</p>
            <p className="mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
              {customerName(customers, job.customer_id)}
            </p>
            <p className="mt-0.5">
              <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: '#EEE8E3', color: 'var(--ms-text-mid)' }}>
                {STATUS_LABELS[job.status] ?? job.status.replace(/_/g, ' ')}
              </span>
            </p>
            <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              {approximated ? 'Approximate position (not geocoded). ' : ''}
              {displayAddress}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <a
                href={`/auto-key/${job.id}`}
                className="inline-block text-xs font-semibold hover:underline"
                style={{ color: 'var(--ms-accent)' }}
                onClick={(e) => e.stopPropagation()}
              >
                View job →
              </a>
              {displayAddress && (
                <a
                  href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(displayAddress)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-xs font-semibold hover:underline"
                  style={{ color: 'var(--ms-accent)' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  Get directions →
                </a>
              )}
            </div>
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
  geocoded: Map<string, MapPinCoords>
  routePath: google.maps.LatLngLiteral[]
}) {
  const map = useGoogleMap()

  useEffect(() => {
    if (!map || geocoded.size === 0) return
    const all = Array.from(geocoded.values())
    const real = all.filter((c) => !c.approximated)
    const coords = real.length > 0 ? real : all
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
            approximated={coords.approximated}
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
  geocoded: Map<string, MapPinCoords>
  routePath: google.maps.LatLngLiteral[]
}) {
  const pinPositions = useMemo(
    () =>
      orderedJobs
        .map((j) => geocoded.get(j.id))
        .filter((c): c is MapPinCoords => Boolean(c))
        .map((c) => [c.lat, c.lng] as [number, number]),
    [orderedJobs, geocoded],
  )
  const linePositions = useMemo(
    () => routePath.map((p) => [p.lat, p.lng] as [number, number]),
    [routePath],
  )
  const approxIcon = useMemo(() => approxLeafletIcon(), [])
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
      <LeafletFitBounds positions={pinPositions.length > 0 ? pinPositions : [[MELBOURNE_CENTRE.lat, MELBOURNE_CENTRE.lng]]} />
      {linePositions.length >= 2 && (
        <Polyline positions={linePositions} pathOptions={{ color: '#C9772A', weight: 3, opacity: 0.88 }} />
      )}
      {orderedJobs.map((job, idx) => {
        const coords = geocoded.get(job.id)
        if (!coords) return null
        const displayAddress = job._addressForMap ?? job.job_address ?? ''
        if (coords.approximated) {
          return (
            <LeafletMarker key={job.id} position={[coords.lat, coords.lng]} icon={approxIcon}>
              <Popup>
                <div className="min-w-[200px] text-sm" style={{ color: '#2C1810' }}>
                  <p className="font-semibold" style={{ color: '#6A4A10' }}>
                    Approximate · #{job.job_number}
                  </p>
                  <p className="mt-1 font-medium">{vehicleLabel(job)}</p>
                  <p className="mt-0.5 text-xs" style={{ color: '#5c4a3a' }}>
                    {customerName(customers, job.customer_id)}
                  </p>
                  <p className="mt-1 text-xs" style={{ color: '#6b5b4a' }}>
                    Position is hashed, not geocoded. {displayAddress}
                  </p>
                  <div className="mt-2 flex items-center gap-3">
                    <a href={`/auto-key/${job.id}`} className="inline-block text-xs font-semibold" style={{ color: '#B8860B' }}>
                      View job →
                    </a>
                    {displayAddress && (
                      <a
                        href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(displayAddress)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-block text-xs font-semibold"
                        style={{ color: '#B8860B' }}
                      >
                        Get directions →
                      </a>
                    )}
                  </div>
                </div>
              </Popup>
            </LeafletMarker>
          )
        }
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
                <div className="mt-2 flex items-center gap-3">
                  <a href={`/auto-key/${job.id}`} className="inline-block text-xs font-semibold" style={{ color: '#B8860B' }}>
                    View job →
                  </a>
                  {displayAddress && (
                    <a
                      href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(displayAddress)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block text-xs font-semibold"
                      style={{ color: '#B8860B' }}
                    >
                      Get directions →
                    </a>
                  )}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}

function MobileServicesMapInner({ jobs, customers = [], rangeLabel, onApplyVisitOrder, applyVisitOrderPending }: Props) {
  const [geocoded, setGeocoded] = useState<Map<string, MapPinCoords>>(new Map())
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
      (j) => realMapCoords(geocoded.get(j.id)),
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
      if (c && !c.approximated) pts.push(c)
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

  const approximatedCount = useMemo(() => countApproximatedPins(geocoded.values()), [geocoded])
  const allStopsReal =
    sortedBySchedule.length > 0 && sortedBySchedule.every((j) => realMapCoords(geocoded.get(j.id)))
  const canOptimize = sortedBySchedule.length >= 2 && allStopsReal && approximatedCount === 0

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
    if (!sortedBySchedule.every((j) => realMapCoords(geocoded.get(j.id)))) return

    const stops = sortedBySchedule.map((j) => realMapCoords(geocoded.get(j.id))!)
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

  /** OpenStreetMap / no-key path only; with `VITE_GOOGLE_MAPS_API_KEY`, geocoding runs in `GoogleMapsJsGeocodeEffect` inside `APIProvider`. */
  useEffect(() => {
    if (apiKey?.trim()) return

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

      const results = new Map<string, MapPinCoords>()
      for (const j of filteredJobsSnapshot) {
        results.set(j.id, { ...approximateMelbourneCoords(j._addressForMap), approximated: true })
      }
      if (isStale()) {
        setLoading(false)
        return
      }
      setGeocoded(results)
      setLoading(false)
    }
    void run()
    return () => {
      geocodeGenerationRef.current += 1
    }
  }, [apiKey, jobsKey])

  if (jobsWithAddresses.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}>
        <p style={{ color: 'var(--ms-text-muted)' }}>No jobs with addresses in this range.</p>
        <p className="mt-2 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Add job or customer addresses to see them on the map.
        </p>
      </div>
    )
  }

  if (mapFilter === 'mobile_visits' && filteredJobs.length === 0) {
    return (
      <div className="space-y-4">
        {rangeLabel && (
          <p className="text-sm font-medium" style={{ color: 'var(--ms-text-muted)' }}>
            {rangeLabel}
          </p>
        )}
        <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}>
          <p style={{ color: 'var(--ms-text-muted)' }}>No on-site / mobile visits with addresses for this range.</p>
          <p className="mt-2 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            Mobile visit job types include lockouts, roadside, all keys lost, ignition work, and similar. In-shop jobs are hidden unless you widen the filter.
          </p>
          <button
            type="button"
            className="mt-4 px-4 py-2 rounded-lg text-sm font-medium touch-manipulation"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#2C1810' }}
            onClick={() => setMapFilter('all_addresses')}
          >
            Show all jobs with addresses
          </button>
        </div>
      </div>
    )
  }

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
        <p className="text-sm font-medium" style={{ color: 'var(--ms-text-muted)' }}>
          {rangeLabel}
        </p>
      )}
      {!useGoogleTiles && (
        <p className="text-xs rounded-lg border px-3 py-2" style={{ backgroundColor: '#F7F0E6', borderColor: 'var(--ms-border)', color: 'var(--ms-text-mid)' }}>
          OpenStreetMap with approximate pin positions (works without a browser key). Set{' '}
          <span className="font-mono text-[11px]">VITE_GOOGLE_MAPS_API_KEY</span> at <strong>build time</strong> (e.g. Docker/Railway build args) for Google Maps and JavaScript geocoding.
        </p>
      )}
      {approximatedCount > 0 && (
        <p className="text-xs rounded-lg border px-3 py-2" style={{ backgroundColor: '#F7F0E6', borderColor: 'var(--ms-border)', color: 'var(--ms-text-mid)' }}>
          {approximatedCount} pin{approximatedCount === 1 ? ' is' : 's are'} approximate (not geocoded) and{' '}
          {approximatedCount === 1 ? 'is' : 'are'} shown as a dashed “?” marker. Optimized and Driving stay off until those addresses geocode.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>Show</span>
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <button
            type="button"
            onClick={() => setMapFilter('mobile_visits')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
            style={{
              backgroundColor: mapFilter === 'mobile_visits' ? 'var(--ms-surface)' : 'transparent',
              color: mapFilter === 'mobile_visits' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
            }}
          >
            Mobile visits
          </button>
          <button
            type="button"
            onClick={() => setMapFilter('all_addresses')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
            style={{
              backgroundColor: mapFilter === 'all_addresses' ? 'var(--ms-surface)' : 'transparent',
              color: mapFilter === 'all_addresses' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
            }}
          >
            All with address
          </button>
        </div>
        <span className="text-xs font-semibold uppercase tracking-wide ml-1" style={{ color: 'var(--ms-text-muted)' }}>Route</span>
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <button
            type="button"
            onClick={() => setRouteOrder('scheduled')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation"
            style={{
              backgroundColor: routeOrder === 'scheduled' ? 'var(--ms-surface)' : 'transparent',
              color: routeOrder === 'scheduled' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
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
              backgroundColor: routeOrder === 'optimized' ? 'var(--ms-surface)' : 'transparent',
              color: routeOrder === 'optimized' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
            }}
            title={
              !canOptimize
                ? approximatedCount > 0
                  ? `${approximatedCount} pin${approximatedCount === 1 ? ' is' : 's are'} approximate and excluded from optimisation.`
                  : 'Geocode all stops first (wait for loading to finish).'
                : 'Reorder by nearest-neighbor from the first scheduled stop'
            }
          >
            Optimized
          </button>
          <button
            type="button"
            disabled={!allStopsReal || loading}
            onClick={() => setRouteOrder('driving')}
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition touch-manipulation disabled:opacity-45"
            style={{
              backgroundColor: routeOrder === 'driving' ? 'var(--ms-surface)' : 'transparent',
              color: routeOrder === 'driving' ? 'var(--ms-text)' : 'var(--ms-text-muted)',
            }}
            title={
              !allStopsReal
                ? approximatedCount > 0
                  ? `${approximatedCount} pin${approximatedCount === 1 ? ' is' : 's are'} approximate — cannot compute a driving order from hashed locations.`
                  : 'Geocode every stop first.'
                : 'Shortest driving order via Google (first & last appointment fixed). Requires server GOOGLE_MAPS_WEB_SERVICES_KEY.'
            }
          >
            Driving
          </button>
        </div>
        {orderedJobs.length >= 1 && (
          <a
            href={mapsDirUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold hover:underline touch-manipulation"
            style={{ color: 'var(--ms-accent)' }}
          >
            {orderedJobs.length === 1 ? 'Open directions in Google Maps →' : 'Open route in Google Maps →'}
          </a>
        )}
      </div>
      {routeOrder === 'optimized' && canOptimize && (
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Line shows a straight path between stops (not driving directions). Use Open in Google Maps for turn-by-turn.
        </p>
      )}
      {routeOrder === 'driving' && allStopsReal && sortedBySchedule.length >= 3 && (
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          First and last stops stay in appointment order; Google reorders the middle for driving distance. Map line is still straight between stops; use Open in Google Maps for roads.
        </p>
      )}
      {routeOrder === 'driving' && drivingLoading && (
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Computing driving order…
        </p>
      )}
      {routeOrder === 'driving' && drivingErr && (
        <p className="text-sm" style={{ color: 'var(--ms-error)' }}>
          {drivingErr}
        </p>
      )}
      {loading && (
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Geocoding addresses…
        </p>
      )}
      {!loading && ungeocodedJobs.length > 0 && (
        <div className="rounded-lg border p-3 text-sm" style={{ borderColor: '#E7C6B7', backgroundColor: '#FFF7F3', color: 'var(--ms-text-mid)' }}>
          <p className="font-medium">
            Could not place {ungeocodedJobs.length} job{ungeocodedJobs.length === 1 ? '' : 's'} on the map.
          </p>
          <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
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
      <div className="h-[min(520px,70vh)] min-h-[320px] rounded-lg border overflow-hidden" style={{ borderColor: 'var(--ms-border)' }}>
        {useGoogleTiles ? (
          <APIProvider apiKey={apiKey!}>
            <GoogleMapsJsGeocodeEffect
              jobsKey={jobsKey}
              filteredJobsRef={filteredJobsRef}
              setGeocoded={setGeocoded}
              setLoading={setLoading}
            />
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
      {onApplyVisitOrder && routeOrder !== 'scheduled' && orderedJobs.length >= 2 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2" style={{ borderColor: 'var(--ms-accent)', backgroundColor: 'var(--ms-accent-light)' }}>
          <span className="text-xs font-medium" style={{ color: 'var(--ms-text-mid)' }}>
            Save this {routeOrder === 'driving' ? 'driving' : 'optimized'} order as the day's visit order?
          </span>
          <button
            type="button"
            disabled={applyVisitOrderPending}
            onClick={() => onApplyVisitOrder(orderedJobs.map((j) => j.id))}
            className="px-3 py-1.5 rounded-md text-xs font-semibold touch-manipulation disabled:opacity-50"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#2C1810' }}
          >
            {applyVisitOrderPending ? 'Applying…' : 'Apply to schedule'}
          </button>
        </div>
      )}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--ms-text-muted)' }}>
          Stops ({routeStopsLegend}):
        </span>
        {orderedJobs.map((j, i) => (
          <span key={j.id} className="text-sm">
            <a
              href={`/auto-key/${j.id}`}
              className="px-3 py-1.5 rounded inline-block"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#2C1810' }}
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
