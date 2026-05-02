import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Upload, CheckCircle, AlertCircle, FileSpreadsheet } from 'lucide-react'
import axios from 'axios'
import {
  listCustomerOrders,
  createCustomerOrder,
  updateCustomerOrder,
  deleteCustomerOrder,
  importCustomerOrders,
  listCustomers,
  getApiErrorMessage,
  type CustomerOrder,
  type CustomerOrderImportResult,
  type CustomerOrderStatus,
} from '@/lib/api'
import { PageHeader, Button, Spinner, Modal } from '@/components/ui'
import { KanbanBoard, CUSTOMER_ORDER_KANBAN_COLUMNS } from '@/components/kanban'
import { formatCents } from '@/lib/utils'

function PriorityPill({ priority }: { priority: string }) {
  const p = priority.toLowerCase()
  if (p !== 'urgent' && p !== 'high') return null
  return (
    <span
      style={{
        backgroundColor: p === 'urgent' ? '#FEEEED' : '#FFF0E0',
        color: p === 'urgent' ? 'var(--ms-error)' : '#8A5010',
        fontSize: 9,
        fontWeight: 700,
        padding: '2px 6px',
        borderRadius: 4,
        letterSpacing: '0.06em',
        textTransform: 'uppercase' as const,
      }}
    >
      {p === 'urgent' ? 'Urgent' : 'High'}
    </span>
  )
}

function OrderCard({
  order,
  accentColor,
  onClick,
}: {
  order: CustomerOrder
  accentColor: string
  onClick: () => void
}) {
  const [dragging, setDragging] = useState(false)
  return (
    <div
      draggable
      onDragStart={e => {
        e.dataTransfer.setData('jobId', order.id)
        setDragging(true)
      }}
      onDragEnd={() => setDragging(false)}
      onClick={onClick}
      style={{
        backgroundColor: 'var(--ms-surface)',
        border: '1px solid var(--ms-border)',
        borderRadius: 10,
        padding: '10px 12px',
        cursor: 'pointer',
        opacity: dragging ? 0.4 : 1,
        userSelect: 'none',
      }}
    >
      <div style={{ borderLeft: `3px solid ${accentColor}`, paddingLeft: 8 }}>
        <div className="flex items-start justify-between gap-2 mb-1">
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--ms-text)', lineHeight: 1.3 }}>
            {order.title}
          </span>
          <PriorityPill priority={order.priority} />
        </div>

        {order.customer_name && (
          <p style={{ fontSize: 11, color: 'var(--ms-text-muted)', marginBottom: 2 }}>
            {order.customer_name}
          </p>
        )}
        {order.supplier && (
          <p style={{ fontSize: 11, color: 'var(--ms-text-muted)' }}>
            via {order.supplier}
          </p>
        )}
        {order.estimated_cost_cents > 0 && (
          <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--ms-text)', marginTop: 4 }}>
            {formatCents(order.estimated_cost_cents)}
          </p>
        )}
      </div>
    </div>
  )
}

const PRIORITY_OPTIONS = ['normal', 'high', 'urgent'] as const

