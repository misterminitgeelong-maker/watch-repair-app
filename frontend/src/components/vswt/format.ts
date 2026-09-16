import type { VswtKpiGroup, VswtKpiType } from '@/lib/api'

/** Every KPI group, in display order — shared by Directory, Shop Report, and anywhere else a KPI
 * group picker is needed, so the list is only ever spelled out once. */
export const VSWT_KPI_GROUPS: VswtKpiGroup[] = [
  'Headline', 'Budget & Last Year', 'Conversion', 'Category Sales', 'Category Jobs', 'Watch & Service Detail',
]

/** Formats one VSWT KPI value per its type — mirrors the reference app's fmtVal(). */
export function fmtVswtVal(value: number | null | undefined, type: VswtKpiType): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (type === 'currency') return '$' + Math.round(value).toLocaleString()
  if (type === 'percent') return (value >= 0 ? '+' : '') + (value * 100).toFixed(1) + '%'
  if (type === 'ratio') return value.toFixed(1)
  return Math.round(value).toLocaleString()
}

/** Formats movement without turning a change between two percentage rates into a misleading
 * percentage-of-a-percentage. For example, -20.5% to -5.4% is +15.1 percentage points. */
export function fmtVswtDelta(
  value: number | null | undefined,
  relativeChange: number | null | undefined,
  type: VswtKpiType,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (type === 'percent') {
    const points = value * 100
    return `${points > 0 ? '+' : ''}${points.toFixed(1)} pp`
  }
  const absolute = `${value > 0 ? '+' : ''}${fmtVswtVal(value, type)}`
  if (relativeChange === null || relativeChange === undefined || Number.isNaN(relativeChange)) return absolute
  return `${absolute} (${relativeChange > 0 ? '+' : ''}${(relativeChange * 100).toFixed(1)}%)`
}

export type RankTone = 'good' | 'warn' | 'bad' | 'neutral'

/** Buckets a rank (1 = best) into a good/warn/bad tone given the field size — top third good,
 * middle third warn, bottom third bad. Matches the reference app's rankColor() thresholds. */
export function rankTone(rank: number | null | undefined, n: number): RankTone {
  if (rank === null || rank === undefined || n <= 1) return 'neutral'
  const pct = (rank - 1) / (n - 1)
  if (pct <= 0.33) return 'good'
  if (pct <= 0.66) return 'warn'
  return 'bad'
}

/** Badge/cell background + text CSS var pair for a rank tone — reuses the same badge tokens
 * as job-status pills elsewhere in the app, so the heatmap fits the rest of Mainspring. */
export function rankToneColors(tone: RankTone): { bg: string; fg: string } {
  switch (tone) {
    case 'good': return { bg: 'var(--ms-badge-done-bg)', fg: 'var(--ms-badge-done-text)' }
    case 'warn': return { bg: 'var(--ms-badge-wait-bg)', fg: 'var(--ms-badge-wait-text)' }
    case 'bad': return { bg: 'var(--ms-badge-alert-bg)', fg: 'var(--ms-badge-alert-text)' }
    default: return { bg: 'var(--ms-badge-neutral-bg)', fg: 'var(--ms-badge-neutral-text)' }
  }
}

export function rankToneBadgeVariant(tone: RankTone): 'success' | 'warning' | 'danger' | 'default' {
  switch (tone) {
    case 'good': return 'success'
    case 'warn': return 'warning'
    case 'bad': return 'danger'
    default: return 'default'
  }
}
