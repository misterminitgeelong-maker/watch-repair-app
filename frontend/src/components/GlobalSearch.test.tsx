import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'

import { testServer } from '@/test/msw/server'
import GlobalSearch from './GlobalSearch'

describe('<GlobalSearch /> (F-M8 stale-result regression)', () => {
  it('keeps only the latest response when an earlier one resolves last', async () => {
    // Simulate a slow first response and a fast second response: the typical
    // "type fast and an old result overwrites a new one" bug. The fix uses
    // a monotonically-increasing requestIdRef to drop stale results.
    let callNumber = 0
    testServer.use(
      http.get('*/v1/repair-jobs', async ({ request }) => {
        callNumber += 1
        const url = new URL(request.url)
        const q = url.searchParams.get('q') || ''
        // First call ("a"): return SLOW with a stale job title.
        // Second call ("ab"): return FAST with the fresh job title.
        if (callNumber === 1) {
          await new Promise((r) => setTimeout(r, 250))
          return HttpResponse.json([
            { id: 'stale', job_number: 'JOB-1', title: `stale result for "${q}"`, status: 'awaiting_quote', customer_name: null },
          ])
        }
        return HttpResponse.json([
          { id: 'fresh', job_number: 'JOB-2', title: `fresh result for "${q}"`, status: 'awaiting_quote', customer_name: null },
        ])
      }),
      http.get('*/v1/customers', () => HttpResponse.json([])),
    )

    render(
      <MemoryRouter>
        <GlobalSearch open onClose={() => {}} />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText(/Search jobs, customers/i)

    // Type "a" then quickly "b" so two debounced fetches queue up.
    await userEvent.type(input, 'a')
    // Wait slightly past the 280ms debounce so the first fetch is in flight.
    await new Promise((r) => setTimeout(r, 290))
    await userEvent.type(input, 'b')

    // Eventually the fresh result is visible.
    await waitFor(
      () => {
        expect(screen.getByText(/fresh result for "ab"/)).toBeInTheDocument()
      },
      { timeout: 2000 },
    )

    // After the slow first response has had time to resolve, the stale
    // result must NOT have replaced the fresh one.
    await new Promise((r) => setTimeout(r, 400))
    expect(screen.queryByText(/stale result for "a"/)).not.toBeInTheDocument()
    expect(screen.getByText(/fresh result for "ab"/)).toBeInTheDocument()
  })
})
