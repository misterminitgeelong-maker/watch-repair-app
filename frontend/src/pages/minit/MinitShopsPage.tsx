import { useMemo, useState } from 'react'
import { formatTenantLabel, type ParentAccountSite } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { useParentAccount } from '@/hooks/useParentAccount'
import { MinitShopImport } from '@/components/MinitShopImport'
import { Button, Card, Input, PageHeader, Select } from '@/components/ui'

const OPERATOR_PLANS = new Set([
  'basic_auto_key',
  'basic_shoe_auto_key',
  'basic_watch_auto_key',
  'basic_all_tabs',
  'auto_key',
  'minit_hq',
])

/** TSS region display order (matches import). */
const REGION_ORDER = ['VIC', 'NSW', 'QLD', 'SW', 'NZ', 'SEA'] as const

const UNASSIGNED_REGION = 'Unassigned'

function isRetailShop(planCode: string) {
  return !OPERATOR_PLANS.has(planCode)
}

function regionSortIndex(region: string): number {
  const idx = REGION_ORDER.indexOf(region as (typeof REGION_ORDER)[number])
  return idx >= 0 ? idx : REGION_ORDER.length
}

function compareShopNumber(a: ParentAccountSite, b: ParentAccountSite): number {
  const na = Number.parseInt(a.shop_number ?? '', 10)
  const nb = Number.parseInt(b.shop_number ?? '', 10)
  if (!Number.isNaN(na) && !Number.isNaN(nb) && na !== nb) return na - nb
  return a.tenant_name.localeCompare(b.tenant_name, undefined, { sensitivity: 'base' })
}

function groupRetailByRegion(sites: ParentAccountSite[]): { region: string; shops: ParentAccountSite[] }[] {
  const map = new Map<string, ParentAccountSite[]>()
  for (const site of sites) {
    const region = site.region?.trim() || UNASSIGNED_REGION
    const list = map.get(region) ?? []
    list.push(site)
    map.set(region, list)
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => {
      const diff = regionSortIndex(a) - regionSortIndex(b)
      if (diff !== 0) return diff
      return a.localeCompare(b)
    })
    .map(([region, shops]) => {
      shops.sort(compareShopNumber)
      return { region, shops }
    })
}

function regionAreaSummary(shops: ParentAccountSite[]): string | null {
  const areas = [...new Set(shops.map(s => s.area?.trim()).filter(Boolean) as string[])].sort((a, b) =>
    a.localeCompare(b),
  )
  if (areas.length === 0) return null
  if (areas.length <= 4) return areas.join(', ')
  return `${areas.slice(0, 3).join(', ')} +${areas.length - 3} more`
}

function ShopRow({
  site,
  activeSiteTenantId,
  switchingId,
  onSwitch,
}: {
  site: ParentAccountSite
  activeSiteTenantId: string | null
  switchingId: string
  onSwitch: (tenantId: string) => void
}) {
  const isActive = site.tenant_id === activeSiteTenantId
  return (
    <div
      className="px-3 py-2.5 flex flex-wrap items-center justify-between gap-2 rounded-md"
      style={{
        backgroundColor: isActive ? 'var(--ms-accent-light)' : 'var(--ms-surface)',
        border: isActive ? '1px solid var(--ms-accent)' : '1px solid var(--ms-border)',
      }}
    >
      <div className="min-w-0">
        <p className="font-medium text-sm truncate" style={{ color: 'var(--ms-text)' }}>
          {formatTenantLabel(site.tenant_name, site.shop_number)}
          {isActive && (
            <span className="ml-2 text-xs font-normal" style={{ color: 'var(--ms-accent)' }}>
              Active
            </span>
          )}
        </p>
        <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>
          {site.area?.trim() ? `${site.area.trim()} · ` : ''}
          {site.tenant_slug}
        </p>
      </div>
      {!isActive && (
        <Button
          variant="secondary"
          className="text-xs px-2.5 py-1 shrink-0"
          onClick={() => onSwitch(site.tenant_id)}
          disabled={switchingId === site.tenant_id}
        >
          {switchingId === site.tenant_id ? '…' : 'Switch'}
        </Button>
      )}
    </div>
  )
}

function RegionSkeleton() {
  return (
    <Card className="p-4 animate-pulse">
      <div className="h-5 w-16 rounded mb-3" style={{ backgroundColor: 'var(--ms-border)' }} />
      <div className="space-y-2">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-14 rounded-md" style={{ backgroundColor: 'var(--ms-border)' }} />
        ))}
      </div>
    </Card>
  )
}

