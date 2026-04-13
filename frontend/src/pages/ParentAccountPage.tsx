import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  clearParentMobileLeadWebhookSecret,
  createMobileSuburbRoute,
  createTenantFromParentAccount,
  deleteMobileSuburbRoute,
  enableParentMobileLeadIngest,
  getApiErrorMessage,
  getMyParentAccount,
  linkTenantToParentAccount,
  listMobileSuburbRoutes,
  listParentAccountActivity,
  setParentMobileLeadDefaultTenant,
  setParentMobileLeadWebhookSecret,
  unlinkTenantFromParentAccount,
  type PlanCode,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'

export default function ParentAccountPage() {
  const navigate = useNavigate()
  const { activeSiteTenantId, switchSite, refreshSession } = useAuth()
  const qc = useQueryClient()
  const [tenantSlug, setTenantSlug] = useState('')
  const [ownerEmail, setOwnerEmail] = useState('')
  const [newTenantName, setNewTenantName] = useState('')
  const [newTenantSlug, setNewTenantSlug] = useState('')
  const [newTenantPlanCode, setNewTenantPlanCode] = useState<PlanCode>('basic_watch')
  const [error, setError] = useState('')
  const [switchingTenantId, setSwitchingTenantId] = useState('')
  const [removingTenantId, setRemovingTenantId] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [routeState, setRouteState] = useState('NSW')
  const [routeSuburb, setRouteSuburb] = useState('')
  const [routeTargetTenantId, setRouteTargetTenantId] = useState('')
  const [deletingRouteId, setDeletingRouteId] = useState('')
  const [defaultTenantDraft, setDefaultTenantDraft] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['parent-account-me'],
    queryFn: () => getMyParentAccount().then(r => r.data),
  })

  const { data: activity = [] } = useQuery({
    queryKey: ['parent-account-activity'],
    queryFn: () => listParentAccountActivity(30).then(r => r.data),
  })

  const { data: suburbRoutes = [] } = useQuery({
    queryKey: ['parent-account-mobile-routes'],
    queryFn: () => listMobileSuburbRoutes().then(r => r.data),
    enabled: !!data,
  })

  useEffect(() => {
    if (data?.mobile_lead_default_tenant_id != null) {
      setDefaultTenantDraft(data.mobile_lead_default_tenant_id)
    } else {
      setDefaultTenantDraft('')
    }
  }, [data?.mobile_lead_default_tenant_id])

  const enableIngestMut = useMutation({
    mutationFn: () => enableParentMobileLeadIngest().then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not enable ingest URL.')),
  })

  const setSecretMut = useMutation({
    mutationFn: (secret: string) => setParentMobileLeadWebhookSecret(secret).then(r => r.data),
    onSuccess: () => {
      setError('')
      setWebhookSecret('')
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not save webhook secret.')),
  })

  const clearSecretMut = useMutation({
    mutationFn: () => clearParentMobileLeadWebhookSecret().then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not clear webhook secret.')),
  })

  const setDefaultTenantMut = useMutation({
    mutationFn: (tenant_id: string | null) => setParentMobileLeadDefaultTenant(tenant_id).then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not update default site.')),
  })

  const createRouteMut = useMutation({
    mutationFn: () =>
      createMobileSuburbRoute({
        state_code: routeState,
        suburb: routeSuburb.trim(),
        target_tenant_id: routeTargetTenantId,
      }).then(r => r.data),
    onSuccess: () => {
      setError('')
      setRouteSuburb('')
      qc.invalidateQueries({ queryKey: ['parent-account-mobile-routes'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not add suburb route.')),
  })

  const deleteRouteMut = useMutation({
    mutationFn: (id: string) => deleteMobileSuburbRoute(id).then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['parent-account-mobile-routes'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not remove route.')),
  })

  const linkMut = useMutation({
    mutationFn: () => linkTenantToParentAccount({ tenant_slug: tenantSlug.trim(), owner_email: ownerEmail.trim().toLowerCase() }),
    onSuccess: () => {
      setError('')
      setTenantSlug('')
      setOwnerEmail('')
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not link tenant to parent account.')),
  })

  const createTenantMut = useMutation({
    mutationFn: () => createTenantFromParentAccount({ tenant_name: newTenantName.trim(), tenant_slug: newTenantSlug.trim().toLowerCase(), plan_code: newTenantPlanCode }),
    onSuccess: () => {
      setError('')
      setNewTenantName('')
      setNewTenantSlug('')
      setNewTenantPlanCode('basic_watch')
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not create and link new site.')),
  })

  const unlinkMut = useMutation({
    mutationFn: (tenantId: string) => unlinkTenantFromParentAccount(tenantId),
    onSuccess: () => {
      setError('')
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not unlink tenant from parent account.')),
  })

  async function handleSwitchSite(tenantId: string) {
    if (!tenantId || tenantId === activeSiteTenantId) return
    setSwitchingTenantId(tenantId)
    setError('')
    try {
      await switchSite(tenantId)
      navigate('/dashboard')
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not switch to selected site.'))
    } finally {
      setSwitchingTenantId('')
    }
  }

  async function handleUnlinkSite(tenantId: string) {
    if (!tenantId || tenantId === activeSiteTenantId) return
    const confirmed = window.confirm('Unlink this site from your parent account? This can be re-linked later.')
    if (!confirmed) return
    setRemovingTenantId(tenantId)
    setError('')
    try {
      await unlinkMut.mutateAsync(tenantId)
    } finally {
      setRemovingTenantId('')
    }
  }

  if (isLoading) return <Spinner />

  const ingestPublicId = data?.mobile_lead_ingest_public_id ?? null
  const ingestUrl =
    ingestPublicId != null && ingestPublicId !== ''
      ? `${window.location.origin}/v1/public/mobile-key-leads/${ingestPublicId}`
      : ''
  const secretConfigured = data?.mobile_lead_webhook_secret_configured === true
  const savedDefaultTenantId = data?.mobile_lead_default_tenant_id ?? ''
  const defaultTenantDirty = defaultTenantDraft !== savedDefaultTenantId

  function siteLabel(tenantId: string) {
    const s = data?.sites.find(x => x.tenant_id === tenantId)
    return s ? `${s.tenant_name} (#${s.tenant_slug})` : tenantId
  }

  async function copyIngestUrl() {
    if (!ingestUrl) return
    try {
      await navigator.clipboard.writeText(ingestUrl)
    } catch {
      setError('Could not copy to clipboard.')
    }
  }

  return (
    <div>
      <PageHeader title='Parent Account' />

      <Card className='mb-5 p-4 sm:p-5'>
        <p className='text-xs font-semibold tracking-wide uppercase' style={{ color: 'var(--cafe-text-muted)' }}>
          Link existing site
        </p>
        <p className='text-sm mt-2' style={{ color: 'var(--cafe-text-mid)' }}>
          Add another site by supplying its shop number and owner email.
        </p>
        <div className='mt-3 grid gap-3 md:grid-cols-2'>
          <Input label='Shop Number' value={tenantSlug} onChange={e => setTenantSlug(e.target.value)} placeholder='site-b-1234' />
          <Input label='Owner email' type='email' value={ownerEmail} onChange={e => setOwnerEmail(e.target.value)} placeholder='owner@siteb.test' />
        </div>
        {error && <p className='mt-3 text-sm' style={{ color: '#C96A5A' }}>{error}</p>}
        <div className='mt-3 flex justify-end'>
          <Button
            onClick={() => linkMut.mutate()}
            disabled={!tenantSlug.trim() || !ownerEmail.trim() || linkMut.isPending}
          >
            {linkMut.isPending ? 'Linking…' : 'Link Site'}
          </Button>
        </div>
      </Card>

      <Card className='mb-5 p-4 sm:p-5'>
        <p className='text-xs font-semibold tracking-wide uppercase' style={{ color: 'var(--cafe-text-muted)' }}>
          Create new site
        </p>
        <p className='text-sm mt-2' style={{ color: 'var(--cafe-text-mid)' }}>
          Create a new tenant and automatically attach it to this parent account.
        </p>
        <div className='mt-3 grid gap-3 md:grid-cols-3'>
          <Input label='Site name' value={newTenantName} onChange={e => setNewTenantName(e.target.value)} placeholder='Mainspring North' />
          <Input label='Shop Number' value={newTenantSlug} onChange={e => setNewTenantSlug(e.target.value)} placeholder='mainspring-north' />
          <Select label='Plan' value={newTenantPlanCode} onChange={e => setNewTenantPlanCode(e.target.value as PlanCode)}>
            <option value='basic_watch'>Basic - Watch ($25/mo)</option>
            <option value='basic_shoe'>Basic - Shoe ($25/mo)</option>
            <option value='basic_auto_key'>Basic - Mobile Services ($25/mo)</option>
            <option value='basic_watch_shoe'>Basic +1 Tab (Watch + Shoe) ($35/mo)</option>
            <option value='basic_watch_auto_key'>Basic +1 Tab (Watch + Mobile Services) ($35/mo)</option>
            <option value='basic_shoe_auto_key'>Basic +1 Tab (Shoe + Mobile Services) ($35/mo)</option>
            <option value='basic_all_tabs'>Basic +2 Tabs (All Service Tabs) ($45/mo)</option>
            <option value='pro'>Pro ($50/mo)</option>
          </Select>
        </div>
        <div className='mt-3 flex justify-end'>
          <Button
            onClick={() => createTenantMut.mutate()}
            disabled={!newTenantName.trim() || !newTenantSlug.trim() || createTenantMut.isPending}
          >
            {createTenantMut.isPending ? 'Creating…' : 'Create and Link Site'}
          </Button>
        </div>
      </Card>

      <Card className='mb-5'>
        <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>
            Linked Sites {data ? `(${data.sites.length})` : ''}
          </h2>
          {data && (
            <p className='text-xs mt-1' style={{ color: 'var(--cafe-text-muted)' }}>
              Parent: {data.parent_account_name} · {data.owner_email}
            </p>
          )}
        </div>
        {!data || data.sites.length === 0 ? (
          <EmptyState message='No linked sites yet.' />
        ) : (
          <div>
            {data.sites.map(site => (
              <div key={site.tenant_id} className='px-5 py-3 text-sm flex items-start justify-between gap-3' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                <div>
                  <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{site.tenant_name}</p>
                  <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>Shop Number: {site.tenant_slug}</p>
                </div>
                <div className='text-right'>
                  <p className='text-xs font-semibold' style={{ color: 'var(--cafe-text)' }}>{site.owner_full_name}</p>
                  <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>{site.owner_email}</p>
                  <div className='mt-2'>
                    {site.tenant_id === activeSiteTenantId ? (
                      <span className='text-xs font-semibold' style={{ color: 'var(--cafe-text-muted)' }}>Active site</span>
                    ) : (
                      <div className='flex justify-end gap-2'>
                        <Button
                          variant='secondary'
                          className='px-3 py-1.5 text-xs'
                          onClick={() => handleSwitchSite(site.tenant_id)}
                          disabled={switchingTenantId === site.tenant_id || removingTenantId === site.tenant_id}
                        >
                          {switchingTenantId === site.tenant_id ? 'Switching…' : 'Switch to site'}
                        </Button>
                        <Button
                          variant='ghost'
                          className='px-3 py-1.5 text-xs'
                          onClick={() => handleUnlinkSite(site.tenant_id)}
                          disabled={switchingTenantId === site.tenant_id || removingTenantId === site.tenant_id}
                        >
                          {removingTenantId === site.tenant_id ? 'Removing…' : 'Remove'}
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className='mb-5 p-4 sm:p-5'>
        <p className='text-xs font-semibold tracking-wide uppercase' style={{ color: 'var(--cafe-text-muted)' }}>
          Website mobile key lead feed
        </p>
        <p className='text-sm mt-2' style={{ color: 'var(--cafe-text-mid)' }}>
          Point your public website at this endpoint after a customer enters their suburb. The job is created on the mapped site and appears in that site&apos;s Inbox for quoting. Suburbs are matched after normalising (trim, lower case, single spaces).
        </p>
        <div className='mt-3 flex flex-wrap gap-2'>
          <Button
            variant='secondary'
            onClick={() => enableIngestMut.mutate()}
            disabled={enableIngestMut.isPending || !!ingestPublicId}
          >
            {ingestPublicId ? 'Ingest URL ready' : enableIngestMut.isPending ? 'Enabling…' : 'Enable ingest URL'}
          </Button>
          {ingestUrl && (
            <Button variant='secondary' type='button' onClick={() => void copyIngestUrl()}>
              Copy POST URL
            </Button>
          )}
        </div>
        {ingestUrl && (
          <p className='text-xs mt-2 break-all font-mono' style={{ color: 'var(--cafe-text-muted)' }}>
            {ingestUrl}
          </p>
        )}
        <p className='text-xs mt-3' style={{ color: 'var(--cafe-text-muted)' }}>
          Send header <code className='text-[11px]'>X-Mobile-Lead-Secret</code> with the secret below. JSON body fields include{' '}
          <code className='text-[11px]'>suburb</code>, <code className='text-[11px]'>state_code</code>, <code className='text-[11px]'>customer_name</code>, and optional contact and vehicle fields (see API docs / backend schema).
        </p>
        <div className='mt-4 grid gap-3 md:grid-cols-2'>
          <Input
            label='Webhook secret (min 16 characters)'
            type='password'
            autoComplete='new-password'
            value={webhookSecret}
            onChange={e => setWebhookSecret(e.target.value)}
            placeholder='Generate a long random string'
          />
          <div className='flex items-end gap-2 flex-wrap'>
            <Button
              onClick={() => setSecretMut.mutate(webhookSecret.trim())}
              disabled={webhookSecret.trim().length < 16 || setSecretMut.isPending}
            >
              {setSecretMut.isPending ? 'Saving…' : 'Save secret'}
            </Button>
            <Button
              variant='ghost'
              onClick={() => clearSecretMut.mutate()}
              disabled={!secretConfigured || clearSecretMut.isPending}
            >
              {clearSecretMut.isPending ? 'Clearing…' : 'Clear secret'}
            </Button>
          </div>
        </div>
        {secretConfigured && (
          <p className='text-xs mt-2' style={{ color: '#1F6D4C' }}>
            Secret is configured (value is not shown again).
          </p>
        )}
        <div className='mt-5 flex flex-col sm:flex-row sm:items-end gap-3'>
          <div className='flex-1 min-w-0'>
            <Select
              label='Default site (unmapped suburbs)'
              value={defaultTenantDraft}
              onChange={e => setDefaultTenantDraft(e.target.value)}
            >
              <option value=''>None — require a route match</option>
              {(data?.sites ?? []).map(s => (
                <option key={s.tenant_id} value={s.tenant_id}>
                  {s.tenant_name} (#{s.tenant_slug})
                </option>
              ))}
            </Select>
          </div>
          <div className='flex gap-2 shrink-0'>
            <Button
              variant='secondary'
              onClick={() =>
                setDefaultTenantMut.mutate(defaultTenantDraft === '' ? null : defaultTenantDraft)
              }
              disabled={!defaultTenantDirty || setDefaultTenantMut.isPending}
            >
              {setDefaultTenantMut.isPending ? 'Saving…' : 'Save default'}
            </Button>
          </div>
        </div>
        <p className='text-xs mt-4 font-semibold' style={{ color: 'var(--cafe-text-muted)' }}>
          Suburb → site routes
        </p>
        <div className='mt-2 grid gap-3 md:grid-cols-4'>
          <Select label='State' value={routeState} onChange={e => setRouteState(e.target.value)}>
            {['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'].map(st => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </Select>
          <Input label='Suburb (as customers type it)' value={routeSuburb} onChange={e => setRouteSuburb(e.target.value)} placeholder='e.g. Parramatta' />
          <Select label='Site' value={routeTargetTenantId} onChange={e => setRouteTargetTenantId(e.target.value)}>
            <option value=''>Select site</option>
            {(data?.sites ?? []).map(s => (
              <option key={s.tenant_id} value={s.tenant_id}>
                {s.tenant_name}
              </option>
            ))}
          </Select>
          <div className='flex items-end'>
            <Button
              onClick={() => createRouteMut.mutate()}
              disabled={!routeSuburb.trim() || !routeTargetTenantId || createRouteMut.isPending}
            >
              {createRouteMut.isPending ? 'Adding…' : 'Add route'}
            </Button>
          </div>
        </div>
        {suburbRoutes.length === 0 ? (
          <p className='text-sm mt-3' style={{ color: 'var(--cafe-text-muted)' }}>
            No routes yet. Add at least one route or set a default site.
          </p>
        ) : (
          <ul className='mt-3 divide-y' style={{ borderColor: 'var(--cafe-border)' }}>
            {suburbRoutes.map(r => (
              <li key={r.id} className='py-2 flex justify-between gap-3 text-sm'>
                <span style={{ color: 'var(--cafe-text)' }}>
                  <span className='font-medium'>{r.suburb_normalized}</span>
                  <span style={{ color: 'var(--cafe-text-muted)' }}> · {r.state_code} → {siteLabel(r.target_tenant_id)}</span>
                </span>
                <Button
                  variant='ghost'
                  className='px-2 py-1 text-xs shrink-0'
                  onClick={() => {
                    setDeletingRouteId(r.id)
                    void deleteRouteMut.mutateAsync(r.id).finally(() => setDeletingRouteId(''))
                  }}
                  disabled={deleteRouteMut.isPending && deletingRouteId === r.id}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>
            Activity Log
          </h2>
          <p className='text-xs mt-1' style={{ color: 'var(--cafe-text-muted)' }}>
            Recent parent-account actions across sites.
          </p>
        </div>
        {activity.length === 0 ? (
          <EmptyState message='No activity recorded yet.' />
        ) : (
          <div>
            {activity.map(event => (
              <div key={event.id} className='px-5 py-3 text-sm flex items-start justify-between gap-3' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                <div>
                  <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{event.event_summary}</p>
                  <p className='text-xs capitalize' style={{ color: 'var(--cafe-text-muted)' }}>
                    {event.event_type.replace(/_/g, ' ')}{event.actor_email ? ` · ${event.actor_email}` : ''}
                  </p>
                </div>
                <p className='text-xs whitespace-nowrap' style={{ color: 'var(--cafe-text-muted)' }}>
                  {new Date(event.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
