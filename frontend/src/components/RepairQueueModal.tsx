import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, ChevronRight, SkipForward, CheckCircle } from 'lucide-react'
import {
  listJobs, updateJobStatus,
  listShoeRepairJobs, updateShoeRepairJobStatus,
  type RepairJob, type ShoeRepairJob, type JobStatus,
} from '@/lib/api'
import { Spinner } from '@/components/ui'
import { STATUS_LABELS } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────────

interface QueueJob {
  id: string
  job_number: string
  title: string
  priority: string
  status: string
  created_at: string
  customer_name?: string | null
}

interface Props {
  mode: 'watch' | 'shoe'
  onClose: () => void
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 }

const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#e53e3e',
  high: '#dd6b20',
  normal: '#3182ce',
  low: '#718096',
}

const STATUS_NEXT: Record<string, string> = {
  awaiting_quote: 'awaiting_go_ahead',
  awaiting_go_ahead: 'go_ahead',
  go_ahead: 'working_on',
  working_on: 'completed',
  completed: 'awaiting_collection',
  awaiting_collection: 'collected',
}

const STATUS_STEP_NOTES: Record<string, string[]> = {
  awaiting_go_ahead: ['Called customer', 'Left voicemail', 'Sent SMS', 'Emailed customer'],
  go_ahead: ['Customer confirmed by phone', 'Customer confirmed by SMS', 'Customer came in'],
  working_on: ['Parts sourced', 'Started movement service', 'Battery replaced', 'Crystal replaced', 'Waiting on parts'],
  completed: ['Service complete', 'Pressure tested', 'Timekeeping checked', 'Ready for collection'],
  awaiting_collection: ['Customer notified', 'SMS sent', 'Called customer'],
  collected: ['Customer collected', 'Shipped to customer'],
}

// Terminal statuses excluded from queue
const EXCLUDE_STATUSES = new Set(['collected', 'no_go'])

const SWIPE_THRESHOLD = 80

// ── Helpers ────────────────────────────────────────────────────────────────────

function sortQueue(jobs: QueueJob[]): QueueJob[] {
  return [...jobs].sort((a, b) => {
    const pa = PRIORITY_ORDER[a.priority] ?? 99
    const pb = PRIORITY_ORDER[b.priority] ?? 99
    if (pa !== pb) return pa - pb
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })
}

