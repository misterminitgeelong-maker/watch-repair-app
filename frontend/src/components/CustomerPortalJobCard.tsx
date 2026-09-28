import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createPublicAutoKeyInvoiceCheckout,
  decidePublicAutoKeyQuote,
  decideShoeQuote,
  submitQuoteDecision,
  confirmPublicAutoKeyBooking,
  portalMessageToShop,
  type CustomerPortalJob,
  type CustomerPortalPendingAction,
  type CustomerPortalShop,
} from '@/lib/api'
import { portalJobStage, portalJobStatusLabel, type PortalStage } from '@/lib/portalStatus'
import {
  Wrench,
  ChevronRight,
  Loader2,
  BellRing,
  MessageCircle,
  Send,
  Check,
  Phone,
  Mail,
  Sparkles,
} from 'lucide-react'
import { StageRing, StageStepper } from '@/components/portal/PortalChrome'
import { jobIcon, jobTypeLabel, portalAccentStyle } from '@/components/portal/portalUtils'
import { clsx } from 'clsx'

function formatDateShort(s: string) {
  return new Date(s).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function StatusPill({ stage, label }: { stage: PortalStage; label: string }) {
  const cls =
    stage === 'ready' ? 'pt-pill pt-pill--ready'
    : stage === 'collected' ? 'pt-pill pt-pill--done'
    : stage === 'received' ? 'pt-pill pt-pill--quiet'
    : 'pt-pill'
  return (
    <span className={cls}>
      {stage === 'ready' ? (
        <Sparkles size={12} />
      ) : stage === 'collected' ? (
        <Check size={12} strokeWidth={3} />
      ) : (
        <span className={clsx('pt-pill-dot', stage === 'in_progress' && 'pt-pill-dot--live')} />
      )}
      {label}
    </span>
  )
}

function actionLabel(kind: CustomerPortalPendingAction['kind']): string {
  switch (kind) {
    case 'watch_quote_decision':
    case 'shoe_quote_decision':
    case 'auto_key_quote_decision':
      return 'Review quote'
    case 'auto_key_booking_confirm':
      return 'Confirm booking'
    case 'auto_key_invoice_checkout':
      return 'Pay invoice'
    case 'job_receipt':
    case 'auto_key_invoice_receipt':
      return 'View receipt'
    default:
      return 'Take action'
  }
}

async function runPortalAction(action: CustomerPortalPendingAction): Promise<string | null> {
  switch (action.kind) {
    case 'watch_quote_decision':
      await submitQuoteDecision(action.token, 'declined')
      return 'Quote declined'
    case 'shoe_quote_decision':
      await decideShoeQuote(action.token, 'declined')
      return 'Quote declined'
    case 'auto_key_quote_decision':
      await decidePublicAutoKeyQuote(action.token, 'declined')
      return 'Quote declined'
    case 'auto_key_booking_confirm':
      await confirmPublicAutoKeyBooking(action.token)
      return 'Booking confirmed'
    case 'auto_key_invoice_checkout': {
      const res = await createPublicAutoKeyInvoiceCheckout(action.token)
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url
        return null
      }
      throw new Error('Payment unavailable')
    }
    case 'job_receipt':
    case 'auto_key_invoice_receipt':
      window.location.href = action.url.startsWith('http') ? action.url : `${window.location.origin}${action.url}`
      return null
    default:
      return null
  }
}

