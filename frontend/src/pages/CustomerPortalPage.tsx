import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Watch, Footprints, KeyRound, ArrowRight, Search, Link2, Copy, Check, History, Sparkles } from 'lucide-react'
import {
  customerPortalLookup,
  createPortalSession,
  getPortalSession,
  type CustomerPortalJob,
  type CustomerPortalLookupResponse,
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

function JobCard({ job, accent }: { job: CustomerPortalJob; accent?: string | null }) {
  const Icon = jobIcon(job.type)
  const stage = portalJobStage(job.type, job.status)
  const label = portalJobStatusLabel(job.type, job.status)

  return (
    <Link
      to={job.status_url}
      className="flex items-start gap-4 p-4 rounded-xl transition-opacity active:opacity-70"
      style={{
        backgroundColor: 'var(--ms-surface)',
        border: `1px solid ${accent ? `${accent}33` : 'var(--ms-border)'}`,
        textDecoration: 'none',
      }}
    >
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
  )
}

function ShopSection({ shop }: { shop: CustomerPortalShop }) {
  const accent = shop.brand_color?.trim() || null
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-3">
        {shop.logo_url ? (
          <img
            src={shop.logo_url}
            alt=""
            className="w-10 h-10 rounded-lg object-contain shrink-0"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
          />
        ) : (
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 text-sm font-bold"
            style={{
              backgroundColor: accent ? `${accent}18` : 'var(--ms-surface)',
              color: accent || 'var(--ms-accent)',
              border: `1px solid ${accent ? `${accent}44` : 'var(--ms-border)'}`,
            }}
          >
            {shop.shop_name.charAt(0).toUpperCase()}
          </div>
        )}
        <div className="min-w-0">
          <h2 className="text-base font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{shop.shop_name}</h2>
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            {shop.jobs.length} repair{shop.jobs.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {shop.jobs.map((job) => (
          <JobCard key={`${job.type}-${job.job_number}`} job={job} accent={accent} />
        ))}
      </div>
    </section>
  )
}

function ViewToggle({ mode, onChange }: { mode: 'active' | 'history'; onChange: (m: 'active' | 'history') => void }) {
  return (
    <div
      className="flex rounded-xl p-1 gap-1"
      style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
    >
      {(['active', 'history'] as const).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-colors"
          style={{
            backgroundColor: mode === m ? 'var(--ms-accent)' : 'transparent',
            color: mode === m ? '#fff' : 'var(--ms-text-muted)',
          }}
        >
          {m === 'history' ? <History size={13} /> : <Sparkles size={13} />}
          {m === 'active' ? 'Active' : 'History'}
        </button>
      ))}
    </div>
  )
}

