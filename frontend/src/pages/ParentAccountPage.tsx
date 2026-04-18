import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  API_ORIGIN,
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
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

export default function ParentAccountPage() {
  const navigate = useNavigate()
  const { activeSiteTenantId, switchSite, refreshSession } = useAuth()
  const qc = useQueryClient()

  // Add shop modal
  const [showAddModal, setShowAddModal] = useState(false)
  const [addMode, setAddMode] = useState<'link' | 'create'>('create')

  // Link existing
  const [tenantSlug, setTenantSlug] = useState('')
  const [ownerEmail, setOwnerEmail] = useState('')

  // Create new
  const [newTenantName, setNewTenantName] = useState('')
  const [newTenantSlug, setNewTenantSlug] = useState('')
  const [newTenantPlanCode, setNewTenantPlanCode] = useState<PlanCode>('basic_watch')

  const [error, setError] = useState('')
  const [switchingTenantId, setSwitchingTenantId] = useState('')
  const [removingTenantId, setRemovingTenantId] = useState('')

  // Lead routing
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
    onError: err => setError(getApiErrorMessage(err, 'Could not save security password.')),
  })

  const clearSecretMut = useMutation({
    mutationFn: () => clearParentMobileLeadWebhookSecret().then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not clear security password.')),
  })

  const setDefaultTenantMut = useMutation({
    mutationFn: (tenant_id: string | null) => setParentMobileLeadDefaultTenant(tenant_id).then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not update default shop.')),
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
      setShowAddModal(false)
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not link shop. Check the shop number and owner email match.')),
  })

  const createTenantMut = useMutation({
    mutationFn: () => createTenantFromParentAccount({ tenant_name: newTenantName.trim(), tenant_slug: newTenantSlug.trim().toLowerCase(), plan_code: newTenantPlanCode }),
    onSuccess: () => {
      setError('')
      setNewTenantName('')
      setNewTenantSlug('')
      setNewTenantPlanCode('basic_watch')
      setShowAddModal(false)
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not create new shop.')),
  })

  const unlinkMut = useMutation({
    mutationFn: (tenantId: string) => unlinkTenantFromParentAccount(tenantId),
    onSuccess: () => {
      setError('')
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not remove shop from this account.')),
  })

  async function handleSwitchSite(tenantId: string) {
    if (!tenantId || tenantId === activeSiteTenantId) return
    setSwitchingTenantId(tenantId)
    setError('')
    try {
      await switchSite(tenantId)
      navigate('/dashboard')
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not switch to selected shop.'))
    } finally {
      setSwitchingTenantId('')
    }
  }

  async function handleUnlinkSite(tenantId: string) {
    if (!tenantId || tenantId === activeSiteTenantId) return
    const confirmed = window.confirm('Remove this shop from your account? You can re-add it later.')
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
      ? `${API_ORIGIN || window.location.origin}/v1/public/mobile-key-leads/${ingestPublicId}`
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

  function closeModal() {
    setShowAddModal(false)
    setError('')
    setTenantSlug('')
    setOwnerEmail('')
    setNewTenantName('')
    setNewTenantSlug('')
    setNewTenantPlanCode('basic_watch')
  }

  return (
    <div>
      <PageHeader
        title='My Shops'
        action={<Button onClick={() => { setError(''); setShowAddModal(true) }}>+ Add Shop</Button>}
      />
      <p className='text-sm mb-5' style={{ color: 'var(--cafe-text-muted)', marginTop: '-12px' }}>
        Manage all your shop locations from one login. Switch between shops or set up website lead routing below.
      </p>

      {/* Global error */}
      {error && !showAddModal && (
        <div className='mb-4 text-sm rounded-lg px-4 py-3' style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

      {/* Add Shop Modal */}
      {showAddModal && (
        <Modal title='Add a Shop' onClose={closeModal}>
          <div className='flex gap-2 mb-4'>
            <button
              className='flex-1 py-2 rounded-lg text-sm font-medium transition-colors'
              style={{
                backgroundColor: addMode === 'create' ? 'var(--cafe-accent)' : 'var(--cafe-surface)',
                color: addMode === 'create' ? 'var(--cafe-accent-text, #fff)' : 'var(--cafe-text-mid)',
                border: '1px solid var(--cafe-border-2)',
              }}
              onClick={() => { setAddMode('create'); setError('') }}
            >
              Create new shop
            </button>
            <button
              className='flex-1 py-2 rounded-lg text-sm font-medium transition-colors'
              style={{
                backgroundColor: addMode === 'link' ? 'var(--cafe-accent)' : 'var(--cafe-surface)',
                color: addMode === 'link' ? 'var(--cafe-accent-text, #fff)' : 'var(--cafe-text-mid)',
                border: '1px solid var(--cafe-border-2)',
              }}
              onClick={() => { setAddMode('link'); setError('') }}
            >
              Link existing shop
            </button>
          </div>

          {addMode === 'create' && (
            <div className='space-y-3'>
              <p className='text-sm' style={{ color: 'var(--cafe-text-mid)' }}>
                Set up a brand new shop and it will appear in your shop list straight away.
              </p>
              <Input
                label='Shop name'
                value={newTenantName}
                onChange={e => setNewTenantName(e.target.value)}
                placeholder='Mainspring North'
                autoFocus
              />
              <Input
                label='Shop Number'
                value={newTenantSlug}
                onChange={e => setNewTenantSlug(e.target.value)}
                placeholder='mainspring-north'
              />
              <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>
                The shop number is used to log in. Use lowercase letters, numbers and hyphens only.
              </p>
              <Select label='Plan' value={newTenantPlanCode} onChange={e => setNewTenantPlanCode(e.target.value as PlanCode)}>
                <option value='basic_watch'>Basic - Watch ($25/mo)</option>
                <option value='basic_shoe'>Basic - Shoe ($25/mo)</option>
                <option value='basic_auto_key'>Basic - Mobile Services ($25/mo)</option>
                <option value='basic_watch_shoe'>Watch + Shoe ($35/mo)</option>
                <option value='basic_watch_auto_key'>Watch + Mobile Services ($35/mo)</option>
                <option value='basic_shoe_auto_key'>Shoe + Mobile Services ($35/mo)</option>
                <option value='basic_all_tabs'>All service tabs ($45/mo)</option>
                <option value='pro'>Pro — full access ($50/mo)</option>
              </Select>
              {error && <p className='text-sm' style={{ color: '#C96A5A' }}>{error}</p>}
              <div className='flex justify-end gap-2 pt-1'>
                <Button variant='secondary' onClick={closeModal}>Cancel</Button>
                <Button
                  onClick={() => createTenantMut.mutate()}
                  disabled={!newTenantName.trim() || !newTenantSlug.trim() || createTenantMut.isPending}
                >
                  {createTenantMut.isPending ? 'Creating…' : 'Create Shop'}
                </Button>
              </div>
            </div>
          )}

          {addMode === 'link' && (
            <div className='space-y-3'>
              <p className='text-sm' style={{ color: 'var(--cafe-text-mid)' }}>
                Already have a shop on the system? Enter its shop number and owner email to link it to your account.
              </p>
              <Input
                label='Shop Number'
                value={tenantSlug}
                onChange={e => setTenantSlug(e.target.value)}
                placeholder='mainspring-south'
                autoFocus
              />
              <Input
                label='Owner email'
                type='email'
                value={ownerEmail}
                onChange={e => setOwnerEmail(e.target.value)}
                placeholder='owner@mainspringsouth.com'
              />
              {error && <p className='text-sm' style={{ color: '#C96A5A' }}>{error}</p>}
              <div className='flex justify-end gap-2 pt-1'>
                <Button variant='secondary' onClick={closeModal}>Cancel</Button>
                <Button
                  onClick={() => linkMut.mutate()}
                  disabled={!tenantSlug.trim() || !ownerEmail.trim() || linkMut.isPending}
                >
                  {linkMut.isPending ? 'Linking…' : 'Link Shop'}
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}

      {/* Shops list */}
      <Card className='mb-6'>
        <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>
            Your Shops {data ? `(${data.sites.length})` : ''}
          </h2>
          {data && (
            <p className='text-xs mt-0.5' style={{ color: 'var(--cafe-text-muted)' }}>
              {data.parent_account_name} · {data.owner_email}
            </p>
          )}
        </div>
        {!data || data.sites.length === 0 ? (
          <div className='px-5 py-8 text-center'>
            <p className='text-sm' style={{ color: 'var(--cafe-text-muted)' }}>No shops yet. Hit <strong>Add Shop</strong> to get started.</p>
          </div>
        ) : (
          <div>
            {data.sites.map(site => (
              <div
                key={site.tenant_id}
                className='px-5 py-4 flex items-center justify-between gap-4'
                style={{ borderBottom: '1px solid var(--cafe-border)' }}
              >
                <div className='min-w-0'>
                  <div className='flex items-center gap-2 flex-wrap'>
                    <p className='font-semibold text-sm' style={{ color: 'var(--cafe-text)' }}>{site.tenant_name}</p>
                    {site.tenant_id === activeSiteTenantId && (
                      <span
                        className='text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide'
                        style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)' }}
                      >
                        Active
                      </span>
                    )}
                  </div>
                  <p className='text-xs mt-0.5' style={{ color: 'var(--cafe-text-muted)' }}>
                    Shop #{site.tenant_slug} · {site.owner_email}
                  </p>
                </div>
                {site.tenant_id !== activeSiteTenantId && (
                  <div className='flex gap-2 shrink-0'>
                    <Button
                      variant='secondary'
                      className='px-3 py-1.5 text-xs'
                      onClick={() => handleSwitchSite(site.tenant_id)}
                      disabled={switchingTenantId === site.tenant_id || removingTenantId === site.tenant_id}
                    >
                      {switchingTenantId === site.tenant_id ? 'Switching…' : 'Switch to this shop'}
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
            ))}
          </div>
        )}
      </Card>

      {/* Website lead routing */}
      <Card className='mb-6 p-5'>
        <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Website Lead Routing</h2>
        <p className='text-sm mt-1 mb-5' style={{ color: 'var(--cafe-text-mid)' }}>
          Customers submit a job request on your website, pick their suburb, and it automatically lands in the right shop's inbox — ready to quote.
        </p>

        {/* Step 1 */}
        <div className='mb-5'>
          <div className='flex items-center gap-2 mb-2'>
            <StepBadge n={1} done={!!ingestUrl} />
            <p className='text-sm font-semibold' style={{ color: 'var(--cafe-text)' }}>Generate your link</p>
          </div>
          <p className='text-sm mb-3 ml-8' style={{ color: 'var(--cafe-text-mid)' }}>
            This is the URL your website posts to when a customer fills in their details.
          </p>
          <div className='ml-8 flex flex-wrap gap-2'>
            <Button
              variant='secondary'
              onClick={() => enableIngestMut.mutate()}
              disabled={enableIngestMut.isPending || !!ingestPublicId}
            >
              {ingestPublicId ? 'Link ready' : enableIngestMut.isPending ? 'Generating…' : 'Generate link'}
            </Button>
            {ingestUrl && (
              <Button variant='secondary' onClick={() => void copyIngestUrl()}>
                Copy link
              </Button>
            )}
          </div>
          {ingestUrl && (
            <p className='text-xs mt-2 ml-8 break-all font-mono' style={{ color: 'var(--cafe-text-muted)' }}>
              {ingestUrl}
            </p>
          )}
        </div>

        {/* Step 2 */}
        <div className='mb-5'>
          <div className='flex items-center gap-2 mb-2'>
            <StepBadge n={2} done={secretConfigured} />
            <p className='text-sm font-semibold' style={{ color: 'var(--cafe-text)' }}>Set a security password</p>
          </div>
          <p className='text-sm mb-3 ml-8' style={{ color: 'var(--cafe-text-mid)' }}>
            Your website sends this password with every request so only your site can submit leads. Must be at least 16 characters.
          </p>
          <div className='ml-8 grid gap-3 md:grid-cols-2 max-w-lg'>
            <Input
              label='Security password'
              type='password'
              autoComplete='new-password'
              value={webhookSecret}
              onChange={e => setWebhookSecret(e.target.value)}
              placeholder='Make it long and random'
            />
            <div className='flex items-end gap-2'>
              <Button
                onClick={() => setSecretMut.mutate(webhookSecret.trim())}
                disabled={webhookSecret.trim().length < 16 || setSecretMut.isPending}
              >
                {setSecretMut.isPending ? 'Saving…' : 'Save'}
              </Button>
              {secretConfigured && (
                <Button
                  variant='ghost'
                  onClick={() => clearSecretMut.mutate()}
                  disabled={clearSecretMut.isPending}
                >
                  {clearSecretMut.isPending ? 'Clearing…' : 'Clear'}
                </Button>
              )}
            </div>
          </div>
          {secretConfigured && (
            <p className='text-xs mt-2 ml-8 font-medium' style={{ color: '#1F6D4C' }}>
              Password saved — your website is ready to connect.
            </p>
          )}
        </div>

        {/* Step 3 */}
        <div>
          <div className='flex items-center gap-2 mb-2'>
            <StepBadge n={3} done={suburbRoutes.length > 0 || !!savedDefaultTenantId} />
            <p className='text-sm font-semibold' style={{ color: 'var(--cafe-text)' }}>Map suburbs to shops</p>
          </div>
          <p className='text-sm mb-3 ml-8' style={{ color: 'var(--cafe-text-mid)' }}>
            When a customer picks their suburb, the lead goes to the matching shop. Set a fallback shop for any suburbs you haven't mapped.
          </p>

          {/* Default shop */}
          <div className='ml-8 mb-4 flex flex-col sm:flex-row sm:items-end gap-3 max-w-lg'>
            <div className='flex-1 min-w-0'>
              <Select
                label='Fallback shop (unrecognised suburbs)'
                value={defaultTenantDraft}
                onChange={e => setDefaultTenantDraft(e.target.value)}
              >
                <option value=''>No fallback — only mapped suburbs accepted</option>
                {(data?.sites ?? []).map(s => (
                  <option key={s.tenant_id} value={s.tenant_id}>
                    {s.tenant_name} (#{s.tenant_slug})
                  </option>
                ))}
              </Select>
            </div>
            <Button
              variant='secondary'
              onClick={() => setDefaultTenantMut.mutate(defaultTenantDraft === '' ? null : defaultTenantDraft)}
              disabled={!defaultTenantDirty || setDefaultTenantMut.isPending}
            >
              {setDefaultTenantMut.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>

          {/* Add route */}
          <div className='ml-8 grid gap-3 md:grid-cols-4 max-w-2xl'>
            <Select label='State' value={routeState} onChange={e => setRouteState(e.target.value)}>
              {['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'].map(st => (
                <option key={st} value={st}>{st}</option>
              ))}
            </Select>
            <Input
              label='Suburb'
              value={routeSuburb}
              onChange={e => setRouteSuburb(e.target.value)}
              placeholder='e.g. Parramatta'
            />
            <Select label='Goes to' value={routeTargetTenantId} onChange={e => setRouteTargetTenantId(e.target.value)}>
              <option value=''>Select shop</option>
              {(data?.sites ?? []).map(s => (
                <option key={s.tenant_id} value={s.tenant_id}>{s.tenant_name}</option>
              ))}
            </Select>
            <div className='flex items-end'>
              <Button
                onClick={() => createRouteMut.mutate()}
                disabled={!routeSuburb.trim() || !routeTargetTenantId || createRouteMut.isPending}
              >
                {createRouteMut.isPending ? 'Adding…' : 'Add'}
              </Button>
            </div>
          </div>

          {/* Route list */}
          {suburbRoutes.length === 0 ? (
            <p className='text-sm mt-3 ml-8' style={{ color: 'var(--cafe-text-muted)' }}>
              No suburb routes yet.
            </p>
          ) : (
            <ul className='mt-3 ml-8 divide-y rounded-lg border' style={{ borderColor: 'var(--cafe-border)' }}>
              {suburbRoutes.map(r => (
                <li key={r.id} className='px-3 py-2.5 flex justify-between gap-3 text-sm'>
                  <span style={{ color: 'var(--cafe-text)' }}>
                    <span className='font-medium'>{r.suburb_normalized}</span>
                    <span style={{ color: 'var(--cafe-text-muted)' }}>, {r.state_code}</span>
                    <span style={{ color: 'var(--cafe-text-muted)' }}> → {siteLabel(r.target_tenant_id)}</span>
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
        </div>
      </Card>

      {/* Activity log */}
      <Card>
        <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
          <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Recent Activity</h2>
          <p className='text-xs mt-0.5' style={{ color: 'var(--cafe-text-muted)' }}>
            Actions taken across all your shops.
          </p>
        </div>
        {activity.length === 0 ? (
          <EmptyState message='No activity recorded yet.' />
        ) : (
          <div>
            {activity.map(event => (
              <div
                key={event.id}
                className='px-5 py-3 text-sm flex items-start justify-between gap-3'
                style={{ borderBottom: '1px solid var(--cafe-border)' }}
              >
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

function StepBadge({ n, done }: { n: number; done: boolean }) {
  return (
    <div
      className='w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0'
      style={{
        backgroundColor: done ? '#1F6D4C' : 'var(--cafe-border-2)',
        color: done ? '#fff' : 'var(--cafe-text-muted)',
      }}
    >
      {done ? '✓' : n}
    </div>
  )
}