function PendingActions({
  actions,
  onDone,
}: {
  actions: CustomerPortalPendingAction[]
  onDone?: () => void
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!actions.length) return null

  async function handleQuick(action: CustomerPortalPendingAction) {
    if (action.kind.endsWith('_quote_decision')) {
      setBusy(action.token)
      setError(null)
      try {
        const msg = await runPortalAction(action)
        setMessage(msg)
        onDone?.()
      } catch {
        setError('Could not complete action. Try the full review page.')
      } finally {
        setBusy(null)
      }
      return
    }
    if (action.kind === 'auto_key_booking_confirm') {
      setBusy(action.token)
      setError(null)
      try {
        const msg = await runPortalAction(action)
        setMessage(msg)
        onDone?.()
      } catch {
        setError('Could not confirm booking.')
      } finally {
        setBusy(null)
      }
      return
    }
    if (action.kind === 'auto_key_invoice_checkout') {
      setBusy(action.token)
      setError(null)
      try {
        await runPortalAction(action)
      } catch {
        setError('Online payment is unavailable.')
        setBusy(null)
      }
      return
    }
  }

  const needsYou = actions.some((a) => a.kind !== 'job_receipt' && a.kind !== 'auto_key_invoice_receipt')

  return (
    <div className="pt-job-section">
      <div className={needsYou ? 'pt-callout' : 'pt-callout pt-callout--note'}>
        <BellRing size={17} className="pt-callout-icon" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: 13.5, fontWeight: 700, margin: 0 }}>
            {needsYou ? 'Waiting on you' : 'Paperwork'}
          </p>
          <p className="pt-muted" style={{ fontSize: 12.5, margin: '2px 0 0' }}>
            {needsYou ? 'A quick decision keeps your repair moving.' : 'Your receipt is ready to view.'}
          </p>
          {message && <p className="pt-flash pt-flash--ok" style={{ marginTop: 8 }}><Check size={13} /> {message}</p>}
          {error && <p className="pt-flash pt-flash--err" style={{ marginTop: 8 }}>{error}</p>}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
            {actions.map((action) => {
              const isDeclineOnlyQuick =
                action.kind === 'watch_quote_decision'
                || action.kind === 'shoe_quote_decision'
                || action.kind === 'auto_key_quote_decision'
              return (
                <div key={`${action.kind}-${action.token}`} style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  <Link to={action.url} className="pt-btn pt-btn--sm">
                    {actionLabel(action.kind)}
                  </Link>
                  {isDeclineOnlyQuick && (
                    <button
                      type="button"
                      disabled={busy === action.token}
                      onClick={() => handleQuick(action)}
                      className="pt-btn-ghost"
                    >
                      {busy === action.token ? <Loader2 size={12} className="animate-spin" /> : 'Decline'}
                    </button>
                  )}
                  {action.kind === 'auto_key_booking_confirm' && (
                    <button
                      type="button"
                      disabled={busy === action.token}
                      onClick={() => handleQuick(action)}
                      className="pt-btn pt-btn--sm"
                    >
                      {busy === action.token ? 'Confirming…' : 'Confirm now'}
                    </button>
                  )}
                  {action.kind === 'auto_key_invoice_checkout' && (
                    <button
                      type="button"
                      disabled={busy === action.token}
                      onClick={() => handleQuick(action)}
                      className="pt-btn pt-btn--sm"
                    >
                      {busy === action.token ? 'Starting…' : 'Pay online'}
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

function MessageToShop({
  sessionToken,
  job,
}: {
  sessionToken: string
  job: CustomerPortalJob
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [sent, setSent] = useState(false)
  const [sending, setSending] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function send() {
    const body = text.trim()
    if (!body) return
    setErr(null)
    setSending(true)
    try {
      const jobType =
        job.type === 'watch' ? 'repair_job' : job.type === 'shoe' ? 'shoe_repair_job' : 'auto_key_job'
      await portalMessageToShop(sessionToken, { job_type: jobType, job_id: job.id, message: body })
      setSent(true)
      setText('')
      setOpen(false)
    } catch {
      setErr('Could not send message.')
    } finally {
      setSending(false)
    }
  }

  if (!open) {
    return (
      <div className="pt-job-section" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {sent ? (
          <span className="pt-flash pt-flash--ok"><Check size={13} /> Message sent — the shop will be in touch.</span>
        ) : (
          <span className="pt-muted" style={{ fontSize: 12.5 }}>Questions?</span>
        )}
        <button type="button" className="pt-link" onClick={() => { setOpen(true); setSent(false) }}>
          <MessageCircle size={14} /> {sent ? 'Send another' : 'Message the shop'}
        </button>
      </div>
    )
  }

  return (
    <div className="pt-job-section pt-rise">
      <label className="pt-field">
        <span>Message the shop</span>
        <textarea
          rows={3}
          autoFocus
          value={text}
          onChange={e => setText(e.target.value)}
          className="pt-input"
          style={{ fontSize: 14 }}
          placeholder="Ask a question about this repair…"
        />
      </label>
      <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
        <button
          type="button"
          onClick={() => void send()}
          disabled={sending || !text.trim()}
          className="pt-btn pt-btn--sm"
        >
          {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          Send message
        </button>
        <button type="button" className="pt-btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
      </div>
      {err && <p className="pt-flash pt-flash--err" style={{ marginTop: 8 }}>{err}</p>}
    </div>
  )
}

export function CustomerPortalJobCard({
  job,
  shop,
  sessionToken,
  onRefresh,
  linkToDetail = true,
  index = 0,
}: {
  job: CustomerPortalJob
  shop: CustomerPortalShop
  sessionToken?: string | null
  onRefresh?: () => void
  /** False on the job's own detail page, where the card shouldn't link to itself. */
  linkToDetail?: boolean
  /** Position in the list, for a staggered entrance. */
  index?: number
}) {
  const Icon = jobIcon(job.type)
  const stage = portalJobStage(job.type, job.status)
  const label = portalJobStatusLabel(job.type, job.status)
  const detailPath = `/customer-portal/job/${job.type}/${job.status_token}`
  const actions = job.pending_actions ?? []

  const head = (
    <>
      <StageRing stage={stage} size={64}>
        <Icon size={20} strokeWidth={1.75} />
      </StageRing>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="pt-type">{jobTypeLabel(job.type)}</span>
          <span className="pt-mono pt-muted">#{job.job_number}</span>
        </div>
        <h3 className="pt-job-title">{job.title}</h3>
        <div className="pt-job-meta">
          <StatusPill stage={stage} label={label} />
          <span>
            {job.detail ? `${job.detail} · ` : ''}Since {formatDateShort(job.created_at)}
          </span>
        </div>
      </div>
      {linkToDetail ? (
        <span className="pt-chev" aria-hidden="true"><ChevronRight size={16} /></span>
      ) : <span />}
    </>
  )

  return (
    <article
      className={clsx('pt-card pt-job', stage === 'ready' && 'pt-job--ready')}
      style={{ ...portalAccentStyle(shop.brand_color), animationDelay: `${Math.min(index, 8) * 70}ms` }}
    >
      {linkToDetail ? (
        <Link to={detailPath} className="pt-job-head" aria-label={`${job.title} — ${label}. View details`}>
          {head}
        </Link>
      ) : (
        <div className="pt-job-head">{head}</div>
      )}
      <div style={{ padding: '2px 18px 18px' }}>
        <StageStepper stage={stage} />
      </div>
      {stage === 'ready' && (
        <div className="pt-job-section" style={{ fontSize: 13, color: 'var(--pt-text-mid)', display: 'flex', gap: 8, alignItems: 'center' }}>
          <Sparkles size={15} style={{ color: 'var(--pt-brass)', flexShrink: 0 }} />
          {job.type === 'auto_key'
            ? 'All done — your keys are ready.'
            : `All done — ready to collect from ${shop.shop_name.replace(/\.$/, '')}.`}
        </div>
      )}
      <PendingActions actions={actions} onDone={onRefresh} />
      {sessionToken && <MessageToShop sessionToken={sessionToken} job={job} />}
    </article>
  )
}

export function PortalEmptyState({ shop }: { shop?: CustomerPortalShop | null }) {
  const phone = shop?.shop_phone?.trim()
  const email = shop?.shop_email?.trim()
  return (
    <div className="pt-card pt-card-pad pt-rise" style={{ textAlign: 'center', padding: '36px 24px' }}>
      <div style={{ display: 'inline-block', marginBottom: 14 }}>
        <StageRing stage="received" size={72}>
          <Wrench size={22} strokeWidth={1.5} />
        </StageRing>
      </div>
      <p className="pt-serif" style={{ fontSize: 26, margin: 0 }}>Nothing on the bench</p>
      <p className="pt-muted" style={{ fontSize: 14, margin: '6px auto 0', maxWidth: 320 }}>
        Book a drop-off with your shop or get in touch to start a repair.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8, marginTop: 18 }}>
        {phone && (
          <a href={`tel:${phone}`} className="pt-btn pt-btn--sm">
            <Phone size={13} /> Call shop
          </a>
        )}
        {email && (
          <a href={`mailto:${email}`} className="pt-btn-ghost">
            <Mail size={13} /> Email shop
          </a>
        )}
        {!phone && !email && (
          <p className="pt-muted" style={{ fontSize: 13 }}>
            Contact the shop where you dropped off your item.
          </p>
        )}
      </div>
    </div>
  )
}
