import { isNativeApp } from '@/lib/native'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, Navigate, Link, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  getRememberMe,
  getApiErrorMessage,
  login,
  multiSiteLogin,
  seedDemoData,
  setRememberMe,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import {
  applyMinitBrandingIfNeeded,
  isMinitTenantSlug,
} from '@/lib/minitBranding'
import {
  defaultHomePathForMinit,
  homePathAfterLogin,
  isMinitHqTenantSlug,
  seedLoginTenantHint,
} from '@/lib/minitProduct'
import {
  forgetShopId,
  readRememberedShopId,
  rememberShopId,
} from '@/lib/rememberedShopId'
import {
  enableDemoMode,
  isDemoModeEnabled,
  resetAllPageTutorials,
  resetDemoTour,
} from '@/lib/onboarding'
import { AUTO_KEY_VIEWS_KEY, clearSavedView } from '@/lib/savedViews'
import { persistTheme, readStoredTheme } from '@/context/ThemeContext'
import { safeNextPath } from '@/lib/safeNext'
import { markJustLoggedIn } from '@/lib/postLoginGate'
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  ChevronDown,
  Eye,
  EyeOff,
} from 'lucide-react'
import './LoginPage.css'

export default function LoginPage() {
  const {
    token,
    sessionReady,
    login: setToken,
    planCode,
    tenantSlug,
  } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  const demoCreds = useMemo(
    () => ({
      slug: String(import.meta.env.VITE_DEMO_TENANT_SLUG ?? 'myshop'),
      email: String(import.meta.env.VITE_DEMO_EMAIL ?? 'admin@admin.com'),
      password: String(import.meta.env.VITE_DEMO_PASSWORD ?? 'Admin'),
    }),
    [],
  )

  // Pre-filled with the Shop ID this device last signed in to (or claimed an invite for).
  const [slug, setSlug] = useState(readRememberedShopId)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const [rememberMe, setRememberMeChecked] = useState(getRememberMe)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [editShop, setEditShop] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const showMinitBranding = isMinitTenantSlug(slug)

  useEffect(() => {
    if (searchParams.get('demo') !== '1') return
    setSlug(demoCreds.slug)
    setEmail(demoCreds.email)
    setPassword(demoCreds.password)
  }, [demoCreds.email, demoCreds.password, demoCreds.slug, searchParams])

  useEffect(() => {
    applyMinitBrandingIfNeeded(slug)
  }, [slug])

  // Optional post-login destination (?next=/jobs/…) — same-origin paths only
  const nextPath = safeNextPath(searchParams.get('next'))

  if (token && sessionReady) {
    const demoLanding = isDemoModeEnabled() || searchParams.get('demo') === '1'
    return (
      <Navigate
        to={
          nextPath ??
          (demoLanding
            ? '/dashboard'
            : defaultHomePathForMinit(planCode, tenantSlug))
        }
        replace
      />
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      setRememberMe(rememberMe)
      // A blank Shop ID signs in by email and password alone, so an owner who
      // has forgotten theirs isn't locked out.
      const byEmail = !slug.trim()
      const { data } = byEmail
        ? await multiSiteLogin(email, password)
        : await login(slug, email, password)
      if (!byEmail) {
        seedLoginTenantHint(slug)
        if (rememberMe) rememberShopId(slug)
        else forgetShopId()
      }
      enableDemoMode(false)
      setToken(data.access_token, data.refresh_token, data.expires_in_seconds)
      if (!byEmail) applyMinitBrandingIfNeeded(slug)
      if (!byEmail && isMinitHqTenantSlug(slug)) {
        void import('@/pages/minit/MinitOperationsPage')
      }
      markJustLoggedIn()
      navigate(nextPath ?? (!byEmail ? homePathAfterLogin(slug) : '/dashboard'))
    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        (!err.response || err.response.status >= 500)
      ) {
        setError(
          'Server is temporarily unavailable. Please try again in a moment.',
        )
      } else {
        const msg = getApiErrorMessage(
          err,
          !slug.trim()
            ? 'Invalid email or password.'
            : 'Invalid shop ID, email, or password.',
        )
        setError(
          err &&
            typeof (err as { code?: string }).code === 'string' &&
            (err as { code: string }).code === 'ECONNABORTED'
            ? 'Request timed out. Please try again in a moment.'
            : msg,
        )
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleDemoLogin() {
    setError('')
    setLoading(true)
    try {
      setRememberMe(true)
      const { data } = await login(
        demoCreds.slug,
        demoCreds.email,
        demoCreds.password,
      )
      enableDemoMode(true)
      if (readStoredTheme() === 'minit') persistTheme('warm')
      setToken(data.access_token, data.refresh_token, data.expires_in_seconds)
      // Rebuilding the demo shop is not something to hold the login on: it
      // waited up to 20s before the dashboard would open, for work the user
      // does not need finished before they are in. Kick it off and let the
      // invalidate pull the fresh data in once it lands.
      void seedDemoData()
        .then(() => {
          void queryClient.invalidateQueries()
        })
        .catch(() => {
          /* Non-fatal: the dashboard still opens and the seed can be retried. */
        })
      resetDemoTour()
      resetAllPageTutorials()
      clearSavedView(AUTO_KEY_VIEWS_KEY)
      seedLoginTenantHint(demoCreds.slug)
      markJustLoggedIn()
      navigate(nextPath ?? '/dashboard')
    } catch {
      setError('Demo login is currently unavailable. Please try again shortly.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="ms-login">
      <section className="ms-login-form-panel" aria-labelledby="login-title">
        <header className="ms-login-top">
          {!isNativeApp && (
            <Link to="/" className="ms-login-back">
              <ArrowLeft size={16} aria-hidden="true" /> Back to website
            </Link>
          )}
          <Link to="/customer-portal" className="ms-login-track">
            Track a repair <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
        </header>
        <div className="ms-login-form-wrap">
          <Link
            to="/"
            className="ms-login-brand"
            aria-label={
              showMinitBranding ? 'Mister Minit home' : 'Mainspring home'
            }
          >
            {showMinitBranding ? (
              <img
                className="ms-login-minit"
                src="/minit-logo.jpg"
                alt="Mister Minit"
              />
            ) : (
              <>
                <img src="/mainspring-icon.svg" alt="" width="38" height="38" />
                <span>
                  Mainspring<span className="ms-login-brand-dot">.</span>
                </span>
              </>
            )}
          </Link>
          <h1 id="login-title">Welcome back.</h1>
          <p className="ms-login-intro">
            Log in to your {showMinitBranding ? 'Mister Minit' : 'Mainspring'}{' '}
            workspace.
          </p>
          <form onSubmit={handleSubmit} className="ms-login-form">
            <label htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              name="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@yourshop.com.au"
              required
            />
            <label htmlFor="login-password">Password</label>
            <div className="ms-login-password">
              <input
                id="login-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <div className="ms-login-shop">
              <button
                type="button"
                className="ms-login-shop-toggle"
                aria-expanded={editShop}
                aria-controls="login-shop-options"
                onClick={() => setEditShop(!editShop)}
              >
                {slug.trim() ? (
                  <>
                    Signing in to <strong>{slug.trim()}</strong>
                  </>
                ) : (
                  'Use a Shop ID'
                )}
                <ChevronDown size={15} aria-hidden="true" />
              </button>
              {editShop && (
                <div id="login-shop-options">
                  <label htmlFor="login-shop">
                    Shop ID <span>(optional)</span>
                  </label>
                  <input
                    id="login-shop"
                    name="shop"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                    placeholder="e.g. myshop"
                    autoComplete="organization"
                  />
                  <p>Leave blank to sign in with your email address.</p>
                </div>
              )}
            </div>
            <label className="ms-login-remember">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMeChecked(e.target.checked)}
              />
              Remember this device
            </label>
            {error && (
              <p className="ms-login-error" role="alert">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="ms-login-submit"
            >
              {loading ? 'Logging in…' : 'Log in'}
              <ArrowRight size={17} aria-hidden="true" />
            </button>
          </form>
          {!isNativeApp && (
            <p className="ms-login-signup">
              New to Mainspring?{' '}
              <Link to="/signup">
                Start your free trial{' '}
                <ArrowUpRight size={13} aria-hidden="true" />
              </Link>
            </p>
          )}
          <div className="ms-login-demo">
            <span>Just having a look?</span>
            <button type="button" disabled={loading} onClick={handleDemoLogin}>
              {loading ? 'Preparing demo…' : 'Explore the demo'}{' '}
              <ArrowUpRight size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
        <footer className="ms-login-footer">
          <span>© {new Date().getFullYear()} Mainspring</span>
          <Link to="/privacy">Privacy</Link>
        </footer>
      </section>
      <aside className="ms-login-product" aria-label="About Mainspring">
        <div className="ms-login-product-copy">
          <p className="ms-login-eyebrow">Made for your working day</p>
          <h2>
            Your working day,
            <br />
            <span>in good order.</span>
          </h2>
          <p>
            One clear place for the jobs on your bench,
            <br />
            the customers you serve and the work ahead.
          </p>
        </div>
        <figure className="ms-login-product-shot">
          <div aria-hidden="true">
            <i />
            <i />
            <i />
            <span>mainspring.au</span>
          </div>
          <img
            src="/marketing/product/watch-jobs.jpg"
            alt="Mainspring watch repair list showing sample jobs, customers, statuses and quotes"
            width="1349"
            height="809"
          />
          <figcaption>Real Mainspring screen · Sample records</figcaption>
        </figure>
        <div className="ms-login-product-bottom">
          <span>Watch repairs</span>
          <span>Shoe repairs</span>
          <span>Mobile services</span>
        </div>
      </aside>
    </main>
  )
}
