import { cn, STATUS_COLORS, STATUS_LABELS } from '@/lib/utils'

export function Badge({ status }: { status: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium tracking-wide', STATUS_COLORS[status] ?? 'bg-[#EEEBE5] text-[#7A6A5A]')}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn('rounded-2xl border shadow-sm', className)}
      style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}
    >
      {children}
    </div>
  )
}

export function PageHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-7">
      <div>
        <h1
          className="text-3xl font-semibold leading-tight"
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
  children, onClick, type = 'button', variant = 'primary', disabled, className,
}: {
  children: React.ReactNode; onClick?: () => void; type?: 'button' | 'submit' | 'reset'
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; disabled?: boolean; className?: string
}) {
  const base = 'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none'
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
      onClick={onClick}
      disabled={disabled}
      className={cn(base, variants[variant], className)}
      style={styles[variant]}
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

export function Input({ label, error, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string }) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
          {label}
        </label>
      )}
      <input
        {...props}
        className={cn(
          'rounded-lg border px-3 py-2 text-sm outline-none transition focus:ring-2',
          props.className
        )}
        style={{
          backgroundColor: 'var(--cafe-surface)',
          borderColor: error ? '#C96A5A' : 'var(--cafe-border-2)',
          color: 'var(--cafe-text)',
          // @ts-ignore
          '--tw-ring-color': 'var(--cafe-gold)',
        }}
      />
      {error && <p className="text-xs" style={{ color: '#C96A5A' }}>{error}</p>}
    </div>
  )
}

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
          'rounded-lg border px-3 py-2 text-sm outline-none transition focus:ring-2',
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

interface ModalProps { title: string; children: React.ReactNode; onClose: () => void }
export function Modal({ title, children, onClose }: ModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(28,13,5,0.55)', backdropFilter: 'blur(4px)' }}>
      <div className="rounded-2xl shadow-2xl w-full max-w-md mx-4" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
        <div
          className="flex items-center justify-between px-6 py-4"
          style={{ borderBottom: '1px solid var(--cafe-border)' }}
        >
          <h2
            className="font-semibold text-lg"
            style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
          >
            {title}
          </h2>
          <button
            onClick={onClose}
            className="text-xl leading-none transition-colors w-7 h-7 flex items-center justify-center rounded-full"
            style={{ color: 'var(--cafe-text-muted)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-text)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
          >
            &times;
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
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
          'rounded-lg border px-3 py-2 text-sm outline-none transition focus:ring-2 resize-none',
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
