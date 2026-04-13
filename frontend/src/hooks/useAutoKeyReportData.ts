import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAutoKeyCommissionReport, getAutoKeyReports } from '@/lib/api'

export type AutoKeyReportPreset = 'today' | 'week' | 'month' | 'last_month' | 'all' | 'custom'

type ReportParams = { date_from: string; date_to: string }

function ymd(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function buildReportDateParams(preset: AutoKeyReportPreset, dateFrom?: string, dateTo?: string): ReportParams | undefined {
  if (preset === 'custom' && dateFrom && dateTo) return { date_from: dateFrom, date_to: dateTo }
  const now = new Date()
  if (preset === 'today') {
    const d = ymd(now)
    return { date_from: d, date_to: d }
  }
  if (preset === 'week') {
    const day = now.getDay()
    const mondayOffset = (day + 6) % 7
    const start = new Date(now)
    start.setDate(now.getDate() - mondayOffset)
    const end = new Date(start)
    end.setDate(start.getDate() + 6)
    return { date_from: ymd(start), date_to: ymd(end) }
  }
  if (preset === 'month') {
    const start = new Date(now.getFullYear(), now.getMonth(), 1)
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    return { date_from: ymd(start), date_to: ymd(end) }
  }
  if (preset === 'last_month') {
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    const start = new Date(prev.getFullYear(), prev.getMonth(), 1)
    const end = new Date(prev.getFullYear(), prev.getMonth() + 1, 0)
    return { date_from: ymd(start), date_to: ymd(end) }
  }
  if (preset === 'all') return { date_from: '2000-01-01', date_to: '2099-12-31' }
  return undefined
}

export function useAutoKeyReportData({
  view,
  role,
  preset,
  customDateFrom,
  customDateTo,
}: {
  view: string
  role: string | null
  preset: AutoKeyReportPreset
  customDateFrom?: string
  customDateTo?: string
}) {
  const reportDateParams = useMemo(
    () => buildReportDateParams(preset, customDateFrom, customDateTo),
    [preset, customDateFrom, customDateTo],
  )

  const reportsQuery = useQuery({
    queryKey: ['auto-key-reports', reportDateParams?.date_from, reportDateParams?.date_to],
    queryFn: () => getAutoKeyReports(reportDateParams!).then(r => r.data),
    enabled: view === 'reports' && !!reportDateParams,
  })

  const commissionQuery = useQuery({
    queryKey: ['auto-key-commission', reportDateParams?.date_from, reportDateParams?.date_to],
    queryFn: () =>
      getAutoKeyCommissionReport({
        date_from: reportDateParams!.date_from,
        date_to: reportDateParams!.date_to,
      }).then(r => r.data),
    enabled: view === 'reports' && !!reportDateParams && (role === 'owner' || role === 'manager'),
  })

  return { reportDateParams, reportsQuery, commissionQuery }
}
