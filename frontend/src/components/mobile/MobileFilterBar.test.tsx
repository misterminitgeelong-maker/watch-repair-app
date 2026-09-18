import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import MobileFilterBar from './MobileFilterBar'

describe('MobileFilterBar', () => {
  it('keeps search visible and labelled', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <MobileFilterBar
        search={{ value: '', onChange, label: 'Search invoices by number', placeholder: 'Search…' }}
      />,
    )
    const field = screen.getByLabelText('Search invoices by number')
    expect(field).toHaveAttribute('placeholder', 'Search…')
    await user.type(field, 'A')
    expect(onChange).toHaveBeenCalledWith('A')
  })

  it('uses 16px search text on phones so iOS does not zoom', () => {
    render(<MobileFilterBar search={{ value: '', onChange: () => {}, label: 'Search' }} />)
    const field = screen.getByLabelText('Search')
    expect(field.className).toContain('text-base')
    expect(field.className).toContain('h-11')
  })

  it('hides secondary filters until asked, and says how many are active', async () => {
    const user = userEvent.setup()
    render(
      <MobileFilterBar
        primary={<button type="button">Status</button>}
        secondary={<button type="button">Sort by total</button>}
        activeFilters={[{ key: 'status', label: 'Status: Sent', onClear: () => {} }]}
      />,
    )
    // Primary stays put; secondary starts collapsed.
    expect(screen.getByRole('button', { name: 'Status' })).toBeVisible()
    const toggle = screen.getByRole('button', { name: /more filters/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveTextContent('1')
    // `hidden` keeps the collapsed controls out of the accessibility tree too,
    // not merely out of sight.
    expect(screen.queryByRole('button', { name: 'Sort by total' })).not.toBeInTheDocument()

    await user.click(toggle)
    expect(screen.getByRole('button', { name: /hide filters/i })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Sort by total' })).toBeVisible()
  })

  it('names what is filtering the list and clears one filter at a time', async () => {
    const user = userEvent.setup()
    const clearStatus = vi.fn()
    render(
      <MobileFilterBar
        activeFilters={[
          { key: 'status', label: 'Status: Sent', onClear: clearStatus },
          { key: 'age', label: 'Sent 7+ days ago', onClear: () => {} },
        ]}
        onClearAll={() => {}}
      />,
    )
    expect(screen.getByText('Status: Sent')).toBeInTheDocument()
    expect(screen.getByText('Sent 7+ days ago')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filter Status: Sent' }))
    expect(clearStatus).toHaveBeenCalledTimes(1)
  })

  it('offers an obvious clear-all only while filters are on', async () => {
    const user = userEvent.setup()
    const clearAll = vi.fn()
    const { rerender } = render(<MobileFilterBar activeFilters={[]} onClearAll={clearAll} />)
    expect(screen.queryByRole('button', { name: /clear all filters/i })).not.toBeInTheDocument()

    rerender(
      <MobileFilterBar activeFilters={[{ key: 'q', label: 'Search: abc', onClear: () => {} }]} onClearAll={clearAll} />,
    )
    await user.click(screen.getByRole('button', { name: /clear all filters/i }))
    expect(clearAll).toHaveBeenCalledTimes(1)
  })

  it('announces the result count politely', () => {
    render(<MobileFilterBar resultSummary="12 of 40 invoices" />)
    const summary = screen.getByRole('status')
    expect(summary).toHaveAttribute('aria-live', 'polite')
    expect(summary).toHaveTextContent('12 of 40 invoices')
  })

  it('renders nothing extra when given no filters at all', () => {
    render(<MobileFilterBar />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
