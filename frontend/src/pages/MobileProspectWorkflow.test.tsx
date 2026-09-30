import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import api from '@/lib/api'
import { testServer } from '@/test/msw/server'
import { renderAtRoute } from '@/test/renderPage'
import ProspectBoardPage from './ProspectBoardPage'
import ProspectsPage from './ProspectsPage'
import ToolkitPage from './ToolkitPage'

vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ role: 'owner', refreshSession: vi.fn() }) }))
const BASE = 'http://localhost/v1'
const lead = { id: 'lead-1', name: 'Field Mechanics', status: 'visited', contact_name: 'Old contact', contact_email: 'old@example.test', notes: 'Old notes', visit_scheduled_at: '2026-10-02T00:00:00Z' }
const board = () => renderAtRoute(<ProspectBoardPage />, { path: '/auto-key/prospects/board', route: '/auto-key/prospects/board' })
const toolkit = () => renderAtRoute(<ToolkitPage />, { path: '/auto-key/toolkit', route: '/auto-key/toolkit' })

function toolkitHandlers() {
  testServer.use(
    http.get(`${BASE}/toolkit/catalog`, () => HttpResponse.json({ groups: [{ id: 'other', label: 'Other tools', tools: [{ key: 'other', name: 'Other tool' }] }, { id: 'cutters', label: 'Cutters', tools: [{ key: 'ninja', name: 'Ninja Total' }] }], scenarios: [{ id: 'add', label: 'Add key' }, { id: 'remote', label: 'Remote' }] })),
    http.get(`${BASE}/toolkit/my-selection`, () => HttpResponse.json({ tool_keys: [] })),
    http.get(`${BASE}/toolkit/mobile-notifications`, () => HttpResponse.json({ customer_sms_enabled: true, dispatch_phone: null })),
    http.get(`${BASE}/toolkit/mobile-catalogue`, () => HttpResponse.json({ available_categories: [], enabled_categories: [] })),
  )
}

