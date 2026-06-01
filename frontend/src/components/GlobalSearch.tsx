import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { globalSearch, type GlobalSearchHit } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { getApiErrorMessage } from '@/lib/api/client'
import { loadRecentHits, pushRecentHit, type RecentHit } from '@/lib/recentSearch'
import { useToast } from '@/lib/toast'
import { Badge } from '@/components/ui'

interface GlobalSearchProps {
  open: boolean
  onClose: () => void
}

const KIND_LABEL: Record<string, string> = {
  repair_job: 'Watch',
  shoe_repair_job: 'Shoe',
  auto_key_job: 'Mobile',
  customer: 'Customer',
  invoice: 'Invoice',
}

export default function GlobalSearch({ open, onClose }: GlobalSearchProps) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<GlobalSearchHit[]>([])
  const [recent, setRecent] = useState<RecentHit[]>([])
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const { hasFeature } = useAuth()
  const toast = useToast()

  useEffect(() => {
    if (open) {
      setQ('')
      setHits([])
      setRecent(loadRecentHits())
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [open])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  useEffect(() => {
    if (!q.trim()) {
      setHits([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await globalSearch(q.trim())
        const filtered = (res.data?.hits ?? []).filter(h => {
          if (h.kind === 'repair_job') return hasFeature('watch')
          if (h.kind === 'shoe_repair_job') return hasFeature('shoe')
          if (h.kind === 'auto_key_job') return hasFeature('auto_key')
          return true
        })
        setHits(filtered)
      } catch (e) {
        toast.error(getApiErrorMessage(e, 'Search failed'))
        setHits([])
      } finally {
        setLoading(false)
      }
    }, 280)
    return () => clearTimeout(timer)
  }, [q, hasFeature, toast])

  function go(hit: GlobalSearchHit | RecentHit) {
    pushRecentHit({ kind: hit.kind, id: hit.id, title: hit.title, href: hit.href })
    navigate(hit.href)
    onClose()
  }

  if (!open) return null

  const showRecent = !q.trim() && recent.length > 0
  const hasResults = hits.length > 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4"
      style={{ paddingTop: '10vh', backgroundColor: 'rgba(30,20,10,0.45)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden"
        style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <Search size={16} style={{ color: 'var(--ms-text-muted)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search jobs, customers, invoices…"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--ms-text)' }}
          />
          {q && (
            <button type="button" onClick={() => setQ('')} style={{ color: 'var(--ms-text-muted)', flexShrink: 0 }}>
              <X size={14} />
            </button>
          )}
        </div>

        <div className="max-h-96 overflow-y-auto">
          {!q.trim() && !showRecent && (
            <p className="px-4 py-8 text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
              Search across watch, shoe, and mobile jobs
            </p>
          )}
          {showRecent && (
            <div>
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>
                Recent
              </p>
              {recent.map(r => (
                <ResultRow
                  key={`${r.kind}-${r.id}`}
                  title={r.title}
                  subtitle={KIND_LABEL[r.kind] ?? r.kind}
                  badge={null}
                  onClick={() => go(r)}
                />
              ))}
            </div>
          )}
          {loading && q.trim() && (
            <p className="px-4 py-6 text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>Searching…</p>
          )}
          {!loading && q.trim() && !hasResults && (
            <p className="px-4 py-8 text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
              No results for <strong>&quot;{q}&quot;</strong>
            </p>
          )}
          {!loading && hits.map(h => (
            <ResultRow
              key={`${h.kind}-${h.id}`}
              title={h.title}
              subtitle={[KIND_LABEL[h.kind], h.subtitle].filter(Boolean).join(' · ')}
              badge={h.status ? <Badge status={h.status} /> : null}
              onClick={() => go(h)}
            />
          ))}
        </div>

        <div className="px-4 py-2 flex items-center justify-between" style={{ borderTop: '1px solid var(--ms-border)' }}>
          <span className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>↵ open · esc close</span>
          <span className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>⌘K</span>
        </div>
      </div>
    </div>
  )
}

function ResultRow({
  title,
  subtitle,
  badge,
  onClick,
}: {
  title: string
  subtitle: string
  badge: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className="w-full text-left px-4 py-2.5 flex items-center justify-between gap-3 transition-colors"
      style={{ borderBottom: '1px solid var(--ms-border)' }}
      onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--ms-hover)')}
      onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
      onClick={onClick}
    >
      <div className="min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: 'var(--ms-text)' }}>{title}</p>
        <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>{subtitle}</p>
      </div>
      {badge}
    </button>
  )
}
