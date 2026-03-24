/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Tag, X } from 'lucide-react'
import {
  listShoeCatalogueGroups,
  searchShoeCatalogueItems,
  listCustomServices,
  createCustomService,
  formatShoePricingType,
  type ShoeCatalogueItem,
  type ShoePricingType,
  type ShoeRepairJobItemInput,
} from '@/lib/api'
import { Button, Input } from '@/components/ui'
import { getApiErrorMessage } from '@/lib/api'
import { formatEstimatedTurnaround, COMPLEXITY_LABELS } from '@/lib/utils'

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

// Mapping shoe types to relevant group IDs
export const SHOE_TYPE_GROUPS: Record<string, string[]> = {
  'Boots': ['full_soles', 'miscellaneous_repairs', 'additional_repairs', 'shoe_revival'],
  'Dress shoes': ['heels', 'half_soles', 'full_soles', 'scratch_repair_and_polish', 'shoe_revival'],
  'Sneakers': ['half_soles', 'full_soles', 'miscellaneous_repairs', 'shoe_revival'],
  'Sandals / Thongs': ['miscellaneous_repairs', 'additional_repairs', 'shoe_revival'],
  'Heels / Stilettos': ['heels', 'half_soles', 'scratch_repair_and_polish', 'shoe_revival'],
  'Work boots': ['full_soles', 'miscellaneous_repairs', 'additional_repairs', 'shoe_revival'],
  'Birkenstocks': ['full_soles', 'miscellaneous_repairs', 'shoe_revival'],
  'Other': ['heels', 'half_soles', 'full_soles', 'miscellaneous_repairs', 'additional_repairs', 'shoe_revival', 'scratch_repair_and_polish'],
}

export default function ShoeServicePicker({
  selected,
  onChange,
  contextLabel,
  shoeType,
}: {
  selected: SelectedShoeService[]
  onChange: (items: SelectedShoeService[]) => void
  contextLabel?: string
  shoeType?: string
}) {
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', price: '' })
  const [addError, setAddError] = useState('')
  const qc = useQueryClient()

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

  const { data: customItems = [] } = useQuery({
    queryKey: ['custom-services', 'shoe'],
    queryFn: () => listCustomServices('shoe').then(r => r.data),
    staleTime: 60_000,
  })

  const createMut = useMutation({
    mutationFn: (payload: Parameters<typeof createCustomService>[0]) => createCustomService(payload).then(r => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['custom-services', 'shoe'] })
      setAddForm({ name: '', price: '' })
      setAddOpen(false)
      addItem(data as ShoeCatalogueItem)
    },
    onError: (err) => setAddError(getApiErrorMessage(err, 'Failed to add service')),
  })

  const customAsShoe = customItems.map(c => ({
    ...c,
    price: c.price ?? (c.price_cents ?? 0) / 100,
    price_cents: c.price_cents,
    complexity: 'standard' as const,
    estimated_days_min: 3,
    estimated_days_max: 7,
  })) as ShoeCatalogueItem[]

  // Filter items by applicable_shoe_types if present, else fallback to group filter
  let filteredItems = items
  let hiddenCount = 0
  if (shoeType) {
    filteredItems = items.filter(item => {
      if (Array.isArray(item.applicable_shoe_types)) {
        const match = item.applicable_shoe_types.includes(shoeType)
        if (!match) hiddenCount++
        return match
      }
      // fallback to group filter for legacy items
      const groupMatch = SHOE_TYPE_GROUPS[shoeType]?.includes(item.group_id)
      if (!groupMatch) hiddenCount++
      return groupMatch
    })
  }
  const q = search.trim().toLowerCase()
  const filteredCustom = customAsShoe.filter(c => {
    if (groupFilter && (c.group_id ?? '') !== groupFilter) return false
    if (q && !c.name.toLowerCase().includes(q)) return false
    return true
  })
  const allItems = [...filteredItems, ...filteredCustom]

  const selectedKeys = new Set(selected.map(s => s.item.key))

  function addItem(item: ShoeCatalogueItem) {
    if (selectedKeys.has(item.key)) return
    onChange([...selected, { item, quantity: 1, notes: item.notes ?? '', agreedPrice: '' }])
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
      service_type: 'shoe',
      name,
      price_cents: Math.round(price * 100),
      group_id: 'custom',
      group_label: 'Custom',
      pricing_type: 'fixed',
    })
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
          {customAsShoe.length > 0 && !groups.some(g => g.id === 'custom') && (
            <option value="custom">Custom</option>
          )}
        </select>
      </div>

      <div className="mb-3">
        <button
          type="button"
          onClick={() => setAddOpen(!addOpen)}
          className="flex items-center gap-1.5 text-xs font-medium py-1.5 px-2 rounded"
          style={{ color: 'var(--cafe-amber)' }}
        >
          <Plus size={14} />
          Add your own service
        </button>
        {addOpen && (
          <div className="mt-2 p-3 rounded-lg border space-y-2" style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)' }}>
            <Input
              label="Service name"
              value={addForm.name}
              onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Hand dye job"
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
        style={{ maxHeight: '220px', borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
      >
        {allItems.length === 0 ? (
          <p className="text-center py-6 text-sm italic" style={{ color: 'var(--cafe-text-muted)' }}>No services found for this shoe type</p>
        ) : (
          allItems.map(item => {
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
                  <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                    {item.group_label}
                    {item.complexity && (
                      <>
                        {' · '}
                        <span className="capitalize" style={{ color: item.complexity === 'complex' ? '#8B3A3A' : item.complexity === 'simple' ? '#2E7D32' : 'inherit' }}>
                          {COMPLEXITY_LABELS[item.complexity] ?? item.complexity}
                        </span>
                      </>
                    )}
                    {item.estimated_days_min != null && item.estimated_days_max != null && (
                      <> · {formatEstimatedTurnaround(item.estimated_days_min, item.estimated_days_max)}</>
                    )}
                  </p>
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
      {hiddenCount > 0 && (
        <div className="text-xs italic text-center mb-2" style={{ color: 'var(--cafe-text-muted)' }}>
          {hiddenCount} service{hiddenCount > 1 ? 's are' : ' is'} hidden for this shoe type
        </div>
      )}

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
                    {item.complexity && <> · {COMPLEXITY_LABELS[item.complexity] ?? item.complexity}</>}
                    {item.estimated_days_min != null && item.estimated_days_max != null && (
                      <> · Est. {formatEstimatedTurnaround(item.estimated_days_min, item.estimated_days_max)}</>
                    )}
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