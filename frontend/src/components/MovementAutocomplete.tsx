import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listWatchMovements } from '@/lib/api'
import type { WatchMovement } from '@/lib/api'
import { Input } from '@/components/ui'

interface Props {
  label?: string
  placeholder?: string
  onSelect: (movementKey: string) => void
  disabled?: boolean
}

export default function MovementAutocomplete({ label, placeholder = 'Search movements…', onSelect, disabled }: Props) {
  const [value, setValue] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const { data: movementsData, isLoading: movementsLoading } = useQuery({
    queryKey: ['watch-movements'],
    queryFn: () => listWatchMovements().then(r => r.data),
    enabled: open,
  })

  const movements = movementsData?.movements ?? []
  const q = value.trim().toLowerCase()
  const suggestions = q.length
    ? movements.filter(
        m =>
          m.name.toLowerCase().includes(q) ||
          (m.key ?? '').toLowerCase().includes(q),
      )
    : movements

  const safeHighlight = suggestions.length === 0 ? 0 : Math.min(highlight, suggestions.length - 1)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const h = (e: MouseEvent) => {
      if (!el.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0) {
      if (e.key === 'Escape') setOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight(i => (i + 1) % suggestions.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight(i => (i - 1 + suggestions.length) % suggestions.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      pick(suggestions[safeHighlight])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const pick = (m: WatchMovement) => {
    onSelect(m.key)
    setValue('')
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <Input
        label={label}
        value={value}
        onChange={e => {
          setValue(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={e => {
          const next = e.relatedTarget as Node | null
          if (containerRef.current?.contains(next)) return
          setTimeout(() => setOpen(false), 150)
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
      />
      {open && (
        <ul
          className="absolute z-50 w-full mt-1 py-1 rounded-lg border shadow-lg overflow-y-auto max-h-64"
          style={{
            backgroundColor: 'var(--ms-surface)',
            borderColor: 'var(--ms-border-strong)',
          }}
        >
          {movementsLoading ? (
            <li className="px-3 py-4 text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>Loading movements…</li>
          ) : suggestions.length === 0 ? (
            <li className="px-3 py-4 text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>No movements found</li>
          ) : (
          suggestions.slice(0, 30).map((m, i) => (
            <li key={m.key}>
              <button
                type="button"
                className="w-full text-left px-3 py-2 text-sm flex justify-between items-center gap-2"
                style={{
                  color: 'var(--ms-text)',
                  backgroundColor: i === safeHighlight ? '#F5EDE0' : 'transparent',
                }}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={e => {
                  e.preventDefault()
                  pick(m)
                }}
              >
                <span className="truncate flex-1 min-w-0">{m.name}</span>
                <span className="shrink-0 text-right">
                  <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                    Cost: ${((m.purchase_cost_cents ?? 0) / 100).toFixed(2)}
                  </span>
                  <span className="mx-1.5" style={{ color: 'var(--ms-border)' }}>→</span>
                  <span className="font-medium" style={{ color: 'var(--ms-accent)' }}>
                    RRP: {m.quote_cents != null ? `$${(m.quote_cents / 100).toFixed(2)}` : '—'}
                  </span>
                </span>
              </button>
            </li>
          ))
          )}
        </ul>
      )}
    </div>
  )
}
