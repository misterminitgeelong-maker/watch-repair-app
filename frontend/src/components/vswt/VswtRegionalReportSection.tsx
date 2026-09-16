import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight, Gauge, LayoutGrid, Table2, Trophy, LineChart as LineChartIcon, Upload, Search, FileText, ClipboardList } from 'lucide-react'
import { getVswtExportCsv, getVswtSummary, getVswtWeeks, type VswtSummary, type VswtUnavailable } from '@/lib/api'
import { Button, Card, EmptyState, Spinner } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import { VswtRankGauge } from './VswtRankGauge'
import { fmtVswtVal, rankTone, rankToneColors } from './format'
import { VswtScorecard } from './VswtScorecard'
import { VswtRankings } from './VswtRankings'
import { VswtLeaderboards } from './VswtLeaderboards'
import { VswtTrends } from './VswtTrends'
import { VswtShopReport } from './VswtShopReport'
import { VswtUploadPanel } from './VswtUploadPanel'
import { VswtShopDirectory } from './VswtShopDirectory'
import { VswtWeeklyReportBuilder } from './VswtWeeklyReportBuilder'
import type { ViewingShop } from './VswtViewingBanner'

type SubTab =
  | 'overview' | 'directory' | 'shop-report' | 'scorecard' | 'rankings' | 'leaderboards' | 'trends'
  | 'weekly-report' | 'upload'

const MANAGER_ROLES = new Set(['owner', 'manager', 'platform_admin'])

