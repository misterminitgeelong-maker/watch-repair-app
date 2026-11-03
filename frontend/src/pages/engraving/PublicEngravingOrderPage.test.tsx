import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { renderAtRoute } from '@/test/renderPage'
import * as engravingApi from '@/lib/api/engraving'
import PublicEngravingOrderPage from './PublicEngravingOrderPage'

vi.mock('@/lib/api/engraving', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/engraving')>()
  return {
    ...actual,
    getPublicEngravingEvent: vi.fn(),
    createPublicEngravingOrder: vi.fn(),
  }
})

const event = {
  name: 'Little Athletics — Saturday',
  shop_name: 'Minit Chadstone',
  event_date: '2026-11-07',
  location: null,
  price_cents: 1500,
  accepting_orders: true,
  status: 'open' as const,
  wait_minutes: 12,
  medals_ahead: 4,
  name_max: 24,
  line2_max: 28,
  places: engravingApi.ENGRAVING_PLACES,
}

function renderPage() {
  return renderAtRoute(<PublicEngravingOrderPage />, { path: '/engrave/:token', route: '/engrave/abc123' })
}

describe('PublicEngravingOrderPage', () => {
  beforeEach(() => {
    vi.mocked(engravingApi.getPublicEngravingEvent).mockResolvedValue({ data: event } as never)
    vi.mocked(engravingApi.createPublicEngravingOrder).mockResolvedValue({
      data: { status_token: 'tok-1', order_number: 'A-001' },
    } as never)
  })

  it('previews the engraving live and totals by quantity', async () => {
    renderPage()
    const name = await screen.findByLabelText("Athlete's name")
    await userEvent.type(name, 'Mia Thompson')
    expect(screen.getByRole('img', { name: /Medal preview: Mia Thompson, 1st Place/ })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'One more medal' }))
    expect(screen.getByText('Total $30.00')).toBeInTheDocument()
  })

  it('needs the spelling check before ordering, then submits the order', async () => {
    renderPage()
    await userEvent.type(await screen.findByLabelText("Athlete's name"), 'Mia Thompson')
    await userEvent.type(screen.getByLabelText(/Event or second line/), 'U9 Girls 100m')
    const submit = screen.getByRole('button', { name: /Tick the spelling check/ })
    expect(submit).toBeDisabled()

    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: /Place order/ }))

    await waitFor(() =>
      expect(engravingApi.createPublicEngravingOrder).toHaveBeenCalledWith('abc123', {
        athlete_name: 'Mia Thompson',
        line2: 'U9 Girls 100m',
        place: '1st',
        qty: 1,
        phone: null,
      }),
    )
  })

  it('tells parents when orders are paused', async () => {
    vi.mocked(engravingApi.getPublicEngravingEvent).mockResolvedValue({
      data: { ...event, accepting_orders: false, status: 'paused' },
    } as never)
    renderPage()
    expect(await screen.findByText(/Orders are paused/)).toBeInTheDocument()
  })
})
