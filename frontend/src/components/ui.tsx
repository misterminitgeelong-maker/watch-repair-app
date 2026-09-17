import React, { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

import { cn, STATUS_COLORS, STATUS_LABELS } from '@/lib/utils'

export type BadgeVariant = 'default' | 'success' | 'warning' | 'danger'

const VARIANT_COLORS: Record<BadgeVariant, string> = {
  default: 'bg-[var(--ms-badge-neutral-bg)] text-[var(--ms-badge-neutral-text)]',
  success: 'bg-[var(--ms-badge-done-bg)] text-[var(--ms-badge-done-text)]',
  warning: 'bg-[var(--ms-badge-wait-bg)] text-[var(--ms-badge-wait-text)]',
  danger: 'bg-[var(--ms-badge-alert-bg)] text-[var(--ms-badge-alert-text)]',
}

export function Badge({
  status,
  variant = 'default',
  children,
  className,
}: {
  status?: string
  variant?: BadgeVariant
  children?: React.ReactNode
  className?: string
}) {
  const useStatusColors = status != null
  const colorClass = useStatusColors
    ? (STATUS_COLORS[status] ?? VARIANT_COLORS.default)
    : VARIANT_COLORS[variant]

  const label = children ?? (status != null ? (STATUS_LABELS[status] ?? status) : null)

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-[3px] text-[11px] font-semibold',
        colorClass,
        className,
      )}
      style={{ letterSpacing: '0.015em' }}
    >
      {useStatusColors && (
        <span
          aria-hidden
          style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', opacity: 0.75 }}
        />
      )}
      {label}
    </span>
  )
}

/**
 * Inline surface. Carries no shadow by policy — it separates from the page
 * with a hairline rule and the surface/bg step. Border colour lives in the
 * class (not inline style) so the `.ms-card-hoverable` :hover rule can
 * override it; callers passing `style.borderColor` still win as before.
 */
export function Card({
  className, children, style, hoverable, ...props
}: React.HTMLAttributes<HTMLDivElement> & { hoverable?: boolean }) {
  // Inline surface: no shadow. A hairline rule and the --ms-bg/--ms-surface
  // step do the separating. Hover is a CSS class (see index.css) so it also
  // answers keyboard focus, and it only firms the rule — no lift.
  return (
    <div
      {...props}
      className={cn('border', hoverable && 'ms-card-hoverable', className)}
      style={{
        backgroundColor: 'var(--ms-surface)',
        borderColor: 'var(--ms-card-border, var(--ms-border))',
        borderRadius: 'var(--ms-radius)',
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
        <h1 className="ms-page-title text-[26px] leading-none sm:text-[30px]">
          {title}
        </h1>
        <div
          className="mt-2"
          style={{ height: 2, width: 28, backgroundColor: 'var(--ms-accent)' }}
        />
      </div>
      {action}
    </div>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'subtle'

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: 'sm' | 'normal'
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    children,
    className,
    size,
    variant = 'primary',
    style: styleProp,
    disabled,
    type = 'button',
    onMouseEnter,
    onMouseLeave,
    ...rest
  },
  ref,
) {
  const isSmall = size === 'sm'
  const base =
    'inline-flex min-h-11 items-center justify-center gap-2 border transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none sm:min-h-0'

  const sizing: React.CSSProperties = isSmall
    ? { padding: '5px 11px', fontSize: 11 }
    : { padding: '8px 16px', fontSize: 13 }

  const variants: Record<ButtonVariant, React.CSSProperties> = {
    primary:   { backgroundColor: 'var(--ms-accent)',     color: 'var(--ms-on-accent)',  borderColor: 'var(--ms-accent)' },
    secondary: { backgroundColor: 'var(--ms-surface)',    color: 'var(--ms-text-mid)',   borderColor: 'var(--ms-border)' },
    ghost:     { backgroundColor: 'transparent',          color: 'var(--ms-text-mid)',   borderColor: 'transparent' },
    danger:    { backgroundColor: 'var(--ms-danger)',     color: 'var(--ms-on-danger)',  borderColor: 'var(--ms-danger)' },
    subtle:    { backgroundColor: 'var(--ms-accent-pop)', color: 'var(--ms-accent)',     borderColor: 'var(--ms-accent-light)' },
  }

  const hover: Record<ButtonVariant, string> = {
    primary:   'var(--ms-accent-hover)',
    secondary: 'var(--ms-hover)',
    ghost:     'var(--ms-hover)',
    danger:    'var(--ms-danger-hover)',
    subtle:    'var(--ms-accent-light)',
  }

  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled}
      className={cn(base, className)}
      style={{
        ...variants[variant],
        ...sizing,
        fontWeight: 600,
        borderRadius: 'var(--ms-radius-sm)',
        ...styleProp,
      }}
      {...rest}
      onMouseEnter={e => {
        onMouseEnter?.(e)
        if (disabled) return
        e.currentTarget.style.backgroundColor = hover[variant]
      }}
      onMouseLeave={e => {
        onMouseLeave?.(e)
        e.currentTarget.style.backgroundColor = variants[variant].backgroundColor as string
      }}
    >
      {children}
    </button>
  )
})

const inputBase: React.CSSProperties = {
  backgroundColor: 'var(--ms-surface)',
  color: 'var(--ms-text)',
  borderRadius: 'var(--ms-radius-sm)',
  padding: '0 12px',
}

