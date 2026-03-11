import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, ChevronDown, Shield, Tag } from 'lucide-react'
import {
  listShoeRepairJobs, updateShoeRepairJobStatus, getShoeGuarantee, listShoeCombos,
  formatShoePricingType,
  type ShoeRepairJob, type ShoeRepairJobItem, type ShoePricingType
} from '@/lib/api'

const FROM_PRICING_TYPES: ShoePricingType[] = [
  'from', 'pair_from', 'each_from', 'from_per_boot', 'from_per_strap', 'quoted_upon_inspection',
]

function itemPriceDisplay(item: ShoeRepairJobItem): string {
  const isPriceAdjustable = FROM_PRICING_TYPES.includes(item.pricing_type as ShoePricingType)
  if (item.unit_price_cents == null) return 'Quoted'
  if (isPriceAdjustable) {
    // Show the actual agreed price — not "From $X"
    return `$${(item.unit_price_cents / 100).toFixed(2)}`
  }
  return formatShoePricingType(item.pricing_type as ShoePricingType, item.unit_price_cents)
}
import { Card, PageHeader, Button, Spinner, EmptyState, Badge } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewShoeJobModal from '@/components/NewShoeJobModal'

const SHOE_STATUSES = [
  'awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'working_on',
  'completed', 'awaiting_collection', 'collected', 'no_go',
]

const SHOE_STATUS_LABELS: Record<string, string> = {
  awaiting_quote: 'Awaiting Quote',
  awaiting_go_ahead: 'Awaiting Go Ahead',
  go_ahead: 'Go Ahead Given',
  working_on: 'Working On',
  completed: 'Work Completed',
  awaiting_collection: 'Ready for Collection',
  collected: 'Collected',
  no_go: 'No Go',
}

