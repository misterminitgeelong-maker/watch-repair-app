import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { WatchIcon } from 'lucide-react'
import { signup } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Input } from '@/components/ui'

export default function SignupPage() {
  const navigate = useNavigate()
  const { token, login: setToken } = useAuth()

  const [tenantName, setTenantName] = useState('')
  const [tenantSlug, setTenantSlug] = useState('')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (token) return <Navigate to="/dashboard" replace />

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
      })
      setToken(data.access_token)
      navigate('/dashboard')
    } catch (err: unknown) {
      const apiMessage =
        typeof err === 'object' &&
        err !== null &&
        'response' in err &&
        typeof (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(typeof apiMessage === 'string' ? apiMessage : 'Could not create account. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <div className="w-full max-w-lg">
        <div className="flex flex-col items-center mb-8 gap-3">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center shadow-lg"
            style={{ backgroundColor: 'var(--cafe-espresso)' }}
          >
            <WatchIcon size={28} style={{ color: 'var(--cafe-gold)' }} />
          </div>
          <div className="text-center">
            <h1
              className="text-3xl font-semibold"
              style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
            >
              Create Your Shop
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-mid)' }}>
              Set up your account and start tracking repairs.
            </p>
          </div>
        </div>

        <div
          className="rounded-2xl shadow-sm p-8 space-y-5"
          style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
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

            {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}

            <Button type="submit" className="w-full justify-center py-2.5" disabled={loading}>
              {loading ? 'Creating account…' : 'Create account'}
            </Button>
          </form>

          <p className="text-sm text-center" style={{ color: 'var(--cafe-text-mid)' }}>
            Already have an account?{' '}
            <Link to="/login" className="underline" style={{ color: 'var(--cafe-espresso)' }}>
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
