import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getVswtShopReport, type VswtKpiGroup, type VswtShopReportRow } from '@/lib/api'
import { Badge, EmptyState, Spinner } from '@/components/ui'
import { PillToggle } from './VswtRegionalReportSection'
import { fmtVswtVal, rankToneBadgeVariant, rankTone, VSWT_KPI_GROUPS } from './format'
import { VswtViewingBanner, type ViewingShop } from './VswtViewingBanner'

type Window = 'week' | 'month' | 'year'
const WINDOWS: { key: Window; label: string }[] = [
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
  { key: 'year', label: 'Year' },
]

export function VswtShopReport({
  viewingShop, onBackToMyShop,
}: { viewingShop?: ViewingShop | null; onBackToMyShop?: () => void } = {}) {
  const [group, setGroup] = useState<VswtKpiGroup>('Headline')
  const [timeWindow, setTimeWindow] = useState<Window>('week')

  const { data, isLoading } = useQuery({
    queryKey: ['vswt-shop-report', viewingShop?.shopNumber ?? null, group],
    queryFn: () => getVswtShopReport(viewingShop?.shopNumber, group).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load the shop report." />
  if (!data.available) return <EmptyState message="No shop report available for this shop yet." />

  const shopLabel = data.viewing_own_shop ? 'Your Shop' : (data.shop_name ?? 'Shop')
  let lastGroup: string | null = null

  return (
    <div>
      {viewingShop && onBackToMyShop && <VswtViewingBanner viewing={viewingShop} onBack={onBackToMyShop} />}
      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
        Week compares the latest upload only. Month is a rolling 4-week average. Year averages
        every week on file, so it rewards being consistently strong over one standout week — the
        gap between Month and Year is exactly that story.
      </p>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <PillToggle value={timeWindow} onChange={setTimeWindow} options={WINDOWS} />
        <PillToggle value={group} onChange={setGroup} options={VSWT_KPI_GROUPS.map(g => ({ key: g, label: g }))} />
        <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          {data.weeks_tracked} week{data.weeks_tracked !== 1 ? 's' : ''} on file · {data.region_size} shops in region
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
        <table className="border-collapse text-sm" style={{ width: '100%' }}>
          <thead>
            <tr style={{ background: 'var(--ms-bg)' }}>
              <th style={{ ...thStyle, textAlign: 'left', position: 'sticky', left: 0, background: 'var(--ms-bg)' }}>KPI</th>
              <th style={thStyle}>{shopLabel}</th>
              <th style={thStyle}>Region Rank</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map(row => {
              const showGroupHeader = row.group !== lastGroup
              lastGroup = row.group
              return (
                <RowWithGroupHeader
                  key={row.key}
                  row={row}
                  window={timeWindow}
                  showGroupHeader={showGroupHeader}
                  regionSize={data.region_size}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RowWithGroupHeader({
  row, window: timeWindow, showGroupHeader, regionSize,
}: { row: VswtShopReportRow; window: Window; showGroupHeader: boolean; regionSize: number }) {
  const cell = row[timeWindow]
  const note = windowNote(row, timeWindow)
  return (
    <>
      {showGroupHeader && (
        <tr>
          <td
            colSpan={3}
            className="text-[10.5px] font-bold uppercase tracking-wide"
            style={{ padding: '7px 12px', background: 'var(--ms-bg)', color: 'var(--ms-accent)', borderBottom: '1px solid var(--ms-border)', position: 'sticky', left: 0 }}
          >
            {row.group}
          </td>
        </tr>
      )}
      <tr>
        <td style={{ ...tdStyle, textAlign: 'left', position: 'sticky', left: 0, background: 'var(--ms-surface)', color: 'var(--ms-text)', fontWeight: 500 }}>
          {row.label}
        </td>
        <td style={{ ...tdStyle, color: 'var(--ms-text)', fontWeight: 600 }}>
          {fmtVswtVal(cell.value, row.type)}
          {note && <div className="text-[10.5px] font-normal mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{note}</div>}
        </td>
        <td style={tdStyle}>
          {cell.rank != null
            ? <Badge variant={rankToneBadgeVariant(rankTone(cell.rank, regionSize))}>#{cell.rank} / {regionSize}</Badge>
            : <span style={{ color: 'var(--ms-text-muted)' }}>—</span>}
        </td>
      </tr>
    </>
  )
}

function windowNote(row: VswtShopReportRow, timeWindow: Window): string | null {
  if (timeWindow === 'month') return `avg of ${row.month.weeks_counted} wk${row.month.weeks_counted !== 1 ? 's' : ''}`
  if (timeWindow === 'year') {
    const { weeks_counted, best_rank, worst_rank } = row.year
    const base = `avg of ${weeks_counted} wk${weeks_counted !== 1 ? 's' : ''}`
    if (best_rank != null && worst_rank != null && best_rank !== worst_rank) {
      return `${base} · rank ranged #${best_rank}–#${worst_rank}`
    }
    return base
  }
  return null
}

const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'right', fontSize: 11, fontWeight: 600, color: 'var(--ms-text-muted)',
  borderBottom: '1px solid var(--ms-border)', textTransform: 'uppercase', letterSpacing: 0.4, whiteSpace: 'nowrap',
}
const tdStyle: React.CSSProperties = {
  padding: '7px 12px', textAlign: 'right', borderBottom: '1px solid var(--ms-border)',
}
