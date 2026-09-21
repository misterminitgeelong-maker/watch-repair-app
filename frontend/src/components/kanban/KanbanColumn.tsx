import React, { useState } from 'react'

import type { KanbanColumnDef } from './columns'

interface KanbanColumnProps {
  column: KanbanColumnDef
  count: number
  children: React.ReactNode
  onDropJob?: (jobId: string) => void
  acceptsDrop?: boolean
}

export default function KanbanColumn({ column, count, children, onDropJob, acceptsDrop }: KanbanColumnProps) {
  const [isOver, setIsOver] = useState(false)
  // How many nested elements the drag is currently inside — see onDragLeave.
  const depth = React.useRef(0)

  return (
    <div
      style={{
        width: 230,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
      onDragOver={e => {
        if (!acceptsDrop) return
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
        if (!isOver) setIsOver(true)
      }}
      onDragEnter={() => {
        if (!acceptsDrop) return
        depth.current += 1
        if (!isOver) setIsOver(true)
      }}
      onDragLeave={() => {
        if (!acceptsDrop) return
        // Both dragenter and dragleave bubble from every card inside this
        // column, so entering a card fires leave on the column too. Clearing
        // on each one made the highlight strobe the whole way down a column.
        // Counting depth instead means we only clear on the leave that
        // actually takes the pointer out. Deliberately not using
        // relatedTarget, which Safari reports as null mid-drag.
        depth.current -= 1
        if (depth.current <= 0) {
          depth.current = 0
          setIsOver(false)
        }
      }}
      onDrop={e => {
        if (!acceptsDrop) return
        e.preventDefault()
        depth.current = 0
        setIsOver(false)
        const jobId = e.dataTransfer.getData('text/job-id')
        if (jobId && onDropJob) onDropJob(jobId)
      }}
    >
      <div
        style={{
          height: 3,
          background: column.color,
          borderTopLeftRadius: 'var(--ms-radius)',
          borderTopRightRadius: 'var(--ms-radius)',
        }}
      />
      <div
        style={{
          background: 'var(--ms-surface)',
          padding: '8px 12px',
          borderLeft: '1px solid var(--ms-border)',
          borderRight: '1px solid var(--ms-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--ms-text)', letterSpacing: '0.02em' }}>
          {column.label}
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: '2px 7px',
            borderRadius: 99,
            background: column.bg,
            color: column.color,
          }}
        >
          {count}
        </span>
      </div>
      <div
        style={{
          background: isOver ? column.bg : 'var(--ms-bg)',
          border: '1px solid var(--ms-border)',
          borderTop: 'none',
          borderBottomLeftRadius: 'var(--ms-radius)',
          borderBottomRightRadius: 'var(--ms-radius)',
          padding: '10px 8px',
          flex: 1,
          minHeight: 120,
          transition: 'background 120ms ease',
          outline: isOver ? `2px dashed ${column.color}` : 'none',
          outlineOffset: -4,
        }}
      >
        {children}
      </div>
    </div>
  )
}
