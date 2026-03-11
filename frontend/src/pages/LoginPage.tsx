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
        style={{ backgroundColor: 'var(--cafe-bg)', position: 'relative', overflow: 'hidden' }}
      >
        {/* Subtle warm radial glow */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse 720px 480px at 50% 46%, rgba(201,162,72,0.14) 0%, transparent 70%)',
        }} />

        <div className="w-full max-w-sm" style={{ position: 'relative', zIndex: 1 }}>

          {/* Logo + tagline */}
          <div className="ms-logo flex flex-col items-center mb-10">
            <img
              src="/mainspring-logo.png"
              alt="Mainspring"
              style={{ width: '240px', height: 'auto', borderRadius: '12px' }}
            />
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
            border: '1px solid #E8DDD0',
            borderRadius: '20px',
            padding: '2.25rem 2.1rem',
            boxShadow: '0 2px 4px rgba(100,65,30,0.05), 0 8px 28px rgba(100,65,30,0.10), inset 0 1px 0 rgba(255,255,255,0.55)',
          }}>
            <p style={{
              textAlign: 'center',
              fontSize: '0.7rem',
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              color: 'var(--cafe-text-muted)',
              marginBottom: '1.25rem',
            }}>
              Sign in to your account
            </p>

            <div style={{ height: '1px', backgroundColor: '#EDE4D8', marginBottom: '1.5rem' }} />

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
                  padding: '0.72rem',
                  marginTop: '0.25rem',
                  borderRadius: '10px',
                  border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  backgroundColor: btnHover && !loading ? '#B8922A' : '#C9A248',
                  color: '#FFF8EC',
                  fontFamily: "'DM Sans', sans-serif",
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  letterSpacing: '0.04em',
                  transform: btnHover && !loading ? 'translateY(-2px)' : 'translateY(0)',
                  boxShadow: btnHover && !loading
                    ? '0 6px 18px rgba(180,130,40,0.38)'
                    : '0 2px 6px rgba(180,130,40,0.22)',
                  transition: 'background-color 0.17s ease, transform 0.17s ease, box-shadow 0.17s ease',
                  opacity: loading ? 0.72 : 1,
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
          padding: '0.62rem 0.9rem',
          borderRadius: '9px',
          border: focused ? '1.5px solid #C9A248' : '1.5px solid #DDD3C5',
          backgroundColor: focused ? '#FFFCF6' : 'var(--cafe-bg)',
          color: 'var(--cafe-text)',
          fontFamily: "'DM Sans', sans-serif",
          fontSize: '0.9rem',
          outline: 'none',
          boxSizing: 'border-box',
          boxShadow: focused ? '0 0 0 3px rgba(201,162,72,0.16)' : 'none',
          transition: 'border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease',
        }}
      />
    </label>
  )
}
