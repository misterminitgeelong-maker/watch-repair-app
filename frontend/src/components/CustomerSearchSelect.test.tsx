import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CustomerSearchSelect } from './CustomerSearchSelect'
import { Modal } from './ui'
import type { Customer } from '@/lib/api'

function makeCustomer(overrides: Partial<Customer>): Customer {
  return {
    id: overrides.id ?? 'c1',
    tenant_id: 't1',
    full_name: overrides.full_name ?? 'Jane Smith',
    email: overrides.email,
    phone: overrides.phone,
    created_at: '2026-01-01T00:00:00Z',
  }
}

const CUSTOMERS: Customer[] = [
  makeCustomer({ id: 'c1', full_name: 'Jane Smith', phone: '0412 111 111' }),
  makeCustomer({ id: 'c2', full_name: 'John Doe', phone: '0412 222 222' }),
  makeCustomer({ id: 'c3', full_name: 'Priya Patel', phone: '0412 333 333' }),
]

describe('CustomerSearchSelect', () => {
  it('filters the suggestion list as the user types', async () => {
    const user = userEvent.setup()
    render(<CustomerSearchSelect customers={CUSTOMERS} value="" onChange={() => {}} />)

    await user.click(screen.getByPlaceholderText('Type name, phone or email…'))
    await user.type(screen.getByPlaceholderText('Type name, phone or email…'), 'Jane')

    expect(await screen.findByText(/Jane Smith/)).toBeInTheDocument()
    expect(screen.queryByText(/John Doe/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Priya Patel/)).not.toBeInTheDocument()
  })

  it('does not match every customer on a letters-only query via the phone branch', async () => {
    // Regression: `q.replace(/\D/g, '')` on a query with no digits (e.g.
    // "Jane") produced '', and every phone number `.includes('')`, so the
    // phone-match branch trivially matched all customers regardless of what
    // was typed - defeating the filter entirely for any non-numeric search.
    const user = userEvent.setup()
    render(<CustomerSearchSelect customers={CUSTOMERS} value="" onChange={() => {}} />)

    await user.click(screen.getByPlaceholderText('Type name, phone or email…'))
    await user.type(screen.getByPlaceholderText('Type name, phone or email…'), 'zzz-no-match')

    await screen.findByText('No customers match')
    expect(screen.queryByText(/Jane Smith/)).not.toBeInTheDocument()
    expect(screen.queryByText(/John Doe/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Priya Patel/)).not.toBeInTheDocument()
  })

  it('calls onChange with the matching customer id on selection', async () => {
    const user = userEvent.setup()
    let selectedId = ''
    render(<CustomerSearchSelect customers={CUSTOMERS} value="" onChange={id => { selectedId = id }} />)

    await user.click(screen.getByPlaceholderText('Type name, phone or email…'))
    await user.type(screen.getByPlaceholderText('Type name, phone or email…'), 'John')
    await user.click(await screen.findByText(/John Doe/))

    expect(selectedId).toBe('c2')
  })

  it('renders the dropdown outside the Modal body, so its overflow-y-auto never clips it', async () => {
    // Regression: every caller renders this inside <Modal>, whose body div
    // (components/ui.tsx) has overflow-y-auto with a fixed max-height. A
    // plain `position: absolute` dropdown gets silently clipped there —
    // the list still filters correctly underneath, it just never becomes
    // visible. The fix portals the dropdown to document.body instead.
    const user = userEvent.setup()
    render(
      <Modal title="New job" onClose={() => {}}>
        <CustomerSearchSelect customers={CUSTOMERS} value="" onChange={() => {}} />
      </Modal>,
    )

    const modalBody = screen.getByText('New job').closest('div')!.parentElement!.querySelector('.overflow-y-auto') as HTMLElement
    expect(modalBody).toBeTruthy()

    await user.click(screen.getByPlaceholderText('Type name, phone or email…'))
    await user.type(screen.getByPlaceholderText('Type name, phone or email…'), 'Priya')

    const match = await screen.findByText(/Priya Patel/)
    // The suggestion must not be a descendant of the clipping modal body.
    expect(within(modalBody).queryByText(/Priya Patel/)).not.toBeInTheDocument()
    expect(document.body.contains(match)).toBe(true)
  })
})
