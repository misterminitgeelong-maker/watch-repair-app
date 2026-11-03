import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import PublicEngravingStatusPage from './PublicEngravingStatusPage'

const order = {
  order_number: 'A-001', status_token: 'tok', event_name: 'Meet', shop_name: 'Shop', athlete_name: 'Mia', line2: null,
  place: '1st', qty: 1, medals_done: 0, status: 'waiting', paid: false, amount_cents: 1500, can_pay_online: true,
  amount_due_cents: 3000, queue_position: 1, wait_minutes: 3, phone_masked: null, created_at: '', ready_at: null,
  ticket_number: null, group_members: [],
}

vi.mock('@/lib/api/engraving', async (orig) => {
  const mod = await orig<typeof import('@/lib/api/engraving')>()
  return { ...mod, getPublicEngravingOrder: vi.fn(() => Promise.resolve({ data: order })) }
})

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/engrave/o/tok']}>
        <Routes><Route path="/engrave/o/:statusToken" element={<PublicEngravingStatusPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PublicEngravingStatusPage payment', () => {
  it('offers card payment for everything still owed', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /Pay \$30\.00 by card/ })).toBeTruthy()
  })
})
