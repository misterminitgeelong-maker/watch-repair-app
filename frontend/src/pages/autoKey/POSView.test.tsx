import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAtRoute } from '@/test/renderPage'
import { POSView } from './POSView'
import { createAutoKeyInvoiceFromQuote, createAutoKeyJob, createAutoKeyQuote, getMobileServicesPricingMeta, listAutoKeyJobs, updateAutoKeyJobStatus } from '@/lib/api'

vi.mock('@/lib/api', async original => ({ ...await original<typeof import('@/lib/api')>(), createAutoKeyInvoiceFromQuote: vi.fn(), createAutoKeyJob: vi.fn(), createAutoKeyQuote: vi.fn(), getMobileServicesPricingMeta: vi.fn(), listAutoKeyJobs: vi.fn(), updateAutoKeyJobStatus: vi.fn() }))
vi.mock('@/components/CustomerSearchSelect', () => ({ CustomerSearchSelect: ({ onChange }: { onChange: (id: string) => void }) => <button onClick={() => onChange('customer')}>Select test customer</button> }))
vi.mock('@/components/PricingSelector', () => ({ default: () => null }))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getMobileServicesPricingMeta).mockResolvedValue({ data: { enabled_categories: ['general_service'] } } as unknown as Awaited<ReturnType<typeof getMobileServicesPricingMeta>>)
  vi.mocked(listAutoKeyJobs).mockResolvedValue({ data: [] } as unknown as Awaited<ReturnType<typeof listAutoKeyJobs>>)
  vi.mocked(createAutoKeyJob).mockResolvedValue({ data: { id: 'job' } } as unknown as Awaited<ReturnType<typeof createAutoKeyJob>>)
  vi.mocked(createAutoKeyQuote).mockResolvedValue({ data: { id: 'quote' } } as unknown as Awaited<ReturnType<typeof createAutoKeyQuote>>)
  vi.mocked(createAutoKeyInvoiceFromQuote).mockResolvedValue({ data: { id: 'invoice' } } as unknown as Awaited<ReturnType<typeof createAutoKeyInvoiceFromQuote>>)
  vi.mocked(updateAutoKeyJobStatus).mockResolvedValue({ data: { id: 'job' } } as unknown as Awaited<ReturnType<typeof updateAutoKeyJobStatus>>)
})

function renderPos() {
  return renderAtRoute(<POSView customers={[]} customerAccounts={[]} onComplete={vi.fn()} initialMode="sale" />, { path: '/auto-key', route: '/auto-key' })
}

describe('Mobile Services POS discounts', () => {
  it('discounts the next custom item, resets the entry setting, and saves the discounted sale', async () => {
    const user = userEvent.setup()
    renderPos()
    await user.click(screen.getByRole('button', { name: 'Select test customer' }))
    await user.selectOptions(screen.getByLabelText('Next item discount type'), 'percent')
    await user.type(screen.getByLabelText('Next item discount value'), '10')
    await user.type(screen.getByLabelText('Custom item description'), 'Mobile key')
    await user.type(screen.getByLabelText('Custom item price'), '100')
    await user.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByLabelText('Next item discount type')).toHaveValue('none')
    expect(screen.getByText('10% discount · Save $10.00')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Increase quantity of Mobile key' }))
    expect(screen.getByText('10% discount · Save $20.00')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Complete sale' })[0])
    await waitFor(() => expect(createAutoKeyQuote).toHaveBeenCalledWith('job', { line_items: [{ description: 'Mobile key (10% discount; was $100.00 each)', quantity: 2, unit_price_cents: 9000 }], gst_enabled: true, gst_inclusive: true }))
    expect(createAutoKeyJob).toHaveBeenCalledWith(expect.objectContaining({ cost_cents: 18000 }))
    expect(createAutoKeyInvoiceFromQuote).toHaveBeenCalledWith('job', 'quote')
  })
  it('edits a quick-item discount and prevents checkout above its price', async () => {
    const user = userEvent.setup()
    renderPos()
    await user.click(await screen.findByRole('button', { name: /^Gain entry/ }))
    await user.selectOptions(screen.getByLabelText('Discount type for Gain entry — Callout charged separately'), 'amount')
    await user.type(screen.getByLabelText('Discount value for Gain entry — Callout charged separately'), '101')
    expect(screen.getByRole('alert')).toHaveTextContent('Dollar discount cannot exceed the item price.')
    for (const button of screen.getAllByRole('button', { name: 'Complete sale' })) expect(button).toBeDisabled()
    await user.clear(screen.getByLabelText('Discount value for Gain entry — Callout charged separately'))
    await user.type(screen.getByLabelText('Discount value for Gain entry — Callout charged separately'), '15')
    expect(screen.getByText('$15.00 discount per item · Save $15.00')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Discount type for Gain entry — Callout charged separately'), 'none')
    expect(screen.queryByText('Item discounts')).not.toBeInTheDocument()
  })
  it('keeps services and different discounts separate when their prices match', async () => {
    const user = userEvent.setup()
    renderPos()
    await user.click(await screen.findByRole('button', { name: /^Gain entry/ }))
    await user.click(screen.getByRole('button', { name: /Diagnostic fee/ }))
    await user.selectOptions(screen.getByLabelText('Next item discount type'), 'percent')
    await user.type(screen.getByLabelText('Next item discount value'), '10')
    await user.click(screen.getByRole('button', { name: /^Gain entry/ }))
    expect(screen.getAllByText('Gain entry — Callout charged separately')).toHaveLength(2)
    expect(screen.getByText('Diagnostic fee — Callout charged separately')).toBeInTheDocument()
    expect(screen.getByText('10% discount · Save $10.00')).toBeInTheDocument()
  })
})
