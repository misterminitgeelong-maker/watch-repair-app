import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Download, Info, RefreshCw, Target, Timer, TrendingUp } from 'lucide-react'
import { Button, Card, Spinner } from '@/components/ui'
import {
  downloadAutoKeyFinanceExport,
  getApiErrorMessage,
  getAutoKeyFinance,
  type MobileCockpitTone,
  type MobileFinanceMetric,
  type MobileFinanceParams,
  type MobileFinancePreset,
  type MobileFinanceReport as FinanceReport,
} from '@/lib/api'
import { TONE_BACKGROUNDS, TONE_COLORS, formatDelta, formatMetricValue, formatMinutes } from '@/lib/cockpitFormat'
import { FINANCE_PRESETS, drillHref, focusHref } from '@/lib/cockpitFocus'
import { formatCents } from '@/lib/money'

function fmt(value: number | null, unit: MobileFinanceMetric['unit']): string {
  if (value == null) return '—'
  if (unit === 'pct') return `${value}%`
  if (unit === 'minutes') return formatMinutes(Math.round(value))
  return formatMetricValue(value, unit)
}

function MetricTile({ metric, previousLabel }: { metric: MobileFinanceMetric; previousLabel: string }) {
  const href = drillHref(metric.drill)
  const unavailable = metric.current == null
  const body = (
    <Card className="p-4 min-w-0 h-full" hoverable={!!href}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--ms-text-muted)' }}>{metric.label}</p>
        <span title={metric.definition} aria-label={metric.definition}><Info size={13} style={{ color: 'var(--ms-text-muted)' }} /></span>
      </div>
      <p className="mt-1 text-2xl font-extrabold tabular-nums" style={{ color: unavailable ? 'var(--ms-text-muted)' : 'var(--ms-text)' }}>{fmt(metric.current, metric.unit)}</p>
      {unavailable ? (
        <p className="text-[11px] mt-1" style={{ color: 'var(--ms-text-muted)' }}>Not available — see data quality</p>
      ) : (
        <>
          <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
            {previousLabel} {fmt(metric.previous, metric.unit)}
            {metric.sample != null && metric.key !== 'quotes_sent' && ` · n=${metric.sample}`}
          </p>
          <p className="mt-1 text-xs font-semibold tabular-nums" style={{ color: TONE_COLORS[metric.vs_previous_tone] }}>{formatDelta(metric.vs_previous, metric.unit === 'cents' ? 'cents' : 'count')}</p>
        </>
      )}
    </Card>
  )
  return href ? <Link to={href} className="block min-w-0" aria-label={`${metric.label}: open the records behind this figure`}>{body}</Link> : <div className="min-w-0">{body}</div>
}

