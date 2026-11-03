import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import PlatformHqBillingPanel from './PlatformHqBillingPanel'
import { createHqInvoiceDraft, getHqBillingSettings, getHqInvoice, issueHqInvoice, listHqInvoices, listPlatformHqs, saveHqBillingSettings } from '@/lib/api'

vi.mock('@/lib/api', async original => ({
  ...await original<typeof import('@/lib/api')>(),
  listPlatformHqs: vi.fn(), getHqBillingSettings: vi.fn(), saveHqBillingSettings: vi.fn(), listHqInvoices: vi.fn(),
  createHqInvoiceDraft: vi.fn(), getHqInvoice: vi.fn(), issueHqInvoice: vi.fn(), voidHqInvoice: vi.fn(), downloadHqInvoicePdf: vi.fn(),
}))
const res = <T,>(data: T) => ({ data }) as never

const ROW = { id: 'i1', parent_account_id: 'p1', billing_month: '2026-11', invoice_number: 'MS-202611-AB12', status: 'draft', operator_count: 2, subtotal_ex_gst_cents: 11000, gst_cents: 1100, total_inc_gst_cents: 12100, currency: 'AUD', stripe_hosted_url: null, issued_at: null, due_at: null, paid_at: null }
const DETAIL = { ...ROW, snapshot: { lines: [{ tenant_id: 't1', name: 'Shop One', shop_number: '12', core_cents: 5500, routing_cents: 0, prospecting_cents: 0, subtotal_ex_gst_cents: 5500, gst_cents: 550 }], excluded: [{ tenant_id: 't9', name: 'Comp Shop', reason: 'billing_exempt' }] } }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listPlatformHqs).mockResolvedValue(res({ hqs: [{ parent_account_id: 'p1', display_name: 'Mister Minit' }], available_modules: [], available_site_plans: [] }))
  vi.mocked(getHqBillingSettings).mockResolvedValue(res({ parent_account_id: 'p1', routing_addon: false, prospecting_addon: false, billing_email: 'owner@minit.test', billing_email_is_default: true }))
  vi.mocked(listHqInvoices).mockResolvedValue(res({ invoices: [] }))
})

const render = () => renderAtRoute(<PlatformHqBillingPanel />, { path: '/platform-admin/hq-billing', route: '/platform-admin/hq-billing' })

describe('HQ invoices', () => {
  it('saves add-on settings', async () => {
    vi.mocked(saveHqBillingSettings).mockResolvedValue(res({}))
    render()
    await userEvent.click(await screen.findByLabelText('Lead routing add-on'))
    await userEvent.click(screen.getByRole('button', { name: 'Save billing settings' }))
    await waitFor(() => expect(saveHqBillingSettings).toHaveBeenCalledWith('p1', { routing_addon: true, prospecting_addon: false, billing_email: null }))
  })

  it('prepares a draft, shows exclusions, and issues only after confirming', async () => {
    vi.mocked(createHqInvoiceDraft).mockImplementation(async () => { vi.mocked(listHqInvoices).mockResolvedValue(res({ invoices: [ROW] })); return res(DETAIL) })
    vi.mocked(getHqInvoice).mockResolvedValue(res(DETAIL))
    vi.mocked(issueHqInvoice).mockResolvedValue(res({ ...ROW, status: 'issued' }))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render()
    await userEvent.click(await screen.findByRole('button', { name: 'Prepare invoice' }))
    expect(await screen.findByText(/Comp Shop \(Billing exempt\)/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Issue and email via Stripe' }))
    await waitFor(() => expect(issueHqInvoice).toHaveBeenCalledWith('i1'))
  })
})
