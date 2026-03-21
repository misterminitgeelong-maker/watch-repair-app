import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listWatchBrands } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
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
  const { token, activeSiteTenantId } = useAuth()
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const { data: brands = [] } = useQuery({
    queryKey: ['watch-brands', activeSiteTenantId ?? 'none'],
    queryFn: () => listWatchBrands().then(r => r.data),
    enabled: !!token,
  })

  const q = value.trim().toLowerCase()
  const suggestions = q.length
    ? brands.filter(b => b.toLowerCase().includes(q))
    : brands

  useEffect(() => {
    setHighlight(0)
  }, [value, suggestions])

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
      onChange(suggestions[highlight])
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
        onBlur={() => setTimeout(() => setOpen(false), 150)}
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
                  backgroundColor: i === highlight ? '#F5EDE0' : 'transparent',
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
