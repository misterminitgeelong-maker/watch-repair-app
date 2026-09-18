import { act, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MobileStickyBar from './MobileStickyBar'
import { isEditableElement } from '@/hooks/useEditableFieldFocused'

function focus(el: HTMLElement) {
  act(() => {
    el.focus()
    el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
  })
}

function blur(el: HTMLElement) {
  act(() => {
    el.blur()
    el.dispatchEvent(new FocusEvent('focusout', { bubbles: true }))
  })
}

describe('MobileStickyBar', () => {
  it('renders its actions above the bottom tab bar and the home indicator', () => {
    render(<MobileStickyBar label="Cart total and checkout"><button type="button">Complete sale</button></MobileStickyBar>)
    const bar = screen.getByTestId('mobile-sticky-bar')
    // --ms-mobile-bar-h already folds in env(safe-area-inset-bottom).
    expect(bar).toHaveStyle({ bottom: 'var(--ms-mobile-bar-h)' })
    expect(bar.className).toContain('md:hidden')
    expect(bar).toHaveAttribute('aria-label', 'Cart total and checkout')
  })

  it('steps aside while a text field is focused so the keyboard cannot bury it', () => {
    render(
      <>
        <input aria-label="Description" />
        <MobileStickyBar><button type="button">Complete sale</button></MobileStickyBar>
      </>,
    )
    expect(screen.getByTestId('mobile-sticky-bar')).toBeInTheDocument()

    const field = screen.getByLabelText('Description')
    focus(field)
    expect(screen.queryByTestId('mobile-sticky-bar')).not.toBeInTheDocument()

    blur(field)
    expect(screen.getByTestId('mobile-sticky-bar')).toBeInTheDocument()
  })

  it('stays put for focus on a button, which opens no keyboard', () => {
    render(
      <>
        <button type="button">Add item</button>
        <MobileStickyBar><button type="button">Complete sale</button></MobileStickyBar>
      </>,
    )
    focus(screen.getByText('Add item'))
    expect(screen.getByTestId('mobile-sticky-bar')).toBeInTheDocument()
  })

  it('can be told never to hide', () => {
    render(
      <>
        <input aria-label="Description" />
        <MobileStickyBar hideWhileTyping={false}><button type="button">Save</button></MobileStickyBar>
      </>,
    )
    focus(screen.getByLabelText('Description'))
    expect(screen.getByTestId('mobile-sticky-bar')).toBeInTheDocument()
  })
})

describe('isEditableElement', () => {
  it('recognises the fields that open a software keyboard', () => {
    for (const type of ['text', 'number', 'email', 'tel', 'search', 'date']) {
      const input = document.createElement('input')
      input.type = type
      expect(isEditableElement(input)).toBe(true)
    }
    expect(isEditableElement(document.createElement('textarea'))).toBe(true)
  })

  it('ignores controls that do not', () => {
    const checkbox = document.createElement('input')
    checkbox.type = 'checkbox'
    expect(isEditableElement(checkbox)).toBe(false)
    expect(isEditableElement(document.createElement('button'))).toBe(false)
    expect(isEditableElement(document.createElement('select'))).toBe(false)
    expect(isEditableElement(null)).toBe(false)
  })
})
