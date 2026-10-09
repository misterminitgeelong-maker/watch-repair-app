import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import PlatformHqsPanel from './PlatformHqsPanel'
import { createPlatformHq, listPlatformHqs, updatePlatformHq } from '@/lib/api'

vi.mock('@/lib/api', async original => ({ ...await original<typeof import('@/lib/api')>(), createPlatformHq: vi.fn(), listPlatformHqs: vi.fn(), updatePlatformHq: vi.fn() }))

const LIST = {
  hqs: [{ parent_account_id: 'p1', tenant_id: 't1', tenant_slug: 'mmsupport', product_key: 'minit', display_name: 'Mister Minit', logo_url: null, brand_color: '#E31837', modules: ['mobile_services'], site_plans: ['booking_only'], shop_count: 3 }],
  available_modules: ['mobile_services', 'shoe', 'stock'],
  available_site_plans: ['basic_shoe', 'booking_only'],
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listPlatformHqs).mockResolvedValue({ data: LIST } as unknown as Awaited<ReturnType<typeof listPlatformHqs>>)
})

const render = () => renderAtRoute(<PlatformHqsPanel />, { path: '/platform-admin/hqs', route: '/platform-admin/hqs' })

describe('Create HQ', () => {
  it('lists existing HQs with their modules and shop counts', async () => {
    render()
    expect(await screen.findByText('Mister Minit')).toBeInTheDocument()
    expect(screen.getByText(/3 shops/)).toBeInTheDocument()
    expect(screen.getByText('Mobile services', { selector: 'p' })).toBeInTheDocument()
  })

  it('creates an HQ with the chosen modules and plans', async () => {
    vi.mocked(createPlatformHq).mockResolvedValue({ data: { display_name: 'Birkenstock', invite_url: 'https://mainspring.au/hq-invite/x', email_sent: false } } as unknown as Awaited<ReturnType<typeof createPlatformHq>>)
    const user = userEvent.setup()
    render()
    await user.type(await screen.findByLabelText('Company name'), 'Birkenstock')
    await user.type(screen.getByLabelText('Account ID'), 'Birkenstock')
    await user.type(screen.getByLabelText('Owner name'), 'Pat Owner')
    await user.type(screen.getByLabelText('Owner email'), 'pat@example.com')
    const modules = screen.getByRole('group', { name: 'New HQ modules' })
    await user.click(within(modules).getByLabelText('Shoe repairs'))
    await user.click(within(modules).getByLabelText('Stock'))
    await user.click(within(screen.getByRole('group', { name: 'New HQ shop plans' })).getByLabelText('basic shoe'))
    await user.click(screen.getByLabelText('Email the owner their invitation'))
    await user.click(screen.getByRole('button', { name: 'Create HQ' }))
    await waitFor(() => expect(createPlatformHq).toHaveBeenCalledWith({
      slug: 'birkenstock', display_name: 'Birkenstock', brand_color: null, modules: ['shoe', 'stock'], site_plans: ['basic_shoe'],
      owner_name: 'Pat Owner', owner_email: 'pat@example.com', send_invite: false,
    }))
    expect(await screen.findByLabelText('Invite link')).toHaveValue('https://mainspring.au/hq-invite/x')
  })

  it('shows the server error when creation is refused', async () => {
    vi.mocked(createPlatformHq).mockRejectedValue({ isAxiosError: true, response: { status: 409, data: { detail: 'That account ID is already taken.' } } })
    const user = userEvent.setup()
    render()
    await user.type(await screen.findByLabelText('Company name'), 'Dup')
    await user.type(screen.getByLabelText('Account ID'), 'dupco')
    await user.type(screen.getByLabelText('Owner name'), 'O')
    await user.type(screen.getByLabelText('Owner email'), 'o@example.com')
    await user.click(screen.getByRole('button', { name: 'Create HQ' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already taken/i)
  })

  it('saves edits to an existing HQ', async () => {
    vi.mocked(updatePlatformHq).mockResolvedValue({ data: LIST.hqs[0] } as unknown as Awaited<ReturnType<typeof updatePlatformHq>>)
    const user = userEvent.setup()
    render()
    await user.click(await screen.findByRole('button', { name: 'Edit Mister Minit' }))
    await user.click(within(screen.getByRole('group', { name: 'Modules' })).getByLabelText('Shoe repairs'))
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(updatePlatformHq).toHaveBeenCalledWith('p1', {
      display_name: 'Mister Minit', brand_color: '#E31837', logo_url: null, modules: ['mobile_services', 'shoe'], site_plans: ['booking_only'],
    }))
  })
})
