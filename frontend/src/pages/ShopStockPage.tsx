import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import {
  getApiErrorMessage, shopAdjustStock, shopCreateTransfer, shopListTransfers, shopReceiveTransfer, shopStockLevels, shopStockLocations,
  type StockTransferRow,
} from '@/lib/api'

const muted = { color: 'var(--ms-text-muted)' } as const

function Notice({ error }: { error: unknown }) {
  if (!error) return null
  return <p role="alert" className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(error, 'Something went wrong.')}</p>
}

function lineText(t: StockTransferRow) {
  return t.lines.map(l => `${l.quantity} × ${l.name || l.sku}`).join(', ')
}

export default function ShopStockPage() {
  const qc = useQueryClient()
  const locations = useQuery({ queryKey: ['shop-stock-locations'], queryFn: () => shopStockLocations().then(r => r.data) })
  const levels = useQuery({ queryKey: ['shop-stock-levels'], queryFn: () => shopStockLevels().then(r => r.data) })
  const transfers = useQuery({ queryKey: ['shop-stock-transfers'], queryFn: () => shopListTransfers().then(r => r.data) })
  const all = locations.data ?? []
  const mine = all.filter(l => l.mine)
  const names = new Map(all.map(l => [l.id, l.name]))
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['shop-stock-levels'] })
    qc.invalidateQueries({ queryKey: ['shop-stock-transfers'] })
  }

  const [adj, setAdj] = useState({ location: '', sku: '', qty: '1', kind: 'receive' as 'receive' | 'adjust' })
  const adjust = useMutation({
    mutationFn: () => shopAdjustStock({ location_id: adj.location || mine[0]?.id, sku: adj.sku.trim(), quantity: Number(adj.qty), kind: adj.kind }),
    onSuccess: () => { setAdj({ ...adj, sku: '', qty: '1' }); refresh() },
  })

  const [form, setForm] = useState({ from: '', to: '', sku: '', qty: '1' })
  const [lines, setLines] = useState<Array<{ sku: string; quantity: number }>>([])
  const send = useMutation({
    mutationFn: () => shopCreateTransfer({ from_location_id: form.from || mine[0]?.id, to_location_id: form.to, lines }),
    onSuccess: () => { setLines([]); refresh() },
  })
  const receive = useMutation({ mutationFn: (id: string) => shopReceiveTransfer(id), onSuccess: refresh })

  if (locations.isLoading) return <Spinner />
  const myIds = new Set(mine.map(l => l.id))
  const rows = (levels.data ?? []).filter(r => myIds.has(r.location_id))
  const incoming = (transfers.data ?? []).filter(t => t.status === 'in_transit' && myIds.has(t.to_location_id))

  return (
    <div className="space-y-4">
      <PageHeader title="Parts stock" />
      {mine.length === 0 && <EmptyState message="This shop isn't linked to a stock location yet. Ask support to link it." />}

      {incoming.length > 0 && (
        <Card className="p-4 space-y-2">
          <h2 className="font-semibold">Arriving</h2>
          <ul className="space-y-2">
            {incoming.map(t => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>{lineText(t)} <span style={muted}>from {names.get(t.from_location_id) ?? 'another location'}</span></span>
                <Button size="sm" disabled={receive.isPending} onClick={() => receive.mutate(t.id)}>Receive all</Button>
              </li>
            ))}
          </ul>
          <Notice error={receive.error} />
        </Card>
      )}

      <Card className="p-4 space-y-3">
        <h2 className="font-semibold">My stock</h2>
        {levels.isLoading ? <Spinner /> : rows.length === 0 ? <EmptyState message="No stock recorded here yet." /> : (
          <table className="w-full text-sm">
            <thead><tr style={muted}><th className="text-left">Part</th><th className="text-left">SKU</th><th className="text-right">Qty</th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={`${r.location_id}-${r.part_id}`}>
                  <td>{r.name}</td><td>{r.sku}</td>
                  <td className="text-right">{r.quantity} {r.low && <Badge variant="warning">Low</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {mine.length > 0 && (
        <Card className="p-4 space-y-3">
          <h2 className="font-semibold">Scan stock in or correct a count</h2>
          <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); if (adj.sku.trim()) adjust.mutate() }}>
            {mine.length > 1 && (
              <Select label="Location" value={adj.location} onChange={e => setAdj({ ...adj, location: e.target.value })}>
                {mine.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </Select>
            )}
            <Select label="Action" value={adj.kind} onChange={e => setAdj({ ...adj, kind: e.target.value as 'receive' | 'adjust' })}>
              <option value="receive">Add to stock</option>
              <option value="adjust">Set count to</option>
            </Select>
            <Input label="Scan or type SKU" value={adj.sku} onChange={e => setAdj({ ...adj, sku: e.target.value })} />
            <Input label="Qty" type="number" min="0" value={adj.qty} onChange={e => setAdj({ ...adj, qty: e.target.value })} />
            <Button type="submit" disabled={!adj.sku.trim() || adjust.isPending}>Save</Button>
          </form>
          <Notice error={adjust.error} />
        </Card>
      )}

      {mine.length > 0 && (
        <Card className="p-4 space-y-3">
          <h2 className="font-semibold">Send stock to another location</h2>
          <div className="flex flex-wrap gap-2 items-end">
            {mine.length > 1 && (
              <Select label="From" value={form.from} onChange={e => setForm({ ...form, from: e.target.value })}>
                {mine.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </Select>
            )}
            <Select label="To" value={form.to} onChange={e => setForm({ ...form, to: e.target.value })}>
              <option value="">Choose</option>
              {all.filter(l => !myIds.has(l.id)).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
            </Select>
          </div>
          <form className="flex flex-wrap gap-2 items-end" onSubmit={e => { e.preventDefault(); if (form.sku.trim()) { setLines([...lines, { sku: form.sku.trim(), quantity: Number(form.qty) || 1 }]); setForm({ ...form, sku: '', qty: '1' }) } }}>
            <Input label="Scan or type SKU" value={form.sku} onChange={e => setForm({ ...form, sku: e.target.value })} />
            <Input label="Qty" type="number" min="1" value={form.qty} onChange={e => setForm({ ...form, qty: e.target.value })} />
            <Button type="submit" variant="secondary" disabled={!form.sku.trim()}>Add line</Button>
          </form>
          {lines.length > 0 && <p className="text-sm">{lines.map(l => `${l.quantity} × ${l.sku}`).join(', ')}</p>}
          <Button disabled={!form.to || lines.length === 0 || send.isPending} onClick={() => send.mutate()}>Send</Button>
          <Notice error={send.error} />
        </Card>
      )}
    </div>
  )
}
