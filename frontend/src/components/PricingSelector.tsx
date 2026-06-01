import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Search, X } from 'lucide-react'
import {
  getApiErrorMessage,
  listGarageServicingPricing,
  listMobileServicesOemKeyPricing,
  listMobileServicesOemMakes,
  listMobileServicesServicePricing,
  type GarageServicingPricingRow,
  type MobileServicesPricingSelection,
  type OemKeyPricingRow,
  type ServicePricingRow,
} from '@/lib/api'
import { Button, Input } from '@/components/ui'

type TabId = 'vehicle_key' | 'general_service' | 'garage_door'

const TABS: { id: TabId; label: string }[] = [
  { id: 'vehicle_key', label: 'Vehicle Key' },
  { id: 'general_service', label: 'General Service' },
  { id: 'garage_door', label: 'Garage Door' },
]

function formatPrice(amount: number) {
  return `$${amount.toFixed(2)}`
}

function CalloutBadge({ inclusive }: { inclusive: boolean }) {
  return (
    <span
      className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
      style={{
        backgroundColor: inclusive ? 'rgba(46,125,50,0.12)' : 'rgba(201,162,72,0.12)',
        color: inclusive ? '#2E7D32' : '#9A7220',
      }}
    >
      {inclusive ? 'Callout incl.' : '+ Callout'}
    </span>
  )
}

function PoaBadge() {
  return (
    <span
      className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
      style={{ backgroundColor: 'rgba(201,106,90,0.15)', color: '#C96A5A' }}
    >
      POA
    </span>
  )
}

function SectionHeader({ title }: { title: string }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide px-1 pt-2 pb-1" style={{ color: 'var(--ms-text-muted)' }}>
      {title}
    </p>
  )
}

