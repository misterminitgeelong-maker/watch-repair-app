import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, KeyRound, Mail, MessageSquare } from 'lucide-react'
import {
  API_ORIGIN,
  createJobFromInboundEmail,
  getInbox,
  getInboundEmail,
  getInboundEmailParsed,
  listInboundEmails,
  updateInboundEmailStatus,
  type InboundEmailJobCreateRequest,
  type InboundEmailJobCreateResult,
} from '@/lib/api'
import { useParentLeadIngest } from '@/hooks/useParentLeadIngest'
import { Button, Card, EmptyState, Input, PageHeader, Spinner, Textarea } from '@/components/ui'

function formatDate(s: string) {
  const d = new Date(s)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  return d.toLocaleDateString()
}

const STATUS_COLORS: Record<string, string> = {
  new: '#B47828',
  processed: '#2F855A',
  dismissed: '#718096',
}

type EmailLeadForm = Omit<InboundEmailJobCreateRequest, 'target_tenant_id'>

const EMPTY_FORM: EmailLeadForm = {
  customer_name: '',
  phone: '',
  email: '',
  suburb: '',
  state_code: '',
  service_required: '',
  vehicle_make: '',
  vehicle_model: '',
  vehicle_year: '',
  details: '',
  contact_preference: '',
}

function EmailLeadReviewForm({ id, onCreated }: { id: string; onCreated: (result: InboundEmailJobCreateResult) => void }) {
  const [form, setForm] = useState<EmailLeadForm>(EMPTY_FORM)
  const [seeded, setSeeded] = useState(false)
  const [showRaw, setShowRaw] = useState(false)

  const { data: parsed, isLoading: parsedLoading } = useQuery({
    queryKey: ['inbound-email-parsed', id],
    queryFn: () => getInboundEmailParsed(id).then(r => r.data),
  })
  const { data: detail } = useQuery({
    queryKey: ['inbound-email', id],
    queryFn: () => getInboundEmail(id).then(r => r.data),
  })

  // Pre-fill the form once from the parsed preview — after that it's the
  // staff's own edits, so we don't want the query re-seeding it on refetch.
  useEffect(() => {
    if (!parsed || seeded) return
    setForm({
      customer_name: parsed.customer_name ?? '',
      phone: parsed.phone ?? '',
      email: parsed.email ?? '',
      // The form only tells us the customer's state, not their suburb — staff fill that in from the details field.
      suburb: '',
      state_code: parsed.location_state_raw ?? '',
      service_required: parsed.service_required ?? '',
      vehicle_make: parsed.vehicle_make ?? '',
      vehicle_model: parsed.vehicle_model ?? '',
      vehicle_year: parsed.vehicle_year ?? '',
      details: parsed.details ?? '',
      contact_preference: parsed.contact_preference ?? '',
    })
    setSeeded(true)
  }, [parsed, seeded])

  const createMutation = useMutation({
    mutationFn: () => createJobFromInboundEmail(id, form).then(r => r.data),
    onSuccess: onCreated,
  })

  const field = (key: keyof EmailLeadForm) => ({
    value: form[key] ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm(f => ({ ...f, [key]: e.target.value })),
  })

  if (parsedLoading) return <Spinner />

  return (
    <div className="mt-3 space-y-3">
      {parsed && !parsed.fields_found && (
        <p className="text-xs rounded p-2" style={{ backgroundColor: 'rgba(180,120,40,0.1)', color: '#B47828' }}>
          No fields could be extracted from this email — fill in the form manually, or use Mark processed / Dismiss
          if you're handling it another way.
        </p>
      )}
      {parsed?.suggested_operator_name && (
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Nearest provider per the email: <strong>{parsed.suggested_operator_name}</strong> ({parsed.match_confidence}).
          The job below still lands in HQ — this is informational only.
        </p>
      )}
      {parsed?.nearest_provider_raw && !parsed?.suggested_operator_name && (
        <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
          Email says nearest provider is "{parsed.nearest_provider_raw}" but no matching operator was found ({parsed.match_confidence}).
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Input label="Customer name" {...field('customer_name')} required />
        <Input label="Phone" {...field('phone')} />
        <Input label="Email" {...field('email')} />
        <Input label="Contact preference" {...field('contact_preference')} placeholder="Phone / Email" />
        <Input label="Suburb" {...field('suburb')} />
        <Input label="State" {...field('state_code')} placeholder="NSW" />
        <Input label="Service required" {...field('service_required')} />
        <Input label="Vehicle make" {...field('vehicle_make')} />
        <Input label="Vehicle model" {...field('vehicle_model')} />
        <Input label="Vehicle year" {...field('vehicle_year')} />
      </div>
      <Textarea label="Details" rows={3} {...field('details')} />

      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          size="sm"
          disabled={!form.customer_name.trim() || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          Create job
        </Button>
        <button
          type="button"
          className="text-xs font-medium"
          style={{ color: 'var(--ms-text-muted)' }}
          onClick={() => setShowRaw(v => !v)}
        >
          {showRaw ? 'Hide' : 'View'} raw email
        </button>
      </div>
      {createMutation.isError && (
        <p className="text-xs" style={{ color: 'var(--ms-danger, #C0392B)' }}>
          Couldn't create the job — please try again.
        </p>
      )}
      {showRaw && (
        detail?.text_body ? (
          <pre
            className="text-xs whitespace-pre-wrap rounded p-3 max-h-80 overflow-y-auto"
            style={{ backgroundColor: 'var(--ms-bg, rgba(0,0,0,0.04))', color: 'var(--ms-text)' }}
          >
            {detail.text_body}
          </pre>
        ) : (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>No plain-text body captured.</p>
        )
      )}
    </div>
  )
}

function InboundEmailCard({ id, subject, fromEmail, status, createdAt, autoKeyJobId }: {
  id: string
  subject?: string | null
  fromEmail?: string | null
  status: 'new' | 'processed' | 'dismissed'
  createdAt: string
  autoKeyJobId?: string | null
}) {
  const [expanded, setExpanded] = useState(false)
  const [justCreated, setJustCreated] = useState<InboundEmailJobCreateResult | null>(null)
  const queryClient = useQueryClient()

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['inbound-email', id],
    queryFn: () => getInboundEmail(id).then(r => r.data),
    enabled: expanded && status !== 'new',
  })

  const statusMutation = useMutation({
    mutationFn: (next: 'processed' | 'dismissed') => updateInboundEmailStatus(id, next),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbound-emails'] })
      queryClient.invalidateQueries({ queryKey: ['inbound-email', id] })
    },
  })

  const showReviewForm = expanded && status === 'new' && !justCreated

  return (
    <Card className="p-4">
      <div className="flex items-start gap-4">
        <div
          className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: 'rgba(180,120,40,0.15)', color: '#B47828' }}
        >
          <Mail size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <button
            type="button"
            className="text-left w-full"
            onClick={() => setExpanded(v => !v)}
          >
            <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
              {subject?.trim() || '(no subject)'}
            </p>
            <p className="text-xs mt-1 truncate" style={{ color: 'var(--ms-text-muted)' }}>
              {fromEmail || 'Unknown sender'} · {formatDate(createdAt)}
            </p>
          </button>

          {justCreated && (
            <div className="mt-3 flex items-center gap-2 text-sm" style={{ color: '#2F855A' }}>
              <CheckCircle2 size={16} />
              Job #{justCreated.job_number} created on {justCreated.tenant_name}.
            </div>
          )}

          {expanded && !justCreated && status === 'new' && (
            <EmailLeadReviewForm id={id} onCreated={result => {
              setJustCreated(result)
              queryClient.invalidateQueries({ queryKey: ['inbound-emails'] })
            }} />
          )}

          {expanded && status !== 'new' && (
            <div className="mt-3">
              {detailLoading ? (
                <Spinner />
              ) : detail?.text_body ? (
                <pre
                  className="text-xs whitespace-pre-wrap rounded p-3 max-h-80 overflow-y-auto"
                  style={{ backgroundColor: 'var(--ms-bg, rgba(0,0,0,0.04))', color: 'var(--ms-text)' }}
                >
                  {detail.text_body}
                </pre>
              ) : (
                <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                  No plain-text body captured{detail?.html_body ? ' (HTML only — open the job email in your mail client if needed)' : ''}.
                </p>
              )}
              {autoKeyJobId && (
                <Link to="/minit/mobile-services" className="text-xs font-medium inline-block mt-2" style={{ color: 'var(--ms-accent)' }}>
                  View jobs →
                </Link>
              )}
            </div>
          )}

          {showReviewForm && (
            <div className="flex gap-3 mt-3">
              <button
                type="button"
                className="text-sm font-medium"
                style={{ color: 'var(--ms-accent)' }}
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate('processed')}
              >
                Mark processed
              </button>
              <button
                type="button"
                className="text-sm font-medium"
                style={{ color: 'var(--ms-text-muted)' }}
                disabled={statusMutation.isPending}
                onClick={() => statusMutation.mutate('dismissed')}
              >
                Dismiss
              </button>
            </div>
          )}
        </div>
        <span
          className="text-xs font-medium shrink-0 capitalize"
          style={{ color: STATUS_COLORS[status] ?? 'var(--ms-text-muted)' }}
        >
          {status}
        </span>
      </div>
    </Card>
  )
}

