import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
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

export default function SignupCheckoutPage() {
  const { token } = useAuth()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState('')

  const selectedPlan = useMemo(() => {
    const raw = searchParams.get('plan')
    if (!raw) return null
    return VALID_PLANS.includes(raw as PlanCode) ? (raw as PlanCode) : null
  }, [searchParams])

  useEffect(() => {
    if (!token || !selectedPlan) return
    const plan: PlanCode = selectedPlan

    let canceled = false

    async function startCheckout() {
      try {
        const { data } = await createBillingCheckoutForPlan(plan)
        if (!canceled) {
          window.location.assign(data.checkout_url)
        }
      } catch (err: unknown) {
        if (canceled) return
        const apiMessage =
          typeof err === 'object' &&
          err !== null &&
          'response' in err &&
          typeof (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : undefined
        setError(typeof apiMessage === 'string' ? apiMessage : 'Could not start Stripe checkout. Please try again.')
      }
    }

    startCheckout()
    return () => {
      canceled = true
    }
  }, [token, selectedPlan])

  if (!token) return <Navigate to="/login" replace />
  if (!selectedPlan) return <Navigate to="/signup" replace />

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <div
        className="w-full max-w-xl rounded-2xl shadow-sm p-8 space-y-5"
        style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
      >
        <h1
          className="text-2xl font-semibold text-center"
          style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
        >
          Redirecting to secure payment...
        </h1>
        <p className="text-sm text-center" style={{ color: 'var(--cafe-text-mid)' }}>
          We are preparing your Stripe checkout session for the selected plan.
        </p>

        {error ? (
          <div className="space-y-3">
            <p className="text-sm text-center" style={{ color: '#C96A5A' }}>
              {error}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Button type="button" className="w-full justify-center" onClick={() => window.location.reload()}>
                Try Again
              </Button>
              <Link to="/accounts" className="w-full">
                <Button type="button" variant="secondary" className="w-full justify-center">
                  Go to Accounts
                </Button>
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
