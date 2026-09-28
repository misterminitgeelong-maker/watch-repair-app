import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  CalendarDays,
  Car,
  CheckCircle2,
  ClipboardList,
  KeyRound,
  Loader2,
  LogOut,
  MessageSquareText,
  Star,
} from 'lucide-react'
import {
  portalLookup,
  portalVerify,
  portalGetProfile,
  portalBook,
  portalGetShop,
  type PortalProfile,
  type PortalShop,
} from '@/lib/api'
import {
  PortalBody,
  PortalHero,
  PortalLoading,
  PortalPage,
  Segmented,
} from '@/components/portal/PortalChrome'
import { greeting } from '@/components/portal/portalUtils'
import { clsx } from 'clsx'

const TIERS = [
  { name: 'Bronze', label: 'Fixer', min: 0 },
  { name: 'Silver', label: 'Regular', min: 500 },
  { name: 'Gold', label: 'Trusted', min: 1500 },
  { name: 'Platinum', label: 'Master', min: 3000 },
]

const TIER_SWATCH: Record<string, string> = {
  Bronze: '#A26A3F',
  Silver: '#8E97A3',
  Gold: '#C99A3B',
  Platinum: '#6F6A92',
}

function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="pt-callout pt-rise" style={{ background: 'color-mix(in srgb, var(--pt-error) 9%, transparent)', borderColor: 'color-mix(in srgb, var(--pt-error) 25%, transparent)' }}>
      <p className="pt-flash pt-flash--err" style={{ margin: 0 }}>{children}</p>
    </div>
  )
}

function IntakeStatus({ status }: { status: string }) {
  if (status === 'unclaimed') return <span className="pt-pill pt-pill--quiet"><span className="pt-pill-dot" />Pending</span>
  if (status === 'claimed') return <span className="pt-pill"><span className="pt-pill-dot pt-pill-dot--live" />Booked in</span>
  return <span className="pt-pill pt-pill--done"><CheckCircle2 size={12} />{status.replace(/_/g, ' ')}</span>
}