function Bars({ rows, valueKey, unit, label }: { rows: FinanceReport['trend']['weeks']; valueKey: 'collected_cents' | 'invoiced_cents' | 'booked_cents' | 'jobs_completed'; unit: 'cents' | 'count'; label: string }) {
  const max = Math.max(1, ...rows.map(r => r[valueKey]))
  const H = 72
  return (
    <div>
      <p className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
      <div className="flex items-end gap-1" style={{ height: H + 18 }} role="img" aria-label={`${label}, weekly, last 13 weeks`}>
        {rows.map((r, i) => {
          const v = r[valueKey]
          const h = Math.round((v / max) * H)
          const last = i === rows.length - 1
          return (
            <div key={r.week_start} className="flex-1 flex flex-col items-center justify-end min-w-0" title={`Week of ${r.week_start}: ${unit === 'cents' ? formatCents(v) : v}`}>
              <div className="w-full rounded-t" style={{ height: Math.max(h, v > 0 ? 3 : 1), backgroundColor: last ? 'var(--ms-accent)' : 'var(--ms-accent-light)' }} />
              <span className="text-[9px] mt-1 truncate w-full text-center" style={{ color: 'var(--ms-text-muted)' }}>{r.week_start.slice(5)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export interface MobileFinanceReportProps {
  params: MobileFinanceParams
  onParamsChange: (next: MobileFinanceParams) => void
  /** Called with the resolved shop-local period so sibling sections can use the same dates. */
  onPeriodResolved?: (period: { start: string; end: string }) => void
  canExport: boolean
}

export default function MobileFinanceReport({ params, onParamsChange, onPeriodResolved, canExport }: MobileFinanceReportProps) {
  const enabled = params.period !== 'custom' || (!!params.date_from && !!params.date_to)
  const query = useQuery({
    queryKey: ['auto-key-finance', params.period, params.date_from, params.date_to],
    queryFn: () => getAutoKeyFinance(params).then(r => r.data),
    enabled,
    staleTime: 60_000,
    placeholderData: previous => previous,
  })
  const [exporting, setExporting] = useState<'summary' | 'invoices' | null>(null)
  const [exportError, setExportError] = useState('')
  const period = query.data?.period
  useEffect(() => {
    if (period && onPeriodResolved) onPeriodResolved({ start: period.start, end: period.end })
  }, [period, onPeriodResolved])

  async function exportCsv(kind: 'summary' | 'invoices') {
    setExporting(kind)
    setExportError('')
    try {
      const { data } = await downloadAutoKeyFinanceExport({ ...params, kind })
      downloadBlob(data, `mobile-finance-${kind}-${period?.start ?? ''}-to-${period?.end ?? ''}.csv`)
    } catch (e) {
      setExportError(getApiErrorMessage(e, 'Export failed'))
    } finally {
      setExporting(null)
    }
  }

  const data = query.data
  const previousLabel = data ? `prev ${data.period.previous_start.slice(5)}–${data.period.previous_end.slice(5)}` : 'prev'
  const money = data?.metrics.filter(m => ['booked', 'completed', 'invoiced', 'collected', 'outstanding'].includes(m.key)) ?? []
  const profit = data?.metrics.filter(m => ['commission', 'contribution', 'aov'].includes(m.key)) ?? []
  const activity = data?.metrics.filter(m => ['jobs_created', 'jobs_completed', 'jobs_per_working_day', 'quotes_sent'].includes(m.key)) ?? []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>Mobile Services finance</h2>
          {data && (
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
              {data.period.label} · {data.period.start} → {data.period.end} · {data.period.working_days} working day{data.period.working_days === 1 ? '' : 's'}{data.period.complete ? '' : ' so far'} · shop time {data.timezone}
              {query.isFetching && ' · refreshing…'}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Report period"
            value={params.period}
            onChange={e => onParamsChange({ ...params, period: e.target.value as MobileFinancePreset })}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            {FINANCE_PRESETS.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
          </select>
          {params.period === 'custom' && (
            <>
              <input type="date" aria-label="From" value={params.date_from ?? ''} onChange={e => onParamsChange({ ...params, date_from: e.target.value })} className="rounded-lg px-2 py-1.5 text-xs" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }} />
              <input type="date" aria-label="To" value={params.date_to ?? ''} onChange={e => onParamsChange({ ...params, date_to: e.target.value })} className="rounded-lg px-2 py-1.5 text-xs" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }} />
            </>
          )}
          {canExport && (
            <>
              <Button type="button" variant="secondary" size="sm" disabled={!data || exporting != null} onClick={() => void exportCsv('summary')}><Download size={14} /> {exporting === 'summary' ? 'Exporting…' : 'Summary CSV'}</Button>
              <Button type="button" variant="secondary" size="sm" disabled={!data || exporting != null} onClick={() => void exportCsv('invoices')}><Download size={14} /> {exporting === 'invoices' ? 'Exporting…' : 'Invoices CSV'}</Button>
            </>
          )}
        </div>
      </div>
      {exportError && <p className="text-xs" style={{ color: 'var(--ms-error)' }}>{exportError}</p>}

      {!enabled && <Card className="p-4"><p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Pick a from and to date for the custom period.</p></Card>}
      {enabled && query.isLoading && <Spinner />}
      {enabled && query.isError && (
        <Card className="p-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(query.error, 'Could not load the finance report.')}</p>
          <Button type="button" variant="secondary" onClick={() => void query.refetch()}><RefreshCw size={14} /> Retry</Button>
        </Card>
      )}

      {data && (
        <>
          {/* Money ladder */}
          <section aria-label="Money">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {money.map(m => <MetricTile key={m.key} metric={m} previousLabel={previousLabel} />)}
            </div>
          </section>

          {/* Target + profitability + conversion */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2"><Target size={15} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Target</h3></div>
              {data.target ? (
                <>
                  <p className="text-2xl font-extrabold tabular-nums" style={{ color: TONE_COLORS[data.target.tone] }}>{data.target.attainment_pct == null ? '—' : `${data.target.attainment_pct}%`}</p>
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{formatCents(data.target.collected_cents)} collected of {formatCents(data.target.to_date_cents)} due to date ({formatCents(data.target.period_cents)} for the full period)</p>
                  <p className="mt-1 text-xs font-semibold tabular-nums" style={{ color: TONE_COLORS[data.target.tone] }}>Variance {formatDelta({ abs: data.target.variance_cents, pct: null }, 'cents').replace(' (no prior)', '')}</p>
                  <p className="text-[11px] mt-1" style={{ color: 'var(--ms-text-muted)' }}>{data.definitions.target}</p>
                </>
              ) : (
                <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No weekly cash target set. An owner can set one on the Today tab.</p>
              )}
            </Card>
            <Card className="p-4">
              <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--ms-text)' }}>After commission</h3>
              <div className="space-y-2">
                {profit.map(m => (
                  <div key={m.key} className="flex items-baseline justify-between gap-2 text-sm">
                    <span title={m.definition} style={{ color: 'var(--ms-text-muted)' }}>{m.label}</span>
                    <span className="text-right">
                      <span className="font-bold tabular-nums" style={{ color: m.current == null ? 'var(--ms-text-muted)' : 'var(--ms-text)' }}>{fmt(m.current, m.unit)}</span>
                      {m.current != null && <span className="block text-[11px] tabular-nums" style={{ color: TONE_COLORS[m.vs_previous_tone] }}>{formatDelta(m.vs_previous, 'cents')}</span>}
                    </span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] mt-2" style={{ color: 'var(--ms-text-muted)' }}>{data.definitions.contribution}</p>
            </Card>
            <Card className="p-4">
              <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--ms-text)' }}>Conversion</h3>
              <div className="space-y-2">
                {data.conversion.map(c => (
                  <div key={c.key} className="flex items-baseline justify-between gap-2 text-sm" title={c.definition}>
                    <span style={{ color: 'var(--ms-text-muted)' }}>{c.label}</span>
                    <span className="text-right">
                      <span className="font-bold tabular-nums" style={{ color: 'var(--ms-text)' }}>{c.pct == null ? '—' : `${c.pct}%`}</span>
                      <span className="block text-[11px] tabular-nums" style={{ color: TONE_COLORS[c.vs_previous_tone] }}>{c.numerator}/{c.denominator}{c.previous_pct != null ? ` · prev ${c.previous_pct}%` : ' · no prior'}</span>
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Activity */}
          <section aria-label="Activity">
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              {activity.map(m => <MetricTile key={m.key} metric={m} previousLabel={previousLabel} />)}
            </div>
          </section>

          {/* Receivables + trend */}
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="p-4 lg:col-span-2">
              <div className="flex items-center justify-between gap-2 mb-2">
                <h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Receivables ageing</h3>
                <Link to={focusHref('unpaid_invoices')} className="text-xs font-semibold" style={{ color: 'var(--ms-accent)' }}>All unpaid →</Link>
              </div>
              <p className="text-2xl font-extrabold tabular-nums" style={{ color: data.ar_ageing.overdue_cents > 0 ? TONE_COLORS.bad : 'var(--ms-text)' }}>{formatCents(data.ar_ageing.total_cents)}</p>
              <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>{formatCents(data.ar_ageing.overdue_cents)} overdue{data.ar_ageing.overdue_pct != null ? ` (${data.ar_ageing.overdue_pct}%)` : ''} · as of now, not period based</p>
              <div className="space-y-1.5">
                {data.ar_ageing.buckets.map((b, i) => {
                  const tone: MobileCockpitTone = i === 0 ? 'neutral' : i === 1 ? 'warn' : 'bad'
                  const share = data.ar_ageing.total_cents ? (b.cents / data.ar_ageing.total_cents) * 100 : 0
                  return (
                    <div key={b.key} className="text-xs">
                      <div className="flex items-baseline justify-between gap-2">
                        <span style={{ color: 'var(--ms-text-muted)' }}>{b.label}</span>
                        <span className="font-semibold tabular-nums" style={{ color: b.cents > 0 ? TONE_COLORS[tone] : 'var(--ms-text-muted)' }}>{formatCents(b.cents)}{b.count ? ` · ${b.count}` : ''}</span>
                      </div>
                      <div className="h-1 rounded-full mt-0.5" style={{ backgroundColor: 'var(--ms-border)' }}><div className="h-full rounded-full" style={{ width: `${share}%`, backgroundColor: TONE_COLORS[tone] === 'var(--ms-text-muted)' ? 'var(--ms-accent)' : TONE_COLORS[tone] }} /></div>
                    </div>
                  )
                })}
              </div>
              {data.ar_ageing.open_invoices.length > 0 && (
                <div className="mt-3 pt-2 space-y-1" style={{ borderTop: '1px dashed var(--ms-border)' }}>
                  {data.ar_ageing.open_invoices.slice(0, 5).map(inv => (
                    <Link key={inv.invoice_id} to={`/auto-key/${inv.job_id}`} className="flex items-center justify-between gap-2 text-xs">
                      <span className="truncate" style={{ color: 'var(--ms-text)' }}><strong style={{ color: 'var(--ms-accent)' }}>#{inv.job_number}</strong> {inv.customer_name ?? inv.invoice_number}</span>
                      <span className="shrink-0 tabular-nums" style={{ color: inv.age_days > 7 ? TONE_COLORS.bad : 'var(--ms-text-muted)' }}>{inv.age_days}d · {formatCents(inv.total_cents)}</span>
                    </Link>
                  ))}
                </div>
              )}
            </Card>
            <Card className="p-4 lg:col-span-3">
              <div className="flex items-center gap-2 mb-3"><TrendingUp size={15} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>13-week trend</h3><span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>weeks ending in the period · 4-wk avg {formatCents(data.trend.averages.collected_cents.last_4_avg ?? 0)} · 13-wk avg {formatCents(data.trend.averages.collected_cents.last_13_avg ?? 0)} collected</span></div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Bars rows={data.trend.weeks} valueKey="collected_cents" unit="cents" label="Cash collected" />
                <Bars rows={data.trend.weeks} valueKey="invoiced_cents" unit="cents" label="Invoiced" />
                <Bars rows={data.trend.weeks} valueKey="booked_cents" unit="cents" label="Booked" />
                <Bars rows={data.trend.weeks} valueKey="jobs_completed" unit="count" label="Jobs completed" />
              </div>
            </Card>
          </div>

          {/* Technicians + durations */}
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="overflow-hidden lg:col-span-3">
              <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Technicians this period</h3></div>
              {data.technicians.length === 0 ? (
                <p className="px-4 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No technicians with activity in this period.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs min-w-[560px]">
                    <thead>
                      <tr style={{ backgroundColor: 'var(--ms-bg)' }}>
                        {['Technician', 'Booked', 'Done', 'Collected', 'Per job', 'Commission', 'Util.', 'On site (avg)'].map(h => <th key={h} className="px-3 py-2 text-left font-semibold" style={{ color: 'var(--ms-text-muted)' }}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {data.technicians.map(t => (
                        <tr key={t.user_id} style={{ borderTop: '1px solid var(--ms-border)' }}>
                          <td className="px-3 py-2 font-semibold" style={{ color: 'var(--ms-text)' }}><Link to={`/auto-key?view=jobs&jobs_layout=list&tech=${t.user_id}&date_field=completed&date_from=${data.period.start}&date_to=${data.period.end}`}>{t.name}</Link></td>
                          <td className="px-3 py-2 tabular-nums">{t.jobs_scheduled}</td>
                          <td className="px-3 py-2 tabular-nums">{t.jobs_completed}</td>
                          <td className="px-3 py-2 tabular-nums">{formatCents(t.collected_cents)}</td>
                          <td className="px-3 py-2 tabular-nums">{t.revenue_per_job_cents == null ? '—' : formatCents(t.revenue_per_job_cents)}</td>
                          <td className="px-3 py-2 tabular-nums">{formatCents(t.commission_cents)}</td>
                          <td className="px-3 py-2 tabular-nums">{t.utilisation_pct == null ? '—' : `${t.utilisation_pct}%`}</td>
                          <td className="px-3 py-2 tabular-nums">{t.on_site.avg_minutes == null ? '—' : `${formatMinutes(Math.round(t.on_site.avg_minutes))} (n=${t.on_site.count})`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="px-4 py-2 text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>Utilisation = {data.durations.estimated_minutes} min per booking against an 8-hour day × working days in the period.</p>
            </Card>
            <Card className="p-4 lg:col-span-2">
              <div className="flex items-center gap-2 mb-2"><Timer size={15} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Estimated vs actual duration</h3></div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--ms-text-muted)' }}>Estimated</p>
                  <p className="text-xl font-extrabold tabular-nums" style={{ color: 'var(--ms-text)' }}>{formatMinutes(data.durations.estimated_minutes)}</p>
                  <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>assumed — no estimate is recorded per job</p>
                </div>
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--ms-text-muted)' }}>Actual on site</p>
                  <p className="text-xl font-extrabold tabular-nums" style={{ color: data.durations.on_site.count ? 'var(--ms-text)' : 'var(--ms-text-muted)' }}>{data.durations.on_site.median_minutes == null ? '—' : formatMinutes(Math.round(data.durations.on_site.median_minutes))}</p>
                  <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>median · n={data.durations.on_site.count}{data.durations.on_site.p90_minutes != null ? ` · p90 ${formatMinutes(Math.round(data.durations.on_site.p90_minutes))}` : ''}</p>
                </div>
              </div>
              <p className="mt-3 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                Travel (En Route → On Site): {data.durations.travel.median_minutes == null ? 'no data yet' : `median ${formatMinutes(Math.round(data.durations.travel.median_minutes))} · n=${data.durations.travel.count}`}. Locations are not geocoded, so no route or clustering estimate is made.
              </p>
              {data.durations.by_job_type.length > 0 && (
                <div className="mt-3 space-y-1 text-xs">
                  {data.durations.by_job_type.slice(0, 5).map(r => (
                    <div key={r.job_type} className="flex justify-between gap-2"><span style={{ color: 'var(--ms-text-muted)' }}>{r.job_type}</span><span className="tabular-nums" style={{ color: 'var(--ms-text)' }}>{formatMinutes(Math.round(r.median_minutes ?? 0))} · n={r.count}</span></div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Definitions & data quality */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-2"><Info size={15} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>Metric definitions and data quality</h3></div>
            <div className="grid gap-4 md:grid-cols-2">
              <ul className="space-y-1 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                {data.metrics.map(m => <li key={m.key}><strong style={{ color: 'var(--ms-text)' }}>{m.label}:</strong> {m.definition}</li>)}
              </ul>
              <ul className="space-y-1.5 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                {data.data_quality.map(item => (
                  <li key={item.code} className="flex gap-2">
                    <span className="shrink-0 rounded-full px-1.5" style={{ color: TONE_COLORS[item.count ? 'warn' : 'neutral'], backgroundColor: TONE_BACKGROUNDS[item.count ? 'warn' : 'neutral'] }}>{item.count ?? '•'}</span>
                    <span>{item.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
