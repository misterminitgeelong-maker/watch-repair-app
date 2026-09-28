import { useState } from 'react'
import { Link, NavLink, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useIsFetching, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, BarChart3, Clock, Download, RefreshCw, Search } from 'lucide-react'
import { deletePlatformTenant, forcePlatformTenantLogout, getApiErrorMessage, getPlatformReports, listPlatformActivity, listPlatformTenants, listPlatformUsers, markPlatformTenantPaid, setPlatformTenantBillingExempt, setPlatformTenantPlan, setPlatformTenantStatus, updatePlatformTenant } from '@/lib/api'
import { Card, EmptyState, Modal, Spinner } from '@/components/ui'
import { useAdminEnterShop } from '@/lib/adminImpersonation'
import { formatCents } from '@/lib/money'
import { isMinitHqTenantSlug } from '@/lib/minitProduct'
import './platformAdmin.css'

type Tab = 'overview' | 'shops' | 'billing' | 'audit' | 'users' | 'reports'
const TABS: Tab[] = ['overview', 'shops', 'billing', 'audit', 'users', 'reports']
const TAB_LABELS: Record<Tab, string> = { overview: 'Overview', shops: 'Shops', billing: 'Billing', audit: 'Audit log', users: 'Users', reports: 'Reports' }

const ACTIVITY_PAGE_SIZE = 100
const formatLabel = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
const shortId = (value?: string) => (value ? value.slice(0, 8) : '')

const TAB_DESCRIPTIONS: Record<Tab, string> = {
  overview: 'The big picture, and the details that deserve your attention.',
  shops: 'Every shop in your network. Find an account, check its status, and step inside.',
  billing: 'Keep subscriptions, trials, and payment follow-ups in view.',
  users: 'The people behind your network, with a direct route to their shop.',
  audit: 'A clear record of who did what, and when.',
  reports: 'Understand shop activity, adoption, and invoicing across your network.',
}

export default function PlatformAdminPage() {
  const params = useParams<{ tab?: string }>()
  const queryClient = useQueryClient()
  const refreshing = useIsFetching({ predicate: q => String(q.queryKey[0]).startsWith('platform-') }) > 0
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get('q') ?? ''
  const setSearch = (value: string) => setSearchParams(value ? { q: value } : {}, { replace: true })
  const raw = params.tab === 'activity' ? 'audit' : params.tab
  if (!raw || !(TABS as string[]).includes(raw)) return <Navigate to="/platform-admin/overview" replace />
  const tab = raw as Tab
  return (
    <div className="platform-console">
      <header className="console-heading">
        <div><div className="console-eyebrow">Mainspring / Platform administration</div>
          <h1>{TAB_LABELS[tab]}</h1><p>{TAB_DESCRIPTIONS[tab]}</p></div>
        <div className="flex items-center gap-3"><span className="console-badge">Platform workspace</span><button className="console-button" disabled={refreshing} onClick={() => void queryClient.invalidateQueries({ predicate: q => String(q.queryKey[0]).startsWith('platform-') })}><RefreshCw size={13} />{refreshing ? 'Refreshing…' : 'Refresh'}</button></div>
      </header>
      <nav className="console-nav" aria-label="Console sections">
        {TABS.map(t => <NavLink key={t} to={`/platform-admin/${t}`}>{TAB_LABELS[t]}</NavLink>)}
      </nav>
      {tab === 'overview' && <OverviewTab />}
      {tab === 'shops' && <ShopsTab key="shops" search={search} setSearch={setSearch} />}
      {tab === 'billing' && <BillingTab search={search} setSearch={setSearch} />}
      {tab === 'users' && <UsersTab search={search} setSearch={setSearch} />}
      {tab === 'audit' && <ActivityTab search={search} setSearch={setSearch} />}
      {tab === 'reports' && <ReportsTab />}
    </div>
  )
}

function OverviewTab() {
  const { data: tenants, isLoading, isError, refetch } = useQuery({ queryKey: ['platform-tenants'], queryFn: () => listPlatformTenants().then(r => r.data) })
  const reports = useQuery({ queryKey: ['platform-reports'], queryFn: () => getPlatformReports().then(r => r.data) })
  if (isLoading) return <Spinner />
  if (isError || !tenants) return <div className="console-error" role="alert">Could not load the overview. <button className="console-button" onClick={() => void refetch()}>Try again</button></div>
  const attention = tenants.filter(t => billingAttention(t))
  const recent = [...tenants].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).slice(0, 5)
  const plans = Object.entries(tenants.reduce<Record<string, number>>((acc, t) => { acc[t.plan_code] = (acc[t.plan_code] ?? 0) + 1; return acc }, {})).sort((a, b) => b[1] - a[1])
  return <>
    <section className="console-hero">
      <div><div className="console-eyebrow">Your network, in focus</div><h2>Your network.<br />At a glance.</h2>
        <p>{attention.length ? `${attention.length} shop${attention.length === 1 ? '' : 's'} need a billing review. Start there, or explore what’s happening across your network.` : 'Your billing review queue is clear. Explore your shops and see where your network is growing.'}</p>
        <Link className="console-button primary" to={attention.length ? '/platform-admin/billing' : '/platform-admin/shops'}>{attention.length ? 'Review billing' : 'Explore shops'}<ArrowUpRight size={15} /></Link>
      </div><div className="console-dial"><strong>{tenants.length.toLocaleString()}</strong><span>Shops connected</span></div>
    </section>
    <div className="console-metrics">
      <StatCard label="Total shops" value={String(tenants.length)} />
      <StatCard label="Active accounts" value={String(tenants.filter(t => t.is_active).length)} />
      <StatCard label="Users across shops" value={String(tenants.reduce((n, t) => n + t.user_count, 0))} />
      <StatCard label="Billing to review" value={String(attention.length)} />
    </div>
    <div className="console-grid">
      <section className="console-panel"><h2>Needs your attention</h2><p className="console-subtitle">Billing follow-ups, with a direct route to the shop.</p>
        {attention.length === 0 && <EmptyState message="No billing follow-ups right now." />}
        {attention.slice(0, 5).map(t => <div className="console-list-row" key={t.id}><div><strong>{t.name}</strong><small>{billingAttention(t)}</small></div><Link to={`/platform-admin/shops?q=${encodeURIComponent(t.slug)}`}>Review <span aria-hidden="true">↗</span></Link></div>)}
        {attention.length > 5 && <Link className="console-button" to="/platform-admin/billing">View all {attention.length} follow-ups</Link>}
      </section>
      <section className="console-panel"><h2>Network activity</h2><p className="console-subtitle">Shop operations over the last 30 days.</p>
        {reports.isLoading ? <Spinner /> : reports.data ? <><div className="console-list-row"><span>Jobs created</span><strong>{reports.data.totals.jobs_last_30_days.toLocaleString()}</strong></div><div className="console-list-row"><span>Invoices created</span><strong>{reports.data.totals.invoices_last_30_days.toLocaleString()}</strong></div><div className="console-list-row"><span>Shops with no activity in 7 days</span><strong>{reports.data.totals.health.tenants_no_activity_7_days}</strong></div><Link className="console-button mt-4" to="/platform-admin/reports">Explore reports <ArrowUpRight size={14} /></Link></> : <div role="alert">Activity is unavailable. <button className="console-button" onClick={() => void reports.refetch()}>Try again</button></div>}
      </section>
      <section className="console-panel"><h2>Latest additions</h2><p className="console-subtitle">The most recently created shop accounts.</p>
        {recent.length === 0 && <EmptyState message="No shops yet." />}
        {recent.map(t => <div className="console-list-row" key={t.id}><div className="console-shop"><span className="console-avatar" aria-hidden="true">{t.name.slice(0, 2).toUpperCase()}</span><div><strong>{t.name}</strong><small>{formatLabel(t.plan_code)} · {new Date(t.created_at).toLocaleDateString()}</small></div></div><Link to={`/platform-admin/shops?q=${encodeURIComponent(t.slug)}`}>View</Link></div>)}
      </section>
      <section className="console-panel"><h2>Your plan mix</h2><p className="console-subtitle">Account distribution across the platform.</p>
        {plans.length === 0 && <EmptyState message="Plan distribution appears when shops are added." />}
        {plans.map(([plan, count]) => <div key={plan}><div className="flex justify-between gap-3 text-xs"><span>{formatLabel(plan)}</span><strong>{count}</strong></div><div className="console-bar"><span style={{ width: `${count / tenants.length * 100}%` }} /></div></div>)}
      </section>
    </div>
  </>
}

