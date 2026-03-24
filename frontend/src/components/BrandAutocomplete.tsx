import { useState, useRef, useEffect } from 'react'
import { WATCH_BRANDS } from '@/lib/watchBrands'
import { Input } from '@/components/ui'

interface Props {
  label?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  autoFocus?: boolean
  className?: string
}

export default function BrandAutocomplete({ label, value, onChange, placeholder = 'Rolex, Omega…', autoFocus, className }: Props) {
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const q = value.trim().toLowerCase()
  const suggestions = q.length
    ? WATCH_BRANDS.filter(b => b.toLowerCase().includes(q))
    : WATCH_BRANDS

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
      onChange(suggestions[safeHighlight])
      setOpen(false)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const pick = (brand: string) => {
    onChange(brand)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <Input
        label={label}
        value={value}
        onChange={e => {
          onChange(e.target.value)
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
        autoFocus={autoFocus}
        className={className}
      />
      {open && suggestions.length > 0 && (
        <ul
          className="absolute z-50 w-full mt-1 py-1 rounded-lg border shadow-lg overflow-y-auto max-h-48"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            borderColor: 'var(--cafe-border-2)',
          }}
        >
          {suggestions.slice(0, 20).map((brand, i) => (
            <li key={brand}>
              <button
                type="button"
                className="w-full text-left px-3 py-2 text-sm truncate"
                style={{
                  color: 'var(--cafe-text)',
                  backgroundColor: i === safeHighlight ? '#F5EDE0' : 'transparent',
                }}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={e => {
                  e.preventDefault()
                  pick(brand)
                }}
              >
                {brand}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
