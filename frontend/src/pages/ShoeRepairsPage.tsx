import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Search, ChevronDown, Shield, Tag, Camera, Upload, X } from 'lucide-react'
import {
  deleteShoeRepairJob,
  getApiErrorMessage,
  listShoeRepairJobs, updateShoeRepairJobStatus, getShoeGuarantee, listShoeCombos,
  formatShoePricingType, listShoeAttachments, uploadShoeAttachment, getAttachmentDownloadUrl,
  type ShoeRepairJob, type ShoeRepairJobItem, type ShoePricingType
} from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState, Badge, Modal } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import NewShoeJobModal from '@/components/NewShoeJobModal'

const FROM_PRICING_TYPES: ShoePricingType[] = [
  'from', 'pair_from', 'each_from', 'from_per_boot', 'from_per_strap', 'quoted_upon_inspection',
]

function itemPriceDisplay(item: ShoeRepairJobItem): string {
  const isPriceAdjustable = FROM_PRICING_TYPES.includes(item.pricing_type as ShoePricingType)
  if (item.unit_price_cents == null) return 'Quoted'
  if (isPriceAdjustable) {
    return `$${(item.unit_price_cents / 100).toFixed(2)}`
  }
  return formatShoePricingType(item.pricing_type as ShoePricingType, item.unit_price_cents)
}

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
  const navigate = useNavigate()
  const [showItems, setShowItems] = useState(false)
  const [showPhotos, setShowPhotos] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [updatingStatus, setUpdatingStatus] = useState(false)
  const [uploading, setUploading] = useState(false)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateShoeRepairJobStatus(job.id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteShoeRepairJob(job.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      setShowDeleteConfirm(false)
      setDeleteError('')
    },
    onError: (err) => {
      setDeleteError(getApiErrorMessage(err, 'Failed to delete job.'))
    },
  })

  const { data: photos } = useQuery({
    queryKey: ['shoe-attachments', job.id],
    queryFn: () => listShoeAttachments(job.id).then(r => r.data),
    enabled: showPhotos,
  })

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (!files.length) return
    setUploading(true)
    try {
      await Promise.all(files.map(f => uploadShoeAttachment(f, job.id)))
      qc.invalidateQueries({ queryKey: ['shoe-attachments', job.id] })
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const total = job.items.reduce((sum, item) =>
    sum + (item.unit_price_cents != null ? item.unit_price_cents * item.quantity : 0), 0)

  return (
    <>
      <Card className="p-0 overflow-hidden">
      {/* Clickable body — navigates to detail page */}
      <div
        className="px-5 py-4 cursor-pointer"
        onClick={() => navigate(`/shoe-repairs/${job.id}`)}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && navigate(`/shoe-repairs/${job.id}`)}
      >
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

          <button
            type="button"
            aria-label={`Delete job ${job.job_number}`}
            onClick={e => {
              e.stopPropagation()
              setDeleteError('')
              setShowDeleteConfirm(true)
            }}
            className="h-7 w-7 rounded-full flex items-center justify-center transition-colors shrink-0"
            style={{ color: '#A4664A', border: '1px solid #E7C6B7', backgroundColor: '#FFF7F3' }}
          >
            <X size={14} />
          </button>
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

        {/* Services toggle */}
        {job.items.length > 0 && (
          <button
            type="button"
            onClick={e => { e.stopPropagation(); setShowItems(v => !v) }}
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

        {/* Photos toggle */}
        <button
          type="button"
          onClick={e => { e.stopPropagation(); setShowPhotos(v => !v) }}
          className="flex items-center gap-1.5 mt-3 text-xs font-medium transition-colors"
          style={{ color: 'var(--cafe-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
        >
          <Camera size={12} />
          Photos{photos ? ` (${photos.length})` : ''}
          <ChevronDown size={12} className={`transition-transform ${showPhotos ? 'rotate-180' : ''}`} />
        </button>

        {showPhotos && (
          <div className="mt-3">
            {(photos ?? []).length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-3">
                {(photos ?? []).map(photo => (
                  <a
                    key={photo.id}
                    href={getAttachmentDownloadUrl(photo.storage_key)}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="block rounded-lg overflow-hidden"
                    style={{ border: '1px solid var(--cafe-border)', aspectRatio: '1' }}
                  >
                    <img
                      src={getAttachmentDownloadUrl(photo.storage_key)}
                      alt={photo.file_name ?? 'photo'}
                      className="w-full h-full object-cover"
                    />
                  </a>
                ))}
              </div>
            )}
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={handlePhotoUpload}
            />
            <input
              ref={photoInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handlePhotoUpload}
            />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={uploading}
                onClick={e => { e.stopPropagation(); cameraInputRef.current?.click() }}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  backgroundColor: 'var(--cafe-amber)',
                  border: '1px solid var(--cafe-amber)',
                  color: '#fff',
                  opacity: uploading ? 0.7 : 1,
                }}
              >
                <Camera size={11} />
                {uploading ? 'Uploading...' : 'Take photo'}
              </button>
              <button
                type="button"
                disabled={uploading}
                onClick={e => { e.stopPropagation(); photoInputRef.current?.click() }}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  backgroundColor: 'var(--cafe-surface)',
                  border: '1px dashed var(--cafe-border-2)',
                  color: uploading ? 'var(--cafe-text-muted)' : 'var(--cafe-amber)',
                }}
              >
                <Upload size={11} />
                Gallery upload
              </button>
            </div>
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
      {showDeleteConfirm && (
        <Modal
          title="Delete Job"
          onClose={() => {
            if (!deleteMutation.isPending) {
              setShowDeleteConfirm(false)
              setDeleteError('')
            }
          }}
        >
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--cafe-text)' }}>
              Are you sure you want to delete this job?
            </p>
            <div className="rounded-lg px-3 py-2" style={{ border: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
              <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
                #{job.job_number} · {job.title}
              </p>
            </div>
            <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              This action cannot be undone.
            </p>
            {deleteError && <p className="text-sm" style={{ color: '#C96A5A' }}>{deleteError}</p>}
            <div className="flex gap-2 pt-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowDeleteConfirm(false)
                  setDeleteError('')
                }}
                className="flex-1"
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => deleteMutation.mutate()}
                className="flex-1"
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Delete Job'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}

// -- Combo info cards ----------------------------------------------------------
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

// -- Page ---------------------------------------------------------------------
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
          <div className="flex flex-col items-end gap-1">
            <Button onClick={() => setShowAdd(true)}>
              <Plus size={16} />
              New Job
            </Button>
            <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
              After create, you can print tickets from the desktop flow.
            </span>
          </div>
        }
      />

      <ComboBanner />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row mb-6">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--cafe-text-muted)' }} />
          <input
            type="text"
            placeholder="Search jobs or services..."
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
        <EmptyState message={jobs?.length === 0 ? 'No shoe repair jobs yet - create one to get started.' : 'No jobs match the current filters.'} />
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
