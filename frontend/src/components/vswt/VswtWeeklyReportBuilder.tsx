import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Download, Search, X } from 'lucide-react'
import {
  getVswtDirectory, getVswtWeeklyReport, getVswtWeeklyReportPdf,
  type VswtKpiDef, type VswtUnavailable, type VswtWeeklyReport, type VswtWeeklyReportShop,
} from '@/lib/api'
import { Badge, Button, Card, EmptyState, Spinner } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import { fmtVswtVal } from './format'

const DEFAULT_TITLE = 'Weekly Regional Report'

function storageKey(tenantId: string | null, suffix: string) {
  return `vswt-weekly-report:${tenantId ?? 'anon'}:${suffix}`
}

function loadShopNumbers(tenantId: string | null): string[] {
  try {
    const raw = localStorage.getItem(storageKey(tenantId, 'shops'))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

function saveShopNumbers(tenantId: string | null, shopNumbers: string[]) {
  try {
    localStorage.setItem(storageKey(tenantId, 'shops'), JSON.stringify(shopNumbers))
  } catch {
    /* ignore quota / private mode */
  }
}

function loadTitle(tenantId: string | null): string {
  try {
    return localStorage.getItem(storageKey(tenantId, 'title')) || DEFAULT_TITLE
  } catch {
    return DEFAULT_TITLE
  }
}

function saveTitle(tenantId: string | null, title: string) {
  try {
    localStorage.setItem(storageKey(tenantId, 'title'), title)
  } catch {
    /* ignore quota / private mode */
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
}

/** Build-your-own weekly report: search the whole region, pick a handful of shops (your own
 * franchisee group, say), and get a fully comprehensive week — every KPI HQ tracks, grouped the
 * same way the rest of Regional Reports groups them, each with a value *and* a region rank — laid
 * out for just those shops. Downloads as a PDF you can drop straight into a group chat. Picks and
 * title are remembered per-tenant so this doesn't need rebuilding from scratch every week. */
export function VswtWeeklyReportBuilder() {
  const { tenantId } = useAuth()
  const [shopNumbers, setShopNumbers] = useState<string[]>(() => loadShopNumbers(tenantId))
  const [shopNames, setShopNames] = useState<Record<string, string | null>>({})
  const [title, setTitle] = useState(() => loadTitle(tenantId))
  const [week, setWeek] = useState<number | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => { saveShopNumbers(tenantId, shopNumbers) }, [tenantId, shopNumbers])
  useEffect(() => { saveTitle(tenantId, title) }, [tenantId, title])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const { data: dirData, isLoading: dirLoading } = useQuery({
    queryKey: ['vswt-directory', debouncedSearch, 'Headline', false],
    queryFn: () => getVswtDirectory({ search: debouncedSearch || undefined, group: 'Headline' }).then(r => r.data),
    placeholderData: keepPreviousData,
    enabled: debouncedSearch.trim().length > 0,
  })

  const { data: reportData, isLoading: reportLoading, isFetching: reportFetching } = useQuery({
    queryKey: ['vswt-weekly-report', shopNumbers, week],
    queryFn: () => getVswtWeeklyReport({ shopNumbers, week }).then(r => r.data),
    enabled: shopNumbers.length > 0,
  })

  const downloadMut = useMutation({
    mutationFn: () => getVswtWeeklyReportPdf({ shopNumbers, week: reportData?.available ? reportData.week : week, title }),
    onSuccess: r => {
      const weekLabel = reportData?.available ? reportData.week : week ?? 'latest'
      downloadBlob(r.data, `weekly-report-week-${weekLabel}.pdf`)
    },
  })

  function toggleShop(shopNumber: string, shopName: string | null) {
    setShopNames(prev => ({ ...prev, [shopNumber]: shopName }))
    setShopNumbers(prev => (prev.includes(shopNumber) ? prev.filter(s => s !== shopNumber) : [...prev, shopNumber]))
  }

  function removeShop(shopNumber: string) {
    setShopNumbers(prev => prev.filter(s => s !== shopNumber))
  }

  // Keep a display name for every chip even after the directory search that found it has moved
  // on — the report response (once loaded) is the source of truth, directory search results are
  // just how names get learned before the first fetch completes.
  const chipShops = useMemo(
    () => shopNumbers.map(sn => {
      const fromReport = reportData?.available ? reportData.shops.find(s => s.shop_number === sn) : undefined
      return { shop_number: sn, shop_name: fromReport?.shop_name ?? shopNames[sn] ?? null }
    }),
    [shopNumbers, shopNames, reportData],
  )

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
        Search the region, pick the shops you want in this week's report, then download it as a PDF
        ready to drop into your group chat — every KPI HQ tracks, with a rank alongside each value.
        Your picks and title are remembered for next time.
      </p>

      <Card className="p-4 mb-4">
        <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--ms-text-muted)' }}>
          Report title
        </label>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder={DEFAULT_TITLE}
          className="w-full max-w-md px-3 py-1.5 rounded-md text-sm mb-4"
          style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
        />

        <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--ms-text-muted)' }}>
          Search shops to add
        </label>
        <div className="relative max-w-md mb-2">
          <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search shop name, number, or area…"
            className="w-full pl-8 pr-3 py-1.5 rounded-md text-sm"
            style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          />
        </div>

        {debouncedSearch.trim().length > 0 && (
          <div className="max-w-md rounded-lg mb-4 max-h-64 overflow-y-auto" style={{ border: '1px solid var(--ms-border)' }}>
            {dirLoading && <div className="p-3"><Spinner /></div>}
            {dirData?.available && dirData.rows.length === 0 && (
              <p className="text-sm p-3" style={{ color: 'var(--ms-text-muted)' }}>No shops match "{search}".</p>
            )}
            {dirData?.available && dirData.rows.map(row => {
              const picked = shopNumbers.includes(row.shop_number)
              return (
                <button
                  key={row.shop_number}
                  type="button"
                  onClick={() => toggleShop(row.shop_number, row.shop_name)}
                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm transition-colors"
                  style={{
                    borderBottom: '1px solid var(--ms-border)',
                    backgroundColor: picked ? 'var(--ms-accent-light)' : 'transparent',
                  }}
                >
                  <span>
                    <span style={{ color: 'var(--ms-text)', fontWeight: 500 }}>{row.shop_name ?? row.shop_number}</span>
                    <span className="text-xs ml-1.5" style={{ color: 'var(--ms-text-muted)' }}>
                      #{row.shop_number}{row.area_name ? ` · ${row.area_name}` : ''}
                    </span>
                  </span>
                  <span className="text-xs font-semibold" style={{ color: picked ? 'var(--ms-accent)' : 'var(--ms-text-muted)' }}>
                    {picked ? 'Added ✓' : '+ Add'}
                  </span>
                </button>
              )
            })}
          </div>
        )}

        <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--ms-text-muted)' }}>
          In this report ({chipShops.length})
        </label>
        {chipShops.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Search above and add shops to get started.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {chipShops.map(s => (
              <span
                key={s.shop_number}
                className="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-full text-xs font-medium"
                style={{ backgroundColor: 'var(--ms-accent-light)', color: 'var(--ms-accent)' }}
              >
                {s.shop_name ?? `#${s.shop_number}`}
                <button
                  type="button"
                  onClick={() => removeShop(s.shop_number)}
                  className="rounded-full p-0.5"
                  aria-label={`Remove ${s.shop_name ?? s.shop_number}`}
                  style={{ color: 'inherit' }}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
      </Card>

      {shopNumbers.length === 0 ? (
        <EmptyState message="Pick at least one shop above to preview and download a report." />
      ) : (
        <WeeklyReportPreview
          reportData={reportData}
          isLoading={reportLoading}
          isFetching={reportFetching}
          title={title}
          onWeekChange={setWeek}
          onDownload={() => downloadMut.mutate()}
          downloading={downloadMut.isPending}
        />
      )}
    </div>
  )
}

function WeeklyReportPreview({
  reportData: data, isLoading, isFetching, title, onWeekChange, onDownload, downloading,
}: {
  reportData: VswtWeeklyReport | VswtUnavailable | undefined
  isLoading: boolean
  isFetching: boolean
  title: string
  onWeekChange: (w: number) => void
  onDownload: () => void
  downloading: boolean
}) {
  const kpisByGroup = useMemo(() => {
    if (!data?.available) return []
    const map = new Map<string, VswtKpiDef[]>()
    for (const k of data.kpis) {
      if (!map.has(k.group)) map.set(k.group, [])
      map.get(k.group)!.push(k)
    }
    return data.groups.filter(g => map.has(g)).map(g => ({ group: g, kpis: map.get(g)! }))
  }, [data])

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load this report." />
  if (!data.available) {
    return <EmptyState message="None of the selected shops were found in the region's data for this week." />
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
          <div>
            <h3 className="text-base font-bold" style={{ color: 'var(--ms-text)' }}>{title || DEFAULT_TITLE}</h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
              Week {data.week} · {data.region_size} shops in region · {data.shops.length} shop{data.shops.length !== 1 ? 's' : ''} in this report
              {isFetching && ' · refreshing…'}
            </p>
            {data.missing_shop_numbers.length > 0 && (
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-badge-alert-text)' }}>
                Not found this week: {data.missing_shop_numbers.join(', ')}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={data.week}
              onChange={e => onWeekChange(Number(e.target.value))}
              className="rounded-md px-2 py-1 text-sm"
              style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            >
              {data.weeks.map(w => <option key={w} value={w}>Week {w}</option>)}
            </select>
            <Button onClick={onDownload} disabled={downloading}>
              <Download size={14} /> {downloading ? 'Preparing…' : 'Download PDF'}
            </Button>
          </div>
        </div>

        <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>Summary</p>
        <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
          <table className="border-collapse text-sm" style={{ width: '100%' }}>
            <thead>
              <tr style={{ background: 'var(--ms-bg)' }}>
                <th style={{ ...thStyle, textAlign: 'left' }}>Shop</th>
                <th style={{ ...thStyle, textAlign: 'left' }}>Area</th>
                <th style={thStyle}>Sales $</th>
                <th style={thStyle}>Sales Rank</th>
                <th style={thStyle}>Customers</th>
                <th style={thStyle}>Jobs</th>
                <th style={thStyle}>Overall Avg Rank</th>
              </tr>
            </thead>
            <tbody>
              {data.shops.map(s => (
                <tr key={s.shop_number} style={s.is_me ? { backgroundColor: 'var(--ms-accent-light)' } : undefined}>
                  <td style={{ ...tdStyle, textAlign: 'left', color: s.is_me ? 'var(--ms-accent)' : 'var(--ms-text)', fontWeight: 600 }}>
                    <span className="flex items-center gap-1.5">
                      {s.shop_name ?? s.shop_number}
                      {s.is_me && <Badge variant="default">You</Badge>}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'left', color: 'var(--ms-text-mid)' }}>{s.area_name ?? '—'}</td>
                  <td style={{ ...tdStyle, color: 'var(--ms-text)', fontWeight: 600 }}>{fmtVswtVal(s.sales_value, 'currency')}</td>
                  <td style={tdStyle}>{s.sales_rank != null ? <Badge variant="default">#{s.sales_rank}</Badge> : <span style={{ color: 'var(--ms-text-muted)' }}>—</span>}</td>
                  <td style={{ ...tdStyle, color: 'var(--ms-text)' }}>{fmtVswtVal(s.customer_value, 'count')}</td>
                  <td style={{ ...tdStyle, color: 'var(--ms-text)' }}>{fmtVswtVal(s.jobs_value, 'count')}</td>
                  <td style={{ ...tdStyle, color: 'var(--ms-text)' }}>{s.overall_avg_rank != null ? `#${s.overall_avg_rank.toFixed(1)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 700, color: 'var(--ms-text)' }}>Group total</td>
                <td style={tdStyle} />
                <td style={{ ...tdStyle, fontWeight: 700, color: 'var(--ms-text)' }}>{fmtVswtVal(data.totals.sales, 'currency')}</td>
                <td style={{ ...tdStyle, fontWeight: 700, color: 'var(--ms-text)' }}>
                  {data.totals.avg_sales_rank != null ? `avg #${data.totals.avg_sales_rank.toFixed(1)}` : '—'}
                </td>
                <td style={{ ...tdStyle, fontWeight: 700, color: 'var(--ms-text)' }}>{fmtVswtVal(data.totals.customers, 'count')}</td>
                <td style={{ ...tdStyle, fontWeight: 700, color: 'var(--ms-text)' }}>{fmtVswtVal(data.totals.jobs, 'count')}</td>
                <td style={tdStyle} />
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>

      {kpisByGroup.map(({ group, kpis }) => (
        <Card key={group} className="p-5">
          <p className="text-sm font-bold mb-2" style={{ color: 'var(--ms-text)' }}>{group}</p>
          <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
            <table className="border-collapse text-sm" style={{ width: '100%' }}>
              <thead>
                <tr style={{ background: 'var(--ms-bg)' }}>
                  <th style={{ ...thStyle, textAlign: 'left' }}>Shop</th>
                  {kpis.map(k => <th key={k.key} style={thStyle}>{k.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.shops.map(s => (
                  <tr key={s.shop_number} style={s.is_me ? { backgroundColor: 'var(--ms-accent-light)' } : undefined}>
                    <td style={{ ...tdStyle, textAlign: 'left', color: s.is_me ? 'var(--ms-accent)' : 'var(--ms-text)', fontWeight: 600 }}>
                      {s.shop_name ?? s.shop_number}
                    </td>
                    {kpis.map(k => <ValueRankCell key={k.key} shop={s} kpi={k} />)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </div>
  )
}

function ValueRankCell({ shop, kpi }: { shop: VswtWeeklyReportShop; kpi: VswtKpiDef }) {
  const value = shop.values[kpi.key]
  const rank = shop.ranks[kpi.key]
  return (
    <td style={{ ...tdStyle, color: 'var(--ms-text)' }}>
      {fmtVswtVal(value, kpi.type)}
      {rank != null && <span className="block text-[10px]" style={{ color: 'var(--ms-text-muted)' }}>#{rank}</span>}
    </td>
  )
}

const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'right', fontSize: 11, fontWeight: 600, color: 'var(--ms-text-muted)',
  borderBottom: '1px solid var(--ms-border)', textTransform: 'uppercase', letterSpacing: 0.4, whiteSpace: 'nowrap',
}
const tdStyle: React.CSSProperties = {
  padding: '7px 12px', textAlign: 'right', borderBottom: '1px solid var(--ms-border)',
}
