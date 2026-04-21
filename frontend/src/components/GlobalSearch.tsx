import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { listCustomers, listJobs, type Customer, type RepairJob } from '@/lib/api'
import { Badge } from '@/components/ui'

interface GlobalSearchProps {
  open: boolean
  onClose: () => void
}

export default function GlobalSearch({ open, onClose }: GlobalSearchProps) {
  const [q, setQ] = useState('')
  const [jobs, setJobs] = useState<RepairJob[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Autofocus + reset on open
  useEffect(() => {
    if (open) {
      setQ('')
      setJobs([])
      setCustomers([])
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [open])

  // Escape to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // Debounced search with stale-result guard (F-M8).
  // Each effect run bumps a monotonically increasing request id; when the
  // response comes back we only apply its results if its id still matches
  // the latest request. This avoids the typical "type fast, older slower
  // response overwrites newer result" flash. We also clear state immediately
  // on unmount so a late response cannot call setState on an unmounted tree.
  const requestIdRef = useRef(0)
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!q.trim()) {
      setJobs([])
      setCustomers([])
      return
    }
    const timer = setTimeout(async () => {
      const myRequestId = ++requestIdRef.current
      setLoading(true)
      try {
        const [jobRes, custRes] = await Promise.all([
          listJobs({ limit: 6, q: q.trim() }),
          listCustomers({ limit: 6, q: q.trim() }),
        ])
        if (!mountedRef.current || myRequestId !== requestIdRef.current) return
        setJobs(jobRes.data ?? [])
        setCustomers(custRes.data ?? [])
      } catch {
        // silently ignore search errors (including stale-request aborts)
      } finally {
        if (mountedRef.current && myRequestId === requestIdRef.current) {
          setLoading(false)
        }
      }
    }, 280)
    return () => clearTimeout(timer)
  }, [q])

  function go(path: string) {
    navigate(path)
    onClose()
  }

  if (!open) return null

  const hasResults = jobs.length > 0 || customers.length > 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4"
      style={{ paddingTop: '10vh', backgroundColor: 'rgba(30,20,10,0.45)' }}
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Global search"
        className="w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden"
        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <Search size={16} style={{ color: 'var(--cafe-text-muted)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search jobs, customers…"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--cafe-text)' }}
          />
          {q && (
            <button onClick={() => setQ('')} style={{ color: 'var(--cafe-text-muted)', flexShrink: 0 }}>
              <X size={14} />
            </button>
          )}
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {!q.trim() && (
            <p className="px-4 py-8 text-sm text-center" style={{ color: 'var(--cafe-text-muted)' }}>
              Type to search jobs and customers
            </p>
          )}
          {loading && q.trim() && (
            <p className="px-4 py-6 text-sm text-center" style={{ color: 'var(--cafe-text-muted)' }}>Searching…</p>
          )}
          {!loading && q.trim() && !hasResults && (
            <p className="px-4 py-8 text-sm text-center" style={{ color: 'var(--cafe-text-muted)' }}>
              No results for <strong>"{q}"</strong>
            </p>
          )}

          {!loading && jobs.length > 0 && (
            <div>
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>
                Jobs
              </p>
              {jobs.map(j => (
                <button
                  key={j.id}
                  className="w-full text-left px-4 py-2.5 flex items-center justify-between gap-3 transition-colors"
                  style={{ borderBottom: '1px solid var(--cafe-border)' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  onClick={() => go(`/jobs/${j.id}`)}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--cafe-text)' }}>{j.title}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                      #{j.job_number}{j.customer_name ? ` · ${j.customer_name}` : ''}
                    </p>
                  </div>
                  <Badge status={j.status} />
                </button>
              ))}
            </div>
          )}

          {!loading && customers.length > 0 && (
            <div>
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>
                Customers
              </p>
              {customers.map(c => (
                <button
                  key={c.id}
                  className="w-full text-left px-4 py-2.5 transition-colors"
                  style={{ borderBottom: '1px solid var(--cafe-border)' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  onClick={() => go(`/customers/${c.id}`)}
                >
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{c.full_name}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                    {[c.email, c.phone].filter(Boolean).join(' · ') || 'No contact details'}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 flex items-center justify-between" style={{ borderTop: '1px solid var(--cafe-border)' }}>
          <span className="text-[11px]" style={{ color: 'var(--cafe-text-muted)' }}>↵ open · esc close</span>
          <span className="text-[11px]" style={{ color: 'var(--cafe-text-muted)' }}>⌘K</span>
        </div>
      </div>
    </div>
  )
}
