import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getApiErrorMessage } from '@/lib/api'
import { assignHubs, messagingNetworks, type HubAssignmentResult } from '@/lib/api/networkCommunity'
import { PARENT_ACCOUNT_SITES_QUERY_KEY } from '@/hooks/useParentAccountSites'
import { Button, Card, Select } from '@/components/ui'

const HUBS = ['VIC', 'NSW', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT', 'NZ']

/** Bulk-assign shops (by shop number) to a messaging hub. Always previews before saving. */
export function HubAssignmentCard() {
  const qc = useQueryClient()
  const networks = useQuery({ queryKey: ['community-networks-admin'], queryFn: messagingNetworks })
  const network = networks.data?.find(n => n.can_publish_network)
  const [open, setOpen] = useState(false)
  const [state, setState] = useState('ACT')
  const [numbers, setNumbers] = useState('')
  const [result, setResult] = useState<HubAssignmentResult | null>(null)
  const list = () => numbers.split(/[\s,;]+/).map(n => n.trim()).filter(Boolean)
  const run = useMutation({
    mutationFn: (dry_run: boolean) => assignHubs(network!.id, { state, shop_numbers: list(), dry_run }),
    onSuccess: r => { setResult(r); if (!r.dry_run) void qc.invalidateQueries({ queryKey: PARENT_ACCOUNT_SITES_QUERY_KEY }) },
  })
  if (!network) return null
  return <Card className="p-4 mb-5">
    <button type="button" className="text-sm font-semibold" aria-expanded={open} onClick={() => setOpen(!open)}>
      {open ? '▾' : '▸'} Assign messaging hubs in bulk
    </button>
    {open && <div className="mt-3 space-y-3">
      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
        Paste shop numbers, pick a hub, then preview. Shops otherwise follow their area, then their region.
      </p>
      <Select value={state} onChange={e => { setState(e.target.value); setResult(null) }} aria-label="Messaging hub">
        {HUBS.map(h => <option key={h} value={h}>{h}</option>)}
        <option value="NONE">No hub (leave out of messaging hubs)</option>
        <option value="AUTO">Automatic (clear override)</option>
      </Select>
      <textarea className="w-full rounded border p-2 text-sm" rows={4} value={numbers} aria-label="Shop numbers"
        placeholder="1046, 1925, 1409 …" onChange={e => { setNumbers(e.target.value); setResult(null) }} />
      <div className="flex gap-2">
        <Button variant="secondary" disabled={!list().length || run.isPending} onClick={() => run.mutate(true)}>Preview</Button>
        <Button disabled={!result?.dry_run || !result.changed.length || run.isPending} onClick={() => run.mutate(false)}>
          Apply to {result?.changed.length ?? 0} shops
        </Button>
      </div>
      {run.error && <p className="text-sm" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(run.error, 'Could not assign hubs.')}</p>}
      {result && <div className="text-sm">
        <p><strong>{result.dry_run ? 'Preview' : 'Saved'}:</strong> {result.changed.length} {result.dry_run ? 'will change' : 'changed'}, {result.unchanged.length} already set{result.not_found.length ? `, ${result.not_found.length} shop numbers not found: ${result.not_found.join(', ')}` : ''}.</p>
        {result.changed.length > 0 && <ul className="list-disc pl-5 max-h-48 overflow-auto">{result.changed.map(c => <li key={c.shop_number}>{c.name}</li>)}</ul>}
      </div>}
    </div>}
  </Card>
}
