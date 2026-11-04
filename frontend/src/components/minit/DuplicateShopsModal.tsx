import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getApiErrorMessage,
  getDuplicateShops,
  retireDuplicateShop,
  type DuplicateShopGroup,
  type DuplicateShopMember,
} from '@/lib/api'
import { PARENT_ACCOUNT_QUERY_KEY } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Modal, Spinner } from '@/components/ui'

function describe(m: DuplicateShopMember) {
  const bits = [m.is_member ? (m.network_role === 'operator' ? 'Operator site' : 'Retail site') : 'Reporting link only']
  bits.push(`${m.record_total} record${m.record_total === 1 ? '' : 's'}`)
  return bits.join(' · ')
}

/**
 * One site per shop number. Pick the record to keep, review what moves, then
 * retire the other. Nothing is deleted; a record holding real work is blocked.
 */
export function DuplicateShopsModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [keepByNumber, setKeepByNumber] = useState<Record<string, string>>({})
  const [moveUsers, setMoveUsers] = useState<Set<string>>(new Set())
  const [emails, setEmails] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const keepIds = Object.values(keepByNumber).sort()
  const { data, isLoading, error } = useQuery({
    queryKey: ['duplicate-shops', keepIds],
    queryFn: () => getDuplicateShops(keepIds).then(r => r.data),
    staleTime: 0,
  })
  const retire = useMutation({
    mutationFn: (v: { group: DuplicateShopGroup; keep: string; member: DuplicateShopMember }) =>
      retireDuplicateShop({
        keep_tenant_id: v.keep,
        retire_tenant_id: v.member.tenant_id,
        preview_token: v.member.preview_token ?? '',
        move_user_ids: v.member.users.filter(u => moveUsers.has(u.id)).map(u => u.id),
        user_email_overrides: Object.fromEntries(
          v.member.users.filter(u => moveUsers.has(u.id) && emails[u.id]?.trim()).map(u => [u.id, emails[u.id].trim()])),
      }).then(r => r.data),
    onSuccess: r => {
      setNotice(r.message)
      qc.invalidateQueries({ queryKey: ['duplicate-shops'] })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['minit-mobile-kpis-live'] })
      qc.invalidateQueries({ queryKey: ['minit-mobile-jobs-report'] })
    },
  })

  return (
    <Modal title="Duplicate shop numbers" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Each shop number should be one site. Choose the record to keep; the other is taken off the network and
          suspended, not deleted, and its lead routing moves to the one you keep. A record that holds jobs, customers
          or other work cannot be retired here.
        </p>
        {notice && <p className="text-sm" role="status">{notice}</p>}
        {retire.error && <p role="alert" className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(retire.error, 'Could not retire this record.')}</p>}
        {isLoading && <Spinner />}
        {error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(error, 'Could not load duplicates.')}</p>}
        {data && data.groups.length === 0 && <p className="text-sm">No shop number has more than one record.</p>}
        <div className="max-h-[55vh] overflow-y-auto space-y-3">
          {data?.groups.map(g => {
            const keep = keepByNumber[g.shop_number] ?? g.suggested_keep
            return (
              <div key={g.shop_number} className="rounded-lg p-3 text-sm" style={{ border: '1px solid var(--ms-border)' }}>
                <p className="font-semibold">Shop #{g.shop_number}</p>
                {g.members.map(m => (
                  <div key={m.tenant_id} className="mt-2 text-xs space-y-1">
                    <label className="flex gap-2 items-center">
                      <input type="radio" name={`keep-${g.shop_number}`} checked={keep === m.tenant_id}
                        disabled={retire.isPending}
                        onChange={() => setKeepByNumber(prev => ({ ...prev, [g.shop_number]: m.tenant_id }))} />
                      <span><strong>{m.name}</strong> ({m.slug}) — {describe(m)}{keep === m.tenant_id ? ' · keep' : ''}</span>
                    </label>
                    {keep !== m.tenant_id && (
                      <div className="pl-6 space-y-1">
                        {m.blockers.map(b => <p key={b} style={{ color: '#8A5010' }}>{b}</p>)}
                        {m.users.map(u => (
                          <div key={u.id} className="flex flex-wrap gap-2 items-center">
                            <label className="flex gap-1 items-center">
                              <input type="checkbox" checked={moveUsers.has(u.id)}
                                onChange={e => setMoveUsers(prev => { const n = new Set(prev); if (e.target.checked) n.add(u.id); else n.delete(u.id); return n })} />
                              Move login {u.full_name || u.email} to the kept shop as staff
                            </label>
                            {moveUsers.has(u.id) && (
                              <input className="rounded border p-1" aria-label={`Email for ${u.email}`} defaultValue={u.email}
                                onChange={e => setEmails(prev => ({ ...prev, [u.id]: e.target.value }))} />
                            )}
                          </div>
                        ))}
                        <Button variant="secondary" className="text-xs px-3 py-1.5"
                          disabled={retire.isPending || m.blockers.length > 0 || !m.preview_token}
                          onClick={() => {
                            if (window.confirm(`Retire "${m.name}" into the record you kept for shop #${g.shop_number}? Nothing is deleted.`))
                              retire.mutate({ group: g, keep, member: m })
                          }}>
                          Retire this record
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
        <div className="flex justify-end"><Button onClick={onClose}>Close</Button></div>
      </div>
    </Modal>
  )
}
