import { useState } from 'react'
import { Search, Wrench, Cpu } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { listWatchCatalogueGroups, searchWatchCatalogueItems, listWatchMovements } from '@/lib/api'
import { Card } from '@/components/ui'

export default function WatchCatalogueTab() {
  const [repairSearch, setRepairSearch] = useState('')
  const [repairGroup, setRepairGroup] = useState('')
  const [movementSearch, setMovementSearch] = useState('')

  const { data: groups = [] } = useQuery({
    queryKey: ['watch-catalogue-groups'],
    queryFn: () => listWatchCatalogueGroups().then(r => r.data),
  })
  const { data: repairItems = [] } = useQuery({
    queryKey: ['watch-catalogue-items', repairSearch, repairGroup],
    queryFn: () => searchWatchCatalogueItems({ q: repairSearch || undefined, group: repairGroup || undefined }).then(r => r.data),
  })
  const { data: movementsData } = useQuery({
    queryKey: ['watch-movements'],
    queryFn: () => listWatchMovements().then(r => r.data),
  })

  const movements = movementsData?.movements ?? []
  const q = movementSearch.trim().toLowerCase()
  const filteredMovements = q
    ? movements.filter(m => m.name.toLowerCase().includes(q) || (m.key ?? '').toLowerCase().includes(q))
    : movements

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={20} style={{ color: 'var(--ms-accent)' }} />
          <h2 className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>Repair Services</h2>
        </div>
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--ms-text-muted)' }} />
            <input
              type="text"
              placeholder="Search repairs…"
              value={repairSearch}
              onChange={e => setRepairSearch(e.target.value)}
              className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
              style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
            />
          </div>
          <select
            value={repairGroup}
            onChange={e => setRepairGroup(e.target.value)}
            className="h-9 rounded-lg border px-2 text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
          >
            <option value="">All categories</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.label}</option>)}
          </select>
        </div>
        <div className="rounded-lg border overflow-y-auto" style={{ maxHeight: '240px', borderColor: 'var(--ms-border)' }}>
          {repairItems.length === 0 ? (
            <p className="text-center py-6 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No repairs found</p>
          ) : (
            <table className="w-full text-sm">
              <thead style={{ backgroundColor: 'var(--ms-bg)' }}>
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">Service</th>
                  <th className="text-left px-4 py-2 font-semibold">Category</th>
                  <th className="text-right px-4 py-2 font-semibold">Price</th>
                </tr>
              </thead>
              <tbody>
                {repairItems.map(item => (
                  <tr key={item.key} style={{ borderTop: '1px solid var(--ms-border)' }}>
                    <td className="px-4 py-2" style={{ color: 'var(--ms-text)' }}>{item.name}</td>
                    <td className="px-4 py-2" style={{ color: 'var(--ms-text-muted)' }}>{item.group_label}</td>
                    <td className="px-4 py-2 text-right font-medium" style={{ color: 'var(--ms-accent)' }}>${((item.price_cents ?? 0) / 100).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={20} style={{ color: 'var(--ms-accent)' }} />
          <h2 className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>Movement Database</h2>
        </div>
        <p className="text-xs mb-3" style={{ color: 'var(--ms-text-muted)' }}>
          RRP = max($80 floor, cost × 2.75). One formula for all movements.
        </p>
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--ms-text-muted)' }} />
          <input
            type="text"
            placeholder="Search movements by name or caliber…"
            value={movementSearch}
            onChange={e => setMovementSearch(e.target.value)}
            className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
            style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
          />
        </div>
        <div className="rounded-lg border overflow-y-auto" style={{ maxHeight: '420px', borderColor: 'var(--ms-border)' }}>
          {filteredMovements.length === 0 ? (
            <p className="text-center py-6 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No movements found</p>
          ) : (
            <table className="w-full text-sm">
              <thead style={{ backgroundColor: 'var(--ms-bg)' }}>
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">Movement</th>
                  <th className="text-right px-4 py-2 font-semibold">Our cost</th>
                  <th className="text-right px-4 py-2 font-semibold">RRP (customer)</th>
                </tr>
              </thead>
              <tbody>
                {filteredMovements.slice(0, 500).map(m => (
                  <tr key={m.key} style={{ borderTop: '1px solid var(--ms-border)' }}>
                    <td className="px-4 py-2" style={{ color: 'var(--ms-text)' }}>{m.name}</td>
                    <td className="px-4 py-2 text-right" style={{ color: 'var(--ms-text-muted)' }}>
                      ${((m.purchase_cost_cents ?? 0) / 100).toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-right font-medium" style={{ color: 'var(--ms-accent)' }}>
                      {m.quote_cents != null ? `$${(m.quote_cents / 100).toFixed(2)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {filteredMovements.length > 500 && (
            <p className="text-center py-2 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              Showing 500 of {filteredMovements.length} movements. Refine search to see more.
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}
