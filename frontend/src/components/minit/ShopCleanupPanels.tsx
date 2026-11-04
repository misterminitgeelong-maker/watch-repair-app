import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  applyEntitlementBackfill,
  getApiErrorMessage,
  getEntitlementBackfill,
  getEntitlementUsage,
  getVanMergePreview,
  runVanMerge,
  type VanMergePreview,
} from '@/lib/api'
import { PARENT_ACCOUNT_QUERY_KEY } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Input } from '@/components/ui'

/** Fold a mobile-service record (van) into its franchisee's shop site. Nothing is deleted. */
export function VanMergePanel() {
  const qc = useQueryClient()
  const [shopNumber, setShopNumber] = useState('')
  const [vanNumber, setVanNumber] = useState('')
  const [mvNumber, setMvNumber] = useState('')
  const [allowOther, setAllowOther] = useState(false)
  const [preview, setPreview] = useState<VanMergePreview | null>(null)
  const [moveUsers, setMoveUsers] = useState<Set<string>>(new Set())
  const [emails, setEmails] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')

  const load = useMutation({
    mutationFn: () =>
      getVanMergePreview({ shop_number: shopNumber.trim(), van_number: vanNumber.trim(), allow_other_networks: allowOther })
        .then(r => r.data),
    onSuccess: p => { setPreview(p); setNotice(''); setMvNumber(vanNumber.trim()) },
  })
  const merge = useMutation({
    mutationFn: (p: VanMergePreview) =>
      runVanMerge({
        shop_tenant_id: p.shop.tenant_id,
        van_tenant_id: p.van.tenant_id,
        preview_token: p.preview_token,
        mv_number: mvNumber.trim() || undefined,
        allow_other_networks: allowOther,
        move_user_ids: p.van.users.filter(u => moveUsers.has(u.id)).map(u => u.id),
        user_email_overrides: Object.fromEntries(
          p.van.users.filter(u => moveUsers.has(u.id) && emails[u.id]?.trim()).map(u => [u.id, emails[u.id].trim()])),
      }).then(r => r.data),
    onSuccess: r => {
      setNotice(r.message)
      setPreview(null)
      for (const key of [PARENT_ACCOUNT_SITES_QUERY_KEY, PARENT_ACCOUNT_QUERY_KEY, ['duplicate-shops'], ['entitlement-usage'],
        ['minit-mobile-kpis-live'], ['minit-mobile-jobs-report']]) qc.invalidateQueries({ queryKey: key })
    },
  })
  const err = load.error ?? merge.error

  return (
    <div className="rounded-lg p-3 text-sm space-y-2" style={{ border: '1px solid var(--ms-border)' }}>
      <p className="font-semibold">Merge a van into its shop</p>
      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
        For a franchisee whose mobile service is a separate record. The shop keeps its number and gains mobile services
        (paid by the network) plus the van&rsquo;s MV number. Lead routing and base move across. Refused if the van holds jobs or customers.
      </p>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-xs">Shop #<Input value={shopNumber} onChange={e => setShopNumber(e.target.value)} aria-label="Shop number" /></label>
        <label className="text-xs">Van #<Input value={vanNumber} onChange={e => setVanNumber(e.target.value)} aria-label="Van number" /></label>
        <label className="text-xs flex gap-1 items-center">
          <input type="checkbox" checked={allowOther} onChange={e => setAllowOther(e.target.checked)} />
          Van is also in another network; fold it anyway
        </label>
        <Button variant="secondary" disabled={!shopNumber.trim() || !vanNumber.trim() || load.isPending} onClick={() => load.mutate()}>
          Preview
        </Button>
      </div>
      {err && <p role="alert" className="text-xs" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(err, 'That did not work.')}</p>}
      {notice && <p role="status" className="text-xs">{notice}</p>}
      {preview && (
        <div className="text-xs space-y-1">
          <p><strong>Keep:</strong> {preview.shop.name} (#{preview.shop.shop_number}) · <strong>Fold in:</strong> {preview.van.name} (#{preview.van.shop_number})</p>
          {preview.other_networks.length > 0 && <p>Also a member of: {preview.other_networks.join(', ')} (left as is, suspended with the van)</p>}
          {preview.blockers.map(b => <p key={b} style={{ color: '#8A5010' }}>{b}</p>)}
          <label className="block">MV number on the shop
            <Input value={mvNumber} onChange={e => setMvNumber(e.target.value)} aria-label="MV number" />
          </label>
          {preview.van.users.map(u => (
            <div key={u.id} className="flex flex-wrap gap-2 items-center">
              <label className="flex gap-1 items-center">
                <input type="checkbox" checked={moveUsers.has(u.id)}
                  onChange={e => setMoveUsers(prev => { const n = new Set(prev); if (e.target.checked) n.add(u.id); else n.delete(u.id); return n })} />
                Move login {u.full_name || u.email} to the shop as staff
              </label>
              {moveUsers.has(u.id) && (
                <input className="rounded border p-1" aria-label={`Email for ${u.email}`} defaultValue={u.email}
                  onChange={e => setEmails(prev => ({ ...prev, [u.id]: e.target.value }))} />
              )}
            </div>
          ))}
          <Button disabled={preview.blockers.length > 0 || merge.isPending}
            onClick={() => { if (window.confirm(`Fold "${preview.van.name}" into "${preview.shop.name}"? Nothing is deleted.`)) merge.mutate(preview) }}>
            Fold van into shop
          </Button>
        </div>
      )}
    </div>
  )
}

