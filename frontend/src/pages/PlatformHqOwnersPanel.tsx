import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createPlatformHqInvite, getApiErrorMessage, listPlatformHqOwners, revokePlatformHqInvite } from '@/lib/api'
import { Spinner } from '@/components/ui'

export default function PlatformHqOwnersPanel() {
  const cache = useQueryClient()
  const query = useQuery({ queryKey: ['platform-hq-owners'], queryFn: () => listPlatformHqOwners().then(r => r.data) })
  const [account, setAccount] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [sendEmail, setSendEmail] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const invite = useMutation({
    mutationFn: () => {
      const selected = query.data?.accounts.find(a => `${a.parent_account_id}:${a.tenant_id}` === account)
      if (!selected) throw new Error('Select an HQ account.')
      return createPlatformHqInvite({ parent_account_id: selected.parent_account_id, tenant_id: selected.tenant_id, email: email.trim(), full_name: name.trim(), send_email: sendEmail }).then(r => r.data)
    },
    onSuccess: () => { setCopied(false); setError(''); void cache.invalidateQueries({ queryKey: ['platform-hq-owners'] }) },
    onError: err => setError(getApiErrorMessage(err, 'Could not create the invitation.')),
  })
  const revoke = useMutation({ mutationFn: revokePlatformHqInvite, onSuccess: () => { setError(''); void cache.invalidateQueries({ queryKey: ['platform-hq-owners'] }) }, onError: err => setError(getApiErrorMessage(err, 'Could not revoke the invitation.')) })
  if (query.isLoading) return <Spinner />
  if (query.isError) return <div role="alert">Could not load HQ accounts. <button className="console-button" onClick={() => void query.refetch()}>Try again</button></div>
  return <div className="space-y-5">
    <section className="console-panel">
      <h2>Invite an HQ owner</h2>
      <p className="console-subtitle">Give an owner management access to an existing HQ network. Links expire in seven days and can be used once. A fresh invite replaces any pending link for the same account and email.</p>
      <form className="space-y-4 mt-4" onSubmit={e => { e.preventDefault(); setError(''); invite.mutate() }}>
        <label className="block text-sm">HQ account<select className="block w-full border rounded p-2 mt-1" required value={account} onChange={e => setAccount(e.target.value)}><option value="">Select HQ account…</option>{query.data?.accounts.map(a => <option key={`${a.parent_account_id}:${a.tenant_id}`} value={`${a.parent_account_id}:${a.tenant_id}`}>{a.name} · {a.tenant_name} ({a.tenant_slug})</option>)}</select></label>
        {!query.data?.accounts.length && <p>No active HQ accounts are configured. An HQ account must be linked to its network before inviting an owner.</p>}
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">Owner name<input className="block w-full border rounded p-2 mt-1" required maxLength={200} value={name} onChange={e => setName(e.target.value)} /></label>
          <label className="block text-sm">Owner email<input className="block w-full border rounded p-2 mt-1" type="email" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sendEmail} onChange={e => setSendEmail(e.target.checked)} />Email the invitation to this owner</label>
        <button className="console-button primary" disabled={invite.isPending || !account}>{invite.isPending ? 'Creating…' : sendEmail ? 'Create & email invite' : 'Create invite link'}</button>
      </form>
      {error && <p className="console-error mt-4" role="alert">{error}</p>}
      {invite.data && <div className="mt-5 space-y-3" role="status">
        <p>{invite.data.email_sent ? `Invitation emailed to ${invite.data.email}.` : `Link created for ${invite.data.email}. ${sendEmail ? 'Email delivery was unavailable. Share the link below.' : 'Share the link below.'}`}</p>
        <p className="text-sm">Expires {new Date(invite.data.expires_at).toLocaleString('en-AU')}.</p>
        <label className="block text-sm">Invite link<input className="block w-full border rounded p-2 mt-1" readOnly value={invite.data.invite_url} onFocus={e => e.currentTarget.select()} /></label>
        <button type="button" className="console-button" onClick={() => { void navigator.clipboard.writeText(invite.data!.invite_url).then(() => setCopied(true)).catch(() => setError('Copy failed. Select and copy the link above.')) }}>{copied ? 'Copied' : 'Copy invite link'}</button>
      </div>}
    </section>
    <section className="console-panel"><h2>Recent HQ invitations</h2><div className="mt-3 space-y-4">
      {!query.data?.invites.length && <p>No HQ invitations yet.</p>}
      {query.data?.invites.map(i => <div key={i.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-3"><div><strong>{i.full_name}</strong><p className="text-sm">{i.email} · {query.data.accounts.find(a => a.tenant_id === i.tenant_id && a.parent_account_id === i.parent_account_id)?.name ?? 'HQ account'}</p><p className="text-xs">{i.status} · expires {new Date(i.expires_at).toLocaleDateString('en-AU')}</p></div>{i.status === 'pending' && <button className="console-button" disabled={revoke.isPending} onClick={() => { revoke.mutate(i.id); if (invite.data?.id === i.id) invite.reset() }}>Revoke invite</button>}</div>)}
    </div></section>
  </div>
}
