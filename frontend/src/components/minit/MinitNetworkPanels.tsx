import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createRegion,
  deleteRegion,
  getApiErrorMessage,
  grantParentAccountRole,
  listParentAccountUsers,
  listRegions,
  revokeParentAccountRole,
  updateRegion,
  type ParentAccountUser,
  type ParentRole,
  type Region,
  type RegionInput,
} from '@/lib/api'
import { PARENT_ACCOUNT_QUERY_KEY } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Card, Input, Modal, Select } from '@/components/ui'

export const REGIONS_QUERY_KEY = ['parent-account-regions'] as const
export const PARENT_USERS_QUERY_KEY = ['parent-account-users'] as const

export function useRegions() {
  return useQuery({
    queryKey: REGIONS_QUERY_KEY,
    queryFn: () => listRegions().then(r => r.data),
    staleTime: 120_000,
  })
}

const ROLE_LABEL: Record<ParentRole, string> = {
  hq_admin: 'HQ admin',
  hq_viewer: 'HQ viewer',
}

const SOURCE_LABEL: Record<ParentAccountUser['source'], string> = {
  explicit: 'set by HQ',
  hq_site: 'HQ tenant',
  owner_email: 'account owner',
}

function emptyRegion(): RegionInput {
  return { name: '', manager_name: '', manager_email: '', manager_phone: '', escalation_email: '', notes: '' }
}

/**
 * Regions are rows, not strings: the dashboard groups by them, sites point at
 * them, and each carries the people a franchise network wants attached to a
 * region — its manager and where escalations go.
 */
