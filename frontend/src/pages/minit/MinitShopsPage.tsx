import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  formatTenantLabel,
  getMyParentAccount,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'

const OPERATOR_PLANS = new Set([
  'basic_auto_key',
  'basic_shoe_auto_key',
  'basic_watch_auto_key',
  'basic_all_tabs',
  'auto_key',
  'minit_hq',
])

function isRetailShop(planCode: string) {
  return !OPERATOR_PLANS.has(planCode)
}

function formatAreaRegion(area?: string | null, region?: string | null) {
  const parts = [area?.trim(), region?.trim()].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : null
}

export default function MinitShopsPage() {
  const { activeSiteTenantId, switchSite } = useAuth()

  const { data, isLoading } = useQuery({
    queryKey: ['parent-account-me'],
    queryFn: () => getMyParentAccount().then(r => r.data),
  })

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
      if (site.region?.trim()) values.add(site.region.trim())
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b))
  }, [retailSites])

  const searchLower = search.trim().toLowerCase()
  const filteredRetail = useMemo(() => {
    return retailSites.filter(site => {
      if (regionFilter && (site.region ?? '') !== regionFilter) return false
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

  if (isLoading) return <Spinner />

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
      <PageHeader title="Shops" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        View and switch between retail shops and mobile operators on the network. Add or remove shops in Accounts.
      </p>

      <Card className="mb-6 overflow-hidden">
        <div
          className="px-5 py-3 flex flex-wrap items-center justify-between gap-3"
          style={{ borderBottom: '1px solid var(--ms-border)' }}
        >
          <span className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
            Retail shops ({retailSites.length})
          </span>
          {retailSites.length > 0 && (
            <div className="flex flex-wrap items-end gap-3 w-full sm:w-auto sm:justify-end">
              {regionOptions.length > 0 && (
                <div className="w-full sm:w-40">
                  <Select
                    label="Region"
                    value={regionFilter}
                    onChange={e => setRegionFilter(e.target.value)}
                    aria-label="Filter by region"
                  >
                    <option value="">All regions</option>
                    {regionOptions.map(region => (
                      <option key={region} value={region}>{region}</option>
                    ))}
                  </Select>
                </div>
              )}
              <div className="w-full sm:w-64">
                <Input
                  type="search"
                  placeholder="Search name, shop #, area…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  aria-label="Search retail shops"
                />
              </div>
            </div>
          )}
        </div>
        {retailSites.length === 0 ? (
          <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No retail shops linked yet.</p>
        ) : filteredRetail.length === 0 ? (
          <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            No shops match your filters.
          </p>
        ) : (
          filteredRetail.map(site => {
            const areaRegion = formatAreaRegion(site.area, site.region)
            return (
              <div
                key={site.tenant_id}
                className="px-5 py-4 flex flex-wrap items-center justify-between gap-3"
                style={{ borderBottom: '1px solid var(--ms-border)' }}
              >
                <div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                    {formatTenantLabel(site.tenant_name, site.shop_number)}
                    {site.tenant_id === activeSiteTenantId && (
                      <span className="ml-2 text-xs font-normal" style={{ color: 'var(--ms-accent)' }}>Active</span>
                    )}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                    {areaRegion ? `${areaRegion} · ` : ''}login {site.tenant_slug} · {site.plan_code}
                  </p>
                </div>
                {site.tenant_id !== activeSiteTenantId && (
                  <Button
                    variant="secondary"
                    className="text-xs px-3 py-1.5"
                    onClick={() => handleSwitch(site.tenant_id)}
                    disabled={switchingId === site.tenant_id}
                  >
                    {switchingId === site.tenant_id ? 'Switching…' : 'Switch site'}
                  </Button>
                )}
              </div>
            )
          })
        )}
      </Card>

      {operators.length > 0 && (
        <Card className="overflow-hidden">
          <div className="px-5 py-3 font-semibold text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
            Mobile operators ({operators.length})
          </div>
          {operators.map(site => {
            const areaRegion = formatAreaRegion(site.area, site.region)
            return (
              <div
                key={site.tenant_id}
                className="px-5 py-4 flex flex-wrap items-center justify-between gap-3"
                style={{ borderBottom: '1px solid var(--ms-border)' }}
              >
                <div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                    {formatTenantLabel(site.tenant_name, site.shop_number)}
                    {site.tenant_id === activeSiteTenantId && (
                      <span className="ml-2 text-xs font-normal" style={{ color: 'var(--ms-accent)' }}>Active</span>
                    )}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                    {areaRegion ? `${areaRegion} · ` : ''}{site.tenant_slug} · {site.plan_code}
                  </p>
                </div>
                {site.tenant_id !== activeSiteTenantId && (
                  <Button
                    variant="secondary"
                    className="text-xs px-3 py-1.5"
                    onClick={() => handleSwitch(site.tenant_id)}
                    disabled={switchingId === site.tenant_id}
                  >
                    {switchingId === site.tenant_id ? 'Switching…' : 'Switch site'}
                  </Button>
                )}
              </div>
            )
          })}
        </Card>
      )}
    </div>
  )
}