function Pagination({ page, total, onChange }: { page: number; total: number; onChange: (page: number) => void }) {
  return <div className="console-pager"><span aria-live="polite">{total ? `${page * 25 + 1}–${Math.min((page + 1) * 25, total)} of ${total}` : '0 results'}</span><div><button className="console-button" disabled={page === 0} onClick={() => onChange(page - 1)}>Previous</button><button className="console-button" disabled={(page + 1) * 25 >= total} onClick={() => onChange(page + 1)}>Next</button></div></div>
}

/** Why a shop's billing needs a look, or null when it's fine. */
function billingAttention(t: { is_active: boolean; signup_payment_pending: boolean; billing_exempt?: boolean; subscription_status?: string | null; trial_end?: string | null }): string | null {
  if (t.billing_exempt) return null
  if (t.signup_payment_pending) return 'Signup payment pending'
  const status = (t.subscription_status || '').toLowerCase()
  if (status === 'past_due' || status === 'unpaid') return 'Payment failing'
  if (status === 'canceled' || status === 'incomplete_expired') return 'Subscription cancelled'
  if (status === 'trialing' && t.trial_end) {
    const days = Math.ceil((new Date(t.trial_end).getTime() - Date.now()) / 86_400_000)
    if (days <= 3) return days < 0 ? 'Trial ended' : `Trial ends in ${days} day${days === 1 ? '' : 's'}`
  }
  return null
}

