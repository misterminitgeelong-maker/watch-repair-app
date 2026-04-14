import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, ChevronRight, SkipForward, CheckCircle, StickyNote, Wrench } from 'lucide-react'
import {
  listJobs, updateJobStatus, addJobNote,
  listShoeRepairJobs, updateShoeRepairJobStatus, addShoeJobNote,
  type RepairJob, type ShoeRepairJob, type JobStatus,
} from '@/lib/api'
import { Spinner } from '@/components/ui'
import { STATUS_LABELS } from '@/lib/utils'

// ── Types ─────────────────────────────────────────────────────────────────────

interface QueueJob {
  id: string
  job_number: string
  title: string
  priority: string
  status: string
  created_at: string
  collection_date?: string
  customer_name?: string | null
  description?: string
  items?: string[]       // shoe item names
  quote_status?: string
  type: 'watch' | 'shoe'
}

interface Props {
  mode: 'watch' | 'shoe'
  onClose: () => void
}

type CardState = 'view' | 'advance' | 'note'

// ── Constants ──────────────────────────────────────────────────────────────────

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

// Note chips shown when *advancing* to a status
const ADVANCE_NOTE_CHIPS: Record<string, string[]> = {
  awaiting_go_ahead: ['Called customer', 'Left voicemail', 'Sent SMS', 'Emailed customer'],
  go_ahead: ['Confirmed by phone', 'Confirmed by SMS', 'Customer came in'],
  working_on: ['Parts sourced', 'Started service', 'Battery replaced', 'Crystal replaced'],
  completed: ['Service complete', 'Pressure tested', 'Timekeeping checked'],
  awaiting_collection: ['Customer notified', 'SMS sent', 'Called customer'],
  collected: ['Customer collected', 'Shipped to customer'],
}

// Note chips shown when adding a note WITHOUT advancing
const STATUS_NOTE_CHIPS: Record<string, string[]> = {
  awaiting_quote: ['Needs parts assessment', 'Complex movement', 'Awaiting supplier quote', 'Rush job'],
  awaiting_go_ahead: ['Called — no answer', 'SMS sent', 'Quote expires soon', 'Customer reconsidering'],
  go_ahead: ['Parts ordered', 'Sourcing parts', 'Waiting on delivery'],
  working_on: ['Waiting on parts', 'Movement stripped', 'Parts arrived', 'Extra time needed', 'Testing in progress'],
  completed: ['Invoice ready', 'Tested and passed', 'Waiting for packaging'],
  awaiting_collection: ['Reminder sent', 'Customer unavailable', 'Left message'],
}

// Recommended action per status
const RECOMMENDED_ACTION: Record<string, string> = {
  awaiting_quote: 'Write up a quote',
  awaiting_go_ahead: 'Waiting on customer approval',
  go_ahead: 'Ready to start — begin work',
  working_on: 'In progress — continue work',
  completed: 'Notify customer for collection',
  awaiting_collection: 'Waiting at counter for pickup',
}

const EXCLUDE_STATUSES = new Set(['collected', 'no_go'])
const SWIPE_THRESHOLD = 80

// ── Helpers ────────────────────────────────────────────────────────────────────

function getCollectionUrgency(collectionDate?: string): 0 | 1 | 2 {
  if (!collectionDate) return 2
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1)
  const d = new Date(collectionDate)
  if (d <= today) return 0
  if (d <= tomorrow) return 1
  return 2
}

function sortQueue(jobs: QueueJob[]): QueueJob[] {
  return [...jobs].sort((a, b) => {
    const cu = getCollectionUrgency(a.collection_date) - getCollectionUrgency(b.collection_date)
    if (cu !== 0) return cu
    const pu = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99)
    if (pu !== 0) return pu
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })
}

function daysInShop(createdAt: string): number {
  return Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
}

