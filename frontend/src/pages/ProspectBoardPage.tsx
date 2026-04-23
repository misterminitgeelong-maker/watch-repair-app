import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listProspectLeads,
  advanceProspectLead,
  deleteProspectLead,
  updateProspectLead,
  type ProspectLead,
  type ProspectLeadStatus,
} from '@/lib/api'
import { Button, PageHeader, Spinner } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'

const STATUS_COLUMNS: { key: ProspectLeadStatus; label: string; color: string }[] = [
  { key: 'new', label: 'New Business', color: 'var(--ms-accent)' },
  { key: 'contacted', label: 'Business Contacted', color: '#f59e0b' },
  { key: 'visited', label: 'Business Visited', color: '#8b5cf6' },
  { key: 'onboarded', label: 'Business Onboarded', color: '#10b981' },
]

function LeadCard({ lead, isLast }: { lead: ProspectLead; isLast: boolean }) {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [contactName, setContactName] = useState(lead.contact_name ?? '')
  const [contactEmail, setContactEmail] = useState(lead.contact_email ?? '')
  const [notes, setNotes] = useState(lead.notes ?? '')
  const [visitDate, setVisitDate] = useState(
    lead.visit_scheduled_at ? lead.visit_scheduled_at.slice(0, 10) : ''
  )

  const advance = useMutation({
    mutationFn: () => advanceProspectLead(lead.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prospect-leads'] }),
  })

  const remove = useMutation({
    mutationFn: () => deleteProspectLead(lead.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prospect-leads'] }),
  })

  const update = useMutation({
    mutationFn: () =>
      updateProspectLead(lead.id, {
        contact_name: contactName || undefined,
        contact_email: contactEmail || undefined,
        notes: notes || undefined,
        visit_scheduled_at: visitDate ? new Date(visitDate).toISOString() : null,
      }),
    onSuccess: () => {
      setEditing(false)
      qc.invalidateQueries({ queryKey: ['prospect-leads'] })
    },
  })

  const startEdit = () => {
    setContactName(lead.contact_name ?? '')
    setContactEmail(lead.contact_email ?? '')
    setNotes(lead.notes ?? '')
    setVisitDate(lead.visit_scheduled_at ? lead.visit_scheduled_at.slice(0, 10) : '')
    setEditing(true)
  }

  return (
    <div
      className="rounded-lg border p-3"
      style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate" style={{ color: 'var(--ms-text)' }}>
            {lead.name}
          </p>
          {lead.address && (
            <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>
              {lead.address}
            </p>
          )}
          <div className="flex flex-wrap gap-3 mt-1 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
            {lead.phone && <span>{lead.phone}</span>}
            {lead.rating && <span>★ {lead.rating}</span>}
            {lead.website && (
              <a
                href={lead.website}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--ms-accent)' }}
              >
                Website ↗
              </a>
            )}
          </div>
          {(lead.contact_name || lead.contact_email) && (
            <div className="mt-1.5 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
              {lead.contact_name}
              {lead.contact_name && lead.contact_email ? ' · ' : ''}
              {lead.contact_email}
            </div>
          )}
          {lead.visit_scheduled_at && (
            <div className="mt-1 text-xs font-medium" style={{ color: '#8b5cf6' }}>
              Visit:{' '}
              {new Date(lead.visit_scheduled_at).toLocaleDateString('en-AU', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </div>
          )}
          {lead.notes && !expanded && (
            <p className="mt-1 text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>
              {lead.notes}
            </p>
          )}
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-xs px-1 rounded flex-shrink-0"
          style={{ color: 'var(--ms-text-muted)' }}
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? '▴' : '▾'}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--ms-border)' }}>
          {editing ? (
            <div className="space-y-2">
              <input
                className="w-full rounded border px-2 py-1 text-xs"
                style={{
                  borderColor: 'var(--ms-border)',
                  backgroundColor: 'var(--ms-bg)',
                  color: 'var(--ms-text)',
                }}
                placeholder="Contact name"
                value={contactName}
                onChange={e => setContactName(e.target.value)}
              />
              <input
                className="w-full rounded border px-2 py-1 text-xs"
                style={{
                  borderColor: 'var(--ms-border)',
                  backgroundColor: 'var(--ms-bg)',
                  color: 'var(--ms-text)',
                }}
                placeholder="Contact email"
                value={contactEmail}
                onChange={e => setContactEmail(e.target.value)}
              />
              <textarea
                className="w-full rounded border px-2 py-1 text-xs resize-none"
                style={{
                  borderColor: 'var(--ms-border)',
                  backgroundColor: 'var(--ms-bg)',
                  color: 'var(--ms-text)',
                }}
                placeholder="Notes"
                rows={2}
                value={notes}
                onChange={e => setNotes(e.target.value)}
              />
              <div>
                <label
                  className="text-xs block mb-1"
                  style={{ color: 'var(--ms-text-muted)' }}
                >
                  Schedule visit
                </label>
                <input
                  type="date"
                  className="rounded border px-2 py-1 text-xs"
                  style={{
                    borderColor: 'var(--ms-border)',
                    backgroundColor: 'var(--ms-bg)',
                    color: 'var(--ms-text)',
                  }}
                  value={visitDate}
                  onChange={e => setVisitDate(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => update.mutate()} disabled={update.isPending}>
                  {update.isPending ? 'Saving…' : 'Save'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div>
              {lead.notes && (
                <p className="text-xs mb-2" style={{ color: 'var(--ms-text-muted)' }}>
                  {lead.notes}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={startEdit}
                  className="text-xs px-2 py-1 rounded"
                  style={{ backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text)' }}
                >
                  Edit details
                </button>
                {!isLast && (
                  <button
                    onClick={() => advance.mutate()}
                    disabled={advance.isPending}
                    className="text-xs px-2 py-1 rounded font-medium"
                    style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
                  >
                    {advance.isPending ? '…' : 'Move to next →'}
                  </button>
                )}
                <button
                  onClick={() => {
                    if (window.confirm(`Remove ${lead.name} from board?`)) remove.mutate()
                  }}
                  className="text-xs px-2 py-1 rounded"
                  style={{ color: 'var(--ms-badge-alert-text)' }}
                >
                  Remove
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ProspectBoardPage() {
  const [view, setView] = useState<'board' | 'visits'>('board')

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['prospect-leads'],
    queryFn: () => listProspectLeads().then(r => r.data),
  })

  const byStatus = (status: string) => leads.filter(l => l.status === status)

  const upcomingVisits = [...leads]
    .filter(l => l.visit_scheduled_at)
    .sort(
      (a, b) =>
        new Date(a.visit_scheduled_at!).getTime() - new Date(b.visit_scheduled_at!).getTime()
    )

  return (
    <div className="p-6">
      <MobileServicesSubNav className="mb-4" />
      <div className="flex items-center justify-between mb-5">
        <PageHeader title="Prospect Board" />
        <div
          className="flex gap-1 rounded-lg p-1"
          style={{ backgroundColor: 'var(--ms-hover)' }}
        >
          {(['board', 'visits'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-3 py-1 rounded-md text-sm font-medium transition-colors"
              style={{
                backgroundColor: view === v ? 'var(--ms-surface)' : 'transparent',
                color: view === v ? 'var(--ms-text)' : 'var(--ms-text-muted)',
                boxShadow: view === v ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              {v === 'board' ? 'Board' : 'Visit Calendar'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <Spinner />
      ) : view === 'board' ? (
        <div className="overflow-x-auto pb-4">
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: 'repeat(4, minmax(230px, 1fr))', minWidth: 960 }}
          >
            {STATUS_COLUMNS.map((col, colIdx) => (
              <div key={col.key}>
                <div className="flex items-center gap-2 mb-3">
                  <span
                    className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: col.color }}
                  />
                  <h3
                    className="text-xs font-semibold uppercase tracking-wide flex-1"
                    style={{ color: 'var(--ms-text-muted)' }}
                  >
                    {col.label}
                  </h3>
                  <span
                    className="text-xs rounded-full px-1.5 py-0.5"
                    style={{
                      backgroundColor: 'var(--ms-hover)',
                      color: 'var(--ms-text-muted)',
                    }}
                  >
                    {byStatus(col.key).length}
                  </span>
                </div>
                <div className="space-y-2 min-h-[80px]">
                  {byStatus(col.key).length === 0 ? (
                    <div
                      className="rounded-lg border border-dashed p-4 text-center text-xs"
                      style={{
                        borderColor: 'var(--ms-border)',
                        color: 'var(--ms-text-muted)',
                      }}
                    >
                      No businesses
                    </div>
                  ) : (
                    byStatus(col.key).map(lead => (
                      <LeadCard
                        key={lead.id}
                        lead={lead}
                        isLast={colIdx === STATUS_COLUMNS.length - 1}
                      />
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--ms-text)' }}>
            Upcoming Visits ({upcomingVisits.length})
          </h2>
          {upcomingVisits.length === 0 ? (
            <p className="text-sm py-4" style={{ color: 'var(--ms-text-muted)' }}>
              No visits scheduled. Open the board, expand a card, and set a visit date.
            </p>
          ) : (
            <div className="space-y-3">
              {upcomingVisits.map(lead => {
                const d = new Date(lead.visit_scheduled_at!)
                const isPast = d < new Date()
                const col = STATUS_COLUMNS.find(c => c.key === lead.status)
                return (
                  <div
                    key={lead.id}
                    className="flex items-start gap-4 p-4 rounded-lg border"
                    style={{
                      backgroundColor: 'var(--ms-surface)',
                      borderColor: 'var(--ms-border)',
                    }}
                  >
                    <div className="text-center min-w-[48px]">
                      <div
                        className="text-xl font-bold leading-none"
                        style={{ color: isPast ? 'var(--ms-badge-alert-text)' : 'var(--ms-accent)' }}
                      >
                        {d.getDate()}
                      </div>
                      <div className="text-xs uppercase mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                        {d.toLocaleDateString('en-AU', { month: 'short' })}
                      </div>
                      {isPast && (
                        <div className="text-xs mt-0.5" style={{ color: 'var(--ms-badge-alert-text)' }}>
                          Past
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                        {lead.name}
                      </p>
                      {lead.address && (
                        <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                          {lead.address}
                        </p>
                      )}
                      <div
                        className="flex flex-wrap gap-3 mt-1 text-xs"
                        style={{ color: 'var(--ms-text-mid)' }}
                      >
                        {lead.phone && <span>{lead.phone}</span>}
                        {lead.contact_name && <span>Contact: {lead.contact_name}</span>}
                        {lead.website && (
                          <a
                            href={lead.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: 'var(--ms-accent)' }}
                          >
                            Website ↗
                          </a>
                        )}
                      </div>
                      {lead.notes && (
                        <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                          {lead.notes}
                        </p>
                      )}
                    </div>
                    {col && (
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0"
                        style={{ backgroundColor: col.color + '22', color: col.color }}
                      >
                        {col.label}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
