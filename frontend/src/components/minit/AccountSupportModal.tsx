import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  changeAccountEmail,
  formatTenantLabel,
  getApiErrorMessage,
  listSiteAccounts,
  listSiteMessageLogs,
  sendAccountResetLink,
  type HqAccount,
  type ParentAccountSite,
} from '@/lib/api'
import { useToast } from '@/lib/toast'
import { Button, Input, Modal, Spinner } from '@/components/ui'

const muted = { color: 'var(--ms-text-muted)' }

function when(value?: string | null) {
  return value ? new Date(value).toLocaleString('en-AU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'never'
}

function AccountRow({ tenantId, account }: { tenantId: string; account: HqAccount }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [email, setEmail] = useState(account.email)
  const [error, setError] = useState('')
  const key = ['hq-site-accounts', tenantId]

  const resetMut = useMutation({
    mutationFn: () => sendAccountResetLink(tenantId, account.user_id).then(r => r.data),
    onSuccess: res => {
      setError('')
      const via = [res.email_sent && 'email', res.sms_sent && 'text'].filter(Boolean).join(' and ')
      if (via) toast.success(`Reset link sent by ${via}.`)
      else setError('The link was created but could not be delivered. Check their email and mobile, then try again.')
      qc.invalidateQueries({ queryKey: key })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not send the reset link.')),
  })
  const emailMut = useMutation({
    mutationFn: () => changeAccountEmail(tenantId, account.user_id, email.trim()).then(r => r.data),
    onSuccess: () => {
      setError('')
      setEditing(false)
      toast.success('Login email changed. They have been signed out.')
      qc.invalidateQueries({ queryKey: key })
    },
    onError: err => setError(getApiErrorMessage(err, 'Could not change the email.')),
  })

  return (
    <div className="rounded border p-3 space-y-2" style={{ borderColor: 'var(--ms-border)' }}>
      <div>
        <p className="text-sm font-medium">{account.full_name || account.email}</p>
        <p className="text-xs" style={muted}>
          {account.email} · {account.role}
          {account.is_active ? '' : ' · deactivated'}
        </p>
        <p className="text-xs" style={muted}>
          Last sign-in: {when(account.last_login_at)}
          {account.latest_link_status ? ` · reset link ${account.latest_link_status}` : ''}
        </p>
      </div>
      {account.is_hq_login ? (
        <p className="text-xs" style={muted}>
          This is a copy of an HQ login. Use "Invite owner" to hand it to the shop.
        </p>
      ) : editing ? (
        <div className="space-y-2">
          <Input label="Login email" type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="off" />
          <div className="flex gap-2">
            <Button className="text-xs px-3 py-1.5" onClick={() => emailMut.mutate()} disabled={emailMut.isPending}>
              {emailMut.isPending ? 'Saving…' : 'Save email'}
            </Button>
            <Button variant="ghost" className="text-xs px-3 py-1.5" onClick={() => { setEditing(false); setEmail(account.email) }}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            className="text-xs px-3 py-1.5"
            onClick={() => resetMut.mutate()}
            disabled={resetMut.isPending || !account.is_active}
            title="Emails and texts them a one-time link to choose a new password. You never see it."
          >
            {resetMut.isPending ? 'Sending…' : 'Send reset link'}
          </Button>
          <Button variant="ghost" className="text-xs px-3 py-1.5" onClick={() => setEditing(true)}>
            Change email
          </Button>
        </div>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function AccountSupportModal({ site, onClose }: { site: ParentAccountSite; onClose: () => void }) {
  const accounts = useQuery({
    queryKey: ['hq-site-accounts', site.tenant_id],
    queryFn: () => listSiteAccounts(site.tenant_id).then(r => r.data),
  })
  const logs = useQuery({
    queryKey: ['hq-site-message-logs', site.tenant_id],
    queryFn: () => listSiteMessageLogs(site.tenant_id).then(r => r.data),
  })

  return (
    <Modal title={`Accounts — ${formatTenantLabel(site.tenant_name, site.shop_number)}`} onClose={onClose} size="wide">
      <div className="space-y-5">
        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Who can sign in</h3>
          {accounts.isLoading ? (
            <Spinner />
          ) : accounts.isError ? (
            <p className="text-sm text-red-600">{getApiErrorMessage(accounts.error, 'Could not load accounts.')}</p>
          ) : (
            (accounts.data ?? []).map(a => <AccountRow key={a.user_id} tenantId={site.tenant_id} account={a} />)
          )}
          <p className="text-xs" style={muted}>
            Passwords are never shown. Every change here is recorded in the HQ activity log.
          </p>
        </section>
        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Recent texts and emails</h3>
          {logs.isLoading ? (
            <Spinner />
          ) : (logs.data ?? []).length === 0 ? (
            <p className="text-xs" style={muted}>Nothing sent yet.</p>
          ) : (
            <div className="max-h-64 overflow-y-auto divide-y" style={{ borderColor: 'var(--ms-border)' }}>
              {(logs.data ?? []).map((l, i) => (
                <div key={i} className="py-1.5 text-xs">
                  <span className="font-medium">{l.channel === 'sms' ? 'Text' : 'Email'}</span> to {l.to} · {l.event} ·{' '}
                  <span className={l.status === 'failed' ? 'text-red-600' : ''}>{l.status}</span>
                  {l.error ? ` (${l.error})` : ''}
                  <span style={muted}> · {new Date(l.created_at).toLocaleString('en-AU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </Modal>
  )
}
