import type { JobStatus } from '@/lib/api'
import { hourMinuteInTimeZone, zonedWallTimeToUtcIso } from '@/lib/shopCalendarTime'

/**
 * Pure helpers, constants, types, and the SLA chip badge extracted from
 * AutoKeyJobsPage. No component state or API calls — safe to unit test and
 * reuse. Kept together because they form the dispatch/scheduling vocabulary
 * that page (and its sub-components) share.
 */

export const STATUSES: JobStatus[] = [
  'awaiting_quote',
  'quote_sent',
  'booking_confirmed',
  'en_route',
  'booking_on_hold',
  'booking_completed',
  'failed_job',
]

export const AUTO_KEY_CLOSED_STATUSES = ['booking_completed', 'failed_job'] as const
export const AUTO_KEY_ACTIVE_STATUSES = [
  'awaiting_quote',
  'awaiting_customer_details',
  'quote_sent',
  'awaiting_booking_confirmation',
  'booking_confirmed',
  'en_route',
  'on_site',
  'booking_on_hold',
] as const

export function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

export function ymdLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function isYmd(value: string | null | undefined): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value)
}

export function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

// ── Dispatch SLA chips ────────────────────────────────────────────────────────
/** Statuses where the SLA clock stops (the tech is en route / on site / done). */
const SLA_STOP_CLOCK_STATUSES = new Set<string>([
  'en_route',
  'on_site',
  'work_completed',
  'invoice_paid',
  'booking_completed',
  'failed_job',
])

export type SlaChipKind = 'late' | 'at_risk' | 'aging'
export interface SlaChip { kind: SlaChipKind; label: string }

const SLA_AT_RISK_MINUTES = 30
const SLA_UNSCHEDULED_AGING_HOURS = 24

/** Derive an at-a-glance SLA chip for a job from existing fields (pure, no API). */
export function computeSlaChip(
  job: { scheduled_at?: string | null; status: string; created_at: string },
  now: number = Date.now(),
): SlaChip | null {
  if (SLA_STOP_CLOCK_STATUSES.has(job.status)) return null

  if (job.scheduled_at) {
    const scheduled = new Date(job.scheduled_at).getTime()
    if (Number.isFinite(scheduled)) {
      if (scheduled < now) return { kind: 'late', label: 'Late' }
      if (scheduled <= now + SLA_AT_RISK_MINUTES * 60_000) return { kind: 'at_risk', label: 'At risk' }
    }
    return null
  }

  // Unscheduled active job that has been sitting too long.
  const created = new Date(job.created_at).getTime()
  if (Number.isFinite(created) && now - created >= SLA_UNSCHEDULED_AGING_HOURS * 3_600_000) {
    return { kind: 'aging', label: 'Unscheduled aging' }
  }
  return null
}

/** Order by saved visit_order (when present) first, then appointment time. */
export function compareByVisitThenTime(
  a: { visit_order?: number | null; scheduled_at?: string | null },
  b: { visit_order?: number | null; scheduled_at?: string | null },
): number {
  const va = a.visit_order ?? null
  const vb = b.visit_order ?? null
  if (va !== null && vb !== null && va !== vb) return va - vb
  if (va !== null && vb === null) return -1
  if (va === null && vb !== null) return 1
  const ta = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0
  const tb = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0
  return ta - tb
}

/** Higher = more urgent. Used to sort the dispatch list by risk. */
export function slaRiskWeight(chip: SlaChip | null): number {
  if (!chip) return 0
  return chip.kind === 'late' ? 3 : chip.kind === 'at_risk' ? 2 : 1
}

