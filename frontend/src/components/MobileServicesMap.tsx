import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

interface Job {
  id: string
  job_number: string
  title: string
  job_address?: string
  scheduled_at?: string
}

interface Props {
  jobs: Job[]
  date: string
}

async function geocode(address: string, country = 'Australia'): Promise<[number, number] | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&countrycodes=au&limit=1`,
      { headers: { 'User-Agent': 'Mainspring/1.0' } }
    )
    const data = await res.json()
    if (data?.[0]?.lat && data?.[0]?.lon) {
      return [parseFloat(data[0].lat), parseFloat(data[0].lon)]
    }
  } catch {
    // ignore
  }
  return null
}

export default function MobileServicesMap({ jobs, date }: Props) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<L.Map | null>(null)
  const markersRef = useRef<L.Marker[]>([])
  const [geocoded, setGeocoded] = useState<Map<string, [number, number]>>(new Map())
  const [loading, setLoading] = useState(true)

  const mobileJobs = jobs.filter((j) => j.job_type === 'mobile' && j.job_address)

  useEffect(() => {
    const geocodeAll = async () => {
      const results = new Map<string, [number, number]>()
      for (let i = 0; i < mobileJobs.length; i++) {
        const j = mobileJobs[i]
        const coords = await geocode(j.job_address!)
        if (coords) results.set(j.id, coords)
        if (i < mobileJobs.length - 1) await new Promise((r) => setTimeout(r, 1100))
      }
      setGeocoded(results)
      setLoading(false)
    }
    if (mobileJobs.length > 0) geocodeAll()
    else setLoading(false)
  }, [date, mobileJobs.map((j) => `${j.id}:${j.job_address}`).join('|')])

  useEffect(() => {
    if (!mapRef.current) return
    if (mapInstance.current) {
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
    }
    const map = L.map(mapRef.current).setView([-33.8688, 151.2093], 11)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
    }).addTo(map)
    mapInstance.current = map
    return () => {
      map.remove()
      mapInstance.current = null
    }
  }, [date])

  useEffect(() => {
    const map = mapInstance.current
    if (!map || geocoded.size === 0) return
    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []
    const bounds: L.LatLngExpression[] = []
    geocoded.forEach((coords, jobId) => {
      const job = mobileJobs.find((j) => j.id === jobId)
      if (!job) return
      const marker = L.marker(coords)
        .addTo(map)
        .bindPopup(
          `<strong>#${job.job_number}</strong> ${job.title}<br><a href="/auto-key/${job.id}">View job</a>`
        )
      markersRef.current.push(marker)
      bounds.push(coords)
    })
    if (bounds.length > 1) map.fitBounds(bounds as L.LatLngBoundsExpression, { padding: [30, 30] })
    else if (bounds.length === 1) map.setView(bounds[0], 14)
  }, [geocoded, mobileJobs])

  if (mobileJobs.length === 0) {
    return (
      <div className="rounded-lg border p-8 text-center" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
        <p style={{ color: 'var(--cafe-text-muted)' }}>No mobile jobs with addresses for this date.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {loading && (
        <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>Geocoding addresses…</p>
      )}
      <div ref={mapRef} className="h-[400px] rounded-lg border" style={{ borderColor: 'var(--cafe-border)' }} />
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--cafe-text-muted)' }}>Route order:</span>
        {mobileJobs.map((j, i) => (
          <span key={j.id} className="text-sm">
            <Link
              to={`/auto-key/${j.id}`}
              className="px-3 py-1.5 rounded inline-block"
              style={{ backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }}
            >
              {i + 1}. #{j.job_number} · {j.title}
            </Link>
          </span>
        ))}
      </div>
    </div>
  )
}
