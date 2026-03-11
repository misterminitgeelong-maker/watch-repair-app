import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { ChevronLeft, Camera, Upload, Tag, Pencil } from 'lucide-react'
import {
  getShoeRepairJob, updateShoeRepairJob, updateShoeRepairJobStatus,
  listShoeAttachments, uploadShoeAttachment, getAttachmentDownloadUrl,
  formatShoePricingType,
  type ShoeRepairJob, type ShoeRepairJobItem, type ShoePricingType,
} from '@/lib/api'
import { Card, PageHeader, Badge, Button, Modal, Select, Spinner, Input } from '@/components/ui'
import { formatDate } from '@/lib/utils'

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

// ── Status modal ───────────────────────────────────────────────────────────────
function StatusModal({ job, onClose }: { job: ShoeRepairJob; onClose: () => void }) {
  const qc = useQueryClient()
  const [status, setStatus] = useState(job.status)
  const [note, setNote] = useState('')
  const mut = useMutation({
    mutationFn: () => updateShoeRepairJobStatus(job.id, status, note || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', job.id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      onClose()
    },
  })

  return (
    <Modal title="Update Status" onClose={onClose}>
      <div className="space-y-3">
        <Select label="New Status" value={status} onChange={e => setStatus(e.target.value)}>
          {SHOE_STATUSES.map(s => (
            <option key={s} value={s}>{SHOE_STATUS_LABELS[s] ?? s}</option>
          ))}
        </Select>
        <Input label="Note (optional)" value={note} onChange={e => setNote(e.target.value)} placeholder="Ready for collection, waiting on parts…" />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>
            {mut.isPending ? 'Updating…' : 'Update'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function ShoeJobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [showStatus, setShowStatus] = useState(false)
  const [editingCost, setEditingCost] = useState(false)
  const [costInput, setCostInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const photoInputRef = useRef<HTMLInputElement>(null)

  const { data: job, isLoading } = useQuery({
    queryKey: ['shoe-repair-job', id],
    queryFn: () => getShoeRepairJob(id!).then(r => r.data),
  })

  const { data: photos } = useQuery({
    queryKey: ['shoe-attachments', id],
    queryFn: () => listShoeAttachments(id!).then(r => r.data),
    enabled: !!id,
  })

  const updateCostMutation = useMutation({
    mutationFn: (cost_cents: number) => updateShoeRepairJob(id!, { cost_cents }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      setEditingCost(false)
    },
  })

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (!files.length) return
    setUploading(true)
    try {
      await Promise.all(files.map(f => uploadShoeAttachment(f, id!)))
      qc.invalidateQueries({ queryKey: ['shoe-attachments', id] })
    } finally {
      setUploading(false)
      if (photoInputRef.current) photoInputRef.current.value = ''
    }
  }

  if (isLoading) return <Spinner />
  if (!job) return <p style={{ color: 'var(--cafe-text-muted)' }}>Job not found.</p>

  const total = job.items.reduce(
    (sum, item) => sum + (item.unit_price_cents != null ? item.unit_price_cents * item.quantity : 0),
    0,
  )

  return (
    <div>
      {/* Back link */}
      <div className="mb-5">
        <Link
          to="/shoe-repairs"
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--cafe-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
        >
          <ChevronLeft size={14} /> Back to Shoe Repairs
        </Link>
      </div>

      <PageHeader
        title={`#${job.job_number} · ${job.title}`}
        action={
          <Button variant="ghost" onClick={() => setShowStatus(true)}>Change Status</Button>
        }
      />

      {showStatus && <StatusModal job={job} onClose={() => setShowStatus(false)} />}

      {/* Summary strip */}
      <div className="flex flex-wrap gap-4 mb-6 text-sm">
        <span style={{ color: 'var(--cafe-text-muted)' }}>Status: <Badge status={job.status} /></span>
        <span style={{ color: 'var(--cafe-text-muted)' }}>
          Priority:{' '}
          <span
            className="font-medium capitalize"
            style={{
              color: job.priority === 'urgent' ? '#8B3A3A' : job.priority === 'high' ? '#9B4E0F' : 'var(--cafe-text)',
            }}
          >
            {job.priority}
          </span>
        </span>
        {total > 0 && (
          <span style={{ color: 'var(--cafe-text-muted)' }}>
            Estimated: <span className="font-medium" style={{ color: 'var(--cafe-text)' }}>${(total / 100).toFixed(2)}</span>
          </span>
        )}
        <span style={{ color: 'var(--cafe-text-muted)' }}>
          Created: <span style={{ color: 'var(--cafe-text)' }}>{formatDate(job.created_at)}</span>
        </span>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left column: Job Info */}
        <Card className="p-5 space-y-3">
          <h2 className="font-semibold text-xs uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>
            Job Info
          </h2>
          <div className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <span style={{ color: 'var(--cafe-text-muted)' }}>Job #</span>
              <span className="font-mono" style={{ color: 'var(--cafe-text)' }}>#{job.job_number}</span>
            </div>
            <div className="flex justify-between items-center">
              <span style={{ color: 'var(--cafe-text-muted)' }}>Status</span>
              <Badge status={job.status} />
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--cafe-text-muted)' }}>Priority</span>
              <span className="capitalize font-medium" style={{ color: 'var(--cafe-text)' }}>{job.priority}</span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--cafe-text-muted)' }}>Date In</span>
              <span style={{ color: 'var(--cafe-text)' }}>{formatDate(job.created_at)}</span>
            </div>
            {job.collection_date && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--cafe-text-muted)' }}>Collection</span>
                <span style={{ color: 'var(--cafe-text)' }}>{job.collection_date}</span>
              </div>
            )}
            {job.salesperson && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--cafe-text-muted)' }}>Salesperson</span>
                <span style={{ color: 'var(--cafe-text)' }}>{job.salesperson}</span>
              </div>
            )}
            {job.deposit_cents > 0 && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--cafe-text-muted)' }}>Deposit</span>
                <span className="font-medium" style={{ color: '#3B6B42' }}>${(job.deposit_cents / 100).toFixed(2)}</span>
              </div>
            )}
            {/* Cost / quote — editable */}
            <div className="flex justify-between items-center">
              <span style={{ color: 'var(--cafe-text-muted)' }}>Cost</span>
              {editingCost ? (
                <div className="flex items-center gap-1.5">
                  <span className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>$</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={costInput}
                    onChange={e => setCostInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        updateCostMutation.mutate(Math.round(parseFloat(costInput || '0') * 100))
                      }
                      if (e.key === 'Escape') setEditingCost(false)
                    }}
                    autoFocus
                    className="w-24 text-right text-sm rounded px-1.5 py-0.5"
                    style={{
                      border: '1px solid var(--cafe-border)',
                      background: 'var(--cafe-bg)',
                      color: 'var(--cafe-text)',
                    }}
                  />
                  <button
                    onClick={() => updateCostMutation.mutate(Math.round(parseFloat(costInput || '0') * 100))}
                    disabled={updateCostMutation.isPending}
                    className="text-xs px-2 py-0.5 rounded font-medium"
                    style={{ backgroundColor: '#EEE6DA', color: 'var(--cafe-text)' }}
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingCost(false)}
                    className="text-xs"
                    style={{ color: 'var(--cafe-text-muted)' }}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="font-medium" style={{ color: 'var(--cafe-text-mid)' }}>
                    {job.cost_cents > 0 ? `$${(job.cost_cents / 100).toFixed(2)}` : '—'}
                  </span>
                  <button
                    onClick={() => {
                      setCostInput(job.cost_cents > 0 ? (job.cost_cents / 100).toFixed(2) : '')
                      setEditingCost(true)
                    }}
                    className="opacity-50 hover:opacity-100 transition-opacity"
                    title="Edit cost"
                  >
                    <Pencil size={12} style={{ color: 'var(--cafe-text-muted)' }} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Right columns: Services + Description + Photos */}
        <div className="lg:col-span-2 flex flex-col gap-5">
          {/* Services */}
          {job.items.length > 0 && (
            <Card>
              <div
                className="flex items-center gap-2 px-5 py-3.5"
                style={{ borderBottom: '1px solid var(--cafe-border)' }}
              >
                <Tag size={14} style={{ color: 'var(--cafe-amber)' }} />
                <h2 className="font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  Services
                </h2>
                <span className="text-xs ml-auto font-mono" style={{ color: 'var(--cafe-text-muted)' }}>
                  {job.items.length} item{job.items.length !== 1 ? 's' : ''}
                </span>
              </div>
              <div>
                {job.items.map((item, i) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-3 px-5 py-3 text-sm"
                    style={{
                      borderBottom: i < job.items.length - 1 ? '1px solid var(--cafe-border)' : 'none',
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>{item.item_name}</p>
                      <p className="text-xs capitalize mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                        {item.catalogue_group.replace(/_/g, ' ')}
                        {item.quantity > 1 ? ` · qty ${item.quantity}` : ''}
                        {item.notes ? ` · ${item.notes}` : ''}
                      </p>
                    </div>
                    <span className="text-sm font-semibold shrink-0" style={{ color: 'var(--cafe-amber)' }}>
                      {itemPriceDisplay(item)}
                    </span>
                  </div>
                ))}
                {total > 0 && (
                  <div
                    className="flex justify-between px-5 py-3 text-sm font-semibold"
                    style={{ borderTop: '1px solid var(--cafe-border)', color: 'var(--cafe-text)' }}
                  >
                    <span>Total</span>
                    <span style={{ color: 'var(--cafe-amber)' }}>${(total / 100).toFixed(2)}</span>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Description */}
          {job.description && (
            <Card className="p-5">
              <h2 className="font-semibold text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--cafe-text-muted)' }}>
                Notes
              </h2>
              <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--cafe-text-mid)' }}>
                {job.description}
              </p>
            </Card>
          )}

          {/* Photos */}
          <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-xs uppercase tracking-widest flex items-center gap-1.5" style={{ color: 'var(--cafe-text-muted)' }}>
                <Camera size={13} />
                Photos{photos ? ` (${photos.length})` : ''}
              </h2>
              <button
                type="button"
                disabled={uploading}
                onClick={() => photoInputRef.current?.click()}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  backgroundColor: 'var(--cafe-surface)',
                  border: '1px dashed var(--cafe-border-2)',
                  color: uploading ? 'var(--cafe-text-muted)' : 'var(--cafe-amber)',
                }}
              >
                <Upload size={11} />
                {uploading ? 'Uploading…' : 'Add photos'}
              </button>
            </div>

            <input
              ref={photoInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handlePhotoUpload}
            />

            {(photos ?? []).length === 0 ? (
              <p className="text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                No photos yet.
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {(photos ?? []).map(photo => (
                  <a
                    key={photo.id}
                    href={getAttachmentDownloadUrl(photo.storage_key)}
                    target="_blank"
                    rel="noopener noreferrer"
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
          </Card>
        </div>
      </div>
    </div>
  )
}
