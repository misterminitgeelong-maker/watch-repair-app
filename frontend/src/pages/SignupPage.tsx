import { useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import { signup } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Input } from '@/components/ui'

type PlanId =
  | 'basic_watch'
  | 'basic_shoe'
  | 'basic_auto_key'
  | 'basic_watch_shoe'
  | 'basic_watch_auto_key'
  | 'basic_shoe_auto_key'
  | 'basic_all_tabs'
  | 'pro'

type UseCaseId = 'watch' | 'shoe' | 'auto_key' | 'multi_site'

const USE_CASE_OPTIONS: Array<{ id: UseCaseId; label: string; hint: string }> = [
  { id: 'watch', label: 'Watch repairs', hint: 'Traditional watch service and restoration workflow' },
  { id: 'shoe', label: 'Shoe repairs', hint: 'Intake, status tracking, and completion for footwear jobs' },
  { id: 'auto_key', label: 'Mobile Services', hint: 'Track key cutting, programming, and mobile/shop jobs' },
  { id: 'multi_site', label: 'Multiple shop locations', hint: 'Manage sites under one parent account' },
]

const PLAN_OPTIONS: Array<{ id: PlanId; name: string; price: string; description: string }> = [
  { id: 'basic_watch', name: 'Basic - Watch', price: 'A$25/month', description: 'One tab: watch repairs' },
  { id: 'basic_shoe', name: 'Basic - Shoe', price: 'A$25/month', description: 'One tab: shoe repairs' },
  { id: 'basic_auto_key', name: 'Basic - Mobile Services', price: 'A$25/month', description: 'One tab: mobile services jobs' },
  { id: 'basic_watch_shoe', name: 'Basic - Watch + Shoe', price: 'A$35/month', description: 'Two service tabs' },
  { id: 'basic_watch_auto_key', name: 'Basic - Watch + Mobile Services', price: 'A$35/month', description: 'Two service tabs' },
  { id: 'basic_shoe_auto_key', name: 'Basic - Shoe + Mobile Services', price: 'A$35/month', description: 'Two service tabs' },
  { id: 'basic_all_tabs', name: 'Basic - All Tabs', price: 'A$45/month', description: 'All three service tabs' },
  { id: 'pro', name: 'Pro - Full Access', price: 'A$50/month', description: 'All tabs + multi-site + full features' },
]

