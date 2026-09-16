/**
 * Tests for the network administration report page.
 *
 * The number this page exists to show is "shops still on HQ's credential" — a
 * shop HQ has not actually handed over, and one more site a single leaked login
 * would open. The tests are mostly about that number being visible and the rows
 * saying the right thing about each shop's access state.
 */
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import api from '@/lib/api'
import { testServer } from '@/test/msw/server'
import { renderAtRoute } from '@/test/renderPage'

const API_BASE = 'http://127.0.0.1/v1'
const enterShop = vi.fn()

vi.mock('@/lib/adminImpersonation', () => ({
  useMinitHqEnterShop: () => ({ enterShop, entering: '', error: '' }),
}))

function shop(o: Record<string, unknown> = {}) {
  return {
    tenant_id: 't-1',
    tenant_name: 'Shop A',
    tenant_slug: 'minit-8001',
    shop_number: '8001',
    area: 'AREA 1',
    region: 'VIC',
    plan_code: 'booking_only',
    is_active: true,
    owner_email: 'hq@mistermint.example',
    owner_full_name: 'HQ Owner',
    has_own_login: false,
    invite_status: null,
    invite_expires_at: null,
    invite_completed_at: null,
    last_support_entry_at: null,
    ...o,
  }
}

function report(o: Record<string, unknown> = {}) {
  return {
    shop_total: 1,
    own_login_count: 0,
    shared_credential_count: 1,
    invite_pending_count: 0,
    invite_expired_count: 0,
    inactive_count: 0,
    shops: [shop()],
    recent_support_sessions: [],
    ...o,
  }
}

function handlers(body: unknown) {
  return [
    http.get(`${API_BASE}/parent-accounts/me/operations/administration`, () =>
      HttpResponse.json(body),
    ),
    http.get(`${API_BASE}/*`, () => HttpResponse.json([])),
  ]
}

/** The shop rows, scoped away from the filter options and the summary cards.
 *
 * Both reuse the same words -- "Own login" is a stat-card label as well as a row
 * badge -- so an unscoped query silently matched the wrong element and passed
 * against a page that had stopped rendering the badge at all. */
function shopList() {
  return within(screen.getByRole('list', { name: 'Shops' }))
}

function summary() {
  return within(screen.getByRole('group', { name: 'Network access summary' }))
}

function badge(text: string | RegExp) {
  return shopList().getByText(text)
}

function queryBadge(text: string | RegExp) {
  return shopList().queryAllByText(text)
}

async function renderPage() {
  const { default: Page } = await import('./MinitAdministrationPage')
  return renderAtRoute(<Page />, { path: '/minit/administration', route: '/minit/administration' })
}

describe('MinitAdministrationPage', () => {
  const previousBase = api.defaults.baseURL
  beforeAll(() => {
    api.defaults.baseURL = API_BASE
  })
  afterAll(() => {
    api.defaults.baseURL = previousBase
  })

  it('leads with how many shops are still on HQ\'s credential', async () => {
    testServer.use(...handlers(report({ shop_total: 12, shared_credential_count: 9, own_login_count: 3 })))
    await renderPage()

    await waitFor(() => expect(summary().getByText(/On HQ's credential/)).toBeInTheDocument())
    expect(summary().getByText('9')).toBeInTheDocument()
  })

  it('marks a shop that has taken its own login', async () => {
    testServer.use(
      ...handlers(report({
        own_login_count: 1,
        shared_credential_count: 0,
        shops: [shop({ has_own_login: true, owner_email: 'shop@example.com' })],
      })),
    )
    await renderPage()

    await waitFor(() => expect(badge('Own login')).toBeInTheDocument())
    expect(screen.getByText(/shop@example.com/)).toBeInTheDocument()
  })

  it('distinguishes an expired invite from a pending one', async () => {
    testServer.use(
      ...handlers(report({
        invite_expired_count: 1,
        shops: [shop({ invite_status: 'expired' })],
      })),
    )
    await renderPage()

    await waitFor(() => expect(badge('Invite expired')).toBeInTheDocument())
    expect(queryBadge('Invite pending')).toHaveLength(0)
  })

  it('does not offer to open a deactivated shop', async () => {
    testServer.use(...handlers(report({ inactive_count: 1, shops: [shop({ is_active: false })] })))
    await renderPage()

    await waitFor(() => expect(badge('Deactivated')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Open Shop A/ })).toBeDisabled()
  })

  it('opens a shop through the support-session flow', async () => {
    testServer.use(...handlers(report()))
    await renderPage()

    await waitFor(() => expect(screen.getByRole('button', { name: /Open Shop A/ })).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: /Open Shop A/ }))

    expect(enterShop).toHaveBeenCalledWith('t-1')
  })

  it('filters down to the shops still on HQ\'s credential', async () => {
    testServer.use(
      ...handlers(report({
        shop_total: 2,
        own_login_count: 1,
        shared_credential_count: 1,
        shops: [
          shop({ tenant_id: 't-1', tenant_name: 'Shared Shop', has_own_login: false }),
          shop({
            tenant_id: 't-2', tenant_name: 'Independent Shop', shop_number: '8002',
            tenant_slug: 'minit-8002', has_own_login: true,
          }),
        ],
      })),
    )
    await renderPage()

    await waitFor(() => expect(screen.getByText(/Independent Shop/)).toBeInTheDocument())
    await userEvent.selectOptions(
      screen.getByLabelText('Filter shops by access state'),
      'shared',
    )

    expect(screen.getByText(/Shared Shop/)).toBeInTheDocument()
    expect(screen.queryByText(/Independent Shop/)).not.toBeInTheDocument()
  })

  it('shows who has been opening shops', async () => {
    testServer.use(
      ...handlers(report({
        recent_support_sessions: [
          {
            tenant_id: 't-1', tenant_name: 'Shop A', shop_number: '8001',
            actor_email: 'admin@mistermint.example', created_at: '2026-03-04T05:06:07Z',
          },
        ],
      })),
    )
    await renderPage()

    await waitFor(() =>
      expect(screen.getByText(/admin@mistermint.example/)).toBeInTheDocument(),
    )
  })

  it('says so plainly when nobody has opened a shop yet', async () => {
    testServer.use(...handlers(report()))
    await renderPage()

    await waitFor(() =>
      expect(screen.getByText(/No administrator has opened a shop yet/)).toBeInTheDocument(),
    )
  })

  it('says the report could not be loaded rather than showing zeros', async () => {
    // Zeros would read as "every shop has its own login", which is the opposite
    // of what an unknown state means.
    testServer.use(
      http.get(`${API_BASE}/parent-accounts/me/operations/administration`, () =>
        HttpResponse.json(null, { status: 500 }),
      ),
      http.get(`${API_BASE}/*`, () => HttpResponse.json([])),
    )
    await renderPage()

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText(/Could not load the administration report/)).toBeInTheDocument()
    expect(screen.queryByText(/On HQ's credential/)).not.toBeInTheDocument()
  })

  it('renders dates rather than raw timestamps', async () => {
    testServer.use(
      ...handlers(report({ shops: [shop({ last_support_entry_at: '2026-03-04T05:06:07Z' })] })),
    )
    await renderPage()

    await waitFor(() => expect(screen.getByText(/last opened by HQ/)).toBeInTheDocument())
    expect(screen.queryByText(/2026-03-04T05:06:07Z/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument()
  })
})
