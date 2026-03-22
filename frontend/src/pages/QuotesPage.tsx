import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Trash2, MessageSquare, Copy, CheckCheck } from 'lucide-react'
import { listQuotes, createQuote, sendQuote, listJobs, type QuoteLineItemInput } from '@/lib/api'
import { Card, PageHeader, Button, Input, Modal, Spinner, EmptyState, Badge, Select } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'

function AddLineItemRow({ item, index, onChange, onRemove }: {
  item: QuoteLineItemInput; index: number
  onChange: (i: number, key: keyof QuoteLineItemInput, value: string | number) => void
  onRemove: (i: number) => void
}) {
  return (
    <div className="grid grid-cols-12 gap-2 items-end">
      <div className="col-span-3">
        {index === 0 && <label className="text-xs font-medium block mb-1" style={{ color: 'var(--cafe-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Type</label>}
        <select
          className="w-full rounded px-2 py-1.5 text-sm"
          style={{ border: '1px solid var(--cafe-border-2)', backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)' }}
          value={item.item_type}
          onChange={e => onChange(index, 'item_type', e.target.value)}
        >
          <option value="labor">Labor</option>
          <option value="part">Part</option>
          <option value="fee">Fee</option>
        </select>
      </div>
      <div className="col-span-4">
        {index === 0 && <label className="text-xs font-medium block mb-1" style={{ color: 'var(--cafe-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Description</label>}
        <input
          className="w-full rounded px-2 py-1.5 text-sm"
          style={{ border: '1px solid var(--cafe-border-2)', backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)' }}
          value={item.description}
          onChange={e => onChange(index, 'description', e.target.value)}
          placeholder="Movement service…"
        />
      </div>
      <div className="col-span-2">
        {index === 0 && <label className="text-xs font-medium block mb-1" style={{ color: 'var(--cafe-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Qty</label>}
        <input
          type="number" min="0.01" step="0.01"
          className="w-full rounded px-2 py-1.5 text-sm"
          style={{ border: '1px solid var(--cafe-border-2)', backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)' }}
          value={item.quantity}
          onChange={e => onChange(index, 'quantity', parseFloat(e.target.value))}
        />
      </div>
      <div className="col-span-2">
        {index === 0 && <label className="text-xs font-medium block mb-1" style={{ color: 'var(--cafe-text-muted)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Unit Price</label>}
        <input
          type="number" min="0" step="1"
          className="w-full rounded px-2 py-1.5 text-sm"
          style={{ border: '1px solid var(--cafe-border-2)', backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)' }}
          value={item.unit_price_cents}
          placeholder="5000"
          onChange={e => onChange(index, 'unit_price_cents', parseInt(e.target.value))}
        />
      </div>
      <div className="col-span-1 flex justify-end">
        {index === 0 && <div className="mb-1 h-4" />}
        <button onClick={() => onRemove(index)} className="p-1.5 transition-colors" style={{ color: '#C96A5A' }} onMouseEnter={e => (e.currentTarget.style.color = '#9B3D2A')} onMouseLeave={e => (e.currentTarget.style.color = '#C96A5A')}>
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

function CreateQuoteModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: jobs } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })
  const [jobId, setJobId] = useState('')
  const [taxCents, setTaxCents] = useState(0)
  const [items, setItems] = useState<QuoteLineItemInput[]>([{ item_type: 'labor', description: '', quantity: 1, unit_price_cents: 0 }])
  const [error, setError] = useState('')

  const updateItem = (i: number, key: keyof QuoteLineItemInput, value: string | number) =>
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, [key]: value } : it))
  const removeItem = (i: number) => setItems(prev => prev.filter((_, idx) => idx !== i))
  const addItem = () => setItems(prev => [...prev, { item_type: 'labor', description: '', quantity: 1, unit_price_cents: 0 }])

  const subtotal = items.reduce((s, it) => s + it.quantity * it.unit_price_cents, 0)
  const total = subtotal + taxCents

  const mut = useMutation({
    mutationFn: () => createQuote({ repair_job_id: jobId, tax_cents: taxCents, line_items: items }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['quotes'] }); onClose() },
    onError: () => setError('Failed to create quote.'),
  })

  const activeJobs = (jobs ?? []).filter(j => !['collected', 'no_go'].includes(j.status))

  return (
    <Modal title="Create Quote" onClose={onClose}>
      <div className="space-y-4">
        <Select label="Repair Job *" value={jobId} onChange={e => setJobId(e.target.value)}>
          <option value="">Select a job…</option>
          {activeJobs.map(j => <option key={j.id} value={j.id}>#{j.job_number} — {j.title}</option>)}
        </Select>

        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Line Items</label>
          {items.map((item, i) => (
            <AddLineItemRow key={i} item={item} index={i} onChange={updateItem} onRemove={removeItem} />
          ))}
          <button onClick={addItem} className="text-sm flex items-center gap-1 font-medium transition-colors" style={{ color: 'var(--cafe-amber)' }} onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-gold-dark)')} onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}><Plus size={14} />Add line</button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input label="Tax (cents)" type="number" min="0" value={taxCents} onChange={e => setTaxCents(parseInt(e.target.value) || 0)} />
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>Total</label>
            <div className="rounded-lg px-3 py-2 text-sm font-semibold" style={{ border: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)' }}>{formatCents(total)}</div>
          </div>
        </div>

        {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!jobId || items.some(i => !i.description) || mut.isPending}>
            {mut.isPending ? 'Creating…' : 'Create Quote'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function QuotesPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const { data: quotes, isLoading } = useQuery({ queryKey: ['quotes'], queryFn: () => listQuotes().then(r => r.data) })

  const sendMut = useMutation({
    mutationFn: (id: string) => sendQuote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes'] }),
  })

  function copyApprovalLink(token: string, id: string) {
    const url = `${window.location.origin}/approve/${token}`
    navigator.clipboard.writeText(url)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div>
      <PageHeader title="Quotes" action={<Button onClick={() => setShowCreate(true)}><Plus size={16} />New Quote</Button>} />
      {showCreate && <CreateQuoteModal onClose={() => setShowCreate(false)} />}

      {isLoading ? <Spinner /> : (
        <Card>
          {(quotes ?? []).length === 0 ? <EmptyState message="No quotes yet." /> : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-widest" style={{ borderBottom: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}>
                  <th className="px-5 py-3 font-medium">Source</th>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Total</th>
                  <th className="px-5 py-3 font-medium">Sent</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(quotes ?? []).map(q => (
                  <tr key={q.id} style={{ borderBottom: '1px solid var(--cafe-border)' }} onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')} onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}>
                    <td className="px-5 py-3">
                      <span className="text-xs font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: '#E8E6F0', color: '#4A4566' }}>Watch</span>
                    </td>
                    <td className="px-5 py-3">
                      <Link to={`/jobs/${q.repair_job_id}`} className="text-xs font-mono transition-colors" style={{ color: 'var(--cafe-amber)' }} onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-gold-dark)')} onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}>View Job</Link>
                    </td>
                    <td className="px-5 py-3"><Badge status={q.status} /></td>
                    <td className="px-5 py-3 font-semibold">{formatCents(q.total_cents)}</td>
                    <td className="px-5 py-3">
                      {q.sent_at ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <MessageSquare size={12} /> {formatDate(q.sent_at)}
                        </span>
                      ) : (
                        <span className="text-xs" style={{ color: 'var(--cafe-border-2)' }}>—</span>
                      )}
                    </td>
                    <td className="px-5 py-3" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(q.created_at)}</td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        {q.status === 'draft' && (
                          <Button
                            variant="secondary"
                            onClick={() => sendMut.mutate(q.id)}
                            disabled={sendMut.isPending}
                            className="text-xs py-1 px-2"
                          >
                            <MessageSquare size={12} /> Send SMS
                          </Button>
                        )}
                        {q.status === 'sent' && (
                          <span className="text-xs italic" style={{ color: 'var(--cafe-text-muted)' }}>Awaiting response</span>
                        )}
                        {(q.status === 'sent' || q.status === 'draft') && (
                          <button
                            title="Copy approval link"
                            onClick={() => copyApprovalLink(q.approval_token, q.id)}
                            className="p-1 transition-colors"
                            style={{ color: 'var(--cafe-text-muted)' }}
                            onMouseEnter={e => (e.currentTarget.style.color = 'var(--cafe-amber)')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'var(--cafe-text-muted)')}
                          >
                            {copiedId === q.id ? <CheckCheck size={14} className="text-green-500" /> : <Copy size={14} />}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