function JobCard({ job }: { job: ShoeRepairJob }) {
  const qc = useQueryClient()
  const [showItems, setShowItems] = useState(false)
  const [updatingStatus, setUpdatingStatus] = useState(false)

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateShoeRepairJobStatus(job.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] }),
  })

  const total = job.items.reduce((sum, item) =>
    sum + (item.unit_price_cents != null ? item.unit_price_cents * item.quantity : 0), 0)

  return (
    <Card className="p-0 overflow-hidden">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-xs font-mono font-bold tracking-wide"
                style={{ color: 'var(--cafe-amber)' }}
              >
                #{job.job_number}
              </span>
              <Badge status={job.status} />
              {job.priority === 'urgent' && (
                <span className="text-xs font-semibold rounded-full px-2 py-0.5 bg-red-100 text-red-700">Urgent</span>
              )}
            </div>
            <h3 className="font-semibold text-sm leading-snug" style={{ color: 'var(--cafe-text)' }}>
              {job.title}
            </h3>
            {job.description && (
              <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--cafe-text-muted)' }}>{job.description}</p>
            )}
          </div>

          {total > 0 && (
            <div className="text-right shrink-0">
              <p className="text-sm font-bold" style={{ color: 'var(--cafe-text)' }}>
                ${(total / 100).toFixed(2)}
              </p>
              <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>estimated</p>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 mt-3 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
          <span>{formatDate(job.created_at)}</span>
          {job.salesperson && <span>· {job.salesperson}</span>}
          {job.deposit_cents > 0 && (
            <span>· Deposit ${(job.deposit_cents / 100).toFixed(2)}</span>
          )}
          {job.collection_date && (
            <span>· Collect {job.collection_date}</span>
          )}
        </div>

        {/* Items toggle */}
        {job.items.length > 0 && (
          <button
            type="button"
            onClick={() => setShowItems(v => !v)}
            className="flex items-center gap-1.5 mt-3 text-xs font-medium transition-colors"
            style={{ color: 'var(--cafe-text-muted)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
          >
            <Tag size={12} />
            {job.items.length} service{job.items.length !== 1 ? 's' : ''}
            <ChevronDown size={12} className={`transition-transform ${showItems ? 'rotate-180' : ''}`} />
          </button>
        )}

        {showItems && (
          <div className="mt-3 rounded-xl overflow-hidden" style={{ border: '1px solid var(--cafe-border)' }}>
            {job.items.map(item => (
              <div
                key={item.id}
                className="flex items-center justify-between gap-3 px-3 py-2.5 border-b last:border-b-0 text-sm"
                style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate" style={{ color: 'var(--cafe-text)' }}>{item.item_name}</p>
                  <p className="text-xs capitalize" style={{ color: 'var(--cafe-text-muted)' }}>
                    {item.catalogue_group.replace(/_/g, ' ')}
                    {item.notes ? ` · ${item.notes}` : ''}
                  </p>
                </div>
                <p className="text-xs font-semibold shrink-0" style={{ color: 'var(--cafe-amber)' }}>
                  {itemPriceDisplay(item)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Status update footer */}
      <div
        className="px-5 py-3 flex items-center gap-2"
        style={{ backgroundColor: 'var(--cafe-bg)', borderTop: '1px solid var(--cafe-border)' }}
      >
        <select
          value={job.status}
          disabled={updatingStatus}
          onChange={async e => {
            setUpdatingStatus(true)
            await statusMutation.mutateAsync(e.target.value)
            setUpdatingStatus(false)
          }}
          className="flex-1 h-8 rounded-lg border px-2 text-xs outline-none focus:ring-1"
          style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text)' }}
        >
          {SHOE_STATUSES.map(s => (
            <option key={s} value={s}>{SHOE_STATUS_LABELS[s] ?? s}</option>
          ))}
        </select>
      </div>
    </Card>
  )
}

// ── Combo info cards ──────────────────────────────────────────────────────────
function ComboBanner() {
  const [expanded, setExpanded] = useState(false)
  const { data: combos } = useQuery({
    queryKey: ['shoe-combos'],
    queryFn: () => listShoeCombos().then(r => r.data),
    staleTime: Infinity,
  })
  const { data: guarantee } = useQuery({
    queryKey: ['shoe-guarantee'],
    queryFn: () => getShoeGuarantee().then(r => r.data),
    staleTime: Infinity,
  })

  if (!combos && !guarantee) return null

  return (
    <div className="mb-6">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-2 text-sm font-medium mb-2 transition-colors"
        style={{ color: 'var(--cafe-text-muted)' }}
        onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
      >
        <Shield size={14} />
        Pricing combos &amp; guarantee
        <ChevronDown size={13} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="space-y-2">
          {(combos ?? []).map(combo => (
            <div
              key={combo.id}
              className="rounded-xl px-4 py-3 text-sm"
              style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>{combo.name}</span>
                {combo.discount && (
                  <span
                    className="text-xs font-bold rounded-full px-2 py-0.5"
                    style={{ backgroundColor: 'var(--cafe-amber)', color: '#fff' }}
                  >
                    {combo.discount}
                  </span>
                )}
                {combo.discounts && combo.discounts.map(d => (
                  <span
                    key={d}
                    className="text-xs font-bold rounded-full px-2 py-0.5"
                    style={{ backgroundColor: 'var(--cafe-amber)', color: '#fff' }}
                  >
                    {d}
                  </span>
                ))}
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
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function ShoeRepairsPage() {
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['shoe-repair-jobs'],
    queryFn: () => listShoeRepairJobs().then(r => r.data),
  })

  const filtered = (jobs ?? []).filter(job => {
    if (statusFilter !== 'all' && job.status !== statusFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return (
        job.job_number.toLowerCase().includes(q) ||
        job.title.toLowerCase().includes(q) ||
        (job.description ?? '').toLowerCase().includes(q) ||
        job.items.some(i => i.item_name.toLowerCase().includes(q))
      )
    }
    return true
  })

  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8 max-w-5xl mx-auto">
      <PageHeader
        title="Shoe Repairs"
        action={
          <Button onClick={() => setShowAdd(true)}>
            <Plus size={16} />
            New Job
          </Button>
        }
      />

      <ComboBanner />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row mb-6">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search jobs or services…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-10 rounded-xl border pl-9 pr-3 text-sm outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              borderColor: 'var(--cafe-border)',
              color: 'var(--cafe-text)',
            }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="h-10 rounded-xl border px-3 text-sm outline-none focus:ring-2 sm:w-48"
          style={{ backgroundColor: 'var(--cafe-surface)', borderColor: 'var(--cafe-border)', color: 'var(--cafe-text)' }}
        >
          <option value="all">All statuses</option>
          {SHOE_STATUSES.map(s => (
            <option key={s} value={s}>{SHOE_STATUS_LABELS[s]}</option>
          ))}
        </select>
      </div>

      {isLoading && <Spinner />}

      {!isLoading && filtered.length === 0 && (
        <EmptyState message={jobs?.length === 0 ? 'No shoe repair jobs yet — create one to get started.' : 'No jobs match the current filters.'} />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {filtered.map(job => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>

      {showAdd && <NewShoeJobModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}