/** Who pays for what: starting entitlements from current plans, and the counts Minit is invoiced on. */
export function EntitlementsPanel() {
  const qc = useQueryClient()
  const usage = useQuery({ queryKey: ['entitlement-usage'], queryFn: () => getEntitlementUsage().then(r => r.data.usage), staleTime: 0 })
  const proposal = useQuery({ queryKey: ['entitlement-backfill'], queryFn: () => getEntitlementBackfill().then(r => r.data), staleTime: 0 })
  const apply = useMutation({
    mutationFn: (token: string) => applyEntitlementBackfill(token).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entitlement-usage'] })
      qc.invalidateQueries({ queryKey: ['entitlement-backfill'] })
    },
  })
  const rows = proposal.data?.rows ?? []
  const label = (n: { name: string; shop_number?: string | null }) => `${n.name}${n.shop_number ? ` (#${n.shop_number})` : ''}`
  return (
    <div className="rounded-lg p-3 text-sm space-y-2" style={{ border: '1px solid var(--ms-border)' }}>
      <p className="font-semibold">Entitlements: what each side pays for</p>
      <p className="text-xs">Active now: {Object.keys(usage.data ?? {}).length === 0 ? 'none yet' :
        Object.entries(usage.data ?? {}).map(([kind, payers]) =>
          `${kind} — ${Object.entries(payers).map(([p, n]) => `${n} paid by ${p}`).join(', ')}`).join('; ')}</p>
      {rows.length > 0 ? (
        <>
          <p className="text-xs font-semibold">To grant from current plans</p>
          <ul className="text-xs list-disc pl-5">
            {Object.entries(proposal.data?.breakdown ?? {}).flatMap(([kind, payers]) =>
              Object.entries(payers).map(([payer, n]) => (
                <li key={`${kind}-${payer}`}>{n} × {kind} — {payer === 'parent' ? 'Minit pays' : payer === 'comp' ? 'complimentary, never invoiced' : 'shop pays'}</li>
              )))}
          </ul>
          {(proposal.data?.flagged.length ?? 0) > 0 && (
            <div className="text-xs" style={{ color: '#8A5010' }}>
              <p className="font-semibold">Check these before granting</p>
              {proposal.data!.flagged.map(f => <p key={f.site_id}>{label(f)}: {f.note}</p>)}
            </div>
          )}
          {(proposal.data?.skipped.length ?? 0) > 0 && (
            <details className="text-xs">
              <summary>Skipped, no entitlement ({proposal.data!.skipped.length})</summary>
              {proposal.data!.skipped.map(k => <p key={k.site_id}>{label(k)}: {k.reason}</p>)}
            </details>
          )}
          <Button variant="secondary" disabled={apply.isPending}
            onClick={() => { if (window.confirm(`Grant ${rows.length} starting entitlements? This can be undone by hand from the activity log.`)) apply.mutate(proposal.data!.preview_token) }}>
            Grant starting entitlements
          </Button>
        </>
      ) : <p className="text-xs">Nothing left to grant from current plans.</p>}
      {apply.error && <p role="alert" className="text-xs" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(apply.error, 'Could not grant.')}</p>}
    </div>
  )
}
