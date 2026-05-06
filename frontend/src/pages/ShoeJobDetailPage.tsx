import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { ChevronLeft, Camera, Upload, Tag, Pencil, Plus, X, Footprints, Printer, MessageSquare, RefreshCw, History } from 'lucide-react'
import {
  getShoeRepairJob, updateShoeRepairJob, updateShoeRepairJobStatus,
  listShoeAttachments, uploadShoeAttachment,
  listCustomerAccounts,
  listShoes, createShoe,
  addShoeToJob, appendShoeRepairJobItems, removeShoeFromJob, removeShoeRepairJobItem,
  formatShoePricingType,
  getShoeJobSmsLog, resendShoeNotification, sendShoeQuote,
  getShoeJobHistory,
  type ShoeRepairJob, type ShoeRepairJobItem, type ShoePricingType, type Shoe, type CustomerAccount, type SmsLogEntry, type ShoeJobHistoryEntry,
} from '@/lib/api'
import { SecureAttachmentImage, SecureAttachmentLink } from '@/components/SecureAttachment'
import ShoeServicePicker, { buildShoeRepairJobItemsPayload, type SelectedShoeService } from '@/components/ShoeServicePicker'
import { Card, PageHeader, Badge, Button, Modal, Select, Spinner, Input } from '@/components/ui'
import { formatDate, STATUS_LABELS } from '@/lib/utils'

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

function shoeLabel(shoe: Shoe | undefined): string {
  if (!shoe) return 'Pair'
  const parts = [shoe.brand, shoe.shoe_type, shoe.color].filter(Boolean)
  return parts.join(' · ') || 'Pair'
}

const SHOE_STATUSES = [
  'awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'working_on',
  'completed', 'awaiting_collection', 'collected', 'no_go',
]

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
            <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
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

