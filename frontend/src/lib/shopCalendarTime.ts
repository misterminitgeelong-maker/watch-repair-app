/** Shop calendar uses the same YYYY-MM-DD labels as the API `date_from` / `date_to` filter (see `schedule_calendar_timezone`). */

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

/** Gregorian calendar add; Y-M-D is a civil date label, not a UTC instant. */
export function civilAddDays(ymd: string, deltaDays: number): string {
  const [y, m, d] = ymd.split('-').map(Number)
  const t = Date.UTC(y, m - 1, d) + deltaDays * 86400000
  const x = new Date(t)
  return `${x.getUTCFullYear()}-${pad2(x.getUTCMonth() + 1)}-${pad2(x.getUTCDate())}`
}

/** Monday–Sunday week (Monday first) containing this civil day. */
export function civilMondayOfWeekContaining(ymd: string): string {
  const [y, m, d] = ymd.split('-').map(Number)
  const utc = Date.UTC(y, m - 1, d)
  const dow = new Date(utc).getUTCDay()
  const mondayOffset = (dow + 6) % 7
  const monMs = utc - mondayOffset * 86400000
  const mon = new Date(monMs)
  return `${mon.getUTCFullYear()}-${pad2(mon.getUTCMonth() + 1)}-${pad2(mon.getUTCDate())}`
}

/** Wall clock (hour / minute) in `timeZone` for an API ISO timestamp. */
export function hourMinuteInTimeZone(isoUtc: string, timeZone: string): { hour: number; minute: number } {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const parts = dtf.formatToParts(new Date(isoUtc))
  const g = (ty: Intl.DateTimeFormatPartTypes) => Number(parts.find((p) => p.type === ty)?.value ?? '0')
  return { hour: g('hour'), minute: g('minute') }
}

/**
 * UTC instant for civil Y-M-D + H:M interpreted in `timeZone`.
 * Binary search (DST-safe enough for shop scheduling).
 */
export function zonedWallTimeToUtcIso(ymd: string, hour: number, minute: number, timeZone: string): string {
  const [y, mo, day] = ymd.split('-').map(Number)
  const target = { y, m: mo, d: day, hour, minute }
  function cmp(
    a: typeof target,
    b: typeof target,
  ) {
    if (a.y !== b.y) return a.y - b.y
    if (a.m !== b.m) return a.m - b.m
    if (a.d !== b.d) return a.d - b.d
    if (a.hour !== b.hour) return a.hour - b.hour
    return a.minute - b.minute
  }
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: 'numeric',
    hour12: false,
  })
  function read(ms: number) {
    const parts = dtf.formatToParts(new Date(ms))
    const g = (t: Intl.DateTimeFormatPartTypes) => Number(parts.find((p) => p.type === t)?.value ?? '0')
    return { y: g('year'), m: g('month'), d: g('day'), hour: g('hour'), minute: g('minute') }
  }
  let lo = Date.UTC(y, mo - 1, day, 0, 0, 0) - 48 * 3600000
  let hi = Date.UTC(y, mo - 1, day, 23, 59, 0) + 48 * 3600000
  for (let i = 0; i < 64 && lo <= hi; i++) {
    const mid = Math.floor((lo + hi) / 2)
    const w = read(mid)
    const c = cmp(w, target)
    if (c === 0) return new Date(mid).toISOString()
    if (c < 0) lo = mid + 1
    else hi = mid - 1
  }
  return new Date(Date.UTC(y, mo - 1, day, 12, 0, 0)).toISOString()
}
