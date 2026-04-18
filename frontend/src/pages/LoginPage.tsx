import { useEffect, useMemo, useState } from 'react'
import { useNavigate, Navigate, Link, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff } from 'lucide-react'
import axios from 'axios'
import { getRememberMe, getApiErrorMessage, login, multiSiteLogin, seedDemoData, setRememberMe } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { enableDemoMode, resetAllPageTutorials, resetDemoTour } from '@/lib/onboarding'

const ANIM_CSS = `
  @keyframes msSlideUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .ms-logo { animation: msSlideUp 0.68s cubic-bezier(.22,.68,0,1.0) both; }
  .ms-card { animation: msSlideUp 0.82s cubic-bezier(.22,.68,0,1.0) 0.18s both; }
`

export default function LoginPage() {
  const { token, login: setToken } = useAuth()
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
  const [btnHover, setBtnHover] = useState(false)

  useEffect(() => {
    if (searchParams.get('demo') !== '1') return
    setSlug(demoCreds.slug)
    setEmail(demoCreds.email)
    setPassword(demoCreds.password)
  }, [demoCreds.email, demoCreds.password, demoCreds.slug, searchParams])

  if (token) return <Navigate to="/dashboard" replace />

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      setRememberMe(rememberMe)
      const { data } = mode === 'multi'
        ? await multiSiteLogin(email, password)
        : await login(slug, email, password)
      enableDemoMode(false)
      setToken(data.access_token, data.refresh_token, data.expires_in_seconds)
      navigate('/dashboard')
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
      navigate('/dashboard')
    } catch {
      setError('Demo login is currently unavailable. Please try again shortly.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <style>{ANIM_CSS}</style>
      <div
        className="min-h-screen flex items-center justify-center px-4"
        style={{ background: 'linear-gradient(180deg, #F9F6F0 0%, #F1EAE0 52%, #E8DED1 100%)', position: 'relative', overflow: 'hidden' }}
      >
        {/* Subtle warm radial glow */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse 880px 600px at 50% 46%, rgba(184,149,86,0.09) 0%, rgba(122,93,46,0.03) 42%, transparent 70%)',
        }} />

        <div className="w-full max-w-md" style={{ position: 'relative', zIndex: 1 }}>

          {/* Logo + tagline */}
          <div className="ms-logo flex flex-col items-center mb-10">
            <div style={{
              background: 'linear-gradient(150deg, #FCF8F1 0%, #F0E7DA 100%)',
              borderRadius: '23px',
              padding: '14px 18px',
              boxShadow: '0 2px 6px rgba(120,80,20,0.08), 0 8px 24px rgba(120,80,20,0.13), 0 1px 0 rgba(255,255,255,0.7) inset',
              display: 'inline-block',
            }}>
              <img
                src="/mainspring-logo.svg"
                alt="Mainspring"
                style={{
                  width: 'min(88vw, 458px)',
                  height: 'auto',
                  display: 'block',
                  maxWidth: '100%',
                  objectFit: 'contain',
                }}
              />
            </div>
            <p style={{
              marginTop: '0.85rem',
              fontSize: '0.7rem',
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'var(--cafe-text-muted)',
            }}>
              Repair OS for the modern bench.
            </p>
          </div>

          {/* Card */}
          <div className="ms-card" style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1px solid #EAE0D4',
            borderRadius: '22px',
            padding: '2.6rem 2.4rem',
            boxShadow: [
              '0 1px 2px rgba(100,65,30,0.04)',
              '0 4px 10px rgba(100,65,30,0.07)',
              '0 14px 36px rgba(100,65,30,0.10)',
              '0 32px 56px rgba(100,65,30,0.06)',
              'inset 0 1px 0 rgba(255,255,255,0.65)',
            ].join(', '),
          }}>
            <p style={{
              textAlign: 'center',
              fontSize: '0.7rem',
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              color: 'var(--cafe-text-muted)',
              marginBottom: '1.4rem',
            }}>
              Sign in to your account
            </p>

            <div style={{
              height: '1px',
              background: 'linear-gradient(to right, transparent, #D8CCBE 25%, #D8CCBE 75%, transparent)',
              marginBottom: '1.6rem',
            }} />

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
              <div className="flex gap-2" style={{ marginBottom: '0.2rem' }}>
                <button
                  type="button"
                  onClick={() => setMode('single')}
                  style={{
                    flex: 1,
                    padding: '0.5rem',
                    borderRadius: '10px',
                    border: mode === 'single' ? '1px solid #C9A248' : '1px solid #D8CBBA',
                    backgroundColor: mode === 'single' ? '#F6EFE5' : 'var(--cafe-bg)',
                    color: mode === 'single' ? '#6B513A' : 'var(--cafe-text-muted)',
                    fontFamily: "'DM Sans', sans-serif",
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    cursor: 'pointer',
                  }}
                >
                  Shop Login
                </button>
                <button
                  type="button"
                  onClick={() => setMode('multi')}
                  style={{
                    flex: 1,
                    padding: '0.5rem',
                    borderRadius: '10px',
                    border: mode === 'multi' ? '1px solid #C9A248' : '1px solid #D8CBBA',
                    backgroundColor: mode === 'multi' ? '#F6EFE5' : 'var(--cafe-bg)',
                    color: mode === 'multi' ? '#6B513A' : 'var(--cafe-text-muted)',
                    fontFamily: "'DM Sans', sans-serif",
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    letterSpacing: '0.06em',
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
                style={{
                  width: '100%',
                  padding: '0.62rem',
                  borderRadius: '10px',
                  border: '1px solid #D8CBBA',
                  backgroundColor: '#F6EFE5',
                  color: '#6B513A',
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  letterSpacing: '0.07em',
                  textTransform: 'uppercase',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.75 : 1,
                }}
              >
                {loading ? 'Preparing Demo…' : 'Launch Interactive Demo'}
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
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--cafe-text-mid)' }}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={e => setRememberMeChecked(e.target.checked)}
                />
                Remember this device
              </label>

              {error && (
                <p style={{ fontSize: '0.85rem', color: '#C96A5A', margin: 0 }}>{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                onMouseEnter={() => setBtnHover(true)}
                onMouseLeave={() => setBtnHover(false)}
                style={{
                  width: '100%',
                  padding: '0.78rem',
                  marginTop: '0.35rem',
                  borderRadius: '11px',
                  border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  backgroundColor: btnHover && !loading ? '#AE8522' : '#C9A248',
                  color: '#FFF8EC',
                  fontFamily: "'DM Sans', sans-serif",
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  letterSpacing: '0.05em',
                  transform: btnHover && !loading ? 'translateY(-2px)' : 'translateY(0)',
                  boxShadow: btnHover && !loading
                    ? '0 4px 8px rgba(140,95,15,0.18), 0 8px 24px rgba(140,95,15,0.30)'
                    : '0 1px 3px rgba(140,95,15,0.12), 0 3px 9px rgba(140,95,15,0.20)',
                  transition: 'background-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease',
                  opacity: loading ? 0.70 : 1,
                }}
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            <p style={{ fontSize: '0.85rem', textAlign: 'center', marginTop: '1.25rem', color: 'var(--cafe-text-mid)' }}>
              New here?{' '}
              <Link to="/signup" style={{ color: 'var(--cafe-espresso)', textDecoration: 'underline' }}>
                Create your shop account
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Styled input used only on the login page ──────────────────────────────────
function LoginField({
  label, value, onChange, type = 'text', placeholder = '', autoComplete, autoFocus = false, showPasswordToggle = false,
}: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; placeholder?: string; autoComplete?: string; autoFocus?: boolean; showPasswordToggle?: boolean
}) {
  const [focused, setFocused] = useState(false)
  const [revealed, setRevealed] = useState(false)
  const isPassword = type === 'password'
  const inputType = isPassword && showPasswordToggle ? (revealed ? 'text' : 'password') : type
  const hasToggle = isPassword && showPasswordToggle

  return (
    <label style={{ display: 'block' }}>
      <span style={{
        display: 'block',
        marginBottom: '0.35rem',
        fontSize: '0.68rem',
        fontWeight: 600,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        color: 'var(--cafe-text-muted)',
      }}>
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
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: '100%',
            padding: '0.66rem 0.95rem',
            paddingRight: hasToggle ? '2.75rem' : '0.95rem',
            borderRadius: '11px',
            border: focused ? '1.5px solid #C9A248' : '1.5px solid #D8CBBA',
            backgroundColor: focused ? '#FFFDF8' : 'var(--cafe-bg)',
            color: 'var(--cafe-text)',
            fontFamily: "'DM Sans', sans-serif",
            fontSize: '0.9rem',
            outline: 'none',
            boxSizing: 'border-box',
            boxShadow: focused
              ? '0 0 0 3.5px rgba(201,162,72,0.18), 0 1px 4px rgba(140,95,15,0.10)'
              : '0 1px 2px rgba(100,65,30,0.05)',
            transition: 'border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease',
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
              right: '0.5rem',
              top: '50%',
              transform: 'translateY(-50%)',
              padding: '0.25rem',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              color: 'var(--cafe-text-muted)',
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
