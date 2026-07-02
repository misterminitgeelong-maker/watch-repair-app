import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  API_ORIGIN,
  clearParentMobileLeadWebhookSecret,
  createMobileSuburbRoute,
  deleteMobileSuburbRoute,
  enableParentMobileLeadIngest,
  formatTenantLabel,
  getApiErrorMessage,
  getMobileSuburbRoutesSummary,
  listMobileSuburbRoutes,
  setParentMobileLeadDefaultTenant,
  setParentMobileLeadDispatchSettings,
  setParentMobileLeadEscalationTenant,
  setParentMobileLeadWebhookSecret,
  testMobileLeadRouting,
  type MobileSuburbRoute,
} from '@/lib/api'
import { PARENT_ACCOUNT_QUERY_KEY, useParentAccount } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY, useParentAccountSites } from '@/hooks/useParentAccountSites'
import { PARENT_LEAD_INGEST_QUERY_KEY, useParentLeadIngest } from '@/hooks/useParentLeadIngest'
import { Button, Card, Input, Select } from '@/components/ui'

const ROUTE_LIST_THRESHOLD = 100

function StepBadge({ n, done }: { n: number; done: boolean }) {
  return (
    <div
      className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
      style={{
        backgroundColor: done ? '#1F6D4C' : 'var(--ms-border-strong)',
        color: done ? '#fff' : 'var(--ms-text-muted)',
      }}
    >
      {done ? '✓' : n}
    </div>
  )
}

export interface WebsiteLeadRoutingPanelProps {
  /** When true, show territory summary instead of full route list (HQ default). */
  hqMode?: boolean
  onError?: (message: string) => void
}

