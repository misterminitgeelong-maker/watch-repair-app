import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getVswtLeaderboards, type VswtLeaderboardEntry } from '@/lib/api'
import { Badge, Card, EmptyState, Spinner } from '@/components/ui'
import { PillToggle } from './VswtRegionalReportSection'
import { fmtVswtVal, rankToneBadgeVariant, rankTone } from './format'

const GROUPS = ['All', 'Headline', 'Conversion', 'Category Sales', 'Category Jobs'] as const

export function VswtLeaderboards() {
  const [group, setGroup] = useState<string>('All')
  const { data, isLoading } = useQuery({
    queryKey: ['vswt-leaderboards', group],
    queryFn: () => getVswtLeaderboards(undefined, group === 'All' ? undefined : group).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load leaderboards." />
  if (!data.available) return <EmptyState message="No leaderboard data available yet." />

  return (
    <div>
      <div className="flex justify-between items-center mb-4 flex-wrap gap-3">
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Week {data.week} — who's ahead of you, and who's behind, across every KPI.
        </p>
        <PillToggle value={group} onChange={setGroup} options={GROUPS.map(g => ({ key: g, label: g }))} />
      </div>
      <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
        {data.boards.map(board => (
          <Card key={board.key} className="p-4">
            <div className="flex justify-between items-baseline mb-2.5">
              <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>{board.label}</p>
              {board.my_rank != null && (
                <Badge variant={rankToneBadgeVariant(rankTone(board.my_rank, board.total))}>You: #{board.my_rank}</Badge>
              )}
            </div>
            <LbList entries={board.top} type={board.type} />
            {board.bottom.length > 0 && (
              <>
                <div className="text-center text-xs my-1.5" style={{ color: 'var(--ms-text-muted)' }}>· · ·</div>
                <LbList entries={board.bottom} type={board.type} />
              </>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}

function LbList({ entries, type }: { entries: VswtLeaderboardEntry[]; type: 'currency' | 'percent' | 'count' | 'ratio' }) {
  return (
    <div className="space-y-0.5">
      {entries.map(e => (
        <div
          key={e.shop_number ?? `rank-${e.rank}`}
          className="flex items-center gap-2 px-1.5 py-1 rounded"
          style={e.is_me ? { backgroundColor: 'var(--ms-accent-light)', border: '1px solid var(--ms-accent)' } : { border: '1px solid transparent' }}
        >
          <span className="w-6 text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>{e.rank}</span>
          <span className="flex-1 text-xs truncate" style={{ color: e.is_me ? 'var(--ms-accent)' : 'var(--ms-text)', fontWeight: e.is_me ? 700 : 400 }}>
            {e.shop_name ?? e.shop_number ?? 'Another shop'}
          </span>
          <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{fmtVswtVal(e.value, type)}</span>
        </div>
      ))}
    </div>
  )
}
