import type { MobileCockpitDelta, MobileCockpitMetric, MobileCockpitTone } from '@/lib/api'
import { formatCents } from '@/lib/money'

/**
 * Presentation helpers for the Mobile Services operations cockpit. All the
 * arithmetic (deltas, percentages, good/bad semantics) is done on the server;
 * these only turn it into text and colour, so the two sides cannot disagree.
 */

export const TONE_COLORS: Record<MobileCockpitTone, string> = {
  bad: 'var(--ms-error)',
  warn: '#9A5A00',
  good: '#1A6A3A',
  neutral: 'var(--ms-text-muted)',
}

export const TONE_BACKGROUNDS: Record<MobileCockpitTone, string> = {
  bad: 'rgba(163,56,56,0.12)',
  warn: 'rgba(154,90,0,0.12)',
  good: 'rgba(26,106,58,0.12)',
  neutral: 'var(--ms-bg)',
}

export function formatMetricValue(value: number, unit: 'cents' | 'count'): string {
  if (unit === 'cents') return formatCents(Math.round(value))
  // Averages can be fractional; whole numbers stay whole.
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** "+$1,200 (+20%)", "−3 (−50%)", "+2 (no prior)" … never divides by zero here. */
export function formatDelta(delta: MobileCockpitDelta | null, unit: 'cents' | 'count'): string {
  if (!delta) return '—'
  const sign = delta.abs > 0 ? '+' : delta.abs < 0 ? '−' : ''
  const abs = formatMetricValue(Math.abs(delta.abs), unit)
  if (delta.pct == null) {
    if (delta.abs === 0) return 'no change'
    return `${sign}${abs} (no prior)`
  }
  const pctSign = delta.pct > 0 ? '+' : delta.pct < 0 ? '−' : ''
  return `${sign}${abs} (${pctSign}${Math.abs(delta.pct)}%)`
}

/** Pacing label for a partial week. */
export function comparisonLabel(metric: Pick<MobileCockpitMetric, 'partial' | 'days_elapsed'>, baseline: 'previous' | 'four_week' | 'target'): string {
  const base = baseline === 'previous' ? 'last wk' : baseline === 'four_week' ? '4-wk avg' : 'target'
  if (!metric.partial) return `vs ${base}`
  return `vs ${base} (${metric.days_elapsed}d)`
}

export function formatMinutes(minutes: number): string {
  if (minutes <= 0) return '0h'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m}m`
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

export function formatShopTime(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', timeZone })
}

export function formatShopDay(iso: string | null | undefined, timeZone: string, todayYmd: string): string {
  if (!iso) return 'Unscheduled'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const ymd = d.toLocaleDateString('en-CA', { timeZone })
  const time = formatShopTime(iso, timeZone)
  if (ymd === todayYmd) return `Today ${time}`
  return `${d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short', timeZone })} ${time}`
}

/** Age in whole days from an ISO timestamp; 0 for missing/invalid. */
export function ageDays(iso: string | null | undefined, now: number = Date.now()): number {
  if (!iso) return 0
  const t = new Date(iso).getTime()
  if (!Number.isFinite(t)) return 0
  return Math.max(0, Math.floor((now - t) / 86_400_000))
}