export default function WebsiteLeadRoutingPanel({ hqMode = false, onError }: WebsiteLeadRoutingPanelProps) {
  const qc = useQueryClient()
  const { data } = useParentAccount()
  const { data: leadIngest } = useParentLeadIngest()
  const { data: retailPage } = useParentAccountSites({ plan_kind: 'retail', limit: 50 })
  const { data: operatorsPage } = useParentAccountSites({ plan_kind: 'operator', limit: 50 })

  const [webhookSecret, setWebhookSecret] = useState('')
  const [routeState, setRouteState] = useState('NSW')
  const [routeSuburb, setRouteSuburb] = useState('')
  const [routeTargetTenantId, setRouteTargetTenantId] = useState('')
  const [deletingRouteId, setDeletingRouteId] = useState('')
  const [defaultTenantDraft, setDefaultTenantDraft] = useState('')
  const [escalationTenantDraft, setEscalationTenantDraft] = useState('')
  const [offerTimeoutDraft, setOfferTimeoutDraft] = useState('30')
  const [maxOffersDraft, setMaxOffersDraft] = useState('3')
  const [forceHqDraft, setForceHqDraft] = useState(false)
  const [routeSearch, setRouteSearch] = useState('')
  const [debouncedRouteSearch, setDebouncedRouteSearch] = useState('')
  const [testSuburb, setTestSuburb] = useState('')
  const [testState, setTestState] = useState('NSW')

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedRouteSearch(routeSearch), 300)
    return () => window.clearTimeout(handle)
  }, [routeSearch])

  const { data: routeSummary } = useQuery({
    queryKey: ['parent-account-mobile-routes-summary'],
    queryFn: () => getMobileSuburbRoutesSummary().then(r => r.data),
    enabled: hqMode || !!data,
  })

  const useSummaryView = hqMode || (routeSummary?.total_routes ?? 0) > ROUTE_LIST_THRESHOLD

  const { data: suburbRoutes = [] } = useQuery({
    queryKey: ['parent-account-mobile-routes', debouncedRouteSearch, useSummaryView],
    queryFn: () =>
      listMobileSuburbRoutes({
        search: debouncedRouteSearch || undefined,
        limit: useSummaryView ? 50 : 200,
      }).then(r => r.data),
    enabled: !!data && (!useSummaryView || debouncedRouteSearch.length >= 2),
  })

  const { data: routingTest, isFetching: routingTestLoading, refetch: runRoutingTest } = useQuery({
    queryKey: ['parent-routing-test', testState, testSuburb],
    queryFn: () =>
      testMobileLeadRouting({ suburb: testSuburb.trim(), state_code: testState }).then(r => r.data),
    enabled: false,
  })

  useEffect(() => {
    if (data?.mobile_lead_default_tenant_id != null) {
      setDefaultTenantDraft(data.mobile_lead_default_tenant_id)
    } else {
      setDefaultTenantDraft('')
    }
  }, [data?.mobile_lead_default_tenant_id])

  useEffect(() => {
    if (leadIngest?.mobile_lead_escalation_tenant_id != null) {
      setEscalationTenantDraft(leadIngest.mobile_lead_escalation_tenant_id)
    } else {
      setEscalationTenantDraft('')
    }
    if (leadIngest?.mobile_lead_offer_timeout_minutes != null) {
      setOfferTimeoutDraft(String(leadIngest.mobile_lead_offer_timeout_minutes))
    }
    if (leadIngest?.mobile_lead_max_operator_offers != null) {
      setMaxOffersDraft(String(leadIngest.mobile_lead_max_operator_offers))
    }
    setForceHqDraft(leadIngest?.mobile_lead_force_hq_dispatch === true)
  }, [
    leadIngest?.mobile_lead_escalation_tenant_id,
    leadIngest?.mobile_lead_offer_timeout_minutes,
    leadIngest?.mobile_lead_max_operator_offers,
    leadIngest?.mobile_lead_force_hq_dispatch,
  ])

  function invalidateParentQueries() {
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
    qc.invalidateQueries({ queryKey: PARENT_LEAD_INGEST_QUERY_KEY })
    qc.invalidateQueries({ queryKey: ['parent-account-mobile-routes'] })
    qc.invalidateQueries({ queryKey: ['parent-account-mobile-routes-summary'] })
  }

  function reportError(err: unknown, fallback: string) {
    onError?.(getApiErrorMessage(err, fallback))
  }

  const enableIngestMut = useMutation({
    mutationFn: () => enableParentMobileLeadIngest().then(r => r.data),
    onSuccess: () => {
      invalidateParentQueries()
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => reportError(err, 'Could not enable ingest URL.'),
  })

  const setSecretMut = useMutation({
    mutationFn: (secret: string) => setParentMobileLeadWebhookSecret(secret).then(r => r.data),
    onSuccess: () => {
      setWebhookSecret('')
      invalidateParentQueries()
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => reportError(err, 'Could not save security password.'),
  })

  const clearSecretMut = useMutation({
    mutationFn: () => clearParentMobileLeadWebhookSecret().then(r => r.data),
    onSuccess: () => invalidateParentQueries(),
    onError: err => reportError(err, 'Could not clear security password.'),
  })

  const setDefaultTenantMut = useMutation({
    mutationFn: (tenant_id: string | null) => setParentMobileLeadDefaultTenant(tenant_id).then(r => r.data),
    onSuccess: () => invalidateParentQueries(),
    onError: err => reportError(err, 'Could not update default operator.'),
  })

  const setEscalationTenantMut = useMutation({
    mutationFn: (tenant_id: string | null) => setParentMobileLeadEscalationTenant(tenant_id).then(r => r.data),
    onSuccess: () => invalidateParentQueries(),
    onError: err => reportError(err, 'Could not update HQ escalation site.'),
  })

  const setDispatchSettingsMut = useMutation({
    mutationFn: () =>
      setParentMobileLeadDispatchSettings({
        offer_timeout_minutes: Number(offerTimeoutDraft),
        max_operator_offers: Number(maxOffersDraft),
        force_hq_dispatch: forceHqDraft,
      }).then(r => r.data),
    onSuccess: () => invalidateParentQueries(),
    onError: err => reportError(err, 'Could not update dispatch settings.'),
  })

  const createRouteMut = useMutation({
    mutationFn: () =>
      createMobileSuburbRoute({
        state_code: routeState,
        suburb: routeSuburb.trim(),
        target_tenant_id: routeTargetTenantId,
      }).then(r => r.data),
    onSuccess: () => {
      setRouteSuburb('')
      invalidateParentQueries()
    },
    onError: err => reportError(err, 'Could not add suburb route.'),
  })

  const deleteRouteMut = useMutation({
    mutationFn: (id: string) => deleteMobileSuburbRoute(id).then(r => r.data),
    onSuccess: () => invalidateParentQueries(),
    onError: err => reportError(err, 'Could not remove route.'),
  })

  const ingestPublicId = data?.mobile_lead_ingest_public_id ?? null
  const ingestUrl =
    ingestPublicId != null && ingestPublicId !== ''
      ? `${API_ORIGIN || window.location.origin}/v1/public/mobile-key-leads/${ingestPublicId}`
      : ''
  const secretConfigured = data?.mobile_lead_webhook_secret_configured === true
  const savedDefaultTenantId = data?.mobile_lead_default_tenant_id ?? ''
  const defaultTenantDirty = defaultTenantDraft !== savedDefaultTenantId
  const savedEscalationTenantId = leadIngest?.mobile_lead_escalation_tenant_id ?? ''
  const escalationTenantDirty = escalationTenantDraft !== savedEscalationTenantId
  const dispatchSettingsDirty =
    offerTimeoutDraft !== String(leadIngest?.mobile_lead_offer_timeout_minutes ?? 30)
    || maxOffersDraft !== String(leadIngest?.mobile_lead_max_operator_offers ?? 3)
    || forceHqDraft !== (leadIngest?.mobile_lead_force_hq_dispatch === true)

  const retailSites = retailPage?.sites ?? []
  const operatorSites = operatorsPage?.sites ?? []

  function siteLabel(tenantId: string) {
    const s =
      retailSites.find(x => x.tenant_id === tenantId)
      ?? operatorSites.find(x => x.tenant_id === tenantId)
    return s ? formatTenantLabel(s.tenant_name, s.shop_number ?? undefined) : tenantId
  }

  async function copyIngestUrl() {
    if (!ingestUrl) return
    try {
      await navigator.clipboard.writeText(ingestUrl)
    } catch {
      onError?.('Could not copy to clipboard.')
    }
  }

  return (
    <Card className="p-5">
      <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>Website lead routing</h2>
      <p className="text-sm mt-1 mb-5" style={{ color: 'var(--ms-text-mid)' }}>
        Connect minit.com.au job requests to mobile operators. Mapped suburbs go to the nearest operator;
        unmapped suburbs and escalations land in HQ for manual quoting.
      </p>

      <div className="mb-5">
        <div className="flex items-center gap-2 mb-2">
          <StepBadge n={1} done={!!ingestUrl} />
          <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Generate your link</p>
        </div>
        <p className="text-sm mb-3 ml-8" style={{ color: 'var(--ms-text-mid)' }}>
          URL your website posts to when a customer submits a mobile key request.
        </p>
        <div className="ml-8 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => enableIngestMut.mutate()}
            disabled={enableIngestMut.isPending || !!ingestPublicId}
          >
            {ingestPublicId ? 'Link ready' : enableIngestMut.isPending ? 'Generating…' : 'Generate link'}
          </Button>
          {ingestUrl && (
            <Button variant="secondary" onClick={() => void copyIngestUrl()}>
              Copy link
            </Button>
          )}
        </div>
        {ingestUrl && (
          <p className="text-xs mt-2 ml-8 break-all font-mono" style={{ color: 'var(--ms-text-muted)' }}>
            {ingestUrl}
          </p>
        )}
      </div>

      <div className="mb-5">
        <div className="flex items-center gap-2 mb-2">
          <StepBadge n={2} done={secretConfigured} />
          <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Set a security password</p>
        </div>
        <p className="text-sm mb-3 ml-8" style={{ color: 'var(--ms-text-mid)' }}>
          Your website sends this with every request. Also used for inbound email parse ({'`'}?key={'`'}).
          Minimum 16 characters.
        </p>
        <div className="ml-8 grid gap-3 md:grid-cols-2 max-w-lg">
          <Input
            label="Security password"
            type="password"
            autoComplete="new-password"
            value={webhookSecret}
            onChange={e => setWebhookSecret(e.target.value)}
            placeholder="Make it long and random"
          />
          <div className="flex items-end gap-2">
            <Button
              onClick={() => setSecretMut.mutate(webhookSecret.trim())}
              disabled={webhookSecret.trim().length < 16 || setSecretMut.isPending}
            >
              {setSecretMut.isPending ? 'Saving…' : 'Save'}
            </Button>
            {secretConfigured && (
              <Button
                variant="ghost"
                onClick={() => clearSecretMut.mutate()}
                disabled={clearSecretMut.isPending}
              >
                {clearSecretMut.isPending ? 'Clearing…' : 'Clear'}
              </Button>
            )}
          </div>
        </div>
        {secretConfigured && (
          <p className="text-xs mt-2 ml-8 font-medium" style={{ color: '#1F6D4C' }}>
            Password saved — your website can connect.
          </p>
        )}
      </div>

      <div>
        <div className="flex items-center gap-2 mb-2">
          <StepBadge n={3} done={(routeSummary?.total_routes ?? suburbRoutes.length) > 0 || !!savedDefaultTenantId} />
          <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Dispatch & territory</p>
        </div>
        <p className="text-sm mb-3 ml-8" style={{ color: 'var(--ms-text-mid)' }}>
          ~7,500 AU suburbs are mapped within 100km of operator hubs. Outside that range, leads go straight to HQ.
        </p>

        <div className="ml-8 mb-4 flex flex-col sm:flex-row sm:items-end gap-3 max-w-lg">
          <div className="flex-1 min-w-0">
            <Select
              label="HQ escalation (manual quoting inbox)"
              value={escalationTenantDraft}
              onChange={e => setEscalationTenantDraft(e.target.value)}
            >
              <option value="">No HQ escalation</option>
              {[...(retailSites.length ? retailSites : data?.sites ?? []), ...operatorSites].map(s => (
                <option key={s.tenant_id} value={s.tenant_id}>
                  {s.tenant_name} (#{s.tenant_slug})
                </option>
              ))}
            </Select>
          </div>
          <Button
            variant="secondary"
            onClick={() => setEscalationTenantMut.mutate(escalationTenantDraft === '' ? null : escalationTenantDraft)}
            disabled={!escalationTenantDirty || setEscalationTenantMut.isPending}
          >
            {setEscalationTenantMut.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>

        <label className="ml-8 mb-4 flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'var(--ms-text-mid)' }}>
          <input
            type="checkbox"
            checked={forceHqDraft}
            onChange={e => setForceHqDraft(e.target.checked)}
          />
          <span>
            <strong style={{ color: 'var(--ms-text)' }}>HQ testing mode</strong>
            {' — send all website leads to HQ (skip operator SMS cascade)'}
          </span>
        </label>

        <div className="ml-8 mb-4 grid gap-3 md:grid-cols-3 max-w-2xl">
          <Input
            label="Minutes per operator to quote"
            type="number"
            min={5}
            max={240}
            value={offerTimeoutDraft}
            onChange={e => setOfferTimeoutDraft(e.target.value)}
          />
          <Input
            label="Max operators before HQ"
            type="number"
            min={1}
            max={10}
            value={maxOffersDraft}
            onChange={e => setMaxOffersDraft(e.target.value)}
          />
          <div className="flex items-end">
            <Button
              variant="secondary"
              onClick={() => setDispatchSettingsMut.mutate()}
              disabled={!dispatchSettingsDirty || setDispatchSettingsMut.isPending}
            >
              {setDispatchSettingsMut.isPending ? 'Saving…' : 'Save dispatch settings'}
            </Button>
          </div>
        </div>
        <p className="text-xs mb-4 ml-8" style={{ color: 'var(--ms-text-muted)' }}>
          Operators receive SMS when assigned. On timeout, the next nearest operator is notified, then HQ.
        </p>

        {useSummaryView && routeSummary && routeSummary.total_routes > 0 && (
          <div className="ml-8 mb-5">
            <p className="text-sm font-medium mb-2" style={{ color: 'var(--ms-text)' }}>
              Territory map: {routeSummary.total_routes.toLocaleString()} suburbs across {routeSummary.operators.length} operators
            </p>
            <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--ms-border)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                    <th className="text-left font-medium px-3 py-2">Operator</th>
                    <th className="text-right font-medium px-3 py-2">Suburbs</th>
                  </tr>
                </thead>
                <tbody>
                  {routeSummary.operators.map(op => (
                    <tr key={op.target_tenant_id} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                      <td className="px-3 py-2" style={{ color: 'var(--ms-text)' }}>
                        {formatTenantLabel(op.operator_name, op.operator_shop_number ?? undefined)}
                        <span className="text-xs ml-1" style={{ color: 'var(--ms-text-muted)' }}>({op.operator_slug})</span>
                      </td>
                      <td className="text-right px-3 py-2 tabular-nums" style={{ color: 'var(--ms-text)' }}>
                        {op.route_count.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="ml-8 mb-4 p-4 rounded-lg" style={{ backgroundColor: 'var(--ms-bg, rgba(0,0,0,0.03))', border: '1px solid var(--ms-border)' }}>
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--ms-text)' }}>Test routing</p>
          <div className="flex flex-wrap gap-3 items-end">
            <Select label="State" value={testState} onChange={e => setTestState(e.target.value)} className="w-28">
              {['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'].map(st => (
                <option key={st} value={st}>{st}</option>
              ))}
            </Select>
            <Input
              label="Suburb"
              value={testSuburb}
              onChange={e => setTestSuburb(e.target.value)}
              placeholder="e.g. Parramatta"
              className="w-48"
            />
            <Button
              variant="secondary"
              onClick={() => void runRoutingTest()}
              disabled={!testSuburb.trim() || routingTestLoading}
            >
              {routingTestLoading ? 'Testing…' : 'Test'}
            </Button>
          </div>
          {routingTest && (
            <p className="text-sm mt-3" style={{ color: 'var(--ms-text)' }}>
              <strong>{routingTest.suburb}, {routingTest.state_code}</strong>
              {' → '}
              {routingTest.operator_name
                ? `${formatTenantLabel(routingTest.operator_name, routingTest.operator_shop_number ?? undefined)} (${routingTest.routing_rule})`
                : routingTest.message ?? routingTest.routing_rule}
            </p>
          )}
        </div>

        <p className="text-sm font-medium ml-8 mb-2" style={{ color: 'var(--ms-text)' }}>Manual suburb override</p>
        <div className="ml-8 grid gap-3 md:grid-cols-4 max-w-2xl">
          <Select label="State" value={routeState} onChange={e => setRouteState(e.target.value)}>
            {['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'].map(st => (
              <option key={st} value={st}>{st}</option>
            ))}
          </Select>
          <Input
            label="Suburb"
            value={routeSuburb}
            onChange={e => setRouteSuburb(e.target.value)}
            placeholder="e.g. Parramatta"
          />
          <Select label="Mobile operator" value={routeTargetTenantId} onChange={e => setRouteTargetTenantId(e.target.value)}>
            <option value="">Select operator</option>
            {operatorSites.map(s => (
              <option key={s.tenant_id} value={s.tenant_id}>{s.tenant_name}</option>
            ))}
          </Select>
          <div className="flex items-end">
            <Button
              onClick={() => createRouteMut.mutate()}
              disabled={!routeSuburb.trim() || !routeTargetTenantId || createRouteMut.isPending}
            >
              {createRouteMut.isPending ? 'Adding…' : 'Add'}
            </Button>
          </div>
        </div>

        {useSummaryView ? (
          <div className="ml-8 mt-4">
            <Input
              label="Search suburb overrides"
              value={routeSearch}
              onChange={e => setRouteSearch(e.target.value)}
              placeholder="Type at least 2 characters to search…"
              className="max-w-md"
            />
            {debouncedRouteSearch.length >= 2 && (
              <RouteList
                routes={suburbRoutes}
                siteLabel={siteLabel}
                deletingRouteId={deletingRouteId}
                deletePending={deleteRouteMut.isPending}
                onDelete={id => {
                  setDeletingRouteId(id)
                  void deleteRouteMut.mutateAsync(id).finally(() => setDeletingRouteId(''))
                }}
              />
            )}
          </div>
        ) : (
          <RouteList
            routes={suburbRoutes}
            siteLabel={siteLabel}
            deletingRouteId={deletingRouteId}
            deletePending={deleteRouteMut.isPending}
            onDelete={id => {
              setDeletingRouteId(id)
              void deleteRouteMut.mutateAsync(id).finally(() => setDeletingRouteId(''))
            }}
            className="ml-8"
          />
        )}

        {!useSummaryView && (
          <div className="ml-8 mt-4 flex flex-col sm:flex-row sm:items-end gap-3 max-w-lg">
            <div className="flex-1 min-w-0">
              <Select
                label="Legacy fallback operator (optional)"
                value={defaultTenantDraft}
                onChange={e => setDefaultTenantDraft(e.target.value)}
              >
                <option value="">No fallback</option>
                {operatorSites.map(s => (
                  <option key={s.tenant_id} value={s.tenant_id}>
                    {s.tenant_name} (#{s.tenant_slug})
                  </option>
                ))}
              </Select>
            </div>
            <Button
              variant="secondary"
              onClick={() => setDefaultTenantMut.mutate(defaultTenantDraft === '' ? null : defaultTenantDraft)}
              disabled={!defaultTenantDirty || setDefaultTenantMut.isPending}
            >
              {setDefaultTenantMut.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}

function RouteList({
  routes,
  siteLabel,
  deletingRouteId,
  deletePending,
  onDelete,
  className = 'mt-3 ml-8',
}: {
  routes: MobileSuburbRoute[]
  siteLabel: (id: string) => string
  deletingRouteId: string
  deletePending: boolean
  onDelete: (id: string) => void
  className?: string
}) {
  if (routes.length === 0) {
    return (
      <p className={`text-sm ${className}`} style={{ color: 'var(--ms-text-muted)' }}>
        No matching suburb routes.
      </p>
    )
  }
  return (
    <ul className={`${className} divide-y rounded-lg border`} style={{ borderColor: 'var(--ms-border)' }}>
      {routes.map(r => (
        <li key={r.id} className="px-3 py-2.5 flex justify-between gap-3 text-sm">
          <span style={{ color: 'var(--ms-text)' }}>
            <span className="font-medium">{r.suburb_normalized}</span>
            <span style={{ color: 'var(--ms-text-muted)' }}>, {r.state_code}</span>
            <span style={{ color: 'var(--ms-text-muted)' }}> → {siteLabel(r.target_tenant_id)}</span>
          </span>
          <Button
            variant="ghost"
            className="px-2 py-1 text-xs shrink-0"
            onClick={() => onDelete(r.id)}
            disabled={deletePending && deletingRouteId === r.id}
          >
            Remove
          </Button>
        </li>
      ))}
    </ul>
  )
}
