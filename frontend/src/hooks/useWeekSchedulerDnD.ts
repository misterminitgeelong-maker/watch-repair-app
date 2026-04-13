import { useState } from 'react'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'

const WEEK_UNSCHEDULED_DROP_ID = 'week-unscheduled'
const WEEK_DAY_DROP_PREFIX = 'week-day:'
const WEEK_SLOT_DROP_PREFIX = 'week-slot:'

export function useWeekSchedulerDnD({
  onReschedule,
  scheduledForDay,
  scheduledForSlot,
}: {
  onReschedule: (jobId: string, scheduledAt: string | null) => void
  scheduledForDay: (jobId: string, dayYmd: string) => string
  scheduledForSlot: (dayYmd: string, hour: number) => string
}) {
  const [weekRelocateJobId, setWeekRelocateJobId] = useState<string | null>(null)
  const [activeWeekJobId, setActiveWeekJobId] = useState<string | null>(null)
  const [weekScheduleErr, setWeekScheduleErr] = useState<string | null>(null)

  const handleWeekDragStart = (event: DragStartEvent) => {
    const draggedJob = event.active.data.current?.job as { id?: string } | undefined
    const jobId = draggedJob?.id ?? (event.active.data.current?.jobId as string | undefined)
    if (!jobId) return
    setActiveWeekJobId(jobId)
    setWeekRelocateJobId(null)
    setWeekScheduleErr(null)
  }

  const handleWeekDragCancel = () => {
    setActiveWeekJobId(null)
  }

  const handleWeekDragEnd = (event: DragEndEvent) => {
    const draggedJob = event.active.data.current?.job as { id?: string } | undefined
    const jobId = draggedJob?.id ?? (event.active.data.current?.jobId as string | undefined)
    const overId = event.over?.id ? String(event.over.id) : ''
    setActiveWeekJobId(null)
    if (!jobId || !overId) return

    if (overId === WEEK_UNSCHEDULED_DROP_ID) {
      onReschedule(jobId, null)
      return
    }
    if (overId.startsWith(WEEK_DAY_DROP_PREFIX)) {
      const dayStr = overId.slice(WEEK_DAY_DROP_PREFIX.length)
      onReschedule(jobId, scheduledForDay(jobId, dayStr))
      return
    }
    if (overId.startsWith(WEEK_SLOT_DROP_PREFIX)) {
      const [dayStr, hourStr] = overId.slice(WEEK_SLOT_DROP_PREFIX.length).split(':')
      const hour = Number(hourStr)
      if (!dayStr || Number.isNaN(hour)) return
      onReschedule(jobId, scheduledForSlot(dayStr, hour))
    }
  }

  return {
    weekRelocateJobId,
    setWeekRelocateJobId,
    activeWeekJobId,
    weekScheduleErr,
    setWeekScheduleErr,
    handleWeekDragStart,
    handleWeekDragCancel,
    handleWeekDragEnd,
  }
}
