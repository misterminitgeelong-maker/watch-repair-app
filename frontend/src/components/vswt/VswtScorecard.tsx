import { useQuery } from '@tanstack/react-query'
import { getVswtScorecard } from '@/lib/api'
import { EmptyState, Spinner } from '@/components/ui'
import { fmtVswtVal, rankTone, rankToneColors } from './format'
import { VswtViewingBanner, type ViewingShop } from './VswtViewingBanner'

export function VswtScorecard({
  viewingShop, onBackToMyShop,
}: { viewingShop?: ViewingShop | null; onBackToMyShop?: () => void } = {}) {
  const { data, isLoading } = useQuery({
    queryKey: ['vswt-scorecard', viewingShop?.shopNumber ?? null],
    queryFn: () => getVswtScorecard(viewingShop?.shopNumber).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load the scorecard." />
  if (!data.available) return <EmptyState message="No scorecard data available for this shop yet." />

  const groupCounts: Record<string, number> = {}
  data.kpis.forEach(k => { groupCounts[k.group] = (groupCounts[k.group] ?? 0) + 1 })

  return (
    <div>
      {viewingShop && onBackToMyShop && <VswtViewingBanner viewing={viewingShop} onBack={onBackToMyShop} />}
      <p className="text-sm mb-3" style={{ color: 'var(--ms-text-muted)' }}>
        {data.viewing_own_shop ? "Your shop's" : `${data.shop_name ?? 'This shop'}'s`} rank out of the region, every metric, every week.
      </p>
      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
        <table className="border-collapse text-xs" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th style={stickyHeadStyle} rowSpan={2}>Week</th>
              {data.groups.map(g => (
                <th key={g} colSpan={groupCounts[g] ?? 0} style={groupHeadStyle}>{g}</th>
              ))}
            </tr>
            <tr>
              {data.kpis.map(k => (
                <th key={k.key} style={subHeadStyle}>{k.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.matrix.map(row => (
              <tr key={row.week}>
                <td style={weekCellStyle}>{row.week}</td>
                {data.kpis.map(k => {
                  const cell = row.cells[k.key]
                  const tone = rankTone(cell?.rank ?? null, row.region_size)
                  const colors = rankToneColors(tone)
                  return (
                    <td
                      key={k.key}
                      title={cell && cell.value != null ? `${k.label}: ${fmtVswtVal(cell.value, k.type)}` : undefined}
                      style={{ ...rankCellStyle, backgroundColor: colors.bg, color: colors.fg }}
                    >
                      {cell?.rank ?? '—'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const stickyHeadStyle: React.CSSProperties = {
  position: 'sticky', left: 0, background: 'var(--ms-bg)', color: 'var(--ms-text-muted)',
  padding: '8px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600,
  borderBottom: '1px solid var(--ms-border)', zIndex: 2, minWidth: 64,
}
const groupHeadStyle: React.CSSProperties = {
  background: 'var(--ms-bg)', color: 'var(--ms-accent)', padding: '6px 8px', textAlign: 'center',
  fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6,
  borderBottom: '1px solid var(--ms-border)', borderLeft: '1px solid var(--ms-border)',
}
const subHeadStyle: React.CSSProperties = {
  background: 'var(--ms-bg)', color: 'var(--ms-text-muted)', padding: '6px 8px', textAlign: 'center',
  fontSize: 10.5, fontWeight: 500, borderBottom: '1px solid var(--ms-border)',
  borderLeft: '1px solid var(--ms-border)', whiteSpace: 'nowrap',
}
const weekCellStyle: React.CSSProperties = {
  position: 'sticky', left: 0, background: 'var(--ms-surface)', color: 'var(--ms-text)',
  padding: '7px 12px', fontWeight: 700, fontSize: 12.5, borderBottom: '1px solid var(--ms-border)', zIndex: 1,
}
const rankCellStyle: React.CSSProperties = {
  padding: '7px 8px', textAlign: 'center', fontWeight: 600,
  borderBottom: '1px solid var(--ms-border)', borderLeft: '1px solid var(--ms-border)', minWidth: 56,
}
