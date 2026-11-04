import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import NetworkMessagingPage from './NetworkMessagingPage'

const mocks = vi.hoisted(() => ({
  get: vi.fn(), networks: vi.fn(), hubs: vi.fn(), messages: vi.fn(), read: vi.fn(),
  send: vi.fn(), direct: vi.fn(), update: vi.fn(), announcements: vi.fn(), publish: vi.fn(), acknowledge: vi.fn(),
}))
vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ tenantId: 'my-shop' }) }))
vi.mock('@/lib/api', () => ({ default: { get: mocks.get }, getApiErrorMessage: (_error: unknown, fallback: string) => fallback }))
vi.mock('@/lib/api/networkCommunity', () => ({
  messagingNetworks: mocks.networks, stateHubs: mocks.hubs, hubMessages: mocks.messages,
  readHub: mocks.read, sendHubPost: mocks.send, sendDirectPost: mocks.direct,
  updateHubMessage: mocks.update, listAnnouncements: mocks.announcements,
  publishAnnouncement: mocks.publish, acknowledgeAnnouncement: mocks.acknowledge,
}))

const network = { id: 'network', name: 'Minit', own_state: 'VIC', allowed_states: ['VIC'], can_post: true, can_publish_network: false, publish_states: [] as string[] }
const message = { id: 'message', body: 'Need a spring bar', created_at: '2026-11-03T01:00:00Z', sender_name: 'Sarah', shop_name: 'Chadstone', mine: false, kind: 'stock_request', resolved_at: null, pinned: false, reply_preview: null, reply_to_id: null, can_moderate: false, attachments: [] }
const announcement = { id: 'notice', title: 'Campaign kit', body: 'Please confirm your shop has received the kit.', state_code: null, category: 'important', pinned: true, requires_confirmation: true, created_at: '2026-11-03T01:00:00Z', author_name: 'Support Office', read: false, confirmed: false }
function render(route = '/messages') { return renderAtRoute(<NetworkMessagingPage />, { path: '/messages', route }) }

beforeEach(() => {
  vi.clearAllMocks()
  mocks.networks.mockResolvedValue([network])
  mocks.hubs.mockResolvedValue([
    { code: 'VIC', name: 'Victoria', mine: true, accessible: true, can_post: true, unread: 1 },
    { code: 'QLD', name: 'Queensland', mine: false, accessible: false, can_post: false, unread: 0 },
  ])
  mocks.messages.mockResolvedValue({ messages: [message], has_more: false, next_before: null })
  mocks.read.mockResolvedValue(undefined)
  mocks.send.mockResolvedValue({ ...message, id: 'sent' })
  mocks.direct.mockResolvedValue({ conversation_id: 'conversation' })
  mocks.update.mockResolvedValue(message)
  mocks.announcements.mockResolvedValue({ announcements: [announcement], has_more: false })
  mocks.publish.mockResolvedValue(announcement)
  mocks.acknowledge.mockResolvedValue({ ...announcement, confirmed: true, read: true })
  mocks.get.mockImplementation((path: string) => Promise.resolve({ data: path.includes('/contacts') ? [
    { tenant_id: 'brisbane', name: 'Brisbane City · 2104', network_role: 'retail', state_code: 'QLD', shop_number: '2104' },
  ] : [] }))
})

describe('Network messaging workspace', () => {
  it('shows state hubs without opening other states to a shop', async () => {
    render('/messages?tab=hubs')
    expect(await screen.findByRole('heading', { name: 'Victoria' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Queensland/ })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Open my state hub' }))
    expect(await screen.findByText('Need a spring bar')).toBeInTheDocument()
    expect(mocks.messages).toHaveBeenCalledWith('network', 'VIC', undefined)
  })

  it('searches interstate shops and starts a direct conversation', async () => {
    render('/messages?tab=directory')
    expect(await screen.findByText('Brisbane City · 2104')).toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox', { name: 'Search shops' }), '2104')
    await userEvent.click(screen.getByRole('button', { name: 'Message shop' }))
    await userEvent.type(await screen.findByRole('textbox', { name: 'Direct message' }), 'Hello Queensland')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await waitFor(() => expect(mocks.direct).toHaveBeenCalledWith('network', 'brisbane', 'Hello Queensland', []))
  })

  it('sends a real reply and hides moderation actions from other shops', async () => {
    render('/messages?hub=VIC')
    await userEvent.click(await screen.findByRole('button', { name: 'Reply' }))
    expect(screen.queryByRole('button', { name: 'Mark resolved' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox', { name: 'Message Victoria' }), 'We have one')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith('network', 'VIC', { body: 'We have one', kind: 'message', reply_to_id: 'message' }, []))
  })

  it('does not mark announcements read simply by fetching them', async () => {
    render('/messages?tab=announcements')
    expect(await screen.findByRole('heading', { name: 'Campaign kit' })).toBeInTheDocument()
    expect(mocks.acknowledge).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm received' }))
    await waitFor(() => expect(mocks.acknowledge).toHaveBeenCalledWith('network', 'notice', true))
  })

  it('offers regional managers only their authorised publishing audience', async () => {
    mocks.networks.mockResolvedValue([{ ...network, publish_states: ['VIC'] }])
    render('/messages?tab=announcements')
    await userEvent.click(await screen.findByRole('button', { name: 'New announcement' }))
    expect(screen.queryByRole('option', { name: 'All shops in this network' })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Queensland' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox', { name: 'Title' }), 'Victoria meeting')
    await userEvent.type(screen.getByRole('textbox', { name: 'Message' }), 'See you Thursday')
    await userEvent.click(screen.getByRole('button', { name: 'Publish announcement' }))
    await waitFor(() => expect(mocks.publish).toHaveBeenCalledWith('network', expect.objectContaining({ state_code: 'VIC', title: 'Victoria meeting' })))
  })

  it('includes selected photos with the message instead of a separate unbound upload', async () => {
    render('/messages?hub=VIC')
    const input = await screen.findByLabelText('Attach photo')
    const file = new File(['photo'], 'part.png', { type: 'image/png' })
    fireEvent.change(input, { target: { files: [file] } })
    expect(screen.getByText('part.png')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith('network', 'VIC', { body: '', kind: 'message' }, [file]))
  })
})


it('describes directory records as linked rather than online participants', async () => {
  render('/messages?tab=directory')
  expect(await screen.findByText(/LINKED SITES/)).toBeInTheDocument()
  expect(screen.getByText(/does not show who is online/)).toBeInTheDocument()
  expect(screen.getByText(/Singapore and Malaysia/)).toBeInTheDocument()
})

it('uses Support office hub wording for accounts with multiple state hubs', async () => {
  mocks.networks.mockResolvedValue([{ ...network, allowed_states: ['VIC', 'QLD'], can_publish_network: true }])
  render('/messages?tab=hubs')
  expect(await screen.findByRole('heading', { name: 'Support office state hubs' })).toBeInTheDocument()
  expect(screen.queryByText('YOUR SHOP’S HUB')).not.toBeInTheDocument()
})