export default function MinitShopsPage() {
  const { activeSiteTenantId, switchSite } = useAuth()
  const { data, isLoading, isFetching } = useParentAccount()

  const [switchingId, setSwitchingId] = useState('')
  const [search, setSearch] = useState('')
  const [regionFilter, setRegionFilter] = useState('')

  const retailSites = useMemo(
    () => (data?.sites ?? []).filter(s => isRetailShop(s.plan_code)),
    [data?.sites],
  )
  const operators = useMemo(
    () => (data?.sites ?? []).filter(s => !isRetailShop(s.plan_code)),
    [data?.sites],
  )

  const regionOptions = useMemo(() => {
    const values = new Set<string>()
    for (const site of retailSites) {
      const r = site.region?.trim()
      if (r) values.add(r)
    }
    return Array.from(values).sort((a, b) => regionSortIndex(a) - regionSortIndex(b) || a.localeCompare(b))
  }, [retailSites])

  const searchLower = search.trim().toLowerCase()
  const filteredRetail = useMemo(() => {
    return retailSites.filter(site => {
      if (regionFilter && (site.region?.trim() || UNASSIGNED_REGION) !== regionFilter) return false
      if (!searchLower) return true
      const label = formatTenantLabel(site.tenant_name, site.shop_number).toLowerCase()
      return (
        label.includes(searchLower)
        || site.tenant_slug.toLowerCase().includes(searchLower)
        || (site.shop_number ?? '').includes(searchLower)
        || (site.area ?? '').toLowerCase().includes(searchLower)
        || (site.region ?? '').toLowerCase().includes(searchLower)
      )
    })
  }, [retailSites, searchLower, regionFilter])

  const regionGroups = useMemo(() => groupRetailByRegion(filteredRetail), [filteredRetail])

  async function handleSwitch(tenantId: string) {
    setSwitchingId(tenantId)
    try {
      await switchSite(tenantId)
    } finally {
      setSwitchingId('')
    }
  }

  return (
    <div>
      <PageHeader title="Shops" action={<MinitShopImport />} />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Retail shops grouped by region. Import from Excel or manage accounts under Accounts.
        {isFetching && !isLoading && (
          <span className="ml-2 opacity-70">Refreshing…</span>
        )}
      </p>

      <div
        className="mb-4 flex flex-wrap items-end gap-3"
        style={{ opacity: isLoading && !data ? 0.6 : 1 }}
      >
        <div className="w-full sm:w-40">
          <Select
            label="Region"
            value={regionFilter}
            onChange={e => setRegionFilter(e.target.value)}
            aria-label="Filter by region"
            disabled={isLoading && !data}
          >
            <option value="">All regions</option>
            {regionOptions.map(region => (
              <option key={region} value={region}>{region}</option>
            ))}
            {retailSites.some(s => !s.region?.trim()) && (
              <option value={UNASSIGNED_REGION}>{UNASSIGNED_REGION}</option>
            )}
          </Select>
        </div>
        <div className="w-full sm:flex-1 sm:max-w-md">
          <Input
            type="search"
            label="Search"
            placeholder="Name, shop #, area…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search retail shops"
            disabled={isLoading && !data}
          />
        </div>
        <p className="text-sm pb-2 sm:pb-0" style={{ color: 'var(--ms-text-muted)' }}>
          {isLoading && !data ? 'Loading shops…' : `${filteredRetail.length} of ${retailSites.length} shops`}
        </p>
      </div>

      {isLoading && !data ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {REGION_ORDER.slice(0, 4).map(r => (
            <RegionSkeleton key={r} />
          ))}
        </div>
      ) : retailSites.length === 0 ? (
        <Card className="mb-6 p-6">
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            No retail shops linked yet. Use Import shops or Accounts to add stores.
          </p>
        </Card>
      ) : filteredRetail.length === 0 ? (
        <Card className="mb-6 p-6">
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            No shops match your filters.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {regionGroups.map(({ region, shops }) => {
            const areaLine = regionAreaSummary(shops)
            return (
              <Card
                key={region}
                className="flex flex-col overflow-hidden"
                style={{ maxHeight: 'min(70vh, 520px)' }}
              >
                <div
                  className="px-4 py-3 shrink-0"
                  style={{
                    borderBottom: '1px solid var(--ms-border)',
                    backgroundColor: 'var(--ms-surface-raised, var(--ms-surface))',
                  }}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="font-semibold text-base" style={{ color: 'var(--ms-text)' }}>
                      {region}
                    </h2>
                    <span
                      className="text-xs font-semibold tabular-nums px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: 'var(--ms-accent-light)',
                        color: 'var(--ms-accent)',
                      }}
                    >
                      {shops.length}
                    </span>
                  </div>
                  {areaLine && (
                    <p className="text-xs mt-1 leading-snug" style={{ color: 'var(--ms-text-muted)' }}>
                      {areaLine}
                    </p>
                  )}
                </div>
                <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
                  {shops.map(site => (
                    <ShopRow
                      key={site.tenant_id}
                      site={site}
                      activeSiteTenantId={activeSiteTenantId}
                      switchingId={switchingId}
                      onSwitch={handleSwitch}
                    />
                  ))}
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {operators.length > 0 && (
        <Card className="overflow-hidden">
          <div
            className="px-5 py-3 font-semibold text-sm"
            style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
          >
            Mobile operators ({operators.length})
          </div>
          <div className="p-3 space-y-2">
            {operators.map(site => (
              <ShopRow
                key={site.tenant_id}
                site={site}
                activeSiteTenantId={activeSiteTenantId}
                switchingId={switchingId}
                onSwitch={handleSwitch}
              />
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