function recommendPlan(uses: UseCaseId[]): PlanId {
  if (uses.includes('multi_site')) return 'pro'

  const selectedServices = ['watch', 'shoe', 'auto_key'].filter((service) => uses.includes(service as UseCaseId))

  if (selectedServices.length === 0) return 'basic_watch'
  if (selectedServices.length === 1) {
    if (selectedServices[0] === 'watch') return 'basic_watch'
    if (selectedServices[0] === 'shoe') return 'basic_shoe'
    return 'basic_auto_key'
  }

  if (selectedServices.length === 2) {
    const hasWatch = selectedServices.includes('watch')
    const hasShoe = selectedServices.includes('shoe')
    if (hasWatch && hasShoe) return 'basic_watch_shoe'
    if (hasWatch) return 'basic_watch_auto_key'
    return 'basic_shoe_auto_key'
  }

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
  const [selectedPlan, setSelectedPlan] = useState<PlanId>('basic_watch')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [redirectingToPayment, setRedirectingToPayment] = useState(false)

  const recommendedPlan = useMemo(() => recommendPlan(selectedUses), [selectedUses])

  if (token && !redirectingToPayment) return <Navigate to="/dashboard" replace />

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
    <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
      <div className="w-full max-w-3xl">
        {redirectingToPayment ? (
          <div
            className="rounded-2xl shadow-sm p-8 space-y-5"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
          >
            <h1
              className="text-2xl font-semibold text-center"
              style={{ color: 'var(--ms-text)' }}
            >
              Redirecting to payment…
            </h1>
            <p className="text-sm text-center" style={{ color: 'var(--ms-text-mid)' }}>
              Setting up your plan with Stripe. This window will redirect automatically.
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-col items-center mb-8 gap-4">
              <img
                src="/mainspring-logo.svg"
                alt="Mainspring"
                style={{
                  width: 'min(100%, 338px)',
                  height: 'auto',
                  display: 'block',
                  maxWidth: '100%',
                  objectFit: 'contain',
                }}
              />
              <div className="text-center">
                <h1
                  className="text-3xl font-semibold"
                  style={{ color: 'var(--ms-text)' }}
                >
                  Create Your Shop
                </h1>
                <p className="text-sm mt-1" style={{ color: 'var(--ms-text-mid)' }}>
                  Answer a few questions so we can recommend the right plan.
                </p>
              </div>
            </div>

            <div
              className="rounded-2xl shadow-sm p-8 space-y-5"
              style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
            >
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="rounded-xl p-3" style={{ border: '1px solid var(--ms-border)', backgroundColor: '#FBF8F3' }}>
                  <p className="mb-2 text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
                    What are you most likely to use the app for?
                  </p>
                  <div className="space-y-2">
                    {USE_CASE_OPTIONS.map((item) => {
                      const checked = selectedUses.includes(item.id)
                      return (
                        <label key={item.id} className="flex cursor-pointer items-start gap-2 rounded-lg p-2" style={{ backgroundColor: checked ? '#F6EFE3' : 'transparent' }}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleUseCase(item.id)}
                            className="mt-0.5"
                          />
                          <span>
                            <span className="block text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>{item.label}</span>
                            <span className="block text-xs" style={{ color: 'var(--ms-text-mid)' }}>{item.hint}</span>
                          </span>
                        </label>
                      )
                    })}
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
                      Recommended plan: <strong style={{ color: 'var(--ms-text)' }}>{PLAN_OPTIONS.find((p) => p.id === recommendedPlan)?.name}</strong>
                    </p>
                    <button
                      type="button"
                      onClick={() => setSelectedPlan(recommendedPlan)}
                      className="rounded-md px-2.5 py-1 text-xs font-semibold"
                      style={{ backgroundColor: '#EFE5D7', color: '#5A4632', border: '1px solid #D7C7B2' }}
                    >
                      Apply recommendation
                    </button>
                  </div>
                </div>

                <Input
                  label="Shop Name"
                  placeholder="Example: Heritage Watch Co"
                  value={tenantName}
                  onChange={(e) => setTenantName(e.target.value)}
                  required
                  autoFocus
                />
                <Input
                  label="Shop ID"
                  placeholder="heritagewatch"
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  required
                />
                <Input
                  label="Your Full Name"
                  placeholder="Jane Smith"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
                <Input
                  label="Email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <Input
                  label="Password"
                  type="password"
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

                <div className="pt-2">
                  <p className="mb-2 text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
                    Choose your plan
                  </p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {PLAN_OPTIONS.map((plan) => {
                      const active = selectedPlan === plan.id
                      return (
                        <button
                          key={plan.id}
                          type="button"
                          onClick={() => setSelectedPlan(plan.id)}
                          className="rounded-xl p-3 text-left"
                          style={{
                            border: active ? '2px solid #B0812A' : '1px solid var(--ms-border)',
                            backgroundColor: active ? '#F6EFE3' : 'var(--ms-surface)',
                          }}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>{plan.name}</p>
                              <p className="mt-1 text-xs" style={{ color: 'var(--ms-text-mid)' }}>{plan.description}</p>
                              <p className="mt-2 text-xs font-semibold" style={{ color: '#8D6420' }}>{plan.price}</p>
                            </div>
                            {active ? <Check size={16} style={{ color: '#8D6420' }} /> : null}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

                <Button type="submit" className="w-full justify-center py-2.5" disabled={loading || redirectingToPayment}>
                  {redirectingToPayment ? 'Setting up payment…' : loading ? 'Creating account…' : 'Create account & continue to payment'}
                </Button>
              </form>

              <p className="text-sm text-center" style={{ color: 'var(--ms-text-mid)' }}>
                Already have an account?{' '}
                <Link to="/login" className="underline" style={{ color: 'var(--ms-sidebar)' }}>
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
