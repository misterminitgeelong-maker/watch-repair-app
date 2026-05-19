export function defaultReportFromDate(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

export function defaultReportToDate(): string {
  return new Date().toISOString().slice(0, 10)
}

export function toIsoStart(ymd: string): string {
  return `${ymd}T00:00:00.000Z`
}

export function toIsoEnd(ymd: string): string {
  return `${ymd}T23:59:59.999Z`
}