function BookmarkBanner({ sessionToken, emailSent }: { email: string; sessionToken: string; emailSent?: boolean }) {
  const [copied, setCopied] = useState(false)
  const url = `${window.location.origin}/customer-portal/s/${sessionToken}`

  function copy() {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
      <div className="flex items-start gap-3">
        <Link2 size={18} style={{ color: 'var(--ms-accent)', flexShrink: 0, marginTop: 2 }} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Bookmark this page</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
            {emailSent !== false
              ? 'We emailed you this link — valid for 30 days. You can also copy it below.'
              : 'Save this link to check your repairs any time — valid for 30 days.'}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs truncate flex-1 font-mono" style={{ color: 'var(--ms-text-mid)' }}>{url}</span>
            <button
              type="button"
              onClick={copy}
              className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-lg shrink-0"
              style={{
                backgroundColor: copied ? 'rgba(31,109,76,0.12)' : 'var(--ms-bg)',
                color: copied ? '#1F6D4C' : 'var(--ms-accent)',
                border: '1px solid var(--ms-border-strong)',
              }}
            >
              {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function PortalResults({
  data,
  email,
  sessionToken,
  viewMode,
  onViewModeChange,
  loading,
}: {
  data: CustomerPortalLookupResponse
  email: string
  sessionToken?: string | null
  viewMode: 'active' | 'history'
  onViewModeChange: (m: 'active' | 'history') => void
  loading?: boolean
}) {
  const totalJobs = data.shops.reduce((n, s) => n + s.jobs.length, 0)

  return (
    <div className="space-y-5">
      <ViewToggle mode={viewMode} onChange={onViewModeChange} />

      {loading && (
        <p className="text-center text-sm" style={{ color: 'var(--ms-text-muted)' }}>Updating…</p>
      )}

      {totalJobs === 0 ? (
        <div
          className="rounded-xl p-6 text-center space-y-2"
          style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
        >
          <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
            {viewMode === 'active' ? 'No active repairs' : 'No past repairs'}
          </p>
          <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
            {viewMode === 'active'
              ? 'When you drop off a repair, it will appear here.'
              : 'Completed and collected jobs will show in history.'}
          </p>
        </div>
      ) : (
        data.shops.map((shop) => <ShopSection key={shop.tenant_id} shop={shop} />)
      )}

      {sessionToken && viewMode === 'active' && totalJobs > 0 && (
        <BookmarkBanner email={email} sessionToken={sessionToken} />
      )}
    </div>
  )
}

function PortalShell({ children, subtitle }: { children: React.ReactNode; subtitle?: string }) {
  return (
    <div className="min-h-screen py-10 px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-1" style={{ color: 'var(--ms-text)' }}>My Repairs</h1>
          {subtitle && <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>{subtitle}</p>}
        </div>
        {children}
      </div>
    </div>
  )
}

function SessionView({ token }: { token: string }) {
  const [data, setData] = useState<CustomerPortalLookupResponse | null>(null)
  const [viewMode, setViewMode] = useState<'active' | 'history'>('active')
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
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="max-w-md text-center space-y-3">
          <p className="text-lg font-semibold" style={{ color: 'var(--ms-text)' }}>Link expired</p>
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>{error}</p>
          <Link to="/customer-portal" className="text-sm font-medium" style={{ color: 'var(--ms-accent)' }}>
            Enter your email again →
          </Link>
        </div>
      </div>
    )
  }

  if (data === null) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Loading your repairs…</p>
      </div>
    )
  }

  return (
    <PortalShell subtitle={data.email}>
      <PortalResults
        data={data}
        email={data.email || ''}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        loading={loading}
      />
    </PortalShell>
  )
}

function CustomerPortalLookupPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<CustomerPortalLookupResponse | null>(null)
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'active' | 'history'>('active')
  const [refreshing, setRefreshing] = useState(false)

  async function fetchJobs(targetEmail: string, history: boolean) {
    const res = await customerPortalLookup(targetEmail, history)
    setData(res.data)
    return res.data
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setData(null)
    setSessionToken(null)
    const trimmed = email.trim()
    if (!trimmed) return
    setLoading(true)
    try {
      const result = await fetchJobs(trimmed, viewMode === 'history')
      if (viewMode === 'active' && result.shops.some((s) => s.jobs.length > 0)) {
        createPortalSession(trimmed)
          .then((r) => setSessionToken(r.data.session_token))
          .catch(() => { /* session optional */ })
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleViewChange(mode: 'active' | 'history') {
    setViewMode(mode)
    if (!email.trim() || data === null) return
    setRefreshing(true)
    try {
      await fetchJobs(email.trim(), mode === 'history')
    } catch {
      /* keep prior data */
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="min-h-screen py-10 px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--ms-text)' }}>
            Track Your Repairs
          </h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>
            Enter your email to see repairs across every shop you use.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            required
            className="w-full px-4 py-3 rounded-xl text-sm"
            style={{
              backgroundColor: 'var(--ms-surface)',
              border: '1px solid var(--ms-border-strong)',
              color: 'var(--ms-text)',
              outline: 'none',
            }}
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold transition-opacity"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#fff', opacity: loading ? 0.7 : 1 }}
          >
            <Search size={15} />
            {loading ? 'Looking up…' : 'Find my repairs'}
          </button>
        </form>

        {error && <p className="text-sm text-center" style={{ color: '#C96A5A' }}>{error}</p>}

        {data !== null && (
          <PortalResults
            data={data}
            email={email.trim()}
            sessionToken={sessionToken}
            viewMode={viewMode}
            onViewModeChange={handleViewChange}
            loading={refreshing}
          />
        )}
      </div>
    </div>
  )
}

export default function CustomerPortalPage() {
  const { token } = useParams<{ token?: string }>()
  if (token) return <SessionView token={token} />
  return <CustomerPortalLookupPage />
}
