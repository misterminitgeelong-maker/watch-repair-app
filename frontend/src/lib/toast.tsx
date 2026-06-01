import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { X } from 'lucide-react'

export type ToastVariant = 'success' | 'error' | 'info'

export type ToastItem = {
  id: string
  message: string
  variant: ToastVariant
}

type ToastContextValue = {
  toast: (message: string, variant?: ToastVariant) => void
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const VARIANT_STYLE: Record<ToastVariant, { bg: string; border: string; color: string }> = {
  success: { bg: '#F0FAF0', border: '#1F6D4C', color: '#1F6D4C' },
  error: { bg: '#FDF0EE', border: '#C96A5A', color: '#8B3A3A' },
  info: { bg: 'var(--ms-surface)', border: 'var(--ms-border-strong)', color: 'var(--ms-text)' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: string) => {
    setItems(prev => prev.filter(t => t.id !== id))
  }, [])

  const push = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = crypto.randomUUID()
    setItems(prev => [...prev.slice(-4), { id, message, variant }])
    window.setTimeout(() => dismiss(id), variant === 'error' ? 6000 : 4000)
  }, [dismiss])

  const value = useMemo<ToastContextValue>(
    () => ({
      toast: push,
      success: (m: string) => push(m, 'success'),
      error: (m: string) => push(m, 'error'),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="fixed bottom-20 md:bottom-6 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none"
        aria-live="polite"
      >
        {items.map(t => {
          const s = VARIANT_STYLE[t.variant]
          return (
            <div
              key={t.id}
              className="pointer-events-auto rounded-lg px-4 py-3 text-sm shadow-lg flex items-start gap-2"
              style={{ backgroundColor: s.bg, border: `1px solid ${s.border}`, color: s.color }}
            >
              <span className="flex-1">{t.message}</span>
              <button
                type="button"
                className="shrink-0 opacity-70 hover:opacity-100"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
