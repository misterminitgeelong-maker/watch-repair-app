/**
 * Characterisation tests for the shoe job-detail page (1,114 lines, no tests).
 *
 * Same purpose as the watch equivalent: pin what a user sees before the three
 * pages are collapsed into a shared shell. Assertions are on visible text, and
 * where the three verticals differ that difference is asserted deliberately —
 * this page shows the shoe, the watch page does not show the watch.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import api from '@/lib/api'
import { testServer } from '@/test/msw/server'
import { API_BASE, jobDetailHandlers, makeShoeJob } from '@/test/msw/jobDetail'
import { renderAtRoute } from '@/test/renderPage'
import ShoeJobDetailPage from './ShoeJobDetailPage'

function renderJob() {
  return renderAtRoute(<ShoeJobDetailPage />, {
    path: '/shoe-jobs/:id',
    route: '/shoe-jobs/job-1',
  })
}

describe('ShoeJobDetailPage', () => {
  const previousBase = api.defaults.baseURL
  beforeAll(() => {
    api.defaults.baseURL = API_BASE
  })
  afterAll(() => {
    api.defaults.baseURL = previousBase
  })

  it('shows the job number and title once loaded', async () => {
    testServer.use(...jobDetailHandlers())
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/SHOE-00007/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/Resole and stretch/).length).toBeGreaterThan(0)
  })

  it('shows the shoe the job is for', async () => {
    // The per-vertical subject. Unlike the watch page, this one puts it on the
    // summary view, so a shared shell has to keep that difference.
    testServer.use(...jobDetailHandlers())
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/Loake/).length).toBeGreaterThan(0))
  })

  it('reflects the status that came back from the API', async () => {
    testServer.use(...jobDetailHandlers({ shoeJob: makeShoeJob({ status: 'ready_for_collection' }) }))
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/SHOE-00007/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/ready|collection/i).length).toBeGreaterThan(0)
  })

  it('renders an empty line-item list without breaking', async () => {
    testServer.use(...jobDetailHandlers({ shoeJob: makeShoeJob({ items: [] }) }))
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/SHOE-00007/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
  })

  it('renders line items with money formatted as dollars', async () => {
    testServer.use(
      ...jobDetailHandlers({
        shoeJob: makeShoeJob({
          items: [
            {
              id: 'item-1',
              shoe_repair_job_id: 'job-1',
              catalogue_key: 'resole_full',
              catalogue_group: 'Soles',
              item_name: 'Full resole',
              pricing_type: 'fixed',
              unit_price_cents: 18500,
              quantity: 1,
              notes: null,
              created_at: '2026-01-02T03:04:05Z',
            },
          ],
        }),
      }),
    )
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/Full resole/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/\$185\.00/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/18500/)).not.toBeInTheDocument()
  })

  it('does not render job details when the fetch fails', async () => {
    testServer.use(...jobDetailHandlers({ jobStatus: 500 }))
    const { container } = renderJob()

    await waitFor(() => expect(container).not.toBeEmptyDOMElement())
    expect(screen.queryByText(/SHOE-00007/)).not.toBeInTheDocument()
  })

  it('renders nothing of the job while it is still loading', async () => {
    let release: (() => void) | undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    testServer.use(
      ...jobDetailHandlers(),
      http.get(`${API_BASE}/shoe-repair-jobs/:id`, async () => {
        await gate
        return HttpResponse.json(makeShoeJob())
      }),
    )
    renderJob()

    expect(screen.queryByText(/SHOE-00007/)).not.toBeInTheDocument()
    release?.()
    await waitFor(() => expect(screen.getAllByText(/SHOE-00007/).length).toBeGreaterThan(0))
  })

  it('survives null optional fields on the shoe', async () => {
    testServer.use(
      ...jobDetailHandlers({
        shoeJob: makeShoeJob({
          shoe: {
            id: 'shoe-1',
            tenant_id: 'tenant-1',
            customer_id: 'cust-1',
            brand: 'Loake',
            model: null,
            colour: null,
            created_at: '2026-01-01T00:00:00Z',
          },
        }),
      }),
    )
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/SHOE-00007/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument()
  })
})
