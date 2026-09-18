import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PeriodChips, PeriodDateInput, PeriodSelect, ReportStateNote } from './ReportControls'

const RANGES = [
  { key: 'day', label: 'Day' },
  { key: 'week', label: 'Week' },
  { key: 'custom', label: 'Custom' },
] as const

describe('PeriodChips', () => {
  it('marks the active period for assistive tech, not by colour alone', () => {
    render(<PeriodChips label="Sales range" options={RANGES} value="week" onChange={() => {}} />)
    expect(screen.getByRole('group', { name: 'Sales range' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Week' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Day' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('reports the chosen period', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<PeriodChips label="Sales range" options={RANGES} value="week" onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Custom' }))
    expect(onChange).toHaveBeenCalledWith('custom')
  })

  it('gives every chip a 44px row on phones and a compact one from sm:', () => {
    render(<PeriodChips label="Sales range" options={RANGES} value="day" onChange={() => {}} />)
    for (const option of RANGES) {
      const chip = screen.getByRole('button', { name: option.label })
      expect(chip.className).toContain('min-h-11')
      expect(chip.className).toContain('sm:min-h-0')
    }
  })
})

describe('PeriodDateInput', () => {
  it('is labelled even though the row shows no visible label', () => {
    render(<PeriodDateInput label="Sales from" value="2026-09-01" onChange={() => {}} />)
    expect(screen.getByLabelText('Sales from')).toHaveValue('2026-09-01')
  })

  it('uses 16px text on phones so iOS does not zoom the page on focus', () => {
    render(<PeriodDateInput label="Sales from" value="" onChange={() => {}} />)
    const input = screen.getByLabelText('Sales from')
    expect(input.className).toContain('text-base')
    expect(input.className).toContain('h-11')
    expect(input.className).toContain('sm:text-xs')
  })

  it('passes the range bounds through', () => {
    render(<PeriodDateInput label="Sales to" value="2026-09-30" min="2026-09-01" onChange={() => {}} />)
    expect(screen.getByLabelText('Sales to')).toHaveAttribute('min', '2026-09-01')
  })

  it('reports the picked date', () => {
    const onChange = vi.fn()
    render(<PeriodDateInput label="Reference date" value="2026-09-01" onChange={onChange} />)
    // Date pickers commit a whole value rather than per-keystroke input.
    fireEvent.change(screen.getByLabelText('Reference date'), { target: { value: '2026-09-18' } })
    expect(onChange).toHaveBeenCalledWith('2026-09-18')
  })
})

describe('PeriodSelect', () => {
  it('is labelled and reports the chosen preset', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <PeriodSelect label="Report period" value="this_week" onChange={onChange}>
        <option value="this_week">This week</option>
        <option value="last_week">Last week</option>
      </PeriodSelect>,
    )
    await user.selectOptions(screen.getByLabelText('Report period'), 'last_week')
    expect(onChange).toHaveBeenCalledWith('last_week')
  })
})

describe('ReportStateNote', () => {
  it('announces partial-period and empty states politely', () => {
    render(<ReportStateNote tone="warn">Partial period: this week is still running.</ReportStateNote>)
    const note = screen.getByRole('status')
    expect(note).toHaveAttribute('aria-live', 'polite')
    expect(note).toHaveTextContent(/partial period/i)
  })
})
