import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { ChevronLeft, ArrowRight, Clock, Paperclip, History, FileText, Plus, Download, Upload, Camera, Pencil, Printer } from 'lucide-react'
import {
  getJob, quickStatusAction, updateJobStatus, updateJob, listQuotes,
  listWorkLogs, createWorkLog,
  listAttachments, uploadAttachment, getAttachmentDownloadUrl,
  getStatusHistory,
  listCustomerAccounts, getWatch,
  type JobStatus, type RepairJob, type CustomerAccount,
} from '@/lib/api'
import { Card, PageHeader, Badge, Button, Modal, Select, Spinner, EmptyState, Input, Textarea } from '@/components/ui'
import { formatDate, STATUS_LABELS } from '@/lib/utils'

const STATUS_FLOW: Record<JobStatus, JobStatus | null> = {
  awaiting_quote:      'awaiting_go_ahead',
  awaiting_go_ahead:   'go_ahead',
  go_ahead:            'working_on',
  no_go:               null,
  working_on:          'completed',
  awaiting_parts:      'working_on',
  parts_to_order:      'sent_to_labanda',
  sent_to_labanda:     'quoted_by_labanda',
  quoted_by_labanda:   'awaiting_parts',
  service:             'completed',
  completed:           'awaiting_collection',
  awaiting_collection: 'collected',
  collected:           null,
}

const QUICK_ACTION_STATUSES: JobStatus[] = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'completed',
  'awaiting_collection',
]

