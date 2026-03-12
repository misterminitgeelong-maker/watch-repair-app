import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { createUser, getBillingLimits, getBillingPortalUrl, listUsers, type PlanCode, type TenantUser, updateTenantPlan, updateUser } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { isChecklistDismissed, setChecklistDismissed } from '@/lib/onboarding'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

type UserRole = 'owner' | 'manager' | 'tech' | 'intake'

const ROLE_OPTIONS: UserRole[] = ['owner', 'manager', 'tech', 'intake']

const PLAN_BUNDLES = [
  { code: 'shoe' as PlanCode, name: 'Shoe', modules: ['Shoe repairs', 'Customers', 'Invoices'] },
  { code: 'watch' as PlanCode, name: 'Watch', modules: ['Watch repairs', 'Customers', 'Invoices'] },
  { code: 'auto_key' as PlanCode, name: 'Auto Key', modules: ['Auto key jobs', 'Customers', 'Invoices'] },
  { code: 'enterprise' as PlanCode, name: 'Enterprise', modules: ['Watch repairs', 'Shoe repairs', 'Auto key jobs', 'Reports', 'Multi-site'] },
]

function AddUserModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'manager' as UserRole })
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: unknown) => {
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(msg || 'Could not create account. Only owner accounts can create users.')
    },
  })

  return (
    <Modal title="Add Team Account" onClose={onClose}>
      <div className="space-y-3">
        <Input
          label="Full Name *"
          value={form.full_name}
          onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
          placeholder="Workshop Manager"
          autoFocus
        />
        <Input
          label="Email *"
          type="email"
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          placeholder="manager@yourshop.com"
        />
        <Input
          label="Password *"
          type="password"
          value={form.password}
          onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
          placeholder="At least 8 characters"
        />
        <Select
          label="Role"
          value={form.role}
          onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserRole }))}
        >
          {ROLE_OPTIONS.map((role) => (
            <option key={role} value={role}>{role}</option>
          ))}
        </Select>

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            onClick={() => mut.mutate()}
            disabled={!form.full_name || !form.email || form.password.length < 8 || mut.isPending}
          >
            {mut.isPending ? 'Creating…' : 'Create Account'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function AccountsPage() {
  const { role, planCode, tenantId, refreshSession } = useAuth()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState<Record<string, { role: UserRole; is_active: boolean }>>({})
  const [selectedPlanCode, setSelectedPlanCode] = useState<PlanCode>(planCode)
  const [checklistHidden, setChecklistHidden] = useState(false)

  const canManagePlan = role === 'owner' || role === 'platform_admin'

  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then((r) => r.data),
  })

  const mut = useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: { role?: UserRole; is_active?: boolean } }) =>
      updateUser(userId, payload),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err: unknown) => {
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(msg || 'Could not update account. Only owner accounts can manage users.')
    },
  })

  const planMut = useMutation({
    mutationFn: (nextPlan: PlanCode) => updateTenantPlan(nextPlan),
    onSuccess: async () => {
      setError('')
      await refreshSession()
    },
    onError: (err: unknown) => {
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(msg || 'Could not update plan. Only owner accounts can manage billing plans.')
    },
  })

  const filtered = (users ?? []).filter((u) =>
    [u.full_name, u.email, u.role].join(' ').toLowerCase().includes(search.toLowerCase())
  )

  useEffect(() => {
    setSelectedPlanCode(planCode)
  }, [planCode])

  useEffect(() => {
    setChecklistHidden(isChecklistDismissed(tenantId))
  }, [tenantId])

  function currentDraft(u: TenantUser) {
    return drafts[u.id] ?? { role: u.role as UserRole, is_active: u.is_active }
  }

  function saveUser(u: TenantUser) {
    const d = currentDraft(u)
    const payload: { role?: UserRole; is_active?: boolean } = {}
    if (d.role !== u.role) payload.role = d.role
    if (d.is_active !== u.is_active) payload.is_active = d.is_active
    if (!payload.role && payload.is_active === undefined) return
    mut.mutate({ userId: u.id, payload })
  }

  return (
    <div>
      <PageHeader title="Team Accounts" action={<Button onClick={() => setShowAdd(true)}><Plus size={16} />Add Account</Button>} />
      {showAdd && <AddUserModal onClose={() => setShowAdd(false)} />}

      <Card className="mb-5 p-4 sm:p-5">
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
          Plan bundles
        </p>
        <div className="mt-3 rounded-xl border p-3 sm:flex sm:items-center sm:justify-between sm:gap-3" style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-surface)' }}>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>
              Active plan: {PLAN_BUNDLES.find(p => p.code === planCode)?.name ?? planCode}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>
              Change this to switch enabled modules for your tenant.
            </p>
          </div>
          <div className="mt-3 flex gap-2 sm:mt-0 sm:w-[360px]">
            <Select
              value={selectedPlanCode}
              onChange={e => setSelectedPlanCode(e.target.value as PlanCode)}
              disabled={!canManagePlan || planMut.isPending}
              className="flex-1"
            >
              {PLAN_BUNDLES.map(bundle => (
                <option key={bundle.code} value={bundle.code}>{bundle.name}</option>
              ))}
            </Select>
            <Button
              onClick={() => planMut.mutate(selectedPlanCode)}
              disabled={!canManagePlan || selectedPlanCode === planCode || planMut.isPending}
            >
              {planMut.isPending ? 'Saving…' : 'Save Plan'}
            </Button>
          </div>
        </div>
        {!canManagePlan && (
          <p className="text-xs mt-2" style={{ color: 'var(--cafe-text-muted)' }}>
            Only owner accounts can change plans.
          </p>
        )}
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {PLAN_BUNDLES.map(bundle => (
            <div
              key={bundle.code}
              className="rounded-xl border p-3"
              style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-bg)' }}
            >
              <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>{bundle.name}</p>
              <p className="mt-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{bundle.modules.join(' · ')}</p>
            </div>
          ))}
        </div>
      </Card>

      <BillingCard />

      <Card className="mb-5 p-4 sm:p-5">
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
          Onboarding checklist
        </p>
        <p className="text-sm mt-2" style={{ color: 'var(--cafe-text-mid)' }}>
          Dashboard checklist is currently <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{checklistHidden ? 'hidden' : 'visible'}</span>.
        </p>
        <div className="mt-3 flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setChecklistDismissed(tenantId, false)
              setChecklistHidden(false)
            }}
          >
            Reset / Show Checklist
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setChecklistDismissed(tenantId, true)
              setChecklistHidden(true)
            }}
          >
            Dismiss Checklist
          </Button>
        </div>
      </Card>

      <div className="mb-5 relative w-full max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
        <input
          className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1px solid var(--cafe-border-2)',
            color: 'var(--cafe-text)',
          }}
          placeholder="Search accounts…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No team accounts found." /> : (
            <>
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
                {filtered.map((u) => {
                  const d = currentDraft(u)
                  return (
                    <div key={u.id} className="p-4 space-y-2">
                      <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>{u.full_name}</p>
                      <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{u.email}</p>
                      <div className="grid grid-cols-2 gap-2">
                        <Select value={d.role} onChange={(e) => setDrafts((m) => ({ ...m, [u.id]: { ...d, role: e.target.value as UserRole } }))}>
                          {ROLE_OPTIONS.map((role) => (
                            <option key={role} value={role}>{role}</option>
                          ))}
                        </Select>
                        <Select value={d.is_active ? 'active' : 'inactive'} onChange={(e) => setDrafts((m) => ({ ...m, [u.id]: { ...d, is_active: e.target.value === 'active' } }))}>
                          <option value="active">Active</option>
                          <option value="inactive">Inactive</option>
                        </Select>
                      </div>
                      <Button className="w-full justify-center" variant="secondary" onClick={() => saveUser(u)} disabled={mut.isPending}>
                        {mut.isPending ? 'Saving…' : 'Save Changes'}
                      </Button>
                    </div>
                  )
                })}
              </div>

              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['Name', 'Email', 'Role', 'Status', 'Actions'].map((h) => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u, i) => {
                    const d = currentDraft(u)
                    return (
                      <tr key={u.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                        <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text)' }}>{u.full_name}</td>
                        <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{u.email}</td>
                        <td className="px-5 py-3.5">
                          <Select value={d.role} onChange={(e) => setDrafts((m) => ({ ...m, [u.id]: { ...d, role: e.target.value as UserRole } }))}>
                            {ROLE_OPTIONS.map((role) => (
                              <option key={role} value={role}>{role}</option>
                            ))}
                          </Select>
                        </td>
                        <td className="px-5 py-3.5">
                          <Select value={d.is_active ? 'active' : 'inactive'} onChange={(e) => setDrafts((m) => ({ ...m, [u.id]: { ...d, is_active: e.target.value === 'active' } }))}>
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                          </Select>
                        </td>
                        <td className="px-5 py-3.5">
                          <Button variant="secondary" onClick={() => saveUser(u)} disabled={mut.isPending}>
                            {mut.isPending ? 'Saving…' : 'Save'}
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </>
          )}
        </Card>
      )}
    </div>
  )
}

