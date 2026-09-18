import type { ReactNode } from 'react'
import { useEditableFieldFocused } from '@/hooks/useEditableFieldFocused'

type Props = {
  children: ReactNode
  /**
   * Hide while a keyboard-opening field has focus. On a phone the software
   * keyboard covers the bottom of the viewport, so a bar parked there would
   * sit either under the keyboard (useless) or over the field being typed
   * into (worse). Pass false only for a bar that must never disappear.
   */
  hideWhileTyping?: boolean
  /** Announced label for the bar's region. */
  label?: string
  className?: string
}

/**
 * Phone-only action bar pinned above Mainspring's bottom tab bar.
 *
 * `--ms-mobile-bar-h` already includes the iOS bottom safe-area inset, so
 * offsetting by it clears both the tab bar and the home indicator. Hidden from
 * `md:` up, where the desktop layout keeps its own in-page actions.
 */
export default function MobileStickyBar({ children, hideWhileTyping = true, label, className }: Props) {
  const typing = useEditableFieldFocused()
  if (hideWhileTyping && typing) return null

  return (
    <div
      role="region"
      aria-label={label}
      data-testid="mobile-sticky-bar"
      className={`print-hide fixed inset-x-0 z-30 border-t md:hidden ${className ?? ''}`}
      style={{
        bottom: 'var(--ms-mobile-bar-h)',
        backgroundColor: 'var(--ms-surface)',
        borderColor: 'var(--ms-border)',
        paddingLeft: 'max(0.75rem, env(safe-area-inset-left, 0px))',
        paddingRight: 'max(0.75rem, env(safe-area-inset-right, 0px))',
        paddingTop: '0.5rem',
        paddingBottom: '0.5rem',
        boxShadow: '0 -6px 18px rgba(31, 23, 18, 0.10)',
      }}
    >
      {children}
    </div>
  )
}

/**
 * Spacer that reserves room for a MobileStickyBar so the last row of content
 * can still be scrolled clear of it.
 */
export function MobileStickyBarSpacer({ height = '4.5rem' }: { height?: string }) {
  return <div aria-hidden="true" className="md:hidden" style={{ height }} />
}
