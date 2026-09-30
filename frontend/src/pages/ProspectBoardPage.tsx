import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listProspectLeads,
  getApiErrorMessage,
  advanceProspectLead,
  deleteProspectLead,
  updateProspectLead,
  type ProspectLead,
  type ProspectLeadStatus,
} from '@/lib/api'
import { Button, Input, Modal, PageHeader, Spinner } from '@/components/ui'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'

const STATUS_COLUMNS: { key: ProspectLeadStatus; label: string; color: string }[] = [
  { key: 'new', label: 'New Business', color: 'var(--ms-accent)' },
  { key: 'contacted', label: 'Business Contacted', color: '#f59e0b' },
  { key: 'visited', label: 'Business Visited', color: '#8b5cf6' },
  { key: 'onboarded', label: 'Business Onboarded', color: '#10b981' },
  { key: 'quote_needed', label: 'Quote needed', color: '#B87030' },
  { key: 'follow_up_due', label: 'Follow-up due', color: '#A2502E' },
  { key: 'won', label: 'Won', color: '#4F7A4A' },
  { key: 'lost', label: 'Archived', color: '#777777' },
]

const NEXT_STATUS: Record<ProspectLeadStatus, ProspectLeadStatus | null> = {
  quote_needed: 'contacted',
  follow_up_due: 'contacted',
  won: null,
  lost: null,
  new: 'contacted',
  contacted: 'visited',
  visited: 'onboarded',
  onboarded: null,
}

const NEXT_LABEL: Record<ProspectLeadStatus, string> = {
  quote_needed: 'Mark as Contacted',
  follow_up_due: 'Mark as Contacted',
  won: '',
  lost: '',
  new: 'Mark as Contacted',
  contacted: 'Mark as Visited',
  visited: 'Mark as Onboarded',
  onboarded: '',
}

