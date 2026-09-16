import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, BellRing, CheckCircle2, Mail, Target, TrendingDown, TrendingUp } from 'lucide-react'
import {
  deleteRegionAnnotation,
  fillRegionTargets,
  getApiErrorMessage,
  getRegionCockpit,
  putRegionAnnotation,
  sendRegionReportNow,
  updateRegion,
  type RegionCockpitRow,
  type RegionShopRow,
  type RegionTargetStrategy,
  type VswtComparison,
} from '@/lib/api'
import { useParentAccount } from '@/hooks/useParentAccount'
import { useHqEnterShop } from '@/lib/hqEnterShop'
import { REGIONS_QUERY_KEY } from '@/components/minit/MinitNetworkPanels'
import { Button, Card, EmptyState, PageHeader, Select, Spinner } from '@/components/ui'
import { fmtVswtDelta, fmtVswtVal } from '@/components/vswt/format'

const COMPARISONS: { key: VswtComparison; label: string; short: string }[] = [
  { key: 'previous', label: 'Previous week', short: 'Prev week' },
  { key: '4w', label: 'Prior 4-week average', short: '4-week avg' },
  { key: '13w', label: 'Prior 13-week average', short: '13-week avg' },
  { key: '52w', label: 'Prior 52-week average', short: '52-week avg' },
  { key: 'last_year', label: 'Same period last year', short: 'Last year' },
]

const EVENT_TYPES = [
  ['other', 'General note'], ['closure', 'Centre closure'], ['weather', 'Weather'], ['holiday', 'Public holiday'],
  ['promotion', 'Promotion'], ['staffing', 'Staffing'], ['refit', 'Refit / works'],
] as const

const STRATEGIES: { key: RegionTargetStrategy; label: string; hint: string }[] = [
  { key: 'last_year_plus_pct', label: 'Last year + %', hint: "Each shop's same week last year, uplifted" },
  { key: 'region_median', label: 'Region median', hint: "This week's median across the region, for every shop" },
  { key: 'previous_week', label: 'Previous week', hint: "Carry each shop's last actual forward" },
]

export const REGION_COCKPIT_QUERY_KEY = ['region-cockpit'] as const

function deltaTone(value: number | null | undefined) {
  if (value == null || value === 0) return 'var(--ms-text-muted)'
  return value > 0 ? '#1A6A3A' : '#A33838'
}

function AnomalyBadge({ anomaly, watch, z }: { anomaly: 'high' | 'low' | null; watch: 'high' | 'low' | null; z: number | null }) {
  const level = anomaly ?? watch
  if (!level || z == null) return null
  const low = level === 'low'
  const strong = anomaly != null
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
      style={{
        backgroundColor: low ? (strong ? 'rgba(163,56,56,0.14)' : 'rgba(154,90,0,0.14)') : 'rgba(26,106,58,0.14)',
        color: low ? (strong ? '#A33838' : '#9A5A00') : '#1A6A3A',
      }}
      title={`${z > 0 ? '+' : ''}${z.toFixed(1)} standard deviations from this shop's own 13-week norm`}
    >
      {low ? <TrendingDown size={11} /> : <TrendingUp size={11} />}
      {z > 0 ? '+' : ''}{z.toFixed(1)}σ
    </span>
  )
}

