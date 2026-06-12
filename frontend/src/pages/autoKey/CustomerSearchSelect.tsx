import { useEffect, useRef, useState } from 'react'
import type { Customer } from '@/lib/api'
import { Input } from '@/components/ui'

/**
 * Typeahead customer picker (name / phone / email) used by the auto-key
 * new-job and POS flows. Controlled via value + onChange; no API calls.
 */
export function CustomerSearchSelect({ customers, value, onChange }: { customers: Customer[]; value: string; onChange: (id: string) => void }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const q = search.trim().toLowerCase()
  const filtered = q
    ? customers.filter(c =>
        c.full_name.toLowerCase().includes(q) ||
        (c.phone && c.phone.replace(/\D/g, '').includes(q.replace(/\D/g, ''))) ||
        (c.email && c.email.toLowerCase().includes(q))
      )
    : customers
  const selected = customers.find(c => c.id === value)
  const display = selected ? `${selected.full_name}${selected.phone ? ` · ${selected.phone}` : ''}` : search
  const safeHighlight = filtered.length === 0 ? 0 : Math.min(highlight, filtered.length - 1)
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const h = (e: MouseEvent) => { if (!el.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={containerRef} className="relative">
      <Input
        label="Search customer"
        value={open ? search : display}
        onChange={e => { setSearch(e.target.value); setOpen(true); setHighlight(0) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={e => {
          if (!open || filtered.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(i => (i + 1) % filtered.length) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(i => (i - 1 + filtered.length) % filtered.length) }
          else if (e.key === 'Enter') { e.preventDefault(); onChange(filtered[safeHighlight].id); setOpen(false); setSearch('') }
          else if (e.key === 'Escape') setOpen(false)
        }}
        placeholder="Type name, phone or email…"
      />
      {open && (
        <ul className="absolute z-50 w-full mt-1 py-1 rounded-lg border shadow-lg overflow-y-auto max-h-48" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)' }}>
          {filtered.slice(0, 30).map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                className="w-full text-left px-3 py-2 text-sm truncate"
                style={{ color: 'var(--ms-text)', backgroundColor: i === safeHighlight ? '#F5EDE0' : 'transparent' }}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={e => { e.preventDefault(); onChange(c.id); setOpen(false); setSearch('') }}
              >
                {c.full_name}{c.phone ? ` · ${c.phone}` : ''}{c.email ? ` · ${c.email}` : ''}
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="px-3 py-2 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No customers match</li>}
        </ul>
      )}
    </div>
  )
}
