import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { CheckCircle, KeyRound } from 'lucide-react'
import { completeShopOwnerInvite, getApiErrorMessage, getShopOwnerInvitePublic } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { Button, Card, Input, Spinner } from '@/components/ui'

function loadErrorCopy(error: unknown): { title: string; body: string } {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return { title: status === 404 ? 'Invalid link' : 'This invite is no longer valid', body: detail }
    }
    if (status === 404) {
      return { title: 'Invalid link', body: 'This invite link is not valid. Check the URL or contact HQ.' }
    }
  }
  return { title: 'Unable to load invite', body: 'Something went wrong. Please try again or contact HQ.' }
}

export default function ShopOwnerInvitePage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { login: setSession } = useAuth()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  const { data: invite, isLoading, isError, error: loadError } = useQuery({
    queryKey: ['shop-owner-invite', token],
    queryFn: () => getShopOwnerInvitePublic(token!).then((r) => r.data),
    enabled: !!token,
    retry: false,
  })

  const mut = useMutation({
    mutationFn: () => completeShopOwnerInvite(token!, { full_name: fullName.trim(), email: email.trim(), password }),
    onSuccess: ({ data }) => {
      setSession(data.access_token, data.refresh_token, data.expires_in_seconds)
      navigate('/dashboard', { replace: true })
    },
    onError: (err) => setError(getApiErrorMessage(err, 'Could not set up your login. Please try again.')),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (!fullName.trim()) return setError('Your name is required.')
    if (!email.trim() || !email.includes('@')) return setError('A valid email is required.')
    if (password.length < 8) return setError('Password must be at least 8 characters long.')
    if (password !== confirmPassword) return setError('Passwords do not match.')
    mut.mutate()
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-10"
      style={{ backgroundColor: 'var(--ms-bg, #F7F4EF)' }}
    >
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 justify-center mb-6" style={{ color: 'var(--ms-text-muted)' }}>
          <KeyRound size={18} />
          <span className="text-sm font-medium">Set up your shop login</span>
        </div>

        {isLoading && (
          <Card className="p-8">
            <Spinner />
          </Card>
        )}

        {isError && (
          <Card className="p-8 text-center">
            <h1 className="text-lg font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>
              {loadErrorCopy(loadError).title}
            </h1>
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              {loadErrorCopy(loadError).body}
            </p>
          </Card>
        )}

        {invite && (
          <Card className="p-8">
            <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--ms-text)' }}>
              Claim your {invite.tenant_name}
              {invite.shop_number ? ` (#${invite.shop_number})` : ''} login
            </h1>
            <p className="text-sm mb-6" style={{ color: 'var(--ms-text-muted)' }}>
              Replace the shared HQ login (currently <strong>{invite.masked_email}</strong>) with your own email and
              password. Once you save, you&rsquo;ll be signed in.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Your full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                required
              />
              <Input
                label="Your email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
              <Input
                label="New password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              <Input
                label="Confirm password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              {error && <p className="text-sm" style={{ color: '#C96A5A' }}>{error}</p>}
              <Button type="submit" className="w-full" disabled={mut.isPending}>
                {mut.isPending ? 'Setting up…' : 'Save & sign in'}
              </Button>
            </form>
          </Card>
        )}

        {mut.isSuccess && (
          <div className="mt-4 flex items-center gap-2 justify-center text-sm" style={{ color: '#1A6A3A' }}>
            <CheckCircle size={16} />
            <span>You&rsquo;re all set.</span>
          </div>
        )}
      </div>
    </div>
  )
}
