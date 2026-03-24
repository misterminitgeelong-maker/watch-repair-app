import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, Shield, Tag } from 'lucide-react'
import { listShoeCatalogueGroups, searchShoeCatalogueItems, listShoeCombos, getShoeGuarantee, formatShoePricingType } from '@/lib/api'
import { PageHeader } from '@/components/ui'
import type { ShoePricingType } from '@/lib/api'

const FROM_PRICING_TYPES: ShoePricingType[] = [
  'from', 'pair_from', 'each_from', 'from_per_boot', 'from_per_strap', 'quoted_upon_inspection',
]

function formatPrice(item: { pricing_type: string; price_cents: number | null }) {
  const cents = item.price_cents ?? 0
  if (FROM_PRICING_TYPES.includes(item.pricing_type as ShoePricingType)) {
    return `$${(cents / 100).toFixed(2)}`
  }
  return formatShoePricingType(item.pricing_type as ShoePricingType, cents)
}

export default function ShoeServicesPage() {
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')

  const { data: groups = [] } = useQuery({
    queryKey: ['shoe-catalogue-groups', 'reference'],
    queryFn: () => listShoeCatalogueGroups().then(r => r.data),
    staleTime: Infinity,
  })
  const { data: items = [] } = useQuery({
    queryKey: ['shoe-catalogue-items', search, groupFilter, 'reference'],
    queryFn: () => searchShoeCatalogueItems({ q: search || undefined, group: groupFilter || undefined }).then(r => r.data),
    staleTime: 30_000,
  })
  const { data: combos = [] } = useQuery({
    queryKey: ['shoe-combos', 'reference'],
    queryFn: () => listShoeCombos().then(r => r.data),
    staleTime: Infinity,
  })
  const { data: guarantee } = useQuery({
    queryKey: ['shoe-guarantee', 'reference'],
    queryFn: () => getShoeGuarantee().then(r => r.data),
    staleTime: Infinity,
  })

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 max-w-5xl mx-auto">
      <PageHeader title="Shoe Repairs" />
      <p className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
        Soles, heels, stitching, cleaning, and more. Multi-pair intake with combo pricing.
      </p>

      <div className="mb-6 flex items-center gap-2">
        <div className="inline-flex rounded-lg p-1" style={{ backgroundColor: '#F3EADF' }}>
          <Link
            to="/shoe-repairs"
            className="px-3 py-1.5 text-xs font-semibold rounded-md transition"
            style={{
              backgroundColor: 'transparent',
              color: 'var(--cafe-text-muted)',
              textDecoration: 'none',
            }}
          >
            Jobs
          </Link>
          <span
            className="px-3 py-1.5 text-xs font-semibold rounded-md"
            style={{ backgroundColor: 'var(--cafe-paper)', color: 'var(--cafe-text)' }}
          >
            Services
          </span>
        </div>
      </div>

      {/* Combos & Guarantee */}
      {(combos.length > 0 || guarantee) && (
        <div className="mb-8 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
            Combo pricing & guarantee
          </h2>
          {combos.map(combo => (
            <div
              key={combo.id}
              className="rounded-xl px-4 py-3 text-sm"
              style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{combo.name}</span>
                {(combo.discount || combo.discounts?.length) && (
                  <span className="text-xs font-bold rounded-full px-2 py-0.5" style={{ backgroundColor: 'var(--cafe-amber)', color: '#fff' }}>
                    {combo.discount ?? combo.discounts?.join(', ')}
                  </span>
                )}
              </div>
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{combo.rule}</p>
            </div>
          ))}
          {guarantee && (
            <div
              className="rounded-xl px-4 py-3 flex items-start gap-2 text-sm"
              style={{ backgroundColor: 'rgba(130,160,100,0.08)', border: '1px solid rgba(130,160,100,0.25)' }}
            >
              <Shield size={14} className="mt-0.5 shrink-0" style={{ color: '#6A9A50' }} />
              <p style={{ color: 'var(--cafe-text)' }}>{guarantee.shoe_repairs}</p>
            </div>
          )}
        </div>
      )}

      {/* Service catalogue */}
      <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
        Service reference
      </h2>
      <p className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>
        Browse services by group. Use when creating jobs to ensure consistent naming and pricing.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search services..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-10 rounded-xl border pl-9 pr-3 text-sm outline-none focus:ring-2"
            style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)', color: 'var(--cafe-text)' }}
          />
        </div>
        <select
          value={groupFilter}
          onChange={e => setGroupFilter(e.target.value)}
          className="h-10 rounded-xl border px-3 text-sm sm:w-48"
          style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)', color: 'var(--cafe-text)' }}
        >
          <option value="">All groups</option>
          {groups.map(g => (
            <option key={g.id} value={g.id}>{g.label ?? g.id}</option>
          ))}
        </select>
      </div>
      <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-surface)' }}>
        <div className="max-h-[400px] overflow-y-auto">
          {items.length === 0 ? (
            <p className="px-5 py-8 text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No services match your search.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase" style={{ borderBottom: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}>
                  <th className="px-4 py-3 font-medium">Service</th>
                  <th className="px-4 py-3 font-medium">Group</th>
                  <th className="px-4 py-3 font-medium text-right">Price</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.key} style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                    <td className="px-4 py-2.5">
                      <span className="font-medium" style={{ color: 'var(--cafe-text)' }}>{item.name}</span>
                      {item.notes && (
                        <span className="block text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>{item.notes}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs" style={{ backgroundColor: '#EEE6DA', color: 'var(--cafe-text-mid)' }}>
                        <Tag size={10} />{item.group_label ?? item.group_id}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium" style={{ color: 'var(--cafe-amber)' }}>
                      {formatPrice(item)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