describe('Mobile prospect field fixes', () => {
  const previousBase = api.defaults.baseURL
  beforeAll(() => { api.defaults.baseURL = BASE })
  beforeEach(() => { sessionStorage.clear() })
  afterAll(() => { api.defaults.baseURL = previousBase })

  it('sends explicit null when clearing saved details', async () => {
    const user = userEvent.setup()
    let submitted: unknown
    testServer.use(
      http.get(`${BASE}/prospect-leads`, () => HttpResponse.json([lead])),
      http.patch(`${BASE}/prospect-leads/lead-1`, async ({ request }) => { submitted = await request.json(); return HttpResponse.json({ ...lead, ...(submitted as object) }) }),
    )
    board()
    await user.click((await screen.findAllByRole('button', { name: /Field Mechanics/ }))[0])
    const dialog = within(screen.getByRole('dialog'))
    await user.clear(dialog.getByLabelText('Contact name'))
    await user.clear(dialog.getByLabelText('Contact email'))
    await user.clear(dialog.getByLabelText('Notes'))
    await user.click(dialog.getByRole('button', { name: 'Clear date' }))
    await user.click(dialog.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(submitted).toEqual({ contact_name: null, contact_email: null, notes: null, visit_scheduled_at: null }))
  })

  it('advances with the visible draft in the same request', async () => {
    const user = userEvent.setup()
    let submitted: unknown
    testServer.use(
      http.get(`${BASE}/prospect-leads`, () => HttpResponse.json([lead])),
      http.post(`${BASE}/prospect-leads/lead-1/advance`, async ({ request }) => { submitted = await request.json(); return HttpResponse.json({ ...lead, status: 'onboarded', customer_account_id: 'account-1' }) }),
    )
    board()
    await user.click((await screen.findAllByRole('button', { name: /Field Mechanics/ }))[0])
    await user.clear(screen.getByLabelText('Contact name'))
    await user.type(screen.getByLabelText('Contact name'), 'Visible draft')
    await user.click(screen.getByRole('button', { name: 'Mark as Onboarded' }))
    await waitFor(() => expect(submitted).toMatchObject({ contact_name: 'Visible draft' }))
    expect(await screen.findByText('elsewhere')).toBeInTheDocument()
  })

  it('supports Escape and protects an unsaved draft', async () => {
    const user = userEvent.setup()
    testServer.use(http.get(`${BASE}/prospect-leads`, () => HttpResponse.json([lead])))
    board()
    await user.click((await screen.findAllByRole('button', { name: /Field Mechanics/ }))[0])
    await user.type(screen.getByLabelText('Contact name'), ' edit')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    await user.keyboard('{Escape}')
    expect(confirm).toHaveBeenCalledWith('Discard unsaved prospect changes?')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    confirm.mockReturnValue(true)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    confirm.mockRestore()
  })

  it('keeps Inbox stages visible in the list', async () => {
    const user = userEvent.setup()
    testServer.use(http.get(`${BASE}/prospect-leads`, () => HttpResponse.json([{ ...lead, status: 'quote_needed' }])))
    board()
    await user.click(screen.getByRole('button', { name: 'List' }))
    expect(await screen.findByRole('button', { name: /Field Mechanics/ })).toBeInTheDocument()
    expect(screen.getByText('Quote needed')).toBeInTheDocument()
  })

  it('opens filtered tools and checks the unsaved selection', async () => {
    const user = userEvent.setup()
    toolkitHandlers()
    let submitted: unknown
    testServer.use(http.post(`${BASE}/toolkit/recommend`, async ({ request }) => { submitted = await request.json(); return HttpResponse.json({ label: 'Draft result', ready_for_required: true, required: [], missing_required: [], missing_nice_to_have: [] }) }))
    toolkit()
    await user.type(await screen.findByPlaceholderText('Name or notes…'), 'Ninja')
    await user.click(screen.getByRole('checkbox', { name: 'Ninja Total' }))
    await user.selectOptions(screen.getByRole('combobox'), 'add')
    await user.click(screen.getByRole('button', { name: 'What do I need?' }))
    await waitFor(() => expect(submitted).toEqual({ scenario_id: 'add', tool_keys: ['ninja'] }))
    expect(await screen.findByText(/Draft result/)).toBeInTheDocument()
    expect(screen.getByText(/Checking the unsaved selection/)).toBeInTheDocument()
  })

  it('ignores a late recommendation after the scenario changes', async () => {
    const user = userEvent.setup()
    toolkitHandlers()
    testServer.use(http.post(`${BASE}/toolkit/recommend`, async () => { await delay(150); return HttpResponse.json({ label: 'Obsolete result', ready_for_required: true, required: [], missing_required: [], missing_nice_to_have: [] }) }))
    toolkit()
    await screen.findByPlaceholderText('Name or notes…')
    await user.selectOptions(screen.getByRole('combobox'), 'add')
    await user.click(screen.getByRole('button', { name: 'What do I need?' }))
    await user.selectOptions(screen.getByRole('combobox'), 'remote')
    await delay(200)
    expect(screen.queryByText(/Obsolete result/)).not.toBeInTheDocument()
  })

  it('restores submitted search filters from the URL and exposes contact lookup', async () => {
    const user = userEvent.setup()
    testServer.use(
      http.get(`${BASE}/prospects/categories`, () => HttpResponse.json({ categories: [{ key: 'mechanics', label: 'Mechanics' }] })),
      http.get(`${BASE}/prospects/regions`, () => HttpResponse.json({ states: [{ code: 'VIC', name: 'Victoria' }], suburbs: { VIC: ['Geelong'] } })),
      http.get(`${BASE}/prospect-leads`, () => HttpResponse.json([])),
      http.get(`${BASE}/prospects/search`, () => HttpResponse.json({ results: [{ name: 'Found business', address: 'Geelong', category: 'mechanics', place_id: 'place-1' }], total: 1, category: 'mechanics', source: 'stored' })),
      http.get(`${BASE}/prospects/contact-details`, () => HttpResponse.json({ place_id: 'place-1', phone: '03 9000 1111', website: 'https://example.test', attributions: [] })),
    )
    const first = renderAtRoute(<ProspectsPage />, { path: '/auto-key/prospects', route: '/auto-key/prospects?category=mechanics&state=VIC&suburbs=Geelong&live=0' })
    await screen.findByText('Found business')
    expect(screen.getByLabelText('Category')).toHaveValue('mechanics')
    expect(screen.getByLabelText('State')).toHaveValue('VIC')
    await user.click(screen.getByRole('button', { name: 'Find contact details' }))
    expect(await screen.findByRole('link', { name: 'Call 03 9000 1111' })).toHaveAttribute('href', 'tel:03 9000 1111')
    await user.click(screen.getByRole('button', { name: 'Search prospects' }))
    first.unmount()
    renderAtRoute(<ProspectsPage />, { path: '/auto-key/prospects', route: '/auto-key/prospects' })
    await waitFor(() => expect(screen.getByLabelText('Category')).toHaveValue('mechanics'))
    expect(screen.getByLabelText('State')).toHaveValue('VIC')
    expect(await screen.findByText('Found business')).toBeInTheDocument()
  })
})
