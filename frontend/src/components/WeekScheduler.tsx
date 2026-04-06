import { useState, useMemo } from 'react'
import type { CSSProperties } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core'
import { useDroppable, useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { RepairJob } from '@/lib/api'
import { Badge } from '@/components/ui'

// ── Date helpers ──────────────────────────────────────────────────────────────

function startOfWeek(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay() // 0=Sun … 6=Sat
  const diff = day === 0 ? -6 : 1 - day // shift to Monday
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

function addDays(date: Date, n: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + n)
  return d
}

function toISODate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function formatDayLabel(date: Date): string {
  return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

function isToday(date: Date): boolean {
  const today = new Date()
  return toISODate(date) === toISODate(today)
}

// ── Draggable job card ────────────────────────────────────────────────────────

interface DraggableJobCardProps {
  job: RepairJob
}

function DraggableJobCard({ job }: DraggableJobCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: job.id })
  const style: CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.35 : 1,
    cursor: 'grab',
  }

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className="rounded-lg px-3 py-2.5 mb-2 select-none transition-shadow"
      style={{
        ...style,
        backgroundColor: 'var(--cafe-paper)',
        border: '1px solid var(--cafe-border)',
        boxShadow: isDragging ? '0 4px 12px rgba(0,0,0,0.15)' : '0 1px 3px rgba(0,0,0,0.06)',
      }}
    >
      <Link
        to={`/jobs/${job.id}`}
        className="text-xs font-semibold hover:underline block truncate"
        style={{ color: 'var(--cafe-amber)' }}
        // Prevent link navigation while dragging
        onClick={e => { if (isDragging) e.preventDefault() }}
        draggable={false}
      >
        {job.title}
      </Link>
      <p className="text-[11px] mt-0.5 truncate" style={{ color: 'var(--cafe-text-muted)' }}>
        #{job.job_number}
      </p>
      <div className="mt-1.5">
        <Badge status={job.status} />
      </div>
    </div>
  )
}

// Static (non-draggable) overlay card shown during drag
function JobCardOverlay({ job }: { job: RepairJob }) {
  return (
    <div
      className="rounded-lg px-3 py-2.5 w-44 rotate-2"
      style={{
        backgroundColor: 'var(--cafe-paper)',
        border: '1px solid var(--cafe-amber)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
        cursor: 'grabbing',
      }}
    >
      <p className="text-xs font-semibold truncate" style={{ color: 'var(--cafe-amber)' }}>{job.title}</p>
      <p className="text-[11px] mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>#{job.job_number}</p>
      <div className="mt-1.5"><Badge status={job.status} /></div>
    </div>
  )
}

// ── Droppable day column ──────────────────────────────────────────────────────

interface DayColumnProps {
  columnId: string
  label: string
  isToday: boolean
  jobs: RepairJob[]
}

function DayColumn({ columnId, label, isToday: today, jobs }: DayColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: columnId })

  return (
    <div className="flex flex-col min-w-0" style={{ flex: '1 1 0' }}>
      <div
        className="px-2 py-2 text-center text-xs font-semibold rounded-t-lg mb-1"
        style={{
          backgroundColor: today ? 'var(--cafe-amber)' : 'var(--cafe-bg)',
          color: today ? '#fff' : 'var(--cafe-text-muted)',
          border: '1px solid var(--cafe-border)',
          borderBottom: 'none',
        }}
      >
        {label}
      </div>
      <div
        ref={setNodeRef}
        className="flex-1 rounded-b-lg p-2 transition-colors min-h-[120px]"
        style={{
          backgroundColor: isOver ? '#FDF5E8' : 'var(--cafe-surface)',
          border: `1px solid ${isOver ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
        }}
      >
        {jobs.length === 0 ? (
          <p
            className="text-[11px] italic text-center mt-4"
            style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}
          >
            Drop here
          </p>
        ) : (
          jobs.map(j => <DraggableJobCard key={j.id} job={j} />)
        )}
      </div>
    </div>
  )
}

// ── Unscheduled column ────────────────────────────────────────────────────────

interface UnscheduledColumnProps {
  jobs: RepairJob[]
}

function UnscheduledColumn({ jobs }: UnscheduledColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: 'unscheduled' })

  return (
    <div className="flex flex-col" style={{ width: 176, flexShrink: 0 }}>
      <div
        className="px-2 py-2 text-center text-xs font-semibold rounded-t-lg mb-1"
        style={{
          backgroundColor: 'var(--cafe-bg)',
          color: 'var(--cafe-text-muted)',
          border: '1px solid var(--cafe-border)',
          borderBottom: 'none',
        }}
      >
        Unscheduled ({jobs.length})
      </div>
      <div
        ref={setNodeRef}
        className="flex-1 rounded-b-lg p-2 overflow-y-auto transition-colors"
        style={{
          backgroundColor: isOver ? '#FDF5E8' : 'var(--cafe-surface)',
          border: `1px solid ${isOver ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
          maxHeight: 'calc(100vh - 260px)',
        }}
      >
        {jobs.length === 0 ? (
          <p
            className="text-[11px] italic text-center mt-4"
            style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}
          >
            All jobs scheduled
          </p>
        ) : (
          jobs.map(j => <DraggableJobCard key={j.id} job={j} />)
        )}
      </div>
    </div>
  )
}

