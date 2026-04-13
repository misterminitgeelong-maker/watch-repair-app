import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BarChart3, Clock, Download, Search } from 'lucide-react'
import { forcePlatformTenantLogout, getPlatformReports, listPlatformActivity, listPlatformTenants, listPlatformUsers, platformAdminEnterShop, setPlatformTenantStatus } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Card, EmptyState, PageHeader, Spinner } from '@/components/ui'

type Tab = 'shops' | 'users' | 'activity' | 'reports'

const ADMIN_PREV_TOKEN_KEY = 'admin_prev_token'
const ADMIN_PREV_REFRESH_KEY = 'admin_prev_refresh_token'
const ADMIN_IMPERSONATION_STARTED_KEY = 'admin_impersonation_started_at'
const ADMIN_IMPERSONATION_EXPIRES_KEY = 'admin_impersonation_expires_at'
const ADMIN_IMPERSONATION_DURATION_MS = 20 * 60 * 1000
const ACTIVITY_PAGE_SIZE = 100
const formatLabel = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
const shortId = (value?: string) => (value ? value.slice(0, 8) : '')
const formatCents = (value: number) => `$${(value / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

function formatCountdown(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function useAdminEnterShop() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const [entering, setEntering] = useState('')
  const [error, setError] = useState('')

  async function enterShop(tenantId: string) {
    setEntering(tenantId)
    setError('')
    try {
      // Save current admin tokens so we can return
      const prevAccess = localStorage.getItem('token') ?? sessionStorage.getItem('token') ?? ''
      const prevRefresh = localStorage.getItem('refresh_token') ?? sessionStorage.getItem('refresh_token') ?? ''
      if (prevAccess) sessionStorage.setItem(ADMIN_PREV_TOKEN_KEY, prevAccess)
      if (prevRefresh) sessionStorage.setItem(ADMIN_PREV_REFRESH_KEY, prevRefresh)
      sessionStorage.setItem(ADMIN_IMPERSONATION_STARTED_KEY, String(Date.now()))
      sessionStorage.setItem(ADMIN_IMPERSONATION_EXPIRES_KEY, String(Date.now() + ADMIN_IMPERSONATION_DURATION_MS))

      const { data } = await platformAdminEnterShop(tenantId)

      // Use AuthContext login so tokens + role are set correctly
      authLogin(data.access_token, data.refresh_token, data.expires_in_seconds)
      await refreshSession()
      navigate('/dashboard')
    } catch {
      setError('Could not enter shop. Try again.')
    } finally {
      setEntering('')
    }
  }

  return { enterShop, entering, error }
}

export function AdminReturnBanner() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const prevToken = sessionStorage.getItem(ADMIN_PREV_TOKEN_KEY)
  const [nowMs, setNowMs] = useState(Date.now())
  const [returning, setReturning] = useState(false)

  const expiresAt = Number(sessionStorage.getItem(ADMIN_IMPERSONATION_EXPIRES_KEY) ?? '0')
  const remainingMs = expiresAt > 0 ? expiresAt - nowMs : 0

  useEffect(() => {
    if (!prevToken) return
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [prevToken])

  async function returnToAdmin() {
    if (returning) return
    setReturning(true)
    const prevAccess = sessionStorage.getItem(ADMIN_PREV_TOKEN_KEY) ?? ''
    const prevRefresh = sessionStorage.getItem(ADMIN_PREV_REFRESH_KEY) ?? ''
    sessionStorage.removeItem(ADMIN_PREV_TOKEN_KEY)
    sessionStorage.removeItem(ADMIN_PREV_REFRESH_KEY)
    sessionStorage.removeItem(ADMIN_IMPERSONATION_STARTED_KEY)
    sessionStorage.removeItem(ADMIN_IMPERSONATION_EXPIRES_KEY)
    if (prevAccess) {
      authLogin(prevAccess, prevRefresh || null)
      await refreshSession()
    }
    navigate('/platform-admin/users')
  }

  useEffect(() => {
    if (!prevToken) return
    if (remainingMs <= 0 && expiresAt > 0 && !returning) {
      void returnToAdmin()
    }
  }, [prevToken, remainingMs, expiresAt, returning])

  if (!prevToken) return null

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between px-5 py-3 text-sm font-medium"
      style={{ backgroundColor: '#1F3A5F', color: '#E8F0FB' }}
    >
      <span>
        Viewing as Platform Admin. Session window {returning ? 'ending...' : formatCountdown(remainingMs)}.
      </span>
      <button
        className="ml-4 px-3 py-1.5 rounded-lg text-xs font-semibold"
        style={{ backgroundColor: '#4A7FC1', color: '#fff' }}
        onClick={() => void returnToAdmin()}
      >
        Return to Admin
      </button>
    </div>
  )
}

export default function PlatformAdminPage() {
  const [tab, setTab] = useState<Tab>('shops')
  const [search, setSearch] = useState('')

  return (
    <div>
      <PageHeader title="Platform Admin" />
      <p className="mb-5 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
        All shops and users across the platform.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 p-1 rounded-lg w-fit" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}>
        {(['shops', 'users', 'activity', 'reports'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setSearch('') }}
            className="px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors"
            style={{
              backgroundColor: tab === t ? 'var(--cafe-bg)' : 'transparent',
              color: tab === t ? 'var(--cafe-text)' : 'var(--cafe-text-muted)',
              boxShadow: tab === t ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'shops' && <ShopsTab search={search} setSearch={setSearch} />}
      {tab === 'users' && <UsersTab search={search} setSearch={setSearch} />}
      {tab === 'activity' && <ActivityTab search={search} setSearch={setSearch} />}
      {tab === 'reports' && <ReportsTab />}
    </div>
  )
}

function SearchBar({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="mb-5 relative w-full max-w-md">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
      <input
        className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
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
    const reason = window.prompt(`${isActive ? 'Suspend' : 'Reactivate'} ${name} (optional reason):`, '') ?? ''
    setStatus.mutate({ tenantId, isActive: !isActive, reason: reason.trim() || undefined })
  }
  function handleForceLogout(tenantId: string, name: string, slug: string) {
    if (!requireSlugConfirmation(name, slug, 'force logout users for')) return
    const reason = window.prompt(`Force logout all users in ${name}? Optional reason:`, '') ?? ''
    forceLogout.mutate({ tenantId, reason: reason.trim() || undefined })
  }

  const filtered = (tenants ?? []).filter(t =>
    [t.name, t.slug, t.plan_code].join(' ').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <>
      <SearchBar value={search} onChange={setSearch} placeholder="Search shops or plan…" />
      <p className="mb-4 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
        Use <strong>Enter Shop</strong> to open that shop account and view its full dashboard, jobs, customers, and settings.
      </p>
      {isError && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          Could not load shops. Check backend logs.
        </div>
      )}
      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}
      {adminActionError && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {adminActionError}
        </div>
      )}
      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No shops found." /> : (
            <>
              {/* Mobile */}
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
                {filtered.map(t => (
                  <div key={t.id} className="p-4 space-y-1">
                    <p className="font-semibold text-sm" style={{ color: 'var(--cafe-text)' }}>{t.name}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      #{t.slug} · {t.plan_code} · {t.user_count} user{t.user_count !== 1 ? 's' : ''} · {t.is_active ? 'Active' : 'Suspended'}
                    </p>
                    <div className="pt-2">
                      <button
                        onClick={() => void enterShop(t.id)}
                        disabled={!!entering}
                        className="text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)', opacity: entering === t.id ? 0.6 : 1 }}
                      >
                        {entering === t.id ? 'Entering…' : 'Enter Shop'}
                      </button>
                      <button
                        onClick={() => {
                          handleToggleStatus(t.id, t.name, t.slug, t.is_active)
                        }}
                        className="ml-2 text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
                      >
                        {t.is_active ? 'Suspend' : 'Reactivate'}
                      </button>
                      <button
                        onClick={() => {
                          handleForceLogout(t.id, t.name, t.slug)
                        }}
                        className="ml-2 text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ backgroundColor: 'transparent', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text-muted)' }}
                      >
                        Force Logout
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {/* Desktop */}
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['Shop', 'Shop Number', 'Plan', 'Users', 'Status', 'Created', 'Actions'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((t, i) => (
                    <tr key={t.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                      <td className="px-5 py-3.5 font-medium" style={{ color: 'var(--cafe-text)' }}>{t.name}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>#{t.slug}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{t.plan_code}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{t.user_count}</td>
                      <td className="px-5 py-3.5 font-medium" style={{ color: t.is_active ? '#497A59' : '#A06757' }}>{t.is_active ? 'Active' : 'Suspended'}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>
                        {new Date(t.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3.5">
                        <button
                          onClick={() => void enterShop(t.id)}
                          disabled={!!entering}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
                          style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)', opacity: entering === t.id ? 0.6 : 1 }}
                        >
                          {entering === t.id ? 'Entering…' : 'Enter Shop'}
                        </button>
                        <button
                          onClick={() => {
                            handleToggleStatus(t.id, t.name, t.slug, t.is_active)
                          }}
                          className="ml-2 text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
                        >
                          {t.is_active ? 'Suspend' : 'Reactivate'}
                        </button>
                        <button
                          onClick={() => {
                            handleForceLogout(t.id, t.name, t.slug)
                          }}
                          className="ml-2 text-xs px-3 py-1.5 rounded-lg font-medium"
                          style={{ backgroundColor: 'transparent', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text-muted)' }}
                        >
                          Force Logout
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
    </>
  )
}

function UsersTab({ search, setSearch }: { search: string; setSearch: (v: string) => void }) {
  const { data: users, isLoading } = useQuery({
    queryKey: ['platform-users'],
    queryFn: () => listPlatformUsers().then(r => r.data),
  })
  const { enterShop, entering, error } = useAdminEnterShop()

  const filtered = (users ?? []).filter(u =>
    [u.full_name, u.email, u.role, u.tenant_name, u.tenant_slug].join(' ').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <>
      <SearchBar value={search} onChange={setSearch} placeholder="Search users, roles, or shops…" />
      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          {error}
        </div>
      )}
      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No users found." /> : (
            <>
              {/* Mobile */}
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
                {filtered.map(u => (
                  <div key={u.id} className="p-4 space-y-0.5">
                    <p className="font-semibold text-sm" style={{ color: 'var(--cafe-text)' }}>{u.full_name}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{u.email}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{u.role} · {u.tenant_name} (#{u.tenant_slug})</p>
                    <p className="text-xs font-medium" style={{ color: u.is_active ? '#497A59' : '#A06757' }}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </p>
                    <div className="pt-2">
                      <button
                        onClick={() => void enterShop(u.tenant_id)}
                        disabled={!!entering}
                        className="text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === u.tenant_id ? 0.6 : 1 }}
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
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['Name', 'Email', 'Role', 'Shop', 'Status', 'Enter Shop'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u, i) => (
                    <tr key={u.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text)' }}>{u.full_name}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{u.email}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{u.role}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{u.tenant_name} (#{u.tenant_slug})</td>
                      <td className="px-5 py-3.5 font-medium" style={{ color: u.is_active ? '#497A59' : '#A06757' }}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </td>
                      <td className="px-5 py-3.5">
                        <button
                          onClick={() => void enterShop(u.tenant_id)}
                          disabled={!!entering}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
                          style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === u.tenant_id ? 0.6 : 1 }}
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
    queryKey: ['platform-tenants-for-activity'],
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
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          Event type
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            value={eventTypeDraft}
            onChange={(e) => setEventTypeDraft(e.target.value)}
          >
            <option value="all">All events</option>
            {eventTypes.map((type) => (
              <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          Entity
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            value={entityTypeDraft}
            onChange={(e) => setEntityTypeDraft(e.target.value)}
          >
            <option value="all">All entities</option>
            {entityTypes.map((type) => (
              <option key={type} value={type}>{formatLabel(type)}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          Actor
          <select
            className="mt-1 block min-w-52 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
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
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          Shop
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            value={shopDraft}
            onChange={(e) => setShopDraft(e.target.value)}
          >
            <option value="all">All shops</option>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          From
          <input
            type="date"
            className="mt-1 block rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            value={dateFromDraft}
            onChange={(e) => setDateFromDraft(e.target.value)}
          />
        </label>
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          To
          <input
            type="date"
            className="mt-1 block rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            value={dateToDraft}
            onChange={(e) => setDateToDraft(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold"
          style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border-2)' }}
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
          style={{ backgroundColor: 'transparent', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border-2)' }}
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
          style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)' }}
          onClick={exportCsv}
          disabled={filtered.length === 0}
        >
          <Download size={14} />
          Export CSV
        </button>
      </div>
      {isError && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
          Could not load activity log.
        </div>
      )}
      {isLoading ? <Spinner /> : (
        <>
          <Card>
            {filtered.length === 0 ? <EmptyState message="No admin activity found." /> : (
              <>
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
                {filtered.map((e) => (
                  <div key={e.id} className="p-4 space-y-1">
                    <p className="font-semibold text-sm" style={{ color: 'var(--cafe-text)' }}>{formatLabel(e.event_type)}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-mid)' }}>{e.event_summary}</p>
                    <div className="flex flex-wrap gap-1 pt-1">
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'rgba(201,162,72,0.12)', color: '#9A7220' }}>
                        {formatLabel(e.entity_type)}
                      </span>
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border-2)' }}>
                        ID {shortId(e.entity_id)}
                      </span>
                      <button
                        type="button"
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border-2)' }}
                        onClick={() => void copyValue(e.entity_id)}
                      >
                        {copiedValue === e.entity_id ? 'Copied' : 'Copy ID'}
                      </button>
                      <button
                        type="button"
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border-2)' }}
                        onClick={() => setSelectedEventId(e.id)}
                      >
                        Details
                      </button>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {new Date(e.created_at).toLocaleString()} · {e.actor_email ?? 'System'} · {tenantNameById.get(e.tenant_id ?? '') ?? 'Platform'}
                    </p>
                    {showTechnical && (
                      <p className="text-[11px]" style={{ color: 'var(--cafe-text-muted)' }}>
                        Actor ID: {e.actor_user_id ?? 'n/a'} · Entity ID: {e.entity_id ?? 'n/a'}
                      </p>
                    )}
                  </div>
                ))}
              </div>
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['When', 'Actor', 'Event', 'Entity', 'Shop', 'Summary'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((e, i) => (
                    <tr key={e.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                      <td className="px-5 py-3.5 whitespace-nowrap" style={{ color: 'var(--cafe-text-muted)' }}>
                        <span className="inline-flex items-center gap-1.5">
                          <Clock size={12} />
                          {new Date(e.created_at).toLocaleString()}
                        </span>
                      </td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{e.actor_email ?? 'System'}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text)' }}>{formatLabel(e.event_type)}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>
                        <div className="flex flex-col">
                          <span>{formatLabel(e.entity_type)}</span>
                          <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                            ID {shortId(e.entity_id)}
                            {' '}
                            <button
                              type="button"
                              className="underline"
                              style={{ color: 'var(--cafe-text-muted)' }}
                              onClick={() => void copyValue(e.entity_id)}
                            >
                              {copiedValue === e.entity_id ? 'copied' : 'copy'}
                            </button>
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{tenantNameById.get(e.tenant_id ?? '') ?? 'Platform'}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>
                        <div className="flex flex-col">
                          <span>{e.event_summary}</span>
                          {showTechnical && (
                            <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                              actor_user_id={e.actor_user_id ?? 'n/a'} entity_id={e.entity_id ?? 'n/a'}
                            </span>
                          )}
                          <button
                            type="button"
                            className="text-xs underline text-left mt-1"
                            style={{ color: 'var(--cafe-text-muted)' }}
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
                style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border-2)' }}
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? 'Loading more…' : 'Load more activity'}
              </button>
            )}
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-xs font-semibold"
              style={{ backgroundColor: 'transparent', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border-2)' }}
              onClick={() => setShowTechnical((s) => !s)}
            >
              {showTechnical ? 'Hide technical fields' : 'Show technical fields'}
            </button>
          </div>
          {selectedEvent && (
            <div className="mt-3 rounded-lg p-3" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>
                  Activity details: {formatLabel(selectedEvent.event_type)}
                </p>
                <button
                  type="button"
                  className="text-xs underline"
                  style={{ color: 'var(--cafe-text-muted)' }}
                  onClick={() => setSelectedEventId(null)}
                >
                  Close
                </button>
              </div>
              <div className="grid gap-1 text-xs" style={{ color: 'var(--cafe-text-mid)' }}>
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

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return (
      <div className="text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
        Could not load platform reports.
      </div>
    )
  }

  return (
    <>
      <div className="mb-4 rounded-lg px-4 py-3 flex items-center gap-2" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}>
        <BarChart3 size={16} />
        <span className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
          Network snapshot generated {new Date(data.generated_at).toLocaleString()}
        </span>
      </div>
      {error && (
        <div className="mb-4 text-sm rounded-lg px-4 py-3" style={{ color: '#C96A5A', backgroundColor: '#FDF0EE', border: '1px solid #E8B4AA' }}>
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
        <StatCard label="Healthy shops" value={String(data.totals.health.active_tenants)} />
        <StatCard label="Suspended shops" value={String(data.totals.health.suspended_tenants)} />
        <StatCard label="No activity 7d" value={String(data.totals.health.tenants_no_activity_7_days)} />
        <StatCard label="No jobs 30d" value={String(data.totals.health.tenants_no_jobs_30_days)} />
        <StatCard label="No active users" value={String(data.totals.health.tenants_no_active_users)} />
      </div>
      <Card>
        <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
          {data.tenants.map((t) => (
            <div key={t.tenant_id} className="p-4 space-y-1">
              <p className="font-semibold text-sm" style={{ color: 'var(--cafe-text)' }}>{t.tenant_name} (#{t.tenant_slug})</p>
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{t.plan_code} · {t.users} users · {t.jobs_total} jobs</p>
              <p className="text-xs" style={{ color: 'var(--cafe-text-mid)' }}>
                Billed {formatCents(t.billed_total_cents)} · Paid {formatCents(t.paid_total_cents)}
              </p>
              <p className="text-xs" style={{ color: t.health_status === 'healthy' ? '#497A59' : t.health_status === 'suspended' ? '#A06757' : '#9A7220' }}>
                Health: {t.health_status} · Logins 7d: {t.logins_last_7_days} · Days since activity: {t.days_since_activity ?? 'n/a'}
              </p>
              <button
                onClick={() => void enterShop(t.tenant_id)}
                disabled={!!entering}
                className="text-xs px-3 py-1.5 rounded-lg font-medium mt-1"
                style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === t.tenant_id ? 0.6 : 1 }}
              >
                {entering === t.tenant_id ? 'Entering…' : 'Enter Shop'}
              </button>
            </div>
          ))}
        </div>
        <table className="w-full text-sm hidden md:table">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              {['Shop', 'Plan', 'Users', 'Jobs', 'Jobs 30d', 'Invoices', 'Billed', 'Paid', 'Health', 'Last activity', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.tenants.map((t, i) => (
              <tr key={t.tenant_id} style={{ borderBottom: i < data.tenants.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text)' }}>{t.tenant_name} (#{t.tenant_slug})</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{t.plan_code}</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{t.active_users}/{t.users}</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{t.jobs_total}</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{t.jobs_last_30_days}</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{t.paid_invoices}/{t.invoices}</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{formatCents(t.billed_total_cents)}</td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-mid)' }}>{formatCents(t.paid_total_cents)}</td>
                <td className="px-4 py-3" style={{ color: t.health_status === 'healthy' ? '#497A59' : t.health_status === 'suspended' ? '#A06757' : '#9A7220' }}>
                  {t.health_status} · {t.logins_last_7_days} logins
                </td>
                <td className="px-4 py-3" style={{ color: 'var(--cafe-text-muted)' }}>{t.last_activity_at ? new Date(t.last_activity_at).toLocaleString() : '—'}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => void enterShop(t.tenant_id)}
                    disabled={!!entering}
                    className="text-xs px-3 py-1.5 rounded-lg font-medium"
                    style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === t.tenant_id ? 0.6 : 1 }}
                  >
                    {entering === t.tenant_id ? 'Entering…' : 'Enter Shop'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg px-4 py-3" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}>
      <p className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>{label}</p>
      <p className="text-lg font-semibold mt-1" style={{ color: 'var(--cafe-text)' }}>{value}</p>
    </div>
  )
}
