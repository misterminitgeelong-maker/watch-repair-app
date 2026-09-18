/**
 * Period controls shared by the reports screens.
 *
 * Report headers were built desktop-first with 11–13px chips and date inputs
 * about 28px tall. On a phone those are under the 44px touch target, and any
 * focusable field below 16px makes iOS Safari zoom the whole page in. These
 * give phones a comfortable control and keep the compact desktop density from
 * `sm:` up.
 */
import type { ReactNode } from 'react'

const FIELD_CLASS =
  'h-11 w-full rounded-lg border px-3 text-base outline-none transition focus:ring-2 sm:h-8 sm:w-auto sm:text-xs'

const FIELD_STYLE = {
  backgroundColor: 'var(--ms-surface)',
  borderColor: 'var(--ms-border)',
  color: 'var(--ms-text)',
  '--tw-ring-color': 'var(--ms-accent-pop)',
} as React.CSSProperties

export function PeriodDateInput({
  label,
  value,
  onChange,
  min,
  max,
  className,
}: {
  /** Always set: these inputs sit in a row with no visible label. */
  label: string
  value: string
  onChange: (value: string) => void
  min?: string
  max?: string
  className?: string
}) {
  return (
    <input
      type="date"
      aria-label={label}
      value={value}
      min={min}
      max={max}
      onChange={e => onChange(e.target.value)}
      className={`${FIELD_CLASS} ${className ?? ''}`}
      style={FIELD_STYLE}
    />
  )
}

export function PeriodSelect({
  label,
  value,
  onChange,
  children,
  className,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  children: ReactNode
  className?: string
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={e => onChange(e.target.value)}
      className={`${FIELD_CLASS} font-semibold ${className ?? ''}`}
      style={FIELD_STYLE}
    >
      {children}
    </select>
  )
}

export type PeriodChoice<T extends string> = { key: T; label: string }

/**
 * Segmented period presets. Wraps into comfortable chips on a phone and keeps
 * the tight desktop segmented control from `sm:` up.
 */
export function PeriodChips<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly PeriodChoice<T>[]
  value: T
  onChange: (key: T) => void
  label: string
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="flex flex-wrap gap-1 rounded-lg p-1"
      style={{ backgroundColor: 'var(--ms-bg)' }}
    >
      {options.map(option => {
        const active = option.key === value
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.key)}
            className="min-h-11 flex-1 rounded-md px-3 text-sm font-semibold transition-colors sm:min-h-0 sm:flex-none sm:px-2.5 sm:py-1 sm:text-xs"
            style={{
              backgroundColor: active ? 'var(--ms-surface)' : 'transparent',
              color: active ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
            }}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

/**
 * States a report can be in before its numbers mean anything. Rendered as a
 * live region so a screen reader hears the change of state, and each one is
 * worded rather than signalled by colour alone.
 */
export function ReportStateNote({
  tone = 'info',
  children,
}: {
  tone?: 'info' | 'warn'
  children: ReactNode
}) {
  return (
    <p
      role="status"
      aria-live="polite"
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        backgroundColor: tone === 'warn' ? 'rgba(180,120,40,0.14)' : 'var(--ms-bg)',
        color: tone === 'warn' ? '#6A4A10' : 'var(--ms-text-mid)',
      }}
    >
      {children}
    </p>
  )
}
