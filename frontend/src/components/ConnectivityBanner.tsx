import { Wifi, WifiOff } from 'lucide-react'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'

/**
 * Compact app-level connectivity banner.
 *
 * Pinned above the app rather than inserted into the layout, so nothing
 * reflows when the connection flaps, and `pointer-events: none` keeps cached,
 * read-only screens fully tappable underneath. Announced politely (not
 * assertively) so it never interrupts a screen reader mid-sentence, and it
 * pairs an icon with wording so the state is not carried by colour alone.
 */
export default function ConnectivityBanner() {
  const { online, justReconnected } = useOnlineStatus()

  if (online && !justReconnected) {
    // Keep the live region mounted so the recovery message is announced.
    return <div role="status" aria-live="polite" className="sr-only" />
  }

  const offline = !online
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="connectivity-banner"
      className="print-hide fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-2 text-center text-sm font-medium"
      style={{
        minHeight: '2.25rem',
        pointerEvents: 'none',
        paddingTop: 'max(0.4rem, env(safe-area-inset-top, 0px))',
        paddingBottom: '0.4rem',
        paddingLeft: 'max(0.75rem, env(safe-area-inset-left, 0px))',
        paddingRight: 'max(0.75rem, env(safe-area-inset-right, 0px))',
        backgroundColor: offline ? '#F6E3C4' : '#DFF3E6',
        color: offline ? '#6A4A10' : '#1F6D4C',
        borderBottom: `1px solid ${offline ? '#D9B978' : '#A9D8BC'}`,
      }}
    >
      {offline ? <WifiOff size={15} aria-hidden="true" /> : <Wifi size={15} aria-hidden="true" />}
      <span>
        {offline
          ? 'No internet connection — saved screens still work; new changes need a connection.'
          : 'Back online — refreshing.'}
      </span>
    </div>
  )
}