function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function RepairQueueModal({ mode, onClose }: Props) {
  const qc = useQueryClient()

  // Queue ordering: initialised once from sorted data; skip pushes ID to end
  const [queueOrder, setQueueOrder] = useState<string[] | null>(null)
  // IDs of jobs whose status was successfully advanced this session
  const [done, setDone] = useState<Set<string>>(new Set())
  // Confirm-advance panel state
  const [confirmAdvance, setConfirmAdvance] = useState(false)
  const [selectedNote, setSelectedNote] = useState('')
  const [customNote, setCustomNote] = useState('')
  // Drag/swipe state
  const [dragX, setDragX] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const dragStartX = useRef<number | null>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  // ── Data fetching ──────────────────────────────────────────────────────────

  const watchQuery = useQuery({
    queryKey: ['repair-jobs', 'all'],
    queryFn: () => listJobs({ limit: 200 }).then(r => r.data),
    enabled: mode === 'watch',
    staleTime: 30_000,
  })

  const shoeQuery = useQuery({
    queryKey: ['shoe-repair-jobs'],
    queryFn: () => listShoeRepairJobs().then(r => r.data),
    enabled: mode === 'shoe',
    staleTime: 30_000,
  })

  const isLoading = mode === 'watch' ? watchQuery.isLoading : shoeQuery.isLoading

  const allJobs: QueueJob[] = mode === 'watch'
    ? ((watchQuery.data ?? []) as RepairJob[])
        .filter(j => !EXCLUDE_STATUSES.has(j.status))
        .map(j => ({ id: j.id, job_number: j.job_number, title: j.title, priority: j.priority, status: j.status, created_at: j.created_at, customer_name: j.customer_name }))
    : ((shoeQuery.data ?? []) as ShoeRepairJob[])
        .filter(j => !EXCLUDE_STATUSES.has(j.status))
        .map(j => ({ id: j.id, job_number: j.job_number, title: j.title, priority: j.priority, status: j.status, created_at: j.created_at, customer_name: undefined }))

  // Initialise queue order once data arrives
  useEffect(() => {
    if (allJobs.length > 0 && queueOrder === null) {
      setQueueOrder(sortQueue(allJobs).map(j => j.id))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allJobs.length, queueOrder])

  // Derive current job from queue order
  const jobMap = Object.fromEntries(allJobs.map(j => [j.id, j]))
  const visibleIds = (queueOrder ?? []).filter(id => !done.has(id) && jobMap[id])
  const currentId = visibleIds[0] ?? null
  const current = currentId ? jobMap[currentId] : null

  // ── Mutation ───────────────────────────────────────────────────────────────

  const advanceMutation = useMutation({
    mutationFn: (vars: { id: string; status: string; note?: string }) =>
      mode === 'watch'
        ? updateJobStatus(vars.id, vars.status as JobStatus, vars.note)
        : updateShoeRepairJobStatus(vars.id, vars.status, vars.note),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] })
      setDone(prev => new Set([...prev, vars.id]))
      resetConfirm()
    },
  })

  // ── Handlers ───────────────────────────────────────────────────────────────

  function resetConfirm() {
    setConfirmAdvance(false)
    setSelectedNote('')
    setCustomNote('')
    setDragX(0)
  }

  function handleAdvance() {
    if (!current) return
    const nextStatus = STATUS_NEXT[current.status]
    if (!nextStatus) return
    advanceMutation.mutate({
      id: current.id,
      status: nextStatus,
      note: selectedNote || customNote || undefined,
    })
  }

  function handleSkip() {
    if (!currentId) return
    setQueueOrder(prev => {
      if (!prev) return prev
      const rest = prev.filter(id => id !== currentId)
      return [...rest, currentId]
    })
    resetConfirm()
  }

  // ── Pointer / touch events ─────────────────────────────────────────────────

  function onPointerDown(e: React.PointerEvent) {
    if (confirmAdvance) return
    dragStartX.current = e.clientX
    setIsDragging(true)
    cardRef.current?.setPointerCapture(e.pointerId)
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!isDragging || dragStartX.current === null) return
    setDragX(e.clientX - dragStartX.current)
  }

  function onPointerUp() {
    if (!isDragging) return
    setIsDragging(false)
    dragStartX.current = null
    if (dragX > SWIPE_THRESHOLD) {
      setDragX(0)
      setConfirmAdvance(true)
    } else if (dragX < -SWIPE_THRESHOLD) {
      handleSkip()
    } else {
      setDragX(0)
    }
  }

  // ── Derived display values ─────────────────────────────────────────────────

  const rotation = Math.min(Math.max(dragX / 18, -12), 12)
  const advanceHint = dragX > SWIPE_THRESHOLD * 0.4
  const skipHint = dragX < -SWIPE_THRESHOLD * 0.4
  const nextStatus = current ? STATUS_NEXT[current.status] : null
  const noteChips = nextStatus ? (STATUS_STEP_NOTES[nextStatus] ?? []) : []

  // ── Render: loading ────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center"
        style={{ background: 'radial-gradient(1200px 600px at 50% -20%, #2d2455 0%, #151326 48%, #0c0c18 100%)' }}
      >
        <Spinner />
      </div>
    )
  }

  // ── Render: empty / complete ───────────────────────────────────────────────

  if (!current) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-6"
        style={{ background: 'radial-gradient(1200px 600px at 50% -20%, #2d2455 0%, #151326 48%, #0c0c18 100%)' }}
      >
        <div
          className="rounded-3xl p-8 text-center w-full max-w-sm"
          style={{
            background: 'linear-gradient(160deg, rgba(31,28,53,0.95) 0%, rgba(18,17,33,0.96) 100%)',
            border: '1px solid rgba(255,255,255,0.14)',
            boxShadow: '0 20px 50px rgba(0,0,0,0.38)',
          }}
        >
          <CheckCircle size={54} className="mx-auto mb-4" style={{ color: '#63d99d' }} />
          <h2 className="text-xl font-bold mb-2" style={{ color: '#F6F0E8' }}>Queue Clear</h2>
          <p className="text-sm mb-6" style={{ color: 'rgba(246,240,232,0.72)' }}>
            All {mode === 'watch' ? 'watch' : 'shoe'} repairs have been reviewed.
          </p>
          <button
            onClick={onClose}
            className="px-8 py-2.5 rounded-xl font-semibold"
            style={{ backgroundColor: '#C9A248', color: '#fff' }}
          >
            Done
          </button>
        </div>
      </div>
    )
  }

  const days = daysInShop(current.created_at)
  const totalQueued = (queueOrder ?? []).filter(id => !done.has(id) && jobMap[id]).length
  const doneCount = done.size
  const progressTotal = doneCount + totalQueued
  const progressPct = progressTotal > 0 ? Math.round((doneCount / progressTotal) * 100) : 0

  // ── Render: main ──────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: 'radial-gradient(1200px 600px at 50% -20%, #2d2455 0%, #151326 48%, #0c0c18 100%)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: '1px solid rgba(255,255,255,0.09)' }}>
        <div className="flex items-center gap-3">
          <div>
            <span className="text-white font-bold text-lg">{mode === 'watch' ? 'Watch' : 'Shoe'} Queue</span>
            <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.62)' }}>
              Swipe cards to triage or move jobs forward
            </p>
          </div>
          <span
            className="text-xs px-2.5 py-0.5 rounded-full"
            style={{ backgroundColor: 'rgba(201,162,72,0.16)', color: '#F3D79E', border: '1px solid rgba(201,162,72,0.38)' }}
          >
            {doneCount} done · {totalQueued} left
          </span>
        </div>
        <button onClick={onClose} className="p-2 rounded-full" style={{ color: 'rgba(255,255,255,0.65)' }}>
          <X size={20} />
        </button>
      </div>

      {/* Progress bar */}
      {progressTotal > 0 && (
        <div className="h-1.5" style={{ backgroundColor: 'rgba(255,255,255,0.09)' }}>
          <div
            className="h-full transition-all duration-300"
            style={{
              width: `${progressPct}%`,
              background: 'linear-gradient(90deg, #63d99d 0%, #58c78f 100%)',
              boxShadow: '0 0 10px rgba(99,217,157,0.45)',
            }}
          />
        </div>
      )}

      {/* Card area */}
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-6 relative overflow-hidden">

        {/* Skip label (drag left) */}
        {skipHint && !confirmAdvance && (
          <div
            className="absolute left-5 top-1/2 z-20 pointer-events-none"
            style={{ transform: 'translateY(-50%) rotate(-12deg)', opacity: Math.min(1, Math.abs(dragX) / SWIPE_THRESHOLD) }}
          >
            <span className="block px-4 py-2 rounded-xl font-black text-xl text-white tracking-wider" style={{ backgroundColor: '#d14040', border: '3px solid #fa8f8f' }}>
              SKIP
            </span>
          </div>
        )}

        {/* Advance label (drag right) */}
        {advanceHint && !confirmAdvance && (
          <div
            className="absolute right-5 top-1/2 z-20 pointer-events-none"
            style={{ transform: 'translateY(-50%) rotate(12deg)', opacity: Math.min(1, dragX / SWIPE_THRESHOLD) }}
          >
            <span className="block px-4 py-2 rounded-xl font-black text-xl text-white tracking-wider" style={{ backgroundColor: '#2f9862', border: '3px solid #79dfaa' }}>
              ADVANCE
            </span>
          </div>
        )}

        {/* ── Job card (swipeable) ── */}
        {!confirmAdvance && (
          <div
            ref={cardRef}
            className="w-full max-w-sm rounded-2xl shadow-2xl"
            style={{
              background: 'linear-gradient(160deg, rgba(31,28,53,0.95) 0%, rgba(18,17,33,0.96) 100%)',
              border: '1px solid rgba(255,255,255,0.14)',
              transform: `translateX(${dragX}px) rotate(${rotation}deg)`,
              transition: isDragging ? 'none' : 'transform 0.35s cubic-bezier(0.34,1.56,0.64,1)',
              touchAction: 'none',
              userSelect: 'none',
              cursor: isDragging ? 'grabbing' : 'grab',
              boxShadow: '0 22px 52px rgba(0,0,0,0.4)',
            }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {/* Priority colour bar */}
            <div
              className="h-2 rounded-t-2xl"
              style={{ background: `linear-gradient(90deg, ${PRIORITY_COLORS[current.priority] ?? '#718096'} 0%, rgba(255,255,255,0.45) 100%)` }}
            />

            <div className="p-5">
              {/* Job number + priority */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="text-3xl font-black tracking-tight" style={{ color: '#F6F0E8' }}>
                    {current.job_number}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: 'rgba(246,240,232,0.68)' }}>
                    {days === 0 ? 'Taken in today' : days === 1 ? '1 day in shop' : `${days} days in shop`}
                  </div>
                </div>
                <span
                  className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase text-white"
                  style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#718096' }}
                >
                  {current.priority}
                </span>
              </div>

              {/* Title */}
              <div className="text-lg font-semibold leading-snug mb-1" style={{ color: '#F6F0E8' }}>
                {current.title}
              </div>

              {/* Customer */}
              {current.customer_name && (
                <div className="text-sm mb-3" style={{ color: 'rgba(246,240,232,0.74)' }}>
                  {current.customer_name}
                </div>
              )}

              {/* Status → next status */}
              <div className="mt-4 flex items-center gap-2 flex-wrap">
                <span
                  className="text-xs px-2.5 py-1 rounded-full"
                  style={{ backgroundColor: 'rgba(255,255,255,0.1)', color: 'rgba(246,240,232,0.72)' }}
                >
                  {STATUS_LABELS[current.status] ?? current.status}
                </span>
                {nextStatus && (
                  <>
                    <ChevronRight size={13} style={{ color: 'rgba(255,255,255,0.3)' }} />
                    <span
                      className="text-xs px-2.5 py-1 rounded-full"
                      style={{ backgroundColor: 'rgba(104,211,145,0.12)', color: '#68d391' }}
                    >
                      {STATUS_LABELS[nextStatus] ?? nextStatus}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Advance confirm panel ── */}
        {confirmAdvance && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-bg-card)' }}>
            <div className="h-2 rounded-t-2xl" style={{ background: 'linear-gradient(90deg, #2f9862 0%, #79dfaa 100%)' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: '#F6F0E8' }}>
                {current.job_number} — {current.title}
              </div>
              <div className="text-sm mb-4" style={{ color: '#68d391' }}>
                Advance to: <strong>{STATUS_LABELS[nextStatus!] ?? nextStatus}</strong>
              </div>

              {noteChips.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'rgba(246,240,232,0.66)' }}>
                    Add a note (optional)
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {noteChips.map(chip => (
                      <button
                        key={chip}
                        onClick={() => { setSelectedNote(prev => prev === chip ? '' : chip); setCustomNote('') }}
                        className="px-3 py-1 rounded-full text-xs font-medium transition-all"
                        style={{
                          backgroundColor: selectedNote === chip ? 'var(--cafe-accent)' : 'rgba(255,255,255,0.07)',
                          color: selectedNote === chip ? '#fff' : 'var(--cafe-text-muted)',
                          border: `1px solid ${selectedNote === chip ? 'var(--cafe-accent)' : 'rgba(255,255,255,0.12)'}`,
                        }}
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <input
                type="text"
                placeholder="Or type a custom note…"
                value={customNote}
                onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }}
                className="w-full px-3 py-2 rounded-lg text-sm mb-4"
                style={{
                  backgroundColor: 'rgba(255,255,255,0.08)',
                  color: '#F6F0E8',
                  border: '1px solid rgba(255,255,255,0.16)',
                  outline: 'none',
                }}
              />

              <div className="flex gap-3">
                <button
                  onClick={resetConfirm}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ backgroundColor: 'rgba(255,255,255,0.09)', color: 'rgba(246,240,232,0.76)' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleAdvance}
                  disabled={advanceMutation.isPending}
                  className="flex-1 py-2.5 rounded-xl text-sm font-bold"
                  style={{ backgroundColor: '#38a169', color: '#fff', opacity: advanceMutation.isPending ? 0.65 : 1 }}
                >
                  {advanceMutation.isPending ? 'Saving…' : 'Confirm'}
                </button>
              </div>

              {advanceMutation.isError && (
                <p className="text-xs mt-2 text-center" style={{ color: '#fc8181' }}>
                  Failed to update — please try again.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Swipe hint */}
        {!confirmAdvance && (
          <div
            className="mt-8 px-4 py-2 rounded-full text-xs text-center select-none"
            style={{ backgroundColor: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.76)' }}
          >
            <span style={{ color: '#fa8f8f' }}>← swipe to skip</span>
            {'  ·  '}
            <span style={{ color: '#79dfaa' }}>swipe to advance →</span>
          </div>
        )}
      </div>

      {/* Bottom buttons */}
      {!confirmAdvance && (
        <div className="px-5 pb-8 pt-2 flex gap-4">
          <button
            onClick={handleSkip}
            className="flex-1 py-3.5 rounded-2xl font-semibold flex items-center justify-center gap-2 text-sm"
            style={{
              backgroundColor: 'rgba(209,64,64,0.18)',
              color: '#ffadad',
              border: '1px solid rgba(209,64,64,0.42)',
            }}
          >
            <SkipForward size={16} />
            Skip
          </button>
          <button
            onClick={() => setConfirmAdvance(true)}
            disabled={!nextStatus}
            className="py-3.5 rounded-2xl font-semibold flex items-center justify-center gap-2 text-sm"
            style={{
              flex: 2,
              backgroundColor: nextStatus ? 'rgba(47,152,98,0.2)' : 'rgba(255,255,255,0.05)',
              color: nextStatus ? '#79dfaa' : 'rgba(255,255,255,0.25)',
              border: `1px solid ${nextStatus ? 'rgba(121,223,170,0.45)' : 'rgba(255,255,255,0.08)'}`,
            }}
          >
            <ChevronRight size={16} />
            Advance Status
          </button>
        </div>
      )}
    </div>
  )
}
