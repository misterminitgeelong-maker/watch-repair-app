import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import PlatformHqOwnersPanel from './PlatformHqOwnersPanel'
import { createPlatformHqInvite, listPlatformHqOwners, revokePlatformHqInvite } from '@/lib/api'

vi.mock('@/lib/api', async original => ({ ...await original<typeof import('@/lib/api')>(), createPlatformHqInvite: vi.fn(), listPlatformHqOwners: vi.fn(), revokePlatformHqInvite: vi.fn() }))
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listPlatformHqOwners).mockResolvedValue({ data: { accounts: [{ parent_account_id: 'network', tenant_id: 'hq', name: 'Minit', tenant_name: 'HQ', tenant_slug: 'mmsupport' }], invites: [] } } as unknown as Awaited<ReturnType<typeof listPlatformHqOwners>>)
  vi.mocked(createPlatformHqInvite).mockResolvedValue({ data: { id: 'invite', email: 'owner@example.com', invite_url: 'https://mainspring.au/hq-invite/one-time', email_sent: false, expires_at: '2026-10-08T00:00:00Z' } } as unknown as Awaited<ReturnType<typeof createPlatformHqInvite>>)
})
describe('HQ owner invitations', () => {
  it('creates a link for the selected HQ and supports manual sharing', async () => {
    const user = userEvent.setup()
    renderAtRoute(<PlatformHqOwnersPanel />, { path: '/platform-admin/hq-owners', route: '/platform-admin/hq-owners' })
    await user.selectOptions(await screen.findByLabelText('HQ account'), 'network:hq')
    await user.type(screen.getByLabelText('Owner name'), 'HQ Owner')
    await user.type(screen.getByLabelText('Owner email'), 'owner@example.com')
    await user.click(screen.getByLabelText('Email the invitation to this owner'))
    await user.click(screen.getByRole('button', { name: 'Create invite link' }))
    await waitFor(() => expect(createPlatformHqInvite).toHaveBeenCalledWith({ parent_account_id: 'network', tenant_id: 'hq', email: 'owner@example.com', full_name: 'HQ Owner', send_email: false }))
    expect(await screen.findByLabelText('Invite link')).toHaveValue('https://mainspring.au/hq-invite/one-time')
    await user.click(screen.getByRole('button', { name: 'Copy invite link' }))
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
    expect(await navigator.clipboard.readText()).toBe('https://mainspring.au/hq-invite/one-time')
  })
  it('revokes a pending invitation', async () => {
    vi.mocked(listPlatformHqOwners).mockResolvedValue({ data: { accounts: [], invites: [{ id: 'pending', full_name: 'Owner', email: 'owner@example.com', status: 'pending', expires_at: '2026-10-08T00:00:00Z' }] } } as unknown as Awaited<ReturnType<typeof listPlatformHqOwners>>)
    vi.mocked(revokePlatformHqInvite).mockResolvedValue({ data: { revoked: true } } as unknown as Awaited<ReturnType<typeof revokePlatformHqInvite>>)
    const user = userEvent.setup()
    renderAtRoute(<PlatformHqOwnersPanel />, { path: '/platform-admin/hq-owners', route: '/platform-admin/hq-owners' })
    await user.click(await screen.findByRole('button', { name: 'Revoke invite' }))
    await waitFor(() => expect(revokePlatformHqInvite).toHaveBeenCalledWith('pending', expect.anything()))
  })
})
