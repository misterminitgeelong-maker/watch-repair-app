import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { acceptHqOwnerInvite, getApiErrorMessage, getHqOwnerInvite } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import { rememberShopId } from '@/lib/rememberedShopId'
import { Button, Spinner } from '@/components/ui'

export default function HqOwnerInvitePage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['hq-invite', token], queryFn: () => getHqOwnerInvite(token!).then(r => r.data), enabled: !!token, retry: false })
  const accept = useMutation({ mutationFn: () => acceptHqOwnerInvite(token!, password).then(r => r.data), onSuccess: data => {
    if (query.data) rememberShopId(query.data.tenant_slug)
    login(data.access_token, data.refresh_token, data.expires_in_seconds)
    navigate('/dashboard', { replace: true })
  }, onError: err => setError(getApiErrorMessage(err, 'Could not accept the invitation.')) })
  return <main className="min-h-screen flex items-center justify-center p-5" style={{ background: 'var(--ms-bg)' }}><section className="w-full max-w-md space-y-5 rounded-xl border p-6" style={{ background: 'var(--ms-panel, white)', color: 'var(--ms-text)' }}>
    <img src="/mainspring-logo.svg" alt="Mainspring" className="w-40" />
    {query.isLoading ? <Spinner /> : query.isError ? <><h1 className="text-xl font-semibold">Invitation unavailable</h1><p role="alert">{getApiErrorMessage(query.error, 'Ask your platform admin for a new invitation.')}</p></> : query.data && <>
      <h1 className="text-xl font-semibold">Join {query.data.name} HQ</h1>
      <p>Welcome, {query.data.full_name}. This invitation gives you management access to this HQ network.</p>
      <p className="text-sm">Email: <strong>{query.data.email}</strong><br />Account ID: <strong>{query.data.tenant_slug}</strong></p>
      <p className="text-sm">{query.data.existing_account ? 'Enter your existing password for this account to accept.' : 'Create a password for your HQ login.'}</p>
      <form className="space-y-4" onSubmit={e => { e.preventDefault(); setError(''); if (!query.data.existing_account && password !== confirm) { setError('Passwords do not match.'); return } accept.mutate() }}>
        <label className="block text-sm">{query.data.existing_account ? 'Existing password' : 'New password'}<input className="block w-full border rounded p-2 mt-1" required type="password" autoComplete={query.data.existing_account ? 'current-password' : 'new-password'} minLength={query.data.existing_account ? 1 : 8} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></label>
        {!query.data.existing_account && <label className="block text-sm">Confirm password<input className="block w-full border rounded p-2 mt-1" required type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} /></label>}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <Button type="submit" disabled={accept.isPending}>{accept.isPending ? 'Accepting…' : 'Accept HQ invitation'}</Button>
      </form>
      {query.data.existing_account && <Link to="/login" className="text-sm underline">Forgot your password? Go to login.</Link>}
    </>}
  </section></main>
}
