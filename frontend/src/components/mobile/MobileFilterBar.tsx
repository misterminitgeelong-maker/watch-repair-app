import { useId, useState, type ReactNode } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'

export type ActiveFilter = {
  /** Stable key for React and for tests. */
  key: string
  /** Human-readable summary, e.g. "Status: Unpaid". */
  label: string
  onClear: () => void
}

type Props = {
  /** Free-text search, kept visible at all times when provided. */
  search?: {
    value: string
    onChange: (value: string) => void
    placeholder?: string
    label: string
  }
  /** Filters important enough to stay on screen (usually one). */
  primary?: ReactNode
  /** Everything else, behind the Filters disclosure. */
  secondary?: ReactNode
  /** Chips describing what is currently narrowing the list. */
  activeFilters?: ActiveFilter[]
  onClearAll?: () => void
  /** e.g. "12 of 40 quotes" — announced politely when it changes. */
  resultSummary?: string
}

/**
 * Search-first filter bar for list screens.
 *
 * Phones cannot afford four always-visible dropdowns above a list, but hiding
 * filters silently is worse: a list can end up filtered with no visible reason.
 * So search and the primary filter stay put, the rest collapse, and whatever is
 * actually narrowing the list is spelled out in removable chips.
 */
export default function MobileFilterBar({
  search,
  primary,
  secondary,
  activeFilters = [],
  onClearAll,
  resultSummary,
}: Props) {
  const [showSecondary, setShowSecondary] = useState(false)
  const secondaryId = useId()

  return (
    <div className="mb-4 space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        {search && (
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--ms-text-muted)' }}
            />
            <input
              type="search"
              aria-label={search.label}
              placeholder={search.placeholder}
              value={search.value}
              onChange={e => search.onChange(e.target.value)}
              className="h-11 w-full rounded-lg border pl-9 pr-3 text-base outline-none transition focus:ring-2 sm:h-9 sm:text-sm"
              style={{
                backgroundColor: 'var(--ms-surface)',
                borderColor: 'var(--ms-border-strong)',
                color: 'var(--ms-text)',
                '--tw-ring-color': 'var(--ms-accent-pop)',
              } as React.CSSProperties}
            />
          </div>
        )}
        {primary}
        {secondary && (
          <button
            type="button"
            onClick={() => setShowSecondary(open => !open)}
            aria-expanded={showSecondary}
            aria-controls={secondaryId}
            className="flex min-h-11 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold sm:min-h-9"
            style={{
              backgroundColor: 'var(--ms-surface)',
              borderColor: 'var(--ms-border-strong)',
              color: 'var(--ms-text-mid)',
            }}
          >
            <SlidersHorizontal size={15} aria-hidden="true" />
            {showSecondary ? 'Hide filters' : 'More filters'}
            {activeFilters.length > 0 && (
              <span
                className="rounded-full px-1.5 text-xs font-bold"
                style={{ backgroundColor: 'var(--ms-accent-pop)', color: 'var(--ms-accent)' }}
              >
                {activeFilters.length}
              </span>
            )}
          </button>
        )}
      </div>

      {secondary && (
        <div id={secondaryId} hidden={!showSecondary} className="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap sm:items-center">
          {secondary}
        </div>
      )}

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {activeFilters.map(filter => (
            <span
              key={filter.key}
              className="inline-flex items-center gap-1 rounded-full py-1 pl-3 pr-1 text-xs font-semibold"
              style={{ backgroundColor: 'var(--ms-accent-pop)', color: 'var(--ms-accent)' }}
            >
              {filter.label}
              <button
                type="button"
                onClick={filter.onClear}
                aria-label={`Clear filter ${filter.label}`}
                className="flex h-7 w-7 items-center justify-center rounded-full"
                style={{ color: 'var(--ms-accent)' }}
              >
                <X size={14} aria-hidden="true" />
              </button>
            </span>
          ))}
          {onClearAll && (
            <button
              type="button"
              onClick={onClearAll}
              className="min-h-11 rounded-lg px-3 text-xs font-semibold underline sm:min-h-0"
              style={{ color: 'var(--ms-text-mid)' }}
            >
              Clear all filters
            </button>
          )}
        </div>
      )}

      {resultSummary && (
        <p role="status" aria-live="polite" className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          {resultSummary}
        </p>
      )}
    </div>
  )
}
