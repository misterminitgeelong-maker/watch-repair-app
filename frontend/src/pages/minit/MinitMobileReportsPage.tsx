import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  formatTenantLabel,
  getApiErrorMessage,
  getParentEmailLeadsByShopReport,
  getParentMobileJobsReport,
  getParentMobileKpiDay,
  getParentMobileKpiDays,
  getParentMobileKpiRecipients,
  getParentMobileKpiWeek,
  getParentMobileKpiWeekCsv,
  getParentMobileKpiWeeks,
  getParentMobileKpisLive,
  getParentMobileKpisLiveCsv,
  sendParentMobileWeeklyReportNow,
  updateParentMobileKpiRecipient,
  updateParentMobileWeeklyReportSettings,
  type MobileKpiOperatorRow,
  type MobileKpiPeriod,
} from '@/lib/api'
import { formatCents, formatDate } from '@/lib/utils'
import { Button, Card, Input, PageHeader, Spinner } from '@/components/ui'
import { useParentAccount } from '@/hooks/useParentAccount'
import { defaultReportFromDate, defaultReportToDate, toIsoEnd, toIsoStart } from './dateRange'

type TabKey = 'live' | 'daily' | 'weekly' | 'recipients' | 'jobs'
const TABS: { key: TabKey; label: string }[] = [
  { key: 'live', label: 'Live' },
  { key: 'daily', label: 'Daily' },
  { key: 'weekly', label: 'Weekly' },
  { key: 'recipients', label: 'Recipients' },
  { key: 'jobs', label: 'Jobs' },
]

const CATEGORY_ORDER = [
  ['lockout', 'Lockout'],
  ['all_keys_lost', 'AKL'],
  ['key_cutting', 'Keys'],
  ['remote_fob', 'Remote'],
  ['ignition', 'Ignition'],
  ['transponder', 'Transponder'],
  ['diagnostic', 'Diagnostic'],
  ['other', 'Other'],
] as const

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function formatPct(value: number | null | undefined) {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function pctTone(value: number | null | undefined) {
  if (value == null || value === 0) return 'var(--ms-text-muted)'
  return value > 0 ? '#1A6A3A' : '#A33838'
}

function formatStamp(iso: string) {
  try {
    return new Date(iso).toLocaleString('en-AU', { timeZone: 'Australia/Sydney', hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })
  } catch {
    return iso
  }
}

function HeadlineTiles({ network, comparisonLabel }: { network: MobileKpiOperatorRow; comparisonLabel: string }) {
  const tiles = [
    { label: 'Sales', value: formatCents(network.sales_cents), sub: `${formatPct(network.sales_pct_change)} vs ${comparisonLabel}`, tone: pctTone(network.sales_pct_change) },
    { label: 'Customers', value: String(network.customers_count), sub: `${network.jobs_per_customer?.toFixed(2) ?? '—'} jobs / customer` },
    { label: 'Jobs created', value: String(network.jobs_created), sub: `${network.jobs_completed} completed` },
    { label: 'Outstanding', value: formatCents(network.outstanding_cents), sub: `${network.active_jobs} active · ${network.enquiries_not_actioned} enquiries open` },
  ]
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-5">
      {tiles.map(tile => (
        <Card key={tile.label} className="p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{tile.label}</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--ms-text)' }}>{tile.value}</p>
          <p className="text-xs mt-1" style={{ color: tile.tone ?? 'var(--ms-text-muted)' }}>{tile.sub}</p>
        </Card>
      ))}
    </div>
  )
}

