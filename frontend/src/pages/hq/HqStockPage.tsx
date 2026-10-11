import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import {
  getApiErrorMessage,
  hqAdjustStock, hqCreateLocation, hqCreateModel, hqCreatePart, hqCreateTransfer, hqGetModelParts, hqImportPurchases,
  hqListLocations, hqListModels, hqListParts, hqListTransfers, hqReceiveTransfer, hqSetModelParts, hqStockLevels, hqStockSummary,
  hqSyncStock, hqUpdatePart,
  type PurchaseImportRow, type StockLocation, type StockPart, type StockTransferRow,
} from '@/lib/api'

const TABS = ['Overview', 'Catalogue', 'Stock', 'Transfers', 'Sales'] as const
type Tab = (typeof TABS)[number]
const PART_TYPES = ['footbed', 'sole', 'upper', 'buckle', 'liner', 'other']
const LOCATION_KINDS = ['workshop', 'store', 'warehouse']

const muted = { color: 'var(--ms-text-muted)' } as const
const errorStyle = { color: 'var(--ms-error)' } as const

function Notice({ error }: { error: unknown }) {
  if (!error) return null
  return <p role="alert" className="text-sm" style={errorStyle}>{getApiErrorMessage(error, 'Something went wrong.')}</p>
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide" style={muted}>{label}</p>
      <p className="text-2xl font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>{value}</p>
    </Card>
  )
}

