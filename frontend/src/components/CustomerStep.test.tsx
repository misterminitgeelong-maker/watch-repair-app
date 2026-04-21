import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { renderHook } from '@testing-library/react'

import { testServer } from '@/test/msw/server'
import { CustomerStep, useCustomerStep } from './CustomerStep'

function wrap(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

function Harness(props: {
  onNextSpy?: () => void
  onCancelSpy?: () => void
  includeAddressAndNotes?: boolean
  includePhoneMatchHint?: boolean
  error?: string | null
}) {
  const state = useCustomerStep()
  return (
    <CustomerStep
      state={state}
      includeAddressAndNotes={props.includeAddressAndNotes}
      includePhoneMatchHint={props.includePhoneMatchHint}
      error={props.error ?? null}
      onNext={props.onNextSpy ?? (() => {})}
      onCancel={props.onCancelSpy}
    />
  )
}

describe('<CustomerStep /> (M4 shared extraction)', () => {
  it('watch-style step shows address + notes + cancel', async () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    render(wrap(<Harness includeAddressAndNotes includePhoneMatchHint onCancelSpy={() => {}} />))
    await userEvent.click(screen.getByRole('button', { name: /new customer/i }))
    expect(screen.getByText(/Address/i)).toBeInTheDocument()
    expect(screen.getByText(/Notes/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('shoe-style step hides address + notes and cancel', async () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    render(wrap(<Harness />))
    await userEvent.click(screen.getByRole('button', { name: /new customer/i }))
    expect(screen.queryByText(/Address/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Notes/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument()
  })

  it('surfaces the error prop above the primary button', () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    render(wrap(<Harness error="Please select a customer." />))
    expect(screen.getByText('Please select a customer.')).toBeInTheDocument()
  })

  it('invokes onNext when the primary button is clicked', async () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    const onNext = vi.fn()
    render(wrap(<Harness onNextSpy={onNext} />))
    await userEvent.click(screen.getByRole('button', { name: /next|continue/i }))
    expect(onNext).toHaveBeenCalled()
  })
})

describe('useCustomerStep.submit (M4 shared extraction)', () => {
  function HookHarness({ onResult }: { onResult: (v: unknown) => void }) {
    const s = useCustomerStep()
    return (
      <div>
        <button onClick={() => s.setCustomerMode('new')}>switch-new</button>
        <button
          onClick={() =>
            s.setNewCustomerField('full_name', 'Pat Smith')
          }
        >
          name
        </button>
        <button onClick={async () => onResult(await s.submit())}>go</button>
        <span data-testid="mode">{s.customerMode}</span>
      </div>
    )
  }

  it('returns an error when new-mode submits without a name', async () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    const got: unknown[] = []
    render(wrap(<HookHarness onResult={(v) => got.push(v)} />))
    await userEvent.click(screen.getByRole('button', { name: 'switch-new' }))
    await userEvent.click(screen.getByRole('button', { name: 'go' }))
    expect(got).toHaveLength(1)
    expect(got[0]).toMatchObject({ ok: false, error: expect.stringMatching(/name/i) })
  })

  it('returns an error when existing-mode submits without a selection', async () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    const got: unknown[] = []
    render(wrap(<HookHarness onResult={(v) => got.push(v)} />))
    await userEvent.click(screen.getByRole('button', { name: 'go' }))
    expect(got[0]).toMatchObject({ ok: false, error: expect.stringMatching(/select/i) })
  })

  it('creates the customer and returns ok + id when new-mode submits with a name', async () => {
    testServer.use(
      http.get('*/v1/customers', () => HttpResponse.json([])),
      http.post('*/v1/customers', async () =>
        HttpResponse.json(
          { id: 'cust-abc', full_name: 'Pat Smith', phone: null, email: null },
          { status: 201 },
        ),
      ),
    )
    const got: unknown[] = []
    render(wrap(<HookHarness onResult={(v) => got.push(v)} />))
    await userEvent.click(screen.getByRole('button', { name: 'switch-new' }))
    await userEvent.click(screen.getByRole('button', { name: 'name' }))
    await userEvent.click(screen.getByRole('button', { name: 'go' }))
    expect(got[0]).toMatchObject({ ok: true, customerId: 'cust-abc' })
  })
})

// Simple renderHook sanity for the returned shape — cheap guardrail against
// accidental rename / removal breaks in future refactors.
describe('useCustomerStep return shape', () => {
  it('exposes the documented fields', () => {
    testServer.use(http.get('*/v1/customers', () => HttpResponse.json([])))
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useCustomerStep(), {
      wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>,
    })
    expect(result.current).toMatchObject({
      customerMode: 'existing',
      selectedCustomerId: '',
      createdCustomerId: '',
      phoneMatch: null,
      activeCustomerId: '',
    })
    expect(typeof result.current.submit).toBe('function')
    expect(typeof result.current.setCustomerMode).toBe('function')
  })
})
