import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, BellRing, CheckCircle2, ChevronRight, Mail, Save, Target } from 'lucide-react'
import {
  deleteVswtAnnotation,
  getVswtCockpit,
  putVswtAnnotation,
  putVswtEmailPreference,
  putVswtTargets,
  sendVswtEmailNow,
  type VswtCockpitRow,
  type VswtComparison,
  type VswtKpiGroup,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Card, EmptyState, Spinner } from '@/components/ui'
import { fmtVswtVal, VSWT_KPI_GROUPS } from './format'
import type { ViewingShop } from './VswtViewingBanner'
import { VswtViewingBanner } from './VswtViewingBanner'

const COMPARISONS: { key: VswtComparison; label: string; short: string }[] = [
  { key: 'previous', label: 'Previous week', short: 'Prev week' },
  { key: '4w', label: 'Prior 4-week average', short: '4-week avg' },
  { key: '13w', label: 'Prior 13-week average', short: '13-week avg' },
  { key: '52w', label: 'Prior 52-week average', short: '52-week avg' },
  { key: 'last_year', label: 'Same period last year', short: 'Last year' },
]

const EVENT_TYPES = [
  ['other', 'General note'], ['promotion', 'Promotion'], ['staffing', 'Staffing'],
  ['holiday', 'Public holiday'], ['stock', 'Stock issue'], ['major_job', 'Major job'],
] as const

const MANAGER_ROLES = new Set(['owner', 'manager', 'platform_admin'])

function deltaTone(value: number | null) {
  if (value == null || value === 0) return 'var(--ms-text-muted)'
  return value > 0 ? '#1A6A3A' : '#A33838'
}

