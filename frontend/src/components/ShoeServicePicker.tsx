import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Tag, X } from 'lucide-react'
import {
  listShoeCatalogueGroups,
  searchShoeCatalogueItems,
  formatShoePricingType,
  type ShoeCatalogueItem,
  type ShoePricingType,
  type ShoeRepairJobItemInput,
} from '@/lib/api'

const FROM_PRICING_TYPES: ShoePricingType[] = [
  'from', 'pair_from', 'each_from', 'from_per_boot', 'from_per_strap', 'quoted_upon_inspection',
]

function isPriceAdjustable(t: ShoePricingType) {
  return FROM_PRICING_TYPES.includes(t)
}

export interface SelectedShoeService {
  item: ShoeCatalogueItem
  quantity: number
  notes: string
  agreedPrice: string
}

export function buildShoeRepairJobItemsPayload(selected: SelectedShoeService[]): ShoeRepairJobItemInput[] {
  return selected.map(service => ({
    catalogue_key: service.item.key,
    catalogue_group: service.item.group_id,
    item_name: service.item.name,
    pricing_type: service.item.pricing_type,
    unit_price_cents: service.agreedPrice
      ? Math.round(parseFloat(service.agreedPrice) * 100)
      : service.item.price_cents,
    quantity: service.quantity,
    notes: service.notes || undefined,
  }))
}

export default function ShoeServicePicker({
  selected,
  onChange,
  contextLabel,
}: {
  selected: SelectedShoeService[]
  onChange: (items: SelectedShoeService[]) => void
  contextLabel?: string
}) {
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')

  const { data: groups = [] } = useQuery({
    queryKey: ['shoe-catalogue-groups'],
    queryFn: () => listShoeCatalogueGroups().then(r => r.data),
    staleTime: Infinity,
  })

  const { data: items = [] } = useQuery({
    queryKey: ['shoe-catalogue-items', search, groupFilter],
    queryFn: () => searchShoeCatalogueItems({ q: search || undefined, group: groupFilter || undefined }).then(r => r.data),
    staleTime: 30_000,
  })

  const selectedKeys = new Set(selected.map(s => s.item.key))

  function addItem(item: ShoeCatalogueItem) {
    if (selectedKeys.has(item.key)) return
    onChange([...selected, { item, quantity: 1, notes: item.notes ?? '', agreedPrice: '' }])
  }

  function removeItem(key: string) {
    onChange(selected.filter(s => s.item.key !== key))
  }

  return (
    <div>
      {contextLabel && (
        <div
          className="mb-3 rounded-lg px-3 py-2 text-xs"
          style={{ backgroundColor: '#F7F0E5', border: '1px solid #E4D7C3', color: 'var(--cafe-text-mid)' }}
        >
          Quoting for: <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{contextLabel}</span>
        </div>
      )}

      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search services…"
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
        style={{ maxHeight: '220px', borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
      >
        {items.length === 0 ? (
          <p className="text-center py-6 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No services found</p>
        ) : (
          items.map(item => {
            const alreadyAdded = selectedKeys.has(item.key)
            const priceLabel = formatShoePricingType(item.pricing_type as ShoePricingType, item.price_cents)
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
                  <p className="text-sm font-semibold" style={{ color: 'var(--cafe-amber)' }}>{priceLabel}</p>
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
            Selected services ({selected.length})
          </p>
          <div className="space-y-2">
            {selected.map(({ item, notes, agreedPrice }, idx) => (
              <div
                key={item.key}
                className="flex items-start gap-2 rounded-lg px-3 py-2"
                style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border-2)' }}
              >
                <Tag size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--cafe-amber)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{item.name}</p>
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                    {item.group_label}
                    {isPriceAdjustable(item.pricing_type as ShoePricingType)
                      ? <>
                          {' · '}
                          <span style={{ color: 'var(--cafe-amber)' }}>
                            {formatShoePricingType(item.pricing_type as ShoePricingType, item.price_cents)}
                          </span>
                        </>
                      : <> · {formatShoePricingType(item.pricing_type as ShoePricingType, item.price_cents)}</>}
                  </p>
                  {item.includes && item.includes.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {item.includes.map(inc => (
                        <li key={inc} className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>• {inc}</li>
                      ))}
                    </ul>
                  )}
                  {isPriceAdjustable(item.pricing_type as ShoePricingType) && (
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="text-xs font-semibold" style={{ color: 'var(--cafe-text-muted)' }}>Agreed $</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder={item.pricing_type === 'quoted_upon_inspection' ? '0.00' : ((item.price_cents ?? 0) / 100).toFixed(2)}
                        value={agreedPrice}
                        onChange={e => {
                          const updated = [...selected]
                          updated[idx] = { ...updated[idx], agreedPrice: e.target.value }
                          onChange(updated)
                        }}
                        className="w-24 h-7 rounded border px-2 text-xs outline-none focus:ring-1"
                        style={{
                          backgroundColor: 'var(--cafe-bg)',
                          borderColor: agreedPrice ? 'var(--cafe-amber)' : 'var(--cafe-border-2)',
                          color: 'var(--cafe-text)',
                        }}
                      />
                      {agreedPrice && (
                        <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                          = ${parseFloat(agreedPrice || '0').toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}
                  <input
                    type="text"
                    placeholder="Notes (optional)"
                    value={notes}
                    onChange={e => {
                      const updated = [...selected]
                      updated[idx] = { ...updated[idx], notes: e.target.value }
                      onChange(updated)
                    }}
                    className="mt-1.5 w-full h-7 rounded border px-2 text-xs outline-none focus:ring-1"
                    style={{
                      backgroundColor: 'var(--cafe-bg)',
                      borderColor: 'var(--cafe-border-2)',
                      color: 'var(--cafe-text)',
                    }}
                  />
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