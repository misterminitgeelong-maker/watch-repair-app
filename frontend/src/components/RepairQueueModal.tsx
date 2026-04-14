import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, ChevronRight, SkipForward, CheckCircle, StickyNote, Wrench, CheckCheck } from 'lucide-react'
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
  items?: string[]
  quote_status?: string
  type: 'watch' | 'shoe'
}

interface Props {
  mode: 'watch' | 'shoe'
  onClose: () => void
}

type CardState = 'view' | 'advance' | 'note' | 'noUpdate'

// ── Constants ──────────────────────────────────────────────────────────────────

const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 }

const PRIORITY_COLORS: Record<string, string> = {
  urgent: '#C0392B',
  high: '#D4693A',
  normal: '#7A5D2E',
  low: '#8A7563',
}

const STATUS_NEXT: Record<string, string> = {
  awaiting_quote: 'awaiting_go_ahead',
  awaiting_go_ahead: 'go_ahead',
  go_ahead: 'working_on',
  working_on: 'completed',
  completed: 'awaiting_collection',
  awaiting_collection: 'collected',
}

const ADVANCE_NOTE_CHIPS: Record<string, string[]> = {
  awaiting_go_ahead: ['Called customer', 'Left voicemail', 'Sent SMS', 'Emailed customer'],
  go_ahead: ['Confirmed by phone', 'Confirmed by SMS', 'Customer came in'],
  working_on: ['Parts sourced', 'Started service', 'Battery replaced', 'Crystal replaced'],
  completed: ['Service complete', 'Pressure tested', 'Timekeeping checked'],
  awaiting_collection: ['Customer notified', 'SMS sent', 'Called customer'],
  collected: ['Customer collected', 'Shipped to customer'],
}

const STATUS_NOTE_CHIPS: Record<string, string[]> = {
  awaiting_quote: ['Needs parts assessment', 'Complex movement', 'Awaiting supplier quote', 'Rush job'],
  awaiting_go_ahead: ['Called — no answer', 'SMS sent', 'Quote expires soon', 'Customer reconsidering'],
  go_ahead: ['Parts ordered', 'Sourcing parts', 'Waiting on delivery'],
  working_on: ['Waiting on parts', 'Movement stripped', 'Parts arrived', 'Extra time needed'],
  completed: ['Invoice ready', 'Tested and passed'],
  awaiting_collection: ['Reminder sent', 'Left message'],
}