// ── Add pair modal ────────────────────────────────────────────────────────────
function AddPairModal({ job, onClose }: { job: ShoeRepairJob; onClose: () => void }) {
  const qc = useQueryClient()
  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  const [selectedShoeId, setSelectedShoeId] = useState('')
  const [selectedItems, setSelectedItems] = useState<SelectedShoeService[]>([])
  // New shoe fields
  const [shoeType, setShoeType] = useState('')
  const [brand, setBrand] = useState('')
  const [color, setColor] = useState('')
  const [notes, setNotes] = useState('')

  // Need customer_id — get from primary shoe
  const customerId = job.shoe?.customer_id ?? ''

  const { data: existingShoes = [] } = useQuery({
    queryKey: ['shoes', customerId],
    queryFn: () => listShoes(customerId).then(r => r.data),
    enabled: !!customerId,
  })

  // Filter out shoes already on this job
  const usedIds = new Set([
    job.shoe_id,
    ...job.extra_shoes.map(e => e.shoe_id),
  ])
  const availableShoes = existingShoes.filter(s => !usedIds.has(s.id))

  const addMut = useMutation({
    mutationFn: async () => {
      let shoeId = selectedShoeId
      if (mode === 'new') {
        const res = await createShoe({ customer_id: customerId, shoe_type: shoeType || undefined, brand: brand || undefined, color: color || undefined, description_notes: notes || undefined })
        shoeId = res.data.id
      }
      await addShoeToJob(job.id, shoeId)
      if (selectedItems.length > 0) {
        return appendShoeRepairJobItems(job.id, buildShoeRepairJobItemsPayload(selectedItems))
      }
      return getShoeRepairJob(job.id)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', job.id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      onClose()
    },
  })

  const canSubmit = mode === 'new' ? (shoeType || brand || color) : !!selectedShoeId

  return (
    <Modal title="Add Another Pair" onClose={onClose}>
      <div className="space-y-4">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMode('existing')}
            className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{
              backgroundColor: mode === 'existing' ? 'var(--ms-accent)' : 'var(--ms-surface)',
              color: mode === 'existing' ? '#fff' : 'var(--ms-text-muted)',
              border: '1px solid var(--ms-border-strong)',
            }}
          >
            From this customer
          </button>
          <button
            type="button"
            onClick={() => setMode('new')}
            className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{
              backgroundColor: mode === 'new' ? 'var(--ms-accent)' : 'var(--ms-surface)',
              color: mode === 'new' ? '#fff' : 'var(--ms-text-muted)',
              border: '1px solid var(--ms-border-strong)',
            }}
          >
            New pair
          </button>
        </div>

        {mode === 'existing' ? (
          availableShoes.length === 0 ? (
            <p className="text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No other shoes on file for this customer. Use "New pair" instead.</p>
          ) : (
            <Select label="Choose shoe" value={selectedShoeId} onChange={e => setSelectedShoeId(e.target.value)}>
              <option value="">Select…</option>
              {availableShoes.map(s => (
                <option key={s.id} value={s.id}>{shoeLabel(s)}</option>
              ))}
            </Select>
          )
        ) : (
          <div className="space-y-3">
            <Input label="Type (e.g. boots, sneakers)" value={shoeType} onChange={e => setShoeType(e.target.value)} placeholder="boots" />
            <Input label="Brand" value={brand} onChange={e => setBrand(e.target.value)} placeholder="Nike, Timberland…" />
            <Input label="Colour" value={color} onChange={e => setColor(e.target.value)} placeholder="black, tan…" />
            <Input label="Notes" value={notes} onChange={e => setNotes(e.target.value)} placeholder="scuff on toe cap…" />
          </div>
        )}

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ms-text-muted)' }}>
            Services For This Pair
          </p>
          <ShoeServicePicker selected={selectedItems} onChange={setSelectedItems} />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => addMut.mutate()} disabled={!canSubmit || addMut.isPending}>
            {addMut.isPending ? 'Adding…' : 'Add Pair'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Add services modal ───────────────────────────────────────────────────────
function AddServicesModal({ job, onClose }: { job: ShoeRepairJob; onClose: () => void }) {
  const qc = useQueryClient()
  const [selectedItems, setSelectedItems] = useState<SelectedShoeService[]>([])
  const mut = useMutation({
    mutationFn: () => appendShoeRepairJobItems(job.id, buildShoeRepairJobItemsPayload(selectedItems)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', job.id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      onClose()
    },
  })
  return (
    <Modal title="Add Services" onClose={onClose}>
      <div className="space-y-4">
        <ShoeServicePicker selected={selectedItems} onChange={setSelectedItems} />
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={selectedItems.length === 0 || mut.isPending}>
            {mut.isPending ? 'Adding…' : `Add ${selectedItems.length > 0 ? selectedItems.length : ''} Service${selectedItems.length !== 1 ? 's' : ''}`}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Services card ──────────────────────────────────────────────────────────────
function ServicesCard({ job, onAddServices }: { job: ShoeRepairJob; onAddServices: () => void }) {
  const qc = useQueryClient()
  const removeMut = useMutation({
    mutationFn: (itemId: string) => removeShoeRepairJobItem(job.id, itemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', job.id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
    },
  })
  const total = job.items.reduce(
    (sum, item) => sum + (item.unit_price_cents != null ? item.unit_price_cents * item.quantity : 0),
    0,
  )
  return (
    <Card>
      <div
        className="flex items-center gap-2 px-5 py-3.5"
        style={{ borderBottom: '1px solid var(--ms-border)' }}
      >
        <Tag size={14} style={{ color: 'var(--ms-accent)' }} />
        <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>
          Services
        </h2>
        {job.items.length > 0 && (
          <span className="text-xs font-mono" style={{ color: 'var(--ms-text-muted)' }}>
            {job.items.length} item{job.items.length !== 1 ? 's' : ''}
          </span>
        )}
        <button
          type="button"
          onClick={onAddServices}
          className="ml-auto flex items-center gap-1 text-xs font-medium transition-colors"
          style={{ color: 'var(--ms-accent)' }}
        >
          <Plus size={13} /> Add service
        </button>
      </div>
      {job.items.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center gap-2 py-8 cursor-pointer"
          style={{ color: 'var(--ms-text-muted)' }}
          onClick={onAddServices}
        >
          <Tag size={24} style={{ opacity: 0.25 }} />
          <p className="text-xs">No services yet. Tap to add from the shoe repair catalogue.</p>
        </div>
      ) : (
        <div>
          {job.items.map((item, i) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 px-5 py-3 text-sm"
              style={{ borderBottom: i < job.items.length - 1 ? '1px solid var(--ms-border)' : 'none' }}
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium" style={{ color: 'var(--ms-text)' }}>{item.item_name}</p>
                <p className="text-xs capitalize mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                  {item.catalogue_group.replace(/_/g, ' ')}
                  {item.quantity > 1 ? ` · qty ${item.quantity}` : ''}
                  {item.notes ? ` · ${item.notes}` : ''}
                </p>
              </div>
              <span className="text-sm font-semibold shrink-0" style={{ color: 'var(--ms-accent)' }}>
                {itemPriceDisplay(item)}
              </span>
              <button
                type="button"
                onClick={() => removeMut.mutate(item.id)}
                disabled={removeMut.isPending}
                className="opacity-40 hover:opacity-100 transition-opacity"
                title="Remove service"
              >
                <X size={13} style={{ color: '#C96A5A' }} />
              </button>
            </div>
          ))}
          {total > 0 && (
            <div
              className="flex justify-between px-5 py-3 text-sm font-semibold"
              style={{ borderTop: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
            >
              <span>Total</span>
              <span style={{ color: 'var(--ms-accent)' }}>${(total / 100).toFixed(2)}</span>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ── Messages card ──────────────────────────────────────────────────────────────
function MessagesCard({ job }: { job: ShoeRepairJob }) {
  const qc = useQueryClient()
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['shoe-sms-log', job.id],
    queryFn: () => getShoeJobSmsLog(job.id).then(r => r.data),
  })
  const resendMut = useMutation({
    mutationFn: (event: string) => resendShoeNotification(job.id, event),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['shoe-sms-log', job.id] }) },
  })

  const RESEND_EVENTS = [
    { label: 'Job live', event: 'job_live' },
    { label: `Status: ${job.status}`, event: `status_${job.status}` },
  ]

  return (
    <Card className="overflow-hidden">
      <div
        className="px-5 py-3.5 flex items-center justify-between"
        style={{ borderBottom: '1px solid var(--ms-border)' }}
      >
        <div className="flex items-center gap-2">
          <MessageSquare size={14} style={{ color: 'var(--ms-accent)' }} />
          <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>
            Messages
          </h2>
          {logs.length > 0 && (
            <span className="text-xs font-mono" style={{ color: 'var(--ms-text-muted)' }}>{logs.length}</span>
          )}
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Resend buttons */}
        <div className="flex flex-wrap gap-2">
          {RESEND_EVENTS.map(({ label, event }) => (
            <button
              key={event}
              type="button"
              onClick={() => resendMut.mutate(event)}
              disabled={resendMut.isPending}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-accent)' }}
            >
              <RefreshCw size={11} className={resendMut.isPending ? 'animate-spin' : ''} />
              Resend: {label}
            </button>
          ))}
        </div>

        {/* Log */}
        {isLoading ? (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Loading…</p>
        ) : logs.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>No messages sent yet.</p>
        ) : (
          <div className="space-y-3">
            {logs.map((log: SmsLogEntry) => (
              <div key={log.id} className="text-xs rounded-lg p-3" style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{log.event.replace(/_/g, ' ')}</span>
                  <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                    style={{
                      backgroundColor: log.status === 'sent' ? 'rgba(31,109,76,0.12)' : 'rgba(180,120,40,0.15)',
                      color: log.status === 'sent' ? '#1F6D4C' : '#B47828',
                    }}
                  >
                    {log.status}
                  </span>
                </div>
                <p style={{ color: 'var(--ms-text-mid)' }}>{log.body}</p>
                <p className="mt-1" style={{ color: 'var(--ms-text-muted)' }}>{new Date(log.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

// ── Shoe tab content ──────────────────────────────────────────────────────────
function ShoeTab({ shoe }: { shoe: Shoe | undefined }) {
  if (!shoe) return <p className="text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No shoe details.</p>
  const rows = [
    ['Type', shoe.shoe_type],
    ['Brand', shoe.brand],
    ['Colour', shoe.color],
    ['Notes', shoe.description_notes],
  ].filter(([, v]) => v)

  if (rows.length === 0) return <p className="text-sm italic" style={{ color: 'var(--ms-text-muted)' }}>No shoe details recorded.</p>

  return (
    <div className="space-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="flex gap-3">
          <span className="w-16 shrink-0 text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{label}</span>
          <span style={{ color: 'var(--ms-text)' }}>{value}</span>
        </div>
      ))}
    </div>
  )
}

// ── History card ──────────────────────────────────────────────────────────────
function HistoryCard({ jobId }: { jobId: string }) {
  const { data: history = [], isLoading } = useQuery({
    queryKey: ['shoe-history', jobId],
    queryFn: () => getShoeJobHistory(jobId).then(r => r.data),
  })
  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3.5 flex items-center gap-2" style={{ borderBottom: '1px solid var(--ms-border)' }}>
        <History size={14} style={{ color: 'var(--ms-accent)' }} />
        <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>History</h2>
        {history.length > 0 && <span className="text-xs font-mono" style={{ color: 'var(--ms-text-muted)' }}>{history.length}</span>}
      </div>
      <div className="p-5">
        {isLoading ? (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-xs italic" style={{ color: 'var(--ms-text-muted)' }}>No history yet.</p>
        ) : (
          <div className="relative pl-5 space-y-4">
            <div className="absolute left-1.5 top-0 bottom-0 w-0.5" style={{ backgroundColor: 'var(--ms-border-strong)' }} />
            {history.map((h: ShoeJobHistoryEntry) => {
              const isNote = h.old_status === h.new_status
              return (
                <div key={h.id} className="relative">
                  <div className="absolute -left-[18px] top-1.5 w-2 h-2 rounded-full border-2" style={{ backgroundColor: isNote ? 'var(--ms-bg)' : 'var(--ms-accent)', borderColor: isNote ? 'var(--ms-border-strong)' : 'var(--ms-accent)' }} />
                  <p className="text-xs font-medium" style={{ color: 'var(--ms-text)' }}>
                    {isNote ? 'Note added' : `${STATUS_LABELS[h.old_status ?? ''] ?? h.old_status ?? '—'} → ${STATUS_LABELS[h.new_status] ?? h.new_status}`}
                  </p>
                  {h.change_note && (
                    <p className="text-xs mt-0.5 italic" style={{ color: 'var(--ms-text-mid)' }}>{h.change_note}</p>
                  )}
                  <p className="text-[11px] mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>{formatDate(h.created_at)}</p>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Card>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function ShoeJobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [showStatus, setShowStatus] = useState(false)
  const [showAddPair, setShowAddPair] = useState(false)
  const sendQuoteMut = useMutation({
    mutationFn: () => sendShoeQuote(id!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['shoe-repair-job', id] }) },
  })
  const [showAddServices, setShowAddServices] = useState(false)
  const [activePairIdx, setActivePairIdx] = useState(0)
  const [editingCost, setEditingCost] = useState(false)
  const [costInput, setCostInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)

  const { data: job, isLoading } = useQuery({
    queryKey: ['shoe-repair-job', id],
    queryFn: () => getShoeRepairJob(id!).then(r => r.data),
  })

  const { data: photos = [] } = useQuery({
    queryKey: ['shoe-attachments', id],
    queryFn: () => listShoeAttachments(id!).then(r => r.data),
    enabled: !!id,
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const matchingAccounts = job?.shoe?.customer_id
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(job.shoe!.customer_id))
    : customerAccounts

  const updateAccountMutation = useMutation({
    mutationFn: (customer_account_id: string | null) => updateShoeRepairJob(id!, { customer_account_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
    },
  })

  const updateCostMutation = useMutation({
    mutationFn: (cost_cents: number) => updateShoeRepairJob(id!, { cost_cents }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', id] })
      qc.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
      setEditingCost(false)
    },
  })

  const removePairMutation = useMutation({
    mutationFn: (entryId: string) => removeShoeFromJob(id!, entryId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shoe-repair-job', id] })
      setActivePairIdx(0)
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
      e.target.value = ''
    }
  }

  if (isLoading) return <Spinner />
  if (!job) return <p style={{ color: 'var(--ms-text-muted)' }}>Job not found.</p>

  const allShoes = [
    { id: 'primary', shoe: job.shoe, isPrimary: true, entryId: null as string | null },
    ...job.extra_shoes.map(e => ({ id: e.id, shoe: e.shoe, isPrimary: false, entryId: e.id })),
  ]
  // Guard index
  const safeIdx = Math.min(activePairIdx, allShoes.length - 1)
  const activePair = allShoes[safeIdx]

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
          style={{ color: 'var(--ms-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--ms-accent)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--ms-text-muted)')}
        >
          <ChevronLeft size={14} /> Back to Shoe Repairs
        </Link>
      </div>

      <PageHeader
        title={`#${job.job_number} · ${job.title}`}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => window.open(`/shoe-repairs/${job.id}/intake-print?autoprint=1`, '_blank', 'noopener,noreferrer')}>
              <Printer size={15} /><span className="hidden sm:inline">Print Intake Tickets</span>
            </Button>
            <Button
              variant="secondary"
              onClick={() => sendQuoteMut.mutate()}
              disabled={sendQuoteMut.isPending || job.quote_status === 'approved'}
              title={job.quote_status === 'approved' ? 'Quote already approved' : 'Send quote approval SMS to customer'}
            >
              {sendQuoteMut.isPending ? 'Sending…' : job.quote_status === 'sent' ? 'Resend Quote' : job.quote_status === 'approved' ? 'Approved ✓' : 'Send Quote'}
            </Button>
            <Button variant="ghost" onClick={() => setShowStatus(true)}>
              <span className="hidden sm:inline">Change Status</span>
              <span className="sm:hidden">Status</span>
            </Button>
          </div>
        }
      />

      {showStatus && <StatusModal job={job} onClose={() => setShowStatus(false)} />}
      {showAddPair && <AddPairModal job={job} onClose={() => setShowAddPair(false)} />}
      {showAddServices && <AddServicesModal job={job} onClose={() => setShowAddServices(false)} />}

      {/* Summary strip */}
      <div className="flex flex-wrap gap-4 mb-6 text-sm">
        <span style={{ color: 'var(--ms-text-muted)' }}>Status: <Badge status={job.status} /></span>
        {job.quote_status !== 'none' && (
          <span style={{ color: 'var(--ms-text-muted)' }}>
            Quote:{' '}
            <span
              className="font-medium capitalize"
              style={{
                color: job.quote_status === 'approved' ? '#1F6D4C'
                  : job.quote_status === 'declined' ? '#8B3A3A'
                  : 'var(--ms-accent)',
              }}
            >
              {job.quote_status}
            </span>
          </span>
        )}
        <span style={{ color: 'var(--ms-text-muted)' }}>
          Priority:{' '}
          <span
            className="font-medium capitalize"
            style={{
              color: job.priority === 'urgent' ? '#8B3A3A' : job.priority === 'high' ? '#9B4E0F' : 'var(--ms-text)',
            }}
          >
            {job.priority}
          </span>
        </span>
        {total > 0 && (
          <span style={{ color: 'var(--ms-text-muted)' }}>
            Estimated: <span className="font-medium" style={{ color: 'var(--ms-text)' }}>${(total / 100).toFixed(2)}</span>
          </span>
        )}
        <span style={{ color: 'var(--ms-text-muted)' }}>
          Created: <span style={{ color: 'var(--ms-text)' }}>{formatDate(job.created_at)}</span>
        </span>
      </div>

      {/* Photo hero — full-width 4-col grid above main grid */}
      <Card className="overflow-hidden mb-5">
        <div
          className="px-5 py-3.5 flex items-center justify-between flex-wrap gap-2"
          style={{ borderBottom: photos.length > 0 ? '1px solid var(--ms-border)' : 'none' }}
        >
          <div className="flex items-center gap-2">
            <Camera size={14} style={{ color: 'var(--ms-accent)' }} />
            <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>
              Photos
            </h2>
            {photos.length > 0 && (
              <span className="text-xs font-mono" style={{ color: 'var(--ms-text-muted)' }}>{photos.length}</span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={uploading}
              onClick={() => cameraInputRef.current?.click()}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              style={{
                backgroundColor: 'var(--ms-accent)',
                border: '1px solid var(--ms-accent)',
                color: '#fff',
                opacity: uploading ? 0.7 : 1,
              }}
            >
              <Camera size={11} />
              {uploading ? 'Uploading…' : 'Take photo'}
            </button>
            <button
              type="button"
              disabled={uploading}
              onClick={() => photoInputRef.current?.click()}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              style={{
                backgroundColor: 'var(--ms-surface)',
                border: '1px dashed var(--ms-border-strong)',
                color: uploading ? 'var(--ms-text-muted)' : 'var(--ms-accent)',
              }}
            >
              <Upload size={11} />
              Gallery upload
            </button>
          </div>
        </div>
        <input ref={cameraInputRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
        <input ref={photoInputRef} type="file" accept="image/*" multiple className="hidden" onChange={handlePhotoUpload} />
        {photos.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center gap-2 py-8 cursor-pointer"
            style={{ color: 'var(--ms-text-muted)' }}
            onClick={() => cameraInputRef.current?.click()}
          >
            <Camera size={28} style={{ opacity: 0.3 }} />
            <p className="text-xs mt-2">No photos yet. Tap to add intake or gallery photos.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 p-5">
            {photos.map(photo => (
              <SecureAttachmentLink key={photo.id} storageKey={photo.storage_key} target="_blank" rel="noopener noreferrer" className="group">
                <SecureAttachmentImage storageKey={photo.storage_key} alt={photo.label || 'Shoe photo'} className="w-full aspect-square object-cover rounded-lg transition-shadow" style={{ border: '1px solid var(--ms-border)' }} />
                <p className="text-[10px] text-center mt-1" style={{ color: 'var(--ms-text-muted)' }}>{photo.label || 'Photo'}</p>
              </SecureAttachmentLink>
            ))}
          </div>
        )}
      </Card>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left column */}
        <div className="flex flex-col gap-5">

          {/* ── Shoes section with tabs ─────────────────────────── */}
          <Card className="overflow-hidden">
            <div
              className="px-5 py-3.5 flex items-center justify-between"
              style={{ borderBottom: '1px solid var(--ms-border)' }}
            >
              <div className="flex items-center gap-2">
                <Footprints size={14} style={{ color: 'var(--ms-accent)' }} />
                <h2 className="font-semibold" style={{ color: 'var(--ms-text)' }}>
                  Shoes
                </h2>
                <span className="text-xs font-mono" style={{ color: 'var(--ms-text-muted)' }}>
                  {allShoes.length} pair{allShoes.length !== 1 ? 's' : ''}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowAddPair(true)}
                className="flex items-center gap-1 text-xs font-medium transition-colors"
                style={{ color: 'var(--ms-accent)' }}
                title="Add another pair"
              >
                <Plus size={13} /> Add pair
              </button>
            </div>

            {/* Pair tabs */}
            {allShoes.length > 1 && (
              <div className="flex gap-0 overflow-x-auto" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                {allShoes.map((pair, idx) => (
                  <button
                    key={pair.id}
                    type="button"
                    onClick={() => setActivePairIdx(idx)}
                    className="flex-shrink-0 px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap"
                    style={{
                      borderBottomColor: safeIdx === idx ? 'var(--ms-accent)' : 'transparent',
                      color: safeIdx === idx ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
                      fontWeight: safeIdx === idx ? 700 : 500,
                      marginBottom: '-1px',
                    }}
                  >
                    Pair {idx + 1}
                  </button>
                ))}
              </div>
            )}

            {/* Active pair details */}
            <div className="p-5">
              <div className="flex items-start justify-between gap-2 mb-3">
                <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>
                  {activePair.isPrimary ? 'Primary pair' : `Pair ${safeIdx + 1}`}
                </p>
                {!activePair.isPrimary && activePair.entryId && (
                  <button
                    type="button"
                    onClick={() => removePairMutation.mutate(activePair.entryId!)}
                    disabled={removePairMutation.isPending}
                    className="text-xs opacity-50 hover:opacity-100 transition-opacity flex items-center gap-0.5"
                    style={{ color: '#C96A5A' }}
                    title="Remove this pair from job"
                  >
                    <X size={12} /> Remove
                  </button>
                )}
              </div>
              <ShoeTab shoe={activePair.shoe} />
            </div>
          </Card>

          {/* ── Job Info ──────────────────────────────────────────── */}
          <Card className="p-5 space-y-3">
            <h2 className="font-semibold text-xs uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>
              Job Info
            </h2>
            <div className="space-y-2.5 text-sm">
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Job #</span>
                <span className="font-mono" style={{ color: 'var(--ms-text)' }}>#{job.job_number}</span>
              </div>
              <div className="flex justify-between items-center">
                <span style={{ color: 'var(--ms-text-muted)' }}>Status</span>
                <Badge status={job.status} />
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Priority</span>
                <span className="capitalize font-medium" style={{ color: 'var(--ms-text)' }}>{job.priority}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Date In</span>
                <span style={{ color: 'var(--ms-text)' }}>{formatDate(job.created_at)}</span>
              </div>
              {job.collection_date && (
                <div className="flex justify-between">
                  <span style={{ color: 'var(--ms-text-muted)' }}>Collection</span>
                  <span style={{ color: 'var(--ms-text)' }}>{job.collection_date}</span>
                </div>
              )}
              {job.salesperson && (
                <div className="flex justify-between">
                  <span style={{ color: 'var(--ms-text-muted)' }}>Salesperson</span>
                  <span style={{ color: 'var(--ms-text)' }}>{job.salesperson}</span>
                </div>
              )}
              {job.deposit_cents > 0 && (
                <div className="flex justify-between">
                  <span style={{ color: 'var(--ms-text-muted)' }}>Deposit</span>
                  <span className="font-medium" style={{ color: '#3B6B42' }}>${(job.deposit_cents / 100).toFixed(2)}</span>
                </div>
              )}
              <div className="space-y-1">
                <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Customer Account</span>
                <Select
                  value={job.customer_account_id ?? ''}
                  onChange={e => updateAccountMutation.mutate(e.target.value || null)}
                  disabled={updateAccountMutation.isPending}
                >
                  <option value="">No B2B account</option>
                  {matchingAccounts.map((account: CustomerAccount) => (
                    <option key={account.id} value={account.id}>
                      {account.name}{account.account_code ? ` (${account.account_code})` : ''}
                    </option>
                  ))}
                </Select>
              </div>
              {/* Cost — editable */}
              <div className="flex justify-between items-center">
                <span style={{ color: 'var(--ms-text-muted)' }}>Cost</span>
                {editingCost ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>$</span>
                    <input
                      type="number" min="0" step="0.01"
                      value={costInput}
                      onChange={e => setCostInput(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') updateCostMutation.mutate(Math.round(parseFloat(costInput || '0') * 100))
                        if (e.key === 'Escape') setEditingCost(false)
                      }}
                      autoFocus
                      className="w-24 text-right text-sm rounded px-1.5 py-0.5"
                      style={{ border: '1px solid var(--ms-border)', background: 'var(--ms-bg)', color: 'var(--ms-text)' }}
                    />
                    <button
                      onClick={() => updateCostMutation.mutate(Math.round(parseFloat(costInput || '0') * 100))}
                      disabled={updateCostMutation.isPending}
                      className="text-xs px-2 py-0.5 rounded font-medium"
                      style={{ backgroundColor: '#EEE6DA', color: 'var(--ms-text)' }}
                    >Save</button>
                    <button onClick={() => setEditingCost(false)} className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>✕</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="font-medium" style={{ color: 'var(--ms-text-mid)' }}>
                      {job.cost_cents > 0 ? `$${(job.cost_cents / 100).toFixed(2)}` : '—'}
                    </span>
                    <button
                      onClick={() => { setCostInput(job.cost_cents > 0 ? (job.cost_cents / 100).toFixed(2) : ''); setEditingCost(true) }}
                      className="opacity-50 hover:opacity-100 transition-opacity" title="Edit cost"
                    >
                      <Pencil size={12} style={{ color: 'var(--ms-text-muted)' }} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Right columns: Services + Description */}
        <div className="lg:col-span-2 flex flex-col gap-5">

          {/* ── Services ──────────────────────────────────────────── */}
          <ServicesCard job={job} onAddServices={() => setShowAddServices(true)} />

          {/* ── Description ───────────────────────────────────────── */}
          {job.description && (
            <Card className="p-5">
              <h2 className="font-semibold text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                Notes
              </h2>
              <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--ms-text-mid)' }}>
                {job.description}
              </p>
            </Card>
          )}

          {/* ── Messages ──────────────────────────────────────────── */}
          <MessagesCard job={job} />

          {/* ── History ───────────────────────────────────────────── */}
          <HistoryCard jobId={job.id} />
        </div>
      </div>
    </div>
  )
}
