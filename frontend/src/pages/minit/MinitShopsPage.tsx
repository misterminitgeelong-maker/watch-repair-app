import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  formatTenantLabel,
  getMyParentAccount,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Card, PageHeader, Spinner } from '@/components/ui'

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

export default function MinitShopsPage() {
  const { activeSiteTenantId, switchSite } = useAuth()

  const { data, isLoading } = useQuery({
    queryKey: ['parent-account-me'],
    queryFn: () => getMyParentAccount().then(r => r.data),
  })

  const [switchingId, setSwitchingId] = useState('')

  if (isLoading) return <Spinner />

  const retailSites = (data?.sites ?? []).filter(s => isRetailShop(s.plan_code))
  const operators = (data?.sites ?? []).filter(s => !isRetailShop(s.plan_code))

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
        <div className="px-5 py-3 font-semibold text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
          Retail shops ({retailSites.length})
        </div>
        {retailSites.length === 0 ? (
          <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No retail shops linked yet.</p>
        ) : (
          retailSites.map(site => (
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
                  login {site.tenant_slug} · {site.plan_code}
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
          ))
        )}
      </Card>

      {operators.length > 0 && (
        <Card className="overflow-hidden">
          <div className="px-5 py-3 font-semibold text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
            Mobile operators ({operators.length})
          </div>
          {operators.map(site => (
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
                  {site.tenant_slug} · {site.plan_code}
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
          ))}
        </Card>
      )}
    </div>
  )
}
