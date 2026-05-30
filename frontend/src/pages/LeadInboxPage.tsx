import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listInboundLeads,
  createInboundLead,
  updateInboundLead,
  convertInboundLeadToAccount,
  getApiErrorMessage,
  type InboundLead,
  type InboundLeadStatus,
} from '@/lib/api'
import { Button, Input, PageHeader, Select, Spinner } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'

// Active pipeline statuses shown as columns. `won`/`lost` are terminal and hidden.
const PIPELINE: { key: InboundLeadStatus; label: string; color: string }[] = [
  { key: 'new', label: 'New', color: 'var(--ms-accent)' },
  { key: 'quote_needed', label: 'Quote needed', color: '#B87030' },
  { key: 'contacted', label: 'Contacted', color: '#4F7A4A' },
  { key: 'follow_up_due', label: 'Follow-up due', color: '#C96A5A' },
]

const STATUS_OPTIONS: { value: InboundLeadStatus; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'quote_needed', label: 'Quote needed' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow_up_due', label: 'Follow-up due' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

function isOverdue(dateStr?: string | null): boolean {
  if (!dateStr) return false
  const d = new Date(`${dateStr}T23:59:59`)
  return Number.isFinite(d.getTime()) && d.getTime() < Date.now()
}

function AddLeadForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [suburb, setSuburb] = useState('')
  const [notes, setNotes] = useState('')
  const [status, setStatus] = useState<InboundLeadStatus>('new')
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () =>
      createInboundLead({
        name: name.trim(),
        phone: phone.trim() || undefined,
        suburb_name: suburb.trim() || undefined,
        notes: notes.trim() || undefined,
        status,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inbound-leads'] })
      onDone()
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Could not save the lead.')),
  })

  return (
    <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-surface)' }}>
      <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>New inbound lead</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Name / business" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Jane (Toyota Hilux)" />
        <Input label="Phone" value={phone} onChange={e => setPhone(e.target.value)} placeholder="04xx xxx xxx" />
        <Input label="Suburb" value={suburb} onChange={e => setSuburb(e.target.value)} placeholder="Geelong" />
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: 'var(--ms-text-muted)' }}>Status</label>
          <Select value={status} onChange={e => setStatus(e.target.value as InboundLeadStatus)}>
            {STATUS_OPTIONS.filter(o => o.value !== 'won' && o.value !== 'lost').map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
        </div>
      </div>
      <Input label="Notes" value={notes} onChange={e => setNotes(e.target.value)} placeholder="What do they need?" />
      {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
      <div className="flex gap-2">
        <Button onClick={() => mut.mutate()} disabled={mut.isPending || !name.trim()}>
          {mut.isPending ? 'Saving…' : 'Add lead'}
        </Button>
        <Button variant="secondary" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  )
}