export function PillToggle<T extends string>({
  value, onChange, options,
}: { value: T; onChange: (v: T) => void; options: { key: T; label: string }[] }) {
  return (
    <div
      className="inline-flex flex-wrap rounded-lg p-0.5 gap-0.5"
      style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}
    >
      {options.map(o => (
        <button
          key={o.key}
          type="button"
          onClick={() => onChange(o.key)}
          className="px-3 py-1 text-xs font-medium rounded-md transition-colors"
          style={{
            backgroundColor: value === o.key ? 'var(--ms-surface)' : 'transparent',
            color: value === o.key ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
            boxShadow: value === o.key ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function VswtRegionalReportSection() {
  const { role } = useAuth()
  const canUpload = role != null && MANAGER_ROLES.has(role)
  const [subTab, setSubTab] = useState<SubTab>('overview')
  // Set by picking a shop in the Directory; carries across Scorecard/Rankings/Trends until the
  // user explicitly goes "back to my shop" — switching those tabs while browsing keeps browsing.
  const [viewingShop, setViewingShop] = useState<ViewingShop | null>(null)

  const subTabs: { key: SubTab; label: string; icon: React.ElementType }[] = [
    { key: 'overview', label: 'Overview', icon: Gauge },
    { key: 'directory', label: 'Shop Directory', icon: Search },
    { key: 'shop-report', label: 'Shop Report', icon: FileText },
    { key: 'scorecard', label: 'Scorecard', icon: LayoutGrid },
    { key: 'rankings', label: 'Rankings', icon: Table2 },
    { key: 'leaderboards', label: 'Leaderboards', icon: Trophy },
    { key: 'trends', label: 'Trends', icon: LineChartIcon },
    { key: 'weekly-report', label: 'Weekly Report', icon: ClipboardList },
    ...(canUpload ? [{ key: 'upload' as SubTab, label: 'Upload', icon: Upload }] : []),
  ]

  function viewShop(shopNumber: string, shopName: string | null) {
    setViewingShop({ shopNumber, shopName })
    setSubTab('shop-report')
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
        Your shop's rank against every VSWT region shop, from Mister Minit HQ's weekly export —
        updated whenever any shop uploads the latest file.
      </p>
      <div className="mb-5">
        <PillToggle value={subTab} onChange={setSubTab} options={subTabs.map(t => ({ key: t.key, label: t.label }))} />
      </div>

      {subTab === 'overview' && <VswtOverview canUpload={canUpload} onGoToUpload={() => setSubTab('upload')} />}
      {subTab === 'directory' && <VswtShopDirectory onSelectShop={viewShop} />}
      {subTab === 'shop-report' && (
        <VswtShopReport viewingShop={viewingShop} onBackToMyShop={() => setViewingShop(null)} />
      )}
      {subTab === 'scorecard' && (
        <VswtScorecard viewingShop={viewingShop} onBackToMyShop={() => setViewingShop(null)} />
      )}
      {subTab === 'rankings' && (
        <VswtRankings viewingShop={viewingShop} onBackToMyShop={() => setViewingShop(null)} />
      )}
      {subTab === 'leaderboards' && <VswtLeaderboards />}
      {subTab === 'trends' && (
        <VswtTrends viewingShop={viewingShop} onBackToMyShop={() => setViewingShop(null)} />
      )}
      {subTab === 'weekly-report' && <VswtWeeklyReportBuilder />}
      {subTab === 'upload' && canUpload && <VswtUploadPanel />}
    </div>
  )
}

function unavailableMessage(reason: VswtUnavailable['reason']): string {
  switch (reason) {
    case 'no_shop_number':
      return "This shop isn't linked to a VSWT shop number yet, so regional ranking isn't available here."
    case 'no_data':
      return 'No weekly regional data has been uploaded yet.'
    case 'shop_not_found':
      return "This shop's number wasn't found in the most recent regional data."
  }
}

function VswtOverview({ canUpload, onGoToUpload }: { canUpload: boolean; onGoToUpload: () => void }) {
  const { tenantId } = useAuth()
  const { data, isLoading } = useQuery({ queryKey: ['vswt-summary'], queryFn: () => getVswtSummary().then(r => r.data) })
  const { data: weekData } = useQuery({ queryKey: ['vswt-weeks'], queryFn: () => getVswtWeeks().then(r => r.data.weeks) })
  const [targets, setTargets] = useState(() => loadTargets(tenantId))

  useEffect(() => { saveTargets(tenantId, targets) }, [tenantId, targets])

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load regional data." />

  if (!data.available) {
    return (
      <Card className="p-6">
        <EmptyState message={unavailableMessage(data.reason)} />
        {canUpload && data.reason === 'no_data' && (
          <div className="flex justify-center -mt-8">
            <button
              onClick={onGoToUpload}
              className="text-sm font-semibold underline"
              style={{ color: 'var(--ms-accent)' }}
            >
              Upload this week's file
            </button>
          </div>
        )}
      </Card>
    )
  }

  const summary: VswtSummary = data
  const tone = rankTone(summary.sales.region_rank, summary.region_size)
  const toneColors = rankToneColors(tone)

  return (
    <div>
      <div className="flex flex-wrap gap-5 mb-6">
        <Card className="p-5 flex flex-col items-center justify-center">
          <VswtRankGauge rank={summary.sales.region_rank} n={summary.region_size} label="Sales rank, region" />
        </Card>
        <div className="flex-1 min-w-[280px] flex flex-col gap-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <VswtStatCard label="Sales" currentValue={summary.sales.value} value={fmtVswtVal(summary.sales.value, 'currency')} previousValue={summary.sales.prev_value} previousRank={summary.sales.prev_region_rank} type="currency" rank={summary.sales.region_rank} n={summary.region_size} />
            <VswtStatCard label="Customers" currentValue={summary.customers.value} value={fmtVswtVal(summary.customers.value, 'count')} previousValue={summary.customers.prev_value} previousRank={summary.customers.prev_region_rank} type="count" rank={summary.customers.region_rank} n={summary.region_size} />
            <VswtStatCard label="Jobs" currentValue={summary.jobs.value} value={fmtVswtVal(summary.jobs.value, 'count')} previousValue={summary.jobs.prev_value} previousRank={summary.jobs.prev_region_rank} type="count" rank={summary.jobs.region_rank} n={summary.region_size} />
          </div>
          <Card className="p-4 text-sm leading-relaxed" style={{ color: 'var(--ms-text-mid)' }}>
            {summary.area_name && summary.sales.area_rank != null && (
              <>
                In <strong style={{ color: 'var(--ms-text)' }}>{summary.area_name}</strong>, {summary.shop_name ?? 'this shop'} ranks{' '}
                <strong style={{ color: toneColors.fg }}>#{summary.sales.area_rank} of {summary.area_size}</strong> shops on sales this week.{' '}
              </>
            )}
            Region-wide, that's <strong style={{ color: toneColors.fg }}>#{summary.sales.region_rank} of {summary.region_size}</strong>.
            {summary.sales.peer_rank != null && (
              <> Among comparable franchise stores, <strong style={{ color: 'var(--ms-text)' }}>#{summary.sales.peer_rank}</strong>.</>
            )}
          </Card>
        </div>
      </div>
      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
        Week {summary.latest_week} · {summary.weeks_tracked} week{summary.weeks_tracked !== 1 ? 's' : ''} tracked · {summary.region_size} shops in region
      </p>
      <div className="grid gap-4 lg:grid-cols-2 mt-5">
        <TargetPanel summary={summary} targets={targets} onChange={setTargets} />
        <InsightsPanel summary={summary} weeks={weekData ?? []} onExport={() => downloadRegionalCsv()} />
      </div>
    </div>
  )
}

type Targets = { sales: number | null; customers: number | null; jobs: number | null }
function loadTargets(tenantId: string | null): Targets {
  try {
    const raw = localStorage.getItem(`vswt-targets:${tenantId ?? 'anon'}`)
    const parsed = raw ? JSON.parse(raw) : {}
    return { sales: Number.isFinite(parsed.sales) ? parsed.sales : null, customers: Number.isFinite(parsed.customers) ? parsed.customers : null, jobs: Number.isFinite(parsed.jobs) ? parsed.jobs : null }
  } catch { return { sales: null, customers: null, jobs: null } }
}
function saveTargets(tenantId: string | null, targets: Targets) {
  try { localStorage.setItem(`vswt-targets:${tenantId ?? 'anon'}`, JSON.stringify(targets)) } catch { /* private mode */ }
}
function TargetPanel({ summary, targets, onChange }: { summary: VswtSummary; targets: Targets; onChange: (v: Targets) => void }) {
  const items = [
    { key: 'sales' as const, label: 'Sales target', current: summary.sales.value, type: 'currency' as const },
    { key: 'customers' as const, label: 'Customer target', current: summary.customers.value, type: 'count' as const },
    { key: 'jobs' as const, label: 'Job target', current: summary.jobs.value, type: 'count' as const },
  ]
  return <Card className="p-4">
    <div className="flex justify-between items-baseline gap-3 mb-3"><p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Weekly targets</p><span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Saved for this shop</span></div>
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map(item => {
        const target = targets[item.key]
        const variance = target != null && item.current != null ? item.current - target : null
        return <div key={item.key}>
          <label className="block text-[11px] font-medium mb-1" style={{ color: 'var(--ms-text-muted)' }}>{item.label}</label>
          <input type="number" min="0" value={target ?? ''} placeholder="Set target" onChange={e => onChange({ ...targets, [item.key]: e.target.value === '' ? null : Number(e.target.value) })} className="w-full rounded-md px-2 py-1.5 text-sm" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }} />
          {variance != null && <p className="text-[11px] mt-1" style={{ color: variance >= 0 ? '#1A6A3A' : '#A33838' }}>{variance >= 0 ? '+' : ''}{fmtVswtVal(variance, item.type)} vs target</p>}
        </div>
      })}
    </div>
  </Card>
}
function InsightsPanel({ summary, weeks, onExport }: { summary: VswtSummary; weeks: { week: number; uploaded_at: string | null }[]; onExport: () => void }) {
  const insights: string[] = []
  for (const [label, metric] of [['Sales', summary.sales], ['Customers', summary.customers], ['Jobs', summary.jobs]] as const) {
    if (metric.value != null && metric.prev_value != null && metric.value !== metric.prev_value) insights.push(`${label} ${metric.value > metric.prev_value ? 'increased' : 'fell'} ${fmtVswtVal(Math.abs(metric.value - metric.prev_value), label === 'Sales' ? 'currency' : 'count')} week over week.`)
  }
  if (!insights.length) insights.push('Add another weekly upload to unlock movement insights.')
  const latestUpload = weeks.find(w => w.week === summary.latest_week)?.uploaded_at
  return <Card className="p-4">
    <div className="flex justify-between items-baseline gap-3 mb-3"><p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Performance signals</p><Button onClick={onExport} variant="secondary" className="text-xs">Export CSV</Button></div>
    <div className="space-y-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>{insights.map(i => <p key={i}>• {i}</p>)}</div>
    <p className="text-[11px] mt-3" style={{ color: 'var(--ms-text-muted)' }}>{latestUpload ? `Latest data uploaded ${new Date(latestUpload).toLocaleDateString()}.` : 'Upload timestamp unavailable.'} {weeks.length} weekly upload{weeks.length === 1 ? '' : 's'} on file.</p>
  </Card>
}
async function downloadRegionalCsv() {
  const response = await getVswtExportCsv()
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a'); link.href = url; link.download = 'regional-report.csv'; link.click(); URL.revokeObjectURL(url)
}

function VswtStatCard({ label, currentValue, value, previousValue, previousRank, type, rank, n }: { label: string; currentValue: number | null; value: string; previousValue: number | null; previousRank: number | null; type: 'currency' | 'count'; rank: number | null; n: number }) {
  const tone = rankTone(rank, n)
  const toneColors = rankToneColors(tone)
  const delta = currentValue != null && previousValue != null ? (previousValue === 0 ? null : ((currentValue - previousValue) / Math.abs(previousValue)) * 100) : null
  const rankDelta = rank != null && previousRank != null ? previousRank - rank : null
  return (
    <Card className="p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full" style={{ backgroundColor: toneColors.fg }} />
      <p className="text-[11px] uppercase tracking-wide font-medium mb-1" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
      <p className="text-xl font-bold" style={{ color: 'var(--ms-text)' }}>{value}</p>
      {rank != null && (
        <p className="text-xs font-semibold mt-1" style={{ color: toneColors.fg }}>#{rank} / {n}</p>
      )}
      <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1 text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
        {previousValue != null && <span>Prev {fmtVswtVal(previousValue, type)}</span>}
        {delta != null && <span style={{ color: delta >= 0 ? '#1A6A3A' : '#A33838' }}>{delta >= 0 ? '+' : ''}{delta.toFixed(1)}%</span>}
        {rankDelta != null && <span className="inline-flex items-center gap-0.5" style={{ color: rankDelta >= 0 ? '#1A6A3A' : '#A33838' }}>{rankDelta >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}{Math.abs(rankDelta)} rank{Math.abs(rankDelta) === 1 ? '' : 's'}</span>}
      </div>
    </Card>
  )
}
