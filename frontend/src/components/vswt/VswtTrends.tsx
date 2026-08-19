import { useQuery } from '@tanstack/react-query'
import { getVswtTrends } from '@/lib/api'
import { Card, EmptyState, Spinner } from '@/components/ui'
import { fmtVswtVal } from './format'
import { VswtViewingBanner, type ViewingShop } from './VswtViewingBanner'

const SHOP_COLOR = 'var(--ms-accent)'
const REGION_COLOR = 'var(--ms-text-muted)'
const PEER_COLOR = '#5B9BD5'

function ChartPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="p-4">
      <p className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>{title}</p>
      {children}
    </Card>
  )
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex gap-4 mb-3 flex-wrap">
      {items.map(it => (
        <span key={it.label} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: it.color, display: 'inline-block' }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

/** Grouped bars (2-3 series per category), CSS-only — matches the app's existing bar-chart style
 * (no charting library). */
function GroupedBars({
  categories, series, format,
}: {
  categories: string[]
  series: { label: string; color: string; values: (number | null)[] }[]
  format: (v: number) => string
}) {
  const max = Math.max(1, ...series.flatMap(s => s.values.map(v => v ?? 0)))
  return (
    <div className="flex items-end gap-4" style={{ height: 180 }}>
      {categories.map((cat, i) => (
        <div key={cat} className="flex-1 flex flex-col items-center gap-1 min-w-0">
          <div className="flex items-end gap-1" style={{ height: 140 }}>
            {series.map(s => {
              const v = s.values[i]
              const h = v ? Math.max(Math.round((v / max) * 140), 3) : 0
              return (
                <div
                  key={s.label}
                  title={v != null ? `${s.label}: ${format(v)}` : undefined}
                  className="w-4 rounded-t transition-all"
                  style={{ height: h, backgroundColor: s.color }}
                />
              )
            })}
          </div>
          <span className="text-[10px] truncate w-full text-center" style={{ color: 'var(--ms-text-muted)' }}>{cat}</span>
        </div>
      ))}
    </div>
  )
}

export function VswtTrends({
  viewingShop, onBackToMyShop,
}: { viewingShop?: ViewingShop | null; onBackToMyShop?: () => void } = {}) {
  const { data, isLoading } = useQuery({
    queryKey: ['vswt-trends', viewingShop?.shopNumber ?? null],
    queryFn: () => getVswtTrends(8, viewingShop?.shopNumber).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load trends." />
  if (!data.available) return <EmptyState message="No trend data available for this shop yet." />

  const weekLabels = data.sales_series.map(s => String(s.week))
  const maxRank = data.region_size
  const shopLabel = data.viewing_own_shop ? 'Your Shop' : (data.shop_name ?? 'Shop')

  return (
    <div className="flex flex-col gap-5">
      {viewingShop && onBackToMyShop && <VswtViewingBanner viewing={viewingShop} onBack={onBackToMyShop} />}
      <ChartPanel title={`Sales — ${data.viewing_own_shop ? 'your shop' : shopLabel} vs region vs peer average`}>
        <Legend items={[
          { label: shopLabel, color: SHOP_COLOR },
          { label: 'Region Avg', color: REGION_COLOR },
          { label: 'Peer Avg', color: PEER_COLOR },
        ]}
        />
        <GroupedBars
          categories={weekLabels}
          series={[
            { label: shopLabel, color: SHOP_COLOR, values: data.sales_series.map(s => s.shop) },
            { label: 'Region Avg', color: REGION_COLOR, values: data.sales_series.map(s => s.region_avg) },
            { label: 'Peer Avg', color: PEER_COLOR, values: data.sales_series.map(s => s.peer_avg) },
          ]}
          format={v => fmtVswtVal(v, 'currency')}
        />
      </ChartPanel>

      <ChartPanel title="Sales rank trend — taller is better">
        <div className="flex items-end gap-2" style={{ height: 160 }}>
          {data.rank_series.map(r => {
            const h = r.rank ? Math.max(Math.round(((maxRank - r.rank + 1) / maxRank) * 120), 3) : 0
            return (
              <div key={r.week} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                <span className="text-[10px] font-semibold" style={{ color: 'var(--ms-text)' }}>{r.rank ?? '—'}</span>
                <div className="w-full rounded-t" style={{ height: h, backgroundColor: SHOP_COLOR, minHeight: r.rank ? 3 : 0 }} />
                <span className="text-[10px]" style={{ color: 'var(--ms-text-muted)' }}>{r.week}</span>
              </div>
            )
          })}
        </div>
      </ChartPanel>

      <ChartPanel title={`Category sales — Week ${data.latest_week}`}>
        <Legend items={[{ label: shopLabel, color: SHOP_COLOR }, { label: 'Region Avg', color: REGION_COLOR }]} />
        <GroupedBars
          categories={data.category_series.map(c => c.name)}
          series={[
            { label: shopLabel, color: SHOP_COLOR, values: data.category_series.map(c => c.shop) },
            { label: 'Region Avg', color: REGION_COLOR, values: data.category_series.map(c => c.region_avg) },
          ]}
          format={v => fmtVswtVal(v, 'currency')}
        />
      </ChartPanel>
    </div>
  )
}
