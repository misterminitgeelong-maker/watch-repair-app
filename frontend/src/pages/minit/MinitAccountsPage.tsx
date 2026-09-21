import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Copy, Download, KeyRound, LogIn } from 'lucide-react'
import {
  createShopOwnerInvite,
  formatTenantLabel,
  getApiErrorMessage,
  linkTenantToParentAccount,
  MINIT_INVITE_PLAN_OPTIONS,
  MINIT_SHOP_TYPE_OPTIONS,
  provisionMinitShop,
  unlinkTenantFromParentAccount,
  updateLinkedSite,
  type MinitShopType,
  type ParentAccountSite,
  type PlanCode,
  type ShopOwnerInvite,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { useHqEnterShop } from '@/lib/hqEnterShop'
import { PARENT_ACCOUNT_QUERY_KEY, useParentAccount } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY, useParentAccountSites } from '@/hooks/useParentAccountSites'
import { HqStaffCard, REGIONS_QUERY_KEY, RegionsCard, useRegions } from '@/components/minit/MinitNetworkPanels'
import { Button, Card, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

function formatAreaRegion(area?: string | null, region?: string | null) {
  const parts = [area?.trim(), region?.trim()].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : null
}

/** The owner contact line under each shop: who an invite would actually reach. */
function OwnerContact({ site }: { site: ParentAccountSite }) {
  const mobile = site.owner_mobile?.trim()
  if (site.owner_is_shared_hq_login) {
    return (
      <p className="text-xs mt-1" style={{ color: '#8A5010' }}>
        Shared HQ login — no franchisee contact on file yet
      </p>
    )
  }
  return (
    <p className="text-xs mt-1" style={{ color: 'var(--ms-text)' }}>
      {site.owner_full_name ? `${site.owner_full_name} · ` : ''}
      <a href={`mailto:${site.owner_email}`} style={{ textDecoration: 'underline' }}>
        {site.owner_email}
      </a>
      {mobile ? (
        <>
          {' · '}
          <a href={`tel:${mobile.replace(/\s+/g, '')}`} style={{ textDecoration: 'underline' }}>
            {mobile}
          </a>
        </>
      ) : (
        <span style={{ color: 'var(--ms-text-muted)' }}> · no mobile on file</span>
      )}
    </p>
  )
}

function csvCell(value: string | null | undefined) {
  const text = (value ?? '').toString()
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** Download every loaded shop's owner contact details, for working through invites. */
function downloadContactsCsv(sites: ParentAccountSite[]) {
  const header = ['Shop number', 'Shop name', 'Type', 'Area', 'Region', 'Owner name', 'Owner email', 'Owner mobile', 'Has franchisee contact']
  const rows = sites.map(site => [
    site.shop_number ?? '',
    site.tenant_name,
    site.network_role === 'operator' ? 'Mobile' : 'Physical',
    site.area ?? '',
    site.region ?? '',
    site.owner_is_shared_hq_login ? '' : site.owner_full_name,
    site.owner_is_shared_hq_login ? '' : site.owner_email,
    site.owner_is_shared_hq_login ? '' : (site.owner_mobile ?? ''),
    site.owner_is_shared_hq_login ? 'No — shared HQ login' : 'Yes',
  ])
  const csv = [header, ...rows].map(cols => cols.map(csvCell).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `minit-shop-contacts-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

export default function MinitAccountsPage() {
  const { refreshSession, sessionUserId } = useAuth()
  const qc = useQueryClient()
  const { enterShop, entering, error: enterError } = useHqEnterShop()
  const { data: regions = [] } = useRegions()
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [shopNumber, setShopNumber] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [businessAddress, setBusinessAddress] = useState('')
  const [linkSlug, setLinkSlug] = useState('')
  const [linkEmail, setLinkEmail] = useState('')
  const [addMode, setAddMode] = useState<'provision' | 'link'>('provision')
  const [shopType, setShopType] = useState<MinitShopType>('physical')
  const [ownerEmail, setOwnerEmail] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [ownerMobile, setOwnerMobile] = useState('')
  const [removingId, setRemovingId] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [retailLimit, setRetailLimit] = useState(50)
  const [inviteTarget, setInviteTarget] = useState<ParentAccountSite | null>(null)
  const [invitePlanCode, setInvitePlanCode] = useState<PlanCode | string>('')
  const [inviteResult, setInviteResult] = useState<ShopOwnerInvite | null>(null)
  const [inviteCopied, setInviteCopied] = useState(false)
  const [openTarget, setOpenTarget] = useState<ParentAccountSite | null>(null)
  const [openReason, setOpenReason] = useState('')

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
  // Only HQ admins restructure the network or walk into its shops.
  const canEdit = summary?.my_role === 'hq_admin'

  const regionMut = useMutation({
    mutationFn: ({ tenantId, regionId }: { tenantId: string; regionId: string }) =>
      updateLinkedSite(tenantId, regionId ? { region_id: regionId } : { clear_region: true }).then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      qc.invalidateQueries({ queryKey: REGIONS_QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not change that shop\'s region.')),
  })

  function openShopButton(site: ParentAccountSite) {
    if (!canEdit) return null
    return (
      <Button
        variant="ghost"
        className="text-xs px-3 py-1.5"
        onClick={() => { setOpenReason(''); setOpenTarget(site) }}
        disabled={entering === site.tenant_id}
        title="Open a 30-minute support session inside this shop, as its owner"
      >
        <span className="inline-flex items-center gap-1">
          <LogIn size={13} />
          {entering === site.tenant_id ? 'Opening…' : 'Open shop'}
        </span>
      </Button>
    )
  }

  const provisionMut = useMutation({
    mutationFn: () =>
      provisionMinitShop({
        shop_number: shopNumber.trim(),
        tenant_name: tenantName.trim(),
        business_address: businessAddress.trim() || undefined,
        shop_type: shopType,
        owner_email: ownerEmail.trim() || undefined,
        owner_full_name: ownerName.trim() || undefined,
        owner_mobile: ownerMobile.trim() || undefined,
      }).then(r => r.data),
    onSuccess: () => {
      setError('')
      setShowAdd(false)
      setShopNumber('')
      setTenantName('')
      setBusinessAddress('')
      setShopType('physical')
      setOwnerEmail('')
      setOwnerName('')
      setOwnerMobile('')
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
    mutationFn: ({ tenantId, planCode }: { tenantId: string; planCode: string }) =>
      createShopOwnerInvite(tenantId, planCode || undefined).then(r => r.data),
    onSuccess: invite => {
      setError('')
      setInviteCopied(false)
      setInviteTarget(null)
      setInviteResult(invite)
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
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

  function openInvite(site: ParentAccountSite) {
    setError('')
    const currentPlan = MINIT_INVITE_PLAN_OPTIONS.some(o => o.code === site.plan_code) ? site.plan_code : ''
    setInvitePlanCode(currentPlan)
    setInviteTarget(site)
  }

  function sendInvite() {
    if (!inviteTarget) return
    inviteMut.mutate({ tenantId: inviteTarget.tenant_id, planCode: invitePlanCode })
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
          canEdit ? <Button onClick={() => { setError(''); setShowAdd(true) }}>+ Add shop</Button> : undefined
        }
      />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Add, link, or remove shops on the network. Use Shops to browse by region.
      </p>

      {(error || enterError) && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error || enterError}
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
          {retailSites.length + operators.length > 0 && (
            <Button
              variant="secondary"
              className="text-xs px-3 py-1.5"
              onClick={() => downloadContactsCsv([...retailSites, ...operators])}
              title="Download the owner name, email and mobile for every shop loaded below"
            >
              <span className="inline-flex items-center gap-1">
                <Download size={13} />
                Export contacts
              </span>
            </Button>
          )}
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
                <OwnerContact site={site} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {canEdit && regions.length > 0 && (
                  <Select
                    value={site.region_id ?? ''}
                    onChange={e => regionMut.mutate({ tenantId: site.tenant_id, regionId: e.target.value })}
                    aria-label={`Region for ${site.tenant_name}`}
                    disabled={regionMut.isPending}
                    className="text-xs"
                  >
                    <option value="">No region</option>
                    {regions.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </Select>
                )}
                {openShopButton(site)}
                {canEdit && (
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => openInvite(site)}
                  title="Choose a plan level and send a link letting this shop set its own email & password"
                >
                  <span className="inline-flex items-center gap-1">
                    <KeyRound size={13} />
                    Invite owner
                  </span>
                </Button>
                )}
                {canEdit && (
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => handleRemove(site.tenant_id)}
                  disabled={removingId === site.tenant_id}
                >
                  {removingId === site.tenant_id ? 'Removing…' : 'Remove'}
                </Button>
                )}
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
                <OwnerContact site={site} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {openShopButton(site)}
                {canEdit && (
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => openInvite(site)}
                  title="Choose a plan level and send a link letting this shop set its own email & password"
                >
                  <span className="inline-flex items-center gap-1">
                    <KeyRound size={13} />
                    Invite owner
                  </span>
                </Button>
                )}
                {canEdit && (
                <Button
                  variant="ghost"
                  className="text-xs px-3 py-1.5"
                  onClick={() => handleRemove(site.tenant_id)}
                  disabled={removingId === site.tenant_id}
                >
                  {removingId === site.tenant_id ? 'Removing…' : 'Remove'}
                </Button>
                )}
              </div>
            </div>
            )
          })}
        </Card>
      )}

      <div className="mt-6">
        <RegionsCard canEdit={canEdit} />
        <HqStaffCard canEdit={canEdit} currentUserId={sessionUserId ?? undefined} />
      </div>

      {showAdd && (
        <Modal title="Add shop" onClose={() => setShowAdd(false)}>
          <div className="space-y-4">
            <Select label="Mode" value={addMode} onChange={e => setAddMode(e.target.value as 'provision' | 'link')}>
              <option value="provision">New Minit shop (minit-{'{number}'})</option>
              <option value="link">Link existing tenant</option>
            </Select>
            {addMode === 'provision' ? (
              <>
                <Select
                  label="Shop type"
                  value={shopType}
                  onChange={e => setShopType(e.target.value as MinitShopType)}
                >
                  {MINIT_SHOP_TYPE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </Select>
                <Input label="Minit shop number" value={shopNumber} onChange={e => setShopNumber(e.target.value)} placeholder="3269" />
                <Input label="Shop name" value={tenantName} onChange={e => setTenantName(e.target.value)} placeholder="Chadstone" />
                <Input
                  label={shopType === 'mobile' ? 'Base address (optional)' : 'Address (optional)'}
                  value={businessAddress}
                  onChange={e => setBusinessAddress(e.target.value)}
                />
                <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                  {shopType === 'mobile'
                    ? 'Starts on Auto Key Basic and joins the mobile operator roll-up.'
                    : 'Starts on booking-only and joins the retail shops list.'}
                </p>

                <div className="pt-2" style={{ borderTop: '1px solid var(--ms-border)' }}>
                  <p className="text-xs font-semibold mb-1" style={{ color: 'var(--ms-text)' }}>
                    Owner contact (optional)
                  </p>
                  <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                    Fill these in and the shop gets its own owner login, so &ldquo;Invite owner&rdquo; reaches
                    them. Leave blank and it shares the HQ login until someone adds them.
                  </p>
                  <div className="space-y-3">
                    <Input
                      label="Owner name"
                      value={ownerName}
                      onChange={e => setOwnerName(e.target.value)}
                      placeholder="Jane Smith"
                    />
                    <Input
                      label="Owner email"
                      type="email"
                      value={ownerEmail}
                      onChange={e => setOwnerEmail(e.target.value)}
                      placeholder="jane@example.com"
                    />
                    <Input
                      label="Owner mobile"
                      type="tel"
                      value={ownerMobile}
                      onChange={e => setOwnerMobile(e.target.value)}
                      placeholder="0412 345 678"
                    />
                  </div>
                </div>
              </>
            ) : (
              <>
                <Input label="Tenant slug" value={linkSlug} onChange={e => setLinkSlug(e.target.value)} />
                <Input label="Owner email" value={linkEmail} onChange={e => setLinkEmail(e.target.value)} />
                <Input label="Shop number (optional)" value={shopNumber} onChange={e => setShopNumber(e.target.value)} />
              </>
            )}
            {error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}
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

      {openTarget && (
        <Modal title={`Open ${formatTenantLabel(openTarget.tenant_name, openTarget.shop_number)}`} onClose={() => setOpenTarget(null)}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              You'll work inside this shop as its owner for up to 30 minutes. The shop sees the visit in its inbox — say why.
            </p>
            <Input
              label="Reason (shown to the shop)"
              value={openReason}
              onChange={e => setOpenReason(e.target.value)}
              placeholder="e.g. Checking the booking screen config"
              maxLength={300}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setOpenTarget(null)}>Cancel</Button>
              <Button
                onClick={() => {
                  const target = openTarget
                  setOpenTarget(null)
                  void enterShop(target.tenant_id, '/minit/accounts', openReason.trim() || undefined)
                }}
                disabled={entering === openTarget.tenant_id}
              >
                Open shop
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {inviteTarget && (
        <Modal title="Invite owner" onClose={() => setInviteTarget(null)}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              Choose the account level for {formatTenantLabel(inviteTarget.tenant_name, inviteTarget.shop_number)}{' '}
              before sending the login invite to <strong>{inviteTarget.owner_email}</strong>.
            </p>
            <Select
              label="Account level"
              value={invitePlanCode}
              onChange={e => setInvitePlanCode(e.target.value)}
            >
              <option value="">Keep current plan ({inviteTarget.plan_code})</option>
              {MINIT_INVITE_PLAN_OPTIONS.map(opt => (
                <option key={opt.code} value={opt.code}>{opt.label}</option>
              ))}
            </Select>
            {error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setInviteTarget(null)}>Cancel</Button>
              <Button onClick={sendInvite} disabled={inviteMut.isPending}>
                {inviteMut.isPending ? 'Sending…' : 'Send invite'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {inviteResult && (
        <Modal title="Invite sent" onClose={() => setInviteResult(null)}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              For {inviteResult.tenant_name}
              {inviteResult.shop_number ? ` (#${inviteResult.shop_number})` : ''} — account level{' '}
              <strong>{MINIT_INVITE_PLAN_OPTIONS.find(o => o.code === inviteResult.plan_code)?.label ?? inviteResult.plan_code}</strong>.
              It lets <strong>{inviteResult.owner_email}</strong> set their own email &amp; password — it expires{' '}
              {new Date(inviteResult.expires_at).toLocaleDateString()}.
            </p>
            {inviteResult.email_sent || inviteResult.sms_sent ? (
              <p className="text-sm rounded-lg px-3 py-2" style={{ color: '#1A6A3A', backgroundColor: '#EBF8EF' }}>
                Sent to {inviteResult.owner_email}
                {inviteResult.sms_sent ? ` and ${inviteResult.owner_mobile} by text` : ''} automatically.
              </p>
            ) : (
              <p className="text-sm rounded-lg px-3 py-2" style={{ color: '#8A5010', backgroundColor: '#FFF8EE' }}>
                Couldn&rsquo;t send automatically{inviteResult.owner_mobile ? '' : ' (no mobile on file for SMS)'} — share
                the link below yourself.
              </p>
            )}
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
