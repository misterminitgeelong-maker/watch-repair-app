import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { MKT } from '@/lib/marketingTheme'

/** Flat, bordered labeled input shared by the public-facing auth pages (login, signup). */
export function MarketingField({
  label, value, onChange, type = 'text', placeholder = '', autoComplete, autoFocus = false, required = false, showPasswordToggle = false,
}: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; placeholder?: string; autoComplete?: string; autoFocus?: boolean; required?: boolean; showPasswordToggle?: boolean
}) {
  const [revealed, setRevealed] = useState(false)
  const isPassword = type === 'password'
  const inputType = isPassword && showPasswordToggle ? (revealed ? 'text' : 'password') : type
  const hasToggle = isPassword && showPasswordToggle

  return (
    <label style={{ display: 'block' }}>
      <span style={{ display: 'block', marginBottom: 6, fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: MKT.textMuted }}>
        {label}
      </span>
      <div style={{ position: 'relative' }}>
        <input
          type={inputType}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          required={required}
          onChange={e => onChange(e.target.value)}
          className="mkt-input"
          style={{
            width: '100%',
            padding: '11px 14px',
            paddingRight: hasToggle ? 42 : 14,
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontSize: 14,
            boxSizing: 'border-box',
          }}
        />
        {hasToggle && (
          <button
            type="button"
            onClick={() => setRevealed(v => !v)}
            title={revealed ? 'Hide password' : 'Show password'}
            aria-label={revealed ? 'Hide password' : 'Show password'}
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              padding: 4,
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              color: MKT.textMuted,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {revealed ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>
    </label>
  )
}
