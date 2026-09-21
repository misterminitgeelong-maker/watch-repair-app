import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import KanbanColumn from './KanbanColumn'
import KanbanBoard from './KanbanBoard'
import type { KanbanColumnDef } from './columns'

beforeAll(() => {
  // jsdom has no ResizeObserver, and the board measures itself with one.
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})

const column: KanbanColumnDef = {
  key: 'in_progress',
  label: 'In progress',
  statuses: ['in_progress'],
  color: '#2F6A3D',
  bg: '#EAF4EA',
}

function dropZoneOf(container: HTMLElement) {
  // The column's body — the element that carries the drop highlight.
  return container.querySelector('[data-testid="card"]')!.parentElement!
}

describe('KanbanColumn drop highlight', () => {
  it('stays lit while the pointer crosses the cards inside it', () => {
    const { container } = render(
      <KanbanColumn column={column} count={1} acceptsDrop onDropJob={() => {}}>
        <div data-testid="card">A job card</div>
      </KanbanColumn>,
    )
    const zone = dropZoneOf(container)
    const card = screen.getByTestId('card')

    fireEvent.dragEnter(zone)
    fireEvent.dragOver(zone, { dataTransfer: { dropEffect: '' } })
    expect(zone.style.outline).toContain('dashed')

    // Moving onto a card inside the column: enter fires on the card and leave
    // fires on the column body. Clearing on that leave was what made the
    // highlight strobe all the way down a column.
    fireEvent.dragEnter(card)
    fireEvent.dragLeave(zone)
    expect(zone.style.outline).toContain('dashed')

    // And back off the card onto the column body — still inside.
    fireEvent.dragEnter(zone)
    fireEvent.dragLeave(card)
    expect(zone.style.outline).toContain('dashed')
  })

  it('clears once the pointer genuinely leaves', () => {
    const { container } = render(
      <KanbanColumn column={column} count={1} acceptsDrop onDropJob={() => {}}>
        <div data-testid="card">A job card</div>
      </KanbanColumn>,
    )
    const zone = dropZoneOf(container)

    fireEvent.dragEnter(zone)
    fireEvent.dragOver(zone, { dataTransfer: { dropEffect: '' } })
    expect(zone.style.outline).toContain('dashed')

    fireEvent.dragLeave(zone)
    expect(zone.style.outline).toBe('none')
  })

  it('does not get stuck lit after an unbalanced leave', () => {
    const { container } = render(
      <KanbanColumn column={column} count={1} acceptsDrop onDropJob={() => {}}>
        <div data-testid="card">A job card</div>
      </KanbanColumn>,
    )
    const zone = dropZoneOf(container)

    // A drag that ends oddly (cancelled, or a leave the browser never paired)
    // must not leave the counter negative and the next drag permanently lit.
    fireEvent.dragLeave(zone)
    fireEvent.dragLeave(zone)
    fireEvent.dragEnter(zone)
    expect(zone.style.outline).toContain('dashed')
    fireEvent.dragLeave(zone)
    expect(zone.style.outline).toBe('none')
  })
})

describe('KanbanBoard', () => {
  const columns = [column, { ...column, key: 'done', label: 'Done', statuses: ['done'] }] as const
  const jobs = [{ id: 'j1', status: 'in_progress' }]

  it('moves a job to the column it was dropped on', () => {
    const onStatusChange = vi.fn()
    const { container } = render(
      <MemoryRouter>
        <KanbanBoard
          jobs={jobs}
          columns={columns}
          onStatusChange={onStatusChange}
          renderCard={job => <div data-testid={`card-${job.id}`}>{job.id}</div>}
        />
      </MemoryRouter>,
    )

    const doneZone = container.querySelectorAll('[style*="min-height"]')[1] as HTMLElement
    fireEvent.drop(doneZone, { dataTransfer: { getData: () => 'j1' } })
    expect(onStatusChange).toHaveBeenCalledWith('j1', 'done')
  })

  it('ignores a drop back onto the column the job came from', () => {
    const onStatusChange = vi.fn()
    const { container } = render(
      <MemoryRouter>
        <KanbanBoard
          jobs={jobs}
          columns={columns}
          onStatusChange={onStatusChange}
          renderCard={job => <div data-testid={`card-${job.id}`}>{job.id}</div>}
        />
      </MemoryRouter>,
    )

    const sameZone = container.querySelectorAll('[style*="min-height"]')[0] as HTMLElement
    fireEvent.drop(sameZone, { dataTransfer: { getData: () => 'j1' } })
    expect(onStatusChange).not.toHaveBeenCalled()
  })
})


describe('KanbanBoard sideways scrolling', () => {
  const columns = [column, { ...column, key: 'done', label: 'Done', statuses: ['done'] }] as const
  const jobs = [{ id: 'j1', status: 'in_progress' }]

  function renderBoard() {
    const view = render(
      <MemoryRouter>
        <KanbanBoard
          jobs={jobs}
          columns={columns}
          renderCard={job => <div>{job.id}</div>}
        />
      </MemoryRouter>,
    )
    const board = view.container.querySelector('.overflow-x-auto') as HTMLDivElement
    return { ...view, board }
  }

  it('does not write the board back while the board is the one being scrolled', () => {
    const { board } = renderBoard()

    // The board is mid-gesture and has moved on under momentum.
    board.scrollLeft = 400
    fireEvent.scroll(board)

    // The floating scrollbar's own scroll event arrives late, carrying the
    // position it had caught up to. Acting on it would drag the board back
    // there and break the momentum — that was the stutter.
    const scrollbar = document.createElement('div')
    Object.defineProperty(scrollbar, 'scrollLeft', { value: 280, writable: true })

    board.scrollLeft = 520
    fireEvent.scroll(board)
    expect(board.scrollLeft).toBe(520)
  })

  it('lets the other element take over once the gesture stops', () => {
    vi.useFakeTimers()
    try {
      const { board } = renderBoard()
      board.scrollLeft = 100
      fireEvent.scroll(board)

      // Ownership is released after a short idle, so the floating scrollbar
      // can drive the next time the user grabs it instead.
      act(() => {
        vi.advanceTimersByTime(300)
      })
      expect(board.scrollLeft).toBe(100)
    } finally {
      vi.useRealTimers()
    }
  })
})
