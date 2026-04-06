/**
 * scheduling.ts — Conflict detection and validation utilities for time-based
 * scheduling. These are used by both the optimistic UI layer and (mirrored) on
 * the backend. Keeping them here makes the frontend able to show errors before
 * a network round-trip.
 *
 * All checks are intentionally side-effect-free and return structured results
 * so callers can decide how to present the error.
 */

// ── Constants (must mirror backend business-logic) ───────────────────────────

export const BUSINESS_HOURS_START = 8   // 08:00
export const BUSINESS_HOURS_END   = 18  // 18:00 (exclusive upper bound)
export const SLOT_MINUTES         = 15  // snap granularity
export const MIN_DURATION_MINUTES = 15  // minimum booking length

// ── Types ────────────────────────────────────────────────────────────────────

export interface TimeRange {
  start: Date
  end: Date
}

export type ValidationResult =
  | { ok: true }
  | { ok: false; reason: string }

// Minimal shape of a job that the overlap checker needs
export interface ScheduledJob {
  id: string
  assigned_user_id?: string | null
  scheduled_start?: string | null
  scheduled_end?: string | null
}

// ── Snap helpers ─────────────────────────────────────────────────────────────

/** Round a Date down to the nearest SLOT_MINUTES boundary. */
export function snapToSlot(date: Date): Date {
  const d = new Date(date)
  const remainder = d.getMinutes() % SLOT_MINUTES
  d.setMinutes(d.getMinutes() - remainder, 0, 0)
  return d
}

/** Build a Date from a YYYY-MM-DD string + hour + minute. */
export function buildDatetime(dateISO: string, hour: number, minute: number): Date {
  return new Date(`${dateISO}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`)
}

// ── Validation checks (returns a ValidationResult) ───────────────────────────

/**
 * Ensure end is strictly after start and the duration meets the minimum.
 */
export function validateDuration(start: Date, end: Date): ValidationResult {
  if (end <= start) return { ok: false, reason: 'End time must be after start time' }
  const durationMin = (end.getTime() - start.getTime()) / 60_000
  if (durationMin < MIN_DURATION_MINUTES) {
    return { ok: false, reason: `Minimum booking duration is ${MIN_DURATION_MINUTES} minutes` }
  }
  return { ok: true }
}

/**
 * Ensure both start and end fall within configured business hours.
 * The end boundary is exclusive — a booking ending exactly at 18:00 is allowed.
 */
export function validateBusinessHours(start: Date, end: Date): ValidationResult {
  if (
    start.getHours() < BUSINESS_HOURS_START ||
    end.getHours() > BUSINESS_HOURS_END ||
    (end.getHours() === BUSINESS_HOURS_END && end.getMinutes() > 0)
  ) {
    return {
      ok: false,
      reason: `Bookings must fall within business hours (${BUSINESS_HOURS_START}:00–${BUSINESS_HOURS_END}:00)`,
    }
  }
  return { ok: true }
}

/**
 * Statuses that cannot be moved / rescheduled.
 */
const LOCKED_STATUSES = new Set(['collected', 'no_go'])

export function isJobLocked(status: string): boolean {
  return LOCKED_STATUSES.has(status)
}

/**
 * Standard interval overlap check.
 * Returns true when [aStart, aEnd) overlaps with [bStart, bEnd).
 */
export function intervalsOverlap(
  aStart: Date, aEnd: Date,
  bStart: Date, bEnd: Date,
): boolean {
  return aStart < bEnd && aEnd > bStart
}

/**
 * Find jobs that overlap the proposed time range for the given technician.
 * Pass `excludeJobId` to ignore the job being moved.
 */
export function findOverlappingJobs(
  jobs: ScheduledJob[],
  proposedStart: Date,
  proposedEnd: Date,
  technicianId: string | null,
  excludeJobId: string,
): ScheduledJob[] {
  return jobs.filter(j => {
    if (j.id === excludeJobId) return false
    if (!j.scheduled_start || !j.scheduled_end) return false
    // Only check same technician (null === unassigned)
    const sameTech = technicianId === null
      ? j.assigned_user_id == null
      : j.assigned_user_id === technicianId
    if (!sameTech) return false
    return intervalsOverlap(
      proposedStart, proposedEnd,
      new Date(j.scheduled_start), new Date(j.scheduled_end),
    )
  })
}

/**
 * Run all frontend validations in sequence and return the first failure.
 * Does NOT check overlap (that requires the full jobs list; call separately).
 */
export function validateReschedule(start: Date, end: Date): ValidationResult {
  const durationCheck = validateDuration(start, end)
  if (!durationCheck.ok) return durationCheck
  const hoursCheck = validateBusinessHours(start, end)
  if (!hoursCheck.ok) return hoursCheck
  return { ok: true }
}
