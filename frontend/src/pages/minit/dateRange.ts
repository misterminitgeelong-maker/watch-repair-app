// Minit HQ reports are read in Melbourne time, so a picked day runs Melbourne midnight to midnight
// (not UTC midnight, which would start the day at 11am Melbourne time).
const HQ_TIME_ZONE = 'Australia/Melbourne'

function ymdInHqZone(d: Date): string {
  // en-CA formats as YYYY-MM-DD
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: HQ_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(d)
}

/** UTC offset of the HQ zone at the given instant, in minutes (e.g. 660 for AEDT). */
function hqOffsetMinutes(at: Date): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: HQ_TIME_ZONE, hourCycle: 'h23',
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).formatToParts(at)
  const get = (t: string) => Number(parts.find(p => p.type === t)?.value)
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return Math.round((asUtc - Math.floor(at.getTime() / 1000) * 1000) / 60000)
}

/** The UTC instant at which the HQ-zone wall clock reads ymd + h:m:s.ms. */
function hqWallToUtc(ymd: string, h: number, m: number, s: number, ms: number): Date {
  const [y, mo, d] = ymd.split('-').map(Number)
  const naive = Date.UTC(y, mo - 1, d, h, m, s, ms)
  // Two passes handle a DST change falling between the guess and the real offset.
  let offset = hqOffsetMinutes(new Date(naive))
  offset = hqOffsetMinutes(new Date(naive - offset * 60000))
  return new Date(naive - offset * 60000)
}

export function defaultReportFromDate(): string {
  return ymdInHqZone(new Date(Date.now() - 30 * 86_400_000))
}

export function defaultReportToDate(): string {
  return ymdInHqZone(new Date())
}

export function toIsoStart(ymd: string): string {
  return hqWallToUtc(ymd, 0, 0, 0, 0).toISOString()
}

export function toIsoEnd(ymd: string): string {
  return hqWallToUtc(ymd, 23, 59, 59, 999).toISOString()
}
