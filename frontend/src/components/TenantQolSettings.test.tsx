import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TenantQolSettings from './TenantQolSettings'

const state = vi.hoisted(() => ({ allowed: false }))
const api = vi.hoisted(() => ({ keys: vi.fn(), hooks: vi.fn() }))
vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ tenantId: 'current-workspace' }) }))
vi.mock('@/lib/toast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }))
vi.mock('@/lib/api', () => ({
  getAuthSession: async () => ({ data: { tenant_id: 'current-workspace', can_manage_integrations: state.allowed } }),
  getNotificationPreferences: async () => ({ data: {} }),
  getIntegrationHealth: async () => ({ data: { attachment_backend: 'local', twilio_configured: false } }),
  listTenantApiKeys: api.keys,
  listTenantWebhooks: api.hooks,
  createTenantApiKey: vi.fn(), createTenantWebhook: vi.fn(), deleteTenantApiKey: vi.fn(), deleteTenantWebhook: vi.fn(),
  getApiErrorMessage: vi.fn(), patchNotificationPreferences: vi.fn(),
}))

function open() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><TenantQolSettings /></QueryClientProvider>)
}
beforeEach(() => {
  state.allowed = false
  api.keys.mockReset().mockResolvedValue({ data: [{ id: 'key', name: 'HQ connector', key_prefix: 'msk_demo' }] })
  api.hooks.mockReset().mockResolvedValue({ data: [] })
})
describe('HQ-only integration management', () => {
  it('keeps shop notification and health settings while hiding and not fetching keys or webhooks', async () => {
    open()
    expect(await screen.findByText('Integration health')).toBeTruthy()
    expect(screen.getByText('Email alerts for you')).toBeTruthy()
    expect(screen.queryByText('API keys')).toBeNull()
    expect(screen.queryByText('Outbound webhooks')).toBeNull()
    expect(api.keys).not.toHaveBeenCalled()
    expect(api.hooks).not.toHaveBeenCalled()
  })
  it('shows management only after the current workspace capability is confirmed', async () => {
    state.allowed = true
    open()
    expect(await screen.findByText('API keys')).toBeTruthy()
    expect(screen.getByText('Outbound webhooks')).toBeTruthy()
    await waitFor(() => expect(api.keys).toHaveBeenCalledTimes(1))
    expect(api.hooks).toHaveBeenCalledTimes(1)
  })
})
