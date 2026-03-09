import { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { WatchIcon } from 'lucide-react'
import { login } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Input, Button } from '@/components/ui'

export default function LoginPage() {
  const { token, login: setToken } = useAuth()
  const navigate = useNavigate()
  const [slug, setSlug] = useState('myshop')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: 'var(--cafe-bg)' }}
    >
      {/* Decorative grain overlay */}
      <div className="w-full max-w-sm">
        {/* Branding */}
        <div className="flex flex-col items-center mb-10 gap-3">
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
              WatchRepair
            </h1>
            <p
              className="text-xs tracking-[0.22em] uppercase mt-1"
              style={{ color: 'var(--cafe-text-muted)' }}
            >
              Atelier
            </p>
          </div>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl shadow-sm p-8 space-y-5"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1px solid var(--cafe-border)',
          }}
        >
          <p
            className="text-center text-sm mb-1"
            style={{ color: 'var(--cafe-text-mid)' }}
          >
            Sign in to your account
          </p>

          <div className="h-px" style={{ backgroundColor: 'var(--cafe-border)' }} />

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Shop ID"
              placeholder="myshop"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              required
              autoFocus
            />
            <Input
              label="Email"
              type="email"
              placeholder="admin@myshop.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error && (
              <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>
            )}
            <Button type="submit" className="w-full justify-center py-2.5" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
