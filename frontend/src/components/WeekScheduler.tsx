import { useState, useMemo } from 'react'
import type { CSSProperties } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  defaultDropAnimationSideEffects,
  type DragStartEvent,
  type DragEndEvent,
  type DropAnimation,
} from '@dnd-kit/core'
import { useDroppable, useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { ChevronLeft, ChevronRight, GripVertical, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { RepairJob } from '@/lib/api'
import { Badge } from '@/components/ui'

// ── Date helpers ──────────────────────────────────────────────────────────────

function startOfWeek(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
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

function formatDayLabel(date: Date): { weekday: string; date: string } {
  return {
    weekday: date.toLocaleDateString('en-US', { weekday: 'short' }),
    date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }
}

function isToday(date: Date): boolean {
  return toISODate(date) === toISODate(new Date())
}

// ── Priority helpers ──────────────────────────────────────────────────────────

const PRIORITY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  low:    { bg: '#EEEBE5', text: '#7A6A5A', label: 'Low' },
  normal: { bg: '#E8EEF8', text: '#3A508B', label: 'Normal' },
  high:   { bg: '#FEF0DC', text: '#9B6820', label: 'High' },
  urgent: { bg: '#F5E8E8', text: '#8B3A3A', label: 'Urgent' },
}

// ── Job card (draggable) ──────────────────────────────────────────────────────

function JobCard({ job, isOverlay = false }: { job: RepairJob; isOverlay?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: job.id })

  const priority = PRIORITY_STYLES[job.priority] ?? PRIORITY_STYLES.normal

  const cardStyle: CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : 1,
    touchAction: 'none',
  }

  const inner = (
    <div
      className="rounded-xl mb-2 overflow-hidden select-none"
      style={{
        backgroundColor: 'var(--cafe-paper)',
        border: `1px solid ${isDragging || isOverlay ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
        boxShadow: isOverlay
          ? '0 8px 28px rgba(80,50,15,0.18)'
          : isDragging
          ? '0 4px 14px rgba(80,50,15,0.14)'
          : '0 1px 3px rgba(80,50,15,0.06)',
        transform: isOverlay ? 'rotate(1.5deg)' : undefined,
      }}
    >
      {/* Card header: job# + priority */}
      <div
        className="flex items-center justify-between px-3 pt-2.5 pb-1"
        style={{ borderBottom: '1px solid var(--cafe-border)' }}
      >
        <span className="text-[11px] font-semibold tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
          #{job.job_number}
        </span>
        <span
          className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
          style={{ backgroundColor: priority.bg, color: priority.text }}
        >
          {priority.label}
        </span>
      </div>

      {/* Card body: title + drag handle */}
      <div className="flex items-start gap-1 px-3 py-2">
        <div className="flex-1 min-w-0">
          <Link
            to={`/jobs/${job.id}`}
            className="text-xs font-semibold leading-snug hover:underline line-clamp-2 flex items-start gap-1"
            style={{ color: 'var(--cafe-amber)' }}
            draggable={false}
          >
            {job.title}
            {!isOverlay && <ExternalLink size={10} className="mt-0.5 shrink-0 opacity-50" />}
          </Link>
        </div>
        {/* Drag handle – only active element that triggers drag */}
        {!isOverlay && (
          <div
            {...listeners}
            {...attributes}
            className="shrink-0 flex items-center justify-center rounded p-0.5 cursor-grab active:cursor-grabbing mt-0.5"
            style={{ color: 'var(--cafe-text-muted)', touchAction: 'none' }}
            aria-label="Drag to reschedule"
          >
            <GripVertical size={13} />
          </div>
        )}
      </div>

      {/* Card footer: status badge */}
      <div className="px-3 pb-2.5">
        <Badge status={job.status} />
      </div>
    </div>
  )

  if (isOverlay) return inner

  return (
    <div ref={setNodeRef} style={cardStyle}>
      {inner}
    </div>
  )
}

// ── Drop animation ────────────────────────────────────────────────────────────

const dropAnimation: DropAnimation = {
  sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.4' } } }),
}

// ── Droppable day column ──────────────────────────────────────────────────────

interface DayColumnProps {
  columnId: string
  weekday: string
  date: string
  today: boolean
  jobs: RepairJob[]
}

function DayColumn({ columnId, weekday, date, today, jobs }: DayColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: columnId })

  return (
    <div className="flex flex-col" style={{ flex: '1 1 0', minWidth: 110 }}>
      {/* Column header */}
      <div
        className="rounded-t-xl px-2 py-2 text-center mb-0"
        style={{
          backgroundColor: today ? 'var(--cafe-amber)' : 'var(--cafe-bg)',
          borderTop: `1px solid ${today ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
          borderLeft: `1px solid ${today ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
          borderRight: `1px solid ${today ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
        }}
      >
        <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: today ? 'rgba(255,255,255,0.8)' : 'var(--cafe-text-muted)' }}>
          {weekday}
        </p>
        <p className="text-sm font-semibold leading-tight mt-0.5" style={{ color: today ? '#fff' : 'var(--cafe-text)' }}>
          {date}
        </p>
        {jobs.length > 0 && (
          <span
            className="inline-block mt-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
            style={{ backgroundColor: today ? 'rgba(255,255,255,0.2)' : '#EEE6DA', color: today ? '#fff' : 'var(--cafe-text-mid)' }}
          >
            {jobs.length}
          </span>
        )}
      </div>

      {/* Drop zone body */}
      <div
        ref={setNodeRef}
        className="flex-1 rounded-b-xl p-2 transition-all duration-150 min-h-[140px]"
        style={{
          backgroundColor: isOver ? '#FDF5E8' : 'var(--cafe-surface)',
          border: `1px solid ${isOver ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
          borderTop: isOver ? `1px solid var(--cafe-amber)` : 'none',
          outline: isOver ? '2px solid var(--cafe-amber)' : 'none',
          outlineOffset: '-2px',
        }}
      >
        {jobs.length === 0 && (
          <p
            className="text-[10px] italic text-center mt-6 opacity-60"
            style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}
          >
            {isOver ? '↓ Drop here' : 'Empty'}
          </p>
        )}
        {jobs.map(j => <JobCard key={j.id} job={j} />)}
      </div>
    </div>
  )
}

// ── Unscheduled sidebar ───────────────────────────────────────────────────────

function UnscheduledColumn({ jobs }: { jobs: RepairJob[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: 'unscheduled' })

  return (
    <div className="flex flex-col" style={{ width: 180, flexShrink: 0 }}>
      <div
        className="rounded-t-xl px-3 py-2.5"
        style={{
          backgroundColor: 'var(--cafe-bg)',
          borderTop: '1px solid var(--cafe-border)',
          borderLeft: '1px solid var(--cafe-border)',
          borderRight: '1px solid var(--cafe-border)',
        }}
      >
        <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--cafe-text-muted)' }}>
          Unscheduled
        </p>
        <p className="text-sm font-semibold mt-0.5" style={{ color: 'var(--cafe-text)' }}>
          {jobs.length} job{jobs.length !== 1 ? 's' : ''}
        </p>
      </div>
      <div
        ref={setNodeRef}
        className="flex-1 rounded-b-xl p-2 overflow-y-auto transition-all duration-150"
        style={{
          backgroundColor: isOver ? '#FDF5E8' : 'var(--cafe-surface)',
          border: `1px solid ${isOver ? 'var(--cafe-amber)' : 'var(--cafe-border)'}`,
          borderTop: isOver ? `1px solid var(--cafe-amber)` : 'none',
          outline: isOver ? '2px solid var(--cafe-amber)' : 'none',
          outlineOffset: '-2px',
          maxHeight: 'calc(100vh - 280px)',
        }}
      >
        {jobs.length === 0 ? (
          <p
            className="text-[10px] italic text-center mt-6 opacity-60"
            style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}
          >
            All scheduled ✓
          </p>
        ) : (
          jobs.map(j => <JobCard key={j.id} job={j} />)
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
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
  )

  const days = useMemo(() =>
    Array.from({ length: 7 }, (_v, i) => addDays(weekStart, i)),
    [weekStart]
  )

  const activeJobs = useMemo(() =>
    jobs.filter(j => j.status !== 'collected' && j.status !== 'no_go'),
    [jobs]
  )

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
    setActiveJob(activeJobs.find(j => j.id === event.active.id) ?? null)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveJob(null)
    const { over, active } = event
    if (!over) return
    const targetId = over.id as string
    const newDate = targetId === 'unscheduled' ? null : targetId
    const job = activeJobs.find(j => j.id === active.id)
    if (!job) return
    if (newDate === (job.collection_date ?? null)) return
    onUpdateCollectionDate(job.id, newDate)
  }

  function prevWeek() { setWeekStart(d => addDays(d, -7)) }
  function nextWeek() { setWeekStart(d => addDays(d, 7)) }
  function goToday()  { setWeekStart(startOfWeek(new Date())) }

  const weekLabel = `${days[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${days[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      {/* Week navigation */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          type="button"
          onClick={prevWeek}
          className="h-8 w-8 rounded-lg flex items-center justify-center transition-colors"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)', backgroundColor: 'var(--cafe-surface)' }}
          aria-label="Previous week"
        >
          <ChevronLeft size={15} />
        </button>
        <span
          className="text-sm font-semibold px-3"
          style={{ color: 'var(--cafe-text)', minWidth: 210, textAlign: 'center' }}
        >
          {weekLabel}
        </span>
        <button
          type="button"
          onClick={nextWeek}
          className="h-8 w-8 rounded-lg flex items-center justify-center transition-colors"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-muted)', backgroundColor: 'var(--cafe-surface)' }}
          aria-label="Next week"
        >
          <ChevronRight size={15} />
        </button>
        <button
          type="button"
          onClick={goToday}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ml-1"
          style={{ border: '1px solid var(--cafe-border)', color: 'var(--cafe-text-mid)', backgroundColor: 'var(--cafe-surface)' }}
        >
          Today
        </button>
        <p className="text-xs ml-auto" style={{ color: 'var(--cafe-text-muted)' }}>
          Grab <GripVertical size={11} className="inline -mt-0.5" /> to reschedule
        </p>
      </div>

      {/* Grid */}
      <div className="flex gap-2 items-start overflow-x-auto pb-4">
        {days.map((day, i) => {
          const iso = weekDayISOs[i]
          const { weekday, date } = formatDayLabel(day)
          return (
            <DayColumn
              key={iso}
              columnId={iso}
              weekday={weekday}
              date={date}
              today={isToday(day)}
              jobs={jobsByDate.get(iso) ?? []}
            />
          )
        })}
        <UnscheduledColumn jobs={unscheduledJobs} />
      </div>

      {/* Drag overlay */}
      <DragOverlay dropAnimation={dropAnimation}>
        {activeJob ? <JobCard job={activeJob} isOverlay /> : null}
      </DragOverlay>
    </DndContext>
  )
}
