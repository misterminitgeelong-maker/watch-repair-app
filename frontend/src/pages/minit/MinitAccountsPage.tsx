import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound } from 'lucide-react'
import {
  createShopOwnerInvite,
  formatTenantLabel,
  getApiErrorMessage,
  linkTenantToParentAccount,
  provisionMinitShop,
  unlinkTenantFromParentAccount,
  type ShopOwnerInvite,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { PARENT_ACCOUNT_QUERY_KEY, useParentAccount } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY, useParentAccountSites } from '@/hooks/useParentAccountSites'
import { Button, Card, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

function formatAreaRegion(area?: string | null, region?: string | null) {
  const parts = [area?.trim(), region?.trim()].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : null
}

export default function MinitAccountsPage() {
  const { refreshSession } = useAuth()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [shopNumber, setShopNumber] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [businessAddress, setBusinessAddress] = useState('')
  const [linkSlug, setLinkSlug] = useState('')
  const [linkEmail, setLinkEmail] = useState('')
  const [addMode, setAddMode] = useState<'provision' | 'link'>('provision')
  const [removingId, setRemovingId] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [retailLimit, setRetailLimit] = useState(50)
  const [invitingId, setInvitingId] = useState('')
  const [inviteResult, setInviteResult] = useState<ShopOwnerInvite | null>(null)
  const [inviteCopied, setInviteCopied] = useState(false)

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(search)
      setRetailLimit(50)
    }, 300)
    return () => window.clearTimeout(handle)
  }, [search])

  const { data: summary, isLoading: summaryLoading } = useParentAccount()
  const { data: retailPage, isLoading: retailLoading } = useParentAccountSites({
    plan_kind: 'retail',
    limit: retailLimit,
    search: debouncedSearch || undefined,
  })
  const { data: operatorsPage } = useParentAccountSites({
    plan_kind: 'operator',
    limit: 50,
  })

  const retailSites = retailPage?.sites ?? []
  const retailTotal = retailPage?.total ?? summary?.site_count ?? 0
  const operators = operatorsPage?.sites ?? []
  const isLoading = summaryLoading && !summary

  const provisionMut = useMutation({
    mutationFn: () =>
      provisionMinitShop({
        shop_number: shopNumber.trim(),
        tenant_name: tenantName.trim(),
        business_address: businessAddress.trim() || undefined,
      }).then(r => r.data),
    onSuccess: () => {
      setError('')
      setShowAdd(false)
      setShopNumber('')
      setTenantName('')
      setBusinessAddress('')
      void refreshSession()
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not add shop.')),
  })

  const linkMut = useMutation({
    mutationFn: () =>
      linkTenantToParentAccount({
        tenant_slug: linkSlug.trim().toLowerCase(),
        owner_email: linkEmail.trim().toLowerCase(),
        shop_number: shopNumber.trim() || undefined,
      }).then(r => r.data),
    onSuccess: () => {
      setError('')
      setShowAdd(false)
      void refreshSession()
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not link shop.')),
  })

  const unlinkMut = useMutation({
    mutationFn: (tenantId: string) => unlinkTenantFromParentAccount(tenantId).then(r => r.data),
    onSuccess: () => {
      void refreshSession()
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not remove shop.')),
  })

  const inviteMut = useMutation({
    mutationFn: (tenantId: string) => createShopOwnerInvite(tenantId).then(r => r.data),
    onSuccess: invite => {
      setError('')
      setInviteCopied(false)
      setInviteResult(invite)
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not create an invite link.')),
  })

  if (isLoading) return <Spinner />

  async function handleRemove(tenantId: string) {
    if (!window.confirm('Remove this shop from the network? The tenant is not deleted.')) return
    setRemovingId(tenantId)
    try {
      await unlinkMut.mutateAsync(tenantId)
    } finally {
      setRemovingId('')
    }
  }

  async function handleInvite(tenantId: string) {
    setInvitingId(tenantId)
    try {
      await inviteMut.mutateAsync(tenantId)
    } finally {
      setInvitingId('')
    }
  }

  async function copyInviteLink() {
    if (!inviteResult) return
    try {
      await navigator.clipboard.writeText(inviteResult.invite_url)
      setInviteCopied(true)
    } catch {
      setInviteCopied(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Manage shops"
        action={
          <Button onClick={() => { setError(''); setShowAdd(true) }}>+ Add shop</Button>
        }
      />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Add, link, or remove shops on the network. Use Shops to browse by region.
      </p>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

      <Card className="mb-6 overflow-hidden">
        <div
          className="px-5 py-3 flex flex-wrap items-center justify-between gap-3"
          style={{ borderBottom: '1px solid var(--ms-border)' }}
        >
          <span className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
            Retail shops ({retailTotal})
          </span>
          {retailTotal > 0 && (
            <div className="w-full sm:w-64">
              <Input
                type="search"
                placeholder="Search name, shop #, area…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                aria-label="Search retail shops"
              />
            </div>
          )}
        </div>
        {retailTotal === 0 ? (
          <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No retail shops linked yet.</p>
        ) : retailSites.length === 0 && !retailLoading ? (
          <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            No shops match your search.
          </p>
        ) : (
          <>
          {retailSites.map(site => {
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
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                  {areaRegion ? `${areaRegion} · ` : ''}login {site.tenant_slug} · {site.plan_code}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => handleInvite(site.tenant_id)}
                  disabled={invitingId === site.tenant_id}
                  title="Send a link letting this shop set its own email & password"
                >
                  <span className="inline-flex items-center gap-1">
                    <KeyRound size={13} />
                    {invitingId === site.tenant_id ? 'Sending…' : 'Invite owner'}
                  </span>
                </Button>
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => handleRemove(site.tenant_id)}
                  disabled={removingId === site.tenant_id}
                >
                  {removingId === site.tenant_id ? 'Removing…' : 'Remove'}
                </Button>
              </div>
            </div>
            )
          })}
          {retailSites.length < retailTotal && (
            <div className="px-5 py-4">
              <Button
                variant="secondary"
                onClick={() => setRetailLimit(limit => limit + 50)}
                disabled={retailLoading}
              >
                {retailLoading ? 'Loading…' : `Load more (${retailSites.length} of ${retailTotal})`}
              </Button>
            </div>
          )}
          </>
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
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                  {areaRegion ? `${areaRegion} · ` : ''}{site.tenant_slug} · {site.plan_code}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => handleInvite(site.tenant_id)}
                  disabled={invitingId === site.tenant_id}
                  title="Send a link letting this shop set its own email & password"
                >
                  <span className="inline-flex items-center gap-1">
                    <KeyRound size={13} />
                    {invitingId === site.tenant_id ? 'Sending…' : 'Invite owner'}
                  </span>
                </Button>
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => handleRemove(site.tenant_id)}
                  disabled={removingId === site.tenant_id}
                >
                  {removingId === site.tenant_id ? 'Removing…' : 'Remove'}
                </Button>
              </div>
            </div>
            )
          })}
        </Card>
      )}

      {showAdd && (
        <Modal title="Add shop" onClose={() => setShowAdd(false)}>
          <div className="space-y-4">
            <Select label="Mode" value={addMode} onChange={e => setAddMode(e.target.value as 'provision' | 'link')}>
              <option value="provision">New Minit shop (minit-{'{number}'})</option>
              <option value="link">Link existing tenant</option>
            </Select>
            {addMode === 'provision' ? (
              <>
                <Input label="Minit shop number" value={shopNumber} onChange={e => setShopNumber(e.target.value)} placeholder="3269" />
                <Input label="Shop name" value={tenantName} onChange={e => setTenantName(e.target.value)} placeholder="Chadstone" />
                <Input label="Address (optional)" value={businessAddress} onChange={e => setBusinessAddress(e.target.value)} />
              </>
            ) : (
              <>
                <Input label="Tenant slug" value={linkSlug} onChange={e => setLinkSlug(e.target.value)} />
                <Input label="Owner email" value={linkEmail} onChange={e => setLinkEmail(e.target.value)} />
                <Input label="Shop number (optional)" value={shopNumber} onChange={e => setShopNumber(e.target.value)} />
              </>
            )}
            {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
              <Button
                onClick={() => (addMode === 'provision' ? provisionMut.mutate() : linkMut.mutate())}
                disabled={provisionMut.isPending || linkMut.isPending}
              >
                {provisionMut.isPending || linkMut.isPending ? 'Saving…' : 'Add shop'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {inviteResult && (
        <Modal title="Invite sent" onClose={() => setInviteResult(null)}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              Share this one-time link with {inviteResult.tenant_name}
              {inviteResult.shop_number ? ` (#${inviteResult.shop_number})` : ''}. It lets{' '}
              <strong>{inviteResult.owner_email}</strong> set their own email &amp; password — it expires{' '}
              {new Date(inviteResult.expires_at).toLocaleDateString()}.
            </p>
            <div className="flex items-center gap-2">
              <Input readOnly value={inviteResult.invite_url} onFocus={e => e.currentTarget.select()} />
              <Button variant="secondary" onClick={copyInviteLink} className="px-3 py-2 shrink-0">
                <Copy size={14} />
              </Button>
            </div>
            {inviteCopied && <p className="text-xs" style={{ color: '#1A6A3A' }}>Copied to clipboard.</p>}
            <div className="flex justify-end">
              <Button onClick={() => setInviteResult(null)}>Done</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
