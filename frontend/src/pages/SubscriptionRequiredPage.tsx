import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { createBillingCheckoutForPlan, type PlanCode } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui'

const VALID_PLANS: PlanCode[] = [
  'basic_watch',
  'basic_shoe',
  'basic_auto_key',
  'basic_watch_shoe',
  'basic_watch_auto_key',
  'basic_shoe_auto_key',
  'basic_all_tabs',
  'pro',
]

export default function SubscriptionRequiredPage() {
  const { planCode, logout, refreshSession } = useAuth()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const selectedPlan = useMemo(() => {
    const raw = searchParams.get('plan')
    if (raw && VALID_PLANS.includes(raw as PlanCode)) return raw as PlanCode
    return planCode && VALID_PLANS.includes(planCode) ? planCode : 'basic_watch'
  }, [searchParams, planCode])

  async function continueToCheckout() {
    setError('')
    setLoading(true)
    try {
      const { data } = await createBillingCheckoutForPlan(selectedPlan)
      window.location.assign(data.checkout_url)
    } catch (err: unknown) {
      const apiMessage =
        typeof err === 'object' &&
        err !== null &&
        'response' in err &&
        typeof (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(typeof apiMessage === 'string' ? apiMessage : 'Could not open checkout. Try again in a moment.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-6 py-10">
      <h1
        className="text-2xl font-semibold"
        style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
      >
        Complete subscription to continue
      </h1>
      <p className="mt-3 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
        Your workspace was created, but payment was not completed. Finish checkout with Stripe to access the app. If you
        closed the payment page by mistake, you can open it again below.
      </p>

      {error && (
        <p className="mt-4 text-sm" style={{ color: '#C96A5A' }}>
          {error}
        </p>
      )}

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button onClick={() => void continueToCheckout()} disabled={loading} className="sm:flex-1">
          {loading ? 'Opening…' : 'Continue to secure payment'}
        </Button>
        <Button variant="secondary" type="button" onClick={() => void refreshSession()} disabled={loading}>
          I already paid — refresh
        </Button>
      </div>

      <p className="mt-8 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
        Wrong account?{' '}
        <button type="button" className="underline hover:opacity-90" onClick={() => logout()}>
          Sign out
        </button>
      </p>
    </div>
  )
}
