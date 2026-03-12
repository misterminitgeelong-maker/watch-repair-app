import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createTenantFromParentAccount, getApiErrorMessage, getMyParentAccount, linkTenantToParentAccount, listParentAccountActivity, unlinkTenantFromParentAccount, type PlanCode } from '@/lib/api'
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
  const [newTenantPlanCode, setNewTenantPlanCode] = useState<PlanCode>('enterprise')
  const [error, setError] = useState('')
  const [switchingTenantId, setSwitchingTenantId] = useState('')
  const [removingTenantId, setRemovingTenantId] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['parent-account-me'],
    queryFn: () => getMyParentAccount().then(r => r.data),
  })

  const { data: activity = [] } = useQuery({
    queryKey: ['parent-account-activity'],
    queryFn: () => listParentAccountActivity(30).then(r => r.data),
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
      setNewTenantPlanCode('enterprise')
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

  return (
    <div>
      <PageHeader title='Parent Account' />

      <Card className='mb-5 p-4 sm:p-5'>
        <p className='text-xs font-semibold tracking-wide uppercase' style={{ color: 'var(--cafe-text-muted)' }}>
          Link existing site
        </p>
        <p className='text-sm mt-2' style={{ color: 'var(--cafe-text-mid)' }}>
          Add another tenant/site by supplying its tenant slug and owner email.
        </p>
        <div className='mt-3 grid gap-3 md:grid-cols-2'>
          <Input label='Tenant slug' value={tenantSlug} onChange={e => setTenantSlug(e.target.value)} placeholder='site-b-1234' />
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
          <Input label='Site slug' value={newTenantSlug} onChange={e => setNewTenantSlug(e.target.value)} placeholder='mainspring-north' />
          <Select label='Plan' value={newTenantPlanCode} onChange={e => setNewTenantPlanCode(e.target.value as PlanCode)}>
            <option value='enterprise'>Enterprise</option>
            <option value='watch'>Watch</option>
            <option value='shoe'>Shoe</option>
            <option value='auto_key'>Auto Key</option>
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
                  <p className='text-xs' style={{ color: 'var(--cafe-text-muted)' }}>Slug: {site.tenant_slug}</p>
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