export default function PublicCustomerPortalPage() {
  const { slug } = useParams<{ slug: string }>()
  const storageKey = `portal_token_${slug}`

  const [token, setToken] = useState<string | null>(() => localStorage.getItem(storageKey))
  const [shopInfo, setShopInfo] = useState<PortalShop | null>(null)

  // The shop's name and logo (Mister Minit's, for Minit shops) for the header,
  // before anyone signs in. Cosmetic: the page works without it.
  useEffect(() => {
    if (!slug) return
    let cancelled = false
    portalGetShop(slug)
      .then((r) => { if (!cancelled) setShopInfo(r.data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [slug])
  const [profile, setProfile] = useState<PortalProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'book' | 'jobs' | 'points'>('book')

  // Lookup form
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [codeSent, setCodeSent] = useState(false)
  const [code, setCode] = useState('')

  // Book form
  const [bookAddress, setBookAddress] = useState('')
  const [bookMake, setBookMake] = useState('')
  const [bookModel, setBookModel] = useState('')
  const [bookYear, setBookYear] = useState('')
  const [bookPlate, setBookPlate] = useState('')
  const [bookDesc, setBookDesc] = useState('')
  const [bookDate, setBookDate] = useState('')
  const [bookSubmitting, setBookSubmitting] = useState(false)
  const [bookSuccess, setBookSuccess] = useState(false)

  useEffect(() => {
    if (token && slug) loadProfile()
  }, [token])

  async function loadProfile() {
    if (!slug || !token) return
    setLoading(true)
    setError(null)
    try {
      const res = await portalGetProfile(slug, token)
      setProfile(res.data)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        localStorage.removeItem(storageKey)
        setToken(null)
        setProfile(null)
      } else {
        setError('Could not load your profile. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault()
    if (!slug) return
    setLoading(true)
    setError(null)
    try {
      await portalLookup(slug, name.trim(), phone.trim())
      setCodeSent(true)
      setCode('')
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault()
    if (!slug) return
    setLoading(true)
    setError(null)
    try {
      const res = await portalVerify(slug, phone.trim(), code.trim())
      const { token: newToken } = res.data
      localStorage.setItem(storageKey, newToken)
      setCodeSent(false)
      setToken(newToken)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  async function handleBook(e: React.FormEvent) {
    e.preventDefault()
    if (!slug || !token) return
    setBookSubmitting(true)
    setError(null)
    try {
      await portalBook(slug, token, {
        job_address: bookAddress.trim(),
        vehicle_make: bookMake.trim() || undefined,
        vehicle_model: bookModel.trim() || undefined,
        vehicle_year: bookYear.trim() || undefined,
        registration_plate: bookPlate.trim() || undefined,
        description: bookDesc.trim() || undefined,
        preferred_date: bookDate || undefined,
      })
      setBookSuccess(true)
      setBookAddress('')
      setBookMake('')
      setBookModel('')
      setBookYear('')
      setBookPlate('')
      setBookDesc('')
      setBookDate('')
      await loadProfile()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Booking failed. Please try again.')
    } finally {
      setBookSubmitting(false)
    }
  }

  function handleSignOut() {
    localStorage.removeItem(storageKey)
    setToken(null)
    setProfile(null)
    setBookSuccess(false)
    setError(null)
    setName('')
    setPhone('')
    setCodeSent(false)
    setCode('')
  }

  const shop = profile?.shop ?? shopInfo

  // --- Lookup screen ---
  if (!token || (!profile && !loading)) {
    return (
      <PortalPage accent={shop?.brand_color} minit={!!shop?.is_minit}>
        <PortalHero
          brand={{ name: shop?.name, logoUrl: shop?.logo_url, minit: !!shop?.is_minit }}
          eyebrow="Mobile key service"
          title={<>Keys cut and coded, <em>wherever you are.</em></>}
          lede="Sign in with your name and mobile number and we’ll text you a code. Then book a visit, track it, and check your points."
        />
        <PortalBody>
          {error && <ErrorNote>{error}</ErrorNote>}
          {codeSent ? (
            <form onSubmit={handleVerify} className="pt-card pt-card-pad pt-rise" style={{ padding: 24 }}>
              <p className="pt-label" style={{ margin: 0 }}>Step 2 of 2</p>
              <p className="pt-serif" style={{ fontSize: 26, margin: '6px 0 4px' }}>Enter your code</p>
              <p className="pt-muted" style={{ fontSize: 14, margin: '0 0 18px' }}>
                We texted a 6-digit code to <strong style={{ color: 'var(--pt-text)' }}>{phone.trim()}</strong>.
              </p>
              <label htmlFor="portal-code" className="pt-label" style={{ display: 'block', marginBottom: 6 }}>Code</label>
              <input
                id="portal-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                autoFocus
                value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="pt-input pt-input--code"
                placeholder="••••••"
              />
              <button
                type="submit"
                disabled={loading || code.length < 6}
                className="pt-btn pt-btn--block"
                style={{ marginTop: 16, padding: '13px 18px' }}
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                {loading ? 'Checking…' : 'Sign in'}
              </button>
              <div style={{ textAlign: 'center', marginTop: 14 }}>
                <button
                  type="button"
                  className="pt-link"
                  onClick={() => { setCodeSent(false); setError(null) }}
                >
                  Use a different number
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleLookup} className="pt-card pt-card-pad pt-rise" style={{ padding: 24 }}>
              <p className="pt-label" style={{ margin: 0 }}>Step 1 of 2</p>
              <p className="pt-serif" style={{ fontSize: 26, margin: '6px 0 18px' }}>Who’s booking?</p>
              <div className="pt-stack">
                <label className="pt-field">
                  <span>Full name</span>
                  <input
                    type="text"
                    required
                    autoComplete="name"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    className="pt-input"
                    placeholder="Jane Smith"
                  />
                </label>
                <label className="pt-field">
                  <span>Mobile number</span>
                  <input
                    type="tel"
                    required
                    autoComplete="tel"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    className="pt-input"
                    placeholder="04xx xxx xxx"
                  />
                </label>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="pt-btn pt-btn--block"
                style={{ marginTop: 18, padding: '13px 18px' }}
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <MessageSquareText size={16} />}
                {loading ? 'Sending…' : 'Text me a code'}
              </button>
            </form>
          )}
        </PortalBody>
      </PortalPage>
    )
  }

  if (loading && !profile) return <PortalLoading label="Loading your profile…" />

  const firstName = profile?.name.split(' ')[0]
  const loyalty = profile?.loyalty
  const spend = loyalty ? loyalty.rolling_12m_spend_cents / 100 : 0
  const tierIdx = loyalty ? TIERS.findIndex(t => t.name === loyalty.tier_name) : -1
  const nextTier = tierIdx >= 0 ? TIERS[tierIdx + 1] : undefined
  const tierFloor = tierIdx >= 0 ? TIERS[tierIdx].min : 0
  const toNext = nextTier ? Math.max(0, nextTier.min - spend) : 0
  const tierProgress = nextTier
    ? Math.min(1, Math.max(0, (spend - tierFloor) / (nextTier.min - tierFloor)))
    : 1

  // --- Portal screen ---
  return (
    <PortalPage accent={shop?.brand_color} minit={!!shop?.is_minit}>
      <PortalHero
        brand={{ name: shop?.name, logoUrl: shop?.logo_url, minit: !!shop?.is_minit }}
        barRight={
          <button type="button" onClick={handleSignOut} className="pt-btn-ghost pt-btn-ghost--on-ink">
            <LogOut size={13} /> Sign out
          </button>
        }
        eyebrow={greeting()}
        title={<>Hi, <em>{firstName}.</em></>}
        lede={loyalty ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Star size={14} style={{ color: TIER_SWATCH[loyalty.tier_name] ?? '#D9BD8C' }} fill="currentColor" />
            {loyalty.tier_label} member · {loyalty.points_balance.toLocaleString()} points
          </span>
        ) : 'What can we help you with today?'}
      />

      <PortalBody>
        <Segmented<'book' | 'jobs' | 'points'>
          label="Portal sections"
          value={tab}
          onChange={(t) => {
            setTab(t)
            setBookSuccess(false)
            setError(null)
          }}
          options={[
            { value: 'book', label: 'Book', icon: <KeyRound size={14} /> },
            { value: 'jobs', label: 'My jobs', icon: <ClipboardList size={14} /> },
            { value: 'points', label: 'Points', icon: <Star size={14} /> },
          ]}
        />

        {error && <ErrorNote>{error}</ErrorNote>}

        {/* Book tab */}
        {tab === 'book' &&
          (bookSuccess ? (
            <div className="pt-card pt-card-pad pt-rise" style={{ textAlign: 'center', padding: '40px 24px' }}>
              <span
                className="pt-pop"
                style={{
                  width: 68, height: 68, borderRadius: 999, display: 'inline-grid', placeItems: 'center',
                  background: 'var(--pt-ok-soft)', color: 'var(--pt-ok)',
                }}
              >
                <CheckCircle2 size={32} />
              </span>
              <p className="pt-serif" style={{ fontSize: 30, margin: '16px 0 6px' }}>Booking received</p>
              <p className="pt-muted" style={{ fontSize: 14, margin: '0 0 22px' }}>We’ll call you to confirm your appointment time.</p>
              <button onClick={() => setBookSuccess(false)} className="pt-btn">
                Book another
              </button>
            </div>
          ) : (
            <form onSubmit={handleBook} className="pt-card pt-card-pad pt-rise" style={{ padding: 22 }}>
              <p className="pt-label" style={{ margin: 0 }}>New booking</p>
              <p className="pt-serif" style={{ fontSize: 26, margin: '6px 0 18px' }}>Where should we meet you?</p>
              <div className="pt-stack">
                <label className="pt-field">
                  <span>Job address <span style={{ color: 'var(--pt-accent)' }}>*</span></span>
                  <input
                    type="text"
                    required
                    autoComplete="street-address"
                    value={bookAddress}
                    onChange={e => setBookAddress(e.target.value)}
                    className="pt-input"
                    placeholder="123 Main St, Melbourne VIC 3000"
                  />
                </label>

                <p className="pt-label" style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 6 }}>
                  <Car size={14} style={{ color: 'var(--pt-brass)' }} /> The vehicle
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 10 }}>
                  <label className="pt-field">
                    <span>Make</span>
                    <input type="text" value={bookMake} onChange={e => setBookMake(e.target.value)} className="pt-input" placeholder="Toyota" />
                  </label>
                  <label className="pt-field">
                    <span>Model</span>
                    <input type="text" value={bookModel} onChange={e => setBookModel(e.target.value)} className="pt-input" placeholder="Corolla" />
                  </label>
                  <label className="pt-field">
                    <span>Year</span>
                    <input type="text" inputMode="numeric" value={bookYear} onChange={e => setBookYear(e.target.value)} className="pt-input" placeholder="2019" />
                  </label>
                  <label className="pt-field">
                    <span>Rego plate</span>
                    <input
                      type="text"
                      value={bookPlate}
                      onChange={e => setBookPlate(e.target.value)}
                      className="pt-input"
                      style={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}
                      placeholder="ABC123"
                    />
                  </label>
                </div>

                <label className="pt-field">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><CalendarDays size={13} /> Preferred date</span>
                  <input
                    type="date"
                    value={bookDate}
                    onChange={e => setBookDate(e.target.value)}
                    min={new Date().toISOString().split('T')[0]}
                    className="pt-input"
                  />
                </label>
                <p className="pt-muted" style={{ fontSize: 12.5, marginTop: 6 }}>We’ll call to confirm a time that works for you.</p>

                <label className="pt-field">
                  <span>What do you need?</span>
                  <textarea
                    value={bookDesc}
                    onChange={e => setBookDesc(e.target.value)}
                    rows={3}
                    className="pt-input"
                    placeholder="e.g. Lost all keys, need 2 remotes cut and programmed"
                  />
                </label>
              </div>
              <button
                type="submit"
                disabled={bookSubmitting}
                className="pt-btn pt-btn--block"
                style={{ marginTop: 20, padding: '14px 18px' }}
              >
                {bookSubmitting ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />}
                {bookSubmitting ? 'Submitting…' : 'Request booking'}
              </button>
            </form>
          ))}

        {/* My Jobs tab */}
        {tab === 'jobs' && (
          !profile?.intake_jobs.length ? (
            <div className="pt-card pt-card-pad pt-rise" style={{ textAlign: 'center', padding: '40px 24px' }}>
              <p className="pt-serif" style={{ fontSize: 26, margin: 0 }}>No bookings yet</p>
              <p className="pt-muted" style={{ fontSize: 14, margin: '6px 0 18px' }}>When you book a visit it’ll show up here.</p>
              <button type="button" className="pt-btn" onClick={() => setTab('book')}>
                <KeyRound size={15} /> Book a visit
              </button>
            </div>
          ) : (
            profile.intake_jobs.map((job, i) => (
              <article key={job.id} className="pt-card pt-job pt-card-pad" style={{ animationDelay: `${Math.min(i, 8) * 70}ms` }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ minWidth: 0 }}>
                    <p className="pt-type" style={{ margin: 0 }}>
                      {new Date(job.created_at).toLocaleDateString('en-AU', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </p>
                    <h3 className="pt-job-title" style={{ fontSize: 21 }}>{job.job_address}</h3>
                    {(job.vehicle_make || job.vehicle_model) && (
                      <p style={{ fontSize: 13, margin: '6px 0 0', color: 'var(--pt-text-mid)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Car size={13} style={{ color: 'var(--pt-brass)' }} />
                        {[job.vehicle_year, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ')}
                      </p>
                    )}
                    {job.description && (
                      <p className="pt-muted line-clamp-2" style={{ fontSize: 13, margin: '6px 0 0' }}>{job.description}</p>
                    )}
                  </div>
                  <IntakeStatus status={job.status} />
                </div>
              </article>
            ))
          )
        )}

        {/* My Points tab */}
        {tab === 'points' && (
          !loyalty ? (
            <div className="pt-card pt-card-pad pt-rise" style={{ textAlign: 'center', padding: '40px 24px' }}>
              <p className="pt-serif" style={{ fontSize: 26, margin: 0 }}>Your points start here</p>
              <p className="pt-muted" style={{ fontSize: 14, margin: '6px 0 0' }}>
                No loyalty record yet. Points are awarded on completed jobs.
              </p>
            </div>
          ) : (
            <>
              <div className={clsx('pt-member', TIER_SWATCH[loyalty.tier_name] ? `pt-member--${loyalty.tier_name}` : 'pt-member--default', 'pt-rise')}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <span className="pt-eyebrow" style={{ color: 'rgba(255,255,255,0.85)' }}>{loyalty.tier_label}</span>
                  <span className="pt-eyebrow" style={{ color: 'rgba(255,255,255,0.7)' }}>{loyalty.tier_name}</span>
                </div>
                <div>
                  <p className="pt-member-points" style={{ margin: 0 }}>{loyalty.points_balance.toLocaleString()}</p>
                  <p style={{ margin: '4px 0 0', fontSize: 13, opacity: 0.85 }}>
                    points · worth ${loyalty.points_dollar_value.toFixed(2)}
                  </p>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: '0.04em' }}>{profile?.name}</span>
                  <span className="pt-serif" style={{ fontSize: 18, opacity: 0.9 }}>Member</span>
                </div>
              </div>

              <div className="pt-card pt-card-pad pt-rise" style={{ animationDelay: '0.1s' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
                  <p className="pt-label" style={{ margin: 0 }}>12-month spend</p>
                  <p className="pt-serif" style={{ fontSize: 24, margin: 0, fontVariantNumeric: 'tabular-nums' }}>${spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </div>
                <div className="pt-meter" style={{ marginTop: 12 }}>
                  <span style={{ width: `${tierProgress * 100}%` }} />
                </div>
                <p className="pt-muted" style={{ fontSize: 12.5, margin: '10px 0 0' }}>
                  {nextTier
                    ? <>Spend <strong style={{ color: 'var(--pt-text)' }}>${Math.ceil(toNext).toLocaleString()}</strong> more this year to reach {nextTier.name}.</>
                    : 'You’re at the top tier — thank you for being a regular.'}
                  {' '}Earn 1 point per $1 spent on any service (watch, shoe, or key). Redeem in store.
                </p>
              </div>

              <div className="pt-card pt-card-pad pt-rise" style={{ animationDelay: '0.18s' }}>
                <p className="pt-label" style={{ margin: '0 0 12px' }}>Membership tiers</p>
                <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                  {TIERS.map((tier, idx) => {
                    const current = loyalty.tier_name === tier.name
                    const reached = tierIdx >= idx
                    return (
                      <li
                        key={tier.name}
                        aria-current={current ? 'true' : undefined}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 12,
                          background: current ? 'var(--pt-card-alt)' : undefined,
                          border: current ? '1px solid var(--pt-line-strong)' : '1px solid transparent',
                          opacity: reached ? 1 : 0.7,
                        }}
                      >
                        <span
                          style={{
                            width: 28, height: 28, borderRadius: 999, flexShrink: 0, display: 'grid', placeItems: 'center',
                            background: `linear-gradient(135deg, ${TIER_SWATCH[tier.name]}, color-mix(in srgb, ${TIER_SWATCH[tier.name]} 55%, #fff))`,
                            color: '#fff',
                          }}
                        >
                          <Star size={13} fill={reached ? 'currentColor' : 'none'} />
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>
                            {tier.name} <span className="pt-muted" style={{ fontWeight: 500 }}>· {tier.label}</span>
                          </p>
                        </div>
                        {current && <span className="pt-pill pt-pill--ready">You’re here</span>}
                        <span className="pt-muted" style={{ fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
                          ${tier.min.toLocaleString()}+/yr
                        </span>
                      </li>
                    )
                  })}
                </ol>
              </div>
            </>
          )
        )}
      </PortalBody>
    </PortalPage>
  )
}