// Quick-reason chips for "no update / checked in"
const NO_UPDATE_CHIPS: Record<string, string[]> = {
  awaiting_quote: ['Still assessing', 'Awaiting parts price', 'Complex job — more time needed'],
  awaiting_go_ahead: ['Waiting on customer', 'Customer not responding', 'Quote sent — awaiting reply'],
  go_ahead: ['Parts not arrived yet', 'Waiting on supplier', 'Backlogged'],
  working_on: ['Waiting on parts', 'Still in progress', 'Waiting on tools'],
  completed: ['Awaiting customer collection', 'Will notify shortly'],
  awaiting_collection: ['Customer unavailable', 'Will call again'],
}

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
        .map(j => ({ id: j.id, job_number: j.job_number, title: j.title, priority: j.priority, status: j.status, created_at: j.created_at, collection_date: j.collection_date, customer_name: j.customer_name, description: j.description, type: 'watch' as const }))
    : ((shoeQuery.data ?? []) as ShoeRepairJob[])
        .filter(j => !EXCLUDE_STATUSES.has(j.status))
        .map(j => ({ id: j.id, job_number: j.job_number, title: j.title, priority: j.priority, status: j.status, created_at: j.created_at, collection_date: j.collection_date, customer_name: undefined, description: j.description, items: j.items?.map(i => i.item_name).filter(Boolean), quote_status: j.quote_status, type: 'shoe' as const }))

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
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: mode === 'watch' ? ['repair-jobs'] : ['shoe-repair-jobs'] })
      // If this was a "no update" check-in, mark as done in this session
      if (cardState === 'noUpdate') {
        setDone(prev => new Set([...prev, vars.id]))
      }
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

  function handleCheckedIn() {
    if (!current) return
    const note = selectedNote || customNote || 'Checked in — no update'
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
  // We delay setPointerCapture until the user has actually moved horizontally
  // so that taps on inner buttons still fire their click events normally.

  const pointerIdRef = useRef<number | null>(null)
  const capturedRef = useRef(false)

  function onPointerDown(e: React.PointerEvent) {
    if (cardState !== 'view') return
    dragStartX.current = e.clientX
    pointerIdRef.current = e.pointerId
    capturedRef.current = false
    setIsDragging(true)
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!isDragging || dragStartX.current === null) return
    const dx = e.clientX - dragStartX.current
    // Only capture once a real horizontal drag is detected
    if (!capturedRef.current && Math.abs(dx) > 6) {
      cardRef.current?.setPointerCapture(e.pointerId)
      capturedRef.current = true
    }
    if (capturedRef.current) setDragX(dx)
  }
  function onPointerUp() {
    if (!isDragging) return
    setIsDragging(false)
    dragStartX.current = null
    pointerIdRef.current = null
    capturedRef.current = false
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
  const noUpdateChips = current ? (NO_UPDATE_CHIPS[current.status] ?? []) : []
  const collectionUrgency = current ? getCollectionUrgency(current.collection_date) : 2
  const days = current ? daysInShop(current.created_at) : 0
  const isPending = advanceMutation.isPending || noteMutation.isPending

  // ── Shared panel styles ────────────────────────────────────────────────────

  const chipBase = 'px-3 py-1 rounded-full text-xs font-medium transition-all border'

  function chipStyle(active: boolean, activeColor = 'var(--cafe-gold)') {
    return {
      backgroundColor: active ? activeColor : 'rgba(31,23,18,0.06)',
      color: active ? '#fff' : 'var(--cafe-text-muted)',
      borderColor: active ? activeColor : 'var(--cafe-border)',
    }
  }

  // ── Loading ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(31,23,18,0.92)' }}>
        <Spinner />
      </div>
    )
  }

  // ── Empty ──────────────────────────────────────────────────────────────────

  if (!current) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ backgroundColor: 'rgba(31,23,18,0.97)' }}>
        <div className="rounded-2xl p-8 text-center w-full max-w-sm" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
          <CheckCircle size={52} className="mx-auto mb-4" style={{ color: 'var(--cafe-gold)' }} />
          <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--cafe-text)' }}>Queue Clear!</h2>
          <p className="text-sm mb-6" style={{ color: 'var(--cafe-text-muted)' }}>
            All {mode === 'watch' ? 'watch' : 'shoe'} repairs have been reviewed.
          </p>
          <button onClick={onClose} className="px-8 py-2.5 rounded-xl font-semibold" style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff' }}>
            Done
          </button>
        </div>
      </div>
    )
  }

  // ── Main ───────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ backgroundColor: '#1F1712' }}>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="flex items-center gap-3">
          <span className="font-bold text-lg" style={{ color: '#FCFAF6', fontFamily: "'Playfair Display', Georgia, serif" }}>
            {mode === 'watch' ? 'Watch' : 'Shoe'} Queue
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(184,149,86,0.15)', color: '#B89556' }}>
            {doneCount} done · {remaining} left
          </span>
        </div>
        <button onClick={onClose} className="p-2 rounded-full" style={{ color: '#8A7563' }}>
          <X size={20} />
        </button>
      </div>

      {/* Progress bar — gold */}
      {(doneCount + remaining) > 0 && (
        <div className="h-1" style={{ backgroundColor: 'rgba(184,149,86,0.15)' }}>
          <div className="h-full transition-all duration-300" style={{ width: `${(doneCount / (doneCount + remaining)) * 100}%`, backgroundColor: 'var(--cafe-gold)' }} />
        </div>
      )}

      {/* Card area */}
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-6 relative overflow-hidden">

        {/* Swipe hints */}
        {skipHint && cardState === 'view' && (
          <div className="absolute left-5 top-1/2 z-20 pointer-events-none" style={{ transform: 'translateY(-50%) rotate(-12deg)', opacity: Math.min(1, Math.abs(dragX) / SWIPE_THRESHOLD) }}>
            <span className="block px-4 py-2 rounded-xl font-black text-base" style={{ backgroundColor: '#3B2F27', color: '#D3C8BA', border: '2px solid #5F4D3E' }}>SKIP</span>
          </div>
        )}
        {advanceHint && cardState === 'view' && (
          <div className="absolute right-5 top-1/2 z-20 pointer-events-none" style={{ transform: 'translateY(-50%) rotate(12deg)', opacity: Math.min(1, dragX / SWIPE_THRESHOLD) }}>
            <span className="block px-4 py-2 rounded-xl font-black text-base" style={{ backgroundColor: '#B89556', color: '#fff', border: '2px solid #D4AF5E' }}>ADVANCE</span>
          </div>
        )}

        {/* ── VIEW card ── */}
        {cardState === 'view' && (
          <div
            ref={cardRef}
            className="w-full max-w-sm rounded-2xl shadow-2xl"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              border: '1px solid var(--cafe-border)',
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
            {/* Priority bar */}
            <div className="h-2 rounded-t-2xl flex overflow-hidden">
              <div className="flex-1" style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#8A7563' }} />
              {isClaimed && <div className="w-6" style={{ backgroundColor: 'var(--cafe-gold)' }} />}
            </div>

            <div className="p-5">
              {/* Job number row */}
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-3xl font-black tracking-tight" style={{ color: 'var(--cafe-espresso)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                    {current.job_number}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                    <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                      {days === 0 ? 'Today' : days === 1 ? '1 day in shop' : `${days} days in shop`}
                    </span>
                    {collectionUrgency === 0 && (
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#C0392B', color: '#fff' }}>DUE TODAY</span>
                    )}
                    {collectionUrgency === 1 && (
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: '#D4693A', color: '#fff' }}>DUE TOMORROW</span>
                    )}
                    {isClaimed && (
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff' }}>ON IT</span>
                    )}
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase text-white shrink-0" style={{ backgroundColor: PRIORITY_COLORS[current.priority] ?? '#8A7563' }}>
                  {current.priority}
                </span>
              </div>

              {/* Title + customer */}
              <div className="text-lg font-semibold leading-snug mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.title}</div>
              {current.customer_name && (
                <div className="text-sm mb-2" style={{ color: 'var(--cafe-text-muted)' }}>{current.customer_name}</div>
              )}

              {/* Context */}
              {current.type === 'shoe' && current.items && current.items.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {current.items.slice(0, 4).map((item, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>{item}</span>
                  ))}
                  {current.items.length > 4 && (
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>+{current.items.length - 4} more</span>
                  )}
                </div>
              )}
              {current.type === 'watch' && current.description && (
                <p className="text-xs mb-2 line-clamp-2" style={{ color: 'var(--cafe-text-muted)' }}>{current.description}</p>
              )}

              {/* Recommended action */}
              {RECOMMENDED_ACTION[current.status] && (
                <div className="flex items-center gap-1.5 mb-3 mt-1">
                  <ChevronRight size={13} style={{ color: 'var(--cafe-gold)', flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: 'var(--cafe-amber)' }}>{RECOMMENDED_ACTION[current.status]}</span>
                </div>
              )}

              {/* Status → next status pills */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <span className="text-xs px-2.5 py-1 rounded-full" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>
                  {STATUS_LABELS[current.status] ?? current.status}
                </span>
                {nextStatus && (
                  <>
                    <ChevronRight size={13} style={{ color: 'var(--cafe-border-2)' }} />
                    <span className="text-xs px-2.5 py-1 rounded-full" style={{ backgroundColor: 'rgba(184,149,86,0.12)', color: 'var(--cafe-gold-dark)', border: '1px solid rgba(184,149,86,0.25)' }}>
                      {STATUS_LABELS[nextStatus] ?? nextStatus}
                    </span>
                  </>
                )}
              </div>

              {/* Card action row */}
              <div className="flex gap-2 pt-2" style={{ borderTop: '1px solid var(--cafe-border)' }}>
                <button
                  onPointerDown={e => e.stopPropagation()}
                  onClick={() => { setCardState('note'); setSelectedNote(''); setCustomNote('') }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                  style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>
                  <StickyNote size={13} /> Add Note
                </button>
                <button
                  onPointerDown={e => e.stopPropagation()}
                  onClick={toggleClaim}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                  style={{ backgroundColor: isClaimed ? 'rgba(184,149,86,0.12)' : 'var(--cafe-bg)', color: isClaimed ? 'var(--cafe-gold-dark)' : 'var(--cafe-text-muted)', border: `1px solid ${isClaimed ? 'rgba(184,149,86,0.4)' : 'var(--cafe-border)'}` }}>
                  <Wrench size={13} /> {isClaimed ? 'Release' : 'Claim'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── ADVANCE panel ── */}
        {cardState === 'advance' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: 'var(--cafe-gold)' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: 'var(--cafe-amber)' }}>
                Advance to: <strong>{STATUS_LABELS[nextStatus!] ?? nextStatus}</strong>
              </div>
              {advanceChips.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Add a note (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {advanceChips.map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }}
                        className={chipBase} style={chipStyle(selectedNote === chip)}>{chip}</button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Or type a custom note…" value={customNote}
                onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }}
                className="w-full px-3 py-2 rounded-lg text-sm mb-4"
                style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>Cancel</button>
                <button onClick={handleAdvance} disabled={isPending} className="flex-1 py-2.5 rounded-xl text-sm font-bold"
                  style={{ backgroundColor: 'var(--cafe-gold)', color: '#fff', opacity: isPending ? 0.65 : 1 }}>
                  {isPending ? 'Saving…' : 'Confirm'}
                </button>
              </div>
              {advanceMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#C0392B' }}>Failed to update — try again.</p>}
            </div>
          </div>
        )}

        {/* ── ADD NOTE panel ── */}
        {cardState === 'note' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: 'var(--cafe-espresso-3)' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Add a note — status unchanged</div>
              {noteChips.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Quick notes</div>
                  <div className="flex flex-wrap gap-2">
                    {noteChips.map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }}
                        className={chipBase} style={chipStyle(selectedNote === chip, 'var(--cafe-espresso-3)')}>{chip}</button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Type a note…" value={customNote}
                onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }}
                className="w-full px-3 py-2 rounded-lg text-sm mb-4"
                style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>Cancel</button>
                <button onClick={handleSaveNote} disabled={isPending || (!selectedNote && !customNote.trim())}
                  className="flex-1 py-2.5 rounded-xl text-sm font-bold"
                  style={{ backgroundColor: 'var(--cafe-espresso-2)', color: '#D5C8BB', opacity: isPending || (!selectedNote && !customNote.trim()) ? 0.5 : 1 }}>
                  {isPending ? 'Saving…' : 'Save Note'}
                </button>
              </div>
              {noteMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#C0392B' }}>Failed to save — try again.</p>}
            </div>
          </div>
        )}

        {/* ── NO UPDATE / CHECKED IN panel ── */}
        {cardState === 'noUpdate' && (
          <div className="w-full max-w-sm rounded-2xl shadow-2xl" style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}>
            <div className="h-2 rounded-t-2xl" style={{ backgroundColor: 'var(--cafe-border-2)' }} />
            <div className="p-5">
              <div className="font-bold text-base mb-0.5" style={{ color: 'var(--cafe-text)' }}>{current.job_number} — {current.title}</div>
              <div className="text-sm mb-4" style={{ color: 'var(--cafe-text-muted)' }}>Mark as checked in — no update needed right now</div>
              {noUpdateChips.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Reason (optional)</div>
                  <div className="flex flex-wrap gap-2">
                    {noUpdateChips.map(chip => (
                      <button key={chip} onClick={() => { setSelectedNote(p => p === chip ? '' : chip); setCustomNote('') }}
                        className={chipBase} style={chipStyle(selectedNote === chip, 'var(--cafe-text-muted)')}>{chip}</button>
                    ))}
                  </div>
                </div>
              )}
              <input type="text" placeholder="Add a reason (optional)…" value={customNote}
                onChange={e => { setCustomNote(e.target.value); setSelectedNote('') }}
                className="w-full px-3 py-2 rounded-lg text-sm mb-4"
                style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)', border: '1px solid var(--cafe-border)', outline: 'none' }} />
              <div className="flex gap-3">
                <button onClick={resetPanel} className="flex-1 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)', border: '1px solid var(--cafe-border)' }}>Cancel</button>
                <button onClick={handleCheckedIn} disabled={isPending}
                  className="flex-1 py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2"
                  style={{ backgroundColor: 'var(--cafe-espresso)', color: '#D5C8BB', opacity: isPending ? 0.65 : 1 }}>
                  <CheckCheck size={15} />
                  {isPending ? 'Saving…' : 'Checked In'}
                </button>
              </div>
              {noteMutation.isError && <p className="text-xs mt-2 text-center" style={{ color: '#C0392B' }}>Failed to save — try again.</p>}
            </div>
          </div>
        )}

        {/* Swipe hint */}
        {cardState === 'view' && (
          <p className="mt-8 text-xs text-center select-none" style={{ color: 'rgba(184,149,86,0.3)' }}>
            <span>← skip</span>{'  ·  '}<span>advance →</span>
          </p>
        )}
      </div>

      {/* Bottom buttons */}
      {cardState === 'view' && (
        <div className="px-5 pb-8 pt-2 flex gap-3">
          {/* Skip */}
          <button onClick={handleSkip}
            className="flex-1 py-3 rounded-2xl font-semibold flex items-center justify-center gap-1.5 text-sm"
            style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#8A7563', border: '1px solid rgba(255,255,255,0.1)' }}>
            <SkipForward size={15} /> Skip
          </button>
          {/* No Update */}
          <button onClick={() => { setCardState('noUpdate'); setSelectedNote(''); setCustomNote('') }}
            className="flex-1 py-3 rounded-2xl font-semibold flex items-center justify-center gap-1.5 text-sm"
            style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#D5C8BB', border: '1px solid rgba(255,255,255,0.1)' }}>
            <CheckCheck size={15} /> No Update
          </button>
          {/* Advance */}
          <button onClick={() => setCardState('advance')} disabled={!nextStatus}
            className="flex-1 py-3 rounded-2xl font-semibold flex items-center justify-center gap-1.5 text-sm"
            style={{ backgroundColor: nextStatus ? 'var(--cafe-gold)' : 'rgba(255,255,255,0.05)', color: nextStatus ? '#fff' : 'rgba(255,255,255,0.2)', border: 'none' }}>
            <ChevronRight size={15} /> Advance
          </button>
        </div>
      )}
    </div>
  )
}
