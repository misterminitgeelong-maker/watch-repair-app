import { X } from 'lucide-react'

export interface ViewingShop {
  shopNumber: string
  shopName: string | null
}

/** Shown on Scorecard/Rankings/Trends when browsing another shop instead of your own, so it's
 * always obvious whose numbers are on screen — with a one-click way back to your own. */
export function VswtViewingBanner({ viewing, onBack }: { viewing: ViewingShop; onBack: () => void }) {
  return (
    <div
      className="flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-lg mb-4 text-sm"
      style={{ backgroundColor: 'var(--ms-accent-light)', border: '1px solid var(--ms-accent)' }}
    >
      <span style={{ color: 'var(--ms-accent)' }}>
        Viewing <strong>{viewing.shopName ?? `Shop #${viewing.shopNumber}`}</strong> (#{viewing.shopNumber})
      </span>
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-xs font-semibold shrink-0"
        style={{ color: 'var(--ms-accent)' }}
      >
        <X size={13} /> Back to my shop
      </button>
    </div>
  )
}