function loadClaimed(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem('msp_queue_claimed') ?? '[]')) }
  catch { return new Set() }
}
function saveClaimed(s: Set<string>) {
  localStorage.setItem('msp_queue_claimed', JSON.stringify([...s]))
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function RepairQueueModal({ mode, onClose }: Props) {
  const qc = useQueryClient()

  const [queueOrder, setQueueOrder] = useState<string[] | null>(null)
  const [done, setDone] = useState<Set<string>>(new Set())
  const [claimed, setClaimed] = useState<Set<string>>(loadClaimed)
  const [cardState, setCardState] = useState<CardState>('view')
  const [selectedNote, setSelectedNote] = useState('')
  const [customNote, setCustomNote] = useState('')
  const [dragX, setDragX] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const dragStartX = useRef<number | null>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  // ── Data ──────────────────────────────────────────────────────────────────

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
        .map(j => ({
          id: j.id, job_number: j.job_number, title: j.title,
          priority: j.priority, status: j.status, created_at: j.created_at,
          collection_date: j.collection_date, customer_name: j.customer_name,
          description: j.description, type: 'watch' as const,
        }))
    : ((shoeQuery.data ?? []) as ShoeRepairJob[])
        .filter(j => !EXCLUDE_STATUSES.has(j.status))
        .map(j => ({
          id: j.id, job_number: j.job_number, title: j.title,
          priority: j.priority, status: j.status, created_at: j.created_at,
          collection_date: j.collection_date, customer_name: undefined,
          description: j.description,
          items: j.items?.map(i => i.item_name).filter(Boolean),
          quote_status: j.quote_status,
          type: 'shoe' as const,
        }))

  useEffect(() => {
    if (allJobs.length > 0 && queueOrder === null) {
      setQueueOrder(sortQueue(allJobs).map(j => j.id))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allJobs.length, queueOrder])

  const jobMap = Object.fromEntries(allJobs.map(j => [j.id, j]))
  const visibleIds = (queueOrder ?? []).filter(id => !done.has(id) && jobMap[id])
  const currentId = visibleIds[0] ?? null
  const current = currentId ? jobMap[currentId] : null
  const remaining = visibleIds.length
  const doneCount = done.size
  const isClaimed = currentId ? claimed.has(currentId) : false

  // ── Mutations ──────────────────────────────────────────────────────────────

  const advanceMutation = useMutation({
    mutationFn: (vars: { id: string; status: string; note?: string }) =>
      mode === 'watch'
        ? updateJobStatus(vars.id, vars.status as JobStatus, vars.note)
        : updateShoeRepairJobStatus(vars.id, vars.status, vars.note),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] })
      // Auto-release claim when advanced
      if (claimed.has(vars.id)) {
        setClaimed(prev => { const n = new Set(prev); n.delete(vars.id); saveClaimed(n); return n })
      }
      setDone(prev => new Set([...prev, vars.id]))
      resetPanel()
    },
  })

  const noteMutation = useMutation({
    mutationFn: (vars: { id: string; note: string }) =>
      mode === 'watch' ? addJobNote(vars.id, vars.note) : addShoeJobNote(vars.id, vars.note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] })
      resetPanel()
    },
  })

  // ── Handlers ──────────────────────────────────────────────────────────────

  function resetPanel() {
    setCardState('view')
    setSelectedNote('')
    setCustomNote('')
    setDragX(0)
  }

  function handleAdvance() {
    if (!current) return
    const nextStatus = STATUS_NEXT[current.status]
    if (!nextStatus) return
    advanceMutation.mutate({ id: current.id, status: nextStatus, note: selectedNote || customNote || undefined })
  }

  function handleSaveNote() {
    if (!current) return
    const note = selectedNote || customNote
    if (!note.trim()) return
    noteMutation.mutate({ id: current.id, note: note.trim() })
  }

  function handleSkip() {
    if (!currentId) return
    setQueueOrder(prev => prev ? [...prev.filter(id => id !== currentId), currentId] : prev)
    resetPanel()
  }

  function toggleClaim() {
    if (!currentId) return
    setClaimed(prev => {
      const n = new Set(prev)
      n.has(currentId) ? n.delete(currentId) : n.add(currentId)
      saveClaimed(n)
      return n
    })
  }

  // ── Pointer / swipe ────────────────────────────────────────────────────────

  function onPointerDown(e: React.PointerEvent) {
    if (cardState !== 'view') return
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
    if (dragX > SWIPE_THRESHOLD) { setDragX(0); setCardState('advance') }
    else if (dragX < -SWIPE_THRESHOLD) { handleSkip() }
    else setDragX(0)
  }

  // ── Derived ────────────────────────────────────────────────────────────────

  const rotation = Math.min(Math.max(dragX / 18, -12), 12)
  const advanceHint = dragX > SWIPE_THRESHOLD * 0.4
  const skipHint = dragX < -SWIPE_THRESHOLD * 0.4
  const nextStatus = current ? STATUS_NEXT[current.status] : null
  const advanceChips = nextStatus ? (ADVANCE_NOTE_CHIPS[nextStatus] ?? []) : []
  const noteChips = current ? (STATUS_NOTE_CHIPS[current.status] ?? []) : []
  const collectionUrgency = current ? getCollectionUrgency(current.collection_date) : 2
  const days = current ? daysInShop(current.created_at) : 0

  const isPending = advanceMutation.isPending || noteMutation.isPending

  // ── Loading ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.85)' }}>
        <Spinner />
      </div>
    )
  }

  // ── Empty / all done ───────────────────────────────────────────────────────

  if (!current) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ backgroundColor: 'rgba(15,15,30,0.97)' }}>
        <div className="rounded-2xl p-8 text-center w-full max-w-sm" style={{ backgroundColor: 'var(--cafe-bg-card)' }}>
          <CheckCircle size={52} className="mx-auto mb-4" style={{ color: '#68d391' }} />
          <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--cafe-text)' }}>Queue Clear!</h2>
          <p className="text-sm mb-6" style={{ color: 'var(--cafe-text-muted)' }}>
            All {mode === 'watch' ? 'watch' : 'shoe'} repairs have been reviewed.
          </p>
          <button onClick={onClose} className="px-8 py-2.5 rounded-xl font-semibold" style={{ backgroundColor: 'var(--cafe-accent)', color: '#fff' }}>
            Done
          </button>
        </div>
      </div>
    )
  }

  // ── Main ───────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ backgroundColor: '#0f0f1e' }}>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="flex items-center gap-3">
          <span className="text-white font-bold text-lg">{mode === 'watch' ? 'Watch' : 'Shoe'} Queue</span>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)' }}>
            {doneCount} done · {remaining} left
          </span>
        </div>
        <button onClick={onClose} className="p-2 rounded-full" style={{ color: 'rgba(255,255,255,0.5)' }}>
          <X size={20} />
        </button>
      </div>

      {/* Progress bar */}
      {(doneCount + remaining) > 0 && (
        <div className="h-1" style={{ backgroundColor: 'rgba(255,255,255,0.07)' }}>
          <div className="h-full transition-all duration-300" style={{ width: `${(doneCount / (doneCount + remaining)) * 100}%`, backgroundColor: '#68d391' }} />
        </div>
      )}

      {/* Card area */}
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-6 relative overflow-hidden">

        {/* Swipe hints */}
        {skipHint && cardState === 'view' && (
          <div className="absolute left-5 top-1/2 z-20 pointer-events-none" style={{ transform: 'translateY(-50%) rotate(-12deg)', opacity: Math.min(1, Math.abs(dragX) / SWIPE_THRESHOLD) }}>
            <span className="block px-4 py-2 rounded-xl font-black text-xl text-white" style={{ backgroundColor: '#e53e3e', border: '3px solid #fc8181' }}>SKIP</span>
          </div>
        )}
        {advanceHint && cardState === 'view' && (
          <div className="absolute right-5 top-1/2 z-20 pointer-events-none" style={{ transform: 'translateY(-50%) rotate(12deg)', opacity: Math.min(1, dragX / SWIPE_THRESHOLD) }}>
            <span className="block px-4 py-2 rounded-xl font-black text-xl text-white" style={{ backgroundColor: '#38a169', border: '3px solid #68d391' }}>ADVANCE</span>
          </div>
        )}

        {/* ── VIEW card ── */}
        {cardState === 'view' && (
          <div
            ref={cardRef}
            className="w-full max-w-sm rounded-2xl shadow-2xl"
            style={{
              backgroundColor: 'var(--cafe-bg-card)',
              transform: `translateX(${dragX}px) rotate(${rotation}deg)`,
              transition: isDragging ? 'none' : 'transform 0.35s cubic-bezier(0.34,1.56,0.64,1)',
              touchAction: 'none', userSelect: 'none',
              cursor: isDragging ? 'grabbing' : 'grab',
            }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {/* Priority + claimed bar */}
            <div className="h-2 rounded-t-2xl flex overflow-hidden">
              <div className="flex-1" style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#718096' }} />
              {isClaimed && <div className="w-8" style={{ backgroundColor: '#319795' }} />}
            </div>

            <div className="p-5">
              {/* Job number row */}
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-3xl font-black tracking-tight" style={{ color: 'var(--cafe-text)' }}>{current.job_number}</div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {days === 0 ? 'Today' : days === 1 ? '1 day in shop' : `${days} days in shop`}
                    </span>
                    {collectionUrgency === 0 && (
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#e53e3e', color: '#fff' }}>DUE TODAY</span>
                    )}
                    {collectionUrgency === 1 && (
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#dd6b20', color: '#fff' }}>DUE TOMORROW</span>
                    )}
                    {isClaimed && (
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#319795', color: '#fff' }}>YOU'RE ON IT</span>
                    )}
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase text-white shrink-0" style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#718096' }}>
                  {current.priority}
                </span>
              </div>

              {/* Title + customer */}
              <div className="text-lg font-semibold leading-snug mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.title}</div>
              {current.customer_name && (
                <div className="text-sm mb-2" style={{ color: 'var(--cafe-text-muted)' }}>{current.customer_name}</div>
              )}

              {/* Context: shoe items or watch description */}
              {current.type === 'shoe' && current.items && current.items.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {current.items.slice(0, 4).map((item, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.07)', color: 'var(--cafe-text-muted)' }}>{item}</span>
                  ))}
                  {current.items.length > 4 && (
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.07)', color: 'var(--cafe-text-muted)' }}>+{current.items.length - 4} more</span>
                  )}
                </div>
              )}
              {current.type === 'watch' && current.description && (
                <p className="text-xs mb-2 line-clamp-2" style={{ color: 'var(--cafe-text-muted)' }}>{current.description}</p>
              )}

              {/* Recommended action */}
              {RECOMMENDED_ACTION[current.status] && (
                <div className="flex items-center gap-1.5 mb-3 mt-1">
                  <ChevronRight size={13} style={{ color: 'var(--cafe-accent)', flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: 'var(--cafe-accent)' }}>{RECOMMENDED_ACTION[current.status]}</span>
                </div>
              )}

              {/* Status → next status */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <span className="text-xs px-2.5 py-1 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.07)', color: 'var(--cafe-text-muted)' }}>
                  {STATUS_LABELS[current.status] ?? current.status}
                </span>
                {nextStatus && (
                  <>
                    <ChevronRight size={13} style={{ color: 'rgba(255,255,255,0.3)' }} />
                    <span className="text-xs px-2.5 py-1 rounded-full" style={{ backgroundColor: 'rgba(104,211,145,0.12)', color: '#68d391' }}>
                      {STATUS_LABELS[nextStatus] ?? nextStatus}
                    </span>
                  </>
                )}
              </div>

              {/* Card action row */}
              <div className="flex gap-2 pt-1" style={{ borderTop: '1px solid rgba(255,255,255,0.07)' }}>
                <button
                  onClick={() => { setCardState('note'); setSelectedNote(''); setCustomNote('') }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                  style={{ backgroundColor: 'rgba(255,255,255,0.06)', color: 'var(--cafe-text-muted)' }}
                >
                  <StickyNote size={13} /> Add Note
                </button>
                <button
                  onClick={toggleClaim}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                  style={{
                    backgroundColor: isClaimed ? 'rgba(49,151,149,0.2)' : 'rgba(255,255,255,0.06)',
                    color: isClaimed ? '#81e6d9' : 'var(--cafe-text-muted)',
                  }}
                >
                  <Wrench size={13} /> {isClaimed ? 'Release' : 'Claim'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── ADVANCE panel ── */}
        {cardState === 'advance' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-bg-card)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: '#38a169' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: '#68d391' }}>
                Advance to: <strong>{STATUS_LABELS[nextStatus!] ?? nextStatus}</strong>
              </div>
              {advanceChips.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Add a note (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {advanceChips.map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }}
                        className="px-3 py-1 rounded-full text-xs font-medium transition-all"
                        style={{ backgroundColor: selectedNote === chip ? 'var(--cafe-accent)' : 'rgba(255,255,255,0.07)', color: selectedNote === chip ? '#fff' : 'var(--cafe-text-muted)', border: `1px solid ${selectedNote === chip ? 'var(--cafe-accent)' : 'rgba(255,255,255,0.12)'}` }}>
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Or type a custom note…" value={customNote}
                onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }}
                className="w-full px-3 py-2 rounded-lg text-sm mb-4"
                style={{ backgroundColor: 'rgba(255,255,255,0.06)', color: 'var(--cafe-text)', border: '1px solid rgba(255,255,255,0.12)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold" style={{ backgroundColor: 'rgba(255,255,255,0.07)', color: 'var(--cafe-text-muted)' }}>Cancel</button>
                <button onClick={handleAdvance} disabled={isPending} className="flex-1 py-2.5 rounded-xl text-sm font-bold"
                  style={{ backgroundColor: '#38a169', color: '#fff', opacity: isPending ? 0.65 : 1 }}>
                  {isPending ? 'Saving…' : 'Confirm'}
                </button>
              </div>
              {advanceMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#fc8181' }}>Failed to update — try again.</p>}
            </div>
          </div>
        )}

        {/* ── NOTE panel ── */}
        {cardState === 'note' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-bg-card)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: '#d69e2e' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: '#f6e05e' }}>Add a note (status unchanged)</div>
              {noteChips.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Quick notes</div>
                  <div className="flex flex-wrap gap-2">
                    {noteChips.map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }}
                        className="px-3 py-1 rounded-full text-xs font-medium transition-all"
                        style={{ backgroundColor: selectedNote === chip ? '#d69e2e' : 'rgba(255,255,255,0.07)', color: selectedNote === chip ? '#fff' : 'var(--cafe-text-muted)', border: `1px solid ${selectedNote === chip ? '#d69e2e' : 'rgba(255,255,255,0.12)'}` }}>
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Type a note…" value={customNote}
                onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }}
                className="w-full px-3 py-2 rounded-lg text-sm mb-4"
                style={{ backgroundColor: 'rgba(255,255,255,0.06)', color: 'var(--cafe-text)', border: '1px solid rgba(255,255,255,0.12)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold" style={{ backgroundColor: 'rgba(255,255,255,0.07)', color: 'var(--cafe-text-muted)' }}>Cancel</button>
                <button onClick={handleSaveNote} disabled={isPending || (!selectedNote && !customNote.trim())}
                  className="flex-1 py-2.5 rounded-xl text-sm font-bold"
                  style={{ backgroundColor: '#d69e2e', color: '#fff', opacity: isPending || (!selectedNote && !customNote.trim()) ? 0.5 : 1 }}>
                  {isPending ? 'Saving…' : 'Save Note'}
                </button>
              </div>
              {noteMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#fc8181' }}>Failed to save note — try again.</p>}
            </div>
          </div>
        )}

        {/* Swipe hint */}
        {cardState === 'view' && (
          <p className="mt-8 text-xs text-center select-none" style={{ color: 'rgba(255,255,255,0.18)' }}>
            <span style={{ color: 'rgba(229,62,62,0.5)' }}>← skip</span>{'  ·  '}
            <span style={{ color: 'rgba(56,161,105,0.5)' }}>advance →</span>
          </p>
        )}
      </div>

      {/* Bottom buttons — only in view state */}
      {cardState === 'view' && (
        <div className="px-5 pb-8 pt-2 flex gap-4">
          <button onClick={handleSkip} className="flex-1 py-3.5 rounded-2xl font-semibold flex items-center justify-center gap-2 text-sm"
            style={{ backgroundColor: 'rgba(229,62,62,0.12)', color: '#fc8181', border: '1px solid rgba(229,62,62,0.25)' }}>
            <SkipForward size={16} /> Skip
          </button>
          <button onClick={() => setCardState('advance')} disabled={!nextStatus} className="py-3.5 rounded-2xl font-semibold flex items-center justify-center gap-2 text-sm"
            style={{ flex: 2, backgroundColor: nextStatus ? 'rgba(56,161,105,0.18)' : 'rgba(255,255,255,0.05)', color: nextStatus ? '#68d391' : 'rgba(255,255,255,0.25)', border: `1px solid ${nextStatus ? 'rgba(56,161,105,0.35)' : 'rgba(255,255,255,0.08)'}` }}>
            <ChevronRight size={16} /> Advance Status
          </button>
        </div>
      )}
    </div>
  )
}