function LeadCard({ lead }: { lead: InboundLead }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [error, setError] = useState('')

  const update = useMutation({
    mutationFn: (data: Parameters<typeof updateInboundLead>[1]) => updateInboundLead(lead.id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inbound-leads'] }),
    onError: (err) => setError(getApiErrorMessage(err, 'Could not update the lead.')),
  })
  const convert = useMutation({
    mutationFn: () => convertInboundLeadToAccount(lead.id, { account_name: lead.name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inbound-leads'] })
      navigate('/customer-accounts')
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Could not convert the lead.')),
  })

  const overdue = lead.status === 'follow_up_due' && isOverdue(lead.next_follow_up_on)

  return (
    <div
      className="rounded-lg border p-3 space-y-2"
      style={{ borderColor: overdue ? '#C96A5A' : 'var(--ms-border)', backgroundColor: 'var(--ms-surface)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-sm leading-snug" style={{ color: 'var(--ms-text)' }}>{lead.name}</p>
        {lead.next_follow_up_on && (
          <span className="text-[11px] font-medium whitespace-nowrap" style={{ color: overdue ? '#C96A5A' : 'var(--ms-text-muted)' }}>
            {overdue ? 'Due ' : 'Follow-up '}
            {new Date(`${lead.next_follow_up_on}T00:00:00`).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}
          </span>
        )}
      </div>
      {lead.phone && (
        <a href={`tel:${lead.phone.replace(/\s/g, '')}`} className="text-xs flex items-center gap-1 w-fit" style={{ color: 'var(--ms-accent)' }}>
          📞 {lead.phone}
        </a>
      )}
      {(lead.suburb_name || lead.address) && (
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>📍 {lead.suburb_name || lead.address}</p>
      )}
      {lead.notes && <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>{lead.notes}</p>}

      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        <Select
          value={lead.status}
          onChange={e => update.mutate({ status: e.target.value as InboundLeadStatus })}
          className="text-xs py-1"
          style={{ maxWidth: 150 }}
        >
          {STATUS_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </Select>
        {lead.status !== 'follow_up_due' && (
          <button
            type="button"
            onClick={() => {
              const d = new Date()
              d.setDate(d.getDate() + 3)
              update.mutate({ status: 'follow_up_due', next_follow_up_on: d.toISOString().slice(0, 10) })
            }}
            className="text-xs px-2 py-1 rounded-md"
            style={{ backgroundColor: 'var(--ms-accent-light)', color: 'var(--ms-accent)' }}
          >
            Follow up in 3d
          </button>
        )}
        {!lead.customer_account_id ? (
          <button
            type="button"
            onClick={() => convert.mutate()}
            disabled={convert.isPending}
            className="text-xs px-2 py-1 rounded-md font-semibold disabled:opacity-50"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#2C1810' }}
          >
            {convert.isPending ? '…' : 'Convert to account'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => navigate('/customer-accounts')}
            className="text-xs px-2 py-1 rounded-md"
            style={{ backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-mid)' }}
          >
            View account →
          </button>
        )}
      </div>
      {error && <p className="text-xs" style={{ color: '#C96A5A' }}>{error}</p>}
    </div>
  )
}

export default function LeadInboxPage() {
  const [adding, setAdding] = useState(false)
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['inbound-leads'],
    queryFn: () => listInboundLeads().then(r => r.data),
  })

  const byStatus = useMemo(() => {
    const map: Record<string, InboundLead[]> = {}
    for (const l of leads) (map[l.status] ??= []).push(l)
    return map
  }, [leads])

  const followUpsDue = useMemo(
    () => leads.filter(l => l.status === 'follow_up_due' && isOverdue(l.next_follow_up_on)),
    [leads],
  )

  return (
    <div className="p-6">
      <MobileServicesSubNav className="mb-4" />
      <div className="flex items-center justify-between mb-5">
        <PageHeader title="Lead inbox" />
        {!adding && <Button onClick={() => setAdding(true)}>+ New lead</Button>}
      </div>

      {adding && <div className="mb-5"><AddLeadForm onDone={() => setAdding(false)} /></div>}

      {followUpsDue.length > 0 && (
        <div className="mb-5 rounded-lg border p-3" style={{ borderColor: '#C96A5A', backgroundColor: 'rgba(201,106,90,0.08)' }}>
          <p className="text-sm font-semibold" style={{ color: '#A4392B' }}>
            {followUpsDue.length} follow-up{followUpsDue.length !== 1 ? 's' : ''} overdue
          </p>
        </div>
      )}

      {isLoading ? (
        <Spinner />
      ) : leads.length === 0 ? (
        <p className="text-sm py-6" style={{ color: 'var(--ms-text-muted)' }}>
          No leads yet. Add inbound calls and enquiries here so they don't slip through.
        </p>
      ) : (
        <div className="overflow-x-auto pb-4">
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${PIPELINE.length}, minmax(230px, 1fr))`, minWidth: 960 }}>
            {PIPELINE.map(col => {
              const items = byStatus[col.key] ?? []
              return (
                <div key={col.key}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: col.color }} />
                    <h3 className="text-xs font-semibold uppercase tracking-wide flex-1" style={{ color: 'var(--ms-text-muted)' }}>{col.label}</h3>
                    <span className="text-xs rounded-full px-1.5 py-0.5" style={{ backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-muted)' }}>{items.length}</span>
                  </div>
                  <div className="space-y-2 min-h-[80px]">
                    {items.length === 0 ? (
                      <div className="rounded-lg border border-dashed p-4 text-center text-xs" style={{ borderColor: 'var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                        Empty
                      </div>
                    ) : (
                      items.map(lead => <LeadCard key={lead.id} lead={lead} />)
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