export default function PricingSelector({
  open,
  onClose,
  onConfirm,
  initialMake,
}: {
  open: boolean
  onClose: () => void
  onConfirm: (selection: MobileServicesPricingSelection) => void
  initialMake?: string
}) {
  const [tab, setTab] = useState<TabId>('vehicle_key')
  const [makeSearch, setMakeSearch] = useState(initialMake ?? '')
  const [selectedMake, setSelectedMake] = useState(initialMake?.trim() ?? '')
  const [selectedRow, setSelectedRow] = useState<{
    type: 'oem_key' | 'service' | 'garage'
    id: string
    label: string
    isPoa: boolean
    retailPrice: number | null
    calloutInclusive: boolean
  } | null>(null)
  const [customPrice, setCustomPrice] = useState('')

  useEffect(() => {
    if (open && initialMake?.trim()) {
      setMakeSearch(initialMake)
      setSelectedMake(initialMake.trim())
    }
  }, [open, initialMake])

  useEffect(() => {
    if (!open) {
      setSelectedRow(null)
      setCustomPrice('')
    }
  }, [open])

  const {
    data: makes = [],
    isFetching: makesLoading,
    isError: makesError,
    error: makesQueryError,
  } = useQuery({
    queryKey: ['mobile-services-pricing', 'oem-makes'],
    queryFn: () => listMobileServicesOemMakes().then(r => r.data),
    enabled: open,
    staleTime: 60_000,
  })

  const makeSearchNorm = makeSearch.trim().toLowerCase()
  const selectedMakeNorm = selectedMake.trim().toLowerCase()
  const makeSearchMatchesSelection = !!selectedMakeNorm && makeSearchNorm === selectedMakeNorm

  const filteredMakes = useMemo(() => {
    const q = makeSearch.trim().toLowerCase()
    if (!q) return makes
    return makes.filter(m => m.toLowerCase().includes(q))
  }, [makes, makeSearch])

  useEffect(() => {
    if (!open || makesLoading || !makeSearchNorm) return
    const exact = makes.find(m => m.toLowerCase() === makeSearchNorm)
    if (exact && exact !== selectedMake) setSelectedMake(exact)
  }, [open, makes, makesLoading, makeSearchNorm, selectedMake])

  const pickMake = (make: string) => {
    setSelectedMake(make)
    setMakeSearch(make)
  }

  const { data: oemKeys = [], isFetching: oemLoading, isError: oemError, error: oemQueryError } = useQuery({
    queryKey: ['mobile-services-pricing', 'oem-keys', selectedMake],
    queryFn: () => listMobileServicesOemKeyPricing(selectedMake).then(r => r.data),
    enabled: open && tab === 'vehicle_key' && makeSearchMatchesSelection,
    staleTime: 30_000,
  })

  const {
    data: services = [],
    isFetching: servicesLoading,
    isError: servicesError,
    error: servicesQueryError,
  } = useQuery({
    queryKey: ['mobile-services-pricing', 'services'],
    queryFn: () => listMobileServicesServicePricing().then(r => r.data),
    enabled: open,
    staleTime: 60_000,
  })

  const {
    data: garageItems = [],
    isFetching: garageLoading,
    isError: garageError,
    error: garageQueryError,
  } = useQuery({
    queryKey: ['mobile-services-pricing', 'garage'],
    queryFn: () => listGarageServicingPricing().then(r => r.data),
    enabled: open,
    staleTime: 60_000,
  })

  const addKeyRows = oemKeys.filter(r => r.job_type === 'Add Key')
  const aklRows = oemKeys.filter(r => r.job_type === 'AKL')

  const servicesByCategory = useMemo(() => {
    const map = new Map<string, ServicePricingRow[]>()
    for (const row of services) {
      const list = map.get(row.category) ?? []
      list.push(row)
      map.set(row.category, list)
    }
    return [...map.entries()]
  }, [services])

  const effectivePrice = useMemo(() => {
    if (!selectedRow) return null
    if (selectedRow.isPoa) {
      const parsed = parseFloat(customPrice)
      return Number.isFinite(parsed) && parsed > 0 ? parsed : null
    }
    return selectedRow.retailPrice
  }, [selectedRow, customPrice])

  const confirmDisabled = !selectedRow || effectivePrice == null

  const selectOem = (row: OemKeyPricingRow) => {
    setSelectedRow({
      type: 'oem_key',
      id: row.id,
      label: [row.model_variant, row.key_type].filter(Boolean).join(' · ') || row.job_type,
      isPoa: row.is_poa,
      retailPrice: row.retail_price ?? null,
      calloutInclusive: row.callout_inclusive,
    })
    setCustomPrice('')
  }

  const selectService = (row: ServicePricingRow) => {
    setSelectedRow({
      type: 'service',
      id: row.id,
      label: row.service_name,
      isPoa: row.is_poa,
      retailPrice: row.retail_price ?? null,
      calloutInclusive: row.callout_inclusive,
    })
    setCustomPrice('')
  }

  const selectGarage = (row: GarageServicingPricingRow) => {
    setSelectedRow({
      type: 'garage',
      id: row.id,
      label: row.service_name,
      isPoa: false,
      retailPrice: row.retail_price ?? null,
      calloutInclusive: row.callout_inclusive,
    })
    setCustomPrice('')
  }

  const handleConfirm = () => {
    if (!selectedRow || effectivePrice == null) return
    onConfirm({
      pricing_ref_id: selectedRow.id,
      pricing_type: selectedRow.type,
      quoted_price: effectivePrice,
      callout_inclusive: selectedRow.calloutInclusive,
      label: selectedRow.label,
    })
    onClose()
  }

  if (!open) return null

  const renderOemRow = (row: OemKeyPricingRow) => {
    const isSelected = selectedRow?.id === row.id
    return (
      <div
        key={row.id}
        role="button"
        tabIndex={0}
        onClick={() => selectOem(row)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') selectOem(row) }}
        className="w-full text-left px-3 py-2.5 border-b last:border-b-0 transition-colors cursor-pointer"
        style={{
          borderColor: 'var(--ms-border)',
          backgroundColor: isSelected ? 'rgba(201,162,72,0.1)' : 'transparent',
        }}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
              {row.model_variant || '—'}
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
              {[row.key_type, row.service_location, row.tool_required].filter(Boolean).join(' · ')}
            </p>
            {row.notes && (
              <p className="text-xs mt-0.5 italic" style={{ color: 'var(--ms-text-muted)' }}>{row.notes}</p>
            )}
          </div>
          <div className="shrink-0 text-right space-y-1">
            {row.is_poa ? <PoaBadge /> : (
              <span className="text-sm font-semibold tabular-nums" style={{ color: 'var(--ms-accent)' }}>
                {formatPrice(row.retail_price!)}
              </span>
            )}
            <div><CalloutBadge inclusive={row.callout_inclusive} /></div>
          </div>
        </div>
        {isSelected && row.is_poa && (
          <div className="mt-2 flex items-center gap-2" onClick={e => e.stopPropagation()}>
            <span className="text-xs font-medium" style={{ color: 'var(--ms-text-muted)' }}>Custom $</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={customPrice}
              onChange={e => setCustomPrice(e.target.value)}
              className="flex-1 rounded border px-2 py-1 text-sm"
              style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              placeholder="Enter price"
              autoFocus
            />
          </div>
        )}
      </div>
    )
  }

  const renderServiceRow = (row: ServicePricingRow) => {
    const isSelected = selectedRow?.id === row.id
    return (
      <div
        key={row.id}
        role="button"
        tabIndex={0}
        onClick={() => selectService(row)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') selectService(row) }}
        className="w-full text-left px-3 py-2.5 border-b last:border-b-0 transition-colors cursor-pointer"
        style={{
          borderColor: 'var(--ms-border)',
          backgroundColor: isSelected ? 'rgba(201,162,72,0.1)' : 'transparent',
        }}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{row.service_name}</p>
            {row.unit && (
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>Unit: {row.unit}</p>
            )}
            {row.notes && (
              <p className="text-xs mt-0.5 italic" style={{ color: 'var(--ms-text-muted)' }}>{row.notes}</p>
            )}
          </div>
          <div className="shrink-0 text-right space-y-1">
            {row.is_poa ? <PoaBadge /> : (
              <span className="text-sm font-semibold tabular-nums" style={{ color: 'var(--ms-accent)' }}>
                {formatPrice(row.retail_price!)}
              </span>
            )}
            <div><CalloutBadge inclusive={row.callout_inclusive} /></div>
          </div>
        </div>
        {isSelected && row.is_poa && (
          <div className="mt-2 flex items-center gap-2" onClick={e => e.stopPropagation()}>
            <span className="text-xs font-medium" style={{ color: 'var(--ms-text-muted)' }}>Custom $</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={customPrice}
              onChange={e => setCustomPrice(e.target.value)}
              className="flex-1 rounded border px-2 py-1 text-sm"
              style={{ borderColor: 'var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              placeholder="Enter price"
              autoFocus
            />
          </div>
        )}
      </div>
    )
  }

  const renderGarageRow = (row: GarageServicingPricingRow) => {
    const isSelected = selectedRow?.id === row.id
    return (
      <button
        key={row.id}
        type="button"
        onClick={() => selectGarage(row)}
        className="w-full text-left px-3 py-2.5 border-b last:border-b-0 transition-colors"
        style={{
          borderColor: 'var(--ms-border)',
          backgroundColor: isSelected ? 'rgba(201,162,72,0.1)' : 'transparent',
        }}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>{row.service_name}</p>
            {row.description && (
              <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{row.description}</p>
            )}
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
              {[row.part_cost_notes, row.labour_time && `Labour: ${row.labour_time}`].filter(Boolean).join(' · ')}
            </p>
            {row.notes && (
              <p className="text-xs mt-0.5 italic" style={{ color: 'var(--ms-text-muted)' }}>{row.notes}</p>
            )}
          </div>
          <div className="shrink-0 text-right space-y-1">
            <span className="text-sm font-semibold tabular-nums" style={{ color: 'var(--ms-accent)' }}>
              {formatPrice(row.retail_price)}
            </span>
            <div><CalloutBadge inclusive={row.callout_inclusive} /></div>
          </div>
        </div>
      </button>
    )
  }

  return (
    <div
      className="absolute inset-0 z-20 flex justify-end"
      style={{ backgroundColor: 'rgba(0,0,0,0.35)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md h-full flex flex-col shadow-xl"
        style={{ backgroundColor: 'var(--ms-surface)', borderLeft: '1px solid var(--ms-border-strong)' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--ms-border-strong)' }}>
          <h3 className="text-base font-semibold" style={{ color: 'var(--ms-text)' }}>Pricing catalogue</h3>
          <button type="button" onClick={onClose} aria-label="Close pricing panel" className="p-1 rounded" style={{ color: 'var(--ms-text-muted)' }}>
            <X size={20} />
          </button>
        </div>

        <div className="flex border-b" style={{ borderColor: 'var(--ms-border-strong)' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => { setTab(t.id); setSelectedRow(null); setCustomPrice('') }}
              className="flex-1 py-2.5 text-xs font-semibold uppercase tracking-wide transition-colors"
              style={{
                color: tab === t.id ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
                borderBottom: tab === t.id ? '2px solid var(--ms-accent)' : '2px solid transparent',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2">
          {tab === 'vehicle_key' && (
            <>
              <div className="relative mb-2">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--ms-text-muted)' }} />
                <Input
                  value={makeSearch}
                  onChange={e => {
                    const next = e.target.value
                    setMakeSearch(next)
                    if (next.trim().toLowerCase() !== selectedMake.trim().toLowerCase()) {
                      setSelectedMake('')
                    }
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && filteredMakes.length > 0) {
                      e.preventDefault()
                      pickMake(filteredMakes[0])
                    }
                  }}
                  placeholder="Search make…"
                  className="pl-8"
                />
              </div>
              {makesError && (
                <p className="text-sm py-2 px-1" style={{ color: '#C96A5A' }}>
                  {getApiErrorMessage(makesQueryError, 'Could not load vehicle makes')}
                </p>
              )}
              {makesLoading && !makesError && (
                <p className="text-sm py-2 text-center" style={{ color: 'var(--ms-text-muted)' }}>Loading makes…</p>
              )}
              {!makesLoading && !makesError && makeSearchNorm && !makeSearchMatchesSelection && filteredMakes.length > 0 && (
                <div
                  className="rounded-lg border overflow-y-auto mb-2"
                  style={{ maxHeight: '140px', borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)' }}
                >
                  {filteredMakes.map(make => (
                    <button
                      key={make}
                      type="button"
                      onClick={() => pickMake(make)}
                      className="w-full text-left px-3 py-2 text-sm border-b last:border-b-0"
                      style={{ borderColor: 'var(--ms-border)', color: 'var(--ms-text)' }}
                    >
                      {make}
                    </button>
                  ))}
                </div>
              )}
              {!makesLoading && !makesError && makeSearchNorm && !makeSearchMatchesSelection && filteredMakes.length === 0 && (
                <p className="text-sm py-2 text-center italic" style={{ color: 'var(--ms-text-muted)' }}>
                  {makes.length === 0 ? 'No makes in catalogue yet' : 'No makes match your search'}
                </p>
              )}
              {makeSearchMatchesSelection && selectedMake && (
                <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>
                  Showing prices for <strong style={{ color: 'var(--ms-text)' }}>{selectedMake}</strong>
                  {' · '}
                  <button type="button" className="underline" onClick={() => { setSelectedMake(''); setMakeSearch('') }}>Change</button>
                </p>
              )}
              {oemError && (
                <p className="text-sm py-2 px-1" style={{ color: '#C96A5A' }}>
                  {getApiErrorMessage(oemQueryError, 'Could not load pricing for this make')}
                </p>
              )}
              {oemLoading && makeSearchMatchesSelection && !oemError && (
                <p className="text-sm py-4 text-center" style={{ color: 'var(--ms-text-muted)' }}>Loading prices…</p>
              )}
              {!oemLoading && !oemError && makeSearchMatchesSelection && selectedMake && addKeyRows.length === 0 && aklRows.length === 0 && (
                <p className="text-sm py-4 text-center italic" style={{ color: 'var(--ms-text-muted)' }}>No pricing for this make</p>
              )}
              {addKeyRows.length > 0 && (
                <>
                  <SectionHeader title="Add Key" />
                  <div className="rounded-lg border overflow-hidden mb-2" style={{ borderColor: 'var(--ms-border)' }}>
                    {addKeyRows.map(renderOemRow)}
                  </div>
                </>
              )}
              {aklRows.length > 0 && (
                <>
                  <SectionHeader title="AKL" />
                  <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--ms-border)' }}>
                    {aklRows.map(renderOemRow)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'general_service' && (
            <>
              {servicesError && (
                <p className="text-sm py-4 text-center" style={{ color: '#C96A5A' }}>
                  {getApiErrorMessage(servicesQueryError, 'Could not load general services')}
                </p>
              )}
              {servicesLoading && !servicesError && (
                <p className="text-sm py-4 text-center" style={{ color: 'var(--ms-text-muted)' }}>Loading…</p>
              )}
              {!servicesLoading && !servicesError && servicesByCategory.length === 0 && (
                <p className="text-sm py-4 text-center italic" style={{ color: 'var(--ms-text-muted)' }}>No services listed</p>
              )}
              {servicesByCategory.map(([category, rows]) => (
                <div key={category} className="mb-3">
                  <SectionHeader title={category} />
                  <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--ms-border)' }}>
                    {rows.map(renderServiceRow)}
                  </div>
                </div>
              ))}
            </>
          )}

          {tab === 'garage_door' && (
            <>
              {garageError && (
                <p className="text-sm py-4 text-center" style={{ color: '#C96A5A' }}>
                  {getApiErrorMessage(garageQueryError, 'Could not load garage services')}
                </p>
              )}
              {garageLoading && !garageError && (
                <p className="text-sm py-4 text-center" style={{ color: 'var(--ms-text-muted)' }}>Loading…</p>
              )}
              {!garageLoading && !garageError && garageItems.length === 0 && (
                <p className="text-sm py-4 text-center italic" style={{ color: 'var(--ms-text-muted)' }}>No garage services listed</p>
              )}
              <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--ms-border)' }}>
                {garageItems.map(renderGarageRow)}
              </div>
            </>
          )}
        </div>

        <div className="border-t px-4 py-3 space-y-2" style={{ borderColor: 'var(--ms-border-strong)' }}>
          {selectedRow?.isPoa && effectivePrice == null && (
            <p className="text-xs" style={{ color: '#C96A5A' }}>Enter a price to continue</p>
          )}
          {selectedRow && effectivePrice != null && (
            <p className="text-sm" style={{ color: 'var(--ms-text)' }}>
              Selected: <span className="font-medium">{selectedRow.label}</span>
              {' · '}
              <span className="font-semibold tabular-nums" style={{ color: 'var(--ms-accent)' }}>{formatPrice(effectivePrice)}</span>
            </p>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button className="flex-1" onClick={handleConfirm} disabled={confirmDisabled}>
              <Check size={16} className="mr-1 inline" />
              Confirm price
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
