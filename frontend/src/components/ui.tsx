import React from 'react'

import { cn, STATUS_COLORS, STATUS_LABELS } from '@/lib/utils'

export function Badge({ status }: { status: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold tracking-wide', STATUS_COLORS[status] ?? 'bg-[#EEEBE5] text-[#7A6A5A]')}>
      <span style={{ fontSize: '0.5rem', lineHeight: 1, opacity: 0.85 }}>●</span>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

export function Card({ className, children, style, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      className={cn('rounded-2xl border shadow-sm', className)}
      style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)', ...style }}
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
          className="text-2xl font-semibold leading-tight sm:text-3xl"
          style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
        >
          {title}
        </h1>
        <div className="mt-1.5 h-px w-12" style={{ backgroundColor: 'var(--cafe-gold)' }} />
      </div>
      {action}
    </div>
  )
}

export function Button({
  children, onClick, type = 'button', variant = 'primary', disabled, className, size: _size, style: styleProp, title,
}: {
  children: React.ReactNode; onClick?: () => void; type?: 'button' | 'submit' | 'reset'
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; disabled?: boolean; className?: string; size?: string
  style?: React.CSSProperties
  title?: string
}) {
  const base = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none md:min-h-10 md:py-2'
  const variants = {
    primary:   'text-white focus:ring-[var(--cafe-gold)]',
    secondary: 'border focus:ring-[var(--cafe-gold)]',
    danger:    'text-white focus:ring-[#C96A5A]',
    ghost:     'focus:ring-[var(--cafe-gold)]',
  }
  const styles = {
    primary:   { backgroundColor: 'var(--cafe-amber)', color: '#fff' },
    secondary: { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-mid)', borderColor: 'var(--cafe-border-2)' },
    danger:    { backgroundColor: '#8B3A2A', color: '#fff' },
    ghost:     { color: 'var(--cafe-text-mid)' },
  }
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cn(base, variants[variant], className)}
      style={{ ...styles[variant], ...styleProp }}
      onMouseEnter={e => {
        if (disabled) return
        const el = e.currentTarget
        if (variant === 'primary')    el.style.backgroundColor = 'var(--cafe-gold-dark)'
        if (variant === 'secondary')  el.style.backgroundColor = '#F5EDE0'
        if (variant === 'danger')     el.style.backgroundColor = '#722E20'
        if (variant === 'ghost')      el.style.backgroundColor = '#F5EDE0'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        const s = styles[variant] as React.CSSProperties
        el.style.backgroundColor = (s.backgroundColor as string) ?? 'transparent'
      }}
    >
      {children}
    </button>
  )
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string }>(
  function Input({ label, error, ...props }, ref) {
    const inputStyle: React.CSSProperties & { '--tw-ring-color': string } = {
      backgroundColor: 'var(--cafe-surface)',
      borderColor: error ? '#C96A5A' : 'var(--cafe-border-2)',
      color: 'var(--cafe-text)',
      '--tw-ring-color': 'var(--cafe-gold)',
    }
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
            {label}
          </label>
        )}
        <input
          ref={ref}
          {...props}
          className={cn(
            'h-11 rounded-lg border px-3 text-base outline-none transition focus:ring-2 sm:text-sm',
            props.className
          )}
          style={inputStyle}
        />
        {error && <p className="text-xs" style={{ color: '#C96A5A' }}>{error}</p>}
      </div>
    )
  }
)

export function Select({ label, error, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label?: string; error?: string }) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
          {label}
        </label>
      )}
      <select
        {...props}
        className={cn(
          'h-11 rounded-lg border px-3 text-base outline-none transition focus:ring-2 sm:text-sm',
          props.className
        )}
        style={{
          backgroundColor: 'var(--cafe-surface)',
          borderColor: error ? '#C96A5A' : 'var(--cafe-border-2)',
          color: 'var(--cafe-text)',
        }}
      >
        {children}
      </select>
      {error && <p className="text-xs" style={{ color: '#C96A5A' }}>{error}</p>}
    </div>
  )
}

export function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div
        className="w-9 h-9 border-4 rounded-full animate-spin"
        style={{ borderColor: 'var(--cafe-border)', borderTopColor: 'var(--cafe-amber)' }}
      />
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16" style={{ color: 'var(--cafe-text-muted)' }}>
      <div className="w-8 h-px mb-4" style={{ backgroundColor: 'var(--cafe-border-2)' }} />
      <p className="text-sm italic" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>{message}</p>
    </div>
  )
}

interface ModalProps {
  title: string
  children: React.ReactNode
  onClose: () => void
  /** Wider panel on sm+ for dense forms (e.g. new Mobile Services job). */
  size?: 'default' | 'wide'
}
export function Modal({ title, children, onClose, size = 'default' }: ModalProps) {
  const maxWidth =
    size === 'wide'
      ? 'max-w-[min(100%,42rem)] sm:max-w-2xl lg:max-w-3xl'
      : 'max-w-md'
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" style={{ backgroundColor: 'rgba(28,13,5,0.55)', backdropFilter: 'blur(4px)' }}>
      <div
        className={cn(
          'max-h-[90vh] w-full overflow-y-auto rounded-t-2xl shadow-2xl mx-2 sm:mx-4 sm:rounded-2xl',
          maxWidth
        )}
        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
      >
        <div
          className="flex items-center justify-between px-4 py-3 sm:px-6 sm:py-4"
          style={{ borderBottom: '1px solid var(--cafe-border)' }}
        >
          <h2
            className="font-semibold text-base sm:text-lg pr-2"
            style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
          >
            {title}
          </h2>
          <button
            onClick={onClose}
            className="text-xl leading-none transition-colors w-7 h-7 flex shrink-0 items-center justify-center rounded-full"
            style={{ color: 'var(--cafe-text-muted)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-text)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
          >
            &times;
          </button>
        </div>
        <div className="px-4 py-4 sm:px-6 sm:py-5">{children}</div>
      </div>
    </div>
  )
}

export function Textarea({ label, error, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string }) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
          {label}
        </label>
      )}
      <textarea
        {...props}
        className={cn(
          'rounded-lg border px-3 py-2.5 text-base outline-none transition focus:ring-2 resize-none sm:text-sm',
          props.className
        )}
        style={{
          backgroundColor: 'var(--cafe-surface)',
          borderColor: error ? '#C96A5A' : 'var(--cafe-border-2)',
          color: 'var(--cafe-text)',
        }}
      />
      {error && <p className="text-xs" style={{ color: '#C96A5A' }}>{error}</p>}
    </div>
  )
}