function OrderModal({
  order,
  onClose,
}: {
  order: CustomerOrder | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const isEdit = !!order

  const [title, setTitle] = useState(order?.title ?? '')
  const [supplier, setSupplier] = useState(order?.supplier ?? '')
  const [customerId, setCustomerId] = useState(order?.customer_id ?? '')
  const [priority, setPriority] = useState(order?.priority ?? 'normal')
  const [estimatedCents, setEstimatedCents] = useState(
    order ? String(order.estimated_cost_cents / 100) : ''
  )
  const [notes, setNotes] = useState(order?.notes ?? '')
  const [status, setStatus] = useState<CustomerOrderStatus>(order?.status ?? 'to_order')
  const [error, setError] = useState('')

  const { data: customers = [] } = useQuery({
    queryKey: ['customers', 'order-modal'],
    queryFn: () => listCustomers({ limit: 200 }).then(r => r.data),
  })

  const saveMutation = useMutation({
    mutationFn: () => {
      const cents = Math.round(parseFloat(estimatedCents || '0') * 100) || 0
      const payload = {
        title: title.trim(),
        supplier: supplier.trim() || undefined,
        customer_id: customerId || undefined,
        priority,
        estimated_cost_cents: cents,
        notes: notes.trim() || undefined,
      }
      if (isEdit && order) {
        return updateCustomerOrder(order.id, { ...payload, status })
      }
      return createCustomerOrder(payload)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customer-orders'] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteCustomerOrder(order!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customer-orders'] })
      onClose()
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  })

  const STATUS_LABELS: Record<CustomerOrderStatus, string> = {
    to_order: 'To Order',
    ordered: 'Ordered',
    arrived: 'Arrived',
    notified: 'Customer Notified',
    collected: 'Collected',
  }

  return (
    <Modal title={isEdit ? 'Edit Order' : 'New Customer Order'} onClose={onClose}>
      <div style={{ padding: '20px 22px' }}>
        <div className="space-y-4">
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
              Item *
            </label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Leather watch band 22mm brown"
              style={{
                width: '100%',
                borderRadius: 8,
                border: '1px solid var(--ms-border)',
                padding: '8px 10px',
                fontSize: 13,
                color: 'var(--ms-text)',
                backgroundColor: 'var(--ms-input)',
                outline: 'none',
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
              Customer
            </label>
            <select
              value={customerId}
              onChange={e => setCustomerId(e.target.value)}
              style={{
                width: '100%',
                borderRadius: 8,
                border: '1px solid var(--ms-border)',
                padding: '8px 10px',
                fontSize: 13,
                color: 'var(--ms-text)',
                backgroundColor: 'var(--ms-input)',
                outline: 'none',
              }}
            >
              <option value="">— No customer linked —</option>
              {customers.map(c => (
                <option key={c.id} value={c.id}>{c.full_name}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
                Supplier
              </label>
              <input
                value={supplier}
                onChange={e => setSupplier(e.target.value)}
                placeholder="e.g. Watch Depot"
                style={{
                  width: '100%',
                  borderRadius: 8,
                  border: '1px solid var(--ms-border)',
                  padding: '8px 10px',
                  fontSize: 13,
                  color: 'var(--ms-text)',
                  backgroundColor: 'var(--ms-input)',
                  outline: 'none',
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
                Est. Cost ($)
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={estimatedCents}
                onChange={e => setEstimatedCents(e.target.value)}
                placeholder="0.00"
                style={{
                  width: '100%',
                  borderRadius: 8,
                  border: '1px solid var(--ms-border)',
                  padding: '8px 10px',
                  fontSize: 13,
                  color: 'var(--ms-text)',
                  backgroundColor: 'var(--ms-input)',
                  outline: 'none',
                }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
                Priority
              </label>
              <select
                value={priority}
                onChange={e => setPriority(e.target.value)}
                style={{
                  width: '100%',
                  borderRadius: 8,
                  border: '1px solid var(--ms-border)',
                  padding: '8px 10px',
                  fontSize: 13,
                  color: 'var(--ms-text)',
                  backgroundColor: 'var(--ms-input)',
                  outline: 'none',
                }}
              >
                {PRIORITY_OPTIONS.map(p => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            {isEdit && (
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
                  Status
                </label>
                <select
                  value={status}
                  onChange={e => setStatus(e.target.value as CustomerOrderStatus)}
                  style={{
                    width: '100%',
                    borderRadius: 8,
                    border: '1px solid var(--ms-border)',
                    padding: '8px 10px',
                    fontSize: 13,
                    color: 'var(--ms-text)',
                    backgroundColor: 'var(--ms-input)',
                    outline: 'none',
                  }}
                >
                  {(Object.keys(STATUS_LABELS) as CustomerOrderStatus[]).map(s => (
                    <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
              Description / Notes
            </label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              placeholder="Any extra details for this order…"
              style={{
                width: '100%',
                borderRadius: 8,
                border: '1px solid var(--ms-border)',
                padding: '8px 10px',
                fontSize: 13,
                color: 'var(--ms-text)',
                backgroundColor: 'var(--ms-input)',
                outline: 'none',
                resize: 'vertical',
              }}
            />
          </div>

          {error && (
            <p style={{ color: 'var(--ms-error)', fontSize: 12 }}>{error}</p>
          )}

          <div className="flex items-center justify-between pt-1">
            {isEdit ? (
              <button
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                style={{ color: 'var(--ms-error)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}
              >
                <Trash2 size={14} />
                Delete
              </button>
            ) : <span />}
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button
                onClick={() => saveMutation.mutate()}
                disabled={!title.trim() || saveMutation.isPending}
              >
                {saveMutation.isPending ? 'Saving…' : isEdit ? 'Save' : 'Create Order'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}

function Code({ children }: { children: string }) {
  return (
    <code
      className="text-xs px-1 py-0.5 rounded"
      style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-mid)' }}
    >
      {children}
    </code>
  )
}

function ImportModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [sheetName, setSheetName] = useState('')
  const [dryRun, setDryRun] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<CustomerOrderImportResult | null>(null)
  const [error, setError] = useState('')

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setResult(null)
    setError('')
  }

  async function runImport(opts: { dryRun: boolean }) {
    if (!file) return
    setUploading(true)
    setError('')
    setResult(null)
    try {
      const { data } = await importCustomerOrders(file, opts.dryRun, sheetName || undefined)
      setResult(data)
      if (!opts.dryRun) {
        setFile(null)
        if (fileRef.current) fileRef.current.value = ''
        void qc.invalidateQueries({ queryKey: ['customer-orders'] })
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 429) {
        setError('Too many import attempts — try again in a minute.')
      } else {
        setError(getApiErrorMessage(err, 'Import failed. Check column names and try again.'))
      }
    }
    setUploading(false)
  }

  return (
    <Modal title="Import Customer Orders" onClose={onClose}>
      <div style={{ padding: '20px 22px', maxWidth: 480 }} className="space-y-5">
        <p style={{ fontSize: 13, color: 'var(--ms-text-muted)' }}>
          Upload a CSV or Excel file. Each row becomes one customer order.
          Expected columns:{' '}
          <Code>title</Code> (required),{' '}
          <Code>customer</Code>,{' '}
          <Code>phone</Code>,{' '}
          <Code>supplier</Code>,{' '}
          <Code>cost</Code>,{' '}
          <Code>status</Code>,{' '}
          <Code>priority</Code>,{' '}
          <Code>notes</Code>.
        </p>

        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,.xls,.xlsm"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="w-full border-2 border-dashed rounded-lg p-6 text-center transition-colors"
          style={{ borderColor: 'var(--ms-border-strong)' }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--ms-accent)'; e.currentTarget.style.backgroundColor = '#FEF0DC' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--ms-border-strong)'; e.currentTarget.style.backgroundColor = 'transparent' }}
        >
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileSpreadsheet size={28} style={{ color: 'var(--ms-accent)' }} />
              <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--ms-text)' }}>{file.name}</p>
              <p style={{ fontSize: 11, color: 'var(--ms-text-muted)' }}>{(file.size / 1024).toFixed(1)} KB · Click to change</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2" style={{ color: 'var(--ms-text-muted)' }}>
              <Upload size={28} />
              <p style={{ fontSize: 13, fontWeight: 500 }}>Click to select a CSV or Excel file</p>
            </div>
          )}
        </button>

        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ms-text-muted)', display: 'block', marginBottom: 4 }}>
            Excel sheet / tab name <span style={{ fontWeight: 400 }}>(optional)</span>
          </label>
          <input
            value={sheetName}
            onChange={e => setSheetName(e.target.value)}
            placeholder="e.g. Orders — leave blank to use the first sheet"
            style={{
              width: '100%',
              borderRadius: 8,
              border: '1px solid var(--ms-border)',
              padding: '8px 10px',
              fontSize: 13,
              color: 'var(--ms-text)',
              backgroundColor: 'var(--ms-input)',
              outline: 'none',
            }}
          />
        </div>

        <label className="flex items-start gap-2 text-sm cursor-pointer" style={{ color: 'var(--ms-text-mid)' }}>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={e => setDryRun(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Dry run (preview only — recommended)
            <span className="block text-xs" style={{ color: 'var(--ms-text-muted)' }}>
              Validates the file and shows a row count without writing anything. Uncheck to apply.
            </span>
          </span>
        </label>

        {error && (
          <div className="flex items-start gap-2 rounded-lg p-3" style={{ backgroundColor: '#FEF0EE', border: '1px solid #F5C6C0' }}>
            <AlertCircle size={16} style={{ color: 'var(--ms-error)', flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 13, color: 'var(--ms-error)' }}>{error}</p>
          </div>
        )}

        {result && (
          <div className="rounded-lg p-4 space-y-1" style={{ backgroundColor: '#EBF8EF', border: '1px solid #A8DABD' }}>
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle size={16} style={{ color: '#1A6A3A' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#1A4A2A' }}>
                {result.dry_run ? 'Dry run complete' : 'Import complete'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1" style={{ fontSize: 12, color: '#1A4A2A' }}>
              <span>Total rows</span><span style={{ fontWeight: 600 }}>{result.total_rows}</span>
              <span>Will import / Imported</span><span style={{ fontWeight: 600 }}>{result.imported}</span>
              <span>Skipped</span><span style={{ fontWeight: 600 }}>{result.skipped}</span>
            </div>
            {Object.keys(result.skipped_reasons).length > 0 && (
              <div style={{ fontSize: 12, color: '#1A4A2A', marginTop: 6 }}>
                <p style={{ fontWeight: 600 }}>Skip reasons:</p>
                {Object.entries(result.skipped_reasons).map(([reason, count]) => (
                  <p key={reason}>{reason}: {count}</p>
                ))}
              </div>
            )}
            {result.dry_run && file && (
              <div className="mt-3 rounded-lg px-3 py-3" style={{ backgroundColor: '#FEF9E8', border: '1px solid #E8D4A0' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: '#5A4A2A' }}>Ready to apply?</p>
                <Button
                  className="mt-2"
                  disabled={uploading}
                  onClick={() => { void runImport({ dryRun: false }); setDryRun(false) }}
                >
                  Run import (apply changes)
                </Button>
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => void runImport({ dryRun })} disabled={!file || uploading}>
            <Upload size={14} />
            {uploading ? 'Working…' : dryRun ? 'Preview import' : 'Run import'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function CustomerOrdersPage() {
  const qc = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [editOrder, setEditOrder] = useState<CustomerOrder | null>(null)

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ['customer-orders'],
    queryFn: () => listCustomerOrders().then(r => r.data),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: CustomerOrderStatus }) =>
      updateCustomerOrder(id, { status }),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ['customer-orders'] })
      const prev = qc.getQueryData<CustomerOrder[]>(['customer-orders'])
      qc.setQueryData<CustomerOrder[]>(['customer-orders'], old =>
        old?.map(o => (o.id === id ? { ...o, status } : o)) ?? []
      )
      return { prev }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(['customer-orders'], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['customer-orders'] }),
  })

  return (
    <div className="flex flex-col h-full min-h-0">
      <PageHeader
        title="Customer Orders"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={15} className="mr-1" />
              Import
            </Button>
            <Button onClick={() => setShowNew(true)}>
              <Plus size={15} className="mr-1" />
              New Order
            </Button>
          </div>
        }
      />

      <div className="flex-1 min-h-0 overflow-auto px-6 pb-6">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        ) : (
          <KanbanBoard
            jobs={orders}
            columns={CUSTOMER_ORDER_KANBAN_COLUMNS}
            emptyMessage="Nothing here"
            onStatusChange={(id, nextStatus) =>
              statusMutation.mutate({ id, status: nextStatus as CustomerOrderStatus })
            }
            renderCard={(order, column) => (
              <OrderCard
                order={order}
                accentColor={column.color}
                onClick={() => setEditOrder(order)}
              />
            )}
          />
        )}
      </div>

      {showNew && <OrderModal order={null} onClose={() => setShowNew(false)} />}
      {editOrder && <OrderModal order={editOrder} onClose={() => setEditOrder(null)} />}
      {showImport && <ImportModal onClose={() => setShowImport(false)} />}
    </div>
  )
}
