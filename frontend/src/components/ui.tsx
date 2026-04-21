import React from 'react'

import { cn, STATUS_COLORS, STATUS_LABELS } from '@/lib/utils'

export function Badge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-[3px] text-[11px] font-semibold',
        STATUS_COLORS[status] ?? 'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
      )}
      style={{ letterSpacing: '0.015em' }}
    >
      <span
        aria-hidden
        style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', opacity: 0.75 }}
      />
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

export function Card({ className, children, style, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      className={cn('border', className)}
      style={{
        backgroundColor: 'var(--ms-surface)',
        borderColor: 'var(--ms-border)',
        borderRadius: 'var(--ms-radius)',
        boxShadow: 'var(--ms-shadow)',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

export function PageHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:mb-7 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1
          className="text-lg font-extrabold leading-tight sm:text-xl"
          style={{ color: 'var(--ms-text)', letterSpacing: '-0.02em' }}
        >
          {title}
        </h1>
        <div
          className="mt-1"
          style={{ height: 2, width: 26, borderRadius: 2, backgroundColor: 'var(--ms-accent)' }}
        />
      </div>
      {action}
    </div>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'subtle'

export function Button({
  children, onClick, type = 'button', variant = 'primary', disabled, className, size, style: styleProp, title,
}: {
  children: React.ReactNode
  onClick?: () => void
  type?: 'button' | 'submit' | 'reset'
  variant?: ButtonVariant
  disabled?: boolean
  className?: string
  size?: 'sm' | 'normal'
  style?: React.CSSProperties
  title?: string
}) {
  const isSmall = size === 'sm'
  const base =
    'inline-flex items-center justify-center gap-2 border transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none'

  const sizing: React.CSSProperties = isSmall
    ? { padding: '5px 11px', fontSize: 11 }
    : { padding: '8px 16px', fontSize: 13 }

  const variants: Record<ButtonVariant, React.CSSProperties> = {
    primary:   { backgroundColor: 'var(--ms-accent)',     color: '#fff',                 borderColor: 'var(--ms-accent)' },
    secondary: { backgroundColor: 'var(--ms-surface)',    color: 'var(--ms-text-mid)',   borderColor: 'var(--ms-border)' },
    ghost:     { backgroundColor: 'transparent',          color: 'var(--ms-text-mid)',   borderColor: 'transparent' },
    danger:    { backgroundColor: '#7A3020',              color: '#fff',                 borderColor: '#7A3020' },
    subtle:    { backgroundColor: 'var(--ms-accent-pop)', color: 'var(--ms-accent)',     borderColor: 'var(--ms-accent-light)' },
  }

  const hover: Record<ButtonVariant, string> = {
    primary:   'var(--ms-accent-hover)',
    secondary: 'var(--ms-hover)',
    ghost:     'var(--ms-hover)',
    danger:    '#5A2015',
    subtle:    'var(--ms-accent-light)',
  }

  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cn(base, className)}
      style={{
        ...variants[variant],
        ...sizing,
        fontWeight: 600,
        borderRadius: 'var(--ms-radius-sm)',
        ...styleProp,
      }}
      onMouseEnter={e => {
        if (disabled) return
        e.currentTarget.style.backgroundColor = hover[variant]
      }}
      onMouseLeave={e => {
        e.currentTarget.style.backgroundColor = variants[variant].backgroundColor as string
      }}
    >
      {children}
    </button>
  )
}

const inputBase: React.CSSProperties = {
  height: 36,
  backgroundColor: 'var(--ms-surface)',
  color: 'var(--ms-text)',
  borderRadius: 'var(--ms-radius-sm)',
  fontSize: 13,
  padding: '0 12px',
}

const labelClass = 'text-[10px] font-bold uppercase'
const labelStyle: React.CSSProperties = { color: 'var(--ms-text-muted)', letterSpacing: '0.10em', marginBottom: 5 }

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string }>(
  function Input({ label, error, ...props }, ref) {
    return (
      <div className="flex flex-col">
        {label && <label className={labelClass} style={labelStyle}>{label}</label>}
        <input
          ref={ref}
          {...props}
          className={cn('w-full border outline-none transition focus:ring-2', props.className)}
          style={{
            ...inputBase,
            borderColor: error ? '#8B3A2A' : 'var(--ms-border)',
            '--tw-ring-color': 'var(--ms-accent-pop)',
          } as React.CSSProperties}
          onFocus={e => {
            e.currentTarget.style.borderColor = error ? '#8B3A2A' : 'var(--ms-accent)'
            props.onFocus?.(e)
          }}
          onBlur={e => {
            e.currentTarget.style.borderColor = error ? '#8B3A2A' : 'var(--ms-border)'
            props.onBlur?.(e)
          }}
        />
        {error && <p className="mt-1 text-[11px]" style={{ color: '#8B3A2A' }}>{error}</p>}
      </div>
    )
  },
)

export function Select({ label, error, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label?: string; error?: string }) {
  return (
    <div className="flex flex-col">
      {label && <label className={labelClass} style={labelStyle}>{label}</label>}
      <select
        {...props}
        className={cn('w-full border outline-none transition focus:ring-2', props.className)}
        style={{
          ...inputBase,
          borderColor: error ? '#8B3A2A' : 'var(--ms-border)',
          '--tw-ring-color': 'var(--ms-accent-pop)',
        } as React.CSSProperties}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-[11px]" style={{ color: '#8B3A2A' }}>{error}</p>}
    </div>
  )
}

export function Textarea({ label, error, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string }) {
  return (
    <div className="flex flex-col">
      {label && <label className={labelClass} style={labelStyle}>{label}</label>}
      <textarea
        {...props}
        className={cn('w-full resize-none border outline-none transition focus:ring-2', props.className)}
        style={{
          backgroundColor: 'var(--ms-surface)',
          color: 'var(--ms-text)',
          borderColor: error ? '#8B3A2A' : 'var(--ms-border)',
          borderRadius: 'var(--ms-radius-sm)',
          padding: '8px 12px',
          fontSize: 13,
          '--tw-ring-color': 'var(--ms-accent-pop)',
        } as React.CSSProperties}
      />
      {error && <p className="mt-1 text-[11px]" style={{ color: '#8B3A2A' }}>{error}</p>}
    </div>
  )
}

export function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div
        className="h-9 w-9 animate-spin rounded-full border-4"
        style={{ borderColor: 'var(--ms-border)', borderTopColor: 'var(--ms-accent)' }}
      />
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16" style={{ color: 'var(--ms-text-muted)' }}>
      <div className="mb-4 h-px w-8" style={{ backgroundColor: 'var(--ms-border-strong)' }} />
      <p className="text-sm">{message}</p>
    </div>
  )
}

