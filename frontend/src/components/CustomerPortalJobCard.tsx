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
import {
  portalJobStage,
  portalJobStatusLabel,
  portalStageIndex,
  portalStageLabel,
  STAGE_ORDER,
  type PortalStage,
} from '@/lib/portalStatus'
import { Watch, Footprints, KeyRound, ArrowRight, Loader2 } from 'lucide-react'

function formatDateShort(s: string) {
  return new Date(s).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

function jobIcon(type: CustomerPortalJob['type']) {
  if (type === 'shoe') return Footprints
  if (type === 'auto_key') return KeyRound
  return Watch
}

function StageTrack({ stage }: { stage: PortalStage }) {
  const activeIdx = portalStageIndex(stage)
  return (
    <div className="flex items-center gap-1 mt-2">
      {STAGE_ORDER.map((s, idx) => (
        <div key={s} className="flex items-center gap-1 flex-1 min-w-0">
          <div
            className="h-1.5 flex-1 rounded-full"
            style={{
              backgroundColor: idx <= activeIdx ? 'var(--ms-accent)' : 'var(--ms-border)',
              opacity: idx <= activeIdx ? 1 : 0.55,
            }}
            title={portalStageLabel(s)}
          />
        </div>
      ))}
    </div>
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
  accent,
  onDone,
}: {
  actions: CustomerPortalPendingAction[]
  accent?: string | null
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

  return (
    <div className="mt-3 pt-3 space-y-2" style={{ borderTop: '1px solid var(--ms-border)' }}>
      {message && <p className="text-xs font-medium" style={{ color: '#1F6D4C' }}>{message}</p>}
      {error && <p className="text-xs" style={{ color: '#C96A5A' }}>{error}</p>}
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => {
          const isDeclineOnlyQuick =
            action.kind === 'watch_quote_decision'
            || action.kind === 'shoe_quote_decision'
            || action.kind === 'auto_key_quote_decision'
          return (
            <div key={`${action.kind}-${action.token}`} className="flex gap-2">
              <Link
                to={action.url}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                style={{
                  backgroundColor: accent || 'var(--ms-accent)',
                  color: '#fff',
                  textDecoration: 'none',
                }}
              >
                {actionLabel(action.kind)}
              </Link>
              {isDeclineOnlyQuick && (
                <button
                  type="button"
                  disabled={busy === action.token}
                  onClick={() => handleQuick(action)}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg"
                  style={{
                    border: '1px solid var(--ms-border-strong)',
                    color: 'var(--ms-text-muted)',
                    backgroundColor: 'var(--ms-bg)',
                  }}
                >
                  {busy === action.token ? <Loader2 size={12} className="animate-spin inline" /> : 'Decline'}
                </button>
              )}
              {action.kind === 'auto_key_booking_confirm' && (
                <button
                  type="button"
                  disabled={busy === action.token}
                  onClick={() => handleQuick(action)}
                  className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                  style={{ backgroundColor: accent || 'var(--ms-accent)', color: '#fff' }}
                >
                  {busy === action.token ? 'Confirming…' : 'Confirm now'}
                </button>
              )}
              {action.kind === 'auto_key_invoice_checkout' && (
                <button
                  type="button"
                  disabled={busy === action.token}
                  onClick={() => handleQuick(action)}
                  className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                  style={{ backgroundColor: accent || 'var(--ms-accent)', color: '#fff' }}
                >
                  {busy === action.token ? 'Starting…' : 'Pay online'}
                </button>
              )}
            </div>
          )
        })}
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
  const [text, setText] = useState('')
  const [sent, setSent] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function send() {
    const body = text.trim()
    if (!body) return
    setErr(null)
    try {
      const jobType =
        job.type === 'watch' ? 'repair_job' : job.type === 'shoe' ? 'shoe_repair_job' : 'auto_key_job'
      await portalMessageToShop(sessionToken, { job_type: jobType, job_id: job.id, message: body })
      setSent(true)
      setText('')
    } catch {
      setErr('Could not send message.')
    }
  }

  return (
    <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--ms-border)' }}>
      <p className="text-xs font-medium mb-1" style={{ color: 'var(--ms-text-muted)' }}>Message the shop</p>
      <textarea
        rows={2}
        value={text}
        onChange={e => setText(e.target.value)}
        className="w-full text-xs rounded-lg px-2 py-1.5 outline-none resize-y"
        style={{ border: '1px solid var(--ms-border-strong)', backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
        placeholder="Ask a question about this repair…"
      />
      <button
        type="button"
        onClick={() => void send()}
        className="mt-1 text-xs font-semibold px-3 py-1 rounded-lg"
        style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
      >
        Send message
      </button>
      {sent && <p className="text-xs mt-1" style={{ color: '#1F6D4C' }}>Message sent.</p>}
      {err && <p className="text-xs mt-1" style={{ color: '#C96A5A' }}>{err}</p>}
    </div>
  )
}

export function CustomerPortalJobCard({
  job,
  shop,
  sessionToken,
  onRefresh,
}: {
  job: CustomerPortalJob
  shop: CustomerPortalShop
  sessionToken?: string | null
  onRefresh?: () => void
}) {
  const Icon = jobIcon(job.type)
  const stage = portalJobStage(job.type, job.status)
  const label = portalJobStatusLabel(job.type, job.status)
  const accent = shop.brand_color?.trim() || null
  const detailPath = `/customer-portal/job/${job.type}/${job.status_token}`
  const actions = job.pending_actions ?? []

  return (
    <div
      className="p-4 rounded-xl"
      style={{
        backgroundColor: 'var(--ms-surface)',
        border: `1px solid ${accent ? `${accent}33` : 'var(--ms-border)'}`,
      }}
    >
      <Link to={detailPath} className="flex items-start gap-4" style={{ textDecoration: 'none' }}>
        <div
          className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: accent ? `${accent}18` : '#EEE6DA' }}
        >
          <Icon size={18} style={{ color: accent || 'var(--ms-accent-hover)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
            #{job.job_number}{job.detail ? ` · ${job.detail}` : ''} · {formatDateShort(job.created_at)}
          </p>
          <p className="text-xs mt-1 font-medium" style={{ color: accent || 'var(--ms-accent)' }}>
            {label}
            <span style={{ color: 'var(--ms-text-muted)', fontWeight: 400 }}> · {portalStageLabel(stage)}</span>
          </p>
          <StageTrack stage={stage} />
        </div>
        <ArrowRight size={16} style={{ color: 'var(--ms-text-muted)', flexShrink: 0, marginTop: 4 }} />
      </Link>
      <PendingActions actions={actions} accent={accent} onDone={onRefresh} />
      {sessionToken && <MessageToShop sessionToken={sessionToken} job={job} />}
    </div>
  )
}

export function PortalEmptyState({ shop }: { shop?: CustomerPortalShop | null }) {
  const phone = shop?.shop_phone?.trim()
  const email = shop?.shop_email?.trim()
  return (
    <div
      className="rounded-xl p-6 text-center space-y-3"
      style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
    >
      <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>No repairs here yet</p>
      <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
        Book a drop-off with your shop or get in touch to start a repair.
      </p>
      <div className="flex flex-wrap justify-center gap-2 pt-1">
        {phone && (
          <a
            href={`tel:${phone}`}
            className="text-xs font-semibold px-4 py-2 rounded-lg"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', textDecoration: 'none' }}
          >
            Call shop
          </a>
        )}
        {email && (
          <a
            href={`mailto:${email}`}
            className="text-xs font-semibold px-4 py-2 rounded-lg"
            style={{
              border: '1px solid var(--ms-border-strong)',
              color: 'var(--ms-text)',
              textDecoration: 'none',
              backgroundColor: 'var(--ms-bg)',
            }}
          >
            Email shop
          </a>
        )}
        {!phone && !email && (
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            Contact the shop where you dropped off your item.
          </p>
        )}
      </div>
    </div>
  )
}
