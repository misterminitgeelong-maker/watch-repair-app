import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createHqInvoiceDraft, downloadHqInvoicePdf, getApiErrorMessage, getHqBillingSettings, getHqInvoice, issueHqInvoice,
  listHqInvoices, listPlatformHqs, saveHqBillingSettings, voidHqInvoice, type HqInvoiceRow,
} from '@/lib/api'
import { Spinner } from '@/components/ui'
import { formatCents } from '@/lib/money'

const STATUS_LABEL: Record<HqInvoiceRow['status'], string> = { draft: 'Draft', issued: 'Sent, awaiting payment', paid: 'Paid', void: 'Void' }
const REASON_LABEL: Record<string, string> = { hq: 'HQ itself', not_operator: 'Retail shop', billing_exempt: 'Billing exempt', inactive: 'Inactive' }

function lastMonth() {
  const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

async function savePdf(inv: HqInvoiceRow) {
  const res = await downloadHqInvoicePdf(inv.id)
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a'); a.href = url; a.download = `${inv.invoice_number}.pdf`; a.click(); URL.revokeObjectURL(url)
}

function InvoiceDetail({ id, onChanged }: { id: string; onChanged: () => void }) {
  const [error, setError] = useState('')
  const q = useQuery({ queryKey: ['platform-hq-invoice', id], queryFn: () => getHqInvoice(id).then(r => r.data) })
  const done = () => { setError(''); void q.refetch(); onChanged() }
  const fail = (err: unknown) => setError(getApiErrorMessage(err, 'That did not work.'))
  const issue = useMutation({ mutationFn: () => issueHqInvoice(id), onSuccess: done, onError: fail })
  const doVoid = useMutation({ mutationFn: () => voidHqInvoice(id), onSuccess: done, onError: fail })
  if (q.isLoading) return <Spinner />
  const inv = q.data
  if (!inv) return <p role="alert">Could not load this invoice.</p>
  return <div className="mt-3 space-y-3">
    <p className="text-sm">{inv.invoice_number} · {inv.operator_count} operator{inv.operator_count === 1 ? '' : 's'} · {formatCents(inv.subtotal_ex_gst_cents)} + GST {formatCents(inv.gst_cents)} = <strong>{formatCents(inv.total_inc_gst_cents)}</strong> · {STATUS_LABEL[inv.status]}</p>
    <div className="overflow-x-auto"><table className="w-full text-sm">
      <thead><tr className="text-left"><th>Shop</th><th>Operator</th><th className="text-right">Core</th><th className="text-right">Routing</th><th className="text-right">Prospecting</th><th className="text-right">GST</th></tr></thead>
      <tbody>{inv.snapshot.lines.map(l => <tr key={l.tenant_id}><td>{l.shop_number ?? ''}</td><td>{l.name}</td><td className="text-right">{formatCents(l.core_cents)}</td><td className="text-right">{formatCents(l.routing_cents)}</td><td className="text-right">{formatCents(l.prospecting_cents)}</td><td className="text-right">{formatCents(l.gst_cents)}</td></tr>)}</tbody>
    </table></div>
    {inv.snapshot.excluded.length > 0 && <p className="text-xs">Not billed: {inv.snapshot.excluded.map(e => `${e.name} (${REASON_LABEL[e.reason] ?? e.reason})`).join(', ')}</p>}
    <div className="flex flex-wrap gap-2">
      <button className="console-button" onClick={() => void savePdf(inv)}>Download PDF</button>
      {inv.stripe_hosted_url && <a className="console-button" href={inv.stripe_hosted_url} target="_blank" rel="noreferrer">Open Stripe payment page</a>}
      {inv.status === 'draft' && <button className="console-button primary" disabled={issue.isPending} onClick={() => { if (window.confirm(`Email this ${formatCents(inv.total_inc_gst_cents)} invoice to the HQ now?`)) issue.mutate() }}>{issue.isPending ? 'Sending…' : 'Issue and email via Stripe'}</button>}
      {(inv.status === 'draft' || inv.status === 'issued') && <button className="console-button" disabled={doVoid.isPending} onClick={() => { if (window.confirm('Void this invoice?')) doVoid.mutate() }}>Void</button>}
    </div>
    {error && <p className="console-error" role="alert">{error}</p>}
  </div>
}

export default function PlatformHqBillingPanel() {
  const cache = useQueryClient()
  const hqs = useQuery({ queryKey: ['platform-hqs'], queryFn: () => listPlatformHqs().then(r => r.data) })
  const [hqId, setHqId] = useState('')
  const [month, setMonth] = useState(lastMonth())
  const [openId, setOpenId] = useState<string | null>(null)
  const [routing, setRouting] = useState(false)
  const [prospecting, setProspecting] = useState(false)
  const [email, setEmail] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const list = hqs.data?.hqs ?? []
  const selected = hqId || list[0]?.parent_account_id || ''
  const settings = useQuery({ queryKey: ['platform-hq-billing-settings', selected], enabled: !!selected, queryFn: () => getHqBillingSettings(selected).then(r => r.data) })
  const invoices = useQuery({ queryKey: ['platform-hq-invoices', selected], enabled: !!selected, queryFn: () => listHqInvoices(selected).then(r => r.data.invoices) })
  useEffect(() => {
    const s = settings.data
    if (s) { setRouting(s.routing_addon); setProspecting(s.prospecting_addon); setEmail(s.billing_email_is_default ? '' : s.billing_email) }
  }, [settings.data])
  const refresh = () => void cache.invalidateQueries({ queryKey: ['platform-hq-invoices', selected] })
  const save = useMutation({
    mutationFn: () => saveHqBillingSettings(selected, { routing_addon: routing, prospecting_addon: prospecting, billing_email: email.trim() || null }),
    onSuccess: () => { setError(''); setMsg('Billing settings saved.'); void settings.refetch() },
    onError: err => { setMsg(''); setError(getApiErrorMessage(err, 'Could not save billing settings.')) },
  })
  const draft = useMutation({
    mutationFn: () => createHqInvoiceDraft(selected, month),
    onSuccess: r => { setError(''); setMsg(''); setOpenId(r.data.id); refresh() },
    onError: err => { setMsg(''); setError(getApiErrorMessage(err, 'Could not prepare that invoice.')) },
  })
  if (hqs.isLoading) return <Spinner />
  if (hqs.isError) return <div role="alert">Could not load HQs. <button className="console-button" onClick={() => void hqs.refetch()}>Try again</button></div>
  if (!list.length) return <p>No HQs yet.</p>
  return <div className="space-y-5">
    <section className="console-panel">
      <h2>HQ monthly invoice</h2>
      <p className="console-subtitle">One bundled invoice per HQ per month: A$55 per billable operator, plus Routing and Prospecting add-ons (A$15 each until 28 Feb 2027, A$25 after). HQ-linked, exempt, retail and inactive shops are left off. Amounts are ex-GST; GST is added at 10% (15% for NZ operators).</p>
      <label className="block text-sm mt-3 max-w-sm">HQ
        <select className="block w-full border rounded p-2 mt-1" value={selected} onChange={e => { setHqId(e.target.value); setOpenId(null); setMsg(''); setError('') }}>
          {list.map(h => <option key={h.parent_account_id} value={h.parent_account_id}>{h.display_name}</option>)}
        </select>
      </label>
      <form className="space-y-3 mt-4" onSubmit={e => { e.preventDefault(); save.mutate() }}>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={routing} onChange={e => setRouting(e.target.checked)} />Lead routing add-on</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={prospecting} onChange={e => setProspecting(e.target.checked)} />Prospecting add-on</label>
        </div>
        <label className="block text-sm max-w-sm">Billing email<input className="block w-full border rounded p-2 mt-1" type="email" placeholder={settings.data?.billing_email_is_default ? settings.data.billing_email : 'accounts@example.com'} value={email} onChange={e => setEmail(e.target.value)} /></label>
        <button className="console-button" disabled={save.isPending || settings.isLoading}>{save.isPending ? 'Saving…' : 'Save billing settings'}</button>
      </form>
      <div className="flex flex-wrap items-end gap-3 mt-5">
        <label className="block text-sm">Month<input className="block border rounded p-2 mt-1" type="month" value={month} onChange={e => setMonth(e.target.value)} /></label>
        <button className="console-button primary" disabled={draft.isPending || !month} onClick={() => draft.mutate()}>{draft.isPending ? 'Preparing…' : 'Prepare invoice'}</button>
      </div>
      <p className="text-xs mt-2">Save the add-on settings first: preparing an invoice uses them. Nothing is sent until you press Issue.</p>
      {msg && <p role="status" className="mt-2 text-sm">{msg}</p>}
      {error && <p className="console-error mt-2" role="alert">{error}</p>}
    </section>
    <section className="console-panel">
      <h2>Invoices</h2>
      {invoices.isLoading && <Spinner />}
      {invoices.data && !invoices.data.length && <p>No invoices yet.</p>}
      <div className="mt-3 space-y-3">
        {(invoices.data ?? []).map(inv => <div key={inv.id} className="border-b pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><strong>{inv.billing_month}</strong> · {formatCents(inv.total_inc_gst_cents)} inc GST <span className="text-sm">· {STATUS_LABEL[inv.status]}</span></div>
            <button className="console-button" onClick={() => setOpenId(openId === inv.id ? null : inv.id)}>{openId === inv.id ? 'Hide' : 'View'}</button>
          </div>
          {openId === inv.id && <InvoiceDetail id={inv.id} onChanged={refresh} />}
        </div>)}
      </div>
    </section>
  </div>
}
