/**
 * Characterisation tests for the mobile services (auto key) job-detail page.
 *
 * At 1,631 lines this is the largest of the three and the most divergent — it
 * carries vehicle fields and dispatch concepts the other two have no notion of.
 * The collapse plan does this vertical last for that reason, so these tests
 * matter most.
 *
 * AuthContext is mocked rather than provided: the page gates parts of itself on
 * hasFeature, and a test should be able to state the feature set outright.
 */
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import api from '@/lib/api'
import { testServer } from '@/test/msw/server'
import { API_BASE, jobDetailHandlers, makeAutoKeyJob } from '@/test/msw/jobDetail'
import { renderAtRoute } from '@/test/renderPage'

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    role: 'owner',
    planCode: 'pro',
    product: 'mainspring',
    tenantSlug: 'demo',
    featuresKnown: true,
    authStatus: 'authenticated',
    hasFeature: () => true,
  }),
}))

async function renderJob() {
  const { default: AutoKeyJobDetailPage } = await import('./AutoKeyJobDetailPage')
  return renderAtRoute(<AutoKeyJobDetailPage />, {
    path: '/auto-key-jobs/:id',
    route: '/auto-key-jobs/job-1',
  })
}

describe('AutoKeyJobDetailPage', () => {
  const previousBase = api.defaults.baseURL
  beforeAll(() => {
    api.defaults.baseURL = API_BASE
  })
  afterAll(() => {
    api.defaults.baseURL = previousBase
  })

  it('shows the job number and title once loaded', async () => {
    testServer.use(...jobDetailHandlers())
    await renderJob()

    await waitFor(() => expect(screen.getAllByText(/AK-00013/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/Spare key cut and programmed/).length).toBeGreaterThan(0)
  })

  it('shows the vehicle, which is what makes this vertical different', async () => {
    testServer.use(...jobDetailHandlers())
    await renderJob()

    await waitFor(() => expect(screen.getAllByText(/Toyota/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/HiLux/).length).toBeGreaterThan(0)
  })

  it('shows the customer', async () => {
    testServer.use(...jobDetailHandlers())
    await renderJob()

    await waitFor(() => expect(screen.getAllByText(/Marge Hooper/).length).toBeGreaterThan(0))
  })

  it('reflects the status that came back from the API', async () => {
    testServer.use(
      ...jobDetailHandlers({ autoKeyJob: makeAutoKeyJob({ status: 'awaiting_go_ahead' }) }),
    )
    await renderJob()

    await waitFor(() => expect(screen.getAllByText(/AK-00013/).length).toBeGreaterThan(0))
    expect(screen.getAllByText(/awaiting|go.?ahead/i).length).toBeGreaterThan(0)
  })

  it('survives a job with no vehicle details at all', async () => {
    // Every vehicle field is nullable on the backend model.
    testServer.use(
      ...jobDetailHandlers({
        autoKeyJob: makeAutoKeyJob({
          vehicle_make: null,
          vehicle_model: null,
          vehicle_year: null,
          registration_plate: null,
        }),
      }),
    )
    await renderJob()

    await waitFor(() => expect(screen.getAllByText(/AK-00013/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    expect(screen.queryByText(/null/)).not.toBeInTheDocument()
  })

  it('does not render job details when the fetch fails', async () => {
    testServer.use(...jobDetailHandlers({ jobStatus: 500 }))
    const { container } = await renderJob()

    await waitFor(() => expect(container).not.toBeEmptyDOMElement())
    expect(screen.queryByText(/AK-00013/)).not.toBeInTheDocument()
  })

  it('renders nothing of the job while it is still loading', async () => {
    let release: (() => void) | undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    testServer.use(
      ...jobDetailHandlers(),
      http.get(`${API_BASE}/auto-key-jobs/:id`, async () => {
        await gate
        return HttpResponse.json(makeAutoKeyJob())
      }),
    )
    await renderJob()

    expect(screen.queryByText(/AK-00013/)).not.toBeInTheDocument()
    release?.()
    await waitFor(() => expect(screen.getAllByText(/AK-00013/).length).toBeGreaterThan(0))
  })

  it('renders a date rather than a raw timestamp or Invalid Date', async () => {
    testServer.use(
      ...jobDetailHandlers({ autoKeyJob: makeAutoKeyJob({ created_at: '2026-01-02T03:04:05Z' }) }),
    )
    await renderJob()

    await waitFor(() => expect(screen.getAllByText(/AK-00013/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument()
    expect(screen.queryByText(/2026-01-02T03:04:05Z/)).not.toBeInTheDocument()
  })
})