function Overview() {
  const summary = useQuery({ queryKey: ['hq-stock-summary'], queryFn: () => hqStockSummary().then(r => r.data) })
  if (summary.isLoading) return <Spinner />
  if (summary.isError || !summary.data) return <Notice error={summary.error} />
  const s = summary.data
  return (
    <div className="space-y-4">
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat label="Locations" value={s.locations} />
        <Stat label="Low stock lines" value={s.low_stock.length} />
        <Stat label="Transfers on the way" value={s.in_transit_transfers} />
        <Stat label="Parts used (30 days)" value={s.parts_used_30d.reduce((n, p) => n + p.quantity, 0)} />
      </div>
      <Card className="p-4 space-y-2">
        <h2 className="font-semibold">Low stock</h2>
        {s.low_stock.length === 0 ? <EmptyState message="Nothing is at or below its reorder level." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left" style={muted}><th className="py-1">Location</th><th>Part</th><th>SKU</th><th>On hand</th><th>Reorder at</th></tr></thead>
            <tbody>
              {s.low_stock.map(l => (
                <tr key={`${l.location_id}-${l.part_id}`} className="border-t" style={{ borderColor: 'var(--ms-border)' }}>
                  <td className="py-1">{l.location_name}</td><td>{l.name}</td><td>{l.sku}</td>
                  <td><Badge variant={l.quantity <= 0 ? 'danger' : 'warning'}>{l.quantity}</Badge></td><td>{l.reorder_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card className="p-4 space-y-2">
        <h2 className="font-semibold">Most used parts (30 days)</h2>
        {s.parts_used_30d.length === 0 ? <EmptyState message="No parts have been used on repairs yet." /> : (
          <ul className="text-sm space-y-1">
            {s.parts_used_30d.map(p => <li key={p.sku}>{p.name} <span style={muted}>({p.sku})</span> · {p.quantity}</li>)}
          </ul>
        )}
      </Card>
    </div>
  )
}

function PartRow({ part }: { part: StockPart }) {
  const qc = useQueryClient()
  const [reorder, setReorder] = useState(String(part.reorder_level))
  const save = useMutation({
    mutationFn: () => hqUpdatePart(part.id, { reorder_level: Number(reorder) || 0 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hq-stock-parts'] }),
  })
  return (
    <tr className="border-t" style={{ borderColor: 'var(--ms-border)' }}>
      <td className="py-1">{part.sku}</td><td>{part.name}</td><td>{part.part_type ?? '–'}</td>
      <td className="w-40">
        <div className="flex gap-1 items-center">
          <input aria-label={`Reorder level for ${part.sku}`} className="h-8 w-16 border px-2 text-sm" type="number" min="0" value={reorder} onChange={e => setReorder(e.target.value)} />
          {String(part.reorder_level) !== reorder && <Button size="sm" onClick={() => save.mutate()}>Save</Button>}
        </div>
      </td>
    </tr>
  )
}

function ModelPartsEditor({ modelId, parts }: { modelId: string; parts: StockPart[] }) {
  const qc = useQueryClient()
  const current = useQuery({ queryKey: ['hq-stock-model-parts', modelId], queryFn: () => hqGetModelParts(modelId).then(r => r.data) })
  const [partId, setPartId] = useState('')
  const [size, setSize] = useState('')
  const [qty, setQty] = useState('1')
  const save = useMutation({
    mutationFn: (lines: Array<{ part_id: string; size: string | null; quantity: number }>) => hqSetModelParts(modelId, lines),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hq-stock-model-parts', modelId] }),
  })
  if (current.isLoading) return <Spinner />
  const rows = (current.data ?? []).map(r => ({ part_id: r.part_id, size: r.size, quantity: r.quantity }))
  return (
    <div className="space-y-2 mt-2">
      {rows.length === 0 && <p className="text-sm" style={muted}>No parts listed for this model yet.</p>}
      <ul className="text-sm space-y-1">
        {(current.data ?? []).map((r, i) => (
          <li key={`${r.part_id}-${r.size}`} className="flex items-center gap-2">
            <span>{r.quantity} × {r.name} <span style={muted}>({r.sku}) {r.size ? `· size ${r.size}` : '· all sizes'}</span></span>
            <Button size="sm" variant="secondary" onClick={() => save.mutate(rows.filter((_, j) => j !== i))}>Remove</Button>
          </li>
        ))}
      </ul>
      <form
        className="flex flex-wrap gap-2 items-end"
        onSubmit={e => { e.preventDefault(); if (!partId) return; save.mutate([...rows, { part_id: partId, size: size.trim() || null, quantity: Number(qty) || 1 }]); setPartId(''); setSize(''); setQty('1') }}
      >
        <Select label="Part" value={partId} onChange={e => setPartId(e.target.value)}>
          <option value="">Choose a part</option>
          {parts.filter(p => p.active).map(p => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
        </Select>
        <Input label="Size (blank = all)" value={size} onChange={e => setSize(e.target.value)} />
        <Input label="Qty" type="number" min="1" value={qty} onChange={e => setQty(e.target.value)} />
        <Button type="submit" disabled={!partId || save.isPending}>Add to list</Button>
      </form>
      <Notice error={save.error} />
    </div>
  )
}

function Catalogue() {
  const qc = useQueryClient()
  const parts = useQuery({ queryKey: ['hq-stock-parts'], queryFn: () => hqListParts().then(r => r.data) })
  const models = useQuery({ queryKey: ['hq-stock-models'], queryFn: () => hqListModels().then(r => r.data) })
  const [open, setOpen] = useState<string | null>(null)
  const [part, setPart] = useState({ sku: '', name: '', part_type: '', cost: '', reorder: '' })
  const [model, setModel] = useState({ name: '', category: '' })
  const addPart = useMutation({
    mutationFn: () => hqCreatePart({
      sku: part.sku.trim(), name: part.name.trim(), part_type: part.part_type || undefined,
      cost_cents: Math.round((Number(part.cost) || 0) * 100), reorder_level: Number(part.reorder) || 0,
    }),
    onSuccess: () => { setPart({ sku: '', name: '', part_type: '', cost: '', reorder: '' }); qc.invalidateQueries({ queryKey: ['hq-stock-parts'] }) },
  })
  const addModel = useMutation({
    mutationFn: () => hqCreateModel({ name: model.name.trim(), category: model.category || undefined }),
    onSuccess: () => { setModel({ name: '', category: '' }); qc.invalidateQueries({ queryKey: ['hq-stock-models'] }) },
  })
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-4 space-y-3">
        <h2 className="font-semibold">Parts</h2>
        <form className="grid grid-cols-2 gap-2" onSubmit={e => { e.preventDefault(); addPart.mutate() }}>
          <Input label="SKU / barcode" value={part.sku} onChange={e => setPart({ ...part, sku: e.target.value })} />
          <Input label="Name" value={part.name} onChange={e => setPart({ ...part, name: e.target.value })} />
          <Select label="Type" value={part.part_type} onChange={e => setPart({ ...part, part_type: e.target.value })}>
            <option value="">Select type</option>
            {PART_TYPES.map(t => <option key={t}>{t}</option>)}
          </Select>
          <Input label="Cost ($)" type="number" min="0" step="0.01" value={part.cost} onChange={e => setPart({ ...part, cost: e.target.value })} />
          <Input label="Reorder at" type="number" min="0" value={part.reorder} onChange={e => setPart({ ...part, reorder: e.target.value })} />
          <div className="flex items-end"><Button type="submit" disabled={!part.sku.trim() || !part.name.trim() || addPart.isPending}>Add part</Button></div>
        </form>
        <Notice error={addPart.error} />
        {parts.isLoading ? <Spinner /> : (parts.data ?? []).length === 0 ? <EmptyState message="No parts yet." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left" style={muted}><th className="py-1">SKU</th><th>Name</th><th>Type</th><th>Reorder at</th></tr></thead>
            <tbody>{(parts.data ?? []).map(p => <PartRow key={p.id} part={p} />)}</tbody>
          </table>
        )}
      </Card>
      <Card className="p-4 space-y-3">
        <h2 className="font-semibold">Models and their parts</h2>
        <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); addModel.mutate() }}>
          <Input label="Model" value={model.name} onChange={e => setModel({ ...model, name: e.target.value })} placeholder="e.g. Arizona" />
          <Select label="Category" value={model.category} onChange={e => setModel({ ...model, category: e.target.value })}>
            <option value="">Select</option>
            {['sandal', 'clog', 'shoe', 'boot', 'slipper', 'kids', 'work'].map(c => <option key={c}>{c}</option>)}
          </Select>
          <Button type="submit" disabled={!model.name.trim() || addModel.isPending}>Add model</Button>
        </form>
        <Notice error={addModel.error} />
        {models.isLoading ? <Spinner /> : (models.data ?? []).length === 0 ? <EmptyState message="No models yet." /> : (
          <ul className="space-y-2">
            {(models.data ?? []).map(m => (
              <li key={m.id} className="border-t pt-2" style={{ borderColor: 'var(--ms-border)' }}>
                <button className="text-left font-medium" onClick={() => setOpen(open === m.id ? null : m.id)}>
                  {m.name} <span className="text-xs" style={muted}>{m.category ?? ''} · {open === m.id ? 'hide parts' : 'edit parts'}</span>
                </button>
                {open === m.id && <ModelPartsEditor modelId={m.id} parts={parts.data ?? []} />}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function parseCsvPairs(text: string): Array<{ sku: string; quantity: number }> {
  return text.split('\n').map(line => line.trim()).filter(Boolean).map(line => {
    const [sku, qty] = line.split(/[,\t;]/).map(v => v.trim())
    return { sku, quantity: Number(qty) }
  }).filter(r => r.sku && Number.isFinite(r.quantity) && r.quantity >= 0)
}

function StockTab() {
  const qc = useQueryClient()
  const locations = useQuery({ queryKey: ['hq-stock-locations'], queryFn: () => hqListLocations().then(r => r.data) })
  const [locationId, setLocationId] = useState('')
  const levels = useQuery({ queryKey: ['hq-stock-levels', locationId], queryFn: () => hqStockLevels(locationId || undefined).then(r => r.data) })
  const [newLoc, setNewLoc] = useState({ name: '', kind: 'workshop' })
  const [scan, setScan] = useState({ sku: '', qty: '1' })
  const [feed, setFeed] = useState('')
  const [feedResult, setFeedResult] = useState('')
  const refresh = () => { qc.invalidateQueries({ queryKey: ['hq-stock-levels'] }); qc.invalidateQueries({ queryKey: ['hq-stock-summary'] }) }
  const addLoc = useMutation({
    mutationFn: () => hqCreateLocation({ name: newLoc.name.trim(), kind: newLoc.kind }),
    onSuccess: () => { setNewLoc({ name: '', kind: 'workshop' }); qc.invalidateQueries({ queryKey: ['hq-stock-locations'] }) },
  })
  const receive = useMutation({
    mutationFn: () => hqAdjustStock({ location_id: locationId, sku: scan.sku.trim(), quantity: Number(scan.qty) || 1, kind: 'receive' }),
    onSuccess: () => { setScan({ sku: '', qty: '1' }); refresh() },
  })
  const sync = useMutation({
    mutationFn: () => hqSyncStock({ location_id: locationId, rows: parseCsvPairs(feed) }),
    onSuccess: ({ data }) => {
      setFeedResult(`${data.updated} counts changed.${data.unknown_skus.length ? ` Unknown SKUs: ${data.unknown_skus.join(', ')}` : ''}`)
      refresh()
    },
  })
  const locs: StockLocation[] = locations.data ?? []
  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <h2 className="font-semibold">Locations</h2>
        <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); addLoc.mutate() }}>
          <Input label="Name" value={newLoc.name} onChange={e => setNewLoc({ ...newLoc, name: e.target.value })} placeholder="e.g. Melbourne workshop" />
          <Select label="Kind" value={newLoc.kind} onChange={e => setNewLoc({ ...newLoc, kind: e.target.value })}>
            {LOCATION_KINDS.map(k => <option key={k}>{k}</option>)}
          </Select>
          <Button type="submit" disabled={!newLoc.name.trim() || addLoc.isPending}>Add location</Button>
        </form>
        <Notice error={addLoc.error} />
        <p className="text-sm" style={muted}>{locs.length === 0 ? 'No locations yet.' : locs.map(l => `${l.name} (${l.kind})`).join(' · ')}</p>
        <p className="text-xs" style={muted}>To let a workshop or shop's own staff scan stock, link the location to their shop account (ask support to set this up).</p>
      </Card>
      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap gap-2 items-end">
          <Select label="Location" value={locationId} onChange={e => setLocationId(e.target.value)}>
            <option value="">All locations</option>
            {locs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
        </div>
        {locationId && (
          <>
            <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); receive.mutate() }}>
              <Input label="Scan or type SKU to receive" value={scan.sku} onChange={e => setScan({ ...scan, sku: e.target.value })} autoFocus />
              <Input label="Qty" type="number" min="1" value={scan.qty} onChange={e => setScan({ ...scan, qty: e.target.value })} />
              <Button type="submit" disabled={!scan.sku.trim() || receive.isPending}>Receive</Button>
            </form>
            <Notice error={receive.error} />
            <details>
              <summary className="text-sm cursor-pointer" style={muted}>Set counts from an inventory export (one "SKU, quantity" per line)</summary>
              <textarea className="mt-2 w-full border p-2 text-sm" rows={4} value={feed} onChange={e => setFeed(e.target.value)} placeholder={'FB-ARI-41, 12\nBK-01, 40'} />
              <Button disabled={!feed.trim() || sync.isPending} onClick={() => sync.mutate()}>Apply counts</Button>
              {feedResult && <p className="text-sm mt-1">{feedResult}</p>}
              <Notice error={sync.error} />
            </details>
          </>
        )}
        {levels.isLoading ? <Spinner /> : (levels.data ?? []).length === 0 ? <EmptyState message="No stock recorded yet." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left" style={muted}><th className="py-1">Location</th><th>Part</th><th>SKU</th><th>On hand</th></tr></thead>
            <tbody>
              {(levels.data ?? []).map(l => (
                <tr key={`${l.location_id}-${l.part_id}`} className="border-t" style={{ borderColor: 'var(--ms-border)' }}>
                  <td className="py-1">{l.location_name}</td><td>{l.name}</td><td>{l.sku}</td>
                  <td><Badge variant={l.quantity < 0 ? 'danger' : l.low ? 'warning' : 'success'}>{l.quantity}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}

function TransferCard({ t, names, onReceive }: { t: StockTransferRow; names: Map<string, string>; onReceive: () => void }) {
  return (
    <li className="border-t pt-2 text-sm" style={{ borderColor: 'var(--ms-border)' }}>
      <div className="flex items-center gap-2 flex-wrap">
        <strong>{names.get(t.from_location_id) ?? '?'} → {names.get(t.to_location_id) ?? '?'}</strong>
        <Badge variant={t.status === 'in_transit' ? 'warning' : 'success'}>{t.status === 'in_transit' ? 'On the way' : 'Received'}</Badge>
        <span style={muted}>{new Date(t.created_at).toLocaleDateString()}</span>
        {t.status === 'in_transit' && <Button size="sm" onClick={onReceive}>Receive all</Button>}
      </div>
      <p style={muted}>{t.lines.map(l => `${l.quantity} × ${l.name}${t.status === 'received' && l.received_quantity !== l.quantity ? ` (got ${l.received_quantity})` : ''}`).join(', ')}</p>
    </li>
  )
}

function Transfers() {
  const qc = useQueryClient()
  const locations = useQuery({ queryKey: ['hq-stock-locations'], queryFn: () => hqListLocations().then(r => r.data) })
  const transfers = useQuery({ queryKey: ['hq-stock-transfers'], queryFn: () => hqListTransfers().then(r => r.data) })
  const [form, setForm] = useState({ from: '', to: '', sku: '', qty: '1' })
  const [lines, setLines] = useState<Array<{ sku: string; quantity: number }>>([])
  const names = new Map((locations.data ?? []).map(l => [l.id, l.name]))
  const refresh = () => { qc.invalidateQueries({ queryKey: ['hq-stock-transfers'] }); qc.invalidateQueries({ queryKey: ['hq-stock-levels'] }); qc.invalidateQueries({ queryKey: ['hq-stock-summary'] }) }
  const send = useMutation({
    mutationFn: () => hqCreateTransfer({ from_location_id: form.from, to_location_id: form.to, lines }),
    onSuccess: () => { setLines([]); refresh() },
  })
  const receive = useMutation({ mutationFn: (id: string) => hqReceiveTransfer(id), onSuccess: refresh })
  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <h2 className="font-semibold">Send stock</h2>
        <div className="flex flex-wrap gap-2 items-end">
          <Select label="From" value={form.from} onChange={e => setForm({ ...form, from: e.target.value })}>
            <option value="">Choose</option>{(locations.data ?? []).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
          <Select label="To" value={form.to} onChange={e => setForm({ ...form, to: e.target.value })}>
            <option value="">Choose</option>{(locations.data ?? []).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
        </div>
        <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); if (form.sku.trim()) { setLines([...lines, { sku: form.sku.trim(), quantity: Number(form.qty) || 1 }]); setForm({ ...form, sku: '', qty: '1' }) } }}>
          <Input label="Scan or type SKU" value={form.sku} onChange={e => setForm({ ...form, sku: e.target.value })} />
          <Input label="Qty" type="number" min="1" value={form.qty} onChange={e => setForm({ ...form, qty: e.target.value })} />
          <Button type="submit" variant="secondary" disabled={!form.sku.trim()}>Add line</Button>
        </form>
        {lines.length > 0 && <p className="text-sm">{lines.map(l => `${l.quantity} × ${l.sku}`).join(', ')}</p>}
        <Button disabled={!form.from || !form.to || lines.length === 0 || send.isPending} onClick={() => send.mutate()}>Send</Button>
        <Notice error={send.error} />
      </Card>
      <Card className="p-4 space-y-2">
        <h2 className="font-semibold">Transfers</h2>
        {transfers.isLoading ? <Spinner /> : (transfers.data ?? []).length === 0 ? <EmptyState message="No transfers yet." /> : (
          <ul className="space-y-2">{(transfers.data ?? []).map(t => <TransferCard key={t.id} t={t} names={names} onReceive={() => receive.mutate(t.id)} />)}</ul>
        )}
        <Notice error={receive.error} />
      </Card>
    </div>
  )
}

/** Header names an export might use, mapped to our fields. */
const SALES_COLUMNS: Record<string, keyof PurchaseImportRow> = {
  ref: 'purchase_ref', receipt: 'purchase_ref', order: 'purchase_ref', purchase_ref: 'purchase_ref',
  date: 'purchase_date', purchase_date: 'purchase_date', store: 'store', shop: 'store',
  name: 'customer_name', customer: 'customer_name', customer_name: 'customer_name',
  email: 'customer_email', customer_email: 'customer_email', phone: 'customer_phone', mobile: 'customer_phone', customer_phone: 'customer_phone',
  model: 'model_name', style: 'model_name', model_name: 'model_name', size: 'size',
}

export function parseSalesCsv(text: string): PurchaseImportRow[] {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
  if (lines.length < 2) return []
  const split = (line: string) => line.split(line.includes('\t') ? '\t' : ',').map(v => v.trim().replace(/^"|"$/g, ''))
  const header = split(lines[0]).map(h => SALES_COLUMNS[h.toLowerCase().replace(/[\s-]+/g, '_')])
  const rows: PurchaseImportRow[] = []
  for (const line of lines.slice(1)) {
    const row: Record<string, string> = {}
    split(line).forEach((value, i) => { const key = header[i]; if (key && value) row[key] = value })
    if (row.purchase_ref) rows.push(row as unknown as PurchaseImportRow)
  }
  return rows
}

function Sales() {
  const [text, setText] = useState('')
  const [result, setResult] = useState('')
  const rows = parseSalesCsv(text)
  const imp = useMutation({
    mutationFn: () => hqImportPurchases(rows),
    onSuccess: ({ data }) => { setResult(`${data.created} added, ${data.updated} updated.`); setText('') },
  })
  return (
    <Card className="p-4 space-y-3">
      <h2 className="font-semibold">Sales from your branded shops</h2>
      <p className="text-sm" style={muted}>
        Paste an export from your till (CSV with a header row). Columns recognised: ref/receipt/order, date, store, name, email, phone, model, size.
        Shop staff can then search by name, email, phone or receipt number when a customer brings a pair in for repair.
        Re-importing the same receipt number updates it.
      </p>
      <textarea className="w-full border p-2 text-sm" rows={8} value={text} onChange={e => setText(e.target.value)} placeholder={'receipt,date,store,name,email,phone,model,size\nR-1001,2026-03-01,Melbourne,Dana Smith,dana@example.com,0400111222,Arizona,41'} />
      <Button disabled={rows.length === 0 || imp.isPending} onClick={() => imp.mutate()}>Import {rows.length} sale{rows.length === 1 ? '' : 's'}</Button>
      {result && <p className="text-sm">{result}</p>}
      <Notice error={imp.error} />
    </Card>
  )
}

/** Parts catalogue, stock by location, transfers and sales lookup for an HQ with the stock module on. */
export default function HqStockPage() {
  const [tab, setTab] = useState<Tab>('Overview')
  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHeader title="Stock" />
      <div className="flex gap-1 flex-wrap" role="tablist">
        {TABS.map(t => (
          <Button key={t} role="tab" aria-selected={tab === t} variant={tab === t ? 'primary' : 'secondary'} onClick={() => setTab(t)}>{t}</Button>
        ))}
      </div>
      {tab === 'Overview' && <Overview />}
      {tab === 'Catalogue' && <Catalogue />}
      {tab === 'Stock' && <StockTab />}
      {tab === 'Transfers' && <Transfers />}
      {tab === 'Sales' && <Sales />}
    </div>
  )
}
