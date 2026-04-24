import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  portalLookup,
  portalGetProfile,
  portalBook,
  type PortalProfile,
} from '@/lib/api'

const TIER_COLORS: Record<string, string> = {
  Bronze: 'text-amber-700 bg-amber-50 border-amber-200',
  Silver: 'text-slate-600 bg-slate-50 border-slate-200',
  Gold: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  Platinum: 'text-purple-700 bg-purple-50 border-purple-200',
}

export default function PublicCustomerPortalPage() {
  const { slug } = useParams<{ slug: string }>()
  const storageKey = `portal_token_${slug}`

  const [token, setToken] = useState<string | null>(() => localStorage.getItem(storageKey))
  const [profile, setProfile] = useState<PortalProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'book' | 'jobs' | 'points'>('book')

  // Lookup form
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')

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
    } catch (e: any) {
      if (e.response?.status === 401) {
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
      const res = await portalLookup(slug, name.trim(), phone.trim())
      const { token: newToken } = res.data
      localStorage.setItem(storageKey, newToken)
      setToken(newToken)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Something went wrong. Please try again.')
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
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Booking failed. Please try again.')
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
  }

  // --- Lookup screen ---
  if (!token || (!profile && !loading)) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-start justify-center pt-16 px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="text-4xl mb-3">🔑</div>
            <h1 className="text-3xl font-bold text-gray-900">Book a Mobile Key Service</h1>
            <p className="text-gray-500 mt-2 text-sm">Enter your name and phone number to continue.</p>
          </div>
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>
          )}
          <form
            onSubmit={handleLookup}
            className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4"
          >
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
              <input
                type="text"
                required
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Jane Smith"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone number</label>
              <input
                type="tel"
                required
                value={phone}
                onChange={e => setPhone(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="04xx xxx xxx"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Loading...' : 'Continue'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  if (loading && !profile) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading your profile…</div>
      </div>
    )
  }

  // --- Portal screen ---
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">
                Hi, {profile?.name.split(' ')[0]}
              </h1>
              {profile?.loyalty && (
                <span
                  className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full border mt-0.5 ${
                    TIER_COLORS[profile.loyalty.tier_name] ?? 'text-gray-600 bg-gray-50 border-gray-200'
                  }`}
                >
                  {profile.loyalty.tier_label} Member
                </span>
              )}
            </div>
          </div>
          <button
            onClick={handleSignOut}
            className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-lg mx-auto flex">
          {(['book', 'jobs', 'points'] as const).map(t => (
            <button
              key={t}
              onClick={() => {
                setTab(t)
                setBookSuccess(false)
                setError(null)
              }}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t === 'book' ? 'Book a Job' : t === 'jobs' ? 'My Jobs' : 'My Points'}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 py-6">
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>
        )}

        {/* Book tab */}
        {tab === 'book' &&
          (bookSuccess ? (
            <div className="text-center py-14">
              <div className="text-5xl mb-4">✅</div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Booking Submitted!</h2>
              <p className="text-gray-500 text-sm mb-6">We'll call you to confirm your appointment time.</p>
              <button
                onClick={() => setBookSuccess(false)}
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
              >
                Book Another
              </button>
            </div>
          ) : (
            <form onSubmit={handleBook} className="space-y-4">
              <h2 className="text-base font-semibold text-gray-900">Mobile Key Service Booking</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Job address <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={bookAddress}
                  onChange={e => setBookAddress(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="123 Main St, Melbourne VIC 3000"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Vehicle make</label>
                  <input
                    type="text"
                    value={bookMake}
                    onChange={e => setBookMake(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Toyota"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
                  <input
                    type="text"
                    value={bookModel}
                    onChange={e => setBookModel(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Corolla"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                  <input
                    type="text"
                    value={bookYear}
                    onChange={e => setBookYear(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="2019"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Rego plate</label>
                  <input
                    type="text"
                    value={bookPlate}
                    onChange={e => setBookPlate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="ABC123"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Preferred date</label>
                <input
                  type="date"
                  value={bookDate}
                  onChange={e => setBookDate(e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">We'll call to confirm a time that works for you.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes / description</label>
                <textarea
                  value={bookDesc}
                  onChange={e => setBookDesc(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  placeholder="e.g. Lost all keys, need 2 remotes cut and programmed"
                />
              </div>
              <button
                type="submit"
                disabled={bookSubmitting}
                className="w-full py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {bookSubmitting ? 'Submitting…' : 'Submit Booking Request'}
              </button>
            </form>
          ))}

        {/* My Jobs tab */}
        {tab === 'jobs' && (
          <div className="space-y-3">
            <h2 className="text-base font-semibold text-gray-900">My Bookings</h2>
            {!profile?.intake_jobs.length ? (
              <div className="text-center py-12 text-gray-400 text-sm">No bookings yet.</div>
            ) : (
              profile.intake_jobs.map(job => (
                <div key={job.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{job.job_address}</p>
                      {(job.vehicle_make || job.vehicle_model) && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {[job.vehicle_year, job.vehicle_make, job.vehicle_model]
                            .filter(Boolean)
                            .join(' ')}
                        </p>
                      )}
                      {job.description && (
                        <p className="text-xs text-gray-400 mt-1 line-clamp-2">{job.description}</p>
                      )}
                    </div>
                    <span
                      className={`shrink-0 text-xs px-2 py-1 rounded-full font-medium ${
                        job.status === 'unclaimed'
                          ? 'bg-yellow-50 text-yellow-700'
                          : job.status === 'claimed'
                          ? 'bg-blue-50 text-blue-700'
                          : 'bg-green-50 text-green-700'
                      }`}
                    >
                      {job.status === 'unclaimed'
                        ? 'Pending'
                        : job.status === 'claimed'
                        ? 'Assigned'
                        : job.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-2">
                    {new Date(job.created_at).toLocaleDateString('en-AU', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        {/* My Points tab */}
        {tab === 'points' && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-gray-900">Loyalty Points</h2>
            {!profile?.loyalty ? (
              <div className="text-center py-12 text-gray-400 text-sm">
                No loyalty record yet. Points are awarded on completed jobs.
              </div>
            ) : (
              <>
                <div className="bg-white rounded-2xl border border-gray-200 p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <p className="text-4xl font-bold text-gray-900">
                        {profile.loyalty.points_balance.toLocaleString()}
                      </p>
                      <p className="text-sm text-gray-500 mt-0.5">
                        points · ${profile.loyalty.points_dollar_value.toFixed(2)} value
                      </p>
                    </div>
                    <span
                      className={`text-sm font-bold px-3 py-1.5 rounded-full border ${
                        TIER_COLORS[profile.loyalty.tier_name] ?? 'text-gray-600 bg-gray-50 border-gray-200'
                      }`}
                    >
                      {profile.loyalty.tier_label}
                    </span>
                  </div>
                  <div className="pt-3 border-t border-gray-100 space-y-1">
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>12-month spend</span>
                      <span>${(profile.loyalty.rolling_12m_spend_cents / 100).toFixed(2)}</span>
                    </div>
                    <p className="text-xs text-gray-400">
                      Earn 1 point per $1 spent on any service (watch, shoe, or key). Redeem in store.
                    </p>
                  </div>
                </div>

                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Membership Tiers</h3>
                  <div className="space-y-2">
                    {[
                      { name: 'Bronze', label: 'Fixer', min: '$0' },
                      { name: 'Silver', label: 'Regular', min: '$500' },
                      { name: 'Gold', label: 'Trusted', min: '$1,500' },
                      { name: 'Platinum', label: 'Master', min: '$3,000' },
                    ].map(tier => (
                      <div
                        key={tier.name}
                        className={`flex items-center justify-between px-3 py-2 rounded-lg ${
                          profile.loyalty!.tier_name === tier.name
                            ? 'bg-blue-50 border border-blue-200'
                            : 'bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
                              TIER_COLORS[tier.name] ?? ''
                            }`}
                          >
                            {tier.name}
                          </span>
                          <span className="text-sm text-gray-700">{tier.label}</span>
                          {profile.loyalty!.tier_name === tier.name && (
                            <span className="text-xs text-blue-600 font-medium">← you</span>
                          )}
                        </div>
                        <span className="text-xs text-gray-500">{tier.min}+/yr</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
