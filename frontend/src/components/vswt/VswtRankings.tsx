import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getVswtRankings } from '@/lib/api'
import { Badge, EmptyState, Spinner } from '@/components/ui'
import { fmtVswtVal, rankToneBadgeVariant, rankTone } from './format'
import { VswtViewingBanner, type ViewingShop } from './VswtViewingBanner'

export function VswtRankings({
  viewingShop, onBackToMyShop,
}: { viewingShop?: ViewingShop | null; onBackToMyShop?: () => void } = {}) {
  const [week, setWeek] = useState<number | undefined>(undefined)
  const { data, isLoading } = useQuery({
    queryKey: ['vswt-rankings', week, viewingShop?.shopNumber ?? null],
    queryFn: () => getVswtRankings(week, viewingShop?.shopNumber).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load rankings." />
  if (!data.available) return <EmptyState message="No ranking data available for this shop yet." />

  let lastGroup: string | null = null

  return (
    <div>
      {viewingShop && onBackToMyShop && <VswtViewingBanner viewing={viewingShop} onBack={onBackToMyShop} />}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Week</span>
        <select
          value={data.week}
          onChange={e => setWeek(Number(e.target.value))}
          className="rounded-md px-2 py-1 text-sm"
          style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
        >
          {data.weeks.map(w => <option key={w} value={w}>{w}</option>)}
        </select>
        <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Peer group = Franchise + Comparable stores only ({data.peer_size} shops)
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
        <table className="border-collapse text-sm" style={{ width: '100%' }}>
          <thead>
            <tr style={{ background: 'var(--ms-bg)' }}>
              <th style={{ ...thStyle, textAlign: 'left', position: 'sticky', left: 0, background: 'var(--ms-bg)' }}>KPI</th>
              <th style={thStyle}>{data.viewing_own_shop ? 'Your Shop' : (data.shop_name ?? 'Shop')}</th>
              <th style={thStyle}>Region Avg</th>
              <th style={thStyle}>Region Rank</th>
              <th style={thStyle}>Percentile</th>
              <th style={thStyle}>Peer Avg</th>
              <th style={thStyle}>Peer Rank</th>
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
                  showGroupHeader={showGroupHeader}
                  regionSize={data.region_size}
                  peerSize={data.peer_size}
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
  row, showGroupHeader, regionSize, peerSize,
}: {
  row: {
    key: string; label: string; group: string; type: 'currency' | 'percent' | 'count' | 'ratio'
    value: number | null; region_avg: number | null; region_rank: number | null
    percentile: number | null; peer_avg: number | null; peer_rank: number | null
  }
  showGroupHeader: boolean
  regionSize: number
  peerSize: number
}) {
  return (
    <>
      {showGroupHeader && (
        <tr>
          <td
            colSpan={7}
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
        <td style={{ ...tdStyle, color: 'var(--ms-text)', fontWeight: 600 }}>{fmtVswtVal(row.value, row.type)}</td>
        <td style={{ ...tdStyle, color: 'var(--ms-text-muted)' }}>{fmtVswtVal(row.region_avg, row.type)}</td>
        <td style={tdStyle}>
          {row.region_rank != null
            ? <Badge variant={rankToneBadgeVariant(rankTone(row.region_rank, regionSize))}>#{row.region_rank}</Badge>
            : <span style={{ color: 'var(--ms-text-muted)' }}>—</span>}
        </td>
        <td style={{ ...tdStyle, color: 'var(--ms-text-muted)' }}>{row.percentile != null ? `${(row.percentile * 100).toFixed(0)}%` : '—'}</td>
        <td style={{ ...tdStyle, color: 'var(--ms-text-muted)' }}>{fmtVswtVal(row.peer_avg, row.type)}</td>
        <td style={tdStyle}>
          {row.peer_rank != null
            ? <Badge variant={rankToneBadgeVariant(rankTone(row.peer_rank, peerSize))}>#{row.peer_rank} / {peerSize}</Badge>
            : <span style={{ color: 'var(--ms-text-muted)' }}>—</span>}
        </td>
      </tr>
    </>
  )
}

const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'right', fontSize: 11, fontWeight: 600, color: 'var(--ms-text-muted)',
  borderBottom: '1px solid var(--ms-border)', textTransform: 'uppercase', letterSpacing: 0.4, whiteSpace: 'nowrap',
}
const tdStyle: React.CSSProperties = {
  padding: '7px 12px', textAlign: 'right', borderBottom: '1px solid var(--ms-border)',
}