function OperatorTable({ period }: { period: MobileKpiPeriod }) {
  const rows = period.operators ?? []
  return (
    <Card className="overflow-hidden">
      {rows.length === 0 ? (
        <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No mobile operators in this network yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                <th className="text-left px-4 py-2 font-medium">Operator</th>
                <th className="text-right px-4 py-2 font-medium">Customers</th>
                <th className="text-right px-4 py-2 font-medium">Jobs</th>
                <th className="text-right px-4 py-2 font-medium">Done</th>
                <th className="text-right px-4 py-2 font-medium">Sales</th>
                <th className="text-right px-4 py-2 font-medium">% chg</th>
                {CATEGORY_ORDER.map(([key, label]) => (
                  <th key={key} className="text-right px-4 py-2 font-medium">{label}</th>
                ))}
                <th className="text-right px-4 py-2 font-medium">Open enquiries</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.operator_tenant_id} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                  <td className="px-4 py-2">
                    <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{formatTenantLabel(row.operator_name, row.operator_shop_number)}</span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">{row.customers_count}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{row.jobs_created}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{row.jobs_completed}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{formatCents(row.sales_cents)}</td>
                  <td className="px-4 py-2 text-right tabular-nums" style={{ color: pctTone(row.sales_pct_change) }}>{formatPct(row.sales_pct_change)}</td>
                  {CATEGORY_ORDER.map(([key]) => (
                    <td key={key} className="px-4 py-2 text-right tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>
                      {row.category_jobs?.[key] ?? 0}
                    </td>
                  ))}
                  <td className="px-4 py-2 text-right tabular-nums" style={{ color: row.enquiries_not_actioned > 0 ? 'var(--ms-error)' : 'var(--ms-text-muted)' }}>
                    {row.enquiries_not_actioned}
                  </td>
                </tr>
              ))}
              <tr>
                <td className="px-4 py-2 font-semibold">Network total</td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold">{period.network.customers_count}</td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold">{period.network.jobs_created}</td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold">{period.network.jobs_completed}</td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold">{formatCents(period.network.sales_cents)}</td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold" style={{ color: pctTone(period.network.sales_pct_change) }}>{formatPct(period.network.sales_pct_change)}</td>
                {CATEGORY_ORDER.map(([key]) => (
                  <td key={key} className="px-4 py-2 text-right tabular-nums font-semibold">{period.network.category_jobs?.[key] ?? 0}</td>
                ))}
                <td className="px-4 py-2 text-right tabular-nums font-semibold">{period.network.enquiries_not_actioned}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function EnquiriesByShopSection({ fromYmd, toYmd }: { fromYmd: string; toYmd: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['minit-email-leads-by-shop', fromYmd, toYmd],
    queryFn: () =>
      getParentEmailLeadsByShopReport({
        from_date: toIsoStart(fromYmd),
        to_date: toIsoEnd(toYmd),
      }).then(r => r.data),
  })

  return (
    <section className="mb-8">
      <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--ms-text)' }}>Enquiries by shop</h2>
      <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
        Email enquiries grouped by the operator each one names.
      </p>
      {isLoading || !data ? (
        <Spinner />
      ) : (data.shops ?? []).length === 0 ? (
        <Card className="p-4">
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No email enquiries in range.</p>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                  <th className="text-left px-5 py-2 font-medium">Shop / operator</th>
                  <th className="text-right px-5 py-2 font-medium">Total</th>
                  <th className="text-right px-5 py-2 font-medium">Not actioned</th>
                  <th className="text-right px-5 py-2 font-medium">Job created</th>
                  <th className="text-right px-5 py-2 font-medium">Dismissed</th>
                  <th className="text-left px-5 py-2 font-medium">Oldest unactioned</th>
                </tr>
              </thead>
              <tbody>
                {(data.shops ?? []).map(shop => (
                  <tr key={`${shop.operator_tenant_id ?? 'none'}-${shop.operator_name}`} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                    <td className="px-5 py-2" style={{ color: 'var(--ms-text)' }}>{shop.operator_name}</td>
                    <td className="px-5 py-2 text-right tabular-nums">{shop.total_count}</td>
                    <td className="px-5 py-2 text-right tabular-nums font-semibold" style={{ color: (shop.new_count ?? 0) > 0 ? 'var(--ms-error)' : 'var(--ms-text-muted)' }}>
                      {shop.new_count ?? 0}
                    </td>
                    <td className="px-5 py-2 text-right tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>{shop.processed_count}</td>
                    <td className="px-5 py-2 text-right tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>{shop.dismissed_count}</td>
                    <td className="px-5 py-2 whitespace-nowrap" style={{ color: 'var(--ms-text-muted)' }}>
                      {shop.oldest_new_at ? formatDate(shop.oldest_new_at) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </section>
  )
}

export default function MinitMobileReportsPage() {
  const [tab, setTab] = useState<TabKey>('live')
  const [liveScope, setLiveScope] = useState<'day' | 'week'>('week')
  const [fromYmd, setFromYmd] = useState(defaultReportFromDate)
  const [toYmd, setToYmd] = useState(defaultReportToDate)
  const [selectedDay, setSelectedDay] = useState<string | null>(null)
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null)
  const [error, setError] = useState('')
  const queryClient = useQueryClient()
  const { data: summary } = useParentAccount()
  const canEdit = summary?.my_role === 'hq_admin'

  const liveQuery = useQuery({
    queryKey: ['minit-mobile-kpis-live'],
    queryFn: () => getParentMobileKpisLive().then(r => r.data),
    refetchInterval: 60_000,
    enabled: tab === 'live',
  })
  const daysQuery = useQuery({
    queryKey: ['minit-mobile-kpis-days'],
    queryFn: () => getParentMobileKpiDays().then(r => r.data),
    enabled: tab === 'daily',
  })
  const weeksQuery = useQuery({
    queryKey: ['minit-mobile-kpis-weeks'],
    queryFn: () => getParentMobileKpiWeeks().then(r => r.data),
    enabled: tab === 'weekly' || tab === 'recipients',
  })
  const recipientsQuery = useQuery({
    queryKey: ['minit-mobile-kpis-recipients'],
    queryFn: () => getParentMobileKpiRecipients().then(r => r.data),
    enabled: tab === 'recipients',
  })
  const jobsQuery = useQuery({
    queryKey: ['minit-mobile-jobs-report', fromYmd, toYmd],
    queryFn: () =>
      getParentMobileJobsReport({
        from_date: toIsoStart(fromYmd),
        to_date: toIsoEnd(toYmd),
        limit: 200,
      }).then(r => r.data),
    enabled: tab === 'jobs',
  })

  const dayList = daysQuery.data?.days ?? []
  const weekList = weeksQuery.data?.weeks ?? []
  const activeDay = selectedDay ?? dayList[0]?.trade_date ?? null
  const activeWeek = selectedWeek ?? weekList[0]?.week_start_ymd ?? null

  const dayDetail = useQuery({
    queryKey: ['minit-mobile-kpis-day', activeDay],
    queryFn: () => getParentMobileKpiDay(activeDay!).then(r => r.data),
    enabled: tab === 'daily' && Boolean(activeDay),
  })
  const weekDetail = useQuery({
    queryKey: ['minit-mobile-kpis-week', activeWeek],
    queryFn: () => getParentMobileKpiWeek(activeWeek!).then(r => r.data),
    enabled: tab === 'weekly' && Boolean(activeWeek),
  })

  const livePeriod = liveQuery.data ? (liveScope === 'day' ? liveQuery.data.day : liveQuery.data.week) : null

  const resolvedDay = useMemo(() => {
    if (dayDetail.data && dayDetail.data.trade_date === activeDay) return dayDetail.data
    return null
  }, [dayDetail.data, activeDay])
  const resolvedWeek = useMemo(() => {
    if (weekDetail.data && weekDetail.data.week_start_ymd === activeWeek) return weekDetail.data
    return null
  }, [weekDetail.data, activeWeek])

  const toggleRecipient = useMutation({
    mutationFn: ({ userId, enabled }: { userId: string; enabled: boolean }) =>
      updateParentMobileKpiRecipient(userId, enabled).then(r => r.data),
    onSuccess: () => { setError(''); queryClient.invalidateQueries({ queryKey: ['minit-mobile-kpis-recipients'] }) },
    onError: err => setError(getApiErrorMessage(err, 'Could not update recipient.')),
  })
  const optInMut = useMutation({
    mutationFn: (optIn: boolean) => updateParentMobileWeeklyReportSettings(optIn).then(r => r.data),
    onSuccess: () => { setError(''); queryClient.invalidateQueries({ queryKey: ['minit-mobile-kpis-recipients'] }) },
    onError: err => setError(getApiErrorMessage(err, 'Could not change the weekly email setting.')),
  })
  const sendNowMut = useMutation({
    mutationFn: () => sendParentMobileWeeklyReportNow().then(r => r.data),
    onSuccess: () => {
      setError('')
      queryClient.invalidateQueries({ queryKey: ['minit-mobile-kpis-recipients'] })
      queryClient.invalidateQueries({ queryKey: ['minit-mobile-kpis-weeks'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not send the weekly report.')),
  })

  return (
    <div>
      <PageHeader title="Mobile reports" />
      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Live mobile-services KPIs for every operator in the network. Days freeze at 9pm Sydney time; the weekly CSV compiles Saturday 11:05pm.
      </p>

      <div className="flex flex-wrap gap-2 mb-5">
        {TABS.map(item => (
          <button
            key={item.key}
            type="button"
            onClick={() => { setTab(item.key); setError('') }}
            className="rounded-full px-3 py-1.5 text-sm font-medium"
            style={
              tab === item.key
                ? { backgroundColor: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }
                : { backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-mid)' }
            }
          >
            {item.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>{error}</div>
      )}

      {tab === 'live' && (
        liveQuery.isLoading || !livePeriod || !liveQuery.data ? <Spinner /> : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div className="flex gap-2">
                <Button size="sm" variant={liveScope === 'week' ? 'primary' : 'secondary'} onClick={() => setLiveScope('week')}>Week to date</Button>
                <Button size="sm" variant={liveScope === 'day' ? 'primary' : 'secondary'} onClick={() => setLiveScope('day')}>Today</Button>
              </div>
              <div className="flex items-center gap-3">
                <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                  Live poll · last updated {formatStamp(liveQuery.data.generated_at)} Sydney
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => getParentMobileKpisLiveCsv(liveScope).then(r => downloadBlob(r.data, `minit-mobile-live-${liveScope}.csv`))}
                >
                  Download CSV
                </Button>
              </div>
            </div>
            <HeadlineTiles network={livePeriod.network} comparisonLabel={liveScope === 'day' ? 'same day last week' : 'prior week'} />
            <OperatorTable period={livePeriod} />
          </>
        )
      )}

      {tab === 'daily' && (
        daysQuery.isLoading ? <Spinner /> : dayList.length === 0 ? (
          <Card className="p-5"><p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No 9pm daily reports compiled yet. They appear after 9pm Sydney time.</p></Card>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-4">
              {dayList.slice(0, 14).map(day => (
                <button
                  key={day.trade_date}
                  type="button"
                  onClick={() => setSelectedDay(day.trade_date)}
                  className="rounded-full px-3 py-1 text-xs font-medium"
                  style={
                    (activeDay === day.trade_date)
                      ? { backgroundColor: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }
                      : { backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-mid)' }
                  }
                >
                  {day.trade_date}
                </button>
              ))}
            </div>
            {activeDay && !resolvedDay && dayDetail.isLoading ? <Spinner /> : resolvedDay ? (
              <>
                <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                  Compiled at {formatStamp(resolvedDay.compiled_at)} · frozen 9pm trade day
                </p>
                <HeadlineTiles network={resolvedDay.report.network} comparisonLabel="same day last week" />
                <OperatorTable period={resolvedDay.report} />
              </>
            ) : (
              <Card className="p-5"><p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Select a compiled day.</p></Card>
            )}
          </>
        )
      )}

      {tab === 'weekly' && (
        weeksQuery.isLoading ? <Spinner /> : weekList.length === 0 ? (
          <Card className="p-5"><p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No Saturday weekly reports compiled yet. They appear after 11:05pm Saturday Sydney time.</p></Card>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-4">
              {weekList.map(week => (
                <button
                  key={week.week_start_ymd}
                  type="button"
                  onClick={() => setSelectedWeek(week.week_start_ymd)}
                  className="rounded-full px-3 py-1 text-xs font-medium"
                  style={
                    (activeWeek === week.week_start_ymd)
                      ? { backgroundColor: 'var(--ms-accent)', color: 'var(--ms-on-accent)' }
                      : { backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-mid)' }
                  }
                >
                  {week.week_start_ymd} → {week.week_end_ymd}
                </button>
              ))}
            </div>
            {activeWeek && !resolvedWeek && weekDetail.isLoading ? <Spinner /> : resolvedWeek ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                    Compiled at {formatStamp(resolvedWeek.compiled_at)}
                    {resolvedWeek.emailed_at ? ` · emailed ${formatStamp(resolvedWeek.emailed_at)}` : ' · not yet emailed'}
                  </p>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => getParentMobileKpiWeekCsv(resolvedWeek.week_start_ymd).then(r =>
                      downloadBlob(r.data, `minit-mobile-weekly-${resolvedWeek.week_start_ymd}_${resolvedWeek.week_end_ymd}.csv`))}
                  >
                    Download CSV
                  </Button>
                </div>
                <HeadlineTiles network={resolvedWeek.report.network} comparisonLabel="prior week" />
                <OperatorTable period={resolvedWeek.report} />
              </>
            ) : (
              <Card className="p-5"><p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Select a compiled week.</p></Card>
            )}
          </>
        )
      )}

      {tab === 'recipients' && (
        recipientsQuery.isLoading || !recipientsQuery.data ? <Spinner /> : (
          <>
            <Card className="p-5 mb-5">
              <p className="text-sm font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>Saturday CSV email</p>
              <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                Master switch for the weekly file. Allocated HQ workers below get the CSV; if none are ticked, the parent owner email is used.
              </p>
              <div className="flex flex-wrap gap-2">
                {canEdit && (
                  <Button
                    size="sm"
                    variant={recipientsQuery.data.opt_in ? 'primary' : 'secondary'}
                    onClick={() => optInMut.mutate(!recipientsQuery.data.opt_in)}
                    disabled={optInMut.isPending}
                  >
                    {recipientsQuery.data.opt_in ? 'Weekly email on' : 'Weekly email off'}
                  </Button>
                )}
                {canEdit && (
                  <Button size="sm" variant="secondary" onClick={() => sendNowMut.mutate()} disabled={sendNowMut.isPending}>
                    Send last week now
                  </Button>
                )}
              </div>
              {recipientsQuery.data.last_sent_at && (
                <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>Last send-now: {formatStamp(recipientsQuery.data.last_sent_at)}</p>
              )}
            </Card>
            <Card className="overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                    <th className="text-left px-5 py-2 font-medium">HQ worker</th>
                    <th className="text-left px-5 py-2 font-medium">Role</th>
                    <th className="text-right px-5 py-2 font-medium">Email the Saturday CSV</th>
                  </tr>
                </thead>
                <tbody>
                  {(recipientsQuery.data.recipients ?? []).map(person => (
                    <tr key={person.user_id} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                      <td className="px-5 py-2">
                        <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{person.full_name}</span>
                        <span className="block text-xs" style={{ color: 'var(--ms-text-muted)' }}>{person.email}</span>
                      </td>
                      <td className="px-5 py-2 capitalize" style={{ color: 'var(--ms-text-muted)' }}>{person.role.replace('_', ' ')}</td>
                      <td className="px-5 py-2 text-right">
                        <input
                          type="checkbox"
                          checked={person.email_mobile_kpi_report}
                          disabled={!canEdit || toggleRecipient.isPending}
                          onChange={e => toggleRecipient.mutate({ userId: person.user_id, enabled: e.target.checked })}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </>
        )
      )}

      {tab === 'jobs' && (
        <>
          <Card className="p-5 mb-6">
            <div className="flex flex-wrap gap-4 items-end">
              <Input label="From" type="date" value={fromYmd} onChange={e => setFromYmd(e.target.value)} className="w-40" />
              <Input label="To" type="date" value={toYmd} onChange={e => setToYmd(e.target.value)} className="w-40" />
            </div>
          </Card>
          <EnquiriesByShopSection fromYmd={fromYmd} toYmd={toYmd} />
          {jobsQuery.isLoading || !jobsQuery.data ? (
            <Spinner />
          ) : (
            <>
              <Card className="p-5 mb-6">
                <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
                  {jobsQuery.data.total_count} jobs in range · {jobsQuery.data.active_count} still active
                </p>
              </Card>
              <Card className="overflow-hidden">
                {(jobsQuery.data.jobs ?? []).length === 0 ? (
                  <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No mobile jobs in range.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                          <th className="text-left px-5 py-2 font-medium">Job</th>
                          <th className="text-left px-5 py-2 font-medium">Operator</th>
                          <th className="text-left px-5 py-2 font-medium">Referring shop</th>
                          <th className="text-left px-5 py-2 font-medium">Status</th>
                          <th className="text-left px-5 py-2 font-medium">Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(jobsQuery.data.jobs ?? []).map(job => (
                          <tr key={job.id} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                            <td className="px-5 py-2">
                              <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{job.job_number}</span>
                              <span className="block text-xs" style={{ color: 'var(--ms-text-muted)' }}>{job.title}</span>
                            </td>
                            <td className="px-5 py-2">{formatTenantLabel(job.operator_name, job.operator_shop_number)}</td>
                            <td className="px-5 py-2">
                              {job.referring_shop_name
                                ? formatTenantLabel(job.referring_shop_name, job.referring_shop_number)
                                : '—'}
                            </td>
                            <td className="px-5 py-2 capitalize">{job.status.replace(/_/g, ' ')}</td>
                            <td className="px-5 py-2 whitespace-nowrap">{formatDate(job.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </>
          )}
        </>
      )}
    </div>
  )
}