function BillingCard() {
  const { data: billing } = useQuery({
    queryKey: ['billing-limits'],
    queryFn: () => getBillingLimits().then(r => r.data),
  })

  const [portalLoading, setPortalLoading] = useState(false)
  const [portalError, setPortalError] = useState('')

  async function openPortal() {
    setPortalLoading(true)
    setPortalError('')
    try {
      const { data } = await getBillingPortalUrl()
      window.open(data.url, '_blank', 'noopener')
    } catch {
      setPortalError('Could not open billing portal. Ensure Stripe is configured.')
    } finally {
      setPortalLoading(false)
    }
  }

  if (!billing) return null

  const { plan_code, limits, usage, stripe_configured, stripe_subscription_id } = billing

  function UsageRow({ label, used, max }: { label: string; used: number; max: number }) {
    const unlimited = max === 0
    const pct = unlimited ? 0 : Math.min(Math.round((used / max) * 100), 100)
    const nearLimit = !unlimited && pct >= 80
    return (
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span style={{ color: 'var(--cafe-text-mid)' }}>{label}</span>
          <span style={{ color: nearLimit ? '#8B3A3A' : 'var(--cafe-text-muted)' }}>
            {used} {unlimited ? '(unlimited)' : `/ ${max}`}
          </span>
        </div>
        {!unlimited && (
          <div className="h-1.5 rounded overflow-hidden" style={{ backgroundColor: 'var(--cafe-bg)' }}>
            <div
              className="h-full rounded"
              style={{
                width: `${pct}%`,
                backgroundColor: pct >= 90 ? '#8B3A3A' : pct >= 70 ? '#9B4E0F' : '#2A6B65',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        )}
      </div>
    )
  }

  return (
    <Card className="mb-5 p-4 sm:p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
          Plan usage — {plan_code}
        </p>
        {stripe_configured && stripe_subscription_id && (
          <button
            onClick={openPortal}
            disabled={portalLoading}
            className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
            style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: portalLoading ? 0.6 : 1 }}
          >
            {portalLoading ? 'Opening…' : 'Manage Billing'}
          </button>
        )}
      </div>

      <div className="space-y-3">
        <UsageRow label="Team accounts" used={usage.users} max={limits.max_users} />
        {limits.max_repair_jobs > 0 || usage.repair_jobs > 0
          ? <UsageRow label="Watch repair jobs" used={usage.repair_jobs} max={limits.max_repair_jobs} />
          : null}
        {limits.max_shoe_jobs > 0 || usage.shoe_jobs > 0
          ? <UsageRow label="Shoe repair jobs" used={usage.shoe_jobs} max={limits.max_shoe_jobs} />
          : null}
        {limits.max_auto_key_jobs > 0 || usage.auto_key_jobs > 0
          ? <UsageRow label="Auto key jobs" used={usage.auto_key_jobs} max={limits.max_auto_key_jobs} />
          : null}
      </div>

      {portalError && (
        <p className="text-xs mt-3" style={{ color: '#C96A5A' }}>{portalError}</p>
      )}

      {stripe_configured && !stripe_subscription_id && (
        <p className="text-xs mt-3" style={{ color: 'var(--cafe-text-muted)' }}>
          No active Stripe subscription. Contact support or configure billing to subscribe.
        </p>
      )}
    </Card>
  )
}
