import { useState, useMemo, useRef, useCallback } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDndMonitor,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core'
import { useDroppable, useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { ChevronLeft, ChevronRight, GripVertical, AlertCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { RepairJob, TenantUser } from '@/lib/api'
import { Badge } from '@/components/ui'
import { PRIORITY_STYLES } from '@/lib/utils'

// ── Constants ────────────────────────────────────────────────────────────────

const DAY_START_HOUR = 8
const DAY_END_HOUR = 18
const SLOT_MIN = 15
const SLOT_H = 20            // px per 15-min slot
const SLOTS_PER_HOUR = 60 / SLOT_MIN
const TOTAL_SLOTS = (DAY_END_HOUR - DAY_START_HOUR) * SLOTS_PER_HOUR  // 40
const TIME_COL_W = 52        // px for time label column
const DEFAULT_DURATION_SLOTS = 4  // 1 hour default when placing

// ── Date / time helpers ──────────────────────────────────────────────────────

function toDateISO(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function addDays(date: Date, n: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + n)
  return d
}

function slotToLabel(slot: number): string {
  const totalMin = DAY_START_HOUR * 60 + slot * SLOT_MIN
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  const period = h < 12 ? 'am' : 'pm'
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h
  return m === 0 ? `${h12}${period}` : `${h12}:${String(m).padStart(2, '0')}`
}

function datetimeToSlot(iso: string): number {
  const dt = new Date(iso)
  return Math.round((dt.getHours() * 60 + dt.getMinutes() - DAY_START_HOUR * 60) / SLOT_MIN)
}

function slotToDatetime(dateISO: string, slot: number): string {
  const totalMin = DAY_START_HOUR * 60 + slot * SLOT_MIN
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return `${dateISO}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`
}

function isOnDate(isoDatetime: string, dateISO: string): boolean {
  return isoDatetime.startsWith(dateISO)
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface OptimisticOverride {
  scheduled_start: string
  scheduled_end: string
  assigned_user_id: string | null
}

interface ResourceCalendarProps {
  jobs: RepairJob[]
  users: TenantUser[]
  onReschedule: (
    jobId: string,
    start: string,
    end: string,
    resourceId: string | null
  ) => Promise<void>
}

// ── Droppable slot cell ──────────────────────────────────────────────────────

interface SlotCellProps {
  colId: string
  slotIdx: number
  previewSlot: number | null
  previewColId: string | null
  previewDuration: number
}

function SlotCell({ colId, slotIdx, previewSlot, previewColId, previewDuration }: SlotCellProps) {
  const id = `${colId}::${slotIdx}`
  const { setNodeRef, isOver } = useDroppable({ id })

  const isHourBoundary = slotIdx % SLOTS_PER_HOUR === 0
  const isHalfHour = slotIdx % 2 === 0

  // Is this cell within the drag preview range?
  const isPreview =
    previewSlot !== null &&
    previewColId === colId &&
    slotIdx >= previewSlot &&
    slotIdx < previewSlot + previewDuration

  return (
    <div
      ref={setNodeRef}
      style={{
        height: SLOT_H,
        borderTop: isHourBoundary
          ? '1px solid var(--cafe-border)'
          : isHalfHour
          ? '1px dashed var(--cafe-border)'
          : 'none',
        backgroundColor: isPreview
          ? 'rgba(183, 130, 50, 0.15)'
          : isOver
          ? 'rgba(183, 130, 50, 0.08)'
          : undefined,
        transition: 'background-color 80ms',
        outline: isPreview && slotIdx === previewSlot ? '2px solid var(--cafe-amber)' : undefined,
        outlineOffset: '-1px',
      }}
    />
  )
}

// ── Draggable event card ──────────────────────────────────────────────────────

interface EventCardProps {
  job: RepairJob
  override?: OptimisticOverride
  dateISO: string
  colId: string
  onResizeStart: (jobId: string, e: ReactPointerEvent<HTMLDivElement>) => void
  isOverlay?: boolean
}

function EventCard({ job, override, dateISO, colId, onResizeStart, isOverlay = false }: EventCardProps) {
  const startISO = override?.scheduled_start ?? job.scheduled_start
  const endISO = override?.scheduled_end ?? job.scheduled_end
  const assignedId = override !== undefined ? override.assigned_user_id : (job.assigned_user_id ?? null)

  if (!startISO || !endISO) return null

  const effectiveColId = assignedId ?? 'unassigned'
  if (!isOverlay && effectiveColId !== colId) return null
  if (!isOnDate(startISO, dateISO)) return null

  const startSlot = Math.max(0, datetimeToSlot(startISO))
  const endSlot = Math.min(TOTAL_SLOTS, datetimeToSlot(endISO))
  const durationSlots = Math.max(1, endSlot - startSlot)

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: job.id,
    data: { durationSlots, startSlot },
    disabled: isOverlay,
  })

  const priority = PRIORITY_STYLES[job.priority] ?? PRIORITY_STYLES.normal

  const cardStyle: CSSProperties = {
    position: isOverlay ? 'relative' : 'absolute',
    top: isOverlay ? undefined : startSlot * SLOT_H,
    height: isOverlay ? undefined : durationSlots * SLOT_H - 2,
    left: 2,
    right: 2,
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.35 : 1,
    zIndex: isDragging ? 1 : 2,
    touchAction: 'none',
    overflow: 'hidden',
  }

  const closed = job.status === 'collected' || job.status === 'no_go'

  return (
    <div
      ref={isOverlay ? undefined : setNodeRef}
      style={{
        ...cardStyle,
        borderRadius: 8,
        backgroundColor: closed ? '#F5F0EC' : 'var(--cafe-paper)',
        border: `1px solid ${isDragging || isOverlay ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
        boxShadow: isOverlay
          ? '0 6px 24px rgba(80,50,15,0.2)'
          : isDragging
          ? '0 4px 14px rgba(80,50,15,0.14)'
          : '0 1px 2px rgba(80,50,15,0.06)',
        cursor: closed ? 'default' : undefined,
        transform: isOverlay ? 'rotate(1deg)' : CSS.Translate.toString(transform),
      }}
    >
      {/* Drag handle — only triggers drag, not the Link */}
      {!isOverlay && !closed && (
        <div
          {...listeners}
          {...attributes}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            bottom: durationSlots > 1 ? 14 : 0,
            width: 18,
            display: 'flex',
            alignItems: 'flex-start',
            paddingTop: 3,
            paddingLeft: 1,
            cursor: 'grab',
            color: 'var(--cafe-text-muted)',
            touchAction: 'none',
            zIndex: 3,
          }}
          aria-label="Drag to reschedule"
        >
          <GripVertical size={12} />
        </div>
      )}

      {/* Card content */}
      <div style={{ paddingLeft: closed ? 6 : 20, paddingRight: 6, paddingTop: 3, paddingBottom: durationSlots > 1 ? 16 : 4 }}>
        <div className="flex items-center gap-1 mb-0.5">
          <span
            className="text-[9px] font-semibold px-1 py-0.5 rounded-full shrink-0"
            style={{ backgroundColor: priority.bg, color: priority.text }}
          >
            {priority.label}
          </span>
          {closed && (
            <span className="text-[9px]" style={{ color: 'var(--cafe-text-muted)' }}>
              {job.status === 'no_go' ? 'No Go' : 'Collected'}
            </span>
          )}
        </div>
        <Link
          to={`/jobs/${job.id}`}
          className="text-[11px] font-semibold hover:underline block leading-tight line-clamp-2"
          style={{ color: 'var(--cafe-amber)' }}
          draggable={false}
          onClick={e => { if (!isOverlay) e.stopPropagation() }}
        >
          {job.title}
        </Link>
        {durationSlots >= 3 && (
          <p className="text-[10px] mt-0.5 truncate" style={{ color: 'var(--cafe-text-muted)' }}>
            #{job.job_number}
          </p>
        )}
        {durationSlots >= 4 && (
          <div className="mt-1">
            <Badge status={job.status} />
          </div>
        )}
      </div>

      {/* Resize handle */}
      {!isOverlay && !closed && durationSlots >= 1 && (
        <div
          onPointerDown={e => onResizeStart(job.id, e)}
          style={{
            position: 'absolute',
            bottom: 0,
            left: 4,
            right: 4,
            height: 12,
            cursor: 'ns-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 4,
          }}
        >
          <div style={{
            width: 24,
            height: 3,
            borderRadius: 2,
            backgroundColor: 'var(--cafe-border)',
          }} />
        </div>
      )}
    </div>
  )
}

// ── Drag preview tracker (inside DndContext) ─────────────────────────────────

interface DragPreviewState {
  colId: string | null
  slotIdx: number | null
  durationSlots: number
}

function DragPreviewTracker({ onPreviewChange }: { onPreviewChange: (p: DragPreviewState) => void }) {
  useDndMonitor({
    onDragMove(event) {
      const overId = event.over?.id as string | undefined
      if (!overId || !overId.includes('::')) {
        onPreviewChange({ colId: null, slotIdx: null, durationSlots: 1 })
        return
      }
      const [colId, slotStr] = overId.split('::')
      const slotIdx = parseInt(slotStr, 10)
      const durationSlots = (event.active.data.current as { durationSlots?: number })?.durationSlots ?? 1
      onPreviewChange({ colId, slotIdx, durationSlots })
    },
    onDragEnd() {
      onPreviewChange({ colId: null, slotIdx: null, durationSlots: 1 })
    },
    onDragCancel() {
      onPreviewChange({ colId: null, slotIdx: null, durationSlots: 1 })
    },
  })
  return null
}

// ── Main ResourceCalendar ────────────────────────────────────────────────────

export default function ResourceCalendar({ jobs, users, onReschedule }: ResourceCalendarProps) {
  const [selectedDate, setSelectedDate] = useState<Date>(() => new Date())
  const dateISO = toDateISO(selectedDate)

  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [overrides, setOverrides] = useState<Map<string, OptimisticOverride>>(new Map())
  const [dragPreview, setDragPreview] = useState<DragPreviewState>({
    colId: null, slotIdx: null, durationSlots: 1,
  })
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'info' } | null>(null)

  // Resize state
  const resizeRef = useRef<{
    jobId: string
    startY: number
    origEndSlot: number
    dateISO: string
    colId: string
  } | null>(null)
  const [resizeSlot, setResizeSlot] = useState<number | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  )

  // Resources: techs first, then unassigned column
  const resources = useMemo(() => {
    const techUsers = users
      .filter(u => u.is_active && ['owner', 'manager', 'tech'].includes(u.role))
      .map(u => ({ id: u.id, label: u.full_name || u.email, role: u.role }))
    return [...techUsers, { id: 'unassigned', label: 'Unassigned', role: '' }]
  }, [users])

  // Effective job data (optimistic overrides applied)
  const effectiveJobs = useMemo(() => jobs.map(j => {
    const ov = overrides.get(j.id)
    if (!ov) return j
    return { ...j, scheduled_start: ov.scheduled_start, scheduled_end: ov.scheduled_end, assigned_user_id: ov.assigned_user_id ?? undefined }
  }), [jobs, overrides])

  // Jobs visible on this date
  const visibleJobs = useMemo(() =>
    effectiveJobs.filter(j => j.scheduled_start && isOnDate(j.scheduled_start, dateISO)),
    [effectiveJobs, dateISO]
  )

  const activeJob = useMemo(() =>
    activeJobId ? jobs.find(j => j.id === activeJobId) ?? null : null,
    [activeJobId, jobs]
  )

  function showToast(msg: string, type: 'error' | 'info' = 'error') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  // ── Drag handlers ─────────────────────────────────────────────────────────

  function handleDragStart(event: DragStartEvent) {
    setActiveJobId(event.active.id as string)
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveJobId(null)
    setDragPreview({ colId: null, slotIdx: null, durationSlots: 1 })

    const { over, active } = event
    if (!over) return

    const overId = over.id as string
    if (!overId.includes('::')) return

    const [colId, slotStr] = overId.split('::')
    const targetSlot = parseInt(slotStr, 10)
    const durationSlots = (active.data.current as { durationSlots?: number })?.durationSlots ?? DEFAULT_DURATION_SLOTS

    const endSlot = targetSlot + durationSlots

    if (targetSlot < 0 || endSlot > TOTAL_SLOTS) {
      showToast('Outside business hours', 'info')
      return
    }

    const newStart = slotToDatetime(dateISO, targetSlot)
    const newEnd = slotToDatetime(dateISO, endSlot)
    const newResourceId = colId === 'unassigned' ? null : colId

    const jobId = active.id as string
    const job = jobs.find(j => j.id === jobId)
    if (!job) return

    // Closed jobs can't be moved
    if (job.status === 'collected' || job.status === 'no_go') {
      showToast('Cannot reschedule a closed job', 'info')
      return
    }

    // Optimistic update
    const prevOverride = overrides.get(jobId)
    const newOverride: OptimisticOverride = {
      scheduled_start: newStart,
      scheduled_end: newEnd,
      assigned_user_id: newResourceId,
    }
    setOverrides(prev => new Map(prev).set(jobId, newOverride))

    try {
      await onReschedule(jobId, newStart, newEnd, newResourceId)
    } catch (err: unknown) {
      // Revert
      setOverrides(prev => {
        const next = new Map(prev)
        if (prevOverride) next.set(jobId, prevOverride)
        else next.delete(jobId)
        return next
      })
      const msg = err instanceof Error ? err.message : 'Failed to reschedule'
      showToast(msg)
    }
  }

  // ── Resize handlers ───────────────────────────────────────────────────────

  const handleResizeStart = useCallback((jobId: string, e: ReactPointerEvent<HTMLDivElement>) => {
    e.stopPropagation()
    e.preventDefault()
    const job = effectiveJobs.find(j => j.id === jobId)
    if (!job?.scheduled_end || !job.scheduled_start) return
    const origEndSlot = datetimeToSlot(job.scheduled_end)
    const colId = job.assigned_user_id ?? 'unassigned'
    resizeRef.current = { jobId, startY: e.clientY, origEndSlot, dateISO, colId }
    setResizeSlot(origEndSlot)

    const onMove = (ev: globalThis.PointerEvent) => {
      if (!resizeRef.current) return
      const deltaSlots = Math.round((ev.clientY - resizeRef.current.startY) / SLOT_H)
      const rawEnd = resizeRef.current.origEndSlot + deltaSlots
      const clampedEnd = Math.max(datetimeToSlot(job.scheduled_start!) + 1, Math.min(TOTAL_SLOTS, rawEnd))
      setResizeSlot(clampedEnd)
    }

    const onUp = async (ev: globalThis.PointerEvent) => {
      document.removeEventListener('pointermove', onMove)
      document.removeEventListener('pointerup', onUp)
      if (!resizeRef.current) return

      const deltaSlots = Math.round((ev.clientY - resizeRef.current.startY) / SLOT_H)
      const rawEnd = resizeRef.current.origEndSlot + deltaSlots
      const startSlot = datetimeToSlot(job.scheduled_start!)
      const endSlot = Math.max(startSlot + 1, Math.min(TOTAL_SLOTS, rawEnd))

      if (endSlot === resizeRef.current.origEndSlot) {
        resizeRef.current = null
        setResizeSlot(null)
        return
      }

      const newEnd = slotToDatetime(resizeRef.current.dateISO, endSlot)
      const jid = resizeRef.current.jobId
      const rid = resizeRef.current.colId === 'unassigned' ? null : resizeRef.current.colId

      // Optimistic
      const prevOv = overrides.get(jid)
      setOverrides(prev => new Map(prev).set(jid, {
        scheduled_start: job.scheduled_start!,
        scheduled_end: newEnd,
        assigned_user_id: rid,
      }))

      resizeRef.current = null
      setResizeSlot(null)

      try {
        await onReschedule(jid, job.scheduled_start!, newEnd, rid)
      } catch {
        setOverrides(prev => {
          const next = new Map(prev)
          if (prevOv) next.set(jid, prevOv)
          else next.delete(jid)
          return next
        })
        showToast('Failed to resize booking')
      }
    }

    document.addEventListener('pointermove', onMove)
    document.addEventListener('pointerup', onUp)
  }, [effectiveJobs, overrides, dateISO, onReschedule])

  // Build resize overlay overrides while actively resizing
  const displayJobs = useMemo(() => {
    if (resizeRef.current && resizeSlot !== null) {
      const { jobId, dateISO: rDateISO } = resizeRef.current
      const j = effectiveJobs.find(j => j.id === jobId)
      if (j?.scheduled_start) {
        return effectiveJobs.map(job =>
          job.id === jobId
            ? { ...job, scheduled_end: slotToDatetime(rDateISO, resizeSlot) }
            : job
        )
      }
    }
    return effectiveJobs
  }, [effectiveJobs, resizeSlot])

  // ── Render ────────────────────────────────────────────────────────────────

  const slotLabels = useMemo(() =>
    Array.from({ length: TOTAL_SLOTS }, (_, i) => slotToLabel(i)),
    []
  )

  const formattedDate = selectedDate.toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  })

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <DragPreviewTracker onPreviewChange={setDragPreview} />

      {/* Header: date nav + hint */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <button
          type="button"
          onClick={() => setSelectedDate(d => addDays(d, -1))}
          className="h-8 w-8 rounded-lg flex items-center justify-center"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}
          aria-label="Previous day"
        >
          <ChevronLeft size={15} />
        </button>

        <span className="text-sm font-semibold" style={{ color: 'var(--cafe-text)', minWidth: 240, textAlign: 'center' }}>
          {formattedDate}
        </span>

        <button
          type="button"
          onClick={() => setSelectedDate(d => addDays(d, 1))}
          className="h-8 w-8 rounded-lg flex items-center justify-center"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}
          aria-label="Next day"
        >
          <ChevronRight size={15} />
        </button>

        <button
          type="button"
          onClick={() => setSelectedDate(new Date())}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-mid)', backgroundColor: 'var(--cafe-surface)' }}
        >
          Today
        </button>

        <span className="text-xs ml-auto" style={{ color: 'var(--cafe-text-muted)' }}>
          Drag events to reschedule · Drag bottom edge to resize
        </span>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg mb-3 text-sm"
          style={{
            backgroundColor: toast.type === 'error' ? '#FEF2F2' : '#FEF9EC',
            border: `1px solid ${toast.type === 'error' ? '#FCA5A5' : '#FDE68A'}`,
            color: toast.type === 'error' ? '#991B1B' : '#92400E',
          }}
        >
          <AlertCircle size={15} />
          {toast.msg}
        </div>
      )}

      {/* Calendar grid */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: '1px solid var(--cafe-border)', backgroundColor: 'var(--cafe-surface)' }}
      >
        {/* Column headers */}
        <div
          className="flex"
          style={{ borderBottom: '2px solid var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}
        >
          {/* Time gutter header */}
          <div
            style={{ width: TIME_COL_W, flexShrink: 0, padding: '8px 6px', fontSize: 10, color: 'var(--cafe-text-muted)' }}
          />
          {/* Resource headers */}
          {resources.map(res => (
            <div
              key={res.id}
              className="flex-1 px-3 py-2.5 text-center"
              style={{
                borderLeft: '1px solid var(--cafe-border)',
                minWidth: 120,
              }}
            >
              <div className="text-xs font-semibold truncate" style={{ color: 'var(--cafe-text)' }}>
                {res.label}
              </div>
              {res.role && (
                <div className="text-[10px] capitalize mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>
                  {res.role}
                </div>
              )}
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--cafe-amber)' }}>
                {visibleJobs.filter(j =>
                  res.id === 'unassigned'
                    ? !j.assigned_user_id
                    : j.assigned_user_id === res.id
                ).length} jobs
              </div>
            </div>
          ))}
        </div>

        {/* Time grid (scrollable) */}
        <div
          className="overflow-y-auto"
          style={{ maxHeight: 'calc(100vh - 320px)', minHeight: 300 }}
        >
          <div className="flex">
            {/* Time labels */}
            <div style={{ width: TIME_COL_W, flexShrink: 0 }}>
              {slotLabels.map((label, i) => (
                <div
                  key={i}
                  style={{
                    height: SLOT_H,
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'flex-end',
                    paddingRight: 6,
                    paddingTop: 2,
                    fontSize: 10,
                    color: 'var(--cafe-text-muted)',
                    borderTop: i % SLOTS_PER_HOUR === 0
                      ? '1px solid var(--cafe-border)'
                      : i % 2 === 0
                      ? '1px dashed var(--cafe-border)'
                      : 'none',
                    borderRight: '1px solid var(--cafe-border)',
                    lineHeight: 1,
                  }}
                >
                  {i % SLOTS_PER_HOUR === 0 ? label : ''}
                </div>
              ))}
            </div>

            {/* Resource columns */}
            {resources.map(res => (
              <div
                key={res.id}
                className="flex-1 relative"
                style={{ borderLeft: '1px solid var(--cafe-border)', minWidth: 120 }}
              >
                {/* Droppable slot cells (background layer) */}
                {Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) => (
                  <SlotCell
                    key={slotIdx}
                    colId={res.id}
                    slotIdx={slotIdx}
                    previewSlot={dragPreview.slotIdx}
                    previewColId={dragPreview.colId}
                    previewDuration={dragPreview.durationSlots}
                  />
                ))}

                {/* Event cards (absolute positioned above cells) */}
                {displayJobs.map(job => (
                  <EventCard
                    key={job.id}
                    job={job}
                    override={overrides.get(job.id)}
                    dateISO={dateISO}
                    colId={res.id}
                    onResizeStart={handleResizeStart}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Drag overlay — shows card following cursor */}
      <DragOverlay>
        {activeJob && (
          <div style={{ width: 160 }}>
            <EventCard
              job={activeJob}
              dateISO={dateISO}
              colId=""
              onResizeStart={() => {}}
              isOverlay
            />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}
