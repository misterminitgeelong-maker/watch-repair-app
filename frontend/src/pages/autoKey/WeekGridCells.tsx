import type { ReactNode } from 'react'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import { GripVertical, MapPin } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { AklComplexityPill, parseAklComplexity } from '@/components/auto-key/AklComplexityPill'
import { STATUS_LABELS } from '@/lib/utils'
import {
  type WeekSchedulerJob,
  weekJobVehicleSummary,
  weekJobSecondarySummary,
  stopDragControlPropagation,
  WEEK_UNSCHEDULED_DROP_ID,
  weekDayDropId,
} from './dispatchHelpers'

/**
 * Presentational drag-and-drop cells for the auto-key week scheduler,
 * extracted from AutoKeyJobsPage. Each is a self-contained component driven
 * entirely by props (plus dnd-kit) — no page state.
 */

export function WeekJobChip({
  job,
  selected = false,
  isDragging = false,
  isOverlay = false,
  compact = false,
  customerName,
  assignedTechName,
  onMoveToggle,
}: {
  job: WeekSchedulerJob
  selected?: boolean
  isDragging?: boolean
  isOverlay?: boolean
  compact?: boolean
  customerName?: string
  assignedTechName?: string
  onMoveToggle?: () => void
}) {
  const navigate = useNavigate()
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: isOverlay ? `week-job-overlay:${job.id}` : `week-job:${job.id}`,
    data: { jobId: job.id, job },
    disabled: isOverlay,
  })

  const translated = transform && !isDragging && !isOverlay
    ? `translate3d(${Math.round(transform.x)}px, ${Math.round(transform.y)}px, 0)`
    : undefined
  const vehicleSummary = weekJobVehicleSummary(job)
  const secondarySummary = weekJobSecondarySummary(job, customerName, assignedTechName)
  const keySummary = [
    job.key_type ? `Key: ${job.key_type}` : undefined,
    typeof job.key_quantity === 'number' ? `Qty ${job.key_quantity}` : undefined,
  ].filter(Boolean).join(' · ')
  const metaTags = [
    job.job_type || undefined,
    assignedTechName ? `Tech: ${assignedTechName}` : undefined,
    !compact && keySummary ? keySummary : undefined,
  ].filter(Boolean)
  const hoverTitle = [job.title, customerName, vehicleSummary, secondarySummary, job.job_address].filter(Boolean).join(' • ')

  return (
    <div
      ref={setNodeRef}
      {...(isOverlay ? {} : attributes)}
      {...(isOverlay ? {} : listeners)}
      data-week-job-chip
      className={`group flex items-stretch shrink-0 rounded-lg border overflow-hidden select-none transition-[box-shadow,transform,opacity] ${compact ? 'mb-1 last:mb-0' : 'max-w-[min(420px,96vw)]'}`}
      style={{
        borderColor: selected ? 'var(--ms-accent)' : 'var(--ms-border)',
        outline: selected ? '2px solid rgba(245,158,11,0.35)' : undefined,
        outlineOffset: 1,
        opacity: isDragging ? 0.38 : 1,
        transform: isOverlay ? 'scale(1.02)' : translated,
        boxShadow: isOverlay
          ? '0 18px 36px rgba(44,24,16,0.24), 0 6px 16px rgba(44,24,16,0.16)'
          : selected
            ? '0 0 0 2px rgba(245,158,11,0.18)'
            : '0 3px 10px rgba(44,24,16,0.06)',
        cursor: isOverlay ? 'grabbing' : 'grab',
        touchAction: 'none',
        backgroundColor: compact ? 'rgba(245, 158, 11, 0.08)' : 'var(--ms-surface)',
      }}
      title={isOverlay ? undefined : hoverTitle || 'Drag the whole booking card to reschedule'}
    >
      <div
        className="flex items-center justify-center px-1.5 shrink-0 self-stretch"
        style={{
          backgroundColor: isOverlay ? 'rgba(245, 158, 11, 0.2)' : compact ? 'rgba(141, 103, 37, 0.16)' : '#EDE6DC',
          color: '#5c4a32',
        }}
      >
        <GripVertical size={compact ? 12 : 14} aria-hidden />
      </div>

      <div className="min-w-0 flex-1 px-2.5 py-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="rounded-full px-1.5 py-0.5 text-[10px] font-mono font-semibold" style={{ backgroundColor: '#F8EBDD', color: 'var(--ms-accent)' }}>
                #{job.job_number}
              </span>
              {job.status && (
                <span className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: '#EEE6DA', color: 'var(--ms-text-mid)' }}>
                  {STATUS_LABELS[job.status] ?? job.status.replace(/_/g, ' ')}
                </span>
              )}
            </div>
            <p
              className={`${compact ? 'text-[11px]' : 'text-sm'} mt-1 font-semibold leading-tight`}
              style={{
                color: 'var(--ms-text)',
                display: '-webkit-box',
                WebkitBoxOrient: 'vertical',
                WebkitLineClamp: compact ? 2 : 2,
                overflow: 'hidden',
              }}
            >
              {job.title}
            </p>
          </div>
        </div>

        {customerName && (
          <p className="text-[11px] mt-1 font-medium" style={{ color: 'var(--ms-text)' }}>
            {customerName}
          </p>
        )}

        {vehicleSummary && (
          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
            <p className="text-[11px]" style={{ color: 'var(--ms-text-mid)' }}>
              {vehicleSummary}
            </p>
            {(() => {
              const complexity = parseAklComplexity(job.tech_notes)
              return complexity ? <AklComplexityPill complexity={complexity} /> : null
            })()}
          </div>
        )}

        {metaTags.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {metaTags.map((tag) => (
              <span
                key={tag}
                className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                style={{ backgroundColor: '#F7F1E8', color: 'var(--ms-text-mid)' }}
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {!compact && job.job_address && (
          <p className="text-[11px] mt-1.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>
            <span className="inline-flex items-center gap-1"><MapPin size={11} /> {job.job_address}</span>
          </p>
        )}

        {!isOverlay && (
          <div className="mt-2 flex items-center justify-end gap-1.5 border-t pt-2" style={{ borderColor: 'rgba(44,24,16,0.08)' }}>
            <button
              type="button"
              className={`rounded-md font-semibold touch-manipulation ${compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1 text-[11px]'}`}
              style={{ backgroundColor: '#F7F1E8', color: 'var(--ms-text)' }}
              onPointerDown={stopDragControlPropagation}
              onMouseDown={stopDragControlPropagation}
              onTouchStart={stopDragControlPropagation}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                navigate(`/auto-key/${job.id}`)
              }}
            >
              Open
            </button>
            {onMoveToggle && (
              <button
                type="button"
                className={`rounded-md font-semibold touch-manipulation ${compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1 text-[11px]'}`}
                style={{
                  backgroundColor: compact ? '#E8DCC8' : 'var(--ms-accent)',
                  color: compact ? '#3d2f20' : '#2C1810',
                }}
                onPointerDown={stopDragControlPropagation}
                onMouseDown={stopDragControlPropagation}
                onTouchStart={stopDragControlPropagation}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onMoveToggle()
                }}
              >
                Move
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function WeekUnscheduledDropZone({
  canTapPlace,
  onClick,
  children,
}: {
  canTapPlace: boolean
  onClick: (event: React.MouseEvent<HTMLDivElement>) => void
  children: ReactNode
}) {
  const { isOver, setNodeRef } = useDroppable({ id: WEEK_UNSCHEDULED_DROP_ID })

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[52px] p-2 rounded border flex flex-wrap gap-2 content-start transition-colors ${canTapPlace ? 'cursor-pointer' : ''}`}
      style={{
        backgroundColor: isOver ? '#F5EDE0' : 'var(--ms-bg)',
        borderColor: isOver ? 'var(--ms-accent)' : 'var(--ms-border)',
        borderStyle: 'dashed',
        boxShadow: isOver ? 'inset 0 0 0 1px rgba(245,158,11,0.18)' : undefined,
      }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

export function WeekDayHeaderDrop({
  dayStr,
  dayName,
  dayNum,
  isToday,
  canTapPlace,
  onClick,
}: {
  dayStr: string
  dayName: string
  dayNum: number
  isToday: boolean
  canTapPlace: boolean
  onClick: () => void
}) {
  const { isOver, setNodeRef } = useDroppable({ id: weekDayDropId(dayStr) })
  const baseBg = isToday ? 'rgba(245, 158, 11, 0.15)' : 'var(--ms-surface)'

  return (
    <div
      ref={setNodeRef}
      className={`text-center py-2 rounded-lg min-h-[56px] flex flex-col items-center justify-center transition-colors ${canTapPlace ? 'cursor-pointer' : ''}`}
      style={{
        backgroundColor: isOver ? 'rgba(245, 158, 11, 0.28)' : baseBg,
        border: `1px dashed ${isOver ? 'var(--ms-accent)' : 'var(--ms-border)'}`,
        boxShadow: isOver ? '0 0 0 2px rgba(245,158,11,0.18)' : undefined,
      }}
      title={canTapPlace ? 'Tap to place the selected job on this day' : 'Drag a booking card here to move it to this day (same clock time)'}
      onClick={onClick}
    >
      <p className="text-xs font-semibold" style={{ color: 'var(--ms-text-muted)' }}>{dayName}</p>
      <p className="text-sm font-bold" style={{ color: 'var(--ms-text)' }}>{dayNum}</p>
    </div>
  )
}

export function WeekHourDropCell({
  dropId,
  canTapPlace,
  onClick,
  children,
}: {
  dropId: string
  canTapPlace: boolean
  onClick: (event: React.MouseEvent<HTMLDivElement>) => void
  children: ReactNode
}) {
  const { isOver, setNodeRef } = useDroppable({ id: dropId })

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[44px] p-1 rounded border transition-colors ${canTapPlace ? 'cursor-pointer' : ''}`}
      style={{
        backgroundColor: isOver ? '#F5EDE0' : 'var(--ms-bg)',
        borderColor: isOver ? 'var(--ms-accent)' : 'var(--ms-border)',
        boxShadow: isOver ? 'inset 0 0 0 1px rgba(245,158,11,0.18)' : undefined,
      }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
