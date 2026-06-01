import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createTenantApiKey,
  createTenantWebhook,
  deleteTenantApiKey,
  deleteTenantWebhook,
  getApiErrorMessage,
  getIntegrationHealth,
  getNotificationPreferences,
  listTenantApiKeys,
  listTenantWebhooks,
  patchNotificationPreferences,
  type IntegrationHealth,
  type NotificationPrefs,
} from '@/lib/api'
import { useToast } from '@/lib/toast'
import { Button, Card, Input, Spinner } from '@/components/ui'

export default function TenantQolSettings() {
  const qc = useQueryClient()
  const toast = useToast()
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookEvents, setWebhookEvents] = useState('quote_approved,job_created')

  const { data: prefs, isLoading: prefsLoading } = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: () => getNotificationPreferences().then(r => r.data),
  })
  const { data: health } = useQuery({
    queryKey: ['integration-health'],
    queryFn: () => getIntegrationHealth().then(r => r.data),
  })
  const { data: apiKeys = [] } = useQuery({
    queryKey: ['tenant-api-keys'],
    queryFn: () => listTenantApiKeys().then(r => r.data),
  })
  const { data: webhooks = [] } = useQuery({
    queryKey: ['tenant-webhooks'],
    queryFn: () => listTenantWebhooks().then(r => r.data),
  })

  const patchPrefsMut = useMutation({
    mutationFn: (body: Partial<NotificationPrefs>) => patchNotificationPreferences(body),
    onSuccess: () => {
      toast.success('Preferences saved')
      void qc.invalidateQueries({ queryKey: ['notification-preferences'] })
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, 'Failed to save')),
  })

  const createKeyMut = useMutation({
    mutationFn: () => createTenantApiKey(newKeyName.trim()),
    onSuccess: (res) => {
      setCreatedKey(res.data.api_key)
      setNewKeyName('')
      toast.success('API key created — copy it now')
      void qc.invalidateQueries({ queryKey: ['tenant-api-keys'] })
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, 'Failed to create key')),
  })

  const createHookMut = useMutation({
    mutationFn: () =>
      createTenantWebhook(webhookUrl.trim(), webhookEvents.split(',').map(s => s.trim()).filter(Boolean)),
    onSuccess: () => {
      setWebhookUrl('')
      toast.success('Webhook added')
      void qc.invalidateQueries({ queryKey: ['tenant-webhooks'] })
    },
    onError: (e: unknown) => toast.error(getApiErrorMessage(e, 'Failed to add webhook')),
  })

  if (prefsLoading) return <Spinner />

  return (
    <div className="space-y-5 mt-8">
      <h2 className="text-lg font-semibold" style={{ color: 'var(--ms-text)' }}>Notifications & integrations</h2>

      <Card className="p-5 space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Email alerts for you</h3>
        {(['email_quote_approved', 'email_invoice_paid', 'email_sms_reply', 'email_daily_digest'] as const).map(key => (
          <label key={key} className="flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text)' }}>
            <input
              type="checkbox"
              checked={prefs?.[key] ?? false}
              onChange={e => patchPrefsMut.mutate({ [key]: e.target.checked })}
            />
            {key.replace(/_/g, ' ')}
          </label>
        ))}
      </Card>

      {health && <IntegrationHealthCard health={health} />}

      <Card className="p-5 space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>API keys</h3>
        <div className="flex gap-2">
          <Input value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder="Key name" />
          <Button variant="secondary" onClick={() => createKeyMut.mutate()} disabled={!newKeyName.trim() || createKeyMut.isPending}>
            Create
          </Button>
        </div>
        {createdKey && (
          <p className="text-xs font-mono break-all p-2 rounded" style={{ backgroundColor: 'var(--ms-bg)' }}>
            {createdKey}
          </p>
        )}
        <ul className="text-xs space-y-1" style={{ color: 'var(--ms-text-muted)' }}>
          {apiKeys.map(k => (
            <li key={k.id} className="flex justify-between gap-2">
              <span>{k.name} ({k.key_prefix}…)</span>
              <button type="button" className="underline" onClick={() => deleteTenantApiKey(k.id).then(() => qc.invalidateQueries({ queryKey: ['tenant-api-keys'] }))}>
                Revoke
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="p-5 space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Outbound webhooks</h3>
        <Input value={webhookUrl} onChange={e => setWebhookUrl(e.target.value)} placeholder="https://…" />
        <Input value={webhookEvents} onChange={e => setWebhookEvents(e.target.value)} placeholder="quote_approved,job_created" />
        <Button variant="secondary" onClick={() => createHookMut.mutate()} disabled={!webhookUrl.trim() || createHookMut.isPending}>
          Add webhook
        </Button>
        <ul className="text-xs space-y-1" style={{ color: 'var(--ms-text-muted)' }}>
          {webhooks.map(h => (
            <li key={h.id} className="flex justify-between gap-2">
              <span className="truncate">{h.url}</span>
              <button type="button" className="underline shrink-0" onClick={() => deleteTenantWebhook(h.id).then(() => qc.invalidateQueries({ queryKey: ['tenant-webhooks'] }))}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

function IntegrationHealthCard({ health }: { health: IntegrationHealth }) {
  const rows = [
    { label: 'Twilio SMS', ok: health.twilio_configured, detail: health.last_sms_sent_at ? `Last sent ${health.last_sms_sent_at}` : 'Not configured' },
    { label: 'Stripe billing', ok: health.stripe_configured, detail: health.stripe_connect_ready ? 'Connect ready' : 'Not connected' },
    { label: 'SendGrid email', ok: health.sendgrid_configured, detail: health.sendgrid_configured ? 'Configured' : 'Not configured' },
    { label: 'Attachments', ok: true, detail: health.attachment_backend },
  ]
  return (
    <Card className="p-5 space-y-2">
      <h3 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Integration health</h3>
      {rows.map(r => (
        <div key={r.label} className="flex justify-between text-sm gap-4">
          <span style={{ color: 'var(--ms-text)' }}>{r.label}</span>
          <span style={{ color: r.ok ? '#1F6D4C' : 'var(--ms-text-muted)' }}>{r.detail}</span>
        </div>
      ))}
    </Card>
  )
}