function HeadlineTile({ row, comparisonLabel, regionCount }: { row: RegionCockpitRow; comparisonLabel: string; regionCount: number }) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{row.label}</p>
        <AnomalyBadge anomaly={row.anomaly} watch={row.watch} z={row.zscore} />
      </div>
      <p className="text-2xl font-bold mt-1" style={{ color: 'var(--ms-text)' }}>{fmtVswtVal(row.current, row.type)}</p>
      <div className="flex flex-wrap items-center gap-x-2 mt-1 text-xs">
        <span style={{ color: 'var(--ms-text-muted)' }}>{comparisonLabel}: {fmtVswtVal(row.comparison, row.type)}</span>
        {row.delta_pct != null && (
          <span className="inline-flex items-center font-semibold" style={{ color: deltaTone(row.delta_pct) }}>
            {row.delta_pct >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {Math.abs(row.delta_pct * 100).toFixed(1)}%
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 mt-2 text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
        {row.rank != null && <span>#{row.rank} of {regionCount} regions</span>}
        {row.rank_change != null && row.rank_change !== 0 && (
          <span style={{ color: deltaTone(row.rank_change) }}>{row.rank_change > 0 ? '+' : ''}{row.rank_change} places</span>
        )}
        <span>Network avg/shop {fmtVswtVal(row.network_avg, row.type)}</span>
      </div>
    </Card>
  )
}

function MoverList({ title, rows, up }: { title: string; rows: RegionShopRow[]; up: boolean }) {
  return (
    <div>
      <p className="text-xs font-semibold mb-1.5 inline-flex items-center gap-1" style={{ color: up ? '#1A6A3A' : '#A33838' }}>
        {up ? <TrendingUp size={13} /> : <TrendingDown size={13} />} {title}
      </p>
      {rows.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>None this week.</p>
      ) : (
        <div className="space-y-1">
          {rows.map(r => (
            <div key={r.shop_number} className="grid grid-cols-[1fr_auto_auto] gap-2 text-xs items-center">
              <span className="truncate" style={{ color: 'var(--ms-text)' }}>{r.shop_name} <span style={{ color: 'var(--ms-text-muted)' }}>#{r.shop_number}</span></span>
              <span style={{ color: 'var(--ms-text-muted)' }}>{fmtVswtVal(r.delta, 'currency')}</span>
              <span className="font-semibold tabular-nums" style={{ color: deltaTone(r.delta_pct) }}>{r.delta_pct != null ? `${r.delta_pct > 0 ? '+' : ''}${(r.delta_pct * 100).toFixed(1)}%` : '—'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function MinitRegionCockpitPage() {
  const { regionId = '' } = useParams()
  const qc = useQueryClient()
  const { data: summary } = useParentAccount()
  const canEdit = summary?.my_role === 'hq_admin'
  const isMyRegion = summary?.my_region_id === regionId
  const canAnnotate = canEdit || isMyRegion
  const { enterShop, entering } = useHqEnterShop()

  const [week, setWeek] = useState<number | undefined>()
  const [comparison, setComparison] = useState<VswtComparison>('previous')
  const [eventType, setEventType] = useState('other')
  const [note, setNote] = useState('')
  const [exclude, setExclude] = useState(false)
  const [strategy, setStrategy] = useState<RegionTargetStrategy>('last_year_plus_pct')
  const [pct, setPct] = useState('5')
  const [error, setError] = useState('')
  const [fillResult, setFillResult] = useState('')

  const { data, isLoading, isFetching } = useQuery({
    queryKey: [...REGION_COCKPIT_QUERY_KEY, regionId, week ?? null, comparison],
    queryFn: () => getRegionCockpit(regionId, { week, comparison }).then(r => r.data),
    enabled: Boolean(regionId),
  })

  useEffect(() => {
    if (data?.available && week == null) setWeek(data.week)
  }, [data, week])

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: REGION_COCKPIT_QUERY_KEY })
    void qc.invalidateQueries({ queryKey: REGIONS_QUERY_KEY })
    void qc.invalidateQueries({ queryKey: ['vswt-cockpit'] })
  }
  const annotationMut = useMutation({
    mutationFn: () => putRegionAnnotation(regionId, { week: data?.available ? data.week : 0, event_type: eventType, note, exclude_from_baselines: exclude }),
    onSuccess: () => { setNote(''); setExclude(false); setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not save the week note.')),
  })
  const deleteAnnotationMut = useMutation({
    mutationFn: (id: string) => deleteRegionAnnotation(regionId, id),
    onSuccess: invalidate,
  })
  const fillMut = useMutation({
    mutationFn: () => fillRegionTargets(regionId, {
      strategy,
      pct: Number(pct) || 0,
      metric_keys: ['sales_ty', 'customer_ty', 'jobs_ty'],
      week: data?.available ? data.week : undefined,
    }).then(r => r.data),
    onSuccess: result => {
      setError('')
      setFillResult(`Set targets for ${result.shops_updated} shop${result.shops_updated === 1 ? '' : 's'} (${result.targets_written} values)${result.shops_skipped_no_data ? `; ${result.shops_skipped_no_data} skipped with no figure` : ''}.`)
      invalidate()
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not fill targets.')),
  })
  const optInMut = useMutation({
    mutationFn: (enabled: boolean) => updateRegion(regionId, { weekly_report_opt_in: enabled }),
    onSuccess: () => { setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not change the weekly report setting.')),
  })
  const sendNowMut = useMutation({
    mutationFn: () => sendRegionReportNow(regionId).then(r => r.data),
    onSuccess: () => { setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not send the report.')),
  })

  const comparisonLabel = COMPARISONS.find(c => c.key === comparison)?.short ?? 'Comparison'
  const selectedNote = useMemo(
    () => (data?.available ? data.annotations.find(a => a.week === data.week) : undefined),
    [data],
  )

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load this region." />
  if (!data.available) {
    return (
      <div>
        <PageHeader title="Region" />
        <EmptyState message={data.reason === 'no_shops' ? 'No shops with a shop number are assigned to this region yet. Assign them under Manage shops.' : 'No weekly regional data has been uploaded yet.'} />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={data.region.name}
        action={
          <div className="flex flex-wrap gap-2">
            {!isMyRegion && <Link to="/minit/dashboard"><Button variant="secondary">Dashboard</Button></Link>}
            {canEdit && <Link to="/minit/accounts"><Button variant="secondary">Manage shops</Button></Link>}
          </div>
        }
      />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        {data.region.manager_name ? `Regional manager ${data.region.manager_name}` : 'No regional manager set'} · {data.shops_reported} of {data.shop_count} shops reported
        {isFetching && <span className="ml-2 opacity-70">Updating…</span>}
      </p>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>{error}</div>
      )}

      <div className="flex flex-wrap items-end gap-3 mb-5">
        <div className="w-40">
          <Select label="Reporting week" value={data.week} onChange={e => setWeek(Number(e.target.value))}>
            {[...data.weeks].reverse().map(v => <option key={v} value={v}>Week {v}</option>)}
          </Select>
        </div>
        <div className="w-56">
          <Select label="Compare against" value={comparison} onChange={e => setComparison(e.target.value as VswtComparison)}>
            {COMPARISONS.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
          </Select>
        </div>
        {data.excluded_weeks.length > 0 && (
          <p className="text-[11px] pb-2" style={{ color: 'var(--ms-text-muted)' }}>
            Excluded from baselines: week{data.excluded_weeks.length === 1 ? '' : 's'} {data.excluded_weeks.join(', ')}
          </p>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 mb-5">
        {data.headline.map(row => <HeadlineTile key={row.key} row={row} comparisonLabel={comparisonLabel} regionCount={data.region_count} />)}
      </div>

      <Card className="p-4 mb-5" style={{ borderLeft: '4px solid var(--ms-accent)' }}>
        <p className="text-[11px] font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>This week, in one paragraph</p>
        <p className="text-sm leading-relaxed" style={{ color: 'var(--ms-text)' }}>{data.narrative}</p>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3 mb-5">
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3"><BellRing size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Needs a call</h3></div>
          <div className="space-y-2">
            {data.alerts.map((alert, i) => {
              const good = alert.severity === 'positive'
              const color = good ? '#1A6A3A' : alert.severity === 'critical' ? '#A33838' : alert.severity === 'warning' ? '#9A5A00' : 'var(--ms-text-mid)'
              return (
                <div key={`${alert.title}-${i}`} className="flex gap-2 rounded-md p-2.5" style={{ background: 'var(--ms-bg)' }}>
                  {good ? <CheckCircle2 size={15} style={{ color, marginTop: 2 }} /> : <AlertTriangle size={15} style={{ color, marginTop: 2 }} />}
                  <div><p className="text-xs font-semibold" style={{ color }}>{alert.title}</p><p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>{alert.message}</p></div>
                </div>
              )
            })}
          </div>
        </Card>
        <Card className="p-4 space-y-4">
          <MoverList title="Moved up most" rows={data.movers.up} up />
          <MoverList title="Moved down most" rows={data.movers.down} up={false} />
        </Card>
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Regions this week</h3>
          <div className="space-y-1.5">
            {data.leaderboard.map(r => (
              <div key={r.region_id} className="grid grid-cols-[auto_1fr_auto_auto] gap-2 text-xs items-center rounded-md px-2 py-1.5" style={{ background: r.is_me ? 'var(--ms-accent-light)' : 'transparent' }}>
                <span className="font-semibold tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>#{r.rank ?? '—'}</span>
                {r.is_me || !canEdit ? (
                  <span className="font-medium truncate" style={{ color: 'var(--ms-text)' }}>{r.region_name} <span style={{ color: 'var(--ms-text-muted)' }}>· {r.shops}</span></span>
                ) : (
                  <Link to={`/minit/regions/${r.region_id}`} className="font-medium truncate" style={{ color: 'var(--ms-accent)' }}>{r.region_name} <span style={{ color: 'var(--ms-text-muted)' }}>· {r.shops}</span></Link>
                )}
                <span className="tabular-nums" style={{ color: 'var(--ms-text)' }}>{fmtVswtVal(r.sales, 'currency')}</span>
                <span className="tabular-nums font-semibold" style={{ color: deltaTone(r.delta_pct) }}>{r.delta_pct != null ? `${r.delta_pct > 0 ? '+' : ''}${(r.delta_pct * 100).toFixed(1)}%` : '—'}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden mb-5">
        <div className="p-4 flex flex-wrap items-center gap-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Shops in {data.region.name}</h3>
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Week {data.week} against the previous week. σ is how unusual the week is for that shop alone.</p>
          </div>
          {data.target_attainment.shops_with_target > 0 && (
            <div className="ml-auto text-right text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              <div className="inline-flex items-center gap-1 font-semibold" style={{ color: 'var(--ms-text)' }}><Target size={13} /> {data.target_attainment.shops_met} of {data.target_attainment.shops_with_target} met sales target</div>
              {data.target_attainment.attainment_pct != null && <div>{(data.target_attainment.attainment_pct * 100).toFixed(0)}% of the region's combined target</div>}
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead><tr style={{ background: 'var(--ms-bg)' }}>
              {['Shop', 'Sales', 'Change', 'Customers', 'Avg sale', 'Region', 'Network', 'σ', 'Target', ''].map(label => <th key={label} style={{ ...thStyle, textAlign: label === 'Shop' ? 'left' : 'right' }}>{label}</th>)}
            </tr></thead>
            <tbody>{data.shops.map(r => (
              <tr key={r.shop_number} style={{ opacity: r.reported ? 1 : 0.55 }}>
                <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 600, color: 'var(--ms-text)' }}>
                  {r.shop_name} <span className="font-normal" style={{ color: 'var(--ms-text-muted)' }}>#{r.shop_number}{r.area_name ? ` · ${r.area_name}` : ''}</span>
                  {!r.reported && <span className="ml-2 font-normal" style={{ color: '#9A5A00' }}>not in upload</span>}
                </td>
                <td style={tdStyle}>{fmtVswtVal(r.sales, 'currency')}</td>
                <td style={{ ...tdStyle, color: deltaTone(r.delta) }}>{fmtVswtDelta(r.delta, r.delta_pct, 'currency')}</td>
                <td style={tdStyle}>{fmtVswtVal(r.customers, 'count')}</td>
                <td style={tdStyle}>{fmtVswtVal(r.avg_sale, 'currency')}</td>
                <td style={tdStyle}>{r.rank_in_region != null ? `#${r.rank_in_region}` : '—'}</td>
                <td style={tdStyle}>{r.rank_in_network != null ? `#${r.rank_in_network}` : '—'}</td>
                <td style={tdStyle}><AnomalyBadge anomaly={r.anomaly} watch={r.watch} z={r.zscore} /></td>
                <td style={{ ...tdStyle, color: r.target_met == null ? 'var(--ms-text-muted)' : r.target_met ? '#1A6A3A' : '#A33838' }}>
                  {r.target != null ? `${fmtVswtVal(r.target, 'currency')}${r.target_variance != null ? ` (${r.target_variance >= 0 ? '+' : ''}${fmtVswtVal(r.target_variance, 'currency')})` : ''}` : '—'}
                </td>
                <td style={tdStyle}>
                  {canEdit && r.tenant_id && (
                    <button type="button" className="font-semibold" style={{ color: 'var(--ms-accent)' }} disabled={entering === r.tenant_id} onClick={() => void enterShop(r.tenant_id!, `/minit/regions/${regionId}`)}>
                      {entering === r.tenant_id ? 'Opening…' : 'Open shop'}
                    </button>
                  )}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--ms-text)' }}>Week {data.week} across the region</h3>
          <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>One note for every shop in {data.region.name}. Exclude the week to keep it out of every shop's baselines.</p>
          {selectedNote && (
            <div className="rounded-md p-2.5 mb-3 text-xs" style={{ background: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}>
              <strong style={{ color: 'var(--ms-text)' }}>{selectedNote.event_type.replaceAll('_', ' ')}</strong>
              {selectedNote.exclude_from_baselines && <span className="ml-2 rounded-full px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(154,90,0,0.14)', color: '#9A5A00' }}>excluded from baselines</span>}
              <p className="mt-1">{selectedNote.note}</p>
              {canAnnotate && <button className="mt-2 font-semibold" style={{ color: '#A33838' }} onClick={() => deleteAnnotationMut.mutate(selectedNote.id)}>Delete note</button>}
            </div>
          )}
          {canAnnotate && (
            <>
              <Select value={eventType} onChange={e => setEventType(e.target.value)} className="mb-2">
                {EVENT_TYPES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </Select>
              <textarea value={note} onChange={e => setNote(e.target.value)} maxLength={500} rows={3} placeholder={selectedNote ? 'Replace this week note…' : 'e.g. Centre closed Tuesday, flooding'} className="w-full rounded-md px-2 py-2 text-xs" style={controlStyle} />
              <label className="flex items-center gap-2 mt-2 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                <input type="checkbox" checked={exclude} onChange={e => setExclude(e.target.checked)} /> Exclude this week from baselines
              </label>
              <Button className="mt-2 w-full" disabled={!note.trim() || annotationMut.isPending} onClick={() => annotationMut.mutate()}>Save region note</Button>
            </>
          )}
          {data.annotations.length > 0 && <p className="text-[10px] mt-2" style={{ color: 'var(--ms-text-muted)' }}>{data.annotations.length} annotated week{data.annotations.length === 1 ? '' : 's'} on file.</p>}
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 mb-1"><Target size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Set targets for the region</h3></div>
          <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>Sales, customers and jobs for every shop in {data.region.name}, from one rule. Shops with no figure for the rule are left alone.</p>
          {canEdit ? (
            <>
              <Select value={strategy} onChange={e => setStrategy(e.target.value as RegionTargetStrategy)} className="mb-2">
                {STRATEGIES.map(s => <option key={s.key} value={s.key}>{s.label} — {s.hint}</option>)}
              </Select>
              {strategy === 'last_year_plus_pct' && (
                <label className="grid grid-cols-[1fr_100px] items-center gap-3 text-xs mb-2" style={{ color: 'var(--ms-text-mid)' }}>
                  Uplift on last year (%)
                  <input type="number" value={pct} onChange={e => setPct(e.target.value)} className="rounded-md px-2 py-1.5" style={controlStyle} />
                </label>
              )}
              <Button className="w-full" onClick={() => fillMut.mutate()} disabled={fillMut.isPending}>{fillMut.isPending ? 'Setting…' : `Set targets from week ${data.week}`}</Button>
              {fillResult && <p className="text-[11px] mt-2" style={{ color: '#1A6A3A' }}>{fillResult}</p>}
            </>
          ) : (
            <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Only HQ admins set targets.</p>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2"><Mail size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Monday email to the regional manager</h3></div>
          <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
            {data.region.manager_email ? `Goes to ${data.region.manager_email}: the region's week, who moved, what needs a call, and every shop as a CSV.` : 'Set a manager email on the region first (Manage shops → Regions).'}
          </p>
          <label className="flex items-center justify-between gap-3 rounded-md p-3" style={{ background: 'var(--ms-bg)' }}>
            <span className="text-xs font-medium" style={{ color: 'var(--ms-text)' }}>Send every week</span>
            <input type="checkbox" checked={data.region.weekly_report_opt_in} disabled={!canEdit || !data.region.manager_email} onChange={e => optInMut.mutate(e.target.checked)} />
          </label>
          {data.region.last_weekly_report_sent_at && <p className="text-[10px] mt-2" style={{ color: 'var(--ms-text-muted)' }}>Last generated {new Date(data.region.last_weekly_report_sent_at).toLocaleString()}</p>}
          {canAnnotate && data.region.manager_email && (
            <Button variant="secondary" className="w-full mt-3" onClick={() => sendNowMut.mutate()} disabled={sendNowMut.isPending}>Send now</Button>
          )}
          {sendNowMut.isSuccess && <p className="text-[11px] mt-2" style={{ color: sendNowMut.data.sent ? '#1A6A3A' : 'var(--ms-text-muted)' }}>{sendNowMut.data.sent ? `Sent to ${sendNowMut.data.to}.` : 'Report generated; email delivery is not configured.'}</p>}
        </Card>
      </div>
    </div>
  )
}

const controlStyle: React.CSSProperties = { backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }
const thStyle: React.CSSProperties = { padding: '9px 10px', textAlign: 'right', color: 'var(--ms-text-muted)', borderBottom: '1px solid var(--ms-border)', whiteSpace: 'nowrap', fontWeight: 600 }
const tdStyle: React.CSSProperties = { padding: '8px 10px', textAlign: 'right', color: 'var(--ms-text-mid)', borderBottom: '1px solid var(--ms-border)', whiteSpace: 'nowrap' }
