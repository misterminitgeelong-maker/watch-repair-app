import { useCallback, useEffect, useRef, useState } from 'react'
import {
  clearDraft,
  clearExpiredDrafts,
  loadDraft,
  saveDraft,
  type LoadedDraft,
} from '@/lib/draftStorage'

export type IntakeDraftOptions<T> = {
  /** Intake kind, e.g. `watch-intake`. Combined with `scope` to key the draft. */
  kind: string
  /** Shop/user scope — see `draftScope`. A null scope disables the draft. */
  scope: string | null
  /** Current serialisable form snapshot. */
  value: T
  /** False once the ticket is created (or while submitting) so we stop saving. */
  enabled?: boolean
  /** Only save when the form actually holds something worth restoring. */
  hasContent: (value: T) => boolean
  /** Called once on mount with a restorable draft. */
  onRestore: (data: T) => void
  /** Autosave debounce; keeps typing cheap on low-end phones. */
  debounceMs?: number
}

export type IntakeDraftState = {
  /** Epoch ms of the restored draft, or null when nothing was restored. */
  restoredAt: number | null
  /** Hide the "Draft restored" notice but keep the draft. */
  dismissNotice: () => void
  /** Drop the saved draft (explicit user action). Callers reset the form; autosave stays armed. */
  discardDraft: () => void
  /** Drop the saved draft and stop saving — call after a successful job creation. */
  clearSavedDraft: () => void
}

/**
 * Autosave a form snapshot and restore it when the same intake is reopened.
 *
 * Restore happens once, on mount, before the user types. The draft is cleared
 * only by `clearSavedDraft` (successful creation) or `discardDraft` (explicit
 * user action) — never by simply closing the form.
 */
export function useIntakeDraft<T>({
  kind,
  scope,
  value,
  enabled = true,
  hasContent,
  onRestore,
  debounceMs = 600,
}: IntakeDraftOptions<T>): IntakeDraftState {
  const [restoredAt, setRestoredAt] = useState<number | null>(null)
  const discardedRef = useRef(false)

  // Keep the latest callbacks/values in refs so effects stay stable and the
  // restore effect can run exactly once.
  const onRestoreRef = useRef(onRestore)
  onRestoreRef.current = onRestore
  const hasContentRef = useRef(hasContent)
  hasContentRef.current = hasContent
  const valueRef = useRef(value)
  valueRef.current = value

  useEffect(() => {
    if (!scope) return
    clearExpiredDrafts()
    let found: LoadedDraft<T> | null = null
    try {
      found = loadDraft<T>(kind, scope)
    } catch {
      found = null
    }
    if (!found) return
    onRestoreRef.current(found.data)
    setRestoredAt(found.savedAt)
  }, [kind, scope])

  useEffect(() => {
    if (!scope || !enabled || discardedRef.current) return
    if (!hasContentRef.current(value)) return
    const timer = window.setTimeout(() => {
      saveDraft(kind, scope, valueRef.current)
    }, debounceMs)
    return () => window.clearTimeout(timer)
  }, [kind, scope, enabled, value, debounceMs])

  // A backgrounded tab may never run another timer — flush on hide/unload.
  useEffect(() => {
    if (!scope || !enabled) return
    const flush = () => {
      if (discardedRef.current) return
      if (!hasContentRef.current(valueRef.current)) return
      saveDraft(kind, scope, valueRef.current)
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', flush)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', flush)
    }
  }, [kind, scope, enabled])

  const dismissNotice = useCallback(() => setRestoredAt(null), [])

  const clearSavedDraft = useCallback(() => {
    discardedRef.current = true
    if (scope) clearDraft(kind, scope)
    setRestoredAt(null)
  }, [kind, scope])

  // Explicit discard: forget what was stored, but keep protecting whatever the
  // user types next (the caller resets the form to empty).
  const discardDraft = useCallback(() => {
    if (scope) clearDraft(kind, scope)
    setRestoredAt(null)
  }, [kind, scope])

  return { restoredAt, dismissNotice, discardDraft, clearSavedDraft }
}