function LeadModal({ lead, onClose }: { lead: ProspectLead; onClose: () => void }) {
  const navigate = useNavigate()
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
    mutationFn: () => advanceProspectLead(lead.id, details()),
    onSuccess: (res) => {
      setDirty(false)
      qc.invalidateQueries({ queryKey: ['prospect-leads'] })
      qc.invalidateQueries({ queryKey: ['inbound-leads'] })
      if (res.data.status === 'onboarded' && res.data.customer_account_id) {
        navigate('/customer-accounts')
      }
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteProspectLead(lead.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prospect-leads'] }); onClose() },
  })

  const details = () => ({
    contact_name: contactName.trim() || null,
    contact_email: contactEmail.trim() || null,
    notes: notes || null,
    visit_scheduled_at: visitDate ? `${visitDate}T00:00:00Z` : null,
  })

  const save = useMutation({
    mutationFn: () =>
      updateProspectLead(lead.id, details()),
    onSuccess: () => { setDirty(false); qc.invalidateQueries({ queryKey: ['prospect-leads'] }); qc.invalidateQueries({ queryKey: ['inbound-leads'] }) },
  })

  const mapsUrl = lead.address
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(lead.address)}`
    : null

  const busy = save.isPending || advance.isPending || remove.isPending
  const close = () => {
    if (!busy && (!dirty || window.confirm('Discard unsaved prospect changes?'))) onClose()
  }
  const mutationError = save.error || advance.error || remove.error

  return (
    <Modal title={lead.name} onClose={close} closeDisabled={busy} mobileFullScreen>
      <p className="mb-3 text-sm font-medium">{col?.label ?? lead.status}</p>
        {/* Body */}
        <div className="overflow-y-auto flex-1 py-2 space-y-4">

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
              aria-label="Contact name" placeholder="Contact name" disabled={busy}
              value={contactName}
              onChange={e => { setContactName(e.target.value); setDirty(true) }}
            />
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              aria-label="Contact email" type="email" placeholder="Contact email" disabled={busy}
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
              aria-label="Notes" placeholder="Add notes about this business…" disabled={busy}
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
              aria-label="Visit date" disabled={busy} type="date"
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
              value={visitDate}
              onChange={e => { setVisitDate(e.target.value); setDirty(true) }}
            />
            {visitDate && (
              <button
                onClick={() => { setVisitDate(''); setDirty(true) }}
                disabled={busy} className="text-xs ml-2 min-h-11 px-3"
                style={{ color: 'var(--ms-text-muted)' }}
              >
                Clear date
              </button>
            )}
          </div>
        </div>

        {mutationError && <p role="alert" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(mutationError)}</p>}
        {dirty && <p className="text-sm">Unsaved changes. Advancing also saves these details.</p>}
        {/* Footer actions */}
        <div
          className="sticky bottom-0 py-4 flex flex-wrap items-center gap-2"
          style={{ borderTop: '1px solid var(--ms-border)', backgroundColor: 'var(--ms-surface)' }}
        >
          {dirty && (
            <Button onClick={() => save.mutate()} disabled={busy}>
              {save.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          )}
          {nextStatus && (
            <Button
              variant="secondary"
              onClick={() => advance.mutate()}
              disabled={busy}
            >
              {advance.isPending ? '…' : NEXT_LABEL[lead.status]}
            </Button>
          )}
          {lead.status === 'onboarded' && lead.customer_account_id && (
            <Button
              variant="secondary"
              onClick={() => navigate('/customer-accounts')}
            >
              View Customer Account →
            </Button>
          )}
          <div className="flex-1" />
          <button
            onClick={() => { if (window.confirm(`Remove ${lead.name} from board?`)) remove.mutate() }}
            disabled={busy} className="text-xs px-3 min-h-11 rounded"
            style={{ color: 'var(--ms-badge-alert-text)' }}
          >
            Remove
          </button>
        </div>
    </Modal>
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
            {new Date(`${lead.visit_scheduled_at.slice(0, 10)}T12:00:00`).toLocaleDateString('en-AU', {
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
  const [view, setView] = useState<'board' | 'list' | 'visits'>('board')
  const [selectedLead, setSelectedLead] = useState<ProspectLead | null>(null)

  const [search, setSearch] = useState('')
  const { data: leads = [], isLoading, error, refetch } = useQuery({
    queryKey: ['prospect-leads'],
    queryFn: () => listProspectLeads().then(r => r.data),
  })

  const filtered = leads.filter(l => `${l.name} ${l.address ?? ''} ${l.contact_name ?? ''}`.toLowerCase().includes(search.toLowerCase()))
  const byStatus = (status: string) => filtered.filter(l => l.status === status)

  const upcomingVisits = [...filtered]
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
    <div className="p-2 sm:p-6">
      <MobileServicesSubNav className="mb-4" />
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <PageHeader title="Prospect Board" />
        <div
          className="flex gap-1 rounded-lg p-1"
          style={{ backgroundColor: 'var(--ms-hover)' }}
        >
          {(['board', 'list', 'visits'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="min-h-11 px-3 py-1 rounded-md text-sm font-medium transition-colors"
              style={{
                backgroundColor: view === v ? 'var(--ms-surface)' : 'transparent',
                color: view === v ? 'var(--ms-text)' : 'var(--ms-text-muted)',
                boxShadow: view === v ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              {v === 'board' ? 'Board' : v === 'list' ? 'List' : 'Visits'}
            </button>
          ))}
        </div>
      </div>

      <p className="mb-3 text-sm">{leads.length} prospects · {upcomingVisits.length} scheduled visits</p>
      <Input label="Find a prospect" placeholder="Business, suburb or contact…" value={search} onChange={e => setSearch(e.target.value)} />
      {!isLoading && !error && view !== 'visits' && (
        <div className={view === 'board' ? 'md:hidden mt-4 space-y-3' : 'mt-4 space-y-3'}>
          {filtered.length ? filtered.map(lead => <div key={lead.id}><p className="text-xs font-medium mb-1">{STATUS_COLUMNS.find(c => c.key === lead.status)?.label ?? lead.status}</p><LeadCard lead={lead} onClick={() => setSelectedLead(lead)} /></div>) : <p>No prospects match these filters.</p>}
        </div>
      )}
      {isLoading ? (
        <Spinner />
      ) : error ? (<div role="alert">{getApiErrorMessage(error, 'Could not load prospects.')}<Button onClick={() => void refetch()}>Retry</Button></div>) : view === 'list' ? null : view === 'board' ? (
        <div className="hidden md:block pb-4 mt-4">
          <div
            className="grid grid-cols-2 xl:grid-cols-4 gap-4"
          >
            {STATUS_COLUMNS.map(col => (
              <div key={col.key} className="min-w-0">
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
                const d = new Date(`${lead.visit_scheduled_at!.slice(0, 10)}T12:00:00`)
                const today = new Date(); today.setHours(0, 0, 0, 0)
                const isPast = d < today
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
                        style={{ backgroundColor: 'var(--ms-hover)', color: col.color }}
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
        <LeadModal key={currentSelected.id} lead={currentSelected} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  )
}
