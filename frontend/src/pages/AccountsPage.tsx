import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Trash2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  createBillingCheckoutForPlan,
  createStripeConnectAccountLink,
  createUser,
  deleteUser,
  getApiErrorMessage,
  getBillingLimits,
  isDuplicateTenantUserEmailError,
  getBillingPortalUrl,
  listUsers,
  refreshStripeConnectStatus,
  type PlanCode,
  type TenantUser,
  updateTenantPlan,
  updateUser,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { useTheme, type Theme } from '@/context/ThemeContext'
import { isChecklistDismissed, setChecklistDismissed } from '@/lib/onboarding'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

type UserRole = 'owner' | 'manager' | 'tech' | 'intake'

const ROLE_OPTIONS: UserRole[] = ['owner', 'manager', 'tech', 'intake']

type PlanBundle = {
  code: PlanCode
  name: string
  monthlyLabel: string
  modules: string[]
  summary: string
}

const PLAN_BUNDLES: PlanBundle[] = [
  {
    code: 'basic_watch',
    name: 'Basic - Watch',
    monthlyLabel: '$40/mo',
    modules: ['Watch repairs', 'Reports', 'Customers', 'Invoices'],
    summary: '1 service tab included',
  },
  {
    code: 'basic_shoe',
    name: 'Basic - Shoe',
    monthlyLabel: '$40/mo',
    modules: ['Shoe repairs', 'Reports', 'Customers', 'Invoices'],
    summary: '1 service tab included',
  },
  {
    code: 'basic_auto_key',
    name: 'Basic - Mobile Services',
    monthlyLabel: '$40/mo',
    modules: ['Mobile Services jobs', 'Reports', 'Customers', 'Invoices'],
    summary: '1 service tab included',
  },
  {
    code: 'basic_watch_shoe',
    name: 'Basic +1 Tab (Watch + Shoe)',
    monthlyLabel: '$55/mo',
    modules: ['Watch repairs', 'Shoe repairs', 'Reports', 'Customers', 'Invoices'],
    summary: '2 service tabs',
  },
  {
    code: 'basic_watch_auto_key',
    name: 'Basic +1 Tab (Watch + Mobile Services)',
    monthlyLabel: '$55/mo',
    modules: ['Watch repairs', 'Mobile Services jobs', 'Reports', 'Customers', 'Invoices'],
    summary: '2 service tabs',
  },
  {
    code: 'basic_shoe_auto_key',
    name: 'Basic +1 Tab (Shoe + Mobile Services)',
    monthlyLabel: '$55/mo',
    modules: ['Shoe repairs', 'Mobile Services jobs', 'Reports', 'Customers', 'Invoices'],
    summary: '2 service tabs',
  },
  {
    code: 'pro',
    name: 'Pro',
    monthlyLabel: '$80/mo',
    modules: ['All service tabs', 'Reports', 'Customer accounts', 'Multi-site', 'Priority access'],
    summary: 'Full app access',
  },
]

function AddUserModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'manager' as UserRole })
  const [error, setError] = useState<string | 'duplicate_email' | null>(null)

  const mut = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: unknown) => {
      if (isDuplicateTenantUserEmailError(err)) {
        setError('duplicate_email')
        return
      }
      setError(getApiErrorMessage(err, 'Could not create account. Only owner accounts can create users.'))
    },
  })

  return (
    <Modal title="Add Team Account" onClose={onClose}>
      <div className="space-y-3">
        <Input
          label="Full Name *"
          value={form.full_name}
          onChange={(e) => { setError(null); setForm((f) => ({ ...f, full_name: e.target.value })) }}
          placeholder="Workshop Manager"
          autoFocus
        />
        <Input
          label="Email *"
          type="email"
          value={form.email}
          onChange={(e) => { setError(null); setForm((f) => ({ ...f, email: e.target.value })) }}
          placeholder="manager@yourshop.com"
        />
        <Input
          label="Password *"
          type="password"
          value={form.password}
          onChange={(e) => { setError(null); setForm((f) => ({ ...f, password: e.target.value })) }}
          placeholder="At least 8 characters"
        />
        <Select
          label="Role"
          value={form.role}
          onChange={(e) => { setError(null); setForm((f) => ({ ...f, role: e.target.value as UserRole })) }}
        >
          {ROLE_OPTIONS.map((role) => (
            <option key={role} value={role}>{role}</option>
          ))}
        </Select>

        {error === 'duplicate_email' && (
          <div className="text-sm space-y-2 rounded-lg border px-3 py-2" style={{ borderColor: 'var(--ms-border-strong)', color: '#C96A5A' }}>
            <p className="font-medium" style={{ color: 'var(--ms-text)' }}>This email is already on your team</p>
            <p style={{ color: 'var(--ms-text-muted)' }}>
              Close this dialog and find them in the table on this page to edit role, password, or status. Technicians also appear under{' '}
              <Link to="/auto-key/team" className="font-medium underline" style={{ color: 'var(--ms-accent)' }} onClick={onClose}>Mobile Services → Team</Link>.
            </p>
          </div>
        )}
        {error && error !== 'duplicate_email' && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            onClick={() => { setError(null); mut.mutate() }}
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
  const { role, planCode, tenantId, refreshSession, sessionUserId } = useAuth()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<TenantUser | null>(null)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState<Record<string, { role: UserRole; is_active: boolean }>>({})
  const [selectedPlanCode, setSelectedPlanCode] = useState<PlanCode>(planCode)
  const [checklistHidden, setChecklistHidden] = useState(false)
  const [showAllPlans, setShowAllPlans] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const billingStatus = searchParams.get('billing') as 'success' | 'cancelled' | null

  useEffect(() => {
    if (billingStatus === 'success') {
      void refreshSession()
    }
  }, [billingStatus])

  function dismissBillingBanner() {
    const next = new URLSearchParams(searchParams)
    next.delete('billing')
    setSearchParams(next, { replace: true })
  }

  const canManagePlan = role === 'owner' || role === 'platform_admin'

  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then((r) => r.data),
  })

  const { data: billing } = useQuery({
    queryKey: ['billing-limits'],
    queryFn: () => getBillingLimits().then(r => r.data),
  })

  const ownerCount = (users ?? []).filter((u) => u.role === 'owner').length

  function rowIsOnlyRemainingOwner(u: TenantUser) {
    return u.role === 'owner' && ownerCount <= 1
  }

  function canDeleteUserRow(u: TenantUser) {
    if (!canManagePlan || !sessionUserId) return false
    if (u.id === sessionUserId) return false
    if (rowIsOnlyRemainingOwner(u)) return false
    return true
  }

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

  const deleteMut = useMutation({
    mutationFn: (userId: string) => deleteUser(userId),
    onSuccess: (_, userId) => {
      setError('')
      setDeleteTarget(null)
      setDrafts((m) => {
        const next = { ...m }
        delete next[userId]
        return next
      })
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err: unknown) => {
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(msg || 'Could not delete account. Only owner accounts can remove users.')
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

  const stripePlanCheckoutMut = useMutation({
    mutationFn: (nextPlan: PlanCode) => createBillingCheckoutForPlan(nextPlan),
    onSuccess: ({ data }) => {
      setError('')
      window.open(data.checkout_url, '_blank', 'noopener')
    },
    onError: (err: unknown) => {
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(msg || 'Could not open Stripe checkout. Confirm Stripe price IDs are configured.')
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

  const stripeConfigured = Boolean(billing?.stripe_configured)
  const usage = billing?.usage
  const limits = billing?.limits
  const atOrNearLimit = limits && usage && (
    (limits.max_users > 0 && usage.users >= limits.max_users) ||
    (limits.max_repair_jobs > 0 && usage.repair_jobs >= limits.max_repair_jobs) ||
    (limits.max_shoe_jobs > 0 && usage.shoe_jobs >= limits.max_shoe_jobs) ||
    (limits.max_auto_key_jobs > 0 && usage.auto_key_jobs >= limits.max_auto_key_jobs)
  )

  return (
    <div>
      <PageHeader title="Account Settings" />
      {showAdd && <AddUserModal onClose={() => setShowAdd(false)} />}
      {deleteTarget && (
        <Modal title="Delete team account" onClose={() => { if (!deleteMut.isPending) setDeleteTarget(null) }}>
          <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
            Permanently remove{' '}
            <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{deleteTarget.full_name}</span>{' '}
            ({deleteTarget.email})? Assigned jobs will show as unassigned; history may no longer name this user.
          </p>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)} disabled={deleteMut.isPending}>Cancel</Button>
            <Button variant="danger" onClick={() => deleteMut.mutate(deleteTarget.id)} disabled={deleteMut.isPending}>
              {deleteMut.isPending ? 'Deleting…' : 'Delete account'}
            </Button>
          </div>
        </Modal>
      )}

      {billingStatus === 'success' && (
        <div className="mb-4 flex items-center justify-between rounded-lg px-4 py-3 text-sm" style={{ backgroundColor: '#EDF7F1', border: '1px solid #A8D5B8', color: '#1F6D4C' }}>
          <span><strong>Subscription active.</strong> Your plan has been updated — welcome to Mainspring.</span>
          <button onClick={dismissBillingBanner} className="ml-4 text-xs underline opacity-70 hover:opacity-100">Dismiss</button>
        </div>
      )}
      {billingStatus === 'cancelled' && (
        <div className="mb-4 flex items-center justify-between rounded-lg px-4 py-3 text-sm" style={{ backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA', color: '#C96A5A' }}>
          <span>Checkout was cancelled. Your plan has not changed.</span>
          <button onClick={dismissBillingBanner} className="ml-4 text-xs underline opacity-70 hover:opacity-100">Dismiss</button>
        </div>
      )}

      {atOrNearLimit && (
        <Card className="mb-4 p-4 border-amber-200" style={{ borderWidth: 1, backgroundColor: '#FFFBEB' }}>
          <p className="text-sm font-medium" style={{ color: '#92400E' }}>Plan limit reached</p>
          <p className="text-xs mt-1" style={{ color: '#B45309' }}>Upgrade to Pro for unlimited users and jobs, or add more capacity on your current plan.</p>
          {canManagePlan && stripeConfigured && (
            <Button className="mt-3" onClick={() => stripePlanCheckoutMut.mutate('pro')} disabled={stripePlanCheckoutMut.isPending}>
              {stripePlanCheckoutMut.isPending ? 'Opening…' : 'Upgrade to Pro'}
            </Button>
          )}
        </Card>
      )}


      <Card className="mb-5 p-4 sm:p-5">
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--ms-text-muted)' }}>
          Pricing and plan access
        </p>
        <div className="mt-3 rounded-xl border p-3 sm:flex sm:items-center sm:justify-between sm:gap-3" style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)' }}>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
              Active plan: {PLAN_BUNDLES.find(p => p.code === planCode)?.name ?? planCode} ({PLAN_BUNDLES.find(p => p.code === planCode)?.monthlyLabel ?? 'Custom'})
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
              Basic: $40/month (1 tab) or $55/month (2 tabs). Pro: $80/month — all 3 service tabs, multi-site, customer accounts. Each extra shop location adds $25/month.
            </p>
          </div>
          <div className="mt-3 flex gap-2 sm:mt-0 sm:w-[360px]">
            <Select
              value={selectedPlanCode}
              onChange={e => setSelectedPlanCode(e.target.value as PlanCode)}
              disabled={!canManagePlan || planMut.isPending || stripePlanCheckoutMut.isPending}
              className="flex-1"
            >
              {PLAN_BUNDLES.map(bundle => (
                <option key={bundle.code} value={bundle.code}>{bundle.name}</option>
              ))}
            </Select>
            {stripeConfigured ? (
              <Button
                onClick={() => stripePlanCheckoutMut.mutate(selectedPlanCode)}
                disabled={!canManagePlan || selectedPlanCode === planCode || stripePlanCheckoutMut.isPending}
              >
                {stripePlanCheckoutMut.isPending ? 'Opening…' : 'Checkout'}
              </Button>
            ) : (
              <Button
                onClick={() => planMut.mutate(selectedPlanCode)}
                disabled={!canManagePlan || selectedPlanCode === planCode || planMut.isPending}
              >
                {planMut.isPending ? 'Saving…' : 'Save Plan'}
              </Button>
            )}
          </div>
        </div>
        {stripeConfigured && (
          <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>
            Stripe is active. Use Checkout to subscribe or change plan; access updates after Stripe confirms payment.
          </p>
        )}
        {!canManagePlan && (
          <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>
            Only owner accounts can change plans.
          </p>
        )}
        <div className="mt-3">
          <button
            className="text-xs font-medium underline"
            style={{ color: 'var(--ms-text-muted)' }}
            onClick={() => setShowAllPlans(v => !v)}
          >
            {showAllPlans ? 'Hide plan comparison' : 'Compare all plans'}
          </button>
          {showAllPlans && (
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
              {PLAN_BUNDLES.map(bundle => (
                <div
                  key={bundle.code}
                  className="rounded-xl border p-3"
                  style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)' }}
                >
                  <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>{bundle.name}</p>
                  <p className="mt-0.5 text-xs font-semibold" style={{ color: 'var(--ms-text-mid)' }}>{bundle.monthlyLabel}</p>
                  <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-muted)' }}>{bundle.summary}</p>
                  <p className="mt-2 text-xs" style={{ color: 'var(--ms-text-muted)' }}>{bundle.modules.join(' · ')}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <BillingCard />

      <StripeConnectCard />

      <div className="mb-4 flex items-center justify-between">
        <div className="relative w-full max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
          <input
            className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
            style={{
              backgroundColor: 'var(--ms-surface)',
              border: '1px solid var(--ms-border-strong)',
              color: 'var(--ms-text)',
            }}
            placeholder="Search accounts…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button onClick={() => setShowAdd(true)} className="ml-3 shrink-0"><Plus size={16} />Add Account</Button>
      </div>

      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}

      {isLoading ? <Spinner /> : (
        <Card className="mb-5">
          {filtered.length === 0 ? <EmptyState message="No team accounts found." /> : (
            <>
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--ms-border)' }}>
                {filtered.map((u) => {
                  const d = currentDraft(u)
                  return (
                    <div key={u.id} className="p-4 space-y-2">
                      <p className="font-medium" style={{ color: 'var(--ms-text)' }}>{u.full_name}</p>
                      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{u.email}</p>
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
                      <div className="flex gap-2">
                        <Button className="flex-1 justify-center" variant="secondary" onClick={() => saveUser(u)} disabled={mut.isPending}>
                          {mut.isPending ? 'Saving…' : 'Save Changes'}
                        </Button>
                        {canDeleteUserRow(u) && (
                          <Button
                            variant="danger"
                            className="justify-center px-3"
                            aria-label={`Delete ${u.full_name}`}
                            onClick={() => setDeleteTarget(u)}
                            disabled={deleteMut.isPending}
                          >
                            <Trash2 size={16} />
                          </Button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ms-border)' }}>
                    {['Name', 'Email', 'Role', 'Status', 'Actions'].map((h) => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--ms-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u, i) => {
                    const d = currentDraft(u)
                    return (
                      <tr key={u.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                        <td className="px-5 py-3.5" style={{ color: 'var(--ms-text)' }}>{u.full_name}</td>
                        <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{u.email}</td>
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
                          <div className="flex flex-wrap items-center gap-2">
                            <Button variant="secondary" onClick={() => saveUser(u)} disabled={mut.isPending}>
                              {mut.isPending ? 'Saving…' : 'Save'}
                            </Button>
                            {canDeleteUserRow(u) && (
                              <Button
                                variant="danger"
                                onClick={() => setDeleteTarget(u)}
                                disabled={deleteMut.isPending}
                                aria-label={`Delete ${u.full_name}`}
                              >
                                <Trash2 size={16} />
                              </Button>
                            )}
                          </div>
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

      <AppearanceCard />

      <Card className="mb-5 p-4 sm:p-5">
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--ms-text-muted)' }}>
          Onboarding checklist
        </p>
        <p className="text-sm mt-2" style={{ color: 'var(--ms-text-mid)' }}>
          Dashboard checklist is currently <span className="font-semibold" style={{ color: 'var(--ms-text)' }}>{checklistHidden ? 'hidden' : 'visible'}</span>.
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
    </div>
  )
}

function AppearanceCard() {
  const { theme, setTheme } = useTheme()
  const themes: { key: Theme; label: string; desc: string; swatches: string[] }[] = [
    { key: 'warm',    label: 'Refined Warmth', desc: 'Cream parchment, gold accent.',        swatches: ['#F5F1EC', '#FDFCF9', '#9A6E26', '#1C1510'] },
    { key: 'neutral', label: 'Steel & Amber',  desc: 'Cooler greys with deeper amber.',      swatches: ['#F6F5F3', '#FFFFFF', '#C07820', '#181614'] },
    { key: 'dark',    label: 'Night Workshop', desc: 'Low-light palette for late shifts.',   swatches: ['#121110', '#1C1A18', '#D4940A', '#0C0B0A'] },
    { key: 'minit',   label: 'Mister Minit',   desc: 'Brand red sidebar, clean white UI.',   swatches: ['#F4F4F4', '#FFFFFF', '#E31837', '#C41230'] },
  ]
  return (
    <Card className="mb-5 p-4 sm:p-5">
      <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--ms-text-muted)' }}>
        Appearance
      </p>
      <p className="text-sm mt-2" style={{ color: 'var(--ms-text-mid)' }}>
        Choose how Mainspring looks on this device. Stored locally.
      </p>
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {themes.map(t => {
          const active = theme === t.key
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTheme(t.key)}
              className="text-left rounded-lg p-4 transition-all"
              style={{
                backgroundColor: active ? 'var(--ms-accent-light)' : 'var(--ms-surface)',
                border: active ? '2px solid var(--ms-accent)' : '1px solid var(--ms-border)',
                boxShadow: active ? 'var(--ms-shadow)' : 'none',
              }}
              aria-pressed={active}
            >
              <div className="flex gap-1 mb-3">
                {t.swatches.map(c => (
                  <span
                    key={c}
                    className="w-6 h-6 rounded-full"
                    style={{ backgroundColor: c, border: '1px solid var(--ms-border)' }}
                  />
                ))}
              </div>
              <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>{t.label}</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{t.desc}</p>
              {active && (
                <p className="text-[10px] mt-2 font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-accent)' }}>
                  Active
                </p>
              )}
            </button>
          )
        })}
      </div>
    </Card>
  )
}

function StripeConnectCard() {
  const { role } = useAuth()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: billing } = useQuery({
    queryKey: ['billing-limits'],
    queryFn: () => getBillingLimits().then((r) => r.data),
  })

  const isOwner = role === 'owner' || role === 'platform_admin'
  const showMobilePayouts =
    Boolean(billing?.stripe_configured) &&
    (billing?.limits.max_auto_key_jobs ?? 0) > 0

  const refreshMut = useMutation({
    mutationFn: () => refreshStripeConnectStatus(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['billing-limits'] }),
  })

  const connectMut = useMutation({
    mutationFn: () => createStripeConnectAccountLink(),
    onSuccess: ({ data }) => {
      if (data.url) window.location.assign(data.url)
    },
  })

  useEffect(() => {
    const c = searchParams.get('connect')
    if (c !== 'return' && c !== 'refresh') return
    let cancelled = false
    void (async () => {
      try {
        await refreshStripeConnectStatus()
        if (!cancelled) await qc.invalidateQueries({ queryKey: ['billing-limits'] })
      } catch {
        /* refresh is best-effort after Stripe redirect */
      } finally {
        if (!cancelled) {
          const next = new URLSearchParams(searchParams)
          next.delete('connect')
          setSearchParams(next, { replace: true })
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- sync once when returning from Stripe

  if (!billing || !showMobilePayouts) return null

  const present = Boolean(billing.stripe_connect_account_present)
  const chargesOk = Boolean(billing.stripe_connect_charges_enabled)
  const statusLine = !present
    ? 'Connect your bank so customer invoice payments deposit to your workspace.'
    : chargesOk
      ? 'Card payments for Mobile Services invoices are enabled; funds route to your connected Stripe account.'
      : 'Finish Stripe onboarding to accept card payments on customer invoices.'

  return (
    <Card className="mb-5 p-4 sm:p-5">
      <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--ms-text-muted)' }}>
        Mobile invoice payouts (Stripe Connect)
      </p>
      <p className="text-sm mt-2" style={{ color: 'var(--ms-text-mid)' }}>
        {statusLine}
      </p>
      {isOwner && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            onClick={() => connectMut.mutate()}
            disabled={connectMut.isPending || refreshMut.isPending}
          >
            {connectMut.isPending ? 'Opening Stripe…' : present ? 'Continue setup' : 'Connect bank account'}
          </Button>
          <Button
            variant="secondary"
            onClick={() => refreshMut.mutate()}
            disabled={!present || refreshMut.isPending || connectMut.isPending}
          >
            {refreshMut.isPending ? 'Refreshing…' : 'Refresh status'}
          </Button>
        </div>
      )}
      {!isOwner && (
        <p className="text-xs mt-2" style={{ color: 'var(--ms-text-muted)' }}>
          Only an owner can complete Stripe Connect for this workspace.
        </p>
      )}
      {(connectMut.isError || refreshMut.isError) && (
        <p className="text-xs mt-2" style={{ color: '#C96A5A' }}>
          {getApiErrorMessage(connectMut.error ?? refreshMut.error, 'Could not reach Stripe. Try again.')}
        </p>
      )}
    </Card>
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
          <span style={{ color: 'var(--ms-text-mid)' }}>{label}</span>
          <span style={{ color: nearLimit ? '#8B3A3A' : 'var(--ms-text-muted)' }}>
            {used} {unlimited ? '(unlimited)' : `/ ${max}`}
          </span>
        </div>
        {!unlimited && (
          <div className="h-1.5 rounded overflow-hidden" style={{ backgroundColor: 'var(--ms-bg)' }}>
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
        <p className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--ms-text-muted)' }}>
          Plan usage — {plan_code}
        </p>
        {stripe_configured && stripe_subscription_id && (
          <button
            onClick={openPortal}
            disabled={portalLoading}
            className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: portalLoading ? 0.6 : 1 }}
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
          ? <UsageRow label="Mobile Services jobs" used={usage.auto_key_jobs} max={limits.max_auto_key_jobs} />
          : null}
      </div>

      {portalError && (
        <p className="text-xs mt-3" style={{ color: '#C96A5A' }}>{portalError}</p>
      )}

      {stripe_configured && !stripe_subscription_id && (
        <p className="text-xs mt-3" style={{ color: 'var(--ms-text-muted)' }}>
          No active Stripe subscription. Contact support or configure billing to subscribe.
        </p>
      )}
    </Card>
  )
}
