import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button, MobileActionMenu, Modal } from './ui'

describe('Modal', () => {
  it('exposes dialog semantics and labels from the title', () => {
    render(
      <Modal title="New Job Ticket" onClose={() => {}}>
        <p>Body</p>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog', { name: 'New Job Ticket' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })

  it('closes on Escape unless close is disabled', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { rerender } = render(
      <Modal title="Edit" onClose={onClose}>
        <button type="button">Save</button>
      </Modal>,
    )
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    onClose.mockClear()
    rerender(
      <Modal title="Edit" onClose={onClose} closeDisabled>
        <button type="button">Save</button>
      </Modal>,
    )
    await user.keyboard('{Escape}')
    expect(onClose).not.toHaveBeenCalled()
  })

  it('keeps Tab inside the dialog and restores focus on unmount', async () => {
    const user = userEvent.setup()
    const trigger = document.createElement('button')
    trigger.textContent = 'Open'
    document.body.appendChild(trigger)
    trigger.focus()

    const { unmount } = render(
      <Modal title="Focus trap" onClose={() => {}}>
        <button type="button">First</button>
        <button type="button">Last</button>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog.contains(document.activeElement)).toBe(true)

    await user.tab()
    expect(dialog.contains(document.activeElement)).toBe(true)
    await user.tab()
    expect(dialog.contains(document.activeElement)).toBe(true)
    await user.tab()
    expect(dialog.contains(document.activeElement)).toBe(true)

    unmount()
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it('keeps focus in a field while typing, even with a fresh onClose each render', async () => {
    const user = userEvent.setup()

    // Mirrors how every caller uses Modal: an inline arrow for onClose, and a
    // parent that re-renders on each keystroke. The focus effect must not
    // re-run, or focus is yanked back to the first field on every letter.
    function Harness() {
      const [value, setValue] = useState('')
      return (
        <Modal title="Add shop" onClose={() => {}}>
          <input aria-label="First field" />
          <input aria-label="Shop name" value={value} onChange={e => setValue(e.target.value)} />
        </Modal>
      )
    }

    render(<Harness />)
    const field = screen.getByLabelText('Shop name')
    await user.click(field)
    await user.keyboard('Chadstone')

    expect(field).toHaveValue('Chadstone')
    expect(document.activeElement).toBe(field)
  })
})

describe('Button', () => {
  it('forwards refs and extra button attributes', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    const ref = { current: null as HTMLButtonElement | null }
    render(
      <Button ref={el => { ref.current = el }} aria-label="Delete job" data-testid="danger-btn" onClick={onClick}>
        Delete
      </Button>,
    )
    const btn = screen.getByRole('button', { name: 'Delete job' })
    expect(btn).toHaveAttribute('data-testid', 'danger-btn')
    expect(ref.current).toBe(btn)
    await user.click(btn)
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

describe('MobileActionMenu', () => {
  it('opens secondary actions and closes after choosing one', async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()
    render(
      <MobileActionMenu actions={[{ label: 'Edit job', onClick: onEdit }]} />,
    )

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'More actions' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()

    await user.click(screen.getByRole('menuitem', { name: 'Edit job' }))
    expect(onEdit).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
