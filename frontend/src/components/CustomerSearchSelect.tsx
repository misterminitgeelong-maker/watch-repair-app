import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { Customer } from '@/lib/api'
import { Input } from '@/components/ui'

/**
 * Typeahead customer picker (name / phone / email). Controlled via
 * value + onChange, filters an already-loaded customer list client-side;
 * no API calls.
 *
 * The suggestion list is portaled to <body> and positioned from the
 * input's live viewport rect rather than plain `position: absolute`.
 * Every caller renders this inside a Modal whose body scrolls with
 * `overflow-y-auto`, which silently clips an absolutely-positioned
 * dropdown — the list would filter correctly underneath but never
 * become visible.
 */
export function CustomerSearchSelect({ customers, value, onChange }: { customers: Customer[]; value: string; onChange: (id: string) => void }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const [rect, setRect] = useState<{ top: number; left: number; width: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const dropdownRef = useRef<HTMLUListElement>(null)
  const q = search.trim().toLowerCase()
  // Digits-only form of the query, for matching phone numbers regardless of
  // formatting. Must stay empty (not match) when q has no digits at all -
  // otherwise `phone.includes('')` is trivially true and a plain-text query
  // like "Jane" would match every customer via the phone branch.
  const qDigits = q.replace(/\D/g, '')
  const filtered = q
    ? customers.filter(c =>
        c.full_name.toLowerCase().includes(q) ||
        (qDigits && c.phone && c.phone.replace(/\D/g, '').includes(qDigits)) ||
        (c.email && c.email.toLowerCase().includes(q))
      )
    : customers
  const selected = customers.find(c => c.id === value)
  const display = selected ? `${selected.full_name}${selected.phone ? ` · ${selected.phone}` : ''}` : search
  const safeHighlight = filtered.length === 0 ? 0 : Math.min(highlight, filtered.length - 1)

  useEffect(() => {
    const h = (e: MouseEvent) => {
      const target = e.target as Node
      if (containerRef.current?.contains(target)) return
      if (dropdownRef.current?.contains(target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  // Recompute position whenever open, and while open track scroll (capture,
  // so scrolling the modal body counts) and resize so the list follows the
  // input instead of drifting once the page/modal scrolls.
  useLayoutEffect(() => {
    if (!open) return
    const update = () => {
      const el = containerRef.current
      if (!el) return
      const r = el.getBoundingClientRect()
      setRect({ top: r.bottom, left: r.left, width: r.width })
    }
    update()
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [open])

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
      {open && rect && createPortal(
        <ul
          ref={dropdownRef}
          className="fixed z-50 py-1 rounded-lg border shadow-lg overflow-y-auto max-h-48"
          style={{
            top: rect.top + 4,
            left: rect.left,
            width: rect.width,
            backgroundColor: 'var(--ms-surface)',
            borderColor: 'var(--ms-border-strong)',
          }}
        >
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
        </ul>,
        document.body,
      )}
    </div>
  )
}
