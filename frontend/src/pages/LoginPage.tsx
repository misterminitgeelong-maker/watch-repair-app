import { useState } from 'react'
import { useNavigate, Navigate, Link } from 'react-router-dom'
import { login } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

const ANIM_CSS = `
  @keyframes msSlideUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .ms-logo { animation: msSlideUp 0.55s cubic-bezier(.22,.68,0,1.1) both; }
  .ms-card { animation: msSlideUp 0.65s cubic-bezier(.22,.68,0,1.1) 0.13s both; }
`

export default function LoginPage() {
  const { token, login: setToken } = useAuth()
  const navigate = useNavigate()
  const [slug, setSlug] = useState('myshop')
  const [email, setEmail] = useState('admin@admin.com')
  const [password, setPassword] = useState('Admin')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [btnHover, setBtnHover] = useState(false)

  if (token) return <Navigate to="/" replace />

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await login(slug, email, password)
      setToken(data.access_token)
      navigate('/')
    } catch {
      setError('Invalid shop ID, email, or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <style>{ANIM_CSS}</style>
      <div
        className="min-h-screen flex items-center justify-center px-4"
        style={{ background: 'linear-gradient(180deg, #FBF6EE 0%, #F5ECD9 48%, #EDE2CE 100%)', position: 'relative', overflow: 'hidden' }}
      >
        {/* Subtle warm radial glow */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse 880px 600px at 50% 46%, rgba(201,162,72,0.18) 0%, rgba(185,142,55,0.07) 42%, transparent 70%)',
        }} />

        <div className="w-full max-w-sm" style={{ position: 'relative', zIndex: 1 }}>

          {/* Logo + tagline */}
          <div className="ms-logo flex flex-col items-center mb-10">
            <div style={{
              background: 'linear-gradient(150deg, #FDF8F0 0%, #F5EAD8 100%)',
              borderRadius: '23px',
              padding: '14px 18px',
              boxShadow: '0 2px 6px rgba(120,80,20,0.08), 0 8px 24px rgba(120,80,20,0.13), 0 1px 0 rgba(255,255,255,0.7) inset',
              display: 'inline-block',
            }}>
              <img
                src="/mainspring-logo.png"
                alt="Mainspring"
                style={{ width: '276px', height: 'auto', display: 'block', borderRadius: '10px' }}
              />
            </div>
            <p style={{
              marginTop: '0.85rem',
              fontSize: '0.7rem',
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'var(--cafe-text-muted)',
            }}>
              Repair OS for modern watchmakers
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
              background: 'linear-gradient(to right, transparent, #DDD0BE 25%, #DDD0BE 75%, transparent)',
              marginBottom: '1.6rem',
            }} />

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
              <LoginField label="Shop ID"   value={slug}     onChange={setSlug}     placeholder="myshop"          autoFocus />
              <LoginField label="Email"     value={email}    onChange={setEmail}    placeholder="you@example.com"  type="email" />
              <LoginField label="Password"  value={password} onChange={setPassword} placeholder="••••••••"         type="password" />

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
  label, value, onChange, type = 'text', placeholder = '', autoFocus = false,
}: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; placeholder?: string; autoFocus?: boolean
}) {
  const [focused, setFocused] = useState(false)
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
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        autoFocus={autoFocus}
        required
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%',
          padding: '0.66rem 0.95rem',
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
    </label>
  )
}