export default function MinitInboxPage() {
  const { data: alerts, isLoading: inboxLoading } = useQuery({
    queryKey: ['inbox', 0],
    queryFn: () => getInbox(50, 0).then(r => r.data),
  })

  const { data: emailLeads, isLoading: emailsLoading } = useQuery({
    queryKey: ['inbound-emails'],
    queryFn: () => listInboundEmails().then(r => r.data),
  })

  const { data: leadIngest, isLoading: ingestLoading } = useParentLeadIngest()

  if (inboxLoading || emailsLoading) return <Spinner />

  const networkAlerts = (alerts ?? []).filter(ev => ev.event_type !== 'inbound_email_received')
  const emails = emailLeads ?? []
  const newEmailCount = emails.filter(e => e.status === 'new').length
  const ingestPublicId = leadIngest?.mobile_lead_ingest_public_id ?? null
  const ingestUrl = ingestPublicId
    ? `${API_ORIGIN || window.location.origin}/v1/public/mobile-key-leads/${ingestPublicId}`
    : null
  const ingestReady = Boolean(ingestPublicId && leadIngest?.mobile_lead_webhook_secret_configured)
  const forceHq = leadIngest?.mobile_lead_force_hq_dispatch === true
  const isEmpty = networkAlerts.length === 0 && emails.length === 0

  return (
    <div>
      <PageHeader title="Inbox" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        HQ triage for website mobile key leads, BCC email enquiries, and escalated dispatch alerts.
      </p>

      {!ingestReady && !ingestLoading && (
        <Card className="mb-6 p-5">
          <div className="flex items-start gap-3">
            <MessageSquare size={20} style={{ color: 'var(--ms-accent)', flexShrink: 0, marginTop: 2 }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
                Website lead ingest {ingestPublicId ? 'needs webhook secret' : 'not enabled yet'}
              </p>
              <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
                Configure the ingest URL and security password so minit.com.au can send job requests.
                {forceHq && ' HQ testing mode is on — all leads will appear here.'}
              </p>
              {ingestUrl && (
                <p className="text-xs mt-2 font-mono break-all" style={{ color: 'var(--ms-text-muted)' }}>
                  {ingestUrl}
                </p>
              )}
              <Link
                to="/minit/lead-routing"
                className="text-sm font-medium inline-block mt-2"
                style={{ color: 'var(--ms-accent)' }}
              >
                Open lead routing settings →
              </Link>
            </div>
          </div>
        </Card>
      )}

      {ingestReady && forceHq && (
        <Card className="mb-6 p-4" style={{ borderColor: 'var(--ms-accent)', backgroundColor: 'rgba(79,130,201,0.06)' }}>
          <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
            HQ testing mode is active — all website leads skip operators and land here.
          </p>
          <Link to="/minit/lead-routing" className="text-xs font-medium mt-1 inline-block" style={{ color: 'var(--ms-accent)' }}>
            Change in lead routing →
          </Link>
        </Card>
      )}

      {networkAlerts.length > 0 && (
        <section className="mb-8">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--ms-text)' }}>
            <KeyRound size={16} style={{ color: 'var(--ms-accent)' }} />
            Mobile key leads & alerts
            <span className="text-xs font-normal tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>
              ({networkAlerts.length})
            </span>
          </h2>
          <div className="space-y-3">
            {networkAlerts.map(ev => (
              <Card key={ev.id} className="p-4">
                <div className="flex items-start gap-4">
                  <div
                    className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(180,120,40,0.15)', color: '#B47828' }}
                  >
                    <KeyRound size={20} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                      {ev.event_summary}
                    </p>
                    <p className="text-xs mt-1 capitalize" style={{ color: 'var(--ms-text-muted)' }}>
                      {ev.event_type.replace(/_/g, ' ')} · {formatDate(ev.created_at)}
                    </p>
                  </div>
                  {ev.entity_type === 'auto_key_job' && ev.entity_id && (
                    <Link
                      to="/minit/mobile-services"
                      className="text-sm font-medium shrink-0"
                      style={{ color: 'var(--ms-accent)' }}
                    >
                      View jobs
                    </Link>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section className="mb-6">
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--ms-text)' }}>
          <Mail size={16} style={{ color: 'var(--ms-accent)' }} />
          Email leads
          {newEmailCount > 0 && (
            <span
              className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
              style={{ backgroundColor: '#C96A5A', color: '#fff' }}
            >
              {newEmailCount} new
            </span>
          )}
        </h2>
        {emails.length === 0 ? (
          <Card className="p-4">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              No BCC enquiry emails yet. They appear here once inbound email parse is configured.
            </p>
            <Link
              to="/minit/lead-routing"
              className="text-sm font-medium inline-block mt-2"
              style={{ color: 'var(--ms-accent)' }}
            >
              Lead routing settings →
            </Link>
          </Card>
        ) : (
          <div className="space-y-3">
            {emails.map(em => (
              <InboundEmailCard
                key={em.id}
                id={em.id}
                subject={em.subject}
                fromEmail={em.from_email}
                status={em.status}
                createdAt={em.created_at}
                autoKeyJobId={em.auto_key_job_id}
              />
            ))}
          </div>
        )}
      </section>

      {isEmpty && (
        <EmptyState message="Nothing in the inbox yet. Website mobile key leads and email enquiries will appear here once ingest is configured." />
      )}
    </div>
  )
}
