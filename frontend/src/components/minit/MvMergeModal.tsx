import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  formatTenantLabel,
  getApiErrorMessage,
  getMvMergePreview,
  runMvMerge,
  updateMvOperator,
  type MvMergeCandidate,
  type MvMergePair,
  type MvMergeResult,
} from '@/lib/api'
import { PARENT_ACCOUNT_QUERY_KEY } from '@/hooks/useParentAccount'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Modal, Spinner } from '@/components/ui'

const REASON_LABEL: Record<string, string> = {
  phone: 'same phone',
  shop_number: 'same shop #',
  name: 'same place',
}

function mergeable(c: MvMergeCandidate) {
  return !!c.operator_tenant_id && !c.blocked
}

/**
 * Review screen for folding each "Mobile Services X" operator into its
 * "X (MV)" shop. Nothing changes until HQ ticks pairs and presses Merge.
 */
export function MvMergeModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['mv-merge-preview'],
    queryFn: () => getMvMergePreview().then(r => r.data),
    staleTime: 0,
  })
  const [ticked, setTicked] = useState<Set<string>>(new Set())
  const [results, setResults] = useState<MvMergeResult[] | null>(null)
  const [phones, setPhones] = useState<Record<string, string>>({})
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set())
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!data) return
    setTicked(new Set(data.candidates.filter(c => c.preselected && mergeable(c)).slice(0, 5).map(c => c.mv_tenant_id)))
    setPhones(Object.fromEntries(data.candidates.map(c => [c.mv_tenant_id, c.dispatch_phone ?? ''])))
    setConfirmed(new Set())
  }, [data])

  const mergeMut = useMutation({
    mutationFn: (pairs: MvMergePair[]) =>
      runMvMerge(pairs).then(r => r.data.results),
    onSuccess: res => {
      setResults(res)
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['mv-merge-preview'] })
      qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
      qc.invalidateQueries({ queryKey: ['minit-mobile-kpis-live'] })
      qc.invalidateQueries({ queryKey: ['minit-mobile-jobs-report'] })
      qc.invalidateQueries({ queryKey: ['minit-email-leads-by-shop'] })
    },
  })

  const operatorMut = useMutation({
    mutationFn: ({ candidate, activate }: { candidate: MvMergeCandidate; activate: boolean }) =>
      updateMvOperator(candidate.mv_tenant_id, {
        preview_token: candidate.preview_token,
        activate_dispatch: activate,
        ...(activate ? { dispatch_phone: phones[candidate.mv_tenant_id] } : {}),
      }),
    onSuccess: response => {
      setNotice(response.data.message)
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY })
      qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_QUERY_KEY })
      qc.invalidateQueries({ queryKey: ['mv-merge-preview'] })
      qc.invalidateQueries({ queryKey: ['minit-operations-overview'] })
      qc.invalidateQueries({ queryKey: ['minit-mobile-kpis-live'] })
      qc.invalidateQueries({ queryKey: ['minit-mobile-jobs-report'] })
    },
  })
  const busy = mergeMut.isPending || operatorMut.isPending

  const candidates = data?.candidates ?? []
  const matched = candidates.filter(c => c.operator_tenant_id)
  const unmatchedVans = candidates.filter(c => !c.operator_tenant_id)
  const selected = matched.filter(c => ticked.has(c.mv_tenant_id) && mergeable(c))

  function toggle(id: string) {
    setTicked(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < 5) next.add(id)
      return next
    })
  }

  const nameById = new Map(candidates.map(c => [c.mv_tenant_id, c.mv_name]))

  function controls(c: MvMergeCandidate) {
    const id = c.mv_tenant_id
    return (
      <div className="mt-2 space-y-2 text-xs">
        <p>Shop phone: {c.shop_phone || 'missing'} · Shop email: {c.shop_email || 'missing'}</p>
        <p>Dispatch email: {c.dispatch_email || 'missing'} · {c.network_role === 'operator' ? 'Operator' : 'Retail'} · Dispatch {c.dispatch_paused ? 'paused' : 'enabled'}</p>
        <p>Plan after merge/activation: {c.proposed_plan_code} · Suburb routes to move: {c.routes_to_move}</p>
        {c.readiness_issues.map(issue => <p key={issue} style={{ color: '#8A5010' }}>{issue}</p>)}
        <label className="block">
          Dispatch mobile ({c.dispatch_phone_source})
          <input className="block w-full rounded border p-1" aria-label={`Dispatch mobile for ${c.mv_name}`}
            value={phones[id] ?? ''} disabled={busy}
            onChange={e => {
              setPhones(prev => ({ ...prev, [id]: e.target.value }))
              setConfirmed(prev => { const next = new Set(prev); next.delete(id); return next })
            }} />
        </label>
        <label className="flex gap-2">
          <input type="checkbox" checked={confirmed.has(id)} disabled={busy || !phones[id]?.trim() || c.blocked}
            onChange={e => setConfirmed(prev => { const next = new Set(prev); if (e.target.checked) next.add(id); else next.delete(id); return next })} />
          I verified this SMS number and the franchisee’s access; enable dispatch when applied.
        </label>
        {c.network_role !== 'operator' && (
          <Button variant="ghost" disabled={busy} onClick={() => operatorMut.mutate({ candidate: c, activate: false })}>
            Make operator only
          </Button>
        )}
        {!c.operator_tenant_id && c.dispatch_paused && (
          <>
            <p>Activation changes a booking-only plan to Basic Auto Key. Existing suburb routes stay unchanged.</p>
            <Button disabled={busy || !confirmed.has(id)} onClick={() => operatorMut.mutate({ candidate: c, activate: true })}>
              Activate dispatch
            </Button>
          </>
        )}
      </div>
    )
  }

  return (
    <Modal title="Merge mobile van duplicates" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          Each ticked pair keeps the <strong>(MV)</strong> shop — its franchisee, number and any invite already sent —
          makes it the mobile operator, and moves the Mobile Services shop&rsquo;s lead routing onto it. The Mobile
          Services shop is taken off the network and suspended, not deleted.
          {' '}Existing MV contacts are kept. Historical reports remain unchanged. Select up to five pairs;
          dispatch stays paused unless you confirm the number and access below. Making an operator only
          keeps the duplicate and its routing in place.
        </p>
        {notice && <p className="text-sm" role="status">{notice}</p>}
        {operatorMut.error && <p role="alert">{getApiErrorMessage(operatorMut.error, 'Could not update operator.')}</p>}

        {isLoading && <Spinner />}
        {error && (
          <p className="text-sm" style={{ color: 'var(--ms-error)' }}>
            {getApiErrorMessage(error, 'Could not load the pairs.')}
          </p>
        )}

        {results ? (
          <div className="space-y-2">
            <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
              {results.filter(r => r.ok).length} merged
              {results.some(r => !r.ok) ? `, ${results.filter(r => !r.ok).length} not merged` : ''}
            </p>
            {results.map(r => (
              <p key={r.mv_tenant_id} className="text-xs" style={{ color: r.ok ? '#1A6A3A' : 'var(--ms-error)' }}>
                {nameById.get(r.mv_tenant_id) ?? r.mv_tenant_id}: {r.message}
              </p>
            ))}
            <div className="flex justify-end">
              <Button onClick={onClose}>Done</Button>
            </div>
          </div>
        ) : data ? (
          <>
            {matched.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No duplicates left to merge.</p>
            ) : (
              <div className="max-h-[50vh] overflow-y-auto rounded-lg" style={{ border: '1px solid var(--ms-border)' }}>
                {matched.map(c => {
                  const can = mergeable(c)
                  return (
                    <div
                      key={c.mv_tenant_id}
                      className="flex gap-3 px-3 py-2.5 text-sm"
                      style={{ borderBottom: '1px solid var(--ms-border)', opacity: can ? 1 : 0.6, cursor: can ? 'pointer' : 'default' }}
                    >
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={ticked.has(c.mv_tenant_id) && can}
                        disabled={!can || busy || (!ticked.has(c.mv_tenant_id) && ticked.size >= 5)}
                        aria-label={`Merge ${c.mv_name}`}
                        onChange={() => toggle(c.mv_tenant_id)}
                      />
                      <div className="min-w-0">
                        <span className="font-semibold" style={{ color: 'var(--ms-text)' }}>
                          {formatTenantLabel(c.mv_name, c.mv_shop_number)}
                        </span>
                        {c.mv_owner ? <span style={{ color: 'var(--ms-text-muted)' }}> · {c.mv_owner}</span> : null}
                        <br />
                        <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                          ← absorbs {formatTenantLabel(c.operator_name ?? '', c.operator_shop_number)}
                          {c.reasons.length > 0 ? ` · ${c.reasons.map(r => REASON_LABEL[r] ?? r).join(', ')}` : ''}
                        </span>
                        {c.note && (
                          <span className="block text-xs mt-0.5" style={{ color: c.blocked ? 'var(--ms-error)' : '#8A5010' }}>
                            {c.note}
                          </span>
                        )}
                        {controls(c)}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {(unmatchedVans.length > 0 || data.unmatched_operators.length > 0) && (
              <div className="text-xs space-y-1" style={{ color: 'var(--ms-text-muted)' }}>
                {unmatchedVans.length > 0 && (
                  <div>
                    <strong>MV shops with no remaining Mobile Services match</strong>
                    {unmatchedVans.map(c => <div key={c.mv_tenant_id} className="my-3 rounded border p-3">
                      <strong>{formatTenantLabel(c.mv_name, c.mv_shop_number)}</strong>
                      {controls(c)}
                    </div>)}
                  </div>
                )}
                {data.unmatched_operators.length > 0 && (
                  <p>
                    <strong>Mobile Services shops with no MV match</strong> (left as they are):{' '}
                    {data.unmatched_operators.map(o => formatTenantLabel(o.name, o.shop_number)).join(', ')}
                  </p>
                )}
              </div>
            )}

            {mergeMut.error && (
              <p className="text-sm" style={{ color: 'var(--ms-error)' }}>
                {getApiErrorMessage(mergeMut.error, 'Could not merge.')}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button
                onClick={() =>
                  mergeMut.mutate(
                    selected.map(c => ({ mv_tenant_id: c.mv_tenant_id, operator_tenant_id: c.operator_tenant_id!,
                      preview_token: c.preview_token, activate_dispatch: confirmed.has(c.mv_tenant_id),
                      dispatch_phone: phones[c.mv_tenant_id] })),
                  )
                }
                disabled={selected.length === 0 || busy}
              >
                {mergeMut.isPending ? 'Merging…' : `Merge ${selected.length} pair${selected.length === 1 ? '' : 's'}`}
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  )
}
