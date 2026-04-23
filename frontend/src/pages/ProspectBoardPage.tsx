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

const NEXT_STATUS: Record<ProspectLeadStatus, ProspectLeadStatus | null> = {
  new: 'contacted',
  contacted: 'visited',
  visited: 'onboarded',
  onboarded: null,
}

const NEXT_LABEL: Record<ProspectLeadStatus, string> = {
  new: 'Mark as Contacted',
  contacted: 'Mark as Visited',
  visited: 'Mark as Onboarded',
  onboarded: '',
}

function LeadModal({ lead, onClose }: { lead: ProspectLead; onClose: () => void }) {
  const qc = useQueryClient()
  const [contactName, setContactName] = useState(lead.contact_name ?? '')
  const [contactEmail, setContactEmail] = useState(lead.contact_email ?? '')
  const [notes, setNotes] = useState(lead.notes ?? '')
  const [visitDate, setVisitDate] = useState(
    lead.visit_scheduled_at ? lead.visit_scheduled_at.slice(0, 10) : ''
  )
  const [dirty, setDirty] = useState(false)

  const col = STATUS_COLUMNS.find(c => c.key === lead.status)
  const nextStatus = NEXT_STATUS[lead.status]

  const advance = useMutation({
    mutationFn: () => advanceProspectLead(lead.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prospect-leads'] }),
  })

  const remove = useMutation({
    mutationFn: () => deleteProspectLead(lead.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prospect-leads'] }); onClose() },
  })

  const save = useMutation({
    mutationFn: () =>
      updateProspectLead(lead.id, {
        contact_name: contactName || undefined,
        contact_email: contactEmail || undefined,
        notes: notes || undefined,
        visit_scheduled_at: visitDate ? new Date(visitDate).toISOString() : null,
      }),
    onSuccess: () => { setDirty(false); qc.invalidateQueries({ queryKey: ['prospect-leads'] }) },
  })

  const mapsUrl = lead.address
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(lead.address)}`
    : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-full max-w-lg rounded-xl shadow-2xl overflow-hidden flex flex-col"
        style={{ backgroundColor: 'var(--ms-surface)', maxHeight: '90vh' }}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-4" style={{ borderBottom: '1px solid var(--ms-border)' }}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h2 className="font-bold text-lg leading-tight" style={{ color: 'var(--ms-text)' }}>
                {lead.name}
              </h2>
              {lead.category && (
                <p className="text-xs mt-0.5 capitalize" style={{ color: 'var(--ms-text-muted)' }}>
                  {lead.category.replace(/_/g, ' ')}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {col && (
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ backgroundColor: col.color + '22', color: col.color }}
                >
                  {col.label}
                </span>
              )}
              <button
                onClick={onClose}
                className="rounded-full w-7 h-7 flex items-center justify-center text-lg leading-none"
                style={{ backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-muted)' }}
                aria-label="Close"
              >
                ×
              </button>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">

          {/* Contact info from Google */}
          <div className="rounded-lg p-3 space-y-2" style={{ backgroundColor: 'var(--ms-hover)' }}>
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
              Business info
            </p>
            {lead.phone && (
              <a
                href={`tel:${lead.phone}`}
                className="flex items-center gap-2 text-sm font-medium"
                style={{ color: 'var(--ms-accent)' }}
              >
                <span>📞</span> {lead.phone}
              </a>
            )}
            {lead.address && (
              <div className="flex items-start gap-2">
                <span className="text-sm mt-0.5">📍</span>
                <div>
                  <p className="text-sm" style={{ color: 'var(--ms-text)' }}>{lead.address}</p>
                  {mapsUrl && (
                    <a
                      href={mapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs"
                      style={{ color: 'var(--ms-accent)' }}
                    >
                      Open in Google Maps ↗
                    </a>
                  )}
                </div>
              </div>
            )}
            {lead.website && (
              <a
                href={lead.website}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm"
                style={{ color: 'var(--ms-accent)' }}
              >
                <span>🌐</span> {lead.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            )}
            {lead.rating && (
              <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
                ★ {lead.rating} ({lead.review_count ?? 0} reviews)
              </p>
            )}
          </div>

          {/* CRM contact details */}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
              Your contact
            </p>
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              placeholder="Contact name"
              value={contactName}
              onChange={e => { setContactName(e.target.value); setDirty(true) }}
            />
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              placeholder="Contact email"
              value={contactEmail}
              onChange={e => { setContactEmail(e.target.value); setDirty(true) }}
            />
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
              Notes
            </p>
            <textarea
              className="w-full rounded-lg border px-3 py-2 text-sm resize-none"
              style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              placeholder="Add notes about this business…"
              rows={3}
              value={notes}
              onChange={e => { setNotes(e.target.value); setDirty(true) }}
            />
          </div>

          {/* Visit scheduling */}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
              Schedule a visit
            </p>
            <input
              type="date"
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              value={visitDate}
              onChange={e => { setVisitDate(e.target.value); setDirty(true) }}
            />
            {visitDate && (
              <button
                onClick={() => { setVisitDate(''); setDirty(true) }}
                className="text-xs ml-2"
                style={{ color: 'var(--ms-text-muted)' }}
              >
                Clear date
              </button>
            )}
          </div>
        </div>

        {/* Footer actions */}
        <div
          className="px-5 py-4 flex flex-wrap items-center gap-2"
          style={{ borderTop: '1px solid var(--ms-border)' }}
        >
          {dirty && (
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          )}
          {nextStatus && (
            <Button
              variant="secondary"
              onClick={() => advance.mutate()}
              disabled={advance.isPending}
            >
              {advance.isPending ? '…' : NEXT_LABEL[lead.status]}
            </Button>
          )}
          <div className="flex-1" />
          <button
            onClick={() => { if (window.confirm(`Remove ${lead.name} from board?`)) remove.mutate() }}
            className="text-xs px-3 py-1.5 rounded"
            style={{ color: 'var(--ms-badge-alert-text)' }}
          >
            Remove
          </button>
        </div>
      </div>
    </div>
  )
}

function LeadCard({ lead, onClick }: { lead: ProspectLead; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left rounded-lg border p-3 transition-shadow hover:shadow-md"
      style={{
        backgroundColor: 'var(--ms-surface)',
        borderColor: 'var(--ms-border)',
        cursor: 'pointer',
      }}
    >
      <p className="font-semibold text-sm leading-snug" style={{ color: 'var(--ms-text)' }}>
        {lead.name}
      </p>
      {lead.address && (
        <p className="text-xs mt-0.5 line-clamp-1" style={{ color: 'var(--ms-text-muted)' }}>
          📍 {lead.address}
        </p>
      )}
      {lead.phone && (
        <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>
          📞 {lead.phone}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 mt-1.5">
        {lead.rating && (
          <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            ★ {lead.rating}
          </span>
        )}
        {lead.visit_scheduled_at && (
          <span className="text-xs font-medium" style={{ color: '#8b5cf6' }}>
            Visit{' '}
            {new Date(lead.visit_scheduled_at).toLocaleDateString('en-AU', {
              day: 'numeric',
              month: 'short',
            })}
          </span>
        )}
        {lead.notes && (
          <span className="text-xs truncate flex-1" style={{ color: 'var(--ms-text-muted)' }}>
            {lead.notes}
          </span>
        )}
      </div>
      {(lead.contact_name || lead.contact_email) && (
        <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
          Contact: {lead.contact_name || lead.contact_email}
        </p>
      )}
    </button>
  )
}

export default function ProspectBoardPage() {
  const [view, setView] = useState<'board' | 'visits'>('board')
  const [selectedLead, setSelectedLead] = useState<ProspectLead | null>(null)

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

  // Keep modal in sync with latest data after mutations
  const currentSelected = selectedLead
    ? leads.find(l => l.id === selectedLead.id) ?? null
    : null

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
            {STATUS_COLUMNS.map(col => (
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
                    style={{ backgroundColor: 'var(--ms-hover)', color: 'var(--ms-text-muted)' }}
                  >
                    {byStatus(col.key).length}
                  </span>
                </div>
                <div className="space-y-2 min-h-[80px]">
                  {byStatus(col.key).length === 0 ? (
                    <div
                      className="rounded-lg border border-dashed p-4 text-center text-xs"
                      style={{ borderColor: 'var(--ms-border)', color: 'var(--ms-text-muted)' }}
                    >
                      No businesses
                    </div>
                  ) : (
                    byStatus(col.key).map(lead => (
                      <LeadCard
                        key={lead.id}
                        lead={lead}
                        onClick={() => setSelectedLead(lead)}
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
              No visits scheduled. Open the board, click a card, and set a visit date.
            </p>
          ) : (
            <div className="space-y-3">
              {upcomingVisits.map(lead => {
                const d = new Date(lead.visit_scheduled_at!)
                const isPast = d < new Date()
                const col = STATUS_COLUMNS.find(c => c.key === lead.status)
                return (
                  <button
                    key={lead.id}
                    type="button"
                    onClick={() => setSelectedLead(lead)}
                    className="w-full text-left flex items-start gap-4 p-4 rounded-lg border hover:shadow-md transition-shadow"
                    style={{ backgroundColor: 'var(--ms-surface)', borderColor: 'var(--ms-border)' }}
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
                          📍 {lead.address}
                        </p>
                      )}
                      {lead.phone && (
                        <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-mid)' }}>
                          📞 {lead.phone}
                        </p>
                      )}
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
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {currentSelected && (
        <LeadModal lead={currentSelected} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  )
}
