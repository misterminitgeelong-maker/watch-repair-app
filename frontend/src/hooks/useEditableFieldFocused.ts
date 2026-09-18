import { useEffect, useState } from 'react'

const EDITABLE_INPUT_TYPES = new Set([
  'text',
  'number',
  'email',
  'tel',
  'search',
  'url',
  'password',
  'date',
  'datetime-local',
  'time',
  'month',
  'week',
])

/**
 * True when the focused element is one the software keyboard opens for.
 *
 * `visualViewport` resize is the precise signal, but it is unavailable in
 * tests and unreliable on older Android WebViews; focus tracking is
 * deterministic and good enough to decide whether a bottom bar would be
 * sitting under the keyboard, on top of the field being typed into.
 */
export function isEditableElement(el: Element | null): boolean {
  if (!el) return false
  const node = el as HTMLElement
  if (node.isContentEditable) return true
  const tag = node.tagName
  if (tag === 'TEXTAREA') return true
  if (tag !== 'INPUT') return false
  const type = (node as HTMLInputElement).type?.toLowerCase() ?? 'text'
  return EDITABLE_INPUT_TYPES.has(type)
}

/**
 * Track whether a keyboard-opening field currently has focus, so callers can
 * get a fixed bottom bar out of the way while someone types.
 */
export function useEditableFieldFocused(): boolean {
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    const sync = () => setFocused(isEditableElement(document.activeElement))
    sync()
    document.addEventListener('focusin', sync)
    document.addEventListener('focusout', sync)
    return () => {
      document.removeEventListener('focusin', sync)
      document.removeEventListener('focusout', sync)
    }
  }, [])

  return focused
}
