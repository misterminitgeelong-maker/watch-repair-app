import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getApiErrorMessage, getProspectCollectorStatus, listProspectCategories, listProspectRegions, searchProspects, type Prospect, type ProspectSearchResponse } from '@/lib/api'
import { Button, Card, PageHeader, Select, Spinner } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'

export default function ProspectsPage() {
  const { data: catData } = useQuery<{ categories: { key: string; label: string }[] }>({
    queryKey: ['prospect-categories'],
    queryFn: () => listProspectCategories().then(r => r.data),
  })
  const { data: regions } = useQuery({
    queryKey: ['prospect-regions'],
    queryFn: () => listProspectRegions().then(r => r.data),
  })

  const [category, setCategory] = useState<string | null>(null)
  const [state, setState] = useState<string>('')
  const [suburbs, setSuburbs] = useState<Set<string>>(new Set())
  const [useLiveApi, setUseLiveApi] = useState(false)
  const [collapsedRegions, setCollapsedRegions] = useState<Set<string>>(new Set())

  const regionGroupsForState: Record<string, string[]> = useMemo(() => {
    if (!state || !regions?.region_groups) return {}
    return regions.region_groups[state] ?? {}
  }, [state, regions])

  const suburbsForState: string[] = useMemo(() => {
    const raw = state && regions?.suburbs?.[state]
    return Array.isArray(raw) ? raw : []
  }, [state, regions?.suburbs])

  const toggleRegion = (regionSuburbs: string[]) => {
    const allSelected = regionSuburbs.every(s => suburbs.has(s))
    setSuburbs(prev => {
      const next = new Set(prev)
      if (allSelected) {
        regionSuburbs.forEach(s => next.delete(s))
      } else {
        regionSuburbs.forEach(s => next.add(s))
      }
      return next
    })
  }

  const toggleRegionCollapse = (region: string) => {
    setCollapsedRegions(prev => {
      const next = new Set(prev)
      if (next.has(region)) next.delete(region)
      else next.add(region)
      return next
    })
  }

  const toggleSuburb = (suburb: string) => {
    setSuburbs(prev => {
      const next = new Set(prev)
      if (next.has(suburb)) next.delete(suburb)
      else next.add(suburb)
      return next
    })
  }

  const selectAllSuburbs = () => {
    setSuburbs(new Set(suburbsForState))
  }

  const clearSuburbs = () => {
    setSuburbs(new Set())
  }

  const searchParams = useMemo(
    () => (category && state ? { category, state, suburbs: suburbs.size ? Array.from(suburbs) : undefined, live: useLiveApi } : null),
    [category, state, suburbs, useLiveApi]
  )

  const [searched, setSearched] = useState(false)

  const { data: searchData, refetch, isFetching, error: searchError } = useQuery<ProspectSearchResponse>({
    queryKey: ['prospects', searchParams?.category, searchParams?.state, searchParams?.suburbs?.join(','), searchParams?.live],
    queryFn: () =>
      searchProspects(
        searchParams!.category,
        searchParams!.state,
        searchParams!.suburbs,
        searchParams!.live
      ).then(r => r.data),
    enabled: false,
    retry: false,
  })

  const { data: collectorStatus } = useQuery({
    queryKey: ['prospect-collector-status'],
    queryFn: () => getProspectCollectorStatus().then(r => r.data),
  })

  return (
    <div className="p-6">
      <MobileServicesSubNav className="mb-4" />
      <PageHeader title="Prospects" />
      <Card className="p-5 mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--ms-text-muted)' }}>
          Search filters
        </h2>
        <div className="flex flex-wrap gap-6">
          <div className="min-w-[200px]">
            <Select
              label="Category"
              value={category ?? ''}
              onChange={e => setCategory(e.target.value || null)}
            >
              <option value="">Select category</option>
              {catData?.categories?.map(c => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </Select>
          </div>
          <div className="min-w-[200px]">
            <Select
              label="State"
              value={state}
              onChange={e => {
                setState(e.target.value)
                setSuburbs(new Set())
                setCollapsedRegions(new Set())
              }}
            >
              <option value="">Select state</option>
              {regions?.states?.map(s => (
                <option key={s.code} value={s.code}>{s.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex items-end gap-3">
            <Button
              onClick={() => { setSearched(true); void refetch() }}
              disabled={!category || !state || isFetching}
            >
              {isFetching ? 'Searching…' : 'Search'}
            </Button>
            <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'var(--ms-text-mid)' }}>
              <input
                type="checkbox"
                checked={useLiveApi}
                onChange={e => setUseLiveApi(e.target.checked)}
                className="rounded border"
                style={{ accentColor: 'var(--ms-accent)' }}
              />
              Refresh from Google (live API)
            </label>
          </div>
        </div>

        {state && (Object.keys(regionGroupsForState).length > 0 ? (
          <div className="mt-5 pt-5" style={{ borderTop: '1px solid var(--ms-border)' }}>
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                Regions — narrow your search
                {suburbs.size > 0 && (
                  <span className="ml-2 text-xs font-normal" style={{ color: 'var(--ms-text-muted)' }}>
                    ({suburbs.size} suburb{suburbs.size !== 1 ? 's' : ''} selected)
                  </span>
                )}
              </label>
              <div className="flex gap-2">
                <button type="button" onClick={selectAllSuburbs} className="text-xs font-medium px-2 py-1 rounded hover:bg-black/5" style={{ color: 'var(--ms-accent)' }}>
                  Select all
                </button>
                <button type="button" onClick={clearSuburbs} className="text-xs font-medium px-2 py-1 rounded hover:bg-black/5" style={{ color: 'var(--ms-text-muted)' }}>
                  Clear
                </button>
              </div>
            </div>

            <div className="space-y-2">
              {Object.entries(regionGroupsForState).map(([region, regionSuburbs]) => {
                const allSelected = regionSuburbs.length > 0 && regionSuburbs.every(s => suburbs.has(s))
                const someSelected = regionSuburbs.some(s => suburbs.has(s))
                const collapsed = collapsedRegions.has(region)
                const isOther = region === 'Other'

                return (
                  <div
                    key={region}
                    className="rounded-lg border overflow-hidden"
                    style={{ borderColor: someSelected ? 'var(--ms-accent)' : 'var(--ms-border)', borderWidth: someSelected ? 1.5 : 1 }}
                  >
                    <div
                      className="flex items-center gap-3 px-3 py-2 select-none"
                      style={{ backgroundColor: allSelected ? 'var(--ms-accent-light)' : someSelected ? 'var(--ms-hover)' : 'var(--ms-surface)' }}
                    >
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
                        onChange={() => toggleRegion(regionSuburbs)}
                        className="rounded"
                        style={{ accentColor: 'var(--ms-accent)', flexShrink: 0 }}
                      />
                      <button
                        type="button"
                        className="flex-1 text-left text-sm font-semibold"
                        style={{ color: 'var(--ms-text)' }}
                        onClick={() => toggleRegionCollapse(region)}
                      >
                        {region}
                        <span className="ml-1.5 text-xs font-normal" style={{ color: 'var(--ms-text-muted)' }}>
                          {someSelected ? `${regionSuburbs.filter(s => suburbs.has(s)).length}/${regionSuburbs.length}` : regionSuburbs.length}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleRegionCollapse(region)}
                        className="text-xs px-1"
                        style={{ color: 'var(--ms-text-muted)' }}
                        aria-label={collapsed ? 'Expand' : 'Collapse'}
                      >
                        {collapsed ? '▸' : '▾'}
                      </button>
                    </div>

                    {!collapsed && (
                      <div className="px-3 py-2 flex flex-wrap gap-x-5 gap-y-1.5 max-h-36 overflow-y-auto" style={{ borderTop: '1px solid var(--ms-border)' }}>
                        {regionSuburbs.map(sub => (
                          <label key={sub} className="flex items-center gap-1.5 cursor-pointer text-xs" style={{ color: 'var(--ms-text)' }}>
                            <input
                              type="checkbox"
                              checked={suburbs.has(sub)}
                              onChange={() => toggleSuburb(sub)}
                              className="rounded"
                              style={{ accentColor: 'var(--ms-accent)' }}
                            />
                            {sub}
                          </label>
                        ))}
                        {isOther && regionSuburbs.length === 0 && (
                          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>No unclassified suburbs.</p>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ) : suburbsForState.length > 0 ? (
          <div className="mt-5 pt-5" style={{ borderTop: '1px solid var(--ms-border)' }}>
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                Suburbs (optional) — narrow your search
              </label>
              <div className="flex gap-2">
                <button type="button" onClick={selectAllSuburbs} className="text-xs font-medium px-2 py-1 rounded hover:bg-black/5" style={{ color: 'var(--ms-accent)' }}>Select all</button>
                <button type="button" onClick={clearSuburbs} className="text-xs font-medium px-2 py-1 rounded hover:bg-black/5" style={{ color: 'var(--ms-text-muted)' }}>Clear</button>
              </div>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-2 max-h-[160px] overflow-y-auto py-1 pr-2" style={{ color: 'var(--ms-text)' }}>
              {suburbsForState.map(sub => (
                <label key={sub} className="flex items-center gap-2 cursor-pointer text-sm">
                  <input type="checkbox" checked={suburbs.has(sub)} onChange={() => toggleSuburb(sub)} className="rounded border" style={{ accentColor: 'var(--ms-accent)' }} />
                  {sub}
                </label>
              ))}
            </div>
          </div>
        ) : null)}
      </Card>

      {collectorStatus && collectorStatus.total > 0 && (
        <p className="text-sm mb-4" style={{ color: 'var(--ms-text-muted)' }}>
          {collectorStatus.total.toLocaleString()} prospects stored. Searches use stored data unless &quot;Refresh from Google&quot; is checked.
        </p>
      )}

      <div>
        {isFetching ? (
          <Spinner />
        ) : searchError ? (
          <div className="rounded-lg px-4 py-3 text-sm" style={{ backgroundColor: 'var(--ms-badge-alert-bg)', color: 'var(--ms-badge-alert-text)', border: '1px solid var(--ms-badge-alert-text)' }}>
            <p className="font-semibold mb-1">Search failed</p>
            <p>{getApiErrorMessage(searchError)}</p>
          </div>
        ) : searchData?.results?.length ? (
          <ul className="space-y-3">
            {searchData.results.map((p: Prospect) => (
              <li key={p.place_id} className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>{p.name}</div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{p.address}</div>
                    <div className="flex flex-wrap gap-3 mt-1.5 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                      {p.phone && <span>{p.phone}</span>}
                      {p.rating && <span>★ {p.rating} ({p.review_count ?? 0})</span>}
                      {p.website && (
                        <a href={p.website} style={{ color: 'var(--ms-accent)' }} target="_blank" rel="noopener noreferrer">
                          Website ↗
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : searched ? (
          <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>
            No results found. Try a different category, state, or suburbs.
          </p>
        ) : (
          <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>
            Choose a category and state, then click Search.
          </p>
        )}
      </div>
    </div>
  )
}