// ── Status update modal ───────────────────────────────────────────────────────
function StatusModal({ job, onClose }: { job: RepairJob; onClose: () => void }) {
  const qc = useQueryClient()
  const [status, setStatus] = useState<JobStatus>(job.status)
  const [note, setNote] = useState('')
  const mut = useMutation({
    mutationFn: () => updateJobStatus(job.id, status, note || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', job.id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['history', job.id] })
      onClose()
    },
  })
  const statuses: JobStatus[] = ['awaiting_quote', 'awaiting_go_ahead', 'go_ahead', 'no_go', 'parts_to_order', 'sent_to_labanda', 'quoted_by_labanda', 'awaiting_parts', 'working_on', 'completed', 'awaiting_collection', 'collected']

  return (
    <Modal title="Update Status" onClose={onClose}>
      <div className="space-y-3">
        <Select label="New Status" value={status} onChange={e => setStatus(e.target.value as JobStatus)}>
          {statuses.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </Select>
        <Input label="Note (optional)" value={note} onChange={e => setNote(e.target.value)} placeholder="Parts arrived, awaiting…" />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending}>{mut.isPending ? 'Updating…' : 'Update'}</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Work log modal ────────────────────────────────────────────────────────────
function LogWorkModal({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [minutes, setMinutes] = useState('')
  const [error, setError] = useState('')
  const mut = useMutation({
    mutationFn: () => createWorkLog({ repair_job_id: jobId, note, minutes_spent: minutes ? parseInt(minutes) : undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['worklogs', jobId] }); onClose() },
    onError: () => setError('Failed to save work log.'),
  })
  return (
    <Modal title="Log Work" onClose={onClose}>
      <div className="space-y-3">
        <Textarea
          label="Work done *"
          value={note}
          onChange={e => setNote(e.target.value)}
          rows={4}
          placeholder="Cleaned movement, replaced mainspring, re-lubricated escapement…"
          autoFocus
        />
        <Input
          label="Time spent (minutes)"
          type="number"
          min="1"
          value={minutes}
          onChange={e => setMinutes(e.target.value)}
          placeholder="45"
        />
        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!note || mut.isPending}>{mut.isPending ? 'Saving…' : 'Save Log'}</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Tab types ─────────────────────────────────────────────────────────────────
type Tab = 'details' | 'worklogs' | 'attachments' | 'history'

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('details')
  const [showStatus, setShowStatus] = useState(false)
  const [showLogWork, setShowLogWork] = useState(false)
    const [editingQuote, setEditingQuote] = useState(false)
    const [quoteInput, setQuoteInput] = useState('')
    const updateJobMutation = useMutation({
      mutationFn: (cost_cents: number) => updateJob(id!, { cost_cents }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['job', id] })
        qc.invalidateQueries({ queryKey: ['jobs'] })
        setEditingQuote(false)
      },
    })
  const quickStatusMutation = useMutation({
    mutationFn: ({ status, note }: { status: JobStatus; note?: string }) => quickStatusAction(id!, status, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['history', id] })
    },
  })
  const fileRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const { data: job, isLoading } = useQuery({ queryKey: ['job', id], queryFn: () => getJob(id!).then(r => r.data) })
  const { data: watch } = useQuery({
    queryKey: ['watch', job?.watch_id],
    queryFn: () => getWatch(job!.watch_id).then(r => r.data),
    enabled: !!job?.watch_id,
  })
  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })
  const matchingAccounts = watch?.customer_id
    ? customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(watch.customer_id))
    : customerAccounts

  const updateAccountMutation = useMutation({
    mutationFn: (customer_account_id: string | null) => updateJob(id!, { customer_account_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const { data: quotes } = useQuery({ queryKey: ['quotes', id], queryFn: () => listQuotes(id).then(r => r.data) })
  const { data: workLogs } = useQuery({ queryKey: ['worklogs', id], queryFn: () => listWorkLogs(id!).then(r => r.data), enabled: tab === 'worklogs' })
  const { data: attachments } = useQuery({ queryKey: ['attachments', id], queryFn: () => listAttachments(id!).then(r => r.data) })
  const { data: history } = useQuery({ queryKey: ['history', id], queryFn: () => getStatusHistory(id!).then(r => r.data), enabled: tab === 'history' })

  const nextStatus = job ? STATUS_FLOW[job.status] : null

  async function uploadFile(file: File, label?: string) {
    if (!file || !id) return
    setUploading(true)
    try {
      await uploadAttachment(file, id, label)
      qc.invalidateQueries({ queryKey: ['attachments', id] })
    } finally {
      setUploading(false)
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadFile(file)
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleCameraCapture(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadFile(file, 'extra_photo')
    } finally {
      if (cameraRef.current) cameraRef.current.value = ''
    }
  }

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'details', label: 'Details', icon: <FileText size={14} /> },
    { key: 'worklogs', label: 'Work Logs', icon: <Clock size={14} /> },
    { key: 'attachments', label: 'Attachments', icon: <Paperclip size={14} /> },
    { key: 'history', label: 'History', icon: <History size={14} /> },
  ]

  if (isLoading) return <Spinner />
  if (!job) return <p style={{ color: 'var(--cafe-text-muted)' }}>Job not found.</p>

  return (
    <div>
      <div className="mb-5">
        <Link
          to="/jobs"
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--cafe-text-muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
        >
          <ChevronLeft size={14} /> Back to Jobs
        </Link>
      </div>
      <PageHeader
        title={`#${job.job_number} · ${job.title}`}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => window.open(`/jobs/${job.id}/intake-print`, '_blank', 'noopener,noreferrer')}>
              <Printer size={15} /> Print Intake Tickets
            </Button>
            {nextStatus && (
              <Button variant="secondary" onClick={() => setShowStatus(true)}>
                <ArrowRight size={15} /> Move to {STATUS_LABELS[nextStatus]}
              </Button>
            )}
            <Button variant="ghost" onClick={() => setShowStatus(true)}>Change Status</Button>
          </div>
        }
      />
      {showStatus && <StatusModal job={job} onClose={() => setShowStatus(false)} />}
      {showLogWork && <LogWorkModal jobId={id!} onClose={() => setShowLogWork(false)} />}

      {/* Summary strip */}
      <div className="flex flex-wrap gap-4 mb-6 text-sm">
        <span style={{ color: 'var(--cafe-text-muted)' }}>Status: <Badge status={job.status} /></span>
        <span style={{ color: 'var(--cafe-text-muted)' }}>Priority: <span className="font-medium capitalize" style={{ color: job.priority === 'urgent' ? '#8B3A3A' : job.priority === 'high' ? '#9B4E0F' : 'var(--cafe-text)' }}>{job.priority}</span></span>
        <span style={{ color: 'var(--cafe-text-muted)' }}>Quote: <span className="font-medium" style={{ color: 'var(--cafe-text)' }}>${((job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents) / 100).toFixed(2)}</span></span>
        <span style={{ color: 'var(--cafe-text-muted)' }}>Created: <span style={{ color: 'var(--cafe-text)' }}>{formatDate(job.created_at)}</span></span>
      </div>

      <Card className="p-4 mb-5">
        <div className="flex flex-wrap gap-2">
          {QUICK_ACTION_STATUSES.map((status) => (
            <Button
              key={status}
              variant="secondary"
              onClick={() => quickStatusMutation.mutate({ status, note: `Quick action: ${STATUS_LABELS[status]}` })}
              disabled={quickStatusMutation.isPending}
            >
              {STATUS_LABELS[status]}
            </Button>
          ))}
        </div>
      </Card>

      {/* Tabs */}
      <div className="flex gap-0.5 mb-6" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-all duration-150"
            style={{
              borderBottomColor: tab === t.key ? 'var(--cafe-gold)' : 'transparent',
              color: tab === t.key ? 'var(--cafe-amber)' : 'var(--cafe-text-muted)',
            }}
            onMouseEnter={e => { if (tab !== t.key) e.currentTarget.style.color = 'var(--cafe-text-mid)' }}
            onMouseLeave={e => { if (tab !== t.key) e.currentTarget.style.color = 'var(--cafe-text-muted)' }}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Details ─────────────────────────────────────────── */}
      {tab === 'details' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Card className="p-5 space-y-3">
            <h2 className="font-semibold text-xs uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Job Info</h2>
            <div className="space-y-2.5 text-sm">
              <div className="flex justify-between"><span style={{ color: 'var(--cafe-text-muted)' }}>Job #</span><span className="font-mono" style={{ color: 'var(--cafe-text)' }}>#{job.job_number}</span></div>
              <div className="flex justify-between items-center"><span style={{ color: 'var(--cafe-text-muted)' }}>Status</span><Badge status={job.status} /></div>
              <div className="flex justify-between"><span style={{ color: 'var(--cafe-text-muted)' }}>Priority</span><span className="capitalize font-medium" style={{ color: 'var(--cafe-text)' }}>{job.priority}</span></div>
              <div className="flex justify-between"><span style={{ color: 'var(--cafe-text-muted)' }}>Date In</span><span style={{ color: 'var(--cafe-text)' }}>{formatDate(job.created_at)}</span></div>
              {job.collection_date && <div className="flex justify-between"><span style={{ color: 'var(--cafe-text-muted)' }}>Collection</span><span style={{ color: 'var(--cafe-text)' }}>{job.collection_date}</span></div>}
              {job.salesperson && <div className="flex justify-between"><span style={{ color: 'var(--cafe-text-muted)' }}>Salesperson</span><span style={{ color: 'var(--cafe-text)' }}>{job.salesperson}</span></div>}
              {job.deposit_cents > 0 && <div className="flex justify-between"><span style={{ color: 'var(--cafe-text-muted)' }}>Deposit</span><span className="font-medium" style={{ color: '#3B6B42' }}>${(job.deposit_cents / 100).toFixed(2)}</span></div>}
              <div className="space-y-1">
                <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>Customer Account</span>
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
              <div className="flex justify-between items-center">
                <span style={{ color: 'var(--cafe-text-muted)' }}>Quote{job.cost_cents === 0 && job.pre_quote_cents > 0 ? ' (est.)' : ''}</span>
                {editingQuote ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>$</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={quoteInput}
                      onChange={e => setQuoteInput(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') updateJobMutation.mutate(Math.round(parseFloat(quoteInput || '0') * 100))
                        if (e.key === 'Escape') setEditingQuote(false)
                      }}
                      autoFocus
                      className="w-24 text-right text-sm rounded px-1.5 py-0.5"
                      style={{ border: '1px solid var(--cafe-border)', background: 'var(--cafe-bg)', color: 'var(--cafe-text)' }}
                    />
                    <button
                      onClick={() => updateJobMutation.mutate(Math.round(parseFloat(quoteInput || '0') * 100))}
                      disabled={updateJobMutation.isPending}
                      className="text-xs px-2 py-0.5 rounded font-medium"
                      style={{ backgroundColor: '#EEE6DA', color: 'var(--cafe-text)' }}
                    >
                      Save
                    </button>
                    <button onClick={() => setEditingQuote(false)} className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>✕</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="font-medium" style={{ color: 'var(--cafe-text-mid)' }}>
                      ${((job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents) / 100).toFixed(2)}
                    </span>
                    <button
                      onClick={() => {
                        setQuoteInput(((job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents) / 100).toFixed(2))
                        setEditingQuote(true)
                      }}
                      className="opacity-50 hover:opacity-100 transition-opacity"
                      title="Edit quote"
                    >
                      <Pencil size={12} style={{ color: 'var(--cafe-text-muted)' }} />
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Intake Photos */}
            {(() => {
              const frontPhoto = (attachments ?? []).find(a => a.label === 'watch_front')
              const backPhoto = (attachments ?? []).find(a => a.label === 'watch_back')
              if (!frontPhoto && !backPhoto) return null
              return (
                <div className="pt-3" style={{ borderTop: '1px solid var(--cafe-border)' }}>
                  <h2 className="font-semibold text-xs uppercase tracking-widest mb-2 flex items-center gap-1.5" style={{ color: 'var(--cafe-text-muted)' }}><Camera size={13} />Intake Photos</h2>
                  <div className="grid grid-cols-2 gap-2">
                    {frontPhoto && (
                      <a href={getAttachmentDownloadUrl(frontPhoto.storage_key)} target="_blank" rel="noopener noreferrer" className="group">
                        <img src={getAttachmentDownloadUrl(frontPhoto.storage_key)} alt="Watch front" className="w-full aspect-square object-cover rounded-lg transition-shadow" style={{ border: '1px solid var(--cafe-border)' }} />
                        <p className="text-[10px] text-center mt-1" style={{ color: 'var(--cafe-text-muted)' }}>Front</p>
                      </a>
                    )}
                    {backPhoto && (
                      <a href={getAttachmentDownloadUrl(backPhoto.storage_key)} target="_blank" rel="noopener noreferrer" className="group">
                        <img src={getAttachmentDownloadUrl(backPhoto.storage_key)} alt="Watch back" className="w-full aspect-square object-cover rounded-lg transition-shadow" style={{ border: '1px solid var(--cafe-border)' }} />
                        <p className="text-[10px] text-center mt-1" style={{ color: 'var(--cafe-text-muted)' }}>Back</p>
                      </a>
                    )}
                  </div>
                </div>
              )
            })()}
          </Card>

          <div className="lg:col-span-2 flex flex-col gap-5">
            {job.description && (
              <Card className="p-5">
                <h2 className="font-semibold text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--cafe-text-muted)' }}>Description / Fault Report</h2>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--cafe-text-mid)' }}>{job.description}</p>
              </Card>
            )}

            <Card>
              <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                <h2 className="font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>Quotes</h2>
                <Link to="/quotes" className="text-xs font-medium tracking-wide uppercase transition-colors" style={{ color: 'var(--cafe-amber)' }}>Manage quotes →</Link>
              </div>
              <div>
                {(quotes ?? []).map((q, i) => (
                  <div key={q.id} className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: i < (quotes ?? []).length - 1 ? '1px solid var(--cafe-border)' : 'none' }}>
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Quote</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(q.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>${((q.total_cents ?? 0) / 100).toFixed(2)}</span>
                      <Badge status={q.status} />
                    </div>
                  </div>
                ))}
                {(quotes ?? []).length === 0 && (
                  <p className="px-5 py-5 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>No quotes yet.</p>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* ── Tab: Work Logs ──────────────────────────────────────── */}
      {tab === 'worklogs' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>{(workLogs ?? []).length} log{(workLogs ?? []).length !== 1 ? 's' : ''}</p>
            <Button onClick={() => setShowLogWork(true)}><Plus size={15} />Log Work</Button>
          </div>
          {!workLogs ? <Spinner /> : workLogs.length === 0 ? <EmptyState message="No work logged yet. Tap 'Log Work' to record what was done." /> : (
            <div className="space-y-3">
              {workLogs.map(log => (
                <Card key={log.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap flex-1" style={{ color: 'var(--cafe-text-mid)' }}>{log.note}</p>
                    {log.minutes_spent && (
                      <span className="text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap" style={{ backgroundColor: '#EEE6DA', color: 'var(--cafe-text-mid)' }}>
                        <Clock size={11} className="inline mr-0.5" />{log.minutes_spent} min
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-2" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(log.created_at)}</p>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Attachments ──────────────────────────────────── */}
      {tab === 'attachments' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>{(attachments ?? []).length} file{(attachments ?? []).length !== 1 ? 's' : ''}</p>
            <div className="flex items-center gap-2">
              <input ref={fileRef} type="file" className="hidden" onChange={handleFileUpload} />
              <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleCameraCapture} />
              <Button variant="secondary" onClick={() => cameraRef.current?.click()} disabled={uploading}>
                <Camera size={15} />{uploading ? 'Uploading…' : 'Take Extra Photo'}
              </Button>
              <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
                <Upload size={15} />{uploading ? 'Uploading…' : 'Upload File'}
              </Button>
            </div>
          </div>
          {!attachments ? <Spinner /> : attachments.length === 0 ? <EmptyState message="No attachments yet. Upload photos or documents." /> : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {attachments.map(att => (
                <Card key={att.id} className="p-4 flex items-start gap-3">
                  <Paperclip size={17} className="mt-0.5 shrink-0" style={{ color: 'var(--cafe-text-muted)' }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--cafe-text)' }}>{att.file_name}</p>
                    <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{att.content_type} · {att.file_size_bytes ? `${(att.file_size_bytes / 1024).toFixed(1)} KB` : ''}</p>
                  </div>
                  <a
                    href={getAttachmentDownloadUrl(att.storage_key)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 transition-colors"
                    style={{ color: 'var(--cafe-amber)' }}
                    title="Download"
                  >
                    <Download size={15} />
                  </a>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: History ───────────────────────────────────────── */}
      {tab === 'history' && (
        <div>
          {!history ? <Spinner /> : history.length === 0 ? <EmptyState message="No status history yet." /> : (
            <div className="relative pl-6 space-y-4">
              <div className="absolute left-2 top-0 bottom-0 w-0.5" style={{ backgroundColor: 'var(--cafe-border-2)' }} />
              {history.map((h, i) => (
                <div key={h.id} className="relative">
                  <div
                    className="absolute -left-4 top-1 w-3 h-3 rounded-full border-2"
                    style={{
                      borderColor: 'var(--cafe-surface)',
                      backgroundColor: i === 0 ? 'var(--cafe-gold)' : 'var(--cafe-border-2)',
                    }}
                  />
                  <Card className="p-4">
                    <div className="flex items-center justify-between">
                      <Badge status={h.new_status} />
                      <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(h.created_at)}</span>
                    </div>
                    {h.old_status && <p className="text-xs mt-1" style={{ color: 'var(--cafe-text-muted)' }}>from: {h.old_status.replace(/_/g, ' ')}</p>}
                    {h.change_note && <p className="text-sm mt-1.5" style={{ color: 'var(--cafe-text-mid)' }}>{h.change_note}</p>}
                  </Card>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
