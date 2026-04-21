import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Watch, Footprints, ArrowRight, Search, Link2, Copy, Check } from 'lucide-react'
import { customerPortalLookup, createPortalSession, getPortalSession, type CustomerPortalJob } from '@/lib/api'

function readableStatus(status: string) {
  return status.replace(/_/g, ' ')
}

function formatDateShort(s: string) {
  return new Date(s).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

function JobList({ jobs }: { jobs: CustomerPortalJob[] }) {
  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: 'var(--ms-text-muted)' }}>
        {jobs.length} repair{jobs.length !== 1 ? 's' : ''} found
      </p>
      {jobs.map((job, idx) => (
        <Link
          key={`${job.job_number}-${idx}`}
          to={job.status_url}
          className="flex items-center gap-4 p-4 rounded-xl transition-opacity active:opacity-70"
          style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', textDecoration: 'none' }}
        >
          <div className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: '#EEE6DA' }}>
            {job.type === 'shoe'
              ? <Footprints size={18} style={{ color: 'var(--ms-accent-hover)' }} />
              : <Watch size={18} style={{ color: 'var(--ms-accent-hover)' }} />
            }
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold truncate" style={{ color: 'var(--ms-text)' }}>{job.title}</p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
              #{job.job_number}{job.detail ? ` · ${job.detail}` : ''} · {formatDateShort(job.created_at)}
            </p>
            <p className="text-xs mt-0.5 capitalize font-medium" style={{ color: 'var(--ms-accent)' }}>
              {readableStatus(job.status)}
            </p>
          </div>
          <ArrowRight size={16} style={{ color: 'var(--ms-text-muted)', flexShrink: 0 }} />
        </Link>
      ))}
    </div>
  )
}

function BookmarkBanner({ sessionToken }: { email: string; sessionToken: string }) {
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
            Save this link to check your repairs any time — valid for 30 days.
          </p>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-xs truncate flex-1 font-mono" style={{ color: 'var(--ms-text-mid)' }}>{url}</span>
            <button
              type="button"
              onClick={copy}
              className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-lg shrink-0"
              style={{ backgroundColor: copied ? 'rgba(31,109,76,0.12)' : 'var(--ms-bg)', color: copied ? '#1F6D4C' : 'var(--ms-accent)', border: '1px solid var(--ms-border-strong)' }}
            >
              {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Session view (token from URL) ─────────────────────────────────────────────
function SessionView({ token }: { token: string }) {
  const [jobs, setJobs] = useState<CustomerPortalJob[] | null>(null)
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPortalSession(token)
      .then(r => { setJobs(r.data.jobs); setEmail(r.data.email) })
      .catch(err => {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setError(detail || 'This portal link is invalid or has expired.')
      })
  }, [token])

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

  if (jobs === null) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Loading your repairs…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-10 px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-5">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-1" style={{ color: 'var(--ms-text)' }}>My Repairs</h1>
          <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>{email}</p>
        </div>
        {jobs.length === 0 ? (
          <p className="text-center text-sm" style={{ color: 'var(--ms-text-muted)' }}>No active repairs found.</p>
        ) : (
          <JobList jobs={jobs} />
        )}
      </div>
    </div>
  )
}

// ── Email lookup view ─────────────────────────────────────────────────────────
export default function CustomerPortalPage() {
  const { token } = useParams<{ token?: string }>()

  // If a session token is in the URL, show session view
  if (token) return <SessionView token={token} />

  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [jobs, setJobs] = useState<CustomerPortalJob[] | null>(null)
  const [sessionToken, setSessionToken] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setJobs(null)
    setSessionToken(null)
    if (!email.trim()) return
    setLoading(true)
    try {
      const res = await customerPortalLookup(email.trim())
      setJobs(res.data.jobs)
      // Create a bookmarkable session in the background
      createPortalSession(email.trim())
        .then(r => setSessionToken(r.data.session_token))
        .catch(() => {/* silent — session is optional */})
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen py-10 px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="max-w-lg mx-auto space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--ms-text)' }}>
            Track Your Repairs
          </h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>Enter your email to see all your active repairs.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="your@email.com"
            required
            className="w-full px-4 py-3 rounded-xl text-sm"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)', outline: 'none' }}
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

        {jobs !== null && (
          <div className="space-y-4">
            {jobs.length === 0 ? (
              <p className="text-center text-sm" style={{ color: 'var(--ms-text-muted)' }}>
                No active repairs found for this email address.
              </p>
            ) : (
              <JobList jobs={jobs} />
            )}
            {sessionToken && <BookmarkBanner email={email} sessionToken={sessionToken} />}
          </div>
        )}
      </div>
    </div>
  )
}
