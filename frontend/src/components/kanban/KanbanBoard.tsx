import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import KanbanColumn from './KanbanColumn'
import { findColumnForStatus, groupJobsByKanbanColumn, type KanbanColumnDef } from './columns'

const SCROLL_STEP = 242

interface KanbanBoardProps<J extends { id: string; status: string }> {
  jobs: J[]
  columns: readonly KanbanColumnDef[]
  renderCard: (job: J, column: KanbanColumnDef) => React.ReactNode
  onStatusChange?: (jobId: string, nextStatus: string) => void
  emptyMessage?: string
}

export default function KanbanBoard<J extends { id: string; status: string }>({
  jobs,
  columns,
  renderCard,
  onStatusChange,
  emptyMessage = 'No jobs in this stage.',
}: KanbanBoardProps<J>) {
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const floatRef = React.useRef<HTMLDivElement>(null)
  const [scrollWidth, setScrollWidth] = React.useState(0)
  const [overflowing, setOverflowing] = React.useState(false)
  const [canScrollLeft, setCanScrollLeft] = React.useState(false)
  const [canScrollRight, setCanScrollRight] = React.useState(false)

  const measureScrollEdges = () => {
    const el = scrollRef.current
    if (!el) return
    setCanScrollLeft(el.scrollLeft > 1)
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1)
  }

  // Keep the floating scrollbar's spacer width in sync with the board's
  // scrollable width, and only show it while the board actually overflows.
  React.useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    const measure = () => {
      setScrollWidth(el.scrollWidth)
      setOverflowing(el.scrollWidth > el.clientWidth + 1)
      measureScrollEdges()
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [jobs, columns])

  // Mirror scroll position between the real board and the floating scrollbar.
  const syncFromBoard = () => {
    if (scrollRef.current && floatRef.current) {
      floatRef.current.scrollLeft = scrollRef.current.scrollLeft
    }
    measureScrollEdges()
  }
  const syncFromFloat = () => {
    if (scrollRef.current && floatRef.current) {
      scrollRef.current.scrollLeft = floatRef.current.scrollLeft
    }
    measureScrollEdges()
  }
  const scrollByStep = (direction: 1 | -1) => {
    scrollRef.current?.scrollBy({ left: direction * SCROLL_STEP, behavior: 'smooth' })
  }

  const jobsByColumn = React.useMemo(
    () => groupJobsByKanbanColumn(jobs, columns),
    [jobs, columns],
  )

  return (
    <div style={{ position: 'relative' }}>
      {overflowing && canScrollLeft && (
        <button
          type="button"
          aria-label="Scroll columns left"
          onClick={() => scrollByStep(-1)}
          className="flex items-center justify-center"
          style={{
            position: 'absolute',
            left: -4,
            top: 17,
            zIndex: 10,
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            boxShadow: 'var(--ms-shadow)',
            color: 'var(--ms-text-mid)',
          }}
        >
          <ChevronLeft size={16} />
        </button>
      )}
      {overflowing && canScrollRight && (
        <button
          type="button"
          aria-label="Scroll columns right"
          onClick={() => scrollByStep(1)}
          className="flex items-center justify-center"
          style={{
            position: 'absolute',
            right: -4,
            top: 17,
            zIndex: 10,
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'var(--ms-surface)',
            border: '1px solid var(--ms-border-strong)',
            boxShadow: 'var(--ms-shadow)',
            color: 'var(--ms-text-mid)',
          }}
        >
          <ChevronRight size={16} />
        </button>
      )}
      <div
        ref={scrollRef}
        onScroll={syncFromBoard}
        className="flex gap-3 overflow-x-auto pb-2"
        style={{ scrollbarColor: 'var(--ms-border-strong) transparent' }}
      >
        {columns.map(column => {
          const jobsInColumn = jobsByColumn.get(column.key) ?? []
          return (
            <KanbanColumn
              key={column.key}
              column={column}
              count={jobsInColumn.length}
              acceptsDrop={!!onStatusChange}
              onDropJob={jobId => {
                if (!onStatusChange) return
                const job = jobs.find(j => j.id === jobId)
                if (!job) return
                const sourceColumn = findColumnForStatus(columns, job.status)
                if (sourceColumn?.key === column.key) return
                onStatusChange(jobId, column.statuses[0])
              }}
            >
              {jobsInColumn.length === 0 ? (
                <p className="italic text-center py-6" style={{ fontSize: 11, color: 'var(--ms-text-muted)' }}>
                  {emptyMessage}
                </p>
              ) : (
                jobsInColumn.map(job => <React.Fragment key={job.id}>{renderCard(job, column)}</React.Fragment>)
              )}
            </KanbanColumn>
          )
        })}
      </div>

      {/* Floating horizontal scrollbar that sticks to the bottom of the viewport,
          so you can scroll the board sideways without scrolling the page down. */}
      {overflowing && (
        <div
          ref={floatRef}
          onScroll={syncFromFloat}
          className="overflow-x-auto"
          style={{
            position: 'sticky',
            bottom: 0,
            zIndex: 20,
            scrollbarColor: 'var(--ms-border-strong) transparent',
          }}
          aria-hidden="true"
        >
          <div style={{ width: scrollWidth, height: 1 }} />
        </div>
      )}
    </div>
  )
}
