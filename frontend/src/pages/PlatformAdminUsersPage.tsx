import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Clock, Download, Search } from 'lucide-react'
import { listPlatformActivity, listPlatformTenants, listPlatformUsers, platformAdminEnterShop } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Card, EmptyState, PageHeader, Spinner } from '@/components/ui'

type Tab = 'shops' | 'users' | 'activity'

const ADMIN_PREV_TOKEN_KEY = 'admin_prev_token'
const ADMIN_PREV_REFRESH_KEY = 'admin_prev_refresh_token'
const ACTIVITY_PAGE_SIZE = 100

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
  if (!prevToken) return null

  async function returnToAdmin() {
    const prevAccess = sessionStorage.getItem(ADMIN_PREV_TOKEN_KEY) ?? ''
    const prevRefresh = sessionStorage.getItem(ADMIN_PREV_REFRESH_KEY) ?? ''
    sessionStorage.removeItem(ADMIN_PREV_TOKEN_KEY)
    sessionStorage.removeItem(ADMIN_PREV_REFRESH_KEY)
    if (prevAccess) {
      authLogin(prevAccess, prevRefresh || null)
      await refreshSession()
    }
    navigate('/platform-admin/users')
  }

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between px-5 py-3 text-sm font-medium"
      style={{ backgroundColor: '#1F3A5F', color: '#E8F0FB' }}
    >
      <span>Viewing as Platform Admin — you have full access to this shop.</span>
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
        {(['shops', 'users', 'activity'] as Tab[]).map(t => (
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
  const { data: tenants, isLoading, isError } = useQuery({
    queryKey: ['platform-tenants'],
    queryFn: () => listPlatformTenants().then(r => r.data),
  })
  const { enterShop, entering, error } = useAdminEnterShop()

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
      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No shops found." /> : (
            <>
              {/* Mobile */}
              <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border)' }}>
                {filtered.map(t => (
                  <div key={t.id} className="p-4 space-y-1">
                    <p className="font-semibold text-sm" style={{ color: 'var(--cafe-text)' }}>{t.name}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>#{t.slug} · {t.plan_code} · {t.user_count} user{t.user_count !== 1 ? 's' : ''}</p>
                    <div className="pt-2">
                      <button
                        onClick={() => void enterShop(t.id)}
                        disabled={!!entering}
                        className="text-xs px-3 py-1.5 rounded-lg font-medium"
                        style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === t.id ? 0.6 : 1 }}
                      >
                        {entering === t.id ? 'Entering…' : 'Enter Shop'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              {/* Desktop */}
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['Shop', 'Shop Number', 'Plan', 'Users', 'Created', ''].map(h => (
                      <th key={h} className="px-5 py-3.5 text-left font-semibold text-[11px] tracking-widest uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((t, i) => (
                    <tr key={t.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                      <td className="px-5 py-3.5 font-medium" style={{ color: 'var(--cafe-text)' }}>
                        <div className="flex items-center justify-between gap-2">
                          <span>{t.name}</span>
                          <button
                            type="button"
                            onClick={() => void enterShop(t.id)}
                            disabled={!!entering}
                            className="text-[11px] px-2 py-1 rounded-md font-semibold"
                            style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === t.id ? 0.6 : 1 }}
                          >
                            {entering === t.id ? 'Opening…' : 'Open'}
                          </button>
                        </div>
                      </td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>#{t.slug}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{t.plan_code}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{t.user_count}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-muted)' }}>
                        {new Date(t.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3.5">
                        <button
                          onClick={() => void enterShop(t.id)}
                          disabled={!!entering}
                          className="text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity"
                          style={{ backgroundColor: 'var(--cafe-accent)', color: 'var(--cafe-accent-text, #fff)', opacity: entering === t.id ? 0.6 : 1 }}
                        >
                          {entering === t.id ? 'Entering…' : 'Enter Shop'}
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

  const filtered = (users ?? []).filter(u =>
    [u.full_name, u.email, u.role, u.tenant_name, u.tenant_slug].join(' ').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <>
      <SearchBar value={search} onChange={setSearch} placeholder="Search users, roles, or shops…" />
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
                  </div>
                ))}
              </div>
              {/* Desktop */}
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['Name', 'Email', 'Role', 'Shop', 'Status'].map(h => (
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
  const [eventTypeFilter, setEventTypeFilter] = useState('all')
  const [shopFilter, setShopFilter] = useState('all')
  const [dateFromDraft, setDateFromDraft] = useState('')
  const [dateToDraft, setDateToDraft] = useState('')
  const [dateFromApplied, setDateFromApplied] = useState('')
  const [dateToApplied, setDateToApplied] = useState('')
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
  const tenantNameById = new Map(tenants.map((t) => [t.id, t.name]))

  const filtered = (events ?? []).filter((e) => {
    const searchable = [e.event_type, e.event_summary, e.actor_email ?? '', e.tenant_id ?? '', tenantNameById.get(e.tenant_id ?? '') ?? '']
      .join(' ')
      .toLowerCase()
    if (!searchable.includes(search.toLowerCase())) return false
    if (eventTypeFilter !== 'all' && e.event_type !== eventTypeFilter) return false
    if (shopFilter !== 'all' && (e.tenant_id ?? '') !== shopFilter) return false
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
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
          >
            <option value="all">All events</option>
            {eventTypes.map((type) => (
              <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          Shop
          <select
            className="mt-1 block min-w-40 rounded-lg px-2 py-2 text-sm"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)', color: 'var(--cafe-text)' }}
            value={shopFilter}
            onChange={(e) => setShopFilter(e.target.value)}
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
            setDateFromApplied(dateFromDraft)
            setDateToApplied(dateToDraft)
          }}
        >
          Show activity
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold"
          style={{ backgroundColor: 'transparent', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border-2)' }}
          onClick={() => {
            setDateFromDraft('')
            setDateToDraft('')
            setDateFromApplied('')
            setDateToApplied('')
          }}
        >
          Clear dates
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
                    <p className="font-semibold text-sm capitalize" style={{ color: 'var(--cafe-text)' }}>{e.event_type.replace(/_/g, ' ')}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-mid)' }}>{e.event_summary}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {new Date(e.created_at).toLocaleString()} · {e.actor_email ?? 'System'} · {tenantNameById.get(e.tenant_id ?? '') ?? 'Platform'}
                    </p>
                  </div>
                ))}
              </div>
              <table className="w-full text-sm hidden md:table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    {['When', 'Actor', 'Type', 'Shop', 'Summary'].map(h => (
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
                      <td className="px-5 py-3.5 capitalize" style={{ color: 'var(--cafe-text)' }}>{e.event_type.replace(/_/g, ' ')}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{tenantNameById.get(e.tenant_id ?? '') ?? 'Platform'}</td>
                      <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{e.event_summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </>
            )}
          </Card>
          {hasNextPage && (
            <div className="mt-3">
              <button
                type="button"
                className="rounded-lg px-3 py-2 text-xs font-semibold"
                style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border-2)' }}
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? 'Loading more…' : 'Load more activity'}
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}
