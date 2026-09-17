import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, ArrowUpRight, Clock3 } from 'lucide-react'
import { Button, Card, EmptyState, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'
import { useAuth } from '@/context/AuthContext'
import { getApiErrorMessage } from '@/lib/api'
import { formatCents } from '@/lib/money'
import { getRevenueControl, saveRevenueFollowUp, type RevenueItem, type RevenueKind, type RevenueResponse } from '@/lib/api/revenueControl'

const labels: Record<RevenueKind, string> = {
  unpaid: 'Unpaid invoices', uninvoiced: 'Completed, no invoice', quote_followup: 'Quotes to follow up',
  quote_draft: 'Quotes to prepare', booking_confirmation: 'Unconfirmed bookings',
  unscheduled: 'Needs scheduling', unassigned: 'Needs a technician', blocked: 'Bookings on hold',
}
const order: RevenueKind[] = ['unpaid', 'uninvoiced', 'quote_followup', 'quote_draft', 'booking_confirmation', 'unscheduled', 'unassigned', 'blocked']
const muted = { color: 'var(--ms-text-muted)' }
const dateTime = (value: string, timeZone: string) => new Date(value).toLocaleString('en-AU', { timeZone, dateStyle: 'medium', timeStyle: 'short' })

function FollowUpModal({ item, owners, timeZone, onClose }: { item: RevenueItem; owners: RevenueResponse['owners']; timeZone: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [owner, setOwner] = useState(item.owner_user_id ?? '')
  const [note, setNote] = useState(item.note ?? '')
  const [schedule, setSchedule] = useState('keep')
  const [contacted, setContacted] = useState(false)
  const mutation = useMutation({
    mutationFn: () => saveRevenueFollowUp(item.key, {
      expected_version: item.version ?? 0, owner_user_id: owner || null, note, contacted,
      next_follow_up_at: schedule === 'keep' ? (item.due ? null : item.due_at) :
        schedule === 'now' ? null : new Date(Date.now() + Number(schedule) * 86400000).toISOString(),
    }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['revenue-control'] })
      await qc.invalidateQueries({ queryKey: ['auto-key-job-events', item.job_id] })
      onClose()
    },
  })
  return <Modal title={`Follow up · ${item.job_number}`} onClose={onClose} closeDisabled={mutation.isPending}>
    <form className="space-y-4" onSubmit={e => { e.preventDefault(); mutation.mutate() }}>
      <p className="text-sm" style={muted}>{item.next_action}. Saving records an internal task. It does not send a customer message or mark an invoice paid.</p>
      <Select label="Responsible team member" aria-label="Responsible team member" value={owner} onChange={e => setOwner(e.target.value)}>
        <option value="">Unassigned</option>
        {owners.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
      </Select>
      <Select label="Return to the due queue" aria-label="Return to the due queue" value={schedule} onChange={e => setSchedule(e.target.value)}>
        <option value="keep">Keep current timing{!item.due ? ` · ${dateTime(item.due_at, timeZone)}` : ' · due now'}</option>
        <option value="now">Now</option><option value="1">In 24 hours</option><option value="3">In 3 days</option><option value="7">In 7 days</option><option value="14">In 14 days</option>
      </Select>
      <Textarea label="Next action / conversation notes" aria-label="Next action / conversation notes" rows={4} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} placeholder="What happened, and what should happen next?" />
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={contacted} onChange={e => setContacted(e.target.checked)} />I contacted the customer</label>
      {mutation.isError && <p role="alert" className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(mutation.error, 'Could not save follow-up. Try again.')}</p>}
      <div className="flex justify-end gap-2"><Button type="button" variant="secondary" disabled={mutation.isPending} onClick={onClose}>Cancel</Button><Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save follow-up'}</Button></div>
    </form>
  </Modal>
}

