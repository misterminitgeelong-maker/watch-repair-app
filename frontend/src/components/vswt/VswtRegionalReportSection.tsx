import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Gauge, LayoutGrid, Table2, Trophy, LineChart as LineChartIcon, Upload, Search, FileText } from 'lucide-react'
import { getVswtSummary, type VswtSummary, type VswtUnavailable } from '@/lib/api'
import { Card, EmptyState, Spinner } from '@/components/ui'
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
import type { ViewingShop } from './VswtViewingBanner'

type SubTab = 'overview' | 'directory' | 'shop-report' | 'scorecard' | 'rankings' | 'leaderboards' | 'trends' | 'upload'

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
  const { data, isLoading } = useQuery({ queryKey: ['vswt-summary'], queryFn: () => getVswtSummary().then(r => r.data) })

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
            <VswtStatCard label="Sales" value={fmtVswtVal(summary.sales.value, 'currency')} rank={summary.sales.region_rank} n={summary.region_size} />
            <VswtStatCard label="Customers" value={fmtVswtVal(summary.customers.value, 'count')} rank={summary.customers.region_rank} n={summary.region_size} />
            <VswtStatCard label="Jobs" value={fmtVswtVal(summary.jobs.value, 'count')} rank={summary.jobs.region_rank} n={summary.region_size} />
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
    </div>
  )
}

function VswtStatCard({ label, value, rank, n }: { label: string; value: string; rank: number | null; n: number }) {
  const tone = rankTone(rank, n)
  const toneColors = rankToneColors(tone)
  return (
    <Card className="p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full" style={{ backgroundColor: toneColors.fg }} />
      <p className="text-[11px] uppercase tracking-wide font-medium mb-1" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
      <p className="text-xl font-bold" style={{ color: 'var(--ms-text)' }}>{value}</p>
      {rank != null && (
        <p className="text-xs font-semibold mt-1" style={{ color: toneColors.fg }}>#{rank} / {n}</p>
      )}
    </Card>
  )
}
