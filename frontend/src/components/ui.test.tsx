import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button, Modal } from './ui'

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
