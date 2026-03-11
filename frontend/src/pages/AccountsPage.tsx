import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { createUser, listUsers, type TenantUser, updateUser } from '@/lib/api'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'

type UserRole = 'owner' | 'manager' | 'tech' | 'intake'

const ROLE_OPTIONS: UserRole[] = ['owner', 'manager', 'tech', 'intake']

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
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState<Record<string, { role: UserRole; is_active: boolean }>>({})

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

  const filtered = (users ?? []).filter((u) =>
    [u.full_name, u.email, u.role].join(' ').toLowerCase().includes(search.toLowerCase())
  )

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
