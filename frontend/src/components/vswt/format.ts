import type { VswtKpiType } from '@/lib/api'

/** Formats one VSWT KPI value per its type — mirrors the reference app's fmtVal(). */
export function fmtVswtVal(value: number | null | undefined, type: VswtKpiType): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (type === 'currency') return '$' + Math.round(value).toLocaleString()
  if (type === 'percent') return (value >= 0 ? '+' : '') + (value * 100).toFixed(1) + '%'
  if (type === 'ratio') return value.toFixed(1)
  return Math.round(value).toLocaleString()
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
