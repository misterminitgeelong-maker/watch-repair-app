import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest'
import axios from 'axios'
import { http, HttpResponse } from 'msw'
import api, {
  createQuote,
  sendQuote,
  getPublicQuote,
  submitQuoteDecision,
  createInvoiceFromQuote,
  recordPayment,
} from './api'
import { testServer } from '@/test/msw/server'

/**
 * Integration test for the revenue-critical path:
 *   create quote -> send (issue approval token) -> public approval
 *   -> invoice from quote -> record payment.
 *
 * Uses MSW with a small in-memory store so values thread through the flow
 * (quote total -> public quote -> invoice total -> payment / balance).
 */
describe('revenue flow: quote -> approval -> invoice -> payment', () => {
  const previousApiBase = api.defaults.baseURL
  const previousAxiosBase = axios.defaults.baseURL

  // `api` uses a relative `/v1` base and the public endpoints use raw axios with
  // relative paths; node/jsdom needs an absolute origin for MSW to intercept.
  beforeAll(() => {
    api.defaults.baseURL = 'http://127.0.0.1/v1'
    axios.defaults.baseURL = 'http://127.0.0.1'
  })

  afterAll(() => {
    api.defaults.baseURL = previousApiBase
    axios.defaults.baseURL = previousAxiosBase
  })

  beforeEach(() => {
    testServer.resetHandlers()
  })

  function buildHandlers() {
    const store: {
      quote?: { id: string; total_cents: number; tax_cents: number; status: string; approval_token: string }
      invoice?: { id: string; invoice_number: string; total_cents: number; status: string; paid_cents: number }
    } = {}

    return [
      http.post('*/v1/quotes', async ({ request }) => {
        const body = (await request.json()) as { tax_cents: number; line_items: Array<{ quantity: number; unit_price_cents: number }> }
        const subtotal = body.line_items.reduce((sum, li) => sum + li.quantity * li.unit_price_cents, 0)
        const total = subtotal + (body.tax_cents ?? 0)
        store.quote = {
          id: 'quote-1',
          total_cents: total,
          tax_cents: body.tax_cents ?? 0,
          status: 'draft',
          approval_token: '',
        }
        return HttpResponse.json({
          id: store.quote.id,
          status: store.quote.status,
          subtotal_cents: subtotal,
          tax_cents: store.quote.tax_cents,
          total_cents: total,
        })
      }),

      http.post('*/v1/quotes/:id/send', () => {
        if (!store.quote) return new HttpResponse(null, { status: 404 })
        store.quote.status = 'sent'
        store.quote.approval_token = 'approval-tok-123'
        return HttpResponse.json({
          id: store.quote.id,
          status: store.quote.status,
          sent_at: '2026-05-31T00:00:00Z',
          approval_token: store.quote.approval_token,
        })
      }),

      http.get('*/v1/public/quotes/:token', ({ params }) => {
        if (!store.quote || params.token !== store.quote.approval_token) {
          return new HttpResponse(null, { status: 404 })
        }
        return HttpResponse.json({
          id: store.quote.id,
          status: store.quote.status,
          subtotal_cents: store.quote.total_cents - store.quote.tax_cents,
          tax_cents: store.quote.tax_cents,
          total_cents: store.quote.total_cents,
          currency: 'AUD',
          line_items: [],
        })
      }),

      http.post('*/v1/public/quotes/:token/decision', async ({ request, params }) => {
        if (!store.quote || params.token !== store.quote.approval_token) {
          return new HttpResponse(null, { status: 404 })
        }
        const body = (await request.json()) as { decision: 'approved' | 'declined' }
        store.quote.status = body.decision === 'approved' ? 'approved' : 'declined'
        return HttpResponse.json({ status: store.quote.status })
      }),

      http.post('*/v1/invoices/from-quote/:quoteId', () => {
        if (!store.quote || store.quote.status !== 'approved') {
          return new HttpResponse(null, { status: 409 })
        }
        store.invoice = {
          id: 'invoice-1',
          invoice_number: 'INV-1001',
          total_cents: store.quote.total_cents,
          status: 'unpaid',
          paid_cents: 0,
        }
        return HttpResponse.json({ invoice: { ...store.invoice } })
      }),

      http.post('*/v1/invoices/:invoiceId/payments', async ({ request }) => {
        if (!store.invoice) return new HttpResponse(null, { status: 404 })
        const body = (await request.json()) as { amount_cents: number }
        store.invoice.paid_cents += body.amount_cents
        if (store.invoice.paid_cents >= store.invoice.total_cents) store.invoice.status = 'paid'
        return HttpResponse.json({
          invoice_id: store.invoice.id,
          status: store.invoice.status,
          paid_cents: store.invoice.paid_cents,
        })
      }),
    ]
  }

  it('threads totals from quote through to a paid invoice', async () => {
    testServer.use(...buildHandlers())

    const { data: quote } = await createQuote({
      repair_job_id: 'job-1',
      tax_cents: 1000,
      line_items: [
        { item_type: 'labor', description: 'Service', quantity: 1, unit_price_cents: 5000 },
        { item_type: 'part', description: 'Crystal', quantity: 2, unit_price_cents: 2500 },
      ],
    })
    expect(quote.total_cents).toBe(5000 + 5000 + 1000)

    const { data: sent } = await sendQuote(quote.id)
    expect(sent.status).toBe('sent')
    const token = sent.approval_token
    expect(token).toBeTruthy()

    const { data: publicQuote } = await getPublicQuote(token)
    expect(publicQuote.total_cents).toBe(11000)
    expect(publicQuote.status).toBe('sent')

    const { data: decision } = await submitQuoteDecision(token, 'approved')
    expect((decision as { status: string }).status).toBe('approved')

    const { data: invoiceResp } = await createInvoiceFromQuote(quote.id)
    expect(invoiceResp.invoice.total_cents).toBe(11000)
    expect(invoiceResp.invoice.status).toBe('unpaid')

    const { data: payment } = await recordPayment(invoiceResp.invoice.id, 11000)
    expect((payment as { status: string }).status).toBe('paid')
  })

  it('refuses to invoice a quote that was not approved', async () => {
    testServer.use(...buildHandlers())

    const { data: quote } = await createQuote({
      repair_job_id: 'job-2',
      tax_cents: 0,
      line_items: [{ item_type: 'labor', description: 'Service', quantity: 1, unit_price_cents: 5000 }],
    })
    const { data: sent } = await sendQuote(quote.id)
    await submitQuoteDecision(sent.approval_token, 'declined')

    await expect(createInvoiceFromQuote(quote.id)).rejects.toMatchObject({
      response: { status: 409 },
    })
  })
})
