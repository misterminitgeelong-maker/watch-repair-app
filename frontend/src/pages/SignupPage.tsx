import { useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import { signup } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { isDemoModeEnabled } from '@/lib/onboarding'
import { MKT, MARKETING_CSS } from '@/lib/marketingTheme'
import { MarketingField } from '@/components/MarketingField'

type PlanId = 'basic_all_tabs' | 'pro'

type UseCaseId = 'watch' | 'shoe' | 'auto_key' | 'multi_site'

const USE_CASE_OPTIONS: Array<{ id: UseCaseId; label: string; hint: string }> = [
  { id: 'watch', label: 'Watch repairs', hint: 'Traditional watch service and restoration workflow' },
  { id: 'shoe', label: 'Shoe repairs', hint: 'Intake, status tracking, and completion for footwear jobs' },
  { id: 'auto_key', label: 'Mobile Services', hint: 'Track key cutting, programming, and mobile/shop jobs' },
  { id: 'multi_site', label: 'Multiple shop locations', hint: 'Manage sites under one parent account' },
]

const PLAN_OPTIONS: Array<{ id: PlanId; name: string; price: string; description: string }> = [
  { id: 'basic_all_tabs', name: 'Shop', price: 'A$50/month', description: 'One location: watch, shoe and mobile services' },
  { id: 'pro', name: 'Pro', price: 'A$90/month', description: 'Multi-site + extra locations at A$25 each' },
]

function recommendPlan(uses: UseCaseId[]): PlanId {
  if (uses.includes('multi_site')) return 'pro'
  return 'basic_all_tabs'
}

export default function SignupPage() {
  const { token, login: setToken } = useAuth()

  const [tenantName, setTenantName] = useState('')
  const [tenantSlug, setTenantSlug] = useState('')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [selectedUses, setSelectedUses] = useState<UseCaseId[]>(['watch'])
  const [selectedPlan, setSelectedPlan] = useState<PlanId>('basic_all_tabs')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [redirectingToPayment, setRedirectingToPayment] = useState(false)

  const recommendedPlan = useMemo(() => recommendPlan(selectedUses), [selectedUses])

  if (token && !redirectingToPayment && !isDemoModeEnabled()) return <Navigate to="/dashboard" replace />

  function toggleUseCase(id: UseCaseId) {
    setSelectedUses((prev) => {
      if (prev.includes(id)) return prev.filter((item) => item !== id)
      return [...prev, id]
    })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    const normalizedSlug = tenantSlug.trim().toLowerCase()
    if (!normalizedSlug) {
      setError('Shop ID is required.')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setLoading(true)
    try {
      const { data } = await signup({
        tenant_name: tenantName,
        tenant_slug: normalizedSlug,
        full_name: fullName,
        email,
        password,
        plan_code: selectedPlan,
      })
      setRedirectingToPayment(true)
      setToken(data.access_token, data.refresh_token, data.expires_in_seconds)
      window.location.assign(`/signup/checkout?plan=${encodeURIComponent(selectedPlan)}`)
    } catch (err: unknown) {
      const apiMessage =
        typeof err === 'object' &&
        err !== null &&
        'response' in err &&
        typeof (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(typeof apiMessage === 'string' ? apiMessage : 'Could not create account. Please try again.')
      setRedirectingToPayment(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mkt-landing min-h-screen flex items-center justify-center px-4 py-10" style={{ background: MKT.oatmeal }}>
      <style>{MARKETING_CSS}</style>

      <div className="w-full" style={{ maxWidth: 620 }}>
        {redirectingToPayment ? (
          <div className="mkt-slide-up" style={{ background: MKT.paper, border: `1px solid ${MKT.ink}`, padding: '40px 32px', textAlign: 'center' }}>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, letterSpacing: '-0.03em', color: MKT.ink }}>
              Redirecting to payment…
            </h1>
            <p style={{ marginTop: 10, fontSize: 14, color: MKT.textBody }}>
              Setting up your plan with Stripe. This window will redirect automatically.
            </p>
          </div>
        ) : (
          <>
            <div className="mkt-slide-up flex flex-col items-center mb-8">
              <div style={{ border: `1px solid ${MKT.ink}`, background: MKT.paper, padding: '16px 22px', display: 'inline-block' }}>
                <img
                  src="/marketing/mainspring-logo-vermilion.svg"
                  alt="Mainspring"
                  style={{ width: 'min(76vw, 320px)', height: 'auto', display: 'block', maxWidth: '100%', objectFit: 'contain' }}
                />
              </div>
              <p style={{ marginTop: 14, fontSize: 11, fontWeight: 700, letterSpacing: '0.24em', textTransform: 'uppercase', color: MKT.vermilionDeep }}>
                Create your shop
              </p>
            </div>

            {token && isDemoModeEnabled() && (
              <div className="mkt-slide-up mb-5" style={{ background: MKT.paper, border: `1px solid ${MKT.ink}`, padding: '16px 20px' }}>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: MKT.ink }}>Ready to start your own shop?</p>
                <p style={{ margin: '8px 0 0', fontSize: 13, color: MKT.textBody }}>
                  You are still in the public demo. This form creates a real workspace — not another copy of the demo shop.
                </p>
              </div>
            )}

            <div className="mkt-slide-up-delay" style={{ background: MKT.paper, border: `1px solid ${MKT.ink}`, padding: '32px 28px' }}>
              <p style={{ textAlign: 'center', fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted, marginBottom: 6 }}>
                Set up your account
              </p>
              <p style={{ textAlign: 'center', fontSize: 13, color: MKT.textBody, marginBottom: 20 }}>
                Answer a few questions so we can recommend the right plan.
              </p>

              <div style={{ height: 1, background: MKT.ruleMid, marginBottom: 22 }} />

              <form onSubmit={handleSubmit} className="flex flex-col" style={{ gap: 18 }}>
                <div style={{ border: `1px solid ${MKT.ruleMid}`, padding: 16 }}>
                  <p style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 700, color: MKT.ink }}>
                    What are you most likely to use the app for?
                  </p>
                  <div className="flex flex-col" style={{ gap: 2 }}>
                    {USE_CASE_OPTIONS.map((item) => {
                      const checked = selectedUses.includes(item.id)
                      return (
                        <label
                          key={item.id}
                          className="flex items-start"
                          style={{ gap: 10, padding: '8px 8px', cursor: 'pointer', background: checked ? MKT.oatmealPanel : 'transparent' }}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleUseCase(item.id)}
                            style={{ marginTop: 3 }}
                          />
                          <span>
                            <span style={{ display: 'block', fontSize: 13, fontWeight: 700, color: MKT.ink }}>{item.label}</span>
                            <span style={{ display: 'block', fontSize: 11, color: MKT.textMuted }}>{item.hint}</span>
                          </span>
                        </label>
                      )
                    })}
                  </div>
                  <div className="flex items-center justify-between flex-wrap" style={{ gap: 8, marginTop: 12 }}>
                    <p style={{ margin: 0, fontSize: 11, color: MKT.textBody }}>
                      Recommended plan: <strong style={{ color: MKT.ink }}>{PLAN_OPTIONS.find((p) => p.id === recommendedPlan)?.name}</strong>
                    </p>
                    <button
                      type="button"
                      onClick={() => setSelectedPlan(recommendedPlan)}
                      className="mkt-btn-outline-ink whitespace-nowrap"
                      style={{ padding: '6px 12px', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}
                    >
                      Apply recommendation
                    </button>
                  </div>
                </div>

                <MarketingField
                  label="Shop Name"
                  placeholder="Example: Heritage Watch Co"
                  value={tenantName}
                  onChange={setTenantName}
                  autoFocus
                  required
                />
                <MarketingField
                  label="Shop ID"
                  placeholder="heritagewatch"
                  value={tenantSlug}
                  onChange={setTenantSlug}
                  required
                />
                <MarketingField
                  label="Your Full Name"
                  placeholder="Jane Smith"
                  value={fullName}
                  onChange={setFullName}
                  required
                />
                <MarketingField
                  label="Email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={setEmail}
                  required
                />
                <MarketingField
                  label="Password"
                  type="password"
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={setPassword}
                  showPasswordToggle
                  required
                />

                <div>
                  <p style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: MKT.ink }}>
                    Choose your plan
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 10 }}>
                    {PLAN_OPTIONS.map((plan) => {
                      const active = selectedPlan === plan.id
                      return (
                        <button
                          key={plan.id}
                          type="button"
                          onClick={() => setSelectedPlan(plan.id)}
                          className="text-left"
                          style={{
                            padding: 12,
                            border: active ? `2px solid ${MKT.vermilion}` : `1px solid ${MKT.ruleMid}`,
                            background: active ? MKT.oatmealPanel : MKT.paper,
                          }}
                        >
                          <div className="flex items-start justify-between" style={{ gap: 8 }}>
                            <div>
                              <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: MKT.ink }}>{plan.name}</p>
                              <p style={{ margin: '4px 0 0', fontSize: 11, color: MKT.textMuted }}>{plan.description}</p>
                              <p style={{ margin: '8px 0 0', fontSize: 12, fontWeight: 700, color: MKT.vermilionDeep }}>{plan.price}</p>
                            </div>
                            {active && <Check size={16} style={{ color: MKT.vermilionDeep, flexShrink: 0 }} aria-hidden />}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {error && <p style={{ fontSize: 13, color: MKT.vermilionDeep, margin: 0 }}>{error}</p>}

                <button
                  type="submit"
                  disabled={loading || redirectingToPayment}
                  className="mkt-btn-primary"
                  style={{ width: '100%', padding: '13px', fontSize: 13, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}
                >
                  {redirectingToPayment ? 'Setting up payment…' : loading ? 'Creating account…' : 'Create account & continue to payment'}
                </button>
                <p style={{ margin: 0, fontSize: 11, color: MKT.textMuted, textAlign: 'center' }}>
                  14-day trial. Stripe Checkout needs a card; you are not charged until the trial ends.
                </p>
              </form>

              <p style={{ fontSize: 13, textAlign: 'center', marginTop: 20, color: MKT.textBody }}>
                Already have an account?{' '}
                <Link to="/login" style={{ color: MKT.vermilionDeep, fontWeight: 600 }}>
                  Sign in
                </Link>
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
