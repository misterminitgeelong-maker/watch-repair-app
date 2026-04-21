import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Modal } from './ui'

describe('<Modal /> (F-M-ACCESS regression)', () => {
  it('has role=dialog + aria-modal=true and labels itself with the title', () => {
    render(
      <Modal title="Test Dialog" onClose={() => {}}>
        <p>body content</p>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    const labelledBy = dialog.getAttribute('aria-labelledby')
    expect(labelledBy).toBeTruthy()
    // The labelled-by id should resolve to the visible title text.
    const titleEl = labelledBy ? document.getElementById(labelledBy) : null
    expect(titleEl?.textContent).toBe('Test Dialog')
  })

  it('close button has an aria-label and triggers onClose', async () => {
    const onClose = vi.fn()
    render(
      <Modal title="Close me" onClose={onClose}>
        <p>body</p>
      </Modal>,
    )
    const closeBtn = screen.getByRole('button', { name: /close dialog/i })
    await userEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Escape key triggers onClose', () => {
    const onClose = vi.fn()
    render(
      <Modal title="Esc me" onClose={onClose}>
        <p>body</p>
      </Modal>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('clicking inside the panel does NOT close, but backdrop click does', async () => {
    const onClose = vi.fn()
    render(
      <Modal title="Backdrop" onClose={onClose}>
        <button>inside</button>
      </Modal>,
    )
    // Click the inside button — backdrop handler must not fire.
    await userEvent.click(screen.getByRole('button', { name: 'inside' }))
    expect(onClose).not.toHaveBeenCalled()

    // Backdrop is the dialog's parent overlay. Click it directly.
    const dialog = screen.getByRole('dialog')
    const backdrop = dialog.parentElement
    expect(backdrop).not.toBeNull()
    if (backdrop) {
      fireEvent.click(backdrop)
    }
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
