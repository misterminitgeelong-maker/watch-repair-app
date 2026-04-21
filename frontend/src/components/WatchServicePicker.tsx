import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Tag, X } from 'lucide-react'
import {
  listWatchCatalogueGroups,
  searchWatchCatalogueItems,
  listCustomServices,
  createCustomService,
  type WatchCatalogueItem,
} from '@/lib/api'
import { Button, Input } from '@/components/ui'
import { getApiErrorMessage } from '@/lib/api'

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
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', price: '' })
  const [addError, setAddError] = useState('')
  const qc = useQueryClient()

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

  const { data: customItems = [] } = useQuery({
    queryKey: ['custom-services', 'watch'],
    queryFn: () => listCustomServices('watch').then(r => r.data),
    staleTime: 60_000,
  })

  const createMut = useMutation({
    mutationFn: (payload: Parameters<typeof createCustomService>[0]) => createCustomService(payload).then(r => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['custom-services', 'watch'] })
      setAddForm({ name: '', price: '' })
      setAddOpen(false)
      addItem({ ...data, key: data.id, price: data.price_cents / 100 } as WatchCatalogueItem)
    },
    onError: (err) => setAddError(getApiErrorMessage(err, 'Failed to add service')),
  })

  const customAsWatch = customItems.map(c => ({
    ...c,
    key: c.id,
    price: c.price_cents / 100,
    price_cents: c.price_cents,
  })) as WatchCatalogueItem[]
  const q = search.trim().toLowerCase()
  const filteredCustom = customAsWatch.filter(c => {
    if (groupFilter && (c.group_id ?? '') !== groupFilter) return false
    if (q && !c.name.toLowerCase().includes(q)) return false
    return true
  })
  const searchFiltered = [...items, ...filteredCustom]
  const selectedKeys = new Set(selected.map(s => s.item.key))

  function addItem(item: WatchCatalogueItem) {
    if (selectedKeys.has(item.key)) return
    onChange([...selected, { item }])
  }

  function removeItem(key: string) {
    onChange(selected.filter(s => s.item.key !== key))
  }

  function submitAdd() {
    setAddError('')
    const name = addForm.name.trim()
    const price = parseFloat(addForm.price)
    if (!name) { setAddError('Service name is required.'); return }
    if (isNaN(price) || price < 0) { setAddError('Enter a valid price.'); return }
    createMut.mutate({
      service_type: 'watch',
      name,
      price_cents: Math.round(price * 100),
      group_id: 'custom',
      group_label: 'Custom',
    })
  }

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--ms-text-muted)' }} />
          <input
            type="text"
            placeholder="Search repairs…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-9 rounded-lg border pl-8 pr-3 text-sm outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--ms-surface)',
              borderColor: 'var(--ms-border-strong)',
              color: 'var(--ms-text)',
            }}
          />
        </div>
        <select
          value={groupFilter}
          onChange={e => setGroupFilter(e.target.value)}
          className="h-9 rounded-lg border px-2 text-sm outline-none focus:ring-2"
          style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border-strong)', color: 'var(--ms-text)' }}
        >
          <option value="">All categories</option>
          {groups.map(g => (
            <option key={g.id} value={g.id}>{g.label}</option>
          ))}
          {customAsWatch.length > 0 && !groups.some(g => g.id === 'custom') && (
            <option value="custom">Custom</option>
          )}
        </select>
      </div>

      <div className="mb-3">
        <button
          type="button"
          onClick={() => setAddOpen(!addOpen)}
          className="flex items-center gap-1.5 text-xs font-medium py-1.5 px-2 rounded"
          style={{ color: 'var(--ms-accent)' }}
        >
          <Plus size={14} />
          Add your own service
        </button>
        {addOpen && (
          <div className="mt-2 p-3 rounded-lg border space-y-2" style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}>
            <Input
              label="Service name"
              value={addForm.name}
              onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Custom engraving"
            />
            <Input
              label="Price ($)"
              type="number"
              step="0.01"
              min="0"
              value={addForm.price}
              onChange={e => setAddForm(f => ({ ...f, price: e.target.value }))}
              placeholder="0.00"
            />
            {addError && <p className="text-xs" style={{ color: '#C96A5A' }}>{addError}</p>}
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => { setAddOpen(false); setAddError('') }}>Cancel</Button>
              <Button onClick={submitAdd} disabled={createMut.isPending}>{createMut.isPending ? 'Adding…' : 'Add'}</Button>
            </div>
          </div>
        )}
      </div>

      <div
        className="rounded-xl border overflow-y-auto mb-4"
        style={{ maxHeight: '200px', borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}
      >
        {searchFiltered.length === 0 ? (
          <p className="text-center py-6 text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No repairs found</p>
        ) : (
          searchFiltered.map(item => {
            const alreadyAdded = selectedKeys.has(item.key)
            return (
              <button
                key={item.key}
                type="button"
                disabled={alreadyAdded}
                onClick={() => addItem(item)}
                className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left text-sm border-b last:border-b-0 transition-colors"
                style={{
                  borderColor: 'var(--ms-border)',
                  backgroundColor: alreadyAdded ? 'var(--ms-border)' : 'transparent',
                  opacity: alreadyAdded ? 0.5 : 1,
                  cursor: alreadyAdded ? 'default' : 'pointer',
                }}
                onMouseEnter={e => { if (!alreadyAdded) (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--ms-surface)' }}
                onMouseLeave={e => { if (!alreadyAdded) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate" style={{ color: 'var(--ms-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{item.group_label}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-semibold" style={{ color: 'var(--ms-accent)' }}>${((item.price_cents ?? 0) / 100).toFixed(2)}</p>
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
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>
            Selected repairs ({selected.length})
          </p>
          <div className="space-y-2">
            {selected.map(({ item }) => (
              <div
                key={item.key}
                className="flex items-center gap-2 rounded-lg px-3 py-2"
                style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)' }}
              >
                <Tag size={13} className="shrink-0" style={{ color: 'var(--ms-accent)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                    {item.group_label} · ${((item.price_cents ?? 0) / 100).toFixed(2)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeItem(item.key)}
                  className="p-0.5 rounded hover:bg-[#F5EDE0] transition-colors"
                  style={{ color: 'var(--ms-text-muted)' }}
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