function MetricCard({ row, comparisonLabel }: { row: VswtCockpitRow; comparisonLabel: string }) {
  return (
    <Card className="p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{row.label}</p>
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
        <span>Region {fmtVswtVal(row.region_avg, row.type)}</span>
        {row.rank != null && <span>Rank #{row.rank}</span>}
        {row.rank_change != null && row.rank_change !== 0 && (
          <span style={{ color: deltaTone(row.rank_change) }}>{row.rank_change > 0 ? '+' : ''}{row.rank_change} places</span>
        )}
      </div>
      {row.target != null && (
        <div className="mt-2 pt-2 text-[11px]" style={{ borderTop: '1px dashed var(--ms-border)', color: deltaTone(row.target_variance) }}>
          {row.target_variance != null && row.target_variance >= 0 ? 'Above' : 'Below'} target by {fmtVswtVal(Math.abs(row.target_variance ?? 0), row.type)}
        </div>
      )}
    </Card>
  )
}

export function VswtComparisonCockpit({
  viewingShop,
  onBackToMyShop,
  onOpenDetails,
}: {
  viewingShop?: ViewingShop | null
  onBackToMyShop?: () => void
  onOpenDetails: (group: VswtKpiGroup) => void
}) {
  const { role } = useAuth()
  const canManage = role != null && MANAGER_ROLES.has(role)
  const queryClient = useQueryClient()
  const [week, setWeek] = useState<number | undefined>()
  const [comparison, setComparison] = useState<VswtComparison>('previous')
  const [group, setGroup] = useState<VswtKpiGroup>('Headline')
  const [targetDraft, setTargetDraft] = useState<Record<string, string>>({})
  const [eventType, setEventType] = useState('other')
  const [note, setNote] = useState('')

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['vswt-cockpit', week ?? null, comparison, viewingShop?.shopNumber ?? null],
    queryFn: () => getVswtCockpit({ week, comparison, shopNumber: viewingShop?.shopNumber }).then(r => r.data),
  })

  useEffect(() => {
    if (data?.available && week == null) setWeek(data.week)
  }, [data, week])

  useEffect(() => {
    if (!data?.available) return
    setTargetDraft(Object.fromEntries(Object.entries(data.targets).map(([key, value]) => [key, String(value)])))
  }, [data])

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['vswt-cockpit'] })
    void queryClient.invalidateQueries({ queryKey: ['vswt-summary'] })
    void queryClient.invalidateQueries({ queryKey: ['vswt-trends'] })
    void queryClient.invalidateQueries({ queryKey: ['vswt-targets'] })
  }
  const targetsMutation = useMutation({
    mutationFn: () => putVswtTargets(Object.fromEntries(
      ['sales_ty', 'customer_ty', 'jobs_ty'].map(key => [key, targetDraft[key] === '' || targetDraft[key] == null ? null : Number(targetDraft[key])]),
    )),
    onSuccess: invalidate,
  })
  const annotationMutation = useMutation({
    mutationFn: () => putVswtAnnotation({ week: data?.available ? data.week : 0, event_type: eventType, note }),
    onSuccess: () => { setNote(''); invalidate() },
  })
  const deleteAnnotationMutation = useMutation({ mutationFn: deleteVswtAnnotation, onSuccess: invalidate })
  const emailMutation = useMutation({
    mutationFn: (enabled: boolean) => putVswtEmailPreference(enabled),
    onSuccess: invalidate,
  })
  const sendNowMutation = useMutation({ mutationFn: sendVswtEmailNow })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load the comparison cockpit." />
  if (!data.available) return <EmptyState message="No comparison data is available for this shop yet." />

  const comparisonLabel = COMPARISONS.find(item => item.key === comparison)?.short ?? 'Comparison'
  const byKey = Object.fromEntries(data.rows.map(row => [row.key, row]))
  const headlineRows = ['sales_ty', 'customer_ty', 'jobs_ty', 'avg_sale'].map(key => byKey[key]).filter(Boolean)
  const tableRows = data.rows.filter(row => row.group === group)
  const selectedAnnotation = data.annotations.find(annotation => annotation.week === data.week)
  const annotationByWeek = new Map(data.annotations.map(annotation => [annotation.week, annotation]))

  return (
    <div className="space-y-5">
      {viewingShop && onBackToMyShop && <VswtViewingBanner viewing={viewingShop} onBack={onBackToMyShop} />}

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium" style={{ color: 'var(--ms-text-muted)' }}>
          Reporting week
          <select value={data.week} onChange={event => setWeek(Number(event.target.value))} className="block mt-1 rounded-md px-3 py-2 text-sm" style={controlStyle}>
            {[...data.weeks].reverse().map(value => <option key={value} value={value}>Week {value}</option>)}
          </select>
        </label>
        <label className="text-xs font-medium" style={{ color: 'var(--ms-text-muted)' }}>
          Compare against
          <select value={comparison} onChange={event => setComparison(event.target.value as VswtComparison)} className="block mt-1 rounded-md px-3 py-2 text-sm" style={controlStyle}>
            {COMPARISONS.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </label>
        {isFetching && <span className="text-xs pb-2" style={{ color: 'var(--ms-text-muted)' }}>Updating…</span>}
        <div className="ml-auto text-right text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
          <div>{data.source.filename ?? 'Regional source file'}</div>
          <div>{data.source.uploaded_at ? `Uploaded ${new Date(data.source.uploaded_at).toLocaleDateString()}` : 'Upload date unavailable'} · {data.source.shops_in_upload} shops</div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {headlineRows.map(row => <MetricCard key={row.key} row={row} comparisonLabel={comparisonLabel} />)}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3"><BellRing size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Exceptions and opportunities</h3></div>
          <div className="space-y-2">
            {data.alerts.map((alert, index) => {
              const good = alert.severity === 'positive'
              const critical = alert.severity === 'critical'
              const color = good ? '#1A6A3A' : critical ? '#A33838' : alert.severity === 'warning' ? '#9A5A00' : 'var(--ms-text-mid)'
              return <div key={`${alert.title}-${index}`} className="flex gap-2 rounded-md p-2.5" style={{ background: 'var(--ms-bg)' }}>
                {good ? <CheckCircle2 size={15} style={{ color, marginTop: 2 }} /> : <AlertTriangle size={15} style={{ color, marginTop: 2 }} />}
                <div><p className="text-xs font-semibold" style={{ color }}>{alert.title}</p><p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>{alert.message}</p></div>
              </div>
            })}
          </div>
        </Card>

        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>What changed sales</h3>
          <div className="grid grid-cols-3 gap-2 mb-4">
            {[
              ['Total change', data.drivers.sales_bridge.total_change],
              ['Customer volume', data.drivers.sales_bridge.customer_volume_effect],
              ['Average sale', data.drivers.sales_bridge.average_sale_effect],
            ].map(([label, value]) => <div key={String(label)} className="rounded-md p-2" style={{ background: 'var(--ms-bg)' }}>
              <p className="text-[10px]" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
              <p className="text-sm font-semibold" style={{ color: deltaTone(value as number | null) }}>{fmtVswtVal(value as number | null, 'currency')}</p>
            </div>)}
          </div>
          <div className="space-y-2">
            {data.drivers.category_sales.map(driver => <div key={driver.key} className="grid grid-cols-[1fr_auto_auto] gap-3 text-xs items-center">
              <span style={{ color: 'var(--ms-text)' }}>{driver.label}</span>
              <span style={{ color: 'var(--ms-text-muted)' }}>{driver.share_of_sales != null ? `${(driver.share_of_sales * 100).toFixed(1)}% of sales` : '—'}</span>
              <span className="font-semibold" style={{ color: deltaTone(driver.delta) }}>{driver.delta != null && driver.delta > 0 ? '+' : ''}{fmtVswtVal(driver.delta, 'currency')}</span>
            </div>)}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="p-4 flex flex-wrap items-center gap-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <div><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Complete KPI comparison</h3><p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Every metric uses the same selected week and baseline.</p></div>
          <select value={group} onChange={event => setGroup(event.target.value as VswtKpiGroup)} className="ml-auto rounded-md px-2 py-1.5 text-xs" style={controlStyle}>
            {VSWT_KPI_GROUPS.map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead><tr style={{ background: 'var(--ms-bg)' }}>
              {['Metric', 'Current', comparisonLabel, 'Change', '4 wk', '13 wk', '52 wk', 'Region', 'Peer', 'Rank', ''].map(label => <th key={label} style={thStyle}>{label}</th>)}
            </tr></thead>
            <tbody>{tableRows.map(row => <tr key={row.key}>
              <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 600, color: 'var(--ms-text)' }}>{row.label}</td>
              <td style={tdStyle}>{fmtVswtVal(row.current, row.type)}</td>
              <td style={tdStyle}>{fmtVswtVal(row.comparison, row.type)}</td>
              <td style={{ ...tdStyle, color: deltaTone(row.delta) }}>{row.delta != null && row.delta > 0 ? '+' : ''}{fmtVswtVal(row.delta, row.type)}{row.delta_pct != null ? ` (${row.delta_pct >= 0 ? '+' : ''}${(row.delta_pct * 100).toFixed(1)}%)` : ''}</td>
              <td style={tdStyle}>{fmtVswtVal(row.rolling_4, row.type)}</td>
              <td style={tdStyle}>{fmtVswtVal(row.rolling_13, row.type)}</td>
              <td style={tdStyle}>{fmtVswtVal(row.rolling_52, row.type)}</td>
              <td style={tdStyle}>{fmtVswtVal(row.region_avg, row.type)}</td>
              <td style={tdStyle}>{fmtVswtVal(row.peer_avg, row.type)}</td>
              <td style={tdStyle}>{row.rank != null ? `#${row.rank}` : '—'}</td>
              <td style={tdStyle}><button type="button" className="inline-flex items-center font-semibold" style={{ color: 'var(--ms-accent)' }} onClick={() => onOpenDetails(row.group)} aria-label={`Open ${row.group} detail`}>Details <ChevronRight size={13} /></button></td>
            </tr>)}</tbody>
          </table>
        </div>
      </Card>

      {data.viewing_own_shop && (
        <div className="grid gap-4 xl:grid-cols-3">
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3"><Target size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Shared weekly targets</h3></div>
            <div className="space-y-2">
              {[
                ['sales_ty', 'Sales', 'number'], ['customer_ty', 'Customers', 'number'], ['jobs_ty', 'Jobs', 'number'],
              ].map(([key, label, type]) => <label key={key} className="grid grid-cols-[1fr_120px] items-center gap-3 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                {label}<input type={type} min="0" disabled={!canManage} value={targetDraft[key] ?? ''} onChange={event => setTargetDraft({ ...targetDraft, [key]: event.target.value })} placeholder="No target" className="rounded-md px-2 py-1.5" style={controlStyle} />
              </label>)}
            </div>
            {canManage && <Button className="mt-3 w-full" onClick={() => targetsMutation.mutate()} disabled={targetsMutation.isPending}><Save size={14} className="mr-1" /> Save targets</Button>}
          </Card>

          <Card className="p-4">
            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--ms-text)' }}>Week {data.week} context</h3>
            <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>Explain promotions, staffing, holidays, stock issues, or unusual jobs.</p>
            {selectedAnnotation && <div className="rounded-md p-2.5 mb-3 text-xs" style={{ background: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}><strong style={{ color: 'var(--ms-text)' }}>{selectedAnnotation.event_type.replaceAll('_', ' ')}</strong><p className="mt-1">{selectedAnnotation.note}</p>{canManage && <button className="mt-2 font-semibold" style={{ color: '#A33838' }} onClick={() => deleteAnnotationMutation.mutate(selectedAnnotation.id)}>Delete note</button>}</div>}
            {canManage && <>
              <select value={eventType} onChange={event => setEventType(event.target.value)} className="w-full rounded-md px-2 py-1.5 text-xs mb-2" style={controlStyle}>{EVENT_TYPES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
              <textarea value={note} onChange={event => setNote(event.target.value)} maxLength={500} rows={3} placeholder={selectedAnnotation ? 'Replace this week note…' : 'Add context for this week…'} className="w-full rounded-md px-2 py-2 text-xs" style={controlStyle} />
              <Button className="mt-2 w-full" disabled={!note.trim() || annotationMutation.isPending} onClick={() => annotationMutation.mutate()}>Save week note</Button>
            </>}
            {annotationByWeek.size > 0 && <p className="text-[10px] mt-2" style={{ color: 'var(--ms-text-muted)' }}>{annotationByWeek.size} annotated week{annotationByWeek.size === 1 ? '' : 's'} on file.</p>}
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-2 mb-2"><Mail size={16} style={{ color: 'var(--ms-accent)' }} /><h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Weekly management email</h3></div>
            <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>Receive the comparison, exceptions, targets, and full KPI CSV after each reporting week.</p>
            <label className="flex items-center justify-between gap-3 rounded-md p-3" style={{ background: 'var(--ms-bg)' }}>
              <span className="text-xs font-medium" style={{ color: 'var(--ms-text)' }}>Email me each week</span>
              <input type="checkbox" checked={data.email_weekly_report} onChange={event => emailMutation.mutate(event.target.checked)} />
            </label>
            {data.last_weekly_report_sent_at && <p className="text-[10px] mt-2" style={{ color: 'var(--ms-text-muted)' }}>Last generated {new Date(data.last_weekly_report_sent_at).toLocaleString()}</p>}
            <Button variant="secondary" className="w-full mt-3" onClick={() => sendNowMutation.mutate()} disabled={sendNowMutation.isPending}>Send a report now</Button>
            {sendNowMutation.isSuccess && <p className="text-[11px] mt-2" style={{ color: sendNowMutation.data.data.sent ? '#1A6A3A' : 'var(--ms-text-muted)' }}>{sendNowMutation.data.data.sent ? 'Report sent.' : 'Report generated; email delivery is not configured.'}</p>}
          </Card>
        </div>
      )}
    </div>
  )
}

const controlStyle: React.CSSProperties = { backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }
const thStyle: React.CSSProperties = { padding: '9px 10px', textAlign: 'right', color: 'var(--ms-text-muted)', borderBottom: '1px solid var(--ms-border)', whiteSpace: 'nowrap', fontWeight: 600 }
const tdStyle: React.CSSProperties = { padding: '8px 10px', textAlign: 'right', color: 'var(--ms-text-mid)', borderBottom: '1px solid var(--ms-border)', whiteSpace: 'nowrap' }
