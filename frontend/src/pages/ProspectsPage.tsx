import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProspectCollectorStatus, listProspectCategories, listProspectRegions, searchProspects, type Prospect, type ProspectSearchResponse } from '@/lib/api'
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

  const suburbsForState: string[] = useMemo(() => {
    const raw = state && regions?.suburbs?.[state]
    return Array.isArray(raw) ? raw : []
  }, [state, regions?.suburbs])

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

  const { data: searchData, refetch, isFetching } = useQuery<ProspectSearchResponse>({
    queryKey: ['prospects', searchParams?.category, searchParams?.state, searchParams?.suburbs?.join(','), searchParams?.live],
    queryFn: () =>
      searchProspects(
        searchParams!.category,
        searchParams!.state,
        searchParams!.suburbs,
        searchParams!.live
      ).then(r => r.data),
    enabled: !!searchParams,
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
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
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
              onClick={() => refetch()}
              disabled={!category || !state || isFetching}
            >
              {isFetching ? 'Searching…' : 'Search'}
            </Button>
            <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'var(--cafe-text-mid)' }}>
              <input
                type="checkbox"
                checked={useLiveApi}
                onChange={e => setUseLiveApi(e.target.checked)}
                className="rounded border"
                style={{ accentColor: 'var(--cafe-amber)' }}
              />
              Refresh from Google (live API)
            </label>
          </div>
        </div>

        {state && suburbsForState.length > 0 && (
          <div className="mt-5 pt-5" style={{ borderTop: '1px solid var(--cafe-border)' }}>
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                Suburbs (optional) — narrow your search
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={selectAllSuburbs}
                  className="text-xs font-medium px-2 py-1 rounded hover:bg-black/5"
                  style={{ color: 'var(--cafe-amber)' }}
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={clearSuburbs}
                  className="text-xs font-medium px-2 py-1 rounded hover:bg-black/5"
                  style={{ color: 'var(--cafe-text-muted)' }}
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-2 max-h-[160px] overflow-y-auto py-1 pr-2" style={{ color: 'var(--cafe-text)' }}>
              {suburbsForState.map(sub => (
                <label key={sub} className="flex items-center gap-2 cursor-pointer text-sm">
                  <input
                    type="checkbox"
                    checked={suburbs.has(sub)}
                    onChange={() => toggleSuburb(sub)}
                    className="rounded border"
                    style={{ accentColor: 'var(--cafe-amber)' }}
                  />
                  {sub}
                </label>
              ))}
            </div>
          </div>
        )}
      </Card>

      {collectorStatus && collectorStatus.total > 0 && (
        <p className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
          {collectorStatus.total.toLocaleString()} prospects stored. Searches use stored data unless &quot;Refresh from Google&quot; is checked.
        </p>
      )}

      <div>
        {isFetching ? (
          <Spinner />
        ) : searchData?.results?.length ? (
          <ul className="space-y-3">
            {searchData.results.map((p: Prospect) => (
              <li key={p.place_id} className="p-3 rounded-lg border" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
                <div className="font-semibold">{p.name}</div>
                <div className="text-sm">{p.address}</div>
                <div className="text-sm mt-1">
                  {p.phone}
                  {p.website && (
                    <a href={p.website} className="ml-2" style={{ color: 'var(--cafe-amber)' }} target="_blank" rel="noopener noreferrer">
                      Website
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : searchParams ? (
          <p className="text-sm py-4" style={{ color: 'var(--cafe-text-muted)' }}>
            No results. Try a different state or suburbs.
          </p>
        ) : (
          <p className="text-sm py-4" style={{ color: 'var(--cafe-text-muted)' }}>
            Choose a category and state, then click Search.
          </p>
        )}
      </div>
    </div>
  )
}
