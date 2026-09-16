import { useState } from 'react'
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
  categories, series, format, notes,
}: {
  categories: string[]
  series: { label: string; color: string; values: (number | null)[] }[]
  format: (v: number) => string
  notes?: Record<string, string>
}) {
  const max = Math.max(1, ...series.flatMap(s => s.values.map(v => v ?? 0)))
  return (
    <div className="flex items-end gap-4" style={{ height: 180 }}>
      {categories.map((cat, i) => (
        <div key={cat} className="flex-1 flex flex-col items-center gap-1 min-w-0">
          {notes?.[cat] && <span title={notes[cat]} className="w-2 h-2 rounded-full" style={{ background: '#9A5A00' }} />}
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
  const [weeksBack, setWeeksBack] = useState(8)
  const { data, isLoading } = useQuery({
    queryKey: ['vswt-trends', weeksBack, viewingShop?.shopNumber ?? null],
    queryFn: () => getVswtTrends(weeksBack, viewingShop?.shopNumber).then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load trends." />
  if (!data.available) return <EmptyState message="No trend data available for this shop yet." />

  const weekLabels = data.sales_series.map(s => String(s.week))
  const maxRank = data.region_size
  const shopLabel = data.viewing_own_shop ? 'Your Shop' : (data.shop_name ?? 'Shop')
  const notes = Object.fromEntries(data.annotations.map(annotation => [String(annotation.week), annotation.note]))

  return (
    <div className="flex flex-col gap-5">
      {viewingShop && onBackToMyShop && <VswtViewingBanner viewing={viewingShop} onBack={onBackToMyShop} />}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Compare</span>
        <select value={weeksBack} onChange={e => setWeeksBack(Number(e.target.value))} className="rounded-md px-2 py-1 text-sm" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
          {[4, 8, 13, 26, 52, 104].map(w => <option key={w} value={w}>{w === 104 ? 'All available weeks' : `Last ${w} weeks`}</option>)}
        </select>
        <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Week-over-week values and rank movement are shown in the scorecard.</span>
      </div>
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
          notes={notes}
        />
      </ChartPanel>

      <ChartPanel title={`Customers and jobs — ${data.viewing_own_shop ? 'your shop' : shopLabel} vs region vs peer average`}>
        <Legend items={[{ label: shopLabel, color: SHOP_COLOR }, { label: 'Region Avg', color: REGION_COLOR }, { label: 'Peer Avg', color: PEER_COLOR }]} />
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>Customers</p>
            <GroupedBars categories={data.customers_series.map(s => String(s.week))} series={[{ label: shopLabel, color: SHOP_COLOR, values: data.customers_series.map(s => s.shop) }, { label: 'Region Avg', color: REGION_COLOR, values: data.customers_series.map(s => s.region_avg) }, { label: 'Peer Avg', color: PEER_COLOR, values: data.customers_series.map(s => s.peer_avg) }]} format={v => fmtVswtVal(v, 'count')} />
          </div>
          <div>
            <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>Jobs</p>
            <GroupedBars categories={data.jobs_series.map(s => String(s.week))} series={[{ label: shopLabel, color: SHOP_COLOR, values: data.jobs_series.map(s => s.shop) }, { label: 'Region Avg', color: REGION_COLOR, values: data.jobs_series.map(s => s.region_avg) }, { label: 'Peer Avg', color: PEER_COLOR, values: data.jobs_series.map(s => s.peer_avg) }]} format={v => fmtVswtVal(v, 'count')} />
          </div>
        </div>
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

      {data.annotations.length > 0 && (
        <ChartPanel title="Week notes">
          <div className="space-y-2">
            {data.annotations.filter(annotation => data.weeks.includes(annotation.week)).map(annotation => (
              <div key={annotation.id} className="grid grid-cols-[80px_120px_1fr] gap-3 text-xs rounded-md p-2" style={{ background: 'var(--ms-bg)' }}>
                <strong style={{ color: 'var(--ms-text)' }}>Week {annotation.week}</strong>
                <span className="capitalize" style={{ color: 'var(--ms-accent)' }}>{annotation.event_type.replaceAll('_', ' ')}</span>
                <span style={{ color: 'var(--ms-text-mid)' }}>{annotation.note}</span>
              </div>
            ))}
          </div>
        </ChartPanel>
      )}
    </div>
  )
}
