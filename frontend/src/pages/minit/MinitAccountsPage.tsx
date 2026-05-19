import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  formatTenantLabel,
  getApiErrorMessage,
  getMyParentAccount,
  linkTenantToParentAccount,
  provisionMinitShop,
  unlinkTenantFromParentAccount,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Card, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

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

  const { data, isLoading } = useQuery({
    queryKey: ['parent-account-me'],
    queryFn: () => getMyParentAccount().then(r => r.data),
  })

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
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
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
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not link shop.')),
  })

  const unlinkMut = useMutation({
    mutationFn: (tenantId: string) => unlinkTenantFromParentAccount(tenantId).then(r => r.data),
    onSuccess: () => {
      void refreshSession()
      qc.invalidateQueries({ queryKey: ['parent-account-me'] })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not remove shop.')),
  })

  if (isLoading) return <Spinner />

  const retailSites = (data?.sites ?? []).filter(s => isRetailShop(s.plan_code))
  const operators = (data?.sites ?? []).filter(s => !isRetailShop(s.plan_code))

  async function handleRemove(tenantId: string) {
    if (!window.confirm('Remove this shop from the network? The tenant is not deleted.')) return
    setRemovingId(tenantId)
    try {
      await unlinkMut.mutateAsync(tenantId)
    } finally {
      setRemovingId('')
    }
  }

  return (
    <div>
      <PageHeader
        title="Accounts"
        action={
          <Button onClick={() => { setError(''); setShowAdd(true) }}>+ Add shop</Button>
        }
      />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Add or remove shops on the Mister Minit network. Use Shops for day-to-day operational control.
      </p>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

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
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                  login {site.tenant_slug} · {site.plan_code}
                </p>
              </div>
              <Button
                variant="ghost"
                className="text-xs px-3 py-1.5"
                onClick={() => handleRemove(site.tenant_id)}
                disabled={removingId === site.tenant_id}
              >
                {removingId === site.tenant_id ? 'Removing…' : 'Remove'}
              </Button>
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
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                  {site.tenant_slug} · {site.plan_code}
                </p>
              </div>
              <Button
                variant="ghost"
                className="text-xs px-3 py-1.5"
                onClick={() => handleRemove(site.tenant_id)}
                disabled={removingId === site.tenant_id}
              >
                {removingId === site.tenant_id ? 'Removing…' : 'Remove'}
              </Button>
            </div>
          ))}
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
    </div>
  )
}
