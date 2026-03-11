import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { listPlatformUsers } from '@/lib/api'
import { Card, EmptyState, PageHeader, Spinner } from '@/components/ui'

export default function PlatformAdminUsersPage() {
  const [search, setSearch] = useState('')

  const { data: users, isLoading } = useQuery({
    queryKey: ['platform-users'],
    queryFn: () => listPlatformUsers().then((r) => r.data),
  })

  const filtered = (users ?? []).filter((u) =>
    [u.full_name, u.email, u.role, u.tenant_name, u.tenant_slug].join(' ').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <PageHeader title="Platform Admin" />
      <p className="mb-4 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
        View all registered users across every shop.
      </p>

      <div className="mb-5 relative w-full max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
        <input
          className="w-full pl-9 pr-4 py-2.5 rounded-lg text-base sm:text-sm outline-none transition"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1px solid var(--cafe-border-2)',
            color: 'var(--cafe-text)',
          }}
          placeholder="Search users, roles, or shops…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? <Spinner /> : (
        <Card>
          {filtered.length === 0 ? <EmptyState message="No users found." /> : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  {['Name', 'Email', 'Role', 'Shop', 'Status'].map((h) => (
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
                    <td className="px-5 py-3.5" style={{ color: 'var(--cafe-text-mid)' }}>{u.tenant_name} ({u.tenant_slug})</td>
                    <td className="px-5 py-3.5" style={{ color: u.is_active ? '#497A59' : '#A06757' }}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
