import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createTenantFromParentAccount,
  formatTenantLabel,
  getApiErrorMessage,
  getParentShopBookingUsage,
  linkTenantToParentAccount,
  listParentAccountActivity,
  unlinkTenantFromParentAccount,
  type PlanCode,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { isMinitHqUi } from '@/lib/minitProduct'
import WebsiteLeadRoutingPanel from '@/components/minit/WebsiteLeadRoutingPanel'
import { PARENT_ACCOUNT_QUERY_KEY, useParentAccount } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY, useParentAccountSites } from '@/hooks/useParentAccountSites'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

export default function ParentAccountPage() {
  const navigate = useNavigate()
  const { activeSiteTenantId, switchSite, refreshSession, minitHqUi, product, planCode, tenantSlug: sessionTenantSlug } = useAuth()
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
  const [newShopNumber, setNewShopNumber] = useState('')
  const [linkShopNumber, setLinkShopNumber] = useState('')
  const [newTenantPlanCode, setNewTenantPlanCode] = useState<PlanCode>('basic_watch')

  const [error, setError] = useState('')
  const [switchingTenantId, setSwitchingTenantId] = useState('')
  const [removingTenantId, setRemovingTenantId] = useState('')
  const [usageMonth, setUsageMonth] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  })
  const [siteSearch, setSiteSearch] = useState('')
  const [debouncedSiteSearch, setDebouncedSiteSearch] = useState('')
  const [retailLimit, setRetailLimit] = useState(50)

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSiteSearch(siteSearch)
      setRetailLimit(50)
    }, 300)
    return () => window.clearTimeout(handle)
  }, [siteSearch])

  const { data, isLoading } = useParentAccount()
  const { data: retailPage } = useParentAccountSites({
    plan_kind: 'retail',
    limit: retailLimit,
    search: debouncedSiteSearch || undefined,
  })
  const { data: operatorsPage } = useParentAccountSites({
    plan_kind: 'operator',
    limit: 50,
  })

  function invalidateParentQueries() {
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
  }

  const { data: activity = [] } = useQuery({
    queryKey: ['parent-account-activity'],
    queryFn: () => listParentAccountActivity(30).then(r => r.data),
  })

  const { data: bookingUsage } = useQuery({
    queryKey: ['parent-shop-booking-usage', usageMonth],
    queryFn: () => getParentShopBookingUsage(usageMonth).then(r => r.data),
    enabled: !!data,
  })

  const linkMut = useMutation({
    mutationFn: () =>
      linkTenantToParentAccount({
        tenant_slug: tenantSlug.trim(),
        owner_email: ownerEmail.trim().toLowerCase(),
        shop_number: linkShopNumber.trim() || undefined,
      }),
    onSuccess: () => {
      setError('')
      setTenantSlug('')
      setOwnerEmail('')
      setLinkShopNumber('')
      setShowAddModal(false)
      void refreshSession()
      invalidateParentQueries()
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not link shop. Check the shop number and owner email match.')),
  })

  const createTenantMut = useMutation({
    mutationFn: () =>
      createTenantFromParentAccount({
        tenant_name: newTenantName.trim(),
        tenant_slug: newTenantSlug.trim().toLowerCase(),
        plan_code: newTenantPlanCode,
        shop_number: newShopNumber.trim() || undefined,
      }),
    onSuccess: () => {
      setError('')
      setNewTenantName('')
      setNewTenantSlug('')
      setNewShopNumber('')
      setNewTenantPlanCode('basic_watch')
      setShowAddModal(false)
      void refreshSession()
      invalidateParentQueries()
      qc.invalidateQueries({ queryKey: ['parent-account-activity'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not create new shop.')),
  })

  const unlinkMut = useMutation({
    mutationFn: (tenantId: string) => unlinkTenantFromParentAccount(tenantId),
    onSuccess: () => {
      setError('')
      void refreshSession()
      invalidateParentQueries()
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

  function renderSiteRow(site: (typeof retailSites)[number]) {
    return (
      <div
        key={site.tenant_id}
        className='px-5 py-4 flex items-center justify-between gap-4'
        style={{ borderBottom: '1px solid var(--ms-border)' }}
      >
        <div className='min-w-0'>
          <div className='flex items-center gap-2 flex-wrap'>
            <p className='font-semibold text-sm' style={{ color: 'var(--ms-text)' }}>{site.tenant_name}</p>
            {site.tenant_id === activeSiteTenantId && (
              <span
                className='text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide'
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
              >
                Active
              </span>
            )}
          </div>
          <p className='text-xs mt-0.5' style={{ color: 'var(--ms-text-muted)' }}>
            {site.shop_number ? `Minit #${site.shop_number} · ` : ''}login {site.tenant_slug} · {site.plan_code} · {site.owner_email}
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
              {switchingTenantId === site.tenant_id ? 'Switching…' : 'Switch to this site'}
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
    )
  }

  if (isLoading) return <Spinner />

  if (minitHqUi || isMinitHqUi(product, planCode, sessionTenantSlug)) {
    return <Navigate to="/minit/lead-routing" replace />
  }

  const retailSites = retailPage?.sites ?? []
  const retailTotal = retailPage?.total ?? data?.site_count ?? 0
  const operatorSites = operatorsPage?.sites ?? []

  function closeModal() {
    setShowAddModal(false)
    setError('')
    setTenantSlug('')
    setOwnerEmail('')
    setNewTenantName('')
    setNewTenantSlug('')
    setNewShopNumber('')
    setLinkShopNumber('')
    setNewTenantPlanCode('basic_watch')
  }

  return (
    <div>
      <PageHeader
        title='My Shops'
        action={<Button onClick={() => { setError(''); setShowAddModal(true) }}>+ Add Shop</Button>}
      />
      <p className='text-sm mb-5' style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Manage all your shop locations from one login. Switch between shops or set up website lead routing below.
      </p>

      {/* Global error */}
      {error && !showAddModal && (
        <div className='mb-4 text-sm rounded-lg px-4 py-3' style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

      <Card className='mb-6 p-5'>
        <h2 className='font-semibold mb-3' style={{ color: 'var(--ms-text)' }}>
          Shop mobile booking usage
        </h2>
        <div className='flex flex-wrap items-end gap-3 mb-4'>
          <Input
            label='Month'
            type='month'
            value={usageMonth}
            onChange={e => setUsageMonth(e.target.value)}
            className='w-44'
          />
        </div>
        {bookingUsage ? (
          <>
            <p className='text-sm mb-3' style={{ color: 'var(--ms-text-mid)' }}>
              {bookingUsage.booking_tenant_count} shop{bookingUsage.booking_tenant_count === 1 ? '' : 's'} with booking access
              {' · '}
              {bookingUsage.shops.reduce((n, s) => n + s.accepted_bookings_count, 0)} accepted in {bookingUsage.month}
            </p>
            {bookingUsage.shops.length === 0 ? (
              <p className='text-sm' style={{ color: 'var(--ms-text-muted)' }}>No booking shops linked yet.</p>
            ) : (
              <div className='divide-y' style={{ borderColor: 'var(--ms-border)' }}>
                {bookingUsage.shops.map(shop => (
                  <div key={shop.tenant_id} className='py-2 flex justify-between gap-4 text-sm'>
                    <span style={{ color: 'var(--ms-text)' }}>{formatTenantLabel(shop.tenant_name, shop.shop_number)}</span>
                    <span style={{ color: 'var(--ms-text-muted)' }}>
                      {shop.accepted_bookings_count} accepted · {shop.pending_count} pending
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <Spinner />
        )}
      </Card>

      {/* Add Shop Modal */}
      {showAddModal && (
        <Modal title='Add a Shop' onClose={closeModal}>
          <div className='flex gap-2 mb-4'>
            <button
              className='flex-1 py-2 rounded-lg text-sm font-medium transition-colors'
              style={{
                backgroundColor: addMode === 'create' ? 'var(--ms-accent)' : 'var(--ms-surface)',
                color: addMode === 'create' ? '#fff' : 'var(--ms-text-mid)',
                border: '1px solid var(--ms-border-strong)',
              }}
              onClick={() => { setAddMode('create'); setError('') }}
            >
              Create new shop
            </button>
            <button
              className='flex-1 py-2 rounded-lg text-sm font-medium transition-colors'
              style={{
                backgroundColor: addMode === 'link' ? 'var(--ms-accent)' : 'var(--ms-surface)',
                color: addMode === 'link' ? '#fff' : 'var(--ms-text-mid)',
                border: '1px solid var(--ms-border-strong)',
              }}
              onClick={() => { setAddMode('link'); setError('') }}
            >
              Link existing shop
            </button>
          </div>

          {addMode === 'create' && (
            <div className='space-y-3'>
              <p className='text-sm' style={{ color: 'var(--ms-text-mid)' }}>
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
                label='Minit shop number'
                value={newShopNumber}
                onChange={e => setNewShopNumber(e.target.value.replace(/\D/g, '').slice(0, 10))}
                placeholder='3269'
                inputMode='numeric'
              />
              <Input
                label='Login slug'
                value={newTenantSlug}
                onChange={e => setNewTenantSlug(e.target.value)}
                placeholder='mainspring-north'
              />
              <p className='text-xs' style={{ color: 'var(--ms-text-muted)' }}>
                The login slug is used to sign in. Use lowercase letters, numbers and hyphens only.
              </p>
              <Select label='Plan' value={newTenantPlanCode} onChange={e => setNewTenantPlanCode(e.target.value as PlanCode)}>
                <option value='basic_watch'>Basic - Watch ($25/mo)</option>
                <option value='basic_shoe'>Basic - Shoe ($25/mo)</option>
                <option value='basic_auto_key'>Basic - Mobile Services ($25/mo)</option>
                <option value='basic_watch_shoe'>Watch + Shoe ($35/mo)</option>
                <option value='basic_watch_auto_key'>Watch + Mobile Services ($35/mo)</option>
                <option value='basic_shoe_auto_key'>Shoe + Mobile Services ($35/mo)</option>
                <option value='basic_all_tabs'>All service tabs ($45/mo)</option>
                <option value='booking_only'>Shop booking only ($15/mo)</option>
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
              <p className='text-sm' style={{ color: 'var(--ms-text-mid)' }}>
                Already have a shop on the system? Enter its login slug and owner email to link it to your account.
              </p>
              <Input
                label='Login slug'
                value={tenantSlug}
                onChange={e => setTenantSlug(e.target.value)}
                placeholder='mainspring-south'
                autoFocus
              />
              <Input
                label='Minit shop number (optional)'
                value={linkShopNumber}
                onChange={e => setLinkShopNumber(e.target.value.replace(/\D/g, '').slice(0, 10))}
                placeholder='3269'
                inputMode='numeric'
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

      {/* Sites list — retail vs operators */}
      <Card className='mb-6'>
        <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <h2 className='font-semibold' style={{ color: 'var(--ms-text)' }}>
            Linked sites {data ? `(${data.site_count})` : ''}
          </h2>
          {data && (
            <p className='text-xs mt-0.5' style={{ color: 'var(--ms-text-muted)' }}>
              {data.parent_account_name} · {data.owner_email}
            </p>
          )}
        </div>
        {!data || data.site_count === 0 ? (
          <div className='px-5 py-8 text-center'>
            <p className='text-sm' style={{ color: 'var(--ms-text-muted)' }}>No shops yet. Hit <strong>Add Shop</strong> to get started.</p>
          </div>
        ) : (
          <div>
            {retailTotal > 0 && (
              <>
                <div className='px-5 pt-4 pb-2 flex flex-wrap items-center justify-between gap-3'>
                  <p className='text-xs font-semibold uppercase tracking-wide' style={{ color: 'var(--ms-text-muted)' }}>
                    Retail shops ({retailTotal})
                  </p>
                  <div className='w-full sm:w-64'>
                    <Input
                      type='search'
                      placeholder='Search name, shop #, area…'
                      value={siteSearch}
                      onChange={e => setSiteSearch(e.target.value)}
                      aria-label='Search retail shops'
                    />
                  </div>
                </div>
                {retailSites.map(site => renderSiteRow(site))}
                {retailSites.length < retailTotal && (
                  <div className='px-5 py-4'>
                    <Button variant='secondary' onClick={() => setRetailLimit(limit => limit + 50)}>
                      Load more ({retailSites.length} of {retailTotal})
                    </Button>
                  </div>
                )}
              </>
            )}
            {operatorSites.length > 0 && (
              <>
                <p className='px-5 pt-4 pb-1 text-xs font-semibold uppercase tracking-wide' style={{ color: 'var(--ms-text-muted)' }}>
                  Mobile operators ({operatorSites.length})
                </p>
                {operatorSites.map(site => renderSiteRow(site))}
              </>
            )}
          </div>
        )}
      </Card>

      <div className='mb-6'>
        <WebsiteLeadRoutingPanel onError={setError} />
      </div>

      {/* Activity log */}
      <Card>
        <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <h2 className='font-semibold' style={{ color: 'var(--ms-text)' }}>Recent Activity</h2>
          <p className='text-xs mt-0.5' style={{ color: 'var(--ms-text-muted)' }}>
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
                style={{ borderBottom: '1px solid var(--ms-border)' }}
              >
                <div>
                  <p className='font-semibold' style={{ color: 'var(--ms-text)' }}>{event.event_summary}</p>
                  <p className='text-xs capitalize' style={{ color: 'var(--ms-text-muted)' }}>
                    {event.event_type.replace(/_/g, ' ')}{event.actor_email ? ` · ${event.actor_email}` : ''}
                  </p>
                </div>
                <p className='text-xs whitespace-nowrap' style={{ color: 'var(--ms-text-muted)' }}>
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