// ── Main WeekScheduler ────────────────────────────────────────────────────────

interface WeekSchedulerProps {
  jobs: RepairJob[]
  onUpdateCollectionDate: (jobId: string, date: string | null) => void
}

export default function WeekScheduler({ jobs, onUpdateCollectionDate }: WeekSchedulerProps) {
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeek(new Date()))
  const [activeJob, setActiveJob] = useState<RepairJob | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  // Build array of 7 days for the current week
  const days = useMemo(() =>
    Array.from({ length: 7 }, (_v, i) => addDays(weekStart, i)),
    [weekStart]
  )

  // Active (non-closed) jobs only – exclude collected/no_go for the scheduler
  const activeJobs = useMemo(() =>
    jobs.filter(j => j.status !== 'collected' && j.status !== 'no_go'),
    [jobs]
  )

  // Build maps: dateISO → jobs[]
  const weekDayISOs = useMemo(() => days.map(toISODate), [days])
  const weekStart_ISO = weekDayISOs[0]
  const weekEnd_ISO = weekDayISOs[6]

  const jobsByDate = useMemo(() => {
    const map = new Map<string, RepairJob[]>()
    for (const iso of weekDayISOs) map.set(iso, [])
    for (const job of activeJobs) {
      const cd = job.collection_date
      if (cd && cd >= weekStart_ISO && cd <= weekEnd_ISO) {
        map.get(cd)?.push(job)
      }
    }
    return map
  }, [activeJobs, weekDayISOs, weekStart_ISO, weekEnd_ISO])

  const unscheduledJobs = useMemo(() =>
    activeJobs.filter(j => {
      const cd = j.collection_date
      return !cd || cd < weekStart_ISO || cd > weekEnd_ISO
    }),
    [activeJobs, weekStart_ISO, weekEnd_ISO]
  )

  function handleDragStart(event: DragStartEvent) {
    const job = activeJobs.find(j => j.id === event.active.id)
    setActiveJob(job ?? null)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveJob(null)
    const { over, active } = event
    if (!over) return

    const targetId = over.id as string
    const newDate = targetId === 'unscheduled' ? null : targetId
    const job = activeJobs.find(j => j.id === active.id)
    if (!job) return

    const currentDate = job.collection_date ?? null
    if (newDate === currentDate) return

    onUpdateCollectionDate(job.id, newDate)
  }

  function prevWeek() { setWeekStart(d => addDays(d, -7)) }
  function nextWeek() { setWeekStart(d => addDays(d, 7)) }
  function goToday()  { setWeekStart(startOfWeek(new Date())) }

  const weekLabel = `${days[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${days[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      {/* Week navigation */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <button
          type="button"
          onClick={prevWeek}
          className="h-8 w-8 rounded-lg flex items-center justify-center transition-colors"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}
          aria-label="Previous week"
        >
          <ChevronLeft size={15} />
        </button>
        <span className="text-sm font-semibold" style={{ color: 'var(--cafe-text)', minWidth: 200, textAlign: 'center' }}>
          {weekLabel}
        </span>
        <button
          type="button"
          onClick={nextWeek}
          className="h-8 w-8 rounded-lg flex items-center justify-center transition-colors"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)' }}
          aria-label="Next week"
        >
          <ChevronRight size={15} />
        </button>
        <button
          type="button"
          onClick={goToday}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-mid)', backgroundColor: 'var(--cafe-surface)' }}
        >
          Today
        </button>
        <span className="text-xs ml-auto" style={{ color: 'var(--cafe-text-muted)' }}>
          Drag jobs between days to reschedule
        </span>
      </div>

      {/* Grid: 7 day columns + unscheduled sidebar */}
      <div className="flex gap-3 items-start overflow-x-auto pb-4">
        {/* Day columns */}
        <div className="flex gap-2 flex-1 min-w-0" style={{ minWidth: 0 }}>
          {days.map((day, i) => {
            const iso = weekDayISOs[i]
            return (
              <DayColumn
                key={iso}
                columnId={iso}
                label={formatDayLabel(day)}
                isToday={isToday(day)}
                jobs={jobsByDate.get(iso) ?? []}
              />
            )
          })}
        </div>

        {/* Unscheduled sidebar */}
        <UnscheduledColumn jobs={unscheduledJobs} />
      </div>

      {/* Drag overlay */}
      <DragOverlay dropAnimation={null}>
        {activeJob ? <JobCardOverlay job={activeJob} /> : null}
      </DragOverlay>
    </DndContext>
  )
}
