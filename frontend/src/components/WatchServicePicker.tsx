import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Tag, X } from 'lucide-react'
import {
  listWatchCatalogueGroups,
  searchWatchCatalogueItems,
  type WatchCatalogueItem,
} from '@/lib/api'

export interface SelectedWatchService {
  item: WatchCatalogueItem
}

export default function WatchServicePicker({
  selected,
  onChange,
}: {
  selected: SelectedWatchService[]
  onChange: (items: SelectedWatchService[]) => void
}) {
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')

  const { data: groups = [] } = useQuery({
    queryKey: ['watch-catalogue-groups'],
    queryFn: () => listWatchCatalogueGroups().then(r => r.data),
    staleTime: Infinity,
  })

  const { data: items = [] } = useQuery({
    queryKey: ['watch-catalogue-items', search, groupFilter],
    queryFn: () => searchWatchCatalogueItems({ q: search || undefined, group: groupFilter || undefined }).then(r => r.data),
    staleTime: 30_000,
  })

  const selectedKeys = new Set(selected.map(s => s.item.key))

  function addItem(item: WatchCatalogueItem) {
    if (selectedKeys.has(item.key)) return
    onChange([...selected, { item }])
  }

  function removeItem(key: string) {
    onChange(selected.filter(s => s.item.key !== key))
  }

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search repairs…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              borderColor: 'var(--cafe-border-2)',
              color: 'var(--cafe-text)',
            }}
          />
        </div>
        <select
          value={groupFilter}
          onChange={e => setGroupFilter(e.target.value)}
          className="h-9 rounded-lg border px-2 text-sm outline-none focus:ring-2"
          style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
        >
          <option value="">All categories</option>
          {groups.map(g => (
            <option key={g.id} value={g.id}>{g.label}</option>
          ))}
        </select>
      </div>

      <div
        className="rounded-xl border overflow-y-auto mb-4"
        style={{ maxHeight: '200px', borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
      >
        {items.length === 0 ? (
          <p className="text-center py-6 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No repairs found</p>
        ) : (
          items.map(item => {
            const alreadyAdded = selectedKeys.has(item.key)
            return (
              <button
                key={item.key}
                type="button"
                disabled={alreadyAdded}
                onClick={() => addItem(item)}
                className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left text-sm border-b last:border-b-0 transition-colors"
                style={{
                  borderColor: 'var(--cafe-border)',
                  backgroundColor: alreadyAdded ? 'var(--cafe-border)' : 'transparent',
                  opacity: alreadyAdded ? 0.5 : 1,
                  cursor: alreadyAdded ? 'default' : 'pointer',
                }}
                onMouseEnter={e => { if (!alreadyAdded) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--cafe-surface)' }}
                onMouseLeave={e => { if (!alreadyAdded) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate" style={{ color: 'var(--cafe-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{item.group_label}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-semibold" style={{ color: 'var(--cafe-amber)' }}>${(item.price_cents / 100).toFixed(2)}</p>
                  {alreadyAdded && (
                    <span className="text-[10px] text-green-600 font-medium">Added</span>
                  )}
                </div>
              </button>
            )
          })
        )}
      </div>

      {selected.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--cafe-text-muted)' }}>
            Selected repairs ({selected.length})
          </p>
          <div className="space-y-2">
            {selected.map(({ item }) => (
              <div
                key={item.key}
                className="flex items-center gap-2 rounded-lg px-3 py-2"
                style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}
              >
                <Tag size={13} className="shrink-0" style={{ color: 'var(--cafe-amber)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                    {item.group_label} · ${(item.price_cents / 100).toFixed(2)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeItem(item.key)}
                  className="p-0.5 rounded hover:bg-[#F5EDE0] transition-colors"
                  style={{ color: 'var(--cafe-text-muted)' }}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