export default function RevenueControlPage() {
  const { tenantId, role } = useAuth()
  const [params, setParams] = useSearchParams()
  const [editing, setEditing] = useState<RevenueItem | null>(null)
  const rawKind = params.get('kind')
  const kind = order.includes(rawKind as RevenueKind) ? rawKind as RevenueKind : undefined
  const rawState = params.get('state')
  const state = rawState === 'all' || rawState === 'scheduled' ? rawState : 'due'
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const owner = params.get('owner') || undefined
  const search = params.get('search') || ''
  const [searchDraft, setSearchDraft] = useState(search)
  const filters = { kind, state, offset, owner, search } as const
  const allowed = ['owner', 'manager', 'tech', 'platform_admin'].includes(role ?? '')
  const query = useQuery({ queryKey: ['revenue-control', tenantId, filters], queryFn: () => getRevenueControl(filters).then(r => r.data), enabled: allowed, refetchInterval: 60000 })
  const data = query.data
  function filter(key: string, value: string) {
    setParams(previous => { const next = new URLSearchParams(previous); next.delete('offset'); if (value) next.set(key, value); else next.delete(key); return next })
  }
  return <div className="p-4 sm:p-6 space-y-5" style={{ color: 'var(--ms-text)' }}>
    <MobileServicesSubNav />
    <PageHeader title="Revenue control" action={<Button variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}><RefreshCw size={16} />Refresh</Button>} />
    <p className="text-sm max-w-3xl" style={muted}>Work through the next action for every quote, booking and unpaid invoice. Scheduled follow-ups return automatically; items clear when their source records are resolved.</p>
    {!allowed ? <EmptyState message="Revenue control is available to technicians, managers and owners." /> : <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Select label="Queue" aria-label="Queue" value={state} onChange={e => filter('state', e.target.value)}><option value="due">Due now</option><option value="scheduled">Scheduled follow-ups</option><option value="all">All open items</option></Select>
        <Select label="Responsible person" aria-label="Responsible person" value={owner ?? ''} onChange={e => filter('owner', e.target.value)}><option value="">Everyone</option><option value="me">Assigned to me</option><option value="unassigned">Unassigned</option>{data?.owners.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</Select>
        <form className="flex items-end gap-2" onSubmit={e => { e.preventDefault(); filter('search', searchDraft) }}><Input label="Find a job or customer" aria-label="Find a job or customer" value={searchDraft} onChange={e => setSearchDraft(e.target.value)} maxLength={200} /><Button type="submit" variant="secondary">Find</Button></form>
      </div>
      {query.isError && <Card><div role="alert" className="p-4"><p>{getApiErrorMessage(query.error, 'Could not load revenue control.')}</p><Button variant="secondary" onClick={() => void query.refetch()}>Try again</Button></div></Card>}
      {query.isLoading && <Spinner />}
      {data && <>
        {query.isError && <p role="status" style={muted}>The figures below are from the last successful refresh.</p>}
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          {order.map(k => { const bucket = data.buckets.find(b => b.kind === k); return <button key={k} aria-pressed={kind === k} onClick={() => filter('kind', kind === k ? '' : k)} className="rounded-xl border p-4 text-left min-w-0 transition-colors" style={{ backgroundColor: kind === k ? 'var(--ms-accent-pop)' : 'var(--ms-surface)', borderColor: kind === k ? 'var(--ms-accent)' : 'var(--ms-border)' }}>
            <span className="block text-xs font-semibold" style={muted}>{labels[k]}</span><span className="block text-2xl font-semibold mt-2 tabular-nums">{bucket?.count ?? 0}</span>
            <span className="block text-sm mt-1 tabular-nums">{formatCents(bucket?.amount_cents ?? 0)}</span><span className="block text-xs mt-2" style={muted}>{bucket?.due_count ?? 0} due now{bucket?.unknown_amount_count ? ` · ${bucket.unknown_amount_count} unpriced` : ''}</span>
          </button> })}
        </div>
        <p className="text-xs" style={muted}>Cards show all open items for the selected person and search, including scheduled follow-ups. Amounts are AUD and are not additive across categories.</p>
        <div className="flex flex-wrap justify-between items-center gap-3"><h2 className="text-lg font-semibold">{kind ? labels[kind] : 'Action queue'} <span style={muted}>({data.total})</span></h2>{kind && <Button variant="secondary" onClick={() => filter('kind', '')}>All categories</Button>}</div>
        {!data.items.length && <EmptyState message={state === 'due' ? 'Nothing needs action in this view. Check scheduled follow-ups or change your filters.' : 'No open items match these filters.'} />}
        <div className="space-y-3">{data.items.map(item => <Card key={item.key}><article className="p-4 sm:p-5 space-y-3">
          <div className="flex flex-wrap gap-3 justify-between"><div className="min-w-0"><div className="flex flex-wrap gap-2 text-xs mb-1"><span className="font-semibold" style={{ color: item.priority === 'high' ? 'var(--ms-error)' : 'var(--ms-text-muted)' }}>{item.priority === 'high' ? 'High priority · ' : ''}{labels[item.kind]}</span><span style={muted}>{item.age_days} days old</span></div><Link className="font-semibold underline underline-offset-4 break-words" to={`/auto-key/${item.job_id}`}>{item.job_number} · {item.title}</Link><p className="text-sm mt-1" style={muted}>{item.customer_name}</p></div><div className="text-right"><p className="text-xl font-semibold tabular-nums">{item.amount_cents === null ? 'Unpriced' : formatCents(item.amount_cents)}</p>{item.deposit_cents > 0 && <p className="text-xs" style={muted}>Deposit recorded: {formatCents(item.deposit_cents)}<br />Reconciliation needed</p>}</div></div>
          <p className="text-sm font-medium">{item.next_action}</p>
          {item.note && <p className="text-sm whitespace-pre-wrap break-words rounded-lg p-3" style={{ backgroundColor: 'var(--ms-bg)' }}>{item.note}</p>}
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="text-xs space-y-1" style={muted}><p>Owner: {item.owner_name ?? 'Unassigned'}</p><p className="flex gap-1 items-center"><Clock3 size={12} />{item.due ? 'Due now' : `Returns ${dateTime(item.due_at, data.timezone)}`}</p>{item.last_contact_at && <p>Last contact: {dateTime(item.last_contact_at, data.timezone)}</p>}</div><div className="flex gap-2 flex-wrap"><Link className="inline-flex min-h-11 items-center gap-1 text-sm px-3 underline" to={`/auto-key/${item.job_id}`}>Open job <ArrowUpRight size={14} /></Link><Button variant="secondary" onClick={() => setEditing(item)}>Manage follow-up</Button></div></div>
        </article></Card>)}</div>
        <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs" style={muted}>{data.total ? `${offset + 1}–${Math.min(offset + data.limit, data.total)} of ${data.total}` : '0 items'} · Updated {dateTime(data.generated_at, data.timezone)} ({data.timezone})</p><div className="flex gap-2"><Button variant="secondary" disabled={offset === 0} onClick={() => filter('offset', String(Math.max(0, offset - data.limit)))}>Previous</Button><Button variant="secondary" disabled={offset + data.limit >= data.total} onClick={() => filter('offset', String(offset + data.limit))}>Next</Button></div></div>
        <details className="rounded-xl border p-4 text-sm" style={{ borderColor: 'var(--ms-border)' }}><summary className="cursor-pointer font-semibold">How to read these figures</summary><ul className="list-disc pl-5 space-y-2 mt-3" style={muted}>{data.warnings.map(w => <li key={w}>{w}</li>)}</ul><p className="mt-3" style={muted}>Follow-up dates are shown in {data.timezone}. Source resolution removes an item from both due and scheduled views. Notes are recorded in the job's audit history.</p></details>
      </>}
    </>}
    {editing && data && <FollowUpModal key={editing.key} item={editing} owners={data.owners} timeZone={data.timezone} onClose={() => setEditing(null)} />}
  </div>
}
