import React from 'react'

import KanbanColumn from './KanbanColumn'
import { findColumnForStatus, type KanbanColumnDef } from './columns'

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
  return (
    <div className="flex gap-3 overflow-x-auto pb-2" style={{ scrollbarColor: 'var(--ms-border-strong) transparent' }}>
      {columns.map(column => {
        const jobsInColumn = jobs.filter(j => column.statuses.includes(j.status))
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
  )
}