function BillingTab({ search, setSearch }: { search: string; setSearch: (v: string) => void }) {
  const { data: tenants, isLoading, isError } = useQuery({
    queryKey: ['platform-tenants'],
    queryFn: () => listPlatformTenants().then(r => r.data),
  })
  const [onlyAttention, setOnlyAttention] = useState(true)
  const [page, setPage] = useState(0)
  if (isLoading) return <Spinner />
  if (isError || !tenants) return <EmptyState message="Could not load shops." />
  const q = search.trim().toLowerCase()
  const rows = tenants
    .map(t => ({ t, attention: billingAttention(t) }))
    .filter(({ t }) => !q || t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q))
    .filter(({ attention }) => !onlyAttention || attention !== null)
    .sort((a, b) => Number(b.attention !== null) - Number(a.attention !== null) || a.t.name.localeCompare(b.t.name))
  const currentPage = Math.min(page, Math.max(0, Math.ceil(rows.length / 25) - 1))
  const visible = rows.slice(currentPage * 25, (currentPage + 1) * 25)
  const counts = {
    attention: tenants.filter(t => billingAttention(t) !== null).length,
    paying: tenants.filter(t => (t.subscription_status || '') === 'active' && !t.billing_exempt).length,
    trialing: tenants.filter(t => (t.subscription_status || '') === 'trialing').length,
    exempt: tenants.filter(t => t.billing_exempt).length,
  }
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 mb-5 sm:grid-cols-4">
        <StatCard label="Need attention" value={String(counts.attention)} />
        <StatCard label="Paying" value={String(counts.paying)} />
        <StatCard label="On trial" value={String(counts.trialing)} />
        <StatCard label="Billing exempt" value={String(counts.exempt)} />
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <SearchBar value={search} onChange={v => { setSearch(v); setPage(0) }} placeholder="Search shops…" />
        <label className="mb-5 flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text-mid)' }}>
          <input type="checkbox" checked={onlyAttention} onChange={e => { setOnlyAttention(e.target.checked); setPage(0) }} />
          Only shops that need attention
        </label>
      </div>
      {rows.length === 0 ? (
        <EmptyState message={onlyAttention ? 'No billing problems right now.' : 'No shops match.'} />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: 'var(--ms-text-muted)' }}>
                <th className="text-left font-medium px-4 py-3">Shop</th>
                <th className="text-left font-medium px-4 py-3">Plan</th>
                <th className="text-left font-medium px-4 py-3">Subscription</th>
                <th className="text-left font-medium px-4 py-3">Trial ends</th>
                <th className="text-left font-medium px-4 py-3">Needs</th>
              </tr>
            </thead>
            <tbody>
              {visible.map(({ t, attention }) => (
                <tr key={t.id} style={{ borderTop: '1px solid var(--ms-border)' }}>
                  <td className="px-4 py-3">
                    <Link className="font-semibold underline underline-offset-4" to={`/platform-admin/shops?q=${encodeURIComponent(t.slug)}`}>{t.name}</Link>
                    <div className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{t.slug}{t.is_active ? '' : ' · suspended'}</div>
                  </td>
                  <td className="px-4 py-3">{formatLabel(t.plan_code)}</td>
                  <td className="px-4 py-3">
                    {t.billing_exempt ? 'Exempt' : t.subscription_status ? formatLabel(t.subscription_status) : t.has_stripe_subscription ? 'Unknown' : 'None'}
                  </td>
                  <td className="px-4 py-3">{t.trial_end ? new Date(t.trial_end).toLocaleDateString() : '—'}</td>
                  <td className="px-4 py-3" style={{ color: attention ? 'var(--ms-error)' : 'var(--ms-text-muted)' }}>{attention ?? 'OK'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <Pagination page={currentPage} total={rows.length} onChange={setPage} />
      <p className="mt-3 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
        Select a shop name to review its account, payment status, or plan.
      </p>
    </div>
  )
}

function SearchBar({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="mb-5 relative w-full max-w-md">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
      <input
        className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
        style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
        aria-label={placeholder}
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  )
}

function ShopsTab({ search, setSearch }: { search: string; setSearch: (v: string) => void }) {
  const queryClient = useQueryClient()
  const { data: tenants, isLoading, isError } = useQuery({
    queryKey: ['platform-tenants'],
    queryFn: () => listPlatformTenants().then(r => r.data),
  })
  const { enterShop, entering, error } = useAdminEnterShop()
  const [adminActionError, setAdminActionError] = useState('')
  const setStatus = useMutation({
    mutationFn: ({ tenantId, isActive, reason }: { tenantId: string; isActive: boolean; reason?: string }) =>
      setPlatformTenantStatus(tenantId, isActive, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-reports'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
      setAdminActionError('')
    },
    onError: () => setAdminActionError('Could not update shop status. Try again.'),
  })
  const forceLogout = useMutation({
    mutationFn: ({ tenantId, reason }: { tenantId: string; reason?: string }) =>
      forcePlatformTenantLogout(tenantId, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
      setAdminActionError('')
    },
    onError: () => setAdminActionError('Could not force logout users. Try again.'),
  })
  const deleteAccount = useMutation({
    mutationFn: (tenantId: string) => deletePlatformTenant(tenantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-reports'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
      setAdminActionError('')
    },
    onError: (err) => setAdminActionError(`Delete failed: ${getApiErrorMessage(err)}`),
  })
  const [planModal, setPlanModal] = useState<{ tenantId: string; name: string; currentPlan: string; options: string[]; minit: boolean } | null>(null)
  const [planModalValue, setPlanModalValue] = useState('')
  const [planModalReason, setPlanModalReason] = useState('')
  const [editModal, setEditModal] = useState<{ tenantId: string; name: string; slug: string } | null>(null)
  const [editName, setEditName] = useState('')
  const [editSlug, setEditSlug] = useState('')
  const [editOwnerEmail, setEditOwnerEmail] = useState('')
  const [editPassword, setEditPassword] = useState('')
  const [editError, setEditError] = useState('')
  const changePlan = useMutation({
    mutationFn: ({ tenantId, plan_code, reason }: { tenantId: string; plan_code: string; reason?: string }) =>
      setPlatformTenantPlan(tenantId, plan_code, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-reports'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
      setPlanModal(null)
      setPlanModalValue('')
      setPlanModalReason('')
      setAdminActionError('')
    },
    onError: () => setAdminActionError('Could not change plan. Try again.'),
  })
  const markPaid = useMutation({
    mutationFn: (tenantId: string) => markPlatformTenantPaid(tenantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
    },
    onError: () => setAdminActionError('Could not mark as paid. Try again.'),
  })
  const setBillingExempt = useMutation({
    mutationFn: ({ tenantId, exempt, reason }: { tenantId: string; exempt: boolean; reason?: string }) =>
      setPlatformTenantBillingExempt(tenantId, exempt, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
      setAdminActionError('')
    },
    onError: (err) => setAdminActionError(`Could not update billing status: ${getApiErrorMessage(err)}`),
  })
  const editTenant = useMutation({
    mutationFn: ({ tenantId, payload }: { tenantId: string; payload: { name?: string; slug?: string; owner_email?: string; new_password?: string } }) =>
      updatePlatformTenant(tenantId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })
      void queryClient.invalidateQueries({ queryKey: ['platform-activity'] })
      setEditModal(null)
      setEditName('')
      setEditSlug('')
      setEditOwnerEmail('')
      setEditPassword('')
      setEditError('')
    },
    onError: (err) => setEditError(getApiErrorMessage(err)),
  })
  const PLAN_OPTIONS = ['basic_watch', 'basic_shoe', 'basic_auto_key', 'basic_watch_shoe', 'basic_watch_auto_key', 'basic_shoe_auto_key', 'basic_all_tabs', 'pro']
  // Mister Minit shops only keep these; any other plan is switched back on their next sign-in.
  const planOptionsFor = (t: { slug: string; is_minit?: boolean }) =>
    !t.is_minit ? PLAN_OPTIONS : isMinitHqTenantSlug(t.slug) ? ['minit_hq'] : ['booking_only', 'basic_auto_key']
  function requireSlugConfirmation(shopName: string, shopSlug: string, actionLabel: string) {
    const typed = window.prompt(`Type shop slug "${shopSlug}" to ${actionLabel} ${shopName}:`, '') ?? ''
    if (typed.trim() !== shopSlug) {
      window.alert(`Confirmation failed. You must type "${shopSlug}" exactly.`)
      return false
    }
    return true
  }
  function handleToggleStatus(tenantId: string, name: string, slug: string, isActive: boolean) {
    const actionLabel = isActive ? 'suspend' : 'reactivate'
    if (!requireSlugConfirmation(name, slug, actionLabel)) return
    const reason = window.prompt(`${isActive ? 'Suspend' : 'Reactivate'} ${name} (optional reason):`, '')
    if (reason === null) return
    setStatus.mutate({ tenantId, isActive: !isActive, reason: reason.trim() || undefined })
  }
  function handleForceLogout(tenantId: string, name: string, slug: string) {
    if (!requireSlugConfirmation(name, slug, 'force logout users for')) return
    const reason = window.prompt(`Force logout all users in ${name}? Optional reason:`, '')
    if (reason === null) return
    forceLogout.mutate({ tenantId, reason: reason.trim() || undefined })
  }
  function handleDeleteAccount(tenantId: string, name: string, slug: string) {
    if (!requireSlugConfirmation(name, slug, 'permanently delete')) return
    const confirm2 = window.prompt(`This will DELETE ALL DATA for ${name}. Type DELETE to confirm:`, '') ?? ''
    if (confirm2.trim() !== 'DELETE') {
      window.alert('Cancelled — you must type DELETE exactly.')
      return
    }
    deleteAccount.mutate(tenantId)
  }
  function handleToggleBillingExempt(tenantId: string, name: string, slug: string, exempt: boolean) {
    // Turning billing off cancels the live Stripe subscription, so it gets the
    // same typed confirmation as the other destructive actions.
    if (exempt && !requireSlugConfirmation(name, slug, 'turn off billing for')) return
    const reason = window.prompt(
      exempt
        ? `Turn OFF billing for ${name} (they keep full access, any live Stripe subscription is canceled). Reason:`
        : `Turn billing back ON for ${name}? Reason (optional):`,
      '',
    )
    if (reason === null) return // cancelled
    setBillingExempt.mutate({ tenantId, exempt, reason: reason.trim() || undefined })
  }

  const [statusFilter, setStatusFilter] = useState('all')
  const [planFilter, setPlanFilter] = useState('all')
  const [sort, setSort] = useState('name')
  const [page, setPage] = useState(0)
  const [managedId, setManagedId] = useState<string | null>(null)
  const managed = tenants?.find(t => t.id === managedId)
  const plans = [...new Set((tenants ?? []).map(t => t.plan_code))].sort()
  const exactShop = tenants?.find(t => t.slug.toLowerCase() === search.trim().toLowerCase())
  const filtered = (tenants ?? []).filter(t =>
    (!exactShop || t.id === exactShop.id) && [t.name, t.slug, t.plan_code].join(' ').toLowerCase().includes(search.trim().toLowerCase()) &&
    (planFilter === 'all' || t.plan_code === planFilter) &&
    (statusFilter === 'all' || (statusFilter === 'active' && t.is_active) || (statusFilter === 'suspended' && !t.is_active) || (statusFilter === 'attention' && billingAttention(t) !== null))
  ).sort((a, b) => sort === 'newest' ? Date.parse(b.created_at) - Date.parse(a.created_at) : a.name.localeCompare(b.name))
  const currentPage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 25) - 1))
  const visible = filtered.slice(currentPage * 25, (currentPage + 1) * 25)
  const pending = setStatus.isPending || forceLogout.isPending || deleteAccount.isPending || markPaid.isPending || setBillingExempt.isPending

  return (
    <>
      <div className="console-toolbar">
        <SearchBar value={search} onChange={v => { setSearch(v); setPage(0) }} placeholder="Search shops or plan…" />
        <select aria-label="Filter shop status" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(0) }}><option value="all">All statuses</option><option value="active">Active</option><option value="suspended">Suspended</option><option value="attention">Billing needs attention</option></select>
        <select aria-label="Filter shop plan" value={planFilter} onChange={e => { setPlanFilter(e.target.value); setPage(0) }}><option value="all">All plans</option>{plans.map(p => <option key={p} value={p}>{formatLabel(p)}</option>)}</select>
        <select aria-label="Sort shops" value={sort} onChange={e => { setSort(e.target.value); setPage(0) }}><option value="name">Name A–Z</option><option value="newest">Newest first</option></select>
      </div>
      <p className="console-subtitle">Enter a shop to provide support, or choose Manage for account and billing controls.</p>
      {error && <div className="console-error" role="alert">{error}</div>}
      {adminActionError && !managed && <div className="console-error" role="alert">{adminActionError}</div>}
      {isError ? <div className="console-error" role="alert">Could not load shops. <button className="console-button" onClick={() => void queryClient.invalidateQueries({ queryKey: ['platform-tenants'] })}>Try again</button></div> : isLoading ? <Spinner /> : <>
        <Card className="overflow-x-auto">
          {visible.length === 0 ? <EmptyState message="No shops match your search and filters." /> : <>
            <div className="md:hidden">{visible.map(t => <div className="p-4 border-b border-[var(--ms-border)]" key={t.id}><strong>{t.name}</strong><p className="console-subtitle">#{t.slug} · {formatLabel(t.plan_code)} · {t.is_active ? 'Active' : 'Suspended'}</p><div className="console-actions"><button className="console-button primary" disabled={!!entering} onClick={() => void enterShop(t.id)}>{entering === t.id ? 'Entering…' : 'Enter Shop'}</button><button className="console-button" onClick={() => { setManagedId(t.id); setAdminActionError('') }}>Manage</button></div></div>)}</div>
            <table className="w-full text-sm hidden md:table"><thead><tr>{['Shop', 'Plan', 'Users', 'Status', 'Created', 'Actions'].map(h => <th key={h} className="text-left px-5 py-4 text-[10px] uppercase tracking-widest font-semibold">{h}</th>)}</tr></thead><tbody>{visible.map(t => <tr key={t.id} className="border-t border-[var(--ms-border)]">
              <td className="px-5 py-4"><div className="console-shop"><span className="console-avatar" aria-hidden="true">{t.name.slice(0, 2).toUpperCase()}</span><div className="font-medium">{t.name}<p className="text-xs text-[var(--ms-text-muted)] mt-1">#{t.slug}</p></div></div></td>
              <td className="px-5 py-4 text-xs">{formatLabel(t.plan_code)}</td><td className="px-5 py-4">{t.user_count}</td>
              <td className="px-5 py-4"><span className={`console-badge ${!t.is_active ? 'warning' : ''}`}>{t.is_active ? 'Active' : 'Suspended'}</span>{billingAttention(t) && <p className="mt-2 text-xs text-[var(--ms-error)]">{billingAttention(t)}</p>}{t.billing_exempt && <p className="mt-1 text-xs text-[var(--ms-text-muted)]">Billing exempt</p>}</td>
              <td className="px-5 py-4 text-xs text-[var(--ms-text-muted)]">{new Date(t.created_at).toLocaleDateString()}</td>
              <td className="px-5 py-4"><div className="console-actions"><button className="console-button" disabled={!!entering} onClick={() => void enterShop(t.id)}>{entering === t.id ? 'Entering…' : 'Enter Shop'}<ArrowUpRight size={13} /></button><button className="console-button" aria-label={`Manage ${t.name}`} onClick={() => { setManagedId(t.id); setAdminActionError('') }}>Manage</button></div></td>
            </tr>)}</tbody></table>
          </>}
        </Card>
        <Pagination page={currentPage} total={filtered.length} onChange={setPage} />
      </>}
      {managed && !editModal && !planModal && <Modal title={`Manage ${managed.name}`} onClose={() => setManagedId(null)} closeDisabled={pending}>
        <div className="platform-console"><p className="console-subtitle">#{managed.slug} · {formatLabel(managed.plan_code)} · {managed.user_count} users</p>
          <div className="console-list-row"><span>Account</span><span className={`console-badge ${!managed.is_active ? 'warning' : ''}`}>{managed.is_active ? 'Active' : 'Suspended'}</span></div>
          <div className="console-list-row"><span>Billing</span><strong>{managed.billing_exempt ? 'Exempt' : billingAttention(managed) ?? formatLabel(managed.subscription_status || 'No subscription')}</strong></div>
          <p className="console-subtitle mt-4">Account changes apply to this shop. Turning billing off cancels its live subscription; deleting an account permanently removes its data.</p>
          {adminActionError && <div className="console-error" role="alert">{adminActionError}</div>}
          {error && <div className="console-error" role="alert">{error}</div>}
          <fieldset disabled={pending} className="console-management">{[managed].map(t => <div key={t.id} className="console-actions">
                        <button
                          onClick={() => void enterShop(t.id)}
                          disabled={!!entering}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
                          style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)', opacity: entering === t.id ? 0.6 : 1 }}
                        >
                          {entering === t.id ? 'Entering…' : 'Enter Shop'}
                        </button>
                        <button
                          onClick={() => {
                            handleToggleStatus(t.id, t.name, t.slug, t.is_active)
                          }}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
                        >
                          {t.is_active ? 'Suspend' : 'Reactivate'}
                        </button>
                        <button
                          onClick={() => {
                            handleForceLogout(t.id, t.name, t.slug)
                          }}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'transparent', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
                        >
                          Force Logout
                        </button>
                        <button
                          onClick={() => { setPlanModal({ tenantId: t.id, name: t.name, currentPlan: t.plan_code, options: planOptionsFor(t), minit: Boolean(t.is_minit) }); setPlanModalValue(t.plan_code) }}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'transparent', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
                        >
                          Change Plan
                        </button>
                        <button
                          onClick={() => handleToggleBillingExempt(t.id, t.name, t.slug, !t.billing_exempt)}
                          disabled={setBillingExempt.isPending}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={t.billing_exempt
                            ? { backgroundColor: 'transparent', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text-muted)' }
                            : { backgroundColor: '#E8F6EE', border: '1px solid #A8D5B5', color: '#1F6D4C' }}
                        >
                          {t.billing_exempt ? 'Turn Billing On' : 'Turn Billing Off'}
                        </button>
                        <button
                          onClick={() => { setEditModal({ tenantId: t.id, name: t.name, slug: t.slug }); setEditName(t.name); setEditSlug(t.slug); setEditOwnerEmail(''); setEditPassword(''); setEditError('') }}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'transparent', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text-muted)' }}
                        >
                          Edit
                        </button>
                        {t.signup_payment_pending && (
                          <button
                            onClick={() => markPaid.mutate(t.id)}
                            disabled={markPaid.isPending}
                            className="text-xs px-3 py-1.5 rounded-lg font-medium"
                            style={{ backgroundColor: '#E8F6EE', border: '1px solid #A8D5B5', color: '#1F6D4C' }}
                          >
                            Mark Paid
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteAccount(t.id, t.name, t.slug)}
                          disabled={deleteAccount.isPending}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'transparent', border: '1px solid #E8B4AA', color: 'var(--ms-error)' }}
                        >
                          Delete Account
                        </button>
          </div>)}</fieldset>
        </div>
      </Modal>}

      {/* Edit Shop Modal */}
      {editModal && (
        <Modal title={`Edit Shop — ${editModal.name}`} onClose={() => setEditModal(null)} closeDisabled={editTenant.isPending}>
          <div>
            <p className="text-xs mb-4" style={{ color: 'var(--ms-text-muted)' }}>Leave a field blank to keep its current value.</p>
            {editError && (
              <div className="mb-3 text-xs rounded-lg px-3 py-2" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
                {editError}
              </div>
            )}
            <label htmlFor="editName" className="block text-xs mb-1" style={{ color: 'var(--ms-text-muted)' }}>Shop name</label>
            <input
              className="w-full rounded-lg px-3 py-2.5 text-sm mb-3 outline-none"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              id="editName"
              value={editName}
              onChange={e => setEditName(e.target.value)}
              placeholder={editModal.name}
            />
            <label htmlFor="editSlug" className="block text-xs mb-1" style={{ color: 'var(--ms-text-muted)' }}>Shop slug (ID)</label>
            <input
              className="w-full rounded-lg px-3 py-2.5 text-sm mb-3 outline-none"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              id="editSlug"
              value={editSlug}
              onChange={e => setEditSlug(e.target.value.toLowerCase())}
              placeholder={editModal.slug}
            />
            <label htmlFor="editOwnerEmail" className="block text-xs mb-1" style={{ color: 'var(--ms-text-muted)' }}>Owner email (optional)</label>
            <input
              type="email"
              className="w-full rounded-lg px-3 py-2.5 text-sm mb-3 outline-none"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              id="editOwnerEmail"
              value={editOwnerEmail}
              onChange={e => setEditOwnerEmail(e.target.value)}
              placeholder="Leave blank to keep current"
            />
            <label htmlFor="editPassword" className="block text-xs mb-1" style={{ color: 'var(--ms-text-muted)' }}>New password (optional, min 8 chars)</label>
            <input
              type="password"
              className="w-full rounded-lg px-3 py-2.5 text-sm mb-4 outline-none"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              id="editPassword"
              value={editPassword}
              onChange={e => setEditPassword(e.target.value)}
              placeholder="Leave blank to keep current"
            />
            <div className="flex gap-2 justify-end">
              <button
                disabled={editTenant.isPending}
                onClick={() => { setEditModal(null); setEditError('') }}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              >
                Cancel
              </button>
              <button
                disabled={editTenant.isPending}
                onClick={() => {
                  const payload: { name?: string; slug?: string; owner_email?: string; new_password?: string } = {}
                  if (editName.trim() && editName.trim() !== editModal.name) payload.name = editName.trim()
                  if (editSlug.trim() && editSlug.trim() !== editModal.slug) payload.slug = editSlug.trim()
                  if (editOwnerEmail.trim()) payload.owner_email = editOwnerEmail.trim()
                  if (editPassword.trim()) payload.new_password = editPassword.trim()
                  if (Object.keys(payload).length === 0) { setEditError('No changes made.'); return }
                  editTenant.mutate({ tenantId: editModal.tenantId, payload })
                }}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: editTenant.isPending ? 0.6 : 1 }}
              >
                {editTenant.isPending ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Change Plan Modal */}
      {planModal && (
        <Modal title={`Change Plan — ${planModal.name}`} onClose={() => setPlanModal(null)} closeDisabled={changePlan.isPending}>
          <div>
            {adminActionError && <div role="alert" className="console-error">{adminActionError}</div>}
            <p className="text-xs mb-4" style={{ color: 'var(--ms-text-muted)' }}>Current: <strong>{planModal.currentPlan}</strong></p>
            <select
              className="w-full rounded-lg px-3 py-2.5 text-sm mb-3 outline-none"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              aria-label="New plan"
              value={planModalValue}
              onChange={e => setPlanModalValue(e.target.value)}
            >
              {!planModal.options.includes(planModal.currentPlan) && <option value={planModal.currentPlan}>{formatLabel(planModal.currentPlan)} (current)</option>}{planModal.options.map(p => <option key={p} value={p}>{formatLabel(p)}</option>)}
            </select>
            {planModal.minit && (
              <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                Mister Minit shop: shopfronts run on Booking Only and mobile vans on Basic Auto Key. Changing the plan does not move the shop between HQ&rsquo;s shop and van lists.
              </p>
            )}
            <input
              className="w-full rounded-lg px-3 py-2.5 text-sm mb-4 outline-none"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              aria-label="Reason (optional)"
              placeholder="Reason (optional)"
              value={planModalReason}
              onChange={e => setPlanModalReason(e.target.value)}
            />
            <div className="flex gap-2 justify-end">
              <button
                disabled={changePlan.isPending}
                onClick={() => { setPlanModal(null); setPlanModalReason('') }}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
              >
                Cancel
              </button>
              <button
                disabled={changePlan.isPending || planModalValue === planModal.currentPlan}
                onClick={() => changePlan.mutate({ tenantId: planModal.tenantId, plan_code: planModalValue, reason: planModalReason.trim() || undefined })}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: changePlan.isPending ? 0.6 : 1 }}
              >
                {changePlan.isPending ? 'Saving…' : 'Save Plan'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}

