import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
