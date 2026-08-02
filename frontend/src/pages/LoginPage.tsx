import { useEffect, useMemo, useState } from 'react'
import { useNavigate, Navigate, Link, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff } from 'lucide-react'
import axios from 'axios'
import { getRememberMe, getApiErrorMessage, login, multiSiteLogin, seedDemoData, setRememberMe } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { applyMinitBrandingIfNeeded, isMinitTenantSlug } from '@/lib/minitBranding'
import { defaultHomePathForMinit, homePathAfterLogin, isMinitHqTenantSlug, seedLoginTenantHint } from '@/lib/minitProduct'
import { enableDemoMode, resetAllPageTutorials, resetDemoTour } from '@/lib/onboarding'
import { safeNextPath } from '@/lib/safeNext'
import { MKT, MARKETING_CSS } from '@/lib/marketingTheme'

export default function LoginPage() {
  const { token, sessionReady, login: setToken, planCode, tenantSlug } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  const demoCreds = useMemo(() => ({
    slug: String(import.meta.env.VITE_DEMO_TENANT_SLUG ?? 'myshop'),
    email: String(import.meta.env.VITE_DEMO_EMAIL ?? 'admin@admin.com'),
    password: String(import.meta.env.VITE_DEMO_PASSWORD ?? 'Admin'),
  }), [])

  const [slug, setSlug] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'single' | 'multi'>('single')
  const [rememberMe, setRememberMeChecked] = useState(getRememberMe)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
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
    return <Navigate to={nextPath ?? defaultHomePathForMinit(planCode, tenantSlug)} replace />
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      setRememberMe(rememberMe)
      const { data } = mode === 'multi'
        ? await multiSiteLogin(email, password)
        : await login(slug, email, password)
      if (mode === 'single') seedLoginTenantHint(slug)
      enableDemoMode(false)
      setToken(data.access_token, data.refresh_token, data.expires_in_seconds)
      if (mode === 'single') applyMinitBrandingIfNeeded(slug)
      if (mode === 'single' && isMinitHqTenantSlug(slug)) {
        void import('@/pages/minit/MinitOperationsPage')
      }
      navigate(nextPath ?? (mode === 'single' ? homePathAfterLogin(slug) : '/dashboard'))
    } catch (err) {
      if (axios.isAxiosError(err) && (!err.response || (err.response.status >= 500))) {
        setError('Server is temporarily unavailable. Please try again in a moment.')
      } else {
        const msg = getApiErrorMessage(err, mode === 'multi' ? 'Invalid email or password.' : 'Invalid shop ID, email, or password.')
        setError(err && typeof (err as { code?: string }).code === 'string' && (err as { code: string }).code === 'ECONNABORTED'
          ? 'Request timed out. Please try again in a moment.'
          : msg)
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
      const { data } = await login(demoCreds.slug, demoCreds.email, demoCreds.password)
      enableDemoMode(true)
      setToken(data.access_token, data.refresh_token, data.expires_in_seconds)
      // Run seed in background — don't block login if it hangs or fails
      seedDemoData()
        .then(() => {
          queryClient.invalidateQueries({ queryKey: ['customer-accounts'] })
          queryClient.invalidateQueries({ queryKey: ['jobs'] })
          queryClient.invalidateQueries({ queryKey: ['shoe-repair-jobs'] })
          queryClient.invalidateQueries({ queryKey: ['auto-key-jobs'] })
          queryClient.invalidateQueries({ queryKey: ['customers'] })
          queryClient.invalidateQueries({ queryKey: ['inbox'] })
        })
        .catch(() => { /* Non-fatal */ })
      resetDemoTour()
      resetAllPageTutorials()
      seedLoginTenantHint(demoCreds.slug)
      navigate(nextPath ?? homePathAfterLogin(demoCreds.slug))
    } catch {
      setError('Demo login is currently unavailable. Please try again shortly.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mkt-landing min-h-screen flex items-center justify-center px-4 py-10" style={{ background: MKT.oatmeal }}>
      <style>{MARKETING_CSS}</style>

      <div className="w-full max-w-md">
        {/* Logo + tagline */}
        <div className="mkt-slide-up flex flex-col items-center mb-8">
          <div style={{ border: `1px solid ${MKT.ink}`, background: MKT.paper, padding: '16px 22px', display: 'inline-block' }}>
            <img
              src={showMinitBranding ? '/minit-logo.jpg' : '/marketing/mainspring-logo-vermilion.svg'}
              alt={showMinitBranding ? 'Mister Minit' : 'Mainspring'}
              style={{
                width: showMinitBranding ? 'min(64vw, 240px)' : 'min(76vw, 320px)',
                height: 'auto',
                display: 'block',
                maxWidth: '100%',
                objectFit: 'contain',
              }}
            />
          </div>
          <p style={{ marginTop: 14, fontSize: 11, fontWeight: 700, letterSpacing: '0.24em', textTransform: 'uppercase', color: MKT.vermilionDeep }}>
            {showMinitBranding ? 'Mobile services booking' : 'Repair OS for the modern bench'}
          </p>
        </div>

        {/* Card */}
        <div className="mkt-slide-up-delay" style={{ background: MKT.paper, border: `1px solid ${MKT.ink}`, padding: '32px 28px' }}>
          <p style={{ textAlign: 'center', fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted, marginBottom: 20 }}>
            Sign in to your account
          </p>

          <div style={{ height: 1, background: MKT.ruleMid, marginBottom: 22 }} />

          <form onSubmit={handleSubmit} className="flex flex-col" style={{ gap: 16 }}>
            <div role="tablist" aria-label="Login type" className="flex" style={{ border: `1px solid ${MKT.ink}`, marginBottom: 2 }}>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'single'}
                onClick={() => setMode('single')}
                className="mkt-tab flex-1 whitespace-nowrap"
                style={{
                  padding: '10px 8px',
                  border: 'none',
                  borderRight: `1px solid ${MKT.ink}`,
                  background: mode === 'single' ? MKT.vermilion : 'transparent',
                  color: mode === 'single' ? MKT.ink : MKT.textBody,
                  fontFamily: "'Plus Jakarta Sans', sans-serif",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >
                Shop Login
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'multi'}
                onClick={() => setMode('multi')}
                className="mkt-tab flex-1 whitespace-nowrap"
                style={{
                  padding: '10px 8px',
                  border: 'none',
                  background: mode === 'multi' ? MKT.vermilion : 'transparent',
                  color: mode === 'multi' ? MKT.ink : MKT.textBody,
                  fontFamily: "'Plus Jakarta Sans', sans-serif",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                }}
              >
                Multi-Site
              </button>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={handleDemoLogin}
              className="mkt-btn-outline-ink"
              style={{ width: '100%', padding: '10px', fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}
            >
              {loading ? 'Preparing demo…' : 'Launch interactive demo'}
            </button>

            {mode === 'single' && (
              <LoginField
                label="Shop ID"
                value={slug}
                onChange={setSlug}
                placeholder="myshop"
                autoComplete="organization"
                autoFocus
              />
            )}
            <LoginField
              label="Email"
              value={email}
              onChange={setEmail}
              placeholder="you@example.com"
              autoComplete="email"
              type="email"
            />
            <LoginField
              label="Password"
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
              autoComplete="current-password"
              type="password"
              showPasswordToggle
            />
            <label className="flex items-center" style={{ gap: 8, fontSize: 13, color: MKT.textBody }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={e => setRememberMeChecked(e.target.checked)}
              />
              Remember this device
            </label>

            {error && (
              <p style={{ fontSize: 13, color: MKT.vermilionDeep, margin: 0 }}>{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mkt-btn-primary"
              style={{ width: '100%', padding: '13px', marginTop: 4, fontSize: 13, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p style={{ fontSize: 13, textAlign: 'center', marginTop: 20, color: MKT.textBody }}>
            New here?{' '}
            <Link to="/signup" style={{ color: MKT.vermilionDeep, fontWeight: 600 }}>
              Create your shop account
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Styled input used only on the login page ──────────────────────────────────
function LoginField({
  label, value, onChange, type = 'text', placeholder = '', autoComplete, autoFocus = false, showPasswordToggle = false,
}: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; placeholder?: string; autoComplete?: string; autoFocus?: boolean; showPasswordToggle?: boolean
}) {
  const [revealed, setRevealed] = useState(false)
  const isPassword = type === 'password'
  const inputType = isPassword && showPasswordToggle ? (revealed ? 'text' : 'password') : type
  const hasToggle = isPassword && showPasswordToggle

  return (
    <label style={{ display: 'block' }}>
      <span style={{ display: 'block', marginBottom: 6, fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: MKT.textMuted }}>
        {label}
      </span>
      <div style={{ position: 'relative' }}>
        <input
          type={inputType}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          required
          onChange={e => onChange(e.target.value)}
          className="mkt-input"
          style={{
            width: '100%',
            padding: '11px 14px',
            paddingRight: hasToggle ? 42 : 14,
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontSize: 14,
            boxSizing: 'border-box',
          }}
        />
        {hasToggle && (
          <button
            type="button"
            onClick={() => setRevealed(v => !v)}
            title={revealed ? 'Hide password' : 'Show password'}
            aria-label={revealed ? 'Hide password' : 'Show password'}
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              padding: 4,
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              color: MKT.textMuted,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {revealed ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>
    </label>
  )
}