function UsersTab({ search, setSearch }: { search: string; setSearch: (v: string) => void }) {
  const { data: users, isLoading, isError, refetch } = useQuery({
    queryKey: ['platform-users'],
    queryFn: () => listPlatformUsers().then(r => r.data),
  })
  const { enterShop, entering, error } = useAdminEnterShop()

  const [page, setPage] = useState(0)
  const [role, setRole] = useState('all')
  const roles = [...new Set((users ?? []).map(u => u.role))].sort()
  const filtered = (users ?? []).filter(u =>
    [u.full_name, u.email, u.role, u.tenant_name, u.tenant_slug].join(' ').toLowerCase().includes(search.trim().toLowerCase()) && (role === 'all' || u.role === role)
  )

  const currentPage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 25) - 1))
  const visible = filtered.slice(currentPage * 25, (currentPage + 1) * 25)
  return (
    <>
      <div className="console-toolbar"><SearchBar value={search} onChange={v => { setSearch(v); setPage(0) }} placeholder="Search users, roles, or shops…" /><select aria-label="Filter user role" value={role} onChange={e => { setRole(e.target.value); setPage(0) }}><option value="all">All roles</option>{roles.map(r => <option key={r} value={r}>{formatLabel(r)}</option>)}</select></div>
      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}
      {isError ? <div className="console-error" role="alert">Could not load users. <button className="console-button" onClick={() => void refetch()}>Try again</button></div> : isLoading ? <Spinner /> : (
        <Card className="overflow-x-auto">
          {filtered.length === 0 ? <EmptyState message="No users found." /> : (
            <>
              {/* Mobile */}
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--ms-border)' }}>
                {visible.map(u => (
                  <div key={u.id} className="p-4 space-y-0.5">
                    <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>{u.full_name}</p>
                    <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{u.email}</p>
                    <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{formatLabel(u.role)} · {u.tenant_name} (#{u.tenant_slug})</p>
                    <p className="text-xs font-medium" style={{ color: u.is_active ? '#497A59' : '#A06757' }}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </p>
                    <div className="pt-2">
                      <button
                        onClick={() => void enterShop(u.tenant_id)}
                        disabled={!!entering}
                        className="text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: entering === u.tenant_id ? 0.6 : 1 }}
                      >
                        {entering === u.tenant_id ? 'Entering…' : 'Enter Shop'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {/* Desktop */}
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ms-border)' }}>
                    {['Name', 'Email', 'Role', 'Shop', 'Status', 'Enter Shop'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--ms-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((u, i) => (
                    <tr key={u.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text)' }}>{u.full_name}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{u.email}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{formatLabel(u.role)}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{u.tenant_name} (#{u.tenant_slug})</td>
                      <td className="px-5 py-3.5 font-medium" style={{ color: u.is_active ? '#497A59' : '#A06757' }}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </td>
                      <td className="px-5 py-3.5">
                        <button
                          onClick={() => void enterShop(u.tenant_id)}
                          disabled={!!entering}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
                          style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: entering === u.tenant_id ? 0.6 : 1 }}
                        >
                          {entering === u.tenant_id ? 'Entering…' : 'Enter Shop'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </Card>
      )}
      {!isError && !isLoading && <Pagination page={currentPage} total={filtered.length} onChange={setPage} />}
    </>
  )
}

function ActivityTab({ search, setSearch }: { search: string; setSearch: (v: string) => void }) {
  const [eventTypeDraft, setEventTypeDraft] = useState('all')
  const [entityTypeDraft, setEntityTypeDraft] = useState('all')
  const [actorEmailDraft, setActorEmailDraft] = useState('all')
  const [shopDraft, setShopDraft] = useState('all')
  const [eventTypeApplied, setEventTypeApplied] = useState('all')
  const [entityTypeApplied, setEntityTypeApplied] = useState('all')
  const [actorEmailApplied, setActorEmailApplied] = useState('all')
  const [shopApplied, setShopApplied] = useState('all')
  const [dateFromDraft, setDateFromDraft] = useState('')
  const [dateToDraft, setDateToDraft] = useState('')
  const [dateFromApplied, setDateFromApplied] = useState('')
  const [dateToApplied, setDateToApplied] = useState('')
  const [showTechnical, setShowTechnical] = useState(false)
  const [copiedValue, setCopiedValue] = useState('')
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const {
    data: activityPages,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = useInfiniteQuery({
    queryKey: ['platform-activity'],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listPlatformActivity(ACTIVITY_PAGE_SIZE, pageParam).then(r => r.data),
    getNextPageParam: (lastPage, pages) => {
      if (lastPage.length < ACTIVITY_PAGE_SIZE) return undefined
      return pages.reduce((count, page) => count + page.length, 0)
    },
  })
  const { data: tenants = [] } = useQuery({
    queryKey: ['platform-tenants'],
    queryFn: () => listPlatformTenants().then(r => r.data),
  })

  const events = activityPages?.pages.flatMap((page) => page) ?? []
  const eventTypes = Array.from(new Set((events ?? []).map((e) => e.event_type))).sort((a, b) => a.localeCompare(b))
  const entityTypes = Array.from(new Set((events ?? []).map((e) => e.entity_type))).sort((a, b) => a.localeCompare(b))
  const actorEmails = Array.from(new Set((events ?? []).map((e) => e.actor_email).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b))
  const tenantNameById = new Map(tenants.map((t) => [t.id, t.name]))
  const selectedEvent = events.find((e) => e.id === selectedEventId) ?? null

  const filtered = (events ?? []).filter((e) => {
    const searchable = [e.event_type, e.event_summary, e.actor_email ?? '', e.tenant_id ?? '', tenantNameById.get(e.tenant_id ?? '') ?? '']
      .join(' ')
      .toLowerCase()
    if (!searchable.includes(search.toLowerCase())) return false
    if (eventTypeApplied !== 'all' && e.event_type !== eventTypeApplied) return false
    if (entityTypeApplied !== 'all' && e.entity_type !== entityTypeApplied) return false
    if (actorEmailApplied !== 'all' && (e.actor_email ?? 'System') !== actorEmailApplied) return false
    if (shopApplied !== 'all' && (e.tenant_id ?? '') !== shopApplied) return false
    const eventDate = new Date(e.created_at)
    if (dateFromApplied) {
      const from = new Date(`${dateFromApplied}T00:00:00`)
      if (eventDate < from) return false
    }
    if (dateToApplied) {
      const to = new Date(`${dateToApplied}T23:59:59`)
      if (eventDate > to) return false
    }
    return true
  })

  async function copyValue(value?: string) {
    if (!value) return
    await navigator.clipboard.writeText(value)
    setCopiedValue(value)
    window.setTimeout(() => setCopiedValue(''), 1200)
  }

  function csvCell(value: string) {
    return `"${value.replace(/"/g, '""')}"`
  }

  function exportCsv() {
    const header = ['created_at', 'actor_email', 'event_type', 'shop_name', 'tenant_id', 'event_summary']
    const lines = filtered.map((e) => [
      e.created_at,
      e.actor_email ?? 'System',
      e.event_type,
      tenantNameById.get(e.tenant_id ?? '') ?? '',
      e.tenant_id ?? '',
      e.event_summary ?? '',
    ].map(csvCell).join(','))
    const csv = [header.join(','), ...lines].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `platform-admin-activity-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <SearchBar value={search} onChange={setSearch} placeholder="Search activity type, actor, summary…" />
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Event type
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={eventTypeDraft}
            onChange={(e) => setEventTypeDraft(e.target.value)}
          >
            <option value="all">All events</option>
            {eventTypes.map((type) => (
              <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Entity
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={entityTypeDraft}
            onChange={(e) => setEntityTypeDraft(e.target.value)}
          >
            <option value="all">All entities</option>
            {entityTypes.map((type) => (
              <option key={type} value={type}>{formatLabel(type)}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Actor
          <select
            className="mt-1 block min-w-52 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={actorEmailDraft}
            onChange={(e) => setActorEmailDraft(e.target.value)}
          >
            <option value="all">All actors</option>
            <option value="System">System</option>
            {actorEmails.map((email) => (
              <option key={email} value={email}>{email}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Shop
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={shopDraft}
            onChange={(e) => setShopDraft(e.target.value)}
          >
            <option value="all">All shops</option>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          From
          <input
            type="date"
            className="mt-1 block rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={dateFromDraft}
            onChange={(e) => setDateFromDraft(e.target.value)}
          />
        </label>
        <label className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          To
          <input
            type="date"
            className="mt-1 block rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
            value={dateToDraft}
            onChange={(e) => setDateToDraft(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold"
          style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border-strong)' }}
          onClick={() => {
            setEventTypeApplied(eventTypeDraft)
            setEntityTypeApplied(entityTypeDraft)
            setActorEmailApplied(actorEmailDraft)
            setShopApplied(shopDraft)
            setDateFromApplied(dateFromDraft)
            setDateToApplied(dateToDraft)
          }}
        >
          Apply filters
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold"
          style={{ backgroundColor: 'transparent', color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border-strong)' }}
          onClick={() => {
            setEventTypeDraft('all')
            setEntityTypeDraft('all')
            setActorEmailDraft('all')
            setShopDraft('all')
            setEventTypeApplied('all')
            setEntityTypeApplied('all')
            setActorEmailApplied('all')
            setShopApplied('all')
            setDateFromDraft('')
            setDateToDraft('')
            setDateFromApplied('')
            setDateToApplied('')
          }}
        >
          Clear filters
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold"
          style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
          onClick={exportCsv}
          disabled={filtered.length === 0}
        >
          <Download size={14} />
          Export loaded results
        </button>
      </div>
      {isError && (
        <div role="alert" className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          Could not load activity log.
        </div>
      )}
      {isLoading ? <Spinner /> : (
        <>
          <p className="console-subtitle">Showing {filtered.length} matching events from {events.length} loaded. Filters and export apply to loaded events; load more to search older activity.</p>
          <Card className="overflow-x-auto">
            {filtered.length === 0 ? <EmptyState message="No matching events in the loaded activity." /> : (
              <>
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--ms-border)' }}>
                {filtered.map((e) => (
                  <div key={e.id} className="p-4 space-y-1">
                    <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>{formatLabel(e.event_type)}</p>
                    <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>{e.event_summary}</p>
                    <div className="flex flex-wrap gap-1 pt-1">
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(201,162,72,0.12)', color: '#9A7220' }}>
                        {formatLabel(e.entity_type)}
                      </span>
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border-strong)' }}>
                        ID {shortId(e.entity_id)}
                      </span>
                      <button
                        type="button"
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border-strong)' }}
                        onClick={() => void copyValue(e.entity_id)}
                      >
                        {copiedValue === e.entity_id ? 'Copied' : 'Copy ID'}
                      </button>
                      <button
                        type="button"
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border-strong)' }}
                        onClick={() => setSelectedEventId(e.id)}
                      >
                        Details
                      </button>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                      {new Date(e.created_at).toLocaleString()} · {e.actor_email ?? 'System'} · {tenantNameById.get(e.tenant_id ?? '') ?? 'Platform'}
                    </p>
                    {showTechnical && (
                      <p className="text-[11px]" style={{ color: 'var(--ms-text-muted)' }}>
                        Actor ID: {e.actor_user_id ?? 'n/a'} · Entity ID: {e.entity_id ?? 'n/a'}
                      </p>
                    )}
                  </div>
                ))}
              </div>
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ms-border)' }}>
                    {['When', 'Actor', 'Event', 'Entity', 'Shop', 'Summary'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--ms-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((e, i) => (
                    <tr key={e.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                      <td className="px-5 py-3.5 whitespace-nowrap" style={{ color: 'var(--ms-text-muted)' }}>
                        <span className="inline-flex items-center gap-1.5">
                          <Clock size={12} />
                          {new Date(e.created_at).toLocaleString()}
                        </span>
                      </td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{e.actor_email ?? 'System'}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text)' }}>{formatLabel(e.event_type)}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>
                        <div className="flex flex-col">
                          <span>{formatLabel(e.entity_type)}</span>
                          <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                            ID {shortId(e.entity_id)}
                            {' '}
                            <button
                              type="button"
                              className="underline"
                              style={{ color: 'var(--ms-text-muted)' }}
                              onClick={() => void copyValue(e.entity_id)}
                            >
                              {copiedValue === e.entity_id ? 'copied' : 'copy'}
                            </button>
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>{tenantNameById.get(e.tenant_id ?? '') ?? 'Platform'}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--ms-text-mid)' }}>
                        <div className="flex flex-col">
                          <span>{e.event_summary}</span>
                          {showTechnical && (
                            <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                              actor_user_id={e.actor_user_id ?? 'n/a'} entity_id={e.entity_id ?? 'n/a'}
                            </span>
                          )}
                          <button
                            type="button"
                            className="text-xs underline text-left mt-1"
                            style={{ color: 'var(--ms-text-muted)' }}
                            onClick={() => setSelectedEventId(e.id)}
                          >
                            View details
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </>
            )}
          </Card>
          <div className="mt-3 flex items-center gap-2">
            {hasNextPage && (
              <button
                type="button"
                className="rounded-lg px-3 py-2 text-xs font-semibold"
                style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)', border: '1px solid var(--ms-border-strong)' }}
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? 'Loading more…' : 'Load more activity'}
              </button>
            )}
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-xs font-semibold"
              style={{ backgroundColor: 'transparent', color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border-strong)' }}
              onClick={() => setShowTechnical((s) => !s)}
            >
              {showTechnical ? 'Hide technical fields' : 'Show technical fields'}
            </button>
          </div>
          {selectedEvent && (
            <div className="mt-3 rounded-lg p-3" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)' }}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
                  Activity details: {formatLabel(selectedEvent.event_type)}
                </p>
                <button
                  type="button"
                  className="text-xs underline"
                  style={{ color: 'var(--ms-text-muted)' }}
                  onClick={() => setSelectedEventId(null)}
                >
                  Close
                </button>
              </div>
              <div className="grid gap-1 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                <p><strong>Summary:</strong> {selectedEvent.event_summary}</p>
                <p><strong>When:</strong> {new Date(selectedEvent.created_at).toLocaleString()}</p>
                <p><strong>Shop:</strong> {tenantNameById.get(selectedEvent.tenant_id ?? '') ?? 'Platform'} ({selectedEvent.tenant_id ?? 'n/a'})</p>
                <p><strong>Actor:</strong> {selectedEvent.actor_email ?? 'System'} ({selectedEvent.actor_user_id ?? 'n/a'})</p>
                <p><strong>Entity:</strong> {formatLabel(selectedEvent.entity_type)} ({selectedEvent.entity_id ?? 'n/a'})</p>
                <p><strong>Raw event type:</strong> {selectedEvent.event_type}</p>
                <p><strong>Event id:</strong> {selectedEvent.id}</p>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}

function ReportsTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['platform-reports'],
    queryFn: () => getPlatformReports().then(r => r.data),
  })
  const { enterShop, entering, error } = useAdminEnterShop()

  const [search, setSearch] = useState('')
  const [health, setHealth] = useState('all')
  const [page, setPage] = useState(0)
  const filtered = (data?.tenants ?? []).filter(t => [t.tenant_name, t.tenant_slug, t.plan_code].join(' ').toLowerCase().includes(search.trim().toLowerCase()) && (health === 'all' || health === t.health_status))
  const currentPage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 25) - 1))
  const visible = filtered.slice(currentPage * 25, (currentPage + 1) * 25)

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return (
      <div className="text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
        Could not load platform reports.
      </div>
    )
  }

  return (
    <>
      <div className="mb-4 rounded-lg px-4 py-3 flex items-center gap-2" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)' }}>
        <BarChart3 size={16} />
        <span className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
          Network snapshot generated {new Date(data.generated_at).toLocaleString()}
        </span>
      </div>
      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: 'var(--ms-error)', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-4">
        <StatCard label="Shops" value={String(data.totals.tenants)} />
        <StatCard label="Users (active)" value={`${data.totals.users} (${data.totals.active_users})`} />
        <StatCard label="Jobs total" value={String(data.totals.repair_jobs + data.totals.shoe_jobs + data.totals.auto_key_jobs)} />
        <StatCard label="Jobs last 30d" value={String(data.totals.jobs_last_30_days)} />
        <StatCard label="Invoices total" value={String(data.totals.invoices)} />
        <StatCard label="Paid invoices" value={String(data.totals.paid_invoices)} />
        <StatCard label="Billed total" value={formatCents(data.totals.billed_total_cents)} />
        <StatCard label="Paid total" value={formatCents(data.totals.paid_total_cents)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 mb-4">
        <StatCard label="Active accounts" value={String(data.totals.health.active_tenants)} />
        <StatCard label="Suspended shops" value={String(data.totals.health.suspended_tenants)} />
        <StatCard label="No activity 7d" value={String(data.totals.health.tenants_no_activity_7_days)} />
        <StatCard label="No jobs 30d" value={String(data.totals.health.tenants_no_jobs_30_days)} />
        <StatCard label="No active users" value={String(data.totals.health.tenants_no_active_users)} />
      </div>
      <div className="console-grid">
        <section className="console-panel"><h2>Work across your network</h2><p className="console-subtitle">All-time jobs by service. Counts reflect shop operations.</p>
          {([['Watch repairs', data.totals.repair_jobs], ['Shoe repairs', data.totals.shoe_jobs], ['Auto keys', data.totals.auto_key_jobs]] as const).map(([label, value]) => <div key={label}><div className="flex justify-between text-sm"><span>{label}</span><strong>{value.toLocaleString()}</strong></div><div className="console-bar"><span style={{ width: `${value / Math.max(1, data.totals.repair_jobs + data.totals.shoe_jobs + data.totals.auto_key_jobs) * 100}%` }} /></div></div>)}
        </section>
        <section className="console-panel"><h2>Read the numbers clearly</h2><p className="console-subtitle">Billed and paid totals are shop invoice amounts, not Mainspring subscription revenue. Active accounts are enabled accounts; their activity health is shown separately below.</p><div className="console-list-row"><span>Healthy shops</span><strong>{data.tenants.filter(t => t.health_status === 'healthy').length}</strong></div><div className="console-list-row"><span>Shops needing attention</span><strong>{data.tenants.filter(t => t.health_status === 'attention').length}</strong></div></section>
      </div>
      <div className="console-toolbar"><SearchBar value={search} onChange={v => { setSearch(v); setPage(0) }} placeholder="Search report shops…" /><select aria-label="Filter report health" value={health} onChange={e => { setHealth(e.target.value); setPage(0) }}><option value="all">All health statuses</option><option value="healthy">Healthy</option><option value="attention">Needs attention</option><option value="suspended">Suspended</option></select></div>
      {filtered.length === 0 && <EmptyState message="No shops match these report filters." />}
      <Card className="overflow-x-auto">
        <div className="md:hidden divide-y" style={{ borderColor: 'var(--ms-border)' }}>
          {visible.map((t) => (
            <div key={t.tenant_id} className="p-4 space-y-1">
              <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>{t.tenant_name} (#{t.tenant_slug})</p>
              <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{t.plan_code} · {t.users} users · {t.jobs_total} jobs</p>
              <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                Billed {formatCents(t.billed_total_cents)} · Paid {formatCents(t.paid_total_cents)}
              </p>
              <p className="text-xs" style={{ color: t.health_status === 'healthy' ? '#497A59' : t.health_status === 'suspended' ? '#A06757' : '#9A7220' }}>
                Health: {t.health_status} · Logins 7d: {t.logins_last_7_days} · Days since activity: {t.days_since_activity ?? 'n/a'}
              </p>
              <button
                onClick={() => void enterShop(t.tenant_id)}
                disabled={!!entering}
                className="text-xs px-3 py-1.5 rounded-lg font-medium mt-1"
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: entering === t.tenant_id ? 0.6 : 1 }}
              >
                {entering === t.tenant_id ? 'Entering…' : 'Enter Shop'}
              </button>
            </div>
          ))}
        </div>
        <table className="w-full text-sm hidden md:table">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ms-border)' }}>
              {['Shop', 'Plan', 'Users', 'Jobs', 'Jobs 30d', 'Invoices', 'Billed', 'Paid', 'Health', 'Last activity', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--ms-text-muted)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((t, i) => (
              <tr key={t.tenant_id} style={{ borderBottom: i < data.tenants.length - 1 ? '1px solid var(--ms-border)' : 'none' }}>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text)' }}>{t.tenant_name} (#{t.tenant_slug})</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{t.plan_code}</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{t.active_users}/{t.users}</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{t.jobs_total}</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{t.jobs_last_30_days}</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{t.paid_invoices}/{t.invoices}</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{formatCents(t.billed_total_cents)}</td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-mid)' }}>{formatCents(t.paid_total_cents)}</td>
                <td className="px-4 py-3" style={{ color: t.health_status === 'healthy' ? '#497A59' : t.health_status === 'suspended' ? '#A06757' : '#9A7220' }}>
                  {t.health_status} · {t.logins_last_7_days} logins
                </td>
                <td className="px-4 py-3" style={{ color: 'var(--ms-text-muted)' }}>{t.last_activity_at ? new Date(t.last_activity_at).toLocaleString() : '—'}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => void enterShop(t.tenant_id)}
                    disabled={!!entering}
                    className="text-xs px-3 py-1.5 rounded-lg font-medium"
                    style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: entering === t.tenant_id ? 0.6 : 1 }}
                  >
                    {entering === t.tenant_id ? 'Entering…' : 'Enter Shop'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Pagination page={currentPage} total={filtered.length} onChange={setPage} />
    </>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="console-stat">
      <p className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
      <p className="text-lg font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>{value}</p>
    </div>
  )
}