export function dateFromYmdLocal(ymd: string): Date {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Reschedule onto target civil YYYY-MM-DD in shop calendar, keeping wall time in `shopTimeZone`, or 09:00 if unscheduled. */
export function isoScheduledOnDayKeepingShopTime(
  jobId: string,
  targetDayYmd: string,
  jobs: Array<{ id: string; scheduled_at?: string }>,
  shopTimeZone: string,
): string {
  const job = jobs.find((j) => j.id === jobId)
  let hour = 9
  let minute = 0
  if (job?.scheduled_at) {
    const hm = hourMinuteInTimeZone(job.scheduled_at, shopTimeZone)
    hour = hm.hour
    minute = hm.minute
  }
  return zonedWallTimeToUtcIso(targetDayYmd, hour, minute, shopTimeZone)
}

/** Local hour rows for week grid: 7:00–21:00 slots (7am–9pm). */
export const WEEK_SCHEDULE_HOURS = Array.from({ length: 15 }, (_, i) => 7 + i)
export const WEEK_UNSCHEDULED_DROP_ID = 'week-unscheduled'
export const WEEK_DAY_DROP_PREFIX = 'week-day:'
export const WEEK_SLOT_DROP_PREFIX = 'week-slot:'

export function weekDayDropId(dayStr: string) {
  return `${WEEK_DAY_DROP_PREFIX}${dayStr}`
}

export function weekSlotDropId(dayStr: string, hour: number) {
  return `${WEEK_SLOT_DROP_PREFIX}${dayStr}:${hour}`
}

export function weekSlotScheduledAt(dayStr: string, hour: number, shopTimeZone: string): string {
  return new Date(zonedWallTimeToUtcIso(dayStr, hour, 0, shopTimeZone)).toISOString()
}

export function stopDragControlPropagation(event: { stopPropagation: () => void }) {
  event.stopPropagation()
}

export interface WeekSchedulerJob {
  id: string
  job_number: string
  title: string
  scheduled_at?: string
  customer_id?: string
  customer_name?: string | null
  customer_phone?: string | null
  assigned_user_id?: string
  status?: JobStatus
  vehicle_make?: string
  vehicle_model?: string
  vehicle_year?: number
  registration_plate?: string
  key_type?: string
  key_quantity?: number
  job_type?: string
  job_address?: string
  tech_notes?: string
}

export function weekJobVehicleSummary(job: WeekSchedulerJob) {
  const vehicle = [job.vehicle_year, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')
  return [vehicle || undefined, job.registration_plate || undefined].filter(Boolean).join(' · ') || undefined
}

export function weekJobSecondarySummary(job: WeekSchedulerJob, customerName?: string, assignedTechName?: string) {
  const bits = [
    customerName,
    job.job_type || undefined,
    assignedTechName ? `Tech: ${assignedTechName}` : undefined,
  ].filter(Boolean)
  return bits.length ? bits.join(' · ') : undefined
}

/** Monday–Sunday week in local time containing YYYY-MM-DD anchor */
export function weekRangeFromYmd(ymd: string): { date_from: string; date_to: string } {
  const anchor = dateFromYmdLocal(ymd)
  const day = anchor.getDay()
  const diff = anchor.getDate() - day + (day === 0 ? -6 : 1)
  const mon = new Date(anchor)
  mon.setDate(diff)
  const sun = new Date(mon)
  sun.setDate(mon.getDate() + 6)
  return { date_from: ymdLocal(mon), date_to: ymdLocal(sun) }
}

export function monthRangeFromYmd(ymd: string): { date_from: string; date_to: string } {
  const [y, m] = ymd.split('-').map(Number)
  const pad = (n: number) => String(n).padStart(2, '0')
  const start = `${y}-${pad(m)}-01`
  const last = new Date(y, m, 0)
  const end = `${y}-${pad(m)}-${pad(last.getDate())}`
  return { date_from: start, date_to: end }
}

export function nextMobileStatus(status: JobStatus): JobStatus | null {
  if (status === 'awaiting_quote') return 'quote_sent'
  if (status === 'quote_sent') return 'awaiting_booking_confirmation'
  if (status === 'awaiting_booking_confirmation') return 'booking_confirmed'
  if (status === 'booking_confirmed') return 'en_route'
  if (status === 'en_route') return 'on_site'
  if (status === 'on_site') return 'work_completed'
  return null
}
