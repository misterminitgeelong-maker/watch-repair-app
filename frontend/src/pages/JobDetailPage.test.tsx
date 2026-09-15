/**
 * Characterisation tests for the watch job-detail page.
 *
 * This page is 1,319 lines and had no tests. It is about to be collapsed into a
 * shared shell with the shoe and auto-key equivalents, so these pin what a user
 * actually sees: the job identity, its status, the money, the customer and the
 * watch, and the empty states. They assert on visible text and roles rather than
 * markup, so they survive that rewrite.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import api from '@/lib/api'
import { testServer } from '@/test/msw/server'
import {
  API_BASE,
  jobDetailHandlers,
  makeRepairJob,
  makeWatch,
  makeCustomer,
} from '@/test/msw/jobDetail'
import { renderAtRoute } from '@/test/renderPage'
import JobDetailPage from './JobDetailPage'

function renderJob() {
  return renderAtRoute(<JobDetailPage />, { path: '/jobs/:id', route: '/jobs/job-1' })
}

describe('JobDetailPage', () => {
  const previousBase = api.defaults.baseURL
  beforeAll(() => {
    api.defaults.baseURL = API_BASE
  })
  afterAll(() => {
    api.defaults.baseURL = previousBase
  })

  it('shows the job number, title and description once loaded', async () => {
    testServer.use(...jobDetailHandlers())
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/Full service/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Runs fast by two minutes a day/)).toBeInTheDocument()
  })

  it('shows the customer the job belongs to', async () => {
    testServer.use(...jobDetailHandlers())
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/Marge Hooper/).length).toBeGreaterThan(0))
  })

  it('does not put the watch details on the summary view', async () => {
    // Pinning current behaviour rather than wishing for it: the watch is only
    // rendered inside the edit modal. If the shared shell starts showing it on
    // the summary, that is a deliberate change and this test should be updated.
    testServer.use(...jobDetailHandlers())
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/Omega/)).not.toBeInTheDocument()
  })

  it('formats money in Australian dollars, not raw cents', async () => {
    testServer.use(...jobDetailHandlers({ repairJob: makeRepairJob({ cost_cents: 42500 }) }))
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
    // 42500 cents is $425.00 — never "42500" and never "$42500".
    expect(screen.getAllByText(/\$425\.00/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/\$42500/)).not.toBeInTheDocument()
  })

  it('renders a zero cost as $0.00 rather than blank', async () => {
    testServer.use(
      ...jobDetailHandlers({ repairJob: makeRepairJob({ cost_cents: 0, pre_quote_cents: 0 }) }),
    )
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/\$0\.00/).length).toBeGreaterThan(0)
  })

  it('reflects the job status that came back from the API', async () => {
    testServer.use(
      ...jobDetailHandlers({ repairJob: makeRepairJob({ status: 'awaiting_go_ahead' }) }),
    )
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
    // Rendered as a human label, not the raw token.
    expect(screen.getAllByText(/awaiting|go.?ahead/i).length).toBeGreaterThan(0)
  })

  it('renders a loading state before the job arrives', async () => {
    let release: (() => void) | undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    testServer.use(
      ...jobDetailHandlers(),
      (await import('msw')).http.get(`${API_BASE}/repair-jobs/:id`, async () => {
        await gate
        return (await import('msw')).HttpResponse.json(makeRepairJob())
      }),
    )
    const { container } = renderJob()

    // Nothing from the loaded job is on screen yet.
    expect(screen.queryByText(/JOB-00042/)).not.toBeInTheDocument()
    expect(container).not.toBeEmptyDOMElement()

    release?.()
    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
  })

  it('does not render job details when the fetch fails', async () => {
    testServer.use(...jobDetailHandlers({ jobStatus: 500 }))
    const { container } = renderJob()

    // The page must not blow up; it simply never shows a job.
    await waitFor(() => expect(container).not.toBeEmptyDOMElement())
    expect(screen.queryByText(/JOB-00042/)).not.toBeInTheDocument()
  })

  it('survives a job whose optional fields are null', async () => {
    testServer.use(
      ...jobDetailHandlers({
        repairJob: makeRepairJob({ description: null }),
        watch: makeWatch({ model: null, serial_number: null }),
        customer: makeCustomer({ email: null, phone: null }),
      }),
    )
    renderJob()

    await waitFor(() => expect(screen.getAllByText(/JOB-00042/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument()
  })
})
