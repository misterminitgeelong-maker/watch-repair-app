import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Search } from 'lucide-react'
import { getVswtDirectory, type VswtDirectoryRow, type VswtKpiGroup } from '@/lib/api'
import { Badge, EmptyState, Spinner } from '@/components/ui'
import { PillToggle } from './VswtRegionalReportSection'
import { fmtVswtVal, VSWT_KPI_GROUPS } from './format'

const GROUPS = VSWT_KPI_GROUPS

type SortState = { key: string; dir: 'asc' | 'desc' }

export function VswtShopDirectory({ onSelectShop }: { onSelectShop: (shopNumber: string, shopName: string | null) => void }) {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [group, setGroup] = useState<VswtKpiGroup>('Headline')
  const [peerOnly, setPeerOnly] = useState(false)
  const [sort, setSort] = useState<SortState>({ key: 'shop_name', dir: 'asc' })

  // Wait for a short pause in typing before refetching, so each keystroke doesn't
  // fire its own round trip against the full region.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const { data, isLoading } = useQuery({
    queryKey: ['vswt-directory', debouncedSearch, group, peerOnly],
    queryFn: () => getVswtDirectory({ search: debouncedSearch || undefined, group, peerOnly }).then(r => r.data),
    // Keep showing the previous rows while a new search/filter is in flight instead of
    // blanking the table out to a spinner between every debounced fetch.
    placeholderData: keepPreviousData,
  })

  const sortedRows = useMemo(() => {
    if (!data?.available) return []
    const rows = [...data.rows]
    rows.sort((a, b) => {
      let av: string | number | null
      let bv: string | number | null
      if (sort.key === 'shop_name') {
        av = (a.shop_name ?? '').toLowerCase()
        bv = (b.shop_name ?? '').toLowerCase()
      } else if (sort.key === 'area_name') {
        av = (a.area_name ?? '').toLowerCase()
        bv = (b.area_name ?? '').toLowerCase()
      } else {
        av = a.values[sort.key]
        bv = b.values[sort.key]
      }
      if (av == null && bv == null) return 0
      if (av == null) return 1 // nulls always sink, regardless of direction
      if (bv == null) return -1
      const cmp = typeof av === 'string' ? av.localeCompare(bv as string) : av - (bv as number)
      return sort.dir === 'asc' ? cmp : -cmp
    })
    return rows
  }, [data, sort])

  function toggleSort(key: string) {
    setSort(prev => (prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))
  }

  if (isLoading) return <Spinner />
  if (!data) return <EmptyState message="Couldn't load the shop directory." />
  if (!data.available) return <EmptyState message="This shop isn't linked to a VSWT shop number yet, so the directory isn't available here." />

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search shop name, number, or area…"
            className="w-full pl-8 pr-3 py-1.5 rounded-md text-sm"
            style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          />
        </div>
        <PillToggle value={group} onChange={setGroup} options={GROUPS.map(g => ({ key: g, label: g }))} />
        <label className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          <input type="checkbox" checked={peerOnly} onChange={e => setPeerOnly(e.target.checked)} />
          Franchise + Comparable only
        </label>
      </div>

      <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>
        Week {data.week} · {data.result_size} of {data.region_size} shops · click a shop to see its full profile
      </p>

      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
        <table className="border-collapse text-sm" style={{ width: '100%' }}>
          <thead>
            <tr style={{ background: 'var(--ms-bg)' }}>
              <SortableHead label="Shop" sortKey="shop_name" sort={sort} onSort={toggleSort} align="left" />
              <SortableHead label="Area" sortKey="area_name" sort={sort} onSort={toggleSort} align="left" />
              {data.kpis.map(k => (
                <SortableHead key={k.key} label={k.label} sortKey={k.key} sort={sort} onSort={toggleSort} />
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map(row => (
              <DirectoryRow key={row.shop_number} row={row} kpis={data.kpis} onSelect={onSelectShop} />
            ))}
            {sortedRows.length === 0 && (
              <tr>
                <td colSpan={2 + data.kpis.length} className="text-center text-sm py-8" style={{ color: 'var(--ms-text-muted)' }}>
                  No shops match "{search}".
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SortableHead({
  label, sortKey, sort, onSort, align = 'right',
}: { label: string; sortKey: string; sort: SortState; onSort: (key: string) => void; align?: 'left' | 'right' }) {
  const active = sort.key === sortKey
  return (
    <th
      onClick={() => onSort(sortKey)}
      className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide whitespace-nowrap cursor-pointer select-none"
      style={{
        textAlign: align,
        color: active ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
        borderBottom: '1px solid var(--ms-border)',
      }}
    >
      <span className="inline-flex items-center gap-1" style={{ flexDirection: align === 'left' ? 'row' : 'row-reverse' }}>
        {label}
        {active && (sort.dir === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
      </span>
    </th>
  )
}

function DirectoryRow({
  row, kpis, onSelect,
}: { row: VswtDirectoryRow; kpis: { key: string; type: 'currency' | 'percent' | 'count' | 'ratio' }[]; onSelect: (shopNumber: string, shopName: string | null) => void }) {
  return (
    <tr
      onClick={() => onSelect(row.shop_number, row.shop_name)}
      className="cursor-pointer transition-colors"
      style={row.is_me ? { backgroundColor: 'var(--ms-accent-light)' } : undefined}
      onMouseEnter={e => { if (!row.is_me) e.currentTarget.style.backgroundColor = 'var(--ms-bg)' }}
      onMouseLeave={e => { if (!row.is_me) e.currentTarget.style.backgroundColor = '' }}
    >
      <td className="px-3 py-2" style={{ borderBottom: '1px solid var(--ms-border)' }}>
        <div className="flex items-center gap-1.5">
          <span className="font-medium" style={{ color: row.is_me ? 'var(--ms-accent)' : 'var(--ms-text)' }}>
            {row.shop_name ?? row.shop_number}
          </span>
          <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>#{row.shop_number}</span>
          {row.is_me && <Badge variant="default">You</Badge>}
        </div>
        <div className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
          {row.store_format}{row.store_format && row.comp_status ? ' · ' : ''}{row.comp_status}
        </div>
      </td>
      <td className="px-3 py-2 text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-mid)' }}>
        {row.area_name ?? '—'}
      </td>
      {kpis.map(k => (
        <td key={k.key} className="px-3 py-2 text-sm text-right" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
          {fmtVswtVal(row.values[k.key], k.type)}
        </td>
      ))}
    </tr>
  )
}
