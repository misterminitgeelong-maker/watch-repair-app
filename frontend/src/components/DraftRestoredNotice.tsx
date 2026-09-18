import { RotateCcw } from 'lucide-react'
import { describeDraftAge } from '@/lib/draftStorage'

type Props = {
  /** Epoch ms of the restored draft; nothing renders when null. */
  savedAt: number | null
  onDiscard: () => void
  /** True when the draft referenced photos that cannot be restored. */
  photosNeedReselect?: boolean
  photoCount?: number
}

/**
 * "Draft restored" notice shown at the top of an intake form. Announced through
 * a polite live region, and paired with an icon + text so status is never
 * carried by colour alone.
 */
export default function DraftRestoredNotice({ savedAt, onDiscard, photosNeedReselect, photoCount = 0 }: Props) {
  if (savedAt == null) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-4 rounded-lg border px-3 py-2.5"
      style={{ borderColor: 'var(--ms-accent)', backgroundColor: '#FEF0DC' }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex min-w-0 items-center gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
          <RotateCcw size={15} aria-hidden="true" style={{ color: 'var(--ms-accent)', flexShrink: 0 }} />
          <span>
            <span className="font-semibold">Draft restored</span>
            <span style={{ color: 'var(--ms-text-mid)' }}> — saved {describeDraftAge(savedAt)}.</span>
          </span>
        </p>
        <button
          type="button"
          onClick={onDiscard}
          className="min-h-11 shrink-0 rounded-lg border px-3 text-sm font-semibold"
          style={{ borderColor: 'var(--ms-accent)', color: 'var(--ms-accent)', backgroundColor: 'transparent' }}
        >
          Discard draft
        </button>
      </div>
      {photosNeedReselect && (
        <p className="mt-1.5 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
          {photoCount === 1 ? '1 photo was' : `${photoCount} photos were`} attached before — photos can&rsquo;t be
          saved in a draft, so please take or choose them again.
        </p>
      )}
    </div>
  )
}