const labelClass = 'text-[10px] font-semibold uppercase'
const labelStyle: React.CSSProperties = { fontFamily: 'var(--ms-font-heading)', color: 'var(--ms-text-muted)', letterSpacing: '0.10em', marginBottom: 5 }

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string }>(
  function Input({ label, error, ...props }, ref) {
    return (
      <div className="flex flex-col">
        {label && <label className={labelClass} style={labelStyle}>{label}</label>}
        <input
          ref={ref}
          {...props}
          className={cn('h-11 w-full border text-base outline-none transition focus:ring-2 sm:h-9 sm:text-[13px]', props.className)}
          style={{
            ...inputBase,
            borderColor: error ? 'var(--ms-error)' : 'var(--ms-border)',
            '--tw-ring-color': 'var(--ms-accent-pop)',
          } as React.CSSProperties}
          onFocus={e => {
            e.currentTarget.style.borderColor = error ? 'var(--ms-error)' : 'var(--ms-accent)'
            props.onFocus?.(e)
          }}
          onBlur={e => {
            e.currentTarget.style.borderColor = error ? 'var(--ms-error)' : 'var(--ms-border)'
            props.onBlur?.(e)
          }}
        />
        {error && <p className="mt-1 text-[11px]" style={{ color: 'var(--ms-error)' }}>{error}</p>}
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
        className={cn('h-11 w-full border text-base outline-none transition focus:ring-2 sm:h-9 sm:text-[13px]', props.className)}
        style={{
          ...inputBase,
          borderColor: error ? 'var(--ms-error)' : 'var(--ms-border)',
          '--tw-ring-color': 'var(--ms-accent-pop)',
        } as React.CSSProperties}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-[11px]" style={{ color: 'var(--ms-error)' }}>{error}</p>}
    </div>
  )
}

export function Textarea({ label, error, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string }) {
  return (
    <div className="flex flex-col">
      {label && <label className={labelClass} style={labelStyle}>{label}</label>}
      <textarea
        {...props}
        className={cn('w-full resize-none border text-base outline-none transition focus:ring-2 sm:text-[13px]', props.className)}
        style={{
          backgroundColor: 'var(--ms-surface)',
          color: 'var(--ms-text)',
          borderColor: error ? 'var(--ms-error)' : 'var(--ms-border)',
          borderRadius: 'var(--ms-radius-sm)',
          padding: '8px 12px',
          '--tw-ring-color': 'var(--ms-accent-pop)',
        } as React.CSSProperties}
      />
      {error && <p className="mt-1 text-[11px]" style={{ color: 'var(--ms-error)' }}>{error}</p>}
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
  /** Use the whole phone viewport for longer, task-focused flows. */
  mobileFullScreen?: boolean
  /** When true, the close button is disabled (e.g. during submit). */
  closeDisabled?: boolean
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusableIn(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    el => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true',
  )
}

export function Modal({ title, children, onClose, size = 'default', mobileFullScreen = false, closeDisabled = false }: ModalProps) {
  const maxWidth = size === 'wide' ? 'sm:max-w-[780px]' : 'sm:max-w-[480px]'
  const mobilePanel = mobileFullScreen
    ? 'h-[100dvh] max-h-[100dvh] rounded-none'
    : 'mx-2 max-h-[calc(100dvh-8px)] rounded-t-[var(--ms-radius)]'
  const mobileBody = mobileFullScreen
    ? 'max-h-[calc(100dvh-56px)]'
    : 'max-h-[calc(100dvh-64px)]'
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const panel = panelRef.current
    const initial = panel ? focusableIn(panel)[0] : undefined
    ;(initial ?? panel)?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (!closeDisabled) {
          event.preventDefault()
          onClose()
        }
        return
      }
      if (event.key !== 'Tab' || !panel) return
      const nodes = focusableIn(panel)
      if (nodes.length === 0) {
        event.preventDefault()
        panel.focus()
        return
      }
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      previousFocusRef.current?.focus?.()
    }
  }, [onClose, closeDisabled])

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      style={{ backgroundColor: 'var(--ms-overlay)', backdropFilter: 'blur(4px)' }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn('w-full overflow-hidden sm:mx-4 sm:h-auto sm:max-h-[90vh] sm:rounded-[var(--ms-radius)]', mobilePanel, maxWidth)}
        style={{
          backgroundColor: 'var(--ms-surface)',
          border: '1px solid var(--ms-border)',
          boxShadow: 'var(--ms-shadow-overlay)',
        }}
      >
        <div
          className="flex min-h-14 items-center justify-between px-4 py-3 sm:min-h-0 sm:px-[22px] sm:py-[14px]"
          style={{
            backgroundColor: 'var(--ms-bg)',
            borderBottom: '1px solid var(--ms-border)',
          }}
        >
          <h2 id={titleId} className="pr-2 text-[15px] font-bold" style={{ color: 'var(--ms-text)' }}>
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={closeDisabled}
            aria-label="Close"
            aria-disabled={closeDisabled}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-xl leading-none transition-colors disabled:cursor-not-allowed disabled:opacity-40 sm:h-7 sm:w-7"
            style={{ color: 'var(--ms-text-muted)' }}
            onMouseEnter={e => { if (!closeDisabled) e.currentTarget.style.color = 'var(--ms-text)' }}
            onMouseLeave={e => { if (!closeDisabled) e.currentTarget.style.color = 'var(--ms-text-muted)' }}
          >
            &times;
          </button>
        </div>
        <div
          className={cn(mobileBody, 'overflow-y-auto px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:max-h-[calc(90vh-52px)] sm:px-6 sm:py-5')}
        >
          {children}
        </div>
      </div>
    </div>,
    document.body,
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
              boxShadow: active ? '0 0 0 1px var(--ms-border)' : 'none',
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
