import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowRight,
  Bell,
  Bookmark,
  Check,
  Copy,
  History,
  Loader2,
  Mail,
  Phone,
  Ticket,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import {
  getPortalSession,
  patchPortalNotificationPrefs,
  requestPortalCode,
  verifyPortalCode,
  type CustomerPortalLookupResponse,
  type CustomerPortalShop,
} from '@/lib/api'
import { portalJobStage } from '@/lib/portalStatus'
import { CustomerPortalJobCard, PortalEmptyState } from '@/components/CustomerPortalJobCard'
import {
  MinitLogoPlate,
  PortalBody,
  PortalHero,
  PortalLoading,
  PortalPage,
  Segmented,
  Switch,
} from '@/components/portal/PortalChrome'
import { greeting, minitBranchName } from '@/components/portal/portalUtils'

type ViewMode = 'active' | 'history'

function BookmarkBanner({ sessionToken }: { sessionToken: string }) {
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/customer-portal/s/${sessionToken}`

  function copy() {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  return (
    <div className="pt-card pt-card-pad" style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
      <span
        style={{
          width: 38, height: 38, borderRadius: 12, display: 'grid', placeItems: 'center', flexShrink: 0,
          background: 'color-mix(in srgb, var(--pt-brass) 14%, transparent)', color: 'var(--pt-brass)',
        }}
      >
        <Bookmark size={17} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 14, fontWeight: 700, margin: 0 }}>Keep this page handy</p>
        <p className="pt-muted" style={{ fontSize: 13, margin: '3px 0 0' }}>
          We emailed you this link — it works for 30 days. Bookmark it or copy it below.
        </p>
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, padding: '6px 6px 6px 12px',
            borderRadius: 12, background: 'var(--pt-card-alt)', border: '1px solid var(--pt-line)',
          }}
        >
          <span className="pt-mono pt-muted" style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {url}
          </span>
          <button type="button" onClick={copy} className={copied ? 'pt-btn pt-btn--sm' : 'pt-btn-ghost'} style={{ flexShrink: 0 }}>
            {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
          </button>
        </div>
      </div>
    </div>
  )
}

function ShopSection({
  shop,
  sessionToken,
  onRefresh,
  showHeader,
  startIndex,
}: {
  shop: CustomerPortalShop
  sessionToken?: string | null
  onRefresh?: () => void
  showHeader: boolean
  startIndex: number
}) {
  const jobs = shop.jobs ?? []
  const phone = shop.shop_phone?.trim()
  const email = shop.shop_email?.trim()
  return (
    <section className="pt-stack" aria-label={shop.shop_name}>
      {showHeader && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 4px 0' }}>
          {shop.is_minit ? (
            <MinitLogoPlate small />
          ) : shop.logo_url ? (
            <img
              src={shop.logo_url}
              alt=""
              style={{ width: 40, height: 40, borderRadius: 12, objectFit: 'contain', background: 'var(--pt-card)', border: '1px solid var(--pt-line)', flexShrink: 0 }}
            />
          ) : (
            <span
              className="pt-serif"
              style={{
                width: 40, height: 40, borderRadius: 12, display: 'grid', placeItems: 'center', flexShrink: 0, fontSize: 20,
                background: 'var(--pt-ink)', color: '#D9BD8C',
              }}
            >
              {shop.shop_name.charAt(0).toUpperCase()}
            </span>
          )}
          <div style={{ minWidth: 0, flex: 1 }}>
            <h2 className="pt-serif" style={{ fontSize: 22, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {(shop.is_minit && minitBranchName(shop.shop_name)) || shop.shop_name}
            </h2>
            <p className="pt-label" style={{ margin: '2px 0 0' }}>
              {jobs.length} repair{jobs.length !== 1 ? 's' : ''}
            </p>
          </div>
          {phone && (
            <a href={`tel:${phone}`} className="pt-btn-ghost" aria-label={`Call ${shop.shop_name}`} style={{ padding: 9 }}>
              <Phone size={14} />
            </a>
          )}
          {email && (
            <a href={`mailto:${email}`} className="pt-btn-ghost" aria-label={`Email ${shop.shop_name}`} style={{ padding: 9 }}>
              <Mail size={14} />
            </a>
          )}
        </div>
      )}
      {jobs.length === 0 ? (
        <PortalEmptyState shop={shop} />
      ) : (
        jobs.map((job, i) => (
          <CustomerPortalJobCard
            key={`${job.type}-${job.job_number}`}
            job={job}
            shop={shop}
            sessionToken={sessionToken}
            onRefresh={onRefresh}
            index={startIndex + i}
          />
        ))
      )}
    </section>
  )
}

function PortalNotifyPrefs({
  sessionToken,
  initialEmail,
  initialSms,
}: {
  sessionToken: string
  initialEmail?: boolean
  initialSms?: boolean
}) {
  const [emailOn, setEmailOn] = useState(initialEmail ?? false)
  const [smsOn, setSmsOn] = useState(initialSms ?? false)

  useEffect(() => {
    setEmailOn(initialEmail ?? false)
    setSmsOn(initialSms ?? false)
  }, [initialEmail, initialSms, sessionToken])

  function save(patch: { status_notify_email?: boolean; status_notify_sms?: boolean }) {
    void patchPortalNotificationPrefs(sessionToken, patch)
  }

  return (
    <div className="pt-card pt-card-pad">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Bell size={15} style={{ color: 'var(--pt-brass)' }} />
        <p className="pt-label" style={{ margin: 0 }}>Keep me posted</p>
      </div>
      <div className="pt-switch-row">
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Email updates</p>
          <p className="pt-muted" style={{ fontSize: 12.5, margin: '2px 0 0' }}>When a repair moves to its next stage</p>
        </div>
        <Switch
          label="Email me when job status changes"
          checked={emailOn}
          onChange={(v) => { setEmailOn(v); save({ status_notify_email: v }) }}
        />
      </div>
      <div className="pt-switch-row">
        <div>
          <p style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Text messages</p>
          <p className="pt-muted" style={{ fontSize: 12.5, margin: '2px 0 0' }}>An SMS for the same updates</p>
        </div>
        <Switch
          label="SMS me when job status changes"
          checked={smsOn}
          onChange={(v) => { setSmsOn(v); save({ status_notify_sms: v }) }}
        />
      </div>
    </div>
  )
}

function summarize(data: CustomerPortalLookupResponse) {
  let workshop = 0
  let ready = 0
  let waiting = 0
  let total = 0
  for (const shop of data.shops ?? []) {
    for (const job of shop.jobs ?? []) {
      total += 1
      const stage = portalJobStage(job.type, job.status)
      if (stage === 'ready') ready += 1
      else if (stage === 'in_progress' || stage === 'received') workshop += 1
      if ((job.pending_actions ?? []).some((a) => a.kind !== 'job_receipt' && a.kind !== 'auto_key_invoice_receipt')) {
        waiting += 1
      }
    }
  }
  return { workshop, ready, waiting, total }
}

function headline(s: ReturnType<typeof summarize>, mode: ViewMode) {
  if (mode === 'history') return <>Every repair, <em>on record.</em></>
  if (s.waiting > 0) return <>We need a quick <em>yes</em> from you.</>
  if (s.ready > 0) return <>Something’s <em>ready</em> for you.</>
  if (s.total > 0) return <>Your repairs, <em>in good hands.</em></>
  return <>All quiet <em>on the bench.</em></>
}

function SessionView({ token }: { token: string }) {
  const [data, setData] = useState<CustomerPortalLookupResponse | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('active')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    getPortalSession(token, viewMode === 'history')
      .then((r) => { setData(r.data); setError(null) })
      .catch((err) => {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setError(detail || 'This portal link is invalid or has expired.')
      })
      .finally(() => setLoading(false))
  }, [token, viewMode])

  useEffect(() => { load() }, [load])

  if (error) {
    return (
      <PortalPage>
        <PortalHero
          eyebrow="Link expired"
          title={<>This link has <em>run its course.</em></>}
          lede={error}
        >
          <div style={{ marginTop: 24 }}>
            <Link to="/customer-portal" className="pt-btn">
              Send me a fresh link <ArrowRight size={15} />
            </Link>
          </div>
        </PortalHero>
      </PortalPage>
    )
  }

  if (data === null) return <PortalLoading label="Gathering your repairs…" />

  const shops = data.shops ?? []
  const summary = summarize(data)
  const onlyShop = shops.length === 1 ? shops[0] : null
  // One brand across the top: the shop's when there's one, Mister Minit's when
  // every shop is in the Minit network.
  const minit = shops.length > 0 && shops.every((s) => s.is_minit)
  let running = 0

  return (
    <PortalPage accent={onlyShop?.brand_color} minit={minit}>
      <PortalHero
        brand={{ name: onlyShop?.shop_name, logoUrl: onlyShop?.logo_url, minit }}
        barRight={
          <button
            type="button"
            className="pt-btn-ghost pt-btn-ghost--on-ink"
            onClick={load}
            disabled={loading}
            aria-label="Refresh"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        }
        eyebrow={greeting()}
        title={headline(summary, viewMode)}
        lede={data.email ? <>Signed in as <span style={{ color: 'var(--pt-on-ink)' }}>{data.email}</span></> : undefined}
      >
        {viewMode === 'active' && summary.total > 0 && (
          <div className="pt-stats pt-rise" style={{ animationDelay: '0.2s' }}>
            {summary.workshop > 0 && (
              <span className="pt-stat">
                <span className="pt-stat-dot" style={{ color: 'var(--pt-accent)' }} />
                <b>{summary.workshop}</b> in the workshop
              </span>
            )}
            {summary.ready > 0 && (
              <span className="pt-stat">
                <Sparkles size={13} style={{ color: '#D9BD8C' }} />
                <b>{summary.ready}</b> ready to collect
              </span>
            )}
            {summary.waiting > 0 && (
              <span className="pt-stat">
                <span className="pt-stat-dot" style={{ color: '#E4B45E' }} />
                <b>{summary.waiting}</b> waiting on you
              </span>
            )}
          </div>
        )}
      </PortalHero>

      <PortalBody>
        <Segmented<ViewMode>
          label="Which repairs to show"
          value={viewMode}
          onChange={setViewMode}
          options={[
            { value: 'active', label: 'Current', icon: <Sparkles size={14} /> },
            { value: 'history', label: 'History', icon: <History size={14} /> },
          ]}
        />

        {summary.total === 0 ? (
          <PortalEmptyState shop={shops[0] ?? null} />
        ) : (
          shops.map((shop) => {
            const start = running
            running += (shop.jobs ?? []).length
            return (
              <ShopSection
                key={shop.tenant_id}
                shop={shop}
                sessionToken={token}
                onRefresh={load}
                showHeader={shops.length > 1 || !!shop.shop_phone || !!shop.shop_email}
                startIndex={start}
              />
            )
          })
        )}

        <PortalNotifyPrefs
          sessionToken={token}
          initialEmail={data.status_notify_email ?? undefined}
          initialSms={data.status_notify_sms ?? undefined}
        />
        {viewMode === 'active' && summary.total > 0 && <BookmarkBanner sessionToken={token} />}

        <PortalFooter />
      </PortalBody>
    </PortalPage>
  )
}

function PortalFooter() {
  return (
    <p className="pt-label" style={{ textAlign: 'center', paddingTop: 16, opacity: 0.8 }}>
      Powered by Mainspring
    </p>
  )
}

function CustomerPortalLookupPage() {
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [ticket, setTicket] = useState('')
  const [code, setCode] = useState('')
  const [challenge, setChallenge] = useState<{ id: string; minutes: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function errorMessage(err: unknown) {
    const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    return msg || 'Something went wrong. Please try again.'
  }

  // Step 1: the phone number and ticket number must belong to the same repair.
  // We always answer the same way, so nobody can use this to probe tickets.
  async function requestCode(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!phone.trim() || !ticket.trim()) return
    setLoading(true)
    try {
      const res = await requestPortalCode(phone.trim(), ticket.trim())
      setChallenge({ id: res.data.challenge_id, minutes: res.data.expires_minutes })
      setCode('')
    } catch (err: unknown) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Step 2: the code texted to that phone opens the tracker.
  async function submitCode(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!challenge || !code.trim()) return
    setLoading(true)
    try {
      const res = await verifyPortalCode(challenge.id, code.trim())
      navigate(`/customer-portal/s/${res.data.session_token}`)
    } catch (err: unknown) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <PortalPage>
      <PortalHero
        eyebrow="Repair tracking"
        title={<>Where’s my <em>repair?</em></>}
        lede={
          challenge
            ? 'Enter the 6-digit code we just texted you.'
            : 'Enter the phone number you gave us and the ticket number from your receipt or text message.'
        }
      />
      <PortalBody>
        {challenge ? (
          <form onSubmit={submitCode} className="pt-card pt-card-pad pt-rise" style={{ padding: 24 }}>
            <p className="pt-muted" style={{ fontSize: 13.5, margin: '0 0 14px', lineHeight: 1.55 }}>
              If that phone number and ticket match a repair, we’ve texted a code to the number on file. It expires in {challenge.minutes} minutes.
            </p>
            <label className="pt-field">
              <span>6-digit code</span>
              <input
                type="text"
                inputMode="numeric"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="123456"
                autoComplete="one-time-code"
                required
                className="pt-input"
              />
            </label>
            <button type="submit" disabled={loading} className="pt-btn pt-btn--block" style={{ marginTop: 14, padding: '13px 18px' }}>
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Ticket size={16} />}
              {loading ? 'Checking…' : 'Track my repair'}
            </button>
            {error && <p role="alert" className="pt-flash pt-flash--err" style={{ marginTop: 12, justifyContent: 'center', width: '100%' }}>{error}</p>}
            <button type="button" className="pt-link" style={{ marginTop: 14 }} onClick={() => { setChallenge(null); setError(null) }}>
              Start again
            </button>
          </form>
        ) : (
          <form onSubmit={requestCode} className="pt-card pt-card-pad pt-rise" style={{ padding: 24 }}>
            <label className="pt-field">
              <span>Phone number</span>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="0412 345 678"
                autoComplete="tel"
                required
                className="pt-input"
              />
            </label>
            <label className="pt-field" style={{ marginTop: 12 }}>
              <span>Ticket number</span>
              <input
                type="text"
                value={ticket}
                onChange={(e) => setTicket(e.target.value)}
                placeholder="e.g. 00142"
                autoComplete="off"
                autoCapitalize="characters"
                required
                className="pt-input"
              />
            </label>
            <button type="submit" disabled={loading} className="pt-btn pt-btn--block" style={{ marginTop: 14, padding: '13px 18px' }}>
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Ticket size={16} />}
              {loading ? 'Sending…' : 'Text me a code'}
            </button>
            {error && <p role="alert" className="pt-flash pt-flash--err" style={{ marginTop: 12, justifyContent: 'center', width: '100%' }}>{error}</p>}
            <p className="pt-muted" style={{ fontSize: 12.5, textAlign: 'center', margin: '14px 0 0' }}>
              No password needed. Can’t find your ticket number? It’s on your receipt and in our texts and emails.
            </p>
          </form>
        )}

        <div className="pt-rise" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, animationDelay: '0.15s' }}>
          {[
            { k: 'Live status', v: 'From bench to ready' },
            { k: 'Approve quotes', v: 'In one tap' },
            { k: 'Message the shop', v: 'Right from the job' },
          ].map((f) => (
            <div key={f.k} className="pt-card" style={{ padding: '14px 12px', textAlign: 'center' }}>
              <p style={{ fontSize: 13, fontWeight: 700, margin: 0 }}>{f.k}</p>
              <p className="pt-muted" style={{ fontSize: 11.5, margin: '3px 0 0' }}>{f.v}</p>
            </div>
          ))}
        </div>

        <PortalFooter />
      </PortalBody>
    </PortalPage>
  )
}

export default function CustomerPortalPage() {
  const { token } = useParams<{ token?: string }>()
  if (token) return <SessionView token={token} />
  return <CustomerPortalLookupPage />
}