interface ModalProps {
  title: string
  children: React.ReactNode
  onClose: () => void
  size?: 'default' | 'wide'
}
export function Modal({ title, children, onClose, size = 'default' }: ModalProps) {
  const maxWidth = size === 'wide' ? 'sm:max-w-[780px]' : 'sm:max-w-[480px]'
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      style={{ backgroundColor: 'rgba(28, 21, 16, 0.50)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className={cn('mx-2 max-h-[90vh] w-full overflow-hidden sm:mx-4', maxWidth)}
        style={{
          backgroundColor: 'var(--ms-surface)',
          border: '1px solid var(--ms-border)',
          borderRadius: 'var(--ms-radius)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
        }}
      >
        <div
          className="flex items-center justify-between"
          style={{
            backgroundColor: 'var(--ms-bg)',
            padding: '14px 22px',
            borderBottom: '1px solid var(--ms-border)',
          }}
        >
          <h2 className="pr-2 text-[15px] font-bold" style={{ color: 'var(--ms-text)' }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xl leading-none transition-colors"
            style={{ color: 'var(--ms-text-muted)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-text)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-text-muted)')}
          >
            &times;
          </button>
        </div>
        <div
          className="overflow-y-auto"
          style={{ padding: '20px 24px', maxHeight: 'calc(90vh - 52px)' }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}

export function ViewToggle<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: React.ReactNode }[]
  onChange: (v: T) => void
}) {
  return (
    <div
      className="inline-flex"
      style={{
        gap: 2,
        backgroundColor: 'var(--ms-bg)',
        borderRadius: 'var(--ms-radius-sm)',
        padding: 3,
      }}
    >
      {options.map(opt => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            style={{
              padding: '4px 12px',
              fontSize: 12,
              fontWeight: active ? 700 : 400,
              color: active ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
              backgroundColor: active ? 'var(--ms-surface)' : 'transparent',
              borderRadius: 'var(--ms-radius-sm)',
              boxShadow: active ? 'var(--ms-shadow)' : 'none',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