export function RegionsCard({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient()
  const { data: regions = [], isLoading } = useRegions()
  const [editing, setEditing] = useState<Region | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<RegionInput>(emptyRegion())
  const [error, setError] = useState('')

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: REGIONS_QUERY_KEY })
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
    qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
  }

  const createMut = useMutation({
    mutationFn: (payload: RegionInput) => createRegion(payload).then(r => r.data),
    onSuccess: () => { setCreating(false); setForm(emptyRegion()); setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not create region.')),
  })
  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<RegionInput> }) =>
      updateRegion(id, payload).then(r => r.data),
    onSuccess: () => { setEditing(null); setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not update region.')),
  })
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteRegion(id).then(r => r.data),
    onSuccess: () => { setEditing(null); setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not delete region.')),
  })

  function openEdit(region: Region) {
    setError('')
    setForm({
      name: region.name,
      manager_name: region.manager_name ?? '',
      manager_email: region.manager_email ?? '',
      manager_phone: region.manager_phone ?? '',
      escalation_email: region.escalation_email ?? '',
      notes: region.notes ?? '',
    })
    setEditing(region)
  }

  const fields = (
    <>
      <Input label="Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="VIC South" />
      <Input label="Regional manager" value={form.manager_name ?? ''} onChange={e => setForm(f => ({ ...f, manager_name: e.target.value }))} />
      <Input label="Manager email" type="email" value={form.manager_email ?? ''} onChange={e => setForm(f => ({ ...f, manager_email: e.target.value }))} />
      <Input label="Manager phone" value={form.manager_phone ?? ''} onChange={e => setForm(f => ({ ...f, manager_phone: e.target.value }))} />
      <Input label="Escalation email" type="email" value={form.escalation_email ?? ''} onChange={e => setForm(f => ({ ...f, escalation_email: e.target.value }))} />
      <Input label="Notes" value={form.notes ?? ''} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
    </>
  )

  return (
    <Card className="mb-6 overflow-hidden">
      <div
        className="px-5 py-3 flex flex-wrap items-center justify-between gap-3"
        style={{ borderBottom: '1px solid var(--ms-border)' }}
      >
        <div>
          <span className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
            Regions ({regions.length})
          </span>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
            Imports create these from the TSS region column; add a manager and escalation contact here.
          </p>
        </div>
        {canEdit && (
          <Button variant="secondary" className="text-xs px-3 py-1.5" onClick={() => { setError(''); setForm(emptyRegion()); setCreating(true) }}>
            + Add region
          </Button>
        )}
      </div>
      {isLoading ? (
        <p className="px-5 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>Loading regions…</p>
      ) : regions.length === 0 ? (
        <p className="px-5 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          No regions yet. Import shops, or add one.
        </p>
      ) : (
        regions.map(region => (
          <div
            key={region.id}
            className="px-5 py-3 flex flex-wrap items-center justify-between gap-3"
            style={{ borderBottom: '1px solid var(--ms-border)' }}
          >
            <div className="min-w-0">
              <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                {region.name}
                <span className="ml-2 text-xs font-normal" style={{ color: 'var(--ms-text-muted)' }}>
                  {region.code} · {region.site_count} {region.site_count === 1 ? 'site' : 'sites'}
                </span>
              </p>
              <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>
                {region.manager_name
                  ? `${region.manager_name}${region.manager_email ? ` · ${region.manager_email}` : ''}${region.manager_phone ? ` · ${region.manager_phone}` : ''}`
                  : 'No regional manager set'}
                {region.escalation_email ? ` · escalations → ${region.escalation_email}` : ''}
              </p>
            </div>
            {canEdit && (
              <Button variant="ghost" className="text-xs px-3 py-1.5" onClick={() => openEdit(region)}>
                Edit
              </Button>
            )}
          </div>
        ))
      )}

      {creating && (
        <Modal title="Add region" onClose={() => setCreating(false)}>
          <div className="space-y-4">
            {fields}
            {error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
              <Button onClick={() => createMut.mutate(form)} disabled={createMut.isPending || !form.name.trim()}>
                {createMut.isPending ? 'Saving…' : 'Add region'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit ${editing.name}`} onClose={() => setEditing(null)}>
          <div className="space-y-4">
            {fields}
            {error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}
            <div className="flex flex-wrap justify-between gap-2">
              <Button
                variant="ghost"
                className="text-xs"
                onClick={() => {
                  if (window.confirm(`Delete region ${editing.name}? Its ${editing.site_count} sites become unassigned.`)) {
                    deleteMut.mutate(editing.id)
                  }
                }}
                disabled={deleteMut.isPending}
              >
                {deleteMut.isPending ? 'Deleting…' : 'Delete region'}
              </Button>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                <Button
                  onClick={() => updateMut.mutate({ id: editing.id, payload: form })}
                  disabled={updateMut.isPending || !form.name.trim()}
                >
                  {updateMut.isPending ? 'Saving…' : 'Save'}
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  )
}

/**
 * Who can act on the network and how far. People in the HQ tenant are HQ by
 * default (owners run it, everyone else reads it); explicit grants override
 * that per person, and let someone outside the HQ tenant in.
 */
export function HqStaffCard({ canEdit, currentUserId }: { canEdit: boolean; currentUserId?: string }) {
  const qc = useQueryClient()
  const { data: users = [], isLoading } = useQuery({
    queryKey: PARENT_USERS_QUERY_KEY,
    queryFn: () => listParentAccountUsers().then(r => r.data),
    staleTime: 60_000,
  })
  const [granting, setGranting] = useState(false)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<ParentRole>('hq_viewer')
  const [error, setError] = useState('')

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: PARENT_USERS_QUERY_KEY })
    qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
  }
  const grantMut = useMutation({
    mutationFn: (payload: { user_id?: string; email?: string; role: ParentRole }) =>
      grantParentAccountRole(payload).then(r => r.data),
    onSuccess: () => { setGranting(false); setEmail(''); setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not change that role.')),
  })
  const revokeMut = useMutation({
    mutationFn: (userId: string) => revokeParentAccountRole(userId).then(r => r.data),
    onSuccess: () => { setError(''); invalidate() },
    onError: err => setError(getApiErrorMessage(err, 'Could not remove that grant.')),
  })

  return (
    <Card className="mb-6 overflow-hidden">
      <div
        className="px-5 py-3 flex flex-wrap items-center justify-between gap-3"
        style={{ borderBottom: '1px solid var(--ms-border)' }}
      >
        <div>
          <span className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
            HQ staff ({users.length})
          </span>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
            HQ admins can change the network; viewers can only read it. Add HQ people under Users; grant roles here.
          </p>
        </div>
        {canEdit && (
          <Button variant="secondary" className="text-xs px-3 py-1.5" onClick={() => { setError(''); setGranting(true) }}>
            + Grant role
          </Button>
        )}
      </div>
      {error && !granting && (
        <p className="px-5 py-2 text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>
      )}
      {isLoading ? (
        <p className="px-5 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>Loading…</p>
      ) : (
        users.map(u => (
          <div
            key={u.user_id}
            className="px-5 py-3 flex flex-wrap items-center justify-between gap-3"
            style={{ borderBottom: '1px solid var(--ms-border)' }}
          >
            <div className="min-w-0">
              <p className="font-semibold text-sm truncate" style={{ color: 'var(--ms-text)' }}>
                {u.full_name}
                <span className="ml-2 text-xs font-normal" style={{ color: 'var(--ms-text-muted)' }}>{u.email}</span>
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                {ROLE_LABEL[u.role]} · {SOURCE_LABEL[u.source]} · {u.tenant_slug} ({u.tenant_role})
              </p>
            </div>
            {canEdit && u.user_id !== currentUserId && (
              <div className="flex items-center gap-2">
                <Select
                  value={u.role}
                  onChange={e => grantMut.mutate({ user_id: u.user_id, role: e.target.value as ParentRole })}
                  aria-label={`Role for ${u.email}`}
                  disabled={grantMut.isPending}
                >
                  <option value="hq_admin">HQ admin</option>
                  <option value="hq_viewer">HQ viewer</option>
                </Select>
                {u.source === 'explicit' && (
                  <Button
                    variant="ghost"
                    className="text-xs px-3 py-1.5"
                    onClick={() => revokeMut.mutate(u.user_id)}
                    disabled={revokeMut.isPending}
                    title="Remove the explicit grant; HQ-tenant users fall back to their default role"
                  >
                    Remove grant
                  </Button>
                )}
              </div>
            )}
          </div>
        ))
      )}

      {granting && (
        <Modal title="Grant network role" onClose={() => setGranting(false)}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              The person must already have a login in one of the network's shops (or in HQ).
            </p>
            <Input label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            <Select label="Role" value={role} onChange={e => setRole(e.target.value as ParentRole)}>
              <option value="hq_viewer">HQ viewer — read dashboards and reports</option>
              <option value="hq_admin">HQ admin — manage shops, staff, regions; open shops</option>
            </Select>
            {error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setGranting(false)}>Cancel</Button>
              <Button onClick={() => grantMut.mutate({ email: email.trim(), role })} disabled={grantMut.isPending || !email.trim()}>
                {grantMut.isPending ? 'Saving…' : 'Grant'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  )
}
